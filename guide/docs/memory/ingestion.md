
# Knowledge ingestion

This article describes every way to put knowledge into memory (articles,
documents as ready-made fragments, structured facts, observations from
external systems, source snapshots, and loading a document directory), as well
as updating, deleting, and computing embeddings. It is for integrators who
populate the knowledge base.

## Which method to choose

| Method | Route | When to use | Idempotency | Embeddings |
|---|---|---|---|---|
| Article / note | `POST /api/brain/retain` | Raw article text "as is", short notes and agent decisions | `external_id` | One chunk per record |
| Document as fragments | `POST /api/brain/documents` | Knowledge base migration: PDF/DOCX/HTML already split into fragments on your side | `natural_key` + `replace` | Each fragment |
| Structural node | `POST /api/brain/facts` | A node with its own key, type, and properties | `natural_key` | One chunk |
| Observation | `POST /api/memory/observations[:batch]` | Events from external systems (tracker, CRM, email, the core) | `source.system` + `stream` + `external_id` | Only for `text` assertions |
| Source snapshot | `POST /api/memory/reconcile` | The full state of a source (code, registry, tracker) according to a domain pack | `snapshotId` | None |
| Document directory | `cb ingest --vault …` | A Markdown vault with frontmatter, loaded from the administrator's machine | mark-and-sweep | Each fragment |

All write routes require **write** permission on the namespace (see
[Namespaces and access](namespaces.md)) and accept the `X-Run-Id` header, an
end-to-end identifier that goes into provenance and audit.

!!! tip "The main rule"
    Always pass a stable key (`external_id`, `natural_key`, `source.external_id`).
    Then sending again updates the record instead of creating a copy, and a
    deletion on request goes through the same key.

## Article: `POST /api/brain/retain`

The main path for content copied from a page: the text is stored as is, and
the original is kept in the node and returned in the source view.

```bash
curl -X POST "$MEMORY_URL/api/brain/retain" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "content": "How to get a guest pass.\n\nAn employee submits the request...",
    "type": "article",
    "title": "Guest pass",
    "external_id": "https://kb.example.com/articles/guest-pass",
    "provenance": {"source": "kb.example.com", "actor": "kb-import"},
    "confidence": 0.9,
    "scope": {"namespace": "support"}
  }'
```

Response `201`:

```json
{
  "retained": true,
  "type": "article",
  "title": "Guest pass",
  "natural_key": "https://kb.example.com/articles/guest-pass",
  "namespace": "support",
  "origin": "agent",
  "edges": 0,
  "trace": null
}
```

How the fields are processed:

| Field | Default | What happens |
|---|---|---|
| `content` | — | Stored in the node's `props.content` and, in full, in **one** index chunk |
| `type` | `note` | Node type and its graph label |
| `title` | the first non-empty line of `content` (up to 120 characters) | Node and chunk title |
| `external_id` | — | Becomes the node's `natural_key`. Without it, the key is derived from the content: `fact:<sha1[:16]>` or `fact:<trace_id>:<sha1[:16]>` |
| `provenance` | — | Stored as a whole in `props.provenance`; the fields `actor`, `actor_id`, `issue_id`, `trace_id`, `kind`, `source` are copied to the node's properties |
| `provenance.source` | `agent:run/<run_id>` | Becomes the chunk's `source_path`, the citation target |
| `provenance.trace_id` / `issue_id` / `run_id` | `run_id` from `X-Run-Id` | Trace: the node is linked by an `IN_TRACE` edge to the anchor `pc-trace:<trace_id>`; the response has `"trace"` |
| `links` | — | `LINKS_TO` edges to **existing** nodes |
| `confidence` | `0.8` | Stored in the node |
| `pii`, `pii_categories` | — | Explicit personal data labeling (with `CB_PII_PROTECTION=true`) |

!!! warning "Without `external_id`, editing the text creates a new record"
    A key derived from the content changes with the text. An updated article
    without `external_id` ends up next to the old one. Use the article URL or
    an identifier from your system.

!!! note "One article, one fragment"
    `retain` indexes the whole `content` as one chunk (without `heading`). For
    long documents this hurts search precision, and embedding models have an
    input length limit. Split long texts yourself and load them through
    `POST /api/brain/documents`.

## Document as fragments: `POST /api/brain/documents`

For migrating existing knowledge bases: you parse the document on your side
and send ready-made text fragments. In one call, the engine computes
embeddings, creates the document node, and puts the fragments into the index.

