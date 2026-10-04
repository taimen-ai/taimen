"""The identity of the service agents in bootstrap (steps 5c/5d).

Bootstrap links a service's account by an idempotent `PUT /agents/{key}/identity`, and moves an
account created anew (the previous one is gone from IAM — revoked or deleted) by
`POST /agents/{key}/identity:replace` — the core's principal stays, the previous binding is
revoked. A changed ceiling and a lost env file do not create a new account: a PATCH keeps the
principal, the identity stays. Checked on a fake IAM and a fake core with the semantics of the
core's routes: a change goes through `:replace`, the same identity changes nothing, a repeat is
idempotent, other refusals do not turn into a replacement. The issuer is
`${TAIMEN_PUBLIC_URL}/iam`, as `CP_IAM_ISSUER` in compose.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


bootstrap = load("deploy_bootstrap_service_identity", ROOT / "deploy" / "bootstrap.py")

TENANT = "iam-tenant-1"
PUBLIC_URL = "https://platform.example.com"
ISSUER = f"{PUBLIC_URL}/iam"
HEADER = {"X-IAM-Bootstrap-Token": "x"}
AUTH = {"Authorization": "Bearer operator"}
KEY = "notification-service"


def refusal(method: str, path: str, status: int, code: str, **details) -> Exception:
    body = {"error": {"code": code, "message": code, "details": details, "requestId": "r-1"}}
    return bootstrap.HttpError(method, path, status, json.dumps(body))


class FakeIam:
    """IAM service accounts: issuing, a PATCH that keeps the principal, and revocation or
    deletion of an account by an "administrator" (`gone`)."""

    def __init__(self) -> None:
        self.issued = 0
        self.revoked: list[str] = []
        self.accounts: dict[str, dict] = {}
        self.writes: list[tuple[str, str]] = []

    def gone(self, client: str, how: str) -> None:
        if how == "revoked":
            self.accounts[client]["revoked"] = True
        else:
            del self.accounts[client]

    def call(self, method, path, body=None, headers=None):
        assert headers == HEADER, "the IAM administrative API — only with the bootstrap token"
        base = f"/api/v1/tenants/{TENANT}/service-accounts"
        assert path.startswith(base), path
        if method == "PATCH" and not body:
            pass  # the reconciliation by an empty PATCH writes nothing
        else:
            self.writes.append((method, path))
        if method == "POST" and path == base:
            assert body["audiences"] and body["scopeCeiling"]
            self.issued += 1
            client = f"client-{self.issued}"
            self.accounts[client] = {
                "principalId": f"iam-principal-{self.issued}",
                "revoked": False,
                "secret": f"secret-{self.issued}",
            }
            return {
                "clientId": client,
                "clientSecret": f"secret-{self.issued}",
                "principalId": f"iam-principal-{self.issued}",
            }
        if method == "PATCH":
            client = path[len(base) + 1 :]
            account = self.accounts.get(client)
            if account is None:
                raise bootstrap.HttpError(method, path, 404, json.dumps({"detail": "service_account_not_found"}))
            if account["revoked"]:
                raise bootstrap.HttpError(method, path, 409, json.dumps({"detail": "service_account_revoked"}))
            view = {"clientId": client, "principalId": account["principalId"]}
            if body.get("rotateSecret"):
                account["secret"] = view["clientSecret"] = f"{account['secret']}-rotated"
            return view
        if method == "POST" and path.endswith(":revoke"):
            self.revoked.append(path[len(base) + 1 : -len(":revoke")])
            return {}
        raise AssertionError(f"unexpected IAM call {method} {path}")


class FakeCp:
    """The core's agent registry: publishing, `PUT …/identity`, `POST …/identity:replace`, bindings."""

    def __init__(self, trusted_issuer: str = ISSUER) -> None:
        self.trusted = trusted_issuer
        self.agents: dict[str, dict] = {}
        # (issuer, iamPrincipalId) → {principal, iamTenantId, status}
        self.bindings: dict[tuple[str, str], dict] = {}
        self.calls: list[tuple[str, str]] = []
        self.events: list[str] = []

    def call(self, method, path, body=None, headers=None):
        assert headers and headers.get("Authorization") == AUTH["Authorization"]
        self.calls.append((method, path))
        if method == "POST" and path == "/api/v1/agents":
            assert headers.get("Idempotency-Key")
            agent = self.agents.setdefault(
                body["key"], {"principalId": None, "identity": None, "kind": body["spec"]["identity"]["kind"]}
            )
            return self._out(body["key"], agent)
        prefix = "/api/v1/agents/"
        assert path.startswith(prefix), path
        key, _, action = path[len(prefix) :].partition("/")
        assert headers.get("Idempotency-Key"), "a write to the core — with an Idempotency-Key"
        if method == "PUT" and action == "identity":
            return self._link(method, path, key, body)
        if method == "POST" and action == "identity:replace":
            return self._replace(method, path, key, body)
        raise AssertionError(f"unexpected core call {method} {path}")

    def _out(self, key: str, agent: dict) -> dict:
        return {"key": key, "currentRevision": 1, "principalId": agent["principalId"]}

    def _check_issuer(self, method, path, issuer, fallback=None):
        expected = self.trusted or fallback
        if expected and issuer != expected:
            raise refusal(method, path, 422, "iam_issuer_untrusted", issuer=issuer, expected=expected)

    def _taken(self, method, path, key, identity, principal):
        held = self.bindings.get(identity)
        if held is not None and held["principal"] != principal:
            raise refusal(method, path, 409, "agent_identity_conflict", agent=key)

    def _link(self, method, path, key, body):
        self._check_issuer(method, path, body["issuer"])
        agent = self.agents[key]
        requested = (body["issuer"], body["iamTenantId"], body["iamPrincipalId"])
        if agent["principalId"] is not None:
            if agent["identity"] == requested:
                return self._out(key, agent)
            raise refusal(method, path, 409, "agent_identity_conflict", agent=key)
        identity = (body["issuer"], body["iamPrincipalId"])
        self._taken(method, path, key, identity, None)
        agent["principalId"] = f"cp-principal-{key}"
        agent["identity"] = requested
        self.bindings[identity] = {
            "principal": agent["principalId"],
            "iamTenantId": body["iamTenantId"],
            "status": "active",
        }
        self.events.append("iam_binding.created")
        return self._out(key, agent)

    def _replace(self, method, path, key, body):
        assert 1 <= len(body.get("reason", "")) <= 500, "the reason is required"
        agent = self.agents[key]
        if agent["principalId"] is None:
            raise refusal(method, path, 409, "agent_identity_not_linked", agent=key)
        if agent["kind"] != "service":
            raise refusal(method, path, 409, "agent_identity_conflict", agent=key, kind=agent["kind"])
        self._check_issuer(method, path, body["issuer"], agent["identity"][0])
        requested = (body["issuer"], body["iamTenantId"], body["iamPrincipalId"])
        if agent["identity"] == requested:
            return self._out(key, agent)
        identity = (body["issuer"], body["iamPrincipalId"])
        self._taken(method, path, key, identity, agent["principalId"])
        for held_identity, held in self.bindings.items():
            if held["principal"] == agent["principalId"] and held_identity != identity and held["status"] != "revoked":
                held["status"] = "revoked"
                self.events.append("iam_binding.revoked")
        self.bindings[identity] = {
            "principal": agent["principalId"],
            "iamTenantId": body["iamTenantId"],
            "status": "active",
        }
        agent["identity"] = requested
        self.events.append("agent.identity_replaced")
        return self._out(key, agent)

    def active_identities(self, key: str) -> list[tuple[str, str]]:
        principal = self.agents[key]["principalId"]
        return sorted(i for i, b in self.bindings.items() if b["principal"] == principal and b["status"] == "active")


