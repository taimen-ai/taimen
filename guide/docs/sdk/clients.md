
# Service clients

The platform's canonical Python clients: `control-plane-client` for Control Plane and
`platform-memory-client` for memory-service. The article covers connecting, credential
resolution, PAT-to-access-token exchange, retries and idempotency, error handling, and
typical scenarios. For developers of executors, connectors, demos, and vertical packages.

!!! tip "Do not write your own client"
    The logic of token exchange, retries under the same `Idempotency-Key`, and parsing the
    error envelope already exists in the canonical implementation (TAI-ADR-0030). If
    something is missing, add a method to the client next to the server, not a wrapper "from
    memory of the contract" in your own repository.

## control-plane-client {#control-plane-client}

| | |
|---|---|
| Package | `control_plane_client` (distribution `control-plane-client`) |
| Location | `services/control-plane/client` |
| Dependencies | `httpx` only |
| Protocol | `control-harness/2`; base path `{server}/api/v1` |

```toml
[tool.uv.sources]
control-plane-client = { path = "../control-plane/client", editable = true }
```

### Quick start

```python
from control_plane_client import ControlPlaneClient, IamCredential

credential = IamCredential(
    "https://platform.example.com/iam",   # IAM
    "<iam-tenant-id>",
    audience="control-plane",
    scopes=("control-plane:read", "control-plane:write"),
)

async with ControlPlaneClient("https://platform.example.com", credential,
                              user_agent="acme-connector/0.1") as cp:
    ctx = await cp.get_context()
    task = await cp.create_task(...)       # the Idempotency-Key is generated automatically
```

The second argument of `ControlPlaneClient` is a string (a static API key) or a
`CredentialProvider` (an object with `token()`, `refresh()`, `refreshable`). `user_agent` is
placed before the SDK token: `acme-connector/0.1 control-plane-client/<version>`.

### Credential: where the PAT comes from

Control Plane **does not accept a PAT as a Bearer**: a PAT is presented only to IAM, and the
service receives a short-lived access token for its audience. `IamCredential` performs the
exchange `POST {iam}/api/v1/platform-access-tokens:exchange` with the body
`{token, audience, scopes}`, caches the token, and exchanges again
`refresh_margin_seconds` (30 s by default) before expiry.

PAT lookup order:

| Source | When it is used |
|---|---|
| the `platform_access_token=` argument (a string or a callable) | explicit passing; a callable is read on **every** exchange — file rotation is picked up without a restart; the local store is not read, the tenant can be empty |
| `IAM_PLATFORM_ACCESS_TOKEN` | only together with `IAM_CREDENTIAL_MODE=environment` (or `ci`); without the mode — error `iam_environment_mode_required` |
| macOS Keychain | unless disabled with `IAM_NO_KEYCHAIN=1` |
| the file `~/.config/iam/credentials.json` | `XDG_CONFIG_HOME` is respected |

An entry in the local store is addressed by the triple `issuer|tenant|principal`. If the
machine has several credentials of one tenant (several executors), the process must name
itself with the `IAM_PRINCIPAL` variable; otherwise it gets the refusal
`iam_credential_ambiguous` instead of working under someone else's identity.

A process in a container with the PAT in a file:

```python
from pathlib import Path
from control_plane_client import IamCredential

pat_file = Path("/run/secrets/agent.pat")
credential = IamCredential(
    "http://iam-service:8010", "",
    audience="control-plane",
    scopes=("control-plane:read", "control-plane:write"),
    platform_access_token=lambda: pat_file.read_text(),
)
```

If one process needs two services, use two `IamCredential` objects over one PAT with
different `audience` values (the "one token — one audience" rule).

### Configuration from the environment

`resolve_credential(server_url)` chooses the harness credential: IAM first, then an API key.

| Variable | Meaning |
|---|---|
| `CONTROL_PLANE_IAM_URL` | IAM address; IAM mode is not turned on without it |
| `CONTROL_PLANE_IAM_TENANT` | IAM tenant; a URL without a tenant is a configuration error, not a silent fallback |
| `CONTROL_PLANE_IAM_AUDIENCE` | audience, default `control-plane` |
| `CONTROL_PLANE_IAM_SCOPES` | scopes separated by spaces or commas, for example `"control-plane:read control-plane:write"` |
| `IAM_PRINCIPAL` | which principal this process is, if the machine has several |
| `CONTROL_PLANE_API_KEY` | legacy API key (only if IAM is not configured) |

Quote values with spaces in env files that a shell reads (`source`).

### Commands, retries, and idempotency

