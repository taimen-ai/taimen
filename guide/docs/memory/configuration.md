
# Configuration and operations

A reference for memory-service environment variables (`CB_*`), how they relate
to the variables in the platform's root `.env`, how to configure embedding and
LLM providers, and operations: backup, reindexing,
performance, and common problems. It is for administrators.

## How settings are specified

The service reads environment variables with the `CB_` prefix (and the `.env`
file in the process's working directory, if there is one). The full list is in
`src/platform_memory/core/config.py` in the memory-service repository. As part
of the platform, the values are set by the `memory-service` block of the `deploy/local/compose.yml`, some of them through variables of the root `.env`:

| `.env` variable | Default | What it becomes |
|---|---|---|
| `MEMORY_POSTGRES_PASSWORD` | — (required) | Password of `memory-db`, part of `CB_DATABASE_URL` |
| `MEMORY_API_KEY` | — (required) | `CB_SERVER_API_KEY`; the core also uses it to call memory before bootstrap |
| `MEMORY_EMBEDDING_PROVIDER` | `fake` | `CB_EMBEDDING_PROVIDER` |
| `MEMORY_EMBEDDING_MODEL` | `text-embedding-3-small` | `CB_EMBEDDING_MODEL` |
| `MEMORY_LLM_PROVIDER` | `echo` | `CB_LLM_PROVIDER` |
| `LLM_BASE_URL` | see `.env.example` | `CB_EMBEDDING_BASE_URL` and `CB_LLM_BASE_URL` |
| `LLM_API_KEY` | — | `CB_EMBEDDING_API_KEY` and `CB_LLM_API_KEY` |
| `LLM_MODEL` | see `.env.example` | `CB_LLM_MODEL` |
| `MEMORY_RERANK_ENABLED` | `false` | `CB_RERANK_ENABLED` |
| `MEMORY_CONSOLE_ENABLED` | `false` | `CB_CONSOLE_ENABLED` |
| `MEMORY_IAM_ENABLED` | `true` | `CB_IAM_ENABLED` |
| `MEMORY_POLICY_ENABLED` | `false` | `CB_POLICY_ENABLED` |
| `TAIMEN_PUBLIC_URL` | — | `CB_IAM_ISSUER` = `${TAIMEN_PUBLIC_URL}/iam` |
| `MEMORY_HOST_PORT` | `18001` | Port on the host's `127.0.0.1` |
| `MEMORY_MEM_LIMIT` / `MEMORY_DB_MEM_LIMIT` | `512m` / `512m` | Container memory limits |
| `VOLUME_MEMORY_DB` | `<project>_memory_db` | Name of the database volume |


Hard-coded in `deploy/local/compose.yml`: `CB_PII_PROTECTION=true`, an empty
`CB_SERVER_API_KEYS_PII`, `CB_DEFAULT_NAMESPACE=main`, `CB_EMBEDDING_DIM=1536`,
`CB_EMBEDDING_TIMEOUT=60`, `CB_RERANK_POOL=20`,
`CB_IAM_JWKS_URL=http://iam-service:8010/.well-known/jwks.json`,
`CB_IAM_AUDIENCE=memory-service`,
`CB_IAM_BASE_URL=http://iam-service:8010`. The file
`secrets/memory-service-iam.env` (optional: memory's service identity for calling
an external PDP; you add it together with the PDP) adds `CB_IAM_CLIENT_ID` and
`CB_IAM_CLIENT_SECRET`.

!!! warning "Offline providers by default"
    Without a provider key, the platform runs memory on `fake`/`echo`:
    everything works, but search is lexical, and there is no synthesis or
    reranking. For real data, enable a real provider **before** loading
    knowledge; otherwise you will need a reindex.

## `CB_*` variable reference

### Database and storage

| Variable | Default | Meaning |
|---|---|---|
| `CB_DATABASE_URL` | assembled from `POSTGRES_USER/PASSWORD/HOST/PORT/DB` (`brain`/`brain`/`localhost`/`5432`/`company_brain`) | Connection string for PostgreSQL with pgvector (`pg_trgm` recommended) |
| `CB_GRAPH_NAME` | `company_brain` | PostgreSQL schema with the graph tables (`graph_nodes`, `graph_edges`) |
| `CB_CHUNKS_TABLE` | `chunks` | Fragments table |
| `CB_DB_JIT` | `false` | PostgreSQL JIT for the service's connections (see [Performance](#performance)) |
| `CB_DEFAULT_NAMESPACE` | `nexus` | Namespace for requests without `scope`; set it explicitly |
| `CB_OBSERVATIONS_TABLE` | `observations` | Observations table |
| `CB_CONTEXT_TRACES_TABLE` | `context_traces` | Compilation traces table |
| `CB_DOMAIN_PACKS_TABLE` | `domain_packs` | Domain pack registry |
| `CB_NAMESPACE_SETTINGS_TABLE` | `namespace_settings` | Namespace kind settings |
| `CB_SNAPSHOTS_TABLE` | `source_snapshots` | Snapshot journal (+ `<name>_items`) |

### HTTP service and authentication

| Variable | Default | Meaning |
|---|---|---|
| `CB_SERVER_HOST` | `127.0.0.1` (`0.0.0.0` in the image) | Listen address |
| `CB_SERVER_PORT` | `8077` | Port |
| `CB_SERVER_API_KEY` | — | Static key: all namespaces; masked output when personal data protection is on |
| `CB_SERVER_API_KEYS_PII` | — | Keys with full personal data clearance, comma-separated |
| `CB_API_KEYS` | — | JSON registry of keys with grants (see [Namespaces and access](namespaces.md)) |
| `CB_IAM_ENABLED` | `false` | Accept IAM access tokens |
| `CB_IAM_ISSUER` | — | Exact `iss` of the token |
| `CB_IAM_JWKS_URL` | — | IAM JWKS (internal address) |
| `CB_IAM_AUDIENCE` | `memory-service` | Exact `aud` |
| `CB_IAM_LEEWAY_SECONDS` | `5` | Clock skew tolerance |
| `CB_CORE_ONLY` | `false` | Close core routes to everyone except the core identity |
| `CB_CORE_IDENTITIES` | — | Core identity labels, comma-separated; a non-empty list also enables the restriction |

### Principal-based visibility (experimental)


| Variable | Default | Meaning |
|---|---|---|
| `CB_POLICY_ENABLED` | `false` | Take the visibility of people and agents from the external PDP |
| `CB_POLICY_URL` | `http://localhost:8030` | PDP address |
| `CB_POLICY_TIMEOUT_SECONDS` | `3.0` | Call timeout |
| `CB_POLICY_CACHE_TTL_SECONDS` | `5.0` | Per-principal response cache |
| `CB_IAM_BASE_URL`, `CB_IAM_CLIENT_ID`, `CB_IAM_CLIENT_SECRET` | — | Memory's service identity in IAM (client credentials) |

### Embeddings

| Variable | Default | Meaning |
|---|---|---|
| `CB_EMBEDDING_PROVIDER` | `openai` | `openai` (any OpenAI-compatible endpoint) or `fake` |
| `CB_EMBEDDING_BASE_URL` | a public OpenAI-compatible gateway (see `config.py`) | Base URL of the endpoint; set it explicitly in an installation |
| `CB_EMBEDDING_API_KEY` | — | Required for `openai` |
| `CB_EMBEDDING_MODEL` | `text-embedding-3-small` | Model |
| `CB_EMBEDDING_DIM` | `1536` | Dimension; must match the model |
| `CB_EMBEDDING_TIMEOUT` | `25.0` | Call timeout, seconds |

### LLM, synthesis, and reranking

| Variable | Default | Meaning |
|---|---|---|
| `CB_LLM_PROVIDER` | `openai` | `openai` or `echo` (no generation) |
| `CB_LLM_BASE_URL` | same as for embeddings | Base URL for chat completions |
| `CB_LLM_API_KEY` | — | Required for `openai` |
| `CB_LLM_MODEL` | `gpt-4o-mini` | Synthesis model (and the rerank model by default) |
| `CB_QUERY_SYNTHESIZE_DEFAULT` | `false` | The `synthesize` value if the client did not pass it |
| `CB_RERANK_ENABLED` | `false` | Reranking in `query`/`recall`/`search` |
| `CB_RERANK_PROVIDER` | `llm` | Rerank provider |
| `CB_RERANK_POOL` | `20` | Size of the rerank candidate pool |
| `CB_RERANK_MODEL` | — (= `CB_LLM_MODEL`) | A separate rerank model |
| `CB_EXTRACT_ENTITIES` | `false` | Extract entities from vault text through an LLM during `cb ingest` |

### Context Compiler and observations

| Variable | Default | Meaning |
|---|---|---|
| `CB_CONTEXT_DEFAULT_MAX_TOKENS` | `8000` | Default ContextPack budget |
| `CB_CONTEXT_CHARS_PER_TOKEN` | `3.0` | Size estimate (conservative for Cyrillic; 4.0 is fine for English) |
| `CB_CONTEXT_MAX_DEPTH` | `2` | Graph traversal depth |
| `CB_CONTEXT_MAX_NODES` | `60` | Maximum traversal nodes |
| `CB_CONTEXT_MAX_EDGES` | `120` | Maximum traversal edges |
| `CB_OBSERVATIONS_EMBED` | `false` | Embed the `content` of observations |
| `CB_OBSERVATIONS_MAX_BATCH` | `500` | Maximum observations per batch |
| `CB_RECONCILE_MAX_ITEMS` | `20000` | Maximum items per snapshot |
| `CB_RUN_AUDIT_ENABLED` | `true` | Run lifecycle events in the trace |

### Personal data protection

| Variable | Default | Meaning |
|---|---|---|
| `CB_PII_PROTECTION` | `false` (`true` in the platform) | Masking, labeling, and the personal data access log |

### Vault loading (CLI)

| Variable | Default | Meaning |
|---|---|---|
| `CB_VAULT_PATH` | — | Document directory for `cb ingest` |
| `CB_CACHE_DIR` | — | Cache of unchanged notes and embeddings; empty means off |
| `CB_PROJECT_VALUES` | — | Allowed project slugs (synthetic `project:*` nodes), comma-separated |

### Console and demo showcase {#console-demo}

| Variable | Default | Meaning |
|---|---|---|
| `CB_CONSOLE_ENABLED` | `false` | Administrative console `/console`; when off, all its routes return `404` |
| `CB_CONSOLE_NAMESPACES` | — | Comma-separated list of the console's knowledge bases (empty means only the default namespace) |
| `CB_DEMO_PUBLIC_ENABLED` | `false` | Public read-only showcase `/demo` |
| `CB_DEMO_NAMESPACE` | `demo` | The showcase's only knowledge base |
| `CB_DEMO_RATE_LIMIT` | `30` | Requests per minute from one IP to `/demo/api/*` (`0` means no limit) |
| `CB_DEMO_SEARCH_K`, `CB_DEMO_RERANK`, `CB_DEMO_MIN_CONFIDENCE` | `5`, `true`, `0.3` | Showcase search: top-k, its own rerank, `rerank_score` threshold |
| `CB_DEMO_BRAND_NAME`, `CB_DEMO_BRAND_TAGLINE`, `CB_DEMO_CTA_URL`, `CB_DEMO_DOMAIN` | neutral | Showcase branding |

!!! danger "The console has no authentication of its own"
    `/console` calls the engine in-process and does not check the user. Enable
    it only behind a reverse proxy that authenticates the administrator, or do
    not publish it at all and access it through an SSH tunnel. Do not enable
    the `/demo` showcase on an installation with real data: it is intended for
    a clean synthetic database.

## Embedding and LLM providers

The service uses an OpenAI-compatible API through the official `openai`
client: `embeddings.create` for embeddings and `chat.completions.create` for
synthesis and reranking. Any endpoint with this protocol works (a cloud
gateway, a local model server).

=== "Production mode"

    ```bash
    CB_EMBEDDING_PROVIDER=openai
    CB_EMBEDDING_BASE_URL=https://llm-gateway.example.com/v1
    CB_EMBEDDING_API_KEY=<key>
    CB_EMBEDDING_MODEL=text-embedding-3-small
    CB_EMBEDDING_DIM=1536
    CB_EMBEDDING_TIMEOUT=60

    CB_LLM_PROVIDER=openai
    CB_LLM_BASE_URL=https://llm-gateway.example.com/v1
    CB_LLM_API_KEY=<key>
    CB_LLM_MODEL=<fast model>
    CB_RERANK_ENABLED=true
    ```

=== "Offline (tests, development)"

    ```bash
    CB_EMBEDDING_PROVIDER=fake
    CB_LLM_PROVIDER=echo
    CB_RERANK_ENABLED=false
    ```

=== "In the platform's root .env"

    ```bash
    LLM_API_KEY=<key>
    LLM_BASE_URL=https://llm-gateway.example.com/v1
    LLM_MODEL=<fast model>
    MEMORY_EMBEDDING_PROVIDER=openai
    MEMORY_LLM_PROVIDER=openai
    MEMORY_RERANK_ENABLED=true
    ```

Selection guidelines:

- **Embeddings** must support Russian. The `CB_EMBEDDING_DIM` dimension must
  match the model's dimension; for models of the `text-embedding-3-*` family,
  the service passes `dimensions` and may get a shortened vector.
- **Increase the embedding timeout** if the provider has occasional latency
  spikes (60 s in the platform). Embedding is the first step of every search:
  without a timeout, a hung provider holds the handler.
- **Choose the synthesis and rerank model** by latency: rerank is one call per
  search with a 12 s timeout, synthesis has a 25 s timeout. Reranking requires
  the model to return JSON reliably; with an incomplete response, search
  silently falls back to the RRF order.
- Set a separate rerank model with `CB_RERANK_MODEL`.

## Operations

### Resources and placement

- The service is stateless; all state is in `memory-db`. The port is not
  published externally: in `deploy/local/compose.yml` it is bound to `127.0.0.1`, and the
  platform calls memory at the internal address.
- The schema (graph, tables, indexes) is created and completed idempotently
  when the service starts; migrations are additive and need no separate steps
  during an upgrade, except a one-time move of the graph from Apache AGE
  (below).
- The memory graph is ordinary PostgreSQL tables `graph_nodes` and
  `graph_edges` in the `CB_GRAPH_NAME` schema (MEM-ADR-023), vectors are
  pgvector, text search is `pg_trgm`. Of the extensions only `vector` is
  required and `pg_trgm` is recommended: without the right to
  `CREATE EXTENSION pg_trgm`, identifier search uses a sequential `ILIKE`,
  which is correct but slower. The service needs no graph extension and no
  superuser, so any PostgreSQL 16 with pgvector will do.
- The `memory-db` image in the distribution is still based on the official
  Apache AGE image for PostgreSQL 16, with pgvector built from source; when the
  volume is first created, the init script installs the extensions `age`,
  `vector`, `pg_trgm`. The service does not use the AGE extension; it remains
  only for moving the graph from older installations.

#### Moving from Apache AGE {#age-migration}

Before memory-service v0.2.1, the graph was stored in Apache AGE. The new
version neither reads nor touches AGE data: on an installation with an old
graph, the graph looks empty after the upgrade until it is moved with
`cb migrate-graph-from-age`. Run the move while the AGE extension is still
installed in the database and with the service **stopped**:

```bash
tools/compose stop memory-service
tools/compose run --rm memory-service cb migrate-graph-from-age --dry-run   # reconciliation without writing
tools/compose run --rm memory-service cb migrate-graph-from-age             # move
tools/compose up -d memory-service
```

The command is idempotent and at the end reconciles the node and edge counts
for each namespace; a mismatch or a skipped record means exit code 1 and a
report. Once the service has started, **do not** run the move again (only
`--dry-run`): the service has already deleted nodes that remain in AGE, and a
repeat would bring the deleted data back, including purged personal data. For
details, see the memory-service README and MEM-ADR-023.

### Performance {#performance}

| Setting / specific | Why it matters |
|---|---|
| `CB_DB_JIT=false` (default) | A legacy of the Apache AGE graph: its inflated cardinality estimates made PostgreSQL JIT recompile every graph query (MEM-ADR-010). On the graph tables, the MEM-ADR-023 benchmark shows JIT does not kick in; the setting is kept for now. The service opens sessions with `-c jit=off`; an explicitly set `options` in `CB_DATABASE_URL` is not overwritten |
| One connection per request | There is no connection pool: each HTTP request opens its own connection. For an external pooler that does not support `options`, set the session parameters in the connection string itself |
| Indexes | HNSW on embeddings, GIN on the full-text document, GIN on `meta`, trigrams on text, B-tree and GIN indexes on the graph tables (`graph_nodes`, `graph_edges`) |
| Provider timeouts | Embedding `CB_EMBEDDING_TIMEOUT`, rerank 12 s, synthesis 25 s: a hung provider does not hold a request forever |
| Rerank and synthesis | Each adds an LLM call to the request latency |
| Rate limiting | None at the API level (except the `/demo` showcase); run bulk loading sequentially |

For measurements, the memory-service repository has `benchmarks/bench.py`
(loading speed and search channel latencies on synthetic datasets); it runs
against a separate throwaway database.

### Backup and restore

All of memory is in the single `memory-db` database, so a backup is a
`pg_dump`:

```bash
tools/compose exec -T memory-db \
  pg_dump -U memory -d company_brain -Fc > memory-$(date +%Y%m%d-%H%M).dump
```

Restore onto a fresh volume where the init script has already created the
extensions:

```bash
tools/compose stop memory-service
tools/compose exec -T memory-db \
  pg_restore -U memory -d company_brain --clean --if-exists < memory-XXXX.dump
```

The graph is stored in ordinary tables (`graph_nodes`, `graph_edges` in the
`CB_GRAPH_NAME` schema), so a dump moves to another cluster without manual
catalog fixes. A dump of an installation whose graph is still in Apache AGE is
restored the same way, and the graph is moved after the restore; see [Moving
from Apache AGE](#age-migration).

Then start the service and check:

```bash
tools/compose start memory-service
curl -fsS http://127.0.0.1:18001/healthz        # nodes and chunks > 0
curl -fsS -X POST http://127.0.0.1:18001/api/brain/recall \
  -H "Authorization: Bearer $MEMORY_API_KEY" -H "Content-Type: application/json" \
  -d '{"query": "control question", "budget": "low", "scope": {"namespace": "<ns>"}}'
```

!!! warning "Dumps contain customer data, including personal data"
    Keep them inside the installation's perimeter according to its policy and
    do not take them outside. General platform backup rules are in
    [Backup](../operations/backup.md).

### Changing the embedding model and reindexing {#reindex}

Vectors from different models are incompatible, and the dimension of the
`embedding` column is fixed when the table is created. The service protects
against mixing:

- if the table was created with a different dimension, writes and searches
  fail with an error that names both dimensions;
- if the provider returns a vector of the wrong dimension, the write is
  rejected.

There is no built-in "recompute embeddings" command for data loaded through
the API. The model change procedure:

1. Back up the database.
2. Stop writes to memory (integrations, `context-adapter`).
3. Change `CB_EMBEDDING_MODEL` and, if needed, `CB_EMBEDDING_DIM`.
4. If the dimension changed, drop the fragments table (the service recreates
   it on startup). This **deletes all fragments of all namespaces**:
   ```sql
   DROP TABLE public.chunks;
   ```
5. Restart the service and load the knowledge again from the sources:
   `retain` and `documents` are idempotent by key and replace the fragments;
   for the vault, `cb ingest --vault …` (the `--reset` flag recreates both the
   graph and the index entirely).
6. If the dimension did not change but the model did, the old fragments are
   formally valid, but their vectors are not comparable with the new ones;
   reload all documents the same way.

The same applies to data loaded with `CB_EMBEDDING_PROVIDER=fake`.

### Upgrade

```bash
tools/compose build memory-service
tools/compose up -d memory-service
curl -fsS http://127.0.0.1:18001/healthz
```

New tables and indexes are created on startup. The general platform upgrade
procedure is in [Upgrades](../operations/upgrades.md).

### Monitoring and diagnostics

| What to look at | How |
|---|---|
| Liveness and database availability | `GET /healthz` (no token); `503` means the database is unavailable; the container healthcheck calls `127.0.0.1:8077/healthz` |
| Validity of a client's token | `GET /api/brain/health` |
| Observation projection | `GET /api/memory/observations?namespace=…&status=failed`; retry with `POST /api/memory/consolidate` |
| Why this context was assembled | `GET /api/memory/context/trace/{trace_id}` |
| Trace of an operation (write, deletion, personal data access) | `GET /api/brain/trace/{trace_id}?namespace=…` |
| Logs | `tools/compose logs -f memory-service` |

## Common problems

| Symptom | Cause | What to do |
|---|---|---|
| Search finds only exact words | `CB_EMBEDDING_PROVIDER=fake` | Enable a real provider and reindex |
| `500` with an error about the dimension and `CB_EMBEDDING_DIM` | The model and `CB_EMBEDDING_DIM` differ from the table | See [reindex](#reindex) |
| After an upgrade the graph is empty and search finds only fragments | The graph stayed in Apache AGE and was not moved | [Moving from Apache AGE](#age-migration) |
| `401` for a valid IAM token | `iss` (`CB_IAM_ISSUER`) or `aud` does not match; the token was not issued for `memory-service` | Compare the issuer with IAM's public address; exchange the PAT for audience `memory-service` |
| `503` on requests with an IAM token | JWKS unavailable or `CB_IAM_JWKS_URL` empty | Check the internal IAM address |
| `403` "no permission on the namespace" | A request without `scope` went to the default namespace, or the grant does not cover the base | Pass `scope` explicitly, check the grants |
| `403` on `packages`/`reconcile` | The core routes restriction is enabled | Call through Control Plane or as the core identity |
| `500` on every request with a token | Invalid JSON in `CB_API_KEYS` | Fix the configuration |
| `[ПДн:…]` in responses | A token without clearance with `CB_PII_PROTECTION=true` | Issue a key with `"pii": true` or the `memory:pii` scope, if justified |
| Rerank "does not work", `rerank_score: null` | `CB_LLM_PROVIDER=echo`, an empty key, or the model did not return valid JSON | Check the LLM provider and model |
| Slow graph traversal | JIT is enabled (`CB_DB_JIT=true` or `options` in the URL) | Restore `jit=off` |

More scenarios are in [Common memory problems](../troubleshooting/memory.md).

## See also

- [Namespaces and access](namespaces.md)
- [Search and context assembly](retrieval.md)
- [Environment variables](../reference/environment.md)
- [Services and ports](../reference/services-and-ports.md)
- [Backup](../operations/backup.md)
- [Deployment](../operations/deployment.md)
