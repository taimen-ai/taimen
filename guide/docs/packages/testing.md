
# Package tests

How to check a whole package with one command: the `package-sdk test`
pyramid from the static check to process, rule, and task type scenarios, the
PostgreSQL sandbox, a run on the deployment's core, coverage, and the check
in CI. This page is for package authors; the process scenario format is
covered in detail in [Scenarios and the core plan](../processes/package-tests.md),
and rule and task type scenarios in [Rules](rules.md#tests) and
[Work](work.md#tests). Rationale: TAI-ADR-0062 (items 2 and 11), CP-ADR-0074.

## The pyramid in one command

```bash
package-sdk test .
```

`test` goes through four stages in order and prints a combined report:

```mermaid
flowchart LR
    C["1. check<br/>schema, references,<br/>core validators"] --> S["2. skills<br/>skill contracts<br/>against the code"]
    S --> I["3. integration<br/>pytest of the<br/>integration code"]
    I --> SC["4. scenarios<br/>tests/*.test.yaml<br/>with core code"]
```

| Stage | What it checks | What executes it | When it is skipped |
|---|---|---|---|
| `check` | the format schema, closed references, variables, the manifest, core validators, as `package-sdk check` does | core code (the `sandbox` extra) | never; if it fails, the stages above do not run |
| `skills` | the package's `kind: Skill` YAML matches the integration code (`skill-sdk export --check`) | `skill-sdk` (the `skills` extra) | there is no `integration/` directory or it has no modules |
| `integration` | unit tests of the integration code in `integration/tests/` | `pytest` | there is no `integration/tests/` or pytest found no tests |
| `scenarios` | the process language (expressions, data, step reachability), then the package scenarios `tests/*.test.yaml`: processes, rules, task types | core code: the in-process sandbox or the deployment's core (`--server`) | the package has no scenarios |

- **A skip is not a failure.** A stage with nothing to check is marked `SKIP`
  and does not fail the run.
- **Nothing to execute with is a failure.** If a stage has no tool (core
  code, `skill-sdk`, `pytest`), the stage is `ERR`, and the run is not green.
  A stage is never skipped silently.
- **The check is a gate.** If `check` finds an error, the other stages are
  marked `статическая проверка не пройдена — тесты не запускались` ("static
  check failed, tests were not run").

Exit code `0` means all stages are green or skipped because there was nothing
to check.

| Flag | What it does |
|---|---|
| `<directory> …`, `--package <directory or key>` | which packages to test; without them, all packages from `packages/` in the current directory |
| `--install <file>` | all packages of the installation, sources from git according to `packages.lock` |
| `--test <name or file>` | only one scenario (by `name`, the file name, or its base without `.test.yaml`) |
| `--server <url>` | the deployment's core executes the scenarios instead of the sandbox |
| `--workspace <id>` | with `--server`: whose roles, calendars, and instances the run reads |
| `--database-url <url>` | the sandbox database for rules and task types (or `PACKAGE_SDK_SANDBOX_DATABASE_URL`) |
| `--env <file>` | values of the package's `${VARIABLES}`, `.env` by default; the process environment takes precedence over the file |
| `--json` | the report as a document |

## What to install { #install }

All stages run in the environment of `package-sdk` itself: the integration
code and its tests are run by the same interpreter. That is why everything
they need is installed into the tool's environment:

```bash
uv tool install "./sdk/package-sdk[all]" --with pytest
```

| Extra | For which stage |
|---|---|
| `sandbox` | `check` with core validators and scenarios in the sandbox |
| `skills` | skill contract verification (`skill-sdk`) |
| `connector` | observer tests (`package_sdk.connector.testing`) |
| `all` | everything listed plus the author MCP server |

- `pytest` is not part of the extras: add it with `--with pytest`.
- Third-party dependencies of the integration code (what is listed in
  `integration/pyproject.toml`) are also added with `--with`: the stage does
  not install them itself.
- Core code and the SDK are connected as directories in the installation's
  layout (`services/`, `sdk/`), as described in
  [A package in 10 minutes](quickstart.md#install). The neighbours each extra
  needs:

| Extra | Directories next to `sdk/package-sdk` |
|---|---|
| `sandbox` | `services/control-plane`, `sdk/platform-auth-sdk` |
| `connector` | `services/control-plane` (the core client from its `client/`) |
| `skills` | `sdk/skill-sdk` |
| `mcp` | `services/control-plane` |
| `all` | `services/control-plane`, `sdk/platform-auth-sdk`, `sdk/skill-sdk` |

The `skill-sdk` and `pytest` commands installed this way live in the tool's
environment, not on `PATH`: only `package-sdk` is exposed. How to call them
by hand is in [Integration code](#integration-code).

!!! note "Integration code environment"
    Subprocesses of the `skills` and `integration` stages do not receive
    variables that look like a secret: `*TOKEN*`, `*SECRET*`, `*PASSWORD*`,
    `*API_KEY*`, database addresses (`DATABASE_URL`, `*_DSN`), everything with
    the prefixes `CP_`, `CONTROL_PLANE_`, `IAM_`, `PACKAGE_SDK_`, and
    addresses with a password inside. These tests need neither the deployment
    nor a database. This is not a sandbox: `HOME` is kept, and credential
    files in it are accessible to the integration code.

## The PostgreSQL sandbox { #sandbox }

Scenarios are executed by **core code** of the version installed next to the
tool: `package-sdk` has no engine of its own for processes, expressions, or
rules.

| Subject | How it runs in the sandbox | Needs a database |
|---|---|---|
| process | the core process engine in memory: virtual time, tasks, approvals, and timers in memory, and skills, agents, and memory as mocks | no |
| rule, task type | core application code: publishing the package objects, recording an observation, a gate decision, completion, and acceptance, in a transaction that is always rolled back | yes |

Rules and task types need an **empty** PostgreSQL 16 database with the
`pg_trgm` extension available (the official `postgres` images have it). The
sandbox applies the core schema and creates its own tenant on the first run.
It works only with an empty database or one it has prepared itself; it
rejects a deployment database or someone else's before any write.

```bash
docker run -d --rm --name package-sandbox-db \
  -e POSTGRES_PASSWORD=sandbox -p 127.0.0.1:55432:5432 postgres:16-alpine
export PACKAGE_SDK_SANDBOX_DATABASE_URL=postgresql://postgres:sandbox@127.0.0.1:55432/postgres
package-sdk test .
```

Without a database, rule and task type scenarios are marked `SKIP` with the
finding `sandbox_database_required`, the scenarios stage is `FAIL`, and the
exit code is `1`.

Each rule or task type test is its own transaction: tests do not see each
other. One test has a time limit (30 seconds), and one request has at most
100 such tests.

### The sandbox and the deployment's core

With `--server`, the same files go to the deployment's core
(`POST /api/v1/packages:test`, the `packages.test` permission), and its code
executes the scenarios. Nothing is written.

```bash
export CP_TOKEN=<access token audience control-plane>
package-sdk test . --server https://platform.example.com --workspace <workspace-id>
```

| | Sandbox | Deployment's core |
|---|---|---|
| Catalog | the package objects and its `requires`, from files | the tenant's catalog on top of the package objects |
| Core code version | the one installed next to the tool | the deployment's version |
| `governedBy` | not reconciled with the knowledge base | reconciled |
| Live instances | none: the `given.fromInstance` dry run is unavailable | available, with the `processes.read` permission on the workspace |
| Needs | the `sandbox` extra, a database for rules and task types | a token and the `packages.test` permission |

The sandbox and the core judge a package the same way on the same files: the
same result, the same findings, the same scenario results, and the same
coverage. A discrepancy between them is a bug in the tool or the core, not in
the package.

## Scenarios: process, rule, task type { #subjects }

A scenario is a `tests/<name>.test.yaml` file following the
`schema/v1/test.schema.json` schema. What it checks is set by the `subject`
field:

| `subject` | Object key | `given` | Steps |
|---|---|---|---|
| `process` (default) | `process` | `clock`, `data`, `stage`, `principals`, `calendar`, `settings`, `fromInstance` | `emit`, `advance`, `complete`, `approve`, `settings`, `expect` |
| `rule` | `rule` | exactly one of `observation`, `event`; `clock`, `variables`, `settings` | only `expect`: `result`, `ensureWork`, `invokeSkill`, `noSideEffects` |
| `taskType` | `taskType` | `task`, `artifacts`, `principals`, `clock`, `variables` | `approve`, `verify`, `complete`, `expect` |

`check` verifies that the subject is an object of the same package, and for a
process, that `complete.step` and `approve.step` name its steps. Skill
responses are set by `mocks.skills` (`name@version` → responses in invocation
order); the mock output is checked against the skill's output schema from the
catalog.

=== "Process"

    ```yaml
    process: claim
    name: a small refund is reviewed, replied and closed without an approval
    given:
      principals: {claims-officer: [alice], claims-manager: [bob]}
    mocks:
      skills:
        claims.classify@1:
          - output: {category: defect, severity: medium, confidence: 0.9}
    steps:
      - emit:
          observation: helpdesk.ticket_created
          payload:
            data: {ticketId: T-1001, customerId: C-7, customerName: Northwind Ltd, product: Grinder X2,
                   subject: The grinder stopped working, text: It stopped after a week., amount: 120, currency: EUR}
      - complete:
          step: review-claim
          by: alice
          output: {resolution: refund, refundAmount: 120, reply: We refund the grinder in full.}
      - expect: {stages: {review: completed, reply: open}}
    ```

    The full format, agent and memory mocks, replay, and the dry run are in
    [Scenarios and the core plan](../processes/package-tests.md).

=== "Rule"

    ```yaml
    subject: rule
    rule: claim-reopened
    name: a reopened ticket is filed as a follow-up
    given:
      observation:
        kind: helpdesk.ticket_reopened
        data: {ticketId: T-1001, version: 3, channel: web, subject: The grinder stopped working,
               text: The replacement broke too.}
    mocks:
      skills:
        claims.classify@1:
          - output: {category: defect, severity: medium, confidence: 0.9}
    steps:
      - expect:
          result: matched
          ensureWork:
            - type: claim-followup
              customFields: {ticketId: T-1001}
    ```

    See [Rules in a package](rules.md#tests) for details.

=== "Task type"

    ```yaml
    subject: taskType
    taskType: claim-reply
    name: an approved reply is sent and completes the task
    given:
      task:
        assignee: alice
        customFields: {ticketId: T-1001, message: We refund it.}
      principals: {claims-officer: [alice, bob]}
    mocks:
      skills:
        helpdesk.reply@1:
          - output: {replyId: R-1, status: closed}
    steps:
      - approve: {decision: approved, by: bob}
      - expect:
          invokeSkill: [{skill: helpdesk.reply@1, inputs: {ticketId: T-1001}}]
          status: {category: terminal_success}
    ```

    See [Work](work.md#tests) for details.

Specifics of rule and task type scenarios:

- time does not move in them: they do not check deadlines and timers; that
  is the job of processes;
- a skill invocation without a mock stays unanswered; if the rule waits
  because of this, the test fails with `unmocked_skill_call`;
- an input that the background rule evaluation would not evaluate (a
  different workspace, a consequence of another rule) is not evaluated in
  the test either; the `input_not_delivered` warning says why;
- a setup that the core rejected (for example, `given.task` does not pass
  the type) is shown by the test as a `given_refused` error;
- values of `${VARIABLES}` are taken from `given.variables`, then from
  `--env` and the environment, then from the manifest's `default`;
- a scenario need not set variables of kinds `workspace`, `principal`, and
  `role`: the sandbox substitutes its own test workspace, people, and roles,
  and drops a process's `workspaceId` of the form `${…}`. That is why a run
  with `--env /dev/null` is green without the deployment's UUIDs;
- an unset variable of another kind is an `unresolved_install_variable`
  error, and only for a scenario that needs an object using it.

The decision on an approval is spelled differently in scenarios: the vote of a
process's `approve` step is `decision: approve` or `reject`, and the decision
of a task type's gate is `decision: approved` or `rejected`.

## Settings in scenarios { #settings }

A package with [settings](settings.md) checks in scenarios both the default
values and a change of a value by an administrator. The sandbox keeps
settings versions the same way the core does: every value goes through the
`PUT` check — the package settings schema from the files sent, `x-ref`, and
the secret markers.

| Where | What it sets | Values version |
|---|---|---|
| no `given.settings` | the schema `default` values are in effect | `0` |
| `given.settings` (process, rule) | the values saved by the start of the scenario | `1` |
| the `settings` step (process only) | an administrator saved new values in the middle of the scenario | the next one; the same values do not make a version |

The values in `given.settings` and in the `settings` step are the whole
saved set, like the `PUT` body: a field that is not there takes its
`default`, so a required field without a `default` (`escalationRole` of the
`claims` package) is given in every set. Computations after the `settings`
step read the new values, while decisions a case has already made keep the
values they read. The case state in `expect` (`data`, `stages`, `status`,
`outcome`) is read from the first case of the scenario, and another case
cannot be picked, so the old case and a new case are checked by separate
scenarios:

```yaml
process: claim
name: a raised refund limit does not change the route already chosen
given:
  principals: {claims-officer: [alice], claims-manager: [bob]}
  settings: {refundLimit: 500, escalationRole: 0c000000-0000-4000-8000-000000000001}
steps:
  - emit: {observation: helpdesk.ticket_created, payload: {data: {ticketId: T-1, amount: 800}}}
  - expect: {data: {route: manager}}
  - settings: {refundLimit: 1000, escalationRole: 0c000000-0000-4000-8000-000000000001}  # an administrator raised the limit
  - expect: {data: {route: manager}}   # the route of the case is already chosen
```

```yaml
process: claim
name: a claim opened after the raise follows the new limit
given:
  principals: {claims-officer: [alice], claims-manager: [bob]}
  settings: {refundLimit: 500, escalationRole: 0c000000-0000-4000-8000-000000000001}
steps:
  - settings: {refundLimit: 1000, escalationRole: 0c000000-0000-4000-8000-000000000001}  # an administrator raised the limit before the first case
  - emit: {observation: helpdesk.ticket_created, payload: {data: {ticketId: T-2, amount: 800}}}
  - expect: {data: {route: officer}}   # the case follows the new limit
```

- A due date computed from a setting (`due: {workdays: {expr: settings.…}}`)
  is computed on entering the step: the `settings` step does not move a due
  date that is already open.
- In a rule scenario, `given.settings` holds the values saved for the
  evaluation; without it and without references to `settings` in the rule,
  the sandbox does not touch settings.
- A value that does not match the schema, an `x-ref` reference to an object
  that does not exist, or secret material stops the test with the code
  `settings_invalid`, `unknown_ref`, or `secret_material_rejected` — with no
  value in the message.
- If the package declares no settings but the scenario sets them, the test
  stops with `settings_not_declared`.
- An `x-ref` to a task type or a calendar must name an object of the package
  or of its `requires`. The sandbox does not check the ids of roles,
  principals, and workspaces; with `--server`, the deployment's core checks
  them against the organization.
- Core code next to `package-sdk` that does not know settings yet gives the
  error `sandbox_settings_unsupported`: update `control-plane`.

## Coverage { #coverage }

The report computes coverage across all scenarios of the package together,
using core functions, and lists what no scenario has passed:

| Subject | Counters |
|---|---|
| process | `elements` (stages, steps, milestones, timers), `transitions`, `decisionRows`, `handlers` |
| rule | `branches`: the branches of `condition` and `where`; `outcomes`: the evaluation results, including the interpretation response and failure |
| task type | `outcomes`: gate outcomes and their `onSuccess`/`onFailure` reactions; `preconditions`; `completion`: completion actions; `acceptance`: acceptance criterion outcomes |

The report of the end-to-end "customer claims" example (see
[Example](tutorial.md)), abridged:

```text
ok   проверка: схема, ссылки, валидаторы ядра
ok   контракты скиллов (skill-sdk export --check)
   ok   claims: ok
ok   тесты кода интеграции (pytest)
   ok   claims: 10 passed in 0.29s
ok   сценарии пакета — песочница ядра
== claims
ok   tests/claim-large-refund.test.yaml: a large refund is approved by a manager who did not review the claim [claim] (22 мс)
ok   tests/claim-reopened.test.yaml: a reopened ticket is classified and filed as a follow-up for the officers [rule claim-reopened] (155 мс)
ok   tests/claim-reply-approved.test.yaml: an approved reply is sent to the helpdesk and completes the task [taskType claim-reply] (197 мс)
…
покрытие claim v1: elements 13/13, transitions 12/12, decisionRows 3/3, handlers 1/1
покрытие правила claim-reopened (тестов 4): branches 6/6, outcomes 4/4
покрытие типа задачи claim-reply v1 (тестов 3): outcomes 4/4
ok (passed): тестов 12, зелёных 12
покрытие — процессы: elements 13/13, transitions 12/12, decisionRows 3/3, handlers 1/1; правила: branches 6/6, outcomes 4/4; типы: outcomes 4/4
ok: пирамида пакетов claims (11612 мс)
```

The tool prints the report in Russian. The stage lines are, in order: check
(schema, references, core validators), skill contracts, integration code
tests, and package scenarios in the core sandbox. `покрытие` means
"coverage", `правила` "rule", `типа задачи` "task type", `тестов N, зелёных N`
"N tests, N green", and `пирамида пакетов` "package pyramid".

- Lines `не пройдены (<counter>): …` ("not passed") name the elements,
  branches, and outcomes not passed: this is a ready list of the missing
  scenarios.
- `без сценариев: <package>: <kind>/<key>` ("without scenarios") is a
  process, rule, or task type with something to cover for which the package
  has no scenario file at all. This does not fail the run, but it shows up in
  the report.
- `coverage.minimum` in a process scenario is a threshold, in percent, for
  the share of process elements that this scenario passes through; below the
  threshold, the scenario fails.
- With `--test`, coverage is counted over the one scenario that ran: the
  `не пройдены` and `без сценариев` lines name everything the other scenarios,
  which did not run, would have reached, and say nothing about completeness.
  Look at coverage in a run without `--test`.

A task type with only statuses and fields (without gates, acceptance, and
work after completion) has nothing to cover and does not appear in the
report: such tasks are checked by the scenarios of the process that creates
them. In the example, `claim-review` and `claim-followup` are built this way.

## Integration code { #integration-code }

The `skills` and `integration` stages check the code next to the package:

| What | Tool | Article |
|---|---|---|
| the skill contract against the package YAML | `skill-sdk export --check`, the `skills` stage | [Package skills](skills.md) |
| skill logic | `skill_sdk.testing`: `invoke`, `check_contract`, `FakeLlm`, `FakeCore` | [Package skills](skills.md#tests) |
| the observer loop | `package_sdk.connector.testing`: `run_once`, `FakeCore` | [Integrations](integrations.md#tests) |

Package scenarios do not execute skills: a skill invocation in a scenario is
answered by a mock from `mocks.skills`. That is why the whole pyramid is
needed: unit tests check the skill code, and scenarios check how the package
uses it.

`test` runs the integration code stages by itself: with the interpreter of the
tool's environment and with `integration/src` on `PYTHONPATH`. `test` has no
"this stage only" flag. The same commands by hand, from the `integration/`
directory:

```bash
TOOL="$(uv tool dir)/package-sdk/bin"                 # the tool's environment
PYTHONPATH=src "$TOOL/skill-sdk" export --package .. <module>.skills          # write skills/*.yaml
PYTHONPATH=src "$TOOL/skill-sdk" export --package .. --check <module>.skills  # compare
PYTHONPATH=src "$TOOL/python" -m pytest -q tests
```

Without `PYTHONPATH=src`, the integration module is not importable
(`ModuleNotFoundError: No module named '<module>'`), and a system `pytest`
does not see `skill_sdk` and `package_sdk.connector`: they exist only in the
tool's environment.

## Check in CI { #ci }

`package-sdk init` puts a working `.github/workflows/package.yml` scaffold in
place: the job checks out the package and the platform components, installs
`package-sdk` from a pinned clone, and runs `package-sdk test .` and
`package-sdk docs . --check`. Committing the scaffold is enough: the job is
green after the first push.

How it is built:

- **Directories.** The package is checked out into a directory named by its
  key (`path: <key>`): `check`, `test`, and `docs` match the directory name
  against the key. The platform components are sibling clones in `.platform/`;
  a package key never starts with a dot, so the package directory cannot
  coincide with any component.
- **Revisions.** The `PLATFORM_GIT` variable sets where the clones come from: a
  component is cloned from `$PLATFORM_GIT/<name>.git`. One `*_REF` variable sets
  the revision of each component, a `v…` tag or a full commit SHA:
  `PACKAGE_SDK_REF`, `CONTROL_PLANE_REF`, `PLATFORM_AUTH_SDK_REF`, and, for a
  package with integration code (`init --integration`), also `SKILL_SDK_REF`.
  Every step of the job reads only these variables. `init` fills them from the
  installation it runs in: the address is the owner of the `package-sdk`
  repository, the revisions are those of the components next to the tool. An
  empty variable stops the job at the first step with a `not set: …` error.
- **Extras.** `package-sdk` is installed with `sandbox` (the `control-plane` and
  `platform-auth-sdk` siblings); for a package with integration code, also with
  `skills` and `connector` and with `--with pytest`. Add third-party
  dependencies of the integration code to the `uv tool install` line, one
  `--with` each.
- **The PostgreSQL database** for rule and task type scenarios is the
  `postgres` service and the `PACKAGE_SDK_SANDBOX_DATABASE_URL` variable. `init`
  enables them by itself if the directory already contains rules, task types,
  or their scenarios, and with the `init --database` flag; otherwise the block
  stays commented out in the file. `package-sdk add` of a rule or a task type
  enables the database in the workflow by itself. If the database block was
  edited by hand, `add` leaves it alone and prints a warning: enable the
  database by hand then, or the job is red on `sandbox_database_required`.
- **README.** If `README.md` already exists (for example, a clone with the
  hosting's README), `init` keeps its text and appends the generated section at
  the end: the `docs --check` step compares it, and without the section the job
  would be red from the first push.

A fragment of the scaffold for an `acme-claims` package with integration code
and rule scenarios (comments and the variable check step are shortened):

```yaml
jobs:
  check:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16            # pin it by digest: postgres:16@sha256:…
        env: {POSTGRES_PASSWORD: sandbox, POSTGRES_DB: sandbox}
        ports: ["5432:5432"]
    env:
      PLATFORM_GIT: "https://github.com/<owner>"
      PACKAGE_SDK_REF: "<tag or full SHA>"
      CONTROL_PLANE_REF: "<tag or full SHA>"
      PLATFORM_AUTH_SDK_REF: "<tag or full SHA>"
      SKILL_SDK_REF: "<tag or full SHA>"
      PACKAGE_SDK_SANDBOX_DATABASE_URL: postgresql://postgres:sandbox@localhost:5432/sandbox
    steps:
      - name: Pinned revisions        # an empty variable is an error
        run: …
      - uses: actions/checkout@<SHA>  # v4
        with:
          path: acme-claims
          persist-credentials: false
      - uses: astral-sh/setup-uv@<SHA>  # v6
      - name: package-sdk and the components of the platform as sibling directories
        run: |
          mkdir -p .platform && cd .platform
          clone() { … }               # git clone $PLATFORM_GIT/<name>.git, checkout <revision>
          clone package-sdk "$PACKAGE_SDK_REF"
          clone control-plane "$CONTROL_PLANE_REF"
          clone platform-auth-sdk "$PLATFORM_AUTH_SDK_REF"
          clone skill-sdk "$SKILL_SDK_REF"
          uv tool install "./sdk/package-sdk[sandbox,skills,connector]" --with pytest
          echo "$(uv tool dir --bin)" >> "$GITHUB_PATH"
      - name: package-sdk test
        run: package-sdk test .
        working-directory: acme-claims
      - name: The generated README section is up to date
        run: package-sdk docs . --check
        working-directory: acme-claims
```

Rules for any package workflow:

- The tool and the platform components are installed from pinned sources:
  clones at tags or full SHAs of a single platform release (for the compatible
  revisions, see [A package in 10 minutes](quickstart.md#install)). They are not
  installed from the public package index: there are no such names there, and
  this closes the path for dependency substitution.
- When moving to a new platform release, change the `*_REF` values in one
  place, the job's `env`.
- The actions in the scaffold are pinned by SHA; pin the database image by
  digest.

## Through MCP

The same pyramid is available to an author agent through the tool
`pkg_test(path | install, tests?, server?, workspace_id?, env_file?)` of the
`package-sdk mcp` MCP server: the response is the `--json` report. See
[Package author in Claude Code](author-plugin.md).

## Common problems

| Symptom | Cause | What to do |
|---|---|---|
| `ERR` on the contracts stage: `сверке контрактов скиллов нужен skill-sdk` ("skill contract verification needs skill-sdk") | there is no `skill-sdk` in the tool's environment | reinstall with `[skills]` or `[all]` |
| `ERR` on the integration stage: `тестам кода интеграции нужен pytest` ("integration code tests need pytest") | there is no `pytest` in the tool's environment | `uv tool install --reinstall "./sdk/package-sdk[all]" --with pytest` |
| `ModuleNotFoundError` in integration tests | a dependency of the integration code is not in the tool's environment | add it with `--with` |
| `ModuleNotFoundError: No module named '<module>'` on a manual `skill-sdk export` or `pytest` | the integration code in `integration/src` is not on `sys.path` | run from `integration/` with `PYTHONPATH=src` (see [Integration code](#integration-code)) |
| `skill-sdk: command not found` | the command lives in the environment of the `package-sdk` tool | `"$(uv tool dir)/package-sdk/bin/skill-sdk"` |
| `sandbox_database_required`, the scenarios stage is `FAIL` | there is no database for rules and task types | set `PACKAGE_SDK_SANDBOX_DATABASE_URL` or `--database-url` |
| the sandbox rejected the database | the database is not empty and was not prepared by the sandbox | use an empty database |
| `unmocked_skill_call` | the rule invokes a skill whose response is not in `mocks.skills` | add a mock |
| `unresolved_install_variable` | there is no value for a `${VARIABLE}` | `given.variables`, `.env`, or `default` in the manifest |
| a rule scenario created nothing, `input_not_delivered` | the input would not reach the rule on the deployment either | check `trigger`, the workspace, and the observation kind |
| `нет тестов: … нет сценария '…'` ("no tests: … no scenario '…'") | `--test` did not find the scenario | give the `name`, the file, or its base |
| CI: `not set: …` or `PLATFORM_GIT is not set` | a revision or address variable in the job's `env` is empty | set a tag or a full SHA of the component from a single release (see [Check in CI](#ci)) |
| CI: `cannot clone …: no such repository or no access` | `PLATFORM_GIT` has no such repository, or there is no access to it | fix `PLATFORM_GIT`; for a private repository, give the job access |

## See also

- [A package in 10 minutes](quickstart.md#test): the first run
- [Scenarios and the core plan](../processes/package-tests.md): the process scenario format, replay, dry run
- [Rules in a package](rules.md#tests)
- [Work: task types and roles](work.md#tests)
- [Package skills](skills.md#tests)
- [Package settings](settings.md): the declaration, `settings` references, permissions
- [Integrations](integrations.md#tests)
- [Installation and release](install-and-release.md)
- [Package readiness checklist](checklist.md)
