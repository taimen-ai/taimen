
# Configuration

Reference for Control Plane settings: all server `CP_*` variables with the
defaults from `control_plane/config.py`, variables at the `deploy/local/compose.yml` level,
and the `CONTROL_PLANE_*` variables of the client tools (CLI, MCP server, SDK).
It is for those who deploy and maintain the Control Plane.

## How settings are read

- All server settings are fields of the `Settings` class (pydantic-settings)
  with the `CP_` prefix. Variable names are case-insensitive.
- Sources: the process environment variables and the `.env` file in the
  process's working directory. Environment variables take precedence over the
  file.
- **Lists are set as a JSON array**, for example
  `CP_CORS_ORIGINS='["https://platform.example.com"]'`. A comma-separated
  string will not parse.
- The same settings are read by three processes from one image:

| Process | Command | Service in `deploy/local/compose.yml` |
|---|---|---|
| API | `alembic upgrade head && uvicorn control_plane.main:app --host 0.0.0.0 --port 8000` | `control-plane-api` |
| Worker | `python -m control_plane.worker` | `control-plane-worker` |
| Context-adapter | `python -m control_plane.worker.context_adapter` | `context-adapter` |

!!! warning "An incomplete configuration fails startup"
    The process does not start if a mode is half-enabled:
    `CP_IAM_ENABLED=true` without `CP_IAM_ISSUER` or `CP_IAM_JWKS_URL`;
    `CP_ENTITLEMENT_ENABLED=true`, `CP_AUTHZ_MODE=shadow|policy`, or
    `CP_CONTEXT_AUTH=iam` without `CP_IAM_CLIENT_ID` and `CP_IAM_CLIENT_SECRET`;
    an unknown value of `CP_AUTHZ_MODE`, `CP_CONTEXT_PROVIDER`, or
    `CP_CONTEXT_AUTH`. Silently falling back to the previous mode would be
    worse.

## Core settings

| Variable | Default | Meaning |
|---|---|---|
| `CP_ENV` | `dev` | environment label |
| `CP_DATABASE_URL` | `postgresql+psycopg://control_plane:control_plane@localhost:5433/control_plane` | PostgreSQL connection string (psycopg 3 driver, async) |
| `CP_LOG_LEVEL` | `INFO` | structured JSON log level |
| `CP_BOOTSTRAP_TOKEN` | — | token for `POST /api/v1/bootstrap`; if not set, the endpoint is disabled (`403 bootstrap_disabled`) |
| `CP_CORS_ORIGINS` | `[]` | allowed origins; an empty list disables CORS |
| `CP_MAX_BODY_BYTES` | `1048576` (1 MiB) | maximum request body size; larger — `413 request_too_large` |
| `CP_KNOWLEDGE_SNAPSHOT_MAX_BODY_BYTES` | `8388608` (8 MiB) | body limit only for `POST /api/v1/knowledge/snapshots` |
| `CP_KNOWLEDGE_PACK_ADMINS` | `[]` | principal ids (Control Plane or IAM) allowed to call `POST /api/v1/knowledge/packs`; an empty list closes the endpoint |

## Leases: sessions and claims

A TTL passed by the client is clamped to the `[MIN, MAX]` bounds. If the client
did not pass a TTL, the default is used.

| Variable | Default | Meaning |
|---|---|---|
| `CP_SESSION_TTL_SECONDS` | `300` | default session TTL |
| `CP_SESSION_TTL_MIN_SECONDS` | `10` | lower bound |
| `CP_SESSION_TTL_MAX_SECONDS` | `3600` | upper bound |
| `CP_CLAIM_TTL_SECONDS` | `300` | default claim TTL |
| `CP_CLAIM_TTL_MIN_SECONDS` | `10` | lower bound; it also limits the skill invocation lease |
| `CP_CLAIM_TTL_MAX_SECONDS` | `3600` | upper bound |

## Idempotency

| Variable | Default | Meaning |
|---|---|---|
| `CP_IDEMPOTENCY_TTL_SECONDS` | `86400` | how long a response is stored by `Idempotency-Key` |
| `CP_IDEMPOTENCY_WAIT_TIMEOUT_SECONDS` | `10.0` | how long a parallel duplicate waits for the first request, then `409 idempotency_in_flight` |
| `CP_IDEMPOTENCY_PENDING_TTL_SECONDS` | `60` | how long a record without a stored response lives (the executor crashed) |

