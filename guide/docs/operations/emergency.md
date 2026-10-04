
# Emergency procedures

A runbook for incidents: what keeps working when an individual component
fails, how to roll back a release, what to do when you lose the runner host,
and what to do when credentials are compromised. This article is for the
on-call engineer; each procedure starts with an assessment, followed by
steps and verification.

## Dependency map

What stops working when a component fails:

| Failed | What keeps working | What stops |
|---|---|---|
| `iam-service` or `iam-db` | Already issued access tokens until they expire (up to 300 s); signature verification against the JWKS cache; the static memory key | PAT and client credentials exchange; after ~5 minutes, every harness, executor, and people's sign-in through federation; delivery to memory through the core service account |
| `control-plane-api` / `control-plane-db` | Memory and IAM on their own | All coordination: tasks, claims, runs, approvals; delivery to memory |
| `memory-service` / `memory-db` | Coordination entirely: claims, runs, approvals, task completion | Context assembly (returned degraded); log delivery accumulates lag or gets parked |
| `keycloak` / `keycloak-db` | Harnesses, the MCP plugin, and executors (they use PATs and bypass Keycloak) | New sign-ins of people to workplaces |
| `caddy` | Everything inside the host; access through an SSH tunnel to `127.0.0.1` | Any access from outside |
| Runner host | The whole platform | Autonomous execution of tasks assigned to this executor |

## IAM outage

**Assessment.**

```bash
tools/compose ps iam-service iam-db
curl -s http://127.0.0.1:18010/healthz
tools/compose logs --since 15m iam-service | tail -50
```

**What happens.** Control Plane verifies the access token signature against
JWKS from its cache (a stale cache is acceptable up to
`CP_IAM_JWKS_STALE_AFTER_SECONDS`, 3600 s by default), so tokens issued
before the outage keep working until they expire. No new tokens are issued:
harnesses and executors lose access within the access token lifetime
(300 s). The workplace launcher cannot let a person in (`federation:exchange`
is unavailable). `context-adapter`, which works through a service account, gets
refusals and accumulates lag.

**Steps.**

1. If the database is down: `tools/compose up -d iam-db`, check the disk
   and the PostgreSQL logs.
2. If the service fails at startup, look at the first error in the logs:
    - an Alembic migration error → roll back the release (below);
    - `PermissionError` on the signing key → the owner of
      `secrets/iam-signing.pem` must be uid 10001 (`chown 10001:10001`,
      mode `600`);
    - a database connection error → the `IAM_POSTGRES_PASSWORD` password in
      `.env` does not match the role in the database.
3. `tools/compose up -d iam-service`, wait for `healthy`.
4. Check `context_adapter_parked_tenants`; if it is `> 0`, run
   `control-plane ops adapter redrive <tenant-id>`.

### Emergency access while IAM is down

If restoring IAM takes long and you need to get into Control Plane (release
a claim, cancel a task, revoke a binding), the host owner issues a
**break-glass key**: a short-lived Control Plane admin key for a person
(CP-ADR-0065). There is no API for this: the command runs in the
`control-plane-api` container, and the shell on the host is the trust
boundary.

```bash
# the operator principal is cpOperatorPrincipalId in deploy/state/<env>.json
PRINCIPAL=$(python3 -c 'import json;print(json.load(open("deploy/state/taimen.json"))["cpOperatorPrincipalId"])')
tools/compose exec -e BREAK_GLASS_OPERATOR="$(whoami)" control-plane-api \
  python -m control_plane.break_glass issue --principal "$PRINCIPAL" --ttl 3600 \
  --reason "IAM unavailable, <incident number>"
```

The `cp_bg…` key is printed once. You use it like a regular Bearer token
(`Authorization: Bearer cp_bg…`), including when
`CP_LEGACY_API_KEYS_ENABLED=false`; regular legacy keys are still not
accepted in that case.

| Constraint | Value |
|---|---|
| For whom | only an active principal of kind `human` |
| Permissions | `admin` |
| Lifetime | `--ttl` from 60 s to `CP_BREAK_GLASS_MAX_TTL_SECONDS` (4 h); 1 h by default |
| Audit | the `api_key.break_glass_issued` event: principal, prefix, lifetime, reason, who issued it |
| Kill switch | `CP_BREAK_GLASS_ENABLED=false`: neither issuance nor acceptance of issued keys |

As soon as IAM is back up, revoke all break-glass keys:

```bash
tools/compose exec control-plane-api python -m control_plane.break_glass revoke
```

## Control Plane is not ready

**Assessment:** `curl -s http://127.0.0.1:18000/health/ready`.

