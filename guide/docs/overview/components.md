
# Delivery contents

This page lists the components of the Taimen platform, shows how they map to
the profiles of the `deploy/local/compose.yml`, and records the status of each profile:
what is in the default set, what is experimental, and what is frozen. Use it
when you plan a deployment and choose which profiles to enable.

## Repository layout

The platform is assembled in a **superproject**, an umbrella repository to
which the components are attached as git submodules: services in `services/`,
libraries in `sdk/`:

```text
<superproject>/
├── services/
│   ├── control-plane/          # submodule
│   ├── iam-service/            # submodule
│   ├── memory-service/         # submodule
│   └── notification-service/   # submodule (notify profile)
├── sdk/
│   ├── platform-auth-sdk/      # submodule (library)
│   ├── skill-sdk/              # submodule (library)
│   ├── platform-llm/           # submodule (library)
│   └── package-sdk/            # submodule (package author tools)
├── deploy/
│   ├── local/compose.yml       # single description of the services, run from the root
│   └── bootstrap.py, caddy/    # initialization, Caddyfile
├── .env.example  Makefile
├── tools/                      # compose (wrapper), smoke, fill_secrets, docs_gen, …
└── docs/                       # architecture and ADRs
```

!!! warning "The `services/`, `sdk/` layout is mandatory"
    `control-plane`, `memory-service`, and other services include
    `platform-auth-sdk` as the **path dependency** `../../sdk/platform-auth-sdk`,
    so their images are built with the superproject root as the build context.
    Do not move submodules into other directories: the build will break. Compose
    is run from the root, with `make` targets or the `tools/compose` wrapper.

A change to a component is committed in that component's repository, and the
submodule pointer in the superproject is updated in a separate commit.
`make submodules` checks out the submodules at their pinned revisions, and
`make status` shows the pointers.

## Components

### Core services

| Component | What it does | Processes in compose | Storage |
|---|---|---|---|
| **control-plane** | Authoritative operational state: tasks, types, claims, runs, approvals, artifacts, goals, event log, harness protocol; the `control-plane` CLI, the `control-plane-mcp` MCP server, the `control-plane-agent` executor daemon | `control-plane-api`, `control-plane-worker`, `context-adapter` (one image) | PostgreSQL 16 (`control-plane-db`) |
| **iam-service** | Tenants, principals, audiences, PAT, service accounts, federation with external IdPs, SCIM, RS256 token issuance, JWKS | `iam-service` | PostgreSQL 16 (`iam-db`) |
| **memory-service** | Knowledge graph with temporal facts and provenance, documents, hybrid search (vector + lexical + graph), Context Compiler; HTTP API, MCP server, CLI | `memory-service` | PostgreSQL 16 with Apache AGE and pgvector (`memory-db`, its own image) |

### Libraries

| Component | Purpose |
|---|---|
| **platform-auth-sdk** | The shared Policy Enforcement Point: IAM token verification against JWKS, trusted auth context, revocation, entitlement and policy checks, a single denial contract, audit. Used by all resource services |
| **skill-sdk** | You write a skill once, in code; the SDK provides the contract, the invocation context, hosting over the `local`, `http`, and `mcp` protocols, and YAML export into a catalog package |
| **platform-llm** | A shared LLM client: any OpenAI-compatible `/chat/completions`, responses constrained by a JSON schema, retries, and model fallback |
| **package-sdk** | Tools for catalog package authors: the `package-sdk` CLI (`check`, `test`, `lock`, `plan`, `apply`), the format schemas, the `package_sdk.connector` observer runtime, and the `package-author` Claude Code plugin. See [Packages](../packages/index.md) |
| **control-plane-client** | The Control Plane client (distribution in `services/control-plane/client`): PAT-to-token exchange, retries, typed calls. See [Service clients](../sdk/clients.md) |

### Peripheral components

| Component | What it does | Status |
|---|---|---|
| **notification-service** | Rule-based notifications for people: reads the Control Plane event log and delivers messages to channels (Telegram) | optional, `notify` profile |


