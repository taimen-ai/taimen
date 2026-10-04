
# Production deployment

This article describes how to install Taimen on a dedicated server: the
directory layout, preparing `.env` and secrets, choosing profiles, the first
start, bootstrap, and moving autonomous executors to a separate runner host.
To get acquainted with the platform locally, the
[quick start](../getting-started/quickstart.md) is enough; this article covers
what sets a production installation apart.

## Target topology


| Node | What runs there | Where the code comes from |
|---|---|---|
| Platform host | One compose project on the `deploy/local/compose.yml`: core (`core`), edge (`edge`), and notifications (`notify`) if needed | Superproject clone with submodules; a release is a superproject commit |
| Runner host (optional) | The `control-plane-agent` daemon with a coding agent, bare repository mirrors, working copies | The `control-plane` package from the superproject: in a container or as a systemd service |
| Operator workstations | MCP plugin / `control-plane` CLI | The `control-plane` package from the superproject |

The platform host and the runner host are connected only through the
platform's public address: the runner exchanges its PAT for an access token
in IAM and calls the Control Plane API through Caddy. It needs no direct
network access to the databases.

!!! note "Why the runner is separate"
    The coding agent is allowed to run arbitrary commands
    (`bypassPermissions` mode); otherwise it cannot work. The perimeter
    around it is a separate machine or a container without access to the
    platform's secrets, not the permission mode. Do not keep the agent on
    the host with the databases and the IAM signing key.

## Host requirements

| What | Minimum | Comment |
|---|---|---|
| OS | Linux x86_64 with systemd | Tested on Ubuntu 24.04 LTS |
| Docker Engine | 24+ | With the Compose v2 plugin |
| Docker Compose | v2.24+ | `deploy/local/compose.yml` uses `env_file` with `required: false` |
| git | any recent version | Clone with submodules |
| python3 + PyYAML and jsonschema (or uv) | 3.10+ | `deploy/bootstrap.py` and `tools/smoke.py` run on the host. Installing the catalog from packages (bootstrap step 5b) needs PyYAML and jsonschema: `make bootstrap` adds them itself when uv is installed; when you call the script directly (on a host without `make`), use either `uv run --no-project --with pyyaml --with jsonschema python3 deploy/bootstrap.py …` or a system `python3` that has them (on Ubuntu, the `python3-yaml` and `python3-jsonschema` packages) |
| openssl, make | — | `make secrets` generates RSA 3072 signing keys |
| DNS | An A/AAAA record of the public name pointing to the host | Before Caddy's first start; see [Edge and TLS](edge-and-tls.md) |
| Ports | 80 and 443 from outside | Other service ports are bound to `127.0.0.1` |

Resources (CPU, RAM, disk) are covered in [Resources and scaling](capacity.md).

## Directory layout

The recommended layout on the platform host:

```text
/opt/taimen/
├── src/                         superproject clone with submodules (release = commit)
│   ├── services/, sdk/          component submodules (TAI-ADR-0064)
│   ├── deploy/local/compose.yml single description of all services (run from the root: tools/compose)
│   ├── .env                     installation environment, 0600
│   ├── secrets/                 signing keys, PATs, service account env files, 0600
│   │   ├── iam-signing.pem      IAM private signing key (owner uid 10001)
│   │   ├── harness-pat          operator PAT, issued by bootstrap
│   │   └── control-plane-iam.env  core service account for memory (bootstrap)
│   └── deploy/state/<env>.json  identifiers written by bootstrap (not a secret)
├── Caddyfile                    edge configuration of this installation
└── backups/                     database dumps (see "Backup")
```

`.env`, `secrets/`, and `deploy/state/` are listed in the superproject's
`.gitignore`: `git pull` does not touch them.


!!! warning "Keep the Caddyfile outside the clone"
    The `CADDYFILE` variable sets the path to the file mounted into the
    `caddy` container. It is more convenient to keep the installation file
    with your domain outside the git working tree (for example,
    `/opt/taimen/Caddyfile`), using `deploy/caddy/Caddyfile.local` as a
    template. That way superproject upgrades do not conflict with local
    edits.

## Compose profiles


| Profile | Services | When you need it |
|---|---|---|
| `core` | `iam-db`, `iam-service`, `control-plane-db`, `control-plane-api`, `control-plane-worker`, `context-adapter`, `memory-db`, `memory-service`, `minio`, `minio-bootstrap` | Always (MinIO stores artifact content; see [Object storage](object-storage.md)) |
| `edge` | `caddy` | Always: the only entry point from outside |
| `notify` | `notification-db`, `notification-service` | Notifying people about platform events |

`make up` without arguments starts only `core edge`; you enable the other
profiles explicitly.

## First deployment procedure

