# API сервисов ядра

Перечень операций HTTP API трёх сервисов ядра, снятый с их OpenAPI на
ревизиях сабмодулей суперпроекта. Колонка «Периметр» — как операция доступна
снаружи через Caddy ([Периметр и TLS](../operations/edge-and-tls.md)):
публичный путь или «только внутри сети» (административная поверхность IAM,
метрики, memory-service целиком).

Полные схемы запросов и ответов — в OpenAPI самих сервисов:
`https://<публичный адрес>/openapi.json` для Control Plane, `/iam/openapi.json`
для IAM; memory-service — изнутри сети compose.

## Control Plane

<!-- generated:api-control-plane -->
_Раздел генерируется из кода — не правьте его руками._

Версия API `0.9.0`, операций: 176.

| Метод | Путь | Описание | Периметр |
|---|---|---|---|
| `POST` | `/api/v1/api-keys/{api_key_id}:revoke` | Revoke Api Key | публичный |
| `GET` | `/api/v1/approvals` | List Approvals | публичный |
| `POST` | `/api/v1/approvals` | Request Approval | публичный |
| `GET` | `/api/v1/approvals/{approval_id}` | Get Approval | публичный |
| `GET` | `/api/v1/approvals/{approval_id}/outcome` | The declared outcome of a decision and what happened to each action | публичный |
| `POST` | `/api/v1/approvals/{approval_id}:approve` | Approve | публичный |
| `POST` | `/api/v1/approvals/{approval_id}:cancel` | Cancel | публичный |
| `POST` | `/api/v1/approvals/{approval_id}:reject` | Reject | публичный |
| `POST` | `/api/v1/approvals/{approval_id}:replay-outcome` | Resume a failed or stuck approval outcome at its first action that did not execute | публичный |
| `GET` | `/api/v1/artifacts` | List Artifacts | публичный |
| `POST` | `/api/v1/artifacts` | Create Artifact | публичный |
| `GET` | `/api/v1/artifacts/{artifact_id}` | Get Artifact | публичный |
| `POST` | `/api/v1/bootstrap` | Create the first tenant, admin principal, admin API key and, optionally, the admin's IAM binding | публичный |
| `GET` | `/api/v1/capabilities` | List Capabilities | публичный |
| `POST` | `/api/v1/capabilities` | Create Capability | публичный |
| `GET` | `/api/v1/capabilities/{capability_id}` | Get Capability | публичный |
| `POST` | `/api/v1/child-handles/{handle_id}:revoke` | Withdraw a child handle, optionally asking the child to stop | публичный |
| `GET` | `/api/v1/child-handles/{ref}` | Resolve a child handle by id or by ch1_ token | публичный |
| `GET` | `/api/v1/claims` | List Claims | публичный |
| `GET` | `/api/v1/claims/{claim_id}` | Get Claim | публичный |
| `POST` | `/api/v1/claims/{claim_id}:heartbeat` | Heartbeat Claim | публичный |
| `POST` | `/api/v1/claims/{claim_id}:reclaim` | Take over an expired claim atomically (new fencing token) | публичный |
| `POST` | `/api/v1/claims/{claim_id}:release` | Release Claim | публичный |
| `POST` | `/api/v1/context` | Working Context | публичный |
| `GET` | `/api/v1/context-packs/{pack_id}` | Get Context Pack | публичный |
| `POST` | `/api/v1/context-packs/{pack_id}:replay` | Replay Context Pack | публичный |
| `POST` | `/api/v1/context/recall` | Recall Graph | публичный |
| `GET` | `/api/v1/delegations` | List Delegations | публичный |
| `POST` | `/api/v1/delegations` | Create Delegation | публичный |
| `POST` | `/api/v1/delegations/{delegation_id}:revoke` | Revoke Delegation | публичный |
| `GET` | `/api/v1/events` | List Events | публичный |
| `GET` | `/api/v1/external-references` | List External References | публичный |
| `POST` | `/api/v1/external-references` | Register External Reference | публичный |
| `GET` | `/api/v1/goals` | List Goals | публичный |
| `POST` | `/api/v1/goals` | State a desired state that work items can serve | публичный |
| `GET` | `/api/v1/goals/{goal_id}` | Get Goal | публичный |
| `PATCH` | `/api/v1/goals/{goal_id}` | Update Goal | публичный |
| `GET` | `/api/v1/goals/{goal_id}/work` | Work items that serve this goal, newest first | публичный |
| `GET` | `/api/v1/harness/context` | Get Harness Context | публичный |
| `POST` | `/api/v1/iam-bindings/{binding_id}:revoke` | Close entry for a federated identity without waiting for its token to expire | публичный |
| `POST` | `/api/v1/knowledge/packs` | Register Pack | публичный |
| `POST` | `/api/v1/knowledge/snapshots` | Submit Snapshot | публичный |
| `POST` | `/api/v1/observations` | Record Observation | публичный |
| `GET` | `/api/v1/operations/context-adapter` | Context Adapter Status | публичный |
| `POST` | `/api/v1/operations/context-adapter/{tenant_id}:rebuild` | Rebuild Context Adapter | публичный |
| `POST` | `/api/v1/operations/context-adapter/{tenant_id}:redrive` | Redrive Context Adapter | публичный |
| `POST` | `/api/v1/operations/journal:archive` | Archive Journal | публичный |
| `POST` | `/api/v1/operations/journal:prune` | Prune Journal | публичный |
| `GET` | `/api/v1/principals` | List Principals | публичный |
| `POST` | `/api/v1/principals` | Create Principal | публичный |
| `GET` | `/api/v1/principals/{principal_id}` | Get Principal | публичный |
| `POST` | `/api/v1/principals/{principal_id}/api-keys` | Issue an API key; the full key is returned only in this response | публичный |
| `GET` | `/api/v1/principals/{principal_id}/capabilities` | List Capabilities | публичный |
| `POST` | `/api/v1/principals/{principal_id}/capabilities` | Assign Capability | публичный |
| `POST` | `/api/v1/principals/{principal_id}/capabilities/{capability_id}:revoke` | Revoke Capability | публичный |
| `GET` | `/api/v1/principals/{principal_id}/iam-bindings` | Federated identities bound to a principal, revoked ones included | публичный |
| `POST` | `/api/v1/principals/{principal_id}/iam-bindings` | Bind an IAM identity to a principal (upsert by issuer + IAM principal) | публичный |
| `GET` | `/api/v1/principals/{principal_id}/roles` | List Roles | публичный |
| `POST` | `/api/v1/principals/{principal_id}/roles` | Assign Role | публичный |
| `POST` | `/api/v1/principals/{principal_id}/roles/{role_id}:revoke` | Revoke Role | публичный |
| `GET` | `/api/v1/principals/{principal_id}/skills` | List Skills | публичный |
| `POST` | `/api/v1/principals/{principal_id}/skills` | Assign Skill | публичный |
| `POST` | `/api/v1/principals/{principal_id}/skills/{skill_id}:revoke` | Revoke Skill | публичный |
| `GET` | `/api/v1/project-templates` | List Project Templates | публичный |
| `POST` | `/api/v1/project-templates` | Create the next immutable version of a project template | публичный |
| `GET` | `/api/v1/project-templates/{template_id}` | Get Project Template | публичный |
| `POST` | `/api/v1/project-templates/{template_id}:deprecate` | Deprecate Project Template | публичный |
| `GET` | `/api/v1/projects` | List Projects | публичный |
| `POST` | `/api/v1/projects` | Create Project | публичный |
| `GET` | `/api/v1/projects/{project_id}` | Get Project | публичный |
| `PATCH` | `/api/v1/projects/{project_id}` | Update Project | публичный |
| `GET` | `/api/v1/projects/{project_id}/config-revisions` | List Config Revisions | публичный |
| `POST` | `/api/v1/projects/{project_id}/config-revisions` | Create Config Revision | публичный |
| `POST` | `/api/v1/projects/{project_id}/config-revisions/{revision}:activate` | Activate Config Revision | публичный |
| `GET` | `/api/v1/projects/{project_id}/effective-config` | Get Effective Config | публичный |
| `GET` | `/api/v1/projects/{project_id}/external-references` | List External References | публичный |
| `POST` | `/api/v1/projects/{project_id}/external-references` | Add External Reference | публичный |
| `POST` | `/api/v1/projects/{project_id}:archive` | Archive Project | публичный |
| `POST` | `/api/v1/projects/{project_id}:transition` | Transition Project | публичный |
| `GET` | `/api/v1/roles` | List Roles | публичный |
| `POST` | `/api/v1/roles` | Create Role | публичный |
| `GET` | `/api/v1/roles/{role_id}` | Get Role | публичный |
| `PATCH` | `/api/v1/roles/{role_id}` | Update Role | публичный |
| `GET` | `/api/v1/roles/{role_id}/principals` | List Role Holders | публичный |
| `GET` | `/api/v1/rules` | List Rules | публичный |
| `POST` | `/api/v1/rules` | Write a rule that derives work from observed facts | публичный |
| `GET` | `/api/v1/rules/{rule_id}` | Get Rule | публичный |
| `PATCH` | `/api/v1/rules/{rule_id}` | Update Rule | публичный |
| `DELETE` | `/api/v1/rules/{rule_id}` | Archive a rule; its history and the work it filed stay | публичный |
| `GET` | `/api/v1/rules/{rule_id}/evaluations` | What the rule looked at and what it did, newest first | публичный |
| `POST` | `/api/v1/rules/{rule_id}:disable` | Disable a rule: it stops evaluating new facts | публичный |
| `POST` | `/api/v1/rules/{rule_id}:enable` | Enable a rule: it acts from now on, with the caller's authority | публичный |
| `GET` | `/api/v1/runs` | List Runs | публичный |
| `GET` | `/api/v1/runs/{run_id}` | Get Run | публичный |
| `GET` | `/api/v1/runs/{run_id}/actions` | List Actions | публичный |
| `POST` | `/api/v1/runs/{run_id}/actions` | Record an execution action (audit trail; enforces the run budget) | публичный |
| `POST` | `/api/v1/runs/{run_id}/actions/{action_id}:finish` | Finish Action | публичный |
| `GET` | `/api/v1/runs/{run_id}/checkpoints` | List Checkpoints | публичный |
| `POST` | `/api/v1/runs/{run_id}/checkpoints` | Append a durable execution checkpoint (live owner only) | публичный |
| `GET` | `/api/v1/runs/{run_id}/child-handles` | List child handles launched by this Run | публичный |
| `POST` | `/api/v1/runs/{run_id}/child-handles` | Launch a child run under this Run and return its durable handle | публичный |
| `GET` | `/api/v1/runs/{run_id}/context` | Structured execution context for a run (task, claim, artifacts, checkpoints, skills) | публичный |
| `GET` | `/api/v1/runs/{run_id}/control-messages` | List durable Run control messages in Run-local sequence order | публичный |
| `POST` | `/api/v1/runs/{run_id}/control-messages` | Append one durable Active Turn Control message | публичный |
| `POST` | `/api/v1/runs/{run_id}/control-messages/{message_id}:acknowledge` | Acknowledge the oldest accepted control message at a safe boundary | публичный |
| `GET` | `/api/v1/runs/{run_id}/harness-manifest` | Effective Harness Manifest of a run (frozen base, provenance, captured state) | публичный |
| `POST` | `/api/v1/runs/{run_id}/harness-manifest/ephemeral` | Record an ephemeral steering/warning marker (never changes the frozen base) | публичный |
| `POST` | `/api/v1/runs/{run_id}/harness-manifest:compile` | Recompile the manifest; a new version appears only if the frozen base changed | публичный |
| `GET` | `/api/v1/runs/{run_id}/harness-manifests` | Manifest version history of a run (newest first) | публичный |
| `POST` | `/api/v1/runs/{run_id}:cancel` | Cancel Run | публичный |
| `POST` | `/api/v1/runs/{run_id}:fail` | Fail Run | публичный |
| `POST` | `/api/v1/runs/{run_id}:handoff` | Checkpoint, suspend and release a run for a new human-operated harness | публичный |
| `POST` | `/api/v1/runs/{run_id}:request-cancel` | Signal cooperative cancellation (authoritative stop is :cancel) | публичный |
| `POST` | `/api/v1/runs/{run_id}:succeed` | Finish a run successfully (atomically completes the task by default) | публичный |
| `POST` | `/api/v1/runs/{run_id}:suspend` | Pause execution: run -> suspended, claim released (waiting semantics) | публичный |
| `GET` | `/api/v1/sessions` | List Sessions | публичный |
| `POST` | `/api/v1/sessions` | Open Session | публичный |
| `GET` | `/api/v1/sessions/{session_id}` | Get Session | публичный |
| `POST` | `/api/v1/sessions/{session_id}:close` | Close Session | публичный |
| `POST` | `/api/v1/sessions/{session_id}:heartbeat` | Heartbeat Session | публичный |
| `GET` | `/api/v1/skill-invocations/{invocation_id}` | Get Skill Invocation | публичный |
| `POST` | `/api/v1/skill-invocations/{invocation_id}:cancel` | Cancel Skill Invocation | публичный |
| `POST` | `/api/v1/skill-invocations/{invocation_id}:complete` | Complete Skill Invocation | публичный |
| `POST` | `/api/v1/skill-invocations/{invocation_id}:fail` | Fail Skill Invocation | публичный |
| `POST` | `/api/v1/skill-invocations/{invocation_id}:heartbeat` | Heartbeat Skill Invocation | публичный |
| `POST` | `/api/v1/skill-invocations:claim` | Claim Skill Invocation | публичный |
| `GET` | `/api/v1/skills` | List Skills | публичный |
| `POST` | `/api/v1/skills` | Register Skill | публичный |
| `PATCH` | `/api/v1/skills/{skill_id}` | Update Skill | публичный |
| `GET` | `/api/v1/skills/{skill_ref}` | Get Skill | публичный |
| `POST` | `/api/v1/skills/{skill_ref}:invoke` | Invoke Skill | публичный |
| `GET` | `/api/v1/task-types` | List Task Types | публичный |
| `POST` | `/api/v1/task-types` | Create the next immutable version of a work item type | публичный |
| `GET` | `/api/v1/task-types/{type_id}` | Get Task Type | публичный |
| `POST` | `/api/v1/task-types/{type_id}:deprecate` | Deprecate Task Type | публичный |
| `GET` | `/api/v1/tasks` | List Tasks | публичный |
| `POST` | `/api/v1/tasks` | Create Task | публичный |
| `GET` | `/api/v1/tasks/{task_ref}` | Get Task | публичный |
| `PATCH` | `/api/v1/tasks/{task_ref}` | Update Task | публичный |
| `GET` | `/api/v1/tasks/{task_ref}/claimability` | Advisory diagnosis: can the caller claim this task, and why not | публичный |
| `GET` | `/api/v1/tasks/{task_ref}/comments` | One page of the thread, oldest first | публичный |
| `POST` | `/api/v1/tasks/{task_ref}/comments` | Append a reply to a work item's discussion | публичный |
| `GET` | `/api/v1/tasks/{task_ref}/comments/{comment_id}` | Get Comment | публичный |
| `PATCH` | `/api/v1/tasks/{task_ref}/comments/{comment_id}` | Correct one's own comment; the previous version is kept | публичный |
| `GET` | `/api/v1/tasks/{task_ref}/comments/{comment_id}/revisions` | Superseded versions of a comment, oldest first | публичный |
| `GET` | `/api/v1/tasks/{task_ref}/relations` | List Relations | публичный |
| `POST` | `/api/v1/tasks/{task_ref}/relations` | Add Relation | публичный |
| `DELETE` | `/api/v1/tasks/{task_ref}/relations/{relation_id}` | Remove Relation | публичный |
| `GET` | `/api/v1/tasks/{task_ref}/requirements` | Get Requirements | публичный |
| `GET` | `/api/v1/tasks/{task_ref}/transitions` | Where this task may move next, per the lifecycle of its type | публичный |
| `GET` | `/api/v1/tasks/{task_ref}/verifications` | Attempts of the verification stage, newest first (CP-ADR-0067) | публичный |
| `POST` | `/api/v1/tasks/{task_ref}:claim` | Atomically claim a task (lease + fencing token) | публичный |
| `POST` | `/api/v1/tasks/{task_ref}:complete` | Complete Task | публичный |
| `POST` | `/api/v1/tasks/{task_ref}:start-run` | Start an execution attempt under a live claim | публичный |
| `GET` | `/api/v1/tools` | Tools this principal may use right now (bounded projection) | публичный |
| `GET` | `/api/v1/tools/{tool_ref}` | Full sanitized projection of one tool | публичный |
| `GET` | `/api/v1/work/available` | Tasks the calling principal could claim right now (advisory) | публичный |
| `GET` | `/api/v1/workspace-types` | List Workspace Types | публичный |
| `POST` | `/api/v1/workspace-types` | Create Workspace Type | публичный |
| `GET` | `/api/v1/workspace-types/{type_id}` | Get Workspace Type | публичный |
| `PATCH` | `/api/v1/workspace-types/{type_id}` | Update Workspace Type | публичный |
| `POST` | `/api/v1/workspace-types/{type_id}:archive` | Archive Workspace Type | публичный |
| `GET` | `/api/v1/workspaces` | List Workspaces | публичный |
| `POST` | `/api/v1/workspaces` | Create Workspace | публичный |
| `GET` | `/api/v1/workspaces/tree` | Get Workspace Tree | публичный |
| `GET` | `/api/v1/workspaces/{workspace_id}` | Get Workspace | публичный |
| `PATCH` | `/api/v1/workspaces/{workspace_id}` | Update Workspace | публичный |
| `PUT` | `/api/v1/workspaces/{workspace_id}/knowledge-packs` | Set Workspace Packs | публичный |
| `GET` | `/api/v1/workspaces/{workspace_id}/members` | List Members | публичный |
| `POST` | `/api/v1/workspaces/{workspace_id}/members` | Add Member | публичный |
| `POST` | `/api/v1/workspaces/{workspace_id}/members/{principal_id}:remove` | Remove Member | публичный |
| `POST` | `/api/v1/workspaces/{workspace_id}:archive` | Archive Workspace | публичный |
| `POST` | `/api/v1/workspaces/{workspace_id}:move` | Move Workspace | публичный |
| `GET` | `/health/live` | Health Live | публичный |
| `GET` | `/health/ready` | Health Ready | публичный |
| `GET` | `/metrics` | Metrics Endpoint | только внутри сети |
<!-- /generated:api-control-plane -->

