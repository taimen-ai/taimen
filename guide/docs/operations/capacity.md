
# Resources and scaling

How much CPU, memory, and disk a Taimen installation needs, which limits are
set in `deploy/local/compose.yml`, how to change them, and where the platform's scaling
limits are. This article is for the engineer who picks the machine and plans
for growth.

## Container memory limits

Every service in the `deploy/local/compose.yml` has a `mem_limit` set by an
environment variable with a default value. The value is a ceiling: when a
process exceeds it, the kernel kills the container process (OOM), and Docker
restarts it according to `restart: unless-stopped`.

### Core and edge (`core`, `edge`)

| Service | Variable | Default |
|---|---|---|
| `iam-db` | `PG_MEM_LIMIT` | 256m |
| `iam-service` | `IAM_MEM_LIMIT` | 256m |
| `control-plane-db` | `PG_MEM_LIMIT` | 256m |
| `control-plane-api` | `CP_MEM_LIMIT` | 512m |
| `control-plane-worker` | `CP_WORKER_MEM_LIMIT` | 256m |
| `context-adapter` | `CP_WORKER_MEM_LIMIT` | 256m |
| `memory-db` | `MEMORY_DB_MEM_LIMIT` | 512m |
| `memory-service` | `MEMORY_MEM_LIMIT` | 512m |
| `minio` | `MINIO_MEM_LIMIT` | 256m |
| `minio-bootstrap` | — | one-shot, exits after startup |
| `caddy` | — | no limit (usually tens of MB) |
| `guide` | — | 64m |
| **Total of ceilings** | | **≈ 3.1 GiB** |

### Sign-in for people and workplaces (`idp`, `harness`)

| Service | Variable | Default |
|---|---|---|
| `keycloak-db` | `PG_MEM_LIMIT` | 256m |
| `keycloak` | `KEYCLOAK_MEM_LIMIT` | 768m |
| `realm-render`, `harness-image` | — | one-shot, exit after startup |
| `harness-launcher` | — | 128m |
| `harness-docker-proxy` | — | 64m |
| **Total of ceilings** | | **≈ 1.2 GiB** |
| workplace container, per active person | `HARNESS_MEM_LIMIT_MB` | 1536 MiB |

A workplace container goes to sleep after `HARNESS_IDLE_MINUTES` (30) without
requests, so memory is estimated by the number of people working at the same
time.


!!! note "`PG_MEM_LIMIT` is shared"
    One variable sets the ceiling for all databases on the `postgres:16-alpine`
    image. `memory-db` (graph and vectors) has its own ceiling,
    `MEMORY_DB_MEM_LIMIT`, because it needs the most.

### How to change a limit

Set the variable in `.env` and recreate the service:

```bash
echo 'MEMORY_DB_MEM_LIMIT=1g' >> .env
tools/compose up -d memory-db
docker stats --no-stream        # actual usage against the limit
```

## Recommended host configurations

| Composition | vCPU | RAM | Swap | Disk | Comment |
|---|---|---|---|---|---|
| `core edge` (minimum) | 2 | 4 GiB | 2 GiB | 40 GB | Coordination, IAM, memory on small knowledge bases |
| `core idp harness edge` | 2 | 6 GiB | 2 GiB | 80 GB | The core with sign-in for people and one or two active workplaces |
| `core idp harness edge` + a vertical package | 4 | 8 GiB | 4 GiB | 100 GB | With package executors, several workplaces, and experimental profiles |

How to estimate:

- The sum of ceilings is an upper bound. At rest the services use noticeably
  less, but under load `memory-db`, `memory-service`, and `keycloak` approach
  their ceilings. Check actual usage with `docker stats`.

- Leave at least 1 GiB for the OS, Docker, the file cache, and **image builds**:
  `tools/compose build` on the host briefly needs more memory and CPU than
  the running stack. On a 2 vCPU machine, run the build ahead of time, before
  the switchover (see [Upgrades and migrations](upgrades.md)).
- Swap does not replace memory, but it saves you from OOM during builds and
  peaks.

!!! warning "Keycloak is the most memory-hungry"
    Keycloak runs on the JVM, takes up to a minute to start, and gets the
    highest ceiling in the stack (768m). On a 4 GiB machine, do not start the
    `idp` and `harness` profiles.

## Disk