class Setup:
    def __init__(self, tmp_path: Path, cp: FakeCp | None = None) -> None:
        self.iam = FakeIam()
        self.cp = cp or FakeCp()
        self.state: dict = {}
        self.saves = 0
        self.env_file = tmp_path / "notification-iam.env"

    def save(self) -> None:
        self.saves += 1

    def run(self, issuer: str = ISSUER) -> None:
        bootstrap.ensure_service_identity(
            self.iam,
            bootstrap.Authorized(self.cp, AUTH["Authorization"].removeprefix("Bearer ")),
            HEADER,
            self.state,
            self.save,
            iam_tenant=TENANT,
            issuer=issuer,
            step="5c",
            key=KEY,
            env_file=self.env_file,
            env_lines=lambda issued: f"NS_SERVICE_CLIENT_ID={issued['clientId']}\n",
            prefix="notify",
            restart="tools/compose --profile notify up -d notification-service",
        )

    def snapshot(self) -> tuple:
        return (
            copy.deepcopy(self.state),
            copy.deepcopy(self.cp.agents),
            copy.deepcopy(self.cp.bindings),
            list(self.cp.events),
            self.env_file.read_text(),
        )


def test_first_link_goes_through_put(tmp_path):
    s = Setup(tmp_path)
    s.run()
    assert s.cp.calls == [("POST", "/api/v1/agents"), ("PUT", f"/api/v1/agents/{KEY}/identity")]
    assert s.state["notifyCpPrincipalId"] == f"cp-principal-{KEY}"
    assert s.cp.agents[KEY]["identity"] == (ISSUER, TENANT, "iam-principal-1")
    assert s.cp.active_identities(KEY) == [(ISSUER, "iam-principal-1")]


