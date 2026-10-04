# Конфигурация

Справочник настроек Control Plane: все переменные `CP_*` сервера с
умолчаниями из `control_plane/config.py`, переменные уровня `deploy/local/compose.yml` и
переменные `CONTROL_PLANE_*` клиентских инструментов (CLI, MCP-сервер, SDK).
Статья для тех, кто разворачивает и сопровождает Control Plane.

## Как читаются настройки

- Все настройки сервера — поля класса `Settings` (pydantic-settings) с
  префиксом `CP_`. Регистр имени переменной не важен.
- Источники: переменные окружения процесса и файл `.env` в рабочем каталоге
  процесса. Переменные окружения важнее файла.
- **Списки задаются JSON-массивом**, например
  `CP_CORS_ORIGINS='["https://platform.example.com"]'`. Строка через запятую
  не распарсится.
- Одни и те же настройки читают три процесса из одного образа:

| Процесс | Команда | Сервис в `deploy/local/compose.yml` |
|---|---|---|
| API | `alembic upgrade head && uvicorn control_plane.main:app --host 0.0.0.0 --port 8000` | `control-plane-api` |
| Worker | `python -m control_plane.worker` | `control-plane-worker` |
| Context-adapter | `python -m control_plane.worker.context_adapter` | `context-adapter` |

!!! warning "Незаконченная конфигурация валит старт"
    Процесс не стартует, если режим включён наполовину:
    `CP_IAM_ENABLED=true` без `CP_IAM_ISSUER` или `CP_IAM_JWKS_URL`;
    `CP_ENTITLEMENT_ENABLED=true`, `CP_AUTHZ_MODE=shadow|policy` или
    `CP_CONTEXT_AUTH=iam` без `CP_IAM_CLIENT_ID` и `CP_IAM_CLIENT_SECRET`;
    неизвестное значение `CP_AUTHZ_MODE`, `CP_CONTEXT_PROVIDER` или
    `CP_CONTEXT_AUTH`. Молча откатиться в предыдущий режим было бы хуже.

## Основные

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CP_ENV` | `dev` | метка окружения |
| `CP_DATABASE_URL` | `postgresql+psycopg://control_plane:control_plane@localhost:5433/control_plane` | строка подключения к PostgreSQL (драйвер psycopg 3, async) |
| `CP_LOG_LEVEL` | `INFO` | уровень структурированного JSON-лога |
| `CP_BOOTSTRAP_TOKEN` | — | токен `POST /api/v1/bootstrap`; не задан — endpoint выключен (`403 bootstrap_disabled`) |
| `CP_CORS_ORIGINS` | `[]` | разрешённые origins; пустой список — CORS выключен |
| `CP_MAX_BODY_BYTES` | `1048576` (1 МиБ) | предельный размер тела запроса, больше — `413 request_too_large` |
| `CP_KNOWLEDGE_SNAPSHOT_MAX_BODY_BYTES` | `8388608` (8 МиБ) | предел тела только для `POST /api/v1/knowledge/snapshots` |
| `CP_KNOWLEDGE_PACK_ADMINS` | `[]` | id principal (Control Plane или IAM), которым разрешён `POST /api/v1/knowledge/packs`; пустой список закрывает endpoint |

## Аренды: сессии и claims

TTL, переданный клиентом, зажимается в границы `[MIN, MAX]`. Если клиент TTL не
передал, берётся значение по умолчанию.

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CP_SESSION_TTL_SECONDS` | `300` | TTL сессии по умолчанию |
| `CP_SESSION_TTL_MIN_SECONDS` | `10` | нижняя граница |
| `CP_SESSION_TTL_MAX_SECONDS` | `3600` | верхняя граница |
| `CP_CLAIM_TTL_SECONDS` | `300` | TTL claim по умолчанию |
| `CP_CLAIM_TTL_MIN_SECONDS` | `10` | нижняя граница; ею же ограничен lease вызова скилла |
| `CP_CLAIM_TTL_MAX_SECONDS` | `3600` | верхняя граница |

## Идемпотентность

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CP_IDEMPOTENCY_TTL_SECONDS` | `86400` | сколько хранится ответ по `Idempotency-Key` |
| `CP_IDEMPOTENCY_WAIT_TIMEOUT_SECONDS` | `10.0` | сколько параллельный дубль ждёт первый запрос, потом `409 idempotency_in_flight` |
| `CP_IDEMPOTENCY_PENDING_TTL_SECONDS` | `60` | сколько живёт запись без сохранённого ответа (исполнитель упал) |

