
# Package anatomy

What a package consists of: the directory layout, the object wrapper, the
manifest (`engines`, `requires`, `variables`, `knowledge`), references between
objects by key, versions and their immutability, renames, and the installation
file. This page is for package authors and installation administrators; a
first package step by step is in [A package in 10 minutes](quickstart.md).

## Layout { #layout }

```text
<package>/
├── package.yaml               # kind: Package — manifest
├── task-types/                # kind: TaskType
├── artifact-types/            # kind: ArtifactType
├── project-templates/         # kind: ProjectTemplate
├── workspace-types/           # kind: WorkspaceType
├── roles/                     # kind: Role
├── capabilities/              # kind: Capability
├── skills/                    # kind: Skill
├── agents/                    # kind: Agent
├── rules/                     # kind: WorkRule
├── processes/                 # kind: Process
├── calendars/                 # kind: Calendar
├── knowledge-packs/           # kind: KnowledgePack
├── notification-rules/        # kind: NotificationRule
├── schemas/                   # JSON Schema of process data (data: {$ref: …})
├── tests/                     # *.test.yaml — scenarios
├── .layout/                   # visual editor layout; carries no logic
├── integration/               # observer and skill code — for an integration
└── README.md
```

- **The package directory is named after its key.** `check` and `test` by
  a directory path take the package key from the directory name
  and compare it with the manifest's `key`: a mismatch is the error
  `key … не совпадает с ключом пакета в установке` ("key … does not match the
  package key in the installation"). Put a trial copy of a package into a
  directory with the same name. A package from another repository, connected
  in the installation file by `path` or `git`, may live anywhere: its key is
  the key of the installation entry.
- **The object kind is set by the `kind` field, not by the folder.** Folders
  are a convention for people; `package-sdk add` places files in them.
- The loader reads all `*.yaml` files of the package in all subdirectories
  except `package.yaml`, `tests/`, `schemas/`, and `.layout/`. Each such file
  must be a catalog object: a file with an unknown `kind` is an error. So put
  auxiliary YAML files in `schemas/` or give them a different extension.
- In `tests/`, only `*.test.yaml` files are read.
- The file language is YAML 1.2: booleans are only `true` and `false`. Quote
  the `on` key of a process start (`"on":`) if the file is also read by a
  YAML 1.1 tool.
- `package-sdk` reads numbers and dates the way the core does on publishing:
  `012` is twelve, `1_000` and `2026-09-30` are strings, `.inf` and `.nan` are
  errors. So `check`, `test`, and `plan` see exactly the values the deployment
  will get.

## Object wrapper

```yaml
# yaml-language-server: $schema=<path to schema/v1/object.schema.json>
apiVersion: taimen.ai/v1
kind: Role
key: access-approver
spec:
  name: Access approver
  description: Decides on access requests
```

| Field | Rule |
|---|---|
| `apiVersion` | the format constant `taimen.ai/v1`: a schema name, not a service address |
| `kind` | the object kind: `Package`, `Installation`, and the catalog kinds from the [map of kinds](index.md#kinds) |
| `key` | the object's identity in the tenant; the key form depends on the kind (below) |
| `spec` | exactly the API request body of the service that stores the object, in camelCase and without the identity field |

| Kind | Key |
|---|---|
| `Package`, `TaskType`, `ArtifactType`, `ProjectTemplate`, `WorkspaceType`, `Process`, `Calendar` | `^[a-z0-9][a-z0-9_-]*$`, up to 63 characters |
| `Role`, `Agent` | slug `^[a-z0-9][a-z0-9-]*$`, 2–63 characters |
| `WorkRule`, `NotificationRule` | `^[a-z0-9][a-z0-9._-]*$`, up to 128 characters |
| `Skill` | the skill name, for example `access.grant`; the version is in `spec.version` |
| `Capability` | the capability name |
| `KnowledgePack` | the ontology name `^[a-z0-9][a-z0-9._-]{0,63}$`; matches `spec.name` |

The package key that `package-sdk init` creates follows a stricter rule:
lowercase letters, digits, and `-`, starting with a letter.

The first comment line connects the schema to an editor with YAML Language
Server: field suggestions and errors as you type. `package-sdk init` and `add`
write it themselves, with a link to the schema of the installed SDK.

!!! note "The core is the final validator"
    The schema checks the shape. The grammar of expressions, rule conditions,
    decision outcomes, and processes is checked by the core code: `check`
    imports its validators (the `sandbox` extra), and with `--server` it also
    sends the package to the deployment's core.

## Manifest

```yaml
apiVersion: taimen.ai/v1
kind: Package
key: access-requests
spec:
  version: 0.2.0
  displayName: Access requests
  description: Access requests to internal resources and their review
  license: Apache-2.0
  authors: ["Example Integrations <dev@example.com>"]
  homepage: https://git.example.com/example/access-requests
  engines:
    control-plane: ">=0.10,<0.11"
  requires:
    - {package: access-base, version: ">=0.1"}
  knowledge: ["access@1"]
  variables:
    ACCESS_WORKSPACE_ID:
      kind: workspace
      description: Workspace where access requests are reviewed
    ACCESS_ESCALATION_HOURS:
      kind: integer
      description: Hours before an unanswered request is escalated
      default: "24"
```

| Field | Required | What it defines |
|---|---|---|
| `version` | yes | the package version, SemVer `X.Y.Z` |
| `displayName` | yes | a name for people |
| `description` | no | a description |
| `engines` | no | version ranges of the components the package is compatible with |
| `requires` | no | packages whose objects this package references |
| `variables` | no | the declaration of each installation variable `${NAME}` |
| `knowledge` | no | ontologies (`name@major`) that the package's processes rely on |
| `license` | no | the license, an SPDX identifier |
| `authors`, `homepage` | no | authors; the package address (`https://`) |
| `renames` | no | explicit object renames (see [below](#renames)) |

### `engines`: compatibility { #engines }

`engines` are the version ranges of platform components the package has been
checked against: `{control-plane: ">=0.10,<0.11"}`. A range is a
comma-separated list of conditions, all of which must hold; the operators are
`>=`, `>`, `<=`, `<`, `=`, `^`, `~`; a version without an operator is an exact
version or a prefix (`1.2` is any `1.2.x`); `*` is any version.

- `init` writes the range based on the core code installed next to the tool:
  the same minor version.
- `check` rejects an unparsable range (`engines_invalid`) and warns if the
  core code next to the tool is outside the range (`engines_mismatch`): in
  that case the check and the tests run on a version the package was not
  designed for.
- `plan` reads the deployment's core version from its `openapi.json` and
  refuses before any write if it is outside the range.

### `requires`: dependencies

A package references only its own objects and the objects of packages listed
in `requires`. An element is a package key (any version) or
`{package, version}` with a range in the same grammar as `engines`.

- `requires` are pulled into the installation automatically: in the
  installation file, it is enough to name the package you install.
- A dependency is looked up in order: the installation's `spec.packagesDir`,
  `packages/` next to the installation file, the installation file's
  directory. A package checked by path (`check --package <directory>`) looks
  for its `requires` next to itself, in neighboring directories.
- A dependency version in the installation outside the range is the error
  `requires_version_mismatch`; a dependency cycle is the error
  `цикл requires` ("requires cycle").
- The test sandbox builds the catalog from the objects of the package and all
  of its `requires`: a role or a skill from a dependency package is visible in
  a test.

### `variables`: installation variables { #variables }

Anything that depends on a particular deployment (a workspace UUID, an
external system address, an amount threshold) is not written into the
package but moved into a variable: `${NAME}` is written in any `spec` string,
and the variable is declared in the manifest.

| Variable field | What it defines |
|---|---|
| `description` | required: what it is and where to get the value |
| `kind` | required: `url` (an absolute `http(s)://` URL), `workspace`, `project`, `principal`, `role` (the UUID of a deployment object), `integer`, `string` |
| `required` | `true` by default |
| `default` | the value if the installation does not set its own (as a string) |
| `example` | an example value for `describe --env-example` |

`check` rules:

- a variable that is used but not declared is the error `variable_undeclared`;
- a variable that is declared but used nowhere is the error `variable_unused`;
- a `default` or `example` that does not fit the kind is the error
  `variable_invalid_value`;
- `required: true` together with `default` is the warning
  `variable_required_with_default`: `default` already makes the variable
  optional.

Variable values are set by the installation: the `--env` file (`.env` in the
current directory by default) and the process environment, with the
environment taking precedence over the file. `plan` checks that every
required variable is set, that the value fits the kind, and that the UUID of
the workspace, project, principal, or role exists on the deployment. `plan`
does not write the values themselves into the plan file, only their hash.
`package-sdk describe <package> --env-example` prints a scaffold of the
variables file.

!!! warning "No secrets in the package"
    A variable has no `secret` field, and secret values are not written into
    the package or the variables file. An executor's secret is a name in the
    agent description's `placement.secrets`: the secret itself lives on the
    node that runs the agent.

A work rule's `workspaceId` is set only through a variable: it is the
installation's topology, not the package's content.

`${NAME}` substitution is **textual** and happens before the core parses the
value: inside a process expression, the variable becomes part of its text.
Wrap a numeric variable in `double(…)` when comparing it with a `number`, and
put a string variable in CEL quotes; examples are in
[Expressions](../processes/expressions.md#install-variables). A substituted
value is always a string, even for a variable of kind `integer`.

### `knowledge`: ontologies

`knowledge` lists the memory ontologies (`name@major`) whose kinds and
relations the package's processes rely on in `memory`, `recall`, `remember`,
and step context.

- An ontology from the list must be declared as a `KnowledgePack` in the
  package or its `requires` (otherwise `knowledge_unknown`); the built-in
  memory ontology `default` needs no declaration.
- A kind or relation that is absent from the declared ontologies is the error
  `knowledge_term_unknown` (a warning if the content of some ontologies is
  not visible, for example the built-in `default`: then memory decides at
  registration).
- Processes access memory but `knowledge` is not declared: the warning
  `knowledge_undeclared`.

Enabling ontologies for a workspace is topology, so it is set in the
[installation](#installation), not in the package.

## References by key

Objects reference each other by key, not by deployment identifiers:

| From | To | Example |
|---|---|---|
| a rule action, a process `human` step, an outcome's `ensureWork` | task type | `taskType: access-review` |
| `identity` of a process and a rule, a rule's `assignee` | agent | `identity: {agent: access-requests-process}`, `assignee: agent:<key>` |
| `owner`, `assign` of process steps | role | `assign: [{role: access-approver}]` |
| a rule interpretation, a `call` step, `invokeSkill` | skill | `access.grant@1`: name and version |
| a task type's `artifactSchema` | artifact type | `type: access-grant` |
| `knowledge`, an ontology's `extends` | ontology | `access@1` |

`check` verifies that every reference is closed within the package and its
`requires`. The system task type `task` exists in every tenant and needs no
declaration. Identifiers of a particular deployment (a workspace or
principal UUID) are not written into the package, only through
[variables](#variables).

## Versions

### Package version

`spec.version` is the package's SemVer. The installation checks `requires`
ranges against it, it goes into `packages.lock`, and the core records for
each installed object which package and which version installed it (the
object's link to the package; see [Catalog packages](../control-plane/catalog-packages.md#package-links)).

Raise the package version with every release: patch for a fix without a
behavior change, minor for new objects and compatible changes, major for a
change that breaks installations or dependent packages.

### Immutable object versions

Some kinds are versioned in the core and immutable: a published version does
not change, and an edit is a new version.

| Kind | How an edit is published |
|---|---|
| `TaskType`, `ProjectTemplate` | if the file differs from the newest active version, a new version is published and the previous active ones are moved to `deprecated`; tasks and projects stay on their version |
| `ArtifactType` | a new version if the file differs from the newest one |
| `Process` | `spec.version` is an integer; an edit is `version: N+1`. The same number with different content gives `409 process_version_conflict`. Open cases finish on their version unless there is a migration map |
| `Skill` | the package sets `spec.version`. A change to the contract, protocol, side effects, or risk level at the same version is an error that asks you to raise `spec.version` |
| `KnowledgePack` | `spec.version` is an integer. Different content at the same version is the error `knowledge_pack_conflict` |
| `Agent` | a new immutable revision appears only if the description has changed |

Mutable kinds are edited in place: `WorkRule`, `Role`, `WorkspaceType` by a
partial update; `Capability` is only created. No kind supports deletion. Task
types, project templates, work rules, agents, notification rules, processes,
and calendars are retired with the [installation's](#installation) `retire`
list.

### Renames { #renames }

Renaming an object is not deleting the old one and creating a new one. For
this, the manifest has `renames`, like `moved` in Terraform:

```yaml
spec:
  version: 0.3.0
  renames:
    - {kind: Process, from: access-intake, to: access-requests}
```

- `to` is an object of this package, and `from` is a key the package no
  longer has (`check`: the kind must be a catalog kind, and the `to` object
  must exist).
- The plan moves a process or a calendar together with its version history;
  the old key is retired: it opens no new cases (`409 process_retired`), and
  open ones finish.
- The plan does not move renames of other kinds; this is the warning
  `rename_not_planned`: the old object stays and a new one is created.
- `package-sdk edit rename --package <directory> --kind Process --from <key> --to <key>`
  renames the file and the key and appends `renames` itself.

## Installation { #installation }

The installation file says which packages are installed on a particular
deployment and where they come from. It lives in the installation's git,
separately from the packages. This section shows the file's shape; the whole
procedure (git sources, lock and cache, plan, console edits, apply,
retirement, release by tag) is in [Installation and release](install-and-release.md).

```yaml
apiVersion: taimen.ai/v1
kind: Installation
key: prod
spec:
  packages:
    - notifications                                   # installation directory: packages/notifications
    - {key: access-requests, path: ../access-requests} # path relative to the installation file
    - {key: helpdesk, git: https://git.example.com/example/helpdesk.git, ref: v0.2.0}
  knowledge:
    - {workspace: "${ACCESS_WORKSPACE_ID}", packs: ["access@1"]}
  retire:
    TaskType: [legacy-access-review]
```

| Source | Form | Package key |
|---|---|---|
| installation directory | key | equals the directory name in `packages/` next to the installation file (or `spec.packagesDir`) |
| path | `{key, path}` | from the manifest, checked against `key` |
| git | `{key, git, ref, path?}` | from the manifest, checked against `key` |

- `git` is `https://host/path` without credentials in the address, or
  `git@host:path`; access is provided by the git credential helper. `ref` is
  a tag only: branches and commits are not accepted. `path` is the package's
  subdirectory in the repository.
- `knowledge` says which ontologies to enable for a workspace; the set
  replaces the previous one entirely, and the plan shows the result and the
  difference.
- `retire` lists keys that the installation retires: `TaskType`,
  `ProjectTemplate`, `WorkRule`, `Agent`, `NotificationRule`, `Process`,
  `Calendar`.
- An empty `packages: []` is a valid installation: only the system type
  `task`.

### `packages.lock`: reproducibility

```bash
package-sdk lock --install installation.yaml
```

`lock` writes `packages.lock` (`package-sdk.lock/v1`) next to the
installation file: for each package, the source, the version, the tag's
commit (for git), and `contentHash`, the hash of the package's canonical set
of files. `plan` is built only from the pinned content:

| Refusal | When |
|---|---|
| `lock_required` | the package comes from git, and the lock has no entry for it |
| `source_ref_moved` | the tag in the source was moved after pinning |
| `content_mismatch` | the content diverged from `contentHash` |
| `lock_stale` | the lock does not match the installation: a package is missing, the source differs |

For packages from the installation directory and by path, the lock is
optional: they are already in the installation's git; but if a lock exists,
it covers all packages and is verified. The git source cache is
`$PACKAGE_SDK_CACHE`, otherwise `$XDG_CACHE_HOME/package-sdk` or
`~/.cache/package-sdk`.

### Plan and apply

```bash
package-sdk plan --install installation.yaml --server https://platform.example.com --out plan.json
package-sdk apply --plan plan.json --server https://platform.example.com
```

A `package-sdk.plan/v1` plan is a single document for all kinds, built
without a single write. Its sections are applied in order:

1. `catalog`: the kinds that the installer installs as core resources;
2. `core`: the core plan for packages with processes or calendars: for such a
   package, the core itself plans and installs task types, agents, calendars,
   processes, and work rules;
3. `knowledge`: registering ontologies and enabling them for workspaces;
4. `notification-rules`: notification rules that passed the service's check;
5. `retire`: retirement.

The plan records the deployment's core version, the hash of the pinned
sources (`lockHash`), the hash of the variable values (`variablesHash`), and
the `planHash` of the whole document. `apply` applies only an unmodified plan,
to the same deployment, after a human confirms in the terminal. Before each
section, it builds the section again and compares it with the plan: a
divergence gives `plan_stale` before the first write of that section.

!!! note "Sections are not atomic with respect to each other"
    Each write is idempotent. If an apply is interrupted between sections, a
    repeated `plan` shows the remainder, and a repeated `apply` delivers it.

## See also

- [Packages](index.md): the map of kinds and the author's path
- [A package in 10 minutes](quickstart.md)
- [Work: task types and roles](work.md)
- [Processes in a package](processes.md): case versions and migrations
- [Installation and release](install-and-release.md): lock, plan, apply, release by tag
- [Catalog packages](../control-plane/catalog-packages.md): how each kind maps to the API
- [Scenarios and the core plan](../processes/package-tests.md#plan): the core plan for processes
