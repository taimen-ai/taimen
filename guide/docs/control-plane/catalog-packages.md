
# Catalog packages

Reference of the catalog package kinds: how each kind maps to the API of the
service that stores it, in which order the kinds are applied, which of them are
versioned and retired, and how the core remembers which package installed an
object. This page is for installation administrators and for those who read the
catalog through the API. How to write, test, and install a package is described
in the [Packages](../packages/index.md) section. Rationale: TAI-ADR-0044,
TAI-ADR-0062.

## Object format

Each package file is one object in a common envelope; `spec` is exactly the API
request body of the service that stores the object, in camelCase and without
the identity field:

```yaml
apiVersion: taimen.ai/v1
kind: TaskType
key: document-review
spec:
  displayName: Document review
  fieldSchema: { ... }
  lifecycleSchema: { ... }
```

Key rules, the manifest, and variables are described in [Package
anatomy](../packages/anatomy.md).

## Kinds and the API { #kinds }

| `kind` | Folder | Identity in the API | How it is applied |
|---|---|---|---|
| `KnowledgePack` | `knowledge-packs/` | `name` | a memory ontology: registration of a version with `POST /api/v1/knowledge/packs`; different content under the same version is an error. Enabling it for workspaces is the installation's `knowledge` section, `PUT /api/v1/workspaces/{id}/knowledge-packs` |
| `WorkspaceType` | `workspace-types/` | `key` | create, or `PATCH` (with `If-Match`) on divergence; a package will not restore an archived type — this is an error |
| `Capability` | `capabilities/` | `name` | creation only; a description divergence is a warning (the API does not change the description) |
| `Role` | `roles/` | `slug` | tenant-level roles; create or `PATCH` |
| `Skill` | `skills/` | `name` + `spec.version` | create a version; a divergence in `protocol`, `sideEffects`, `riskLevel`, or `contract` is an error "bump `spec.version`"; for a published version only `description` and the status change |
| `ArtifactType` | `artifact-types/` | `key` | a new immutable version, only if the file differs from the newest one (see [below](#artifact-type)) |
| `TaskType` | `task-types/` | `key` | on divergence from the newest active version a new one is published, and the other active versions → `deprecated`. `acceptance` holds the default acceptance criteria for all tasks of the type ([Type acceptance](task-types.md#type-acceptance)) |
| `Agent` | `agents/` | `key` | first `POST /api/v1/agents:validate`; if neither the revision nor the desired state changes — "no changes", otherwise `POST /api/v1/agents` (see [below](#agent)) |
| `ProjectTemplate` | `project-templates/` | `key` | the same as `TaskType` |
| `Calendar` | `calendars/` | `key` | a business calendar; applied only through a core plan (see [below](#processes)) |
| `Process` | `processes/` | `key` + `spec.version` | a process; applied only through a core plan (see [below](#processes)) |
| `WorkRule` | `rules/` | `key` | a work rule ([Work rules](work-rules.md)): create, or `PATCH` (with `If-Match`) the changed `description`, `trigger`, `condition`, `interpretation`, `action`, `identity`; `status` — through `:enable`/`:disable`. `workspaceId` is set only by an installation variable and does not change after creation. With `identity: {agent: <key>}` the rule acts with the authority of this agent |
| `NotificationRule` | `notification-rules/` | `key` | applied **to the notification service**, not to the core; the service computes the version from the spec hash (see [below](#notification-rule)) |

There is no deletion for any kind.

## Application order

The single installation plan (see [Installation and
release](../packages/install-and-release.md#plan)) is applied in sections:
`catalog` → `core` → `knowledge` → `notification-rules` → `retire`.

- **`catalog`** — the kinds the installer applies as core resources, in
  dependency order: `WorkspaceType` → `Capability` → `Role` → `Skill` →
  `ArtifactType` → `TaskType` → `Agent` → `ProjectTemplate` → `WorkRule`.
  Whatever is referenced is created earlier: a task type's `artifactSchema`
  references artifact types, an agent references roles and task types, and a
  rule with `identity` references an agent.
- **`core`** — a package with processes or calendars is planned and applied by
  the core itself (`POST /api/v1/packages:plan`, `/packages:apply`): for such a
  package these are task types, agents, calendars, processes, and work rules.
  For it, they are not part of the `catalog` section.
- **`knowledge`** — registration of ontologies, then enabling the packs for
  workspaces.
- **`notification-rules`** — notification rules do not reference anything in
  the core, but they take effect immediately after being applied, so they go
  when the core is already reconciled.
- **`retire`** — retirement.

## Agent (`Agent`) { #agent }

A file in the `agents/` folder describes an agent in full: identity and
permissions, which work it takes, the executor kind with parameters and
instructions, the working copy, skills, and placement (TAI-ADR-0052). The
schema is `$defs.agentSpec` in `sdk/package-sdk/schema/v1/object.schema.json`; for
the author, see [Package agents](../packages/agents.md).

- `check` validates the description against the format schema and the core's
  `AgentSpec` model, requires `work.taskTypes` to be declared in the package or
  its `requires`, and warns about roles from `identity.roles` that are not in
  the packages (they must already exist in the tenant);
- topology — `work.workspace`, `work.project` — is written as an installation variable
  `${NAME}`;
- secret values are not written into the description — only names in
  `placement.secrets`; the core rejects `params` keys that look like a secret
  with `422 secret_material_rejected`;
- a new immutable revision appears only if the description hash differs;
  `state` and `placement.replicas` change the desired state without a revision,
  and every application brings the agent to them;
- the permissions the description grants to the agent must be held by whoever
  applies it: otherwise `403 permission_escalation`;
- `retire.Agent` retires the agent: the executor stops, the credential is
  revoked, the run history remains;
- `export` exports the `spec` of the current (or the `--version`-specified)
  revision, and `state` and `replicas` from the desired state, omitting
  defaults.

Placement of executors on machines according to the `placement` description is
not part of the delivery: you can start an executor described by an agent
manually with the `control-plane-agent` daemon (see [Runner](../runner/index.md)).

## Notification rule (`NotificationRule`) { #notification-rule }

A file in the `notification-rules/` folder describes which Control Plane event
becomes a notification. The schema is `$defs.notificationRuleSpec`, the full
description is in [Notification rules](../notifications/notification-rules.md),
and for the author, see [Package notifications](../packages/notifications.md).

- It is applied to the notification service: the address is the installation
  variable `NOTIFICATION_SERVICE_URL`, the token is `NOTIFY_TOKEN` (audience
  `notification-service`, scope `notifications:admin`) or an exchange of the
  same IAM credential the installer uses.
- `plan` calls `:validate` for all rules of the installation: a rule the service
  will not accept stops the whole plan; only changed rules get into the plan.
- The `on` key is written in quotes (`"on":`) — otherwise YAML 1.1 reads it as
  `true`.
- `retire.NotificationRule` retires the rule; sent notifications remain.
  `export --kind NotificationRule` exports the active version from the service;
  `--server` is not needed, `--version` is not supported.

## Artifact type (`ArtifactType`) { #artifact-type }

An artifact type is a key, a `metadata` schema, allowed media types, and a
content size ceiling (the model is in [Artifacts](artifacts.md#artifact-types)):

```yaml
apiVersion: taimen.ai/v1
kind: ArtifactType
key: review-report
spec:
  displayName: Заключение проверки
  mediaTypes: [application/pdf]
  maxBytes: 10485760            # optional
  metadataSchema:
    type: object
    properties:
      reviewer: {type: string}
```

| `spec` field | Default in the package | How it is compared with the live version |
|---|---|---|
| `displayName`, `description` | `""` | always |
| `metadataSchema` | `{}` | always |
| `mediaTypes` | `["*/*"]` | always; before comparison they are lowercased, and parameters and duplicates are dropped — this is how the core stores them |
| `maxBytes` | not set — the core takes the installation's `CP_ARTIFACT_MAX_BYTES` at the time of publication | only if set in the file |

- Versions are immutable, and artifact types have no deprecation: old versions
  are not moved to `deprecated`, and `retire` is not supported for
  `ArtifactType`.
- Artifacts are always validated against the newest version: narrowing
  `mediaTypes` or `maxBytes` immediately affects new artifacts.
- `check` validates `metadataSchema`, the grammar of `mediaTypes`, a positive
  `maxBytes`, that every `type` in a task type's `artifactSchema` is declared in
  the package or its `requires`, and that a slot's `mediaTypes` narrow the
  `mediaTypes` of its type. Exceeding `CP_ARTIFACT_MAX_BYTES` is caught by the
  core on application (`422 invalid_artifact_type`).

## Processes and calendars { #processes }

A process (`kind: Process`) and a business calendar (`kind: Calendar`) are
executed and validated by the core itself (TAI-ADR-0054, CP-ADR-0074). The
language is described in the [Processes](../processes/index.md) section;
scenarios, replay, and the core plan in [Scenarios and the core
plan](../processes/package-tests.md); versions and live cases in [Processes in a
package](../packages/processes.md).

```text
<package>/
├── package.yaml               # renames — explicit object renames
├── processes/<key>.yaml       # kind: Process
├── calendars/<key>.yaml       # kind: Calendar
├── schemas/<name>.schema.json # data schemas: data: {$ref: ../schemas/<name>.schema.json}
├── tests/<name>.test.yaml     # scenarios (schema/v1/test.schema.json)
└── .layout/<key>.json         # layout for the visual editor; carries no logic
```

- A package with processes or calendars is installed only through a core plan:
  the `core` section of the single plan, the requests `POST
  /api/v1/packages:plan` and `/packages:apply` with the package files (with
  `tests/`, without `.layout/`, with variables substituted).
- `data: {$ref: …}` references only a file inside the package.
- If the core does not know the process package routes (`404` or `501`),
  `check --server` reports "the core does not support process validation … —
  only the schema was checked", while `test --server` and `plan` fail with an
  error.

## Editing files: `package-sdk edit` { #pkg }

`package-sdk edit` performs small edits to a process and a package and changes
only the affected lines: comments, key order, quotes, and the flow/block style
of the rest of the file stay as they were. An edit that the catalog schema
rejects or that repeats an element id is not written.

| Operation | What it does |
|---|---|
| `add-step --in <stage or step> --step <yaml> [--after/--before <id>]` | adds a step to a stage or to the `do` block of a step, branch, or timer |
| `add-stage --stage <yaml> [--after/--before <id>]` | adds a stage |
| `add-decision-row --table <id> --row <yaml> [--index N]` | adds a decision table row; the columns are checked against the table's inputs and outputs |
| `add-rule --table <id> --row <yaml>` or `add-rule --on-event <yaml>` | a decision table row or a process reaction to an event (`onEvent`) |
| `add-form-field --step <id> --name <field> --schema <yaml> [--required] [--label]` | a form field of a human step |
| `rename --file <process> --from <id> --to <id> [--no-migration]` | renames a process element, the references to it, and the package tests; appends the `migrations` map |
| `rename --package <directory> --kind <kind> --from <key> --to <key>` | renames a package object and its file, appends `renames` to `package.yaml`; with history, the plan carries over `Process` and `Calendar`, for other kinds it issues the warning `rename_not_planned` ([Anatomy](../packages/anatomy.md#renames)) |
| `set --path <path> --value <yaml>` | writes a value; in the path, `[N]` is an index and `[id]` is a list element by id |

`--json` prints the result or the error in machine-readable form, and
`--dry-run` prints a diff without writing. The package language is YAML 1.2:
boolean values are only `true`/`false`.

## Linking objects to a package { #package-links }

Control Plane remembers which package installed a catalog object: read
responses carry the object's `package {key, version, installHash, installedAt}`
field, and lists accept the `?package=<package key>` filter. The link belongs to
the object (`kind` + key), not to a version: all versions of a task type are one
object.

- Processes, calendars, and the other kinds of a package with processes are
  linked by the core itself when it applies the core plan.
- The rest the installer applies through their own routes and then tells the
  core what it installed: one `POST /api/v1/packages:record` call per package,
  with all objects of the package of the kinds the core records, **the
  unchanged ones too** — when a package is upgraded, their link moves to the
  new version. The installer takes the list of kinds from the core's OpenAPI
  (`GET /openapi.json`).
- An agent published from a package is sent to `POST /api/v1/agents` together
  with `package {key, version}`: the new revision records the package as its
  source.

`installHash` is `sha256:<hex>` of the contents of the package files: sorted
relative paths, and for each file its path, length, and bytes as they are
stored in git, before `${VARIABLES}` are substituted. The same package gives the
same hash on any machine.

```bash
curl -s -H "Authorization: Bearer $CP_TOKEN" \
  "https://platform.example.com/api/v1/task-types?package=<package>" | jq '.items[] | {key, package}'
```

`/artifact-types`, `/workspace-types`, `/project-templates`, `/roles`,
`/capabilities`, `/skills`, `/rules`, and `/agents` are filtered the same way.
Recording the link requires the `packages.plan` permission and the write
permission of every named kind.

## Exporting from a deployment: `export`

An object that was created or edited through the API is exported into a package
file:

```bash
package-sdk export --server https://platform.example.com \
  --kind TaskType --key document-review --package <package-dir>
```

`export` takes the newest active version (or the one given in `--version`),
drops empty fields and default values, and for a skill with a contract removes
the fields derived from the contract (`inputSchema`, `outputSchema`,
`protocol`). For `Process` and `Calendar`, `--env` turns values back into
`${VARIABLE}` references, and `--workspace` takes console fields into account.

## What a package does not include

- **Topology**: workspaces, projects, membership, and role assignments to
  people. Principals and agent bindings are not written into a package either:
  the platform derives them from the `Agent` description.
- **Fixture tasks.**
- **Enabling ontologies for workspace trees** — the installation's `knowledge`
  section; the ontology itself is a `KnowledgePack` object of the package.
- **Retirement** — the installation's `retire` list (see [Installation and
  release](../packages/install-and-release.md#retire)).

## Deployment initialization

`make bootstrap` installs the default installation catalog
`deploy/packages.yaml` at step 5b (a different file — the `--packages` flag);
the identifiers of published objects are saved in the bootstrap state, and UUIDs
do not live in the packages themselves. For details, see the article
[Bootstrap](../getting-started/bootstrap.md).

## Common problems

| Message | Cause | What to do |
|---|---|---|
| `в опубликованной версии отличаются contract — контракт версии неизменяем` ("contract differs in the published version — the version contract is immutable") | the skill contract was edited without changing the version | bump the skill's `spec.version` |
| `artifactSchema.inputs '…': тип артефакта '…' не объявлен ни в пакете …, ни в его requires` ("artifact type '…' is declared in neither the package … nor its requires") | unclosed reference to an artifact type | declare the `ArtifactType` or add the package that has it to `requires` |
| `artifactSchema.outputs '…': mediaTypes [...] шире, чем у типа …` ("mediaTypes [...] are wider than those of type …") | the output widens rather than narrows the type's media types | narrow the output's `mediaTypes` or widen the type |
| `retire: вид ArtifactType не выводится из оборота` ("kind ArtifactType cannot be retired") | `ArtifactType` in `retire` | remove it from the list |
| `retire: системный тип task вывести нельзя` ("the system type task cannot be retired") | `task` in `retire` | remove it from the list |
| `422 non_canonical_value` when applying an agent | a fractional number in the description (for example, `resources.cpus`) | integers only |
| `403 permission_escalation` | the token lacks the permissions the description grants to the agent | apply with a token that has these permissions |
| `пакет …: объекты применены, но ядро не записало их связь с пакетом` ("package …: the objects are applied, but the core did not record their link to the package") | the token lacks `packages.plan` or the write permission of a kind | grant the permissions and repeat the application: it is idempotent |
| `ядро не записывает связь объектов с пакетом (нет POST /api/v1/packages:record)` ("the core does not record the link of objects to a package") | Control Plane predates package links | update Control Plane |
| `сервис уведомлений не принимает правило — …` ("the notification service does not accept the rule — …") | `:validate` returned `422 invalid_notification_rule` | fix the rule according to `details.errors` |
| `element_id_taken` from `package-sdk edit` | the element id already exists in the process | choose a different id |

## See also

- [Packages](../packages/index.md) — the package author section
- [Installation and release](../packages/install-and-release.md)
- [Processes](../processes/index.md) — the language of the `Process` kind
- [Task types and statuses](task-types.md)
- [Work rules](work-rules.md)
- [Notification rules](../notifications/notification-rules.md)
- [Artifacts and comments](artifacts.md#artifact-types)
- [Bootstrap](../getting-started/bootstrap.md)
- [skill-sdk](../sdk/skill-sdk.md)
