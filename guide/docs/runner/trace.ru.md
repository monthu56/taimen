# Трасса прогонов

Что автономный исполнитель сообщает Control Plane о ходе своей работы (CP-ADR-0051):
ограниченный отредактированный транскрипт как артефакт `transcript` и по одному run action
на каждый вызов инструмента в реальном времени. Статья для оператора, читающего прогоны, и
для инженера, решающего, что можно публиковать с конкретной площадки.

## Что публикуется, а что нет

| Данные | Куда | Условие |
|---|---|---|
| Итоговое summary агента | артефакт `report` (`content.summary`, до 60000 символов, пути вырезаны) | всегда |
| Счётчики хода (модель, число ходов, длительность, стоимость, токены) | metadata артефакта `report` | всегда |
| Сообщения агента, вызовы инструментов с входом и результатом, итог | артефакт `transcript` (`agent-transcript/1`) | `CONTROL_PLANE_TRACE_TRANSCRIPT` |
| Результаты инструментов внутри транскрипта | там же | `CONTROL_PLANE_TRACE_TOOL_RESULTS` |
| Один action на вызов инструмента | run actions `tool.<имя>` | `CONTROL_PLANE_TRACE_ACTIONS` |
| Action хода целиком | `claude-code.turn` / `codex.turn` | всегда |
| Prompt | — | **никогда** |
| Скрытые рассуждения (`thinking`, reasoning summaries) | — | **никогда**; только счётчик `hiddenReasoningBlocks` |
| Сырой поток CLI | локальный журнал на хосте runner'а | `CONTROL_PLANE_CLAUDE_LOGS` / `CONTROL_PLANE_CODEX_LOGS` |

Трассу публикуют адаптеры `claude-code` и `codex`. Харнесс OpenCode и адаптер `echo`
транскрипт не публикуют.

## Флаги

| Переменная | По умолчанию | `0` / `false` / `no` / `off` означает |
|---|---|---|
| `CONTROL_PLANE_TRACE_TRANSCRIPT` | `1` | не публиковать артефакт `transcript` |
| `CONTROL_PLANE_TRACE_ACTIONS` | `1` | не писать run actions `tool.*` |
| `CONTROL_PLANE_TRACE_TOOL_RESULTS` | `1` | в транскрипте у результатов инструментов оставить только размер и флаг ошибки |

!!! tip "Площадка, где вывод инструментов не должен покидать хост"
    Выключите только `CONTROL_PLANE_TRACE_TOOL_RESULTS`. Разговор агента, список вызовов и
    аудит в run actions останутся, а содержимое файлов и вывод команд — нет.

## Артефакт `transcript`

Один JSON-документ схемы `agent-transcript/1`, не больше **512 КиБ**.

```json
{
  "schema": "agent-transcript/1",
  "harnessType": "claude-code",
  "sessionId": "5b0e…",
  "model": "<model-id>",
  "tools": ["Bash", "Read", "Edit", "mcp__control-plane__cp_get_run_context"],
  "entries": [
    {"seq": 1, "at": "2026-01-15T10:00:01.120Z", "kind": "assistant", "text": "Смотрю структуру модуля."},
    {"seq": 2, "at": "…", "kind": "tool_call", "call": 1, "callId": "toolu_…", "tool": "Read",
     "input": "{\n \"file_path\": \"<path>/service.py\"\n}"},
    {"seq": 3, "at": "…", "kind": "tool_result", "call": 1, "callId": "toolu_…", "isError": false,
     "output": "…"},
    {"seq": 4, "at": "…", "kind": "tool_call", "call": 2, "tool": "Bash",
     "input": "{\n \"command\": \"uv run pytest -q\"\n}"},
    {"seq": 5, "at": "…", "kind": "tool_result", "call": 2, "isError": false,
     "withheld": true, "outputChars": 1830}
  ],
  "final": {"text": "Сделано: …", "truncated": false},
  "usage": {"inputTokens": 120345, "outputTokens": 8812, "costUsd": 0.61, "durationMs": 412000, "turns": 28},
  "stats": {
    "assistantMessages": 14, "userMessages": 0, "toolCalls": 31, "toolErrors": 2,
    "hiddenReasoningBlocks": 9, "truncatedEntries": 1, "droppedEntries": 0
  },
  "truncated": true
}
```

### Виды записей

| `kind` | Поля | Откуда |
|---|---|---|
| `assistant` | `text` | текстовые блоки ответа агента |
| `user` | `text` | текстовый ввод в ходе (не prompt) |
| `tool_call` | `call` (порядковый номер), `callId`, `tool`, `input` | вызов инструмента |
| `tool_result` | `call`, `callId`, `isError`, `output` **или** `withheld: true` + `outputChars` | результат инструмента |

У каждой записи есть `seq` и `at`; запись, обрезанная по лимиту, помечена `truncated: true`.

### Лимиты

