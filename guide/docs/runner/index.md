
# Agents and runner

This section describes autonomous executors: the `control-plane-agent` daemon, which
claims tasks from Control Plane on its own and executes them with a coding agent (Claude
Code, Codex) or with skills in an isolated working copy. Each executor is described by the
catalog kind `Agent`, and the platform runs it on fleet node machines. The section is for
engineers who connect machines and describe agents, and for operators who assign tasks to
agents and accept the results.

## Agent by description and nodes

An agent is one YAML object in a catalog package: identity and permissions, which work to
take, the executor kind with its model and instructions, the working copy, review, skills,
placement. Control Plane stores immutable revisions of the description and derives the
agent's principal and binding from them; fleet-controller picks a node by labels, secrets,
executor kinds, and capacity and delivers the PAT to the agent; the node starts a container
with the daemon, and the daemon takes its configuration from its revision
(`GET /agents/me`).

```mermaid
flowchart LR
    Y["agents/*.yaml"] -->|package-sdk apply| CP["Control Plane<br/>revisions"]
    CP --> FC["fleet-controller<br/>placement, PAT"]
    FC --> N["fleet-node<br/>on a machine"]
    N --> D["container<br/>control-plane-agent"]
    D -->|GET /agents/me, work| CP
```

Editing the description creates a new revision: the executor finishes the current run,
exits with code 75, and comes back up on the new revision. Details are in
[Agents by description](declarative-agents.md) and [Nodes and fleet](fleet.md).

## What a runner is

A runner is a **client** of Control Plane, not part of the core. It goes through the same
harness protocol cycle as a human in Claude Code: session → finding work → claim → run →
artifacts → completion. There is no special server path for agents: the same endpoints, the
same `control_plane_client` SDK, the same checks of permissions, leases, and fencing tokens.

There is one difference: a human operator makes decisions personally (claim, completion,
approval), while the runner daemon acts according to its configuration — it claims
automatically and decides the run outcome from the adapter result.

```mermaid
flowchart LR
    subgraph Host["Runner host or container"]
        D["control-plane-agent<br/>(daemon)"]
        A["Adapter<br/>claude-code / codex"]
        CLI["Agent CLI<br/>claude -p / codex exec"]
        W["Working copy<br/>worktrees/&lt;id&gt;/&lt;repo&gt;"]
        M["Bare mirrors<br/>of repositories"]
        D --> A --> CLI
        CLI --> W
        M --> W
    end
    D -- "HTTPS, access token<br/>audience control-plane" --> CP["Control Plane API"]
    D -- "PAT → exchange" --> IAM["IAM"]
    D -- "git push task/&lt;publicId&gt;" --> F["Forge (Git)"]
    CLI -. "MCP control-plane<br/>(Claude Code only)" .-> CP
```

## Process roles

| Process | What it does | What it does not do |
|---|---|---|
| `control-plane-agent` daemon | opens a session, finds work, claims, starts the run, prepares the working copy, commits and publishes the branch, writes artifacts, completes the run, creates the review | does not write code |
| Adapter (`claude-code`, `codex`) | builds the prompt, starts the agent CLI, writes the session checkpoint, publishes the summary and the transcript | does not decide the run outcome, does not hold the claim |
| Coding agent inside the run | changes files in the working copy, can read context and leave checkpoints through MCP | does not claim, does not complete, does not push, does not open a PR |

The boundary is fundamental: the run outcome is decided by whoever holds the claim and its
fencing token, that is, the daemon. The agent inside is not even offered the authoritative
MCP tools (see [Adapters](adapters.md#mcp-inside)).

## Lifecycle of one task

```mermaid
sequenceDiagram
    autonumber
    participant D as Daemon
    participant CP as Control Plane
    participant WS as Working copy pool
    participant AD as Adapter + CLI
    participant G as Forge
    D->>CP: GET /work/available (assignedToMe, workspaceId…)
    D->>CP: claim the task (intent "autonomous-agent auto")
    D->>CP: start run (claimId + fencingToken)
    D->>WS: acquire(publicId) — worktree on task/<publicId> + neighbours
    D->>CP: checkpoint execution.workspace
    D->>AD: execute(task, run, client, workspace)
    AD->>CP: checkpoint <adapter>.session, actions tool.*, context
    AD-->>D: artifacts report + transcript
    D->>WS: commit
    D->>G: push task/<publicId> (if a remote is set)
    D->>CP: checkpoint (head, published) + commit artifact
    D->>CP: succeed run
    CP->>CP: verification attempt: type criteria (for example review → merge)
```

If anything goes wrong at any step, the run ends with an honest `fail` and a reason
(`lease_lost`, `ownership_lost`, `workspace_busy`, exception text with host paths stripped),
and the working copy is kept for the next attempt.

## What a runner takes

The `work` section of the agent description defines which work to take:

- `onlyAssigned` (default `true`) — only tasks assigned to this agent's principal
  (`assigneeId`): "I can take it" and "it is meant for me" are different questions;
- `workspace` — only tasks of this Workspace (together with its subtree);
- `project` (+ `includeSubprojects`) — only tasks of the project;
- `taskTypes` — only tasks of these types.

Tasks whose type declares skill execution (`execution = {skill, version}`) go not to the
coding adapter but to the skill executor of the same daemon — and only if it can run that
skill. Without the `task_types.read` permission the daemon does not touch such tasks at all
(fail-closed).

!!! warning "No queue narrowing"
    An agent with `onlyAssigned: false` and no `workspace` takes any available task of the
    tenant, including epics and tasks of other repositories. Release an executor into the
    shared queue only deliberately. The same applies to a daemon started manually without a
    description: its `CONTROL_PLANE_AGENT_ONLY_ASSIGNED` filter is off by default.

## Deployment

An executor always runs in a container on a fleet node: the perimeter is the container,
which holds only the replica volume with working copies and mirrors and the secrets named in
the agent description. A node can be a dedicated server, a VM, or a developer machine — any
machine with Docker and outbound HTTPS to the deployment. The daemon can also be started
manually, without a description (env mode), but only for debugging. Details are in
[Installing an executor](installation.md).

## Sections

| Article | About |
|---|---|
| [Agents by description](declarative-agents.md) | the `Agent` kind: description sections, revisions, applying through packages, stopping and retiring, service agents |
| [Nodes and fleet](fleet.md) | the controller and nodes: registration, `node.yaml`, placement by labels, PAT delivery, failures |
| [Agent identity](agent-identity.md) | a separate `agent` principal, a binding without admin, the PAT and its storage |
| [Installing an executor](installation.md) | the controller, the image, a node, the first agent, updates, manual launch for debugging |
| [Executor adapters](adapters.md) | Claude Code, Codex, OpenCode: CLI launch, tokens, permission modes, prompt |
| [Working copies](execution-workspace.md) | the `worktrees/<id>/<repo>` container, neighbours, branches, evidence, publishing |
| [Run trace](trace.md) | the `transcript` artifact, `tool.*` actions, publishing flags |
| [Configuration](configuration.md) | what comes from the revision, host variables, and env mode |

## See also

- [Catalog packages](../control-plane/catalog-packages.md#agent)

- [Execution — claims and runs](../control-plane/execution.md)
- [Harness protocol](../control-plane/harness-protocol.md)
- [Operator work](../operator/index.md)
- [Troubleshooting: execution and runner](../troubleshooting/runner.md)