## IAM

<!-- generated:api-iam-service -->
_Раздел генерируется из кода — не правьте его руками._

Версия API `0.1.0`, операций: 52.

| Метод | Путь | Описание | Периметр |
|---|---|---|---|
| `GET` | `/.well-known/jwks.json` | Jwks | `/iam/.well-known/jwks.json` |
| `GET` | `/api/v1/events` | List Events | только внутри сети |
| `POST` | `/api/v1/platform-access-tokens:exchange` | Exchange Platform Access Token | `/iam/api/v1/platform-access-tokens:exchange` |
| `POST` | `/api/v1/platform-access-tokens:introspect` | Introspect Platform Access Token | `/iam/api/v1/platform-access-tokens:introspect` |
| `POST` | `/api/v1/platform-access-tokens:revoke-self` | Revoke Presented Platform Access Token | `/iam/api/v1/platform-access-tokens:revoke-self` |
| `POST` | `/api/v1/tenants` | Create Tenant | только внутри сети |
| `GET` | `/api/v1/tenants/{tenant_id}/audiences` | List Audiences | только внутри сети |
| `POST` | `/api/v1/tenants/{tenant_id}/audiences` | Create Audience | только внутри сети |
| `PATCH` | `/api/v1/tenants/{tenant_id}/audiences/{key}` | Update Audience | только внутри сети |
| `POST` | `/api/v1/tenants/{tenant_id}/channel-assertions:exchange` | Exchange Channel Assertion | только внутри сети |
| `POST` | `/api/v1/tenants/{tenant_id}/channel-link-intents` | Create Channel Link Intent | только внутри сети |
| `GET` | `/api/v1/tenants/{tenant_id}/channel-links` | List Channel Links | только внутри сети |
| `POST` | `/api/v1/tenants/{tenant_id}/channel-links/{link_id}:revoke` | Revoke Channel Link | только внутри сети |
| `POST` | `/api/v1/tenants/{tenant_id}/channel-links:confirm` | Confirm Channel Link | только внутри сети |
| `GET` | `/api/v1/tenants/{tenant_id}/channel-providers` | List Channel Providers | только внутри сети |
| `PUT` | `/api/v1/tenants/{tenant_id}/channel-providers/{channel}` | Configure Channel Provider | только внутри сети |
| `POST` | `/api/v1/tenants/{tenant_id}/federation:authenticate` | Authenticate Federated Identity | `/iam/api/v1/tenants/{tenant_id}/federation:authenticate` |
| `POST` | `/api/v1/tenants/{tenant_id}/federation:exchange` | Exchange Federated Identity | `/iam/api/v1/tenants/{tenant_id}/federation:exchange` |
| `POST` | `/api/v1/tenants/{tenant_id}/groups` | Create Group | только внутри сети |
| `POST` | `/api/v1/tenants/{tenant_id}/groups/{group_id}/members` | Add Group Member | только внутри сети |
| `POST` | `/api/v1/tenants/{tenant_id}/identity-providers` | Create Identity Provider | только внутри сети |
| `POST` | `/api/v1/tenants/{tenant_id}/legacy-credentials:import` | Import Legacy Credential | только внутри сети |
| `GET` | `/api/v1/tenants/{tenant_id}/platform-access-tokens` | List Platform Access Tokens | только внутри сети |
| `POST` | `/api/v1/tenants/{tenant_id}/platform-access-tokens/{credential_id}:revoke` | Revoke Platform Access Token | только внутри сети |
| `POST` | `/api/v1/tenants/{tenant_id}/platform-access-tokens/{credential_id}:rotate` | Rotate Platform Access Token | только внутри сети |
| `POST` | `/api/v1/tenants/{tenant_id}/principals` | Create Principal | только внутри сети |
| `GET` | `/api/v1/tenants/{tenant_id}/principals/{principal_id}` | Get Principal | только внутри сети |
| `POST` | `/api/v1/tenants/{tenant_id}/principals/{principal_id}/authentication-contexts` | Create Authentication Context | только внутри сети |
| `POST` | `/api/v1/tenants/{tenant_id}/principals/{principal_id}/external-identities` | Link External Identity | только внутри сети |
| `POST` | `/api/v1/tenants/{tenant_id}/principals/{principal_id}/platform-access-tokens` | Issue Platform Access Token | только внутри сети |
| `POST` | `/api/v1/tenants/{tenant_id}/principals/{principal_id}:disable` | Disable Principal | только внутри сети |
| `GET` | `/api/v1/tenants/{tenant_id}/provisioning-sources` | List Provisioning Sources | только внутри сети |
| `POST` | `/api/v1/tenants/{tenant_id}/provisioning-sources` | Register Provisioning Source | только внутри сети |
| `POST` | `/api/v1/tenants/{tenant_id}/service-accounts` | Create Service Account | только внутри сети |
| `POST` | `/api/v1/tenants/{tenant_id}/service-accounts/{client_id}:revoke` | Revoke Service Account | только внутри сети |
| `POST` | `/api/v1/tokens/exchange` | Exchange Token | `/iam/api/v1/tokens/exchange` |
| `GET` | `/healthz` | Health | `/iam/healthz` |
| `GET` | `/scim/v2/Groups` | Scim List Groups | `/iam/scim/v2/Groups` |
| `POST` | `/scim/v2/Groups` | Scim Create Group | `/iam/scim/v2/Groups` |
| `GET` | `/scim/v2/Groups/{group_id}` | Scim Get Group | `/iam/scim/v2/Groups/{group_id}` |
| `PUT` | `/scim/v2/Groups/{group_id}` | Scim Replace Group | `/iam/scim/v2/Groups/{group_id}` |
| `PATCH` | `/scim/v2/Groups/{group_id}` | Scim Patch Group | `/iam/scim/v2/Groups/{group_id}` |
| `DELETE` | `/scim/v2/Groups/{group_id}` | Scim Delete Group | `/iam/scim/v2/Groups/{group_id}` |
| `GET` | `/scim/v2/ResourceTypes` | Scim Resource Types | `/iam/scim/v2/ResourceTypes` |
| `GET` | `/scim/v2/Schemas` | Scim Schemas | `/iam/scim/v2/Schemas` |
| `GET` | `/scim/v2/ServiceProviderConfig` | Scim Service Provider Config | `/iam/scim/v2/ServiceProviderConfig` |
| `GET` | `/scim/v2/Users` | Scim List Users | `/iam/scim/v2/Users` |
| `POST` | `/scim/v2/Users` | Scim Create User | `/iam/scim/v2/Users` |
| `GET` | `/scim/v2/Users/{user_id}` | Scim Get User | `/iam/scim/v2/Users/{user_id}` |
| `PUT` | `/scim/v2/Users/{user_id}` | Scim Replace User | `/iam/scim/v2/Users/{user_id}` |
| `PATCH` | `/scim/v2/Users/{user_id}` | Scim Patch User | `/iam/scim/v2/Users/{user_id}` |
| `DELETE` | `/scim/v2/Users/{user_id}` | Scim Delete User | `/iam/scim/v2/Users/{user_id}` |
<!-- /generated:api-iam-service -->

