
# Environment variables

The full list of Taimen delivery environment variables: the root `.env` (the
`.env.example` contract), the variables that `deploy/local/compose.yml` passes into
containers, the settings of each service (pydantic-settings with a prefix),
and the variables of processes outside compose: the runner agent, the CLI, the
MCP server, the connector, and the SDK. This page is for an engineer who
configures a deployment or investigates where a service got a value from.

## How configuration works

```mermaid
flowchart LR
    ENV[".env<br/>(from .env.example)"] -->|${VAR} interpolation| COMPOSE["deploy/local/compose.yml"]
    COMPOSE -->|environment:| SVC["container<br/>CP_* / IAM_* / CB_* / ..."]
    SECRETS["secrets/*.env<br/>(written by bootstrap)"] -->|env_file| SVC
    PEM["secrets/*.pem"] -->|docker secret| SVC
```


1. The operator fills in **one** `.env` file in the superproject root. In it,
   one concept has one name (`MEMORY_API_KEY`, `TAIMEN_PUBLIC_URL`,
   `LLM_MODEL`). `make secrets` creates it from `.env.example` and generates
   random secrets.
2. `deploy/local/compose.yml` distributes the values across service prefixes: for example,
   `MEMORY_API_KEY` becomes `CB_SERVER_API_KEY` for memory-service and
   `CP_CONTEXT_API_KEY` for Control Plane.
   Compose hard-codes some service variables (addresses inside the network,
   audience); you cannot change them through `.env`.
3. Secrets that appear only after bootstrap (service account client
   credentials) live in `secrets/*.env` and are attached through `env_file`
   with `required: false`, so the first `up` succeeds without them.
4. Inside a service, pydantic-settings reads the values with a prefix
   (`CP_`, `IAM_`, `CB_`, `NS_`). Unknown variables are ignored
   (`extra="ignore"`).

| Prefix | Component | Where it is read |
|---|---|---|
| `CP_` | Control Plane (api, worker, context-adapter) | `control_plane/config.py` |
| `IAM_` | iam-service | `iam_service/config.py` |
| `CB_` | memory-service | `platform_memory/core/config.py` |
| `NS_` | notification-service | `notification_service/config.py` |
| `FLEET_` | fleet-controller | `fleet_controller/wiring.py` (read directly from the environment) |
| `CONTROL_PLANE_*`, `IAM_*` (client-side) | runner, CLI, MCP server, SDK client | `control_plane_agent`, `control_plane_client` |

!!! warning "Required variables are checked for all profiles"
    Variables of the form `${VAR:?…}` in `deploy/local/compose.yml` are required **for any
    set of profiles**: Docker Compose interpolates the whole file before
    filtering by profile. That is why only the values that `make secrets`
    generates are declared required (`:?`); identifiers that there is nothing

    to generate from (`IAM_TENANT_ID`) are empty by default and are checked by
    the services of their own profiles. Check with `make config`.

## Root `.env`

The `.env.example` contract variables and the other `deploy/local/compose.yml`
interpolation variables. The "Default" column is the substitution value in
`deploy/local/compose.yml` (`${VAR:-…}`); "required" means the `${VAR:?…}` substitution.

### Environment and edge

