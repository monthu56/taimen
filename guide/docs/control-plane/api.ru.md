# API

Справочник HTTP API Control Plane. Все endpoints живут под `/api/v1`, поля
тела и ответа в camelCase. Статья описывает общие правила (аутентификация,
заголовки, пагинация, идемпотентность, формат ошибок) и перечисляет каждый
endpoint с правом и назначением, сгруппировав их по ресурсам. Справочник для
разработчиков интеграций и харнессов.

!!! tip "Машинная схема"
    Полная схема OpenAPI отдаётся самим сервисом: `GET /openapi.json`,
    Swagger UI — `GET /docs`. Справочник ниже составлен по той же схеме и по
    коду команд, которые проверяют права.

## Базовый адрес

| Где | Адрес |
|---|---|
| Внутри сети compose | `http://control-plane-api:8000` |
| С хоста (по умолчанию только loopback) | `http://127.0.0.1:${CP_HOST_PORT:-18000}` |
| Снаружи через периметр | `https://platform.example.com` (маршруты `/api/v1/*`, `/health/*`, `/metrics`, `/docs*`, `/openapi.json`) |

Схема периметра описана в статье [Периметр и TLS](../operations/edge-and-tls.md).

## Аутентификация

```http
Authorization: Bearer <access-token IAM audience control-plane>
```

- IAM access token: права берутся из привязки identity к principal и
  сужаются scopes токена (`control-plane:read`, `control-plane:write`,
  `control-plane:admin`).
- Legacy-ключ `cp_<prefix>_<secret>` принимается только при
  `CP_LEGACY_API_KEYS_ENABLED=true`.
- `POST /api/v1/bootstrap` принимает только `Bearer <CP_BOOTSTRAP_TOKEN>`.
- `/health/live`, `/health/ready` и `/metrics` открыты без аутентификации.

Actor всегда вычисляется из credential. Подробности — в статье
[Авторизация и права](authorization.md).

## Заголовки протокола

