#!/usr/bin/env python3
"""Idempotent bootstrap of the Taimen platform (make bootstrap).

Initial setup of IAM, the Control Plane and the platform services in one pass:

  1. waits for the Control Plane and IAM to be ready on the 127.0.0.1 ports;
  2. IAM: the tenant, audiences by the AUDIENCES registry (missing scopes are added, foreign
     ones are not taken away — the sync only adds; --prune-scopes removes the scopes that are
     not in the registry from the registry's audiences), the operator's human principal;
  2b. groups of privileged scopes (source=local) with the operator: `people-admins` — federation
     gives the operator `iam:people` (managing people in the console), `fleet-admins` —
     `fleet:admin` (node join keys). Such a scope is issued by federation only to a member of
     the group and only on an explicit request; a PAT never carries it;
  2c. (--identity-provider) an IAM identity provider from a description file and the link of the
     operator's `sub` at that IdP to the operator's principal;
  2a. IAM: the Control Plane service account (memory) → secrets/control-plane-iam.env;
  3. Control Plane: POST /api/v1/bootstrap with the operator's `iamBinding` → the tenant (the
     same UUID as in IAM), the admin principal and the first IAM↔CP binding in one transaction;
     the legacy api-key from the response is revoked at the end: the installation is IAM-only;
  4. a fresh authentication context (not older than 300 s) → the operator's Platform Access Token
     with the read/write/admin ceiling → secrets/harness-pat (0600);
  5. the PAT is exchanged for an access token of the control-plane audience, and through it:
     the project template, the project and the workspace. An access token lives minutes and
     step 5b may take longer, so bootstrap holds a token provider, not a header
     (`package_sdk.auth.Bearer`): `Authorization` is set before every request to the core and
     to the notification service, and the token is exchanged again before it expires (and once
     after `401 invalid_credentials`);
  5b. packages by the installation file (--packages, default deploy/packages.yaml) as one
     installation plan of the package SDK (sdk/package-sdk): `install.plan()` writes the plan
     to deploy/state/<env>.packages-plan.json and `install.apply()` applies exactly that plan —
     the catalog, processes and calendars, ontologies, notification rules and `retire` of the
     installation file. Running the initial setup stands for the human's confirmation here
     (assume_yes, marked in the log); an empty plan is not applied. --no-packages skips the
     step: on a running installation packages are installed by a human — plan → review → apply;
  5c, 5d. platform services — notification-service and fleet-controller: an IAM service
     account by the service's description (SERVICE_AGENTS below; a changed ceiling or a lost
     env file is a PATCH that keeps the principal), the description published in the core and
     its identity in the agent registry — `PUT /agents/{key}/identity` (the first link or the
     same account); an account created anew (the previous one is gone from IAM) —
     `POST /agents/{key}/identity:replace`. Secrets → secrets/notification-iam.env and
     secrets/fleet-iam.env (the services pick them up on `up -d`);
  8. (--harness-people) personal assistants: a PAT of each person → their credentials.json,
     the launcher's cookie key and the people registry secrets/harness/people.json.

`TAIMEN_PUBLIC_URL` must not end with `/`: the issuer `${TAIMEN_PUBLIC_URL}/iam` must match
`CP_IAM_ISSUER` of compose character by character, so a value with `/` is refused.

State lives in deploy/state/<env>.json: the identifiers are not secret; a repeated run skips
what is done and brings the mutable parts (audience ceilings, service accounts, the catalog) in
line with the registries in this script and the packages. Secrets are never printed. HTTP uses
the Python standard library; the package SDK needs PyYAML and jsonschema (`make bootstrap`
provides them through uv):

    uv run --no-project --with pyyaml --with jsonschema python3 deploy/bootstrap.py --env .env
    python3 deploy/bootstrap.py --env .env --dry-run        # what steps 2–2c would change, no writes
    python3 deploy/bootstrap.py --env .env --prune-scopes   # remove scopes outside the registry
    python3 deploy/bootstrap.py --env .env --harness-people deploy/harness-people.json
"""

from __future__ import annotations

import argparse
import errno
import importlib.util
import json
import os
import stat
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The package SDK (the sdk/package-sdk submodule) plans and applies the packages at step 5b and
# provides the token provider of the core's requests.
PACKAGE_SDK_SRC = ROOT / "sdk" / "package-sdk" / "src"
# Python modules the package SDK needs: import name → package name.
PACKAGE_SDK_MODULES = {"yaml": "PyYAML", "jsonschema": "jsonschema"}

sys.path.insert(0, str(PACKAGE_SDK_SRC))
try:
    from package_sdk import install as package_install  # noqa: E402
    from package_sdk import model as package_model  # noqa: E402
    from package_sdk.apply import Http as PackageHttp  # noqa: E402
    from package_sdk.apply import HttpError as PackageHttpError  # noqa: E402
    from package_sdk.auth import Authorized, Bearer  # noqa: E402
    from package_sdk.install.plan import needs_notify  # noqa: E402
except ImportError as error:  # require_package_sdk() explains it before the first step
    PACKAGE_SDK_IMPORT_ERROR: ImportError | None = error
else:
    PACKAGE_SDK_IMPORT_ERROR = None
    # The root of the tool is this repository, however bootstrap is started.
    package_model.ROOT = ROOT
    package_model.PACKAGES_DIR = ROOT / "packages"

# IAM audiences and their scope ceilings: one token — one service.
AUDIENCES = {
    # control-plane:decide — deciding a single approval from a notification channel
    "control-plane": ["control-plane:read", "control-plane:write", "control-plane:admin", "control-plane:decide"],
    # memory:tenants and memory:service — only the core's service account;
    # memory:on-behalf — a service reads memory on behalf of a principal
    "memory-service": [
        "memory:read",
        "memory:write",
        "memory:pii",
        "memory:tenants",
        "memory:on-behalf",
        "memory:service",
    ],
    # send — senders, read — a person's inbox, admin — mandatory rules and channel groups
    "notification-service": ["notifications:send", "notifications:read", "notifications:admin"],
    # IAM itself as an audience: iam:channel-links — the notification service confirms channel
    # links; iam:agents — fleet-controller creates agents and their PATs; iam:people — the
    # people administrator in the console (federation gives it only to a member of
    # people-admins and only on an explicit request; never to a PAT or a service account);
    # iam:identities.link — a connector matches people of an external system to principals
    "iam": ["iam:channel-links", "iam:agents", "iam:people", "iam:identities.link"],
    # the launcher of personal assistants: use — a person signs in (federation: the console's
    # assistant), inbound — channels (notification-service) pass text into a conversation
    "human-harness": ["harness:use", "harness:inbound"],
    # fleet-controller: read — nodes and placements, admin — node join keys. The console gets
    # them for a person through federation:exchange
    "fleet": ["fleet:read", "fleet:admin"],
}
# Groups of privileged scopes: only bootstrap creates them (source=local) — federation and
# SCIM do not create a group with such a key, otherwise the IdP would hand out administrator
# rights. The scope is issued by federation only to a member of the group and only on an
# explicit request; a PAT never carries it. The operator is a local member; others come
# through the IdP's groupMappings. The group keys are built into IAM.
PEOPLE_ADMINS = {"key": "people-admins", "name": "People admins"}
FLEET_ADMINS = {"key": "fleet-admins", "name": "Fleet admins"}
# scope → (group, state key of the group id, state key of the members)
PRIVILEGED_GROUPS = {
    "iam:people": (PEOPLE_ADMINS, "iamPeopleAdminsGroupId", "iamPeopleAdminsMembers"),
    "fleet:admin": (FLEET_ADMINS, "iamFleetAdminsGroupId", "iamFleetAdminsMembers"),
}

# Control Plane service account: context-adapter writes the memory of all tenants. The secret
# lives only in secrets/control-plane-iam.env (env_file of the three core processes).
CP_SERVICE_ACCOUNT = {
    "displayName": "Taimen Control Plane",
    "audiences": ["memory-service"],
    "scopeCeiling": ["memory:read", "memory:write", "memory:tenants", "memory:on-behalf", "memory:service"],
}

