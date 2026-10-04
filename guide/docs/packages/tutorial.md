
# Example: customer claims

An end-to-end example of a package outside software development, "customer
claims", step by step: the manifest and ontology, the work of people, skills, a
process, a rule, an observer, agents, a notification, tests, and installation.
Each step ends with a check, and each step is sensibly made as a separate commit.
The page is for an author who has gone through [A package in 10
minutes](quickstart.md) and is building a first real vertical.

The finished package lives in the `package-sdk` repository, in the
`examples/claims/` directory, and is checked by its CI: the whole pyramid in the
sandbox on every change. The core knows nothing about claims: everything
domain-specific here is package data and the code of its integration.

## What we build

A customer files a claim in the helpdesk. The integration observer turns a new
ticket into an observation, and the observation opens an instance: a skill
classifies the claim, a decision table chooses who reviews it, a human decides and
writes a reply, a large refund is approved by a manager (but not the one who
reviewed the claim), and the reply goes to the helpdesk only after a human
decision. A ticket reopened after the instance is closed is one-off work: a rule
creates it.

```mermaid
flowchart LR
    H["Helpdesk"] -->|"new ticket"| O["helpdesk-observer"]
    O -->|"helpdesk.ticket_created"| P["Process claim"]
    P -->|"claims.classify@1"| S["claims-skills"]
    P -->|"table claim-route"| R["Review task<br/>(officer or manager)"]
    R -->|"refund above the threshold"| A["Manager approval<br/>(not the reviewer)"]
    R --> Y["Reply task"]
    A --> Y
    Y -->|"approved gate: helpdesk.reply@1"| S
    S -->|"reply, ticket closed"| H
    H -->|"reopened"| O
    O -->|"helpdesk.ticket_reopened"| W["Rule claim-reopened<br/>→ follow-up task"]
```

```text
examples/claims/
├── packages.yaml                  installation: the package and the workspace ontologies
└── claims/                        the package
    ├── package.yaml               manifest: variables, compatibility, ontologies
    ├── knowledge-packs/claims.yaml
    ├── roles/                     claims-officer, claims-manager
    ├── task-types/                claim-review, claim-reply, claim-followup
    ├── skills/                    contracts exported from the integration code
    ├── processes/claim.yaml       the instance: intake → review → reply
    ├── rules/claim-reopened.yaml
    ├── agents/                    observer, skill host, identities of the process and the rule
    ├── notification-rules/claim-reply-approval.yaml
    ├── tests/                     scenarios of the process, the rule, and the task type
    ├── integration/               observer and skills with unit tests
    └── Dockerfile, Dockerfile.skills
```

## 1. Scaffold and manifest { #init }

```bash
package-sdk init claims --display-name "Customer claims" --license Apache-2.0 \
    --integration --image
cd claims
```

The scaffold provides a manifest, a sample process with an identity and an owner
role, the observer code in `integration/`, its agent, and a `Dockerfile`. The
example chose its own names: the process `claim`, the roles `claims-officer` and
`claims-manager`, the integration module `claims_helpdesk`, the agent
`helpdesk-observer`. The package is not installed anywhere yet, so simply delete
the unneeded scaffold files or rename them together with their keys.
`package-sdk edit rename --package …` is for an object that is already installed:
it appends `renames` to the manifest so that the plan moves the object instead of
creating a new one.

The manifest declares everything that depends on the deployment as variables:

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

Check: `package-sdk check --package .`. As long as no object uses a variable,
`check` reports the `variable_unused` error: variables are declared together with
the first object that uses them (here, the process at step 5 and the agents at
step 9).

## 2. Ontology { #ontology }

The instance is projected into the knowledge base: the claim, the customer, the
product, the decision. The customer (an organization), the product, and the
decision are kinds of the platform ontology `default@1`; the package adds only the
claim and its relations.

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

Scaffold: `package-sdk add knowledge-pack claims`. Details are in [Knowledge and
ontology](knowledge.md).

## 3. The work of people { #work }

Two roles and three task types:

| Object | Why |
|---|---|
| `Role` `claims-officer` | reviews claims and writes replies, receives follow-ups |
| `Role` `claims-manager` | the process owner; reviews serious and billing claims, approves large refunds |
| `TaskType` `claim-review` | the task of the review step: the fields `resolution`, `refundAmount`, `reply` are the result of the step |
| `TaskType` `claim-reply` | the reply to the customer: goes to the helpdesk only through an approved gate |
| `TaskType` `claim-followup` | one-off work on a reopened ticket |

The key one is `claim-reply`. A reply to the customer is a write to an external
system on behalf of the organization, so it is performed by the outcome of a
human decision, not by the assignee:

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