| Property | Behavior |
|---|---|
| Creating and action commands (`create_task`, `claim_task`, `start_run`, `succeed_run`, `fail_run`, `create_artifact`, `request_approval`, …) | the client sets an `Idempotency-Key` and retries the request on a **transport** failure (up to 3 attempts in total, pauses of 0.5 s and 1 s) **with the same key** — a retried HTTP request never becomes a second business command |
| Your own key | `idempotency_key=` on `create_task`, `succeed_run`, `fail_run`, `create_artifact`, `request_approval` — for consumers that retry a command based on their own state |
| 401 with a refreshable credential | one re-exchange and one retry with the same key; a second 401 is a real refusal |
| Optimistic locking | `update_task(..., expected_version=)`, `complete_task(..., version=)` send `If-Match: "task-<version>"` |
| Reads | no retries |

### Errors

Control Plane responses arrive in the envelope
`{"error": {"code", "message", "details", "requestId"}}` and are turned into exceptions by
code, and for an unknown code — by status:

| Exception | Codes / status | What to do |
|---|---|---|
| `AuthenticationError` | `invalid_credentials`, 401 | check the PAT and the binding |
| `PermissionDeniedError` | `permission_denied`, 403 | a permission is missing in the binding |
| `NotEligibleError` | `not_eligible` | no role/capability for the task |
| `NotFoundError` | `not_found`, 404 | — |
| `ValidationError` | 422, 428, `unsupported_protocol_version` | fix the request |
| `StaleClaimError` | `stale_claim` | **stop writing**: ownership of the task is lost |
| `ClaimConflictError` | `task_already_claimed`, `task_claimed`, `claim_conflict`, … | the task is taken |
| `VersionConflictError` | `version_conflict` | re-read the task, retry with the new version |
| `IdempotencyConflictError` | `idempotency_key_reused`, `idempotency_in_flight` | the key was used with a different body, or the command is still running |
| `SessionExpiredError` | `session_expired`, `session_not_active` | open a new session |
| `ApprovalRequiredError`, `TaskNotReadyError`, `BudgetExceededError`, `SkillUnavailableError`, `RunNotActiveError`, `CancelledError` | codes of the same name | see [Execution — claims and runs](../control-plane/execution.md) |
| `TransportError` | no response | retry later |
| `IamCredentialError` | `iam_unreachable`, `iam_invalid_token`, `iam_audience_not_allowed`, `iam_exchange_failed`, `iam_not_authenticated`, `iam_credential_ambiguous` | an exchange problem in IAM |

All exceptions inherit from `ControlPlaneError` (`code`, `message`, `status`, `details`).

### Leases: `HeartbeatRunner`

The session and the claim are leases with a TTL. `HeartbeatRunner` renews them in the
background:

```python
from control_plane_client import HeartbeatRunner

runner = HeartbeatRunner(cp, session_id=session["id"], claim_id=claim["id"],
                         interval_seconds=60, max_transport_failures=3)
runner.start()
try:
    # … in the work loop:
    if runner.error is not None:
        ...  # ownership lost — stop authoritative writes
finally:
    await runner.stop()
```

A domain error (the lease expired, ownership lost) is terminal and is stored in `error`; a
transport error is retried on the next tick and becomes terminal only after
`max_transport_failures` in a row.

### Binding a directory to a project

`find_project_config()` searches upward from the current directory for
`.control-plane/config.json` — a non-secret binding of the working copy to a server, tenant,
workspace, project, and repository; `write_project_config()` writes it. The file contains no
secrets, and you can commit it.

### Method groups

| Group | Methods (selection) |
|---|---|
| context and sessions | `get_context`, `open_session`, `heartbeat_session`, `close_session` |
| work | `list_available_work`, `list_tasks`, `get_task`, `get_task_transitions`, `get_claimability` |
| tasks | `create_task`, `update_task`, `complete_task`, `add_task_relation`, `add_task_comment`, `edit_task_comment` |
| goals | `create_goal`, `list_goals`, `get_goal`, `update_goal`, `list_goal_work` |
| claims and runs | `claim_task`, `heartbeat_claim`, `release_claim`, `start_run`, `succeed_run`, `fail_run`, `suspend_run`, `prepare_handoff`, `continue_after_handoff`, `launch_child_run` |
| trace | `create_checkpoint`, `record_action`, `finish_action` |
| artifacts | `create_artifact`, `get_artifact`, `list_artifacts` |
| approvals | `request_approval`, `list_approvals`, `approve`, `reject`, `get_approval_outcome` |
| tools | `search_tools`, `describe_tool` |
| agents | `get_my_agent`, `get_agent`, `list_agents`, `publish_agent`, `list_agent_revisions` |

The full contract is the Control Plane OpenAPI (`/openapi.json`, see
[Control Plane API](../control-plane/api.md)).

## platform-memory-client {#memory-client}

