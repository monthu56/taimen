
# Event subscriptions

How a service or integration subscribes to the Control Plane event log: filters
by type and workspace, the workspace permission, cursors, the WebSocket as a
wake-up signal, event data versions, and the catalog. The second part covers
the Python consumer SDK `control_plane_client.events`, which takes care of
cursor storage, deduplication, and retries. This page is for developers of
consumers: notification services, bridges, webhook relays. The event log model
and the full list of types are in [Events](events.md).

## A subscription is a read filter

The core has no stateful server-side subscriptions. A consumer reads the same
event log `GET /api/v1/events` (or `WS /api/v1/events/ws`) with filters and
stores the cursor itself. A filter narrows the output but changes neither the
order nor the meaning of the cursor: a filtered reader continues from
`nextCursor` just like a reader of the whole event log. Rationale: CP-ADR-0068.

```bash
# All approval events and failed verifications in a workspace subtree
curl -s "$CP/events?types=approval.,task.verification_failed&workspaceId=<workspace-id>&limit=200" \
  -H "Authorization: Bearer $TOKEN"

# The same, continuing from a saved cursor
curl -s "$CP/events?types=approval.&types=task.verification_failed&workspaceId=<workspace-id>&cursor=ec1_…" \
  -H "Authorization: Bearer $TOKEN"
```

| Parameter | Meaning |
|---|---|
| `types` | Type prefixes. `approval.` — all approval events, `task.verified` — this type (and everything that starts with this string). A repeatable parameter and/or a comma-separated list, up to 20 prefixes. Format `^[a-z][a-z0-9_]*(\.[a-z0-9_]*)*$` |
| `workspaceId` | Events of this workspace and all its descendants. The subtree is computed at read time |
| `cursor`, `limit`, `tail`, `entityType`, `entityId` | As in a regular read, see [Events](events.md); combine with filters |

| Error | HTTP | When |
|---|---|---|
| `invalid_event_type_filter` | 422 | A prefix is not in the format, or there are more than 20 |
| `not_found` | 404 | The filter workspace does not exist |
| `permission_denied` | 403 | No `events.read` on the workspace (or on the tenant without `workspaceId`) |
| `invalid_request` | 400 | Unknown query parameter |

### Workspace permission

- **With `workspaceId`**, the `events.read` permission is checked on the
  `workspace:<id>` resource. In `policy` authorization mode, grants on
  ancestors are taken into account. An approvals consumer for one department
  does not need a permission on the whole tenant.
- **Without `workspaceId`** — the `events.read` permission on the tenant, as
  before.
- Tenant-level events (principals, keys, bootstrap) are not visible under a
  workspace filter.

### Event workspace

Every event envelope has a `workspaceId`. The core fills it in based on the
event's entity:

- the entity's own workspace — for `task`, `approval`, `artifact`, `goal`,
  `rule`, `role`, `project`, and `workspace` itself;
- otherwise the workspace of the task the entity belongs to — for `run`,
  `claim`, `skill_invocation`, and for an approval or artifact without its own
  workspace;
- other events are tenant-level (`workspaceId: null`).

A task's approval lives in the task's workspace: `workspaceId` in the
envelope, in the `approval.requested` payload, and in the approval projection
is the same value, and the holders of the role in this workspace are exactly
those who can decide.

!!! note "Events from before filters existed"
    The event log is append-only. Events written before the core started
    filling in `workspaceId` have an empty field, and a workspace filter does
    not see them.

### Cursor across skipped events

A page that reached the end of the event log carries `nextCursor` across the
events dropped by the filter, up to a position stable at the time of the
request. A reader of a rare type therefore does not rescan the same tail of the
event log on every poll. The cursor stays opaque: store the last one you
received — the `cursor` of the processed event or the page's `nextCursor` —
and pass it back.

The output order, the cursor guarantees, and the cursor errors
(`invalid_cursor`, `cursor_below_journal_floor`) are the same as for an
unfiltered read — see [Reliable cursor](events.md).

## WebSocket as an alarm clock

```text
WS /api/v1/events/ws?after=<cursor>&types=approval.&workspaceId=<workspace-id>
```

The WebSocket accepts the same `types` and `workspaceId` filters. The server
sends events after `after` and then as they commit. But a reliable consumer
**does not process frames**: any frame only wakes the loop that reads
`GET /events` from the saved cursor. There is one source of truth; a frame lost
together with the socket costs a delay, not an event.

Errors are delivered as a close code after the connection is established:

| Code | Cause | Is retrying useful |
|---|---|---|
| `4401` | Missing or invalid credentials | After refreshing the token |
| `4403` | No `events.read` permission (on the filter workspace or the tenant) | No |
| `4404` | The filter workspace does not exist | No |
| `4400` | Malformed or unsupported cursor, invalid filter | No |
| `4503` | No authorization decision received (PDP unavailable) | Yes |
| `1011` | Internal server error | Yes |

A single-decision token from a channel (scope `control-plane:decide`) is not
allowed on the WebSocket.

