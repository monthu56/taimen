# Taimen

*English summary. The primary documentation of this repository is in Russian:
[README.md](README.md).*

Taimen is an organizational runtime: a control plane for governed execution of
organizational work by people, AI agents, software services and deterministic
processes, in any combination. The central entity is **work**, not an agent, a chat or
a model: executors and models are replaceable, while the work graph, authority and
execution history stay in the platform.

## What is inside

- **Governed work graph**: task types with your own status vocabulary, atomic claims
  with leases and fencing tokens, runs with checkpoints, typed immutable artifacts in
  S3-compatible storage, comments, and approvals whose outcomes are declared by the
  task type.
- **Work that derives itself**: work rules turn facts — external observations, core
  events, schedule slots — into tasks that are opened, updated or closed
  automatically, each evaluation keeping its evidence.
- **Processes in the core**: stages, deadlines on business calendars, assignments,
  approvals with quorum and separation of duties, timers, external events and
  compensation, written as YAML data and executed deterministically by the Control
  Plane; expressions in CEL.
- **Verified results**: every task carries its origin, acceptance criteria
  (deterministic, external state, human or model judgement) and evidence; a task is
  done only when its criteria pass.
- **Catalog as code**: task and artifact types, roles, skills, rules, processes,
  calendars, agent descriptions and notification rules live in git as packages;
  `tools/cp_packages.py` checks, tests, plans and applies them.
- **Vendor-neutral executors**: one protocol for people (MCP plugin, CLI), the runner
  daemon with Claude Code, Codex and OpenCode adapters, and services over HTTP;
  skills are written with `skill-sdk` and invoked locally, over HTTP or via MCP.
- **Identity for people, agents and services**: a separate IAM issues Platform Access
  Tokens and exchanges them for short-lived, audience-specific tokens with scope
  ceilings; service accounts, OIDC federation, SCIM; IAM-only from the first start,
  with a break-glass path.
- **Memory with provenance**: a knowledge graph (Apache AGE + pgvector) with temporal
  facts, hybrid retrieval and a context compiler that assembles task context within a
  token budget and with source references.
- **Events and notifications**: an immutable event log with an outbox, filtered
  subscriptions and a consumer SDK; web inbox, Telegram and email notifications driven
  by data rules, with approval decisions right from the message.

## Components

| Component | Purpose |
|---|---|
| [control-plane](https://github.com/taimen-ai/control-plane) | Work graph, work rules, processes, acceptance, skills, event log; CLI, MCP plugin, runner daemon |
| [iam-service](https://github.com/taimen-ai/iam-service) | Tenants, principals, Platform Access Tokens, token exchange, service accounts, federation, SCIM |
| [memory-service](https://github.com/taimen-ai/memory-service) | Knowledge graph memory and context assembly |
| [notification-service](https://github.com/taimen-ai/notification-service) | Notifications and channel decisions |
| [platform-auth-sdk](https://github.com/taimen-ai/platform-auth-sdk) | Token and permission enforcement for services |
| [skill-sdk](https://github.com/taimen-ai/skill-sdk) | Skill SDK with `local`, `http` and `mcp` hosting |
| [platform-llm](https://github.com/taimen-ai/platform-llm) | Client for any OpenAI-compatible endpoint |

## Quick start

Requirements: Docker with Compose v2, Python 3, `openssl`, and
[uv](https://docs.astral.sh/uv/) for the CLI and the MCP plugin.

```bash
git clone --recurse-submodules https://github.com/taimen-ai/taimen.git && cd taimen
make secrets
make up           # profiles core edge
make bootstrap
docker compose up -d control-plane-api control-plane-worker context-adapter
make smoke
```

The platform is then served at `http://taimen.localhost`: the Control Plane API under
`/api/v1` (schema at `/docs`), IAM under `/iam` and the guide under `/guide/`. Add
`notify` to `PROFILES` for notifications; `idp` (Keycloak) is optional.

## Guide

The technical and operations guide lives in `guide/` (MkDocs Material, in Russian):
`make guide` builds it, `make guide-serve` serves it at `http://127.0.0.1:8008`.

## Contributing and licence

Contributions require a signed Contributor License Agreement
([individual](cla/CLA-individual.md) or [entity](cla/CLA-entity.md)); see
[CONTRIBUTING.md](CONTRIBUTING.md). Report vulnerabilities privately as described in
[SECURITY.md](SECURITY.md). Licensed under [Apache-2.0](LICENSE); the Taimen name and
logo are covered by [TRADEMARK.md](TRADEMARK.md).
