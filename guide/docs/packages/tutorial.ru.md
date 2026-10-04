# Пример: претензии клиентов

Сквозной пример пакета не из разработки — «претензии клиентов» — шаг за шагом:
манифест и онтология, работа людей, скиллы, процесс, правило, наблюдатель, агенты,
уведомление, тесты и установка. Каждый шаг заканчивается проверкой, и каждый шаг
разумно делать отдельным коммитом. Страница для автора, который прошёл [Пакет за 10
минут](quickstart.md) и собирает первую настоящую вертикаль.

Готовый пакет лежит в репозитории `package-sdk`, каталог `examples/claims/`, и
проверяется его CI: вся пирамида в песочнице на каждом изменении. Ядро о претензиях
ничего не знает — всё предметное здесь данные пакета и код его интеграции.

## Что строим

Клиент подаёт претензию в хелпдеске. Наблюдатель интеграции превращает новый тикет в
наблюдение, наблюдение открывает дело: скилл классифицирует претензию, таблица
решений выбирает, кто её разбирает, человек решает и пишет ответ, крупный возврат
согласует руководитель (но не тот, кто разбирал), а ответ уходит в хелпдеск только
после решения человека. Тикет, переоткрытый после закрытия дела, — разовая работа:
её заводит правило.

```mermaid
flowchart LR
    H["Хелпдеск"] -->|"новый тикет"| O["helpdesk-observer"]
    O -->|"helpdesk.ticket_created"| P["Процесс claim"]
    P -->|"claims.classify@1"| S["claims-skills"]
    P -->|"таблица claim-route"| R["Задача разбора<br/>(officer или manager)"]
    R -->|"возврат выше порога"| A["Согласование руководителя<br/>(не того, кто разбирал)"]
    R --> Y["Задача ответа"]
    A --> Y
    Y -->|"одобренный гейт: helpdesk.reply@1"| S
    S -->|"ответ, тикет закрыт"| H
    H -->|"переоткрыт"| O
    O -->|"helpdesk.ticket_reopened"| W["Правило claim-reopened<br/>→ задача follow-up"]
```

```text
examples/claims/
├── packages.yaml                  установка: пакет и онтологии пространства работы
└── claims/                        пакет
    ├── package.yaml               манифест: переменные, совместимость, онтологии
    ├── knowledge-packs/claims.yaml
    ├── roles/                     claims-officer, claims-manager
    ├── task-types/                claim-review, claim-reply, claim-followup
    ├── skills/                    выгрузка контрактов из кода интеграции
    ├── processes/claim.yaml       дело: intake → review → reply
    ├── rules/claim-reopened.yaml
    ├── agents/                    наблюдатель, хост скиллов, личности процесса и правила
    ├── notification-rules/claim-reply-approval.yaml
    ├── tests/                     сценарии процесса, правила и типа задачи
    ├── integration/               наблюдатель и скиллы с unit-тестами
    └── Dockerfile, Dockerfile.skills
```

## 1. Заготовка и манифест { #init }

```bash
package-sdk init claims --display-name "Customer claims" --license Apache-2.0 \
    --integration --image
cd claims
```

Заготовка даёт манифест, процесс-пример с личностью и ролью владельца, код
наблюдателя в `integration/`, его агента и `Dockerfile`. Пример выбрал свои имена:
процесс `claim`, роли `claims-officer` и `claims-manager`, модуль интеграции
`claims_helpdesk`, агент `helpdesk-observer`. Пакет ещё нигде не стоит, поэтому
лишние файлы заготовки просто удалите или переименуйте вместе с ключами.
`package-sdk edit rename --package …` нужен для уже установленного объекта: он
дописывает `renames` в манифест, чтобы план перенёс объект, а не создал новый.

Манифест объявляет всё, что зависит от стенда, переменными:

```yaml
apiVersion: taimen.ai/v1
kind: Package
key: claims
spec:
  version: 0.1.0
  displayName: Customer claims
  license: Apache-2.0
  engines:
    control-plane: ">=0.10,<0.11"
  knowledge: ["default@1", "claims@1"]
  variables:
    CLAIMS_WORKSPACE_ID:
      kind: workspace
      description: Root workspace of the claims — the cases, their tasks and the observations of the helpdesk
    CLAIMS_REFUND_THRESHOLD:
      kind: integer
      description: A refund above this amount needs the approval of a claims manager
      default: "500"
    HELPDESK_URL:
      kind: url
      description: API of the helpdesk the observer polls
      example: http://helpdesk:8080
```

