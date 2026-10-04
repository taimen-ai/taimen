
# Knowledge and ontology

Package processes query the knowledge base (`recall`), write to it (`remember`),
and keep a case projection in it (`memory`); integration observers give it
snapshots of external systems. To make these records typed and verifiable, a
package declares an **ontology** (entity kinds and the relations between them) and
states which ontologies it relies on. This article is for package authors: how to
describe an ontology with the `KnowledgePack` kind, declare it in the manifest,
enable it through the installation, and keep personal data out of the graph.
Rationale: TAI-ADR-0056 (company knowledge base), TAI-ADR-0062 (item 5).

Memory is available to a package only through the core: process queries,
observer snapshots, and the `ctx.knowledge` of skills go to Control Plane, and it
goes to memory. A package has no direct access to the memory service.

## Where things live

| What | Where | Who sets it |
|---|---|---|
| The package ontology | `knowledge-packs/<name>.yaml`, kind `KnowledgePack` | the package author |
| Which ontologies the package relies on | `Package.spec.knowledge: [name@version]` | the package author |
| Which ontologies are enabled for a workspace | `Installation.spec.knowledge` | the installation: this is topology |

## Package ontology: `KnowledgePack`

```yaml
# knowledge-packs/claims.yaml
apiVersion: taimen.ai/v1
kind: KnowledgePack
key: claims
spec:
  name: claims
  version: 1
  description: Claims of customers and their resolution
  extends: ["default@1"]
  kinds:
    - kind: claim
      title: Claim
      naturalKey: "claim:<source>:<id>"
      attributes:
        type: object
        properties:
          subject: {type: string, title: Subject}
          severity: {type: string, enum: [low, medium, high]}
          openedOn: {type: string, format: date}
      searchable: {fields: [subject]}
  relations:
    - relation: filed_by
      title: Filed by
      fromKinds: [claim]
      toKinds: [legal_entity]
      cardinality: one
```

`package-sdk add KnowledgePack claims` writes a scaffold with a single kind.

| `spec` field | What it sets |
|---|---|
| `name` | the ontology name without a prefix, `^[a-z0-9][a-z0-9._-]{0,63}$`; matches the object `key` (`check`: `knowledge_pack_key`) |
| `version` | an integer from 1. A registered version is immutable: editing the description means a new version |
| `scope` | `common` (the default): the shared registry; `tenant`: a tenant ontology |
| `extends` | up to 10 `name@version` ontologies whose kinds the relations and profiles of this one refer to; the base one does not change |
| `kinds[]` | a kind: `kind`, `title`, `description`, `naturalKey` (a template with placeholders or a JSON Schema of a string), `attributes` (JSON Schema), `searchable: {fields}` (attributes for semantic search), `aliases`, `kindAliases`, `idPatterns` |
| `relations[]` | a relation: `relation`, `title`, `fromKinds`, `toKinds`, `temporal` (`true` by default), `cardinality` (`one` or `many`) |
| `profiles[]` | attributes of a kind of this or another ontology; with `when: {attr, equals}`, only for entities where the attribute equals the value |
| `expiry[]` | to whom (`role`) and how many days ahead (`leadDays`, 1–365) to create a task about the expiry of the kind's `validUntil` |

The full form is `sdk/package-sdk/schema/v1/knowledge-pack.schema.json`.

- **Validity periods** are, by convention, the `validFrom` and `validUntil`
  attributes (`format: date`).
- **Your own on top of the base.** A class or vertical ontology adds only its own
  kinds and relations, and describes the attributes of someone else's kind with a
  profile instead of redeclaring it. An entity from a new source that already
  exists in the base is merged with it by the natural key.
- `extends` must name an ontology from this package, from its `requires`, or the
  platform memory ontology `default@1`; otherwise `check` reports
  `knowledge_extends_unknown`. `default@1` already contains an organization
  (`legal_entity`), a product (`product`), a contract (`contract`), a decision
  (`decision`), and other base kinds; your own ontology refers to them rather than
  redeclaring them. An ontology of another package is used through its
  `requires`.
- The same `name@version` ontology in two packages of an installation is allowed
  only if it is identical; otherwise `knowledge_pack_conflict`.

## Declaring what the package relies on

The manifest names the ontologies that the package's processes and rules rely on:

```yaml
# package.yaml
spec:
  knowledge: ["default@1", "claims@1"]
```

`check` collects kinds and relations from `memory`, `recall`, `remember`, and the
step context of the package's processes and reconciles them with the declared
ontologies:

| Code | Level | When |
|---|---|---|
| `knowledge_undeclared` | warning | processes access memory, but there is no `spec.knowledge` |
| `knowledge_unknown` | error | an ontology from `spec.knowledge` is not declared as a `KnowledgePack` in the package or its `requires` (except `default@1`) |
| `knowledge_term_unknown` | error | a kind or relation of a process is not in any of the declared ontologies (with their `extends`); a warning if the content of some ontologies is not visible because their `extends` are outside the packages. `default@1` is checked against the snapshot that the SDK carries |
| `knowledge_extends_unknown` | error | `extends` names an ontology that does not exist |
| `knowledge_pack_key` | error | the object `key` does not match `spec.name` |
| `knowledge_pack_conflict` | error | the same `name@version` in another package with different content |

