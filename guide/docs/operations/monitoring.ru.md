# Мониторинг и здоровье

Как понять, что установка Taimen работает: health-эндпоинты сервисов,
метрики Control Plane, `make smoke`, логи и набор алертов, которые стоит
завести. Статья для дежурного инженера и того, кто настраивает наблюдаемость.

## Быстрая проверка

```bash
cd /opt/taimen/src
make smoke                                   # health всех поднятых сервисов
tools/compose --profile "*" ps              # статусы и healthcheck контейнеров
curl -s http://127.0.0.1:18000/health/ready  # Control Plane: БД + ревизия миграций
curl -s http://127.0.0.1:18000/metrics | grep -E '^(context_adapter|active_)'
```

Пример вывода `make smoke`:


```text
  iam-service          OK  200 http://127.0.0.1:18010/healthz
  control-plane-api    OK  200 http://127.0.0.1:18000/health/ready
  memory-service       OK  200 http://127.0.0.1:18001/healthz
  keycloak             OK  200 http://127.0.0.1:18081/auth/realms/platform
```

Скрипт `tools/smoke.py` берёт порты из `.env`, пропускает сервисы, которых
нет среди запущенных, и завершается с кодом `1`, если хоть один запущенный
сервис ответил статусом `≥ 400`. Его удобно ставить последним шагом выкладки
и в cron с алертом по коду возврата.

## Health-эндпоинты

| Сервис | Эндпоинт | Порт на хосте | Что проверяет |
|---|---|---|---|
| `iam-service` | `GET /healthz` | 18010 | Процесс жив (`{"status":"ok"}`); БД не проверяется |
| `control-plane-api` | `GET /health/live` | 18000 | Процесс жив (`{"status":"alive"}`) |
| `control-plane-api` | `GET /health/ready` | 18000 | БД доступна **и** ревизия Alembic равна head; иначе `503` с `reason` |
| `memory-service` | `GET /healthz` | 18001 | Подключение к БД, число узлов графа и чанков; `503`, если БД недоступна |
| `keycloak` | `GET /auth/health/ready` | только внутри контейнера (порт управления 9000) | Готовность Keycloak; снаружи smoke проверяет `/auth/realms/platform` на 18081 |
| `harness-launcher` | `GET /harness/_launcher/health` | только внутри контейнера | Healthcheck compose |
| Базы PostgreSQL | `pg_isready` | — | Healthcheck compose |

Ответы `/health/ready` Control Plane:

=== "Готов"

    ```json
    {"status": "ready", "revision": "<alembic revision>"}
    ```

=== "БД недоступна"

    ```json
    {"status": "unavailable", "reason": "database_unreachable"}
    ```

=== "Миграции отстали"

    ```json
    {"status": "unavailable", "reason": "migrations_pending",
     "dbRevision": "<в базе>", "headRevision": "<в образе>"}
    ```

!!! note "Healthcheck внутри контейнеров"
    Все healthcheck в `deploy/local/compose.yml` и Dockerfile обращаются к
    `127.0.0.1`, а не к `localhost`: в slim- и busybox-образах `localhost`
    может резолвиться в IPv6 `::1`, а сервис слушает только IPv4 —
    контейнер навсегда остаётся `unhealthy` при живом сервисе. Если пишете
    свой healthcheck, следуйте тому же правилу.

## Метрики Control Plane

`GET /metrics` отдаёт метрики в текстовом формате Prometheus. Эндпоинт **не
аутентифицирован** — снимайте его с `127.0.0.1:18000` или изнутри сети
compose (`control-plane-api:8000`) и не публикуйте наружу (см.
[Периметр и TLS](edge-and-tls.md)). Метки намеренно низкой кардинальности:
ни tenant, ни задача в метки не попадают.

### Счётчики и датчики

