# Аварийные процедуры

Runbook для инцидентов: что продолжает работать при отказе отдельного
компонента, как откатить релиз, что делать при потере runner-хоста и при
компрометации credentials. Статья для дежурного инженера; каждая процедура
начинается с оценки, затем идут шаги и проверка.

## Карта зависимостей

Что перестаёт работать при отказе компонента:

| Отказал | Что продолжает работать | Что встаёт |
|---|---|---|
| `iam-service` или `iam-db` | Уже выданные access token до истечения (до 300 с); проверка подписи по кэшу JWKS; статический ключ памяти | Обмен PAT и client credentials; через ~5 минут — все harness, исполнители, вход людей через федерацию; доставка в память через service account ядра |
| `control-plane-api` / `control-plane-db` | Память и IAM сами по себе | Вся координация: задачи, claims, runs, approvals; доставка в память |
| `memory-service` / `memory-db` | Координация полностью: claims, runs, approvals, завершение задач | Сборка контекста (отдаётся деградированным), доставка журнала копит отставание или паркуется |
| `keycloak` / `keycloak-db` | Harness, MCP-плагин и исполнители (ходят по PAT мимо Keycloak) | Новый вход людей в рабочие места |
| `caddy` | Всё внутри хоста; доступ через SSH-туннель к `127.0.0.1` | Любой доступ снаружи |
| Runner-хост | Платформа целиком | Автономное исполнение задач, назначенных этому исполнителю |

## Отказ IAM

**Оценка.**

```bash
tools/compose ps iam-service iam-db
curl -s http://127.0.0.1:18010/healthz
tools/compose logs --since 15m iam-service | tail -50
```

**Что происходит.** Control Plane проверяет подпись access token по JWKS из
кэша (устаревший кэш допустим до `CP_IAM_JWKS_STALE_AFTER_SECONDS`, по
умолчанию 3600 с), поэтому токены, выданные до отказа, работают до своего
истечения. Новые токены не выдаются: harness и исполнители теряют доступ в
пределах срока жизни access token (300 с). Launcher рабочих мест не может
впустить человека (`federation:exchange` недоступен). `context-adapter`, работающий через
service account, получает отказы и копит отставание.

**Шаги.**

1. Если лежит база: `tools/compose up -d iam-db`, проверить диск и логи
   PostgreSQL.
2. Если сервис падает при старте — смотреть первую ошибку в логах:
    - ошибка миграции Alembic → откат релиза (ниже);
    - `PermissionError` на ключе подписи → владелец `secrets/iam-signing.pem`
      должен быть uid 10001 (`chown 10001:10001`, режим `600`);
    - ошибка подключения к БД → пароль `IAM_POSTGRES_PASSWORD` в `.env`
      не совпадает с ролью в базе.
3. `tools/compose up -d iam-service`, дождаться `healthy`.
4. Проверить `context_adapter_parked_tenants`; при `> 0` —
   `control-plane ops adapter redrive <tenant-id>`.

### Аварийный вход, пока IAM не поднят

Если восстановление IAM затягивается, а в Control Plane нужно войти (снять
claim, отменить задачу, отозвать binding), владелец хоста выпускает
**аварийный ключ** — короткоживущий admin-ключ Control Plane для человека
(CP-ADR-0065). API для этого нет: команда выполняется в контейнере
`control-plane-api`, границей доверия служит shell на хосте.

```bash
# principal оператора — cpOperatorPrincipalId в deploy/state/<env>.json
PRINCIPAL=$(python3 -c 'import json;print(json.load(open("deploy/state/taimen.json"))["cpOperatorPrincipalId"])')
tools/compose exec -e BREAK_GLASS_OPERATOR="$(whoami)" control-plane-api \
  python -m control_plane.break_glass issue --principal "$PRINCIPAL" --ttl 3600 \
  --reason "IAM недоступен, <номер инцидента>"
```

