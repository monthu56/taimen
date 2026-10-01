
# Work: task types and roles

How a package describes work: task types with their lifecycle, fields,
instructions, decision outcomes, work after completion, acceptance, inputs,
and outputs; roles and capabilities, artifact types, project templates, and
workspace types. This page is for package authors: what to write in the files
and how to test it. The full grammar of each field is in the Control Plane
articles that the links lead to.

## What belongs to the package and what to the installation

| In the package | In the installation and with the administrator |
|---|---|
| which tasks exist, their statuses, fields, and outcomes | in which workspace they appear (variables) |
| roles and their assignment to the package's agents | which people hold a role |
| artifact types and their schema | the installation's storage limits |
| project templates, workspace types | the workspace tree itself and the projects |

A package knows nothing about the people of a particular tenant. A role is an
address ("who approves access"), and who stands behind it is decided by the
installation administrator by assigning the role to a principal.

## Task types { #task-types }

A task type (`TaskType`, folder `task-types/`) is the vocabulary and rules of
one kind of work. Core tasks created by processes, rules, decision outcomes,
and people always belong to some version of a type.

```yaml
apiVersion: taimen.ai/v1
kind: TaskType
key: access-review
spec:
  displayName: Access review
  description: A decision on an access request
  fieldSchema: {…}          # task fields — customFields
  lifecycleSchema: {…}      # statuses, transitions, system statuses
  instructions: |           # text for the executor
    …
  execution: {…}            # the task is executed by one skill invocation
  approvalSchema: {…}       # what the core does after a decision on the task
  completionSchema: {…}     # what the core creates after the task is completed
  acceptance: […]           # acceptance criteria for all tasks of the type
  artifactSchema: {…}       # inputs and outputs — artifacts
  contextSchema: {…}        # task context profile from memory
```

Only `displayName` and `lifecycleSchema` are required.

### Lifecycle

Status names belong to the package; the core makes decisions by the status
**category**: `backlog`, `active`, `blocked`, `terminal_success`,
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
    claimStatus: in_progress      # on claim; not terminal
    releaseStatus: todo           # on release; not terminal
    completionStatus: done        # on successful completion; terminal_success
```

`package-sdk add task-type <key>` writes exactly this four-status lifecycle.
A status can have any name: the core looks at the category. Transitions are
declared explicitly: status changes and outcome actions follow only the
declared edges. See [Task types and statuses](../control-plane/task-types.md)
for details.

### Fields and instructions

- `fieldSchema` is a JSON Schema 2020-12 of the task fields (`customFields`):
  their form for a person and the executor's input.
- `instructions` is Markdown up to 16 KiB: what the executor has to do and how
  to hand in the result. This is the task type layer of the executor
  instructions, after the general rules of the platform and the project; the
  core checks the size and the absence of secrets.
- `execution: {skill, version, inputs?}` means a task of the type is executed
  by one skill invocation; the default input is `$.customFields`.

### Decisions: `approvalSchema`

A person's decision on a task is a gate approval. The type declares what the
core does after the decision, using a closed vocabulary of actions:
`ensureWork`, `completeTask`, `comment`, `transition`, `invokeSkill` with the
reactions `onSuccess` and `onFailure`. Only the `default` gate with the
outcomes `approved` and `rejected` is executed.

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

- Strings are the expressions `$.task…`, `$.spawnedBy…`, `$.approval…`, and
  in reactions to an invocation also `$.invocation…`. The `!` suffix makes a
  value required: an empty value does not turn into, for example, an
  invocation without input.
- Close the task in `onSuccess`, not next to `invokeSkill`: an approval is
  grounds for an external write only while the task is open.
- The core checks the grammar when a type version is published:
  `422 invalid_approval_schema` with the path to the error.

The action vocabulary and expressions are in
[Approvals](../control-plane/approvals.md).

**Who decides the gate.** `approvalSchema` declares only the outcomes. The
addressee, a role holder (`requiredRoleId`) or a specific principal
(`assignedPrincipalId`), is set by whoever requests the gate approval on the
task:

| Who requests | How they address it |
|---|---|
| the task's executor (a person or an agent) | `POST /api/v1/approvals` with `gate: true` and the addressee (the `approvals.manage` permission), see [Approvals](../control-plane/approvals.md) |
| a package rule | the `request_decision` action: `fields.approverRole` is a role UUID (in a package, a variable of kind `role`), or `fields.approver` is a principal |
| an outcome or `completionSchema` of another type | `ensureWork.requestApproval.assignee`, a principal only (a `$.task…` expression or a UUID); a role cannot be addressed here |

A package cannot yet bind "the gate of this type is decided by role X" to the
type: the requester chooses the addressee. Until there is such a field, write
the addressee into the type's `instructions` ("ask the `purchase-approver`
role for an approval") or create the task with a rule's `request_decision`.
A task type scenario does not check the decider's rights either: `approve.by`
passes for any principal, even without a role in `given.principals`.

### After completion: `completionSchema`

What the core creates when a task of the type completes successfully,
whoever completed it. The vocabulary is narrower: `ensureWork` (with
`customFields`, `relation`, and `requestApproval`) and `comment`; the
expressions are `$.task…` and `$.spawnedBy…`.

```yaml
  completionSchema:
    onComplete:
      when: ["$.task.customFields.resource"]   # all non-empty — otherwise nothing
      actions:
        - comment: {body: "Access review closed"}
