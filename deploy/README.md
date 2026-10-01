# deploy/ — startup and bootstrap

Everything needed to bring Taimen up from a clean clone to a working state. There are
no secrets in this directory: `.env`, PATs and the signing key live in `secrets/` and
`deploy/state/`, both in `.gitignore`. The detailed description is in the guide
`guide/` (the getting-started and operations sections).

```text
deploy/
├── bootstrap.py                 idempotent bootstrap: IAM → Control Plane → PAT → catalog → services → agents
├── packages.yaml                catalog installation file: which packages/ bootstrap installs
├── caddy/Caddyfile.local        edge for a local run: http, one host, routing by path
├── keycloak/platform-realm.json realm template for the optional idp profile
└── state/<env>.json             bootstrap state: identifiers, not secrets (in .gitignore)
```

Compose profiles, environment variables and ports are described in `compose.yml` and
`.env.example` at the root; they are not duplicated here.

## Local run

```bash
make secrets                     # .env (0600) with random secrets + secrets/iam-signing.pem
make up PROFILES="core notify edge"
make bootstrap
docker compose --profile notify up -d control-plane-api control-plane-worker context-adapter notification-service
make smoke
```

After the first bootstrap the core and notification-service are restarted once to
pick up the service accounts issued for them (`secrets/control-plane-iam.env`,
`secrets/notification-iam.env`); the script reminds you of this. On Linux the signing
key `secrets/iam-signing.pem`, which is mounted into the IAM container, must be owned
by uid 10001 with mode 600.

## What bootstrap does

`deploy/bootstrap.py --env .env` is idempotent: what has been done is recorded in
`deploy/state/<env>.json` (`<env>` is `COMPOSE_PROJECT_NAME` or `--name`); a repeated
run skips completed steps and brings the mutable parts (audience ceilings, binding
permissions, the catalog) in line with the registry in the script and the packages.
Secrets are never printed. The step numbers below are the ones the script prints.

- **1.** Waits for the Control Plane and IAM to be ready on the `127.0.0.1` ports.
- **2.** IAM: the tenant, audiences with their own scope ceilings (`control-plane`,
  `memory-service`, `notification-service`, `iam`), the operator's human principal
  (`--operator`, `Human Operator` by default).
- **2a.** IAM: the Control Plane service account for access to memory →
  `secrets/control-plane-iam.env`.
- **3.** Control Plane: `POST /api/v1/bootstrap` — the tenant (the same UUID as in IAM), the
  operator's admin principal and its binding in one transaction.
- **4.** The operator's PAT with the `control-plane:read/write/admin` ceiling →
  `secrets/harness-pat` (0600, lifetime `--pat-ttl`, 180 days by default); the
  exchange of the PAT for an access token is verified right away.
- **5.** Control Plane: a project template, a project and a workspace named after the
  tenant.
- **5b.** The catalog from [packages/](../packages/README.md) by the installation file
  `--packages` (default [packages.yaml](packages.yaml)) as one installation plan of the
  package SDK (the `package-sdk/` submodule): the plan is written to
  `deploy/state/<env>.packages-plan.json` and exactly that plan is applied; an empty
  plan is not applied, so a repeated run changes nothing. Needs the `package-sdk/`
  submodule (`make submodules`) and PyYAML with jsonschema — `make bootstrap` provides
  them through uv; without uv, the system `python3` must have them. Without either the
  script stops before its first step.
- **5c.** notification-service: an IAM service account → `secrets/notification-iam.env`, the
  service description and its identity in the Control Plane (permissions: reading
  events, approvals, tasks, principals and workspaces). The step always runs; the
  service picks up the file once the `notify` profile is started.
  Then the legacy api-key issued in step 3 is revoked: the installation is IAM-only.
- **6.** `--agents agents.json` (optional): agents — see below.

After the volumes are reset, the state file refers to objects that no longer exist;
the script notices this and asks for `make reset-state` — that target moves the state
and the issued credentials to `secrets/stale-<time>/`.

At the end the script reminds you to add `IAM_TENANT_ID=<uuid>` to `.env` and prints
the credential key for the CLI and the MCP plugin: `~/.config/iam/credentials.json`
(0600), entry `<issuer>|<tenant>|<principal>` → the contents of `secrets/harness-pat`.
The alternative without a file is the variables `IAM_CREDENTIAL_MODE=environment` and
`IAM_PLATFORM_ACCESS_TOKEN` (only together).

