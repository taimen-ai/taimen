# Переменные окружения

Полный перечень переменных окружения поставки Taimen: корневой `.env`
(контракт `.env.example`), переменные, которые `deploy/local/compose.yml` передаёт в
контейнеры, настройки каждого сервиса (pydantic-settings с префиксом) и
переменные процессов вне compose — runner-агента, CLI, MCP-сервера, коннектора
и SDK. Статья для инженера, который настраивает стенд или разбирается, откуда
сервис взял значение.

## Как устроена конфигурация

```mermaid
flowchart LR
    ENV[".env<br/>(из .env.example)"] -->|интерполяция ${VAR}| COMPOSE["deploy/local/compose.yml"]
    COMPOSE -->|environment:| SVC["контейнер<br/>CP_* / IAM_* / CB_* / ..."]
    SECRETS["secrets/*.env<br/>(пишет bootstrap)"] -->|env_file| SVC
    PEM["secrets/*.pem"] -->|docker secret| SVC
```


1. Оператор заполняет **один** файл `.env` в корне суперпроекта. В нём одно
   понятие — одно имя (`MEMORY_API_KEY`, `TAIMEN_PUBLIC_URL`, `LLM_MODEL`).
   `make secrets` создаёт его из `.env.example` и генерирует случайные секреты.
2. `deploy/local/compose.yml` раскладывает значения по префиксам сервисов: например,
   `MEMORY_API_KEY` превращается в `CB_SERVER_API_KEY` у memory-service и
   `CP_CONTEXT_API_KEY` у Control Plane.
   Часть переменных сервиса compose задаёт жёстко (адреса внутри сети,
   audience), их менять через `.env` нельзя.
3. Секреты, которые появляются только после bootstrap (client credentials
   service accounts), лежат в `secrets/*.env` и подключаются через
   `env_file` с `required: false` — первый `up` проходит и без них.
4. Внутри сервиса значения читает pydantic-settings с префиксом
   (`CP_`, `IAM_`, `CB_`, `NS_`). Неизвестные
   переменные игнорируются (`extra="ignore"`).

| Префикс | Компонент | Где читается |
|---|---|---|
| `CP_` | Control Plane (api, worker, context-adapter) | `control_plane/config.py` |
| `IAM_` | iam-service | `iam_service/config.py` |
| `CB_` | memory-service | `platform_memory/core/config.py` |
| `NS_` | notification-service | `notification_service/config.py` |
| `FLEET_` | fleet-controller | `fleet_controller/wiring.py` (читается напрямую из окружения) |
| `CONTROL_PLANE_*`, `IAM_*` (клиентские) | runner, CLI, MCP-сервер, SDK-клиент | `control_plane_agent`, `control_plane_client` |

!!! warning "Обязательные переменные проверяются для всех профилей"
    Переменные вида `${VAR:?…}` в `deploy/local/compose.yml` обязательны **при любом
    наборе профилей**: Docker Compose интерполирует весь файл до фильтрации
    по профилям. Поэтому обязательными (`:?`) объявлены только значения,
    которые генерирует `make secrets`; идентификаторы, которые генерировать

    нечем (`IAM_TENANT_ID`), по умолчанию пусты и проверяются самими
    сервисами своих профилей. Проверка — `make config`.

## Корневой `.env`

Переменные контракта `.env.example` и прочие переменные интерполяции
`deploy/local/compose.yml`. Колонка «По умолчанию» — значение подстановки в `deploy/local/compose.yml`
(`${VAR:-…}`); «обязательна» — подстановка `${VAR:?…}`.

### Окружение и периметр

| Переменная | По умолчанию | Обязательна | Назначение |
|---|---|---|---|
| `TAIMEN_PUBLIC_URL` | — (в `.env.example`: `http://taimen.localhost`) | да | Публичный адрес платформы без завершающего `/`. Из него строятся issuer IAM (`${TAIMEN_PUBLIC_URL}/iam`), issuer Keycloak (`…/auth/realms/platform`), адреса launcher'а рабочих мест (`…/harness`) и redirect URI клиента `human-harness` в шаблоне realm. Смена адреса меняет issuer — см. предупреждение в [Права и scopes](permissions.md#iam-principal-bindings). |
| `TAIMEN_PUBLIC_HOST` | `taimen.localhost` | нет | Сетевой alias контейнера `caddy`: контейнеры ходят к IAM и Keycloak по публичному имени (hairpin), чтобы issuer совпадал с тем, что видит браузер. |
| `COMPOSE_PROJECT_NAME` | `taimen` | нет | Имя compose-проекта. Префикс имён volumes по умолчанию. Читается также `deploy/bootstrap.py` (имя окружения и slug tenant). |
| `TAIMEN_NETWORK` | `taimen_default` | нет | Имя docker-сети `taimen`. |
| `CADDYFILE` | `./deploy/caddy/Caddyfile.local` | нет | Файл конфигурации Caddy, монтируется в контейнер `caddy`. Для TLS-стенда — свой файл с той же раскладкой путей. |
| `EDGE_HTTP_PORT` | `80` | нет | Публикуемый порт HTTP контейнера `caddy`. |
| `EDGE_HTTPS_PORT` | `443` | нет | Публикуемый порт HTTPS контейнера `caddy`. |
| `LOG_LEVEL` | `INFO` | нет | Уровень логов: `CP_LOG_LEVEL`. |
| `LOG_RENDERER`, `CP_TIMEZONE` | — | нет | Объявлены в `.env.example`, но сервисами `deploy/local/compose.yml` не читаются. |
| `IMAGE_PREFIX` | `taimen` | нет | Префикс имён образов: `${IMAGE_PREFIX}/control-plane:${IMAGE_TAG}`. |
| `IMAGE_TAG` | `local` | нет | Тег образов. |

### Tenant и идентификаторы

| Переменная | По умолчанию | Обязательна | Назначение |
|---|---|---|---|
| `IAM_TENANT_ID` | `""` | нет | UUID tenant в IAM. Нужен fleet-controller и launcher'у рабочих мест (`LAUNCHER_IAM_TENANT`, `HARNESS_IAM_TENANT` контейнеров людей). `make bootstrap` печатает значение, которое нужно вписать. Читается также `deploy/bootstrap.py`. |

### Секреты

Все значения из этой таблицы, кроме отмеченных, `make secrets` заполняет
случайной строкой (`tools/fill_secrets.py`), если они пусты или отсутствуют в `.env`.


| Переменная | По умолчанию | Обязательна | Назначение |
|---|---|---|---|
| `CP_POSTGRES_PASSWORD` | — | да | Пароль БД `control_plane` (роль `control_plane`). |
| `IAM_POSTGRES_PASSWORD` | — | да | Пароль БД `iam`. |
| `MEMORY_POSTGRES_PASSWORD` | — | да | Пароль БД `company_brain` (роль `memory`). |
| `KEYCLOAK_DB_PASSWORD` | — | да | Пароль БД и роли `keycloak` в `keycloak-db`. |
| `NOTIFY_POSTGRES_PASSWORD` | — | да | Пароль БД `notify` (notification-service). |
| `CP_BOOTSTRAP_TOKEN` | — | да | Токен `POST /api/v1/bootstrap` Control Plane (`Authorization: Bearer`). |
| `IAM_BOOTSTRAP_TOKEN` | — | да | Токен bootstrap-эндпоинтов IAM (заголовок `X-IAM-Bootstrap-Token`). |
| `MEMORY_API_KEY` | — | да | Статический ключ памяти: `CB_SERVER_API_KEY` memory-service, `CP_CONTEXT_API_KEY` ядра (используется до появления service account, см. `CP_CONTEXT_AUTH`). |
| `KEYCLOAK_ADMIN` | `admin` | нет | Логин bootstrap-администратора Keycloak. |
| `KEYCLOAK_ADMIN_PASSWORD` | — | да | Пароль bootstrap-администратора Keycloak. |
| `KEYCLOAK_HOSTNAME_STRICT` | `true` | нет | `KC_HOSTNAME_STRICT`. Локально по HTTP без домена — `false`. |
| `S3_ACCESS_KEY_ID` | — | да | Root-пользователь MinIO; им ходит только `minio-bootstrap`. |
| `S3_SECRET_ACCESS_KEY` | — | да | Пароль root MinIO. |
| `CP_S3_ACCESS_KEY_ID`, `CP_S3_SECRET_ACCESS_KEY` | — | да | Пользователь MinIO ядра с политикой `cp-artifacts` (заводит `minio-bootstrap`); ими процессы Control Plane пишут и читают содержимое артефактов. |
| `CP_S3_BUCKET` | `artifacts` | нет | Бакет содержимого артефактов (создаёт `minio-bootstrap`). |
| `CP_S3_ENDPOINT_URL`, `CP_S3_REGION` | `http://minio:9000`, `us-east-1` | нет | Адрес и регион S3; пустой адрес выключает хранилище содержимого. См. [Хранилище объектов](../operations/object-storage.md). |
| `IAM_SIGNING_KEY_FILE` | `./secrets/iam-signing.pem` | нет | Файл приватного ключа подписи токенов IAM (RSA 3072, `make secrets`); монтируется docker-секретом `iam_signing_key`. |
| `IAM_SIGNING_KEY_ID` | `local-dev` | нет | `kid` ключа подписи IAM. |

!!! note "Файлы ключей читает uid 10001"
    Контейнеры `iam-service`, `control-plane-*` и другие сервисы платформы работают под
    непривилегированным пользователем с uid 10001. На Linux файлы
    `secrets/*.pem` должны принадлежать этому uid при
    правах `600`: иначе сервис получает `PermissionError` при чтении ключа.


### LLM и память

