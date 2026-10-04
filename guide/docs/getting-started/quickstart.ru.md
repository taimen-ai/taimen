# Установка и первый запуск

Пошаговая процедура: от клонирования суперпроекта до работающего ядра платформы
(профили `core edge`), прошедшего bootstrap и smoke-проверку. Рассчитана на
локальную машину или тестовый сервер; для промышленного стенда шаги те же, но
`.env` и Caddyfile другие — см. [Промышленное развёртывание](../operations/deployment.md).

!!! abstract "Что получится в конце"
    - 9 контейнеров профилей `core` и `edge` в состоянии `running`/`healthy`;
    - tenant, оператор-человек с правами администратора, проект и workspace;
    - PAT оператора в `secrets/harness-pat` и service account ядра в
      `secrets/control-plane-iam.env`;
    - каталог по файлу установки `deploy/packages.yaml` (ядро без пакетов знает только
      системный тип задачи `task`).

## Шаг 0. Проверить требования

Убедитесь, что установлены Docker с Compose v2.24+, git, make, Python 3 с
uv (без него — PyYAML и jsonschema в системном Python), openssl, и свободны порты `80`, `18000`, `18001`,
`18010`. Подробно — [Требования](requirements.md).

## Шаг 1. Получить исходники

Компоненты подключены git-сабмодулями, поэтому клонировать нужно рекурсивно:

```bash
git clone --recurse-submodules <url-суперпроекта> taimen
cd taimen
```

Если репозиторий уже склонирован без сабмодулей:

```bash
make submodules          # git submodule update --init --recursive
make status              # указатели сабмодулей и незакоммиченные изменения
```

Сабмодули встают на ревизии, закреплённые в суперпроекте, — это и есть
согласованная версия платформы. Не переключайте их на ветки вручную, если не
разрабатываете сам компонент.

## Шаг 2. Сгенерировать `.env` и ключи

```bash
make secrets
```

Что делает цель (`Makefile`, `tools/fill_secrets.py`):

1. Если `.env` нет — копирует `.env.example` в `.env` и ставит права `600`.
2. Заполняет **пустые** секреты случайными значениями (`secrets.token_hex`):
   пароли всех БД, `CP_BOOTSTRAP_TOKEN`, `IAM_BOOTSTRAP_TOKEN`,
   `MEMORY_API_KEY`, пароль администратора Keycloak, ключи MinIO. Уже заданные
   значения не трогает — повторный запуск безопасен.
3. Создаёт каталог `secrets/`.
4. Генерирует RSA-3072 ключ подписи `secrets/iam-signing.pem` и секреты
   консоли `secrets/runtime-console-{oidc,cookie}-secret` (если их нет) с
   правами `600`.

```text
создан .env
заполнены секреты: CP_POSTGRES_PASSWORD, IAM_POSTGRES_PASSWORD, …, S3_SECRET_ACCESS_KEY
секреты на месте: .env, secrets/*.pem (на Linux: chown 10001 secrets/*.pem)
```

На Linux сразу отдайте ключи uid контейнеров:

```bash
sudo chown 10001:10001 secrets/*.pem
```

## Шаг 3. Проверить `.env` перед первым запуском

Для ядра (`core edge`) правки `.env` после `make secrets` не нужны.


### Необязательно: LLM-провайдер

Память по умолчанию работает офлайн (`MEMORY_EMBEDDING_PROVIDER=fake`,
`MEMORY_LLM_PROVIDER=echo`): поиск работает, но эмбеддинги фиктивные. Для
настоящего поиска укажите OpenAI-совместимый endpoint — см.
[Конфигурацию .env](configuration.md).

## Шаг 4. Поднять ядро

```bash
make config       # проверить deploy/local/compose.yml после интерполяции
make up           # tools/compose --profile core --profile edge up -d --build
```

Первая сборка занимает несколько минут. Порядок старта задан `depends_on` с
healthcheck: базы → `iam-service` и `memory-service` → `control-plane-api`
(применяет миграции Alembic) → `control-plane-worker` и `context-adapter`.

Проверить состояние:

```bash
make ps
```

