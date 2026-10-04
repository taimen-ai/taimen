# Установка и запуск

Отказы при подготовке окружения, сборке образов, старте контейнеров,
миграциях и bootstrap. Каждая таблица построена как «симптом → причина →
решение»; команды выполняются из корня клона суперпроекта.

## Конфигурация compose

| Симптом | Причина | Решение |
|---|---|---|
| `required variable CP_POSTGRES_PASSWORD is missing a value: set CP_POSTGRES_PASSWORD` (или другая переменная с `:?`) | Нет `.env`, compose запущен не из корня клона или с `-f` без `--env-file` | `make secrets`; запускать из корня; иначе `--env-file <корень клона>/.env` |
| `no such service: control-plane-context-adapter` | Неверное имя сервиса. Ошибка в одном имени роняет всю команду | Имя адаптера — `context-adapter`; список: `tools/compose --profile "*" config --services` |
| Ошибка разбора `env_file` с полем `required` | Старый Docker Compose | Обновить Compose до v2.24+ |
| `network <имя> declared as external, but could not be found` | Дополнительный compose-файл установки ссылается на внешнюю сеть, которой нет | `docker network create <имя>` до `up` |
| Ошибка монтирования тома с неизвестным драйвером | Compose-файл установки использует сторонний volume driver, плагин не установлен | Установить плагин (и его systemd-юнит) до первого `up` |
| `Bind for 127.0.0.1:18000 failed: port is already allocated` | Порт занят другим процессом или второй копией стека | Освободить порт или задать другой `*_HOST_PORT` в `.env` |
| `tools/compose ps` показывает не все сервисы | Профиль не указан | `tools/compose --profile "*" ps`; `make ps` делает это сам |

Проверить итоговую конфигурацию после интерполяции:

```bash
make config PROFILES="core idp harness edge"
tools/compose --profile core --profile edge config | less
```

## Сборка образов

| Симптом | Причина | Решение |
|---|---|---|
| Сборка `control-plane`, `memory-service` падает на установке зависимостей: не найден `../platform-auth-sdk` или пустой каталог компонента | Сабмодули не инициализированы или на другой ревизии | `git submodule update --init --recursive`; `git submodule status` без `-` и `+` |
| После `build` worker или адаптер работают на старом коде | Собран не тот сервис или не пересоздан контейнер. У `control-plane-worker` и `context-adapter` нет `build:`, они используют образ `control-plane-api` | `tools/compose build control-plane-api` и `tools/compose up -d control-plane-api control-plane-worker context-adapter` |
| Сборка на хосте идёт очень долго, стек в это время частично недоступен | `make up` собирает во время переключения | Раздельно: `tools/compose … build`, затем `up -d` |
| Контекст сборки огромный, сборка медленная | Нарушен корневой `.dockerignore` или в дереве лишние каталоги (`node_modules`, `.venv`, `.git`) | Проверить `.dockerignore` в корне; не класть данные в рабочее дерево |
| Не хватает памяти при сборке (`Killed` в выводе сборки) | Мало RAM, нет swap | Добавить swap; собирать при остановленных тяжёлых необязательных сервисах |

## Старт контейнеров и healthcheck

| Симптом | Причина | Решение |
|---|---|---|
| Контейнер вечно `unhealthy`, хотя сервис отвечает | Healthcheck обращается к `localhost`: в slim/busybox-образах он резолвится в IPv6 `::1`, а сервис слушает только IPv4 | В своих healthcheck использовать `127.0.0.1`. Все healthcheck поставки уже так написаны |
| `iam-service` стартует, но обмен токенов отвечает `500`; в логах `PermissionError` на `/run/secrets/iam_signing_key` | Файл ключа принадлежит root при режиме `600`, а сервис работает под uid 10001 | `sudo chown 10001:10001 secrets/iam-signing.pem`, режим оставить `600` |
| Контейнер, читающий PAT или токен из `secrets/` (исполнители пакета), падает с `Permission denied` | Та же причина: владелец не uid 10001 | `chown 10001` на файлы, права не ослаблять |
| `control-plane-worker` и `context-adapter` висят в `Created`/`Waiting` | Ждут `service_healthy` от `control-plane-api` | Разбираться с `control-plane-api` (см. ниже) |
| `control-plane-api` рестартует; в логах ошибка Alembic | Миграция не применилась | Прочитать ошибку; при неисправимой — откат релиза, см. [Обновление и миграции](../operations/upgrades.md) |
| `/health/ready` → `503 migrations_pending`, ревизия БД **новее** head | Поверх новой схемы запущен старый образ | Вернуть образ нового релиза или выполнить downgrade новым образом |
| `/health/ready` → `503 database_unreachable` | База не поднялась, неверный пароль, закончился диск | `tools/compose logs control-plane-db`, `df -h` |
| `password authentication failed for user "…"` после смены пароля в `.env` | `POSTGRES_PASSWORD` применяется только при инициализации пустого тома | Сменить пароль роли `ALTER ROLE` в базе или вернуть прежнее значение в `.env`, см. [Секреты и ротация](../operations/secrets.md) |
| `keycloak-db` не стартует: `set KEYCLOAK_DB_PASSWORD` | Не задан пароль БД Keycloak | `make secrets` или задать вручную |
| `keycloak` долго `starting` | Нормально: JVM и импорт realm, `start_period` 40 с, до 20 попыток | Ждать; при OOM — поднять `KEYCLOAK_MEM_LIMIT` |
| `control-plane-api` не стартует: зависимость `minio-bootstrap` завершилась с ошибкой | Одноразовый контейнер упал | `tools/compose logs minio minio-bootstrap` |
| `memory-service` падает с `graph with oid … does not exist` | База памяти восстановлена логическим дампом в новый кластер | Исправление OID каталога AGE, см. [Резервное копирование](../operations/backup.md) |
| `harness-launcher` не пускает людей или сервис профиля `harness` не стартует без `idp` | Профиль `harness` требует `idp` (вход через Keycloak) | Поднимать профили вместе: `make up PROFILES="core idp harness edge"` |

