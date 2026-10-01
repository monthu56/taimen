# Taimen

![Taimen — an open platform for humans, agents and workflows](.github/assets/cover.webp)

*Russian version: [README.ru.md](README.ru.md)*

**Taimen is an organizational runtime.** A platform where the work of an organization
is carried out by people, AI agents, software services and deterministic processes — in
any combination and under a single governance model. The central entity is not an
agent, a chat or a model but **work**: it has an origin, an executor, permissions,
acceptance criteria and evidence. Executors and models are replaceable; the work graph,
authority and execution history stay in the platform.

```text
State → Goal → Work derivation → Delegation → Execution → Observation
      → Verification → Reconciliation → New state
```

We do not aim to make AI as autonomous as possible. We aim for the work of an
organization to be done efficiently and verifiably — by the best available executor —
with every decision leaving a trace.

## Capabilities

### Work as a governed graph

- **Task types with their own vocabulary.** A tenant declares statuses, transitions,
  fields and approval outcomes; the core reasons about system status categories
  without knowing your names for them. Types are versioned.
- **Claiming and execution without races.** An atomic claim with a lease and a
  fencing token; execution attempts (runs) with checkpoints, actions and child runs;
  control of a run in progress.
- **Results and discussion.** Immutable artifacts with a type registry and files in
  S3-compatible storage; comments with edit history.
- **Approvals.** Approvals with outcomes declared by the task type: a human decision
  triggers declarative actions — open work, close it, send it back.

### Work that derives itself

- **Work rules.** A fact — an external observation, a core event or a schedule slot —
  is checked against a condition, interpreted by a skill when needed, and the core
  itself opens, updates, closes or cancels tasks. A rule has its own identity, and
  every evaluation has a history with evidence.
- **Processes in the core.** How an organization carries a matter through to a
  result — stages, deadlines on business calendars, assignments, approvals with quorum
  and separation of duties, timers, external events, compensation on cancellation. A
  process is written as YAML data and executed deterministically by the Control Plane
  itself: a test, a replay from the journal and a live run make the same decisions.
- **One expression language.** Conditions, keys, deadlines and computed fields are
  written in CEL, in the platform profile, with business-calendar functions.

### Verifying the result, not ticking "done"

- **Origin and acceptance.** A task has an `origin` (why it exists), acceptance
  criteria and evidence. Criteria can be deterministic, based on the state of an
  external system, or a judgement by a human or by a model against a rubric.
- **Verification stage.** A task becomes done only when its criteria pass; a failure
  returns the work to the executor or waits for a human.

### Catalog as code

- **Catalog packages in git.** Task and artifact types, roles, skills, rules,
  processes, calendars, agent descriptions and notification rules are YAML objects of
  a package. The package SDK (`package-sdk/`) checks a package without a running
  installation, runs its tests, builds an installation plan and applies exactly that
  plan to a live installation; how a package is structured, with an example, is in
  [packages/](packages/README.md).

### Vendor-neutral executors

- **One protocol for everyone.** A person through the MCP plugin or the CLI, the
  runner daemon with Claude Code, Codex and OpenCode adapters, a service over HTTP —
  all take work and write checkpoints and artifacts with the same commands.
- **An isolated working copy.** The runner prepares a working copy for the task with
  its neighbouring repositories, assembles the executor's instructions from layers
  (task type, project) and context from memory, and records the run as a transcript
  plus an action for every tool call.
- **Skills with a contract.** A skill is written in code with `skill-sdk`, and its
  contract is derived from the types; the core invokes it locally, over HTTP or via
  MCP. An external write requires a basis — an approved approval; network and tokens
  are up to the executor, not the contract.

### Identity and security

- **A separate IAM.** Tenants, principals for people, agents and services, Platform
  Access Tokens, exchange for short-lived tokens of a specific service with a scope
  ceiling, service accounts, OIDC federation of an external IdP, SCIM.
- **An agent is a full but constrained participant.** Its own principal and
  permissions, without `admin` and without deciding approvals; its work is
  distinguishable from a person's work in the audit log.
- **IAM-only from the first start**, with break-glass access in case IAM is
  unavailable.

### Memory with provenance

- **Knowledge graph.** Apache AGE and pgvector in a single PostgreSQL: observations,
  temporal facts, source documents, provenance and audit.
- **Retrieval and context assembly.** Hybrid search (vector, full-text, graph) with
  fusion and reranking; the Context Compiler assembles task context within a token
  budget, with references to sources. Processes read and write memory with the
  `recall` and `remember` steps.
