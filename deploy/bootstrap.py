#!/usr/bin/env python3
"""Идемпотентный bootstrap платформы Taimen (make bootstrap).

Первичная инициализация IAM и Control Plane в один проход:

  1. ждёт готовности Control Plane и IAM по портам на 127.0.0.1;
  2. IAM: tenant, audiences со своими потолками scope, human principal оператора;
  2a. IAM: service account Control Plane (память) → secrets/control-plane-iam.env;
  3. Control Plane: POST /api/v1/bootstrap с `iamBinding` оператора → tenant (тот же
     UUID, что у IAM), admin principal и первый binding IAM↔CP одной транзакцией;
  4. свежий authentication context → Platform Access Token оператора с потолком
     read/write/admin → secrets/harness-pat (0600); обмен PAT проверяется тут же;
  5. Control Plane: project template, project и workspace;
  5a. notification-service: service account IAM, описание сервиса и его личность в
     ядре → secrets/notification-iam.env (сервис подхватит файл при `up -d`);
     legacy api-key из ответа шага 3 отзывается — инсталляция IAM-only;
  6. --agents agents.json (необязательно): principals агентов в Control Plane и IAM,
     bindings и PAT с потолком read/write → secrets/agents/<slug>.pat.

Состояние — deploy/state/<env>.json: идентификаторы не секретны, повторный запуск
пропускает сделанное и приводит изменяемое (потолки audiences, права bindings) к
реестру в скрипте. Секреты не печатаются. Только стандартная библиотека Python.

    python3 deploy/bootstrap.py --env .env
    python3 deploy/bootstrap.py --env .env --agents agents.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Audiences IAM и их потолки scope: один токен — один сервис.
AUDIENCES = {
    # control-plane:decide — решение одного approval из канала уведомлений
    "control-plane": ["control-plane:read", "control-plane:write", "control-plane:admin", "control-plane:decide"],
    # memory:tenants и memory:service — только service account ядра;
    # memory:on-behalf — сервис читает память от имени principal
    "memory-service": [
        "memory:read",
        "memory:write",
        "memory:pii",
        "memory:tenants",
        "memory:on-behalf",
        "memory:service",
    ],
    # send — отправители, read — инбокс человека, admin — обязательные правила и группы каналов
    "notification-service": ["notifications:send", "notifications:read", "notifications:admin"],
    # сам IAM как audience: сервис уведомлений подтверждает привязки каналов
    "iam": ["iam:channel-links"],
}

# Service account Control Plane: context-adapter пишет память всех tenant'ов.
# Секрет живёт только в secrets/control-plane-iam.env (env_file процессов ядра).
CP_SERVICE_ACCOUNT = {
    "displayName": "Taimen Control Plane",
    "audiences": ["memory-service"],
    "scopeCeiling": ["memory:read", "memory:write", "memory:tenants", "memory:on-behalf", "memory:service"],
}

# notification-service — агент без размещения с личностью вида service: описание в ядре
# задаёт его права, IAM-часть — service account. Читает события и каталог адресатов
# ядра, подтверждает привязки каналов в IAM.
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

# Права агента по умолчанию (реестр --agents): без admin и approvals.decide.
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
                raise SystemExit(f"не дождался {self.base}{path}")
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
        print("   прежний service account отозван:", client_id)
    except RuntimeError as error:
        print("   прежний service account не отозван:", str(error)[:120])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env", default=".env")
    parser.add_argument("--name", default=None, help="имя окружения (по умолчанию COMPOSE_PROJECT_NAME)")
    parser.add_argument("--operator", default="Human Operator")
    parser.add_argument("--tenant-slug", default=None)
    parser.add_argument("--agents", default=None, help="реестр агентов (agents.json) — необязательно")
    parser.add_argument("--pat-ttl", type=int, default=180 * 24 * 3600)
    parser.add_argument("--secrets-dir", default="secrets")
    parser.add_argument(
        "--reissue-agent-pats",
        action="store_true",
        help="перевыпустить PAT агентов, даже если файл есть (старый файл → .bak)",
    )
    args = parser.parse_args()

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

    print("1. ожидание сервисов")
    cp.wait("/health/ready")
    iam.wait("/healthz")

    if "iamTenantId" in state:
        # State пережил сброс volumes: id из него уже не существуют, и «уже сделано»
        # было бы ложью.
        try:
            iam.call("GET", f"/api/v1/tenants/{state['iamTenantId']}/audiences", headers=bootstrap_header)
        except RuntimeError as error:
            if "HTTP 404" in str(error):
                raise SystemExit(
                    f"{state_path.relative_to(ROOT)} ссылается на IAM tenant {state['iamTenantId']}, "
                    "которого нет в IAM (volumes сброшены?). Запустите `make reset-state` и повторите bootstrap."
                ) from error
            raise

    print("2. IAM tenant, audiences, principal оператора")
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
        # Потолок сервиса растёт вместе с сервисом: приводим allowedScopes к реестру.
        iam.call("PATCH", f"/api/v1/tenants/{iam_tenant}/audiences/{key}", {"allowedScopes": scopes}, bootstrap_header)
    if "iamOperatorPrincipalId" not in state:
        principal = iam.call(
            "POST",
            f"/api/v1/tenants/{iam_tenant}/principals",
            {"kind": "human", "displayName": args.operator},
            bootstrap_header,
        )
        state["iamOperatorPrincipalId"] = principal["id"]
        save()
    print("   IAM tenant", iam_tenant, "оператор", state["iamOperatorPrincipalId"])
    if env.get("IAM_TENANT_ID", "") != iam_tenant:
        print(f"   !! впишите в {args.env}: IAM_TENANT_ID={iam_tenant} (нужен клиентам и раннерам)")

    print("2a. service account Control Plane в IAM")
    sa_env = secrets_dir / "control-plane-iam.env"
    # PATCH потолка у service account в IAM нет: если потолок в коде вырос, выпускаем
    # новый service account, прежний отзывается.
    ceiling = sorted(CP_SERVICE_ACCOUNT["scopeCeiling"]) + sorted(CP_SERVICE_ACCOUNT["audiences"])
    stale = "cpServiceAccountClientId" in state and state.get("cpServiceAccountCeiling") != ceiling
    if stale:
        print("   потолок service account изменился — перевыпуск")
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
        print("   выпущен →", sa_env, "client", issued["clientId"])
        print(
            "   !! перезапустите ядро, чтобы оно взяло env-файл: "
            "docker compose up -d control-plane-api control-plane-worker context-adapter"
        )
    else:
        print("   уже есть:", sa_env, "client", state["cpServiceAccountClientId"])

    print("3. Control Plane bootstrap с binding оператора")
    if "cpTenantId" not in state:
        # Единый tenant платформы: Control Plane получает UUID tenant'а IAM.
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
            "оператор",
            state["cpOperatorPrincipalId"],
            "binding",
            state["cpOperatorBindingId"],
        )
    else:
        print("   уже сделано:", state["cpTenantId"])

    print("4. PAT оператора")
    pat_file = secrets_dir / "harness-pat"
    if not pat_file.exists():
        # Человеку IAM выпускает PAT только со свежим authentication context (≤ 300 с).
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
            name=f"operator-{time.strftime('%Y-%m')}",
            ceiling=OPERATOR_CEILING,
            ttl=args.pat_ttl,
        )
        secure_write(pat_file, issued["token"] + "\n")
        credential = issued.get("credential") or {}
        state["operatorPatPrefix"] = credential.get("publicPrefix")
        state["operatorPatExpiresAt"] = credential.get("expiresAt")
        save()
        print("   выпущен →", pat_file, "prefix", state.get("operatorPatPrefix"))
    else:
        print("   уже есть:", pat_file)
    pat = pat_file.read_text().strip()
    exchange = iam.call(
        "POST",
        "/api/v1/platform-access-tokens:exchange",
        {"token": pat, "audience": "control-plane", "scopes": OPERATOR_CEILING},
    )
    auth = {"Authorization": f"Bearer {exchange['accessToken']}"}
    print("   обмен PAT → access token: ok")

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

    print("5a. notification-service: service account IAM, личность в ядре, env-файл")
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
        print("   потолок или audiences изменились — перевыпуск")
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
        print("   выпущен →", ns_env, "client", issued["clientId"])
        print("   !! перезапустите сервис: docker compose --profile notify up -d notification-service")
    else:
        print("   уже есть:", ns_env)
    # Описание — источник прав в ядре: principal и binding с правами описания выводит ядро.
    published = cp.call("POST", "/api/v1/agents", NOTIFICATION_AGENT, {**auth, "Idempotency-Key": str(uuid.uuid4())})
    linked = cp.call(
        "PUT",
        f"/api/v1/agents/{NOTIFICATION_AGENT['key']}/identity",
        {"issuer": issuer, "iamTenantId": iam_tenant, "iamPrincipalId": state["notifyIamPrincipalId"]},
        {**auth, "Idempotency-Key": str(uuid.uuid4())},
    )
    state["notifyCpPrincipalId"] = linked.get("principalId") or state.get("notifyCpPrincipalId")
    save()
    print("   ревизия", published.get("currentRevision"), "principal", state["notifyCpPrincipalId"])

    if state.get("cpLegacyAdminKeyId") and not state.get("cpLegacyAdminKeyRevoked"):
        try:
            cp.call("POST", f"/api/v1/api-keys/{state['cpLegacyAdminKeyId']}:revoke", None, auth)
            state["cpLegacyAdminKeyRevoked"] = True
            save()
            print("   legacy admin api-key отозван")
        except RuntimeError as error:
            print("   legacy admin api-key не отозван:", str(error)[:120])

    if args.agents:
        print("6. агенты из", args.agents)
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
                raise SystemExit(f"{agent_slug}: агенту нельзя выдавать admin / approvals.decide")
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
    print("готово:", state_path.relative_to(ROOT))
    print(
        "credential для MCP-плагина и CLI: ~/.config/iam/credentials.json, ключ "
        f"{issuer}|{iam_tenant}|{state['iamOperatorPrincipalId']} → содержимое {pat_file.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
