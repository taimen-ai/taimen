# Клиенты сервисов

Канонические Python-клиенты платформы: `control-plane-client` для Control
Plane и `platform-memory-client` для memory-service. Статья описывает
подключение, разрешение credential, обмен PAT на access token, повторы и
идемпотентность, обработку ошибок и типовые сценарии. Для разработчиков
исполнителей, коннекторов, демо и вертикальных пакетов.

!!! tip "Не пишите свой клиент"
    Логика обмена токенов, повторов под тем же `Idempotency-Key` и разбора
    конверта ошибок уже есть в каноне (TAI-ADR-0030). Если чего-то не хватает,
    добавьте метод в клиент рядом с сервером, а не обёртку «по памяти о
    контракте» в своём репозитории.

## control-plane-client {#control-plane-client}

| | |
|---|---|
| Пакет | `control_plane_client` (дистрибутив `control-plane-client`) |
| Где лежит | `services/control-plane/client` |
| Зависимости | только `httpx` |
| Протокол | `control-harness/2`; базовый путь `{server}/api/v1` |

```toml
[tool.uv.sources]
control-plane-client = { path = "../control-plane/client", editable = true }
```

### Быстрый старт

```python
from control_plane_client import ControlPlaneClient, IamCredential

credential = IamCredential(
    "https://platform.example.com/iam",   # IAM
    "<iam-tenant-id>",
    audience="control-plane",
    scopes=("control-plane:read", "control-plane:write"),
)

async with ControlPlaneClient("https://platform.example.com", credential,
                              user_agent="acme-connector/0.1") as cp:
    ctx = await cp.get_context()
    task = await cp.create_task(...)       # Idempotency-Key генерируется сам
```

Второй аргумент `ControlPlaneClient` — строка (статический API-ключ) или
`CredentialProvider` (объект с `token()`, `refresh()`, `refreshable`).
`user_agent` ставится перед токеном SDK: `acme-connector/0.1 control-plane-client/<версия>`.

### Credential: откуда берётся PAT

Control Plane **не принимает PAT как Bearer**: PAT предъявляется только IAM,
а сервис получает короткоживущий access token своего audience.
`IamCredential` делает обмен
`POST {iam}/api/v1/platform-access-tokens:exchange` с телом
`{token, audience, scopes}`, кэширует токен и обменивает заново за
`refresh_margin_seconds` (по умолчанию 30 с) до истечения.

Порядок поиска PAT:

| Источник | Когда используется |
|---|---|
| аргумент `platform_access_token=` (строка или callable) | явная передача; callable читается при **каждом** обмене — ротация файла подхватывается без перезапуска; локальное хранилище не читается, tenant может быть пустым |
| `IAM_PLATFORM_ACCESS_TOKEN` | только вместе с `IAM_CREDENTIAL_MODE=environment` (или `ci`); без режима — ошибка `iam_environment_mode_required` |
| Keychain macOS | если не отключён `IAM_NO_KEYCHAIN=1` |
| файл `~/.config/iam/credentials.json` | учитывается `XDG_CONFIG_HOME` |

Запись в локальном хранилище адресуется тройкой `issuer|tenant|principal`.
Если на машине несколько credential одного tenant'а (несколько
исполнителей), процесс обязан назвать себя переменной `IAM_PRINCIPAL`; иначе
— отказ `iam_credential_ambiguous`, а не работа под чужой identity.

Процесс в контейнере с PAT в файле:

```python
from pathlib import Path
from control_plane_client import IamCredential

pat_file = Path("/run/secrets/agent.pat")
credential = IamCredential(
    "http://iam-service:8010", "",
    audience="control-plane",
    scopes=("control-plane:read", "control-plane:write"),
    platform_access_token=lambda: pat_file.read_text(),
)
```

Одному процессу нужны два сервиса — два `IamCredential` над одним PAT с
разными `audience` (правило «один токен — один audience»).

### Конфигурация из окружения

`resolve_credential(server_url)` выбирает credential харнесса: сначала IAM,
затем API-ключ.

| Переменная | Смысл |
|---|---|
| `CONTROL_PLANE_IAM_URL` | адрес IAM; без него IAM-режим не включается |
| `CONTROL_PLANE_IAM_TENANT` | tenant IAM; URL без tenant'а — ошибка конфигурации, а не молчаливый откат |
| `CONTROL_PLANE_IAM_AUDIENCE` | audience, по умолчанию `control-plane` |
| `CONTROL_PLANE_IAM_SCOPES` | scopes через пробел или запятую, например `"control-plane:read control-plane:write"` |
| `IAM_PRINCIPAL` | какой principal этот процесс, если на машине их несколько |
| `CONTROL_PLANE_API_KEY` | legacy API-ключ (только если IAM не настроен) |

Значения со пробелами в env-файлах, которые читает shell (`source`),
заключайте в кавычки.

### Команды, повторы и идемпотентность

