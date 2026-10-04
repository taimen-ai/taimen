# Секреты и ротация

Где в установке Taimen лежат секреты, с какими правами, как следить за сроками
и как менять каждый вид секрета — плановая ротация и замена при компрометации.
Статья для инженера эксплуатации и ответственного за безопасность.

## Принципы

- Место секрета задаёт его класс. **Инфраструктурные секреты** платформы —
  пароли баз, ключи подписи, bootstrap-токены, учётные данные service accounts
  компонентов — живут только в `.env` и каталоге `secrets/` клона суперпроекта
  (оба в `.gitignore`) и в credential-файлах рабочих мест и runner-хоста. Это
  описывает эта статья. **Секреты подключений и агентов** — токены и ключи
  внешних систем, секреты агентов реестра — живут в [хранилище
  секретов](secret-store.md).
- Права — `0600` на файл, `0700` на каталог. Клиент `control-plane`
  отказывается читать `~/.config/iam/credentials.json`, если файл доступен
  кому-то кроме владельца (`iam_credentials_file_permissions`).
- Скрипты платформы секреты не печатают: `make secrets`, `deploy/bootstrap.py`
  пишут их сразу в файлы с `0600` и выводят только идентификаторы и
  публичные префиксы PAT.
- Секрет, который прошёл через чат, тикет, скриншот или историю shell,
  считается скомпрометированным и перевыпускается.

## Инвентарь

### Хост платформы: `.env`


| Переменная | Кто использует | Как заменить |
|---|---|---|
| `CP_POSTGRES_PASSWORD`, `IAM_POSTGRES_PASSWORD`, `MEMORY_POSTGRES_PASSWORD`, `NOTIFY_POSTGRES_PASSWORD` | Базы и сервисы | `ALTER ROLE` в базе, затем `.env`, затем пересоздание сервиса (см. ниже) |
| `CP_BOOTSTRAP_TOKEN` | `POST /api/v1/bootstrap` Control Plane | `.env` и `up -d control-plane-api` |
| `IAM_BOOTSTRAP_TOKEN` | Административные операции IAM (`X-IAM-Bootstrap-Token`) | `.env` и пересоздание `iam-service` |
| `MEMORY_API_KEY` | Статический ключ памяти: `memory-service`, ядро до перехода на service account | `.env` и пересоздание всех потребителей |
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | Root-учётка MinIO; ею пользуется только `minio-bootstrap` | См. [Хранилище объектов](object-storage.md) |
| `CP_S3_ACCESS_KEY_ID`, `CP_S3_SECRET_ACCESS_KEY` | Пользователь Control Plane в хранилище объектов (только свой бакет), его заводит `minio-bootstrap` | `.env`, повторный запуск `minio-bootstrap`, затем пересоздание `control-plane-api`, `control-plane-worker`, `context-adapter`; для внешнего S3 — сначала у провайдера (см. [Хранилище объектов](object-storage.md)) |
| `LLM_API_KEY` | Ключ OpenAI-совместимого LLM-провайдера для памяти и исполнителей | У провайдера, затем `.env` и пересоздание потребителей |


`make secrets` заполняет случайными значениями все перечисленные пароли,
bootstrap-токены, `MEMORY_API_KEY` и ключи MinIO, если они пусты.

Секретов со значением по умолчанию в `deploy/local/compose.yml` нет: пароли БД и
bootstrap-токены всех профилей, включая экспериментальные, объявлены
обязательными (`${VAR:?…}`) и генерируются `make secrets`. Если ключа нет в
`.env` (файл создан по старому `.env.example` или строка закомментирована),
`make secrets` дописывает его.

### Хост платформы: `secrets/`

| Файл | Что | Кто пишет | Кто читает |
|---|---|---|---|
| `iam-signing.pem` | Приватный ключ подписи access token (RSA 3072) | `make secrets` | `iam-service` (uid 10001, docker secret) |
| `harness-pat` | PAT оператора (read/write/admin) | bootstrap, шаг 4 | Переносится на рабочее место оператора |
| `control-plane-iam.env` | `CP_IAM_CLIENT_ID`, `CP_IAM_CLIENT_SECRET` — service account ядра | bootstrap, шаг 2a | `docker compose` (`env_file` трёх процессов ядра) |

