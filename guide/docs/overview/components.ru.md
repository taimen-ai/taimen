# Состав поставки

Статья перечисляет компоненты платформы Taimen, показывает, как они
раскладываются по профилям `deploy/local/compose.yml`, и фиксирует статус каждого
профиля: что входит в набор по умолчанию, что экспериментально, что заморожено.
Она нужна при планировании стенда и при выборе, какие профили включать.

## Устройство репозитория

Платформа собирается в **суперпроекте** — репозитории-зонтике, к которому
компоненты подключены git-сабмодулями: сервисы — в `services/`, библиотеки — в `sdk/`:

```text
<суперпроект>/
├── services/
│   ├── control-plane/          # сабмодуль
│   ├── iam-service/            # сабмодуль
│   ├── memory-service/         # сабмодуль
│   └── notification-service/   # сабмодуль (профиль notify)
├── sdk/
│   ├── platform-auth-sdk/      # сабмодуль (библиотека)
│   ├── skill-sdk/              # сабмодуль (библиотека)
│   ├── platform-llm/           # сабмодуль (библиотека)
│   └── package-sdk/            # сабмодуль (инструменты автора пакетов)
├── deploy/
│   ├── local/compose.yml       # единое описание сервисов, запуск из корня
│   └── bootstrap.py, caddy/    # инициализация, Caddyfile
├── .env.example  Makefile
├── tools/                      # compose (обёртка), smoke, fill_secrets, docs_gen, …
└── docs/                       # архитектура и ADR
```

!!! warning "Раскладка `services/`, `sdk/` обязательна"
    `control-plane`, `memory-service` и другие сервисы подключают
    `platform-auth-sdk` **path-зависимостью** `../../sdk/platform-auth-sdk`,
    поэтому их образы собираются с контекстом — корнем суперпроекта. Переносить
    сабмодули в другие каталоги нельзя: сборка сломается. Compose запускается из
    корня — целями `make` или обёрткой `tools/compose`.

Изменение в компоненте коммитится в его репозитории, а указатель сабмодуля в
суперпроекте обновляется отдельным коммитом. `make submodules` поднимает
сабмодули на закреплённых ревизиях, `make status` показывает указатели.

## Компоненты

### Сервисы ядра

| Компонент | Что делает | Процессы в compose | Хранилище |
|---|---|---|---|
| **control-plane** | Авторитетное операционное состояние: задачи, типы, claims, runs, approvals, артефакты, цели, журнал событий, харнесс-протокол; CLI `control-plane`, MCP-сервер `control-plane-mcp`, демон исполнителя `control-plane-agent` | `control-plane-api`, `control-plane-worker`, `context-adapter` (один образ) | PostgreSQL 16 (`control-plane-db`) |
| **iam-service** | Tenants, principals, audiences, PAT, service accounts, федерация внешних IdP, SCIM, выпуск RS256-токенов, JWKS | `iam-service` | PostgreSQL 16 (`iam-db`) |
| **console** | Веб-консоль работающей организации: пульс, происхождение работы, процессы, правила, агенты, управляющие действия, пакеты, люди и роли. Сабмодуль `console`, своей базы нет; см. [Консоль](../operator/console.md) | `console` | нет (сессии в памяти) |
| **memory-service** | Граф знаний с временными фактами и provenance, документы, гибридный поиск (векторный + лексический + графовый), Context Compiler; HTTP API, MCP-сервер, CLI | `memory-service` | PostgreSQL 16 с pgvector и `pg_trgm`, граф — обычные таблицы (`memory-db`, свой образ) |

### Библиотеки

| Компонент | Назначение |
|---|---|
| **platform-auth-sdk** | Общий Policy Enforcement Point: проверка токенов IAM по JWKS, trusted auth context, отзыв, проверки entitlement и policy, единый контракт отказа, аудит. Используют все resource services |
| **skill-sdk** | Скилл пишется один раз в коде; SDK даёт контракт, контекст вызова, хостинг по протоколам `local`, `http`, `mcp` и экспорт YAML в пакет каталога |
| **platform-llm** | Общий LLM-клиент: любой OpenAI-совместимый `/chat/completions`, ответы по JSON-схеме, ретраи и переключение моделей |
| **package-sdk** | Инструменты автора пакетов каталога: CLI `package-sdk` (`check`, `test`, `lock`, `plan`, `apply`), схемы формата, среда наблюдателя `package_sdk.connector` и плагин Claude Code `package-author`. См. [Пакеты](../packages/index.md) |
| **control-plane-client** | Клиент Control Plane (дистрибутив в `services/control-plane/client`): обмен PAT на токен, ретраи, типизированные вызовы. См. [Клиенты сервисов](../sdk/clients.md) |

### Периферия

| Компонент | Что делает | Статус |
|---|---|---|
| **notification-service** | Уведомления людей по правилам: читает журнал событий Control Plane и доставляет сообщения в каналы (Telegram) | опционально, профиль `notify` |


## Профили compose

