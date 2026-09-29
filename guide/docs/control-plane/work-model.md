# Модель работы

Статья описывает, как в Control Plane организована работа: tenant, иерархия
workspaces, проекты с шаблонами и конфигурацией, задачи (work items) с
полями, датами, требованиями и связями, а также выборки задач с фильтрами и
сортировкой. Она нужна всем, кто заводит структуру платформы или
интегрирует внешние системы с задачами ядра.

## Иерархия сущностей

```text
Tenant
└── Workspace (дерево; slug уникален среди соседей)
    ├── Project Profile (0..1 на workspace)
    ├── Principals (члены, роли, capabilities, skills)
    ├── Goals
    └── Tasks
         ├── тип (Task type, закреплённая версия)
         ├── статус = ключ + системная категория
         ├── custom fields, плановые даты
         ├── requirements (roles / capabilities / skills)
         ├── relations (parent | blocks | depends_on | spawned_by | related_to)
         ├── comments (с историей правок)
         ├── claims → runs → checkpoints, actions, artifacts
         └── approvals
```

Дерево **одно**: `Workspace` — единственная иерархия, а проект — это профиль,
привязанный к workspace отношением один-к-одному. Принадлежность задачи
проекту не хранится, а вычисляется из дерева при чтении.

## Tenant

Tenant — граница изоляции данных. Любая сущность принадлежит ровно одному
tenant'у; составные внешние ключи вида `(tenant_id, …)` делают
межтенантные ссылки невозможными на уровне базы, а обращение к чужому
объекту отвечает `404` — так же, как к несуществующему.

Tenant создаётся одноразовым вызовом `POST /api/v1/bootstrap`, защищённым
токеном `CP_BOOTSTRAP_TOKEN`: он заводит tenant, первого principal-администратора
и его credential, а также системные справочники (системный тип задачи `task`,
системный тип workspace `generic`). Повторный вызов даёт
`409 already_bootstrapped`. Обычно bootstrap выполняет скрипт развёртывания —
см. [Bootstrap](../getting-started/bootstrap.md).

## Workspaces

Workspace — узел дерева, в котором живут задачи, цели, члены и роли.

| Поле | Описание |
|---|---|
| `slug` | `^[a-z0-9][a-z0-9-]*$`, 2–63 символа, уникален среди детей одного родителя |
| `name`, `description` | Отображаемые имя и описание |
| `parentId` | Родитель; `null` — корень |
| `typeId` / `typeKey` | Тип узла; не указан — системный тип tenant'а |
| `customFields` | Поля, проверяемые по `fieldSchema` типа |
| `status` | `active` или `archived` |

Операции:

```bash
# Создать workspace
curl -s -X POST "$CP/workspaces" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"slug": "platform", "name": "Platform team", "typeKey": "team"}'

# Дерево целиком (один рекурсивный запрос)
curl -s "$CP/workspaces/tree?includeProjects=true" -H "Authorization: Bearer $TOKEN"

# Переместить под другого родителя (циклы запрещены)
curl -s -X POST "$CP/workspaces/<workspace-id>:move" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"newParentId": "<parent-id>"}'
```

- `PATCH /workspaces/{id}` требует `If-Match: "workspace-<version>"`.
- `:archive` требует отсутствия активных детей
  (`422 workspace_has_active_children`); в архивном workspace нельзя
  создавать задачи (`422 workspace_archived`).
- `:move` в собственное поддерево отклоняется (`422 workspace_cycle`) и
  перепроверяет governance перемещаемого поддерева
  (`422 governance_weakened`, откат целиком).
- Члены: `POST /workspaces/{id}/members`, `GET …/members`,
  `POST …/members/{principalId}:remove`.

Права: `workspaces.read` на чтение, `workspaces.manage` на изменения.

### Типы workspaces

