
# Installation and startup

Failures during environment preparation, image builds, container startup,
migrations, and bootstrap. Each table follows the "symptom → cause → fix"
pattern; run commands from the root of the superproject clone.

## Compose configuration

| Symptom | Cause | Fix |
|---|---|---|
| `required variable CP_POSTGRES_PASSWORD is missing a value: set CP_POSTGRES_PASSWORD` (or another variable with `:?`) | No `.env`, or compose is run outside the clone root, or with `-f` but without `--env-file` | Run `make secrets`; run from the root; otherwise pass `--env-file <clone root>/.env` |
| `no such service: control-plane-context-adapter` | Wrong service name. An error in one name fails the entire command | The adapter name is `context-adapter`; to list services: `tools/compose --profile "*" config --services` |
| Parse error for `env_file` with the `required` field | Old Docker Compose | Upgrade Compose to v2.24+ |
| `network <name> declared as external, but could not be found` | An additional compose file of the installation references an external network that does not exist | Run `docker network create <name>` before `up` |
| Volume mount error with an unknown driver | The installation's compose file uses a third-party volume driver whose plugin is not installed | Install the plugin (and its systemd unit) before the first `up` |
| `Bind for 127.0.0.1:18000 failed: port is already allocated` | The port is taken by another process or by a second copy of the stack | Free the port or set a different `*_HOST_PORT` in `.env` |
| `tools/compose ps` does not show all services | No profile specified | `tools/compose --profile "*" ps`; `make ps` does this for you |

To check the resulting configuration after interpolation:


```bash
make config PROFILES="core notify edge"
tools/compose --profile core --profile edge config | less
```

## Image builds

| Symptom | Cause | Fix |
|---|---|---|
| The `control-plane` or `memory-service` build fails while installing dependencies: `../platform-auth-sdk` not found, or a component directory is empty | Submodules are not initialized or are at a different revision | `git submodule update --init --recursive`; `git submodule status` shows no `-` or `+` |
| After `build`, the worker or adapter runs old code | The wrong service was built, or the container was not recreated. `control-plane-worker` and `context-adapter` have no `build:`; they use the `control-plane-api` image | `tools/compose build control-plane-api` and `tools/compose up -d control-plane-api control-plane-worker context-adapter` |
| The build on the host takes very long, and the stack is partially unavailable meanwhile | `make up` builds during the switchover | Separate the steps: `tools/compose … build`, then `up -d` |
| The build context is huge and the build is slow | The root `.dockerignore` is broken, or the tree contains extra directories (`node_modules`, `.venv`, `.git`) | Check `.dockerignore` at the root; do not put data in the working tree |
| Out of memory during the build (`Killed` in the build output) | Little RAM, no swap | Add swap; build with heavy optional services stopped |

## Container startup and healthcheck

| Symptom | Cause | Fix |
|---|---|---|
| A container stays `unhealthy` forever although the service responds | The healthcheck calls `localhost`: in slim/busybox images it resolves to IPv6 `::1`, while the service listens on IPv4 only | Use `127.0.0.1` in your own healthchecks. All healthchecks in the delivery already do this |
| `iam-service` starts, but token exchange returns `500`; the logs show `PermissionError` on `/run/secrets/iam_signing_key` | The key file is owned by root with mode `600`, while the service runs as uid 10001 | `sudo chown 10001:10001 secrets/iam-signing.pem`; keep mode `600` |
| A container that reads a PAT or token from `secrets/` (package executors) fails with `Permission denied` | Same cause: the owner is not uid 10001 | `chown 10001` the files; do not loosen permissions |
| `control-plane-worker` and `context-adapter` hang in `Created`/`Waiting` | They wait for `service_healthy` from `control-plane-api` | Troubleshoot `control-plane-api` (see below) |
| `control-plane-api` restarts; the logs show an Alembic error | A migration did not apply | Read the error; if it cannot be fixed, roll back the release, see [Upgrades and migrations](../operations/upgrades.md) |
| `/health/ready` → `503 migrations_pending`, the database revision is **newer** than head | An old image runs on top of the new schema | Restore the new release's image or run a downgrade with the new image |
| `/health/ready` → `503 database_unreachable` | The database did not start, the password is wrong, or the disk is full | `tools/compose logs control-plane-db`, `df -h` |
| `password authentication failed for user "…"` after changing a password in `.env` | `POSTGRES_PASSWORD` applies only when an empty volume is initialized | Change the role password with `ALTER ROLE` in the database or restore the previous value in `.env`, see [Secrets and rotation](../operations/secrets.md) |
| `control-plane-api` does not start: dependency `minio-bootstrap` exited with an error | The one-shot container failed | `tools/compose logs minio minio-bootstrap` |
| `memory-service` fails with `graph with oid … does not exist` | The memory database was restored from a logical dump into a new cluster | Fix the AGE catalog OIDs, see [Backup](../operations/backup.md) |

