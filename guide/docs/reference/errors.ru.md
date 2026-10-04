# Коды ошибок

Машинные коды ошибок всех сервисов платформы: код, HTTP-статус, причина и
что делать. Статья для разработчика харнесса или интеграции и для
инженера, который разбирает отказ по логу. Коды — стабильный контракт:
реагируйте на `code`, а не на текст сообщения.

## Форматы ответа об ошибке

Сервисы используют разные конверты. Код ошибки всегда в одном поле:

| Сервис | Конверт | Поле с кодом |
|---|---|---|
| Control Plane | `{"error": {"code", "message", "details", "requestId"}}` | `error.code` |
| iam-service | стандартный FastAPI `{"detail": "<code>"}` (SCIM — формат SCIM, см. ниже) | `detail` |
| memory-service | `{"detail": "<текст>"}` — человекочитаемый текст, машинных кодов нет | HTTP-статус |

Пример ответа Control Plane:

```json
{
  "error": {
    "code": "stale_claim",
    "message": "Presented claim is no longer live",
    "details": {"taskId": "<task-id>"},
    "requestId": "req_…"
  }
}
```

`requestId` совпадает с полем в логе сервиса — по нему ищется запись с
трассировкой для `500 internal_error`.

### Общие правила реакции

| HTTP | Смысл | Повторять? |
|---|---|---|
| 400, 422 | Запрос нарушает контракт или бизнес-правило | Нет — исправить запрос |
| 401 | Нет действительного credential | Нет — перевыпустить токен |
| 403 | Credential валиден, но прав не хватает | Нет — выдать права |
| 404 | Не найдено или не видно этому principal | Нет |
| 409 | Конфликт состояния (claim, версия, идемпотентность) | Зависит от кода: перечитать состояние |
| 413 | Слишком большое тело | Нет |
| 428 | Нужен `If-Match` | Повторить с заголовком |
| 429 | Лимит частоты | Да, с задержкой |
| 502, 503 | Зависимость недоступна; решение не принято (fail closed) | Да, с задержкой и тем же `Idempotency-Key` |

