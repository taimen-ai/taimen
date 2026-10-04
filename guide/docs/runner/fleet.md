
# Nodes and fleet

The `fleet` service decides **where** agents described by the `Agent` kind run: it knows the
machines (nodes), distributes agent instances across them, creates identities for agents and
delivers their PATs, and reports the actual state to Control Plane. The article is for the
operations engineer who connects machines to the platform and for the administrator who is
figuring out why an agent did not start. What to write in an agent description is covered in
[Declarative agents](declarative-agents.md). Rationale: TAI-ADR-0052.

## Architecture

The service consists of two processes:

- **fleet-controller** runs next to Control Plane (compose profile `fleet`). It stores nodes
  and placements in SQLite, reads active agents from Control Plane, places instances on
  nodes, creates a principal and a PAT in IAM for each agent, and writes the actual state of
  agents to Control Plane.
- **fleet-node** is the node agent on every machine that executes agents: a server, a
  separate VM, a developer machine. It registers with a one-time key, pulls its desired
  state, reports its health, and starts agent containers through a Docker socket proxy.

```mermaid
flowchart LR
    subgraph Center["Center (platform compose)"]
        CADDY["caddy<br/>/fleet/*"]
        FC["fleet-controller:8040<br/>SQLite /data"]
        CP["control-plane-api"]
        IAM["iam-service"]
        CADDY --> FC
        FC -- "agents.read, agents.status.write" --> CP
        FC -- "iam:agents" --> IAM
    end
    subgraph Node["Node (any machine with Docker)"]
        FN["fleet-node"]
        PX["docker-socket-proxy<br/>containers only"]
        A1["fleet-&lt;agent&gt;-0<br/>executor daemon"]
        A2["fleet-&lt;agent&gt;-1"]
        FN --> PX --> A1 & A2
    end
    FN -- "HTTPS, outbound only:<br/>join, long-poll desired, observed" --> CADDY
    A1 -- "GET /agents/me, work" --> CP
```

Properties you can rely on:

- **Outbound connections only.** The node calls the controller itself; the controller never
  calls the node and holds no keys to machines. A node behind NAT works.
- **No commands from the center.** The node receives only the desired state and brings its
  containers to it on its own.
- **The node keeps working without the center.** The last received desired state is stored
  on the node's disk; while the controller is unavailable, agents keep working and only
  changes wait.