# Platform services with IAM client credentials (notification-service, fleet-controller) are
# agents without placement, with an identity of kind service: the description in the core
# defines their permissions, its IAM part is the service account. Secrets — only in
# secrets/<service>-iam.env (env_file of the service).
SERVICE_AGENTS = {
    # Events and the core's recipient directory, channel links and button presses in IAM,
    # Telegram as an entry into an assistant conversation.
    "notification-service": {
        "displayName": "Taimen Notification Service",
        "identity": {
            "kind": "service",
            "permissions": ["events.read", "approvals.read", "tasks.read", "principals.read", "workspaces.read"],
            "iam": {
                "audiences": ["control-plane", "iam", "human-harness"],
                "scopeCeiling": ["control-plane:read", "iam:channel-links", "harness:inbound"],
            },
        },
        "placement": "none",
    },
    # Agents and their actual state in the core, IAM agents and their PATs (iam:agents); the
    # ceiling of agent PATs is never wider than this account.
    "fleet-controller": {
        "displayName": "Taimen Fleet Controller",
        "identity": {
            "kind": "service",
            "permissions": ["agents.read", "agents.status.write"],
            "iam": {
                "audiences": ["control-plane", "iam", "notification-service"],
                "scopeCeiling": ["control-plane:read", "control-plane:write", "iam:agents", "notifications:send"],
            },
        },
        "placement": "none",
    },
}
# Scopes beyond the description: they belong to the IAM part of the service account but not to
# the description in the core — the core accepts scopes only of the form <audience>:<action>
# without a dot, and iam:identities.link has one.
SERVICE_EXTRA_SCOPES = {
    # fleet-controller issues agent PATs no wider than its own account: without this scope a
    # connector with identity.iam.scopeCeiling [iam:identities.link] would not get it.
    "fleet-controller": ["iam:identities.link"],
}


def service_agent(key: str) -> dict:
    """The description of a platform service: {key, spec} (kind Agent, identity of kind service)."""
    return {"key": key, "spec": SERVICE_AGENTS[key]}


def service_account_ceiling(account: dict) -> list[str]:
    """The fingerprint of an account in the state: scopes and audiences. A mismatch with the code
    is a PATCH of the ceiling of the existing service account; the principal stays."""
    return sorted(account["scopeCeiling"]) + sorted(account["audiences"])


def service_account_for(key: str) -> dict:
    """The IAM part of a service's account: identity.iam of its description plus SERVICE_EXTRA_SCOPES."""
    spec = SERVICE_AGENTS[key]
    iam = spec["identity"]["iam"]
    extra = [scope for scope in SERVICE_EXTRA_SCOPES.get(key, []) if scope not in iam["scopeCeiling"]]
    return {
        "displayName": spec["displayName"],
        "audiences": iam["audiences"],
        "scopeCeiling": [*iam["scopeCeiling"], *extra],
    }


class HttpError(RuntimeError):
    """A 4xx/5xx response. The text is `METHOD path: HTTP code: body`; plus the status, `detail`
    (the IAM format) and the error code (the core's envelope `{"error": {"code": …}}`, otherwise
    the same `detail`): decisions are made by them, not by a substring."""

    def __init__(self, method: str, path: str, status: int, body: str) -> None:
        super().__init__(f"{method} {path}: HTTP {status}: {body[:400]}")
        self.status = status
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = None
        detail = parsed.get("detail") if isinstance(parsed, dict) else None
        self.detail = detail if isinstance(detail, str) else None
        envelope = parsed.get("error") if isinstance(parsed, dict) else None
        code = envelope.get("code") if isinstance(envelope, dict) else None
        self.code = code if isinstance(code, str) else self.detail


class Http:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")

    def call(self, method: str, path: str, body: dict | str | None = None, headers: dict | None = None) -> dict:
        # A string goes as is, a dictionary as JSON.
        if body is None:
            data = None
        elif isinstance(body, str):
            data = body.encode()
        else:
            data = json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if not any(key.lower() == "content-type" for key in (headers or {})):
            req.add_header("Content-Type", "application/json")
        for key, value in (headers or {}).items():
            req.add_header(key, value)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            raise HttpError(method, path, error.code, error.read().decode(errors="replace")) from error

    def wait(self, path: str, timeout: int = 180) -> None:
        deadline = time.time() + timeout
        while True:
            try:
                with urllib.request.urlopen(self.base + path, timeout=5) as response:
                    if response.status < 400:
                        return
            except (urllib.error.URLError, OSError):
                pass
            if time.time() >= deadline:
                raise SystemExit(f"timed out waiting for {self.base}{path}")
            time.sleep(2)


def read_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def require_package_sdk() -> None:
    """Fail before the first write if the package SDK cannot run: better than a half-done bootstrap."""
    if not (PACKAGE_SDK_SRC / "package_sdk").is_dir():
        raise SystemExit(
            "there is no sdk/package-sdk submodule: bootstrap needs the package SDK — run `make submodules`"
        )
    missing = [name for module, name in PACKAGE_SDK_MODULES.items() if importlib.util.find_spec(module) is None]
    if missing:
        raise SystemExit(
            f"{' and '.join(missing)} required by the package SDK: install uv and run "
            "`make bootstrap`, or `pip install pyyaml jsonschema` for this python3"
        )
    if PACKAGE_SDK_IMPORT_ERROR is not None:
        raise SystemExit(
            f"the package SDK in sdk/package-sdk does not import ({PACKAGE_SDK_IMPORT_ERROR}): "
            "update the submodules (`make submodules`)"
        )


# Where a symbolic link inside the secrets directory may lead: --secrets-link-root adds roots.
# Roots of secret writes: main() puts realpath(--secrets-dir) and the link roots here. Empty
# (functions called without main, tests) — the only root is the file's own directory.
SECRET_ROOTS: list[Path] = []


def set_secret_roots(secrets_dir: Path, link_roots=()) -> list[Path]:
    SECRET_ROOTS[:] = [Path(os.path.realpath(root)) for root in (secrets_dir, *link_roots)]
    return SECRET_ROOTS


def _secret_target_and_root(path: Path, roots=None) -> tuple[Path, Path]:
    target = Path(os.path.realpath(path))
    allowed = [Path(os.path.realpath(root)) for root in (roots if roots is not None else SECRET_ROOTS or [path.parent])]
    inside = [root for root in allowed if target == root or root in target.parents]
    if not inside:
        raise SystemExit(
            f"{path} leads to {target} — outside the secrets directory ({', '.join(map(str, allowed))}). "
            "Writing the secret stopped, nothing created. If the link is intended, add its root: "
            "--secrets-link-root <directory>."
        )
    return target, max(inside, key=lambda root: len(root.parts))


def secret_target(path: Path, roots=None) -> Path:
    """Where a write to `path` actually goes: realpath, and only inside the allowed roots.

    A link in the secrets directory leading out of it (or out of an explicit link root) stops
    the run: the secret would go into a foreign file, and a bootstrap running as root would
    rewrite it with mode 0600. A dangling link is checked the same way, and the directories of
    its target are not created."""
    return _secret_target_and_root(path, roots)[0]


_NOFOLLOW_DIR = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _open_parent(target: Path, root: Path) -> int:
    """The target's directory — from the root one component at a time, each with `O_NOFOLLOW`:
    a directory inside the root replaced by a link between the check and the write gives
    ELOOP/ENOTDIR, not a write outside the root. Missing directories are created the same way."""
    root.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        for part in target.parent.relative_to(root).parts:
            try:
                os.mkdir(part, dir_fd=descriptor)
            except FileExistsError:
                pass
            child = os.open(part, _NOFOLLOW_DIR, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def secure_write(path: Path, value: str, *, roots=None) -> None:
    """Atomic write of a secret with mode 0600: either the previous file or the new one in full.

    An incomplete env file is worse than a missing one: the next bootstrap sees the file and
    does not ask for a new secret. Hence a temporary file next to it (`O_EXCL`, 0600), `fsync`,
    `os.replace`, `fsync` of the directory. The mode and the owner are set explicitly: the
    previous file could have another mode or belong to the container's uid. A link to a secret
    is not replaced by a file — its target is written if it is inside the allowed roots
    (`secret_target`), checked before any directory is created."""
    target, root = _secret_target_and_root(path, roots)
    folder = _open_parent(target, root)
    name = target.name
    temporary = f".{name}.{uuid.uuid4().hex}.tmp"
    try:
        for stale in os.listdir(folder):  # a trace of a killed process
            if stale.startswith(f".{name}.") and stale.endswith(".tmp"):
                os.unlink(stale, dir_fd=folder)
        try:
            owner = os.stat(name, dir_fd=folder, follow_symlinks=False)
        except FileNotFoundError:
            owner = None
        descriptor = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=folder
        )
        try:
            try:
                os.fchmod(descriptor, 0o600)
                if owner is not None and (owner.st_uid, owner.st_gid) != (os.geteuid(), os.getegid()):
                    os.fchown(descriptor, owner.st_uid, owner.st_gid)
                data = memoryview(value.encode())
                while data:
                    data = data[os.write(descriptor, data) :]
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            os.replace(temporary, name, src_dir_fd=folder, dst_dir_fd=folder)
        except BaseException:
            try:
                os.unlink(temporary, dir_fd=folder)
            except FileNotFoundError:
                pass
            raise
        _fsync_descriptor(folder)
    finally:
        os.close(folder)


