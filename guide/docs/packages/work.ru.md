# Работа: типы задач и роли

Как пакет описывает работу: типы задач с их жизненным циклом, полями,
инструкциями, исходами решений, работой после завершения, приёмкой, входами и
выходами; роли и capabilities, типы артефактов, шаблоны проектов и типы
пространств работы. Страница для автора пакета: что писать в файлы и как это
тестировать. Полная грамматика каждого поля — в статьях Control Plane, на
которые ведут ссылки.

## Что в пакете, а что в установке

| В пакете | В установке и у администратора |
|---|---|
| какие бывают задачи, их статусы, поля и исходы | в каком пространстве работы они появляются (переменные) |
| роли и их назначение агентам пакета | кто из людей держит роль |
| типы артефактов и их схема | лимиты хранилища установки |
| шаблоны проектов, типы пространств работы | само дерево пространств работы и проекты |

Пакет ничего не знает о людях конкретного tenant'а. Роль — это адрес («кто
согласует доступ»), а кто за ним стоит, решает администратор установки
назначением роли principal'у.

## Типы задач { #task-types }

Тип задачи (`TaskType`, папка `task-types/`) — словарь и правила одного вида
работы. Задачи ядра, которые заводят процессы, правила, исходы решений и люди,
всегда принадлежат какой-то версии типа.

```yaml
apiVersion: taimen.ai/v1
kind: TaskType
key: access-review
spec:
  displayName: Access review
  description: A decision on an access request
  fieldSchema: {…}          # поля задачи — customFields
  lifecycleSchema: {…}      # статусы, переходы, служебные статусы
  instructions: |           # текст для исполнителя
    …
  execution: {…}            # задачу исполняет один вызов скилла
  approvalSchema: {…}       # что ядро делает после решения по задаче
  completionSchema: {…}     # что ядро заводит после завершения задачи
  acceptance: […]           # критерии приёмки у всех задач типа
  artifactSchema: {…}       # входы и выходы — артефакты
  contextSchema: {…}        # профиль контекста задачи из памяти
```

Обязательны только `displayName` и `lifecycleSchema`.

### Жизненный цикл

Названия статусов принадлежат пакету, решения ядро принимает по **категории**
статуса: `backlog`, `active`, `blocked`, `terminal_success`,
`terminal_cancelled`.

```yaml
  lifecycleSchema:
    statuses:
      - {key: todo, category: active, displayName: To do}
      - {key: in_progress, category: active, displayName: In progress}
      - {key: done, category: terminal_success, displayName: Done}
      - {key: cancelled, category: terminal_cancelled, displayName: Cancelled}
    transitions:
      - {from: todo, to: [in_progress, done, cancelled]}
      - {from: in_progress, to: [todo, done, cancelled]}
    initialStatus: todo
    claimStatus: in_progress      # при взятии в работу; не терминальный
    releaseStatus: todo           # при освобождении; не терминальный
    completionStatus: done        # при успешном завершении; terminal_success
```

`package-sdk add task-type <ключ>` пишет именно такой цикл из четырёх
статусов. Статус можно назвать как угодно — ядро будет смотреть на категорию.
Переходы объявляются явно: смена статуса и действия исходов идут только по
объявленным рёбрам. Подробно — в [Типах задач и статусах](../control-plane/task-types.md).

### Поля и инструкции

- `fieldSchema` — JSON Schema 2020-12 полей задачи (`customFields`): их
  форма у человека и вход исполнителя.
- `instructions` — Markdown до 16 КиБ: что сделать исполнителю и как сдать
  результат. Это слой типа задачи в инструкциях исполнителя, после общих
  правил платформы и проекта; ядро проверяет размер и отсутствие секретов.
- `execution: {skill, version, inputs?}` — задачу типа исполняет один вызов
  скилла; вход по умолчанию — `$.customFields`.

### Решения: `approvalSchema`

Решение человека по задаче — gate-approval. Тип объявляет, что ядро сделает
после решения, закрытым словарём действий: `ensureWork`, `completeTask`,
`comment`, `transition`, `invokeSkill` с реакциями `onSuccess` и `onFailure`.
Исполняется только гейт `default` с исходами `approved` и `rejected`.