| Переменная | По умолчанию | Обязательна | Назначение |
|---|---|---|---|
| `LLM_API_KEY` | `""` | нет | Ключ OpenAI-совместимого провайдера: эмбеддинги и LLM памяти (`CB_EMBEDDING_API_KEY`, `CB_LLM_API_KEY`), демо-бот. Пусто — память работает офлайн (`fake`/`echo`). |
| `LLM_BASE_URL` | для памяти `""`; для демо `https://api.aitunnel.ru/v1` | нет | Базовый URL OpenAI-совместимого API. |
| `LLM_MODEL` | `gemini-3.5-flash-lite` | нет | Модель LLM памяти (`CB_LLM_MODEL`) и демо-бота. |
| `MEMORY_EMBEDDING_PROVIDER` | `fake` | нет | `CB_EMBEDDING_PROVIDER`: `fake` (офлайн) или `openai`. |
| `MEMORY_EMBEDDING_MODEL` | `text-embedding-3-small` | нет | `CB_EMBEDDING_MODEL`. |
| `MEMORY_LLM_PROVIDER` | `echo` | нет | `CB_LLM_PROVIDER`: `echo` (офлайн) или `openai`. |
| `MEMORY_RERANK_ENABLED` | `false` | нет | `CB_RERANK_ENABLED`. |
| `MEMORY_CONSOLE_ENABLED` | `false` | нет | `CB_CONSOLE_ENABLED` — административная Memory Console. |
| `MEMORY_IAM_ENABLED` | `true` | нет | `CB_IAM_ENABLED` — приём IAM-токенов audience `memory-service` в дополнение к статическому ключу. |
| `MEMORY_POLICY_ENABLED` | `false` | нет | `CB_POLICY_ENABLED` — видимость памяти по principal через внешний PDP (экспериментально). |

### Control Plane


| Переменная | По умолчанию | Обязательна | Назначение |
|---|---|---|---|
| `CP_LEGACY_API_KEYS_ENABLED` | `false` | нет | Принимать ли legacy-ключи `cp_…` (`CP_LEGACY_API_KEYS_ENABLED`). В стеке IAM включён всегда (`CP_IAM_ENABLED: "true"`). |
| `CP_CONTEXT_AUTH` | `auto` | нет | Как ядро аутентифицируется в памяти: `auto`, `api_key`, `iam`. |
| `CP_AUTHZ_MODE` | `local` | нет | Источник доменной авторизации: `local`, `shadow`, `policy` (CP-ADR-0055). |
| `CP_CORS_ORIGINS` | `[]` | нет | JSON-список разрешённых CORS-источников API. |

### Сервис уведомлений

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `NOTIFY_EMAIL_FROM` | `notifications@localhost` | `NS_EMAIL_FROM` — отправитель писем. |
| `NOTIFY_SMTP_HOST` | `localhost` | `NS_SMTP_HOST`. |
| `NOTIFY_SMTP_PORT` | `587` | `NS_SMTP_PORT`. |

### Рабочие места (`harness`)

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `HARNESS_MEM_LIMIT_MB` | `1536` | Лимит памяти контейнера человека (`LAUNCHER_HARNESS_MEMORY_MB`). |
| `HARNESS_CPUS` | `1` | Лимит CPU контейнера человека в ядрах (`LAUNCHER_HARNESS_CPUS`). |
| `HARNESS_PIDS_LIMIT` | `512` | Лимит процессов контейнера человека (`LAUNCHER_HARNESS_PIDS`). |
| `HARNESS_PEOPLE_NETWORK` | `<COMPOSE_PROJECT_NAME>_harness-people` | Сеть контейнеров людей (`LAUNCHER_NETWORK`): launcher, ядро, уведомления, caddy — без баз и прокси Docker. |
| `HARNESS_CONTROL_NETWORK` | `<COMPOSE_PROJECT_NAME>_harness-control` | Внутренняя сеть прокси Docker и launcher'а. См. [Изоляция рабочих мест](../workplace/index.md#isolation). |
| `HARNESS_IDLE_MINUTES` | `30` | Через сколько минут без запросов контейнер человека засыпает (`LAUNCHER_IDLE_MINUTES`). |
| `HARNESS_APP_NAME` | `Human Harness` | Имя приложения рабочего места (`appName` в ответе `whoami` движка ассистента). |
| `HARNESS_COOKIE_SECRET_FILE` | `./secrets/harness/cookie-secret` | Файл ключа cookie launcher'а (docker-секрет `harness_cookie_secret`, пишет bootstrap шагом 8). |
| `NOTIFY_HARNESS_LAUNCHER_URL` | `http://harness-launcher:8080/harness` | Адрес launcher'а для сервиса уведомлений (ассистент в Telegram). |

Подробно — [Рабочее место человека](../workplace/index.md).

### Консоль runtime (OIDC)

Консоль входит через OIDC IdP (Authorization Code + PKCE, confidential client) и
обменивает id token IdP в IAM `federation:exchange` на токены audiences
`control-plane`, `iam`, `human-harness`. Про сам IdP консоль знает только
issuer, client id и секрет.

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `RUNTIME_CONSOLE_OIDC_ISSUER` | `${TAIMEN_PUBLIC_URL}/auth/realms/platform` | Issuer OIDC IdP. |
| `RUNTIME_CONSOLE_OIDC_CLIENT_ID` | `runtime-console` | Client id консоли в IdP. |
| `RUNTIME_CONSOLE_OIDC_SECRET_FILE` | `./secrets/runtime-console-oidc-secret` | Файл секрета клиента (0600, docker-секрет `runtime_console_oidc_secret`). Пишет `make secrets` или `deploy/keycloak/keycloak-runtime-console-client.py`. |
| `RUNTIME_CONSOLE_IDENTITY_PROVIDER` | `keycloak` | Ключ identity provider в IAM для `federation:exchange`. |
| `RUNTIME_CONSOLE_OIDC_SCOPES` | `openid profile email` | Scope запроса к IdP. Keycloak выдаёт refresh token и без `offline_access`. |
| `RUNTIME_CONSOLE_COOKIE_SECRET_FILE` | `./secrets/runtime-console-cookie-secret` | Секрет cookie консоли, не короче 32 байт (0600, пишет `make secrets`): из него выводятся ключ подписи сессии и ключ шифрования cookie незавершённого входа. В cookie только случайный id сессии, токены остаются на сервере консоли. |
| `RUNTIME_CONSOLE_CP_SCOPES` | `control-plane:read control-plane:write` | Scope, которые консоль явно просит у federation. Что человеку можно по делу, решают его связки в ядре. |
| `RUNTIME_CONSOLE_SESSION_TTL_HOURS` | `12` | Срок сессии консоли. |
| `RUNTIME_CONSOLE_PRODUCT_NAME`, `RUNTIME_CONSOLE_ORG_NAME` | `Console`, пусто | Имя продукта и организации в интерфейсе консоли (white-label): сервер консоли отдаёт их интерфейсу при старте, в коде консоли имени продукта нет. |
| `RUNTIME_CONSOLE_LOCALES`, `RUNTIME_CONSOLE_DEFAULT_LOCALE` | `en,ru`, `en` | Языки интерфейса и язык по умолчанию. |

Привилегированные scope federation выдаёт только членам группы IAM и только по явному
запросу: `iam:people` (управление людьми) — группе `people-admins`, `fleet:admin`
(ключи регистрации узлов fleet) — группе `fleet-admins`. Группы и членство владельца
заводит `deploy/bootstrap.py` (шаг 2b). Консоль по умолчанию просит `fleet:read`;
чтобы получить `fleet:admin`, человек должен состоять в `fleet-admins`.


### Переменные пакетов каталога { #package-variables }

Эти переменные не интерполирует `deploy/local/compose.yml`: их читает установщик пакетов
`package-sdk` (из `.env`, флаг `--env`, и окружения процесса) и
подставляет в `${ИМЯ}` объектов пакета при `plan` и `apply`. Какие переменные
нужны, объявляет сам пакет; незаданная переменная, которая нужна пакету
установки, — ошибка установки.

Токены установщика — тоже переменные процесса, а не `.env`: `CP_TOKEN` (access
token audience `control-plane`) и `NOTIFY_TOKEN` (audience
`notification-service`, scope `notifications:admin`, нужен для
`NotificationRule`). Без них установщик обменивает IAM credential клиента
Control Plane (см. [Пакеты каталога](../control-plane/catalog-packages.md)).

### Порты на 127.0.0.1

Все сервисы, кроме `caddy`, публикуются только на loopback. Подробно — в
[Сервисы и порты](services-and-ports.md).

| Переменная | По умолчанию | Сервис (внутренний порт) |
|---|---|---|
| `CP_HOST_PORT` | `18000` | `control-plane-api` (8000). Читается `deploy/bootstrap.py`. |
| `MEMORY_HOST_PORT` | `18001` | `memory-service` (8077) |
| `IAM_HOST_PORT` | `18010` | `iam-service` (8010). Читается `deploy/bootstrap.py`. |
| `NOTIFY_HOST_PORT` | `18045` | `notification-service` (8000) |
| `KEYCLOAK_HOST_PORT` | `18081` | `keycloak` (8080) |

### Лимиты памяти контейнеров

| Переменная | По умолчанию | Контейнеры |
|---|---|---|
| `PG_MEM_LIMIT` | `256m` | `iam-db`, `control-plane-db`, `keycloak-db` |
| `IAM_MEM_LIMIT` | `256m` | `iam-service` |
| `CP_MEM_LIMIT` | `512m` | `control-plane-api` |
| `CP_WORKER_MEM_LIMIT` | `256m` | `control-plane-worker`, `context-adapter` |
| `MEMORY_DB_MEM_LIMIT` | `512m` | `memory-db` |
| `MEMORY_MEM_LIMIT` | `512m` | `memory-service` |
| `NOTIFY_MEM_LIMIT` | `256m` | `notification-service` |
| `NOTIFY_DB_MEM_LIMIT` | `128m` | `notification-db` |
| `KEYCLOAK_MEM_LIMIT` | `768m` | `keycloak` |
| `MINIO_MEM_LIMIT` | `256m` | `minio` |
| `FLEET_MEM_LIMIT` | `128m` | `fleet-controller` |

### Контексты сборки

Переопределяют каталог, из которого собирается образ (например, для сборки
из отдельного клона релиза).

| Переменная | По умолчанию |
|---|---|
| `IAM_BUILD_CONTEXT` | `./services/iam-service` |
| `CP_BUILD_CONTEXT` | `.` (Dockerfile `services/control-plane/Dockerfile`) |
| `MEMORY_BUILD_CONTEXT` | `.` для `memory-service` (Dockerfile `services/memory-service/Dockerfile`); `./services/memory-service` + `/infra/memory-db` для `memory-db` |
| `NOTIFY_BUILD_CONTEXT` | `.` (Dockerfile `services/notification-service/Dockerfile`) |
| `FLEET_BUILD_CONTEXT` | `.` (Dockerfile `services/fleet/Dockerfile`) |

