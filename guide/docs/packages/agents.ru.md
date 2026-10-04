# Агенты пакета

Пакет не только описывает работу, но и приносит тех, кто её делает: исполнителей
задач, хостов скиллов, наблюдателей внешних систем и личности, от имени которых
действуют правила и процессы. Все они — объекты вида `Agent` в папке `agents/`.
Статья для автора пакета: какого агента завести под какую роль, какие права ему
дать, как описать размещение и образ так, чтобы пакет ставился на чужой
инсталляции без правки. Обоснование — TAI-ADR-0052, TAI-ADR-0062 (п.9) и
CP-ADR-0073.

Полный справочник разделов описания, ревизий, событий и API реестра — в статье
[Агенты описанием](../runner/declarative-agents.md), размещение на машинах — в
[Узлах и fleet](../runner/fleet.md). Здесь — то, что нужно автору пакета.

## Какой агент нужен

| Роль в пакете | `identity.kind` | `executor.kind` | `placement` | Пример |
|---|---|---|---|---|
| Исполнитель задач агентом-программистом или ассистентом | `agent` | `claude-code` или `codex` | узел с нужными метками и секретами | разбор обращения, подготовка черновика |
| Хост скиллов пакета | `agent` | `skills` | узел, где установлен код интеграции | скиллы класса `helpdesk.*` |
| Наблюдатель внешней системы | `agent` | `observer` (или собственный вид со своими `params`) | узел с доступом к системе | опрос очереди обращений |
| Личность правил и процессов | `service` или `agent` | — | `none` | от чьего имени правило заводит работу |
| Сервисная учётка компонента | `service` | — | `none` | права и потолок scope сервиса |

Одна роль — один агент. Хост скиллов и наблюдатель одной интеграции — два агента с
разными правами, хотя образ у них может быть общий.

## Заготовки

```bash
# личность без процесса: identity.kind service, placement: none
package-sdk add Agent intake-rules --package .

# процесс — вместе с личностью <ключ>-process и ролью владельца <ключ>-owner
package-sdk add Process intake --package .

# новый пакет с кодом интеграции: наблюдатель и его агент (state: stopped)
package-sdk init claims --integration --image
```

`add` пишет `agents/<ключ>.yaml` со ссылкой на схему для редактора, минимальным
`spec` и подсказками необязательных полей из описаний схемы. Существующие файлы
заготовка не перезаписывает. Минимальное описание, которое проходит схему и
проверки ядра:

```yaml
apiVersion: taimen.ai/v1
kind: Agent
key: intake-rules
spec:
  displayName: Intake rules
  identity:
    kind: service
    permissions: [tasks.read]
  placement: none
```

`init --integration` кладёт агента наблюдателя `agents/<пакет>-observer.yaml` в
состоянии `stopped`: он запустится, когда автор заполнит `config` и поменяет в файле
`state` на `running`, а установка даст узел с нужными метками и секретами.

`add Agent` пишет одну заготовку на любую роль — личность `service` с
`placement: none`. Для хоста скиллов, наблюдателя и исполнителя замените её
описанием своей роли. Полные минимальные описания по ролям (метки, секреты и
образы — примерные):

=== "Хост скиллов"

    ```yaml
    # код интеграции в образе; адрес системы — окружение хоста (см. ниже)
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
      placement:
        requires: [helpdesk-access]
        secrets: [helpdesk-token]
        resources: {cpus: 1, memoryMb: 512}
      state: running
    ```

=== "Наблюдатель"

    ```yaml
    # адрес системы — config из переменной пакета
    apiVersion: taimen.ai/v1
    kind: Agent
    key: helpdesk-observer
    spec:
      displayName: Helpdesk observer
      identity:
        kind: agent
        permissions: [observations.write]
      work:
        workspace: ${CLAIMS_WORKSPACE_ID}
      executor:
        kind: observer
        image: registry.example.com/claims/helpdesk-observer:0.1.0
        params:
          entrypoint: claims_helpdesk.observer:observe
          intervalSeconds: 60
          config: {baseUrl: "${HELPDESK_URL}"}
      placement:
        requires: [helpdesk-access]
        secrets: [helpdesk-token]
        resources: {cpus: 1, memoryMb: 256}
      state: running
    ```

