# Конфигурация и эксплуатация

Справочник переменных окружения memory-service (`CB_*`), их связь с переменными
корневого `.env` платформы, настройка провайдеров эмбеддингов и LLM, а также
эксплуатация: резервное копирование с Apache AGE, переиндексация, производительность
и типичные проблемы. Для администраторов.

## Как задаются настройки

Сервис читает переменные окружения с префиксом `CB_` (и файл `.env` в рабочем
каталоге процесса, если он есть). Полный список — `src/platform_memory/core/config.py`
в репозитории memory-service. В составе платформы значения задаёт блок
`memory-service` `deploy/local/compose.yml`, часть из них — через переменные корневого
`.env`:

| Переменная `.env` | По умолчанию | Во что превращается |
|---|---|---|
| `MEMORY_POSTGRES_PASSWORD` | — (обязательно) | Пароль `memory-db`, часть `CB_DATABASE_URL` |
| `MEMORY_API_KEY` | — (обязательно) | `CB_SERVER_API_KEY`; им же ядро ходит в память до bootstrap |
| `MEMORY_EMBEDDING_PROVIDER` | `fake` | `CB_EMBEDDING_PROVIDER` |
| `MEMORY_EMBEDDING_MODEL` | `text-embedding-3-small` | `CB_EMBEDDING_MODEL` |
| `MEMORY_LLM_PROVIDER` | `echo` | `CB_LLM_PROVIDER` |
| `LLM_BASE_URL` | см. `.env.example` | `CB_EMBEDDING_BASE_URL` и `CB_LLM_BASE_URL` |
| `LLM_API_KEY` | — | `CB_EMBEDDING_API_KEY` и `CB_LLM_API_KEY` |
| `LLM_MODEL` | см. `.env.example` | `CB_LLM_MODEL` |
| `MEMORY_RERANK_ENABLED` | `false` | `CB_RERANK_ENABLED` |
| `MEMORY_CONSOLE_ENABLED` | `false` | `CB_CONSOLE_ENABLED` |
| `MEMORY_IAM_ENABLED` | `true` | `CB_IAM_ENABLED` |
| `MEMORY_POLICY_ENABLED` | `false` | `CB_POLICY_ENABLED` |
| `TAIMEN_PUBLIC_URL` | — | `CB_IAM_ISSUER` = `${TAIMEN_PUBLIC_URL}/iam` |
| `MEMORY_HOST_PORT` | `18001` | Порт на `127.0.0.1` хоста |
| `MEMORY_MEM_LIMIT` / `MEMORY_DB_MEM_LIMIT` | `512m` / `512m` | Лимиты памяти контейнеров |
| `VOLUME_MEMORY_DB` | `<проект>_memory_db` | Имя тома БД |


Жёстко заданы в `deploy/local/compose.yml`: `CB_PII_PROTECTION=true`, пустой
`CB_SERVER_API_KEYS_PII`, `CB_DEFAULT_NAMESPACE=main`, `CB_EMBEDDING_DIM=1536`,
`CB_EMBEDDING_TIMEOUT=60`, `CB_RERANK_POOL=20`,
`CB_IAM_JWKS_URL=http://iam-service:8010/.well-known/jwks.json`,
`CB_IAM_AUDIENCE=memory-service`,
`CB_IAM_BASE_URL=http://iam-service:8010`. Файл `secrets/memory-service-iam.env`
(необязательный: service identity памяти для вызова внешнего PDP; кладётся вместе
с подключением PDP) добавляет `CB_IAM_CLIENT_ID` и `CB_IAM_CLIENT_SECRET`.

!!! warning "Офлайн-провайдеры по умолчанию"
    Без ключа провайдера платформа запускает память на `fake`/`echo`: всё работает,
    но поиск лексический, синтеза и реранка нет. Для реальных данных включите
    настоящий провайдер **до** загрузки знаний — иначе потребуется переиндекс.

## Справочник переменных `CB_*`