Проверка — `package-sdk check --package .`. Пока переменную не использует ни
один объект, `check` показывает ошибку `variable_unused`: переменные объявляют
вместе с первым объектом, который их использует (здесь — процесс на шаге 5 и
агенты на шаге 9).

## 2. Онтология { #ontology }

Дело проецируется в базу знаний: претензия, клиент, продукт, решение. Клиент
(организация), продукт и решение — виды онтологии платформы `default@1`; пакет
добавляет только претензию и её связи.

```yaml
apiVersion: taimen.ai/v1
kind: KnowledgePack
key: claims
spec:
  name: claims
  version: 1
  extends: ["default@1"]
  kinds:
    - kind: claim
      title: Claim
      naturalKey: "claim:<ticketId>"
      attributes:
        type: object
        properties:
          subject: {type: string, maxLength: 300, title: Subject}
          category: {type: string, enum: [defect, delivery, billing, other], title: Category}
          severity: {type: string, enum: [low, medium, high], title: Severity}
          resolution: {type: string, enum: [refund, replacement, rejection], title: Resolution}
          refundAmount: {type: number, minimum: 0, title: Refund}
      searchable: {fields: [subject]}
  relations:
    - {relation: filed_by, title: Filed by, fromKinds: [claim], toKinds: [legal_entity], cardinality: one}
    - {relation: concerns, title: Concerns, fromKinds: [claim], toKinds: [product]}
    - {relation: resolved_by, title: Resolved by, fromKinds: [claim], toKinds: [decision], cardinality: one}
```

Заготовка — `package-sdk add knowledge-pack claims`. Подробно — в [Знаниях и
онтологии](knowledge.md).

## 3. Работа людей { #work }

Две роли и три типа задач:

| Объект | Зачем |
|---|---|
| `Role` `claims-officer` | разбирает претензии и пишет ответы, получает follow-up |
| `Role` `claims-manager` | владелец процесса; разбирает серьёзные и платёжные претензии, согласует крупные возвраты |
| `TaskType` `claim-review` | задача шага разбора: поля `resolution`, `refundAmount`, `reply` — результат шага |
| `TaskType` `claim-reply` | ответ клиенту: уходит в хелпдеск только по одобренному гейту |
| `TaskType` `claim-followup` | разовая работа по переоткрытому тикету |

Главное — `claim-reply`. Ответ клиенту — запись во внешнюю систему от имени
организации, поэтому её делает исход решения человека, а не исполнитель:

```yaml
apiVersion: taimen.ai/v1
kind: TaskType
key: claim-reply
spec:
  displayName: Reply to the customer
  instructions: |-
    Put the ticket id into `ticketId` and the final text into `message`, then ask for
    an approval of the task: the reply is sent when the approval is granted.
  fieldSchema:
    type: object
    properties:
      ticketId: {type: string, title: Ticket}
      message: {type: string, minLength: 1, maxLength: 4000, title: Reply}
      replyId: {type: string, title: Reply in the helpdesk}
  lifecycleSchema:
    statuses:
      - {key: draft, category: active, displayName: Draft}
      - {key: sent, category: terminal_success, displayName: Sent}
      - {key: dropped, category: terminal_cancelled, displayName: Dropped}
    transitions:
      - {from: draft, to: [sent, dropped]}
    initialStatus: draft
    completionStatus: sent
  approvalSchema:
    gates:
      default:
        outcomes:
          approved:
            - invokeSkill:
                skill: helpdesk.reply@1
                inputs:
                  ticketId: $.task.customFields.ticketId!
                  message: $.task.customFields.message!
                onSuccess:
                  - completeTask: {}
                onFailure:
                  - comment: {body: "The reply to ticket $.task.customFields.ticketId was not sent: the helpdesk refused it"}
          rejected:
            - comment: {body: "The reply to ticket $.task.customFields.ticketId was rejected: $.approval.comment"}
```

Заготовки — `package-sdk add role …`, `package-sdk add task-type …`. Поля
типов задач — в [Работе](work.md). `check` сейчас скажет, что скилла
`helpdesk.reply@1` нет, — он появится на следующем шаге.

## 4. Скиллы в коде { #skills }

Скиллы пишутся кодом на skill-sdk в `integration/src/claims_helpdesk/skills.py`;
YAML в `skills/` — выгрузка, руками его не правят.

