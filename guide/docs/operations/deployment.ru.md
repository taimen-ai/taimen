# Промышленное развёртывание

Статья описывает, как поставить Taimen на выделенный сервер: раскладку
каталогов, подготовку `.env` и секретов, выбор профилей, первый запуск,
bootstrap и вынос автономных исполнителей на отдельный runner-хост. Для
локального знакомства с платформой достаточно
[быстрого старта](../getting-started/quickstart.md); здесь — то, что отличает
промышленную установку.

## Целевая топология


| Узел | Что работает | Откуда код |
|---|---|---|
| Хост платформы | Один compose-проект на `deploy/local/compose.yml`: ядро (`core`), периметр (`edge`) и по необходимости уведомления (`notify`) | Клон суперпроекта с сабмодулями; релиз = коммит суперпроекта |
| Runner-хост (необязательно) | Демон `control-plane-agent` с кодовым агентом, bare-зеркала репозиториев, рабочие копии | Пакет `control-plane` из суперпроекта: в контейнере или как systemd-сервис |
| Рабочие места операторов | MCP-плагин / CLI `control-plane` | Пакет `control-plane` из суперпроекта |

Хост платформы и runner-хост связаны только через публичный адрес платформы:
runner обменивает свой PAT на access token в IAM и ходит в Control Plane API
через Caddy. Прямого сетевого доступа к базам ему не нужно.

!!! note "Почему runner отдельно"
    Кодовому агенту разрешено выполнять произвольные команды (режим
    `bypassPermissions`), иначе он не может работать. Периметр вокруг него —
    отдельная машина или контейнер без доступа к секретам платформы, а не
    режим разрешений. Держать агента на хосте с базами и ключом подписи IAM
    нельзя.

## Требования к хосту

| Что | Минимум | Комментарий |
|---|---|---|
| ОС | Linux x86_64 с systemd | Проверено на Ubuntu 24.04 LTS |
| Docker Engine | 24+ | С плагином Compose v2 |
| Docker Compose | v2.24+ | `env_file` с `required: false` используется в `deploy/local/compose.yml` |
| git | любой современный | Клон с сабмодулями |
| python3 + PyYAML и jsonschema (или uv) | 3.10+ | На хосте запускаются `deploy/bootstrap.py` и `tools/smoke.py`. Установке каталога из пакетов (шаг 5b bootstrap) нужны PyYAML и jsonschema: `make bootstrap` при установленном uv подключает их сам; при прямом вызове скрипта (на хосте без `make`) — либо `uv run --no-project --with pyyaml --with jsonschema python3 deploy/bootstrap.py …`, либо системный `python3` с ними (на Ubuntu пакеты `python3-yaml`, `python3-jsonschema`) |
| openssl, make | — | `make secrets` генерирует ключи подписи RSA 3072 |
| DNS | A/AAAA-запись публичного имени на хост | До первого запуска Caddy, см. [Периметр и TLS](edge-and-tls.md) |
| Порты | 80 и 443 снаружи | Остальные порты сервисов привязаны к `127.0.0.1` |

Ресурсы (CPU, RAM, диск) — в статье [Ресурсы и масштабирование](capacity.md).

## Раскладка каталогов

Рекомендуемая раскладка на хосте платформы:

```text
/opt/taimen/
├── src/                         клон суперпроекта с сабмодулями (релиз = коммит)
│   ├── services/, sdk/          сабмодули компонентов (TAI-ADR-0064)
│   ├── deploy/local/compose.yml единое описание всех сервисов (запуск из корня: tools/compose)
│   ├── .env                     окружение установки, 0600
│   ├── secrets/                 ключи подписи, PAT, env-файлы service accounts, 0600
│   │   ├── iam-signing.pem      приватный ключ подписи IAM (владелец uid 10001)
│   │   ├── harness-pat          PAT оператора, выпускает bootstrap
│   │   └── control-plane-iam.env  service account ядра к памяти (bootstrap)
│   └── deploy/state/<env>.json  идентификаторы, записанные bootstrap (не секрет)
├── Caddyfile                    конфигурация периметра этой установки
└── backups/                     дампы БД (см. «Резервное копирование»)
```

