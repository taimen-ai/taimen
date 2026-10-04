# Конфигурация IAM

Справочник по настройке `iam-service`: переменные окружения сервиса с
дефолтами, как они задаются в `deploy/local/compose.yml`, переменные локального
клиента, bootstrap-токен, ключ подписи, миграции и типичные проблемы
конфигурации. Для администраторов инсталляции.

## Переменные сервиса

Сервис читает настройки из окружения с префиксом `IAM_` (pydantic-settings,
регистр не важен, неизвестные переменные игнорируются).

| Переменная | По умолчанию | Описание |
|---|---|---|
| `IAM_DATABASE_URL` | `postgresql+psycopg://iam:iam@localhost:5435/iam` | Строка подключения SQLAlchemy (async, драйвер psycopg). Используется и сервисом, и Alembic |
| `IAM_BOOTSTRAP_TOKEN` | `""` | Секрет административного API (заголовок `X-IAM-Bootstrap-Token`). Пусто — административные эндпоинты закрыты |
| `IAM_ISSUER` | `http://localhost:8010` | Значение `iss` в выпускаемых токенах; должно совпадать с настройкой issuer у всех сервисов |
| `IAM_TOKEN_TTL_SECONDS` | `300` | Срок жизни access token (и `expiresIn` в ответах обмена) |
| `IAM_SIGNING_PRIVATE_KEY` | `""` | RSA private key в PEM (без пароля) строкой |
| `IAM_SIGNING_PRIVATE_KEY_FILE` | `""` | Путь к файлу ключа; используется, если `IAM_SIGNING_PRIVATE_KEY` пуст |
| `IAM_SIGNING_KEY_ID` | `local-dev` | `kid` в заголовке токенов и в JWKS |
| `IAM_CREATE_SCHEMA_ON_STARTUP` | `false` | Создавать таблицы при старте (`create_all`). Только для разработки; в эксплуатации схему меняет только Alembic |
| `IAM_PAT_DEFAULT_TTL_SECONDS` | `2592000` (30 дней) | Срок PAT, если `expiresInSeconds` не передан |
| `IAM_PAT_MAX_TTL_SECONDS` | `31536000` (365 дней) | Максимальный срок PAT |
| `IAM_PAT_MAX_AUTHENTICATION_AGE_SECONDS` | `300` | Максимальный возраст authentication context человека для выпуска PAT |
| `IAM_LEGACY_CREDENTIAL_MAX_TTL_SECONDS` | `7776000` (90 дней) | Максимальное окно совместимости импортированного ключа Control Plane |
| `IAM_SCIM_AUDIENCE` | `iam-scim` | Audience токена SCIM-клиента |
| `IAM_SCIM_SCOPE` | `scim:write` | Scope, обязательный для SCIM |
| `IAM_SCIM_MAX_PAGE_SIZE` | `200` | Максимальный размер страницы выдачи SCIM |

!!! note "Параметры, которые задаются не переменными"
    Кэш JWKS внешнего IdP (`jwksCacheTtlSeconds`, `jwksStaleGraceSeconds`) и
    требования к `acr`/`amr` настраиваются на каждом identity provider (см.
    [Федерация](federation.md)). Реестр audiences и их scopes — данные в базе
    (см. [Токены](tokens.md)).

## Как это задано в `deploy/local/compose.yml`

Корневой `deploy/local/compose.yml` (профиль `core`) передаёт в контейнер `iam-service`
только часть переменных; остальные работают с дефолтами:

```yaml
iam-service:
  command: >
    sh -c "alembic upgrade head &&
           uvicorn iam_service.app:app --host 0.0.0.0 --port 8010"
  environment:
    IAM_DATABASE_URL: postgresql+psycopg://iam:${IAM_POSTGRES_PASSWORD}@iam-db:5432/iam
    IAM_BOOTSTRAP_TOKEN: ${IAM_BOOTSTRAP_TOKEN:?set IAM_BOOTSTRAP_TOKEN}
    IAM_ISSUER: ${TAIMEN_PUBLIC_URL:?set TAIMEN_PUBLIC_URL}/iam
    IAM_SIGNING_PRIVATE_KEY_FILE: /run/secrets/iam_signing_key
    IAM_SIGNING_KEY_ID: ${IAM_SIGNING_KEY_ID:-local-dev}
  secrets: [iam_signing_key]
  ports: ["127.0.0.1:${IAM_HOST_PORT:-18010}:8010"]
  mem_limit: ${IAM_MEM_LIMIT:-256m}
```

