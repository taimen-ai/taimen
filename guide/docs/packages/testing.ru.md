# Тесты пакета

Как проверить пакет целиком одной командой: пирамида `package-sdk test` от
статической проверки до сценариев процессов, правил и типов задач, песочница с
PostgreSQL, прогон на ядре стенда, покрытие и проверка в CI. Страница для автора
пакета; формат сценариев процессов подробно — в [Сценариях и плане ядра](../processes/package-tests.md),
сценарии правил и типов задач — в [Правилах](rules.md#tests) и [Работе](work.md#tests).
Обоснование — TAI-ADR-0062 (п.2, п.11), CP-ADR-0074.

## Пирамида одной командой

```bash
package-sdk test .
```

`test` проходит четыре ступени по порядку и печатает общий отчёт:

```mermaid
flowchart LR
    C["1. check<br/>схема, ссылки,<br/>валидаторы ядра"] --> S["2. skills<br/>контракты скиллов<br/>против кода"]
    S --> I["3. integration<br/>pytest кода<br/>интеграции"]
    I --> SC["4. scenarios<br/>tests/*.test.yaml<br/>кодом ядра"]
```

| Ступень | Что проверяет | Чем исполняется | Когда пропускается |
|---|---|---|---|
| `check` | схема формата, замкнутость ссылок, переменные, манифест, валидаторы ядра — как `package-sdk check` | код ядра (дополнение `sandbox`) | никогда; не прошла — выше не идём |
| `skills` | YAML `kind: Skill` пакета совпадает с кодом интеграции (`skill-sdk export --check`) | `skill-sdk` (дополнение `skills`) | нет каталога `integration/` или в нём нет модулей |
| `integration` | unit-тесты кода интеграции `integration/tests/` | `pytest` | нет `integration/tests/` или pytest не нашёл тестов |
| `scenarios` | язык процессов (выражения, данные, достижимость шагов), затем сценарии пакета `tests/*.test.yaml`: процессы, правила, типы задач | код ядра: песочница в процессе или ядро стенда (`--server`) | в пакете нет сценариев |

- **Пропуск — не провал.** Ступень без предмета помечается `SKIP` и прогон не
  валит.
- **Нечем исполнить — провал.** Если для ступени нет инструмента (кода ядра,
  `skill-sdk`, `pytest`), ступень — `ERR`, и прогон не зелёный. Молча ступень не
  пропускается.
- **Проверка — ворота.** Если `check` нашёл ошибку, остальные ступени
  помечаются «статическая проверка не пройдена — тесты не запускались».

Код выхода `0` — все ступени зелёные или пропущены за отсутствием предмета.

| Флаг | Что делает |
|---|---|
| `<каталог> …`, `--package <каталог или ключ>` | какие пакеты тестировать; без них — все пакеты из `packages/` текущего каталога |
| `--install <файл>` | все пакеты установки, источники из git — по `packages.lock` |
| `--test <имя или файл>` | только один сценарий (по `name`, имени файла или его основе без `.test.yaml`) |
| `--server <адрес>` | сценарии исполняет ядро стенда, а не песочница |
| `--workspace <id>` | с `--server`: чьи роли, календари и экземпляры читает прогон |
| `--database-url <адрес>` | база песочницы для правил и типов задач (или `PACKAGE_SDK_SANDBOX_DATABASE_URL`) |
| `--env <файл>` | значения `${ПЕРЕМЕННЫХ}` пакета, по умолчанию `.env`; окружение процесса сильнее файла |
| `--json` | отчёт документом |

## Что поставить { #install }

Все ступени исполняются в окружении самого `package-sdk`: код интеграции и его
тесты запускает тот же интерпретатор. Поэтому в окружение инструмента ставится
всё, что им нужно:

```bash
uv tool install "./sdk/package-sdk[all]" --with pytest
```

| Дополнение | Для какой ступени |
|---|---|
| `sandbox` | `check` с валидаторами ядра и сценарии в песочнице |
| `skills` | сверка контрактов скиллов (`skill-sdk`) |
| `connector` | тесты наблюдателя (`package_sdk.connector.testing`) |
| `all` | всё перечисленное и MCP-сервер автора |

- `pytest` в дополнения не входит — добавьте его `--with pytest`.
- Сторонние зависимости кода интеграции (то, что перечислено в
  `integration/pyproject.toml`) тоже добавляются `--with`: ступень не ставит их
  сама.
- Код ядра и SDK подключаются каталогами в раскладке установки (`services/`,
  `sdk/`), как описано в [Пакете за 10 минут](quickstart.md#install). Какие
  соседи нужны дополнению:

| Дополнение | Каталоги рядом с `sdk/package-sdk` |
|---|---|
| `sandbox` | `services/control-plane`, `sdk/platform-auth-sdk` |
| `connector` | `services/control-plane` (клиент ядра из его `client/`) |
| `skills` | `sdk/skill-sdk` |
| `mcp` | `services/control-plane` |
| `all` | `services/control-plane`, `sdk/platform-auth-sdk`, `sdk/skill-sdk` |

Команды `skill-sdk` и `pytest`, поставленные так, живут в окружении
инструмента, а не на `PATH`: наружу выставлена только `package-sdk`. Как
вызвать их руками — в разделе [Код интеграции](#integration-code).

!!! note "Окружение кода интеграции"
    Подпроцессы ступеней `skills` и `integration` не получают переменных, похожих
    на секрет: `*TOKEN*`, `*SECRET*`, `*PASSWORD*`, `*API_KEY*`, адреса баз
    (`DATABASE_URL`, `*_DSN`), всё с префиксами `CP_`, `CONTROL_PLANE_`, `IAM_`,
    `PACKAGE_SDK_`, а также адреса с паролем внутри. Стенд и база этим тестам не
    нужны. Это не песочница: `HOME` сохраняется, и файлы учётных данных в нём
    коду интеграции доступны.

## Песочница с PostgreSQL { #sandbox }

Сценарии исполняет **код ядра** той версии, что стоит рядом с инструментом:
своего движка процессов, выражений и правил в `package-sdk` нет.

| Субъект | Как исполняется в песочнице | Нужна база |
|---|---|---|
| процесс | движок процессов ядра в памяти: виртуальное время, задачи, согласования и таймеры в памяти, скиллы, агенты и память — заглушки | нет |
| правило, тип задачи | прикладной код ядра: публикация объектов пакета, запись наблюдения, решение гейта, завершение и приёмка — в транзакции, которая всегда откатывается | да |

Для правил и типов задач нужна **пустая** база PostgreSQL 16 с доступным
расширением `pg_trgm` (оно есть в официальных образах `postgres`). Песочница
сама накатывает схему ядра и заводит свой tenant при первом прогоне. Она работает
только с пустой базой или с той, что уже подготовила сама; базу стенда или
чужую отвергает до любой записи.

```bash
docker run -d --rm --name package-sandbox-db \
  -e POSTGRES_PASSWORD=sandbox -p 127.0.0.1:55432:5432 postgres:16-alpine
export PACKAGE_SDK_SANDBOX_DATABASE_URL=postgresql://postgres:sandbox@127.0.0.1:55432/postgres
package-sdk test .
```

Без базы сценарии правил и типов задач помечаются `SKIP` с находкой
`sandbox_database_required`, ступень сценариев — `FAIL`, код выхода `1`.

Каждый тест правила или типа задачи — своя транзакция: тесты не видят друг
друга. У одного теста есть предел по времени (30 секунд), у одного запроса —
не больше 100 таких тестов.

### Песочница и ядро стенда

С `--server` те же файлы уходят ядру стенда (`POST /api/v1/packages:test`,
право `packages.test`), и сценарии исполняет его код. Ничего не записывается.

```bash
export CP_TOKEN=<access token audience control-plane>
package-sdk test . --server https://platform.example.com --workspace <workspace-id>
```

| | Песочница | Ядро стенда |
|---|---|---|
| Каталог | объекты пакета и его `requires` по файлам | каталог tenant'а поверх объектов пакета |
| Версия кода ядра | та, что стоит рядом с инструментом | версия стенда |
| `governedBy` | с базой знаний не сверяется | сверяется |
| Живые экземпляры | нет: пробный прогон `given.fromInstance` недоступен | есть, с правом `processes.read` на workspace |
| Нужно | дополнение `sandbox`, база для правил и типов задач | токен и право `packages.test` |

Песочница и ядро на одних и тех же файлах судят пакет одинаково: тот же
итог, те же находки, те же результаты сценариев и то же покрытие. Расхождение
между ними — ошибка инструмента или ядра, а не пакета.

## Сценарии: процесс, правило, тип задачи { #subjects }

Сценарий — файл `tests/<имя>.test.yaml` по схеме `schema/v1/test.schema.json`.
Что он проверяет, задаёт поле `subject`:

| `subject` | Ключ объекта | `given` | Шаги |
|---|---|---|---|
| `process` (по умолчанию) | `process` | `clock`, `data`, `stage`, `principals`, `calendar`, `settings`, `fromInstance` | `emit`, `advance`, `complete`, `approve`, `settings`, `expect` |
| `rule` | `rule` | ровно одно из `observation`, `event`; `clock`, `variables`, `settings` | только `expect`: `result`, `ensureWork`, `invokeSkill`, `noSideEffects` |
| `taskType` | `taskType` | `task`, `artifacts`, `principals`, `clock`, `variables` | `approve`, `verify`, `complete`, `expect` |

`check` проверяет, что субъект — объект того же пакета, а у процесса — что
`complete.step` и `approve.step` называют его шаги. Ответы скиллов задаёт
`mocks.skills` (`имя@версия` → ответы по порядку вызовов); выход заглушки
сверяется со схемой выхода скилла из каталога.

=== "Процесс"

    ```yaml
    process: claim
    name: a small refund is reviewed, replied and closed without an approval
    given:
      principals: {claims-officer: [alice], claims-manager: [bob]}
    mocks:
      skills:
        claims.classify@1:
          - output: {category: defect, severity: medium, confidence: 0.9}
    steps:
      - emit:
          observation: helpdesk.ticket_created
          payload:
            data: {ticketId: T-1001, customerId: C-7, customerName: Northwind Ltd, product: Grinder X2,
                   subject: The grinder stopped working, text: It stopped after a week., amount: 120, currency: EUR}
      - complete:
          step: review-claim
          by: alice
          output: {resolution: refund, refundAmount: 120, reply: We refund the grinder in full.}
      - expect: {stages: {review: completed, reply: open}}
    ```

    Формат целиком, заглушки агентов и памяти, replay и пробный прогон — в
    [Сценариях и плане ядра](../processes/package-tests.md).

=== "Правило"

    ```yaml
    subject: rule
    rule: claim-reopened
    name: a reopened ticket is filed as a follow-up
    given:
      observation:
        kind: helpdesk.ticket_reopened
        data: {ticketId: T-1001, version: 3, channel: web, subject: The grinder stopped working,
               text: The replacement broke too.}
    mocks:
      skills:
        claims.classify@1:
          - output: {category: defect, severity: medium, confidence: 0.9}
    steps:
      - expect:
          result: matched
          ensureWork:
            - type: claim-followup
              customFields: {ticketId: T-1001}
    ```

    Подробно — в [Правилах в пакете](rules.md#tests).

=== "Тип задачи"

    ```yaml
    subject: taskType
    taskType: claim-reply
    name: an approved reply is sent and completes the task
    given:
      task:
        assignee: alice
        customFields: {ticketId: T-1001, message: We refund it.}
      principals: {claims-officer: [alice, bob]}
    mocks:
      skills:
        helpdesk.reply@1:
          - output: {replyId: R-1, status: closed}
    steps:
      - approve: {decision: approved, by: bob}
      - expect:
          invokeSkill: [{skill: helpdesk.reply@1, inputs: {ticketId: T-1001}}]
          status: {category: terminal_success}
    ```

    Подробно — в [Работе](work.md#tests).

Особенности сценариев правил и типов задач:

- время в них не движется: сроков и таймеров они не проверяют — это дело
  процессов;
- вызов скилла без заглушки остаётся без ответа; если из-за этого правило
  ждёт, тест падает с `unmocked_skill_call`;
- вход, который фоновая оценка правил не стала бы оценивать (другой
  workspace, следствие другого правила), не оценивается и в тесте —
  предупреждение `input_not_delivered` говорит почему;
- обстановку, которую ядро отвергло (например, `given.task` не проходит
  тип), тест показывает ошибкой `given_refused`;
- значения `${ПЕРЕМЕННЫХ}` берутся из `given.variables`, затем из `--env` и
  окружения, затем из `default` манифеста;
- переменные видов `workspace`, `principal` и `role` сценарию задавать не
  нужно: песочница подставляет свои тестовые пространство работы, людей и
  роли, а `workspaceId` вида `${…}` у процесса снимает. Поэтому прогон с
  `--env /dev/null` зелёный и без UUID стенда;
- незаданная переменная другого вида — ошибка `unresolved_install_variable`,
  и только у сценария, которому нужен объект с ней.

Решение по согласованию в сценариях пишется разными словами: голос шага
`approve` процесса — `decision: approve` или `reject`, решение гейта типа
задачи — `decision: approved` или `rejected`.

## Настройки в сценариях { #settings }

Пакет с [настройками](settings.md) проверяет в сценариях и значения по
умолчанию, и смену значения администратором. Песочница хранит версии
настроек так же, как ядро: каждое значение проходит проверку `PUT` — схему
пакета из присланных файлов, `x-ref` и признаки секрета.

| Где | Что задаёт | Версия значений |
|---|---|---|
| нет `given.settings` | действуют `default` схемы | `0` |
| `given.settings` (процесс, правило) | значения, сохранённые к началу сценария | `1` |
| шаг `settings` (только процесс) | администратор сохранил новые значения посреди сценария | следующая; те же значения версии не дают |

Значения в `given.settings` и шаге `settings` — сохранённый набор целиком,
как тело `PUT`: поле, которого нет, берёт `default`, поэтому обязательное поле
без `default` (`escalationRole` пакета `claims`) указывается в каждом наборе.
Вычисления после шага `settings` читают новые значения, а решения, уже
принятые делом, остаются при прочитанных. Состояние дела в `expect` (`data`,
`stages`, `status`, `outcome`) читается у первого дела сценария, выбрать
другое нельзя, поэтому старое и новое дело проверяют разные сценарии:

```yaml
process: claim
name: a raised refund limit does not change the route already chosen
given:
  principals: {claims-officer: [alice], claims-manager: [bob]}
  settings: {refundLimit: 500, escalationRole: 0c000000-0000-4000-8000-000000000001}
steps:
  - emit: {observation: helpdesk.ticket_created, payload: {data: {ticketId: T-1, amount: 800}}}
  - expect: {data: {route: manager}}
  - settings: {refundLimit: 1000, escalationRole: 0c000000-0000-4000-8000-000000000001}  # администратор поднял порог
  - expect: {data: {route: manager}}   # маршрут дела уже выбран
```

```yaml
process: claim
name: a claim opened after the raise follows the new limit
given:
  principals: {claims-officer: [alice], claims-manager: [bob]}
  settings: {refundLimit: 500, escalationRole: 0c000000-0000-4000-8000-000000000001}
steps:
  - settings: {refundLimit: 1000, escalationRole: 0c000000-0000-4000-8000-000000000001}  # администратор поднял порог до первого дела
  - emit: {observation: helpdesk.ticket_created, payload: {data: {ticketId: T-2, amount: 800}}}
  - expect: {data: {route: officer}}   # дело — по новому порогу
```

- Срок, вычисленный из настройки (`due: {workdays: {expr: settings.…}}`), считается
  при входе в шаг: шаг `settings` уже открытый срок не сдвигает.
- В сценарии правила `given.settings` — сохранённые значения на оценку;
  без него и без ссылок правила на `settings` песочница настроек не трогает.
- Значение не по схеме, ссылка `x-ref` на несуществующий объект или материал
  секрета останавливают тест с кодом `settings_invalid`, `unknown_ref` или
  `secret_material_rejected` — без значения в сообщении.
- Пакет, который настроек не объявляет, а сценарий их задаёт, — тест
  останавливается `settings_not_declared`.
- `x-ref` на тип задачи или календарь должен называть объект пакета или его
  `requires`. Id ролей, principal'ов и workspace песочница не проверяет; с
  `--server` их проверяет ядро стенда по организации.
- Код ядра рядом с `package-sdk`, который настроек ещё не знает, даёт ошибку
  `sandbox_settings_unsupported`: обновите `control-plane`.

## Покрытие { #coverage }

Отчёт считает покрытие по всем сценариям пакета вместе функциями ядра и
перечисляет то, чего не прошёл ни один сценарий:

| Субъект | Счётчики |
|---|---|
| процесс | `elements` (стадии, шаги, вехи, таймеры), `transitions`, `decisionRows`, `handlers` |
| правило | `branches` — ветви `condition` и `where`; `outcomes` — итоги оценки, в том числе ответ и провал интерпретации |
| тип задачи | `outcomes` — исходы гейтов и их реакции `onSuccess`/`onFailure`; `preconditions`; `completion` — действия завершения; `acceptance` — исходы критериев приёмки |

Отчёт сквозного примера «претензии клиентов» (см. [Пример](tutorial.md)),
сокращён:

```text
ok   проверка: схема, ссылки, валидаторы ядра
ok   контракты скиллов (skill-sdk export --check)
   ok   claims: ok
ok   тесты кода интеграции (pytest)
   ok   claims: 10 passed in 0.29s
ok   сценарии пакета — песочница ядра
== claims
ok   tests/claim-large-refund.test.yaml: a large refund is approved by a manager who did not review the claim [claim] (22 мс)
ok   tests/claim-reopened.test.yaml: a reopened ticket is classified and filed as a follow-up for the officers [rule claim-reopened] (155 мс)
ok   tests/claim-reply-approved.test.yaml: an approved reply is sent to the helpdesk and completes the task [taskType claim-reply] (197 мс)
…
покрытие claim v1: elements 13/13, transitions 12/12, decisionRows 3/3, handlers 1/1
покрытие правила claim-reopened (тестов 4): branches 6/6, outcomes 4/4
покрытие типа задачи claim-reply v1 (тестов 3): outcomes 4/4
ok (passed): тестов 12, зелёных 12
покрытие — процессы: elements 13/13, transitions 12/12, decisionRows 3/3, handlers 1/1; правила: branches 6/6, outcomes 4/4; типы: outcomes 4/4
ok: пирамида пакетов claims (11612 мс)
```

- Строки `не пройдены (<счётчик>): …` называют непройденные элементы, ветви
  и исходы — это готовый список сценариев, которых не хватает.
- `без сценариев: <пакет>: <вид>/<ключ>` — процесс, правило или тип задачи с
  предметом покрытия, на который в пакете нет ни одного файла сценария.
  Прогон это не валит, но показывает в отчёте.
- `coverage.minimum` в сценарии процесса — порог доли элементов процесса,
  которые проходит этот сценарий, в процентах; ниже порога — провал сценария.
- С `--test` покрытие считается по одному запущенному сценарию: строки
  `не пройдены` и `без сценариев` называют всё, до чего не дошли остальные,
  не запущенные сценарии, и полноты не показывают. Покрытие смотрят по
  прогону без `--test`.

У типа задачи с одними статусами и полями (без гейтов, приёмки и работы
после завершения) предмета покрытия нет, и в отчёте он не появляется: такие
задачи проверяют сценарии процесса, который их заводит. В примере так устроены
`claim-review` и `claim-followup`.

## Код интеграции { #integration-code }

Ступени `skills` и `integration` проверяют код рядом с пакетом:

| Что | Инструмент | Статья |
|---|---|---|
| контракт скилла против YAML пакета | `skill-sdk export --check` — ступень `skills` | [Скиллы пакета](skills.md) |
| логика скилла | `skill_sdk.testing`: `invoke`, `check_contract`, `FakeLlm`, `FakeCore` | [Скиллы пакета](skills.md#tests) |
| цикл наблюдателя | `package_sdk.connector.testing`: `run_once`, `FakeCore` | [Интеграции](integrations.md#tests) |

Сценарии пакета скиллов не исполняют: вызов скилла в сценарии отвечает
заглушка из `mocks.skills`. Поэтому пирамида нужна целиком: код скилла
проверяют unit-тесты, а то, как пакет им пользуется, — сценарии.

Ступени кода интеграции `test` запускает сам: интерпретатором окружения
инструмента и с `integration/src` в `PYTHONPATH`. Флага «только эта
ступень» у `test` нет. Руками те же команды — из каталога `integration/`:

```bash
TOOL="$(uv tool dir)/package-sdk/bin"                 # окружение инструмента
PYTHONPATH=src "$TOOL/skill-sdk" export --package .. <модуль>.skills          # записать skills/*.yaml
PYTHONPATH=src "$TOOL/skill-sdk" export --package .. --check <модуль>.skills  # сверить
PYTHONPATH=src "$TOOL/python" -m pytest -q tests
```

Без `PYTHONPATH=src` модуль интеграции не импортируется
(`ModuleNotFoundError: No module named '<модуль>'`), а системный `pytest` не
видит `skill_sdk` и `package_sdk.connector` — они есть только в окружении
инструмента.

## Проверка в CI { #ci }

`package-sdk init` кладёт рабочую заготовку `.github/workflows/package.yml`: job
выкачивает пакет и компоненты платформы, ставит `package-sdk` из закреплённого
клона, запускает `package-sdk test .` и `package-sdk docs . --check`. Заготовку
достаточно закоммитить — после первого push job зелёный.

Как она устроена:

- **Каталоги.** Пакет выкачивается в каталог с именем его ключа
  (`path: <ключ>`): `check`, `test` и `docs` сверяют имя каталога с ключом.
  Компоненты платформы — соседние клоны в `.platform/`; ключ пакета с точки не
  начинается, поэтому его каталог ни с одним компонентом не совпадёт.
- **Ревизии.** Адрес клонов задаёт переменная `PLATFORM_GIT`: компонент
  клонируется из `$PLATFORM_GIT/<имя>.git`. Ревизию каждого компонента задаёт
  одна переменная `*_REF` — тег `v…` или полный SHA коммита:
  `PACKAGE_SDK_REF`, `CONTROL_PLANE_REF`, `PLATFORM_AUTH_SDK_REF`, а у пакета с
  кодом интеграции (`init --integration`) ещё `SKILL_SDK_REF`. Все шаги job
  читают только эти переменные. `init` заполняет их из установки, в которой
  выполнен: адрес — владелец репозитория `package-sdk`, ревизии — компоненты,
  которые стоят рядом с инструментом. Пустая переменная останавливает job
  первым шагом с ошибкой `not set: …`.
- **Дополнения.** `package-sdk` ставится с `sandbox` (соседи `control-plane` и
  `platform-auth-sdk`); у пакета с кодом интеграции — ещё с `skills` и
  `connector` и с `--with pytest`. Сторонние зависимости кода интеграции
  добавляйте к строке `uv tool install` по одному `--with`.
- **База PostgreSQL** для сценариев правил и типов задач — сервис `postgres` и
  переменная `PACKAGE_SDK_SANDBOX_DATABASE_URL`. `init` включает их сам, если в
  каталоге уже есть правила, типы задач или их сценарии, и по флагу
  `init --database`; иначе блок лежит в файле закомментированным. `package-sdk
  add` правила или типа задачи включает базу в workflow сам. Если блок базы
  правили руками, `add` его не трогает и печатает предупреждение — тогда
  включите базу вручную, иначе job красный на `sandbox_database_required`.
- **README.** Если `README.md` уже есть (например, клон с README хостинга),
  `init` оставляет его текст и дописывает в конец сгенерированный раздел: его
  сверяет шаг `docs --check`, и без раздела job был бы красным с первого push.

Фрагмент заготовки для пакета `acme-claims` с кодом интеграции и сценариями
правил (комментарии и шаг проверки переменных сокращены):

```yaml
jobs:
  check:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16            # закрепите по digest: postgres:16@sha256:…
        env: {POSTGRES_PASSWORD: sandbox, POSTGRES_DB: sandbox}
        ports: ["5432:5432"]
    env:
      PLATFORM_GIT: "https://github.com/<владелец>"
      PACKAGE_SDK_REF: "<тег или полный SHA>"
      CONTROL_PLANE_REF: "<тег или полный SHA>"
      PLATFORM_AUTH_SDK_REF: "<тег или полный SHA>"
      SKILL_SDK_REF: "<тег или полный SHA>"
      PACKAGE_SDK_SANDBOX_DATABASE_URL: postgresql://postgres:sandbox@localhost:5432/sandbox
    steps:
      - name: Pinned revisions        # пустая переменная — ошибка
        run: …
      - uses: actions/checkout@<SHA>  # v4
        with:
          path: acme-claims
          persist-credentials: false
      - uses: astral-sh/setup-uv@<SHA>  # v6
      - name: package-sdk and the components of the platform as sibling directories
        run: |
          mkdir -p .platform && cd .platform
          clone() { … }               # git clone $PLATFORM_GIT/<имя>.git, checkout <ревизия>
          clone package-sdk "$PACKAGE_SDK_REF"
          clone control-plane "$CONTROL_PLANE_REF"
          clone platform-auth-sdk "$PLATFORM_AUTH_SDK_REF"
          clone skill-sdk "$SKILL_SDK_REF"
          uv tool install "./sdk/package-sdk[sandbox,skills,connector]" --with pytest
          echo "$(uv tool dir --bin)" >> "$GITHUB_PATH"
      - name: package-sdk test
        run: package-sdk test .
        working-directory: acme-claims
      - name: The generated README section is up to date
        run: package-sdk docs . --check
        working-directory: acme-claims
```

Правила для любого workflow пакета:

- Инструмент и компоненты платформы ставятся из закреплённых источников —
  клонов на тегах или полных SHA одного выпуска платформы (совместимые
  ревизии — см. [Пакет за 10 минут](quickstart.md#install)). Из публичного
  индекса пакетов их не ставят: таких имён там нет, и так закрыт путь для
  подмены зависимости.
- Переходя на новый выпуск платформы, меняйте значения `*_REF` в одном месте —
  в `env` job.
- Действия в заготовке закреплены по SHA; образ базы закрепляйте по digest.

## Через MCP

Та же пирамида доступна агенту-автору инструментом `pkg_test(path | install,
tests?, server?, workspace_id?, env_file?)` MCP-сервера `package-sdk mcp`:
ответ — отчёт `--json`. См. [Автор пакетов в Claude Code](author-plugin.md).

## Типичные проблемы

| Симптом | Причина | Что делать |
|---|---|---|
| `ERR` на ступени контрактов: «сверке контрактов скиллов нужен skill-sdk» | нет `skill-sdk` в окружении инструмента | переустановить с `[skills]` или `[all]` |
| `ERR` на ступени интеграции: «тестам кода интеграции нужен pytest» | нет `pytest` в окружении инструмента | `uv tool install --reinstall "./sdk/package-sdk[all]" --with pytest` |
| `ModuleNotFoundError` в тестах интеграции | зависимость кода интеграции не в окружении инструмента | добавить её `--with` |
| `ModuleNotFoundError: No module named '<модуль>'` при ручном `skill-sdk export` или `pytest` | код интеграции в `integration/src` не на `sys.path` | запускать из `integration/` с `PYTHONPATH=src` (см. [Код интеграции](#integration-code)) |
| `skill-sdk: command not found` | команда живёт в окружении инструмента `package-sdk` | `"$(uv tool dir)/package-sdk/bin/skill-sdk"` |
| `sandbox_database_required`, ступень сценариев `FAIL` | нет базы для правил и типов задач | задать `PACKAGE_SDK_SANDBOX_DATABASE_URL` или `--database-url` |
| песочница отвергла базу | база не пустая и её готовила не песочница | взять пустую базу |
| `unmocked_skill_call` | правило вызывает скилл, ответа которого нет в `mocks.skills` | добавить заглушку |
| `unresolved_install_variable` | нет значения `${ПЕРЕМЕННОЙ}` | `given.variables`, `.env` или `default` в манифесте |
| сценарий правила ничего не завёл, `input_not_delivered` | вход не дошёл бы до правила и на стенде | проверить `trigger`, workspace и вид наблюдения |
| `нет тестов: … нет сценария '…'` | `--test` не нашёл сценарий | указать `name`, файл или его основу |
| CI: `not set: …` или `PLATFORM_GIT is not set` | пуста переменная ревизии или адреса в `env` job | задать тег или полный SHA компонента одного выпуска (см. [Проверку в CI](#ci)) |
| CI: `cannot clone …: no such repository or no access` | в `PLATFORM_GIT` нет такого репозитория или нет доступа к нему | исправить `PLATFORM_GIT`; приватному репозиторию — дать job доступ |

## См. также

- [Пакет за 10 минут](quickstart.md#test) — первый прогон
- [Сценарии и план ядра](../processes/package-tests.md) — формат сценариев процесса, replay, пробный прогон
- [Правила в пакете](rules.md#tests)
- [Работа: типы задач и роли](work.md#tests)
- [Скиллы пакета](skills.md#tests)
- [Настройки пакета](settings.md) — объявление, ссылки `settings`, права
- [Интеграции](integrations.md#tests)
- [Установка и выпуск](install-and-release.md)
- [Чек-лист готовности пакета](checklist.md)
