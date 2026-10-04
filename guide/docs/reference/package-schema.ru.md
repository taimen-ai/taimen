# Схема пакета

Справочник полей всех файлов пакета: обёртка объекта, каждый вид каталога,
тесты пакета, фиксация источников `packages.lock`, план установки и экраны. Таблицы
построены из JSON Schema `sdk/package-sdk/schema/v1` и повторяют её поле в поле.
Статья для авторов пакетов; как этим пользоваться, объясняют [Анатомия
пакета](../packages/anatomy.md), [Процессы](../processes/index.md),
[Выражения](../processes/expressions.md) и [Тесты пакета](../packages/testing.md).

!!! note "Схема — первая ступень проверки"
    Схема проверяет форму описания. Вторую ступень — ссылки между объектами,
    типы выражений, неизвестные поля данных, достижимость шагов, пробелы
    таблиц решений — выполняют `package-sdk check` и валидаторы ядра (см.
    [Тесты пакета](../packages/testing.md)).

Подключить схему к редактору — строка в начале файла объекта:

```yaml
# yaml-language-server: $schema=<путь к schema/v1/object.schema.json>
```

Как читать таблицы: «Тип» — тип JSON или ссылка на определение ниже;
`array of` — массив, `map →` — объект с произвольными ключами; «Условия» —
поля, которые обязательны или меняют форму при значении другого поля.

## Обёртка объекта { #object }

Каждый файл объекта пакета — `package.yaml`, файлы видов каталога и установка — одна обёртка `apiVersion` + `kind` + `key` + `spec`. Тип ключа и форма `spec` зависят от вида (таблица «Условия»).

<!-- generated:schema-object -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/object.schema.json`.

### `object` { #schema-object }

One wrapper for the manifest and every catalog kind: apiVersion + kind + key + spec. spec is the control-plane API request body in camelCase without the identity field. The schema checks the shape; the final check is done by the core (and by package-sdk check with its validators).

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `apiVersion` | = `taimen.ai/v1` | да |  |
| `kind` | `Package` \| `Installation` \| `ArtifactType` \| `TaskType` \| `ProjectTemplate` \| `WorkspaceType` \| `Role` \| `Capability` \| `ConnectionType` \| `Skill` \| `WorkRule` \| `Agent` \| `NotificationRule` \| `Process` \| `Calendar` \| `KnowledgePack` | да |  |
| `key` | `string` | да |  |
| `spec` | `object` | да |  |

Условия:

| Условие | Следствие |
|---|---|
| `kind` = `Package` | `key`: [`typeKey`](#schema-typekey); `spec`: [`packageSpec`](#schema-packagespec) |
| `kind` = `Installation` | `spec`: [`installationSpec`](#schema-installationspec) |
| `kind` = `ArtifactType` | `key`: [`typeKey`](#schema-typekey); `spec`: [`artifactTypeSpec`](#schema-artifacttypespec) |
| `kind` = `TaskType` | `key`: [`typeKey`](#schema-typekey); `spec`: [`taskTypeSpec`](#schema-tasktypespec) |
| `kind` = `ProjectTemplate` | `key`: [`typeKey`](#schema-typekey); `spec`: [`projectTemplateSpec`](#schema-projecttemplatespec) |
| `kind` = `WorkspaceType` | `key`: [`typeKey`](#schema-typekey); `spec`: [`workspaceTypeSpec`](#schema-workspacetypespec) |
| `kind` = `Role` | `key`: [`slug`](#schema-slug); `spec`: [`roleSpec`](#schema-rolespec) |
| `kind` = `Capability` | `spec`: [`capabilitySpec`](#schema-capabilityspec) |
| `kind` = `ConnectionType` | `key`: [`connectionKey`](#schema-connectionkey); `spec`: [`connectionTypeSpec`](#schema-connectiontypespec) |
| `kind` = `Skill` | `spec`: [`skillSpec`](#schema-skillspec) |
| `kind` = `WorkRule` | `key`: [`ruleKey`](#schema-rulekey); `spec`: [`workRuleSpec`](#schema-workrulespec) |
| `kind` = `Agent` | `key`: [`slug`](#schema-slug); `spec`: [`agentSpec`](#schema-agentspec) |
| `kind` = `NotificationRule` | `key`: [`ruleKey`](#schema-rulekey); `spec`: [`notificationRuleSpec`](#schema-notificationrulespec) |
| `kind` = `Process` | `key`: [`typeKey`](#schema-typekey); `spec`: [`processSpec`](#schema-processspec) |
| `kind` = `KnowledgePack` | `key`: `string`; `spec`: [`knowledge-pack`](#schema-knowledge-pack) |
| `kind` = `Calendar` | `key`: [`typeKey`](#schema-typekey); `spec`: [`calendarSpec`](#schema-calendarspec) |
<!-- /generated:schema-object -->

## Манифест пакета (`kind: Package`) { #package }

<!-- generated:schema-package -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/object.schema.json`.