def _fsync_descriptor(descriptor: int) -> None:
    """The name written by `os.replace` — to disk. Where a directory cannot be synced
    (EINVAL/ENOTSUP), silently: the file is in place, and the rename is atomic anyway."""
    try:
        os.fsync(descriptor)
    except OSError as error:
        if error.errno not in (errno.EINVAL, errno.ENOTSUP, errno.EBADF):
            raise


def issue_pat(
    iam: Http,
    bootstrap: dict,
    *,
    tenant: str,
    principal: str,
    name: str,
    ceiling: list[str],
    ttl: int,
    audiences: list[str] | None = None,
) -> dict:
    return iam.call(
        "POST",
        f"/api/v1/tenants/{tenant}/principals/{principal}/platform-access-tokens",
        {"name": name, "audiences": audiences or ["control-plane"], "scopeCeiling": ceiling, "expiresInSeconds": ttl},
        {**bootstrap, "Idempotency-Key": str(uuid.uuid4())},
    )


CONTAINER_UID = 10001


def hand_to_container_uid(*paths: Path) -> None:
    """Containers that read these files run as uid 10001: on Linux the files written by a
    bootstrap running as root become theirs. Links are neither touched nor followed
    (`follow_symlinks=False`): a link in the secrets directory must not hand a foreign file to
    the container's uid; the owner of its target is set by hand."""
    if not (hasattr(os, "geteuid") and os.geteuid() == 0):
        if sys.platform.startswith("linux"):
            print(f"   on Linux: chown {CONTAINER_UID}:{CONTAINER_UID}", *paths)
        return
    for path in paths:
        info = os.lstat(path)
        if stat.S_ISLNK(info.st_mode):
            print(f"   !! {path} is a link: set the owner of its target ({CONTAINER_UID}) by hand")
            continue
        if (info.st_uid, info.st_gid) != (CONTAINER_UID, CONTAINER_UID):
            os.chown(path, CONTAINER_UID, CONTAINER_UID, follow_symlinks=False)


def hand_tree_to_container_uid(base: Path) -> None:
    """A tree of the secrets directory goes to the container's uid (personal assistants). The walk
    does not follow links, and links themselves are not touched (`hand_to_container_uid`)."""
    if os.path.islink(base):
        print(f"   !! {base} is a link: set the owner of its target ({CONTAINER_UID}) by hand")
        return
    paths = [base]
    for folder, directories, files in os.walk(base, followlinks=False):
        paths += [Path(folder) / name for name in sorted(directories) + sorted(files)]
    hand_to_container_uid(*paths)


SA_PATCH_REQUIRED = (
    "IAM does not accept a PATCH of a service account: iam-service must be able to change a "
    "ceiling while keeping the principal. Update iam-service and repeat bootstrap. A new service "
    "account is not created instead of the previous one: fleet-controller's agents would stay "
    "with the old owner (403 agent_not_owned)."
)


def patch_service_account(
    iam: Http,
    bootstrap_header: dict,
    iam_tenant: str,
    client_id: str,
    body: dict,
    *,
    attempts: int = 3,
    delay: float = 1.0,
) -> dict:
    """PATCH of a service account. A lost response (a broken connection, a timeout) is repeated
    with the same body: the ceiling is idempotent, and `rotateSecret` issues one more secret —
    the previous one, which we have not seen, expired in the same commit."""
    path = f"/api/v1/tenants/{iam_tenant}/service-accounts/{client_id}"
    for attempt in range(1, attempts + 1):
        try:
            return iam.call("PATCH", path, body, bootstrap_header)
        except HttpError:
            raise
        except OSError as error:  # URLError, a timeout, a reset connection — there is no response
            if attempt == attempts:
                raise
            print(f"   the IAM response to PATCH was lost ({type(error).__name__}) — retry {attempt + 1}/{attempts}")
            time.sleep(delay)
    raise AssertionError("unreachable")


def ensure_service_account(
    iam: Http,
    bootstrap_header: dict,
    iam_tenant: str,
    account: dict,
    state: dict,
    save,
    *,
    prefix: str,
    principal_key: str,
    env_file: Path,
    env_lines,
) -> set[str]:
    """A service account in IAM by the description `account` (displayName, audiences, scopeCeiling).

    State — `<prefix>ServiceAccountClientId`, `<prefix>ServiceAccountCeiling` and `principal_key`;
    the secret — only in the env file (`env_lines(issued)`).

    - no account in the state → POST (the first creation);
    - the fingerprint (scopes + audiences) differs from the code → PATCH with the full
      `{audiences, scopeCeiling}`: the principal, the client id and the env file stay,
      fleet-controller's agents stay its agents;
    - no env file → PATCH `{"rotateSecret": true}` (together with the ceiling if it differs too),
      the new secret goes into the env file right away;
    - an account in the state → every run starts with a reconciliation by an empty `PATCH {}`
      (IAM writes nothing and returns the account): a principal other than the one in the state
      stops the run before any write — the client id in the state belongs to another account;
    - IAM answers `404 service_account_not_found` or `409 service_account_revoked` → POST of a
      new account (there is no previous one to revoke);
    - there is no PATCH route (405, or 404 without `service_account_not_found`) → stop
      (SA_PATCH_REQUIRED), no silent switch to POST.

    Returns what was done: a subset of {"created", "updated", "rotated"}."""
    client_key, ceiling_key = f"{prefix}ServiceAccountClientId", f"{prefix}ServiceAccountCeiling"
    ceiling = service_account_ceiling(account)
    done: set[str] = set()
    client_id = state.get(client_key)
    if client_id:
        body: dict = {}
        if state.get(ceiling_key) != ceiling:
            body = {
                "audiences": sorted(set(account["audiences"])),
                "scopeCeiling": sorted(set(account["scopeCeiling"])),
            }
            print("   the ceiling or the audiences changed — PATCH of the ceiling, the principal stays")
        if not env_file.exists():
            body["rotateSecret"] = True
            print("   no", env_file, "— a new secret of the same account (rotateSecret)")
        known = state.get(principal_key)
        changes = dict(body)

        def check_principal(view: dict, stage: str, *, written: bool = False) -> None:
            if known and view.get("principalId") != known:
                raise SystemExit(
                    f"IAM returned principal {view.get('principalId')} for service account {client_id} "
                    f"on {stage}, and the state has {known}: the state is not of this account (another IAM "
                    f"or tenant, a wrong state restored). Bootstrap stopped, {env_file} and the state are "
                    "untouched"
                    + (
                        ", the secret in IAM did not change; the ceiling of this account in IAM is already replaced."
                        if written
                        else ", nothing changed in IAM."
                    )
                    + " Reconcile IAM and deploy/state."
                )

        try:
            # A reconciliation first — on every run: an empty PATCH writes nothing and returns the
            # account. This way a revoked or deleted account with a living env file and a foreign
            # principal are both visible before the ceiling or the secret change.
            try:
                view = patch_service_account(iam, bootstrap_header, iam_tenant, client_id, {})
            except HttpError as error:
                # IAM checks the final state of the account against the audience registry even on
                # an empty PATCH: the code narrowed the ceiling, sync_audiences has already removed
                # the scope from allowedScopes — the previous ceiling is outside the registry (422).
                # Then PATCH just the new ceiling (without rotateSecret), the principal by its response.
                ceiling_only = {k: changes[k] for k in ("audiences", "scopeCeiling") if k in changes}
                if not (
                    error.status == 422
                    and error.detail in ("invalid_scope_ceiling", "unknown_audience")
                    and ceiling_only
                ):
                    raise
                print(
                    f"   reconciliation: {error.detail} — the previous ceiling is outside the audience "
                    "registry, PATCH of the new ceiling without the secret, the principal by the response"
                )
                view = patch_service_account(iam, bootstrap_header, iam_tenant, client_id, ceiling_only)
                check_principal(view, "the PATCH of the ceiling", written=True)
                body = {k: v for k, v in body.items() if k not in ceiling_only}
            else:
                check_principal(view, "the reconciliation (PATCH {})")
            if body:  # the ceiling and/or the secret — only after the principal matches
                view = patch_service_account(iam, bootstrap_header, iam_tenant, client_id, body)
                check_principal(view, "PATCH")
        except HttpError as error:
            if (error.status, error.detail) in {(404, "service_account_not_found"), (409, "service_account_revoked")}:
                print(f"   service account {client_id}: {error.detail} — a new one is created")
                client_id = None
            elif error.status in (404, 405):
                raise SystemExit(f"{SA_PATCH_REQUIRED} [{error}]") from error
            else:
                raise
        else:
            if changes.get("rotateSecret"):
                if not view.get("clientSecret"):
                    raise SystemExit(f"IAM did not return clientSecret on rotateSecret. {SA_PATCH_REQUIRED}")
                secure_write(
                    env_file,
                    env_lines(
                        {
                            "clientId": client_id,
                            "clientSecret": view["clientSecret"],
                            "principalId": view.get("principalId"),
                        }
                    ),
                )
                done.add("rotated")
            if "scopeCeiling" in changes:
                done.add("updated")
            if not known and view.get("principalId"):
                state[principal_key] = view["principalId"]
            if changes or not known:
                state[ceiling_key] = ceiling
                save()
    if not client_id:
        previous_principal = state.get(principal_key)
        issued = iam.call("POST", f"/api/v1/tenants/{iam_tenant}/service-accounts", account, bootstrap_header)
        check_identity_unique(state, principal_key, issued.get("principalId"), client_key, issued.get("clientId"))
        secure_write(env_file, env_lines(issued))
        state[client_key] = issued["clientId"]
        state[principal_key] = issued["principalId"]
        state[ceiling_key] = ceiling
        save()
        done.add("created")
        if previous_principal and previous_principal != issued["principalId"]:
            print(
                "   !! the principal of the account changed:",
                previous_principal,
                "→",
                issued["principalId"],
                "(the previous account is gone from IAM); whatever was held by the previous principal stays with it",
            )
    return done


