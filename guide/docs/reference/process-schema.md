# Схема языка процессов

Справочник полей языка пакетов процессов: вид каталога `Process`,
производственный календарь `Calendar` и тесты пакета `*.test.yaml`. Таблицы
построены из JSON Schema `packages/schema/v1` и повторяют её поле в поле.
Статья для авторов пакетов; как этим пользоваться, объясняют
[Процессы](../processes/index.md), [Выражения](../processes/expressions.md) и
[Тесты пакета](../processes/package-tests.md).

!!! note "Схема — первая ступень проверки"
    Схема проверяет форму описания. Вторую ступень — типы выражений,
    неизвестные поля данных, достижимость шагов, ссылки на типы задач и
    скиллы, пробелы таблиц решений — выполняет ядро при проверке пакета
    (см. [Тесты пакета](../processes/package-tests.md#check)).

## Процесс (`kind: Process`)

<!-- generated:schema-process -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `packages/schema/v1/object.schema.json`.

### `processSpec` { #schema-processspec }

Процесс (TAI-ADR-0054, CP-ADR-0074): кейс со стадиями и блоками исполнения, данные по схеме, выражения CEL, проекция в память. Исполняет ядро

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `version` | `integer` | да | Версия определения: опубликованная версия неизменяема |
| `displayName` | `displayName` | да |  |
| `description` | `string` |  |  |
| `workspaceId` | `string` |  |  |
| `identity` | [объект](#schema-processspec-identity) |  | От чьего имени действует процесс: описание агента вида service или agent |
| `owner` | [`assignChain`](#schema-assignchain) |  | Владелец процесса — ему адресуются задачи о процессе: расхождение с регламентом, ошибки экземпляров (TAI-ADR-0054 п.5, амендмент 2026-09-27). Не обязателен; проверка пакета предупреждает, если его нет |
| `calendar` | `typeKey` |  | Календарь по умолчанию для cal.* |
| `data` | `jsonSchema` | да | JSON Schema данных экземпляра; {$ref: &lt;файл пакета&gt;} раскрывает cp_packages |
| `start` | [объект](#schema-processspec-start) | да |  |
| `correlate` | array of [объект](#schema-processspec-correlate-item) |  |  |
| `stages` | array of [`processStage`](#schema-processstage) | да |  |
| `onEvent` | array of [объект](#schema-processspec-onevent-item) |  |  |
| `timers` | [`processTimers`](#schema-processtimers) |  |  |
| `decisions` | array of [`decisionTable`](#schema-decisiontable) |  |  |
| `governedBy` | [`governedBy`](#schema-governedby) |  |  |
| `memory` | [`memoryProjection`](#schema-memoryprojection) |  |  |
| `retrospective` | [объект](#schema-processspec-retrospective) |  | Разбор закрытого дела: агент предлагает уроки, человек подтверждает (TAI-ADR-0054 Р18) |
| `migrations` | array of [объект](#schema-processspec-migrations-item) |  |  |

### `processSpec.identity` { #schema-processspec-identity }

От чьего имени действует процесс: описание агента вида service или agent

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `agent` | `slug` | да |  |

### `processSpec.start` { #schema-processspec-start }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `on` | [`processTrigger`](#schema-processtrigger) | да |  |
| `key` | [`cel`](#schema-cel) | да | Ключ экземпляра: повтор события с тем же ключом — correlate, а не новый экземпляр |
| `set` | [`celMap`](#schema-celmap) |  |  |

### `processSpec.correlate[]` { #schema-processspec-correlate-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `on` | [`processTrigger`](#schema-processtrigger) | да |  |
| `key` | [`cel`](#schema-cel) | да |  |
| `set` | [`celMap`](#schema-celmap) |  |  |
| `do` | [`blocks`](#schema-blocks) |  |  |

### `processSpec.onEvent[]` { #schema-processspec-onevent-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `on` | [`processTrigger`](#schema-processtrigger) | да |  |
| `do` | [`blocks`](#schema-blocks) | да |  |

### `processSpec.retrospective` { #schema-processspec-retrospective }

Разбор закрытого дела: агент предлагает уроки, человек подтверждает (TAI-ADR-0054 Р18)

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `skill` | `string` |  | По умолчанию `process.retrospective@1`. |
| `taskType` | `typeKey` | да |  |
| `assign` | [`assignChain`](#schema-assignchain) | да |  |
| `appliesTo` | array of `string` |  | Виды сущностей, к которым привязываются уроки |
| `when` | [`cel`](#schema-cel) |  |  |

### `processSpec.migrations[]` { #schema-processspec-migrations-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `from` | `integer` | да |  |
| `to` | `integer` | да |  |
| `policy` | `pin` \| `migrate` | да |  |
| `map` | map → [`processElementId`](#schema-processelementid) |  |  |

### `processStage` { #schema-processstage }

Стадия кейса (CMMN): вход и выход по сторожам, вехи, обязательная и необязательная работа

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | да |  |
| `displayName` | `displayName` |  |  |
| `entry` | [`cel`](#schema-cel) |  | Сторож входа; stage.&lt;id&gt;.completed, milestone.&lt;id&gt; и data доступны в выражении |
| `exit` | [`cel`](#schema-cel) |  |  |
| `repeatable` | `boolean` |  |  |
| `governedBy` | [`governedBy`](#schema-governedby) |  |  |
| `steps` | [`blocks`](#schema-blocks) | да |  |
| `discretionary` | array of [`processStep`](#schema-processstep) |  | Работа, которую человек добавляет по решению |
| `milestones` | array of [объект](#schema-processstage-milestones-item) |  |  |
| `timers` | [`processTimers`](#schema-processtimers) |  |  |

### `processStage.milestones[]` { #schema-processstage-milestones-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | да |  |
| `when` | [`cel`](#schema-cel) | да |  |

### `processStep` { #schema-processstep }

Шаг процесса: ровно один вид (human, approve, call, decide, recall, remember, listen, wait, set, raise, compensate, fork, try, do, suspend, resume, complete) плюс общие поля

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | да |  |
| `displayName` | `displayName` |  |  |
| `when` | [`cel`](#schema-cel) |  | Сторож: шаг выполняется, только если истинно |
| `input` | [объект](#schema-processstep-input) |  |  |
| `output` | [объект](#schema-processstep-output) |  | Запись результата шага (step.result) в данные экземпляра |
| `export` | [объект](#schema-processstep-export) |  |  |
| `governedBy` | [`governedBy`](#schema-governedby) |  |  |
| `onCompensate` | [`blocks`](#schema-blocks) |  | Компенсация сделанного шага: выполняется при compensate в обратном порядке |
| `human` | [объект](#schema-processstep-human) |  |  |
| `approve` | [объект](#schema-processstep-approve) |  |  |
| `call` | [объект](#schema-processstep-call) |  |  |
| `decide` | [объект](#schema-processstep-decide) |  |  |
| `recall` | [объект](#schema-processstep-recall) |  | Запрос к памяти через ядро; ответ — событие журнала (детерминированный replay) |
| `remember` | [объект](#schema-processstep-remember) |  | Запись в память наблюдением ядра от identity процесса, со ссылкой на дело |
| `listen` | [объект](#schema-processstep-listen) |  | Ожидание первого из событий (отложенный выбор); timeout — таймер |
| `wait` | [`durationOrCel`](#schema-durationorcel) |  |  |
| `set` | [`celMap`](#schema-celmap) |  |  |
| `raise` | [`processError`](#schema-processerror) |  |  |
| `compensate` | = `all` или array of [`processElementId`](#schema-processelementid) |  | Выполнить onCompensate сделанных шагов в обратном порядке |
| `fork` | [объект](#schema-processstep-fork) |  |  |
| `try` | [объект](#schema-processstep-try) |  |  |
| `do` | [`blocks`](#schema-blocks) |  |  |
| `suspend` | [объект](#schema-processstep-suspend) |  |  |
| `resume` | [объект](#schema-processstep-resume) |  |  |
| `complete` | [объект](#schema-processstep-complete) |  |  |

Ровно одно из: `human`, `approve`, `call`, `decide`, `recall`, `remember`, `listen`, `wait`, `set`, `raise`, `compensate`, `fork`, `try`, `do`, `suspend`, `resume`, `complete`.

### `processStep.input` { #schema-processstep-input }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `from` | [`cel`](#schema-cel) |  |  |

### `processStep.output` { #schema-processstep-output }

Запись результата шага (step.result) в данные экземпляра

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `as` | [`celMap`](#schema-celmap) |  |  |

### `processStep.export` { #schema-processstep-export }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `as` | [`celMap`](#schema-celmap) |  |  |

### `processStep.human` { #schema-processstep-human }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `taskType` | `typeKey` | да |  |
| `title` | [`cel`](#schema-cel) |  |  |
| `form` | [`processForm`](#schema-processform) |  |  |
| `assign` | [`assignChain`](#schema-assignchain) | да |  |
| `due` | [`durationOrCel`](#schema-durationorcel) |  |  |
| `escalations` | array of [`escalation`](#schema-escalation) |  |  |
| `context` | [`stepContext`](#schema-stepcontext) |  |  |

### `processStep.approve` { #schema-processstep-approve }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `taskType` | `typeKey` |  |  |
| `approvers` | [`assignChain`](#schema-assignchain) | да |  |
| `mode` | `parallel` \| `sequential` |  | По умолчанию `parallel`. |
| `quorum` | `all` \| `any` или объект `{atLeast}` или объект `{percent}` | да |  |
| `earlyDecision` | `boolean` |  | По умолчанию `true`. |
| `separationOfDuties` | [`cel`](#schema-cel) |  | CEL → список principal, которым голосовать нельзя; проверяет ядро при решении |
| `due` | [`durationOrCel`](#schema-durationorcel) |  |  |
| `onDue` | `approve` \| `reject` \| `escalate` |  |  |
| `escalations` | array of [`escalation`](#schema-escalation) |  |  |
| `context` | [`stepContext`](#schema-stepcontext) |  |  |

### `processStep.call` { #schema-processstep-call }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `skill` | `string` |  |  |
| `agent` | `slug` |  |  |
| `process` | `typeKey` |  |  |
| `input` | [`celMap`](#schema-celmap) |  |  |
| `timeout` | [`durationOrCel`](#schema-durationorcel) |  |  |
| `context` | [`stepContext`](#schema-stepcontext) |  |  |

Ровно одно из: `skill`, `agent`, `process`.

### `processStep.decide` { #schema-processstep-decide }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `table` | [`processElementId`](#schema-processelementid) | да |  |
| `input` | [`celMap`](#schema-celmap) |  |  |

### `processStep.recall` { #schema-processstep-recall }

Запрос к памяти через ядро; ответ — событие журнала (детерминированный replay)

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `anchors` | array of [`memoryAnchor`](#schema-memoryanchor) | да |  |
| `traverse` | [`memoryTraverse`](#schema-memorytraverse) |  |  |
| `query` | [`cel`](#schema-cel) |  | Текст смыслового добора |
| `kinds` | array of `string` |  |  |
| `limit` | `integer` |  |  |
| `timeout` | [`duration`](#schema-duration) |  |  |
| `onTimeout` | [`blocks`](#schema-blocks) |  |  |

### `processStep.remember` { #schema-processstep-remember }

Запись в память наблюдением ядра от identity процесса, со ссылкой на дело

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `entity` | [объект](#schema-processstep-remember-entity) |  |  |
| `facts` | [`celMap`](#schema-celmap) |  | Имя факта дела → значение |

Ровно одно из: `facts`, `entity`.

### `processStep.remember.entity` { #schema-processstep-remember-entity }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | `string` | да |  |
| `key` | [`cel`](#schema-cel) | да |  |
| `name` | [`cel`](#schema-cel) |  |  |
| `text` | [`cel`](#schema-cel) |  |  |
| `links` | array of [объект](#schema-processstep-remember-entity-links-item) |  |  |

### `processStep.remember.entity.links[]` { #schema-processstep-remember-entity-links-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `rel` | `string` | да |  |
| `kind` | `string` | да |  |
| `key` | [`cel`](#schema-cel) | да |  |

### `processStep.listen` { #schema-processstep-listen }

Ожидание первого из событий (отложенный выбор); timeout — таймер

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `any` | array of [объект](#schema-processstep-listen-any-item) | да |  |
| `timeout` | [`durationOrCel`](#schema-durationorcel) |  |  |
| `onTimeout` | [`blocks`](#schema-blocks) |  |  |

### `processStep.listen.any[]` { #schema-processstep-listen-any-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `on` | [`processTrigger`](#schema-processtrigger) | да |  |
| `do` | [`blocks`](#schema-blocks) |  |  |

### `processStep.fork` { #schema-processstep-fork }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `mode` | `all` \| `compete` |  | По умолчанию `all`. |
| `branches` | array of [объект](#schema-processstep-fork-branches-item) | да |  |

### `processStep.fork.branches[]` { #schema-processstep-fork-branches-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | да |  |
| `do` | [`blocks`](#schema-blocks) | да |  |

### `processStep.try` { #schema-processstep-try }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `do` | [`blocks`](#schema-blocks) | да |  |
| `retry` | [объект](#schema-processstep-try-retry) |  |  |
| `catch` | array of [объект](#schema-processstep-try-catch-item) |  |  |

### `processStep.try.retry` { #schema-processstep-try-retry }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `limit` | `integer` | да |  |
| `delay` | [`duration`](#schema-duration) |  |  |
| `backoff` | `constant` \| `exponential` |  |  |
| `maxDelay` | [`duration`](#schema-duration) |  |  |
| `on` | array of `string` |  | Типы ошибок для повтора; по умолчанию все |

### `processStep.try.catch[]` { #schema-processstep-try-catch-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `errors` | [объект](#schema-processstep-try-catch-item-errors) |  |  |
| `as` | `string` |  |  |
| `do` | [`blocks`](#schema-blocks) | да |  |

### `processStep.try.catch[].errors` { #schema-processstep-try-catch-item-errors }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` |  |  |
| `status` | `integer` |  |  |

### `processStep.suspend` { #schema-processstep-suspend }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `reason` | [`cel`](#schema-cel) |  |  |

### `processStep.resume` { #schema-processstep-resume }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `reason` | [`cel`](#schema-cel) |  |  |

### `processStep.complete` { #schema-processstep-complete }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `outcome` | `string` | да |  |

### `processTimers` { #schema-processtimers }

Граничные таймеры: срабатывают, пока стадия (процесс) открыта; at от данных пересчитывается при их изменении

Значение: array of [объект](#schema-processtimers-item).

### `processTimers[]` { #schema-processtimers-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | да |  |
| `at` | [`durationOrCel`](#schema-durationorcel) | да |  |
| `interrupting` | `boolean` |  | По умолчанию `false`. |
| `do` | [`blocks`](#schema-blocks) | да |  |

### `decisionTable` { #schema-decisiontable }

Таблица решений (DMN по смыслу). Ячейка условия: '-' (любое), литерал, список 'a,b', диапазон '[a..b)'

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | да |  |
| `displayName` | `displayName` |  |  |
| `hitPolicy` | `first` \| `unique` \| `collect` | да |  |
| `governedBy` | [`governedBy`](#schema-governedby) |  |  |
| `inputs` | array of [объект](#schema-decisiontable-inputs-item) | да |  |
| `outputs` | array of [объект](#schema-decisiontable-outputs-item) | да |  |
| `rules` | array of [объект](#schema-decisiontable-rules-item) | да |  |

### `decisionTable.inputs[]` { #schema-decisiontable-inputs-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | да |  |
| `expr` | [`cel`](#schema-cel) | да |  |
| `type` | `string` \| `number` \| `boolean` \| `date` \| `timestamp` |  |  |

### `decisionTable.outputs[]` { #schema-decisiontable-outputs-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | да |  |
| `type` | `string` \| `number` \| `boolean` \| `date` \| `duration` \| `object` \| `array` |  |  |

### `decisionTable.rules[]` { #schema-decisiontable-rules-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `when` | map → `string` \| `number` \| `boolean` | да |  |
| `then` | `object` | да |  |
| `note` | `string` |  |  |
| `governedBy` | [`governedBy`](#schema-governedby) |  |  |

### `memoryProjection` { #schema-memoryprojection }

Проекция дела в граф памяти (TAI-ADR-0054 Р15): доставляется событиями, в граф идут только объявленные поля

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `case` | [объект](#schema-memoryprojection-case) | да |  |
| `facts` | [`celMap`](#schema-celmap) |  | Имя факта дела → значение; изменение закрывает прежний факт сроком действия |
| `entities` | array of [объект](#schema-memoryprojection-entities-item) |  |  |
| `documents` | [объект](#schema-memoryprojection-documents) |  |  |

### `memoryProjection.case` { #schema-memoryprojection-case }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | `string` |  | По умолчанию `case`. |
| `key` | [`cel`](#schema-cel) | да |  |
| `title` | [`cel`](#schema-cel) |  |  |

### `memoryProjection.entities[]` { #schema-memoryprojection-entities-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | `string` | да |  |
| `key` | [`cel`](#schema-cel) | да |  |
| `name` | [`cel`](#schema-cel) |  |  |
| `rel` | `string` | да |  |
| `when` | [`cel`](#schema-cel) |  |  |
| `many` | `boolean` |  | key даёт список: по сущности на элемент |

### `memoryProjection.documents` { #schema-memoryprojection-documents }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `artifacts` | array of `typeKey` |  |  |

### `stepContext` { #schema-stepcontext }

Профиль контекста исполнителя шага из памяти (TAI-ADR-0054 Р16): явные связи первыми, смысловой добор с пометкой inferred

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `anchors` | array of [`memoryAnchor`](#schema-memoryanchor) | да |  |
| `traverse` | [`memoryTraverse`](#schema-memorytraverse) |  |  |
| `semantic` | `boolean` |  | Добор по смыслу (inferred); по умолчанию true |
| `budgetTokens` | `integer` |  |  |

### `memoryAnchor` { #schema-memoryanchor }

Якорь обхода графа: узел дела экземпляра или сущность по естественному ключу (CEL от данных)

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `case` | = `true` |  |  |
| `kind` | `string` |  |  |
| `key` | [`cel`](#schema-cel) |  |  |
| `via` | `string` |  |  |

Ровно одно из: `case`, `key` + `kind`.

### `memoryTraverse` { #schema-memorytraverse }

Шаги обхода от якорей — та же форма, что traverse в contextSchema (CP-ADR-0064)

Значение: array of [объект](#schema-memorytraverse-item).

### `memoryTraverse[]` { #schema-memorytraverse-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `relation` | `string` | да |  |
| `direction` | `in` \| `out` \| `both` |  |  |
| `depth` | `integer` |  |  |
| `limit` | `integer` |  |  |
| `from` | `anchors` \| `previous` |  |  |

### `processTrigger` { #schema-processtrigger }

Источник события: событие журнала ядра или наблюдение. where — фильтр CEL над event

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `event` | `string` |  |  |
| `observation` | `string` |  |  |
| `source` | `string` |  |  |
| `where` | [`cel`](#schema-cel) |  |  |

Ровно одно из: `event`, `observation`.

### `assignee` { #schema-assignee }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `principal` | `envOrUuid` |  |  |
| `role` | `slug` |  |  |
| `agent` | `slug` |  |  |
| `expr` | [`cel`](#schema-cel) |  | CEL → id principal, agent:&lt;key&gt; или role:&lt;slug&gt; |

Ровно одно из: `principal`, `role`, `agent`, `expr`.

### `assignChain` { #schema-assignchain }

Кандидаты по порядку: берётся первый разрешимый

Значение: array of [`assignee`](#schema-assignee).

### `escalation` { #schema-escalation }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `after` | = `due` или [`durationOrCel`](#schema-durationorcel) | да | due — в момент срока; длительность — после срока |
| `action` | `remind` \| `reassign` \| `notify` \| `raise` | да |  |
| `to` | [`assignChain`](#schema-assignchain) |  |  |
| `error` | [`processError`](#schema-processerror) |  |  |

### `processError` { #schema-processerror }

Ошибка в форме RFC 7807

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` | да |  |
| `status` | `integer` |  |  |
| `detail` | [`cel`](#schema-cel) |  |  |

### `processForm` { #schema-processform }

Форма шага: JSON Schema данных и uischema JSON Forms представления

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `schema` | `jsonSchema` | да |  |
| `uischema` | `object` |  |  |

### `governedBy` { #schema-governedby }

Регламенты базы знаний, которым подчиняется элемент (TAI-ADR-0054 Р17): естественный ключ документа памяти и, при необходимости, пункт

Значение: array of [объект](#schema-governedby-item).

### `governedBy[]` { #schema-governedby-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `document` | `string` | да |  |
| `section` | `string` |  |  |

### `blocks` { #schema-blocks }

Последовательность шагов (блок do)

Значение: array of [`processStep`](#schema-processstep).

### `durationOrCel` { #schema-durationorcel }

Длительность ISO 8601 или выражение CEL, дающее момент времени (timestamp) или длительность

Значение: [`duration`](#schema-duration) или объект `{at}`.

### `duration` { #schema-duration }

Длительность ISO 8601, например P3D, PT4H

Значение: `string`.

### `cel` { #schema-cel }

Выражение CEL в профиле taimen/1 (CP-ADR-0075): переменные data, event, step, task, instance; функции cal.*; без текущего времени. Типы и лимит стоимости проверяет ядро

Значение: `string`.

### `celMap` { #schema-celmap }

Путь в данных экземпляра → выражение CEL

Значение: map → [`cel`](#schema-cel).

### `processElementId` { #schema-processelementid }

Стабильный id элемента процесса: на него ссылаются раскладка схемы, карты миграции, журнал и граф памяти. Переименование — только картой migrations

Значение: `string`.
<!-- /generated:schema-process -->

## Календарь (`kind: Calendar`)

<!-- generated:schema-calendar -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `packages/schema/v1/object.schema.json`.

### `calendarSpec` { #schema-calendarspec }

Производственный календарь (TAI-ADR-0054 Р6): выходные по умолчанию, праздники и переносы по годам

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `displayName` | `displayName` | да |  |
| `timezone` | `string` | да |  |
| `weekend` | array of `integer` |  | Дни недели ISO: 1 — понедельник. По умолчанию `[6, 7]`. |
| `years` | array of [объект](#schema-calendarspec-years-item) | да |  |

### `calendarSpec.years[]` { #schema-calendarspec-years-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `year` | `integer` | да |  |
| `provisional` | `boolean` |  | Год ещё не утверждён: результаты cal.* помечаются «предварительно» |
| `source` | `string` |  |  |
| `holidays` | array of `string` (date) |  |  |
| `workdays` | array of `string` (date) |  | Перенесённые рабочие дни, выпавшие на выходные |
| `shortDays` | array of `string` (date) |  |  |
<!-- /generated:schema-calendar -->

## Тест пакета (`tests/*.test.yaml`)

<!-- generated:schema-test -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `packages/schema/v1/test.schema.json`.

### `test` { #schema-test }

Файл &lt;имя&gt;.test.yaml в каталоге tests/ пакета. Прогоняет ядро (POST /packages:test) тем же движком, что живой прогон, в песочнице: задачи, approvals и таймеры — в памяти, скиллы, агенты и память — заглушки, проверенные по схемам каталога, время виртуальное. Побочных эффектов нет.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `$schema` | `string` |  |  |
| `process` | `string` | да | Ключ процесса пакета |
| `version` | `integer` |  | По умолчанию — версия в пакете |
| `name` | `string` | да |  |
| `description` | `string` |  |  |
| `given` | [объект](#schema-test-given) |  |  |
| `mocks` | [объект](#schema-test-mocks) |  |  |
| `steps` | array of [`testStep`](#schema-teststep) | да |  |
| `coverage` | [объект](#schema-test-coverage) |  |  |

### `test.given` { #schema-test-given }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `clock` | `string` (date-time) |  | Начальное виртуальное время |
| `data` | `object` |  | Начальные данные экземпляра (без события старта) |
| `stage` | `string` |  | Начать с открытой стадии |
| `fromInstance` | `string` |  | Только пробный прогон на стенде: состояние копируется из живого экземпляра |
| `calendar` | `string` |  | Ключ календаря вместо календаря процесса |
| `principals` | map → array of `string` |  | Роль → вымышленные principal теста (для назначений и разделения обязанностей) |

### `test.mocks` { #schema-test-mocks }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `skills` | map → array of [`mockAnswer`](#schema-mockanswer) |  | name@version → ответы по порядку вызовов (или по when); выход проверяется по схеме скилла из каталога |
| `agents` | map → array of [`mockAnswer`](#schema-mockanswer) |  |  |
| `recall` | array of [`mockAnswer`](#schema-mockanswer) |  | Ответы памяти шагам recall; step — id шага, when — CEL над запросом |

### `test.coverage` { #schema-test-coverage }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `minimum` | `number` |  | Порог покрытия элементов процесса этим тестом, % |

### `mockAnswer` { #schema-mockanswer }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `step` | `string` |  |  |
| `when` | `string` |  | CEL над input вызова |
| `output` | любое |  |  |
| `error` | [объект](#schema-mockanswer-error) |  |  |
| `timeout` | = `true` |  |  |

Ровно одно из: `output`, `error`, `timeout`.

### `mockAnswer.error` { #schema-mockanswer-error }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` | да |  |
| `status` | `integer` |  |  |
| `detail` | `string` |  |  |

### `testStep` { #schema-teststep }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `emit` | [объект](#schema-teststep-emit) |  |  |
| `advance` | `string` |  | Сдвиг виртуального времени (ISO 8601, P3D) или до момента: until:&lt;id таймера&gt; |
| `complete` | [объект](#schema-teststep-complete) |  |  |
| `approve` | [объект](#schema-teststep-approve) |  |  |
| `expect` | [объект](#schema-teststep-expect) |  |  |

Ровно одно из: `emit`, `advance`, `complete`, `approve`, `expect`.

### `testStep.emit` { #schema-teststep-emit }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `event` | `string` |  |  |
| `observation` | `string` |  |  |
| `source` | `string` |  |  |
| `payload` | `object` |  |  |

Ровно одно из: `event`, `observation`.

### `testStep.complete` { #schema-teststep-complete }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `step` | `string` | да |  |
| `by` | `string` |  | principal теста или agent:&lt;key&gt; |
| `output` | `object` |  | Данные формы или результат агента; проверяются по схеме формы |
| `cancel` | = `true` |  |  |

### `testStep.approve` { #schema-teststep-approve }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `step` | `string` | да |  |
| `by` | `string` | да |  |
| `decision` | `approve` \| `reject` | да |  |
| `expectRefused` | `string` |  | Код отказа ядра, например separation_of_duties_violation |

### `testStep.expect` { #schema-teststep-expect }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `stages` | map → `open` \| `completed` \| `skipped` \| `not_started` |  |  |
| `milestones` | array of `string` |  |  |
| `tasks` | array of [объект](#schema-teststep-expect-tasks-item) |  |  |
| `timers` | array of [объект](#schema-teststep-expect-timers-item) |  |  |
| `data` | `object` |  | Путь в данных → ожидаемое значение |
| `events` | array of `string` |  | Типы событий process.* с последнего expect |
| `memory` | [объект](#schema-teststep-expect-memory) |  |  |
| `outcome` | `string` |  |  |
| `status` | `running` \| `suspended` \| `completed` \| `failed` \| `cancelled` |  |  |
| `error` | `string` |  |  |
| `noSideEffects` | = `true` |  |  |

### `testStep.expect.tasks[]` { #schema-teststep-expect-tasks-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `step` | `string` |  |  |
| `status` | `string` |  |  |
| `assignee` | `string` |  |  |
| `due` | `string` |  |  |

### `testStep.expect.timers[]` { #schema-teststep-expect-timers-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | `string` |  |  |
| `at` | `string` |  |  |
| `provisional` | `boolean` |  |  |

### `testStep.expect.memory` { #schema-teststep-expect-memory }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `recalled` | array of `string` |  |  |
| `remembered` | array of `object` |  |  |
<!-- /generated:schema-test -->

## См. также

- [Процессы](../processes/index.md)
- [Выражения](../processes/expressions.md)
- [Тесты пакета](../processes/package-tests.md)
- [Пакеты каталога](../control-plane/catalog-packages.md#processes)
