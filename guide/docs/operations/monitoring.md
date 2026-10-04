
# Monitoring and health

How to tell that a Taimen installation is working: service health
endpoints, Control Plane metrics, `make smoke`, logs, and the set of alerts
worth setting up. This article is for the on-call engineer and whoever sets
up observability.

## Quick check

```bash
cd /opt/taimen/src
make smoke                                   # health of all running services
tools/compose --profile "*" ps              # container statuses and healthchecks
curl -s http://127.0.0.1:18000/health/ready  # Control Plane: database + migration revision
curl -s http://127.0.0.1:18000/metrics | grep -E '^(context_adapter|active_)'
```

Sample `make smoke` output:


```text
  iam-service          OK  200 http://127.0.0.1:18010/healthz
  control-plane-api    OK  200 http://127.0.0.1:18000/health/ready
  memory-service       OK  200 http://127.0.0.1:18001/healthz
```

The `tools/smoke.py` script takes ports from `.env`, skips services that are
not running, and exits with code `1` if any running service responded with a
status `≥ 400`. It works well as the last step of a deployment and in cron
with an alert on the exit code.

## Health endpoints

| Service | Endpoint | Host port | What it checks |
|---|---|---|---|
| `iam-service` | `GET /healthz` | 18010 | The process is alive (`{"status":"ok"}`); the database is not checked |
| `control-plane-api` | `GET /health/live` | 18000 | The process is alive (`{"status":"alive"}`) |
| `control-plane-api` | `GET /health/ready` | 18000 | The database is reachable **and** the Alembic revision equals head; otherwise `503` with `reason` |
| `memory-service` | `GET /healthz` | 18001 | Database connection, the number of graph nodes and chunks; `503` if the database is unreachable |
| PostgreSQL databases | `pg_isready` | — | Compose healthcheck |

Control Plane `/health/ready` responses:

=== "Ready"

    ```json
    {"status": "ready", "revision": "<alembic revision>"}
    ```

=== "Database unreachable"

    ```json
    {"status": "unavailable", "reason": "database_unreachable"}
    ```

=== "Migrations behind"

    ```json
    {"status": "unavailable", "reason": "migrations_pending",
     "dbRevision": "<in the database>", "headRevision": "<in the image>"}
    ```

!!! note "Healthchecks inside containers"
    All healthchecks in `deploy/local/compose.yml` and the Dockerfiles call `127.0.0.1`,
    not `localhost`: in slim and busybox images `localhost` can resolve to
    IPv6 `::1` while the service listens only on IPv4, and the container
    stays `unhealthy` forever while the service is alive. If you write your
    own healthcheck, follow the same rule.

## Control Plane metrics

`GET /metrics` returns metrics in the Prometheus text format. The endpoint
is **not authenticated**: scrape it from `127.0.0.1:18000` or from inside the
compose network (`control-plane-api:8000`) and do not expose it (see
[Edge and TLS](edge-and-tls.md)). Labels are deliberately low-cardinality:
neither tenant nor task goes into labels.

### Counters and gauges

| Metric | Type | Meaning |
|---|---|---|
| `http_requests_total{method,status}` | counter | HTTP requests by method and status |
| `active_harness_sessions` | gauge | Active (unexpired) harness sessions |
| `active_claims` | gauge | Active task claims |
| `active_runs` | gauge | Runs in `running` status |
| `claim_takeovers_total` | counter | Claim takeovers after lease expiry |
| `stale_fencing_rejections_total` | counter | Write rejections with a stale fencing token (a zombie harness after takeover) |
| `run_cancellations_total` | counter | Cancelled runs |
| `context_requests_total`, `context_request_duration_seconds_sum`/`_count` | counter | Context assembly for harnesses and its duration |
| `context_degraded_total` | counter | Context returned in degraded form (memory unavailable) |
| `context_provider_failures_total` | counter | Memory provider failures on the interactive path |
| `context_adapter_delivered_total`, `_duplicates_total`, `_failures_total` | counter | Log delivery to memory: delivered, duplicates, failures |
| `context_adapter_parked_tenants` | gauge | Tenants whose delivery has stopped (parked) |
| `context_adapter_lag` | gauge | Delivery lag in events (capped at 1000) |
| `context_adapter_lag_capped` | gauge | `1` if the lag is at least 1000 |
| `event_replay_requests_total`, `event_replay_events_total` | counter | Log reads by consumers |
| `tool_invocation_denied_total` | counter | Denied tool (skill) invocations |
| `authz_shadow_*`, `authz_policy_unavailable_total` | counter | Only with `CP_AUTHZ_MODE=shadow` or `policy`: comparisons and discrepancies with the PDP |

If the database is unavailable, the endpoint does not fail; instead of the
gauges it outputs the line `# DB gauges unavailable`.

### Prometheus scraping

```yaml
scrape_configs:
  - job_name: taimen-control-plane
    metrics_path: /metrics
    static_configs:
      - targets: ["127.0.0.1:18000"]      # or control-plane-api:8000 from inside the compose network
```

## Recommended alerts