### Agent registry

```json
{
  "defaultAgentPermissions": ["sessions.open", "tasks.read", "tasks.write", "tasks.claim",
                              "events.read", "artifacts.read", "artifacts.write", "projects.read",
                              "task_types.read", "workspaces.read"],
  "agents": [
    {"slug": "coder", "displayName": "Coding Agent"},
    {"slug": "reviewer", "displayName": "Review Agent", "permissions": ["tasks.read", "tasks.write", "events.read"]}
  ]
}
```

`make bootstrap ARGS="--agents agents.json"` creates for each agent a principal in
the Control Plane and in IAM, a binding with permissions (`permissions`, otherwise
`defaultAgentPermissions`, otherwise a built-in list) and a PAT with the
`control-plane:read` + `control-plane:write` ceiling → `secrets/agents/<slug>.pat`. An
agent cannot be granted `admin` or `approvals.decide` — the script stops. The
identifiers are stored in the state under `agents.<slug>`; `--reissue-agent-pats`
reissues the PATs (the old file → `.pat.bak`).

## Runner for autonomous executors

The runner is the `control-plane-agent` daemon from the `control-plane` package: it
takes the tasks assigned to its principal, sets up a working copy of the repository,
starts the coding agent (Claude Code, Codex, OpenCode) and completes the run with
artifacts. It needs only HTTP access to the Control Plane and IAM, a git mirror of the
repository and the coding agent itself.

```bash
uv tool install ./control-plane        # control-plane, control-plane-mcp, control-plane-agent

export CONTROL_PLANE_SERVER=http://taimen.localhost
export CONTROL_PLANE_IAM_URL=http://taimen.localhost/iam
export CONTROL_PLANE_IAM_TENANT=$(grep '^IAM_TENANT_ID=' .env | cut -d= -f2)
export CONTROL_PLANE_IAM_SCOPES="control-plane:read control-plane:write"
export IAM_CREDENTIAL_MODE=environment IAM_PLATFORM_ACCESS_TOKEN=$(cat secrets/agents/coder.pat)
export CONTROL_PLANE_AGENT_ADAPTER=echo CONTROL_PLANE_AGENT_ONLY_ASSIGNED=1
export CONTROL_PLANE_AGENT_REPO=/srv/mirrors/my-repo.git CONTROL_PLANE_AGENT_WORKTREE_ROOT=/srv/worktrees
control-plane-agent
```

The `echo` adapter checks the pipeline without an LLM; for real work use
`CONTROL_PLANE_AGENT_ADAPTER=claude-code` (with `CLAUDE_CODE_OAUTH_TOKEN`) or `codex`.
Keep `CONTROL_PLANE_AGENT_ONLY_ASSIGNED=1` or `CONTROL_PLANE_AGENT_WORKSPACE` set:
without them the daemon takes the first available task of any workspace. The full list
of variables and how to operate the daemon are in the guide `guide/` and in the
`control-plane` documentation.

## Telegram notifications

The Telegram channel is enabled by the file `secrets/notification-telegram.env` with
the variables `NS_TELEGRAM_BOT_TOKEN`, `NS_TELEGRAM_WEBHOOK_SECRET` and
`NS_TELEGRAM_BOT_USERNAME`; without the file the service works with the web inbox and
email. The bot webhook is the public address `/notify/…` behind Caddy.

## External IdP (the idp profile)

The core does not need Keycloak: the operator and the agents work with Platform Access
Tokens. The `idp` profile starts Keycloak under `/auth` for installations where people
are authenticated by an external IdP: its token is exchanged in IAM
(`federation:exchange`), and authority still lives in IAM and the Control Plane. The
realm is imported from `keycloak/platform-realm.json` only on the first start; add the
clients of your own applications through the Admin API.

## Production installation

- Set `TAIMEN_PUBLIC_URL` (https) and `TAIMEN_PUBLIC_HOST`, provide your own Caddyfile
  with the domain (Caddy issues TLS) and point `CADDYFILE` at it; take the path
  layout from `caddy/Caddyfile.local`, without the `/memory/*` route.
- `KEYCLOAK_HOSTNAME_STRICT=true` if the `idp` profile is started.
- The IAM issuer (`${TAIMEN_PUBLIC_URL}/iam`) goes into tokens and into Control Plane
  bindings: changing the public address means migrating the bindings.