| Variable | Default | Required | Purpose |
|---|---|---|---|
| `TAIMEN_PUBLIC_URL` | — (in `.env.example`: `http://taimen.localhost`) | yes | Public address of the platform without a trailing `/`. The IAM issuer (`${TAIMEN_PUBLIC_URL}/iam`), the Keycloak issuer (`…/auth/realms/platform`), the workplace launcher addresses (`…/harness`), and the redirect URIs of the `human-harness` client in the realm template are built from it. Changing the address changes the issuer; see the warning in [Permissions and scopes](permissions.md#iam-principal-bindings). |
| `TAIMEN_PUBLIC_HOST` | `taimen.localhost` | no | Network alias of the `caddy` container: containers reach IAM and Keycloak by the public name (hairpin) so that the issuer matches what the browser sees. |
| `COMPOSE_PROJECT_NAME` | `taimen` | no | Compose project name. The default prefix of volume names. Also read by `deploy/bootstrap.py` (environment name and tenant slug). |
| `TAIMEN_NETWORK` | `taimen_default` | no | Name of the `taimen` docker network. |
| `CADDYFILE` | `./deploy/caddy/Caddyfile.local` | no | Caddy configuration file, mounted into the `caddy` container. For a TLS deployment, use your own file with the same path layout. |
| `EDGE_HTTP_PORT` | `80` | no | Published HTTP port of the `caddy` container. |
| `EDGE_HTTPS_PORT` | `443` | no | Published HTTPS port of the `caddy` container. |
| `LOG_LEVEL` | `INFO` | no | Log level: `CP_LOG_LEVEL`. |
| `LOG_RENDERER`, `CP_TIMEZONE` | — | no | Declared in `.env.example`, but not read by the `deploy/local/compose.yml` services. |
| `IMAGE_PREFIX` | `taimen` | no | Image name prefix: `${IMAGE_PREFIX}/control-plane:${IMAGE_TAG}`. |
| `IMAGE_TAG` | `local` | no | Image tag. |

### Tenant and identifiers

| Variable | Default | Required | Purpose |
|---|---|---|---|
| `IAM_TENANT_ID` | `""` | no | The IAM tenant UUID. Needed by fleet-controller and the workplace launcher (`LAUNCHER_IAM_TENANT`, `HARNESS_IAM_TENANT` of people's containers). `make bootstrap` prints the value to put here. Also read by `deploy/bootstrap.py`. |

### Secrets

`make secrets` fills every value in this table, except those marked
otherwise, with a random string (`tools/fill_secrets.py`) if it is empty or
missing from `.env`.


| Variable | Default | Required | Purpose |
|---|---|---|---|
| `CP_POSTGRES_PASSWORD` | — | yes | Password of the `control_plane` database (role `control_plane`). |
| `IAM_POSTGRES_PASSWORD` | — | yes | Password of the `iam` database. |
| `MEMORY_POSTGRES_PASSWORD` | — | yes | Password of the `company_brain` database (role `memory`). |
| `KEYCLOAK_DB_PASSWORD` | — | yes | Password of the `keycloak` database and role in `keycloak-db`. |
| `NOTIFY_POSTGRES_PASSWORD` | — | yes | Password of the `notify` database (notification-service). |
| `CP_BOOTSTRAP_TOKEN` | — | yes | Token for the Control Plane `POST /api/v1/bootstrap` (`Authorization: Bearer`). |
| `IAM_BOOTSTRAP_TOKEN` | — | yes | Token for the IAM bootstrap endpoints (header `X-IAM-Bootstrap-Token`). |
| `MEMORY_API_KEY` | — | yes | Static memory key: `CB_SERVER_API_KEY` of memory-service, `CP_CONTEXT_API_KEY` of the core (used until the service account exists; see `CP_CONTEXT_AUTH`). |
| `KEYCLOAK_ADMIN` | `admin` | no | Login of the Keycloak bootstrap administrator. |
| `KEYCLOAK_ADMIN_PASSWORD` | — | yes | Password of the Keycloak bootstrap administrator. |
| `KEYCLOAK_HOSTNAME_STRICT` | `true` | no | `KC_HOSTNAME_STRICT`. Locally over HTTP without a domain, `false`. |
| `S3_ACCESS_KEY_ID` | — | yes | MinIO root user; only `minio-bootstrap` uses it. |
| `S3_SECRET_ACCESS_KEY` | — | yes | MinIO root password. |
| `CP_S3_ACCESS_KEY_ID`, `CP_S3_SECRET_ACCESS_KEY` | — | yes | The core's MinIO user with the `cp-artifacts` policy (created by `minio-bootstrap`); Control Plane processes use it to write and read artifact content. |
| `CP_S3_BUCKET` | `artifacts` | no | Artifact content bucket (created by `minio-bootstrap`). |
| `CP_S3_ENDPOINT_URL`, `CP_S3_REGION` | `http://minio:9000`, `us-east-1` | no | S3 address and region; an empty address disables content storage. See [Object storage](../operations/object-storage.md). |
| `IAM_SIGNING_KEY_FILE` | `./secrets/iam-signing.pem` | no | Private key file for signing IAM tokens (RSA 3072, `make secrets`); mounted as the `iam_signing_key` docker secret. |
| `IAM_SIGNING_KEY_ID` | `local-dev` | no | `kid` of the IAM signing key. |

!!! note "Key files are read by uid 10001"
    The `iam-service`, `control-plane-*`, and other platform service containers
    run as an unprivileged user with uid 10001. On Linux, the
    `secrets/*.pem` files must be owned by that uid with mode `600`:
    otherwise the service gets a `PermissionError` when reading the key.

### LLM and memory

| Variable | Default | Required | Purpose |
|---|---|---|---|
| `LLM_API_KEY` | `""` | no | Key of an OpenAI-compatible provider: memory embeddings and LLM (`CB_EMBEDDING_API_KEY`, `CB_LLM_API_KEY`), the demo bot. Empty means memory works offline (`fake`/`echo`). |
| `LLM_BASE_URL` | for memory `""`; for the demo `https://api.aitunnel.ru/v1` | no | Base URL of the OpenAI-compatible API. |
| `LLM_MODEL` | `gemini-3.5-flash-lite` | no | LLM model for memory (`CB_LLM_MODEL`) and the demo bot. |
| `MEMORY_EMBEDDING_PROVIDER` | `fake` | no | `CB_EMBEDDING_PROVIDER`: `fake` (offline) or `openai`. |
| `MEMORY_EMBEDDING_MODEL` | `text-embedding-3-small` | no | `CB_EMBEDDING_MODEL`. |
| `MEMORY_LLM_PROVIDER` | `echo` | no | `CB_LLM_PROVIDER`: `echo` (offline) or `openai`. |
| `MEMORY_RERANK_ENABLED` | `false` | no | `CB_RERANK_ENABLED`. |
| `MEMORY_CONSOLE_ENABLED` | `false` | no | `CB_CONSOLE_ENABLED`: the administrative Memory Console. |
| `MEMORY_IAM_ENABLED` | `true` | no | `CB_IAM_ENABLED`: accept IAM tokens for the `memory-service` audience in addition to the static key. |
| `MEMORY_POLICY_ENABLED` | `false` | no | `CB_POLICY_ENABLED`: memory visibility per principal through an external PDP (experimental). |

### Control Plane


| Variable | Default | Required | Purpose |
|---|---|---|---|
| `CP_LEGACY_API_KEYS_ENABLED` | `false` | no | Whether to accept legacy `cp_…` keys (`CP_LEGACY_API_KEYS_ENABLED`). In the stack, IAM is always enabled (`CP_IAM_ENABLED: "true"`). |
| `CP_CONTEXT_AUTH` | `auto` | no | How the core authenticates to memory: `auto`, `api_key`, `iam`. |
| `CP_AUTHZ_MODE` | `local` | no | Source of domain authorization: `local`, `shadow`, `policy` (CP-ADR-0055). |
| `CP_CORS_ORIGINS` | `[]` | no | JSON list of allowed API CORS origins. |

### Notification service

| Variable | Default | Purpose |
|---|---|---|
| `NOTIFY_EMAIL_FROM` | `notifications@localhost` | `NS_EMAIL_FROM`: the email sender. |
| `NOTIFY_SMTP_HOST` | `localhost` | `NS_SMTP_HOST`. |
| `NOTIFY_SMTP_PORT` | `587` | `NS_SMTP_PORT`. |

### Workplaces (`harness`)

| Variable | Default | Purpose |
|---|---|---|
| `HARNESS_MEM_LIMIT_MB` | `1536` | Memory limit of a person's container (`LAUNCHER_HARNESS_MEMORY_MB`). |
| `HARNESS_CPUS` | `1` | CPU limit of a person's container, in cores (`LAUNCHER_HARNESS_CPUS`). |
| `HARNESS_PIDS_LIMIT` | `512` | Process limit of a person's container (`LAUNCHER_HARNESS_PIDS`). |
| `HARNESS_PEOPLE_NETWORK` | `<COMPOSE_PROJECT_NAME>_harness-people` | Network of people's containers (`LAUNCHER_NETWORK`): the launcher, the core, notifications, caddy; no databases and no Docker proxy. |
| `HARNESS_CONTROL_NETWORK` | `<COMPOSE_PROJECT_NAME>_harness-control` | Internal network of the Docker proxy and the launcher. See [Workplace isolation](../workplace/index.md#isolation). |
| `HARNESS_IDLE_MINUTES` | `30` | After how many minutes without requests a person's container goes to sleep (`LAUNCHER_IDLE_MINUTES`). |
| `HARNESS_APP_NAME` | `Human Harness` | Application name of the workplace (`appName` in the assistant engine's `whoami` response). |
| `HARNESS_COOKIE_SECRET_FILE` | `./secrets/harness/cookie-secret` | The launcher cookie key file (docker secret `harness_cookie_secret`, written by bootstrap step 8). |
| `NOTIFY_HARNESS_LAUNCHER_URL` | `http://harness-launcher:8080/harness` | Launcher address for the notification service (the assistant in Telegram). |

Details are in [Personal workspace](../workplace/index.md).

### Runtime console (OIDC)

The console signs in through an OIDC IdP (Authorization Code + PKCE, confidential client) and
exchanges the IdP id token in IAM `federation:exchange` for tokens of the audiences
`control-plane`, `iam`, `human-harness`. About the IdP itself, the console knows only
the issuer, the client id, and the secret.

| Variable | Default | Purpose |
|---|---|---|
| `RUNTIME_CONSOLE_OIDC_ISSUER` | `${TAIMEN_PUBLIC_URL}/auth/realms/platform` | Issuer of the OIDC IdP. |
| `RUNTIME_CONSOLE_OIDC_CLIENT_ID` | `runtime-console` | Client id of the console in the IdP. |
| `RUNTIME_CONSOLE_OIDC_SECRET_FILE` | `./secrets/runtime-console-oidc-secret` | Client secret file (0600, docker secret `runtime_console_oidc_secret`). Written by `make secrets` or `deploy/keycloak/keycloak-runtime-console-client.py`. |
| `RUNTIME_CONSOLE_IDENTITY_PROVIDER` | `keycloak` | Identity provider key in IAM for `federation:exchange`. |
| `RUNTIME_CONSOLE_OIDC_SCOPES` | `openid profile email` | Scopes of the IdP request. Keycloak issues a refresh token even without `offline_access`. |
| `RUNTIME_CONSOLE_COOKIE_SECRET_FILE` | `./secrets/runtime-console-cookie-secret` | Console cookie secret, at least 32 bytes (0600, written by `make secrets`): the session signing key and the encryption key of the unfinished-sign-in cookie are derived from it. The cookie holds only a random session id; the tokens stay on the console server. |
| `RUNTIME_CONSOLE_CP_SCOPES` | `control-plane:read control-plane:write` | Scopes the console explicitly requests from federation. What a person may do in a given case is decided by their bindings in the core. |
| `RUNTIME_CONSOLE_SESSION_TTL_HOURS` | `12` | Console session lifetime. |
| `RUNTIME_CONSOLE_PRODUCT_NAME`, `RUNTIME_CONSOLE_ORG_NAME` | `Console`, empty | Product and organization name in the console interface (white-label): the console server hands them to the interface at startup; the console code contains no product name. |
| `RUNTIME_CONSOLE_LOCALES`, `RUNTIME_CONSOLE_DEFAULT_LOCALE` | `en,ru`, `en` | Interface languages and the default language. |

Federation issues privileged scopes only to members of an IAM group and only on explicit
request: `iam:people` (managing people) to the `people-admins` group, `fleet:admin`
(fleet node registration keys) to the `fleet-admins` group. The groups and the owner's
membership are created by `deploy/bootstrap.py` (step 2b). By default the console requests `fleet:read`;
to get `fleet:admin`, a person must be a member of `fleet-admins`.


### Catalog package variables { #package-variables }

`deploy/local/compose.yml` does not interpolate these variables: the package installer
`package-sdk` reads them (from `.env`, the `--env` flag, and the
process environment) and substitutes them into `${NAME}` in package objects
during `plan` and `apply`. The package itself declares which variables it
needs; an unset variable that a package in the installation needs is an
installation error.

The installer tokens are also process variables, not `.env`: `CP_TOKEN` (an
access token for the `control-plane` audience) and `NOTIFY_TOKEN` (audience
`notification-service`, scope `notifications:admin`, required for
`NotificationRule`). Without them, the installer exchanges the IAM credential
of the Control Plane client (see [Catalog packages](../control-plane/catalog-packages.md)).

### Ports on 127.0.0.1

All services except `caddy` are published only on loopback. Details are in
[Services and ports](services-and-ports.md).

| Variable | Default | Service (internal port) |
|---|---|---|
| `CP_HOST_PORT` | `18000` | `control-plane-api` (8000). Read by `deploy/bootstrap.py`. |
| `MEMORY_HOST_PORT` | `18001` | `memory-service` (8077) |
| `IAM_HOST_PORT` | `18010` | `iam-service` (8010). Read by `deploy/bootstrap.py`. |
| `NOTIFY_HOST_PORT` | `18045` | `notification-service` (8000) |
| `KEYCLOAK_HOST_PORT` | `18081` | `keycloak` (8080) |

### Container memory limits

| Variable | Default | Containers |
|---|---|---|
| `PG_MEM_LIMIT` | `256m` | `iam-db`, `control-plane-db`, `keycloak-db` |
| `IAM_MEM_LIMIT` | `256m` | `iam-service` |
| `CP_MEM_LIMIT` | `512m` | `control-plane-api` |
| `CP_WORKER_MEM_LIMIT` | `256m` | `control-plane-worker`, `context-adapter` |
| `MEMORY_DB_MEM_LIMIT` | `512m` | `memory-db` |
| `MEMORY_MEM_LIMIT` | `512m` | `memory-service` |
| `NOTIFY_MEM_LIMIT` | `256m` | `notification-service` |
| `NOTIFY_DB_MEM_LIMIT` | `128m` | `notification-db` |
| `KEYCLOAK_MEM_LIMIT` | `768m` | `keycloak` |
| `MINIO_MEM_LIMIT` | `256m` | `minio` |
| `FLEET_MEM_LIMIT` | `128m` | `fleet-controller` |

### Build contexts

They override the directory an image is built from (for example, to build
from a separate release clone).

| Variable | Default |
|---|---|
| `IAM_BUILD_CONTEXT` | `./services/iam-service` |
| `CP_BUILD_CONTEXT` | `.` (Dockerfile `services/control-plane/Dockerfile`) |
| `MEMORY_BUILD_CONTEXT` | `.` for `memory-service` (Dockerfile `services/memory-service/Dockerfile`); `./services/memory-service` + `/infra/memory-db` for `memory-db` |
| `NOTIFY_BUILD_CONTEXT` | `.` (Dockerfile `services/notification-service/Dockerfile`) |
| `FLEET_BUILD_CONTEXT` | `.` (Dockerfile `services/fleet/Dockerfile`) |

!!! warning "One variable, two defaults"
    `MEMORY_BUILD_CONTEXT` is used both for `memory-db`
    (`${MEMORY_BUILD_CONTEXT:-./services/memory-service}/infra/memory-db`) and for
    `memory-service` (`${MEMORY_BUILD_CONTEXT:-.}`). If you set it explicitly,
    one of the two paths will be wrong; leave it empty.

### Volume names

If the variable is not set, each volume gets the name
`${COMPOSE_PROJECT_NAME}_<name>`. Set them to attach existing volumes (for
example, when moving a deployment to the root compose).


`VOLUME_IAM_DB`, `VOLUME_CONTROL_PLANE_DB`, `VOLUME_MEMORY_DB`,
`VOLUME_NOTIFY_DB`,
`VOLUME_KEYCLOAK_DB`, `VOLUME_PLATFORM_MINIO` (the MinIO volume with artifact content),
`VOLUME_REALM_IMPORT`, `VOLUME_HARNESS_LAUNCHER`,
`VOLUME_CADDY_DATA`, `VOLUME_CADDY_CONFIG` and `VOLUME_FLEET_DATA`.

## Control Plane (`CP_`)

Read by the `control-plane-api`, `control-plane-worker`, and
`context-adapter` processes (one image). The "In the stack" column is the
value that `deploy/local/compose.yml` sets.

### General

| Variable | Default | In the stack | Purpose |
|---|---|---|---|
| `CP_ENV` | `dev` | — | Declared in the settings, not used by code. |
| `CP_DATABASE_URL` | `postgresql+psycopg://control_plane:control_plane@localhost:5433/control_plane` | `…@control-plane-db:5432/control_plane` | SQLAlchemy connection string. |
| `CP_BOOTSTRAP_TOKEN` | not set | `${CP_BOOTSTRAP_TOKEN}` (api only) | Token for `POST /api/v1/bootstrap`. If not set, the endpoint returns `403 bootstrap_disabled`. |
| `CP_LOG_LEVEL` | `INFO` | `${LOG_LEVEL}` | Log level. |
| `CP_MAX_BODY_BYTES` | `1048576` | — | Request body limit; larger bodies get `413 request_too_large`. |
| `CP_KNOWLEDGE_SNAPSHOT_MAX_BODY_BYTES` | `8388608` | — | A separate limit for knowledge snapshots. |
| `CP_KNOWLEDGE_PACK_ADMINS` | `[]` | — | JSON list of principal ids (CP or IAM) allowed to register knowledge packs. If empty, `POST /api/v1/knowledge/packs` returns `403`. |
| `CP_CORS_ORIGINS` | `[]` | `${CP_CORS_ORIGINS}` (api) | JSON list of CORS origins. |
| `CP_WS_POLL_INTERVAL_SECONDS` | `5.0` | — | WebSocket stream polling interval when NOTIFY is lost. |
| `CP_API_KEY_LAST_USED_REFRESH_SECONDS` | `60` | — | How often to update the last-used mark of a legacy key. |

### Leases (sessions and claims)

| Variable | Default | Purpose |
|---|---|---|
| `CP_SESSION_TTL_SECONDS` | `300` | Default harness session TTL. |
| `CP_SESSION_TTL_MIN_SECONDS` | `10` | Lower bound of a requested session TTL. |
| `CP_SESSION_TTL_MAX_SECONDS` | `3600` | Upper bound of the session TTL. |
| `CP_CLAIM_TTL_SECONDS` | `300` | Default claim TTL. |
| `CP_CLAIM_TTL_MIN_SECONDS` | `10` | Lower bound of the claim TTL. |
| `CP_CLAIM_TTL_MAX_SECONDS` | `3600` | Upper bound of the claim TTL. Outside the bounds: `422 invalid_ttl`. |

### Idempotency

| Variable | Default | Purpose |
|---|---|---|
| `CP_IDEMPOTENCY_TTL_SECONDS` | `86400` | How long the response for an `Idempotency-Key` is kept. |
| `CP_IDEMPOTENCY_WAIT_TIMEOUT_SECONDS` | `10.0` | How long a concurrent duplicate waits for the first request to finish; after that, `409 idempotency_in_flight`. |
| `CP_IDEMPOTENCY_PENDING_TTL_SECONDS` | `60` | Lifetime of a record without a stored response (protection against a "stuck" key after a process crash). |

### Worker and outbox

| Variable | Default | Purpose |
|---|---|---|
| `CP_WORKER_POLL_INTERVAL_SECONDS` | `1.0` | Worker polling period. |
| `CP_OUTBOX_BATCH_SIZE` | `50` | Outbox batch size. |
| `CP_OUTBOX_MAX_ATTEMPTS` | `8` | Delivery attempts per outbox record. |
| `CP_OUTBOX_LOCK_TIMEOUT_SECONDS` | `60` | Outbox record lock timeout. |
| `CP_OUTBOX_BACKOFF_BASE_SECONDS` | `2.0` | Base of the exponential backoff. |
| `CP_OUTBOX_BACKOFF_MAX_SECONDS` | `300.0` | Backoff ceiling. |
| `CP_APPROVAL_OUTCOME_DEFER_SECONDS` | `15.0` | How long an approval outcome that met a live claim on its target waits before retrying (CP-ADR-0061). |
| `CP_JOURNAL_RETENTION_MIN_AGE_SECONDS` | `2592000` | Minimum age of a log event after which it can be archived or deleted. |

### Memory (context provider)

| Variable | Default | In the stack | Purpose |
|---|---|---|---|
| `CP_CONTEXT_PROVIDER` | `none` | `http` | `none`: the core is standalone; `http`: memory-service. |
| `CP_CONTEXT_BASE_URL` | `http://localhost:8077` | `http://memory-service:8077` | Memory address. |
| `CP_CONTEXT_API_KEY` | not set | `${MEMORY_API_KEY}` | Static Bearer for memory. |
| `CP_CONTEXT_AUTH` | `auto` | `${CP_CONTEXT_AUTH}` | `api_key`: static key; `iam`: the core service account (`CP_IAM_CLIENT_ID/SECRET`); `auto`: `iam` if the service account is configured, otherwise `api_key`. |
| `CP_CONTEXT_IAM_AUDIENCE` | `memory-service` | — | Token audience for memory. |
| `CP_CONTEXT_IAM_SCOPES` | `["memory:read","memory:write","memory:tenants","memory:service"]` | — | Token scopes for memory. |
| `CP_CONTEXT_NAMESPACE_PREFIX` | `tenant:` | — | Tenant memory namespace: `<prefix><tenant_id>`. |
| `CP_CONTEXT_TIMEOUT_SECONDS` | `3.0` | — | Timeout of the interactive `/context`. |
| `CP_CONTEXT_INGEST_TIMEOUT_SECONDS` | `15.0` | — | Timeout of batch observation writes. |
| `CP_CONTEXT_RECONCILE_TIMEOUT_SECONDS` | `60.0` | — | Timeout of snapshot reconciliation and pack administration. |
| `CP_CONTEXT_BATCH_SIZE` | `100` | — | Batch size of delivery to memory. |
| `CP_CONTEXT_TENANT_BATCH_SIZE` | `100` | — | Batch per tenant per cycle. |
| `CP_CONTEXT_MAX_TENANTS_PER_CYCLE` | `20` | — | How many tenants are served per cycle. |
| `CP_CONTEXT_POLL_INTERVAL_SECONDS` | `1.0` | — | context-adapter period. |
| `CP_CONTEXT_RETRY_BACKOFF_BASE_SECONDS` | `1.0` | — | Base of the retry backoff. |
| `CP_CONTEXT_RETRY_BACKOFF_MAX_SECONDS` | `60.0` | — | Backoff ceiling. |
| `CP_CONTEXT_MAX_TOKENS_LIMIT` | `16000` | — | Server ceiling of the ContextPack budget. |
| `CP_CONTEXT_DEFAULT_MAX_TOKENS` | `8000` | — | Default ContextPack budget. |

### IAM

| Variable | Default | In the stack | Purpose |
|---|---|---|---|
| `CP_IAM_ENABLED` | `false` | `true` (api) | Accept IAM tokens. |
| `CP_IAM_ISSUER` | `""` | `${TAIMEN_PUBLIC_URL}/iam` | Exact `iss` of tokens. |
| `CP_IAM_JWKS_URL` | `""` | `http://iam-service:8010/.well-known/jwks.json` | IAM JWKS (internal address). |
| `CP_IAM_AUDIENCE` | `control-plane` | `control-plane` | Expected `aud`. |
| `CP_IAM_LEEWAY_SECONDS` | `5.0` | — | Clock skew tolerance. |
| `CP_IAM_JWKS_REFRESH_AFTER_SECONDS` | `300.0` | — | When to reread JWKS. |
| `CP_IAM_JWKS_STALE_AFTER_SECONDS` | `3600.0` | — | After JWKS reaches this age without a refresh, verification is unavailable (`verification_unavailable`). |
| `CP_IAM_JWKS_MIN_REFRESH_INTERVAL_SECONDS` | `10.0` | — | At most one JWKS reread per interval. |
| `CP_IAM_REQUEST_TIMEOUT_SECONDS` | `3.0` | — | Timeout of requests to IAM. |
| `CP_IAM_BINDING_CACHE_TTL_SECONDS` | `30.0` | — | How long a binding projection is reused. |
| `CP_IAM_BINDING_STALE_AFTER_SECONDS` | `120.0` | — | Age after which an unverified record closes sign-in. |
| `CP_LEGACY_API_KEYS_ENABLED` | `true` | `${CP_LEGACY_API_KEYS_ENABLED:-false}` (api) | Legacy `cp_…` keys as a credential. |
| `CP_BREAK_GLASS_ENABLED` | `true` | — | Break-glass `cp_bg…` keys from the host shell (CP-ADR-0065). |
| `CP_BREAK_GLASS_MAX_TTL_SECONDS` | `14400` | — | Maximum lifetime of a break-glass key. |
| `CP_IAM_BASE_URL` | `http://localhost:8010` | `http://iam-service:8010` | IAM address for client credentials exchange. |
| `CP_IAM_CLIENT_ID` | `""` | from `secrets/control-plane-iam.env` | Client id of the core service account. |
| `CP_IAM_CLIENT_SECRET` | not set | from `secrets/control-plane-iam.env` | Secret of the core service account. |
| `CP_IAM_CLIENT_SCOPES` | `["entitlement:check-on-behalf"]` | — | Service account scopes for entitlement. |

### Entitlement


| Variable | Default | In the stack | Purpose |
|---|---|---|---|
| `CP_ENTITLEMENT_ENABLED` | `false` | — | Check licenses. When off, the audit trail shows the decision source `disabled`. |
| `CP_ENTITLEMENT_BASE_URL` | `http://localhost:8020` | — | Licensing service address. |
| `CP_ENTITLEMENT_PRODUCT` | `control-plane` | — | Product in the license catalog. |
| `CP_ENTITLEMENT_DEFAULT_FEATURE` | `api` | — | Feature, if it cannot be derived from the path (`/api/v1/<feature>/…`). |
| `CP_ENTITLEMENT_CACHE_TTL_SECONDS` | `30.0` | — | Decision cache. |
| `CP_ENTITLEMENT_DEGRADED_MAX_AGE_SECONDS` | `300.0` | — | Maximum cache age while the service is unavailable. |
| `CP_ENTITLEMENT_TIMEOUT_SECONDS` | `3.0` | — | Request timeout. |

### Policy Decision Point

| Variable | Default | In the stack | Purpose |
|---|---|---|---|
| `CP_AUTHZ_MODE` | `local` | `${CP_AUTHZ_MODE}` | `local`: local permissions only; `shadow`: the local check decides, the external PDP is queried in parallel, and discrepancies are logged; `policy`: the PDP decides for credentials with an IAM subject. |
| `CP_POLICY_BASE_URL` | `http://localhost:8030` | — | PDP address. |
| `CP_POLICY_SCOPES` | `["policy:check","policy:check-on-behalf"]` | — | Token scopes. |
| `CP_POLICY_TIMEOUT_SECONDS` | `3.0` | — | Timeout. |
| `CP_POLICY_CACHE_TTL_SECONDS` | `5.0` | — | Decision cache. |

!!! tip "Lists in `CP_` variables are JSON"
    pydantic-settings parses list fields (`CP_CORS_ORIGINS`,
    `CP_KNOWLEDGE_PACK_ADMINS`, `CP_CONTEXT_IAM_SCOPES`, and others) as JSON:
    `CP_CORS_ORIGINS='["https://platform.example.com"]'`. A comma-separated
    string causes a startup error.

## iam-service (`IAM_`)

| Variable | Default | In the stack | Purpose |
|---|---|---|---|
| `IAM_DATABASE_URL` | `postgresql+psycopg://iam:iam@localhost:5435/iam` | `…@iam-db:5432/iam` | IAM database. |
| `IAM_BOOTSTRAP_TOKEN` | `""` | `${IAM_BOOTSTRAP_TOKEN}` | Token for the bootstrap endpoints (`X-IAM-Bootstrap-Token`). |
| `IAM_ISSUER` | `http://localhost:8010` | `${TAIMEN_PUBLIC_URL}/iam` | Issuer of issued tokens. |
| `IAM_TOKEN_TTL_SECONDS` | `300` | — | Access token lifetime. |
| `IAM_SIGNING_PRIVATE_KEY` | `""` | — | Private signing key (PEM as a string); takes precedence over the file. |
| `IAM_SIGNING_PRIVATE_KEY_FILE` | `""` | `/run/secrets/iam_signing_key` | Private key file. |
| `IAM_SIGNING_KEY_ID` | `local-dev` | `${IAM_SIGNING_KEY_ID}` | `kid` in JWKS. |
| `IAM_CREATE_SCHEMA_ON_STARTUP` | `false` | — | Create the database schema at startup (in the stack, `alembic upgrade head` creates the schema). |
| `IAM_PAT_DEFAULT_TTL_SECONDS` | `2592000` (30 days) | — | PAT lifetime if `expiresInSeconds` is not passed. |
| `IAM_PAT_MAX_TTL_SECONDS` | `31536000` (365 days) | — | Ceiling of the PAT lifetime; above it, `422 expiry_too_long`. |
| `IAM_PAT_MAX_AUTHENTICATION_AGE_SECONDS` | `300` | — | Maximum age of a human's authentication context for PAT issuance; older gives `403 authentication_context_expired`. |
| `IAM_LEGACY_CREDENTIAL_MAX_TTL_SECONDS` | `7776000` (90 days) | — | Compatibility window for migrated legacy keys; above it, `422 compatibility_window_too_long`. |
| `IAM_SCIM_AUDIENCE` | `iam-scim` | — | Audience of the SCIM client. |
| `IAM_SCIM_SCOPE` | `scim:write` | — | Scope of the SCIM client. |
| `IAM_SCIM_MAX_PAGE_SIZE` | `200` | — | SCIM page limit. |
| `IAM_CHANNEL_AUDIENCE` | `iam` | — | The audience of IAM itself for channels: the human (link code) and the channel adapter present tokens for it. |
| `IAM_CHANNEL_SCOPE` | `iam:channel-links` | — | Scope of the channel adapter (link confirmation, button-press exchange). |
| `IAM_CHANNEL_LINK_CODE_TTL_SECONDS` | `600` | — | Lifetime of a channel link code. |
| `IAM_CHANNEL_LINK_MAX_AUTHENTICATION_AGE_SECONDS` | `300` | — | Maximum age of the sign-in of the human requesting a code; older gives `403 authentication_context_expired`. |
| `IAM_CHANNEL_ASSERTION_AUDIENCE` | `control-plane` | — | Audience of the token issued for a button press in a channel. |
| `IAM_CHANNEL_ASSERTION_SCOPE` | `control-plane:decide` | — | The only scope of such a token. |
| `IAM_CHANNEL_ASSERTION_TTL_SECONDS` | `60` | — | Lifetime of a button-press token (no longer than `IAM_TOKEN_TTL_SECONDS`). |
| `IAM_CHANNEL_LINK_INTENT_LIMIT`, `IAM_CHANNEL_LINK_INTENT_WINDOW_SECONDS` | `5`, `600` | — | Link codes per human per window. |
| `IAM_CHANNEL_CONFIRM_FAILURE_LIMIT`, `IAM_CHANNEL_CONFIRM_FAILURE_WINDOW_SECONDS` | `10`, `600` | — | Failed code confirmations per adapter per window. |
| `IAM_CHANNEL_ASSERTION_LIMIT`, `IAM_CHANNEL_ASSERTION_WINDOW_SECONDS` | `10`, `60` | — | Button-press exchanges per link and denials per adapter per window. |

## memory-service (`CB_`)

The "In the stack" column is the value from `deploy/local/compose.yml`.

### Storage and HTTP

| Variable | Default | In the stack | Purpose |
|---|---|---|---|
| `CB_DATABASE_URL` | `""` → built from `POSTGRES_USER/PASSWORD/HOST/PORT/DB` | `postgresql://memory:…@memory-db:5432/company_brain` | Database (PostgreSQL with pgvector; `pg_trgm` recommended). |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB` | `brain`, `brain`, `localhost`, `5432`, `company_brain` | — | Used only if `CB_DATABASE_URL` is empty. |
| `CB_GRAPH_NAME` | `company_brain` | — | PostgreSQL schema with the graph tables `graph_nodes`, `graph_edges`. |
| `CB_CHUNKS_TABLE` | `chunks` | — | Chunks table. |
| `CB_DB_JIT` | `false` | — | PostgreSQL JIT for the service's connections; enable only for a measurement. |
| `CB_DEFAULT_NAMESPACE` | `nexus` | `main` | Namespace of requests without a scope. |
| `CB_PROJECT_VALUES` | `""` | — | CSV of allowed project slugs; empty means project nodes are not created. |
| `CB_SERVER_HOST` | `127.0.0.1` | — | HTTP server address when started through the built-in entry point (`uvicorn.run`). |
| `CB_SERVER_PORT` | `8077` | — | HTTP server port when started through the built-in entry point. |
| `CB_SERVER_API_KEY` | `""` | `${MEMORY_API_KEY}` | Static Bearer key; if set, authentication is required. |
| `CB_API_KEYS` | `""` | — | JSON registry of keys with prefix grants on namespaces (MEM-ADR-017). |
| `CB_CORE_ONLY` | `false` | — | Restrict core routes (reconcile, packages, `namespaces/{ns}/kinds`) to the core identity. |
| `CB_CORE_IDENTITIES` | `""` | — | Comma-separated core identity labels; setting it enables the restriction. |
| `CB_QUERY_SYNTHESIZE_DEFAULT` | `false` | — | Synthesize an LLM answer in `/query` by default. |
| `CB_VAULT_PATH` | `""` | — | Path to the notes vault for the ingest CLI. |
| `CB_CACHE_DIR` | `""` | — | Ingest cache; empty means off. |
| `CB_EXTRACT_ENTITIES` | `false` | — | Extract people and organizations from note bodies with an LLM. |
| `CB_RUN_AUDIT_ENABLED` | `true` | — | Run lifecycle events into the graph trace. |

### Embeddings, LLM, rerank

| Variable | Default | In the stack | Purpose |
|---|---|---|---|
| `CB_EMBEDDING_PROVIDER` | `openai` | `${MEMORY_EMBEDDING_PROVIDER:-fake}` | `openai` or `fake`. |
| `CB_EMBEDDING_BASE_URL` | URL of the OpenAI-compatible gateway from code | `${LLM_BASE_URL}` | Embeddings base URL. |
| `CB_EMBEDDING_API_KEY` | `""` | `${LLM_API_KEY}` | Key. |
| `CB_EMBEDDING_MODEL` | `text-embedding-3-small` | `${MEMORY_EMBEDDING_MODEL}` | Model. |
| `CB_EMBEDDING_DIM` | `1536` | `1536` | Vector dimension. |
| `CB_EMBEDDING_TIMEOUT` | `25.0` | `60` | Call timeout, seconds. |
| `CB_LLM_PROVIDER` | `openai` | `${MEMORY_LLM_PROVIDER:-echo}` | `openai` or `echo`. |
| `CB_LLM_BASE_URL` | URL from code | `${LLM_BASE_URL}` | LLM base URL. |
| `CB_LLM_API_KEY` | `""` | `${LLM_API_KEY}` | Key. |
| `CB_LLM_MODEL` | `gpt-4o-mini` | `${LLM_MODEL}` | Model. |
| `CB_RERANK_ENABLED` | `false` | `${MEMORY_RERANK_ENABLED}` | Rerank candidates. |
| `CB_RERANK_PROVIDER` | `llm` | — | Rerank provider. |
| `CB_RERANK_POOL` | `20` | `20` | Pool size before reranking. |
| `CB_RERANK_MODEL` | `""` (→ `CB_LLM_MODEL`) | — | Rerank model. |

### IAM, policy, PII

| Variable | Default | In the stack | Purpose |
|---|---|---|---|
| `CB_IAM_ENABLED` | `false` | `${MEMORY_IAM_ENABLED:-true}` | Accept IAM tokens for the `memory-service` audience. |
| `CB_IAM_ISSUER` | `""` | `${TAIMEN_PUBLIC_URL}/iam` | Exact `iss`. |
| `CB_IAM_JWKS_URL` | `""` | `http://iam-service:8010/.well-known/jwks.json` | JWKS. |
| `CB_IAM_AUDIENCE` | `memory-service` | `memory-service` | Exact `aud`. |
| `CB_IAM_LEEWAY_SECONDS` | `5.0` | — | Clock tolerance. |
| `CB_POLICY_ENABLED` | `false` | `${MEMORY_POLICY_ENABLED}` | Visibility per principal through an external PDP. |
| `CB_POLICY_URL` | `http://localhost:8030` | — | PDP address. |
| `CB_POLICY_TIMEOUT_SECONDS` | `3.0` | — | Timeout. |
| `CB_POLICY_CACHE_TTL_SECONDS` | `5.0` | — | Cache. |
| `CB_IAM_BASE_URL` | `""` | `http://iam-service:8010` | IAM for the service's own client credentials. |
| `CB_IAM_CLIENT_ID`, `CB_IAM_CLIENT_SECRET` | `""` | from `secrets/memory-service-iam.env` | The memory service account (to call the external PDP). |
| `CB_PII_PROTECTION` | `false` | `true` | PII protection: without full clearance, output is masked. |
| `CB_SERVER_API_KEYS_PII` | `""` | `""` | Comma-separated keys with full PII clearance. |

### Console, demo showcase, Context Compiler

| Variable | Default | In the stack | Purpose |
|---|---|---|---|
| `CB_CONSOLE_ENABLED` | `false` | `${MEMORY_CONSOLE_ENABLED}` | Memory Console (`/console`). It has no authentication of its own: protect it with the proxy. |
| `CB_CONSOLE_NAMESPACES` | `""` (→ `CB_DEFAULT_NAMESPACE`) | `""` | CSV allowlist of knowledge bases for the Console. |
| `CB_DEMO_PUBLIC_ENABLED` | `false` | — | The public `/demo` showcase. Do not enable it on customer data. |
| `CB_DEMO_NAMESPACE` | `demo` | — | The only KB of the showcase. |
| `CB_DEMO_RATE_LIMIT` | `30` | — | Requests per minute per IP to `/demo/api/*`; `0` means no limit. |
| `CB_DEMO_SEARCH_K` | `5` | — | Showcase top-k. |
| `CB_DEMO_BRAND_NAME`, `CB_DEMO_BRAND_TAGLINE`, `CB_DEMO_CTA_URL`, `CB_DEMO_DOMAIN` | neutral values | — | Showcase branding. |
| `CB_DEMO_RERANK` | `true` | — | Rerank in showcase search. |
| `CB_DEMO_MIN_CONFIDENCE` | `0.3` | — | `rerank_score` threshold for showcase cards. |
| `CB_OBSERVATIONS_TABLE` | `observations` | — | Observations table. |
| `CB_CONTEXT_TRACES_TABLE` | `context_traces` | — | Context assembly traces table. |
| `CB_OBSERVATIONS_EMBED` | `false` | — | Embed observations at ingest. |
| `CB_OBSERVATIONS_MAX_BATCH` | `500` | — | Observation batch limit; above it, `413`. |
| `CB_CONTEXT_DEFAULT_MAX_TOKENS` | `8000` | — | Default ContextPack budget. |
| `CB_CONTEXT_CHARS_PER_TOKEN` | `3.0` | — | Estimated characters per token. |
| `CB_CONTEXT_MAX_DEPTH` | `2` | — | Graph expansion depth. |
| `CB_CONTEXT_MAX_NODES` | `60` | — | Node limit. |
| `CB_CONTEXT_MAX_EDGES` | `120` | — | Edge limit. |
| `CB_DOMAIN_PACKS_TABLE` | `domain_packs` | — | Registry of kind domain packages. |
| `CB_NAMESPACE_SETTINGS_TABLE` | `namespace_settings` | — | Namespace kind settings. |
| `CB_SNAPSHOTS_TABLE` | `source_snapshots` | — | Source snapshot log. |
| `CB_RECONCILE_MAX_ITEMS` | `20000` | — | Limit of entities and facts in one reconcile snapshot. |

## notification-service (`NS_`) {#notification-service}

Profile `notify`. See [Notifications](../notifications/index.md) and
[Telegram](../notifications/telegram.md).

| Variable | Default | In the stack | Purpose |
|---|---|---|---|
| `NS_HOST`, `NS_PORT` | `0.0.0.0`, `8000` | — | HTTP address and port (read by the `notification-service` entry point). |
| `NS_DATABASE_URL` | `postgresql+psycopg://notify:notify@localhost:5432/notify` | `…@notification-db:5432/notify` | Database. |
| `NS_IAM_URL` | `""` | `http://iam-service:8010` | IAM: client credentials of the service account. |
| `NS_IAM_ISSUER` | `""` | `${TAIMEN_PUBLIC_URL}/iam` | Token issuer; without it and JWKS, all `/api/v1` routes return `503`. |
| `NS_IAM_JWKS_URL` | `""` (otherwise `<NS_IAM_URL>/.well-known/jwks.json`) | `http://iam-service:8010/.well-known/jwks.json` | JWKS. |
| `NS_AUDIENCE` | `notification-service` | `notification-service` | Own audience. |
| `NS_CONTROL_PLANE_URL` | `""` | `http://control-plane-api:8000` | The core: recipient directory, events, decisions. |
| `NS_SERVICE_CLIENT_ID`, `NS_SERVICE_CLIENT_SECRET` | `""` | from `secrets/notification-iam.env` | The service's service account. |
| `NS_EVENTS_ENABLED` | `true` | — | Consumer of core events. |
| `NS_EVENTS_START` | `latest` | — | Where to start on first launch: `latest` or `earliest`. |
| `NS_EVENTS_WORKSPACE_ID` | `""` | — | Workspace subtree; empty means the whole tenant. |
| `NS_EVENTS_POLL_SECONDS` | `30.0` | — | Log polling period (WebSocket wakes it earlier). |
| `NS_WORKER_ENABLED` | `true` | — | Delivery worker in the API process. |
| `NS_WORKER_POLL_SECONDS` | `1.0` | — | Delivery queue polling period. |
| `NS_WORKER_BATCH_SIZE` | `50` | — | Deliveries per pass. |
| `NS_WORKER_LEASE_SECONDS` | `120.0` | — | Delivery lease; sending is limited to half the lease. |
| `NS_DELIVERY_MAX_ATTEMPTS` | `8` | — | Attempts per delivery. |
| `NS_DELIVERY_BACKOFF_SECONDS`, `NS_DELIVERY_BACKOFF_MAX_SECONDS` | `5.0`, `3600.0` | — | Exponential pause between attempts and its ceiling. |
| `NS_EMAIL_MODE` | `log` | — | `smtp`, `log` (log only), or `disabled` (no channel). |
| `NS_EMAIL_FROM` | `notifications@localhost` | `${NOTIFY_EMAIL_FROM}` | Email sender. |
| `NS_SMTP_HOST`, `NS_SMTP_PORT` | `localhost`, `587` | `${NOTIFY_SMTP_HOST}`, `${NOTIFY_SMTP_PORT}` | SMTP server. |
| `NS_SMTP_STARTTLS` | `true` | — | STARTTLS. |
| `NS_SMTP_USERNAME`, `NS_SMTP_PASSWORD` | `""` | — | SMTP credentials. |
| `NS_SMTP_TIMEOUT_SECONDS` | `10.0` | — | SMTP timeout. |
| `NS_TELEGRAM_BOT_TOKEN` | `""` | from `secrets/notification-telegram.env` | Bot token; without it, there is no `telegram` channel. |
| `NS_TELEGRAM_WEBHOOK_SECRET` | `""` | from `secrets/notification-telegram.env` | Webhook secret (`secret_token` in `setWebhook`). |
| `NS_TELEGRAM_BOT_USERNAME` | `""` | from `secrets/notification-telegram.env` | Bot name without `@`: commands and group link URLs. |
| `NS_TELEGRAM_API_URL` | `https://api.telegram.org` | — | Bot API. |
| `NS_TELEGRAM_TIMEOUT_SECONDS` | `10.0` | — | Bot API timeout. |
| `NS_CHANNEL_GROUP_CODE_TTL_SECONDS` | `600` | — | Lifetime of a group link code. |
| `NS_IAM_CHANNEL_AUDIENCE`, `NS_IAM_CHANNEL_SCOPE` | `iam`, `iam:channel-links` | — | The service as a channel adapter in IAM. |
| `NS_INBOX_POLL_SECONDS` | `5.0` | — | How often an idle SSE stream checks the database. |
| `NS_INBOX_KEEPALIVE_SECONDS` | `15.0` | — | SSE stream keep-alive. |

## fleet-controller (`FLEET_`) {#fleet-controller}

The `fleet` profile. The variables are read directly from the environment
(`fleet_controller/wiring.py`); `deploy/local/compose.yml` sets the values, and the client
credentials come from `secrets/fleet-iam.env`.

| Variable | In `deploy/local/compose.yml` | Default in code | Purpose |
|---|---|---|---|
| `FLEET_DATA_DIR` | `/data` | `/data` | Directory of the `fleet.sqlite` SQLite database (volume `fleet_data`). |
| `FLEET_CONTROL_PLANE_URL` | `http://control-plane-api:8000` | — | Control Plane inside the network. |
| `FLEET_IAM_URL` | `http://iam-service:8010` | — | IAM inside the network: client credentials, agents, and their PATs (`iam:agents`). |
| `FLEET_IAM_ISSUER` | `${TAIMEN_PUBLIC_URL}/iam` | — (required) | Public IAM issuer: agent identities are bound with it, and administrative tokens are verified against it. |
| `FLEET_IAM_TENANT` | `${IAM_TENANT_ID:-}` | — | IAM tenant of the agents. |
| `FLEET_JWKS_URL` | `http://iam-service:8010/.well-known/jwks.json` | — (required) | JWKS for verifying administrative tokens. |
| `FLEET_CLIENT_ID`, `FLEET_CLIENT_SECRET` | from `secrets/fleet-iam.env` | empty | The controller's service account. Without them, every route except `/healthz` returns `503 not_configured`. |
| `FLEET_AUDIENCE` | — | `fleet` | Audience of administrative tokens (`fleet:read`, `fleet:admin`). |
| `FLEET_TOKEN_AUDIENCES` | see `deploy/local/compose.yml` | `control-plane` | Audiences an agent PAT may receive (space-separated); beyond `control-plane`, only those the agent requests in `skills.audiences` or `identity.iam.audiences`. |
| `FLEET_TOKEN_SCOPES` | see `deploy/local/compose.yml` | `control-plane:read control-plane:write` | Scope ceiling of agent PATs (space-separated). An agent gets only the scopes of the audiences issued to it, and, when `identity.iam.scopeCeiling` is declared, the intersection with it; a privileged scope (`iam:…`) goes only to the agent that declared it; a scope whose prefix does not match its audience is written as `audience=scope`. |
| `FLEET_TOKEN_TTL_SECONDS` | — | `604800` (7 days) | Agent PAT lifetime; no more than `IAM_AGENT_PAT_MAX_TTL_SECONDS`, otherwise IAM responds `422 expiry_too_long`. A new PAT is issued 2 days before expiry and recreates the agent container. |

The `fleet-node` node reads no prefixed variables: its whole configuration is the
`node.yaml` file, in which `${NAME}` is substituted from the node process environment (see
[Nodes and fleet](../runner/fleet.md#node-yaml)).


## Runner agent and Control Plane clients {#runner-and-clients}

Processes outside the platform compose: the `control-plane-agent` daemon, the
OpenCode adapter, the `control-plane` CLI, the `control-plane-mcp` MCP server,
and the `control_plane_client` library. Variables are read directly from the
environment. The daemon of an agent described by the `Agent` kind takes the agent
settings from its revision, and the host variables are set for it by the fleet node
(`agentEnv` and `executors.<kind>.env` in `node.yaml`); which variables apply in
which mode is described in [Executor configuration](../runner/configuration.md).

### Connection and identity

| Variable | Default | Purpose |
|---|---|---|
| `CONTROL_PLANE_SERVER` | — | Control Plane address (`https://platform.example.com`). Required for the daemon and the OpenCode adapter; the CLI and the MCP server use it if there is no `--server`, and then look for `.control-plane/config.json`. |
| `CONTROL_PLANE_IAM_URL` | — | IAM address (`https://platform.example.com/iam`). If not set, the client considers IAM not configured and falls back to a legacy key. |
| `CONTROL_PLANE_IAM_TENANT` | — | IAM tenant. A URL set without a tenant gives the `iam_tenant_required` error. |
| `CONTROL_PLANE_IAM_AUDIENCE` | `control-plane` | Audience of the PAT exchange. |
| `CONTROL_PLANE_IAM_SCOPES` | empty (= the whole PAT ceiling ∩ audience) | Space- or comma-separated scopes. In an env file, quote a space-separated value. |
| `IAM_PLATFORM_ACCESS_TOKEN` | — | PAT from the environment. Works only together with `IAM_CREDENTIAL_MODE`. |
| `IAM_CREDENTIAL_MODE` | — | `environment` or `ci`: allow a PAT from the variable. Without it, `iam_environment_mode_required`. |
| `IAM_PRINCIPAL` | — | Which principal this process is, if the machine's store has several credentials for the same issuer+tenant. If not set when there are several, `iam_credential_ambiguous`. |
| `IAM_NO_KEYCHAIN` | — | `1`: do not ask the macOS Keychain for the PAT. |
| `XDG_CONFIG_HOME` | `~/.config` | Base of the paths `iam/credentials.json` (PAT file, mode `600`) and `services/control-plane/credentials.json` (legacy keys). |
| `CONTROL_PLANE_API_KEY` | — | Legacy `cp_…` key (only if legacy keys are enabled on the server). |
| `CONTROL_PLANE_NO_KEYCHAIN` | — | `1`: do not look for a legacy key in the Keychain. |

!!! warning "Removed variables"
    `TAIMEN_API_KEY`, `TAIMEN_SERVER`, `TAIMEN_NO_KEYCHAIN`,
    `TAIMEN_AGENT_ADAPTER`, `TAIMEN_AGENT_WORKSPACE`, `TAIMEN_AGENT_POLL`
    are no longer read. The client recognizes them only to report the name of
    the replacement: `CONTROL_PLANE_*`.

### Executor daemon

| Variable | Default | Purpose |
|---|---|---|
| `CONTROL_PLANE_AGENT_CONFIG` | `auto` | Where the configuration comes from: `auto`: the agent revision if the principal is bound to an agent, otherwise the environment; `revision`: the revision only; `env`: the environment only. |
| `CONTROL_PLANE_AGENT_MIRRORS` | `<WORKTREE_ROOT>/.mirrors` | Directory of bare mirrors of the revision's repositories (revision mode). |
| `CONTROL_PLANE_AGENT_DRAIN_SECONDS` | — | Env mode: how long to wait for an in-flight run on `SIGTERM`; in revision mode, `placement.drainSeconds`. |
| `CONTROL_PLANE_AGENT_CONTROL_POLL_SECONDS` | `15` | How often the watchdog reads the run for a cancellation request (at least once every 30 s). |
| `CONTROL_PLANE_AGENT_STALL_WARN_SECONDS` | `600` | With no new actions: a `stall` checkpoint; `0` disables it. |
| `CONTROL_PLANE_AGENT_STALL_STOP_SECONDS` | `1800` | With no new actions: stop, run `no_progress`; `0` disables it. |
| `CONTROL_PLANE_AGENT_ACTION_MAX_SECONDS` | `3600` | How long an unfinished last action lives before the watchdog stops it. |
| `CONTROL_PLANE_AGENT_ADAPTER` | `echo` | Adapter: `echo`, `claude-code`, `codex` (env mode). |
| `CONTROL_PLANE_AGENT_WORKSPACE` | — | The Control Plane workspace to take tasks from. Without it there is no workspace filter: the daemon takes any task available to it, so set up a separate workspace for testing. |
| `CONTROL_PLANE_AGENT_PROJECT` | — | Restrict tasks to a project. |
| `CONTROL_PLANE_AGENT_SUBPROJECTS` | — | `1`: include subprojects. |
| `CONTROL_PLANE_AGENT_ONLY_ASSIGNED` | — | `1`: only tasks assigned to this principal. |
| `CONTROL_PLANE_AGENT_POLL` | `5` | Polling period, seconds. |
| `CONTROL_PLANE_AGENT_REPO` | — | The git repository (usually a bare mirror) that working copies are made from. Together with `…_WORKTREE_ROOT`, it enables the working copy pool. |
| `CONTROL_PLANE_AGENT_WORKTREE_ROOT` | — | Directory of working copies. |
| `CONTROL_PLANE_AGENT_BASE_REF` | `HEAD` | The revision the task branch is created from. |
| `CONTROL_PLANE_AGENT_KEEP_WORKSPACES` | — | `1`: do not delete the working copy after success. |
| `CONTROL_PLANE_AGENT_MAX_WORKSPACES` | `8` | Limit of working copies. |
| `CONTROL_PLANE_AGENT_PUSH_REMOTE` | `""` | Remote for publishing the task branch. Empty means the branch stays local. |
| `CONTROL_PLANE_AGENT_REPO_DIR` | `""` | Name of the repository directory inside the container working copy. |
| `CONTROL_PLANE_AGENT_NEIGHBOURS` | `""` | Neighboring repositories: comma-separated `name=path-to-mirror`. |
| `CONTROL_PLANE_AGENT_SUPERPROJECT` | — | Mirror of the superproject that pins the neighbors' revisions. |
| `CONTROL_PLANE_AGENT_SUPERPROJECT_REF` | `HEAD` | Superproject revision. |
| `CONTROL_PLANE_AGENT_SUPERPROJECT_REMOTE` | `""` | Superproject remote for fetch. |
| `CONTROL_PLANE_CONTEXT_BUDGET_CHARS` | `12000` | Budget of the "Task context" section in the prompt, in characters. |
| `CONTROL_PLANE_TRACE_TRANSCRIPT` | enabled | `0`/`false`/`no`/`off`: do not publish the `transcript` artifact. |
| `CONTROL_PLANE_TRACE_ACTIONS` | enabled | Do not write `tool.<name>` run actions. |
| `CONTROL_PLANE_TRACE_TOOL_RESULTS` | enabled | Do not store tool call results in the trace. |

### Skills in the daemon

| Variable | Default | Purpose |
|---|---|---|
| `CONTROL_PLANE_SKILLS_PROTOCOLS` | `local` if packages are set, otherwise none | Which protocols to execute: `local`, `http`, `mcp`. |
| `CONTROL_PLANE_SKILLS_LOCAL_PACKAGES` | — | Entrypoints or packages of local skills. |
| `CONTROL_PLANE_SKILLS_LOCAL_ISOLATION` | `process` | `process` or `thread`. |
| `CONTROL_PLANE_SKILLS_HTTP_ALLOWED_ORIGINS` | — | Comma-separated `scheme://host[:port]`; without them the `http` protocol does not start. |
| `CONTROL_PLANE_SKILLS_MCP_ALLOWED_ORIGINS` | — | The same for `mcp`; without them `mcp` works only with `stdio` servers. |
| `CONTROL_PLANE_SKILLS_MCP_SERVERS` | `{}` | JSON `{name: {command, args, env}}` for `stdio:<name>` endpoints. |
| `CONTROL_PLANE_SKILLS_PRIVATE_HOSTS` | — | Hosts of allowed origins that may resolve to non-public addresses. |
| `CONTROL_PLANE_SKILLS_ALLOWED_AUDIENCES` | — | IAM audiences a skill may get a token for (never `control-plane`, `iam`, or its own). |
| `CONTROL_PLANE_SKILLS_CONCURRENCY` | `1` | Concurrent invocations alongside Work; `0` means only when there is no Work. |

### Code agent adapters

| Variable | Default | Purpose |
|---|---|---|
| `CONTROL_PLANE_CLAUDE_BINARY` | `claude` | Claude Code executable. |
| `CONTROL_PLANE_CLAUDE_MODEL` | — | Model. |
| `CONTROL_PLANE_CLAUDE_PERMISSION_MODE` | `acceptEdits` | Claude Code permission mode. |
| `CONTROL_PLANE_CLAUDE_TIMEOUT` | `3600` | Run timeout, seconds. |
| `CONTROL_PLANE_CLAUDE_RESUME` | `1` | Resume sessions. |
| `CONTROL_PLANE_CLAUDE_MCP` | `1` | `1`: write `mcp.json` to the runtime directory and connect the Control Plane MCP server to Claude Code. |
| `CONTROL_PLANE_CLAUDE_LOGS` | `1` | `1`: session logs in `<runtime>/sessions`. |
| `CONTROL_PLANE_CLAUDE_RUNTIME_DIR` | `~/.claude-runner` | Adapter runtime directory. |
| `CONTROL_PLANE_CLAUDE_PROMPT_FILE` | — | A conventions file appended to every prompt. |
| `CLAUDE_CODE_OAUTH_TOKEN` | — | Claude Code subscription token (read by the `claude` CLI itself). |
| `CONTROL_PLANE_CODEX_BINARY` | `codex` | Codex executable. |
| `CONTROL_PLANE_CODEX_MODEL` | — | Model. |
| `CONTROL_PLANE_CODEX_SANDBOX` | `workspace-write` | Codex sandbox mode. |
| `CONTROL_PLANE_CODEX_TIMEOUT` | `3600` | Timeout. |
| `CONTROL_PLANE_CODEX_RESUME` | `1` | Resume sessions. |
| `CONTROL_PLANE_CODEX_LOGS` | `1` | `1`: session logs in `<runtime>/sessions`. |
| `CONTROL_PLANE_CODEX_RUNTIME_DIR` | `~/.codex-runner` | Runtime directory. |
| `CONTROL_PLANE_CODEX_CREDENTIAL_CLASS` | — | Credential class of the Codex adapter. |
| `OPENCODE_SERVER` | `http://127.0.0.1:4096` | OpenCode server (the `control-plane-opencode` adapter). |
| `OPENCODE_SERVER_PASSWORD` | — | OpenCode server password. |
| `OPENCODE_MODEL`, `OPENCODE_AGENT` | — | OpenCode model and agent. |
| `CP_LOG_LEVEL` | `INFO` | Log level of the OpenCode adapter. |

### MCP server

| Variable | Default | Purpose |
|---|---|---|
| `CONTROL_PLANE_HARNESS_TYPE` | `mcp-client` | Harness type when opening a session (`[a-z0-9][a-z0-9._-]{0,99}`), otherwise `invalid_harness_configuration`. |
| `CONTROL_PLANE_HARNESS_VERSION` | package version | Harness version. |
| `CONTROL_PLANE_HARNESS_CLIENT_NAME` | `control-plane-mcp` | Client name. |

## Other processes

| Process | Variables |
|---|---|
| skill-sdk (skill hosting) | `SKILL_SDK_IAM_ISSUER`, `SKILL_SDK_AUDIENCE`, `SKILL_SDK_JWKS_URL`: IAM token verification in the `http` and `mcp-http` modes (without them, only `--allow-anonymous`); `SKILL_LLM_BASE_URL`, `SKILL_LLM_API_KEY`, `SKILL_LLM_MODELS` (CSV): the LLM of the skill context. |
| Human Harness | `IAM_CREDENTIAL_MODE`, `IAM_PLATFORM_ACCESS_TOKEN`: the same environment PAT contract as the Control Plane client. |
| `deploy/bootstrap.py` | Reads from `.env`: `TAIMEN_PUBLIC_URL`, `COMPOSE_PROJECT_NAME`, `CP_HOST_PORT`, `IAM_HOST_PORT`, `IAM_TENANT_ID`, `CP_BOOTSTRAP_TOKEN`, `IAM_BOOTSTRAP_TOKEN`. |

## `secrets/*.env` files written by bootstrap

| File | Variables | Read by |
|---|---|---|
| `secrets/control-plane-iam.env` | `CP_IAM_CLIENT_ID`, `CP_IAM_CLIENT_SECRET` | `control-plane-api`, `control-plane-worker`, `context-adapter` |
| `secrets/notification-iam.env` | `NS_SERVICE_CLIENT_ID`, `NS_SERVICE_CLIENT_SECRET` | `notification-service` |
| `secrets/fleet-iam.env` | `FLEET_CLIENT_ID`, `FLEET_CLIENT_SECRET` | `fleet-controller` |

Bootstrap does not write the `secrets/notification-telegram.env` file
(`NS_TELEGRAM_BOT_TOKEN`, `NS_TELEGRAM_WEBHOOK_SECRET`,
`NS_TELEGRAM_BOT_USERNAME`): the operator fills it in; see
[Telegram](../notifications/telegram.md). Nor does bootstrap write the optional
`secrets/memory-service-iam.env` (`CB_IAM_CLIENT_ID`, `CB_IAM_CLIENT_SECRET`,
the memory service identity for calling an external PDP): it is added together
with an external PDP connection, which is not part of the delivery.

After the file appears, recreate the corresponding container
(`tools/compose up -d <service>`): `env_file` is read when the container is
created.

## Summary: all `deploy/local/compose.yml` and `.env.example` variables

A checklist for the tables above: every variable that `deploy/local/compose.yml`
interpolates or `.env.example` declares, with the services and profiles
where it is used. The "Described above" column shows whether the variable
has a row in the hand-written tables on this page; "**no**" is a reason to
add a description.

<!-- generated:env-summary -->
_This section is generated from code; do not edit it by hand._

Total variables: 148 (in `deploy/local/compose.yml`: 123, in `.env.example`: 110). Not described in the tables above: 7.

| Variable | Compose default | Services | Profiles | `.env.example` | Described above |
|---|---|---|---|---|---|
| `CADDYFILE` | `./deploy/caddy/Caddyfile.local` | caddy | edge | yes | yes |
| `COMPOSE_PROJECT_NAME` | `taimen` | (volumes) | — | yes | yes |
| `CP_AUTHZ_MODE` | `local` | context-adapter, control-plane-api, control-plane-worker | core | yes | yes |
| `CP_BOOTSTRAP_TOKEN` | — | control-plane-api | core | yes | yes |
| `CP_BUILD_CONTEXT` | `.` | control-plane-api | core | — | yes |
| `CP_CONTEXT_AUTH` | `auto` | context-adapter, control-plane-api, control-plane-worker | core | yes | yes |
| `CP_CONTEXT_TIMEOUT_SECONDS` | `3` | control-plane-api | core | — | yes |
| `CP_CORS_ORIGINS` | `[]` | control-plane-api | core | yes | yes |
| `CP_HOST_PORT` | `18000` | control-plane-api | core | yes | yes |
| `CP_KNOWLEDGE_PACK_ADMINS` | `[]` | control-plane-api | core | yes | yes |
| `CP_LEGACY_API_KEYS_ENABLED` | `false` | control-plane-api | core | yes | yes |
| `CP_MEM_LIMIT` | `512m` | control-plane-api | core | yes | yes |
| `CP_POSTGRES_PASSWORD` | — | context-adapter, control-plane-api, control-plane-db, control-plane-worker | core | yes | yes |
| `CP_S3_ACCESS_KEY_ID` | — | context-adapter, control-plane-api, control-plane-worker, minio-bootstrap | core | yes | yes |
| `CP_S3_BUCKET` | `artifacts` | context-adapter, control-plane-api, control-plane-worker, minio-bootstrap | core | yes | yes |
| `CP_S3_ENDPOINT_URL` | `http://minio:9000` | context-adapter, control-plane-api, control-plane-worker | core | yes | yes |
| `CP_S3_REGION` | `us-east-1` | context-adapter, control-plane-api, control-plane-worker | core | yes | yes |
| `CP_S3_SECRET_ACCESS_KEY` | — | context-adapter, control-plane-api, control-plane-worker, minio-bootstrap | core | yes | yes |
| `CP_TIMEZONE` | — | — | — | yes | yes |
| `CP_WORKER_MEM_LIMIT` | `256m` | context-adapter, control-plane-worker | core | — | yes |
| `EDGE_HTTPS_PORT` | `443` | caddy | edge | yes | yes |
| `EDGE_HTTP_PORT` | `80` | caddy | edge | yes | yes |
| `FLEET_BUILD_CONTEXT` | `.` | fleet-controller | fleet | — | yes |
| `FLEET_MEM_LIMIT` | `128m` | fleet-controller | fleet | yes | yes |
| `HARNESS_APP_NAME` | `Human Harness` | harness-launcher | harness | — | yes |
| `HARNESS_CONTROL_NETWORK` | `${COMPOSE_PROJECT_NAME:-taimen` | (networks) | — | — | yes |
| `HARNESS_COOKIE_SECRET_FILE` | `./secrets/harness/cookie-secret` | (secrets) | — | — | yes |
| `HARNESS_CPUS` | `1` | harness-launcher | harness | — | yes |
| `HARNESS_IDLE_MINUTES` | `30` | harness-launcher | harness | — | yes |
| `HARNESS_MEM_LIMIT_MB` | `1536` | harness-launcher | harness | — | yes |
| `HARNESS_PEOPLE_NETWORK` | `${COMPOSE_PROJECT_NAME:-taimen` | (networks), harness-launcher | harness | — | yes |
| `HARNESS_PIDS_LIMIT` | `512` | harness-launcher | harness | — | yes |
| `IAM_BOOTSTRAP_TOKEN` | — | iam-service | core | yes | yes |
| `IAM_BUILD_CONTEXT` | `./services/iam-service` | iam-service | core | — | yes |
| `IAM_HOST_PORT` | `18010` | iam-service | core | yes | yes |
| `IAM_MEM_LIMIT` | `256m` | iam-service | core | — | yes |
| `IAM_POSTGRES_PASSWORD` | — | iam-db, iam-service | core | yes | yes |
| `IAM_SIGNING_KEY_FILE` | `./secrets/iam-signing.pem` | (secrets) | — | yes | yes |
| `IAM_SIGNING_KEY_ID` | `local-dev` | iam-service | core | yes | yes |
| `IAM_TENANT_ID` | empty | console, fleet-controller, harness-launcher | core, fleet, harness | yes | yes |
| `KEYCLOAK_ADMIN` | `admin` | keycloak | idp | yes | yes |
| `KEYCLOAK_ADMIN_PASSWORD` | — | keycloak | idp | yes | yes |
| `KEYCLOAK_DB_PASSWORD` | — | keycloak, keycloak-db | idp | yes | yes |
| `KEYCLOAK_HOSTNAME_STRICT` | `true` | keycloak | idp | yes | yes |
| `KEYCLOAK_HOST_PORT` | `18081` | keycloak | idp | yes | yes |
| `KEYCLOAK_IMAGE` | `quay.io/keycloak/keycloak:26.5.2` | keycloak | idp | yes | **no** |
| `KEYCLOAK_MEM_LIMIT` | `768m` | keycloak | idp | yes | yes |
| `LOG_LEVEL` | `INFO` | context-adapter, control-plane-api, control-plane-worker | core | yes | yes |
| `LOG_RENDERER` | — | — | — | yes | yes |
| `MEMORY_BUILD_CONTEXT` | `.` | memory-db, memory-service | core | — | yes |
| `MEMORY_CONSOLE_ENABLED` | `false` | memory-service | core | yes | yes |
| `MEMORY_DB_MEM_LIMIT` | `512m` | memory-db | core | — | yes |
| `MEMORY_EMBEDDING_MODEL` | `text-embedding-3-small` | memory-service | core | — | yes |
| `MEMORY_EMBEDDING_PROVIDER` | `fake` | memory-service | core | yes | yes |
| `MEMORY_HOST_PORT` | `18001` | memory-service | core | yes | yes |
| `MEMORY_IAM_ENABLED` | `true` | memory-service | core | yes | yes |
| `MEMORY_LLM_PROVIDER` | `echo` | memory-service | core | yes | yes |
| `MEMORY_MEM_LIMIT` | `512m` | memory-service | core | — | yes |
| `MEMORY_POLICY_ENABLED` | `false` | memory-service | core | yes | yes |
| `MEMORY_POSTGRES_PASSWORD` | — | memory-db, memory-service | core | yes | yes |
| `MEMORY_RERANK_ENABLED` | `false` | memory-service | core | yes | yes |
| `MINIO_MEM_LIMIT` | `256m` | minio | core | — | yes |
| `NOTIFICATION_SERVICE_URL` | — | — | — | yes | yes |
| `NOTIFY_BUILD_CONTEXT` | `.` | notification-service | notify | — | yes |
| `NOTIFY_DB_MEM_LIMIT` | `128m` | notification-db | notify | — | yes |
| `NOTIFY_EMAIL_FROM` | `notifications@localhost` | notification-service | notify | — | yes |
| `NOTIFY_HARNESS_LAUNCHER_URL` | `http://harness-launcher:8080/harness` | notification-service | notify | — | yes |
| `NOTIFY_HOST_PORT` | `18045` | notification-service | notify | — | yes |
| `NOTIFY_MEM_LIMIT` | `256m` | notification-service | notify | — | yes |
| `NOTIFY_POSTGRES_PASSWORD` | — | notification-db, notification-service | notify | yes | yes |
| `NOTIFY_SMTP_HOST` | `localhost` | notification-service | notify | — | yes |
| `NOTIFY_SMTP_PORT` | `587` | notification-service | notify | — | yes |
| `PG_MEM_LIMIT` | `256m` | control-plane-db, iam-db, keycloak-db | core, idp | — | yes |
| `RUNTIME_CONSOLE_COOKIE_SECRET_FILE` | `./secrets/runtime-console-cookie-secret` | (secrets) | — | yes | yes |
| `RUNTIME_CONSOLE_CP_SCOPES` | `control-plane:read control-plane:write` | console | core | yes | yes |
| `RUNTIME_CONSOLE_DEFAULT_LOCALE` | `en` | console | core | yes | yes |
| `RUNTIME_CONSOLE_IDENTITY_PROVIDER` | `keycloak` | console | core | yes | yes |
| `RUNTIME_CONSOLE_IDP_ADMIN` | `off` | console | core | yes | **no** |
| `RUNTIME_CONSOLE_KEYCLOAK_URL` | empty | console | core | yes | **no** |
| `RUNTIME_CONSOLE_LOCALES` | `en,ru` | console | core | yes | yes |
| `RUNTIME_CONSOLE_OIDC_CLIENT_ID` | `runtime-console` | console | core | yes | yes |
| `RUNTIME_CONSOLE_OIDC_ISSUER` | `${TAIMEN_PUBLIC_URL` | console | core | yes | yes |
| `RUNTIME_CONSOLE_OIDC_SCOPES` | `openid profile email` | console | core | yes | yes |
| `RUNTIME_CONSOLE_OIDC_SECRET_FILE` | `./secrets/runtime-console-oidc-secret` | (secrets) | — | yes | yes |
| `RUNTIME_CONSOLE_ORG_NAME` | empty | console | core | yes | yes |
| `RUNTIME_CONSOLE_PEOPLE_SECRET_FILE` | `./secrets/runtime-console-people-secret` | (secrets) | — | — | **no** |
| `RUNTIME_CONSOLE_PRODUCT_NAME` | `Console` | console | core | yes | yes |
| `RUNTIME_CONSOLE_SESSION_TTL_HOURS` | `12` | console | core | yes | yes |
| `S3_ACCESS_KEY_ID` | — | minio, minio-bootstrap | core | yes | yes |
| `S3_SECRET_ACCESS_KEY` | — | minio, minio-bootstrap | core | yes | yes |
| `TAIMEN_NETWORK` | `taimen_default` | (networks) | — | yes | yes |
| `TAIMEN_PUBLIC_HOST` | `taimen.localhost` | caddy, harness-launcher | edge, harness | yes | yes |
| `TAIMEN_PUBLIC_URL` | — | console, control-plane-api, dex-render, fleet-controller, harness-launcher, iam-service, keycloak, memory-service, notification-service, realm-render | core, fleet, harness, idp, idp-dex, notify | yes | yes |
| `TASK_URL_BASE` | — | — | — | yes | yes |
| `VOLUME_CADDY_CONFIG` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | yes | yes |
| `VOLUME_CADDY_DATA` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | yes | yes |
| `VOLUME_CONSOLE_SESSIONS` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | — | **no** |
| `VOLUME_CONTROL_PLANE_DB` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | yes | yes |
| `VOLUME_FLEET_DATA` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | yes | yes |
| `VOLUME_HARNESS_LAUNCHER` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | — | yes |
| `VOLUME_IAM_DB` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | yes | yes |
| `VOLUME_KEYCLOAK_DB` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | yes | yes |
| `VOLUME_MEMORY_DB` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | yes | yes |
| `VOLUME_NOTIFY_DB` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | — | yes |
| `VOLUME_PLATFORM_MINIO` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | yes | yes |
| `VOLUME_REALM_IMPORT` | `${COMPOSE_PROJECT_NAME:-taimen` | (volumes) | — | yes | yes |
<!-- /generated:env-summary -->

## See also

- [.env configuration](../getting-started/configuration.md)
- [Services and ports](services-and-ports.md)
- [Control Plane configuration](../control-plane/configuration.md)
- [IAM configuration](../iam/configuration.md)
- [Memory configuration](../memory/configuration.md)
- [Runner configuration](../runner/configuration.md)
- [Nodes and fleet](../runner/fleet.md)
- [Secrets and rotation](../operations/secrets.md)
