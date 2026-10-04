# Узлы и fleet

Сервис `fleet` решает, **где** работают агенты, описанные видом `Agent`: знает машины
(узлы), раскладывает на них экземпляры агентов, заводит агентам личности и доставляет им
PAT, сообщает фактическое состояние в Control Plane. Статья для инженера эксплуатации,
который подключает машины к платформе, и для администратора, который разбирается, почему
агент не запустился. Что писать в описании агента — в статье [Агенты
описанием](declarative-agents.md). Обоснование — TAI-ADR-0052.

## Архитектура

Сервис состоит из двух процессов:

- **fleet-controller** — работает рядом с Control Plane (профиль compose `fleet`). Хранит
  узлы и размещения в SQLite, читает активных агентов из Control Plane, размещает
  экземпляры по узлам, заводит агентам principal и PAT в IAM, пишет фактическое состояние
  агентов в Control Plane.
- **fleet-node** — агент узла на каждой машине, которая исполняет агентов: сервер,
  отдельная VM, машина разработчика. Регистрируется одноразовым ключом, тянет своё
  желаемое состояние, отчитывается о здоровье и запускает контейнеры агентов через
  Docker socket proxy.

```mermaid
flowchart LR
    subgraph Center["Центр (compose платформы)"]
        CADDY["caddy<br/>/fleet/*"]
        FC["fleet-controller:8040<br/>SQLite /data"]
        CP["control-plane-api"]
        IAM["iam-service"]
        CADDY --> FC
        FC -- "agents.read, agents.status.write" --> CP
        FC -- "iam:agents" --> IAM
    end
    subgraph Node["Узел (любая машина с Docker)"]
        FN["fleet-node"]
        PX["docker-socket-proxy<br/>только контейнеры"]
        A1["fleet-&lt;agent&gt;-0<br/>демон исполнителя"]
        A2["fleet-&lt;agent&gt;-1"]
        FN --> PX --> A1 & A2
    end
    FN -- "HTTPS, только исходящие:<br/>join, long-poll desired, observed" --> CADDY
    A1 -- "GET /agents/me, работа" --> CP
```

Свойства, на которые можно опираться:

- **Соединения только исходящие.** Узел сам ходит к контроллеру; контроллер никогда не
  вызывает узел и не держит ключей к машинам. Узел за NAT работает.
- **Команд с центра нет.** Узел получает только желаемое состояние и сам приводит к нему
  свои контейнеры.
- **Без центра узел продолжает работать.** Последнее полученное желаемое состояние
  хранится на диске узла; при недоступном контроллере агенты работают, ждут только
  изменения.
