#!/usr/bin/env python3
"""Idempotent bootstrap of the Taimen platform (make bootstrap).

Initial setup of IAM and the Control Plane in one pass:

  1. waits for the Control Plane and IAM to be ready on the 127.0.0.1 ports;
  2. IAM: the tenant, audiences with their own scope ceilings, the operator's human principal;
  2a. IAM: the Control Plane service account (memory) → secrets/control-plane-iam.env;
  3. Control Plane: POST /api/v1/bootstrap with the operator's `iamBinding` → the tenant (the
     same UUID as in IAM), the admin principal and the first IAM↔CP binding in one transaction;
  4. a fresh authentication context → the operator's Platform Access Token with the
     read/write/admin ceiling → secrets/harness-pat (0600); the PAT exchange is verified right away;
  5. Control Plane: project template, project and workspace;
  5b. packages by the installation file (--packages, default deploy/packages.yaml) as one
     installation plan of the package SDK (the package-sdk submodule): `install.plan()`
     writes the plan to deploy/state/<env>.packages-plan.json and `install.apply()` applies
     exactly that plan — the catalog, processes and calendars, notification rules and
     `retire` of the installation file. Running the initial setup stands for the human's
     confirmation here (assume_yes, marked in the log); an empty plan is not applied;
  5c. notification-service: an IAM service account, the service description and its identity in
     the core → secrets/notification-iam.env (the service picks up the file on `up -d`);
     then the legacy api-key from the step 3 response is revoked — the installation is IAM-only;
  6. --agents agents.json (optional): agent principals in the Control Plane and IAM,
     bindings and PATs with the read/write ceiling → secrets/agents/<slug>.pat.

State lives in deploy/state/<env>.json: the identifiers are not secret; a repeated run
skips what is done and brings the mutable parts (audience ceilings, binding permissions)
in line with the registry in the script and the catalog with the packages. Secrets are never
printed. HTTP uses the Python standard library only; step 5b needs the package-sdk
submodule (`make submodules`) and PyYAML with jsonschema (`make bootstrap` provides them
through uv):

    uv run --no-project --with pyyaml --with jsonschema python3 deploy/bootstrap.py --env .env
    python3 deploy/bootstrap.py --env .env --agents agents.json   # system python3 with both modules
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The package SDK (the package-sdk submodule) installs the packages at step 5b.
PACKAGE_SDK_SRC = ROOT / "package-sdk" / "src"

# Python modules step 5b needs (the package SDK): import name → package name.
CATALOG_MODULES = {"yaml": "PyYAML", "jsonschema": "jsonschema"}

# IAM audiences and their scope ceilings: one token — one service.
AUDIENCES = {
    # control-plane:decide — deciding a single approval from a notification channel
    "control-plane": ["control-plane:read", "control-plane:write", "control-plane:admin", "control-plane:decide"],
    # memory:tenants and memory:service — only the core's service account;
    # memory:on-behalf — a service reads memory on behalf of a principal
    "memory-service": [
        "memory:read",
        "memory:write",
        "memory:pii",
        "memory:tenants",
        "memory:on-behalf",
        "memory:service",
    ],
    # send — senders, read — a person's inbox, admin — mandatory rules and channel groups
    "notification-service": ["notifications:send", "notifications:read", "notifications:admin"],
    # IAM itself as an audience: the notification service confirms channel links
    "iam": ["iam:channel-links", "iam:agents"],
}

# Control Plane service account: context-adapter writes the memory of all tenants.
# The secret lives only in secrets/control-plane-iam.env (env_file of the core processes).
CP_SERVICE_ACCOUNT = {
    "displayName": "Taimen Control Plane",
    "audiences": ["memory-service"],
    "scopeCeiling": ["memory:read", "memory:write", "memory:tenants", "memory:on-behalf", "memory:service"],
}

# notification-service is an agent without placement, with an identity of kind service: the
# description in the core defines its permissions, the IAM part is a service account. It reads
# events and the core's recipient directory, and confirms channel links in IAM.
NOTIFICATION_AGENT = {
    "key": "notification-service",
    "spec": {
        "displayName": "Taimen Notification Service",
        "identity": {
            "kind": "service",
            "permissions": ["events.read", "approvals.read", "tasks.read", "principals.read", "workspaces.read"],
            "iam": {
                "audiences": ["control-plane", "iam"],
                "scopeCeiling": ["control-plane:read", "iam:channel-links"],
            },
        },
        "placement": "none",
    },
}

# Default agent permissions (the --agents registry): without admin and approvals.decide.
AGENT_DEFAULT_PERMISSIONS = [
    "sessions.open",
    "tasks.read",
    "tasks.write",
    "tasks.claim",
    "events.read",
    "artifacts.read",
    "artifacts.write",
    "projects.read",
    "task_types.read",
    "workspaces.read",
]
OPERATOR_CEILING = ["control-plane:read", "control-plane:write", "control-plane:admin"]


class Http:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")

    def call(self, method: str, path: str, body: dict | None = None, headers: dict | None = None) -> dict:
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        for key, value in (headers or {}).items():
            req.add_header(key, value)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")[:400]
            raise RuntimeError(f"{method} {path}: HTTP {error.code}: {detail}") from error

    def wait(self, path: str, timeout: int = 180) -> None:
        deadline = time.time() + timeout
        while True:
            try:
                with urllib.request.urlopen(self.base + path, timeout=5) as response:
                    if response.status < 400:
                        return
            except (urllib.error.URLError, OSError):
                pass
            if time.time() >= deadline:
                raise SystemExit(f"timed out waiting for {self.base}{path}")
            time.sleep(2)


def read_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def secure_write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(descriptor, value.encode())
    finally:
        os.close(descriptor)


def require_catalog_modules() -> None:
    """Fail before the first write if step 5b could not run: better than a half-done bootstrap."""
    if not (PACKAGE_SDK_SRC / "package_sdk").is_dir():
        raise SystemExit(
            "there is no package-sdk/ submodule: step 5b (catalog from packages) needs the package SDK — "
            "run `make submodules`"
        )
    missing = [name for module, name in CATALOG_MODULES.items() if importlib.util.find_spec(module) is None]
    if missing:
        raise SystemExit(
            f"{' and '.join(missing)} required by step 5b (catalog from packages): install uv and run "
            "`make bootstrap`, or `pip install pyyaml jsonschema` for this python3"
        )


def install_packages(installation: Path, *, cp_base: str, exchange, env: dict, plan_path: Path, log=print) -> dict:
    """5b. Packages as one installation plan of the package SDK: the plan is written to
    plan_path and exactly that plan is applied. Bootstrap is not interactive: assume_yes
    stands for the human's answer — the only way to install without a confirmation, and the
    log says so. A plan without changes is not applied, so a repeated bootstrap writes
    nothing. The token of the core comes from `exchange` before every request and is renewed
    before it expires: an access token lives minutes."""
    sys.path.insert(0, str(PACKAGE_SDK_SRC))
    # the package-sdk submodule, checked by require_catalog_modules before the first step
    from package_sdk import install, model
    from package_sdk.apply import Http as PackageHttp
    from package_sdk.apply import HttpError
    from package_sdk.auth import Bearer
    from package_sdk.install.plan import needs_notify

    model.ROOT = ROOT
    model.PACKAGES_DIR = ROOT / "packages"
    try:
        target = install.Target(server=cp_base, http=PackageHttp(cp_base), token=Bearer.expiring(exchange))
        if needs_notify(install.load(installation, strict=False).installation):
            url, token = env.get(model.NOTIFY_URL_ENV), env.get(model.NOTIFY_TOKEN_ENV)
            if not url or not token:
                raise SystemExit(
                    f"step 5b stopped: {installation.name} installs or retires notification rules — set "
                    f"{model.NOTIFY_URL_ENV} (the notification-service address) and {model.NOTIFY_TOKEN_ENV} "
                    f"(an access token for the {model.NOTIFY_AUDIENCE} audience)"
                )
            target.notify = (PackageHttp(url), Bearer.static_token(token))
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        document = install.plan(installation, target=target, env=env, out=plan_path, log=log)
        changes = install.count_changes(document)
        summary = {"plan": str(plan_path.relative_to(ROOT)), "planHash": document["planHash"], "changes": changes}
        if not changes:
            log("the plan is empty: the installation already matches, nothing to apply")
            return {**summary, "applied": False}
        log(
            f"bootstrap: plan {document['planHash']} ({changes} changes) is applied without a human's "
            "confirmation — running the initial setup is the operator's decision (assume_yes)"
        )
        install.apply(plan_path, target=target, env=env, assume_yes=True, log=log)
        return {**summary, "applied": True}
    except model.PackageError as error:
        raise SystemExit(f"step 5b stopped: {error}") from error
    except HttpError as error:
        message = f"step 5b stopped: the installation answered HTTP {error.status}: {str(error)[:400]}"
        raise SystemExit(message) from error


def issue_pat(
    iam: Http,
    bootstrap: dict,
    *,
    tenant: str,
    principal: str,
    name: str,
    ceiling: list[str],
    ttl: int,
    audiences: list[str] | None = None,
) -> dict:
    return iam.call(
        "POST",
        f"/api/v1/tenants/{tenant}/principals/{principal}/platform-access-tokens",
        {"name": name, "audiences": audiences or ["control-plane"], "scopeCeiling": ceiling, "expiresInSeconds": ttl},
        {**bootstrap, "Idempotency-Key": str(uuid.uuid4())},
    )


def revoke_service_account(iam: Http, bootstrap: dict, tenant: str, client_id: str) -> None:
    try:
        iam.call("POST", f"/api/v1/tenants/{tenant}/service-accounts/{client_id}:revoke", None, bootstrap)
        print("   previous service account revoked:", client_id)
    except RuntimeError as error:
        print("   previous service account not revoked:", str(error)[:120])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env", default=".env")
    parser.add_argument("--name", default=None, help="environment name (default: COMPOSE_PROJECT_NAME)")
    parser.add_argument("--operator", default="Human Operator")
    parser.add_argument("--tenant-slug", default=None)
    parser.add_argument("--agents", default=None, help="agent registry (agents.json) — optional")
    parser.add_argument("--pat-ttl", type=int, default=180 * 24 * 3600)
    parser.add_argument("--secrets-dir", default="secrets")
    parser.add_argument(
        "--packages", default="deploy/packages.yaml", help="catalog installation file (kind: Installation), step 5b"
    )
    parser.add_argument(
        "--reissue-agent-pats",
        action="store_true",
        help="reissue agent PATs even if the file exists (old file → .bak)",
    )
    args = parser.parse_args()
    require_catalog_modules()

    env = read_env(ROOT / args.env)
    project = env.get("COMPOSE_PROJECT_NAME", "taimen")
    name = args.name or project
    public_url = env["TAIMEN_PUBLIC_URL"].rstrip("/")
    issuer = f"{public_url}/iam"
    slug = args.tenant_slug or project
    secrets_dir = ROOT / args.secrets_dir
    state_path = ROOT / "deploy" / "state" / f"{name}.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    cp = Http(f"http://127.0.0.1:{env.get('CP_HOST_PORT', '18000')}")
    iam = Http(f"http://127.0.0.1:{env.get('IAM_HOST_PORT', '18010')}")
    bootstrap_header = {"X-IAM-Bootstrap-Token": env["IAM_BOOTSTRAP_TOKEN"]}

    def save() -> None:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")

    print("1. waiting for services")
    cp.wait("/health/ready")
    iam.wait("/healthz")

    if "iamTenantId" in state:
        # The state survived a volume reset: its ids no longer exist, and "already done"
        # would be a lie.
        try:
            iam.call("GET", f"/api/v1/tenants/{state['iamTenantId']}/audiences", headers=bootstrap_header)
        except RuntimeError as error:
            if "HTTP 404" in str(error):
                raise SystemExit(
                    f"{state_path.relative_to(ROOT)} refers to IAM tenant {state['iamTenantId']}, "
                    "which does not exist in IAM (volumes reset?). Run `make reset-state` and repeat bootstrap."
                ) from error
            raise

    print("2. IAM tenant, audiences, operator principal")
    if "iamTenantId" not in state:
        tenant = iam.call("POST", "/api/v1/tenants", {"slug": slug, "name": slug}, bootstrap_header)
        state["iamTenantId"] = tenant["id"]
        save()
    iam_tenant = state["iamTenantId"]
    ready = set(state.get("iamAudiences", []))
    for key, scopes in AUDIENCES.items():
        if key not in ready:
            try:
                iam.call(
                    "POST",
                    f"/api/v1/tenants/{iam_tenant}/audiences",
                    {"key": key, "allowedScopes": scopes},
                    bootstrap_header,
                )
            except RuntimeError as error:
                if "409" not in str(error):
                    raise
            ready.add(key)
            state["iamAudiences"] = sorted(ready)
            save()
        # A service's ceiling grows with the service: bring allowedScopes in line with the registry
        # (PATCH is idempotent; an older IAM without it is a warning, not a stop).
        try:
            iam.call(
                "PATCH", f"/api/v1/tenants/{iam_tenant}/audiences/{key}", {"allowedScopes": scopes}, bootstrap_header
            )
        except RuntimeError as error:
            if "HTTP 404" in str(error) or "HTTP 405" in str(error):
                print(f"   !! IAM cannot PATCH audiences ({key}): upgrade iam-service")
            else:
                raise
    if "iamOperatorPrincipalId" not in state:
        principal = iam.call(
            "POST",
            f"/api/v1/tenants/{iam_tenant}/principals",
            {"kind": "human", "displayName": args.operator},
            bootstrap_header,
        )
        state["iamOperatorPrincipalId"] = principal["id"]
        save()
    print("   IAM tenant", iam_tenant, "operator", state["iamOperatorPrincipalId"])
    if env.get("IAM_TENANT_ID", "") != iam_tenant:
        print(f"   !! add to {args.env}: IAM_TENANT_ID={iam_tenant} (needed by clients and runners)")

    print("2a. Control Plane service account in IAM")
    sa_env = secrets_dir / "control-plane-iam.env"
    # IAM has no PATCH for a service account's ceiling: if the ceiling in the code grew, issue
    # a new service account and revoke the previous one.
    ceiling = sorted(CP_SERVICE_ACCOUNT["scopeCeiling"]) + sorted(CP_SERVICE_ACCOUNT["audiences"])
    stale = "cpServiceAccountClientId" in state and state.get("cpServiceAccountCeiling") != ceiling
    if stale:
        print("   service account ceiling changed — reissuing")
    if "cpServiceAccountClientId" not in state or not sa_env.exists() or stale:
        issued = iam.call(
            "POST", f"/api/v1/tenants/{iam_tenant}/service-accounts", CP_SERVICE_ACCOUNT, bootstrap_header
        )
        secure_write(sa_env, f"CP_IAM_CLIENT_ID={issued['clientId']}\nCP_IAM_CLIENT_SECRET={issued['clientSecret']}\n")
        previous = state.get("cpServiceAccountClientId")
        state["cpServiceAccountClientId"] = issued["clientId"]
        state["cpServiceAccountPrincipalId"] = issued["principalId"]
        state["cpServiceAccountCeiling"] = ceiling
        save()
        if previous and previous != issued["clientId"]:
            revoke_service_account(iam, bootstrap_header, iam_tenant, previous)
        print("   issued →", sa_env, "client", issued["clientId"])
        print(
            "   !! restart the core so that it picks up the env file: "
            "docker compose up -d control-plane-api control-plane-worker context-adapter"
        )
    else:
        print("   already exists:", sa_env, "client", state["cpServiceAccountClientId"])

    print("3. Control Plane bootstrap with the operator binding")
    if "cpTenantId" not in state:
        # A single platform tenant: the Control Plane gets the UUID of the IAM tenant.
        boot = cp.call(
            "POST",
            "/api/v1/bootstrap",
            {
                "tenantSlug": slug,
                "tenantName": slug.replace("-", " ").title(),
                "adminDisplayName": args.operator,
                "tenantId": iam_tenant,
                "iamBinding": {
                    "issuer": issuer,
                    "iamTenantId": iam_tenant,
                    "iamPrincipalId": state["iamOperatorPrincipalId"],
                },
            },
            {"Authorization": f"Bearer {env['CP_BOOTSTRAP_TOKEN']}"},
        )
        state["cpTenantId"] = boot["tenant"]["id"]
        state["cpOperatorPrincipalId"] = boot["adminPrincipal"]["id"]
        state["cpLegacyAdminKeyId"] = boot["apiKey"]["id"]
        state["cpOperatorBindingId"] = (boot.get("iamBinding") or {}).get("id")
        save()
        print(
            "   tenant",
            state["cpTenantId"],
            "operator",
            state["cpOperatorPrincipalId"],
            "binding",
            state["cpOperatorBindingId"],
        )
    else:
        print("   already done:", state["cpTenantId"])
    if state["cpTenantId"] != iam_tenant:
        print(
            f"   !! core tenant {state['cpTenantId']} ≠ IAM tenant {iam_tenant}: "
            "the installation predates the single tenant"
        )

    print("4. operator PAT")
    pat_file = secrets_dir / "harness-pat"
    if not pat_file.exists():
        # IAM issues a PAT to a human only with a fresh authentication context (≤ 300 s).
        iam.call(
            "POST",
            f"/api/v1/tenants/{iam_tenant}/principals/{state['iamOperatorPrincipalId']}/authentication-contexts",
            {"issuer": issuer, "acr": "bootstrap", "amr": ["bootstrap-script"]},
            bootstrap_header,
        )
        issued = issue_pat(
            iam,
            bootstrap_header,
            tenant=iam_tenant,
            principal=state["iamOperatorPrincipalId"],
            name=f"harness-admin-{time.strftime('%Y-%m')}",
            ceiling=OPERATOR_CEILING,
            ttl=args.pat_ttl,
        )
        secure_write(pat_file, issued["token"] + "\n")
        credential = issued.get("credential") or {}
        state["operatorPatPrefix"] = credential.get("publicPrefix")
        state["operatorPatExpiresAt"] = credential.get("expiresAt")
        save()
        print("   issued →", pat_file, "prefix", state.get("operatorPatPrefix"))
    else:
        print("   already exists:", pat_file)
    pat = pat_file.read_text().strip()
    exchange = iam.call(
        "POST",
        "/api/v1/platform-access-tokens:exchange",
        {"token": pat, "audience": "control-plane", "scopes": OPERATOR_CEILING},
    )
    auth = {"Authorization": f"Bearer {exchange['accessToken']}"}
    print("   PAT → access token exchange: ok")

    print("5. Control Plane: project template, project, workspace")
    if "templateId" not in state:
        template = cp.call(
            "POST", "/api/v1/project-templates", {"key": slug, "displayName": slug.replace("-", " ").title()}, auth
        )
        state["templateId"] = template["id"]
        save()
    if "projectId" not in state:
        project_view = cp.call(
            "POST",
            "/api/v1/projects",
            {
                "workspaceSlug": slug,
                "workspaceName": slug.replace("-", " ").title(),
                "workspaceTypeKey": "generic",
                "templateId": state["templateId"],
                "ownerPrincipalId": state["cpOperatorPrincipalId"],
            },
            auth,
        )
        state["projectId"] = project_view["id"]
        state["workspaceId"] = project_view["workspaceId"]
        save()
    print("   project", state["projectId"], "workspace", state["workspaceId"])

    print("5b. packages as one installation plan:", args.packages)
    state.pop("catalog", None)  # the summary of the previous installer, without a plan
    state["packages"] = {
        "install": args.packages,
        **install_packages(
            ROOT / args.packages,
            cp_base=cp.base,
            exchange=lambda: iam.call(
                "POST",
                "/api/v1/platform-access-tokens:exchange",
                {"token": pat, "audience": "control-plane", "scopes": OPERATOR_CEILING},
            ),
            env={**env, **os.environ},
            plan_path=state_path.with_name(f"{name}.packages-plan.json"),
            log=lambda line: print("  ", line),
        ),
    }
    save()

    print("5c. notification-service: IAM service account, identity in the core, env file")
    ns_env = secrets_dir / "notification-iam.env"
    identity = NOTIFICATION_AGENT["spec"]["identity"]
    account = {
        "displayName": NOTIFICATION_AGENT["spec"]["displayName"],
        "audiences": identity["iam"]["audiences"],
        "scopeCeiling": identity["iam"]["scopeCeiling"],
    }
    ceiling = sorted(account["scopeCeiling"]) + sorted(account["audiences"])
    stale = "notifyServiceAccountClientId" in state and state.get("notifyServiceAccountCeiling") != ceiling
    if stale:
        print("   ceiling or audiences changed — reissuing")
    if "notifyServiceAccountClientId" not in state or not ns_env.exists() or stale:
        issued = iam.call("POST", f"/api/v1/tenants/{iam_tenant}/service-accounts", account, bootstrap_header)
        previous = state.get("notifyServiceAccountClientId")
        state["notifyServiceAccountClientId"] = issued["clientId"]
        state["notifyIamPrincipalId"] = issued["principalId"]
        state["notifyServiceAccountCeiling"] = ceiling
        save()
        secure_write(
            ns_env, f"NS_SERVICE_CLIENT_ID={issued['clientId']}\nNS_SERVICE_CLIENT_SECRET={issued['clientSecret']}\n"
        )
        if previous and previous != issued["clientId"]:
            revoke_service_account(iam, bootstrap_header, iam_tenant, previous)
        print("   issued →", ns_env, "client", issued["clientId"])
        print("   !! restart the service: docker compose --profile notify up -d notification-service")
    else:
        print("   already exists:", ns_env)
    # The description is the source of permissions in the core: the core derives the principal
    # and the binding with the description's permissions.
    published = cp.call("POST", "/api/v1/agents", NOTIFICATION_AGENT, {**auth, "Idempotency-Key": str(uuid.uuid4())})
    linked = cp.call(
        "PUT",
        f"/api/v1/agents/{NOTIFICATION_AGENT['key']}/identity",
        {"issuer": issuer, "iamTenantId": iam_tenant, "iamPrincipalId": state["notifyIamPrincipalId"]},
        {**auth, "Idempotency-Key": str(uuid.uuid4())},
    )
    state["notifyCpPrincipalId"] = linked.get("principalId") or state.get("notifyCpPrincipalId")
    save()
    print("   revision", published.get("currentRevision"), "principal", state["notifyCpPrincipalId"])

    if state.get("cpLegacyAdminKeyId") and not state.get("cpLegacyAdminKeyRevoked"):
        try:
            cp.call("POST", f"/api/v1/api-keys/{state['cpLegacyAdminKeyId']}:revoke", None, auth)
            state["cpLegacyAdminKeyRevoked"] = True
            save()
            print("   legacy admin api-key revoked")
        except RuntimeError as error:
            print("   legacy admin api-key not revoked:", str(error)[:120])

    if args.agents:
        print("6. agents from", args.agents)
        registry = json.loads(Path(args.agents).read_text())
        agents_state = state.setdefault("agents", {})
        for agent in registry["agents"]:
            agent_slug = agent["slug"]
            entry = agents_state.setdefault(agent_slug, {})
            if "cpPrincipalId" not in entry:
                created = cp.call(
                    "POST",
                    "/api/v1/principals",
                    {
                        "kind": agent.get("cpKind", "agent"),
                        "displayName": agent["displayName"],
                        "metadata": {"slug": agent_slug},
                    },
                    auth,
                )
                entry["cpPrincipalId"] = created["id"]
                save()
            if "iamPrincipalId" not in entry:
                created = iam.call(
                    "POST",
                    f"/api/v1/tenants/{iam_tenant}/principals",
                    {"kind": agent.get("iamKind", "agent"), "displayName": agent["displayName"]},
                    bootstrap_header,
                )
                entry["iamPrincipalId"] = created["id"]
                save()
            permissions = (
                agent.get("permissions") or registry.get("defaultAgentPermissions") or AGENT_DEFAULT_PERMISSIONS
            )
            if "admin" in permissions or "approvals.decide" in permissions:
                raise SystemExit(f"{agent_slug}: an agent must not be granted admin / approvals.decide")
            binding = cp.call(
                "POST",
                f"/api/v1/principals/{entry['cpPrincipalId']}/iam-bindings",
                {
                    "issuer": issuer,
                    "iamTenantId": iam_tenant,
                    "iamPrincipalId": entry["iamPrincipalId"],
                    "permissions": permissions,
                },
                {**auth, "Idempotency-Key": str(uuid.uuid4())},
            )
            entry["bindingId"] = binding.get("id")
            agent_pat = secrets_dir / "agents" / f"{agent_slug}.pat"
            if agent_pat.exists() and args.reissue_agent_pats:
                agent_pat.replace(agent_pat.with_suffix(".pat.bak"))
            if not agent_pat.exists():
                issued = issue_pat(
                    iam,
                    bootstrap_header,
                    tenant=iam_tenant,
                    principal=entry["iamPrincipalId"],
                    name=f"{agent_slug}-{time.strftime('%Y-%m')}",
                    ceiling=["control-plane:read", "control-plane:write"],
                    ttl=args.pat_ttl,
                )
                secure_write(agent_pat, issued["token"])
                entry["patPrefix"] = (issued.get("credential") or {}).get("publicPrefix")
                save()
            print(
                f"   {agent_slug}: cp {entry['cpPrincipalId']} iam {entry['iamPrincipalId']} "
                f"binding {binding.get('status', '?')}"
            )

    save()
    print("done:", state_path.relative_to(ROOT))
    print(
        "credential for the MCP plugin and CLI: ~/.config/iam/credentials.json, key "
        f"{issuer}|{iam_tenant}|{state['iamOperatorPrincipalId']} → contents of {pat_file.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
