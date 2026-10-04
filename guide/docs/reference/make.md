
# Make targets

All targets of the superproject's root `Makefile`, the single mechanism for
launching, checking, and documenting the platform. This page is for an
engineer who brings up a deployment, runs checks before a commit, or builds
this guide. Run `make` from the superproject root; `make` without arguments
prints the list of targets with descriptions (`make help`).

## Summary

| Target | Parameters | What it does |
|---|---|---|
| `help` | — | List of targets with descriptions (the default target). |
| `secrets` | — | Creates `.env` from `.env.example` (if it does not exist), fills empty secrets, generates signing keys. |
| `config` | `PROFILES` | Validates `deploy/local/compose.yml` after interpolation for the selected profiles. |
| `build` | `PROFILES` | Builds the images of the selected profiles. |
| `up` | `PROFILES` | Builds and starts the selected profiles in the background. |
| `down` | — | Stops and removes the containers of all profiles; volumes are kept. |
| `ps` | — | Container status for all profiles. |
| `logs` | `svc` | Log stream of a service (or of all services). |
| `smoke` | — | Checks the health of running services through `127.0.0.1` ports. |
| `bootstrap` | `ARGS` | Initial setup: tenant, principals, PAT, bindings, catalog. |
| `reset-state` | — | After a volume reset, moves the bootstrap state and the credentials it issued to `secrets/stale-<time>/`. |
| `check` | — | Lint + unit tests of all core components (same as the required CI). |
| `check-<component>` | — | Lint + tests of a single component. |
| `lint-<component>` | — | Lint only, for a single component. |
| `test-<component>` | — | Tests only, for a single component. |
| `packages-check` | — | Checks the catalog packages in `packages/`. |
| `linkcheck` | — | Checks relative links in the documentation. |
| `submodules` | — | Initializes submodules at the pinned revisions. |
| `status` | — | Submodule pointers and uncommitted changes. |
| `guide` | — | Builds this guide into `guide/site`. |
| `guide-serve` | — | The guide with live reload on `http://127.0.0.1:8008`. |

## Make variables

| Variable | Default | Where it is used |
|---|---|---|
| `PROFILES` | `core edge` | `config`, `build`, `up`: expands to `tools/compose --profile <p> …` for each profile. |
| `svc` | empty (all services) | `logs`. |
| `ARGS` | empty | `bootstrap`: extra arguments for `deploy/bootstrap.py`. |
| `BOOTSTRAP_PY` | `uv run --no-project --quiet --with pyyaml --with jsonschema python3` if uv is installed; otherwise `python3` | `bootstrap`: the script interpreter. |
| `ENV_NAME` | `COMPOSE_PROJECT_NAME` from `.env`, otherwise `taimen` | `reset-state`: the state file name. |

Internal component lists:

| List | Members |
|---|---|
| `COMPONENTS_PY` (core, `make check`) | `platform-auth-sdk`, `platform-llm`, `skill-sdk`, `iam-service`, `control-plane`, `memory-service` |

## Running the stack

### make secrets

```bash
make secrets
```