| Что | Лимит |
|---|---|
| Весь документ | 512 КиБ; записи сверх бюджета не сохраняются, а считаются в `droppedEntries` |
| Текст сообщения | 20000 символов |
| Вход инструмента | 6000 символов |
| Результат инструмента | 6000 символов |
| Итоговый ответ | 60000 символов, у него свой слот вне бюджета записей |

Обрезанный текст заканчивается пометкой `… [truncated N chars]`.

### Редакция

Каждая строка перед сохранением проходит две редакции:

- **пути хоста** заменяются на `<path>`; у глубоких путей (от четырёх сегментов) сохраняется
  имя файла — `<path>/README.md` говорит читателю, какой файл агент трогал, не раскрывая
  раскладку хоста;
- **credentials** заменяются на `<redacted>`: префиксы `cp_`, `sk-`, `ghp_`, `github_pat_`,
  `xox?-`, JWT вида `eyJ….….…`, пары `token=…`, `password: …`, `api_key=…`,
  `authorization: …`, `client_secret=…` и подобные; приватные ключи PEM — на
  `<redacted private key>`.

После сборки документ целиком проверяется тем же guard'ом переносимости, что и все
артефакты. Если что-то всё же не прошло, транскрипт **не публикуется текстом**: вместо него
уходит документ с `withheld: true`, `reason: "unsafe_payload"`, счётчиками и usage — run
при этом не падает.

### Metadata

Metadata артефакта — то, что читатель хочет знать до открытия документа:

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

Пока ход идёт, адаптер на каждый `tool_use` пишет run action и закрывает его по
`tool_result`. Так клиенты видят ход прогона вживую, не дожидаясь транскрипта.

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
{"status": "completed"}        // или "failed", если результат с is_error
```

| Поле | Правило |
|---|---|
| `action` | `tool.<имя>`; из имени остаются только `[A-Za-z0-9_.:/-]`, остальное заменяется на `_`; до 200 символов |
| `metadata.summary` | одна строка до 160 символов: первое содержательное поле входа (`command`, `cmd`, `file_path`, `path`, `pattern`, `query`, `url`, `prompt`, `skill`), отредактированное |
| `externalReference` | указатель в транскрипт: `<адаптер>:session/<id>#call/<n>` |

Run actions несут **ссылки, а не полезную нагрузку**: входы и выходы живут только в
артефакте.

Особые случаи:

- вызов, результат которого так и не пришёл (падение, таймаут), по окончании хода
  закрывается со статусом `failed`;
- если run упёрся в свой бюджет actions (`budget_exceeded`), адаптер перестаёт писать
  actions, но продолжает работу; транскрипт по-прежнему содержит всё;
- сбой записи action пишется в журнал runner'а и проглатывается — учёт не должен
  превращать сделанную работу в провал.

Кроме `tool.*` каждый ход оборачивается action'ом `claude-code.turn` / `codex.turn` со
ссылкой на сессию агента.

## Checkpoints прогона

Трасса дополняется checkpoints, которые пишут адаптер и демон:

| `kind` | Кто | Данные |
|---|---|---|
| `execution.workspace` | демон | ключ копии, ветка, базовый коммит, ревизии соседей; после коммита — `head`, `published` |
| `claude-code.session` | адаптер | `claudeSessionId`, `resumed`, `phase` (`started` / `finished` / `failed`), `subtype`, `turns` |
| `codex.session` | адаптер | `codexSessionId`, `phase` |
| `opencode.session` | харнесс OpenCode | `openCodeSessionId`, `lastMessageId` |

## Где это читать

=== "MCP"

    ```text
    cp_get_run(run_id)              → сам run
    cp_get_run_context(run_id)      → checkpoints, артефакты, approvals
    cp_list_artifacts(task_id)      → report, transcript, commit
    ```

=== "API"

    ```bash
    curl -sS "$CP/api/v1/runs/<run-id>/actions" -H "Authorization: Bearer $TOKEN"
    curl -sS "$CP/api/v1/runs/<run-id>/checkpoints" -H "Authorization: Bearer $TOKEN"
    curl -sS "$CP/api/v1/artifacts?taskId=<task-id>" -H "Authorization: Bearer $TOKEN"
    ```

## Локальный журнал на хосте

Сырой поток CLI (stream-json Claude Code или JSON-события Codex) и stderr пишутся в
`<runtime>/sessions/<publicId>-<session>.jsonl` с правами `0600`. Потолок — 32 МБ на файл за
всю его жизнь, включая продолженные ходы; сверх потолка строки не пишутся. Это единственное
место, где остаётся prompt и полный вывод, — доступ к нему ограничен доступом к хосту
runner'а. Выключается `CONTROL_PLANE_CLAUDE_LOGS=0` / `CONTROL_PLANE_CODEX_LOGS=0`.

## См. также

- [Артефакты и комментарии](../control-plane/artifacts.md)
- [Исполнение — claims и runs](../control-plane/execution.md)
- [Адаптеры исполнителей](adapters.md)
- [Модель безопасности](../overview/security-model.md)
