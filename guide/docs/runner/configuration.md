# Конфигурация исполнителя

Откуда демон исполнителя `control-plane-agent` берёт настройки и какие переменные
окружения он читает. В поставке демон запускается вручную и настраивается переменными
окружения («режим env»). Если principal демона привязан к агенту реестра ядра (вид
`Agent`), всё, что касается агента, демон берёт из ревизии описания. Статья-справочник
для инженера эксплуатации.

## Два источника настроек

| Что | Откуда | Кто задаёт |
|---|---|---|
| Что это за агент: работа, вид исполнителя, модель, режим разрешений, инструкции, рабочая копия, соседи, ревью, скиллы, срок дренажа | ревизия агента, `GET /api/v1/agents/me`; для principal'а без агента — переменные режима env | автор описания в пакете ([Пакеты каталога](../control-plane/catalog-packages.md#agent)) или тот, кто запускает демон |
| Что принадлежит машине: адрес Control Plane и IAM, credential, каталоги рабочих копий и зеркал, бинарники CLI, проброс MCP, локальные журналы, трасса, изоляция локальных скиллов, сторож прогресса | переменные окружения | тот, кто запускает демон (unit systemd, compose, контейнер) |

!!! tip "Как менять настройки агента"
    Модель, `permissionMode`, соседей, ревью или скиллы меняют правкой описания агента и
    `cp_packages apply`: появится новая ревизия, исполнитель перейдёт на неё после
    текущего прогона. Переменные `CONTROL_PLANE_AGENT_*`, `CONTROL_PLANE_CLAUDE_MODEL` и
    подобные на агента с описанием не действуют.

## Режим конфигурации

При старте демон решает, чей он, по `CONTROL_PLANE_AGENT_CONFIG`:

| Значение | Поведение |
|---|---|
| `auto` (по умолчанию) | `GET /agents/me`: principal привязан к агенту — режим ревизии; `404` — режим env |
| `revision` | агент обязателен; principal без агента — выход с кодом `2` |
| `env` | только окружение, для principal'а без агента |

Режим `auto` — не удобство. Principal агента обязан называть ревизию в каждом
`start-run`; в режиме env он не запустил бы ни одного прогона (`422
agent_revision_required`). Если прочитать `/agents/me` при старте не удалось, демон
завершается с кодом `75` и ждёт перезапуска, а не угадывает режим.

### Коды выхода

| Код | Когда | Что делать надзирателю процесса |
|---|---|---|
| `0` | агент остановлен (`state: stopped`) или выведен из оборота | не перезапускать, пока агент не запущен снова |
| `2` | конфигурация неисполнима: нет `CONTROL_PLANE_SERVER` или credential, неизвестный вид исполнителя, неверные `executor.params`, `review` без `reviewer`, зеркало с чужим `origin` | исправить конфигурацию; перезапуск без исправления бесполезен |
| `75` | появилась новая ревизия агента (после текущего прогона) или не удалось прочитать `/agents/me` при старте | запустить снова сразу |

## Что берётся из ревизии

В режиме ревизии разделы описания заменяют переменные режима env:

| Раздел описания | Заменяет в режиме env |
|---|---|
| `work.workspace`, `work.project`, `work.includeSubprojects` | `CONTROL_PLANE_AGENT_WORKSPACE`, `…_PROJECT`, `…_SUBPROJECTS` |
| `work.onlyAssigned` (по умолчанию `true`) | `CONTROL_PLANE_AGENT_ONLY_ASSIGNED` (по умолчанию выкл.) |
| `work.taskTypes` | — (фильтр по типу задачи есть только в описании) |
| `executor.kind` | `CONTROL_PLANE_AGENT_ADAPTER` |
| `executor.params` (Claude Code) | `CONTROL_PLANE_CLAUDE_MODEL`, `…_PERMISSION_MODE`, `…_TIMEOUT`, `…_RESUME`; `tools.allow`/`tools.deny` — только в описании |
| `executor.params` (Codex) | `CONTROL_PLANE_CODEX_MODEL`, `…_SANDBOX`, `…_TIMEOUT`, `…_RESUME`, `…_CREDENTIAL_CLASS` |
| `executor.instructions` | файл `CONTROL_PLANE_CLAUDE_PROMPT_FILE` |
| `workingCopy.repository`, `neighbours`, `superproject` (URL) | `CONTROL_PLANE_AGENT_REPO`, `…_NEIGHBOURS`, `…_SUPERPROJECT` (пути к зеркалам) |
| `workingCopy.directory`, `baseRef` | `CONTROL_PLANE_AGENT_REPO_DIR`, `…_BASE_REF` |
| `workingCopy.publish` | `CONTROL_PLANE_AGENT_PUSH_REMOTE`, `…_SUPERPROJECT_REMOTE` (в режиме ревизии — `origin` зеркала) |
| `skills.protocols`, `local`, `httpOrigins`, `mcpOrigins`, `audiences`, `concurrency` | `CONTROL_PLANE_SKILLS_PROTOCOLS`, `…_LOCAL_PACKAGES`, `…_HTTP_ALLOWED_ORIGINS`, `…_MCP_ALLOWED_ORIGINS`, `…_ALLOWED_AUDIENCES`, `…_CONCURRENCY` |
| `placement.drainSeconds` | `CONTROL_PLANE_AGENT_DRAIN_SECONDS` |

Чего нет в разделе `skills` описания, того нет и у исполнителя, даже если переменная
`CONTROL_PLANE_SKILLS_*` из этой таблицы задана на хосте.

## Переменные хоста

Эти переменные демон и адаптеры читают в обоих режимах. Значения по умолчанию подходят
большинству установок.

### Подключение и credential

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CONTROL_PLANE_SERVER` | — (обязательна) | базовый URL Control Plane, например `https://platform.example.com` |
| `CONTROL_PLANE_IAM_URL` | — | URL IAM; наличие включает IAM-identity |
| `CONTROL_PLANE_IAM_TENANT` | — | IAM tenant; обязателен вместе с `CONTROL_PLANE_IAM_URL` (`iam_tenant_required`) |
| `CONTROL_PLANE_IAM_AUDIENCE` | `control-plane` | audience обмениваемого access token |
| `CONTROL_PLANE_IAM_SCOPES` | весь потолок PAT ∩ audience | scopes через пробел или запятую |
| `IAM_PRINCIPAL` | — | IAM principal этого процесса; нужен, если в хранилище несколько PAT одного tenant'а |
| `IAM_CREDENTIAL_MODE` | — | `environment` (или `ci`) — разрешает PAT из `IAM_PLATFORM_ACCESS_TOKEN` |
| `IAM_PLATFORM_ACCESS_TOKEN` | — | PAT в окружении; без `IAM_CREDENTIAL_MODE` — `iam_environment_mode_required` |
| `IAM_NO_KEYCHAIN` | — | `1` — не искать PAT в Keychain macOS |
| `XDG_CONFIG_HOME` | `~/.config` | где искать `iam/credentials.json` |
| `CONTROL_PLANE_API_KEY` | — | legacy API-ключ; только если IAM не настроен и сервер ещё принимает такие ключи |
| `HOME` | — | должен быть задан: от него зависят `~/.config`, `~/.gitconfig`, каталоги runtime по умолчанию |

Подробно — [Identity агента](agent-identity.md).

