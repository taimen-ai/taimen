# API памяти

Справочник HTTP API memory-service: все маршруты `/api/brain/*` и `/api/memory/*`,
их параметры, ответы и коды ошибок, а также MCP-сервер и клиентская библиотека.
Для интеграторов. Концепции — в [Модели знаний](knowledge-model.md), правила
доступа — в [Namespaces и доступ](namespaces.md).

## Общие правила

| Что | Правило |
|---|---|
| Базовый адрес | Внутри сети compose — `http://memory-service:8077`; с хоста — `http://127.0.0.1:${MEMORY_HOST_PORT:-18001}`. Ниже — `$MEMORY_URL` |
| Авторизация | `Authorization: Bearer <token>` на всех маршрутах, кроме `GET /healthz` и автодокументации |
| Формат | JSON, UTF-8 |
| Ошибки | `{"detail": "<описание>"}` с HTTP-кодом |
| Сквозной идентификатор | Заголовок `X-Run-Id` — попадает в provenance записи и в аудит |
| Автодокументация | `GET /docs` (Swagger UI), `GET /openapi.json` |
| Совместимость | `/api/brain/*` расширяется только аддитивно: новые поля и маршруты |

Типовые коды ответа:

| Код | Смысл |
|---|---|
| `200` / `201` / `207` | Успех / создано / пакетный результат по элементам |
| `400` | Некорректные данные: имя namespace, противоречивые поля, лимиты, невалидный `uuid` в данных |
| `401` | Нет или неверный токен, дефектный IAM-токен |
| `403` | Нет прав на namespace, вне видимости principal, нужен service scope |
| `404` | Не найдено в этом namespace |
| `409` | Конфликт версии пакета, устаревший снимок |
| `413` | Слишком большой пакет наблюдений |
| `422` | Вид сущности или связь вне схемы в строгом namespace |
| `500` | Внутренняя ошибка (в том числе ошибка провайдера эмбеддингов/LLM) или некорректный `CB_API_KEYS` |
| `503` | БД, JWKS IAM или внешний PDP видимости (если включён) недоступны |

## Сводка маршрутов

| Метод и путь | Доступ | Назначение |
|---|---|---|
| `GET /healthz` | без авторизации | Живость + статистика графа |
| `GET /api/brain/health` (`/health`) | любой токен | То же с проверкой токена |
| `POST /api/brain/query` | чтение | Вопрос → фрагменты, соседи, источники, опционально ответ LLM |
| `POST /api/brain/recall` (`/recall`) | чтение | Контекст под бюджет |
| `POST /api/brain/search` (`/search`) | чтение | Семантический или структурный поиск |
| `GET /api/brain/nodes` | чтение | Список узлов с фильтром |
| `GET /api/brain/nodes/{natural_key}` | чтение | Узел и соседи |
| `GET /api/brain/sources/{natural_key}` | чтение | Оригинал документа и provenance |
| `DELETE /api/brain/nodes/{natural_key}` | запись | Удалить узел с аудитом |
| `GET /api/brain/stats` | глобальный грант | Статистика инстанса |
| `POST /api/brain/retain` (`/retain`) | запись | Статья или заметка |
| `POST /api/brain/facts` | запись | Узел с ключом и свойствами |
| `POST /api/brain/documents` | запись | Документ готовыми фрагментами |
| `DELETE /api/brain/documents/{natural_key}` | запись | Удалить документ |
| `POST /api/brain/audit` (`/audit`) | запись | Событие аудита |
| `GET /api/brain/trace/{trace_id}` | чтение | Подграф трейса |
| `POST /api/memory/observations` | запись | Принять наблюдение |
| `POST /api/memory/observations:batch` | запись | Пакет наблюдений |
| `GET /api/memory/observations` | чтение | Свежие наблюдения и статусы |
| `GET /api/memory/observations/{id}` | чтение | Наблюдение по id |
| `DELETE /api/memory/observations/{id}` | запись | Redact или purge |
| `POST /api/memory/consolidate` | запись | Повторная обработка наблюдений |
| `POST /api/memory/context` | чтение | Собрать ContextPack |
| `GET /api/memory/context/trace/{trace_id}` | чтение | Трейс компиляции |
| `POST /api/memory/context/typed` | чтение | Типизированный обход |
| `POST /api/memory/packages` | service scope | Зарегистрировать доменный пакет |
| `GET /api/memory/packages` | любой токен* | Список пакетов |
| `GET /api/memory/packages/{name}` | любой токен* | Версия пакета |
| `GET /api/memory/namespaces/{ns}/kinds` | чтение* | Каталог видов namespace |
| `PUT /api/memory/namespaces/{ns}/kinds` | запись* | Строгий режим и пакеты namespace |
| `POST /api/memory/reconcile` | запись* | Сверить снимок источника |