| Response | Cause | Action |
|---|---|---|
| `503 database_unreachable` | The database is unavailable | `tools/compose ps control-plane-db`, logs, disk; `tools/compose up -d control-plane-db` |
| `503 migrations_pending` | The database revision does not equal the image's head | If the API does not start because of a migration error: `control-plane-api` logs, roll back the release; if the database revision is **newer** than the image, an old image is running on top of a new schema: bring back the new image or run a downgrade |
| No response | The container is in a restart loop | `tools/compose logs --tail 100 control-plane-api` |

While the API is not ready, `control-plane-worker` and `context-adapter` do
not start (the `service_healthy` dependency); this is a safeguard, not a
separate problem.

## Release rollback

The short version; the full one is in [Upgrades and migrations](upgrades.md).

```bash
cd /opt/taimen/src
# 1. If the new release applied migrations, downgrade with the NEW image
tools/compose stop control-plane-worker context-adapter control-plane-api
tools/compose run --rm --no-deps control-plane-api alembic downgrade <previous release revision>
# 2. Code and images of the previous release
git checkout <previous release commit> && git submodule update --init --recursive
tools/compose --profile core --profile edge build     # or the previous IMAGE_TAG without a build
tools/compose --profile core --profile edge up -d
make smoke
```

If a downgrade is impossible, restore the database from the backup taken
before the release (see [Backup](backup.md)).

## Loss of the runner host

**Assessment.** The machine is unavailable or compromised. It held: the
executor PAT, the coding agent's subscription token, the forge token, and
working copies with unpublished changes.

**What happens to tasks.** The executor's claims expire by lease
(`CP_CLAIM_TTL_SECONDS`, 300 s by default), after which another executor can
claim the task (takeover). An unfinished run stays in `running` status; when
an executor with the same principal starts again, it finds its orphaned run
through `/api/v1/harness/context` and closes it with
`failure_reason=restart_recovery`, returning the task to the queue.

**Steps.**

1. **If the loss is uncontrolled** (theft, a break-in, access by outsiders),
   consider all secrets on the host compromised:
    - revoke the executor's binding in Control Plane (closes access
      immediately): `POST /api/v1/iam-bindings/<binding-id>:revoke`;
    - revoke the executor's PAT in IAM (`…/platform-access-tokens/<id>:revoke`);
    - revoke the subscription token at the provider and the forge token in
      the forge.
2. Bring up a new executor machine the same way as the previous one.
3. Issue a new PAT to the executor (see [Secrets and rotation](secrets.md));
   if the binding was revoked, create it again with
   `POST /api/v1/principals/<principal-id>/iam-bindings` and the previous
   permissions.
4. Start the executor. Check in the logs that orphaned runs were closed with
   `restart_recovery` and the tasks returned to the queue.
5. Unpublished work is lost; published `task/<id>` branches are in the forge
   and available for review.

**Stop an executor in an emergency, without investigating:**

=== "Container"

    ```bash
    docker compose -f <executor compose file> stop
    ```

=== "systemd"

    ```bash
    systemctl stop <unit> && systemctl disable <unit>
    ```

Stopping is safe at any moment: the run is closed with `restart_recovery`
at the next start, and the working copy is preserved.

## Credential compromise

### A person's or an agent's PAT

| Step | Command | Effect |
|---|---|---|
| 1. Close access to Control Plane | `POST /api/v1/iam-bindings/<binding-id>:revoke` | Immediate: the binding cache is reset in the API process |
| 2. Revoke the PAT | `POST …/tenants/<t>/platform-access-tokens/<id>:revoke?reason=leaked` (bootstrap) or `POST /api/v1/platform-access-tokens:revoke-self` (owner) | New exchanges are impossible |
| 3. Assess the consequences | IAM audit (`platform_access_tokens.exchange` by PAT prefix), the Control Plane event log by principal | Find out what was done with the stolen token |
| 4. Restore access | New PAT, another `POST /api/v1/principals/<id>/iam-bindings` | The owner continues working |

Access tokens already issued for this PAT live up to 300 s; step 1 closes
them in Control Plane earlier. If the PAT had `control-plane:admin`, check
the log for principals, bindings, and catalog changes created during the
leak period.

### IAM bootstrap token

`IAM_BOOTSTRAP_TOKEN` lets you issue a PAT to any principal; this is an
incident of the highest severity.


1. Change the value in `.env` to a new random one (`openssl rand -hex 24`),
   then `tools/compose up -d iam-service`.
2. Export the PAT list (`GET …/platform-access-tokens?includeRevoked=true`)
   and the IAM audit; revoke everything that was issued by someone other
   than you after the likely moment of the leak.
3. Check service accounts created during the same period and revoke the
   extra ones (`…/service-accounts/<client-id>:revoke`).

