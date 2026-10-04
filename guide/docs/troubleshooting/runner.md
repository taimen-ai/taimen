
# Execution and runner

Failures of the autonomous executor (`control-plane-agent`) and of task runs:
the executor does not pick up work, a run fails, a branch is not published, the
machine runs out of memory. This article is for engineers who maintain the
runner host and for operators who investigate failed runs.

## How to see quickly what is going on

```bash
# container variant
docker compose -f <executor compose file> ps
docker compose -f <executor compose file> logs --since 30m runner

# systemd variant
systemctl status <unit>
journalctl -u <unit> -n 100      # or the log file from the unit's StandardOutput
```

Look for the following in the log:

- credential errors (`iam_*`, `has no credentials`): the executor cannot even
  open a session;
- `failure_reason` on `fail_run`: why a specific run was closed;
- `no task_types.read`, `workspace busy`, `lease lost`, `no changes`.

A failed run is also visible in Control Plane: `failure_reason` on the run
card, and the run trace, which is the `transcript` artifact plus `tool.<name>`
actions (see [Run trace](../runner/trace.md)).

## Run termination reasons (`failure_reason`)

| `failure_reason` | What happened | What to do |
|---|---|---|
| `restart_recovery` | The daemon restarted in the middle of a run (deployment, OOM, machine reboot). On startup it found its orphaned run and closed it; the task returned to the queue | Nothing, if it is a one-off. If it repeats on the same task, check for OOM (below) |
| `workspace_busy` | The task's working copy is held by another process (a lock in the working copy directory) | Check whether two daemons run with the same `CONTROL_PLANE_AGENT_WORKTREE_ROOT` |
| `lease_lost` | The claim lease expired while the adapter was working (a heartbeat failed); the daemon stopped writing to avoid a fencing rejection | Check the network path to the platform and API availability; if frequent, look for long process stalls (swap, CPU quota) |
| `ownership_lost` | The claim was taken over or released while the daemon was working | Find out who else claimed the task; make sure the executors have different principals |

### Skill invocation errors

If a task is executed by a skill (an HTTP call under a contract), the failure
comes with a skill code:

| Code | Cause | Fix |
|---|---|---|
| `insecure_endpoint` | The skill contract requires a token, but the endpoint is not `https://` | Fix the skill endpoint; tokens are sent over https only |
| `audience_not_allowed` | The executor does not issue tokens for the skill's audience | Add the audience to the executor's `CONTROL_PLANE_SKILLS_ALLOWED_AUDIENCES` |
| `executor_auth_unavailable` | The executor could not obtain a token for the audience (no IAM identity, or the exchange was rejected). The error is retryable: another executor can run the skill | Check the executor's PAT and whether the audience is within its ceiling |

## The executor does not claim tasks

| Symptom | Cause | Fix |
|---|---|---|
| The log shows `iam_*` or `has no credentials` errors | No PAT, wrong file permissions, several credentials without `IAM_PRINCIPAL` | See [Authentication and access](auth.md) |
| A task is in the queue, but the executor does not see it | `CONTROL_PLANE_AGENT_ONLY_ASSIGNED=1`, and the task is not assigned to its principal | Assign the task to the executor's CP principal (`assigneeId`) |
| It does not see tasks of the required workspace | `CONTROL_PLANE_AGENT_WORKSPACE` points to another workspace | Fix the variable. Do not confuse it with `CONTROL_PLANE_AGENT_WORKTREE_ROOT`, which is the working copy directory |
| The log shows `no task_types.read: leaving … alone` | The executor's binding lacks the `task_types.read` permission. Without it, the daemon cannot tell whether a task is a code task or a skill, and it fails closed by skipping typed work | Add `task_types.read` to the binding permissions (bootstrap includes it in the default agent permissions) |
| The task is claimed, but nothing happens | A long turn of the coding agent is in progress; a turn is limited by `CONTROL_PLANE_CLAUDE_TIMEOUT` (3600 s by default) | Check whether the agent process is alive; the run trace shows tool calls live |

!!! danger "The executor claims other people's tasks"
    Without `CONTROL_PLANE_AGENT_ONLY_ASSIGNED=1` and `CONTROL_PLANE_AGENT_WORKSPACE`,
    the daemon claims the **first available task by priority** among all tasks
    it can see, including epics and tasks of other repositories. For testing,
    create a separate sandbox workspace.

## Coding agent

| Symptom | Cause | Fix |
|---|---|---|
| The agent's report says every tool call requires approval, and it works blind | The default permission mode (`acceptEdits`) does not allow commands without a human | `CONTROL_PLANE_CLAUDE_PERMISSION_MODE=bypassPermissions`, **only** inside an isolated perimeter (a container without platform secrets, or an unprivileged user with `ProtectSystem=strict`) |
| Claude Code is not authenticated on the runner host | The server has no browser for sign-in | Issue a token with `claude setup-token` on a machine with a browser and pass it in `CLAUDE_CODE_OAUTH_TOKEN` (a secret file or an env file with mode `0600`) |
| The agent consistently fails tasks after the subscription was revoked | The subscription token is revoked, but the daemon keeps claiming tasks | Stop the executor until the token is replaced |
| The agent writes code against an invented API of a neighbouring service, and tests pass on its own mocks | The agent cannot see the neighbour's code and reconstructs the contract by guessing | Add the neighbouring repository to `CONTROL_PLANE_AGENT_NEIGHBOURS` (read the code instead of guessing); in the task statement, name the source of the schemas explicitly and require contract tests |
| Tests that need Docker do not run in the container executor | The Docker socket is intentionally not passed into the container | Run integration tests in CI; for unit tests with a database, the executor has test databases (`db-test`, `memory-db-test`) |