### База данных и хранилище

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CB_DATABASE_URL` | собирается из `POSTGRES_USER/PASSWORD/HOST/PORT/DB` (`brain`/`brain`/`localhost`/`5432`/`company_brain`) | Строка подключения к PostgreSQL с AGE и pgvector |
| `CB_GRAPH_NAME` | `company_brain` | Имя графа AGE |
| `CB_CHUNKS_TABLE` | `chunks` | Таблица фрагментов |
| `CB_DB_JIT` | `false` | JIT PostgreSQL для соединений сервиса (см. [Производительность](#performance)) |
| `CB_DEFAULT_NAMESPACE` | `nexus` | Namespace запросов без `scope`; задавайте явно |
| `CB_OBSERVATIONS_TABLE` | `observations` | Таблица наблюдений |
| `CB_CONTEXT_TRACES_TABLE` | `context_traces` | Таблица трейсов компиляции |
| `CB_DOMAIN_PACKS_TABLE` | `domain_packs` | Реестр доменных пакетов |
| `CB_NAMESPACE_SETTINGS_TABLE` | `namespace_settings` | Настройки видов namespace |
| `CB_SNAPSHOTS_TABLE` | `source_snapshots` | Журнал снимков (+ `<имя>_items`) |

### HTTP-сервис и аутентификация

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CB_SERVER_HOST` | `127.0.0.1` (в образе `0.0.0.0`) | Адрес прослушивания |
| `CB_SERVER_PORT` | `8077` | Порт |
| `CB_SERVER_API_KEY` | — | Статический ключ: все namespaces; при защите ПДн — маска |
| `CB_SERVER_API_KEYS_PII` | — | Ключи с полным допуском к ПДн, через запятую |
| `CB_API_KEYS` | — | JSON-реестр ключей с грантами (см. [Namespaces и доступ](namespaces.md)) |
| `CB_IAM_ENABLED` | `false` | Принимать access token IAM |
| `CB_IAM_ISSUER` | — | Точный `iss` токена |
| `CB_IAM_JWKS_URL` | — | JWKS IAM (внутренний адрес) |
| `CB_IAM_AUDIENCE` | `memory-service` | Точный `aud` |
| `CB_IAM_LEEWAY_SECONDS` | `5` | Допуск рассинхрона часов |
| `CB_CORE_ONLY` | `false` | Закрыть маршруты ядра для всех, кроме identity ядра |
| `CB_CORE_IDENTITIES` | — | Метки identity ядра через запятую; непустой список тоже включает ограничение |

### Видимость по principal (экспериментально)


| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CB_POLICY_ENABLED` | `false` | Брать видимость людей и агентов из внешнего PDP |
| `CB_POLICY_URL` | `http://localhost:8030` | Адрес PDP |
| `CB_POLICY_TIMEOUT_SECONDS` | `3.0` | Таймаут вызова |
| `CB_POLICY_CACHE_TTL_SECONDS` | `5.0` | Кэш ответа по principal |
| `CB_IAM_BASE_URL`, `CB_IAM_CLIENT_ID`, `CB_IAM_CLIENT_SECRET` | — | Service identity памяти в IAM (client credentials) |

### Эмбеддинги

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CB_EMBEDDING_PROVIDER` | `openai` | `openai` (любой OpenAI-совместимый endpoint) или `fake` |
| `CB_EMBEDDING_BASE_URL` | публичный OpenAI-совместимый шлюз (см. `config.py`) | Базовый URL endpoint'а; в инсталляции задавайте явно |
| `CB_EMBEDDING_API_KEY` | — | Обязателен для `openai` |
| `CB_EMBEDDING_MODEL` | `text-embedding-3-small` | Модель |
| `CB_EMBEDDING_DIM` | `1536` | Размерность; должна совпадать с моделью |
| `CB_EMBEDDING_TIMEOUT` | `25.0` | Таймаут вызова, секунды |

### LLM, синтез и реранкинг

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CB_LLM_PROVIDER` | `openai` | `openai` или `echo` (без генерации) |
| `CB_LLM_BASE_URL` | как у эмбеддингов | Базовый URL chat completions |
| `CB_LLM_API_KEY` | — | Обязателен для `openai` |
| `CB_LLM_MODEL` | `gpt-4o-mini` | Модель синтеза (и реранка по умолчанию) |
| `CB_QUERY_SYNTHESIZE_DEFAULT` | `false` | Значение `synthesize`, если клиент его не передал |
| `CB_RERANK_ENABLED` | `false` | Реранкинг в `query`/`recall`/`search` |
| `CB_RERANK_PROVIDER` | `llm` | Провайдер реранка |
| `CB_RERANK_POOL` | `20` | Размер пула кандидатов реранка |
| `CB_RERANK_MODEL` | — (= `CB_LLM_MODEL`) | Отдельная модель реранка |
| `CB_EXTRACT_ENTITIES` | `false` | Извлекать сущности из текста vault через LLM при `cb ingest` |

