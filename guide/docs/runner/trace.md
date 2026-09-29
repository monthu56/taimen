
# Run trace

What an autonomous executor reports to Control Plane about the progress of its work
(CP-ADR-0051): a bounded, redacted transcript as a `transcript` artifact and one run action
per tool call in real time. The article is for operators who read runs and for engineers who
decide what may be published from a specific site.

## What is published and what is not

| Data | Where | Condition |
|---|---|---|
| Final agent summary | `report` artifact (`content.summary`, up to 60000 characters, paths stripped) | always |
| Turn counters (model, number of turns, duration, cost, tokens) | metadata of the `report` artifact | always |
| Agent messages, tool calls with input and result, final answer | `transcript` artifact (`agent-transcript/1`) | `CONTROL_PLANE_TRACE_TRANSCRIPT` |
| Tool results inside the transcript | same place | `CONTROL_PLANE_TRACE_TOOL_RESULTS` |
| One action per tool call | run actions `tool.<name>` | `CONTROL_PLANE_TRACE_ACTIONS` |
| Action for the whole turn | `claude-code.turn` / `codex.turn` | always |
| Prompt | — | **never** |
| Hidden reasoning (`thinking`, reasoning summaries) | — | **never**; only the `hiddenReasoningBlocks` counter |
| Raw CLI stream | local log on the runner host | `CONTROL_PLANE_CLAUDE_LOGS` / `CONTROL_PLANE_CODEX_LOGS` |

The trace is published by the `claude-code` and `codex` adapters. The OpenCode harness and
the `echo` adapter do not publish a transcript.

## Flags

| Variable | Default | `0` / `false` / `no` / `off` means |
|---|---|---|
| `CONTROL_PLANE_TRACE_TRANSCRIPT` | `1` | do not publish the `transcript` artifact |
| `CONTROL_PLANE_TRACE_ACTIONS` | `1` | do not write `tool.*` run actions |
| `CONTROL_PLANE_TRACE_TOOL_RESULTS` | `1` | keep only the size and the error flag of tool results in the transcript |

!!! tip "A site where tool output must not leave the host"
    Turn off only `CONTROL_PLANE_TRACE_TOOL_RESULTS`. The agent conversation, the list of
    calls, and the audit in run actions remain, while file contents and command output do not.

## The `transcript` artifact

One JSON document with the `agent-transcript/1` schema, no larger than **512 KiB**.

```json
{
  "schema": "agent-transcript/1",
  "harnessType": "claude-code",
  "sessionId": "5b0e…",
  "model": "<model-id>",
  "tools": ["Bash", "Read", "Edit", "mcp__control-plane__cp_get_run_context"],
  "entries": [
    {"seq": 1, "at": "2026-01-15T10:00:01.120Z", "kind": "assistant", "text": "Looking at the module structure."},
    {"seq": 2, "at": "…", "kind": "tool_call", "call": 1, "callId": "toolu_…", "tool": "Read",
     "input": "{\n \"file_path\": \"<path>/service.py\"\n}"},
    {"seq": 3, "at": "…", "kind": "tool_result", "call": 1, "callId": "toolu_…", "isError": false,
     "output": "…"},
    {"seq": 4, "at": "…", "kind": "tool_call", "call": 2, "tool": "Bash",
     "input": "{\n \"command\": \"uv run pytest -q\"\n}"},
    {"seq": 5, "at": "…", "kind": "tool_result", "call": 2, "isError": false,
     "withheld": true, "outputChars": 1830}
  ],
  "final": {"text": "Done: …", "truncated": false},
  "usage": {"inputTokens": 120345, "outputTokens": 8812, "costUsd": 0.61, "durationMs": 412000, "turns": 28},
  "stats": {
    "assistantMessages": 14, "userMessages": 0, "toolCalls": 31, "toolErrors": 2,
    "hiddenReasoningBlocks": 9, "truncatedEntries": 1, "droppedEntries": 0
  },
  "truncated": true
}
```

### Entry kinds

| `kind` | Fields | Source |
|---|---|---|
| `assistant` | `text` | text blocks of the agent response |
| `user` | `text` | text input during the turn (not the prompt) |
| `tool_call` | `call` (sequence number), `callId`, `tool`, `input` | tool call |
| `tool_result` | `call`, `callId`, `isError`, `output` **or** `withheld: true` + `outputChars` | tool result |

Every entry has `seq` and `at`; an entry cut by a limit is marked `truncated: true`.

### Limits

| What | Limit |
|---|---|
| Whole document | 512 KiB; entries over budget are not stored but counted in `droppedEntries` |
| Message text | 20000 characters |
| Tool input | 6000 characters |
| Tool result | 6000 characters |
| Final answer | 60000 characters, in its own slot outside the entry budget |

Truncated text ends with the marker `… [truncated N chars]`.

### Redaction

Every string passes two redactions before it is stored:

- **host paths** are replaced with `<path>`; deep paths (four segments or more) keep the file
  name — `<path>/README.md` tells the reader which file the agent touched without revealing
  the host layout;
- **credentials** are replaced with `<redacted>`: prefixes `cp_`, `sk-`, `ghp_`, `github_pat_`,
  `xox?-`, JWTs of the form `eyJ….….…`, pairs `token=…`, `password: …`, `api_key=…`,
  `authorization: …`, `client_secret=…` and similar; PEM private keys become
  `<redacted private key>`.

After assembly, the whole document is checked by the same portability guard as all
artifacts. If something still fails, the transcript is **not published as text**: instead, a
document with `withheld: true`, `reason: "unsafe_payload"`, counters, and usage is sent — the
run does not fail because of this.

### Metadata

The artifact metadata is what a reader wants to know before opening the document:

```json
{
  "schema": "agent-transcript/1",
  "harnessType": "claude-code",
  "entries": 57,
  "toolCalls": 31,
  "toolErrors": 2,
  "assistantMessages": 14,
  "truncated": true,
  "model": "<model-id>",
  "sessionId": "5b0e…",
  "inputTokens": 120345,
  "outputTokens": 8812,
  "costUsd": 0.61,
  "claudeSessionId": "5b0e…",
  "turns": 28
}
```

## Run actions `tool.*`

While a turn is in progress, the adapter writes a run action for every `tool_use` and closes
it on `tool_result`. This way clients see the run's progress live without waiting for the
transcript.

```http
POST /api/v1/runs/<run-id>/actions
{
  "action": "tool.Bash",
  "status": "started",
  "externalReference": "claude-code:session/<session-id>#call/2",
  "metadata": {"tool": "Bash", "call": 2, "summary": "uv run pytest -q"}
}
```

```http
POST /api/v1/runs/<run-id>/actions/<action-id>:finish
{"status": "completed"}        // or "failed" if the result has is_error
```

| Field | Rule |
|---|---|
| `action` | `tool.<name>`; only `[A-Za-z0-9_.:/-]` is kept from the name, everything else becomes `_`; up to 200 characters |
| `metadata.summary` | one line up to 160 characters: the first meaningful input field (`command`, `cmd`, `file_path`, `path`, `pattern`, `query`, `url`, `prompt`, `skill`), redacted |
| `externalReference` | pointer into the transcript: `<adapter>:session/<id>#call/<n>` |

Run actions carry **references, not payload**: inputs and outputs live only in the artifact.

Special cases:

- a call whose result never arrived (crash, timeout) is closed with status `failed` when the
  turn ends;
- if the run hits its actions budget (`budget_exceeded`), the adapter stops writing actions
  but keeps working; the transcript still contains everything;
- a failure to write an action is logged to the runner log and swallowed — bookkeeping must
  not turn completed work into a failure.

Besides `tool.*`, every turn is wrapped in a `claude-code.turn` / `codex.turn` action with a
reference to the agent session.

## Run checkpoints

The trace is complemented by checkpoints written by the adapter and the daemon:

| `kind` | Who | Data |
|---|---|---|
| `execution.workspace` | daemon | copy key, branch, base commit, neighbour revisions; after the commit — `head`, `published` |
| `claude-code.session` | adapter | `claudeSessionId`, `resumed`, `phase` (`started` / `finished` / `failed`), `subtype`, `turns` |
| `codex.session` | adapter | `codexSessionId`, `phase` |
| `opencode.session` | OpenCode harness | `openCodeSessionId`, `lastMessageId` |

## Where to read it

=== "MCP"

    ```text
    cp_get_run(run_id)              → the run itself
    cp_get_run_context(run_id)      → checkpoints, artifacts, approvals
    cp_list_artifacts(task_id)      → report, transcript, commit
    ```

=== "API"

    ```bash
    curl -sS "$CP/api/v1/runs/<run-id>/actions" -H "Authorization: Bearer $TOKEN"
    curl -sS "$CP/api/v1/runs/<run-id>/checkpoints" -H "Authorization: Bearer $TOKEN"
    curl -sS "$CP/api/v1/artifacts?taskId=<task-id>" -H "Authorization: Bearer $TOKEN"
    ```

## Local log on the host

The raw CLI stream (Claude Code stream-json or Codex JSON events) and stderr are written to
`<runtime>/sessions/<publicId>-<session>.jsonl` with permissions `0600`. The cap is 32 MB per
file over its whole lifetime, including resumed turns; lines beyond the cap are not written.
This is the only place where the prompt and the full output remain — access to it is limited
by access to the runner host. Turn it off with `CONTROL_PLANE_CLAUDE_LOGS=0` /
`CONTROL_PLANE_CODEX_LOGS=0`.

## See also

- [Artifacts and comments](../control-plane/artifacts.md)
- [Execution — claims and runs](../control-plane/execution.md)
- [Executor adapters](adapters.md)
- [Security model](../overview/security-model.md)