Workspace Type — справочник tenant'а: `key`, `displayName`, `fieldSchema`
(JSON Schema 2020-12 для `customFields` узла) и `allowedChildTypes` —
какие типы допустимы детьми. У каждого tenant'а есть системный тип `generic`,
разрешающий любых детей. Правило «родитель — ребёнок» проверяется при
создании, перемещении и смене типа под тем же per-tenant lock, что и прочие
структурные мутации.

```bash
curl -s -X POST "$CP/workspace-types" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "key": "portfolio",
    "displayName": "Portfolio",
    "allowedChildTypes": ["project", "team"]
  }'
```

`POST /workspace-types/{id}:archive` отклоняется, пока тип используется
(`422 workspace_type_in_use`).

## Проекты

Проект — это **профиль** (`project_profiles`), привязанный к workspace.
Родитель проекта не хранится: это ближайший предок-workspace, у которого
тоже есть профиль.

```text
Tenant
└── Workspace (portfolio)
    ├── Workspace (project)  + Project Profile     ← проект A
    │   ├── Workspace (workstream)                 ← принадлежит A
    │   └── Workspace (project) + Project Profile  ← проект B, вложен в A
    └── Workspace (team)
```

### Шаблоны проектов

Project Template версионируется и **неизменяем**: `POST /project-templates`
создаёт следующую версию ключа, а триггер базы разрешает единственную
мутацию — `active → deprecated`. Проект ссылается на точную версию, поэтому
его поля и статус всегда проверяются по той схеме, под которой были записаны.

Шаблон несёт `fieldSchema`, `lifecycleSchema`, `defaultConfig`,
`defaultViews`, `governanceSchema` и `memoryDefaults`.

### Lifecycle проекта

Статусы пользовательские, решения системные: каждый статус шаблона
отображается в одну из пяти категорий — `planned`, `active`, `paused`,
`terminal_success`, `terminal_cancelled`. Ядро ветвится только по категории.
Смена статуса — `POST /projects/{id}:transition` с `If-Match` и только по
объявленному ребру; событие `project.status_changed`.

!!! note "Категории проекта и задачи различаются"
    У проекта есть `paused`, у задачи — `blocked` и `backlog`. Это разные
    словари поверх одного механизма разбора lifecycle; подробнее о задачах —
    в [Типах задач и статусах](task-types.md).

### Конфигурация проекта

- `POST /projects/{id}/config-revisions` добавляет ревизию (append-only) и
  **не** активирует её.
- `POST /projects/{id}/config-revisions/{n}:activate` с `If-Match` делает её
  единственным авторитетным указателем.
- `GET /projects/{id}/effective-config` возвращает сложенную конфигурацию и
  provenance по каждому ключу верхнего уровня.

Порядок сложения детерминирован: defaults шаблона → разрешённые settings
предков (от корня к родителю) → активная ревизия → overlay профиля.
`settings` и `memory` сливаются рекурсивно (массивы и скаляры заменяются
целиком), `views` заменяются полностью, `governance` сворачивается операцией
«строже»: потомок может только ужесточить ограничения.

Права: `projects.read` / `projects.manage`, `project_templates.read` /
`project_templates.manage`.

## Задачи (work items)

### Поля задачи

| Поле | Тип | Описание |
|---|---|---|
| `id` | UUID | Идентификатор |
| `publicId` | строка | Человекочитаемый номер вида `TASK-000123`, уникален в tenant'е. Везде, где путь принимает `{task_ref}`, подходит и UUID, и `publicId` |
| `title` | строка ≤ 500 | Не пустой |
| `description` | строка | Произвольный текст |
| `typeId`, `typeKey`, `typeVersion` | — | Закреплённая версия [типа задачи](task-types.md) |
| `status` | строка ≤ 64 | Ключ статуса из lifecycle типа |
| `systemStatusCategory` | enum | `backlog`, `active`, `blocked`, `terminal_success`, `terminal_cancelled`; выводится из ключа, клиентом не задаётся |
| `priority` | enum | `critical`, `high`, `medium` (по умолчанию), `low` |
| `ownerId`, `assigneeId` | UUID | Principal'ы tenant'а |
| `workspaceId` | UUID | Workspace задачи (может быть `null`) |
| `projectId` | UUID | Вычисляется из дерева при чтении, не хранится |
| `customFields` | объект | Проверяется по `fieldSchema` версии типа |
| `startDate`, `dueDate` | ISO-8601 | Плановые даты |
| `goalId`, `origin`, `acceptance`, `evidence` | — | Граф работы, см. [Цели, приёмка и evidence](goals-and-evidence.md) |
| `version` | int | Версия для `If-Match` |
| `claimEpoch`, `activeClaimId` | — | Fencing и текущий claim, см. [Исполнение](execution.md) |
| `createdBy`, `createdAt`, `updatedAt`, `completedAt` | — | Аудит |

