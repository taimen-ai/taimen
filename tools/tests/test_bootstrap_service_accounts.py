"""Service accounts in deploy/bootstrap.py against a fake IAM with a service account PATCH.

The fake is a real HTTP server in the process: bootstrap talks to it with its own `Http`, so
parsing of the response (the status and `detail`) is checked too. The IAM model is reduced to
what decides the scenarios: a service account (principal, audiences, ceiling, secret,
revocation), the audience registry, the client credentials exchange and IAM agents with an
owner (only the owning principal issues a PAT to an agent, and the PAT's audiences are never
wider than the owner's account).

    uv run --no-project --with pytest --with pyyaml --with jsonschema python -m pytest -q \\
      tools/tests/test_bootstrap_service_accounts.py
"""

from __future__ import annotations

import http.server
import importlib.util
import json
import os
import re
import secrets
import stat
import sys
import threading
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("taimen_bootstrap", ROOT / "deploy" / "bootstrap.py")
bs = importlib.util.module_from_spec(_spec)
sys.modules["taimen_bootstrap"] = bs
_spec.loader.exec_module(bs)

TENANT = str(uuid.uuid4())
HEADER = {"X-IAM-Bootstrap-Token": "bootstrap-test"}
SA = re.compile(r"^/api/v1/tenants/[^/]+/service-accounts/([^/:]+)$")
AUD = re.compile(r"^/api/v1/tenants/[^/]+/audiences/([^/]+)$")
AGENT_PAT = re.compile(r"^/api/v1/tenants/[^/]+/agents/([^/]+)/platform-access-tokens$")