Переменные `.env`, относящиеся к IAM:

| Переменная `.env` | По умолчанию | Куда попадает |
|---|---|---|
| `TAIMEN_PUBLIC_URL` | — (обязательна) | `IAM_ISSUER` = `${TAIMEN_PUBLIC_URL}/iam`; также issuer у всех сервисов (`CP_IAM_ISSUER`, `CB_IAM_ISSUER`, …) |
| `IAM_POSTGRES_PASSWORD` | — (обязательна) | пароль `iam-db` и `IAM_DATABASE_URL` |
| `IAM_BOOTSTRAP_TOKEN` | — (обязательна) | `IAM_BOOTSTRAP_TOKEN`; также bootstrap-скрипт и чтение журнала IAM проекциями внешних сервисов (например, PDP) |
| `IAM_SIGNING_KEY_FILE` | `./secrets/iam-signing.pem` | файл docker-секрета `iam_signing_key` |
| `IAM_SIGNING_KEY_ID` | `local-dev` | `IAM_SIGNING_KEY_ID` |
| `IAM_TENANT_ID` | пусто | tenant IAM для сервисов и исполнителей, которым он нужен при обмене credentials; заполнить после `make bootstrap` |
| `IAM_HOST_PORT` | `18010` | порт IAM на `127.0.0.1` хоста |
| `IAM_MEM_LIMIT` | `256m` | лимит памяти контейнера |
| `IAM_BUILD_CONTEXT` | `./services/iam-service` | контекст сборки образа |
| `PG_MEM_LIMIT` | `256m` | лимит памяти `iam-db` (общий для баз) |
| `VOLUME_IAM_DB` | `${COMPOSE_PROJECT_NAME}_iam_db` | имя volume базы |

`make secrets` создаёт `.env` из `.env.example`, заполняет пустые секреты
случайными значениями и генерирует `secrets/iam-signing.pem` (RSA 3072, `0600`).

### Изменение параметров, которых нет в `deploy/local/compose.yml`

Чтобы поменять, например, срок access token или PAT, добавьте переменные в
override-файл compose, не правя поставляемый `deploy/local/compose.yml`:

```yaml
# compose.override.yml
services:
  iam-service:
    environment:
      IAM_TOKEN_TTL_SECONDS: "600"
      IAM_PAT_DEFAULT_TTL_SECONDS: "7776000"
```

```bash
tools/compose up -d iam-service
```

!!! warning "Не увеличивайте TTL access token без нужды"
    Уже выданный access token IAM не может отозвать: он живёт до `exp`.
    Чем длиннее `IAM_TOKEN_TTL_SECONDS`, тем шире окно, в течение которого
    отключённый пользователь ещё проходит проверку у сервисов без собственной
    revocation-проекции. Режим `TokenLifetimeWindow` в platform-auth-sdk по
    умолчанию отклоняет токены, которым осталось жить больше 900 с.

## Bootstrap-токен {#bootstrap-token}

`IAM_BOOTSTRAP_TOKEN` — единственная граница административного API IAM:

- сравнивается в постоянном времени с заголовком `X-IAM-Bootstrap-Token`;
- пустое значение переменной закрывает все административные эндпоинты
  (`401 unauthorized`);
- заголовок `Authorization: Bearer …` для административных операций **не**
  принимается — только `X-IAM-Bootstrap-Token`;
- в audit действие записывается от имени `bootstrap`.

Рекомендации:

1. Генерируйте длинное случайное значение (`make secrets` делает это сам) и
   храните только в `.env` с правами `0600`.