### Создание

```bash
curl -s -X POST "$CP/tasks" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "title": "Подготовить отчёт о нагрузке",
    "typeKey": "task",
    "priority": "high",
    "workspaceId": "<workspace-id>",
    "assigneeId": "<principal-id>",
    "dueDate": "2026-10-01T12:00:00Z",
    "customFields": {},
    "requirements": {"roles": ["analyst"], "capabilities": [], "skills": []}
  }'
```

Правила создания:

- без `typeId` / `typeKey` задача получает системный тип `task`; `typeKey`
  без `typeVersion` резолвится в новейшую `active` версию ключа;
- `status` по умолчанию — `initialStatus` типа. Явно можно указать только
  начальный статус или статус категории `backlog`, иначе
  `422 invalid_status`: задача не может родиться «в работе» без claim;
- статус вне lifecycle типа — `422 status_not_in_lifecycle`;
- `parentTask` (UUID или `publicId`) в той же транзакции создаёт связь
  `parent` и выставляет `origin.kind = "parent"`;
- `workspaceId` должен указывать на активный workspace; право `tasks.write`
  проверяется на этом workspace.

Ответ — `201` с телом задачи. Номер `publicId` выдаётся транзакционно из
счётчика tenant'а, коллизии исключены.

### Изменение

`PATCH /tasks/{ref}` требует `If-Match: "task-<version>"`. Если у задачи
есть живой claim, запрос обязан нести `claimId` и `fencingToken` этого
claim — иначе `409 task_claimed` (подробности в [Исполнении](execution.md)).

```bash
curl -s -X PATCH "$CP/tasks/TASK-000123" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H 'If-Match: "task-4"' \
  -d '{"status": "blocked", "dueDate": null, "priority": "critical"}'
```

| Поле в PATCH | Семантика |
|---|---|
| `title`, `description`, `priority`, `status` | `null` запрещён (`422 invalid_field`) |
| `status` | Только по объявленному ребру lifecycle; переход в `terminal_success` идёт через `:complete`, а не PATCH |
| `customFields` | Заменяет документ **целиком**; `null` запрещён, очистка — `{}` |
| `startDate`, `dueDate` | `null` очищает дату; новое значение проверяется против другого конца интервала |
| `ownerId`, `assigneeId`, `workspaceId`, `goalId` | `null` снимает значение |
| `requirements` | Заменяет набор требований; `null` запрещён, очистка — пустой объект |
| `acceptance`, `evidence` | Заменяют список целиком; `null` запрещён |
| `origin` | Отсутствует в контракте: происхождение неизменяемо (`400 invalid_request`) |

Пустой PATCH — `422 empty_update`. Каждый успешный PATCH увеличивает
`version` и пишет событие `task.updated` со списком изменённых полей;
при смене статуса в событии есть `fromStatus`, `status` и
`systemStatusCategory`.

### Завершение

`POST /tasks/{ref}:complete` с `If-Match` переводит задачу в
`completionStatus` её типа, освобождает claim и проставляет `completedAt`.
Подробности и ограничения — в [Типах задач](task-types.md) и
[Исполнении](execution.md).

## Custom fields