```

`when` is optional: without it, the actions run on every completion.

### Acceptance: `acceptance`

Criteria that every task of the type passes at the verification stage,
before the task's own criteria. Kinds: `deterministic`, `external_state`,
`human`, `llm_judge`; `when` holds `$.task…` paths, and when they are empty
the criterion is skipped.

```yaml
  acceptance:
    - key: decided
      kind: human
      description: An approver decided on the request
```

- A task cannot replace a type criterion with its own criterion with the same
  `key` (`422`).
- A `deterministic` criterion with an external-write skill is allowed only if
  a human decision (`human` or `llm_judge`) comes before it.

See [Type acceptance](../control-plane/task-types.md#type-acceptance) and
[Verification stage](../control-plane/goals-and-evidence.md#verification-stage)
for details.

### Inputs and outputs: `artifactSchema`

Which artifacts a task of the type receives as input from related tasks and
which it has to hand in:

```yaml
  artifactSchema:
    outputs:
      - {key: grant, type: access-grant, required: false}
```

An element has `key`, `type` (the artifact type key), `required`, and
`mediaTypes` (a narrowing of the artifact type). Without a required input,
the task cannot be claimed (`409 input_missing`); a required output is a
deterministic criterion of the verification stage. See
[Inputs and outputs](../control-plane/task-types.md#artifact-schema) for
details.

### Context: `contextSchema`

The task context profile from memory: anchors, graph traversal, a time
slice, a token budget. The core checks the grammar. See
[Task context and memory](../control-plane/context.md) for details.

### Type versions

A published type version is immutable. If the file differs from the newest
active version, a new version is published, and the previous active ones
move to `deprecated`. A task remembers the version it was created with: its
outcomes and acceptance run according to that version, not the new one.

## Task type tests { #tests }

A test with `subject: taskType` checks decision outcomes, acceptance, and
work after completion with the same core code as on the deployment, in a
transaction that is rolled back. Skills are replaced with responses from
`mocks`.

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

| Step | What it does |
|---|---|
| `approve: {decision, by?, gate?, comment?}` | a decision on a gate (`approved` or `rejected`); the outcomes run |
| `verify: {check, result, output?}` | the result of a type acceptance criterion (`passed` or `failed`) |
| `complete: {output?}` | successful completion of the task; `completionSchema` runs |
| `expect` | `ensureWork`, `invokeSkill`, `status {key?, category?}`, `comments` (substrings), `noSideEffects` |

The `package-sdk test` report shows the type's coverage: the outcomes passed
(including the `onSuccess`/`onFailure` reactions), completion actions, and
acceptance criterion outcomes, and lists what is not covered.

```text
покрытие типа задачи access-review v1 (тестов 2): outcomes 3/4, completion 1/1, acceptance 1/2
   не пройдены (outcomes): default/approved/0/onFailure
   не пройдены (acceptance): acceptance/decided:failed
```

The tool prints the report in Russian: `покрытие типа задачи … (тестов 2)`
means "task type coverage … (2 tests)", and `не пройдены` means "not passed".

!!! note "Variables in tests"
    If the package objects use `${VARIABLES}`, a test needs their values: the
    `--env` file (`.env` by default), the environment, or `given.variables` in
    the test itself. Otherwise the test fails with the error
    `unresolved_install_variable`. The exception is variables of kinds
    `workspace`, `principal`, and `role`: the sandbox replaces them with its
    own test rows (see [Package tests](testing.md#subjects)).

## Roles { #roles }

A role (`Role`, folder `roles/`) is a tenant-level address for work and
decisions: a process assigns a step to a role, an approval is addressed to a
role, and an executor with this role can claim a task with such a
requirement.

```yaml
apiVersion: taimen.ai/v1
kind: Role
key: access-approver
spec:
  name: Access approver
  description: Decides on access requests
