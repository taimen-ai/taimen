# Резервное копирование

Что в установке Taimen нужно бэкапить, как снимать дампы каждой базы, какие
особенности есть у базы памяти и как восстановить
установку целиком или по частям. Статья для инженера эксплуатации.

## Что бэкапить

Сервисы платформы stateless: всё состояние лежит в томах Docker и в
нескольких файлах на хосте.

| Объект | Где | Содержимое | Критичность |
|---|---|---|---|
| БД IAM | том `iam_db`, сервис `iam-db`, БД `iam` | Tenants, principals, хэши PAT, service accounts, audiences, audit, outbox | Критично |
| БД Control Plane | том `control_plane_db`, сервис `control-plane-db`, БД `control_plane` | Задачи, claims, runs, артефакты, approvals, журнал событий и его архив, курсоры потребителей, IAM bindings | Критично |
| БД памяти | том `memory_db`, сервис `memory-db`, БД `company_brain` | Граф знаний (таблицы PostgreSQL), чанки и вектора (pgvector), наблюдения, трассы контекста | Критично; содержит данные заказчика, возможно ПДн |
| БД Keycloak | том `keycloak_db`, сервис `keycloak-db`, БД `keycloak` | Живой realm, пользователи и их пароли | Критично при профиле `idp`: без неё людей заводят заново |
| Объекты MinIO | том `platform_minio` | Содержимое артефактов Control Plane (бакет `CP_S3_BUCKET`) | Критично: MinIO входит в профиль `core`; бэкапить вместе с `control-plane-db` |
| Сертификаты | том `caddy_data` | Сертификаты, ключи, ACME-аккаунт | Желательно: без него сертификаты выпускаются заново |
| Конфигурация | `.env`, `secrets/`, `deploy/state/<env>.json`, Caddyfile установки | Секреты, ключ подписи IAM, PAT, идентификаторы bootstrap | Критично; хранить отдельно и шифровать |

Имена томов в Docker — с префиксом проекта:
`${COMPOSE_PROJECT_NAME}_iam_db` и т. д. (переопределяются переменными
`VOLUME_*` в `.env`). Точный список:

```bash
docker volume ls --filter "name=${COMPOSE_PROJECT_NAME:-taimen}_"
```

!!! danger "Ключ подписи IAM и `.env` — часть бэкапа"
    Без `secrets/iam-signing.pem` восстановленная БД IAM выдаёт токены
    новым ключом — это переживаемо. Без `.env` не подойдут пароли к
    восстановленным томам, а без `deploy/state/<env>.json` повторный
    bootstrap заведёт tenant и principals заново. Храните конфигурацию
    отдельно от дампов, в зашифрованном виде.

Runner-хост критичных данных не хранит: рабочие копии воссоздаются из
bare-зеркал, опубликованные ветки задач лежат в forge. Потеряется только
неопубликованная работа текущих задач.

## Логические дампы PostgreSQL

Все базы снимаются `pg_dump` в формате custom изнутри контейнеров. Базы
разные и восстанавливаются независимо; внутри Control Plane состояние,
журнал, архив и курсоры лежат в одной базе и согласованы одним дампом.

| Сервис | Пользователь | База |
|---|---|---|
| `iam-db` | `iam` | `iam` |
| `control-plane-db` | `control_plane` | `control_plane` |
| `memory-db` | `memory` | `company_brain` |
| `keycloak-db` | `keycloak` | `keycloak` |

### Скрипт ежедневного бэкапа

```bash
#!/usr/bin/env bash
# /opt/taimen/backup.sh — дампы всех поднятых БД + конфигурация + тома без СУБД
set -euo pipefail
cd /opt/taimen/src
STAMP=$(date -u +%Y%m%dT%H%MZ)
OUT=/opt/taimen/backups/$STAMP
mkdir -p "$OUT" && chmod 700 "$OUT"
DC=(tools/compose --profile "*")

dump() {  # dump <сервис> <пользователь> <база>
  if "${DC[@]}" ps --status running --services | grep -qx "$1"; then
    "${DC[@]}" exec -T "$1" pg_dump -U "$2" -d "$3" -Fc > "$OUT/$1-$3.dump"
  fi
}
dump iam-db           iam            iam
dump control-plane-db control_plane  control_plane
dump memory-db        memory         company_brain
dump keycloak-db      keycloak       keycloak

# Конфигурация (секреты!) — отдельным архивом
tar czf "$OUT/config.tgz" .env secrets deploy/state /opt/taimen/Caddyfile

# Тома без СУБД: сертификаты и объекты MinIO
vol() { docker run --rm -v "$1":/data:ro -v "$OUT":/backup alpine tar czf "/backup/$1.tgz" -C /data .; }
P=${COMPOSE_PROJECT_NAME:-taimen}
vol "${P}_caddy_data"
docker volume inspect "${P}_platform_minio" >/dev/null 2>&1 && vol "${P}_platform_minio"

chmod 600 "$OUT"/*
find /opt/taimen/backups -maxdepth 1 -type d -mtime +14 -exec rm -rf {} +
```

