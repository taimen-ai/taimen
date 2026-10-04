"""Bootstrap step 5b — packages as one installation plan.

`deploy/bootstrap.py` installs the catalog through ``install.plan()`` → ``install.apply()`` of
the package SDK: the plan is written to a file in the state directory, exactly that plan is
applied without a human's answer (``assume_yes`` — running the initial setup is the operator's
decision), and a repeated bootstrap writes nothing — the plan is empty.

The credentials of step 5b are token providers (``package_sdk.auth.Bearer``): the core's access
token lives minutes and an installation may take longer, so ``Authorization`` is taken before
every request. This is checked on a core whose token expires faster than the installation runs.

The stand is the fake core of the package SDK (``FakeCore`` of its installation tests: the
catalog, the core's plan with processes and calendars, ontologies, retire) and a fake
notification service. The core's code is usually not importable in the tools/tests environment
(its dependencies are missing): then the three normalizations the fake takes from the core are
replaced by identities — the plan compares what it writes.

The installation under test is built in ``tmp_path`` from the package SDK's sample packages
(``acme-base``, ``acme-claims``) plus an ontology, a notification rule and a ``retire`` section,
so that every section of the plan has work to do; the umbrella's own ``deploy/packages.yaml``
is the installation without notification rules.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import types
import uuid
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_SDK = ROOT / "sdk" / "package-sdk"
for path in (PACKAGE_SDK / "src", PACKAGE_SDK):  # the SDK itself and its tests (the fake core)
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

try:
    from tests.test_install import FIXTURES, FakeCore  # noqa: E402
    from tests.umbrella.test_cp_packages import FakeNotificationService  # noqa: E402
except ImportError as error:  # the submodule without tests, or the fakes moved
    pytest.skip(
        f"the fake core of the package SDK (tests.test_install.FakeCore, "
        f"tests.umbrella.test_cp_packages.FakeNotificationService) does not import: {error}",
        allow_module_level=True,
    )

from package_sdk import install  # noqa: E402
from package_sdk.apply import HttpError as PackageHttpError  # noqa: E402
from package_sdk.install.plan import VARIABLE_LOOKUP, read_plan  # noqa: E402

SERVER = "http://127.0.0.1:18000"
DEFAULT = ROOT / "deploy" / "packages.yaml"
COMPANY = {"name": "company", "version": 1, "kinds": [{"kind": "customer"}]}
CLAIMS = {
    "name": "claims",
    "version": 1,
    "extends": ["company@1"],
    "kinds": [{"kind": "case"}, {"kind": "claim_outcome"}],
    "relations": [{"relation": "filed_by"}, {"relation": "resolved_by"}],
}
RULE = {
    "description": "Ask the assignee for a decision",
    "on": {"type": "approval.requested"},
    "recipient": {"kind": "assigned"},
    "notification": {"type": "approval.requested", "title": "Decision needed: {{task.title}}"},
    "dedupKeyTemplate": "approval:{{event.entityId}}",
    "close": {"on": ["approval.approved", "approval.rejected"]},
}


def _bootstrap() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("taimen_bootstrap", ROOT / "deploy" / "bootstrap.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BOOTSTRAP = _bootstrap()


def _write(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _object(kind: str, key: str, spec: dict) -> dict:
    return {"apiVersion": "taimen.ai/v1", "kind": kind, "key": key, "spec": spec}


@pytest.fixture
def claims(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An installation with every kind of work for the plan: the catalog and a process of the
    sample packages, two ontologies enabled for a workspace, a notification rule, and a task
    type and a calendar to retire. Returns the installation file."""
    packages = tmp_path / "packages"
    shutil.copytree(FIXTURES, packages)
    monkeypatch.setattr(BOOTSTRAP.package_model, "ROOT", tmp_path)
    monkeypatch.setattr(BOOTSTRAP.package_model, "PACKAGES_DIR", packages)
    _write(packages / "acme-base" / "knowledge-packs" / "company.yaml", _object("KnowledgePack", "company", COMPANY))
    _write(packages / "acme-claims" / "knowledge-packs" / "claims.yaml", _object("KnowledgePack", "claims", CLAIMS))
    _write(
        packages / "acme-base" / "notification-rules" / "approval-requested.yaml",
        _object("NotificationRule", "approval-requested", RULE),
    )
    installation = tmp_path / "deploy" / "packages.yaml"
    _write(
        installation,
        {
            "apiVersion": "taimen.ai/v1",
            "kind": "Installation",
            "key": "claims",
            "spec": {
                "packages": ["acme-claims"],
                "knowledge": [{"workspace": "${CLAIMS_WORKSPACE_ID}", "packs": ["company@1", "claims@1"]}],
                "retire": {"TaskType": ["legacy-claim"], "Calendar": ["old-calendar"]},
            },
        },
    )
    return installation


