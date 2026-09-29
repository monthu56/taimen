# Вертикальные пакеты

Вертикальный пакет — способ добавить в платформу предметную область
(закупки, поддержка, юридическая проверка и т. п.), **не меняя ядро**:
доменный сервис со своей базой, каталог типов задач, ролей и скиллов,
агенты-исполнители и оркестратор. Статья описывает
архитектурные правила пакета, его составные части и порядок сборки поверх
ядра. Для архитекторов и разработчиков интеграций.

## Главное правило: пакет, а не расширение ядра

Если функциональность имеет смысл без предметной области — она кандидат в
ядро и оформляется отдельным решением. Если она существует **потому, что**
есть предметная область, — это пакет. В ядро Control Plane не добавляется
ни таблиц, ни эндпоинтов, ни событий со словами домена (обоснование —
TAI-ADR-0026, TAI-ADR-0030).

| Где живёт | Что |
|---|---|
| **Ядро** (Control Plane, IAM, память) | задачи, claims, runs, approvals, артефакты, события, роли, identity, знания |
| **Пакет** | доменные сущности и их правила, state machine домена, доменные гейты, интеграции с внешними источниками, UI домена |

Связь пакета с ядром — **только идентификаторами** (`task_id`, `run_id`,
`artifact_id`, `approval_id`, `principal_id`, `workspace_id`) и external
references ядра. Внешних ключей в чужие базы нет; двоичные документы —
артефакты ядра (содержимое — в хранилище артефактов ядра, см.
[Артефакты и комментарии](../control-plane/artifacts.md)).

## Анатомия пакета

```mermaid
flowchart TB
    subgraph Пакет
      API["Доменный сервис<br/>(своя БД, свой audience IAM)"]
      ORC["Оркестратор<br/>(reconciliation по журналу ядра)"]
      RUN["Исполнители<br/>(principal + PAT на агента)"]
      CAT["Пакет каталога<br/>(task types, роли, capabilities, skills)"]
    end
    subgraph Ядро
      CP[Control Plane]
      IAM[iam-service]
      MEM[memory-service]
    end
    CAT -->|make bootstrap| CP
    ORC -->|"GET /events, POST /tasks, approvals"| CP
    RUN -->|"claim → run → artifacts"| CP
    RUN -->|"доменные записи"| API
    ORC --> API
    API -->|TokenVerifier| IAM
    RUN -->|"обмен PAT ×2 audience"| IAM
    API -.->|"знания домена"| MEM
```

| Часть | Назначение | На чём строится |
|---|---|---|
| Доменный сервис | сущности домена, инварианты, state machine, API для UI и агентов | FastAPI + своя PostgreSQL + [platform-auth-sdk](platform-auth-sdk.md) |
| Пакет каталога | типы задач домена, роли, capabilities, скиллы — как данные | YAML в `packages/<пакет>/`, [skill-sdk](skill-sdk.md) для скиллов |
| Исполнители | агенты, которые берут назначенные им задачи домена | [control-plane-client](clients.md), [platform-llm](platform-llm.md) или runner-адаптеры |
| Оркестратор | «что дальше» для доменного объекта: заводит задачи и approvals в ядре по событиям | журнал событий ядра, `control-plane-client` |
| Знания | справочники и история домена | namespace в memory-service |

## Шаг 1. Доменный сервис

Сервис — обычный resource service платформы:

- принимает **только** access token IAM своего audience (например
  `acme-pack`); токен ядра (`control-plane`) он не принимает — `401
  invalid_token`, даже для того же principal'а;
- проверяет токен через `platform-auth-sdk` (`TokenVerifier` + `JwksCache` +
  `PolicyEnforcementPoint`), отвечает кодами SDK;
- различает читателей и писателей по scopes (`acme-pack:read`,
  `acme-pack:write`, `acme-pack:admin`);
- tenant и principal берёт из токена, каждую запись помечает principal'ом
  из токена;
- изолирует данные по tenant'у и workspace;
- делает записи идемпотентными по естественным ключам (внешний id источника,
  хеш документа, `run_id` решения) — агенты и оркестратор повторяют команды;
- отдаёт ошибки единым конвертом `{"error": {"code", "message", "details"}}`,
  как ядро.