## Realtime, worker, outbox

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CP_WS_POLL_INTERVAL_SECONDS` | `5.0` | период опроса журнала WebSocket-ом, если NOTIFY потерян |
| `CP_WORKER_POLL_INTERVAL_SECONDS` | `1.0` | период цикла worker'а |
| `CP_OUTBOX_BATCH_SIZE` | `50` | записей outbox за цикл |
| `CP_OUTBOX_MAX_ATTEMPTS` | `8` | попыток доставки до dead-letter |
| `CP_OUTBOX_LOCK_TIMEOUT_SECONDS` | `60` | блокировка записи outbox |
| `CP_OUTBOX_BACKOFF_BASE_SECONDS` | `2.0` | база экспоненциального backoff |
| `CP_OUTBOX_BACKOFF_MAX_SECONDS` | `300.0` | потолок backoff |
| `CP_APPROVAL_OUTCOME_DEFER_SECONDS` | `15.0` | через сколько повторить исход approval, если цель занята живым claim |
| `CP_API_KEY_LAST_USED_REFRESH_SECONDS` | `60` | не чаще этого обновлять `last_used_at` legacy-ключа |
| `CP_JOURNAL_RETENTION_MIN_AGE_SECONDS` | `2592000` (30 суток) | минимальный возраст события для архивации и очистки журнала |

Worker доставляет outbox, пожинает просроченные сессии, claims и lease
вызовов скиллов, чистит записи идемпотентности и исполняет исходы approvals.
Для корректности он не обязателен: аренды пожинаются и лениво, самими
командами. Но без него не будут исполняться исходы approvals и доставляться
outbox.

## Память (context provider и context-adapter)

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CP_CONTEXT_PROVIDER` | `none` | `none` — без памяти (Control Plane автономен, readiness от памяти не зависит); `http` — memory-service |
| `CP_CONTEXT_BASE_URL` | `http://localhost:8077` | адрес memory-service |
| `CP_CONTEXT_API_KEY` | — | статический Bearer к memory-service |
| `CP_CONTEXT_AUTH` | `auto` | `api_key`, `iam` или `auto` (`iam`, если задан service account, иначе `api_key`) |
| `CP_CONTEXT_IAM_AUDIENCE` | `memory-service` | audience токена service account |
| `CP_CONTEXT_IAM_SCOPES` | `["memory:read","memory:write","memory:tenants","memory:service"]` | scopes токена; при `CP_AUTHZ_MODE=policy` добавляется `memory:on-behalf` |
| `CP_CONTEXT_NAMESPACE_PREFIX` | `tenant:` | namespace tenant'а = префикс + `<tenant-id>` |
| `CP_CONTEXT_TIMEOUT_SECONDS` | `3.0` | таймаут чтения `/context` (синхронный путь харнесса) |
| `CP_CONTEXT_INGEST_TIMEOUT_SECONDS` | `15.0` | таймаут пакетной записи адаптера |
| `CP_CONTEXT_RECONCILE_TIMEOUT_SECONDS` | `60.0` | таймаут `/knowledge/*` |
| `CP_CONTEXT_BATCH_SIZE` | `100` | размер пакета событий |
| `CP_CONTEXT_TENANT_BATCH_SIZE` | `100` | событий одного tenant'а за цикл |
| `CP_CONTEXT_MAX_TENANTS_PER_CYCLE` | `20` | tenant'ов за цикл (справедливость) |
| `CP_CONTEXT_POLL_INTERVAL_SECONDS` | `1.0` | период опроса журнала адаптером |
| `CP_CONTEXT_RETRY_BACKOFF_BASE_SECONDS` | `1.0` | база backoff при сбое доставки |
| `CP_CONTEXT_RETRY_BACKOFF_MAX_SECONDS` | `60.0` | потолок backoff |
| `CP_CONTEXT_MAX_TOKENS_LIMIT` | `16000` | потолок бюджета пакета памяти |
| `CP_CONTEXT_DEFAULT_MAX_TOKENS` | `8000` | бюджет по умолчанию |

Подробности — в [Контекст задачи и память](context.md).

## Хранилище содержимого артефактов { #content-store }

