# Скиллы пакета

Скилл — версионированное действие с контрактом: входы, выходы, побочные эффекты,
риск, таймаут, повторы, реализация. Пакету скиллы нужны там, где правилу,
процессу или типу задачи требуется что-то сделать или посчитать кодом: прочитать
внешнюю систему, подготовить черновик, записать результат наружу. Статья для
автора пакета: как написать скилл на `skill-sdk`, положить его контракт в пакет,
выбрать способ хостинга и провести внешнюю запись через согласование.
Обоснование — TAI-ADR-0045 (скиллы из кода), CP-ADR-0056 (контракт и вызов).

API библиотеки целиком — в статье [skill-sdk](../sdk/skill-sdk.md).

## Код — источник, YAML — выгрузка

Скилл пишется один раз в коде интеграции пакета. Контракт — из аннотаций и
аргументов декоратора, описание — из первого абзаца docstring:

```python
# integration/src/claims_integration/skills.py
from pydantic import BaseModel
from skill_sdk import SkillContext, skill


class DraftIn(BaseModel):
    claim: str
    history: list[str] = []


class DraftOut(BaseModel):
    draft: str


@skill("claim.draft_reply", version="1", side_effects="none", risk="low", timeout=120)
async def draft_reply(inputs: DraftIn, ctx: SkillContext) -> DraftOut:
    """Draft a reply to a customer claim for a person to review."""
    answer = await ctx.llm.chat_json(
        system_prompt="You draft polite replies to customer claims.",
        messages=[{"role": "user", "content": inputs.claim}],
        response_model=DraftOut,
        schema_name="draft",
    )
    return answer.data
```

Файл пакета `skills/<имя>.yaml` генерирует `skill-sdk` и руками не правят:

```bash
SKILL_SDK="$(uv tool dir)/package-sdk/bin/skill-sdk"     # из окружения инструмента
PYTHONPATH=integration/src "$SKILL_SDK" export --package . claims_integration           # записать skills/*.yaml
PYTHONPATH=integration/src "$SKILL_SDK" export --package . --check claims_integration   # код совпадает с YAML
```

- **Где взять команду.** `skill-sdk` ставится дополнением `skills` в окружение
  инструмента `package-sdk`, но на `PATH` не выставляется — отсюда путь через
  `uv tool dir`. Отдельно на `PATH` её ставит `uv tool install --editable
  ./sdk/skill-sdk`; тогда сторонние зависимости кода интеграции нужно добавить и
  туда (`--with`).
- **`PYTHONPATH`.** Код интеграции лежит в `integration/src`, и без него на
  `sys.path` модуль не импортируется (`ModuleNotFoundError`). Ступень контрактов
  `package-sdk test` добавляет путь сама, поэтому для сверки в CI ручной вызов
  не нужен: `test` сверяет контракты и без команды на `PATH`.

```yaml
# Сгенерировано skill-sdk из кода — правьте код и перегенерируйте (TAI-ADR-0045).
apiVersion: taimen.ai/v1
kind: Skill
key: claim.draft_reply
spec:
  version: '1'
  description: Draft a reply to a customer claim for a person to review.
  sideEffects: none
  riskLevel: low
  contract:
    inputs: {…}          # JSON Schema из DraftIn
    outputs: {…}         # JSON Schema из DraftOut
    idempotency: none
    timeoutSeconds: 120
    retryPolicy: {maxAttempts: 1, backoffSeconds: 0}
    implementation:
      protocol: local
      entrypoint: claims_integration.skills:draft_reply
```

- `key` — имя скилла, `spec.version` — его версия; вместе это `имя@версия`, по
  которому на скилл ссылаются правила, процессы и типы задач.
- Контракт опубликованной версии неизменяем. Изменились схемы или политика —
  новая `version` в декораторе, новый файл, новая версия в каталоге. `plan`,
  увидев отличие `protocol`, `sideEffects`, `riskLevel` или `contract` у уже
  опубликованной версии, не строится: «поднимите `spec.version`».
- Исключение — адрес реализации `implementation.endpoint`: это свойство
  инсталляции, а не обещание версии. Если контракт отличается только им, `apply`
  переносит адрес правкой версии, без новой версии.
- `description`, `config`, `inputSchema`, `outputSchema` без контракта — изменяемые
  поля: `apply` правит их у опубликованной версии.

`package-sdk test` сверяет контракты кода интеграции с файлами пакета тем же
`skill-sdk export --check` — отдельной ступенью перед сценариями.

## Контракт и политика

