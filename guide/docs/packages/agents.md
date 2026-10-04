
# Package agents

A package not only describes work but also brings those who do it: task
executors, skill hosts, observers of external systems, and the identities on
whose behalf rules and processes act. All of them are objects of kind `Agent` in
the `agents/` folder. This article is for package authors: which agent to create
for which role, which permissions to give it, and how to describe placement and
the image so that the package installs on someone else's installation without
edits. Rationale: TAI-ADR-0052, TAI-ADR-0062 (item 9), and CP-ADR-0073.

The full reference for the description sections, revisions, events, and the
registry API is in the [Declarative agents](../runner/declarative-agents.md) article;
placement on machines is in [Nodes and fleet](../runner/fleet.md). This page covers
what a package author needs.

## Which agent you need

| Role in the package | `identity.kind` | `executor.kind` | `placement` | Example |
|---|---|---|---|---|
| Task executor with a coding agent or an assistant | `agent` | `claude-code` or `codex` | a node with the required labels and secrets | triaging a request, preparing a draft |
| Host of the package's skills | `agent` | `skills` | a node where the integration code is installed | skills of the `helpdesk.*` class |
| Observer of an external system | `agent` | `observer` (or a custom kind with its own `params`) | a node with access to the system | polling a request queue |
| Identity of rules and processes | `service` or `agent` | — | `none` | on whose behalf a rule creates work |
| Service account of a component | `service` | — | `none` | permissions and scope ceiling of the service |

One role, one agent. The skill host and the observer of the same integration are
two agents with different permissions, even though they can share an image.

## Scaffolds

```bash
# identity without a process: identity.kind service, placement: none
package-sdk add Agent intake-rules --package .

# process, together with the identity <key>-process and the owner role <key>-owner
package-sdk add Process intake --package .

# new package with integration code: the observer and its agent (state: stopped)
package-sdk init claims --integration --image
```

`add` writes `agents/<key>.yaml` with a schema reference for the editor, a minimal
`spec`, and hints for optional fields taken from the schema descriptions. The
scaffold does not overwrite existing files. A minimal description that passes the
schema and the core checks:

```yaml
apiVersion: taimen.ai/v1
kind: Agent
key: intake-rules
spec:
  displayName: Intake rules
  identity:
    kind: service
    permissions: [tasks.read]
  placement: none
```

`init --integration` puts the observer agent `agents/<package>-observer.yaml` in
the `stopped` state: it starts once the author fills in `config` and changes
`state` to `running` in the file, and the installation provides a node with the
required labels and secrets.

`add Agent` writes one scaffold for any role: a `service` identity with
`placement: none`. For a skills host, an observer, or an executor, replace it
with the description of your role. Full minimal descriptions by role (the
labels, secrets, and images are examples):

=== "Skills host"

    ```yaml
    # integration code in the image; the system address is the host's environment (see below)
    apiVersion: taimen.ai/v1
    kind: Agent
    key: claims-skills
    spec:
      displayName: Claims skills
      identity:
        kind: agent
        permissions: [sessions.open, tasks.read, skills.execute]
      executor:
        kind: skills
        image: registry.example.com/claims/claims-skills:0.1.0
      skills:
        protocols: [local]
        local: [claims_helpdesk.skills]
      placement:
        requires: [helpdesk-access]
        secrets: [helpdesk-token]
        resources: {cpus: 1, memoryMb: 512}
      state: running
    ```

=== "Observer"

    ```yaml
    # the system address is config from a package variable
    apiVersion: taimen.ai/v1
    kind: Agent
    key: helpdesk-observer
    spec:
      displayName: Helpdesk observer
      identity:
        kind: agent
        permissions: [observations.write]
      work:
        workspace: ${CLAIMS_WORKSPACE_ID}
      executor:
        kind: observer
        image: registry.example.com/claims/helpdesk-observer:0.1.0
        params:
          entrypoint: claims_helpdesk.observer:observe
          intervalSeconds: 60
          config: {baseUrl: "${HELPDESK_URL}"}
      placement:
        requires: [helpdesk-access]
        secrets: [helpdesk-token]
        resources: {cpus: 1, memoryMb: 256}
      state: running
    ```