=== "Исполнитель задач"

    ```yaml
    # кодовый агент берёт назначенные ему задачи типа
    apiVersion: taimen.ai/v1
    kind: Agent
    key: claims-drafter
    spec:
      displayName: Claims drafter
      identity:
        kind: agent
        permissions: [sessions.open, tasks.read, tasks.write, tasks.claim, claims.manage,
                      events.read, artifacts.read, artifacts.write, projects.read,
                      workspaces.read, task_types.read, rules.read]
      work:
        workspace: ${CLAIMS_WORKSPACE_ID}
        onlyAssigned: true
        taskTypes: [claim-draft]
      executor:
        kind: claude-code
        instructions: Draft the reply; do not send anything yourself.
      placement:
        requires: [coding-agent]
        resources: {cpus: 1, memoryMb: 1024}
      state: running
    ```

=== "Личность"

    ```yaml
    # личность правил или процесса: principal и права, процесса нет
    apiVersion: taimen.ai/v1
    kind: Agent
    key: claims-rules
    spec:
      displayName: Claims rules
      identity:
        kind: service
        permissions: [events.read, tasks.read, tasks.write, skills.invoke]
      placement: none
    ```

## Личность и права { #identity }

Права агента — ровно то, что делают его действия. Платформа проверяет их при
каждом применении: право, которого нет у применяющего, — `403
permission_escalation`; `admin` и `approvals.decide` у агента и сервиса — `422
permissions_not_allowed_for_kind`.

| Роль | Типичный набор `identity.permissions` |
|---|---|
| Исполнитель задач | `sessions.open`, `tasks.read`, `tasks.write`, `tasks.claim`, `claims.manage`, `events.read`, `artifacts.read`, `artifacts.write`, `projects.read`, `workspaces.read`, `task_types.read`, `rules.read` |
| Хост скиллов | `skills.execute`, а также `sessions.open` и `tasks.read`: демон хоста открывает сессию и ищет свою работу. Права из `requiredPermissions` контрактов ядро проверяет у вызывающего, а не у исполнителя |
| Наблюдатель | `observations.write`; `artifacts.write`, если он заводит документы |
| Личность процесса | `tasks.read`, `tasks.write`, `approvals.manage`, `skills.invoke`, `observations.write`, `events.read` — по намерениям процесса; плюс права из `requiredPermissions` скиллов, которые процесс вызывает |
| Личность правил | по действиям правил: `events.read` — чтение факта; `tasks.read`, `tasks.write` — поиск и заведение работы; `skills.invoke` — интерпретация скиллом; `approvals.manage` — `request_decision`; `claims.manage` — `complete_work` и `cancel_work` работы под claim; плюс права из `requiredPermissions` скиллов интерпретации |

- `observations.write` даёт и запись наблюдений (`POST /api/v1/observations`), и
  снимки знаний (`POST /api/v1/knowledge/snapshots`).
- `identity.roles` — роли tenant'а. Если роль объявлена в пакете или его
  `requires`, `check` молчит; иначе предупреждает: роль должна уже быть в tenant'е.
  Для ролей и `capabilities` применяющему нужно `org.manage`.
- `identity.iam` (`audiences`, `scopeCeiling`) — только для сервисных учёток, чью
  учётку выпускает установка; ядро раздел хранит, но не толкует.
- `skills.invoke: [имя@версия]` — версии скиллов, которые агент вызывает через
  ядро. Реестр назначает их principal'у агента сам при публикации ревизии, ручное
  назначение не нужно. Для этого у агента в `identity.permissions` должно быть
  право `skills.invoke` (иначе `422 skills_invoke_not_permitted`), а у применяющего —
  `org.manage` (иначе `403 permission_escalation`). Неизвестную или выключенную
  версию отвергает ядро (`422 unknown_reference`, `422 skill_disabled`); `check`
  этот раздел не сверяет.

## Работа и топология

Раздел `work` говорит, какую работу агент берёт. Топологию окружения — workspace
и проект — пакет не знает, поэтому пишет её переменной установки:

```yaml
# package.yaml
spec:
  variables:
    CLAIMS_WORKSPACE_ID:
      kind: workspace
      description: Workspace, где живут дела по обращениям
```

```yaml
# agents/claims-drafter.yaml
spec:
  work:
    workspace: ${CLAIMS_WORKSPACE_ID}
    onlyAssigned: true
    taskTypes: [claim-draft]
```

- Использованная переменная обязана быть объявлена в `spec.variables`, объявленная —
  использована (`variable_undeclared`, `variable_unused` в `check`). Вид `workspace`
  значит UUID, который `plan` проверяет на стенде.
- `work.taskTypes` должны быть объявлены в пакете или его `requires`, иначе `check`
  даёт ошибку.
- `onlyAssigned` по умолчанию `true`: агент берёт только назначенную ему работу.
  Назначают его ссылкой `agent:<key>` — в `assignee` исходов и правил, в
  `assigneeId` задач. `check` проверяет литеральные ссылки: агент должен быть описан
  в пакете или его `requires` и не выводиться из оборота той же установкой.

