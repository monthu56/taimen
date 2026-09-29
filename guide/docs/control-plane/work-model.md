
# Work model

This article describes how work is organized in Control Plane: the tenant, the
workspace hierarchy, projects with templates and configuration, tasks (work items) with
fields, dates, requirements, and relations, and task queries with filters and
sorting. It is for anyone who sets up the platform structure or
integrates external systems with core tasks.

## Entity hierarchy

```text
Tenant
└── Workspace (tree; slug is unique among siblings)
    ├── Project Profile (0..1 per workspace)
    ├── Principals (members, roles, capabilities, skills)
    ├── Goals
    └── Tasks
         ├── type (Task type, pinned version)
         ├── status = key + system category
         ├── custom fields, planned dates
         ├── requirements (roles / capabilities / skills)
         ├── relations (parent | blocks | depends_on | spawned_by | related_to)
         ├── comments (with edit history)
         ├── claims → runs → checkpoints, actions, artifacts
         └── approvals
```

There is **one** tree: `Workspace` is the only hierarchy, and a project is a profile
bound to a workspace one-to-one. A task's membership in a
project is not stored; it is computed from the tree on read.

## Tenant

A tenant is the data isolation boundary. Every entity belongs to exactly one
tenant; composite foreign keys of the form `(tenant_id, …)` make
cross-tenant references impossible at the database level, and accessing another tenant's
object returns `404` — the same as for a nonexistent one.

A tenant is created by a one-time call to `POST /api/v1/bootstrap`, protected by
the `CP_BOOTSTRAP_TOKEN` token: it creates the tenant, the first administrator principal
and its credential, as well as the system reference data (the system task type `task`,
the system workspace type `generic`). A repeated call returns
`409 already_bootstrapped`. Bootstrap is usually performed by the deployment script —
see [Bootstrap](../getting-started/bootstrap.md).

## Workspaces

A workspace is a tree node where tasks, goals, members, and roles live.

| Field | Description |
|---|---|
| `slug` | `^[a-z0-9][a-z0-9-]*$`, 2–63 characters, unique among the children of one parent |
| `name`, `description` | Display name and description |
| `parentId` | Parent; `null` is a root |
| `typeId` / `typeKey` | Node type; if omitted, the tenant's system type |
| `customFields` | Fields validated against the type's `fieldSchema` |
| `status` | `active` or `archived` |

Operations:

```bash
# Create a workspace
curl -s -X POST "$CP/workspaces" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"slug": "platform", "name": "Platform team", "typeKey": "team"}'

# The whole tree (one recursive query)
curl -s "$CP/workspaces/tree?includeProjects=true" -H "Authorization: Bearer $TOKEN"

# Move under another parent (cycles are forbidden)
curl -s -X POST "$CP/workspaces/<workspace-id>:move" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"newParentId": "<parent-id>"}'
```

- `PATCH /workspaces/{id}` requires `If-Match: "workspace-<version>"`.
- `:archive` requires that there are no active children
  (`422 workspace_has_active_children`); you cannot create tasks in an archived
  workspace (`422 workspace_archived`).
- `:move` into its own subtree is rejected (`422 workspace_cycle`) and
  re-checks the governance of the moved subtree
  (`422 governance_weakened`, full rollback).
- Members: `POST /workspaces/{id}/members`, `GET …/members`,
  `POST …/members/{principalId}:remove`.

Permissions: `workspaces.read` for reading, `workspaces.manage` for changes.

### Workspace types