### IAM signing key

It lets an attacker forge an access token for any principal. Rotate the key
immediately and restart the services that verify tokens; see
[Secrets and rotation](secrets.md).

### Service account secret

```bash
# core: bootstrap reissues it and revokes the previous one
mv secrets/control-plane-iam.env /tmp/ && python3 deploy/bootstrap.py --env .env --name <env>
tools/compose up -d control-plane-api control-plane-worker context-adapter
```

For other service accounts: revoke in IAM and reissue; see
[Secrets and rotation](secrets.md).

### `MEMORY_API_KEY`, LLM provider key, database passwords

Change the value (for database passwords, `ALTER ROLE` in the database
first), update `.env`, recreate the consumers. The procedures are in
[Secrets and rotation](secrets.md).

## Edge unavailable or certificate expired

Everything inside the host keeps working. For operational tasks, use the
ports on `127.0.0.1` through an SSH tunnel:

```bash
ssh -N -L 18000:127.0.0.1:18000 -L 18010:127.0.0.1:18010 <platform host>
curl -s http://127.0.0.1:18000/health/ready
```

!!! tip "Tunnels in an ssh alias"
    If `~/.ssh/config` defines `LocalForward` for the host and the ports are
    already taken by another session, ssh fails entirely (`bind … Address
    already in use`), along with the command you connected for. Connect
    with `ssh -o ClearAllForwardings=yes <alias>`; for git over such an
    alias, use `GIT_SSH_COMMAND='ssh -o ClearAllForwardings=yes'`.

Causes and certificate fixes are in [Edge and TLS](edge-and-tls.md).

## Disk full

PostgreSQL stops accepting writes, and services return `5xx`.

```bash
df -h /var/lib/docker
docker system df
docker builder prune -f            # build cache
docker image prune -f              # dangling images
journalctl --vacuum-size=500M
```

Then find the growing object (see [Resources and scaling](capacity.md)) and
set up an alert on disk usage. Do not delete files inside database volumes
by hand.

## Changing the public address (issuer)

Not an emergency, but a procedure that risks locking everyone out: the IAM
issuer equals `${TAIMEN_PUBLIC_URL}/iam`, and Control Plane looks up a
binding by the pair `(issuer, iam_principal_id)`.


1. **Before the switch**, while the old address works, create a binding with
   the new issuer for each principal using the same call,
   `POST /api/v1/principals/<principal-id>/iam-bindings`, with
   `"issuer": "https://new.example.com/iam"` and the previous permissions.
   The old bindings remain and do not interfere.
2. Configure DNS and the Caddyfile for the new name, wait for the
   certificate.
3. Change `TAIMEN_PUBLIC_URL` and `TAIMEN_PUBLIC_HOST` in `.env`.
4. Recreate the services so they pick up the new address:
   `tools/compose … up -d`.
5. If the `idp` profile is running, update the redirect URIs of the console
   and assistant clients in Keycloak (for the console, run
   `deploy/keycloak/keycloak-runtime-console-client.py` with the new
   `WEB_BASE_URL`; for the others, use the Admin API or the Keycloak admin
   console; the realm template is not applied to an existing realm). The
   Keycloak issuer changes too: the identity provider in IAM and the people's
   external identities are recorded with the old issuer, and the provider
   cannot be changed through the API (see [Identity federation](../iam/federation.md)).
6. Update `CONTROL_PLANE_SERVER` and `CONTROL_PLANE_IAM_URL` for executors
   and operators. The record key in `credentials.json` includes the IAM
   address, so move the records under the new address.
7. After verification, revoke the bindings with the old issuer.

If step 1 was skipped and access is already closed, move the bindings with
SQL in the Control Plane database:

```sql
UPDATE iam_principal_bindings
   SET issuer = 'https://new.example.com/iam', updated_at = now()
 WHERE issuer = 'https://old.example.com/iam';
```

After editing the database behind the API's back, Control Plane may keep
answering with a cached refusal for up to
`CP_IAM_BINDING_STALE_AFTER_SECONDS` (120 s by default); to avoid waiting,
restart `control-plane-api`.

## After the incident

- Record the timeline, the affected components, and the measures taken.
- Check `make smoke`, `/health/ready`, `context_adapter_parked_tenants`.
- If credentials were revoked, make sure all legitimate clients received new
  ones and are working.
- Add an alert that would have caught the incident earlier (see
  [Monitoring and health](monitoring.md)).

## See also

- [Secrets and rotation](secrets.md)
- [Backup](backup.md)
- [Upgrades and migrations](upgrades.md)
- [Execution and claims](../control-plane/execution.md)
- [Troubleshooting](../troubleshooting/index.md)