| Метрика | Тип | Смысл |
|---|---|---|
| `http_requests_total{method,status}` | counter | HTTP-запросы по методу и статусу |
| `active_harness_sessions` | gauge | Активные сессии harness (не истёкшие) |
| `active_claims` | gauge | Активные claims задач |
| `active_runs` | gauge | Runs в статусе `running` |
| `claim_takeovers_total` | counter | Перехваты claim после истечения аренды |
| `stale_fencing_rejections_total` | counter | Отказы записи со старым fencing token (зомби-harness после takeover) |
| `run_cancellations_total` | counter | Отменённые runs |
| `context_requests_total`, `context_request_duration_seconds_sum`/`_count` | counter | Сборка контекста для harness и её длительность |
| `context_degraded_total` | counter | Контекст отдан в деградированном виде (память недоступна) |
| `context_provider_failures_total` | counter | Отказы провайдера памяти на интерактивном пути |
| `context_adapter_delivered_total`, `_duplicates_total`, `_failures_total` | counter | Доставка журнала в память: доставлено, дубликаты, отказы |
| `context_adapter_parked_tenants` | gauge | Tenants, доставка которых встала (parked) |
| `context_adapter_lag` | gauge | Отставание доставки в событиях (ограничено 1000) |
| `context_adapter_lag_capped` | gauge | `1`, если отставание не меньше 1000 |
| `event_replay_requests_total`, `event_replay_events_total` | counter | Чтение журнала потребителями |
| `tool_invocation_denied_total` | counter | Отказы вызова инструментов (скиллов) |
| `authz_shadow_*`, `authz_policy_unavailable_total` | counter | Только при `CP_AUTHZ_MODE=shadow` или `policy`: сверки и расхождения с PDP |

Если база недоступна, эндпоинт не падает, а вместо датчиков выводит строку
`# DB gauges unavailable`.

### Сбор Prometheus

```yaml
scrape_configs:
  - job_name: taimen-control-plane
    metrics_path: /metrics
    static_configs:
      - targets: ["127.0.0.1:18000"]      # или control-plane-api:8000 изнутри сети compose
```

## Рекомендуемые алерты

| Условие | Порог | Что делать |
|---|---|---|
| `/health/ready` Control Plane не `200` | 2 мин | См. [Установка и запуск](../troubleshooting/startup.md): `database_unreachable` или `migrations_pending` |
| Любой контейнер `unhealthy` или в цикле рестартов | 5 мин | `tools/compose logs <сервис>` |
| `context_adapter_parked_tenants > 0` | сразу | Сценарий «доставка встала» ниже |
| `context_adapter_lag_capped == 1` или `context_adapter_lag` растёт | 15 мин | Проверить `memory-service`, провайдер эмбеддингов, логи `context-adapter` |
| Рост `context_provider_failures_total` / `context_degraded_total` | 10 мин | Память недоступна или медленна; координация при этом работает |
| Доля `http_requests_total{status=~"5.."}` | > 1 % за 10 мин | Логи `control-plane-api` по `request_id` |
| Всплеск `stale_fencing_rejections_total` | относительно нормы | Два процесса пишут от одного claim: проверить исполнителей |
| `active_runs > 0`, но `active_harness_sessions == 0` долго | 15 мин | Исполнители потеряли связь; проверить runner-хост |
| Диск хоста | > 80 % | Журнал, память, образы: `docker system df`, retention журнала |
| Срок сертификата | < 14 дней | Caddy перестал продлевать: логи `caddy`, DNS, порты |
| Срок ближайшего PAT | < 14 дней | Перевыпуск, см. [Секреты и ротация](secrets.md) |
| Возраст последнего бэкапа | > 26 ч | Проверить задание бэкапа |

## Логи

```bash
tools/compose logs -f --since 10m control-plane-api
tools/compose logs --since 1h context-adapter | grep -iE 'error|park'
make logs svc=iam-service                    # tools/compose --profile "*" logs -f iam-service
```