```

- The key is the role slug. A role from a dependency package is visible to
  the package through `requires`.
- A role is assigned to the agents of the package itself in the agent
  description: `identity.roles: [access-approver]`. To people, it is assigned
  by the installation administrator.
- In tests, the role holders are set by `given.principals: {<role>:
  [<fictitious principals>]}`.
- Roles do not grant API permissions: they determine who can claim a task and
  decide an approval (see
  [Organizational model](../control-plane/authorization.md#org-model)).

## Capabilities { #capabilities }

A capability (`Capability`, folder `capabilities/`) is an ability of an
executor that a task can require: "knows Python", "has access to the
directory". The key is the name of the ability, and `spec` holds only
`description`.

```yaml
apiVersion: taimen.ai/v1
kind: Capability
key: directory-admin
spec:
  description: Can change access rights in the directory service
```

A capability is assigned to an agent of the package itself in the agent
description: `identity.capabilities: [directory-admin]`. A capability is only
created: an installation cannot change the description of an existing one,
and a mismatch is a warning.

## Artifact types { #artifact-types }

An artifact type (`ArtifactType`, folder `artifact-types/`) is the form of a
result that tasks hand in and pass to each other.

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

| Field | What it sets |
|---|---|
| `metadataSchema` | the JSON Schema of the `metadata` of an artifact of this type, up to 16 KiB |
| `mediaTypes` | allowed media types of the content; any by default |
| `maxBytes` | the content size limit; not above the installation limit |

Versions are immutable, as with a task type; a task type's `artifactSchema`
references the artifact type. See
[Artifacts](../control-plane/artifacts.md#artifact-types) for details.

## Project templates { #project-templates }

A project template (`ProjectTemplate`, folder `project-templates/`) sets the
project fields (`fieldSchema`), its statuses (`lifecycleSchema` with the
categories `planned`, `active`, `paused`, `terminal_success`,
`terminal_cancelled`), default settings (`defaultConfig`, `defaultViews`),
execution constraints (`governanceSchema`), and memory defaults
(`memoryDefaults`). A template is versioned and immutable: a project
references an exact version. See [Work model](../control-plane/work-model.md)
for details.

## Workspace types { #workspace-types }

A workspace type (`WorkspaceType`, folder `workspace-types/`) is a kind of
node in the workspace tree: `displayName`, the node fields (`fieldSchema`),
and which types are allowed as children (`allowedChildTypes`).

```yaml
apiVersion: taimen.ai/v1
kind: WorkspaceType
key: department
spec:
  displayName: Department
  allowedChildTypes: [team]
```

A type is edited in place. An installation does not restore an archived
type: that is an error. A package does not create the workspace tree itself:
it is the installation's topology, and its UUIDs reach the package as
[variables](anatomy.md#variables).

## Common problems

| Symptom | Cause | What to do |
|---|---|---|
| `invalid_approval_schema` during the check | the gate is not `default`, an unknown action or expression, a transition not along a declared edge | fix it using the path in the message |
| `invokeSkill.skill: … cannot be invoked here (not_found)` | the skill is not in the package and its `requires`, or the type was not published in the sandbox because of another error | declare the `Skill` in the package or add the package with the skill to `requires` |
| test: `unresolved_install_variable` | an object uses a variable, and there is no value | set it in `.env`, the environment, or `given.variables` |
| the task is not completed after approval | `completeTask` is next to `invokeSkill`, not in `onSuccess`, or there is no edge to `completionStatus` | move it to `onSuccess`, declare the transition |
| a step task did not appear, `intent_failed unknown_role` | the role has no holders in `given.principals` and is not declared in the package | declare the role in the package and set its holders in the test |

## See also

- [Packages](index.md)
- [Package anatomy](anatomy.md): keys, versions, variables
- [Rules in a package](rules.md): who creates tasks from facts
- [Processes in a package](processes.md): tasks of case steps
- [Task types and statuses](../control-plane/task-types.md)
- [Approvals](../control-plane/approvals.md)
- [Goals, acceptance, and evidence](../control-plane/goals-and-evidence.md)