### Context Compiler и наблюдения

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CB_CONTEXT_DEFAULT_MAX_TOKENS` | `8000` | Бюджет ContextPack по умолчанию |
| `CB_CONTEXT_CHARS_PER_TOKEN` | `3.0` | Оценка размера (консервативно для кириллицы; для английского можно 4.0) |
| `CB_CONTEXT_MAX_DEPTH` | `2` | Глубина обхода графа |
| `CB_CONTEXT_MAX_NODES` | `60` | Максимум узлов обхода |
| `CB_CONTEXT_MAX_EDGES` | `120` | Максимум рёбер обхода |
| `CB_OBSERVATIONS_EMBED` | `false` | Эмбеддить `content` наблюдений |
| `CB_OBSERVATIONS_MAX_BATCH` | `500` | Максимум наблюдений в пакете |
| `CB_RECONCILE_MAX_ITEMS` | `20000` | Максимум элементов в снимке |
| `CB_RUN_AUDIT_ENABLED` | `true` | События жизненного цикла прогонов в трейс |

### Защита ПДн

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CB_PII_PROTECTION` | `false` (в платформе `true`) | Маскирование, маркировка и журнал доступа к ПДн |

### Загрузка vault (CLI)

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CB_VAULT_PATH` | — | Каталог документов для `cb ingest` |
| `CB_CACHE_DIR` | — | Кэш неизменённых заметок и эмбеддингов; пусто — выключен |
| `CB_PROJECT_VALUES` | — | Разрешённые слаги проектов (синтетические узлы `project:*`) через запятую |

### Консоль и демо-витрина {#console-demo}

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CB_CONSOLE_ENABLED` | `false` | Административная консоль `/console`; выключена — все её маршруты `404` |
| `CB_CONSOLE_NAMESPACES` | — | Список баз знаний консоли через запятую (пусто — только namespace по умолчанию) |
| `CB_DEMO_PUBLIC_ENABLED` | `false` | Публичная read-only витрина `/demo` |
| `CB_DEMO_NAMESPACE` | `demo` | Единственная база знаний витрины |
| `CB_DEMO_RATE_LIMIT` | `30` | Запросов в минуту с одного IP к `/demo/api/*` (`0` — без лимита) |
| `CB_DEMO_SEARCH_K`, `CB_DEMO_RERANK`, `CB_DEMO_MIN_CONFIDENCE` | `5`, `true`, `0.3` | Поиск витрины: top-k, собственный реранк, порог `rerank_score` |
| `CB_DEMO_BRAND_NAME`, `CB_DEMO_BRAND_TAGLINE`, `CB_DEMO_CTA_URL`, `CB_DEMO_DOMAIN` | нейтральные | Оформление витрины |

!!! danger "У консоли нет собственной аутентификации"
    `/console` вызывает движок внутри процесса и не проверяет пользователя. Включайте
    её только за reverse-прокси, который аутентифицирует администратора, либо не
    публикуйте вовсе и заходите через SSH-туннель. Витрину `/demo` не включайте на
    инсталляции с реальными данными: она предназначена для чистой синтетической базы.

## Провайдеры эмбеддингов и LLM

