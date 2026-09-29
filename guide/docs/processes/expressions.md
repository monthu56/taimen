
# Expressions

All expressions in the process language (conditions, keys, computed fields,
deadlines, assignments, decision table inputs, memory anchors) are written
in one language: CEL (Common Expression Language) in the platform profile.
This article is for process authors: variables, types, calendar functions,
restrictions, and translation of earlier syntaxes. Rationale: CP-ADR-0075.

## The `cp/1` profile

A profile is an environment (variables and their types), a set of
functions, prohibitions, and limits. The core records the profile name in
the definition version (`expressionProfile`). A new function that does not
change earlier values stays in `cp/1`; a change in meaning is a new
profile, and a definition on `cp/1` is evaluated by `cp/1` for as long as
its instances are alive.

!!! note "One profile name"
    In catalog schema descriptions, the profile may be named after the
    product with the same `/1` number; it is the same profile. Packages do
    not store the profile name.

Where expressions appear:

| Place | What the expression produces |
|---|---|
| `when`, `entry`, `exit`, milestones, trigger `where` | `bool` |
| `start.key`, `correlate[].key` | instance key |
| `set`, `output.as`, `export.as`, `start.set`, `correlate[].set` | data field value |
| `input.from`, `call.input`, `decide.input` | step input |
| `due.at`, `timeout.at`, `wait.at`, timer `at`, escalation `after` | `timestamp` or `duration` |
| `assign[].expr`, `approvers[].expr` | a principal id, `agent:<key>`, or `role:<slug>` |
| `separationOfDuties` | a list of principals |
| `title`, `raise.detail`, `suspend.reason` | string |
| decision table inputs (`inputs[].expr`) | input value |
| `memory`, `recall` and `context` anchors, `remember` | keys and values for the knowledge base |

In YAML an expression is a string. A string literal inside an expression is
enclosed in single quotes: `"'invoice:' + data.number"`.

## Variables

| Variable | What | Type |
|---|---|---|
| `data` | instance data | from the JSON Schema `spec.data` |
| `event` | the input event: `id`, `type`, `time`, `entityType`, `entityId`, `actorId`, `correlationId`, `payload` | `payload` comes from the event catalog for `event:` or is `map(string, dyn)` |
| `step` | step result: `id`, `skill`, `status`, `result`, `error.code`, `error.message`; in a block, the last completed step of the flow; in `output.as`, the step itself | the skill output per its schema, the task form, table outputs, the `recall` response |
| `task` | the step's task: `id`, `publicId`, `typeKey`, `title`, `status`, `assigneeId`, `customFields`, `artifacts`… | `customFields` follows the task type's `fieldSchema` |
| `stage` | `stage.<id>.completed`, `stage.<id>.active` (or `stage["<id>"]`) | `bool` |
| `instance` | `id`, `key`, `version`, `startedAt`, `clock` | `clock` is the time of the current input |

Besides the profile variables, local bindings are visible where they apply:
`milestone.<id>` (stage milestones), the error name from `try.catch[].as` in
its handler, and `compensated` (the step being compensated) inside
`onCompensate`.

`step.result` depends on the kind of step:

| Step | `step.result` |
|---|---|
| `human` | the step's form fields (or the task type's `fieldSchema`) |
| `approve` | `{outcome, approvedBy, rejectedBy}` |
| skill `call` | the skill output per its schema |
| `decide` | the outputs of the table row; for `collect`, `{items: [...]}` |
| `recall` | `{nodes, edges, truncated}` |
| `listen` | `{option, event}` |

## Types from the data schema { #types }

Expression types are derived from the process's data JSON Schema:

| JSON Schema | CEL |
|---|---|
| `string` | `string` |
| `integer` | `int` |
| `number` | `double` |
| `boolean` | `bool` |
| `array` | `list(T)`; a missing array is an empty list |
| `object` with `properties` | a record with the declared fields; accessing an undeclared field is an **error at publication** |
| `object` without `properties` | `map(string, dyn)` |
| `format: date-time` | `timestamp` |
| `format: duration` | `duration` |
| `oneOf`, `$ref`, mixed types | `dyn`, checked at evaluation |