Workspace Type is tenant reference data: `key`, `displayName`, `fieldSchema`
(JSON Schema 2020-12 for the node's `customFields`), and `allowedChildTypes` —
which types are allowed as children. Every tenant has the system type `generic`,
which allows any children. The parent–child rule is checked on
creation, move, and type change under the same per-tenant lock as other
structural mutations.

```bash
curl -s -X POST "$CP/workspace-types" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "key": "portfolio",
    "displayName": "Portfolio",
    "allowedChildTypes": ["project", "team"]
  }'
```

`POST /workspace-types/{id}:archive` is rejected while the type is in use
(`422 workspace_type_in_use`).

## Projects

A project is a **profile** (`project_profiles`) bound to a workspace.
A project's parent is not stored: it is the nearest ancestor workspace that
also has a profile.

```text
Tenant
└── Workspace (portfolio)
    ├── Workspace (project)  + Project Profile     ← project A
    │   ├── Workspace (workstream)                 ← belongs to A
    │   └── Workspace (project) + Project Profile  ← project B, nested in A
    └── Workspace (team)
```

### Project templates

A Project Template is versioned and **immutable**: `POST /project-templates`
creates the next version of the key, and a database trigger allows a single
mutation — `active → deprecated`. A project references an exact version, so
its fields and status are always validated against the schema they were written under.

A template carries `fieldSchema`, `lifecycleSchema`, `defaultConfig`,
`defaultViews`, `governanceSchema`, and `memoryDefaults`.

### Project lifecycle

Statuses are user-defined, decisions are system-defined: each template status
maps to one of five categories — `planned`, `active`, `paused`,
`terminal_success`, `terminal_cancelled`. The core branches only on the category.
A status change is `POST /projects/{id}:transition` with `If-Match`, and only along a
declared edge; the event is `project.status_changed`.

!!! note "Project and task categories differ"
    A project has `paused`, a task has `blocked` and `backlog`. These are different
    vocabularies on top of the same lifecycle parsing mechanism; for more on tasks,
    see [Task types and statuses](task-types.md).

### Project configuration

- `POST /projects/{id}/config-revisions` adds a revision (append-only) and
  does **not** activate it.
- `POST /projects/{id}/config-revisions/{n}:activate` with `If-Match` makes it
  the single authoritative pointer.
- `GET /projects/{id}/effective-config` returns the merged configuration and
  provenance for each top-level key.

The merge order is deterministic: template defaults → resolved settings
of ancestors (from the root to the parent) → active revision → profile overlay.
`settings` and `memory` are merged recursively (arrays and scalars are replaced
entirely), `views` are replaced completely, `governance` is folded with the
"stricter" operation: a descendant can only tighten restrictions.

Permissions: `projects.read` / `projects.manage`, `project_templates.read` /
`project_templates.manage`.

## Tasks (work items)

### Task fields

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Identifier |
| `publicId` | string | Human-readable number of the form `TASK-000123`, unique within the tenant. Wherever a path accepts `{task_ref}`, both the UUID and the `publicId` work |
| `title` | string ≤ 500 | Not empty |
| `description` | string | Free text |
| `typeId`, `typeKey`, `typeVersion` | — | Pinned version of the [task type](task-types.md) |
| `status` | string ≤ 64 | Status key from the type's lifecycle |
| `systemStatusCategory` | enum | `backlog`, `active`, `blocked`, `terminal_success`, `terminal_cancelled`; derived from the key, not set by the client |
| `priority` | enum | `critical`, `high`, `medium` (default), `low` |
| `ownerId`, `assigneeId` | UUID | Principals of the tenant |
| `workspaceId` | UUID | The task's workspace (can be `null`) |
| `projectId` | UUID | Computed from the tree on read, not stored |
| `customFields` | object | Validated against the `fieldSchema` of the type version |
| `startDate`, `dueDate` | ISO-8601 | Planned dates |
| `goalId`, `origin`, `acceptance`, `evidence` | — | The work graph, see [Goals, acceptance, and evidence](goals-and-evidence.md) |
| `version` | int | Version for `If-Match` |
| `claimEpoch`, `activeClaimId` | — | Fencing and the current claim, see [Execution](execution.md) |
| `createdBy`, `createdAt`, `updatedAt`, `completedAt` | — | Audit |

### Creation

```bash
curl -s -X POST "$CP/tasks" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "title": "Prepare a load report",
    "typeKey": "task",
    "priority": "high",
    "workspaceId": "<workspace-id>",
    "assigneeId": "<principal-id>",
    "dueDate": "2026-10-01T12:00:00Z",
    "customFields": {},
    "requirements": {"roles": ["analyst"], "capabilities": [], "skills": []}
  }'
```

Creation rules:

- without `typeId` / `typeKey` the task gets the system type `task`; `typeKey`
  without `typeVersion` resolves to the newest `active` version of the key;
- the default `status` is the type's `initialStatus`. You can explicitly specify only
  the initial status or a status of the `backlog` category, otherwise
  `422 invalid_status`: a task cannot be born "in progress" without a claim;
- a status outside the type's lifecycle — `422 status_not_in_lifecycle`;
- `parentTask` (UUID or `publicId`) creates a `parent` relation in the same
  transaction and sets `origin.kind = "parent"`;
- `workspaceId` must point to an active workspace; the `tasks.write` permission
  is checked on that workspace.

The response is `201` with the task body. The `publicId` number is issued transactionally from
the tenant's counter, so collisions are impossible.

### Update

`PATCH /tasks/{ref}` requires `If-Match: "task-<version>"`. If the task
has a live claim, the request must carry that claim's `claimId` and `fencingToken`
— otherwise `409 task_claimed` (details in [Execution](execution.md)).

```bash
curl -s -X PATCH "$CP/tasks/TASK-000123" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H 'If-Match: "task-4"' \
  -d '{"status": "blocked", "dueDate": null, "priority": "critical"}'
```

| Field in PATCH | Semantics |
|---|---|
| `title`, `description`, `priority`, `status` | `null` is forbidden (`422 invalid_field`) |
| `status` | Only along a declared lifecycle edge; the transition to `terminal_success` goes through `:complete`, not PATCH |
| `customFields` | Replaces the document **entirely**; `null` is forbidden, clear with `{}` |
| `startDate`, `dueDate` | `null` clears the date; a new value is checked against the other end of the interval |
| `ownerId`, `assigneeId`, `workspaceId`, `goalId` | `null` removes the value |
| `requirements` | Replaces the set of requirements; `null` is forbidden, clear with an empty object |
| `acceptance`, `evidence` | Replace the list entirely; `null` is forbidden |
| `origin` | Not part of the contract: origin is immutable (`400 invalid_request`) |

An empty PATCH — `422 empty_update`. Each successful PATCH increments
`version` and writes a `task.updated` event with the list of changed fields;
on a status change the event contains `fromStatus`, `status`, and
`systemStatusCategory`.

### Completion

`POST /tasks/{ref}:complete` with `If-Match` moves the task to
its type's `completionStatus`, releases the claim, and sets `completedAt`.
Details and restrictions are in [Task types](task-types.md) and
[Execution](execution.md).

## Custom fields

Custom fields are fields the tenant declares itself in the task type's `fieldSchema`
(JSON Schema draft 2020-12).

- Validation uses the schema of **the type version the task pinned**, not
  the newest one: the type the task was created under is its contract.
- The schema can reference only itself (`$ref` of the form `#…`); external references
  are rejected with `422 invalid_json_schema`.
- The document is limited to 64 KiB, depth 20, and 5,000 nodes.
- A schema violation — `422 custom_fields_invalid` with a list of errors and
  JSON paths.
- Keys that look like secrets (`password`, `token`, `apiKey`, `secret`,
  `credential`, `authorization`, and so on) are rejected with
  `422 secret_material_rejected`. For references to secrets, use the
  `secretRef` key.
- The contents of custom fields do not go into the event log — only the fact of
  the change (`"customFields": true`).

An example of a type with fields and a task under it:

```json
{
  "key": "incident",
  "displayName": "Incident",
  "fieldSchema": {
    "type": "object",
    "properties": {
      "severity": {"type": "string", "enum": ["sev1", "sev2", "sev3"]},
      "service": {"type": "string", "maxLength": 100}
    },
    "required": ["severity"],
    "additionalProperties": false
  }
}
```

```json
{"title": "Spike in 5xx errors", "typeKey": "incident",
 "customFields": {"severity": "sev2", "service": "billing"}}
```

## Planned dates

`startDate` and `dueDate` are typed `timestamptz` columns, not custom
fields: they need indexes, filters, and "soonest first" sorting.

- A time without a time zone is read as UTC.
- `startDate` later than `dueDate` — `422 invalid_planned_dates` (the database checks
  the same thing).
- When one end of the interval changes, the new value is checked against the
  stored other end.

## Requirements and eligibility

A task's `requirements` are lists of roles, capabilities, and skills, **all**
mandatory for whoever claims the task:

```json
{"requirements": {"roles": ["reviewer"], "capabilities": ["python"], "skills": ["repo.search@1.2.0"]}}
```

A skill is specified as `name` or `name@version` (exact version). An unknown
requirement — `422 unknown_requirement`. Requirements **do not grant** API permissions:
they define eligibility — who can take the task at all. A claim is allowed
only when all four conditions hold at once:

```text
API permission tasks.claim ∧ eligibility (requirements) ∧ readiness (dependencies) ∧ concurrency (claim, fencing)
```

The task's current requirements are at `GET /tasks/{ref}/requirements`; diagnostics for
"why can't I claim this task" are at `GET /tasks/{ref}/claimability` (see
[Execution](execution.md)). For more on roles and capabilities, see
[Authorization and permissions](authorization.md).

## Task relations

A relation is directed: `from --type--> to`.

| Type | Meaning | Affects execution |
|---|---|---|
| `parent` | `from` is a subtask of `to` | Acyclicity is checked |
| `blocks` | `from` must finish before `to` is claimed | Yes: `to` is not ready until `from` is in `terminal_success` |
| `depends_on` | `from` cannot be claimed until `to` is finished | Yes: `from` is not ready until `to` is in `terminal_success` |
| `spawned_by` | `from` was created as a consequence of `to` | Used by the child run cancellation cascade and by approval outcome expressions |
| `related_to` | Free association | No |

```bash
# TASK-000124 depends on TASK-000123
curl -s -X POST "$CP/tasks/TASK-000124/relations" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"toTask": "TASK-000123", "type": "depends_on"}'

# All relations of the task (both sides)
curl -s "$CP/tasks/TASK-000124/relations" -H "Authorization: Bearer $TOKEN"

# Delete a relation
curl -s -X DELETE "$CP/tasks/TASK-000124/relations/<relation-id>" \
  -H "Authorization: Bearer $TOKEN"
```

- For `parent`, `blocks`, `depends_on` the core checks acyclicity under a
  per-tenant advisory lock: a cycle — `422 dependency_cycle`.
- Repeating an existing relation — `409 relation_exists`; relating a task to itself —
  `422 invalid_relation`.
- Readiness is computed by **category**: a prerequisite is satisfied only in
  `terminal_success`.

!!! warning "A cancelled dependency keeps blocking"
    A prerequisite in the `terminal_cancelled` category is **not** considered satisfied:
    the dependent task stays not ready (`409 task_not_ready`) until the relation is
    deleted. This is deliberate — cancelling a prerequisite requires a human
    decision, not silent unblocking.

## Task queries

`GET /tasks` is a paginated list with filters. All filters are applied before
pagination, so pages neither skip nor duplicate records.

| Parameter | Description |
|---|---|
| `status` | Status key |
| `systemStatusCategory` | Category — the preferred filter when the meaning matters more than the label |
| `typeKey` | Task type key |
| `priority` | Priority |
| `ownerId`, `assigneeId` | Principal |
| `workspaceId` + `includeDescendants=true` | Workspace (and its subtree) |
| `projectId` + `includeSubprojects=true` | Project (expands into a set of workspaces) |
| `startFrom`, `startTo`, `dueFrom`, `dueTo` | Inclusive date bounds; tasks without a date do not match such a filter |
| `goalId` | Tasks linked to a goal |
| `sort` | `createdAt` (default, newest first), `startDate`, `dueDate` |
| `limit`, `cursor` | Pagination (50 by default, maximum 200) |

```bash
# Open tasks of a workspace and its subtree, nearest deadline first
curl -s "$CP/tasks?workspaceId=<workspace-id>&includeDescendants=true&systemStatusCategory=active&sort=dueDate" \
  -H "Authorization: Bearer $TOKEN"

# Overdue as of the end of the month
curl -s "$CP/tasks?dueTo=2026-09-30T23:59:59Z&systemStatusCategory=active" \
  -H "Authorization: Bearer $TOKEN"
```

Date sorting specifics:

- "soonest first", tasks without a date go last, ties are broken by `id`;
- the cursor is bound to the order it was issued under: applied to a different
  `sort` — `422 invalid_cursor`;
- an unknown `sort` value — `422 invalid_sort`.

Response:

```json
{
  "items": [
    {
      "id": "…", "publicId": "TASK-000123", "title": "…",
      "typeKey": "task", "typeVersion": 1,
      "status": "todo", "systemStatusCategory": "active",
      "priority": "high", "workspaceId": "…", "projectId": "…",
      "dueDate": "2026-10-01T12:00:00Z", "version": 4, "…": "…"
    }
  ],
  "nextCursor": "…"
}
```

!!! tip "Discovery for executors"
    To find work, an executor is better served by
    `GET /work/available`: it returns only what the caller can claim
    right now (eligible, ready, no live claim, and no gate), and supports
    `assignedToMe=true`. The result is advisory — only the claim itself
    is authoritative. An archived project does not hand out new work. See [Execution](execution.md).

## Comments

Task discussion is a comment thread with an append-only edit history. It
is described together with artifacts in [Artifacts and comments](artifacts.md).

## See also

- [Task types and statuses](task-types.md)
- [Goals, acceptance, and evidence](goals-and-evidence.md)
- [Execution — claims and runs](execution.md)
- [Authorization and permissions](authorization.md)
- [Events](events.md) — which events each operation writes.