Ключ `cp_bg…` печатается один раз. Им работают как обычным Bearer-токеном
(`Authorization: Bearer cp_bg…`), в том числе при
`CP_LEGACY_API_KEYS_ENABLED=false`: обычные legacy-ключи при этом
по-прежнему не принимаются.

| Ограничение | Значение |
|---|---|
| Кому | только активному principal вида `human` |
| Права | `admin` |
| Срок жизни | `--ttl` от 60 с до `CP_BREAK_GLASS_MAX_TTL_SECONDS` (4 ч); по умолчанию 1 ч |
| Аудит | событие `api_key.break_glass_issued`: principal, префикс, срок, причина, кто выпустил |
| Выключатель | `CP_BREAK_GLASS_ENABLED=false` — нет ни выпуска, ни приёма выпущенных |

Как только IAM поднят — отзовите все аварийные ключи:

```bash
tools/compose exec control-plane-api python -m control_plane.break_glass revoke
```

## Control Plane не готов

**Оценка:** `curl -s http://127.0.0.1:18000/health/ready`.

| Ответ | Причина | Действие |
|---|---|---|
| `503 database_unreachable` | База недоступна | `tools/compose ps control-plane-db`, логи, диск; `tools/compose up -d control-plane-db` |
| `503 migrations_pending` | Ревизия БД не равна head образа | Если API не стартует из-за ошибки миграции — логи `control-plane-api`, откат релиза; если ревизия БД **новее** образа — запущен старый образ поверх новой схемы: вернуть новый образ или сделать downgrade |
| Нет ответа | Контейнер в цикле рестартов | `tools/compose logs --tail 100 control-plane-api` |

Пока API не готов, `control-plane-worker` и `context-adapter` не стартуют
(зависимость `service_healthy`) — это защита, а не отдельная проблема.

## Откат релиза

Короткая версия; полная — в [Обновлении и миграциях](upgrades.md).

```bash
cd /opt/taimen/src
# 1. Если новый релиз применил миграции — downgrade НОВЫМ образом
tools/compose stop control-plane-worker context-adapter control-plane-api
tools/compose run --rm --no-deps control-plane-api alembic downgrade <ревизия прошлого релиза>
# 2. Код и образы прошлого релиза
git checkout <коммит прошлого релиза> && git submodule update --init --recursive
tools/compose --profile core --profile edge build     # или прежний IMAGE_TAG без сборки
tools/compose --profile core --profile edge up -d
make smoke
```

Если downgrade невозможен — восстановление базы из бэкапа, снятого перед
релизом (см. [Резервное копирование](backup.md)).

## Потеря runner-хоста

**Оценка.** Машина недоступна или скомпрометирована. На ней лежали: PAT
исполнителя, токен подписки кодового агента, токен forge, рабочие копии с
неопубликованными изменениями.

**Что происходит с задачами.** Claims исполнителя истекают по аренде
(`CP_CLAIM_TTL_SECONDS`, по умолчанию 300 с), после чего задачу может взять
другой исполнитель (takeover). Незавершённый run остаётся в статусе
`running`; когда исполнитель с тем же principal стартует снова, он находит
свой осиротевший run через `/api/v1/harness/context` и закрывает его с
`failure_reason=restart_recovery`, возвращая задачу в очередь.

**Шаги.**

1. **Если потеря неконтролируемая** (кража, взлом, доступ посторонних) —
   считать все секреты хоста скомпрометированными:
    - отозвать binding исполнителя в Control Plane (немедленно закрывает вход):
      `POST /api/v1/iam-bindings/<binding-id>:revoke`;
    - отозвать PAT исполнителя в IAM (`…/platform-access-tokens/<id>:revoke`);
    - отозвать токен подписки у поставщика и токен forge в forge.
