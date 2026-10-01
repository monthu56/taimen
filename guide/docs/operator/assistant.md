
# Assistant

The assistant is a person's own conversation partner in the [console](console.md): a panel
that opens from any screen, sees what the person is looking at, and answers from core data.
This page is for people who work with it and for the administrator who enables it.
Rationale: TAI-ADR-0058 (revision 2).

## What it is

The assistant panel is one more surface of the person's conversation, not a separate console
chat. A person has a single conversation; the assistant engine keeps it, while the console
only shows it and passes messages along. The console neither stores the conversation nor
writes it to its log.
The assistant engine ships separately and is not part of the open-source distribution.
Without it the panel still opens but reports that the conversation could not be loaded; the
rest of the console works as usual.

The assistant reads tasks, approvals, runs, processes, and company memory with Control Plane
tools and answers from them, not from the conversation's memory. Its permissions are the
person's own: the assistant cannot do more than the person can.

## Opening the panel

| How | What happens |
|---|---|
| The "Assistant" button in the header | The panel opens to the right of the screen; the screen stays in place |
| ⌘J / Ctrl+J | The same from the keyboard; pressing it again closes the panel |
| An address with `?assistant=open` | The console opens with the panel already open; the parameter is removed from the address, so reloading or going "Back" does not reopen the panel |
| "Discuss" on a "Waiting for you" item in the pulse | The panel opens with that item as context; the screen does not change |

Escape closes the panel. A message draft is not lost when the panel closes. The live
conversation stream is open while the panel is open; when the panel is opened again, the
stream resumes where it stopped.

## Screen context

With every message the assistant receives the screen context, so a question does not need to
name the object: "why is this stuck?" on a work screen refers to that work.

Above the input field there is a "Context" chip with the screen's label. It can be removed:
the context is then not sent until the person clicks "Send it again" or moves to another
screen. When the screen changes, the context follows on its own.

The console server assembles the context on behalf of the signed-in person, from the same
data the screen shows. The browser sends only the screen address; anything else it might send
as context is discarded.

| Screen | What the assistant receives |
|---|---|
| Work | a condensed provenance chain: where the work came from, runs, verification |
| Process instance | open steps, time on the step, the latest decision log entries |
| Run | the outcome, the latest actions, and the last checkpoint |
| Rule, agent, artifact | label and status |
| Overview screens | only the screen kind and address |

The context carries only identifiers, statuses, short labels, and times. It contains no run
input or output, no process data, and no artifact content or location; values that look like
tokens or passwords are scrubbed. Of the address parameters, only the tab, the status and kind
filters, the workspace, and the revision remain; search text is not sent. The context is at
most 8 KB: lists are shortened first, and as a last resort only the screen kind and address
remain. If the data is not assembled within 3 seconds, the message goes out with the screen
kind and address and nothing else.

## Conversation

- **History.** The panel shows the latest messages of the conversation; "Show earlier" loads
  older ones. Your messages sent from outside the console are marked with where they came
  from.
- **Assistant turn.** While the assistant is replying, the panel shows "The assistant is
  replying…" and a "Read and done: N" summary: which tools it called and with what result.
- **Queue.** A message sent while the assistant is replying is queued and goes out when the
  assistant finishes its current turn.
- **Retry.** A message that failed to send can be retried: the retry reuses the same request
  number and does not duplicate the message.

### Confirmations

The assistant does not perform an action that changes state in the core (create a task,
accept a result, decide an approval, invoke a skill) without confirmation. The panel shows a
"The assistant asks for confirmation" card with the action, how long it waits, and the
"Allow" and "Reject" buttons.
A request that gets no answer expires; an interrupted turn withdraws its requests.

## "Waiting for you" in the pulse

The personal part of the [pulse](console.md#pulse) is the "Waiting for you" list: decisions
addressed to the person or their role, results awaiting review, upcoming and missed
deadlines, blocked work, and assignments that keep failing for their executor. The core
computes the list (`GET /api/v1/me/attention`); every item carries a reason.

Each item has buttons: "Discuss" (opens the assistant with the item as context) and "No need
to show", which is feedback to the core; an approval can be decided right in the list. Hidden
items can be shown and brought back.

## Privacy

Only its owner sees the conversation. The console stores neither messages nor replies: the
console server's access log holds only the request number, without text. The organization
sees core objects and the action log (tasks, approvals, artifacts, events), but not the
conversation. Each person talks only to their own assistant: the console server takes the
principal from the session, not from the request.


## If something goes wrong

| What the panel shows | Cause and what to do |
|---|---|
| "The assistant is waking up…" | The assistant container is starting; the console keeps working meanwhile. A cold start takes seconds |
| "The assistant did not wake up in time." | The engine did not start within the allotted time: click "Retry"; if it repeats, check the engine's log |
| "Could not load the conversation: …" | The engine is unavailable or refused; the error code is in the message |
| "The assistant stream is not open: …" | The engine refused the stream (for example, missing permissions); the stream does not reconnect by itself: after fixing the cause, click "Retry" |
| "Too many tabs with the assistant are open" | The limit of simultaneous streams per person is exceeded: close the panel in extra tabs |
| "The screen context is too large" | Remove the context chip and retry |
| "The session has ended — taking you to sign in." | The console session expired; after sign-in the console returns to the same screen |

## See also

- [Console](console.md)
- [Approvals](../control-plane/approvals.md)
- [Operator guide](index.md)