\* При включённом ограничении маршрутов ядра (`CB_CORE_ONLY` / `CB_CORE_IDENTITIES`)
дополнительно требуется identity ядра — см.
[Namespaces и доступ](namespaces.md#core-routes).

Маршруты с путём `{natural_key}` принимают ключи со слэшами (например, URL) без
экранирования.

## Служебные маршруты

### GET /healthz

```bash
curl -fsS "$MEMORY_URL/healthz"
```

```json
{"ok": true, "graph": "company_brain", "nodes": 123, "chunks": 456}
```

`503` — БД недоступна. `GET /api/brain/health` возвращает то же, но требует валидный
токен — удобно для проверки конфигурации клиента.

### GET /api/brain/stats

Узлы и рёбра по типам и число фрагментов по всему инстансу:
`{"nodes_by_type": {...}, "edges_by_type": {...}, "chunks": N}`. Доступно только
вызывающим без ограничения по namespaces (ключ с грантом на пустой префикс или
legacy-ключ); IAM-токену — `403`.

## Чтение: `/api/brain/*`

### POST /api/brain/query

| Поле | Тип | По умолчанию | Смысл |
|---|---|---|---|
| `question` | string | — | Вопрос |
| `k` | int | 8 | Сколько фрагментов вернуть |
| `hops` | int | 1 | Глубина соседей по графу (1–2) |
| `synthesize` | bool | `CB_QUERY_SYNTHESIZE_DEFAULT` | Сгенерировать ответ LLM |
| `scope` | object | namespace по умолчанию | `{"namespace": "…"}` или `{"namespaces": [...]}` |
| `allowedNamespaces`, `allowedScopes` | string[] | — | Сужение видимости |

Ответ при `synthesize: false`:

```json
{
  "question": "…", "scope": {"namespace": "support"}, "synthesized": false,
  "hits": [{"chunk_id": 1, "node_key": "…", "source_path": "…", "title": "…",
            "heading": "…", "text": "…", "score": 0.0325, "namespace": "support",
            "meta": {}, "rerank_score": null}],
  "neighbors": [{"natural_key": "…", "type": "…", "title": "…", "source_path": "…"}],
  "sources": [{"source_path": "…", "node_key": "…", "title": "…"}],
  "context": "# Найденные фрагменты…"
}
```

При `synthesize: true` ответ содержит `answer` (текст), `sources`, а `hits` и
`neighbors` — **числа** найденных фрагментов и соседей (поля `context` нет).

### POST /api/brain/recall

| Поле | По умолчанию | Смысл |
|---|---|---|
| `query` | — | Запрос |
| `budget` | `mid` | `low` (4), `mid` (8), `high` (16) фрагментов |
| `hops` | 1 | Глубина соседей |
| `scope`, `allowedNamespaces`, `allowedScopes` | — | Как у `query` |

```bash
curl -X POST "$MEMORY_URL/api/brain/recall" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"query": "не приходит уведомление", "budget": "low",
       "scope": {"namespace": "support"}}'
```

Ответ: `query`, `budget`, `scope`, `count`, `memories[]` (`node_key`, `title`,
`heading`, `source_path`, `text`, `namespace`), `sources`, `neighbors`, `context`.

### POST /api/brain/search

| Поле | Смысл |
|---|---|
| `query` | Запрос (в структурном режиме может быть пустым) |
| `filters.type` | Включает структурный режим: список узлов этого типа |
| `filters.status` | Фильтр по статусу узла (структурный режим) |
| `filters.limit` | Размер выдачи, по умолчанию 20 |
| `filters.meta` | Фильтр по тегам фрагментов (семантический режим) |
| `scope`, `allowedNamespaces`, `allowedScopes` | Как у `query` |

Семантический режим: `{"mode": "semantic", "count", "results": [{node_key, title,
source_path, text, namespace, meta}], "sources"}`. Структурный:
`{"mode": "structural", "count", "results": [<узлы>]}`.

### GET /api/brain/nodes

Query-параметры: `type`, `status`, `limit` (1–500, по умолчанию 50), `namespace`.
Ответ: `{"count": N, "nodes": [...]}`.

### GET /api/brain/nodes/{natural_key}

Query-параметры: `hops` (1–2), `namespace`. Ответ: `{"node": {...}, "neighbors": [...]}`;
`404`, если узла нет в этом namespace.

### GET /api/brain/sources/{natural_key}

Query-параметр: `namespace`. Ответ `200`:

```json
{
  "natural_key": "…", "namespace": "support", "type": "article", "title": "…",
  "content": "полный текст, как был загружен",
  "content_source": "original",
  "chunks": 3,
  "provenance": {"source": "…", "source_path": "…", "origin": "agent",
                 "actor": "kb-import", "actor_id": null, "trace_id": null,
                 "issue_id": null, "confidence": 0.9, "last_seen": "…",
                 "metadata": {}},
  "pii": false, "pii_categories": []
}
```

`content_source: "chunks"` — оригинала в узле нет, текст склеен из фрагментов.

### GET /api/brain/trace/{trace_id}

Query-параметр: `namespace`. Возвращает подграф трейса в аудит-контуре namespace:

```json
{"trace_id": "…", "anchor": "pc-trace:…", "events": [...], "facts": [...],
 "event_count": 2, "fact_count": 1}
```

## Запись: `/api/brain/*`

Подробное поведение полей — в [Загрузке знаний](ingestion.md).

### POST /api/brain/retain

Поля: `content` (обязательно), `type` (`note`), `title`, `external_id`, `provenance`,
`links`, `confidence` (0.8), `pii`, `pii_categories`, `scope`. Ответ `201`:
`{"retained": true, "type", "title", "natural_key", "namespace", "origin": "agent",
"edges", "trace"}` и `pii_categories`, если ПДн обнаружены.

### POST /api/brain/facts

Поля: `natural_key`, `type`, `title` (обязательно), `properties`, `links`, `run_id`,
`confidence` (0.8), `scope`. Ответ `201`:
`{"natural_key", "namespace", "origin": "agent", "edges", "trace"}`.

### POST /api/brain/documents

Поля: `natural_key`, `title` (обязательно), `type` (`document`), `namespace` или
`scope.namespace`, `source_path`, `properties`, `meta`, `links`, `chunks[]`
(`text`, `heading`, `order`; до 500), `replace` (`true`), `pii`, `pii_categories`.
Ответ `201`: `{"natural_key", "namespace", "type", "chunks", "replaced"}` и
`pii_categories` при обнаружении ПДн. `400` — больше 500 фрагментов или разные
`namespace` и `scope.namespace`.

### DELETE /api/brain/documents/{natural_key}

Query: `namespace`, `actor` (`api`), `trace_id`. Ответ `200`:
`{"natural_key", "namespace", "deleted": true|false, "chunks_deleted", "trace_id"}`.
Повторное удаление — не ошибка (`deleted: false`).

### DELETE /api/brain/nodes/{natural_key}

Query: `namespace`, `actor` (`api`), `trace_id` (иначе `X-Run-Id`, иначе генерируется).
Ответ `200`: `{"deleted": true, "natural_key", "type", "title", "chunks_deleted",
"trace_id"}`. `404` — узла нет (в том числе при повторном вызове), `400` — узел
аудит-контура.

### POST /api/brain/audit

```json
{"trace_id": "run-42", "action": "answer.sent", "actor": "answer-bot",
 "actor_id": "…", "actor_kind": "agent", "payload": {"ticket": "…"},
 "ts": "2026-09-01T10:00:00Z", "run_id": "…", "scope": {"namespace": "support"}}
```

Ответ `201`: `{"recorded": true, "natural_key", "namespace", "trace", "action", "ts"}`.

## Персональные данные {#pii}

Защита включается `CB_PII_PROTECTION=true`. Тогда:

- **Маскированная выдача.** У вызывающего без допуска во всех полях `text`, `context`,
  `content`, `title`, `answer`, `heading` (на любой глубине ответа) обнаруженные ПДн
  заменяются масками `[ПДн:phone]`, `[ПДн:email]`, `[ПДн:passport_rf]`,
  `[ПДн:snils]`, `[ПДн:card]`, `[ПДн:inn]`, а ответ получает `"pii_masked": true`.
- **Допуск.** Полный допуск дают ключи `CB_SERVER_API_KEYS_PII`, ключи реестра с
  `"pii": true` и IAM-токены со scope `memory:pii`.
- **Журнал доступа.** Выдача немаскированных ПДн вызывающему с допуском фиксируется
  событием `pii_access` (маршрут и категории) в аудит-контуре namespace. Передавайте
  `X-Run-Id`, чтобы связать событие с вашей операцией.
- **Маркировка при записи.** `retain` и `documents` помечают узел по автодетекции и
  явной метке и возвращают итоговый `pii_categories`.
- **Уничтожение по требованию** — штатный `DELETE` с аудитом.

Маскирование выполняется по шаблонам на выдаче, поэтому работает и для
непомеченных при записи данных. ФИО и адреса детектор не распознаёт.

## Context Memory Engine: `/api/memory/*`

Авторизация, гранты, видимость и защита ПДн — те же, что у `/api/brain/*`.

### POST /api/memory/observations

Тело — наблюдение (см. [Загрузку знаний](ingestion.md#observations)) плюс
`scope.namespace`. Ответ `201`:
`{"observation_id": "obs-…", "duplicate": false, "status": "processed"}`.
`400` — невалидное наблюдение.

### POST /api/memory/observations:batch

```json
{"observations": [{...}, {...}], "scope": {"namespace": "tenant:<tenant-id>"}}
```

Ответ `207`: `results[]` (у каждого `observation_id` или `error`), `accepted`,
`duplicates`, `failed`. Больше `CB_OBSERVATIONS_MAX_BATCH` → `413`.

### GET /api/memory/observations

Query: `namespace`, `kind`, `status`, `limit` (1–500, по умолчанию 50). Ответ:
`{"count", "observations": [...], "statuses": {"processed": N, "failed": M, …}}`.

### GET /api/memory/observations/{id}

Query: `namespace`. `404`, если нет.

### DELETE /api/memory/observations/{id}

Query: `namespace`, `mode` (`redact` по умолчанию | `purge`), `actor` (`api`),
`trace_id`. Ответ `200`: `{"deleted": true, …}`; `404`, если нет.

### POST /api/memory/consolidate

Повторная обработка необработанных наблюдений — идемпотентно. Тело — объект
namespace записи (`{"namespace": "support"}`), query-параметр `limit` (1–5000, по
умолчанию 500).

```bash
curl -X POST "$MEMORY_URL/api/memory/consolidate?limit=500" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"namespace": "support"}'
```

### POST /api/memory/context

Тело — `ContextRequest` (`query`, `scopes`, `anchors`, `subject`,
`ephemeral_context`, `budget.tokens` или `max_tokens`, `strategy`, `as_of`, `k`) плюс
`scope` и необязательные `allowedNamespaces`/`allowedScopes`. Поля принимаются и в
camelCase (`ephemeralContext`, `maxTokens`, `asOf`). Неизвестная `strategy` → `400`.
Ответ — `ContextPack`: `query`, `sections[]`, `sources`, `token_estimate`, `budget`,
`conflicts`, `trace_id`, `stats`. Подробно — в
[Поиске и сборке контекста](retrieval.md#context-compiler).

### GET /api/memory/context/trace/{trace_id}

Query: `namespace`. Трейс компиляции; `404`, если нет.

### POST /api/memory/context/typed

Тело: `anchors[]` (`{kind?, value}`), `traverse[]` (`relation`, `direction`,
`depth`, `limit`, `from`), `as_of`, `allow_semantic`, `scope`, `allowedNamespaces`,
`allowedScopes`. См. [Типизированный обход](retrieval.md#typed). `400` — неизвестный
пакет или некорректный запрос.

## Доменные пакеты и снимки

### POST /api/memory/packages

Регистрация версии доменного пакета. Нужен service scope (ключ с `"service": true`,
IAM `memory:service`, ключ с грантом записи на пустой префикс или legacy-ключ).

```json
{
  "name": "code",
  "version": 1,
  "kinds": [
    {"kind": "component", "naturalKey": "<repo>"},
    {"kind": "source_file", "naturalKey": "<repo>:<path>"},
    {"kind": "endpoint",
     "naturalKey": "<METHOD> <path с параметрами как {}>",
     "aliases": ["<path с исходными именами параметров>"],
     "kindAliases": ["route"],
     "idPatterns": ["\\b(?:GET|POST|PUT|PATCH|DELETE)\\s+/[\\w{}./:-]+"],
     "attributes": {"type": "object", "properties": {"method": {"type": "string"}}}},
    {"kind": "ui_call", "naturalKey": "<repo>:<path>:<line>"}
  ],
  "relations": [
    {"relation": "defined_in", "fromKinds": ["endpoint", "ui_call"], "toKinds": ["source_file"]},
    {"relation": "part_of", "fromKinds": ["source_file"], "toKinds": ["component"]},
    {"relation": "calls", "fromKinds": ["ui_call"], "toKinds": ["endpoint"]}
  ]
}
```

| Код | Смысл |
|---|---|
| `201` | Версия создана |
| `200` | Та же версия с тем же содержимым уже есть |
| `409` | Версия уже зарегистрирована с **другим** содержимым (версия неизменяема) |
| `400` | Пакет некорректен |
| `403` | Нет service scope (или не identity ядра при ограничении) |

`version` — строка или число (`1` хранится как `"1"`). `naturalKey` — JSON Schema
ключа (`type`, `pattern`, `minLength`, `maxLength`, `enum`) или шаблон с
плейсхолдерами `<name …>` / `{name}`. `cardinality` связи — `many` (по умолчанию) или
`one`: при `one` смена объекта при сверке закрывает старый факт.

`GET /api/memory/packages` — список пакетов с версиями;
`GET /api/memory/packages/{name}?version=…` — версия (по умолчанию последняя), `404`
если нет.

### GET/PUT /api/memory/namespaces/{namespace}/kinds

```json
{"strict": true, "packages": ["code@1"]}
```

`packages` — какие пакеты действуют в namespace: `name` — последняя версия,
`name@version` — закреплённая; `null` — только встроенный `default`. `PUT` требует
права записи в namespace, `GET` — чтения. Ответ обоих:
`{"settings": {...}, "catalog": {...}}` — настройка и действующий каталог видов.

### POST /api/memory/reconcile {#reconcile}

Тело — документ снимка плюс namespace (поле `namespace` или `?namespace=`) и
необязательные `scopes` видимости, которые пишутся на все узлы и связи снимка.

```json
{
  "pack": "code@1",
  "source": "git:web-app",
  "scope": "web-app",
  "snapshotId": "web-app@9ab1c2d",
  "observedAt": "2026-09-23T08:47:12+00:00",
  "entities": [
    {"kind": "ui_call", "key": "web-app:src/runs/page.tsx:38",
     "title": "/runs/${id}/checkpoints (src/runs/page.tsx:38)",
     "attributes": {"queryParams": ["limit"]},
     "provenance": {"repo": "web-app", "sha": "9ab1c2d",
                    "path": "src/runs/page.tsx", "line": 38}}
  ],
  "relations": [
    {"relation": "calls",
     "from": {"kind": "ui_call", "key": "web-app:src/runs/page.tsx:38"},
     "to": {"kind": "endpoint", "key": "GET /api/v1/runs/{}/checkpoints"}}
  ],
  "namespace": "tenant:<tenant-id>:ws:<workspace-id>",
  "scopes": ["workspace:<workspace-id>"]
}
```

!!! note "Два разных `scope`"
    В снимке `scope` — **строка**, часть идентичности источника (`source` + `scope`).
    Namespace передаётся отдельным полем `namespace`.

Ответ:

```json
{"source": "git:web-app", "scope": "web-app", "namespace": "…",
 "snapshot_id": "web-app@9ab1c2d", "observed_at": "2026-09-23T08:47:12Z",
 "pack": "code@1", "opened": 2, "closed": 0, "unchanged": 0, "superseded": 0,
 "entities": {"opened": 1, "closed": 0, "unchanged": 0, "superseded": 0},
 "relations": {"opened": 1, "closed": 0, "unchanged": 0, "superseded": 0,
               "pending": 1, "resolved": 0, "retried": 0},
 "duplicate": false}
```

| Код | Смысл |
|---|---|
| `200` | Сверка выполнена (или повтор с `duplicate: true`) |
| `400` | Некорректный снимок, пакет не включён в namespace, разные namespace в query и теле |
| `409` | Снимок старше последнего принятого для `(source, scope)` |
| `422` | Сущность или связь вне схемы в строгом namespace |

Ключ сущности обязателен либо собирается шаблоном `naturalKey` вида. `provenance`
`{repo, sha, path, line}` превращается в цитату `repo@sha:path:line`.

## MCP-сервер

`platform-memory-mcp` поднимает MCP-сервер поверх того же движка — stdio для
локального использования или streamable HTTP с проверкой ключа. Инструменты:

| Инструмент | Назначение |
|---|---|
| `query_graph` | Поиск по графу |
| `get_node` | Узел по ключу |
| `get_neighbors` | Соседи узла |
| `get_community` | Узлы сообщества (кластера) |
| `shortest_path` | Кратчайший путь между узлами |
| `build_context` | Собрать ContextPack |
| `remember_observation` | Записать наблюдение |

## Клиентская библиотека

`platform-memory-client` (каталог `services/memory-service/client`) — канонический
HTTP-клиент: `MemoryClient` (sync) и `AsyncMemoryClient` (asyncio) над
`/api/brain/*` и `/api/memory/*`. Зависимости — только `httpx` и `pydantic`.
Токен передаётся строкой, callable или (в async-клиенте) объектом с `async token()`,
поэтому IAM-credential с audience `memory-service` подключается напрямую.

```python
from platform_memory_client import MemoryClient

with MemoryClient("http://memory-service:8077", token=token) as mem:
    res = mem.recall("как оформить пропуск?", budget="low", namespaces=["support"])
    for m in res.memories:
        print(m.source_path, m.title)
    for src in res.sources:          # источники — словари {source_path, node_key, title}
        print(src["source_path"])
    mem.retain_document("doc:guide", "Руководство", [{"text": "…", "heading": "Введение"}],
                        namespace="support")
```

Ошибки: `MemoryServiceError` (`status_code`, `detail`, свойства `unavailable` для
`5xx` и `not_found`) и `MemoryTransportError` — ответа не было. Подробнее — в
[Клиентах SDK](../sdk/clients.md).

## См. также

- [Namespaces и доступ](namespaces.md)
- [Загрузка знаний](ingestion.md)
- [Поиск и сборка контекста](retrieval.md)
- [Коды ошибок](../reference/errors.md)
- [Сервисы и порты](../reference/services-and-ports.md)