2. Поднять новую машину исполнителя тем же способом, что и прежнюю.
3. Выпустить исполнителю новый PAT (см. [Секреты и ротация](secrets.md));
   если binding отзывался — создать заново
   `POST /api/v1/principals/<principal-id>/iam-bindings` с прежними правами.
4. Запустить исполнителя. Проверить в логах, что осиротевшие runs закрыты
   `restart_recovery`, а задачи вернулись в очередь.
5. Неопубликованная работа утеряна; опубликованные ветки `task/<id>` лежат в
   forge и доступны для ревью.

**Экстренно остановить исполнителя, не разбираясь:**

=== "Контейнер"

    ```bash
    docker compose -f <compose-файл исполнителя> stop
    ```

=== "systemd"

    ```bash
    systemctl stop <юнит> && systemctl disable <юнит>
    ```

Остановка безопасна в любой момент: run будет закрыт `restart_recovery`
при следующем старте, рабочая копия сохранится.

## Компрометация credentials

### PAT человека или агента

| Шаг | Команда | Эффект |
|---|---|---|
| 1. Закрыть вход в Control Plane | `POST /api/v1/iam-bindings/<binding-id>:revoke` | Сразу: кэш binding сбрасывается в процессе API |
| 2. Отозвать PAT | `POST …/tenants/<t>/platform-access-tokens/<id>:revoke?reason=leaked` (bootstrap) или `POST /api/v1/platform-access-tokens:revoke-self` (владелец) | Новые обмены невозможны |
| 3. Разобрать последствия | Audit IAM (`platform_access_tokens.exchange` по префиксу PAT), журнал событий Control Plane по principal | Понять, что сделано чужим токеном |
| 4. Вернуть доступ | Новый PAT, повторный `POST /api/v1/principals/<id>/iam-bindings` | Владелец работает дальше |

Уже выданные этим PAT access token живут до 300 с; шаг 1 закрывает их в
Control Plane раньше. Если PAT имел `control-plane:admin`, проверьте в
журнале созданные principals, bindings и изменения каталога за период утечки.

### Bootstrap-токен IAM

`IAM_BOOTSTRAP_TOKEN` позволяет выпустить PAT любому principal — это
инцидент наивысшей важности.


1. Сменить значение в `.env` на новое случайное (`openssl rand -hex 24`),
   `tools/compose up -d iam-service`.
2. Выгрузить список PAT (`GET …/platform-access-tokens?includeRevoked=true`)
   и audit IAM; отозвать всё, что выпущено не вами после вероятного момента
   утечки.
3. Проверить service accounts, созданные за тот же период, и отозвать
   лишние (`…/service-accounts/<client-id>:revoke`).

### Ключ подписи IAM

Позволяет подделать access token любого principal. Немедленная ротация
ключа и перезапуск сервисов, проверяющих токены, — см.
[Секреты и ротация](secrets.md).

### Секрет service account

```bash
# ядро: bootstrap перевыпустит и отзовёт прежний
mv secrets/control-plane-iam.env /tmp/ && python3 deploy/bootstrap.py --env .env --name <env>
tools/compose up -d control-plane-api control-plane-worker context-adapter
```

Для прочих service accounts — отзыв в IAM и перевыпуск; см.
[Секреты и ротация](secrets.md).

### `MEMORY_API_KEY`, ключ LLM-провайдера, пароли БД

Сменить значение (для паролей БД — сначала `ALTER ROLE` в базе), обновить
`.env`, пересоздать потребителей. Процедуры — в
[Секретах и ротации](secrets.md).

## Периметр недоступен или истёк сертификат

Всё внутри хоста продолжает работать. Для эксплуатационных операций
используйте порты на `127.0.0.1` через SSH-туннель:

```bash
ssh -N -L 18000:127.0.0.1:18000 -L 18010:127.0.0.1:18010 <хост платформы>
curl -s http://127.0.0.1:18000/health/ready
```

