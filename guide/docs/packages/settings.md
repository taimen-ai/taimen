
# Package settings

Settings are values that an organization administrator changes in the live
system without a new package version and without an installation plan: an
approval threshold, a review due date, an escalation role. The package
declares their shape in the manifest, the core keeps the values with their
history, and the package's processes, rules, and screens read them as
`settings.<field>`. The first half of the page is for the package author, the
second is for the administrator. Rationale: TAI-ADR-0067, CP-ADR-0081.

## Setting or installation variable { #settings-or-variables }

A package has two ways to keep a value out of its files. They do not replace
each other:

| | Installation variable `${NAME}` | Setting `settings.<field>` |
|---|---|---|
| Declared in | `spec.variables` of the manifest | `spec.settings` of the manifest |
| Where the value lives | the installation file, `.env`, the environment | the core, with a version history |
| Who changes it and how | the installation author: edit, `plan`, `apply` | the administrator: the console or `PUT /api/v1/packages/{key}/settings` |
| When it takes effect | after `apply` of a new revision of the objects | on the next computation, without a plan and without a new process version |
| How it reaches the object | as text in the file before the expression is parsed | the `settings` variable, typed from the schema |
| What it suits | deployment topology: a workspace id, a system address | the organization's rules of the game: thresholds, due dates, roles |
| Secrets | no (secrets belong to credentials and connections) | no: a schema or values with secret markers are rejected |