```text
NAME                           SERVICE                STATUS
taimen-caddy-1                 caddy                  Up
taimen-context-adapter-1       context-adapter        Up
taimen-control-plane-api-1     control-plane-api      Up (healthy)
taimen-control-plane-db-1      control-plane-db       Up (healthy)
taimen-control-plane-worker-1  control-plane-worker   Up
taimen-iam-db-1                iam-db                 Up (healthy)
taimen-iam-service-1           iam-service            Up (healthy)
taimen-memory-db-1             memory-db              Up (healthy)
taimen-memory-service-1        memory-service         Up (healthy)
```

Логи отдельного сервиса: `make logs svc=control-plane-api`.

## Шаг 5. Выполнить bootstrap

Bootstrap создаёт tenant, оператора, его PAT, проект, workspace, каталог типов
задач и service accounts. Скрипт идемпотентен: повторный запуск пропускает
сделанное.

```bash
make bootstrap ARGS='--operator "Alice Operator"'
```

`make bootstrap` запускает `deploy/bootstrap.py` через
`uv run --no-project --with pyyaml --with jsonschema python3`, если uv
установлен, иначе — системным `python3` (тогда PyYAML и jsonschema нужны в нём).

`--operator` — отображаемое имя первого человека-администратора; задайте своё.
Ожидаемый вывод (идентификаторы сокращены):

```text
1. ожидание сервисов
2. IAM tenant, audience, principal оператора
   IAM tenant <tenant-id> оператор <iam-principal-id>
   !! впишите в .env: IAM_TENANT_ID=<tenant-id> (нужен launcher харнесса и fleet-controller)
2a. service account Control Plane в IAM
   выпущен → secrets/control-plane-iam.env client <client-id>
   !! перезапустите ядро, чтобы оно взяло env-файл: tools/compose up -d control-plane-api control-plane-worker context-adapter
3. Control Plane bootstrap с binding оператора
   tenant <tenant-id> оператор <cp-principal-id> binding <binding-id>
4. PAT оператора
   выпущен → secrets/harness-pat prefix <prefix>
   обмен PAT → access token: ok
5. Control Plane: project template, workspace, legacy-ключ
   project <project-id> workspace <workspace-id>
5b. Каталог из пакетов: deploy/packages.yaml (TAI-ADR-0044)
   …
5c. notification-service: service account IAM по описанию, личность в ядре, env-файл
   выпущен → secrets/notification-iam.env client <client-id>
   !! перезапустите сервис: tools/compose --profile notify up -d notification-service
   ревизия 1 principal <principal-id>
5d. fleet-controller: service account IAM по описанию, личность в ядре, env-файл
   …
   legacy admin api-key отозван
готово: deploy/state/taimen.json
credential для MCP-плагина/CLI: ~/.config/iam/credentials.json, ключ http://taimen.localhost/iam|<tenant-id>|<iam-principal-id> → содержимое secrets/harness-pat
```

Что происходит на каждом шаге — в статье [Bootstrap](bootstrap.md).

## Шаг 6. Применить результаты bootstrap

1. Впишите tenant IAM в `.env` (до bootstrap переменная пуста):

    ```bash
    TENANT=$(python3 -c 'import json;print(json.load(open("deploy/state/taimen.json"))["iamTenantId"])')
    sed -i.bak -E "s/^IAM_TENANT_ID=.*/IAM_TENANT_ID=$TENANT/" .env
    ```

2. Перезапустите процессы ядра, чтобы они подхватили service account
   (`secrets/control-plane-iam.env`) — после этого Control Plane ходит в память
   токеном IAM, а не статическим ключом:

    ```bash
    tools/compose up -d control-plane-api control-plane-worker context-adapter
    ```

Имя файла состояния — `deploy/state/<COMPOSE_PROJECT_NAME>.json` (по умолчанию
`taimen.json`) или значение `--name`.

## Шаг 7. Smoke-проверка

```bash
make smoke
```

```text
  iam-service          OK  200 http://127.0.0.1:18010/healthz
  control-plane-api    OK  200 http://127.0.0.1:18000/health/ready
  memory-service       OK  200 http://127.0.0.1:18001/healthz
  keycloak             —   не запущен
```

