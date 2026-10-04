# Резервное копирование

Что в установке Taimen нужно бэкапить, как снимать дампы каждой базы, какие
особенности есть у графовой базы памяти (Apache AGE) и как восстановить
установку целиком или по частям. Статья для инженера эксплуатации.

## Что бэкапить

Сервисы платформы stateless: всё состояние лежит в томах Docker и в
нескольких файлах на хосте.

| Объект | Где | Содержимое | Критичность |
|---|---|---|---|
| БД IAM | том `iam_db`, сервис `iam-db`, БД `iam` | Tenants, principals, хэши PAT, service accounts, audiences, audit, outbox | Критично |
| БД Control Plane | том `control_plane_db`, сервис `control-plane-db`, БД `control_plane` | Задачи, claims, runs, артефакты, approvals, журнал событий и его архив, курсоры потребителей, IAM bindings | Критично |
| БД памяти | том `memory_db`, сервис `memory-db`, БД `company_brain` | Граф знаний (Apache AGE), чанки и вектора (pgvector), наблюдения, трассы контекста | Критично; содержит данные заказчика, возможно ПДн |
| Объекты MinIO | том `platform_minio` | Содержимое артефактов Control Plane (бакет `CP_S3_BUCKET`) | Критично: MinIO входит в профиль `core`; бэкапить вместе с `control-plane-db` |
| Хранилище секретов | том `openbao_data`, сервис `openbao` | Материал подключений, секреты агентов, OAuth-приложения типов, политики и роли агентов | Критично: без него подключения подключаются заново, секреты агентов задаются снова. Не копировать том, а снимать `bao operator raft snapshot` токеном `backup` — см. [Хранилище секретов](secret-store.md#backup). Ключ распечатывания `secrets/openbao-unseal.key` хранить **отдельно** от снимков |
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

## Особенность памяти: Apache AGE и OID

`memory-db` — PostgreSQL 16 с расширениями Apache AGE (граф) и pgvector.
Каталог AGE хранит ссылки на граф как **OID PostgreSQL**: `ag_graph.graphid`
и `ag_label.graph` — обычные `oid`, тогда как `ag_graph.namespace` имеет тип
`regnamespace` и при восстановлении переразрешается по имени схемы. После
`pg_restore` в **другой** кластер (новый том, новый хост) OID схемы графа
меняется, а `graphid` приезжает старым.

Симптом: `memory-service` падает или отвечает ошибками с
`graph with oid NNNNN does not exist`.

Исправление — в одной транзакции (порядок важен: внешний ключ не даст
обновить таблицы в другом порядке):

```sql
BEGIN;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- имя FK проверьте командой \d ag_catalog.ag_label
ALTER TABLE ag_catalog.ag_label DROP CONSTRAINT fk_graph_oid;

UPDATE ag_catalog.ag_label l
   SET graph = g.namespace::oid
  FROM ag_catalog.ag_graph g
 WHERE l.graph = g.graphid;

UPDATE ag_catalog.ag_graph SET graphid = namespace::oid;

ALTER TABLE ag_catalog.ag_label
  ADD CONSTRAINT fk_graph_oid FOREIGN KEY (graph) REFERENCES ag_catalog.ag_graph (graphid);
COMMIT;
```

```bash
tools/compose exec -T memory-db psql -U memory -d company_brain -v ON_ERROR_STOP=1 < fix-age-oids.sql
tools/compose restart memory-service
curl -fsS http://127.0.0.1:18001/healthz     # {"ok": true, "graph": ..., "nodes": N, "chunks": M}
```

Возвращённый FK сам проверит, что все метки ссылаются на существующий граф.

!!! tip "Физическая копия тома обходит проблему"
    Копия тома `memory_db`, снятая при **остановленном** `memory-db`
    (`tools/compose stop memory-db` и `tar` тома), сохраняет OID как есть и
    восстанавливается без правки каталога. Для переноса памяти на новый хост
    это самый надёжный путь; логический дамп оставьте для ежедневных копий.

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
6. Для памяти выполните исправление OID AGE (если восстанавливали логическим
   дампом) и проверьте `/healthz`.
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

- [Хранилище секретов](secret-store.md)
- [Обновление и миграции](upgrades.md)
- [Хранилище объектов (MinIO)](object-storage.md)
- [Аварийные процедуры](emergency.md)
- [Модель знаний памяти](../memory/knowledge-model.md)
- [Контекст задачи и память](../control-plane/context.md)
- [Память и контекст — диагностика](../troubleshooting/memory.md)
