
# Backup

What you need to back up in a Taimen installation, how to take dumps of
each database, what is special about the memory database,
and how to restore the installation as a whole or in parts. This article is
for the operations engineer.

## What to back up

Platform services are stateless: all state lives in Docker volumes and in a
few files on the host.

| Object | Where | Contents | Criticality |
|---|---|---|---|
| IAM database | volume `iam_db`, service `iam-db`, database `iam` | Tenants, principals, PAT hashes, service accounts, audiences, audit, outbox | Critical |
| Control Plane database | volume `control_plane_db`, service `control-plane-db`, database `control_plane` | Tasks, claims, runs, artifacts, approvals, the event log and its archive, consumer cursors, IAM bindings | Critical |
| Memory database | volume `memory_db`, service `memory-db`, database `company_brain` | Knowledge graph (PostgreSQL tables), chunks and vectors (pgvector), observations, context traces | Critical; contains customer data, possibly personal data |
| Keycloak database | volume `keycloak_db`, service `keycloak-db`, database `keycloak` | The live realm, users and their passwords | Critical with the `idp` profile: without it, people are onboarded again |
| MinIO objects | volume `platform_minio` | Control Plane artifact content (the `CP_S3_BUCKET` bucket) | Critical: MinIO is part of the `core` profile; back it up together with `control-plane-db` |
| Certificates | volume `caddy_data` | Certificates, keys, ACME account | Recommended: without it, certificates are issued again |
| Configuration | `.env`, `secrets/`, `deploy/state/<env>.json`, the installation's Caddyfile | Secrets, the IAM signing key, PATs, bootstrap identifiers | Critical; store separately and encrypt |

Docker volume names carry the project prefix:
`${COMPOSE_PROJECT_NAME}_iam_db` and so on (overridden by `VOLUME_*`
variables in `.env`). The exact list:

```bash
docker volume ls --filter "name=${COMPOSE_PROJECT_NAME:-taimen}_"
```

!!! danger "The IAM signing key and `.env` are part of the backup"
    Without `secrets/iam-signing.pem`, a restored IAM database issues tokens
    with a new key; that is survivable. Without `.env`, the passwords will
    not match the restored volumes, and without `deploy/state/<env>.json` a
    repeated bootstrap creates the tenant and principals from scratch. Store
    the configuration separately from the dumps, encrypted.

The runner host keeps no critical data: working copies are recreated from
bare mirrors, and published task branches are in the forge. Only the
unpublished work of current tasks is lost.

## Logical PostgreSQL dumps

All databases are dumped with `pg_dump` in custom format from inside the
containers. The databases are separate and are restored independently;
inside Control Plane, state, log, archive, and cursors live in one database
and are consistent within one dump.

| Service | User | Database |
|---|---|---|
| `iam-db` | `iam` | `iam` |
| `control-plane-db` | `control_plane` | `control_plane` |
| `memory-db` | `memory` | `company_brain` |
| `keycloak-db` | `keycloak` | `keycloak` |

### Daily backup script

```bash
#!/usr/bin/env bash
# /opt/taimen/backup.sh — dumps of all running databases + configuration + non-DBMS volumes
set -euo pipefail
cd /opt/taimen/src
STAMP=$(date -u +%Y%m%dT%H%MZ)
OUT=/opt/taimen/backups/$STAMP
mkdir -p "$OUT" && chmod 700 "$OUT"
DC=(tools/compose --profile "*")

dump() {  # dump <service> <user> <database>
  if "${DC[@]}" ps --status running --services | grep -qx "$1"; then
    "${DC[@]}" exec -T "$1" pg_dump -U "$2" -d "$3" -Fc > "$OUT/$1-$3.dump"
  fi
}
dump iam-db           iam            iam
dump control-plane-db control_plane  control_plane
dump memory-db        memory         company_brain
dump keycloak-db      keycloak       keycloak

# Configuration (secrets!) as a separate archive
tar czf "$OUT/config.tgz" .env secrets deploy/state /opt/taimen/Caddyfile

# Non-DBMS volumes: certificates and MinIO objects
vol() { docker run --rm -v "$1":/data:ro -v "$OUT":/backup alpine tar czf "/backup/$1.tgz" -C /data .; }
P=${COMPOSE_PROJECT_NAME:-taimen}
vol "${P}_caddy_data"
docker volume inspect "${P}_platform_minio" >/dev/null 2>&1 && vol "${P}_platform_minio"

chmod 600 "$OUT"/*
find /opt/taimen/backups -maxdepth 1 -type d -mtime +14 -exec rm -rf {} +
```

