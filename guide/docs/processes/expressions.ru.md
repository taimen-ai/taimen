# Выражения

Все выражения языка процессов — условия, ключи, вычисляемые поля, сроки,
назначения, входы таблиц решений, якоря памяти — пишутся на одном языке:
CEL (Common Expression Language) в профиле платформы. Статья для авторов
процессов: переменные, типы, функции календаря, ограничения и перевод
прежних синтаксисов. Обоснование — CP-ADR-0075.

## Профиль `cp/1`

Профиль — это окружение (переменные и их типы), набор функций, запреты и
лимиты. Ядро записывает имя профиля в версию определения
(`expressionProfile`). Новая функция, не меняющая прежних значений,
остаётся в `cp/1`; изменение смысла — новый профиль, и определение на
`cp/1` вычисляется по `cp/1`, пока живы его экземпляры.

!!! note "Одно имя профиля"
    В описаниях схемы каталога профиль может называться по имени продукта с
    тем же номером `/1` — это тот же профиль. Пакеты имя профиля не хранят.

Где встречаются выражения:

| Место | Что даёт выражение |
|---|---|
| `when`, `entry`, `exit`, вехи, `where` триггера | `bool` |
| `start.key`, `correlate[].key` | ключ экземпляра |
| `set`, `output.as`, `export.as`, `start.set`, `correlate[].set` | значение поля данных |
| `input.from`, `call.input`, `decide.input` | вход шага |
| `due.at`, `timeout.at`, `wait.at`, `at` таймеров, `after` эскалаций | `timestamp` или `duration` |
| `assign[].expr`, `approvers[].expr` | id principal'а, `agent:<ключ>` или `role:<slug>` |
| `separationOfDuties` | список principal'ов |
| `title`, `raise.detail`, `suspend.reason` | строка |
| входы таблиц решений (`inputs[].expr`) | значение входа |
| `memory`, якоря `recall` и `context`, `remember` | ключи и значения для базы знаний |

В YAML выражение — строка. Строковый литерал внутри выражения берётся в
одинарные кавычки: `"'invoice:' + data.number"`.

## Переменные { #variables }

