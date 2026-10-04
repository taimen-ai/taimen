
# Reference

Summary tables for the whole delivery: environment variables, services and
ports, permissions and scopes, machine error codes, `make` targets, the package
schema and commands, and the glossary. The section is built for keyword search (`Ctrl+K`) and for reading
"by row": every table row is checked against the component code,
`deploy/local/compose.yml`, `.env.example`, `Makefile`, or `deploy/`.

## Where to find what

| Question | Page |
|---|---|
| What the `CP_AUTHZ_MODE` variable means, what its default is, whether it is required | [Environment variables](environment.md) |
| Which port `iam-service` listens on, what `control-plane-api` depends on, what memory limit memory-service has, where Caddy sends `/notify/*` | [Services and ports](services-and-ports.md) |
| Which permission you need to claim a task; what the `control-plane:write` scope grants; which permissions an agent gets after `make bootstrap` | [Permissions and scopes](permissions.md) |
| What `stale_claim`, `scope_not_allowed`, `iam_credential_ambiguous` mean and what to do about them | [Error codes](errors.md) |
| How to bring up the stack with a different set of profiles, run the tests of a single component | [Make targets](make.md) |
| Which fields a task type, an agent, or a process has in a package, what type a kind's key has, what `packages.lock` contains | [Package schema](package-schema.md) |
| Which arguments `package-sdk plan` takes, what `package-sdk edit set` does | [package-sdk commands](package-sdk-cli.md) |
| How a claim differs from a run, and an audience from a scope | [Glossary](glossary.md) |

## Section conventions

- Names of variables, fields, codes, and services are given **exactly as in
  code**: you can copy them into `.env`, requests, and log filters.
- "Default" means the value that applies when the variable is not set. If
  `deploy/local/compose.yml` substitutes its own value, this is stated separately: for the
  stack containers, that value is the one that applies.
- Addresses and identifiers in examples are neutral: `platform.example.com`,
  `<tenant-id>`, `<principal-id>`, `/opt/taimen`.

- Experimental features are described alongside the rest but are marked:
  they are enabled only explicitly.

## See also

- [.env configuration](../getting-started/configuration.md): step-by-step
  environment setup for the first launch.
- [Installation and first launch](../getting-started/quickstart.md).
- [Troubleshooting](../troubleshooting/index.md): problem-solving scenarios
  that use the codes from the [error reference](errors.md).