## Data versions and the catalog

### `schemaVersion`

The event envelope carries `schemaVersion` — the version of the `payload`
schema for this type (`1` for older events). The evolution rule:

- a new version **only adds** fields: a consumer of version N reads N+1
  without changes and ignores unfamiliar fields;
- a field that changes meaning or disappears is a **new event type**, not a
  new version;
- old versions stay in the catalog as long as the event log may hold events
  under them.

The core sets the current version of the type on write and refuses to write a
type that is not in the catalog. Every event in the core's integration tests
is validated against the JSON Schema of its (type, version) pair.

### Event catalog

The catalog is generated from the core's code (`make event-catalog` in the
`control-plane` repository) into two files: `docs/events/catalog.md` — a table
of types, the envelope, and the fields of each version, and
`docs/events/catalog.json` — JSON Schema 2020-12 for all versions for
consumer-side validation. The catalog is neutral: it contains only core
entities.

Example — the `approval.requested` payload of version 2 (v2 fields are added
to v1):

| Field | Version | Meaning |
|---|---|---|
| `taskId`, `artifactId` | 1 | The subject of the decision |
| `requiredRoleId` | 1 | Set if any holder of the role decides |
| `assignedPrincipalId` | 1 | Set if a single principal decides |
| `gate` | 1 | A gate holds the claim and task completion until the decision |
| `workspaceId` | 2 | The approval's workspace |
| `taskPublicId`, `taskTitle` | 2 | What is being decided — without re-reading the task |
| `requestedBy` | 2 | Who requested it |
| `comment` | 2 | The request comment |

Version 2 of `approval.approved` and `approval.rejected` adds `decisionBy`,
`comment` (the decision comment or `null`), and `channel` — the channel the
decision came through (`telegram`), `null` for a direct API call.
`approval.cancelled` v2 adds `cancelledBy`. The `comment` text in the event
goes through redaction of secret-like material (a match is replaced with
`[redacted]`) and is truncated to 1000 characters; the full text stays in the
approval itself.

### Role holders

To address a decision by role, a consumer needs the list of those entitled to
decide. The core returns it by the same rule it uses to check the right to
decide:

```bash
curl -s "$CP/roles/<role-id>/principals?workspaceId=<workspace-id>" \
  -H "Authorization: Bearer $TOKEN"
```

It returns the principals to whom the role is assigned at the tenant level or
on this workspace or its ancestor; without `workspaceId` — only tenant-level
assignments. An item is `{id, kind, displayName, status}`, with pagination as
in other lists. The principal status is not filtered: the addressing party
decides. Permission — `org.read` or `principals.read`.

## Consumer SDK: `control_plane_client.events` {#sdk}

The SDK is part of the `control-plane-client` package (see
[Service clients](../sdk/clients.md)). Rationale: CP-ADR-0069. The client core
stays on `httpx`; the consumer dependencies are extras:

```bash
uv add 'control-plane-client[events]'   # websockets + sqlalchemy[asyncio]
```

| Extra | What it provides |
|---|---|
| `[ws]` | Wake-up over WebSocket; without it the consumer only polls |
| `[sqlalchemy]` | Cursor store in SQL (`control_plane_client.events.sqlalchemy`) |
| `[events]` | Both |

The consumer installs the database driver (`psycopg`, `asyncpg`, `aiosqlite`)
itself.

### Minimal consumer

```python
from control_plane_client import ControlPlaneClient
from control_plane_client.events import Event, EventConsumer
from control_plane_client.events.sqlalchemy import SqlAlchemyCursorStore
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine("postgresql+psycopg://…")
store = SqlAlchemyCursorStore(engine)


async def handler(event: Event) -> None:
    # An exception: the event arrives again; a return: the event is processed.
    await notify(event["payload"])


async def main() -> None:
    await store.create_tables()  # or the tables in the consumer's migration
    async with ControlPlaneClient(url, credential) as client:
        consumer = EventConsumer(
            client,
            ["approval.", "task.verification_failed"],
            workspace_id,          # None — the whole tenant
            store,
            handler,
            name="notifications",
            start="latest",
        )
        await consumer.run()       # until consumer.stop() or cancellation
```

### `EventConsumer` parameters

`EventConsumer(client, types, workspace_id, cursor_store, handler, *, name, …)`:

| Parameter | Default | Meaning |
|---|---|---|
| `types` | — | Type prefixes; empty — all types |
| `workspace_id` | — | Workspace subtree; `None` — the whole tenant (requires `events.read` on the tenant) |
| `cursor_store` | — | Where the position and processed-event marks are stored |
| `handler` | — | `async (event) -> None`; the event is as in `GET /events` |
| `name` | required | The cursor key in the store: one name, one position |
| `start` | `"earliest"` | Only when there is no cursor yet: `earliest` — the whole available event log, `latest` — after the last matching event (the cursor is saved immediately) |
| `poll_interval` | `30.0` | Polling period, seconds; the WebSocket wakes earlier |
| `page_size` | `200` | `GET /events` page size |
| `websocket` | `True` | Keep a WebSocket for wake-ups |
| `retry_initial`, `retry_max` | `1.0`, `60.0` | Pause before retrying a failed page: doubles from the first to the second |