1. If there is no `.env`, copies `.env.example` to `.env` and sets mode `600`.
2. `tools/fill_secrets.py .env` fills **only empty** values from a fixed list
   with random hex strings (`secrets.token_hex`): database passwords (`CP_`,
   `IAM_`, `MEMORY_`, `NOTIFY_`), bootstrap tokens (`CP_`, `IAM_`),
   `MEMORY_API_KEY`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`,
   `CP_S3_ACCESS_KEY_ID`, `CP_S3_SECRET_ACCESS_KEY`. Existing values are left
   untouched; running it again is safe.
3. Creates the `secrets` directory.
4. Generates an RSA 3072 key `secrets/iam-signing.pem` if it does not exist,
   and sets mode `600`.

!!! note "On Linux, the owner is uid 10001"
    Containers read the keys as uid 10001. After `make secrets`, run
    `chown 10001 secrets/*.pem`, otherwise IAM cannot read the signing key.


The target does not fill `IAM_TENANT_ID`: there is nothing to generate it
from. In `deploy/local/compose.yml` it is empty by default, so `make up` for `core edge`
works right after `make secrets`; see [Environment variables](environment.md).

### make config


```bash
make config
make config PROFILES="core notify edge"
```

`tools/compose … config --quiet`; on success it prints
`deploy/local/compose.yml is valid for profiles: …`. It catches empty required variables and interpolation errors before
launch.

### make build / make up


```bash
make up                                   # core edge
make up PROFILES="core notify edge"      # with notifications
make build PROFILES="core"
```


`up` runs `tools/compose --profile … up -d --build`: it rebuilds changed
images and recreates containers.

### make down / ps / logs

```bash
make down
make ps
make logs svc=control-plane-api
make logs                       # all services
```

These targets work with `--profile "*"`, that is, with all profiles at once,
regardless of `PROFILES`. `down` does not remove volumes: data is kept.

### make smoke

```bash
make smoke
```

`tools/smoke.py` reads ports from `.env` (or the environment) and polls the
health endpoints of running services; services that are not running are
marked `not running` and do not count as an error. The exit
code is `1` if at least one running service responded with `≥ 400`. The list
of checks is in [Services and ports](services-and-ports.md#healthchecks).

### make bootstrap


```bash
make bootstrap
make bootstrap ARGS="--name local --secrets-dir secrets --packages deploy/packages.yaml"
```

Runs `deploy/bootstrap.py --env .env $(ARGS)`: if uv is installed, through
`uv run --no-project --quiet --with pyyaml --with jsonschema python3` (you do
not need to install PyYAML and jsonschema system-wide); otherwise with the
system `python3`, which then must have PyYAML and jsonschema. The script is
idempotent: state is stored in `deploy/state/<env>.json`, and a repeated run
skips what is already done. Arguments:

| Argument | Default | Purpose |
|---|---|---|
| `--env` | `.env` | Environment file (the target passes `.env`). |
| `--name` | `COMPOSE_PROJECT_NAME` | Environment name, which is also the state file name. |
| `--operator` | value from code | Display name of the human operator. |
| `--tenant-slug` | `COMPOSE_PROJECT_NAME` | Tenant slug. |
| `--pat-ttl` | `15552000` (180 days) | Lifetime of issued PATs, in seconds. |
| `--secrets-dir` | `secrets` | Where to write PATs and service account env files. |
| `--packages` | `deploy/packages.yaml` | Catalog installation file (`kind: Installation`). |

What it does step by step and which permissions it grants: [Bootstrap](../getting-started/bootstrap.md)
and [Permissions and scopes](permissions.md#bootstrap-grants).

### make reset-state

```bash
tools/compose --profile "*" down -v   # reset volumes
make reset-state
make up && make bootstrap
```

You need it after removing volumes: the bootstrap state file refers to a tenant
and principals that no longer exist in the empty databases, and in that case
bootstrap stops with the hint `make reset-state`. The target moves the
following into `secrets/stale-<YYYYMMDD-HHMMSS>/`:

- `deploy/state/<ENV_NAME>.json`;

- `secrets/harness-pat`, `secrets/control-plane-iam.env`,
  `secrets/notification-iam.env`, `secrets/memory-service-iam.env`,
  `secrets/agents/`.

It does not touch the signing keys (`secrets/*.pem`) or `.env`. If there is
nothing to move, it prints `nothing to move`; otherwise it lists the moved
files and ends with `state reset; the signing key and .env are untouched — next:
make bootstrap`. Files are
not deleted: you can revoke or delete the old credentials manually later.

## Checks


### make check

```bash
make check            # core: same as the required CI
```

For each component, `lint-<component>` and `test-<component>` run.

### make check-&lt;component&gt;, lint-&lt;component&gt;, test-&lt;component&gt;

```bash
make check-control-plane
make lint-memory-service
make test-iam-service
```

`lint-<component>` runs `uv run ruff check .` and `uv run ruff format --check .`
in the component directory.

`test-<component>` runs `uv run pytest -q` in the component directory by
default. Some components have their own rules:

| Target | What it does in addition |
|---|---|
| `test-control-plane` | Starts `db-test` from `services/control-plane/docker-compose.yml` (profile `test`, port 5434), runs `pytest tests/unit tests/client`, then stops the database. |
| `test-skill-sdk` | `skill-sdk` tests with all extras, then an end-to-end executor test through `control-plane` (`tests/test_executor_e2e.py`). |
| `test-memory-service` | `pytest` with the `mcp` extra, without `tests/integration`. |

!!! tip "Test databases occupy host ports"

    `test-control-plane` starts a container on port 5434. If the port is busy,
    the tests do not start.

### make packages-check

```bash
make packages-check
```


1. `package-sdk check`: schema, references, and core validators for
   the packages in `packages/`.
2. `package-sdk check --install <installation file>`: checks the
   installation file.
3. `pytest -q tools/tests` (through `uv run --no-project` with `pytest`,
   `pyyaml`, `jsonschema`, `regex`, `ruamel.yaml`).

See [Catalog packages](../control-plane/catalog-packages.md).

## Documentation and repository

| Target | Command | Note |
|---|---|---|
| `linkcheck` | `python3 tools/linkcheck.py` | Relative links in the superproject documentation. |
| `submodules` | `git submodule update --init --recursive` | After cloning and after bumping pointers. |
| `status` | `git submodule status` and `git status --short` | A quick status overview. |
| `guide` | `cd guide && uv run --with-requirements requirements.txt mkdocs build --strict` | Any MkDocs warning fails the build. |
| `guide-serve` | `… mkdocs serve -a 127.0.0.1:8008` | Live preview of the guide. |

## Typical sequences

=== "First launch"

    ```bash
    make submodules
    make secrets
    make config
    make up
    make smoke
    make bootstrap
    # put the printed IAM_TENANT_ID into .env, then
    make up
    ```

=== "Again after a volume reset"

    ```bash
    tools/compose --profile "*" down -v
    make reset-state
    make up
    make bootstrap
    ```

=== "Before a commit to a component"

    ```bash
    make check-control-plane
    ```

=== "Updating a deployment"

    ```bash
    git pull --ff-only
    make submodules
    make up PROFILES="core edge"
    make smoke
    ```

## See also

- [Installation and first launch](../getting-started/quickstart.md)
- [Bootstrap](../getting-started/bootstrap.md)
- [Services and ports](services-and-ports.md)
- [Upgrades and migrations](../operations/upgrades.md)