Запуск по расписанию (systemd timer или cron) и перед каждой выкладкой:

```cron
15 3 * * * root /opt/taimen/backup.sh >> /var/log/taimen-backup.log 2>&1
```

!!! warning "Бэкап на том же диске — не бэкап"
    Копируйте каталог дампов за пределы хоста и шифруйте: дампы памяти
    содержат данные заказчика, дамп IAM — хэши credential'ов,
    `config.tgz` — секреты в открытом виде.

### Согласованность между базами

Дампы разных баз снимаются в разные моменты. Платформа это переносит:

- **Control Plane ↔ память.** Доставка в память идёт через outbox и курсор
  `context-adapter`, лежащие в базе Control Plane. Если память восстановлена
  из более старого дампа, чем Control Plane, выполните `:rebuild` — адаптер
  переиграет журнал, память дедуплицирует повторы по `event:<uuid>`. Если
  наоборот — адаптер доставит часть событий повторно, что тоже безопасно.
- **IAM ↔ Control Plane.** Bindings лежат в Control Plane, principals и PAT —
  в IAM. Principal, созданный после дампа IAM, при восстановлении пропадёт;
  его binding в Control Plane перестанет срабатывать (вход закроется) —
  перевыпустите principal и binding.
- **Control Plane ↔ MinIO.** Записи артефактов (размер, media type,
  SHA-256) в базе Control Plane, байты — в MinIO. Копию тома снимайте
  **после** дампа базы: объекты неизменяемы, и всё, на что ссылается дамп,
  уже лежит в томе. Если том окажется старше базы, выдача части артефактов
  ответит `503 content_store_unavailable`. Подробнее — в
  [Хранилище объектов](object-storage.md#backup).

## Особенность памяти: граф в таблицах PostgreSQL

`memory-db` — PostgreSQL 16 с расширениями pgvector и `pg_trgm`. Граф памяти —
обычные таблицы `graph_nodes` и `graph_edges` в схеме `CB_GRAPH_NAME`
(MEM-ADR-023), поэтому особых шагов нет: база снимается `pg_dump` и
восстанавливается `pg_restore`, в том числе в другой кластер (новый том, новый
хост).

```bash
tools/compose stop memory-service
tools/compose exec -T memory-db pg_restore -U memory -d company_brain \
  --clean --if-exists --no-owner < backups/<stamp>/memory-db-company_brain.dump
tools/compose up -d memory-service
curl -fsS http://127.0.0.1:18001/healthz     # {"ok": true, "graph": ..., "nodes": N, "chunks": M}
```

!!! note "Установка, где граф ещё в Apache AGE"
    До memory-service v0.2.1 граф хранился в Apache AGE. Дамп такой установки
    восстанавливается так же (образ `memory-db` поставки основан на образе
    Apache AGE, расширение в нём есть), а затем граф переносится в таблицы
    командой `cb migrate-graph-from-age` при остановленном сервисе: сначала
    `--dry-run`, потом перенос. После запуска сервиса перенос повторно не
    запускайте. Команда читает таблицы меток AGE напрямую, мимо каталога,
    поэтому правка OID каталога AGE для переноса не нужна. Подробно — в
    [Конфигурации памяти](../memory/configuration.md#age-migration).

После любого восстановления памяти сверяйте счётчики `nodes` и `chunks` из
`/healthz` со значениями до инцидента.

## Восстановление

### Одна база Control Plane

```bash
tools/compose stop control-plane-worker context-adapter control-plane-api
tools/compose exec -T control-plane-db pg_restore -U control_plane -d control_plane \
  --clean --if-exists --no-owner < backups/<stamp>/control-plane-db-control_plane.dump
tools/compose up -d control-plane-api           # применит миграции, если дамп старее
curl -fsS http://127.0.0.1:18000/health/ready    # 503 migrations_pending, пока ревизия отстаёт
tools/compose up -d control-plane-worker context-adapter
```

Частичное восстановление отдельных таблиц Control Plane не поддерживается:
журнал, состояние и курсоры связаны инвариантами (append-only, внешние
ключи, позиции курсоров).

Если после восстановления память опережает журнал — ничего делать не нужно.
Если память отстаёт или потеряна — перестройте доставку:

```bash
curl -s -X POST http://127.0.0.1:18000/api/v1/operations/context-adapter/<tenant-id>:rebuild \
  -H "Authorization: Bearer <admin access token>" -H 'Content-Type: application/json' \
  -d '{"reason": "memory restored from backup"}'
```

### База IAM

```bash
tools/compose stop iam-service
tools/compose exec -T iam-db pg_restore -U iam -d iam --clean --if-exists --no-owner \
  < backups/<stamp>/iam-db-iam.dump
tools/compose up -d iam-service
```

!!! danger "Отзывы после даты дампа теряются"
    Восстановленная база IAM не знает об отзывах PAT и service accounts,
    сделанных после снятия дампа: такие credentials снова становятся
    действительными. Сразу после восстановления повторите отзывы по журналу
    инцидентов или внешнему журналу операций.

### Полное восстановление на новый хост

1. Подготовьте хост по [Промышленному развёртыванию](deployment.md), клонируйте
   суперпроект **на том же коммите**, что работал до аварии.
2. Распакуйте `config.tgz`: `.env`, `secrets/`, `deploy/state/`, Caddyfile.
   Восстановите владельца ключей: `chown 10001:10001 secrets/*.pem`.
3. Восстановите том `caddy_data` до первого запуска `caddy`:

    ```bash
    docker volume create taimen_caddy_data
    docker run --rm -v taimen_caddy_data:/data -v "$PWD/backups/<stamp>":/backup alpine \
      tar xzf /backup/taimen_caddy_data.tgz -C /data
    ```

4. Поднимите только базы и дождитесь `healthy`:

    ```bash
    tools/compose up -d iam-db control-plane-db memory-db    # + базы других поднятых профилей
    ```

5. Восстановите каждую базу `pg_restore --clean --if-exists --no-owner`.
6. Для памяти: если граф установки ещё в Apache AGE, перенесите его
   `cb migrate-graph-from-age` до запуска memory-service (см. выше); затем
   проверьте `/healthz`.
7. Восстановите том MinIO (`platform_minio`) тем же способом, что
   `caddy_data`: в нём содержимое артефактов ядра.
   Если ядро работает с внешним S3 (`deploy/local/compose.s3.example.yml`), восстановите
   бакет средствами провайдера.
8. Поднимите всё: `tools/compose --profile core --profile edge … up -d`.
9. Проверьте `make smoke`, `/health/ready`, вход оператора, метрику
   `context_adapter_parked_tenants`.
10. Переключите DNS на новый хост.

## Проверка бэкапов

Бэкап, который ни разу не восстанавливали, — гипотеза. Раз в месяц:

- поднимите копию установки на отдельной машине или в отдельном
  compose-проекте (`COMPOSE_PROJECT_NAME=taimen-restore`, свои порты);
- восстановите все дампы, выполните шаги полного восстановления;
- сравните число задач, событий журнала, principals, узлов и чанков памяти
  с боевыми значениями на момент дампа.

## Хранение журнала Control Plane

Журнал событий растёт вместе с работой. Retention — операторская команда,
планировщика нет: `:archive` переносит подтверждённую историю в архивную
таблицу той же базы, `:prune` удаляет физически. Горизонт ограничен
минимальным курсором потребителей, поэтому нужное кому-то не удаляется.
Подробности и команды — в [Мониторинге и здоровье](monitoring.md) и
[Событиях Control Plane](../control-plane/events.md).

!!! warning
    `:prune` — единственная операция, после которой данные теряются. Перед
    ней должен быть свежий бэкап базы Control Plane.

## См. также

- [Обновление и миграции](upgrades.md)
- [Хранилище объектов (MinIO)](object-storage.md)
- [Аварийные процедуры](emergency.md)
- [Модель знаний памяти](../memory/knowledge-model.md)
- [Контекст задачи и память](../control-plane/context.md)
- [Память и контекст — диагностика](../troubleshooting/memory.md)
