# Настройки пакета

Настройки — значения, которые администратор организации меняет в работающей
системе без новой версии пакета и без плана установки: порог согласования,
срок проверки, роль для эскалации. Пакет объявляет их форму в манифесте, ядро
хранит значения с историей, процессы, правила и экраны пакета читают их как
`settings.<поле>`. Первая половина страницы — для автора пакета, вторая — для
администратора. Обоснование — TAI-ADR-0067, CP-ADR-0081.

## Настройка или переменная установки { #settings-or-variables }

У пакета два способа не зашивать значение в файлы. Они не заменяют друг друга:

| | Переменная установки `${NAME}` | Настройка `settings.<поле>` |
|---|---|---|
| Где объявлена | `spec.variables` манифеста | `spec.settings` манифеста |
| Где лежит значение | файл установки, `.env`, окружение | ядро, с историей версий |
| Кто и как меняет | автор установки: правка, `plan`, `apply` | администратор: консоль или `PUT /api/v1/packages/{key}/settings` |
| Когда действует | после `apply` новой ревизии объектов | на следующем вычислении, без плана и без новой версии процесса |
| Как попадает в объект | текстом в файл до разбора выражения | переменная `settings` с типами из схемы |
| Что подходит | топология стенда: id workspace, адрес системы | правила игры организации: пороги, сроки, роли |
| Секреты | нет (секреты — в credential и подключениях) | нет: схема и значения с признаками секрета отвергаются |

