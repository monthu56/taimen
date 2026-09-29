
# Vertical packages

A vertical package is a way to add a subject area to the platform (procurement, support,
legal review, and so on) **without changing the core**: a domain service with its own
database, a catalog of task types, roles, and skills, executor agents, and an orchestrator.
The article describes the architectural rules of a package, its parts, and the order of
building it on top of the core. For architects and integration developers.

## The main rule: a package, not a core extension

If functionality makes sense without a subject area, it is a candidate for the core and is
handled by a separate decision. If it exists **because** there is a subject area, it is a
package. No tables, endpoints, or events with domain words are added to the Control Plane
core (Rationale: TAI-ADR-0026, TAI-ADR-0030).

| Where it lives | What |
|---|---|
| **Core** (Control Plane, IAM, memory) | tasks, claims, runs, approvals, artifacts, events, roles, identity, knowledge |
| **Package** | domain entities and their rules, the domain state machine, domain gates, integrations with external sources, domain UI |

A package is connected to the core **only by identifiers** (`task_id`, `run_id`,
`artifact_id`, `approval_id`, `principal_id`, `workspace_id`) and core external references.
There are no foreign keys into other databases; binary documents are core artifacts (the
content lives in the core artifact storage, see
[Artifacts and comments](../control-plane/artifacts.md)).

## Package anatomy

```mermaid
flowchart TB
    subgraph Package
      API["Domain service<br/>(own DB, own IAM audience)"]
      ORC["Orchestrator<br/>(reconciliation over the core log)"]
      RUN["Executors<br/>(principal + PAT per agent)"]
      CAT["Catalog package<br/>(task types, roles, capabilities, skills)"]
    end
    subgraph Core
      CP[Control Plane]
      IAM[iam-service]
      MEM[memory-service]
    end
    CAT -->|make bootstrap| CP
    ORC -->|"GET /events, POST /tasks, approvals"| CP
    RUN -->|"claim → run → artifacts"| CP
    RUN -->|"domain writes"| API
    ORC --> API
    API -->|TokenVerifier| IAM
    RUN -->|"PAT exchange ×2 audiences"| IAM
    API -.->|"domain knowledge"| MEM
```

| Part | Purpose | Built on |
|---|---|---|
| Domain service | domain entities, invariants, state machine, API for the UI and agents | FastAPI + its own PostgreSQL + [platform-auth-sdk](platform-auth-sdk.md) |
| Catalog package | domain task types, roles, capabilities, skills — as data | YAML in `packages/<package>/`, [skill-sdk](skill-sdk.md) for skills |
| Executors | agents that take domain tasks assigned to them | [control-plane-client](clients.md), [platform-llm](platform-llm.md), or runner adapters |
| Orchestrator | "what next" for a domain object: creates tasks and approvals in the core based on events | the core event log, `control-plane-client` |
| Knowledge | domain reference data and history | a namespace in memory-service |

## Step 1. Domain service

The service is an ordinary platform resource service:

- it accepts **only** an IAM access token for its own audience (for example `acme-pack`); it
  does not accept a core token (`control-plane`) — `401 invalid_token`, even for the same
  principal;
- it verifies the token through `platform-auth-sdk` (`TokenVerifier` + `JwksCache` +
  `PolicyEnforcementPoint`) and responds with SDK codes;
- it distinguishes readers and writers by scopes (`acme-pack:read`, `acme-pack:write`,
  `acme-pack:admin`);
- it takes the tenant and principal from the token and marks every record with the principal
  from the token;
- it isolates data by tenant and workspace;
- it makes writes idempotent by natural keys (the source's external id, a document hash, the
  `run_id` of a decision) — agents and the orchestrator retry commands;
- it returns errors in a single envelope `{"error": {"code", "message", "details"}}`, like the
  core.

