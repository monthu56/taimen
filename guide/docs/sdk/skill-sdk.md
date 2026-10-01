
# skill-sdk

`skill-sdk` (package `skill_sdk`) is the platform's skill SDK: you write a skill once as a
Python function, and the SDK derives the v1 contract from the code, provides a call context,
hosts the skill over any of the three executor protocols (`local`, `http`, `mcp`), and
generates YAML for a Control Plane catalog package. For developers who add new actions for
agents and processes to the platform. Rationale: TAI-ADR-0045; the skill contract is
CP-ADR-0056.

!!! note "Status"
    Version `0.1.x`, license Apache-2.0. The package is connected as a path dependency in a
    neighbouring folder, like the other platform libraries
    (see [SDK and integrations](index.md#connect)). How skills live in a catalog package
    (who calls them, where they are hosted, how an external write is approved) is described
    in [Package skills](../packages/skills.md).

## What a skill is

A skill is a named, versioned action with a formal contract: input and output JSON schemas,
a side-effect class, a risk level, idempotency, a timeout, a retry policy. The core stores
the version contract as immutable; the executor (runner) calls the skill implementation,
checks input and output against the schemas, and publishes the result in the task.

```mermaid
flowchart LR
    Code["@skill in code"] -->|"skill-sdk export"| Y["package/skills/*.yaml"]
    Y -->|"package installation: plan and apply"| CP[Control Plane: Skill name@version]
    CP -->|task with execution.skill| R[Executor]
    R -->|local / http / mcp| H[Skill hosting: skill-sdk]
    H --> Code
```

## Writing a skill

```python
from typing import Literal

from pydantic import BaseModel
from skill_sdk import SkillContext, SkillError, skill


class MergeIn(BaseModel):
    repository: str
    branch: str
    commit: str
    target: str


class MergeOut(BaseModel):
    merged: bool
    sha: str | None = None
    reason: Literal["conflict", "branch_moved", "already_merged"] | None = None


@skill(
    "git.merge",
    version="2",
    side_effects="external_write",
    risk="medium",
    idempotency="natural",
    timeout=300,
    retry=(3, 30),
)
def merge(inputs: MergeIn, ctx: SkillContext) -> MergeOut:
    """Merge a published branch into the target branch."""
    ...
    if conflict:
        return MergeOut(merged=False, reason="conflict")   # an expected outcome is an output
    raise SkillError("git_unavailable", "remote unavailable", retryable=True)  # a failure is an error
```

### The contract from code

| Contract part | Where it comes from |
|---|---|
| Input schema | the pydantic model of the first argument (or `inputs_schema=`) |
| Output schema | the pydantic model of the return value (or `outputs_schema=`) |
| Description | the first paragraph of the docstring (or `description=`) |
| Policy | decorator arguments |
| Default implementation | `local` with the entrypoint `module:name` of the function itself |

Schemas are JSON Schema 2020-12. Explicit `inputs_schema`/`outputs_schema` are needed when an
already published version has its own schema that the model does not reproduce.

### `@skill` decorator parameters

| Parameter | Values | Default | Meaning |
|---|---|---|---|
| `name` | string | — | skill key, for example `git.merge` |
| `version` | string | — | contract version; a contract change = a new version |
| `side_effects` | `none`, `external_read`, `external_write` | — | what the skill does in the outside world |
| `risk` | `low`, `medium`, `high` | — | risk level |
| `idempotency` | `required`, `natural`, `none` | `none` | a retry with the same key does not produce a second effect |
| `timeout` | seconds | `60` | call timeout |
| `retry` | `(maxAttempts, backoffSeconds)` | `(1, 0)` | the executor's retry policy |
| `permissions`, `preconditions`, `postconditions`, `cost_model` | — | empty | additional parts of the v1 contract |
| `implementation` | `Local(...)`, `Http(...)`, `Mcp(...)` | `Local()` | how to host (usually set at export) |

At **import** time the SDK rejects what the core would reject: unknown values of
`side_effects`/`risk`/`idempotency`, a function whose signature is not `(inputs)` or
`(inputs, ctx)`, a missing input or output schema, and `external_write` without idempotency
with `maxAttempts > 1` (retrying an external write without idempotency is a second external
effect).

### Outcome versus failure { #outcome-vs-failure }

| Situation | How to express it |
|---|---|
| An outcome anticipated by the contract ("conflict", "not found") | return an output with the corresponding field |
| An environment failure: network, limit, unavailable service | `SkillError(code, message, retryable=True)` |
| A failure a retry will not fix | `SkillError(code, message, retryable=False)` |

The error code is `^[a-z0-9][a-z0-9_.-]{0,99}$`. Any other exception from the implementation
becomes a `SkillError` with the code from the exception's `code` attribute (if valid) or
`skill_error`. A schema violation is `input_contract_violation` or
`output_contract_violation` with the list of errors in `details`.

## Call context `SkillContext`

The function can be synchronous or `async`; the second argument is the context.

| Member | Purpose |
|---|---|
| `ctx.invocation_id`, `ctx.idempotency_key` | call identifier and idempotency key — a retry with the same key must not produce a second external effect |
| `ctx.remaining()` | seconds until the contract timeout (`None` if the hosting does not know it) |
| `ctx.check_deadline()` | raises a retryable `SkillError("timeout")` if the time is up |
| `ctx.log` | a logger with the call id |
| `ctx.config(name, default=None)` | a hosting parameter (from the process environment) |
| `ctx.secret(name)` | a hosting secret: the process environment, then the node's secret file (see [below](#secrets)); found in neither — a retryable `config_missing` (another host may have it) |
| `ctx.llm` | an LLM client configured by the installation (see [below](#llm)); tokens are counted into the cost automatically |
| `ctx.artifacts` | artifact content through the core (see [below](#core-access)) |
| `ctx.knowledge` | the knowledge base through the core (see [below](#core-access)) |
| `ctx.add_cost(unit, amount)` | account for your own consumption (API requests, pages, and so on) |
| `ctx.caller` | the verified caller context (`TrustedAuthContext`) for `http`/`mcp-http` |

There is **intentionally no** Control Plane client in the context: a skill does not create or
move tasks — approval outcomes and core rules do that. A skill's access to the core is narrow:
artifact content and the knowledge base.

### Secrets { #secrets }

`ctx.secret(name)` looks up the value in two places, in order:

1. **The environment variable** `name` of the hosting process: this is how hosting outside
   a placement node (your own `http` or `mcp` service) receives secrets.
2. **The node's secret file** `$SKILL_SDK_SECRETS_DIR/<name>` (`/run/secrets/<name>` by
   default): this is how the node passes the names from `placement.secrets` of the agent
   description. The file name equals the secret name without case conversion; the file is
   looked up only if the name matches the pattern `[a-z0-9][a-z0-9-]{0,62}`.

The file reading rule is the same for all platform SDKs; the canonical implementation is the
`skill_sdk.secrets` module (`read_secret`, `read_secret_file`):

- an empty file or one of only whitespace characters means there is no secret;
- only trailing `\r` and `\n` are trimmed from a non-empty value; spaces inside and at the
  edges are part of the value;
- at most 64 KiB, UTF-8, a regular file only (a directory or FIFO is refused);
- symbolic links are resolved only inside the secrets directory (this is how Kubernetes lays
  out secrets); a link outside or `..` above the directory is refused; a path swapped during
  reading is read again, up to three attempts;
- `agent-pat` is reserved: it is the PAT of the agent itself, which the node puts alongside,
  not an installation secret.

| Error code | When | Retryable |
|---|---|---|
| `config_missing` | neither the variable nor the file exists (or the file is empty); the message names both lookup places, without values | yes |
| `secret_name_invalid` | the name is a path (`/`, `..`) or the reserved `agent-pat` | no |
| `secret_unreadable` | the process user has no permission on the file | yes |
| `secret_file_rejected` | the file is rejected by the rule; the reason is in `details.reason`: `outside_secrets_dir`, `symlink_swapped`, `not_regular_file`, `too_large`, `not_utf8`, `unreadable` | no |

### LLM { #llm }

The installation chooses the `ctx.llm` provider with the `SKILL_LLM_PROVIDER` variable:

| Provider | Variables | What it is |
|---|---|---|
| `openai` (default) | `SKILL_LLM_BASE_URL`, `SKILL_LLM_API_KEY`, `SKILL_LLM_MODELS` (comma-separated, the rotation order) | `OpenAICompatibleClient` from [platform-llm](platform-llm.md); needs the `llm` extra |
| `claude-code` | `SKILL_LLM_MODELS`, `SKILL_LLM_CLAUDE_BINARY` (`claude` by default), `SKILL_LLM_TIMEOUT_SECONDS` (300 by default); `CLAUDE_CODE_OAUTH_TOKEN` in the executor's environment | Claude on a subscription through the Claude Code CLI in non-interactive mode: no tools and no MCP servers, the prompt goes through stdin; only tokens count toward the cost |

- A provider or its variables not configured — a retryable `llm_not_configured`; no library
  or CLI — a retryable `llm_unavailable`; a subscription limit or `429` from `claude-code` —
  a retryable `llm_rate_limited`.
- **Personal data guard.** `system_prompt` and `messages` pass through it before the model
  call: a SNILS (Russian individual insurance account number), a passport number (next to
  the word `паспорт` "passport" or `серия` "series"), phone numbers, e-mail addresses, and
  full names are replaced with a marker such as `[ПДн:фио]`; the log records only how many
  of what were found. Organizations' INN and KPP, amounts, and dates are left untouched.
- For another provider, use `skill_sdk.configure_llm(factory)`.

### Core access: `ctx.artifacts` and `ctx.knowledge` { #core-access }

| Call | What it does | Core route |
|---|---|---|
| `await ctx.artifacts.read(artifact_id)` | artifact content: `ArtifactContent` with `data`, `media_type`, `sha256`, `text()` | `GET /api/v1/artifacts/{id}/content` |
| `await ctx.knowledge.preview(snapshot, workspace_id=…)` | what a source snapshot would change in the graph, and its `stateToken` | `POST /api/v1/knowledge/snapshots:preview` |
| `await ctx.knowledge.apply(snapshot, workspace_id=…, expected_state=…)` | apply a snapshot; if the state changed after the preview — `SnapshotStale` (`snapshot_stale`, not retryable: build the plan again) | `POST /api/v1/knowledge/snapshots` |
| `await ctx.knowledge.document(workspace_id=…, natural_key=…, title=…, chunks=…)` | a document in the knowledge base | `POST /api/v1/knowledge/documents` |
| `await ctx.knowledge.recall(**query)` | the memory answer to a query | `POST /api/v1/context/recall` |
| `await ctx.knowledge.query(workspace_id=…, kinds=…, where=…)` | all entities of the kinds with a filter, across all pages; more than `max_items` (10,000 by default) is a `knowledge_query_too_large` error, not truncation | `POST /api/v1/knowledge/entities:query` |

- The core address is `CONTROL_PLANE_URL` or the executor daemon's address
  `CONTROL_PLANE_SERVER`; without them — `config_missing`. The credential is the skill
  executor's account; the core client finds it.
- Permissions are checked for the skill executor on the task's workspace: for example,
  `artifacts.read` to read an artifact.
- This is the only way a skill sees memory: through the core.

## Hosting

| Protocol | How to run | What the executor sees |
|---|---|---|
| `local` | the package is installed next to the executor daemon, `CONTROL_PLANE_SKILLS_LOCAL_PACKAGES=<package>`; in a catalog package, an agent of kind `skills` (see [Package skills](../packages/skills.md#hosting)) | the executor finds the skills itself, calls `__skill_invoke__`, and gets `{outputs, cost}` |
| `http` | `skill-sdk serve http <module>` or `skill_sdk.http.create_app(...)` in your own ASGI | `POST /skills/{name}@{version}` |
| `mcp` | `skill-sdk serve mcp-stdio <module>` or `serve mcp-http` | an MCP tool named after the skill |

### HTTP protocol

```bash
skill-sdk serve http my_skills --host 0.0.0.0 --port 8080
```

```http
POST /skills/git.merge@2
Authorization: Bearer <IAM access token for the skill audience>
Content-Type: application/json

{"invocationId": "…", "idempotencyKey": "…", "inputs": {"repository": "…", "branch": "b", "commit": "abc1234", "target": "main"}}
```

| Response | Meaning |
|---|---|
| `200` | the body is the `outputs` themselves, without an envelope; the cost is in the `X-Skill-Cost` header |
| `422` | a non-retryable `SkillError`: `{"error": {"code", "message", "retryable", "details"}}` |
| `503` | a retryable `SkillError` in the same envelope |
| `401` | the token failed verification |
| `404` | no such skill on this hosting |
| `500` | implementation failure |

`GET /skills` lists the skills of the hosting.

### MCP

A skill is a tool of the MCP server; the cost is in `_meta["skill/cost"]`, an error is a
result with `isError` and a single text block `{"error": {…}}` of the same form.

### Hosting authentication

`http` and `mcp-http` verify an IAM token for the skill audience through
[platform-auth-sdk](platform-auth-sdk.md):

| Variable | Meaning |
|---|---|
| `SKILL_SDK_IAM_ISSUER` | IAM issuer (`${TAIMEN_PUBLIC_URL}/iam`) |
| `SKILL_SDK_AUDIENCE` | skill audience (the same as in the implementation contract) |
| `SKILL_SDK_JWKS_URL` | IAM JWKS |

Without these variables the hosting **does not start**. The `--allow-anonymous` flag
(`allow_anonymous=True`) turns verification off — for local development only. An unavailable
JWKS gives `503`, an invalid token gives `401`.

## Catalog package

Skills reach Control Plane through catalog packages (TAI-ADR-0044, see
[Package skills](../packages/skills.md)). The skill YAML is generated from code and never
edited by hand; `package-sdk test` checks it against the code at the contracts level (see
[Package tests](../packages/testing.md)):


```bash
# write packages/acme/skills/*.yaml
skill-sdk export --package ../packages/acme acme_skills

# CI: check that code and YAML match
skill-sdk export --package ../packages/acme --check acme_skills

# http hosting: implementation in the contract, address from an installation environment variable
skill-sdk export --package ../packages/acme --protocol http \
    --endpoint '${ACME_SKILLS_URL}' --audience acme-skills acme_skills
```

| `export` parameter | Meaning |
|---|---|
| `--package` | package directory (required) |
| `--protocol` | `local`, `http`, or `mcp`; defaults to the one declared in code |
| `--endpoint` | `http`: service base, accepts `${VAR}`; `mcp`: URL or `stdio:<name>` |
| `--audience` | the IAM audience whose token the executor carries |
| `--check` | do not write, compare with the files instead (for CI) |

A fragment of a generated file:

```yaml
# Generated by skill-sdk from code — edit the code and regenerate (TAI-ADR-0045).
kind: Skill
key: adr.conformance_check
spec:
  version: '1'
  description: Check Accepted ADRs against the code with probes (no LLM)
  sideEffects: none
  riskLevel: low
  contract:
    inputs:
      $schema: https://json-schema.org/draft/2020-12/schema
      type: object
      required: [repository]
      …
```

A version contract in the core is immutable: a change of schemas or policy is a new
`version` in the decorator, a new file, and a new Skill object in the catalog.

## Other CLI commands

| Command | What it does |
|---|---|
| `skill-sdk list <modules…>` | skills in the modules |
| `skill-sdk contract <module:name>` | the v1 contract of one skill (JSON) |
| `skill-sdk invoke <module:name> --input '<json>'` | call locally with contract checks (`--input @file` — from a file) |
| `skill-sdk serve {http,mcp-http,mcp-stdio} <modules…>` | hosting |

Targets are `module:name`, a module, or a package (with all submodules). Two different
declarations of the same `name@version` are an error.

## Skill tests

```python
from skill_sdk.testing import FakeLlm, check_contract, invoke


def test_merge_contract():
    check_contract(merge)   # core validators, if control-plane is installed alongside


def test_conflict_is_an_outcome():
    result = invoke(merge, {"repository": "…", "branch": "b", "commit": "abc1234", "target": "main"},
                    env={"GIT_REMOTE": "…"}, idempotency_key="k-1")
    assert result.outputs["reason"] == "conflict"


def test_summary_uses_the_model():
    llm = FakeLlm([{"summary": "Коротко"}])
    result = invoke(summarize, {"text": "…"}, llm=llm)
    assert result.outputs == {"summary": "Коротко"}
    assert len(llm.calls) == 1
```

| Tool | What it does |
|---|---|
| `invoke(skill, inputs, *, env=None, idempotency_key=None, llm=None)` | a call with input and output checked against the contract, as in hosting; `SkillError` propagates; `ainvoke` is the asynchronous variant |
| `check_contract(skill)` | runs the contract through the same validators the core uses, if the `control-plane` package is available in the environment |
| `FakeLlm(answers)` | a fake `ctx.llm`: a single answer, a list in call order, or a function of the call; a `chat_json` answer is validated by the response model; calls are recorded in `llm.calls` after the personal data guard; an extra call is an `AssertionError` |
| `FakeCore` + `configure_core(lambda ctx: fake)` | an in-memory core for `ctx.artifacts` (`fake.artifacts.put(id, data)`) and `ctx.knowledge` (snapshots with `stateToken` and `SnapshotStale`, the `recall_answer` response, `query` over applied snapshots) |

`env` sets the hosting environment for the duration of the call: `ctx.config` parameters and
`ctx.secret` secrets. The `llm` fake lives in a context variable: the asyncio tasks of this
call see it, and the global configuration does not change.

## Installation

| Dependency | What it provides |
|---|---|
| `skill-sdk` | contract, `local`, tests, export |
| `skill-sdk[http]` | + ASGI hosting and token verification |
| `skill-sdk[mcp]` | + MCP server |
| `skill-sdk[llm]` | + `ctx.llm` with the `openai` provider |
| `skill-sdk[all]` | everything at once |

`skill-sdk`, `platform-auth-sdk`, and `platform-llm` are connected as neighbouring folders
(see [Connecting](index.md#connect)), not from the public package index. A package's
integration code gets `skill-sdk` from the executor's base image (see
[Integrations](../packages/integrations.md#images)).

## See also

- [SDK and integrations](index.md)
- [Package skills](../packages/skills.md)
- [Package tests](../packages/testing.md)
- [Catalog packages](../control-plane/catalog-packages.md)
- [Executor adapters](../runner/adapters.md)
- [platform-llm](platform-llm.md)
- [platform-auth-sdk](platform-auth-sdk.md)
