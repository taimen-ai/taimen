
# Requirements

This page lists what the machine that runs the Taimen platform needs:
resources, software, free ports, and network access. The figures apply to the
`deploy/local/compose.yml` profiles; for a production deployment, also see
[Capacity and scaling](../operations/capacity.md).

## Hardware resources

Container memory limits are set in `deploy/local/compose.yml` (`mem_limit`, overridden by
the `*_MEM_LIMIT` variables). The sum of the limits is an upper bound; actual
usage is lower.

| Profile set | Containers | Default `mem_limit` total | Recommended machine |
|---|---|---|---|
| `core edge` (default) | 9 | ≈ 2.8 GB (excluding Caddy, which has no limit) | 2 vCPU, 4 GB RAM |
| `+ notify` | +2 | +0.5 GB | as needed |

Practical reference points:

- an idle `core edge` stack uses about **0.7 GB RSS**;
- the **first image build** takes several minutes (Python dependencies, the
  `memory-db` image with Apache AGE and pgvector); a rebuild with a warm cache
  takes tens of seconds.

Disk: the core images take several gigabytes, plus PostgreSQL data in volumes.
Plan for **at least 20 GB** of free space for Docker for `core edge`.

!!! note "Docker Desktop"
    On macOS and Windows, resources are limited by Docker Desktop settings, not
    by the machine. Give the VM at least 4 GB of memory for `core edge`;
    otherwise containers are OOM-killed without a clear error from `make up`.

## Software

| Tool | Version | Purpose |
|---|---|---|
| **Docker Engine** or Docker Desktop | current | containers for all services |
| **Docker Compose** | v2.24 or later | `deploy/local/compose.yml` uses `env_file` with `required: false` and `--profile "*"` |
| **git** | any recent | superproject and submodules |
| **make** | GNU make or BSD make | `Makefile` targets |
| **Python 3** | 3.10+ | `tools/fill_secrets.py`, `tools/smoke.py`, `deploy/bootstrap.py` |
| **PyYAML**, **jsonschema** | — | only if uv is not installed: `deploy/bootstrap.py` reads and validates catalog packages (`packages/`); with uv installed, `make bootstrap` adds them itself; without uv, it takes them from the system Python, and without them bootstrap stops at step 5b |
| **openssl** | any | `make secrets` generates the IAM RSA signing key |
| **uv** | current | installing the Control Plane CLI and MCP server, `make check`, building the guide; `make bootstrap` runs the script through it with PyYAML and jsonschema |
| **curl**, **jq** | — | checks and examples in this guide (optional) |

Check:

```bash
docker compose version          # Docker Compose version v2.24+ (or later)
openssl version
uv --version
# only if uv is missing: bootstrap dependencies in the system Python:
python3 -c 'import yaml, jsonschema; print("ok")'
```

`make bootstrap` picks the interpreter itself: with uv installed, it uses
`uv run --no-project --with pyyaml --with jsonschema python3`; otherwise, the
system `python3`.

### Operating system

- **Linux** (x86_64): the primary target platform, including for production
  deployments.
- **macOS** with Docker Desktop: supported for local work.
- **Windows**: through WSL 2 with Docker Desktop; run the commands in this
  guide in the WSL shell.

!!! warning "Secret file permissions on Linux"
    The IAM and Control Plane containers run as uid `10001`. Files mounted into
    them as secrets (`secrets/iam-signing.pem`) must be owned by that uid; keep
    the mode at `600`:

    ```bash
    sudo chown 10001:10001 secrets/*.pem
    ```

    Otherwise IAM cannot read the signing key and token exchange fails with
    `500`. This is not required on macOS with Docker Desktop.

## Ports

Only Caddy is published externally. The other services listen on the host's
`127.0.0.1`, which bootstrap, `make smoke`, and local debugging need.

| Host port | Service | Variable | Profile |
|---|---|---|---|
| `80`, `443` | `caddy` | `EDGE_HTTP_PORT`, `EDGE_HTTPS_PORT` | `edge` |
| `127.0.0.1:18000` | `control-plane-api` | `CP_HOST_PORT` | `core` |
| `127.0.0.1:18001` | `memory-service` | `MEMORY_HOST_PORT` | `core` |
| `127.0.0.1:18010` | `iam-service` | `IAM_HOST_PORT` | `core` |
| `127.0.0.1:18045` | `notification-service` | `NOTIFY_HOST_PORT` | `notify` |

`make check` also starts a test database on `5434` (Control Plane).

Check whether the ports are in use:

```bash
# Linux
ss -ltnp | grep -E ':(80|443|18000|18001|18010)\b'
# macOS
lsof -nP -iTCP -sTCP:LISTEN | grep -E ':(80|443|18000|18001|18010) '
```

## Host name for a local deployment

By default, the platform's public address is `http://taimen.localhost`
(`TAIMEN_PUBLIC_URL`). The IAM issuer is derived from it
(`http://taimen.localhost/iam`).

- Chrome and Firefox resolve `*.localhost` to `127.0.0.1` on their own.
- For `curl`, Safari, and system resolvers, add a line to `/etc/hosts`:

    ```text
    127.0.0.1 taimen.localhost
    ```

Inside the compose network, containers reach the same address through Caddy:
the `caddy` service has the network alias `${TAIMEN_PUBLIC_HOST}`, so the
issuer is the same in the browser and in containers.

!!! tip "Without Caddy and without /etc/hosts"
    For API work, the ports on `127.0.0.1` are enough: bootstrap, `curl`, and
    the CLI can call `http://127.0.0.1:18010` (IAM) and
    `http://127.0.0.1:18000` (Control Plane) directly. The issuer in a token is
    determined by the IAM configuration, not by the address used to reach IAM,
    so Control Plane accepts tokens obtained directly.

## Network

| Destination | Needed for | Required |
|---|---|---|
| Docker Hub, `ghcr.io` | base images (`postgres`, `caddy`, `uv`, `minio`) | at build time and first launch |
| PyPI, npm registry | dependencies when building images | at build time |
| OpenAI-compatible LLM endpoint (`LLM_BASE_URL`) | memory embeddings and reranking, skills | no: memory works offline (`MEMORY_EMBEDDING_PROVIDER=fake`, `MEMORY_LLM_PROVIDER=echo`) |
| Let's Encrypt (ports 80/443 from outside) | TLS for a production deployment through Caddy | only for a production deployment |

## See also

- [Installation and first launch](quickstart.md)
- [Services and ports](../reference/services-and-ports.md)
- [Capacity and scaling](../operations/capacity.md)
- [Installation and startup (troubleshooting)](../troubleshooting/startup.md)