If the business changes the value, rather than whoever installs the package,
it is a setting. Installation variables are covered in
[Package anatomy](anatomy.md#variables).

## Declaration { #declaration }

Settings are declared by the `spec.settings` section of the `package.yaml`
manifest: the `schema` of the values and an optional form layout, `uischema`.

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

### The JSON Schema subset { #schema }

`schema` is a subset of JSON Schema, as for process data. The root is an
object; a field name is camelCase (`^[a-z][A-Za-z0-9_]{0,62}$`), since
expressions read the field by it.

| Keyword | For which types |
|---|---|
| `type` | `string`, `integer`, `number`, `boolean`, `array`, `object` |
| `properties`, `required` | `object` |
| `items`, `minItems`, `maxItems` | `array`; `minItems`, `maxItems` are integers from 0 |
| `enum` | scalars, up to 100 values |
| `minimum`, `maximum` | `integer`, `number` |
| `minLength`, `maxLength`, `pattern`, `format` | `string`; `format` is `date`, `uri`, `email`, or `uuid` |
| `default` | any; the value must match the field schema |
| `x-ref` | `string`: a reference to a platform object (below) |

Limits: objects nest at most three levels deep, counting the root, and at the
third level an array holds only scalars; an object has at most 100
properties. `additionalProperties` is allowed only as `false` (which is
implied anyway). Do not write `title` and `description` in the schema: the
labels come from the package dictionaries (see [Labels](#labels)).

`x-ref` says that the string references a platform object in the
organization. On save, the core checks that the object exists and is in use:

| `x-ref` | Value | "In use" |
|---|---|---|
| `role` | role id | the role exists in the organization |
| `principal` | principal id | the principal is not disabled |
| `workspace` | workspace id (not a slug) | the workspace is active |
| `taskType` | task type key | it has an active version |
| `calendar` | calendar key | the calendar is not retired |

### Default values { #defaults }

Every **optional** scalar field and array has a `default`: the package works
right after installation without saving anything. An optional object needs
no `default`: it is assembled from the default values of its fields.

A required field (`required`) may do without a `default`, but then it has no
effective value until the first save, and the package object must account for
that: `has(settings.escalationRole)` in CEL. A reference to a role, principal,
or workspace gets no `default`: every organization has its own ids, so such a
field is declared required.

### No secrets in settings { #no-secrets }

Settings are visible to everyone with the read permission, and their values
go to the package's agents and skills. That is why secret markers are
rejected already in the declaration: `writeOnly`, `format: password`, a field
name such as `password`, `secret`, `token`, `apiKey`, `privateKey`,
`credential`, `authorization`, `clientSecret` (the name `secretRef` is
allowed), and secret material in `default` or `enum`. A secret belongs to a
connection or to a named secret of an agent.

## Labels { #labels }

The schema holds no form strings: labels are keys of the package dictionaries
`i18n/<locale>.yaml`. A package with settings declares its languages in the
manifest (`locales`, `defaultLocale`), and every required key is present in
the dictionary of every declared language.

| String | Dictionary key | Required |
|---|---|---|
| package name on the settings screen | `<package>.title` | yes |
| field label | `<package>.settings.<path>` | yes, for every property |
| hint under the field | `<package>.settings.<path>.help` | no |
| group title (`label` of a `Group`) | `<package>.settings.groups.<id>` | yes |
| `label` of a `Control`, `text` of a `Label` | any key of the package dictionary | yes |

`<path>` is the property names joined by dots from the schema root
(`limits.refund`). Properties of objects inside the `items` of an array have
no labels: the form shows the array as a whole.

```yaml
# i18n/en.yaml
claims.title: Customer claims
claims.settings.refundLimit: Refund without approval, up to
claims.settings.refundLimit.help: >-
  A refund above this amount is approved by the claims manager. Cases where the
  decision has already been made keep the previous limit
claims.settings.replyDueWorkdays: Reply to the customer within, workdays
claims.settings.escalationRole: Escalation role
claims.settings.groups.refund: Refunds
claims.settings.groups.reply: Reply to the customer
```

The core returns the strings in the requested language (`?locale=`); if the
package lacks that language, in its `defaultLocale`.

## Form layout: `uischema` { #uischema }

`uischema` is a closed subset of JSON Forms that the console renders. Without
it, the console lays the fields out in a column in schema order, with a
nested object as a group.

| `type` | Fields | What |
|---|---|---|
| `VerticalLayout` | `elements` | elements in a column |
| `HorizontalLayout` | `elements` | elements in a row |
| `Group` | `label`, `elements` | a frame with a title |
| `Control` | `scope`, `label?` | a form field |
| `Label` | `text` | a line of text |

- The root is a `VerticalLayout`, `HorizontalLayout`, or `Group`; nesting is
  at most 5, and there are at most 200 elements in total.
- `scope` is a pointer to a schema property: `#/properties/<field>`, nested
  `#/properties/<a>/properties/<b>`. One property has at most one `Control`;
  a pointer into the `items` of an array is not allowed.
- Any element may have a `rule`: an `effect` (`SHOW`, `HIDE`, `ENABLE`,
  `DISABLE`) and a `condition {scope, schema}`, where `schema` is `const`,
  `enum`, or `minimum`/`maximum`. A rule only changes how the form looks: a
  hidden field is still saved and checked.
- A field without a `Control` in a given `uischema` is the warning
  `settings_uischema_uncovered`: the value is in effect, but it cannot be
  changed in the form.
- Elements have no other fields: the core rejects `options` on a `Control`
  (`multi`, `format: radio` from JSON Forms) at plan time with the code
  `settings_uischema_unsupported`.

## Reading settings: `settings` { #references }

A package object reads the settings of its own package by the name
`settings`. Another package, and an object created by hand rather than by a
package, do not see the settings: a reference to `settings` in it is the
publishing error `settings_ref_unknown`.

| Where | How | When it is read |
|---|---|---|
| Process | the CEL variable `settings.<path>`, typed from the schema | once per step transaction |
| Process step due date | `{expr: settings.<field>}` in place of the number in `workdays`, `workhours`, and the same in `warnBefore`: `due: {workdays: {expr: settings.<field>}}`, a non-negative integer | once on entering the step |
| Work rule | `{var: settings.<path>}` in a condition, `{{settings.<path>}}` in a template | once per evaluation |
| Package screen (`View`) | the `settings` variable in expressions | once per block data query |
| Package agent | `packageSettings` in the `GET /api/v1/agents/me` response | on request |
| Package skill | `ctx.settings` in `skill-sdk` | pinned to the invocation attempt |

```yaml
# process: a decision table input and a step due date from settings
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
# rule: a condition on a setting
spec:
  condition:
    gt: [{var: payload.data.amount}, {var: settings.refundLimit}]
```

The effective value is the saved one over the schema `default`: nested
objects are merged field by field, and an array is replaced as a whole. A
changed value takes effect on the next computation; a case that has already
passed the step does not change.

### Journal and replay { #journal }

If a process version reads `settings` in at least one expression, every
journal entry of the instance carries `settingsVersion` and
`settingsSchemaRevision`: the values version and the schema revision the step
saw. Replay and a dry run give the step the values of that version, not the
current ones, so the decision of an earlier case is reproduced even after the
setting changes. An entry whose version is not in the database is the replay
divergence `{kind: "settings", journalSeq, recorded}`. A rule writes the same
pair into the `evidence` of its evaluation as the element
`{"kind": "settings", …}`.

## Checking without a deployment { #check }

`package-sdk check` checks the declaration and the references with the same
codes the core uses at plan time. The path of a declaration finding starts
at `/spec/settings`; a reference finding has the path of the expression in
the object file.

| Code | When |
|---|---|
| `settings_schema_unsupported` | a keyword outside the subset, `title`/`description`, a root that is not an `object`, exceeded limits, an `x-ref` of an unknown kind or not on a string |
| `settings_default_missing` | an optional field has no `default` |
| `settings_default_invalid` | the `default` does not match the field schema |
| `settings_secret_field` | a secret marker in the schema, a field name, `default`, or `enum` |
| `settings_uischema_unsupported` | a layout outside the subset: an element field outside the table (for example, `options`), a `scope` not on a property, a second `Control` on the same property, a group label that is not `<package>.settings.groups.<id>` |
| `settings_uischema_uncovered` | a warning: a field has no `Control` |
| `settings_label_missing` | the package declares no `locales`, or a required label key is missing from a language's dictionary |
| `settings_ref_unknown` | `settings.<path>` reads an undeclared field, or the object's package declares no settings |
| `settings_ref_type` | the field type does not fit the place: an object in a string template, an array in a comparison, a non-`integer` in a due date |

`check` checks rules completely; the CEL expressions of processes and screens
are typed by the core code next to `package-sdk` (the `sandbox` extra).
Without it, `check` catches only undeclared fields and warns that the types
were not checked.

`package-sdk describe` shows settings next to installation variables:

```text
settings (changed by an administrator in the live system):
  escalationRole [string, ref role, required] (claims)
  refundLimit [number, default 500] (claims)
  replyDueWorkdays [integer, default 2] (claims)
```

Scenarios with settings are covered in [Package tests](testing.md#settings).

## Compatibility on upgrade { #upgrade }

`apply` of a new package version writes a new revision of the settings
schema but does not touch the saved values: the values version, the history,
and the event do not change. What will change is shown by `plan` in its
`settings` section:

```json
"settings": {
  "schemaRevision": {"before": 1, "after": 2},
  "added":        [{"path": "/replyDueWorkdays", "default": 2}],
  "removed":      [{"path": "/legacyLimit", "saved": true}],
  "incompatible": [{"path": "/refundLimit", "code": "maximum"}],
  "uischemaChanged": true
}
```

| Field | Meaning |
|---|---|
| `schemaRevision` | the schema revision before and after; `after: null` means the schema does not change or the package stops declaring settings |
| `added` | a new field and its `default`: it takes effect at once, nothing needs saving |
| `removed` | the field left the schema; `saved` tells whether it had a saved value. That value stays in the history, but it no longer appears in responses and expressions |
| `incompatible` | a **saved** value does not match the schema of the new revision: the path and the keyword, without the value |
| `uischemaChanged` | the form layout changed |

An incompatible value is also the plan error `settings_incompatible`; `apply`
of such a plan answers `422 invalid_package`. There is no automatic migration
of values: the administrator saves a fitting value, and the author builds the
plan again. Hence the rules for the author of a new version:

- give a new field a `default`, and the upgrade requires nothing from the
  administrator;
- check a narrowing (a smaller `maximum`, a shorter `enum`, a new required
  field without a `default`) against the deployment's saved values: the plan
  shows each incompatible one;
- renaming a field is a removal plus an addition: the saved value of the old
  field is not carried over;
- a value saved between `plan` and `apply` makes the plan stale:
  `409 plan_stale`, and the plan is built again.

If a package stops declaring settings, its objects no longer read
`settings`, the settings routes answer `404 settings_not_declared`, and the
history stays. How the plan and its application work is covered in
[Installation and release](install-and-release.md#plan).

## For the administrator { #admin }

### The Settings screen { #console }

In the console, package settings are the Packages section of the Settings screen
(`/console/settings`): one item for each installed package that has settings. The
form is built from the package's schema and layout, with labels and hints in the
user's language. Each value shows whether it is the default, saved, or changed.
Save writes a new version under your name; core errors are shown next to the
fields. Change history shows the author, the time, and the changed fields of any
version, and you can restore it: the restore is written as a new version. Without
the `packages.settings.manage` permission the form opens read-only.

### Permissions { #permissions }

| Permission | What it allows |
|---|---|
| `packages.settings.read` | the list of packages with settings, the settings of a package, and their history |
| `packages.settings.manage` | saving the settings of a package; `canManage: true` in the read response |

Both permissions are at the organization level and independent of
`packages.plan`: whoever changes thresholds does not have to be able to
install packages, and vice versa. The `admin` permission includes both. A
summary of permissions is in [Permissions and scopes](../reference/permissions.md).

### Routes { #routes }

| Method | Path | Permission | What |
|---|---|---|---|
| GET | `/api/v1/package-settings` | `packages.settings.read` | the packages whose installed revision declares settings |
| GET | `/api/v1/packages/{key}/settings` | `packages.settings.read` | the schema, the layout, the saved and the effective values |
| PUT | `/api/v1/packages/{key}/settings` | `packages.settings.manage` | save the values as a whole |
| GET | `/api/v1/packages/{key}/settings/versions` | `packages.settings.read` | the version history, newest first |

All routes except the history accept `?locale=`, the language of the response strings.

### Reading { #read }

```bash
# packages that have settings
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://platform.example.com/api/v1/package-settings?locale=en"

# the settings of one package
curl -si -H "Authorization: Bearer $TOKEN" \
  "https://platform.example.com/api/v1/packages/claims/settings?locale=en"
```

```json
{
  "package": "claims",
  "title": "Customer claims",
  "packageVersion": "0.2.0",
  "schema": {"type": "object", "properties": {
    "refundLimit": {"type": "number", "minimum": 0, "default": 500,
                    "title": "Refund without approval, up to", "description": "…"}}},
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

| Field | What |
|---|---|
| `schema`, `uischema` | the schema and layout of the active revision; labels are filled in as `title`, `description`, `label`, `text` in the requested language |
| `values` | the saved values |
| `effective` | the effective values: `values` over `default` |
| `version` | the values version; `0` means nothing has been saved yet |
| `canManage` | whether the caller holds `packages.settings.manage` |

The response header `ETag: "package-settings-<version>"` is needed for
saving.

### Saving { #save }

`PUT` saves the set of values **as a whole**: a field missing from the body
returns to its default value. `If-Match` is required: the version you read;
before the first save, `"package-settings-0"`.

```bash
curl -s -X PUT -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'If-Match: "package-settings-3"' \
  -d '{"values": {"refundLimit": 1000, "escalationRole": "<role-id>"}}' \
  "https://platform.example.com/api/v1/packages/claims/settings"
```

The response is the new state in the same form as for `GET`, with a new
`ETag`. A body equal to the saved values creates neither a version nor an
event.

| Response | Code | What to do |
|---|---|---|
| 428 | `if_match_required` | send `If-Match` |
| 400 | `invalid_if_match`, `invalid_request` | `If-Match` has the wrong form; the body has something other than `values` |
| 404 | `package_not_installed`, `settings_not_declared` | the package is not installed or declares no settings |
| 422 | `secret_material_rejected` | a value holds secret material; `details.errors[]` gives the `path` and the kind of match, the value is not repeated |
| 422 | `settings_invalid` | the values do not match the schema; `details.errors[]` gives the `path` and the `code` (the keyword), all errors at once |
| 422 | `unknown_ref` | an `x-ref` references an object that does not exist or is not in use; `details.errors[]` gives the `path` and the `ref` |
| 409 | `version_conflict` | someone saved first; `details.currentVersion` — read again and retry |

The schema check does not execute the `uischema` rules: a hidden field is
checked like any other.

### History and restoring { #history }

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

Versions go from newest to oldest; `limit` is 1 to 100 (50 by default); the
next page is `?cursor=<nextCursor>`. There is no separate rollback route: to
restore a version, save its `values` with a regular `PUT`. The restore
becomes a new version, and the history is not rewritten.

### The `package.settings_changed` event { #event }

Every save that creates a version writes the `package.settings_changed` event
to the journal. It carries no values, only what changed and who changed it:

| Payload field | What |
|---|---|
| `package` | the package key |
| `version`, `previousVersion` | the new and the previous values version (`0` on the first save) |
| `schemaRevision` | the schema revision the values were checked against |
| `changedPaths` | the paths of the changed fields |
| `actorId` | who saved |

A package `apply` does not write the event. How to subscribe to the journal is
covered in [Events](../control-plane/events.md).

## Common problems { #troubleshooting }

| Symptom | Cause | What to do |
|---|---|---|
| `settings_default_missing` | an optional field has no `default` | give it a `default` or add the field to `required` |
| `settings_label_missing` | a label key is missing from the dictionary of one of the languages, or the package declares no `locales` | add the key to `i18n/<locale>.yaml`; declare `locales` and `defaultLocale` |
| `settings_ref_unknown` on a process | the field is not declared, the path has a typo, or the process was not created by a package | declare the field in `spec.settings` or fix the path |
| `settings_ref_type` | the field type does not fit the place in the expression | change the field type or the expression: a due date needs an `integer` field |
| plan: `settings_incompatible` | a saved value does not match the new schema | save a fitting value and build the plan again |
| `PUT`: `409 version_conflict` | the values were saved after you read them | read again, retry with the new `If-Match` |
| `PUT`: `422 unknown_ref` | the role, principal, or workspace was deleted or disabled, or the task type has no active version | choose an object that is in use |
| a changed value did not affect a case | the case has already passed the step that reads the setting | expected: the value takes effect on subsequent computations |

## See also

- [Package anatomy](anatomy.md#variables): installation variables
- [Package tests](testing.md#settings): `given.settings` and the `settings` step
- [Scenarios and the core plan](../processes/package-tests.md): the process scenario format and replay
- [Process expressions](../processes/expressions.md#variables): CEL variables
- [Rules in a package](rules.md)
- [Installation and release](install-and-release.md#plan)
- [Package schema](../reference/package-schema.md#schema-packagesettings): the `spec.settings` reference
- [Events](../control-plane/events.md)