=== "Task executor"

    ```yaml
    # a coding agent takes the tasks of the type assigned to it
    apiVersion: taimen.ai/v1
    kind: Agent
    key: claims-drafter
    spec:
      displayName: Claims drafter
      identity:
        kind: agent
        permissions: [sessions.open, tasks.read, tasks.write, tasks.claim, claims.manage,
                      events.read, artifacts.read, artifacts.write, projects.read,
                      workspaces.read, task_types.read, rules.read]
      work:
        workspace: ${CLAIMS_WORKSPACE_ID}
        onlyAssigned: true
        taskTypes: [claim-draft]
      executor:
        kind: claude-code
        instructions: Draft the reply; do not send anything yourself.
      placement:
        requires: [coding-agent]
        resources: {cpus: 1, memoryMb: 1024}
      state: running
    ```

=== "Identity"

    ```yaml
    # the identity of rules or a process: a principal and permissions, no process
    apiVersion: taimen.ai/v1
    kind: Agent
    key: claims-rules
    spec:
      displayName: Claims rules
      identity:
        kind: service
        permissions: [events.read, tasks.read, tasks.write, skills.invoke]
      placement: none
    ```

## Identity and permissions { #identity }

An agent's permissions are exactly what its actions do. The platform checks them
on every application: a permission the applier does not hold gives `403
permission_escalation`; `admin` and `approvals.decide` on an agent or a service
give `422 permissions_not_allowed_for_kind`.

| Role | Typical set of `identity.permissions` |
|---|---|
| Task executor | `sessions.open`, `tasks.read`, `tasks.write`, `tasks.claim`, `claims.manage`, `events.read`, `artifacts.read`, `artifacts.write`, `projects.read`, `workspaces.read`, `task_types.read`, `rules.read` |
| Skill host | `skills.execute`, plus `sessions.open` and `tasks.read`: the host daemon opens a session and looks for its work. The core checks the permissions from the contracts' `requiredPermissions` on the caller, not on the executor |
| Observer | `observations.write`; `artifacts.write` if it creates documents |
| Process identity | `tasks.read`, `tasks.write`, `approvals.manage`, `skills.invoke`, `observations.write`, `events.read`, according to the process intents; plus the permissions from the `requiredPermissions` of the skills the process invokes |
| Rules identity | according to the rule actions: `events.read` — reading the fact; `tasks.read`, `tasks.write` — finding and creating work; `skills.invoke` — interpretation by a skill; `approvals.manage` — `request_decision`; `claims.manage` — `complete_work` and `cancel_work` of work under a claim; plus the permissions from the `requiredPermissions` of the interpretation skills |

- `observations.write` grants both writing observations (`POST /api/v1/observations`)
  and knowledge snapshots (`POST /api/v1/knowledge/snapshots`).
- `identity.roles` are tenant roles. If a role is declared in the package or its
  `requires`, `check` stays silent; otherwise it warns that the role must already
  exist in the tenant. Roles and `capabilities` require `org.manage` from the
  applier.
- `identity.iam` (`audiences`, `scopeCeiling`) is only for service accounts whose
  credential the installation issues; the core stores the section but does not
  interpret it.
- `skills.invoke: [name@version]` lists the skill versions the agent invokes
  through the core. The registry assigns them to the agent's principal itself when
  it publishes a revision; no manual assignment is needed. For this the agent must
  have the `skills.invoke` permission in `identity.permissions` (otherwise `422
  skills_invoke_not_permitted`), and the applier must hold `org.manage` (otherwise
  `403 permission_escalation`). The core rejects an unknown or disabled version
  (`422 unknown_reference`, `422 skill_disabled`); `check` does not verify this
  section.

## Work and topology

The `work` section says which work the agent takes. The package does not know the
environment topology (workspace and project), so it writes it as an installation
variable:

```yaml
# package.yaml
spec:
  variables:
    CLAIMS_WORKSPACE_ID:
      kind: workspace
      description: Workspace, где живут дела по обращениям
```

```yaml
# agents/claims-drafter.yaml
spec:
  work:
    workspace: ${CLAIMS_WORKSPACE_ID}
    onlyAssigned: true
    taskTypes: [claim-draft]
```

- A variable that is used must be declared in `spec.variables`, and a declared
  variable must be used (`variable_undeclared`, `variable_unused` in `check`). The
  `workspace` kind means a UUID that `plan` verifies against the deployment.
- `work.taskTypes` must be declared in the package or its `requires`; otherwise
  `check` reports an error.