!!! warning "Одна переменная — два значения по умолчанию"
    `MEMORY_BUILD_CONTEXT` используется и для `memory-db`
    (`${MEMORY_BUILD_CONTEXT:-./services/memory-service}/infra/memory-db`), и для
    `memory-service` (`${MEMORY_BUILD_CONTEXT:-.}`). Если задать её явно,
    одно из двух путей окажется неверным; оставляйте её пустой.

### Имена volumes

Каждый volume получает имя `${COMPOSE_PROJECT_NAME}_<имя>`, если переменная
не задана. Задавать их нужно, чтобы подключить уже существующие volumes
(например, при переходе стенда на корневой compose).


`VOLUME_IAM_DB`, `VOLUME_CONTROL_PLANE_DB`, `VOLUME_MEMORY_DB`,
`VOLUME_NOTIFY_DB`,
`VOLUME_KEYCLOAK_DB`, `VOLUME_PLATFORM_MINIO` (том MinIO с содержимым артефактов),
`VOLUME_REALM_IMPORT`, `VOLUME_HARNESS_LAUNCHER`,
`VOLUME_CADDY_DATA`, `VOLUME_CADDY_CONFIG` и `VOLUME_FLEET_DATA`.

## Control Plane (`CP_`)

Читаются процессами `control-plane-api`, `control-plane-worker` и
`context-adapter` (один образ). Колонка «В стеке» — значение, которое
задаёт `deploy/local/compose.yml`.

### Основное

| Переменная | По умолчанию | В стеке | Назначение |
|---|---|---|---|
| `CP_ENV` | `dev` | — | Объявлена в настройках, кодом не используется. |
| `CP_DATABASE_URL` | `postgresql+psycopg://control_plane:control_plane@localhost:5433/control_plane` | `…@control-plane-db:5432/control_plane` | Строка подключения SQLAlchemy. |
| `CP_BOOTSTRAP_TOKEN` | не задан | `${CP_BOOTSTRAP_TOKEN}` (только api) | Токен `POST /api/v1/bootstrap`. Не задан — эндпоинт отвечает `403 bootstrap_disabled`. |
| `CP_LOG_LEVEL` | `INFO` | `${LOG_LEVEL}` | Уровень логов. |
| `CP_MAX_BODY_BYTES` | `1048576` | — | Предел тела запроса; больше — `413 request_too_large`. |
| `CP_KNOWLEDGE_SNAPSHOT_MAX_BODY_BYTES` | `8388608` | — | Отдельный предел для снимков знаний. |
| `CP_KNOWLEDGE_PACK_ADMINS` | `[]` | — | JSON-список id principal (CP или IAM), которым разрешено регистрировать knowledge packs. Пусто — `POST /api/v1/knowledge/packs` отвечает `403`. |
| `CP_CORS_ORIGINS` | `[]` | `${CP_CORS_ORIGINS}` (api) | JSON-список CORS-источников. |
| `CP_WS_POLL_INTERVAL_SECONDS` | `5.0` | — | Интервал опроса WebSocket-потока при потере NOTIFY. |
| `CP_API_KEY_LAST_USED_REFRESH_SECONDS` | `60` | — | Как часто обновлять отметку последнего использования legacy-ключа. |

### Аренды (sessions и claims)

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `CP_SESSION_TTL_SECONDS` | `300` | TTL сессии харнесса по умолчанию. |
| `CP_SESSION_TTL_MIN_SECONDS` | `10` | Нижняя граница запрошенного TTL сессии. |
| `CP_SESSION_TTL_MAX_SECONDS` | `3600` | Верхняя граница TTL сессии. |
| `CP_CLAIM_TTL_SECONDS` | `300` | TTL claim по умолчанию. |
| `CP_CLAIM_TTL_MIN_SECONDS` | `10` | Нижняя граница TTL claim. |
| `CP_CLAIM_TTL_MAX_SECONDS` | `3600` | Верхняя граница TTL claim. Вне границ — `422 invalid_ttl`. |

### Идемпотентность

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `CP_IDEMPOTENCY_TTL_SECONDS` | `86400` | Сколько хранится ответ по `Idempotency-Key`. |
| `CP_IDEMPOTENCY_WAIT_TIMEOUT_SECONDS` | `10.0` | Сколько параллельный дубль ждёт завершения первого запроса; дальше — `409 idempotency_in_flight`. |
| `CP_IDEMPOTENCY_PENDING_TTL_SECONDS` | `60` | Время жизни записи без сохранённого ответа (защита от «залипшего» ключа после падения процесса). |


### Worker и outbox

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `CP_WORKER_POLL_INTERVAL_SECONDS` | `1.0` | Период опроса воркера. |
| `CP_OUTBOX_BATCH_SIZE` | `50` | Размер пачки outbox. |
| `CP_OUTBOX_MAX_ATTEMPTS` | `8` | Попыток доставки записи outbox. |
| `CP_OUTBOX_LOCK_TIMEOUT_SECONDS` | `60` | Таймаут блокировки записи outbox. |
| `CP_OUTBOX_BACKOFF_BASE_SECONDS` | `2.0` | База экспоненциальной задержки. |
| `CP_OUTBOX_BACKOFF_MAX_SECONDS` | `300.0` | Потолок задержки. |
| `CP_APPROVAL_OUTCOME_DEFER_SECONDS` | `15.0` | Сколько исход approval, встретивший живой claim цели, ждёт повторной попытки (CP-ADR-0061). |
| `CP_JOURNAL_RETENTION_MIN_AGE_SECONDS` | `2592000` | Минимальный возраст события журнала, после которого его можно архивировать или удалить. |

### Память (context provider)

| Переменная | По умолчанию | В стеке | Назначение |
|---|---|---|---|
| `CP_CONTEXT_PROVIDER` | `none` | `http` | `none` — ядро автономно; `http` — memory-service. |
| `CP_CONTEXT_BASE_URL` | `http://localhost:8077` | `http://memory-service:8077` | Адрес памяти. |
| `CP_CONTEXT_API_KEY` | не задан | `${MEMORY_API_KEY}` | Статический Bearer для памяти. |
| `CP_CONTEXT_AUTH` | `auto` | `${CP_CONTEXT_AUTH}` | `api_key` — статический ключ; `iam` — service account ядра (`CP_IAM_CLIENT_ID/SECRET`); `auto` — `iam`, если service account настроен, иначе `api_key`. |
| `CP_CONTEXT_IAM_AUDIENCE` | `memory-service` | — | Audience токена для памяти. |
| `CP_CONTEXT_IAM_SCOPES` | `["memory:read","memory:write","memory:tenants","memory:service"]` | — | Scopes токена для памяти. |
| `CP_CONTEXT_NAMESPACE_PREFIX` | `tenant:` | — | Namespace памяти tenant: `<prefix><tenant_id>`. |
| `CP_CONTEXT_TIMEOUT_SECONDS` | `3.0` | — | Таймаут интерактивного `/context`. |
| `CP_CONTEXT_INGEST_TIMEOUT_SECONDS` | `15.0` | — | Таймаут пакетной записи наблюдений. |
| `CP_CONTEXT_RECONCILE_TIMEOUT_SECONDS` | `60.0` | — | Таймаут сверки снимков и администрирования packs. |
| `CP_CONTEXT_BATCH_SIZE` | `100` | — | Размер пачки доставки в память. |
| `CP_CONTEXT_TENANT_BATCH_SIZE` | `100` | — | Пачка на один tenant за цикл. |
| `CP_CONTEXT_MAX_TENANTS_PER_CYCLE` | `20` | — | Сколько tenant обслуживается за цикл. |
| `CP_CONTEXT_POLL_INTERVAL_SECONDS` | `1.0` | — | Период context-adapter. |
| `CP_CONTEXT_RETRY_BACKOFF_BASE_SECONDS` | `1.0` | — | База задержки повторов. |
| `CP_CONTEXT_RETRY_BACKOFF_MAX_SECONDS` | `60.0` | — | Потолок задержки. |
| `CP_CONTEXT_MAX_TOKENS_LIMIT` | `16000` | — | Серверный потолок бюджета ContextPack. |
| `CP_CONTEXT_DEFAULT_MAX_TOKENS` | `8000` | — | Бюджет ContextPack по умолчанию. |

### IAM

| Переменная | По умолчанию | В стеке | Назначение |
|---|---|---|---|
| `CP_IAM_ENABLED` | `false` | `true` (api) | Принимать токены IAM. |
| `CP_IAM_ISSUER` | `""` | `${TAIMEN_PUBLIC_URL}/iam` | Точный `iss` токенов. |
| `CP_IAM_JWKS_URL` | `""` | `http://iam-service:8010/.well-known/jwks.json` | JWKS IAM (внутренний адрес). |
| `CP_IAM_AUDIENCE` | `control-plane` | `control-plane` | Ожидаемый `aud`. |
| `CP_IAM_LEEWAY_SECONDS` | `5.0` | — | Допуск рассинхрона часов. |
| `CP_IAM_JWKS_REFRESH_AFTER_SECONDS` | `300.0` | — | Когда перечитывать JWKS. |
| `CP_IAM_JWKS_STALE_AFTER_SECONDS` | `3600.0` | — | После этого возраста JWKS без обновления проверка недоступна (`verification_unavailable`). |
| `CP_IAM_JWKS_MIN_REFRESH_INTERVAL_SECONDS` | `10.0` | — | Не чаще одного перечитывания JWKS за интервал. |
| `CP_IAM_REQUEST_TIMEOUT_SECONDS` | `3.0` | — | Таймаут запросов к IAM. |
| `CP_IAM_BINDING_CACHE_TTL_SECONDS` | `30.0` | — | Сколько переиспользуется проекция binding. |
| `CP_IAM_BINDING_STALE_AFTER_SECONDS` | `120.0` | — | Возраст, после которого непроверенная запись закрывает вход. |
| `CP_LEGACY_API_KEYS_ENABLED` | `true` | `${CP_LEGACY_API_KEYS_ENABLED:-false}` (api) | Legacy-ключи `cp_…` как credential. |
| `CP_BREAK_GLASS_ENABLED` | `true` | — | Аварийные ключи `cp_bg…` из shell хоста (CP-ADR-0065). |
| `CP_BREAK_GLASS_MAX_TTL_SECONDS` | `14400` | — | Предельный срок жизни аварийного ключа. |
| `CP_IAM_BASE_URL` | `http://localhost:8010` | `http://iam-service:8010` | Адрес IAM для обмена client credentials. |
| `CP_IAM_CLIENT_ID` | `""` | из `secrets/control-plane-iam.env` | Client id service account ядра. |
| `CP_IAM_CLIENT_SECRET` | не задан | из `secrets/control-plane-iam.env` | Секрет service account ядра. |
| `CP_IAM_CLIENT_SCOPES` | `["entitlement:check-on-behalf"]` | — | Scopes service account для entitlement. |

