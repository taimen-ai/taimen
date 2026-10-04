# syntax=docker/dockerfile:1.7
# The agent runner image: the control-plane-agent daemon with the Claude Code CLI, and the
# skill SDK for local skills. The daemon also has a Codex adapter, but the Codex CLI is not
# in this image: install it in a derived image (npm install -g @openai/codex). A fleet node (deploy/node/) creates agent
# containers from it; the daemon reads its configuration — kind, model, working copy,
# neighbours, review, skills — from the revision of its agent (GET /agents/me).
#
# The container is the perimeter around a coding agent that runs with bypassPermissions:
# inside there are only the replica's volume with working copies and mirrors, the secret
# files the node mounted by the agent's description, and the network. The host's home
# directory, ~/.ssh and a person's credentials never get here.
#
# The build context is the repository root (platform-auth-sdk is a path dependency at
# ../../sdk/platform-auth-sdk, as in services/control-plane/Dockerfile):
#
#   docker build -f deploy/agent-runner/Dockerfile -t taimen/agent-runner:local .
#   docker compose -f deploy/node/compose.yml build agent-runner-image     # the same
#
# Local skills of your own packages: extend this image —
#   FROM taimen/agent-runner:local
#   RUN uv pip install --python /opt/taimen/services/control-plane/.venv/bin/python <your package>
# and list the package in the agent's description (spec.skills).

ARG NODE_IMAGE=node:22-bookworm-slim
FROM ${NODE_IMAGE} AS node

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
ARG CLAUDE_CODE_VERSION=latest

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates openssh-client procps curl make \
 && rm -rf /var/lib/apt/lists/*

# Node and npm from the official image — Claude Code is installed through npm; corepack
# provides pnpm and yarn for repositories that pin them (`packageManager`).
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
ENV COREPACK_HOME=/opt/corepack COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
 && ln -s /usr/local/lib/node_modules/corepack/dist/corepack.js /usr/local/bin/corepack \
 && corepack enable --install-directory /usr/local/bin \
 && npm install -g --no-fund --no-audit "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
 && npm cache clean --force

# The control-plane package (the control-plane-agent daemon, the coding agent adapters, the
# MCP bridge) is installed from the same tree as the server: the runner's version is the
# platform's version.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /opt/taimen/services/control-plane
COPY sdk/platform-auth-sdk /opt/taimen/sdk/platform-auth-sdk
COPY services/control-plane/pyproject.toml services/control-plane/uv.lock services/control-plane/README.md ./
COPY services/control-plane/client ./client
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-install-project --no-dev
COPY services/control-plane/src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

# The skill SDK and platform-llm in the daemon's environment: the skill executor
# (RUNNER_MODE=skills) imports the entry points of local skills from it, and ctx.llm is
# platform-llm or the model subscription through the Claude Code CLI of this image
# (SKILL_LLM_PROVIDER=claude-code, set by the node). The neighbours keep their relative paths.
COPY sdk/platform-llm /opt/taimen/sdk/platform-llm
COPY sdk/skill-sdk /opt/taimen/sdk/skill-sdk
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /opt/taimen/services/control-plane/.venv/bin/python \
      /opt/taimen/sdk/platform-llm "/opt/taimen/sdk/skill-sdk[llm]"

RUN useradd --create-home --uid 10001 --shell /bin/bash runner \
 && mkdir -p /runner "$COREPACK_HOME" && chown runner:runner /runner \
 && chown -R runner:runner "$COREPACK_HOME"

# The git credential helper of the forge: a token from a file that the fleet node refreshes
# by an atomic replace (/run/fleet/forge-token), read on every request;
# runner-forge-credentials checks FORGE_TOKEN_FILE/FORGE_HOST and configures the helper.
COPY --chmod=0755 deploy/agent-runner/git-credential-forge-token /usr/local/bin/git-credential-forge-token
COPY --chmod=0755 deploy/agent-runner/runner-forge-credentials /usr/local/bin/runner-forge-credentials

COPY --chmod=0755 <<'EOF' /usr/local/bin/runner-entrypoint
#!/bin/sh
# Secrets are read from files at start-up and live only in the process environment.
set -eu
secret() { tr -d '\r\n' < "/run/secrets/$1"; }

export IAM_CREDENTIAL_MODE=environment
IAM_PLATFORM_ACCESS_TOKEN="$(secret agent-pat)"
export IAM_PLATFORM_ACCESS_TOKEN

# The model subscription token for Claude Code and ctx.llm — if the node mounted it.
if [ -f /run/secrets/claude-oauth-token ]; then
  CLAUDE_CODE_OAUTH_TOKEN="$(secret claude-oauth-token)"
  export CLAUDE_CODE_OAUTH_TOKEN
fi

# The forge token for git: the helper reads the files on every request and answers only for
# FORGE_HOST (github.com). Only the paths are in the git configuration; the token goes
# neither into the configuration, nor into a URL, nor into the environment. Invalid
# FORGE_TOKEN_FILE/FORGE_HOST stop the start (set -e).
runner-forge-credentials
git config --global init.defaultBranch main

# A skill executor (RUNNER_MODE=skills): no coding agent and no mirrors — only the daemon,
# which takes work with an execution basis and skill invocations.
if [ "${RUNNER_MODE:-agent}" = skills ]; then
  git config --global user.name "${RUNNER_GIT_NAME:-Taimen Skills}"
  git config --global user.email "${RUNNER_GIT_EMAIL:-skills@taimen.invalid}"
  exec control-plane-agent
fi

# An agent on a fleet node: the daemon takes its configuration from the revision of its
# agent and sets up the mirrors itself; secrets are the files the node mounted.
if [ -z "${CONTROL_PLANE_AGENT_KEY:-}" ]; then
  echo "runner: CONTROL_PLANE_AGENT_KEY is not set — this image is started by a fleet node" >&2
  exit 64
fi
export CONTROL_PLANE_AGENT_WORKTREE_ROOT="${CONTROL_PLANE_AGENT_WORKTREE_ROOT:-/runner/worktrees}"
export CONTROL_PLANE_CLAUDE_RUNTIME_DIR="${CONTROL_PLANE_CLAUDE_RUNTIME_DIR:-/runner/claude}"
git config --global user.name "${RUNNER_GIT_NAME:-Taimen Agent}"
git config --global user.email "${RUNNER_GIT_EMAIL:-agent@taimen.invalid}"
mkdir -p "$CONTROL_PLANE_AGENT_WORKTREE_ROOT" "$CONTROL_PLANE_CLAUDE_RUNTIME_DIR"
exec control-plane-agent
EOF

ENV PATH="/opt/taimen/services/control-plane/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    HOME=/home/runner
USER runner
WORKDIR /runner
ENTRYPOINT ["runner-entrypoint"]