Scaffolds: `package-sdk add role …`, `package-sdk add task-type …`. Task type
fields are covered in [Work](work.md). At this point `check` reports that the
skill `helpdesk.reply@1` does not exist; it appears at the next step.

## 4. Skills in code { #skills }

Skills are written as skill-sdk code in `integration/src/claims_helpdesk/skills.py`;
the YAML in `skills/` is an export and is not edited by hand.

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

- `claims.classify@1` writes nothing: it can be called from a process and a rule.
- `helpdesk.reply@1` is `external_write`: the core executes it only through an
  approved gate of the `claim-reply` task. The idempotency key of the call goes to
  the helpdesk: a retry does not produce a second reply.
- The helpdesk address is a host parameter, `ctx.config`, and the token is a node
  secret, `ctx.secret`; the package contains neither value.

Exporting contracts and unit tests. `skill-sdk` and `pytest` live in the
environment of the `package-sdk` tool (the `skills` extra, `--with pytest`),
not on `PATH`, and the integration code lives in `integration/src`, so the
commands are run from the tool's environment with `PYTHONPATH=src`:

```bash
cd integration
TOOL="$(uv tool dir)/package-sdk/bin"                 # the tool's environment
PYTHONPATH=src "$TOOL/skill-sdk" export --package .. claims_helpdesk.skills
PYTHONPATH=src "$TOOL/python" -m pytest -q tests/test_skills.py
cd ..
```