def _core_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    """The core's normalizations FakeControlPlane uses; without the core's code — identities."""
    stubs = {
        "control_plane.domain.skill_contract": {"normalize_contract": lambda contract: contract},
        "control_plane.domain.work_rules": {
            "normalize_rule_spec": lambda trigger, condition, interpretation, action: types.SimpleNamespace(
                trigger=trigger,
                condition=True if condition is None else condition,
                interpretation=interpretation,
                action=action,
            )
        },
        "control_plane.domain.artifact_type": {
            "validate_artifact_type_definition": lambda metadata_schema, media_types, max_bytes, global_max_bytes: (
                types.SimpleNamespace(metadata_schema=metadata_schema, media_types=media_types, max_bytes=max_bytes)
            )
        },
    }
    for name, attrs in stubs.items():
        try:
            importlib.import_module(name)
        except ImportError:
            module = types.ModuleType(name)
            for attr, value in attrs.items():
                setattr(module, attr, value)
            monkeypatch.setitem(sys.modules, name, module)


class Core(FakeCore):
    """Plus the stand objects the installation variables refer to (principal, role, project)."""

    def __init__(self, known: set[str]) -> None:
        super().__init__()
        self.known = known

    def call(self, method, path, body=None, headers=None):  # type: ignore[no-untyped-def]
        for kind in ("principal", "role", "project"):
            prefix = "/api/v1" + VARIABLE_LOOKUP[kind].split("{", 1)[0]
            if method == "GET" and path.startswith(prefix) and path[len(prefix) :] in self.known:
                return {"id": path[len(prefix) :]}
        return super().call(method, path, body, headers)


def _stand(
    installation: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    make_core=None,
    operator=None,
    notify_bearer=None,
    notify=None,
):
    """A copy of the installation file, values of all its variables and a fake stand for them.
    Credentials are as in bootstrap: token providers of the core and of the notification service."""
    _core_domain(monkeypatch)
    copy = tmp_path / "state" / "install" / installation.name
    copy.parent.mkdir(parents=True)
    shutil.copy(installation, copy)
    loaded = install.load(copy, strict=False).installation
    env: dict[str, str] = {}
    for package in loaded.packages:
        for name, declared in (package.spec.get("variables") or {}).items():
            if isinstance(declared, dict):
                kind = declared.get("kind", "string")
                if kind == "url":
                    env[name] = f"https://example.com/{name.lower()}"
                elif kind in VARIABLE_LOOKUP:
                    env[name] = str(uuid.uuid4())
    for entry in loaded.knowledge:
        name = str(entry["workspace"]).strip("${}")
        env.setdefault(name, str(uuid.uuid4()))
    core = (make_core or Core)(set(env.values()))
    core.workspaces |= set(env.values())
    notify = notify if notify is not None else FakeNotificationService()
    tokens: list[str] = []

    def notify_token() -> str:
        tokens.append("n")
        return "n"

    target = BOOTSTRAP.package_target(
        SERVER,
        operator or BOOTSTRAP.Bearer.static_token("t"),
        {**env, "NOTIFICATION_SERVICE_URL": "https://example.com/notify"},
        copy,
        notify_bearer or BOOTSTRAP.Bearer(notify_token),
    )
    if target.notify is not None:
        target.notify = (notify, target.notify[1])  # the token provider is the one bootstrap gave
    assert isinstance(target.http, BOOTSTRAP.Authorized), "the core's token — before every request"
    target.http.http = core
    return copy, env, core, notify, target, tokens