def test_same_identity_and_rerun_change_nothing(tmp_path):
    s = Setup(tmp_path)
    s.run()
    before = s.snapshot()
    for _ in range(2):
        s.cp.calls.clear()
        s.run()
        # IAM is not touched; in the core — only publishing and an idempotent PUT, no :replace
        assert s.iam.writes == [("POST", f"/api/v1/tenants/{TENANT}/service-accounts")]
        assert s.cp.calls == [("POST", "/api/v1/agents"), ("PUT", f"/api/v1/agents/{KEY}/identity")]
        assert s.snapshot() == before


@pytest.mark.parametrize("change", ["env-file-lost", "ceiling-changed"])
def test_patched_account_keeps_the_identity(tmp_path, change):
    """A lost env file and a new ceiling are a PATCH of the same account: the IAM principal
    stays, the identity in the core does not change, `:replace` is not needed."""
    s = Setup(tmp_path)
    s.run()
    if change == "env-file-lost":
        s.env_file.unlink()
    else:
        s.state["notifyServiceAccountCeiling"] = ["notifications:send"]
    s.cp.calls.clear()
    s.run()
    assert s.iam.issued == 1 and s.iam.revoked == []
    assert ("PATCH", f"/api/v1/tenants/{TENANT}/service-accounts/client-1") in s.iam.writes
    assert s.state["notifyIamPrincipalId"] == "iam-principal-1"
    assert s.cp.calls == [("POST", "/api/v1/agents"), ("PUT", f"/api/v1/agents/{KEY}/identity")]
    assert s.cp.active_identities(KEY) == [(ISSUER, "iam-principal-1")]
    if change == "env-file-lost":
        assert s.env_file.read_text() == "NS_SERVICE_CLIENT_ID=client-1\n"


@pytest.mark.parametrize("reissue", ["revoked", "deleted"])
def test_reissued_account_moves_the_identity_through_replace(tmp_path, capsys, reissue):
    s = Setup(tmp_path)
    s.run()
    principal = s.state["notifyCpPrincipalId"]
    s.iam.gone("client-1", reissue)
    s.cp.calls.clear()
    s.cp.events.clear()
    s.run()

    assert s.iam.revoked == []  # the previous account is gone — nothing to revoke
    assert s.state["notifyIamPrincipalId"] == "iam-principal-2"
    assert s.cp.calls == [
        ("POST", "/api/v1/agents"),
        ("PUT", f"/api/v1/agents/{KEY}/identity"),
        ("POST", f"/api/v1/agents/{KEY}/identity:replace"),
    ]
    # the core's principal stays, only the new identity signs in as the service
    assert s.state["notifyCpPrincipalId"] == principal == s.cp.agents[KEY]["principalId"]
    assert s.cp.agents[KEY]["identity"] == (ISSUER, TENANT, "iam-principal-2")
    assert s.cp.active_identities(KEY) == [(ISSUER, "iam-principal-2")]
    assert s.cp.bindings[(ISSUER, "iam-principal-1")]["status"] == "revoked"
    assert s.cp.events == ["iam_binding.revoked", "agent.identity_replaced"]
    assert "identity:replace" in capsys.readouterr().out

    # a repeat after the change is idempotent: no issuing, no :replace, no events
    before = s.snapshot()
    s.cp.calls.clear()
    s.run()
    assert s.iam.issued == 2
    assert ("POST", f"/api/v1/agents/{KEY}/identity:replace") not in s.cp.calls
    assert s.snapshot() == before