### 1. Clone the superproject

```bash
sudo mkdir -p /opt/taimen && sudo chown "$USER" /opt/taimen
git clone --recursive <superproject-url> /opt/taimen/src
cd /opt/taimen/src
git submodule status        # no submodule line starts with "-"
```

If you cloned without `--recursive`, run `make submodules`
(`git submodule update --init --recursive`). A build without submodules
fails: the build context of `control-plane`, `memory-service`, and others is
the superproject root, and `platform-auth-sdk` is included as a path
dependency in a sibling folder.

### 2. `.env` and signing keys

```bash
make secrets
```

The `make secrets` target:

1. copies `.env.example` to `.env` with mode `0600` (if `.env` does not exist yet);
2. fills empty secrets with random values (`tools/fill_secrets.py`
   touches only empty values, so a repeated run overwrites nothing);

3. generates the signing key `secrets/iam-signing.pem` (RSA 3072) and sets
   it to `0600`.

Then edit `.env` for your installation:


```dotenv
TAIMEN_PUBLIC_URL=https://platform.example.com
TAIMEN_PUBLIC_HOST=platform.example.com
COMPOSE_PROJECT_NAME=taimen
TAIMEN_NETWORK=taimen_default
CADDYFILE=/opt/taimen/Caddyfile
LOG_RENDERER=json
IAM_SIGNING_KEY_ID=prod-2026-01        # a meaningful kid; changes when the key is rotated
CP_LEGACY_API_KEYS_ENABLED=false
```

