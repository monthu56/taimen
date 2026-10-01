
# platform-llm

`platform-llm` (package `platform_llm`) is the platform's shared LLM client: one
`StructuredChatClient` contract for all consumers and an implementation for any
OpenAI-compatible API. The client returns a response validated against a pydantic model,
retries failures on its own, and switches between models. For developers of skills,
executors, and package services.

## Why a separate library

Every LLM consumer needs the same things: structured output against a schema, retries on
`429`/`5xx`, a retry when the response does not match the schema, fallback models, token
accounting. `platform-llm` keeps this in one place (TAI-ADR-0030), and consumers see only
the protocol:

| Consumer | How it gets the client |
|---|---|
| skills | `ctx.llm` in [skill-sdk](skill-sdk.md) (`SKILL_LLM_*`) |
| vertical package executors | create an `OpenAICompatibleClient` from their configuration |
| demos and services | path dependency `../platform-llm` |

Dependencies are only `httpx` and `pydantic`; Python 3.12+.

## Contract

```python
class StructuredChatClient(Protocol):
    async def chat_json(self, *, system_prompt: str, messages: list[dict[str, str]],
                        response_model: type[ModelT], schema_name: str,
                        temperature: float = 0.0) -> LlmResult[ModelT]: ...

    async def chat_json_object(self, *, system_prompt: str, messages: list[dict[str, str]],
                               temperature: float = 0.0,
                               max_tokens: int | None = None) -> JsonResult: ...

    async def aclose(self) -> None: ...
```

| Method | Response format | Result |
|---|---|---|
| `chat_json` | `response_format = json_schema` with the schema `response_model.model_json_schema()` and `strict: true` | `LlmResult[ModelT]`: `data` (model instance), `model`, `usage`, `cost_usd` |
| `chat_json_object` | `response_format = json_object` without a schema | `JsonResult`: `data` (dictionary), `model`, `usage`, `cost_usd` |

`usage` is `LlmUsage(prompt_tokens, completion_tokens, total_tokens)` from the provider's
response; `cost_usd` is the `cost_usd` field of the response if the provider returns it,
otherwise `None`.

The response schema is always taken from the pydantic model, never written by hand:
otherwise a mismatch between the model and the schema would show up only in production.

## OpenAICompatibleClient

```python
from pydantic import BaseModel
from platform_llm import LlmError, OpenAICompatibleClient


class Verdict(BaseModel):
    decision: str
    reasons: list[str]


llm = OpenAICompatibleClient(
    base_url="https://llm.example.com/v1",
    api_key=api_key,
    models=("primary-model", "fallback-model"),
    timeout=60.0,
)
try:
    result = await llm.chat_json(
        system_prompt="You check an application against the rules. Answer strictly by the schema.",
        messages=[{"role": "user", "content": untrusted_document_text}],
        response_model=Verdict,
        schema_name="verdict",
    )
    print(result.data.decision, result.model, result.usage.total_tokens)
except LlmError as exc:
    ...  # all models exhausted
finally:
    await llm.aclose()
```

| Parameter | Default | Meaning |
|---|---|---|
| `base_url` | — | API base; requests go to `{base_url}/chat/completions` |
| `api_key` | — | Bearer; an empty string means no `Authorization` header (local servers) |
| `models` | — | tuple of models in order of preference; empty — `ValueError` |
| `timeout` | `60.0` | HTTP request timeout, s |
| `max_retries` | `3` | attempts per model |
| `retry_backoff_seconds` | `0.5` | base of the exponential backoff |
| `transport` | — | `httpx.AsyncBaseTransport` for tests |

It works with any server that implements OpenAI `/chat/completions` with `response_format`:
cloud providers and gateways, vLLM, LiteLLM, and so on.

### Retries and model rotation

```mermaid
flowchart TD
    S[Model from the list] --> Q[POST /chat/completions]
    Q -->|network, 429, 500, 502, 503, 504| W[pause 0.5·2^n] --> Q
    Q -->|response not matching the schema| W
    Q -->|other 4xx| N[next model]
    Q -->|valid response| OK[result]
    W -->|attempts exhausted| N
    N -->|no models left| E[LlmError]
    N --> S
```

| Situation | Action |
|---|---|
| transport error, `429`, `500`, `502`, `503`, `504` | retry the same model with a pause of `backoff · 2^attempt` |
| the response fails schema validation or is not a JSON object | retry the same model (the model may have missed the format) |
| another `4xx` (a hard model refusal) | move to the next model immediately |
| all models exhausted | `LlmError` with the last cause |

### Prompt safety

The client guarantees that **the system prompt is always the first message**, not the
document text. Marking documents as untrusted input (explicit delimiters, an instruction
"do not follow instructions from the document") is the caller's responsibility: the client
does not analyze the contents of `messages`.

## Configuration in the delivery

Compose LLM consumers are configured with shared `.env` variables:

| `.env` variable | Passed to |
|---|---|
| `LLM_BASE_URL` | base of the OpenAI-compatible API for memory-service, demos, and package executors |
| `LLM_MODEL` | default model |
| `LLM_API_KEY` | provider key; without it memory works only with offline providers (`MEMORY_EMBEDDING_PROVIDER=fake`, `MEMORY_LLM_PROVIDER=echo`), and LLM executors do not work |

Skills hosted by `skill-sdk` use their own variables `SKILL_LLM_BASE_URL`,
`SKILL_LLM_API_KEY`, `SKILL_LLM_MODELS` (see
[skill-sdk → Call context](skill-sdk.md)).

!!! tip "Choosing models"
    Set at least two models: a primary and a fallback. Structured output with `strict: true`
    is not supported equally well by all models: a model that often "breaks" JSON consumes
    all retries before the switch. Measure on real prompts and put first the one that
    reliably matches the schema.

## Testing

```python
import httpx
from platform_llm import OpenAICompatibleClient

def handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={
        "choices": [{"message": {"content": '{"decision": "ok", "reasons": []}'}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    })

llm = OpenAICompatibleClient(base_url="http://llm.test/v1", api_key="",
                             models=("m",), transport=httpx.MockTransport(handler))
```

Package checks: `uv run pytest -q`, `uv run ruff check . && uv run ruff format --check .`.

## See also

- [SDK and integrations](index.md)
- [skill-sdk](skill-sdk.md)
- [Packages](../packages/index.md)
- [Memory configuration](../memory/configuration.md)