def test_replace_carries_the_identity_and_a_reason(tmp_path):
    s = Setup(tmp_path)
    s.run()
    s.iam.gone("client-1", "revoked")
    sent: list[dict] = []
    original = s.cp._replace

    def spy(method, path, key, body):
        sent.append(dict(body))
        return original(method, path, key, body)

    s.cp._replace = spy
    s.run()
    assert len(sent) == 1
    body = sent[0]
    assert {k: body[k] for k in ("issuer", "iamTenantId", "iamPrincipalId")} == {
        "issuer": ISSUER,
        "iamTenantId": TENANT,
        "iamPrincipalId": "iam-principal-2",
    }
    assert KEY in body["reason"] and "5c" in body["reason"]


def test_identity_of_another_principal_is_not_replaced(tmp_path):
    """The agent is not linked yet and the identity is held by another principal: `PUT` answers
    with the same code `agent_identity_conflict`, but a replacement cures nothing here — the
    refusal as it is."""
    s = Setup(tmp_path)
    s.cp.bindings[(ISSUER, "iam-principal-1")] = {
        "principal": "someone-else",
        "iamTenantId": TENANT,
        "status": "active",
    }
    with pytest.raises(bootstrap.HttpError) as refused:
        s.run()
    assert refused.value.status == 409 and refused.value.code == "agent_identity_conflict"
    assert ("POST", f"/api/v1/agents/{KEY}/identity:replace") not in s.cp.calls


def test_untrusted_issuer_is_refused_not_replaced(tmp_path):
    s = Setup(tmp_path)
    s.run()
    s.iam.gone("client-1", "revoked")
    s.cp.calls.clear()
    with pytest.raises(bootstrap.HttpError) as refused:
        s.run(issuer=f"{PUBLIC_URL}//iam")
    assert refused.value.status == 422 and refused.value.code == "iam_issuer_untrusted"
    assert ("POST", f"/api/v1/agents/{KEY}/identity:replace") not in s.cp.calls
    assert s.cp.agents[KEY]["identity"] == (ISSUER, TENANT, "iam-principal-1")


def test_http_error_keeps_the_message_and_reads_the_core_code():
    error = refusal("PUT", "/api/v1/agents/x/identity", 409, "agent_identity_conflict", agent="x")
    assert isinstance(error, RuntimeError) and "HTTP 409" in str(error)
    assert (error.status, error.code) == (409, "agent_identity_conflict")
    plain = bootstrap.HttpError("GET", "/healthz", 502, "<html>bad gateway</html>" + "x" * 1000)
    assert plain.code is None and len(str(plain)) < 500


def test_public_url_with_trailing_slash_is_refused():
    assert bootstrap.public_url_of({"TAIMEN_PUBLIC_URL": PUBLIC_URL}) == PUBLIC_URL
    for bad in (f"{PUBLIC_URL}/", f"{PUBLIC_URL}//"):
        with pytest.raises(SystemExit, match="ends with '/'"):
            bootstrap.public_url_of({"TAIMEN_PUBLIC_URL": bad})
    with pytest.raises(SystemExit, match="is not set"):
        bootstrap.public_url_of({})


def test_bootstrap_issuer_is_the_issuer_compose_gives_the_services():
    """compose builds the issuer from `TAIMEN_PUBLIC_URL` without normalization — bootstrap derives the same."""
    services = yaml.safe_load((ROOT / "deploy/local/compose.yml").read_text(encoding="utf-8"))["services"]
    issuers = {
        "control-plane-api": services["control-plane-api"]["environment"]["CP_IAM_ISSUER"],
        "iam-service": services["iam-service"]["environment"]["IAM_ISSUER"],
        "fleet-controller": services["fleet-controller"]["environment"]["FLEET_IAM_ISSUER"],
        "notification-service": services["notification-service"]["environment"]["NS_IAM_ISSUER"],
    }
    public_url = bootstrap.public_url_of({"TAIMEN_PUBLIC_URL": PUBLIC_URL})
    for service, template in issuers.items():
        head, _, tail = template.partition("}")
        assert head.startswith("${TAIMEN_PUBLIC_URL") and tail == "/iam", (service, template)
        assert public_url + tail == f"{public_url}/iam" == ISSUER, service
    source = (ROOT / "deploy" / "bootstrap.py").read_text(encoding="utf-8")
    assert 'issuer = f"{public_url}/iam"' in source and "public_url_of(env)" in source
    assert '"TAIMEN_PUBLIC_URL"].rstrip' not in source