| Переменная | Что | Тип |
|---|---|---|
| `data` | данные экземпляра | из JSON Schema `spec.data` |
| `event` | событие входа: `id`, `type`, `time`, `entityType`, `entityId`, `actorId`, `correlationId`, `payload` | `payload` — из каталога событий для `event:` или `map(string, dyn)` |
| `step` | результат шага: `id`, `skill`, `status`, `result`, `error.code`, `error.message`; в блоке — последний завершённый шаг потока, в `output.as` — сам шаг | выход скилла по его схеме, форма задачи, выходы таблицы, ответ `recall` |
| `task` | задача шага: `id`, `publicId`, `typeKey`, `title`, `status`, `assigneeId`, `customFields`, `artifacts`… | `customFields` — по `fieldSchema` типа задачи |
| `stage` | `stage.<id>.completed`, `stage.<id>.active` (или `stage["<id>"]`) | `bool` |
| `instance` | `id`, `key`, `version`, `startedAt`, `clock` | `clock` — время текущего входа |
| `settings` | действующие [настройки пакета](../packages/settings.md#references) процесса; читаются один раз на транзакцию шага | из схемы `spec.settings` манифеста |

Кроме переменных профиля, по месту видны привязки: `milestone.<id>` (вехи
стадий), имя ошибки из `try.catch[].as` в её обработчике и `compensated`
(компенсируемый шаг) внутри `onCompensate`.

`step.result` зависит от вида шага:

| Шаг | `step.result` |
|---|---|
| `human` | поля формы шага (или `fieldSchema` типа задачи) |
| `approve` | `{outcome, approvedBy, rejectedBy}` |
| `call` скилла | выход скилла по его схеме |
| `decide` | выходы строки таблицы; у `collect` — `{items: [...]}` |
| `recall` | `{nodes, edges, truncated}` |
| `listen` | `{option, event}` |

В `output.as` шага `human` видна и его задача `task`: форма даёт только поля,
а кто задачу исполнил — `task.assigneeId`, исполнитель на момент завершения (в
сценарии — `complete.by`). Так сохраняют того, кто разбирал дело, для
разделения обязанностей следующего согласования:

```yaml
- id: review
  human: {taskType: purchase-review, assign: [{role: purchase-buyer}]}
  output:
    as:
      decision: step.result.decision
      reviewedBy: string(task.assigneeId)   # id principal'а строкой
- id: approve-large
  when: data.decision == 'approve'
  approve:
    approvers: [{role: purchase-approver}]
    quorum: any
    separationOfDuties: "[data.reviewedBy]"   # разбиравший не согласует
```

## Переменные установки в выражениях { #install-variables }

`${NAME}` пакета подставляется в файл **текстом до разбора** выражения:
ядро видит уже готовый текст CEL. Отсюда два правила:

```yaml
# PURCHASE_APPROVAL_THRESHOLD=1000 — число в тексте выражения; data.amount — number,
# поэтому целое оборачивают в double(), иначе сравнение int с double не пройдёт проверку
when: data.amount > double(${PURCHASE_APPROVAL_THRESHOLD})

# REVIEW_CHANNEL=portal — строка: без кавычек CEL прочитал бы её как имя переменной
when: data.channel == '${REVIEW_CHANNEL}'
```

Значение с кавычкой или переводом строки ломает выражение — такие значения в
выражения не подставляйте. Объявление
переменных и откуда берутся значения — в [Анатомии пакета](../packages/anatomy.md#variables).

## Типы из схемы данных { #types }

Типы выражений выводятся из JSON Schema данных процесса:

| JSON Schema | CEL |
|---|---|
| `string` | `string` |
| `integer` | `int` |
| `number` | `double` |
| `boolean` | `bool` |
| `array` | `list(T)`; отсутствующий массив — пустой список |
| `object` с `properties` | запись с объявленными полями — обращение к необъявленному полю — **ошибка при публикации** |
| `object` без `properties` | `map(string, dyn)` |
| `format: date-time` | `timestamp` |
| `format: duration` | `duration` |
| `oneOf`, `$ref`, смесь типов | `dyn` — проверяется при вычислении |

Отсутствующее или `null` скалярное поле читается как `null` и падает при
использовании. Для необязательных полей:

```text
has(data.review)                         // есть ли поле
data.?review.orValue('')                 // значение или '' — результат не должен остаться optional
data.?approval.orValue('') == 'approved'
```

Незаданное поле времени без `has()` или `.?` — ошибка вычисления: иначе оно
читалось бы как 1970 год.

## Функции

### Календарь { #calendar }

| Функция | Что возвращает |
|---|---|
| `cal.addWorkdays(ts, n)` | `n`-й рабочий день после дня `ts` (при `n < 0` — до него); сам день `ts` не считается, `n = 0` — тот же момент; время суток сохраняется в поясе календаря |
| `cal.isWorkday(ts)` | рабочий ли день `ts` |
| `cal.workdaysBetween(a, b)` | число рабочих дней в `(a, b]`, при `b < a` — со знаком минус |
| `cal.addWorkingTime(ts, d)` | момент через длительность `d` рабочего времени от `ts` по [рабочим часам](index.md#working-hours) календаря; отрицательная `d` — назад, нулевая — сам `ts` |
| `cal.workingTimeBetween(a, b)` | длительность рабочего времени между `a` и `b` |

Последний аргумент — ключ календаря (`cal.addWorkdays(ts, -3, 'ru')`). Его
можно опустить, если у процесса есть `spec.calendar`; без календаря
процесса короткая форма — ошибка типа при публикации.

- День рабочий, если он в `workdays` года; иначе — если он не в `holidays` и
  не выходной день недели. Для года, которого в календаре нет, известны
  только выходные дни недели.
- Вычисление, которое задело предварительный год (`provisional: true`) или
  год вне календаря, помечается «предварительно».
- Функции рабочего времени требуют календарь с `workingHours`. Календарь без
  часов — ошибка `expression_error` с `details.reason =
  calendar_without_hours`; рабочее время не нашлось в пределах просмотра —
  `calendar_scan_limit`.

```yaml
due: {at: "cal.addWorkdays(data.submissionEnd, -3)"}   # за три рабочих дня до даты
when: cal.workdaysBetween(instance.clock, data.submissionEnd) < 3
due: {at: "cal.addWorkingTime(data.receivedAt, duration('PT8H'))"}   # восемь рабочих часов от получения
```

### Время и длительности

- `duration("P3D")` принимает литерал ISO 8601 (недели, дни, часы, минуты,
  секунды; годы и месяцы — ошибка типа) и форму CEL (`duration("72h")`).
  Строка ISO, вычисленная во время работы, не разбирается — длительности
  данных типизируются схемой (`format: duration`).
- `timestamp("2026-10-19T09:00:00+03:00")` — RFC 3339.
- Арифметика: `data.submissionEnd - duration("72h")`,
  `instance.clock < data.submissionEnd`.

### Строки, списки, макросы

- Строки: `lowerAscii`, `split`, `join`, `replace`, `substring` и другие
  функции расширения `strings`.
- Списки: `size`, `in`, `slice`, `flatten`, `sort`, `distinct`.
- Макросы: `all`, `exists`, `map`, `filter`:
  `size(data.history.filter(n, n.kind == 'lesson')) > 0`.
- Необязательные значения: `.?поле`, `orValue(…)`.
- `cel.bind(имя, значение, выражение)` — локальное имя.

## Чего нет

- **Текущего времени.** Функции `now()` нет, её вызов — ошибка типа с
  подсказкой. Время входит в выражение только как `instance.clock` и
  `event.time` — их задаёт вход движка. Поэтому одно выражение на одних
  входах даёт одно значение в живом прогоне, тесте и replay.
- **Случайности, ввода-вывода, обращений к памяти и каталогу.** База знаний
  попадает в выражения только через записанный ответ `recall`, календарь —
  версией, записанной в журнале.
- **Побочных эффектов.** Запись в данные — только `set` и `output.as`.
- **Шаблонов `{{…}}`.** Они остаются у правил вывода работы и правил
  уведомлений; в процессах их нет.

## Лимиты

| Лимит | Значение | Когда проверяется |
|---|---|---|
| длина выражения | 4000 символов | схема каталога |
| глубина дерева выражения | 32 | при публикации (`expression_too_complex`) |
| вложенность итерирующих макросов | 3 | при публикации (`expression_too_complex`) |
| стоимость вычисления | 10 000 единиц | перед вычислением, по размерам входов (`expression_cost_exceeded`) |

Стоимость оценивается сверху до вычисления: шаг на сегмент пути, вызов
функции, итерации макросов по размеру списка. Выше лимита вычисление не
запускается: шаг получает ошибку `expression_cost_exceeded`, её ловит `try`,
иначе экземпляр переходит в `failed` с понятной причиной — процесс не
зависает молча.

## Ошибки

Ошибки разбора приходят находками проверки с местом в файле и позицией в
выражении:

```json
{"code": "expression_type_error", "severity": "error",
 "path": "/spec/stages/0/steps/1/human/due/at", "file": "processes/purchase.yaml",
 "line": 31, "message": "no such field 'submisionDeadline' at 1:34",
 "hint": "data.procurement has submissionDeadline"}
```

| Код | Когда |
|---|---|
| `expression_syntax_error` | синтаксис |
| `expression_type_error` | тип: неизвестное поле, `now()`, не тот тип результата по месту (ждали `bool`, `timestamp` или `duration`, список) |
| `expression_too_complex` | глубина или вложенность макросов |
| `expression_error` | при вычислении: `null`, отсутствующее поле, нет календаря |
| `expression_cost_exceeded` | превышен лимит стоимости |

## Частые ошибки

| Ошибка | Правильно |
|---|---|
| `title: 'Счёт ' + data.number` — YAML съел кавычки, CEL видит `Счёт` без кавычек | `title: "'Счёт ' + data.number"` |
| `when: data.note != ''` на необязательном поле | `when: data.?note.orValue('') != ''` |
| `due: {at: "now() + duration('P1D')"}` | `due: P1D` или `{at: "cal.addWorkdays(instance.clock, 1)"}` |
| `set: {total: data.amount * 1.2}` при `amount: {type: integer}` | в CEL `int` и `double` не смешиваются: `double(data.amount) * 1.2` |
| `data.?approval` в конце выражения | результат не может остаться optional: `data.?approval.orValue('')` |
| сторож стадии читает результат шага | сторожа стадий и вехи читают `data`, `stage` и `milestone`: запишите результат шага в данные через `output.as` |
| булево значение строкой `set: {done: "yes"}` | `set: {done: "true"}` — строка YAML с выражением `true` |

## Перевод прежних синтаксисов

Правила вывода работы, исходы approval, входы исполнения типов задач и
профиль контекста исторически используют свои синтаксисы путей. Они
продолжают работать, пока пакеты не переведены, а для перевода есть
команда:

```bash
package-sdk migrate-expr --package packages/<пакет>          # diff, ничего не пишет
package-sdk migrate-expr --package packages/<пакет> --write  # записать
```

- Команда печатает diff по файлам; `--write` записывает с сохранением файла
  (комментарии, порядок ключей и стиль остаются).
- Выражения ищет и переводит ядро: нужен control-plane с профилем CEL в
  `PYTHONPATH` (или интерпретатор его uv-окружения).
- Процессы и календари уже на CEL и командой не трогаются.
- То, что не переводится, печатается с причиной и остаётся как было; если
  перевод читает переменные сверх профиля (например `spawnedBy`), это тоже
  печатается.

| Прежнее | CEL |
|---|---|
| `{"var": "payload.data.repo"}` | `event.payload.?data.?repo.orValue(null)` |
| `{"exists": "payload.data.url"}` | `event.payload.?data.?url.orValue(null) != null` |
| `{"lt": [{"var": "x"}, 3]}` | `x != null && x < 3` |
| `$.task.customFields.branch` | `task.customFields.?branch.orValue(null)` |
| `$.task.customFields.branch!` | `task.customFields.branch` (нет поля — ошибка) |
| `$.task.artifact[commit].metadata.sha` | `task.artifacts.?commit.?metadata.?sha.orValue(null)` |
| `$.invocation.output.x` | `step.result.?x.orValue(null)` |
| шаблон `"Merge $.task.publicId!: $.task.title"` | конкатенация; отсутствующее — `""` |
| `execution.inputs: $.customFields.url` | `task.customFields.?url.orValue(null)` |
| `from: "$.customFields.okpdCodes"` | `task.customFields.?okpdCodes.orValue(null)` |

!!! warning "Где перевод расходится с прежним вычислением"
    `0` в `when` прежде считался невыполненным условием, в CEL — выполненным;
    нестроковое значение в шаблоне печатается `true`, а не `True`;
    обязательное `!` на поле с пустой строкой прежде давало отказ, в CEL —
    `""`. Проверьте такие места после перевода.

## См. также

- [Процессы](index.md)
- [Тесты пакета](package-tests.md)
- [Схема пакета](../reference/package-schema.md#schema-cel)
- [Правила вывода работы](../control-plane/work-rules.md)