- **Secret values never leave the machine.** The node reports only the names of its secrets.
- **The node decides what to run.** An agent description names an executor kind
  (`claude-code`, `codex`, `skills`, `observer`), and the node configuration sets the default
  image for the kind. A description may name its own image (`executor.image`), but the node
  runs it only if the node's own `executors.<kind>.images` list allows the image (see
  [Images an agent can name](#images)). The node runs no other image, no matter who names
  it.

## Reconciliation loop

The controller runs a single reconciliation procedure every 5 seconds, after a node
registers, and after each node report:

1. reads active agents from Control Plane (`GET /api/v1/agents?status=active`). If the core
   is unavailable, it works with the last known list;
2. marks as `offline` the nodes that have not reported for more than **60 seconds**;
3. places agent instances (see below);
4. for each placement, ensures the agent's identity and a PAT sealed with the node's key;
5. rebuilds the desired state of each node. The generation number (`generation`) grows only
   on change, and this wakes the node's long-poll;
6. revokes PATs that are no longer needed;
7. reports the actual state of agents to the core (`PUT /api/v1/agents/{key}/status`), but
   only if the report changed.

Everything is level-based, not event-based: a missed event breaks nothing, the next
reconciliation brings the system to the description.

## Placement and labels

A node fits an agent instance if all of the following hold:

| Condition | Source on the node | Source on the agent |
|---|---|---|
| the node is `online` | report no older than 60 s | — |
| the node runs the executor kind | `executors` keys in `node.yaml` | `executor.kind` |
| the node allows the agent's image, if the agent named one | `executors.<kind>.images` in `node.yaml` | `executor.image` |
| the node has all labels | `labels` in `node.yaml` | `placement.requires` |
| the node has all secrets | files in `secretsDir` | `placement.secrets` |
| there is room | `capacity.slots` and, if set on both sides, `capacity.cpus` and `capacity.memoryMb` | one slot per instance, `placement.resources` |

Label matching: the requirement `name` is satisfied by the label `name` and by any
`name=value`; the requirement `name=value` only by exactly that label.

Selection rules:

- **Placement is sticky.** An instance whose node still fits stays on it: agents do not jump
  between nodes.
- **A new instance** goes to the fitting node with the most free slots; on a tie, by node
  name.
- **A node went `offline`**: its instances move to another fitting node. If there is none,
  the instance stays with the old node (it will come back with it), and the agent gets the
  phase `node_unavailable`.
- **No fitting node at all**: the agent is in `waiting_for_node` with the first reason that
  excludes all nodes, in this order: `no_node` (no node is `online`), `no_executor_kind`,
  `image_not_allowed`, `no_label`, `no_secret`, `no_capacity`. A waiting agent does not take
  a slot.
- Only agents with `state: running`, `identity.kind: agent`, and without `placement: none`
  are placed; the number of instances is `placement.replicas`.

To see what is placed where:

```bash
curl -sS https://platform.example.com/fleet/api/v1/placements \
  -H "Authorization: Bearer $FLEET_TOKEN"
```

```json
{
  "items": [
    {"agentKey": "coder", "revision": 4, "nodeId": "<node-id>", "replicas": 1,
     "status": "placed", "reason": null},
    {"agentKey": "publisher", "revision": 2, "nodeId": null, "replicas": 1,
     "status": "pending", "reason": "no_secret"}
  ]
}
```

## Node registration

```mermaid
sequenceDiagram
    autonumber
    participant Adm as Administrator
    participant FC as fleet-controller
    participant FN as fleet-node
    Adm->>FC: join-key (CLI in the container or POST /api/v1/join-keys)
    FC-->>Adm: one-time key, expiry
    Adm->>FN: key → joinKeyFile
    FN->>FN: X25519 key pair (the private key stays on the node)
    FN->>FC: POST /api/v1/nodes:join {key, name, publicKey, labels, executorKinds, capacity, secrets}
    FC-->>FN: nodeId, nodeToken (once; the controller stores only the hash)
    loop
        FN->>FC: GET /api/v1/nodes/me/desired?since=&wait=60
        FN->>FC: PUT /api/v1/nodes/me/observed (every observeSeconds)
    end
```

### 1. Issue a join key

The simplest way is a command inside the controller container: it writes the key straight
into its database and does not need a token.

```bash
tools/compose --profile fleet exec fleet-controller \
  fleet-controller join-key --ttl 3600 --note "worker-1"
```

Or through the API with an IAM token of audience `fleet` and scope `fleet:admin`:

```bash
curl -sS -X POST https://platform.example.com/fleet/api/v1/join-keys \
  -H "Authorization: Bearer $FLEET_TOKEN" -H 'Content-Type: application/json' \
  -d '{"ttlSeconds": 3600, "note": "worker-1"}'
```

```json
{"joinKey": "<key>", "expiresAt": "2026-01-15T11:00:00Z"}
```

`ttlSeconds` ranges from 60 seconds to 7 days, 3600 by default. The key is single-use: the
controller stores its hash and marks it used on registration.

### 2. Put the key on the node and start it

The key is written to the `joinKeyFile` file from `node.yaml`, then
`fleet-node --config node.yaml` is started. The node registers once: the node token, its id,
and the key pair are saved in `stateDir`, and later starts do not need the join key.

| Registration response | Reason |
|---|---|
| `201` | the node is registered |
| `401 join_key_invalid` | the key is unknown, already used, or expired |
| `409 node_name_taken` | a node with this `name` is already registered |
| `503 not_configured` | the controller has no service account yet (see [Controller](#controller)) |

## Node configuration `node.yaml` { #node-yaml }

```yaml
controllerUrl: https://platform.example.com/fleet
name: worker-1
labels: [claude-subscription, repos]
capacity: {slots: 4, cpus: 8, memoryMb: 16384}
executors:                            # executor kind -> default image and allowed images
  claude-code:
    image: agent-runner:1.4.0
    dataPath: /runner
    env:
      CP_TEST_DATABASE_URL: postgresql+psycopg://test:test@db-test:5432/test
  skills:
    image: agent-runner:1.4.0
    dataPath: /runner
    env: {RUNNER_MODE: skills}
  observer:
    image: observer-base:1.0.0
    dataPath: /data
    images:                           # what else an agent description of this kind may name
      - registry.example.com/observers/mail:1.*
      - registry.example.com/observers/tickets:2.0.3
stateDir: /var/lib/fleet-node
secretsDir: /etc/fleet-node/secrets
dockerUrl: tcp://docker-proxy:2375
network: fleet-agents
agentEnv:                             # for every agent container; no secrets
  CONTROL_PLANE_SERVER: https://platform.example.com
  CONTROL_PLANE_IAM_URL: https://platform.example.com/iam
  CONTROL_PLANE_IAM_SCOPES: control-plane:read control-plane:write
joinKeyFile: /etc/fleet-node/join-key
observeSeconds: 20
```

| Field | Default | Meaning |
|---|---|---|
| `controllerUrl` | — (required) | controller address; outside the platform perimeter, `https://<host>/fleet` |
| `name` | — (required) | node name `^[a-z0-9][a-z0-9.-]*$`, up to 100 characters; unique within the fleet. Goes into the `node` field of the agent's actual state |
| `labels` | `[]` | labels: `name` or `name=value` (`^[a-z0-9][a-z0-9.-]*(=[a-zA-Z0-9._-]+)?$`) |
| `capacity.slots` | — (required) | how many agent instances the node holds, 0–100 |
| `capacity.cpus` | — | CPU for agents; taken into account if the agent sets `resources.cpus` |
| `capacity.memoryMb` | — | memory for agents, from 64; taken into account if the agent sets `resources.memoryMb` |
| `executors` | — (required) | executor kind → `{image, images, env, dataPath}`. The keys are the kinds the node declares to the controller |
| `executors.<kind>.image` | — (required) | the kind's default image, for agents without `executor.image`; must already be on the machine (see [Common problems](#troubleshooting)) |
| `executors.<kind>.images` | `[]` | up to 50 images that an agent description of this kind may name: exact references and patterns with a single `*` in the tag (see [below](#images)). Empty means only the default image |
| `executors.<kind>.env` | `{}` | extra environment for containers of this kind, no secrets |
| `executors.<kind>.dataPath` | — | path inside the container where the replica's named volume is mounted (working copies, mirrors); the kind's `env` and `dataPath` also apply to an image named by the agent |
| `stateDir` | — (required) | node state: token, keys, the last desired state, agent PATs (directory `0700`, files `0600`) |
| `hostStateDir` | = `stateDir` | the same directory as the Docker daemon sees it; needed when the node itself runs in a container |
| `secretsDir` | — (required) | secrets directory: one file per secret |
| `hostSecretsDir` | = `secretsDir` | the same directory as the Docker daemon sees it |
| `dockerUrl` | `unix:///var/run/docker.sock` | Docker Engine API; `unix://…` or `tcp://…` (socket proxy) |
| `network` | — | Docker network for agent containers |
| `agentEnv` | `{}` | environment of every agent container: Control Plane and IAM addresses, scopes |
| `joinKeyFile` | — | file with the one-time join key; not needed after registration |
| `observeSeconds` | `20` | period of the report and the local reconciliation, 5–300 |

- `${NAME}` in the file is substituted from the environment of the node process; an unset
  variable is a startup error that lists the names. Comment lines (`# …`) are neither
  checked nor substituted.
- An unknown field is a startup error: the configuration is validated strictly.
- The configuration is read at startup. After changing labels, capacity, or `executors`,
  restart `fleet-node`; the new values reach the controller with the next report.

!!! warning "Node in a container: host paths"
    The agent PAT and secrets are mounted into agent containers with a bind mount **by the
    host path**. If `fleet-node` itself runs in a container, set `hostStateDir` and
    `hostSecretsDir` as the Docker daemon sees these directories, or mount them into the
    node container at the same paths as on the host.

### Images an agent can name { #images }

An agent description may name the image of its executor, `executor.image`: a reference with
a tag or a digest (see [Declarative agents](declarative-agents.md#executor)). This is how an
integration package brings an image with its own code. Naming an image is not the right to
run it: the node runs it only if the `images` list for this kind in its `node.yaml` allows
the image. The node administrator decides what executes on the machine.

| List entry | Allows |
|---|---|
| `registry.example.com/observers/mail:1.4.2` | only this reference |
| `registry.example.com/observers/mail:1.*` | any tag of this repository that starts with `1.` |
| `registry.example.com/observers/mail:*` | any tag of this repository |
| `registry.example.com/observers/mail@sha256:<hex>` | only this digest |

- An entry has at most one `*`, and only in the tag. It replaces any sequence of tag
  characters and never allows another repository or registry. A reference with a digest is
  allowed only by an exact entry.
- References are compared as written, without Docker defaults: `alpine:3.20` and
  `docker.io/library/alpine:3.20` are different entries.
- The kind's default image (`image`) is not itself part of the list: if agents may name it
  too, list it in `images`.
- The node reports the lists to the controller (`executorImages`) together with its labels
  and secret names. The controller places an agent with `executor.image` only on a node
  whose list allows the image; otherwise the agent waits with the reason
  `image_not_allowed`.
- The node also checks what it receives. An image that is not allowed (for example, the
  list was shortened and the controller does not know yet) is not run: a running container
  with it is stopped with draining, and the instance is reported as `stopped` with a message
  starting with `image_not_allowed`. The refusal costs the machine nothing, however many
  times the desired state repeats it: no container, no restart counter, no back-off.
- The node does not pull images: every image it can run must already be on the machine (the
  node's compose builds or loads it).
- Without `executor.image`, the agent runs on the kind's default image.

!!! warning "Upgrade order"
    Upgrade the controller first, then the nodes with image lists: a controller without
    image list support does not know `executorImages` and rejects such a node's report. A
    node without lists sends nothing new, and the controller does not place an agent with
    `executor.image` on a node without list support.

### Node secrets { #node-secrets }

`secretsDir` is a directory where each secret is a separate file; the file name is the
secret name from `placement.secrets` in agent descriptions:

```text
/etc/fleet-node/secrets/          0700
├── claude-oauth-token            0600  subscription token of the coding agent
└── github-token                  0600  forge token for publishing branches
```

- The node reports to the controller only the **names** of files matching
  `^[a-z0-9][a-z0-9-]{0,62}$`; other files (`README`, `agent.pat`) are not offered.
- The list is re-read on every report: an added file becomes visible to the controller
  within `observeSeconds`, no node restart is needed.
- An agent container receives only the secrets named in its description: one file each,
  read-only, at `/run/secrets/<name>`.
- The files must be readable by the user the executor image runs as (uid `10001` for the
  reference image).

### What the agent container receives { #agent-container }

| Where | What |
|---|---|
| `/run/secrets/agent-pat` | the agent PAT, opened from its sealed form; read-only |
| `/run/secrets/<name>` | each secret from `placement.secrets`; read-only |
| `CONTROL_PLANE_AGENT_KEY` | the agent key |
| `IAM_PRINCIPAL`, `CONTROL_PLANE_IAM_TENANT` | whose identity this is in IAM |
| `FLEET_REPLICA` | the instance number |
| `agentEnv`, `executors.<kind>.env` | environment from `node.yaml` |
| `<dataPath>` | named volume `fleet-<agent>-<replica>-data`, read-write; survives restarts and new revisions |

The container is named `fleet-<agent>-<replica>`, labeled `fleet.managed=1` (the node does
not touch containers without this label), and started with `init` and without a Docker
restart policy: the node restarts it. The description's `resources.cpus` and
`resources.memoryMb` limits become the container limits.

The reference executor image (`deploy/agent-runner/`) recognizes from
`CONTROL_PLANE_AGENT_KEY` that it was started by a node: it takes the PAT from
`/run/secrets/agent-pat` into the process environment (`IAM_CREDENTIAL_MODE=environment`),
the subscription token and the forge token from `/run/secrets/claude-oauth-token` and
`/run/secrets/github-token` if they are mounted, and starts the daemon. The daemon takes all
other configuration from the agent revision (`GET /agents/me`) and sets up repository
mirrors on the replica's volume by itself.

## Agent identity and PAT delivery { #identity-and-pat }

```mermaid
sequenceDiagram
    autonumber
    participant FC as fleet-controller
    participant IAM as IAM
    participant CP as Control Plane
    participant FN as fleet-node
    FC->>IAM: POST /tenants/{t}/agents (principal of kind agent, owned by the controller)
    FC->>CP: PUT /agents/{key}/identity {issuer, iamTenantId, iamPrincipalId}
    CP-->>CP: CP principal + binding with the revision's permissions
    FC->>IAM: POST /tenants/{t}/agents/{id}/platform-access-tokens (Idempotency-Key)
    FC->>FC: seal(PAT, node public key) — the plain PAT is not stored
    FC-->>FN: desired: identity.credential {credentialId, ciphertext, expiresAt}
    FN->>FN: open with the private key → stateDir/agents/<key>/agent-pat (0600)
```

- **Principal.** For every active agent of kind `agent`, whether placed or with
  `placement: none`, the controller creates a principal in IAM with the `iam:agents`
  permission and reports it to the core. The core itself derives the CP principal and the
  binding with permissions from the revision; the controller has no right to grant
  permissions. The controller does not touch agents of kind `service`: their credential is
  issued by bootstrap.
- **A PAT per placement.** Each "agent — node" pair has its own PAT. It is encrypted with
  that node's X25519 public key (libsodium sealed box, X25519 + XSalsa20-Poly1305), and the
  controller stores only the ciphertext. Only the placement node can open it.
- **PAT ceiling.** The audience is always `control-plane` plus those audiences from the
  agent's `skills.audiences` and `identity.iam.audiences` that are listed in the
  controller's `FLEET_TOKEN_AUDIENCES`; the scope
  ceiling is those scopes from `FLEET_TOKEN_SCOPES` whose audience the PAT receives (IAM
  rejects a ceiling with a scope that no audience of the token allows:
  `422 invalid_scope_ceiling`). A scope belongs to an audience by prefix
  (`control-plane:read` → `control-plane`); a scope of another audience is written as
  `audience=scope`, for example `notification-service=notifications:send`. If the agent
  description declares `identity.iam.scopeCeiling`, the PAT gets only the intersection with
  it. An agent receives a privileged
  scope (`iam:…`, for example the CRM connector's `iam:identities.link`) only if it declared
  it in `identity.iam.scopeCeiling`; so `iam` and `iam=iam:identities.link` in the controller
  settings add nothing to other agents. On top of that, IAM will not give an agent more than
  the controller's own service account holds, and `iam:agents` is never delegated.
- **Rotation.** The controller requests a PAT with the lifetime `FLEET_TOKEN_TTL_SECONDS` (7
  days by default, which is also the IAM ceiling for an agent PAT,
  `IAM_AGENT_PAT_MAX_TTL_SECONDS`; more gives `422 expiry_too_long`) and issues a new one 2
  days before expiry (no more than a third of the lifetime). The node receives it with the
  next desired state; the agent container is recreated (the credential changed). The
  previous PAT is revoked after 10 minutes.
- **Revocation.** A PAT for a placement that no longer exists (the agent moved, was
  stopped, retired, or dropped out of the active list) is revoked at the next
  reconciliation. When an agent moves, the new node gets a new PAT.
- While the identity or the PAT is not ready (IAM or the core is unavailable), the agent
  stays in the `pending` phase with `reason.code: identity_pending`, and the controller
  retries at every reconciliation.

## Node: how it brings containers to the desired state

The node runs two loops over the same state:

- **pull**: long-poll `GET /api/v1/nodes/me/desired?since=<generation>&wait=60`. A new
  generation is saved to `stateDir/desired.json` and applied immediately. On network errors
  it retries after 2, 5, 10, 30, 60 seconds. A `401` response (the controller no longer
  accepts the node token) stops the node process;
- **report**: every `observeSeconds`, a local reconciliation of containers and `PUT
  /api/v1/nodes/me/observed`. If Docker is unavailable, the node reports `health: degraded`
  and keeps trying.

Container rules:

| Event | What the node does |
|---|---|
| the instance does not exist | creates and starts a container |
| the image (the kind's default or one named by the agent), environment, secrets, resources, network, or credential changed | stops the old container in the background with the agent's `drainSeconds` timeout, removes it, and creates a new one after draining; while the old container is draining, the replica name is taken and the instance is reported as `draining` |
| a new agent revision | nothing: the container is not touched, the executor exits with code 75 after its run on its own |
| the container exited with code `0` or `75` | starts it again immediately |
| the container exited with another code | restart with a pause of 5, 10, 20… up to 300 seconds; three failures in a row give the state `crashloop` |
| the instance is no longer needed (the agent is stopped, retired, moved, `replicas` reduced) | stops the container in the background and removes it. If the agent disappeared from the desired state entirely, the stop timeout is 30 seconds |
| the executor kind is not configured, the agent's image is not allowed by the list (`image_not_allowed`), a secret is missing, the PAT cannot be opened with the node's key | no container is created; the instance is reported as `stopped` with the reason |
| the container cannot be created (the image is not on the machine, the disk is full) | waits as on a failure: a pause of 5, 10, 20… up to 300 seconds, reported as `starting`, after three failures `crashloop` with the error. A changed specification (another image) is tried immediately |

Stopping always happens in the background: a long drain of one agent does not delay the
others. The node deletes the opened PATs of agents that are no longer in the desired state.

!!! note "`drainSeconds` and `SIGKILL`"
    `docker stop` gets exactly the agent's `drainSeconds`. On `SIGTERM`, the daemon gives
    the in-flight run the same `drainSeconds` and then cancels it (`cancelled`, reason
    `drained`, the task returns to the queue). Cancellation needs time to poll the run (up
    to 30 s), so when the time runs out `SIGKILL` may come earlier: the run stays `running`
    until the lease expires and is closed by recovery (`restart_recovery`).

### Observed state

The node report is `PUT /api/v1/nodes/me/observed`:

| Field | Meaning |
|---|---|
| `appliedGeneration` | the generation the node applied |
| `health` | `ok` or `degraded` (Docker unavailable) |
| `labels`, `executorKinds`, `executorImages`, `capacity`, `secrets` | current labels, kinds, allowed images per kind (non-empty lists only), capacity, and secret **names** |
| `replicas[]` | `agentKey`, `revision`, `replica`, `state`, `restarts`, `lastExitCode`, `message` |
| `version` | the version of the `fleet` package on the node |

Instance states: `starting`, `running`, `draining`, `crashloop`, `stopped`. From them the
controller derives the agent phase in Control Plane: at least one `crashloop` gives the phase
`crash_looping` with the instance message; at least as many ready (`running`) instances as
desired gives `running`; otherwise `pending`. `observedRevision` is the lowest revision among
the running instances.

## Node and controller failure

| What happened | What happens |
|---|---|
| the node disappeared (powered off, network) | after 60 s without a report it is `offline`; its instances move to fitting nodes with new PATs, the old PATs are revoked. Nowhere to move gives `node_unavailable`, and the instance waits for the node to return |
| the controller is unavailable | nodes keep working from `desired.json`; new revisions, stops, and moves wait for the controller |
| Control Plane is unavailable to the controller | the controller works with the last known list of agents |
| the controller restarted | nodes, placements, identities, and PAT ciphertexts are in SQLite on the `fleet_data` volume; the desired state of nodes is rebuilt on the first request |
| the node came back after its agents moved | its former instances are absent from the new desired state, and the node stops them |

!!! warning "A disconnected node keeps executing"
    A node with no connection to the controller does not know that its agents were moved.
    While it is unreachable but running (for example, it lost only its route to the
    controller), its containers keep taking work with their previous PAT until the
    controller revokes it at the next reconciliation after the move. If you need to stop a
    machine for sure, stop `fleet-node` and the `fleet-*` containers on it.

## Controller { #controller }

### Startup

```bash
tools/compose --profile fleet up -d fleet-controller
```

| Parameter | Value |
|---|---|
| Profile | `fleet` |
| Image | `${IMAGE_PREFIX:-taimen}/fleet-controller:${IMAGE_TAG:-local}`, Dockerfile `services/fleet/Dockerfile`, context `${FLEET_BUILD_CONTEXT:-.}` (root: `platform-auth-sdk` is attached as a sibling directory) |
| Port | 8040, not published to the host |
| Caddy path | `/fleet/*` (the prefix is stripped) |
| Volume | `fleet_data` → `/data` (SQLite `fleet.sqlite`) |
| Healthcheck | `GET /healthz` on `127.0.0.1:8040` |
| Memory limit | `${FLEET_MEM_LIMIT:-128m}` |
| Depends on | `control-plane-api`, `iam-service` (healthy) |
| User | uid `10001` |

### Controller credential

The controller is a platform service with a credential of kind `service`
(`identity.kind: service`, `placement: none`, see
[Service agents](declarative-agents.md#service-agents)); its description and permissions are
set by the installation's bootstrap:

- in Control Plane, the permissions `agents.read` and `agents.status.write`;
- in IAM, the audiences `control-plane`, `iam`, `notification-service` and the ceiling
  `control-plane:read`, `control-plane:write`, `iam:agents`, `notifications:send`.

`deploy/bootstrap.py` issues this service account at step **5d** and writes
`secrets/fleet-iam.env` (`FLEET_CLIENT_ID`, `FLEET_CLIENT_SECRET`). After that the controller
must be recreated: `tools/compose --profile fleet up -d fleet-controller`. Until the file
exists, all routes except `/healthz` respond `503 not_configured`.

Bootstrap also registers in IAM the audience `fleet` with the scopes `fleet:read` and
`fleet:admin`, for administrative calls to the controller API.

### Environment variables

| Variable | Value in `deploy/local/compose.yml` | Meaning |
|---|---|---|
| `FLEET_DATA_DIR` | `/data` | SQLite database directory |
| `FLEET_CONTROL_PLANE_URL` | `http://control-plane-api:8000` | Control Plane inside the network |
| `FLEET_IAM_URL` | `http://iam-service:8010` | IAM inside the network |
| `FLEET_IAM_ISSUER` | `${TAIMEN_PUBLIC_URL}/iam` | the public IAM issuer; agent identities are bound with it and administrative tokens are verified against it |
| `FLEET_IAM_TENANT` | `${IAM_TENANT_ID}` | IAM tenant |
| `FLEET_JWKS_URL` | `http://iam-service:8010/.well-known/jwks.json` | JWKS for verifying administrative tokens |
| `FLEET_CLIENT_ID`, `FLEET_CLIENT_SECRET` | from `secrets/fleet-iam.env` | the controller's service account |
| `FLEET_AUDIENCE` | not set, `fleet` by default | audience of administrative tokens |
| `FLEET_TOKEN_AUDIENCES` | see `deploy/local/compose.yml` | which audiences an agent PAT may receive (space-separated) |
| `FLEET_TOKEN_SCOPES` | see `deploy/local/compose.yml` | scope ceiling of agent PATs (space-separated); a scope whose prefix is not its audience is written as `audience=scope`; a privileged one (`iam:…`) goes only to an agent that declared it in `identity.iam.scopeCeiling` |
| `FLEET_TOKEN_TTL_SECONDS` | not set, 7 days by default | agent PAT lifetime, no more than `IAM_AGENT_PAT_MAX_TTL_SECONDS` |

`FLEET_MEM_LIMIT`, `FLEET_BUILD_CONTEXT`, and `VOLUME_FLEET_DATA` are set in `.env` (see
[Environment variables](../reference/environment.md)).

### Controller API

Public under `https://<host>/fleet`. Contract: `services/fleet/openapi/fleet.json`.

| Method and path | Who | What it does |
|---|---|---|
| `GET /healthz` | everyone | `{"status": "ok"}` |
| `POST /api/v1/join-keys` | token of audience `fleet`, `fleet:admin` | issue a one-time join key |
| `GET /api/v1/nodes` | `fleet:read` or `fleet:admin` | nodes: labels, kinds, allowed images (`executorImages`), capacity, secret names, `health`, `status` (`online`/`offline`), `lastSeenAt`, `version` |
| `GET /api/v1/placements` | `fleet:read` or `fleet:admin` | agent placements: `status` (`placed`, `pending`, `stopped`), `reason` |
| `POST /api/v1/nodes:join` | one-time key in the body | node registration |
| `GET /api/v1/nodes/me/desired` | node token | long-poll of the desired state (`since`, `wait` ≤ 60) |
| `PUT /api/v1/nodes/me/observed` | node token | node report, `204` |

Errors of the administrative routes: `401 invalid_token` (the token failed verification),
`403 insufficient_scope`. Node routes: `401 node_token_invalid`.

```bash
curl -sS https://platform.example.com/fleet/api/v1/nodes \
  -H "Authorization: Bearer $FLEET_TOKEN"
```

```json
{
  "items": [
    {
      "id": "<node-id>",
      "name": "worker-1",
      "labels": ["claude-subscription", "repos"],
      "executorKinds": ["claude-code", "skills"],
      "capacity": {"slots": 4, "cpus": 8.0, "memoryMb": 16384},
      "secrets": ["claude-oauth-token", "github-token"],
      "health": "ok",
      "status": "online",
      "lastSeenAt": "2026-01-15T10:00:20Z",
      "version": "0.1.0"
    }
  ]
}
```

The API has no node deletion and no reissue of a node token. A node that is no longer needed
can simply be switched off: after 60 seconds it is `offline`, and its agents move.

## Node deployment

A node needs Docker, outbound HTTPS to the controller, and a secrets directory. The
reference node layout is the `deploy/node/` directory (node compose and an example
`node.yaml`); the executor image is `deploy/agent-runner/`. The node compose brings up:

| Service | Purpose |
|---|---|
| executor image build | only builds the image from `deploy/agent-runner/`; agent containers are created by the node |
| `docker-proxy` | `tecnativa/docker-socket-proxy`: `CONTAINERS`, `VOLUMES`, `POST` are allowed; `EXEC`, `IMAGES`, `NETWORKS`, `BUILD` are closed |
| `fleet-node` | image `services/fleet/Dockerfile`, command `fleet-node --config /etc/fleet-node/node.yaml`, uid `10001`; the state and secrets directories are mounted at host paths |
| auxiliary services for agents | for example, disposable test databases on `tmpfs` in the node's `network`; their addresses are passed to agents through `executors.<kind>.env` |


First startup:

```bash
# on the node machine
install -d -m 0700 /var/lib/fleet-node /etc/fleet-node/secrets
install -m 0600 /dev/null /etc/fleet-node/secrets/claude-oauth-token   # and fill it in
echo '<join key>' > /etc/fleet-node/join-key
docker compose -f <node compose> up -d --build
docker compose -f <node compose> logs -f fleet-node
```

The node log shows `joined the fleet as <node-id>`, then `started fleet-<agent>-0` for the
placed agents. To check from the center: `GET /fleet/api/v1/nodes` and
`GET /api/v1/agents/{key}/status`.


## Common problems { #troubleshooting }

| Symptom | Cause and fix |
|---|---|
| all controller routes respond `503 not_configured` | there is no `secrets/fleet-iam.env`: run bootstrap (step 5d) and recreate `fleet-controller` |
| the node fails at startup: `node is not joined and no join key file is configured` | there is no token in `stateDir` and no `joinKeyFile` file: issue a key and put it in the file |
| `401 join_key_invalid` | the key expired or was already used: issue a new one |
| `409 node_name_taken` | the name is taken (including by an earlier registration of this machine with a lost `stateDir`): set a new `name` |
| the node exited: `the controller no longer accepts this node's credential` | the node token was not accepted (`401`): register the node again under a new name |
| `unset environment variables …` at node startup | `node.yaml` contains a `${NAME}` that is not in the node process environment |
| agent `waiting_for_node`, `no_executor_kind` | no `online` node declares the agent's `executor.kind`: add the kind to the node's `executors` |
| `no_label` / `no_secret` | a label from `placement.requires` is missing, or a file for a secret from `placement.secrets` is missing in `secretsDir`. The file name must match the secret name |
| `no_capacity` | slots are taken or `cpus`/`memoryMb` are insufficient: increase the node's `capacity` or reduce the agent's `resources` |
| agent `pending`, `identity_pending` | the controller could not create the principal or issue the PAT: see the `fleet-controller` log. Common causes: IAM is unavailable, the service account lacks `iam:agents`, IAM limits the agent PAT lifetime below what the controller requests (`422 expiry_too_long`) |
| instance `stopped`, `credential cannot be opened with this node's key` | `stateDir` with the node keys was recreated after registration: register the node again |
| instance `starting` or `crashloop`, `start failed: …` | Docker did not create the container; most often the image is not on the machine. The socket proxy does not let the node pull images, so build or load the image in advance |
| agent `waiting_for_node`, `image_not_allowed` | no `online` node with the agent's kind allows its `executor.image`: add the image or a pattern to the node's `executors.<kind>.images` and restart `fleet-node`, or remove the field from the description |
| instance `stopped`, `image_not_allowed: image … is not allowed for executor kind …` | the node's image list was shortened after placement: put the image back in the list or wait until the controller re-places the agent |
| the node report is rejected after adding `images` | a controller without image list support does not know `executorImages`: upgrade the controller |
| agent `crash_looping` | the executor fails at startup; the cause is in the report's `message` and in `docker logs fleet-<agent>-<replica>`. Exit code 2 means the agent description cannot be executed on this image |
| a new image under the same tag is not picked up | the node compares the `image` string, not the content: a rebuild under the same tag does not recreate the container, and a restart after exit 75 starts the previous container. Change the tag in `executors.<kind>.image` and restart `fleet-node` |
| the agent container does not see the PAT or a secret | the node runs in a container without `hostStateDir`/`hostSecretsDir`, or the files are not readable by the executor image's uid |
| a `node.yaml` change is not visible to the controller | the configuration is read at startup: restart `fleet-node` |

## See also

- [Declarative agents](declarative-agents.md): the `git-connector` executor kind, `executor.image`
- [Package agents](../packages/agents.md): the executor image in a package
- [Integrations](../packages/integrations.md#images): building observer and skill host images
- [Runner configuration](configuration.md)
- [Runner installation](installation.md)
- [Agent identity](agent-identity.md)
- [Services and ports](../reference/services-and-ports.md)
- [Bootstrap](../getting-started/bootstrap.md)