### Entitlement

| Переменная | По умолчанию | В стеке | Назначение |
|---|---|---|---|
| `CP_ENTITLEMENT_ENABLED` | `false` | — | Проверять лицензии. Выключено — в audit источник решения `disabled`. |
| `CP_ENTITLEMENT_BASE_URL` | `http://localhost:8020` | — | Адрес сервиса лицензий. |
| `CP_ENTITLEMENT_PRODUCT` | `control-plane` | — | Продукт в каталоге лицензий. |
| `CP_ENTITLEMENT_DEFAULT_FEATURE` | `api` | — | Feature, если не выводится из пути (`/api/v1/<feature>/…`). |
| `CP_ENTITLEMENT_CACHE_TTL_SECONDS` | `30.0` | — | Кэш решения. |
| `CP_ENTITLEMENT_DEGRADED_MAX_AGE_SECONDS` | `300.0` | — | Предельный возраст кэша при недоступности сервиса. |
| `CP_ENTITLEMENT_TIMEOUT_SECONDS` | `3.0` | — | Таймаут запроса. |

### Policy Decision Point

| Переменная | По умолчанию | В стеке | Назначение |
|---|---|---|---|
| `CP_AUTHZ_MODE` | `local` | `${CP_AUTHZ_MODE}` | `local` — только локальные права; `shadow` — решает локальная проверка, внешний PDP спрашивается параллельно, расхождения пишутся в журнал; `policy` — решает PDP для credential с IAM-субъектом. |
| `CP_POLICY_BASE_URL` | `http://localhost:8030` | — | Адрес PDP. |
| `CP_POLICY_SCOPES` | `["policy:check","policy:check-on-behalf"]` | — | Scopes токена. |
| `CP_POLICY_TIMEOUT_SECONDS` | `3.0` | — | Таймаут. |
| `CP_POLICY_CACHE_TTL_SECONDS` | `5.0` | — | Кэш решения. |

!!! tip "Списки в `CP_`-переменных — JSON"
    Поля-списки (`CP_CORS_ORIGINS`, `CP_KNOWLEDGE_PACK_ADMINS`,
    `CP_CONTEXT_IAM_SCOPES` и др.) pydantic-settings разбирает как JSON:
    `CP_CORS_ORIGINS='["https://platform.example.com"]'`. Строка через
    запятую приведёт к ошибке старта.

## iam-service (`IAM_`)

| Переменная | По умолчанию | В стеке | Назначение |
|---|---|---|---|
| `IAM_DATABASE_URL` | `postgresql+psycopg://iam:iam@localhost:5435/iam` | `…@iam-db:5432/iam` | БД IAM. |
| `IAM_BOOTSTRAP_TOKEN` | `""` | `${IAM_BOOTSTRAP_TOKEN}` | Токен bootstrap-эндпоинтов (`X-IAM-Bootstrap-Token`). |
| `IAM_ISSUER` | `http://localhost:8010` | `${TAIMEN_PUBLIC_URL}/iam` | Issuer выпускаемых токенов. |
| `IAM_TOKEN_TTL_SECONDS` | `300` | — | Время жизни access token. |
| `IAM_SIGNING_PRIVATE_KEY` | `""` | — | Приватный ключ подписи (PEM строкой); приоритетнее файла. |
| `IAM_SIGNING_PRIVATE_KEY_FILE` | `""` | `/run/secrets/iam_signing_key` | Файл приватного ключа. |
| `IAM_SIGNING_KEY_ID` | `local-dev` | `${IAM_SIGNING_KEY_ID}` | `kid` в JWKS. |
| `IAM_CREATE_SCHEMA_ON_STARTUP` | `false` | — | Создавать схему БД при старте (в стеке схему создаёт `alembic upgrade head`). |
| `IAM_PAT_DEFAULT_TTL_SECONDS` | `2592000` (30 дней) | — | Срок PAT, если `expiresInSeconds` не передан. |
| `IAM_PAT_MAX_TTL_SECONDS` | `31536000` (365 дней) | — | Потолок срока PAT; больше — `422 expiry_too_long`. |
| `IAM_PAT_MAX_AUTHENTICATION_AGE_SECONDS` | `300` | — | Предельный возраст authentication context человека для выпуска PAT; старше — `403 authentication_context_expired`. |
| `IAM_LEGACY_CREDENTIAL_MAX_TTL_SECONDS` | `7776000` (90 дней) | — | Окно совместимости для перенесённых legacy-ключей; больше — `422 compatibility_window_too_long`. |
| `IAM_SCIM_AUDIENCE` | `iam-scim` | — | Audience SCIM-клиента. |
| `IAM_SCIM_SCOPE` | `scim:write` | — | Scope SCIM-клиента. |
| `IAM_SCIM_MAX_PAGE_SIZE` | `200` | — | Предел страницы SCIM. |
| `IAM_CHANNEL_AUDIENCE` | `iam` | — | Audience самого IAM для каналов: им предъявляют токены человек (код привязки) и адаптер канала. |
| `IAM_CHANNEL_SCOPE` | `iam:channel-links` | — | Scope адаптера канала (подтверждение привязки, обмен нажатия). |
| `IAM_CHANNEL_LINK_CODE_TTL_SECONDS` | `600` | — | Срок кода привязки канала. |
| `IAM_CHANNEL_LINK_MAX_AUTHENTICATION_AGE_SECONDS` | `300` | — | Предельный возраст входа человека, запрашивающего код; старше — `403 authentication_context_expired`. |
| `IAM_CHANNEL_ASSERTION_AUDIENCE` | `control-plane` | — | Audience токена, выданного по нажатию в канале. |
| `IAM_CHANNEL_ASSERTION_SCOPE` | `control-plane:decide` | — | Единственный scope такого токена. |
| `IAM_CHANNEL_ASSERTION_TTL_SECONDS` | `60` | — | Срок токена по нажатию (не больше `IAM_TOKEN_TTL_SECONDS`). |
| `IAM_CHANNEL_LINK_INTENT_LIMIT`, `IAM_CHANNEL_LINK_INTENT_WINDOW_SECONDS` | `5`, `600` | — | Кодов привязки на человека в окне. |
| `IAM_CHANNEL_CONFIRM_FAILURE_LIMIT`, `IAM_CHANNEL_CONFIRM_FAILURE_WINDOW_SECONDS` | `10`, `600` | — | Неудачных подтверждений кода на адаптер в окне. |
| `IAM_CHANNEL_ASSERTION_LIMIT`, `IAM_CHANNEL_ASSERTION_WINDOW_SECONDS` | `10`, `60` | — | Обменов нажатия на привязку и отказов на адаптер в окне. |

## memory-service (`CB_`)

Колонка «В стеке» — значение из `deploy/local/compose.yml`.

### Хранилище и HTTP