### Демон и рабочие копии

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CONTROL_PLANE_AGENT_CONFIG` | `auto` | режим конфигурации (см. выше) |
| `CONTROL_PLANE_AGENT_POLL` | `5` | пауза между опросами очереди без работы, секунды |
| `CONTROL_PLANE_AGENT_WORKTREE_ROOT` | в режиме ревизии `~/.control-plane-agent/worktrees` | каталог рабочих копий |
| `CONTROL_PLANE_AGENT_MIRRORS` | `<WORKTREE_ROOT>/.mirrors` | где лежат bare-зеркала репозиториев ревизии; недостающее зеркало клонируется |
| `CONTROL_PLANE_AGENT_KEEP_WORKSPACES` | выкл. | `1` — не удалять копию после успеха |
| `CONTROL_PLANE_AGENT_MAX_WORKSPACES` | `8` | сколько простаивающих копий держать на диске |
| `CONTROL_PLANE_AGENT_RUNTIME_DIR` | `<WORKTREE_ROOT>/.runtime`, без пула — `~/.control-plane-agent/runtime` | куда скачиваются входы задач: `<каталог>/<publicId>/inputs/<key>/<имя>` (см. [Входы задачи](adapters.md#task-inputs)) |

За один цикл демон просматривает до 10 доступных задач и берёт первую, которую может
исполнить. Heartbeat сессии и claim — раз в 60 секунд. В режиме ревизии между прогонами
(не чаще раза в 30 секунд в простое) демон перечитывает `/agents/me`.

### Сторож прогона

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CONTROL_PLANE_AGENT_CONTROL_POLL_SECONDS` | `15` | как часто читать прогон ради запроса отмены (не реже раза в 30 с) |
| `CONTROL_PLANE_AGENT_STALL_WARN_SECONDS` | `600` | без новых actions столько секунд — checkpoint `stall`; `0` отключает шаг |
| `CONTROL_PLANE_AGENT_STALL_STOP_SECONDS` | `1800` | после этого исполнитель останавливается, run проваливается `no_progress`, задача возвращается в очередь; `0` отключает |
| `CONTROL_PLANE_AGENT_ACTION_MAX_SECONDS` | `3600` | сколько живёт незавершённое последнее action (долгие тесты, сборка), прежде чем сторож остановит прогон; не меньше `STALL_STOP` |

### Адаптеры: часть хоста

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | — | токен подписки Claude Code (`claude setup-token`); наследуется CLI |
| `ANTHROPIC_API_KEY` | — | альтернатива подписке; наследуется CLI |
| `CONTROL_PLANE_CLAUDE_BINARY` | `claude` | путь к CLI |
| `CONTROL_PLANE_CLAUDE_MCP` | `1` | `0` — не передавать MCP `control-plane` внутрь агента |
| `CONTROL_PLANE_CLAUDE_LOGS` | `1` | `0` — не писать локальный журнал сессии |
| `CONTROL_PLANE_CLAUDE_RUNTIME_DIR` | `~/.claude-runner` | `mcp.json` и `sessions/` |
| `CODEX_HOME` | `~/.codex` | каталог `auth.json` Codex; должен быть записываемым и постоянным |
| `OPENAI_API_KEY` | — | альтернатива входу по подписке; наследуется CLI |
| `CONTROL_PLANE_CODEX_BINARY` | `codex` | путь к CLI |
| `CONTROL_PLANE_CODEX_LOGS` | `1` | `0` — без локального журнала |
| `CONTROL_PLANE_CODEX_RUNTIME_DIR` | `~/.codex-runner` | каталог `sessions/` |

### Контекст и трасса

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CONTROL_PLANE_CONTEXT_BUDGET_CHARS` | `12000` | бюджет раздела «Контекст задачи» в prompt (все адаптеры); некорректное значение — умолчание |
| `CONTROL_PLANE_TRACE_TRANSCRIPT` | `1` | публиковать артефакт `transcript` |
| `CONTROL_PLANE_TRACE_ACTIONS` | `1` | писать run actions `tool.*` |
| `CONTROL_PLANE_TRACE_TOOL_RESULTS` | `1` | хранить результаты инструментов в транскрипте |

Флаги трассы выключаются значениями `0`, `false`, `no`, `off`. Подробно —
[Трасса прогонов](trace.md).

### Скиллы: часть хоста

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CONTROL_PLANE_SKILLS_LOCAL_ISOLATION` | `process` | `process` — дочерний процесс, убиваемый по таймауту и потере аренды; `thread` — поток, который остановить нельзя |
| `CONTROL_PLANE_SKILLS_MCP_SERVERS` | — | JSON `{имя: {command, args, env}}` для эндпоинтов `stdio:<имя>` |
| `CONTROL_PLANE_SKILLS_PRIVATE_HOSTS` | — | хосты разрешённых origins, которым можно резолвиться в непубличные адреса (сервисы внутри кластера) |