Run it on a schedule (systemd timer or cron) and before every deployment:

```cron
15 3 * * * root /opt/taimen/backup.sh >> /var/log/taimen-backup.log 2>&1
```

!!! warning "A backup on the same disk is not a backup"
    Copy the dump directory off the host and encrypt it: memory dumps
    contain customer data, the IAM dump contains credential hashes, and
    `config.tgz` contains secrets in plain text.

### Consistency across databases

Dumps of different databases are taken at different moments. The platform
tolerates this:

- **Control Plane ↔ memory.** Delivery to memory goes through the outbox and
  the `context-adapter` cursor, both in the Control Plane database. If memory
  is restored from an older dump than Control Plane, run `:rebuild`: the
  adapter replays the log, and memory deduplicates repeats by
  `event:<uuid>`. In the opposite case the adapter delivers some events
  again, which is also safe.
- **IAM ↔ Control Plane.** Bindings live in Control Plane, principals and
  PATs in IAM. A principal created after the IAM dump disappears on
  restore; its binding in Control Plane stops matching (access closes), so
  reissue the principal and the binding.
- **Control Plane ↔ MinIO.** Artifact records (size, media type, SHA-256)
  are in the Control Plane database, the bytes in MinIO. Copy the volume
  **after** the database dump: objects are immutable, and everything the
  dump references is already in the volume. If the volume turns out older
  than the database, downloading some artifacts returns
  `503 content_store_unavailable`. See
  [Object storage](object-storage.md#backup) for details.

## Memory specifics: the graph in PostgreSQL tables

`memory-db` is PostgreSQL 16 with the pgvector and `pg_trgm` extensions. The
memory graph is ordinary tables `graph_nodes` and `graph_edges` in the
`CB_GRAPH_NAME` schema (MEM-ADR-023), so there are no special steps: the
database is dumped with `pg_dump` and restored with `pg_restore`, including
into a different cluster (a new volume, a new host).

```bash
tools/compose stop memory-service
tools/compose exec -T memory-db pg_restore -U memory -d company_brain \
  --clean --if-exists --no-owner < backups/<stamp>/memory-db-company_brain.dump
tools/compose up -d memory-service
curl -fsS http://127.0.0.1:18001/healthz     # {"ok": true, "graph": ..., "nodes": N, "chunks": M}
```

!!! note "An installation whose graph is still in Apache AGE"
    Before memory-service v0.2.1, the graph was stored in Apache AGE. A dump
    of such an installation is restored the same way (the distribution's
    `memory-db` image is based on the Apache AGE image, so the extension is
    there), and then the graph is moved into the tables with
    `cb migrate-graph-from-age` while the service is stopped: first
    `--dry-run`, then the move. Once the service has started, do not run the
    move again. The command reads the AGE label tables directly, bypassing the
    catalog, so the move does not need the AGE catalog OID fix. For details,
    see [Memory configuration](../memory/configuration.md#age-migration).

After any memory restore, compare the `nodes` and `chunks` counters from
`/healthz` with the values before the incident.

## Restore

### The Control Plane database alone

```bash
tools/compose stop control-plane-worker context-adapter control-plane-api
tools/compose exec -T control-plane-db pg_restore -U control_plane -d control_plane \
  --clean --if-exists --no-owner < backups/<stamp>/control-plane-db-control_plane.dump
tools/compose up -d control-plane-api           # applies migrations if the dump is older
curl -fsS http://127.0.0.1:18000/health/ready    # 503 migrations_pending while the revision lags
tools/compose up -d control-plane-worker context-adapter
```

Partial restore of individual Control Plane tables is not supported: the
log, state, and cursors are bound by invariants (append-only, foreign keys,
cursor positions).

If after the restore memory is ahead of the log, you do not need to do
anything. If memory is behind or lost, rebuild the delivery:

```bash
curl -s -X POST http://127.0.0.1:18000/api/v1/operations/context-adapter/<tenant-id>:rebuild \
  -H "Authorization: Bearer <admin access token>" -H 'Content-Type: application/json' \
  -d '{"reason": "memory restored from backup"}'
```

### The IAM database

```bash
tools/compose stop iam-service
tools/compose exec -T iam-db pg_restore -U iam -d iam --clean --if-exists --no-owner \
  < backups/<stamp>/iam-db-iam.dump
tools/compose up -d iam-service
```

!!! danger "Revocations after the dump date are lost"
    A restored IAM database does not know about PAT and service account
    revocations made after the dump was taken: such credentials become valid
    again. Right after the restore, repeat the revocations from the incident
    log or an external operations log.

### Full restore to a new host

1. Prepare the host following [Production deployment](deployment.md), and
   clone the superproject **at the same commit** that was running before the
   failure.
2. Unpack `config.tgz`: `.env`, `secrets/`, `deploy/state/`, the Caddyfile.
   Restore the key owner: `chown 10001:10001 secrets/*.pem`.
3. Restore the `caddy_data` volume before the first start of `caddy`:

    ```bash
    docker volume create taimen_caddy_data
    docker run --rm -v taimen_caddy_data:/data -v "$PWD/backups/<stamp>":/backup alpine \
      tar xzf /backup/taimen_caddy_data.tgz -C /data
    ```

4. Start only the databases and wait for `healthy`:

    ```bash
    tools/compose up -d iam-db control-plane-db memory-db    # + databases of other running profiles
    ```

5. Restore each database with `pg_restore --clean --if-exists --no-owner`.
6. For memory: if the installation's graph is still in Apache AGE, move it
   with `cb migrate-graph-from-age` before starting memory-service (see
   above); then check `/healthz`.
7. Restore the MinIO volume (`platform_minio`) the same way as
   `caddy_data`: it holds the core's artifact content.
   If the core works with an external S3 (`deploy/local/compose.s3.example.yml`), restore
   the bucket with the provider's tools.
8. Start everything: `tools/compose --profile core --profile edge … up -d`.
9. Check `make smoke`, `/health/ready`, operator sign-in, and the
   `context_adapter_parked_tenants` metric.
10. Switch DNS to the new host.

## Verifying backups

A backup that has never been restored is a hypothesis. Once a month:

- bring up a copy of the installation on a separate machine or in a separate
  compose project (`COMPOSE_PROJECT_NAME=taimen-restore`, its own ports);
- restore all dumps and perform the full restore steps;
- compare the number of tasks, log events, principals, memory nodes, and
  chunks with the production values at the time of the dump.

## Control Plane log retention

The event log grows with the work. Retention is an operator command; there
is no scheduler: `:archive` moves acknowledged history to an archive table
in the same database, and `:prune` deletes it physically. The horizon is
bounded by the minimum consumer cursor, so nothing still needed by someone
is deleted. Details and commands are in [Monitoring and health](monitoring.md)
and [Control Plane events](../control-plane/events.md).

!!! warning
    `:prune` is the only operation after which data is lost. Make sure you
    have a fresh backup of the Control Plane database before it.

## See also

- [Upgrades and migrations](upgrades.md)
- [Object storage (MinIO)](object-storage.md)
- [Emergency procedures](emergency.md)
- [Memory knowledge model](../memory/knowledge-model.md)
- [Task context and memory](../control-plane/context.md)
- [Memory and context: troubleshooting](../troubleshooting/memory.md)