!!! warning "Отказы аутентификации намеренно неразличимы"
    Битый, истёкший, отозванный токен, чужой issuer или audience,
    отключённый principal, отсутствующий binding — клиент всегда видит
    один и тот же ответ (`401 invalid_credentials` у Control Plane,
    `401 invalid_token` у IAM и SDK-сервисов). Разные коды превратили бы
    эндпоинт в оракул о чужих credential. Точная причина пишется только в
    audit и лог — см. [Причины в audit](#audit-reasons).

## Control Plane

Коды `DomainError` и обработчиков API `control-plane`. Статус по классу
ошибки: `ValidationError` — 422, `BadRequestError` — 400, `ConflictError`
— 409, `AuthorizationError` — 403, `AuthenticationError` — 401,
`UpstreamError` — 502, `DependencyUnavailableError` — 503.

### Общие ошибки запроса

| Код | HTTP | Причина | Что делать |
|---|---|---|---|
| `custom_fields_invalid` | 422 | `customFields` не проходят JSON Schema типа задачи, шаблона или workspace. | Сверить поля со схемой (`details`). |
| `empty_update` | 422 | PATCH без полей. | Передать хотя бы одно поле. |
| `if_match_required` | 428 | Операция требует заголовок `If-Match` (оптимистичная блокировка). | Прочитать сущность, передать её `ETag` вида `"task-<version>"`. |
| `internal_error` | 500 | Необработанная ошибка сервера; трассировка — только в логе. | Найти запись в логе по `requestId`. |
| `invalid_document` | 422 | Поле должно быть JSON-объектом. | Передать объект. |
| `invalid_field` | 422 | Поле передано в недопустимом виде (например, `null` там, где нужно `{}`). | См. `details.field`. |
| `invalid_if_match` | 400 | `If-Match` не в формате `"<entity>-<version>"`. | Передавать значение `ETag` без изменений. |
| `invalid_json_schema` | 422 | Недопустимая JSON Schema (например, `$ref` не на тот же документ). | Оставить только локальные `$ref`. |
| `invalid_limit` | 422 | `limit` вне допустимого диапазона. | Уменьшить `limit`. |
| `invalid_priority` | 422 | Неизвестный приоритет. | `critical`, `high`, `medium`, `low`. |
| `invalid_request` | 400 | Тело или параметры не соответствуют контракту API (ошибки pydantic, до 20 штук в `details.errors`). | Исправить запрос по `details.errors[].loc`. |
| `invalid_sort` | 422 | Неизвестное значение `sort`. | Использовать поддерживаемый ключ сортировки. |
| `invalid_status` | 422 | Неизвестное значение статуса в фильтре или теле. | Сверить со статусами типа задачи / сущности. |
| `invalid_status_category` | 422 | Неизвестная категория статуса в фильтре. | `backlog`, `active`, `blocked`, `terminal_success`, `terminal_cancelled`. |
| `method_not_allowed` | 405 | Метод не поддерживается маршрутом. | Сверить метод с OpenAPI (`/openapi.json`). |
| `non_canonical_value` | 422 | В каноническом документе недопустимое значение (например, число с плавающей точкой). | Передавать целые числа или строки. |
| `not_found` | 404 | Сущность не найдена или не видна вызывающему (в том числе чужой tenant). | Проверить id и tenant токена. |
| `payload_too_deep` | 422 | JSON-документ вложен глубже предела. | Упростить структуру. |
| `payload_too_large` | 422 | Строка или документ длиннее предела. | Сократить значение. |
| `rate_limited` | 429 | Превышен лимит запросов. | Повторить с задержкой. |
| `request_too_large` | 413 | Тело больше `CP_MAX_BODY_BYTES` (для снимков знаний — `CP_KNOWLEDGE_SNAPSHOT_MAX_BODY_BYTES`). | Уменьшить тело или поднять лимит. |
| `secret_material_rejected` | 422 | В конфигурации или полях обнаружено значение, похожее на секрет. | Хранить секрет вне ядра, передавать непрозрачный `secretRef`. |
| `unavailable` | 503 | Сервис временно не готов. | Повторить позже; проверить `/health/ready`. |
| `version_conflict` | 409 | Версия в `If-Match` устарела: сущность изменил кто-то другой. | Перечитать сущность и повторить с новой версией. |

### Аутентификация и авторизация

| Код | HTTP | Причина | Что делать |
|---|---|---|---|
| `already_bootstrapped` | 409 | Tenant уже инициализирован. | Повторный bootstrap не нужен. |
| `authorization_unavailable` | 503 | Решение внешнего PDP получить не удалось (SDK). | Проверить доступность PDP. |
| `bootstrap_disabled` | 403 | `CP_BOOTSTRAP_TOKEN` не задан — bootstrap выключен. | Задать токен и перезапустить API. |
| `decision_unavailable` | 503 | Внешнее решение (PDP) недоступно; запрос не выполнен (fail closed). | Проверить PDP и `CP_POLICY_BASE_URL`; повторить. |
| `delegation_required` | 403 | Нет активного делегирования, позволяющего действовать от имени этого principal. | Создать делегирование (`delegations.manage`). |
| `entitlement_unavailable` | 503 | Сервис лицензий недоступен, кэш устарел. | Проверить сервис; повторить. |
| `iam_identity_bound_elsewhere` | 409 | IAM identity уже связана с другим tenant. | Использовать отдельную identity на tenant. |
| `insufficient_scope` | 403 | Scope токена не покрывает операцию (проверка SDK). | Обменять PAT с нужным scope. |
| `invalid_credentials` | 401 | Нет credential или он недействителен: битый, истёкший, чужой issuer/audience, отозванный, нет или отключён binding. Причина пишется только в audit. | Перевыпустить токен обменом PAT; проверить binding и `CP_IAM_ISSUER`. |
| `invalid_delegation` | 422 | Делегирование некорректно (например, `agentPrincipalId` — не агент). | Исправить стороны делегирования. |
| `invalid_display_name` | 422 | Пустое `displayName`. | Задать имя. |
| `invalid_kind` | 422 | Неизвестный вид principal. | `human`, `agent`, `service`. |
| `invalid_permissions` | 422 | Неизвестные права или не-admin создаёт admin-ключ. | Сверить с перечнем прав. |
| `invalid_requirement` | 422 | Некорректная ссылка в требованиях (skill `name` или `name@version`). | Исправить `requirements`. |
| `not_eligible` | 403 | Principal не удовлетворяет требованиям задачи (роль/capability/skill) или не может решать этот approval. | Назначить нужную роль/capability или выбрать другого исполнителя. |
| `not_entitled` | 403 | Продукт или feature не лицензированы (entitlement). | Выдать лицензию или отключить `CP_ENTITLEMENT_ENABLED`. |
| `permission_denied` | 403 | Не хватает права (`details.required`), либо PDP отказал (`details.reasonCode`, `decisionId`). | Выдать право в binding или роль во внешнем PDP; проверить scope токена. |
| `permission_escalation` | 403 | Попытка выдать права, которых нет у вызывающего credential. | Выдавать только свои права или действовать администратором. |
| `permissions_not_allowed_for_kind` | 422 | `admin` или `approvals.decide` для principal вида `agent`/`service`. | Убрать human-only права. |
| `policy_unavailable` | 503 | `CP_AUTHZ_MODE=policy`: внешний PDP не ответил, решения нет; запрос не выполнен (fail closed). | Восстановить PDP или вернуть `CP_AUTHZ_MODE=local`. |
| `principal_not_active` | 403, 422 | Principal не активен (403 при входе, 422 при привязке identity). | Активировать principal. |
| `unknown_requirement` | 422 | Роль или capability из требований не найдена в scope задачи. | Создать роль в workspace задачи. |
| `verification_unavailable` | 503 | Нечем проверить токен: JWKS недоступен дольше `CP_IAM_JWKS_STALE_AFTER_SECONDS` или источник отзыва недоступен. | Проверить доступность `iam-service` из контейнера. |

### Отключение и включение principal { #principal-disable-enable }

`POST /api/v1/principals/{principal_id}:disable` и `:enable` (CP-ADR-0077). Те же отказы
возвращают ворота `POST /api/v1/authz:check` для действий `disable` и `enable` над
ресурсом `principal`: в `reason.code` ответа — код эндпоинта.

| Код | HTTP | Причина | Что делать |
|---|---|---|---|
| `permission_denied` | 403 | Нет права `principals.write`. | Выдать право в связке. |
| `principal_kind_not_disableable`, `principal_kind_not_enableable` | 422 | Цель — сервисная учётка (`service`). | Сервис выключает его установщик. |
| `cannot_disable_self` | 409 | Попытка отключить себя. | Отключает другой человек с правами. |
| `permission_escalation` | 403 | `:disable`: у цели `admin` в неотозванной связке или API-ключе, а у вызывающего `admin` нет (`details.missing=["admin"]`). `:enable`: права живых ключей и неотозванных связок цели выходят за права вызывающего (`details.missing`). | Действовать администратором. |
| `use_agent_retire` | 409 | `:disable`: цель — principal агента реестра (`details.agent`). | Выводить агента `POST /api/v1/agents/{key}:retire`. |
| `use_agent_publish` | 409 | `:enable`: цель — principal агента реестра любого статуса (`details.agent`, `details.agentStatus`). | Возвращать агента публикацией ревизии. |

Повтор по уже отключённому (`:disable`) или уже активному (`:enable`) principal'у —
`200` без изменений.

### Идемпотентность

| Код | HTTP | Причина | Что делать |
|---|---|---|---|
| `idempotency_in_flight` | 409 | Такой же запрос ещё выполняется, ожидание истекло (`CP_IDEMPOTENCY_WAIT_TIMEOUT_SECONDS`). | Повторить с тем же ключом позже. |
| `idempotency_key_required` | 400, 422 | Операция требует `Idempotency-Key` (1..200 символов). 400 — у вызовов skills, 422 — у runs и child handles. | Передавать уникальный ключ на каждую логическую операцию. |
| `idempotency_key_reuse` | 409 | Ключ уже называет другой вызов skill. | Новый ключ для нового вызова. |
| `idempotency_key_reused` | 409 | Ключ уже использован с другим телом или другим principal. | Сгенерировать новый ключ. |
| `invalid_idempotency_key` | 422 | Ключ неверной длины. | 1..200 символов. |

### Сессии и claims

| Код | HTTP | Причина | Что делать |
|---|---|---|---|
| `claim_expired` | 409 | Аренда claim истекла. | Взять задачу заново. |
| `claim_holder_mismatch` | 403 | Claim держит другой principal. | Не писать в чужую задачу; `claims.manage` — для администратора. |
| `claim_not_active` | 409 | Claim не активен (освобождён или устарел). | Перечитать контекст; взять задачу заново. |
| `claim_not_expired` | 409 | Reclaim живого claim. | Дождаться истечения или освободить claim. |
| `invalid_harness` | 422 | `harness.type` не в формате идентификатора клиента. | Строчные буквы, цифры, `.`, `_`, `-`. |
| `invalid_ttl` | 422 | TTL вне границ `CP_*_TTL_MIN/MAX_SECONDS`. | Запросить TTL в допустимом диапазоне. |
| `session_expired` | 409 | Аренда сессии истекла. | Открыть новую сессию, затем заново взять задачу. |
| `session_not_active` | 409 | Сессия claim больше не жива. | Открыть сессию и перечитать контекст. |
| `session_owner_mismatch` | 403 | Сессия принадлежит другому principal. | Использовать свою сессию. |
| `stale_claim` | 409 | Fencing отклонил операцию: процесс больше не владеет задачей (claim перехвачен, устарел, неверный `fencingToken`). | Прекратить запись, перечитать контекст (`/api/v1/harness/context`), при необходимости взять задачу заново. |
| `task_already_claimed` | 409 | У задачи уже есть активный claim. | Выбрать другую задачу или дождаться освобождения. |
| `task_claimed` | 409 | Изменение задачи с активным claim без `claimId` и `fencingToken`. | Передать `claimId` и `fencingToken` своего claim. |
| `task_not_claimable` | 422 | Статус задачи не допускает claim. | Перевести задачу в рабочий статус. |
| `task_not_ready` | 409 | Не завершены блокирующие зависимости (`blocks`/`depends_on`). | Завершить зависимости. |
| `unsupported_protocol_version` | 422 | Версия харнесс-протокола не поддерживается. | Использовать `control-harness/2` (поддерживаются `1` и `2`). |

### Runs и исполнение

| Код | HTTP | Причина | Что делать |
|---|---|---|---|
| `action_already_finished` | 409 | Action уже завершён. | Не завершать повторно. |
| `agent_revision_mismatch` | 422 | `:start-run`: ревизия не принадлежит агенту вызывающего или передана principal без агента. | Передать ревизию своего агента (`GET /agents/me`) или не передавать поле. |
| `agent_revision_required` | 422 | `:start-run` от principal, привязанного к агенту, без `agentRevisionId`. | Передать ревизию своего агента (`GET /agents/me`). |
| `artifact_mismatch` | 422 | Run не принадлежит указанной задаче. | Сверить `taskId` и `runId`. |
| `budget_exceeded` | 409 | Run превысил бюджет длительности. | Завершить run; увеличить `maxDurationSeconds` для нового. |
| `invalid_action` | 422 | Пустое имя action. | Задать `action`. |
| `invalid_budget` | 422 | Бюджет не положителен. | `maxDurationSeconds > 0`. |
| `invalid_checkpoint` | 422 | Пустой `kind` checkpoint. | Задать `kind`. |
| `invalid_handoff` | 422 | Handoff человеку требует `reason=human_harness_handoff` и `kind=handoff`. | Исправить поля handoff. |
| `invalid_name` | 422 | Пустое имя артефакта. | Задать `name`. |
| `invalid_type` | 422 | Пустой тип артефакта. | Задать `type`. |
| `run_already_active` | 409 | У claim уже есть работающий run. | Завершить текущий run. |
| `run_cancel_requested` | 409 | Run принял кооперативную отмену и не может начинать новые actions. | Завершить run. |
| `run_holder_mismatch` | 403 | Операция требует держателя run (или `claims.manage`). | Выполнять от principal, держащего run. |
| `run_id_required` | 403 | Вызывающий исполняет ограниченный child run и должен указать `runId`. | Передать `runId`. |
| `run_in_progress` | 409 | У задачи активный run. | Завершить run через `:succeed`, `:fail` или `:cancel`. |
| `run_not_active` | 409 | Run не в состоянии `running`. | Перечитать run; начать новый. |
| `run_owner_mismatch` | 403 | Run принадлежит другому principal. | Действовать своим run. |
| `run_version_conflict` | 409 | `expectedRunVersion` не совпадает. | Перечитать run. |
| `task_not_runnable` | 422 | Статус задачи не позволяет начать run. | Перевести задачу в рабочий статус. |
| `tool_not_authorized` | 403 | Skill или инструмент не разрешён для этого run. | Назначить skill principal или задаче. |
| `unsafe_handoff_payload` | 422 | Checkpoint handoff содержит абсолютные локальные пути или чувствительные ключи. | Убрать пути и секреты. |

### Управление run (run controls)

| Код | HTTP | Причина | Что делать |
|---|---|---|---|
| `control_message_out_of_order` | 409 | Есть более раннее принятое управляющее сообщение без исхода. | Сначала подтвердить предыдущее. |
| `control_message_terminal` | 409 | Сообщение уже разрешено. | Не подтверждать повторно. |
| `control_message_version_conflict` | 409 | `expectedMessageVersion` не совпадает. | Перечитать сообщение. |
| `invalid_control_message` | 422 | Поле недопустимо для операции (например, `directive` вместо `reason`). | Исправить тело. |
| `invalid_control_operation` | 422 | Неизвестная операция. | `queue`, `steer`, `redirect`, `request_cancel`, `force_cancel`. |
| `invalid_control_status` | 422 | Неизвестный статус подтверждения. | `applied`, `rejected`, `superseded`. |
| `unsafe_control_payload` | 422 | Сообщение содержит абсолютные локальные пути. | Убрать пути. |

### Дочерние runs (child handles)

| Код | HTTP | Причина | Что делать |
|---|---|---|---|
| `child_depth_exceeded` | 422 | Превышена глубина вложенности child runs. | Упростить декомпозицию. |
| `child_grant_exceeded` | 403 | Run ограничен child handle, который не даёт это право. | Расширить grant при выпуске handle (в пределах родителя). |
| `child_grant_exceeds_parent` | 422 | Запрошенный grant больше потолка родителя. | Сузить grant. |
| `child_handle_expired` | 409 | Child handle истёк. | Выпустить новый. |
| `child_handle_revoked` | 409 | Child handle отозван. | Выпустить новый. |
| `child_result_too_large` | 422 | У run слишком много артефактов для результата. | Перечислить нужные в `output.artifactRefs`. |
| `child_run_already_bound` | 409 | У handle уже есть работающий run. | Дождаться завершения. |
| `invalid_cancellation_policy` | 422 | Неизвестная политика отмены. | Сверить с API. |
| `invalid_child_expiry` | 422 | `expiresInSeconds` больше предела. | Уменьшить срок. |
| `invalid_child_grant` | 422 | В grant допустимы только permissions, capabilities, skills. | Исправить grant. |
| `invalid_child_handle_ref` | 422 | Ожидался id handle или токен `ch1_…`. | Передать корректную ссылку. |
| `invalid_child_handle_token` | 422 | Токен не в формате `ch1_<id>_<secret>`. | Передать токен без изменений. |
| `invalid_child_result` | 422 | `artifactRefs` должны быть id артефактов. | Исправить результат. |
| `invalid_correlation_id` | 422 | `correlationId` не соответствует `^[A-Za-z0-9._:-]{1,128}$`. | Исправить значение. |

### Задачи, связи, комментарии, типы

| Код | HTTP | Причина | Что делать |
|---|---|---|---|
| `comment_mismatch` | 422 | Артефакт не принадлежит задаче комментария. | Сверить ссылки. |
| `dependency_cycle` | 422 | Связь создала бы цикл зависимостей. | Пересмотреть граф зависимостей. |
| `external_reference_conflict` | 409 | Внешний идентификатор уже связан с другой сущностью. | Проверить `externalSystem`/`externalId`. |
| `invalid_comment_body` | 422 | Пустой текст комментария. | Задать текст. |
| `invalid_entity_reference` | 422 | Недопустимый `entityId`. | Исправить значение. |
| `invalid_entity_type` | 422 | Неизвестный тип сущности. | Сверить с API. |
| `invalid_external_lookup` | 422 | Нужно либо `entityType`+`entityId`, либо `externalSystem`+`externalId`. | Исправить запрос. |
| `invalid_external_reference` | 422 | Недопустимая длина поля внешней ссылки. | Сократить значение. |
| `invalid_lifecycle_schema` | 422 | Жизненный цикл типа задачи некорректен. | См. `details.path`. |
| `invalid_planned_dates` | 422 | `startDate` позже `dueDate`. | Исправить даты. |
| `invalid_relation` | 422 | Связь задачи с самой собой. | Указать другую задачу. |
| `invalid_relation_type` | 422 | Неизвестный тип связи. | `parent`, `blocks`, `depends_on`, `spawned_by`, `related_to`. |
| `invalid_task_execution` | 422 | Описание `execution` задачи некорректно (skill, версия, пути входов). | См. `details`; закрепить версию skill. |
| `invalid_template` | 422 | Шаблон проекта некорректен (например, слишком много представлений по умолчанию). | Исправить шаблон. |
| `invalid_template_reference` | 422 | `templateVersion` без `templateKey`/`templateId`. | Указать шаблон. |
| `invalid_title` | 422 | Пустой заголовок задачи. | Задать `title`. |
| `invalid_transition` | 422 | Переход статуса не объявлен типом задачи. | Взять разрешённые переходы из `GET /tasks/{ref}/transitions`. |
| `not_comment_author` | 403 | Редактировать комментарий может только автор. | — |
| `relation_exists` | 409 | Такая связь уже есть. | — |
| `status_not_in_lifecycle` | 422 | Статус не объявлен жизненным циклом типа. | Использовать статусы типа. |
| `system_task_type_required` | 422 | Tenant должен сохранять активную версию системного типа задачи. | Не выводить системный тип из оборота. |
| `task_already_completed` | 409 | Задача уже завершена. | — |
| `task_cancelled` | 422 | Отменённую задачу нельзя завершить. | Создать новую задачу. |
| `template_deprecated` | 422 | Устаревший шаблон нельзя использовать для нового проекта. | Взять активную версию. |

### Цели, приёмка и evidence (work graph)

| Код | HTTP | Причина | Что делать |
|---|---|---|---|
| `duplicate_check_key` | 422 | Повтор ключа проверки в acceptance. | Сделать ключи уникальными. |
| `duplicate_evidence` | 422 | Повтор evidence. | Убрать дубль. |
| `goal_abandoned` | 422 | Работу нельзя связать с оставленной целью. | Выбрать активную цель. |
| `goal_cycle` | 422 | Новый родитель — потомок этой цели. | Выбрать другого родителя. |
| `goal_too_deep` | 422 | Иерархия целей глубже предела. | Уменьшить вложенность. |
| `goal_workspace_mismatch` | 422 | Цель задачи из другого workspace. | Перепривязать или отвязать цель. |
| `invalid_acceptance` | 422 | Некорректные критерии приёмки. | См. `details.field`. |
| `invalid_desired_state` | 422 | Некорректное желаемое состояние цели. | См. `details.field`. |
| `invalid_evidence` | 422 | Некорректное evidence. | См. `details.field`. |
| `invalid_goal_status` | 422 | Неизвестный статус цели. | Сверить с API. |
| `invalid_origin` | 422 | Некорректный `origin`. | См. `details.field`. |
| `unknown_acceptance_check` | 422 | Evidence ссылается на проверку, которой нет в acceptance. | Сверить ключи проверок. |

### Workspaces, проекты, конфигурация

| Код | HTTP | Причина | Что делать |
|---|---|---|---|
| `child_type_not_allowed` | 422 | Тип дочернего workspace не разрешён родителем. | Сверить `allowedChildTypes`. |
| `governance_not_in_settings` | 422 | Governance задаётся только версионированной ревизией конфигурации. | Использовать ревизию. |
| `governance_weakened` | 422 | Новая иерархия ослабляет governance предка. | — |
| `invalid_config` | 422 | Некорректная конфигурация проекта. | См. `details`. |
| `invalid_governance` | 422 | Некорректный раздел governance. | См. `details.path`. |
| `invalid_project_request` | 422 | Нужен `workspaceId` или `workspaceSlug`. | Исправить запрос. |
| `invalid_workspace_type` | 422 | Некорректный `allowedChildTypes`. | Ключи типов или `*`. |
| `project_archived` | 422 | Архивный проект не активирует ревизии конфигурации. | — |
| `project_exists` | 409 | У workspace уже есть project profile. | — |
| `setting_locked` | 422 | Иерархия заблокирует настройки, которые проект уже переопределяет. | Снять переопределения. |
| `system_type_immutable` | 422 | Системный тип workspace должен принимать любые дочерние типы. | — |
| `unknown_config_section` | 422 | Неизвестный раздел конфигурации. | Убрать раздел. |
| `unknown_governance_field` | 422 | Неизвестное поле governance. | Убрать поле. |
| `workspace_archived` | 422 | Архивный workspace не принимает project profile. | Разархивировать или выбрать другой. |
| `workspace_cycle` | 422 | Перемещение workspace под собственного потомка. | Выбрать другого родителя. |
| `workspace_has_active_children` | 422 | У workspace есть активные дочерние. | Архивировать или перенести дочерние. |
| `workspace_has_active_project` | 422 | На workspace активный проект. | Сначала архивировать проект. |
| `workspace_slug_conflict` | 409 | Соседний workspace с таким slug уже есть. | Выбрать другой slug. |
| `workspace_type_archived` | 422 | Тип workspace архивирован. | Выбрать активный тип. |
| `workspace_type_exists` | 409 | Тип с таким ключом уже есть. | — |
| `workspace_type_in_use` | 422 | Тип используют активные workspaces. | Перевести их на другой тип. |

### Approvals

| Код | HTTP | Причина | Что делать |
|---|---|---|---|
| `approval_already_decided` | 409 | Approval уже не в `pending`. | — |
| `approval_already_used` | 409 | Approval уже авторизовал вызов этой версии skill. | Запросить новый approval. |
| `approval_required` | 409 | Задача ждёт решения по gate approval. | Дождаться решения человека. |
| `credential_inactive` | 403 | Credential, которым принято решение, больше не активен. | Принять решение заново. |
| `invalid_action_input` | 422 | Вход действия исхода не проходит схему. | См. сообщение. |
| `invalid_approval` | 422 | Нужно ровно одно из `requiredRoleId` и `assignedPrincipalId`. | Исправить запрос. |
| `invalid_approval_schema` | 422 | Неподдерживаемое выражение в схеме исхода approval. | См. `details`. |
| `outcome_not_replayable` | 409 | Повторить можно только провалившийся или зависший исход. | — |

### Каталог, skills и вызовы

| Код | HTTP | Причина | Что делать |
|---|---|---|---|
| `capability_exists` | 409 | Capability с таким именем уже есть. | — |
| `execution_already_invoked` | 409 | Run уже сделал свой вызов исполнения. | — |
| `invalid_executor_endpoint` | 422 | Недопустимый endpoint исполнителя. | Сверить с разрешёнными origins. |
| `invalid_protocol` | 422 | Неизвестный протокол skill или исполнитель объявил недопустимый. | `http`, `local`, `mcp`. |
| `invalid_skill_contract` | 422 | Контракт skill некорректен. | См. `details.field`. |
| `invalid_skill_inputs` | 400 | Входы не соответствуют input schema skill. | Исправить `inputs`. |
| `invalid_status_transition` | 409 | Статус skill меняется только `active → deprecated → disabled`. | — |
| `invocation_mismatch` | 422 | Run не принадлежит задаче вызова. | Сверить ссылки. |
| `invocation_terminal` | 409 | Вызов уже завершён. | — |
| `role_slug_conflict` | 409 | Роль с таким slug в этом scope уже есть. | Выбрать другой slug. |
| `skill_disabled` | 422 | Нельзя назначить отключённый skill. | — |
| `skill_exists` | 409 | Skill с таким именем и версией уже есть. | Опубликовать новую версию. |
| `skill_not_invocable` | 409 | Эту версию skill ядро вызвать не может (протокол не `http`/`local`/`mcp`). | Опубликовать версию с поддерживаемым протоколом. |
| `skill_permission_denied` | 403 | У вызывающего нет прав, которых требует skill. | Выдать `requiredPermissions` skill. |
| `skill_side_effect_not_authorized` | 403 | Skill с `external_write` требует одобренного gate на задаче. | Получить approval. |
| `skill_version_immutable` | 409 | Опубликованную версию skill менять нельзя. | Опубликовать новую версию. |
| `stale_invocation_lease` | 409 | Исполнитель больше не держит аренду вызова. | Прекратить работу над вызовом. |
| `task_terminal` | 409 | Skill с `external_write` не может действовать для закрытой задачи. | — |
| `unsupported_skill_condition` | 422 | Условия skill этого вида пока не поддерживаются. | Убрать условие. |

### Поиск инструментов

| Код | HTTP | Причина | Что делать |
|---|---|---|---|
| `invalid_tool_query` | 422 | Слишком длинный запрос поиска инструментов. | Сократить. |
| `invalid_tool_schema` | 422 | Input schema инструмента должна быть объектом. | Исправить схему. |

### События и операции

| Код | HTTP | Причина | Что делать |
|---|---|---|---|
| `cursor_below_journal_floor` | 422 | Курсор старше сохранённой части журнала. | Перестроить состояние с начала доступного журнала. |
| `cursor_must_not_advance` | 422 | Rebuild может только сдвигать курсор назад. | — |
| `invalid_cursor` | 422 | Некорректный курсор событий или страницы. | Передавать курсор без изменений. |
| `retention_blocked_by_consumer` | 409 | Нет курсора потребителя: доставка не подтверждена, чистить журнал нельзя. | Дождаться потребителей. |
| `unsupported_cursor_version` | 422 | Версия курсора не поддерживается сервером. | Начать чтение заново. |

### Память и знания

| Код | HTTP | Причина | Что делать |
|---|---|---|---|
| `invalid_context_request` | 422 | Некорректный запрос контекста (например, `maxTokens ≤ 0`). | Исправить запрос. |
| `memory_disabled` | 503 | Провайдер памяти не настроен (`CP_CONTEXT_PROVIDER=none`). | Включить `http`-провайдер. |
| `memory_unavailable` | 502 | memory-service не обработал запрос (5xx, транспорт, 401/403 для identity ядра); `details.memoryStatus`, `details.retryable`. | Проверить память и credential ядра (`CP_CONTEXT_AUTH`). |
| `observation_invalid` | 422 | Наблюдение некорректно (например, `source` не по шаблону). | См. сообщение. |
| `pack_invalid` | 422 | Память отвергла манифест knowledge pack. | Исправить манифест. |
| `pack_version_conflict` | 409 | Эта версия pack уже зарегистрирована с другим содержимым. | Опубликовать новую версию. |
| `pack_version_required` | 422 | Knowledge packs включаются закреплённой ссылкой `name@version`. | Указать версию. |
| `snapshot_invalid` | 422 | Память отвергла снимок источника. | Исправить снимок. |
| `snapshot_stale` | 409 | В памяти уже более новый снимок этого источника. | Отправить актуальный снимок. |
| `workspace_not_root` | 422 | Knowledge packs задаются на корневом workspace дерева. | Указать корневой workspace. |
### Коды клиентской библиотеки и CLI

Эти коды порождает не сервер, а `control_plane_client` (его используют
runner, CLI, MCP-сервер, коннекторы) до или вместо обращения к серверу.
Они приходят как `ControlPlaneError.code`.

| Код | Причина | Что делать |
|---|---|---|
| `transport_error` | Сетевая ошибка: запрос мог выполниться, а мог и нет. | Повторять только с тем же `Idempotency-Key` (клиент делает это сам для идемпотентных команд). |
| `iam_url_required` | Не задан `CONTROL_PLANE_IAM_URL` при явном создании IAM-credential. | Задать адрес IAM. |
| `iam_tenant_required` | Задан `CONTROL_PLANE_IAM_URL`, но не `CONTROL_PLANE_IAM_TENANT`. | Задать tenant. |
| `iam_unreachable` | IAM недоступен при обмене PAT. | Проверить сеть и адрес IAM. |
| `iam_invalid_token` | IAM отверг PAT (401): отозван, истёк, неизвестен. | Перевыпустить PAT (`iam auth login` или выпуск администратором). |
| `iam_audience_not_allowed` | IAM ответил 403 на обмен: audience или scope вне потолка PAT. | Сверить audiences и `scopeCeiling` PAT с `CONTROL_PLANE_IAM_AUDIENCE`/`…_SCOPES`. |
| `iam_exchange_failed` | Иной отказ IAM при обмене (≥ 400). | Смотреть лог IAM. |
| `iam_exchange_malformed` | Ответ обмена без `accessToken`/`expiresIn` или с пустым токеном. | Проверить версию IAM. |
| `iam_not_authenticated` | На машине нет PAT для этой пары IAM URL + tenant (или явно переданный PAT пуст). | Выполнить вход или положить PAT в хранилище. |
| `iam_credential_ambiguous` | В хранилище несколько credential для одной пары IAM URL + tenant, а процесс не объявил себя. | Задать `IAM_PRINCIPAL=<principal-id>` для процесса. |
| `iam_environment_mode_required` | `IAM_PLATFORM_ACCESS_TOKEN` задан без `IAM_CREDENTIAL_MODE=environment` (или `ci`). | Добавить режим — унаследованная переменная не должна молча подменять учётку. |
| `iam_credentials_file_permissions` | `~/.config/iam/credentials.json` доступен не только владельцу. | `chmod 600`. |
| `iam_credentials_file_unreadable` | Файл credentials не читается или не JSON. | Восстановить файл. |
| `not_configured` | MCP-сервер: нет `CONTROL_PLANE_SERVER` и `.control-plane/config.json`. | Задать сервер. |
| `not_authenticated` | MCP-сервер: нет ни IAM-identity, ни legacy-ключа. | Настроить IAM (`iam auth login`). |
| `invalid_harness_configuration` | `CONTROL_PLANE_HARNESS_TYPE` не в формате идентификатора. | Исправить значение. |

Клиент отображает коды сервера на типизированные исключения:
`stale_claim` → `StaleClaimError`; `task_already_claimed`, `task_claimed`,
`claim_not_expired` → `ClaimConflictError`; `task_not_ready` →
`TaskNotReadyError`; `approval_required` → `ApprovalRequiredError`;
`not_eligible` → `NotEligibleError`; `session_expired`,
`session_not_active` → `SessionExpiredError`; `version_conflict` →
`VersionConflictError`; `idempotency_key_reused`, `idempotency_in_flight` →
`IdempotencyConflictError`; `budget_exceeded` → `BudgetExceededError`;
`run_not_active` → `RunNotActiveError`; `task_cancelled` →
`CancelledError`; `invalid_credentials` → `AuthenticationError`;
`permission_denied` → `PermissionDeniedError`; `not_found` →
`NotFoundError`. Остальные — по HTTP-статусу.

## iam-service

Ответ — `{"detail": "<code>"}`.

### Токены и обмен

| Код | HTTP | Эндпоинт | Причина | Что делать |
|---|---|---|---|---|
| `invalid_token` | 401 | PAT: `…:exchange`, introspect, self-revoke | PAT неизвестен, неверный секрет, отозван, истёк; неактивны tenant, membership или principal. Точная причина — в audit. | Перевыпустить PAT; проверить статус principal. |
| `audience_not_allowed` | 403 | обмен PAT, client credentials, федерация | Audience нет в списке credential или он не активен в tenant. | Выпустить PAT на нужный audience; завести audience в IAM. |
| `scope_not_allowed` | 403 | обмен | Запрошенные scopes вне потолка credential или `allowedScopes` audience. Частая причина — scope без префикса (`read` вместо `control-plane:read`). | Запрашивать scopes с префиксом audience в пределах потолка. |
| `invalid_client` | 401 | `POST /api/v1/tokens/exchange` | Неизвестный или отозванный client, неверный секрет, неактивны membership/principal. | Перевыпустить service account. |
| `human_principal_required` | 422 | федерация, authentication context, выпуск PAT человеком | Операция доступна только principal вида `human`. | — |

### Выпуск и управление PAT

| Код | HTTP | Причина | Что делать |
|---|---|---|---|
| `idempotency_key_required` | 400 | Выпуск PAT без заголовка `Idempotency-Key`. | Передать уникальный ключ. |
| `authentication_context_required` | 403 | Для человека нет authentication context. | Создать контекст (`POST …/principals/{id}/authentication-contexts`) и сразу выпускать. |
| `authentication_context_expired` | 403 | Контекст старше `IAM_PAT_MAX_AUTHENTICATION_AGE_SECONDS` (300 с). | Создать свежий контекст. |
| `principal_kind_not_allowed` | 422 | PAT выпускается только `human` и `agent`; `service_account` — нет. | Для сервисов использовать client credentials; сервисный агент заводить видом `agent`. |
| `invalid_scope_ceiling` | 422 | Потолок PAT шире `allowedScopes` его audiences. | Сузить `scopeCeiling`. |
| `expiry_too_long` | 422 | Срок больше `IAM_PAT_MAX_TTL_SECONDS` (365 дней). | Уменьшить `expiresInSeconds`. |
| `unknown_audience` | 422 | Audience PAT (или service account) не зарегистрирован и не активен в tenant. | Завести audience. |
| `principal_not_found` | 404 | Нет такого principal. | — |
| `principal_not_active` | 409 | Principal не активен. | Активировать. |
| `credential_not_found` | 404 | Нет credential для ротации/отзыва. | — |
| `credential_not_active` | 409 | Ротация отозванного или истёкшего PAT. | Выпустить новый — ротация срок не продлевает. |
| `credential_conflict` | 409 | Параллельная запись того же credential. | Повторить с тем же `Idempotency-Key`. |
| `credential_exists` | 409 | Перенос legacy-ключа, который уже перенесён. | — |
| `invalid_credential_material` | 422 | Перенос legacy-ключа: неверный префикс или хэш. | — |
| `compatibility_window_too_long` | 422 | Окно перенесённого legacy-ключа больше `IAM_LEGACY_CREDENTIAL_MAX_TTL_SECONDS`. | Уменьшить срок. |

### Администрирование tenant

| Код | HTTP | Причина |
|---|---|---|
| `unauthorized` | 401 | Bootstrap-эндпоинт без верного `X-IAM-Bootstrap-Token` (заголовок `Authorization: Bearer` не подходит). |
| `tenant_not_found` | 404 | Нет tenant. |
| `tenant_id_exists` | 409 | Tenant с переданным `id` уже есть. |
| `tenant_slug_exists` | 409 | Tenant с таким slug уже есть. |
| `audience_exists` | 409 | Audience уже заведён. |
| `audience_not_found` | 404 | Нет audience (PATCH). |
| `invalid_scope` | 422 | Пустой scope или длиннее 120 символов в `allowedScopes` audience. |
| `service_account_not_found` | 404 | Нет service account. |
| `group_not_found`, `group_exists`, `group_membership_exists` | 404, 409, 409 | Группы. |
| `group_is_federated` | 409 | Группа управляется федерацией. |
| `identity_provider_not_found`, `identity_provider_exists` | 404, 409 | Identity provider. |
| `identity_provider_managed` | 409 | Внешнюю identity нельзя привязать вручную: её issuer обслуживает активный provider с профилем `read_only`. |
| `invalid_issuer` | 422 | Недопустимый issuer provider. |
| `external_identity_exists` | 409 | Внешняя identity уже привязана. |
| `service_account_required`, `service_principal_required` | 422 | SCIM-источник должен быть service account. |
| `provisioning_source_exists` | 409 | SCIM-источник уже заведён. |
| `population_managed_by_directory` | 409 | Популяцией principals управляет каталог (SCIM). |

### Отключение и включение людей { #iam-people }

`POST /api/v1/tenants/{tenant_id}/principals/{principal_id}:disable` и `:enable` (scope
`iam:people`).

| Код | HTTP | Причина |
|---|---|---|
| `human_principal_required` | 422 | По `iam:people` отключают и включают только людей. |
| `self_disable_forbidden`, `self_enable_forbidden` | 409 | Попытка отключить или включить себя. |
| `people_admin_protected` | 403 | `:disable`: цель — член группы `people-admins`; отключает её только bootstrap IAM, членство вызывающего не учитывается. `:enable`: цель входит в группу привилегий IAM (например, `people-admins`), в которой вызывающий не состоит; включает член той же группы или bootstrap IAM. |
| `principal_paused` | 409 | `:enable`: principal приостановлен другим процессом; `:enable` это не снимает. |
| `principal_provisioned` | 409 | `:enable`: человека отключил источник SCIM; включает его он же (`active: true`). |
| `principal_status_not_enableable` | 409 | `:enable`: из этого статуса не включают. |
| `principal_conflict` | 409 | `:enable`: статус principal'а изменился параллельно; перечитать и повторить. |
| `idempotency_key_required` | 400 | `:enable` токеном без заголовка `Idempotency-Key` (bootstrap-токену ключ не обязателен). |
| `idempotency_key_reused` | 409 | `:enable`: этот `Idempotency-Key` вызывающий уже использовал для другого principal'а. |

### Федерация identity

| Код | HTTP | Причина |
|---|---|---|
| `invalid_token`, `invalid_signature`, `token_expired`, `invalid_issuer`, `invalid_audience`, `unknown_signing_key`, `unsupported_algorithm`, `missing_subject_claim` | 401 | Токен upstream-провайдера (внешнего IdP) не прошёл проверку. |
| `step_up_required` | 403 | Требуется более сильная аутентификация (`acr`/`amr`). |
| `identity_disabled`, `principal_disabled`, `principal_not_in_tenant` | 403 | Внешняя identity или principal отключены либо не в tenant. |
| `external_identity_conflict` | 409 | Конфликт привязки внешней identity. |
| `identity_provider_unavailable` | 503 | JWKS провайдера недоступен. |

### SCIM

SCIM-эндпоинты отвечают в формате SCIM (`scimType`): `invalidFilter`,
`invalidValue`, `invalidSyntax`, `uniqueness` (400/404/409), 412 при
несовпадении `If-Match`, 401 без токена или с токеном не для
`IAM_SCIM_AUDIENCE`, 403 без scope `IAM_SCIM_SCOPE` или без активного
источника provisioning, 502/503 при недоступности upstream-провайдера.


## Коды platform-auth-sdk (resource services)

Общий deny-контракт всех resource services, использующих SDK. Клиенту
уходит только код; Control Plane переносит коды SDK в свой конверт как
есть (кроме `invalid_token`, который становится `invalid_credentials`).

| Код | HTTP | Причина |
|---|---|---|
| `invalid_token` | 401 | Любой дефект токена (включая отзыв). |
| `insufficient_scope` | 403 | Scope токена не покрывает операцию. |
| `not_entitled` | 403 | Нет лицензии на продукт или feature. |
| `permission_denied` | 403 | Доменная политика не даёт операцию. |
| `verification_unavailable` | 503 | Нечем проверить токен (нет ключей, JWKS устарел, источник отзыва недоступен). |
| `entitlement_unavailable` | 503 | Нет решения entitlement, кэш устарел. |
| `authorization_unavailable` | 503 | Нет решения внешнего PDP. |
| `denied` | 403 | Базовый отказ без уточнения. |

### Причины в audit {#audit-reasons}

Эти строки клиенту не отдаются — их видно в audit и логе resource
service. По ним разбирается `401 invalid_credentials` / `invalid_token`.

| Причина | Откуда | Значение |
|---|---|---|
| `missing_authorization`, `malformed_authorization`, `missing_token` | SDK | Нет заголовка `Authorization: Bearer …` или он битый. |
| `malformed_token`, `unsupported_algorithm`, `invalid_token` | SDK | Токен не разбирается или подпись неверна. |
| `expired` | SDK | Истёк `exp`. |
| `issuer_mismatch` | SDK | `iss` не равен ожидаемому issuer (например, после смены `TAIMEN_PUBLIC_URL`). |
| `audience_mismatch`, `audience_not_exact` | SDK | Токен выпущен на другой audience или `aud` — список. |
| `missing_required_claim`, `missing_exp`, `missing_credential_id` | SDK | Нет обязательного claim. |
| `unknown_key_id` | SDK | `kid` не найден в JWKS (ротация ключа IAM). |
| `jwks_stale`, `public_key_not_configured`, `verifier_not_configured` | SDK | Нечем проверять (→ `verification_unavailable`). |
| `revocation_source_unavailable` | SDK | Источник отзыва недоступен вне stale-окна. |
| `credential_revoked` | SDK, IAM | Credential отозван. |
| `token_ttl_exceeds_revocation_window` | SDK | Токен живёт дольше допустимого окна отзыва. |
| `service_credentials_not_configured`, `service_token_exchange_failed`, `service_token_malformed` | SDK | Собственный service account сервиса не настроен или обмен не удался. |
| `quota_reserve_unavailable` | SDK | Резерв квоты entitlement недоступен. |
| `binding_not_found` | Control Plane | Нет строки `iam_principal_bindings` для пары (issuer, IAM principal). |
| `binding_disabled` | Control Plane | Binding отключён или отозван. |
| `credential_expired`, `tenant_not_active`, `membership_not_active`, `principal_not_active` | IAM | Причины отказа обмена PAT. |

## memory-service

Ответы — `{"detail": "<текст на русском>"}`; машинных кодов нет,
ориентируйтесь на статус.

| HTTP | Когда |
|---|---|
| 400 | Некорректный запрос: namespace в query и в теле различаются, `namespace` и `scope.namespace` задают разные базы, неверный фильтр; база знаний не разрешена в Console. |
| 401 | Нет или неверный Bearer (`Требуется корректный Authorization: Bearer <key>`). |
| 403 | Нет прав на namespace (чтение/запись); нет прав на глобальную статистику; нужен service scope (`memory:service`) для пакетов видов; маршрут доступен только identity ядра (`CB_CORE_ONLY`/`CB_CORE_IDENTITIES`); namespace вне видимости principal (policy); cross-origin запрос в Console. |
| 404 | Узел, источник, наблюдение или трейс не найдены. |
| 409 | Конфликт (например, снимок источника старее сохранённого). |
| 413 | Пачка наблюдений больше `CB_OBSERVATIONS_MAX_BATCH`. |
| 429 | Лимит запросов демо-витрины. |
| 500 | Внутренняя ошибка движка. |
| 503 | БД недоступна; проверка IAM-токена недоступна (JWKS/конфигурация IAM); внешний PDP видимости (если включён) недоступен — видимость не определена. |

Control Plane переводит ответы памяти в свои коды: `memory_unavailable`
(502), `snapshot_invalid`, `snapshot_stale`, `pack_invalid`,
`pack_version_conflict`.

## См. также

- [Аутентификация и доступ — диагностика](../troubleshooting/auth.md)
- [Исполнение и runner — диагностика](../troubleshooting/runner.md)
- [Исполнение — claims и runs](../control-plane/execution.md)
- [Права и scopes](permissions.md)
- [Credentials и PAT](../iam/credentials.md)
- [API Control Plane](../control-plane/api.md)