Сервис использует OpenAI-совместимый API через официальный клиент `openai`:
`embeddings.create` для эмбеддингов и `chat.completions.create` для синтеза и
реранка. Подходит любой endpoint с таким протоколом (облачный шлюз, локальный
сервер моделей).

=== "Боевой режим"

    ```bash
    CB_EMBEDDING_PROVIDER=openai
    CB_EMBEDDING_BASE_URL=https://llm-gateway.example.com/v1
    CB_EMBEDDING_API_KEY=<ключ>
    CB_EMBEDDING_MODEL=text-embedding-3-small
    CB_EMBEDDING_DIM=1536
    CB_EMBEDDING_TIMEOUT=60

    CB_LLM_PROVIDER=openai
    CB_LLM_BASE_URL=https://llm-gateway.example.com/v1
    CB_LLM_API_KEY=<ключ>
    CB_LLM_MODEL=<быстрая модель>
    CB_RERANK_ENABLED=true
    ```

=== "Офлайн (тесты, разработка)"

    ```bash
    CB_EMBEDDING_PROVIDER=fake
    CB_LLM_PROVIDER=echo
    CB_RERANK_ENABLED=false
    ```

=== "В корневом .env платформы"

    ```bash
    LLM_API_KEY=<ключ>
    LLM_BASE_URL=https://llm-gateway.example.com/v1
    LLM_MODEL=<быстрая модель>
    MEMORY_EMBEDDING_PROVIDER=openai
    MEMORY_LLM_PROVIDER=openai
    MEMORY_RERANK_ENABLED=true
    ```

Рекомендации по выбору:

- **Эмбеддинги** должны поддерживать русский язык. Размерность `CB_EMBEDDING_DIM`
  обязана совпадать с размерностью модели; для моделей семейства
  `text-embedding-3-*` сервис передаёт `dimensions` и может получить укороченный
  вектор.
- **Таймаут эмбеддингов** увеличивайте, если провайдер даёт редкие пики задержки
  (в платформе — 60 с). Эмбеддинг — первый шаг каждого поиска: без таймаута
  зависший провайдер держит обработчик.
- **Модель синтеза и реранка** выбирайте по задержке: реранк — один вызов на поиск
  с таймаутом 12 с, синтез — с таймаутом 25 с. Реранк требует, чтобы модель
  надёжно возвращала JSON; при неполном ответе поиск тихо откатывается к порядку RRF.
- Отдельную модель для реранка задавайте `CB_RERANK_MODEL`.

## Эксплуатация

### Ресурсы и размещение

- Сервис stateless, всё состояние — в `memory-db`. Порт наружу не публикуется:
  в `deploy/local/compose.yml` он привязан к `127.0.0.1`, а платформа вызывает память по
  внутреннему адресу.
- Схема (граф, таблицы, индексы) создаётся и доводится идемпотентно при старте
  сервиса; миграции аддитивны, отдельных шагов при обновлении не требуют.
- Образ `memory-db` собран на официальном образе Apache AGE для PostgreSQL 16 с
  pgvector; init-скрипт при первом создании тома ставит расширения `age`, `vector`,
  `pg_trgm` и создаёт граф `company_brain`. Без прав на `CREATE EXTENSION pg_trgm`
  поиск идентификаторов работает последовательным `ILIKE` — корректно, но медленнее.

### Производительность {#performance}

| Настройка / особенность | Почему важно |
|---|---|
| `CB_DB_JIT=false` (по умолчанию) | AGE отдаёт планировщику завышенные оценки кардинальности, и JIT PostgreSQL компилирует каждый графовый запрос заново — это основная доля времени обхода графа. Сервис открывает сессии с `-c jit=off`; явно заданный `options` в `CB_DATABASE_URL` не перетирается |
| Соединение на запрос | Пула соединений нет: каждый HTTP-запрос открывает своё соединение. Для внешнего пулера, не поддерживающего `options`, задайте параметры сессии в самой строке подключения |
| Индексы | HNSW по эмбеддингам, GIN по полнотекстовому документу, GIN по `meta`, триграммы по тексту, GIN/hash-индексы меток графа |
| Таймауты провайдеров | Эмбеддинг `CB_EMBEDDING_TIMEOUT`, реранк 12 с, синтез 25 с — зависший провайдер не держит запрос бесконечно |
| Реранк и синтез | Каждый добавляет вызов LLM к задержке запроса |
| Rate limiting | На уровне API нет (кроме витрины `/demo`) — массовую загрузку ведите последовательно |