```yaml
  approvalSchema:
    gates:
      default:
        outcomes:
          approved:
            - invokeSkill:
                skill: access.grant@1
                inputs:
                  requestId: $.task.customFields.requestId!
                  resource: $.task.customFields.resource!
                onSuccess:
                  - completeTask: {}
                onFailure:
                  - comment: {body: "Access was not granted: $.invocation.error.message"}
          rejected:
            - comment: {body: "Access request $.task.customFields.requestId denied"}
            - transition: {status: cancelled}
```

- Строки — выражения `$.task…`, `$.spawnedBy…`, `$.approval…`, а в реакциях
  на вызов — `$.invocation…`. Суффикс `!` делает значение обязательным: пустое
  значение не превращается, например, в вызов без входа.
- Закрывайте задачу в `onSuccess`, а не рядом с `invokeSkill`: одобрение —
  основание для внешней записи, только пока задача открыта.
- Грамматику проверяет ядро при публикации версии типа:
  `422 invalid_approval_schema` с путём до ошибки.

Словарь действий и выражения — в [Approvals](../control-plane/approvals.md).

**Кто решает гейт.** `approvalSchema` объявляет только исходы. Адресата —
держателя роли (`requiredRoleId`) или конкретного principal'а
(`assignedPrincipalId`) — задаёт тот, кто запрашивает gate-approval на задаче:

| Кто запрашивает | Как адресует |
|---|---|
| исполнитель задачи (человек или агент) | `POST /api/v1/approvals` с `gate: true` и адресатом (право `approvals.manage`), см. [Approvals](../control-plane/approvals.md) |
| правило пакета | действие `request_decision`: `fields.approverRole` — UUID роли (в пакете — переменная вида `role`) или `fields.approver` — principal |
| исход или `completionSchema` другого типа | `ensureWork.requestApproval.assignee` — только principal (выражение `$.task…` или UUID), роль здесь не адресуется |

Закрепить за типом «гейт этого типа решает роль X» пакет пока не может:
адресата выбирает запрашивающий. Пока такого поля нет, пишите адресата в
`instructions` типа — «попросите одобрения у роли `purchase-approver`» — или
заводите задачу правилом с `request_decision`. Сценарий типа задачи право
решающего тоже не сверяет: `approve.by` проходит у любого principal'а, даже
без роли в `given.principals`.

### После завершения: `completionSchema`

Что ядро заводит, когда задача типа завершена успешно — кем бы она ни была
завершена. Словарь уже: `ensureWork` (с `customFields`, `relation` и
`requestApproval`) и `comment`; выражения — `$.task…` и `$.spawnedBy…`.

```yaml
  completionSchema:
    onComplete:
      when: ["$.task.customFields.resource"]   # все непусты — иначе ничего
      actions:
        - comment: {body: "Access review closed"}
```

`when` необязателен: без него действия исполняются при каждом завершении.

### Приёмка: `acceptance`

Критерии, которые проходит каждая задача типа на стадии проверки, до
критериев самой задачи. Виды: `deterministic`, `external_state`, `human`,
`llm_judge`; `when` — пути `$.task…`, при пустых
критерий пропускается.

```yaml
  acceptance:
    - key: decided
      kind: human
      description: An approver decided on the request
```

- Задача не может заменить критерий типа своим с тем же `key` (`422`).
- `deterministic` со скиллом внешней записи допустим, только если раньше
  стоит решение человека (`human` или `llm_judge`).