2. Не передавайте его клиентам, агентам и в CI, которым нужны только PAT.
3. Ограничьте административные пути IAM на периметре (см.
   [API](api.md) и [Периметр и TLS](../operations/edge-and-tls.md)).
4. При подозрении на компрометацию смените значение в `.env`, пересоздайте
   `iam-service` (`tools/compose up -d iam-service`) и проверьте журнал
   `GET /api/v1/events` на неожиданные `principal.created`,
   `platform_access_token.issued`, `service_account.created`.

!!! danger "Токен не для разработки в общих средах"
    Самостоятельный `docker-compose.yml` репозитория `iam-service` по
    умолчанию использует `dev-bootstrap-token-change-me`. Это значение только
    для локальной разработки — в любой общей среде его нужно заменить.

## Ключ подписи

| Требование | Почему |
|---|---|
| RSA, PEM, без пароля | IAM загружает ключ без passphrase и отвергает не-RSA ключи |
| Файл `0600`, владелец uid `10001` (Linux) | контейнер работает под пользователем `iam` (uid 10001); root-овый `0600` он не прочитает |
| Уникальный `IAM_SIGNING_KEY_ID` на каждый ключ | сервисы кешируют ключи по `kid` |
| Файл вне git | `secrets/` в `.gitignore` |

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out secrets/iam-signing.pem
chmod 600 secrets/iam-signing.pem
sudo chown 10001:10001 secrets/iam-signing.pem   # Linux
```

Процедура смены ключа — в статье [Токены, audiences, scopes](tokens.md).

## Issuer

`IAM_ISSUER` определяет `iss` каждого токена и должен **точно** совпадать с
issuer, настроенным в сервисах (`CP_IAM_ISSUER`, `CB_IAM_ISSUER`,
`NS_IAM_ISSUER`, …). В `deploy/local/compose.yml` все
они выводятся из одного `TAIMEN_PUBLIC_URL`, поэтому совпадают автоматически.

!!! danger "Смена `TAIMEN_PUBLIC_URL` меняет issuer"
    Binding principal в Control Plane хранится по паре
    `(issuer, iam_principal_id)`. После смены публичного адреса старые
    bindings перестают находиться, и вход закрывается для всех. Переносите
    bindings тем же изменением — см. [Обновление и миграции](../operations/upgrades.md).

## База данных и миграции

- Отдельная база PostgreSQL 16 (`iam-db`, пользователь и база `iam`).
- Схема управляется Alembic; контейнер выполняет `alembic upgrade head`
  перед запуском API. `alembic` берёт строку подключения из `IAM_DATABASE_URL`.
- Ручной запуск миграций (например, из исходников против базы на хосте):

    ```bash
    cd services/iam-service
    IAM_DATABASE_URL=postgresql+psycopg://iam:<password>@127.0.0.1:5435/iam \
      uv run alembic upgrade head
    ```

| Ревизия | Содержимое |
|---|---|
| `0001` | tenants, principals, memberships, external identities, группы, audiences, service accounts, outbox, audit |
| `0002` | identity providers, федерация, проекция групп |
| `0003` | Platform Access Tokens и authentication contexts |
| `0004` | SCIM: provisioning sources, SCIM-пользователи и группы |

Резервное копирование — обычный `pg_dump` базы `iam` (см.
[Резервное копирование](../operations/backup.md)). В базе хранятся только хэши
секретов; ключ подписи в базу не входит и копируется отдельно.

## Переменные локального клиента

Используются CLI `iam` и клиентами на `control-plane-client` (MCP-плагин,
runner). Подробно — в [Credentials и PAT](credentials.md).

| Переменная | По умолчанию | Описание |
|---|---|---|
| `IAM_CREDENTIAL_MODE` | пусто | `environment` (или `ci`) — брать PAT из `IAM_PLATFORM_ACCESS_TOKEN` |
| `IAM_PLATFORM_ACCESS_TOKEN` | пусто | PAT в режиме environment; без режима — ошибка |
| `IAM_PRINCIPAL` | пусто | чей credential использовать, если на машине их несколько для одной пары IAM + tenant |
| `IAM_NO_KEYCHAIN` | пусто | `1` — не использовать macOS Keychain (только файл) |
| `IAM_BINDING_FILE` | пусто | явный путь к `binding.json` вместо поиска `.iam/binding.json` |
| `XDG_CONFIG_HOME` | `~/.config` | база пути `iam/credentials.json` |
| `CONTROL_PLANE_IAM_URL` | пусто | адрес IAM для клиента Control Plane |
| `CONTROL_PLANE_IAM_TENANT` | пусто | tenant IAM |
| `CONTROL_PLANE_IAM_AUDIENCE` | `control-plane` | audience обмена |
| `CONTROL_PLANE_IAM_SCOPES` | пусто | scopes через пробел или запятую |

## Типичные проблемы конфигурации

| Симптом | Причина | Что сделать |
|---|---|---|
| `401 unauthorized` на административных вызовах | неверный/пустой `X-IAM-Bootstrap-Token`, пустой `IAM_BOOTSTRAP_TOKEN` в контейнере, или использован `Authorization: Bearer` | передавайте именно `X-IAM-Bootstrap-Token`; проверьте переменные контейнера: `tools/compose exec iam-service env` (ищите `IAM_BOOTSTRAP_TOKEN`) |
| `500` на `/.well-known/jwks.json` и на любом обмене | ключ подписи не задан или не читается | проверьте `IAM_SIGNING_KEY_FILE`, наличие файла и владельца uid 10001 |
| `500` при обмене после смены ключа, `PermissionError` в логах | файл ключа `root:root 0600` | `chown 10001:10001` на хосте, права оставить `0600` |
| Сервис отвечает `401` на свежий токен | `iss` в токене не равен issuer сервиса | сверить `IAM_ISSUER` и `*_IAM_ISSUER`; оба должны выводиться из `TAIMEN_PUBLIC_URL` |
| Сервис отвечает `503 verification_unavailable` | сервис не может получить JWKS дольше `stale_after` | проверить доступность `http://iam-service:8010/.well-known/jwks.json` из контейнера сервиса |
| Все токены отклоняются несколько минут после смены ключа | `kid` не изменён | задать новый `IAM_SIGNING_KEY_ID` и пересоздать `iam-service` |
| `403 scope_not_allowed` при обмене | scope без префикса (`write` вместо `control-plane:write`) или вне потолка | запрашивать полные имена scopes из `allowedScopes` |
| `403 authentication_context_required/expired` при выпуске PAT человеку | нет входа или прошло больше 300 с | записать authentication context и сразу выпустить PAT |
| `400 idempotency_key_required` | не передан `Idempotency-Key` | добавить заголовок с новым UUID |
| `422 principal_kind_not_allowed` | PAT для service account | использовать client credentials |
| `iam_environment_mode_required` у клиента | задан `IAM_PLATFORM_ACCESS_TOKEN` без режима | добавить `IAM_CREDENTIAL_MODE=environment` |
| `credential_ambiguous` / `iam_credential_ambiguous` | несколько credentials одной пары IAM + tenant на машине | задать `IAM_PRINCIPAL` для каждого процесса |
| `credentials_file_permissions` | `credentials.json` доступен группе/всем | `chmod 600 ~/.config/iam/credentials.json` |
| `503 identity_provider_unavailable` при федерации | IAM не достаёт discovery/JWKS IdP | проверить, что IAM разрешает адрес issuer; при необходимости задать `jwksUri` |
| Вход через браузер создаёт второй principal | external identity не привязана к существующему principal | привязать заранее, см. [Федерация](federation.md) |

Больше сценариев — в [Диагностике: аутентификация и доступ](../troubleshooting/auth.md).

## См. также

- [Конфигурация .env](../getting-started/configuration.md)
- [Переменные окружения](../reference/environment.md)
- [Секреты и ротация](../operations/secrets.md)
- [Сервисы и порты](../reference/services-and-ports.md)
- [API IAM](api.md)