- `onlyAssigned` defaults to `true`: the agent takes only work assigned to it.
  It is assigned with the `agent:<key>` reference: in the `assignee` of outcomes
  and rules and in the `assigneeId` of tasks. `check` verifies literal references:
  the agent must be described in the package or its `requires` and must not be
  retired by the same installation.

## Execution

`executor.kind` is the executor kind, `executor.params` are its parameters, which
the package schema validates per kind, and `executor.instructions` are the
instructions for the executor (up to 64 KiB), a layer after the platform, project,
and task type instructions.

| Kind | What it does | Required `params` |
|---|---|---|
| `claude-code`, `codex` | executes tasks with a coding agent | — |
| `skills` | executes only the skills from the `skills` section | — (without the `skills` section the daemon does not start) |
| `observer` | an integration observer on `package_sdk.connector` | `entrypoint` |
| `git-connector` | a custom git observer kind with its own `params` | `repositories` |

Secrets are not written into the description: the core rejects `params` keys that
look like a secret (`token`, `password`, …) with `422 secret_material_rejected`,
and the schema does not allow them in an observer's `config`. The observer and the
skill host receive a secret by name in `placement.secrets`: the node puts the file
`/run/secrets/<name>`, and `ctx.secret("<name>")` in the observer and skill-sdk
environments reads it by the same rule (see
[Integrations](integrations.md#secrets)).

A skill host lists what it executes and where it connects:

```yaml
spec:
  identity:
    kind: agent
    permissions: [sessions.open, tasks.read, skills.execute]
  executor: {kind: skills}
  skills:
    protocols: [local]
    local: [claims_integration.skills]     # module or module:function
    audiences: [control-plane]
    concurrency: 4
```

What is not in the `skills` section is not available to the executor either, even
if it is set on the host through environment variables. See
[Package skills](skills.md) for details.

!!! warning "A package cannot set a non-secret skills host parameter yet"
    The `skills` kind has no `params`: unlike an observer's `config`, the agent
    description cannot pass the host, for example, the address of an external
    system from a package variable, and `describe` does not print such a
    parameter. `ctx.config(…)` reads the environment of the host process, and
    that is set by the installation on the node, through the common
    environment variables of executors of the `skills` kind. Until there is a
    mechanism, name the parameter in the package README ("the skills host
    needs `HELPDESK_URL`") and pass it to the installer; keep an address that
    the observer also needs as a package variable in the observer's `config`.

## Placement

`placement` is the package's contract with the installation: where the agent can
run. The package names **labels** and **secret names**; the installation decides
which machines provide them.

```yaml
spec:
  placement:
    requires: [claims-source-access]   # node label: name or name=value
    secrets: [claims-source-token]     # secret file on the node; the value is not here
    resources: {cpus: 1, memoryMb: 256}
    replicas: 1
    drainSeconds: 600
  state: running
```

- `resources.cpus` is an integer: the core rejects a fractional value with `422
  non_canonical_value`.
- `placement: none` means an identity only, without a process.
- `state` and `replicas` are the desired state, not a revision: `apply` brings the
  agent to them every time. To stop an agent for a long time, edit the file rather
  than stopping it manually; otherwise the next `apply` starts it again.
- Name labels and secrets by the meaning of the access, not by the machine:
  `claims-source-access`, not a server name. `describe` prints their list:

```bash
package-sdk describe .
```

```text
агенты и узлы:
  claims-observer (observer, образ registry.example.com/claims/observer:1.2.0): метки claims-source-access; секреты claims-source-token
  claims-rules (—): без процесса (только личность)
```

The output lists agents and nodes: for each agent, its image, node labels, and
secrets; `без процесса (только личность)` means "no process (identity only)".

## Executor image { #image }

By default an agent runs on the image the node maps to the executor kind. A
package with integration code needs its own image with this code inside. The
`executor.image` field names it:

```yaml
spec:
  executor:
    kind: observer
    image: registry.example.com/claims/observer:1.2.0
    params:
      entrypoint: claims_integration.observer:observe
```

| Rule | Meaning |
|---|---|
| Form | `[registry[:port]/]path:tag`, `…@sha256:<64 hex>`, or `…:tag@sha256:<64 hex>`, up to 255 characters. A tag or a digest is required: there is no implicit `latest` |
| Core check | form only: an invalid reference gives `400 invalid_request` with `loc` `body.spec.executor.image` |
| Revision | the image is part of the description and its hash: changing the image is a new revision; without the field the description is the same as before the field appeared |
| Who reads it | `GET /api/v1/agents/me` and the agent list return the revision's `spec.executor.image`; the image is not included in the `agent.revision_published` event |

Naming an image does not grant the right to run it.

A node runs the named image only if the `executors.<kind>.images` list in that node's
`node.yaml` allows it: an exact reference or a pattern with a single `*` in the tag.
Otherwise the agent waits with the placement reason `image_not_allowed`, and a node
that is sent the image anyway does not run it. How the node checks the list is
described in [Nodes and fleet](../runner/fleet.md#images).

The image is built from the `package-sdk image observer` or `package-sdk image
skills` scaffold (see [Integrations](integrations.md#images)). The package pins
the image version with a tag: a running container does not pick up an image
rebuilt under the same tag.

## Agents of rules and processes

A rule or a process acts not on behalf of whoever applied the package, but on
behalf of an identity:

```yaml
# rules/claim-reopened.yaml
spec:
  identity: {agent: claims-rules}
```

```yaml
# processes/claim.yaml
spec:
  identity: {agent: claim-process}
  owner: [{role: claim-owner}]
```

- The identity is an `Agent` with `placement: none`: there is no process, only a
  principal and permissions.
- `check` requires the agent from `identity.agent` to be described in the package
  or its `requires`.
- Application order: `Agent` comes after roles, skills, and task types and before
  rules and processes, so the identity already exists when a rule refers to it.

## Validation and application

```bash
package-sdk check --package .          # schema, references, the core AgentSpec model
package-sdk plan --install packages.yaml --server https://platform.example.com --out plan.json
package-sdk apply --plan plan.json --server https://platform.example.com
```

- `check` validates the description against the format schema
  (`$defs.agentSpec`), the core's `AgentSpec` model (requires
  `package-sdk[sandbox]`), and the package references.
- `plan` builds a single installation plan without a single write. For an agent it
  asks the core (`POST /api/v1/agents:validate`) whether there will be a new
  revision and whether the desired state changes. For a package with processes or
  calendars, the core itself plans the agents together with them (`POST
  /api/v1/packages:plan`). The plan checks variables of the `workspace`,
  `project`, `principal`, and `role` kinds against the deployment: such a UUID
  must exist.
- `apply --plan` applies exactly the saved plan after a human confirms it; if the
  deployment has diverged from the plan, the installation stops with `plan_stale`
  before the first write. The agent is published with `POST /api/v1/agents`.

The installation token needs `agents.manage` and all the permissions the package
grants to agents.

Retirement is a key in `retire.Agent` of the installation file: the executor
stops, the credential is revoked, and the run history remains. The key of a
retired agent is not reused (`409 agent_retired`).

## Common problems

| Symptom | Cause and fix |
|---|---|
| `403 permission_escalation`, `details.missing` | the installation token lacks a permission that the package grants to an agent, or `org.manage` for roles, capabilities, and `skills.invoke` |
| `422 skills_invoke_not_permitted` | the agent has a `skills.invoke` section but no `skills.invoke` permission in `identity.permissions` |
| `422 permissions_not_allowed_for_kind` | `admin` or `approvals.decide` on an agent: remove them, decisions are made by a human |
| `422 secret_material_rejected` | a key in `params`, `workingCopy`, or `resources` looks like a secret: pass the secret by name in `placement.secrets` |
| `400 invalid_request` on `spec.executor.image` | no tag and no digest, or extra characters in the reference |
| `check`: `work.taskTypes '…' — такого TaskType нет` ("no such TaskType") | the task type is not declared in the package or its `requires` |
| `check`: `variable_undeclared` | `${NAME}` in the description without a declaration in `spec.variables` |
| the agent is running again after `apply` | the file has `state: running`: stop it by editing the file |
| the agent waits for placement with `image_not_allowed` | no node allows the image from `executor.image`: the node administrator adds it to the list, or the package removes the field |

## See also

- [Package skills](skills.md)
- [Integrations](integrations.md)
- [Catalog packages](../control-plane/catalog-packages.md#agent)
- [Declarative agents](../runner/declarative-agents.md)
- [Nodes and fleet](../runner/fleet.md)
- [Work rules](../control-plane/work-rules.md#identity): the rules identity
- [Processes](../processes/index.md): the process owner and identity