class FakeIam:
    """IAM as far as the scenarios need it. `patch_mode`: "patch" — the route exists; "405" /
    "404" — an older IAM without the route. `drop_patches` — how many service account PATCHes
    to apply but then drop the connection without a response (a lost response)."""

    def __init__(self, audiences: dict[str, list[str]], *, patch_mode: str = "patch") -> None:
        self.audiences = {key: set(scopes) for key, scopes in audiences.items()}
        self.accounts: dict[str, dict] = {}
        self.agents: dict[str, str] = {}  # agent id → the owner's principal
        self.tokens: dict[str, dict] = {}
        self.requests: list[tuple[str, str, dict]] = []
        self.patch_mode = patch_mode
        self.drop_patches = 0
        self.next_principal: str | None = None  # the principal of the next account (a faulty IAM)
        fake = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def _handle(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                fake.requests.append((self.command, self.path, body))
                result = fake.route(self.command, self.path, body, self.headers)
                if result is None:  # the response is lost: the connection drops without a status
                    self.close_connection = True
                    return
                status, payload = result
                raw = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            do_GET = do_POST = do_PATCH = _handle

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    # ------------------------------------------------------------------ routes

    def route(self, method: str, path: str, body: dict, headers) -> tuple[int, dict] | None:
        bootstrap = headers.get("X-IAM-Bootstrap-Token") == HEADER["X-IAM-Bootstrap-Token"]
        if method == "GET" and path.endswith("/audiences"):  # sync_audiences of main(): the IAM registry list
            return 200, [{"key": key, "allowedScopes": sorted(scopes)} for key, scopes in self.audiences.items()]
        if method == "POST" and path.endswith("/audiences"):
            if body["key"] in self.audiences:
                return 409, {"detail": "audience_exists"}
            self.audiences[body["key"]] = set(body["allowedScopes"])
            return 201, {"key": body["key"]}
        if method == "PATCH" and (m := AUD.match(path)):
            self.audiences[m.group(1)] = set(body["allowedScopes"])
            return 200, {"key": m.group(1)}
        if method == "POST" and path.endswith("/service-accounts"):
            assert bootstrap
            if not set(body["audiences"]) <= set(self.audiences):
                return 422, {"detail": "unknown_audience"}
            client, secret = f"iam_sa_{secrets.token_hex(6)}", secrets.token_urlsafe(16)
            principal, self.next_principal = self.next_principal or str(uuid.uuid4()), None
            self.accounts[client] = {
                "principalId": principal,
                "audiences": sorted(set(body["audiences"])),
                "scopeCeiling": sorted(set(body["scopeCeiling"])),
                "secret": secret,
                "revoked": False,
            }
            return 201, {
                "principalId": self.accounts[client]["principalId"],
                "clientId": client,
                "clientSecret": secret,
            }
        if method == "PATCH" and (m := SA.match(path)):
            if self.patch_mode == "405":
                return 405, {"detail": "Method Not Allowed"}
            if self.patch_mode == "404":
                return 404, {"detail": "Not Found"}
            assert bootstrap
            return self.patch_account(m.group(1), body)
        if method == "POST" and path.endswith(":revoke"):
            self.accounts[path.rsplit("/", 1)[1].removesuffix(":revoke")]["revoked"] = True
            return 204, {}
        if method == "POST" and path == "/api/v1/tokens/exchange":
            account = self.accounts.get(body["clientId"])
            if not account or account["revoked"] or account["secret"] != body["clientSecret"]:
                return 401, {"detail": "invalid_client"}
            if body["audience"] not in account["audiences"] or not set(body["scopes"]) <= set(account["scopeCeiling"]):
                return 403, {"detail": "scope_not_allowed"}
            token = secrets.token_urlsafe(16)
            self.tokens[token] = {"clientId": body["clientId"], "audience": body["audience"], "scopes": body["scopes"]}
            return 200, {"accessToken": token}
        if method == "POST" and path.endswith("/agents"):
            owner = self.agent_owner(headers)
            if isinstance(owner, tuple):
                return owner
            agent = str(uuid.uuid4())
            self.agents[agent] = owner["principalId"]
            return 201, {"id": agent}
        if method == "POST" and (m := AGENT_PAT.match(path)):
            owner = self.agent_owner(headers)
            if isinstance(owner, tuple):
                return owner
            if self.agents.get(m.group(1)) != owner["principalId"]:
                return 403, {"detail": "agent_not_owned"}
            # the ceiling of an agent PAT is never wider than the owner's account
            if not set(body["audiences"]) <= set(owner["audiences"]):
                return 403, {"detail": "audience_not_allowed"}
            return 201, {"token": "tpat_" + secrets.token_hex(4)}
        return 404, {"detail": "Not Found"}

    def patch_account(self, client: str, body: dict) -> tuple[int, dict] | None:
        account = self.accounts.get(client)
        if account is None:
            return 404, {"detail": "service_account_not_found"}
        if account["revoked"]:
            return 409, {"detail": "service_account_revoked"}
        audiences = sorted(set(body.get("audiences", account["audiences"])))
        ceiling = sorted(set(body.get("scopeCeiling", account["scopeCeiling"])))
        if not set(audiences) <= set(self.audiences):
            return 422, {"detail": "unknown_audience"}
        if not set(ceiling) <= set().union(*(self.audiences[a] for a in audiences)):
            return 422, {"detail": "invalid_scope_ceiling"}
        account["audiences"], account["scopeCeiling"] = audiences, ceiling
        secret = None
        if body.get("rotateSecret"):
            secret = secrets.token_urlsafe(16)
            account["secret"] = secret
        if self.drop_patches and body:  # the response to a change is lost, not to the reconciliation
            self.drop_patches -= 1
            return None
        return 200, {
            "principalId": account["principalId"],
            "clientId": client,
            "audiences": audiences,
            "scopeCeiling": ceiling,
            "clientSecret": secret,
        }

    def agent_owner(self, headers) -> dict | tuple[int, dict]:
        grant = self.tokens.get(headers.get("Authorization", "").removeprefix("Bearer "))
        if not grant:
            return 401, {"detail": "invalid_token"}
        account = self.accounts[grant["clientId"]]
        if grant["audience"] != "iam" or "iam:agents" not in grant["scopes"]:
            return 403, {"detail": "scope_not_granted"}
        return account

    # ------------------------------------------------------------------ helpers

    def service_account_calls(self, method: str) -> list[tuple[str, str, dict]]:
        return [r for r in self.requests if r[0] == method and "/service-accounts" in r[1] and ":revoke" not in r[1]]

    def changes(self) -> list[tuple[str, str, dict]]:
        """Service account PATCHes with changes — without the empty reconciliations `PATCH {}`."""
        return [r for r in self.service_account_calls("PATCH") if r[2]]


def _fleet_lines(issued: dict) -> str:
    return f"FLEET_CLIENT_ID={issued['clientId']}\nFLEET_CLIENT_SECRET={issued['clientSecret']}\n"


def _read_env(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)


class Fleet:
    """fleet-controller as an IAM client: an exchange of its account → IAM agents and their PATs."""

    def __init__(self, iam: bs.Http, env_file: Path) -> None:
        self.iam, self.env_file = iam, env_file

    def token(self) -> dict:
        env = _read_env(self.env_file)
        exchanged = self.iam.call(
            "POST",
            "/api/v1/tokens/exchange",
            {
                "clientId": env["FLEET_CLIENT_ID"],
                "clientSecret": env["FLEET_CLIENT_SECRET"],
                "audience": "iam",
                "scopes": ["iam:agents"],
            },
        )
        return {"Authorization": f"Bearer {exchanged['accessToken']}"}

    def create_agent(self) -> str:
        return self.iam.call("POST", f"/api/v1/tenants/{TENANT}/agents", {"displayName": "coder"}, self.token())["id"]

    def agent_pat(self, agent: str, audiences: list[str]) -> dict:
        return self.iam.call(
            "POST",
            f"/api/v1/tenants/{TENANT}/agents/{agent}/platform-access-tokens",
            {"audiences": audiences, "scopeCeiling": []},
            {**self.token(), "Idempotency-Key": str(uuid.uuid4())},
        )


def _old_registry() -> dict[str, list[str]]:
    """The audience registry of an earlier release: without the `notification-service` audience
    and without `iam:identities.link`."""
    registry = {key: list(scopes) for key, scopes in bs.AUDIENCES.items() if key != "notification-service"}
    registry["iam"] = [scope for scope in registry["iam"] if scope != "iam:identities.link"]
    return registry


def _old_fleet_account() -> dict:
    """The fleet-controller account of that release: no `notification-service` audience and none
    of the scopes added since."""
    account = bs.service_account_for("fleet-controller")
    return {
        **account,
        "audiences": [a for a in account["audiences"] if a != "notification-service"],
        "scopeCeiling": [s for s in account["scopeCeiling"] if s not in ("notifications:send", "iam:identities.link")],
    }


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(bs.time, "sleep", lambda _seconds: None)
    fake = FakeIam(_old_registry())
    state = {"iamAudiences": sorted(_old_registry())}
    saves: list[dict] = []

    def ensure(account: dict) -> set[str]:
        return bs.ensure_service_account(
            bs.Http(fake.url),
            HEADER,
            TENANT,
            account,
            state,
            lambda: saves.append(json.loads(json.dumps(state))),
            prefix="fleet",
            principal_key="fleetIamPrincipalId",
            env_file=tmp_path / "fleet-iam.env",
            env_lines=_fleet_lines,
        )

    yield {
        "fake": fake,
        "state": state,
        "saves": saves,
        "ensure": ensure,
        "env": tmp_path / "fleet-iam.env",
        "http": bs.Http(fake.url),
    }
    fake.server.shutdown()


# ---------------------------------------------------------------- scenarios


def test_fleet_ceiling_extension_patches_and_keeps_the_agents(world):
    """Extending the fleet-controller ceiling (the notification-service audience,
    notifications:send, iam:identities.link) is a PATCH of the same account: the principal and
    the env file stay, the agents stay the controller's agents, and it keeps issuing PATs to
    them — now with the notification-service audience too."""
    fake, state, env = world["fake"], world["state"], world["env"]
    assert world["ensure"](_old_fleet_account()) == {"created"}
    principal, client = state["fleetIamPrincipalId"], state["fleetServiceAccountClientId"]
    env_before = env.read_text()

    fleet = Fleet(world["http"], env)
    agent = fleet.create_agent()
    fleet.agent_pat(agent, ["control-plane"])
    with pytest.raises(bs.HttpError) as refused:  # the account does not have this audience yet
        fleet.agent_pat(agent, ["control-plane", "notification-service"])
    assert refused.value.status == 403 and refused.value.detail == "audience_not_allowed"

    # the order of main(): the audience registry first, then the account's ceiling
    bs.sync_audiences(world["http"], HEADER, TENANT, state, lambda: None)
    new_account = bs.service_account_for("fleet-controller")
    assert world["ensure"](new_account) == {"updated"}

    assert len(fake.service_account_calls("POST")) == 1  # only the first creation
    (patch,) = fake.changes()
    assert patch[1].endswith(f"/service-accounts/{client}")
    assert patch[2] == {
        "audiences": sorted(set(new_account["audiences"])),
        "scopeCeiling": sorted(set(new_account["scopeCeiling"])),
    }
    assert not [r for r in fake.requests if r[1].endswith(":revoke")]
    assert state["fleetIamPrincipalId"] == principal and state["fleetServiceAccountClientId"] == client
    assert state["fleetServiceAccountCeiling"] == bs.service_account_ceiling(new_account)
    assert env.read_text() == env_before  # the same secret, the env file untouched
    account = fake.accounts[client]
    assert "notification-service" in account["audiences"]
    assert {"notifications:send", "iam:identities.link"} <= set(account["scopeCeiling"])

    # the same controller with its previous secret serves the previous agent
    assert fleet.agent_pat(agent, ["control-plane", "notification-service"])["token"].startswith("tpat_")

    # a repeated bootstrap changes nothing: only the reconciliation by an empty PATCH, no writes
    before = len(fake.requests)
    secret_before = account["secret"]
    assert world["ensure"](new_account) == set()
    assert [r[2] for r in fake.requests[before:]] == [{}]
    assert account["secret"] == secret_before and env.read_text() == env_before


def test_ceiling_patch_before_the_audience_registry_is_refused(world):
    """IAM checks the ceiling against the audience registry: without sync_audiences a PATCH with
    a new audience fails — that is why main() calls sync_audiences before the accounts."""
    world["ensure"](_old_fleet_account())
    with pytest.raises(bs.HttpError) as refused:
        world["ensure"](bs.service_account_for("fleet-controller"))
    assert refused.value.status == 422
    source = (ROOT / "deploy" / "bootstrap.py").read_text(encoding="utf-8")
    main = source[source.index("def main()") :]
    assert main.index("sync_audiences(") < main.index("ensure_service_account(")


def test_lost_env_file_rotates_the_secret_of_the_same_account(world):
    fake, state, env = world["fake"], world["state"], world["env"]
    account = bs.service_account_for("fleet-controller")
    bs.sync_audiences(world["http"], HEADER, TENANT, state, lambda: None)
    world["ensure"](account)
    principal, client = state["fleetIamPrincipalId"], state["fleetServiceAccountClientId"]
    old_secret = _read_env(env)["FLEET_CLIENT_SECRET"]
    agent = Fleet(world["http"], env).create_agent()
    env.unlink()

    assert world["ensure"](account) == {"rotated"}
    (patch,) = fake.changes()
    assert patch[2] == {"rotateSecret": True}  # the ceiling matches — only the secret
    assert len(fake.service_account_calls("POST")) == 1
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    new = _read_env(env)
    assert new["FLEET_CLIENT_ID"] == client and new["FLEET_CLIENT_SECRET"] != old_secret
    assert state["fleetIamPrincipalId"] == principal
    # the new secret works and the agent is the same; the old secret is gone
    assert Fleet(world["http"], env).agent_pat(agent, ["notification-service"])
    with pytest.raises(bs.HttpError) as refused:
        world["http"].call(
            "POST",
            "/api/v1/tokens/exchange",
            {"clientId": client, "clientSecret": old_secret, "audience": "iam", "scopes": ["iam:agents"]},
        )
    assert refused.value.status == 401


def test_lost_env_and_changed_ceiling_go_in_one_patch(world):
    fake, state = world["fake"], world["state"]
    world["ensure"](_old_fleet_account())
    world["env"].unlink()
    bs.sync_audiences(world["http"], HEADER, TENANT, state, lambda: None)
    assert world["ensure"](bs.service_account_for("fleet-controller")) == {"updated", "rotated"}
    (patch,) = fake.changes()
    assert patch[2]["rotateSecret"] is True and "notification-service" in patch[2]["audiences"]
    assert Fleet(world["http"], world["env"]).create_agent()


def test_lost_rotate_response_is_retried_and_the_last_secret_is_written(world):
    fake, state, env = world["fake"], world["state"], world["env"]
    account = bs.service_account_for("fleet-controller")
    bs.sync_audiences(world["http"], HEADER, TENANT, state, lambda: None)
    world["ensure"](account)
    client = state["fleetServiceAccountClientId"]
    env.unlink()
    fake.drop_patches = 1  # IAM changed the secret, but the response did not reach bootstrap

    assert world["ensure"](account) == {"rotated"}
    patches = fake.service_account_calls("PATCH")
    assert [p[2] for p in patches] == [{}, {"rotateSecret": True}, {"rotateSecret": True}]
    assert _read_env(env)["FLEET_CLIENT_SECRET"] == fake.accounts[client]["secret"]
    assert Fleet(world["http"], env).create_agent()


def test_lost_response_on_every_attempt_fails_without_writing(world):
    fake, state, env = world["fake"], world["state"], world["env"]
    bs.sync_audiences(world["http"], HEADER, TENANT, state, lambda: None)
    world["ensure"](bs.service_account_for("fleet-controller"))
    env.unlink()
    fake.drop_patches = 10
    with pytest.raises(OSError):
        world["ensure"](bs.service_account_for("fleet-controller"))
    assert not env.exists()  # the next bootstrap asks for rotateSecret again


@pytest.mark.parametrize("mode", ["405", "404"])
def test_iam_without_patch_stops_the_bootstrap(world, mode, capsys):
    fake, state, env = world["fake"], world["state"], world["env"]
    world["ensure"](_old_fleet_account())
    principal, env_before = state["fleetIamPrincipalId"], env.read_text()
    fake.patch_mode = mode
    bs.sync_audiences(world["http"], HEADER, TENANT, state, lambda: None)

    with pytest.raises(SystemExit) as stopped:
        world["ensure"](bs.service_account_for("fleet-controller"))
    assert "IAM does not accept a PATCH of a service account" in str(stopped.value)
    assert len(fake.service_account_calls("POST")) == 1  # no silent switch to POST
    assert state["fleetIamPrincipalId"] == principal and env.read_text() == env_before
    assert state["fleetServiceAccountCeiling"] == bs.service_account_ceiling(_old_fleet_account())
    assert "FLEET_CLIENT_SECRET" not in capsys.readouterr().out


@pytest.mark.parametrize("gone", ["revoked", "missing"])
def test_revoked_or_missing_account_is_created_anew(world, gone):
    fake, state, env = world["fake"], world["state"], world["env"]
    bs.sync_audiences(world["http"], HEADER, TENANT, state, lambda: None)
    account = bs.service_account_for("fleet-controller")
    world["ensure"](account)
    old_client, old_principal = state["fleetServiceAccountClientId"], state["fleetIamPrincipalId"]
    if gone == "revoked":
        fake.accounts[old_client]["revoked"] = True
    else:
        del fake.accounts[old_client]
    env.unlink()

    assert world["ensure"](account) == {"created"}
    assert len(fake.service_account_calls("POST")) == 2
    assert state["fleetServiceAccountClientId"] != old_client and state["fleetIamPrincipalId"] != old_principal
    assert _read_env(env)["FLEET_CLIENT_ID"] == state["fleetServiceAccountClientId"]


def test_other_patch_errors_are_not_masked(world):
    world["ensure"](_old_fleet_account())
    world["fake"].audiences.pop("iam")  # the audience is withdrawn from the registry
    with pytest.raises(bs.HttpError) as refused:
        world["ensure"]({**_old_fleet_account(), "scopeCeiling": [*_old_fleet_account()["scopeCeiling"], "x:y"]})
    assert refused.value.status == 422 and refused.value.detail == "unknown_audience"
    assert len(world["fake"].service_account_calls("POST")) == 1


def test_bootstrap_has_no_sql_ownership_transfer_and_no_reissue():
    source = (ROOT / "deploy" / "bootstrap.py").read_text(encoding="utf-8")
    assert "AGENT_OWNERS" not in source and "owner_principal_id" not in source
    assert "UPDATE principals" not in source
    # the accounts of the core and of the services go one way; a changed ceiling does not
    # revoke the previous account
    assert source.count("ensure_service_account(") == 3  # the definition + step 2a + service_identity
    assert "/service-accounts/{previous}:revoke" not in source
    assert '"rotateSecret"' in source
    readme = (ROOT / "deploy" / "README.md").read_text(encoding="utf-8")
    assert "UPDATE principals" not in readme and "PATCH of the same account" in readme


# ---------------------------------------------------------------- the principal in the PATCH response


@pytest.mark.parametrize("lost_env", [False, True], ids=["ceiling", "rotate"])
def test_patch_answer_with_another_principal_stops_without_touching_env_and_state(world, lost_env):
    """The principal is checked by an empty `PATCH {}` before any change: a foreign principal
    means the client id in the state belongs to another account. The run stops before writing:
    the ceiling and the secret in IAM are unchanged, the env file and the state are as they were."""
    fake, state, env, saves = world["fake"], world["state"], world["env"], world["saves"]
    world["ensure"](_old_fleet_account())
    bs.sync_audiences(world["http"], HEADER, TENANT, state, lambda: None)
    foreign = str(uuid.uuid4())
    state["fleetIamPrincipalId"] = foreign  # a state of another IAM / tenant
    env_before = None if lost_env else env.read_text()
    if lost_env:
        env.unlink()
    state_before, saves_before = json.loads(json.dumps(state)), len(saves)
    client = state["fleetServiceAccountClientId"]
    account_before = dict(fake.accounts[client])

    with pytest.raises(SystemExit) as stopped:
        world["ensure"](bs.service_account_for("fleet-controller"))
    message = str(stopped.value)
    assert foreign in message and fake.accounts[client]["principalId"] in message and client in message
    assert "PATCH {}" in message and "nothing changed in IAM" in message
    assert fake.accounts[client] == account_before  # neither the ceiling nor the secret
    assert [r[2] for r in fake.service_account_calls("PATCH")] == [{}]
    assert fake.accounts[client]["secret"] not in message
    assert state == state_before and len(saves) == saves_before
    if lost_env:
        assert not env.exists()
    else:
        assert env.read_text() == env_before
    assert len(fake.service_account_calls("POST")) == 1  # no new account


def test_revoked_account_with_live_env_file_is_noticed_by_the_probe(world):
    """The reconciliation runs on every start: the account was revoked, the env file is in place,
    the ceiling is the same — bootstrap still sees `409 service_account_revoked` and creates a
    new one."""
    fake, state, env = world["fake"], world["state"], world["env"]
    bs.sync_audiences(world["http"], HEADER, TENANT, state, lambda: None)
    account = bs.service_account_for("fleet-controller")
    world["ensure"](account)
    old_client = state["fleetServiceAccountClientId"]
    fake.accounts[old_client]["revoked"] = True
    assert world["ensure"](account) == {"created"}
    assert _read_env(env)["FLEET_CLIENT_ID"] == state["fleetServiceAccountClientId"] != old_client


# ---------------------------------------------------------------- atomic write of a secret


def _leftovers(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir() if p.name.endswith(".tmp"))


@pytest.fixture(params=["write", "fsync"])
def failing_io(request, monkeypatch):
    """A failure in the middle of a write: `write` manages to write half, `fsync` fails after a
    full write — in both cases the content must not reach the target name."""
    real_write = bs.os.write

    def broken_write(descriptor, data):
        real_write(descriptor, bytes(data[: max(1, len(data) // 2)]))
        raise OSError(28, "No space left on device")

    def broken_fsync(descriptor):
        raise OSError(5, "Input/output error")

    if request.param == "write":
        monkeypatch.setattr(bs.os, "write", broken_write)
    else:
        monkeypatch.setattr(bs.os, "fsync", broken_fsync)
    return request.param


def test_interrupted_write_of_a_new_file_leaves_nothing(tmp_path, failing_io):
    target = tmp_path / "secrets" / "fleet-iam.env"
    with pytest.raises(OSError):
        bs.secure_write(target, "FLEET_CLIENT_ID=a\nFLEET_CLIENT_SECRET=" + "s" * 64 + "\n")
    assert not target.exists()  # the next bootstrap asks for rotateSecret
    assert _leftovers(target.parent) == []


def test_interrupted_write_keeps_the_previous_file(tmp_path, failing_io):
    target = tmp_path / "fleet-iam.env"
    target.write_text("FLEET_CLIENT_ID=old\nFLEET_CLIENT_SECRET=old\n")
    target.chmod(0o600)
    with pytest.raises(OSError):
        bs.secure_write(target, "FLEET_CLIENT_ID=new\nFLEET_CLIENT_SECRET=" + "n" * 64 + "\n")
    assert target.read_text() == "FLEET_CLIENT_ID=old\nFLEET_CLIENT_SECRET=old\n"
    assert _leftovers(tmp_path) == []


def test_secure_write_replaces_whole_file_with_0600_and_keeps_links(tmp_path):
    loose = tmp_path / "loose.env"
    loose.write_text("A=very long previous value that must not survive as a tail\n")
    loose.chmod(0o644)  # O_CREAT did not touch the mode of an existing file
    bs.secure_write(loose, "A=1\n")
    assert loose.read_text() == "A=1\n" and stat.S_IMODE(loose.stat().st_mode) == 0o600

    # secrets/ may hold links into another secrets directory (an explicit root): the target is
    # written, the link stays a link
    real = tmp_path / "real" / "fleet-iam.env"
    real.parent.mkdir()
    real.write_text("old\n")
    link = tmp_path / "secrets" / "fleet-iam.env"
    link.parent.mkdir()
    link.symlink_to(real)
    roots = [link.parent, real.parent]
    bs.secure_write(link, "new\n", roots=roots)
    assert link.is_symlink() and real.read_text() == "new\n"
    assert stat.S_IMODE(real.stat().st_mode) == 0o600

    # the trace of a killed process is removed by the next write
    (real.parent / ".fleet-iam.env.deadbeef.tmp").write_text("half")
    bs.secure_write(link, "newer\n", roots=roots)
    assert _leftovers(real.parent) == [] and real.read_text() == "newer\n"


def test_link_outside_the_secret_roots_stops_the_write(tmp_path):
    """A write through a link — only within realpath(secrets) and the explicit roots."""
    secrets_dir, elsewhere = tmp_path / "secrets", tmp_path / "etc"
    secrets_dir.mkdir()
    elsewhere.mkdir()
    victim = elsewhere / "passwd"
    victim.write_text("root:x:0:0\n")
    victim.chmod(0o644)
    link = secrets_dir / "fleet-iam.env"
    link.symlink_to(victim)
    roots = bs.set_secret_roots(secrets_dir, ())
    try:
        with pytest.raises(SystemExit) as stopped:
            bs.secure_write(link, "FLEET_CLIENT_SECRET=x\n")
        assert str(victim.resolve()) in str(stopped.value) and "--secrets-link-root" in str(stopped.value)
        assert victim.read_text() == "root:x:0:0\n" and stat.S_IMODE(victim.stat().st_mode) == 0o644
        assert _leftovers(elsewhere) == [] and _leftovers(secrets_dir) == []

        # a dangling link outside the root: stop, the target's directories are not created
        dangling = secrets_dir / "notification-iam.env"
        dangling.symlink_to(tmp_path / "nowhere" / "deep" / "notification-iam.env")
        with pytest.raises(SystemExit):
            bs.secure_write(dangling, "NS=1\n")
        assert not (tmp_path / "nowhere").exists()

        # a subdirectory that is a link leading out — outside the root as well
        (secrets_dir / "linked").symlink_to(elsewhere, target_is_directory=True)
        with pytest.raises(SystemExit):
            bs.secure_write(secrets_dir / "linked" / "control-plane-iam.env", "A=1\n")
        assert not (elsewhere / "control-plane-iam.env").exists()

        # the same directory as an explicit link root: the write goes through
        bs.set_secret_roots(secrets_dir, (elsewhere,))
        bs.secure_write(link, "FLEET_CLIENT_SECRET=x\n")
        assert victim.read_text() == "FLEET_CLIENT_SECRET=x\n"
        # a dangling link inside the root is written, the target's directory is created in the root
        inside = secrets_dir / "harness-pat"
        inside.symlink_to(secrets_dir / "store" / "harness-pat")
        bs.secure_write(inside, "pat\n")
        assert (secrets_dir / "store" / "harness-pat").read_text() == "pat\n"
    finally:
        roots.clear()


def test_main_sets_secret_roots_from_the_secrets_dir_and_flags(tmp_path):
    source = (ROOT / "deploy" / "bootstrap.py").read_text(encoding="utf-8")
    main = source[source.index("def main()") :]
    assert "--secrets-link-root" in main
    assert "set_secret_roots(secrets_dir, tuple(args.secrets_link_root))" in main
    assert main.index("set_secret_roots(") < main.index("secure_write(")
    assert main.index("set_secret_roots(") < main.index("ensure_service_account(")
    # no built-in link roots: only the secrets directory, unless --secrets-link-root adds one
    roots = bs.set_secret_roots(tmp_path / "secrets", ())
    try:
        assert roots == [Path(os.path.realpath(tmp_path / "secrets"))]
    finally:
        roots.clear()


# ---------------------------------------------------------------- personal assistants: the owner without links


def test_harness_tree_is_handed_to_the_container_without_following_links(tmp_path, monkeypatch, capsys):
    """`harness_people` hands the tree to uid 10001 through lchown: links are neither touched nor
    followed, a directory behind a link is not walked."""
    outside = tmp_path / "outside"
    (outside / "dir").mkdir(parents=True)
    (outside / "token").write_text("x")
    (outside / "dir" / "inner").write_text("y")
    secrets_dir = tmp_path / "secrets"
    folder = secrets_dir / "harness" / "p1"
    folder.mkdir(parents=True)
    (folder / "credentials.json").write_text("{}\n")
    (folder / "claude-oauth-token").symlink_to(outside / "token")
    (folder / "linked-dir").symlink_to(outside / "dir", target_is_directory=True)
    registry = tmp_path / "people.json"
    registry.write_text(json.dumps({"people": [{"iamPrincipalId": "p1", "name": "P"}]}))
    state = {"harnessPeople": {"p1": {"ceiling": sorted(bs.HARNESS_PERSON_CEILING)}}}

    chowned: list[tuple[str, bool]] = []
    monkeypatch.setattr(bs.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        bs.os,
        "chown",
        lambda path, uid, gid, *, follow_symlinks=True: chowned.append((str(path), follow_symlinks)),
    )

    class NoIam:
        def call(self, *args, **kwargs):  # the credentials exist — IAM is not called
            raise AssertionError(args)

    args = type("Args", (), {"harness_people": str(registry), "pat_ttl": 3600})()
    bs.harness_people(args, NoIam(), HEADER, TENANT, "https://example.test/iam", state, lambda: None, secrets_dir)

    paths = {path for path, _ in chowned}
    base = secrets_dir / "harness"
    assert {
        str(base),
        str(folder),
        str(folder / "credentials.json"),
        str(base / "people.json"),
        str(base / "cookie-secret"),
    } <= paths
    assert all(follow is False for _, follow in chowned)
    assert not {str(folder / "claude-oauth-token"), str(folder / "linked-dir")} & paths
    assert not [path for path in paths if path.startswith(str(outside))]
    assert "is a link" in capsys.readouterr().out


# ---------------------------------------------------------------- the identity of a service after recreation
# The account is created anew (the previous one is gone from IAM) → a new IAM principal →
# `PUT …/identity` answers 409 → `POST …/identity:replace`. Registry agents are not relinked
# through the principal's IAM bindings: the core refuses those for registry agents.


ISSUER = "https://cp.example.test/iam"
OPERATOR = {"Authorization": "Bearer operator-admin"}
AGENT_PATH = re.compile(r"^/api/v1/agents/([^/:]+)(/identity|/status)?$")
BINDINGS = re.compile(r"^/api/v1/principals/([^/]+)/iam-bindings$")
REVOKE = re.compile(r"^/api/v1/iam-bindings/([^/]+):revoke$")
REPLACE = re.compile(r"^/api/v1/agents/([^/:]+)/identity:replace$")
HUMAN_ONLY = {"admin", "approvals.decide"}


class FakeCp:
    """The Control Plane as far as the agent registry and IAM bindings go.

    Sign-in: `operator-admin` is the administrator; otherwise an access token of FakeIam with
    the `control-plane` audience → the account's principal → an active binding → the binding's
    permissions. `PUT …/identity` behaves like the core: another identity of a linked agent is a
    409; a new revision with other permissions brings the agent's binding to them (and makes it
    active again)."""

    def __init__(self, iam: FakeIam) -> None:
        self.iam = iam
        self.agents: dict[str, dict] = {}
        self.bindings: dict[str, dict] = {}
        self.principals: dict[str, str] = {}
        self.requests: list[tuple[str, str, dict]] = []
        fake = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def _handle(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                fake.requests.append((self.command, self.path, body))
                status, payload = fake.route(self.command, self.path, body, self.headers)
                raw = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            do_GET = do_POST = do_PUT = _handle

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    @staticmethod
    def error(status: int, code: str) -> tuple[int, dict]:
        return status, {"error": {"code": code, "message": code}}

    def caller(self, headers) -> set[str] | None:
        token = headers.get("Authorization", "").removeprefix("Bearer ")
        if token == "operator-admin":
            return {"*"}
        grant = self.iam.tokens.get(token)
        if not grant or grant["audience"] != "control-plane":
            return None
        account = self.iam.accounts[grant["clientId"]]
        if account["revoked"]:
            return None
        binding = self.binding_of(ISSUER, account["principalId"])
        return set(binding["permissions"]) if binding and binding["status"] == "active" else None

    def binding_of(self, issuer: str, iam_principal: str) -> dict | None:
        return next(
            (b for b in self.bindings.values() if (b["issuer"], b["iamPrincipalId"]) == (issuer, iam_principal)),
            None,
        )

    def upsert(self, principal: str, identity: dict, permissions: list[str]) -> tuple[int, dict]:
        binding = self.binding_of(identity["issuer"], identity["iamPrincipalId"])
        created = binding is None
        if created:
            binding = {"id": str(uuid.uuid4())}
            self.bindings[binding["id"]] = binding
        binding.update(
            principalId=principal,
            issuer=identity["issuer"],
            iamTenantId=identity["iamTenantId"],
            iamPrincipalId=identity["iamPrincipalId"],
            permissions=sorted(set(permissions)),
            status="active",
        )
        return (201 if created else 200), binding

    def route(self, method: str, path: str, body: dict, headers) -> tuple[int, dict]:
        allowed = self.caller(headers)
        if allowed is None:
            return self.error(401, "unauthenticated")

        def need(permission: str) -> bool:
            return "*" in allowed or permission in allowed

        if method == "POST" and path == "/api/v1/agents":
            if not need("agents.manage"):
                return self.error(403, "forbidden")
            agent = self.agents.setdefault(
                body["key"],
                {
                    "key": body["key"],
                    "status": "active",
                    "revision": 0,
                    "spec": None,
                    "principalId": None,
                    "identity": None,
                },
            )
            if agent["spec"] != body["spec"]:
                agent["spec"], agent["revision"] = body["spec"], agent["revision"] + 1
                if agent["identity"]:  # as the core does: the binding by the registry's identity
                    self.upsert(agent["principalId"], agent["identity"], body["spec"]["identity"]["permissions"])
            return 200, {"key": body["key"], "currentRevision": agent["revision"], "principalId": agent["principalId"]}
        if method == "POST" and (m := REPLACE.match(path)):
            # as the core does: only a linked active service; the principal stays, the other
            # bindings of the principal are revoked, the new one gets the revision's permissions
            agent = self.agents.get(m.group(1))
            if agent is None:
                return self.error(404, "not_found")
            if not need("agents.manage"):
                return self.error(403, "forbidden")
            assert 1 <= len(body.get("reason", "")) <= 500
            if not agent["principalId"]:
                return self.error(409, "agent_identity_not_linked")
            if agent["status"] != "active" or agent["spec"]["identity"]["kind"] != "service":
                return self.error(409, "agent_identity_conflict")
            requested = {k: body[k] for k in ("issuer", "iamTenantId", "iamPrincipalId")}
            held = self.binding_of(body["issuer"], body["iamPrincipalId"])
            if held is not None and held["principalId"] != agent["principalId"]:
                return self.error(409, "agent_identity_conflict")
            for binding in self.bindings.values():
                if binding["principalId"] == agent["principalId"] and binding is not held:
                    binding["status"] = "revoked"
            self.upsert(agent["principalId"], requested, agent["spec"]["identity"]["permissions"])
            agent["identity"] = requested
            return 200, {"key": agent["key"], "principalId": agent["principalId"]}
        if m := AGENT_PATH.match(path):
            agent = self.agents.get(m.group(1))
            if agent is None:
                return self.error(404, "not_found")
            if method == "GET" and not m.group(2):
                return 200, {
                    "key": agent["key"],
                    "status": agent["status"],
                    "principalId": agent["principalId"],
                    "revision": {"spec": agent["spec"]},
                }
            if method == "PUT" and m.group(2) == "/status":
                if not need("agents.status.write"):
                    return self.error(403, "forbidden")
                return 200, {"phase": body.get("phase")}
            if method == "PUT" and m.group(2) == "/identity":
                if not need("agents.status.write"):
                    return self.error(403, "forbidden")
                requested = {k: body[k] for k in ("issuer", "iamTenantId", "iamPrincipalId")}
                if agent["principalId"]:
                    if agent["identity"] == requested:
                        return 200, {"key": agent["key"], "principalId": agent["principalId"]}
                    return self.error(409, "agent_identity_conflict")
                if self.binding_of(body["issuer"], body["iamPrincipalId"]):
                    return self.error(409, "agent_identity_conflict")
                principal = str(uuid.uuid4())
                self.principals[principal] = agent["spec"]["identity"]["kind"]
                self.upsert(principal, requested, agent["spec"]["identity"]["permissions"])
                agent["principalId"], agent["identity"] = principal, requested
                return 200, {"key": agent["key"], "principalId": principal}
        if (m := BINDINGS.match(path)) and m.group(1) in self.principals:
            if method != "GET" and any(a["principalId"] == m.group(1) for a in self.agents.values()):
                return self.error(409, "agent_binding_managed_by_registry")
            if not need("principals.write"):
                return self.error(403, "forbidden")
            if method == "GET":
                return 200, {"items": [b for b in self.bindings.values() if b["principalId"] == m.group(1)]}
            if self.principals[m.group(1)] != "human" and HUMAN_ONLY & set(body["permissions"]):
                return self.error(422, "permissions_not_allowed_for_kind")
            return self.upsert(m.group(1), body, body["permissions"])
        if method == "POST" and (m := REVOKE.match(path)):
            if not need("principals.write"):
                return self.error(403, "forbidden")
            self.bindings[m.group(1)]["status"] = "revoked"
            return 200, self.bindings[m.group(1)]
        return self.error(404, "not_found")

    def writes(self) -> list[tuple[str, str, dict]]:
        return [r for r in self.requests if r[0] != "GET"]


def _operator(cp: FakeCp) -> bs.Authorized:
    """The core's transport with the operator's token, as platform_services() of main()."""
    return bs.Authorized(bs.Http(cp.url), OPERATOR["Authorization"].removeprefix("Bearer "))


@pytest.fixture
def platform(tmp_path, monkeypatch):
    monkeypatch.setattr(bs.time, "sleep", lambda _seconds: None)
    iam = FakeIam({key: list(scopes) for key, scopes in bs.AUDIENCES.items()})
    cp = FakeCp(iam)
    state: dict = {"iamAudiences": sorted(bs.AUDIENCES)}
    env = tmp_path / "fleet-iam.env"

    def run(key: str = "fleet-controller", prefix: str = "fleet", env_file: Path = env) -> None:
        bs.ensure_service_identity(
            bs.Http(iam.url),
            _operator(cp),
            HEADER,
            state,
            lambda: None,
            iam_tenant=TENANT,
            issuer=ISSUER,
            step="5d",
            key=key,
            env_file=env_file,
            env_lines=_fleet_lines,
            prefix=prefix,
            restart="restart",
        )

    yield {"iam": iam, "cp": cp, "state": state, "env": env, "run": run}
    iam.server.shutdown()
    cp.server.shutdown()


def _fleet_reports_status(iam: FakeIam, cp: FakeCp, env: Path) -> dict:
    """fleet-controller with its account from the env file: an exchange → PUT /agents/{key}/status in the core."""
    creds = _read_env(env)
    token = bs.Http(iam.url).call(
        "POST",
        "/api/v1/tokens/exchange",
        {
            "clientId": creds["FLEET_CLIENT_ID"],
            "clientSecret": creds["FLEET_CLIENT_SECRET"],
            "audience": "control-plane",
            "scopes": ["control-plane:write"],
        },
    )["accessToken"]
    return bs.Http(cp.url).call(
        "PUT", "/api/v1/agents/fleet-controller/status", {"phase": "running"}, {"Authorization": f"Bearer {token}"}
    )


def test_revoked_fleet_account_is_recreated_and_the_identity_replaced(platform, capsys):
    """The fleet-controller account is revoked → bootstrap creates a new one → PUT identity
    answers 409 agent_identity_conflict → the identity is moved by `identity:replace` →
    fleet-controller works with the core under the new account."""
    iam, cp, state, env = platform["iam"], platform["cp"], platform["state"], platform["env"]
    platform["run"]()
    cp_principal, old_iam = state["fleetCpPrincipalId"], state["fleetIamPrincipalId"]
    old_client = state["fleetServiceAccountClientId"]
    assert _fleet_reports_status(iam, cp, env) == {"phase": "running"}
    capsys.readouterr()

    iam.accounts[old_client]["revoked"] = True  # the env file is in place — the reconciliation sees the account
    with pytest.raises(bs.HttpError) as refused:
        _fleet_reports_status(iam, cp, env)
    assert refused.value.status == 401

    platform["run"]()
    out = capsys.readouterr().out
    new_iam = state["fleetIamPrincipalId"]
    assert new_iam != old_iam and state["fleetServiceAccountClientId"] != old_client
    assert "the principal of the account changed" in out and "identity:replace" in out
    assert _read_env(env)["FLEET_CLIENT_SECRET"] not in out
    assert state["fleetCpPrincipalId"] == cp_principal  # the core's principal and its history stay

    # in the core: a binding of the new identity with the description's permissions, the previous one revoked
    new_binding = cp.binding_of(ISSUER, new_iam)
    spec_permissions = sorted(bs.service_agent("fleet-controller")["spec"]["identity"]["permissions"])
    assert new_binding["principalId"] == cp_principal and new_binding["status"] == "active"
    assert new_binding["permissions"] == spec_permissions
    assert cp.binding_of(ISSUER, old_iam)["status"] == "revoked"
    assert not [r for r in cp.requests if "iam-bindings" in r[1]]
    assert _fleet_reports_status(iam, cp, env) == {"phase": "running"}

    # a repeat: the registry remembers the new identity — an idempotent PUT, no :replace
    writes = len(cp.writes())
    platform["run"]()
    assert [r[1] for r in cp.writes()[writes:]] == ["/api/v1/agents", "/api/v1/agents/fleet-controller/identity"]


def test_new_revision_after_replace_widens_the_new_binding(platform):
    """After `identity:replace` the registry remembers the new identity: a new revision with other
    permissions brings the new binding to them, the previous one stays revoked."""
    iam, cp, state, env = platform["iam"], platform["cp"], platform["state"], platform["env"]
    platform["run"]()
    old_iam = state["fleetIamPrincipalId"]
    iam.accounts[state["fleetServiceAccountClientId"]]["revoked"] = True
    platform["run"]()

    widened = json.loads(json.dumps(bs.service_agent("fleet-controller")))
    widened["spec"]["identity"]["permissions"].append("events.read")
    original = bs.service_agent
    try:
        bs.service_agent = lambda key: json.loads(json.dumps(widened)) if key == "fleet-controller" else original(key)
        platform["run"]()
    finally:
        bs.service_agent = original
    new_binding = cp.binding_of(ISSUER, state["fleetIamPrincipalId"])
    assert "events.read" in new_binding["permissions"] and new_binding["status"] == "active"
    assert cp.binding_of(ISSUER, old_iam)["status"] == "revoked"
    assert _fleet_reports_status(iam, cp, env) == {"phase": "running"}


def test_notification_service_identity_is_replaced_the_same_way(platform, tmp_path, capsys):
    iam, cp, state = platform["iam"], platform["cp"], platform["state"]
    env = tmp_path / "notification-iam.env"
    platform["run"]("notification-service", "notify", env)
    del iam.accounts[state["notifyServiceAccountClientId"]]  # the account is gone entirely (404)
    platform["run"]("notification-service", "notify", env)
    assert "identity:replace" in capsys.readouterr().out
    assert cp.binding_of(ISSUER, state["notifyIamPrincipalId"])["principalId"] == state["notifyCpPrincipalId"]


def test_other_identity_errors_are_not_masked(platform):
    """Only 409 agent_identity_conflict leads to a replacement; 403 and the rest — as they are."""
    cp = platform["cp"]
    original = cp.route

    def forbidden(method, path, body, headers):
        if path.endswith("/identity"):
            return cp.error(403, "forbidden")
        return original(method, path, body, headers)

    cp.route = forbidden
    with pytest.raises(bs.HttpError) as refused:
        platform["run"]()
    assert refused.value.status == 403 and refused.value.code == "forbidden"
    assert not [r for r in cp.requests if "iam-bindings" in r[1] or r[1].endswith("identity:replace")]


# ---------------------------------------------------------------- a narrowed ceiling


def _narrowed(scope: str = "notifications:send") -> tuple[dict, dict]:
    """The fleet-controller account without `scope` and the audience registry without it too —
    as after `sync_audiences` once the code removed the scope."""
    account = bs.service_account_for("fleet-controller")
    narrowed = {**account, "scopeCeiling": [s for s in account["scopeCeiling"] if s != scope]}
    registry = {key: [s for s in scopes if s != scope] for key, scopes in bs.AUDIENCES.items()}
    return narrowed, registry


@pytest.mark.parametrize("lost_env", [False, True], ids=["ceiling", "ceiling+rotate"])
def test_narrowed_ceiling_passes_although_the_probe_is_refused(world, lost_env, capsys):
    """IAM checks the final state of the account against the registry even on an empty PATCH: the
    previous ceiling with a scope that is no longer in the registry gives 422. Bootstrap then
    sends just the new ceiling (without rotateSecret), checks the principal by the response and
    only after that rotates the secret, if it is needed at all."""
    fake, state, env = world["fake"], world["state"], world["env"]
    fake.audiences = {key: set(scopes) for key, scopes in bs.AUDIENCES.items()}
    world["ensure"](bs.service_account_for("fleet-controller"))
    client, principal = state["fleetServiceAccountClientId"], state["fleetIamPrincipalId"]
    secret, env_before = fake.accounts[client]["secret"], env.read_text()
    narrowed, registry = _narrowed()
    fake.audiences = {key: set(scopes) for key, scopes in registry.items()}  # sync_audiences has run
    if lost_env:
        env.unlink()

    assert world["ensure"](narrowed) == ({"updated", "rotated"} if lost_env else {"updated"})
    bodies = [r[2] for r in fake.service_account_calls("PATCH")]
    ceiling_only = {
        "audiences": sorted(set(narrowed["audiences"])),
        "scopeCeiling": sorted(set(narrowed["scopeCeiling"])),
    }
    assert bodies == [{}, ceiling_only] + ([{"rotateSecret": True}] if lost_env else [])
    assert "notifications:send" not in fake.accounts[client]["scopeCeiling"]
    assert state["fleetIamPrincipalId"] == principal and state["fleetServiceAccountClientId"] == client
    assert state["fleetServiceAccountCeiling"] == bs.service_account_ceiling(narrowed)
    if lost_env:
        assert _read_env(env)["FLEET_CLIENT_SECRET"] == fake.accounts[client]["secret"] != secret
    else:
        # not rotated without a need
        assert fake.accounts[client]["secret"] == secret and env.read_text() == env_before
    assert "the previous ceiling is outside the audience registry" in capsys.readouterr().out

    # the next run: the ceiling is in the registry, the reconciliation passes, no writes
    before = len(fake.requests)
    assert world["ensure"](narrowed) == set()
    assert [r[2] for r in fake.requests[before:]] == [{}]


def test_narrowed_ceiling_of_a_foreign_account_stops_before_the_secret(world):
    fake, state, env = world["fake"], world["state"], world["env"]
    fake.audiences = {key: set(scopes) for key, scopes in bs.AUDIENCES.items()}
    world["ensure"](bs.service_account_for("fleet-controller"))
    client = state["fleetServiceAccountClientId"]
    secret = fake.accounts[client]["secret"]
    narrowed, registry = _narrowed()
    fake.audiences = {key: set(scopes) for key, scopes in registry.items()}
    state["fleetIamPrincipalId"] = str(uuid.uuid4())  # a state of another account
    env.unlink()
    state_before = json.loads(json.dumps(state))

    with pytest.raises(SystemExit) as stopped:
        world["ensure"](narrowed)
    assert "the ceiling of this account in IAM is already replaced" in str(stopped.value)
    assert [r[2] for r in fake.service_account_calls("PATCH")][-1] != {"rotateSecret": True}
    assert not any(r[2].get("rotateSecret") for r in fake.service_account_calls("PATCH"))
    assert fake.accounts[client]["secret"] == secret and not env.exists() and state == state_before


def test_probe_refused_without_a_new_ceiling_is_not_masked(world):
    """422 on the reconciliation while the ceiling in the code did not change (the registry was
    narrowed bypassing the code) — the error as it is: there is nothing to send, and bootstrap
    must not silently fit the ceiling to the registry."""
    fake = world["fake"]
    fake.audiences = {key: set(scopes) for key, scopes in bs.AUDIENCES.items()}
    account = bs.service_account_for("fleet-controller")
    world["ensure"](account)
    fake.audiences["notification-service"].discard("notifications:send")
    with pytest.raises(bs.HttpError) as refused:
        world["ensure"](account)
    assert (refused.value.status, refused.value.detail) == (422, "invalid_scope_ceiling")
    assert [r[2] for r in fake.service_account_calls("PATCH")] == [{}]


# ---------------------------------------------------------------- a foreign identity in the state


def test_new_account_with_a_principal_already_in_state_is_refused(world):
    """IAM gave the new account the operator's principal: relinking would hand the operator's
    binding to the service (the core's upsert moves it without asking) — stop before the env file
    and the state."""
    fake, state, env = world["fake"], world["state"], world["env"]
    operator = str(uuid.uuid4())
    state["iamOperatorPrincipalId"] = operator
    fake.next_principal = operator
    bs.sync_audiences(world["http"], HEADER, TENANT, state, lambda: None)
    with pytest.raises(SystemExit) as stopped:
        world["ensure"](bs.service_account_for("fleet-controller"))
    assert "iamOperatorPrincipalId" in str(stopped.value)
    assert not env.exists() and "fleetIamPrincipalId" not in state and "fleetServiceAccountClientId" not in state


@pytest.mark.parametrize("clash", ["principal", "client"])
def test_service_identity_clashing_with_another_service_is_not_linked(platform, tmp_path, clash):
    iam, cp, state = platform["iam"], platform["cp"], platform["state"]
    platform["run"]()
    platform["run"]("notification-service", "notify", tmp_path / "notification-iam.env")
    key = "IamPrincipalId" if clash == "principal" else "ServiceAccountClientId"
    state[f"notify{key}"] = state[f"fleet{key}"]
    writes = len(cp.writes())
    with pytest.raises(SystemExit) as stopped:
        bs.ensure_service_identity(
            bs.Http(iam.url),
            _operator(cp),
            HEADER,
            state,
            lambda: None,
            iam_tenant=TENANT,
            issuer=ISSUER,
            step="5c",
            key="notification-service",
            env_file=tmp_path / "notification-iam.env",
            env_lines=_fleet_lines,
            prefix="notify",
            restart="restart",
        )
    # stopped by the account's reconciliation (the principal/client is not of this account) or by
    # the identity check
    assert "state" in str(stopped.value)
    assert len(cp.writes()) == writes


def test_identity_check_names_the_clashing_state_key_and_runs_before_the_core():
    state = {
        "iamOperatorPrincipalId": "p-op",
        "fleetIamPrincipalId": "p-fleet",
        "fleetServiceAccountClientId": "c-f",
        "notifyIamPrincipalId": "p-new",
        "cpServiceAccountPrincipalId": "p-cp",
    }
    bs.check_identity_unique(state, "notifyIamPrincipalId", "p-new", "notifyServiceAccountClientId", "c-new")
    for principal, client, key in [
        ("p-op", "c-new", "iamOperatorPrincipalId"),
        ("p-cp", "c-new", "cpServiceAccountPrincipalId"),
        ("p-fleet", "c-new", "fleetIamPrincipalId"),
        ("p-new", "c-f", "fleetServiceAccountClientId"),
    ]:
        with pytest.raises(SystemExit) as stopped:
            bs.check_identity_unique(state, "notifyIamPrincipalId", principal, "notifyServiceAccountClientId", client)
        assert key in str(stopped.value)
    source = (ROOT / "deploy" / "bootstrap.py").read_text(encoding="utf-8")
    body = source[source.index("def ensure_service_identity(") : source.index("def platform_services(")]
    assert body.index("check_identity_unique(") < body.index('"/api/v1/agents"')


# ---------------------------------------------------------------- a race: a directory swapped for a link


def test_directory_swapped_for_a_link_after_the_check_is_not_followed(tmp_path, monkeypatch):
    """The root check passed, and then a directory inside the root was swapped for a link leading
    out: the path components are opened with O_NOFOLLOW — the write fails, nothing goes out."""
    secrets_dir, outside = tmp_path / "secrets", tmp_path / "outside"
    secrets_dir.mkdir()
    outside.mkdir()
    lexical = Path(os.path.realpath(secrets_dir)) / "linked" / "control-plane-iam.env"
    (secrets_dir / "linked").symlink_to(outside, target_is_directory=True)  # swapped after the check
    monkeypatch.setattr(
        bs, "_secret_target_and_root", lambda path, roots=None: (lexical, Path(os.path.realpath(secrets_dir)))
    )
    with pytest.raises(OSError):
        bs.secure_write(secrets_dir / "linked" / "control-plane-iam.env", "A=1\n")
    assert list(outside.iterdir()) == []


def test_secure_write_creates_missing_directories_inside_the_root(tmp_path):
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    target = secrets_dir / "harness" / "p1" / "credentials.json"
    bs.secure_write(target, "{}\n", roots=[secrets_dir])
    assert target.read_text() == "{}\n" and stat.S_IMODE(target.stat().st_mode) == 0o600