Memory provider parameters (`MEMORY_EMBEDDING_PROVIDER`,
`MEMORY_LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, the provider key) are
described in the [memory configuration](../memory/configuration.md); the full
list of variables is in the [reference](../reference/environment.md).

!!! danger "You choose `TAIMEN_PUBLIC_URL` once"
    The IAM issuer is built from it (`${TAIMEN_PUBLIC_URL}/iam`), and Control
    Plane looks up an identity binding by the pair `(issuer, iam_principal_id)`.
    Changing the public address after bootstrap is a separate procedure; see
    [Emergency procedures](emergency.md).

### 3. Secret permissions for containers


Platform services (`iam-service`, `control-plane`) run in a container as
**uid 10001**. Files from the compose `secrets:` section are bind-mounted
with host permissions, so on Linux:

```bash
sudo chown 10001:10001 secrets/iam-signing.pem
sudo chmod 600 secrets/*.pem
```

Do not relax the permissions to `644`: these are private keys. If you leave
root as the owner with mode `600`, IAM cannot read the key and returns `500`
on token issuance. Env files (`secrets/*.env`) are read by `docker compose`
itself on the host, so they do not need `chown`.

### 4. Caddyfile


Start from `deploy/caddy/Caddyfile.local`: replace the site address
`http://taimen.localhost` with your name without a scheme (then Caddy issues
the certificate itself), remove `auto_https off` and the routes of profiles
you do not run. Details are in [Edge and TLS](edge-and-tls.md). Before the
first start, make sure the name already resolves to the host:

```bash
dig +short platform.example.com
```

### 5. Configuration check and build


```bash
make config PROFILES="core edge"   # tools/compose ... config --quiet
make build  PROFILES="core edge"
```

The build runs on the host from source; you do not need a separate registry.
If you want to keep previous images for a fast rollback, set `IMAGE_TAG` in
`.env` (for example, the short hash of the superproject commit); see
[Upgrades and migrations](upgrades.md).

### 6. Start


```bash
make up PROFILES="core edge"     # tools/compose --profile ... up -d --build
tools/compose --profile "*" ps
```


The startup order is set by `depends_on` with `service_healthy` conditions:
databases → IAM and memory → `control-plane-api` (runs `alembic upgrade head`,
then becomes healthy once the database revision matches head) →
`control-plane-worker` and `context-adapter`. The first start with empty
volumes takes 1–3 minutes.

### 7. Bootstrap

```bash
python3 deploy/bootstrap.py --env .env --name prod --operator "Platform Operator"
```

`deploy/bootstrap.py` is idempotent and does the following in one pass:

| Step | What is created | Where the result is written |
|---|---|---|
| 1 | Wait for Control Plane `/health/ready` and IAM `/healthz` on `127.0.0.1` | — |
| 2 | IAM tenant, audiences with scope ceilings, the operator's human principal | `deploy/state/<env>.json` |
| 2a | The core service account (memory, secret storage) | `secrets/control-plane-iam.env` |
| 3 | Control Plane `POST /api/v1/bootstrap`: tenant, admin principal, and the first IAM binding | state |
| 4 | Authentication context and the operator PAT (read/write/admin) | `secrets/harness-pat` |
| 5 | Project template, project, and workspace | state |
| 5b | Catalog from packages (`--packages`, `deploy/packages.yaml` by default) | state |
| — | Revocation of the legacy api-key issued by the Control Plane bootstrap | state |

After the first run, do what the script prints marked with `!!`:


```bash
# 1. Services that call IAM on their own behalf need the IAM tenant
sed -i "s/^IAM_TENANT_ID=.*/IAM_TENANT_ID=<tenant-id>/" .env

# 2. The core must pick up the service account env file (CP_CONTEXT_AUTH=auto)
tools/compose up -d control-plane-api control-plane-worker context-adapter
```

Check that the core switched from `MEMORY_API_KEY` to the service account:

```bash
tools/compose exec context-adapter env | grep -c CP_IAM_CLIENT_ID   # 1
tools/compose logs --since 5m context-adapter | grep -E ' 40[13] ' || echo "no 401/403"
```

### 8. Verification

```bash
make smoke
curl -fsS https://platform.example.com/health/ready
curl -fsS https://platform.example.com/iam/.well-known/jwks.json | head -c 200
```

`make smoke` (the `tools/smoke.py` script) polls the health of every running
service through ports on `127.0.0.1`; profiles that are not running are
marked "not running" and are not counted as errors.

### 9. Operator credential

The operator PAT is in `secrets/harness-pat`. On the operator's workstation
it goes into `~/.config/iam/credentials.json` (mode strictly `0600`,
otherwise the client refuses to read the file) under the key
`<issuer>|<tenant-id>|<principal-id>`; bootstrap prints the exact key as its
last line. See the [MCP plugin](../operator/mcp-plugin.md) and
[Credentials and PATs](../iam/credentials.md) for details.

!!! tip "Moving the file off the server"
    Copy the PAT over a secure channel (`scp`) and delete intermediate
    copies. Do not paste the token into chats, tickets, or a command line
    that keeps history.


## Runner host


An autonomous executor is installed separately from the platform host, in a
container or as a systemd service.

=== "Container"

    The image contains the `control-plane-agent` daemon, the coding agent,
    and, if needed, test databases in tmpfs. Secrets are files in a
    directory with mode `0700`, each `0600`: the agent PAT, the coding
    agent's subscription token, the forge token. The Docker socket is not
    passed into the container.

=== "systemd"

    The daemon is installed as a uv tool under the unprivileged user
    `runner`; the unit limits resources (`CPUQuota`, `MemoryHigh`,
    `MemoryMax`, `IOWeight`) and the file system (`ProtectSystem=strict`,
    `ProtectHome=read-only`, `NoNewPrivileges`). Configuration is an env file
    with mode `0600`; the PAT is in the `runner` user's
    `~/.config/iam/credentials.json`.

Rules common to both options:

- **One executor, one principal.** Each has its own IAM principal of kind
  `agent`, its own PAT, and a binding without `admin` and `approvals.decide`
  (bootstrap refuses to grant these permissions to an agent).
- **`CONTROL_PLANE_AGENT_ONLY_ASSIGNED=1`** and an explicit
  `CONTROL_PLANE_AGENT_WORKSPACE`: without them the agent claims the first
  available task by priority from the shared queue.
- **`IAM_PRINCIPAL` is required** if the machine holds credentials of several
  executors of the same tenant.
- **The sum of memory limits** of all executors must not exceed the host's
  physical memory; see [Resources and scaling](capacity.md).


Executor variables are described in
[Runner configuration](../runner/configuration.md).

## Production readiness checklist

- [ ] `.env` and all files in `secrets/` are `0600`; `.env` is not in git.
- [ ] The IAM signing key is owned by uid 10001, mode `600`.
- [ ] `CP_LEGACY_API_KEYS_ENABLED=false`, the legacy api-key is revoked by bootstrap.
- [ ] Caddy issued a certificate, `http://` redirects to `https://`.
- [ ] `/metrics` is closed to external access (see [Edge and TLS](edge-and-tls.md)).
- [ ] Ports `127.0.0.1:18000`, `18001`, `18010`, and others are not visible
      from outside (`ss -ltnp` on the host shows them on `127.0.0.1`).
- [ ] Backups are configured for all database volumes and the `secrets/` directory.
- [ ] The expiry dates of all PATs are recorded (`deploy/state/<env>.json`
      stores `operatorPatExpiresAt`).
- [ ] The runner host is separate from the platform host.

## See also

- [Installation and first start](../getting-started/quickstart.md)
- [Bootstrap](../getting-started/bootstrap.md)
- [Edge and TLS](edge-and-tls.md)
- [Secrets and rotation](secrets.md)
- [Services and ports](../reference/services-and-ports.md)
- [Installation and startup: troubleshooting](../troubleshooting/startup.md)
