
# package-sdk commands

Reference of the commands of the package author tool `package-sdk`: usage,
arguments, defaults, and subcommands. The tables are built from the tool's own
command-line parsers and repeat `package-sdk <command> --help`. This article is
for package authors; the order of working with the commands is described in the
[Author path](../packages/index.md#author-path), and installing the tool in [A
package in 10 minutes](../packages/quickstart.md).

!!! note "Extra dependencies are installed on demand"
    The tool is installed without additional dependencies; `sandbox` and the
    check by the core require the `sandbox` extra, `mcp` requires the `mcp`
    extra, and export and plan against a deployment through the MCP plugin's
    credential require the `connector` extra. Everything at once is
    `package-sdk[all]` (see [Package tests](../packages/testing.md#install)).

## Commands

<!-- generated:cli-package-sdk -->
_This section is generated from code; do not edit it by hand._

Commands: 17. Source: `sdk/package-sdk/src/package_sdk` (argparse parsers).

| Command | Purpose |
|---|---|
| [`init`](#cli-init) | package scaffold: manifest, process with a test, CI, README |
| [`add`](#cli-add) | scaffold of an object of any catalog kind |
| [`workflow`](#cli-workflow) | regenerate the CI workflow of a package by the layout of this installation |
| [`check`](#cli-check) | check packages: schema and references; with --server also by the core |
| [`test`](#cli-test) | package test pyramid in one command: check, skills, integration, scenarios |
| [`lock`](#cli-lock) | pin installation sources: commit and content hash (packages.lock) |
| [`cache`](#cli-cache) | git source cache (package-sdk cache prune) |
| [`plan`](#cli-plan) | build the one installation plan (all kinds) and save it with its hash |
| [`apply`](#cli-apply) | apply exactly the saved plan (after a human confirms) |
| [`export`](#cli-export) | export objects from Control Plane into a package |
| [`describe`](#cli-describe) | package installation prerequisites: variables, settings, agent nodes, ontologies, dependencies |
| [`docs`](#cli-docs) | generated README sections of a package |
| [`migrate-expr`](#cli-migrate-expr) | migrate legacy package expressions to CEL (diff; --write) |
| [`edit`](#cli-edit) | edit package files preserving the file style |
| [`sandbox`](#cli-sandbox) | package tests by the core's code in-process, without a stand |
| [`image`](#cli-image) | Dockerfile of a package integration image: observer or skill host |
| [`mcp`](#cli-mcp) | package author MCP server over stdio; stands — PACKAGE_SDK_SERVERS, session root — PACKAGE_SDK_ROOT, the client roots or the current directory |

### `package-sdk init` { #cli-init }

package scaffold: manifest, process with a test, CI, README

```text
usage: package-sdk init [-h] [--key KEY] [--display-name DISPLAY_NAME] [--license LICENSE]
                        [--integration] [--image] [--database]
                        dir
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `dir` | yes |  | package directory (new or empty) |
| `--key KEY` |  |  | package key; default: the directory name |
| `--display-name DISPLAY_NAME` |  |  | human-readable package name |
| `--license LICENSE` |  |  | package license (SPDX identifier) |
| `--integration` |  |  | integration code: observer and agent description |
| `--image` |  |  | Dockerfile of the integration image |
| `--database` |  |  | PostgreSQL service in CI for work rule and task type scenarios (default: if they already exist in the directory) |

### `package-sdk add` { #cli-add }

scaffold of an object of any catalog kind

```text
usage: package-sdk add [-h] [--package PACKAGE] kind key
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `kind` | yes |  | kind: TaskType, task-type, rule, process, … |
| `key` | yes |  | object key |
| `--package PACKAGE` |  | `.` | package directory (default: the current one) |

### `package-sdk workflow` { #cli-workflow }

regenerate the CI workflow of a package by the layout of this installation

```text
usage: package-sdk workflow [-h] [--check] [dir]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `dir` |  | `.` | package directory (default: .) |
| `--check` |  |  | exit 1 if the workflow differs; write nothing |

### `package-sdk check` { #cli-check }

check packages: schema and references; with --server also by the core

```text
usage: package-sdk check [-h] [--install INSTALL] [--package PACKAGE] [--server SERVER]
                         [--env ENV] [--workspace WORKSPACE] [--json] [--schema-only]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--install INSTALL` |  |  | installation file; without it, all packages in packages/ |
| `--package PACKAGE` |  |  | package (directory or key); may be repeated; repeatable |
| `--server SERVER` |  |  | Control Plane: check processes by the core (checkOnly) if it supports it |
| `--env ENV` |  |  | where to take package ${VARIABLES} from (default: the environment) |
| `--workspace WORKSPACE` |  |  | workspace whose roles and calendars the core check reads |
| `--json` |  |  | errors as JSON {code, severity, path, file, line, message, hint} |
| `--schema-only` |  |  | without the core's code: schema and references only (otherwise a missing core is an error) |

### `package-sdk test` { #cli-test }

package test pyramid in one command: check, skills, integration, scenarios

```text
usage: package-sdk test [-h] [--package PACKAGE] [--install INSTALL] [--test TEST]
                        [--server SERVER] [--env ENV] [--workspace WORKSPACE]
                        [--database-url DATABASE_URL] [--json]
                        [paths ...]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `paths`… |  |  | packages: directories with package.yaml or keys |
| `--package PACKAGE` |  |  | package (directory or key); may be repeated; repeatable |
| `--install INSTALL` |  |  | installation file: all of its packages |
| `--test TEST` |  |  | only the scenario with this name or file |
| `--server SERVER` |  |  | Control Plane: the server runs the scenarios; without it — the sandbox |
| `--env ENV` |  | `.env` | installation variables |
| `--workspace WORKSPACE` |  |  | with --server: the workspace whose roles, calendars and instances the run reads |
| `--database-url DATABASE_URL` |  |  | sandbox: an empty PostgreSQL database for rule and task type scenarios (or PACKAGE_SDK_SANDBOX_DATABASE_URL) |
| `--json` |  |  | pyramid report as a JSON document |

### `package-sdk lock` { #cli-lock }

pin installation sources: commit and content hash (packages.lock)

```text
usage: package-sdk lock [-h] --install INSTALL
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--install INSTALL` | yes |  | installation file |

### `package-sdk cache` { #cli-cache }

git source cache (package-sdk cache prune)

```text
usage: package-sdk cache [-h] {prune} ...
```

Subcommands: [`prune`](#cli-cache-prune).

#### `package-sdk cache prune` { #cli-cache-prune }

remove checkouts not referenced by any packages.lock of the current directory

```text
usage: package-sdk cache prune [-h] [--all] [--lock LOCK]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--all` |  |  | remove the whole cache: checkouts and source mirrors |
| `--lock LOCK` |  |  | take this lock file into account (may be repeated); by default all packages.lock under the current directory; repeatable |

### `package-sdk plan` { #cli-plan }

build the one installation plan (all kinds) and save it with its hash

```text
usage: package-sdk plan [-h] --install INSTALL --server SERVER --out OUT [--env ENV]
                        [--workspace WORKSPACE] [--replay-limit REPLAY_LIMIT]
                        [--overwrite-console] [--json]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--install INSTALL` | yes |  | installation file |
| `--server SERVER` | yes |  | — |
| `--out OUT` | yes |  | plan file (package-sdk.plan/v1) for apply --plan |
| `--env ENV` |  | `.env` | where to take package ${VARIABLES} from |
| `--workspace WORKSPACE` |  |  | workspace of the package processes (the core's workspaceId) |
| `--replay-limit REPLAY_LIMIT` |  | `50` | instances per process for replay (0–200) |
| `--overwrite-console` |  |  | overwrite fields a human edited in the console since the last apply (by default they are kept); the flag is stored in the plan under its hash |
| `--json` |  |  | the plan as a JSON document |

### `package-sdk apply` { #cli-apply }

apply exactly the saved plan (after a human confirms)

```text
usage: package-sdk apply [-h] --plan PLAN --server SERVER [--env ENV]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--plan PLAN` | yes |  | plan file from plan --out |
| `--server SERVER` | yes |  | stand; must match the one the plan was built for |
| `--env ENV` |  | `.env` | where to take package ${VARIABLES} from |

### `package-sdk export` { #cli-export }

export objects from Control Plane into a package

```text
usage: package-sdk export [-h] [--server SERVER] [--env ENV] [--workspace WORKSPACE] --kind
                          {KnowledgePack,WorkspaceType,Capability,ConnectionType,Role,Skill,ArtifactType,TaskType,Agent,ProjectTemplate,Calendar,Process,WorkRule,NotificationRule}
                          --key KEY [--version VERSION] --package PACKAGE
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--server SERVER` |  |  | Control Plane; not needed for NotificationRule |
| `--env ENV` |  | `.env` | installation variables file: NOTIFICATION_SERVICE_URL for NotificationRule, values ${…} — so that exporting Process and Calendar returns them as variable references |
| `--workspace WORKSPACE` |  |  | workspace of the core plan for console fields (Process and Calendar) |
| `--kind KIND` | yes |  | values: `KnowledgePack`, `WorkspaceType`, `Capability`, `ConnectionType`, `Role`, `Skill`, `ArtifactType`, `TaskType`, `Agent`, `ProjectTemplate`, `Calendar`, `Process`, `WorkRule`, `NotificationRule` |
| `--key KEY` | yes |  | repeatable |
| `--version VERSION` |  |  | version (default: the newest active) |
| `--package PACKAGE` | yes |  | package directory, e.g. packages/&lt;package&gt; |

### `package-sdk describe` { #cli-describe }

package installation prerequisites: variables, settings, agent nodes, ontologies, dependencies

```text
usage: package-sdk describe [-h] [--env-example] [--json] path
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `path` | yes |  | package directory |
| `--env-example` |  |  | template of the installation variables file |
| `--json` |  |  | the same as JSON |

### `package-sdk docs` { #cli-docs }

generated README sections of a package

```text
usage: package-sdk docs [-h] [--write | --check] path
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `path` | yes |  | package directory |
| `--write` |  |  | update the section in README.md; not together with `--check` |
| `--check` |  |  | exit 1 if the README section is outdated; not together with `--write` |

### `package-sdk migrate-expr` { #cli-migrate-expr }

migrate legacy package expressions to CEL (diff; --write)

```text
usage: package-sdk migrate-expr [-h] --package PACKAGE [--write]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--package PACKAGE` | yes |  | package (directory or key) |
| `--write` |  |  | write, preserving the file style |

### `package-sdk edit` { #cli-edit }

edit package files preserving the file style

```text
usage: package-sdk edit [-h] [--json] [--dry-run]
                        {add-step,add-stage,add-decision-row,add-rule,add-form-field,rename,set}
                        ...
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--json` |  |  | result and errors as JSON |
| `--dry-run` |  |  | show the diff, write nothing |

Subcommands: [`add-step`](#cli-edit-add-step), [`add-stage`](#cli-edit-add-stage), [`add-decision-row`](#cli-edit-add-decision-row), [`add-rule`](#cli-edit-add-rule), [`add-form-field`](#cli-edit-add-form-field), [`rename`](#cli-edit-rename), [`set`](#cli-edit-set).

#### `package-sdk edit add-step` { #cli-edit-add-step }

add a step to a stage or a step block

```text
usage: package-sdk edit add-step [-h] --file FILE [--json] [--dry-run] --in TARGET [--block BLOCK]
                                 --step STEP [--after AFTER] [--before BEFORE]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--file FILE` | yes |  | process file (processes/&lt;key&gt;.yaml) |
| `--json` |  |  | — |
| `--dry-run` |  |  | — |
| `--in TARGET` | yes |  | id of a stage, a step with do, a fork branch or a timer |
| `--block BLOCK` |  |  | block name: steps\|discretionary for a stage, do\|onCompensate for a step |
| `--step STEP` | yes |  | YAML (flow or block); @file reads it from a file |
| `--after AFTER` |  |  | — |
| `--before BEFORE` |  |  | — |

#### `package-sdk edit add-stage` { #cli-edit-add-stage }

add a stage

```text
usage: package-sdk edit add-stage [-h] --file FILE [--json] [--dry-run] --stage STAGE
                                  [--after AFTER] [--before BEFORE]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--file FILE` | yes |  | process file (processes/&lt;key&gt;.yaml) |
| `--json` |  |  | — |
| `--dry-run` |  |  | — |
| `--stage STAGE` | yes |  | YAML (flow or block); @file reads it from a file |
| `--after AFTER` |  |  | — |
| `--before BEFORE` |  |  | — |

#### `package-sdk edit add-decision-row` { #cli-edit-add-decision-row }

add a decision table row

```text
usage: package-sdk edit add-decision-row [-h] --file FILE [--json] [--dry-run] --table TABLE --row
                                         ROW [--index INDEX]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--file FILE` | yes |  | process file (processes/&lt;key&gt;.yaml) |
| `--json` |  |  | — |
| `--dry-run` |  |  | — |
| `--table TABLE` | yes |  | — |
| `--row ROW` | yes |  | YAML (flow or block); @file reads it from a file |
| `--index INDEX` |  |  | row position (default: at the end) |

#### `package-sdk edit add-rule` { #cli-edit-add-rule }

add a rule: a table row (--table) or an event reaction (--on-event)

```text
usage: package-sdk edit add-rule [-h] --file FILE [--json] [--dry-run] [--table TABLE] [--row ROW]
                                 [--on-event ON_EVENT] [--index INDEX]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--file FILE` | yes |  | process file (processes/&lt;key&gt;.yaml) |
| `--json` |  |  | — |
| `--dry-run` |  |  | — |
| `--table TABLE` |  |  | — |
| `--row ROW` |  |  | YAML (flow or block); @file reads it from a file |
| `--on-event ON_EVENT` |  |  | YAML (flow or block); @file reads it from a file |
| `--index INDEX` |  |  | — |

#### `package-sdk edit add-form-field` { #cli-edit-add-form-field }

add a field to the form of a human step

```text
usage: package-sdk edit add-form-field [-h] --file FILE [--json] [--dry-run] --step STEP_ID --name
                                       NAME --schema SCHEMA [--required] [--label LABEL]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--file FILE` | yes |  | process file (processes/&lt;key&gt;.yaml) |
| `--json` |  |  | — |
| `--dry-run` |  |  | — |
| `--step STEP_ID` | yes |  | — |
| `--name NAME` | yes |  | — |
| `--schema SCHEMA` | yes |  | YAML (flow or block); @file reads it from a file |
| `--required` |  |  | — |
| `--label LABEL` |  |  | label in uischema, if the form has uischema.elements |

#### `package-sdk edit rename` { #cli-edit-rename }

rename a process element or a package object

```text
usage: package-sdk edit rename [-h] [--file FILE] [--json] [--dry-run] [--package PACKAGE]
                               [--kind KIND] --from OLD --to NEW [--no-migration]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--file FILE` |  |  | process file (processes/&lt;key&gt;.yaml) |
| `--json` |  |  | — |
| `--dry-run` |  |  | — |
| `--package PACKAGE` |  |  | package directory — rename an object (renames in package.yaml) |
| `--kind KIND` |  |  | object kind for --package (default: Process) |
| `--from OLD` | yes |  | — |
| `--to NEW` | yes |  | — |
| `--no-migration` |  |  | do not append migrations (the process is not published yet) |

#### `package-sdk edit set` { #cli-edit-set }

write a value at a path

```text
usage: package-sdk edit set [-h] --file FILE [--json] [--dry-run] --path PATH --value VALUE
                            [--string]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--file FILE` | yes |  | process file (processes/&lt;key&gt;.yaml) |
| `--json` |  |  | — |
| `--dry-run` |  |  | — |
| `--path PATH` | yes |  | spec.stages[go-no-go].exit; an index or an id in brackets |
| `--value VALUE` | yes |  | YAML value |
| `--string` |  |  | the value is a string as is, without YAML parsing |

### `package-sdk sandbox` { #cli-sandbox }

package tests by the core's code in-process, without a stand

```text
usage: package-sdk sandbox [-h] [--test TEST] [--json] [--env ENV] [--database-url DATABASE_URL]
                           [packages ...]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `packages`… |  |  | package keys or directories with package.yaml; by default all packages with tests |
| `--test TEST` |  |  | path of a test file in the package (tests/&lt;name&gt;.test.yaml); repeatable |
| `--json` |  |  | PackageTestOut responses as JSON |
| `--env ENV` |  | `.env` | installation variables file |
| `--database-url DATABASE_URL` |  |  | an empty PostgreSQL database for work rule and task type tests (or PACKAGE_SDK_SANDBOX_DATABASE_URL) |

### `package-sdk image` { #cli-image }

Dockerfile of a package integration image: observer or skill host

```text
usage: package-sdk image [-h] {observer,skills} ...
```

Subcommands: [`observer`](#cli-image-observer), [`skills`](#cli-image-skills).

#### `package-sdk image observer` { #cli-image-observer }

Dockerfile of the observer image

```text
usage: package-sdk image observer [-h] [--package PACKAGE] [--source SOURCE] [--base BASE]
                                  [--out OUT] [--entrypoint ENTRYPOINT]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--package PACKAGE` |  | `.` | package directory |
| `--source SOURCE` |  |  | python project of the integration in the package (default integration/) |
| `--base BASE` |  |  | base image of the delivery (otherwise --build-arg at build time); observer |
| `--out OUT` |  |  | where to write; .dockerignore is written alongside, in the package directory |
| `--entrypoint ENTRYPOINT` |  |  | observer module:function — checked at build time |

#### `package-sdk image skills` { #cli-image-skills }

Dockerfile of the skills image

```text
usage: package-sdk image skills [-h] [--package PACKAGE] [--source SOURCE] [--base BASE]
                                [--out OUT] --modules MODULES
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--package PACKAGE` |  | `.` | package directory |
| `--source SOURCE` |  |  | python project of the integration in the package (default integration/) |
| `--base BASE` |  |  | base image of the delivery (otherwise --build-arg at build time); runner |
| `--out OUT` |  |  | where to write; .dockerignore is written alongside, in the package directory |
| `--modules MODULES` | yes |  | comma-separated modules or skill entrypoints |

### `package-sdk mcp` { #cli-mcp }

package author MCP server over stdio; stands — PACKAGE_SDK_SERVERS, session root — PACKAGE_SDK_ROOT, the client roots or the current directory

```text
usage: package-sdk mcp [-h]
```
<!-- /generated:cli-package-sdk -->

## Tokens and variables

| Variable | Read by | Purpose |
|---|---|---|
| `CP_TOKEN` | `plan`, `apply`, `export`, `test --server`, `check --server` | access token with audience `control-plane`; without it, the MCP plugin's credential through the `connector` extra |
| `NOTIFY_TOKEN` | `plan`, `apply`, `export --kind NotificationRule` | access token with audience `notification-service` (scope `notifications:admin`) for notification rules |
| `PACKAGE_SDK_SANDBOX_DATABASE_URL` | `test`, `sandbox` | an empty PostgreSQL database of the sandbox for rule and task type scenarios (the same as `--database-url`) |

## See also

- [Package schema](package-schema.md)
- [Author path](../packages/index.md#author-path)
- [Package tests](../packages/testing.md)
- [Installation and release](../packages/install-and-release.md)
- [Package author in Claude Code](../packages/author-plugin.md)