def check_identity_unique(
    state: dict, principal_key: str, principal: str | None, client_key: str | None = None, client: str | None = None
) -> None:
    """The IAM principal and the client id of an account do not match other identities of the state.

    The core finds a binding by its identity, and `POST /principals/{id}/iam-bindings` moves an
    existing binding to a new principal without asking whose it was. If IAM gave a new account
    the principal of the operator or of another service, relinking would hand that entry to the
    service — so the run stops before the write."""
    principals = {
        key: value
        for key, value in state.items()
        if key != principal_key
        and isinstance(value, str)
        and (key.endswith("IamPrincipalId") or key in ("iamOperatorPrincipalId", "cpServiceAccountPrincipalId"))
    }
    clients = {
        key: value
        for key, value in state.items()
        if key != client_key and isinstance(value, str) and key.endswith("ServiceAccountClientId")
    }
    clashes = [key for key, value in principals.items() if principal and value == principal]
    clashes += [key for key, value in clients.items() if client and value == client]
    if clashes:
        raise SystemExit(
            f"IAM principal {principal} / client {client} of the account ({principal_key}) is already in the "
            f"state as {', '.join(sorted(clashes))}: this is a foreign identity. Bootstrap stopped before writing "
            "the env file, the state and the core's bindings; reconcile IAM and deploy/state."
        )


# The operator's PAT: the whole core. The installation's notification rules (NotificationRule)
# are applied to notification-service with a token of the notification-service audience and the
# notifications:admin scope — the PAT gets this audience only if step 5b installs or retires
# such rules (least privilege).
OPERATOR_PAT_AUDIENCES = ["control-plane"]
OPERATOR_PAT_CEILING = ["control-plane:read", "control-plane:write", "control-plane:admin"]
OPERATOR_PAT_NOTIFY_AUDIENCE = "notification-service"
OPERATOR_PAT_NOTIFY_SCOPES = ["notifications:admin"]
OPERATOR_EXCHANGE_SCOPES = ["control-plane:read", "control-plane:write", "control-plane:admin"]


def operator_pat_grant(installation: Path | None) -> tuple[list[str], list[str]]:
    """Audiences and the ceiling of the operator's PAT; the notification service audience only if
    the installation of step 5b (None — the step is skipped, --no-packages) has NotificationRule
    objects or retires them. Otherwise a token for the rules is NOTIFY_TOKEN."""
    audiences, ceiling = list(OPERATOR_PAT_AUDIENCES), list(OPERATOR_PAT_CEILING)
    if installation is not None and needs_notify(package_install.load(installation, strict=False).installation):
        audiences.append(OPERATOR_PAT_NOTIFY_AUDIENCE)
        ceiling += OPERATOR_PAT_NOTIFY_SCOPES
    return audiences, ceiling


def operator_bearer(iam: Http, pat: str, *, clock=time.monotonic) -> Bearer:
    """4. The provider of the operator's access token (audience control-plane) by the PAT: the
    exchange in IAM on the first request, then whenever the token is about to expire
    (`Bearer.expiring`, 30 s of margin) or the core answered `401 invalid_credentials`."""
    return Bearer.expiring(
        lambda: iam.call(
            "POST",
            "/api/v1/platform-access-tokens:exchange",
            {"token": pat, "audience": "control-plane", "scopes": list(OPERATOR_EXCHANGE_SCOPES)},
        ),
        clock=clock,
    )


def notify_bearer(iam: Http, pat: str, env: dict, *, pat_file: Path, clock=time.monotonic) -> Bearer:
    """The notification service credential for the installation's rules: NOTIFY_TOKEN, as with the
    package SDK CLI (static, its lifetime is on the human), otherwise an exchange of the operator's
    PAT for the notification-service audience — renewed before it expires as well."""
    if env.get(package_model.NOTIFY_TOKEN_ENV):
        return Bearer.static_token(env[package_model.NOTIFY_TOKEN_ENV])

    def exchange() -> dict:
        try:
            return iam.call(
                "POST",
                "/api/v1/platform-access-tokens:exchange",
                {"token": pat, "audience": package_model.NOTIFY_AUDIENCE, "scopes": list(package_model.NOTIFY_SCOPES)},
            )
        except RuntimeError as error:
            raise SystemExit(
                f"no token of the {package_model.NOTIFY_AUDIENCE} audience ({str(error)[:160]}): set "
                f"{package_model.NOTIFY_TOKEN_ENV} or reissue the operator's PAT with this audience — remove "
                f"{pat_file} and run bootstrap again (step 4 issues a PAT with the "
                f"{package_model.NOTIFY_AUDIENCE} audience when the installation of step 5b installs or "
                "retires notification rules)"
            ) from error

    return Bearer.expiring(exchange, clock=clock)


def package_target(
    cp_base: str, operator: Bearer, env: dict, installation: Path, notify: Bearer
) -> package_install.Target:
    """The target of the installation plan: the core by its 127.0.0.1 port and, if the
    installation has notification rules (or retires them), the notification service at
    NOTIFICATION_SERVICE_URL, as with the package SDK CLI. Credentials are token providers:
    `Target` wraps the transport in `Authorized`, and `Authorization` is taken before every
    request. The notification service token is taken right away — a failed exchange shows
    before the plan."""
    target = package_install.Target(server=cp_base, http=PackageHttp(cp_base), token=operator)
    loaded = package_install.load(installation, strict=False).installation
    if needs_notify(loaded):
        url = env.get(package_model.NOTIFY_URL_ENV)
        if not url:
            raise SystemExit(
                f"the installation {installation.name} has notification rules — set "
                f"{package_model.NOTIFY_URL_ENV} (the notification-service address)"
            )
        notify.token()
        target.notify = (PackageHttp(url), notify)
    return target


def install_packages(
    installation: Path, *, target: package_install.Target, env: dict, plan_path: Path, log=print
) -> dict:
    """5b. Packages as one installation plan: the plan is written to plan_path and exactly that
    plan is applied. Bootstrap is not interactive: assume_yes stands for the human's answer — the
    only way to install without a confirmation, and the log says so. A plan without changes is
    not applied, so a repeated bootstrap writes nothing."""
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    document = package_install.plan(installation, target=target, env=env, out=plan_path, log=log)
    changes = package_install.count_changes(document)
    summary = {
        "install": str(installation),
        "plan": str(plan_path),
        "planHash": document["planHash"],
        "changes": changes,
        "applied": False,
    }
    if not changes:
        log("the plan is empty: the installation already matches, nothing to apply")
        return summary
    log(
        f"bootstrap: plan {document['planHash']} ({changes} changes) is applied without a human's "
        "confirmation — running the initial setup is the operator's decision (assume_yes)"
    )
    package_install.apply(plan_path, target=target, env=env, assume_yes=True, log=log)
    summary["applied"] = True
    return summary