- **Memory advises but does not govern.** Decisions are checked by the Control Plane;
  unavailability of memory does not block authoritative operations. It also works
  offline — with stubs instead of an LLM.

### Events and notifications

- **Event log.** An immutable log of domain events with a transactional outbox, a
  type catalog and data versions; subscriptions with filters, a cursor and WebSocket,
  and a Python consumer SDK.
- **Notifications.** Web inbox, Telegram and email; an approval can be decided right
  from the message. Which events become notifications, and for whom, is defined by
  data rules, not by service code.

## Components

The components are separate repositories, attached as submodules flat at the root of
this repository.

| Component | Purpose |
|---|---|
| [control-plane](https://github.com/taimen-ai/control-plane) | Work graph, work rules, processes, acceptance, skills, event log; CLI, MCP plugin and runner daemon |
| [iam-service](https://github.com/taimen-ai/iam-service) | Identity: tenants, principals, Platform Access Tokens, token exchange by audience, service accounts, federation, SCIM |
| [memory-service](https://github.com/taimen-ai/memory-service) | Memory: knowledge graph (Apache AGE + pgvector), hybrid search, context assembly, MCP server and client |
| [notification-service](https://github.com/taimen-ai/notification-service) | Notifications: web inbox, Telegram, email, notification rules, decisions from the channel |
| [platform-auth-sdk](https://github.com/taimen-ai/platform-auth-sdk) | Token and permission checks in services (Policy Enforcement Point) |
| [skill-sdk](https://github.com/taimen-ai/skill-sdk) | Skill SDK: contract from code, invocation context, `local` / `http` / `mcp` hosting |
| [platform-llm](https://github.com/taimen-ai/platform-llm) | Client for any OpenAI-compatible endpoint with structured output |
| [package-sdk](https://github.com/taimen-ai/package-sdk) | Package SDK: tools for catalog package authors — `check` / `test` / `plan` / `apply`, an MCP server and a plugin for Claude Code |

The flat layout is intentional: `control-plane`, `memory-service`,
`notification-service` and `skill-sdk` take their neighbours (`../platform-auth-sdk`,
`../platform-llm`, the core client) as path dependencies, so images are built from the
root of this repository. `package-sdk` takes `../control-plane` (the core and its
client) and `../skill-sdk` the same way for its extras.

This repository itself is the assembly: `compose.yml`, `.env.example`, `Makefile`,
[deploy/](deploy/README.md) (bootstrap and the edge), `tools/` (build and check
scripts) and the guide `guide/`.

## Quick start

You need Docker with Compose v2, Python 3, `openssl` and
[uv](https://docs.astral.sh/uv/): `make bootstrap` runs through uv to get PyYAML and
jsonschema for its catalog step, and uv installs the CLI and the MCP plugin. The default memory limits are sized for a machine with 8 GB of RAM.

```bash
git clone --recurse-submodules https://github.com/taimen-ai/taimen.git && cd taimen
make secrets      # .env (0600) with random secrets + secrets/iam-signing.pem
make up           # profiles core edge: IAM, Control Plane, memory, MinIO, Caddy, guide
make bootstrap    # tenant, operator, PAT, workspace, catalog → deploy/state/<env>.json and secrets/
docker compose up -d control-plane-api control-plane-worker context-adapter
make smoke        # healthz of the running services
```

Restarting the core after the first `make bootstrap` is needed once: the core picks up
the service account issued by bootstrap for access to memory (the script reminds you
of this itself).

Once running, the platform is available at `http://taimen.localhost` (Chrome and
Firefox resolve `*.localhost` themselves; for curl and Safari add
`127.0.0.1 taimen.localhost` to `/etc/hosts`): the Control Plane at `/api/v1` with the
schema at `/docs`, IAM at `/iam`, the guide at `/guide/`. The same services listen on
`127.0.0.1` on the ports from `.env` (`CP_HOST_PORT`, `IAM_HOST_PORT`,
`MEMORY_HOST_PORT`). `make down` stops the containers; data stays in the volumes.

Compose profiles:

| Profile | What it starts |
|---|---|
| `core` | IAM, Control Plane (api / worker / context-adapter), memory-service, their databases, MinIO for artifacts |
| `notify` | notification-service and its database |
| `edge` | Caddy — the only entry point from outside — and the guide `guide/` |
| `idp` | optional: Keycloak as an external IdP for people via IAM federation; the core does not need it |

```bash
make up PROFILES="core notify edge"   # with notifications
```

By default memory works offline (`MEMORY_EMBEDDING_PROVIDER=fake`,
`MEMORY_LLM_PROVIDER=echo`). To connect any OpenAI-compatible endpoint, set
`LLM_BASE_URL` and `LLM_API_KEY` in `.env` and switch both providers to `openai`. On
Linux the signing key `secrets/iam-signing.pem` must be owned by uid 10001 (mode 600).

### First task through the MCP plugin

1. `make bootstrap` prints the credential key for the CLI and the MCP plugin: put the
   contents of `secrets/harness-pat` into `~/.config/iam/credentials.json` (0600)
   under the key `<issuer>|<tenant>|<principal>` and add the printed
   `IAM_TENANT_ID=<uuid>` to `.env`.
2. Install the Control Plane package (the neighbouring `platform-auth-sdk` is already
   in place): `uv tool install ./control-plane` — this gives you `control-plane` (the
   CLI), `control-plane-mcp` (the MCP server) and `control-plane-agent` (the runner
   daemon).
3. Connect the MCP server to your coding agent, for example Claude Code:
   `claude mcp add control-plane -- control-plane-mcp`. There are no secrets in the MCP
   configuration: the server finds the credential itself.
4. In a session, call `cp_whoami` and `cp_context`, then create a task with
   `cp_create_task` and take it through `cp_claim_task`, `cp_start_run`,
   `cp_create_artifact` and `cp_complete_run`.

Agents with their own principals and PATs are created by `make bootstrap ARGS="--agents
agents.json"`; the registry format and how to start the runner daemon are in
[deploy/README.md](deploy/README.md).

### Package authoring in Claude Code

Catalog packages (task types, rules, processes, agents, integrations, ontologies,
notifications) are written with an agent in Claude Code through the `package-author`
plugin of the [package-sdk](package-sdk/README.md) component. The `package-sdk/`
submodule is both the `package-sdk` marketplace (`.claude-plugin/marketplace.json`) and
the source of the plugin (`plugin/package-author`). From the root of this repository:

```bash
# The plugin's MCP server is package-sdk mcp. Install it from a permanent checkout:
# the core and skill-sdk are linked as editable references to the neighbouring directories.
uv tool install --reinstall "./package-sdk[mcp,sandbox,skills]"

# The marketplace and the plugin (inside Claude Code, the same commands through /plugin)
claude plugin marketplace add ./package-sdk
claude plugin install package-author@package-sdk
```

Inside a session: `/plugin marketplace add ./package-sdk`, then
`/plugin install package-author@package-sdk`. Instead of the local submodule you can
point to the component's repository on GitHub: `/plugin marketplace add
taimen-ai/package-sdk`. The installations the server may reach are listed in
`PACKAGE_SDK_SERVERS` in the session environment; the core's `cp_*` tools come to the
skills from the operator's MCP plugin above. Check: in a new session `/plugin` shows
`package-author`, and `/mcp` shows the `package-sdk` server with its `pkg_*` tools.
Details are in the [plugin README](package-sdk/plugin/package-author/README.md) and the
[guide article](guide/docs/packages/author-plugin.md).

## Guide

The technical and operations documentation of the platform is the guide in the
`guide/` directory (MkDocs Material, in English, with a Russian version): installation
and configuration, the work model, identity, memory, notifications, executors,
operations and the API reference.

```bash
make guide         # build into guide/site (mkdocs --strict)
make guide-serve   # with live reload at http://127.0.0.1:8008
```

In a running platform the guide is served at `/guide/`, with the Russian version at
`/guide/ru/` (the `guide` service of the `edge` profile).

## Development

```bash
make submodules          # submodules at their pinned revisions
make check               # ruff + unit tests of all components and tools/, as in CI
make check-control-plane # a single component
make help                # all targets
```

A change to a component is made as a pull request to its repository; the submodule
pointer here is moved in a separate commit after the component is released.

## Versions

The platform is at version 0.x: API compatibility is not promised before 1.0, and
breaking changes are described in the component's release notes. A platform tag
`vX.Y.Z` is set in this repository and pins the revisions of all components.

## Contributing, security and licence

- [CONTRIBUTING.md](CONTRIBUTING.md) — how to propose a change; every contribution
  requires a signed Contributor License Agreement (CLA).
- [SECURITY.md](SECURITY.md) — how to report a vulnerability privately.
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — the code of conduct.
- Licence — [Apache-2.0](LICENSE); see also [NOTICE](NOTICE) and
  [THIRD_PARTY.md](THIRD_PARTY.md). The Taimen name and logo are not covered by the
  licence — see [TRADEMARK.md](TRADEMARK.md).

## Author

Aleksandr Pereboev — architecture and code of the platform. Questions and proposals —
via the issues of this repository.
