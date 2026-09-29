# Пакеты каталога

Каталог Control Plane — это типы задач, типы артефактов, шаблоны проектов,
типы workspace, роли, capabilities, скиллы, правила вывода работы и описания
агентов; рядом с ними в пакете живут правила уведомлений сервиса уведомлений. Он
хранится в git как **пакеты**: YAML-файлы в
каталоге `packages/` суперпроекта. Инструмент `tools/cp_packages.py` проверяет
пакеты без стенда, сверяет их с живым Control Plane и применяет. Статья для
администраторов инсталляции и авторов вертикальных пакетов. Обоснование
решения — TAI-ADR-0044.

## Зачем пакеты

- **Источник истины — git.** Control Plane хранит опубликованные версии
  объектов, а пакет говорит, какими они должны быть. Правка через API в обход
  пакета видна: `plan` покажет расхождение, а `apply` опубликует версию из git
  поверх неё.
- **Воспроизводимость.** Новая инсталляция получает каталог на шаге bootstrap,
  без ручных вызовов API.
- **Одинаково для человека и машины.** Файлы пишут руками, выгружают из
  стенда командой `export` или генерируют из кода (скиллы, через skill-sdk).
- **Пакет — это данные.** Формат и установщик относятся к ядру, содержимое
  пакетов — к домену.

## Структура каталога `packages/`

```text
packages/
├── README.md
├── schema/
│   └── v1/object.schema.json      # JSON Schema 2020-12 формата
└── example/                       # условный пакет (requires: [])
    ├── package.yaml               # манифест: kind: Package
    ├── agents/                    # kind: Agent
    ├── artifact-types/            # kind: ArtifactType
    ├── task-types/                # kind: TaskType
    ├── rules/                     # kind: WorkRule
    ├── notification-rules/        # kind: NotificationRule — к сервису уведомлений
    └── skills/                    # kind: Skill
```

В поставку входят формат, схема `packages/schema` и установщик
`tools/cp_packages.py`; доменных пакетов в ней нет. Примеры ниже используют
условный пакет `example`.

Файлы установки (какие пакеты ставить в конкретное окружение) лежат в
`deploy/`:

| Файл | Назначение |
|---|---|
| `deploy/packages.yaml` | установка по умолчанию, её использует `make bootstrap` |
| `deploy/<окружение>/packages.yaml` | своя установка окружения со своим списком `retire` |

## Формат объекта

Каждый файл — один объект в общей обёртке:

```yaml
# yaml-language-server: $schema=../../schema/v1/object.schema.json
apiVersion: taimen.ai/v1
kind: TaskType
key: document-review
spec:
  displayName: Document review
  description: Проверка документа юристом.
  fieldSchema: { ... }
  lifecycleSchema: { ... }
  approvalSchema: { ... }
  acceptance: [ ... ]
```

| Поле | Правило |
|---|---|
| `apiVersion` | константа формата `taimen.ai/v1` (идентификатор схемы, а не адрес сервиса) |
| `kind` | `Package`, `Installation`, `ArtifactType`, `TaskType`, `ProjectTemplate`, `WorkspaceType`, `Role`, `Capability`, `Skill`, `WorkRule`, `Agent`, `NotificationRule` |
| `key` | идентичность внутри tenant'а, 1–200 символов; у `Package`, `ArtifactType`, `TaskType` и `ProjectTemplate` — `^[a-z0-9][a-z0-9_-]*$`, не длиннее 63; у `Role` и `Agent` — slug `^[a-z0-9][a-z0-9-]*$`, 2–63 символа; у `WorkRule` и `NotificationRule` — `^[a-z0-9][a-z0-9._-]*$`, до 128 символов |
| `spec` | **ровно тело запроса API** в camelCase, без поля идентичности: Control Plane, а для `NotificationRule` — сервиса уведомлений. Имена полей совпадают с OpenAPI сервиса |

Строка `# yaml-language-server: $schema=…` включает проверку и подсказки по
схеме в редакторе. Папки по видам (`task-types/`, `skills/`, …) — только
соглашение для людей. Вид объекта определяется полем `kind`, а не путём.

### Отображение на API