| Заголовок | Направление | Семантика |
|---|---|---|
| `Idempotency-Key` | запрос, мутации | идемпотентное выполнение, см. раздел [Идемпотентность](#idempotency) |
| `Idempotency-Replayed: true` | ответ | ответ взят из сохранённого, команда не выполнялась повторно |
| `If-Match: "<entity>-<version>"` | запрос | оптимистичная блокировка: PATCH задачи, workspace, типа workspace, проекта, роли, скилла, цели и комментария; `:complete` задачи; `:transition` проекта; `config-revisions/{n}:activate` |
| `ETag` | ответ | `"<entity>-<version>"` у GET задачи (`task-`), workspace (`workspace-`), типа workspace (`workspace_type-`), проекта (`project-`), роли (`role-`), скилла (`skill-<rowVersion>`), цели (`goal-`), комментария (`comment-`); у `GET /tools` — `viewHash` |
| `If-None-Match` | запрос | для `GET /tools`: `304`, пока ревизии каталога и политики не изменились |
| `X-Request-ID` | оба | принимается или генерируется; возвращается в ответе и в `error.requestId` |
| `X-Correlation-ID` | запрос | попадает в `correlationId` событий |
| `X-Run-Id` | оба | сквозной trace-коррелятор (`^[A-Za-z0-9._:-]{1,128}$`, иначе генерируется); пишется в `traceRunId` событий, outbox, логи и заголовок к memory-service. Это **не** сущность Run |

Ошибки `If-Match`:

| Ситуация | Ответ |
|---|---|
| заголовка нет | `428 if_match_required` |
| заголовок нельзя разобрать | `400 invalid_if_match` |
| версия не совпала | `409 version_conflict`, в `details.currentVersion` — текущая версия |

## Пагинация

```text
GET /api/v1/tasks?limit=50&cursor=<opaque>
```

```json
{"items": [ ... ], "nextCursor": "..."}
```

- `limit`: по умолчанию 50, максимум 200. Значение вне диапазона даёт
  `422 invalid_limit`.
- Курсор непрозрачен. Чужой курсор или курсор от другого порядка сортировки
  даёт `422 invalid_cursor`.
- Списки сущностей сортируются стабильно по `(created_at, id)`, новые первыми.
- Журналы прогона (`/runs/{id}/checkpoints`, `/runs/{id}/actions`) идут по
  `seq`, старые первыми, курсор привязан к прогону. Без `limit` и `cursor`
  журнал отдаётся целиком одной страницей (`nextCursor: null`).
- Комментарии задачи — единственная сущностная выборка от старых к новым. Её
  курсор имеет собственный формат.
- `GET /tasks?sort=startDate|dueDate`: ближайшие первыми, задачи без даты — в
  конце. Неизвестный `sort` даёт `422 invalid_sort`.
- `GET /work/available` может вернуть страницу короче `limit` при непустом
  `nextCursor`.

### События

`GET /events` — отдельный контракт:

| Параметр | Смысл |
|---|---|
| `cursor` | непрозрачный курсор `ec1_…` |
| `after` | целочисленный `sequence` старого формата; адаптируется сервером |
| `tail=N` | последние N стабильных событий |
| `entityType`, `entityId` | фильтр по сущности |
| `types` | префиксы типа событий, до 20 |
| `workspaceId` | поддерево workspace; `events.read` проверяется на нём |
| `limit` | размер страницы |

Ответ: `{items[], nextCursor, hasMore}`, у каждого события есть своё поле
`cursor`. При пустой странице `nextCursor` повторяет переданный.
Малформированный курсор даёт `422 invalid_cursor`, курсор будущей версии —
`422 unsupported_cursor_version`.

WebSocket: `WS /api/v1/events/ws?after=<cursor>`, право `events.read`. Коды
закрытия: `4401` — нет credentials, `4403` — нет права, `4404` — нет workspace
фильтра, `4400` — плохой курсор или фильтр, `4503` — PDP недоступен. Фильтры
и SDK потребителя — в статье [Подписки на события](event-subscriptions.md).

## Неизвестные query-параметры

Сервер не игнорирует query-параметры молча. Параметр, которого endpoint не
объявляет, даёт `400 invalid_request`, и выборка не выполняется:

```json
{
  "error": {
    "code": "invalid_request",
    "message": "Request does not match the API contract",
    "details": {"errors": [{"loc": "query.assignedToMee", "message": "Unknown query parameter: ..."}]},
    "requestId": "req_..."
  }
}
```

Правило действует на всех endpoints `/api/v1`, кроме WebSocket. Не добавляйте
служебные параметры вроде cache-buster `_=`: они тоже будут отклонены.
Неизвестные поля в JSON-теле также отклоняются (`extra="forbid"`), кроме тела
компиляции манифеста.

## Идемпотентность {#idempotency}

Любая мутация (POST-команда или PATCH) принимает заголовок `Idempotency-Key`
длиной 1–200 символов, иначе `422 invalid_idempotency_key`.

| Ситуация | Результат |
|---|---|
| первый запрос | выполняется, ответ сохраняется на `CP_IDEMPOTENCY_TTL_SECONDS` (сутки) |
| повтор с тем же ключом, методом, путём, телом и principal | сохранённый ответ и `Idempotency-Replayed: true` |
| тот же ключ с другим телом **или другим principal** | `409 idempotency_key_reused` |
| параллельный дубль, пока первый не завершился | ждёт до `CP_IDEMPOTENCY_WAIT_TIMEOUT_SECONDS` (10 с), затем `409 idempotency_in_flight` |
| исполнитель упал на полпути | незавершённая запись живёт не дольше `CP_IDEMPOTENCY_PENDING_TTL_SECONDS` (60 с) |

Одноразовые секреты не сохраняются: повтор выпуска API-ключа вернёт
`key: null`. Для двух команд ключ обязателен: `POST /runs/{id}/control-messages`
и `POST /runs/{id}/child-handles` (без него `422 idempotency_key_required`).
Для `:handoff` и `:revoke` дочернего handle ключ настоятельно рекомендуется:
повтор без него после неоднозначного ответа становится новой командой.

!!! tip "Правило клиента"
    Один логический вызов — один ключ на все транспортные повторы. Повтор
    HTTP-запроса не должен превращаться во вторую бизнес-команду. SDK
    `control_plane_client` делает это сам.

## Формат ошибок {#errors}

Единый конверт с честными HTTP-кодами. Ответа `200` с ошибкой внутри не
бывает.

```json
{
  "error": {
    "code": "task_already_claimed",
    "message": "Task already has an active claim",
    "details": {"taskId": "...", "claimId": "...", "expiresAt": "..."},
    "requestId": "req_..."
  }
}
```

Клиенту следует опираться на `code` и `details`, а не на текст `message`.

| HTTP | Типичные `error.code` |
|---|---|
| 400 | `invalid_request` (нарушение контракта, в т.ч. неизвестный параметр; `details.errors[].loc`), `invalid_if_match`, `invalid_skill_inputs`, `idempotency_key_required` |
| 401 | `invalid_credentials` |
| 403 | `permission_denied` (`details.required`), `principal_not_active`, `delegation_required`, `claim_holder_mismatch`, `session_owner_mismatch`, `bootstrap_disabled`, `permission_escalation`, `not_eligible`, `run_holder_mismatch`, `tool_not_authorized`, `child_grant_exceeded`, `skill_permission_denied`, `skill_side_effect_not_authorized`, `run_owner_mismatch`, `run_id_required`, `scope_not_granted` |
| 404 | `not_found`, `tool_not_found` (объект чужого tenant'а тоже даёт 404: существование не раскрывается) |
| 409 | `version_conflict`, `stale_claim`, `task_already_claimed`, `task_claimed`, `session_expired`, `session_not_active`, `claim_expired`, `claim_not_active`, `claim_not_expired`, `idempotency_key_reused`, `idempotency_in_flight`, `already_bootstrapped`, `task_already_completed`, `task_not_ready`, `run_already_active`, `run_not_active`, `run_in_progress`, `approval_required`, `approval_already_decided`, `budget_exceeded`, `action_already_finished`, `skill_not_invocable`, `stale_invocation_lease`, `outcome_not_replayable`, `snapshot_stale`, `pack_version_conflict`, `retention_blocked_by_consumer`, конфликты уникальности (`*_exists`, `*_conflict`) |
| 413 | `request_too_large` — тело больше `CP_MAX_BODY_BYTES` |
| 422 | доменная валидация: `invalid_*`, `task_not_claimable`, `task_cancelled`, `empty_update`, `dependency_cycle`, `workspace_cycle`, `workspace_archived`, `unsupported_protocol_version`, `server_authoritative_section`, `secret_material_rejected`, `child_grant_exceeds_parent`, `child_result_too_large`, `cursor_must_not_advance`, `workspace_not_root`, `pack_*`, `snapshot_invalid` и др. |
| 428 | `if_match_required` |
| 500 | `internal_error` — без стектрейса, подробности в логе по `requestId` |
| 502 | `memory_unavailable` — memory-service не обработал проксируемый запрос (`details.memoryStatus`, `details.retryable`) |
| 503 | `policy_unavailable`, `memory_disabled`; readiness — БД недоступна или миграции не применены |

Полный реестр кодов всех сервисов — в [Коды ошибок](../reference/errors.md).

## Служебные endpoints

| Метод и путь | Аутентификация | Ответ |
|---|---|---|
| `GET /health/live` | нет | `{"status": "alive"}` |
| `GET /health/ready` | нет | `200 {"status": "ready", "revision": "<alembic>"}`; `503` с `reason: database_unreachable` или `migrations_pending` (`dbRevision`, `headRevision`) |
| `GET /metrics` | нет | метрики в формате Prometheus: `http_requests_total`, `active_harness_sessions`, `active_claims`, `active_runs`, `context_adapter_*`, `stale_fencing_rejections_total`, `authz_*` и др. |
| `GET /openapi.json`, `GET /docs` | нет | схема OpenAPI и Swagger UI |

!!! warning "`/metrics` открыт"
    Эндпоинт не аутентифицирован. Закрывайте его на уровне периметра, см.
    [Мониторинг и здоровье](../operations/monitoring.md).

## Справочник endpoints

Колонка «Право» перечисляет permission, которое проверяет сервер. «Владелец»
означает держателя сессии, claim или прогона. `{ref}` у задачи — это UUID или
`publicId` (`TASK-000123`).

### Bootstrap

| Метод | Путь | Право | Назначение |
|---|---|---|---|
| POST | `/bootstrap` | `Bearer <CP_BOOTSTRAP_TOKEN>` | один раз создать tenant, admin-principal, admin API-ключ и (с `iamBinding`) IAM-привязку администратора |

Тело: `tenantSlug` (`^[a-z0-9][a-z0-9-]*$`, 2–63), `tenantName`,
`adminDisplayName`, `tenantId?` (UUID tenant'а, общий с IAM),
`iamBinding? {issuer, iamTenantId, iamPrincipalId}`. Ответ `201`:
`{tenant, adminPrincipal, apiKey (с полным key), iamBinding}`.

### Principals, ключи, привязки, делегирование

| Метод | Путь | Право | Назначение |
|---|---|---|---|
| POST | `/principals` | `principals.write` | создать principal (`kind`: `human`, `agent`, `service`; `displayName`, `status`, `metadata`) |
| GET | `/principals` | `principals.read` | список (`?kind=`) |
| GET | `/principals/{id}` | `principals.read` | principal |
| POST | `/principals/{id}/api-keys` | `principals.write` | выпустить legacy-ключ `{permissions, expiresAt?}`; полный ключ — только в этом ответе |
| POST | `/api-keys/{id}:revoke` | `principals.write` | отозвать ключ |
| GET | `/principals/{id}/iam-bindings` | `principals.read` | IAM-привязки principal, включая отозванные (без пагинации) |
| POST | `/principals/{id}/iam-bindings` | `principals.write` | upsert привязки `{issuer, iamTenantId, iamPrincipalId, permissions}`; `201` / `200` |
| POST | `/iam-bindings/{id}:revoke` | `principals.write` | закрыть вход identity |
| POST | `/delegations` | `delegations.manage` | делегирование человек → агент |
| GET | `/delegations` | `delegations.manage` | список |
| POST | `/delegations/{id}:revoke` | `delegations.manage` | отозвать |

### Сессии и харнесс

| Метод | Путь | Право | Назначение |
|---|---|---|---|
| POST | `/sessions` | `sessions.open` | открыть сессию; блок `harness`, `onBehalfOf` требует delegation |
| GET | `/sessions` | `sessions.manage` | список (`?status=`) |
| GET | `/sessions/{id}` | владелец или `sessions.manage` | сессия |
| POST | `/sessions/{id}:heartbeat` | владелец или `sessions.manage` | продлить аренду (`ttlSeconds?`) |
| POST | `/sessions/{id}:close` | владелец или `sessions.manage` | закрыть и снять claims сессии |
| GET | `/harness/context` | аутентификация | self-контекст харнесса (`?sessionId=`) |
| GET | `/work/available` | `tasks.read` | доступная работа (`workspaceId`, `includeDescendants`, `projectId`, `includeSubprojects`, `assigneeId`, `assignedToMe`) |
| GET | `/tools` | `tasks.read` | поиск инструментов (`query`, `runId`); ETag, `If-None-Match` |
| GET | `/tools/{ref}` | `tasks.read` | инструмент по `uuid`, `name` или `name@version` (`?runId=`); вне политики — `404 tool_not_found` |

Протокол подробно описан в статье [Харнесс-протокол](harness-protocol.md).

### Типы задач

| Метод | Путь | Право | Назначение |
|---|---|---|---|
| POST | `/task-types` | `task_types.manage` | следующая неизменяемая версия ключа (`lifecycleSchema`, `fieldSchema`, `approvalSchema`, `execution`) |
| GET | `/task-types` | `task_types.read` | список (`?key=&status=`) |
| GET | `/task-types/{id}` | `task_types.read` | версия типа |
| POST | `/task-types/{id}:deprecate` | `task_types.manage` | вывести версию из оборота (идемпотентно) |

См. [Типы задач и статусы](task-types.md) и [Пакеты каталога](catalog-packages.md).

### Задачи

| Метод | Путь | Право | Назначение |
|---|---|---|---|
| POST | `/tasks` | `tasks.write` | создать задачу |
| GET | `/tasks` | `tasks.read` | список: `status`, `systemStatusCategory`, `typeKey`, `priority`, `ownerId`, `assigneeId`, `workspaceId`, `includeDescendants`, `projectId`, `includeSubprojects`, `startFrom`, `startTo`, `dueFrom`, `dueTo`, `sort` (`createdAt`, `startDate`, `dueDate`), `goalId` |
| GET | `/tasks/{ref}` | `tasks.read` | задача (+ETag) |
| PATCH | `/tasks/{ref}` | `tasks.write` | изменить (`If-Match`; при живом claim — `claimId` и `fencingToken`) |
| GET | `/tasks/{ref}/claimability` | `tasks.read` | можно ли взять и почему нет |
| GET | `/tasks/{ref}/transitions` | `tasks.read` | куда можно перейти из текущего статуса (`route`: `update` или `complete`) |
| POST | `/tasks/{ref}:claim` | `tasks.claim` | атомарный claim `{sessionId, ttlSeconds?, intent?}` → fencing token |
| POST | `/tasks/{ref}:complete` | `tasks.write` | завершить (`If-Match`; при живом claim — `claimId` и `fencingToken`) |
| POST | `/tasks/{ref}:start-run` | `tasks.claim` | прогон под живым claim `{claimId, fencingToken, input?, maxDurationSeconds?, maxActions?, agentRevisionId?}` |
| POST | `/tasks/{ref}/relations` | `tasks.write` | связь `{toTask, type}`: `parent`, `blocks`, `depends_on`, `spawned_by`, `related_to`; циклы — `422` |
| GET | `/tasks/{ref}/relations` | `tasks.read` | связи в обе стороны |
| DELETE | `/tasks/{ref}/relations/{relationId}` | `tasks.write` | удалить связь |
| GET | `/tasks/{ref}/requirements` | `tasks.read` | требования (roles, capabilities, skills) |

Пример создания задачи:

```bash
curl -s -X POST https://platform.example.com/api/v1/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "title": "Добавить индекс на events(tenant_id, tx_id)",
    "description": "Запросы журнала упираются в seq scan",
    "priority": "high",
    "typeKey": "coding-task",
    "workspaceId": "<workspace-id>",
    "requirements": {"skills": ["git.merge@1"]},
    "acceptance": [{"key": "tests", "kind": "deterministic", "description": "make test проходит"}]
  }'
```

Поля `POST /tasks`: `title` (1–500), `description`, `priority` (`critical`,
`high`, `medium`, `low`; по умолчанию `medium`), `status` (по умолчанию
`initialStatus` типа), `typeId`, `typeKey`, `typeVersion` (по умолчанию
системный тип `task`), `ownerId`, `assigneeId`, `workspaceId`, `customFields`
(проверяются по `fieldSchema` версии типа), `startDate`, `dueDate`,
`parentTask` (связь `parent` создаётся атомарно), `requirements`, `goalId`,
`origin` (неизменяем; без него ядро выводит `parent`, `human` или `harness`),
`acceptance[]`, `evidence[]`. Семантика — в статьях [Модель работы](work-model.md)
и [Цели, приёмка и evidence](goals-and-evidence.md).

### Цели

| Метод | Путь | Право | Назначение |
|---|---|---|---|
| POST | `/goals` | `goals.write` | цель (`title`, `desiredState`, `criteria[]`, `ownerId`, `workspaceId`, `parentGoalId`, `createdFrom`) |
| GET | `/goals` | `goals.read` | список (`status`, `workspaceId`, `ownerId`, `parentGoalId`) |
| GET | `/goals/{id}` | `goals.read` | цель (+ETag `goal-<v>`) |
| PATCH | `/goals/{id}` | `goals.write` | изменить (`If-Match`); `status`: `active`, `achieved`, `abandoned`; цикл — `422 goal_cycle` |
| GET | `/goals/{id}/work` | `goals.read` + `tasks.read` | задачи цели, новые сверху (`includeSubgoals`, `systemStatusCategory`) |

### Комментарии к задаче

| Метод | Путь | Право | Назначение |
|---|---|---|---|
| POST | `/tasks/{ref}/comments` | `tasks.write` | добавить `{body, runId?, artifactId?}`; автор — вызывающий |
| GET | `/tasks/{ref}/comments` | `tasks.read` | тред, от старых к новым |
| GET | `/tasks/{ref}/comments/{id}` | `tasks.read` | комментарий (+ETag `comment-<v>`) |
| PATCH | `/tasks/{ref}/comments/{id}` | `tasks.write`, только автор | исправить (`If-Match`); прежний текст — ревизия |
| GET | `/tasks/{ref}/comments/{id}/revisions` | `tasks.read` | история правок (append-only) |

### Claims

| Метод | Путь | Право | Назначение |
|---|---|---|---|
| GET | `/claims` | `tasks.read` | список (`taskId`, `sessionId`, `status`) |
| GET | `/claims/{id}` | `tasks.read` | claim |
| POST | `/claims/{id}:heartbeat` | держатель или `claims.manage` | продлить аренду |
| POST | `/claims/{id}:release` | держатель или `claims.manage` | освободить; задача → `releaseStatus` типа, если ребро объявлено |
| POST | `/claims/{id}:reclaim` | `tasks.claim` | перехватить **истёкший** claim (новый token) |

### Прогоны (runs)

| Метод | Путь | Право | Назначение |
|---|---|---|---|
| GET | `/runs` | `tasks.read` | список (`taskId`, `claimId`, `status`) |
| GET | `/runs/{id}` | `tasks.read` | прогон |
| GET | `/runs/{id}/context` | `tasks.read` | Run Context |
| POST | `/runs/{id}:succeed` | `tasks.claim`, владелец | успех `{output?, completeTask=true}` |
| POST | `/runs/{id}:fail` | владелец или `claims.manage` | неудача (задачу не трогает) |
| POST | `/runs/{id}:cancel` | владелец или `claims.manage` | отмена |
| POST | `/runs/{id}:suspend` | `tasks.claim`, владелец живого claim | приостановить `{reason, waitingForApprovalId?}` |
| POST | `/runs/{id}:handoff` | `tasks.claim` | передать другому харнессу (рекомендуется `Idempotency-Key`) |
| POST | `/runs/{id}:request-cancel` | `tasks.write` или `claims.manage` | кооперативный сигнал отмены |
| POST | `/runs/{id}/checkpoints` | `tasks.claim`, владелец живого claim | checkpoint `{kind, data}` |
| GET | `/runs/{id}/checkpoints` | `tasks.read` | checkpoints по `seq` |
| POST | `/runs/{id}/actions` | `tasks.claim`, владелец живого claim | действие `{action, status, skill?, externalReference?, metadata}`; бюджет → `409 budget_exceeded` |
| POST | `/runs/{id}/actions/{actionId}:finish` | `tasks.claim` | завершить `started`-действие |
| GET | `/runs/{id}/actions` | `tasks.read` | журнал действий по `seq` |
| POST | `/runs/{id}/control-messages` | `tasks.write`; `force_cancel` — `claims.manage` | control-сообщение (`Idempotency-Key`, `expectedRunVersion` обязательны) |
| GET | `/runs/{id}/control-messages` | `tasks.read` | сообщения, курсор `rc1_…` |
| POST | `/runs/{id}/control-messages/{messageId}:acknowledge` | `tasks.claim`, держатель живого claim | подтвердить `applied`, `rejected` или `superseded` |
| POST | `/runs/{id}/child-handles` | `tasks.claim` + `tasks.write`, владелец живого claim | запустить дочерний прогон; `201` новый, `200` повтор `correlationId` |
| GET | `/runs/{id}/child-handles` | `tasks.read` | handles прогона (`?active=true`, курсор `cd1_…`) |
| GET | `/child-handles/{idOrToken}` | `tasks.read` | статус и результат по id или `ch1_…` |
| POST | `/child-handles/{id}:revoke` | держатель родительского прогона или `claims.manage` | отозвать `{reason, cancelChild}` |

Прогон называет ревизию агента, по которой идёт (CP-ADR-0073): исполнитель,
чей principal привязан к агенту, передаёт в `:start-run` поле `agentRevisionId`
(без него — `422 agent_revision_required`, ревизия чужого агента —
`422 agent_revision_mismatch`), сервер записывает его на run и в событие
`run.started`. Свою текущую ревизию исполнитель читает через `GET /agents/me`.
Отдельного снимка конфигурации на каждый прогон нет (см.
[Ревизия агента на прогоне](harness-protocol.md#agent-revision)).

См. [Исполнение — claims и runs](execution.md) и [Харнесс-протокол](harness-protocol.md).

### Артефакты

| Метод | Путь | Право | Назначение |
|---|---|---|---|
| POST | `/artifacts` | `artifacts.write` | append-only ссылка на результат: `type`, `name`, `task?`, `runId?`, `workspaceId?`, `uri?`, `content?`, `metadata`, `supersedesArtifactId?` |
| GET | `/artifacts` | `artifacts.read` | список (`taskId`, `runId`, `workspaceId`, `type`) |
| GET | `/artifacts/{id}` | `artifacts.read` | артефакт |

### Approvals

| Метод | Путь | Право | Назначение |
|---|---|---|---|
| POST | `/approvals` | `approvals.manage` | запрос; ровно одно из `requiredRoleId` / `assignedPrincipalId`; `gate: true` требует `task` и блокирует claim и complete |
| GET | `/approvals` | `approvals.read` | список (`status`, `taskId`) |
| GET | `/approvals/{id}` | `approvals.read` | approval |
| POST | `/approvals/{id}:approve` | `approvals.decide` + eligibility | одобрить |
| POST | `/approvals/{id}:reject` | `approvals.decide` + eligibility | отклонить |
| POST | `/approvals/{id}:cancel` | `approvals.manage`; для gate — автор или eligible-решатель | отменить |
| GET | `/approvals/{id}/outcome` | `approvals.read` | объявленный исход решения и статус каждого действия |
| POST | `/approvals/{id}:replay-outcome` | `approvals.decide` (решивший или admin) | продолжить упавший или зависший исход с первого невыполненного действия; иначе `409 outcome_not_replayable` |

См. [Approvals](approvals.md).

### События и наблюдения

| Метод | Путь | Право | Назначение |
|---|---|---|---|
| GET | `/events` | `events.read` | журнал (см. раздел [Пагинация событий](#events-pagination)) |
| WS | `/events/ws?after=<cursor>` | `events.read` | поток событий |
| POST | `/observations` | `observations.write` | явная запись знания; повтор (`source`, `dedupKey`) → `200 deduplicated` |

### Контекст и знания

| Метод | Путь | Право | Назначение |
|---|---|---|---|
| POST | `/context` | аутентификация (`task`/`runId` — `tasks.read`, `projectId` — `projects.read`, память — `events.read`) | operational-контекст и пакет памяти |
| POST | `/knowledge/snapshots` | `observations.write` на `workspace:<workspaceId>` | снимок источника → memory-service (тело до 8 МиБ) |
| POST | `/knowledge/packs` | principal из `CP_KNOWLEDGE_PACK_ADMINS` | регистрация пакета знаний |
| PUT | `/workspaces/{id}/knowledge-packs` | `workspaces.manage` на `workspace:<id>` | пакеты и `strict` namespace дерева (только корень) |

См. [Контекст задачи и память](context.md).

### Workspaces и типы workspace

| Метод | Путь | Право | Назначение |
|---|---|---|---|
| POST | `/workspace-types` | `workspaces.manage` | тип workspace |
| GET | `/workspace-types` | `workspaces.read` | список (`status`) |
| GET | `/workspace-types/{id}` | `workspaces.read` | тип (+ETag) |
| PATCH | `/workspace-types/{id}` | `workspaces.manage` | изменить (`If-Match`) |
| POST | `/workspace-types/{id}:archive` | `workspaces.manage` | архивировать; используется — `422 workspace_type_in_use` |
| POST | `/workspaces` | `workspaces.manage` | workspace (`typeId` или `typeKey`, `customFields`) |
| GET | `/workspaces` | `workspaces.read` | список (`parentId`, `rootsOnly`, `status`) |
| GET | `/workspaces/tree` | `workspaces.read` | дерево (`rootId`, `depth`, `includeArchived`, `includeProjects`) → `{roots: [...]}` |
| GET | `/workspaces/{id}` | `workspaces.read` | workspace (+ETag) |
| PATCH | `/workspaces/{id}` | `workspaces.manage` | изменить (`If-Match`) |
| POST | `/workspaces/{id}:archive` | `workspaces.manage` | архивировать (без активных детей) |
| POST | `/workspaces/{id}:move` | `workspaces.manage` | перенести `{newParentId}` (`null` — в корень); цикл или ослабление governance — `422` |
| POST | `/workspaces/{id}/members` | `workspaces.manage` | добавить участника |
| GET | `/workspaces/{id}/members` | `workspaces.read` | участники |
| POST | `/workspaces/{id}/members/{principalId}:remove` | `workspaces.manage` | удалить участника |

### Проекты и шаблоны

| Метод | Путь | Право | Назначение |
|---|---|---|---|
| POST | `/project-templates` | `project_templates.manage` | следующая неизменяемая версия шаблона |
| GET | `/project-templates` | `project_templates.read` | список (`key`, `status`) |
| GET | `/project-templates/{id}` | `project_templates.read` | шаблон |
| POST | `/project-templates/{id}:deprecate` | `project_templates.manage` | вывести из оборота |
| POST | `/projects` | `projects.manage` | проект: `workspaceId` или `workspaceSlug` (workspace и профиль создаются атомарно); второй профиль — `409 project_exists` |
| GET | `/projects` | `projects.read` | список (`workspaceId`, `status`, `statusKey`, `systemStatusCategory`, `templateKey`, `externalSystem`, `externalType`, `externalId`) |
| GET | `/projects/{id}` | `projects.read` | проект (+ETag) |
| PATCH | `/projects/{id}` | `projects.manage` | изменить (`If-Match`) |
| POST | `/projects/{id}:archive` | `projects.manage` | архивировать (идемпотентно) |
| POST | `/projects/{id}:transition` | `projects.manage` | переход статуса (`If-Match`; только объявленные) |
| GET | `/projects/{id}/effective-config` | `projects.read` | конфигурация и provenance по слоям |
| GET | `/projects/{id}/config-revisions` | `projects.read` | ревизии конфигурации |
| POST | `/projects/{id}/config-revisions` | `projects.manage` | новая ревизия (не активирует) |
| POST | `/projects/{id}/config-revisions/{revision}:activate` | `projects.manage` | активировать ревизию (`If-Match`) |
| GET | `/projects/{id}/external-references` | `projects.read` | внешние ссылки проекта |
| POST | `/projects/{id}/external-references` | `projects.manage` | добавить (`201`) или обновить metadata (`200`); чужая сущность — `409` |

### Внешние ссылки

| Метод | Путь | Право | Назначение |
|---|---|---|---|
| POST | `/external-references` | по `entityType`: `project` → `projects.manage`, `task` → `tasks.write` | зарегистрировать ссылку; `201` новая, `200` тот же ключ, `409 external_reference_conflict` |
| GET | `/external-references` | право чтения типа | прямой поиск `?entityType=&entityId=` или обратный `?externalSystem=&externalType=&externalId=` |

### Организационная модель

| Метод | Путь | Право | Назначение |
|---|---|---|---|
| POST | `/roles` | `org.manage` | роль (`slug` уникален в scope; `workspaceId?`) |
| GET | `/roles` | `org.read` | список (`workspaceId`) |
| GET | `/roles/{id}` | `org.read` | роль (+ETag) |
| PATCH | `/roles/{id}` | `org.manage` | изменить (`If-Match`) |
| POST | `/capabilities` | `org.manage` | capability |
| GET | `/capabilities` | `org.read` | список |
| GET | `/capabilities/{id}` | `org.read` | capability |
| POST | `/principals/{id}/roles` | `org.manage` | назначить `{roleId, workspaceId?}` |
| GET | `/principals/{id}/roles` | `org.read` или `principals.read` | роли principal |
| POST | `/principals/{id}/roles/{roleId}:revoke` | `org.manage` | снять |
| POST | `/principals/{id}/capabilities` | `org.manage` | назначить |
| GET | `/principals/{id}/capabilities` | `org.read` или `principals.read` | capabilities principal |
| POST | `/principals/{id}/capabilities/{capabilityId}:revoke` | `org.manage` | снять |
| POST | `/principals/{id}/skills` | `org.manage` | назначить скилл |
| GET | `/principals/{id}/skills` | `org.read` или `principals.read` | скиллы principal |
| POST | `/principals/{id}/skills/{skillId}:revoke` | `org.manage` | снять |

### Скиллы и вызовы {#skills}

| Метод | Путь | Право | Назначение |
|---|---|---|---|
| POST | `/skills` | `org.manage` | опубликовать версию (`name` + `version` уникальны; `contract`, `sideEffects`, `riskLevel`) |
| GET | `/skills` | `org.read` | список (`name`, `status`) |
| GET | `/skills/{ref}` | `org.read`, `skills.invoke` или `skills.execute` | версия по `id`, `name@version` или `name` (+ETag `skill-<rowVersion>`) |
| PATCH | `/skills/{id}` | `org.manage` | `If-Match`; меняются только `description` и `status` вперёд (`active` → `deprecated` → `disabled`). `config`, `inputSchema`, `outputSchema` допустимы, только если совпадают с сохранёнными, иначе `409 skill_version_immutable`; обратный переход статуса — `invalid_status_transition` |
| POST | `/skills/{ref}:invoke` | `skills.invoke` | вызов `{inputs, idempotencyKey?, taskId?, runId?, approvalId?}` → `201` новый, `200` повтор ключа |
| GET | `/skill-invocations/{id}` | `skills.invoke` или `skills.execute` | вызов (видит authority и исполнитель) |
| POST | `/skill-invocations:claim` | `skills.execute` | взять вызов `{protocols, localEntrypoints, httpOrigins, mcpEndpoints, audiences, sessionId?, leaseSeconds?, invocationId?}` → `200 {invocation, skill}` или `204` |
| POST | `/skill-invocations/{id}:heartbeat` | `skills.execute` | продлить lease `{fencingToken, leaseSeconds?}` |
| POST | `/skill-invocations/{id}:complete` | `skills.execute` | результат `{fencingToken, output, cost?}`; `output` перепроверяется по схеме |
| POST | `/skill-invocations/{id}:fail` | `skills.execute` | неудача `{fencingToken, error: {code, message?, retryable?, details?}}` |
| POST | `/skill-invocations/{id}:cancel` | authority вызова или `org.manage` | отменить `{reason?}` |

Порядок проверок `:invoke`:

1. право `skills.invoke`, версия существует;
2. повтор `idempotencyKey` с теми же `inputs` от того же principal возвращает
   существующий вызов, иначе `409 idempotency_key_reuse`;
3. версия вызываема (`409 skill_not_invocable`, `details.reason`: `disabled`,
   `no_contract`, `protocol_not_invocable`);
4. при `idempotency: required` ключ обязателен
   (`400 idempotency_key_required`);
5. `inputs` проверяются по схеме (`400 invalid_skill_inputs`,
   `details.errors[].path`);
6. `runId` должен принадлежать вызывающему и быть в статусе `running`;
7. `requiredPermissions` контракта проверяются на workspace задачи
   (`403 skill_permission_denied`), эффективная политика инструментов прогона —
   `403 tool_not_authorized` или `403 child_grant_exceeded`;
8. `external_write` требует одобренного gate-approval на той же
   нетерминальной задаче, который ещё не использовался для этой версии
   (`409 approval_already_used`), или основания `execution` (тип задачи
   закрепил эту версию, прогон в статусе `running`).

Успешный `:complete` при `taskId` создаёт артефакт `skill_result`. Подробнее
о контракте скилла — в [skill-sdk](../sdk/skill-sdk.md).

### Операции {#operations}

| Метод | Путь | Право | Назначение |
|---|---|---|---|
| GET | `/operations/context-adapter` | `operations.read` | состояние доставки в память своего tenant'а |
| POST | `/operations/context-adapter/{tenantId}:redrive` | `operations.manage` | снять парковку и повторить ту же позицию `{reason}`; чужой tenant — `404` |
| POST | `/operations/context-adapter/{tenantId}:rebuild` | `operations.manage` | отмотать курсор `{cursor?, reason}`; только назад, иначе `422 cursor_must_not_advance` |
| POST | `/operations/journal:archive` | `operations.manage` | перенести подтверждённую историю в архив `{beforeSeconds?, maxEvents?}` |
| POST | `/operations/journal:prune` | `operations.manage` | физически удалить архив `{beforeSeconds?, maxEvents?}` — **данные теряются** |

```bash
curl -s -X POST https://platform.example.com/api/v1/operations/journal:archive \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"beforeSeconds": 2592000, "maxEvents": 50000}'
```

Горизонт архивации ограничен минимумом consumer-курсоров и самым старым
недоставленным outbox-событием. Если consumer-курсоров нет совсем, ответ —
`409 retention_blocked_by_consumer`. Минимальный возраст события задаёт
`CP_JOURNAL_RETENTION_MIN_AGE_SECONDS` (30 суток). Процедуры описаны в
[Резервное копирование](../operations/backup.md) и
[Мониторинг и здоровье](../operations/monitoring.md).

## Пагинация событий {#events-pagination}

Курсор журнала непрозрачен (`ec1_…`) и выдаётся в порядке `(tx_id, sequence)`
под стабильным горизонтом. Подписка с выданного курсора получит всё, что
закоммитится позже: незавершённые транзакции сортируются строго после любой
выданной позиции. Каждое событие несёт `sequence`, `type`, `entityType`,
`entityId`, `actorId`, `sessionId`, `correlationId`, `requestId`,
`traceRunId`, `payload`, `occurredAt` и `cursor`. Каталог типов событий — в
статье [События](events.md).

## SDK

Официальный клиент — пакет `control-plane-client` (модуль
`control_plane_client`, класс `ControlPlaneClient`). Он сам выставляет
`Idempotency-Key` на логический вызов, обновляет IAM-токен и разбирает
конверт ошибок в исключения. См. [Клиенты сервисов](../sdk/clients.md).

## См. также

- [Авторизация и права](authorization.md)
- [Харнесс-протокол](harness-protocol.md)
- [Конфигурация](configuration.md)
- [Коды ошибок](../reference/errors.md)
- [Права и scopes](../reference/permissions.md)