| Аргумент `@skill` | Поле контракта | Что задаёт |
|---|---|---|
| `side_effects` | `sideEffects` | `none`, `external_read` или `external_write` — что скилл делает во внешнем мире |
| `risk` | `riskLevel` | `low`, `medium`, `high` |
| `idempotency` | `idempotency` | `required`, `natural`, `none` |
| `timeout` | `timeoutSeconds` | 1–3600 секунд |
| `retry=(n, s)` | `retryPolicy` | `maxAttempts` 1–10, `backoffSeconds` 0–3600 |
| `permissions` | `requiredPermissions` | права, которые ядро проверит у вызывающего на workspace задачи (`403 skill_permission_denied`) |
| `cost_model` | `costModel` | единица и оценка стоимости вызова |

SDK отвергает при импорте то, что отвергло бы ядро: например `external_write` без
идемпотентности с повторами — повтор внешней записи без ключа дал бы второй эффект.

**Исход против сбоя.** Ожидаемый результат контракта — это выход, даже если он
«отрицательный»: `conflict`, `not_found`, `rejected` пишутся полями модели выхода.
`SkillError(code, message, retryable=…)` — только для сбоя, когда результата нет:
внешняя система недоступна, время вышло.

## Кто вызывает скилл

Скилл ничего не делает, пока на него не сослались. Ссылки в пакете замкнуты: скилл
в `execution`, `invokeSkill`, `interpretation.skill` и `call.skill` должен быть
объявлен в том же пакете или в пакете из `requires`, иначе `check` даёт ошибку.
`skills.invoke` агента `check` не сверяет: неизвестную версию отвергает ядро при
публикации агента (`422 unknown_reference`).

| Где | Поле | Что происходит |
|---|---|---|
| Тип задачи | `execution: {skill, version, inputs}` | задачу типа исполняет один вызов скилла; входы по умолчанию — `$.customFields` |
| Исход согласования или сдачи | `invokeSkill: {skill: имя@версия, inputs}` | вызов по решению человека; реакции `onSuccess`/`onFailure` — по итогу вызова |
| Правило вывода работы | `interpretation.skill: имя@версия` | скилл толкует факт: что это и какую работу завести |
| Шаг процесса | `call: {skill: имя@версия, input}` | вызов из экземпляра процесса |
| Агент | `skills.invoke: [имя@версия]` | агент вызывает скилл через ядро; реестр назначает версию его principal'у |

Правило, которое толкует факт, не может звать скилл внешней записи: `422
rule_skill_side_effects` — у правила нет решения человека, на которое сослаться.

## Внешняя запись и согласование { #external-write }

`sideEffects: external_write` — действие во внешнем мире от имени организации.
Ядро исполняет такой вызов, только если у него есть **основание**:

- **одобренный gate-approval** на той же нетерминальной задаче, ещё не
  использованный для этой версии скилла (`409 approval_already_used` при повторе);
- или **основание исполнения**: тип задачи закрепил эту версию в `execution`, и
  прогон задачи идёт. Основание действует, только пока на задаче нет ожидающего
  gate-approval: иначе вызов получает `409 approval_required`;