Custom fields — поля, которые tenant объявляет сам в `fieldSchema` типа
задачи (JSON Schema draft 2020-12).

- Проверка идёт по схеме **той версии типа, которую закрепила задача**, а не
  новейшей: тип, под которым задача создана, — её контракт.
- Схема может ссылаться только на себя (`$ref` вида `#…`); внешние ссылки
  отклоняются `422 invalid_json_schema`.
- Документ ограничен 64 КиБ, глубиной 20 и 5 000 узлами.
- Нарушение схемы — `422 custom_fields_invalid` со списком ошибок и
  JSON-путями.
- Ключи, похожие на секреты (`password`, `token`, `apiKey`, `secret`,
  `credential`, `authorization` и т. п.), отклоняются
  `422 secret_material_rejected`. Для ссылок на секреты используйте ключ
  `secretRef`.
- В журнал событий содержимое custom fields не попадает — только факт
  изменения (`"customFields": true`).

Пример типа с полями и задачи под ним:

```json
{
  "key": "incident",
  "displayName": "Incident",
  "fieldSchema": {
    "type": "object",
    "properties": {
      "severity": {"type": "string", "enum": ["sev1", "sev2", "sev3"]},
      "service": {"type": "string", "maxLength": 100}
    },
    "required": ["severity"],
    "additionalProperties": false
  }
}
```

```json
{"title": "Рост ошибок 5xx", "typeKey": "incident",
 "customFields": {"severity": "sev2", "service": "billing"}}
```

## Плановые даты

`startDate` и `dueDate` — типизированные колонки `timestamptz`, а не custom
fields: по ним нужны индексы, фильтры и сортировка «ближайшие первыми».

- Время без часового пояса читается как UTC.
- `startDate` позже `dueDate` — `422 invalid_planned_dates` (база проверяет
  то же самое).
- При изменении одного конца интервала новое значение сверяется с
  сохранённым другим концом.

## Требования и eligibility

`requirements` задачи — списки ролей, capabilities и skills, **все**
обязательные для того, кто захватывает задачу:

```json
{"requirements": {"roles": ["reviewer"], "capabilities": ["python"], "skills": ["repo.search@1.2.0"]}}
```

Skill указывается как `name` или `name@version` (точная версия). Неизвестное
требование — `422 unknown_requirement`. Требования **не дают** API-прав:
они определяют eligibility — кто вообще может взять задачу. Захват разрешён
только при одновременном выполнении четырёх условий:

```text
API permission tasks.claim ∧ eligibility (требования) ∧ readiness (зависимости) ∧ concurrency (claim, fencing)
```

Текущие требования задачи — `GET /tasks/{ref}/requirements`; диагностика
«почему я не могу взять задачу» — `GET /tasks/{ref}/claimability` (см.
[Исполнение](execution.md)). Подробнее о ролях и capabilities — в
[Авторизации и правах](authorization.md).

## Связи задач

Связь направленная: `from --type--> to`.

| Тип | Смысл | Влияет на исполнение |
|---|---|---|
| `parent` | `from` — подзадача `to` | Проверяется ацикличность |
| `blocks` | `from` должна завершиться до захвата `to` | Да: `to` не готова, пока `from` не в `terminal_success` |
| `depends_on` | `from` нельзя захватить, пока `to` не завершена | Да: `from` не готова, пока `to` не в `terminal_success` |
| `spawned_by` | `from` создана как следствие `to` | Используется каскадом отмены child runs и выражениями исходов approval |
| `related_to` | Свободная ассоциация | Нет |

```bash
# TASK-000124 зависит от TASK-000123
curl -s -X POST "$CP/tasks/TASK-000124/relations" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"toTask": "TASK-000123", "type": "depends_on"}'

# Все связи задачи (обе стороны)
curl -s "$CP/tasks/TASK-000124/relations" -H "Authorization: Bearer $TOKEN"

# Удалить связь
curl -s -X DELETE "$CP/tasks/TASK-000124/relations/<relation-id>" \
  -H "Authorization: Bearer $TOKEN"
```