Права: всё — `0600`. Файлы, которые монтируются в контейнер (ключи подписи),
на Linux должны принадлежать uid `10001`:


```bash
sudo chown 10001:10001 secrets/iam-signing.pem
sudo chmod 600 secrets/*.pem
```

Ослаблять права до `644` вместо `chown` нельзя: это приватные ключи и токены.
Env-файлы (`*.env`) читает `docker compose` на хосте, их владелец — тот, кто
запускает compose.

### Runner-хост и рабочие места

| Где | Секрет | Комментарий |
|---|---|---|
| Runner | PAT агента | Файл-секрет контейнера или `~/.config/iam/credentials.json` пользователя `runner` |
| Runner | `CLAUDE_CODE_OAUTH_TOKEN` | Токен подписки кодового агента; принадлежит человеку, а не агенту. Выпускается `claude setup-token` на машине с браузером |
| Runner | Токен forge (для push веток задач) | Минимальные права: запись только в репозитории задач, чтение соседей |
| Оператор | `~/.config/iam/credentials.json` | JSON-объект: ключ — адрес IAM, tenant и principal через вертикальную черту, значение с полем `token`; режим `0600` |


## Сроки жизни credentials

| Credential | Срок | Параметр |
|---|---|---|
| Access token IAM | 300 с | `IAM_TOKEN_TTL_SECONDS` (по умолчанию) |
| PAT, срок по умолчанию | 30 дней | `IAM_PAT_DEFAULT_TTL_SECONDS=2592000` |
| PAT, максимальный срок | 365 дней | `IAM_PAT_MAX_TTL_SECONDS=31536000`; больше — `422 expiry_too_long` |
| PAT, выпущенный `deploy/bootstrap.py` | 180 дней | Аргумент `--pat-ttl` (секунды) |
| Свежесть входа человека для выпуска PAT | 300 с | `IAM_PAT_MAX_AUTHENTICATION_AGE_SECONDS` |
| Service account (client credentials) | Без срока | Отзыв — `…/service-accounts/{client_id}:revoke` |

Параметры IAM в `deploy/local/compose.yml` не пробрасываются: чтобы изменить значения по
умолчанию, добавьте их в `environment` сервиса `iam-service` через
`compose.override.yml`.

!!! danger "Ротация не продлевает PAT"
    `POST …/platform-access-tokens/{id}:rotate` меняет только секрет: новый
    токен наследует audiences, потолок scope и **`expiresAt`**
    предшественника. Это инструмент для утечки, а не для продления. Чтобы
    продлить доступ, выпускается **новый** PAT, а старый отзывается.

### Как следить за сроками

```bash
source <(grep -E '^(IAM_BOOTSTRAP_TOKEN|IAM_TENANT_ID)=' .env)
curl -s "http://127.0.0.1:18010/api/v1/tenants/$IAM_TENANT_ID/platform-access-tokens" \
  -H "X-IAM-Bootstrap-Token: $IAM_BOOTSTRAP_TOKEN" \
  | python3 -c 'import json,sys; [print(t["expiresAt"][:10], t["publicPrefix"], t["name"]) for t in sorted(json.load(sys.stdin), key=lambda t: t["expiresAt"])]'
```

Ответ содержит только активные токены (`includeRevoked=true` — вместе с
отозванными), с полями `publicPrefix`, `name`, `principalId`, `expiresAt`,
`lastUsedAt`. Заведите напоминание за две недели до ближайшего `expiresAt`.

## Процедуры

Во всех примерах ниже переменные окружения:

```bash
IAM=http://127.0.0.1:18010
T=<tenant-id>                       # IAM tenant
H="X-IAM-Bootstrap-Token: $IAM_BOOTSTRAP_TOKEN"
```

### Перевыпуск PAT агента (плановый)

У агента (principal вида `agent`) нет человеческого входа, свежий
authentication context для него не требуется.