Если значение меняет бизнес, а не тот, кто ставит пакет, — это настройка.
Переменные установки — в [Анатомии пакета](anatomy.md#variables).

## Объявление { #declaration }

Настройки объявляет раздел `spec.settings` манифеста `package.yaml`: схема
значений `schema` и необязательная раскладка формы `uischema`.

```yaml
apiVersion: taimen.ai/v1
kind: Package
key: claims
spec:
  version: 0.2.0
  locales: [en, ru]
  defaultLocale: en
  settings:
    schema:
      type: object
      properties:
        refundLimit: {type: number, minimum: 0, default: 500}
        replyDueWorkdays: {type: integer, minimum: 1, maximum: 20, default: 2}
        escalationRole: {type: string, x-ref: role}
      required: [escalationRole]
    uischema:
      type: VerticalLayout
      elements:
        - type: Group
          label: claims.settings.groups.refund
          elements:
            - {type: Control, scope: "#/properties/refundLimit"}
            - {type: Control, scope: "#/properties/escalationRole"}
        - type: Group
          label: claims.settings.groups.reply
          elements:
            - {type: Control, scope: "#/properties/replyDueWorkdays"}
```

### Подмножество JSON Schema { #schema }

`schema` — подмножество JSON Schema, как у данных процесса. Корень — объект,
имя поля — camelCase (`^[a-z][A-Za-z0-9_]{0,62}$`): по нему поле читают
выражения.

| Ключевое слово | У каких типов |
|---|---|
| `type` | `string`, `integer`, `number`, `boolean`, `array`, `object` |
| `properties`, `required` | `object` |
| `items`, `minItems`, `maxItems` | `array`; `minItems`, `maxItems` — целые от 0 |
| `enum` | скаляры, до 100 значений |
| `minimum`, `maximum` | `integer`, `number` |
| `minLength`, `maxLength`, `pattern`, `format` | `string`; `format` — `date`, `uri`, `email`, `uuid` |
| `default` | любые; значение должно проходить схему поля |
| `x-ref` | `string`: ссылка на объект платформы (ниже) |

Пределы: объекты вложены не глубже трёх уровней с корнем, на третьем уровне
массив держит только скаляры; у объекта не больше 100 свойств.
`additionalProperties` допустим только как `false` (он и так подразумевается).
`title` и `description` в схеме не пишут: подписи берутся из словарей пакета
(см. [Подписи](#labels)).

`x-ref` говорит, что строка ссылается на объект платформы в организации. При
сохранении ядро проверяет, что объект есть и в обороте:

| `x-ref` | Значение | «В обороте» |
|---|---|---|
| `role` | id роли | роль есть в организации |
| `principal` | id principal'а | principal не отключён |
| `workspace` | id workspace (не slug) | workspace активен |
| `taskType` | ключ типа задачи | есть активная версия |
| `calendar` | ключ календаря | календарь не выведен из оборота |

### Значения по умолчанию { #defaults }

У каждого **необязательного** скалярного поля и массива есть `default`: пакет
работает сразу после установки, ничего не сохраняя. Необязательному объекту
`default` не нужен — он собирается из значений по умолчанию своих полей.

Обязательное поле (`required`) может обойтись без `default`, но тогда до
первого сохранения у него нет действующего значения, и объект пакета обязан
это учитывать: `has(settings.escalationRole)` в CEL. Ссылке на роль, principal
или workspace `default` не дают: id у каждой организации свой, такое поле
объявляют обязательным.

### Секреты не в настройках { #no-secrets }

Настройки видят все, у кого есть право чтения, их значения уходят агентам и
скиллам пакета. Поэтому признаки секрета отвергаются ещё в объявлении:
`writeOnly`, `format: password`, имя поля вроде `password`, `secret`, `token`,
`apiKey`, `privateKey`, `credential`, `authorization`, `clientSecret` (имя
`secretRef` допустимо), материал секрета в `default` или `enum`. Секрет
принадлежит подключению или именованному секрету агента.

## Подписи { #labels }

Строк формы в схеме нет: подписи — ключи словарей пакета `i18n/<язык>.yaml`.
Пакет с настройками объявляет языки в манифесте (`locales`, `defaultLocale`),
и каждый обязательный ключ есть в словаре каждого объявленного языка.

| Строка | Ключ словаря | Обязателен |
|---|---|---|
| имя пакета на экране настроек | `<пакет>.title` | да |
| подпись поля | `<пакет>.settings.<путь>` | да, у каждого свойства |
| пояснение под полем | `<пакет>.settings.<путь>.help` | нет |
| заголовок группы (`label` у `Group`) | `<пакет>.settings.groups.<id>` | да |
| `label` у `Control`, `text` у `Label` | любой ключ словаря пакета | да |

`<путь>` — имена свойств через точку от корня схемы (`limits.refund`). У
свойств объектов внутри `items` массива подписей нет: форма показывает массив
целиком.

```yaml
# i18n/ru.yaml
claims.title: Претензии клиентов
claims.settings.refundLimit: Возврат без согласования, до
claims.settings.refundLimit.help: >-
  Возврат больше этой суммы согласует руководитель претензий. Дела, где решение
  уже принято, остаются при прежнем пороге
claims.settings.replyDueWorkdays: Срок ответа клиенту, рабочих дней
claims.settings.escalationRole: Роль для эскалации
claims.settings.groups.refund: Возвраты
claims.settings.groups.reply: Ответ клиенту
```

Ядро отдаёт строки на языке запроса (`?locale=`); языка нет в пакете — на
`defaultLocale`.

## Раскладка формы — `uischema` { #uischema }

`uischema` — закрытое подмножество JSON Forms, которое рисует консоль. Без
неё консоль ставит поля столбцом в порядке схемы, вложенный объект — группой.

| `type` | Поля | Что |
|---|---|---|
| `VerticalLayout` | `elements` | элементы столбцом |
| `HorizontalLayout` | `elements` | элементы в строку |
| `Group` | `label`, `elements` | рамка с заголовком |
| `Control` | `scope`, `label?` | поле формы |
| `Label` | `text` | строка текста |

- Корень — `VerticalLayout`, `HorizontalLayout` или `Group`; вложенность не
  больше 5, элементов всего не больше 200.
- `scope` — указатель на свойство схемы: `#/properties/<поле>`, вложенное —
  `#/properties/<a>/properties/<b>`. Одно свойство — не больше одного
  `Control`; указатель внутрь `items` массива не допускается.
- У любого элемента — необязательное `rule`: `effect` (`SHOW`, `HIDE`,
  `ENABLE`, `DISABLE`) и `condition {scope, schema}`, где `schema` — `const`,
  `enum` или `minimum`/`maximum`. Правило меняет только вид формы: скрытое поле
  всё равно сохраняется и проверяется.
- Поле без `Control` в заданной `uischema` — предупреждение
  `settings_uischema_uncovered`: значение действует, но в форме его не
  поменять.
- Других полей у элементов нет: `options` у `Control` (`multi`,
  `format: radio` из JSON Forms) ядро отвергает при плане с кодом
  `settings_uischema_unsupported`.

## Чтение настроек — `settings` { #references }

Объект пакета читает настройки своего пакета по имени `settings`. Чужой пакет
и объект, заведённый вручную, а не пакетом, настроек не видят: ссылка на
`settings` в нём — ошибка публикации `settings_ref_unknown`.

| Где | Как | Когда читается |
|---|---|---|
| Процесс | переменная CEL `settings.<путь>` с типами из схемы | один раз на транзакцию шага |
| Срок шага процесса | `{expr: settings.<поле>}` вместо числа в `workdays`, `workhours` и в них же у `warnBefore`: `due: {workdays: {expr: settings.<поле>}}` — неотрицательное целое | один раз при входе в шаг |
| Правило вывода работы | `{var: settings.<путь>}` в условии, `{{settings.<путь>}}` в шаблоне | один раз на оценку |
| Экран пакета (`View`) | переменная `settings` в выражениях | один раз на запрос данных блока |
| Агент пакета | `packageSettings` в ответе `GET /api/v1/agents/me` | при запросе |
| Скилл пакета | `ctx.settings` в `skill-sdk` | закреплены за попыткой вызова |

```yaml
# процесс: вход таблицы решений и срок шага по настройкам
decisions:
  - id: refund-route
    inputs:
      - {id: small, expr: "data.refundAmount <= settings.refundLimit", type: boolean}
# …
- id: reply
  human:
    taskType: claim-reply
    assign: [{role: claims-officer}]
    due: {workdays: {expr: settings.replyDueWorkdays}, warnBefore: {workhours: 4}}
```

```yaml
# правило: условие по настройке
spec:
  condition:
    gt: [{var: payload.data.amount}, {var: settings.refundLimit}]
```

Действующее значение — сохранённое поверх `default` схемы: вложенные объекты
сливаются по полям, массив заменяется целиком. Смена значения действует на
следующее вычисление; дело, уже прошедшее шаг, не меняется.

### Журнал и replay { #journal }

Если версия процесса читает `settings` хоть в одном выражении, каждая запись
журнала экземпляра несёт `settingsVersion` и `settingsSchemaRevision` — версию
значений и ревизию схемы, которые видел шаг. Replay и пробный прогон подают
шагу значения этой версии, а не текущие, поэтому решение прежнего дела
воспроизводится и после смены настройки. Записи, версии которой нет в базе, —
расхождение replay `{kind: "settings", journalSeq, recorded}`. Правило пишет
ту же пару в `evidence` своей оценки элементом `{"kind": "settings", …}`.

## Проверка без стенда { #check }

`package-sdk check` проверяет объявление и ссылки теми же кодами, что ядро при
плане. Путь находки объявления — от `/spec/settings`, находки ссылки — путь
выражения в файле объекта.

| Код | Когда |
|---|---|
| `settings_schema_unsupported` | ключевое слово вне подмножества, `title`/`description`, корень не `object`, превышены пределы, `x-ref` неизвестного вида или не у строки |
| `settings_default_missing` | у необязательного поля нет `default` |
| `settings_default_invalid` | `default` не проходит схему поля |
| `settings_secret_field` | признак секрета в схеме, имени поля, `default` или `enum` |
| `settings_uischema_unsupported` | раскладка вне подмножества: поле элемента вне таблицы (например, `options`), `scope` не на свойство, второй `Control` на то же свойство, подпись группы не `<пакет>.settings.groups.<id>` |
| `settings_uischema_uncovered` | предупреждение: у поля нет `Control` |
| `settings_label_missing` | пакет не объявил `locales` или обязательного ключа подписи нет в словаре языка |
| `settings_ref_unknown` | `settings.<путь>` читает необъявленное поле, или пакет объекта настроек не объявляет |
| `settings_ref_type` | тип поля не подходит месту: объект в шаблоне строки, массив в сравнении, не `integer` в сроке |

Правила `check` проверяет целиком; выражения CEL процессов и экранов
типизирует код ядра рядом с `package-sdk` (дополнение `sandbox`). Без него
`check` ловит только необъявленные поля и предупреждает, что типы не
проверены.

`package-sdk describe` показывает настройки рядом с переменными установки:

```text
settings (changed by an administrator in the live system):
  escalationRole [string, ref role, required] (claims)
  refundLimit [number, default 500] (claims)
  replyDueWorkdays [integer, default 2] (claims)
```

Сценарии с настройками — в [Тестах пакета](testing.md#settings).

## Совместимость при обновлении { #upgrade }

`apply` новой версии пакета записывает новую ревизию схемы настроек, но не
трогает сохранённые значения: версия значений, история и событие не меняются.
Что изменится, `plan` показывает разделом `settings`:

```json
"settings": {
  "schemaRevision": {"before": 1, "after": 2},
  "added":        [{"path": "/replyDueWorkdays", "default": 2}],
  "removed":      [{"path": "/legacyLimit", "saved": true}],
  "incompatible": [{"path": "/refundLimit", "code": "maximum"}],
  "uischemaChanged": true
}
```

| Поле | Что значит |
|---|---|
| `schemaRevision` | ревизия схемы до и после; `after: null` — схема не меняется или пакет перестаёт объявлять настройки |
| `added` | новое поле и его `default`: действует сразу, сохранять не нужно |
| `removed` | поле ушло из схемы; `saved` — было ли у него сохранённое значение. Оно остаётся в истории, но в ответах и выражениях его больше нет |
| `incompatible` | **сохранённое** значение не проходит схему новой ревизии: путь и ключевое слово, без значения |
| `uischemaChanged` | раскладка формы изменилась |

Несовместимое значение — ещё и ошибка плана `settings_incompatible`; `apply`
такого плана отвечает `422 invalid_package`. Автоматической миграции значений
нет: администратор сохраняет подходящее значение, автор строит план заново.
Отсюда правила для автора новой версии:

- новое поле — с `default`, тогда обновление ничего не требует от
  администратора;
- сужение (`maximum` меньше, `enum` короче, новое обязательное поле без
  `default`) проверяйте против сохранённых значений стенда: план покажет
  каждое несовместимое;
- переименование поля — это удаление и добавление: сохранённое значение
  прежнего поля не переносится;
- значение, сохранённое между `plan` и `apply`, делает план устаревшим:
  `409 plan_stale`, план строится заново.

Пакет перестал объявлять настройки — объекты пакета больше не читают
`settings`, маршруты настроек отвечают `404 settings_not_declared`, история
остаётся. Как устроены план и применение — в [Установке и
выпуске](install-and-release.md#plan).

## Администратору { #admin }

### Экран «Настройки» { #console }

В консоли настройки пакетов — раздел «Пакеты» экрана «Настройки»
(`/console/settings`): по пункту на каждый установленный пакет с
настройками. Форма строится по схеме и раскладке пакета, подписи и пояснения —
на языке пользователя. У значения видно, по умолчанию оно, сохранено или
изменено. «Сохранить» пишет новую версию с вашим именем, ошибки ядра
показываются у полей. В «Истории изменений» видно автора, время и изменённые
поля любой версии, и её можно вернуть: возврат записывается новой версией.
Без права `packages.settings.manage` форма открывается только для чтения.

### Права { #permissions }

| Право | Что разрешает |
|---|---|
| `packages.settings.read` | список пакетов с настройками, настройки пакета и их история |
| `packages.settings.manage` | сохранение настроек пакета; в ответе чтения — `canManage: true` |

Оба права — на уровне организации и не зависят от `packages.plan`: тот, кто
меняет пороги, не обязан уметь ставить пакеты, и наоборот. Право `admin`
включает оба. Сводка прав — в [Правах и scopes](../reference/permissions.md).

### Маршруты { #routes }

| Метод | Путь | Право | Что |
|---|---|---|---|
| GET | `/api/v1/package-settings` | `packages.settings.read` | пакеты, у которых установленная ревизия объявляет настройки |
| GET | `/api/v1/packages/{key}/settings` | `packages.settings.read` | схема, раскладка, сохранённые и действующие значения |
| PUT | `/api/v1/packages/{key}/settings` | `packages.settings.manage` | сохранить значения целиком |
| GET | `/api/v1/packages/{key}/settings/versions` | `packages.settings.read` | история версий, от новой к старой |

Маршруты, кроме истории, принимают `?locale=` — язык строк ответа.

### Чтение { #read }

```bash
# пакеты, у которых есть настройки
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://platform.example.com/api/v1/package-settings?locale=ru"

# настройки одного пакета
curl -si -H "Authorization: Bearer $TOKEN" \
  "https://platform.example.com/api/v1/packages/claims/settings?locale=ru"
```

```json
{
  "package": "claims",
  "title": "Претензии клиентов",
  "packageVersion": "0.2.0",
  "schema": {"type": "object", "properties": {
    "refundLimit": {"type": "number", "minimum": 0, "default": 500,
                    "title": "Возврат без согласования, до", "description": "…"}}},
  "uischema": {"type": "VerticalLayout", "elements": ["…"]},
  "values": {"refundLimit": 800, "escalationRole": "<role-id>"},
  "effective": {"refundLimit": 800, "replyDueWorkdays": 2, "escalationRole": "<role-id>"},
  "version": 3,
  "schemaHash": "sha256:…",
  "updatedBy": "<principal-id>",
  "updatedAt": "2026-10-03T09:00:00Z",
  "canManage": true
}
```

| Поле | Что |
|---|---|
| `schema`, `uischema` | схема и раскладка активной ревизии; подписи подставлены как `title`, `description`, `label`, `text` на языке запроса |
| `values` | сохранённые значения |
| `effective` | действующие: `values` поверх `default` |
| `version` | версия значений; `0` — ещё не сохраняли |
| `canManage` | есть ли у вызывающего `packages.settings.manage` |

Заголовок ответа `ETag: "package-settings-<version>"` нужен для сохранения.

### Сохранение { #save }

`PUT` сохраняет набор значений **целиком**: поле, которого нет в теле,
возвращается к значению по умолчанию. `If-Match` обязателен — версия, которую
вы читали; до первого сохранения — `"package-settings-0"`.

```bash
curl -s -X PUT -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'If-Match: "package-settings-3"' \
  -d '{"values": {"refundLimit": 1000, "escalationRole": "<role-id>"}}' \
  "https://platform.example.com/api/v1/packages/claims/settings"
```

Ответ — новое состояние в той же форме, что у `GET`, и новый `ETag`. Тело,
равное сохранённому, новой версии и события не создаёт.

| Ответ | Код | Что делать |
|---|---|---|
| 428 | `if_match_required` | передать `If-Match` |
| 400 | `invalid_if_match`, `invalid_request` | `If-Match` не той формы; в теле что-то кроме `values` |
| 404 | `package_not_installed`, `settings_not_declared` | пакет не стоит или не объявляет настроек |
| 422 | `secret_material_rejected` | в значении материал секрета; `details.errors[]` — `path` и вид совпадения, значение не повторяется |
| 422 | `settings_invalid` | значения не проходят схему; `details.errors[]` — `path`, `code` (ключевое слово), сразу все ошибки |
| 422 | `unknown_ref` | `x-ref` ссылается на объект, которого нет или он не в обороте; `details.errors[]` — `path`, `ref` |
| 409 | `version_conflict` | кто-то сохранил раньше; `details.currentVersion` — перечитать и повторить |

Проверка по схеме не исполняет правил `uischema`: скрытое поле проверяется,
как любое другое.

### История и возврат { #history }

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://platform.example.com/api/v1/packages/claims/settings/versions?limit=20"
```

```json
{
  "items": [
    {"version": 3, "values": {"refundLimit": 800, "escalationRole": "<role-id>"},
     "changedPaths": ["/refundLimit"], "updatedBy": "<principal-id>",
     "updatedAt": "2026-10-03T09:00:00Z"}
  ],
  "nextCursor": null
}
```

Версии — от новой к старой, `limit` от 1 до 100 (по умолчанию 50), следующая
страница — `?cursor=<nextCursor>`. Отдельного маршрута отката нет: чтобы
вернуть версию, сохраните её `values` обычным `PUT` — возврат станет новой
версией, история не переписывается.

### Событие `package.settings_changed` { #event }

Каждое сохранение, создавшее версию, пишет в журнал событие
`package.settings_changed`. Значений в нём нет — только что изменилось и кем:

| Поле payload | Что |
|---|---|
| `package` | ключ пакета |
| `version`, `previousVersion` | новая и прежняя версия значений (`0` при первом сохранении) |
| `schemaRevision` | ревизия схемы, по которой проверены значения |
| `changedPaths` | пути изменённых полей |
| `actorId` | кто сохранил |

`apply` пакета событие не пишет. Как подписаться на журнал — в
[Событиях](../control-plane/events.md).

## Типичные проблемы { #troubleshooting }

| Симптом | Причина | Что делать |
|---|---|---|
| `settings_default_missing` | у необязательного поля нет `default` | дать `default` или внести поле в `required` |
| `settings_label_missing` | нет ключа подписи в словаре одного из языков или пакет не объявил `locales` | добавить ключ в `i18n/<язык>.yaml`, объявить `locales` и `defaultLocale` |
| `settings_ref_unknown` у процесса | поле не объявлено, опечатка в пути или процесс заведён не пакетом | объявить поле в `spec.settings` или поправить путь |
| `settings_ref_type` | тип поля не подходит месту выражения | поменять тип поля или выражение: сроку нужно поле `integer` |
| план: `settings_incompatible` | сохранённое значение не проходит новую схему | сохранить подходящее значение и построить план заново |
| `PUT`: `409 version_conflict` | значения сохранили после вашего чтения | перечитать, повторить с новым `If-Match` |
| `PUT`: `422 unknown_ref` | роль, principal, workspace удалены или отключены, у типа задачи нет активной версии | выбрать действующий объект |
| смена значения не повлияла на дело | дело уже прошло шаг, читающий настройку | ожидаемо: значение действует на следующих вычислениях |

## См. также

- [Анатомия пакета](anatomy.md#variables) — переменные установки
- [Тесты пакета](testing.md#settings) — `given.settings` и шаг `settings`
- [Сценарии и план ядра](../processes/package-tests.md) — формат сценариев процесса и replay
- [Выражения процессов](../processes/expressions.md#variables) — переменные CEL
- [Правила в пакете](rules.md)
- [Установка и выпуск](install-and-release.md#plan)
- [Схема пакета](../reference/package-schema.md#schema-packagesettings) — справочник `spec.settings`
- [События](../control-plane/events.md)
