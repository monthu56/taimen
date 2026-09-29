# Подписки на события

Как сервис или интеграция подписывается на журнал событий Control Plane:
фильтры по типам и workspace, право на workspace, курсоры, WebSocket как
сигнал пробуждения, версии данных событий и каталог. Во второй части —
Python SDK потребителя `control_plane_client.events`, который берёт на себя
хранение курсора, дедупликацию и повторы. Статья для разработчиков
потребителей: сервисов уведомлений, мостов, ретрансляторов вебхуков. Модель
журнала и полный список типов — в статье [События](events.md).

## Подписка — это фильтр чтения

Серверных подписок с состоянием у ядра нет. Потребитель читает тот же журнал
`GET /api/v1/events` (или `WS /api/v1/events/ws`) с фильтрами и сам хранит
курсор. Фильтр сужает выдачу, но не меняет ни порядок, ни смысл курсора:
отфильтрованный читатель продолжает с `nextCursor` так же, как читатель всего
журнала. Обоснование — CP-ADR-0068.

```bash
# Все события approvals и проваленные проверки в поддереве workspace
curl -s "$CP/events?types=approval.,task.verification_failed&workspaceId=<workspace-id>&limit=200" \
  -H "Authorization: Bearer $TOKEN"

# То же, продолжение с сохранённого курсора
curl -s "$CP/events?types=approval.&types=task.verification_failed&workspaceId=<workspace-id>&cursor=ec1_…" \
  -H "Authorization: Bearer $TOKEN"
```

| Параметр | Смысл |
|---|---|
| `types` | Префиксы типа. `approval.` — все события approvals, `task.verified` — этот тип (и все, что начинаются с этой строки). Повторяемый параметр и/или список через запятую, до 20 префиксов. Формат `^[a-z][a-z0-9_]*(\.[a-z0-9_]*)*$` |
| `workspaceId` | События этого workspace и всех его потомков. Поддерево вычисляется в момент чтения |
| `cursor`, `limit`, `tail`, `entityType`, `entityId` | Как в обычном чтении, см. [События](events.md); сочетаются с фильтрами |

| Ошибка | HTTP | Когда |
|---|---|---|
| `invalid_event_type_filter` | 422 | Префикс не в формате или их больше 20 |
| `not_found` | 404 | Workspace фильтра не существует |
| `permission_denied` | 403 | Нет `events.read` на workspace (или на tenant без `workspaceId`) |
| `invalid_request` | 400 | Неизвестный query-параметр |

### Право на workspace

- **С `workspaceId`** право `events.read` проверяется на ресурсе
  `workspace:<id>`. В режиме авторизации `policy` учитываются гранты на
  предках. Потребителю approvals одного подразделения не нужно право на весь
  tenant.
