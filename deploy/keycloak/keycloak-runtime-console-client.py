"""Create or update the web console's client in a running realm platform.

The realm template (platform-realm.json) already has the client and is imported only on the
first start of Keycloak; on an existing realm — or when the public address or the secret
changed — the client is brought in line through the Admin API with this script.

A confidential OIDC client `runtime-console`: Authorization Code + PKCE S256, redirect
`<public>/console/_auth/callback`. The console (its BFF) hands the IdP token only to IAM
`federation:exchange`, so the audience `iam-service` is added to the access and id tokens —
the same audience as of the `keycloak` provider in IAM. The BFF exchanges the id token: it is
a JWT at any OIDC IdP.

The client secret lives in the file SECRET_FILE (by default /secrets/runtime-console-oidc-secret,
0600, created by `make secrets`): if it exists, it is set in Keycloak as is; otherwise a new one is
generated and written. The secret is never printed. Idempotent: an existing client is brought
in line with the template, a repeat changes nothing. Run it as a one-off container in the
compose network:

    docker run --rm --network taimen_default -v "$PWD/deploy/keycloak:/s:ro" \
      -v "$PWD/secrets:/secrets" -e KC_ADMIN_PASSWORD=… -e WEB_BASE_URL=https://taimen.example.com \
      python:3.12-alpine python /s/keycloak-runtime-console-client.py

Local development of the BFF outside Caddy: LOCAL_PORTS=5173 adds
http://localhost:5173/console/_auth/callback (several ports separated by commas).
On Linux after the first run: chown 10001:10001 secrets/runtime-console-oidc-secret.
"""

import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("KC_INTERNAL_URL", "http://keycloak:8080/auth")
REALM = os.environ.get("KC_REALM", "platform")
CLIENT_ID = os.environ.get("RUNTIME_CONSOLE_OIDC_CLIENT_ID", "runtime-console")
WEB = os.environ["WEB_BASE_URL"].rstrip("/")
SECRET_FILE = os.environ.get("SECRET_FILE", "/secrets/runtime-console-oidc-secret")
LOCAL_PORTS = [p.strip() for p in os.environ.get("LOCAL_PORTS", "").split(",") if p.strip()]
CALLBACK = "/console/_auth/callback"


def call(method, path, token=None, body=None, form=None):
    data = None
    headers = {"Accept": "application/json"}
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


def client_secret():
    """The secret from the file or a new one (0600). The value is never printed."""
    try:
        with open(SECRET_FILE, encoding="utf-8") as handle:
            value = handle.read().strip()
        if value:
            return value, False
    except FileNotFoundError:
        pass
    value = secrets.token_urlsafe(32)
    descriptor = os.open(SECRET_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(descriptor, (value + "\n").encode())
    finally:
        os.close(descriptor)
    return value, True


def representation(secret):
    origins = [WEB] + [f"http://localhost:{port}" for port in LOCAL_PORTS]
    redirects = [origin + CALLBACK for origin in origins]
    return {
        "clientId": CLIENT_ID,
        "name": CLIENT_ID,
        "description": "Web console: a confidential client, Authorization Code + PKCE (BFF)",
        "enabled": True,
        "protocol": "openid-connect",
        "publicClient": False,
        "clientAuthenticatorType": "client-secret",
        "secret": secret,
        "standardFlowEnabled": True,
        "directAccessGrantsEnabled": False,
        "implicitFlowEnabled": False,
        "serviceAccountsEnabled": False,
        "frontchannelLogout": True,
        "redirectUris": redirects,
        "webOrigins": origins,
        "attributes": {
            "pkce.code.challenge.method": "S256",
            "post.logout.redirect.uris": "##".join(origin + "/console/" for origin in origins),
        },
    }


# The IdP token goes only to IAM federation:exchange — the iam-service audience in both tokens.
MAPPER = {
    "name": "iam-service-audience",
    "protocol": "openid-connect",
    "protocolMapper": "oidc-audience-mapper",
    "consentRequired": False,
    "config": {
        "included.client.audience": "iam-service",
        "id.token.claim": "true",
        "access.token.claim": "true",
        "introspection.token.claim": "true",
    },
}


def ok(what, status):
    """A non-2xx status stops the run. The response body is not printed: an Admin API response
    about a client may carry its representation with the secret."""
    if not 200 <= status < 300:
        raise SystemExit(f"{what}: HTTP {status}")
    return status


def find_client(tok):
    st, found = call("GET", f"/admin/realms/{REALM}/clients?clientId={urllib.parse.quote(CLIENT_ID)}", tok)
    ok(f"GET client {CLIENT_ID}", st)
    return found or []


def main():
    st, t = call(
        "POST",
        "/realms/master/protocol/openid-connect/token",
        form={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": os.environ.get("KC_ADMIN_USER", "admin"),
            "password": os.environ["KC_ADMIN_PASSWORD"],
        },
    )
    if st != 200:
        raise SystemExit(f"admin token: HTTP {st}")
    tok = t["access_token"]
    secret, generated = client_secret()
    print("secret:", SECRET_FILE, "(new)" if generated else "(from the file)")
    wanted = representation(secret)
    found = find_client(tok)
    if found:
        cid = found[0]["id"]
        current = found[0]
        # GET does not return the secret of a confidential client: compare without it and always
        # set the secret (PUT is idempotent) — otherwise the file and Keycloak could drift silently.
        same = all(current.get(k) == v for k, v in wanted.items() if k not in ("secret", "attributes")) and all(
            (current.get("attributes") or {}).get(k) == v for k, v in wanted["attributes"].items()
        )
        st, _ = call("PUT", f"/admin/realms/{REALM}/clients/{cid}", tok, {**current, **wanted})
        ok(f"PUT client {CLIENT_ID}", st)
        print("client", CLIENT_ID, "unchanged" if same else "updated", st)
    else:
        st, _ = call("POST", f"/admin/realms/{REALM}/clients", tok, wanted)
        ok(f"POST client {CLIENT_ID}", st)
        print("client", CLIENT_ID, "created", st)
        found = find_client(tok)
        if not found:
            raise SystemExit(f"client {CLIENT_ID}: created, but GET does not find it")
        cid = found[0]["id"]
    st, mappers = call("GET", f"/admin/realms/{REALM}/clients/{cid}/protocol-mappers/models", tok)
    ok("GET protocol mappers", st)
    existing = next((m for m in mappers or [] if m["name"] == MAPPER["name"]), None)
    if existing is None:
        st, _ = call("POST", f"/admin/realms/{REALM}/clients/{cid}/protocol-mappers/models", tok, MAPPER)
        ok(f"POST mapper {MAPPER['name']}", st)
        print("mapper added", st)
    elif existing.get("config") != MAPPER["config"]:
        st, _ = call(
            "PUT",
            f"/admin/realms/{REALM}/clients/{cid}/protocol-mappers/models/{existing['id']}",
            tok,
            {**existing, **MAPPER},
        )
        ok(f"PUT mapper {MAPPER['name']}", st)
        print("mapper updated", st)
    else:
        print("mapper exists")
    print("redirect:", ", ".join(wanted["redirectUris"]))


if __name__ == "__main__":
    main()