- или **шаг процесса**: шаг `call` живого экземпляра называет эту версию скилла.
  Основание держится, пока шаг открыт; ожидающий вызов закрытого шага
  отменяется (`process_step_closed`), а уже выданный — нет (см. [Внешняя запись
  из процесса](processes.md#external-write)).

Без основания — `403 skill_side_effect_not_authorized`; для закрытой задачи —
`409 task_terminal`. Отсюда правила для пакета:

- ссылка на скилл внешней записи в `invokeSkill` пишется **с версией** — ядро
  отвергает публикацию исхода, который разрешается в `external_write` без
  закреплённой версии;
- в критериях приёмки типа задачи скилл внешней записи допустим только после
  критерия решения человека (`human` или `llm_judge`) с тем же `when`, иначе
  публикация типа — `422 invalid_acceptance_spec`, `cause:
  external_write_without_decision` (см. [Приёмка типа](../control-plane/task-types.md#type-acceptance));
- черновик, который человек проверит, — скилл `none` или `external_read`, а запись
  результата наружу — отдельный скилл `external_write` в исходе одобрения.

```yaml
# task-types/claim-reply.yaml — фрагмент spec
approvalSchema:
  gates:
    default:
      outcomes:
        approved:
          - invokeSkill:
              skill: claim.send_reply@1    # external_write: только с версией
              inputs: {claim: $.task.customFields.claim, comment: $.approval.comment}
```

Выражения `$.task.…` и `$.approval.…` (`id`, `comment`, `decidedBy`, `decidedAt`,
`outcome`) — те же, что у остальных действий исхода (см.
[Approvals](../control-plane/approvals.md)).

## Контекст вызова

| Член `SkillContext` | Назначение |
|---|---|
| `ctx.invocation_id`, `ctx.idempotency_key` | какой это вызов; повтор с тем же ключом не должен дать второй внешний эффект |
| `ctx.remaining()`, `ctx.check_deadline()` | сколько осталось до таймаута контракта |
| `ctx.config(name, default)` | параметр хостинга — переменная окружения процесса, который исполняет скилл |
| `ctx.secret(name)` | секрет хостинга: переменная окружения процесса, затем файл секрета узла `/run/secrets/<имя>`; нет ни там, ни там — повторяемый `config_missing` |
| `ctx.llm` | LLM по конфигурации инсталляции; токены учитываются в стоимости сами |
| `ctx.add_cost(unit, amount)` | своё потребление: запросы к API, страницы |
| `ctx.artifacts.read(id)` | содержимое артефакта через ядро: `data`, `media_type`, `text()` |
| `ctx.knowledge` | база знаний через ядро: `preview`, `apply` (со `stateToken`, иначе `SnapshotStale`), `document`, `recall`, `query` |
| `ctx.caller` | проверенный контекст вызывающего (`http`, `mcp-http`) |

Клиента Control Plane в контексте нет намеренно: скилл не заводит и не двигает
задачи — это делают исходы и правила. `ctx.artifacts` и `ctx.knowledge` — узкий
доступ через ядро учётной записью исполнителя; память скилл видит только так.

- **Параметры и секреты скилла — не пакет.** Пакет называет их в документации
  интеграции, значения задаёт установка:
    - параметры (`ctx.config`) — окружение процесса хоста. Объявить такой
      параметр в пакете (как `config` наблюдателя) и показать его в `describe`
      пока нельзя — см. [Агенты пакета](agents.md), раздел «Исполнение»;
    - секреты (`ctx.secret`) — хосту, размещённому узлом, имена из
      `placement.secrets` его агента: узел кладёт файл `/run/secrets/<имя>`, и
      `ctx.secret("<имя>")` его читает. Хосту вне узла (свой сервис `http` или
      `mcp`) — переменная окружения с тем же именем; она сильнее файла.

    Правило чтения файла секрета одно на все SDK — канон `skill_sdk.secrets`:
    пустой или пробельный файл — секрета нет, у значения обрезаются только
    хвостовые `\r\n`, имя `agent-pat` зарезервировано под PAT агента. Отказ
    правила — не «секрета нет», а `secret_file_rejected` с причиной (см.
    [skill-sdk](../sdk/skill-sdk.md), раздел «Секреты»).
- **LLM.** Провайдер выбирает инсталляция переменной `SKILL_LLM_PROVIDER`:
  `openai` (по умолчанию, `SKILL_LLM_BASE_URL`, `SKILL_LLM_API_KEY`,
  `SKILL_LLM_MODELS`) или `claude-code` (Claude по подписке через CLI). Персональные
  данные физических лиц в промпте (ФИО, СНИЛС, паспорт, телефон, e-mail)
  заменяются маркером `[ПДн:вид]` до вызова модели.
- **`ctx.knowledge.query`** обходит страницы ядра сам и возвращает все сущности;
  больше `max_items` — ошибка `knowledge_query_too_large`, а не обрезка.
- **Стоимость** вызова — токены LLM и единицы `add_cost`; ядро пишет её в вызов.

## Хостинг { #hosting }

Где исполняется скилл — решение установки, а не версии. Контракт называет протокол
реализации, а исполняет вызов тот, у кого есть право `skills.execute` и чей
allow-list покрывает реализацию.

=== "local — в хосте скиллов пакета"

    Код интеграции установлен в образ агента вида `skills`, агент перечисляет модули
    в `skills.local`:

    ```yaml
    # agents/claims-skills.yaml
    spec:
      identity: {kind: agent, permissions: [skills.execute]}
      executor:
        kind: skills
        image: registry.example.com/claims/skills:1.0.0
      skills:
        protocols: [local]
        local: [claims_integration.skills]
    ```

    Образ собирает `package-sdk image skills --modules claims_integration.skills`
    (см. [Интеграции](integrations.md#images)). Это путь по умолчанию: без своего
    сервиса, без сети до скилла, с изоляцией исполнителя.

=== "http — свой сервис"

    Скилл живёт в сервисе автора (`skill-sdk serve http <модуль>` или
    `skill_sdk.http.create_app(...)`), контракт называет адрес переменной установки:

    ```bash
    skill-sdk export --package . --protocol http \
        --endpoint '${CLAIMS_SKILLS_URL}' --audience claims-skills claims_integration
    ```

    Вызов идёт `POST /skills/{name}@{version}` с токеном IAM audience скилла;
    хостинг проверяет его (`SKILL_SDK_IAM_ISSUER`, `SKILL_SDK_AUDIENCE`,
    `SKILL_SDK_JWKS_URL`) и без проверки не стартует. Исполнителю нужен протокол
    `http` в `skills.protocols`, origin сервиса в `skills.httpOrigins` и audience в
    `skills.audiences`. Свой сервис оправдан, когда скилл держит состояние или
    ресурсы, которых нет у хоста скиллов.

=== "mcp — MCP-сервер"

    `skill-sdk serve mcp-stdio <модуль>` или `serve mcp-http`: скилл — инструмент с
    именем скилла, стоимость — в `_meta["skill/cost"]`, id вызова и ключ
    идемпотентности — в `_meta` запроса. Исполнителю нужен протокол `mcp` и
    адрес в `skills.mcpOrigins`.

## Тесты скилла { #tests }

```python
# integration/tests/test_skills.py
from skill_sdk.testing import FakeLlm, check_contract, invoke

from claims_integration.skills import draft_reply


def test_contract() -> None:
    check_contract(draft_reply)          # валидаторы ядра, если control-plane рядом


def test_draft_uses_the_claim() -> None:
    llm = FakeLlm([{"draft": "Здравствуйте! …"}])
    result = invoke(draft_reply, {"claim": "C-1"}, llm=llm)
    assert result.outputs["draft"].startswith("Здравствуйте")
    assert llm.calls[0].prompt == "C-1"
```

- `FakeLlm` отвечает одним ответом, списком по порядку или функцией от вызова;
  вызовы копятся в `llm.calls` уже после стража ПДн и учитываются в стоимости.
- `skill_sdk.testing.FakeCore` — ядро в памяти для `ctx.artifacts` и
  `ctx.knowledge` (подключается `configure_core`).
- Эти тесты — ступень кода интеграции в `package-sdk test`. Сценарии пакета
  (`tests/*.test.yaml`) скиллы не исполняют: ответы задаются в `mocks.skills`
  (`имя@версия` → ответы по порядку вызовов), выход проверяется по схеме скилла из
  каталога, а ожидаемые вызовы — `invokeSkill` в `expect`.

## Типичные проблемы

| Симптом | Причина и решение |
|---|---|
| `plan`: «контракт версии неизменяем, поднимите spec.version» | изменили контракт без новой `version` в декораторе |
| `403 skill_permission_denied` | у вызывающего (личности процесса или правила, агента) нет права из `requiredPermissions` контракта на workspace задачи |
| `409 approval_required` | вызов по основанию исполнения, а на задаче ждёт gate-approval |
| `export --check` падает в CI | код скилла изменился, а YAML не перегенерирован — `skill-sdk export` и коммит |
| `check`: ссылка на `имя@версия`, «такого Skill нет» | скилл не объявлен в пакете и его `requires` или версия не совпадает |
| `422 rule_skill_side_effects` | правило толкует факт скиллом `external_write` — вынести запись в исход согласования |
| `403 skill_side_effect_not_authorized` | вызов внешней записи без одобренного gate или основания исполнения |
| вызов висит в очереди | ни у одного исполнителя с `skills.execute` allow-list не покрывает реализацию: протокол, модуль, origin или audience |
| `config_missing` | у хоста не задан параметр или секрет, который читает скилл: нет переменной окружения и нет файла `/run/secrets/<имя>` (или он пуст) |
| `secret_file_rejected`, `secret_unreadable` | файл секрета узла есть, но негоден (ссылка за пределы каталога, не обычный файл, больше 64 КиБ, не UTF-8) или нет прав на чтение у пользователя процесса |

## См. также

- [skill-sdk](../sdk/skill-sdk.md) — API библиотеки
- [Агенты пакета](agents.md) — хост скиллов и права
- [Интеграции](integrations.md) — скиллы как действия интеграции
- [Типы задач и статусы](../control-plane/task-types.md) — `execution`, `approvalSchema`, приёмка
- [Правила вывода работы](../control-plane/work-rules.md) — интерпретация скиллом
- [Авторизация и права](../control-plane/authorization.md) — `skills.invoke`, `skills.execute`
