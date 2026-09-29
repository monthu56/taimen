
# API

Reference for the Control Plane HTTP API. All endpoints live under `/api/v1`,
and request and response body fields use camelCase. This page describes the
common rules (authentication, headers, pagination, idempotency, error format)
and lists every endpoint with its permission and purpose, grouped by resource.
It is a reference for developers of integrations and harnesses.

!!! tip "Machine-readable schema"
    The service itself serves the full OpenAPI schema: `GET /openapi.json`,
    Swagger UI at `GET /docs`. The reference below is built from the same schema
    and from the command code that checks permissions.

## Base address

| Where | Address |
|---|---|
| Inside the compose network | `http://control-plane-api:8000` |
| From the host (loopback only by default) | `http://127.0.0.1:${CP_HOST_PORT:-18000}` |
| From outside through the edge | `https://platform.example.com` (routes `/api/v1/*`, `/health/*`, `/metrics`, `/docs*`, `/openapi.json`) |

The edge layout is described in [Edge and TLS](../operations/edge-and-tls.md).

## Authentication

```http
Authorization: Bearer <access-token IAM audience control-plane>
```

- IAM access token: permissions come from the binding of the identity to a
  principal and are narrowed by the token scopes (`control-plane:read`,
  `control-plane:write`, `control-plane:admin`).
- A legacy key `cp_<prefix>_<secret>` is accepted only when
  `CP_LEGACY_API_KEYS_ENABLED=true`.
- `POST /api/v1/bootstrap` accepts only `Bearer <CP_BOOTSTRAP_TOKEN>`.
- `/health/live`, `/health/ready`, and `/metrics` are open without authentication.

The actor is always derived from the credential. Details are in
[Authorization and permissions](authorization.md).

## Protocol headers