Корневой `deploy/local/compose.yml` — один файл, одна сеть (`${TAIMEN_NETWORK}`), одинаковые
DNS-имена сервисов локально и на промышленном стенде. Набор сервисов выбирается
профилями.

```mermaid
flowchart LR
    subgraph default["по умолчанию: make up"]
        core[core]
        edge[edge]
    end
    subgraph opt["опционально"]
        notify[notify]
        idp[idp]
        console[console]
        harness[harness]
        fleet[fleet]
    end
    core --> edge
    notify -.-> core
    console -.-> idp
    harness -.-> idp
    idp -.-> core
    fleet -.-> core
```

| Профиль | Сервисы | Статус | Когда включать |
|---|---|---|---|
| `core` | `iam-db`, `iam-service`, `control-plane-db`, `control-plane-api`, `control-plane-worker`, `context-adapter`, `memory-db`, `memory-service`, `minio`, `minio-bootstrap` | **стабильное ядро** | всегда (MinIO — содержимое артефактов ядра) |
| `edge` | `caddy` | стабильный | всегда, кроме случаев, когда периметр обеспечен иначе |
| `notify` | `notification-db`, `notification-service` | опционально | уведомления людей по событиям Control Plane; учётку сервиса заводит bootstrap |

Команды:

```bash
make up                                     # core edge (по умолчанию)
make up PROFILES="core notify edge"         # с уведомлениями
tools/compose --profile core --profile edge up -d   # то же без make
```

`make down` останавливает все профили (`--profile "*"`), данные в volumes
сохраняются.

!!! warning "Интерполяция идёт по всему файлу"
    Docker Compose подставляет переменные во **весь** `deploy/local/compose.yml`, а не только
    в сервисы включённых профилей. Поэтому обязательными (`${VAR:?…}`)
    объявлены только значения, которые генерирует `make secrets`.
    Идентификаторы опциональных профилей (например, `IAM_TENANT_ID`) по
    умолчанию пусты и проверяются сервисами своих профилей, так что `make up`
    для `core edge` работает на чистом `.env` — см.
    [Установку и первый запуск](../getting-started/quickstart.md).

## Образы и сборка

| Образ | Контекст сборки | Dockerfile |
|---|---|---|
| `${IMAGE_PREFIX}/control-plane` | корень суперпроекта (`CP_BUILD_CONTEXT`) | `services/control-plane/Dockerfile` |
| `${IMAGE_PREFIX}/iam-service` | `./services/iam-service` (`IAM_BUILD_CONTEXT`) | `services/iam-service/Dockerfile` |
| `${IMAGE_PREFIX}/memory-service` | корень (`MEMORY_BUILD_CONTEXT`) | `services/memory-service/Dockerfile` |
| `${IMAGE_PREFIX}/memory-db` | `services/memory-service/infra/memory-db` | PostgreSQL + pgvector; основан на образе `apache/age`, расширение AGE сервис не использует |
| `${IMAGE_PREFIX}/notification-service` | корень (`NOTIFY_BUILD_CONTEXT`) | `services/notification-service/Dockerfile` |
| `${IMAGE_PREFIX}/human-harness` | `./services/human-harness` | `Dockerfile` (сервис `harness-image`, только сборка) |
| `${IMAGE_PREFIX}/harness-launcher` | `./services/human-harness` | `packages/launcher/Dockerfile` |

`IMAGE_PREFIX` по умолчанию `taimen`, `IMAGE_TAG` — `local`. Контейнеры сервисов
на Python работают под непривилегированным пользователем (у Control Plane и IAM
— uid `10001`), поэтому файлы секретов, которые монтируются в контейнер, на
Linux должны принадлежать этому uid.

## Volumes

Имена volumes задаются явно, чтобы промышленный стенд мог указать уже
существующие: `VOLUME_CONTROL_PLANE_DB`, `VOLUME_IAM_DB`, `VOLUME_MEMORY_DB`,
`VOLUME_NOTIFY_DB` и т.д. По умолчанию имя — `${COMPOSE_PROJECT_NAME}_<volume>`,
например `taimen_control_plane_db`. Список — в
[Переменных окружения](../reference/environment.md), резервное копирование — в
[Резервном копировании](../operations/backup.md).

## Что не входит в compose

- **Runner** (`control-plane-agent`) — демон автономного исполнителя ставится
  на отдельный хост как systemd-юниты. См. [Агенты и runner](../runner/index.md).
- **MCP-сервер и CLI** Control Plane — ставятся на машину оператора
  (`uv tool install`). См. [CLI и MCP-сервер](../control-plane/cli-and-mcp.md).
- **LLM-провайдер** — внешний OpenAI-совместимый endpoint; память может
  работать без него на офлайн-заглушках.

## См. также

- [Архитектура](architecture.md)
- [Установка и первый запуск](../getting-started/quickstart.md)
- [Сервисы и порты](../reference/services-and-ports.md)
- [Цели make](../reference/make.md)