## Edge (Caddy)

| Symptom | Cause | Fix |
|---|---|---|
| `caddy` logs show `challenge failed`, `no valid A records`, `429` | The name does not point to the host, ports 80/443 are closed, or the ACME CA rate limits were exceeded after a series of failures | Check `dig` and the firewall; remove names without DNS from the Caddyfile; after a `429`, wait for the rate-limit window |
| A Caddyfile change does not apply after `caddy reload` | The file was replaced with a new inode (`mv`, atomic write), and the bind mount still sees the old one | Write into the same file (`cat new > Caddyfile`) or run `tools/compose up -d --force-recreate caddy` |
| `502` on a route | The upstream is not running (its profile is off) or has crashed | `tools/compose ps <upstream>`; remove the unneeded route |

For details, see [Edge and TLS](../operations/edge-and-tls.md).

## make and bootstrap

The `bootstrap.py` and `make smoke` messages below are quoted verbatim.

| Symptom | Cause | Fix |
|---|---|---|
| `make secrets`: `openssl: command not found` | openssl is not installed on the host | Install openssl |
| `bootstrap.py`: `timed out waiting for http://127.0.0.1:18000/health/ready` | The stack is not up, the API is not ready (migrations, database), or `CP_HOST_PORT` was changed without recreating containers | `make smoke`, `tools/compose ps`; ports are read from `.env` |
| `bootstrap.py`: `HTTP 401: {"detail":"unauthorized"}` on IAM requests | `IAM_BOOTSTRAP_TOKEN` in `.env` does not match the value `iam-service` was started with (for example, `.env` was edited without recreating the container) | `tools/compose up -d iam-service` or restore the previous value |
| `bootstrap.py`: `HTTP 409 … already_bootstrapped` | `deploy/state/<env>.json` is lost, but Control Plane is already initialized | Restore the state file from a backup; Control Plane bootstrap runs once |
| `bootstrap.py`: `PyYAML and jsonschema required by step 5b (catalog from packages)` (or only one of them) | uv is not installed, and the system Python lacks the dependencies of the catalog-from-packages step; the script stops before its first step | Install uv (`make bootstrap` pulls them in itself) or `apt install python3-yaml python3-jsonschema` / `pip install pyyaml jsonschema` |
| `bootstrap.py`: `… refers to IAM tenant …, which does not exist in IAM (volumes reset?)` | Volumes were reset, but `deploy/state/<env>.json` remains | `make reset-state` and rerun `make bootstrap` |
| `bootstrap.py`: `!! IAM cannot PATCH audiences (…): upgrade iam-service` | `iam-service` is older than the script | Upgrade the whole installation (submodules at the superproject revisions) |
| `bootstrap.py`: `!! core tenant … ≠ IAM tenant …: the installation predates the single tenant` | The installation predates the unified tenant, or Control Plane ignored `tenantId` | Live with different ids: put the IAM tenant that the script prints into `.env` |
| After bootstrap, the core still calls memory with a static key | The core processes were not recreated after `secrets/control-plane-iam.env` appeared | `tools/compose up -d control-plane-api control-plane-worker context-adapter` |
| `make smoke` prints `not running` for a required service | The profile is not up, or the service crashed | `tools/compose --profile "*" ps` |

## Miscellaneous

| Symptom | Cause | Fix |
|---|---|---|
| `ssh <alias>` fails with `bind [127.0.0.1]:… Address already in use` | The alias defines a `LocalForward`, and the port is taken by another session; ssh fails entirely | `ssh -o ClearAllForwardings=yes <alias>`; for git, `GIT_SSH_COMMAND='ssh -o ClearAllForwardings=yes'` |
| Static files delivered by rsync from macOS are served with `403` | The rsync bundled with macOS does not support `--chmod`, so files arrive with mode `600` | After delivery, run `chmod -R a+rX <directory>` on the host |
| The disk fills up quickly | Docker logs without rotation, build cache, the Control Plane event log | See [Resources and scaling](../operations/capacity.md) |

## See also

- [Production deployment](../operations/deployment.md)
- [Upgrades and migrations](../operations/upgrades.md)
- [Installation and first launch](../getting-started/quickstart.md)
- [Authentication and access](auth.md)
