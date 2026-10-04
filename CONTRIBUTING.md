# Contributing to Taimen

Thank you for taking the time to help. Taimen is developed in the open under the
Apache 2.0 licence; this document describes how to propose a change.

## Before you start

- Read the [README.md](README.md) and the guide `guide/` — they describe the work
  model, the components and their boundaries.
- Before a large change, look through the open issues. If the change affects an API,
  the data model or the boundary between services, open an issue with a proposal
  first: such decisions are discussed before the code.

## Contributor License Agreement (CLA)

Every contribution requires a signed Contributor License Agreement. It grants the
project a copyright and patent licence for your contribution; you keep the copyright.
The agreement lets the project defend the code and, if necessary, relicense it without
tracking down every author.

- For individuals — [cla/CLA-individual.md](cla/CLA-individual.md).
- For companies whose employees contribute on their behalf —
  [cla/CLA-entity.md](cla/CLA-entity.md).

The cla-assistant bot checks the signature on every pull request; you only need to
sign once.

## Development environment

The components are separate repositories attached here as submodules: services in
`services/`, libraries in `sdk/`, the web console in `apps/console`. Python
components use [uv](https://docs.astral.sh/uv/).

```bash
git clone --recurse-submodules https://github.com/taimen-ai/taimen.git && cd taimen
make secrets && make up && make bootstrap && make smoke
make check                  # ruff + tests of all components, as in CI
make check-<component>      # for example make check-control-plane
```

The components depend on their neighbours by path at the same relative paths as in
this repository — a service takes `../../sdk/platform-auth-sdk`, `skill-sdk` takes
`../platform-llm`, `package-sdk` takes `../../services/control-plane` and `../skill-sdk` —
so work from a checkout of this repository or keep the same layout around the component.

## Where to send changes

- Component code — a pull request to the component's repository.
- The assembly (`deploy/local/compose.yml`, `Makefile`, `deploy/`, `tools/`, CI) — a pull request
  here.
- The guide `guide/` is generated from the project's documentation sources: report
  errors and inaccuracies in it as an issue in this repository rather than by editing
  `guide/`.

## Pull requests

- One logical change per pull request; linear history (rebase, no merge commits).
- Tests, `ruff check` and `ruff format --check` pass; a change in behaviour comes with
  tests.
- The commit message explains "why", not "what"; reference the issue.
- A change to a public API (routes, schemas, MCP tools, environment variables) updates
  the component's documentation, and a breaking one is described in the release notes.
- The pull request template asks you to confirm the CLA and the absence of secrets,
  customer data and internal addresses.

## Bugs and vulnerabilities

Report a bug as an issue in the component's repository: version, steps to reproduce,
logs. Report a vulnerability only privately, as described in [SECURITY.md](SECURITY.md),
not in a public issue.

## Code of conduct

The project follows the [code of conduct](CODE_OF_CONDUCT.md).