def audience_plan(
    current: dict[str, list[str]], registry: dict[str, list[str]] = AUDIENCES, *, prune: bool = False
) -> list[tuple[str, str, list[str], list[str]]]:
    """A plan to bring IAM audiences in line with the registry: (key, action, scopes, extra).

    The action is create (no audience), update (a registry scope is missing, or there are extra
    ones with prune) or ok. By default the registry only adds: a scope created outside the
    registry stays (and is named among the extra ones) so that bootstrap does not take it away
    from a running service. With prune the extra ones are removed. Audiences outside the
    registry are never touched."""
    plan = []
    for key, scopes in registry.items():
        if key not in current:
            plan.append((key, "create", list(scopes), []))
            continue
        have = list(current[key])
        extra = [scope for scope in have if scope not in scopes]
        wanted = list(scopes) if prune else list(scopes) + extra
        plan.append((key, "update" if set(wanted) != set(have) else "ok", wanted, extra))
    return plan


def list_audiences(iam: Http, header: dict, tenant: str) -> dict[str, list[str]]:
    try:
        listed = iam.call("GET", f"/api/v1/tenants/{tenant}/audiences", headers=header)
    except RuntimeError as error:
        if "HTTP 404" not in str(error):
            raise
        listed = []
    return {item["key"]: item.get("allowed_scopes", item.get("allowedScopes", [])) for item in listed or []}


def warn_privileged(added: dict[str, list[str]], *, dry_run: bool) -> None:
    """A loud warning: a privileged scope is safe only in an IAM that grants it by group."""
    privileged = sorted({scope for scopes in added.values() for scope in scopes if scope in PRIVILEGED_GROUPS})
    if not privileged:
        return
    groups = ", ".join(PRIVILEGED_GROUPS[scope][0]["key"] for scope in privileged)
    print("   " + "!" * 76)
    print(f"   !! privileged scopes {'will be added' if dry_run else 'are added'}: {', '.join(privileged)}")
    print(f"   !! Safe only if iam-service already grants them by group ({groups}) and on an explicit")
    print("   !! request. An older IAM would grant them to ANYONE who signs in through federation.")
    print("   !! Order: iam-service first, bootstrap second.")
    print("   " + "!" * 76)


def sync_audiences(
    iam: Http, header: dict, tenant: str, state: dict, save, *, dry_run: bool = False, prune: bool = False
) -> None:
    """Step 2: IAM audiences by the AUDIENCES registry — create the missing ones, add scopes.

    The sync only adds; with prune (--prune-scopes) it removes the scopes that are not in the
    registry from the registry's audiences and prints which."""
    current = list_audiences(iam, header, tenant)
    plan = audience_plan(current, prune=prune)
    warn_privileged(
        {key: sorted(set(scopes) - set(current.get(key, []))) for key, _, scopes, _ in plan}, dry_run=dry_run
    )
    for key, action, scopes, extra in plan:
        added = sorted(set(scopes) - set(current.get(key, [])))
        if extra and not prune:
            print(f"   audience {key}: outside the registry {', '.join(extra)} — kept (remove: --prune-scopes)")
        if action == "ok":
            continue
        if dry_run:
            if action == "create":
                print(f"   [dry-run] audience {key}: create {', '.join(added)}")
            else:
                if added:
                    print(f"   [dry-run] audience {key}: add {', '.join(added)}")
                if prune and extra:
                    print(f"   [dry-run] audience {key}: remove (--prune-scopes) {', '.join(extra)}")
            continue
        if action == "create":
            try:
                iam.call("POST", f"/api/v1/tenants/{tenant}/audiences", {"key": key, "allowedScopes": scopes}, header)
                print(f"   audience {key}: created ({', '.join(scopes)})")
                continue
            except RuntimeError as error:
                if "409" not in str(error):
                    raise
            # It appeared between GET and POST: read it again and reconcile by its real scopes —
            # a PATCH with the registry alone would take away what was created next to it.
            fresh = list_audiences(iam, header, tenant)
            if key not in fresh:
                raise SystemExit(
                    f"audience {key}: POST answered 409, but a repeated GET does not see it — repeat bootstrap"
                )
            current[key] = fresh[key]
            _, action, scopes, extra = audience_plan({key: fresh[key]}, {key: AUDIENCES[key]}, prune=prune)[0]
            added = sorted(set(scopes) - set(fresh[key]))
            if extra and not prune:
                print(f"   audience {key}: outside the registry {', '.join(extra)} — kept (remove: --prune-scopes)")
            if action == "ok":
                print(f"   audience {key}: already created in parallel (409), scopes in order")
                continue
        try:
            iam.call("PATCH", f"/api/v1/tenants/{tenant}/audiences/{key}", {"allowedScopes": scopes}, header)
            print(f"   audience {key}: added {', '.join(added) or '—'}")
            if prune and extra:
                print(f"   audience {key}: removed (--prune-scopes) {', '.join(extra)}")
        except RuntimeError as error:
            if "404" in str(error) or "405" in str(error):
                print(f"   !! IAM cannot PATCH audiences ({key}): update iam-service")
            else:
                raise
    if not dry_run:
        state["iamAudiences"] = sorted(set(state.get("iamAudiences", [])) | set(AUDIENCES))
        save()


def ensure_admin_group(
    iam: Http, header: dict, tenant: str, owner: str | None, state: dict, save, scope: str, *, dry_run: bool = False
) -> None:
    """The group of a privileged scope (source=local) and the tenant owner in it.

    IAM has no reading of groups by the bootstrap token, so the group id lives in the state.
    A repeat: the group and the membership from the state are skipped; 409 on the membership —
    already a member; 409 on the group without an id in the state — stop: an id must not be guessed."""
    group, id_key, members_key = PRIVILEGED_GROUPS[scope]
    key = group["key"]
    print(f"2b. group {key}: scope {scope} (federation — only to a member and on an explicit request)")
    group_id = state.get(id_key)
    if group_id is None:
        if dry_run:
            print(f"   [dry-run] create group {key} and add the owner {owner or '(the operator of step 2)'}")
            return
        try:
            created = iam.call("POST", f"/api/v1/tenants/{tenant}/groups", group, header)
        except RuntimeError as error:
            if "HTTP 409" not in str(error):
                raise
            raise SystemExit(
                f"group {key} already exists in IAM, but its id is not in the state (IAM does not list groups by "
                f"the bootstrap token). Find the id in the IAM database: SELECT id, source, status FROM groups "
                f"WHERE tenant_id = '{tenant}' AND key = '{key}'; make sure source = local, put it into "
                f'deploy/state/<env>.json as "{id_key}": "<id>" and repeat bootstrap'
            ) from error
        group_id = state[id_key] = created["id"]
        save()
        print("   group created:", group_id)
    members = list(state.get(members_key, []))
    if owner in members:
        print("   already done: the owner", owner, "is in group", group_id)
        return
    if dry_run:
        print(f"   [dry-run] add the owner {owner} to group {group_id}")
        return
    try:
        iam.call("POST", f"/api/v1/tenants/{tenant}/groups/{group_id}/members", {"principalId": owner}, header)
        print("   the owner", owner, "added to group", group_id)
    except RuntimeError as error:
        if "group_is_federated" in str(error):
            raise SystemExit(
                f"group {key} ({group_id}) is not local — {scope} is not granted through it; "
                "sort the group out in IAM before repeating"
            ) from error
        if "HTTP 409" not in str(error):
            raise
        print("   already done: the owner", owner, "is in group", group_id)
    state[members_key] = sorted({*members, owner})
    save()


def ensure_privileged_groups(
    iam: Http, header: dict, tenant: str, owner: str | None, state: dict, save, *, dry_run: bool = False
) -> None:
    """Step 2b: the groups of all privileged scopes of the registry (people-admins, fleet-admins)."""
    for scope in PRIVILEGED_GROUPS:
        ensure_admin_group(iam, header, tenant, owner, state, save, scope, dry_run=dry_run)


def load_identity_provider(path: Path, public_url: str) -> dict:
    """A description of an IAM identity provider (YAML): `identityProvider` — the body of POST
    /identity-providers, `operatorSubject` — the owner's `sub` at this IdP (optional).
    `${TAIMEN_PUBLIC_URL}` is substituted from .env."""
    import yaml  # noqa: PLC0415 — needed only here

    document = yaml.safe_load(path.read_text(encoding="utf-8").replace("${TAIMEN_PUBLIC_URL}", public_url))
    provider = document["identityProvider"]
    for field in ("key", "issuer", "audience"):
        if not provider.get(field):
            raise SystemExit(f"{path}: identityProvider.{field} is required")
    return {"identityProvider": provider, "operatorSubject": document.get("operatorSubject")}


