
# Glossary

Taimen platform terms in alphabetical order: first the names of entities and
contracts as they appear in code and the API, then general terms. Each term
has a short definition and a link to the page that covers it. This page is
for all readers of the guide.

## A

**Access token**: a short-lived JWT that IAM issues in exchange for a PAT,
client credentials, or a federated token. It is issued for exactly one
audience; its lifetime is `IAM_TOKEN_TTL_SECONDS` (300 s). It carries the
identity and scopes, but not domain permissions. → [Tokens, audiences, scopes](../iam/tokens.md)

**Acceptance**: the criteria used to check that a goal (Goal) is achieved; a
set of checks with unique keys. →
[Goals, acceptance, and evidence](../control-plane/goals-and-evidence.md)

**Adapter (executor adapter)**: the part of the runner daemon that executes a
run with a specific code agent: `echo`, `claude-code`, `codex`, and
separately OpenCode. → [Executor adapters](../runner/adapters.md)

**Approval**: a request for a human decision (statuses `pending`, `approved`,
`rejected`, `cancelled`). A principal with the `approvals.decide` permission
decides it; this permission is never granted to an agent. → [Approvals](../control-plane/approvals.md)

**Artifact**: a registered result of work on a task: a commit, a document, a
run transcript, and so on. →
[Artifacts and comments](../control-plane/artifacts.md)


**Audience**: the identifier of one resource service in IAM
(`control-plane`, `memory-service`,
`notification-service` …). The audience registry sets the allowed
scopes (`allowedScopes`). → [Permissions and scopes](permissions.md)

**Audit reason**: the exact denial reason (`binding_not_found`,
`credential_revoked`, `issuer_mismatch` …), written only to the audit trail
and the log; the client receives a generalized code. → [Error codes](errors.md)

**Authentication context**: an IAM record of a human's fresh sign-in
(`issuer`, `acr`, `amr`, time). Issuing a PAT to a human requires a context
no older than `IAM_PAT_MAX_AUTHENTICATION_AGE_SECONDS`. → [Credentials and PAT](../iam/credentials.md)

## B