```bash
curl -X POST "$MEMORY_URL/api/brain/documents" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "natural_key": "doc:licenses-2026",
    "title": "License register",
    "type": "document",
    "namespace": "support",
    "source_path": "s3://kb/licenses.pdf",
    "meta": {"collection": "licenses"},
    "properties": {"owner": "legal"},
    "chunks": [
      {"text": "Construction license...", "heading": "Section 1", "order": 0},
      {"text": "Design license...", "heading": "Section 2", "order": 1}
    ],
    "replace": true
  }'
```

Response `201`:

```json
{"natural_key": "doc:licenses-2026", "namespace": "support", "type": "document",
 "chunks": 2, "replaced": true}
```

| Field | Default | Meaning |
|---|---|---|
| `natural_key` | — | Document key (idempotency) |
| `title` | — | Title of the node and of all fragments |
| `type` | `document` | Node type |
| `namespace` or `scope.namespace` | default namespace | Knowledge base (if both, they must be identical) |
| `source_path` | `agent:run/<X-Run-Id>` | Citation target in results |
| `meta` | `{}` | Tags, copied to each fragment and to the node's properties; the `filters.meta` filter in `search` |
| `properties` | `{}` | Node properties |
| `links` | — | `LINKS_TO` edges to existing nodes |
| `chunks[]` | `[]` | `{text, heading, order}`; without `order`, the position in the array |
| `replace` | `true` | `true`: first delete all of the node's fragments in this namespace |
| `pii`, `pii_categories` | — | Explicit personal data labeling; automatic detection runs over all fragments |

The limit is **500 fragments per call**. Send a large document in parts:

```mermaid
sequenceDiagram
    participant C as Client
    participant M as memory-service
    C->>M: documents {chunks[0..499], order 0..499, replace: true}
    M-->>C: 201 chunks=500, replaced=true
    C->>M: documents {chunks[500..999], order 500..999, replace: false}
    M-->>C: 201 chunks=500, replaced=false
    Note over C,M: Continuations must have an explicit order;<br/>otherwise order starts at 0 and overwrites the first fragments
```

!!! danger "Explicit `order` in continuations"
    Fragments are unique by `(namespace, node_key, order)`. If you do not pass
    `order` in a continuation, it is taken from the position in the array
    (0, 1, 2…) and **replaces** the fragments of the first part.

## Structural node: `POST /api/brain/facts`

Writes a node with its own key, type, and properties (used by agents):

```json
{
  "natural_key": "decision:cache-ttl",
  "type": "decision",
  "title": "Cache TTL is 5 minutes",
  "properties": {"content": "We decided to keep the cache TTL at 5 minutes.", "status": "accepted"},
  "links": ["component:api-gateway"],
  "run_id": "run-42",
  "confidence": 0.8,
  "scope": {"namespace": "support"}
}
```

The text of the indexed chunk is `properties.content`, or `title` if there is
none. The citation target is `agent:run/<run_id>` (`run_id` from the body or
from `X-Run-Id`).

## Observations: `POST /api/memory/observations` {#observations}

An observation is an immutable piece of evidence from an external system.
Control Plane delivers its domain events to memory this way.

```bash
curl -X POST "$MEMORY_URL/api/memory/observations" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "source": {"system": "issue-tracker", "stream": "events", "external_id": "event-1842"},
    "kind": "work.completed",
    "occurred_at": "2026-08-11T10:00:00Z",
    "actor": {"type": "principal", "id": "alice"},
    "scopes": ["project:alpha"],
    "content": "Regression was fixed",
    "data": {"issue": "PROJ-1842"},
    "provenance": {"uri": "https://tracker.example.com/event/1842"},
    "assertions": [
      {"assert": "fact", "fact": {"subject": "person:alice", "predicate": "WORKS_ON",
        "object": "project:alpha", "valid_from": "2026-08-01T00:00:00Z"}}
    ],
    "scope": {"namespace": "support"}
  }'
# 201 {"observation_id": "obs-…", "duplicate": false, "status": "processed"}
```

Delivering the same `source.system` + `source.stream` + `source.external_id`
again returns the same `observation_id` with `"duplicate": true`. Fields and
limits are in [Knowledge model](knowledge-model.md). Fields are also accepted
in camelCase (`occurredAt`, `externalId`).

### Projection pipeline

