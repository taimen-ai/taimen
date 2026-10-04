# Руководство по платформе Taimen

Это техническое и эксплуатационное руководство по Taimen — среде, в которой люди,
AI-агенты, автоматические процессы и сервисы совместно исполняют работу
организации над общей моделью Work. Руководство адресовано инженерам, которые
разворачивают платформу, операторам, которые ведут в ней работу, и разработчикам
интеграций и исполнителей.

!!! note "Как устроено руководство"
    Каждая статья описывает **текущее поведение кода** поставки: API, переменные,
    порты, команды и коды ошибок сверены с исходниками компонентов, `deploy/local/compose.yml`,
    `.env.example`, `Makefile` и `deploy/`. Замысел и обоснования (ADR) упоминаются
    по идентификаторам — `TAI-ADR-…`, `CP-ADR-…`, `MEM-ADR-…`, `PC-ADR-…` — но
    источником истины о поведении остаётся код.

## С чего начать

| Если вы… | Читайте |
|---|---|
| впервые видите платформу | [Что такое Taimen](overview/what-is-taimen.md) → [Архитектура](overview/architecture.md) → [Ключевые понятия](overview/concepts.md) |
| хотите поднять стенд на своей машине | [Требования](getting-started/requirements.md) → [Установка и первый запуск](getting-started/quickstart.md) → [Bootstrap](getting-started/bootstrap.md) |
| подключаете агента или харнесс | [Первая задача](getting-started/first-task.md) → [Харнесс-протокол](control-plane/harness-protocol.md) → [Агенты и runner](runner/index.md) |
| отвечаете за безопасность | [Модель безопасности](overview/security-model.md) → [IAM](iam/index.md) → [Авторизация и права](control-plane/authorization.md) |
| эксплуатируете промышленный стенд | [Эксплуатация](operations/index.md) → [Диагностика](troubleshooting/index.md) → [Справочник](reference/index.md) |

## Карта разделов

<div class="grid cards" markdown>

-   **[Обзор](overview/index.md)**

    ---

    Что такое Taimen, из каких компонентов состоит, где живёт авторитетное
    состояние, ключевые понятия и модель безопасности.

-   **[Быстрый старт](getting-started/index.md)**

    ---

    Требования, `make secrets / up / bootstrap / smoke`, разбор `.env`, шаги
    bootstrap и первая задача через API, CLI и MCP.

-   **[Control Plane](control-plane/index.md)**

    ---

    Модель работы: задачи, типы и статусы, цели и evidence, claims и runs,
    approvals, артефакты, события, харнесс-протокол, пакеты каталога, API.

-   **[Процессы](processes/index.md)**

    ---

    Процессы организации данными: стадии, согласования, сроки по календарю,
    компенсации, связь с базой знаний, выражения CEL и тесты пакета без стенда.

-   **[IAM](iam/index.md)**

    ---

    Tenants и principals, Platform Access Tokens, обмен на токены audience,
    scopes, service accounts и федерация внешних identity.

-   **[Память](memory/index.md)**

    ---

    Граф знаний с provenance, namespaces и доступ, загрузка знаний, поиск и
    сборка контекста для людей и агентов.

-   **[Агенты и runner](runner/index.md)**

    ---

    Identity агента, демон исполнителя, адаптеры, рабочие копии и трасса
    прогонов.

-   **[Работа оператора](operator/index.md)**

    ---

    MCP-плагин для Claude Code и повседневные сценарии.

-   **[SDK и интеграции](sdk/index.md)**

    ---

    `platform-auth-sdk`, клиенты сервисов, `skill-sdk`, `platform-llm` и
    вертикальные пакеты.

-   **[Эксплуатация](operations/index.md)**

    ---

    Промышленное развёртывание, периметр и TLS, обновления, секреты, бэкапы,
    мониторинг, ёмкость и аварийные процедуры.

-   **[Диагностика](troubleshooting/index.md)**

    ---

    Типичные проблемы запуска, аутентификации, исполнения, памяти и входа людей.

-   **[Справочник](reference/index.md)**

    ---

    Переменные окружения, сервисы и порты, права и scopes, коды ошибок, цели
    `make`, глоссарий.

</div>

## Три источника истины

Всё руководство опирается на одно правило: у каждого факта ровно один
авторитетный дом.

| Что | Где живёт | Раздел |
|---|---|---|
| Работа: задачи, claims, runs, approvals, артефакты, события | **Control Plane** | [Control Plane](control-plane/index.md) |
| Identity: tenants, principals, credentials, токены | **IAM Service** | [IAM](iam/index.md) |
| Знание: наблюдения, факты, документы, provenance | **Memory Service** | [Память](memory/index.md) |

Подробнее — в статье [Архитектура](overview/architecture.md).

## Соглашения

- Команды выполняются из корня суперпроекта (каталог с `deploy/local/compose.yml` и
  `Makefile`), если не сказано иное.
- Адреса в примерах нейтральны: локальный стенд — `http://taimen.localhost`,
  промышленный — `https://platform.example.com`; идентификаторы —
  `<tenant-id>`, `<principal-id>`, `<workspace-id>`.
- Имена полей API, переменных и сущностей даются так, как они записаны в коде
  (camelCase в JSON, `SNAKE_CASE` в окружении).
- Блоки `!!! warning` помечают экспериментальные и замороженные модули и места,
  где поведение легко понять неправильно.

## См. также

- [Глоссарий](reference/glossary.md)
- [Цели make](reference/make.md)
- [Сервисы и порты](reference/services-and-ports.md)