`.env`, `secrets/` и `deploy/state/` перечислены в `.gitignore` суперпроекта:
`git pull` их не трогает.


!!! warning "Caddyfile держите вне клона"
    Переменная `CADDYFILE` задаёт путь к файлу, который монтируется в
    контейнер `caddy`. Файл установки с вашим доменом удобнее держать вне
    рабочего дерева git (например, `/opt/taimen/Caddyfile`), взяв за образец
    `deploy/caddy/Caddyfile.local`. Так обновление суперпроекта не
    конфликтует с локальными правками.

## Профили compose


| Профиль | Сервисы | Когда нужен |
|---|---|---|
| `core` | `iam-db`, `iam-service`, `control-plane-db`, `control-plane-api`, `control-plane-worker`, `context-adapter`, `memory-db`, `memory-service`, `minio`, `minio-bootstrap` | Всегда (MinIO — хранилище содержимого артефактов, см. [Хранилище объектов](object-storage.md)) |
| `edge` | `caddy` | Всегда: единственный вход снаружи |
| `notify` | `notification-db`, `notification-service` | Уведомления людей о событиях платформы |

`make up` без аргументов поднимает только `core edge`; остальные профили
включаются явно.

## Процедура первого развёртывания

### 1. Клон суперпроекта

```bash
sudo mkdir -p /opt/taimen && sudo chown "$USER" /opt/taimen
git clone --recursive <url-суперпроекта> /opt/taimen/src
cd /opt/taimen/src
git submodule status        # все сабмодули без «-» в начале строки
```

Если клон сделан без `--recursive`, выполните `make submodules`
(`git submodule update --init --recursive`). Сборка без сабмодулей падает:
контекст сборки `control-plane`, `memory-service` и других — корень
суперпроекта, а `platform-auth-sdk` подключён path-зависимостью соседней папкой.

### 2. `.env` и ключи подписи

```bash
make secrets
```

Цель `make secrets`:

1. копирует `.env.example` в `.env` с правами `0600` (если `.env` ещё нет);
2. заполняет пустые секреты случайными значениями (`tools/fill_secrets.py`
   трогает только пустые значения — повторный запуск ничего не перезапишет);

3. генерирует ключ подписи `secrets/iam-signing.pem` (RSA 3072) и ставит
   ему `0600`.

Затем отредактируйте `.env` под установку:


```dotenv
TAIMEN_PUBLIC_URL=https://platform.example.com
TAIMEN_PUBLIC_HOST=platform.example.com
COMPOSE_PROJECT_NAME=taimen
TAIMEN_NETWORK=taimen_default
CADDYFILE=/opt/taimen/Caddyfile
LOG_RENDERER=json
IAM_SIGNING_KEY_ID=prod-2026-01        # осмысленный kid, меняется при ротации ключа
CP_LEGACY_API_KEYS_ENABLED=false
```

