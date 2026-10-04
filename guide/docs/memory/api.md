
# Memory API

A reference for the memory-service HTTP API: all `/api/brain/*` and
`/api/memory/*` routes, their parameters, responses, and error codes, plus the
MCP server and the client library. It is for integrators. The concepts are in
[Knowledge model](knowledge-model.md), and the access rules are in
[Namespaces and access](namespaces.md).

## General rules

| What | Rule |
|---|---|
| Base address | Inside the compose network, `http://memory-service:8077`; from the host, `http://127.0.0.1:${MEMORY_HOST_PORT:-18001}`. Referred to below as `$MEMORY_URL` |
| Authorization | `Authorization: Bearer <token>` on all routes except `GET /healthz` and the auto-generated docs |
| Format | JSON, UTF-8 |
| Errors | `{"detail": "<description>"}` with an HTTP code |
| End-to-end identifier | The `X-Run-Id` header goes into the record's provenance and into audit |
| Auto-generated docs | `GET /docs` (Swagger UI), `GET /openapi.json` |
| Compatibility | `/api/brain/*` is extended only additively: new fields and routes |

Typical response codes:

| Code | Meaning |
|---|---|
| `200` / `201` / `207` | Success / created / per-element batch result |
| `400` | Invalid data: namespace name, conflicting fields, limits, an invalid `uuid` in the data |
| `401` | Missing or wrong token, defective IAM token |
| `403` | No permission on the namespace, outside the principal's visibility, service scope required |
| `404` | Not found in this namespace |
| `409` | Package version conflict, outdated snapshot |
| `413` | Observation batch too large |
| `422` | Entity kind or relation outside the schema in a strict namespace |
| `500` | Internal error (including an embedding/LLM provider error) or an invalid `CB_API_KEYS` |
| `503` | The database, IAM JWKS, or the external visibility PDP (if enabled) is unavailable |

## Route summary

| Method and path | Access | Purpose |
|---|---|---|
| `GET /healthz` | no authorization | Liveness + graph statistics |
| `GET /api/brain/health` (`/health`) | any token | The same with a token check |
| `POST /api/brain/query` | read | Question → fragments, neighbors, sources, optionally an LLM answer |
| `POST /api/brain/recall` (`/recall`) | read | Context within a budget |
| `POST /api/brain/search` (`/search`) | read | Semantic or structural search |
| `GET /api/brain/nodes` | read | List of nodes with a filter |
| `GET /api/brain/nodes/{natural_key}` | read | A node and its neighbors |
| `GET /api/brain/sources/{natural_key}` | read | Original document and provenance |
| `DELETE /api/brain/nodes/{natural_key}` | write | Delete a node with audit |
| `GET /api/brain/stats` | global grant | Instance statistics |
| `POST /api/brain/retain` (`/retain`) | write | Article or note |
| `POST /api/brain/facts` | write | A node with a key and properties |
| `POST /api/brain/documents` | write | A document as ready-made fragments |
| `DELETE /api/brain/documents/{natural_key}` | write | Delete a document |
| `POST /api/brain/audit` (`/audit`) | write | Audit event |
| `GET /api/brain/trace/{trace_id}` | read | Trace subgraph |
| `POST /api/memory/observations` | write | Accept an observation |
| `POST /api/memory/observations:batch` | write | Batch of observations |
| `GET /api/memory/observations` | read | Recent observations and statuses |
| `GET /api/memory/observations/{id}` | read | Observation by id |
| `DELETE /api/memory/observations/{id}` | write | Redact or purge |
| `POST /api/memory/consolidate` | write | Reprocess observations |
| `POST /api/memory/context` | read | Assemble a ContextPack |
| `GET /api/memory/context/trace/{trace_id}` | read | Compilation trace |
| `POST /api/memory/context/typed` | read | Typed traversal |
| `POST /api/memory/packages` | service scope | Register a domain pack |
| `GET /api/memory/packages` | any token* | List of packages |
| `GET /api/memory/packages/{name}` | any token* | Package version |
| `GET /api/memory/namespaces/{ns}/kinds` | read* | Namespace kind catalog |
| `PUT /api/memory/namespaces/{ns}/kinds` | write* | Strict mode and namespace packages |
| `POST /api/memory/reconcile` | write* | Reconcile a source snapshot |