`tools/smoke.py` проверяет healthz только запущенных сервисов (не поднятые
помечаются «не запущен» и ошибкой не считаются) и возвращает ненулевой код,
если хоть один запущенный ответил ошибкой.

## Шаг 8. Проверить вход оператора

Обменяйте PAT оператора на токен Control Plane и спросите, кто вы:

```bash
PAT=$(cat secrets/harness-pat)
TOKEN=$(curl -s -X POST http://127.0.0.1:18010/api/v1/platform-access-tokens:exchange \
  -H 'Content-Type: application/json' \
  -d "{\"token\": \"$PAT\", \"audience\": \"control-plane\"}" | jq -r .accessToken)

curl -s http://127.0.0.1:18000/api/v1/harness/context \
  -H "Authorization: Bearer $TOKEN" | jq '{tenant, principal, permissions}'
```

```json
{
  "tenant": { "id": "<tenant-id>", "slug": "taimen", "name": "Taimen" },
  "principal": { "id": "<principal-id>", "kind": "human", "displayName": "Alice Operator" },
  "permissions": ["admin", "approvals.decide", "tasks.claim", "…"]
}
```

Интерактивная документация API Control Plane доступна по
`http://taimen.localhost/docs` (через Caddy) или `http://127.0.0.1:18000/docs`.

Дальше — [Первая задача](first-task.md).

## Остановка и сброс

| Действие | Команда | Данные |
|---|---|---|
| Остановить | `make down` | сохраняются в volumes |
| Поднять снова | `make up` | те же данные; bootstrap повторять не нужно |
| Пересобрать один сервис | `tools/compose build control-plane-api && tools/compose up -d control-plane-api control-plane-worker context-adapter` | сохраняются |
| Полный сброс | см. ниже | **удаляются** |

!!! danger "Полный сброс стенда"
    Удаление volumes уничтожает все задачи, identity и знания. После него
    обязательно уберите и **состояние bootstrap** — иначе скрипт остановится
    на проверке state (IAM tenant из файла не найден):

    ```bash
    tools/compose --profile "*" down -v
    make reset-state
    make up && make bootstrap
    ```

    `make reset-state` переносит `deploy/state/<имя>.json` и выданные
    bootstrap credentials в `secrets/stale-<время>/`; `.env` и ключи подписи
    остаются на месте.

## Типичные проблемы

| Симптом | Причина | Что сделать |
|---|---|---|
| `required variable … is missing a value` при `make up` | пусты секреты, которые генерирует `make secrets` | `make secrets` |
| `set CP_POSTGRES_PASSWORD` и подобные | не выполнен `make secrets` или `.env` не в корне | `make secrets` |
| `iam-service` рестартует, в логах `PermissionError` на ключ подписи | Linux, файл ключа принадлежит root | `sudo chown 10001:10001 secrets/*.pem` |
| bootstrap: `нужен PyYAML` / `нужен jsonschema` | uv не установлен, у системного Python нет зависимостей | установить uv (`make bootstrap` возьмёт их сам) или `pip install pyyaml jsonschema` |
| bootstrap: `… ссылается на IAM tenant …, которого нет в IAM (volumes сброшены?)` | volumes сброшены, а `deploy/state/<имя>.json` остался | `make reset-state` и повторить bootstrap |
| bootstrap: `HTTP 409 … already_bootstrapped` на шаге 3 | Control Plane уже инициализирован, а файла состояния нет | восстановить `deploy/state/<имя>.json` или сделать полный сброс |
| `bind: address already in use` на `80` | порт занят другим веб-сервером | освободить порт или поднимать без `edge` (`make up PROFILES=core`) и работать через `127.0.0.1` |
| `curl: Could not resolve host: taimen.localhost` | системный резолвер не знает `*.localhost` | строка в `/etc/hosts` или адреса `127.0.0.1:<порт>` |

Больше — в [Установке и запуске — диагностике](../troubleshooting/startup.md).

## См. также

- [Конфигурация .env](configuration.md)
- [Bootstrap](bootstrap.md)
- [Первая задача](first-task.md)
- [Цели make](../reference/make.md)