| Переменная | По умолчанию | В стеке | Назначение |
|---|---|---|---|
| `CB_DATABASE_URL` | `""` → собирается из `POSTGRES_USER/PASSWORD/HOST/PORT/DB` | `postgresql://memory:…@memory-db:5432/company_brain` | БД (PostgreSQL + Apache AGE + pgvector). |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB` | `brain`, `brain`, `localhost`, `5432`, `company_brain` | — | Используются, только если `CB_DATABASE_URL` пуст. |
| `CB_GRAPH_NAME` | `company_brain` | — | Имя графа AGE. |
| `CB_CHUNKS_TABLE` | `chunks` | — | Таблица чанков. |
| `CB_DB_JIT` | `false` | — | JIT PostgreSQL для соединений сервиса; включать только под замер. |
| `CB_DEFAULT_NAMESPACE` | `nexus` | `main` | Namespace запросов без scope. |
| `CB_PROJECT_VALUES` | `""` | — | CSV разрешённых слагов проектов; пусто — проектные узлы не создаются. |
| `CB_SERVER_HOST` | `127.0.0.1` | — | Адрес HTTP-сервера при запуске встроенной точкой входа (`uvicorn.run`). |
| `CB_SERVER_PORT` | `8077` | — | Порт HTTP-сервера при запуске встроенной точкой входа. |
| `CB_SERVER_API_KEY` | `""` | `${MEMORY_API_KEY}` | Статический Bearer-ключ; задан — аутентификация обязательна. |
| `CB_API_KEYS` | `""` | — | JSON-реестр ключей с префиксными грантами на namespace (MEM-ADR-017). |
| `CB_CORE_ONLY` | `false` | — | Ограничить маршруты ядра (reconcile, packages, `namespaces/{ns}/kinds`) identity ядра. |
| `CB_CORE_IDENTITIES` | `""` | — | Метки identity ядра через запятую; задание включает ограничение. |
| `CB_QUERY_SYNTHESIZE_DEFAULT` | `false` | — | Синтезировать ответ LLM в `/query` по умолчанию. |
| `CB_VAULT_PATH` | `""` | — | Путь к vault заметок для ingest CLI. |
| `CB_CACHE_DIR` | `""` | — | Кэш ingest; пусто — выключен. |
| `CB_EXTRACT_ENTITIES` | `false` | — | Извлекать людей и организации из тел заметок через LLM. |
| `CB_RUN_AUDIT_ENABLED` | `true` | — | События жизненного цикла прогонов в граф-трейс. |

### Эмбеддинги, LLM, реранк

| Переменная | По умолчанию | В стеке | Назначение |
|---|---|---|---|
| `CB_EMBEDDING_PROVIDER` | `openai` | `${MEMORY_EMBEDDING_PROVIDER:-fake}` | `openai` или `fake`. |
| `CB_EMBEDDING_BASE_URL` | URL OpenAI-совместимого шлюза из кода | `${LLM_BASE_URL}` | Базовый URL эмбеддингов. |
| `CB_EMBEDDING_API_KEY` | `""` | `${LLM_API_KEY}` | Ключ. |
| `CB_EMBEDDING_MODEL` | `text-embedding-3-small` | `${MEMORY_EMBEDDING_MODEL}` | Модель. |
| `CB_EMBEDDING_DIM` | `1536` | `1536` | Размерность вектора. |
| `CB_EMBEDDING_TIMEOUT` | `25.0` | `60` | Таймаут вызова, секунды. |
| `CB_LLM_PROVIDER` | `openai` | `${MEMORY_LLM_PROVIDER:-echo}` | `openai` или `echo`. |
| `CB_LLM_BASE_URL` | URL из кода | `${LLM_BASE_URL}` | Базовый URL LLM. |
| `CB_LLM_API_KEY` | `""` | `${LLM_API_KEY}` | Ключ. |
| `CB_LLM_MODEL` | `gpt-4o-mini` | `${LLM_MODEL}` | Модель. |
| `CB_RERANK_ENABLED` | `false` | `${MEMORY_RERANK_ENABLED}` | Реранк кандидатов. |
| `CB_RERANK_PROVIDER` | `llm` | — | Провайдер реранка. |
| `CB_RERANK_POOL` | `20` | `20` | Размер пула до реранка. |
| `CB_RERANK_MODEL` | `""` (→ `CB_LLM_MODEL`) | — | Модель реранка. |

### IAM, policy, ПДн

| Переменная | По умолчанию | В стеке | Назначение |
|---|---|---|---|
| `CB_IAM_ENABLED` | `false` | `${MEMORY_IAM_ENABLED:-true}` | Принимать IAM-токены audience `memory-service`. |
| `CB_IAM_ISSUER` | `""` | `${TAIMEN_PUBLIC_URL}/iam` | Точный `iss`. |
| `CB_IAM_JWKS_URL` | `""` | `http://iam-service:8010/.well-known/jwks.json` | JWKS. |
| `CB_IAM_AUDIENCE` | `memory-service` | `memory-service` | Точный `aud`. |
| `CB_IAM_LEEWAY_SECONDS` | `5.0` | — | Допуск часов. |
| `CB_POLICY_ENABLED` | `false` | `${MEMORY_POLICY_ENABLED}` | Видимость по principal через внешний PDP. |
| `CB_POLICY_URL` | `http://localhost:8030` | — | Адрес PDP. |
| `CB_POLICY_TIMEOUT_SECONDS` | `3.0` | — | Таймаут. |
| `CB_POLICY_CACHE_TTL_SECONDS` | `5.0` | — | Кэш. |
| `CB_IAM_BASE_URL` | `""` | `http://iam-service:8010` | IAM для client credentials самого сервиса. |
| `CB_IAM_CLIENT_ID`, `CB_IAM_CLIENT_SECRET` | `""` | из `secrets/memory-service-iam.env` | Service account памяти (для вызова внешнего PDP). |
| `CB_PII_PROTECTION` | `false` | `true` | Защита ПДн: без полного допуска выдача маскируется. |
| `CB_SERVER_API_KEYS_PII` | `""` | `""` | Ключи с полным допуском к ПДн, через запятую. |

### Console, демо-витрина, Context Compiler

| Переменная | По умолчанию | В стеке | Назначение |
|---|---|---|---|
| `CB_CONSOLE_ENABLED` | `false` | `${MEMORY_CONSOLE_ENABLED}` | Memory Console (`/console`). Своей аутентификации нет — закрывайте прокси. |
| `CB_CONSOLE_NAMESPACES` | `""` (→ `CB_DEFAULT_NAMESPACE`) | `""` | CSV-allowlist баз знаний Console. |
| `CB_DEMO_PUBLIC_ENABLED` | `false` | — | Публичная витрина `/demo`. Не включать на данных клиента. |
| `CB_DEMO_NAMESPACE` | `demo` | — | Единственная KB витрины. |
| `CB_DEMO_RATE_LIMIT` | `30` | — | Запросов в минуту с IP к `/demo/api/*`; `0` — без лимита. |
| `CB_DEMO_SEARCH_K` | `5` | — | Top-k витрины. |
| `CB_DEMO_BRAND_NAME`, `CB_DEMO_BRAND_TAGLINE`, `CB_DEMO_CTA_URL`, `CB_DEMO_DOMAIN` | нейтральные значения | — | Оформление витрины. |
| `CB_DEMO_RERANK` | `true` | — | Реранк поиска витрины. |
| `CB_DEMO_MIN_CONFIDENCE` | `0.3` | — | Порог `rerank_score` карточек витрины. |
| `CB_OBSERVATIONS_TABLE` | `observations` | — | Таблица наблюдений. |
| `CB_CONTEXT_TRACES_TABLE` | `context_traces` | — | Таблица трасс сборки контекста. |
| `CB_OBSERVATIONS_EMBED` | `false` | — | Эмбеддить наблюдения при ingest. |
| `CB_OBSERVATIONS_MAX_BATCH` | `500` | — | Предел пачки наблюдений; больше — `413`. |
| `CB_CONTEXT_DEFAULT_MAX_TOKENS` | `8000` | — | Бюджет ContextPack по умолчанию. |
| `CB_CONTEXT_CHARS_PER_TOKEN` | `3.0` | — | Оценка символов на токен. |
| `CB_CONTEXT_MAX_DEPTH` | `2` | — | Глубина graph expansion. |
| `CB_CONTEXT_MAX_NODES` | `60` | — | Предел узлов. |
| `CB_CONTEXT_MAX_EDGES` | `120` | — | Предел рёбер. |
| `CB_DOMAIN_PACKS_TABLE` | `domain_packs` | — | Реестр доменных пакетов видов. |
| `CB_NAMESPACE_SETTINGS_TABLE` | `namespace_settings` | — | Настройки видов namespace. |
| `CB_SNAPSHOTS_TABLE` | `source_snapshots` | — | Журнал снимков источников. |
| `CB_RECONCILE_MAX_ITEMS` | `20000` | — | Предел сущностей и фактов в одном снимке reconcile. |

## notification-service (`NS_`) {#notification-service}

Профиль `notify`. См. [Уведомления](../notifications/index.md) и
[Telegram](../notifications/telegram.md).

| Переменная | По умолчанию | В стеке | Назначение |
|---|---|---|---|
| `NS_HOST`, `NS_PORT` | `0.0.0.0`, `8000` | — | Адрес и порт HTTP (читает точка входа `notification-service`). |
| `NS_DATABASE_URL` | `postgresql+psycopg://notify:notify@localhost:5432/notify` | `…@notification-db:5432/notify` | БД. |
| `NS_IAM_URL` | `""` | `http://iam-service:8010` | IAM: client credentials service account'а. |
| `NS_IAM_ISSUER` | `""` | `${TAIMEN_PUBLIC_URL}/iam` | Issuer токенов; без него и JWKS все маршруты `/api/v1` — `503`. |
| `NS_IAM_JWKS_URL` | `""` (иначе `<NS_IAM_URL>/.well-known/jwks.json`) | `http://iam-service:8010/.well-known/jwks.json` | JWKS. |
| `NS_AUDIENCE` | `notification-service` | `notification-service` | Собственный audience. |
| `NS_CONTROL_PLANE_URL` | `""` | `http://control-plane-api:8000` | Ядро: каталог адресатов, события, решения. |
| `NS_SERVICE_CLIENT_ID`, `NS_SERVICE_CLIENT_SECRET` | `""` | из `secrets/notification-iam.env` | Service account сервиса. |
| `NS_EVENTS_ENABLED` | `true` | — | Потребитель событий ядра. |
| `NS_EVENTS_START` | `latest` | — | Откуда начать при первом запуске: `latest` или `earliest`. |
| `NS_EVENTS_WORKSPACE_ID` | `""` | — | Поддерево workspace; пусто — весь tenant. |
| `NS_EVENTS_POLL_SECONDS` | `30.0` | — | Период опроса журнала (WebSocket будит раньше). |
| `NS_WORKER_ENABLED` | `true` | — | Воркер доставки в процессе API. |
| `NS_WORKER_POLL_SECONDS` | `1.0` | — | Период опроса очереди доставок. |
| `NS_WORKER_BATCH_SIZE` | `50` | — | Доставок за проход. |
| `NS_WORKER_LEASE_SECONDS` | `120.0` | — | Аренда доставки; отправка ограничена половиной аренды. |
| `NS_DELIVERY_MAX_ATTEMPTS` | `8` | — | Попыток на доставку. |
| `NS_DELIVERY_BACKOFF_SECONDS`, `NS_DELIVERY_BACKOFF_MAX_SECONDS` | `5.0`, `3600.0` | — | Экспоненциальная пауза между попытками и её потолок. |
| `NS_EMAIL_MODE` | `log` | — | `smtp`, `log` (только лог) или `disabled` (канала нет). |
| `NS_EMAIL_FROM` | `notifications@localhost` | `${NOTIFY_EMAIL_FROM}` | Отправитель писем. |
| `NS_SMTP_HOST`, `NS_SMTP_PORT` | `localhost`, `587` | `${NOTIFY_SMTP_HOST}`, `${NOTIFY_SMTP_PORT}` | SMTP-сервер. |
| `NS_SMTP_STARTTLS` | `true` | — | STARTTLS. |
| `NS_SMTP_USERNAME`, `NS_SMTP_PASSWORD` | `""` | — | Учётные данные SMTP. |
| `NS_SMTP_TIMEOUT_SECONDS` | `10.0` | — | Таймаут SMTP. |
| `NS_TELEGRAM_BOT_TOKEN` | `""` | из `secrets/notification-telegram.env` | Токен бота; без него канала `telegram` нет. |
| `NS_TELEGRAM_WEBHOOK_SECRET` | `""` | из `secrets/notification-telegram.env` | Секрет вебхука (`secret_token` в `setWebhook`). |
| `NS_TELEGRAM_BOT_USERNAME` | `""` | из `secrets/notification-telegram.env` | Имя бота без `@`: команды и ссылки привязки групп. |
| `NS_TELEGRAM_API_URL` | `https://api.telegram.org` | — | Bot API. |
| `NS_TELEGRAM_TIMEOUT_SECONDS` | `10.0` | — | Таймаут Bot API. |
| `NS_CHANNEL_GROUP_CODE_TTL_SECONDS` | `600` | — | Срок кода привязки группы. |
| `NS_IAM_CHANNEL_AUDIENCE`, `NS_IAM_CHANNEL_SCOPE` | `iam`, `iam:channel-links` | — | Сервис как адаптер канала в IAM. |
| `NS_INBOX_POLL_SECONDS` | `5.0` | — | Как часто простаивающий поток SSE сверяется с базой. |
| `NS_INBOX_KEEPALIVE_SECONDS` | `15.0` | — | Keep-alive потока SSE. |