## Realtime, worker, outbox

| Variable | Default | Meaning |
|---|---|---|
| `CP_WS_POLL_INTERVAL_SECONDS` | `5.0` | the WebSocket's event log polling period if NOTIFY is lost |
| `CP_WORKER_POLL_INTERVAL_SECONDS` | `1.0` | worker loop period |
| `CP_OUTBOX_BATCH_SIZE` | `50` | outbox records per cycle |
| `CP_OUTBOX_MAX_ATTEMPTS` | `8` | delivery attempts before dead-letter |
| `CP_OUTBOX_LOCK_TIMEOUT_SECONDS` | `60` | outbox record lock |
| `CP_OUTBOX_BACKOFF_BASE_SECONDS` | `2.0` | exponential backoff base |
| `CP_OUTBOX_BACKOFF_MAX_SECONDS` | `300.0` | backoff ceiling |
| `CP_APPROVAL_OUTCOME_DEFER_SECONDS` | `15.0` | after how long to retry an approval outcome if the target is held by a live claim |
| `CP_API_KEY_LAST_USED_REFRESH_SECONDS` | `60` | update a legacy key's `last_used_at` no more often than this |
| `CP_JOURNAL_RETENTION_MIN_AGE_SECONDS` | `2592000` (30 days) | minimum event age for event log archiving and pruning |

The worker delivers the outbox, reaps expired sessions, claims, and skill
invocation leases, cleans up idempotency records, and executes approval
outcomes. It is not required for correctness: leases are also reaped lazily by
the commands themselves. But without it, approval outcomes are not executed
and the outbox is not delivered.

## Memory (context provider and context-adapter)

