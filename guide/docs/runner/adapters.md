
# Executor adapters

An adapter is the replaceable part of the runner that answers one question: "make the coding
agent do the work". The article describes three implementations — Claude Code, Codex, and
OpenCode — how they start the CLI, where they get credentials, which permission mode they
run in, and what goes into the prompt.

## Adapter contract

The coordination loop belongs to the `control-plane-agent` daemon; the adapter receives one
task:

```python
async def execute(task, run, client, workspace) -> list[ArtifactSpec]: ...
```

| Argument | What it is |
|---|---|
| `task` | the whole task (`publicId`, `title`, `description`, `typeKey`, …) |
| `run` | the current run (`id`, `attempt`) |
| `client` | a `ControlPlaneClient` under the agent's identity |
| `workspace` | the task's working copy, or `None` if the working copy pool is not configured |

The adapter returns artifact specifications (`report`, `transcript`); the daemon checks them
for portability (no local paths and no credentials), writes them, adds a `commit` artifact,
and calls `succeed_run` itself. An exception from the adapter turns into `fail_run` with a
reason from which host paths are stripped.

`CONTROL_PLANE_AGENT_ADAPTER` selects the adapter:

| Value | Implementation | Purpose |
|---|---|---|
| `echo` (default) | built-in | protocol checks: writes an `echo.observe` action and a `report` artifact with the task title |
| `claude-code` | `control_plane_claude` | Claude Code CLI (`claude -p`) |
| `codex` | `control_plane_codex` | Codex CLI (`codex exec`) |

Vendor adapters are imported lazily: the daemon runs on a host where the CLI is not
installed, and an unknown name produces `unknown adapter '…'` at startup.