## fleet-controller (`FLEET_`) {#fleet-controller}

Профиль `fleet`. Переменные читаются напрямую из окружения
(`fleet_controller/wiring.py`); значения задаёт `deploy/local/compose.yml`, client
credentials — `secrets/fleet-iam.env`.

| Переменная | В `deploy/local/compose.yml` | По умолчанию в коде | Назначение |
|---|---|---|---|
| `FLEET_DATA_DIR` | `/data` | `/data` | Каталог SQLite `fleet.sqlite` (volume `fleet_data`). |
| `FLEET_CONTROL_PLANE_URL` | `http://control-plane-api:8000` | — | Control Plane внутри сети. |
| `FLEET_IAM_URL` | `http://iam-service:8010` | — | IAM внутри сети: client credentials, агенты и их PAT (`iam:agents`). |
| `FLEET_IAM_ISSUER` | `${TAIMEN_PUBLIC_URL}/iam` | — (обязательна) | Публичный issuer IAM: с ним привязываются личности агентов и проверяются административные токены. |
| `FLEET_IAM_TENANT` | `${IAM_TENANT_ID:-}` | — | IAM tenant агентов. |
| `FLEET_JWKS_URL` | `http://iam-service:8010/.well-known/jwks.json` | — (обязательна) | JWKS для проверки административных токенов. |
| `FLEET_CLIENT_ID`, `FLEET_CLIENT_SECRET` | из `secrets/fleet-iam.env` | пусто | Service account контроллера. Без них все маршруты, кроме `/healthz`, — `503 not_configured`. |
| `FLEET_AUDIENCE` | — | `fleet` | Audience административных токенов (`fleet:read`, `fleet:admin`). |
| `FLEET_TOKEN_AUDIENCES` | см. `deploy/local/compose.yml` | `control-plane` | Audiences, которые может получить PAT агента (через пробел); сверх `control-plane` — только те, что агент просит в `skills.audiences` или `identity.iam.audiences`. |
| `FLEET_TOKEN_SCOPES` | см. `deploy/local/compose.yml` | `control-plane:read control-plane:write` | Потолок scope PAT агентов (через пробел). Агент получает только scopes выданных ему audiences, а при объявленном `identity.iam.scopeCeiling` — пересечение с ним; привилегированный scope (`iam:…`) — только объявившему его агенту; scope не своей по префиксу audience пишется `audience=scope`. |
| `FLEET_TOKEN_TTL_SECONDS` | — | `604800` (7 дней) | Срок PAT агента; не больше `IAM_AGENT_PAT_MAX_TTL_SECONDS`, иначе IAM ответит `422 expiry_too_long`. Новый PAT выпускается за 2 дня до истечения и пересоздаёт контейнер агента. |