- **Значения секретов не покидают машину.** Узел сообщает только имена своих секретов.
- **Что запускать, решает узел.** Описание агента называет вид исполнителя
  (`claude-code`, `codex`, `skills`, `observer`), а образ вида по умолчанию задаёт
  конфигурация узла. Описание может назвать свой образ (`executor.image`), но узел
  запустит его, только если образ допускает список `executors.<вид>.images` самого
  узла (см. [Образы, которые может назвать агент](#images)). Никакой другой образ —
  кто бы его ни назвал — узел не запускает.

## Цикл сверки

Контроллер выполняет одну процедуру сверки каждые 5 секунд, после регистрации узла и
после каждого отчёта узла:

1. читает активных агентов из Control Plane (`GET /api/v1/agents?status=active`). Если
   ядро недоступно, работает с последним известным списком;
2. помечает `offline` узлы, которые не отчитывались дольше **60 секунд**;
3. размещает экземпляры агентов (ниже);
4. для каждого размещения обеспечивает личность агента и PAT, запечатанный ключом узла;
5. пересобирает желаемое состояние каждого узла. Номер поколения (`generation`) растёт
   только при изменении, и это будит long-poll узла;
6. отзывает PAT, которые больше не нужны;
7. сообщает фактическое состояние агентов в ядро (`PUT /api/v1/agents/{key}/status`) —
   только если отчёт изменился.

Всё сделано по уровню, а не по событию: пропущенное событие ничего не ломает, следующая
сверка приведёт систему к описанию.

## Размещение и метки

Узел подходит экземпляру агента, если одновременно:

| Условие | Откуда у узла | Откуда у агента |
|---|---|---|
| узел `online` | отчёт не старше 60 с | — |
| узел запускает вид исполнителя | ключи `executors` в `node.yaml` | `executor.kind` |
| узел допускает образ агента, если агент его назвал | `executors.<вид>.images` в `node.yaml` | `executor.image` |
| у узла есть все метки | `labels` в `node.yaml` | `placement.requires` |
| на узле есть все секреты | файлы в `secretsDir` | `placement.secrets` |
| есть место | `capacity.slots` и, если заданы с обеих сторон, `capacity.cpus` и `capacity.memoryMb` | один слот на экземпляр, `placement.resources` |

Сравнение меток: требование `имя` выполняет метка `имя` и любая `имя=значение`;
требование `имя=значение` — только точно такая метка.

Правила выбора:

- **Размещение липкое.** Экземпляр, чей узел по-прежнему подходит, остаётся на нём:
  агенты не перескакивают между узлами.
- **Новый экземпляр** идёт на подходящий узел с наибольшим числом свободных слотов; при
  равенстве — по имени узла.
- **Узел ушёл в `offline`** — его экземпляры переезжают на другой подходящий узел. Если
  такого нет, экземпляр остаётся за старым узлом (вернётся вместе с ним), а агент
  получает фазу `node_unavailable`.
- **Подходящего узла нет вовсе** — агент в `waiting_for_node` с первой причиной, которая
  исключает все узлы, в таком порядке: `no_node` (нет ни одного узла `online`),
  `no_executor_kind`, `image_not_allowed`, `no_label`, `no_secret`, `no_capacity`.
  Ожидающий агент слота не занимает.
- Размещаются только агенты с `state: running`, `identity.kind: agent` и без
  `placement: none`; число экземпляров — `placement.replicas`.

Посмотреть, куда что размещено:

```bash
curl -sS https://platform.example.com/fleet/api/v1/placements \
  -H "Authorization: Bearer $FLEET_TOKEN"
```

```json
{
  "items": [
    {"agentKey": "coder", "revision": 4, "nodeId": "<node-id>", "replicas": 1,
     "status": "placed", "reason": null},
    {"agentKey": "publisher", "revision": 2, "nodeId": null, "replicas": 1,
     "status": "pending", "reason": "no_secret"}
  ]
}
```

## Регистрация узла

```mermaid
sequenceDiagram
    autonumber
    participant Adm as Администратор
    participant FC as fleet-controller
    participant FN as fleet-node
    Adm->>FC: join-key (CLI в контейнере или POST /api/v1/join-keys)
    FC-->>Adm: одноразовый ключ, срок действия
    Adm->>FN: ключ → файл joinKeyFile
    FN->>FN: X25519 key pair (закрытый ключ остаётся на узле)
    FN->>FC: POST /api/v1/nodes:join {ключ, name, publicKey, labels, executorKinds, capacity, secrets}
    FC-->>FN: nodeId, nodeToken (один раз; контроллер хранит только хэш)
    loop
        FN->>FC: GET /api/v1/nodes/me/desired?since=&wait=60
        FN->>FC: PUT /api/v1/nodes/me/observed (каждые observeSeconds)
    end
```

### 1. Выпустить ключ регистрации

Проще всего — командой внутри контейнера контроллера: она пишет ключ прямо в его базу и
не требует токена.

```bash
tools/compose --profile fleet exec fleet-controller \
  fleet-controller join-key --ttl 3600 --note "worker-1"
```

Или через API с токеном IAM audience `fleet` и scope `fleet:admin`:

```bash
curl -sS -X POST https://platform.example.com/fleet/api/v1/join-keys \
  -H "Authorization: Bearer $FLEET_TOKEN" -H 'Content-Type: application/json' \
  -d '{"ttlSeconds": 3600, "note": "worker-1"}'
```

```json
{"joinKey": "<ключ>", "expiresAt": "2026-01-15T11:00:00Z"}
```

`ttlSeconds` — от 60 секунд до 7 суток, по умолчанию 3600. Ключ одноразовый: контроллер
хранит его хэш и помечает использованным при регистрации.

### 2. Положить ключ на узел и запустить его

Ключ записывается в файл `joinKeyFile` из `node.yaml`, затем запускается
`fleet-node --config node.yaml`. Узел регистрируется один раз: токен узла, его id и пара
ключей сохраняются в `stateDir`, и при следующих запусках ключ регистрации не нужен.

| Ответ регистрации | Причина |
|---|---|
| `201` | узел зарегистрирован |
| `401 join_key_invalid` | ключ неизвестен, уже использован или истёк |
| `409 node_name_taken` | узел с таким `name` уже зарегистрирован |
| `503 not_configured` | у контроллера ещё нет service account (см. [Контроллер](#controller)) |

## Конфигурация узла `node.yaml` { #node-yaml }

```yaml
controllerUrl: https://platform.example.com/fleet
name: worker-1
labels: [claude-subscription, repos]
capacity: {slots: 4, cpus: 8, memoryMb: 16384}
executors:                            # вид исполнителя -> образ по умолчанию и допустимые образы
  claude-code:
    image: agent-runner:1.4.0
    dataPath: /runner
    env:
      CP_TEST_DATABASE_URL: postgresql+psycopg://test:test@db-test:5432/test
  skills:
    image: agent-runner:1.4.0
    dataPath: /runner
    env: {RUNNER_MODE: skills}
  observer:
    image: observer-base:1.0.0
    dataPath: /data
    images:                           # что ещё может назвать описание агента этого вида
      - registry.example.com/observers/mail:1.*
      - registry.example.com/observers/tickets:2.0.3
stateDir: /var/lib/fleet-node
secretsDir: /etc/fleet-node/secrets
dockerUrl: tcp://docker-proxy:2375
network: fleet-agents
agentEnv:                             # каждому контейнеру агента; без секретов
  CONTROL_PLANE_SERVER: https://platform.example.com
  CONTROL_PLANE_IAM_URL: https://platform.example.com/iam
  CONTROL_PLANE_IAM_SCOPES: control-plane:read control-plane:write
joinKeyFile: /etc/fleet-node/join-key
observeSeconds: 20
```

| Поле | По умолчанию | Значение |
|---|---|---|
| `controllerUrl` | — (обязательно) | адрес контроллера; за периметром платформы — `https://<хост>/fleet` |
| `name` | — (обязательно) | имя узла `^[a-z0-9][a-z0-9.-]*$`, до 100 символов; уникально в fleet. Попадает в поле `node` фактического состояния агента |
| `labels` | `[]` | метки: `имя` или `имя=значение` (`^[a-z0-9][a-z0-9.-]*(=[a-zA-Z0-9._-]+)?$`) |
| `capacity.slots` | — (обязательно) | сколько экземпляров агентов узел держит, 0–100 |
| `capacity.cpus` | — | CPU для агентов; учитывается, если у агента задан `resources.cpus` |
| `capacity.memoryMb` | — | память для агентов, от 64; учитывается, если у агента задан `resources.memoryMb` |
| `executors` | — (обязательно) | вид исполнителя → `{image, images, env, dataPath}`. Ключи — виды, которые узел объявляет контроллеру |
| `executors.<вид>.image` | — (обязательно) | образ вида по умолчанию — для агентов без `executor.image`; должен уже быть на машине (см. [Типичные проблемы](#troubleshooting)) |
| `executors.<вид>.images` | `[]` | до 50 образов, которые может назвать описание агента этого вида: точные ссылки и шаблоны с одной `*` в теге (см. [ниже](#images)). Пусто — только образ по умолчанию |
| `executors.<вид>.env` | `{}` | дополнительное окружение контейнеров этого вида, без секретов |
| `executors.<вид>.dataPath` | — | путь внутри контейнера, куда монтируется именованный volume реплики (рабочие копии, зеркала); `env` и `dataPath` вида действуют и для образа, названного агентом |
| `stateDir` | — (обязательно) | состояние узла: токен, ключи, последнее желаемое состояние, PAT агентов (каталог `0700`, файлы `0600`) |
| `hostStateDir` | = `stateDir` | тот же каталог, как его видит Docker-демон; нужен, когда узел сам работает в контейнере |
| `secretsDir` | — (обязательно) | каталог секретов: по файлу на секрет |
| `hostSecretsDir` | = `secretsDir` | тот же каталог глазами Docker-демона |
| `dockerUrl` | `unix:///var/run/docker.sock` | Docker Engine API; `unix://…` или `tcp://…` (socket proxy) |
| `network` | — | Docker-сеть контейнеров агентов |
| `agentEnv` | `{}` | окружение каждого контейнера агента: адреса Control Plane и IAM, scopes |
| `joinKeyFile` | — | файл одноразового ключа регистрации; после регистрации не нужен |
| `observeSeconds` | `20` | период отчёта и локальной сверки, 5–300 |

- `${ИМЯ}` в файле подставляется из окружения процесса узла; незаданная переменная —
  ошибка старта с перечнем имён. Строки-комментарии (`# …`) не проверяются и не
  подставляются.
- Неизвестное поле — ошибка старта: конфигурация проверяется строго.
- Конфигурация читается при старте. После правки меток, ёмкости или `executors`
  перезапустите `fleet-node`; новые значения уйдут контроллеру со следующим отчётом.

!!! warning "Узел в контейнере: пути хоста"
    PAT агента и секреты монтируются в контейнеры агентов bind-mount'ом **по пути хоста**.
    Если `fleet-node` сам работает в контейнере, задайте `hostStateDir` и
    `hostSecretsDir` так, как эти каталоги видит Docker-демон, или смонтируйте их в
    контейнер узла по тем же путям, что на хосте.

### Образы, которые может назвать агент { #images }

Описание агента может назвать образ своего исполнителя — `executor.image`, ссылку с
тегом или дайджестом (см. [Агенты описанием](declarative-agents.md#executor)). Так
пакет интеграции приносит образ со своим кодом. Назвать образ — не право его
запустить: узел запускает его, только если список `images` этого вида в его
`node.yaml` образ допускает. Что исполняется на машине, решает администратор узла.

| Запись списка | Допускает |
|---|---|
| `registry.example.com/observers/mail:1.4.2` | только эту ссылку |
| `registry.example.com/observers/mail:1.*` | любой тег этого репозитория, начинающийся с `1.` |
| `registry.example.com/observers/mail:*` | любой тег этого репозитория |
| `registry.example.com/observers/mail@sha256:<hex>` | только этот дайджест |

- В записи не больше одной `*`, и только в теге. Она заменяет любую
  последовательность символов тега и никогда не допускает другой репозиторий или
  реестр. Ссылку с дайджестом допускает только точная запись.
- Ссылки сравниваются как написаны, без умолчаний Docker: `alpine:3.20` и
  `docker.io/library/alpine:3.20` — разные записи.
- Образ вида по умолчанию (`image`) сам в список не входит: если агентам можно
  называть и его, перечислите его в `images`.
- Узел сообщает списки контроллеру (`executorImages`) вместе с метками и именами
  секретов. Контроллер размещает агента с `executor.image` только на узле, чей
  список образ допускает; иначе агент ждёт с причиной `image_not_allowed`.
- Узел проверяет и то, что ему прислали. Недопущенный образ — например, список
  сократили, а контроллер ещё не узнал, — не запускается: работающий контейнер с ним
  останавливается с дренажом, а экземпляр в отчёте — `stopped` с сообщением,
  начинающимся с `image_not_allowed`. Отказ ничего не стоит машине, сколько бы раз
  желаемое состояние его ни повторило: ни контейнера, ни счётчика перезапусков, ни
  паузы.
- Узел образы не скачивает: каждый образ, который он может запустить, должен уже
  лежать на машине (его собирает или загружает compose узла).
- Без `executor.image` агент работает на образе вида по умолчанию.

!!! warning "Порядок обновления"
    Сначала обновляется контроллер, потом узлы со списками образов: контроллер
    без поддержки списков образов не знает `executorImages` и отвергает отчёт такого узла. Узел
    без списков ничего нового не отправляет, а агента с `executor.image` контроллер
    на узел без поддержки списков не размещает.

### Секреты узла { #node-secrets }

`secretsDir` — каталог, где каждый секрет лежит отдельным файлом, имя файла — имя секрета
из `placement.secrets` описаний агентов:

```text
/etc/fleet-node/secrets/          0700
├── claude-oauth-token            0600  токен подписки кодового агента
└── github-token                  0600  токен forge для публикации веток
```

- Узел сообщает контроллеру только **имена** файлов, подходящих под
  `^[a-z0-9][a-z0-9-]{0,62}$`; остальные файлы (`README`, `agent.pat`) не предлагаются.
- Список перечитывается при каждом отчёте: добавленный файл станет виден контроллеру
  через `observeSeconds`, перезапуск узла не нужен.
- В контейнер агента попадают только секреты, которые названы в его описании, — по
  одному файлу, только для чтения, в `/run/secrets/<имя>`.
- Файлы должны читаться пользователем, под которым работает образ исполнителя
  (у референсного образа — uid `10001`).


### Что получает контейнер агента { #agent-container }

| Где | Что |
|---|---|
| `/run/secrets/agent-pat` | PAT агента, открытый из запечатанной формы; только чтение |
| `/run/secrets/<имя>` | каждый секрет из `placement.secrets`; только чтение |
| `CONTROL_PLANE_AGENT_KEY` | ключ агента |
| `IAM_PRINCIPAL`, `CONTROL_PLANE_IAM_TENANT` | чья это личность в IAM |
| `FLEET_REPLICA` | номер экземпляра |
| `agentEnv`, `executors.<вид>.env` | окружение из `node.yaml` |
| `<dataPath>` | именованный volume `fleet-<agent>-<replica>-data`, чтение и запись; переживает перезапуски и новые ревизии |

Контейнер называется `fleet-<agent>-<replica>`, помечен `fleet.managed=1` (узел не
трогает контейнеры без этой метки), запускается с `init` и без политики перезапуска
Docker — перезапускает узел. Лимиты `resources.cpus` и `resources.memoryMb` описания
становятся лимитами контейнера.

Референсный образ исполнителя (`deploy/agent-runner/`) по `CONTROL_PLANE_AGENT_KEY`
понимает, что запущен узлом: берёт PAT из `/run/secrets/agent-pat` в окружение процесса
(`IAM_CREDENTIAL_MODE=environment`), токен подписки и токен forge — из
`/run/secrets/claude-oauth-token` и `/run/secrets/github-token`, если они смонтированы, и
запускает демон. Всю остальную конфигурацию демон берёт из ревизии агента (`GET
/agents/me`), зеркала репозиториев заводит сам на volume реплики.

## Личность агента и доставка PAT { #identity-and-pat }

```mermaid
sequenceDiagram
    autonumber
    participant FC as fleet-controller
    participant IAM as IAM
    participant CP as Control Plane
    participant FN as fleet-node
    FC->>IAM: POST /tenants/{t}/agents (principal вида agent, владелец — контроллер)
    FC->>CP: PUT /agents/{key}/identity {issuer, iamTenantId, iamPrincipalId}
    CP-->>CP: principal CP + связка с permissions ревизии
    FC->>IAM: POST /tenants/{t}/agents/{id}/platform-access-tokens (Idempotency-Key)
    FC->>FC: seal(PAT, публичный ключ узла) — открытый PAT не хранится
    FC-->>FN: desired: identity.credential {credentialId, ciphertext, expiresAt}
    FN->>FN: открыть закрытым ключом → stateDir/agents/<key>/agent-pat (0600)
```

- **Principal.** Каждому активному агенту вида `agent` — размещённому или с
  `placement: none` — контроллер заводит principal в IAM правом `iam:agents` и сообщает
  его ядру. Principal CP и связку с правами выводит само ядро из ревизии; прав выдавать
  права у контроллера нет. Агенты вида `service` контроллер не трогает — их учётку
  выпускает bootstrap.
- **PAT на размещение.** Для каждой пары «агент — узел» свой PAT. Он шифруется
  публичным ключом X25519 этого узла (libsodium sealed box, X25519 + XSalsa20-Poly1305),
  контроллер хранит только шифротекст. Открыть его может только узел размещения.
- **Потолок PAT.** Audience — всегда `control-plane` и те audiences из
  `skills.audiences` и `identity.iam.audiences` агента, которые перечислены в
  `FLEET_TOKEN_AUDIENCES` контроллера;
  потолок scope — те scopes из `FLEET_TOKEN_SCOPES`, audience которых PAT получает
  (IAM отклоняет потолок со scope, которого не допускает ни одна audience токена:
  `422 invalid_scope_ceiling`). Scope относится к audience по префиксу
  (`control-plane:read` → `control-plane`); scope другой audience записывается как
  `audience=scope`, например `notification-service=notifications:send`. Если описание
  агента объявляет `identity.iam.scopeCeiling`, PAT получает только пересечение с ним.
  Привилегированный scope (`iam:…`, например
  `iam:identities.link` коннектора CRM) агент получает, только если объявил его в
  `identity.iam.scopeCeiling`; поэтому `iam` и `iam=iam:identities.link` в настройке
  контроллера другим агентам ничего не добавляют. IAM сверх того не даст агенту больше, чем
  держит сам service account контроллера, а `iam:agents` не делегируется никогда.
- **Ротация.** Контроллер запрашивает PAT сроком `FLEET_TOKEN_TTL_SECONDS` (по умолчанию
  7 дней — это и потолок IAM для PAT агента, `IAM_AGENT_PAT_MAX_TTL_SECONDS`; больше —
  `422 expiry_too_long`) и за 2 дня до истечения (не больше трети срока) выпускает новый. Узел получает его со следующим желаемым состоянием; контейнер
  агента пересоздаётся (сменился credential). Прежний PAT отзывается через 10 минут.
- **Отзыв.** PAT размещения, которого больше нет (агент переехал, остановлен, выведен из
  оборота или пропал из списка активных), отзывается на следующей сверке. При переезде
  новый узел получает новый PAT.
- Пока личность или PAT не готовы (IAM или ядро недоступны), агент остаётся в фазе
  `pending` с `reason.code: identity_pending`, а контроллер повторяет попытку на каждой
  сверке.

## Узел: как приводит контейнеры к желаемому состоянию

Узел держит два цикла над одним и тем же состоянием:

- **pull** — long-poll `GET /api/v1/nodes/me/desired?since=<generation>&wait=60`. Новое
  поколение сохраняется в `stateDir/desired.json` и сразу применяется. При сетевых
  ошибках — повтор через 2, 5, 10, 30, 60 секунд. Ответ `401` (контроллер больше не
  принимает токен узла) останавливает процесс узла;
- **report** — каждые `observeSeconds` локальная сверка контейнеров и `PUT
  /api/v1/nodes/me/observed`. Если Docker недоступен, узел сообщает `health: degraded` и
  продолжает попытки.

Правила для контейнеров:

| Событие | Что делает узел |
|---|---|
| экземпляра нет | создаёт и запускает контейнер |
| изменились образ (вида по умолчанию или названный агентом), окружение, секреты, ресурсы, сеть или credential | останавливает старый контейнер в фоне с таймаутом `drainSeconds` агента, удаляет, после дренажа создаёт новый; пока старый контейнер на дренаже, имя реплики занято и экземпляр в отчёте — `draining` |
| новая ревизия агента | ничего: контейнер не трогается, исполнитель сам выходит с кодом 75 после прогона |
| контейнер вышел с кодом `0` или `75` | запускает снова сразу |
| контейнер вышел с другим кодом | перезапуск с паузой 5, 10, 20… до 300 секунд; три сбоя подряд — состояние `crashloop` |
| экземпляр больше не нужен (агент остановлен, выведен, переехал, `replicas` уменьшили) | останавливает контейнер в фоне и удаляет. Если агент целиком пропал из желаемого состояния, таймаут остановки — 30 секунд |
| вид исполнителя не настроен, образ агента не допущен списком (`image_not_allowed`), секрета нет, PAT не открывается ключом узла | контейнер не создаётся; в отчёте экземпляр `stopped` с причиной |
| контейнер не создаётся (образа нет на машине, диск полон) | ждёт, как при сбое: пауза 5, 10, 20… до 300 секунд, в отчёте `starting`, после трёх неудач — `crashloop` с ошибкой. Изменённая спецификация (другой образ) пробуется сразу |

Остановка всегда идёт в фоне: долгий дренаж одного агента не задерживает остальные. Узел
удаляет открытые PAT агентов, которых больше нет в желаемом состоянии.

!!! note "`drainSeconds` и `SIGKILL`"
    `docker stop` получает ровно `drainSeconds` агента. Демон на `SIGTERM` даёт прогону
    в полёте те же `drainSeconds` и затем отменяет его (`cancelled`, причина `drained`,
    задача возвращается в очередь). Отмене нужно время на опрос прогона (до 30 с), поэтому
    при исчерпании срока `SIGKILL` может прийти раньше: run останется `running` до
    истечения аренды и будет закрыт восстановлением (`restart_recovery`).

### Наблюдаемое состояние

Отчёт узла — `PUT /api/v1/nodes/me/observed`:

| Поле | Значение |
|---|---|
| `appliedGeneration` | поколение, которое узел применил |
| `health` | `ok` или `degraded` (Docker недоступен) |
| `labels`, `executorKinds`, `executorImages`, `capacity`, `secrets` | текущие метки, виды, допустимые образы видов (только непустые списки), ёмкость и **имена** секретов |
| `replicas[]` | `agentKey`, `revision`, `replica`, `state`, `restarts`, `lastExitCode`, `message` |
| `version` | версия пакета `fleet` на узле |

Состояния экземпляра: `starting`, `running`, `draining`, `crashloop`, `stopped`. Из них
контроллер выводит фазу агента в Control Plane: хотя бы один `crashloop` — фаза
`crash_looping` с сообщением экземпляра; готовых (`running`) экземпляров не меньше
желаемого — `running`; иначе `pending`. `observedRevision` — наименьшая ревизия среди
работающих экземпляров.

## Отказ узла и контроллера

| Что случилось | Что происходит |
|---|---|
| узел пропал (выключен, сеть) | через 60 с без отчёта он `offline`; экземпляры переезжают на подходящие узлы с новыми PAT, старые PAT отзываются. Некуда переехать — `node_unavailable`, экземпляр ждёт возвращения узла |
| контроллер недоступен | узлы продолжают работать по `desired.json`; новые ревизии, остановки и переезды ждут контроллера |
| Control Plane недоступен контроллеру | контроллер работает с последним известным списком агентов |
| контроллер перезапущен | узлы, размещения, личности и шифротексты PAT — в SQLite на volume `fleet_data`; желаемое состояние узлов пересобирается при первом запросе |
| узел вернулся после переезда | его прежние экземпляры отсутствуют в новом желаемом состоянии — узел их останавливает |

!!! warning "Отключённый узел продолжает исполнять"
    Узел без связи с контроллером не знает, что его агентов перенесли. Пока он
    недоступен, но работает (например, потерял только выход к контроллеру), его
    контейнеры продолжают брать работу со своим прежним PAT, пока контроллер не отзовёт
    его на следующей сверке после переезда. Если нужно гарантированно остановить машину —
    остановите `fleet-node` и контейнеры `fleet-*` на ней.

## Контроллер { #controller }

### Запуск

```bash
tools/compose --profile fleet up -d fleet-controller
```

| Параметр | Значение |
|---|---|
| Профиль | `fleet` |
| Образ | `${IMAGE_PREFIX:-taimen}/fleet-controller:${IMAGE_TAG:-local}`, Dockerfile `services/fleet/Dockerfile`, контекст `${FLEET_BUILD_CONTEXT:-.}` (корень: `platform-auth-sdk` подключён соседней папкой) |
| Порт | 8040, на хост не публикуется |
| Путь в Caddy | `/fleet/*` (префикс срезается) |
| Volume | `fleet_data` → `/data` (SQLite `fleet.sqlite`) |
| Healthcheck | `GET /healthz` на `127.0.0.1:8040` |
| Лимит памяти | `${FLEET_MEM_LIMIT:-128m}` |
| Зависит от | `control-plane-api`, `iam-service` (healthy) |
| Пользователь | uid `10001` |

### Учётка контроллера

Контроллер — сервис платформы с учёткой вида `service` (`identity.kind: service`,
`placement: none`, см. [Агенты-сервисы](declarative-agents.md#service-agents)); его
описание и права задаёт bootstrap установки:

- в Control Plane — права `agents.read` и `agents.status.write`;
- в IAM — audiences `control-plane`, `iam`, `notification-service` и потолок
  `control-plane:read`, `control-plane:write`, `iam:agents`, `notifications:send`.

`deploy/bootstrap.py` на шаге **5d** выпускает этот service account и пишет
`secrets/fleet-iam.env` (`FLEET_CLIENT_ID`, `FLEET_CLIENT_SECRET`). После этого контроллер
нужно пересоздать: `tools/compose --profile fleet up -d fleet-controller`. Пока файла
нет, все маршруты, кроме `/healthz`, отвечают `503 not_configured`.

Bootstrap также регистрирует в IAM audience `fleet` со scopes `fleet:read` и
`fleet:admin` — для администраторских вызовов API контроллера.

### Переменные окружения

| Переменная | Значение в `deploy/local/compose.yml` | Смысл |
|---|---|---|
| `FLEET_DATA_DIR` | `/data` | каталог базы SQLite |
| `FLEET_CONTROL_PLANE_URL` | `http://control-plane-api:8000` | Control Plane внутри сети |
| `FLEET_IAM_URL` | `http://iam-service:8010` | IAM внутри сети |
| `FLEET_IAM_ISSUER` | `${TAIMEN_PUBLIC_URL}/iam` | публичный issuer IAM; с ним привязываются личности агентов и проверяются административные токены |
| `FLEET_IAM_TENANT` | `${IAM_TENANT_ID}` | IAM tenant |
| `FLEET_JWKS_URL` | `http://iam-service:8010/.well-known/jwks.json` | JWKS для проверки административных токенов |
| `FLEET_CLIENT_ID`, `FLEET_CLIENT_SECRET` | из `secrets/fleet-iam.env` | service account контроллера |
| `FLEET_AUDIENCE` | не задана, по умолчанию `fleet` | audience административных токенов |
| `FLEET_TOKEN_AUDIENCES` | см. `deploy/local/compose.yml` | какие audiences может получить PAT агента (через пробел) |
| `FLEET_TOKEN_SCOPES` | см. `deploy/local/compose.yml` | потолок scope PAT агентов (через пробел); scope не своей по префиксу audience — `audience=scope`; привилегированный (`iam:…`) — только агенту, объявившему его в `identity.iam.scopeCeiling` |
| `FLEET_TOKEN_TTL_SECONDS` | не задана, по умолчанию 7 дней | срок PAT агента, не больше `IAM_AGENT_PAT_MAX_TTL_SECONDS` |

В `.env` задаются `FLEET_MEM_LIMIT`, `FLEET_BUILD_CONTEXT` и `VOLUME_FLEET_DATA`
(см. [Переменные окружения](../reference/environment.md)).

### API контроллера

Публично — под `https://<хост>/fleet`. Контракт — `services/fleet/openapi/fleet.json`.

| Метод и путь | Кто | Что делает |
|---|---|---|
| `GET /healthz` | все | `{"status": "ok"}` |
| `POST /api/v1/join-keys` | токен audience `fleet`, `fleet:admin` | выпустить одноразовый ключ регистрации |
| `GET /api/v1/nodes` | `fleet:read` или `fleet:admin` | узлы: метки, виды, допустимые образы (`executorImages`), ёмкость, имена секретов, `health`, `status` (`online`/`offline`), `lastSeenAt`, `version` |
| `GET /api/v1/placements` | `fleet:read` или `fleet:admin` | размещения агентов: `status` (`placed`, `pending`, `stopped`), `reason` |
| `POST /api/v1/nodes:join` | одноразовый ключ в теле | регистрация узла |
| `GET /api/v1/nodes/me/desired` | токен узла | long-poll желаемого состояния (`since`, `wait` ≤ 60) |
| `PUT /api/v1/nodes/me/observed` | токен узла | отчёт узла, `204` |

Ошибки административных маршрутов: `401 invalid_token` (токен не прошёл проверку), `403
insufficient_scope`. Маршруты узла: `401 node_token_invalid`.

```bash
curl -sS https://platform.example.com/fleet/api/v1/nodes \
  -H "Authorization: Bearer $FLEET_TOKEN"
```

```json
{
  "items": [
    {
      "id": "<node-id>",
      "name": "worker-1",
      "labels": ["claude-subscription", "repos"],
      "executorKinds": ["claude-code", "skills"],
      "capacity": {"slots": 4, "cpus": 8.0, "memoryMb": 16384},
      "secrets": ["claude-oauth-token", "github-token"],
      "health": "ok",
      "status": "online",
      "lastSeenAt": "2026-01-15T10:00:20Z",
      "version": "0.1.0"
    }
  ]
}
```

Удаления узла и перевыпуска его токена в API нет. Узел, который больше не нужен,
достаточно выключить: через 60 секунд он `offline`, и его агенты переедут.

## Развёртывание узла

Узлу нужны Docker, исходящий HTTPS к контроллеру и каталог секретов. Референсная
раскладка узла — каталог `deploy/node/` (compose узла и пример `node.yaml`), образ
исполнителя — `deploy/agent-runner/`. Compose узла поднимает:

| Сервис | Зачем |
|---|---|
| сборка образа исполнителя | только сборка образа из `deploy/agent-runner/`; контейнеры агентов создаёт узел |
| `docker-proxy` | `tecnativa/docker-socket-proxy`: разрешены `CONTAINERS`, `VOLUMES`, `POST`; закрыты `EXEC`, `IMAGES`, `NETWORKS`, `BUILD` |
| `fleet-node` | образ `services/fleet/Dockerfile`, команда `fleet-node --config /etc/fleet-node/node.yaml`, uid `10001`; каталоги состояния и секретов смонтированы по путям хоста |
| служебные сервисы агентов | например одноразовые тестовые базы на `tmpfs` в сети `network` узла; адреса передаются агентам через `executors.<вид>.env` |


Порядок первого запуска:

```bash
# на машине узла
install -d -m 0700 /var/lib/fleet-node /etc/fleet-node/secrets
install -m 0600 /dev/null /etc/fleet-node/secrets/claude-oauth-token   # и заполнить
echo '<ключ регистрации>' > /etc/fleet-node/join-key
docker compose -f <compose узла> up -d --build
docker compose -f <compose узла> logs -f fleet-node
```

В журнале узла появится `joined the fleet as <node-id>`, затем `started fleet-<agent>-0`
для размещённых агентов. Проверка с центра — `GET /fleet/api/v1/nodes` и
`GET /api/v1/agents/{key}/status`.


## Типичные проблемы { #troubleshooting }

| Симптом | Причина и решение |
|---|---|
| все маршруты контроллера отвечают `503 not_configured` | нет `secrets/fleet-iam.env`: выполнить bootstrap (шаг 5d) и пересоздать `fleet-controller` |
| узел падает при старте: `node is not joined and no join key file is configured` | нет токена в `stateDir` и нет файла `joinKeyFile` — выпустить ключ и положить в файл |
| `401 join_key_invalid` | ключ истёк или уже использован — выпустить новый |
| `409 node_name_taken` | имя занято (в том числе прежней регистрацией этой машины с потерянным `stateDir`) — задать новое `name` |
| узел завершился: `the controller no longer accepts this node's credential` | токен узла не принят (`401`) — зарегистрировать узел заново с новым именем |
| `unset environment variables …` при старте узла | в `node.yaml` есть `${ИМЯ}`, которой нет в окружении процесса узла |
| агент `waiting_for_node`, `no_executor_kind` | ни один узел `online` не объявляет `executor.kind` агента — добавить вид в `executors` узла |
| `no_label` / `no_secret` | нет метки из `placement.requires` или файла секрета из `placement.secrets` в `secretsDir`. Имя файла должно совпадать с именем секрета |
| `no_capacity` | заняты слоты или не хватает `cpus`/`memoryMb` — увеличить `capacity` узла или уменьшить `resources` агента |
| агент `pending`, `identity_pending` | контроллер не смог завести principal или выпустить PAT: смотреть журнал `fleet-controller`. Частые причины — IAM недоступен, у service account нет `iam:agents`, IAM ограничивает срок PAT агента меньше запрашиваемого контроллером (`422 expiry_too_long`) |
| экземпляр `stopped`, `credential cannot be opened with this node's key` | `stateDir` с ключами узла пересоздан после регистрации — зарегистрировать узел заново |
| экземпляр `starting` или `crashloop`, `start failed: …` | Docker не создал контейнер; чаще всего образа нет на машине — socket proxy не даёт узлу скачивать образы, соберите или загрузите образ заранее |
| агент `waiting_for_node`, `image_not_allowed` | ни один узел `online` с видом агента не допускает его `executor.image` — добавить образ или шаблон в `executors.<вид>.images` узла и перезапустить `fleet-node`, либо убрать поле из описания |
| экземпляр `stopped`, `image_not_allowed: image … is not allowed for executor kind …` | список образов узла сократили после размещения — вернуть образ в список или дождаться, пока контроллер переразместит агента |
| отчёт узла отвергается после добавления `images` | контроллер без поддержки списков образов не знает `executorImages` — обновить контроллер |
| агент `crash_looping` | исполнитель падает при старте; причина — в `message` отчёта и в `docker logs fleet-<agent>-<replica>`. Выход с кодом 2 — описание агента не исполнимо на этом образе |
| новый образ под тем же тегом не подхватывается | узел сравнивает строку `image`, а не содержимое: пересборка под тем же тегом не пересоздаёт контейнер, а перезапуск после выхода 75 стартует прежний контейнер. Поменяйте тег в `executors.<вид>.image` и перезапустите `fleet-node` |
| контейнер агента не видит PAT или секрет | узел работает в контейнере без `hostStateDir`/`hostSecretsDir`, либо файлы не читаются uid образа исполнителя |
| правка `node.yaml` не видна контроллеру | конфигурация читается при старте — перезапустить `fleet-node` |

## См. также

- [Агенты описанием](declarative-agents.md) — вид исполнителя `git-connector`, `executor.image`
- [Агенты пакета](../packages/agents.md) — образ исполнителя в пакете
- [Интеграции](../packages/integrations.md#images) — сборка образов наблюдателя и хоста скиллов
- [Конфигурация исполнителя](configuration.md)
- [Установка исполнителя](installation.md)
- [Identity агента](agent-identity.md)
- [Сервисы и порты](../reference/services-and-ports.md)
- [Bootstrap](../getting-started/bootstrap.md)