```text
POST observation
  ├─ raw record (idempotent, immediate ACK)             — always
  ├─ structured assertions → nodes / facts / chunks     — synchronous, no LLM
  └─ unstructured content → lexical/recent channels     — visible immediately
       └─ LLM extraction                               — only on request (consolidate)
```

Assertions are structured statements that need no LLM:

| `assert` | Content | Result |
|---|---|---|
| `entity` | `{"entity": {"key" or "type"+"id", "title", "properties"}}` | An entity node |
| `fact` | `{"fact": {"subject", "predicate", "object", "valid_from", "valid_to", "supersedes", "confidence"}}` | A temporal fact with `evidence=asserted`; missing endpoints are created as placeholder nodes |
| `text` | `{"text": {"content", "key", "title", "type"}}` | A node with text and an indexed chunk citing `provenance.uri` |

A projection error does not lose the raw record. The status reflects the result:

| Status | Meaning |
|---|---|
| `processed` | Everything was projected |
| `partially_processed` | Some assertions were not projected |
| `failed` | Projection failed |

To see the problematic ones, use `GET /api/memory/observations?namespace=…&status=failed`;
to retry processing, use `POST /api/memory/consolidate` (idempotent).
Embedding of the raw `content` of observations is off by default
(`CB_OBSERVATIONS_EMBED=false`): the lexical and recent channels find them
without vectors, and ingestion does not depend on an external provider.

| What | When search sees it |
|---|---|
| Raw observation (lexical/recent) | Right after ACK |
| Nodes and facts from assertions | Right after ACK |
| Vector of a `text` assertion | After embedding (synchronously if the provider is available, otherwise after consolidate) |
| Knowledge inferred by an LLM | Only after explicit extraction |

### Batch ingestion

`POST /api/memory/observations:batch` accepts
`{"observations": [...], "scope": {"namespace": "…"}}` and responds `207` with
per-element results (`results[]` with an `observation_id` or an `error`) and
the counters `accepted`/`duplicates`/`failed`. An error in one element does
not roll back the others. The maximum is `CB_OBSERVATIONS_MAX_BATCH` (500 by
default); more → `413`.

## Source snapshots: `POST /api/memory/reconcile` {#reconcile}