| Condition | Threshold | What to do |
|---|---|---|
| Control Plane `/health/ready` is not `200` | 2 min | See [Installation and startup](../troubleshooting/startup.md): `database_unreachable` or `migrations_pending` |
| Any container `unhealthy` or in a restart loop | 5 min | `tools/compose logs <service>` |
| `context_adapter_parked_tenants > 0` | immediately | The "delivery stopped" scenario below |
| `context_adapter_lag_capped == 1` or `context_adapter_lag` growing | 15 min | Check `memory-service`, the embedding provider, `context-adapter` logs |
| Growth of `context_provider_failures_total` / `context_degraded_total` | 10 min | Memory is unavailable or slow; coordination keeps working |
| Share of `http_requests_total{status=~"5.."}` | > 1% over 10 min | `control-plane-api` logs by `request_id` |
| A spike in `stale_fencing_rejections_total` | relative to normal | Two processes write under one claim: check the executors |
| `active_runs > 0` but `active_harness_sessions == 0` for a long time | 15 min | Executors lost their connection; check the runner host |
| Host disk | > 80% | Log, memory, images: `docker system df`, log retention |
| Certificate expiry | < 14 days | Caddy stopped renewing: `caddy` logs, DNS, ports |
| Expiry of the nearest PAT | < 14 days | Reissue; see [Secrets and rotation](secrets.md) |
| Age of the last backup | > 26 h | Check the backup job |

## Logs

```bash
tools/compose logs -f --since 10m control-plane-api
tools/compose logs --since 1h context-adapter | grep -iE 'error|park'
make logs svc=iam-service                    # tools/compose --profile "*" logs -f iam-service
```

- Control Plane writes structured logs; the level is `LOG_LEVEL`
  (`CP_LOG_LEVEL`). Correlate by `request_id` (one HTTP request, also
  returned in the error body as `requestId`) and `run_id` (the end-to-end
  trace of a run, the `X-Run-Id` header; the same `run_id` appears in the
  memory logs).

- Caddy writes JSON to stderr (in the production Caddyfile template).
- Control Plane API errors always have the form
  `{"error": {"code", "message", "details", "requestId"}}`; search the logs
  by the `requestId` from the response.

!!! warning "Docker log rotation"
    Services in the `deploy/local/compose.yml` use the default log driver, with no
    size limit. Configure rotation for the Docker daemon
    (`/etc/docker/daemon.json`):

    ```json
    {"log-driver": "json-file", "log-opts": {"max-size": "20m", "max-file": "5"}}
    ```

    The change applies to newly created containers.

## Control Plane operational tasks

These operations require the `operations.manage` permission and run through
the API or the `control-plane` CLI (the package from the superproject, with
an operator credential).

### Delivery to memory stopped (parked)

Symptom: `context_adapter_parked_tenants > 0`, and the context response has
`freshness.memoryIngest.status = "parked"`.

```bash
control-plane ops adapter status
# {"parked": true, "parkedReason": "...", "parkedEventId": "...", "cursor": "..."}
```

1. Read `parkedReason`: it is the memory provider's response. Typical
   causes: `401/403` due to a changed key or service account, a rejected
   observation schema.
2. Fix the cause (the key, the service account env file, memory
   availability).
3. Retry the same position:

    ```bash
    control-plane ops adapter redrive <tenant-id> --reason "memory credential rotated"
    ```

Redrive does not move the cursor and is idempotent. There is deliberately
no API that can "skip" an event. While one tenant is parked, the others are
delivered as usual; claims, runs, and approvals do not depend on memory at
all.

### Rebuilding memory

```bash
curl -s -X POST http://127.0.0.1:18000/api/v1/operations/context-adapter/<tenant-id>:rebuild \
  -H "Authorization: Bearer <admin access token>" -H 'Content-Type: application/json' \
  -d '{"reason": "memory restored from an older backup"}'
```

Without `cursor` the tenant is replayed from the start of the log; with
`cursor`, only backward (forward gives `422 cursor_must_not_advance`).

### Log growth

```bash
# move acknowledged history older than 30 days to the archive in the same database
curl -s -X POST http://127.0.0.1:18000/api/v1/operations/journal:archive \
  -H "Authorization: Bearer <admin access token>" -H 'Content-Type: application/json' \
  -d '{"beforeSeconds": 2592000, "maxEvents": 50000}'
```

`archived: 0` while consumers are still lagging is a working safeguard, not
an error. Physical deletion with `:prune` only after a backup. Details are
in [Backup](backup.md).

## Executor observability

- Daemon logs: `docker compose -f <executor compose file> logs -f runner`
  (container) or the unit's log file (systemd).
- The trace of each run is visible through MCP and the API: the `transcript`
  artifact and run actions `tool.<name>`; see [Run trace](../runner/trace.md).
- A sign of a publishing problem: the run succeeded, but the `commit`
  artifact has `published: false`.

## See also

- [Edge and TLS](edge-and-tls.md)
- [Backup](backup.md)
- [Emergency procedures](emergency.md)
- [Control Plane events](../control-plane/events.md)
- [Troubleshooting](../troubleshooting/index.md)
