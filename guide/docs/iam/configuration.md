
# IAM configuration

A reference for configuring `iam-service`: the service's environment variables
with their defaults, how they are set in the `deploy/local/compose.yml`, local client
variables, the bootstrap token, the signing key, migrations, and common
configuration problems. It is for installation administrators.

## Service variables

The service reads its settings from the environment with the `IAM_` prefix
(pydantic-settings; case-insensitive; unknown variables are ignored).

| Variable | Default | Description |
|---|---|---|
| `IAM_DATABASE_URL` | `postgresql+psycopg://iam:iam@localhost:5435/iam` | SQLAlchemy connection string (async, psycopg driver). Used by both the service and Alembic |
| `IAM_BOOTSTRAP_TOKEN` | `""` | Secret for the administrative API (header `X-IAM-Bootstrap-Token`). If empty, administrative endpoints are closed |
| `IAM_ISSUER` | `http://localhost:8010` | The `iss` value in issued tokens; must match the issuer setting of all services |
| `IAM_TOKEN_TTL_SECONDS` | `300` | Access token lifetime (and `expiresIn` in exchange responses) |
| `IAM_SIGNING_PRIVATE_KEY` | `""` | RSA private key in PEM (without a passphrase) as a string |
| `IAM_SIGNING_PRIVATE_KEY_FILE` | `""` | Path to the key file; used if `IAM_SIGNING_PRIVATE_KEY` is empty |
| `IAM_SIGNING_KEY_ID` | `local-dev` | `kid` in the token header and in JWKS |
| `IAM_CREATE_SCHEMA_ON_STARTUP` | `false` | Create tables on startup (`create_all`). Development only; in operation, only Alembic changes the schema |
| `IAM_PAT_DEFAULT_TTL_SECONDS` | `2592000` (30 days) | PAT lifetime if `expiresInSeconds` is not passed |
| `IAM_PAT_MAX_TTL_SECONDS` | `31536000` (365 days) | Maximum PAT lifetime |
| `IAM_PAT_MAX_AUTHENTICATION_AGE_SECONDS` | `300` | Maximum age of a human's authentication context for PAT issuance |
| `IAM_LEGACY_CREDENTIAL_MAX_TTL_SECONDS` | `7776000` (90 days) | Maximum compatibility window for an imported Control Plane key |
| `IAM_SCIM_AUDIENCE` | `iam-scim` | Audience of the SCIM client's token |
| `IAM_SCIM_SCOPE` | `scim:write` | Scope required for SCIM |
| `IAM_SCIM_MAX_PAGE_SIZE` | `200` | Maximum SCIM result page size |

!!! note "Parameters that are not set through variables"
    The external IdP's JWKS cache (`jwksCacheTtlSeconds`,
    `jwksStaleGraceSeconds`) and the `acr`/`amr` requirements are configured
    on each identity provider (see [Federation](federation.md)). The registry
    of audiences and their scopes is data in the database (see
    [Tokens](tokens.md)).

## How it is set in `deploy/local/compose.yml`

The `deploy/local/compose.yml` (profile `core`) passes only some of the variables to
the `iam-service` container; the rest use their defaults:

```yaml
iam-service:
  command: >
    sh -c "alembic upgrade head &&
           uvicorn iam_service.app:app --host 0.0.0.0 --port 8010"
  environment:
    IAM_DATABASE_URL: postgresql+psycopg://iam:${IAM_POSTGRES_PASSWORD}@iam-db:5432/iam
    IAM_BOOTSTRAP_TOKEN: ${IAM_BOOTSTRAP_TOKEN:?set IAM_BOOTSTRAP_TOKEN}
    IAM_ISSUER: ${TAIMEN_PUBLIC_URL:?set TAIMEN_PUBLIC_URL}/iam
    IAM_SIGNING_PRIVATE_KEY_FILE: /run/secrets/iam_signing_key
    IAM_SIGNING_KEY_ID: ${IAM_SIGNING_KEY_ID:-local-dev}
  secrets: [iam_signing_key]
  ports: ["127.0.0.1:${IAM_HOST_PORT:-18010}:8010"]
  mem_limit: ${IAM_MEM_LIMIT:-256m}
```

`.env` variables related to IAM:

