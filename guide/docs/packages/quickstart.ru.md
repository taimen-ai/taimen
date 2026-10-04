<!--
Эту страницу исполняет job «quickstart» в CI package-sdk (ci/quickstart.py, SC-001):
блоки bash — команды, блоки с разметкой «quickstart: file <путь>» — файлы, «skip» —
шаги со стендом. Блок YAML без разметки и неизвестная подстановка <…> ломают job.
Меняя команды или файлы, сдвиньте закрепление в package-sdk (pin update).
-->
# Пакет за 10 минут

Пошаговый путь от пустого каталога до пакета с типом задачи, правилом вывода
работы и процессом, который проходит проверку и тесты без стенда, — и затем до
установки на стенд разработчика по плану. Страница для автора, который видит
`package-sdk` впервые. Понятия — в [обзоре раздела](index.md).

Пример — пакет `access-requests` «заявки на доступ»: заявка на доступ к
ресурсу открывает дело, владелец решает по задаче, дело закрывается; повторно
открытая заявка по правилу заводит новую задачу на разбор.

## Что понадобится

| Что | Зачем |
|---|---|
| `git`, [uv](https://docs.astral.sh/uv/), Python 3.12+ | клоны компонентов и установка инструмента |
| Docker (или любой PostgreSQL 16) | пустая база для сценариев правил и типов задач |
| Стенд разработчика и токен с правом `packages.plan` и правами на ставимые виды объектов (`task_types.manage`, `agents.manage`, `processes.write`, `calendars.write`, `rules.write` — `apply` перепроверяет ими каждое изменение; `org.manage` — роли пакета, их секция `catalog` создаёт через `POST /roles`) | только для последнего шага — `plan` и `apply` |

## 1. Установить package-sdk { #install }

Проверки и тесты без стенда исполняет **код ядра** — дополнение `sandbox`
ставит пакет `control-plane` рядом с инструментом. Компоненты платформы не
ставятся из публичного индекса пакетов: их подключают исходниками в раскладке
корневого репозитория поставки (`services/`, `sdk/`).

```bash
mkdir taimen-src && cd taimen-src
git clone --branch <тег> https://github.com/taimen-ai/package-sdk.git sdk/package-sdk
git clone --branch <тег ядра> https://github.com/taimen-ai/control-plane.git services/control-plane
git clone --branch <тег> https://github.com/taimen-ai/platform-auth-sdk.git sdk/platform-auth-sdk
uv tool install "./sdk/package-sdk[sandbox]"
package-sdk --version
```

- Теги берите из одного выпуска платформы. `<тег ядра>` — выпуск Control
  Plane, на который вы будете ставить пакет: `init` запишет в манифест
  совместимость ровно с его minor-версией.
- Сводной таблицы «выпуск платформы → теги компонентов» пока нет. Совместимые
  ревизии — те, что закрепляет корневой репозиторий поставки на теге выпуска:
  `git submodule status` в его клоне на этом теге печатает ревизию каждого
  компонента (см. [Обновление](../operations/upgrades.md)). Клон корневого
  репозитория с сабмодулями уже разложен так, как нужно `uv tool install`.
- Дополнениям `skills`, `mcp` и `all` нужен ещё один сосед — `skill-sdk`
  (`git clone --branch <тег> https://github.com/taimen-ai/skill-sdk.git sdk/skill-sdk`
  рядом с остальными SDK): без него установка с этими дополнениями не соберётся. Какие
  соседи нужны какому дополнению — в [Тестах пакета](testing.md#install).
- Дополнение ставит соседние каталоги в режиме редактирования: клоны должны
  оставаться на месте, пока инструмент установлен.
- Команда `package-sdk` без аргументов печатает список команд.

!!! tip "Без кода ядра"
    `uv tool install ./sdk/package-sdk` без `[sandbox]` ставит только инструмент.
    Тогда `check` проверяет схему и ссылки и завершается ошибкой «доменные
    валидаторы ядра не импортируются»: молча ограничиться схемой он не станет.
    Явный режим одной схемы — `check --schema-only`. `test` без кода ядра не
    идёт дальше ступени проверки.

## 2. Создать пакет { #init }

```bash
cd ..
package-sdk init access-requests --display-name "Access requests"
cd access-requests
```

```text
создан access-requests/package.yaml
создан access-requests/processes/access-requests.yaml
создан access-requests/agents/access-requests-process.yaml
создан access-requests/roles/access-requests-owner.yaml
создан access-requests/tests/access-requests.test.yaml
создан access-requests/.github/workflows/package.yml
создан access-requests/.gitignore
создан access-requests/README.md
```

Заготовка сразу проходит проверку и свой тест. В ней:

- `package.yaml` — ключ пакета (по умолчанию — имя каталога), версия `0.1.0`,
  `engines` с диапазоном версии ядра, пустые `variables`. Каталог пакета и
  дальше должен называться его ключом: `check` и `test` по пути каталога
  сверяют их (см. [Анатомию](anatomy.md#layout));
- процесс с ключом пакета, его **личность** — агент
  `access-requests-process` (от его имени процесс заводит задачи) — и
  **роль владельца** `access-requests-owner`;
- тест процесса, заготовка CI и README с разделом, который генерирует
  `package-sdk docs`.

Первая строка YAML-файлов, которые пишут `init` и `add`, — комментарий
`# yaml-language-server: $schema=…` со ссылкой на схему установленного SDK:
редактор с поддержкой YAML Language Server подсказывает поля и подсвечивает
ошибки. В примерах ниже эта строка опущена. Заменяя содержимое файла, её
стоит сохранить — на проверку и тесты она не влияет.

!!! warning "Ссылка на схему — путь на вашей машине"
    `$schema=…` — относительный путь от файла до схемы в окружении
    установленного инструмента. У коллеги с другим каталогом инструментов
    ссылка в git не откроется. Стабильного адреса схемы выпуска пока нет:
    для общего репозитория замените путь на путь к `schema/v1/object.schema.json`
    (`test.schema.json` у сценариев) в клоне `package-sdk` по общему соглашению
    команды или уберите строку — на проверку и тесты она не влияет.

## 3. Тип задачи { #task-type }

```bash
package-sdk add task-type access-review
```

`add` пишет минимальный `spec`, который проходит схему и проверки ядра, и
перечисляет в комментариях необязательные поля с описаниями из схемы.
Замените содержимое `task-types/access-review.yaml`:

<!-- quickstart: file task-types/access-review.yaml -->
```yaml
apiVersion: taimen.ai/v1
kind: TaskType
key: access-review
spec:
  displayName: Access review
  description: A decision on an access request
  fieldSchema:
    type: object
    properties:
      requestId: {type: string}
      resource: {type: string}
      decision: {type: string, enum: [granted, denied]}
  lifecycleSchema:
    statuses:
      - {key: todo, category: active, displayName: To do}
      - {key: in_progress, category: active, displayName: In progress}
      - {key: done, category: terminal_success, displayName: Done}
      - {key: cancelled, category: terminal_cancelled, displayName: Cancelled}
    transitions:
      - {from: todo, to: [in_progress, done, cancelled]}
      - {from: in_progress, to: [todo, done, cancelled]}
    initialStatus: todo
    claimStatus: in_progress
    releaseStatus: todo
    completionStatus: done
  instructions: |
    Check who asks for access and to what. Record the decision
    in the field `decision`: granted or denied.
```

Поля задачи — `fieldSchema`, статусы и переходы — `lifecycleSchema`, текст
для исполнителя — `instructions`. Что ещё умеет тип — в
[Работе](work.md#task-types).

## 4. Процесс { #process }

Замените содержимое `processes/access-requests.yaml`: наблюдение
`access.requested` открывает дело, шаг `human` заводит задачу типа
`access-review` на роль владельца, её результат попадает в данные дела, и дело
закрывается.

<!-- quickstart: file processes/access-requests.yaml -->
```yaml
apiVersion: taimen.ai/v1
kind: Process
key: access-requests
spec:
  version: 1
  displayName: Access request
  identity: {agent: access-requests-process}
  owner: [{role: access-requests-owner}]
  data:
    type: object
    properties:
      requestId: {type: string}
      resource: {type: string}
      decision: {type: string}
  start:
    "on": {observation: access.requested}
    key: event.payload.id
    set:
      requestId: event.payload.id
      resource: event.payload.resource
  stages:
    - id: review
      steps:
        - id: review-request
          human:
            taskType: access-review
            assign: [{role: access-requests-owner}]
          output: {as: {decision: step.result.decision}}
        - id: close
          complete: {outcome: reviewed}
```

Ключ `on` взят в кавычки: так файл одинаково читают инструменты на YAML 1.2 и
YAML 1.1.

Тест процесса — замените `tests/access-requests.test.yaml`:

<!-- quickstart: file tests/access-requests.test.yaml -->
```yaml
process: access-requests
name: a request is closed after its review
given:
  principals: {access-requests-owner: [alice]}
steps:
  - emit:
      observation: access.requested
      payload: {id: A-1, resource: billing}
  - expect:
      stages: {review: open}
      tasks: [{step: review-request}]
  - complete: {step: review-request, by: alice, output: {decision: granted}}
  - expect: {status: completed, outcome: reviewed}
```

`given.principals` — кто в тесте держит роль; `complete` сдаёт задачу шага
от имени `alice` с результатом формы.

## 5. Правило вывода работы { #rule }

```bash
package-sdk add rule access-reopened
```

Замените содержимое `rules/access-reopened.yaml`:

<!-- quickstart: file rules/access-reopened.yaml -->
```yaml
apiVersion: taimen.ai/v1
kind: WorkRule
key: access-reopened
spec:
  description: A reopened access request is filed for a new review
  trigger: {kind: observation, type: access.reopened}
  condition:
    exists: payload.data.requestId
  action:
    kind: ensure_work
    taskType: access-review
    dedupKeyTemplate: "access-reopened:{{payload.data.requestId}}"
    fields:
      title: "Review reopened access request {{payload.data.requestId}}"
      customFields:
        requestId: "{{payload.data.requestId}}"
```

Два теста правила — на обе ветки условия. `tests/access-reopened.test.yaml`:

<!-- quickstart: file tests/access-reopened.test.yaml -->
```yaml
subject: rule
rule: access-reopened
name: a reopened request is filed for review
given:
  observation:
    kind: access.reopened
    data: {requestId: A-2}
steps:
  - expect:
      result: matched
      ensureWork:
        - type: access-review
          customFields: {requestId: A-2}
```

`tests/access-reopened-no-id.test.yaml`:

<!-- quickstart: file tests/access-reopened-no-id.test.yaml -->
```yaml
subject: rule
rule: access-reopened
name: an observation without a request id files nothing
given:
  observation:
    kind: access.reopened
    data: {}
steps:
  - expect:
      result: not_matched
      ensureWork: []
```

## 6. Проверить { #check }

```bash
package-sdk check --package .
```

```text
ok: пакетов 1, объектов 5, тестов 3
```

`check` сверяет файлы со схемой, ссылки между объектами (правило → тип
задачи, процесс → агент и роль, тест → свой объект), манифест и прогоняет
доменные валидаторы ядра: типы задач, правила, скиллы, агенты. Язык процессов —
выражения, данные, достижимость шагов — ядро проверяет перед сценариями в
`test` (и по `check --server`). Ошибка печатается с файлом и подсказкой;
`--json` отдаёт находки документом.

## 7. Прогнать тесты { #test }

Сценарии правил и типов задач исполняет прикладной код ядра в транзакции,
которая всегда откатывается, — для этого нужна пустая база PostgreSQL.
Песочница сама накатывает на неё схему ядра и заводит свой tenant.
Поднимите базу и передайте её адрес:

<!-- quickstart: requires docker -->
```bash
docker run -d --rm --name package-sandbox-db \
  -e POSTGRES_PASSWORD=sandbox -p 127.0.0.1:55432:5432 postgres:16-alpine
for _ in $(seq 30); do   # база поднимается несколько секунд
  docker exec package-sandbox-db pg_isready -q -h 127.0.0.1 -U postgres && break
  sleep 1
done
export PACKAGE_SDK_SANDBOX_DATABASE_URL=postgresql://postgres:sandbox@127.0.0.1:55432/postgres
```

Прогоните тесты:

<!-- quickstart: without-docker exit=1 output=sandbox_database_required -->
```bash
package-sdk test .
```

```text
ok   проверка: схема, ссылки, валидаторы ядра
SKIP контракты скиллов (skill-sdk export --check)
   SKIP access-requests: нет кода интеграции (integration/)
SKIP тесты кода интеграции (pytest)
   SKIP access-requests: нет тестов кода интеграции (integration/tests/)
ok   сценарии пакета — песочница ядра
== access-requests
ok   tests/access-reopened-no-id.test.yaml: an observation without a request id files nothing [rule access-reopened] (189 мс)
ok   tests/access-reopened.test.yaml: a reopened request is filed for review [rule access-reopened] (168 мс)
ok   tests/access-requests.test.yaml: a request is closed after its review [access-requests] (7 мс)
покрытие access-requests v1: elements 3/3
покрытие правила access-reopened (тестов 2): branches 2/2, outcomes 2/2
ok (passed): тестов 3, зелёных 3
покрытие — процессы: elements 3/3; правила: branches 2/2, outcomes 2/2
ok: пирамида пакетов access-requests (3628 мс)
```

`test` — одна команда пирамиды: проверка, контракты скиллов кода интеграции,
его unit-тесты и сценарии пакета. У этого пакета нет кода интеграции, поэтому
две средние ступени пропущены — это не провал. Адрес базы можно передать и
флагом `--database-url`.

!!! warning "Без базы прогон не зелёный"
    Если базы нет, сценарии правил и типов задач помечаются `SKIP` с находкой
    `sandbox_database_required`, ступень сценариев — `FAIL`, код выхода `1`.
    Молча такие тесты не пропускаются. Сценарии процессов базы не требуют.

Контейнер базы после работы можно остановить: `docker stop package-sandbox-db`.

## 8. Описать пакет { #describe }

Из каталога пакета:

```bash
package-sdk describe .
package-sdk docs . --write
```

`describe` печатает, что нужно установке: совместимость, зависимости,
переменные, агентов и метки узлов, онтологии. `docs --write` обновляет
сгенерированный раздел README (объекты, переменные, требования, агенты);
`docs --check` в CI падает, если раздел устарел.

## 9. Установить на стенд разработчика { #deploy }

Установка — отдельный файл: какие пакеты и откуда ставить. Он лежит рядом с
каталогом пакета — вернитесь в родительский каталог:

```bash
cd ..
```

и положите туда `installation.yaml`:

<!-- quickstart: file installation.yaml -->
```yaml
apiVersion: taimen.ai/v1
kind: Installation
key: dev
spec:
  packages:
    - {key: access-requests, path: access-requests}
```

Зафиксируйте источники — `package-sdk lock` пишет рядом `packages.lock` с
версией и хэшем содержимого каждого пакета (для пакета из git — ещё и
коммит тега):

```bash
package-sdk lock --install installation.yaml
```

```text
   access-requests 0.1.0: access-requests sha256:…
записан packages.lock
```

План и применение требуют стенда. Токен — переменная `CP_TOKEN` (access
token audience `control-plane`) или IAM credential в
`~/.config/iam/credentials.json`:

<!-- quickstart: skip нужен стенд разработчика -->
```bash
export CP_TOKEN=<access token>
package-sdk plan --install installation.yaml \
    --server https://platform.example.com --out plan.json
package-sdk apply --plan plan.json --server https://platform.example.com
```

- `plan` проверяет пакеты, сверяет версию ядра стенда с `engines`, строит
  изменения всех видов и сохраняет их в `plan.json`, ничего не записывая.
- `apply` показывает план, спрашивает подтверждение в терминале и применяет
  ровно его. Изменился стенд или файлы после `plan` — `plan_stale` до первой
  записи; постройте план заново.

Подробнее об установке, переменных и источниках — в
[Анатомии пакета](anatomy.md#installation).

## Типичные проблемы

| Симптом | Причина | Что делать |
|---|---|---|
| `check`: «доменные валидаторы ядра не импортируются — проверена только схема формата» | инструмент поставлен без `[sandbox]` | переустановить `uv tool install --reinstall "./sdk/package-sdk[sandbox]"` |
| `test`: `sandbox_database_required`, прогон `FAIL` | нет базы для сценариев правил и типов задач | задать `PACKAGE_SDK_SANDBOX_DATABASE_URL` или `--database-url` |
| `engines_mismatch` в предупреждениях | пакет объявляет другую версию ядра, чем код ядра рядом с инструментом | поставить клон ядра нужного тега или поправить `engines` |
| `init`: «уже есть — заготовка не перезаписывает файлы» | в каталоге уже есть файлы пакета | взять пустой каталог; `.gitignore` заготовка оставляет как есть, а в существующий `README.md` дописывает сгенерированный раздел |
| `plan`: «версия ядра не прочитана … план не строится» | стенд недоступен по `--server` | проверить адрес и сеть; `plan` и `apply` без стенда не работают |
| `apply`: «нужен ответ человека в терминале, применение отменено» | команда запущена без терминала | запустить в терминале и подтвердить план |

## См. также

- [Пакеты](index.md) — вертикаль как пакет, карта видов
- [Анатомия пакета](anatomy.md) — манифест, версии, установка
- [Работа: типы задач и роли](work.md)
- [Правила в пакете](rules.md)
- [Процессы в пакете](processes.md)
- [Тесты пакета](testing.md) — пирамида, песочница, покрытие, CI
- [Установка и выпуск](install-and-release.md) — lock, план, применение, выпуск
- [Сценарии и план ядра](../processes/package-tests.md) — формат сценариев процессов
