
# Executor configuration

Where the `control-plane-agent` executor daemon gets its settings and which environment
variables it reads. The main path: the agent is described by the `Agent` kind, the daemon
takes everything about the agent from its revision, and the fleet node sets the environment
variables. The variables described below as "env mode" are needed only by a daemon started
manually for a principal without a description (local debugging). This is a reference
article for operations engineers.

## Two sources of settings

| What | Where from | Who sets it |
|---|---|---|
| What the agent is: work, executor kind, model, permission mode, instructions, working copy, neighbours, review, skills, drain period | the agent revision, `GET /api/v1/agents/me` | the author of the description in the package ([Agents by description](declarative-agents.md)) |
| What belongs to the machine: Control Plane and IAM address, credential, working copy and mirror directories, CLI binaries, MCP passthrough, local logs, trace, isolation of local skills, progress watchdog | environment variables | when started through fleet, the node: `agentEnv` and `executors.<kind>.env` from `node.yaml`, plus the variables the node sets itself ([Nodes and fleet](fleet.md#agent-container)) |

!!! tip "How to change agent settings"
    Change the model, `permissionMode`, neighbours, review, or skills by editing the agent
    description and running `package-sdk apply`: a new revision appears, and the executor
    switches to it after the current run. The `CONTROL_PLANE_AGENT_*`,
    `CONTROL_PLANE_CLAUDE_MODEL`, and similar variables have no effect on an agent with a
    description.

## Configuration mode

At startup the daemon decides whose it is by `CONTROL_PLANE_AGENT_CONFIG`:

| Value | Behavior |
|---|---|
| `auto` (default) | `GET /agents/me`: the principal is bound to an agent — revision mode; `404` — env mode |
| `revision` | an agent is required; a principal without an agent exits with code `2` |
| `env` | environment only, for a principal without an agent |

`auto` mode is not a convenience. An agent principal must name the revision in every
`start-run`; in env mode it would not start a single run (`422 agent_revision_required`).
If reading `/agents/me` at startup fails, the daemon exits with code `75` and waits for a
restart instead of guessing the mode.

### Exit codes

| Code | When | What the fleet node does |
|---|---|---|
| `0` | the agent is stopped (`state: stopped`) or retired | starts it again immediately while the agent is in the node's desired state |
| `2` | the configuration cannot be executed: no `CONTROL_PLANE_SERVER` or credential, unknown executor kind, invalid `executor.params`, `review` without `reviewer`, a mirror with a foreign `origin` | restarts with a growing pause; after three failures, `crash_looping` |
| `75` | a new agent revision appeared (after the current run) or `/agents/me` could not be read at startup | starts it again immediately |

## What comes from the revision

In revision mode, the description sections replace the env mode variables:

| Description section | Replaces in env mode |
|---|---|
| `work.workspace`, `work.project`, `work.includeSubprojects` | `CONTROL_PLANE_AGENT_WORKSPACE`, `…_PROJECT`, `…_SUBPROJECTS` |
| `work.onlyAssigned` (default `true`) | `CONTROL_PLANE_AGENT_ONLY_ASSIGNED` (default off) |
| `work.taskTypes` | — (the task type filter exists only in the description) |
| `executor.kind` | `CONTROL_PLANE_AGENT_ADAPTER` |
| `executor.params` (Claude Code) | `CONTROL_PLANE_CLAUDE_MODEL`, `…_PERMISSION_MODE`, `…_TIMEOUT`, `…_RESUME`; `tools.allow`/`tools.deny` — description only |
| `executor.params` (Codex) | `CONTROL_PLANE_CODEX_MODEL`, `…_SANDBOX`, `…_TIMEOUT`, `…_RESUME`, `…_CREDENTIAL_CLASS` |
| `executor.instructions` | the `CONTROL_PLANE_CLAUDE_PROMPT_FILE` file |
| `workingCopy.repository`, `neighbours`, `superproject` (URL) | `CONTROL_PLANE_AGENT_REPO`, `…_NEIGHBOURS`, `…_SUPERPROJECT` (paths to mirrors) |
| `workingCopy.directory`, `baseRef` | `CONTROL_PLANE_AGENT_REPO_DIR`, `…_BASE_REF` |
| `workingCopy.publish` | `CONTROL_PLANE_AGENT_PUSH_REMOTE`, `…_SUPERPROJECT_REMOTE` (in revision mode — the mirror's `origin`) |
| `skills.protocols`, `local`, `httpOrigins`, `mcpOrigins`, `audiences`, `concurrency` | `CONTROL_PLANE_SKILLS_PROTOCOLS`, `…_LOCAL_PACKAGES`, `…_HTTP_ALLOWED_ORIGINS`, `…_MCP_ALLOWED_ORIGINS`, `…_ALLOWED_AUDIENCES`, `…_CONCURRENCY` |
| `placement.drainSeconds` | `CONTROL_PLANE_AGENT_DRAIN_SECONDS` |

What is missing from the `skills` section of the description is missing from the executor
too, even if a `CONTROL_PLANE_SKILLS_*` variable from this table is set on the host.

## Host variables

The daemon and the adapters read these variables in both modes. When started through
fleet, the node sets them; the defaults suit most installations.

### Connection and credential

| Variable | Default | Meaning |
|---|---|---|
| `CONTROL_PLANE_SERVER` | — (required) | Control Plane base URL, for example `https://platform.example.com`. Through fleet: `agentEnv` |
| `CONTROL_PLANE_IAM_URL` | — | IAM URL; setting it turns on IAM identity. Through fleet: `agentEnv` |
| `CONTROL_PLANE_IAM_TENANT` | — | IAM tenant; required together with `CONTROL_PLANE_IAM_URL` (`iam_tenant_required`). Through fleet, set by the node |
| `CONTROL_PLANE_IAM_AUDIENCE` | `control-plane` | audience of the exchanged access token |
| `CONTROL_PLANE_IAM_SCOPES` | the whole PAT ceiling ∩ audience | scopes separated by spaces or commas |
| `IAM_PRINCIPAL` | — | the IAM principal of this process; needed if the store has several PATs of the same tenant. Through fleet, set by the node |
| `IAM_CREDENTIAL_MODE` | — | `environment` (or `ci`) — allows a PAT from `IAM_PLATFORM_ACCESS_TOKEN` |
| `IAM_PLATFORM_ACCESS_TOKEN` | — | PAT in the environment; without `IAM_CREDENTIAL_MODE` — `iam_environment_mode_required`. The reference image takes it from `/run/secrets/agent-pat` |
| `IAM_NO_KEYCHAIN` | — | `1` — do not look for the PAT in the macOS Keychain |
| `XDG_CONFIG_HOME` | `~/.config` | where to look for `iam/credentials.json` |
| `CONTROL_PLANE_API_KEY` | — | legacy API key; only if IAM is not configured and the server still accepts such keys |
| `HOME` | — | must be set: `~/.config`, `~/.gitconfig`, and the default runtime directories depend on it |

Details: [Agent identity](agent-identity.md).

### Daemon and working copies

| Variable | Default | Meaning |
|---|---|---|
| `CONTROL_PLANE_AGENT_CONFIG` | `auto` | configuration mode (see above) |
| `CONTROL_PLANE_AGENT_POLL` | `5` | pause between queue polls when there is no work, seconds |
| `CONTROL_PLANE_AGENT_WORKTREE_ROOT` | in revision mode `~/.control-plane-agent/worktrees` | working copy directory. The reference image sets `/runner/worktrees` (the replica volume) |
| `CONTROL_PLANE_AGENT_MIRRORS` | `<WORKTREE_ROOT>/.mirrors` | where the bare mirrors of the revision's repositories live; a missing mirror is cloned |
| `CONTROL_PLANE_AGENT_KEEP_WORKSPACES` | off | `1` — do not delete the copy after success |
| `CONTROL_PLANE_AGENT_MAX_WORKSPACES` | `8` | how many idle copies to keep on disk |
| `CONTROL_PLANE_AGENT_RUNTIME_DIR` | `<WORKTREE_ROOT>/.runtime`, without a pool — `~/.control-plane-agent/runtime` | where task inputs are downloaded: `<directory>/<publicId>/inputs/<key>/<name>` (see [Task inputs](adapters.md#task-inputs)) |

In one cycle the daemon looks through up to 10 available tasks and takes the first one it
can execute. The session and claim heartbeat runs every 60 seconds. In revision mode the
daemon re-reads `/agents/me` between runs (no more often than once every 30 seconds when
idle).

### Run watchdog

| Variable | Default | Meaning |
|---|---|---|
| `CONTROL_PLANE_AGENT_CONTROL_POLL_SECONDS` | `15` | how often to read the run for a cancellation request (at least once every 30 s) |
| `CONTROL_PLANE_AGENT_STALL_WARN_SECONDS` | `600` | after this many seconds without new actions — a `stall` checkpoint; `0` disables the step |
| `CONTROL_PLANE_AGENT_STALL_STOP_SECONDS` | `1800` | after this the executor stops, the run fails with `no_progress`, the task returns to the queue; `0` disables |
| `CONTROL_PLANE_AGENT_ACTION_MAX_SECONDS` | `3600` | how long an unfinished last action (long tests, a build) may live before the watchdog stops the run; not less than `STALL_STOP` |

### Adapters: host part

| Variable | Default | Meaning |
|---|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | — | Claude Code subscription token (`claude setup-token`); inherited by the CLI. The reference image takes it from `/run/secrets/claude-oauth-token` |
| `ANTHROPIC_API_KEY` | — | alternative to the subscription; inherited by the CLI |
| `CONTROL_PLANE_CLAUDE_BINARY` | `claude` | path to the CLI |
| `CONTROL_PLANE_CLAUDE_MCP` | `1` | `0` — do not pass the `control-plane` MCP into the agent |
| `CONTROL_PLANE_CLAUDE_LOGS` | `1` | `0` — do not write the local session log |
| `CONTROL_PLANE_CLAUDE_RUNTIME_DIR` | `~/.claude-runner` | `mcp.json` and `sessions/`. The reference image sets `/runner/claude` |
| `CODEX_HOME` | `~/.codex` | Codex `auth.json` directory; must be writable and persistent |
| `OPENAI_API_KEY` | — | alternative to subscription login; inherited by the CLI |
| `CONTROL_PLANE_CODEX_BINARY` | `codex` | path to the CLI |
| `CONTROL_PLANE_CODEX_LOGS` | `1` | `0` — no local log |
| `CONTROL_PLANE_CODEX_RUNTIME_DIR` | `~/.codex-runner` | `sessions/` directory |

### Context and trace

| Variable | Default | Meaning |
|---|---|---|
| `CONTROL_PLANE_CONTEXT_BUDGET_CHARS` | `12000` | budget of the task context section in the prompt (all adapters); an invalid value falls back to the default |
| `CONTROL_PLANE_TRACE_TRANSCRIPT` | `1` | publish the `transcript` artifact |
| `CONTROL_PLANE_TRACE_ACTIONS` | `1` | write `tool.*` run actions |
| `CONTROL_PLANE_TRACE_TOOL_RESULTS` | `1` | keep tool results in the transcript |

Trace flags are turned off with the values `0`, `false`, `no`, `off`. Details:
[Run trace](trace.md).

### Skills: host part

| Variable | Default | Meaning |
|---|---|---|
| `CONTROL_PLANE_SKILLS_LOCAL_ISOLATION` | `process` | `process` — a child process killed on timeout and lease loss; `thread` — a thread that cannot be stopped |
| `CONTROL_PLANE_SKILLS_MCP_SERVERS` | — | JSON `{name: {command, args, env}}` for `stdio:<name>` endpoints |
| `CONTROL_PLANE_SKILLS_PRIVATE_HOSTS` | — | hosts of allowed origins that may resolve to non-public addresses (services inside the cluster) |

The executor principal needs the `skills.execute` permission for skills. Details:
[skill-sdk](../sdk/skill-sdk.md).

## Env mode: configuration without a description { #env-mode }

For a principal that is not bound to an agent (local debugging of the daemon, your own
experiments), everything comes from the environment. These variables have no effect on an
agent with a description.

!!! warning "Not for permanent executors"
    Permanent executors are described by the `Agent` kind and started through fleet: that way
    the configuration goes through review, is versioned, and is visible in runs
    (`agentRevisionId`). Env mode is kept for debugging and gives none of this.

### Queue

| Variable | Default | Meaning |
|---|---|---|
| `CONTROL_PLANE_AGENT_ADAPTER` | `echo` | `echo`, `claude-code`, or `codex` |
| `CONTROL_PLANE_AGENT_ONLY_ASSIGNED` | off | `1` — only tasks assigned to this principal |
| `CONTROL_PLANE_AGENT_WORKSPACE` | — | the Control Plane Workspace to take tasks from (with its subtree) |
| `CONTROL_PLANE_AGENT_PROJECT` | — | project |
| `CONTROL_PLANE_AGENT_SUBPROJECTS` | off | `1` — including subprojects |
| `CONTROL_PLANE_AGENT_DRAIN_SECONDS` | — | how long to wait for an in-flight run on `SIGTERM`; without it the run is finished to the end |

!!! warning "No queue narrowing"
    A daemon without `CONTROL_PLANE_AGENT_ONLY_ASSIGNED` and without
    `CONTROL_PLANE_AGENT_WORKSPACE` takes any available task of the tenant. Create a separate
    workspace for checks.

### Working copies

| Variable | Default | Meaning |
|---|---|---|
| `CONTROL_PLANE_AGENT_REPO` | — | bare mirror from which copies are cut; together with `WORKTREE_ROOT` turns on the pool |
| `CONTROL_PLANE_AGENT_REPO_DIR` | repository name without `.git` | name of the copy directory inside the task container |
| `CONTROL_PLANE_AGENT_BASE_REF` | `HEAD` | what to branch from |
| `CONTROL_PLANE_AGENT_PUSH_REMOTE` | — | remote for publishing `task/<publicId>` branches and updating the base; empty — the work stays local |
| `CONTROL_PLANE_AGENT_NEIGHBOURS` | — | neighbours: `name=mirror-path` separated by commas or spaces |
| `CONTROL_PLANE_AGENT_SUPERPROJECT` | — | mirror of the superproject that pins the neighbour revisions; required with neighbours |
| `CONTROL_PLANE_AGENT_SUPERPROJECT_REF` | `HEAD` | superproject ref for reading revisions |
| `CONTROL_PLANE_AGENT_SUPERPROJECT_REMOTE` | — | remote for updating the superproject before the layout |

Details: [Working copies](execution-workspace.md).

### Review

The daemon has no review variables: review and merge are declared by the task type as
acceptance criteria and executed by the core (see
[Type acceptance](../control-plane/task-types.md#type-acceptance)). The daemon puts
everything the criteria need into the `commit` artifact — the branch, the commit, the
published flag, the remote address, and the target branch.

### Adapters

| Variable | Default | Meaning |
|---|---|---|
| `CONTROL_PLANE_CLAUDE_MODEL` | as in the CLI | model |
| `CONTROL_PLANE_CLAUDE_PERMISSION_MODE` | `acceptEdits` | `--permission-mode` |
| `CONTROL_PLANE_CLAUDE_TIMEOUT` | `3600` | turn cap, seconds |
| `CONTROL_PLANE_CLAUDE_RESUME` | `1` | `0` — do not continue the session of the previous attempt |
| `CONTROL_PLANE_CLAUDE_PROMPT_FILE` | — | conventions file appended to every prompt; re-read on every turn |
| `CONTROL_PLANE_CODEX_MODEL` | as in the CLI | model |
| `CONTROL_PLANE_CODEX_SANDBOX` | `workspace-write` | `--sandbox` |
| `CONTROL_PLANE_CODEX_TIMEOUT` | `3600` | turn cap, seconds |
| `CONTROL_PLANE_CODEX_RESUME` | `1` | `0` — do not continue the session |
| `CONTROL_PLANE_CODEX_CREDENTIAL_CLASS` | — | credential class label in the artifact metadata (`credentialClass`) |

### Skills

| Variable | Default | Meaning |
|---|---|---|
| `CONTROL_PLANE_SKILLS_PROTOCOLS` | `local` if packages are set; otherwise off | protocols: `local`, `http`, `mcp` |
| `CONTROL_PLANE_SKILLS_LOCAL_PACKAGES` | — | `module:function` entry points or packages with `CONTRACT` and a `local` implementation |
| `CONTROL_PLANE_SKILLS_HTTP_ALLOWED_ORIGINS` | — | `scheme://host[:port]` that the `http` protocol may call |
| `CONTROL_PLANE_SKILLS_MCP_ALLOWED_ORIGINS` | — | the same for remote MCP servers |
| `CONTROL_PLANE_SKILLS_ALLOWED_AUDIENCES` | — | IAM audiences whose token a skill may obtain; `control-plane`, `iam`, and the daemon's own audience are forbidden |
| `CONTROL_PLANE_SKILLS_CONCURRENCY` | `1` | concurrent calls alongside coding work; `0` — only when there is none |

## OpenCode harness

The separate `control-plane-opencode` process is not configured by an agent description:

| Variable | Default | Meaning |
|---|---|---|
| `CONTROL_PLANE_SERVER` | — (required) | Control Plane URL |
| `CONTROL_PLANE_API_KEY` | from the `control-plane login` store | API key (the harness does not support IAM identity) |
| `OPENCODE_SERVER` | `http://127.0.0.1:4096` | address of `opencode serve` |
| `OPENCODE_SERVER_PASSWORD` | — | OpenCode server password |
| `OPENCODE_MODEL`, `OPENCODE_AGENT` | — | OpenCode model and agent |
| `CONTROL_PLANE_AGENT_WORKSPACE`, `…_PROJECT`, `…_SUBPROJECTS`, `…_POLL` | as for the daemon | queue |
| `CP_LOG_LEVEL` | `INFO` | log level |

## Reference image entrypoint

The `deploy/agent-runner/` image (user uid `10001`) chooses its path by the
environment:

| Condition | What the entrypoint does |
|---|---|
| always | `IAM_CREDENTIAL_MODE=environment`, `IAM_PLATFORM_ACCESS_TOKEN` from `/run/secrets/agent-pat` |
| `RUNNER_MODE=skills` | no code agent and no mirrors: `CLAUDE_CODE_OAUTH_TOKEN` from `/run/secrets/claude-oauth-token` if the file is mounted (for `ctx.llm` with `SKILL_LLM_PROVIDER=claude-code`), then the daemon |
| `CONTROL_PLANE_AGENT_KEY` is set (the container was created by a fleet node) | `CONTROL_PLANE_AGENT_WORKTREE_ROOT=/runner/worktrees` and `CONTROL_PLANE_CLAUDE_RUNTIME_DIR=/runner/claude` if not set; `CLAUDE_CODE_OAUTH_TOKEN` from `/run/secrets/claude-oauth-token` if the file is mounted; then the daemon. The daemon sets up mirrors itself from the revision |
| otherwise (env mode) | the subscription token and `/run/secrets/github-token` are required; clones the mirrors `RUNNER_REPO_URL`, `RUNNER_SDK_URL`, `RUNNER_SUPERPROJECT_URL`, `RUNNER_EXTRA_MIRRORS` (`url=path,url=path`) and runs `fetch` on them; then the daemon |

## Example: agent environment on a fleet node

The node assembles the container environment from three sources. In `node.yaml`:

```yaml
executors:
  claude-code:
    image: agent-runner:1.4.0
    dataPath: /runner                 # working copies and mirrors on the replica volume
    env:
      IAM_NO_KEYCHAIN: "1"
      CP_TEST_DATABASE_URL: postgresql+psycopg://test:test@db-test:5432/test
agentEnv:
  CONTROL_PLANE_SERVER: https://platform.example.com
  CONTROL_PLANE_IAM_URL: https://platform.example.com/iam
  CONTROL_PLANE_IAM_SCOPES: control-plane:read control-plane:write
```

The node itself adds `CONTROL_PLANE_AGENT_KEY`, `CONTROL_PLANE_IAM_TENANT`,
`IAM_PRINCIPAL`, `FLEET_REPLICA` and mounts `/run/secrets/agent-pat` and the secrets from
the description. Everything else (model, permission mode, repositories, review) is in the
agent description.

## Configuration errors at startup

| Message | What to fix |
|---|---|
| `control-plane-agent requires CONTROL_PLANE_SERVER` | set `CONTROL_PLANE_SERVER` |
| `control-plane-agent has no credentials for <server>` | configure IAM (`CONTROL_PLANE_IAM_URL`, `CONTROL_PLANE_IAM_TENANT` + PAT) or an API key |
| `CONTROL_PLANE_AGENT_CONFIG='…': expected one of auto, revision, env` | the mode value |
| `CONTROL_PLANE_AGENT_CONFIG=revision, but this principal is not an agent` | the principal is not bound to an agent: publish a description or remove `revision` |
| `could not read this principal's agent: …` (exit 75) | Control Plane is unavailable at startup; restart the process |
| `<key>@<N> cannot be run here: …` | the revision cannot run on this image: executor kind, `executor.params`, `workingCopy`, `review`, `skills` — see the text after the colon |
| `unknown adapter '<name>' (available: [...])` | `CONTROL_PLANE_AGENT_ADAPTER` (env mode) |
| `adapter '<name>' is not installed on this runner` | install the package with the adapter |
| `skill executor misconfigured: …` | `CONTROL_PLANE_SKILLS_*` variables (env mode) |
| `neighbours require a superproject that pins their revisions` | neighbours without a superproject: `workingCopy.superproject` or `CONTROL_PLANE_AGENT_SUPERPROJECT` |

## See also

- [Agents by description](declarative-agents.md)
- [Nodes and fleet](fleet.md)
- [Installing executors](installation.md)
- [Executor adapters](adapters.md)
- [Environment variables (consolidated reference)](../reference/environment.md)
- [Permissions and scopes](../reference/permissions.md)