Principal'у исполнителя для скиллов нужно право `skills.execute`. Подробнее —
[skill-sdk](../sdk/skill-sdk.md).

## Режим env: конфигурация без описания { #env-mode }

Для principal'а, который не привязан к агенту, всё берётся из окружения. Это штатный
способ запустить демон вручную: unit systemd, сервис compose или контейнер со своими
переменными. На агента с описанием эти переменные не действуют.

### Очередь

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CONTROL_PLANE_AGENT_ADAPTER` | `echo` | `echo`, `claude-code` или `codex` |
| `CONTROL_PLANE_AGENT_ONLY_ASSIGNED` | выкл. | `1` — только задачи, назначенные этому principal'у |
| `CONTROL_PLANE_AGENT_WORKSPACE` | — | Workspace Control Plane, из которого брать задачи (с поддеревом) |
| `CONTROL_PLANE_AGENT_PROJECT` | — | проект |
| `CONTROL_PLANE_AGENT_SUBPROJECTS` | выкл. | `1` — включая подпроекты |
| `CONTROL_PLANE_AGENT_DRAIN_SECONDS` | — | сколько ждать прогон в полёте на `SIGTERM`; без неё прогон доводится до конца |

!!! warning "Без сужения очереди"
    Демон без `CONTROL_PLANE_AGENT_ONLY_ASSIGNED` и без `CONTROL_PLANE_AGENT_WORKSPACE`
    возьмёт любую доступную задачу tenant'а. Для проверок заводите отдельный workspace.

### Рабочие копии

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CONTROL_PLANE_AGENT_REPO` | — | bare-зеркало, из которого нарезаются копии; вместе с `WORKTREE_ROOT` включает пул |
| `CONTROL_PLANE_AGENT_REPO_DIR` | имя репозитория без `.git` | имя каталога копии внутри контейнера задачи |
| `CONTROL_PLANE_AGENT_BASE_REF` | `HEAD` | от чего ветвиться |
| `CONTROL_PLANE_AGENT_PUSH_REMOTE` | — | remote для публикации веток `task/<publicId>` и обновления базы; пусто — работа остаётся локальной |
| `CONTROL_PLANE_AGENT_NEIGHBOURS` | — | соседи: `имя=путь-к-зеркалу` через запятую или пробел |
| `CONTROL_PLANE_AGENT_SUPERPROJECT` | — | зеркало суперпроекта, закрепляющего ревизии соседей; обязателен при соседях |
| `CONTROL_PLANE_AGENT_SUPERPROJECT_REF` | `HEAD` | ref суперпроекта для чтения ревизий |
| `CONTROL_PLANE_AGENT_SUPERPROJECT_REMOTE` | — | remote для обновления суперпроекта перед раскладкой |

Подробно — [Рабочие копии](execution-workspace.md).

### Ревью