| kind | Папка | Поле идентичности в API | Как применяется |
|---|---|---|---|
| `Package` | `package.yaml` | каталог пакета | `spec.version` (SemVer), `displayName`, `description`, `requires` |
| `ArtifactType` | `artifact-types/` | `key` | тип артефакта (см. [ниже](#artifact-type)): версии неизменяемы и из оборота не выводятся; новая версия публикуется, только если файл отличается от новейшей версии |
| `TaskType` | `task-types/` | `key` | версии неизменяемы: при расхождении с новейшей активной версией публикуется новая, остальные активные версии ключа переводятся в `deprecated`. Секция `acceptance` — критерии приёмки по умолчанию у всех задач типа (см. [Приёмка типа](task-types.md#type-acceptance)) и участвует в сравнении |
| `ProjectTemplate` | `project-templates/` | `key` | так же, как `TaskType` |
| `WorkspaceType` | `workspace-types/` | `key` | создать или `PATCH` (с `If-Match`) при расхождении; архивный тип пакет не восстановит — это ошибка |
| `Role` | `roles/` | `slug` | роли уровня tenant'а; создать или `PATCH` |
| `Capability` | `capabilities/` | `name` | только создание; расхождение описания — предупреждение (API описание не меняет) |
| `Skill` | `skills/` | `name` + `spec.version` | создать версию; расхождение в `protocol`, `sideEffects`, `riskLevel` или `contract` — ошибка «поднимите `spec.version`»; расхождение в `description`, `config`, `inputSchema`, `outputSchema` — `PATCH`, но ядро меняет у опубликованной версии только `description` (и статус), остальное отклоняет `409 skill_version_immutable` |
| `Agent` | `agents/` | `key` | агент (см. [ниже](#agent)): сначала `POST /agents:validate`; если не меняются ни ревизия, ни желаемое состояние — «без изменений», иначе `POST /agents`. Новая неизменяемая ревизия появляется, только если отличается хэш описания; `state` и `placement.replicas` меняют желаемое состояние без ревизии |
| `WorkRule` | `rules/` | `key` | правило вывода работы (см. [Правила вывода работы](work-rules.md)): создать или `PATCH` (с `If-Match`) изменённых `description`, `trigger`, `condition`, `interpretation`, `action`, `identity`; `status` (`enabled`/`disabled`, по умолчанию `enabled`) — через `:enable`/`:disable`. `workspaceId` задаётся только переменной установки (`${NAME}`) и после создания не меняется. С `identity: {agent: <key>}` правило действует полномочиями этого агента; без него — полномочиями того, чьим токеном применён пакет. Снятие `identity` из файла — `PATCH identity: null` |
| `NotificationRule` | `notification-rules/` | `key` | правило уведомления (см. [ниже](#notification-rule)): применяется **к сервису уведомлений**, а не к ядру; версию считает сервис по хэшу спецификации |
| `Calendar` | `calendars/` | `key` | производственный календарь: выходные, праздники и переносы по годам; применяется только планом ядра (см. [Процессы](#processes)) |
| `Process` | `processes/` | `key` + `spec.version` | процесс: стадии, шаги, таблицы решений, таймеры, данные по JSON Schema; применяется только планом ядра (см. [Процессы](#processes)) |

Удаления нет ни для одного вида. Порядок применения задан зависимостями:
`WorkspaceType` → `Capability` → `Role` → `Skill` → `ArtifactType` →
`TaskType` → `Agent` → `ProjectTemplate` → `Calendar` → `Process` → `WorkRule` →
`NotificationRule`. На
что ссылаются, то создаётся раньше: `artifactSchema` типа задачи ссылается на
типы артефактов, поэтому они публикуются до типов задач; агент ссылается на роли
и типы задач, поэтому идёт после них; правило с `identity` ссылается на агента.
Правила уведомлений ни на что в ядре не ссылаются, но исполняются сразу после
применения, поэтому идут последними — когда ядро уже приведено.

### Агент (`Agent`) { #agent }

Файл в папке `agents/` описывает агента целиком: личность и права, какую работу
он берёт, вид исполнителя с параметрами и инструкциями, рабочую копию,
скиллы и размещение на узлах (TAI-ADR-0052). Схема — `$defs.agentSpec` в
`packages/schema/v1/object.schema.json`.

```yaml
# yaml-language-server: $schema=../../schema/v1/object.schema.json
apiVersion: taimen.ai/v1
kind: Agent
key: reviewer
spec:
  displayName: Code reviewer
  identity:
    kind: agent
    permissions: [sessions.open, tasks.read, tasks.write, tasks.claim, artifacts.read, artifacts.write]
  work:
    workspace: ${AGENTS_WORKSPACE_ID}
    taskTypes: [code-review]
  executor:
    kind: claude-code
    params: {model: <model-id>, permissionMode: acceptEdits}
  workingCopy:
    repository: https://git.example.com/org/service.git
    publish: false
  placement:
    requires: [repos]
    secrets: [claude-oauth-token]
```

Особенности вида:

- `check` проверяет описание схемой формата и моделью `AgentSpec` ядра,
  требует, чтобы `work.taskTypes` были объявлены в пакете или его
  `requires`, и предупреждает о ролях из `identity.roles`, которых нет в
  пакетах (они должны уже быть в tenant'е);
- топология — `work.workspace`, `work.project` — пишется переменной установки
  `${NAME}` или UUID;
- раздел `workingCopy.review` устарел: ревью объявляет тип задачи критериями
  приёмки (см. [Приёмка типа](task-types.md#type-acceptance));
- в описание не пишутся значения секретов — только имена в
  `placement.secrets`;
- `apply` применяет и желаемое состояние из файла (`state`,
  `placement.replicas`): агента, остановленного вручную, следующее
  применение запустит снова, если в файле `state: running`;
- `retire.Agent` в файле установки выводит агента из оборота: исполнитель
  останавливается, credential отзывается, история прогонов остаётся;
- `export` выгружает `spec` текущей (или указанной `--version`) ревизии, а
  `state` и `replicas` — из желаемого состояния, опуская умолчания.

Размещение исполнителей по описанию `placement` на машинах в поставку не
входит: исполнителя, описанного агентом, можно запустить вручную демоном
`control-plane-agent` (см. [Runner](../runner/index.md)).

### Правило уведомления (`NotificationRule`) { #notification-rule }

Файл в папке `notification-rules/` описывает, какое событие Control Plane
становится уведомлением: событие и условие → адресат → тип, заголовок, текст,
ссылки, кнопки решения → закрытие кнопок по событию исхода. Схема —
`$defs.notificationRuleSpec` в `packages/schema/v1/object.schema.json`, полное
описание — в статье [Правила уведомлений](../notifications/notification-rules.md).

```yaml
# yaml-language-server: $schema=../../schema/v1/object.schema.json
apiVersion: taimen.ai/v1
kind: NotificationRule
key: task-verified
spec:
  "on": {type: task.verified}
  recipient: {kind: taskOwner, fallback: taskAssignee}
  notification:
    type: task.verified
    title: "Принято: {{task.publicId}} {{task.title}}"
    links:
      - {label: Открыть задачу, url: "${TASK_URL_BASE}/{{task.publicId}}"}
```

Особенности вида:

- применяется **к сервису уведомлений**: адрес — переменная установки
  `NOTIFICATION_SERVICE_URL`, токен — `NOTIFY_TOKEN` (access token audience
  `notification-service`, scope `notifications:admin`) или обмен того же IAM
  credential, что у установщика, на этот audience;
- до первой записи — и в ядро, и в сервис — установщик вызывает `:validate` для
  всех правил установки: правило, которое сервис не примет, останавливает
  установку целиком; дальше `POST` только изменившихся правил;
- без `NOTIFICATION_SERVICE_URL` `apply` пропускает правила уведомлений с
  предупреждением (например, при bootstrap до шага сервиса уведомлений);
- ключ `on` пишется в кавычках (`"on":`) — иначе YAML 1.1 прочтёт его как `true`;
- `retire.NotificationRule` выводит правило из оборота (`:retire`), отправленные
  уведомления остаются;
- `export --kind NotificationRule` выгружает действующую версию из сервиса;
  `--server` не нужен, `--version` не поддерживается.

### Тип артефакта (`ArtifactType`) { #artifact-type }

Файл в папке `artifact-types/` объявляет тип артефакта — ключ, схему
`metadata`, допустимые media types и потолок размера содержимого (модель — в
[Артефактах](artifacts.md#artifact-types)):

```yaml
# yaml-language-server: $schema=../../schema/v1/object.schema.json
apiVersion: taimen.ai/v1
kind: ArtifactType
key: review-report
spec:
  displayName: Заключение проверки
  description: Заключение, которое сдаёт проверка и получает следующий шаг
  mediaTypes: [application/pdf]
  maxBytes: 10485760            # необязательно
  metadataSchema:
    type: object
    properties:
      reviewer: {type: string}
```

| Поле `spec` | Умолчание в пакете | Как сравнивается с живой версией |
|---|---|---|
| `displayName`, `description` | `""` | всегда |
| `metadataSchema` | `{}` | всегда |
| `mediaTypes` | `["*/*"]` | всегда; перед сравнением приводятся к нижнему регистру, параметры и повторы отбрасываются — так их хранит ядро |
| `maxBytes` | не задан — ядро берёт `CP_ARTIFACT_MAX_BYTES` инсталляции на момент публикации | только если задан в файле |

Правила применения:

- версии неизменяемы, у API нет депрецирования типов артефактов, поэтому
  `apply` **не переводит** старые версии в `deprecated`, а `retire` для
  `ArtifactType` не поддерживается;
- новая версия публикуется, только если хоть одно сравниваемое поле файла
  отличается от новейшей версии ключа; иначе — «без изменений»;
- артефакты всегда проверяются по новейшей версии, поэтому сужение
  `mediaTypes` или `maxBytes` в новой версии сразу касается новых
  артефактов этого вида.

`artifactSchema` типа задачи (см. [Входы и выходы](task-types.md#artifact-schema))
ссылается на типы артефактов по ключу. Как и прочие ссылки, она замкнута:
тип артефакта должен быть объявлен в том же пакете или в пакете из
`requires`.

### Манифест пакета

```yaml
# yaml-language-server: $schema=../schema/v1/object.schema.json
apiVersion: taimen.ai/v1
kind: Package
key: example
spec:
  version: 0.1.0                 # SemVer, обязательно
  displayName: Example           # обязательно
  description: Типы задач и скиллы условного домена.
  requires: []                   # пакеты, на объекты которых здесь ссылаются
```

Ключ пакета обязан совпадать с именем его каталога. Циклы в `requires`
запрещены.

### Файл установки

```yaml
# yaml-language-server: $schema=../../packages/schema/v1/object.schema.json
apiVersion: taimen.ai/v1
kind: Installation
key: production
spec:
  packages: [example]             # requires подтягиваются сами
  retire:
    TaskType: [ops, analysis]     # все активные версии → deprecated
```

- `retire` описывает историю **окружения**, а не пакета. Поддерживаются
  `TaskType`, `ProjectTemplate` (активные версии → `deprecated`), `WorkRule`
  (правило архивируется, заведённая им работа остаётся), `Agent`
  (`:retire` — исполнитель остановлен, credential отозван, ключ больше не
  используется) и `NotificationRule` (`:retire` в сервисе уведомлений,
  отправленные уведомления остаются). `ArtifactType` из оборота не выводится.
- Тип задачи, убранный из пакета, сам из оборота не выходит: добавьте его в
  `retire.TaskType`, когда закрыты открытые задачи этого типа. Так выводится,
  например, прежний тип задачи ревью после перехода на приёмку типа.
- Системный тип задачи `task` вывести из оборота нельзя: ядро всегда держит
  его активную версию.
- Ключ не может одновременно быть объявлен в пакете и выводиться из оборота.

## Правила содержимого

**Ссылки — только по ключам, никогда по UUID.** Примеры:

- `execution: {skill: git.merge, version: "1"}` в типе задачи;
- `ensureWork.type: coding-task` в исходе approval;
- `invokeSkill.skill: git.merge@1` в исходе approval;
- `allowedChildTypes: [team]` в типе workspace;
- `artifactSchema.inputs[].type: spec-document` в типе задачи;
- `identity: {agent: example-rules}` в правиле вывода работы;
- `agent:<key>` в полях назначения: `ensureWork.assignee` исхода approval,
  `fields.assignee` правила.

Пакет замкнут: ссылка должна вести в сам пакет или в пакет из `requires`.
Единственное исключение — системный тип `task`. Для агентов (`identity.agent`
правила и литеральный `agent:<key>`) `check` дополнительно отвергает ссылку на
агента, которого та же установка выводит из оборота (`retire.Agent`). Ссылка
через шаблон (`{{…}}`, `$.…`) проверяется ядром при исполнении. Для `allowedChildTypes`
незамкнутая ссылка даёт предупреждение: такой тип должен уже существовать в
tenant'е.

**Параметры окружения — `${NAME}`** в строковых значениях `spec`, например
адрес HTTP-скилла:

```yaml
contract:
  implementation:
    protocol: http
    endpoint: ${EXAMPLE_SKILLS_URL}/merge
```

При `plan` и `apply` значение берётся из `.env` инсталляции (флаг `--env`, по
умолчанию `.env` в корне) и переменных процесса. Незаданная переменная — ошибка
установки. При `check` вместо незаданной переменной подставляется заглушка.

**Секретов в пакете нет.** Ядро само отвергает секретный материал в контрактах
и схемах (`secret_material_rejected`).

**Скиллы генерируются из кода.** YAML скилла не пишут руками: его генерирует
skill-sdk из декораторов в коде интеграции
(`skill-sdk export --package packages/<пакет> <модуль>`). Источник истины
контракта скилла — код, а расхождение ловит тест интеграции. Подробнее — в
[skill-sdk](../sdk/skill-sdk.md).

## Инструмент `tools/cp_packages.py`

```text
python3 tools/cp_packages.py check  [--install <файл> | --package <пакет>] [--server <url>] [--json]
python3 tools/cp_packages.py test   (--install <файл> | --package <пакет>) --server <url> [--test <имя>] [--json]
python3 tools/cp_packages.py plan   --install <файл> --server <url> [--env <.env>] [--out <plan.json>]
python3 tools/cp_packages.py apply  --install <файл> --server <url> [--env <.env>]
python3 tools/cp_packages.py apply  --plan <plan.json>
python3 tools/cp_packages.py migrate-expr --package <пакет> [--write]
python3 tools/cp_packages.py export --server <url> --kind <kind> --key <key> [--key ...] \
                                    [--version <v>] --package packages/<пакет>
```

| Команда | Нужен стенд | Что делает |
|---|---|---|
| `check` | нет (с `--server` — да) | проверяет все пакеты (без `--install`) или состав установки: схему формата, дубли, замкнутость ссылок, `retire`, тесты процессов, а также доменные валидаторы Control Plane; с `--server` — ещё и проверку процессов ядром |
| `test` | да | прогоняет тесты процессов пакета в песочнице ядра и печатает результат и покрытие |
| `plan` | да | сверяет установку с живым Control Plane и печатает, что изменится; ничего не пишет. С `--out` — план ядра с хэшем для `apply --plan` |
| `apply` | да | устанавливает: сначала `check`, при ошибках останавливается, затем применяет объекты по видам и `retire`; `Process` и `Calendar` пропускает — их применяет `apply --plan` |
| `migrate-expr` | нет | переводит прежние синтаксисы выражений пакета в CEL и печатает diff; `--write` записывает |
| `export` | да | выгружает объекты из живого Control Plane (для `NotificationRule` — из сервиса уведомлений) в файлы пакета (`<package>/<папка вида>/<key>.yaml`) |

Доменные валидаторы — те же функции, что ядро вызывает при создании объекта:
разбор жизненного цикла типа задачи, `approvalSchema`, `execution`,
`artifactSchema`, определения типа артефакта, контракта скилла, JSON Schema
полей, конфигурации и governance шаблонов проекта.

Для типов артефактов и `artifactSchema` `check` дополнительно проверяет:

- определение `ArtifactType` — схему `metadataSchema`, грамматику
  `mediaTypes`, положительный `maxBytes`. Потолок `CP_ARTIFACT_MAX_BYTES`
  знает только инсталляция, поэтому превышение его ловит уже ядро при
  `apply` (`422 invalid_artifact_type`);
- грамматику `artifactSchema` (поля слотов, `from`, `content`, ключи);
- что каждый `type` входа и выхода объявлен как `ArtifactType` в пакете или
  его `requires`;
- что `mediaTypes` выхода сужает `mediaTypes` своего типа артефакта. Их
берут из сабмодуля `control-plane`. Если он не импортируется (нет сабмодуля или
`jsonschema`), `check` выдаёт предупреждение и проверяет только схему
формата. Для работы нужны `PyYAML` и `jsonschema`.

### Credential для `plan`, `apply`, `export`

Инструмент ходит в API с `Authorization: Bearer <token>`. Токен берётся:

1. из переменной `CP_TOKEN` — access token IAM audience `control-plane`;
2. если её нет — из credential `control_plane_client`, то есть из той же
   IAM-identity, что у CLI и MCP-сервера (см. [CLI и
   MCP-сервер](cli-and-mcp.md#credentials)). Для этого скрипт нужно запускать
   интерпретатором окружения, где установлен пакет `control-plane`.

Токену нужны права на запись каталога: `task_types.manage`,
`artifact_types.manage`,
`project_templates.manage`, `workspaces.manage`, `org.manage` (роли,
capabilities, скиллы), `agents.manage` (агенты), `rules.write` (правила), а
также соответствующие права чтения. Права, которые описание агента выдаёт
агенту, должны быть у самого токена: иначе `403 permission_escalation`. То же
для правил с `identity`: применяющий должен иметь все права агента-личности.

Для `NotificationRule` нужен второй токен — audience `notification-service`,
scope `notifications:admin`: переменная `NOTIFY_TOKEN` или обмен того же IAM
credential (PAT должен допускать этот audience в потолке, иначе IAM ответит
`iam_audience_not_allowed`).

## Проверка в CI: `make packages-check`

```bash
make packages-check
```

Цель выполняет две проверки:

```bash
python3 tools/cp_packages.py check
python3 tools/cp_packages.py check --install deploy/packages.yaml
```

Вывод:

```text
ok: пакетов 2, объектов 5, тестов 0
```

или список строк `ошибка: <файл>: <сообщение>` с кодом выхода `1`.

## Процессы и календари { #processes }

Процесс (`kind: Process`) и производственный календарь (`kind: Calendar`)
исполняет и проверяет само ядро Control Plane (обоснование — TAI-ADR-0054,
CP-ADR-0074). Язык процессов описан в разделе [Процессы](../processes/index.md),
тесты и план — в [Тестах пакета](../processes/package-tests.md). Локальной копии движка нет: без ядра `check` проверяет только
форму по схеме, ссылки и тесты пакета.

!!! warning "Нужен Control Plane с движком процессов"
    Команды `test`, `plan --out` и `apply --plan`, а также `check --server`
    обращаются к маршрутам `POST /api/v1/packages:test`, `/packages:plan` и
    `/packages:apply`. Если ядро их не знает (`404`) или ещё не реализует
    (`501 not_implemented`), `check --server` сообщает «ядро не поддерживает
    проверку процессов … — проверена только схема» и завершается по
    статической проверке, а остальные команды — ошибкой.

### Раскладка пакета с процессом

```text
packages/<пакет>/
├── package.yaml               # renames — явные переименования объектов
├── processes/<ключ>.yaml      # kind: Process
├── calendars/<ключ>.yaml      # kind: Calendar
├── schemas/<имя>.schema.json  # схемы данных: data: {$ref: ../schemas/<имя>.schema.json}
├── tests/<имя>.test.yaml      # тесты процессов (schema/v1/test.schema.json)
└── .layout/<ключ>.json        # раскладка схемы для визуального редактора
```

`data: {$ref: …}` ссылается только на файл внутри пакета. Раскладка ядру не
отправляется и логики не несёт.

### Проверка, тесты, план, применение

```bash
python3 tools/cp_packages.py check --package packages/<пакет> --server https://platform.example.com --json
python3 tools/cp_packages.py test  --package packages/<пакет> --server https://platform.example.com
python3 tools/cp_packages.py plan  --install deploy/<окружение>/packages.yaml \
    --server https://platform.example.com --out plan.json
python3 tools/cp_packages.py apply --plan plan.json
```

Каждый запрос — один пакет своими файлами: `{package: {files: [{path,
content}]}}`, вместе с `tests/` и без `.layout/`, с подставленными
переменными установки. Пакеты из `requires` ядро берёт из своего каталога,
переименования — из `renames` в `package.yaml`.

- **`check --server`** проверяет названные пакеты запросом
  `POST /packages:test?checkOnly=true`. Находки ядра печатаются как
  `файл:строка: код: сообщение [путь] (подсказка: …)`; с `--json` — список
  объектов `{code, severity, path, file, line, message, hint}`.
- **`test`** печатает по каждому тесту `ok`/`FAIL`, шаг и причину падения, а
  затем покрытие процесса: элементы, переходы, строки таблиц решений,
  обработчики ошибок — и что не пройдено. Код выхода `1`, если есть
  упавшие тесты.
- **`plan --out`** показывает структурный diff (`+` добавится, `~` изменится,
  `-` выводится, `→` переименование), владельца поля (правленное в консоли не
  перезаписывается), расхождения поведения по replay и судьбу открытых
  экземпляров (`pin` — дорабатывают на своей версии, `migrate` — переходят по
  карте), покрытие разделов регламентов. План строится по каждому пакету
  установки (`--replay-limit` — сколько экземпляров прогнать replay, по
  умолчанию 50) и сохраняется в файл вместе с хэшами; план с ошибками
  (например `migration_required`) не сохраняется. `retire` файла установки в
  план ядра не входит — его выполняет обычный `apply --install`.
- **`apply --plan`** отправляет по каждому пакету те же файлы, по которым
  строился план, и его `planHash`. Если каталог стенда успел измениться, ядро отвечает
  `plan_stale` — план строится заново. Файл плана, изменённый после
  построения, не применяется; план, построенный для другого адреса, тоже.

### Правка файлов: `tools/pkg.py` { #pkg }

`tools/pkg.py` выполняет мелкие правки процесса и пакета и меняет только
затронутые строки: комментарии, порядок ключей, кавычки и flow/block-стиль
остального файла остаются как были. Нужен пакет `ruamel.yaml`.

| Операция | Что делает |
|---|---|
| `add-step --in <стадия или шаг> --step <yaml> [--after/--before <id>]` | добавляет шаг в стадию или в блок `do` шага, ветви, таймера |
| `add-stage --stage <yaml> [--after/--before <id>]` | добавляет стадию |
| `add-decision-row --table <id> --row <yaml> [--index N]` | добавляет строку таблицы решений; столбцы проверяются по входам и выходам таблицы |
| `add-rule --table <id> --row <yaml>` или `add-rule --on-event <yaml>` | правило: строка таблицы решений или реакция процесса на событие (`onEvent`) |
| `add-form-field --step <id> --name <поле> --schema <yaml> [--required] [--label]` | поле формы человеческого шага (и элемент `uischema`, если он есть) |
| `rename --file <процесс> --from <id> --to <id> [--no-migration]` | переименовывает элемент процесса, ссылки на него и тесты пакета; дописывает карту `migrations` и переносит координаты раскладки |
| `rename --package <каталог> --kind Process --from <ключ> --to <ключ>` | переименовывает объект пакета и файл, дописывает `renames` в `package.yaml` |
| `set --path <путь> --value <yaml>` | записывает значение; в пути `[N]` — индекс, `[id]` — элемент списка по id |

Флаг `--json` печатает результат или ошибку машиночитаемо
(`{"ok": false, "error": {"code", "message", "path", "hint"}}`), `--dry-run` —
diff без записи. Правка, которую не пропускает схема каталога или которая
повторяет id элемента, не записывается.

Загрузка и запись файла без изменений дают тот же файл байт в байт: стиль
файла (отступы, смещение `-`, ширина строки, запись `null`) подбирается при
загрузке. Переносы строк внутри flow-коллекции (`{a: 1,` и `b: 2}` на разных
строках) ruamel.yaml не хранит — такую правку `pkg.py` переносит на исходный
текст слиянием, и остальные строки файла не меняются.

Язык пакетов — YAML 1.2: булевы значения только `true`/`false`, ключи `on`,
`off`, `yes`, `no` — строки.

## Как применяется каталог

### При bootstrap

`deploy/bootstrap.py` применяет пакеты на шаге **5b** через
`cp_packages.apply()`. По умолчанию используется файл
`deploy/packages.yaml`, другой файл передаётся флагом:

```bash
python3 deploy/bootstrap.py --env .env --packages deploy/production/packages.yaml ...
```

Идентификаторы опубликованных объектов сохраняются в state bootstrap
(`deploy/state/<имя>.json`). В самих пакетах UUID не живут. Подробности —
в статье [Bootstrap](../getting-started/bootstrap.md).

### Вручную на работающей инсталляции

```bash
# 1. Проверить без стенда
make packages-check

# 2. Посмотреть план
export CP_TOKEN=<access-token audience control-plane>
python3 tools/cp_packages.py plan \
  --install deploy/production/packages.yaml \
  --server https://platform.example.com

# 3. Применить
python3 tools/cp_packages.py apply \
  --install deploy/production/packages.yaml \
  --server https://platform.example.com
```

Пример вывода `plan`:

```text
   пакеты: example 0.2.0
   TaskType/coding-task: (план) новая версия (изменились acceptance)
   TaskType/coding-task: (план) v5 → deprecated
   Skill/git.bump_submodule@1: (план) будет зарегистрирован
   WorkRule/submodule-lag: (план) изменятся identity
   NotificationRule/approval-requested: (план) v1 без изменений
   TaskType/ops: v1 → deprecated (retire)
```

!!! note "Задачи на старых версиях не меняются"
    Новая версия типа задачи и перевод старой в `deprecated` не затрагивают
    уже созданные задачи: они продолжают жить на своей версии. Новые задачи
    по ключу получают новейшую активную версию.

### Перенос ручных правок в git

Объект, который завели или поправили через API, выгружается в пакет:

```bash
python3 tools/cp_packages.py export \
  --server https://platform.example.com \
  --kind TaskType --key document-review \
  --package packages/<пакет>
```

`export` берёт новейшую активную версию (или ту, что указана в `--version`),
отбрасывает пустые поля и значения по умолчанию, а у скилла с контрактом
убирает поля, которые выводятся из контракта (`inputSchema`, `outputSchema`,
`protocol`).

## Новый пакет — пошагово

1. Создайте `packages/<key>/package.yaml` с `kind: Package`. Ключ совпадает с
   именем каталога.
2. Положите объекты по одному в файл. Проще всего начать с `export`
   существующего объекта.
3. Если пакет ссылается на объекты другого пакета, перечислите его в
   `requires`.
4. Запустите `make packages-check`.
5. Добавьте ключ пакета в `spec.packages` файла установки окружения.
6. Выполните `plan`, затем `apply` (или повторный bootstrap).

## Что в пакет не входит

- **Топология**: workspaces, проекты, членство и назначения ролей людям.
  Это данные окружения (state bootstrap), а не каталог. Principals и связки
  агентов в пакет тоже не пишутся: их выводит платформа из описания `Agent`.
- **Задачи-фикстуры.**
- **Доменные пакеты онтологии памяти** регистрируются в memory-service
  отдельно, см. [Контекст задачи и память](context.md).

## Типичные проблемы

| Сообщение | Причина | Что делать |
|---|---|---|
| `нужен PyYAML` / `нужен jsonschema` | нет зависимостей | `pip install pyyaml jsonschema` |
| `доменные валидаторы control-plane не импортируются` | нет сабмодуля `control-plane` | `git submodule update --init` |
| `execution ссылается на Skill …, которого нет ни в пакете …, ни в его requires` | незамкнутая ссылка | добавить пакет со скиллом в `requires` или перенести скилл |
| `в опубликованной версии отличаются contract — контракт версии неизменяем` | правили контракт без смены версии | поднять `spec.version` скилла |
| `переменная окружения X не задана (нужна пакету)` | нет значения для `${X}` | задать в `.env` или окружении |
| `retire: системный тип task вывести нельзя` | `task` в `retire` | убрать из списка |
| `artifactSchema.inputs 'spec': тип артефакта 'spec-document' не объявлен ни в пакете …, ни в его requires` | незамкнутая ссылка на тип артефакта | объявить `ArtifactType` в пакете или добавить пакет с ним в `requires` |
| `artifactSchema.outputs '…': mediaTypes [...] шире, чем у типа …` | выход расширяет, а не сужает media types типа | сузить `mediaTypes` выхода или расширить тип артефакта |
| `retire: вид ArtifactType не выводится из оборота` | `ArtifactType` в `retire` | убрать из списка |
| `ядро не принимает описание агента: …` | описание `Agent` не проходит модель `AgentSpec` ядра (неизвестное поле, пустые `permissions`) | исправить описание по сообщению |
| `422 non_canonical_value` при `apply` агента | в описании число с плавающей точкой (например дробное `resources.cpus`) | только целые числа |
| `identity.agent ссылается на агента …` / `… — такого Agent нет в пакете` | правило или назначение ссылается на агента вне пакета и его `requires` или выводимого из оборота | описать агента в пакете или добавить пакет в `requires` |
| `NotificationRule не применены: не задан сервис уведомлений` | нет `NOTIFICATION_SERVICE_URL` или токена | задать переменную и `NOTIFY_TOKEN` |
| `сервис уведомлений не принимает правило — …` | `:validate` вернул `422 invalid_notification_rule` | исправить правило по `details.errors` |
| `work.taskTypes '…' — такого TaskType нет в пакете …` | агент ссылается на тип задачи вне пакета и его `requires` | объявить тип или добавить пакет в `requires` |
| `403 permission_escalation` при `apply` агента | у токена нет прав, которые описание выдаёт агенту | применять токеном с этими правами |
| `нет CP_TOKEN и нет control_plane_client` | нет credential | задать `CP_TOKEN` или запустить интерпретатором с установленным `control-plane` |
| `control-plane не сохранил execution` | релиз ядра не поддерживает `execution` у типа задачи | обновить Control Plane |
| `ядро не поддерживает проверку процессов, только схема` / `ядро не знает /packages:plan` | Control Plane без движка процессов | обновить Control Plane; до этого процессы проверяются только схемой |
| `план устарел: каталог стенда изменился после построения плана` | ответ `plan_stale` на `apply --plan` | построить план заново и применить новый |
| `план правили после построения (хэш не сходится)` | файл плана изменён руками | построить план заново |
| `…: процессы и календари применяет ядро по плану` | в установке есть `Process` или `Calendar`, а вызван обычный `apply` | `plan --out plan.json`, затем `apply --plan plan.json` |
| `element_id_taken` от `pkg.py` | id элемента уже есть в процессе | выбрать другой id |

## См. также

- [Процессы](../processes/index.md) — язык вида `Process`
- [Тесты пакета](../processes/package-tests.md) — проверка, тесты, replay, план
- [Типы задач и статусы](task-types.md)
- [Правила вывода работы](work-rules.md)
- [Правила уведомлений](../notifications/notification-rules.md)
- [Артефакты и комментарии](artifacts.md#artifact-types) — реестр типов артефактов
- [Approvals](approvals.md)
- [Bootstrap](../getting-started/bootstrap.md)
- [skill-sdk](../sdk/skill-sdk.md)
- [Вертикальные пакеты](../sdk/vertical-packages.md)
- [Цели make](../reference/make.md)