### `packageSpec` { #schema-packagespec }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `version` | `string` | да | Package SemVer |
| `displayName` | [`displayName`](#schema-displayname) | да |  |
| `description` | `string` |  |  |
| `requires` | array of [`typeKey`](#schema-typekey) или [объект `{package, version}`](#schema-packagespec-requires-item-2) |  | Packages whose objects this package refers to: a key (any version) or {package, version} with a SemVer range |
| `engines` | map → [`semverRange`](#schema-semverrange) |  | Version ranges of the components the package is tested against, e.g. {control-plane: "&gt;=0.9,&lt;0.11"}; check and plan reject an incompatible version before writing |
| `variables` | map → [`packageVariable`](#schema-packagevariable) |  | Declaration of every ${NAME} of the package. A used variable must be declared, a declared one must be used. There are no secrets in a package: a variable has no secret field |
| `knowledge` | array of `string` |  | Ontologies (name@major) the package's processes and rules rely on; check matches them against recall/remember/memory of the processes |
| `license` | `string` |  | Package license (SPDX identifier) |
| `authors` | array of `string` |  |  |
| `homepage` | `string` |  |  |
| `renames` | array of [объект](#schema-packagespec-renames-item) |  | Explicit object renames (like moved in Terraform): the plan moves the object instead of deleting and creating it |
| `settings` | [`packageSettings`](#schema-packagesettings) |  |  |

### `packageSpec.requires[] (2)` { #schema-packagespec-requires-item-2 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `package` | [`typeKey`](#schema-typekey) | да |  |
| `version` | [`semverRange`](#schema-semverrange) |  |  |

### `packageSpec.renames[]` { #schema-packagespec-renames-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | `string` | да |  |
| `from` | `string` | да |  |
| `to` | `string` | да |  |

### `semverRange` { #schema-semverrange }

Version range: comma-separated conditions, all must hold (&gt;=0.9,&lt;0.11); operators &gt;=, &gt;, &lt;=, &lt;, =, ^, ~; without an operator, a version or prefix (1.2 = 1.2.x); * means any

Значение: `string`.

### `packageVariable` { #schema-packagevariable }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `description` | `string` | да |  |
| `kind` | `url` \| `workspace` \| `project` \| `principal` \| `role` \| `string` \| `integer` | да | Value kind: url is an absolute URL; workspace\|project\|principal\|role is a UUID existing on the environment (checked by plan); integer is an integer; string is anything |
| `required` | `boolean` |  | По умолчанию `true`. |
| `default` | `string` |  | Value used if the installation did not set its own |
| `example` | `string` |  |  |

### `packageSettings` { #schema-packagesettings }

Package settings: values an organization administrator changes in the live system without a new package version or an installation plan. Values live in the core; processes, work rules and views read them as settings.&lt;field&gt;

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `schema` | [`settingsSchema`](#schema-settingsschema) | да |  |
| `uischema` | [`settingsUiElement`](#schema-settingsuielement) |  | Form layout: the closed subset of JSON Forms the console renders — VerticalLayout, HorizontalLayout, Group, Control and Label with SHOW/HIDE/ENABLE/DISABLE rules; anything else, options of a Control included, is rejected. Labels are keys of the package dictionaries, not texts: label of a Group and of a Control, text of a Label. Unlike the uischema of process step forms, which is open and whose label is a text. Without it the console lays the fields out in schema order |

### `settingsSchema` { #schema-settingsschema }

Schema of the settings: a subset of JSON Schema, as for process data. The root is an object; objects nest at most 3 levels deep; at most 100 properties per object. Field labels are not in the schema: they are keys &lt;package&gt;.settings.&lt;path&gt; of the package dictionaries

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | = `object` | да |  |
| `properties` | map → [`settingsField1`](#schema-settingsfield1) | да |  |
| `required` | [`settingsRequired`](#schema-settingsrequired) |  |  |
| `additionalProperties` | = `false` |  | Implied on every object: a value with an undeclared member is refused |

### `settingsFieldName` { #schema-settingsfieldname }

Field name: camelCase, as referenced in expressions (settings.&lt;field&gt;)

Значение: `string`.

### `settingsField1` { #schema-settingsfield1 }

Включает [`settingsKeywords`](#schema-settingskeywords).

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `properties` | любое |  |  |
| `items` | [`settingsField2`](#schema-settingsfield2) |  |  |

### `settingsKeywords` { #schema-settingskeywords }

One settings field: only the keywords listed here; secret markers (writeOnly, format: password) and keywords outside the subset are rejected

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` \| `integer` \| `number` \| `boolean` \| `array` \| `object` | да |  |
| `properties` | `object` |  |  |
| `required` | [`settingsRequired`](#schema-settingsrequired) |  |  |
| `additionalProperties` | = `false` |  |  |
| `enum` | array of [`settingsScalar`](#schema-settingsscalar) |  |  |
| `minimum` | `number` |  |  |
| `maximum` | `number` |  |  |
| `minLength` | `integer` |  |  |
| `maxLength` | `integer` |  |  |
| `pattern` | `string` |  | ECMA-262 regular expression |
| `format` | `date` \| `uri` \| `email` \| `uuid` |  |  |
| `items` | `object` |  |  |
| `minItems` | `integer` |  |  |
| `maxItems` | `integer` |  |  |
| `default` | любое |  | Value in effect until an administrator saves another; every optional field must have one (package-sdk check) |
| `x-ref` | `role` \| `principal` \| `workspace` \| `calendar` \| `taskType` |  | The string references a platform object of this kind in the organization: the id of a role, principal or workspace, the key of a task type or calendar; the core rejects a value that references a missing object |

Условия:

| Условие | Следствие |
|---|---|
| `type` = `object` | обязательно `properties` |
| иначе | `properties`: не допускается; `required`: не допускается; `additionalProperties`: не допускается |
| `type` = `array` | обязательно `items` |
| иначе | `items`: не допускается; `minItems`: не допускается; `maxItems`: не допускается |
| иначе | `minLength`: не допускается; `maxLength`: не допускается; `pattern`: не допускается; `format`: не допускается; `x-ref`: не допускается |
| иначе | `minimum`: не допускается; `maximum`: не допускается |

### `settingsRequired` { #schema-settingsrequired }

Fields that must always have a value

Значение: array of [`settingsFieldName`](#schema-settingsfieldname).

### `settingsScalar` { #schema-settingsscalar }

Значение: `string` \| `integer` \| `number` \| `boolean`.

### `settingsField2` { #schema-settingsfield2 }

Включает [`settingsKeywords`](#schema-settingskeywords).

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `properties` | любое |  |  |
| `items` | [`settingsField3`](#schema-settingsfield3) |  |  |

### `settingsField3` { #schema-settingsfield3 }

The deepest level: a scalar field or an array of scalars, no nested objects

Включает [`settingsKeywords`](#schema-settingskeywords).

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` \| `integer` \| `number` \| `boolean` \| `array` |  |  |
| `items` | [`settingsKeywords`](#schema-settingskeywords) |  |  |

### `settingsUiElement` { #schema-settingsuielement }

Element of the settings form: VerticalLayout, HorizontalLayout, Group, Control or Label. Other JSON Forms elements (Categorization, ListWithDetail, custom renderers) are not rendered by the console and are rejected

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `VerticalLayout` \| `HorizontalLayout` \| `Group` \| `Control` \| `Label` | да |  |

Условия:

| Условие | Следствие |
|---|---|
| `type` ∈ `VerticalLayout`, `HorizontalLayout` | обязательно `elements`; `elements`: [`settingsUiElements`](#schema-settingsuielements); `rule`: [`settingsUiRule`](#schema-settingsuirule) |
| `type` = `Group` | обязательно `label`, `elements`; `label`: [`settingsLabelKey`](#schema-settingslabelkey); `elements`: [`settingsUiElements`](#schema-settingsuielements); `rule`: [`settingsUiRule`](#schema-settingsuirule) |
| `type` = `Control` | обязательно `scope`; `scope`: [`settingsScope`](#schema-settingsscope); `label`: [`settingsLabelKey`](#schema-settingslabelkey); `rule`: [`settingsUiRule`](#schema-settingsuirule) |
| `type` = `Label` | обязательно `text`; `text`: [`settingsLabelKey`](#schema-settingslabelkey); `rule`: [`settingsUiRule`](#schema-settingsuirule) |

### `settingsUiElements` { #schema-settingsuielements }

Значение: array of [`settingsUiElement`](#schema-settingsuielement).

### `settingsUiRule` { #schema-settingsuirule }

JSON Forms rule: the effect applies while the value at condition.scope matches condition.schema

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `effect` | `SHOW` \| `HIDE` \| `ENABLE` \| `DISABLE` | да |  |
| `condition` | [объект](#schema-settingsuirule-condition) | да |  |

### `settingsUiRule.condition` { #schema-settingsuirule-condition }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `scope` | [`settingsScope`](#schema-settingsscope) | да |  |
| `schema` | [объект](#schema-settingsuirule-condition-schema) | да | Condition on the value: the keywords of a settings field without x-ref and default, and const |
| `failWhenUndefined` | `boolean` |  |  |

### `settingsUiRule.condition.schema` { #schema-settingsuirule-condition-schema }

Condition on the value: the keywords of a settings field without x-ref and default, and const

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` \| `integer` \| `number` \| `boolean` \| `array` \| `object` |  |  |
| `const` | [`settingsScalar`](#schema-settingsscalar) |  |  |
| `enum` | array of [`settingsScalar`](#schema-settingsscalar) |  |  |
| `minimum` | `number` |  |  |
| `maximum` | `number` |  |  |
| `minLength` | `integer` |  |  |
| `maxLength` | `integer` |  |  |
| `pattern` | `string` |  |  |
| `format` | `date` \| `uri` \| `email` \| `uuid` |  |  |
| `minItems` | `integer` |  |  |
| `maxItems` | `integer` |  |  |

### `settingsScope` { #schema-settingsscope }

JSON Pointer to a property of the settings schema: #/properties/&lt;field&gt;[/properties/&lt;field&gt;…]

Значение: `string`.

### `settingsLabelKey` { #schema-settingslabelkey }

Key of the package dictionaries (&lt;package&gt;.settings.&lt;name&gt;), not the text: the console shows its string in the user's language

Значение: `string`.
<!-- /generated:schema-package -->

## Установка (`kind: Installation`) { #installation }

<!-- generated:schema-installation -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/object.schema.json`.

### `installationSpec` { #schema-installationspec }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `packages` | array of [`packageSource`](#schema-packagesource) | да | Installation packages: a key (installation catalog), {key, path} or {key, git, ref}; requires are pulled in automatically. Empty means only the core's system task type |
| `packagesDir` | `string` |  | Installation packages directory relative to the installation file; defaults to packages/ next to it |
| `knowledge` | array of [объект](#schema-installationspec-knowledge-item) |  | Ontology inclusion for work spaces is topology, hence in the installation; the set replaces the previous one entirely |
| `retire` | [объект](#schema-installationspec-retire) |  | Keys the environment retires (all active versions → deprecated) |

### `installationSpec.knowledge[]` { #schema-installationspec-knowledge-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `workspace` | `string` | да | Installation ${VARIABLE} or UUID |
| `packs` | array of `string` | да |  |
| `strict` | `boolean` |  | Strict memory mode: records outside the included kinds are rejected rather than accepted as is. По умолчанию `false`. |

### `installationSpec.retire` { #schema-installationspec-retire }

Keys the environment retires (all active versions → deprecated)

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `TaskType` | array of [`typeKey`](#schema-typekey) |  |  |
| `ProjectTemplate` | array of [`typeKey`](#schema-typekey) |  |  |
| `Agent` | array of [`slug`](#schema-slug) |  | The agent is retired: the executor is stopped, the credential revoked, the history kept |
| `NotificationRule` | array of [`ruleKey`](#schema-rulekey) |  | The notification rule is retired in the notification service (:retire); sent notifications remain |
| `WorkRule` | array of [`ruleKey`](#schema-rulekey) |  | The work rule is archived; work it created lives on |
| `Process` | array of [`typeKey`](#schema-typekey) |  | The process is retired via the core's :retire route: new instances do not start, live ones run to completion |
| `Calendar` | array of [`typeKey`](#schema-typekey) |  | A calendar is retired only if no active process refers to it (calendar_in_use) |
| `ConnectionType` | array of [`connectionKey`](#schema-connectionkey) |  | Every active version of the connection type becomes deprecated: no new connections of the type, existing ones keep working |

### `packageSource` { #schema-packagesource }

Значение: [`typeKey`](#schema-typekey) или [объект `{key, path}`](#schema-packagesource-2) или [объект `{key, git, ref, path}`](#schema-packagesource-3).

### `packageSource (2)` { #schema-packagesource-2 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | [`typeKey`](#schema-typekey) | да |  |
| `path` | `string` | да | Package directory path relative to the installation file |

### `packageSource (3)` { #schema-packagesource-3 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | [`typeKey`](#schema-typekey) | да |  |
| `git` | `string` | да | https://host/path without credentials in the address, or git@host:path; access through the git credential helper |
| `ref` | `string` | да | Package release tag (refs/tags/&lt;ref&gt;; branches and commits are not accepted); packages.lock keeps it reproducible |
| `path` | `string` |  | Package subdirectory in the repository if it is not at the root: a relative path without . and .. |
<!-- /generated:schema-installation -->

## Тип артефакта (`kind: ArtifactType`) { #artifact-type }

<!-- generated:schema-artifact-type -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/object.schema.json`.

### `artifactTypeSpec` { #schema-artifacttypespec }

Artifact type: a versioned immutable catalog object, like TaskType.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `displayName` | [`displayName`](#schema-displayname) | да |  |
| `description` | `string` |  |  |
| `metadataSchema` | [`jsonSchema`](#schema-jsonschema) |  | Metadata schema of artifacts of this type (≤ 16 KiB) |
| `mediaTypes` | array of [`mediaType`](#schema-mediatype) |  | Allowed content media types; any by default |
| `maxBytes` | `integer` |  | Content size limit; no more than the installation's global limit (CP_ARTIFACT_MAX_BYTES) |
<!-- /generated:schema-artifact-type -->

## Тип задачи (`kind: TaskType`) { #task-type }

<!-- generated:schema-task-type -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/object.schema.json`.

### `taskTypeSpec` { #schema-tasktypespec }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `displayName` | [`displayName`](#schema-displayname) | да |  |
| `description` | `string` |  |  |
| `fieldSchema` | [`jsonSchema`](#schema-jsonschema) |  | Task customFields schema |
| `lifecycleSchema` | [`workItemLifecycle`](#schema-workitemlifecycle) | да |  |
| `execution` | [`execution`](#schema-execution) |  |  |
| `approvalSchema` | [`approvalSchema`](#schema-approvalschema) |  |  |
| `completionSchema` | `object` |  | Work after the task completes: {onComplete: {when?, actions}}: ensureWork (customFields, relation, requestApproval) and comment. The core checks the grammar. |
| `instructions` | `string` |  | Instructions for the executor: Markdown ≤ 16 KiB, the task type layer after the platform and project contract. The core checks the size in bytes and the absence of secrets. |
| `artifactSchema` | [`artifactSchema`](#schema-artifactschema) |  |  |
| `executorRoles` | array of [`slug`](#schema-slug) |  | Keys of the roles a person needs to take work of this type: a Role of the package, its requires or the tenant. Absent or empty — people are not restricted. The core refuses a role the tenant does not have (422 unknown_role). |
| `acceptance` | array of [`acceptanceCriterion`](#schema-acceptancecriterion) |  | Default acceptance criteria for all tasks of the type: run after the required outputs and before the task's own criteria; a task cannot replace a type criterion, its criterion with the same key is rejected (422). deterministic with an external_write skill only after human in the same attempt. |
| `contextSchema` | [объект](#schema-tasktypespec-contextschema) |  | Task context profile: anchors, traverse, asOf, budgetTokens. The core checks the grammar. |

### `taskTypeSpec.contextSchema` { #schema-tasktypespec-contextschema }

Task context profile: anchors, traverse, asOf, budgetTokens. The core checks the grammar.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `anchors` | array of любое |  |  |
| `traverse` | array of любое |  |  |
| `asOf` | `taskCreated` \| `now` \| `origin` |  |  |
| `budgetTokens` | `integer` |  |  |

### `workItemLifecycle` { #schema-workitemlifecycle }

Включает [`lifecycle`](#schema-lifecycle).

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `statuses` | array of [объект](#schema-workitemlifecycle-statuses-item) |  |  |
| `claimStatus` | [`statusKey`](#schema-statuskey) |  | Status on claim; not terminal |
| `releaseStatus` | [`statusKey`](#schema-statuskey) |  | Status on release; not terminal |
| `completionStatus` | [`statusKey`](#schema-statuskey) |  | Successful completion status; category terminal_success |

### `workItemLifecycle.statuses[]` { #schema-workitemlifecycle-statuses-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `category` | [`workItemCategory`](#schema-workitemcategory) |  |  |

### `workItemCategory` { #schema-workitemcategory }

Значение: `backlog` \| `active` \| `blocked` \| `terminal_success` \| `terminal_cancelled`.

### `execution` { #schema-execution }

A task of this type is executed by one skill call

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `skill` | `string` | да |  |
| `version` | `string` | да |  |
| `inputs` | `string` или map → `string` |  | $.… path to the whole input or an object {inputName: path}; defaults to $.customFields |

### `approvalSchema` { #schema-approvalschema }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `gates` | map → [объект](#schema-approvalschema-gates-value) |  | Only the default gate is supported for now |

### `approvalSchema.gates.*` { #schema-approvalschema-gates-value }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `outcomes` | [объект](#schema-approvalschema-gates-value-outcomes) | да |  |

### `approvalSchema.gates.*.outcomes` { #schema-approvalschema-gates-value-outcomes }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `approved` | array of [`outcomeAction`](#schema-outcomeaction) |  |  |
| `rejected` | array of [`outcomeAction`](#schema-outcomeaction) |  |  |

### `outcomeAction` { #schema-outcomeaction }

One approval outcome action: an object with exactly one key. In strings, $.path expressions; the ! suffix makes the value required.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `ensureWork` | [объект](#schema-outcomeaction-ensurework) |  |  |
| `completeTask` | [объект](#schema-outcomeaction-completetask) |  |  |
| `comment` | [объект](#schema-outcomeaction-comment) |  |  |
| `transition` | [объект](#schema-outcomeaction-transition) |  |  |
| `invokeSkill` | [объект](#schema-outcomeaction-invokeskill) |  | Skill call; reactions run on the call's outcome |

### `outcomeAction.ensureWork` { #schema-outcomeaction-ensurework }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` | да | Task type key |
| `key` | `string` | да | Idempotency key of the created work |
| `title` | `string` | да |  |
| `description` | `string` |  |  |
| `assignee` | `string` |  |  |
| `priority` | `string` |  |  |
| `workspace` | `string` |  |  |
| `relation` | map → `string` |  |  |
| `customFields` | map → `string` |  | Fields of the created task: expressions/templates; checked against the target type's fieldSchema at execution |
| `requestApproval` | [объект](#schema-outcomeaction-ensurework-requestapproval) |  | Gate approval on the task just created |

### `outcomeAction.ensureWork.requestApproval` { #schema-outcomeaction-ensurework-requestapproval }

Gate approval on the task just created

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `assignee` | `string` | да | Principal id or role:&lt;slug&gt;, a role declared by the package (its holder decides); an expression or template |
| `comment` | `string` |  |  |

### `outcomeAction.completeTask` { #schema-outcomeaction-completetask }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `task` | `string` |  |  |

### `outcomeAction.comment` { #schema-outcomeaction-comment }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `body` | `string` | да |  |
| `task` | `string` |  |  |

### `outcomeAction.transition` { #schema-outcomeaction-transition }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `status` | `string` | да |  |
| `task` | `string` |  |  |

### `outcomeAction.invokeSkill` { #schema-outcomeaction-invokeskill }

Skill call; reactions run on the call's outcome

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `skill` | `string` | да | name@version (required with a version for external_write) |
| `inputs` | `object` |  | skill inputs; strings are $.task…, $.spawnedBy…, $.approval… expressions |
| `expect` | `object` |  | expected outputs fields; a mismatch triggers onFailure |
| `onSuccess` | array of [`outcomeAction`](#schema-outcomeaction) |  |  |
| `onFailure` | array of [`outcomeAction`](#schema-outcomeaction) |  |  |

### `artifactSchema` { #schema-artifactschema }

Task type inputs and outputs. An input is the head revisions of artifacts of the required type on tasks via a relation; without a required input, claim is rejected (409 input_missing). A required output is a deterministic criterion of the verification stage.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `inputs` | array of [объект](#schema-artifactschema-inputs-item) |  |  |
| `outputs` | array of [объект](#schema-artifactschema-outputs-item) |  |  |

### `artifactSchema.inputs[]` { #schema-artifactschema-inputs-item }

Включает [`artifactSlot`](#schema-artifactslot).

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | любое | | |
| `type` | любое | | |
| `required` | любое | | |
| `from` | `depends_on` \| `spawned_by` \| `parent` | да | Relation used to find the source task |

### `artifactSchema.outputs[]` { #schema-artifactschema-outputs-item }

Включает [`artifactSlot`](#schema-artifactslot).

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | любое | | |
| `type` | любое | | |
| `required` | любое | | |
| `mediaTypes` | любое | | |
| `content` | `required` \| `optional` |  | Whether the content must be in storage (otherwise a reference is enough). По умолчанию `required`. |

### `artifactSlot` { #schema-artifactslot }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | `string` | да | Input or output name; unique within inputs and within outputs |
| `type` | [`typeKey`](#schema-typekey) | да | Artifact type key (ArtifactType) |
| `required` | `boolean` |  | По умолчанию `false`. |
| `mediaTypes` | array of [`mediaType`](#schema-mediatype) |  | Narrowing of the artifact type's media types (a subset of its mediaTypes) |

### `acceptanceCriterion` { #schema-acceptancecriterion }

Acceptance criterion: the core checks the spec grammar per kind

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | `string` | да |  |
| `kind` | `deterministic` \| `external_state` \| `human` \| `llm_judge` | да |  |
| `description` | `string` | да |  |
| `spec` | `object` |  |  |
| `when` | array of `string` |  | $.task… paths; the criterion runs only if all are non-empty, otherwise skipped |
<!-- /generated:schema-task-type -->

## Шаблон проекта (`kind: ProjectTemplate`) { #project-template }

<!-- generated:schema-project-template -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/object.schema.json`.

### `projectTemplateSpec` { #schema-projecttemplatespec }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `displayName` | [`displayName`](#schema-displayname) | да |  |
| `description` | `string` |  |  |
| `fieldSchema` | [`jsonSchema`](#schema-jsonschema) |  |  |
| `lifecycleSchema` | [`projectLifecycle`](#schema-projectlifecycle) |  |  |
| `defaultConfig` | [объект](#schema-projecttemplatespec-defaultconfig) |  |  |
| `defaultViews` | array of любое |  |  |
| `governanceSchema` | [объект](#schema-projecttemplatespec-governanceschema) |  |  |
| `memoryDefaults` | `object` |  |  |

### `projectTemplateSpec.defaultConfig` { #schema-projecttemplatespec-defaultconfig }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `settings` | `object` |  |  |
| `views` | array of любое |  |  |
| `governance` | `object` |  |  |
| `memory` | `object` |  |  |
| `inheritance` | `object` |  |  |

### `projectTemplateSpec.governanceSchema` { #schema-projecttemplatespec-governanceschema }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `maxAutonomyLevel` | любое |  |  |
| `requireApprovalForRun` | `boolean` |  |  |
| `requireApprovalForCompletion` | `boolean` |  |  |
| `allowedTaskPriorities` | array of `string` |  |  |
| `allowedSkillProtocols` | array of `string` |  |  |
| `maxRunDurationSeconds` | `number` |  |  |
| `maxRunActions` | `number` |  |  |
| `maxConcurrentRuns` | `number` |  |  |
| `memoryScopeSharing` | любое |  |  |

### `projectLifecycle` { #schema-projectlifecycle }

Включает [`lifecycle`](#schema-lifecycle).

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `statuses` | array of [объект](#schema-projectlifecycle-statuses-item) |  |  |

### `projectLifecycle.statuses[]` { #schema-projectlifecycle-statuses-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `category` | [`projectCategory`](#schema-projectcategory) |  |  |

### `projectCategory` { #schema-projectcategory }

Значение: `planned` \| `active` \| `paused` \| `terminal_success` \| `terminal_cancelled`.
<!-- /generated:schema-project-template -->

## Тип пространства работы (`kind: WorkspaceType`) { #workspace-type }

<!-- generated:schema-workspace-type -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/object.schema.json`.

### `workspaceTypeSpec` { #schema-workspacetypespec }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `displayName` | [`displayName`](#schema-displayname) | да |  |
| `description` | `string` |  |  |
| `fieldSchema` | [`jsonSchema`](#schema-jsonschema) |  |  |
| `allowedChildTypes` | array of `string` |  |  |
<!-- /generated:schema-workspace-type -->

## Роль (`kind: Role`) { #role }

<!-- generated:schema-role -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/object.schema.json`.

### `roleSpec` { #schema-rolespec }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `name` | [`displayName`](#schema-displayname) | да |  |
| `description` | `string` |  |  |
<!-- /generated:schema-role -->

## Способность (`kind: Capability`) { #capability }

<!-- generated:schema-capability -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/object.schema.json`.

### `capabilitySpec` { #schema-capabilityspec }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `description` | `string` |  |  |
<!-- /generated:schema-capability -->

## Тип подключения (`kind: ConnectionType`) { #connection-type }

<!-- generated:schema-connection-type -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/object.schema.json`.

### `connectionTypeSpec` { #schema-connectiontypespec }

Connection type: what it takes to connect a system of this kind. Versions work as for Skill: the package sets the version, and a published (key, version) pair is immutable. A type carries no secret values: an administrator enters them in the console.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `version` | `integer` | да | The package sets the version of the type; a published version is immutable |
| `displayName` | [`displayName`](#schema-displayname) | да |  |
| `description` | `string` |  |  |
| `auth` | array of `oauth2` \| `token` | да | Ways to connect: oauth2 — a person consents at the provider, token — a long-lived key an administrator pastes |
| `oauth2` | [объект](#schema-connectiontypespec-oauth2) |  |  |
| `accountField` | [объект](#schema-connectiontypespec-accountfield) |  | Account field: its label in the key form and the account check; required with token or with {account} in tokenUrlTemplate |
| `settingsSchema` | [объект](#schema-connectiontypespec-settingsschema) | да | JSON Schema (draft 2020-12) of the connection's non-secret settings, root type: object. Properties named like secrets (password, token, clientSecret…) are refused |
| `defaultKey` | [`connectionKey`](#schema-connectionkey) | да | Key of the default connection — the agents of the package name it in Agent.spec.connections |

Условия:

| Условие | Следствие |
|---|---|
| всегда | обязательно `oauth2` |
| всегда | обязательно `accountField` |
| всегда | обязательно `accountField`; `oauth2`:  |

### `connectionTypeSpec.oauth2` { #schema-connectiontypespec-oauth2 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `authorizeUrl` | `string` (uri) | да | Where a person is sent to consent |
| `tokenUrlTemplate` | `string` | да | Address of the code exchange and refresh; the only placeholder is {account}, the host is an external DNS name |
| `accountParam` | `string` |  | Callback parameter that names the account; required when tokenUrlTemplate has {account} |
| `authStyle` | `in_params` \| `in_header` | да | How the client id and secret go to the exchange address: in the request body or as Authorization: Basic |
| `scopes` | array of `string` | да | Requested permissions |

### `connectionTypeSpec.accountField` { #schema-connectiontypespec-accountfield }

Account field: its label in the key form and the account check; required with token or with {account} in tokenUrlTemplate

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `title` | `string` | да |  |
| `description` | `string` |  |  |
| `pattern` | `string` | да | Regular expression the whole account matches |

### `connectionTypeSpec.settingsSchema` { #schema-connectiontypespec-settingsschema }

JSON Schema (draft 2020-12) of the connection's non-secret settings, root type: object. Properties named like secrets (password, token, clientSecret…) are refused

Включает [`jsonSchema`](#schema-jsonschema).

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | = `object` | да |  |
<!-- /generated:schema-connection-type -->

## Скилл (`kind: Skill`) { #skill }

<!-- generated:schema-skill -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/object.schema.json`.

### `skillSpec` { #schema-skillspec }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `version` | `string` | да | The package sets the skill version |
| `description` | `string` |  |  |
| `protocol` | `mcp` \| `http` \| `local` \| `opencode` \| `custom` |  |  |
| `config` | `object` |  |  |
| `inputSchema` | [`jsonSchema`](#schema-jsonschema) |  |  |
| `outputSchema` | [`jsonSchema`](#schema-jsonschema) |  |  |
| `sideEffects` | `none` \| `external_read` \| `external_write` |  |  |
| `riskLevel` | `low` \| `medium` \| `high` |  |  |
| `contract` | [`skillContract`](#schema-skillcontract) |  |  |

### `skillContract` { #schema-skillcontract }

Skill v1 contract. Immutable within a version.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `inputs` | [`jsonSchema`](#schema-jsonschema) | да |  |
| `outputs` | [`jsonSchema`](#schema-jsonschema) | да |  |
| `requiredPermissions` | array of `string` |  |  |
| `preconditions` | array of любое |  |  |
| `postconditions` | array of любое |  |  |
| `timeoutSeconds` | `integer` |  |  |
| `retryPolicy` | [объект](#schema-skillcontract-retrypolicy) |  |  |
| `idempotency` | `required` \| `natural` \| `none` |  |  |
| `costModel` | [объект](#schema-skillcontract-costmodel) |  |  |
| `implementation` | [объект](#schema-skillcontract-implementation) | да |  |

### `skillContract.retryPolicy` { #schema-skillcontract-retrypolicy }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `maxAttempts` | `integer` |  |  |
| `backoffSeconds` | `integer` |  |  |

### `skillContract.costModel` { #schema-skillcontract-costmodel }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `unit` | `string` | да |  |
| `estimate` | `number` |  |  |

### `skillContract.implementation` { #schema-skillcontract-implementation }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `protocol` | `http` \| `local` \| `mcp` | да |  |
| `endpoint` | `string` |  | http: address; allows an environment ${VARIABLE} |
| `entrypoint` | `string` |  | local: module:function; mcp: tool name |
| `auth` | `object` |  | audience or secretRef; no secrets |
<!-- /generated:schema-skill -->

## Правило вывода работы (`kind: WorkRule`) { #work-rule }

<!-- generated:schema-work-rule -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/object.schema.json`.

### `workRuleSpec` { #schema-workrulespec }

Work rule: exactly the POST /rules body without key. The core checks the grammar of conditions and templates (normalize_rule_spec). workspaceId is installation topology: only via a ${VARIABLE}, set on creation and not changed afterwards.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `description` | `string` |  |  |
| `workspaceId` | `string` |  |  |
| `trigger` | [объект](#schema-workrulespec-trigger) | да |  |
| `condition` | `object` \| `boolean` |  |  |
| `interpretation` | [объект](#schema-workrulespec-interpretation) |  |  |
| `action` | [объект](#schema-workrulespec-action) | да |  |
| `identity` | [объект](#schema-workrulespec-identity) |  | On whose behalf the rule acts: an agent description of kind service or agent; without identity, with the authority of whoever applied the rule |
| `status` | `enabled` \| `disabled` |  | enabled by default |

### `workRuleSpec.trigger` { #schema-workrulespec-trigger }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | `observation` \| `event` \| `schedule` | да |  |
| `agent` | `string` |  | Only with observation: the observation matches when its author is the principal of this agent. An agent key or an installation ${VARIABLE} — a neutral package does not know the provider's agent |

### `workRuleSpec.interpretation` { #schema-workrulespec-interpretation }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `skill` | `string` | да | name@version |
| `inputs` | `object` |  |  |

### `workRuleSpec.action` { #schema-workrulespec-action }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | `ensure_work` \| `update_work` \| `cancel_work` \| `complete_work` \| `request_decision` | да |  |
| `taskType` | `string` |  | Type key or a {{item.…}} template; a template only with non-empty taskTypes |
| `taskTypes` | array of [`typeKey`](#schema-typekey) |  | Allowed types for a templated taskType; with complete_work and cancel_work with target: task — the types the rule may close |
| `target` | `dedup` \| `task` |  | Only with complete_work and cancel_work: dedup — the work under the rule's key (the default), task — the task the triggering observation is bound to; needs taskTypes and an author filter trigger.agent or trigger.actorId |
| `fields` | [объект](#schema-workrulespec-action-fields) |  |  |

### `workRuleSpec.action.fields` { #schema-workrulespec-action-fields }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `workspaceId` | `string` |  | Template of the workspace id of the created work; defaults to the rule's workspace |
| `relations` | [объект](#schema-workrulespec-action-fields-relations) |  | Relations of the created work: spawnedBy is a task id template; dependsOn are deduplication keys of this rule's work (from the same evaluation or created earlier) |

### `workRuleSpec.action.fields.relations` { #schema-workrulespec-action-fields-relations }

Relations of the created work: spawnedBy is a task id template; dependsOn are deduplication keys of this rule's work (from the same evaluation or created earlier)

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `spawnedBy` | `string` |  |  |
| `dependsOn` | `string` или array of `string` |  |  |

### `workRuleSpec.identity` { #schema-workrulespec-identity }

On whose behalf the rule acts: an agent description of kind service or agent; without identity, with the authority of whoever applied the rule

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `agent` | [`slug`](#schema-slug) | да |  |
<!-- /generated:schema-work-rule -->

## Агент (`kind: Agent`) { #agent }

<!-- generated:schema-agent -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/object.schema.json`.

### `agentSpec` { #schema-agentspec }

Agent: who it is, what work it takes, with what and how it executes, where it is placed. Every change is a new immutable revision in the core; a run remembers its revision.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `displayName` | [`displayName`](#schema-displayname) | да |  |
| `description` | `string` |  |  |
| `identity` | [объект](#schema-agentspec-identity) | да | Identity: the core and IAM principal and its binding to permissions, created and maintained by the platform. Permissions are no broader than those of whoever applies the description. |
| `work` | [объект](#schema-agentspec-work) |  | What work the agent takes from the queue |
| `executor` | [объект](#schema-agentspec-executor) |  | What the agent executes work with. The kind is data (a string for the core); the default image is chosen by the node, an image from the description only from the node's list. |
| `workingCopy` | `object` |  | Task working copy. Interpreted by the executor daemon, the core stores the object as data; the shape is set by the executor kind: shapes per kind are in agentWorkingCopies: for the code executor kind, one repository or a catalog with a task field, for other kinds, one repository |
| `skills` | [объект](#schema-agentspec-skills) |  | Which skills the agent executes itself and where they may connect |
| `placement` | = `none` или [объект](#schema-agentspec-placement) — по условию |  | Where and how many: none means identity only, without a process (service account) |
| `state` | `running` \| `stopped` |  | По умолчанию `running`. |
| `connections` | array of [`connectionKey`](#schema-connectionkey) |  | Keys of the tenant's connections whose access material the agent may read. Whether such a connection exists is not checked on publish; a non-empty list needs connections.manage of whoever applies it |

Условия:

| Условие | Следствие |
|---|---|
| не (`placement` = `none`) | обязательно `executor` |
| `executor.kind` = `claude-code` | `workingCopy`: [`agentWorkingCopies/claude-code`](#schema-agentworkingcopies-claude-code) |
| иначе | `workingCopy`: [`agentWorkingCopies/single`](#schema-agentworkingcopies-single) |

### `agentSpec.identity` { #schema-agentspec-identity }

Identity: the core and IAM principal and its binding to permissions, created and maintained by the platform. Permissions are no broader than those of whoever applies the description.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | `agent` \| `service` | да |  |
| `roles` | array of [`slug`](#schema-slug) |  | Tenant roles (from packages) |
| `permissions` | array of [`permission`](#schema-permission) |  |  |
| `capabilities` | array of `string` |  |  |
| `iam` | [объект](#schema-agentspec-identity-iam) |  | IAM part of the account: audiences and the scope ceiling. Data for whoever issues the account (bootstrap, executor node controller); the core stores it but does not interpret it. |

### `agentSpec.identity.iam` { #schema-agentspec-identity-iam }

IAM part of the account: audiences and the scope ceiling. Data for whoever issues the account (bootstrap, executor node controller); the core stores it but does not interpret it.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `audiences` | array of `string` | да |  |
| `scopeCeiling` | array of `string` | да | Scope &lt;audience&gt;:&lt;action&gt;, segments may be dotted (control-plane:read, iam:identities.link) |

### `agentSpec.work` { #schema-agentspec-work }

What work the agent takes from the queue

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `workspace` | [`envOrUuid`](#schema-envoruuid) |  |  |
| `project` | [`envOrUuid`](#schema-envoruuid) |  |  |
| `includeSubprojects` | `boolean` |  | По умолчанию `false`. |
| `onlyAssigned` | `boolean` |  | Only work assigned to it. По умолчанию `true`. |
| `taskTypes` | array of [`typeKey`](#schema-typekey) |  | Empty means any types |

### `agentSpec.executor` { #schema-agentspec-executor }

What the agent executes work with. The kind is data (a string for the core); the default image is chosen by the node, an image from the description only from the node's list.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | `claude-code` \| `codex` \| `skills` \| `git-connector` \| `observer` | да |  |
| `params` | `object` |  |  |
| `image` | `string` |  | Executor image: [registry[:port]/]path:tag, …@sha256:&lt;64 hex&gt; or …:tag@sha256:&lt;64 hex&gt;; a tag or digest is required. The node runs it only if the image is in the node's executors.&lt;kind&gt;.images list, otherwise image_not_allowed; without the field, the kind's default image |
| `instructions` | `string` |  | Instructions for the executor: a layer after the platform, project and task type instructions |

Условия:

| Условие | Следствие |
|---|---|
| `kind` = `claude-code` | `params`: [`agentExecutors/claude-code`](#schema-agentexecutors-claude-code) |
| `kind` = `codex` | `params`: [`agentExecutors/codex`](#schema-agentexecutors-codex) |
| `kind` = `skills` | `params`: [`agentExecutors/skills`](#schema-agentexecutors-skills) |
| `kind` = `git-connector` | обязательно `params`; `params`: [`agentExecutors/git-connector`](#schema-agentexecutors-git-connector) |
| `kind` = `observer` | обязательно `params`; `params`: [`agentExecutors/observer`](#schema-agentexecutors-observer) |

### `agentSpec.skills` { #schema-agentspec-skills }

Which skills the agent executes itself and where they may connect

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `protocols` | array of `local` \| `http` \| `mcp` |  |  |
| `local` | array of `string` |  | Allowed entrypoints or packages |
| `httpOrigins` | array of `string` |  |  |
| `mcpOrigins` | array of `string` |  |  |
| `audiences` | array of `string` |  | IAM audiences the skills get a token for |
| `concurrency` | `integer` |  |  |
| `invoke` | array of `string` |  | Skill versions the agent invokes through the core (name@version) rather than executing itself; the registry assigns them to the agent's principal |

### `agentSpec.placement` { #schema-agentspec-placement }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `requires` | array of [`nodeLabel`](#schema-nodelabel) |  | Labels the node must have |
| `secrets` | array of [`secretName`](#schema-secretname) |  | Secrets the node must have: static ones (a file in the node's secrets directory) and issued ones, which the node issues and renews itself, e.g. an hourly forge-token from the forge app installation. Declared the same way, by name; the material is not written into the description |
| `resources` | [объект](#schema-agentspec-placement-resources) |  |  |
| `replicas` | `integer` |  | По умолчанию `1`. |
| `drainSeconds` | `integer` |  | How long to wait for the current run before switching to a new revision. По умолчанию `14400`. |

### `agentSpec.placement.resources` { #schema-agentspec-placement-resources }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `cpus` | `integer` |  | Whole CPUs: the core canonical hash of a revision rejects fractional numbers (non_canonical_value) |
| `memoryMb` | `integer` |  |  |

### `permission` { #schema-permission }

Control Plane permission, e.g. tasks.claim

Значение: `string`.

### `agentExecutors` { #schema-agentexecutors }

Executor kind parameters; the core stores them without interpreting, this schema and the adapter check them

Набор определений: [`agentExecutors/claude-code`](#schema-agentexecutors-claude-code), [`agentExecutors/codex`](#schema-agentexecutors-codex), [`agentExecutors/skills`](#schema-agentexecutors-skills), [`agentExecutors/git-connector`](#schema-agentexecutors-git-connector), [`agentExecutors/observer`](#schema-agentexecutors-observer).

### `agentExecutors/claude-code` { #schema-agentexecutors-claude-code }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `model` | `string` |  |  |
| `permissionMode` | `default` \| `acceptEdits` \| `plan` \| `bypassPermissions` |  | По умолчанию `acceptEdits`. |
| `timeoutSeconds` | `integer` |  | По умолчанию `3600`. |
| `resume` | `boolean` |  | По умолчанию `true`. |
| `tools` | [объект](#schema-agentexecutors-claude-code-tools) |  | Narrowing of the agent's tools; the ban on authoritative Control Plane commands is not lifted |

### `agentExecutors/claude-code.tools` { #schema-agentexecutors-claude-code-tools }

Narrowing of the agent's tools; the ban on authoritative Control Plane commands is not lifted

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `allow` | array of `string` |  |  |
| `deny` | array of `string` |  |  |

### `agentExecutors/codex` { #schema-agentexecutors-codex }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `model` | `string` |  |  |
| `sandbox` | `read-only` \| `workspace-write` \| `danger-full-access` |  | По умолчанию `workspace-write`. |
| `timeoutSeconds` | `integer` |  | По умолчанию `3600`. |
| `resume` | `boolean` |  | По умолчанию `true`. |
| `credentialClass` | `subscription` \| `api_key` |  | Whose credential is consumed |

### `agentExecutors/skills` { #schema-agentexecutors-skills }

Skills-only executor: what to execute is the agent's skills section; params are non-secret skill settings

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `env` | map → `string` |  | Non-secret skill settings (portal address, limits): environment variables of every local skill call on the skills host. No secrets here: names like *TOKEN, *SECRET, *PASSWORD, *API_KEY are forbidden, secrets come as node secret files (placement.secrets); host names (CONTROL_PLANE_*, IAM_*, PATH…) are forbidden too |

### `agentExecutors/git-connector` { #schema-agentexecutors-git-connector }

Git observation source: what to observe and which observations to produce. The cursor lives in the replica volume, observations go to POST /observations of the agent's workspace.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `repositories` | array of [объект](#schema-agentexecutors-git-connector-repositories-item) | да |  |
| `observe` | array of `commits` \| `adrRegistry` \| `ciRuns` |  | commits — repo.commit_observed; adrRegistry — adr.registry_observed; ciRuns — ci.run_observed. По умолчанию `["commits"]`. |
| `intervalSeconds` | `integer` |  | По умолчанию `300`. |
| `knowledgeSnapshots` | `boolean` |  | Send contract snapshots to memory via POST /knowledge/snapshots. По умолчанию `true`. |
| `registryRepository` | `string` |  | Repository to read the ADR registry from (a name from repositories) |
| `ciRepository` | `string` |  | owner/repo of CI runs |
| `ciBranch` | `string` |  | По умолчанию `main`. |

### `agentExecutors/git-connector.repositories[]` { #schema-agentexecutors-git-connector-repositories-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `name` | `string` | да | Name in observations (payload.data.repo, source git:&lt;name&gt;) |
| `url` | `string` | да |  |
| `branch` | `string` |  | По умолчанию `main`. |

### `agentExecutors/observer` { #schema-agentexecutors-observer }

Integration package observation source (connector = observer + skills): a long-lived process that polls an external system in a loop and writes observations to the agent's workspace (POST /observations). What to poll is config, interpreted by the integration code; which code is entrypoint, which the observer kind image on the node must contain. The cursor lives in the replica volume, secrets come only as node secret files (placement.secrets).

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `entrypoint` | `string` | да | Integration observer "module:function"; the image process checks that it executes exactly this one |
| `intervalSeconds` | `integer` |  | По умолчанию `900`. |
| `config` | `object` |  | Integration parameters (filters, addresses, limits) are package data. No secrets here: keys like *token, *secret, *password are forbidden |

### `nodeLabel` { #schema-nodelabel }

Node label: name or name=value

Значение: `string`.

### `secretName` { #schema-secretname }

Secret name on the node; the value is not written into the description

Значение: `string`.

### `agentWorkingCopies` { #schema-agentworkingcopies }

Shapes of the workingCopy section per executor kind: the core stores the section as data, this schema and the executor daemon check it

Набор определений: [`agentWorkingCopies/single`](#schema-agentworkingcopies-single), [`agentWorkingCopies/catalog`](#schema-agentworkingcopies-catalog), [`agentWorkingCopies/catalogEntry`](#schema-agentworkingcopies-catalogentry), [`agentWorkingCopies/claude-code`](#schema-agentworkingcopies-claude-code).

### `agentWorkingCopies/claude-code` { #schema-agentworkingcopies-claude-code }

One repository (legacy shape) or a catalog: the presence of repositories or repositoryField selects the catalog

Значение: [`agentWorkingCopies/catalog`](#schema-agentworkingcopies-catalog) или [`agentWorkingCopies/single`](#schema-agentworkingcopies-single) — по условию.

Условия:

| Условие | Следствие |
|---|---|
| задано `repositories` или задано `repositoryField` | [`agentWorkingCopies/catalog`](#schema-agentworkingcopies-catalog) |
| иначе | [`agentWorkingCopies/single`](#schema-agentworkingcopies-single) |

### `agentWorkingCopies/catalog` { #schema-agentworkingcopies-catalog }

Repository catalog: the only source of clone, neighbour and publication addresses. The task repository is a catalog key or an alias in the task field repositoryField; an address from the task is not accepted, there is no default. Keys and aliases are matched case-insensitively (casefold): this is how the executor daemon and tasks.check@1 resolve the task key. package-sdk check verifies that superproject refers to a catalog key and that keys and aliases (casefold), addresses (normalized) and directories are unambiguous across entries

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `repositoryField` | `string` | да | Name of the task's customFields field holding the repository key (repositoryKey for coding-task) |
| `superproject` | любое |  | Catalog key whose submodules pin the neighbours' revisions |
| `publish` | `boolean` |  | Publish the task branch to the forge; a catalog entry may override it. По умолчанию `true`. |
| `checks` | `boolean` |  | Run the checks of .agents/runner.yaml of the base revision before hand-in; the report goes to metadata.checks of the commit artifact. По умолчанию `false`. |
| `repositories` | map → [`agentWorkingCopies/catalogEntry`](#schema-agentworkingcopies-catalogentry) | да |  |

### `repositoryKey` { #schema-repositorykey }

Canonical repository key in the working copy catalog: ASCII, as in the task's customFields. Keys and aliases are matched case-insensitively (casefold): this is how the executor daemon and tasks.check@1 resolve the task key

Значение: `string`.

### `agentWorkingCopies/catalogEntry` { #schema-agentworkingcopies-catalogentry }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `url` | `string` | да | Clone address: an installation ${VARIABLE} or https without credentials, query and fragment (environment topology is not written into the package). Host: DNS labels, port 1–65535; path segments: ASCII without dot segments or a leading dot, since the mirror name is taken from the last segment. package-sdk check looks for matching addresses of two entries after normalization (no trailing /, no .git, case-insensitive) |
| `baseRef` | `string` |  | Task base branch, a git ref name: no leading - / ., no spaces or control characters, no .., @{, //, ~^:?*[\ and no trailing / . .lock |
| `directory` | любое |  | Directory in the working copy: a name (flat layout) or a path of several segments (services/control-plane). It does not repeat the directory or the key of another entry, and is neither inside the directory of another entry nor contains it — checked by package-sdk check |
| `publish` | `boolean` |  | false means a neighbour the agent does not write to; defaults to the catalog's publish |
| `aliases` | array of [`repositoryAlias`](#schema-repositoryalias) |  | Former names accepted instead of the key; matching is case-insensitive (casefold), so aliases repeat neither their own nor other keys and aliases, even in another case |

### `workingCopyPath` { #schema-workingcopypath }

A directory in the working copy relative to its root: one name (flat layout, control-plane) or a path of several segments joined by / (services/control-plane, sdk/platform-auth-sdk). A segment starts with a lowercase Latin letter or a digit, so . and .. do not pass; an absolute path, an empty segment (//, a trailing /) and a backslash are rejected

Значение: `string`.

### `repositoryAlias` { #schema-repositoryalias }

Former repository name (map key, repository row of the task document, connector deduplication key): Latin and Cyrillic letters, digits, . _ -. Matched against the task key case-insensitively (casefold)

Значение: `string`.

### `agentWorkingCopies/single` { #schema-agentworkingcopies-single }

Legacy shape: one repository, neighbours and superproject by address

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `repository` | `string` | да |  |
| `directory` | любое |  | Directory of the repository in the working copy: a name (flat layout) or a path of several segments |
| `baseRef` | `string` |  |  |
| `neighbours` | map → `string` |  | Neighbour repositories at revisions pinned by the superproject. The key is the neighbour's directory in the working copy: a name or a path of several segments |
| `superproject` | `string` |  |  |
| `publish` | `boolean` |  | Publish the task branch to the forge. По умолчанию `true`. |
| `checks` | `boolean` |  | Run the checks of .agents/runner.yaml of the base revision before hand-in; the report goes to metadata.checks of the commit artifact. По умолчанию `false`. |
| `review` | [объект](#schema-agentworkingcopies-single-review) |  | Deprecated: review is declared by the task type as acceptance criteria; the section is removed together with the daemon's auto-review |

### `agentWorkingCopies/single.review` { #schema-agentworkingcopies-single-review }

Deprecated: review is declared by the task type as acceptance criteria; the section is removed together with the daemon's auto-review

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `mode` | `human` \| `agent` \| `none` |  |  |
| `taskType` | [`typeKey`](#schema-typekey) |  |  |
| `taskTypes` | array of [`typeKey`](#schema-typekey) |  | Task types that get a review |
| `reviewer` | [`envOrUuid`](#schema-envoruuid) |  |  |
| `base` | `string` |  |  |
<!-- /generated:schema-agent -->

## Правило уведомления (`kind: NotificationRule`) { #notification-rule }

<!-- generated:schema-notification-rule -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/object.schema.json`.

### `notificationRuleSpec` { #schema-notificationrulespec }

Notification rule: core event and condition → recipient → text and buttons. Stored and executed by the notification service; templates are {{payload.…}}, {{event.…}}, {{task.…}} substitution without logic.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `description` | `string` |  |  |
| `on` | [объект](#schema-notificationrulespec-on) | да |  |
| `recipient` | [объект](#schema-notificationrulespec-recipient) | да |  |
| `notification` | [объект](#schema-notificationrulespec-notification) | да |  |
| `dedupKeyTemplate` | `string` |  |  |
| `close` | [объект](#schema-notificationrulespec-close) |  | Close the notification's buttons with the same deduplication key when the event arrives |
| `status` | `enabled` \| `disabled` |  | enabled by default |

### `notificationRuleSpec.on` { #schema-notificationrulespec-on }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` | да | Core catalog event type or a prefix.* |
| `when` | `object` \| `boolean` |  | Condition in the core rule grammar over payload, event and task |

### `notificationRuleSpec.recipient` { #schema-notificationrulespec-recipient }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | `assigned` \| `role` \| `taskOwner` \| `taskAssignee` \| `principal` | да |  |
| `ref` | `string` |  | Path to a principal or role in the event (assigned, role) or an id/variable (principal) |
| `workspace` | `string` |  | Path to the workspace for role; defaults to the event's workspace |
| `fallback` | `taskOwner` \| `taskAssignee` \| `none` |  | По умолчанию `none`. |

### `notificationRuleSpec.notification` { #schema-notificationrulespec-notification }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` | да | Notification type: recipient settings and mandatory rules work by it |
| `title` | `string` | да |  |
| `body` | `string` |  |  |
| `links` | array of [объект](#schema-notificationrulespec-notification-links-item) |  |  |
| `actions` | array of `approvalDecide` |  | approvalDecide: Approve/Reject buttons for the decision from payload.approvalId |

### `notificationRuleSpec.notification.links[]` { #schema-notificationrulespec-notification-links-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `label` | `string` | да |  |
| `url` | `string` | да |  |

### `notificationRuleSpec.close` { #schema-notificationrulespec-close }

Close the notification's buttons with the same deduplication key when the event arrives

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `on` | array of `string` | да |  |
| `outcome` | `string` |  | Outcome template shown instead of the buttons |
<!-- /generated:schema-notification-rule -->

## Процесс (`kind: Process`) { #process }

<!-- generated:schema-process -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/object.schema.json`.

### `processSpec` { #schema-processspec }

Process: a case with stages and execution blocks, data by schema, CEL expressions, projection into memory. Executed by the core

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `version` | `integer` | да | Definition version: a published version is immutable |
| `displayName` | [`displayName`](#schema-displayname) | да |  |
| `description` | `string` |  |  |
| `workspaceId` | `string` |  |  |
| `identity` | [объект](#schema-processspec-identity) |  | On whose behalf the process acts: an agent description of kind service or agent |
| `owner` | [`assignChain`](#schema-assignchain) |  | Process owner: tasks about the process are addressed to them (divergence from the regulation, instance errors). Optional; the package check warns if it is missing |
| `calendar` | [`typeKey`](#schema-typekey) |  | Default calendar for cal.* |
| `due` | [`processDue`](#schema-processdue) |  | Due of the whole process from the instance start |
| `data` | [`jsonSchema`](#schema-jsonschema) | да | JSON Schema of the instance data; package-sdk expands {$ref: &lt;package file&gt;} |
| `start` | [объект](#schema-processspec-start) | да |  |
| `correlate` | array of [объект](#schema-processspec-correlate-item) |  |  |
| `stages` | array of [`processStage`](#schema-processstage) | да |  |
| `onEvent` | array of [объект](#schema-processspec-onevent-item) |  |  |
| `timers` | [`processTimers`](#schema-processtimers) |  |  |
| `decisions` | array of [`decisionTable`](#schema-decisiontable) |  |  |
| `governedBy` | [`governedBy`](#schema-governedby) |  |  |
| `memory` | [`memoryProjection`](#schema-memoryprojection) |  |  |
| `retrospective` | [объект](#schema-processspec-retrospective) |  | Review of a closed case: the agent proposes lessons, a human confirms |
| `migrations` | array of [объект](#schema-processspec-migrations-item) |  |  |

### `processSpec.identity` { #schema-processspec-identity }

On whose behalf the process acts: an agent description of kind service or agent

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `agent` | [`slug`](#schema-slug) | да |  |

### `processSpec.start` { #schema-processspec-start }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `on` | [`processTrigger`](#schema-processtrigger) | да |  |
| `key` | [`cel`](#schema-cel) | да | Instance key: a repeated event with the same key is a correlate, not a new instance |
| `set` | [`celMap`](#schema-celmap) |  |  |

### `processSpec.correlate[]` { #schema-processspec-correlate-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `on` | [`processTrigger`](#schema-processtrigger) | да |  |
| `key` | [`cel`](#schema-cel) | да |  |
| `set` | [`celMap`](#schema-celmap) |  |  |
| `do` | [`blocks`](#schema-blocks) |  |  |

### `processSpec.onEvent[]` { #schema-processspec-onevent-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `on` | [`processTrigger`](#schema-processtrigger) | да |  |
| `do` | [`blocks`](#schema-blocks) | да |  |

### `processSpec.retrospective` { #schema-processspec-retrospective }

Review of a closed case: the agent proposes lessons, a human confirms

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `skill` | `string` |  | По умолчанию `process.retrospective@1`. |
| `taskType` | [`typeKey`](#schema-typekey) | да |  |
| `assign` | [`assignChain`](#schema-assignchain) | да |  |
| `appliesTo` | array of `string` |  | Entity kinds lessons are attached to |
| `when` | [`cel`](#schema-cel) |  |  |

### `processSpec.migrations[]` { #schema-processspec-migrations-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `from` | `integer` | да |  |
| `to` | `integer` | да |  |
| `policy` | `pin` \| `migrate` | да |  |
| `map` | map → [`processElementId`](#schema-processelementid) |  |  |

### `assignChain` { #schema-assignchain }

Candidates in order: the first resolvable one is taken

Значение: array of [`assignee`](#schema-assignee).

### `assignee` { #schema-assignee }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `principal` | [`envOrUuid`](#schema-envoruuid) |  |  |
| `role` | [`slug`](#schema-slug) |  |  |
| `agent` | [`slug`](#schema-slug) |  |  |
| `expr` | [`cel`](#schema-cel) |  | CEL → principal id, agent:&lt;key&gt; or role:&lt;slug&gt; |

Ровно одно из: `principal`, `role`, `agent`, `expr`.

### `cel` { #schema-cel }

CEL expression in the taimen/1 profile: variables data, event, step, task, instance; cal.* functions; no current time. The core checks types and the cost limit

Значение: `string`.

### `processDue` { #schema-processdue }

Due (SLA) of a step or process: an ISO 8601 duration, {at}, a point in time or a duration from data, or exactly one of duration, workdays, workhours with optional calendar and warnBefore

Значение: [`durationOrCel`](#schema-durationorcel) или [объект `{duration, workdays, workhours, calendar, warnBefore}`](#schema-processdue-2).

### `processDue (2)` { #schema-processdue-2 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `duration` | [`duration`](#schema-duration) |  |  |
| `workdays` | [`workdayAmount`](#schema-workdayamount) |  |  |
| `workhours` | [`workhourAmount`](#schema-workhouramount) |  |  |
| `calendar` | [`typeKey`](#schema-typekey) |  | Calendar of the working units; defaults to the process's spec.calendar |
| `warnBefore` | [`workingSpan`](#schema-workingspan) |  | Warning threshold before the due; without it there is no warning |

Ровно одно из: `duration`, `workdays`, `workhours`.

### `durationOrCel` { #schema-durationorcel }

ISO 8601 duration or a CEL expression yielding a point in time (timestamp) or a duration

Значение: [`duration`](#schema-duration) или [объект `{at}`](#schema-durationorcel-2).

### `durationOrCel (2)` { #schema-durationorcel-2 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `at` | [`cel`](#schema-cel) | да |  |

### `workdayAmount` { #schema-workdayamount }

Значение: [`workdayCount`](#schema-workdaycount) или [`workingAmountExpr`](#schema-workingamountexpr).

### `workdayCount` { #schema-workdaycount }

Workdays by the calendar: the same time of day n workdays later (cal.addWorkdays)

Значение: `integer`.

### `workingAmountExpr` { #schema-workingamountexpr }

Number of work units as a CEL expression: a non-negative integer, evaluated once on entering the step (settings.* are the package settings); after that the due date is computed as from a number

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `expr` | [`cel`](#schema-cel) | да |  |

### `workhourAmount` { #schema-workhouramount }

Значение: [`workhourCount`](#schema-workhourcount) или [`workingAmountExpr`](#schema-workingamountexpr).

### `workhourCount` { #schema-workhourcount }

Working-time hours by a calendar with working hours (cal.addWorkingTime)

Значение: `number`.

### `workingSpan` { #schema-workingspan }

Interval: an ISO 8601 duration (astronomical time), {workdays} or {workhours} by the due calendar

Значение: [`duration`](#schema-duration) или [объект `{workdays}`](#schema-workingspan-2) или [объект `{workhours}`](#schema-workingspan-3).

### `workingSpan (2)` { #schema-workingspan-2 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `workdays` | [`workdayAmount`](#schema-workdayamount) | да |  |

### `workingSpan (3)` { #schema-workingspan-3 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `workhours` | [`workhourAmount`](#schema-workhouramount) | да |  |

### `processTrigger` { #schema-processtrigger }

Event source: a core journal event or an observation. where is a CEL filter over event

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `event` | `string` |  |  |
| `observation` | `string` |  |  |
| `source` | `string` |  |  |
| `where` | [`cel`](#schema-cel) |  |  |

Ровно одно из: `event`, `observation`.

### `celMap` { #schema-celmap }

Path in the instance data → CEL expression

Значение: map → [`cel`](#schema-cel).

### `blocks` { #schema-blocks }

Sequence of steps (do block)

Значение: array of [`processStep`](#schema-processstep).

### `processStep` { #schema-processstep }

Process step: exactly one kind (human, approve, call, decide, recall, remember, listen, wait, set, raise, compensate, fork, try, do, suspend, resume, complete) plus common fields

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | да |  |
| `displayName` | [`displayName`](#schema-displayname) |  |  |
| `when` | [`cel`](#schema-cel) |  | Guard: the step runs only if it is true |
| `input` | [объект](#schema-processstep-input) |  |  |
| `output` | [объект](#schema-processstep-output) |  | Writing the step result (step.result) into the instance data |
| `export` | [объект](#schema-processstep-export) |  |  |
| `governedBy` | [`governedBy`](#schema-governedby) |  |  |
| `onCompensate` | [`blocks`](#schema-blocks) |  | Compensation of a completed step: runs on compensate in reverse order |
| `human` | [объект](#schema-processstep-human) |  |  |
| `approve` | [объект](#schema-processstep-approve) |  |  |
| `call` | [объект](#schema-processstep-call) |  |  |
| `decide` | [объект](#schema-processstep-decide) |  |  |
| `recall` | [объект](#schema-processstep-recall) |  | Memory query through the core; the answer is a journal event (deterministic replay) |
| `remember` | [объект](#schema-processstep-remember) |  | Write to memory as a core observation from the process identity, with a reference to the case |
| `listen` | [объект](#schema-processstep-listen) |  | Waiting for the first of the events (deferred choice); timeout is a timer |
| `wait` | [`durationOrCel`](#schema-durationorcel) |  | Pause: a duration or a point in time; wait has no due, the pause itself sets the time |
| `set` | [`celMap`](#schema-celmap) |  |  |
| `raise` | [`processError`](#schema-processerror) |  |  |
| `compensate` | = `all` или array of [`processElementId`](#schema-processelementid) |  | Run onCompensate of completed steps in reverse order |
| `fork` | [объект](#schema-processstep-fork) |  |  |
| `try` | [объект](#schema-processstep-try) |  |  |
| `do` | [`blocks`](#schema-blocks) |  |  |
| `suspend` | [объект](#schema-processstep-suspend) |  |  |
| `resume` | [объект](#schema-processstep-resume) |  |  |
| `complete` | [объект](#schema-processstep-complete) |  |  |

Ровно одно из: `human`, `approve`, `call`, `decide`, `recall`, `remember`, `listen`, `wait`, `set`, `raise`, `compensate`, `fork`, `try`, `do`, `suspend`, `resume`, `complete`.

### `processStep.input` { #schema-processstep-input }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `from` | [`cel`](#schema-cel) |  |  |

### `processStep.output` { #schema-processstep-output }

Writing the step result (step.result) into the instance data

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `as` | [`celMap`](#schema-celmap) |  |  |

### `processStep.export` { #schema-processstep-export }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `as` | [`celMap`](#schema-celmap) |  |  |

### `processStep.human` { #schema-processstep-human }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `taskType` | [`typeKey`](#schema-typekey) | да |  |
| `title` | [`cel`](#schema-cel) |  |  |
| `customFields` | map → [`cel`](#schema-cel) |  | Prefill of the created task's fields with case data: a field of the type's fieldSchema → CEL; checked against fieldSchema on publication and on task creation, null leaves the field to the human |
| `form` | [`processForm`](#schema-processform) |  |  |
| `assign` | [`assignChain`](#schema-assignchain) | да |  |
| `due` | [`processDue`](#schema-processdue) |  |  |
| `escalations` | array of [`escalation`](#schema-escalation) |  |  |
| `context` | [`stepContext`](#schema-stepcontext) |  |  |

### `processStep.approve` { #schema-processstep-approve }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `taskType` | [`typeKey`](#schema-typekey) |  |  |
| `approvers` | [`assignChain`](#schema-assignchain) | да |  |
| `mode` | `parallel` \| `sequential` |  | По умолчанию `parallel`. |
| `quorum` | `all` \| `any` или [объект `{atLeast}`](#schema-processstep-approve-quorum-2) или [объект `{percent}`](#schema-processstep-approve-quorum-3) | да |  |
| `earlyDecision` | `boolean` |  | По умолчанию `true`. |
| `separationOfDuties` | [`cel`](#schema-cel) |  | CEL → list of principals who may not vote; the core checks it at decision time |
| `due` | [`processDue`](#schema-processdue) |  |  |
| `onDue` | `approve` \| `reject` \| `escalate` |  |  |
| `escalations` | array of [`escalation`](#schema-escalation) |  |  |
| `context` | [`stepContext`](#schema-stepcontext) |  |  |

### `processStep.approve.quorum (2)` { #schema-processstep-approve-quorum-2 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `atLeast` | `integer` | да |  |

### `processStep.approve.quorum (3)` { #schema-processstep-approve-quorum-3 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `percent` | `number` | да |  |

### `processStep.call` { #schema-processstep-call }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `skill` | `string` |  |  |
| `agent` | [`slug`](#schema-slug) |  |  |
| `process` | [`typeKey`](#schema-typekey) |  |  |
| `input` | [`celMap`](#schema-celmap) |  |  |
| `timeout` | [`durationOrCel`](#schema-durationorcel) |  |  |
| `due` | [`processDue`](#schema-processdue) |  |  |
| `context` | [`stepContext`](#schema-stepcontext) |  |  |

Ровно одно из: `skill`, `agent`, `process`.

### `processStep.decide` { #schema-processstep-decide }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `table` | [`processElementId`](#schema-processelementid) | да |  |
| `input` | [`celMap`](#schema-celmap) |  |  |

### `processStep.recall` { #schema-processstep-recall }

Memory query through the core; the answer is a journal event (deterministic replay)

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `anchors` | array of [`memoryAnchor`](#schema-memoryanchor) | да |  |
| `traverse` | [`memoryTraverse`](#schema-memorytraverse) |  |  |
| `query` | [`cel`](#schema-cel) |  | Semantic expansion text |
| `kinds` | array of `string` |  |  |
| `where` | [`memoryWhere`](#schema-memorywhere) |  |  |
| `limit` | `integer` |  |  |
| `timeout` | [`duration`](#schema-duration) |  |  |
| `due` | [`processDue`](#schema-processdue) |  |  |
| `onTimeout` | [`blocks`](#schema-blocks) |  |  |

### `processStep.remember` { #schema-processstep-remember }

Write to memory as a core observation from the process identity, with a reference to the case

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `entity` | [объект](#schema-processstep-remember-entity) |  |  |
| `facts` | [`celMap`](#schema-celmap) |  | Case fact name → value |

Ровно одно из: `facts`, `entity`.

### `processStep.remember.entity` { #schema-processstep-remember-entity }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | `string` | да |  |
| `key` | [`cel`](#schema-cel) | да |  |
| `name` | [`cel`](#schema-cel) |  |  |
| `text` | [`cel`](#schema-cel) |  |  |
| `links` | array of [объект](#schema-processstep-remember-entity-links-item) |  |  |

### `processStep.remember.entity.links[]` { #schema-processstep-remember-entity-links-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `rel` | `string` | да |  |
| `kind` | `string` | да |  |
| `key` | [`cel`](#schema-cel) | да |  |

### `processStep.listen` { #schema-processstep-listen }

Waiting for the first of the events (deferred choice); timeout is a timer

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `any` | array of [объект](#schema-processstep-listen-any-item) | да |  |
| `timeout` | [`durationOrCel`](#schema-durationorcel) |  |  |
| `due` | [`processDue`](#schema-processdue) |  |  |
| `onTimeout` | [`blocks`](#schema-blocks) |  |  |

### `processStep.listen.any[]` { #schema-processstep-listen-any-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `on` | [`processTrigger`](#schema-processtrigger) | да |  |
| `do` | [`blocks`](#schema-blocks) |  |  |

### `processStep.fork` { #schema-processstep-fork }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `mode` | `all` \| `compete` |  | По умолчанию `all`. |
| `branches` | array of [объект](#schema-processstep-fork-branches-item) | да |  |

### `processStep.fork.branches[]` { #schema-processstep-fork-branches-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | да |  |
| `do` | [`blocks`](#schema-blocks) | да |  |

### `processStep.try` { #schema-processstep-try }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `do` | [`blocks`](#schema-blocks) | да |  |
| `retry` | [объект](#schema-processstep-try-retry) |  |  |
| `catch` | array of [объект](#schema-processstep-try-catch-item) |  |  |

### `processStep.try.retry` { #schema-processstep-try-retry }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `limit` | `integer` | да |  |
| `delay` | [`duration`](#schema-duration) |  |  |
| `backoff` | `constant` \| `exponential` |  |  |
| `maxDelay` | [`duration`](#schema-duration) |  |  |
| `on` | array of `string` |  | Error types to retry; all by default |

### `processStep.try.catch[]` { #schema-processstep-try-catch-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `errors` | [объект](#schema-processstep-try-catch-item-errors) |  |  |
| `as` | `string` |  |  |
| `do` | [`blocks`](#schema-blocks) | да |  |

### `processStep.try.catch[].errors` { #schema-processstep-try-catch-item-errors }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` |  |  |
| `status` | `integer` |  |  |

### `processStep.suspend` { #schema-processstep-suspend }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `reason` | [`cel`](#schema-cel) |  |  |

### `processStep.resume` { #schema-processstep-resume }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `reason` | [`cel`](#schema-cel) |  |  |

### `processStep.complete` { #schema-processstep-complete }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `outcome` | `string` | да |  |

### `processElementId` { #schema-processelementid }

Stable process element id: the schema layout, migration maps, the journal and the memory graph refer to it. Renaming only via the migrations map

Значение: `string`.

### `governedBy` { #schema-governedby }

Knowledge base regulations the element is subject to: the natural key of the memory document and, if needed, a clause

Значение: array of [объект](#schema-governedby-item).

### `governedBy[]` { #schema-governedby-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `document` | `string` | да |  |
| `section` | `string` |  |  |

### `processForm` { #schema-processform }

Step form: JSON Schema of the data and JSON Forms uischema of the view

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `schema` | [`jsonSchema`](#schema-jsonschema) | да |  |
| `uischema` | `object` |  |  |

### `escalation` { #schema-escalation }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `after` | = `due` или [`durationOrCel`](#schema-durationorcel) | да | due means at the due moment; a duration means after the due |
| `action` | `remind` \| `reassign` \| `notify` \| `raise` | да |  |
| `to` | [`assignChain`](#schema-assignchain) |  |  |
| `error` | [`processError`](#schema-processerror) |  |  |

### `processError` { #schema-processerror }

Error in RFC 7807 form

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` | да |  |
| `status` | `integer` |  |  |
| `detail` | [`cel`](#schema-cel) |  |  |

### `stepContext` { #schema-stepcontext }

Context profile of the step executor from memory: explicit relations first, semantic expansion marked inferred

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `anchors` | array of [`memoryAnchor`](#schema-memoryanchor) | да |  |
| `traverse` | [`memoryTraverse`](#schema-memorytraverse) |  |  |
| `semantic` | `boolean` |  | Semantic expansion (inferred); true by default |
| `budgetTokens` | `integer` |  |  |

### `memoryAnchor` { #schema-memoryanchor }

Graph traversal anchor: the instance's case node or an entity by natural key (CEL over data)

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `case` | = `true` |  |  |
| `kind` | `string` |  |  |
| `key` | [`cel`](#schema-cel) |  |  |
| `via` | `string` |  |  |

Ровно одно из: `case`, `key` + `kind`.

### `memoryTraverse` { #schema-memorytraverse }

Traversal steps from the anchors, the same shape as traverse in contextSchema

Значение: array of [объект](#schema-memorytraverse-item).

### `memoryTraverse[]` { #schema-memorytraverse-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `relation` | `string` | да |  |
| `direction` | `in` \| `out` \| `both` |  |  |
| `depth` | `integer` |  |  |
| `limit` | `integer` |  |  |
| `from` | `anchors` \| `previous` |  |  |

### `memoryWhere` { #schema-memorywhere }

Filters on node attributes: applied to result nodes and to candidate anchors of semantic expansion; conditions are joined with AND

Значение: array of [объект](#schema-memorywhere-item).

### `memoryWhere[]` { #schema-memorywhere-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `attr` | `string` | да | Node attribute name (flat), e.g. okpd2 or validUntil; a list attribute satisfies the condition if any of its elements does |
| `op` | `eq` \| `in` \| `prefix` \| `lte` \| `gte` \| `exists` | да | prefix compares codes by dot-separated segments: 62.01 matches 62.01.11 but not 62.011; lte/gte are RFC 3339 dates or numbers |
| `value` | [`cel`](#schema-cel) или `number` \| `boolean` или array of [`cel`](#schema-cel) |  | CEL expression over the instance data (a string literal goes in CEL quotes: "'62.01'"); for in, a CEL list or a list of expressions; for exists, true or false |

Условия:

| Условие | Следствие |
|---|---|
| `op` ≠ `exists` | обязательно `value` |

### `processStage` { #schema-processstage }

Case stage (CMMN): entry and exit by guards, milestones, required and optional work

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | да |  |
| `displayName` | [`displayName`](#schema-displayname) |  |  |
| `entry` | [`cel`](#schema-cel) |  | Entry guard; stage.&lt;id&gt;.completed, milestone.&lt;id&gt; and data are available in the expression |
| `exit` | [`cel`](#schema-cel) |  |  |
| `repeatable` | `boolean` |  |  |
| `governedBy` | [`governedBy`](#schema-governedby) |  |  |
| `steps` | [`blocks`](#schema-blocks) | да |  |
| `discretionary` | array of [`processStep`](#schema-processstep) |  | Work a human adds at their discretion |
| `milestones` | array of [объект](#schema-processstage-milestones-item) |  |  |
| `timers` | [`processTimers`](#schema-processtimers) |  |  |

### `processStage.milestones[]` { #schema-processstage-milestones-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | да |  |
| `when` | [`cel`](#schema-cel) | да |  |

### `processTimers` { #schema-processtimers }

Boundary timers: fire while the stage (process) is open; at from data is recalculated when the data changes

Значение: array of [объект](#schema-processtimers-item).

### `processTimers[]` { #schema-processtimers-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | да |  |
| `at` | [`durationOrCel`](#schema-durationorcel) | да |  |
| `interrupting` | `boolean` |  | По умолчанию `false`. |
| `do` | [`blocks`](#schema-blocks) | да |  |

### `decisionTable` { #schema-decisiontable }

Decision table (DMN in spirit). Condition cell: '-' (any), a literal, a list 'a,b', a range '[a..b)'

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | да |  |
| `displayName` | [`displayName`](#schema-displayname) |  |  |
| `hitPolicy` | `first` \| `unique` \| `collect` | да |  |
| `governedBy` | [`governedBy`](#schema-governedby) |  |  |
| `inputs` | array of [объект](#schema-decisiontable-inputs-item) | да |  |
| `outputs` | array of [объект](#schema-decisiontable-outputs-item) | да |  |
| `rules` | array of [объект](#schema-decisiontable-rules-item) | да |  |

### `decisionTable.inputs[]` { #schema-decisiontable-inputs-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | да |  |
| `expr` | [`cel`](#schema-cel) | да |  |
| `type` | `string` \| `number` \| `boolean` \| `date` \| `timestamp` |  |  |

### `decisionTable.outputs[]` { #schema-decisiontable-outputs-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | да |  |
| `type` | `string` \| `number` \| `boolean` \| `date` \| `duration` \| `object` \| `array` |  |  |

### `decisionTable.rules[]` { #schema-decisiontable-rules-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `when` | map → `string` \| `number` \| `boolean` | да |  |
| `then` | `object` | да |  |
| `note` | `string` |  |  |
| `governedBy` | [`governedBy`](#schema-governedby) |  |  |

### `memoryProjection` { #schema-memoryprojection }

Projection of the case into the memory graph: delivered by events, only declared fields go into the graph

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `case` | [объект](#schema-memoryprojection-case) | да |  |
| `facts` | [`celMap`](#schema-celmap) |  | Case fact name → value; a change closes the previous fact with a validity end |
| `entities` | array of [объект](#schema-memoryprojection-entities-item) |  |  |
| `documents` | [объект](#schema-memoryprojection-documents) |  |  |

### `memoryProjection.case` { #schema-memoryprojection-case }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | `string` |  | По умолчанию `case`. |
| `key` | [`cel`](#schema-cel) | да |  |
| `title` | [`cel`](#schema-cel) |  |  |

### `memoryProjection.entities[]` { #schema-memoryprojection-entities-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | `string` | да |  |
| `key` | [`cel`](#schema-cel) | да |  |
| `name` | [`cel`](#schema-cel) |  |  |
| `rel` | `string` | да |  |
| `when` | [`cel`](#schema-cel) |  |  |
| `many` | `boolean` |  | key yields a list: one entity per element |

### `memoryProjection.documents` { #schema-memoryprojection-documents }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `artifacts` | array of [`typeKey`](#schema-typekey) |  |  |
<!-- /generated:schema-process -->

## Календарь (`kind: Calendar`) { #calendar }

<!-- generated:schema-calendar -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/object.schema.json`.

### `calendarSpec` { #schema-calendarspec }

Business calendar: default days off, holidays and transfers by year

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `displayName` | [`displayName`](#schema-displayname) | да |  |
| `timezone` | `string` | да |  |
| `weekend` | array of `integer` |  | ISO weekdays: 1 is Monday. По умолчанию `[6, 7]`. |
| `workingHours` | [объект](#schema-calendarspec-workinghours) |  | Working hours on the calendar's working days, in the calendar's local time. Without the field the calendar knows only working days |
| `years` | array of [объект](#schema-calendarspec-years-item) | да |  |

### `calendarSpec.workingHours` { #schema-calendarspec-workinghours }

Working hours on the calendar's working days, in the calendar's local time. Without the field the calendar knows only working days

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `intervals` | [`workingIntervals`](#schema-workingintervals) | да | Intervals of a regular working day |
| `weekdays` | map → [`workingIntervals`](#schema-workingintervals) |  | Intervals per ISO weekday (1 is Monday) instead of intervals; [] means no working hours |
| `shortDayReduction` | [`duration`](#schema-duration) |  | How much shorter a shortened day (shortDays) is: subtracted from the end of the last interval |

### `calendarSpec.years[]` { #schema-calendarspec-years-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `year` | `integer` | да |  |
| `provisional` | `boolean` |  | The year is not approved yet: cal.* results are marked as preliminary |
| `source` | `string` |  |  |
| `holidays` | array of `string` (date) |  |  |
| `workdays` | array of `string` (date) |  | Transferred working days that fall on days off |
| `shortDays` | array of `string` (date) |  |  |

### `workingIntervals` { #schema-workingintervals }

Working-time intervals of the day, in order and non-overlapping, from before to (the core checks the order); 24:00 is the end of the day

Значение: array of [объект](#schema-workingintervals-item).

### `workingIntervals[]` { #schema-workingintervals-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `from` | `string` | да |  |
| `to` | `string` | да |  |
<!-- /generated:schema-calendar -->

## Онтология (`kind: KnowledgePack`) { #knowledge-pack }

Тело онтологии описывает отдельный файл схемы `knowledge-pack.schema.json`; в пакете к нему добавляется целая версия `version`.

<!-- generated:schema-knowledge-pack -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/object.schema.json`, `sdk/package-sdk/schema/v1/knowledge-pack.schema.json`.

### `KnowledgePack.spec` { #schema-knowledgepack-spec }

Включает [`knowledge-pack`](#schema-knowledge-pack).

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `version` | `integer` |  | Ontology version in the package, an integer: an inclusion refers to it as name@version, an edit is a new version |

### `knowledge-pack` { #schema-knowledge-pack }

Форма пакета видов и связей базы знаний. Пакет регистрируется через ядро (POST /api/v1/knowledge/packs) и включается для дерева workspace. memory-service разбирает name, version, scope, namespace, kinds (kind, kindAliases, aliases, naturalKey, idPatterns, attributes, searchable) и relations; остальные поля — данные загрузчиков и генератора шаблонов импорта, память их пропускает.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `name` | `string` | да | Имя пакета без префикса. Ссылка на пакет арендатора в настройке namespace — tenant:&lt;имя&gt;@&lt;версия&gt; |
| `version` | `string` \| `integer` | да | Версия пакета; шаблоны видов версионируются ею |
| `scope` | `common` \| `tenant` |  | common — общий пакет, регистрирует администратор платформы; tenant — пакет арендатора по праву knowledge.packs.manage: виден и включается только в namespace-владельце и под ним, имена пакета, видов и связей не совпадают с общими. По умолчанию `common`. |
| `namespace` | `string` |  | Namespace-владелец пакета арендатора (scope: tenant); при регистрации через ядро его подставляет ядро по workspace |
| `description` | `string` |  |  |
| `extends` | array of `string` |  | Пакеты, на виды которых ссылаются связи и профили этого пакета (например company@1). Базовый пакет не меняется |
| `kinds` | array of [`knowledge-pack/kind`](#schema-knowledge-pack-kind) | да |  |
| `relations` | array of [`knowledge-pack/relation`](#schema-knowledge-pack-relation) |  |  |
| `profiles` | array of [`knowledge-pack/profile`](#schema-knowledge-pack-profile) |  | Профили атрибутов видов, в том числе видов других пакетов: так пакет описывает атрибуты чужого вида, не меняя и не переобъявляя его (credential с type: sro_membership у расширения отрасли, legal_entity пакета default у company). Проверяют загрузчики и генератор шаблонов |
| `expiry` | array of [`knowledge-pack/expiry`](#schema-knowledge-pack-expiry) |  | Кому и за сколько дней ставить задачу об истечении validUntil вида (правило knowledge-expiry). Без записи — роль владельца базы знаний и 30 дней |

### `knowledge-pack/kind` { #schema-knowledge-pack-kind }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | [`knowledge-pack/name`](#schema-knowledge-pack-name) | да |  |
| `title` | `string` |  | Название вида для людей — заголовок шаблона и раздела консоли |
| `description` | `string` |  |  |
| `kindAliases` | array of [`knowledge-pack/name`](#schema-knowledge-pack-name) |  |  |
| `aliases` | array of `string` |  |  |
| `naturalKey` | `string` или `object` |  | Форма естественного ключа: шаблон с плейсхолдерами ("offering:&lt;source&gt;:&lt;id&gt;") или JSON Schema строки |
| `idPatterns` | array of `string` |  |  |
| `attributes` | [`knowledge-pack/attributes`](#schema-knowledge-pack-attributes) |  |  |
| `searchable` | [объект](#schema-knowledge-pack-kind-searchable) |  | Вид находится поиском по смыслу: сверка индексирует эмбеддинг из title сущности и значений перечисленных атрибутов; каждый атрибут объявлен в attributes.properties |

### `knowledge-pack/kind.searchable` { #schema-knowledge-pack-kind-searchable }

Вид находится поиском по смыслу: сверка индексирует эмбеддинг из title сущности и значений перечисленных атрибутов; каждый атрибут объявлен в attributes.properties

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `fields` | array of `string` | да |  |

### `knowledge-pack/name` { #schema-knowledge-pack-name }

Значение: `string`.

### `knowledge-pack/attributes` { #schema-knowledge-pack-attributes }

JSON Schema атрибутов вида (draft 2020-12). title и description свойства — заголовок и подсказка колонки шаблона; type, format, enum — проверка; required — обязательность. Сроки действия — по соглашению validFrom и validUntil (format: date). Свойство с персональными данными физического лица допустимо только с x-personal-data: allowed — такие значения не попадают в промпты ИИ

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | = `object` |  |  |
| `properties` | [объект](#schema-knowledge-pack-attributes-properties) |  |  |

### `knowledge-pack/attributes.properties` { #schema-knowledge-pack-attributes-properties }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `validFrom` | [`knowledge-pack/dateProperty`](#schema-knowledge-pack-dateproperty) |  |  |
| `validUntil` | [`knowledge-pack/dateProperty`](#schema-knowledge-pack-dateproperty) |  |  |

### `knowledge-pack/dateProperty` { #schema-knowledge-pack-dateproperty }

Соглашение сроков: validFrom и validUntil — день ISO 8601

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | = `string` | да |  |
| `format` | = `date` | да |  |

### `knowledge-pack/relation` { #schema-knowledge-pack-relation }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `relation` | [`knowledge-pack/name`](#schema-knowledge-pack-name) | да |  |
| `title` | `string` |  | Заголовок колонки связи в шаблоне |
| `fromKinds` | array of [`knowledge-pack/name`](#schema-knowledge-pack-name) |  |  |
| `toKinds` | array of [`knowledge-pack/name`](#schema-knowledge-pack-name) |  |  |
| `temporal` | `boolean` |  | По умолчанию `true`. |
| `cardinality` | `one` \| `many` |  | По умолчанию `many`. |

### `knowledge-pack/profile` { #schema-knowledge-pack-profile }

Атрибуты вида этого или другого пакета. С when — у сущностей, где атрибут равен значению (credential с type: sro_membership); без when — у всех сущностей вида (атрибуты legal_entity пакета default)

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | [`knowledge-pack/name`](#schema-knowledge-pack-name) | да |  |
| `when` | [объект](#schema-knowledge-pack-profile-when) |  |  |
| `title` | `string` |  |  |
| `attributes` | [`knowledge-pack/attributes`](#schema-knowledge-pack-attributes) | да |  |

### `knowledge-pack/profile.when` { #schema-knowledge-pack-profile-when }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `attr` | `string` | да |  |
| `equals` | `string` \| `number` \| `boolean` | да |  |

### `knowledge-pack/expiry` { #schema-knowledge-pack-expiry }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | [`knowledge-pack/name`](#schema-knowledge-pack-name) | да |  |
| `role` | `string` |  | Роль, которой ставится задача |
| `leadDays` | `integer` |  |  |
<!-- /generated:schema-knowledge-pack -->

## Общие типы { #common }

Определения, на которые ссылаются несколько видов.

<!-- generated:schema-common -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/object.schema.json`.

### `connectionKey` { #schema-connectionkey }

Key of a connection type or of a connection

Значение: `string`.

### `displayName` { #schema-displayname }

Значение: `string`.

### `duration` { #schema-duration }

ISO 8601 duration, e.g. P3D, PT4H

Значение: `string`.

### `envOrUuid` { #schema-envoruuid }

UUID or an installation ${VARIABLE} (environment topology is not written into the package)

Значение: `string`.

### `jsonSchema` { #schema-jsonschema }

Document JSON Schema (draft 2020-12). The core rejects remote $ref.

Значение: `object`.

### `lifecycle` { #schema-lifecycle }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `statuses` | array of [объект](#schema-lifecycle-statuses-item) | да |  |
| `transitions` | array of [объект](#schema-lifecycle-transitions-item) |  |  |
| `initialStatus` | [`statusKey`](#schema-statuskey) |  |  |

### `lifecycle.statuses[]` { #schema-lifecycle-statuses-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | [`statusKey`](#schema-statuskey) | да |  |
| `category` | `string` | да |  |
| `displayName` | `string` |  |  |

### `lifecycle.transitions[]` { #schema-lifecycle-transitions-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `from` | [`statusKey`](#schema-statuskey) | да |  |
| `to` | array of [`statusKey`](#schema-statuskey) | да |  |

### `mediaType` { #schema-mediatype }

Lowercase media type; a */* or type/* mask is allowed

Значение: `string`.

### `ruleKey` { #schema-rulekey }

Rule key in the tenant

Значение: `string`.

### `slug` { #schema-slug }

Значение: `string`.

### `statusKey` { #schema-statuskey }

Значение: `string`.

### `typeKey` { #schema-typekey }

Type key: lowercase Latin letters, digits, _ and -

Значение: `string`.
<!-- /generated:schema-common -->

## Тест пакета (`tests/*.test.yaml`) { #test-file }

<!-- generated:schema-test -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/test.schema.json`.

### `test` { #schema-test }

File &lt;name&gt;.test.yaml in the package's tests/ directory. Run by the core (POST /packages:test) with the same engine as a live run, in a sandbox: tasks, approvals and timers are in memory, skills, agents and memory are stubs checked against the catalog schemas, time is virtual. No side effects.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `$schema` | `string` |  |  |
| `process` | `string` |  | Package process key |
| `version` | `integer` |  | Defaults to the version in the package |
| `name` | `string` | да |  |
| `description` | `string` |  |  |
| `subject` | `process` \| `rule` \| `taskType` |  | What the test checks: a process (default), a work rule or a task type (gate outcomes, acceptance criteria, completion actions). По умолчанию `process`. |
| `rule` | `string` |  | Package WorkRule key (subject: rule) |
| `taskType` | `string` |  | Package TaskType key (subject: taskType) |
| `given` | `object` |  |  |
| `mocks` | [объект](#schema-test-mocks) |  |  |
| `steps` | array of `object` | да |  |
| `coverage` | [объект](#schema-test-coverage) |  |  |

Условия:

| Условие | Следствие |
|---|---|
| не (`subject` ∈ `rule`, `taskType`) | обязательно `process`; `given`: [`processGiven`](#schema-processgiven); `steps`: array of [`testStep`](#schema-teststep) |
| `subject` = `rule` | обязательно `rule`; `given`: [`ruleGiven`](#schema-rulegiven); `steps`: array of [`ruleStep`](#schema-rulestep) |
| `subject` = `taskType` | обязательно `taskType`; `given`: [`taskTypeGiven`](#schema-tasktypegiven); `steps`: array of [`taskTypeStep`](#schema-tasktypestep) |

### `test.mocks` { #schema-test-mocks }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `skills` | map → array of [`mockAnswer`](#schema-mockanswer) |  | name@version → responses in call order (or by when); the output is checked against the skill schema from the catalog |
| `agents` | map → array of [`mockAnswer`](#schema-mockanswer) |  |  |
| `recall` | array of [`mockAnswer`](#schema-mockanswer) |  | Memory responses to recall steps; step is the step id, when is CEL over the query |

### `test.coverage` { #schema-test-coverage }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `minimum` | `number` |  | Coverage threshold of process elements by this test, % |

### `mockAnswer` { #schema-mockanswer }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `step` | `string` |  |  |
| `when` | `string` |  | CEL over the call input |
| `output` | любое |  |  |
| `error` | [объект](#schema-mockanswer-error) |  |  |
| `timeout` | = `true` |  |  |

Ровно одно из: `output`, `error`, `timeout`.

### `mockAnswer.error` { #schema-mockanswer-error }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` | да |  |
| `status` | `integer` |  |  |
| `detail` | `string` |  |  |

### `processGiven` { #schema-processgiven }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `clock` | `string` (date-time) |  | Initial virtual time |
| `data` | `object` |  | Initial instance data (without a start event) |
| `stage` | `string` |  | Start with an open stage |
| `fromInstance` | `string` |  | Dry run on an environment only: state is copied from a live instance |
| `calendar` | `string` |  | Calendar key instead of the process calendar |
| `settings` | [`settings`](#schema-settings) |  |  |
| `principals` | map → array of `string` |  | Role → fictitious test principals (for assignments and separation of duties) |

### `settings` { #schema-settings }

Saved package settings values, as an administrator saves them: they replace the previously saved values, fields not given take their default from spec.settings of the manifest. The core checks them against the settings schema of the package

Значение: `object`.

### `testStep` { #schema-teststep }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `settings` | [`settings`](#schema-settings) |  | Save new settings values in the middle of the scenario: computations after this step read them, decisions already taken keep the values they read |
| `emit` | [объект](#schema-teststep-emit) |  |  |
| `advance` | `string` |  | Virtual time shift (ISO 8601, P3D) or up to a moment: until:&lt;timer id&gt; |
| `complete` | [объект](#schema-teststep-complete) |  |  |
| `approve` | [объект](#schema-teststep-approve) |  |  |
| `expect` | [объект](#schema-teststep-expect) |  |  |

Ровно одно из: `emit`, `advance`, `complete`, `approve`, `expect`, `settings`.

### `testStep.emit` { #schema-teststep-emit }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `event` | `string` |  |  |
| `observation` | `string` |  |  |
| `source` | `string` |  |  |
| `task` | `string` |  | Only with observation: id of the process step whose latest task the observation is bound to (the task field of the core's observation) |
| `by` | `string` |  | Event author (actorId): a test principal or agent:&lt;key&gt; |
| `payload` | `object` |  |  |

Ровно одно из: `event`, `observation`.

### `testStep.complete` { #schema-teststep-complete }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `step` | `string` | да |  |
| `by` | `string` |  | test principal or agent:&lt;key&gt; |
| `output` | `object` |  | Form data or the agent's result; checked against the form schema |
| `cancel` | = `true` |  |  |

### `testStep.approve` { #schema-teststep-approve }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `step` | `string` | да |  |
| `by` | `string` | да |  |
| `decision` | `approve` \| `reject` | да |  |
| `expectRefused` | `string` |  | Core rejection code, e.g. separation_of_duties_violation |

### `testStep.expect` { #schema-teststep-expect }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `stages` | map → `open` \| `completed` \| `skipped` \| `not_started` |  |  |
| `milestones` | array of `string` |  |  |
| `tasks` | array of [объект](#schema-teststep-expect-tasks-item) |  |  |
| `timers` | array of [объект](#schema-teststep-expect-timers-item) |  |  |
| `data` | `object` |  | Path in data → expected value |
| `sla` | map → `ok` \| `warning` \| `breached` \| `paused` |  | Due state: step id → state of its open attempt; the process key is the process due (spec.due) |
| `events` | array of `string` |  | process.* event types since the last expect |
| `rules` | array of [объект](#schema-teststep-expect-rules-item) |  | Decisions of the package's rules with target: task since the last expect |
| `memory` | [объект](#schema-teststep-expect-memory) |  |  |
| `outcome` | `string` |  |  |
| `status` | `running` \| `suspended` \| `completed` \| `failed` \| `cancelled` |  |  |
| `error` | `string` |  |  |
| `noSideEffects` | = `true` |  |  |

### `testStep.expect.tasks[]` { #schema-teststep-expect-tasks-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `step` | `string` |  |  |
| `status` | `string` |  |  |
| `assignee` | `string` |  |  |
| `due` | `string` |  |  |
| `customFields` | `object` |  | Subset of task fields: the given ones are compared (human step prefill) |

### `testStep.expect.timers[]` { #schema-teststep-expect-timers-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `id` | `string` |  |  |
| `at` | `string` |  |  |
| `provisional` | `boolean` |  |  |

### `testStep.expect.rules[]` { #schema-teststep-expect-rules-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `rule` | `string` |  |  |
| `action` | `string` |  |  |
| `step` | `string` |  |  |
| `result` | `matched` \| `not_matched` \| `skipped` \| `failed` |  |  |
| `reason` | `string` |  |  |

### `testStep.expect.memory` { #schema-teststep-expect-memory }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `recalled` | array of `string` |  |  |
| `remembered` | array of `object` |  |  |

### `ruleGiven` { #schema-rulegiven }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `clock` | `string` (date-time) |  |  |
| `variables` | [`variables`](#schema-variables) |  |  |
| `settings` | [`settings`](#schema-settings) |  |  |
| `task` | [объект](#schema-rulegiven-task) |  | Task created before the input: an event without taskId in the payload is about it |
| `schedule` | [объект](#schema-rulegiven-schedule) |  | Input: a firing of the rule's schedule (trigger.kind: schedule) |
| `observation` | [объект](#schema-rulegiven-observation) |  |  |
| `event` | [объект](#schema-rulegiven-event) |  |  |

Ровно одно из: `observation`, `event`, `schedule`.

### `ruleGiven.task` { #schema-rulegiven-task }

Task created before the input: an event without taskId in the payload is about it

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` | да | Task type key of the package or tenant |
| `title` | `string` |  |  |
| `status` | `string` |  |  |
| `assignee` | `string` |  | agent:&lt;key&gt; or a fictitious principal |
| `customFields` | `object` |  |  |

### `ruleGiven.schedule` { #schema-rulegiven-schedule }

Input: a firing of the rule's schedule (trigger.kind: schedule)

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `at` | `string` (date-time) |  | Slot time; defaults to clock |

### `ruleGiven.observation` { #schema-rulegiven-observation }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | `string` | да |  |
| `data` | `object` |  |  |
| `content` | `string` |  |  |
| `source` | `string` |  |  |
| `externalRef` | `object` |  |  |

### `ruleGiven.event` { #schema-rulegiven-event }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` | да |  |
| `payload` | `object` |  |  |

### `variables` { #schema-variables }

Installation variable values for the test; the rest are defaults from the manifest

Значение: map → `string`.

### `ruleStep` { #schema-rulestep }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `expect` | [объект](#schema-rulestep-expect) | да |  |

### `ruleStep.expect` { #schema-rulestep-expect }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `result` | `string` |  | Outcome of the core's rule evaluation (like result of the rule.evaluated event) |
| `ensureWork` | array of [`workExpectation`](#schema-workexpectation) |  |  |
| `invokeSkill` | array of [`skillExpectation`](#schema-skillexpectation) |  |  |
| `noSideEffects` | = `true` |  |  |

### `workExpectation` { #schema-workexpectation }

Expected work: the given fields are compared, the rest are not checked

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` |  |  |
| `title` | `string` |  |  |
| `assignee` | `string` |  | agent:&lt;key&gt;, a test role or a fictitious principal |
| `customFields` | `object` |  |  |
| `relation` | `object` |  |  |

### `skillExpectation` { #schema-skillexpectation }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `skill` | `string` | да |  |
| `inputs` | `object` |  | Subset of the call input |

### `taskTypeGiven` { #schema-tasktypegiven }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `clock` | `string` (date-time) |  |  |
| `variables` | [`variables`](#schema-variables) |  |  |
| `task` | [объект](#schema-tasktypegiven-task) |  |  |
| `artifacts` | array of [объект](#schema-tasktypegiven-artifacts-item) |  |  |
| `principals` | map → array of `string` |  | Role → fictitious test principals |

### `taskTypeGiven.task` { #schema-tasktypegiven-task }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `title` | `string` |  |  |
| `status` | `string` |  |  |
| `assignee` | `string` |  |  |
| `customFields` | `object` |  |  |

### `taskTypeGiven.artifacts[]` { #schema-tasktypegiven-artifacts-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | `string` |  |  |
| `type` | `string` | да |  |
| `metadata` | `object` |  |  |
| `content` | `string` |  | Content (text): an artifact with stored content, as after an upload |
| `mediaType` | `string` |  | Content type (text/markdown, application/json, …) |

### `taskTypeStep` { #schema-tasktypestep }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `approve` | [объект](#schema-tasktypestep-approve) |  |  |
| `verify` | [объект](#schema-tasktypestep-verify) |  | Outcome of the type's acceptance criterion |
| `complete` | [объект](#schema-tasktypestep-complete) |  |  |
| `expect` | [объект](#schema-tasktypestep-expect) |  |  |

Ровно одно из: `approve`, `verify`, `complete`, `expect`.

### `taskTypeStep.approve` { #schema-tasktypestep-approve }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `gate` | `string` |  | По умолчанию `default`. |
| `decision` | `approved` \| `rejected` | да |  |
| `by` | `string` |  |  |
| `comment` | `string` |  |  |
| `expectRefused` | `string` |  | Core rejection code for the decider, e.g. not_eligible: the decider is not a holder of the gate role |

### `taskTypeStep.verify` { #schema-tasktypestep-verify }

Outcome of the type's acceptance criterion

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `check` | `string` | да |  |
| `result` | `passed` \| `failed` | да |  |
| `output` | `object` |  |  |

### `taskTypeStep.complete` { #schema-tasktypestep-complete }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `output` | `object` |  | Completion output (completionSchema) |

### `taskTypeStep.expect` { #schema-tasktypestep-expect }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `ensureWork` | array of [`workExpectation`](#schema-workexpectation) |  |  |
| `invokeSkill` | array of [`skillExpectation`](#schema-skillexpectation) |  |  |
| `status` | [объект](#schema-tasktypestep-expect-status) |  |  |
| `comments` | array of `string` |  | Substrings of comments left by outcomes |
| `noSideEffects` | = `true` |  |  |

### `taskTypeStep.expect.status` { #schema-tasktypestep-expect-status }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | `string` |  |  |
| `category` | `backlog` \| `active` \| `blocked` \| `terminal_success` \| `terminal_cancelled` |  |  |
<!-- /generated:schema-test -->

## Фиксация источников (`packages.lock`) { #lock }

Файл пишет `package-sdk lock`; руками его не правят.

<!-- generated:schema-lock -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/lock.schema.json`.

### `lock` { #schema-lock }

Файл packages.lock рядом с файлом установки. Пишет package-sdk lock; для каждого пакета — источник, коммит и хэш содержимого. План строится по lock: для источника git без записи — lock_required, при расхождении хэша — отказ.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `format` | = `package-sdk.lock/v1` | да |  |
| `installation` | `string` |  | Ключ установки, для которой снята фиксация |
| `packages` | array of [объект](#schema-lock-packages-item) | да |  |

### `lock.packages[]` { #schema-lock-packages-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | `string` | да |  |
| `version` | `string` | да |  |
| `source` | [объект `{path}`](#schema-lock-packages-item-source-1) или [объект `{git, ref, path}`](#schema-lock-packages-item-source-2) | да | Откуда пакет: {path} — каталог относительно файла установки; {git, ref, path?} — тег git и подкаталог пакета в репозитории (то же имя path, что в установке) |
| `commit` | `string` |  | Коммит источника git |
| `contentHash` | `string` | да | sha256 канонического набора файлов пакета: пути по порядку и их байты, без .layout/ (та же функция, что installHash записи связей) |

### `lock.packages[].source (1)` { #schema-lock-packages-item-source-1 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `path` | `string` | да |  |

### `lock.packages[].source (2)` { #schema-lock-packages-item-source-2 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `git` | `string` | да |  |
| `ref` | `string` | да |  |
| `path` | `string` |  |  |
<!-- /generated:schema-lock -->

## План установки (`plan --out`) { #plan }

Документ пишет `package-sdk plan --out`; `package-sdk apply --plan` применяет его только без правок.

<!-- generated:schema-plan -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/plan.schema.json`.

### `plan` { #schema-plan }

Один документ изменений всех видов установки. Пишет package-sdk plan --out; применяется только package-sdk apply --plan без правок: planHash — хэш документа без самого поля, правленый файл отвергается. Значения переменных в план не пишутся, только их хэш.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `format` | = `package-sdk.plan/v1` | да |  |
| `server` | `string` | да | Стенд: https, http — только localhost |
| `engines` | map → `string` |  | Версии компонентов стенда на момент плана (из openapi.json) |
| `createdAt` | `string` (date-time) | да |  |
| `installation` | `string` |  | Ключ установки (Installation.key) |
| `install` | `string` |  | Файл установки относительно файла плана: apply --plan собирает по нему пакеты заново и сверяет lockHash и variablesHash |
| `lockHash` | [`plan/hash`](#schema-plan-hash) |  |  |
| `variablesHash` | [`plan/hash`](#schema-plan-hash) |  |  |
| `overwriteConsole` | `boolean` |  | plan --overwrite-console: перезаписать поля объектов ядра, которые человек правил в консоли после прошлого применения; без флага ядро их сохраняет. package-sdk plan пишет поле всегда, false по умолчанию; план прежнего формата без поля применяется как false. Входит в planHash; с ним же строится и применяется план ядра |
| `sections` | array of [`plan/section`](#schema-plan-section) | да |  |
| `planHash` | [`plan/hash`](#schema-plan-hash) | да |  |

### `plan/hash` { #schema-plan-hash }

Значение: `string`.

### `plan/section` { #schema-plan-section }

Значение: [объект `{kind, changes}`](#schema-plan-section-1) или [объект `{kind, package, planHash, plan, workspaceId, replayLimit}`](#schema-plan-section-2) или [объект `{kind, changes}`](#schema-plan-section-3) или [объект `{kind, register, enable}`](#schema-plan-section-4) или [объект `{kind, items}`](#schema-plan-section-5).

### `plan/section (1)` { #schema-plan-section-1 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | = `catalog` | да |  |
| `changes` | array of [`plan/change`](#schema-plan-change) | да |  |

### `plan/section (2)` { #schema-plan-section-2 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | = `core` | да |  |
| `package` | `string` | да |  |
| `planHash` | [`plan/hash`](#schema-plan-hash) | да |  |
| `plan` | `object` | да | Ответ /packages:plan ядра как есть |
| `workspaceId` | `string` |  | workspaceId запроса плана — с ним же идёт /packages:apply |
| `replayLimit` | `integer` |  | replayLimit запроса плана — с ним план ядра строится заново перед применением |

### `plan/section (3)` { #schema-plan-section-3 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | = `notification-rules` | да |  |
| `changes` | array of [`plan/change`](#schema-plan-change) | да |  |

### `plan/section (4)` { #schema-plan-section-4 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | = `knowledge` | да |  |
| `register` | array of [`plan/change`](#schema-plan-change) |  |  |
| `enable` | array of [объект](#schema-plan-section-4-enable-item) |  |  |

### `plan/section (4).enable[]` { #schema-plan-section-4-enable-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `workspace` | `string` | да |  |
| `packs` | array of `string` | да |  |
| `current` | array of `string` |  |  |

### `plan/section (5)` { #schema-plan-section-5 }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | = `retire` | да |  |
| `items` | array of [`plan/change`](#schema-plan-change) | да |  |

### `plan/change` { #schema-plan-change }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `package` | `string` |  |  |
| `kind` | `string` | да |  |
| `key` | `string` | да |  |
| `operation` | `create` \| `version` \| `patch` \| `deprecate` \| `enable` \| `disable` \| `register` \| `retire` \| `unchanged` | да |  |
| `fields` | array of `string` |  | Поля, которые меняются |
| `expected` | любое |  | Что установщик ожидает увидеть на стенде перед записью (для plan_stale) |
<!-- /generated:schema-plan -->

## Уточнение шаблона загрузки (`templates/<вид>.yaml`) { #knowledge-template }

<!-- generated:schema-knowledge-template -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/knowledge-template.schema.json`.

### `knowledge-template` { #schema-knowledge-template }

Необязательные данные пакета templates/&lt;вид&gt;.yaml. Шаблон строится генератором из JSON Schema вида; уточнение меняет только подачу: заголовки, порядок, подсказки, примеры и дополнительные запрещённые колонки. Колонок, которых нет в схеме вида, уточнение не добавляет.

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `pack` | `string` | да | Пакет онтологии и версия вида, например company@1 |
| `kind` | `string` | да |  |
| `title` | `string` |  | Название листа и файла шаблона |
| `instructions` | `string` |  | Текст листа «Инструкция» перед сгенерированным описанием колонок |
| `columns` | array of [объект](#schema-knowledge-template-columns-item) |  | Порядок колонок; не перечисленные идут после в порядке схемы |
| `examples` | array of `object` |  | Строки-примеры листа шаблона: field → значение |
| `forbiddenColumns` | array of `string` |  | Запрещённые заголовки сверх общего списка персональных данных (фио, фамилия, паспорт, снилс, дата рождения, адрес, телефон, e-mail) |

### `knowledge-template.columns[]` { #schema-knowledge-template-columns-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `field` | `string` | да | key — естественный ключ, title — имя, attributes.&lt;путь&gt; — атрибут, links.&lt;связь&gt; — ключи связанных сущностей |
| `header` | `string` |  |  |
| `hint` | `string` |  |  |
| `example` | `string` \| `number` \| `boolean` |  |  |
| `separator` | `string` |  | Разделитель списка в ячейке (коды, ключи связей); по умолчанию «;» |
<!-- /generated:schema-knowledge-template -->

## Экраны пакета (`kind: View`, `kind: Component`) { #view }

Экраны пакета лежат в `views/*.yaml` и `components/*.yaml`. Обёртка у них та
же, что у остальных объектов, а `spec` вида `View` описывает `viewSpec`, вида
`Component` — `componentSpec`; подписи экранов — ключи словарей
`i18n/<locale>.yaml`. Схема — копия схемы экранов ядра, её проверяют
`package-sdk check` и `plan`.

<!-- generated:schema-view -->
_Раздел генерируется из кода — не правьте его руками._

Источник: `sdk/package-sdk/schema/v1/view.schema.json`.

### `view` { #schema-view }

Screens of a package: spec of the kinds View and Component

Собственной формы у корня нет — только определения; верхнего уровня: [`view/viewSpec`](#schema-view-viewspec), [`view/componentSpec`](#schema-view-componentspec).

### `view/viewSpec` { #schema-view-viewspec }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `blocks` | = `1` |  | Version of the set of blocks the layout is written in |
| `title` | [`view/messageKey`](#schema-view-messagekey) | да |  |
| `description` | [`view/messageKey`](#schema-view-messagekey) |  |  |
| `nav` | [объект](#schema-view-viewspec-nav) |  |  |
| `audience` | [объект](#schema-view-viewspec-audience) |  |  |
| `source` | [`view/source`](#schema-view-source) | да |  |
| `params` | [`view/params`](#schema-view-params) |  |  |
| `layout` | [`view/layout`](#schema-view-layout) | да |  |

### `view/viewSpec.nav` { #schema-view-viewspec-nav }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `group` | `work` \| `knowledge` \| `packages` |  | A group of the console menu (a closed list, not a key of the dictionaries); none: packages |
| `icon` | `string` |  |  |
| `order` | `integer` |  |  |

### `view/viewSpec.audience` { #schema-view-viewspec-audience }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `roles` | array of [`view/slug`](#schema-view-slug) | да | Roles of the organization (slugs): a holder of one of them sees the view |

### `view/messageKey` { #schema-view-messagekey }

A key of the package dictionaries

Значение: `string`.

### `view/slug` { #schema-view-slug }

Значение: `string`.

### `view/source` { #schema-view-source }

Exactly one of {process, filter?}, {process, instance: param.&lt;name&gt;}, {tasks: {type}}, {knowledge: {kinds}}

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `process` | [`view/key`](#schema-view-key) |  |  |
| `filter` | [`view/expression`](#schema-view-expression) |  |  |
| `instance` | `string` |  |  |
| `tasks` | [объект](#schema-view-source-tasks) |  |  |
| `knowledge` | [объект](#schema-view-source-knowledge) |  |  |

### `view/source.tasks` { #schema-view-source-tasks }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | [`view/key`](#schema-view-key) | да |  |

### `view/source.knowledge` { #schema-view-source-knowledge }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kinds` | array of [`view/kind`](#schema-view-kind) | да |  |

### `view/key` { #schema-view-key }

Значение: `string`.

### `view/expression` { #schema-view-expression }

Значение: `string`.

### `view/kind` { #schema-view-kind }

Значение: `string`.

### `view/params` { #schema-view-params }

Значение: map → [`view/param`](#schema-view-param).

### `view/name` { #schema-view-name }

Значение: `string`.

### `view/param` { #schema-view-param }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `type` | `string` \| `integer` \| `number` \| `boolean` \| `date` \| `datetime` \| `uuid` | да |  |
| `required` | `boolean` |  |  |

### `view/layout` { #schema-view-layout }

Значение: array of [`view/block`](#schema-view-block).

### `view/block` { #schema-view-block }

A block of the closed set of version 1, named by the key block

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `block` | `table` \| `board` \| `list` \| `header` \| `fields` \| `timeline` \| `artifacts` \| `related` \| `metrics` \| `chart` \| `steps` \| `invoke` \| `component` | да |  |

Условия:

| Условие | Следствие |
|---|---|
| `block` ∈ `table`, `list` | обязательно `columns`; `title`: [`view/messageKey`](#schema-view-messagekey); `columns`: [`view/columns`](#schema-view-columns); `open`: [`view/open`](#schema-view-open); `filters`: [`view/paths`](#schema-view-paths); `sort`: [`view/sort`](#schema-view-sort); `pageSize`: `integer` |
| `block` = `board` | обязательно `columns`, `card`; `title`: [`view/messageKey`](#schema-view-messagekey); `columns`: = `stages`; `card`: [`view/card`](#schema-view-card); `open`: [`view/open`](#schema-view-open); `filters`: [`view/paths`](#schema-view-paths) |
| `block` = `header` | обязательно `title`; `title`: [`view/path`](#schema-view-path); `status`: [`view/path`](#schema-view-path); `actions`: `steps` |
| `block` = `fields` | обязательно `items`; `title`: [`view/messageKey`](#schema-view-messagekey); `section`: [`view/messageKey`](#schema-view-messagekey); `items`: [`view/columns`](#schema-view-columns) |
| `block` ∈ `timeline`, `steps` | `title`: [`view/messageKey`](#schema-view-messagekey) |
| `block` = `artifacts` | `title`: [`view/messageKey`](#schema-view-messagekey); `types`: array of [`view/key`](#schema-view-key) |
| `block` = `related` | обязательно `knowledge`; `title`: [`view/messageKey`](#schema-view-messagekey); `knowledge`: [объект](#schema-view-block-knowledge); `include`: [`view/include`](#schema-view-include) |
| `block` = `metrics` | обязательно `items`; `title`: [`view/messageKey`](#schema-view-messagekey); `items`: array of [объект](#schema-view-block-items-item) |
| `block` = `chart` | обязательно `chart`, `groupBy`, `value`; `title`: [`view/messageKey`](#schema-view-messagekey); `chart`: `bar` \| `line` \| `donut`; `groupBy`: [`view/path`](#schema-view-path); `value`: [`view/expression`](#schema-view-expression); `label`: [`view/messageKey`](#schema-view-messagekey); `format`: [`view/format`](#schema-view-format) |
| `block` = `invoke` | обязательно `label`, `skill`; `title`: [`view/messageKey`](#schema-view-messagekey); `label`: [`view/messageKey`](#schema-view-messagekey); `skill`: `string`; `input`: [`view/arguments`](#schema-view-arguments) |
| `block` = `component` | обязательно `component`; `component`: [`view/key`](#schema-view-key); `with`: [`view/arguments`](#schema-view-arguments) |

### `view/block.knowledge` { #schema-view-block-knowledge }

The record of knowledge the block starts from: its kind and a CEL expression of its key

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `kind` | [`view/kind`](#schema-view-kind) | да |  |
| `key` | [`view/expression`](#schema-view-expression) | да |  |

### `view/block.items[]` { #schema-view-block-items-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | [`view/columnKey`](#schema-view-columnkey) |  |  |
| `title` | [`view/messageKey`](#schema-view-messagekey) | да |  |
| `value` | [`view/expression`](#schema-view-expression) | да |  |
| `format` | [`view/format`](#schema-view-format) |  |  |

### `view/columns` { #schema-view-columns }

Значение: array of [`view/column`](#schema-view-column).

### `view/column` { #schema-view-column }

What a cell shows: a path of the source (field) or a CEL expression (value), exactly one; label: none — the key &lt;package&gt;.fields.&lt;path&gt; of the dictionaries; key: none — the path

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `key` | [`view/columnKey`](#schema-view-columnkey) |  |  |
| `label` | [`view/messageKey`](#schema-view-messagekey) |  |  |
| `field` | [`view/path`](#schema-view-path) |  |  |
| `value` | [`view/expression`](#schema-view-expression) |  |  |
| `format` | [`view/format`](#schema-view-format) |  |  |

### `view/columnKey` { #schema-view-columnkey }

The key the values of a column come by in the data of a view

Значение: `string`.

### `view/path` { #schema-view-path }

Значение: `string`.

### `view/format` { #schema-view-format }

Значение: `text` \| `number` \| `money` \| `percent` \| `date` \| `datetime` \| `due` \| `duration` \| `principal` \| `status` \| `link`.

### `view/open` { #schema-view-open }

A view of the same package or of a package it requires: id — CEL of the id of the record it opens, params — CEL of its params

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `view` | [`view/key`](#schema-view-key) | да |  |
| `id` | [`view/expression`](#schema-view-expression) |  |  |
| `params` | [`view/arguments`](#schema-view-arguments) |  |  |

### `view/arguments` { #schema-view-arguments }

Значение: map → [`view/expression`](#schema-view-expression).

### `view/paths` { #schema-view-paths }

Значение: array of [`view/path`](#schema-view-path).

### `view/sort` { #schema-view-sort }

Значение: array of [объект](#schema-view-sort-item).

### `view/sort[]` { #schema-view-sort-item }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `field` | [`view/path`](#schema-view-path) | да |  |
| `dir` | `asc` \| `desc` |  |  |

### `view/card` { #schema-view-card }

A card of a board: paths of the source for its title, subtitle and badge, and its fields

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `title` | [`view/path`](#schema-view-path) | да |  |
| `subtitle` | [`view/path`](#schema-view-path) |  |  |
| `fields` | [`view/columns`](#schema-view-columns) |  |  |
| `badge` | [`view/path`](#schema-view-path) |  |  |

### `view/include` { #schema-view-include }

The links of the record shown: the include of POST /knowledge/entities:query

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `relations` | = `*` или array of `string` | да | Names of the relations shown, or * for every relation the packages of the namespace declare |
| `direction` | `out` \| `in` \| `both` |  |  |
| `limit` | `integer` |  |  |

### `view/componentSpec` { #schema-view-componentspec }

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `description` | [`view/messageKey`](#schema-view-messagekey) |  |  |
| `params` | [`view/componentParams`](#schema-view-componentparams) |  |  |
| `layout` | [`view/layout`](#schema-view-layout) | да |  |

### `view/componentParams` { #schema-view-componentparams }

Значение: map → [`view/schemaParam`](#schema-view-schemaparam) или [`view/param`](#schema-view-param) — по условию.

### `view/schemaParam` { #schema-view-schemaparam }

A param typed by a JSON Schema

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `schema` | `object` | да | JSON Schema of the param: inline or {$ref: &lt;file&gt;#&lt;pointer&gt;} of a schema of the package; CEL reads param.&lt;name&gt; by it |
| `required` | `boolean` |  |  |
<!-- /generated:schema-view -->

## См. также

- [Команды package-sdk](package-sdk-cli.md)
- [Анатомия пакета](../packages/anatomy.md)
- [Процессы](../processes/index.md)
- [Выражения](../processes/expressions.md)
- [Тесты пакета](../packages/testing.md)
- [Пакеты каталога](../control-plane/catalog-packages.md)