The `rel` relation of case entities in `memory.entities` is a predicate of a fact
about the case, not an ontology relation: `check` does not verify it.

## Registration and enabling

Ontologies are a separate `knowledge` section of the single installation plan. It
is applied after the catalog and the core objects: first the versions that are not
yet on the deployment are registered, then the sets are enabled for workspaces:

```yaml
# packages.yaml — installation file
apiVersion: taimen.ai/v1
kind: Installation
key: production
spec:
  packages: [claims]
  knowledge:
    - workspace: ${CLAIMS_WORKSPACE_ID}       # root of the workspace tree
      packs: ["default@1", "claims@1"]
      strict: true
```

| Step | Call | Rules |
|---|---|---|
| Registering a version | `POST /api/v1/knowledge/packs` | a common ontology is registered by a platform administrator from `CP_KNOWLEDGE_PACK_ADMINS`, a tenant ontology (`scope: tenant`) requires the `knowledge.packs.manage` permission; the core fills in the owner namespace. `plan` reads the version from the deployment: if it is missing, registration is in the plan; if it exists but the kinds or relations in the package differ, the plan is not built: `поднимите version` ("raise version") |
| Enabling | `PUT /api/v1/workspaces/{id}/knowledge-packs` | the `workspaces.manage` permission, only on the root of the workspace tree (`422 workspace_not_root`), only pinned `name@version` references (`422 pack_version_required`) |

- An enabling request **replaces the whole set**. List in `packs` everything the
  workspace needs, including `default@1`. Several entries for one workspace are
  merged into one set.
- `plan` shows the resulting set next to the current one (`сейчас: …`, "now: …")
  and does not enable a workspace where the set and strictness are already the
  same.
- `strict: true` is the strict memory mode: records outside the kinds of the
  enabled ontologies are rejected rather than accepted as is. Strictness set in
  even one entry of a workspace applies to its whole set.
- A tenant ontology is enabled with a `tenant:<name>@<version>` reference and is
  visible only in the tenant namespace and the trees under it.
- An enabled ontology that is not in the installation packages must already exist
  on the deployment: `check` warns about it.

## How a package uses knowledge

| Who | How | Article |
|---|---|---|
| Process | `memory` (the case projection), the `recall` and `remember` steps, step context, regulations | [Processes and the knowledge base](../processes/knowledge.md) |
| Observer | `ctx.snapshot(Snapshot(source, snapshot_id, entities, relations, pack, scope))`: a snapshot of the external system that the core reconciles with the graph | [Integrations](integrations.md#observer) |
| Skill | `ctx.knowledge.recall`, `query`, `preview`, and `apply` with `stateToken`, `document` | [Package skills](skills.md) |

A snapshot and a write are made on behalf of the agent or the process identity:
they need the `observations.write` permission, and an observer with snapshots also
needs `workspace` in the `work` section of its description.

## Upload templates

The tables through which people upload records of a kind are not written by hand:
a generator builds them from the JSON Schema of the kind's attributes. So the kind
description is also the template:

- a property's `title` and `description` are the column header and hint;
- `type`, `format`, `enum` validate the value, and `required` makes it mandatory;
- key columns come from the `naturalKey` placeholders, relation columns from the
  relations that have the kind in `fromKinds`.

The form for refining how a template is presented (headers, order, hints,
examples, additional forbidden columns) is
`sdk/package-sdk/schema/v1/knowledge-template.schema.json`; a refinement does not add
columns that are not in the kind's schema.

## Personal data

- An attribute with personal data of an individual is allowed only with the
  `x-personal-data: allowed` mark; such values do not get into AI prompts.
- Upload templates forbid columns with personal data (full name, passport, SNILS,
  date of birth, address, phone, e-mail) and whatever the package added to
  `forbiddenColumns`.
- The `ctx.llm` of skills replaces personal data in the prompt with the
  `[ПДн:вид]` ("personal data: kind") marker before the model is called.
- Design the ontology so that a person is a role or an organization, not an entity
  with personal data: the "claim filed by" relation leads to a legal entity, not
  to a contact person.

## Common problems

| Symptom | Cause and fix |
|---|---|
| `plan`: `онтология … уже зарегистрирована, а kinds в пакете другие — … поднимите version` ("the ontology … is already registered, but the kinds in the package differ — … raise version") | the kinds or relations of the ontology were edited without a new `version` |
| `403` on registering a common ontology | the applier is not in `CP_KNOWLEDGE_PACK_ADMINS`: register it as a platform administrator or make it a tenant ontology (`scope: tenant`) |
| `422 workspace_not_root` | `Installation.spec.knowledge` names something other than the root of the workspace tree |
| kinds of another ontology disappeared after enabling | the set is replaced as a whole: it was not listed in `packs` |
| `check`: `knowledge_term_unknown` | a process refers to a kind or relation that is not in `spec.knowledge`: add the ontology or fix the kind |
| a memory write is rejected in strict mode | the record's kind is not part of the enabled ontologies |

## See also

- [Processes and the knowledge base](../processes/knowledge.md)
- [Integrations](integrations.md): knowledge snapshots by an observer
- [Knowledge model](../memory/knowledge-model.md)
- [Task context and memory](../control-plane/context.md)