## Периметр (Caddy)

| Симптом | Причина | Решение |
|---|---|---|
| `caddy` в логах: `challenge failed`, `no valid A records`, `429` | Имя не указывает на хост, закрыт 80/443 или превышены лимиты ACME-центра после серии неудач | Проверить `dig`, файрвол; убрать из Caddyfile имена без DNS; после `429` ждать окна лимита |
| Правка Caddyfile не применилась после `caddy reload` | Файл заменён новым inode (`mv`, атомарная запись), bind-mount видит старый | Писать в тот же файл (`cat new > Caddyfile`) или `tools/compose up -d --force-recreate caddy` |
| `502` на маршруте | Upstream не поднят (профиль выключен) или упал | `tools/compose ps <upstream>`; убрать лишний маршрут |
| Свой маршрут отвечает `302` на `/console/` | Маршрут объявлен после блока корня (`handle { redir * /console/ 302 }`) | Перенести его выше блока корня |

Подробнее — в [Периметре и TLS](../operations/edge-and-tls.md).

## make и bootstrap

| Симптом | Причина | Решение |
|---|---|---|
| `make secrets`: `openssl: command not found` | Нет openssl на хосте | Установить openssl |
| `bootstrap.py`: `не дождался http://127.0.0.1:18000/health/ready` | Стек не поднят, API не готов (миграции, БД) или изменён `CP_HOST_PORT` без пересоздания | `make smoke`, `tools/compose ps`; порты берутся из `.env` |
| `bootstrap.py`: `HTTP 401: {"detail":"unauthorized"}` на запросах к IAM | `IAM_BOOTSTRAP_TOKEN` в `.env` не совпадает с тем, с которым запущен `iam-service` (например, `.env` правили без пересоздания) | `tools/compose up -d iam-service` или вернуть прежнее значение |
| `bootstrap.py`: `HTTP 409 … already_bootstrapped` | Потерян `deploy/state/<env>.json`, а Control Plane уже инициализирован | Восстановить state-файл из бэкапа; bootstrap Control Plane выполняется один раз |
| `bootstrap.py`: `нужен PyYAML` / `нужен jsonschema` | uv не установлен, у системного Python нет зависимостей шага каталога из пакетов | установить uv (`make bootstrap` подключит их сам) или `apt install python3-yaml python3-jsonschema` / `pip install pyyaml jsonschema` |
| `bootstrap.py`: `… ссылается на IAM tenant …, которого нет в IAM (volumes сброшены?)` | Volumes сброшены, а `deploy/state/<env>.json` остался | `make reset-state` и повторить `make bootstrap` |
| `bootstrap.py`: `!! IAM не умеет PATCH audiences` | `iam-service` старше скрипта | Обновить установку целиком (сабмодули на ревизиях суперпроекта) |
| `bootstrap.py`: `!! tenant ядра … ≠ tenant IAM …` | Инсталляция старше единого tenant или Control Plane проигнорировал `tenantId` | Жить с разными id: в `.env` вписывать tenant IAM, который печатает скрипт |
| После bootstrap ядро продолжает ходить в память статическим ключом | Процессы ядра не пересозданы после появления `secrets/control-plane-iam.env` | `tools/compose up -d control-plane-api control-plane-worker context-adapter` |
| `make smoke` пишет `не запущен` для нужного сервиса | Профиль не поднят или сервис упал | `tools/compose --profile "*" ps` |

## Разное

| Симптом | Причина | Решение |
|---|---|---|
| `ssh <алиас>` падает с `bind [127.0.0.1]:… Address already in use` | В алиасе прописан `LocalForward`, порт занят другой сессией; ssh падает целиком | `ssh -o ClearAllForwardings=yes <алиас>`; для git — `GIT_SSH_COMMAND='ssh -o ClearAllForwardings=yes'` |
| Статические файлы, доставленные rsync с macOS, отдаются `403` | Встроенный в macOS rsync не поддерживает `--chmod`, файлы приезжают с правами `600` | После доставки `chmod -R a+rX <каталог>` на хосте |
| Диск быстро заполняется | Логи Docker без ротации, кэш сборки, журнал Control Plane | См. [Ресурсы и масштабирование](../operations/capacity.md) |

## См. также

- [Промышленное развёртывание](../operations/deployment.md)
- [Обновление и миграции](../operations/upgrades.md)
- [Установка и первый запуск](../getting-started/quickstart.md)
- [Аутентификация и доступ](auth.md)