Reconciliation accepts the **full** state of a source (for example, a
repository's endpoints and files, registry records) in the format of a domain
pack and brings the graph in line with it:

- what is new is opened, what changed is closed and opened as a new version
  (`supersedes`), what disappeared is closed (`valid_to = observedAt`);
- **nothing is deleted**: the past state is available through `as_of`;
- a snapshot of one `(source, scope)` does not close entities of another source;
- a relation to an entity that does not exist yet is kept pending and becomes
  an edge when the target appears;
- repeating the same `(namespace, source, scope, snapshotId)` changes nothing
  and returns `"duplicate": true`; a snapshot older than the last accepted one
  → `409`;
- at most `CB_RECONCILE_MAX_ITEMS` (20000 by default) items in a snapshot.

An example body and response are in [API](api.md#reconcile). In the platform,
clients do not publish snapshots directly but through Control Plane
(`POST /api/v1/knowledge/snapshots`), which computes the workspace namespace
and calls reconciliation with the core service account. When the core routes
restriction is on, only the core identity can call it directly (see
[Namespaces and access](namespaces.md#core-routes)).

## Document directory: `cb ingest`

The CLI projects a directory of Markdown files (vault, read-only) into the
graph and the index:

```bash
cb init-db                          # graph and tables (idempotent)
cb ingest --vault /opt/taimen/kb    # or CB_VAULT_PATH
cb ingest --vault /opt/taimen/kb --reset            # recreate the graph and index
cb ingest --vault /opt/taimen/kb --extract-entities # + entities from text via LLM
cb stats
```

Specifics:

- the vault is projected into the default namespace (`CB_DEFAULT_NAMESPACE`);
- a document's frontmatter sets the node's type and properties, and links
  become edges;
- text is split into fragments by Markdown headings, then by paragraphs with
  a size limit; a fragment's `heading` is the heading "breadcrumbs"
  (`Section > Subsection`);
- ingest cleans up after itself (mark-and-sweep): nodes, edges, and chunks of
  vault origin not encountered in the current run are deleted, **only** in
  this namespace and **only** of vault origin; records written through the API
  are not affected;
- `CB_CACHE_DIR` enables a cache: unchanged notes and already computed
  embeddings are skipped.

!!! warning "`--reset` deletes the graph and index entirely"
    The flag recreates the graph and the chunks table for the whole instance,
    not for one namespace. Make a backup before you use it.

## Embeddings

The service computes embeddings, with a single model and dimension for all
namespaces.

| Parameter | Value |
|---|---|
| Provider | `CB_EMBEDDING_PROVIDER`: `openai` (any OpenAI-compatible endpoint) or `fake` |
| Model | `CB_EMBEDDING_MODEL`, `text-embedding-3-small` by default |
| Dimension | `CB_EMBEDDING_DIM`, `1536` by default; for `text-embedding-3-*` models, passed as the `dimensions` parameter |
| Batch | 64 texts per request to the provider |
| Timeout | `CB_EMBEDDING_TIMEOUT`, 25 s by default |
| Input | `"<title> — <heading>\n<text>"` |

If the provider returns a vector of a different dimension, the write fails with
an error that names both dimensions. Changing the model requires a reindex;
see [Configuration](configuration.md#reindex).

!!! danger "The `fake` provider is not for real data"
    `fake` computes vectors by hashing words at the same dimension, so it
    passes all schema checks, but there is no semantic search: results are
    lexical. The service logs a warning about this. Data indexed this way must
    be reindexed after you enable a real provider.

## Strict kind mode

If strict mode is enabled for a namespace (`PUT /api/memory/namespaces/{ns}/kinds`
with `"strict": true`), writing an entity of an unknown kind, or with a
key/attributes outside the kind's schema, is rejected with `422` on
`/api/brain/facts`, `/api/brain/retain`, `/api/brain/documents`, and
`/api/memory/reconcile`. In observations, such an assertion gets an error
status, while the observation itself is kept. Details are in
[Knowledge model](knowledge-model.md#domain-packs).

## Deletion

| What is deleted | Route | Repeated call | Audit |
|---|---|---|---|
| A node (article, fact) with its edges and chunks | `DELETE /api/brain/nodes/{natural_key}?namespace=…` | `404` | `delete` event |
| A document with its edges and all fragments | `DELETE /api/brain/documents/{natural_key}?namespace=…` | `200 {"deleted": false}` | `delete` event (only on an actual deletion) |
| An observation | `DELETE /api/memory/observations/{id}?namespace=…&mode=redact\|purge` | `404` | deletion event in the audit trail |

```bash
# natural_key may contain slashes; no escaping is needed
curl -X DELETE \
  "$MEMORY_URL/api/brain/nodes/https://kb.example.com/articles/guest-pass?namespace=support&actor=kb-admin" \
  -H "Authorization: Bearer $TOKEN"
```

```json
{"deleted": true, "natural_key": "https://kb.example.com/articles/guest-pass",
 "type": "article", "title": "Guest pass", "chunks_deleted": 1,
 "trace_id": "3f2c…"}
```

- Deletion is **irreversible**: the node is deleted together with its edges
  (`DETACH DELETE`), and its fragments are removed from the index. A snapshot
  of what was deleted (type, title, number of fragments) goes to audit;
  `actor` and `trace_id` (or `X-Run-Id`) are passed as query parameters.
- Audit trail nodes (`audit_event`, `pc_trace`) cannot be deleted → `400`.
- For observations, `redact` wipes the content (the record and id remain),
  and `purge` deletes the row. The observation's chunks are deleted, and the
  evidence is removed from facts; facts with no remaining evidence drop out of
  results.
- Source documents (vault) are not affected.

!!! note "URL keys behind a proxy"
    Some reverse proxies collapse `//` in the path, so `https://x` arrives as
    `https:/x`. The service restores the scheme in route keys by `natural_key`
    automatically.

## Recommendations

- Use the URL or the source system's identifier as `external_id` /
  `natural_key`: this makes loading idempotent and simplifies deletion at the
  request of a data subject.
- Pass `source_path` / `provenance.source` that let the user open the
  original: it is the citation target in all answers.
- Split long documents into fragments by section and pass `heading`: the
  section goes into both the embedding and the results.
- Run bulk loading sequentially: there is no rate limiting at the API level,
  and each call synchronously calls the embedding provider.
- Label full names and addresses explicitly (`"pii": true, "pii_categories": ["fio"]`);
  automatic detection does not recognize them.

## See also

- [Knowledge model](knowledge-model.md)
- [Search and context assembly](retrieval.md)
- [API](api.md)
- [Configuration](configuration.md)
- [Control Plane context](../control-plane/context.md)