Methods: `run()` — the loop until `stop()` or cancellation; `stop()` — finish
the event in hand and exit; `wake()` — read now without waiting for the poll;
`drain()` — read everything available now and return the number of processed
events (for scheduled jobs and tests).

### Guarantees

- **Order** — the event log order; the handler is called one event at a time.
- **No loss.** The cursor moves only after the event is processed. A failed
  handler (`HandlerError`), a network failure, or a `5xx` — the page is read
  again from the saved cursor after a pause. Only the handler can drop an
  event — by returning without an exception.
- **No duplicates.** An event is processed inside a unit of work of the store:
  the `event.id` mark and the event's cursor are written together. A
  redelivered event is skipped.
- **Subscription rejection** — `401`, `403`, `404`, `422` when reading a page —
  ends `run()` with an exception: a retry would not change it.
- **WebSocket.** Frames only wake the loop. After a `4401` close the credential
  is refreshed; after any reconnect the loop reads once out of turn. Without
  the `websockets` package the consumer polls once every `poll_interval`.

!!! warning "An event the handler always fails on"
    Such an event stops the consumer on itself — with a growing pause and a
    warning in the log. This is a deliberate "do not lose" choice. If an event
    cannot be processed in principle (payload outside the schema), the handler
    must log it and return without an exception.

### Cursor stores

The `CursorStore` protocol:

| Method | Meaning |
|---|---|
| `load(consumer)` | The saved cursor or `None` |
| `handle(consumer, event_id, cursor)` | An async context manager: enters with `False` if the event is already processed; on a clean exit writes the mark and cursor together; an exit by exception writes nothing |
| `advance(consumer, cursor)` | Moves the cursor to the page's `nextCursor` (across filtered-out events) |

- **`MemoryCursorStore`** — in process memory: tests and consumers that can
  start over.
- **`SqlAlchemyCursorStore(engine, *, metadata=None, prefix="",
  dedup_retention=7 days, prune_interval=600)`** — tables
  `<prefix>event_cursors` (consumer → cursor) and `<prefix>handled_events`
  (consumer × `event_id`, `handled_at`).
    - An event is one transaction. Rows the handler writes through
      `SqlAlchemyCursorStore.session()` are committed together with the mark
      and cursor or rolled back together with them. For effects in the
      consumer's database this is "exactly once"; for external effects (a
      message to a messenger) it is "at least once" — pass `event.id` to the
      recipient as the idempotency key.
    - The cursor row is locked `FOR UPDATE` for the duration of the event: two
      processes with the same `name` will not both process an event. They can
      still duplicate external effects — run one process per name.
    - Marks older than `dedup_retention` are deleted as the cursor moves, no
      more often than once every `prune_interval` seconds: redelivery happens
      near the cursor, not days behind.
    - The consumer's migration creates the schema: pass your own `MetaData`
      (Alembic `target_metadata`) or declare the tables with
      `cursor_tables(metadata, prefix=…)`; without migrations —
      `await store.create_tables()`.

### Export to CloudEvents

`to_cloudevent(event, *, source=None)` turns an event log event into
CloudEvents 1.0 (structured JSON) — for relaying to a webhook or a bus. The
event log does not change its format: this is an export function.

| CloudEvents | From the event |
|---|---|
| `specversion` | `1.0` |
| `id`, `type` | `id`, `type` |
| `time` | `occurredAt` |
| `subject` | `<entityType>/<entityId>` |
| `source` | the `source` argument (an installation URI, for example `https://platform.example.com/tenants/<tenant-id>`); `/control-plane/tenants/<tenantId>` by default |
| `datacontenttype` | `application/json` |
| `data` | `payload` |
| extensions | `tenantid`, `workspaceid`, `entitytype`, `entityid`, `schemaversion`, `actorid`, `correlationid`, `causationid` — empty ones are omitted |

```python
from control_plane_client.events import to_cloudevent

async def handler(event):
    await relay.post(json=to_cloudevent(event, source="https://platform.example.com/tenants/<tenant-id>"),
                     headers={"Idempotency-Key": event["id"]})
```

The `data` schema is the `schemaversion` version of the type in the event
catalog.

### Simple reading without a store

`ControlPlaneClient.list_events(cursor=…, types=…, workspace_id=…, tail=…)`
reads one page with filters; `follow_events(cursor=…)` is an endless poll
without saving the position and without deduplication. For a reliable
consumer, use `EventConsumer`.

## See also

- [Events](events.md) — the event model, cursor, WebSocket, the full type
  catalog, event log retention.
- [Notifications](../notifications/index.md) — the notification service built
  on this SDK.
- [Approvals](approvals.md) — decision events.
- [Authorization and permissions](authorization.md) — `events.read` and the
  `authorize` modes.
- [Service clients](../sdk/clients.md) — `control-plane-client`.