`package-sdk test` does the same by itself, in the contracts and integration
code stages, so a manual run is needed only to write the YAML or to run the
tests separately (see [Package tests](testing.md#integration-code)).

```python
def test_the_claim_is_classified_by_the_model() -> None:
    llm = FakeLlm([{"category": "defect", "severity": "high", "confidence": 0.93}])
    result = invoke(skills.classify,
                    {"subject": "Sparks from the heater", "text": "It sparked and smells of smoke."},
                    llm=llm)
    assert result.outputs == {"category": "defect", "severity": "high", "confidence": 0.93}
```

Details are in [Package skills](skills.md).

## 5. Process { #process }

The `claim` process opens one instance per ticket, takes it through three stages,
and projects it into the knowledge base. Fragments:

```yaml
spec:
  version: 1
  workspaceId: ${CLAIMS_WORKSPACE_ID}
  identity: {agent: claims-process}
  owner: [{role: claims-manager}]
  start:
    "on": {observation: helpdesk.ticket_created}
    key: "'claim:' + string(event.payload.data.ticketId)"   # one instance per ticket
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
              reviewedBy: string(task.assigneeId)       # the reviewer: the assignee of the step's task
        - id: approve-refund
          when: data.resolution == 'refund' && data.refundAmount > double(${CLAIMS_REFUND_THRESHOLD})
          approve:
            approvers: [{role: claims-manager}]
            quorum: any                                  # required: there is no default
            separationOfDuties: "[data.reviewedBy]"     # the reviewer does not approve
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

A scenario for each branch, before the process is fully written: a small refund, a
large refund with separation of duties and a deadline reminder, a refund refusal,
serious and billing claims. A fragment of the large refund scenario:

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

The process language is covered in the [Processes](../processes/index.md) section,
and the scenario format in [Scenarios and the core
plan](../processes/package-tests.md).

## 6. Rule { #rule }

A reopened ticket of a closed instance is not a new instance but one-off work.
This is a rule, not a process (see [Rule or process](rules.md#rule-or-process)):

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
    dedupKeyTemplate: "claim-reopened:{{payload.data.ticketId}}"   # one follow-up per ticket
    fields:
      title: "Follow up reopened claim {{payload.data.ticketId}}"
      assignee: "role:claims-officer"
      customFields:
        ticketId: "{{payload.data.ticketId}}"
        category: "{{skill.output.category}}"
        severity: "{{skill.output.severity}}"
```

Rule scenarios cover each branch of the condition and each outcome: a reopened
ticket, an internal ticket, an observation without a ticket, the model failing to
classify. They need the sandbox database:

```bash
export PACKAGE_SDK_SANDBOX_DATABASE_URL=postgresql://postgres:sandbox@127.0.0.1:55432/postgres
package-sdk test . --test claim-reopened
```

Details are in [Rules in a package](rules.md).

## 7. A task type with an external write { #task-type-tests }

The `claim-reply` gate is checked by a task type scenario: approval sends the reply
and completes the task, a helpdesk refusal leaves it open, a rejection leaves it a
draft.

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

## 8. Observer { #observer }

The observer polls the helpdesk by cursor and writes two kinds of facts to the
core:

```python
@observer(kind="helpdesk-observer", entrypoint="claims_helpdesk.observer:observe")
def observe(ctx: ObserveContext) -> None:
    base_url = str(ctx.config["baseUrl"])
    token = ctx.secret("helpdesk-token")      # node secret file, read on every cycle
    cursor = int(ctx.state.get("cursor", 0))
    for ticket in fetch(base_url, token, since=cursor, limit=int(ctx.config.get("pageSize") or 50)):
        kind = kind_of(ticket)                # helpdesk.ticket_created | helpdesk.ticket_reopened | None
        if kind is not None:
            ctx.emit(Observation(
                kind=kind,
                dedup_key=f"helpdesk:{ticket['id']}:{ticket['version']}",   # the ticket and its version
                data=data_of(ticket),
                external_ref={"system": "helpdesk", "id": str(ticket["id"]), "url": …},
            ))
        cursor = max(cursor, int(ticket["seq"]))
    ctx.state["cursor"] = cursor              # saved only after a cycle without errors
```

Tests without a deployment use `package_sdk.connector.testing`: a new ticket opens
an instance, replies are skipped, a repeated cycle does not produce a second fact,
a publishing failure does not move the cursor, and without a token the cycle is
skipped with `connector.secret_missing`.

```python
def test_a_repeated_cycle_is_not_a_second_fact(helpdesk: Helpdesk) -> None:
    helpdesk.changed.append(ticket("T-1001", version=1, seq=1, status="open"))
    core = FakeCore()
    run_once(observer.observe, config=CONFIG, secrets=SECRETS, core=core)
    run_once(observer.observe, config=CONFIG, secrets=SECRETS, core=core)
    assert len(core.observations) == 1
```

Details are in [Integrations](integrations.md#observer).

## 9. Agents { #agents }

Four agents, one per role in the package:

| Agent | Role | Permissions |
|---|---|---|
| `claims-process` | the process identity, `placement: none` | `events.read`, `tasks.read`, `tasks.write`, `approvals.manage`, `skills.invoke`, `observations.write` |
| `claims-rules` | the rule identity, `placement: none` | `events.read`, `tasks.read`, `tasks.write`, `skills.invoke` |
| `claims-skills` | the skill host, `executor.kind: skills` | `sessions.open`, `tasks.read`, `skills.execute` |
| `helpdesk-observer` | the observer, `executor.kind: observer` | `observations.write` |

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

The skill host and the observer get the helpdesk token by the same node secret
name, `helpdesk-token`; the observer takes the helpdesk address from `config`
(the `${HELPDESK_URL}` variable), and the skill host takes it from its
environment: a package has no way yet to declare a skills host parameter, so
the installation sets it on the node, and the package names it in the README.
Details are in [Package agents](agents.md).

## 10. Notification { #notification }

A reply to the customer is waiting for a decision: the assigned person receives a
notification with buttons:

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

Details are in [Package notifications](notifications.md).

## 11. The whole pyramid { #pyramid }

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

The output lists the pyramid stages in order (the check, skill contracts,
integration code tests, package scenarios in the core sandbox) and then the
coverage of the process, the rule, and the task type. `--env /dev/null` makes the
run independent of the local `.env`: the refund threshold is taken from the
manifest `default`, and `CLAIMS_WORKSPACE_ID` (of kind `workspace`) is not needed
at all, since the sandbox replaces the `workspaceId` of the process and the rule
with its own test workspace. Details are in [Package tests](testing.md#subjects).

## 12. Images and installation { #install }

The author's CI builds the images from the generated `Dockerfile`s on top of the
platform base images. There are no published base images yet: build them from
the recipes `examples/claims/stand/observer-base.Dockerfile` and
`runner-base.Dockerfile` of the `package-sdk` repository (see
[Integrations](integrations.md#images)):

```bash
docker build --build-arg BASE_IMAGE=<observer image> -f Dockerfile \
  -t registry.example.com/claims/helpdesk-observer:0.1.0 .
docker build --build-arg RUNNER_IMAGE=<executor image> -f Dockerfile.skills \
  -t registry.example.com/claims/claims-skills:0.1.0 .
```

The installation is `examples/claims/packages.yaml`: the package by path and the
ontologies of the claims workspace.

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

The skill host needs `HELPDESK_URL` and a model (`SKILL_LLM_PROVIDER` and the other
`SKILL_LLM_*`) in its environment; the node needs the `helpdesk-access` label and
the `helpdesk-token` secret. The example includes a demo helpdesk without
accounts: `python helpdesk/demo_helpdesk.py --port 8080` (it listens on
`127.0.0.1`; on another address it requires its own token, `HELPDESK_TOKEN`).
Details are in [Installation and release](install-and-release.md).

## See also

- [A package in 10 minutes](quickstart.md)
- [Package tests](testing.md)
- [Installation and release](install-and-release.md)
- [Integrations](integrations.md)
- [Package readiness checklist](checklist.md)
