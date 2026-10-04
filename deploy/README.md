# deploy/ — startup and bootstrap

Everything needed to bring Taimen up from a clean clone to a working state. There are
no secrets in this directory: `.env`, PATs and the keys live in `secrets/` and
`deploy/state/`, both in `.gitignore`. The detailed description is in the guide
`guide/` (the getting-started and operations sections).

```text
deploy/
├── local/compose.yml            all services and profiles; run from the root through make or tools/compose
├── bootstrap.py                 idempotent bootstrap: IAM → Control Plane → PAT → catalog → services → assistants
├── packages.yaml                catalog installation file: which packages/ bootstrap installs
├── harness-people.json          people with a personal assistant (bootstrap step 8)
├── caddy/Caddyfile.local        edge for a local run: http, one host, routing by path
├── keycloak/                    realm template (clients runtime-console and human-harness) and Admin API scripts
├── node/                        a fleet node: compose, node.yaml, .env.example
├── agent-runner/                the agent runner image that a node starts agents from
└── state/<env>.json             bootstrap state: identifiers, not secrets (in .gitignore)
```

Compose profiles, environment variables and ports are described in
[local/compose.yml](local/compose.yml) and `.env.example` at the root; they are not
duplicated here. Compose always runs from the root with `--project-directory .`: `make`
targets and `tools/compose` pass it, and `COMPOSE_FILE` is never written to `.env`.

## Local run

```bash
make secrets                     # .env (0600), secrets/iam-signing.pem, secrets/runtime-console-*-secret
make up PROFILES="core notify console fleet edge"
make bootstrap
tools/compose --profile notify --profile fleet up -d \
  control-plane-api control-plane-worker context-adapter notification-service fleet-controller
make smoke
```

After the first bootstrap the core, notification-service and fleet-controller are
restarted once to pick up the service accounts issued for them
(`secrets/control-plane-iam.env`, `secrets/notification-iam.env`,
`secrets/fleet-iam.env`); the script reminds you of this. Add the printed
`IAM_TENANT_ID=<uuid>` to `.env` and recreate the console
(`tools/compose --profile console up -d console`): the console, the assistant launcher
and fleet-controller need it. On Linux the files in `secrets/` read by containers
(`iam-signing.pem`, `runtime-console-*-secret`, `harness/`) must be owned by uid 10001
with mode 600.

## What bootstrap does

`deploy/bootstrap.py --env .env` is idempotent: what has been done is recorded in
`deploy/state/<env>.json` (`<env>` is `COMPOSE_PROJECT_NAME` or `--name`); a repeated
run skips completed steps and brings the mutable parts (audience ceilings, service
accounts, the catalog) in line with the registries in the script and the packages.
Secrets are never printed. The step numbers below are the ones the script prints.

- **1.** Waits for the Control Plane and IAM to be ready on the `127.0.0.1` ports.
- **2.** IAM: the tenant, audiences with their own scope ceilings (`control-plane`,
  `memory-service`, `notification-service`, `iam`, `human-harness`, `fleet`), the
  operator's human principal (`--operator`, `Human Operator` by default). The sync only
  adds scopes; `--prune-scopes` removes those that are not in the registry, `--dry-run`
  shows what steps 2–2c would change without writing.
- **2b.** The `people-admins` and `fleet-admins` groups with the operator: federation
  grants `iam:people` (managing people in the console) and `fleet:admin` (node join keys)
  only to their members and only on an explicit request.
- **2c.** `--identity-provider <file>` (optional): an IAM identity provider from a YAML
  description and the link of the operator's `sub` at that IdP.
- **2a.** IAM: the Control Plane service account for access to memory →
  `secrets/control-plane-iam.env`.
- **3.** Control Plane: `POST /api/v1/bootstrap` — the tenant (the same UUID as in IAM),
  the operator's admin principal and its binding in one transaction.
- **4.** The operator's PAT with the `control-plane:read/write/admin` ceiling →
  `secrets/harness-pat` (0600, lifetime `--pat-ttl`, 180 days by default).
- **5.** Control Plane: a project template, a project and a workspace named after the
  tenant. From here on the core is called with a token provider that renews the access
  token before it expires.
- **5b.** The catalog from [packages/](../packages/README.md) by the installation file
  `--packages` (default [packages.yaml](packages.yaml)) as one installation plan of the
  package SDK (`sdk/package-sdk`): the plan is written to
  `deploy/state/<env>.packages-plan.json` and exactly that plan is applied; an empty
  plan is not applied, so a repeated run changes nothing. `--no-packages` skips the step.
- **5c.** notification-service: an IAM service account → `secrets/notification-iam.env`,
  the service description and its identity in the Control Plane's agent registry.