| `.env` variable | Default | Where it goes |
|---|---|---|
| `TAIMEN_PUBLIC_URL` | — (required) | `IAM_ISSUER` = `${TAIMEN_PUBLIC_URL}/iam`; also the issuer for all services (`CP_IAM_ISSUER`, `CB_IAM_ISSUER`, …) |
| `IAM_POSTGRES_PASSWORD` | — (required) | password of `iam-db` and `IAM_DATABASE_URL` |
| `IAM_BOOTSTRAP_TOKEN` | — (required) | `IAM_BOOTSTRAP_TOKEN`; also the bootstrap script and reading of the IAM event log by projections of external services (for example, a PDP) |
| `IAM_SIGNING_KEY_FILE` | `./secrets/iam-signing.pem` | file of the docker secret `iam_signing_key` |
| `IAM_SIGNING_KEY_ID` | `local-dev` | `IAM_SIGNING_KEY_ID` |
| `IAM_TENANT_ID` | empty | IAM tenant for services and executors that need it for credential exchange; fill in after `make bootstrap` |
| `IAM_HOST_PORT` | `18010` | IAM port on the host's `127.0.0.1` |
| `IAM_MEM_LIMIT` | `256m` | container memory limit |
| `IAM_BUILD_CONTEXT` | `./services/iam-service` | image build context |
| `PG_MEM_LIMIT` | `256m` | memory limit of `iam-db` (shared by the databases) |
| `VOLUME_IAM_DB` | `${COMPOSE_PROJECT_NAME}_iam_db` | name of the database volume |

`make secrets` creates `.env` from `.env.example`, fills empty secrets with
random values, and generates `secrets/iam-signing.pem` (RSA 3072, `0600`).

### Changing parameters not present in `deploy/local/compose.yml`

To change, for example, the access token or PAT lifetime, add the variables to
a compose override file instead of editing the shipped `deploy/local/compose.yml`:

```yaml
# compose.override.yml
services:
  iam-service:
    environment:
      IAM_TOKEN_TTL_SECONDS: "600"
      IAM_PAT_DEFAULT_TTL_SECONDS: "7776000"
```

```bash
tools/compose up -d iam-service
```

!!! warning "Do not increase the access token TTL without need"
    IAM cannot revoke an access token already issued: it lives until `exp`.
    The longer `IAM_TOKEN_TTL_SECONDS` is, the wider the window during which a
    disabled user still passes verification in services that have no
    revocation projection of their own. The `TokenLifetimeWindow` mode in
    platform-auth-sdk rejects by default tokens that have more than 900 s left
    to live.

## Bootstrap token {#bootstrap-token}

`IAM_BOOTSTRAP_TOKEN` is the only boundary of the IAM administrative API:

- it is compared in constant time with the `X-IAM-Bootstrap-Token` header;
- an empty variable value closes all administrative endpoints
  (`401 unauthorized`);
- the `Authorization: Bearer …` header is **not** accepted for administrative
  operations; only `X-IAM-Bootstrap-Token` is;
- in audit, the action is recorded on behalf of `bootstrap`.

Recommendations:

1. Generate a long random value (`make secrets` does this for you) and store
   it only in `.env` with `0600` permissions.
2. Do not give it to clients, agents, or CI that need only PATs.
3. Restrict the IAM administrative paths at the edge (see [API](api.md) and
   [Edge and TLS](../operations/edge-and-tls.md)).
4. If you suspect compromise, change the value in `.env`, recreate
   `iam-service` (`tools/compose up -d iam-service`), and check the
   `GET /api/v1/events` log for unexpected `principal.created`,
   `platform_access_token.issued`, `service_account.created`.

!!! danger "This token is not for development in shared environments"
    The standalone `docker-compose.yml` of the `iam-service` repository uses
    `dev-bootstrap-token-change-me` by default. This value is for local
    development only; replace it in any shared environment.

## Signing key

