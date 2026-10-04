
<!--
This page is executed by the "quickstart" job in the package-sdk CI (ci/quickstart.py, SC-001):
bash blocks are commands, blocks marked "quickstart: file <path>" are files, "skip" marks
steps that need a deployment. A YAML block without a marker or an unknown substitution <…> breaks the job.
When you change commands or files, move the pin in package-sdk (pin update).
-->
# A package in 10 minutes

A step-by-step path from an empty directory to a package with a task type, a
work rule, and a process that passes the check and the tests without a
deployment, and then on to installation on a developer deployment
according to a plan. This page is for an author who sees `package-sdk` for
the first time. Concepts are in the [section overview](index.md).

The example is the `access-requests` package ("access requests"): an access
request for a resource opens a case, the owner decides on it in a task, and
the case closes; a reopened request makes a rule file a new review task.

## What you need

| What | Why |
|---|---|
| `git`, [uv](https://docs.astral.sh/uv/), Python 3.12+ | component clones and tool installation |
| Docker (or any PostgreSQL 16) | an empty database for rule and task type scenarios |
| A developer deployment and a token with the `packages.plan` permission and permissions for the object kinds being installed (`task_types.manage`, `agents.manage`, `processes.write`, `calendars.write`, `rules.write`: `apply` re-checks every change against them; `org.manage`: package roles, which the `catalog` section creates through `POST /roles`) | only for the last step, `plan` and `apply` |

## 1. Install package-sdk { #install }

Checks and tests without a deployment are executed by **the core code**: the
`sandbox` extra installs the `control-plane` package next to the tool.
Platform components are not installed from the public package index: they are
connected as sources, in the layout of the delivery's root repository
(`services/`, `sdk/`).

```bash
mkdir taimen-src && cd taimen-src
git clone --branch <tag> https://github.com/taimen-ai/package-sdk.git sdk/package-sdk
git clone --branch <core tag> https://github.com/taimen-ai/control-plane.git services/control-plane
git clone --branch <tag> https://github.com/taimen-ai/platform-auth-sdk.git sdk/platform-auth-sdk
uv tool install "./sdk/package-sdk[sandbox]"
package-sdk --version
```

- Take the tags (`<tag>`) from a single platform release. `<core tag>` is
  the Control Plane release you will install the package into:
  `init` writes compatibility with exactly its minor version into the
  manifest.
- There is no summary table "platform release → component tags" yet. The
  compatible revisions are the ones the delivery's root repository pins at the
  release tag: `git submodule status` in its clone at that tag prints the
  revision of every component (see [Upgrades](../operations/upgrades.md)). A
  clone of the root repository with its submodules is already laid out the way
  `uv tool install` needs.
- The `skills`, `mcp`, and `all` extras need one more neighbor, `skill-sdk`
  (`git clone --branch <tag> https://github.com/taimen-ai/skill-sdk.git sdk/skill-sdk`
  next to the other SDKs): without it, installing with these extras fails. Which neighbors
  each extra needs is in [Package tests](testing.md#install).
- The extra installs the neighboring directories in editable mode: the clones
  must stay in place while the tool is installed.
- The `package-sdk` command without arguments prints the list of commands.

!!! tip "Without the core code"
    `uv tool install ./sdk/package-sdk` without `[sandbox]` installs only the tool.
    Then `check` validates the schema and references and exits with the error
    `доменные валидаторы ядра не импортируются` ("core domain validators cannot
    be imported"): it will not silently limit itself to the schema. The
    explicit schema-only mode is `check --schema-only`. Without the core code,
    `test` goes no further than the check stage.

## 2. Create a package { #init }

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

(`создан` means "created".) The scaffold passes the check and its own test
right away. It contains:

- `package.yaml`: the package key (the directory name by default), version
  `0.1.0`, `engines` with the core version range, empty `variables`. The
  package directory must keep being named after its key: `check` and `test`
  by a directory path compare them (see [Anatomy](anatomy.md#layout));
- a process keyed by the package, its **identity**, the agent
  `access-requests-process` (on whose behalf the process creates tasks), and
  the **owner role** `access-requests-owner`;
- a process test, a CI scaffold, and a README with a section that
  `package-sdk docs` generates.

The first line of the YAML files that `init` and `add` write is the comment
`# yaml-language-server: $schema=…` with a link to the schema of the installed
SDK: an editor with YAML Language Server support suggests fields and
highlights errors. The examples below omit this line. When you replace a
file's contents, keep it: it does not affect the check or the tests.

!!! warning "The schema link is a path on your machine"
    `$schema=…` is a relative path from the file to the schema in the
    environment of the installed tool. For a colleague with another tools
    directory, the link in git does not open. There is no stable URL of a
    release's schema yet: for a shared repository, replace the path with the
    path to `schema/v1/object.schema.json` (`test.schema.json` for scenarios)
    in a `package-sdk` clone by your team's convention, or remove the line: it
    does not affect the check or the tests.

## 3. Task type { #task-type }

```bash
package-sdk add task-type access-review
```

`add` writes a minimal `spec` that passes the schema and the core checks, and
lists the optional fields with descriptions from the schema in comments.
Replace the contents of `task-types/access-review.yaml`:

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

Task fields are `fieldSchema`, statuses and transitions are
`lifecycleSchema`, and the text for the executor is `instructions`. What else
a task type can do is in [Work](work.md#task-types).

## 4. Process { #process }

Replace the contents of `processes/access-requests.yaml`: the observation
`access.requested` opens a case, the `human` step creates a task of type
`access-review` for the owner role, its result goes into the case data, and
the case closes.

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

The `on` key is quoted so that tools based on YAML 1.2 and YAML 1.1 read the
file the same way.

The process test: replace `tests/access-requests.test.yaml`:

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

`given.principals` says who holds the role in the test; `complete` delivers
the step's task on behalf of `alice` with a form result.

## 5. Work rule { #rule }

```bash
package-sdk add rule access-reopened
```

Replace the contents of `rules/access-reopened.yaml`:

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

Two rule tests, one for each branch of the condition.
`tests/access-reopened.test.yaml`:

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

## 6. Check { #check }

```bash
package-sdk check --package .
```

```text
ok: пакетов 1, объектов 5, тестов 3
```

(Packages: 1, objects: 5, tests: 3.) `check` validates the files against the
schema, the references between objects (rule → task type, process → agent and
role, test → its object), and the manifest, and runs the core domain
validators: task types, rules, skills, agents. The core checks the process
language (expressions, data, step reachability) before the scenarios in
`test` (and with `check --server`). An error is printed with the file and a
hint; `--json` returns the findings as a document.

## 7. Run the tests { #test }

Rule and task type scenarios are executed by the core application code in a
transaction that is always rolled back, which requires an empty PostgreSQL
database. The sandbox applies the core schema to it and creates its own
tenant. Start a database and pass its address:

<!-- quickstart: requires docker -->
```bash
docker run -d --rm --name package-sandbox-db \
  -e POSTGRES_PASSWORD=sandbox -p 127.0.0.1:55432:5432 postgres:16-alpine
for _ in $(seq 30); do   # the database takes a few seconds to start
  docker exec package-sandbox-db pg_isready -q -h 127.0.0.1 -U postgres && break
  sleep 1
done
export PACKAGE_SDK_SANDBOX_DATABASE_URL=postgresql://postgres:sandbox@127.0.0.1:55432/postgres
```

Run the tests:

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

`test` is a single command for the whole pyramid: the check, the skill
contracts of the integration code, its unit tests, and the package scenarios.
This package has no integration code, so the two middle stages are skipped;
that is not a failure. The output lists the stages (`проверка`: check,
`контракты скиллов`: skill contracts, `тесты кода интеграции`: integration
code tests, `сценарии пакета`: package scenarios) and the coverage
(`покрытие`). The database address can also be passed with the
`--database-url` flag.

!!! warning "Without a database the run is not green"
    If there is no database, rule and task type scenarios are marked `SKIP`
    with the finding `sandbox_database_required`, the scenario stage is
    `FAIL`, and the exit code is `1`. Such tests are never skipped silently.
    Process scenarios do not need a database.

You can stop the database container when you are done:
`docker stop package-sandbox-db`.

## 8. Describe the package { #describe }

From the package directory:

```bash
package-sdk describe .
package-sdk docs . --write
```

`describe` prints what an installation needs: compatibility, dependencies,
variables, agents and node labels, ontologies. `docs --write` updates the
generated README section (objects, variables, requirements, agents);
`docs --check` fails in CI if the section is out of date.

## 9. Install on a developer deployment { #deploy }

An installation is a separate file: which packages to install and where from.
It lives next to the package directory, so go back to the parent directory:

```bash
cd ..
```

and put `installation.yaml` there:

<!-- quickstart: file installation.yaml -->
```yaml
apiVersion: taimen.ai/v1
kind: Installation
key: dev
spec:
  packages:
    - {key: access-requests, path: access-requests}
```

Pin the sources: `package-sdk lock` writes `packages.lock` next to it with the
version and content hash of each package (for a package from git, also the
tag's commit):

```bash
package-sdk lock --install installation.yaml
```

```text
   access-requests 0.1.0: access-requests sha256:…
записан packages.lock
```

(`записан` means "written".) Plan and apply need a deployment. The token is
the `CP_TOKEN` variable (an access token for the `control-plane` audience) or
an IAM credential in `~/.config/iam/credentials.json`:

<!-- quickstart: skip needs a developer deployment -->
```bash
export CP_TOKEN=<access token>
package-sdk plan --install installation.yaml \
    --server https://platform.example.com --out plan.json
package-sdk apply --plan plan.json --server https://platform.example.com
```

- `plan` checks the packages, compares the deployment's core version with
  `engines`, builds changes of all kinds, and saves them to `plan.json`
  without writing anything.
- `apply` shows the plan, asks for confirmation in the terminal, and applies
  exactly that plan. If the deployment or the files changed after `plan`,
  it stops with `plan_stale` before the first write; build the plan again.

More about installation, variables, and sources is in
[Package anatomy](anatomy.md#installation).

## Common problems

| Symptom | Cause | What to do |
|---|---|---|
| `check`: `доменные валидаторы ядра не импортируются — проверена только схема формата` ("core domain validators cannot be imported; only the format schema was checked") | the tool was installed without `[sandbox]` | reinstall with `uv tool install --reinstall "./sdk/package-sdk[sandbox]"` |
| `test`: `sandbox_database_required`, the run is `FAIL` | no database for rule and task type scenarios | set `PACKAGE_SDK_SANDBOX_DATABASE_URL` or `--database-url` |
| `engines_mismatch` among the warnings | the package declares a different core version than the core code next to the tool | install a core clone of the right tag or fix `engines` |
| `init`: `уже есть — заготовка не перезаписывает файлы` ("already exists; the scaffold does not overwrite files") | the directory already contains package files | use an empty directory; the scaffold leaves `.gitignore` as it is and appends the generated section to an existing `README.md` |
| `plan`: `версия ядра не прочитана … план не строится` ("the core version was not read … the plan is not built") | the deployment is unreachable at `--server` | check the address and the network; `plan` and `apply` do not work without a deployment |
| `apply`: `нужен ответ человека в терминале, применение отменено` ("a human answer in the terminal is required; apply cancelled") | the command was run without a terminal | run it in a terminal and confirm the plan |

## See also

- [Packages](index.md): a vertical as a package, the map of kinds
- [Package anatomy](anatomy.md): manifest, versions, installation
- [Work: task types and roles](work.md)
- [Rules in a package](rules.md)
- [Processes in a package](processes.md)
- [Package tests](testing.md): pyramid, sandbox, coverage, CI
- [Installation and release](install-and-release.md): lock, plan, apply, release
- [Scenarios and the core plan](../processes/package-tests.md): the process scenario format
