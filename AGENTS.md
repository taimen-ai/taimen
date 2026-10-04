# Rules for contributing agents

## Language

The documentation of this repository is in English. The primary language is declared
in `.oss-language`. A Russian counterpart of a document is a `*.ru.md` file next to it
(for example `README.ru.md`); an English document that has such a counterpart must
contain no Cyrillic — `tools/oss_check.py` checks this. Names of APIs, protocols,
entities and components, as well as code identifiers, stay in English in both
languages. Legal texts (`LICENSE`, `cla/`) are not translated.

## Layout

- The components are submodules in three directories: `services/` (`control-plane`,
  `iam-service`, `memory-service`, `notification-service`, `fleet`, `human-harness`),
  `sdk/` (`platform-auth-sdk`, `platform-llm`, `skill-sdk`, `package-sdk`) and
  `apps/console`. The layout is mandatory: the relative path between components is the
  same here, in the images and in the components' CI (a service takes
  `../../sdk/platform-auth-sdk`, `package-sdk` takes `../../services/control-plane`). The
  name of a section in `.gitmodules` is the component's stable name; do not rename
  sections or move submodules.
- Catalog packages (`packages/`, the installation `deploy/packages.yaml`) are checked,
  tested, planned and applied with the package SDK from the `package-sdk` submodule
  (`make packages-check`, `make packages-plan`, `make packages-apply`); this repository
  has no package tools of its own. Packages are written with the Claude Code plugin
  `package-author` of the same submodule: `uv tool install --reinstall
  "./sdk/package-sdk[mcp,sandbox,skills]"`, then `claude plugin marketplace add
  ./sdk/package-sdk` and `claude plugin install package-author@package-sdk` (see the
  README, "Package authoring in Claude Code").
- `deploy/local/compose.yml` (run through `make` or `tools/compose`, never a bare
  `docker compose`), `.env.example`, `Makefile` — building and running the platform.
- `deploy/` — bootstrap (`deploy/bootstrap.py`), the edge (`deploy/caddy/`), the
  Keycloak realm template and Admin API scripts (`deploy/keycloak/`), a fleet node
  (`deploy/node/`) and the agent runner image (`deploy/agent-runner/`).
- `tools/` — build and check scripts, Python standard library only; tests live in
  `tools/tests/`.
- `guide/` — the guide (MkDocs). It is generated from the project's documentation
  sources: do not edit `guide/` by hand, report inaccuracies as an issue.

## Where to make changes

- A change to a component goes to its repository; the submodule pointer here is moved
  in a separate commit after the component is released.
- A file without which an installation cannot be reproduced from git must not live
  only on a server: the runtime configuration belongs here.
- Secrets go only into `.env` and `secrets/` (both in `.gitignore`). Do not commit
  tokens, keys, customer data or internal addresses.

## Checks

```bash
make tools-check      # ruff + tests of tools/
make config-all       # deploy/local/compose.yml for every profile (needs .env: make secrets)
make linkcheck        # relative links in the documentation
make check            # tests of all components (heavy: starts a database for control-plane)
```

Do not use absolute local paths in long-lived documentation: refer to components by
name and to documents by relative links.