Параметры провайдеров памяти (`MEMORY_EMBEDDING_PROVIDER`,
`MEMORY_LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, ключ провайдера) описаны в
[конфигурации памяти](../memory/configuration.md); полный список переменных —
в [справочнике](../reference/environment.md).

!!! danger "`TAIMEN_PUBLIC_URL` выбирается один раз"
    Из него строится issuer IAM (`${TAIMEN_PUBLIC_URL}/iam`), а Control Plane
    ищет binding identity по паре `(issuer, iam_principal_id)`. Смена
    публичного адреса после bootstrap — отдельная процедура, см.
    [Аварийные процедуры](emergency.md).

### 3. Права секретов для контейнеров


Сервисы платформы (`iam-service`, `control-plane`) работают в контейнере
под **uid 10001**. Файлы из секции `secrets:` compose монтируются
bind-mount'ом с правами хоста, поэтому на Linux:

```bash
sudo chown 10001:10001 secrets/iam-signing.pem
sudo chmod 600 secrets/*.pem
```

Права не ослабляйте до `644`: это приватные ключи. Если оставить владельцем
root при режиме `600`, IAM не прочитает ключ и ответит `500` на выдаче токенов.
Env-файлы (`secrets/*.env`) читает сам `docker compose` на хосте, для них
`chown` не нужен.

### 4. Caddyfile


Возьмите за основу `deploy/caddy/Caddyfile.local`: замените адрес сайта
`http://taimen.localhost` на своё имя без схемы (тогда Caddy сам выпустит
сертификат), уберите `auto_https off` и маршруты профилей, которые не
поднимаете. Подробно — в статье [Периметр и TLS](edge-and-tls.md). Перед
первым запуском убедитесь, что имя уже резолвится на хост:

```bash
dig +short platform.example.com
```

### 5. Проверка конфигурации и сборка


```bash
make config PROFILES="core edge"   # tools/compose ... config --quiet
make build  PROFILES="core edge"
```

Сборка идёт на хосте из исходников, отдельный registry не нужен. Если
хотите держать предыдущие образы для быстрого отката, задайте в `.env`
`IMAGE_TAG` (например, короткий хэш коммита суперпроекта) — см.
[Обновление и миграции](upgrades.md).

### 6. Запуск


```bash
make up PROFILES="core edge"     # tools/compose --profile ... up -d --build
tools/compose --profile "*" ps
```


Порядок старта задан `depends_on` с условиями `service_healthy`: базы →
IAM и память → `control-plane-api` (выполняет `alembic upgrade head`, затем
становится healthy, когда ревизия БД совпала с head) → `control-plane-worker`
и `context-adapter`. Первый старт с пустыми томами занимает 1–3 минуты.

### 7. Bootstrap

```bash
python3 deploy/bootstrap.py --env .env --name prod --operator "Platform Operator"
```

`deploy/bootstrap.py` идемпотентен и делает за один проход:

| Шаг | Что создаётся | Куда пишется результат |
|---|---|---|
| 1 | Ожидание `/health/ready` Control Plane и `/healthz` IAM на `127.0.0.1` | — |
| 2 | IAM tenant, audiences с потолками scope, human principal оператора | `deploy/state/<env>.json` |
| 2a | Service account ядра (память, хранилище секретов) | `secrets/control-plane-iam.env` |
| 3 | `POST /api/v1/bootstrap` Control Plane: tenant, admin principal и первый IAM binding | state |
| 4 | Authentication context и PAT оператора (read/write/admin) | `secrets/harness-pat` |
| 5 | Шаблон проекта, project и workspace | state |
| 5b | Каталог из пакетов (`--packages`, по умолчанию `deploy/packages.yaml`) | state |
| — | Отзыв legacy api-key, выданного bootstrap Control Plane | state |

После первого прогона выполните то, что скрипт печатает с пометкой `!!`:


```bash
# 1. IAM tenant нужен сервисам, которые обращаются к IAM от своего имени
sed -i "s/^IAM_TENANT_ID=.*/IAM_TENANT_ID=<tenant-id>/" .env

# 2. Ядро должно подхватить env-файл service account (CP_CONTEXT_AUTH=auto)
tools/compose up -d control-plane-api control-plane-worker context-adapter
```

Проверка, что ядро перешло с `MEMORY_API_KEY` на service account:

```bash
tools/compose exec context-adapter env | grep -c CP_IAM_CLIENT_ID   # 1
tools/compose logs --since 5m context-adapter | grep -E ' 40[13] ' || echo "нет 401/403"
```

### 8. Проверка

```bash
make smoke
curl -fsS https://platform.example.com/health/ready
curl -fsS https://platform.example.com/iam/.well-known/jwks.json | head -c 200
```

`make smoke` (скрипт `tools/smoke.py`) опрашивает health каждого запущенного
сервиса через порты на `127.0.0.1`; не поднятые профили помечаются
«не запущен» и ошибкой не считаются.

### 9. Credential оператора

PAT оператора лежит в `secrets/harness-pat`. На рабочем месте оператора он
кладётся в `~/.config/iam/credentials.json` (режим строго `0600`, иначе клиент
откажется читать файл) под ключом `<issuer>|<tenant-id>|<principal-id>` —
bootstrap печатает точный ключ последней строкой. Подробнее — в
[MCP-плагине](../operator/mcp-plugin.md) и
[Credentials и PAT](../iam/credentials.md).

!!! tip "Перенос файла с сервера"
    Копируйте PAT по защищённому каналу (`scp`) и удаляйте промежуточные
    копии. Не вставляйте токен в чаты, тикеты и командную строку с историей.


## Runner-хост


Автономный исполнитель ставится отдельно от хоста платформы — в контейнере
или как systemd-сервис.

=== "Контейнер"

    Образ содержит демон `control-plane-agent`, кодового агента и, при
    необходимости, тестовые базы в tmpfs. Секреты — файлы в каталоге с
    правами `0700`, каждый `0600`: PAT агента, токен подписки кодового
    агента, токен forge. Docker-сокет в контейнер не пробрасывается.

=== "systemd"

    Демон ставится uv-инструментом под непривилегированным пользователем
    `runner`; юнит ограничивает ресурсы (`CPUQuota`, `MemoryHigh`,
    `MemoryMax`, `IOWeight`) и файловую систему (`ProtectSystem=strict`,
    `ProtectHome=read-only`, `NoNewPrivileges`). Конфигурация — env-файл
    `0600`, PAT — `~/.config/iam/credentials.json` пользователя `runner`.

Правила, общие для обоих вариантов:

- **Один исполнитель — один principal.** У каждого свой IAM principal вида
  `agent`, свой PAT и binding без `admin` и `approvals.decide` (bootstrap
  отказывается выдавать агенту эти права).
- **`CONTROL_PLANE_AGENT_ONLY_ASSIGNED=1`** и явный
  `CONTROL_PLANE_AGENT_WORKSPACE`: без них агент берёт первую доступную задачу
  по приоритету из общей очереди.
- **`IAM_PRINCIPAL` обязателен**, если на машине лежат credentials нескольких
  исполнителей одного tenant.
- **Сумма лимитов памяти** всех исполнителей не должна превышать физическую
  память хоста — см. [Ресурсы и масштабирование](capacity.md).


Переменные исполнителя — в статье
[Конфигурация runner](../runner/configuration.md).

## Чек-лист готовности к эксплуатации

- [ ] `.env` и все файлы `secrets/` — `0600`; `.env` не лежит в git.
- [ ] Ключ подписи IAM — владелец uid 10001, режим `600`.
- [ ] `CP_LEGACY_API_KEYS_ENABLED=false`, legacy api-key отозван bootstrap.
- [ ] Caddy выпустил сертификат, `http://` редиректит на `https://`.
- [ ] `/metrics` закрыт от внешнего доступа (см. [Периметр и TLS](edge-and-tls.md)).
- [ ] Порты `127.0.0.1:18000`, `18001`, `18010` и прочие не видны снаружи
      (`ss -ltnp` на хосте показывает их на `127.0.0.1`).
- [ ] Настроены бэкапы всех томов БД и каталога `secrets/`.
- [ ] Записаны даты истечения всех PAT (`deploy/state/<env>.json` хранит
      `operatorPatExpiresAt`).
- [ ] Runner-хост отделён от хоста платформы.

## См. также

- [Установка и первый запуск](../getting-started/quickstart.md)
- [Bootstrap](../getting-started/bootstrap.md)
- [Периметр и TLS](edge-and-tls.md)
- [Секреты и ротация](secrets.md)
- [Сервисы и порты](../reference/services-and-ports.md)
- [Установка и запуск — диагностика](../troubleshooting/startup.md)
