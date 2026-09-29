# Тесты пакета

Пакет процессов проверяется без стенда: ядро находит ошибки описания,
прогоняет тесты сценариев в песочнице с виртуальным временем и заглушками,
сравнивает новую версию с журналами живых экземпляров и показывает план
применения. Применяется ровно показанный план — по его хэшу. Статья для
авторов пакетов и администраторов инсталляции. Обоснование — TAI-ADR-0054
п.8, CP-ADR-0074 §10–11.

```mermaid
flowchart LR
    C[Проверка<br/>checkOnly] --> T[Тесты<br/>песочница] --> R[Replay<br/>по журналу] --> P[План<br/>planHash] --> A[Применение<br/>по хэшу]
    T -.->|пробный прогон| F[given.fromInstance]
```

Все шаги до применения **ничего не пишут**: транзакция ядра — только на
чтение, исходящих вызовов у песочницы нет.

## Проверка { #check }

Две ступени:

1. **Форма и ссылки — локально**, без стенда:
   `python3 tools/cp_packages.py check --package packages/<пакет>` сверяет
   файлы со схемой `packages/schema/v1` и ссылки между объектами пакета.
2. **Язык — в ядре**: с `--server` те же файлы уходят в
   `POST /api/v1/packages:test?checkOnly=true`. Ядро проверяет типы всех
   выражений, неизвестные поля данных, входы и выходы шагов против схемы
   данных, входы скиллов по их схемам, достижимость шагов и стадий, тупики,
   ссылки на типы задач, скиллы, календари и агента-личность, перекрытия и
   пробелы таблиц решений, а также регламенты `governedBy` через базу знаний.

```bash
python3 tools/cp_packages.py check --package packages/<пакет> \
    --server https://platform.example.com --json
```

Каждая находка — машиночитаемая, с местом в файле и подсказкой:

```json
{"code": "unknown_data_field", "severity": "error",
 "path": "/spec/stages/1/steps/0/output/as/decison",
 "file": "processes/purchase.yaml", "line": 42,
 "message": "data has no field decison", "hint": "did you mean decision?"}
```

| Группа | Коды (примеры) |
|---|---|
| форма | `schema_violation`, `invalid_yaml`, `invalid_document`, `unresolved_install_variable`, `unresolved_data_ref` |
| выражения | `expression_syntax_error`, `expression_type_error`, `expression_too_complex` |
| данные | `unknown_data_field`, `data_type_mismatch` |
| ссылки | `unknown_skill`, `unknown_task_type`, `unknown_agent`, `unknown_calendar`, `unknown_decision_table`, `skill_input_missing` |
| структура | `duplicate_element_id`, `element_kind_changed`, `unreachable_step`, `unreachable_stage`, `dead_end` |
| таблицы решений | `invalid_table_cell`, `table_overlap`; предупреждения `table_gap`, `table_rule_unreachable` |
| предупреждения | `process_owner_missing`, `element_removed`, `unwritten_data_field`, `unreachable_milestone`, `governed_by_unknown_document`, `governed_by_unchecked` |

Ошибка блокирует тесты и применение; предупреждения — нет.

## Формат теста

Тест — файл `tests/<имя>.test.yaml` пакета по схеме
`packages/schema/v1/test.schema.json`. Один файл — один сценарий одного
процесса.

```yaml
# yaml-language-server: $schema=../../schema/v1/test.schema.json
process: supplier-invoice
name: загрузивший счёт не согласует его оплату
given:
  clock: "2026-10-01T09:00:00+03:00"
  principals:                       # роль → вымышленные principal'ы теста
    accounting: [1a000000-0000-4000-8000-000000000001, 1a000000-0000-4000-8000-000000000002]
    finance-director: [1f000000-0000-4000-8000-000000000001]
mocks:
  skills:
    notify.send@1:
      - output: {notificationId: 0e000000-0000-4000-8000-000000000001, deliveries: []}
steps:
  - emit:
      observation: invoice.received
      payload:
        data: {invoice: "СЧ-1", supplier: "ООО «Поставщик»", supplierInn: "7701234567",
               amount: 45000, currency: RUB, uploadedBy: 1a000000-0000-4000-8000-000000000001}
  - complete: {step: check-invoice, by: 1a000000-0000-4000-8000-000000000002, output: {verdict: ok}}
  - approve:
      step: approve-payment
      by: 1a000000-0000-4000-8000-000000000001
      decision: approve
      expectRefused: separation_of_duties_violation
  - approve: {step: approve-payment, by: 1a000000-0000-4000-8000-000000000002, decision: approve}
  - expect:
      stages: {approval: completed, payment: open}
      data: {approval: approved}
coverage: {minimum: 60}
```