## Memory Service

<!-- generated:api-memory-service -->
_Раздел генерируется из кода — не правьте его руками._

Версия API `0.1.0`, операций: 36.

| Метод | Путь | Описание | Периметр |
|---|---|---|---|
| `POST` | `/api/brain/audit` | Brain Audit | только внутри сети |
| `POST` | `/api/brain/documents` | Brain Document Ingest | только внутри сети |
| `DELETE` | `/api/brain/documents/{natural_key}` | Brain Document Delete | только внутри сети |
| `POST` | `/api/brain/facts` | Write Fact | только внутри сети |
| `GET` | `/api/brain/health` | Brain Health | только внутри сети |
| `GET` | `/api/brain/nodes` | Brain Nodes | только внутри сети |
| `GET` | `/api/brain/nodes/{natural_key}` | Brain Node | только внутри сети |
| `DELETE` | `/api/brain/nodes/{natural_key}` | Brain Node Delete | только внутри сети |
| `POST` | `/api/brain/query` | Brain Query | только внутри сети |
| `POST` | `/api/brain/recall` | Brain Recall | только внутри сети |
| `POST` | `/api/brain/retain` | Brain Retain | только внутри сети |
| `POST` | `/api/brain/search` | Brain Search | только внутри сети |
| `GET` | `/api/brain/sources/{natural_key}` | Brain Source | только внутри сети |
| `GET` | `/api/brain/stats` | Brain Stats | только внутри сети |
| `GET` | `/api/brain/trace/{trace_id}` | Brain Trace | только внутри сети |
| `POST` | `/api/memory/consolidate` | Memory Consolidate | только внутри сети |
| `POST` | `/api/memory/context` | Memory Context | только внутри сети |
| `GET` | `/api/memory/context/trace/{trace_id}` | Memory Context Trace | только внутри сети |
| `POST` | `/api/memory/context/typed` | Memory Context Typed | только внутри сети |
| `GET` | `/api/memory/namespaces/{namespace}/kinds` | Memory Namespace Kinds | только внутри сети |
| `PUT` | `/api/memory/namespaces/{namespace}/kinds` | Memory Namespace Kinds Put | только внутри сети |
| `GET` | `/api/memory/observations` | Memory Observations List | только внутри сети |
| `POST` | `/api/memory/observations` | Memory Observe | только внутри сети |
| `GET` | `/api/memory/observations/{observation_id}` | Memory Observation Get | только внутри сети |
| `DELETE` | `/api/memory/observations/{observation_id}` | Memory Observation Delete | только внутри сети |
| `POST` | `/api/memory/observations:batch` | Memory Observe Batch | только внутри сети |
| `GET` | `/api/memory/packages` | Memory Packages List | только внутри сети |
| `POST` | `/api/memory/packages` | Memory Package Register | только внутри сети |
| `GET` | `/api/memory/packages/{name}` | Memory Package Get | только внутри сети |
| `POST` | `/api/memory/reconcile` | Memory Reconcile | только внутри сети |
| `POST` | `/audit` | Brain Audit | только внутри сети |
| `GET` | `/health` | Brain Health | только внутри сети |
| `GET` | `/healthz` | Healthz | только внутри сети |
| `POST` | `/recall` | Brain Recall | только внутри сети |
| `POST` | `/retain` | Brain Retain | только внутри сети |
| `POST` | `/search` | Brain Search | только внутри сети |
<!-- /generated:api-memory-service -->