def test_bootstrap_installs_every_kind_of_the_installation_by_one_plan(claims, tmp_path, monkeypatch):
    copy, env, core, notify, target, tokens = _stand(claims, tmp_path, monkeypatch)
    assert tokens == ["n"], "notification rules — a token of the notification-service audience"
    # a stand with what the installation retires (the retire section)
    core.rows["task-types"].append({"id": "tt-legacy", "key": "legacy-claim", "version": 1, "status": "active"})
    core.calendars["old-calendar"] = {"key": "old-calendar", "status": "active"}
    plan_path = tmp_path / "state" / "local.packages-plan.json"
    lines: list[str] = []

    summary = BOOTSTRAP.install_packages(copy, target=target, env=env, plan_path=plan_path, log=lines.append)

    assert summary["applied"] and summary["changes"] > 0
    document = read_plan(plan_path)  # the plan is a file, with the whole planHash
    assert document["planHash"] == summary["planHash"]
    kinds = [s["kind"] for s in document["sections"]]
    assert kinds == ["catalog", "core", "knowledge", "notification-rules", "retire"]
    # processes go through the core's plan, each package with them separately
    assert [s["package"] for s in document["sections"] if s["kind"] == "core"] == ["acme-claims"]
    assert len(core.apply_calls) == 1
    assert "Process/claim" in core.published
    # the catalog: the role of the base package
    assert {r["slug"] for r in core.rows["roles"]} == {"claims-officer"}
    # ontologies: registered as KnowledgePack objects and enabled for the trees of the knowledge section
    assert {"company@1", "claims@1"} <= set(core.packs)
    assert {ws: settings["packs"] for ws, settings in core.enabled.items()} == {
        env["CLAIMS_WORKSPACE_ID"]: ["company@1", "claims@1"]
    }
    # notification rules go to the notification service
    assert {r["key"] for r in notify.rows} == {"approval-requested"}
    # retire: the task type is deprecated, the calendar is retired
    assert {r["status"] for r in core.rows["task-types"] if r["key"] == "legacy-claim"} == {"deprecated"}
    assert core.calendars["old-calendar"]["status"] == "retired"
    # without a human — and the log says so
    assert any("bootstrap" in line and "assume_yes" in line for line in lines)
    assert any("without confirmation by a human (assume_yes)" in line for line in lines)

    applied_before = len(core.apply_calls)
    again = BOOTSTRAP.install_packages(copy, target=target, env=env, plan_path=plan_path, log=lines.append)
    assert again["changes"] == 0 and not again["applied"], "a repeated bootstrap: the plan is empty"
    assert next(s for s in read_plan(plan_path)["sections"] if s["kind"] == "retire")["items"] == []
    assert len(core.apply_calls) == applied_before


def test_default_installation_needs_no_notification_service(tmp_path, monkeypatch):
    copy, env, core, _notify, target, tokens = _stand(DEFAULT, tmp_path, monkeypatch)
    assert target.notify is None and tokens == []
    summary = BOOTSTRAP.install_packages(
        copy, target=target, env=env, plan_path=tmp_path / "state" / "local.packages-plan.json", log=lambda _line: None
    )
    assert summary["applied"]
    assert {r["key"] for r in core.rows["task-types"]} == {"request"}


def test_notification_rules_need_the_service_address(claims):
    with pytest.raises(SystemExit, match="NOTIFICATION_SERVICE_URL"):
        BOOTSTRAP.package_target(
            SERVER, BOOTSTRAP.Bearer.static_token("t"), {}, claims, BOOTSTRAP.Bearer.static_token("n")
        )


def test_bootstrap_uses_the_plan_and_not_the_legacy_installer():
    source = (ROOT / "deploy" / "bootstrap.py").read_text(encoding="utf-8")
    assert "package_apply" not in source and "package_sdk import apply as" not in source
    assert "package_install.plan(" in source and "package_install.apply(" in source
    assert "assume_yes=True" in source and "--no-packages" in source