Узел `fleet-node` переменных с префиксом не читает: вся его конфигурация — файл
`node.yaml`, в котором `${ИМЯ}` подставляется из окружения процесса узла (см.
[Узлы и fleet](../runner/fleet.md#node-yaml)).


## Runner-агент и клиенты Control Plane {#runner-and-clients}

Процессы вне compose платформы: демон `control-plane-agent`, адаптер
OpenCode, CLI `control-plane`, MCP-сервер `control-plane-mcp` и библиотека
`control_plane_client`. Переменные читаются напрямую из окружения. Демон
агента, описанного видом `Agent`, берёт настройки агента из своей ревизии, а
переменные хоста ему задаёт узел fleet (`agentEnv` и `executors.<вид>.env` в
`node.yaml`); какие переменные действуют в каком режиме — в [Конфигурации
исполнителя](../runner/configuration.md).

### Подключение и identity

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `CONTROL_PLANE_SERVER` | — | Адрес Control Plane (`https://platform.example.com`). Обязательна для демона и адаптера OpenCode; CLI и MCP-сервер берут её, если нет `--server`, и затем ищут `.control-plane/config.json`. |
| `CONTROL_PLANE_IAM_URL` | — | Адрес IAM (`https://platform.example.com/iam`). Не задан — клиент считает IAM не настроенным и переходит к legacy-ключу. |
| `CONTROL_PLANE_IAM_TENANT` | — | IAM tenant. Задан URL без tenant — ошибка `iam_tenant_required`. |
| `CONTROL_PLANE_IAM_AUDIENCE` | `control-plane` | Audience обмена PAT. |
| `CONTROL_PLANE_IAM_SCOPES` | пусто (= весь потолок PAT ∩ audience) | Scopes через пробел или запятую. В env-файле со значением через пробел — кавычки. |
| `IAM_PLATFORM_ACCESS_TOKEN` | — | PAT из окружения. Работает только вместе с `IAM_CREDENTIAL_MODE`. |
| `IAM_CREDENTIAL_MODE` | — | `environment` или `ci` — разрешить PAT из переменной. Без него — `iam_environment_mode_required`. |
| `IAM_PRINCIPAL` | — | Какой principal этот процесс, если на машине в хранилище несколько credential одного issuer+tenant. Не задан при нескольких — `iam_credential_ambiguous`. |
| `IAM_NO_KEYCHAIN` | — | `1` — не обращаться к Keychain macOS за PAT. |
| `XDG_CONFIG_HOME` | `~/.config` | База путей `iam/credentials.json` (файл PAT, права `600`) и `services/control-plane/credentials.json` (legacy-ключи). |
| `CONTROL_PLANE_API_KEY` | — | Legacy-ключ `cp_…` (только если на сервере включены legacy-ключи). |
| `CONTROL_PLANE_NO_KEYCHAIN` | — | `1` — не искать legacy-ключ в Keychain. |

!!! warning "Удалённые переменные"
    `TAIMEN_API_KEY`, `TAIMEN_SERVER`, `TAIMEN_NO_KEYCHAIN`,
    `TAIMEN_AGENT_ADAPTER`, `TAIMEN_AGENT_WORKSPACE`, `TAIMEN_AGENT_POLL`
    больше не читаются. Клиент распознаёт их только чтобы сообщить имя
    замены: `CONTROL_PLANE_*`.

### Демон исполнителя

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `CONTROL_PLANE_AGENT_CONFIG` | `auto` | Откуда конфигурация: `auto` — ревизия агента, если principal привязан к агенту, иначе окружение; `revision` — только ревизия; `env` — только окружение. |
| `CONTROL_PLANE_AGENT_MIRRORS` | `<WORKTREE_ROOT>/.mirrors` | Каталог bare-зеркал репозиториев ревизии (режим ревизии). |
| `CONTROL_PLANE_AGENT_DRAIN_SECONDS` | — | Режим env: сколько ждать прогон в полёте на `SIGTERM`; в режиме ревизии — `placement.drainSeconds`. |
| `CONTROL_PLANE_AGENT_CONTROL_POLL_SECONDS` | `15` | Как часто сторож читает прогон ради запроса отмены (не реже раза в 30 с). |
| `CONTROL_PLANE_AGENT_STALL_WARN_SECONDS` | `600` | Без новых actions — checkpoint `stall`; `0` отключает. |
| `CONTROL_PLANE_AGENT_STALL_STOP_SECONDS` | `1800` | Без новых actions — остановка, run `no_progress`; `0` отключает. |
| `CONTROL_PLANE_AGENT_ACTION_MAX_SECONDS` | `3600` | Сколько живёт незавершённое последнее action до остановки сторожем. |
| `CONTROL_PLANE_AGENT_ADAPTER` | `echo` | Адаптер: `echo`, `claude-code`, `codex` (режим env). |
| `CONTROL_PLANE_AGENT_WORKSPACE` | — | Workspace Control Plane, из которого брать задачи. Без него фильтра по workspace нет: демон берёт любую доступную ему задачу — для проверок заводите отдельный workspace. |
| `CONTROL_PLANE_AGENT_PROJECT` | — | Ограничить задачи проектом. |
| `CONTROL_PLANE_AGENT_SUBPROJECTS` | — | `1` — включая подпроекты. |
| `CONTROL_PLANE_AGENT_ONLY_ASSIGNED` | — | `1` — только задачи, назначенные этому principal. |
| `CONTROL_PLANE_AGENT_POLL` | `5` | Период опроса, секунды. |
| `CONTROL_PLANE_AGENT_REPO` | — | Git-репозиторий (обычно bare-зеркало), из которого делаются рабочие копии. Вместе с `…_WORKTREE_ROOT` включает пул рабочих копий. |
| `CONTROL_PLANE_AGENT_WORKTREE_ROOT` | — | Каталог рабочих копий. |
| `CONTROL_PLANE_AGENT_BASE_REF` | `HEAD` | Ревизия, от которой создаётся ветка задачи. |
| `CONTROL_PLANE_AGENT_KEEP_WORKSPACES` | — | `1` — не удалять рабочую копию после успеха. |
| `CONTROL_PLANE_AGENT_MAX_WORKSPACES` | `8` | Предел рабочих копий. |
| `CONTROL_PLANE_AGENT_PUSH_REMOTE` | `""` | Remote для публикации ветки задачи. Пусто — ветка остаётся локальной. |
| `CONTROL_PLANE_AGENT_REPO_DIR` | `""` | Имя каталога репозитория внутри рабочей копии-контейнера. |
| `CONTROL_PLANE_AGENT_NEIGHBOURS` | `""` | Соседние репозитории: `имя=путь-к-зеркалу` через запятую. |
| `CONTROL_PLANE_AGENT_SUPERPROJECT` | — | Зеркало суперпроекта, закрепляющего ревизии соседей. |
| `CONTROL_PLANE_AGENT_SUPERPROJECT_REF` | `HEAD` | Ревизия суперпроекта. |
| `CONTROL_PLANE_AGENT_SUPERPROJECT_REMOTE` | `""` | Remote суперпроекта для fetch. |
| `CONTROL_PLANE_CONTEXT_BUDGET_CHARS` | `12000` | Бюджет раздела «Контекст задачи» в prompt, символов. |
| `CONTROL_PLANE_TRACE_TRANSCRIPT` | включено | `0`/`false`/`no`/`off` — не публиковать артефакт `transcript`. |
| `CONTROL_PLANE_TRACE_ACTIONS` | включено | Не писать run actions `tool.<имя>`. |
| `CONTROL_PLANE_TRACE_TOOL_RESULTS` | включено | Не сохранять результаты вызовов инструментов в трассе. |

### Скиллы в демоне

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `CONTROL_PLANE_SKILLS_PROTOCOLS` | `local`, если заданы пакеты, иначе ничего | Какие протоколы исполнять: `local`, `http`, `mcp`. |
| `CONTROL_PLANE_SKILLS_LOCAL_PACKAGES` | — | Entrypoints или пакеты локальных скиллов. |
| `CONTROL_PLANE_SKILLS_LOCAL_ISOLATION` | `process` | `process` или `thread`. |
| `CONTROL_PLANE_SKILLS_HTTP_ALLOWED_ORIGINS` | — | `scheme://host[:port]` через запятую; без них протокол `http` не запускается. |
| `CONTROL_PLANE_SKILLS_MCP_ALLOWED_ORIGINS` | — | То же для `mcp`; без них `mcp` работает только со `stdio`-серверами. |
| `CONTROL_PLANE_SKILLS_MCP_SERVERS` | `{}` | JSON `{имя: {command, args, env}}` для endpoint'ов `stdio:<имя>`. |
| `CONTROL_PLANE_SKILLS_PRIVATE_HOSTS` | — | Хосты разрешённых origins, которым можно резолвиться в непубличные адреса. |
| `CONTROL_PLANE_SKILLS_ALLOWED_AUDIENCES` | — | IAM audiences, токен которых может получить скилл (никогда `control-plane`, `iam` и собственный). |
| `CONTROL_PLANE_SKILLS_CONCURRENCY` | `1` | Одновременных вызовов рядом с Work; `0` — только когда Work нет. |

### Адаптеры кодовых агентов

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `CONTROL_PLANE_CLAUDE_BINARY` | `claude` | Исполняемый файл Claude Code. |
| `CONTROL_PLANE_CLAUDE_MODEL` | — | Модель. |
| `CONTROL_PLANE_CLAUDE_PERMISSION_MODE` | `acceptEdits` | Режим разрешений Claude Code. |
| `CONTROL_PLANE_CLAUDE_TIMEOUT` | `3600` | Таймаут run, секунды. |
| `CONTROL_PLANE_CLAUDE_RESUME` | `1` | Возобновлять сессии. |
| `CONTROL_PLANE_CLAUDE_MCP` | `1` | `1` — записать `mcp.json` в каталог runtime и подключить MCP-сервер Control Plane к Claude Code. |
| `CONTROL_PLANE_CLAUDE_LOGS` | `1` | `1` — журналы сессий в `<runtime>/sessions`. |
| `CONTROL_PLANE_CLAUDE_RUNTIME_DIR` | `~/.claude-runner` | Каталог runtime адаптера. |
| `CONTROL_PLANE_CLAUDE_PROMPT_FILE` | — | Файл соглашений, добавляемый в каждый prompt. |
| `CLAUDE_CODE_OAUTH_TOKEN` | — | Токен подписки Claude Code (читает сам CLI `claude`). |
| `CONTROL_PLANE_CODEX_BINARY` | `codex` | Исполняемый файл Codex. |
| `CONTROL_PLANE_CODEX_MODEL` | — | Модель. |
| `CONTROL_PLANE_CODEX_SANDBOX` | `workspace-write` | Режим песочницы Codex. |
| `CONTROL_PLANE_CODEX_TIMEOUT` | `3600` | Таймаут. |
| `CONTROL_PLANE_CODEX_RESUME` | `1` | Возобновлять сессии. |
| `CONTROL_PLANE_CODEX_LOGS` | `1` | `1` — журналы сессий в `<runtime>/sessions`. |
| `CONTROL_PLANE_CODEX_RUNTIME_DIR` | `~/.codex-runner` | Каталог runtime. |
| `CONTROL_PLANE_CODEX_CREDENTIAL_CLASS` | — | Класс credential адаптера Codex. |
| `OPENCODE_SERVER` | `http://127.0.0.1:4096` | Сервер OpenCode (адаптер `control-plane-opencode`). |
| `OPENCODE_SERVER_PASSWORD` | — | Пароль сервера OpenCode. |
| `OPENCODE_MODEL`, `OPENCODE_AGENT` | — | Модель и агент OpenCode. |
| `CP_LOG_LEVEL` | `INFO` | Уровень логов адаптера OpenCode. |

### MCP-сервер

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `CONTROL_PLANE_HARNESS_TYPE` | `mcp-client` | Тип харнесса при открытии сессии (`[a-z0-9][a-z0-9._-]{0,99}`), иначе `invalid_harness_configuration`. |
| `CONTROL_PLANE_HARNESS_VERSION` | версия пакета | Версия харнесса. |
| `CONTROL_PLANE_HARNESS_CLIENT_NAME` | `control-plane-mcp` | Имя клиента. |

## Прочие процессы

| Процесс | Переменные |
|---|---|
| skill-sdk (хостинг скиллов) | `SKILL_SDK_IAM_ISSUER`, `SKILL_SDK_AUDIENCE`, `SKILL_SDK_JWKS_URL` — проверка токена IAM в режимах `http` и `mcp-http` (без них — только `--allow-anonymous`); `SKILL_LLM_BASE_URL`, `SKILL_LLM_API_KEY`, `SKILL_LLM_MODELS` (CSV) — LLM контекста скилла. |
| Human Harness | `IAM_CREDENTIAL_MODE`, `IAM_PLATFORM_ACCESS_TOKEN` — тот же контракт PAT из окружения, что у клиента Control Plane. |
| `deploy/bootstrap.py` | Читает из `.env`: `TAIMEN_PUBLIC_URL`, `COMPOSE_PROJECT_NAME`, `CP_HOST_PORT`, `IAM_HOST_PORT`, `IAM_TENANT_ID`, `CP_BOOTSTRAP_TOKEN`, `IAM_BOOTSTRAP_TOKEN`. |

## Файлы `secrets/*.env`, которые пишет bootstrap

| Файл | Переменные | Кто читает |
|---|---|---|
| `secrets/control-plane-iam.env` | `CP_IAM_CLIENT_ID`, `CP_IAM_CLIENT_SECRET` | `control-plane-api`, `control-plane-worker`, `context-adapter` |
| `secrets/notification-iam.env` | `NS_SERVICE_CLIENT_ID`, `NS_SERVICE_CLIENT_SECRET` | `notification-service` |
| `secrets/fleet-iam.env` | `FLEET_CLIENT_ID`, `FLEET_CLIENT_SECRET` | `fleet-controller` |

Файл `secrets/notification-telegram.env` (`NS_TELEGRAM_BOT_TOKEN`,
`NS_TELEGRAM_WEBHOOK_SECRET`, `NS_TELEGRAM_BOT_USERNAME`) bootstrap не пишет —
его заполняет оператор, см. [Telegram](../notifications/telegram.md).
Необязательный `secrets/memory-service-iam.env` (`CB_IAM_CLIENT_ID`,
`CB_IAM_CLIENT_SECRET`, service identity памяти для вызова внешнего PDP) bootstrap
тоже не пишет — он кладётся вместе с подключением внешнего PDP, который в поставку
не входит.

После появления файла соответствующий контейнер нужно пересоздать
(`tools/compose up -d <сервис>`): `env_file` читается при создании
контейнера.

## Сводка: все переменные `deploy/local/compose.yml` и `.env.example`

Проверочный перечень к таблицам выше: каждая переменная, которую интерполирует
`deploy/local/compose.yml` или объявляет `.env.example`, с сервисами и профилями, где она
используется. Колонка «Описана выше» — есть ли у переменной строка в
рукописных таблицах этой страницы; «**нет**» — повод дописать описание.

<!-- generated:env-summary -->
_Раздел генерируется из кода — не правьте его руками._

Всего переменных: 148 (в `deploy/local/compose.yml` — 123, в `.env.example` — 110). Не описаны в таблицах выше: 7.

| Переменная | По умолчанию в compose | Сервисы | Профили | `.env.example` | Описана выше |
|---|---|---|---|---|---|
| `CADDYFILE` | `./deploy/caddy/Caddyfile.local` | caddy | edge | да | да |
| `COMPOSE_PROJECT_NAME` | `taimen` | (volumes) | — | да | да |
| `CP_AUTHZ_MODE` | `local` | context-adapter, control-plane-api, control-plane-worker | core | да | да |
| `CP_BOOTSTRAP_TOKEN` | — | control-plane-api | core | да | да |
| `CP_BUILD_CONTEXT` | `.` | control-plane-api | core | — | да |
| `CP_CONTEXT_AUTH` | `auto` | context-adapter, control-plane-api, control-plane-worker | core | да | да |
| `CP_CONTEXT_TIMEOUT_SECONDS` | `3` | control-plane-api | core | — | да |
| `CP_CORS_ORIGINS` | `[]` | control-plane-api | core | да | да |
| `CP_HOST_PORT` | `18000` | control-plane-api | core | да | да |
| `CP_KNOWLEDGE_PACK_ADMINS` | `[]` | control-plane-api | core | да | да |
| `CP_LEGACY_API_KEYS_ENABLED` | `false` | control-plane-api | core | да | да |
| `CP_MEM_LIMIT` | `512m` | control-plane-api | core | да | да |
| `CP_POSTGRES_PASSWORD` | — | context-adapter, control-plane-api, control-plane-db, control-plane-worker | core | да | да |
| `CP_S3_ACCESS_KEY_ID` | — | context-adapter, control-plane-api, control-plane-worker, minio-bootstrap | core | да | да |
| `CP_S3_BUCKET` | `artifacts` | context-adapter, control-plane-api, control-plane-worker, minio-bootstrap | core | да | да |
| `CP_S3_ENDPOINT_URL` | `http://minio:9000` | context-adapter, control-plane-api, control-plane-worker | core | да | да |
| `CP_S3_REGION` | `us-east-1` | context-adapter, control-plane-api, control-plane-worker | core | да | да |
| `CP_S3_SECRET_ACCESS_KEY` | — | context-adapter, control-plane-api, control-plane-worker, minio-bootstrap | core | да | да |
| `CP_TIMEZONE` | — | — | — | да | да |
| `CP_WORKER_MEM_LIMIT` | `256m` | context-adapter, control-plane-worker | core | — | да |
| `EDGE_HTTPS_PORT` | `443` | caddy | edge | да | да |
| `EDGE_HTTP_PORT` | `80` | caddy | edge | да | да |
| `FLEET_BUILD_CONTEXT` | `.` | fleet-controller | fleet | — | да |
| `FLEET_MEM_LIMIT` | `128m` | fleet-controller | fleet | да | да |
| `HARNESS_APP_NAME` | `Human Harness` | harness-launcher | harness | — | да |
| `HARNESS_CONTROL_NETWORK` | `${COMPOSE_PROJECT_NAME:-taimen` | (networks) | — | — | да |
| `HARNESS_COOKIE_SECRET_FILE` | `./secrets/harness/cookie-secret` | (secrets) | — | — | да |
| `HARNESS_CPUS` | `1` | harness-launcher | harness | — | да |
| `HARNESS_IDLE_MINUTES` | `30` | harness-launcher | harness | — | да |
| `HARNESS_MEM_LIMIT_MB` | `1536` | harness-launcher | harness | — | да |
| `HARNESS_PEOPLE_NETWORK` | `${COMPOSE_PROJECT_NAME:-taimen` | (networks), harness-launcher | harness | — | да |
| `HARNESS_PIDS_LIMIT` | `512` | harness-launcher | harness | — | да |
| `IAM_BOOTSTRAP_TOKEN` | — | iam-service | core | да | да |
| `IAM_BUILD_CONTEXT` | `./services/iam-service` | iam-service | core | — | да |
| `IAM_HOST_PORT` | `18010` | iam-service | core | да | да |
| `IAM_MEM_LIMIT` | `256m` | iam-service | core | — | да |
| `IAM_POSTGRES_PASSWORD` | — | iam-db, iam-service | core | да | да |
| `IAM_SIGNING_KEY_FILE` | `./secrets/iam-signing.pem` | (secrets) | — | да | да |
| `IAM_SIGNING_KEY_ID` | `local-dev` | iam-service | core | да | да |
| `IAM_TENANT_ID` | пусто | console, fleet-controller, harness-launcher | core, fleet, harness | да | да |
| `KEYCLOAK_ADMIN` | `admin` | keycloak | idp | да | да |
| `KEYCLOAK_ADMIN_PASSWORD` | — | keycloak | idp | да | да |
| `KEYCLOAK_DB_PASSWORD` | — | keycloak, keycloak-db | idp | да | да |
| `KEYCLOAK_HOSTNAME_STRICT` | `true` | keycloak | idp | да | да |
| `KEYCLOAK_HOST_PORT` | `18081` | keycloak | idp | да | да |
| `KEYCLOAK_IMAGE` | `quay.io/keycloak/keycloak:26.5.2` | keycloak | idp | да | **нет** |
| `KEYCLOAK_MEM_LIMIT` | `768m` | keycloak | idp | да | да |
| `LOG_LEVEL` | `INFO` | context-adapter, control-plane-api, control-plane-worker | core | да | да |
| `LOG_RENDERER` | — | — | — | да | да |
| `MEMORY_BUILD_CONTEXT` | `.` | memory-db, memory-service | core | — | да |
| `MEMORY_CONSOLE_ENABLED` | `false` | memory-service | core | да | да |
| `MEMORY_DB_MEM_LIMIT` | `512m` | memory-db | core | — | да |
| `MEMORY_EMBEDDING_MODEL` | `text-embedding-3-small` | memory-service | core | — | да |
| `MEMORY_EMBEDDING_PROVIDER` | `fake` | memory-service | core | да | да |
| `MEMORY_HOST_PORT` | `18001` | memory-service | core | да | да |
| `MEMORY_IAM_ENABLED` | `true` | memory-service | core | да | да |
| `MEMORY_LLM_PROVIDER` | `echo` | memory-service | core | да | да |
| `MEMORY_MEM_LIMIT` | `512m` | memory-service | core | — | да |
| `MEMORY_POLICY_ENABLED` | `false` | memory-service | core | да | да |
| `MEMORY_POSTGRES_PASSWORD` | — | memory-db, memory-service | core | да | да |
| `MEMORY_RERANK_ENABLED` | `false` | memory-service | core | да | да |
| `MINIO_MEM_LIMIT` | `256m` | minio | core | — | да |
| `NOTIFICATION_SERVICE_URL` | — | — | — | да | да |
| `NOTIFY_BUILD_CONTEXT` | `.` | notification-service | notify | — | да |
| `NOTIFY_DB_MEM_LIMIT` | `128m` | notification-db | notify | — | да |
| `NOTIFY_EMAIL_FROM` | `notifications@localhost` | notification-service | notify | — | да |
| `NOTIFY_HARNESS_LAUNCHER_URL` | `http://harness-launcher:8080/harness` | notification-service | notify | — | да |
| `NOTIFY_HOST_PORT` | `18045` | notification-service | notify | — | да |
| `NOTIFY_MEM_LIMIT` | `256m` | notification-service | notify | — | да |
| `NOTIFY_POSTGRES_PASSWORD` | — | notification-db, notification-service | notify | да | да |
| `NOTIFY_SMTP_HOST` | `localhost` | notification-service | notify | — | да |
| `NOTIFY_SMTP_PORT` | `587` | notification-service | notify | — | да |
| `PG_MEM_LIMIT` | `256m` | control-plane-db, iam-db, keycloak-db | core, idp | — | да |
| `RUNTIME_CONSOLE_COOKIE_SECRET_FILE` | `./secrets/runtime-console-cookie-secret` | (secrets) | — | да | да |
| `RUNTIME_CONSOLE_CP_SCOPES` | `control-plane:read control-plane:write` | console | core | да | да |
| `RUNTIME_CONSOLE_DEFAULT_LOCALE` | `en` | console | core | да | да |
| `RUNTIME_CONSOLE_IDENTITY_PROVIDER` | `keycloak` | console | core | да | да |
| `RUNTIME_CONSOLE_IDP_ADMIN` | `off` | console | core | да | **нет** |
| `RUNTIME_CONSOLE_KEYCLOAK_URL` | пусто | console | core | да | **нет** |
| `RUNTIME_CONSOLE_LOCALES` | `en,ru` | console | core | да | да |
| `RUNTIME_CONSOLE_OIDC_CLIENT_ID` | `runtime-console` | console | core | да | да |
| `RUNTIME_CONSOLE_OIDC_ISSUER` | `${TAIMEN_PUBLIC_URL` | console | core | да | да |
| `RUNTIME_CONSOLE_OIDC_SCOPES` | `openid profile email` | console | core | да | да |
| `RUNTIME_CONSOLE_OIDC_SECRET_FILE` | `./secrets/runtime-console-oidc-secret` | (secrets) | — | да | да |
| `RUNTIME_CONSOLE_ORG_NAME` | пусто | console | core | да | да |
| `RUNTIME_CONSOLE_PEOPLE_SECRET_FILE` | `./secrets/runtime-console-people-secret` | (secrets) | — | — | **нет** |
| `RUNTIME_CONSOLE_PRODUCT_NAME` | `Console` | console | core | да | да |
| `RUNTIME_CONSOLE_SESSION_TTL_HOURS` | `12` | console | core | да | да |
| `S3_ACCESS_KEY_ID` | — | minio, minio-bootstrap | core | да | да |
| `S3_SECRET_ACCESS_KEY` | — | minio, minio-bootstrap | core | да | да |
| `TAIMEN_NETWORK` | `taimen_default` | (networks) | — | да | да |
| `TAIMEN_PUBLIC_HOST` | `taimen.localhost` | caddy, harness-launcher | edge, harness | да | да |
| `TAIMEN_PUBLIC_URL` | — | console, control-plane-api, dex-render, fleet-controller, harness-launcher, iam-service, keycloak, memory-service, notification-service, realm-render | core, fleet, harness, idp, idp-dex, notify | да | да |
| `TASK_URL_BASE` | — | — | — | да | да |
| `VOLUME_CADDY_CONFIG` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | да | да |
| `VOLUME_CADDY_DATA` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | да | да |
| `VOLUME_CONSOLE_SESSIONS` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | — | **нет** |
| `VOLUME_CONTROL_PLANE_DB` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | да | да |
| `VOLUME_FLEET_DATA` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | да | да |
| `VOLUME_HARNESS_LAUNCHER` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | — | да |
| `VOLUME_IAM_DB` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | да | да |
| `VOLUME_KEYCLOAK_DB` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | да | да |
| `VOLUME_MEMORY_DB` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | да | да |
| `VOLUME_NOTIFY_DB` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | — | да |
| `VOLUME_PLATFORM_MINIO` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | да | да |
| `VOLUME_REALM_IMPORT` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | да | да |
<!-- /generated:env-summary -->

## См. также

- [Конфигурация .env](../getting-started/configuration.md)
- [Сервисы и порты](services-and-ports.md)
- [Конфигурация Control Plane](../control-plane/configuration.md)
- [Конфигурация IAM](../iam/configuration.md)
- [Конфигурация памяти](../memory/configuration.md)
- [Конфигурация runner](../runner/configuration.md)
- [Узлы и fleet](../runner/fleet.md)
- [Секреты и ротация](../operations/secrets.md)
