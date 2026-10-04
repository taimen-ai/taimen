
# Package schema

Field reference for all package files: the object wrapper, each catalog kind,
package tests, source pinning in `packages.lock`, the installation plan, and screens. The tables
are built from the JSON Schema `sdk/package-sdk/schema/v1` and follow it field for field.
This page is for package authors; [Package
anatomy](../packages/anatomy.md), [Processes](../processes/index.md),
[Expressions](../processes/expressions.md), and [Package tests](../packages/testing.md) explain how to use it.

!!! note "The schema is the first stage of checking"
    The schema checks the shape of the description. The second stage — references
    between objects, expression types, unknown data fields, step reachability, gaps
    in decision tables — is performed by `package-sdk check` and the core validators (see
    [Package tests](../packages/testing.md)).

To connect the schema to an editor, add a line at the top of the object file:

```yaml
# yaml-language-server: $schema=<path to schema/v1/object.schema.json>
```

How to read the tables: "Type" is a JSON type or a reference to a definition below;
`array of` is an array, `map →` is an object with arbitrary keys; "Conditions" lists
fields that are required or change shape depending on the value of another field.

## Object wrapper { #object }

Every object file of a package — `package.yaml`, the catalog kind files, and the installation — is one wrapper `apiVersion` + `kind` + `key` + `spec`. The key type and the shape of `spec` depend on the kind (the "Conditions" table).

<!-- generated:schema-object -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/object.schema.json`.

### `object` { #schema-object }

One wrapper for the manifest and all catalog kinds: apiVersion + kind + key + spec. spec is the control-plane API request body in camelCase without the identity field. The schema checks the shape; the core performs the final check (and so does package-sdk check with its validators).

| Field | Type | Required | Description |
|---|---|---|---|
| `apiVersion` | = `taimen.ai/v1` | yes |  |
| `kind` | `Package` \| `Installation` \| `ArtifactType` \| `TaskType` \| `ProjectTemplate` \| `WorkspaceType` \| `Role` \| `Capability` \| `ConnectionType` \| `Skill` \| `WorkRule` \| `Agent` \| `NotificationRule` \| `Process` \| `Calendar` \| `KnowledgePack` | yes |  |
| `key` | `string` | yes |  |
| `spec` | `object` | yes |  |

Conditions:

| Condition | Consequence |
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

## Package manifest (`kind: Package`) { #package }

<!-- generated:schema-package -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/object.schema.json`.

### `packageSpec` { #schema-packagespec }

