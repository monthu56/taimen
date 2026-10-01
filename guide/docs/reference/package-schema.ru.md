# Схема пакета

Справочник полей всех файлов пакета: обёртка объекта, каждый вид каталога,
тесты пакета, фиксация источников `packages.lock` и план установки. Таблицы
построены из JSON Schema `package-sdk/schema/v1` и повторяют её поле в поле.
Статья для авторов пакетов; как этим пользоваться, объясняют [Анатомия
пакета](../packages/anatomy.md), [Процессы](../processes/index.md),
[Выражения](../processes/expressions.md) и [Тесты пакета](../packages/testing.md).

!!! note "Схема — первая ступень проверки"
    Схема проверяет форму описания. Вторую ступень — ссылки между объектами,
    типы выражений, неизвестные поля данных, достижимость шагов, пробелы
    таблиц решений — выполняют `package-sdk check` и валидаторы ядра (см.
    [Тесты пакета](../packages/testing.md)).

Подключить схему к редактору — строка в начале файла объекта:

```yaml
# yaml-language-server: $schema=<путь к schema/v1/object.schema.json>
```

Как читать таблицы: «Тип» — тип JSON или ссылка на определение ниже;
`array of` — массив, `map →` — объект с произвольными ключами; «Условия» —
поля, которые обязательны или меняют форму при значении другого поля.

## Обёртка объекта { #object }

Каждый файл объекта пакета — `package.yaml`, файлы видов каталога и установка — одна обёртка `apiVersion` + `kind` + `key` + `spec`. Тип ключа и форма `spec` зависят от вида (таблица «Условия»).

<!-- generated:schema-object -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `package-sdk/schema/v1/object.schema.json`.

### `object` { #schema-object }

Одна обёртка для манифеста и всех видов каталога: apiVersion + kind + key + spec. spec — тело запроса API control-plane в camelCase без поля идентичности. Схема проверяет форму; окончательную проверку делает ядро (и package-sdk check его валидаторами).

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `apiVersion` | = `taimen.ai/v1` | да |  |
| `kind` | `Package` \| `Installation` \| `ArtifactType` \| `TaskType` \| `ProjectTemplate` \| `WorkspaceType` \| `Role` \| `Capability` \| `Skill` \| `WorkRule` \| `Agent` \| `NotificationRule` \| `Process` \| `Calendar` \| `KnowledgePack` | да |  |
| `key` | `string` | да |  |
| `spec` | `object` | да |  |

Условия:

| Условие | Следствие |
|---|---|
| `kind` = `Package` | `key`: [`typeKey`](#schema-typekey); `spec`: [`packageSpec`](#schema-packagespec) |
| `kind` = `Installation` | `spec`: [`installationSpec`](#schema-installationspec) |
| `kind` = `ArtifactType` | `key`: [`typeKey`](#schema-typekey); `spec`: [`artifactTypeSpec`](#schema-artifacttypespec) |
| `kind` = `TaskType` | `key`: [`typeKey`](#schema-typekey); `spec`: [`taskTypeSpec`](#schema-tasktypespec) |
| `kind` = `ProjectTemplate` | `key`: [`typeKey`](#schema-typekey); `spec`: [`projectTemplateSpec`](#schema-projecttemplatespec) |
| `kind` = `WorkspaceType` | `key`: [`typeKey`](#schema-typekey); `spec`: [`workspaceTypeSpec`](#schema-workspacetypespec) |
| `kind` = `Role` | `key`: [`slug`](#schema-slug); `spec`: [`roleSpec`](#schema-rolespec) |
| `kind` = `Capability` | `spec`: [`capabilitySpec`](#schema-capabilityspec) |
| `kind` = `Skill` | `spec`: [`skillSpec`](#schema-skillspec) |
| `kind` = `WorkRule` | `key`: [`ruleKey`](#schema-rulekey); `spec`: [`workRuleSpec`](#schema-workrulespec) |
| `kind` = `Agent` | `key`: [`slug`](#schema-slug); `spec`: [`agentSpec`](#schema-agentspec) |
| `kind` = `NotificationRule` | `key`: [`ruleKey`](#schema-rulekey); `spec`: [`notificationRuleSpec`](#schema-notificationrulespec) |
| `kind` = `Process` | `key`: [`typeKey`](#schema-typekey); `spec`: [`processSpec`](#schema-processspec) |
| `kind` = `KnowledgePack` | `key`: `string`; `spec`: [`knowledge-pack`](#schema-knowledge-pack) |
| `kind` = `Calendar` | `key`: [`typeKey`](#schema-typekey); `spec`: [`calendarSpec`](#schema-calendarspec) |
<!-- /generated:schema-object -->

## Манифест пакета (`kind: Package`) { #package }

<!-- generated:schema-package -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `package-sdk/schema/v1/object.schema.json`.

### `packageSpec` { #schema-packagespec }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `version` | `string` | да | SemVer пакета |
| `displayName` | [`displayName`](#schema-displayname) | да |  |
| `description` | `string` |  |  |
| `requires` | array of [`typeKey`](#schema-typekey) или [объект `{package, version}`](#schema-packagespec-requires-item-2) |  | Пакеты, на объекты которых этот пакет ссылается: ключ (любая версия) или {package, version} с диапазоном SemVer |
| `engines` | map → [`semverRange`](#schema-semverrange) |  | Диапазоны версий компонентов, против которых пакет проверен, например {control-plane: "&gt;=0.9,&lt;0.11"}; check и plan отвергают несовместимую версию до записи |
| `variables` | map → [`packageVariable`](#schema-packagevariable) |  | Объявление каждой ${NAME} пакета. Использованная переменная обязана быть объявлена, объявленная — использована. Секретов в пакете нет: поля secret у переменной нет |
| `knowledge` | array of `string` |  | Онтологии (имя@мажор), на которые опираются процессы и правила пакета; check сверяет с recall/remember/memory процессов |
| `license` | `string` |  | Лицензия пакета (идентификатор SPDX) |
| `authors` | array of `string` |  |  |
| `homepage` | `string` |  |  |
| `renames` | array of [объект](#schema-packagespec-renames-item) |  | Явные переименования объектов (как moved в Terraform): план переносит объект, а не удаляет и создаёт |

### `packageSpec.requires[] (2)` { #schema-packagespec-requires-item-2 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `package` | [`typeKey`](#schema-typekey) | да |  |
| `version` | [`semverRange`](#schema-semverrange) |  |  |

### `packageSpec.renames[]` { #schema-packagespec-renames-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | `string` | да |  |
| `from` | `string` | да |  |
| `to` | `string` | да |  |

### `semverRange` { #schema-semverrange }

Диапазон версий: условия через запятую, все выполняются (&gt;=0.9,&lt;0.11); операторы &gt;=, &gt;, &lt;=, &lt;, =, ^, ~; без оператора — версия или префикс (1.2 = 1.2.x); * — любая

Значение: `string`.

### `packageVariable` { #schema-packagevariable }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `description` | `string` | да |  |
| `kind` | `url` \| `workspace` \| `project` \| `principal` \| `role` \| `string` \| `integer` | да | Вид значения: url — абсолютный URL; workspace\|project\|principal\|role — UUID, существующий на стенде (проверяет plan); integer — целое; string — любое |
| `required` | `boolean` |  | По умолчанию `true`. |
| `default` | `string` |  | Значение, если инсталляция не задала своё |
| `example` | `string` |  |  |
<!-- /generated:schema-package -->

## Установка (`kind: Installation`) { #installation }

<!-- generated:schema-installation -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `package-sdk/schema/v1/object.schema.json`.

### `installationSpec` { #schema-installationspec }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `packages` | array of [`packageSource`](#schema-packagesource) | да | Пакеты установки: ключ (каталог установки), {key, path} или {key, git, ref}; requires подтягиваются сами. Пусто — только системный тип task ядра |
| `packagesDir` | `string` |  | Каталог пакетов установки относительно файла установки; по умолчанию packages/ рядом с ним |
| `knowledge` | array of [объект](#schema-installationspec-knowledge-item) |  | Включение онтологий для пространств работы — топология, поэтому в установке; набор заменяет прежний целиком |
| `retire` | [объект](#schema-installationspec-retire) |  | Ключи, которые окружение выводит из оборота (все активные версии → deprecated) |

### `installationSpec.knowledge[]` { #schema-installationspec-knowledge-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `workspace` | `string` | да | ${ПЕРЕМЕННАЯ} установки или UUID |
| `packs` | array of `string` | да |  |
| `strict` | `boolean` |  | Строгий режим памяти: записи вне включённых видов отвергаются, а не принимаются как есть. По умолчанию `false`. |

### `installationSpec.retire` { #schema-installationspec-retire }

Ключи, которые окружение выводит из оборота (все активные версии → deprecated)

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `TaskType` | array of [`typeKey`](#schema-typekey) |  |  |
| `ProjectTemplate` | array of [`typeKey`](#schema-typekey) |  |  |
| `Agent` | array of [`slug`](#schema-slug) |  | Агент выводится из оборота: исполнитель остановлен, credential отозван, история сохранена |
| `NotificationRule` | array of [`ruleKey`](#schema-rulekey) |  | Правило уведомления выводится из оборота в сервисе уведомлений (:retire); отправленные уведомления остаются |
| `WorkRule` | array of [`ruleKey`](#schema-rulekey) |  | Правило вывода работы архивируется; заведённые им работы доживают |
| `Process` | array of [`typeKey`](#schema-typekey) |  | Процесс выводится маршрутом ядра :retire: новые экземпляры не стартуют, живые доживают |
| `Calendar` | array of [`typeKey`](#schema-typekey) |  | Календарь выводится, только если на него не ссылается активный процесс (calendar_in_use) |

### `packageSource` { #schema-packagesource }

Значение: [`typeKey`](#schema-typekey) или [объект `{key, path}`](#schema-packagesource-2) или [объект `{key, git, ref, path}`](#schema-packagesource-3).

### `packageSource (2)` { #schema-packagesource-2 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | [`typeKey`](#schema-typekey) | да |  |
| `path` | `string` | да | Путь к каталогу пакета относительно файла установки |

### `packageSource (3)` { #schema-packagesource-3 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | [`typeKey`](#schema-typekey) | да |  |
| `git` | `string` | да | https://хост/путь без учётных данных в адресе или git@хост:путь; доступ — credential helper git |
| `ref` | `string` | да | Тег релиза пакета (refs/tags/&lt;ref&gt;; ветки и коммиты не принимаются); воспроизводимость держит packages.lock |
| `path` | `string` |  | Подкаталог пакета в репозитории, если он не в корне: относительный путь без . и .. |
<!-- /generated:schema-installation -->

## Тип артефакта (`kind: ArtifactType`) { #artifact-type }

<!-- generated:schema-artifact-type -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `package-sdk/schema/v1/object.schema.json`.

### `artifactTypeSpec` { #schema-artifacttypespec }

Тип артефакта: версионируемый неизменяемый объект каталога, как TaskType.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `displayName` | [`displayName`](#schema-displayname) | да |  |
| `description` | `string` |  |  |
| `metadataSchema` | [`jsonSchema`](#schema-jsonschema) |  | Схема metadata артефакта этого типа (≤ 16 KiB) |
| `mediaTypes` | array of [`mediaType`](#schema-mediatype) |  | Допустимые media types содержимого; по умолчанию любой |
| `maxBytes` | `integer` |  | Лимит размера содержимого; не больше глобального лимита установки (CP_ARTIFACT_MAX_BYTES) |
<!-- /generated:schema-artifact-type -->

## Тип задачи (`kind: TaskType`) { #task-type }

<!-- generated:schema-task-type -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `package-sdk/schema/v1/object.schema.json`.

### `taskTypeSpec` { #schema-tasktypespec }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `displayName` | [`displayName`](#schema-displayname) | да |  |
| `description` | `string` |  |  |
| `fieldSchema` | [`jsonSchema`](#schema-jsonschema) |  | Схема customFields задачи |
| `lifecycleSchema` | [`workItemLifecycle`](#schema-workitemlifecycle) | да |  |
| `execution` | [`execution`](#schema-execution) |  |  |
| `approvalSchema` | [`approvalSchema`](#schema-approvalschema) |  |  |
| `completionSchema` | `object` |  | Работа после завершения задачи: {onComplete: {when?, actions}} — ensureWork (customFields, relation, requestApproval) и comment. Грамматику проверяет ядро. |
| `instructions` | `string` |  | Инструкции исполнителю: Markdown ≤ 16 KiB, слой типа задачи после контракта платформы и проекта. Размер в байтах и отсутствие секретов проверяет ядро. |
| `artifactSchema` | [`artifactSchema`](#schema-artifactschema) |  |  |
| `acceptance` | array of [`acceptanceCriterion`](#schema-acceptancecriterion) |  | Критерии приёмки по умолчанию у всех задач типа: исполняются после обязательных выходов и до критериев самой задачи; задача не может заменить критерий типа — её критерий с тем же key отвергается (422). deterministic со скиллом external_write — только после human той же попытки. |
| `contextSchema` | [объект](#schema-tasktypespec-contextschema) |  | Профиль контекста задачи: anchors, traverse, asOf, budgetTokens. Грамматику проверяет ядро. |

### `taskTypeSpec.contextSchema` { #schema-tasktypespec-contextschema }

Профиль контекста задачи: anchors, traverse, asOf, budgetTokens. Грамматику проверяет ядро.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `anchors` | array of любое |  |  |
| `traverse` | array of любое |  |  |
| `asOf` | `taskCreated` \| `now` \| `origin` |  |  |
| `budgetTokens` | `integer` |  |  |

### `workItemLifecycle` { #schema-workitemlifecycle }

Включает [`lifecycle`](#schema-lifecycle).

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `statuses` | array of [объект](#schema-workitemlifecycle-statuses-item) |  |  |
| `claimStatus` | [`statusKey`](#schema-statuskey) |  | Статус при claim; не терминальный |
| `releaseStatus` | [`statusKey`](#schema-statuskey) |  | Статус при release; не терминальный |
| `completionStatus` | [`statusKey`](#schema-statuskey) |  | Статус успешного завершения; категория terminal_success |

### `workItemLifecycle.statuses[]` { #schema-workitemlifecycle-statuses-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `category` | [`workItemCategory`](#schema-workitemcategory) |  |  |

### `workItemCategory` { #schema-workitemcategory }

Значение: `backlog` \| `active` \| `blocked` \| `terminal_success` \| `terminal_cancelled`.

### `execution` { #schema-execution }

Задачу типа исполняет один вызов скилла

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `skill` | `string` | да |  |
| `version` | `string` | да |  |
| `inputs` | `string` или map → `string` |  | Путь $.… ко всему входу или объект {имяВхода: путь}; по умолчанию $.customFields |

### `approvalSchema` { #schema-approvalschema }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `gates` | map → [объект](#schema-approvalschema-gates-value) |  | Пока поддерживается только gate default |

### `approvalSchema.gates.*` { #schema-approvalschema-gates-value }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `outcomes` | [объект](#schema-approvalschema-gates-value-outcomes) | да |  |

### `approvalSchema.gates.*.outcomes` { #schema-approvalschema-gates-value-outcomes }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `approved` | array of [`outcomeAction`](#schema-outcomeaction) |  |  |
| `rejected` | array of [`outcomeAction`](#schema-outcomeaction) |  |  |

### `outcomeAction` { #schema-outcomeaction }

Одно действие исхода approval: объект ровно с одним ключом. В строках — выражения $.path, суффикс ! делает значение обязательным.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `ensureWork` | [объект](#schema-outcomeaction-ensurework) |  |  |
| `completeTask` | [объект](#schema-outcomeaction-completetask) |  |  |
| `comment` | [объект](#schema-outcomeaction-comment) |  |  |
| `transition` | [объект](#schema-outcomeaction-transition) |  |  |
| `invokeSkill` | [объект](#schema-outcomeaction-invokeskill) |  | Вызов скилла; реакции исполняются по итогу вызова |

### `outcomeAction.ensureWork` { #schema-outcomeaction-ensurework }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` | да | Ключ типа задачи |
| `key` | `string` | да | Ключ идемпотентности создаваемой работы |
| `title` | `string` | да |  |
| `description` | `string` |  |  |
| `assignee` | `string` |  |  |
| `priority` | `string` |  |  |
| `workspace` | `string` |  |  |
| `relation` | map → `string` |  |  |
| `customFields` | map → `string` |  | Поля создаваемой задачи — выражения/шаблоны; проверяются по fieldSchema целевого типа при исполнении |
| `requestApproval` | [объект](#schema-outcomeaction-ensurework-requestapproval) |  | Gate-approval на только что созданной задаче |

### `outcomeAction.ensureWork.requestApproval` { #schema-outcomeaction-ensurework-requestapproval }

Gate-approval на только что созданной задаче

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `assignee` | `string` | да |  |
| `comment` | `string` |  |  |

### `outcomeAction.completeTask` { #schema-outcomeaction-completetask }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `task` | `string` |  |  |

### `outcomeAction.comment` { #schema-outcomeaction-comment }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `body` | `string` | да |  |
| `task` | `string` |  |  |

### `outcomeAction.transition` { #schema-outcomeaction-transition }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `status` | `string` | да |  |
| `task` | `string` |  |  |

### `outcomeAction.invokeSkill` { #schema-outcomeaction-invokeskill }

Вызов скилла; реакции исполняются по итогу вызова

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `skill` | `string` | да | name@version (для external_write — обязательно с версией) |
| `inputs` | `object` |  | входы скилла; строки — выражения $.task…, $.spawnedBy…, $.approval… |
| `expect` | `object` |  | ожидаемые поля outputs; расхождение — onFailure |
| `onSuccess` | array of [`outcomeAction`](#schema-outcomeaction) |  |  |
| `onFailure` | array of [`outcomeAction`](#schema-outcomeaction) |  |  |

### `artifactSchema` { #schema-artifactschema }

Входы и выходы типа задачи. Вход — head-ревизии артефактов нужного типа у задач по связи; без обязательного входа claim отвергается (409 input_missing). Обязательный выход — детерминированный критерий стадии проверки.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `inputs` | array of [объект](#schema-artifactschema-inputs-item) |  |  |
| `outputs` | array of [объект](#schema-artifactschema-outputs-item) |  |  |

### `artifactSchema.inputs[]` { #schema-artifactschema-inputs-item }

Включает [`artifactSlot`](#schema-artifactslot).

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | любое | | |
| `type` | любое | | |
| `required` | любое | | |
| `from` | `depends_on` \| `spawned_by` \| `parent` | да | Связь, по которой ищется задача-источник |

### `artifactSchema.outputs[]` { #schema-artifactschema-outputs-item }

Включает [`artifactSlot`](#schema-artifactslot).

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | любое | | |
| `type` | любое | | |
| `required` | любое | | |
| `mediaTypes` | любое | | |
| `content` | `required` \| `optional` |  | Нужно ли содержимое в хранилище (иначе достаточно ссылки). По умолчанию `required`. |

### `artifactSlot` { #schema-artifactslot }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | `string` | да | Имя входа или выхода; уникально внутри inputs и внутри outputs |
| `type` | [`typeKey`](#schema-typekey) | да | Ключ типа артефакта (ArtifactType) |
| `required` | `boolean` |  | По умолчанию `false`. |
| `mediaTypes` | array of [`mediaType`](#schema-mediatype) |  | Сужение media types типа артефакта (подмножество его mediaTypes) |

### `acceptanceCriterion` { #schema-acceptancecriterion }

Критерий приёмки: грамматику spec по виду проверяет ядро

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | `string` | да |  |
| `kind` | `deterministic` \| `external_state` \| `human` \| `llm_judge` | да |  |
| `description` | `string` | да |  |
| `spec` | `object` |  |  |
| `when` | array of `string` |  | Пути $.task…; критерий исполняется, только если все непусты, иначе skipped |
<!-- /generated:schema-task-type -->

## Шаблон проекта (`kind: ProjectTemplate`) { #project-template }

<!-- generated:schema-project-template -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `package-sdk/schema/v1/object.schema.json`.

### `projectTemplateSpec` { #schema-projecttemplatespec }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `displayName` | [`displayName`](#schema-displayname) | да |  |
| `description` | `string` |  |  |
| `fieldSchema` | [`jsonSchema`](#schema-jsonschema) |  |  |
| `lifecycleSchema` | [`projectLifecycle`](#schema-projectlifecycle) |  |  |
| `defaultConfig` | [объект](#schema-projecttemplatespec-defaultconfig) |  |  |
| `defaultViews` | array of любое |  |  |
| `governanceSchema` | [объект](#schema-projecttemplatespec-governanceschema) |  |  |
| `memoryDefaults` | `object` |  |  |

### `projectTemplateSpec.defaultConfig` { #schema-projecttemplatespec-defaultconfig }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `settings` | `object` |  |  |
| `views` | array of любое |  |  |
| `governance` | `object` |  |  |
| `memory` | `object` |  |  |
| `inheritance` | `object` |  |  |

### `projectTemplateSpec.governanceSchema` { #schema-projecttemplatespec-governanceschema }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `maxAutonomyLevel` | любое |  |  |
| `requireApprovalForRun` | `boolean` |  |  |
| `requireApprovalForCompletion` | `boolean` |  |  |
| `allowedTaskPriorities` | array of `string` |  |  |
| `allowedSkillProtocols` | array of `string` |  |  |
| `maxRunDurationSeconds` | `number` |  |  |
| `maxRunActions` | `number` |  |  |
| `maxConcurrentRuns` | `number` |  |  |
| `memoryScopeSharing` | любое |  |  |

### `projectLifecycle` { #schema-projectlifecycle }

Включает [`lifecycle`](#schema-lifecycle).

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `statuses` | array of [объект](#schema-projectlifecycle-statuses-item) |  |  |

### `projectLifecycle.statuses[]` { #schema-projectlifecycle-statuses-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `category` | [`projectCategory`](#schema-projectcategory) |  |  |

### `projectCategory` { #schema-projectcategory }

Значение: `planned` \| `active` \| `paused` \| `terminal_success` \| `terminal_cancelled`.
<!-- /generated:schema-project-template -->

## Тип пространства работы (`kind: WorkspaceType`) { #workspace-type }

<!-- generated:schema-workspace-type -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `package-sdk/schema/v1/object.schema.json`.

### `workspaceTypeSpec` { #schema-workspacetypespec }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `displayName` | [`displayName`](#schema-displayname) | да |  |
| `description` | `string` |  |  |
| `fieldSchema` | [`jsonSchema`](#schema-jsonschema) |  |  |
| `allowedChildTypes` | array of `string` |  |  |
<!-- /generated:schema-workspace-type -->

## Роль (`kind: Role`) { #role }

<!-- generated:schema-role -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `package-sdk/schema/v1/object.schema.json`.

### `roleSpec` { #schema-rolespec }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `name` | [`displayName`](#schema-displayname) | да |  |
| `description` | `string` |  |  |
<!-- /generated:schema-role -->

## Способность (`kind: Capability`) { #capability }

<!-- generated:schema-capability -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `package-sdk/schema/v1/object.schema.json`.

### `capabilitySpec` { #schema-capabilityspec }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `description` | `string` |  |  |
<!-- /generated:schema-capability -->

## Скилл (`kind: Skill`) { #skill }

<!-- generated:schema-skill -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `package-sdk/schema/v1/object.schema.json`.

### `skillSpec` { #schema-skillspec }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `version` | `string` | да | Версию скилла задаёт пакет |
| `description` | `string` |  |  |
| `protocol` | `mcp` \| `http` \| `local` \| `opencode` \| `custom` |  |  |
| `config` | `object` |  |  |
| `inputSchema` | [`jsonSchema`](#schema-jsonschema) |  |  |
| `outputSchema` | [`jsonSchema`](#schema-jsonschema) |  |  |
| `sideEffects` | `none` \| `external_read` \| `external_write` |  |  |
| `riskLevel` | `low` \| `medium` \| `high` |  |  |
| `contract` | [`skillContract`](#schema-skillcontract) |  |  |

### `skillContract` { #schema-skillcontract }

Контракт Skill v1. Неизменяем в версии.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `inputs` | [`jsonSchema`](#schema-jsonschema) | да |  |
| `outputs` | [`jsonSchema`](#schema-jsonschema) | да |  |
| `requiredPermissions` | array of `string` |  |  |
| `preconditions` | array of любое |  |  |
| `postconditions` | array of любое |  |  |
| `timeoutSeconds` | `integer` |  |  |
| `retryPolicy` | [объект](#schema-skillcontract-retrypolicy) |  |  |
| `idempotency` | `required` \| `natural` \| `none` |  |  |
| `costModel` | [объект](#schema-skillcontract-costmodel) |  |  |
| `implementation` | [объект](#schema-skillcontract-implementation) | да |  |

### `skillContract.retryPolicy` { #schema-skillcontract-retrypolicy }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `maxAttempts` | `integer` |  |  |
| `backoffSeconds` | `integer` |  |  |

### `skillContract.costModel` { #schema-skillcontract-costmodel }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `unit` | `string` | да |  |
| `estimate` | `number` |  |  |

### `skillContract.implementation` { #schema-skillcontract-implementation }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `protocol` | `http` \| `local` \| `mcp` | да |  |
| `endpoint` | `string` |  | http: адрес; допускает ${ПЕРЕМЕННУЮ} окружения |
| `entrypoint` | `string` |  | local: module:function; mcp: имя инструмента |
| `auth` | `object` |  | audience или secretRef; никаких секретов |
<!-- /generated:schema-skill -->

## Правило вывода работы (`kind: WorkRule`) { #work-rule }

<!-- generated:schema-work-rule -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `package-sdk/schema/v1/object.schema.json`.

### `workRuleSpec` { #schema-workrulespec }

Правило вывода работы: ровно тело POST /rules без key. Грамматику условий и шаблонов проверяет ядро (normalize_rule_spec). workspaceId — топология установки: только через ${ПЕРЕМЕННУЮ}, задаётся при создании и дальше не меняется.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `description` | `string` |  |  |
| `workspaceId` | `string` |  |  |
| `trigger` | [объект](#schema-workrulespec-trigger) | да |  |
| `condition` | `object` \| `boolean` |  |  |
| `interpretation` | [объект](#schema-workrulespec-interpretation) |  |  |
| `action` | [объект](#schema-workrulespec-action) | да |  |
| `identity` | [объект](#schema-workrulespec-identity) |  | От чьего имени действует правило: описание агента вида service или agent; без identity — полномочиями того, кто применил правило |
| `status` | `enabled` \| `disabled` |  | По умолчанию enabled |

### `workRuleSpec.trigger` { #schema-workrulespec-trigger }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | `observation` \| `event` \| `schedule` | да |  |

### `workRuleSpec.interpretation` { #schema-workrulespec-interpretation }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `skill` | `string` | да | name@version |
| `inputs` | `object` |  |  |

### `workRuleSpec.action` { #schema-workrulespec-action }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | `ensure_work` \| `update_work` \| `cancel_work` \| `complete_work` \| `request_decision` | да |  |
| `taskType` | `string` |  | Ключ типа или шаблон {{item.…}} — шаблон только при непустом taskTypes |
| `taskTypes` | array of [`typeKey`](#schema-typekey) |  | Допустимые типы для шаблонного taskType |
| `fields` | [объект](#schema-workrulespec-action-fields) |  |  |

### `workRuleSpec.action.fields` { #schema-workrulespec-action-fields }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `workspaceId` | `string` |  | Шаблон id workspace заводимой работы; по умолчанию — workspace правила |
| `relations` | [объект](#schema-workrulespec-action-fields-relations) |  | Связи заводимой работы: spawnedBy — шаблон id задачи; dependsOn — ключи дедупликации работы этого правила (той же оценки или заведённой раньше) |

### `workRuleSpec.action.fields.relations` { #schema-workrulespec-action-fields-relations }

Связи заводимой работы: spawnedBy — шаблон id задачи; dependsOn — ключи дедупликации работы этого правила (той же оценки или заведённой раньше)

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `spawnedBy` | `string` |  |  |
| `dependsOn` | `string` или array of `string` |  |  |

### `workRuleSpec.identity` { #schema-workrulespec-identity }

От чьего имени действует правило: описание агента вида service или agent; без identity — полномочиями того, кто применил правило

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `agent` | [`slug`](#schema-slug) | да |  |
<!-- /generated:schema-work-rule -->

## Агент (`kind: Agent`) { #agent }

<!-- generated:schema-agent -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `package-sdk/schema/v1/object.schema.json`.

### `agentSpec` { #schema-agentspec }

Агент: кто он, какую работу берёт, чем и как исполняет, где размещается. Каждое изменение — новая неизменяемая ревизия в ядре; прогон помнит ревизию.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `displayName` | [`displayName`](#schema-displayname) | да |  |
| `description` | `string` |  |  |
| `identity` | [объект](#schema-agentspec-identity) | да | Личность: principal ядра и IAM и связка с правами — их заводит и поддерживает платформа. Права не шире прав того, кто применяет описание. |
| `work` | [объект](#schema-agentspec-work) |  | Какую работу агент берёт из очереди |
| `executor` | [объект](#schema-agentspec-executor) |  | Чем агент исполняет работу. Вид — данные (строка для ядра); образ по умолчанию выбирает узел, image из описания — только из списка узла. |
| `workingCopy` | `object` |  | Рабочая копия задачи. Толкует демон исполнителя, ядро хранит объект как данные; форму задаёт вид исполнителя: формы по видам — agentWorkingCopies: у вида исполнителя кода — один репозиторий или каталог с полем задачи, у остальных видов — один репозиторий |
| `skills` | [объект](#schema-agentspec-skills) |  | Какие скиллы агент исполняет сам и куда им можно ходить |
| `placement` | = `none` или [объект `{requires, secrets, resources, replicas, drainSeconds}`](#schema-agentspec-placement-2) |  | Где и сколько: none — только личность, без процесса (сервисная учётка) |
| `state` | `running` \| `stopped` |  | По умолчанию `running`. |

Условия:

| Условие | Следствие |
|---|---|
| не (`placement` = `none`) | обязательно `executor` |
| `executor.kind` = `claude-code` | `workingCopy`: [`agentWorkingCopies/claude-code`](#schema-agentworkingcopies-claude-code) |
| иначе | `workingCopy`: [`agentWorkingCopies/single`](#schema-agentworkingcopies-single) |

### `agentSpec.identity` { #schema-agentspec-identity }

Личность: principal ядра и IAM и связка с правами — их заводит и поддерживает платформа. Права не шире прав того, кто применяет описание.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | `agent` \| `service` | да |  |
| `roles` | array of [`slug`](#schema-slug) |  | Роли tenant'а (из пакетов) |
| `permissions` | array of [`permission`](#schema-permission) |  |  |
| `capabilities` | array of `string` |  |  |
| `iam` | [объект](#schema-agentspec-identity-iam) |  | IAM-часть учётки: audiences и потолок scope. Данные для того, кто выпускает учётку (bootstrap, контроллер узлов исполнителей); ядро их хранит, но не толкует. |

### `agentSpec.identity.iam` { #schema-agentspec-identity-iam }

IAM-часть учётки: audiences и потолок scope. Данные для того, кто выпускает учётку (bootstrap, контроллер узлов исполнителей); ядро их хранит, но не толкует.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `audiences` | array of `string` | да |  |
| `scopeCeiling` | array of `string` | да | Scope вида &lt;audience&gt;:&lt;действие&gt; |

### `agentSpec.work` { #schema-agentspec-work }

Какую работу агент берёт из очереди

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `workspace` | [`envOrUuid`](#schema-envoruuid) |  |  |
| `project` | [`envOrUuid`](#schema-envoruuid) |  |  |
| `includeSubprojects` | `boolean` |  | По умолчанию `false`. |
| `onlyAssigned` | `boolean` |  | Только назначенная ему работа. По умолчанию `true`. |
| `taskTypes` | array of [`typeKey`](#schema-typekey) |  | Пусто — любые типы |

### `agentSpec.executor` { #schema-agentspec-executor }

Чем агент исполняет работу. Вид — данные (строка для ядра); образ по умолчанию выбирает узел, image из описания — только из списка узла.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | `claude-code` \| `codex` \| `skills` \| `git-connector` \| `observer` | да |  |
| `params` | `object` |  |  |
| `image` | `string` |  | Образ исполнителя: [registry[:port]/]path:tag, …@sha256:&lt;64 hex&gt; или …:tag@sha256:&lt;64 hex&gt; — тег или дайджест обязателен. Узел запускает его, только если образ есть в списке executors.&lt;вид&gt;.images узла, иначе image_not_allowed; без поля — образ вида по умолчанию |
| `instructions` | `string` |  | Инструкции исполнителю — слой после инструкций платформы, проекта и типа задачи |

Условия:

| Условие | Следствие |
|---|---|
| `kind` = `claude-code` | `params`: [`agentExecutors/claude-code`](#schema-agentexecutors-claude-code) |
| `kind` = `codex` | `params`: [`agentExecutors/codex`](#schema-agentexecutors-codex) |
| `kind` = `skills` | `params`: [`agentExecutors/skills`](#schema-agentexecutors-skills) |
| `kind` = `git-connector` | обязательно `params`; `params`: [`agentExecutors/git-connector`](#schema-agentexecutors-git-connector) |
| `kind` = `observer` | обязательно `params`; `params`: [`agentExecutors/observer`](#schema-agentexecutors-observer) |

### `agentSpec.skills` { #schema-agentspec-skills }

Какие скиллы агент исполняет сам и куда им можно ходить

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `protocols` | array of `local` \| `http` \| `mcp` |  |  |
| `local` | array of `string` |  | Разрешённые entrypoints или пакеты |
| `httpOrigins` | array of `string` |  |  |
| `mcpOrigins` | array of `string` |  |  |
| `audiences` | array of `string` |  | Audiences IAM, в которые скиллы получают токен |
| `concurrency` | `integer` |  |  |
| `invoke` | array of `string` |  | Версии скиллов, которые агент вызывает через ядро (имя@версия), а не исполняет сам; реестр назначает их principal'у агента |

### `agentSpec.placement (2)` { #schema-agentspec-placement-2 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `requires` | array of [`nodeLabel`](#schema-nodelabel) |  | Метки, которые должны быть у узла |
| `secrets` | array of [`secretName`](#schema-secretname) |  | Секреты, которые должны быть на узле: статические (файл в каталоге секретов узла) и выдаваемые — их узел выпускает сам и обновляет, например часовой forge-token из установки приложения forge. Объявляются одинаково, по имени; материал в описание не пишется |
| `resources` | [объект](#schema-agentspec-placement-2-resources) |  |  |
| `replicas` | `integer` |  | По умолчанию `1`. |
| `drainSeconds` | `integer` |  | Сколько ждать текущий прогон перед переходом на новую ревизию. По умолчанию `14400`. |

### `agentSpec.placement (2).resources` { #schema-agentspec-placement-2-resources }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `cpus` | `number` |  |  |
| `memoryMb` | `integer` |  |  |

### `permission` { #schema-permission }

Право Control Plane, например tasks.claim

Значение: `string`.

### `agentExecutors` { #schema-agentexecutors }

Параметры видов исполнителя; ядро хранит их, не толкуя, проверяет эта схема и адаптер

Набор определений: [`agentExecutors/claude-code`](#schema-agentexecutors-claude-code), [`agentExecutors/codex`](#schema-agentexecutors-codex), [`agentExecutors/skills`](#schema-agentexecutors-skills), [`agentExecutors/git-connector`](#schema-agentexecutors-git-connector), [`agentExecutors/observer`](#schema-agentexecutors-observer).

### `agentExecutors/claude-code` { #schema-agentexecutors-claude-code }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `model` | `string` |  |  |
| `permissionMode` | `default` \| `acceptEdits` \| `plan` \| `bypassPermissions` |  | По умолчанию `acceptEdits`. |
| `timeoutSeconds` | `integer` |  | По умолчанию `3600`. |
| `resume` | `boolean` |  | По умолчанию `true`. |
| `tools` | [объект](#schema-agentexecutors-claude-code-tools) |  | Сужение инструментов агента; запрет авторитетных команд Control Plane не снимается |

### `agentExecutors/claude-code.tools` { #schema-agentexecutors-claude-code-tools }

Сужение инструментов агента; запрет авторитетных команд Control Plane не снимается

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `allow` | array of `string` |  |  |
| `deny` | array of `string` |  |  |

### `agentExecutors/codex` { #schema-agentexecutors-codex }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `model` | `string` |  |  |
| `sandbox` | `read-only` \| `workspace-write` \| `danger-full-access` |  | По умолчанию `workspace-write`. |
| `timeoutSeconds` | `integer` |  | По умолчанию `3600`. |
| `resume` | `boolean` |  | По умолчанию `true`. |
| `credentialClass` | `subscription` \| `api_key` |  | Чей credential расходуется |

### `agentExecutors/skills` { #schema-agentexecutors-skills }

Исполнитель только скиллов: параметров нет, что исполнять — секция skills агента

Значение: `object`.

### `agentExecutors/git-connector` { #schema-agentexecutors-git-connector }

Источник наблюдений git: что наблюдать и какие наблюдения порождать. Курсор — в томе реплики, наблюдения — POST /observations workspace агента.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `repositories` | array of [объект](#schema-agentexecutors-git-connector-repositories-item) | да |  |
| `observe` | array of `commits` \| `adrRegistry` \| `ciRuns` |  | commits — repo.commit_observed; adrRegistry — adr.registry_observed; ciRuns — ci.run_observed. По умолчанию `["commits"]`. |
| `intervalSeconds` | `integer` |  | По умолчанию `300`. |
| `knowledgeSnapshots` | `boolean` |  | Отдавать снимки контрактов в память через POST /knowledge/snapshots. По умолчанию `true`. |
| `registryRepository` | `string` |  | Из какого репозитория читать реестр ADR (имя из repositories) |
| `ciRepository` | `string` |  | owner/repo прогонов CI |
| `ciBranch` | `string` |  | По умолчанию `main`. |

### `agentExecutors/git-connector.repositories[]` { #schema-agentexecutors-git-connector-repositories-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `name` | `string` | да | Имя в наблюдениях (payload.data.repo, source git:&lt;name&gt;) |
| `url` | `string` | да |  |
| `branch` | `string` |  | По умолчанию `main`. |

### `agentExecutors/observer` { #schema-agentexecutors-observer }

Источник наблюдений пакета интеграции (коннектор = наблюдатель + скиллы): долгоживущий процесс, который по циклу опрашивает внешнюю систему и пишет наблюдения в workspace агента (POST /observations). Что опрашивать — config, его толкует код интеграции; какой код — entrypoint, его должен содержать образ вида observer на узле. Курсор — в томе реплики, секреты — только файлами секретов узла (placement.secrets).

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `entrypoint` | `string` | да | Наблюдатель интеграции «модуль:функция»; процесс образа проверяет, что исполняет именно его |
| `intervalSeconds` | `integer` |  | По умолчанию `900`. |
| `config` | `object` |  | Параметры интеграции (фильтры, адреса, лимиты) — данные пакета. Секретов здесь нет: ключи вида *token, *secret, *password запрещены |

### `nodeLabel` { #schema-nodelabel }

Метка узла: имя или имя=значение

Значение: `string`.

### `secretName` { #schema-secretname }

Имя секрета на узле; значение в описание не пишется

Значение: `string`.

### `agentWorkingCopies` { #schema-agentworkingcopies }

Формы раздела workingCopy по видам исполнителя: ядро хранит раздел как данные, проверяют эта схема и демон исполнителя

Набор определений: [`agentWorkingCopies/single`](#schema-agentworkingcopies-single), [`agentWorkingCopies/catalog`](#schema-agentworkingcopies-catalog), [`agentWorkingCopies/catalogEntry`](#schema-agentworkingcopies-catalogentry), [`agentWorkingCopies/claude-code`](#schema-agentworkingcopies-claude-code).

### `agentWorkingCopies/claude-code` { #schema-agentworkingcopies-claude-code }

Один репозиторий (прежняя форма) или каталог: наличие repositories или repositoryField выбирает каталог

Значение: [`agentWorkingCopies/catalog`](#schema-agentworkingcopies-catalog) или [`agentWorkingCopies/single`](#schema-agentworkingcopies-single) — по условию.

Условия:

| Условие | Следствие |
|---|---|
| задано `repositories` или задано `repositoryField` | [`agentWorkingCopies/catalog`](#schema-agentworkingcopies-catalog) |
| иначе | [`agentWorkingCopies/single`](#schema-agentworkingcopies-single) |

### `agentWorkingCopies/catalog` { #schema-agentworkingcopies-catalog }

Каталог репозиториев — единственный источник адресов клона, соседей и публикации. Репозиторий задачи — ключ каталога или псевдоним в поле задачи repositoryField; адрес из задачи не принимается, значения по умолчанию нет. Ключи и псевдонимы сопоставляются без учёта регистра (casefold) — так разрешают ключ задачи демон исполнителя и tasks.check@1. Ссылку superproject на ключ каталога, однозначность ключей и псевдонимов (casefold), адресов (нормализованных) и каталогов между записями проверяет package-sdk check

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `repositoryField` | `string` | да | Имя поля customFields задачи с ключом репозитория (у coding-task — repositoryKey) |
| `superproject` | любое |  | Ключ каталога, чьи сабмодули закрепляют ревизии соседей |
| `publish` | `boolean` |  | Публиковать ветку задачи в forge; запись каталога может переопределить. По умолчанию `true`. |
| `repositories` | map → [`agentWorkingCopies/catalogEntry`](#schema-agentworkingcopies-catalogentry) | да |  |

### `repositoryKey` { #schema-repositorykey }

Канонический ключ репозитория в каталоге рабочей копии: ASCII, как в customFields задачи. Ключи и псевдонимы сопоставляются без учёта регистра (casefold): так разрешают ключ задачи демон исполнителя и tasks.check@1

Значение: `string`.

### `agentWorkingCopies/catalogEntry` { #schema-agentworkingcopies-catalogentry }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `url` | `string` | да | Адрес клона: ${ПЕРЕМЕННАЯ} установки или https без учётных данных, запроса и фрагмента (топология окружения в пакет не пишется). Хост — метки DNS, порт 1–65535; сегменты пути — ASCII без dot-сегментов и ведущей точки: имя зеркала берётся из последнего сегмента. Совпадение адресов двух записей package-sdk check ищет после нормализации (без завершающего /, без .git, без учёта регистра) |
| `baseRef` | `string` |  | Базовая ветка задачи — имя ref git: без ведущих - / ., без пробелов и управляющих символов, без .., @{, //, ~^:?*[\ и завершающих / . .lock |
| `directory` | `string` |  | Имя каталога в рабочей копии (плоская раскладка); не повторяет каталог или ключ другой записи — проверяет package-sdk check |
| `publish` | `boolean` |  | false — сосед, в который агент не пишет; по умолчанию — publish каталога |
| `aliases` | array of [`repositoryAlias`](#schema-repositoryalias) |  | Прежние имена, которые принимаются вместо ключа; сопоставление без учёта регистра (casefold), поэтому псевдонимы не повторяют ни свои, ни чужие ключи и псевдонимы и в другом регистре |

### `repositoryAlias` { #schema-repositoryalias }

Прежнее имя репозитория (ключ карты, строка «Репозиторий» документа задач, ключ дедупликации коннектора): буквы латиницы и кириллицы, цифры, . _ -. Сопоставляется с ключом задачи без учёта регистра (casefold)

Значение: `string`.

### `agentWorkingCopies/single` { #schema-agentworkingcopies-single }

Прежняя форма: один репозиторий, соседи и суперпроект адресами

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `repository` | `string` | да |  |
| `directory` | `string` |  | Имя каталога репозитория в рабочей копии (плоская раскладка) |
| `baseRef` | `string` |  |  |
| `neighbours` | map → `string` |  | Соседние репозитории на ревизиях, закреплённых суперпроектом |
| `superproject` | `string` |  |  |
| `publish` | `boolean` |  | Публиковать ветку задачи в forge. По умолчанию `true`. |
| `review` | [объект](#schema-agentworkingcopies-single-review) |  | Устарело: ревью объявляет тип задачи критериями приёмки; секция удаляется вместе с авто-ревью демона |

### `agentWorkingCopies/single.review` { #schema-agentworkingcopies-single-review }

Устарело: ревью объявляет тип задачи критериями приёмки; секция удаляется вместе с авто-ревью демона

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `mode` | `human` \| `agent` \| `none` |  |  |
| `taskType` | [`typeKey`](#schema-typekey) |  |  |
| `taskTypes` | array of [`typeKey`](#schema-typekey) |  | Для каких типов задач заводится ревью |
| `reviewer` | [`envOrUuid`](#schema-envoruuid) |  |  |
| `base` | `string` |  |  |
<!-- /generated:schema-agent -->

## Правило уведомления (`kind: NotificationRule`) { #notification-rule }

<!-- generated:schema-notification-rule -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `package-sdk/schema/v1/object.schema.json`.

### `notificationRuleSpec` { #schema-notificationrulespec }

Правило уведомления: событие ядра и условие → адресат → текст и кнопки. Хранит и исполняет сервис уведомлений; шаблоны — подстановка {{payload.…}}, {{event.…}}, {{task.…}} без логики.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `description` | `string` |  |  |
| `on` | [объект](#schema-notificationrulespec-on) | да |  |
| `recipient` | [объект](#schema-notificationrulespec-recipient) | да |  |
| `notification` | [объект](#schema-notificationrulespec-notification) | да |  |
| `dedupKeyTemplate` | `string` |  |  |
| `close` | [объект](#schema-notificationrulespec-close) |  | Закрыть кнопки уведомления с тем же ключом дедупликации, когда пришло событие |
| `status` | `enabled` \| `disabled` |  | По умолчанию enabled |

### `notificationRuleSpec.on` { #schema-notificationrulespec-on }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` | да | Тип события каталога ядра или префикс.* |
| `when` | `object` \| `boolean` |  | Условие грамматики правил ядра над payload, event и task |

### `notificationRuleSpec.recipient` { #schema-notificationrulespec-recipient }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | `assigned` \| `role` \| `taskOwner` \| `taskAssignee` \| `principal` | да |  |
| `ref` | `string` |  | Путь к principal или роли в событии (assigned, role) или id/переменная (principal) |
| `workspace` | `string` |  | Путь к workspace для role; по умолчанию workspace события |
| `fallback` | `taskOwner` \| `taskAssignee` \| `none` |  | По умолчанию `none`. |

### `notificationRuleSpec.notification` { #schema-notificationrulespec-notification }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` | да | Тип уведомления — по нему работают настройки получателя и обязательные правила |
| `title` | `string` | да |  |
| `body` | `string` |  |  |
| `links` | array of [объект](#schema-notificationrulespec-notification-links-item) |  |  |
| `actions` | array of `approvalDecide` |  | approvalDecide — кнопки «Одобрить»/«Отклонить» решения из payload.approvalId |

### `notificationRuleSpec.notification.links[]` { #schema-notificationrulespec-notification-links-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `label` | `string` | да |  |
| `url` | `string` | да |  |

### `notificationRuleSpec.close` { #schema-notificationrulespec-close }

Закрыть кнопки уведомления с тем же ключом дедупликации, когда пришло событие

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `on` | array of `string` | да |  |
| `outcome` | `string` |  | Шаблон исхода, который показывается вместо кнопок |
<!-- /generated:schema-notification-rule -->

## Процесс (`kind: Process`) { #process }

<!-- generated:schema-process -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `package-sdk/schema/v1/object.schema.json`.

### `processSpec` { #schema-processspec }

Процесс: кейс со стадиями и блоками исполнения, данные по схеме, выражения CEL, проекция в память. Исполняет ядро

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `version` | `integer` | да | Версия определения: опубликованная версия неизменяема |
| `displayName` | [`displayName`](#schema-displayname) | да |  |
| `description` | `string` |  |  |
| `workspaceId` | `string` |  |  |
| `identity` | [объект](#schema-processspec-identity) |  | От чьего имени действует процесс: описание агента вида service или agent |
| `owner` | [`assignChain`](#schema-assignchain) |  | Владелец процесса — ему адресуются задачи о процессе: расхождение с регламентом, ошибки экземпляров. Не обязателен; проверка пакета предупреждает, если его нет |
| `calendar` | [`typeKey`](#schema-typekey) |  | Календарь по умолчанию для cal.* |
| `due` | [`processDue`](#schema-processdue) |  | Срок процесса целиком от старта экземпляра |
| `data` | [`jsonSchema`](#schema-jsonschema) | да | JSON Schema данных экземпляра; {$ref: &lt;файл пакета&gt;} раскрывает package-sdk |
| `start` | [объект](#schema-processspec-start) | да |  |
| `correlate` | array of [объект](#schema-processspec-correlate-item) |  |  |
| `stages` | array of [`processStage`](#schema-processstage) | да |  |
| `onEvent` | array of [объект](#schema-processspec-onevent-item) |  |  |
| `timers` | [`processTimers`](#schema-processtimers) |  |  |
| `decisions` | array of [`decisionTable`](#schema-decisiontable) |  |  |
| `governedBy` | [`governedBy`](#schema-governedby) |  |  |
| `memory` | [`memoryProjection`](#schema-memoryprojection) |  |  |
| `retrospective` | [объект](#schema-processspec-retrospective) |  | Разбор закрытого дела: агент предлагает уроки, человек подтверждает |
| `migrations` | array of [объект](#schema-processspec-migrations-item) |  |  |

### `processSpec.identity` { #schema-processspec-identity }

От чьего имени действует процесс: описание агента вида service или agent

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `agent` | [`slug`](#schema-slug) | да |  |

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

Разбор закрытого дела: агент предлагает уроки, человек подтверждает

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `skill` | `string` |  | По умолчанию `process.retrospective@1`. |
| `taskType` | [`typeKey`](#schema-typekey) | да |  |
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

### `assignChain` { #schema-assignchain }

Кандидаты по порядку: берётся первый разрешимый

Значение: array of [`assignee`](#schema-assignee).

### `assignee` { #schema-assignee }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `principal` | [`envOrUuid`](#schema-envoruuid) |  |  |
| `role` | [`slug`](#schema-slug) |  |  |
| `agent` | [`slug`](#schema-slug) |  |  |
| `expr` | [`cel`](#schema-cel) |  | CEL → id principal, agent:&lt;key&gt; или role:&lt;slug&gt; |

Ровно одно из: `principal`, `role`, `agent`, `expr`.

### `cel` { #schema-cel }

Выражение CEL в профиле taimen/1: переменные data, event, step, task, instance; функции cal.*; без текущего времени. Типы и лимит стоимости проверяет ядро

Значение: `string`.

### `processDue` { #schema-processdue }

Срок (SLA) шага или процесса: длительность ISO 8601, {at} — момент или длительность от данных, либо ровно одно из duration, workdays, workhours с необязательными calendar и warnBefore

Значение: [`durationOrCel`](#schema-durationorcel) или [объект `{duration, workdays, workhours, calendar, warnBefore}`](#schema-processdue-2).

### `processDue (2)` { #schema-processdue-2 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `duration` | [`duration`](#schema-duration) |  |  |
| `workdays` | [`workdayCount`](#schema-workdaycount) |  |  |
| `workhours` | [`workhourCount`](#schema-workhourcount) |  |  |
| `calendar` | [`typeKey`](#schema-typekey) |  | Календарь рабочих единиц; по умолчанию spec.calendar процесса |
| `warnBefore` | [`workingSpan`](#schema-workingspan) |  | Порог предупреждения до срока; без него предупреждения нет |

Ровно одно из: `duration`, `workdays`, `workhours`.

### `durationOrCel` { #schema-durationorcel }

Длительность ISO 8601 или выражение CEL, дающее момент времени (timestamp) или длительность

Значение: [`duration`](#schema-duration) или [объект `{at}`](#schema-durationorcel-2).

### `durationOrCel (2)` { #schema-durationorcel-2 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `at` | [`cel`](#schema-cel) | да |  |

### `workdayCount` { #schema-workdaycount }

Рабочие дни по календарю: то же время суток через n рабочих дней (cal.addWorkdays)

Значение: `integer`.

### `workhourCount` { #schema-workhourcount }

Часы рабочего времени по календарю с рабочими часами (cal.addWorkingTime)

Значение: `number`.

### `workingSpan` { #schema-workingspan }

Промежуток: длительность ISO 8601 (астрономическое время), {workdays} или {workhours} по календарю срока

Значение: [`duration`](#schema-duration) или [объект `{workdays}`](#schema-workingspan-2) или [объект `{workhours}`](#schema-workingspan-3).

### `workingSpan (2)` { #schema-workingspan-2 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `workdays` | [`workdayCount`](#schema-workdaycount) | да |  |

### `workingSpan (3)` { #schema-workingspan-3 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `workhours` | [`workhourCount`](#schema-workhourcount) | да |  |

### `processTrigger` { #schema-processtrigger }

Источник события: событие журнала ядра или наблюдение. where — фильтр CEL над event

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `event` | `string` |  |  |
| `observation` | `string` |  |  |
| `source` | `string` |  |  |
| `where` | [`cel`](#schema-cel) |  |  |

Ровно одно из: `event`, `observation`.

### `celMap` { #schema-celmap }

Путь в данных экземпляра → выражение CEL

Значение: map → [`cel`](#schema-cel).

### `blocks` { #schema-blocks }

Последовательность шагов (блок do)

Значение: array of [`processStep`](#schema-processstep).

### `processStep` { #schema-processstep }

Шаг процесса: ровно один вид (human, approve, call, decide, recall, remember, listen, wait, set, raise, compensate, fork, try, do, suspend, resume, complete) плюс общие поля

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | да |  |
| `displayName` | [`displayName`](#schema-displayname) |  |  |
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
| `wait` | [`durationOrCel`](#schema-durationorcel) |  | Пауза: длительность или момент; срока (due) у wait нет — пауза сама задаёт время |
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
| `taskType` | [`typeKey`](#schema-typekey) | да |  |
| `title` | [`cel`](#schema-cel) |  |  |
| `form` | [`processForm`](#schema-processform) |  |  |
| `assign` | [`assignChain`](#schema-assignchain) | да |  |
| `due` | [`processDue`](#schema-processdue) |  |  |
| `escalations` | array of [`escalation`](#schema-escalation) |  |  |
| `context` | [`stepContext`](#schema-stepcontext) |  |  |

### `processStep.approve` { #schema-processstep-approve }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `taskType` | [`typeKey`](#schema-typekey) |  |  |
| `approvers` | [`assignChain`](#schema-assignchain) | да |  |
| `mode` | `parallel` \| `sequential` |  | По умолчанию `parallel`. |
| `quorum` | `all` \| `any` или [объект `{atLeast}`](#schema-processstep-approve-quorum-2) или [объект `{percent}`](#schema-processstep-approve-quorum-3) | да |  |
| `earlyDecision` | `boolean` |  | По умолчанию `true`. |
| `separationOfDuties` | [`cel`](#schema-cel) |  | CEL → список principal, которым голосовать нельзя; проверяет ядро при решении |
| `due` | [`processDue`](#schema-processdue) |  |  |
| `onDue` | `approve` \| `reject` \| `escalate` |  |  |
| `escalations` | array of [`escalation`](#schema-escalation) |  |  |
| `context` | [`stepContext`](#schema-stepcontext) |  |  |

### `processStep.approve.quorum (2)` { #schema-processstep-approve-quorum-2 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `atLeast` | `integer` | да |  |

### `processStep.approve.quorum (3)` { #schema-processstep-approve-quorum-3 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `percent` | `number` | да |  |

### `processStep.call` { #schema-processstep-call }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `skill` | `string` |  |  |
| `agent` | [`slug`](#schema-slug) |  |  |
| `process` | [`typeKey`](#schema-typekey) |  |  |
| `input` | [`celMap`](#schema-celmap) |  |  |
| `timeout` | [`durationOrCel`](#schema-durationorcel) |  |  |
| `due` | [`processDue`](#schema-processdue) |  |  |
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
| `where` | [`memoryWhere`](#schema-memorywhere) |  |  |
| `limit` | `integer` |  |  |
| `timeout` | [`duration`](#schema-duration) |  |  |
| `due` | [`processDue`](#schema-processdue) |  |  |
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
| `due` | [`processDue`](#schema-processdue) |  |  |
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

### `processElementId` { #schema-processelementid }

Стабильный id элемента процесса: на него ссылаются раскладка схемы, карты миграции, журнал и граф памяти. Переименование — только картой migrations

Значение: `string`.

### `governedBy` { #schema-governedby }

Регламенты базы знаний, которым подчиняется элемент: естественный ключ документа памяти и, при необходимости, пункт

Значение: array of [объект](#schema-governedby-item).

### `governedBy[]` { #schema-governedby-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `document` | `string` | да |  |
| `section` | `string` |  |  |

### `processForm` { #schema-processform }

Форма шага: JSON Schema данных и uischema JSON Forms представления

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `schema` | [`jsonSchema`](#schema-jsonschema) | да |  |
| `uischema` | `object` |  |  |

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

### `stepContext` { #schema-stepcontext }

Профиль контекста исполнителя шага из памяти: явные связи первыми, смысловой добор с пометкой inferred

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

Шаги обхода от якорей — та же форма, что traverse в contextSchema

Значение: array of [объект](#schema-memorytraverse-item).

### `memoryTraverse[]` { #schema-memorytraverse-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `relation` | `string` | да |  |
| `direction` | `in` \| `out` \| `both` |  |  |
| `depth` | `integer` |  |  |
| `limit` | `integer` |  |  |
| `from` | `anchors` \| `previous` |  |  |

### `memoryWhere` { #schema-memorywhere }

Фильтры по атрибутам узлов: применяются к узлам результата и к якорям-кандидатам смыслового добора; условия соединяются через И

Значение: array of [объект](#schema-memorywhere-item).

### `memoryWhere[]` { #schema-memorywhere-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `attr` | `string` | да | Имя атрибута узла (плоское), например okpd2 или validUntil; атрибут-список выполняет условие, если его выполняет хоть один элемент |
| `op` | `eq` \| `in` \| `prefix` \| `lte` \| `gte` \| `exists` | да | prefix сравнивает коды по сегментам через точку: 62.01 совпадает с 62.01.11, но не с 62.011; lte/gte — даты RFC 3339 или числа |
| `value` | [`cel`](#schema-cel) или `number` \| `boolean` или array of [`cel`](#schema-cel) |  | CEL-выражение от данных экземпляра (строковый литерал — в кавычках CEL: "'62.01'"); для in — CEL-список или список выражений; для exists — true или false |

Условия:

| Условие | Следствие |
|---|---|
| `op` ≠ `exists` | обязательно `value` |

### `processStage` { #schema-processstage }

Стадия кейса (CMMN): вход и выход по сторожам, вехи, обязательная и необязательная работа

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | да |  |
| `displayName` | [`displayName`](#schema-displayname) |  |  |
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
| `displayName` | [`displayName`](#schema-displayname) |  |  |
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

Проекция дела в граф памяти: доставляется событиями, в граф идут только объявленные поля

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
| `artifacts` | array of [`typeKey`](#schema-typekey) |  |  |
<!-- /generated:schema-process -->

## Календарь (`kind: Calendar`) { #calendar }

<!-- generated:schema-calendar -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `package-sdk/schema/v1/object.schema.json`.

### `calendarSpec` { #schema-calendarspec }

Производственный календарь: выходные по умолчанию, праздники и переносы по годам

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `displayName` | [`displayName`](#schema-displayname) | да |  |
| `timezone` | `string` | да |  |
| `weekend` | array of `integer` |  | Дни недели ISO: 1 — понедельник. По умолчанию `[6, 7]`. |
| `workingHours` | [объект](#schema-calendarspec-workinghours) |  | Рабочие часы в рабочие дни календаря, местное время календаря. Без поля календарь знает только рабочие дни |
| `years` | array of [объект](#schema-calendarspec-years-item) | да |  |

### `calendarSpec.workingHours` { #schema-calendarspec-workinghours }

Рабочие часы в рабочие дни календаря, местное время календаря. Без поля календарь знает только рабочие дни

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `intervals` | [`workingIntervals`](#schema-workingintervals) | да | Интервалы обычного рабочего дня |
| `weekdays` | map → [`workingIntervals`](#schema-workingintervals) |  | Интервалы по дню недели ISO (1 — понедельник) вместо intervals; [] — рабочих часов нет |
| `shortDayReduction` | [`duration`](#schema-duration) |  | На сколько короче сокращённый день (shortDays): вычитается с конца последнего интервала |

### `calendarSpec.years[]` { #schema-calendarspec-years-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `year` | `integer` | да |  |
| `provisional` | `boolean` |  | Год ещё не утверждён: результаты cal.* помечаются «предварительно» |
| `source` | `string` |  |  |
| `holidays` | array of `string` (date) |  |  |
| `workdays` | array of `string` (date) |  | Перенесённые рабочие дни, выпавшие на выходные |
| `shortDays` | array of `string` (date) |  |  |

### `workingIntervals` { #schema-workingintervals }

Интервалы рабочего времени дня по порядку и без пересечений, from раньше to (порядок проверяет ядро); 24:00 — конец суток

Значение: array of [объект](#schema-workingintervals-item).

### `workingIntervals[]` { #schema-workingintervals-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `from` | `string` | да |  |
| `to` | `string` | да |  |
<!-- /generated:schema-calendar -->

## Онтология (`kind: KnowledgePack`) { #knowledge-pack }

Тело онтологии описывает отдельный файл схемы `knowledge-pack.schema.json`; в пакете к нему добавляется целая версия `version`.

<!-- generated:schema-knowledge-pack -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `package-sdk/schema/v1/object.schema.json`, `package-sdk/schema/v1/knowledge-pack.schema.json`.

### `KnowledgePack.spec` { #schema-knowledgepack-spec }

Включает [`knowledge-pack`](#schema-knowledge-pack).

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `version` | `integer` |  | Версия онтологии в пакете — целое: включение ссылается на неё как name@version, правка — новая версия |

### `knowledge-pack` { #schema-knowledge-pack }

Форма пакета видов и связей базы знаний. Пакет регистрируется через ядро (POST /api/v1/knowledge/packs) и включается для дерева workspace. memory-service разбирает name, version, scope, namespace, kinds (kind, kindAliases, aliases, naturalKey, idPatterns, attributes, searchable) и relations; остальные поля — данные загрузчиков и генератора шаблонов импорта, память их пропускает.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `name` | `string` | да | Имя пакета без префикса. Ссылка на пакет арендатора в настройке namespace — tenant:&lt;имя&gt;@&lt;версия&gt; |
| `version` | `string` \| `integer` | да | Версия пакета; шаблоны видов версионируются ею |
| `scope` | `common` \| `tenant` |  | common — общий пакет, регистрирует администратор платформы; tenant — пакет арендатора по праву knowledge.packs.manage: виден и включается только в namespace-владельце и под ним, имена пакета, видов и связей не совпадают с общими. По умолчанию `common`. |
| `namespace` | `string` |  | Namespace-владелец пакета арендатора (scope: tenant); при регистрации через ядро его подставляет ядро по workspace |
| `description` | `string` |  |  |
| `extends` | array of `string` |  | Пакеты, на виды которых ссылаются связи и профили этого пакета (например company@1). Базовый пакет не меняется |
| `kinds` | array of [`knowledge-pack/kind`](#schema-knowledge-pack-kind) | да |  |
| `relations` | array of [`knowledge-pack/relation`](#schema-knowledge-pack-relation) |  |  |
| `profiles` | array of [`knowledge-pack/profile`](#schema-knowledge-pack-profile) |  | Профили атрибутов видов, в том числе видов других пакетов: так пакет описывает атрибуты чужого вида, не меняя и не переобъявляя его (credential с type: sro_membership у расширения отрасли, legal_entity пакета default у company). Проверяют загрузчики и генератор шаблонов |
| `expiry` | array of [`knowledge-pack/expiry`](#schema-knowledge-pack-expiry) |  | Кому и за сколько дней ставить задачу об истечении validUntil вида (правило knowledge-expiry). Без записи — роль владельца базы знаний и 30 дней |

### `knowledge-pack/kind` { #schema-knowledge-pack-kind }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | [`knowledge-pack/name`](#schema-knowledge-pack-name) | да |  |
| `title` | `string` |  | Название вида для людей — заголовок шаблона и раздела консоли |
| `description` | `string` |  |  |
| `kindAliases` | array of [`knowledge-pack/name`](#schema-knowledge-pack-name) |  |  |
| `aliases` | array of `string` |  |  |
| `naturalKey` | `string` или `object` |  | Форма естественного ключа: шаблон с плейсхолдерами ("offering:&lt;source&gt;:&lt;id&gt;") или JSON Schema строки |
| `idPatterns` | array of `string` |  |  |
| `attributes` | [`knowledge-pack/attributes`](#schema-knowledge-pack-attributes) |  |  |
| `searchable` | [объект](#schema-knowledge-pack-kind-searchable) |  | Вид находится поиском по смыслу: сверка индексирует эмбеддинг из title сущности и значений перечисленных атрибутов; каждый атрибут объявлен в attributes.properties |

### `knowledge-pack/kind.searchable` { #schema-knowledge-pack-kind-searchable }

Вид находится поиском по смыслу: сверка индексирует эмбеддинг из title сущности и значений перечисленных атрибутов; каждый атрибут объявлен в attributes.properties

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `fields` | array of `string` | да |  |

### `knowledge-pack/name` { #schema-knowledge-pack-name }

Значение: `string`.

### `knowledge-pack/attributes` { #schema-knowledge-pack-attributes }

JSON Schema атрибутов вида (draft 2020-12). title и description свойства — заголовок и подсказка колонки шаблона; type, format, enum — проверка; required — обязательность. Сроки действия — по соглашению validFrom и validUntil (format: date). Свойство с персональными данными физического лица допустимо только с x-personal-data: allowed — такие значения не попадают в промпты ИИ

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | = `object` |  |  |
| `properties` | [объект](#schema-knowledge-pack-attributes-properties) |  |  |

### `knowledge-pack/attributes.properties` { #schema-knowledge-pack-attributes-properties }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `validFrom` | [`knowledge-pack/dateProperty`](#schema-knowledge-pack-dateproperty) |  |  |
| `validUntil` | [`knowledge-pack/dateProperty`](#schema-knowledge-pack-dateproperty) |  |  |

### `knowledge-pack/dateProperty` { #schema-knowledge-pack-dateproperty }

Соглашение сроков: validFrom и validUntil — день ISO 8601

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | = `string` | да |  |
| `format` | = `date` | да |  |

### `knowledge-pack/relation` { #schema-knowledge-pack-relation }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `relation` | [`knowledge-pack/name`](#schema-knowledge-pack-name) | да |  |
| `title` | `string` |  | Заголовок колонки связи в шаблоне |
| `fromKinds` | array of [`knowledge-pack/name`](#schema-knowledge-pack-name) |  |  |
| `toKinds` | array of [`knowledge-pack/name`](#schema-knowledge-pack-name) |  |  |
| `temporal` | `boolean` |  | По умолчанию `true`. |
| `cardinality` | `one` \| `many` |  | По умолчанию `many`. |

### `knowledge-pack/profile` { #schema-knowledge-pack-profile }

Атрибуты вида этого или другого пакета. С when — у сущностей, где атрибут равен значению (credential с type: sro_membership); без when — у всех сущностей вида (атрибуты legal_entity пакета default)

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | [`knowledge-pack/name`](#schema-knowledge-pack-name) | да |  |
| `when` | [объект](#schema-knowledge-pack-profile-when) |  |  |
| `title` | `string` |  |  |
| `attributes` | [`knowledge-pack/attributes`](#schema-knowledge-pack-attributes) | да |  |

### `knowledge-pack/profile.when` { #schema-knowledge-pack-profile-when }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `attr` | `string` | да |  |
| `equals` | `string` \| `number` \| `boolean` | да |  |

### `knowledge-pack/expiry` { #schema-knowledge-pack-expiry }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | [`knowledge-pack/name`](#schema-knowledge-pack-name) | да |  |
| `role` | `string` |  | Роль, которой ставится задача |
| `leadDays` | `integer` |  |  |
<!-- /generated:schema-knowledge-pack -->

## Общие типы { #common }

Определения, на которые ссылаются несколько видов.

<!-- generated:schema-common -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `package-sdk/schema/v1/object.schema.json`.

### `displayName` { #schema-displayname }

Значение: `string`.

### `duration` { #schema-duration }

Длительность ISO 8601, например P3D, PT4H

Значение: `string`.

### `envOrUuid` { #schema-envoruuid }

UUID или ${ПЕРЕМЕННАЯ} установки (топология окружения в пакет не пишется)

Значение: `string`.

### `jsonSchema` { #schema-jsonschema }

JSON Schema документа (draft 2020-12). Удалённые $ref ядро отвергает.

Значение: `object`.

### `lifecycle` { #schema-lifecycle }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `statuses` | array of [объект](#schema-lifecycle-statuses-item) | да |  |
| `transitions` | array of [объект](#schema-lifecycle-transitions-item) |  |  |
| `initialStatus` | [`statusKey`](#schema-statuskey) |  |  |

### `lifecycle.statuses[]` { #schema-lifecycle-statuses-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | [`statusKey`](#schema-statuskey) | да |  |
| `category` | `string` | да |  |
| `displayName` | `string` |  |  |

### `lifecycle.transitions[]` { #schema-lifecycle-transitions-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `from` | [`statusKey`](#schema-statuskey) | да |  |
| `to` | array of [`statusKey`](#schema-statuskey) | да |  |

### `mediaType` { #schema-mediatype }

Media type в нижнем регистре; маска */* или type/* допустима

Значение: `string`.

### `ruleKey` { #schema-rulekey }

Ключ правила в tenant'е

Значение: `string`.

### `slug` { #schema-slug }

Значение: `string`.

### `statusKey` { #schema-statuskey }

Значение: `string`.

### `typeKey` { #schema-typekey }

Ключ типа: латиница в нижнем регистре, цифры, _ и -

Значение: `string`.
<!-- /generated:schema-common -->

## Тест пакета (`tests/*.test.yaml`) { #test-file }

<!-- generated:schema-test -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `package-sdk/schema/v1/test.schema.json`.

### `test` { #schema-test }

Файл &lt;имя&gt;.test.yaml в каталоге tests/ пакета. Прогоняет ядро (POST /packages:test) тем же движком, что живой прогон, в песочнице: задачи, approvals и таймеры — в памяти, скиллы, агенты и память — заглушки, проверенные по схемам каталога, время виртуальное. Побочных эффектов нет.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `$schema` | `string` |  |  |
| `process` | `string` |  | Ключ процесса пакета |
| `version` | `integer` |  | По умолчанию — версия в пакете |
| `name` | `string` | да |  |
| `description` | `string` |  |  |
| `subject` | `process` \| `rule` \| `taskType` |  | Что проверяет тест: процесс (по умолчанию), правило вывода работы или тип задачи (исходы гейтов, критерии приёмки, действия завершения). По умолчанию `process`. |
| `rule` | `string` |  | Ключ WorkRule пакета (subject: rule) |
| `taskType` | `string` |  | Ключ TaskType пакета (subject: taskType) |
| `given` | `object` |  |  |
| `mocks` | [объект](#schema-test-mocks) |  |  |
| `steps` | array of `object` | да |  |
| `coverage` | [объект](#schema-test-coverage) |  |  |

Условия:

| Условие | Следствие |
|---|---|
| не (`subject` ∈ `rule`, `taskType`) | обязательно `process`; `given`: [`processGiven`](#schema-processgiven); `steps`: array of [`testStep`](#schema-teststep) |
| `subject` = `rule` | обязательно `rule`; `given`: [`ruleGiven`](#schema-rulegiven); `steps`: array of [`ruleStep`](#schema-rulestep) |
| `subject` = `taskType` | обязательно `taskType`; `given`: [`taskTypeGiven`](#schema-tasktypegiven); `steps`: array of [`taskTypeStep`](#schema-tasktypestep) |

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

### `processGiven` { #schema-processgiven }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `clock` | `string` (date-time) |  | Начальное виртуальное время |
| `data` | `object` |  | Начальные данные экземпляра (без события старта) |
| `stage` | `string` |  | Начать с открытой стадии |
| `fromInstance` | `string` |  | Только пробный прогон на стенде: состояние копируется из живого экземпляра |
| `calendar` | `string` |  | Ключ календаря вместо календаря процесса |
| `principals` | map → array of `string` |  | Роль → вымышленные principal теста (для назначений и разделения обязанностей) |

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
| `sla` | map → `ok` \| `warning` \| `breached` \| `paused` |  | Состояние срока: id шага → состояние его открытой попытки; ключ process — срок процесса (spec.due) |
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

### `ruleGiven` { #schema-rulegiven }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `clock` | `string` (date-time) |  |  |
| `variables` | [`variables`](#schema-variables) |  |  |
| `task` | [объект](#schema-rulegiven-task) |  | Задача, заведённая до входа: событие без taskId в payload — о ней |
| `schedule` | [объект](#schema-rulegiven-schedule) |  | Вход — срабатывание расписания правила (trigger.kind: schedule) |
| `observation` | [объект](#schema-rulegiven-observation) |  |  |
| `event` | [объект](#schema-rulegiven-event) |  |  |

Ровно одно из: `observation`, `event`, `schedule`.

### `ruleGiven.task` { #schema-rulegiven-task }

Задача, заведённая до входа: событие без taskId в payload — о ней

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` | да | Ключ типа задачи пакета или tenant'а |
| `title` | `string` |  |  |
| `status` | `string` |  |  |
| `assignee` | `string` |  | agent:&lt;key&gt; или вымышленный principal |
| `customFields` | `object` |  |  |

### `ruleGiven.schedule` { #schema-rulegiven-schedule }

Вход — срабатывание расписания правила (trigger.kind: schedule)

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `at` | `string` (date-time) |  | Время слота; по умолчанию clock |

### `ruleGiven.observation` { #schema-rulegiven-observation }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | `string` | да |  |
| `data` | `object` |  |  |
| `content` | `string` |  |  |
| `source` | `string` |  |  |
| `externalRef` | `object` |  |  |

### `ruleGiven.event` { #schema-rulegiven-event }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` | да |  |
| `payload` | `object` |  |  |

### `variables` { #schema-variables }

Значения переменных установки для теста; остальные — default из манифеста

Значение: map → `string`.

### `ruleStep` { #schema-rulestep }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `expect` | [объект](#schema-rulestep-expect) | да |  |

### `ruleStep.expect` { #schema-rulestep-expect }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `result` | `string` |  | Итог оценки правила ядра (как result события rule.evaluated) |
| `ensureWork` | array of [`workExpectation`](#schema-workexpectation) |  |  |
| `invokeSkill` | array of [`skillExpectation`](#schema-skillexpectation) |  |  |
| `noSideEffects` | = `true` |  |  |

### `workExpectation` { #schema-workexpectation }

Ожидаемая работа: заданные поля сравниваются, незаданные не проверяются

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` |  |  |
| `title` | `string` |  |  |
| `assignee` | `string` |  | agent:&lt;key&gt;, роль теста или вымышленный principal |
| `customFields` | `object` |  |  |
| `relation` | `object` |  |  |

### `skillExpectation` { #schema-skillexpectation }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `skill` | `string` | да |  |
| `inputs` | `object` |  | Подмножество входа вызова |

### `taskTypeGiven` { #schema-tasktypegiven }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `clock` | `string` (date-time) |  |  |
| `variables` | [`variables`](#schema-variables) |  |  |
| `task` | [объект](#schema-tasktypegiven-task) |  |  |
| `artifacts` | array of [объект](#schema-tasktypegiven-artifacts-item) |  |  |
| `principals` | map → array of `string` |  | Роль → вымышленные principal теста |

### `taskTypeGiven.task` { #schema-tasktypegiven-task }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `title` | `string` |  |  |
| `status` | `string` |  |  |
| `assignee` | `string` |  |  |
| `customFields` | `object` |  |  |

### `taskTypeGiven.artifacts[]` { #schema-tasktypegiven-artifacts-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | `string` |  |  |
| `type` | `string` | да |  |
| `metadata` | `object` |  |  |
| `content` | `string` |  | Содержимое (текст): артефакт с сохранённым содержимым, как после загрузки |
| `mediaType` | `string` |  | Тип содержимого (text/markdown, application/json, …) |

### `taskTypeStep` { #schema-tasktypestep }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `approve` | [объект](#schema-tasktypestep-approve) |  |  |
| `verify` | [объект](#schema-tasktypestep-verify) |  | Итог критерия приёмки типа |
| `complete` | [объект](#schema-tasktypestep-complete) |  |  |
| `expect` | [объект](#schema-tasktypestep-expect) |  |  |

Ровно одно из: `approve`, `verify`, `complete`, `expect`.

### `taskTypeStep.approve` { #schema-tasktypestep-approve }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `gate` | `string` |  | По умолчанию `default`. |
| `decision` | `approved` \| `rejected` | да |  |
| `by` | `string` |  |  |
| `comment` | `string` |  |  |

### `taskTypeStep.verify` { #schema-tasktypestep-verify }

Итог критерия приёмки типа

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `check` | `string` | да |  |
| `result` | `passed` \| `failed` | да |  |
| `output` | `object` |  |  |

### `taskTypeStep.complete` { #schema-tasktypestep-complete }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `output` | `object` |  | Выход завершения (completionSchema) |

### `taskTypeStep.expect` { #schema-tasktypestep-expect }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `ensureWork` | array of [`workExpectation`](#schema-workexpectation) |  |  |
| `invokeSkill` | array of [`skillExpectation`](#schema-skillexpectation) |  |  |
| `status` | [объект](#schema-tasktypestep-expect-status) |  |  |
| `comments` | array of `string` |  | Подстроки комментариев, оставленных исходами |
| `noSideEffects` | = `true` |  |  |

### `taskTypeStep.expect.status` { #schema-tasktypestep-expect-status }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | `string` |  |  |
| `category` | `backlog` \| `active` \| `blocked` \| `terminal_success` \| `terminal_cancelled` |  |  |
<!-- /generated:schema-test -->

## Фиксация источников (`packages.lock`) { #lock }

Файл пишет `package-sdk lock`; руками его не правят.

<!-- generated:schema-lock -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `package-sdk/schema/v1/lock.schema.json`.

### `lock` { #schema-lock }

Файл packages.lock рядом с файлом установки. Пишет package-sdk lock; для каждого пакета — источник, коммит и хэш содержимого. План строится по lock: для источника git без записи — lock_required, при расхождении хэша — отказ.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `format` | = `package-sdk.lock/v1` | да |  |
| `installation` | `string` |  | Ключ установки, для которой снята фиксация |
| `packages` | array of [объект](#schema-lock-packages-item) | да |  |

### `lock.packages[]` { #schema-lock-packages-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | `string` | да |  |
| `version` | `string` | да |  |
| `source` | [объект `{path}`](#schema-lock-packages-item-source-1) или [объект `{git, ref, path}`](#schema-lock-packages-item-source-2) | да | Откуда пакет: {path} — каталог относительно файла установки; {git, ref, path?} — тег git и подкаталог пакета в репозитории (то же имя path, что в установке) |
| `commit` | `string` |  | Коммит источника git |
| `contentHash` | `string` | да | sha256 канонического набора файлов пакета: пути по порядку и их байты, без .layout/ (та же функция, что installHash записи связей) |

### `lock.packages[].source (1)` { #schema-lock-packages-item-source-1 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `path` | `string` | да |  |

### `lock.packages[].source (2)` { #schema-lock-packages-item-source-2 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `git` | `string` | да |  |
| `ref` | `string` | да |  |
| `path` | `string` |  |  |
<!-- /generated:schema-lock -->

## План установки (`plan --out`) { #plan }

Документ пишет `package-sdk plan --out`; `package-sdk apply --plan` применяет его только без правок.

<!-- generated:schema-plan -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `package-sdk/schema/v1/plan.schema.json`.

### `plan` { #schema-plan }

Один документ изменений всех видов установки. Пишет package-sdk plan --out; применяется только package-sdk apply --plan без правок: planHash — хэш документа без самого поля, правленый файл отвергается. Значения переменных в план не пишутся, только их хэш.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `format` | = `package-sdk.plan/v1` | да |  |
| `server` | `string` | да | Стенд: https, http — только localhost |
| `engines` | map → `string` |  | Версии компонентов стенда на момент плана (из openapi.json) |
| `createdAt` | `string` (date-time) | да |  |
| `installation` | `string` |  | Ключ установки (Installation.key) |
| `install` | `string` |  | Файл установки относительно файла плана: apply --plan собирает по нему пакеты заново и сверяет lockHash и variablesHash |
| `lockHash` | [`plan/hash`](#schema-plan-hash) |  |  |
| `variablesHash` | [`plan/hash`](#schema-plan-hash) |  |  |
| `overwriteConsole` | `boolean` |  | plan --overwrite-console: перезаписать поля объектов ядра, которые человек правил в консоли после прошлого применения; без флага ядро их сохраняет. package-sdk plan пишет поле всегда, false по умолчанию; план прежнего формата без поля применяется как false. Входит в planHash; с ним же строится и применяется план ядра |
| `sections` | array of [`plan/section`](#schema-plan-section) | да |  |
| `planHash` | [`plan/hash`](#schema-plan-hash) | да |  |

### `plan/hash` { #schema-plan-hash }

Значение: `string`.

### `plan/section` { #schema-plan-section }

Значение: [объект `{kind, changes}`](#schema-plan-section-1) или [объект `{kind, package, planHash, plan, workspaceId, replayLimit}`](#schema-plan-section-2) или [объект `{kind, changes}`](#schema-plan-section-3) или [объект `{kind, register, enable}`](#schema-plan-section-4) или [объект `{kind, items}`](#schema-plan-section-5).

### `plan/section (1)` { #schema-plan-section-1 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | = `catalog` | да |  |
| `changes` | array of [`plan/change`](#schema-plan-change) | да |  |

### `plan/section (2)` { #schema-plan-section-2 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | = `core` | да |  |
| `package` | `string` | да |  |
| `planHash` | [`plan/hash`](#schema-plan-hash) | да |  |
| `plan` | `object` | да | Ответ /packages:plan ядра как есть |
| `workspaceId` | `string` |  | workspaceId запроса плана — с ним же идёт /packages:apply |
| `replayLimit` | `integer` |  | replayLimit запроса плана — с ним план ядра строится заново перед применением |

### `plan/section (3)` { #schema-plan-section-3 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | = `notification-rules` | да |  |
| `changes` | array of [`plan/change`](#schema-plan-change) | да |  |

### `plan/section (4)` { #schema-plan-section-4 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | = `knowledge` | да |  |
| `register` | array of [`plan/change`](#schema-plan-change) |  |  |
| `enable` | array of [объект](#schema-plan-section-4-enable-item) |  |  |

### `plan/section (4).enable[]` { #schema-plan-section-4-enable-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `workspace` | `string` | да |  |
| `packs` | array of `string` | да |  |
| `current` | array of `string` |  |  |

### `plan/section (5)` { #schema-plan-section-5 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | = `retire` | да |  |
| `items` | array of [`plan/change`](#schema-plan-change) | да |  |

### `plan/change` { #schema-plan-change }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `package` | `string` |  |  |
| `kind` | `string` | да |  |
| `key` | `string` | да |  |
| `operation` | `create` \| `version` \| `patch` \| `deprecate` \| `enable` \| `disable` \| `register` \| `retire` \| `unchanged` | да |  |
| `fields` | array of `string` |  | Поля, которые меняются |
| `expected` | любое |  | Что установщик ожидает увидеть на стенде перед записью (для plan_stale) |
<!-- /generated:schema-plan -->

## Уточнение шаблона загрузки (`templates/<вид>.yaml`) { #knowledge-template }

<!-- generated:schema-knowledge-template -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `package-sdk/schema/v1/knowledge-template.schema.json`.

### `knowledge-template` { #schema-knowledge-template }

Необязательные данные пакета templates/&lt;вид&gt;.yaml. Шаблон строится генератором из JSON Schema вида; уточнение меняет только подачу: заголовки, порядок, подсказки, примеры и дополнительные запрещённые колонки. Колонок, которых нет в схеме вида, уточнение не добавляет.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `pack` | `string` | да | Пакет онтологии и версия вида, например company@1 |
| `kind` | `string` | да |  |
| `title` | `string` |  | Название листа и файла шаблона |
| `instructions` | `string` |  | Текст листа «Инструкция» перед сгенерированным описанием колонок |
| `columns` | array of [объект](#schema-knowledge-template-columns-item) |  | Порядок колонок; не перечисленные идут после в порядке схемы |
| `examples` | array of `object` |  | Строки-примеры листа шаблона: field → значение |
| `forbiddenColumns` | array of `string` |  | Запрещённые заголовки сверх общего списка персональных данных (фио, фамилия, паспорт, снилс, дата рождения, адрес, телефон, e-mail) |

### `knowledge-template.columns[]` { #schema-knowledge-template-columns-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `field` | `string` | да | key — естественный ключ, title — имя, attributes.&lt;путь&gt; — атрибут, links.&lt;связь&gt; — ключи связанных сущностей |
| `header` | `string` |  |  |
| `hint` | `string` |  |  |
| `example` | `string` \| `number` \| `boolean` |  |  |
| `separator` | `string` |  | Разделитель списка в ячейке (коды, ключи связей); по умолчанию «;» |
<!-- /generated:schema-knowledge-template -->

## См. также

- [Команды package-sdk](package-sdk-cli.md)
- [Анатомия пакета](../packages/anatomy.md)
- [Процессы](../processes/index.md)
- [Выражения](../processes/expressions.md)
- [Тесты пакета](../packages/testing.md)
- [Пакеты каталога](../control-plane/catalog-packages.md)
