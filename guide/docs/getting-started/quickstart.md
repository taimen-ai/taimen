
# Installation and first launch

A step-by-step procedure: from cloning the superproject to a running platform
core (profiles `core edge`) that has passed bootstrap and the smoke check. It
is intended for a local machine or a test server; for a production deployment
the steps are the same, but `.env` and the Caddyfile differ. See
[Production deployment](../operations/deployment.md).

!!! abstract "What you get at the end"
    - 9 containers of the `core` and `edge` profiles in the `running`/`healthy` state;
    - a tenant, a human operator with administrator rights, a project, and a workspace;
    - the operator's PAT in `secrets/harness-pat` and the core service account in
      `secrets/control-plane-iam.env`;
    - a catalog from the installation file `deploy/packages.yaml` (without packages,
      the core knows only the system task type `task`).

## Step 0. Check the requirements

Make sure you have Docker with Compose v2.24+, git, make, Python 3 with uv
(without uv, PyYAML and jsonschema in the system Python), and openssl, and that
ports `80`, `18000`, `18001`, and `18010` are free. Details:
[Requirements](requirements.md).

## Step 1. Get the sources

Components are included as git submodules, so clone recursively:

```bash
git clone --recurse-submodules <superproject-url> taimen
cd taimen
```

If the repository is already cloned without submodules:

```bash
make submodules          # git submodule update --init --recursive
make status              # submodule pointers and uncommitted changes
```

Submodules check out the revisions pinned in the superproject; together they
form the consistent platform version. Do not switch them to branches by hand
unless you are developing the component itself.

## Step 2. Generate `.env` and keys

```bash
make secrets
```

What the target does (`Makefile`, `tools/fill_secrets.py`):

1. If `.env` does not exist, copies `.env.example` to `.env` and sets mode `600`.
2. Fills **empty** secrets with random values (`secrets.token_hex`): passwords
   for all databases, `CP_BOOTSTRAP_TOKEN`, `IAM_BOOTSTRAP_TOKEN`,
   `MEMORY_API_KEY`, MinIO keys. Values that are already set are left
   untouched, so running it again is safe.
3. Creates the `secrets/` directory.
4. Generates the RSA-3072 signing key `secrets/iam-signing.pem` (if missing)
   and sets its mode to `600`.

Output:

```text
created .env
filled secrets: CP_POSTGRES_PASSWORD, IAM_POSTGRES_PASSWORD, …, S3_SECRET_ACCESS_KEY
secrets in place: .env, secrets/iam-signing.pem (on Linux: chown 10001 secrets/*.pem)
```

On Linux, hand the keys over to the container uid right away:

```bash
sudo chown 10001:10001 secrets/*.pem
```

## Step 3. Check `.env` before the first launch

For the core (`core edge`), you do not need to edit `.env` after `make secrets`.


### Optional: LLM provider

By default, memory works offline (`MEMORY_EMBEDDING_PROVIDER=fake`,
`MEMORY_LLM_PROVIDER=echo`): search works, but the embeddings are fake. For
real search, specify an OpenAI-compatible endpoint; see
[.env configuration](configuration.md).

## Step 4. Start the core

```bash
make config       # check deploy/local/compose.yml after interpolation
make up           # tools/compose --profile core --profile edge up -d --build
```

The first build takes several minutes. The startup order is defined by
`depends_on` with healthchecks: databases → `iam-service` and `memory-service` →
`control-plane-api` (applies Alembic migrations) → `control-plane-worker` and
`context-adapter`.

Check the state:

```bash
make ps
```

```text
NAME                           SERVICE                STATUS
taimen-caddy-1                 caddy                  Up
taimen-context-adapter-1       context-adapter        Up
taimen-control-plane-api-1     control-plane-api      Up (healthy)
taimen-control-plane-db-1      control-plane-db       Up (healthy)
taimen-control-plane-worker-1  control-plane-worker   Up
taimen-iam-db-1                iam-db                 Up (healthy)
taimen-iam-service-1           iam-service            Up (healthy)
taimen-memory-db-1             memory-db              Up (healthy)
taimen-memory-service-1        memory-service         Up (healthy)
```

Logs of a single service: `make logs svc=control-plane-api`.

## Step 5. Run bootstrap

Bootstrap creates the tenant, the operator, the operator's PAT, the project,
the workspace, the task type catalog, and service accounts. The script is
idempotent: a repeated run skips what is already done.

```bash
make bootstrap ARGS='--operator "Alice Operator"'
```

`make bootstrap` runs `deploy/bootstrap.py` through
`uv run --no-project --with pyyaml --with jsonschema python3` if uv is
installed; otherwise, with the system `python3` (which then needs PyYAML and
jsonschema).

`--operator` is the display name of the first human administrator; set your
own. Expected output (IDs and paths shortened; the lines of step 5b come from
`package-sdk`, which prints them in Russian):

```text
1. waiting for services
2. IAM tenant, audiences, operator principal
   IAM tenant <tenant-id> operator <iam-principal-id>
   !! add to .env: IAM_TENANT_ID=<tenant-id> (needed by clients and runners)
2a. Control Plane service account in IAM
   issued → secrets/control-plane-iam.env client <client-id>
   !! restart the core so that it picks up the env file: tools/compose up -d control-plane-api control-plane-worker context-adapter
3. Control Plane bootstrap with the operator binding
   tenant <tenant-id> operator <cp-principal-id> binding <binding-id>
4. operator PAT
   issued → secrets/harness-pat prefix <prefix>
   PAT → access token exchange: ok
5. Control Plane: project template, project, workspace
   project <project-id> workspace <workspace-id>
5b. catalog from packages: deploy/packages.yaml
   …
5c. notification-service: IAM service account, identity in the core, env file
   issued → secrets/notification-iam.env client <client-id>
   !! restart the service: tools/compose --profile notify up -d notification-service
   revision 1 principal <principal-id>
   legacy admin api-key revoked
done: deploy/state/taimen.json
credential for the MCP plugin and CLI: ~/.config/iam/credentials.json, key http://taimen.localhost/iam|<tenant-id>|<iam-principal-id> → contents of secrets/harness-pat
```