| Requirement | Why |
|---|---|
| RSA, PEM, no passphrase | IAM loads the key without a passphrase and rejects non-RSA keys |
| File `0600`, owner uid `10001` (Linux) | the container runs as user `iam` (uid 10001); it cannot read a root-owned `0600` file |
| A unique `IAM_SIGNING_KEY_ID` for each key | services cache keys by `kid` |
| File outside git | `secrets/` is in `.gitignore` |

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out secrets/iam-signing.pem
chmod 600 secrets/iam-signing.pem
sudo chown 10001:10001 secrets/iam-signing.pem   # Linux
```

The key change procedure is in [Tokens, audiences, scopes](tokens.md).

## Issuer

`IAM_ISSUER` defines the `iss` of every token and must **exactly** match the
issuer configured in services (`CP_IAM_ISSUER`, `CB_IAM_ISSUER`,
`NS_IAM_ISSUER`, …). In `deploy/local/compose.yml`, all of them are derived from a single
`TAIMEN_PUBLIC_URL`, so they match automatically.

!!! danger "Changing `TAIMEN_PUBLIC_URL` changes the issuer"
    A principal binding in Control Plane is stored by the
    `(issuer, iam_principal_id)` pair. After the public address changes, old
    bindings can no longer be found, and sign-in closes for everyone. Migrate
    the bindings in the same change; see
    [Upgrades and migrations](../operations/upgrades.md).

## Database and migrations

- A separate PostgreSQL 16 database (`iam-db`, user and database `iam`).
- Alembic manages the schema; the container runs `alembic upgrade head`
  before starting the API. `alembic` takes the connection string from
  `IAM_DATABASE_URL`.
- Running migrations manually (for example, from source against a database on
  the host):

    ```bash
    cd services/iam-service
    IAM_DATABASE_URL=postgresql+psycopg://iam:<password>@127.0.0.1:5435/iam \
      uv run alembic upgrade head
    ```

| Revision | Contents |
|---|---|
| `0001` | tenants, principals, memberships, external identities, groups, audiences, service accounts, outbox, audit |
| `0002` | identity providers, federation, group projection |
| `0003` | Platform Access Tokens and authentication contexts |
| `0004` | SCIM: provisioning sources, SCIM users and groups |

Backup is a regular `pg_dump` of the `iam` database (see
[Backup](../operations/backup.md)). The database stores only hashes of
secrets; the signing key is not part of the database and is backed up
separately.

## Local client variables

Used by the `iam` CLI and by clients built on `control-plane-client` (MCP
plugin, runner). Details are in [Credentials and PAT](credentials.md).

| Variable | Default | Description |
|---|---|---|
| `IAM_CREDENTIAL_MODE` | empty | `environment` (or `ci`): take the PAT from `IAM_PLATFORM_ACCESS_TOKEN` |
| `IAM_PLATFORM_ACCESS_TOKEN` | empty | PAT in environment mode; without the mode, an error |
| `IAM_PRINCIPAL` | empty | whose credential to use if the machine has several for the same IAM + tenant pair |
| `IAM_NO_KEYCHAIN` | empty | `1`: do not use macOS Keychain (file only) |
| `IAM_BINDING_FILE` | empty | explicit path to `binding.json` instead of searching for `.iam/binding.json` |
| `XDG_CONFIG_HOME` | `~/.config` | base of the `iam/credentials.json` path |
| `CONTROL_PLANE_IAM_URL` | empty | IAM address for the Control Plane client |
| `CONTROL_PLANE_IAM_TENANT` | empty | IAM tenant |
| `CONTROL_PLANE_IAM_AUDIENCE` | `control-plane` | exchange audience |
| `CONTROL_PLANE_IAM_SCOPES` | empty | scopes separated by spaces or commas |

## Common configuration problems

| Symptom | Cause | What to do |
|---|---|---|
| `401 unauthorized` on administrative calls | wrong/empty `X-IAM-Bootstrap-Token`, empty `IAM_BOOTSTRAP_TOKEN` in the container, or `Authorization: Bearer` was used | pass exactly `X-IAM-Bootstrap-Token`; check the container variables: `tools/compose exec iam-service env` (look for `IAM_BOOTSTRAP_TOKEN`) |
| `500` on `/.well-known/jwks.json` and on any exchange | the signing key is not set or cannot be read | check `IAM_SIGNING_KEY_FILE`, that the file exists, and that its owner is uid 10001 |
| `500` on exchange after a key change, `PermissionError` in the logs | the key file is `root:root 0600` | `chown 10001:10001` on the host, keep permissions at `0600` |
| A service returns `401` for a fresh token | `iss` in the token does not equal the service's issuer | compare `IAM_ISSUER` and `*_IAM_ISSUER`; both must be derived from `TAIMEN_PUBLIC_URL` |
| A service returns `503 verification_unavailable` | the service cannot get JWKS for longer than `stale_after` | check that `http://iam-service:8010/.well-known/jwks.json` is reachable from the service container |
| All tokens are rejected for several minutes after a key change | the `kid` was not changed | set a new `IAM_SIGNING_KEY_ID` and recreate `iam-service` |
| `403 scope_not_allowed` on exchange | scope without the prefix (`write` instead of `control-plane:write`) or outside the ceiling | request full scope names from `allowedScopes` |
| `403 authentication_context_required/expired` when issuing a PAT to a human | no sign-in, or more than 300 s have passed | record an authentication context and issue the PAT right away |
| `400 idempotency_key_required` | `Idempotency-Key` was not passed | add the header with a new UUID |
| `422 principal_kind_not_allowed` | a PAT for a service account | use client credentials |
| `iam_environment_mode_required` in the client | `IAM_PLATFORM_ACCESS_TOKEN` is set without the mode | add `IAM_CREDENTIAL_MODE=environment` |
| `credential_ambiguous` / `iam_credential_ambiguous` | several credentials for the same IAM + tenant pair on the machine | set `IAM_PRINCIPAL` for each process |
| `credentials_file_permissions` | `credentials.json` is accessible to the group/everyone | `chmod 600 ~/.config/iam/credentials.json` |
| `503 identity_provider_unavailable` during federation | IAM cannot reach the IdP's discovery/JWKS | check that IAM resolves the issuer address; set `jwksUri` if needed |
| Browser sign-in creates a second principal | the external identity is not linked to the existing principal | link it in advance; see [Federation](federation.md) |

More scenarios are in [Troubleshooting: authentication and access](../troubleshooting/auth.md).

## See also

- [.env configuration](../getting-started/configuration.md)
- [Environment variables](../reference/environment.md)
- [Secrets and rotation](../operations/secrets.md)
- [Services and ports](../reference/services-and-ports.md)
- [IAM API](api.md)