```python
@skill("claims.classify", version="1", side_effects="none", risk="low", timeout=120)
async def classify(inputs: ClaimText, ctx: SkillContext) -> Classification:
    """The category and the severity of a customer claim, by its subject and text."""
    answer = await ctx.llm.chat_json(
        system_prompt=CLASSIFY_PROMPT,
        messages=[{"role": "user", "content": f"Subject: {inputs.subject}\n\n{inputs.text}"}],
        response_model=Classification,
        schema_name="classification",
    )
    return answer.data


@skill("helpdesk.reply", version="1", side_effects="external_write", risk="medium",
       idempotency="required", timeout=60, retry=(3, 10))
def reply(inputs: Reply, ctx: SkillContext) -> Replied:
    """Reply to a helpdesk ticket on behalf of the organization and close it."""
    base_url = ctx.config("HELPDESK_URL")
    ...
    answer = post_reply(base_url, ctx.secret("helpdesk-token"), ticket_id=inputs.ticketId,
                        message=inputs.message, close=inputs.close, key=ctx.idempotency_key)
    return Replied(replyId=str(answer["replyId"]), status=str(answer["status"]))
```

- `claims.classify@1` ничего не пишет — его можно звать из процесса и правила.
- `helpdesk.reply@1` — `external_write`: ядро исполняет его только по одобренному
  гейту задачи `claim-reply`. Ключ идемпотентности вызова уходит в хелпдеск: повтор
  не даёт второго ответа.
- Адрес хелпдеска — параметр хоста `ctx.config`, токен — секрет узла `ctx.secret`;
  в пакете их значений нет.

Выгрузка контрактов и unit-тесты. `skill-sdk` и `pytest` живут в окружении
инструмента `package-sdk` (дополнение `skills`, `--with pytest`), а не на `PATH`,
и код интеграции лежит в `integration/src` — поэтому команды вызываются из
окружения инструмента с `PYTHONPATH=src`:

```bash
cd integration
TOOL="$(uv tool dir)/package-sdk/bin"                 # окружение инструмента
PYTHONPATH=src "$TOOL/skill-sdk" export --package .. claims_helpdesk.skills
PYTHONPATH=src "$TOOL/python" -m pytest -q tests/test_skills.py
cd ..
```