!!! tip "Туннели в ssh-алиасе"
    Если в `~/.ssh/config` для хоста прописаны `LocalForward`, а порты уже
    заняты другой сессией, ssh падает целиком (`bind … Address already in
    use`) — вместе с командой, ради которой вы подключались. Подключайтесь
    с `ssh -o ClearAllForwardings=yes <алиас>`; для git поверх такого алиаса —
    `GIT_SSH_COMMAND='ssh -o ClearAllForwardings=yes'`.

Причины и исправление сертификатов — в [Периметре и TLS](edge-and-tls.md).

## Закончился диск

PostgreSQL перестаёт принимать запись, сервисы отвечают `5xx`.

```bash
df -h /var/lib/docker
docker system df
docker builder prune -f            # кэш сборки
docker image prune -f              # висячие образы
journalctl --vacuum-size=500M
```

Затем найдите растущий объект (см. [Ресурсы и масштабирование](capacity.md))
и заведите алерт на заполнение диска. Не удаляйте файлы внутри томов баз
данных вручную.

## Смена публичного адреса (issuer)

Не авария, но процедура с риском закрыть вход всем: issuer IAM равен
`${TAIMEN_PUBLIC_URL}/iam`, а Control Plane ищет binding по паре
`(issuer, iam_principal_id)`.


1. **До переключения**, пока старый адрес работает, создайте для каждого
   principal binding с новым issuer — тем же вызовом
   `POST /api/v1/principals/<principal-id>/iam-bindings`, указав
   `"issuer": "https://new.example.com/iam"` и прежние права. Старые bindings
   остаются и не мешают.
2. Настройте DNS и Caddyfile для нового имени, дождитесь сертификата.
3. Поменяйте `TAIMEN_PUBLIC_URL` и `TAIMEN_PUBLIC_HOST` в `.env`.
4. Пересоздайте сервисы, чтобы они взяли новый адрес: `tools/compose … up -d`.
5. Если поднят профиль `idp`: обновите redirect URI клиентов консоли и
   ассистента в Keycloak (для консоли —
   `deploy/keycloak/keycloak-runtime-console-client.py` с новым `WEB_BASE_URL`,
   для остальных — Admin API или админ-консоль Keycloak; шаблон realm на
   существующий realm не применяется). Issuer Keycloak тоже меняется: identity
   provider в IAM и external identities людей записаны со старым issuer, а
   изменить провайдера через API нельзя (см. [Федерация identity](../iam/federation.md)).
6. Обновите `CONTROL_PLANE_SERVER` и `CONTROL_PLANE_IAM_URL` у исполнителей
   и операторов. Ключ записи в `credentials.json` включает адрес IAM —
   перенесите записи под новый адрес.
7. После проверки отзовите bindings со старым issuer.

Если шаг 1 пропущен и вход уже закрыт, bindings переносятся SQL в базе
Control Plane:

```sql
UPDATE iam_principal_bindings
   SET issuer = 'https://new.example.com/iam', updated_at = now()
 WHERE issuer = 'https://old.example.com/iam';
```

После правки базы мимо API Control Plane может ещё до
`CP_IAM_BINDING_STALE_AFTER_SECONDS` (по умолчанию 120 с) отвечать по
закэшированному отказу; чтобы не ждать, перезапустите `control-plane-api`.

## После инцидента

- Запишите хронологию, затронутые компоненты и принятые меры.
- Проверьте `make smoke`, `/health/ready`, `context_adapter_parked_tenants`.
- Если отзывались credentials — убедитесь, что все легитимные клиенты
  получили новые и работают.
- Добавьте алерт, который поймал бы инцидент раньше (см.
  [Мониторинг и здоровье](monitoring.md)).

## См. также

- [Секреты и ротация](secrets.md)
- [Резервное копирование](backup.md)
- [Обновление и миграции](upgrades.md)
- [Исполнение и claims](../control-plane/execution.md)
- [Диагностика](../troubleshooting/index.md)
