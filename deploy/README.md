# deploy/ — запуск и bootstrap

Всё, что нужно, чтобы поднять Taimen из чистого клона и довести до рабочего
состояния. Секретов в каталоге нет: `.env`, PAT и ключ подписи живут в `secrets/` и
`deploy/state/`, оба в `.gitignore`. Подробное описание — в руководстве `guide/`
(разделы о начале работы и эксплуатации).

```text
deploy/
├── bootstrap.py                 идемпотентный bootstrap: IAM → Control Plane → PAT → сервисы → агенты
├── caddy/Caddyfile.local        внешний контур локального запуска: http, один хост, раскладка по путям
├── keycloak/platform-realm.json шаблон realm для необязательного профиля idp
└── state/<env>.json             состояние bootstrap: идентификаторы, не секреты (в .gitignore)
```

Профили compose, переменные окружения и порты описаны в `compose.yml` и
`.env.example` в корне; здесь они не дублируются.

## Локальный запуск

```bash
make secrets                     # .env (0600) со случайными секретами + secrets/iam-signing.pem
make up PROFILES="core notify edge"
make bootstrap
docker compose --profile notify up -d control-plane-api control-plane-worker context-adapter notification-service
make smoke
```

После первого bootstrap ядро и notification-service перезапускаются один раз, чтобы
подхватить выпущенные для них service accounts (`secrets/control-plane-iam.env`,
`secrets/notification-iam.env`); скрипт напоминает об этом. На Linux ключ подписи
`secrets/iam-signing.pem`, который монтируется в контейнер IAM, должен принадлежать
uid 10001, права 600.

## Что делает bootstrap

`deploy/bootstrap.py --env .env` идемпотентен: сделанное записывается в
`deploy/state/<env>.json` (`<env>` — `COMPOSE_PROJECT_NAME` или `--name`), повторный
запуск пропускает готовые шаги и приводит изменяемое (потолки audiences, права
bindings) к реестру в скрипте. Секреты не печатаются.

1. Ждёт готовности Control Plane и IAM на портах `127.0.0.1`.
2. IAM: tenant, audiences со своими потолками scope (`control-plane`,
   `memory-service`, `notification-service`, `iam`), human principal оператора
   (`--operator`, по умолчанию `Human Operator`).
3. IAM: service account Control Plane для доступа к памяти →
   `secrets/control-plane-iam.env`.
4. Control Plane: `POST /api/v1/bootstrap` — tenant (тот же UUID, что у IAM), admin
   principal оператора и его binding одной транзакцией.
5. PAT оператора с потолком `control-plane:read/write/admin` →
   `secrets/harness-pat` (0600, срок `--pat-ttl`, по умолчанию 180 дней); обмен PAT
   на access token проверяется тут же.
6. Control Plane: project template, project и workspace с именем tenant'а.
7. notification-service: service account IAM → `secrets/notification-iam.env`,
   описание сервиса и его личность в Control Plane (права — чтение событий,
   approvals, задач, principals и workspaces). Шаг выполняется всегда; сервис
   подхватит файл, когда профиль `notify` будет поднят.
8. Отзывает legacy api-key, выданный на шаге 4: инсталляция IAM-only.
9. `--agents agents.json` (необязательно): агенты — см. ниже.

После сброса volumes файл состояния ссылается на несуществующие объекты; скрипт это
заметит и попросит `make reset-state` — цель переносит состояние и выданные
credentials в `secrets/stale-<время>/`.

В конце скрипт напоминает вписать `IAM_TENANT_ID=<uuid>` в `.env` и печатает ключ
credential для CLI и MCP-плагина: `~/.config/iam/credentials.json` (0600), запись
`<issuer>|<tenant>|<principal>` → содержимое `secrets/harness-pat`. Альтернатива без
файла — переменные `IAM_CREDENTIAL_MODE=environment` и `IAM_PLATFORM_ACCESS_TOKEN`
(только вместе).

### Реестр агентов

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

`make bootstrap ARGS="--agents agents.json"` заводит каждому агенту principal в
Control Plane и в IAM, binding с правами (`permissions`, иначе
`defaultAgentPermissions`, иначе встроенный список) и PAT с потолком
`control-plane:read` + `control-plane:write` → `secrets/agents/<slug>.pat`. Агенту
нельзя выдать `admin` и `approvals.decide` — скрипт остановится. Идентификаторы
лежат в state под `agents.<slug>`; `--reissue-agent-pats` перевыпускает PAT
(старый файл → `.pat.bak`).

## Runner автономных исполнителей

Runner — демон `control-plane-agent` из пакета `control-plane`: он забирает
назначенные его principal'у задачи, разворачивает рабочую копию репозитория,
запускает кодовый агент (Claude Code, Codex, OpenCode) и завершает run артефактами.
Ему нужны только HTTP-доступ к Control Plane и IAM, git-зеркало репозитория и сам
кодовый агент.

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

Адаптер `echo` проверяет конвейер без LLM; для настоящей работы —
`CONTROL_PLANE_AGENT_ADAPTER=claude-code` (с `CLAUDE_CODE_OAUTH_TOKEN`) или `codex`.
Держите `CONTROL_PLANE_AGENT_ONLY_ASSIGNED=1` или `CONTROL_PLANE_AGENT_WORKSPACE`:
без них демон возьмёт первую доступную задачу любого workspace. Полный список
переменных и эксплуатация демона — в руководстве `guide/` и в документации
`control-plane`.

## Уведомления в Telegram

Канал Telegram включается файлом `secrets/notification-telegram.env` с переменными
`NS_TELEGRAM_BOT_TOKEN`, `NS_TELEGRAM_WEBHOOK_SECRET` и `NS_TELEGRAM_BOT_USERNAME`;
без файла сервис работает с веб-инбоксом и email. Webhook бота — публичный адрес
`/notify/…` за Caddy.

## Внешний IdP (профиль idp)

Ядру Keycloak не нужен: оператор и агенты работают по Platform Access Token. Профиль
`idp` поднимает Keycloak под `/auth` для инсталляций, где людей аутентифицирует
внешний IdP: его токен обменивается в IAM (`federation:exchange`), полномочия
по-прежнему живут в IAM и Control Plane. Realm импортируется из
`keycloak/platform-realm.json` только при первом старте; клиентов своих приложений
добавляйте через Admin API.

## Промышленная инсталляция

- Задайте `TAIMEN_PUBLIC_URL` (https) и `TAIMEN_PUBLIC_HOST`, положите свой
  Caddyfile с доменом (TLS выпустит Caddy) и укажите его в `CADDYFILE`; раскладку
  путей возьмите из `caddy/Caddyfile.local` без маршрута `/memory/*`.
- `KEYCLOAK_HOSTNAME_STRICT=true`, если поднят профиль `idp`.
- Issuer IAM (`${TAIMEN_PUBLIC_URL}/iam`) попадает в токены и в bindings Control
  Plane: смена публичного адреса означает перенос bindings.