Сборка образа — с контекстом корня суперпроекта (path-зависимости, см.
[SDK и интеграции](index.md#connect)):

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

## Шаг 2. Audience в IAM

Audience пакета заводится в tenant'е IAM со списком разрешённых scopes:

```bash
curl -s -X POST https://platform.example.com/iam/api/v1/tenants/$IAM_TENANT_ID/audiences \
  -H "X-IAM-Bootstrap-Token: $IAM_BOOTSTRAP_TOKEN" -H 'Content-Type: application/json' \
  -d '{"key": "acme-pack", "allowedScopes": ["acme-pack:read", "acme-pack:write", "acme-pack:admin"]}'
```

Для audiences, перечисленных в реестре `AUDIENCES` файла
`deploy/bootstrap.py`, это делает `make bootstrap` (идемпотентно приводит
`allowedScopes` к реестру). Подробнее — [Токены, audiences, scopes](../iam/tokens.md).

## Шаг 3. Пакет каталога

Типы задач, роли, capabilities и скиллы домена описываются данными в
`packages/<пакет>/` (формат — [Пакеты каталога](../control-plane/catalog-packages.md)):

```yaml
# packages/acme/package.yaml
kind: Package
key: acme
spec:
  version: 0.1.0
  displayName: Acme
  description: Типы задач и скиллы предметной области Acme
  requires: []
```

| Объект | Что даёт пакету |
|---|---|
| `TaskType` | типы задач домена со своими статусами, `fieldSchema` для `customFields`, исходами approval |
| `Role` | роли домена (кто решает, кто согласует) |
| `Capability` | что умеют исполнители; задачи требуют capability |
| `Skill` | действия домена с контрактом; YAML генерирует `skill-sdk export` |

Ключи типов задач — с префиксом пакета (`acme_document_parse`), чтобы не
пересекаться с другими пакетами. Установка пакета — его ключ в файле
установки окружения (`deploy/packages.yaml` или свой, передаётся
`bootstrap.py --packages <файл>`), затем `make bootstrap`.

!!! warning "Контракт ядра — из кода, а не из памяти"
    Типичная ошибка пакета — «придуманный» контракт API ядра, под который
    написаны и код, и тесты с фейковым сервером. Берите схемы из
    `control-plane` (OpenAPI `/openapi.json`, канонический клиент) и держите
    contract-тесты против снимка `openapi.json` и снимка реестра типов
    задач (`GET /api/v1/task-types`): ключи `typeKey` и `customFields`,
    которые шлёт пакет, должны существовать в реестре.

## Шаг 4. Агенты-исполнители

**Один агент — один principal — один PAT.** Иначе в audit работа разных
агентов неразличима.

| Что | Где | Как |
|---|---|---|
| principal агента | Control Plane (`kind: agent` или `service`) | `POST /api/v1/principals` |
| principal агента | IAM (`kind: agent` — PAT выпускается только `human` и `agent`) | `POST /api/v1/tenants/{t}/principals` |
| binding | Control Plane | `POST /api/v1/principals/{id}/iam-bindings` с правами; `admin` и `approvals.decide` агентам не выдаются |
| PAT | IAM | `POST /api/v1/tenants/{t}/principals/{id}/platform-access-tokens` с `audiences` и `scopeCeiling` |

PAT агента пакета выпускается сразу на **два audience** — ядра и пакета:

```bash
curl -s -X POST "$IAM/api/v1/tenants/$IAM_TENANT_ID/principals/$AGENT/platform-access-tokens" \
  -H "X-IAM-Bootstrap-Token: $IAM_BOOTSTRAP_TOKEN" -H "Idempotency-Key: $(uuidgen)" \
  -H 'Content-Type: application/json' \
  -d '{"name": "acme-document-analyst",
       "audiences": ["control-plane", "acme-pack"],
       "scopeCeiling": ["control-plane:read", "control-plane:write", "acme-pack:read", "acme-pack:write"],
       "expiresInSeconds": 15552000}'
```

Исполнитель делает **два обмена** одного PAT — по одному на audience — с
независимыми кэшами:

```python
pat = lambda: Path("/run/secrets/acme-document-analyst.pat").read_text()
cp_cred = IamCredential(iam_url, "", audience="control-plane",
                        scopes=("control-plane:read", "control-plane:write"),
                        platform_access_token=pat)
pack_cred = IamCredential(iam_url, "", audience="acme-pack",
                          scopes=("acme-pack:read", "acme-pack:write"),
                          platform_access_token=pat)
```


Для своего пакета выпускайте PAT через API IAM, как выше.

Как исполнители берут работу:

| Вариант | Когда |
|---|---|
| контейнер на агента с демоном, который берёт **только назначенные ему** задачи | детерминированные скиллы домена, LLM-скиллы через `platform-llm` |
| runner-хост с адаптером кодового агента | задачи, требующие работы в репозитории (см. [Адаптеры исполнителей](../runner/adapters.md)) |
| скилл, хостящийся через `skill-sdk` | действие, которое исполнитель ядра вызывает по контракту |

Если исполнитель берёт только назначенные задачи, каждую AI-стадию нужно
назначать агенту **при создании** — иначе конвейер встанет: держите одну
таблицу «тип задачи → скилл → principal» и вычисляйте assignee из неё.

Секреты агентов — файлы `<slug>.pat` с правами `0600`, смонтированные только
для чтения; контейнеры работают под непривилегированным uid (на Linux —
`chown` на этот uid).

## Шаг 5. Оркестратор

Оркестратор отвечает на вопрос «что дальше» для доменного объекта и
реализуется как **детерминированный reconciliation-loop**:

```mermaid
sequenceDiagram
    participant O as Оркестратор
    participant CP as Control Plane
    participant D as БД пакета
    O->>CP: GET /api/v1/events?cursor=… (durable cursor в своей БД)
    CP-->>O: task.completed, approval.approved, artifact.created, …
    O->>D: найти «свой» объект по id задачи/approval (ledger)
    O->>O: пересчитать состояние объекта
    O->>CP: POST /tasks, POST /approvals (ключ идемпотентности = объект + стадия)
    O->>D: записать стадию в ledger, сдвинуть курсор
```

Правила оркестратора:

- **Durable cursor** в базе пакета; событие, которое не удалось
  обработать, повторяется, а не пропускается.
- **Фильтрация — на стороне пакета.** Журнал ядра не фильтруется по
  workspace или типу события; «свои» задачи и approvals находятся по
  таблице-ledger (`core_ref_id` → доменный объект), чужие пропускаются.
- **Идемпотентность** по ключу `(объект, стадия)`: повтор события не создаёт
  дубликатов задач, approvals и решений.
- **Результат стадии** читается из артефактов задачи (`GET /artifacts?taskId=`),
  а непонятный или пустой результат безопасно сводится к эскалации
  человеку, а не к случайному решению.
- **Решение человека** — approval ядра с ролью домена; исход approval
  объявляется типом задачи (TAI-ADR-0041), а не кодом пакета.
- **Статусы** сравниваются по категориям (`terminal_success`,
  `terminal_cancelled`), а не по ключам — ключи объявляет тип задачи.

## Шаг 6. Интерфейс человека


Веб-консоли с модулями пакетов в поставке нет. Человек видит задачи и approvals
пакета там же, где любые задачи ядра: в [MCP-плагине](../operator/mcp-plugin.md),
CLI и [уведомлениях](../notifications/index.md). Решения по approvals принимаются в
ядре, поэтому отдельный интерфейс для них пакету не нужен.

Если домену нужен собственный UI, он — часть пакета и ходит в доменный сервис с
access token IAM его audience, как любой другой клиент.

## Шаг 7. Знания

Справочники, регламенты и история домена загружаются в собственный
namespace memory-service (см. [Загрузка знаний](../memory/ingestion.md)).
Исполнители получают релевантные знания через контекст задачи ядра, а
сервис пакета — через [platform-memory-client](clients.md#memory-client) со
своим грантом.

## Шаг 8. Профили compose

Пакет поднимается отдельными профилями, чтобы ядро работало без него:

| Профиль | Содержимое |
|---|---|
| `<пакет>` | доменный сервис и его БД (оркестратор — внутри сервиса, включается флагом) |
| `<пакет>-runners` | контейнеры исполнителей, по одному на агента |

```bash
make up PROFILES="core <пакет> <пакет>-runners edge"
```

## Чек-лист готовности пакета

- [ ] Ни одного изменения в ядре ради домена.
- [ ] Собственный audience, токены ядра сервисом не принимаются.
- [ ] Все записи идемпотентны и помечены principal'ом из токена.
- [ ] Каталог пакета — YAML в `packages/<пакет>/`, скиллы сгенерированы из кода.
- [ ] Один principal и один PAT на агента, PAT в файлах `0600`.
- [ ] AI-стадии назначаются исполнителю при создании задачи.
- [ ] Оркестратор с durable cursor и ключом идемпотентности `(объект, стадия)`.
- [ ] Contract-тесты против снимка `openapi.json` ядра.
- [ ] Задачи и approvals пакета видны в рабочем месте и MCP-плагине без доработок.

## См. также

- [SDK и интеграции](index.md)
- [Пакеты каталога](../control-plane/catalog-packages.md)
- [Типы задач и статусы](../control-plane/task-types.md)
- [Approvals](../control-plane/approvals.md)
- [События Control Plane](../control-plane/events.md)
- [Identity агента](../runner/agent-identity.md)