- Для `parent`, `blocks`, `depends_on` ядро проверяет ацикличность под
  per-tenant advisory lock: цикл — `422 dependency_cycle`.
- Повтор существующей связи — `409 relation_exists`; связь задачи с собой —
  `422 invalid_relation`.
- Готовность считается по **категории**: пререквизит выполнен только в
  `terminal_success`.

!!! warning "Отменённая зависимость продолжает блокировать"
    Пререквизит в категории `terminal_cancelled` **не** считается выполненным:
    зависимая задача остаётся неготовой (`409 task_not_ready`), пока связь не
    удалят. Это сознательное поведение — отмена предпосылки требует решения
    человека, а не молчаливого разблокирования.

## Выборки задач

`GET /tasks` — постраничный список с фильтрами. Все фильтры применяются до
пагинации, поэтому страницы не пропускают и не дублируют записи.

| Параметр | Описание |
|---|---|
| `status` | Ключ статуса |
| `systemStatusCategory` | Категория — предпочтительный фильтр, если важен смысл, а не подпись |
| `typeKey` | Ключ типа задачи |
| `priority` | Приоритет |
| `ownerId`, `assigneeId` | Principal |
| `workspaceId` + `includeDescendants=true` | Workspace (и его поддерево) |
| `projectId` + `includeSubprojects=true` | Проект (разворачивается в множество workspaces) |
| `startFrom`, `startTo`, `dueFrom`, `dueTo` | Включающие границы по датам; задачи без даты под такой фильтр не попадают |
| `goalId` | Задачи, привязанные к цели |
| `sort` | `createdAt` (по умолчанию, новые первыми), `startDate`, `dueDate` |
| `limit`, `cursor` | Пагинация (по умолчанию 50, максимум 200) |

```bash
# Открытые задачи workspace и его поддерева, ближайший дедлайн первым
curl -s "$CP/tasks?workspaceId=<workspace-id>&includeDescendants=true&systemStatusCategory=active&sort=dueDate" \
  -H "Authorization: Bearer $TOKEN"

# Просроченные на конец месяца
curl -s "$CP/tasks?dueTo=2026-09-30T23:59:59Z&systemStatusCategory=active" \
  -H "Authorization: Bearer $TOKEN"
```

Особенности сортировки по датам:

- «ближайшие первыми», задачи без даты — в хвосте, тай-брейк по `id`;
- курсор привязан к порядку, под которым выдан: применённый к другому
  `sort` — `422 invalid_cursor`;
- неизвестное значение `sort` — `422 invalid_sort`.

Ответ:

```json
{
  "items": [
    {
      "id": "…", "publicId": "TASK-000123", "title": "…",
      "typeKey": "task", "typeVersion": 1,
      "status": "todo", "systemStatusCategory": "active",
      "priority": "high", "workspaceId": "…", "projectId": "…",
      "dueDate": "2026-10-01T12:00:00Z", "version": 4, "…": "…"
    }
  ],
  "nextCursor": "…"
}
```

!!! tip "Discovery для исполнителей"
    Для поиска работы исполнителю лучше подходит
    `GET /work/available`: он отдаёт только то, что вызывающий может взять
    прямо сейчас (eligible, ready, без живого claim и без gate), и поддерживает
    `assignedToMe=true`. Выдача рекомендательная — авторитетен только сам
    claim. Архивный проект новую работу не выдаёт. См. [Исполнение](execution.md).

## Комментарии

Обсуждение задачи — тред комментариев с append-only историей правок. Он
описан вместе с артефактами в [Артефактах и комментариях](artifacts.md).

## См. также

- [Типы задач и статусы](task-types.md)
- [Цели, приёмка и evidence](goals-and-evidence.md)
- [Исполнение — claims и runs](execution.md)
- [Авторизация и права](authorization.md)
- [События](events.md) — какие события пишет каждая операция.