## Compose profiles

The `deploy/local/compose.yml` is one file with one network (`${TAIMEN_NETWORK}`) and the
same service DNS names locally and on a production deployment. You select the
set of services with profiles.

```mermaid
flowchart LR
    subgraph default["default: make up"]
        core[core]
        edge[edge]
    end
    subgraph opt["optional"]
        notify[notify]
    end
    core --> edge
    notify -.-> core
```

| Profile | Services | Status | When to enable |
|---|---|---|---|
| `core` | `iam-db`, `iam-service`, `control-plane-db`, `control-plane-api`, `control-plane-worker`, `context-adapter`, `memory-db`, `memory-service`, `minio`, `minio-bootstrap` | **stable core** | always (MinIO stores the core's artifact content) |
| `edge` | `caddy` | stable | always, unless the edge is provided some other way |
| `notify` | `notification-db`, `notification-service` | optional | notifications for people based on Control Plane events; bootstrap creates the service's account |

Commands:

```bash
make up                                     # core edge (default)
make up PROFILES="core notify edge"         # with notifications
tools/compose --profile core --profile edge up -d   # the same without make
```

`make down` stops all profiles (`--profile "*"`); data in volumes is kept.

!!! warning "Interpolation covers the whole file"
    Docker Compose substitutes variables in the **entire** `deploy/local/compose.yml`, not
    only in the services of enabled profiles. For this reason, only the values
    that `make secrets` generates are declared as required (`${VAR:?…}`).
    Identifiers for optional profiles (for example, `IAM_TENANT_ID`) are empty
    by default and are checked by the services of their own profiles, so
    `make up` for `core edge` works with a clean `.env`. See
    [Installation and first launch](../getting-started/quickstart.md).

## Images and builds

| Image | Build context | Dockerfile |
|---|---|---|
| `${IMAGE_PREFIX}/control-plane` | superproject root (`CP_BUILD_CONTEXT`) | `services/control-plane/Dockerfile` |
| `${IMAGE_PREFIX}/iam-service` | `./services/iam-service` (`IAM_BUILD_CONTEXT`) | `services/iam-service/Dockerfile` |
| `${IMAGE_PREFIX}/memory-service` | root (`MEMORY_BUILD_CONTEXT`) | `services/memory-service/Dockerfile` |
| `${IMAGE_PREFIX}/memory-db` | `services/memory-service/infra/memory-db` | PostgreSQL + AGE + pgvector |
| `${IMAGE_PREFIX}/notification-service` | root (`NOTIFY_BUILD_CONTEXT`) | `services/notification-service/Dockerfile` |

`IMAGE_PREFIX` defaults to `taimen`, and `IMAGE_TAG` to `local`. Python service
containers run as an unprivileged user (uid `10001` for Control Plane and IAM),
so on Linux the secret files mounted into a container must be owned by that
uid.

## Volumes

Volume names are set explicitly so that a production deployment can point to
existing ones: `VOLUME_CONTROL_PLANE_DB`, `VOLUME_IAM_DB`, `VOLUME_MEMORY_DB`,
`VOLUME_NOTIFY_DB`, and so on. The default name is
`${COMPOSE_PROJECT_NAME}_<volume>`, for example `taimen_control_plane_db`. The
list is in [Environment variables](../reference/environment.md); backups are
covered in [Backup](../operations/backup.md).

## What is not in compose

- **Runner** (`control-plane-agent`): the autonomous executor daemon is
  installed on a separate host as systemd units. See
  [Agents and runner](../runner/index.md).
- **Control Plane MCP server and CLI**: installed on the operator's machine
  (`uv tool install`). See [CLI and MCP server](../control-plane/cli-and-mcp.md).
- **LLM provider**: an external OpenAI-compatible endpoint; memory can run
  without it on offline stubs.

## See also

- [Architecture](architecture.md)
- [Installation and first launch](../getting-started/quickstart.md)
- [Services and ports](../reference/services-and-ports.md)
- [Make targets](../reference/make.md)