## Исполнение

`executor.kind` — вид исполнителя, `executor.params` — его параметры, которые
проверяет схема пакета по виду, `executor.instructions` — инструкции исполнителю (до
64 KiB), слой после инструкций платформы, проекта и типа задачи.

| Вид | Что делает | Обязательные `params` |
|---|---|---|
| `claude-code`, `codex` | исполняет задачи кодовым агентом | — |
| `skills` | исполняет только скиллы из раздела `skills` | — (без раздела `skills` демон не стартует) |
| `observer` | наблюдатель интеграции на `package_sdk.connector` | `entrypoint` |
| `git-connector` | собственный вид наблюдателя git с особыми `params` | `repositories` |

Секреты в описание не пишутся: ключи `params`, похожие на секрет (`token`,
`password`, …), ядро отвергает `422 secret_material_rejected`, а в `config`
наблюдателя их не пропускает схема. Наблюдатель и хост скиллов получают секрет
именем в `placement.secrets`: узел кладёт файл `/run/secrets/<имя>`, а
`ctx.secret("<имя>")` — среды наблюдателя и skill-sdk — его читает по одному
правилу (см. [Интеграции](integrations.md#secrets)).

Хост скиллов перечисляет, что исполняет и куда ходит:

```yaml
spec:
  identity:
    kind: agent
    permissions: [sessions.open, tasks.read, skills.execute]
  executor: {kind: skills}
  skills:
    protocols: [local]
    local: [claims_integration.skills]     # модуль или модуль:функция
    audiences: [control-plane]
    concurrency: 4
```

Чего нет в разделе `skills`, того нет и у исполнителя, даже если это задано на
хосте переменными окружения. Подробнее — в статье [Скиллы пакета](skills.md).

!!! warning "Несекретный параметр хоста скиллов пакет пока не задаёт"
    У вида `skills` нет `params`: в отличие от `config` наблюдателя, описание
    агента не может передать хосту, например, адрес внешней системы из
    переменной пакета, и `describe` такой параметр не печатает. `ctx.config(…)`
    читает окружение процесса хоста, а его задаёт установка на узле — общими
    переменными окружения исполнителей вида `skills`. Пока механизма нет,
    назовите параметр в README пакета («хосту скиллов нужен `HELPDESK_URL`») и
    передайте его установщику; адрес, который нужен и наблюдателю, держите
    переменной пакета в его `config`.

## Размещение

`placement` — контракт пакета с установкой: где агент может работать. Пакет
называет **метки** и **имена секретов**, установка решает, какие машины их дают.

```yaml
spec:
  placement:
    requires: [claims-source-access]   # метка узла: имя или имя=значение
    secrets: [claims-source-token]     # файл секрета на узле; значение — не здесь
    resources: {cpus: 1, memoryMb: 256}
    replicas: 1
    drainSeconds: 600
  state: running
```

- `resources.cpus` — целое: дробное ядро отвергает `422 non_canonical_value`.
- `placement: none` — только личность, без процесса.
- `state` и `replicas` — желаемое состояние, а не ревизия: `apply` приводит к ним
  агента каждый раз. Остановить агента надолго — правка файла, а не ручная
  остановка, иначе следующий `apply` запустит его снова.
- Метки и секреты называйте по смыслу доступа, а не по машине: `claims-source-access`,
  а не имя сервера. Их перечень печатает `describe`:

```bash
package-sdk describe .
```

```text
агенты и узлы:
  claims-observer (observer, образ registry.example.com/claims/observer:1.2.0): метки claims-source-access; секреты claims-source-token
  claims-rules (—): без процесса (только личность)
```

## Образ исполнителя { #image }

По умолчанию агент работает на образе, который узел сопоставил виду исполнителя.
Пакету с кодом интеграции нужен свой образ — с этим кодом внутри. Его называет поле
`executor.image`:

```yaml
spec:
  executor:
    kind: observer
    image: registry.example.com/claims/observer:1.2.0
    params:
      entrypoint: claims_integration.observer:observe
```

| Правило | Что значит |
|---|---|
| Форма | `[registry[:port]/]path:tag`, `…@sha256:<64 hex>` или `…:tag@sha256:<64 hex>`, до 255 символов. Тег или дайджест обязателен: неявного `latest` нет |
| Проверка ядра | только форма: неверная ссылка — `400 invalid_request` с `loc` `body.spec.executor.image` |
| Ревизия | образ — часть описания и его хэша: смена образа — новая ревизия; без поля описание то же, что и до появления поля |
| Кто читает | `GET /api/v1/agents/me` и список агентов отдают `spec.executor.image` ревизии; в событие `agent.revision_published` образ не кладётся |

Назвать образ — не право его запустить.

Узел запускает названный образ, только если его допускает список
`executors.<вид>.images` в `node.yaml` этого узла: точная ссылка или шаблон с одной `*`
в теге. Иначе агент ждёт с причиной размещения `image_not_allowed`, а узел, которому
образ всё же прислали, его не запускает. Как узел сверяет список — в статье [Узлы и
fleet](../runner/fleet.md#images).

Образ собирается из заготовки `package-sdk image observer` или `package-sdk image
skills` (см. [Интеграции](integrations.md#images)). Версию образа пакет закрепляет
тегом: пересобранный под тем же тегом образ работающий контейнер не подхватит.

## Агенты правил и процессов

Правило и процесс действуют не от имени того, кто применил пакет, а от личности:

```yaml
# rules/claim-reopened.yaml
spec:
  identity: {agent: claims-rules}
```

```yaml
# processes/claim.yaml
spec:
  identity: {agent: claim-process}
  owner: [{role: claim-owner}]
```

- Личность — `Agent` с `placement: none`: процесса нет, есть principal и права.
- `check` требует, чтобы агент из `identity.agent` был описан в пакете или его
  `requires`.
- Порядок применения: `Agent` идёт после ролей, скиллов и типов задач и до правил и
  процессов, поэтому личность уже есть, когда правило на неё ссылается.

## Проверка и применение

```bash
package-sdk check --package .          # схема, ссылки, модель AgentSpec ядра
package-sdk plan --install packages.yaml --server https://platform.example.com --out plan.json
package-sdk apply --plan plan.json --server https://platform.example.com
```

- `check` проверяет описание схемой формата (`$defs.agentSpec`), моделью `AgentSpec`
  ядра (нужен `package-sdk[sandbox]`) и ссылками пакета.
- `plan` строит единый план установки без единой записи. Для агента он узнаёт у ядра
  (`POST /api/v1/agents:validate`), будет ли новая ревизия и изменится ли желаемое
  состояние. У пакета с процессами или календарями агентов вместе с ними планирует
  само ядро (`POST /api/v1/packages:plan`). Переменные вида `workspace`, `project`,
  `principal`, `role` план сверяет со стендом: такой UUID должен существовать.
- `apply --plan` применяет ровно сохранённый план после подтверждения человека; если
  стенд разошёлся с планом, установка останавливается с `plan_stale` до первой
  записи. Агент публикуется `POST /api/v1/agents`.

Токену установки нужны `agents.manage` и все права, которые пакет выдаёт агентам.

Вывод из оборота — ключ в `retire.Agent` файла установки: исполнитель
останавливается, credential отзывается, история прогонов остаётся. Ключ выведенного
агента заново не используется (`409 agent_retired`).

## Типичные проблемы

| Симптом | Причина и решение |
|---|---|
| `403 permission_escalation`, `details.missing` | у токена установки нет права, которое пакет выдаёт агенту, или `org.manage` для ролей, capabilities и `skills.invoke` |
| `422 skills_invoke_not_permitted` | у агента есть раздел `skills.invoke`, но нет права `skills.invoke` в `identity.permissions` |
| `422 permissions_not_allowed_for_kind` | `admin` или `approvals.decide` у агента — убрать: решения принимает человек |
| `422 secret_material_rejected` | ключ в `params`, `workingCopy` или `resources` похож на секрет — передавать секрет именем в `placement.secrets` |
| `400 invalid_request` на `spec.executor.image` | нет тега и дайджеста или лишние символы в ссылке |
| `check`: `work.taskTypes '…' — такого TaskType нет` | тип задачи не объявлен в пакете и его `requires` |
| `check`: `variable_undeclared` | `${ИМЯ}` в описании без объявления в `spec.variables` |
| агент после `apply` снова запущен | в файле `state: running` — останавливать правкой файла |
| агент ждёт размещения с `image_not_allowed` | ни один узел не допускает образ из `executor.image` — администратор узла добавляет его в список, либо пакет убирает поле |

## См. также

- [Скиллы пакета](skills.md)
- [Интеграции](integrations.md)
- [Пакеты каталога](../control-plane/catalog-packages.md#agent)
- [Агенты описанием](../runner/declarative-agents.md)
- [Узлы и fleet](../runner/fleet.md)
- [Правила вывода работы](../control-plane/work-rules.md#identity) — личность правил
- [Процессы](../processes/index.md) — владелец и личность процесса