def test_operator_pat_gets_the_notification_audience_only_when_step_5b_needs_it(claims, tmp_path):
    """Least privilege: the notification-service audience and notifications:admin — only if step
    5b installs or retires notification rules; otherwise the ceiling is unchanged (the fallback
    is NOTIFY_TOKEN)."""
    base = (["control-plane"], ["control-plane:read", "control-plane:write", "control-plane:admin"])
    assert BOOTSTRAP.operator_pat_grant(None) == base  # --no-packages
    wide = (base[0] + ["notification-service"], base[1] + ["notifications:admin"])
    assert BOOTSTRAP.operator_pat_grant(claims) == wide  # the installation has a NotificationRule
    retiring = tmp_path / "retiring.yaml"
    _write(
        retiring,
        {
            "apiVersion": "taimen.ai/v1",
            "kind": "Installation",
            "key": "retiring",
            "spec": {"packages": ["acme-base"], "retire": {"NotificationRule": ["old-rule"]}},
        },
    )
    assert BOOTSTRAP.operator_pat_grant(retiring) == wide  # retiring a rule also goes to the service


def test_default_installation_keeps_the_operator_pat_narrow():
    base = (["control-plane"], ["control-plane:read", "control-plane:write", "control-plane:admin"])
    assert BOOTSTRAP.operator_pat_grant(DEFAULT) == base  # no notification rules


# -- an installation longer than the life of an access token -------------------------------

TTL = 300.0  # the life of an access token of the core and of the notification service
STEP = 40.0  # the "time" of one request to the stand: the installation runs many times longer than TTL


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class ExpiringIam:
    """IAM of the stand: the exchange of a PAT for an access token with a TTL and the service
    accounts of steps 5c/5d."""

    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.tokens: dict[str, tuple[str, float]] = {}  # token → (audience, expires)
        self.exchanges: list[str] = []
        self.accounts = 0

    def call(self, method, path, body=None, headers=None):  # type: ignore[no-untyped-def]
        if (method, path) == ("POST", "/api/v1/platform-access-tokens:exchange"):
            assert body["token"] == "pat-operator"
            token = f"{body['audience']}-{len(self.exchanges) + 1}"
            self.exchanges.append(body["audience"])
            self.tokens[token] = (body["audience"], self.clock() + TTL)
            return {"accessToken": token, "expiresIn": int(TTL)}
        if method == "POST" and path.endswith("/service-accounts"):
            self.accounts += 1
            return {
                "clientId": f"client-{self.accounts}",
                "clientSecret": "s",
                "principalId": f"iam-principal-{self.accounts}",
            }
        raise AssertionError(f"unexpected IAM call {method} {path}")

    def admit(self, headers, audience: str) -> bool:
        """Every request to the stand takes STEP seconds; the token must be a live token of the audience."""
        self.clock.now += STEP
        token = str((headers or {}).get("Authorization", "")).removeprefix("Bearer ")
        granted, until = self.tokens.get(token, ("", 0.0))
        return granted == audience and self.clock() < until


def expiring_core(iam: ExpiringIam, rejected: list[str]):
    class ExpiringCore(Core):
        def call(self, method, path, body=None, headers=None):  # type: ignore[no-untyped-def]
            if not iam.admit(headers, "control-plane"):
                rejected.append(f"core {method} {path}")
                raise PackageHttpError(f"{method} {path}: HTTP 401", 401, {"error": {"code": "invalid_credentials"}})
            return super().call(method, path, body, headers)

    return ExpiringCore


class ExpiringNotify(FakeNotificationService):
    def __init__(self, iam: ExpiringIam, rejected: list[str]) -> None:
        super().__init__()
        self.iam, self.rejected = iam, rejected

    def call(self, method, path, body=None, headers=None):  # type: ignore[no-untyped-def]
        if not self.iam.admit(headers, "notification-service"):
            self.rejected.append(f"notify {method} {path}")
            raise PackageHttpError(f"{method} {path}: HTTP 401", 401, {"error": "invalid_token"})
        return super().call(method, path, body, {**(headers or {}), "Authorization": "Bearer n"})