What happens at each step is described in [Bootstrap](bootstrap.md).

## Step 6. Apply the bootstrap results

1. Write the IAM tenant into `.env` (the variable is empty before bootstrap):

    ```bash
    TENANT=$(python3 -c 'import json;print(json.load(open("deploy/state/taimen.json"))["iamTenantId"])')
    sed -i.bak -E "s/^IAM_TENANT_ID=.*/IAM_TENANT_ID=$TENANT/" .env
    ```

2. Restart the core processes so they pick up the service account
   (`secrets/control-plane-iam.env`). After this, Control Plane calls memory
   with an IAM token instead of a static key:

    ```bash
    tools/compose up -d control-plane-api control-plane-worker context-adapter
    ```

The state file is named `deploy/state/<COMPOSE_PROJECT_NAME>.json` (by default
`taimen.json`) or after the `--name` value.

## Step 7. Smoke check

```bash
make smoke
```

```text
  iam-service          OK  200 http://127.0.0.1:18010/healthz
  control-plane-api    OK  200 http://127.0.0.1:18000/health/ready
  memory-service       OK  200 http://127.0.0.1:18001/healthz
```

`tools/smoke.py` checks healthz only for running services (services that are
not up are reported as not running and do not count as errors) and returns a
non-zero exit code if any running service responds with an error.

## Step 8. Verify operator sign-in

Exchange the operator's PAT for a Control Plane token and ask who you are:

```bash
PAT=$(cat secrets/harness-pat)
TOKEN=$(curl -s -X POST http://127.0.0.1:18010/api/v1/platform-access-tokens:exchange \
  -H 'Content-Type: application/json' \
  -d "{\"token\": \"$PAT\", \"audience\": \"control-plane\"}" | jq -r .accessToken)

curl -s http://127.0.0.1:18000/api/v1/harness/context \
  -H "Authorization: Bearer $TOKEN" | jq '{tenant, principal, permissions}'
```

```json
{
  "tenant": { "id": "<tenant-id>", "slug": "taimen", "name": "Taimen" },
  "principal": { "id": "<principal-id>", "kind": "human", "displayName": "Alice Operator" },
  "permissions": ["admin", "approvals.decide", "tasks.claim", "…"]
}
```

Interactive Control Plane API documentation is available at
`http://taimen.localhost/docs` (through Caddy) or `http://127.0.0.1:18000/docs`.

Next: [First task](first-task.md).

## Stopping and resetting

| Action | Command | Data |
|---|---|---|
| Stop | `make down` | kept in volumes |
| Start again | `make up` | same data; no need to repeat bootstrap |
| Rebuild one service | `tools/compose build control-plane-api && tools/compose up -d control-plane-api control-plane-worker context-adapter` | kept |
| Full reset | see below | **deleted** |

!!! danger "Full deployment reset"
    Deleting volumes destroys all tasks, identities, and knowledge. After that,
    you must also remove the **bootstrap state**; otherwise the script stops at
    the state check (the IAM tenant from the file is not found):

    ```bash
    tools/compose --profile "*" down -v
    make reset-state
    make up && make bootstrap
    ```

    `make reset-state` moves `deploy/state/<name>.json` and the credentials
    issued by bootstrap to `secrets/stale-<time>/`; `.env` and the signing keys
    stay in place.

## Common problems

| Symptom | Cause | What to do |
|---|---|---|
| `required variable … is missing a value` on `make up` | the secrets that `make secrets` generates are empty | `make secrets` |
| `set CP_POSTGRES_PASSWORD` and similar | `make secrets` was not run, or `.env` is not in the root | `make secrets` |
| `iam-service` restarts, logs show `PermissionError` on the signing key | Linux, the key file is owned by root | `sudo chown 10001:10001 secrets/*.pem` |
| bootstrap: `PyYAML and jsonschema required by step 5b (catalog from packages)` (or only one of them) | uv is not installed, and the system Python lacks the dependencies | install uv (`make bootstrap` then adds them itself) or `pip install pyyaml jsonschema` |
| bootstrap: `… refers to IAM tenant …, which does not exist in IAM (volumes reset?)` | volumes were reset, but `deploy/state/<name>.json` remains | `make reset-state` and rerun bootstrap |
| bootstrap: `HTTP 409 … already_bootstrapped` at step 3 | Control Plane is already initialized, but the state file is missing | restore `deploy/state/<name>.json` or do a full reset |
| `bind: address already in use` on `80` | another web server holds the port | free the port, or start without `edge` (`make up PROFILES=core`) and work through `127.0.0.1` |
| `curl: Could not resolve host: taimen.localhost` | the system resolver does not know `*.localhost` | add a line to `/etc/hosts` or use `127.0.0.1:<port>` addresses |

More in [Installation and startup (troubleshooting)](../troubleshooting/startup.md).

## See also

- [.env configuration](configuration.md)
- [Bootstrap](bootstrap.md)
- [First task](first-task.md)
- [Make targets](../reference/make.md)