| Свойство | Поведение |
|---|---|
| Создающие и action-команды (`create_task`, `claim_task`, `start_run`, `succeed_run`, `fail_run`, `create_artifact`, `request_approval`, …) | клиент ставит `Idempotency-Key` и повторяет запрос при **транспортном** сбое (всего до 3 попыток, паузы 0,5 с и 1 с) **тем же ключом** — повтор HTTP-запроса никогда не становится второй бизнес-командой |
| Свой ключ | `idempotency_key=` у `create_task`, `succeed_run`, `fail_run`, `create_artifact`, `request_approval` — для потребителей, которые повторяют команду по своему состоянию |
| 401 при refreshable credential | один переобмен и один повтор с тем же ключом; второй 401 — настоящий отказ |
| Оптимистичная блокировка | `update_task(..., expected_version=)`, `complete_task(..., version=)` отправляют `If-Match: "task-<version>"` |
| Чтения | без повторов |

### Ошибки

Ответы Control Plane приходят в конверте
`{"error": {"code", "message", "details", "requestId"}}` и превращаются в
исключения по коду, а при незнакомом коде — по статусу:

| Исключение | Коды / статус | Что делать |
|---|---|---|
| `AuthenticationError` | `invalid_credentials`, 401 | проверить PAT, binding |
| `PermissionDeniedError` | `permission_denied`, 403 | не хватает права в binding'е |
| `NotEligibleError` | `not_eligible` | нет роли/capability для задачи |
| `NotFoundError` | `not_found`, 404 | — |
| `ValidationError` | 422, 428, `unsupported_protocol_version` | исправить запрос |
| `StaleClaimError` | `stale_claim` | **прекратить запись**: владение задачей потеряно |
| `ClaimConflictError` | `task_already_claimed`, `task_claimed`, `claim_conflict`, … | задача занята |
| `VersionConflictError` | `version_conflict` | перечитать задачу, повторить с новой версией |
| `IdempotencyConflictError` | `idempotency_key_reused`, `idempotency_in_flight` | ключ использован с другим телом или команда ещё выполняется |
| `SessionExpiredError` | `session_expired`, `session_not_active` | открыть новую сессию |
| `ApprovalRequiredError`, `TaskNotReadyError`, `BudgetExceededError`, `SkillUnavailableError`, `RunNotActiveError`, `CancelledError` | одноимённые коды | см. [Исполнение — claims и runs](../control-plane/execution.md) |
| `TransportError` | ответа нет | повторить позже |
| `IamCredentialError` | `iam_unreachable`, `iam_invalid_token`, `iam_audience_not_allowed`, `iam_exchange_failed`, `iam_not_authenticated`, `iam_credential_ambiguous` | проблема обмена в IAM |

Все исключения наследуют `ControlPlaneError` (`code`, `message`, `status`,
`details`).

### Аренды: `HeartbeatRunner`

Сессия и claim — аренды с TTL. `HeartbeatRunner` продлевает их в фоне:

```python
from control_plane_client import HeartbeatRunner

runner = HeartbeatRunner(cp, session_id=session["id"], claim_id=claim["id"],
                         interval_seconds=60, max_transport_failures=3)
runner.start()
try:
    # … в цикле работы:
    if runner.error is not None:
        ...  # владение потеряно — прекратить авторитетные записи
finally:
    await runner.stop()
```

Доменная ошибка (аренда истекла, владение потеряно) терминальна и
сохраняется в `error`; транспортная ошибка повторяется на следующем тике и
становится терминальной только после `max_transport_failures` подряд.

### Привязка каталога к проекту

`find_project_config()` ищет вверх от текущего каталога
`.control-plane/config.json` — несекретную привязку рабочей копии к серверу,
tenant'у, workspace, проекту и репозиторию; `write_project_config()` её
записывает. Секретов в этом файле нет, его можно коммитить.

### Группы методов

| Группа | Методы (выборочно) |
|---|---|
| контекст и сессии | `get_context`, `open_session`, `heartbeat_session`, `close_session` |
| работа | `list_available_work`, `list_tasks`, `get_task`, `get_task_transitions`, `get_claimability` |
| задачи | `create_task`, `update_task`, `complete_task`, `add_task_relation`, `add_task_comment`, `edit_task_comment` |
| цели | `create_goal`, `list_goals`, `get_goal`, `update_goal`, `list_goal_work` |
| claims и runs | `claim_task`, `heartbeat_claim`, `release_claim`, `start_run`, `succeed_run`, `fail_run`, `suspend_run`, `prepare_handoff`, `continue_after_handoff`, `launch_child_run` |
| трасса | `create_checkpoint`, `record_action`, `finish_action` |
| артефакты | `create_artifact`, `get_artifact`, `list_artifacts` |
| approvals | `request_approval`, `list_approvals`, `approve`, `reject`, `get_approval_outcome` |
| инструменты | `search_tools`, `describe_tool` |
| агенты | `get_my_agent`, `get_agent`, `list_agents`, `publish_agent`, `list_agent_revisions` |

Полный контракт — OpenAPI Control Plane (`/openapi.json`, см.
[API Control Plane](../control-plane/api.md)).

## platform-memory-client {#memory-client}

