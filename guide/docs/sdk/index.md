
# SDK and integrations

This section is for developers who write code on top of the platform: their own resource
service, an executor (agent), a skill, or a package's integration code. It describes the
platform's canonical libraries and the rules for connecting them. All libraries are
Python 3.12+. The package itself, a vertical or an integration, is built with the
`package-sdk` tool; see the [Packages](../packages/index.md) section.

## Libraries

| Library | Python package | Purpose | Dependencies |
|---|---|---|---|
| [platform-auth-sdk](platform-auth-sdk.md) | `platform_auth` | IAM token verification and a Policy Enforcement Point in a resource service: identity → revocation → entitlement → policy → service gates | `pyjwt[crypto]`, `httpx` |
| [control-plane-client](clients.md#control-plane-client) | `control_plane_client` | Control Plane REST API client, credential resolution, PAT-to-access-token exchange | `httpx` |
| [platform-memory-client](clients.md#memory-client) | `platform_memory_client` | memory-service client (`/api/brain/*`, `/api/memory/*`) | `httpx`, `pydantic` |
| [skill-sdk](skill-sdk.md) | `skill_sdk` | write a skill in code, host it over `local`/`http`/`mcp`, and export YAML for a catalog package | `pydantic`, `jsonschema`, `pyyaml`; optionally `platform-auth-sdk`, `platform-llm` |
| [platform-llm](platform-llm.md) | `platform_llm` | a single LLM client with structured output, retries, and model rotation | `httpx`, `pydantic` |
| [package-sdk](../packages/index.md) | `package_sdk` | the package author's tool (`check`, `test`, `lock`, `plan`, `apply`) and the runtime for an integration's observer, `package_sdk.connector` | `pyyaml`, `jsonschema`, `ruamel.yaml`; extras `sandbox`, `connector`, `skills`, `mcp` |

A vertical is a catalog package without its own runtime: the core runs the work, processes,
and rules; skills on `skill-sdk` perform actions in the outside world; an observer on
`package_sdk.connector` writes facts from the outside world. A service of your own with a
database is needed only if the domain has its own data, and then it exposes HTTP skills
(see [Packages](../packages/index.md#vertical)).

## The canonical clients rule

For logic that already has a canonical implementation in the platform, you **do not write**
your own code (Rationale: TAI-ADR-0030):

| Task | Canonical implementation | What not to do |
|---|---|---|
| Verify an IAM token in your service | `platform_auth.TokenVerifier` + `JwksCache` | parse the JWT by hand, accept an audience "by substring" |
| Exchange a PAT or client credentials for an access token | `control_plane_client.IamCredential`, `platform_auth.ServiceTokenProvider` | keep an access token longer than its TTL, send a PAT as a Bearer to a service |
| Call Control Plane | `control_plane_client.ControlPlaneClient` | write your own HTTP client from memory of the contract |
| Read or write memory from a package: a process, rule, skill, observer, or executor | through the core: the process steps `memory`, `recall`, `remember`; the skill's `ctx.knowledge`; the observer's `ctx.snapshot`; the task and run context | access memory-service directly, give the package its own grant on a namespace |
| Read or write memory from an application with its own grant on a namespace | `platform_memory_client` | access the memory database directly |
| Call an LLM | `platform_llm.OpenAICompatibleClient` | copy retries and JSON parsing into every service |

The clients live next to the server in its repository (`services/control-plane/client`,
`services/memory-service/client`) and are versioned together with the server contract.

### Memory only through the core { #memory-through-core }

Package code (a process, rule, skill, observer, or task executor) does not call
memory-service. All its memory requests go to Control Plane, and the core itself calls
memory on its own behalf, checking the caller's permissions on the workspace and the enabled
ontologies (TAI-ADR-0054):

| Who | How it reads and writes memory |
|---|---|
| process | the case projection `memory`, the `recall` and `remember` steps, step context ([Processes and the knowledge base](../processes/knowledge.md)) |
| skill | `ctx.knowledge`: `recall`, `query`, snapshot `preview` and `apply`, `document` ([skill-sdk](skill-sdk.md#core-access)) |
| observer | `ctx.snapshot`, a snapshot of the external system ([Integrations](../packages/integrations.md#observer)) |
| task executor | the task and run context ([Task context and memory](../control-plane/context.md)) |

The direct memory client `platform_memory_client` is for applications with their own grant
on a namespace, not for packages (see [Service clients](clients.md#memory-client)).

## Connecting {#connect}

Libraries are connected as **path dependencies in neighbouring folders**. The superproject
layout is flat: components sit next to each other at the root, and a consumer refers to
`../platform-auth-sdk`, `../control-plane/client`, and so on.

=== "uv (`tool.uv.sources`)"

    ```toml
    [project]
    dependencies = [
        "platform-auth-sdk>=0.1.0",
        "control-plane-client",
        "platform-memory-client",
    ]

    [tool.uv.sources]
    platform-auth-sdk = { path = "../platform-auth-sdk", editable = true }
    control-plane-client = { path = "../control-plane/client", editable = true }
    platform-memory-client = { path = "../memory-service/client", editable = true }
    ```

=== "PEP 508 with `{root:uri}` (hatch)"

    ```toml
    [project]
    dependencies = [
        "platform-auth-sdk @ {root:uri}/../platform-auth-sdk",
        "control-plane-client @ {root:uri}/../control-plane/client",
        "platform-llm @ {root:uri}/../platform-llm",
    ]
    ```

!!! warning "The image build context is the superproject root"
    Because of path dependencies, a service image cannot be built from its own directory:

    the neighbours are not there. Platform services that depend on the SDK (control-plane,
    package services)
    are built with the context `.` (the root) and `dockerfile: <component>/Dockerfile`; the
    `.dockerignore` at the root cuts off everything extra. Do the same for your service:

    ```yaml
    my-service:
      build:
        context: .
        dockerfile: my-service/Dockerfile
    ```

    The runner host that executes agents in working copies materializes the neighbours
    under the same names — that is why the layout must not change.

## Tokens: who presents what


```mermaid
flowchart LR
    subgraph Executor
      PAT[Platform Access Token] ==>|"IamCredential"| X1[POST /iam/api/v1/platform-access-tokens:exchange]
    end
    subgraph Service
      CC[client_id + client_secret] ==>|"ServiceTokenProvider"| X2[POST /iam/api/v1/tokens/exchange]
    end
    X1 ==> AT1[access token audience control-plane]
    X2 ==> AT2[access token audience memory-service / …]
    AT1 ==> CP[Control Plane]
    AT2 ==> RS[Resource service]
    RS ==>|"TokenVerifier (platform-auth-sdk)"| V[verification]
    CP ==>|"TokenVerifier"| V
```


| Who | Credential | How it gets an access token | Library |
|---|---|---|---|
| Agent, harness, CLI | PAT (from a local store, a file, or a variable) | PAT exchange → a token for one audience | `control_plane_client.IamCredential` |
| Platform service | service account client credentials | client credentials exchange → a token for an audience | `platform_auth.ServiceTokenProvider` |
| Human in a browser | login to an external OIDC IdP | `federation:exchange` in IAM (web client) | — (see [Identity federation](../iam/federation.md)) |

The rule is **"one token — one audience"**: a resource service accepts only a token issued
exactly for it. If a process needs two services, it performs two exchanges of the same PAT
(see [Tokens, audiences, scopes](../iam/tokens.md)).

## Checks and tests

| Library | Check |
|---|---|
| platform-auth-sdk | `uv run pytest`, `uv run ruff check .`, `uv run mypy` |
| skill-sdk | `uv run pytest -q` |
| platform-llm | `uv run pytest -q`, `uv run ruff check . && uv run ruff format --check .` |
| clients | client tests run together with the service tests |

`platform_auth.testing` provides a key generator, token issuance with arbitrary claims, and a
controllable clock — use it in your service's tests instead of hand-written fixtures.

## See also

- [platform-auth-sdk](platform-auth-sdk.md)
- [Service clients](clients.md)
- [skill-sdk](skill-sdk.md)
- [platform-llm](platform-llm.md)
- [Packages](../packages/index.md): a vertical as a package, the `package-sdk` tool
- [Tokens, audiences, scopes](../iam/tokens.md)