`package-sdk test` делает то же сам — ступенями контрактов и кода интеграции, —
так что ручной запуск нужен, только чтобы записать YAML или прогнать тесты
отдельно (см. [Тесты пакета](testing.md#integration-code)).

```python
def test_the_claim_is_classified_by_the_model() -> None:
    llm = FakeLlm([{"category": "defect", "severity": "high", "confidence": 0.93}])
    result = invoke(skills.classify,
                    {"subject": "Sparks from the heater", "text": "It sparked and smells of smoke."},
                    llm=llm)
    assert result.outputs == {"category": "defect", "severity": "high", "confidence": 0.93}
```

Подробно — в [Скиллах пакета](skills.md).

## 5. Процесс { #process }

Процесс `claim` открывает одно дело на тикет, ведёт его по трём стадиям и
проецирует в базу знаний. Фрагменты:

```yaml
spec:
  version: 1
  workspaceId: ${CLAIMS_WORKSPACE_ID}
  identity: {agent: claims-process}
  owner: [{role: claims-manager}]
  start:
    "on": {observation: helpdesk.ticket_created}
    key: "'claim:' + string(event.payload.data.ticketId)"   # одно дело на тикет
    set:
      ticketId: string(event.payload.data.ticketId)
      subject: string(event.payload.data.subject)
      # …
  memory:
    case: {kind: claim, key: "'claim:' + data.ticketId", title: "data.ticketId + ': ' + data.subject"}
    entities:
      - {kind: legal_entity, key: data.customerId, name: data.customerName, rel: filed_by}
      - {kind: product, key: data.product, name: data.product, rel: concerns}
  decisions:
    - id: claim-route
      hitPolicy: first
      inputs:
        - {id: severity, expr: data.severity, type: string}
        - {id: category, expr: data.category, type: string}
      outputs: [{id: role, type: string}, {id: note, type: string}]
      rules:
        - when: {severity: high, category: "-"}
          then: {role: claims-manager, note: "High severity: a manager reviews it"}
        - when: {severity: "-", category: billing}
          then: {role: claims-manager, note: "Billing: a manager reviews it"}
        - when: {severity: "-", category: "-"}
          then: {role: claims-officer, note: "Standard handling"}
  stages:
    - id: intake
      steps:
        - id: classify
          call: {skill: claims.classify@1, input: {subject: data.subject, text: data.text}, timeout: PT10M}
          output: {as: {category: step.result.category, severity: step.result.severity}}
        - id: route
          decide: {table: claim-route}
          output: {as: {reviewRole: step.result.role, routeNote: step.result.note}}
    - id: review
      entry: stage.intake.completed
      steps:
        - id: review-claim
          human: {taskType: claim-review, assign: [{expr: "'role:' + data.reviewRole"}], due: P2D, …}
          output:
            as:
              resolution: step.result.resolution
              refundAmount: double(step.result.refundAmount)
              reply: step.result.reply
              reviewedBy: string(task.assigneeId)       # кто разбирал: исполнитель задачи шага
        - id: approve-refund
          when: data.resolution == 'refund' && data.refundAmount > double(${CLAIMS_REFUND_THRESHOLD})
          approve:
            approvers: [{role: claims-manager}]
            quorum: any                                  # обязательно: умолчания нет
            separationOfDuties: "[data.reviewedBy]"     # разбиравший не согласует
            due: P2D
            escalations: [{after: due, action: remind}]
    - id: reply
      entry: stage.review.completed
      steps:
        - id: send-reply
          human: {taskType: claim-reply, …}
        - id: remember-decision
          remember: {facts: {resolution: data.resolution, refundAmount: data.refundAmount}}
        - id: close-refunded
          when: data.resolution == 'refund'
          complete: {outcome: refunded}
        # …
```

Сценарий на каждую ветку — до того, как процесс написан до конца: мелкий возврат,
крупный возврат с разделением обязанностей и напоминанием по сроку, отказ в
возврате, серьёзная и платёжная претензии. Фрагмент сценария крупного возврата:

```yaml
process: claim
name: a large refund is approved by a manager who did not review the claim
given:
  principals:
    claims-officer: [alice]
    claims-manager: [alice, bob]
mocks:
  skills:
    claims.classify@1:
      - output: {category: defect, severity: medium, confidence: 0.8}
steps:
  - emit:
      observation: helpdesk.ticket_created
      payload:
        data: {ticketId: T-1002, customerId: C-8, customerName: Contoso, product: Espresso Pro,
               subject: Broken pump, text: The pump leaks., amount: 1400, currency: EUR}
  - complete:
      step: review-claim
      by: alice
      output: {resolution: refund, refundAmount: 1400, reply: We refund the machine.}
  - advance: P2DT1H
  - expect: {events: [process.escalated], stages: {review: open}}
  - approve: {step: approve-refund, by: alice, decision: approve, expectRefused: separation_of_duties_violation}
  - approve: {step: approve-refund, by: bob, decision: approve}
  - expect:
      data: {approval: approved, approvedBy: [bob]}
      stages: {review: completed, reply: open}
```

```bash
package-sdk test . --test claim-large-refund
```

Язык процессов — в разделе [Процессы](../processes/index.md), формат сценариев — в
[Сценариях и плане ядра](../processes/package-tests.md).

## 6. Правило { #rule }

Переоткрытый тикет закрытого дела — не новое дело, а разовая работа. Это правило, а
не процесс (см. [Правило или процесс](rules.md#rule-or-process)):

```yaml
apiVersion: taimen.ai/v1
kind: WorkRule
key: claim-reopened
spec:
  identity: {agent: claims-rules}
  workspaceId: ${CLAIMS_WORKSPACE_ID}
  trigger: {kind: observation, type: helpdesk.ticket_reopened}
  condition:
    and:
      - {exists: payload.data.ticketId}
      - {ne: [{var: payload.data.channel}, internal]}
  interpretation:
    skill: claims.classify@1
    inputs: {subject: "{{payload.data.subject}}", text: "{{payload.data.text}}"}
  action:
    kind: ensure_work
    taskType: claim-followup
    dedupKeyTemplate: "claim-reopened:{{payload.data.ticketId}}"   # один follow-up на тикет
    fields:
      title: "Follow up reopened claim {{payload.data.ticketId}}"
      assignee: "role:claims-officer"
      customFields:
        ticketId: "{{payload.data.ticketId}}"
        category: "{{skill.output.category}}"
        severity: "{{skill.output.severity}}"
```

Сценарии правила — на каждую ветку условия и каждый исход: переоткрытый тикет,
внутренний тикет, наблюдение без тикета, модель не смогла классифицировать. Им
нужна база песочницы:

```bash
export PACKAGE_SDK_SANDBOX_DATABASE_URL=postgresql://postgres:sandbox@127.0.0.1:55432/postgres
package-sdk test . --test claim-reopened
```

Подробно — в [Правилах в пакете](rules.md).

## 7. Тип задачи с внешней записью { #task-type-tests }

Гейт `claim-reply` проверяется сценарием типа задачи: одобрение отправляет ответ и
завершает задачу, отказ хелпдеска оставляет её открытой, отклонение — черновиком.

```yaml
subject: taskType
taskType: claim-reply
name: a reply the helpdesk refuses leaves the task open
given:
  task:
    assignee: alice
    customFields: {ticketId: T-9999, message: We refund it.}
  principals: {claims-officer: [alice, bob]}
mocks:
  skills:
    helpdesk.reply@1:
      - error: {type: helpdesk_refused, detail: no such ticket}
steps:
  - approve: {decision: approved, by: bob}
  - expect:
      invokeSkill:
        - {skill: helpdesk.reply@1, inputs: {ticketId: T-9999}}
      status: {category: active}
```

## 8. Наблюдатель { #observer }

Наблюдатель опрашивает хелпдеск по курсору и пишет в ядро два вида фактов:

```python
@observer(kind="helpdesk-observer", entrypoint="claims_helpdesk.observer:observe")
def observe(ctx: ObserveContext) -> None:
    base_url = str(ctx.config["baseUrl"])
    token = ctx.secret("helpdesk-token")      # файл секрета узла, читается каждый цикл
    cursor = int(ctx.state.get("cursor", 0))
    for ticket in fetch(base_url, token, since=cursor, limit=int(ctx.config.get("pageSize") or 50)):
        kind = kind_of(ticket)                # helpdesk.ticket_created | helpdesk.ticket_reopened | None
        if kind is not None:
            ctx.emit(Observation(
                kind=kind,
                dedup_key=f"helpdesk:{ticket['id']}:{ticket['version']}",   # тикет и его версия
                data=data_of(ticket),
                external_ref={"system": "helpdesk", "id": str(ticket["id"]), "url": …},
            ))
        cursor = max(cursor, int(ticket["seq"]))
    ctx.state["cursor"] = cursor              # сохраняется только после цикла без ошибок
```

Тесты без стенда — `package_sdk.connector.testing`: новый тикет открывает дело,
ответы пропускаются, повтор цикла не даёт второго факта, сбой публикации не
сдвигает курсор, без токена цикл пропускается с `connector.secret_missing`.

```python
def test_a_repeated_cycle_is_not_a_second_fact(helpdesk: Helpdesk) -> None:
    helpdesk.changed.append(ticket("T-1001", version=1, seq=1, status="open"))
    core = FakeCore()
    run_once(observer.observe, config=CONFIG, secrets=SECRETS, core=core)
    run_once(observer.observe, config=CONFIG, secrets=SECRETS, core=core)
    assert len(core.observations) == 1
```

Подробно — в [Интеграциях](integrations.md#observer).

## 9. Агенты { #agents }

Четыре агента — по одному на роль в пакете:

| Агент | Роль | Права |
|---|---|---|
| `claims-process` | личность процесса, `placement: none` | `events.read`, `tasks.read`, `tasks.write`, `approvals.manage`, `skills.invoke`, `observations.write` |
| `claims-rules` | личность правила, `placement: none` | `events.read`, `tasks.read`, `tasks.write`, `skills.invoke` |
| `claims-skills` | хост скиллов, `executor.kind: skills` | `sessions.open`, `tasks.read`, `skills.execute` |
| `helpdesk-observer` | наблюдатель, `executor.kind: observer` | `observations.write` |

```yaml
apiVersion: taimen.ai/v1
kind: Agent
key: claims-skills
spec:
  displayName: Claims skills
  identity:
    kind: agent
    permissions: [sessions.open, tasks.read, skills.execute]
  executor:
    kind: skills
    image: registry.example.com/claims/claims-skills:0.1.0
  skills:
    protocols: [local]
    local: [claims_helpdesk.skills]
    concurrency: 2
  placement:
    requires: [helpdesk-access]
    secrets: [helpdesk-token]
    resources: {cpus: 1, memoryMb: 512}
  state: running
```

Хост скиллов и наблюдатель получают токен хелпдеска одним именем секрета узла
`helpdesk-token`; адрес хелпдеска наблюдатель берёт из `config` (переменная
`${HELPDESK_URL}`), хост скиллов — из своего окружения: объявить параметр хоста
скиллов в пакете пока нечем, его задаёт установка на узле, а пакет называет в
README. Подробно — в [Агентах пакета](agents.md).

## 10. Уведомление { #notification }

Ответ клиенту ждёт решения — назначенный получает уведомление с кнопками:

```yaml
apiVersion: taimen.ai/v1
kind: NotificationRule
key: claim-reply-approval
spec:
  "on":
    type: approval.requested
    when: {eq: [{var: task.typeKey}, claim-reply]}
  recipient: {kind: assigned}
  notification:
    type: claims.reply_approval_requested
    title: "A reply to a customer waits for your decision: {{task.publicId}}"
    actions: [approvalDecide]
  dedupKeyTemplate: "claims:reply-approval:{{event.entityId}}"
  close:
    "on": [approval.approved, approval.rejected, approval.cancelled]
```

Подробно — в [Уведомлениях пакета](notifications.md).

## 11. Вся пирамида { #pyramid }

```bash
package-sdk test . --env /dev/null
```

```text
ok   проверка: схема, ссылки, валидаторы ядра
ok   контракты скиллов (skill-sdk export --check)
   ok   claims: ok
ok   тесты кода интеграции (pytest)
   ok   claims: 10 passed in 0.29s
ok   сценарии пакета — песочница ядра
== claims
…
покрытие claim v1: elements 13/13, transitions 12/12, decisionRows 3/3, handlers 1/1
покрытие правила claim-reopened (тестов 4): branches 6/6, outcomes 4/4
покрытие типа задачи claim-reply v1 (тестов 3): outcomes 4/4
ok (passed): тестов 12, зелёных 12
ok: пирамида пакетов claims (11612 мс)
```

`--env /dev/null` — прогон не зависит от локального `.env`: порог возврата
берётся из `default` манифеста, а `CLAIMS_WORKSPACE_ID` (вид `workspace`) не
нужен вовсе — `workspaceId` процесса и правила песочница заменяет своим тестовым
пространством работы. Подробно — в [Тестах пакета](testing.md#subjects).

## 12. Образы и установка { #install }

Образы собирает CI автора из сгенерированных `Dockerfile` поверх базовых образов
платформы. Опубликованных базовых образов пока нет: соберите их по рецептам
`examples/claims/stand/observer-base.Dockerfile` и `runner-base.Dockerfile`
репозитория `package-sdk` (см. [Интеграции](integrations.md#images)):

```bash
docker build --build-arg BASE_IMAGE=<образ наблюдателя> -f Dockerfile \
  -t registry.example.com/claims/helpdesk-observer:0.1.0 .
docker build --build-arg RUNNER_IMAGE=<образ исполнителя> -f Dockerfile.skills \
  -t registry.example.com/claims/claims-skills:0.1.0 .
```

Установка — `examples/claims/packages.yaml`: пакет по пути и онтологии
пространства работы претензий.

```yaml
apiVersion: taimen.ai/v1
kind: Installation
key: claims-example
spec:
  packages:
    - {key: claims, path: ./claims}
  knowledge:
    - workspace: ${CLAIMS_WORKSPACE_ID}
      packs: ["default@1", "claims@1"]
```

```bash
cat > claims.env <<'EOF'
CLAIMS_WORKSPACE_ID=<root workspace of the claims>
HELPDESK_URL=http://helpdesk:8080
NOTIFICATION_SERVICE_URL=https://platform.example.com/notify
EOF
export CP_TOKEN=<access token audience control-plane>
export NOTIFY_TOKEN=<access token audience notification-service>
package-sdk plan  --install packages.yaml --server https://platform.example.com --env claims.env --out plan.json
package-sdk apply --plan plan.json        --server https://platform.example.com --env claims.env
```

Хосту скиллов в окружении нужны `HELPDESK_URL` и модель (`SKILL_LLM_PROVIDER` и
остальные `SKILL_LLM_*`); узлу — метка `helpdesk-access` и секрет `helpdesk-token`.
В примере есть демо-хелпдеск без учётных записей:
`python helpdesk/demo_helpdesk.py --port 8080` (слушает `127.0.0.1`; на другом
адресе требует свой токен `HELPDESK_TOKEN`). Подробно — в [Установке и
выпуске](install-and-release.md).

## См. также

- [Пакет за 10 минут](quickstart.md)
- [Тесты пакета](testing.md)
- [Установка и выпуск](install-and-release.md)
- [Интеграции](integrations.md)
- [Чек-лист готовности пакета](checklist.md)
