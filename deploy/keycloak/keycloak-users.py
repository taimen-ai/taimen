"""Create people in Keycloak (realm platform) through the Admin API.

Keycloak is only an external IdP: there are no roles or tenant attributes here, a person's
authority lives in IAM and the Control Plane. Run it as a one-off container in the compose
network (Python standard library only):

  docker run --rm --network taimen_default -v "$PWD/deploy/keycloak:/s:ro" \
    -e KC_ADMIN_PASSWORD=… -e KC_USERS='[{"username":…,"email":…,"password":…}]' \
    python:3.12-alpine python /s/keycloak-users.py

Passwords are passed only through the environment and never printed; the id (sub) is printed.
Idempotent: an existing user is updated (profile, password). firstName/lastName are required:
without them signing in answers "Account is not fully set up" (defaults: the username and "-").
A temporary password does not pass the console's sign-in either: use "temporary": false.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("KC_INTERNAL_URL", "http://keycloak:8080/auth")
REALM = os.environ.get("KC_REALM", "platform")


def call(method: str, path: str, token: str | None = None, body: object | None = None, form: dict | None = None):
    data = None
    headers = {"Accept": "application/json"}
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None), resp.headers
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()[:300], exc.headers


def main() -> None:
    status, tok, _ = call(
        "POST",
        "/realms/master/protocol/openid-connect/token",
        form={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": os.environ.get("KC_ADMIN_USERNAME", "admin"),
            "password": os.environ["KC_ADMIN_PASSWORD"],
        },
    )
    if status != 200:
        raise SystemExit(f"admin login failed: HTTP {status}")
    token = tok["access_token"]
    for spec in json.loads(os.environ["KC_USERS"]):
        payload = {
            "username": spec["username"],
            "email": spec["email"],
            "enabled": True,
            "emailVerified": True,
            "firstName": spec.get("first_name", spec["username"]),
            "lastName": spec.get("last_name", "-"),
        }
        query = urllib.parse.quote(spec["username"])
        status, existing, _ = call("GET", f"/admin/realms/{REALM}/users?username={query}&exact=true", token)
        if existing:
            user_id = existing[0]["id"]
            call("PUT", f"/admin/realms/{REALM}/users/{user_id}", token, payload)
        else:
            status, _, headers = call("POST", f"/admin/realms/{REALM}/users", token, payload)
            if status != 201:
                raise SystemExit(f"create {spec['username']}: HTTP {status}")
            user_id = headers["Location"].rstrip("/").split("/")[-1]
        call(
            "PUT",
            f"/admin/realms/{REALM}/users/{user_id}/reset-password",
            token,
            {"type": "password", "value": spec["password"], "temporary": bool(spec.get("temporary", False))},
        )
        print(json.dumps({"username": spec["username"], "id": user_id}))


if __name__ == "__main__":
    main()