Для замеров в репозитории memory-service есть `benchmarks/bench.py` (скорость загрузки
и задержки каналов поиска на синтетических наборах) — он запускается против
отдельной одноразовой БД.

### Резервное копирование и восстановление

Вся память — в одной БД `memory-db`, поэтому бэкап — это `pg_dump`:

```bash
tools/compose exec -T memory-db \
  pg_dump -U memory -d company_brain -Fc > memory-$(date +%Y%m%d-%H%M).dump
```

Восстановление — на свежий том, где init-скрипт уже создал расширения:

```bash
tools/compose stop memory-service
tools/compose exec -T memory-db \
  pg_restore -U memory -d company_brain --clean --if-exists < memory-XXXX.dump
```

!!! danger "После восстановления графа AGE нужно исправить OID"
    Apache AGE хранит в каталоге `ag_catalog` настоящие OID PostgreSQL. Колонка
    `ag_graph.namespace` имеет тип `regnamespace` и при восстановлении получает
    правильное значение, а `ag_graph.graphid` и `ag_label.graph` — обычные `oid` и
    приезжают со **старого** кластера. Сервис после этого падает с ошибкой вида
    `graph with oid NNNNN does not exist`.

Проверка — у согласованного графа `graphid` совпадает с OID его схемы:

```sql
SELECT name, graphid, namespace::oid AS schema_oid
FROM ag_catalog.ag_graph;
```

Исправление — одной транзакцией. Порядок важен: сначала снять внешний ключ, затем
обновить `ag_label` (пока в `ag_graph` ещё старые `graphid`), затем `ag_graph`, и
вернуть ключ — он же и проверит результат:

```sql
BEGIN;
ALTER TABLE ag_catalog.ag_label DROP CONSTRAINT fk_graph_oid;

UPDATE ag_catalog.ag_label AS l
SET graph = g.namespace::oid
FROM ag_catalog.ag_graph AS g
WHERE l.graph = g.graphid;

UPDATE ag_catalog.ag_graph
SET graphid = namespace::oid;

ALTER TABLE ag_catalog.ag_label
  ADD CONSTRAINT fk_graph_oid FOREIGN KEY (graph)
  REFERENCES ag_catalog.ag_graph (graphid);
COMMIT;
```

Затем запустите сервис и проверьте:

```bash
tools/compose start memory-service
curl -fsS http://127.0.0.1:18001/healthz        # nodes и chunks > 0
curl -fsS -X POST http://127.0.0.1:18001/api/brain/recall \
  -H "Authorization: Bearer $MEMORY_API_KEY" -H "Content-Type: application/json" \
  -d '{"query": "контрольный вопрос", "budget": "low", "scope": {"namespace": "<ns>"}}'
```

!!! warning "Дампы содержат данные клиентов, включая ПДн"
    Храните их в контуре инсталляции по её политике и не выносите наружу. Общие
    правила бэкапа платформы — в [Резервном копировании](../operations/backup.md).

### Смена модели эмбеддингов и переиндекс {#reindex}

Векторы разных моделей несовместимы, а размерность колонки `embedding` фиксируется
при создании таблицы. Сервис защищается от смешения:

- если таблица создана с другой размерностью, запись и поиск падают с ошибкой,
  называющей обе размерности;
- если провайдер вернул вектор не той размерности, запись отвергается.

Встроенной команды «пересчитать эмбеддинги» для данных, загруженных через API, нет.
Порядок смены модели:

1. Сделайте бэкап БД.
2. Остановите запись в память (интеграции, `context-adapter`).
3. Поменяйте `CB_EMBEDDING_MODEL` и, если нужно, `CB_EMBEDDING_DIM`.
4. Если размерность изменилась — удалите таблицу фрагментов (её пересоздаст сервис
   при старте). Это **удаляет все фрагменты всех namespaces**:
   ```sql
   DROP TABLE public.chunks;
   ```
5. Перезапустите сервис и заново загрузите знания из источников: `retain` и
   `documents` идемпотентны по ключам и заменят фрагменты; vault —
   `cb ingest --vault …` (флаг `--reset` пересоздаёт и граф, и индекс целиком).
6. Если размерность не менялась, но модель другая, старые фрагменты формально
   валидны, но их векторы несравнимы с новыми — перезагрузите все документы так же.

То же относится к данным, загруженным при `CB_EMBEDDING_PROVIDER=fake`.

### Обновление

```bash
tools/compose build memory-service
tools/compose up -d memory-service
curl -fsS http://127.0.0.1:18001/healthz
```

Новые таблицы и индексы создаются при старте. Общий порядок обновления платформы —
в [Обновлениях](../operations/upgrades.md).

### Мониторинг и диагностика

| Что смотреть | Как |
|---|---|
| Живость и доступность БД | `GET /healthz` (без токена), `503` — БД недоступна; healthcheck контейнера бьёт в `127.0.0.1:8077/healthz` |
| Валидность токена клиента | `GET /api/brain/health` |
| Проекция наблюдений | `GET /api/memory/observations?namespace=…&status=failed`; повтор — `POST /api/memory/consolidate` |
| Почему собран такой контекст | `GET /api/memory/context/trace/{trace_id}` |
| След операции (запись, удаление, доступ к ПДн) | `GET /api/brain/trace/{trace_id}?namespace=…` |
| Логи | `tools/compose logs -f memory-service` |

## Типичные проблемы

| Симптом | Причина | Что делать |
|---|---|---|
| Поиск находит только точные слова | `CB_EMBEDDING_PROVIDER=fake` | Включить настоящий провайдер и переиндексировать |
| `500` с «размерность … CB_EMBEDDING_DIM» | Модель и `CB_EMBEDDING_DIM` расходятся с таблицей | См. [переиндекс](#reindex) |
| `graph with oid … does not exist` после восстановления | OID каталога AGE со старого кластера | Процедура исправления OID выше |
| `401` на валидный IAM-токен | Не совпадает `iss` (`CB_IAM_ISSUER`) или `aud`; токен выпущен не на `memory-service` | Сверить issuer с публичным адресом IAM, обменять PAT на audience `memory-service` |
| `503` на запросы с IAM-токеном | JWKS недоступен или `CB_IAM_JWKS_URL` пуст | Проверить внутренний адрес IAM |
| `403` «Нет прав на namespace» | Запрос без `scope` попал в namespace по умолчанию, или грант не покрывает базу | Передавать `scope` явно, проверить гранты |
| `403` на `packages`/`reconcile` | Включено ограничение маршрутов ядра | Вызывать через Control Plane или identity ядра |
| `500` на каждый запрос с токеном | Невалидный JSON в `CB_API_KEYS` | Исправить конфигурацию |
| В ответах `[ПДн:…]` | Токен без допуска при `CB_PII_PROTECTION=true` | Выдать ключ с `"pii": true` или scope `memory:pii`, если это оправдано |
| Реранк «не работает», `rerank_score: null` | `CB_LLM_PROVIDER=echo`, пустой ключ или модель не вернула корректный JSON | Проверить провайдер LLM и модель |
| Медленный обход графа | Включён JIT (`CB_DB_JIT=true` или `options` в URL) | Вернуть `jit=off` |

Больше сценариев — в [Типичных проблемах с памятью](../troubleshooting/memory.md).

## См. также

- [Namespaces и доступ](namespaces.md)
- [Поиск и сборка контекста](retrieval.md)
- [Переменные окружения](../reference/environment.md)
- [Сервисы и порты](../reference/services-and-ports.md)
- [Резервное копирование](../operations/backup.md)
- [Развёртывание](../operations/deployment.md)