| What grows | Where | Estimate and management |
|---|---|---|
| Control Plane event log | `control_plane_db` | Grows linearly with work; `:archive` shrinks the hot table but not the total volume size; only `:prune` frees space physically |
| Memory: vectors | `memory_db` | A 1536-dimension embedding in `float4` is 6 KiB per chunk; the vectors alone for 100k chunks are about 600 MB, plus the index, text, and graph |
| Memory: graph, observations, traces | `memory_db` | Grows with the volume of loaded knowledge and the number of context assemblies |
| Artifact content | `platform_minio` (MinIO volume) | Volume of files submitted as task artifacts |
| Images and build cache | Docker | Several GB per release; `docker image prune`, `docker builder prune` |
| Container logs | Docker | Grow without bound without rotation; see [Monitoring](monitoring.md) |
| Backups | `/opt/taimen/backups` | Dumps × retention period; move them off the host |

```bash
docker system df -v | head -40
tools/compose exec control-plane-db psql -U control_plane -d control_plane \
  -c "SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 10"
```

## Scaling limits

The platform is designed for vertical scaling of a single host. What you
need to know:

| Component | Limitation |
|---|---|
| `context-adapter` | Singleton: uniqueness is held by an advisory lock in the database. A second instance does not speed up delivery. Per-tenant isolation isolates **failures** (one parked tenant does not block the others); it does not provide parallelism |
| `control-plane-api` | One container; horizontal scaling is not described in `deploy/local/compose.yml` |
| Databases | Each is a separate PostgreSQL 16 container on the same host. Of the extensions, the memory database needs only pgvector (`pg_trgm` recommended); the service needs no graph extension and no superuser, so a managed PostgreSQL with pgvector will do as well. The extensions are created by a database setup step, and the service runs as the owner of its database |
| Migrations | Indexes are not built `CONCURRENTLY`; large tables need a maintenance window |
| Log retention | There is no scheduler: the operator runs `:archive` |

If the host stops keeping up, in order:

1. Raise `MEMORY_DB_MEM_LIMIT`, `MEMORY_MEM_LIMIT`, `CP_MEM_LIMIT`.
2. Archive the Control Plane log.
3. Move executors and experimental profiles to other machines.
4. Move to a machine with more vCPUs and memory (migrate via
   [Backup](backup.md)).

## Runner host

The coding agent (Node.js plus a model via the provider's API) uses a lot of
memory at peaks, especially when building and running tests inside the
working copy.

=== "Container"

    Limits are set in the executor's compose file: `cpus` and `mem_limit`.
    A reference point is `cpus: 2` and `mem_limit: 4g` per executor, with
    512m for test databases (`db-test`) and 768m (`memory-db-test`, data in
    tmpfs). Two executors with test databases come to about 10 GB of
    ceilings: the machine needs 8–12 GiB of RAM and 4 vCPUs.

=== "systemd"

    Limits are set in the unit or in a `limits.conf` drop-in: `CPUQuota`,
    `MemoryHigh` (a soft threshold above which the kernel starts reclaiming
    memory), `MemoryMax` (a hard ceiling for the whole cgroup, including the
    agent's child processes), `IOWeight`.

!!! danger "The sum of ceilings must not exceed RAM"
    If several executors run on one machine, the sum of their `MemoryMax`
    (or `mem_limit`) must fit into physical memory minus the OS and
    neighboring services. Otherwise two heavy runs at the same time push the
    machine into OOM: the kernel kills the process, systemd or Docker
    restarts it, and the run closes with `failure_reason=restart_recovery`.
    If a task repeatedly hits the ceiling, run it on a larger machine rather
    than raising the ceiling to a level at which the neighbors suffer.

Other executor consumption parameters:

| Variable | Default | Meaning |
|---|---|---|
| `CONTROL_PLANE_AGENT_MAX_WORKSPACES` | 8 | How many working copies to keep on disk |
| `CONTROL_PLANE_CLAUDE_TIMEOUT` | 3600 | Limit for one coding-agent turn, in seconds |
| `CONTROL_PLANE_AGENT_POLL` | 5 | Queue polling interval, in seconds |

## See also

- [Production deployment](deployment.md)
- [Monitoring and health](monitoring.md)
- [Installing executors](../runner/installation.md)
- [Requirements](../getting-started/requirements.md)