| Variable | Default | Meaning |
|---|---|---|
| `CP_CONTEXT_PROVIDER` | `none` | `none` — no memory (the Control Plane is autonomous, readiness does not depend on memory); `http` — memory-service |
| `CP_CONTEXT_BASE_URL` | `http://localhost:8077` | memory-service address |
| `CP_CONTEXT_API_KEY` | — | static Bearer for memory-service |
| `CP_CONTEXT_AUTH` | `auto` | `api_key`, `iam`, or `auto` (`iam` if a service account is set, otherwise `api_key`) |
| `CP_CONTEXT_IAM_AUDIENCE` | `memory-service` | the service account token audience |
| `CP_CONTEXT_IAM_SCOPES` | `["memory:read","memory:write","memory:tenants","memory:service"]` | token scopes; with `CP_AUTHZ_MODE=policy`, `memory:on-behalf` is added |
| `CP_CONTEXT_NAMESPACE_PREFIX` | `tenant:` | tenant namespace = prefix + `<tenant-id>` |
| `CP_CONTEXT_TIMEOUT_SECONDS` | `3.0` | `/context` read timeout (the harness's synchronous path) |
| `CP_CONTEXT_INGEST_TIMEOUT_SECONDS` | `15.0` | timeout of the adapter's batch write |
| `CP_CONTEXT_RECONCILE_TIMEOUT_SECONDS` | `60.0` | `/knowledge/*` timeout |
| `CP_CONTEXT_BATCH_SIZE` | `100` | event batch size |
| `CP_CONTEXT_TENANT_BATCH_SIZE` | `100` | events of one tenant per cycle |
| `CP_CONTEXT_MAX_TENANTS_PER_CYCLE` | `20` | tenants per cycle (fairness) |
| `CP_CONTEXT_POLL_INTERVAL_SECONDS` | `1.0` | the adapter's event log polling period |
| `CP_CONTEXT_RETRY_BACKOFF_BASE_SECONDS` | `1.0` | backoff base on a delivery failure |
| `CP_CONTEXT_RETRY_BACKOFF_MAX_SECONDS` | `60.0` | backoff ceiling |
| `CP_CONTEXT_MAX_TOKENS_LIMIT` | `16000` | memory pack budget ceiling |
| `CP_CONTEXT_DEFAULT_MAX_TOKENS` | `8000` | default budget |

Details are in [Task context and memory](context.md).

## Artifact content storage { #content-store }

The core stores artifact bytes (`PUT /artifact-contents`) in any S3-compatible
storage. Without `CP_S3_ENDPOINT_URL` the storage is disabled: the content
routes respond `503 content_store_unavailable`, while artifact records
(references and JSON) work as usual. See
[Artifacts](artifacts.md#content) and [Object storage](../operations/object-storage.md).

| Variable | Default | Meaning |
|---|---|---|
| `CP_S3_ENDPOINT_URL` | — | address of the S3-compatible service; if not set, the storage is disabled |
| `CP_S3_BUCKET` | `artifacts` | content bucket; the API creates it at startup if it does not exist and permissions allow |
| `CP_S3_REGION` | `us-east-1` | request signing region |
| `CP_S3_ACCESS_KEY_ID` | — | access key of the core's user |
| `CP_S3_SECRET_ACCESS_KEY` | — | secret of the core's user |
| `CP_S3_CONNECT_TIMEOUT_SECONDS` | `5.0` | storage connection timeout |
| `CP_S3_READ_TIMEOUT_SECONDS` | `60.0` | read timeout |
| `CP_ARTIFACT_MAX_BYTES` | `104857600` (100 MiB) | single-file limit; for `PUT /artifact-contents` it replaces `CP_MAX_BODY_BYTES`, larger — `413 request_too_large`. An artifact type can only narrow it (`maxBytes`) |
| `CP_ARTIFACT_UPLOAD_TTL_SECONDS` | `86400` (24 h) | how long an upload waits for an artifact to reference it; after that the worker deletes it |

The API and the worker read the storage: the worker deletes unreferenced
uploads after the deadline and objects that nothing references anymore. A
storage that is unavailable at startup does not stop the API: a warning is
written to the log, and the bucket is checked again on first access.

## IAM

| Variable | Default | Meaning |
|---|---|---|
| `CP_IAM_ENABLED` | `false` | accept IAM access tokens |
| `CP_IAM_ISSUER` | `""` | the expected issuer; **required** when IAM is enabled |
| `CP_IAM_JWKS_URL` | `""` | JWKS address; **required** when IAM is enabled |
| `CP_IAM_AUDIENCE` | `control-plane` | the expected audience |
| `CP_IAM_LEEWAY_SECONDS` | `5.0` | allowed clock skew when checking token lifetime |
| `CP_IAM_JWKS_REFRESH_AFTER_SECONDS` | `300.0` | after how long to refresh the JWKS |
| `CP_IAM_JWKS_STALE_AFTER_SECONDS` | `3600.0` | how long you can live on a stale JWKS if IAM is unavailable |
| `CP_IAM_JWKS_MIN_REFRESH_INTERVAL_SECONDS` | `10.0` | minimum interval between unscheduled JWKS refreshes |
| `CP_IAM_REQUEST_TIMEOUT_SECONDS` | `3.0` | timeout of requests to IAM |
| `CP_IAM_BINDING_CACHE_TTL_SECONDS` | `30.0` | cache of the `iam_principal_bindings` projection |
| `CP_IAM_BINDING_STALE_AFTER_SECONDS` | `120.0` | after this time without a successful re-read, sign-in is closed |
| `CP_LEGACY_API_KEYS_ENABLED` | `true` | accept legacy `cp_…` keys; `false` — IAM only |
| `CP_BREAK_GLASS_ENABLED` | `true` | emergency `cp_bg…` keys from the host shell (CP-ADR-0065): issuance and acceptance, including when the legacy key window is closed |
| `CP_BREAK_GLASS_MAX_TTL_SECONDS` | `14400` | maximum lifetime of an emergency key |
| `CP_IAM_BASE_URL` | `http://localhost:8010` | IAM address for the core's service account |
| `CP_IAM_CLIENT_ID` | `""` | client id of the core's service account |
| `CP_IAM_CLIENT_SECRET` | — | secret of the core's service account |
| `CP_IAM_CLIENT_SCOPES` | `["entitlement:check-on-behalf"]` | scopes of the core's token for entitlement |

The core's service account is needed for memory in `iam` mode, for
entitlement, and for the PDP. Bootstrap creates it and writes
`CP_IAM_CLIENT_ID` and `CP_IAM_CLIENT_SECRET` to
`secrets/control-plane-iam.env`. See [Service accounts](../iam/service-accounts.md).

## Entitlement

!!! note "Extension point"
    The license check is disabled by default: the license service is not part
    of the delivery. The variables below are needed only if it is connected.

| Variable | Default | Meaning |
|---|---|---|
| `CP_ENTITLEMENT_ENABLED` | `false` | check licenses |
| `CP_ENTITLEMENT_BASE_URL` | `http://localhost:8020` | license service address |
| `CP_ENTITLEMENT_PRODUCT` | `control-plane` | product |
| `CP_ENTITLEMENT_AUDIENCE` | license service audience | the audience of the core's token |
| `CP_ENTITLEMENT_DEFAULT_FEATURE` | `api` | feature for paths that cannot be parsed |
| `CP_ENTITLEMENT_CACHE_TTL_SECONDS` | `30.0` | decision cache |
| `CP_ENTITLEMENT_DEGRADED_MAX_AGE_SECONDS` | `300.0` | how long you can live on a stale decision when the service is unavailable |
| `CP_ENTITLEMENT_TIMEOUT_SECONDS` | `3.0` | timeout |

## Domain authorization (PDP)

| Variable | Default | Meaning |
|---|---|---|
| `CP_AUTHZ_MODE` | `local` | `local`, `shadow`, or `policy`, see [Authorization and permissions](authorization.md#authz-mode) |
| `CP_POLICY_BASE_URL` | `http://localhost:8030` | external PDP address |
| `CP_POLICY_AUDIENCE` | PDP audience | the audience of the core's token |
| `CP_POLICY_SCOPES` | `["policy:check","policy:check-on-behalf"]` | scopes of the core's token |
| `CP_POLICY_TIMEOUT_SECONDS` | `3.0` | timeout |
| `CP_POLICY_CACHE_TTL_SECONDS` | `5.0` | decision cache |

!!! note "Extension point"
    `shadow` and `policy` require an external PDP that is not part of the
    delivery.

## `deploy/local/compose.yml`-level variables

The Control Plane itself does not read these variables. `deploy/local/compose.yml`
substitutes them from the superproject's `.env`.

| `.env` variable | Default | Where it goes |
|---|---|---|
| `CP_POSTGRES_PASSWORD` | required | `control-plane-db` password; assembled into `CP_DATABASE_URL` |
| `CP_BOOTSTRAP_TOKEN` | required | the API service's `CP_BOOTSTRAP_TOKEN` |
| `MEMORY_API_KEY` | required | `CP_CONTEXT_API_KEY` of all three processes |
| `TAIMEN_PUBLIC_URL` | — | `CP_IAM_ISSUER=${TAIMEN_PUBLIC_URL}/iam` |
| `LOG_LEVEL` | `INFO` | `CP_LOG_LEVEL` |
| `CP_CONTEXT_AUTH` | `auto` | as is |
| `CP_AUTHZ_MODE` | `local` | as is |
| `CP_LEGACY_API_KEYS_ENABLED` | `false` | as is |
| `CP_CORS_ORIGINS` | `[]` | as is |
| `CP_S3_ACCESS_KEY_ID`, `CP_S3_SECRET_ACCESS_KEY` | required | keys of the core's user in the storage; for the deployment's MinIO, `minio-bootstrap` creates them too |
| `CP_S3_BUCKET` | `artifacts` | as is; `minio-bootstrap` creates the bucket |
| `CP_S3_ENDPOINT_URL` | `http://minio:9000` | as is; for external S3 — the provider's address |
| `CP_S3_REGION` | `us-east-1` | as is |
| `CP_HOST_PORT` | `18000` | publishes the API on the host's `127.0.0.1:<port>` |
| `CP_MEM_LIMIT` | `512m` | API memory limit |
| `CP_WORKER_MEM_LIMIT` | `256m` | memory limit of the worker and context-adapter |
| `CP_BUILD_CONTEXT` | `.` | image build context (the superproject root: the SDK is included as a neighboring directory) |

Values that `deploy/local/compose.yml` fixes for the Control Plane processes:

```yaml
CP_CONTEXT_PROVIDER: http
CP_CONTEXT_BASE_URL: http://memory-service:8077
CP_IAM_BASE_URL: http://iam-service:8010
CP_S3_ENDPOINT_URL: http://minio:9000        # unless overridden in .env
CP_S3_BUCKET: artifacts                      # unless overridden in .env
# control-plane-api only:
CP_IAM_ENABLED: "true"
CP_IAM_JWKS_URL: http://iam-service:8010/.well-known/jwks.json
CP_IAM_AUDIENCE: control-plane
```

The core's service account is connected through the optional `env_file`
`./secrets/control-plane-iam.env`: the first `up` succeeds without it. After
bootstrap, restart `control-plane-api`, `control-plane-worker`, and
`context-adapter` so they pick up the file. The full list of platform variables
is in [Environment variables](../reference/environment.md) and
[.env configuration](../getting-started/configuration.md).

## Typical profiles

=== "Delivery (IAM-only)"

    ```dotenv
    CP_IAM_ENABLED=true
    CP_IAM_ISSUER=https://platform.example.com/iam
    CP_IAM_JWKS_URL=http://iam-service:8010/.well-known/jwks.json
    CP_LEGACY_API_KEYS_ENABLED=false
    CP_CONTEXT_PROVIDER=http
    CP_CONTEXT_AUTH=auto
    CP_AUTHZ_MODE=local
    ```

=== "Local development without memory"

    ```dotenv
    CP_DATABASE_URL=postgresql+psycopg://control_plane:control_plane@localhost:5433/control_plane
    CP_BOOTSTRAP_TOKEN=dev-bootstrap-token
    CP_CONTEXT_PROVIDER=none
    CP_IAM_ENABLED=false
    CP_LEGACY_API_KEYS_ENABLED=true
    ```

=== "Policy verification (shadow)"

    ```dotenv
    CP_AUTHZ_MODE=shadow
    CP_POLICY_BASE_URL=http://<PDP address>:8030
    CP_IAM_CLIENT_ID=<client-id>
    CP_IAM_CLIENT_SECRET=<secret>
    ```

## Client variables `CONTROL_PLANE_*`

These variables are read by the `control-plane` CLI, the `control-plane-mcp`
MCP server, and the `control_plane_client` SDK, not by the server. Details are
in [CLI and MCP server](cli-and-mcp.md#credentials).

| Variable | Who reads it | Meaning |
|---|---|---|
| `CONTROL_PLANE_SERVER` | CLI, MCP | Control Plane address |
| `CONTROL_PLANE_API_KEY` | SDK | legacy key (explicit override) |
| `CONTROL_PLANE_NO_KEYCHAIN` | SDK | `1` — do not use the macOS Keychain for the legacy key |
| `CONTROL_PLANE_IAM_URL` | SDK | IAM base URL; enables the IAM identity |
| `CONTROL_PLANE_IAM_TENANT` | SDK | the tenant in IAM |
| `CONTROL_PLANE_IAM_AUDIENCE` | SDK | exchange audience, `control-plane` by default |
| `CONTROL_PLANE_IAM_SCOPES` | SDK | exchange scopes (separated by spaces or commas) |
| `CONTROL_PLANE_HARNESS_TYPE` | MCP | the session's `harness.type`, `mcp-client` by default |
| `CONTROL_PLANE_HARNESS_VERSION` | MCP | `harness.version`, the package version by default |
| `CONTROL_PLANE_HARNESS_CLIENT_NAME` | MCP | `clientName`, `control-plane-mcp` by default |
| `CONTROL_PLANE_CONTEXT_BUDGET_CHARS` | executor adapters | memory section budget in the prompt, `12000` by default |

The IAM store variables are used alongside: `IAM_PRINCIPAL`,
`IAM_CREDENTIAL_MODE`, `IAM_PLATFORM_ACCESS_TOKEN`, `IAM_NO_KEYCHAIN`.

The executor daemon variables (`CONTROL_PLANE_AGENT_*`,
`CONTROL_PLANE_CLAUDE_*`, `CONTROL_PLANE_CODEX_*`, `CONTROL_PLANE_SKILLS_*`,
`CONTROL_PLANE_TRACE_*`) are described in [Executor configuration](../runner/configuration.md).

## Verifying the configuration

```bash
# the process is up, migrations are applied
curl -s http://127.0.0.1:18000/health/ready
# {"status": "ready", "revision": "<alembic-head>"}

# IAM sign-in works and permissions are correct
control-plane whoami

# memory is connected
curl -s -X POST http://127.0.0.1:18000/api/v1/context \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"query": "ping"}' | jq '.memoryStatus, .warnings'
```

## See also

- [Authorization and permissions](authorization.md)
- [Task context and memory](context.md)
- [API](api.md)
- [Environment variables](../reference/environment.md)
- [Services and ports](../reference/services-and-ports.md)
- [Secrets and rotation](../operations/secrets.md)
- [Object storage (MinIO)](../operations/object-storage.md)