- **5d.** fleet-controller: the same → `secrets/fleet-iam.env`. Both steps always run;
  the services pick up the files once their profiles are started. A changed ceiling or a
  lost env file is a PATCH of the same account (the principal stays). Then the legacy
  api-key issued in step 3 is revoked: the installation is IAM-only.
- **8.** `--harness-people deploy/harness-people.json` (optional): personal assistants —
  see below.

After the volumes are reset, the state file refers to objects that no longer exist;
the script notices this and asks for `make reset-state` — that target moves the state
and the issued credentials to `secrets/stale-<time>/`.

At the end the script prints the credential key for the CLI and the MCP plugin:
`~/.config/iam/credentials.json` (0600), entry `<issuer>|<tenant>|<principal>` → the
contents of `secrets/harness-pat`. The alternative without a file is the variables
`IAM_CREDENTIAL_MODE=environment` and `IAM_PLATFORM_ACCESS_TOKEN` (only together).

## Web console and people (the console profile)

The console signs people in through Keycloak (Authorization Code + PKCE, the
confidential client `runtime-console`) and exchanges the IdP token in IAM
`federation:exchange`. The realm is rendered from
[keycloak/platform-realm.json](keycloak/platform-realm.json) on the first start of
Keycloak: `realm-render` substitutes the public address and the client secret from
`secrets/runtime-console-oidc-secret`. Keycloak imports a realm only once; later changes
(a new public address, a new secret) go through the Admin API —
[keycloak/keycloak-runtime-console-client.py](keycloak/keycloak-runtime-console-client.py).

People: create the user in Keycloak with
[keycloak/keycloak-users.py](keycloak/keycloak-users.py) (firstName and lastName are
required, the password must not be temporary), then add the person in the console by
their IdP subject. The console does not create IdP users itself.

```bash
docker run --rm --network taimen_default -v "$PWD/deploy/keycloak:/s:ro" \
  -e KC_ADMIN_PASSWORD="$(sed -n 's/^KEYCLOAK_ADMIN_PASSWORD=//p' .env)" \
  -e KC_USERS='[{"username":"alice","email":"alice@example.com","password":"…","first_name":"Alice","last_name":"Example"}]' \
  python:3.12-alpine python /s/keycloak-users.py
```

## Personal assistants (the harness profile)

The launcher creates one assistant container per person from the `human-harness` image;
a person signs in through the IdP (the harness profile starts Keycloak as well, with the
client `human-harness` of the realm template) and talks to the assistant in the console. Docker is reached only through a socket
proxy on the internal `harness-control` network; people's containers live on
`harness-people` with the core, the notification service and the edge, but without the
proxy, the databases, IAM or memory. `make bootstrap ARGS="--harness-people
deploy/harness-people.json"` issues each person's PAT (without admin) into
`secrets/harness/<principal>/credentials.json`, the launcher's cookie key and the
registry `secrets/harness/people.json`. Each person puts their model subscription token
(`claude-oauth-token`) and, if needed, a forge token (`forge-token`) into their directory
(0600).

## Agents (the fleet profile)

Agents are described in catalog packages (kind `Agent`): kind, model, working copy,
skills, secrets and placement. fleet-controller creates each agent's identity and token
and places it on a node; a node is a machine you run from [node/](node/README.md), with
agents started from the [agent runner image](agent-runner/README.md). The controller's
service account is created by bootstrap step 5d; a node joins with a single-use key:

```bash
tools/compose --profile fleet exec fleet-controller fleet-controller join-key --ttl 3600
```

## Telegram notifications

The Telegram channel is enabled by the file `secrets/notification-telegram.env` with
the variables `NS_TELEGRAM_BOT_TOKEN`, `NS_TELEGRAM_WEBHOOK_SECRET` and
`NS_TELEGRAM_BOT_USERNAME`; without the file the service works with the web inbox and
email. The bot webhook is the public address `/notify/…` behind Caddy.

## Production installation

- Set `TAIMEN_PUBLIC_URL` (https, without a trailing `/`) and `TAIMEN_PUBLIC_HOST`,
  provide your own Caddyfile with the domain (Caddy issues TLS) and point `CADDYFILE` at
  it; take the path layout from `caddy/Caddyfile.local`, without the `/memory/*` route.
- `KEYCLOAK_HOSTNAME_STRICT=true` if the `idp`, `console` or `harness` profile is started.
- The IAM issuer (`${TAIMEN_PUBLIC_URL}/iam`) goes into tokens and into Control Plane
  bindings: changing the public address means migrating the bindings and the redirect
  addresses of the Keycloak clients.
- Settings of your installation (memory limits, extra volumes, another image registry)
  go into a root `compose.override.yml`: `make` and `tools/compose` add it as a second file.