Подробно — в [Приёмке типа](../control-plane/task-types.md#type-acceptance) и
[Стадии проверки](../control-plane/goals-and-evidence.md#verification-stage).

### Входы и выходы: `artifactSchema`

Какие артефакты задача типа получает на вход от связанных задач и какие
обязана сдать:

```yaml
  artifactSchema:
    outputs:
      - {key: grant, type: access-grant, required: false}
```

Элемент — `key`, `type` (ключ типа артефакта), `required`, `mediaTypes`
(сужение типа артефакта). Без обязательного входа задачу нельзя взять в работу
(`409 input_missing`); обязательный выход — детерминированный критерий стадии
проверки. Подробно — во [Входах и выходах](../control-plane/task-types.md#artifact-schema).

### Контекст: `contextSchema`

Профиль контекста задачи из памяти: якоря, обход графа, срез по времени,
бюджет токенов. Грамматику проверяет ядро. Подробно — в
[Контексте задачи и памяти](../control-plane/context.md).

### Версии типа

Опубликованная версия типа неизменяема. Если файл отличается от новейшей
активной версии, публикуется новая, а прежние активные переводятся в
`deprecated`. Задача помнит версию, с которой создана: её исходы и приёмка
исполняются по той версии, а не по новой.

## Тесты типа задачи { #tests }

Тест с `subject: taskType` проверяет исходы решений, приёмку и работу после
завершения тем же кодом ядра, что на стенде, в транзакции, которая
откатывается. Скиллы подменяются ответами из `mocks`.

```yaml
# tests/access-review-approved.test.yaml
subject: taskType
taskType: access-review
name: an approved request is granted and completed
given:
  task:
    assignee: alice
    customFields: {requestId: A-3, resource: billing}
  principals: {access-approver: [bob]}
mocks:
  skills:
    access.grant@1:
      - output: {grantId: G-1}
steps:
  - approve: {decision: approved, by: bob}
  - expect:
      invokeSkill:
        - {skill: access.grant@1, inputs: {requestId: A-3, resource: billing}}
      status: {category: terminal_success}
```

```yaml
# tests/access-review-rejected.test.yaml
subject: taskType
taskType: access-review
name: a rejected request is cancelled with a comment
given:
  task:
    customFields: {requestId: A-4, resource: billing}
steps:
  - approve: {decision: rejected, by: bob}
  - expect:
      invokeSkill: []
      comments: ["A-4 denied"]
      status: {category: terminal_cancelled}
```

| Шаг | Что делает |
|---|---|
| `approve: {decision, by?, gate?, comment?}` | решение по гейту (`approved` или `rejected`); исполняются исходы |
| `verify: {check, result, output?}` | итог критерия приёмки типа (`passed` или `failed`) |
| `complete: {output?}` | успешное завершение задачи — исполняется `completionSchema` |
| `expect` | `ensureWork`, `invokeSkill`, `status {key?, category?}`, `comments` (подстроки), `noSideEffects` |

Отчёт `package-sdk test` показывает покрытие типа: пройденные исходы
(включая реакции `onSuccess`/`onFailure`), действия завершения и исходы
критериев приёмки, и перечисляет непокрытые.

```text
покрытие типа задачи access-review v1 (тестов 2): outcomes 3/4, completion 1/1, acceptance 1/2
   не пройдены (outcomes): default/approved/0/onFailure
   не пройдены (acceptance): acceptance/decided:failed
```

!!! note "Переменные в тестах"
    Если объекты пакета используют `${ПЕРЕМЕННЫЕ}`, тесту нужны их значения:
    файл `--env` (по умолчанию `.env`), окружение или `given.variables` в
    самом тесте. Иначе тест завершается ошибкой `unresolved_install_variable`.
    Исключение — переменные видов `workspace`, `principal` и `role`: их
    песочница заменяет своими тестовыми строками (см. [Тесты
    пакета](testing.md#subjects)).

## Роли { #roles }

Роль (`Role`, папка `roles/`) — адрес работы и решений уровня tenant'а:
процесс назначает шаг на роль, approval адресуется роли, а исполнитель с этой
ролью может взять задачу с таким требованием.

```yaml
apiVersion: taimen.ai/v1
kind: Role
key: access-approver
spec:
  name: Access approver
  description: Decides on access requests
```

- Ключ — slug роли. Роль из пакета-зависимости видна пакету через
  `requires`.
- Агентам своего пакета роль назначается в описании агента:
  `identity.roles: [access-approver]`. Людям — администратором установки.
- В тестах держателей роли задаёт `given.principals: {<роль>: [<вымышленные
  principal>]}`.
- Роли не дают прав API: они определяют, кто может взять задачу и решить
  approval (см. [Организационную модель](../control-plane/authorization.md#org-model)).

## Capabilities { #capabilities }

Capability (`Capability`, папка `capabilities/`) — способность исполнителя,
которую может требовать задача: «знает Python», «имеет доступ к каталогу».
Ключ — имя способности, `spec` — только `description`.

```yaml
apiVersion: taimen.ai/v1
kind: Capability
key: directory-admin
spec:
  description: Can change access rights in the directory service
```

Агенту своего пакета способность назначается в описании агента:
`identity.capabilities: [directory-admin]`. Capability только создаётся:
изменить описание существующей установка не может — расхождение будет
предупреждением.

## Типы артефактов { #artifact-types }

Тип артефакта (`ArtifactType`, папка `artifact-types/`) — форма результата,
который задачи сдают и передают друг другу.

```yaml
apiVersion: taimen.ai/v1
kind: ArtifactType
key: access-grant
spec:
  displayName: Access grant
  metadataSchema:
    type: object
    properties:
      grantId: {type: string}
    required: [grantId]
  mediaTypes: [application/json]
```

| Поле | Что задаёт |
|---|---|
| `metadataSchema` | JSON Schema `metadata` артефакта этого типа, до 16 КиБ |
| `mediaTypes` | допустимые media types содержимого; по умолчанию любой |
| `maxBytes` | лимит размера содержимого; не больше лимита установки |

Версии неизменяемы, как у типа задачи; на тип артефакта ссылается
`artifactSchema` типа задачи. Подробно — в
[Артефактах](../control-plane/artifacts.md#artifact-types).

## Шаблоны проектов { #project-templates }

Шаблон проекта (`ProjectTemplate`, папка `project-templates/`) задаёт поля
проекта (`fieldSchema`), его статусы (`lifecycleSchema` с категориями
`planned`, `active`, `paused`, `terminal_success`, `terminal_cancelled`),
настройки по умолчанию (`defaultConfig`, `defaultViews`), ограничения
исполнения (`governanceSchema`) и умолчания памяти (`memoryDefaults`).
Шаблон версионируется и неизменяем: проект ссылается на точную версию.
Подробно — в [Модели работы](../control-plane/work-model.md).

## Типы пространств работы { #workspace-types }

Тип пространства работы (`WorkspaceType`, папка `workspace-types/`) — вид
узла дерева пространств: `displayName`, поля узла (`fieldSchema`) и какие
типы допустимы детьми (`allowedChildTypes`).

```yaml
apiVersion: taimen.ai/v1
kind: WorkspaceType
key: department
spec:
  displayName: Department
  allowedChildTypes: [team]
```

Тип правится на месте. Архивный тип установка не восстанавливает — это
ошибка. Само дерево пространств работы пакет не создаёт: это топология
установки, её UUID приходят в пакет [переменными](anatomy.md#variables).

## Типичные проблемы

| Симптом | Причина | Что делать |
|---|---|---|
| `invalid_approval_schema` при проверке | гейт не `default`, неизвестное действие или выражение, переход не по объявленному ребру | исправить по пути в сообщении |
| `invokeSkill.skill: … cannot be invoked here (not_found)` | скилла нет в пакете и его `requires`, или тип не опубликован в песочнице из-за другой ошибки | объявить `Skill` в пакете или добавить пакет со скиллом в `requires` |
| тест: `unresolved_install_variable` | объект использует переменную, а значения нет | задать в `.env`, окружении или `given.variables` |
| задача не завершается после одобрения | `completeTask` стоит рядом с `invokeSkill`, а не в `onSuccess`, или нет ребра в `completionStatus` | перенести в `onSuccess`, объявить переход |
| задача шага не появилась, `intent_failed unknown_role` | у роли нет держателей в `given.principals`, и она не объявлена в пакете | объявить роль в пакете и задать держателей в тесте |

## См. также

- [Пакеты](index.md)
- [Анатомия пакета](anatomy.md) — ключи, версии, переменные
- [Правила в пакете](rules.md) — кто заводит задачи по фактам
- [Процессы в пакете](processes.md) — задачи шагов дела
- [Типы задач и статусы](../control-plane/task-types.md)
- [Approvals](../control-plane/approvals.md)
- [Цели, приёмка и evidence](../control-plane/goals-and-evidence.md)