## Working copies

| Symptom | Cause | Fix |
|---|---|---|
| Building the working copy fails: `../platform-auth-sdk` not found | Neighbours are not configured: the path dependency expects the SDK in a sibling directory | Set `CONTROL_PLANE_AGENT_NEIGHBOURS=platform-auth-sdk=<runner-root>/platform-auth-sdk.git` and `CONTROL_PLANE_AGENT_SUPERPROJECT` |
| `git worktree add` fails with `invalid reference` | The superproject pins a neighbour revision that is not yet in the neighbour's mirror | The daemon itself runs `fetch` on the neighbour's mirror before creating the copy (best-effort). If the forge was unavailable, run `git -C <mirror> fetch origin '+refs/heads/*:refs/heads/*'` as the executor user |
| The agent fixes code that no longer exists in `main` | The bare mirror of the task repository has not been updated for a long time | Update the mirror (the container entrypoint does this on startup; in the systemd variant, do it manually or with a timer) |
| The working copy directory keeps growing | Copies are kept for retries | `CONTROL_PLANE_AGENT_MAX_WORKSPACES` (8 by default) |

## Branch publishing

The `task/<publicId>` branch is published by the daemon, not by the agent: the
daemon holds the claim and the fencing token. A push is never forced and never
touches the base branch; a publishing failure does not fail the run.

| Symptom | Cause | Fix |
|---|---|---|
| The run succeeded, but the `commit` artifact has `published: false` | The push failed; the cause is only in the executor log | Check the executor log around run completion |
| The log shows `could not read Username for 'https://…'` | `HOME` is not set for the process, so git did not find `~/.gitconfig` with the credential helper. systemd does not set `HOME` even for services running as root. It looks like a permissions problem in the forge, but the request never reached the forge | `Environment=HOME=/home/<user>` in the unit (drop-in); in a container, the image sets `HOME` |
| The forge rejects the push (`403`, `denied`) | The forge token has no write access to the task repository, or it is revoked | Issue a token with `Contents: write` on the task repository |
| The push is rejected as non-fast-forward | The branch in the forge has diverged from the local one (a human edited it) | Resolve it manually: the daemon intentionally does not rewrite history |
| The log shows `no changes in …; nothing to commit`, and there is no branch | The agent did not change any files in the working copy | Check the task statement and the run trace. If the agent committed on its own, the daemon still publishes the branch |
| A code task goes straight to `done`, and no review is requested | There is no published commit: the `review` and `merge` criteria are skipped (`skipped`) | Fix branch publishing; check the `commit` artifact (`published`) |
| The run is `failed: executor_blocked`, and the task is `blocked` | The executor reported that it cannot do the work (a `blocked` checkpoint) | The reason is in the task comment; resolve it and return the task to work |

## Installation and upgrade (systemd variant)

| Symptom | Cause | Fix |
|---|---|---|
| After `uv tool install --reinstall`, the executor runs old code | The installation ran as root and went into `/root/.local/share/uv/tools`, bypassing the directory the service runs from | Install as the executor user with its `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR`, see [Upgrades and migrations](../operations/upgrades.md) |
| `uv tool install` as the executor user fails with `Permission denied` | Root-owned files appeared in the source or tool directories (after `git pull` or running python as root) | `chown -R <user>:<group> <runner-root>/src <runner-root>/tools`; from then on, do everything as the executor user |
| The unit cannot find `uv` or other utilities | The unit's `PATH` does not include the user's `~/.local/bin` | Add the directory to `Environment=PATH=…` via a drop-in |
| When started manually, the daemon does not see variables whose values have several words | When a shell `source`s the env file, an unquoted value is truncated | Quote values that contain spaces |

## Memory and CPU

| Symptom | Cause | Fix |
|---|---|---|
| Runs are closed with `restart_recovery`, and `dmesg` / `journalctl -k` shows `Out of memory: Killed process` | The agent process hit `MemoryMax` (systemd) or `mem_limit` (container) | If it repeats on the same task, the task is too heavy for the machine: run it on a larger machine |
| OOM happens when two executors run at the same time | The sum of the executors' memory limits exceeds physical memory | Bring the sum of `MemoryMax`/`mem_limit` within RAM minus the OS; see [Resources and scaling](../operations/capacity.md) |
| Other services on the machine slow down during runs | No CPU/IO limits | `CPUQuota`, `IOWeight` in the unit; `cpus` in compose |

## Emergency actions

```bash
# Stop the executor (safe at any time)
docker compose -f <executor compose file> stop runner
systemctl stop <unit>

# Revoke access: revoke the executor's binding and PAT
#   POST /api/v1/iam-bindings/<binding-id>:revoke
#   POST /api/v1/tenants/<t>/platform-access-tokens/<id>:revoke
```

After the PAT is revoked, the executor gets no new access tokens; one already
issued lives for up to 300 s. Revoking the binding closes access to Control
Plane immediately. The local principal and the work history are preserved. For
loss of the runner host, see [Emergency procedures](../operations/emergency.md).

## See also

- [Installing executors](../runner/installation.md)
- [Runner configuration](../runner/configuration.md)
- [Working copies](../runner/execution-workspace.md)
- [Execution: claims and runs](../control-plane/execution.md)
