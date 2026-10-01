# Команды package-sdk

Справочник команд инструмента автора пакетов `package-sdk`: использование,
аргументы, значения по умолчанию и подкоманды. Таблицы построены из парсеров
командной строки самого инструмента и повторяют `package-sdk <команда> --help`.
Статья для авторов пакетов; порядок работы с командами описан в [Пути
автора](../packages/index.md#author-path), установка инструмента — в [Пакете за
10 минут](../packages/quickstart.md).

!!! note "Лишние зависимости ставятся по требованию"
    Инструмент ставится без дополнительных зависимостей; `sandbox` и проверка
    ядром требуют extra `sandbox`, `mcp` — extra `mcp`, выгрузка и план со
    стендом через credential MCP-плагина — extra `connector`. Всё сразу —
    `package-sdk[all]` (см. [Тесты пакета](../packages/testing.md#install)).

## Команды

<!-- generated:cli-package-sdk -->
_Раздел генерируется из кода — не правьте его руками._

Команд: 16. Источник: `package-sdk/src/package_sdk` (парсеры argparse).

| Команда | Назначение |
|---|---|
| [`init`](#cli-init) | заготовка пакета: манифест, процесс с тестом, CI, README |
| [`add`](#cli-add) | заготовка объекта любого вида каталога |
| [`check`](#cli-check) | проверить пакеты: схема и ссылки; с --server — ещё и ядром |
| [`test`](#cli-test) | пирамида тестов пакета одной командой: проверка, скиллы, интеграция, сценарии |
| [`lock`](#cli-lock) | зафиксировать источники установки: коммит и хэш содержимого (packages.lock) |
| [`cache`](#cli-cache) | кэш источников git (package-sdk cache prune) |
| [`plan`](#cli-plan) | построить единый план установки (все виды) и сохранить его с хэшем |
| [`apply`](#cli-apply) | применить ровно сохранённый план (после подтверждения человека) |
| [`export`](#cli-export) | выгрузить объекты из Control Plane в пакет |
| [`describe`](#cli-describe) | предпосылки установки пакета: переменные, узлы агентов, онтологии, зависимости |
| [`docs`](#cli-docs) | сгенерированные разделы README пакета |
| [`migrate-expr`](#cli-migrate-expr) | перевести прежние выражения пакета в CEL (diff; --write) |
| [`edit`](#cli-edit) | правка файлов пакета с сохранением стиля файла |
| [`sandbox`](#cli-sandbox) | тесты пакета кодом ядра в процессе, без стенда |
| [`image`](#cli-image) | Dockerfile образа интеграции пакета: наблюдатель или хост скиллов |
| [`mcp`](#cli-mcp) | MCP-сервер автора пакетов по stdio; стенды — PACKAGE_SDK_SERVERS, корень сессии — PACKAGE_SDK_ROOT, корни клиента или текущий каталог |

### `package-sdk init` { #cli-init }

заготовка пакета: манифест, процесс с тестом, CI, README

```text
usage: package-sdk init [-h] [--key KEY] [--display-name DISPLAY_NAME] [--license LICENSE]
                        [--integration] [--image] [--database]
                        dir
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `dir` | да |  | каталог пакета (новый или пустой) |
| `--key KEY` |  |  | ключ пакета; по умолчанию — имя каталога |
| `--display-name DISPLAY_NAME` |  |  | название пакета для людей |
| `--license LICENSE` |  |  | лицензия пакета (идентификатор SPDX) |
| `--integration` |  |  | код интеграции: наблюдатель и описание агента |
| `--image` |  |  | Dockerfile образа интеграции |
| `--database` |  |  | сервис PostgreSQL в CI для сценариев правил и типов задач (по умолчанию — если они уже есть в каталоге) |

### `package-sdk add` { #cli-add }

заготовка объекта любого вида каталога

```text
usage: package-sdk add [-h] [--package PACKAGE] kind key
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `kind` | да |  | вид: TaskType, task-type, rule, process, … |
| `key` | да |  | ключ объекта |
| `--package PACKAGE` |  | `.` | каталог пакета (по умолчанию текущий) |

### `package-sdk check` { #cli-check }

проверить пакеты: схема и ссылки; с --server — ещё и ядром

```text
usage: package-sdk check [-h] [--install INSTALL] [--package PACKAGE] [--server SERVER]
                         [--env ENV] [--workspace WORKSPACE] [--json] [--schema-only]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--install INSTALL` |  |  | файл установки; без него — все пакеты packages/ |
| `--package PACKAGE` |  |  | пакет (каталог или ключ); можно несколько |
| `--server SERVER` |  |  | Control Plane: проверка процессов ядром (checkOnly), если оно умеет |
| `--env ENV` |  |  | откуда брать ${ПЕРЕМЕННЫЕ} пакета (по умолчанию — окружение) |
| `--workspace WORKSPACE` |  |  | workspace, чьи роли и календари читает проверка ядром |
| `--json` |  |  | ошибки — JSON {code, severity, path, file, line, message, hint} |
| `--schema-only` |  |  | без кода ядра: только схема и ссылки (иначе отсутствие ядра — ошибка) |

### `package-sdk test` { #cli-test }

пирамида тестов пакета одной командой: проверка, скиллы, интеграция, сценарии

```text
usage: package-sdk test [-h] [--package PACKAGE] [--install INSTALL] [--test TEST]
                        [--server SERVER] [--env ENV] [--workspace WORKSPACE]
                        [--database-url DATABASE_URL] [--json]
                        [paths ...]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `paths`… |  |  | пакеты: каталоги с package.yaml или ключи |
| `--package PACKAGE` |  |  | пакет (каталог или ключ); можно несколько |
| `--install INSTALL` |  |  | файл установки: все её пакеты |
| `--test TEST` |  |  | только сценарий с этим именем или файлом |
| `--server SERVER` |  |  | Control Plane: сценарии исполняет сервер; без него — песочница |
| `--env ENV` |  | `.env` | переменные установки |
| `--workspace WORKSPACE` |  |  | с --server: workspace, чьи роли, календари и экземпляры читает прогон |
| `--database-url DATABASE_URL` |  |  | песочница: пустая база PostgreSQL для сценариев правил и типов задач (или PACKAGE_SDK_SANDBOX_DATABASE_URL) |
| `--json` |  |  | отчёт пирамиды документом JSON |

### `package-sdk lock` { #cli-lock }

зафиксировать источники установки: коммит и хэш содержимого (packages.lock)

```text
usage: package-sdk lock [-h] --install INSTALL
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--install INSTALL` | да |  | файл установки |

### `package-sdk cache` { #cli-cache }

кэш источников git (package-sdk cache prune)

```text
usage: package-sdk cache [-h] {prune} ...
```

Подкоманды: [`prune`](#cli-cache-prune).

#### `package-sdk cache prune` { #cli-cache-prune }

удалить выгрузки, на которые не ссылается ни один packages.lock текущего каталога

```text
usage: package-sdk cache prune [-h] [--all] [--lock LOCK]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--all` |  |  | удалить весь кэш: выгрузки и зеркала источников |
| `--lock LOCK` |  |  | учесть этот lock-файл (можно несколько); по умолчанию — все packages.lock под текущим каталогом |

### `package-sdk plan` { #cli-plan }

построить единый план установки (все виды) и сохранить его с хэшем

```text
usage: package-sdk plan [-h] --install INSTALL --server SERVER --out OUT [--env ENV]
                        [--workspace WORKSPACE] [--replay-limit REPLAY_LIMIT]
                        [--overwrite-console] [--json]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--install INSTALL` | да |  | файл установки |
| `--server SERVER` | да |  | — |
| `--out OUT` | да |  | файл плана (package-sdk.plan/v1) для apply --plan |
| `--env ENV` |  | `.env` | откуда брать ${ПЕРЕМЕННЫЕ} пакета |
| `--workspace WORKSPACE` |  |  | workspace процессов пакета (workspaceId ядра) |
| `--replay-limit REPLAY_LIMIT` |  | `50` | экземпляров на процесс для replay (0–200) |
| `--overwrite-console` |  |  | перезаписать поля, которые человек правил в консоли после прошлого применения (по умолчанию они сохраняются); флаг хранится в плане под его хэшем |
| `--json` |  |  | план документом JSON |

### `package-sdk apply` { #cli-apply }

применить ровно сохранённый план (после подтверждения человека)

```text
usage: package-sdk apply [-h] --plan PLAN --server SERVER [--env ENV]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--plan PLAN` | да |  | файл плана от plan --out |
| `--server SERVER` | да |  | стенд; должен совпасть с тем, для которого построен план |
| `--env ENV` |  | `.env` | откуда брать ${ПЕРЕМЕННЫЕ} пакета |

### `package-sdk export` { #cli-export }

выгрузить объекты из Control Plane в пакет

```text
usage: package-sdk export [-h] [--server SERVER] [--env ENV] [--workspace WORKSPACE] --kind
                          {KnowledgePack,WorkspaceType,Capability,Role,Skill,ArtifactType,TaskType,Agent,ProjectTemplate,Calendar,Process,WorkRule,NotificationRule}
                          --key KEY [--version VERSION] --package PACKAGE
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--server SERVER` |  |  | Control Plane; для NotificationRule не нужен |
| `--env ENV` |  | `.env` | файл переменных установки: NOTIFICATION_SERVICE_URL для NotificationRule, значения ${…} — чтобы выгрузка Process и Calendar вернула их ссылками на переменные |
| `--workspace WORKSPACE` |  |  | workspace плана ядра для полей консоли (Process и Calendar) |
| `--kind KIND` | да |  | значения: `KnowledgePack`, `WorkspaceType`, `Capability`, `Role`, `Skill`, `ArtifactType`, `TaskType`, `Agent`, `ProjectTemplate`, `Calendar`, `Process`, `WorkRule`, `NotificationRule` |
| `--key KEY` | да |  | можно несколько раз |
| `--version VERSION` |  |  | версия (по умолчанию новейшая активная) |
| `--package PACKAGE` | да |  | каталог пакета, например packages/&lt;пакет&gt; |

### `package-sdk describe` { #cli-describe }

предпосылки установки пакета: переменные, узлы агентов, онтологии, зависимости

```text
usage: package-sdk describe [-h] [--env-example] [--json] path
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `path` | да |  | каталог пакета |
| `--env-example` |  |  | заготовка файла переменных установки |
| `--json` |  |  | то же в JSON |

### `package-sdk docs` { #cli-docs }

сгенерированные разделы README пакета

```text
usage: package-sdk docs [-h] [--write | --check] path
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `path` | да |  | каталог пакета |
| `--write` |  |  | обновить раздел в README.md; не вместе с `--check` |
| `--check` |  |  | 1, если раздел README устарел; не вместе с `--write` |

### `package-sdk migrate-expr` { #cli-migrate-expr }

перевести прежние выражения пакета в CEL (diff; --write)

```text
usage: package-sdk migrate-expr [-h] --package PACKAGE [--write]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--package PACKAGE` | да |  | пакет (каталог или ключ) |
| `--write` |  |  | записать с сохранением файла |

### `package-sdk edit` { #cli-edit }

правка файлов пакета с сохранением стиля файла

```text
usage: package-sdk edit [-h] [--json] [--dry-run]
                        {add-step,add-stage,add-decision-row,add-rule,add-form-field,rename,set}
                        ...
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--json` |  |  | результат и ошибки — JSON |
| `--dry-run` |  |  | показать diff, ничего не писать |

Подкоманды: [`add-step`](#cli-edit-add-step), [`add-stage`](#cli-edit-add-stage), [`add-decision-row`](#cli-edit-add-decision-row), [`add-rule`](#cli-edit-add-rule), [`add-form-field`](#cli-edit-add-form-field), [`rename`](#cli-edit-rename), [`set`](#cli-edit-set).

#### `package-sdk edit add-step` { #cli-edit-add-step }

добавить шаг в стадию или блок шага

```text
usage: package-sdk edit add-step [-h] --file FILE [--json] [--dry-run] --in TARGET [--block BLOCK]
                                 --step STEP [--after AFTER] [--before BEFORE]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--file FILE` | да |  | файл процесса (processes/&lt;ключ&gt;.yaml) |
| `--json` |  |  | — |
| `--dry-run` |  |  | — |
| `--in TARGET` | да |  | id стадии, шага с do, ветви fork или таймера |
| `--block BLOCK` |  |  | имя блока: steps\|discretionary у стадии, do\|onCompensate у шага |
| `--step STEP` | да |  | YAML (flow или block); @файл — прочитать из файла |
| `--after AFTER` |  |  | — |
| `--before BEFORE` |  |  | — |

#### `package-sdk edit add-stage` { #cli-edit-add-stage }

добавить стадию

```text
usage: package-sdk edit add-stage [-h] --file FILE [--json] [--dry-run] --stage STAGE
                                  [--after AFTER] [--before BEFORE]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--file FILE` | да |  | файл процесса (processes/&lt;ключ&gt;.yaml) |
| `--json` |  |  | — |
| `--dry-run` |  |  | — |
| `--stage STAGE` | да |  | YAML (flow или block); @файл — прочитать из файла |
| `--after AFTER` |  |  | — |
| `--before BEFORE` |  |  | — |

#### `package-sdk edit add-decision-row` { #cli-edit-add-decision-row }

добавить строку таблицы решений

```text
usage: package-sdk edit add-decision-row [-h] --file FILE [--json] [--dry-run] --table TABLE --row
                                         ROW [--index INDEX]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--file FILE` | да |  | файл процесса (processes/&lt;ключ&gt;.yaml) |
| `--json` |  |  | — |
| `--dry-run` |  |  | — |
| `--table TABLE` | да |  | — |
| `--row ROW` | да |  | YAML (flow или block); @файл — прочитать из файла |
| `--index INDEX` |  |  | позиция строки (по умолчанию — в конец) |

#### `package-sdk edit add-rule` { #cli-edit-add-rule }

добавить правило: строку таблицы (--table) или реакцию на событие (--on-event)

```text
usage: package-sdk edit add-rule [-h] --file FILE [--json] [--dry-run] [--table TABLE] [--row ROW]
                                 [--on-event ON_EVENT] [--index INDEX]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--file FILE` | да |  | файл процесса (processes/&lt;ключ&gt;.yaml) |
| `--json` |  |  | — |
| `--dry-run` |  |  | — |
| `--table TABLE` |  |  | — |
| `--row ROW` |  |  | YAML (flow или block); @файл — прочитать из файла |
| `--on-event ON_EVENT` |  |  | YAML (flow или block); @файл — прочитать из файла |
| `--index INDEX` |  |  | — |

#### `package-sdk edit add-form-field` { #cli-edit-add-form-field }

добавить поле в форму человеческого шага

```text
usage: package-sdk edit add-form-field [-h] --file FILE [--json] [--dry-run] --step STEP_ID --name
                                       NAME --schema SCHEMA [--required] [--label LABEL]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--file FILE` | да |  | файл процесса (processes/&lt;ключ&gt;.yaml) |
| `--json` |  |  | — |
| `--dry-run` |  |  | — |
| `--step STEP_ID` | да |  | — |
| `--name NAME` | да |  | — |
| `--schema SCHEMA` | да |  | YAML (flow или block); @файл — прочитать из файла |
| `--required` |  |  | — |
| `--label LABEL` |  |  | подпись в uischema, если у формы есть uischema.elements |

#### `package-sdk edit rename` { #cli-edit-rename }

переименовать элемент процесса или объект пакета

```text
usage: package-sdk edit rename [-h] [--file FILE] [--json] [--dry-run] [--package PACKAGE]
                               [--kind KIND] --from OLD --to NEW [--no-migration]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--file FILE` |  |  | файл процесса (processes/&lt;ключ&gt;.yaml) |
| `--json` |  |  | — |
| `--dry-run` |  |  | — |
| `--package PACKAGE` |  |  | каталог пакета — переименовать объект (renames в package.yaml) |
| `--kind KIND` |  |  | вид объекта для --package (по умолчанию Process) |
| `--from OLD` | да |  | — |
| `--to NEW` | да |  | — |
| `--no-migration` |  |  | не дописывать migrations (процесс ещё не опубликован) |

#### `package-sdk edit set` { #cli-edit-set }

записать значение по пути

```text
usage: package-sdk edit set [-h] --file FILE [--json] [--dry-run] --path PATH --value VALUE
                            [--string]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--file FILE` | да |  | файл процесса (processes/&lt;ключ&gt;.yaml) |
| `--json` |  |  | — |
| `--dry-run` |  |  | — |
| `--path PATH` | да |  | spec.stages[go-no-go].exit; в скобках индекс или id |
| `--value VALUE` | да |  | значение YAML |
| `--string` |  |  | значение — строка как есть, без разбора YAML |

### `package-sdk sandbox` { #cli-sandbox }

тесты пакета кодом ядра в процессе, без стенда

```text
usage: package-sdk sandbox [-h] [--test TEST] [--json] [--env ENV] [--database-url DATABASE_URL]
                           [packages ...]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `packages`… |  |  | ключи пакетов или каталоги с package.yaml; по умолчанию — все пакеты с тестами |
| `--test TEST` |  |  | путь файла теста в пакете (tests/&lt;имя&gt;.test.yaml); можно несколько раз |
| `--json` |  |  | ответы PackageTestOut в JSON |
| `--env ENV` |  | `.env` | файл переменных установки |
| `--database-url DATABASE_URL` |  |  | пустая база PostgreSQL для тестов правил и типов задач (или PACKAGE_SDK_SANDBOX_DATABASE_URL) |

### `package-sdk image` { #cli-image }

Dockerfile образа интеграции пакета: наблюдатель или хост скиллов

```text
usage: package-sdk image [-h] {observer,skills} ...
```

Подкоманды: [`observer`](#cli-image-observer), [`skills`](#cli-image-skills).

#### `package-sdk image observer` { #cli-image-observer }

Dockerfile образа observer

```text
usage: package-sdk image observer [-h] [--package PACKAGE] [--source SOURCE] [--base BASE]
                                  [--out OUT] [--entrypoint ENTRYPOINT]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--package PACKAGE` |  | `.` | каталог пакета |
| `--source SOURCE` |  |  | python-проект интеграции в пакете (по умолчанию integration/) |
| `--base BASE` |  |  | базовый образ поставки (иначе --build-arg при сборке); наблюдателя |
| `--out OUT` |  |  | куда записать; рядом, в каталоге пакета, пишется .dockerignore |
| `--entrypoint ENTRYPOINT` |  |  | наблюдатель модуль:функция — проверка при сборке |

#### `package-sdk image skills` { #cli-image-skills }

Dockerfile образа skills

```text
usage: package-sdk image skills [-h] [--package PACKAGE] [--source SOURCE] [--base BASE]
                                [--out OUT] --modules MODULES
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--package PACKAGE` |  | `.` | каталог пакета |
| `--source SOURCE` |  |  | python-проект интеграции в пакете (по умолчанию integration/) |
| `--base BASE` |  |  | базовый образ поставки (иначе --build-arg при сборке); раннера |
| `--out OUT` |  |  | куда записать; рядом, в каталоге пакета, пишется .dockerignore |
| `--modules MODULES` | да |  | модули или entrypoint'ы скиллов через запятую |

### `package-sdk mcp` { #cli-mcp }

MCP-сервер автора пакетов по stdio; стенды — PACKAGE_SDK_SERVERS, корень сессии — PACKAGE_SDK_ROOT, корни клиента или текущий каталог

```text
usage: package-sdk mcp [-h]
```
<!-- /generated:cli-package-sdk -->

## Токены и переменные

| Переменная | Кто читает | Назначение |
|---|---|---|
| `CP_TOKEN` | `plan`, `apply`, `export`, `test --server`, `check --server` | access token audience `control-plane`; без неё — credential MCP-плагина через extra `connector` |
| `NOTIFY_TOKEN` | `plan`, `apply`, `export --kind NotificationRule` | access token audience `notification-service` (scope `notifications:admin`) для правил уведомлений |
| `PACKAGE_SDK_SANDBOX_DATABASE_URL` | `test`, `sandbox` | пустая база PostgreSQL песочницы для сценариев правил и типов задач (то же, что `--database-url`) |

## См. также

- [Схема пакета](package-schema.md)
- [Путь автора](../packages/index.md#author-path)
- [Тесты пакета](../packages/testing.md)
- [Установка и выпуск](../packages/install-and-release.md)
- [Автор пакетов в Claude Code](../packages/author-plugin.md)