- Control Plane пишет структурированные логи; уровень — `LOG_LEVEL`
  (`CP_LOG_LEVEL`). Коррелируйте по `request_id` (один HTTP-запрос, также
  возвращается в теле ошибки как `requestId`) и `run_id` (сквозная трасса
  прогона, заголовок `X-Run-Id`; тот же `run_id` виден в логах памяти).

- Caddy пишет JSON в stderr (в образце промышленного Caddyfile); launcher
  рабочих мест — JSON-строки в stdout (см. [Рабочее место](../workplace/index.md)).

- Ошибки API Control Plane всегда имеют форму
  `{"error": {"code", "message", "details", "requestId"}}` — ищите в логах
  по `requestId` из ответа.

!!! warning "Ротация логов Docker"
    Сервисы `deploy/local/compose.yml` используют драйвер логов по умолчанию,
    без ограничения размера. Настройте ротацию для демона Docker
    (`/etc/docker/daemon.json`):

    ```json
    {"log-driver": "json-file", "log-opts": {"max-size": "20m", "max-file": "5"}}
    ```

    Изменение применяется к вновь создаваемым контейнерам.

## Эксплуатационные операции Control Plane

Операции требуют права `operations.manage` и выполняются через API или CLI
`control-plane` (пакет из суперпроекта, credential оператора).

### Доставка в память встала (parked)

Симптом: `context_adapter_parked_tenants > 0`, в ответе контекста
`freshness.memoryIngest.status = "parked"`.

```bash
control-plane ops adapter status
# {"parked": true, "parkedReason": "...", "parkedEventId": "...", "cursor": "..."}
```

1. Прочитайте `parkedReason` — это ответ провайдера памяти. Типичное:
   `401/403` из-за сменившегося ключа или service account, отвергнутая схема
   наблюдения.
2. Устраните причину (ключ, env-файл service account, доступность памяти).
3. Повторите ту же позицию:

    ```bash
    control-plane ops adapter redrive <tenant-id> --reason "memory credential rotated"
    ```

Redrive не двигает курсор и идемпотентен. API, способного «перепрыгнуть»
событие, нет намеренно. Пока один tenant запаркован, остальные доставляются
как обычно; claims, runs и approvals от памяти не зависят вовсе.

### Перестроение памяти

```bash
curl -s -X POST http://127.0.0.1:18000/api/v1/operations/context-adapter/<tenant-id>:rebuild \
  -H "Authorization: Bearer <admin access token>" -H 'Content-Type: application/json' \
  -d '{"reason": "memory restored from an older backup"}'
```

Без `cursor` tenant переигрывается с начала журнала; с `cursor` — только
назад (вперёд — `422 cursor_must_not_advance`).

### Рост журнала

```bash
# перенести подтверждённую историю старше 30 дней в архив той же базы
curl -s -X POST http://127.0.0.1:18000/api/v1/operations/journal:archive \
  -H "Authorization: Bearer <admin access token>" -H 'Content-Type: application/json' \
  -d '{"beforeSeconds": 2592000, "maxEvents": 50000}'
```

`archived: 0` при живом отставании потребителей — работающая защита, а не
ошибка. Физическое удаление `:prune` — только после бэкапа. Подробно — в
[Резервном копировании](backup.md).

## Наблюдаемость исполнителей

- Логи демона: `docker compose -f <compose-файл исполнителя> logs -f runner`
  (контейнер) или файл журнала юнита (systemd).
- Трасса каждого прогона видна через MCP и API: артефакт `transcript`
  и run actions `tool.<имя>` — см. [Трасса прогонов](../runner/trace.md).
- Признак проблемы публикации: run успешен, а в артефакте `commit` поле
  `published: false`.

## См. также

- [Периметр и TLS](edge-and-tls.md)
- [Резервное копирование](backup.md)
- [Аварийные процедуры](emergency.md)
- [События Control Plane](../control-plane/events.md)
- [Диагностика](../troubleshooting/index.md)
