# Глоссарий

Термины платформы Taimen по алфавиту: сначала латиница (имена сущностей и
контрактов, как в коде и API), затем кириллица. Для каждого термина —
краткое определение и ссылка на статью, где он раскрыт. Статья для всех
читателей руководства.

## A

**Access token** — короткоживущий JWT, который IAM выдаёт в обмен на PAT,
client credentials или федеративный токен. Выпускается ровно на один
audience; время жизни — `IAM_TOKEN_TTL_SECONDS` (300 с). Несёт identity и
scopes, но не доменные права. → [Токены, audiences, scopes](../iam/tokens.md)

**Acceptance (приёмка)** — критерии, по которым проверяется, что цель
(Goal) достигнута; набор проверок с уникальными ключами. →
[Цели, приёмка и evidence](../control-plane/goals-and-evidence.md)

**Adapter (адаптер исполнителя)** — часть демона runner, которая
исполняет run конкретным кодовым агентом: `echo`, `claude-code`, `codex`,
отдельно — OpenCode. → [Адаптеры исполнителей](../runner/adapters.md)

**Approval** — запрос решения человека (статусы `pending`, `approved`,
`rejected`, `cancelled`). Решает principal с правом `approvals.decide`;
агенту это право не выдаётся. → [Approvals](../control-plane/approvals.md)

**Artifact (артефакт)** — зарегистрированный результат работы по задаче:
коммит, документ, транскрипт прогона и т. п. →
[Артефакты и комментарии](../control-plane/artifacts.md)


**Audience** — идентификатор одного resource service в IAM
(`control-plane`, `memory-service`,
`notification-service` …). Реестр audience задаёт допустимые
scopes (`allowedScopes`). → [Права и scopes](permissions.md)

**Audit reason** — точная причина отказа (`binding_not_found`,
`credential_revoked`, `issuer_mismatch` …), которая пишется только в audit
и лог; клиенту уходит обобщённый код. → [Коды ошибок](errors.md)

**Authentication context** — запись IAM о свежем входе человека (`issuer`,
`acr`, `amr`, время). Выпуск PAT человеку требует контекста не старше
`IAM_PAT_MAX_AUTHENTICATION_AGE_SECONDS`. → [Credentials и PAT](../iam/credentials.md)

## B