Переменных ревью у демона нет: ревью и вливание объявляет тип задачи критериями
приёмки, а исполняет ядро (см. [Приёмка типа](../control-plane/task-types.md#type-acceptance)).
Демон кладёт в артефакт `commit` всё, что нужно критериям, — ветку, коммит, признак
публикации, адрес remote и целевую ветку.

### Адаптеры

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CONTROL_PLANE_CLAUDE_MODEL` | как у CLI | модель |
| `CONTROL_PLANE_CLAUDE_PERMISSION_MODE` | `acceptEdits` | `--permission-mode` |
| `CONTROL_PLANE_CLAUDE_TIMEOUT` | `3600` | потолок хода, секунды |
| `CONTROL_PLANE_CLAUDE_RESUME` | `1` | `0` — не продолжать сессию прошлой попытки |
| `CONTROL_PLANE_CLAUDE_PROMPT_FILE` | — | файл соглашений, дописывается в каждый prompt; перечитывается на каждый ход |
| `CONTROL_PLANE_CODEX_MODEL` | как у CLI | модель |
| `CONTROL_PLANE_CODEX_SANDBOX` | `workspace-write` | `--sandbox` |
| `CONTROL_PLANE_CODEX_TIMEOUT` | `3600` | потолок хода, секунды |
| `CONTROL_PLANE_CODEX_RESUME` | `1` | `0` — не продолжать сессию |
| `CONTROL_PLANE_CODEX_CREDENTIAL_CLASS` | — | метка класса credential в metadata артефакта (`credentialClass`) |

### Скиллы

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CONTROL_PLANE_SKILLS_PROTOCOLS` | `local`, если заданы пакеты; иначе выкл. | протоколы: `local`, `http`, `mcp` |
| `CONTROL_PLANE_SKILLS_LOCAL_PACKAGES` | — | точки входа `module:function` или пакеты с `CONTRACT` и `local`-реализацией |
| `CONTROL_PLANE_SKILLS_HTTP_ALLOWED_ORIGINS` | — | `scheme://host[:port]`, куда можно ходить протоколу `http` |
| `CONTROL_PLANE_SKILLS_MCP_ALLOWED_ORIGINS` | — | то же для удалённых MCP-серверов |
| `CONTROL_PLANE_SKILLS_ALLOWED_AUDIENCES` | — | IAM audiences, токен которых может получить скилл; `control-plane`, `iam` и собственный audience демона запрещены |
| `CONTROL_PLANE_SKILLS_CONCURRENCY` | `1` | одновременных вызовов рядом с кодовой работой; `0` — только когда её нет |

## Харнесс OpenCode

Отдельный процесс `control-plane-opencode` описанием агента не настраивается:

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CONTROL_PLANE_SERVER` | — (обязательна) | URL Control Plane |
| `CONTROL_PLANE_API_KEY` | из хранилища `control-plane login` | API-ключ (IAM-identity харнесс не поддерживает) |
| `OPENCODE_SERVER` | `http://127.0.0.1:4096` | адрес `opencode serve` |
| `OPENCODE_SERVER_PASSWORD` | — | пароль сервера OpenCode |
| `OPENCODE_MODEL`, `OPENCODE_AGENT` | — | модель и агент OpenCode |
| `CONTROL_PLANE_AGENT_WORKSPACE`, `…_PROJECT`, `…_SUBPROJECTS`, `…_POLL` | как у демона | очередь |
| `CP_LOG_LEVEL` | `INFO` | уровень журнала |

## Ошибки конфигурации при старте

| Сообщение | Что поправить |
|---|---|
| `control-plane-agent requires CONTROL_PLANE_SERVER` | задать `CONTROL_PLANE_SERVER` |
| `control-plane-agent has no credentials for <server>` | настроить IAM (`CONTROL_PLANE_IAM_URL`, `CONTROL_PLANE_IAM_TENANT` + PAT) или API-ключ |
| `CONTROL_PLANE_AGENT_CONFIG='…': expected one of auto, revision, env` | значение режима |
| `CONTROL_PLANE_AGENT_CONFIG=revision, but this principal is not an agent` | principal не привязан к агенту: опубликовать описание или убрать `revision` |
| `could not read this principal's agent: …` (выход 75) | Control Plane недоступен при старте; перезапустить процесс |
| `<key>@<N> cannot be run here: …` | ревизия неисполнима на этом образе: вид исполнителя, `executor.params`, `workingCopy`, `review`, `skills` — текст после двоеточия |
| `unknown adapter '<name>' (available: [...])` | `CONTROL_PLANE_AGENT_ADAPTER` (режим env) |
| `adapter '<name>' is not installed on this runner` | поставить пакет с адаптером |
| `skill executor misconfigured: …` | переменные `CONTROL_PLANE_SKILLS_*` (режим env) |
| `neighbours require a superproject that pins their revisions` | соседи без суперпроекта: `workingCopy.superproject` или `CONTROL_PLANE_AGENT_SUPERPROJECT` |

## См. также

- [Адаптеры исполнителей](adapters.md)
- [Переменные окружения (сводный справочник)](../reference/environment.md)
- [Права и scopes](../reference/permissions.md)