Байты артефактов (`PUT /artifact-contents`) ядро хранит в любом
S3-совместимом хранилище. Без `CP_S3_ENDPOINT_URL` хранилище выключено:
маршруты содержимого отвечают `503 content_store_unavailable`, а записи
артефактов (ссылки и JSON) работают как обычно. См.
[Артефакты](artifacts.md#content) и [Хранилище объектов](../operations/object-storage.md).

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CP_S3_ENDPOINT_URL` | — | адрес S3-совместимого сервиса; не задан — хранилище выключено |
| `CP_S3_BUCKET` | `artifacts` | бакет содержимого; API при старте создаёт его, если его нет и хватает прав |
| `CP_S3_REGION` | `us-east-1` | регион подписи запросов |
| `CP_S3_ACCESS_KEY_ID` | — | ключ доступа пользователя ядра |
| `CP_S3_SECRET_ACCESS_KEY` | — | секрет пользователя ядра |
| `CP_S3_CONNECT_TIMEOUT_SECONDS` | `5.0` | таймаут соединения с хранилищем |
| `CP_S3_READ_TIMEOUT_SECONDS` | `60.0` | таймаут чтения |
| `CP_ARTIFACT_MAX_BYTES` | `104857600` (100 МиБ) | предел одного файла; для `PUT /artifact-contents` заменяет `CP_MAX_BODY_BYTES`, больше — `413 request_too_large`. Тип артефакта может только сузить его (`maxBytes`) |
| `CP_ARTIFACT_UPLOAD_TTL_SECONDS` | `86400` (24 ч) | сколько загрузка ждёт артефакта, который на неё сошлётся; потом worker её удаляет |

Хранилище читают API и worker: worker удаляет загрузки без ссылок после
срока и объекты, на которые больше никто не ссылается. Недоступное при
старте хранилище API не останавливает: в журнал пишется предупреждение, а
бакет проверяется повторно при первом обращении.

## IAM

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CP_IAM_ENABLED` | `false` | принимать IAM access tokens |
| `CP_IAM_ISSUER` | `""` | ожидаемый issuer; **обязателен** при включённом IAM |
| `CP_IAM_JWKS_URL` | `""` | адрес JWKS; **обязателен** при включённом IAM |
| `CP_IAM_AUDIENCE` | `control-plane` | ожидаемый audience |
| `CP_IAM_LEEWAY_SECONDS` | `5.0` | допуск расхождения часов при проверке времени жизни токена |
| `CP_IAM_JWKS_REFRESH_AFTER_SECONDS` | `300.0` | через сколько обновлять JWKS |
| `CP_IAM_JWKS_STALE_AFTER_SECONDS` | `3600.0` | сколько можно жить на старом JWKS, если IAM недоступен |
| `CP_IAM_JWKS_MIN_REFRESH_INTERVAL_SECONDS` | `10.0` | минимальный интервал между внеплановыми обновлениями JWKS |
| `CP_IAM_REQUEST_TIMEOUT_SECONDS` | `3.0` | таймаут запросов к IAM |
| `CP_IAM_BINDING_CACHE_TTL_SECONDS` | `30.0` | кэш проекции `iam_principal_bindings` |
| `CP_IAM_BINDING_STALE_AFTER_SECONDS` | `120.0` | после этого срока без успешного перечитывания вход закрывается |
| `CP_LEGACY_API_KEYS_ENABLED` | `true` | принимать legacy-ключи `cp_…`; `false` — только IAM |
| `CP_BREAK_GLASS_ENABLED` | `true` | аварийные ключи `cp_bg…` из shell хоста (CP-ADR-0065): выпуск и приём, в том числе при закрытом окне legacy-ключей |
| `CP_BREAK_GLASS_MAX_TTL_SECONDS` | `14400` | предельный срок жизни аварийного ключа |
| `CP_IAM_BASE_URL` | `http://localhost:8010` | адрес IAM для service account ядра |
| `CP_IAM_CLIENT_ID` | `""` | client id service account ядра |
| `CP_IAM_CLIENT_SECRET` | — | секрет service account ядра |
| `CP_IAM_CLIENT_SCOPES` | `["entitlement:check-on-behalf"]` | scopes токена ядра для entitlement |

Service account ядра нужен для памяти в режиме `iam`, для entitlement и для
PDP. Bootstrap создаёт его и пишет `CP_IAM_CLIENT_ID` и `CP_IAM_CLIENT_SECRET`
в `secrets/control-plane-iam.env`. См. [Service accounts](../iam/service-accounts.md).

## Entitlement

!!! note "Точка расширения"
    Проверка лицензии выключена по умолчанию: сервис лицензий в поставку не
    входит. Переменные ниже нужны, только если он подключён.

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CP_ENTITLEMENT_ENABLED` | `false` | проверять лицензии |
| `CP_ENTITLEMENT_BASE_URL` | `http://localhost:8020` | адрес сервиса лицензий |
| `CP_ENTITLEMENT_PRODUCT` | `control-plane` | продукт |
| `CP_ENTITLEMENT_AUDIENCE` | audience сервиса лицензий | audience токена ядра |
| `CP_ENTITLEMENT_DEFAULT_FEATURE` | `api` | feature для путей, которые не разбираются |
| `CP_ENTITLEMENT_CACHE_TTL_SECONDS` | `30.0` | кэш решений |
| `CP_ENTITLEMENT_DEGRADED_MAX_AGE_SECONDS` | `300.0` | сколько можно жить на старом решении при недоступности |
| `CP_ENTITLEMENT_TIMEOUT_SECONDS` | `3.0` | таймаут |

## Доменная авторизация (PDP)

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `CP_AUTHZ_MODE` | `local` | `local`, `shadow` или `policy`, см. [Авторизация и права](authorization.md#authz-mode) |
| `CP_POLICY_BASE_URL` | `http://localhost:8030` | адрес внешнего PDP |
| `CP_POLICY_AUDIENCE` | audience PDP | audience токена ядра |
| `CP_POLICY_SCOPES` | `["policy:check","policy:check-on-behalf"]` | scopes токена ядра |
| `CP_POLICY_TIMEOUT_SECONDS` | `3.0` | таймаут |
| `CP_POLICY_CACHE_TTL_SECONDS` | `5.0` | кэш решений |

!!! note "Точка расширения"
    `shadow` и `policy` требуют внешнего PDP, который в поставку не входит.

## Переменные уровня `deploy/local/compose.yml`

Этих переменных Control Plane сам не читает. Их подставляет `deploy/local/compose.yml` из
`.env` суперпроекта.

| Переменная `.env` | По умолчанию | Куда уходит |
|---|---|---|
| `CP_POSTGRES_PASSWORD` | обязательна | пароль `control-plane-db`; собирается в `CP_DATABASE_URL` |
| `CP_BOOTSTRAP_TOKEN` | обязательна | `CP_BOOTSTRAP_TOKEN` сервиса API |
| `MEMORY_API_KEY` | обязательна | `CP_CONTEXT_API_KEY` всех трёх процессов |
| `TAIMEN_PUBLIC_URL` | — | `CP_IAM_ISSUER=${TAIMEN_PUBLIC_URL}/iam` |
| `LOG_LEVEL` | `INFO` | `CP_LOG_LEVEL` |
| `CP_CONTEXT_AUTH` | `auto` | как есть |
| `CP_AUTHZ_MODE` | `local` | как есть |
| `CP_LEGACY_API_KEYS_ENABLED` | `false` | как есть |
| `CP_CORS_ORIGINS` | `[]` | как есть |
| `CP_S3_ACCESS_KEY_ID`, `CP_S3_SECRET_ACCESS_KEY` | обязательны | ключи пользователя ядра в хранилище; для MinIO контура их же заводит `minio-bootstrap` |
| `CP_S3_BUCKET` | `artifacts` | как есть; бакет создаёт `minio-bootstrap` |
| `CP_S3_ENDPOINT_URL` | `http://minio:9000` | как есть; внешний S3 — адрес провайдера |
| `CP_S3_REGION` | `us-east-1` | как есть |
| `CP_HOST_PORT` | `18000` | публикация API на `127.0.0.1:<порт>` хоста |
| `CP_MEM_LIMIT` | `512m` | лимит памяти API |
| `CP_WORKER_MEM_LIMIT` | `256m` | лимит памяти worker и context-adapter |
| `CP_BUILD_CONTEXT` | `.` | контекст сборки образа (корень суперпроекта: SDK подключён соседним каталогом) |

Значения, которые `deploy/local/compose.yml` фиксирует для процессов Control Plane:

```yaml
CP_CONTEXT_PROVIDER: http
CP_CONTEXT_BASE_URL: http://memory-service:8077
CP_IAM_BASE_URL: http://iam-service:8010
CP_S3_ENDPOINT_URL: http://minio:9000        # если не переопределён в .env
CP_S3_BUCKET: artifacts                      # если не переопределён в .env
# только control-plane-api:
CP_IAM_ENABLED: "true"
CP_IAM_JWKS_URL: http://iam-service:8010/.well-known/jwks.json
CP_IAM_AUDIENCE: control-plane
```

Service account ядра подключается необязательным `env_file`
`./secrets/control-plane-iam.env`: первый `up` проходит и без него. После
bootstrap перезапустите `control-plane-api`, `control-plane-worker` и
`context-adapter`, чтобы они подхватили файл. Полный список переменных
платформы — в [Переменные окружения](../reference/environment.md) и
[Конфигурация .env](../getting-started/configuration.md).

## Типовые профили

=== "Поставка (IAM-only)"

    ```dotenv
    CP_IAM_ENABLED=true
    CP_IAM_ISSUER=https://platform.example.com/iam
    CP_IAM_JWKS_URL=http://iam-service:8010/.well-known/jwks.json
    CP_LEGACY_API_KEYS_ENABLED=false
    CP_CONTEXT_PROVIDER=http
    CP_CONTEXT_AUTH=auto
    CP_AUTHZ_MODE=local
    ```

=== "Локальная разработка без памяти"

    ```dotenv
    CP_DATABASE_URL=postgresql+psycopg://control_plane:control_plane@localhost:5433/control_plane
    CP_BOOTSTRAP_TOKEN=dev-bootstrap-token
    CP_CONTEXT_PROVIDER=none
    CP_IAM_ENABLED=false
    CP_LEGACY_API_KEYS_ENABLED=true
    ```

=== "Проверка политики (shadow)"

    ```dotenv
    CP_AUTHZ_MODE=shadow
    CP_POLICY_BASE_URL=http://<адрес PDP>:8030
    CP_IAM_CLIENT_ID=<client-id>
    CP_IAM_CLIENT_SECRET=<secret>
    ```

## Клиентские переменные `CONTROL_PLANE_*`

Эти переменные читают CLI `control-plane`, MCP-сервер `control-plane-mcp` и
SDK `control_plane_client`, а не сервер. Подробности — в [CLI и
MCP-сервер](cli-and-mcp.md#credentials).

| Переменная | Кто читает | Смысл |
|---|---|---|
| `CONTROL_PLANE_SERVER` | CLI, MCP | адрес Control Plane |
| `CONTROL_PLANE_API_KEY` | SDK | legacy-ключ (явный override) |
| `CONTROL_PLANE_NO_KEYCHAIN` | SDK | `1` — не использовать macOS Keychain для legacy-ключа |
| `CONTROL_PLANE_IAM_URL` | SDK | базовый URL IAM; включает IAM-identity |
| `CONTROL_PLANE_IAM_TENANT` | SDK | tenant в IAM |
| `CONTROL_PLANE_IAM_AUDIENCE` | SDK | audience обмена, по умолчанию `control-plane` |
| `CONTROL_PLANE_IAM_SCOPES` | SDK | scopes обмена (через пробел или запятую) |
| `CONTROL_PLANE_HARNESS_TYPE` | MCP | `harness.type` сессии, по умолчанию `mcp-client` |
| `CONTROL_PLANE_HARNESS_VERSION` | MCP | `harness.version`, по умолчанию версия пакета |
| `CONTROL_PLANE_HARNESS_CLIENT_NAME` | MCP | `clientName`, по умолчанию `control-plane-mcp` |
| `CONTROL_PLANE_CONTEXT_BUDGET_CHARS` | адаптеры исполнителей | бюджет раздела памяти в prompt, по умолчанию `12000` |

Рядом используются переменные IAM-хранилища: `IAM_PRINCIPAL`,
`IAM_CREDENTIAL_MODE`, `IAM_PLATFORM_ACCESS_TOKEN`, `IAM_NO_KEYCHAIN`.

Переменные демона исполнителя (`CONTROL_PLANE_AGENT_*`,
`CONTROL_PLANE_CLAUDE_*`, `CONTROL_PLANE_CODEX_*`, `CONTROL_PLANE_SKILLS_*`,
`CONTROL_PLANE_TRACE_*`) описаны в [Конфигурации runner](../runner/configuration.md).

## Проверка конфигурации

```bash
# процесс поднялся, миграции применены
curl -s http://127.0.0.1:18000/health/ready
# {"status": "ready", "revision": "<alembic-head>"}

# IAM-вход работает и права корректны
control-plane whoami

# память подключена
curl -s -X POST http://127.0.0.1:18000/api/v1/context \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"query": "ping"}' | jq '.memoryStatus, .warnings'
```

## См. также

- [Авторизация и права](authorization.md)
- [Контекст задачи и память](context.md)
- [API](api.md)
- [Переменные окружения](../reference/environment.md)
- [Сервисы и порты](../reference/services-and-ports.md)
- [Секреты и ротация](../operations/secrets.md)
- [Хранилище объектов (MinIO)](../operations/object-storage.md)