\* When the core routes restriction is enabled (`CB_CORE_ONLY` /
`CB_CORE_IDENTITIES`), the core identity is additionally required; see
[Namespaces and access](namespaces.md#core-routes).

Routes with a `{natural_key}` path accept keys with slashes (for example,
URLs) without escaping.

## Service routes

### GET /healthz

```bash
curl -fsS "$MEMORY_URL/healthz"
```

```json
{"ok": true, "graph": "company_brain", "nodes": 123, "chunks": 456}
```

`503` means the database is unavailable. `GET /api/brain/health` returns the
same but requires a valid token, which is convenient for checking a client's
configuration.

### GET /api/brain/stats

Nodes and edges by type and the number of fragments across the whole instance:
`{"nodes_by_type": {...}, "edges_by_type": {...}, "chunks": N}`. Available only
to callers without a namespace restriction (a key with a grant on the empty
prefix, or a legacy key); an IAM token gets `403`.

## Read: `/api/brain/*`

### POST /api/brain/query

| Field | Type | Default | Meaning |
|---|---|---|---|
| `question` | string | — | Question |
| `k` | int | 8 | How many fragments to return |
| `hops` | int | 1 | Graph neighbor depth (1–2) |
| `synthesize` | bool | `CB_QUERY_SYNTHESIZE_DEFAULT` | Generate an LLM answer |
| `scope` | object | default namespace | `{"namespace": "…"}` or `{"namespaces": [...]}` |
| `allowedNamespaces`, `allowedScopes` | string[] | — | Visibility narrowing |

Response with `synthesize: false`:

```json
{
  "question": "…", "scope": {"namespace": "support"}, "synthesized": false,
  "hits": [{"chunk_id": 1, "node_key": "…", "source_path": "…", "title": "…",
            "heading": "…", "text": "…", "score": 0.0325, "namespace": "support",
            "meta": {}, "rerank_score": null}],
  "neighbors": [{"natural_key": "…", "type": "…", "title": "…", "source_path": "…"}],
  "sources": [{"source_path": "…", "node_key": "…", "title": "…"}],
  "context": "# Найденные фрагменты…"
}
```

With `synthesize: true`, the response contains `answer` (text) and `sources`,
while `hits` and `neighbors` are the **numbers** of found fragments and
neighbors (there is no `context` field).

### POST /api/brain/recall

| Field | Default | Meaning |
|---|---|---|
| `query` | — | Query |
| `budget` | `mid` | `low` (4), `mid` (8), `high` (16) fragments |
| `hops` | 1 | Neighbor depth |
| `scope`, `allowedNamespaces`, `allowedScopes` | — | As in `query` |

```bash
curl -X POST "$MEMORY_URL/api/brain/recall" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"query": "notification does not arrive", "budget": "low",
       "scope": {"namespace": "support"}}'
```

Response: `query`, `budget`, `scope`, `count`, `memories[]` (`node_key`,
`title`, `heading`, `source_path`, `text`, `namespace`), `sources`,
`neighbors`, `context`.

### POST /api/brain/search

| Field | Meaning |
|---|---|
| `query` | Query (may be empty in structural mode) |
| `filters.type` | Enables structural mode: a list of nodes of this type |
| `filters.status` | Filter by node status (structural mode) |
| `filters.limit` | Result size, 20 by default |
| `filters.meta` | Filter by fragment tags (semantic mode) |
| `scope`, `allowedNamespaces`, `allowedScopes` | As in `query` |

Semantic mode: `{"mode": "semantic", "count", "results": [{node_key, title,
source_path, text, namespace, meta}], "sources"}`. Structural:
`{"mode": "structural", "count", "results": [<nodes>]}`.

### GET /api/brain/nodes

Query parameters: `type`, `status`, `limit` (1–500, 50 by default), `namespace`.
Response: `{"count": N, "nodes": [...]}`.

### GET /api/brain/nodes/{natural_key}

Query parameters: `hops` (1–2), `namespace`. Response:
`{"node": {...}, "neighbors": [...]}`; `404` if the node is not in this
namespace.

### GET /api/brain/sources/{natural_key}

Query parameter: `namespace`. Response `200`:

```json
{
  "natural_key": "…", "namespace": "support", "type": "article", "title": "…",
  "content": "full text, as it was loaded",
  "content_source": "original",
  "chunks": 3,
  "provenance": {"source": "…", "source_path": "…", "origin": "agent",
                 "actor": "kb-import", "actor_id": null, "trace_id": null,
                 "issue_id": null, "confidence": 0.9, "last_seen": "…",
                 "metadata": {}},
  "pii": false, "pii_categories": []
}
```

`content_source: "chunks"` means the node has no original, and the text is
joined from fragments.

### GET /api/brain/trace/{trace_id}

Query parameter: `namespace`. Returns the trace subgraph in the namespace's
audit trail:

```json
{"trace_id": "…", "anchor": "pc-trace:…", "events": [...], "facts": [...],
 "event_count": 2, "fact_count": 1}
```

## Write: `/api/brain/*`

Detailed field behavior is in [Knowledge ingestion](ingestion.md).

### POST /api/brain/retain

Fields: `content` (required), `type` (`note`), `title`, `external_id`,
`provenance`, `links`, `confidence` (0.8), `pii`, `pii_categories`, `scope`.
Response `201`: `{"retained": true, "type", "title", "natural_key",
"namespace", "origin": "agent", "edges", "trace"}` and `pii_categories` if
personal data was detected.

### POST /api/brain/facts

Fields: `natural_key`, `type`, `title` (required), `properties`, `links`,
`run_id`, `confidence` (0.8), `scope`. Response `201`:
`{"natural_key", "namespace", "origin": "agent", "edges", "trace"}`.

### POST /api/brain/documents

Fields: `natural_key`, `title` (required), `type` (`document`), `namespace` or
`scope.namespace`, `source_path`, `properties`, `meta`, `links`, `chunks[]`
(`text`, `heading`, `order`; up to 500), `replace` (`true`), `pii`,
`pii_categories`. Response `201`: `{"natural_key", "namespace", "type",
"chunks", "replaced"}` and `pii_categories` when personal data is detected.
`400` for more than 500 fragments or for different `namespace` and
`scope.namespace`.

### DELETE /api/brain/documents/{natural_key}

Query: `namespace`, `actor` (`api`), `trace_id`. Response `200`:
`{"natural_key", "namespace", "deleted": true|false, "chunks_deleted", "trace_id"}`.
A repeated deletion is not an error (`deleted: false`).

### DELETE /api/brain/nodes/{natural_key}

Query: `namespace`, `actor` (`api`), `trace_id` (otherwise `X-Run-Id`,
otherwise generated). Response `200`: `{"deleted": true, "natural_key", "type",
"title", "chunks_deleted", "trace_id"}`. `404` if there is no node (including
on a repeated call), `400` for an audit trail node.

### POST /api/brain/audit

```json
{"trace_id": "run-42", "action": "answer.sent", "actor": "answer-bot",
 "actor_id": "…", "actor_kind": "agent", "payload": {"ticket": "…"},
 "ts": "2026-09-01T10:00:00Z", "run_id": "…", "scope": {"namespace": "support"}}
```

Response `201`: `{"recorded": true, "natural_key", "namespace", "trace", "action", "ts"}`.

## Personal data {#pii}

Protection is enabled with `CB_PII_PROTECTION=true`. Then:

- **Masked results.** For a caller without clearance, detected personal data
  in all `text`, `context`, `content`, `title`, `answer`, `heading` fields (at
  any depth of the response) is replaced with the masks `[ПДн:phone]`,
  `[ПДн:email]`, `[ПДн:passport_rf]`, `[ПДн:snils]`, `[ПДн:card]`,
  `[ПДн:inn]`, and the response gets `"pii_masked": true`.
- **Clearance.** Full clearance is granted by `CB_SERVER_API_KEYS_PII` keys,
  registry keys with `"pii": true`, and IAM tokens with the `memory:pii` scope.
- **Access log.** Every release of unmasked personal data to a caller with
  clearance is recorded as a `pii_access` event (route and categories) in the
  namespace's audit trail. Pass `X-Run-Id` to link the event to your operation.
- **Labeling on write.** `retain` and `documents` mark the node based on
  automatic detection and the explicit label, and return the resulting
  `pii_categories`.
- **Erasure on request** is the regular `DELETE` with audit.

Masking is done by patterns at output time, so it also works for data that was
not labeled on write. The detector does not recognize full names or addresses.

## Context Memory Engine: `/api/memory/*`

Authorization, grants, visibility, and personal data protection are the same as
for `/api/brain/*`.

### POST /api/memory/observations

The body is an observation (see [Knowledge ingestion](ingestion.md#observations))
plus `scope.namespace`. Response `201`:
`{"observation_id": "obs-…", "duplicate": false, "status": "processed"}`.
`400` for an invalid observation.

### POST /api/memory/observations:batch

```json
{"observations": [{...}, {...}], "scope": {"namespace": "tenant:<tenant-id>"}}
```

Response `207`: `results[]` (each with an `observation_id` or an `error`),
`accepted`, `duplicates`, `failed`. More than `CB_OBSERVATIONS_MAX_BATCH` →
`413`.

### GET /api/memory/observations

Query: `namespace`, `kind`, `status`, `limit` (1–500, 50 by default). Response:
`{"count", "observations": [...], "statuses": {"processed": N, "failed": M, …}}`.

### GET /api/memory/observations/{id}

Query: `namespace`. `404` if not found.

### DELETE /api/memory/observations/{id}

Query: `namespace`, `mode` (`redact` by default | `purge`), `actor` (`api`),
`trace_id`. Response `200`: `{"deleted": true, …}`; `404` if not found.

### POST /api/memory/consolidate

Reprocesses unprocessed observations, idempotently. The body is the write
namespace object (`{"namespace": "support"}`); the query parameter `limit`
(1–5000, 500 by default).

```bash
curl -X POST "$MEMORY_URL/api/memory/consolidate?limit=500" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"namespace": "support"}'
```

### POST /api/memory/context

The body is a `ContextRequest` (`query`, `scopes`, `anchors`, `subject`,
`ephemeral_context`, `budget.tokens` or `max_tokens`, `strategy`, `as_of`, `k`)
plus `scope` and optional `allowedNamespaces`/`allowedScopes`. Fields are also
accepted in camelCase (`ephemeralContext`, `maxTokens`, `asOf`). An unknown
`strategy` → `400`. The response is a `ContextPack`: `query`, `sections[]`,
`sources`, `token_estimate`, `budget`, `conflicts`, `trace_id`, `stats`.
Details are in [Search and context assembly](retrieval.md#context-compiler).

### GET /api/memory/context/trace/{trace_id}

Query: `namespace`. The compilation trace; `404` if not found.

### POST /api/memory/context/typed

Body: `anchors[]` (`{kind?, value}`), `traverse[]` (`relation`, `direction`,
`depth`, `limit`, `from`), `as_of`, `allow_semantic`, `scope`,
`allowedNamespaces`, `allowedScopes`. See [Typed traversal](retrieval.md#typed).
`400` for an unknown package or an invalid request.

## Domain packs and snapshots

### POST /api/memory/packages

Registers a domain pack version. Requires the service scope (a key with
`"service": true`, IAM `memory:service`, a key with a write grant on the empty
prefix, or a legacy key).

```json
{
  "name": "code",
  "version": 1,
  "kinds": [
    {"kind": "component", "naturalKey": "<repo>"},
    {"kind": "source_file", "naturalKey": "<repo>:<path>"},
    {"kind": "endpoint",
     "naturalKey": "<METHOD> <path with parameters as {}>",
     "aliases": ["<path with the original parameter names>"],
     "kindAliases": ["route"],
     "idPatterns": ["\\b(?:GET|POST|PUT|PATCH|DELETE)\\s+/[\\w{}./:-]+"],
     "attributes": {"type": "object", "properties": {"method": {"type": "string"}}}},
    {"kind": "ui_call", "naturalKey": "<repo>:<path>:<line>"}
  ],
  "relations": [
    {"relation": "defined_in", "fromKinds": ["endpoint", "ui_call"], "toKinds": ["source_file"]},
    {"relation": "part_of", "fromKinds": ["source_file"], "toKinds": ["component"]},
    {"relation": "calls", "fromKinds": ["ui_call"], "toKinds": ["endpoint"]}
  ]
}
```

| Code | Meaning |
|---|---|
| `201` | Version created |
| `200` | The same version with the same content already exists |
| `409` | The version is already registered with **different** content (a version is immutable) |
| `400` | The package is invalid |
| `403` | No service scope (or not the core identity when the restriction is on) |

`version` is a string or a number (`1` is stored as `"1"`). `naturalKey` is a
JSON Schema of the key (`type`, `pattern`, `minLength`, `maxLength`, `enum`) or
a template with `<name …>` / `{name}` placeholders. A relation's `cardinality`
is `many` (default) or `one`: with `one`, a change of the object during
reconciliation closes the old fact.

`GET /api/memory/packages` lists packages with their versions;
`GET /api/memory/packages/{name}?version=…` returns a version (the latest by
default), `404` if not found.

### GET/PUT /api/memory/namespaces/{namespace}/kinds

```json
{"strict": true, "packages": ["code@1"]}
```

`packages` lists which packages are in effect in the namespace: `name` means
the latest version, `name@version` a pinned one; `null` means only the
built-in `default`. `PUT` requires write permission on the namespace, `GET`
requires read. Both respond with `{"settings": {...}, "catalog": {...}}`: the
setting and the effective kind catalog.

### POST /api/memory/reconcile {#reconcile}

The body is the snapshot document plus the namespace (the `namespace` field or
`?namespace=`) and optional visibility `scopes`, which are written to all
nodes and relations of the snapshot.

```json
{
  "pack": "code@1",
  "source": "git:web-app",
  "scope": "web-app",
  "snapshotId": "web-app@9ab1c2d",
  "observedAt": "2026-09-23T08:47:12+00:00",
  "entities": [
    {"kind": "ui_call", "key": "web-app:src/runs/page.tsx:38",
     "title": "/runs/${id}/checkpoints (src/runs/page.tsx:38)",
     "attributes": {"queryParams": ["limit"]},
     "provenance": {"repo": "web-app", "sha": "9ab1c2d",
                    "path": "src/runs/page.tsx", "line": 38}}
  ],
  "relations": [
    {"relation": "calls",
     "from": {"kind": "ui_call", "key": "web-app:src/runs/page.tsx:38"},
     "to": {"kind": "endpoint", "key": "GET /api/v1/runs/{}/checkpoints"}}
  ],
  "namespace": "tenant:<tenant-id>:ws:<workspace-id>",
  "scopes": ["workspace:<workspace-id>"]
}
```

!!! note "Two different `scope` fields"
    In a snapshot, `scope` is a **string**, part of the source identity
    (`source` + `scope`). The namespace is passed in a separate `namespace`
    field.

Response:

```json
{"source": "git:web-app", "scope": "web-app", "namespace": "…",
 "snapshot_id": "web-app@9ab1c2d", "observed_at": "2026-09-23T08:47:12Z",
 "pack": "code@1", "opened": 2, "closed": 0, "unchanged": 0, "superseded": 0,
 "entities": {"opened": 1, "closed": 0, "unchanged": 0, "superseded": 0},
 "relations": {"opened": 1, "closed": 0, "unchanged": 0, "superseded": 0,
               "pending": 1, "resolved": 0, "retried": 0},
 "duplicate": false}
```

| Code | Meaning |
|---|---|
| `200` | Reconciliation done (or a repeat with `duplicate: true`) |
| `400` | Invalid snapshot, package not enabled in the namespace, different namespaces in the query and the body |
| `409` | The snapshot is older than the last accepted one for `(source, scope)` |
| `422` | An entity or relation outside the schema in a strict namespace |

An entity key is required, or it is assembled from the kind's `naturalKey`
template. `provenance` `{repo, sha, path, line}` becomes the citation
`repo@sha:path:line`.

## MCP server

`platform-memory-mcp` runs an MCP server on top of the same engine: stdio for
local use, or streamable HTTP with a key check. Tools:

| Tool | Purpose |
|---|---|
| `query_graph` | Graph search |
| `get_node` | Node by key |
| `get_neighbors` | A node's neighbors |
| `get_community` | Nodes of a community (cluster) |
| `shortest_path` | Shortest path between nodes |
| `build_context` | Assemble a ContextPack |
| `remember_observation` | Write an observation |

## Client library

`platform-memory-client` (directory `services/memory-service/client`) is the canonical
HTTP client: `MemoryClient` (sync) and `AsyncMemoryClient` (asyncio) over
`/api/brain/*` and `/api/memory/*`. Its only dependencies are `httpx` and
`pydantic`. The token is passed as a string, a callable, or (in the async
client) an object with `async token()`, so an IAM credential with audience
`memory-service` plugs in directly.

```python
from platform_memory_client import MemoryClient

with MemoryClient("http://memory-service:8077", token=token) as mem:
    res = mem.recall("how do I get a pass?", budget="low", namespaces=["support"])
    for m in res.memories:
        print(m.source_path, m.title)
    for src in res.sources:          # sources are dicts {source_path, node_key, title}
        print(src["source_path"])
    mem.retain_document("doc:guide", "Guide", [{"text": "…", "heading": "Introduction"}],
                        namespace="support")
```

Errors: `MemoryServiceError` (`status_code`, `detail`, properties `unavailable`
for `5xx` and `not_found`) and `MemoryTransportError` when there was no
response. Details are in [SDK clients](../sdk/clients.md).

## See also

- [Namespaces and access](namespaces.md)
- [Knowledge ingestion](ingestion.md)
- [Search and context assembly](retrieval.md)
- [Error codes](../reference/errors.md)
- [Services and ports](../reference/services-and-ports.md)
