# Цели make

Все цели корневого `Makefile` суперпроекта — единого механизма запуска,
проверки и документации платформы. Статья для инженера, который поднимает
стенд, прогоняет проверки перед коммитом или собирает это руководство.
Запускайте `make` из корня суперпроекта; `make` без аргументов печатает
список целей с описаниями (`make help`).

## Сводка

| Цель | Параметры | Что делает |
|---|---|---|
| `help` | — | Список целей с описаниями (цель по умолчанию). |
| `secrets` | — | Создаёт `.env` из `.env.example` (если его нет), заполняет пустые секреты, генерирует ключи подписи. |
| `config` | `PROFILES` | Проверяет `deploy/local/compose.yml` после интерполяции для выбранных профилей. |
| `build` | `PROFILES` | Собирает образы выбранных профилей. |
| `up` | `PROFILES` | Собирает и поднимает выбранные профили в фоне. |
| `down` | — | Останавливает и удаляет контейнеры всех профилей; volumes сохраняются. |
| `ps` | — | Состояние контейнеров всех профилей. |
| `logs` | `svc` | Поток логов сервиса (или всех). |
| `smoke` | — | Проверяет health поднятых сервисов через порты `127.0.0.1`. |
| `bootstrap` | `ARGS` | Первичная инициализация: tenant, principals, PAT, bindings, каталог. |
| `reset-state` | — | После сброса volumes переносит state bootstrap и выданные им credentials в `secrets/stale-<время>/`. |
| `check` | — | Lint + unit-тесты всех компонентов ядра (как обязательный CI). |
| `check-<компонент>` | — | Lint + тесты одного компонента. |
| `lint-<компонент>` | — | Только lint одного компонента. |
| `test-<компонент>` | — | Только тесты одного компонента. |
| `packages-check` | — | Проверка пакетов каталога `packages/`. |
| `linkcheck` | — | Проверяет относительные ссылки в документации. |
| `submodules` | — | Инициализирует сабмодули на закреплённых ревизиях. |
| `status` | — | Указатели сабмодулей и незакоммиченные изменения. |
| `guide` | — | Собирает это руководство в `guide/site`. |
| `guide-serve` | — | Руководство с живой перезагрузкой на `http://127.0.0.1:8008`. |

## Переменные make

| Переменная | По умолчанию | Где используется |
|---|---|---|
| `PROFILES` | `core edge` | `config`, `build`, `up`: превращается в `tools/compose --profile <p> …` для каждого профиля. |
| `svc` | пусто (все сервисы) | `logs`. |
| `ARGS` | пусто | `bootstrap`: дополнительные аргументы `deploy/bootstrap.py`. |
| `BOOTSTRAP_PY` | `uv run --no-project --quiet --with pyyaml --with jsonschema python3`, если uv установлен; иначе `python3` | `bootstrap`: интерпретатор скрипта. |
| `ENV_NAME` | `COMPOSE_PROJECT_NAME` из `.env`, иначе `taimen` | `reset-state`: имя файла состояния. |

Внутренние списки компонентов:

| Список | Состав |
|---|---|
| `COMPONENTS_PY` (ядро, `make check`) | `platform-auth-sdk`, `platform-llm`, `skill-sdk`, `iam-service`, `control-plane`, `memory-service` |

## Запуск стека

### make secrets

```bash
make secrets
```

1. Если `.env` нет — копирует `.env.example` в `.env` и ставит права `600`.
2. `tools/fill_secrets.py .env` заполняет **только пустые** значения из
   фиксированного списка случайными hex-строками (`secrets.token_hex`):
   пароли БД (`CP_`, `IAM_`, `MEMORY_`, `KEYCLOAK_DB_`,
   `NOTIFY_`), bootstrap-токены (`CP_`, `IAM_`),
   `MEMORY_API_KEY`, `KEYCLOAK_ADMIN_PASSWORD`, `S3_ACCESS_KEY_ID`,
   `S3_SECRET_ACCESS_KEY`, `CP_S3_ACCESS_KEY_ID`, `CP_S3_SECRET_ACCESS_KEY`.
   Существующие значения не трогаются; повторный запуск безопасен.