```bash
# 1. Новый PAT; Idempotency-Key обязателен (без него — 400 idempotency_key_required)
curl -s -X POST "$IAM/api/v1/tenants/$T/principals/<agent-principal-id>/platform-access-tokens" \
  -H "$H" -H "Content-Type: application/json" -H "Idempotency-Key: $(uuidgen)" \
  -d '{"name": "runner-2026-q3", "audiences": ["control-plane"],
       "scopeCeiling": ["control-plane:read", "control-plane:write"],
       "expiresInSeconds": 15552000}' > /tmp/pat.json
# поле token — секрет, показывается ровно один раз
```

2. Установите токен на runner-хост (файл-секрет контейнера или
   `credentials.json` пользователя `runner`, `0600`), удалите `/tmp/pat.json`.
3. Перезапустите исполнителя и убедитесь, что он получил задачу или хотя бы
   открыл сессию (в логах нет `invalid_token`).
4. Отзовите прежний PAT:

```bash
curl -s -X POST "$IAM/api/v1/tenants/$T/platform-access-tokens/<old-credential-id>:revoke?reason=superseded" \
  -H "$H"          # 204
```

`scopeCeiling` должен быть подмножеством `allowedScopes` указанных audiences,
иначе `422 invalid_scope_ceiling`. PAT выпускается только principal вида
`human` или `agent`; для `service_account` — `422 principal_kind_not_allowed`
(у сервисов свой поток client credentials).

### Перевыпуск PAT человека

Человеку IAM выпускает PAT только при свежем (не старше 300 с) authentication
context. Запись контекста и выпуск выполняются одна за другой:

```bash
curl -s -X POST "$IAM/api/v1/tenants/$T/principals/<human-principal-id>/authentication-contexts" \
  -H "$H" -H "Content-Type: application/json" \
  -d '{"issuer": "https://platform.example.com/iam", "acr": "bootstrap", "amr": ["bootstrap-script"]}'

curl -s -X POST "$IAM/api/v1/tenants/$T/principals/<human-principal-id>/platform-access-tokens" \
  -H "$H" -H "Content-Type: application/json" -H "Idempotency-Key: $(uuidgen)" \
  -d '{"name": "operator-2026-q3", "audiences": ["control-plane"],
       "scopeCeiling": ["control-plane:read", "control-plane:write", "control-plane:admin"],
       "expiresInSeconds": 15552000}'
```

Если между вызовами прошло больше 300 с — `403 authentication_context_expired`;
если контекста нет вовсе — `403 authentication_context_required`.
`deploy/bootstrap.py` делает то же самое для оператора, если файла
`secrets/harness-pat` нет: удалите (переименуйте) файл и запустите bootstrap
повторно, затем отзовите прежний PAT.

### Замена PAT при утечке

1. **Немедленно перекройте доступ в Control Plane**: отзовите binding
   identity. Это закрывает вход сразу, не дожидаясь истечения уже выданных
   access token (до 300 с):

    ```bash
    curl -s -X POST https://platform.example.com/api/v1/iam-bindings/<binding-id>:revoke \
      -H "Authorization: Bearer <admin access token>"
    ```

2. Отзовите PAT в IAM (`:revoke`) — либо владелец отзывает свой токен сам,
   без bootstrap-полномочий:

    ```bash
    curl -s -X POST "$IAM/api/v1/platform-access-tokens:revoke-self" \
      -H "Content-Type: application/json" -d '{"token": "<leaked PAT>", "reason": "leaked"}'
    ```

3. Выпустите новый PAT (процедуры выше), восстановите binding повторным
   `POST /api/v1/principals/<principal-id>/iam-bindings` с теми же правами.
4. Проверьте audit IAM и журнал Control Plane за период утечки.

Подробный сценарий — в [Аварийных процедурах](emergency.md).

### Ротация секрета service account