- **Без `workspaceId`** — право `events.read` на tenant, как раньше.
- События уровня tenant (principal'ы, ключи, bootstrap) под фильтром по
  workspace не видны.

### Workspace события

У каждого события в конверте есть `workspaceId`. Его заполняет ядро по
сущности события:

- собственный workspace сущности — у `task`, `approval`, `artifact`, `goal`,
  `rule`, `role`, `project` и самого `workspace`;
- иначе workspace задачи, к которой сущность относится, — у `run`, `claim`,
  `skill_invocation`, у approval или артефакта без собственного workspace;
- остальные события — уровня tenant (`workspaceId: null`).

Approval задачи живёт в workspace задачи: `workspaceId` в конверте, в
payload `approval.requested` и в проекции approval — одно и то же значение,
и держатели роли этого workspace — ровно те, кто может решить.

!!! note "События до появления фильтров"
    Журнал append-only. У событий, записанных до того, как ядро начало
    заполнять `workspaceId`, поле пусто, и фильтр по workspace их не видит.

### Курсор через отброшенные события

Страница, дошедшая до конца журнала, переносит `nextCursor` через события,
отброшенные фильтром, до позиции, стабильной на момент запроса. Читатель
редкого типа поэтому не пересканирует один и тот же хвост журнала при каждом
опросе. Курсор остаётся непрозрачным: храните последний полученный —
`cursor` обработанного события или `nextCursor` страницы — и передавайте его
обратно.

Порядок выдачи, гарантии курсора и ошибки курсора (`invalid_cursor`,
`cursor_below_journal_floor`) те же, что у нефильтрованного чтения, — см.
[Надёжный курсор](events.md).

## WebSocket как будильник

```text
WS /api/v1/events/ws?after=<cursor>&types=approval.&workspaceId=<workspace-id>
```

WebSocket принимает те же фильтры `types` и `workspaceId`. Сервер отдаёт
события после `after` и дальше — по мере коммитов. Но надёжный потребитель
**не обрабатывает кадры**: любой кадр только будит цикл, который читает
`GET /events` от сохранённого курсора. Источник истины один; кадр, потерянный
вместе с сокетом, стоит задержки, а не события.

Ошибки передаются кодом закрытия после установления соединения:

| Код | Причина | Повтор имеет смысл |
|---|---|---|
| `4401` | Нет или неверные credentials | После обновления токена |
| `4403` | Нет права `events.read` (на workspace фильтра или tenant) | Нет |
| `4404` | Workspace фильтра не существует | Нет |
| `4400` | Малформированный или неподдерживаемый курсор, неверный фильтр | Нет |
| `4503` | Решение об авторизации не получено (PDP недоступен) | Да |
| `1011` | Внутренняя ошибка сервера | Да |

Токен одного решения из канала (scope `control-plane:decide`) к WebSocket не
допускается.

## Версии данных и каталог

### `schemaVersion`

Конверт события несёт `schemaVersion` — версию схемы `payload` этого типа (у
старых событий — `1`). Правило эволюции:

- новая версия **только добавляет** поля: потребитель версии N читает N+1
  без изменений и игнорирует незнакомые поля;
- поле, которое меняет смысл или исчезает, — это **новый тип** события, а не
  новая версия;
- старые версии остаются в каталоге, пока журнал может хранить события под
  ними.

Ядро ставит текущую версию типа при записи и отказывается записать тип,
которого нет в каталоге. Каждое событие интеграционных тестов ядра
проверяется по JSON Schema своей пары (тип, версия).

### Каталог событий

Каталог генерируется из кода ядра (`make event-catalog` в репозитории
`control-plane`) в два файла: `docs/events/catalog.md` — таблица типов,
конверт и поля каждой версии, и `docs/events/catalog.json` — JSON Schema
2020-12 всех версий для валидации на стороне потребителя. Каталог нейтрален:
в нём только сущности ядра.

Пример — payload `approval.requested` версии 2 (поля v2 добавлены к v1):

| Поле | Версия | Смысл |
|---|---|---|
| `taskId`, `artifactId` | 1 | Предмет решения |
| `requiredRoleId` | 1 | Задан, если решает любой держатель роли |
| `assignedPrincipalId` | 1 | Задан, если решает один principal |
| `gate` | 1 | Gate держит claim и завершение задачи до решения |
| `workspaceId` | 2 | Workspace approval'а |
| `taskPublicId`, `taskTitle` | 2 | Что решается — без дочитывания задачи |
| `requestedBy` | 2 | Кто запросил |
| `comment` | 2 | Комментарий запроса |

У `approval.approved` и `approval.rejected` версии 2 добавлены `decisionBy`,
`comment` (комментарий решения или `null`) и `channel` — канал, через который
пришло решение (`telegram`), `null` для прямого вызова API. У
`approval.cancelled` v2 — `cancelledBy`. Текст `comment` в событии проходит
редакцию похожего на секрет материала (совпадение заменяется на
`[redacted]`) и обрезается до 1000 символов; полный текст остаётся в самом
approval.

### Держатели роли

Чтобы адресовать решение по роли, потребителю нужен список тех, кто вправе
решить. Ядро отдаёт его по тому же правилу, по которому проверяет право
решать:

```bash
curl -s "$CP/roles/<role-id>/principals?workspaceId=<workspace-id>" \
  -H "Authorization: Bearer $TOKEN"
```

Возвращаются principal'ы, которым роль назначена на уровне tenant или на этом
workspace либо его предке; без `workspaceId` — только назначения уровня
tenant. Элемент — `{id, kind, displayName, status}`, пагинация — как у прочих
списков. Статус principal'а не фильтруется: решает адресующий. Право —
`org.read` или `principals.read`.

## SDK потребителя: `control_plane_client.events` {#sdk}

SDK входит в пакет `control-plane-client` (см. [Клиенты сервисов](../sdk/clients.md)).
Обоснование — CP-ADR-0069. Ядро клиента остаётся на `httpx`, зависимости
потребителя — экстры:

```bash
uv add 'control-plane-client[events]'   # websockets + sqlalchemy[asyncio]
```

| Экстра | Что даёт |
|---|---|
| `[ws]` | Пробуждение по WebSocket; без него потребитель только опрашивает |
| `[sqlalchemy]` | Хранилище курсора в SQL (`control_plane_client.events.sqlalchemy`) |
| `[events]` | Оба |

Драйвер базы (`psycopg`, `asyncpg`, `aiosqlite`) ставит сам потребитель.

### Минимальный потребитель

```python
from control_plane_client import ControlPlaneClient
from control_plane_client.events import Event, EventConsumer
from control_plane_client.events.sqlalchemy import SqlAlchemyCursorStore
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine("postgresql+psycopg://…")
store = SqlAlchemyCursorStore(engine)


async def handler(event: Event) -> None:
    # Исключение — событие придёт снова; возврат — событие обработано.
    await notify(event["payload"])


async def main() -> None:
    await store.create_tables()  # или таблицы в миграции потребителя
    async with ControlPlaneClient(url, credential) as client:
        consumer = EventConsumer(
            client,
            ["approval.", "task.verification_failed"],
            workspace_id,          # None — весь tenant
            store,
            handler,
            name="notifications",
            start="latest",
        )
        await consumer.run()       # до consumer.stop() или отмены
```

### Параметры `EventConsumer`

`EventConsumer(client, types, workspace_id, cursor_store, handler, *, name, …)`:

| Параметр | По умолчанию | Смысл |
|---|---|---|
| `types` | — | Префиксы типа; пусто — все типы |
| `workspace_id` | — | Поддерево workspace; `None` — весь tenant (нужно `events.read` на tenant) |
| `cursor_store` | — | Где хранятся позиция и отметки обработанных событий |
| `handler` | — | `async (event) -> None`; событие — как в `GET /events` |
| `name` | обязателен | Ключ курсора в хранилище: одно имя — одна позиция |
| `start` | `"earliest"` | Только когда курсора ещё нет: `earliest` — весь доступный журнал, `latest` — после последнего подходящего события (курсор сохраняется сразу) |
| `poll_interval` | `30.0` | Период опроса, секунд; WebSocket будит раньше |
| `page_size` | `200` | Размер страницы `GET /events` |
| `websocket` | `True` | Держать WebSocket для пробуждения |
| `retry_initial`, `retry_max` | `1.0`, `60.0` | Пауза перед повтором упавшей страницы: удваивается от первой до второй |

Методы: `run()` — цикл до `stop()` или отмены; `stop()` — закончить событие в
руках и выйти; `wake()` — прочитать сейчас, не дожидаясь опроса; `drain()` —
прочитать всё доступное сейчас и вернуть число обработанных событий (для
задач по расписанию и тестов).

### Гарантии

- **Порядок** — порядок журнала; обработчик вызывается по одному событию.
- **Без потерь.** Курсор двигается только после обработки события. Упавший
  обработчик (`HandlerError`), сетевой сбой или `5xx` — страница читается
  заново с сохранённого курсора после паузы. Отбросить событие может только
  обработчик — вернувшись без исключения.
- **Без повторов.** Событие обрабатывается внутри единицы работы хранилища:
  отметка `event.id` и курсор события записываются вместе. Повторно
  доставленное событие пропускается.
- **Отказ в подписке** — `401`, `403`, `404`, `422` при чтении страницы —
  завершает `run()` исключением: повтор его не изменит.
- **WebSocket.** Кадры только будят цикл. После закрытия `4401` credential
  обновляется; после любого переподключения цикл читает один раз вне
  очереди. Без пакета `websockets` потребитель опрашивает раз в
  `poll_interval`.

!!! warning "Событие, на котором обработчик падает всегда"
    Такое событие останавливает потребителя на себе — с растущей паузой и
    предупреждением в логе. Это осознанный выбор «не терять». Если событие
    нельзя обработать в принципе (payload вне схемы), обработчик должен
    залогировать его и вернуться без исключения.

### Хранилища курсора

Протокол `CursorStore`:

| Метод | Смысл |
|---|---|
| `load(consumer)` | Сохранённый курсор или `None` |
| `handle(consumer, event_id, cursor)` | Асинхронный контекст-менеджер: входит с `False`, если событие уже обработано; на чистом выходе записывает отметку и курсор вместе; выход исключением не записывает ничего |
| `advance(consumer, cursor)` | Перенос курсора на `nextCursor` страницы (через отфильтрованные события) |

- **`MemoryCursorStore`** — в памяти процесса: тесты и потребители, которым
  можно начать сначала.
- **`SqlAlchemyCursorStore(engine, *, metadata=None, prefix="",
  dedup_retention=7 дней, prune_interval=600)`** — таблицы
  `<prefix>event_cursors` (потребитель → курсор) и `<prefix>handled_events`
  (потребитель × `event_id`, `handled_at`).
    - Событие — одна транзакция. Строки, которые обработчик пишет через
      `SqlAlchemyCursorStore.session()`, фиксируются вместе с отметкой и
      курсором или откатываются вместе с ними. Для эффектов в базе
      потребителя это «ровно один раз»; для внешних эффектов (сообщение в
      мессенджер) — «хотя бы один раз», передавайте `event.id` получателю как
      ключ идемпотентности.
    - Строка курсора блокируется `FOR UPDATE` на время события: два процесса
      с одним `name` не обработают событие оба. Внешние эффекты они всё равно
      могут задвоить — запускайте один процесс на имя.
    - Отметки старше `dedup_retention` удаляются при движении курсора, не
      чаще раза в `prune_interval` секунд: повторная доставка бывает рядом с
      курсором, а не на дни позади.
    - Схему создаёт миграция потребителя: передайте свой `MetaData` (Alembic
      `target_metadata`) или объявите таблицы через
      `cursor_tables(metadata, prefix=…)`; без миграций —
      `await store.create_tables()`.

### Экспорт в CloudEvents

`to_cloudevent(event, *, source=None)` превращает событие журнала в
CloudEvents 1.0 (структурный JSON) — для ретрансляции в вебхук или шину.
Журнал формат не меняет: это функция экспорта.

| CloudEvents | Из события |
|---|---|
| `specversion` | `1.0` |
| `id`, `type` | `id`, `type` |
| `time` | `occurredAt` |
| `subject` | `<entityType>/<entityId>` |
| `source` | аргумент `source` (URI установки, например `https://platform.example.com/tenants/<tenant-id>`); по умолчанию `/control-plane/tenants/<tenantId>` |
| `datacontenttype` | `application/json` |
| `data` | `payload` |
| расширения | `tenantid`, `workspaceid`, `entitytype`, `entityid`, `schemaversion`, `actorid`, `correlationid`, `causationid` — пустые опускаются |

```python
from control_plane_client.events import to_cloudevent

async def handler(event):
    await relay.post(json=to_cloudevent(event, source="https://platform.example.com/tenants/<tenant-id>"),
                     headers={"Idempotency-Key": event["id"]})
```

Схема `data` — версия `schemaversion` типа в каталоге событий.

### Простое чтение без хранилища

`ControlPlaneClient.list_events(cursor=…, types=…, workspace_id=…, tail=…)`
читает одну страницу с фильтрами, `follow_events(cursor=…)` — бесконечный
опрос без сохранения позиции и без дедупликации. Для надёжного потребителя
используйте `EventConsumer`.

## См. также

- [События](events.md) — модель события, курсор, WebSocket, полный каталог
  типов, хранение журнала.
- [Уведомления](../notifications/index.md) — сервис уведомлений, построенный
  на этом SDK.
- [Approvals](approvals.md) — события решений.
- [Авторизация и права](authorization.md) — `events.read` и режимы
  `authorize`.
- [Клиенты сервисов](../sdk/clients.md) — `control-plane-client`.