3. Создаёт каталог `secrets`.
4. Генерирует RSA 3072 ключ `secrets/iam-signing.pem`, если его нет, и
   ставит `600`.

!!! note "На Linux — владелец uid 10001"
    Контейнеры читают ключи под uid 10001. После `make secrets` выполните
    `chown 10001 secrets/*.pem`, иначе IAM не прочитает ключ подписи.


`IAM_TENANT_ID` цель не заполняет: сгенерировать его нечем. В `deploy/local/compose.yml`
он по умолчанию пуст, поэтому `make up` для `core edge` работает сразу после
`make secrets` — см. [Переменные окружения](environment.md).

### make config

```bash
make config
make config PROFILES="core idp harness edge"
```

`tools/compose … config --quiet`; при успехе печатает
`deploy/local/compose.yml корректен для профилей: …`. Ловит пустые обязательные
переменные и ошибки интерполяции до запуска.

### make build / make up

```bash
make up                                   # core edge
make up PROFILES="core idp harness edge" # с входом людей и рабочими местами
make up PROFILES="core fleet edge"
make build PROFILES="core"
```


`up` выполняет `tools/compose --profile … up -d --build`: пересобирает
изменившиеся образы и пересоздаёт контейнеры.

### make down / ps / logs

```bash
make down
make ps
make logs svc=control-plane-api
make logs                       # все сервисы
```

Эти цели работают с `--profile "*"` — со всеми профилями сразу,
независимо от `PROFILES`. `down` не удаляет volumes: данные сохраняются.

### make smoke

```bash
make smoke
```

