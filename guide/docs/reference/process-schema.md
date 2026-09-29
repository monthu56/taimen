
# Process language schema

Field reference for the process package language: the catalog kind
`Process`, the business calendar `Calendar`, and package tests
`*.test.yaml`. The tables are built from the JSON Schema
`packages/schema/v1` and follow it field for field. This page is for package
authors; [Processes](../processes/index.md),
[Expressions](../processes/expressions.md), and
[Package tests](../processes/package-tests.md) explain how to use it.

!!! note "The schema is the first stage of checking"
    The schema checks the shape of the description. The core performs the
    second stage when it checks a package: expression types, unknown data
    fields, step reachability, references to task types and skills, gaps in
    decision tables (see [Package tests](../processes/package-tests.md#check)).

## Process (`kind: Process`)

<!-- generated:schema-process -->
_This section is generated from code; do not edit it by hand._

Source: `packages/schema/v1/object.schema.json`.

### `processSpec` { #schema-processspec }

Process (TAI-ADR-0054, CP-ADR-0074): a case with stages and execution blocks, data by schema, CEL expressions, projection into memory. The core executes it

| Field | Type | Required | Description |
|---|---|---|---|
| `version` | `integer` | yes | Definition version: a published version is immutable |
| `displayName` | `displayName` | yes |  |
| `description` | `string` |  |  |
| `workspaceId` | `string` |  |  |
| `identity` | [object](#schema-processspec-identity) |  | On whose behalf the process acts: an agent description of kind service or agent |
| `owner` | [`assignChain`](#schema-assignchain) |  | Process owner: tasks about the process are addressed to them: divergence from a regulation, instance errors (TAI-ADR-0054 item 5, amendment 2026-09-27). Optional; the package check warns if it is missing |
| `calendar` | `typeKey` |  | Default calendar for cal.* |
| `data` | `jsonSchema` | yes | JSON Schema of instance data; cp_packages expands {$ref: &lt;package file&gt;} |
| `start` | [object](#schema-processspec-start) | yes |  |
| `correlate` | array of [object](#schema-processspec-correlate-item) |  |  |
| `stages` | array of [`processStage`](#schema-processstage) | yes |  |
| `onEvent` | array of [object](#schema-processspec-onevent-item) |  |  |
| `timers` | [`processTimers`](#schema-processtimers) |  |  |
| `decisions` | array of [`decisionTable`](#schema-decisiontable) |  |  |
| `governedBy` | [`governedBy`](#schema-governedby) |  |  |
| `memory` | [`memoryProjection`](#schema-memoryprojection) |  |  |
| `retrospective` | [object](#schema-processspec-retrospective) |  | Review of a closed case: an agent proposes lessons, a human confirms (TAI-ADR-0054 D18) |
| `migrations` | array of [object](#schema-processspec-migrations-item) |  |  |

### `processSpec.identity` { #schema-processspec-identity }

On whose behalf the process acts: an agent description of kind service or agent

| Field | Type | Required | Description |
|---|---|---|---|
| `agent` | `slug` | yes |  |

### `processSpec.start` { #schema-processspec-start }

| Field | Type | Required | Description |
|---|---|---|---|
| `on` | [`processTrigger`](#schema-processtrigger) | yes |  |
| `key` | [`cel`](#schema-cel) | yes | Instance key: a repeated event with the same key is a correlate, not a new instance |
| `set` | [`celMap`](#schema-celmap) |  |  |

### `processSpec.correlate[]` { #schema-processspec-correlate-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `on` | [`processTrigger`](#schema-processtrigger) | yes |  |
| `key` | [`cel`](#schema-cel) | yes |  |
| `set` | [`celMap`](#schema-celmap) |  |  |
| `do` | [`blocks`](#schema-blocks) |  |  |

### `processSpec.onEvent[]` { #schema-processspec-onevent-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `on` | [`processTrigger`](#schema-processtrigger) | yes |  |
| `do` | [`blocks`](#schema-blocks) | yes |  |

### `processSpec.retrospective` { #schema-processspec-retrospective }

Review of a closed case: an agent proposes lessons, a human confirms (TAI-ADR-0054 D18)

| Field | Type | Required | Description |
|---|---|---|---|
| `skill` | `string` |  | Default: `process.retrospective@1`. |
| `taskType` | `typeKey` | yes |  |
| `assign` | [`assignChain`](#schema-assignchain) | yes |  |
| `appliesTo` | array of `string` |  | Entity kinds that lessons are attached to |
| `when` | [`cel`](#schema-cel) |  |  |

### `processSpec.migrations[]` { #schema-processspec-migrations-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `from` | `integer` | yes |  |
| `to` | `integer` | yes |  |
| `policy` | `pin` \| `migrate` | yes |  |
| `map` | map → [`processElementId`](#schema-processelementid) |  |  |

### `processStage` { #schema-processstage }

Case stage (CMMN): entry and exit by guards, milestones, required and discretionary work

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | yes |  |
| `displayName` | `displayName` |  |  |
| `entry` | [`cel`](#schema-cel) |  | Entry guard; stage.&lt;id&gt;.completed, milestone.&lt;id&gt;, and data are available in the expression |
| `exit` | [`cel`](#schema-cel) |  |  |
| `repeatable` | `boolean` |  |  |
| `governedBy` | [`governedBy`](#schema-governedby) |  |  |
| `steps` | [`blocks`](#schema-blocks) | yes |  |
| `discretionary` | array of [`processStep`](#schema-processstep) |  | Work that a human adds at their discretion |
| `milestones` | array of [object](#schema-processstage-milestones-item) |  |  |
| `timers` | [`processTimers`](#schema-processtimers) |  |  |

### `processStage.milestones[]` { #schema-processstage-milestones-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | yes |  |
| `when` | [`cel`](#schema-cel) | yes |  |

### `processStep` { #schema-processstep }

Process step: exactly one kind (human, approve, call, decide, recall, remember, listen, wait, set, raise, compensate, fork, try, do, suspend, resume, complete) plus common fields

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | yes |  |
| `displayName` | `displayName` |  |  |
| `when` | [`cel`](#schema-cel) |  | Guard: the step runs only if it is true |
| `input` | [object](#schema-processstep-input) |  |  |
| `output` | [object](#schema-processstep-output) |  | Writes the step result (step.result) into instance data |
| `export` | [object](#schema-processstep-export) |  |  |
| `governedBy` | [`governedBy`](#schema-governedby) |  |  |
| `onCompensate` | [`blocks`](#schema-blocks) |  | Compensation of a completed step: runs on compensate in reverse order |
| `human` | [object](#schema-processstep-human) |  |  |
| `approve` | [object](#schema-processstep-approve) |  |  |
| `call` | [object](#schema-processstep-call) |  |  |
| `decide` | [object](#schema-processstep-decide) |  |  |
| `recall` | [object](#schema-processstep-recall) |  | A memory query through the core; the response is a log event (deterministic replay) |
| `remember` | [object](#schema-processstep-remember) |  | A write to memory as a core observation from the process identity, with a reference to the case |
| `listen` | [object](#schema-processstep-listen) |  | Waiting for the first of several events (deferred choice); timeout is a timer |
| `wait` | [`durationOrCel`](#schema-durationorcel) |  |  |
| `set` | [`celMap`](#schema-celmap) |  |  |
| `raise` | [`processError`](#schema-processerror) |  |  |
| `compensate` | = `all` or array of [`processElementId`](#schema-processelementid) |  | Run onCompensate of completed steps in reverse order |
| `fork` | [object](#schema-processstep-fork) |  |  |
| `try` | [object](#schema-processstep-try) |  |  |
| `do` | [`blocks`](#schema-blocks) |  |  |
| `suspend` | [object](#schema-processstep-suspend) |  |  |
| `resume` | [object](#schema-processstep-resume) |  |  |
| `complete` | [object](#schema-processstep-complete) |  |  |

Exactly one of: `human`, `approve`, `call`, `decide`, `recall`, `remember`, `listen`, `wait`, `set`, `raise`, `compensate`, `fork`, `try`, `do`, `suspend`, `resume`, `complete`.

### `processStep.input` { #schema-processstep-input }

| Field | Type | Required | Description |
|---|---|---|---|
| `from` | [`cel`](#schema-cel) |  |  |

### `processStep.output` { #schema-processstep-output }

Writes the step result (step.result) into instance data

| Field | Type | Required | Description |
|---|---|---|---|
| `as` | [`celMap`](#schema-celmap) |  |  |

### `processStep.export` { #schema-processstep-export }

| Field | Type | Required | Description |
|---|---|---|---|
| `as` | [`celMap`](#schema-celmap) |  |  |

### `processStep.human` { #schema-processstep-human }

| Field | Type | Required | Description |
|---|---|---|---|
| `taskType` | `typeKey` | yes |  |
| `title` | [`cel`](#schema-cel) |  |  |
| `form` | [`processForm`](#schema-processform) |  |  |
| `assign` | [`assignChain`](#schema-assignchain) | yes |  |
| `due` | [`durationOrCel`](#schema-durationorcel) |  |  |
| `escalations` | array of [`escalation`](#schema-escalation) |  |  |
| `context` | [`stepContext`](#schema-stepcontext) |  |  |

### `processStep.approve` { #schema-processstep-approve }

| Field | Type | Required | Description |
|---|---|---|---|
| `taskType` | `typeKey` |  |  |
| `approvers` | [`assignChain`](#schema-assignchain) | yes |  |
| `mode` | `parallel` \| `sequential` |  | Default: `parallel`. |
| `quorum` | `all` \| `any` or object `{atLeast}` or object `{percent}` | yes |  |
| `earlyDecision` | `boolean` |  | Default: `true`. |
| `separationOfDuties` | [`cel`](#schema-cel) |  | CEL → a list of principals who must not vote; the core checks it at decision time |
| `due` | [`durationOrCel`](#schema-durationorcel) |  |  |
| `onDue` | `approve` \| `reject` \| `escalate` |  |  |
| `escalations` | array of [`escalation`](#schema-escalation) |  |  |
| `context` | [`stepContext`](#schema-stepcontext) |  |  |

### `processStep.call` { #schema-processstep-call }

| Field | Type | Required | Description |
|---|---|---|---|
| `skill` | `string` |  |  |
| `agent` | `slug` |  |  |
| `process` | `typeKey` |  |  |
| `input` | [`celMap`](#schema-celmap) |  |  |
| `timeout` | [`durationOrCel`](#schema-durationorcel) |  |  |
| `context` | [`stepContext`](#schema-stepcontext) |  |  |

Exactly one of: `skill`, `agent`, `process`.

### `processStep.decide` { #schema-processstep-decide }

| Field | Type | Required | Description |
|---|---|---|---|
| `table` | [`processElementId`](#schema-processelementid) | yes |  |
| `input` | [`celMap`](#schema-celmap) |  |  |

### `processStep.recall` { #schema-processstep-recall }

A memory query through the core; the response is a log event (deterministic replay)

| Field | Type | Required | Description |
|---|---|---|---|
| `anchors` | array of [`memoryAnchor`](#schema-memoryanchor) | yes |  |
| `traverse` | [`memoryTraverse`](#schema-memorytraverse) |  |  |
| `query` | [`cel`](#schema-cel) |  | Text for semantic enrichment |
| `kinds` | array of `string` |  |  |
| `limit` | `integer` |  |  |
| `timeout` | [`duration`](#schema-duration) |  |  |
| `onTimeout` | [`blocks`](#schema-blocks) |  |  |

### `processStep.remember` { #schema-processstep-remember }

A write to memory as a core observation from the process identity, with a reference to the case

| Field | Type | Required | Description |
|---|---|---|---|
| `entity` | [object](#schema-processstep-remember-entity) |  |  |
| `facts` | [`celMap`](#schema-celmap) |  | Case fact name → value |

Exactly one of: `facts`, `entity`.

### `processStep.remember.entity` { #schema-processstep-remember-entity }

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | `string` | yes |  |
| `key` | [`cel`](#schema-cel) | yes |  |
| `name` | [`cel`](#schema-cel) |  |  |
| `text` | [`cel`](#schema-cel) |  |  |
| `links` | array of [object](#schema-processstep-remember-entity-links-item) |  |  |

### `processStep.remember.entity.links[]` { #schema-processstep-remember-entity-links-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `rel` | `string` | yes |  |
| `kind` | `string` | yes |  |
| `key` | [`cel`](#schema-cel) | yes |  |

### `processStep.listen` { #schema-processstep-listen }

Waiting for the first of several events (deferred choice); timeout is a timer

| Field | Type | Required | Description |
|---|---|---|---|
| `any` | array of [object](#schema-processstep-listen-any-item) | yes |  |
| `timeout` | [`durationOrCel`](#schema-durationorcel) |  |  |
| `onTimeout` | [`blocks`](#schema-blocks) |  |  |

### `processStep.listen.any[]` { #schema-processstep-listen-any-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `on` | [`processTrigger`](#schema-processtrigger) | yes |  |
| `do` | [`blocks`](#schema-blocks) |  |  |

### `processStep.fork` { #schema-processstep-fork }

| Field | Type | Required | Description |
|---|---|---|---|
| `mode` | `all` \| `compete` |  | Default: `all`. |
| `branches` | array of [object](#schema-processstep-fork-branches-item) | yes |  |

### `processStep.fork.branches[]` { #schema-processstep-fork-branches-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | yes |  |
| `do` | [`blocks`](#schema-blocks) | yes |  |

### `processStep.try` { #schema-processstep-try }

| Field | Type | Required | Description |
|---|---|---|---|
| `do` | [`blocks`](#schema-blocks) | yes |  |
| `retry` | [object](#schema-processstep-try-retry) |  |  |
| `catch` | array of [object](#schema-processstep-try-catch-item) |  |  |

### `processStep.try.retry` { #schema-processstep-try-retry }

| Field | Type | Required | Description |
|---|---|---|---|
| `limit` | `integer` | yes |  |
| `delay` | [`duration`](#schema-duration) |  |  |
| `backoff` | `constant` \| `exponential` |  |  |
| `maxDelay` | [`duration`](#schema-duration) |  |  |
| `on` | array of `string` |  | Error types to retry; all by default |

### `processStep.try.catch[]` { #schema-processstep-try-catch-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `errors` | [object](#schema-processstep-try-catch-item-errors) |  |  |
| `as` | `string` |  |  |
| `do` | [`blocks`](#schema-blocks) | yes |  |

### `processStep.try.catch[].errors` { #schema-processstep-try-catch-item-errors }

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `string` |  |  |
| `status` | `integer` |  |  |

### `processStep.suspend` { #schema-processstep-suspend }

| Field | Type | Required | Description |
|---|---|---|---|
| `reason` | [`cel`](#schema-cel) |  |  |

### `processStep.resume` { #schema-processstep-resume }

| Field | Type | Required | Description |
|---|---|---|---|
| `reason` | [`cel`](#schema-cel) |  |  |

### `processStep.complete` { #schema-processstep-complete }

| Field | Type | Required | Description |
|---|---|---|---|
| `outcome` | `string` | yes |  |

### `processTimers` { #schema-processtimers }

Boundary timers: fire while the stage (process) is open; an at derived from data is recalculated when the data changes

Value: array of [object](#schema-processtimers-item).

### `processTimers[]` { #schema-processtimers-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | yes |  |
| `at` | [`durationOrCel`](#schema-durationorcel) | yes |  |
| `interrupting` | `boolean` |  | Default: `false`. |
| `do` | [`blocks`](#schema-blocks) | yes |  |

### `decisionTable` { #schema-decisiontable }

Decision table (DMN in spirit). Condition cell: '-' (any), a literal, a list 'a,b', a range '[a..b)'

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | yes |  |
| `displayName` | `displayName` |  |  |
| `hitPolicy` | `first` \| `unique` \| `collect` | yes |  |
| `governedBy` | [`governedBy`](#schema-governedby) |  |  |
| `inputs` | array of [object](#schema-decisiontable-inputs-item) | yes |  |
| `outputs` | array of [object](#schema-decisiontable-outputs-item) | yes |  |
| `rules` | array of [object](#schema-decisiontable-rules-item) | yes |  |

### `decisionTable.inputs[]` { #schema-decisiontable-inputs-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | yes |  |
| `expr` | [`cel`](#schema-cel) | yes |  |
| `type` | `string` \| `number` \| `boolean` \| `date` \| `timestamp` |  |  |

### `decisionTable.outputs[]` { #schema-decisiontable-outputs-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | yes |  |
| `type` | `string` \| `number` \| `boolean` \| `date` \| `duration` \| `object` \| `array` |  |  |

### `decisionTable.rules[]` { #schema-decisiontable-rules-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `when` | map → `string` \| `number` \| `boolean` | yes |  |
| `then` | `object` | yes |  |
| `note` | `string` |  |  |
| `governedBy` | [`governedBy`](#schema-governedby) |  |  |

### `memoryProjection` { #schema-memoryprojection }

Projection of the case into the memory graph (TAI-ADR-0054 D15): delivered by events; only declared fields go into the graph

| Field | Type | Required | Description |
|---|---|---|---|
| `case` | [object](#schema-memoryprojection-case) | yes |  |
| `facts` | [`celMap`](#schema-celmap) |  | Case fact name → value; a change closes the previous fact with a validity period |
| `entities` | array of [object](#schema-memoryprojection-entities-item) |  |  |
| `documents` | [object](#schema-memoryprojection-documents) |  |  |

### `memoryProjection.case` { #schema-memoryprojection-case }

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | `string` |  | Default: `case`. |
| `key` | [`cel`](#schema-cel) | yes |  |
| `title` | [`cel`](#schema-cel) |  |  |

### `memoryProjection.entities[]` { #schema-memoryprojection-entities-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | `string` | yes |  |
| `key` | [`cel`](#schema-cel) | yes |  |
| `name` | [`cel`](#schema-cel) |  |  |
| `rel` | `string` | yes |  |
| `when` | [`cel`](#schema-cel) |  |  |
| `many` | `boolean` |  | key yields a list: one entity per element |

### `memoryProjection.documents` { #schema-memoryprojection-documents }

| Field | Type | Required | Description |
|---|---|---|---|
| `artifacts` | array of `typeKey` |  |  |

### `stepContext` { #schema-stepcontext }

Context profile of the step executor from memory (TAI-ADR-0054 D16): explicit links first, semantic enrichment marked inferred

| Field | Type | Required | Description |
|---|---|---|---|
| `anchors` | array of [`memoryAnchor`](#schema-memoryanchor) | yes |  |
| `traverse` | [`memoryTraverse`](#schema-memorytraverse) |  |  |
| `semantic` | `boolean` |  | Semantic enrichment (inferred); true by default |
| `budgetTokens` | `integer` |  |  |

### `memoryAnchor` { #schema-memoryanchor }

Graph traversal anchor: the instance's case node or an entity by natural key (CEL over data)

| Field | Type | Required | Description |
|---|---|---|---|
| `case` | = `true` |  |  |
| `kind` | `string` |  |  |
| `key` | [`cel`](#schema-cel) |  |  |
| `via` | `string` |  |  |

Exactly one of: `case`, `key` + `kind`.

### `memoryTraverse` { #schema-memorytraverse }

Traversal steps from anchors: the same form as traverse in contextSchema (CP-ADR-0064)

Value: array of [object](#schema-memorytraverse-item).

### `memoryTraverse[]` { #schema-memorytraverse-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `relation` | `string` | yes |  |
| `direction` | `in` \| `out` \| `both` |  |  |
| `depth` | `integer` |  |  |
| `limit` | `integer` |  |  |
| `from` | `anchors` \| `previous` |  |  |

### `processTrigger` { #schema-processtrigger }

Event source: a core log event or an observation. where is a CEL filter over event

| Field | Type | Required | Description |
|---|---|---|---|
| `event` | `string` |  |  |
| `observation` | `string` |  |  |
| `source` | `string` |  |  |
| `where` | [`cel`](#schema-cel) |  |  |

Exactly one of: `event`, `observation`.

### `assignee` { #schema-assignee }

| Field | Type | Required | Description |
|---|---|---|---|
| `principal` | `envOrUuid` |  |  |
| `role` | `slug` |  |  |
| `agent` | `slug` |  |  |
| `expr` | [`cel`](#schema-cel) |  | CEL → a principal id, agent:&lt;key&gt;, or role:&lt;slug&gt; |

Exactly one of: `principal`, `role`, `agent`, `expr`.

### `assignChain` { #schema-assignchain }

Candidates in order: the first resolvable one is taken

Value: array of [`assignee`](#schema-assignee).

### `escalation` { #schema-escalation }

| Field | Type | Required | Description |
|---|---|---|---|
| `after` | = `due` or [`durationOrCel`](#schema-durationorcel) | yes | due: at the deadline; a duration: after the deadline |
| `action` | `remind` \| `reassign` \| `notify` \| `raise` | yes |  |
| `to` | [`assignChain`](#schema-assignchain) |  |  |
| `error` | [`processError`](#schema-processerror) |  |  |

### `processError` { #schema-processerror }

An error in RFC 7807 form

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `string` | yes |  |
| `status` | `integer` |  |  |
| `detail` | [`cel`](#schema-cel) |  |  |

### `processForm` { #schema-processform }

Step form: JSON Schema of the data and the JSON Forms uischema of the view

| Field | Type | Required | Description |
|---|---|---|---|
| `schema` | `jsonSchema` | yes |  |
| `uischema` | `object` |  |  |

### `governedBy` { #schema-governedby }

Knowledge base regulations that govern the element (TAI-ADR-0054 D17): the natural key of the memory document and, if needed, a section

Value: array of [object](#schema-governedby-item).

### `governedBy[]` { #schema-governedby-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `document` | `string` | yes |  |
| `section` | `string` |  |  |

### `blocks` { #schema-blocks }

A sequence of steps (a do block)

Value: array of [`processStep`](#schema-processstep).

### `durationOrCel` { #schema-durationorcel }

An ISO 8601 duration or a CEL expression that yields a point in time (timestamp) or a duration

Value: [`duration`](#schema-duration) or object `{at}`.

### `duration` { #schema-duration }

An ISO 8601 duration, for example P3D, PT4H

Value: `string`.

### `cel` { #schema-cel }

A CEL expression in the taimen/1 profile (CP-ADR-0075): variables data, event, step, task, instance; cal.* functions; no current time. The core checks types and the cost limit

Value: `string`.

### `celMap` { #schema-celmap }

Path in instance data → CEL expression

Value: map → [`cel`](#schema-cel).

### `processElementId` { #schema-processelementid }

Stable id of a process element: the schema layout, migration maps, the log, and the memory graph refer to it. Renaming only through the migrations map

Value: `string`.
<!-- /generated:schema-process -->

## Calendar (`kind: Calendar`)

<!-- generated:schema-calendar -->
_This section is generated from code; do not edit it by hand._

Source: `packages/schema/v1/object.schema.json`.

### `calendarSpec` { #schema-calendarspec }

Business calendar (TAI-ADR-0054 D6): default weekend, holidays, and moved days by year

| Field | Type | Required | Description |
|---|---|---|---|
| `displayName` | `displayName` | yes |  |
| `timezone` | `string` | yes |  |
| `weekend` | array of `integer` |  | ISO weekdays: 1 is Monday. Default: `[6, 7]`. |
| `years` | array of [object](#schema-calendarspec-years-item) | yes |  |

### `calendarSpec.years[]` { #schema-calendarspec-years-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `year` | `integer` | yes |  |
| `provisional` | `boolean` |  | The year is not approved yet: cal.* results are marked "provisional" |
| `source` | `string` |  |  |
| `holidays` | array of `string` (date) |  |  |
| `workdays` | array of `string` (date) |  | Moved working days that fall on weekends |
| `shortDays` | array of `string` (date) |  |  |
<!-- /generated:schema-calendar -->

## Package test (`tests/*.test.yaml`)

<!-- generated:schema-test -->
_This section is generated from code; do not edit it by hand._

Source: `packages/schema/v1/test.schema.json`.

### `test` { #schema-test }

A &lt;name&gt;.test.yaml file in the package's tests/ directory. The core runs it (POST /packages:test) with the same engine as a live run, in a sandbox: tasks, approvals, and timers are in memory; skills, agents, and memory are stubs checked against the catalog schemas; time is virtual. There are no side effects.

| Field | Type | Required | Description |
|---|---|---|---|
| `$schema` | `string` |  |  |
| `process` | `string` | yes | Key of the package process |
| `version` | `integer` |  | Defaults to the version in the package |
| `name` | `string` | yes |  |
| `description` | `string` |  |  |
| `given` | [object](#schema-test-given) |  |  |
| `mocks` | [object](#schema-test-mocks) |  |  |
| `steps` | array of [`testStep`](#schema-teststep) | yes |  |
| `coverage` | [object](#schema-test-coverage) |  |  |

### `test.given` { #schema-test-given }

| Field | Type | Required | Description |
|---|---|---|---|
| `clock` | `string` (date-time) |  | Initial virtual time |
| `data` | `object` |  | Initial instance data (without a start event) |
| `stage` | `string` |  | Start with an open stage |
| `fromInstance` | `string` |  | Only a trial run on a deployment: state is copied from a live instance |
| `calendar` | `string` |  | Calendar key instead of the process calendar |
| `principals` | map → array of `string` |  | Role → fictitious test principals (for assignments and separation of duties) |

### `test.mocks` { #schema-test-mocks }

| Field | Type | Required | Description |
|---|---|---|---|
| `skills` | map → array of [`mockAnswer`](#schema-mockanswer) |  | name@version → answers in call order (or by when); the output is checked against the skill schema from the catalog |
| `agents` | map → array of [`mockAnswer`](#schema-mockanswer) |  |  |
| `recall` | array of [`mockAnswer`](#schema-mockanswer) |  | Memory answers to recall steps; step is the step id, when is CEL over the query |

### `test.coverage` { #schema-test-coverage }

| Field | Type | Required | Description |
|---|---|---|---|
| `minimum` | `number` |  | Coverage threshold of process elements by this test, % |

### `mockAnswer` { #schema-mockanswer }

| Field | Type | Required | Description |
|---|---|---|---|
| `step` | `string` |  |  |
| `when` | `string` |  | CEL over the call input |
| `output` | any |  |  |
| `error` | [object](#schema-mockanswer-error) |  |  |
| `timeout` | = `true` |  |  |

Exactly one of: `output`, `error`, `timeout`.

### `mockAnswer.error` { #schema-mockanswer-error }

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `string` | yes |  |
| `status` | `integer` |  |  |
| `detail` | `string` |  |  |

### `testStep` { #schema-teststep }

| Field | Type | Required | Description |
|---|---|---|---|
| `emit` | [object](#schema-teststep-emit) |  |  |
| `advance` | `string` |  | Advance virtual time (ISO 8601, P3D) or up to a moment: until:&lt;timer id&gt; |
| `complete` | [object](#schema-teststep-complete) |  |  |
| `approve` | [object](#schema-teststep-approve) |  |  |
| `expect` | [object](#schema-teststep-expect) |  |  |

Exactly one of: `emit`, `advance`, `complete`, `approve`, `expect`.

### `testStep.emit` { #schema-teststep-emit }

| Field | Type | Required | Description |
|---|---|---|---|
| `event` | `string` |  |  |
| `observation` | `string` |  |  |
| `source` | `string` |  |  |
| `payload` | `object` |  |  |

Exactly one of: `event`, `observation`.

### `testStep.complete` { #schema-teststep-complete }

| Field | Type | Required | Description |
|---|---|---|---|
| `step` | `string` | yes |  |
| `by` | `string` |  | a test principal or agent:&lt;key&gt; |
| `output` | `object` |  | Form data or the agent result; checked against the form schema |
| `cancel` | = `true` |  |  |

### `testStep.approve` { #schema-teststep-approve }

| Field | Type | Required | Description |
|---|---|---|---|
| `step` | `string` | yes |  |
| `by` | `string` | yes |  |
| `decision` | `approve` \| `reject` | yes |  |
| `expectRefused` | `string` |  | Core denial code, for example separation_of_duties_violation |

### `testStep.expect` { #schema-teststep-expect }

| Field | Type | Required | Description |
|---|---|---|---|
| `stages` | map → `open` \| `completed` \| `skipped` \| `not_started` |  |  |
| `milestones` | array of `string` |  |  |
| `tasks` | array of [object](#schema-teststep-expect-tasks-item) |  |  |
| `timers` | array of [object](#schema-teststep-expect-timers-item) |  |  |
| `data` | `object` |  | Path in data → expected value |
| `events` | array of `string` |  | Types of process.* events since the last expect |
| `memory` | [object](#schema-teststep-expect-memory) |  |  |
| `outcome` | `string` |  |  |
| `status` | `running` \| `suspended` \| `completed` \| `failed` \| `cancelled` |  |  |
| `error` | `string` |  |  |
| `noSideEffects` | = `true` |  |  |

### `testStep.expect.tasks[]` { #schema-teststep-expect-tasks-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `step` | `string` |  |  |
| `status` | `string` |  |  |
| `assignee` | `string` |  |  |
| `due` | `string` |  |  |

### `testStep.expect.timers[]` { #schema-teststep-expect-timers-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `string` |  |  |
| `at` | `string` |  |  |
| `provisional` | `boolean` |  |  |

### `testStep.expect.memory` { #schema-teststep-expect-memory }

| Field | Type | Required | Description |
|---|---|---|---|
| `recalled` | array of `string` |  |  |
| `remembered` | array of `object` |  |  |
<!-- /generated:schema-test -->

## See also

- [Processes](../processes/index.md)
- [Expressions](../processes/expressions.md)
- [Package tests](../processes/package-tests.md)
- [Catalog packages](../control-plane/catalog-packages.md#processes)