**Binding (IAM principal binding)** — строка `iam_principal_bindings` в
Control Plane: пара (issuer, IAM principal) → локальный principal и его
права. Статусы `active`, `disabled`, `revoked`. Без binding токен IAM не
даёт доступа к ядру. → [Права и scopes](permissions.md#iam-principal-bindings)

**Bootstrap** — первичная инициализация: `POST /api/v1/bootstrap` Control
Plane (tenant, администратор, binding) и bootstrap-эндпоинты IAM; в
поставке — `make bootstrap` (`deploy/bootstrap.py`). →
[Bootstrap](../getting-started/bootstrap.md)


**Bootstrap token** — секрет, открывающий bootstrap-эндпоинты:
`CP_BOOTSTRAP_TOKEN` (заголовок `Authorization: Bearer`),
`IAM_BOOTSTRAP_TOKEN` (заголовок `X-IAM-Bootstrap-Token`).

## C

**Capability** — (1) организационная: именованная способность principal,
используемая в требованиях задач; (2) протокольная: что умеет харнесс
(`events.realtime`, `checkpoints`, `skills.protocol.<p>` …), объявляется
при открытии сессии. Не путать.

**Checkpoint** — запись промежуточного состояния run (`kind` + данные),
из которой продолжение работы восстанавливается новым run. →
[Исполнение — claims и runs](../control-plane/execution.md)

**Child handle / child run** — делегирование части работы дочернему run с
ограниченным grant (права, capabilities, skills не шире родителя);
токен вида `ch1_<id>_<secret>`. → [Исполнение](../control-plane/execution.md)

**Claim** — эксклюзивная аренда задачи исполнителем на TTL
(`CP_CLAIM_TTL_SECONDS`). Пока claim жив, писать в задачу может только
его держатель с `claimId` и `fencingToken`. → [Исполнение](../control-plane/execution.md)

**Client credentials** — `clientId` + `clientSecret` service account;
обмениваются на access token через `POST /api/v1/tokens/exchange`. →
[Service accounts](../iam/service-accounts.md)

**Context adapter** — процесс `context-adapter` Control Plane, который
доставляет события ядра в память (memory-service) с изоляцией по tenant.

**ContextPack** — собранный памятью пакет контекста для задачи или run в
пределах бюджета токенов (`CP_CONTEXT_DEFAULT_MAX_TOKENS`). →
[Контекст задачи и память](../control-plane/context.md)

**Control Plane** — ядро платформы: модель Work (задачи, цели, workspaces,
проекты), исполнение (claims, runs), approvals, артефакты, журнал событий,
харнесс-протокол. → [Control Plane](../control-plane/index.md)

**Cursor (курсор событий)** — непрозрачная позиция в журнале событий;
клиент передаёт её без изменений, чтобы продолжить чтение. →
[События](../control-plane/events.md)

## D

**Delegation (делегирование)** — разрешение агенту действовать от имени
конкретного человека (`delegations.manage`).

**Domain pack (пакет видов)** — зарегистрированный в памяти набор видов
сущностей и связей как данные; регистрирует только identity ядра
(`memory:service`). → [Модель знаний](../memory/knowledge-model.md)

## E

**Edge** — профиль compose с единственным внешним контейнером `caddy`. →
[Периметр и TLS](../operations/edge-and-tls.md)

**Entitlement** — лицензирование продуктов и features, квоты и места.
Проверку выполняет внешний сервис лицензий, если он подключён (стадия
entitlement PEP). → [platform-auth-sdk](../sdk/platform-auth-sdk.md#entitlement-stage)

**Event journal (журнал событий)** — упорядоченный поток изменений
Control Plane (`GET /api/v1/events`, WebSocket), источник для адаптеров и
проекций. → [События](../control-plane/events.md)

**Evidence** — подтверждение выполнения проверки приёмки, ссылающееся на
ключ проверки из acceptance. → [Цели, приёмка и evidence](../control-plane/goals-and-evidence.md)

**Execution workspace (рабочая копия)** — локальный git worktree, в
котором runner исполняет задачу на ветке задачи; может включать соседние
репозитории на ревизиях суперпроекта. → [Рабочие копии](../runner/execution-workspace.md)

**Executor (исполнитель skills)** — процесс, исполняющий вызовы skills по
протоколам `local`, `http`, `mcp` (право `skills.execute`); транспорт без
собственных прав.

## F

**Fail closed** — принцип: если решение (проверка токена, PDP,
entitlement) получить нельзя, запрос отклоняется (`503 …_unavailable`), а
не пропускается.


**Federation (федерация)** — обмен токена внешнего OIDC-провайдера на
access token IAM: `POST /api/v1/tenants/{t}/federation:exchange`. Только
для людей. → [Федерация identity](../iam/federation.md)

**Fencing token** — монотонный номер эпохи claim. Операции с устаревшим
токеном отвергаются кодом `stale_claim`, даже если процесс считает себя
владельцем.

## G

**Gate** — approval, который удерживает задачу (`approval_required`) или
разрешает skill с побочным эффектом `external_write`.

**Goal (цель)** — желаемое состояние, которое tenant хочет сделать
истинным; иерархия целей, связь с задачами, acceptance и evidence (права
`goals.read`, `goals.write`). → [Цели, приёмка и evidence](../control-plane/goals-and-evidence.md)

## H

**Handoff** — передача работы: run публикует checkpoint handoff, и
продолжение берёт другой исполнитель или человек в Human Harness
(`reason=human_harness_handoff`).

**Harness (харнесс)** — клиент, через который человек или агент работает
с Control Plane: MCP-плагин, Human Harness, демон runner. Объявляет тип и
capabilities при открытии сессии. → [Харнесс-протокол](../control-plane/harness-protocol.md)

**Harness protocol** — контракт сессий, claims, runs и курсоров между
харнессом и ядром (`control-harness`, версии `1` и `2`).

**Human Harness** — движок ассистента человека: персональный контейнер, с которым человек говорит из панели консоли и из Telegram. → [Ассистент](../operator/assistant.md)

## I

**IAM (iam-service)** — сервис identity: tenants, principals, credentials
(PAT, service accounts, федерация), выпуск access token и JWKS. Доменных
прав не хранит. → [IAM](../iam/index.md)

**Idempotency-Key** — заголовок, делающий повтор записи безопасным: тот же
ключ с тем же телом возвращает сохранённый ответ; с другим телом —
`409 idempotency_key_reused`.

**If-Match / ETag** — оптимистичная блокировка: `ETag` вида
`"task-<version>"`, при несовпадении — `409 version_conflict`, без
заголовка — `428 if_match_required`.

**Installation (установка каталога)** — файл `kind: Installation`
(`deploy/packages.yaml`), перечисляющий пакеты каталога для окружения. →
[Пакеты каталога](../control-plane/catalog-packages.md)

**Issuer** — значение `iss` токенов IAM, `${TAIMEN_PUBLIC_URL}/iam`.
Входит в ключ binding: смена публичного адреса требует переноса bindings.

## J

**JWKS** — публичные ключи IAM (`/.well-known/jwks.json`), по которым
resource services проверяют подпись токенов; кэшируются с границей
устаревания.

## K

**Keycloak** — внешний IdP людей (профиль `idp`, realm `platform`): только
подтверждает, кто человек; токен уходит в IAM `federation:exchange`. →
[Keycloak — внешний IdP](../iam/keycloak.md)

**Knowledge pack** — закреплённый по версии (`name@version`) пакет знаний,
включаемый на корневом workspace. → [Загрузка знаний](../memory/ingestion.md)

## L

**Legacy API key** — ключ вида `cp_<prefix>_<secret>`, прежний способ
аутентификации в Control Plane. Работает только при
`CP_LEGACY_API_KEYS_ENABLED=true`; в стеке по умолчанию выключен.

**Lifecycle (жизненный цикл типа задачи)** — объявленные типом задачи
статусы, их категории и разрешённые переходы.

## M

**MCP-сервер (`control-plane-mcp`)** — сервер Model Context Protocol,
открывающий инструменты `cp_*` Control Plane кодовым агентам. →
[CLI и MCP-сервер](../control-plane/cli-and-mcp.md)

**memory-service** — движок памяти: граф знаний (PostgreSQL + Apache AGE),
векторный поиск (pgvector), наблюдения, сборка ContextPack. →
[Память](../memory/index.md)

## N

**Namespace** — изолированная база знаний в памяти. Память tenant —
`tenant:<tenant_id>` и поддерево `tenant:<tenant_id>:*`. →
[Namespaces и доступ](../memory/namespaces.md)

## O

**Observation (наблюдение)** — сырой факт, записываемый в память
(`observations.write`), с источником и scope.

**Origin** — происхождение задачи в work graph (откуда она возникла).

**Outbox** — таблица исходящих событий, которые worker доставляет с
повторами и экспоненциальной задержкой (`CP_OUTBOX_*`).

## P

**Package (пакет каталога)** — версионируемый набор объектов каталога
(типы задач, шаблоны, роли, capabilities, skills) в `packages/`, который
bootstrap приводит в Control Plane. → [Пакеты каталога](../control-plane/catalog-packages.md)

**PAT (Platform Access Token)** — долгоживущий credential человека или
агента в IAM с потолком scopes и списком audiences. Сам как Bearer не
предъявляется — только обменивается на access token. →
[Credentials и PAT](../iam/credentials.md)

**PDP / PEP** — Policy Decision Point (внешний PDP, решает) и Policy
Enforcement Point (resource service, применяет решение). Режим ядра —
`CP_AUTHZ_MODE`.

**Permission (право)** — плоская строка прав Control Plane (`tasks.read`,
`tasks.claim`, `admin` …), хранится в binding. → [Права и scopes](permissions.md)

**Principal** — участник: `human`, `agent`, `service` в Control Plane;
`human`, `agent`, `service_account`, `workload` в IAM. → [Tenants и principals](../iam/principals.md)

**Profile (профиль compose)** — группа сервисов `deploy/local/compose.yml`, включаемая
флагом `--profile` (`core`, `edge`, `idp`, `harness`, `fleet` …). →
[Сервисы и порты](services-and-ports.md)

**Project profile** — проектная надстройка над workspace: шаблон,
конфигурация по ревизиям, governance, представления.

## R

**Reconcile (сверка снимков)** — приведение памяти к снимку источника
целиком; выполняется только identity ядра.


**Resource service** — сервис, который проверяет чужие токены и сам
решает о доменных правах (Control Plane, memory-service,
notification-service).

**Role (роль)** — организационная роль Control Plane (не даёт прав). →
[Права и scopes](permissions.md#roles)

**Run** — одна попытка исполнения задачи под claim; статусы `running`,
`succeeded`, `failed`, `cancelled`, `suspended`. Несёт actions,
checkpoints, артефакты, бюджет длительности.

**Run action** — зафиксированное действие внутри run (например,
`tool.<имя>` на каждый вызов инструмента агента), `started` → finish.

**Run control** — управляющее сообщение живому run: `queue`, `steer`,
`redirect`, `request_cancel`, `force_cancel`; подтверждается исполнителем.

**Runner** — хост и демон (`control-plane-agent`), который берёт
назначенные задачи и исполняет их адаптером. → [Агенты и runner](../runner/index.md)

## S

**Scope** — единица потолка полномочий токена с префиксом audience
(`control-plane:write`, `memory:read`). Сужает права, никогда не
расширяет. → [Права и scopes](permissions.md)

**Scope ceiling (потолок scopes)** — максимальный набор scopes, который
credential (PAT, service account) может запросить при обмене.

**SCIM** — протокол provisioning пользователей и групп из внешнего
каталога в IAM (audience `iam-scim`).

**Service account** — principal-сервис в IAM с client credentials; PAT не
получает. → [Service accounts](../iam/service-accounts.md)

**Session (сессия харнесса)** — аренда присутствия харнесса
(`CP_SESSION_TTL_SECONDS`), внутри которой берутся claims.

**Shadow mode** — `CP_AUTHZ_MODE=shadow`: решает локальная проверка, PDP
спрашивается параллельно, расхождения пишутся в журнал.

**Skill** — версионированная единица исполнения с контрактом (входы,
выходы, протокол `http`/`local`/`mcp`, побочные эффекты, риск,
идемпотентность). → [skill-sdk](../sdk/skill-sdk.md)

**Skill invocation (вызов skill)** — запрос ядру исполнить версию skill
(`skills.invoke`); исполнитель берёт вызов в аренду.

**Status category (категория статуса)** — единственный словарь статусов, на
который опирается ядро: `backlog`, `active`, `blocked`,
`terminal_success`, `terminal_cancelled`. Ключи статусов задаёт тип задачи.
→ [Типы задач и статусы](../control-plane/task-types.md)

## T

**Task (задача, work item)** — единица работы Control Plane; тип задачи
определяет статусы, поля и исполнение. → [Модель работы](../control-plane/work-model.md)

**Task relation (связь задач)** — `parent`, `blocks`, `depends_on`,
`spawned_by`, `related_to`; `blocks` и `depends_on` влияют на готовность
(`task_not_ready`).


**Task type (тип задачи)** — версионированное описание вида работы:
жизненный цикл, схема полей, исполнение, критерии приёмки по
умолчанию. → [Типы задач и статусы](../control-plane/task-types.md)

**Tenant** — изолированная организация. В IAM и Control Plane у новой
инсталляции единый UUID tenant. → [Tenants и principals](../iam/principals.md)

**Transcript (трасса прогона)** — артефакт `transcript` с лентой
рассуждений и вызовов инструментов агента (без thinking, с редакцией путей
и credential). → [Трасса прогонов](../runner/trace.md)

## W

**Work graph** — граф работы: цели, задачи, связи, origin, acceptance и
evidence.

**Worker** — процесс `control-plane-worker`: outbox, отложенные исходы
approvals, фоновые задачи ядра.

**Workspace** — узел иерархии организации работы внутри tenant; имеет тип
(`allowedChildTypes`), может нести project profile.

## А–Я

**Агент** — principal вида `agent`: автономный исполнитель с собственным
PAT и binding без human-only прав.

**Бюджет run** — предельная длительность run (`maxDurationSeconds`);
превышение — `budget_exceeded`.

**Вертикальный пакет** — предметная вертикаль как пакет каталога без своего runtime: работа, процессы и правила
исполняет ядро, действия во внешнем мире — скиллы. → [Пакеты](../packages/index.md)

**Дело** — экземпляр процесса: данные, стадии, таймеры, журнал решений и
исход; в базе знаний — узел `case`. → [Процессы](../processes/index.md)


**Оператор** — человек, ведущий работу в Control Plane через MCP-плагин
или CLI. → [Работа оператора](../operator/index.md)

**Потолок** — см. *Scope ceiling*.

**Производственный календарь** — объект каталога вида `Calendar`:
рабочие и нерабочие дни по годам для `cal.*` в выражениях.

**Процесс** — объект каталога вида `Process`: стадии, шаги, сроки,
согласования и проекция в базу знаний; исполняет ядро. →
[Процессы](../processes/index.md)

**Суперпроект** — репозиторий верхнего уровня: компоненты подключены
git-сабмодулями плоско в корне, плюс `deploy/local/compose.yml`, `.env.example`,
`Makefile`, `deploy/`, `packages/`, `tools/`.

## См. также

- [Ключевые понятия](../overview/concepts.md)
- [Архитектура](../overview/architecture.md)
- [Права и scopes](permissions.md)
- [Коды ошибок](errors.md)