The image is built with the superproject root as the context (path dependencies, see
[SDK and integrations](index.md#connect)):

```yaml
acme-pack-db:
  image: postgres:16-alpine
  profiles: [acme]
  environment:
    POSTGRES_USER: acme
    POSTGRES_PASSWORD: ${ACME_DB_PASSWORD:?set ACME_DB_PASSWORD}
    POSTGRES_DB: acme
  volumes: [acme_pgdata:/var/lib/postgresql/data]
  networks: [taimen]

acme-pack-api:
  build:
    context: .
    dockerfile: acme-pack/Dockerfile
  profiles: [acme]
  environment:
    ACME_DATABASE_URL: postgresql+asyncpg://acme:${ACME_DB_PASSWORD}@acme-pack-db:5432/acme
    ACME_IAM_ISSUER: ${TAIMEN_PUBLIC_URL}/iam
    ACME_IAM_JWKS_URL: http://iam-service:8010/.well-known/jwks.json
    ACME_IAM_AUDIENCE: acme-pack
  ports: ["127.0.0.1:18110:8000"]
  networks: [taimen]
```

## Step 2. Audience in IAM

The package audience is created in the IAM tenant with a list of allowed scopes:

```bash
curl -s -X POST https://platform.example.com/iam/api/v1/tenants/$IAM_TENANT_ID/audiences \
  -H "X-IAM-Bootstrap-Token: $IAM_BOOTSTRAP_TOKEN" -H 'Content-Type: application/json' \
  -d '{"key": "acme-pack", "allowedScopes": ["acme-pack:read", "acme-pack:write", "acme-pack:admin"]}'
```

For audiences listed in the `AUDIENCES` registry of `deploy/bootstrap.py`, `make bootstrap`
does this (it idempotently brings `allowedScopes` in line with the registry). Details:
[Tokens, audiences, scopes](../iam/tokens.md).

## Step 3. Catalog package

The domain's task types, roles, capabilities, and skills are described as data in
`packages/<package>/` (format: [Catalog packages](../control-plane/catalog-packages.md)):

```yaml
# packages/acme/package.yaml
kind: Package
key: acme
spec:
  version: 0.1.0
  displayName: Acme
  description: Task types and skills for the Acme subject area
  requires: []
```

| Object | What it gives the package |
|---|---|
| `TaskType` | domain task types with their own statuses, `fieldSchema` for `customFields`, approval outcomes |
| `Role` | domain roles (who decides, who approves) |
| `Capability` | what executors can do; tasks require a capability |
| `Skill` | domain actions with a contract; the YAML is generated by `skill-sdk export` |

Task type keys carry the package prefix (`acme_document_parse`) so as not to overlap with
other packages. To install the package, add its key to the environment's installation file
(`deploy/packages.yaml` or your own, passed as `bootstrap.py --packages <file>`), then run
`make bootstrap`.

!!! warning "The core contract comes from code, not from memory"
    A typical package mistake is an "invented" core API contract against which both the code
    and the tests with a fake server are written. Take the schemas from `control-plane`
    (OpenAPI `/openapi.json`, the canonical client) and keep contract tests against a snapshot
    of `openapi.json` and a snapshot of the task type registry (`GET /api/v1/task-types`): the
    `typeKey` and `customFields` keys the package sends must exist in the registry.

## Step 4. Executor agents

**One agent — one principal — one PAT.** Otherwise the work of different agents is
indistinguishable in audit.

| What | Where | How |
|---|---|---|
| agent principal | Control Plane (`kind: agent` or `service`) | `POST /api/v1/principals` |
| agent principal | IAM (`kind: agent` — PATs are issued only to `human` and `agent`) | `POST /api/v1/tenants/{t}/principals` |
| binding | Control Plane | `POST /api/v1/principals/{id}/iam-bindings` with permissions; `admin` and `approvals.decide` are not granted to agents |
| PAT | IAM | `POST /api/v1/tenants/{t}/principals/{id}/platform-access-tokens` with `audiences` and `scopeCeiling` |

A package agent's PAT is issued for **two audiences** at once — the core and the package:

```bash
curl -s -X POST "$IAM/api/v1/tenants/$IAM_TENANT_ID/principals/$AGENT/platform-access-tokens" \
  -H "X-IAM-Bootstrap-Token: $IAM_BOOTSTRAP_TOKEN" -H "Idempotency-Key: $(uuidgen)" \
  -H 'Content-Type: application/json' \
  -d '{"name": "acme-document-analyst",
       "audiences": ["control-plane", "acme-pack"],
       "scopeCeiling": ["control-plane:read", "control-plane:write", "acme-pack:read", "acme-pack:write"],
       "expiresInSeconds": 15552000}'
```

The executor performs **two exchanges** of one PAT — one per audience — with independent
caches:

```python
pat = lambda: Path("/run/secrets/acme-document-analyst.pat").read_text()
cp_cred = IamCredential(iam_url, "", audience="control-plane",
                        scopes=("control-plane:read", "control-plane:write"),
                        platform_access_token=pat)
pack_cred = IamCredential(iam_url, "", audience="acme-pack",
                          scopes=("acme-pack:read", "acme-pack:write"),
                          platform_access_token=pat)
```


For your own package, issue the PAT through the IAM API as shown above.

How executors take work:

| Option | When |
|---|---|
| a container per agent with a daemon that takes **only the tasks assigned to it** | deterministic domain skills, LLM skills through `platform-llm` |
| a runner host with a coding agent adapter | tasks that require work in a repository (see [Executor adapters](../runner/adapters.md)) |
| a skill hosted through `skill-sdk` | an action the core executor calls by contract |

If an executor takes only assigned tasks, every AI stage must be assigned to an agent **at
creation time** — otherwise the pipeline stalls: keep one "task type → skill → principal"
table and compute the assignee from it.

Agent secrets are `<slug>.pat` files with permissions `0600`, mounted read-only; containers
run under an unprivileged uid (on Linux — `chown` to that uid).

## Step 5. Orchestrator

The orchestrator answers the question "what next" for a domain object and is implemented as
a **deterministic reconciliation loop**:

```mermaid
sequenceDiagram
    participant O as Orchestrator
    participant CP as Control Plane
    participant D as Package DB
    O->>CP: GET /api/v1/events?cursor=… (durable cursor in its own DB)
    CP-->>O: task.completed, approval.approved, artifact.created, …
    O->>D: find "its own" object by task/approval id (ledger)
    O->>O: recompute the object state
    O->>CP: POST /tasks, POST /approvals (idempotency key = object + stage)
    O->>D: write the stage to the ledger, advance the cursor
```

Orchestrator rules:

- **A durable cursor** in the package database; an event that could not be processed is
  retried, not skipped.
- **Filtering happens on the package side.** The core log is not filtered by workspace or
  event type; "own" tasks and approvals are found through a ledger table (`core_ref_id` →
  domain object), and others are skipped.
- **Idempotency** by the key `(object, stage)`: a repeated event does not create duplicate
  tasks, approvals, or decisions.
- **The stage result** is read from the task's artifacts (`GET /artifacts?taskId=`), and an
  unclear or empty result safely resolves to escalation to a human rather than to a random
  decision.
- **A human decision** is a core approval with a domain role; the approval outcome is
  declared by the task type (TAI-ADR-0041), not by package code.
- **Statuses** are compared by category (`terminal_success`, `terminal_cancelled`), not by
  key — keys are declared by the task type.

## Step 6. Human interface


The delivery has no web console with package modules. A human sees a package's tasks and
approvals in the same places as any core tasks: in the [MCP plugin](../operator/mcp-plugin.md),
the CLI, and [notifications](../notifications/index.md). Approval decisions are made in the
core, so the package does not need a separate interface for them.

If the domain needs its own UI, the UI is part of the package and calls the domain service
with an IAM access token for its audience, like any other client.

## Step 7. Knowledge

Domain reference data, regulations, and history are loaded into a dedicated memory-service
namespace (see [Knowledge ingestion](../memory/ingestion.md)). Executors get relevant
knowledge through the core task context, and the package service — through
[platform-memory-client](clients.md#memory-client) with its own grant.

## Step 8. Compose profiles

The package is started with separate profiles so that the core works without it:

| Profile | Contents |
|---|---|
| `<package>` | the domain service and its DB (the orchestrator is inside the service, turned on by a flag) |
| `<package>-runners` | executor containers, one per agent |

```bash
make up PROFILES="core <package> <package>-runners edge"
```

## Package readiness checklist

- [ ] Not a single change in the core for the sake of the domain.
- [ ] Its own audience; the service does not accept core tokens.
- [ ] All writes are idempotent and marked with the principal from the token.
- [ ] The package catalog is YAML in `packages/<package>/`, skills are generated from code.
- [ ] One principal and one PAT per agent, PATs in `0600` files.
- [ ] AI stages are assigned to an executor when the task is created.
- [ ] An orchestrator with a durable cursor and the idempotency key `(object, stage)`.
- [ ] Contract tests against a snapshot of the core `openapi.json`.
- [ ] The package's tasks and approvals are visible in the workplace and the MCP plugin
      without extra work.

## See also

- [SDK and integrations](index.md)
- [Catalog packages](../control-plane/catalog-packages.md)
- [Task types and statuses](../control-plane/task-types.md)
- [Approvals](../control-plane/approvals.md)
- [Control Plane events](../control-plane/events.md)
- [Agent identity](../runner/agent-identity.md)