| | |
|---|---|
| Package | `platform_memory_client` (distribution `platform-memory-client`) |
| Location | `services/memory-service/client` |
| Dependencies | `httpx`, `pydantic` (the memory engine is not pulled in) |
| Classes | `MemoryClient` (synchronous), `AsyncMemoryClient` (asyncio) |

!!! note "Who accesses memory directly"
    Executors get the task context through Control Plane (the harness and run context), not
    from memory directly — see [Task context and memory](../control-plane/context.md). Package
    code (processes, rules, skills, observers) also reaches memory only through the core (see
    [Memory only through the core](index.md#memory-through-core)). The memory client is for
    applications with their own grant on a namespace: knowledge ingestion connectors, chat
    bots, consoles.

### Credential

The Bearer is a static key grant on a namespace or an IAM access token for the
`memory-service` audience. The `token` parameter accepts a string or a callable (called
before every request); the asynchronous client also accepts an object with
`async token()`, so `IamCredential` plugs in directly:

```python
from control_plane_client.iam import IamCredential
from platform_memory_client import AsyncMemoryClient

cred = IamCredential(
    "http://iam-service:8010", "",
    audience="memory-service",
    scopes=("memory:read", "memory:write"),
    platform_access_token=lambda: pat,
)
async with AsyncMemoryClient("http://memory-service:8077", token=cred) as mem:
    result = await mem.query("how do I get a visitor pass?", namespaces=["kb"])
```

### Methods

| Method | Path | Purpose |
|---|---|---|
| `healthz()` | `GET /healthz` | liveness and graph statistics |
| `recall(query, budget=, hops=, namespaces=, …)` | `POST /recall` | search with link expansion |
| `search(...)` | `POST /search` | hybrid search |
| `query(question, k=8, hops=1, synthesize=, namespaces=, …)` | `POST /api/brain/query` | answer with sources (optionally LLM synthesis) |
| `retain(content, type=, external_id=, title=, links=, provenance=, run_id=, namespace=)` | `POST /retain` | idempotent write of a fact or a decision |
| `audit(...)` | `POST /audit` | audit of records |
| `retain_document(...)`, `delete_document(key)` | `/api/brain/documents` | upload and delete a document |
| `nodes(...)`, `node(key)`, `source(key)`, `delete_node(key)` | `/api/brain/nodes`, `/api/brain/sources` | graph nodes and sources |
| `observe(...)`, `observe_batch(...)` | `POST /api/memory/observations` | observations |
| `context(request, namespaces=, run_id=, …)` | `POST /api/memory/context` | assemble a bounded ContextPack without synthesis |
| `register_package`, `packages`, `package` | `/api/memory/packages` | domain kind packages (scope `memory:service`) |
| `namespace_kinds`, `set_namespace_kinds` | `/api/memory/namespaces/{ns}/kinds` | namespace kinds |
| `reconcile(...)`, `typed_context(...)` | `/api/memory/reconcile`, `/api/memory/context/typed` | reconciliation and typed context |

The `allowed_namespaces` / `allowed_scopes` parameters of reads narrow visibility: for a
regular caller they are intersected with what the server already allows and never widen it;
an empty list sees nothing. `run_id` is passed in the `X-Run-Id` header for correlation.

### Errors

| Exception | When |
|---|---|
| `MemoryServiceError` | a 4xx/5xx response; fields `status_code`, `detail`; properties `unavailable` (5xx) and `not_found` |
| `MemoryTransportError` | no response (`status_code == 0`) |

Details of the memory contract: [Memory API](../memory/api.md).

## Scenario: a connector that creates tasks

```python
import asyncio
from pathlib import Path
from control_plane_client import ControlPlaneClient, IamCredential, ConflictError

async def main() -> None:
    cred = IamCredential(
        "http://iam-service:8010", "",
        scopes=("control-plane:read", "control-plane:write"),
        platform_access_token=lambda: Path("/run/secrets/connector.pat").read_text(),
    )
    async with ControlPlaneClient("http://control-plane-api:8000", cred,
                                  user_agent="acme-connector/0.1") as cp:
        for item in await fetch_new_items():
            try:
                await cp.create_task(
                    ...,                                 # task fields per OpenAPI
                    idempotency_key=f"acme:{item.id}",   # a retry does not create a duplicate
                )
            except ConflictError:
                continue

asyncio.run(main())
```

The connector principal is of kind `agent` or `service` with an IAM binding in Control Plane
(permissions `tasks.read`, `tasks.write`, and `events.read` if needed); the PAT is in a file
with permissions `0600`.

## See also

- [SDK and integrations](index.md)
- [platform-auth-sdk](platform-auth-sdk.md)
- [Harness protocol](../control-plane/harness-protocol.md)
- [Credentials and PAT](../iam/credentials.md)
- [Memory API](../memory/api.md)