def ensure_identity_provider(
    iam: Http, header: dict, tenant: str, spec: dict, owner: str | None, state: dict, save, *, dry_run: bool = False
) -> None:
    """Step 2c: an IAM identity provider and the link of the owner's `sub` to their principal
    before the first sign-in. The IAM API does not change a registered provider: a repeat skips
    it (409 — already there)."""
    provider = spec["identityProvider"]
    key, issuer = provider["key"], provider["issuer"].rstrip("/")
    print(f"2c. IAM identity provider {key} ({issuer}, audience {provider['audience']})")
    known = state.get("identityProviders", {})
    if key in known:
        print("   already done:", known[key])
    elif dry_run:
        print(f"   [dry-run] register provider {key}")
    else:
        try:
            created = iam.call("POST", f"/api/v1/tenants/{tenant}/identity-providers", provider, header)
            ident = created["id"]
            print("   registered:", ident)
        except RuntimeError as error:
            if "HTTP 409" not in str(error):
                raise
            ident = "exists"
            print("   already there (409): the IAM API does not change a provider — only a new key does")
            print(
                f"   !! compare the issuer of the registered provider {key} with {issuer}: if TAIMEN_PUBLIC_URL "
                "changed, IAM keeps the previous issuer and signing in through this IdP fails"
            )
        state["identityProviders"] = {**known, key: ident}
        save()
    subject = spec.get("operatorSubject")
    if not subject:
        return
    links = state.get("identityProviderOperatorLinks", {})
    if links.get(key) == subject:
        print("   already done: the owner", owner, "is linked to sub", subject)
        return
    if dry_run:
        print(f"   [dry-run] link the owner {owner} to ({issuer}, {subject})")
        return
    try:
        iam.call(
            "POST",
            f"/api/v1/tenants/{tenant}/principals/{owner}/external-identities",
            {"issuer": issuer, "subject": subject},
            header,
        )
        print("   the owner", owner, "is linked to sub", subject)
    except RuntimeError as error:
        if "HTTP 409" not in str(error) or "identity_provider_managed" in str(error):
            raise
        # 409 external_identity_exists: the link exists — with the owner or with a principal that
        # federation created on an earlier sign-in; the second case is sorted out by hand.
        print("   already there (409): identity", subject, "is linked — check that it is the owner's")
    state["identityProviderOperatorLinks"] = {**links, key: subject}
    save()


# The ceiling of a person's PAT in their assistant container: without admin; notifications:send —
# the assistant's replies and confirmations go to the channel (Telegram) on behalf of the person.
HARNESS_PERSON_AUDIENCES = ["control-plane", "notification-service"]
HARNESS_PERSON_CEILING = ["control-plane:read", "control-plane:write", "notifications:send"]


def harness_people(
    args, iam: Http, bootstrap_header: dict, iam_tenant: str, issuer: str, state: dict, save, secrets_dir: Path
) -> None:
    """8. Personal assistants: a person's PAT → credentials.json in their secrets directory, the
    launcher's cookie key and the registry people.json for the launcher. The model subscription
    token (`claude-oauth-token`) and the forge token (`forge-token`) are put into that directory
    by the person — bootstrap does not know them."""
    print("8. personal assistants from", args.harness_people)
    registry = json.loads((ROOT / args.harness_people).read_text())
    base = secrets_dir / "harness"
    cookie = base / "cookie-secret"
    if not cookie.exists():
        secure_write(cookie, uuid.uuid4().hex + uuid.uuid4().hex + "\n")
        print("   the launcher's cookie key →", cookie)
    people: dict[str, dict] = {}
    issued_state = state.setdefault("harnessPeople", {})
    for person in registry.get("people", []):
        principal = person["iamPrincipalId"]
        if principal == "operator":
            principal = state["iamOperatorPrincipalId"]
        folder = base / principal
        credentials = folder / "credentials.json"
        # The ceiling grew (a new audience) — the previous PAT does not fit: reissue.
        stale = credentials.exists() and issued_state.get(principal, {}).get("ceiling") != sorted(
            HARNESS_PERSON_CEILING
        )
        if stale:
            print("   the ceiling of the person's PAT changed — reissue", principal)
        if not credentials.exists() or stale:
            # IAM issues a PAT to a person only with a fresh authentication context (≤ 300 s).
            iam.call(
                "POST",
                f"/api/v1/tenants/{iam_tenant}/principals/{principal}/authentication-contexts",
                {"issuer": issuer, "acr": "bootstrap", "amr": ["bootstrap-script"]},
                bootstrap_header,
            )
            issued = issue_pat(
                iam,
                bootstrap_header,
                tenant=iam_tenant,
                principal=principal,
                name=f"harness-{time.strftime('%Y-%m')}",
                ceiling=HARNESS_PERSON_CEILING,
                ttl=args.pat_ttl,
                audiences=HARNESS_PERSON_AUDIENCES,
            )
            secure_write(
                credentials, json.dumps({f"{issuer}|{iam_tenant}|{principal}": {"token": issued["token"]}}) + "\n"
            )
            credential = issued.get("credential") or {}
            issued_state[principal] = {
                "patPrefix": credential.get("publicPrefix"),
                "expiresAt": credential.get("expiresAt"),
                "ceiling": sorted(HARNESS_PERSON_CEILING),
            }
            save()
            print("   the person's PAT", principal, "→", credentials, "prefix", credential.get("publicPrefix"))
        else:
            print("   already done:", credentials)
        missing = [name for name in ("claude-oauth-token", "forge-token") if not (folder / name).exists()]
        if missing:
            print(
                f"   !! put into {folder}: {', '.join(missing)} (0600) — the model subscription token "
                "(`claude setup-token`) and a personal forge token; without the first the assistant does not answer"
            )
        people[principal] = {
            "secretsDir": str(folder.resolve()),
            **({"name": person["name"]} if person.get("name") else {}),
            **({"email": person["email"]} if person.get("email") else {}),
        }
    secure_write(base / "people.json", json.dumps(people, ensure_ascii=False, indent=2) + "\n")
    # The launcher and people's containers run as uid 10001: on Linux the directory is theirs.
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        hand_tree_to_container_uid(base)
    else:
        print("   on Linux: chown -R 10001:10001", base)
    print("   the launcher's registry →", base / "people.json", f"({len(people)} people)")
    print("   !! a person's binding needs skills.invoke and tasks.claim (the operator has admin)")


def public_url_of(env: dict[str, str]) -> str:
    """`TAIMEN_PUBLIC_URL` without a trailing `/` — otherwise a refusal, not a silent fix.

    compose builds `CP_IAM_ISSUER`, `IAM_ISSUER`, `FLEET_IAM_ISSUER` and the rest as
    `${TAIMEN_PUBLIC_URL}/iam`, and compose interpolation cannot strip a `/`. The core compares
    the issuer of a binding exactly (`https://x/iam` and `https://x//iam` are different issuers):
    a bootstrap that stripped the `/` on its side would link identities to an issuer whose tokens
    the core does not accept (`422 iam_issuer_untrusted`)."""
    value = env.get("TAIMEN_PUBLIC_URL", "")
    if not value:
        raise SystemExit("TAIMEN_PUBLIC_URL is not set: the IAM issuer is derived from it (${TAIMEN_PUBLIC_URL}/iam)")
    if value.endswith("/"):
        raise SystemExit(
            f"TAIMEN_PUBLIC_URL={value} ends with '/': compose would build the issuer {value}/iam with a double "
            "'/', and it would differ from the issuer of the core's bindings. Remove the trailing '/' in .env "
            "and recreate the services (tools/compose up -d)"
        )
    return value


def link_service_identity(cp: Authorized, key: str, identity: dict, *, linked: bool, reason: str) -> tuple[dict, bool]:
    """The identity of a service agent in the core's registry → (agent, whether it was replaced).

    The core does not return the recorded identity — it compares it itself. `PUT …/identity` is
    idempotent: the first link or the same identity — 200, no changes and no events. An agent
    already linked (`linked`: the published description has a principal) with another identity —
    `409 agent_identity_conflict`; then `POST …/identity:replace`: the core's principal stays,
    the previous binding and the bypass bindings are revoked, the new one gets the permissions of
    the current revision. Other refusals (`iam_issuer_untrusted`, an identity of another principal,
    an agent of another kind) are raised as they are: neither a replacement nor a retry cures them.
    `cp` — the core's transport with the operator's token provider."""

    def headers() -> dict:
        return {"Idempotency-Key": str(uuid.uuid4())}

    try:
        return cp.call("PUT", f"/api/v1/agents/{key}/identity", identity, headers()), False
    except HttpError as error:
        if not linked or error.status != 409 or error.code != "agent_identity_conflict":
            raise
    replaced = cp.call("POST", f"/api/v1/agents/{key}/identity:replace", {**identity, "reason": reason}, headers())
    return replaced, True


