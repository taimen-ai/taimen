# Команды package-sdk

Справочник команд инструмента автора пакетов `package-sdk`: использование,
аргументы, значения по умолчанию и подкоманды. Таблицы построены из парсеров
командной строки самого инструмента и повторяют `package-sdk <команда> --help`.
Статья для авторов пакетов; порядок работы с командами описан в [Пути
автора](../packages/index.md#author-path), установка инструмента — в [Пакете за
10 минут](../packages/quickstart.md).

!!! note "Лишние зависимости ставятся по требованию"
    Инструмент ставится без дополнительных зависимостей; `sandbox` и проверка
    ядром требуют extra `sandbox`, `mcp` — extra `mcp`, выгрузка и план со
    стендом через credential MCP-плагина — extra `connector`. Всё сразу —
    `package-sdk[all]` (см. [Тесты пакета](../packages/testing.md#install)).

## Команды

<!-- generated:cli-package-sdk -->
_Раздел генерируется из кода — не правьте его руками._

Команд: 17. Источник: `sdk/package-sdk/src/package_sdk` (парсеры argparse).

| Команда | Назначение |
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

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `dir` | да |  | package directory (new or empty) |
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

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `kind` | да |  | kind: TaskType, task-type, rule, process, … |
| `key` | да |  | object key |
| `--package PACKAGE` |  | `.` | package directory (default: the current one) |

### `package-sdk workflow` { #cli-workflow }

regenerate the CI workflow of a package by the layout of this installation

```text
usage: package-sdk workflow [-h] [--check] [dir]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `dir` |  | `.` | package directory (default: .) |
| `--check` |  |  | exit 1 if the workflow differs; write nothing |

### `package-sdk check` { #cli-check }

check packages: schema and references; with --server also by the core

```text
usage: package-sdk check [-h] [--install INSTALL] [--package PACKAGE] [--server SERVER]
                         [--env ENV] [--workspace WORKSPACE] [--json] [--schema-only]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--install INSTALL` |  |  | installation file; without it, all packages in packages/ |
| `--package PACKAGE` |  |  | package (directory or key); may be repeated; можно несколько раз |
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

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `paths`… |  |  | packages: directories with package.yaml or keys |
| `--package PACKAGE` |  |  | package (directory or key); may be repeated; можно несколько раз |
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

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--install INSTALL` | да |  | installation file |

### `package-sdk cache` { #cli-cache }

git source cache (package-sdk cache prune)

```text
usage: package-sdk cache [-h] {prune} ...
```

Подкоманды: [`prune`](#cli-cache-prune).

#### `package-sdk cache prune` { #cli-cache-prune }

remove checkouts not referenced by any packages.lock of the current directory

```text
usage: package-sdk cache prune [-h] [--all] [--lock LOCK]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--all` |  |  | remove the whole cache: checkouts and source mirrors |
| `--lock LOCK` |  |  | take this lock file into account (may be repeated); by default all packages.lock under the current directory; можно несколько раз |

### `package-sdk plan` { #cli-plan }

build the one installation plan (all kinds) and save it with its hash

```text
usage: package-sdk plan [-h] --install INSTALL --server SERVER --out OUT [--env ENV]
                        [--workspace WORKSPACE] [--replay-limit REPLAY_LIMIT]
                        [--overwrite-console] [--json]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--install INSTALL` | да |  | installation file |
| `--server SERVER` | да |  | — |
| `--out OUT` | да |  | plan file (package-sdk.plan/v1) for apply --plan |
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

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--plan PLAN` | да |  | plan file from plan --out |
| `--server SERVER` | да |  | stand; must match the one the plan was built for |
| `--env ENV` |  | `.env` | where to take package ${VARIABLES} from |

### `package-sdk export` { #cli-export }

export objects from Control Plane into a package

```text
usage: package-sdk export [-h] [--server SERVER] [--env ENV] [--workspace WORKSPACE] --kind
                          {KnowledgePack,WorkspaceType,Capability,ConnectionType,Role,Skill,ArtifactType,TaskType,Agent,ProjectTemplate,Calendar,Process,WorkRule,NotificationRule}
                          --key KEY [--version VERSION] --package PACKAGE
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--server SERVER` |  |  | Control Plane; not needed for NotificationRule |
| `--env ENV` |  | `.env` | installation variables file: NOTIFICATION_SERVICE_URL for NotificationRule, values ${…} — so that exporting Process and Calendar returns them as variable references |
| `--workspace WORKSPACE` |  |  | workspace of the core plan for console fields (Process and Calendar) |
| `--kind KIND` | да |  | значения: `KnowledgePack`, `WorkspaceType`, `Capability`, `ConnectionType`, `Role`, `Skill`, `ArtifactType`, `TaskType`, `Agent`, `ProjectTemplate`, `Calendar`, `Process`, `WorkRule`, `NotificationRule` |
| `--key KEY` | да |  | можно несколько раз |
| `--version VERSION` |  |  | version (default: the newest active) |
| `--package PACKAGE` | да |  | package directory, e.g. packages/&lt;package&gt; |

### `package-sdk describe` { #cli-describe }

package installation prerequisites: variables, settings, agent nodes, ontologies, dependencies

```text
usage: package-sdk describe [-h] [--env-example] [--json] path
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `path` | да |  | package directory |
| `--env-example` |  |  | template of the installation variables file |
| `--json` |  |  | the same as JSON |

### `package-sdk docs` { #cli-docs }

generated README sections of a package

```text
usage: package-sdk docs [-h] [--write | --check] path
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `path` | да |  | package directory |
| `--write` |  |  | update the section in README.md; не вместе с `--check` |
| `--check` |  |  | exit 1 if the README section is outdated; не вместе с `--write` |

### `package-sdk migrate-expr` { #cli-migrate-expr }

migrate legacy package expressions to CEL (diff; --write)

```text
usage: package-sdk migrate-expr [-h] --package PACKAGE [--write]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--package PACKAGE` | да |  | package (directory or key) |
| `--write` |  |  | write, preserving the file style |

### `package-sdk edit` { #cli-edit }

edit package files preserving the file style

```text
usage: package-sdk edit [-h] [--json] [--dry-run]
                        {add-step,add-stage,add-decision-row,add-rule,add-form-field,rename,set}
                        ...
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--json` |  |  | result and errors as JSON |
| `--dry-run` |  |  | show the diff, write nothing |

Подкоманды: [`add-step`](#cli-edit-add-step), [`add-stage`](#cli-edit-add-stage), [`add-decision-row`](#cli-edit-add-decision-row), [`add-rule`](#cli-edit-add-rule), [`add-form-field`](#cli-edit-add-form-field), [`rename`](#cli-edit-rename), [`set`](#cli-edit-set).

#### `package-sdk edit add-step` { #cli-edit-add-step }

add a step to a stage or a step block

```text
usage: package-sdk edit add-step [-h] --file FILE [--json] [--dry-run] --in TARGET [--block BLOCK]
                                 --step STEP [--after AFTER] [--before BEFORE]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--file FILE` | да |  | process file (processes/&lt;key&gt;.yaml) |
| `--json` |  |  | — |
| `--dry-run` |  |  | — |
| `--in TARGET` | да |  | id of a stage, a step with do, a fork branch or a timer |
| `--block BLOCK` |  |  | block name: steps\|discretionary for a stage, do\|onCompensate for a step |
| `--step STEP` | да |  | YAML (flow or block); @file reads it from a file |
| `--after AFTER` |  |  | — |
| `--before BEFORE` |  |  | — |

#### `package-sdk edit add-stage` { #cli-edit-add-stage }

add a stage

```text
usage: package-sdk edit add-stage [-h] --file FILE [--json] [--dry-run] --stage STAGE
                                  [--after AFTER] [--before BEFORE]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--file FILE` | да |  | process file (processes/&lt;key&gt;.yaml) |
| `--json` |  |  | — |
| `--dry-run` |  |  | — |
| `--stage STAGE` | да |  | YAML (flow or block); @file reads it from a file |
| `--after AFTER` |  |  | — |
| `--before BEFORE` |  |  | — |

#### `package-sdk edit add-decision-row` { #cli-edit-add-decision-row }

add a decision table row

```text
usage: package-sdk edit add-decision-row [-h] --file FILE [--json] [--dry-run] --table TABLE --row
                                         ROW [--index INDEX]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--file FILE` | да |  | process file (processes/&lt;key&gt;.yaml) |
| `--json` |  |  | — |
| `--dry-run` |  |  | — |
| `--table TABLE` | да |  | — |
| `--row ROW` | да |  | YAML (flow or block); @file reads it from a file |
| `--index INDEX` |  |  | row position (default: at the end) |

#### `package-sdk edit add-rule` { #cli-edit-add-rule }

add a rule: a table row (--table) or an event reaction (--on-event)

```text
usage: package-sdk edit add-rule [-h] --file FILE [--json] [--dry-run] [--table TABLE] [--row ROW]
                                 [--on-event ON_EVENT] [--index INDEX]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--file FILE` | да |  | process file (processes/&lt;key&gt;.yaml) |
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

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--file FILE` | да |  | process file (processes/&lt;key&gt;.yaml) |
| `--json` |  |  | — |
| `--dry-run` |  |  | — |
| `--step STEP_ID` | да |  | — |
| `--name NAME` | да |  | — |
| `--schema SCHEMA` | да |  | YAML (flow or block); @file reads it from a file |
| `--required` |  |  | — |
| `--label LABEL` |  |  | label in uischema, if the form has uischema.elements |

#### `package-sdk edit rename` { #cli-edit-rename }

rename a process element or a package object

```text
usage: package-sdk edit rename [-h] [--file FILE] [--json] [--dry-run] [--package PACKAGE]
                               [--kind KIND] --from OLD --to NEW [--no-migration]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--file FILE` |  |  | process file (processes/&lt;key&gt;.yaml) |
| `--json` |  |  | — |
| `--dry-run` |  |  | — |
| `--package PACKAGE` |  |  | package directory — rename an object (renames in package.yaml) |
| `--kind KIND` |  |  | object kind for --package (default: Process) |
| `--from OLD` | да |  | — |
| `--to NEW` | да |  | — |
| `--no-migration` |  |  | do not append migrations (the process is not published yet) |

#### `package-sdk edit set` { #cli-edit-set }

write a value at a path

```text
usage: package-sdk edit set [-h] --file FILE [--json] [--dry-run] --path PATH --value VALUE
                            [--string]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--file FILE` | да |  | process file (processes/&lt;key&gt;.yaml) |
| `--json` |  |  | — |
| `--dry-run` |  |  | — |
| `--path PATH` | да |  | spec.stages[go-no-go].exit; an index or an id in brackets |
| `--value VALUE` | да |  | YAML value |
| `--string` |  |  | the value is a string as is, without YAML parsing |

### `package-sdk sandbox` { #cli-sandbox }

package tests by the core's code in-process, without a stand

```text
usage: package-sdk sandbox [-h] [--test TEST] [--json] [--env ENV] [--database-url DATABASE_URL]
                           [packages ...]
```

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `packages`… |  |  | package keys or directories with package.yaml; by default all packages with tests |
| `--test TEST` |  |  | path of a test file in the package (tests/&lt;name&gt;.test.yaml); можно несколько раз |
| `--json` |  |  | PackageTestOut responses as JSON |
| `--env ENV` |  | `.env` | installation variables file |
| `--database-url DATABASE_URL` |  |  | an empty PostgreSQL database for work rule and task type tests (or PACKAGE_SDK_SANDBOX_DATABASE_URL) |

### `package-sdk image` { #cli-image }

Dockerfile of a package integration image: observer or skill host

```text
usage: package-sdk image [-h] {observer,skills} ...
```

Подкоманды: [`observer`](#cli-image-observer), [`skills`](#cli-image-skills).

#### `package-sdk image observer` { #cli-image-observer }

Dockerfile of the observer image

```text
usage: package-sdk image observer [-h] [--package PACKAGE] [--source SOURCE] [--base BASE]
                                  [--out OUT] [--entrypoint ENTRYPOINT]
```

| Аргумент | Обязателен | По умолчанию | Описание |
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

| Аргумент | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--package PACKAGE` |  | `.` | package directory |
| `--source SOURCE` |  |  | python project of the integration in the package (default integration/) |
| `--base BASE` |  |  | base image of the delivery (otherwise --build-arg at build time); runner |
| `--out OUT` |  |  | where to write; .dockerignore is written alongside, in the package directory |
| `--modules MODULES` | да |  | comma-separated modules or skill entrypoints |

### `package-sdk mcp` { #cli-mcp }

package author MCP server over stdio; stands — PACKAGE_SDK_SERVERS, session root — PACKAGE_SDK_ROOT, the client roots or the current directory

```text
usage: package-sdk mcp [-h]
```
<!-- /generated:cli-package-sdk -->

## Токены и переменные

| Переменная | Кто читает | Назначение |
|---|---|---|
| `CP_TOKEN` | `plan`, `apply`, `export`, `test --server`, `check --server` | access token audience `control-plane`; без неё — credential MCP-плагина через extra `connector` |
| `NOTIFY_TOKEN` | `plan`, `apply`, `export --kind NotificationRule` | access token audience `notification-service` (scope `notifications:admin`) для правил уведомлений |
| `PACKAGE_SDK_SANDBOX_DATABASE_URL` | `test`, `sandbox` | пустая база PostgreSQL песочницы для сценариев правил и типов задач (то же, что `--database-url`) |

## См. также

- [Схема пакета](package-schema.md)
- [Путь автора](../packages/index.md#author-path)
- [Тесты пакета](../packages/testing.md)
- [Установка и выпуск](../packages/install-and-release.md)
- [Автор пакетов в Claude Code](../packages/author-plugin.md)
