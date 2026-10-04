# deploy/node/ — a fleet node

A node is a machine on which the platform runs agents: a server, a laptop, a separate host.
Agents are described in catalog packages (kind `Agent`); `fleet-controller` of the
installation (the `fleet` profile) places each agent revision on a node whose labels,
secrets, executor kinds and capacity fit, and keeps the agent's identity and token in step
with its revision. The node only makes outgoing connections to the controller, so a machine
behind NAT works. How a node works, its fields and its contract are in the
[fleet documentation](../../services/fleet/docs/node.md); **read
[SECURITY.md](../../services/fleet/SECURITY.md) before you run a node on a machine you care
about**: whoever controls the node or its Docker proxy controls the host, and agents run code.

```text
deploy/node/
├── compose.yml     the node, the Docker socket proxy, the fleet-services listener, image builds
├── node.yaml       labels, capacity, executor kinds, test service templates
└── .env.example    the node's name and the installation's addresses
```

The agent runner image (the executor kinds `claude-code` and `skills`) is built from
[deploy/agent-runner/](../agent-runner/README.md).

## First start

On the installation (the `fleet` profile and `make bootstrap`, which creates the
controller's service account at step 5d):

```bash
make up PROFILES="core notify fleet edge"
tools/compose --profile fleet up -d fleet-controller      # after the first bootstrap
tools/compose --profile fleet exec fleet-controller fleet-controller join-key --ttl 3600
```

On the node's machine, from the root of this repository with the submodules checked out:

```bash
mkdir -p ~/.taimen-fleet/state ~/.taimen-fleet/secrets && chmod 700 ~/.taimen-fleet ~/.taimen-fleet/*
echo '<join key>' > ~/.taimen-fleet/state/join-key
cp deploy/node/.env.example deploy/node/.env               # name and addresses
docker compose -f deploy/node/compose.yml up -d --build
docker compose -f deploy/node/compose.yml logs -f fleet-node
```

The node joins once; after that the key is not needed. On Linux the node runs as uid
10001: `chown -R 10001:10001 ~/.taimen-fleet` (or set `FLEET_HOME` to a directory of that
user).

## Secrets of the node

`~/.taimen-fleet/secrets/` (0700), one file per secret (0600, one line); the file name is
the secret name an agent description lists (`spec.secrets`). Only the names leave the
machine: the node reports which secrets it holds, and an agent that needs a secret goes only
to a node that has it. Typical files:

| File | For | What |
|---|---|---|
| `claude-oauth-token` | coding agents, skill executors with `ctx.llm` | the Claude Code subscription token (`claude setup-token`) |
| `github-token` | coding agents | a forge token limited to the repositories of the agents' tasks |
| `forge-app-key` | the node itself | the private key of a GitHub App when the node mints `forge-token` (`issuedSecrets` in node.yaml); never reaches a container |

Agent PATs are not in this directory: the controller creates each agent's identity and
delivers its token to the node sealed with the node's key.

## Executor kinds and test services

[node.yaml](node.yaml) offers two executor kinds built from the agent runner image:
`claude-code` (coding agents; working copies and mirrors on the replica's volume `/runner`)
and `skills` (`RUNNER_MODE=skills` — the daemon runs the local skills of its agent).
`services: true` lets the runs of `claude-code` ask the `fleet-services` listener for test
databases from the templates of node.yaml; the node creates one instance per replica and
removes it when idle. Add templates and pull their images in compose.yml: the Docker proxy
keeps `IMAGES` closed, so the node never pulls images itself.

A node on the same machine as a local installation reaches it as
`http://host.docker.internal` (Docker Desktop; the local Caddyfile serves that name). On
Linux use the host's address in the local network.