def ensure_service_identity(
    iam: Http,
    cp: Authorized,
    bootstrap_header: dict,
    state: dict,
    save,
    *,
    iam_tenant: str,
    issuer: str,
    step: str,
    key: str,
    env_file: Path,
    env_lines,
    prefix: str,
    restart: str,
) -> None:
    """A service's account by its description: an IAM service account by identity.iam
    (`ensure_service_account`), the description published in the core and the identity linked —
    the core derives the principal and the binding with the description's permissions. An
    account created anew (the previous one is gone from IAM) is a new identity of the same
    service: the core moves the previous principal to it (`identity:replace`)."""
    agent = service_agent(key)
    print(f"{step}. {key}: IAM service account by the description, identity in the core, env file")
    done = ensure_service_account(
        iam,
        bootstrap_header,
        iam_tenant,
        service_account_for(key),
        state,
        save,
        prefix=prefix,
        principal_key=f"{prefix}IamPrincipalId",
        env_file=env_file,
        env_lines=env_lines,
    )
    if done & {"created", "rotated"}:
        print("   secret →", env_file, "client", state[f"{prefix}ServiceAccountClientId"])
        print("   !! restart the service:", restart)
    elif done:
        print("   ceiling updated, the env file stays; new scopes come with the next token exchange")
    else:
        print("   already done:", env_file)
    check_identity_unique(
        state,
        f"{prefix}IamPrincipalId",
        state[f"{prefix}IamPrincipalId"],
        f"{prefix}ServiceAccountClientId",
        state.get(f"{prefix}ServiceAccountClientId"),
    )
    published = cp.call("POST", "/api/v1/agents", agent, {"Idempotency-Key": str(uuid.uuid4())})
    identity = {"issuer": issuer, "iamTenantId": iam_tenant, "iamPrincipalId": state[f"{prefix}IamPrincipalId"]}
    linked, replaced = link_service_identity(
        cp,
        key,
        identity,
        linked=published.get("principalId") is not None,
        reason=f"bootstrap {step}: service {key} moves to the IAM service account issued by bootstrap",
    )
    if replaced:
        print(
            "   identity in the core replaced (identity:replace): the principal stays, the previous binding is revoked"
        )
    state[f"{prefix}CpPrincipalId"] = linked.get("principalId") or state.get(f"{prefix}CpPrincipalId")
    save()
    print("   revision", published.get("currentRevision"), "principal", state[f"{prefix}CpPrincipalId"])


