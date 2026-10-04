# deploy/agent-runner/ — the agent runner image

[Dockerfile](Dockerfile) builds `taimen/agent-runner:local`: the `control-plane-agent`
daemon with the Claude Code and Codex adapters, the skill SDK and platform-llm for local
skills, Node with corepack, git and make. A fleet node ([deploy/node/](../node/README.md))
creates agent containers from it; the daemon takes its configuration — kind, model, working
copy, neighbours, review, skills — from the revision of its agent (`GET /agents/me`).

```bash
docker build -f deploy/agent-runner/Dockerfile -t taimen/agent-runner:local .   # from the root
docker compose -f deploy/node/compose.yml build agent-runner-image               # the same
```

The build context is the repository root: the control-plane package takes
`sdk/platform-auth-sdk` by path, and the image keeps the same relative paths under
`/opt/taimen`.

## Why a container

A coding agent runs with `bypassPermissions`: without it the agent cannot run a single
command. The perimeter is the container: inside there are only the replica's volume with
working copies and mirrors and the secret files the node mounted by the agent's
description. The host's home directory, `~/.ssh` and a person's credentials never get here.
Treat every agent container as running untrusted code — see
[services/fleet/SECURITY.md](../../services/fleet/SECURITY.md).

## Entry point

- `CONTROL_PLANE_AGENT_KEY` is set (an agent on a fleet node) — the daemon sets up mirrors
  and working copies by the agent's revision; the Claude Code token comes from
  `/run/secrets/claude-oauth-token` if the node mounted it;
- `RUNNER_MODE=skills` — only the daemon, without a coding agent and mirrors: it takes work
  with an execution basis and invocations of the local skills its agent names.

In both modes git gets the credential helper
[`git-credential-forge-token`](git-credential-forge-token), configured by
[`runner-forge-credentials`](runner-forge-credentials). The helper reads the token files on
every request, so an installation token that the node refreshes by an atomic replace in
`/run/fleet/forge-token` is picked up without a restart. The files, in order:
`FORGE_TOKEN_FILE`, then the static `/run/secrets/github-token`; the first non-empty one
wins. It answers only for `FORGE_HOST` (`github.com`); the token is never cached and goes
neither into the git configuration, nor into a URL, nor into the environment.
`FORGE_TOKEN_FILE` and `FORGE_HOST` are checked at start-up (the path — `[A-Za-z0-9/._-]`,
the host — a DNS name), otherwise the container does not start.

## Local skills of your own packages

The skill executor imports the entry points of local skills from the daemon's environment.
Extend the image with your package and name its skills in the agent's description:

```dockerfile
FROM taimen/agent-runner:local
USER root
COPY my-skills /opt/my-skills
RUN uv pip install --python /opt/taimen/services/control-plane/.venv/bin/python /opt/my-skills
USER runner
```
