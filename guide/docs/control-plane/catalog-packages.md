
# Catalog packages

The Control Plane catalog consists of task types, artifact types, project templates,
workspace types, roles, capabilities, skills, work rules, and agent
descriptions; next to them, notification rules of the notification service live in a package. It
is stored in git as **packages**: YAML files in
the superproject's `packages/` directory. The `tools/cp_packages.py` tool validates
packages without a deployment, reconciles them with a live Control Plane, and applies them. This article is for
installation administrators and vertical package authors. Rationale
for the decision: TAI-ADR-0044.

## Why packages

- **Git is the source of truth.** Control Plane stores published versions of
  objects, and a package says what they should be. An edit through the API that bypasses
  the package is visible: `plan` shows the divergence, and `apply` publishes the version from git
  on top of it.
- **Reproducibility.** A new installation gets the catalog at the bootstrap step,
  without manual API calls.
- **The same for humans and machines.** Files are written by hand, exported from
  a deployment with the `export` command, or generated from code (skills, via skill-sdk).
- **A package is data.** The format and the installer belong to the core, the contents
  of packages belong to the domain.

## Structure of the `packages/` directory

```text
packages/
├── README.md
├── schema/
│   └── v1/object.schema.json      # JSON Schema 2020-12 of the format
└── example/                       # hypothetical package (requires: [])
    ├── package.yaml               # manifest: kind: Package
    ├── agents/                    # kind: Agent
    ├── artifact-types/            # kind: ArtifactType
    ├── task-types/                # kind: TaskType
    ├── rules/                     # kind: WorkRule
    ├── notification-rules/        # kind: NotificationRule — for the notification service
    └── skills/                    # kind: Skill
```

The delivery includes the format, the `packages/schema` schema, the installer
`tools/cp_packages.py`, and a minimal sample package, `packages/example` (one
task type, `request`); it contains no domain packages. The examples below use a
package named `example` with more objects than the sample has.

Installation files (which packages to install in a particular environment) live in
`deploy/`:

| File | Purpose |
|---|---|
| `deploy/packages.yaml` | the default installation, used by `make bootstrap` |
| `deploy/<environment>/packages.yaml` | an environment's own installation with its own `retire` list |

## Object format

Each file is one object in a common envelope:

```yaml
# yaml-language-server: $schema=../../schema/v1/object.schema.json
apiVersion: taimen.ai/v1
kind: TaskType
key: document-review
spec:
  displayName: Document review
  description: Review of a document by a lawyer.
  fieldSchema: { ... }
  lifecycleSchema: { ... }
  approvalSchema: { ... }
  acceptance: [ ... ]
```

| Field | Rule |
|---|---|
| `apiVersion` | the format constant `taimen.ai/v1` (a schema identifier, not a service address) |
| `kind` | `Package`, `Installation`, `ArtifactType`, `TaskType`, `ProjectTemplate`, `WorkspaceType`, `Role`, `Capability`, `Skill`, `WorkRule`, `Agent`, `NotificationRule` |
| `key` | the identity within a tenant, 1–200 characters; for `Package`, `ArtifactType`, `TaskType`, and `ProjectTemplate` — `^[a-z0-9][a-z0-9_-]*$`, no longer than 63; for `Role` and `Agent` — a slug `^[a-z0-9][a-z0-9-]*$`, 2–63 characters; for `WorkRule` and `NotificationRule` — `^[a-z0-9][a-z0-9._-]*$`, up to 128 characters |
| `spec` | **exactly the API request body** in camelCase, without the identity field: of Control Plane, and for `NotificationRule`, of the notification service. Field names match the service's OpenAPI |

The line `# yaml-language-server: $schema=…` enables schema validation and hints
in the editor. Folders by kind (`task-types/`, `skills/`, …) are only a
convention for people. The object's kind is determined by the `kind` field, not by the path.

### Mapping to the API