def platform_services(
    iam: Http,
    cp: Authorized,
    bootstrap_header: dict,
    state: dict,
    save,
    *,
    iam_tenant: str,
    issuer: str,
    secrets_dir: Path,
) -> None:
    """5c, 5d — the platform services, then the revocation of the core's legacy key. They run after
    step 5b, so `cp` is the transport with the operator's token provider, not the header of step 4."""

    def service_identity(step: str, key: str, env_file: Path, env_lines, prefix: str, restart: str) -> None:
        ensure_service_identity(
            iam,
            cp,
            bootstrap_header,
            state,
            save,
            iam_tenant=iam_tenant,
            issuer=issuer,
            step=step,
            key=key,
            env_file=env_file,
            env_lines=env_lines,
            prefix=prefix,
            restart=restart,
        )

    # Events of the whole tenant (decisions wait in any workspace); narrow them with
    # NS_EVENTS_WORKSPACE_ID in the service's environment.
    service_identity(
        "5c",
        "notification-service",
        secrets_dir / "notification-iam.env",
        lambda issued: (
            f"NS_SERVICE_CLIENT_ID={issued['clientId']}\nNS_SERVICE_CLIENT_SECRET={issued['clientSecret']}\n"
        ),
        "notify",
        "tools/compose --profile notify up -d notification-service",
    )
    service_identity(
        "5d",
        "fleet-controller",
        secrets_dir / "fleet-iam.env",
        lambda issued: f"FLEET_CLIENT_ID={issued['clientId']}\nFLEET_CLIENT_SECRET={issued['clientSecret']}\n",
        "fleet",
        "tools/compose --profile fleet up -d fleet-controller",
    )

    if state.get("cpLegacyAdminKeyId") and not state.get("cpLegacyAdminKeyRevoked"):
        try:
            cp.call("POST", f"/api/v1/api-keys/{state['cpLegacyAdminKeyId']}:revoke", None, {})
            state["cpLegacyAdminKeyRevoked"] = True
            save()
            print("   legacy admin api-key revoked")
        except RuntimeError as error:
            print("   legacy admin api-key not revoked:", str(error)[:120])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env", default=".env")
    parser.add_argument("--name", default=None, help="environment name (COMPOSE_PROJECT_NAME by default)")
    parser.add_argument("--operator", default="Human Operator")
    parser.add_argument("--tenant-slug", default=None)
    parser.add_argument("--pat-ttl", type=int, default=180 * 24 * 3600)
    parser.add_argument("--secrets-dir", default="secrets")
    parser.add_argument(
        "--secrets-link-root",
        action="append",
        default=[],
        help="a directory that links in --secrets-dir may lead to; a write through a link outside it stops the run",
    )
    parser.add_argument(
        "--packages", default="deploy/packages.yaml", help="catalog installation file (kind: Installation), step 5b"
    )
    parser.add_argument(
        "--no-packages",
        action="store_true",
        help="skip step 5b: on a running installation packages are installed by a human (plan → review → apply)",
    )
    parser.add_argument(
        "--identity-provider",
        default=None,
        help="a description of an IAM identity provider (YAML), step 2c; without it the step is skipped",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="read only: show what steps 2–2c would change (audiences, the people-admins and fleet-admins "
        "groups, the identity provider) and exit without writing; the other steps do not run",
    )
    parser.add_argument(
        "--prune-scopes",
        action="store_true",
        help="remove from the registry's audiences the scopes that are not in the registry (by default the sync "
        "only adds); prints what it removes; with --dry-run only shows",
    )
    parser.add_argument(
        "--harness-people",
        default=None,
        help="registry of people with a personal assistant, for example deploy/harness-people.json; "
        "without it step 8 is skipped",
    )
    args = parser.parse_args()

    require_package_sdk()
    env = read_env(ROOT / args.env)
    project = env.get("COMPOSE_PROJECT_NAME", "taimen")
    name = args.name or project
    public_url = public_url_of(env)
    issuer = f"{public_url}/iam"
    slug = args.tenant_slug or project
    secrets_dir = ROOT / args.secrets_dir
    set_secret_roots(secrets_dir, tuple(args.secrets_link_root))
    state_path = ROOT / "deploy" / "state" / f"{name}.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    cp = Http(f"http://127.0.0.1:{env.get('CP_HOST_PORT', '18000')}")
    iam = Http(f"http://127.0.0.1:{env.get('IAM_HOST_PORT', '18010')}")
    bootstrap_header = {"X-IAM-Bootstrap-Token": env["IAM_BOOTSTRAP_TOKEN"]}

    def save() -> None:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")

    print("1. waiting for the services")
    cp.wait("/health/ready")
    iam.wait("/healthz")

    if "iamTenantId" in state:
        # The state survived a reset of the volumes: its ids no longer exist, and "already done"
        # would be a lie. Checked with the same bootstrap token as the rest of step 2.
        try:
            iam.call("GET", f"/api/v1/tenants/{state['iamTenantId']}/audiences", headers=bootstrap_header)
        except RuntimeError as error:
            if "HTTP 404" in str(error):
                raise SystemExit(
                    f"{state_path.relative_to(ROOT)} refers to IAM tenant {state['iamTenantId']}, which does not "
                    "exist in IAM (volumes reset?). Run `make reset-state` and repeat bootstrap."
                ) from error
            raise

    print("2. IAM tenant, audiences, the operator's principal")
    if args.dry_run and "iamTenantId" not in state:
        groups = ", ".join(group["key"] for group, _, _ in PRIVILEGED_GROUPS.values())
        print(
            "   [dry-run] a clean installation: the tenant, all registry audiences, the operator, groups "
            f"{groups}{', the identity provider' if args.identity_provider else ''} — will be created"
        )
        warn_privileged(AUDIENCES, dry_run=True)
        return 0
    if "iamTenantId" not in state:
        tenant = iam.call("POST", "/api/v1/tenants", {"slug": slug, "name": slug}, bootstrap_header)
        state["iamTenantId"] = tenant["id"]
        save()
    iam_tenant = state["iamTenantId"]
    # A service's ceiling grows with the service: audiences follow the registry on every run.
    sync_audiences(iam, bootstrap_header, iam_tenant, state, save, dry_run=args.dry_run, prune=args.prune_scopes)
    if "iamOperatorPrincipalId" not in state and not args.dry_run:
        principal = iam.call(
            "POST",
            f"/api/v1/tenants/{iam_tenant}/principals",
            {"kind": "human", "displayName": args.operator},
            bootstrap_header,
        )
        state["iamOperatorPrincipalId"] = principal["id"]
        save()
    owner = state.get("iamOperatorPrincipalId")
    ensure_privileged_groups(iam, bootstrap_header, iam_tenant, owner, state, save, dry_run=args.dry_run)
    if args.identity_provider:
        spec = load_identity_provider(ROOT / args.identity_provider, public_url)
        ensure_identity_provider(iam, bootstrap_header, iam_tenant, spec, owner, state, save, dry_run=args.dry_run)
    if args.dry_run:
        print("dry-run: steps 2–2c shown, nothing written; steps 2a–8 did not run")
        return 0
    print("   IAM tenant", iam_tenant, "operator", state["iamOperatorPrincipalId"])
    if env.get("IAM_TENANT_ID", "") != iam_tenant:
        print(
            f"   !! add to {args.env}: IAM_TENANT_ID={iam_tenant} "
            "(needed by the console, the assistant launcher and fleet-controller)"
        )

    print("2a. Control Plane service account in IAM")
    sa_env = secrets_dir / "control-plane-iam.env"
    done = ensure_service_account(
        iam,
        bootstrap_header,
        iam_tenant,
        CP_SERVICE_ACCOUNT,
        state,
        save,
        prefix="cp",
        principal_key="cpServiceAccountPrincipalId",
        env_file=sa_env,
        env_lines=lambda issued: (
            f"CP_IAM_CLIENT_ID={issued['clientId']}\nCP_IAM_CLIENT_SECRET={issued['clientSecret']}\n"
        ),
    )
    if done & {"created", "rotated"}:
        print("   secret →", sa_env, "client", state["cpServiceAccountClientId"])
        print(
            "   !! restart the core so that it picks up the env file: "
            "tools/compose up -d control-plane-api control-plane-worker context-adapter"
        )
    elif done:
        print(
            "   ceiling updated, the env file stays; new scopes come with the next token exchange:",
            state["cpServiceAccountClientId"],
        )
    else:
        print("   already done:", sa_env, "client", state["cpServiceAccountClientId"])

    print("3. Control Plane bootstrap with the operator's binding")
    if "cpTenantId" not in state:
        # One platform tenant: the Control Plane gets the UUID of the IAM tenant.
        boot = cp.call(
            "POST",
            "/api/v1/bootstrap",
            {
                "tenantSlug": slug,
                "tenantName": slug.replace("-", " ").title(),
                "adminDisplayName": args.operator,
                "tenantId": iam_tenant,
                "iamBinding": {
                    "issuer": issuer,
                    "iamTenantId": iam_tenant,
                    "iamPrincipalId": state["iamOperatorPrincipalId"],
                },
            },
            {"Authorization": f"Bearer {env['CP_BOOTSTRAP_TOKEN']}"},
        )
        state["cpTenantId"] = boot["tenant"]["id"]
        state["cpOperatorPrincipalId"] = boot["adminPrincipal"]["id"]
        state["cpLegacyAdminKeyId"] = boot["apiKey"]["id"]
        state["cpOperatorBindingId"] = (boot.get("iamBinding") or {}).get("id")
        save()
        print(
            "   tenant",
            state["cpTenantId"],
            "operator",
            state["cpOperatorPrincipalId"],
            "binding",
            state["cpOperatorBindingId"],
        )
    else:
        print("   already done:", state["cpTenantId"])

    print("4. the operator's PAT")
    pat_file = secrets_dir / "harness-pat"
    if not pat_file.exists():
        # The ceiling — before the authentication context: the freshness of the sign-in (300 s) is
        # not spent on reading the installation, and an unreadable installation leaves no context.
        try:
            audiences, ceiling = operator_pat_grant(None if args.no_packages else ROOT / args.packages)
        except package_model.PackageError as error:
            raise SystemExit(f"4. the installation {args.packages} cannot be read: {error}") from error
        iam.call(
            "POST",
            f"/api/v1/tenants/{iam_tenant}/principals/{state['iamOperatorPrincipalId']}/authentication-contexts",
            {"issuer": issuer, "acr": "bootstrap", "amr": ["bootstrap-script"]},
            bootstrap_header,
        )
        issued = issue_pat(
            iam,
            bootstrap_header,
            tenant=iam_tenant,
            principal=state["iamOperatorPrincipalId"],
            name=f"operator-{time.strftime('%Y-%m')}",
            ceiling=ceiling,
            ttl=args.pat_ttl,
            audiences=audiences,
        )
        secure_write(pat_file, issued["token"] + "\n")
        credential = issued.get("credential") or {}
        state["operatorPatPrefix"] = credential.get("publicPrefix")
        state["operatorPatExpiresAt"] = credential.get("expiresAt")
        save()
        print("   issued →", pat_file, "prefix", state.get("operatorPatPrefix"))
    else:
        print("   already done:", pat_file)
    pat = pat_file.read_text().strip()
    operator = operator_bearer(iam, pat)
    operator.token()  # the first exchange right away: a wrong PAT shows at step 4, not in the middle of 5b
    # The core with the operator's token before every request: the steps after 5b outlive one token.
    cp_op = Authorized(cp, operator)
    print("   PAT exchange → access token: ok (renewed before it expires)")

    print("5. Control Plane: project template, project and workspace")
    if "templateId" not in state:
        template = cp_op.call(
            "POST", "/api/v1/project-templates", {"key": slug, "displayName": slug.replace("-", " ").title()}
        )
        state["templateId"] = template["id"]
        save()
    if "projectId" not in state:
        project_view = cp_op.call(
            "POST",
            "/api/v1/projects",
            {
                "workspaceSlug": slug,
                "workspaceName": slug.replace("-", " ").title(),
                "workspaceTypeKey": "generic",
                "templateId": state["templateId"],
                "ownerPrincipalId": state["cpOperatorPrincipalId"],
            },
        )
        state["projectId"] = project_view["id"]
        state["workspaceId"] = project_view["workspaceId"]
        save()
    print("   project", state["projectId"], "workspace", state["workspaceId"])
    if args.no_packages:
        print("5b. packages skipped (--no-packages): plan → review → apply --plan")
    else:
        print("5b. packages as one plan:", args.packages)
        package_env = {**env, **os.environ}
        installation_path = ROOT / args.packages
        try:
            target = package_target(
                cp.base,
                operator,
                package_env,
                installation_path,
                notify_bearer(iam, pat, package_env, pat_file=pat_file),
            )
        except package_model.PackageError as error:
            raise SystemExit(f"5b. the installation {args.packages} cannot be read: {error}") from error
        try:
            state["packages"] = install_packages(
                installation_path,
                target=target,
                env=package_env,
                plan_path=state_path.with_name(f"{name}.packages-plan.json"),
                log=lambda line: print("  ", line),
            )
        except package_model.PackageError as error:
            raise SystemExit(f"5b. installing the packages stopped: {error}") from error
        except PackageHttpError as error:
            raise SystemExit(
                f"5b. installing the packages stopped: the installation answered HTTP {error.status}: "
                f"{str(error)[:400]}"
            ) from error
        state["packages"]["install"] = args.packages
        state["packages"]["plan"] = str(Path(state["packages"]["plan"]).relative_to(ROOT))
        save()

    platform_services(
        iam, cp_op, bootstrap_header, state, save, iam_tenant=iam_tenant, issuer=issuer, secrets_dir=secrets_dir
    )

    save()
    if args.harness_people:
        harness_people(args, iam, bootstrap_header, iam_tenant, issuer, state, save, secrets_dir)

    print("done:", state_path.relative_to(ROOT))
    print(
        "credential for the MCP plugin and the CLI: ~/.config/iam/credentials.json, key "
        f"{issuer}|{iam_tenant}|{state['iamOperatorPrincipalId']} → the contents of {pat_file.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