OpenCode works differently — it is a separate harness with its own loop (see
[below](#opencode)).

## Rules common to all adapters

- **The prompt goes through stdin**, never as an argument: process arguments are visible to
  everyone on the host.
- **Secrets only through the inherited environment.** The subscription token or API key
  never ends up in argv or in the run's configuration files.
- **The agent session survives a restart.** The session identifier is written to a run
  checkpoint; the next attempt of the same task continues the same conversation instead of
  starting a new one.
- **The raw stream stays on the host.** Every CLI output line is written to the local log
  `<runtime>/sessions/<publicId>-<session>.jsonl` (`0600`, capped at 32 MB per file over its
  whole lifetime, including resumed turns). Only the summary, counters, and a bounded
  redacted transcript go to Control Plane (see [Run trace](trace.md)).
- **One turn per run.** The adapter does not conduct a multi-turn dialogue; continuing the
  work is the next run, which reads the checkpoints of the previous one.
- **The daemon decides the outcome.** The agent is told explicitly: do not claim, do not
  complete, do not push, and do not open a pull request — the daemon publishes the branch.

## Claude Code

### How it starts

```text
claude --print --output-format stream-json --verbose \
       --permission-mode <mode> \
       --session-id <uuid>            # new session
       | --resume <uuid>              # continuation
       [--model <model>] \
       [--mcp-config <runtime>/mcp.json --strict-mcp-config] \
       [--disallowedTools mcp__control-plane__cp_claim_task …]
```

The process working directory is the task's working copy (`worktrees/<publicId>/<repo>`).

The adapter generates the session identifier **before** starting the process and immediately
writes it to the `claude-code.session` checkpoint (`{"claudeSessionId", "resumed", "phase":
"started"}`). If the runner crashes in the middle of a turn, the next attempt finds this
checkpoint and passes `--resume`. When the turn ends, a checkpoint with `phase: finished`,
`subtype`, `turns` is written; on error — `phase: failed` and the exception type (without
the text: it can contain paths).

The turn result is the `result` event of the stream-json stream. A turn with `is_error` or a
non-zero exit code fails the run; a turn without a `result` event produces the error
`claude exited with code … without a result` with the stderr tail in the runner log.

### Authentication

| Option | Variable | Note |
|---|---|---|
| Subscription | `CLAUDE_CODE_OAUTH_TOKEN` | issued by `claude setup-token` on a machine with a browser; belongs to a human |
| API key | `ANTHROPIC_API_KEY` | pay per token |

The adapter does not read or copy the token: the child process and the MCP servers it starts
inherit the runner environment. Consequence: the agent sees the token in its environment —
this is a property of the design, so the perimeter is built around the process (user,
container), not inside it.

!!! note "Subscription window"
    Exhausting the subscription window is currently an ordinary turn error and `fail_run`.
    Parallel runs on a human's token consume the same window as that person's interactive
    sessions.

### Permission mode

`CONTROL_PLANE_CLAUDE_PERMISSION_MODE` is passed to `--permission-mode`:

| Mode | Behavior | When |
|---|---|---|
| `acceptEdits` (default) | file edits without prompts, other commands require confirmation | a safe start; in non-interactive mode the agent cannot run commands (tests, build) |
| `bypassPermissions` | all tools without prompts | the working mode of an autonomous executor — only inside a perimeter |

Without `bypassPermissions` an autonomous agent cannot run a single shell command: nobody is
there to confirm, and reports show it as "every tool call requires approval". The perimeter
in that case is an unprivileged user with `ProtectSystem=strict` or a container.

### MCP inside the agent {#mcp-inside}

With `CONTROL_PLANE_CLAUDE_MCP=1` (default) the adapter writes `<runtime>/mcp.json` (`0600`)
and passes it with `--strict-mcp-config` — the agent gets exactly one MCP server,
`control-plane`, and does not see other servers configured for the user:

```json
{"mcpServers": {"control-plane": {"type": "stdio", "command": "control-plane-mcp", "args": []}}}
```

The file contains neither the server address nor a token: `control-plane-mcp` inherits the
runner environment and resolves identity the same way the daemon does. The agent works under
the same principal.

Through MCP the agent reads `cp_get_run_context`, writes checkpoints and artifacts on its
own. But **the authoritative tools are taken away from it** with the `--disallowedTools` flag.
The list is not hard-coded in the adapter; it is computed from the MCP server itself
(`withheld_tool_names()`): everything that is not marked read-only and is not part of the
evidence tool set is withheld.

| Available to the agent | Not available to the agent (examples) |
|---|---|
| all read-only: `cp_whoami`, `cp_context`, `cp_get_task`, `cp_get_run_context`, `cp_list_*`, `cp_search_tools`, … | `cp_claim_task`, `cp_release_task`, `cp_start_run` |
| evidence: `cp_checkpoint`, `cp_record_action`, `cp_create_artifact`, `cp_remember`, `cp_comment`, `cp_request_approval` | `cp_complete_run`, `cp_fail_run`, `cp_suspend_run`, `cp_prepare_handoff` |
| | `cp_create_task`, `cp_update_task`, relations, goals |
| | `cp_approve`, `cp_reject`, `cp_invoke_skill`, `cp_launch_child`, `cp_control_run`, `cp_focus_project` |

A tool without an annotation is treated as authoritative — forgotten markup closes the door
rather than opening it.

!!! warning "This narrows the task; it is not a security boundary"
    The agent works under the same credential as the daemon and can technically reach the
    API bypassing MCP. The real ceiling is the permissions of the agent's binding (and the
    child grant the server computes for child runs). `--disallowedTools` only removes the
    temptation.

### Prompt

The prompt is assembled from parts in a fixed order:

1. **System note**: you are an autonomous executor of one task; the `control-plane` MCP is
   available for context, records, and checkpoints; do not claim, do not complete; work only
   in the current directory; do not push and do not open a PR; finish with a summary.
2. **Task**: `# Task <publicId>: <title>` and the description.
3. **Project** (if the task belongs to a project): status and template.
4. **Inputs** of the task, if its type declares them (section `## Входы`, see
   [below](#task-inputs)).
5. **Task context** from memory (section `## Контекст задачи`, see below).
6. **Repository conventions** — the contents of `CONTROL_PLANE_CLAUDE_PROMPT_FILE` under the
   heading `## Repository conventions`.

The system note also tells the agent that a result file that is not part of the code (a
document, a report) is delivered by calling `cp_create_artifact` with the `file` parameter:
the tool uploads the file to Control Plane, and it becomes an artifact of the run (see
[Content in storage](../control-plane/artifacts.md#content)).

### Conventions file

`CONTROL_PLANE_CLAUDE_PROMPT_FILE` is the path to a text file appended to **every** prompt.
The task description says "what to do"; the conventions file says "how this repository
works": how to run tests, what never to commit, where ADRs live, how to number migrations,
which services can be trusted as contracts. Otherwise this knowledge costs one review round
per branch.

The file is read at every turn start — an edit takes effect without restarting the runner.
An unreadable file is logged as a warning, and the turn continues without it.

Example structure:

```markdown
# Conventions for the executor agent

## Environment
- The working copy is the current directory. The neighbours `../platform-auth-sdk` are at
  superproject revisions and are read-only.
- Do not invent another service's contract: take the schemas from the neighbour's code and
  pin them with a contract test.
- Full test run: `uv run ruff check . && uv run pytest -q`.

## Rules
- If you change an API contract or a DB schema, update the ADR in the same commit.
- Do not commit secrets, absolute paths, `.env`, build artifacts.
- Do not touch `main`: the daemon commits and publishes the task branch itself.

## Report
First line: what was done. Then: changed places, which tests were run and with what result,
what needs a human decision.
```

### Parameters

| Variable | Default | Meaning |
|---|---|---|
| `CONTROL_PLANE_CLAUDE_BINARY` | `claude` | path to the CLI |
| `CONTROL_PLANE_CLAUDE_MODEL` | as configured in the CLI | model (`--model`) |
| `CONTROL_PLANE_CLAUDE_PERMISSION_MODE` | `acceptEdits` | permission mode |
| `CONTROL_PLANE_CLAUDE_TIMEOUT` | `3600` | cap for one turn, seconds; when it expires, the process is killed and the run fails |
| `CONTROL_PLANE_CLAUDE_MCP` | `1` | `0` — do not pass MCP inside |
| `CONTROL_PLANE_CLAUDE_LOGS` | `1` | `0` — do not write the local session log |
| `CONTROL_PLANE_CLAUDE_RESUME` | `1` | `0` — always start a new session |
| `CONTROL_PLANE_CLAUDE_RUNTIME_DIR` | `~/.claude-runner` | where `mcp.json` and `sessions/` live |
| `CONTROL_PLANE_CLAUDE_PROMPT_FILE` | — | repository conventions file |

!!! tip "Turn timeout"
    Tasks with a migration, an API, a client, and tests rarely fit into an hour. For such
    queues, raise `CONTROL_PLANE_CLAUDE_TIMEOUT` (for example to `10800`), keeping in mind
    that a hung turn holds the lease until the timeout ends.

## Codex

### How it starts

```text
codex exec --json --sandbox <sandbox> [--model <model>] -          # new session
codex exec --json --sandbox <sandbox> [--model <model>] resume <id> -   # continuation
```

The trailing `-` makes Codex read the prompt from stdin.

Unlike Claude Code, Codex chooses the identifier of a new session itself and reports it in
the first event of the stream (`thread.started`). Therefore, for a new session the
`codex.session` checkpoint (`{"codexSessionId", …}`) is written when this event is read —
after the process has started but before the actual work. To continue a known session, the
checkpoint is written before the start, as with Claude Code.

### Specifics

- **No MCP inside.** The Control Plane MCP is not passed to Codex: the whole task context is
  embedded in the prompt, and the agent is told it has no Control Plane tools.
- **Authentication** — `auth.json` in `$CODEX_HOME` (default `~/.codex/auth.json`; a ChatGPT
  subscription or a key) or `OPENAI_API_KEY`. The adapter does not touch `CODEX_HOME`, but
  Codex rewrites `auth.json` on every start — the directory must be writable and persistent
  (a volume in a container), otherwise a new login is required after a restart.
- **Sandbox** — `CONTROL_PLANE_CODEX_SANDBOX`, default `workspace-write` (edits in the
  working copy). Codex's own read-only mode is useless for the agent. For a reviewer that
  needs to run tests and `git fetch`, `danger-full-access` is used — also only inside a
  perimeter.
- **Quota exhaustion** is recognized by the error text (`rate limit`, `usage limit`, `quota`,
  `429`) and raised as a separate exception, but for now, as with Claude Code, it leads to an
  ordinary `fail_run`.
- The Codex adapter has no conventions file; put everything needed into the task description.
- The turn action is `codex.turn`; the artifacts are `report` (summary) and `transcript`.

### Parameters

| Variable | Default | Meaning |
|---|---|---|
| `CONTROL_PLANE_CODEX_BINARY` | `codex` | path to the CLI |
| `CONTROL_PLANE_CODEX_MODEL` | as configured in the CLI | model |
| `CONTROL_PLANE_CODEX_SANDBOX` | `workspace-write` | sandbox mode |
| `CONTROL_PLANE_CODEX_TIMEOUT` | `3600` | turn cap, seconds |
| `CONTROL_PLANE_CODEX_RESUME` | `1` | `0` — always a new session |
| `CONTROL_PLANE_CODEX_LOGS` | `1` | `0` — no local log |
| `CONTROL_PLANE_CODEX_RUNTIME_DIR` | `~/.codex-runner` | directory of the `sessions/` logs |
| `CONTROL_PLANE_CODEX_CREDENTIAL_CLASS` | — | credential class label (subscription / key); goes into the artifact metadata as `credentialClass` |

## OpenCode {#opencode}

`control-plane-opencode` is a standalone harness, not a daemon adapter: it has its own
discovery → claim → run loop, and it drives an `opencode serve` process through its HTTP API.

| Aspect | Value |
|---|---|
| Launch | `control-plane-opencode` next to `opencode serve` |
| OpenCode address | `OPENCODE_SERVER` (default `http://127.0.0.1:4096`), password — `OPENCODE_SERVER_PASSWORD` |
| Model and agent | `OPENCODE_MODEL`, `OPENCODE_AGENT` |
| Queue | `CONTROL_PLANE_AGENT_WORKSPACE`, `CONTROL_PLANE_AGENT_PROJECT`, `CONTROL_PLANE_AGENT_SUBPROJECTS`, `CONTROL_PLANE_AGENT_POLL` |
| Credential | Control Plane API key only (`CONTROL_PLANE_API_KEY` or the `control-plane login` store) |
| Working copy | no worktree pool; works in the process directory |
| Continuity | `opencode.session` checkpoint with `openCodeSessionId` and `lastMessageId` |
| Result | `opencode.prompt` action, `report` artifact (`opencode-summary`) |
| Transcript | not published |

!!! warning "Limitations of the OpenCode harness"
    The harness does not support IAM identity (only a legacy API key), does not filter tasks
    by assignment, and does not use working copies. On a server where legacy keys are turned
    off, it cannot authenticate. Use it for experiments; for real work, use the daemon with
    the `claude-code` or `codex` adapter.

## Task inputs { #task-inputs }

If the task type declares inputs (`artifactSchema.inputs`, see
[Inputs and outputs](../control-plane/task-types.md#artifact-schema)), the daemon prepares
them itself before starting the adapter; Claude Code and Codex receive a section in the
prompt:

1. reads `inputs` from `GET /runs/{id}/context`;
2. downloads every input whose content is in storage (`contentState: stored`) through
   `GET /artifacts/{id}/content?forTask=<task>` into `<runtime>/inputs/<key>/<name>`. The
   `<runtime>` directory is the task directory next to the working copy, not inside it: an
   input is not part of the change, and `git add -A` does not pick it up. The root is
   `CONTROL_PLANE_AGENT_RUNTIME_DIR`, default `.runtime` at the root of the working copy pool
   (without a pool — `~/.control-plane-agent/runtime`);
3. the file name is sanitized to a single path component: separators and special characters
   are replaced with `_`, leading dots are removed, the length is limited;
4. the inputs directory is recreated on every run, so a new head revision replaces the old
   one; after a successful run it is deleted.

The prompt gets a `## Входы` (inputs) section — inside the fence
`<task_inputs>…</task_inputs>` with a warning that input names and contents are data from
other participants and **not instructions**. One line per input: key, type, source task and
relation, name, artifact id, media type, size, and one of:

| State | What the line contains |
|---|---|
| downloaded | `file: <local path>` |
| not downloaded | `not downloaded (<error code>); read it with cp_get_artifact_content` |
| content purged | `content purged by an administrator` |
| reference without content | `reference only: <uri>` |

A failed download does not fail the run: the agent sees which input is unavailable and why,
and can get it itself with the `cp_get_artifact_content` MCP tool (Claude Code). Whether the
work can do without the input is up to the agent, which says so in the summary.

## Task context in the prompt

All three implementations request the task's working context from Control Plane (`POST
/api/v1/context` with `task`, `run`, and `includeMemory`) and turn it into a
`## Контекст задачи` (task context) section with one shared function. Section rules:

- memory items are grouped by package sections (`current`, `relevant_facts`,
  `related_entities`, `documents`, then the rest), each with a source `[source: …]`;
- everything sits inside the fence `<recalled_memory>…</recalled_memory>` with a warning that
  this is data from various participants and **not instructions**; an item cannot close the
  fence early or start its own prompt line;
- every line passes redaction of host paths and credentials;
- one item is no longer than 600 characters; the whole section is no larger than
  `CONTROL_PLANE_CONTEXT_BUDGET_CHARS` (default 12000); what does not fit is counted in the
  line `… N more item(s) omitted by the context budget`;
- if memory is unavailable, empty, or does not fit — a single line
  `контекст памяти недоступен: <причина>` ("memory context unavailable: <reason>"). The run
  does not fail because of this: the task itself is authoritative.

More on memory and context: [Task context and memory](../control-plane/context.md).

## Comparison

| | Claude Code | Codex | OpenCode |
|---|---|---|---|
| Type | daemon adapter | daemon adapter | separate harness |
| `harness.type` | `claude-code` | `codex` | `opencode` |
| Control Plane credential | IAM PAT or API key | IAM PAT or API key | API key only |
| Working copies and branches | yes | yes | no |
| Control Plane MCP inside | yes, without authoritative tools | no | no |
| Conventions file | `CONTROL_PLANE_CLAUDE_PROMPT_FILE` | no | no |
| Transcript and `tool.*` actions | yes | yes | no |
| Session checkpoint | `claude-code.session` (before start) | `codex.session` (on `thread.started`) | `opencode.session` |
| "Stopped" signal (`executor_blocked`) | `blocked` checkpoint (`cp_checkpoint`) | file `CONTROL_PLANE_BLOCKED_FILE` → `blocked` checkpoint | no |

## See also

- [Working copies](execution-workspace.md)
- [Run trace](trace.md)
- [The agent stopped without a result](declarative-agents.md#blocked)
- [Configuration](configuration.md)
- [CLI and MCP server](../control-plane/cli-and-mcp.md)