class ExpiringCp:
    """The core of the steps after 5b: the agent registry (5c/5d) and the revocation of the
    legacy key — with the same token."""

    def __init__(self, iam: ExpiringIam, rejected: list[str]) -> None:
        self.iam, self.rejected = iam, rejected
        self.calls: list[tuple[str, str]] = []

    def call(self, method, path, body=None, headers=None):  # type: ignore[no-untyped-def]
        if not self.iam.admit(headers, "control-plane"):
            self.rejected.append(f"core {method} {path}")
            raise BOOTSTRAP.HttpError(method, path, 401, json.dumps({"error": {"code": "invalid_credentials"}}))
        self.calls.append((method, path))
        if method == "POST" and path == "/api/v1/agents":
            return {"key": body["key"], "currentRevision": 1, "principalId": None}
        if method == "PUT" and path.endswith("/identity"):
            return {"principalId": f"cp-{path.split('/')[-2]}"}
        if method == "POST" and path.endswith(":revoke"):
            return {}
        raise AssertionError(f"unexpected core call {method} {path}")


def test_bootstrap_outlives_the_access_token_through_step_5b_and_after(claims, tmp_path, monkeypatch):
    """The token of the core and of the notification service lives TTL, the installation and the
    steps after it run several times longer: no request gets 401 — the provider exchanges the PAT
    again before it expires. A token taken once at step 4 would fail in the middle of 5b."""
    clock = Clock()
    iam = ExpiringIam(clock)
    rejected: list[str] = []
    monkeypatch.delenv("NOTIFY_TOKEN", raising=False)
    operator = BOOTSTRAP.operator_bearer(iam, "pat-operator", clock=clock)
    operator.token()  # step 4: the first exchange right away
    copy, env, core, notify, target, _ = _stand(
        claims,
        tmp_path,
        monkeypatch,
        make_core=expiring_core(iam, rejected),
        operator=operator,
        notify_bearer=BOOTSTRAP.notify_bearer(iam, "pat-operator", {}, pat_file=tmp_path / "harness-pat", clock=clock),
        notify=ExpiringNotify(iam, rejected),
    )

    summary = BOOTSTRAP.install_packages(
        copy, target=target, env=env, plan_path=tmp_path / "state" / "local.packages-plan.json", log=lambda _line: None
    )
    assert summary["applied"] and rejected == []
    assert notify.rows, "notification rules applied"

    # 5c, 5d and the revocation of the legacy key — after 5b, with the same provider
    cp = ExpiringCp(iam, rejected)
    state = {"cpLegacyAdminKeyId": "key-1"}
    BOOTSTRAP.platform_services(
        iam,
        BOOTSTRAP.Authorized(cp, operator),
        {"X-IAM-Bootstrap-Token": "b"},
        state,
        lambda: None,
        iam_tenant="t",
        issuer="https://x/iam",
        secrets_dir=tmp_path,
    )
    assert rejected == []
    assert state["cpLegacyAdminKeyRevoked"] is True
    assert ("POST", "/api/v1/api-keys/key-1:revoke") in cp.calls
    assert {path for _, path in cp.calls} >= {
        "/api/v1/agents/notification-service/identity",
        "/api/v1/agents/fleet-controller/identity",
    }

    # the installation ran much longer than the life of a token, and the PAT was exchanged as it expired
    assert clock.now > 3 * TTL
    assert iam.exchanges.count("control-plane") >= clock.now // TTL
    assert iam.exchanges.count("notification-service") >= 1


def test_a_token_rejected_before_its_term_is_renewed_once(tmp_path):
    """The stand rejected a token before its term (the signing key changed, the account was
    revoked and reissued): 401 invalid_credentials — one exchange again and a retry of the same
    request."""
    clock = Clock()
    iam = ExpiringIam(clock)
    rejected: list[str] = []
    cp = ExpiringCp(iam, rejected)
    operator = BOOTSTRAP.operator_bearer(iam, "pat-operator", clock=clock)
    authorized = BOOTSTRAP.Authorized(cp, operator)
    authorized.call("POST", "/api/v1/api-keys/k:revoke", None, {})
    iam.tokens.clear()  # the stand no longer recognizes the issued token
    authorized.call("POST", "/api/v1/api-keys/k:revoke", None, {})
    assert rejected == ["core POST /api/v1/api-keys/k:revoke"]
    assert iam.exchanges == ["control-plane", "control-plane"]