| kind | Folder | Identity field in the API | How it is applied |
|---|---|---|---|
| `Package` | `package.yaml` | the package directory | `spec.version` (SemVer), `displayName`, `description`, `requires` |
| `ArtifactType` | `artifact-types/` | `key` | an artifact type (see [below](#artifact-type)): versions are immutable and are never retired; a new version is published only if the file differs from the newest version |
| `TaskType` | `task-types/` | `key` | versions are immutable: on divergence from the newest active version a new one is published, and the other active versions of the key are moved to `deprecated`. The `acceptance` section holds the default acceptance criteria for all tasks of the type (see [Type acceptance](task-types.md#type-acceptance)) and takes part in the comparison |
| `ProjectTemplate` | `project-templates/` | `key` | the same as `TaskType` |
| `WorkspaceType` | `workspace-types/` | `key` | create, or `PATCH` (with `If-Match`) on divergence; a package will not restore an archived type — this is an error |
| `Role` | `roles/` | `slug` | tenant-level roles; create or `PATCH` |
| `Capability` | `capabilities/` | `name` | creation only; a description divergence is a warning (the API does not change the description) |
| `Skill` | `skills/` | `name` + `spec.version` | create a version; a divergence in `protocol`, `sideEffects`, `riskLevel`, or `contract` is an error "bump `spec.version`"; a divergence in `description`, `config`, `inputSchema`, `outputSchema` — `PATCH`, but for a published version the core changes only `description` (and status) and rejects the rest with `409 skill_version_immutable` |
| `Agent` | `agents/` | `key` | an agent (see [below](#agent)): first `POST /agents:validate`; if neither the revision nor the desired state changes — "no changes", otherwise `POST /agents`. A new immutable revision appears only if the description hash differs; `state` and `placement.replicas` change the desired state without a revision |
| `WorkRule` | `rules/` | `key` | a work rule (see [Work rules](work-rules.md)): create, or `PATCH` (with `If-Match`) the changed `description`, `trigger`, `condition`, `interpretation`, `action`, `identity`; `status` (`enabled`/`disabled`, `enabled` by default) — through `:enable`/`:disable`. `workspaceId` is set only by an installation variable (`${NAME}`) and does not change after creation. With `identity: {agent: <key>}` the rule acts with the authority of this agent; without it — with the authority of whoever's token applied the package. Removing `identity` from the file is `PATCH identity: null` |
| `NotificationRule` | `notification-rules/` | `key` | a notification rule (see [below](#notification-rule)): applied **to the notification service**, not to the core; the service computes the version from the spec hash |
| `Calendar` | `calendars/` | `key` | a business calendar: weekends, holidays, and working-day transfers by year; applied only through a core plan (see [Processes](#processes)) |
| `Process` | `processes/` | `key` + `spec.version` | a process: stages, steps, decision tables, timers, data by JSON Schema; applied only through a core plan (see [Processes](#processes)) |

There is no deletion for any kind. The application order is set by dependencies:
`WorkspaceType` → `Capability` → `Role` → `Skill` → `ArtifactType` →
`TaskType` → `Agent` → `ProjectTemplate` → `Calendar` → `Process` → `WorkRule` →
`NotificationRule`. Whatever is
referenced is created earlier: a task type's `artifactSchema` references
artifact types, so they are published before task types; an agent references roles
and task types, so it comes after them; a rule with `identity` references an agent.
Notification rules do not reference anything in the core, but they take effect immediately after
being applied, so they go last — when the core is already reconciled.

### Agent (`Agent`) { #agent }

A file in the `agents/` folder describes an agent in full: identity and permissions, which work
it takes, the executor kind with parameters and instructions, the working copy,
skills, and placement on nodes (TAI-ADR-0052). The schema is `$defs.agentSpec` in
`packages/schema/v1/object.schema.json`.

```yaml
# yaml-language-server: $schema=../../schema/v1/object.schema.json
apiVersion: taimen.ai/v1
kind: Agent
key: reviewer
spec:
  displayName: Code reviewer
  identity:
    kind: agent
    permissions: [sessions.open, tasks.read, tasks.write, tasks.claim, artifacts.read, artifacts.write]
  work:
    workspace: ${AGENTS_WORKSPACE_ID}
    taskTypes: [code-review]
  executor:
    kind: claude-code
    params: {model: <model-id>, permissionMode: acceptEdits}
  workingCopy:
    repository: https://git.example.com/org/service.git
    publish: false
  placement:
    requires: [repos]
    secrets: [claude-oauth-token]
```

Specifics of this kind:

- `check` validates the description against the format schema and the core's `AgentSpec` model,
  requires `work.taskTypes` to be declared in the package or its
  `requires`, and warns about roles from `identity.roles` that are not in
  the packages (they must already exist in the tenant);
- topology — `work.workspace`, `work.project` — is written as an installation variable
  `${NAME}` or a UUID;
- the `workingCopy.review` section is deprecated: review is declared by the task type as acceptance
  criteria (see [Type acceptance](task-types.md#type-acceptance));
- secret values are not written into the description — only names in
  `placement.secrets`;
- `apply` also applies the desired state from the file (`state`,
  `placement.replicas`): an agent stopped manually will be started again by the next
  application if the file has `state: running`;
- `retire.Agent` in the installation file retires the agent: the executor
  stops, the credential is revoked, the run history remains;
- `export` exports the `spec` of the current (or the `--version`-specified) revision, and
  `state` and `replicas` from the desired state, omitting defaults.

Placement of executors on machines according to the `placement` description is not part of
the delivery: you can start an executor described by an agent manually with the
`control-plane-agent` daemon (see [Runner](../runner/index.md)).

### Notification rule (`NotificationRule`) { #notification-rule }

A file in the `notification-rules/` folder describes which Control Plane event
becomes a notification: event and condition → recipient → type, title, text,
links, decision buttons → closing the buttons on the outcome event. The schema is
`$defs.notificationRuleSpec` in `packages/schema/v1/object.schema.json`, and the full
description is in the article [Notification rules](../notifications/notification-rules.md).

```yaml
# yaml-language-server: $schema=../../schema/v1/object.schema.json
apiVersion: taimen.ai/v1
kind: NotificationRule
key: task-verified
spec:
  "on": {type: task.verified}
  recipient: {kind: taskOwner, fallback: taskAssignee}
  notification:
    type: task.verified
    title: "Accepted: {{task.publicId}} {{task.title}}"
    links:
      - {label: Open task, url: "${TASK_URL_BASE}/{{task.publicId}}"}
```

Specifics of this kind:

- it is applied **to the notification service**: the address is the installation variable
  `NOTIFICATION_SERVICE_URL`, the token is `NOTIFY_TOKEN` (an access token with audience
  `notification-service`, scope `notifications:admin`) or an exchange of the same IAM
  credential the installer uses for this audience;
- before the first write — both to the core and to the service — the installer calls `:validate` for
  all rules of the installation: a rule the service will not accept stops
  the whole installation; after that, only changed rules are sent with `POST`;
- without `NOTIFICATION_SERVICE_URL`, `apply` skips notification rules with
  a warning (for example, during bootstrap before the notification service step);
- the `on` key is written in quotes (`"on":`) — otherwise YAML 1.1 reads it as `true`;
- `retire.NotificationRule` retires the rule (`:retire`); sent
  notifications remain;
- `export --kind NotificationRule` exports the active version from the service;
  `--server` is not needed, `--version` is not supported.

### Artifact type (`ArtifactType`) { #artifact-type }

A file in the `artifact-types/` folder declares an artifact type — the key, the `metadata`
schema, allowed media types, and the content size ceiling (the model is in
[Artifacts](artifacts.md#artifact-types)):

```yaml
# yaml-language-server: $schema=../../schema/v1/object.schema.json
apiVersion: taimen.ai/v1
kind: ArtifactType
key: review-report
spec:
  displayName: Review report
  description: The report that a review delivers and the next step receives
  mediaTypes: [application/pdf]
  maxBytes: 10485760            # optional
  metadataSchema:
    type: object
    properties:
      reviewer: {type: string}
```

| `spec` field | Default in the package | How it is compared with the live version |
|---|---|---|
| `displayName`, `description` | `""` | always |
| `metadataSchema` | `{}` | always |
| `mediaTypes` | `["*/*"]` | always; before comparison they are lowercased, and parameters and duplicates are dropped — this is how the core stores them |
| `maxBytes` | not set — the core takes the installation's `CP_ARTIFACT_MAX_BYTES` at the time of publication | only if set in the file |

Application rules:

- versions are immutable and the API has no deprecation of artifact types, so
  `apply` **does not move** old versions to `deprecated`, and `retire` is not supported for
  `ArtifactType`;
- a new version is published only if at least one compared field of the file
  differs from the newest version of the key; otherwise — "no changes";
- artifacts are always validated against the newest version, so narrowing
  `mediaTypes` or `maxBytes` in a new version immediately affects new
  artifacts of this kind.

A task type's `artifactSchema` (see [Inputs and outputs](task-types.md#artifact-schema))
references artifact types by key. Like other references, it is closed:
the artifact type must be declared in the same package or in a package from
`requires`.

### Package manifest

```yaml
# yaml-language-server: $schema=../schema/v1/object.schema.json
apiVersion: taimen.ai/v1
kind: Package
key: example
spec:
  version: 0.1.0                 # SemVer, required
  displayName: Example           # required
  description: Task types and skills of a hypothetical domain.
  requires: []                   # packages whose objects are referenced here
```

The package key must match the name of its directory. Cycles in `requires`
are forbidden.

### Installation file

```yaml
# yaml-language-server: $schema=../../packages/schema/v1/object.schema.json
apiVersion: taimen.ai/v1
kind: Installation
key: production
spec:
  packages: [example]             # requires are pulled in automatically
  retire:
    TaskType: [ops, analysis]     # all active versions → deprecated
```

- `retire` describes the history of the **environment**, not of the package. Supported are
  `TaskType`, `ProjectTemplate` (active versions → `deprecated`), `WorkRule`
  (the rule is archived, the work it created remains), `Agent`
  (`:retire` — the executor is stopped, the credential is revoked, the key is no longer
  used), and `NotificationRule` (`:retire` in the notification service,
  sent notifications remain). `ArtifactType` is never retired.
- A task type removed from a package is not retired by itself: add it to
  `retire.TaskType` once the open tasks of this type are closed. This is how,
  for example, a former review task type is retired after switching to type acceptance.
- The system task type `task` cannot be retired: the core always keeps
  an active version of it.
- A key cannot be declared in a package and retired at the same time.

## Content rules

**References are by key only, never by UUID.** Examples:

- `execution: {skill: git.merge, version: "1"}` in a task type;
- `ensureWork.type: coding-task` in an approval outcome;
- `invokeSkill.skill: git.merge@1` in an approval outcome;
- `allowedChildTypes: [team]` in a workspace type;
- `artifactSchema.inputs[].type: spec-document` in a task type;
- `identity: {agent: example-rules}` in a work rule;
- `agent:<key>` in assignment fields: `ensureWork.assignee` of an approval outcome,
  `fields.assignee` of a rule.

A package is closed: a reference must lead into the package itself or into a package from `requires`.
The only exception is the system type `task`. For agents (a rule's `identity.agent`
and a literal `agent:<key>`), `check` additionally rejects a reference to
an agent that the same installation retires (`retire.Agent`). A reference
through a template (`{{…}}`, `$.…`) is checked by the core at execution time. For `allowedChildTypes`,
an unclosed reference gives a warning: such a type must already exist in the
tenant.

**Environment parameters are `${NAME}`** in string values of `spec`, for example
the address of an HTTP skill:

```yaml
contract:
  implementation:
    protocol: http
    endpoint: ${EXAMPLE_SKILLS_URL}/merge
```

On `plan` and `apply`, the value is taken from the installation's `.env` (the `--env` flag,
`.env` in the root by default) and from process variables. An unset variable is an installation
error. On `check`, a placeholder is substituted for an unset variable.

**There are no secrets in a package.** The core itself rejects secret material in contracts
and schemas (`secret_material_rejected`).

**Skills are generated from code.** A skill's YAML is not written by hand: it is generated by
skill-sdk from decorators in the integration code
(`skill-sdk export --package packages/<package> <module>`). The source of truth
for a skill contract is the code, and a divergence is caught by the integration test. For details, see
[skill-sdk](../sdk/skill-sdk.md).

## The `tools/cp_packages.py` tool

```text
python3 tools/cp_packages.py check  [--install <file> | --package <package>] [--server <url>] [--json]
python3 tools/cp_packages.py test   (--install <file> | --package <package>) --server <url> [--test <name>] [--json]
python3 tools/cp_packages.py plan   --install <file> --server <url> [--env <.env>] [--out <plan.json>]
python3 tools/cp_packages.py apply  --install <file> --server <url> [--env <.env>]
python3 tools/cp_packages.py apply  --plan <plan.json>
python3 tools/cp_packages.py migrate-expr --package <package> [--write]
python3 tools/cp_packages.py export --server <url> --kind <kind> --key <key> [--key ...] \
                                    [--version <v>] --package packages/<package>
```

| Command | Deployment needed | What it does |
|---|---|---|
| `check` | no (with `--server` — yes) | validates all packages (without `--install`) or the contents of an installation: the format schema, duplicates, closure of references, `retire`, process tests, and Control Plane domain validators; with `--server`, also process validation by the core |
| `test` | yes | runs the package's process tests in the core sandbox and prints the result and coverage |
| `plan` | yes | reconciles the installation with the live Control Plane and prints what will change; writes nothing. With `--out`, a core plan with a hash for `apply --plan` |
| `apply` | yes | installs: first `check`, stops on errors, then applies objects by kind and `retire`; skips `Process` and `Calendar` — they are applied by `apply --plan` |
| `migrate-expr` | no | converts the package's former expression syntaxes to CEL and prints a diff; `--write` writes it |
| `export` | yes | exports objects from the live Control Plane (for `NotificationRule`, from the notification service) into package files (`<package>/<kind folder>/<key>.yaml`) |

Domain validators are the same functions the core calls when creating an object:
parsing a task type's lifecycle, `approvalSchema`, `execution`,
`artifactSchema`, an artifact type definition, a skill contract, the JSON Schema
of fields, the configuration and governance of project templates.

For artifact types and `artifactSchema`, `check` additionally validates:

- the `ArtifactType` definition — the `metadataSchema` schema, the grammar of
  `mediaTypes`, a positive `maxBytes`. Only the installation knows the ceiling
  `CP_ARTIFACT_MAX_BYTES`, so exceeding it is caught by the core on
  `apply` (`422 invalid_artifact_type`);
- the `artifactSchema` grammar (slot fields, `from`, `content`, keys);
- that each input and output `type` is declared as an `ArtifactType` in the package or
  its `requires`;
- that an output's `mediaTypes` narrow the `mediaTypes` of its artifact type. They
are taken from the `control-plane` submodule. If it cannot be imported (no submodule or
no `jsonschema`), `check` issues a warning and validates only the format
schema. It requires `PyYAML` and `jsonschema`.

### Credential for `plan`, `apply`, `export`

The tool calls the API with `Authorization: Bearer <token>`. The token is taken:

1. from the `CP_TOKEN` variable — an IAM access token with audience `control-plane`;
2. if it is not set — from the `control_plane_client` credential, that is, from the same
   IAM identity as the CLI and the MCP server (see [CLI and
   MCP server](cli-and-mcp.md#credentials)). For this, run the script with the
   interpreter of the environment where the `control-plane` package is installed.

The token needs catalog write permissions: `task_types.manage`,
`artifact_types.manage`,
`project_templates.manage`, `workspaces.manage`, `org.manage` (roles,
capabilities, skills), `agents.manage` (agents), `rules.write` (rules), as
well as the corresponding read permissions. The permissions that an agent description grants
to the agent must be held by the token itself: otherwise `403 permission_escalation`. The same
applies to rules with `identity`: whoever applies them must have all permissions of the identity agent.

For `NotificationRule`, a second token is needed — audience `notification-service`,
scope `notifications:admin`: the `NOTIFY_TOKEN` variable or an exchange of the same IAM
credential (the PAT must allow this audience in its ceiling, otherwise IAM responds
`iam_audience_not_allowed`).

## CI check: `make packages-check`

```bash
make packages-check
```

The target performs two checks:

```bash
python3 tools/cp_packages.py check
python3 tools/cp_packages.py check --install deploy/packages.yaml
```

Output:

```text
ok: packages 2, objects 5, tests 0
```

or a list of lines `error: <file>: <message>` with exit code `1`.

## Processes and calendars { #processes }

A process (`kind: Process`) and a business calendar (`kind: Calendar`)
are executed and validated by the Control Plane core itself (rationale: TAI-ADR-0054,
CP-ADR-0074). The process language is described in the [Processes](../processes/index.md) section,
tests and the plan in [Package tests](../processes/package-tests.md). There is no local copy of the engine: without the core, `check` validates only
the form against the schema, references, and package tests.

!!! warning "A Control Plane with the process engine is required"
    The `test`, `plan --out`, and `apply --plan` commands, as well as `check --server`,
    call the routes `POST /api/v1/packages:test`, `/packages:plan`, and
    `/packages:apply`. If the core does not know them (`404`) or does not implement them yet
    (`501 not_implemented`), `check --server` reports "the core does not support
    process validation … — only the schema was checked" and finishes based on the
    static check, while the other commands fail with an error.

### Layout of a package with a process

```text
packages/<package>/
├── package.yaml               # renames — explicit object renames
├── processes/<key>.yaml       # kind: Process
├── calendars/<key>.yaml       # kind: Calendar
├── schemas/<name>.schema.json # data schemas: data: {$ref: ../schemas/<name>.schema.json}
├── tests/<name>.test.yaml     # process tests (schema/v1/test.schema.json)
└── .layout/<key>.json         # diagram layout for the visual editor
```

`data: {$ref: …}` references only a file inside the package. The layout is not sent
to the core and carries no logic.

### Validation, tests, plan, application

```bash
python3 tools/cp_packages.py check --package packages/<package> --server https://platform.example.com --json
python3 tools/cp_packages.py test  --package packages/<package> --server https://platform.example.com
python3 tools/cp_packages.py plan  --install deploy/<environment>/packages.yaml \
    --server https://platform.example.com --out plan.json
python3 tools/cp_packages.py apply --plan plan.json
```

Each request carries one package with its files: `{package: {files: [{path,
content}]}}`, including `tests/` and without `.layout/`, with installation variables
substituted. The core takes packages from `requires` from its own catalog, and
renames from `renames` in `package.yaml`.

- **`check --server`** validates the named packages with the request
  `POST /packages:test?checkOnly=true`. The core's findings are printed as
  `file:line: code: message [path] (hint: …)`; with `--json`, as a list of
  objects `{code, severity, path, file, line, message, hint}`.
- **`test`** prints `ok`/`FAIL` for each test, the step, and the failure reason, and
  then the process coverage: elements, transitions, decision table rows,
  error handlers — and what was not covered. The exit code is `1` if there are
  failed tests.
- **`plan --out`** shows a structural diff (`+` will be added, `~` will change,
  `-` is retired, `→` rename), the field owner (what was edited in the console is not
  overwritten), behavior divergences found by replay, and the fate of open
  instances (`pin` — they finish on their own version, `migrate` — they move according to
  the map), and coverage of regulation sections. The plan is built for each package of
  the installation (`--replay-limit` — how many instances to replay,
  50 by default) and saved to a file together with hashes; a plan with errors
  (for example `migration_required`) is not saved. The installation file's `retire` is not part of
  the core plan — it is performed by a regular `apply --install`.
- **`apply --plan`** sends, for each package, the same files the plan
  was built from, and its `planHash`. If the deployment's catalog has changed in the meantime, the core responds
  `plan_stale` — the plan is rebuilt. A plan file modified after
  it was built is not applied; neither is a plan built for a different address.

### Editing files: `tools/pkg.py` { #pkg }

`tools/pkg.py` performs small edits to a process and a package and changes only
the affected lines: comments, key order, quotes, and the flow/block style of
the rest of the file stay as they were. It requires the `ruamel.yaml` package.

| Operation | What it does |
|---|---|
| `add-step --in <stage or step> --step <yaml> [--after/--before <id>]` | adds a step to a stage or to the `do` block of a step, branch, or timer |
| `add-stage --stage <yaml> [--after/--before <id>]` | adds a stage |
| `add-decision-row --table <id> --row <yaml> [--index N]` | adds a decision table row; the columns are checked against the table's inputs and outputs |
| `add-rule --table <id> --row <yaml>` or `add-rule --on-event <yaml>` | a rule: a decision table row or a process reaction to an event (`onEvent`) |
| `add-form-field --step <id> --name <field> --schema <yaml> [--required] [--label]` | a form field of a human step (and a `uischema` element, if there is one) |
| `rename --file <process> --from <id> --to <id> [--no-migration]` | renames a process element, the references to it, and the package tests; appends the `migrations` map and moves the layout coordinates |
| `rename --package <directory> --kind Process --from <key> --to <key>` | renames a package object and its file, appends `renames` to `package.yaml` |
| `set --path <path> --value <yaml>` | writes a value; in the path, `[N]` is an index and `[id]` is a list element by id |

The `--json` flag prints the result or the error in machine-readable form
(`{"ok": false, "error": {"code", "message", "path", "hint"}}`), and `--dry-run` prints a
diff without writing. An edit that the catalog schema rejects or that
repeats an element id is not written.

Loading and writing a file without changes produces the same file byte for byte: the file's
style (indentation, `-` offset, line width, `null` notation) is detected on
load. ruamel.yaml does not preserve line breaks inside a flow collection (`{a: 1,` and `b: 2}` on different
lines) — `pkg.py` transfers such an edit onto the original
text by merging, and the other lines of the file do not change.

The package language is YAML 1.2: boolean values are only `true`/`false`, and the keys `on`,
`off`, `yes`, `no` are strings.

## How the catalog is applied

### During bootstrap

`deploy/bootstrap.py` applies packages at step **5b** through
`cp_packages.apply()`. By default it uses the file
`deploy/packages.yaml`; you pass a different file with a flag:

```bash
python3 deploy/bootstrap.py --env .env --packages deploy/production/packages.yaml ...
```

The identifiers of published objects are saved in the bootstrap state
(`deploy/state/<name>.json`). UUIDs do not live in the packages themselves. For details,
see the article [Bootstrap](../getting-started/bootstrap.md).

### Manually on a running installation

```bash
# 1. Validate without a deployment
make packages-check

# 2. Review the plan
export CP_TOKEN=<access-token audience control-plane>
python3 tools/cp_packages.py plan \
  --install deploy/production/packages.yaml \
  --server https://platform.example.com

# 3. Apply
python3 tools/cp_packages.py apply \
  --install deploy/production/packages.yaml \
  --server https://platform.example.com
```

Example `plan` output:

```text
   packages: example 0.2.0
   TaskType/coding-task: (plan) new version (acceptance changed)
   TaskType/coding-task: (plan) v5 → deprecated
   Skill/git.bump_submodule@1: (plan) will be registered
   WorkRule/submodule-lag: (plan) identity will change
   NotificationRule/approval-requested: (plan) v1 no changes
   TaskType/ops: v1 → deprecated (retire)
```

!!! note "Tasks on old versions do not change"
    A new task type version and moving the old one to `deprecated` do not affect
    already created tasks: they keep living on their version. New tasks
    by key get the newest active version.

### Moving manual edits into git

An object that was created or edited through the API is exported into a package:

```bash
python3 tools/cp_packages.py export \
  --server https://platform.example.com \
  --kind TaskType --key document-review \
  --package packages/<package>
```

`export` takes the newest active version (or the one given in `--version`),
drops empty fields and default values, and for a skill with a contract
removes the fields derived from the contract (`inputSchema`, `outputSchema`,
`protocol`).

## A new package, step by step

1. Create `packages/<key>/package.yaml` with `kind: Package`. The key matches
   the directory name.
2. Put objects one per file. The easiest way to start is to `export`
   an existing object.
3. If the package references objects of another package, list it in
   `requires`.
4. Run `make packages-check`.
5. Add the package key to `spec.packages` of the environment's installation file.
6. Run `plan`, then `apply` (or a repeated bootstrap).

## What a package does not include

- **Topology**: workspaces, projects, membership, and role assignments to people.
  This is environment data (the bootstrap state), not the catalog. Principals and agent
  bindings are not written into a package either: the platform derives them from the `Agent` description.
- **Fixture tasks.**
- **Domain memory ontology packs** are registered in memory-service
  separately, see [Task context and memory](context.md).

## Common problems

| Message | Cause | What to do |
|---|---|---|
| `PyYAML is required` / `jsonschema is required` | missing dependencies | `pip install pyyaml jsonschema` |
| `control-plane domain validators cannot be imported` | no `control-plane` submodule | `git submodule update --init` |
| `execution references Skill …, which is in neither the package … nor its requires` | unclosed reference | add the package with the skill to `requires` or move the skill |
| `contract differs in the published version — the version contract is immutable` | the contract was edited without changing the version | bump the skill's `spec.version` |
| `environment variable X is not set (required by the package)` | no value for `${X}` | set it in `.env` or the environment |
| `retire: the system type task cannot be retired` | `task` in `retire` | remove it from the list |
| `artifactSchema.inputs 'spec': artifact type 'spec-document' is declared in neither the package … nor its requires` | unclosed reference to an artifact type | declare the `ArtifactType` in the package or add the package that has it to `requires` |
| `artifactSchema.outputs '…': mediaTypes [...] are wider than those of type …` | the output widens rather than narrows the type's media types | narrow the output's `mediaTypes` or widen the artifact type |
| `retire: kind ArtifactType cannot be retired` | `ArtifactType` in `retire` | remove it from the list |
| `the core does not accept the agent description: …` | the `Agent` description does not pass the core's `AgentSpec` model (unknown field, empty `permissions`) | fix the description according to the message |
| `422 non_canonical_value` on agent `apply` | a floating-point number in the description (for example, a fractional `resources.cpus`) | integers only |
| `identity.agent references agent …` / `… — there is no such Agent in the package` | a rule or assignment references an agent outside the package and its `requires`, or one being retired | describe the agent in the package or add the package to `requires` |
| `NotificationRule not applied: notification service not set` | no `NOTIFICATION_SERVICE_URL` or token | set the variable and `NOTIFY_TOKEN` |
| `the notification service does not accept the rule — …` | `:validate` returned `422 invalid_notification_rule` | fix the rule according to `details.errors` |
| `work.taskTypes '…' — there is no such TaskType in the package …` | the agent references a task type outside the package and its `requires` | declare the type or add the package to `requires` |
| `403 permission_escalation` on agent `apply` | the token lacks the permissions the description grants to the agent | apply with a token that has these permissions |
| `no CP_TOKEN and no control_plane_client` | no credential | set `CP_TOKEN` or run with an interpreter that has `control-plane` installed |
| `control-plane did not save execution` | the core release does not support `execution` on a task type | update Control Plane |
| `the core does not support process validation, schema only` / `the core does not know /packages:plan` | Control Plane without the process engine | update Control Plane; until then, processes are validated only by the schema |
| `the plan is stale: the deployment catalog changed after the plan was built` | a `plan_stale` response to `apply --plan` | rebuild the plan and apply the new one |
| `the plan was edited after it was built (hash mismatch)` | the plan file was changed by hand | rebuild the plan |
| `…: processes and calendars are applied by the core from a plan` | the installation contains a `Process` or `Calendar`, but a regular `apply` was called | `plan --out plan.json`, then `apply --plan plan.json` |
| `element_id_taken` from `pkg.py` | the element id already exists in the process | choose a different id |

## See also

- [Processes](../processes/index.md) — the language of the `Process` kind
- [Package tests](../processes/package-tests.md) — validation, tests, replay, plan
- [Task types and statuses](task-types.md)
- [Work rules](work-rules.md)
- [Notification rules](../notifications/notification-rules.md)
- [Artifacts and comments](artifacts.md#artifact-types) — the artifact type registry
- [Approvals](approvals.md)
- [Bootstrap](../getting-started/bootstrap.md)
- [skill-sdk](../sdk/skill-sdk.md)
- [Vertical packages](../sdk/vertical-packages.md)
- [Make targets](../reference/make.md)
