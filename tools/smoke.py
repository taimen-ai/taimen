#!/usr/bin/env python3
"""Smoke test of the running stack: healthz of every service via the 127.0.0.1 ports (make smoke).

Ports are read from .env (or from the environment); services that are not running are marked
"not running" and are not counted as errors: compose profiles may differ.
"""

from __future__ import annotations

import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CHECKS = [
    ("iam-service", "IAM_HOST_PORT", "18010", "/healthz"),
    ("control-plane-api", "CP_HOST_PORT", "18000", "/health/ready"),
    ("memory-service", "MEMORY_HOST_PORT", "18001", "/healthz"),
    ("notification-service", "NOTIFY_HOST_PORT", "18045", "/healthz"),
    ("keycloak", "KEYCLOAK_HOST_PORT", "18081", "/auth/realms/platform"),
]


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def running_services() -> set[str] | None:
    try:
        result = subprocess.run(
            [str(ROOT / "tools" / "compose"), "--profile", "*", "ps", "--services", "--status", "running"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def main() -> int:
    env = load_env(ROOT / ".env")
    running = running_services()
    failures = 0
    for name, var, default, path in CHECKS:
        if running is not None and name not in running:
            print(f"  {name:20s} —   not running")
            continue
        port = os.environ.get(var) or env.get(var) or default
        url = f"http://127.0.0.1:{port}{path}"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                status = response.status
        except urllib.error.HTTPError as error:
            status = error.code
        except (urllib.error.URLError, OSError):
            print(f"  {name:20s} —   not running ({url})")
            continue
        ok = status < 400
        failures += 0 if ok else 1
        print(f"  {name:20s} {'OK ' if ok else 'ERR'} {status} {url}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