`tools/smoke.py` читает порты из `.env` (или окружения) и опрашивает
health-эндпоинты поднятых сервисов; не запущенные помечает «не запущен»
и ошибкой не считает. Код выхода `1`, если хотя бы один поднятый сервис
ответил `≥ 400`. Перечень проверок — в
[Сервисы и порты](services-and-ports.md#healthchecks).

### make bootstrap

```bash
make bootstrap
make bootstrap ARGS="--name local --secrets-dir secrets --packages deploy/packages.yaml"
```

Запускает `deploy/bootstrap.py --env .env $(ARGS)`: если uv установлен —
через `uv run --no-project --quiet --with pyyaml --with jsonschema python3`
(PyYAML и jsonschema ставить в систему не нужно), иначе системным `python3`,
в котором тогда должны быть PyYAML и jsonschema. Скрипт
идемпотентен: состояние хранится в `deploy/state/<env>.json`, повторный
запуск пропускает сделанное. Аргументы:

| Аргумент | По умолчанию | Назначение |
|---|---|---|
| `--env` | `.env` | Файл окружения (цель передаёт `.env`). |
| `--name` | `COMPOSE_PROJECT_NAME` | Имя окружения — имя файла состояния. |
| `--operator` | значение из кода | Отображаемое имя human-оператора. |
| `--tenant-slug` | `COMPOSE_PROJECT_NAME` | Slug tenant. |
| `--pat-ttl` | `15552000` (180 дней) | Срок выпускаемых PAT, секунды. |
| `--secrets-dir` | `secrets` | Куда писать PAT и env-файлы service accounts. |
| `--packages` | `deploy/packages.yaml` | Файл установки каталога (`kind: Installation`). |

Что делает по шагам и какие права выдаёт — [Bootstrap](../getting-started/bootstrap.md)
и [Права и scopes](permissions.md#bootstrap-grants).

### make reset-state

```bash
tools/compose --profile "*" down -v   # сброс volumes
make reset-state
make up && make bootstrap
```

Нужна после удаления volumes: файл состояния bootstrap ссылается на tenant и
principals, которых в пустых базах уже нет, и bootstrap в этом случае
останавливается с подсказкой `make reset-state`. Цель переносит в
`secrets/stale-<ГГГГММДД-ЧЧММСС>/`:

- `deploy/state/<ENV_NAME>.json`;

- `secrets/harness-pat`, `secrets/control-plane-iam.env`,
  `secrets/notification-iam.env`, `secrets/memory-service-iam.env`,
  `secrets/agents/`.

Ключи подписи (`secrets/*.pem`) и `.env` не трогает. Если переносить нечего,
печатает `нечего убирать`. Файлы не удаляются — старые credentials можно
отозвать или удалить вручную позже.

## Проверки


### make check

```bash
make check            # ядро: как обязательный CI
```

Для каждого компонента выполняется `lint-<компонент>` и
`test-<компонент>`.

### make check-&lt;компонент&gt;, lint-&lt;компонент&gt;, test-&lt;компонент&gt;

```bash
make check-control-plane
make lint-memory-service
make test-iam-service
```

`lint-<компонент>` — `uv run ruff check .` и `uv run ruff format --check .`
в каталоге компонента.

`test-<компонент>` по умолчанию — `uv run pytest -q` в каталоге
компонента. Для некоторых компонентов есть свои правила:

| Цель | Что делает дополнительно |
|---|---|
| `test-control-plane` | Поднимает `db-test` из `services/control-plane/docker-compose.yml` (профиль `test`, порт 5434), запускает `pytest tests/unit tests/client`, затем останавливает БД. |
| `test-skill-sdk` | Тесты `skill-sdk` со всеми extras, затем сквозной тест исполнителя через `control-plane` (`tests/test_executor_e2e.py`). |
| `test-memory-service` | `pytest` с extra `mcp`, без `tests/integration`. |

!!! tip "Тестовые БД занимают порты хоста"

    `test-control-plane` поднимает контейнер на порту 5434. Если порт занят,
    тесты не стартуют.

### make packages-check

```bash
make packages-check
```


1. `package-sdk check` — схема, ссылки и валидаторы ядра для
   пакетов в `packages/`.
2. `package-sdk check --install <файл установки>` —
   проверка файла установки.
3. `pytest -q tools/tests` (через `uv run --no-project` с `pytest`,
   `pyyaml`, `jsonschema`, `regex`, `ruamel.yaml`).

См. [Пакеты каталога](../control-plane/catalog-packages.md).

## Документация и репозиторий

| Цель | Команда | Примечание |
|---|---|---|
| `linkcheck` | `python3 tools/linkcheck.py` | Относительные ссылки в документации суперпроекта. |
| `submodules` | `git submodule update --init --recursive` | После клонирования и после bump указателей. |
| `status` | `git submodule status` и `git status --short` | Быстрый обзор состояния. |
| `guide` | `cd guide && uv run --with-requirements requirements.txt mkdocs build --strict` | Любое предупреждение MkDocs — ошибка сборки. |
| `guide-serve` | `… mkdocs serve -a 127.0.0.1:8008` | Живой просмотр руководства. |

## Типичные последовательности

=== "Первый запуск"

    ```bash
    make submodules
    make secrets
    make config
    make up
    make smoke
    make bootstrap
    # вписать выведенный IAM_TENANT_ID в .env, затем
    make up
    ```

=== "Заново после сброса volumes"

    ```bash
    tools/compose --profile "*" down -v
    make reset-state
    make up
    make bootstrap
    ```

=== "Перед коммитом в компонент"

    ```bash
    make check-control-plane
    ```

=== "Обновление стенда"

    ```bash
    git pull --ff-only
    make submodules
    make up PROFILES="core edge"
    make smoke
    ```

## См. также

- [Установка и первый запуск](../getting-started/quickstart.md)
- [Bootstrap](../getting-started/bootstrap.md)
- [Сервисы и порты](services-and-ports.md)
- [Обновление и миграции](../operations/upgrades.md)
