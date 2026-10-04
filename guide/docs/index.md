
# Taimen platform guide

This is the technical and operations guide to Taimen, an environment in which
people, AI agents, automated processes, and services carry out an
organization's work together over a shared Work model. The guide is written for
engineers who deploy the platform, operators who run work in it, and developers
of integrations and executors.

!!! note "How this guide is organized"
    Every article describes the **current behavior of the delivery's code**: APIs,
    variables, ports, commands, and error codes are checked against the component
    sources, `deploy/local/compose.yml`, `.env.example`, `Makefile`, and `deploy/`. Intent and
    rationale (ADRs) are referenced by identifier — `TAI-ADR-…`, `CP-ADR-…`,
    `MEM-ADR-…`, `PC-ADR-…` — but the code remains the source of truth about
    behavior.

## Where to start

| If you… | Read |
|---|---|
| are seeing the platform for the first time | [What is Taimen](overview/what-is-taimen.md) → [Architecture](overview/architecture.md) → [Key concepts](overview/concepts.md) |
| want to run a deployment on your own machine | [Requirements](getting-started/requirements.md) → [Installation and first launch](getting-started/quickstart.md) → [Bootstrap](getting-started/bootstrap.md) |
| are connecting an agent or a harness | [First task](getting-started/first-task.md) → [Harness protocol](control-plane/harness-protocol.md) → [Agents and runner](runner/index.md) |
| are responsible for security | [Security model](overview/security-model.md) → [IAM](iam/index.md) → [Authorization and permissions](control-plane/authorization.md) |
| operate a production deployment | [Operations](operations/index.md) → [Troubleshooting](troubleshooting/index.md) → [Reference](reference/index.md) |

## Section map

<div class="grid cards" markdown>

-   **[Overview](overview/index.md)**

    ---

    What Taimen is, which components it consists of, where the authoritative
    state lives, key concepts, and the security model.

-   **[Getting started](getting-started/index.md)**

    ---

    Requirements, `make secrets / up / bootstrap / smoke`, a walkthrough of
    `.env`, the bootstrap steps, and a first task through the API, CLI, and MCP.

-   **[Control Plane](control-plane/index.md)**

    ---

    The work model: tasks, types and statuses, goals and evidence, claims and
    runs, approvals, artifacts, events, the harness protocol, catalog packages,
    and the API.

-   **[Processes](processes/index.md)**

    ---

    An organization's processes as data: stages, approvals, deadlines on a
    business calendar, compensations, the link to the knowledge base, CEL
    expressions, and package tests without a deployment.

-   **[IAM](iam/index.md)**

    ---

    Tenants and principals, Platform Access Tokens, exchange for audience
    tokens, scopes, service accounts, federation of external identities, and
    Keycloak as the IdP for people.

-   **[Memory](memory/index.md)**

    ---

    A knowledge graph with provenance, namespaces and access, knowledge
    ingestion, search, and context assembly for people and agents.

-   **[Agents and runner](runner/index.md)**

    ---

    Agent identity, the executor daemon, adapters, working copies, and the run
    trace.

-   **[Operator guide](operator/index.md)**

    ---

    The MCP plugin for Claude Code and everyday workflows.

-   **[SDK and integrations](sdk/index.md)**

    ---

    `platform-auth-sdk`, service clients, `skill-sdk`, `platform-llm`, and
    vertical packages.

-   **[Operations](operations/index.md)**

    ---

    Production deployment, perimeter and TLS, upgrades, secrets, backups,
    monitoring, capacity, and emergency procedures.

-   **[Troubleshooting](troubleshooting/index.md)**

    ---

    Common problems with startup, authentication, execution, memory, and human
    sign-in.

-   **[Reference](reference/index.md)**

    ---

    Environment variables, services and ports, permissions and scopes, error
    codes, `make` targets, and the glossary.

</div>

## Three sources of truth

The whole guide rests on one rule: every fact has exactly one authoritative
home.

| What | Where it lives | Section |
|---|---|---|
| Work: tasks, claims, runs, approvals, artifacts, events | **Control Plane** | [Control Plane](control-plane/index.md) |
| Identity: tenants, principals, credentials, tokens | **IAM Service** | [IAM](iam/index.md) |
| Knowledge: observations, facts, documents, provenance | **Memory Service** | [Memory](memory/index.md) |

For details, see [Architecture](overview/architecture.md).

## Conventions

- Run commands from the superproject root (the directory with `deploy/local/compose.yml` and
  `Makefile`) unless stated otherwise.
- Addresses in examples are neutral: the local deployment is
  `http://taimen.localhost`, a production one is `https://platform.example.com`;
  identifiers are `<tenant-id>`, `<principal-id>`, `<workspace-id>`.
- Names of API fields, variables, and entities are given exactly as they are
  written in code (camelCase in JSON, `SNAKE_CASE` in the environment).
- `!!! warning` blocks mark experimental and frozen modules, and places where
  the behavior is easy to misread.

## See also

- [Glossary](reference/glossary.md)
- [Make targets](reference/make.md)
- [Services and ports](reference/services-and-ports.md)
