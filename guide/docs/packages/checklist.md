
# Package readiness checklist

A checklist to go through before releasing a package and its integration: what
must be done so that the package installs into someone else's installation
without edits and without core changes. This page is for package authors and
reviewers. Each item links to the article that explains it.

## The boundary with the core

- [ ] Not a single core change for the sake of the domain: statuses, fields,
      steps, decision tables, and domain words are in the package
      ([Packages](index.md#rule-or-process)).
- [ ] The vertical has no orchestrator, database, or daemon of its own: the
      course of a case is a process, reactions to facts are rules, actions in
      the outside world are skills
      ([A vertical is a package without a runtime](index.md#vertical)).
- [ ] The package has no interface of its own: people see its work wherever
      they see any core work ([The human interface](index.md#ui)).
- [ ] Memory is accessed only through the core: processes (`memory`,
      `recall`, `remember`), observer snapshots, skills' `ctx.knowledge`
      ([Knowledge and ontology](knowledge.md)).

## Manifest and variables

- [ ] `spec.version` is SemVer, raised according to the nature of the changes
      ([Installation and release](install-and-release.md#release)).
- [ ] `engines` is the range of core versions the package has been checked
      on; `requires` have ranges ([Anatomy](anatomy.md#engines)).
- [ ] `license` (SPDX), `authors`, and `description` are filled in.
- [ ] Everything that depends on the deployment (workspace UUIDs, addresses,
      thresholds) is a `${NAME}` variable with `description` and `kind`; the
      files contain no deployment UUIDs
      ([Variables](anatomy.md#variables)).
- [ ] Not a single secret value in the package: secrets are names in the
      agents' `placement.secrets`.
- [ ] `knowledge` names the ontologies the processes rely on; the package's
      own ontology extends the base one rather than redeclaring its kinds.

## Work, rules, processes

- [ ] Every task type has `instructions` for the executor and a `fieldSchema`
      for the fields that the process and the rules read ([Work](work.md)).
- [ ] An external write (`external_write`) comes after a human decision: in a
      task type gate outcome or as a `call` step right after a process
      `approve`; the `retry` and short `timeout` around it are chosen
      deliberately ([Package skills](skills.md#external-write),
      [External write from a process](processes.md#external-write)).
- [ ] A one-off reaction to a fact is a rule with `dedupKeyTemplate`; a case
      with stages and deadlines is a process
      ([Rule or process](rules.md#rule-or-process)).
- [ ] Rules and processes have an identity `identity: {agent: …}` with
      permissions for exactly their actions ([Package agents](agents.md)).
- [ ] A process with new behavior gets a new `spec.version`; removed elements
      with live cases get a `migrations` map; an object rename is `renames`
      ([Processes in a package](processes.md#versions)).

## Integration

- [ ] Skill contracts are generated from code (`skill-sdk export`); the YAML
      is not edited by hand ([Package skills](skills.md)).
- [ ] A skill with an external write is idempotent: the invocation key is
      passed to the external system.
- [ ] An expected skill outcome is an output; an environment failure is a
      `SkillError` with `retryable` ([skill-sdk](../sdk/skill-sdk.md),
      "Outcome versus failure").
- [ ] The observer builds `dedup_key` from what makes a fact the same fact
      (the object and its version); the cursor is in `ctx.state`
      ([Integrations](integrations.md#observer)).
- [ ] The observer and skill host images are built from the generated
      `Dockerfile` on top of the platform base images and pinned by tag; the
      package has `executor.image` ([Integrations](integrations.md#images)).
- [ ] Node labels and secret names are named after the meaning of the access,
      not after the machine; `package-sdk describe .` shows their full list.

## Agents and permissions

- [ ] One role, one agent; the skill host and the observer are different
      agents.
- [ ] Agent permissions are exactly what their actions do: for the skill host,
      `sessions.open`, `tasks.read`, `skills.execute`; for the observer,
      `observations.write`; for no one, `admin` and `approvals.decide`
      ([Package agents](agents.md#identity)).
- [ ] The desired state of agents (`state`, `replicas`) is set in the file,
      not by stopping them manually on the deployment.

## Tests

- [ ] `package-sdk test .` is fully green: the check, skill contracts,
      integration code tests, scenarios ([Package tests](testing.md)).
- [ ] A scenario for every process branch, every rule condition branch, and
      every gate outcome; the report has no `не пройдены` (not passed) and no
      `без сценариев` (without scenarios).
- [ ] Skill stubs in scenarios respond according to the skill contract; an
      external system failure is covered by a scenario as well.
- [ ] The package CI runs the pyramid with a PostgreSQL database for rule and
      task type scenarios, and `package-sdk docs . --check`.

## Release and installation

- [ ] The README section is updated with `package-sdk docs . --write`; the
      changelog describes what to do when upgrading.
- [ ] The release tag is published and has not been moved.
- [ ] The installation takes the package from git by tag; `packages.lock` is
      updated and committed to the installation's git
      ([Installation and release](install-and-release.md#lock)).
- [ ] The `plan --out` plan is shown to a human in full: sections, console
      edits, replay, and the fate of live cases; exactly this plan is applied
      with `apply --plan`.
- [ ] What is no longer needed is retired with the installation's `retire`,
      not by deleting package files.

## See also

- [Packages](index.md)
- [Example: customer claims](tutorial.md)
- [Package tests](testing.md)
- [Installation and release](install-and-release.md)
- [Package author in Claude Code](author-plugin.md)