| Header | Direction | Semantics |
|---|---|---|
| `Idempotency-Key` | request, mutations | idempotent execution, see [Idempotency](#idempotency) |
| `Idempotency-Replayed: true` | response | the response comes from storage; the command was not executed again |
| `If-Match: "<entity>-<version>"` | request | optimistic locking: PATCH of a task, workspace, workspace type, project, role, skill, goal, and comment; task `:complete`; project `:transition`; `config-revisions/{n}:activate` |
| `ETag` | response | `"<entity>-<version>"` on GET of a task (`task-`), workspace (`workspace-`), workspace type (`workspace_type-`), project (`project-`), role (`role-`), skill (`skill-<rowVersion>`), goal (`goal-`), comment (`comment-`); on `GET /tools` it is the `viewHash` |
| `If-None-Match` | request | for `GET /tools`: `304` while the catalog and policy revisions are unchanged |
| `X-Request-ID` | both | accepted or generated; returned in the response and in `error.requestId` |
| `X-Correlation-ID` | request | goes into the `correlationId` of events |
| `X-Run-Id` | both | end-to-end trace correlator (`^[A-Za-z0-9._:-]{1,128}$`, otherwise generated); written to the `traceRunId` of events, the outbox, logs, and the header sent to memory-service. It is **not** the Run entity |

`If-Match` errors:

| Situation | Response |
|---|---|
| header missing | `428 if_match_required` |
| header cannot be parsed | `400 invalid_if_match` |
| version mismatch | `409 version_conflict`, `details.currentVersion` holds the current version |

## Pagination

```text
GET /api/v1/tasks?limit=50&cursor=<opaque>
```

```json
{"items": [ ... ], "nextCursor": "..."}
```

- `limit`: 50 by default, 200 maximum. A value out of range returns
  `422 invalid_limit`.
- The cursor is opaque. A foreign cursor or a cursor from a different sort
  order returns `422 invalid_cursor`.
- Entity lists are sorted stably by `(created_at, id)`, newest first.
- Run logs (`/runs/{id}/checkpoints`, `/runs/{id}/actions`) are ordered by
  `seq`, oldest first, and the cursor is bound to the run. Without `limit` and
  `cursor` the whole log is returned as a single page (`nextCursor: null`).
- Task comments are the only entity listing ordered from oldest to newest. Its
  cursor has its own format.
- `GET /tasks?sort=startDate|dueDate`: nearest first, tasks without a date at
  the end. An unknown `sort` returns `422 invalid_sort`.
- `GET /work/available` can return a page shorter than `limit` with a non-empty
  `nextCursor`.

### Events

`GET /events` has its own contract:

| Parameter | Meaning |
|---|---|
| `cursor` | opaque cursor `ec1_…` |
| `after` | integer `sequence` in the old format; the server adapts it |
| `tail=N` | the last N stable events |
| `entityType`, `entityId` | filter by entity |
| `types` | event type prefixes, up to 20 |
| `workspaceId` | workspace subtree; `events.read` is checked on it |
| `limit` | page size |

Response: `{items[], nextCursor, hasMore}`; each event has its own `cursor`
field. On an empty page `nextCursor` repeats the one you passed. A malformed
cursor returns `422 invalid_cursor`, a cursor from a future version returns
`422 unsupported_cursor_version`.

WebSocket: `WS /api/v1/events/ws?after=<cursor>`, permission `events.read`.
Close codes: `4401` — no credentials, `4403` — no permission, `4404` — no
workspace for the filter, `4400` — bad cursor or filter, `4503` — PDP
unavailable. Filters and the consumer SDK are covered in
[Event subscriptions](event-subscriptions.md).

## Unknown query parameters

The server does not silently ignore query parameters. A parameter the endpoint
does not declare returns `400 invalid_request`, and the query is not executed:

```json
{
  "error": {
    "code": "invalid_request",
    "message": "Request does not match the API contract",
    "details": {"errors": [{"loc": "query.assignedToMee", "message": "Unknown query parameter: ..."}]},
    "requestId": "req_..."
  }
}
```

The rule applies to all `/api/v1` endpoints except the WebSocket. Do not add
auxiliary parameters such as a cache-buster `_=`: they are rejected too.
Unknown fields in a JSON body are also rejected (`extra="forbid"`), except in
the manifest compilation body.

## Idempotency {#idempotency}

Any mutation (a POST command or PATCH) accepts an `Idempotency-Key` header of
1–200 characters, otherwise `422 invalid_idempotency_key`.

| Situation | Result |
|---|---|
| first request | executed, the response is stored for `CP_IDEMPOTENCY_TTL_SECONDS` (one day) |
| repeat with the same key, method, path, body, and principal | the stored response and `Idempotency-Replayed: true` |
| the same key with a different body **or a different principal** | `409 idempotency_key_reused` |
| parallel duplicate while the first one has not finished | waits up to `CP_IDEMPOTENCY_WAIT_TIMEOUT_SECONDS` (10 s), then `409 idempotency_in_flight` |
| the executor crashed halfway | the unfinished record lives no longer than `CP_IDEMPOTENCY_PENDING_TTL_SECONDS` (60 s) |

One-time secrets are not stored: repeating an API key issuance returns
`key: null`. Two commands require the key: `POST /runs/{id}/control-messages`
and `POST /runs/{id}/child-handles` (without it, `422 idempotency_key_required`).
For `:handoff`, `harness-manifest:compile`, and `:revoke` of a child handle the
key is strongly recommended: a repeat without it after an ambiguous response
becomes a new command.

!!! tip "Client rule"
    One logical call, one key for all transport retries. A retried HTTP request
    must not turn into a second business command. The `control_plane_client`
    SDK does this for you.

## Error format {#errors}

A single envelope with honest HTTP codes. There is never a `200` response with
an error inside.

```json
{
  "error": {
    "code": "task_already_claimed",
    "message": "Task already has an active claim",
    "details": {"taskId": "...", "claimId": "...", "expiresAt": "..."},
    "requestId": "req_..."
  }
}
```

Clients should rely on `code` and `details`, not on the `message` text.

| HTTP | Typical `error.code` |
|---|---|
| 400 | `invalid_request` (contract violation, including an unknown parameter; `details.errors[].loc`), `invalid_if_match`, `invalid_skill_inputs`, `idempotency_key_required` |
| 401 | `invalid_credentials` |
| 403 | `permission_denied` (`details.required`), `principal_not_active`, `delegation_required`, `claim_holder_mismatch`, `session_owner_mismatch`, `bootstrap_disabled`, `permission_escalation`, `not_eligible`, `run_holder_mismatch`, `tool_not_authorized`, `child_grant_exceeded`, `skill_permission_denied`, `skill_side_effect_not_authorized`, `run_owner_mismatch`, `run_id_required`, `scope_not_granted` |
| 404 | `not_found`, `tool_not_found` (an object of another tenant also returns 404: existence is not disclosed) |
| 409 | `version_conflict`, `stale_claim`, `task_already_claimed`, `task_claimed`, `session_expired`, `session_not_active`, `claim_expired`, `claim_not_active`, `claim_not_expired`, `idempotency_key_reused`, `idempotency_in_flight`, `already_bootstrapped`, `task_already_completed`, `task_not_ready`, `run_already_active`, `run_not_active`, `run_in_progress`, `approval_required`, `approval_already_decided`, `budget_exceeded`, `action_already_finished`, `skill_not_invocable`, `stale_invocation_lease`, `outcome_not_replayable`, `snapshot_stale`, `pack_version_conflict`, `retention_blocked_by_consumer`, uniqueness conflicts (`*_exists`, `*_conflict`) |
| 413 | `request_too_large` — body larger than `CP_MAX_BODY_BYTES` |
| 422 | domain validation: `invalid_*`, `task_not_claimable`, `task_cancelled`, `empty_update`, `dependency_cycle`, `workspace_cycle`, `workspace_archived`, `unsupported_protocol_version`, `server_authoritative_section`, `secret_material_rejected`, `child_grant_exceeds_parent`, `child_result_too_large`, `cursor_must_not_advance`, `workspace_not_root`, `pack_*`, `snapshot_invalid`, and others |
| 428 | `if_match_required` |
| 500 | `internal_error` — no stack trace; details are in the log by `requestId` |
| 502 | `memory_unavailable` — memory-service did not process the proxied request (`details.memoryStatus`, `details.retryable`) |
| 503 | `policy_unavailable`, `memory_disabled`; readiness — the database is unreachable or migrations are not applied |

The full registry of codes for all services is in [Error codes](../reference/errors.md).

## Service endpoints

| Method and path | Authentication | Response |
|---|---|---|
| `GET /health/live` | none | `{"status": "alive"}` |
| `GET /health/ready` | none | `200 {"status": "ready", "revision": "<alembic>"}`; `503` with `reason: database_unreachable` or `migrations_pending` (`dbRevision`, `headRevision`) |
| `GET /metrics` | none | Prometheus metrics: `http_requests_total`, `active_harness_sessions`, `active_claims`, `active_runs`, `context_adapter_*`, `stale_fencing_rejections_total`, `authz_*`, and others |
| `GET /openapi.json`, `GET /docs` | none | OpenAPI schema and Swagger UI |

!!! warning "`/metrics` is open"
    The endpoint is not authenticated. Close it at the edge, see
    [Monitoring and health](../operations/monitoring.md).

## Endpoint reference

The "Permission" column lists the permission the server checks. "Owner" means
the holder of the session, claim, or run. `{ref}` for a task is a UUID or a
`publicId` (`TASK-000123`).

### Bootstrap

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | `/bootstrap` | `Bearer <CP_BOOTSTRAP_TOKEN>` | create, once, the tenant, the admin principal, the admin API key, and (with `iamBinding`) the administrator's IAM binding |

Body: `tenantSlug` (`^[a-z0-9][a-z0-9-]*$`, 2–63), `tenantName`,
`adminDisplayName`, `tenantId?` (tenant UUID shared with IAM),
`iamBinding? {issuer, iamTenantId, iamPrincipalId}`. Response `201`:
`{tenant, adminPrincipal, apiKey (with the full key), iamBinding}`.

### Principals, keys, bindings, delegation

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | `/principals` | `principals.write` | create a principal (`kind`: `human`, `agent`, `service`; `displayName`, `status`, `metadata`) |
| GET | `/principals` | `principals.read` | list (`?kind=`) |
| GET | `/principals/{id}` | `principals.read` | principal |
| POST | `/principals/{id}/api-keys` | `principals.write` | issue a legacy key `{permissions, expiresAt?}`; the full key appears only in this response |
| POST | `/api-keys/{id}:revoke` | `principals.write` | revoke a key |
| GET | `/principals/{id}/iam-bindings` | `principals.read` | IAM bindings of the principal, including revoked ones (no pagination) |
| POST | `/principals/{id}/iam-bindings` | `principals.write` | upsert a binding `{issuer, iamTenantId, iamPrincipalId, permissions}`; `201` / `200` |
| POST | `/iam-bindings/{id}:revoke` | `principals.write` | close sign-in for the identity |
| POST | `/delegations` | `delegations.manage` | delegation from a human to an agent |
| GET | `/delegations` | `delegations.manage` | list |
| POST | `/delegations/{id}:revoke` | `delegations.manage` | revoke |

### Sessions and harness

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | `/sessions` | `sessions.open` | open a session; `harness` block; `onBehalfOf` requires a delegation |
| GET | `/sessions` | `sessions.manage` | list (`?status=`) |
| GET | `/sessions/{id}` | owner or `sessions.manage` | session |
| POST | `/sessions/{id}:heartbeat` | owner or `sessions.manage` | extend the lease (`ttlSeconds?`) |
| POST | `/sessions/{id}:close` | owner or `sessions.manage` | close and release the session's claims |
| GET | `/harness/context` | authentication | harness self-context (`?sessionId=`) |
| GET | `/work/available` | `tasks.read` | available work (`workspaceId`, `includeDescendants`, `projectId`, `includeSubprojects`, `assigneeId`, `assignedToMe`) |
| GET | `/tools` | `tasks.read` | tool search (`query`, `runId`); ETag, `If-None-Match` |
| GET | `/tools/{ref}` | `tasks.read` | tool by `uuid`, `name`, or `name@version` (`?runId=`); outside the policy — `404 tool_not_found` |

The protocol is described in detail in [Harness protocol](harness-protocol.md).

### Task types

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | `/task-types` | `task_types.manage` | the next immutable version of a key (`lifecycleSchema`, `fieldSchema`, `approvalSchema`, `execution`) |
| GET | `/task-types` | `task_types.read` | list (`?key=&status=`) |
| GET | `/task-types/{id}` | `task_types.read` | type version |
| POST | `/task-types/{id}:deprecate` | `task_types.manage` | retire a version (idempotent) |

See [Task types and statuses](task-types.md) and [Catalog packages](catalog-packages.md).

### Tasks

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | `/tasks` | `tasks.write` | create a task |
| GET | `/tasks` | `tasks.read` | list: `status`, `systemStatusCategory`, `typeKey`, `priority`, `ownerId`, `assigneeId`, `workspaceId`, `includeDescendants`, `projectId`, `includeSubprojects`, `startFrom`, `startTo`, `dueFrom`, `dueTo`, `sort` (`createdAt`, `startDate`, `dueDate`), `goalId` |
| GET | `/tasks/{ref}` | `tasks.read` | task (+ETag) |
| PATCH | `/tasks/{ref}` | `tasks.write` | update (`If-Match`; with a live claim — `claimId` and `fencingToken`) |
| GET | `/tasks/{ref}/claimability` | `tasks.read` | whether the task can be claimed and why not |
| GET | `/tasks/{ref}/transitions` | `tasks.read` | where the task can move from the current status (`route`: `update` or `complete`) |
| POST | `/tasks/{ref}:claim` | `tasks.claim` | atomic claim `{sessionId, ttlSeconds?, intent?}` → fencing token |
| POST | `/tasks/{ref}:complete` | `tasks.write` | complete (`If-Match`; with a live claim — `claimId` and `fencingToken`) |
| POST | `/tasks/{ref}:start-run` | `tasks.claim` | run under a live claim `{claimId, fencingToken, input?, maxDurationSeconds?, maxActions?}` |
| POST | `/tasks/{ref}/relations` | `tasks.write` | relation `{toTask, type}`: `parent`, `blocks`, `depends_on`, `spawned_by`, `related_to`; cycles — `422` |
| GET | `/tasks/{ref}/relations` | `tasks.read` | relations in both directions |
| DELETE | `/tasks/{ref}/relations/{relationId}` | `tasks.write` | delete a relation |
| GET | `/tasks/{ref}/requirements` | `tasks.read` | requirements (roles, capabilities, skills) |

Example of creating a task:

```bash
curl -s -X POST https://platform.example.com/api/v1/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "title": "Add an index on events(tenant_id, tx_id)",
    "description": "Event log queries hit a seq scan",
    "priority": "high",
    "typeKey": "coding-task",
    "workspaceId": "<workspace-id>",
    "requirements": {"skills": ["git.merge@1"]},
    "acceptance": [{"key": "tests", "kind": "deterministic", "description": "make test passes"}]
  }'
```

`POST /tasks` fields: `title` (1–500), `description`, `priority` (`critical`,
`high`, `medium`, `low`; `medium` by default), `status` (the type's
`initialStatus` by default), `typeId`, `typeKey`, `typeVersion` (the system
type `task` by default), `ownerId`, `assigneeId`, `workspaceId`, `customFields`
(validated against the type version's `fieldSchema`), `startDate`, `dueDate`,
`parentTask` (the `parent` relation is created atomically), `requirements`,
`goalId`, `origin` (immutable; without it the core derives `parent`, `human`,
or `harness`), `acceptance[]`, `evidence[]`. Semantics are covered in
[Work model](work-model.md) and [Goals, acceptance, and evidence](goals-and-evidence.md).

### Goals

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | `/goals` | `goals.write` | goal (`title`, `desiredState`, `criteria[]`, `ownerId`, `workspaceId`, `parentGoalId`, `createdFrom`) |
| GET | `/goals` | `goals.read` | list (`status`, `workspaceId`, `ownerId`, `parentGoalId`) |
| GET | `/goals/{id}` | `goals.read` | goal (+ETag `goal-<v>`) |
| PATCH | `/goals/{id}` | `goals.write` | update (`If-Match`); `status`: `active`, `achieved`, `abandoned`; a cycle — `422 goal_cycle` |
| GET | `/goals/{id}/work` | `goals.read` + `tasks.read` | tasks of the goal, newest first (`includeSubgoals`, `systemStatusCategory`) |

### Task comments

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | `/tasks/{ref}/comments` | `tasks.write` | add `{body, runId?, artifactId?}`; the author is the caller |
| GET | `/tasks/{ref}/comments` | `tasks.read` | thread, oldest to newest |
| GET | `/tasks/{ref}/comments/{id}` | `tasks.read` | comment (+ETag `comment-<v>`) |
| PATCH | `/tasks/{ref}/comments/{id}` | `tasks.write`, author only | correct (`If-Match`); the previous text becomes a revision |
| GET | `/tasks/{ref}/comments/{id}/revisions` | `tasks.read` | edit history (append-only) |

### Claims

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/claims` | `tasks.read` | list (`taskId`, `sessionId`, `status`) |
| GET | `/claims/{id}` | `tasks.read` | claim |
| POST | `/claims/{id}:heartbeat` | holder or `claims.manage` | extend the lease |
| POST | `/claims/{id}:release` | holder or `claims.manage` | release; the task moves to the type's `releaseStatus` if the edge is declared |
| POST | `/claims/{id}:reclaim` | `tasks.claim` | take over an **expired** claim (new token) |

### Runs

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/runs` | `tasks.read` | list (`taskId`, `claimId`, `status`) |
| GET | `/runs/{id}` | `tasks.read` | run |
| GET | `/runs/{id}/context` | `tasks.read` | Run Context |
| POST | `/runs/{id}:succeed` | `tasks.claim`, owner | success `{output?, completeTask=true}` |
| POST | `/runs/{id}:fail` | owner or `claims.manage` | failure (does not touch the task) |
| POST | `/runs/{id}:cancel` | owner or `claims.manage` | cancellation |
| POST | `/runs/{id}:suspend` | `tasks.claim`, owner of the live claim | suspend `{reason, waitingForApprovalId?}` |
| POST | `/runs/{id}:handoff` | `tasks.claim` | hand off to another harness (`Idempotency-Key` recommended) |
| POST | `/runs/{id}:request-cancel` | `tasks.write` or `claims.manage` | cooperative cancellation signal |
| POST | `/runs/{id}/checkpoints` | `tasks.claim`, owner of the live claim | checkpoint `{kind, data}` |
| GET | `/runs/{id}/checkpoints` | `tasks.read` | checkpoints by `seq` |
| POST | `/runs/{id}/actions` | `tasks.claim`, owner of the live claim | action `{action, status, skill?, externalReference?, metadata}`; budget → `409 budget_exceeded` |
| POST | `/runs/{id}/actions/{actionId}:finish` | `tasks.claim` | finish a `started` action |
| GET | `/runs/{id}/actions` | `tasks.read` | action log by `seq` |
| GET | `/runs/{id}/harness-manifest` | `tasks.read` | manifest (`?version=`) |
| GET | `/runs/{id}/harness-manifests` | `tasks.read` | version history |
| POST | `/runs/{id}/harness-manifest:compile` | `tasks.claim`, owner of the live claim | recompile: `200` unchanged, `201` new version |
| POST | `/runs/{id}/harness-manifest/ephemeral` | `tasks.claim` | note `{kind, summary, data}` |
| POST | `/runs/{id}/control-messages` | `tasks.write`; `force_cancel` — `claims.manage` | control message (`Idempotency-Key` and `expectedRunVersion` are required) |
| GET | `/runs/{id}/control-messages` | `tasks.read` | messages, cursor `rc1_…` |
| POST | `/runs/{id}/control-messages/{messageId}:acknowledge` | `tasks.claim`, holder of the live claim | acknowledge `applied`, `rejected`, or `superseded` |
| POST | `/runs/{id}/child-handles` | `tasks.claim` + `tasks.write`, owner of the live claim | launch a child run; `201` new, `200` repeated `correlationId` |
| GET | `/runs/{id}/child-handles` | `tasks.read` | handles of the run (`?active=true`, cursor `cd1_…`) |
| GET | `/child-handles/{idOrToken}` | `tasks.read` | status and result by id or `ch1_…` |
| POST | `/child-handles/{id}:revoke` | holder of the parent run or `claims.manage` | revoke `{reason, cancelChild}` |

See [Execution — claims and runs](execution.md) and [Harness protocol](harness-protocol.md).

### Artifacts

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | `/artifacts` | `artifacts.write` | append-only reference to a result: `type`, `name`, `task?`, `runId?`, `workspaceId?`, `uri?`, `content?`, `metadata`, `supersedesArtifactId?` |
| GET | `/artifacts` | `artifacts.read` | list (`taskId`, `runId`, `workspaceId`, `type`) |
| GET | `/artifacts/{id}` | `artifacts.read` | artifact |

### Approvals

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | `/approvals` | `approvals.manage` | request; exactly one of `requiredRoleId` / `assignedPrincipalId`; `gate: true` requires `task` and blocks claim and complete |
| GET | `/approvals` | `approvals.read` | list (`status`, `taskId`) |
| GET | `/approvals/{id}` | `approvals.read` | approval |
| POST | `/approvals/{id}:approve` | `approvals.decide` + eligibility | approve |
| POST | `/approvals/{id}:reject` | `approvals.decide` + eligibility | reject |
| POST | `/approvals/{id}:cancel` | `approvals.manage`; for a gate — the author or an eligible decider | cancel |
| GET | `/approvals/{id}/outcome` | `approvals.read` | the declared outcome of the decision and the status of each action |
| POST | `/approvals/{id}:replay-outcome` | `approvals.decide` (the decider or an admin) | resume a failed or stuck outcome from the first unexecuted action; otherwise `409 outcome_not_replayable` |

See [Approvals](approvals.md).

### Events and observations

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/events` | `events.read` | event log (see [Event pagination](#events-pagination)) |
| WS | `/events/ws?after=<cursor>` | `events.read` | event stream |
| POST | `/observations` | `observations.write` | explicit knowledge record; a repeat (`source`, `dedupKey`) → `200 deduplicated` |

### Context and knowledge

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | `/context` | authentication (`task`/`runId` — `tasks.read`, `projectId` — `projects.read`, memory — `events.read`) | operational context and memory pack |
| POST | `/knowledge/snapshots` | `observations.write` on `workspace:<workspaceId>` | source snapshot → memory-service (body up to 8 MiB) |
| POST | `/knowledge/packs` | a principal from `CP_KNOWLEDGE_PACK_ADMINS` | register a knowledge pack |
| PUT | `/workspaces/{id}/knowledge-packs` | `workspaces.manage` on `workspace:<id>` | packs and `strict` namespace of the tree (root only) |

See [Task context and memory](context.md).

### Workspaces and workspace types

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | `/workspace-types` | `workspaces.manage` | workspace type |
| GET | `/workspace-types` | `workspaces.read` | list (`status`) |
| GET | `/workspace-types/{id}` | `workspaces.read` | type (+ETag) |
| PATCH | `/workspace-types/{id}` | `workspaces.manage` | update (`If-Match`) |
| POST | `/workspace-types/{id}:archive` | `workspaces.manage` | archive; in use — `422 workspace_type_in_use` |
| POST | `/workspaces` | `workspaces.manage` | workspace (`typeId` or `typeKey`, `customFields`) |
| GET | `/workspaces` | `workspaces.read` | list (`parentId`, `rootsOnly`, `status`) |
| GET | `/workspaces/tree` | `workspaces.read` | tree (`rootId`, `depth`, `includeArchived`, `includeProjects`) → `{roots: [...]}` |
| GET | `/workspaces/{id}` | `workspaces.read` | workspace (+ETag) |
| PATCH | `/workspaces/{id}` | `workspaces.manage` | update (`If-Match`) |
| POST | `/workspaces/{id}:archive` | `workspaces.manage` | archive (no active children) |
| POST | `/workspaces/{id}:move` | `workspaces.manage` | move `{newParentId}` (`null` — to the root); a cycle or weakened governance — `422` |
| POST | `/workspaces/{id}/members` | `workspaces.manage` | add a member |
| GET | `/workspaces/{id}/members` | `workspaces.read` | members |
| POST | `/workspaces/{id}/members/{principalId}:remove` | `workspaces.manage` | remove a member |

### Projects and templates

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | `/project-templates` | `project_templates.manage` | the next immutable template version |
| GET | `/project-templates` | `project_templates.read` | list (`key`, `status`) |
| GET | `/project-templates/{id}` | `project_templates.read` | template |
| POST | `/project-templates/{id}:deprecate` | `project_templates.manage` | retire |
| POST | `/projects` | `projects.manage` | project: `workspaceId` or `workspaceSlug` (the workspace and the profile are created atomically); a second profile — `409 project_exists` |
| GET | `/projects` | `projects.read` | list (`workspaceId`, `status`, `statusKey`, `systemStatusCategory`, `templateKey`, `externalSystem`, `externalType`, `externalId`) |
| GET | `/projects/{id}` | `projects.read` | project (+ETag) |
| PATCH | `/projects/{id}` | `projects.manage` | update (`If-Match`) |
| POST | `/projects/{id}:archive` | `projects.manage` | archive (idempotent) |
| POST | `/projects/{id}:transition` | `projects.manage` | status transition (`If-Match`; declared ones only) |
| GET | `/projects/{id}/effective-config` | `projects.read` | configuration and provenance by layer |
| GET | `/projects/{id}/config-revisions` | `projects.read` | configuration revisions |
| POST | `/projects/{id}/config-revisions` | `projects.manage` | new revision (not activated) |
| POST | `/projects/{id}/config-revisions/{revision}:activate` | `projects.manage` | activate a revision (`If-Match`) |
| GET | `/projects/{id}/external-references` | `projects.read` | external references of the project |
| POST | `/projects/{id}/external-references` | `projects.manage` | add (`201`) or update metadata (`200`); another entity's reference — `409` |

### External references

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | `/external-references` | by `entityType`: `project` → `projects.manage`, `task` → `tasks.write` | register a reference; `201` new, `200` same key, `409 external_reference_conflict` |
| GET | `/external-references` | read permission of the type | forward lookup `?entityType=&entityId=` or reverse `?externalSystem=&externalType=&externalId=` |

### Organizational model

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | `/roles` | `org.manage` | role (`slug` is unique within the scope; `workspaceId?`) |
| GET | `/roles` | `org.read` | list (`workspaceId`) |
| GET | `/roles/{id}` | `org.read` | role (+ETag) |
| PATCH | `/roles/{id}` | `org.manage` | update (`If-Match`) |
| POST | `/capabilities` | `org.manage` | capability |
| GET | `/capabilities` | `org.read` | list |
| GET | `/capabilities/{id}` | `org.read` | capability |
| POST | `/principals/{id}/roles` | `org.manage` | assign `{roleId, workspaceId?}` |
| GET | `/principals/{id}/roles` | `org.read` or `principals.read` | roles of the principal |
| POST | `/principals/{id}/roles/{roleId}:revoke` | `org.manage` | remove |
| POST | `/principals/{id}/capabilities` | `org.manage` | assign |
| GET | `/principals/{id}/capabilities` | `org.read` or `principals.read` | capabilities of the principal |
| POST | `/principals/{id}/capabilities/{capabilityId}:revoke` | `org.manage` | remove |
| POST | `/principals/{id}/skills` | `org.manage` | assign a skill |
| GET | `/principals/{id}/skills` | `org.read` or `principals.read` | skills of the principal |
| POST | `/principals/{id}/skills/{skillId}:revoke` | `org.manage` | remove |

### Skills and invocations {#skills}

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | `/skills` | `org.manage` | publish a version (`name` + `version` are unique; `contract`, `sideEffects`, `riskLevel`) |
| GET | `/skills` | `org.read` | list (`name`, `status`) |
| GET | `/skills/{ref}` | `org.read`, `skills.invoke`, or `skills.execute` | version by `id`, `name@version`, or `name` (+ETag `skill-<rowVersion>`) |
| PATCH | `/skills/{id}` | `org.manage` | `If-Match`; only `description` and a forward `status` change (`active` → `deprecated` → `disabled`). `config`, `inputSchema`, `outputSchema` are allowed only if they match the stored ones, otherwise `409 skill_version_immutable`; a backward status transition — `invalid_status_transition` |
| POST | `/skills/{ref}:invoke` | `skills.invoke` | invocation `{inputs, idempotencyKey?, taskId?, runId?, approvalId?}` → `201` new, `200` repeated key |
| GET | `/skill-invocations/{id}` | `skills.invoke` or `skills.execute` | invocation (visible to the authority and the executor) |
| POST | `/skill-invocations:claim` | `skills.execute` | take an invocation `{protocols, localEntrypoints, httpOrigins, mcpEndpoints, audiences, sessionId?, leaseSeconds?, invocationId?}` → `200 {invocation, skill}` or `204` |
| POST | `/skill-invocations/{id}:heartbeat` | `skills.execute` | extend the lease `{fencingToken, leaseSeconds?}` |
| POST | `/skill-invocations/{id}:complete` | `skills.execute` | result `{fencingToken, output, cost?}`; `output` is re-validated against the schema |
| POST | `/skill-invocations/{id}:fail` | `skills.execute` | failure `{fencingToken, error: {code, message?, retryable?, details?}}` |
| POST | `/skill-invocations/{id}:cancel` | authority of the invocation or `org.manage` | cancel `{reason?}` |

Order of `:invoke` checks:

1. the `skills.invoke` permission, the version exists;
2. a repeated `idempotencyKey` with the same `inputs` from the same principal
   returns the existing invocation, otherwise `409 idempotency_key_reuse`;
3. the version is invocable (`409 skill_not_invocable`, `details.reason`:
   `disabled`, `no_contract`, `protocol_not_invocable`);
4. with `idempotency: required` the key is mandatory
   (`400 idempotency_key_required`);
5. `inputs` are validated against the schema (`400 invalid_skill_inputs`,
   `details.errors[].path`);
6. `runId` must belong to the caller and be in the `running` status;
7. the contract's `requiredPermissions` are checked on the task's workspace
   (`403 skill_permission_denied`), the run's effective tool policy —
   `403 tool_not_authorized` or `403 child_grant_exceeded`;
8. `external_write` requires an approved gate approval on the same
   non-terminal task that has not yet been used for this version
   (`409 approval_already_used`), or an `execution` basis (the task type
   pinned this version, the run is in the `running` status).

A successful `:complete` with `taskId` creates a `skill_result` artifact. More
about the skill contract is in [skill-sdk](../sdk/skill-sdk.md).

### Operations {#operations}

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/operations/context-adapter` | `operations.read` | state of memory delivery for your own tenant |
| POST | `/operations/context-adapter/{tenantId}:redrive` | `operations.manage` | unpark and retry the same position `{reason}`; another tenant — `404` |
| POST | `/operations/context-adapter/{tenantId}:rebuild` | `operations.manage` | rewind the cursor `{cursor?, reason}`; backward only, otherwise `422 cursor_must_not_advance` |
| POST | `/operations/journal:archive` | `operations.manage` | move confirmed history to the archive `{beforeSeconds?, maxEvents?}` |
| POST | `/operations/journal:prune` | `operations.manage` | physically delete the archive `{beforeSeconds?, maxEvents?}` — **data is lost** |

```bash
curl -s -X POST https://platform.example.com/api/v1/operations/journal:archive \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"beforeSeconds": 2592000, "maxEvents": 50000}'
```

The archiving horizon is limited by the minimum of the consumer cursors and the
oldest undelivered outbox event. If there are no consumer cursors at all, the
response is `409 retention_blocked_by_consumer`. The minimum event age is set by
`CP_JOURNAL_RETENTION_MIN_AGE_SECONDS` (30 days). The procedures are described
in [Backup](../operations/backup.md) and
[Monitoring and health](../operations/monitoring.md).

## Event pagination {#events-pagination}

The event log cursor is opaque (`ec1_…`) and is issued in `(tx_id, sequence)`
order under a stable horizon. A subscription from an issued cursor receives
everything committed later: unfinished transactions are sorted strictly after
any issued position. Each event carries `sequence`, `type`, `entityType`,
`entityId`, `actorId`, `sessionId`, `correlationId`, `requestId`,
`traceRunId`, `payload`, `occurredAt`, and `cursor`. The event type catalog is
in [Events](events.md).

## SDK

The official client is the `control-plane-client` package (module
`control_plane_client`, class `ControlPlaneClient`). It sets
`Idempotency-Key` per logical call, refreshes the IAM token, and parses the
error envelope into exceptions. See [Service clients](../sdk/clients.md).

## See also

- [Authorization and permissions](authorization.md)
- [Harness protocol](harness-protocol.md)
- [Configuration](configuration.md)
- [Error codes](../reference/errors.md)
- [Permissions and scopes](../reference/permissions.md)
