# Адаптеры исполнителей

Адаптер — сменная часть runner'а, которая отвечает на один вопрос: «заставить кодового
агента сделать работу». Статья описывает три реализации — Claude Code, Codex и OpenCode, —
как они запускают CLI, где берут credentials, в каком режиме разрешений работают и что
попадает в prompt.

## Контракт адаптера

Цикл координации принадлежит демону `control-plane-agent`; адаптер получает одну задачу:

```python
async def execute(task, run, client, workspace) -> list[ArtifactSpec]: ...
```

| Аргумент | Что это |
|---|---|
| `task` | задача целиком (`publicId`, `title`, `description`, `typeKey`, …) |
| `run` | текущий run (`id`, `attempt`) |
| `client` | `ControlPlaneClient` под identity агента |
| `workspace` | рабочая копия задачи или `None`, если пул рабочих копий не настроен |

Адаптер возвращает спецификации артефактов (`report`, `transcript`); демон проверяет их на
переносимость (нет локальных путей и credential'ов), записывает, добавляет артефакт
`commit` и сам вызывает `succeed_run`. Исключение из адаптера превращается в `fail_run` с
причиной, из которой вырезаны пути хоста.

Выбор адаптера — `CONTROL_PLANE_AGENT_ADAPTER`:

| Значение | Реализация | Назначение |
|---|---|---|
| `echo` (по умолчанию) | встроенный | протокольные проверки: пишет action `echo.observe` и артефакт `report` с заголовком задачи |
| `claude-code` | `control_plane_claude` | Claude Code CLI (`claude -p`) |
| `codex` | `control_plane_codex` | Codex CLI (`codex exec`) |

Вендорские адаптеры импортируются лениво: демон работает на хосте, где CLI не установлен,
а неизвестное имя даёт `unknown adapter '…'` при старте.

OpenCode устроен иначе — это отдельный харнесс со своим циклом (см.
[ниже](#opencode)).

## Общие правила всех адаптеров

- **Prompt — через stdin**, никогда аргументом: аргументы процесса видны всем на хосте.
- **Секреты — только через наследуемое окружение.** Токен подписки или API-ключ не
  попадают ни в argv, ни в файлы конфигурации run'а.
- **Сессия агента переживает рестарт.** Идентификатор сессии пишется в checkpoint run'а;
  следующая попытка той же задачи продолжает тот же разговор, а не начинает новый.
- **Сырой поток остаётся на хосте.** Каждая строка вывода CLI пишется в локальный журнал
  `<runtime>/sessions/<publicId>-<session>.jsonl` (`0600`, потолок 32 МБ на файл за всю его
  жизнь, включая продолженные ходы). В Control Plane уходят только summary, счётчики и
  ограниченный отредактированный транскрипт (см. [Трасса прогонов](trace.md)).
- **Один ход на run.** Адаптер не ведёт многоходовый диалог; продолжение работы — следующий
  run, читающий checkpoints предыдущего.
- **Исход решает демон.** Агенту прямо сказано: не claim'ить, не завершать, не пушить и не
  открывать pull request — ветку публикует демон.

## Claude Code

### Как запускается

```text
claude --print --output-format stream-json --verbose \
       --permission-mode <mode> \
       --session-id <uuid>            # новая сессия
       | --resume <uuid>              # продолжение
       [--model <model>] \
       [--mcp-config <runtime>/mcp.json --strict-mcp-config] \
       [--disallowedTools mcp__control-plane__cp_claim_task …]
```

Рабочий каталог процесса — рабочая копия задачи (`worktrees/<publicId>/<repo>`).

Идентификатор сессии генерируется адаптером **до** запуска процесса и сразу пишется в
checkpoint `claude-code.session` (`{"claudeSessionId", "resumed", "phase": "started"}`). Если
runner упадёт посреди хода, следующая попытка найдёт этот checkpoint и передаст `--resume`.
По завершении хода пишется checkpoint с `phase: finished`, `subtype`, `turns`; при ошибке —
`phase: failed` и тип исключения (без текста: в нём бывают пути).

Результат хода — событие `result` потока stream-json. Ход с `is_error` или ненулевым кодом
выхода — провал run; ход без события `result` — ошибка `claude exited with code … without a
result` с хвостом stderr в журнале runner'а.

### Аутентификация

| Вариант | Переменная | Примечание |
|---|---|---|
| Подписка | `CLAUDE_CODE_OAUTH_TOKEN` | выпускается `claude setup-token` на машине с браузером; принадлежит человеку |
| API-ключ | `ANTHROPIC_API_KEY` | оплата за токены |

Адаптер токен не читает и не копирует: дочерний процесс и запущенные им MCP-серверы
наследуют окружение runner'а. Следствие: агент видит токен в своём окружении — это свойство
конструкции, поэтому периметр строится вокруг процесса (пользователь, контейнер), а не
внутри него.

!!! note "Окно подписки"
    Исчерпание окна подписки сейчас — обычная ошибка хода и `fail_run`. Параллельные
    прогоны на токене человека расходуют то же окно, что и его интерактивные сессии.

### Режим разрешений

`CONTROL_PLANE_CLAUDE_PERMISSION_MODE` передаётся в `--permission-mode`:

| Режим | Поведение | Когда |
|---|---|---|
| `acceptEdits` (по умолчанию) | правки файлов без запроса, остальные команды требуют подтверждения | безопасный старт; в неинтерактивном режиме агент не сможет выполнять команды (тесты, сборка) |
| `bypassPermissions` | все инструменты без запросов | рабочий режим автономного исполнителя — только внутри периметра |

Без `bypassPermissions` автономный агент не выполнит ни одной shell-команды: подтверждать
некому, и в отчётах это видно как «every tool call requires approval». Периметр при этом —
непривилегированный пользователь с `ProtectSystem=strict` или контейнер.

### MCP внутри агента {#mcp-inside}

При `CONTROL_PLANE_CLAUDE_MCP=1` (по умолчанию) адаптер пишет
`<runtime>/mcp.json` (`0600`) и передаёт его с `--strict-mcp-config` — агент получает ровно
один MCP-сервер `control-plane` и не видит чужих, настроенных у пользователя:

```json
{"mcpServers": {"control-plane": {"type": "stdio", "command": "control-plane-mcp", "args": []}}}
```

В файле нет ни адреса сервера, ни токена: `control-plane-mcp` наследует окружение runner'а и
резолвит identity так же, как демон. Агент работает под тем же principal'ом.

Через MCP агент сам читает `cp_get_run_context`, пишет checkpoints и артефакты. Но
**авторитетные инструменты у него отобраны** флагом `--disallowedTools`. Список не
записан в адаптере, а вычисляется из самого MCP-сервера (`withheld_tool_names()`): отбирается
всё, что не помечено read-only и не входит в набор инструментов evidence.

| Агенту доступно | Агенту недоступно (примеры) |
|---|---|
| все read-only: `cp_whoami`, `cp_context`, `cp_get_task`, `cp_get_run_context`, `cp_list_*`, `cp_search_tools`, … | `cp_claim_task`, `cp_release_task`, `cp_start_run` |
| evidence: `cp_checkpoint`, `cp_record_action`, `cp_create_artifact`, `cp_remember`, `cp_comment`, `cp_request_approval` | `cp_complete_run`, `cp_fail_run`, `cp_suspend_run`, `cp_prepare_handoff` |
| | `cp_create_task`, `cp_update_task`, связи, цели |
| | `cp_approve`, `cp_reject`, `cp_invoke_skill`, `cp_launch_child`, `cp_control_run`, `cp_focus_project` |

Инструмент без аннотации считается авторитетным — забытая разметка закрывает дверь, а не
открывает.

!!! warning "Это сужение задачи, а не граница безопасности"
    Агент работает под тем же credential, что и демон, и технически может дойти до API
    мимо MCP. Настоящий потолок — права binding агента (и child grant, который вычисляет
    сервер для дочерних run). `--disallowedTools` лишь убирает соблазн.

### Prompt

Prompt собирается из частей в фиксированном порядке:

1. **Системная заметка**: ты автономный исполнитель одной задачи; MCP `control-plane`
   доступен для контекста, записей и checkpoints; не claim'ить, не завершать; работать
   только в текущем каталоге; не пушить и не открывать PR; закончить summary.
2. **Задача**: `# Task <publicId>: <title>` и описание.
3. **Проект** (если задача в проекте): статус и шаблон.
4. **Входы** задачи, если их объявил её тип (раздел `## Входы`, см.
   [ниже](#task-inputs)).
5. **Контекст задачи** из памяти (раздел `## Контекст задачи`, см. ниже).
6. **Соглашения репозитория** — содержимое `CONTROL_PLANE_CLAUDE_PROMPT_FILE` под заголовком
   `## Repository conventions`.

Системная заметка также говорит агенту, что файл-результат, который не является
частью кода (документ, отчёт), сдаётся вызовом `cp_create_artifact` с параметром `file`:
инструмент загружает файл в Control Plane, и тот становится артефактом run'а (см.
[Содержимое в хранилище](../control-plane/artifacts.md#content)).

### Файл соглашений

`CONTROL_PLANE_CLAUDE_PROMPT_FILE` — путь к текстовому файлу, который дописывается в
**каждый** prompt. Описание задачи говорит «что сделать»; файл соглашений — «как устроен
этот репозиторий»: как запускать тесты, что никогда не коммитить, где лежат ADR, как
нумеровать миграции, каким сервисам можно доверять как контрактам. Это знание иначе стоит
по одному раунду ревью на каждую ветку.

Файл читается при каждом запуске хода — правка вступает в силу без перезапуска runner'а.
Нечитаемый файл пишется в журнал предупреждением, ход продолжается без него.

Пример структуры:

```markdown
# Соглашения для агента-исполнителя

## Среда
- Рабочая копия — текущий каталог. Соседи `../platform-auth-sdk` стоят на ревизиях
  суперпроекта и доступны только для чтения.
- Контракт другого сервиса не выдумывай: бери схемы из кода соседа и закрепляй
  contract-тестом.
- Полный прогон тестов: `uv run ruff check . && uv run pytest -q`.

## Правила
- Меняешь контракт API или схему БД — обнови ADR в том же коммите.
- Не коммить секреты, абсолютные пути, `.env`, артефакты сборки.
- Не трогай `main`: демон сам коммитит и публикует ветку задачи.

## Отчёт
Первой строкой — что сделано. Дальше: изменённые места, какие тесты прогнаны и с каким
результатом, что требует решения человека.
```

### Параметры

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CONTROL_PLANE_CLAUDE_BINARY` | `claude` | путь к CLI |
| `CONTROL_PLANE_CLAUDE_MODEL` | как настроено у CLI | модель (`--model`) |
| `CONTROL_PLANE_CLAUDE_PERMISSION_MODE` | `acceptEdits` | режим разрешений |
| `CONTROL_PLANE_CLAUDE_TIMEOUT` | `3600` | потолок одного хода, секунды; по истечении процесс убивается, run проваливается |
| `CONTROL_PLANE_CLAUDE_MCP` | `1` | `0` — не передавать MCP внутрь |
| `CONTROL_PLANE_CLAUDE_LOGS` | `1` | `0` — не писать локальный журнал сессии |
| `CONTROL_PLANE_CLAUDE_RESUME` | `1` | `0` — всегда начинать новую сессию |
| `CONTROL_PLANE_CLAUDE_RUNTIME_DIR` | `~/.claude-runner` | где лежат `mcp.json` и `sessions/` |
| `CONTROL_PLANE_CLAUDE_PROMPT_FILE` | — | файл соглашений репозитория |

!!! tip "Таймаут хода"
    Задачи с миграцией, API, клиентом и тестами редко укладываются в час. Для таких
    очередей поднимайте `CONTROL_PLANE_CLAUDE_TIMEOUT` (например до `10800`), помня, что
    зависший ход держит аренду до конца таймаута.

## Codex

### Как запускается

```text
codex exec --json --sandbox <sandbox> [--model <model>] -          # новая сессия
codex exec --json --sandbox <sandbox> [--model <model>] resume <id> -   # продолжение
```

`-` в конце заставляет Codex читать prompt из stdin.

В отличие от Claude Code, идентификатор новой сессии выбирает сам Codex и сообщает первым
событием потока (`thread.started`). Поэтому для новой сессии checkpoint `codex.session`
(`{"codexSessionId", …}`) пишется в момент чтения этого события — уже после старта
процесса, но до реальной работы. Для продолжения известной сессии checkpoint пишется до
старта, как у Claude Code.

### Особенности

- **Без MCP внутри.** Control Plane MCP Codex не передаётся: весь контекст задачи встроен
  в prompt, и агенту сказано, что инструментов Control Plane у него нет.
- **Аутентификация** — `auth.json` в `$CODEX_HOME` (по умолчанию `~/.codex/auth.json`;
  подписка ChatGPT или ключ) или `OPENAI_API_KEY`. Адаптер не трогает `CODEX_HOME`, но
  Codex переписывает `auth.json` при каждом запуске — каталог должен быть записываемым и
  постоянным (volume в контейнере), иначе после рестарта понадобится новый вход.
- **Песочница** — `CONTROL_PLANE_CODEX_SANDBOX`, по умолчанию `workspace-write` (правки в
  рабочей копии). Собственный режим Codex «только чтение» агенту бесполезен. Для
  ревьюера, которому нужно гонять тесты и `git fetch`, применяют `danger-full-access` —
  тоже только внутри периметра.
- **Исчерпание квоты** распознаётся по тексту ошибки (`rate limit`, `usage limit`, `quota`,
  `429`) и именуется отдельным исключением, но пока, как и у Claude Code, приводит к
  обычному `fail_run`.
- Файла соглашений у Codex-адаптера нет; всё нужное кладите в описание задачи.
- Action хода — `codex.turn`; артефакты — `report` (summary) и `transcript`.

### Параметры

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CONTROL_PLANE_CODEX_BINARY` | `codex` | путь к CLI |
| `CONTROL_PLANE_CODEX_MODEL` | как настроено у CLI | модель |
| `CONTROL_PLANE_CODEX_SANDBOX` | `workspace-write` | режим песочницы |
| `CONTROL_PLANE_CODEX_TIMEOUT` | `3600` | потолок хода, секунды |
| `CONTROL_PLANE_CODEX_RESUME` | `1` | `0` — всегда новая сессия |
| `CONTROL_PLANE_CODEX_LOGS` | `1` | `0` — без локального журнала |
| `CONTROL_PLANE_CODEX_RUNTIME_DIR` | `~/.codex-runner` | каталог журналов `sessions/` |
| `CONTROL_PLANE_CODEX_CREDENTIAL_CLASS` | — | метка класса credential (подписка / ключ); попадает в metadata артефакта как `credentialClass` |

## OpenCode {#opencode}

`control-plane-opencode` — самостоятельный харнесс, а не адаптер демона: у него свой цикл
discovery → claim → run, и он управляет процессом `opencode serve` по его HTTP API.

| Особенность | Значение |
|---|---|
| Запуск | `control-plane-opencode` рядом с `opencode serve` |
| Адрес OpenCode | `OPENCODE_SERVER` (по умолчанию `http://127.0.0.1:4096`), пароль — `OPENCODE_SERVER_PASSWORD` |
| Модель и агент | `OPENCODE_MODEL`, `OPENCODE_AGENT` |
| Очередь | `CONTROL_PLANE_AGENT_WORKSPACE`, `CONTROL_PLANE_AGENT_PROJECT`, `CONTROL_PLANE_AGENT_SUBPROJECTS`, `CONTROL_PLANE_AGENT_POLL` |
| Credential | только API-ключ Control Plane (`CONTROL_PLANE_API_KEY` или хранилище `control-plane login`) |
| Рабочая копия | нет пула worktree; работает в каталоге процесса |
| Continuity | checkpoint `opencode.session` с `openCodeSessionId` и `lastMessageId` |
| Результат | action `opencode.prompt`, артефакт `report` (`opencode-summary`) |
| Транскрипт | не публикуется |

!!! warning "Ограничения OpenCode-харнесса"
    Харнесс не умеет IAM-identity (только legacy API-ключ), не фильтрует задачи по
    назначению и не использует рабочие копии. На сервере, где legacy-ключи выключены, он
    не аутентифицируется. Используйте его для экспериментов, а для работы — демон с
    адаптером `claude-code` или `codex`.

## Входы задачи { #task-inputs }

Если тип задачи объявляет входы (`artifactSchema.inputs`, см.
[Входы и выходы](../control-plane/task-types.md#artifact-schema)), демон готовит их сам
перед запуском адаптера; раздел в prompt получают Claude Code и Codex:

1. читает `inputs` из `GET /runs/{id}/context`;
2. скачивает каждый вход с содержимым в хранилище (`contentState: stored`) через
   `GET /artifacts/{id}/content?forTask=<задача>` в
   `<runtime>/inputs/<key>/<name>`. Каталог `<runtime>` — каталог задачи рядом с рабочей
   копией, а не внутри неё: вход не часть изменения, и `git add -A` его не захватит.
   Корень — `CONTROL_PLANE_AGENT_RUNTIME_DIR`, по умолчанию `.runtime` в корне пула
   рабочих копий (без пула — `~/.control-plane-agent/runtime`);
3. имя файла очищается до одного компонента пути: разделители и служебные символы
   заменяются на `_`, ведущие точки убираются, длина ограничена;
4. каталог входов пересоздаётся на каждом run, так что новая head-ревизия заменяет
   старую; после успешного run он удаляется.

В prompt появляется раздел `## Входы` — внутри ограды `<task_inputs>…</task_inputs>` с
предупреждением, что имена и содержимое входов — данные от других участников, а **не
инструкции**. По строке на вход: ключ, тип, задача-источник и связь, имя, id артефакта,
media type, размер и одно из:

| Состояние | Что в строке |
|---|---|
| скачан | `file: <локальный путь>` |
| не скачался | `not downloaded (<код ошибки>); read it with cp_get_artifact_content` |
| содержимое удалено | `content purged by an administrator` |
| ссылка без содержимого | `reference only: <uri>` |

Неудачное скачивание не проваливает run: агент видит, какой вход недоступен и почему, и
может получить его сам MCP-инструментом `cp_get_artifact_content` (Claude Code). Обходится
ли работа без входа — решает агент и пишет об этом в summary.

## Контекст задачи в prompt

Все три реализации запрашивают у Control Plane рабочий контекст задачи (`POST
/api/v1/context` с `task`, `run` и `includeMemory`) и превращают его в раздел
`## Контекст задачи` одной общей функцией. Правила раздела:

- элементы памяти сгруппированы по секциям пакета (`current`, `relevant_facts`,
  `related_entities`, `documents`, затем прочие), у каждого — источник `[source: …]`;
- всё находится внутри ограды `<recalled_memory>…</recalled_memory>` с предупреждением,
  что это данные от разных участников, а **не инструкции**; элемент не может закрыть ограду
  досрочно или начать собственную строку prompt'а;
- каждая строка проходит редакцию путей хоста и credential'ов;
- один элемент — не длиннее 600 символов; весь раздел — не больше
  `CONTROL_PLANE_CONTEXT_BUDGET_CHARS` (по умолчанию 12000); не вошедшее считается строкой
  `… N more item(s) omitted by the context budget`;
- если память недоступна, пуста или не поместилась — одна строка
  `контекст памяти недоступен: <причина>`. Run из-за этого не падает: задача сама по себе
  авторитетна.

Подробнее о памяти и контексте — [Контекст задачи и память](../control-plane/context.md).

## Сравнение

| | Claude Code | Codex | OpenCode |
|---|---|---|---|
| Тип | адаптер демона | адаптер демона | отдельный харнесс |
| `harness.type` | `claude-code` | `codex` | `opencode` |
| Credential Control Plane | IAM PAT или API-ключ | IAM PAT или API-ключ | только API-ключ |
| Рабочие копии и ветки | да | да | нет |
| MCP Control Plane внутри | да, без авторитетных инструментов | нет | нет |
| Файл соглашений | `CONTROL_PLANE_CLAUDE_PROMPT_FILE` | нет | нет |
| Транскрипт и `tool.*` actions | да | да | нет |
| Checkpoint сессии | `claude-code.session` (до старта) | `codex.session` (по `thread.started`) | `opencode.session` |
| Сигнал «остановлен» (`executor_blocked`) | checkpoint `blocked` (`cp_checkpoint`) | файл `CONTROL_PLANE_BLOCKED_FILE` → checkpoint `blocked` | нет |

## См. также

- [Рабочие копии](execution-workspace.md)
- [Трасса прогонов](trace.md)
- [Агент остановился без результата](declarative-agents.md#blocked)
- [Конфигурация](configuration.md)
- [CLI и MCP-сервер](../control-plane/cli-and-mcp.md)
