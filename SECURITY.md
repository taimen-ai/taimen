# Security policy

## Supported versions

Taimen is at version 0.x. Security fixes are made on the `main` branch of each
component and ship in the next platform release; there are no long-term support
branches yet.

| Platform version | Supported |
|---|---|
| latest `main` / latest `v0.x` tag | yes |
| older tags | no |

## Reporting a vulnerability

Do not open a public issue about a security problem.

Report privately through GitHub private vulnerability reporting: open the
**Security** tab of the affected repository and choose **Report a vulnerability**. If
that is not available, open an issue containing only the phrase "security: please
contact me", with no details — a maintainer will contact you privately.

In the private report, include:

- the component and version (tag or commit);
- steps to reproduce or a proof of concept;
- the expected impact (what an attacker gains);
- whether the problem is publicly known.

You will receive an acknowledgement within 5 business days, then a status update at
least every 14 days until the fix. We ask for coordinated disclosure: allow up to 90
days for a fix to be released before publishing details. Credit is given in the
release notes unless you prefer to remain anonymous.

## Scope

In scope: the code of the Taimen component repositories and of this repository
(`deploy/local/compose.yml`, `deploy/`, `tools/`), including the MCP plugin and the runner daemon
from `control-plane`.

Out of scope: third-party dependencies (report to their authors; tell us if a fix
requires a coordinated update) and installations operated by third parties.

## Operational recommendations

- Run with IAM authentication only (`CP_LEGACY_API_KEYS_ENABLED=false`, the default).
- Keep the signing key (`secrets/*.pem`) and Platform Access Tokens
  (`secrets/harness-pat`, `secrets/agents/*.pat`, `~/.config/iam/credentials.json`)
  with mode `0600`; do not commit `secrets/` or `.env`.
- Expose only Caddy to the outside; the other services listen on `127.0.0.1` by
  default.
- The IAM administrative surface is not exposed at the edge — see
  `deploy/caddy/Caddyfile.local`.