A missing or `null` scalar field reads as `null` and fails when used. For
optional fields:

```text
has(data.review)                         // whether the field is present
data.?review.orValue('')                 // the value or '' — the result must not remain optional
data.?approval.orValue('') == 'approved'
```

An unset time field without `has()` or `.?` is an evaluation error;
otherwise it would read as the year 1970.

## Functions

### Calendar { #calendar }

| Function | What it returns |
|---|---|
| `cal.addWorkdays(ts, n)` | the `n`-th workday after the day of `ts` (with `n < 0`, before it); the day of `ts` itself is not counted, `n = 0` returns the same moment; the time of day is preserved in the calendar's time zone |
| `cal.isWorkday(ts)` | whether `ts` falls on a workday |
| `cal.workdaysBetween(a, b)` | the number of workdays in `(a, b]`; negative when `b < a` |

The last argument is the calendar key (`cal.addWorkdays(ts, -3, 'ru')`). You
can omit it if the process has `spec.calendar`; without a process calendar,
the short form is a type error at publication.

- A day is a workday if it is in the year's `workdays`; otherwise, if it is
  not in `holidays` and is not a weekend day of the week. For a year that is
  not in the calendar, only the weekend days of the week are known.
- An evaluation that touched a provisional year (`provisional: true`) or a
  year outside the calendar is marked "provisional".

```yaml
due: {at: "cal.addWorkdays(data.submissionEnd, -3)"}   # three workdays before the date
when: cal.workdaysBetween(instance.clock, data.submissionEnd) < 3
```

### Time and durations

- `duration("P3D")` accepts an ISO 8601 literal (weeks, days, hours,
  minutes, seconds; years and months are a type error) and the CEL form
  (`duration("72h")`). An ISO string computed at run time is not parsed;
  durations in data are typed by the schema (`format: duration`).
- `timestamp("2026-10-19T09:00:00+03:00")` is RFC 3339.
- Arithmetic: `data.submissionEnd - duration("72h")`,
  `instance.clock < data.submissionEnd`.

### Strings, lists, macros

- Strings: `lowerAscii`, `split`, `join`, `replace`, `substring`, and other
  functions of the `strings` extension.
- Lists: `size`, `in`, `slice`, `flatten`, `sort`, `distinct`.
- Macros: `all`, `exists`, `map`, `filter`:
  `size(data.history.filter(n, n.kind == 'lesson')) > 0`.
- Optional values: `.?field`, `orValue(…)`.
- `cel.bind(name, value, expression)` binds a local name.

## What is not available

- **The current time.** There is no `now()` function; calling it is a type
  error with a hint. Time enters an expression only as `instance.clock` and
  `event.time`, which the engine input sets. So one expression on the same
  inputs yields one value in a live run, a test, and a replay.
- **Randomness, I/O, access to memory and the catalog.** The knowledge base
  enters expressions only through a recorded `recall` response, and the
  calendar through the version recorded in the log.
- **Side effects.** Writing to data happens only through `set` and
  `output.as`.
- **`{{…}}` templates.** They remain in work rules and notification rules;
  processes do not have them.

## Limits

| Limit | Value | When it is checked |
|---|---|---|
| expression length | 4000 characters | catalog schema |
| expression tree depth | 32 | at publication (`expression_too_complex`) |
| nesting of iterating macros | 3 | at publication (`expression_too_complex`) |
| evaluation cost | 10,000 units | before evaluation, from input sizes (`expression_cost_exceeded`) |

Cost is estimated from above before evaluation: a step per path segment, a
function call, macro iterations by list size. Above the limit the
evaluation does not start: the step gets an `expression_cost_exceeded`
error, which `try` can catch; otherwise the instance moves to `failed` with
a clear reason, so the process never hangs silently.

## Errors

Parse errors arrive as check findings with the location in the file and the
position in the expression:

```json
{"code": "expression_type_error", "severity": "error",
 "path": "/spec/stages/0/steps/1/human/due/at", "file": "processes/purchase.yaml",
 "line": 31, "message": "no such field 'submisionDeadline' at 1:34",
 "hint": "data.procurement has submissionDeadline"}
```

| Code | When |
|---|---|
| `expression_syntax_error` | syntax |
| `expression_type_error` | type: an unknown field, `now()`, the wrong result type for the place (expected `bool`, `timestamp` or `duration`, a list) |
| `expression_too_complex` | depth or macro nesting |
| `expression_error` | at evaluation: `null`, a missing field, no calendar |
| `expression_cost_exceeded` | the cost limit was exceeded |

## Common mistakes

| Mistake | Correct |
|---|---|
| `title: 'Invoice ' + data.number`: YAML consumed the quotes, and CEL sees `Invoice` without quotes | `title: "'Invoice ' + data.number"` |
| `when: data.note != ''` on an optional field | `when: data.?note.orValue('') != ''` |
| `due: {at: "now() + duration('P1D')"}` | `due: P1D` or `{at: "cal.addWorkdays(instance.clock, 1)"}` |
| `set: {total: data.amount * 1.2}` with `amount: {type: integer}` | CEL does not mix `int` and `double`: `double(data.amount) * 1.2` |
| `data.?approval` at the end of an expression | the result cannot remain optional: `data.?approval.orValue('')` |
| a stage guard reads a step result | stage guards and milestones read `data`, `stage`, and `milestone`: write the step result into data with `output.as` |
| a boolean as a string, `set: {done: "yes"}` | `set: {done: "true"}`, a YAML string with the expression `true` |

## Translating earlier syntaxes

Work rules, approval outcomes, task type execution inputs, and the context
profile historically use their own path syntaxes. They keep working until
the packages are translated, and there is a command for the translation:

```bash
python3 tools/cp_packages.py migrate-expr --package packages/<package>          # diff, writes nothing
python3 tools/cp_packages.py migrate-expr --package packages/<package> --write  # write
```

- The command prints a diff per file; `--write` writes the changes while
  preserving the file (comments, key order, and style remain).
- The core finds and translates the expressions: you need control-plane with
  the CEL profile on `PYTHONPATH` (or the interpreter of its uv environment).
- Processes and calendars are already in CEL, and the command does not touch
  them.
- Anything that cannot be translated is printed with a reason and stays as
  it was; if a translation reads variables beyond the profile (for example,
  `spawnedBy`), that is printed too.

| Earlier | CEL |
|---|---|
| `{"var": "payload.data.repo"}` | `event.payload.?data.?repo.orValue(null)` |
| `{"exists": "payload.data.url"}` | `event.payload.?data.?url.orValue(null) != null` |
| `{"lt": [{"var": "x"}, 3]}` | `x != null && x < 3` |
| `$.task.customFields.branch` | `task.customFields.?branch.orValue(null)` |
| `$.task.customFields.branch!` | `task.customFields.branch` (a missing field is an error) |
| `$.task.artifact[commit].metadata.sha` | `task.artifacts.?commit.?metadata.?sha.orValue(null)` |
| `$.invocation.output.x` | `step.result.?x.orValue(null)` |
| template `"Merge $.task.publicId!: $.task.title"` | concatenation; a missing value becomes `""` |
| `execution.inputs: $.customFields.url` | `task.customFields.?url.orValue(null)` |
| `from: "$.customFields.okpdCodes"` | `task.customFields.?okpdCodes.orValue(null)` |

!!! warning "Where the translation differs from the earlier evaluation"
    `0` in `when` used to count as an unmet condition; in CEL it counts as
    met. A non-string value in a template prints as `true`, not `True`. A
    required `!` on a field with an empty string used to cause a refusal; in
    CEL it yields `""`. Check such places after the translation.

## See also

- [Processes](index.md)
- [Package tests](package-tests.md)
- [Process language schema](../reference/process-schema.md#schema-cel)
- [Work rules](../control-plane/work-rules.md)