| Field | Type | Required | Description |
|---|---|---|---|
| `version` | `string` | yes | Package SemVer |
| `displayName` | [`displayName`](#schema-displayname) | yes |  |
| `description` | `string` |  |  |
| `requires` | array of [`typeKey`](#schema-typekey) or [object `{package, version}`](#schema-packagespec-requires-item-2) |  | Packages whose objects this package references: a key (any version) or {package, version} with a SemVer range |
| `engines` | map → [`semverRange`](#schema-semverrange) |  | Version ranges of the components the package is checked against, for example {control-plane: "&gt;=0.9,&lt;0.11"}; check and plan reject an incompatible version before writing |
| `variables` | map → [`packageVariable`](#schema-packagevariable) |  | Declaration of each ${NAME} of the package. A used variable must be declared, and a declared one must be used. A package holds no secrets: a variable has no secret field |
| `knowledge` | array of `string` |  | Ontologies (name@major) that the package's processes and rules rely on; check compares them with the recall/remember/memory of the processes |
| `license` | `string` |  | Package license (SPDX identifier) |
| `authors` | array of `string` |  |  |
| `homepage` | `string` |  |  |
| `renames` | array of [object](#schema-packagespec-renames-item) |  | Explicit object renames (like moved in Terraform): the plan moves the object instead of deleting and creating it |
| `settings` | [`packageSettings`](#schema-packagesettings) |  |  |

### `packageSpec.requires[] (2)` { #schema-packagespec-requires-item-2 }

| Field | Type | Required | Description |
|---|---|---|---|
| `package` | [`typeKey`](#schema-typekey) | yes |  |
| `version` | [`semverRange`](#schema-semverrange) |  |  |

### `packageSpec.renames[]` { #schema-packagespec-renames-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | `string` | yes |  |
| `from` | `string` | yes |  |
| `to` | `string` | yes |  |

### `semverRange` { #schema-semverrange }

Version range: comma-separated conditions, all of which must hold (&gt;=0.9,&lt;0.11); operators &gt;=, &gt;, &lt;=, &lt;, =, ^, ~; without an operator, a version or a prefix (1.2 = 1.2.x); * means any

Value: `string`.

### `packageVariable` { #schema-packagevariable }

| Field | Type | Required | Description |
|---|---|---|---|
| `description` | `string` | yes |  |
| `kind` | `url` \| `workspace` \| `project` \| `principal` \| `role` \| `string` \| `integer` | yes | Value kind: url is an absolute URL; workspace\|project\|principal\|role is a UUID that exists on the deployment (plan checks it); integer is an integer; string is any string |
| `required` | `boolean` |  | Default: `true`. |
| `default` | `string` |  | Value used if the installation does not set its own |
| `example` | `string` |  |  |

### `packageSettings` { #schema-packagesettings }

Package settings: values an organization administrator changes in the live system without a new package version or an installation plan. Values live in the core; processes, work rules and views read them as settings.&lt;field&gt;

| Field | Type | Required | Description |
|---|---|---|---|
| `schema` | [`settingsSchema`](#schema-settingsschema) | yes |  |
| `uischema` | [`settingsUiElement`](#schema-settingsuielement) |  | Form layout: the closed subset of JSON Forms the console renders — VerticalLayout, HorizontalLayout, Group, Control and Label with SHOW/HIDE/ENABLE/DISABLE rules; anything else, options of a Control included, is rejected. Labels are keys of the package dictionaries, not texts: label of a Group and of a Control, text of a Label. Unlike the uischema of process step forms, which is open and whose label is a text. Without it the console lays the fields out in schema order |

### `settingsSchema` { #schema-settingsschema }

Schema of the settings: a subset of JSON Schema, as for process data. The root is an object; objects nest at most 3 levels deep; at most 100 properties per object. Field labels are not in the schema: they are keys &lt;package&gt;.settings.&lt;path&gt; of the package dictionaries

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | = `object` | yes |  |
| `properties` | map → [`settingsField1`](#schema-settingsfield1) | yes |  |
| `required` | [`settingsRequired`](#schema-settingsrequired) |  |  |
| `additionalProperties` | = `false` |  | Implied on every object: a value with an undeclared member is refused |

### `settingsFieldName` { #schema-settingsfieldname }

Field name: camelCase, as referenced in expressions (settings.&lt;field&gt;)

Value: `string`.

### `settingsField1` { #schema-settingsfield1 }

Includes [`settingsKeywords`](#schema-settingskeywords).

| Field | Type | Required | Description |
|---|---|---|---|
| `properties` | any |  |  |
| `items` | [`settingsField2`](#schema-settingsfield2) |  |  |

### `settingsKeywords` { #schema-settingskeywords }

One settings field: only the keywords listed here; secret markers (writeOnly, format: password) and keywords outside the subset are rejected

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `string` \| `integer` \| `number` \| `boolean` \| `array` \| `object` | yes |  |
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
| `default` | any |  | Value in effect until an administrator saves another; every optional field must have one (package-sdk check) |
| `x-ref` | `role` \| `principal` \| `workspace` \| `calendar` \| `taskType` |  | The string references a platform object of this kind in the organization: the id of a role, principal or workspace, the key of a task type or calendar; the core rejects a value that references a missing object |

Conditions:

| Condition | Consequence |
|---|---|
| `type` = `object` | required `properties` |
| otherwise | `properties`: not allowed; `required`: not allowed; `additionalProperties`: not allowed |
| `type` = `array` | required `items` |
| otherwise | `items`: not allowed; `minItems`: not allowed; `maxItems`: not allowed |
| otherwise | `minLength`: not allowed; `maxLength`: not allowed; `pattern`: not allowed; `format`: not allowed; `x-ref`: not allowed |
| otherwise | `minimum`: not allowed; `maximum`: not allowed |

### `settingsRequired` { #schema-settingsrequired }

Fields that must always have a value

Value: array of [`settingsFieldName`](#schema-settingsfieldname).

### `settingsScalar` { #schema-settingsscalar }

Value: `string` \| `integer` \| `number` \| `boolean`.

### `settingsField2` { #schema-settingsfield2 }

Includes [`settingsKeywords`](#schema-settingskeywords).

| Field | Type | Required | Description |
|---|---|---|---|
| `properties` | any |  |  |
| `items` | [`settingsField3`](#schema-settingsfield3) |  |  |

### `settingsField3` { #schema-settingsfield3 }

The deepest level: a scalar field or an array of scalars, no nested objects

Includes [`settingsKeywords`](#schema-settingskeywords).

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `string` \| `integer` \| `number` \| `boolean` \| `array` |  |  |
| `items` | [`settingsKeywords`](#schema-settingskeywords) |  |  |

### `settingsUiElement` { #schema-settingsuielement }

Element of the settings form: VerticalLayout, HorizontalLayout, Group, Control or Label. Other JSON Forms elements (Categorization, ListWithDetail, custom renderers) are not rendered by the console and are rejected

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `VerticalLayout` \| `HorizontalLayout` \| `Group` \| `Control` \| `Label` | yes |  |

Conditions:

| Condition | Consequence |
|---|---|
| `type` ∈ `VerticalLayout`, `HorizontalLayout` | required `elements`; `elements`: [`settingsUiElements`](#schema-settingsuielements); `rule`: [`settingsUiRule`](#schema-settingsuirule) |
| `type` = `Group` | required `label`, `elements`; `label`: [`settingsLabelKey`](#schema-settingslabelkey); `elements`: [`settingsUiElements`](#schema-settingsuielements); `rule`: [`settingsUiRule`](#schema-settingsuirule) |
| `type` = `Control` | required `scope`; `scope`: [`settingsScope`](#schema-settingsscope); `label`: [`settingsLabelKey`](#schema-settingslabelkey); `rule`: [`settingsUiRule`](#schema-settingsuirule) |
| `type` = `Label` | required `text`; `text`: [`settingsLabelKey`](#schema-settingslabelkey); `rule`: [`settingsUiRule`](#schema-settingsuirule) |

### `settingsUiElements` { #schema-settingsuielements }

Value: array of [`settingsUiElement`](#schema-settingsuielement).

### `settingsUiRule` { #schema-settingsuirule }

JSON Forms rule: the effect applies while the value at condition.scope matches condition.schema

| Field | Type | Required | Description |
|---|---|---|---|
| `effect` | `SHOW` \| `HIDE` \| `ENABLE` \| `DISABLE` | yes |  |
| `condition` | [object](#schema-settingsuirule-condition) | yes |  |

### `settingsUiRule.condition` { #schema-settingsuirule-condition }

| Field | Type | Required | Description |
|---|---|---|---|
| `scope` | [`settingsScope`](#schema-settingsscope) | yes |  |
| `schema` | [object](#schema-settingsuirule-condition-schema) | yes | Condition on the value: the keywords of a settings field without x-ref and default, and const |
| `failWhenUndefined` | `boolean` |  |  |

### `settingsUiRule.condition.schema` { #schema-settingsuirule-condition-schema }

Condition on the value: the keywords of a settings field without x-ref and default, and const

| Field | Type | Required | Description |
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

Value: `string`.

### `settingsLabelKey` { #schema-settingslabelkey }

Key of the package dictionaries (&lt;package&gt;.settings.&lt;name&gt;), not the text: the console shows its string in the user's language

Value: `string`.
<!-- /generated:schema-package -->

## Installation (`kind: Installation`) { #installation }

<!-- generated:schema-installation -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/object.schema.json`.

### `installationSpec` { #schema-installationspec }

| Field | Type | Required | Description |
|---|---|---|---|
| `packages` | array of [`packageSource`](#schema-packagesource) | yes | Packages of the installation: a key (installation catalog), {key, path}, or {key, git, ref}; requires are pulled in automatically. Empty means only the core system type task |
| `packagesDir` | `string` |  | Directory of the installation's packages relative to the installation file; by default packages/ next to it |
| `knowledge` | array of [object](#schema-installationspec-knowledge-item) |  | Enabling ontologies for workspaces — this is topology, so it belongs to the installation; the set replaces the previous one entirely |
| `retire` | [object](#schema-installationspec-retire) |  | Keys the environment retires (all active versions → deprecated) |

### `installationSpec.knowledge[]` { #schema-installationspec-knowledge-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `workspace` | `string` | yes | An installation ${VARIABLE} or a UUID |
| `packs` | array of `string` | yes |  |
| `strict` | `boolean` |  | Strict memory mode: records outside the enabled kinds are rejected instead of being accepted as is. Default: `false`. |

### `installationSpec.retire` { #schema-installationspec-retire }

Keys the environment retires (all active versions → deprecated)

| Field | Type | Required | Description |
|---|---|---|---|
| `TaskType` | array of [`typeKey`](#schema-typekey) |  |  |
| `ProjectTemplate` | array of [`typeKey`](#schema-typekey) |  |  |
| `Agent` | array of [`slug`](#schema-slug) |  | The agent is retired: the executor is stopped, the credential is revoked, the history is kept |
| `NotificationRule` | array of [`ruleKey`](#schema-rulekey) |  | The notification rule is retired in the notification service (:retire); sent notifications remain |
| `WorkRule` | array of [`ruleKey`](#schema-rulekey) |  | The work rule is archived; the work it created runs to completion |
| `Process` | array of [`typeKey`](#schema-typekey) |  | The process is retired through the core :retire route: new instances do not start, running ones run to completion |
| `Calendar` | array of [`typeKey`](#schema-typekey) |  | A calendar is retired only if no active process references it (calendar_in_use) |
| `ConnectionType` | array of [`connectionKey`](#schema-connectionkey) |  | Every active version of the connection type becomes deprecated: no new connections of the type, existing ones keep working |

### `packageSource` { #schema-packagesource }

Value: [`typeKey`](#schema-typekey) or [object `{key, path}`](#schema-packagesource-2) or [object `{key, git, ref, path}`](#schema-packagesource-3).

### `packageSource (2)` { #schema-packagesource-2 }

| Field | Type | Required | Description |
|---|---|---|---|
| `key` | [`typeKey`](#schema-typekey) | yes |  |
| `path` | `string` | yes | Path to the package directory relative to the installation file |

### `packageSource (3)` { #schema-packagesource-3 }

| Field | Type | Required | Description |
|---|---|---|---|
| `key` | [`typeKey`](#schema-typekey) | yes |  |
| `git` | `string` | yes | https://host/path without credentials in the address, or git@host:path; access goes through the git credential helper |
| `ref` | `string` | yes | Package release tag (refs/tags/&lt;ref&gt;; branches and commits are not accepted); packages.lock keeps the result reproducible |
| `path` | `string` |  | Package subdirectory in the repository if it is not at the root: a relative path without . and .. |
<!-- /generated:schema-installation -->

## Artifact type (`kind: ArtifactType`) { #artifact-type }

<!-- generated:schema-artifact-type -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/object.schema.json`.

### `artifactTypeSpec` { #schema-artifacttypespec }

Artifact type: a versioned immutable catalog object, like TaskType.

| Field | Type | Required | Description |
|---|---|---|---|
| `displayName` | [`displayName`](#schema-displayname) | yes |  |
| `description` | `string` |  |  |
| `metadataSchema` | [`jsonSchema`](#schema-jsonschema) |  | Schema of the metadata of artifacts of this type (≤ 16 KiB) |
| `mediaTypes` | array of [`mediaType`](#schema-mediatype) |  | Allowed media types of the content; any by default |
| `maxBytes` | `integer` |  | Content size limit; not more than the installation-wide limit (CP_ARTIFACT_MAX_BYTES) |
<!-- /generated:schema-artifact-type -->

## Task type (`kind: TaskType`) { #task-type }

<!-- generated:schema-task-type -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/object.schema.json`.

### `taskTypeSpec` { #schema-tasktypespec }

| Field | Type | Required | Description |
|---|---|---|---|
| `displayName` | [`displayName`](#schema-displayname) | yes |  |
| `description` | `string` |  |  |
| `fieldSchema` | [`jsonSchema`](#schema-jsonschema) |  | Schema of the task's customFields |
| `lifecycleSchema` | [`workItemLifecycle`](#schema-workitemlifecycle) | yes |  |
| `execution` | [`execution`](#schema-execution) |  |  |
| `approvalSchema` | [`approvalSchema`](#schema-approvalschema) |  |  |
| `completionSchema` | `object` |  | Work after the task completes: {onComplete: {when?, actions}} — ensureWork (customFields, relation, requestApproval) and comment. The core checks the grammar. |
| `instructions` | `string` |  | Instructions for the executor: Markdown ≤ 16 KiB, the task type layer after the platform contract and the project. The core checks the size in bytes and the absence of secrets. |
| `artifactSchema` | [`artifactSchema`](#schema-artifactschema) |  |  |
| `executorRoles` | array of [`slug`](#schema-slug) |  | Keys of the roles a person needs to take work of this type: a Role of the package, its requires, or the tenant. Absent or empty means people are not restricted. The core rejects a role the tenant does not have (422 unknown_role). |
| `acceptance` | array of [`acceptanceCriterion`](#schema-acceptancecriterion) |  | Default acceptance criteria for all tasks of the type: they run after the required outputs and before the task's own criteria; a task cannot replace a type criterion — its criterion with the same key is rejected (422). A deterministic criterion with an external_write skill runs only after a human criterion of the same attempt. |
| `contextSchema` | [object](#schema-tasktypespec-contextschema) |  | Task context profile: anchors, traverse, asOf, budgetTokens. The core checks the grammar. |

### `taskTypeSpec.contextSchema` { #schema-tasktypespec-contextschema }

Task context profile: anchors, traverse, asOf, budgetTokens. The core checks the grammar.

| Field | Type | Required | Description |
|---|---|---|---|
| `anchors` | array of any |  |  |
| `traverse` | array of any |  |  |
| `asOf` | `taskCreated` \| `now` \| `origin` |  |  |
| `budgetTokens` | `integer` |  |  |

### `workItemLifecycle` { #schema-workitemlifecycle }

Includes [`lifecycle`](#schema-lifecycle).

| Field | Type | Required | Description |
|---|---|---|---|
| `statuses` | array of [object](#schema-workitemlifecycle-statuses-item) |  |  |
| `claimStatus` | [`statusKey`](#schema-statuskey) |  | Status on claim; not terminal |
| `releaseStatus` | [`statusKey`](#schema-statuskey) |  | Status on release; not terminal |
| `completionStatus` | [`statusKey`](#schema-statuskey) |  | Status of successful completion; category terminal_success |

### `workItemLifecycle.statuses[]` { #schema-workitemlifecycle-statuses-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `category` | [`workItemCategory`](#schema-workitemcategory) |  |  |

### `workItemCategory` { #schema-workitemcategory }

Value: `backlog` \| `active` \| `blocked` \| `terminal_success` \| `terminal_cancelled`.

### `execution` { #schema-execution }

A task of this type is executed by one skill invocation

| Field | Type | Required | Description |
|---|---|---|---|
| `skill` | `string` | yes |  |
| `version` | `string` | yes |  |
| `inputs` | `string` or map → `string` |  | A $.… path to the whole input or an object {inputName: path}; by default $.customFields |

### `approvalSchema` { #schema-approvalschema }

| Field | Type | Required | Description |
|---|---|---|---|
| `gates` | map → [object](#schema-approvalschema-gates-value) |  | Only the default gate is supported for now |

### `approvalSchema.gates.*` { #schema-approvalschema-gates-value }

| Field | Type | Required | Description |
|---|---|---|---|
| `outcomes` | [object](#schema-approvalschema-gates-value-outcomes) | yes |  |

### `approvalSchema.gates.*.outcomes` { #schema-approvalschema-gates-value-outcomes }

| Field | Type | Required | Description |
|---|---|---|---|
| `approved` | array of [`outcomeAction`](#schema-outcomeaction) |  |  |
| `rejected` | array of [`outcomeAction`](#schema-outcomeaction) |  |  |

### `outcomeAction` { #schema-outcomeaction }

One action of an approval outcome: an object with exactly one key. Strings hold $.path expressions; the ! suffix makes the value required.

| Field | Type | Required | Description |
|---|---|---|---|
| `ensureWork` | [object](#schema-outcomeaction-ensurework) |  |  |
| `completeTask` | [object](#schema-outcomeaction-completetask) |  |  |
| `comment` | [object](#schema-outcomeaction-comment) |  |  |
| `transition` | [object](#schema-outcomeaction-transition) |  |  |
| `invokeSkill` | [object](#schema-outcomeaction-invokeskill) |  | Skill invocation; reactions run according to the invocation result |

### `outcomeAction.ensureWork` { #schema-outcomeaction-ensurework }

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `string` | yes | Task type key |
| `key` | `string` | yes | Idempotency key of the work being created |
| `title` | `string` | yes |  |
| `description` | `string` |  |  |
| `assignee` | `string` |  |  |
| `priority` | `string` |  |  |
| `workspace` | `string` |  |  |
| `relation` | map → `string` |  |  |
| `customFields` | map → `string` |  | Fields of the task being created — expressions/templates; checked against the target type's fieldSchema at execution time |
| `requestApproval` | [object](#schema-outcomeaction-ensurework-requestapproval) |  | Gate approval on the newly created task |

### `outcomeAction.ensureWork.requestApproval` { #schema-outcomeaction-ensurework-requestapproval }

Gate approval on the newly created task

| Field | Type | Required | Description |
|---|---|---|---|
| `assignee` | `string` | yes | Principal id or role:&lt;slug&gt; — a role declared by the package (its holder decides); an expression or a template |
| `comment` | `string` |  |  |

### `outcomeAction.completeTask` { #schema-outcomeaction-completetask }

| Field | Type | Required | Description |
|---|---|---|---|
| `task` | `string` |  |  |

### `outcomeAction.comment` { #schema-outcomeaction-comment }

| Field | Type | Required | Description |
|---|---|---|---|
| `body` | `string` | yes |  |
| `task` | `string` |  |  |

### `outcomeAction.transition` { #schema-outcomeaction-transition }

| Field | Type | Required | Description |
|---|---|---|---|
| `status` | `string` | yes |  |
| `task` | `string` |  |  |

### `outcomeAction.invokeSkill` { #schema-outcomeaction-invokeskill }

Skill invocation; reactions run according to the invocation result

| Field | Type | Required | Description |
|---|---|---|---|
| `skill` | `string` | yes | name@version (for external_write, the version is required) |
| `inputs` | `object` |  | skill inputs; strings are $.task…, $.spawnedBy…, $.approval… expressions |
| `expect` | `object` |  | expected outputs fields; a mismatch triggers onFailure |
| `onSuccess` | array of [`outcomeAction`](#schema-outcomeaction) |  |  |
| `onFailure` | array of [`outcomeAction`](#schema-outcomeaction) |  |  |

### `artifactSchema` { #schema-artifactschema }

Inputs and outputs of a task type. An input is the head revisions of artifacts of the required type on tasks linked by a relation; without a required input, a claim is rejected (409 input_missing). A required output is a deterministic criterion of the verification stage.

| Field | Type | Required | Description |
|---|---|---|---|
| `inputs` | array of [object](#schema-artifactschema-inputs-item) |  |  |
| `outputs` | array of [object](#schema-artifactschema-outputs-item) |  |  |

### `artifactSchema.inputs[]` { #schema-artifactschema-inputs-item }

Includes [`artifactSlot`](#schema-artifactslot).

| Field | Type | Required | Description |
|---|---|---|---|
| `key` | any | | |
| `type` | any | | |
| `required` | any | | |
| `from` | `depends_on` \| `spawned_by` \| `parent` | yes | Relation used to find the source task |

### `artifactSchema.outputs[]` { #schema-artifactschema-outputs-item }

Includes [`artifactSlot`](#schema-artifactslot).

| Field | Type | Required | Description |
|---|---|---|---|
| `key` | any | | |
| `type` | any | | |
| `required` | any | | |
| `mediaTypes` | any | | |
| `content` | `required` \| `optional` |  | Whether the content is needed in storage (otherwise a reference is enough). Default: `required`. |

### `artifactSlot` { #schema-artifactslot }

| Field | Type | Required | Description |
|---|---|---|---|
| `key` | `string` | yes | Input or output name; unique within inputs and within outputs |
| `type` | [`typeKey`](#schema-typekey) | yes | Artifact type key (ArtifactType) |
| `required` | `boolean` |  | Default: `false`. |
| `mediaTypes` | array of [`mediaType`](#schema-mediatype) |  | Narrowing of the artifact type's media types (a subset of its mediaTypes) |

### `acceptanceCriterion` { #schema-acceptancecriterion }

Acceptance criterion: the core checks the spec grammar per kind

| Field | Type | Required | Description |
|---|---|---|---|
| `key` | `string` | yes |  |
| `kind` | `deterministic` \| `external_state` \| `human` \| `llm_judge` | yes |  |
| `description` | `string` | yes |  |
| `spec` | `object` |  |  |
| `when` | array of `string` |  | $.task… paths; the criterion runs only if all of them are non-empty, otherwise skipped |
<!-- /generated:schema-task-type -->

## Project template (`kind: ProjectTemplate`) { #project-template }

<!-- generated:schema-project-template -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/object.schema.json`.

### `projectTemplateSpec` { #schema-projecttemplatespec }

| Field | Type | Required | Description |
|---|---|---|---|
| `displayName` | [`displayName`](#schema-displayname) | yes |  |
| `description` | `string` |  |  |
| `fieldSchema` | [`jsonSchema`](#schema-jsonschema) |  |  |
| `lifecycleSchema` | [`projectLifecycle`](#schema-projectlifecycle) |  |  |
| `defaultConfig` | [object](#schema-projecttemplatespec-defaultconfig) |  |  |
| `defaultViews` | array of any |  |  |
| `governanceSchema` | [object](#schema-projecttemplatespec-governanceschema) |  |  |
| `memoryDefaults` | `object` |  |  |

### `projectTemplateSpec.defaultConfig` { #schema-projecttemplatespec-defaultconfig }

| Field | Type | Required | Description |
|---|---|---|---|
| `settings` | `object` |  |  |
| `views` | array of any |  |  |
| `governance` | `object` |  |  |
| `memory` | `object` |  |  |
| `inheritance` | `object` |  |  |

### `projectTemplateSpec.governanceSchema` { #schema-projecttemplatespec-governanceschema }

| Field | Type | Required | Description |
|---|---|---|---|
| `maxAutonomyLevel` | any |  |  |
| `requireApprovalForRun` | `boolean` |  |  |
| `requireApprovalForCompletion` | `boolean` |  |  |
| `allowedTaskPriorities` | array of `string` |  |  |
| `allowedSkillProtocols` | array of `string` |  |  |
| `maxRunDurationSeconds` | `number` |  |  |
| `maxRunActions` | `number` |  |  |
| `maxConcurrentRuns` | `number` |  |  |
| `memoryScopeSharing` | any |  |  |

### `projectLifecycle` { #schema-projectlifecycle }

Includes [`lifecycle`](#schema-lifecycle).

| Field | Type | Required | Description |
|---|---|---|---|
| `statuses` | array of [object](#schema-projectlifecycle-statuses-item) |  |  |

### `projectLifecycle.statuses[]` { #schema-projectlifecycle-statuses-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `category` | [`projectCategory`](#schema-projectcategory) |  |  |

### `projectCategory` { #schema-projectcategory }

Value: `planned` \| `active` \| `paused` \| `terminal_success` \| `terminal_cancelled`.
<!-- /generated:schema-project-template -->

## Workspace type (`kind: WorkspaceType`) { #workspace-type }

<!-- generated:schema-workspace-type -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/object.schema.json`.

### `workspaceTypeSpec` { #schema-workspacetypespec }

| Field | Type | Required | Description |
|---|---|---|---|
| `displayName` | [`displayName`](#schema-displayname) | yes |  |
| `description` | `string` |  |  |
| `fieldSchema` | [`jsonSchema`](#schema-jsonschema) |  |  |
| `allowedChildTypes` | array of `string` |  |  |
<!-- /generated:schema-workspace-type -->

## Role (`kind: Role`) { #role }

<!-- generated:schema-role -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/object.schema.json`.

### `roleSpec` { #schema-rolespec }

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | [`displayName`](#schema-displayname) | yes |  |
| `description` | `string` |  |  |
<!-- /generated:schema-role -->

## Capability (`kind: Capability`) { #capability }

<!-- generated:schema-capability -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/object.schema.json`.

### `capabilitySpec` { #schema-capabilityspec }

| Field | Type | Required | Description |
|---|---|---|---|
| `description` | `string` |  |  |
<!-- /generated:schema-capability -->

## Connection type (`kind: ConnectionType`) { #connection-type }

<!-- generated:schema-connection-type -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/object.schema.json`.

### `connectionTypeSpec` { #schema-connectiontypespec }

Connection type: what it takes to connect a system of this kind. Versions work as for Skill: the package sets the version, and a published (key, version) pair is immutable. A type carries no secret values: an administrator enters them in the console.

| Field | Type | Required | Description |
|---|---|---|---|
| `version` | `integer` | yes | The package sets the version of the type; a published version is immutable |
| `displayName` | [`displayName`](#schema-displayname) | yes |  |
| `description` | `string` |  |  |
| `auth` | array of `oauth2` \| `token` | yes | Ways to connect: oauth2 — a person consents at the provider, token — a long-lived key an administrator pastes |
| `oauth2` | [object](#schema-connectiontypespec-oauth2) |  |  |
| `accountField` | [object](#schema-connectiontypespec-accountfield) |  | Account field: its label in the key form and the account check; required with token or with {account} in tokenUrlTemplate |
| `settingsSchema` | [object](#schema-connectiontypespec-settingsschema) | yes | JSON Schema (draft 2020-12) of the connection's non-secret settings, root type: object. Properties named like secrets (password, token, clientSecret…) are refused |
| `defaultKey` | [`connectionKey`](#schema-connectionkey) | yes | Key of the default connection — the agents of the package name it in Agent.spec.connections |

Conditions:

| Condition | Consequence |
|---|---|
| always | required `oauth2` |
| always | required `accountField` |
| always | required `accountField`; `oauth2`:  |

### `connectionTypeSpec.oauth2` { #schema-connectiontypespec-oauth2 }

| Field | Type | Required | Description |
|---|---|---|---|
| `authorizeUrl` | `string` (uri) | yes | Where a person is sent to consent |
| `tokenUrlTemplate` | `string` | yes | Address of the code exchange and refresh; the only placeholder is {account}, the host is an external DNS name |
| `accountParam` | `string` |  | Callback parameter that names the account; required when tokenUrlTemplate has {account} |
| `authStyle` | `in_params` \| `in_header` | yes | How the client id and secret go to the exchange address: in the request body or as Authorization: Basic |
| `scopes` | array of `string` | yes | Requested permissions |

### `connectionTypeSpec.accountField` { #schema-connectiontypespec-accountfield }

Account field: its label in the key form and the account check; required with token or with {account} in tokenUrlTemplate

| Field | Type | Required | Description |
|---|---|---|---|
| `title` | `string` | yes |  |
| `description` | `string` |  |  |
| `pattern` | `string` | yes | Regular expression the whole account matches |

### `connectionTypeSpec.settingsSchema` { #schema-connectiontypespec-settingsschema }

JSON Schema (draft 2020-12) of the connection's non-secret settings, root type: object. Properties named like secrets (password, token, clientSecret…) are refused

Includes [`jsonSchema`](#schema-jsonschema).

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | = `object` | yes |  |
<!-- /generated:schema-connection-type -->

## Skill (`kind: Skill`) { #skill }

<!-- generated:schema-skill -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/object.schema.json`.

### `skillSpec` { #schema-skillspec }

| Field | Type | Required | Description |
|---|---|---|---|
| `version` | `string` | yes | The package sets the skill version |
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

| Field | Type | Required | Description |
|---|---|---|---|
| `inputs` | [`jsonSchema`](#schema-jsonschema) | yes |  |
| `outputs` | [`jsonSchema`](#schema-jsonschema) | yes |  |
| `requiredPermissions` | array of `string` |  |  |
| `preconditions` | array of any |  |  |
| `postconditions` | array of any |  |  |
| `timeoutSeconds` | `integer` |  |  |
| `retryPolicy` | [object](#schema-skillcontract-retrypolicy) |  |  |
| `idempotency` | `required` \| `natural` \| `none` |  |  |
| `costModel` | [object](#schema-skillcontract-costmodel) |  |  |
| `implementation` | [object](#schema-skillcontract-implementation) | yes |  |

### `skillContract.retryPolicy` { #schema-skillcontract-retrypolicy }

| Field | Type | Required | Description |
|---|---|---|---|
| `maxAttempts` | `integer` |  |  |
| `backoffSeconds` | `integer` |  |  |

### `skillContract.costModel` { #schema-skillcontract-costmodel }

| Field | Type | Required | Description |
|---|---|---|---|
| `unit` | `string` | yes |  |
| `estimate` | `number` |  |  |

### `skillContract.implementation` { #schema-skillcontract-implementation }

| Field | Type | Required | Description |
|---|---|---|---|
| `protocol` | `http` \| `local` \| `mcp` | yes |  |
| `endpoint` | `string` |  | http: address; may contain an environment ${VARIABLE} |
| `entrypoint` | `string` |  | local: module:function; mcp: tool name |
| `auth` | `object` |  | audience or secretRef; no secrets |
<!-- /generated:schema-skill -->

## Work rule (`kind: WorkRule`) { #work-rule }

<!-- generated:schema-work-rule -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/object.schema.json`.

### `workRuleSpec` { #schema-workrulespec }

Work rule: exactly the POST /rules body without key. The core checks the grammar of conditions and templates (normalize_rule_spec). workspaceId is installation topology: only through a ${VARIABLE}, set on creation and not changed afterwards.

| Field | Type | Required | Description |
|---|---|---|---|
| `description` | `string` |  |  |
| `workspaceId` | `string` |  |  |
| `trigger` | [object](#schema-workrulespec-trigger) | yes |  |
| `condition` | `object` \| `boolean` |  |  |
| `interpretation` | [object](#schema-workrulespec-interpretation) |  |  |
| `action` | [object](#schema-workrulespec-action) | yes |  |
| `identity` | [object](#schema-workrulespec-identity) |  | On whose behalf the rule acts: an agent description of kind service or agent; without identity, the rule acts with the authority of whoever applied it |
| `status` | `enabled` \| `disabled` |  | Default enabled |

### `workRuleSpec.trigger` { #schema-workrulespec-trigger }

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | `observation` \| `event` \| `schedule` | yes |  |
| `agent` | `string` |  | Only with observation: the observation matches when its author is the principal of this agent. An agent key or an installation ${VARIABLE} — a neutral package does not know the provider's agent |

### `workRuleSpec.interpretation` { #schema-workrulespec-interpretation }

| Field | Type | Required | Description |
|---|---|---|---|
| `skill` | `string` | yes | name@version |
| `inputs` | `object` |  |  |

### `workRuleSpec.action` { #schema-workrulespec-action }

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | `ensure_work` \| `update_work` \| `cancel_work` \| `complete_work` \| `request_decision` | yes |  |
| `taskType` | `string` |  | Type key or a {{item.…}} template — a template only with a non-empty taskTypes |
| `taskTypes` | array of [`typeKey`](#schema-typekey) |  | Allowed types for a templated taskType; with complete_work and cancel_work with target: task — the types the rule may close |
| `target` | `dedup` \| `task` |  | Only with complete_work and cancel_work: dedup — the work under the rule's key (the default), task — the task the triggering observation is bound to; needs taskTypes and an author filter trigger.agent or trigger.actorId |
| `fields` | [object](#schema-workrulespec-action-fields) |  |  |

### `workRuleSpec.action.fields` { #schema-workrulespec-action-fields }

| Field | Type | Required | Description |
|---|---|---|---|
| `workspaceId` | `string` |  | Template of the workspace id of the work being created; by default the rule's workspace |
| `relations` | [object](#schema-workrulespec-action-fields-relations) |  | Relations of the work being created: spawnedBy is a task id template; dependsOn is deduplication keys of work of this rule (from the same evaluation or created earlier) |

### `workRuleSpec.action.fields.relations` { #schema-workrulespec-action-fields-relations }

Relations of the work being created: spawnedBy is a task id template; dependsOn is deduplication keys of work of this rule (from the same evaluation or created earlier)

| Field | Type | Required | Description |
|---|---|---|---|
| `spawnedBy` | `string` |  |  |
| `dependsOn` | `string` or array of `string` |  |  |

### `workRuleSpec.identity` { #schema-workrulespec-identity }

On whose behalf the rule acts: an agent description of kind service or agent; without identity, the rule acts with the authority of whoever applied it

| Field | Type | Required | Description |
|---|---|---|---|
| `agent` | [`slug`](#schema-slug) | yes |  |
<!-- /generated:schema-work-rule -->

## Agent (`kind: Agent`) { #agent }

<!-- generated:schema-agent -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/object.schema.json`.

### `agentSpec` { #schema-agentspec }

Agent: who it is, what work it takes, with what and how it executes that work, where it is placed. Each change is a new immutable revision in the core; a run remembers its revision.

| Field | Type | Required | Description |
|---|---|---|---|
| `displayName` | [`displayName`](#schema-displayname) | yes |  |
| `description` | `string` |  |  |
| `identity` | [object](#schema-agentspec-identity) | yes | Identity: the core and IAM principal and the binding with permissions — the platform creates and maintains them. Permissions are no wider than those of whoever applies the description. |
| `work` | [object](#schema-agentspec-work) |  | What work the agent takes from the queue |
| `executor` | [object](#schema-agentspec-executor) |  | What the agent executes work with. The kind is data (a string for the core); the node chooses the default image, and an image from the description is allowed only from the node's list. |
| `workingCopy` | `object` |  | Task working copy. The executor daemon interprets it, the core stores the object as data; its shape is set by the executor kind: shapes per kind are in agentWorkingCopies: for the coding executor kind, one repository or a catalog with a task field; for other kinds, one repository |
| `skills` | [object](#schema-agentspec-skills) |  | Which skills the agent executes itself and where they may connect |
| `placement` | = `none` or [object](#schema-agentspec-placement) — by condition |  | Where and how many: none means identity only, without a process (a service account) |
| `state` | `running` \| `stopped` |  | Default: `running`. |
| `connections` | array of [`connectionKey`](#schema-connectionkey) |  | Keys of the tenant's connections whose access material the agent may read. Whether such a connection exists is not checked on publish; a non-empty list needs connections.manage of whoever applies it |

Conditions:

| Condition | Consequence |
|---|---|
| not (`placement` = `none`) | `executor` required |
| `executor.kind` = `claude-code` | `workingCopy`: [`agentWorkingCopies/claude-code`](#schema-agentworkingcopies-claude-code) |
| otherwise | `workingCopy`: [`agentWorkingCopies/single`](#schema-agentworkingcopies-single) |

### `agentSpec.identity` { #schema-agentspec-identity }

Identity: the core and IAM principal and the binding with permissions — the platform creates and maintains them. Permissions are no wider than those of whoever applies the description.

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | `agent` \| `service` | yes |  |
| `roles` | array of [`slug`](#schema-slug) |  | Tenant roles (from packages) |
| `permissions` | array of [`permission`](#schema-permission) |  |  |
| `capabilities` | array of `string` |  |  |
| `iam` | [object](#schema-agentspec-identity-iam) |  | IAM part of the account: audiences and the scope ceiling. Data for whoever issues the account (bootstrap, the executor node controller); the core stores it but does not interpret it. |

### `agentSpec.identity.iam` { #schema-agentspec-identity-iam }

IAM part of the account: audiences and the scope ceiling. Data for whoever issues the account (bootstrap, the executor node controller); the core stores it but does not interpret it.

| Field | Type | Required | Description |
|---|---|---|---|
| `audiences` | array of `string` | yes |  |
| `scopeCeiling` | array of `string` | yes | Scope &lt;audience&gt;:&lt;action&gt;, segments may be dotted (control-plane:read, iam:identities.link) |

### `agentSpec.work` { #schema-agentspec-work }

What work the agent takes from the queue

| Field | Type | Required | Description |
|---|---|---|---|
| `workspace` | [`envOrUuid`](#schema-envoruuid) |  |  |
| `project` | [`envOrUuid`](#schema-envoruuid) |  |  |
| `includeSubprojects` | `boolean` |  | Default: `false`. |
| `onlyAssigned` | `boolean` |  | Only work assigned to it. Default: `true`. |
| `taskTypes` | array of [`typeKey`](#schema-typekey) |  | Empty means any types |

### `agentSpec.executor` { #schema-agentspec-executor }

What the agent executes work with. The kind is data (a string for the core); the node chooses the default image, and an image from the description is allowed only from the node's list.

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | `claude-code` \| `codex` \| `skills` \| `git-connector` \| `observer` | yes |  |
| `params` | `object` |  |  |
| `image` | `string` |  | Executor image: [registry[:port]/]path:tag, …@sha256:&lt;64 hex&gt; or …:tag@sha256:&lt;64 hex&gt; — a tag or a digest is required. The node runs it only if the image is in the node's executors.&lt;kind&gt;.images list, otherwise image_not_allowed; without the field, the kind's default image is used |
| `instructions` | `string` |  | Instructions for the executor — a layer after the instructions of the platform, the project, and the task type |

Conditions:

| Condition | Consequence |
|---|---|
| `kind` = `claude-code` | `params`: [`agentExecutors/claude-code`](#schema-agentexecutors-claude-code) |
| `kind` = `codex` | `params`: [`agentExecutors/codex`](#schema-agentexecutors-codex) |
| `kind` = `skills` | `params`: [`agentExecutors/skills`](#schema-agentexecutors-skills) |
| `kind` = `git-connector` | `params` required; `params`: [`agentExecutors/git-connector`](#schema-agentexecutors-git-connector) |
| `kind` = `observer` | `params` required; `params`: [`agentExecutors/observer`](#schema-agentexecutors-observer) |

### `agentSpec.skills` { #schema-agentspec-skills }

Which skills the agent executes itself and where they may connect

| Field | Type | Required | Description |
|---|---|---|---|
| `protocols` | array of `local` \| `http` \| `mcp` |  |  |
| `local` | array of `string` |  | Allowed entrypoints or packages |
| `httpOrigins` | array of `string` |  |  |
| `mcpOrigins` | array of `string` |  |  |
| `audiences` | array of `string` |  | IAM audiences for which skills receive a token |
| `concurrency` | `integer` |  |  |
| `invoke` | array of `string` |  | Skill versions that the agent invokes through the core (name@version) instead of executing them itself; the registry assigns them to the agent's principal |

### `agentSpec.placement` { #schema-agentspec-placement }

| Field | Type | Required | Description |
|---|---|---|---|
| `requires` | array of [`nodeLabel`](#schema-nodelabel) |  | Labels the node must have |
| `secrets` | array of [`secretName`](#schema-secretname) |  | Secrets that must be on the node: static ones (a file in the node's secrets directory) and issued ones — the node issues and refreshes them itself, for example an hourly forge-token from the forge app installation. Both are declared the same way, by name; the secret material is not written into the description |
| `resources` | [object](#schema-agentspec-placement-resources) |  |  |
| `replicas` | `integer` |  | Default: `1`. |
| `drainSeconds` | `integer` |  | How long to wait for the current run before switching to a new revision. Default: `14400`. |

### `agentSpec.placement.resources` { #schema-agentspec-placement-resources }

| Field | Type | Required | Description |
|---|---|---|---|
| `cpus` | `integer` |  | Whole CPUs: the core's canonical revision hash rejects fractional numbers (non_canonical_value) |
| `memoryMb` | `integer` |  |  |

### `permission` { #schema-permission }

A Control Plane permission, for example tasks.claim

Value: `string`.

### `agentExecutors` { #schema-agentexecutors }

Parameters of executor kinds; the core stores them without interpreting them, this schema and the adapter check them

Definitions: [`agentExecutors/claude-code`](#schema-agentexecutors-claude-code), [`agentExecutors/codex`](#schema-agentexecutors-codex), [`agentExecutors/skills`](#schema-agentexecutors-skills), [`agentExecutors/git-connector`](#schema-agentexecutors-git-connector), [`agentExecutors/observer`](#schema-agentexecutors-observer).

### `agentExecutors/claude-code` { #schema-agentexecutors-claude-code }

| Field | Type | Required | Description |
|---|---|---|---|
| `model` | `string` |  |  |
| `permissionMode` | `default` \| `acceptEdits` \| `plan` \| `bypassPermissions` |  | Default: `acceptEdits`. |
| `timeoutSeconds` | `integer` |  | Default: `3600`. |
| `resume` | `boolean` |  | Default: `true`. |
| `tools` | [object](#schema-agentexecutors-claude-code-tools) |  | Narrowing of the agent's tools; the ban on authoritative Control Plane commands cannot be lifted |

### `agentExecutors/claude-code.tools` { #schema-agentexecutors-claude-code-tools }

Narrowing of the agent's tools; the ban on authoritative Control Plane commands cannot be lifted

| Field | Type | Required | Description |
|---|---|---|---|
| `allow` | array of `string` |  |  |
| `deny` | array of `string` |  |  |

### `agentExecutors/codex` { #schema-agentexecutors-codex }

| Field | Type | Required | Description |
|---|---|---|---|
| `model` | `string` |  |  |
| `sandbox` | `read-only` \| `workspace-write` \| `danger-full-access` |  | Default: `workspace-write`. |
| `timeoutSeconds` | `integer` |  | Default: `3600`. |
| `resume` | `boolean` |  | Default: `true`. |
| `credentialClass` | `subscription` \| `api_key` |  | Whose credential is consumed |

### `agentExecutors/skills` { #schema-agentexecutors-skills }

A skills-only executor: what to execute is defined by the agent's skills section; the parameters are non-secret skill settings

| Field | Type | Required | Description |
|---|---|---|---|
| `env` | map → `string` |  | Non-secret skill settings (portal address, limits): environment variables of every local skill call on the skill host. No secrets here: names like *TOKEN, *SECRET, *PASSWORD, *API_KEY are forbidden, secrets go in the node's secret files (placement.secrets); host names (CONTROL_PLANE_*, IAM_*, PATH…) too |

### `agentExecutors/git-connector` { #schema-agentexecutors-git-connector }

Source of git observations: what to observe and which observations to produce. The cursor is in the replica volume; observations go to POST /observations of the agent's workspace.

| Field | Type | Required | Description |
|---|---|---|---|
| `repositories` | array of [object](#schema-agentexecutors-git-connector-repositories-item) | yes |  |
| `observe` | array of `commits` \| `adrRegistry` \| `ciRuns` |  | commits — repo.commit_observed; adrRegistry — adr.registry_observed; ciRuns — ci.run_observed. Default: `["commits"]`. |
| `intervalSeconds` | `integer` |  | Default: `300`. |
| `knowledgeSnapshots` | `boolean` |  | Send contract snapshots to memory through POST /knowledge/snapshots. Default: `true`. |
| `registryRepository` | `string` |  | Repository to read the ADR registry from (a name from repositories) |
| `ciRepository` | `string` |  | owner/repo of the CI runs |
| `ciBranch` | `string` |  | Default: `main`. |

### `agentExecutors/git-connector.repositories[]` { #schema-agentexecutors-git-connector-repositories-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | yes | Name in observations (payload.data.repo, source git:&lt;name&gt;) |
| `url` | `string` | yes |  |
| `branch` | `string` |  | Default: `main`. |

### `agentExecutors/observer` { #schema-agentexecutors-observer }

Observation source of an integration package (a connector = an observer + skills): a long-running process that polls an external system in a loop and writes observations to the agent's workspace (POST /observations). What to poll is config, interpreted by the integration code; which code runs is entrypoint, which the observer kind image on the node must contain. The cursor is in the replica volume; secrets come only as node secret files (placement.secrets).

| Field | Type | Required | Description |
|---|---|---|---|
| `entrypoint` | `string` | yes | Integration observer "module:function"; the image process checks that it runs exactly this one |
| `intervalSeconds` | `integer` |  | Default: `900`. |
| `config` | `object` |  | Integration parameters (filters, addresses, limits) — package data. No secrets here: keys such as *token, *secret, *password are forbidden |

### `nodeLabel` { #schema-nodelabel }

Node label: name or name=value

Value: `string`.

### `secretName` { #schema-secretname }

Name of a secret on the node; the value is not written into the description

Value: `string`.

### `agentWorkingCopies` { #schema-agentworkingcopies }

Shapes of the workingCopy section per executor kind: the core stores the section as data; this schema and the executor daemon check it

Definitions: [`agentWorkingCopies/single`](#schema-agentworkingcopies-single), [`agentWorkingCopies/catalog`](#schema-agentworkingcopies-catalog), [`agentWorkingCopies/catalogEntry`](#schema-agentworkingcopies-catalogentry), [`agentWorkingCopies/claude-code`](#schema-agentworkingcopies-claude-code).

### `agentWorkingCopies/claude-code` { #schema-agentworkingcopies-claude-code }

One repository (the previous shape) or a catalog: the presence of repositories or repositoryField selects the catalog

Value: [`agentWorkingCopies/catalog`](#schema-agentworkingcopies-catalog) or [`agentWorkingCopies/single`](#schema-agentworkingcopies-single) — by condition.

Conditions:

| Condition | Consequence |
|---|---|
| `repositories` is set or `repositoryField` is set | [`agentWorkingCopies/catalog`](#schema-agentworkingcopies-catalog) |
| otherwise | [`agentWorkingCopies/single`](#schema-agentworkingcopies-single) |

### `agentWorkingCopies/catalog` { #schema-agentworkingcopies-catalog }

Repository catalog — the only source of clone, neighbour, and publication addresses. The task repository is a catalog key or an alias in the task field repositoryField; an address from the task is not accepted, and there is no default. Keys and aliases are matched case-insensitively (casefold) — this is how the executor daemon and tasks.check@1 resolve the task key. package-sdk check verifies the superproject reference to a catalog key and the uniqueness of keys and aliases (casefold), addresses (normalized), and directories across entries

| Field | Type | Required | Description |
|---|---|---|---|
| `repositoryField` | `string` | yes | Name of the task customFields field that holds the repository key (for coding-task, repositoryKey) |
| `superproject` | any |  | Catalog key whose submodules pin the revisions of the neighbours |
| `publish` | `boolean` |  | Publish the task branch to the forge; a catalog entry can override this. Default: `true`. |
| `checks` | `boolean` |  | Run the checks of .agents/runner.yaml of the base revision before hand-in; the report goes to metadata.checks of the commit artifact. Default: `false`. |
| `repositories` | map → [`agentWorkingCopies/catalogEntry`](#schema-agentworkingcopies-catalogentry) | yes |  |

### `repositoryKey` { #schema-repositorykey }

Canonical repository key in the working copy catalog: ASCII, as in the task customFields. Keys and aliases are matched case-insensitively (casefold): this is how the executor daemon and tasks.check@1 resolve the task key

Value: `string`.

### `agentWorkingCopies/catalogEntry` { #schema-agentworkingcopies-catalogentry }

| Field | Type | Required | Description |
|---|---|---|---|
| `url` | `string` | yes | Clone address: an installation ${VARIABLE} or https without credentials, query, and fragment (environment topology is not written into the package). The host is DNS labels, the port is 1–65535; path segments are ASCII without dot segments and without a leading dot: the mirror name is taken from the last segment. package-sdk check looks for matching addresses of two entries after normalization (without a trailing /, without .git, case-insensitive) |
| `baseRef` | `string` |  | Base branch of the task — a git ref name: no leading - / ., no spaces or control characters, no .., @{, //, ~^:?*[\ and no trailing / . .lock |
| `directory` | any |  | Directory in the working copy: a name (flat layout) or a path of several segments (services/control-plane). It does not repeat the directory or the key of another entry, and is neither inside the directory of another entry nor contains it — checked by package-sdk check |
| `publish` | `boolean` |  | false — a neighbour the agent does not write to; by default the catalog's publish |
| `aliases` | array of [`repositoryAlias`](#schema-repositoryalias) |  | Previous names accepted instead of the key; matching is case-insensitive (casefold), so aliases do not repeat their own or other entries' keys and aliases, even in a different case |

### `workingCopyPath` { #schema-workingcopypath }

A directory in the working copy relative to its root: one name (flat layout, control-plane) or a path of several segments joined by / (services/control-plane, sdk/platform-auth-sdk). A segment starts with a lowercase Latin letter or a digit, so . and .. do not pass; an absolute path, an empty segment (//, a trailing /) and a backslash are rejected

Value: `string`.

### `repositoryAlias` { #schema-repositoryalias }

Previous repository name (a map key, the `Репозиторий` ("Repository") line of the task document, a connector deduplication key): Latin and Cyrillic letters, digits, . _ -. Matched against the task key case-insensitively (casefold)

Value: `string`.

### `agentWorkingCopies/single` { #schema-agentworkingcopies-single }

Previous shape: one repository, with neighbours and the superproject given by address

| Field | Type | Required | Description |
|---|---|---|---|
| `repository` | `string` | yes |  |
| `directory` | any |  | Directory of the repository in the working copy: a name (flat layout) or a path of several segments |
| `baseRef` | `string` |  |  |
| `neighbours` | map → `string` |  | Neighbour repositories at revisions pinned by the superproject. The key is the neighbour's directory in the working copy: a name or a path of several segments |
| `superproject` | `string` |  |  |
| `publish` | `boolean` |  | Publish the task branch to the forge. Default: `true`. |
| `checks` | `boolean` |  | Run the checks of .agents/runner.yaml of the base revision before hand-in; the report goes to metadata.checks of the commit artifact. Default: `false`. |
| `review` | [object](#schema-agentworkingcopies-single-review) |  | Deprecated: the task type declares review through acceptance criteria; the section is removed together with the daemon's auto-review |

### `agentWorkingCopies/single.review` { #schema-agentworkingcopies-single-review }

Deprecated: the task type declares review through acceptance criteria; the section is removed together with the daemon's auto-review

| Field | Type | Required | Description |
|---|---|---|---|
| `mode` | `human` \| `agent` \| `none` |  |  |
| `taskType` | [`typeKey`](#schema-typekey) |  |  |
| `taskTypes` | array of [`typeKey`](#schema-typekey) |  | Task types for which a review is created |
| `reviewer` | [`envOrUuid`](#schema-envoruuid) |  |  |
| `base` | `string` |  |  |
<!-- /generated:schema-agent -->

## Notification rule (`kind: NotificationRule`) { #notification-rule }

<!-- generated:schema-notification-rule -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/object.schema.json`.

### `notificationRuleSpec` { #schema-notificationrulespec }

Notification rule: a core event and a condition → a recipient → text and buttons. The notification service stores and executes it; templates are {{payload.…}}, {{event.…}}, {{task.…}} substitution without logic.

| Field | Type | Required | Description |
|---|---|---|---|
| `description` | `string` |  |  |
| `on` | [object](#schema-notificationrulespec-on) | yes |  |
| `recipient` | [object](#schema-notificationrulespec-recipient) | yes |  |
| `notification` | [object](#schema-notificationrulespec-notification) | yes |  |
| `dedupKeyTemplate` | `string` |  |  |
| `close` | [object](#schema-notificationrulespec-close) |  | Close the buttons of the notification with the same deduplication key when the event arrives |
| `status` | `enabled` \| `disabled` |  | Default enabled |

### `notificationRuleSpec.on` { #schema-notificationrulespec-on }

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `string` | yes | Event type from the core catalog, or prefix.* |
| `when` | `object` \| `boolean` |  | Condition in the core rule grammar over payload, event, and task |

### `notificationRuleSpec.recipient` { #schema-notificationrulespec-recipient }

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | `assigned` \| `role` \| `taskOwner` \| `taskAssignee` \| `principal` | yes |  |
| `ref` | `string` |  | Path to the principal or role in the event (assigned, role) or an id/variable (principal) |
| `workspace` | `string` |  | Path to the workspace for role; by default the event's workspace |
| `fallback` | `taskOwner` \| `taskAssignee` \| `none` |  | Default: `none`. |

### `notificationRuleSpec.notification` { #schema-notificationrulespec-notification }

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `string` | yes | Notification type — recipient settings and mandatory rules work by it |
| `title` | `string` | yes |  |
| `body` | `string` |  |  |
| `links` | array of [object](#schema-notificationrulespec-notification-links-item) |  |  |
| `actions` | array of `approvalDecide` |  | approvalDecide — "Approve"/"Reject" buttons for the decision from payload.approvalId |

### `notificationRuleSpec.notification.links[]` { #schema-notificationrulespec-notification-links-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `label` | `string` | yes |  |
| `url` | `string` | yes |  |

### `notificationRuleSpec.close` { #schema-notificationrulespec-close }

Close the buttons of the notification with the same deduplication key when the event arrives

| Field | Type | Required | Description |
|---|---|---|---|
| `on` | array of `string` | yes |  |
| `outcome` | `string` |  | Outcome template shown instead of the buttons |
<!-- /generated:schema-notification-rule -->

## Process (`kind: Process`) { #process }

<!-- generated:schema-process -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/object.schema.json`.

### `processSpec` { #schema-processspec }

Process: a case with stages and execution blocks, data by schema, CEL expressions, projection into memory. The core executes it

| Field | Type | Required | Description |
|---|---|---|---|
| `version` | `integer` | yes | Definition version: a published version is immutable |
| `displayName` | [`displayName`](#schema-displayname) | yes |  |
| `description` | `string` |  |  |
| `workspaceId` | `string` |  |  |
| `identity` | [object](#schema-processspec-identity) |  | On whose behalf the process acts: an agent description of kind service or agent |
| `owner` | [`assignChain`](#schema-assignchain) |  | Process owner: tasks about the process are addressed to them: divergence from a regulation, instance errors. Optional; the package check warns if it is missing |
| `calendar` | [`typeKey`](#schema-typekey) |  | Default calendar for cal.* |
| `due` | [`processDue`](#schema-processdue) |  | Deadline of the whole process from the instance start |
| `data` | [`jsonSchema`](#schema-jsonschema) | yes | JSON Schema of the instance data; package-sdk expands {$ref: &lt;package file&gt;} |
| `start` | [object](#schema-processspec-start) | yes |  |
| `correlate` | array of [object](#schema-processspec-correlate-item) |  |  |
| `stages` | array of [`processStage`](#schema-processstage) | yes |  |
| `onEvent` | array of [object](#schema-processspec-onevent-item) |  |  |
| `timers` | [`processTimers`](#schema-processtimers) |  |  |
| `decisions` | array of [`decisionTable`](#schema-decisiontable) |  |  |
| `governedBy` | [`governedBy`](#schema-governedby) |  |  |
| `memory` | [`memoryProjection`](#schema-memoryprojection) |  |  |
| `retrospective` | [object](#schema-processspec-retrospective) |  | Review of a closed case: an agent proposes lessons, a human confirms |
| `migrations` | array of [object](#schema-processspec-migrations-item) |  |  |

### `processSpec.identity` { #schema-processspec-identity }

On whose behalf the process acts: an agent description of kind service or agent

| Field | Type | Required | Description |
|---|---|---|---|
| `agent` | [`slug`](#schema-slug) | yes |  |

### `processSpec.start` { #schema-processspec-start }

| Field | Type | Required | Description |
|---|---|---|---|
| `on` | [`processTrigger`](#schema-processtrigger) | yes |  |
| `key` | [`cel`](#schema-cel) | yes | Instance key: a repeated event with the same key is a correlate, not a new instance |
| `set` | [`celMap`](#schema-celmap) |  |  |

### `processSpec.correlate[]` { #schema-processspec-correlate-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `on` | [`processTrigger`](#schema-processtrigger) | yes |  |
| `key` | [`cel`](#schema-cel) | yes |  |
| `set` | [`celMap`](#schema-celmap) |  |  |
| `do` | [`blocks`](#schema-blocks) |  |  |

### `processSpec.onEvent[]` { #schema-processspec-onevent-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `on` | [`processTrigger`](#schema-processtrigger) | yes |  |
| `do` | [`blocks`](#schema-blocks) | yes |  |

### `processSpec.retrospective` { #schema-processspec-retrospective }

Review of a closed case: an agent proposes lessons, a human confirms

| Field | Type | Required | Description |
|---|---|---|---|
| `skill` | `string` |  | Default: `process.retrospective@1`. |
| `taskType` | [`typeKey`](#schema-typekey) | yes |  |
| `assign` | [`assignChain`](#schema-assignchain) | yes |  |
| `appliesTo` | array of `string` |  | Entity kinds that lessons are attached to |
| `when` | [`cel`](#schema-cel) |  |  |

### `processSpec.migrations[]` { #schema-processspec-migrations-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `from` | `integer` | yes |  |
| `to` | `integer` | yes |  |
| `policy` | `pin` \| `migrate` | yes |  |
| `map` | map → [`processElementId`](#schema-processelementid) |  |  |

### `assignChain` { #schema-assignchain }

Candidates in order: the first resolvable one is taken

Value: array of [`assignee`](#schema-assignee).

### `assignee` { #schema-assignee }

| Field | Type | Required | Description |
|---|---|---|---|
| `principal` | [`envOrUuid`](#schema-envoruuid) |  |  |
| `role` | [`slug`](#schema-slug) |  |  |
| `agent` | [`slug`](#schema-slug) |  |  |
| `expr` | [`cel`](#schema-cel) |  | CEL → a principal id, agent:&lt;key&gt;, or role:&lt;slug&gt; |

Exactly one of: `principal`, `role`, `agent`, `expr`.

### `cel` { #schema-cel }

A CEL expression in the taimen/1 profile: variables data, event, step, task, instance; cal.* functions; no current time. The core checks types and the cost limit

Value: `string`.

### `processDue` { #schema-processdue }

Deadline (SLA) of a step or a process: an ISO 8601 duration, {at} — a point in time or a duration from the data, or exactly one of duration, workdays, workhours with optional calendar and warnBefore

Value: [`durationOrCel`](#schema-durationorcel) or [object `{duration, workdays, workhours, calendar, warnBefore}`](#schema-processdue-2).

### `processDue (2)` { #schema-processdue-2 }

| Field | Type | Required | Description |
|---|---|---|---|
| `duration` | [`duration`](#schema-duration) |  |  |
| `workdays` | [`workdayAmount`](#schema-workdayamount) |  |  |
| `workhours` | [`workhourAmount`](#schema-workhouramount) |  |  |
| `calendar` | [`typeKey`](#schema-typekey) |  | Calendar of the working units; by default the process's spec.calendar |
| `warnBefore` | [`workingSpan`](#schema-workingspan) |  | Warning threshold before the deadline; without it there is no warning |

Exactly one of: `duration`, `workdays`, `workhours`.

### `durationOrCel` { #schema-durationorcel }

An ISO 8601 duration or a CEL expression that yields a point in time (timestamp) or a duration

Value: [`duration`](#schema-duration) or [object `{at}`](#schema-durationorcel-2).

### `durationOrCel (2)` { #schema-durationorcel-2 }

| Field | Type | Required | Description |
|---|---|---|---|
| `at` | [`cel`](#schema-cel) | yes |  |

### `workdayAmount` { #schema-workdayamount }

Value: [`workdayCount`](#schema-workdaycount) or [`workingAmountExpr`](#schema-workingamountexpr).

### `workdayCount` { #schema-workdaycount }

Working days by the calendar: the same time of day n working days later (cal.addWorkdays)

Value: `integer`.

### `workingAmountExpr` { #schema-workingamountexpr }

A number of working units as a CEL expression: a non-negative integer, evaluated once on entering the step (settings.* are the package settings); after that the due date is computed as from a number

| Field | Type | Required | Description |
|---|---|---|---|
| `expr` | [`cel`](#schema-cel) | yes |  |

### `workhourAmount` { #schema-workhouramount }

Value: [`workhourCount`](#schema-workhourcount) or [`workingAmountExpr`](#schema-workingamountexpr).

### `workhourCount` { #schema-workhourcount }

Hours of working time by a calendar with working hours (cal.addWorkingTime)

Value: `number`.

### `workingSpan` { #schema-workingspan }

A span: an ISO 8601 duration (astronomical time), {workdays} or {workhours} by the deadline's calendar

Value: [`duration`](#schema-duration) or [object `{workdays}`](#schema-workingspan-2) or [object `{workhours}`](#schema-workingspan-3).

### `workingSpan (2)` { #schema-workingspan-2 }

| Field | Type | Required | Description |
|---|---|---|---|
| `workdays` | [`workdayAmount`](#schema-workdayamount) | yes |  |

### `workingSpan (3)` { #schema-workingspan-3 }

| Field | Type | Required | Description |
|---|---|---|---|
| `workhours` | [`workhourAmount`](#schema-workhouramount) | yes |  |

### `processTrigger` { #schema-processtrigger }

Event source: a core log event or an observation. where is a CEL filter over event

| Field | Type | Required | Description |
|---|---|---|---|
| `event` | `string` |  |  |
| `observation` | `string` |  |  |
| `source` | `string` |  |  |
| `where` | [`cel`](#schema-cel) |  |  |

Exactly one of: `event`, `observation`.

### `celMap` { #schema-celmap }

Path in instance data → CEL expression

Value: map → [`cel`](#schema-cel).

### `blocks` { #schema-blocks }

A sequence of steps (a do block)

Value: array of [`processStep`](#schema-processstep).

### `processStep` { #schema-processstep }

Process step: exactly one kind (human, approve, call, decide, recall, remember, listen, wait, set, raise, compensate, fork, try, do, suspend, resume, complete) plus common fields

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | yes |  |
| `displayName` | [`displayName`](#schema-displayname) |  |  |
| `when` | [`cel`](#schema-cel) |  | Guard: the step runs only if it is true |
| `input` | [object](#schema-processstep-input) |  |  |
| `output` | [object](#schema-processstep-output) |  | Writes the step result (step.result) into instance data |
| `export` | [object](#schema-processstep-export) |  |  |
| `governedBy` | [`governedBy`](#schema-governedby) |  |  |
| `onCompensate` | [`blocks`](#schema-blocks) |  | Compensation of a completed step: runs on compensate in reverse order |
| `human` | [object](#schema-processstep-human) |  |  |
| `approve` | [object](#schema-processstep-approve) |  |  |
| `call` | [object](#schema-processstep-call) |  |  |
| `decide` | [object](#schema-processstep-decide) |  |  |
| `recall` | [object](#schema-processstep-recall) |  | A memory query through the core; the response is a log event (deterministic replay) |
| `remember` | [object](#schema-processstep-remember) |  | A write to memory as a core observation from the process identity, with a reference to the case |
| `listen` | [object](#schema-processstep-listen) |  | Waiting for the first of several events (deferred choice); timeout is a timer |
| `wait` | [`durationOrCel`](#schema-durationorcel) |  | A pause: a duration or a point in time; wait has no deadline (due), the pause itself sets the time |
| `set` | [`celMap`](#schema-celmap) |  |  |
| `raise` | [`processError`](#schema-processerror) |  |  |
| `compensate` | = `all` or array of [`processElementId`](#schema-processelementid) |  | Run onCompensate of completed steps in reverse order |
| `fork` | [object](#schema-processstep-fork) |  |  |
| `try` | [object](#schema-processstep-try) |  |  |
| `do` | [`blocks`](#schema-blocks) |  |  |
| `suspend` | [object](#schema-processstep-suspend) |  |  |
| `resume` | [object](#schema-processstep-resume) |  |  |
| `complete` | [object](#schema-processstep-complete) |  |  |

Exactly one of: `human`, `approve`, `call`, `decide`, `recall`, `remember`, `listen`, `wait`, `set`, `raise`, `compensate`, `fork`, `try`, `do`, `suspend`, `resume`, `complete`.

### `processStep.input` { #schema-processstep-input }

| Field | Type | Required | Description |
|---|---|---|---|
| `from` | [`cel`](#schema-cel) |  |  |

### `processStep.output` { #schema-processstep-output }

Writes the step result (step.result) into instance data

| Field | Type | Required | Description |
|---|---|---|---|
| `as` | [`celMap`](#schema-celmap) |  |  |

### `processStep.export` { #schema-processstep-export }

| Field | Type | Required | Description |
|---|---|---|---|
| `as` | [`celMap`](#schema-celmap) |  |  |

### `processStep.human` { #schema-processstep-human }

| Field | Type | Required | Description |
|---|---|---|---|
| `taskType` | [`typeKey`](#schema-typekey) | yes |  |
| `title` | [`cel`](#schema-cel) |  |  |
| `customFields` | map → [`cel`](#schema-cel) |  | Prefilling the fields of the created task with case data: a field of the type's fieldSchema → CEL; checked against fieldSchema on publication and on task creation, null leaves the field to a person |
| `form` | [`processForm`](#schema-processform) |  |  |
| `assign` | [`assignChain`](#schema-assignchain) | yes |  |
| `due` | [`processDue`](#schema-processdue) |  |  |
| `escalations` | array of [`escalation`](#schema-escalation) |  |  |
| `context` | [`stepContext`](#schema-stepcontext) |  |  |

### `processStep.approve` { #schema-processstep-approve }

| Field | Type | Required | Description |
|---|---|---|---|
| `taskType` | [`typeKey`](#schema-typekey) |  |  |
| `approvers` | [`assignChain`](#schema-assignchain) | yes |  |
| `mode` | `parallel` \| `sequential` |  | Default: `parallel`. |
| `quorum` | `all` \| `any` or [object `{atLeast}`](#schema-processstep-approve-quorum-2) or [object `{percent}`](#schema-processstep-approve-quorum-3) | yes |  |
| `earlyDecision` | `boolean` |  | Default: `true`. |
| `separationOfDuties` | [`cel`](#schema-cel) |  | CEL → a list of principals who must not vote; the core checks it at decision time |
| `due` | [`processDue`](#schema-processdue) |  |  |
| `onDue` | `approve` \| `reject` \| `escalate` |  |  |
| `escalations` | array of [`escalation`](#schema-escalation) |  |  |
| `context` | [`stepContext`](#schema-stepcontext) |  |  |

### `processStep.approve.quorum (2)` { #schema-processstep-approve-quorum-2 }

| Field | Type | Required | Description |
|---|---|---|---|
| `atLeast` | `integer` | yes |  |

### `processStep.approve.quorum (3)` { #schema-processstep-approve-quorum-3 }

| Field | Type | Required | Description |
|---|---|---|---|
| `percent` | `number` | yes |  |

### `processStep.call` { #schema-processstep-call }

| Field | Type | Required | Description |
|---|---|---|---|
| `skill` | `string` |  |  |
| `agent` | [`slug`](#schema-slug) |  |  |
| `process` | [`typeKey`](#schema-typekey) |  |  |
| `input` | [`celMap`](#schema-celmap) |  |  |
| `timeout` | [`durationOrCel`](#schema-durationorcel) |  |  |
| `due` | [`processDue`](#schema-processdue) |  |  |
| `context` | [`stepContext`](#schema-stepcontext) |  |  |

Exactly one of: `skill`, `agent`, `process`.

### `processStep.decide` { #schema-processstep-decide }

| Field | Type | Required | Description |
|---|---|---|---|
| `table` | [`processElementId`](#schema-processelementid) | yes |  |
| `input` | [`celMap`](#schema-celmap) |  |  |

### `processStep.recall` { #schema-processstep-recall }

A memory query through the core; the response is a log event (deterministic replay)

| Field | Type | Required | Description |
|---|---|---|---|
| `anchors` | array of [`memoryAnchor`](#schema-memoryanchor) | yes |  |
| `traverse` | [`memoryTraverse`](#schema-memorytraverse) |  |  |
| `query` | [`cel`](#schema-cel) |  | Text for semantic enrichment |
| `kinds` | array of `string` |  |  |
| `where` | [`memoryWhere`](#schema-memorywhere) |  |  |
| `limit` | `integer` |  |  |
| `timeout` | [`duration`](#schema-duration) |  |  |
| `due` | [`processDue`](#schema-processdue) |  |  |
| `onTimeout` | [`blocks`](#schema-blocks) |  |  |

### `processStep.remember` { #schema-processstep-remember }

A write to memory as a core observation from the process identity, with a reference to the case

| Field | Type | Required | Description |
|---|---|---|---|
| `entity` | [object](#schema-processstep-remember-entity) |  |  |
| `facts` | [`celMap`](#schema-celmap) |  | Case fact name → value |

Exactly one of: `facts`, `entity`.

### `processStep.remember.entity` { #schema-processstep-remember-entity }

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | `string` | yes |  |
| `key` | [`cel`](#schema-cel) | yes |  |
| `name` | [`cel`](#schema-cel) |  |  |
| `text` | [`cel`](#schema-cel) |  |  |
| `links` | array of [object](#schema-processstep-remember-entity-links-item) |  |  |

### `processStep.remember.entity.links[]` { #schema-processstep-remember-entity-links-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `rel` | `string` | yes |  |
| `kind` | `string` | yes |  |
| `key` | [`cel`](#schema-cel) | yes |  |

### `processStep.listen` { #schema-processstep-listen }

Waiting for the first of several events (deferred choice); timeout is a timer

| Field | Type | Required | Description |
|---|---|---|---|
| `any` | array of [object](#schema-processstep-listen-any-item) | yes |  |
| `timeout` | [`durationOrCel`](#schema-durationorcel) |  |  |
| `due` | [`processDue`](#schema-processdue) |  |  |
| `onTimeout` | [`blocks`](#schema-blocks) |  |  |

### `processStep.listen.any[]` { #schema-processstep-listen-any-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `on` | [`processTrigger`](#schema-processtrigger) | yes |  |
| `do` | [`blocks`](#schema-blocks) |  |  |

### `processStep.fork` { #schema-processstep-fork }

| Field | Type | Required | Description |
|---|---|---|---|
| `mode` | `all` \| `compete` |  | Default: `all`. |
| `branches` | array of [object](#schema-processstep-fork-branches-item) | yes |  |

### `processStep.fork.branches[]` { #schema-processstep-fork-branches-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | yes |  |
| `do` | [`blocks`](#schema-blocks) | yes |  |

### `processStep.try` { #schema-processstep-try }

| Field | Type | Required | Description |
|---|---|---|---|
| `do` | [`blocks`](#schema-blocks) | yes |  |
| `retry` | [object](#schema-processstep-try-retry) |  |  |
| `catch` | array of [object](#schema-processstep-try-catch-item) |  |  |

### `processStep.try.retry` { #schema-processstep-try-retry }

| Field | Type | Required | Description |
|---|---|---|---|
| `limit` | `integer` | yes |  |
| `delay` | [`duration`](#schema-duration) |  |  |
| `backoff` | `constant` \| `exponential` |  |  |
| `maxDelay` | [`duration`](#schema-duration) |  |  |
| `on` | array of `string` |  | Error types to retry; all by default |

### `processStep.try.catch[]` { #schema-processstep-try-catch-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `errors` | [object](#schema-processstep-try-catch-item-errors) |  |  |
| `as` | `string` |  |  |
| `do` | [`blocks`](#schema-blocks) | yes |  |

### `processStep.try.catch[].errors` { #schema-processstep-try-catch-item-errors }

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `string` |  |  |
| `status` | `integer` |  |  |

### `processStep.suspend` { #schema-processstep-suspend }

| Field | Type | Required | Description |
|---|---|---|---|
| `reason` | [`cel`](#schema-cel) |  |  |

### `processStep.resume` { #schema-processstep-resume }

| Field | Type | Required | Description |
|---|---|---|---|
| `reason` | [`cel`](#schema-cel) |  |  |

### `processStep.complete` { #schema-processstep-complete }

| Field | Type | Required | Description |
|---|---|---|---|
| `outcome` | `string` | yes |  |

### `processElementId` { #schema-processelementid }

Stable id of a process element: the schema layout, migration maps, the log, and the memory graph refer to it. Renaming only through the migrations map

Value: `string`.

### `governedBy` { #schema-governedby }

Knowledge base regulations that govern the element: the natural key of the memory document and, if needed, a section

Value: array of [object](#schema-governedby-item).

### `governedBy[]` { #schema-governedby-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `document` | `string` | yes |  |
| `section` | `string` |  |  |

### `processForm` { #schema-processform }

Step form: JSON Schema of the data and the JSON Forms uischema of the view

| Field | Type | Required | Description |
|---|---|---|---|
| `schema` | [`jsonSchema`](#schema-jsonschema) | yes |  |
| `uischema` | `object` |  |  |

### `escalation` { #schema-escalation }

| Field | Type | Required | Description |
|---|---|---|---|
| `after` | = `due` or [`durationOrCel`](#schema-durationorcel) | yes | due: at the deadline; a duration: after the deadline |
| `action` | `remind` \| `reassign` \| `notify` \| `raise` | yes |  |
| `to` | [`assignChain`](#schema-assignchain) |  |  |
| `error` | [`processError`](#schema-processerror) |  |  |

### `processError` { #schema-processerror }

An error in RFC 7807 form

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `string` | yes |  |
| `status` | `integer` |  |  |
| `detail` | [`cel`](#schema-cel) |  |  |

### `stepContext` { #schema-stepcontext }

Context profile of the step executor from memory: explicit links first, semantic enrichment marked inferred

| Field | Type | Required | Description |
|---|---|---|---|
| `anchors` | array of [`memoryAnchor`](#schema-memoryanchor) | yes |  |
| `traverse` | [`memoryTraverse`](#schema-memorytraverse) |  |  |
| `semantic` | `boolean` |  | Semantic enrichment (inferred); true by default |
| `budgetTokens` | `integer` |  |  |

### `memoryAnchor` { #schema-memoryanchor }

Graph traversal anchor: the instance's case node or an entity by natural key (CEL over data)

| Field | Type | Required | Description |
|---|---|---|---|
| `case` | = `true` |  |  |
| `kind` | `string` |  |  |
| `key` | [`cel`](#schema-cel) |  |  |
| `via` | `string` |  |  |

Exactly one of: `case`, `key` + `kind`.

### `memoryTraverse` { #schema-memorytraverse }

Traversal steps from anchors: the same form as traverse in contextSchema

Value: array of [object](#schema-memorytraverse-item).

### `memoryTraverse[]` { #schema-memorytraverse-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `relation` | `string` | yes |  |
| `direction` | `in` \| `out` \| `both` |  |  |
| `depth` | `integer` |  |  |
| `limit` | `integer` |  |  |
| `from` | `anchors` \| `previous` |  |  |

### `memoryWhere` { #schema-memorywhere }

Filters on node attributes: applied to the result nodes and to the candidate anchors of semantic enrichment; conditions are combined with AND

Value: array of [object](#schema-memorywhere-item).

### `memoryWhere[]` { #schema-memorywhere-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `attr` | `string` | yes | Node attribute name (flat), for example okpd2 or validUntil; a list attribute satisfies the condition if at least one of its elements does |
| `op` | `eq` \| `in` \| `prefix` \| `lte` \| `gte` \| `exists` | yes | prefix compares codes by dot-separated segments: 62.01 matches 62.01.11 but not 62.011; lte/gte take RFC 3339 dates or numbers |
| `value` | [`cel`](#schema-cel) or `number` \| `boolean` or array of [`cel`](#schema-cel) |  | A CEL expression over the instance data (a string literal goes in CEL quotes: "'62.01'"); for in, a CEL list or a list of expressions; for exists, true or false |

Conditions:

| Condition | Consequence |
|---|---|
| `op` ≠ `exists` | `value` required |

### `processStage` { #schema-processstage }

Case stage (CMMN): entry and exit by guards, milestones, required and discretionary work

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | yes |  |
| `displayName` | [`displayName`](#schema-displayname) |  |  |
| `entry` | [`cel`](#schema-cel) |  | Entry guard; stage.&lt;id&gt;.completed, milestone.&lt;id&gt;, and data are available in the expression |
| `exit` | [`cel`](#schema-cel) |  |  |
| `repeatable` | `boolean` |  |  |
| `governedBy` | [`governedBy`](#schema-governedby) |  |  |
| `steps` | [`blocks`](#schema-blocks) | yes |  |
| `discretionary` | array of [`processStep`](#schema-processstep) |  | Work that a human adds at their discretion |
| `milestones` | array of [object](#schema-processstage-milestones-item) |  |  |
| `timers` | [`processTimers`](#schema-processtimers) |  |  |

### `processStage.milestones[]` { #schema-processstage-milestones-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | yes |  |
| `when` | [`cel`](#schema-cel) | yes |  |

### `processTimers` { #schema-processtimers }

Boundary timers: fire while the stage (process) is open; an at derived from data is recalculated when the data changes

Value: array of [object](#schema-processtimers-item).

### `processTimers[]` { #schema-processtimers-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | yes |  |
| `at` | [`durationOrCel`](#schema-durationorcel) | yes |  |
| `interrupting` | `boolean` |  | Default: `false`. |
| `do` | [`blocks`](#schema-blocks) | yes |  |

### `decisionTable` { #schema-decisiontable }

Decision table (DMN in spirit). Condition cell: '-' (any), a literal, a list 'a,b', a range '[a..b)'

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | yes |  |
| `displayName` | [`displayName`](#schema-displayname) |  |  |
| `hitPolicy` | `first` \| `unique` \| `collect` | yes |  |
| `governedBy` | [`governedBy`](#schema-governedby) |  |  |
| `inputs` | array of [object](#schema-decisiontable-inputs-item) | yes |  |
| `outputs` | array of [object](#schema-decisiontable-outputs-item) | yes |  |
| `rules` | array of [object](#schema-decisiontable-rules-item) | yes |  |

### `decisionTable.inputs[]` { #schema-decisiontable-inputs-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | yes |  |
| `expr` | [`cel`](#schema-cel) | yes |  |
| `type` | `string` \| `number` \| `boolean` \| `date` \| `timestamp` |  |  |

### `decisionTable.outputs[]` { #schema-decisiontable-outputs-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | [`processElementId`](#schema-processelementid) | yes |  |
| `type` | `string` \| `number` \| `boolean` \| `date` \| `duration` \| `object` \| `array` |  |  |

### `decisionTable.rules[]` { #schema-decisiontable-rules-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `when` | map → `string` \| `number` \| `boolean` | yes |  |
| `then` | `object` | yes |  |
| `note` | `string` |  |  |
| `governedBy` | [`governedBy`](#schema-governedby) |  |  |

### `memoryProjection` { #schema-memoryprojection }

Projection of the case into the memory graph: delivered by events; only declared fields go into the graph

| Field | Type | Required | Description |
|---|---|---|---|
| `case` | [object](#schema-memoryprojection-case) | yes |  |
| `facts` | [`celMap`](#schema-celmap) |  | Case fact name → value; a change closes the previous fact with a validity period |
| `entities` | array of [object](#schema-memoryprojection-entities-item) |  |  |
| `documents` | [object](#schema-memoryprojection-documents) |  |  |

### `memoryProjection.case` { #schema-memoryprojection-case }

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | `string` |  | Default: `case`. |
| `key` | [`cel`](#schema-cel) | yes |  |
| `title` | [`cel`](#schema-cel) |  |  |

### `memoryProjection.entities[]` { #schema-memoryprojection-entities-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | `string` | yes |  |
| `key` | [`cel`](#schema-cel) | yes |  |
| `name` | [`cel`](#schema-cel) |  |  |
| `rel` | `string` | yes |  |
| `when` | [`cel`](#schema-cel) |  |  |
| `many` | `boolean` |  | key yields a list: one entity per element |

### `memoryProjection.documents` { #schema-memoryprojection-documents }

| Field | Type | Required | Description |
|---|---|---|---|
| `artifacts` | array of [`typeKey`](#schema-typekey) |  |  |
<!-- /generated:schema-process -->

## Calendar (`kind: Calendar`) { #calendar }

<!-- generated:schema-calendar -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/object.schema.json`.

### `calendarSpec` { #schema-calendarspec }

Business calendar: default weekend, holidays, and moved days by year

| Field | Type | Required | Description |
|---|---|---|---|
| `displayName` | [`displayName`](#schema-displayname) | yes |  |
| `timezone` | `string` | yes |  |
| `weekend` | array of `integer` |  | ISO weekdays: 1 is Monday. Default: `[6, 7]`. |
| `workingHours` | [object](#schema-calendarspec-workinghours) |  | Working hours on the calendar's working days, in the calendar's local time. Without the field, the calendar knows only working days |
| `years` | array of [object](#schema-calendarspec-years-item) | yes |  |

### `calendarSpec.workingHours` { #schema-calendarspec-workinghours }

Working hours on the calendar's working days, in the calendar's local time. Without the field, the calendar knows only working days

| Field | Type | Required | Description |
|---|---|---|---|
| `intervals` | [`workingIntervals`](#schema-workingintervals) | yes | Intervals of a regular working day |
| `weekdays` | map → [`workingIntervals`](#schema-workingintervals) |  | Intervals per ISO weekday (1 is Monday) instead of intervals; [] means no working hours |
| `shortDayReduction` | [`duration`](#schema-duration) |  | How much shorter a short day (shortDays) is: subtracted from the end of the last interval |

### `calendarSpec.years[]` { #schema-calendarspec-years-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `year` | `integer` | yes |  |
| `provisional` | `boolean` |  | The year is not approved yet: cal.* results are marked "provisional" |
| `source` | `string` |  |  |
| `holidays` | array of `string` (date) |  |  |
| `workdays` | array of `string` (date) |  | Moved working days that fall on weekends |
| `shortDays` | array of `string` (date) |  |  |

### `workingIntervals` { #schema-workingintervals }

Intervals of a day's working time, in order and without overlaps, from earlier than to (the core checks the order); 24:00 is the end of the day

Value: array of [object](#schema-workingintervals-item).

### `workingIntervals[]` { #schema-workingintervals-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `from` | `string` | yes |  |
| `to` | `string` | yes |  |
<!-- /generated:schema-calendar -->

## Ontology (`kind: KnowledgePack`) { #knowledge-pack }

The ontology body is described by a separate schema file, `knowledge-pack.schema.json`; in a package, an integer version `version` is added to it.

<!-- generated:schema-knowledge-pack -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/object.schema.json`, `sdk/package-sdk/schema/v1/knowledge-pack.schema.json`.

### `KnowledgePack.spec` { #schema-knowledgepack-spec }

Includes [`knowledge-pack`](#schema-knowledge-pack).

| Field | Type | Required | Description |
|---|---|---|---|
| `version` | `integer` |  | Version of the ontology in the package, an integer: enablement refers to it as name@version, and an edit is a new version |

### `knowledge-pack` { #schema-knowledge-pack }

Form of a package of knowledge base kinds and relations. The package is registered through the core (POST /api/v1/knowledge/packs) and enabled for a workspace tree. memory-service parses name, version, scope, namespace, kinds (kind, kindAliases, aliases, naturalKey, idPatterns, attributes, searchable) and relations; the other fields are data for the loaders and the import template generator, and memory skips them.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | yes | Package name without a prefix. A reference to a tenant package in the namespace settings is tenant:&lt;name&gt;@&lt;version&gt; |
| `version` | `string` \| `integer` | yes | Package version; kind templates are versioned by it |
| `scope` | `common` \| `tenant` |  | common: a shared package, registered by a platform administrator; tenant: a tenant package, under the knowledge.packs.manage permission: visible and enabled only in the owner namespace and below it, and the names of the package, its kinds, and relations do not coincide with the common ones. Default: `common`. |
| `namespace` | `string` |  | Owner namespace of a tenant package (scope: tenant); on registration through the core, the core fills it in from the workspace |
| `description` | `string` |  |  |
| `extends` | array of `string` |  | Packages whose kinds the relations and profiles of this package refer to (for example company@1). The base package does not change |
| `kinds` | array of [`knowledge-pack/kind`](#schema-knowledge-pack-kind) | yes |  |
| `relations` | array of [`knowledge-pack/relation`](#schema-knowledge-pack-relation) |  |  |
| `profiles` | array of [`knowledge-pack/profile`](#schema-knowledge-pack-profile) |  | Attribute profiles of kinds, including kinds of other packages: this is how a package describes attributes of another package's kind without changing or redeclaring it (credential with type: sro_membership in an industry extension, legal_entity of the default package in company). Checked by the loaders and the template generator |
| `expiry` | array of [`knowledge-pack/expiry`](#schema-knowledge-pack-expiry) |  | Who gets a task about the expiry of a kind's validUntil and how many days ahead (the knowledge-expiry rule). Without an entry: the knowledge base owner role and 30 days |

### `knowledge-pack/kind` { #schema-knowledge-pack-kind }

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | [`knowledge-pack/name`](#schema-knowledge-pack-name) | yes |  |
| `title` | `string` |  | Human-readable kind name: the heading of the template and of the console section |
| `description` | `string` |  |  |
| `kindAliases` | array of [`knowledge-pack/name`](#schema-knowledge-pack-name) |  |  |
| `aliases` | array of `string` |  |  |
| `naturalKey` | `string` or `object` |  | Form of the natural key: a template with placeholders ("offering:&lt;source&gt;:&lt;id&gt;") or a JSON Schema of a string |
| `idPatterns` | array of `string` |  |  |
| `attributes` | [`knowledge-pack/attributes`](#schema-knowledge-pack-attributes) |  |  |
| `searchable` | [object](#schema-knowledge-pack-kind-searchable) |  | The kind is found by semantic search: reconciliation indexes an embedding of the entity title and the values of the listed attributes; each attribute is declared in attributes.properties |

### `knowledge-pack/kind.searchable` { #schema-knowledge-pack-kind-searchable }

The kind is found by semantic search: reconciliation indexes an embedding of the entity title and the values of the listed attributes; each attribute is declared in attributes.properties

| Field | Type | Required | Description |
|---|---|---|---|
| `fields` | array of `string` | yes |  |

### `knowledge-pack/name` { #schema-knowledge-pack-name }

Value: `string`.

### `knowledge-pack/attributes` { #schema-knowledge-pack-attributes }

JSON Schema of the kind's attributes (draft 2020-12). The title and description of a property are the header and hint of the template column; type, format, enum are validation; required is mandatory presence. Validity periods follow the validFrom and validUntil convention (format: date). A property with personal data of an individual is allowed only with x-personal-data: allowed; such values do not get into AI prompts

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | = `object` |  |  |
| `properties` | [object](#schema-knowledge-pack-attributes-properties) |  |  |

### `knowledge-pack/attributes.properties` { #schema-knowledge-pack-attributes-properties }

| Field | Type | Required | Description |
|---|---|---|---|
| `validFrom` | [`knowledge-pack/dateProperty`](#schema-knowledge-pack-dateproperty) |  |  |
| `validUntil` | [`knowledge-pack/dateProperty`](#schema-knowledge-pack-dateproperty) |  |  |

### `knowledge-pack/dateProperty` { #schema-knowledge-pack-dateproperty }

Validity period convention: validFrom and validUntil are an ISO 8601 day

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | = `string` | yes |  |
| `format` | = `date` | yes |  |

### `knowledge-pack/relation` { #schema-knowledge-pack-relation }

| Field | Type | Required | Description |
|---|---|---|---|
| `relation` | [`knowledge-pack/name`](#schema-knowledge-pack-name) | yes |  |
| `title` | `string` |  | Header of the relation column in the template |
| `fromKinds` | array of [`knowledge-pack/name`](#schema-knowledge-pack-name) |  |  |
| `toKinds` | array of [`knowledge-pack/name`](#schema-knowledge-pack-name) |  |  |
| `temporal` | `boolean` |  | Default: `true`. |
| `cardinality` | `one` \| `many` |  | Default: `many`. |

### `knowledge-pack/profile` { #schema-knowledge-pack-profile }

Attributes of a kind of this or another package. With when: on entities where the attribute equals the value (credential with type: sro_membership); without when: on all entities of the kind (attributes of legal_entity of the default package)

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | [`knowledge-pack/name`](#schema-knowledge-pack-name) | yes |  |
| `when` | [object](#schema-knowledge-pack-profile-when) |  |  |
| `title` | `string` |  |  |
| `attributes` | [`knowledge-pack/attributes`](#schema-knowledge-pack-attributes) | yes |  |

### `knowledge-pack/profile.when` { #schema-knowledge-pack-profile-when }

| Field | Type | Required | Description |
|---|---|---|---|
| `attr` | `string` | yes |  |
| `equals` | `string` \| `number` \| `boolean` | yes |  |

### `knowledge-pack/expiry` { #schema-knowledge-pack-expiry }

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | [`knowledge-pack/name`](#schema-knowledge-pack-name) | yes |  |
| `role` | `string` |  | Role that gets the task |
| `leadDays` | `integer` |  |  |
<!-- /generated:schema-knowledge-pack -->

## Common types { #common }

Definitions referenced by several kinds.

<!-- generated:schema-common -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/object.schema.json`.

### `connectionKey` { #schema-connectionkey }

Key of a connection type or of a connection

Value: `string`.

### `displayName` { #schema-displayname }

Value: `string`.

### `duration` { #schema-duration }

An ISO 8601 duration, for example P3D, PT4H

Value: `string`.

### `envOrUuid` { #schema-envoruuid }

A UUID or an installation ${VARIABLE} (the environment topology is not written into the package)

Value: `string`.

### `jsonSchema` { #schema-jsonschema }

JSON Schema of a document (draft 2020-12). The core rejects remote $ref.

Value: `object`.

### `lifecycle` { #schema-lifecycle }

| Field | Type | Required | Description |
|---|---|---|---|
| `statuses` | array of [object](#schema-lifecycle-statuses-item) | yes |  |
| `transitions` | array of [object](#schema-lifecycle-transitions-item) |  |  |
| `initialStatus` | [`statusKey`](#schema-statuskey) |  |  |

### `lifecycle.statuses[]` { #schema-lifecycle-statuses-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `key` | [`statusKey`](#schema-statuskey) | yes |  |
| `category` | `string` | yes |  |
| `displayName` | `string` |  |  |

### `lifecycle.transitions[]` { #schema-lifecycle-transitions-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `from` | [`statusKey`](#schema-statuskey) | yes |  |
| `to` | array of [`statusKey`](#schema-statuskey) | yes |  |

### `mediaType` { #schema-mediatype }

A lowercase media type; a */* or type/* mask is allowed

Value: `string`.

### `ruleKey` { #schema-rulekey }

Rule key within a tenant

Value: `string`.

### `slug` { #schema-slug }

Value: `string`.

### `statusKey` { #schema-statuskey }

Value: `string`.

### `typeKey` { #schema-typekey }

Type key: lowercase Latin letters, digits, _ and -

Value: `string`.
<!-- /generated:schema-common -->

## Package test (`tests/*.test.yaml`) { #test-file }

<!-- generated:schema-test -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/test.schema.json`.

### `test` { #schema-test }

A &lt;name&gt;.test.yaml file in the package's tests/ directory. The core runs it (POST /packages:test) with the same engine as a live run, in a sandbox: tasks, approvals, and timers are in memory; skills, agents, and memory are stubs checked against the catalog schemas; time is virtual. There are no side effects.

| Field | Type | Required | Description |
|---|---|---|---|
| `$schema` | `string` |  |  |
| `process` | `string` |  | Key of the package process |
| `version` | `integer` |  | Defaults to the version in the package |
| `name` | `string` | yes |  |
| `description` | `string` |  |  |
| `subject` | `process` \| `rule` \| `taskType` |  | What the test checks: a process (the default), a work rule, or a task type (gate outcomes, acceptance criteria, completion actions). Default: `process`. |
| `rule` | `string` |  | Key of the package WorkRule (subject: rule) |
| `taskType` | `string` |  | Key of the package TaskType (subject: taskType) |
| `given` | `object` |  |  |
| `mocks` | [object](#schema-test-mocks) |  |  |
| `steps` | array of `object` | yes |  |
| `coverage` | [object](#schema-test-coverage) |  |  |

Conditions:

| Condition | Consequence |
|---|---|
| not (`subject` ∈ `rule`, `taskType`) | `process` required; `given`: [`processGiven`](#schema-processgiven); `steps`: array of [`testStep`](#schema-teststep) |
| `subject` = `rule` | `rule` required; `given`: [`ruleGiven`](#schema-rulegiven); `steps`: array of [`ruleStep`](#schema-rulestep) |
| `subject` = `taskType` | `taskType` required; `given`: [`taskTypeGiven`](#schema-tasktypegiven); `steps`: array of [`taskTypeStep`](#schema-tasktypestep) |

### `test.mocks` { #schema-test-mocks }

| Field | Type | Required | Description |
|---|---|---|---|
| `skills` | map → array of [`mockAnswer`](#schema-mockanswer) |  | name@version → answers in call order (or by when); the output is checked against the skill schema from the catalog |
| `agents` | map → array of [`mockAnswer`](#schema-mockanswer) |  |  |
| `recall` | array of [`mockAnswer`](#schema-mockanswer) |  | Memory answers to recall steps; step is the step id, when is CEL over the query |

### `test.coverage` { #schema-test-coverage }

| Field | Type | Required | Description |
|---|---|---|---|
| `minimum` | `number` |  | Coverage threshold of process elements by this test, % |

### `mockAnswer` { #schema-mockanswer }

| Field | Type | Required | Description |
|---|---|---|---|
| `step` | `string` |  |  |
| `when` | `string` |  | CEL over the call input |
| `output` | any |  |  |
| `error` | [object](#schema-mockanswer-error) |  |  |
| `timeout` | = `true` |  |  |

Exactly one of: `output`, `error`, `timeout`.

### `mockAnswer.error` { #schema-mockanswer-error }

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `string` | yes |  |
| `status` | `integer` |  |  |
| `detail` | `string` |  |  |

### `processGiven` { #schema-processgiven }

| Field | Type | Required | Description |
|---|---|---|---|
| `clock` | `string` (date-time) |  | Initial virtual time |
| `data` | `object` |  | Initial instance data (without a start event) |
| `stage` | `string` |  | Start with an open stage |
| `fromInstance` | `string` |  | Only a trial run on a deployment: state is copied from a live instance |
| `calendar` | `string` |  | Calendar key instead of the process calendar |
| `settings` | [`settings`](#schema-settings) |  |  |
| `principals` | map → array of `string` |  | Role → fictitious test principals (for assignments and separation of duties) |

### `settings` { #schema-settings }

Saved package settings values, as an administrator saves them: they replace the previously saved values, fields not given take their default from spec.settings of the manifest. The core checks them against the settings schema of the package

Value: `object`.

### `testStep` { #schema-teststep }

| Field | Type | Required | Description |
|---|---|---|---|
| `settings` | [`settings`](#schema-settings) |  | Save new settings values in the middle of the scenario: computations after this step read them, decisions already taken keep the values they read |
| `emit` | [object](#schema-teststep-emit) |  |  |
| `advance` | `string` |  | Advance virtual time (ISO 8601, P3D) or up to a moment: until:&lt;timer id&gt; |
| `complete` | [object](#schema-teststep-complete) |  |  |
| `approve` | [object](#schema-teststep-approve) |  |  |
| `expect` | [object](#schema-teststep-expect) |  |  |

Exactly one of: `emit`, `advance`, `complete`, `approve`, `expect`, `settings`.

### `testStep.emit` { #schema-teststep-emit }

| Field | Type | Required | Description |
|---|---|---|---|
| `event` | `string` |  |  |
| `observation` | `string` |  |  |
| `source` | `string` |  |  |
| `task` | `string` |  | Only with observation: id of the process step whose latest task the observation is bound to (the task field of the core's observation) |
| `by` | `string` |  | Author of the event (actorId): a test principal or agent:&lt;key&gt; |
| `payload` | `object` |  |  |

Exactly one of: `event`, `observation`.

### `testStep.complete` { #schema-teststep-complete }

| Field | Type | Required | Description |
|---|---|---|---|
| `step` | `string` | yes |  |
| `by` | `string` |  | a test principal or agent:&lt;key&gt; |
| `output` | `object` |  | Form data or the agent result; checked against the form schema |
| `cancel` | = `true` |  |  |

### `testStep.approve` { #schema-teststep-approve }

| Field | Type | Required | Description |
|---|---|---|---|
| `step` | `string` | yes |  |
| `by` | `string` | yes |  |
| `decision` | `approve` \| `reject` | yes |  |
| `expectRefused` | `string` |  | Core denial code, for example separation_of_duties_violation |

### `testStep.expect` { #schema-teststep-expect }

| Field | Type | Required | Description |
|---|---|---|---|
| `stages` | map → `open` \| `completed` \| `skipped` \| `not_started` |  |  |
| `milestones` | array of `string` |  |  |
| `tasks` | array of [object](#schema-teststep-expect-tasks-item) |  |  |
| `timers` | array of [object](#schema-teststep-expect-timers-item) |  |  |
| `data` | `object` |  | Path in data → expected value |
| `sla` | map → `ok` \| `warning` \| `breached` \| `paused` |  | Deadline state: step id → state of its open attempt; the process key is the deadline of the process (spec.due) |
| `events` | array of `string` |  | Types of process.* events since the last expect |
| `rules` | array of [object](#schema-teststep-expect-rules-item) |  | Decisions of the package's rules with target: task since the last expect |
| `memory` | [object](#schema-teststep-expect-memory) |  |  |
| `outcome` | `string` |  |  |
| `status` | `running` \| `suspended` \| `completed` \| `failed` \| `cancelled` |  |  |
| `error` | `string` |  |  |
| `noSideEffects` | = `true` |  |  |

### `testStep.expect.tasks[]` { #schema-teststep-expect-tasks-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `step` | `string` |  |  |
| `status` | `string` |  |  |
| `assignee` | `string` |  |  |
| `due` | `string` |  |  |
| `customFields` | `object` |  | A subset of the task's fields: the ones given are compared (prefilling of the human step) |

### `testStep.expect.timers[]` { #schema-teststep-expect-timers-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `string` |  |  |
| `at` | `string` |  |  |
| `provisional` | `boolean` |  |  |

### `testStep.expect.rules[]` { #schema-teststep-expect-rules-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `rule` | `string` |  |  |
| `action` | `string` |  |  |
| `step` | `string` |  |  |
| `result` | `matched` \| `not_matched` \| `skipped` \| `failed` |  |  |
| `reason` | `string` |  |  |

### `testStep.expect.memory` { #schema-teststep-expect-memory }

| Field | Type | Required | Description |
|---|---|---|---|
| `recalled` | array of `string` |  |  |
| `remembered` | array of `object` |  |  |

### `ruleGiven` { #schema-rulegiven }

| Field | Type | Required | Description |
|---|---|---|---|
| `clock` | `string` (date-time) |  |  |
| `variables` | [`variables`](#schema-variables) |  |  |
| `settings` | [`settings`](#schema-settings) |  |  |
| `task` | [object](#schema-rulegiven-task) |  | A task created before the input: an event without taskId in the payload is about it |
| `schedule` | [object](#schema-rulegiven-schedule) |  | The input is a firing of the rule's schedule (trigger.kind: schedule) |
| `observation` | [object](#schema-rulegiven-observation) |  |  |
| `event` | [object](#schema-rulegiven-event) |  |  |

Exactly one of: `observation`, `event`, `schedule`.

### `ruleGiven.task` { #schema-rulegiven-task }

A task created before the input: an event without taskId in the payload is about it

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `string` | yes | Key of a task type of the package or the tenant |
| `title` | `string` |  |  |
| `status` | `string` |  |  |
| `assignee` | `string` |  | agent:&lt;key&gt; or a fictitious principal |
| `customFields` | `object` |  |  |

### `ruleGiven.schedule` { #schema-rulegiven-schedule }

The input is a firing of the rule's schedule (trigger.kind: schedule)

| Field | Type | Required | Description |
|---|---|---|---|
| `at` | `string` (date-time) |  | Time of the slot; clock by default |

### `ruleGiven.observation` { #schema-rulegiven-observation }

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | `string` | yes |  |
| `data` | `object` |  |  |
| `content` | `string` |  |  |
| `source` | `string` |  |  |
| `externalRef` | `object` |  |  |

### `ruleGiven.event` { #schema-rulegiven-event }

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `string` | yes |  |
| `payload` | `object` |  |  |

### `variables` { #schema-variables }

Values of installation variables for the test; the others take the default from the manifest

Value: map → `string`.

### `ruleStep` { #schema-rulestep }

| Field | Type | Required | Description |
|---|---|---|---|
| `expect` | [object](#schema-rulestep-expect) | yes |  |

### `ruleStep.expect` { #schema-rulestep-expect }

| Field | Type | Required | Description |
|---|---|---|---|
| `result` | `string` |  | Result of the core's rule evaluation (as result of the rule.evaluated event) |
| `ensureWork` | array of [`workExpectation`](#schema-workexpectation) |  |  |
| `invokeSkill` | array of [`skillExpectation`](#schema-skillexpectation) |  |  |
| `noSideEffects` | = `true` |  |  |

### `workExpectation` { #schema-workexpectation }

Expected work: the fields that are set are compared, the ones not set are not checked

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `string` |  |  |
| `title` | `string` |  |  |
| `assignee` | `string` |  | agent:&lt;key&gt;, a test role, or a fictitious principal |
| `customFields` | `object` |  |  |
| `relation` | `object` |  |  |

### `skillExpectation` { #schema-skillexpectation }

| Field | Type | Required | Description |
|---|---|---|---|
| `skill` | `string` | yes |  |
| `inputs` | `object` |  | A subset of the call input |

### `taskTypeGiven` { #schema-tasktypegiven }

| Field | Type | Required | Description |
|---|---|---|---|
| `clock` | `string` (date-time) |  |  |
| `variables` | [`variables`](#schema-variables) |  |  |
| `task` | [object](#schema-tasktypegiven-task) |  |  |
| `artifacts` | array of [object](#schema-tasktypegiven-artifacts-item) |  |  |
| `principals` | map → array of `string` |  | Role → fictitious test principals |

### `taskTypeGiven.task` { #schema-tasktypegiven-task }

| Field | Type | Required | Description |
|---|---|---|---|
| `title` | `string` |  |  |
| `status` | `string` |  |  |
| `assignee` | `string` |  |  |
| `customFields` | `object` |  |  |

### `taskTypeGiven.artifacts[]` { #schema-tasktypegiven-artifacts-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `key` | `string` |  |  |
| `type` | `string` | yes |  |
| `metadata` | `object` |  |  |
| `content` | `string` |  | Content (text): an artifact with stored content, as after an upload |
| `mediaType` | `string` |  | Media type of the content (text/markdown, application/json, …) |

### `taskTypeStep` { #schema-tasktypestep }

| Field | Type | Required | Description |
|---|---|---|---|
| `approve` | [object](#schema-tasktypestep-approve) |  |  |
| `verify` | [object](#schema-tasktypestep-verify) |  | Result of an acceptance criterion of the type |
| `complete` | [object](#schema-tasktypestep-complete) |  |  |
| `expect` | [object](#schema-tasktypestep-expect) |  |  |

Exactly one of: `approve`, `verify`, `complete`, `expect`.

### `taskTypeStep.approve` { #schema-tasktypestep-approve }

| Field | Type | Required | Description |
|---|---|---|---|
| `gate` | `string` |  | Default: `default`. |
| `decision` | `approved` \| `rejected` | yes |  |
| `by` | `string` |  |  |
| `comment` | `string` |  |  |
| `expectRefused` | `string` |  | The core's refusal code to the decider, for example not_eligible: the decider does not hold the gate's role |

### `taskTypeStep.verify` { #schema-tasktypestep-verify }

Result of an acceptance criterion of the type

| Field | Type | Required | Description |
|---|---|---|---|
| `check` | `string` | yes |  |
| `result` | `passed` \| `failed` | yes |  |
| `output` | `object` |  |  |

### `taskTypeStep.complete` { #schema-tasktypestep-complete }

| Field | Type | Required | Description |
|---|---|---|---|
| `output` | `object` |  | Completion output (completionSchema) |

### `taskTypeStep.expect` { #schema-tasktypestep-expect }

| Field | Type | Required | Description |
|---|---|---|---|
| `ensureWork` | array of [`workExpectation`](#schema-workexpectation) |  |  |
| `invokeSkill` | array of [`skillExpectation`](#schema-skillexpectation) |  |  |
| `status` | [object](#schema-tasktypestep-expect-status) |  |  |
| `comments` | array of `string` |  | Substrings of comments left by outcomes |
| `noSideEffects` | = `true` |  |  |

### `taskTypeStep.expect.status` { #schema-tasktypestep-expect-status }

| Field | Type | Required | Description |
|---|---|---|---|
| `key` | `string` |  |  |
| `category` | `backlog` \| `active` \| `blocked` \| `terminal_success` \| `terminal_cancelled` |  |  |
<!-- /generated:schema-test -->

## Source lock (`packages.lock`) { #lock }

The file is written by `package-sdk lock`; it is not edited by hand.

<!-- generated:schema-lock -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/lock.schema.json`.

### `lock` { #schema-lock }

The packages.lock file next to the installation file. It is written by package-sdk lock; for each package, it holds the source, the commit, and the content hash. The plan is built from the lock: for a git source without an entry, lock_required; on a hash mismatch, a refusal.

| Field | Type | Required | Description |
|---|---|---|---|
| `format` | = `package-sdk.lock/v1` | yes |  |
| `installation` | `string` |  | Key of the installation the lock was taken for |
| `packages` | array of [object](#schema-lock-packages-item) | yes |  |

### `lock.packages[]` { #schema-lock-packages-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `key` | `string` | yes |  |
| `version` | `string` | yes |  |
| `source` | [object `{path}`](#schema-lock-packages-item-source-1) or [object `{git, ref, path}`](#schema-lock-packages-item-source-2) | yes | Where the package comes from: {path} is a directory relative to the installation file; {git, ref, path?} is a git tag and the package subdirectory in the repository (the same path name as in the installation) |
| `commit` | `string` |  | Commit of the git source |
| `contentHash` | `string` | yes | sha256 of the package's canonical set of files: paths in order and their bytes, without .layout/ (the same function as installHash of the link record) |

### `lock.packages[].source (1)` { #schema-lock-packages-item-source-1 }

| Field | Type | Required | Description |
|---|---|---|---|
| `path` | `string` | yes |  |

### `lock.packages[].source (2)` { #schema-lock-packages-item-source-2 }

| Field | Type | Required | Description |
|---|---|---|---|
| `git` | `string` | yes |  |
| `ref` | `string` | yes |  |
| `path` | `string` |  |  |
<!-- /generated:schema-lock -->

## Installation plan (`plan --out`) { #plan }

The document is written by `package-sdk plan --out`; `package-sdk apply --plan` applies it only without edits.

<!-- generated:schema-plan -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/plan.schema.json`.

### `plan` { #schema-plan }

One document with the changes of all installation kinds. It is written by package-sdk plan --out and applied only by package-sdk apply --plan, without edits: planHash is the hash of the document without the field itself, and an edited file is rejected. Variable values are not written into the plan, only their hash.

| Field | Type | Required | Description |
|---|---|---|---|
| `format` | = `package-sdk.plan/v1` | yes |  |
| `server` | `string` | yes | Deployment: https; http only for localhost |
| `engines` | map → `string` |  | Versions of the deployment components at the time of the plan (from openapi.json) |
| `createdAt` | `string` (date-time) | yes |  |
| `installation` | `string` |  | Installation key (Installation.key) |
| `install` | `string` |  | Installation file relative to the plan file: apply --plan rebuilds the packages from it and compares lockHash and variablesHash |
| `lockHash` | [`plan/hash`](#schema-plan-hash) |  |  |
| `variablesHash` | [`plan/hash`](#schema-plan-hash) |  |  |
| `overwriteConsole` | `boolean` |  | plan --overwrite-console: overwrite the fields of core objects that a human edited in the console after the previous application; without the flag the core keeps them. package-sdk plan always writes the field, false by default; a plan of the previous format without the field is applied as false. Part of planHash; the core's plan is built and applied with it too |
| `sections` | array of [`plan/section`](#schema-plan-section) | yes |  |
| `planHash` | [`plan/hash`](#schema-plan-hash) | yes |  |

### `plan/hash` { #schema-plan-hash }

Value: `string`.

### `plan/section` { #schema-plan-section }

Value: [object `{kind, changes}`](#schema-plan-section-1) or [object `{kind, package, planHash, plan, workspaceId, replayLimit}`](#schema-plan-section-2) or [object `{kind, changes}`](#schema-plan-section-3) or [object `{kind, register, enable}`](#schema-plan-section-4) or [object `{kind, items}`](#schema-plan-section-5).

### `plan/section (1)` { #schema-plan-section-1 }

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | = `catalog` | yes |  |
| `changes` | array of [`plan/change`](#schema-plan-change) | yes |  |

### `plan/section (2)` { #schema-plan-section-2 }

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | = `core` | yes |  |
| `package` | `string` | yes |  |
| `planHash` | [`plan/hash`](#schema-plan-hash) | yes |  |
| `plan` | `object` | yes | The core's /packages:plan response as is |
| `workspaceId` | `string` |  | workspaceId of the plan request; /packages:apply is sent with the same value |
| `replayLimit` | `integer` |  | replayLimit of the plan request; the core plan is rebuilt with it before applying |

### `plan/section (3)` { #schema-plan-section-3 }

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | = `notification-rules` | yes |  |
| `changes` | array of [`plan/change`](#schema-plan-change) | yes |  |

### `plan/section (4)` { #schema-plan-section-4 }

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | = `knowledge` | yes |  |
| `register` | array of [`plan/change`](#schema-plan-change) |  |  |
| `enable` | array of [object](#schema-plan-section-4-enable-item) |  |  |

### `plan/section (4).enable[]` { #schema-plan-section-4-enable-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `workspace` | `string` | yes |  |
| `packs` | array of `string` | yes |  |
| `current` | array of `string` |  |  |

### `plan/section (5)` { #schema-plan-section-5 }

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | = `retire` | yes |  |
| `items` | array of [`plan/change`](#schema-plan-change) | yes |  |

### `plan/change` { #schema-plan-change }

| Field | Type | Required | Description |
|---|---|---|---|
| `package` | `string` |  |  |
| `kind` | `string` | yes |  |
| `key` | `string` | yes |  |
| `operation` | `create` \| `version` \| `patch` \| `deprecate` \| `enable` \| `disable` \| `register` \| `retire` \| `unchanged` | yes |  |
| `fields` | array of `string` |  | Fields that change |
| `expected` | any |  | What the installer expects to see on the deployment before writing (for plan_stale) |
<!-- /generated:schema-plan -->

## Upload template refinement (`templates/<kind>.yaml`) { #knowledge-template }

<!-- generated:schema-knowledge-template -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/knowledge-template.schema.json`.

### `knowledge-template` { #schema-knowledge-template }

Optional package data templates/&lt;kind&gt;.yaml. The template is built by the generator from the kind's JSON Schema; a refinement changes only the presentation: headers, order, hints, examples, and additional forbidden columns. A refinement does not add columns that are not in the kind's schema.

| Field | Type | Required | Description |
|---|---|---|---|
| `pack` | `string` | yes | Ontology package and kind version, for example company@1 |
| `kind` | `string` | yes |  |
| `title` | `string` |  | Name of the template sheet and file |
| `instructions` | `string` |  | Text of the `Инструкция` ("Instructions") sheet before the generated column descriptions |
| `columns` | array of [object](#schema-knowledge-template-columns-item) |  | Column order; columns not listed follow in schema order |
| `examples` | array of `object` |  | Example rows of the template sheet: field → value |
| `forbiddenColumns` | array of `string` |  | Forbidden headers beyond the common list of personal data (full name, surname, passport, SNILS, date of birth, address, phone, e-mail) |

### `knowledge-template.columns[]` { #schema-knowledge-template-columns-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `field` | `string` | yes | key: the natural key; title: the name; attributes.&lt;path&gt;: an attribute; links.&lt;relation&gt;: keys of the related entities |
| `header` | `string` |  |  |
| `hint` | `string` |  |  |
| `example` | `string` \| `number` \| `boolean` |  |  |
| `separator` | `string` |  | List separator within a cell (codes, relation keys); ";" by default |
<!-- /generated:schema-knowledge-template -->

## Package screens (`kind: View`, `kind: Component`) { #view }

Package screens live in `views/*.yaml` and `components/*.yaml`. Their wrapper is
the same as for other objects; the `spec` of the `View` kind is described by
`viewSpec`, and that of the `Component` kind by `componentSpec`; screen labels are keys of the
`i18n/<locale>.yaml` dictionaries. The schema is a copy of the core's screen schema;
`package-sdk check` and `plan` validate it.

<!-- generated:schema-view -->
_This section is generated from code; do not edit it by hand._

Source: `sdk/package-sdk/schema/v1/view.schema.json`.

### `view` { #schema-view }

Screens of a package: spec of the kinds View and Component

The root has no shape of its own, only definitions; top-level ones: [`view/viewSpec`](#schema-view-viewspec), [`view/componentSpec`](#schema-view-componentspec).

### `view/viewSpec` { #schema-view-viewspec }

| Field | Type | Required | Description |
|---|---|---|---|
| `blocks` | = `1` |  | Version of the set of blocks the layout is written in |
| `title` | [`view/messageKey`](#schema-view-messagekey) | yes |  |
| `description` | [`view/messageKey`](#schema-view-messagekey) |  |  |
| `nav` | [object](#schema-view-viewspec-nav) |  |  |
| `audience` | [object](#schema-view-viewspec-audience) |  |  |
| `source` | [`view/source`](#schema-view-source) | yes |  |
| `params` | [`view/params`](#schema-view-params) |  |  |
| `layout` | [`view/layout`](#schema-view-layout) | yes |  |

### `view/viewSpec.nav` { #schema-view-viewspec-nav }

| Field | Type | Required | Description |
|---|---|---|---|
| `group` | `work` \| `knowledge` \| `packages` |  | A group of the console menu (a closed list, not a key of the dictionaries); none: packages |
| `icon` | `string` |  |  |
| `order` | `integer` |  |  |

### `view/viewSpec.audience` { #schema-view-viewspec-audience }

| Field | Type | Required | Description |
|---|---|---|---|
| `roles` | array of [`view/slug`](#schema-view-slug) | yes | Roles of the organization (slugs): a holder of one of them sees the view |

### `view/messageKey` { #schema-view-messagekey }

A key of the package dictionaries

Value: `string`.

### `view/slug` { #schema-view-slug }

Value: `string`.

### `view/source` { #schema-view-source }

Exactly one of {process, filter?}, {process, instance: param.&lt;name&gt;}, {tasks: {type}}, {knowledge: {kinds}}

| Field | Type | Required | Description |
|---|---|---|---|
| `process` | [`view/key`](#schema-view-key) |  |  |
| `filter` | [`view/expression`](#schema-view-expression) |  |  |
| `instance` | `string` |  |  |
| `tasks` | [object](#schema-view-source-tasks) |  |  |
| `knowledge` | [object](#schema-view-source-knowledge) |  |  |

### `view/source.tasks` { #schema-view-source-tasks }

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | [`view/key`](#schema-view-key) | yes |  |

### `view/source.knowledge` { #schema-view-source-knowledge }

| Field | Type | Required | Description |
|---|---|---|---|
| `kinds` | array of [`view/kind`](#schema-view-kind) | yes |  |

### `view/key` { #schema-view-key }

Value: `string`.

### `view/expression` { #schema-view-expression }

Value: `string`.

### `view/kind` { #schema-view-kind }

Value: `string`.

### `view/params` { #schema-view-params }

Value: map → [`view/param`](#schema-view-param).

### `view/name` { #schema-view-name }

Value: `string`.

### `view/param` { #schema-view-param }

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | `string` \| `integer` \| `number` \| `boolean` \| `date` \| `datetime` \| `uuid` | yes |  |
| `required` | `boolean` |  |  |

### `view/layout` { #schema-view-layout }

Value: array of [`view/block`](#schema-view-block).

### `view/block` { #schema-view-block }

A block of the closed set of version 1, named by the key block

| Field | Type | Required | Description |
|---|---|---|---|
| `block` | `table` \| `board` \| `list` \| `header` \| `fields` \| `timeline` \| `artifacts` \| `related` \| `metrics` \| `chart` \| `steps` \| `invoke` \| `component` | yes |  |

Conditions:

| Condition | Consequence |
|---|---|
| `block` ∈ `table`, `list` | required `columns`; `title`: [`view/messageKey`](#schema-view-messagekey); `columns`: [`view/columns`](#schema-view-columns); `open`: [`view/open`](#schema-view-open); `filters`: [`view/paths`](#schema-view-paths); `sort`: [`view/sort`](#schema-view-sort); `pageSize`: `integer` |
| `block` = `board` | required `columns`, `card`; `title`: [`view/messageKey`](#schema-view-messagekey); `columns`: = `stages`; `card`: [`view/card`](#schema-view-card); `open`: [`view/open`](#schema-view-open); `filters`: [`view/paths`](#schema-view-paths) |
| `block` = `header` | required `title`; `title`: [`view/path`](#schema-view-path); `status`: [`view/path`](#schema-view-path); `actions`: `steps` |
| `block` = `fields` | required `items`; `title`: [`view/messageKey`](#schema-view-messagekey); `section`: [`view/messageKey`](#schema-view-messagekey); `items`: [`view/columns`](#schema-view-columns) |
| `block` ∈ `timeline`, `steps` | `title`: [`view/messageKey`](#schema-view-messagekey) |
| `block` = `artifacts` | `title`: [`view/messageKey`](#schema-view-messagekey); `types`: array of [`view/key`](#schema-view-key) |
| `block` = `related` | required `knowledge`; `title`: [`view/messageKey`](#schema-view-messagekey); `knowledge`: [object](#schema-view-block-knowledge); `include`: [`view/include`](#schema-view-include) |
| `block` = `metrics` | required `items`; `title`: [`view/messageKey`](#schema-view-messagekey); `items`: array of [object](#schema-view-block-items-item) |
| `block` = `chart` | required `chart`, `groupBy`, `value`; `title`: [`view/messageKey`](#schema-view-messagekey); `chart`: `bar` \| `line` \| `donut`; `groupBy`: [`view/path`](#schema-view-path); `value`: [`view/expression`](#schema-view-expression); `label`: [`view/messageKey`](#schema-view-messagekey); `format`: [`view/format`](#schema-view-format) |
| `block` = `invoke` | required `label`, `skill`; `title`: [`view/messageKey`](#schema-view-messagekey); `label`: [`view/messageKey`](#schema-view-messagekey); `skill`: `string`; `input`: [`view/arguments`](#schema-view-arguments) |
| `block` = `component` | required `component`; `component`: [`view/key`](#schema-view-key); `with`: [`view/arguments`](#schema-view-arguments) |

### `view/block.knowledge` { #schema-view-block-knowledge }

The record of knowledge the block starts from: its kind and a CEL expression of its key

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | [`view/kind`](#schema-view-kind) | yes |  |
| `key` | [`view/expression`](#schema-view-expression) | yes |  |

### `view/block.items[]` { #schema-view-block-items-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `key` | [`view/columnKey`](#schema-view-columnkey) |  |  |
| `title` | [`view/messageKey`](#schema-view-messagekey) | yes |  |
| `value` | [`view/expression`](#schema-view-expression) | yes |  |
| `format` | [`view/format`](#schema-view-format) |  |  |

### `view/columns` { #schema-view-columns }

Value: array of [`view/column`](#schema-view-column).

### `view/column` { #schema-view-column }

What a cell shows: a path of the source (field) or a CEL expression (value), exactly one; label: none — the key &lt;package&gt;.fields.&lt;path&gt; of the dictionaries; key: none — the path

| Field | Type | Required | Description |
|---|---|---|---|
| `key` | [`view/columnKey`](#schema-view-columnkey) |  |  |
| `label` | [`view/messageKey`](#schema-view-messagekey) |  |  |
| `field` | [`view/path`](#schema-view-path) |  |  |
| `value` | [`view/expression`](#schema-view-expression) |  |  |
| `format` | [`view/format`](#schema-view-format) |  |  |

### `view/columnKey` { #schema-view-columnkey }

The key the values of a column come by in the data of a view

Value: `string`.

### `view/path` { #schema-view-path }

Value: `string`.

### `view/format` { #schema-view-format }

Value: `text` \| `number` \| `money` \| `percent` \| `date` \| `datetime` \| `due` \| `duration` \| `principal` \| `status` \| `link`.

### `view/open` { #schema-view-open }

A view of the same package or of a package it requires: id — CEL of the id of the record it opens, params — CEL of its params

| Field | Type | Required | Description |
|---|---|---|---|
| `view` | [`view/key`](#schema-view-key) | yes |  |
| `id` | [`view/expression`](#schema-view-expression) |  |  |
| `params` | [`view/arguments`](#schema-view-arguments) |  |  |

### `view/arguments` { #schema-view-arguments }

Value: map → [`view/expression`](#schema-view-expression).

### `view/paths` { #schema-view-paths }

Value: array of [`view/path`](#schema-view-path).

### `view/sort` { #schema-view-sort }

Value: array of [object](#schema-view-sort-item).

### `view/sort[]` { #schema-view-sort-item }

| Field | Type | Required | Description |
|---|---|---|---|
| `field` | [`view/path`](#schema-view-path) | yes |  |
| `dir` | `asc` \| `desc` |  |  |

### `view/card` { #schema-view-card }

A card of a board: paths of the source for its title, subtitle and badge, and its fields

| Field | Type | Required | Description |
|---|---|---|---|
| `title` | [`view/path`](#schema-view-path) | yes |  |
| `subtitle` | [`view/path`](#schema-view-path) |  |  |
| `fields` | [`view/columns`](#schema-view-columns) |  |  |
| `badge` | [`view/path`](#schema-view-path) |  |  |

### `view/include` { #schema-view-include }

The links of the record shown: the include of POST /knowledge/entities:query

| Field | Type | Required | Description |
|---|---|---|---|
| `relations` | = `*` or array of `string` | yes | Names of the relations shown, or * for every relation the packages of the namespace declare |
| `direction` | `out` \| `in` \| `both` |  |  |
| `limit` | `integer` |  |  |

### `view/componentSpec` { #schema-view-componentspec }

| Field | Type | Required | Description |
|---|---|---|---|
| `description` | [`view/messageKey`](#schema-view-messagekey) |  |  |
| `params` | [`view/componentParams`](#schema-view-componentparams) |  |  |
| `layout` | [`view/layout`](#schema-view-layout) | yes |  |

### `view/componentParams` { #schema-view-componentparams }

Value: map → [`view/schemaParam`](#schema-view-schemaparam) or [`view/param`](#schema-view-param) — by condition.

### `view/schemaParam` { #schema-view-schemaparam }

A param typed by a JSON Schema

| Field | Type | Required | Description |
|---|---|---|---|
| `schema` | `object` | yes | JSON Schema of the param: inline or {$ref: &lt;file&gt;#&lt;pointer&gt;} of a schema of the package; CEL reads param.&lt;name&gt; by it |
| `required` | `boolean` |  |  |
<!-- /generated:schema-view -->

## See also

- [package-sdk commands](package-sdk-cli.md)
- [Package anatomy](../packages/anatomy.md)
- [Processes](../processes/index.md)
- [Expressions](../processes/expressions.md)
- [Package tests](../packages/testing.md)
- [Catalog packages](../control-plane/catalog-packages.md)