### `given` — начальное состояние

| Поле | Что задаёт |
|---|---|
| `clock` | начальное виртуальное время; без него — `2026-01-05T09:00:00Z`, чтобы тест всегда давал один ответ |
| `data` | начальные данные: явный старт экземпляра с ключом `test` без события старта |
| `principals` | роль → вымышленные principal'ы теста: кому назначаются задачи роли и кто держит роль при голосовании |
| `calendar` | ключ календаря вместо календаря процесса |
| `fromInstance` | пробный прогон: состояние копируется из живого экземпляра (см. [ниже](#dry-run)) |

### `mocks` — заглушки { #mocks }

Скиллы, агенты и база знаний в тесте — заглушки. Ответы берутся по порядку
вызовов; после последнего повторяется последний. `step` и `when` (CEL над
входом вызова) выбирают ответ для конкретного шага или входа.

```yaml
mocks:
  skills:
    docs.analyze@1:
      - output: {status: ok, summary: ok, risks: [], requirements: [], questions: [], stopFactors: []}
  agents:
    reviewer: [{output: {verdict: approve}}]
  recall:
    - step: recall-history
      when: input.anchors[0].key == '7700000001'
      output:
        nodes:
          - {kind: lesson, key: "lesson:purchase:0000000000025000007/1", text: Заказчик снижает цену на переторжке}
        edges: []
    - {output: {nodes: []}}           # всем остальным recall
```

| Ответ | Что значит |
|---|---|
| `output` | ответ. Выход заглушки скилла **сверяется со схемой выхода скилла** из каталога: не по схеме — тест падает, а не проходит. Ответ `recall` сверяется с формой ответа памяти |
| `error: {type, status, detail}` | скилл ответил ошибкой; у `recall` — таймаут шага с этой причиной |
| `timeout: true` | ответа нет — шаг ждёт своего таймаута |

Вызов без подходящей заглушки остаётся без ответа, как скилл, который ещё не
ответил. Ответ заглушки приходит следующим входом, после текущего.

### `steps` — сценарий

| Шаг | Что делает |
|---|---|
| `emit: {event или observation, source?, payload}` | подаёт событие так же, как живой цикл: старт или корреляция открытых экземпляров |
| `advance: P3D` | сдвигает виртуальное время; ожидающие таймеры срабатывают по порядку, каждый в свой момент |
| `advance: until:<id>` | двигает время до срабатывания таймера с этим id (или таймера этого элемента) |
| `complete: {step, by, output, cancel?}` | завершает задачу шага от имени исполнителя или держателя роли; `output` сверяется с формой шага и `fieldSchema` типа задачи; `cancel: true` — отмена |
| `approve: {step, by, decision, expectRefused?}` | голос в согласовании; `expectRefused` — ожидаемый код отказа ядра: `separation_of_duties_violation`, `not_eligible` |
| `expect: {…}` | ожидания (ниже) |

`expect` проверяет состояние после предыдущих шагов:

| Поле | Что сравнивается |
|---|---|
| `stages` | стадия → `open`, `completed`, `skipped`, `not_started` |
| `milestones` | достигнутые вехи |
| `tasks` | задачи: `step`, `status`, `assignee` (исполнитель или `role:<slug>`), `due` |
| `timers` | таймеры: `id`, `at`, `provisional` |
| `data` | путь в данных (`a.b` или `/a/b`) → значение |
| `events` | типы событий `process.*` с прошлого `expect` |
| `memory` | `recalled` — шаги `recall`, `remembered` — записи `remember` (частичное совпадение) |
| `status`, `outcome`, `error` | статус экземпляра, исход, тип ошибки |
| `noSideEffects: true` | прогон не сделал ни одной записи в базу |

Невыполнимый шаг (задачи нет, голос неожиданно отвергнут) останавливает тест;
несбывшееся ожидание — провал шага, но тест идёт дальше и показывает
`expected` и `actual`.

### Покрытие

Прогон считает покрытие по всем тестам процесса вместе и перечисляет
непройденное:

| Счётчик | Что считается |
|---|---|
| `elements` | стадии, шаги, вехи, таймеры |
| `transitions` | вход и выход стадий, `when`/`skip` шагов, ветви `listen` и таймауты, ответы и таймауты `recall`, `approved`/`rejected`, ветви `fork`, `correlate`, `onEvent` |
| `decisionRows` | строки таблиц решений |
| `handlers` | `catch`, `retry`, `onTimeout`, `onCompensate`, уровни эскалаций, `onDue` |

`coverage.minimum` теста — порог доли элементов процесса, которые проходит
этот тест, в процентах.

## Как запускать

=== "Ядро (`cp_packages test`)"

    ```bash
    CP_TOKEN=<access token audience control-plane> \
    python3 tools/cp_packages.py test --package packages/<пакет> \
        --server https://platform.example.com [--test tests/<имя>.test.yaml] [--workspace <workspace-id>]
    ```

    Пакет уходит в `POST /api/v1/packages:test` (право `packages.test`).
    Ядро собирает определения пакета в памяти поверх каталога tenant'а —
    объекты самого пакета (типы задач, скиллы, агенты, календари) известны
    его процессам до применения. `--workspace` — чьи роли, календари и
    экземпляры читает прогон (нужно `processes.read` на него).

=== "Песочница локально (`package_sandbox.py`)"

    ```bash
    PYTHONPATH=control-plane/src:control-plane/client/src \
    python3 tools/package_sandbox.py <пакет> [--test tests/<имя>.test.yaml] [--json]
    ```

    Тот же код ядра (движок, проверка, песочница), но в процессе, без стенда и
    без базы. Каталог — только объекты пакета и его `requires`; `governedBy` с
    базой знаний не сверяется; переменные `${…}` берутся из `--env` (по
    умолчанию `.env`) и окружения. Без аргументов — все пакеты с тестами
    (так тесты пакетов идут в CI). Код выхода `0` — все тесты зелёные и
    находок-ошибок нет.

=== "Из Claude Code"

    Инструмент MCP `cp_pkg_test(path, tests?)` с путём каталога пакета —
    тот же `POST /packages:test`.

Вывод:

```text
== supplier-invoice (песочница ядра в процессе, 136 мс)
ok   tests/above-threshold.test.yaml: счёт выше порога согласует финансовый директор [supplier-invoice] (13 мс)
ok   tests/escalation.test.yaml: просроченное согласование эскалируется [supplier-invoice] (7 мс)
ok   tests/separation-of-duties.test.yaml: загрузивший счёт не согласует его оплату [supplier-invoice] (7 мс)
…
покрытие supplier-invoice v1: elements 13/13, transitions 12/12, decisionRows 2/2, handlers 2/2
ok (passed): тестов 7, зелёных 7
```

Упавший тест печатается как `FAIL <файл>: <имя>` со строками
`шаг N: <сообщение>` и `ожидалось: …; получено: …`; непройденное покрытие —
строками `не пройдены (<счётчик>): …`. Ответ ядра — `status` `passed`,
`failed` или `invalid` (есть находка-ошибка, тесты не запускались).

## Replay по журналу

Replay прогоняет **кандидата** — новую версию процесса — по журналам
реальных экземпляров и показывает, где решения разошлись бы с записанными:

```bash
curl -sS -X POST "https://platform.example.com/api/v1/process-definitions/supplier-invoice:replay" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"spec": { … }, "limit": 50}'
```

- Экземпляры — `instanceIds` или последние `limit` (по умолчанию 50, не
  больше 200) экземпляров текущей версии из workspace'ов, где у вызывающего
  есть `processes.read`. Нужно ещё право `packages.test`.
- Кандидат идёт под номером версии экземпляра: номер версии — не поведение.
- Ответы базы знаний на `recall` и версии календарей берутся из журнала —
  память не зовётся.
- Расхождение у экземпляра одно, первое: `journalSeq`, `kind` (`decision`,
  `intent`, `input`, `data`, `timer`, `state`), `element`, `recorded` и
  `replayed`. Дальше пути разошлись, и сравнивать нечего.
- Replay текущей версии на её же журнале даёт ноль расхождений; изменённая
  строка таблицы решений даёт расхождение `decision` ровно у тех экземпляров,
  чьи входы она решает иначе.

## Пробный прогон на живом экземпляре { #dry-run }

Тест со сценарием `given.fromInstance: <id экземпляра>` продолжает **копию**
состояния живого экземпляра на версии процесса из пакета:

```yaml
process: supplier-invoice
name: пробный прогон — что будет с этим счётом по новой версии
given: {fromInstance: <instance-id>}
steps:
  - approve: {step: approve-payment, by: <principal-id>, decision: approve}
  - expect: {stages: {payment: open}}
```

Открытые задачи и approvals экземпляра становятся объектами песочницы,
ожидающие вызовы скиллов и `recall` остаются без ответа. Часы — `given.clock`
или время последнего входа экземпляра. Живой экземпляр не меняется; нужно
`processes.read` на его workspace. `given.data` рядом с `fromInstance`
несовместим. Пробный прогон работает только через ядро — у локальной
песочницы живых экземпляров нет.

## План и применение { #plan }

План строит ядро: `POST /api/v1/packages:plan` (право `packages.plan`).
Процессы и календари применяются **только планом ядра**; остальные виды
пакета ставит обычная установка `cp_packages apply --install`.

```bash
python3 tools/cp_packages.py plan --install deploy/<окружение>/packages.yaml \
    --server https://platform.example.com --out plan.json [--workspace <workspace-id>] [--replay-limit 50]
python3 tools/cp_packages.py apply --plan plan.json
```

Пример вывода (сокращён):

```text
план supplier-invoice 0.3.0: sha256:3f… (каталог sha256:9a…)
  ~ Process/supplier-invoice: /spec/stages; /spec/version
процесс supplier-invoice: v1 → v2
  поведение (replay): экземпляров 12, расхождений 2: <instance-id>, <instance-id>
  открытые экземпляры v1: 3 → migrate
регламент regulation:payments: разделов с элементами 4, без элементов: 5.1
```

| Раздел плана | Что показывает |
|---|---|
| `changes` | структурный diff по объектам: `create` (`+`), `update` (`~`), `rename` (`→`), `unchanged`; у поля — было, стало и владелец: `package` или `console` |
| `processes[].behaviour` | replay новой версии на `replayLimit` недавних экземплярах: сколько решили бы иначе |
| `processes[].instances` | судьба открытых экземпляров по версиям: `pin`, `migrate`, `unaffected`; `migrationRequired` |
| `regulationCoverage` | разделы регламентов и элементы, которые их исполняют; непокрытые разделы |
| `problems` | находки проверки |
| `planHash`, `catalogEtag` | хэш плана и отпечаток каталога, на котором он построен |

- **Поле, которое правил человек в консоли** после последнего применения, —
  владелец `console`. Пакет его не перетирает: публикуемая версия берёт
  значение из консоли. Перетереть — план с `overwriteConsole: true` (флаг
  входит в хэш плана).
- **Применение — ровно показанный план.** `POST /packages:apply {package,
  planHash}` строит план заново под блокировкой и сравнивает хэши: стенд,
  открытые экземпляры или файлы изменились после показа — `409 plan_stale`,
  нужен новый план. Файл плана, изменённый после построения, `cp_packages`
  не применяет.
- **Открытые экземпляры на удалённом элементе** без карты миграции — ошибка
  плана `migration_required`; такой план не сохраняется, а применение
  отказывает `422 migration_required`. Прочие ошибки — `422 invalid_package`.
- Применение — одна транзакция: календари, процессы, перенос экземпляров по
  `migrate` с событием `process.migrated`, вывод переименованного ключа.
  Каждое изменение проходит право своего вида (`processes.write`,
  `calendars.write`).

### Переименования и миграции

- **Объект целиком** — `renames` в `package.yaml`:

  ```yaml
  spec:
    version: 0.4.0
    renames:
      - {kind: Process, from: invoice-intake, to: supplier-invoice}
  ```

  План показывает `rename`, объект переносится с историей версий, а старый
  ключ выводится: новых экземпляров не заводит (`409 process_retired`), его
  открытые экземпляры дорабатывают. Команда
  `tools/pkg.py rename --package <каталог> --kind Process --from <ключ> --to <ключ>`
  переименует файл и допишет `renames` сама.
- **Элемент процесса** — карта `migrations` новой версии
  (см. [Процессы](index.md#versions)). Команда
  `tools/pkg.py rename --file <процесс> --from <id> --to <id>` меняет id,
  ссылки и тесты и дописывает карту.

## Типичные проблемы

| Симптом | Причина | Что делать |
|---|---|---|
| тест падает на заглушке скилла | выход заглушки не проходит схему выхода скилла | привести `output` к контракту скилла — так и задумано |
| задача шага в тесте не появилась, `intent_failed unknown_role` | у роли нет держателей в `given.principals` и она не объявлена в пакете | добавить роль в `given.principals` или пакет |
| `recall` в тесте уходит в таймаут | нет заглушки `mocks.recall` для шага | добавить ответ (можно общий, без `step`) |
| `status: invalid`, тесты не запускались | находка-ошибка проверки | исправить по `file`, `line`, `hint` |
| `plan_stale` при применении | после плана изменились каталог, экземпляры или файлы | построить план заново |
| «ядро не поддерживает проверку процессов … — проверена только схема» | у ядра нет маршрутов пакетов процессов | обновить Control Plane или запускать `package_sandbox.py` |

## См. также

- [Процессы](index.md)
- [Выражения](expressions.md)
- [Схема языка процессов](../reference/process-schema.md#schema-test)
- [Пакеты каталога](../control-plane/catalog-packages.md#processes)