Секрет service account ядра и сервисов платформы (`control-plane-iam.env`,
`notification-iam.env`) меняет bootstrap: если env-файла нет, он просит у IAM
новый секрет **той же** учётки (`PATCH {"rotateSecret": true}`, см. [Service
accounts](../iam/service-accounts.md#update)) и сразу пишет его в файл; прежний
секрет гаснет. Principal и `clientId` не меняются.

```bash
mv secrets/control-plane-iam.env secrets/control-plane-iam.env.old
python3 deploy/bootstrap.py --env .env --name <env>
tools/compose up -d control-plane-api control-plane-worker context-adapter
shred -u secrets/control-plane-iam.env.old
```


### Ротация ключа подписи IAM

IAM публикует в `/.well-known/jwks.json` **один** ключ — текущий. Сервисы
проверяют подпись по JWKS с кэшем и обновляют его при встрече неизвестного
`kid`.

1. Сгенерируйте новый ключ и дайте ему новый `kid`:

    ```bash
    openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out secrets/iam-signing.new.pem
    sudo chown 10001:10001 secrets/iam-signing.new.pem && chmod 600 secrets/iam-signing.new.pem
    ```

2. В `.env`: `IAM_SIGNING_KEY_FILE=./secrets/iam-signing.new.pem`,
   `IAM_SIGNING_KEY_ID=<новый kid>`.
3. `tools/compose up -d iam-service`.
4. Проверьте `curl -s $IAM/.well-known/jwks.json` — новый `kid`.

Что происходит: PAT и секреты service accounts от ключа подписи не зависят и
остаются действительными. Access token, подписанные старым ключом (живут
до 300 с), перестают проходить проверку, как только сервис обновит JWKS;
клиенты получают `401` и заново обменивают PAT. Выполняйте ротацию в период
низкой активности. Старый файл ключа храните до конца окна как точку отката.

!!! danger "Компрометация ключа подписи"
    Утечка `iam-signing.pem` позволяет подделать access token любого
    principal. Ротируйте ключ немедленно и перезапустите сервисы,
    проверяющие токены (`control-plane-api`, `memory-service` и другие),
    чтобы они сбросили кэш JWKS со старым ключом.

### Пароли баз данных

`POSTGRES_PASSWORD` применяется образом PostgreSQL только при инициализации
пустого тома. Изменение `.env` на существующей базе пароль **не меняет** —
сервис просто перестанет подключаться. Порядок:

```bash
# 1. Сменить пароль роли в базе
tools/compose exec control-plane-db psql -U control_plane -d control_plane \
  -c "ALTER ROLE control_plane PASSWORD '<новый пароль>'"
# 2. Записать тот же пароль в .env (CP_POSTGRES_PASSWORD)
# 3. Пересоздать потребителей
tools/compose up -d control-plane-api control-plane-worker context-adapter
```


### Токен подписки кодового агента и токен forge

- Токен подписки выпускается человеком на машине с браузером
  (`claude setup-token`), на runner-хосте войти интерактивно нельзя.
  Замена: новый токен → файл-секрет или env-файл исполнителя → перезапуск.
- Отзыв токена подписки выполняется на стороне поставщика. После отзыва
  исполнитель продолжает брать задачи и валить их — остановите его.
- Токен forge заменяется так же; проверка — успешная публикация ветки
  следующей задачи (в артефакте `commit` поле `published: true`).

## Рекомендуемый календарь

| Периодичность | Действие |
|---|---|
| Раз в 5–15 минут | Страж политик хранилища секретов (`openbao-bootstrap check-agents`), оповещение по ненулевому коду — см. [Хранилище секретов](secret-store.md#policy-guard) |
| Ежедневно | Снимок raft хранилища секретов токеном `backup` — см. [Хранилище секретов](secret-store.md#backup) |
| Еженедельно | Список PAT с `expiresAt` ближе 30 дней |
| За 2 недели до истечения | Перевыпуск PAT исполнителей и операторов |
| Раз в квартал | Ротация `MEMORY_API_KEY`, ключа LLM-провайдера, секретов service accounts |
| Раз в год | Ротация ключа подписи IAM и паролей БД |
| Сразу | Любой секрет, прошедший через переписку или логи |

## См. также

- [Хранилище секретов](secret-store.md)
- [Credentials и PAT](../iam/credentials.md)
- [Токены, audiences, scopes](../iam/tokens.md)
- [Service accounts](../iam/service-accounts.md)
- [Аварийные процедуры](emergency.md)
- [Аутентификация и доступ — диагностика](../troubleshooting/auth.md)