**Binding (IAM principal binding)**: an `iam_principal_bindings` row in
Control Plane: the pair (issuer, IAM principal) → a local principal and its
permissions. Statuses `active`, `disabled`, `revoked`. Without a binding, an
IAM token gives no access to the core. → [Permissions and scopes](permissions.md#iam-principal-bindings)

**Bootstrap**: initial setup: the Control Plane `POST /api/v1/bootstrap`
(tenant, administrator, binding) and the IAM bootstrap endpoints; in the
delivery, `make bootstrap` (`deploy/bootstrap.py`). →
[Bootstrap](../getting-started/bootstrap.md)


**Bootstrap token**: a secret that unlocks the bootstrap endpoints:
`CP_BOOTSTRAP_TOKEN` (header `Authorization: Bearer`),
`IAM_BOOTSTRAP_TOKEN` (header `X-IAM-Bootstrap-Token`).

## C

**Capability**: (1) organizational: a named ability of a principal, used in
task requirements; (2) protocol: what a harness can do (`events.realtime`,
`checkpoints`, `skills.protocol.<p>` …), declared when a session opens. Do
not confuse the two.

**Checkpoint**: a record of the intermediate state of a run (`kind` + data)
from which a new run restores and continues the work. →
[Execution: claims and runs](../control-plane/execution.md)

**Child handle / child run**: delegating part of the work to a child run with
a limited grant (permissions, capabilities, skills no wider than the
parent's); a token of the form `ch1_<id>_<secret>`. → [Execution](../control-plane/execution.md)

**Claim**: an exclusive lease of a task by an executor for a TTL
(`CP_CLAIM_TTL_SECONDS`). While the claim is alive, only its holder, with
`claimId` and `fencingToken`, can write to the task. → [Execution](../control-plane/execution.md)

**Client credentials**: the `clientId` + `clientSecret` of a service account;
exchanged for an access token through `POST /api/v1/tokens/exchange`. →
[Service accounts](../iam/service-accounts.md)

**Context adapter**: the Control Plane `context-adapter` process that
delivers core events to memory (memory-service) with per-tenant isolation.

**ContextPack**: a context package that memory assembles for a task or a run
within a token budget (`CP_CONTEXT_DEFAULT_MAX_TOKENS`). →
[Task context and memory](../control-plane/context.md)

**Control Plane**: the platform core: the Work model (tasks, goals,
workspaces, projects), execution (claims, runs), approvals, artifacts, the
event log, the harness protocol. → [Control Plane](../control-plane/index.md)

**Cursor (event cursor)**: an opaque position in the event log; the client
passes it back unchanged to continue reading. →
[Events](../control-plane/events.md)

## D

**Delegation**: permission for an agent to act on behalf of a specific human
(`delegations.manage`).

**Domain pack**: a set of entity and relation kinds registered in memory as
data; only the core identity registers it (`memory:service`). → [Knowledge model](../memory/knowledge-model.md)

## E

**Edge**: the compose profile with the only external container, `caddy`. →
[Edge and TLS](../operations/edge-and-tls.md)


**Entitlement**: licensing of products and features, quotas, and seats. An
external licensing service performs the check if one is connected (the
entitlement PEP stage). → [platform-auth-sdk](../sdk/platform-auth-sdk.md#entitlement-stage)

**Event journal (event log)**: the ordered stream of Control Plane changes
(`GET /api/v1/events`, WebSocket), the source for adapters and projections. →
[Events](../control-plane/events.md)

**Evidence**: confirmation that an acceptance check passed, referring to the
check key from acceptance. → [Goals, acceptance, and evidence](../control-plane/goals-and-evidence.md)

**Execution workspace (working copy)**: a local git worktree in which the
runner executes a task on the task branch; it can include neighboring
repositories at superproject revisions. → [Working copies](../runner/execution-workspace.md)

**Executor (skill executor)**: a process that executes skill invocations over
the `local`, `http`, `mcp` protocols (permission `skills.execute`); a
transport without permissions of its own.

## F

**Fail closed**: the principle that if a decision (token check, PDP,
entitlement) cannot be obtained, the request is rejected
(`503 …_unavailable`), not let through.


**Federation**: exchanging a token from an external OIDC provider for an IAM
access token: `POST /api/v1/tenants/{t}/federation:exchange`. Humans only. →
[Identity federation](../iam/federation.md)

**Fencing token**: a monotonic claim epoch number. Operations with a stale
token are rejected with `stale_claim`, even if the process considers itself
the owner.


## G

**Gate**: an approval that holds a task (`approval_required`) or allows a
skill with the `external_write` side effect.

**Goal**: a desired state that the tenant wants to make true; a hierarchy of
goals, links to tasks, acceptance, and evidence (permissions `goals.read`,
`goals.write`). → [Goals, acceptance, and evidence](../control-plane/goals-and-evidence.md)

## H


**Handoff**: passing work on: a run publishes a handoff checkpoint, and
another executor or a human picks up the continuation
(`reason=human_harness_handoff`).


**Harness**: the client through which a human or an agent works with Control
Plane: the MCP plugin, the CLI, the runner daemon. It declares its type and
capabilities when a session opens. → [Harness protocol](../control-plane/harness-protocol.md)

**Harness protocol**: the contract for sessions, claims, runs, and cursors
between a harness and the core (`control-harness`, versions `1` and `2`).


## I

**IAM (iam-service)**: the identity service: tenants, principals,
credentials (PAT, service accounts, federation), access token issuance, and
JWKS. It stores no domain permissions. → [IAM](../iam/index.md)

**Idempotency-Key**: a header that makes a repeated write safe: the same key
with the same body returns the stored response; with a different body,
`409 idempotency_key_reused`.

**If-Match / ETag**: optimistic locking: an `ETag` of the form
`"task-<version>"`; on mismatch, `409 version_conflict`; without the header,
`428 if_match_required`.

**Installation (catalog installation)**: a `kind: Installation` file
(`deploy/packages.yaml`) that lists the catalog packages for an environment. →
[Catalog packages](../control-plane/catalog-packages.md)

**Issuer**: the `iss` value of IAM tokens, `${TAIMEN_PUBLIC_URL}/iam`. It is
part of the binding key: changing the public address requires moving the
bindings.

## J

**JWKS**: the IAM public keys (`/.well-known/jwks.json`) that resource
services use to verify token signatures; cached with a staleness bound.

## K


**Knowledge pack**: a version-pinned (`name@version`) package of knowledge,
enabled on a root workspace. → [Knowledge ingestion](../memory/ingestion.md)

## L

**Legacy API key**: a key of the form `cp_<prefix>_<secret>`, the former way
to authenticate to Control Plane. It works only with
`CP_LEGACY_API_KEYS_ENABLED=true`; it is off in the default stack.

**Lifecycle (task type lifecycle)**: the statuses a task type declares, their
categories, and the allowed transitions.

## M

**MCP server (`control-plane-mcp`)**: a Model Context Protocol server that
exposes the Control Plane `cp_*` tools to code agents. →
[CLI and MCP server](../control-plane/cli-and-mcp.md)

**memory-service**: the memory engine: knowledge graph (PostgreSQL + Apache
AGE), vector search (pgvector), observations, ContextPack assembly. →
[Memory](../memory/index.md)

## N

**Namespace**: an isolated knowledge base in memory. A tenant's memory is
`tenant:<tenant_id>` and the subtree `tenant:<tenant_id>:*`. →
[Namespaces and access](../memory/namespaces.md)

## O

**Observation**: a raw fact written to memory (`observations.write`), with a
source and a scope.


**Origin**: where a task in the work graph came from.

**Outbox**: the table of outgoing events that the worker delivers with
retries and exponential backoff (`CP_OUTBOX_*`).

## P

**Package (catalog package)**: a versioned set of catalog objects (task
types, templates, roles, capabilities, skills) in `packages/` that bootstrap
applies to Control Plane. → [Catalog packages](../control-plane/catalog-packages.md)

**PAT (Platform Access Token)**: a long-lived IAM credential of a human or an
agent with a scope ceiling and a list of audiences. It is never presented as
a Bearer itself; it is only exchanged for an access token. →
[Credentials and PAT](../iam/credentials.md)


**PDP / PEP**: Policy Decision Point (the external PDP, which decides) and
Policy Enforcement Point (the resource service, which enforces the decision).
The core mode is `CP_AUTHZ_MODE`.

**Permission**: a flat Control Plane permission string (`tasks.read`,
`tasks.claim`, `admin` …), stored in a binding. → [Permissions and scopes](permissions.md)

**Principal**: a participant: `human`, `agent`, `service` in Control Plane;
`human`, `agent`, `service_account`, `workload` in IAM. → [Tenants and principals](../iam/principals.md)


**Profile (compose profile)**: a group of `deploy/local/compose.yml` services enabled with
the `--profile` flag (`core`, `edge`, `notify` …). →
[Services and ports](services-and-ports.md)

**Project profile**: a project layer over a workspace: template,
configuration by revision, governance, views.

## R

**Reconcile (snapshot reconciliation)**: bringing memory in line with a
source snapshot as a whole; only the core identity performs it.


**Resource service**: a service that verifies tokens issued by others and
decides on domain permissions itself (Control Plane, memory-service,
notification-service).


**Role**: a Control Plane organizational role (grants no permissions). →
[Permissions and scopes](permissions.md#roles)

**Run**: one attempt to execute a task under a claim; statuses `running`,
`succeeded`, `failed`, `cancelled`, `suspended`. It carries actions,
checkpoints, artifacts, and a duration budget.

**Run action**: a recorded action inside a run (for example,
`tool.<name>` for each agent tool call), `started` → finish.

**Run control**: a control message to a live run: `queue`, `steer`,
`redirect`, `request_cancel`, `force_cancel`; the executor acknowledges it.

**Runner**: the host and daemon (`control-plane-agent`) that takes assigned
tasks and executes them with an adapter. → [Agents and runner](../runner/index.md)

## S

**Scope**: a unit of a token's authority ceiling, with the audience prefix
(`control-plane:write`, `memory:read`). It narrows permissions and never
widens them. → [Permissions and scopes](permissions.md)

**Scope ceiling**: the maximum set of scopes that a credential (PAT, service
account) can request during exchange.

**SCIM**: the protocol for provisioning users and groups from an external
directory into IAM (audience `iam-scim`).

**Service account**: a service principal in IAM with client credentials; it
does not get a PAT. → [Service accounts](../iam/service-accounts.md)

**Session (harness session)**: a lease on the harness's presence
(`CP_SESSION_TTL_SECONDS`) within which claims are taken.

**Shadow mode**: `CP_AUTHZ_MODE=shadow`: the local check decides, the PDP is
queried in parallel, and discrepancies are logged.

**Skill**: a versioned unit of execution with a contract (inputs, outputs,
protocol `http`/`local`/`mcp`, side effects, risk, idempotency). →
[skill-sdk](../sdk/skill-sdk.md)

**Skill invocation**: a request to the core to execute a skill version
(`skills.invoke`); an executor takes the invocation on lease.

**Status category**: the only status vocabulary the core relies on:
`backlog`, `active`, `blocked`, `terminal_success`, `terminal_cancelled`. The
task type sets the status keys.
→ [Task types and statuses](../control-plane/task-types.md)

## T

**Task (work item)**: the Control Plane unit of work; the task type defines
statuses, fields, and execution. → [Work model](../control-plane/work-model.md)

**Task relation**: `parent`, `blocks`, `depends_on`, `spawned_by`,
`related_to`; `blocks` and `depends_on` affect readiness
(`task_not_ready`).


**Task type**: a versioned description of a kind of work: lifecycle, field
schema, execution, default acceptance criteria. → [Task types and statuses](../control-plane/task-types.md)

**Tenant**: an isolated organization. In a new installation, IAM and Control
Plane share a single tenant UUID. → [Tenants and principals](../iam/principals.md)

**Transcript (run trace)**: the `transcript` artifact with the feed of the
agent's reasoning and tool calls (without thinking, with paths and
credentials redacted). → [Run trace](../runner/trace.md)

## W

**Work graph**: the graph of work: goals, tasks, relations, origin,
acceptance, and evidence.

**Worker**: the `control-plane-worker` process: outbox, deferred approval
outcomes, background core jobs.

**Workspace**: a node in the hierarchy that organizes work inside a tenant;
it has a type (`allowedChildTypes`) and can carry a project profile.

## General terms

**Agent**: a principal of kind `agent`: an autonomous executor with its own
PAT and a binding without human-only permissions.

**Run budget**: the maximum duration of a run (`maxDurationSeconds`);
exceeding it gives `budget_exceeded`.

**Vertical package**: a domain vertical as a catalog package without its own
runtime: the core runs the work, processes, and rules, and skills perform
actions in the outside world. → [Packages](../packages/index.md)

**Case**: a process instance: data, stages, timers, decision log, and
outcome; in the knowledge base, a `case` node. → [Processes](../processes/index.md)


**Operator**: a human who runs work in Control Plane through the MCP plugin
or the CLI. → [Operator work](../operator/index.md)

**Ceiling**: see *Scope ceiling*.

**Business calendar**: a catalog object of kind `Calendar`: working and
non-working days by year for `cal.*` in expressions.

**Process**: a catalog object of kind `Process`: stages, steps, deadlines,
approvals, and a projection into the knowledge base; the core executes it. →
[Processes](../processes/index.md)

**Superproject**: the top-level repository: components are attached as git
submodules flat in the root, plus `deploy/local/compose.yml`, `.env.example`,
`Makefile`, `deploy/`, `packages/`, `tools/`.

## See also

- [Key concepts](../overview/concepts.md)
- [Architecture](../overview/architecture.md)
- [Permissions and scopes](permissions.md)
- [Error codes](errors.md)