| | |
|---|---|
| Пакет | `platform_memory_client` (дистрибутив `platform-memory-client`) |
| Где лежит | `services/memory-service/client` |
| Зависимости | `httpx`, `pydantic` (движок памяти не подтягивается) |
| Классы | `MemoryClient` (синхронный), `AsyncMemoryClient` (asyncio) |

!!! note "Кто ходит в память напрямую"
    Исполнители получают контекст задачи через Control Plane (контекст
    харнесса и run'а), а не из памяти напрямую — см.
    [Контекст задачи и память](../control-plane/context.md). Код пакетов —
    процессы, правила, скиллы, наблюдатели — тоже ходит в память только через
    ядро (см. [Память — только через ядро](index.md#memory-through-core)).
    Клиент памяти нужен приложениям с собственным грантом на namespace:
    коннекторам загрузки знаний, чат-ботам, консолям.

### Credential

Bearer — статический ключ-грант на namespace или access token IAM audience
`memory-service`. Параметр `token` принимает строку или callable
(вызывается перед каждым запросом); асинхронный клиент — ещё и объект с
`async token()`, то есть `IamCredential` подключается напрямую:

```python
from control_plane_client.iam import IamCredential
from platform_memory_client import AsyncMemoryClient

cred = IamCredential(
    "http://iam-service:8010", "",
    audience="memory-service",
    scopes=("memory:read", "memory:write"),
    platform_access_token=lambda: pat,
)
async with AsyncMemoryClient("http://memory-service:8077", token=cred) as mem:
    result = await mem.query("как получить пропуск для посетителя?", namespaces=["kb"])
```

### Методы

| Метод | Путь | Назначение |
|---|---|---|
| `healthz()` | `GET /healthz` | живость и статистика графа |
| `recall(query, budget=, hops=, namespaces=, …)` | `POST /recall` | поиск с раскрытием связей |
| `search(...)` | `POST /search` | гибридный поиск |
| `query(question, k=8, hops=1, synthesize=, namespaces=, …)` | `POST /api/brain/query` | ответ с источниками (опционально — синтез LLM) |
| `retain(content, type=, external_id=, title=, links=, provenance=, run_id=, namespace=)` | `POST /retain` | идемпотентная запись факта или решения |
| `audit(...)` | `POST /audit` | аудит записей |
| `retain_document(...)`, `delete_document(key)` | `/api/brain/documents` | загрузка и удаление документа |
| `nodes(...)`, `node(key)`, `source(key)`, `delete_node(key)` | `/api/brain/nodes`, `/api/brain/sources` | узлы графа и источники |
| `observe(...)`, `observe_batch(...)` | `POST /api/memory/observations` | наблюдения |
| `context(request, namespaces=, run_id=, …)` | `POST /api/memory/context` | собрать ограниченный ContextPack без синтеза |
| `register_package`, `packages`, `package` | `/api/memory/packages` | доменные пакеты видов (scope `memory:service`) |
| `namespace_kinds`, `set_namespace_kinds` | `/api/memory/namespaces/{ns}/kinds` | виды namespace |
| `reconcile(...)`, `typed_context(...)` | `/api/memory/reconcile`, `/api/memory/context/typed` | сверка и типизированный контекст |

Параметры `allowed_namespaces` / `allowed_scopes` у чтений сужают видимость:
для обычного вызывающего они пересекаются с тем, что сервер и так
разрешает, и никогда не расширяют её; пустой список не видит ничего.
`run_id` передаётся заголовком `X-Run-Id` для корреляции.

### Ошибки

| Исключение | Когда |
|---|---|
| `MemoryServiceError` | ответ 4xx/5xx; поля `status_code`, `detail`; свойства `unavailable` (5xx) и `not_found` |
| `MemoryTransportError` | ответа нет (`status_code == 0`) |

Подробно о контракте памяти — [API памяти](../memory/api.md).

## Сценарий: коннектор, который заводит задачи

```python
import asyncio
from pathlib import Path
from control_plane_client import ControlPlaneClient, IamCredential, ConflictError

async def main() -> None:
    cred = IamCredential(
        "http://iam-service:8010", "",
        scopes=("control-plane:read", "control-plane:write"),
        platform_access_token=lambda: Path("/run/secrets/connector.pat").read_text(),
    )
    async with ControlPlaneClient("http://control-plane-api:8000", cred,
                                  user_agent="acme-connector/0.1") as cp:
        for item in await fetch_new_items():
            try:
                await cp.create_task(
                    ...,                                 # поля задачи по OpenAPI
                    idempotency_key=f"acme:{item.id}",   # повтор не создаст дубль
                )
            except ConflictError:
                continue

asyncio.run(main())
```

Principal коннектора — вида `agent` или `service` с IAM-binding'ом в Control
Plane (права `tasks.read`, `tasks.write`, при необходимости `events.read`),
PAT — в файле с правами `0600`.

## См. также

- [SDK и интеграции](index.md)
- [platform-auth-sdk](platform-auth-sdk.md)
- [Харнесс-протокол](../control-plane/harness-protocol.md)
- [Credentials и PAT](../iam/credentials.md)
- [API памяти](../memory/api.md)
