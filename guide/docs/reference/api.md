
# Core service APIs

The list of HTTP API operations of the three core services, taken from their
OpenAPI at the superproject's submodule revisions. The "Edge" column shows how
the operation is reachable from outside through Caddy
([Edge and TLS](../operations/edge-and-tls.md)): a public path or "internal
network only" (the IAM administrative surface, metrics, all of memory-service).

Full request and response schemas are in the services' own OpenAPI:
`https://<public address>/openapi.json` for Control Plane, `/iam/openapi.json`
for IAM; memory-service, from inside the compose network.

## Control Plane

<!-- generated:api-control-plane -->
_This section is generated from code; do not edit it by hand._

API version `0.9.0`, operations: 256.

| Method | Path | Description | Edge |
|---|---|---|---|
| `GET` | `/api/v1/agents` | A page of agents; include=status adds the observed state of each | public |
| `POST` | `/api/v1/agents` | Publish an agent spec: a new revision only when its canonical hash differs | public |
| `GET` | `/api/v1/agents/me` | The agent the caller is, with its current revision and its package's settings | public |
| `GET` | `/api/v1/agents/me/connections` | The connections the caller's agent names, without material | public |
| `GET` | `/api/v1/agents/me/connections/{key}` | One connection the caller's agent names; any other key is not found | public |
| `PUT` | `/api/v1/agents/{key}/identity` | Link the IAM identity of an agent; the core derives principal and binding | public |
| `POST` | `/api/v1/agents/{key}/identity:replace` | Move a service agent to a new IAM identity; the principal stays the same | public |
| `GET` | `/api/v1/agents/{key}/revisions` | Revisions of an agent, newest first, without their specs (those are key@revision) | public |
| `GET` | `/api/v1/agents/{key}/secrets` | The names of an agent's secrets, without values | public |
| `PUT` | `/api/v1/agents/{key}/secrets/{name}` | Set an agent's secret by name: the value goes to the secret store | public |
| `DELETE` | `/api/v1/agents/{key}/secrets/{name}` | Delete an agent's secret with every version from the secret store | public |
| `PATCH` | `/api/v1/agents/{key}/state` | Change the desired state or replicas; never a new revision | public |
| `GET` | `/api/v1/agents/{key}/status` | Observed state of an agent | public |
| `PUT` | `/api/v1/agents/{key}/status` | Report the observed state of an agent (placement service only) | public |
| `POST` | `/api/v1/agents/{key}:retire` | Retire an agent: stop it, revoke its binding, keep its history | public |
| `GET` | `/api/v1/agents/{ref}` | An agent by key (current revision) or key@revision | public |
| `POST` | `/api/v1/agents:validate` | Run every check of POST /agents without saving anything | public |
| `POST` | `/api/v1/api-keys/{api_key_id}:revoke` | Revoke Api Key | public |
| `GET` | `/api/v1/approvals` | List Approvals | public |
| `POST` | `/api/v1/approvals` | Request Approval | public |
| `GET` | `/api/v1/approvals/{approval_id}` | Get Approval | public |
| `GET` | `/api/v1/approvals/{approval_id}/outcome` | The declared outcome of a decision and what happened to each action | public |
| `POST` | `/api/v1/approvals/{approval_id}:approve` | Approve | public |
| `POST` | `/api/v1/approvals/{approval_id}:cancel` | Cancel | public |
| `POST` | `/api/v1/approvals/{approval_id}:reject` | Reject | public |
| `POST` | `/api/v1/approvals/{approval_id}:replay-outcome` | Resume a failed or stuck approval outcome at its first action that did not execute | public |
| `PUT` | `/api/v1/artifact-contents` | Upload the bytes of an artifact; returns a contentRef | public |
| `GET` | `/api/v1/artifact-types` | List Artifact Types | public |
| `POST` | `/api/v1/artifact-types` | Create the next immutable version of an artifact type | public |
| `GET` | `/api/v1/artifact-types/{ref}` | Get Artifact Type | public |
| `GET` | `/api/v1/artifacts` | List Artifacts | public |
| `POST` | `/api/v1/artifacts` | Create Artifact | public |
| `GET` | `/api/v1/artifacts/{artifact_id}` | Get Artifact | public |
| `GET` | `/api/v1/artifacts/{artifact_id}/content` | Stream the stored content of an artifact | public |
| `POST` | `/api/v1/artifacts/{artifact_id}:purge-content` | Remove the stored bytes of an artifact (admin); the record stays | public |
| `POST` | `/api/v1/authz:check` | Whether the caller may perform each action on its resource, as the endpoint decides | public |
| `POST` | `/api/v1/bootstrap` | Create the first tenant, admin principal, admin API key and, optionally, the admin's IAM binding | public |
| `GET` | `/api/v1/calendars` | List Calendars | public |
| `POST` | `/api/v1/calendars` | Publish a calendar: a new version only when its canonical hash differs | public |
| `POST` | `/api/v1/calendars/{key}:retire` | Retire a calendar no process needs any more | public |
| `GET` | `/api/v1/calendars/{ref}` | A calendar by key (latest version) or key@version | public |
| `GET` | `/api/v1/capabilities` | List Capabilities | public |
| `POST` | `/api/v1/capabilities` | Create Capability | public |
| `GET` | `/api/v1/capabilities/{capability_id}` | Get Capability | public |
| `POST` | `/api/v1/child-handles/{handle_id}:revoke` | Withdraw a child handle, optionally asking the child to stop | public |
| `GET` | `/api/v1/child-handles/{ref}` | Resolve a child handle by id or by ch1_ token | public |
| `GET` | `/api/v1/claims` | List Claims | public |
| `GET` | `/api/v1/claims/{claim_id}` | Get Claim | public |
| `POST` | `/api/v1/claims/{claim_id}:heartbeat` | Heartbeat Claim | public |
| `POST` | `/api/v1/claims/{claim_id}:reclaim` | Take over an expired claim atomically (new fencing token) | public |
| `POST` | `/api/v1/claims/{claim_id}:release` | Release Claim | public |
| `GET` | `/api/v1/connection-types` | List Connection Types | public |
| `POST` | `/api/v1/connection-types` | Publish a version of a connection type; the same spec again changes nothing | public |
| `GET` | `/api/v1/connection-types/{key}/oauth-app` | Whether the OAuth application of a type is set, and its client id | public |
| `PUT` | `/api/v1/connection-types/{key}/oauth-app` | Set the OAuth application of a type; the secret goes to the secret store only | public |
| `GET` | `/api/v1/connection-types/{ref}` | Get Connection Type | public |
| `PATCH` | `/api/v1/connection-types/{ref}` | Move the status of one version (key@version) forward | public |
| `GET` | `/api/v1/connections` | List Connections | public |
| `POST` | `/api/v1/connections` | Create a connection; it waits for authorization | public |
| `GET` | `/api/v1/connections/{key}` | Get Connection | public |
| `PATCH` | `/api/v1/connections/{key}` | Change the display name, settings or type version of a connection | public |
| `PUT` | `/api/v1/connections/{key}/status` | Report that access still works or has expired (the connector only) | public |
| `PUT` | `/api/v1/connections/{key}/token` | Connect with a key: the key goes to the secret store, the connection is active | public |
| `POST` | `/api/v1/connections/{key}:authorize` | Start OAuth: a one-time state and the provider's address for consent | public |
| `POST` | `/api/v1/connections/{key}:revoke` | Revoke: the material and the agents' access go, the connection is revoked | public |
| `GET` | `/api/v1/connections:callback` | The provider returns the browser here; the one-time state authenticates it | public |
| `POST` | `/api/v1/context` | Working Context | public |
| `GET` | `/api/v1/context-packs/{pack_id}` | Get Context Pack | public |
| `POST` | `/api/v1/context-packs/{pack_id}:replay` | Replay Context Pack | public |
| `POST` | `/api/v1/context/recall` | Recall Graph | public |
| `GET` | `/api/v1/delegations` | List Delegations | public |
| `POST` | `/api/v1/delegations` | Create Delegation | public |
| `POST` | `/api/v1/delegations/{delegation_id}:revoke` | Revoke Delegation | public |
| `GET` | `/api/v1/event-types` | The event catalog: groups, versions and payload schemas of the types, captions in the language asked | public |
| `GET` | `/api/v1/events` | List Events | public |
| `GET` | `/api/v1/events:export` | Export the journal of a bounded period for an audit, streamed as JSONL or CSV | public |
| `GET` | `/api/v1/external-references` | List External References | public |
| `POST` | `/api/v1/external-references` | Register External Reference | public |
| `GET` | `/api/v1/goals` | List Goals | public |
| `POST` | `/api/v1/goals` | State a desired state that work items can serve | public |
| `GET` | `/api/v1/goals/{goal_id}` | Get Goal | public |
| `PATCH` | `/api/v1/goals/{goal_id}` | Update Goal | public |
| `GET` | `/api/v1/goals/{goal_id}/work` | Work items that serve this goal, newest first | public |
| `GET` | `/api/v1/harness/context` | Get Harness Context | public |
| `POST` | `/api/v1/iam-bindings/{binding_id}:revoke` | Close entry for a federated identity without waiting for its token to expire | public |
| `POST` | `/api/v1/knowledge/documents` | Submit Document | public |
| `POST` | `/api/v1/knowledge/entities:query` | Query Entities | public |
| `POST` | `/api/v1/knowledge/packs` | Register Pack | public |
| `GET` | `/api/v1/knowledge/packs/{ref}` | Get Pack | public |
| `POST` | `/api/v1/knowledge/snapshots` | Submit Snapshot | public |
| `POST` | `/api/v1/knowledge/snapshots:preview` | Preview Snapshot | public |
| `GET` | `/api/v1/me/attention` | What needs the calling principal now, highest score first | public |
| `POST` | `/api/v1/me/attention/{item_key}:feedback` | Record whether an item of the caller's attention list was worth showing | public |
| `POST` | `/api/v1/observations` | Record Observation | public |
| `GET` | `/api/v1/operations/context-adapter` | Context Adapter Status | public |
| `POST` | `/api/v1/operations/context-adapter/{tenant_id}:rebuild` | Rebuild Context Adapter | public |
| `POST` | `/api/v1/operations/context-adapter/{tenant_id}:redrive` | Redrive Context Adapter | public |
| `POST` | `/api/v1/operations/journal:archive` | Archive Journal | public |
| `POST` | `/api/v1/operations/journal:prune` | Prune Journal | public |
| `GET` | `/api/v1/package-settings` | The packages whose installed revision declares settings | public |
| `GET` | `/api/v1/packages/{key}/settings` | The settings of a package: schema and layout with their strings, saved and effective values | public |
| `PUT` | `/api/v1/packages/{key}/settings` | Save the settings of a package whole: a new version, or the state as it is when nothing changes | public |
| `GET` | `/api/v1/packages/{key}/settings/versions` | The history of the settings of a package, newest first | public |
| `POST` | `/api/v1/packages:apply` | Apply exactly the plan with this hash; the catalog changed since — 409 plan_stale | public |
| `POST` | `/api/v1/packages:plan` | Plan applying a package: structural and behavioural diff, open instances, hash | public |
| `POST` | `/api/v1/packages:record` | Link the objects an installer applied through their routes to their package | public |
| `POST` | `/api/v1/packages:test` | Check a package and run the tests of its processes, rules and task types; nothing is written | public |
| `GET` | `/api/v1/principals` | List Principals | public |
| `POST` | `/api/v1/principals` | Create Principal | public |
| `GET` | `/api/v1/principals/{principal_id}` | Get Principal | public |
| `PATCH` | `/api/v1/principals/{principal_id}` | Change the display name and profile of a principal | public |
| `POST` | `/api/v1/principals/{principal_id}/api-keys` | Issue an API key; the full key is returned only in this response | public |
| `GET` | `/api/v1/principals/{principal_id}/capabilities` | List Capabilities | public |
| `POST` | `/api/v1/principals/{principal_id}/capabilities` | Assign Capability | public |
| `POST` | `/api/v1/principals/{principal_id}/capabilities/{capability_id}:revoke` | Revoke Capability | public |
| `GET` | `/api/v1/principals/{principal_id}/iam-bindings` | Federated identities bound to a principal, revoked ones included | public |
| `POST` | `/api/v1/principals/{principal_id}/iam-bindings` | Bind an IAM identity to a principal (upsert by issuer + IAM principal) | public |
| `GET` | `/api/v1/principals/{principal_id}/roles` | List Roles | public |
| `POST` | `/api/v1/principals/{principal_id}/roles` | Assign Role | public |
| `POST` | `/api/v1/principals/{principal_id}/roles/{role_id}:revoke` | Revoke Role | public |
| `GET` | `/api/v1/principals/{principal_id}/skills` | List Skills | public |
| `POST` | `/api/v1/principals/{principal_id}/skills` | Assign Skill | public |
| `POST` | `/api/v1/principals/{principal_id}/skills/{skill_id}:revoke` | Revoke Skill | public |
| `POST` | `/api/v1/principals/{principal_id}:disable` | Disable a human or agent: revoke its bindings, close its sessions, free its claims | public |
| `POST` | `/api/v1/principals/{principal_id}:enable` | Enable a disabled human or agent; IAM bindings revoked by :disable stay revoked | public |
| `GET` | `/api/v1/process-definitions` | List Process Definitions | public |
| `POST` | `/api/v1/process-definitions` | Publish a process version: immutable, the same version with other content is 409 | public |
| `GET` | `/api/v1/process-definitions/{key}/versions` | Versions of a process, newest first, without their spec (ProcessVersionOut) | public |
| `POST` | `/api/v1/process-definitions/{key}:replay` | Feed the journals of real instances to a candidate version; nothing is written | public |
| `POST` | `/api/v1/process-definitions/{key}:retire` | Retire a process — no new instances, open ones run to the end | public |
| `GET` | `/api/v1/process-definitions/{ref}` | A process by key (latest version) or key@version | public |
| `GET` | `/api/v1/process-instances` | List Process Instances | public |
| `POST` | `/api/v1/process-instances` | Start an instance without a trigger event; a key that has one is 409 | public |
| `GET` | `/api/v1/process-instances/{instance_id}` | State of an instance: data, stages, open elements, timers | public |
| `GET` | `/api/v1/process-instances/{instance_id}/journal` | Decision journal of an instance (ProcessJournalEntryOut), oldest first | public |
| `POST` | `/api/v1/process-instances/{instance_id}:cancel` | Cancel an instance, compensating completed steps first by default | public |
| `POST` | `/api/v1/process-instances/{instance_id}:resume` | Resume a suspended instance; frozen timers get their remaining time back | public |
| `POST` | `/api/v1/process-instances/{instance_id}:suspend` | Suspend an instance; its timers freeze | public |
| `GET` | `/api/v1/project-templates` | List Project Templates | public |
| `POST` | `/api/v1/project-templates` | Create the next immutable version of a project template | public |
| `GET` | `/api/v1/project-templates/{template_id}` | Get Project Template | public |
| `POST` | `/api/v1/project-templates/{template_id}:deprecate` | Deprecate Project Template | public |
| `GET` | `/api/v1/projects` | List Projects | public |
| `POST` | `/api/v1/projects` | Create Project | public |
| `GET` | `/api/v1/projects/{project_id}` | Get Project | public |
| `PATCH` | `/api/v1/projects/{project_id}` | Update Project | public |
| `GET` | `/api/v1/projects/{project_id}/config-revisions` | List Config Revisions | public |
| `POST` | `/api/v1/projects/{project_id}/config-revisions` | Create Config Revision | public |
| `POST` | `/api/v1/projects/{project_id}/config-revisions/{revision}:activate` | Activate Config Revision | public |
| `GET` | `/api/v1/projects/{project_id}/effective-config` | Get Effective Config | public |
| `GET` | `/api/v1/projects/{project_id}/external-references` | List External References | public |
| `POST` | `/api/v1/projects/{project_id}/external-references` | Add External Reference | public |
| `POST` | `/api/v1/projects/{project_id}:archive` | Archive Project | public |
| `POST` | `/api/v1/projects/{project_id}:transition` | Transition Project | public |
| `GET` | `/api/v1/roles` | List Roles | public |
| `POST` | `/api/v1/roles` | Create Role | public |
| `GET` | `/api/v1/roles/{role_id}` | Get Role | public |
| `PATCH` | `/api/v1/roles/{role_id}` | Update Role | public |
| `GET` | `/api/v1/roles/{role_id}/principals` | List Role Holders | public |
| `GET` | `/api/v1/rule-evaluations/{evaluation_id}` | One evaluation by id: what origin.ref = rule_evaluation:<id> points to | public |
| `GET` | `/api/v1/rules` | List Rules | public |
| `POST` | `/api/v1/rules` | Write a rule that derives work from observed facts | public |
| `GET` | `/api/v1/rules/{rule_id}` | Get Rule | public |
| `PATCH` | `/api/v1/rules/{rule_id}` | Update Rule | public |
| `DELETE` | `/api/v1/rules/{rule_id}` | Archive a rule; its history and the work it filed stay | public |
| `GET` | `/api/v1/rules/{rule_id}/evaluations` | What the rule looked at and what it did, newest first | public |
| `POST` | `/api/v1/rules/{rule_id}:disable` | Disable a rule: it stops evaluating new facts | public |
| `POST` | `/api/v1/rules/{rule_id}:enable` | Enable a rule: it acts from now on, with the caller's authority | public |
| `GET` | `/api/v1/runs` | List Runs | public |
| `GET` | `/api/v1/runs/{run_id}` | Get Run | public |
| `GET` | `/api/v1/runs/{run_id}/actions` | List Actions | public |
| `POST` | `/api/v1/runs/{run_id}/actions` | Record an execution action (audit trail; enforces the run budget) | public |
| `POST` | `/api/v1/runs/{run_id}/actions/{action_id}:finish` | Finish Action | public |
| `GET` | `/api/v1/runs/{run_id}/checkpoints` | List Checkpoints | public |
| `POST` | `/api/v1/runs/{run_id}/checkpoints` | Append a durable execution checkpoint (live owner only) | public |
| `GET` | `/api/v1/runs/{run_id}/child-handles` | List child handles launched by this Run | public |
| `POST` | `/api/v1/runs/{run_id}/child-handles` | Launch a child run under this Run and return its durable handle | public |
| `GET` | `/api/v1/runs/{run_id}/context` | Structured execution context for a run (task, claim, artifacts, checkpoints, skills) | public |
| `GET` | `/api/v1/runs/{run_id}/control-messages` | List durable Run control messages in Run-local sequence order | public |
| `POST` | `/api/v1/runs/{run_id}/control-messages` | Append one durable Active Turn Control message | public |
| `POST` | `/api/v1/runs/{run_id}/control-messages/{message_id}:acknowledge` | Acknowledge the oldest accepted control message at a safe boundary | public |
| `POST` | `/api/v1/runs/{run_id}:cancel` | Cancel Run | public |
| `POST` | `/api/v1/runs/{run_id}:fail` | Fail Run | public |
| `POST` | `/api/v1/runs/{run_id}:handoff` | Checkpoint, suspend and release a run for a new human-operated harness | public |
| `POST` | `/api/v1/runs/{run_id}:request-cancel` | Signal cooperative cancellation (authoritative stop is :cancel) | public |
| `POST` | `/api/v1/runs/{run_id}:succeed` | Finish a run successfully (atomically completes the task by default) | public |
| `POST` | `/api/v1/runs/{run_id}:suspend` | Pause execution: run -> suspended, claim released (waiting semantics) | public |
| `GET` | `/api/v1/sessions` | List Sessions | public |
| `POST` | `/api/v1/sessions` | Open Session | public |
| `GET` | `/api/v1/sessions/{session_id}` | Get Session | public |
| `POST` | `/api/v1/sessions/{session_id}:close` | Close Session | public |
| `POST` | `/api/v1/sessions/{session_id}:heartbeat` | Heartbeat Session | public |
| `GET` | `/api/v1/skill-invocations/{invocation_id}` | Get Skill Invocation | public |
| `POST` | `/api/v1/skill-invocations/{invocation_id}:cancel` | Cancel Skill Invocation | public |
| `POST` | `/api/v1/skill-invocations/{invocation_id}:complete` | Complete Skill Invocation | public |
| `POST` | `/api/v1/skill-invocations/{invocation_id}:fail` | Fail Skill Invocation | public |
| `POST` | `/api/v1/skill-invocations/{invocation_id}:heartbeat` | Heartbeat Skill Invocation | public |
| `POST` | `/api/v1/skill-invocations:claim` | Claim Skill Invocation | public |
| `GET` | `/api/v1/skills` | List Skills | public |
| `POST` | `/api/v1/skills` | Register Skill | public |
| `PATCH` | `/api/v1/skills/{skill_id}` | Update Skill | public |
| `GET` | `/api/v1/skills/{skill_ref}` | Get Skill | public |
| `POST` | `/api/v1/skills/{skill_ref}:invoke` | Invoke Skill | public |
| `GET` | `/api/v1/task-types` | List Task Types | public |
| `POST` | `/api/v1/task-types` | Create the next immutable version of a work item type | public |
| `GET` | `/api/v1/task-types/{type_id}` | Get Task Type | public |
| `GET` | `/api/v1/task-types/{type_id}/executors` | Who may take this task type version in a workspace (ADR-0048, 2026-10-03 A2) | public |
| `POST` | `/api/v1/task-types/{type_id}:deprecate` | Deprecate Task Type | public |
| `POST` | `/api/v1/task-types/{type_id}:migrate-tasks` | Move the open tasks of this version to another version of its key (ADR-0048) | public |
| `GET` | `/api/v1/tasks` | List Tasks | public |
| `POST` | `/api/v1/tasks` | Create Task | public |
| `GET` | `/api/v1/tasks/{task_ref}` | Get Task | public |
| `PATCH` | `/api/v1/tasks/{task_ref}` | Update Task | public |
| `GET` | `/api/v1/tasks/{task_ref}/claimability` | Advisory diagnosis: can the caller claim this task, and why not | public |
| `GET` | `/api/v1/tasks/{task_ref}/comments` | One page of the thread, oldest first | public |
| `POST` | `/api/v1/tasks/{task_ref}/comments` | Append a reply to a work item's discussion | public |
| `GET` | `/api/v1/tasks/{task_ref}/comments/{comment_id}` | Get Comment | public |
| `PATCH` | `/api/v1/tasks/{task_ref}/comments/{comment_id}` | Correct one's own comment; the previous version is kept | public |
| `GET` | `/api/v1/tasks/{task_ref}/comments/{comment_id}/revisions` | Superseded versions of a comment, oldest first | public |
| `GET` | `/api/v1/tasks/{task_ref}/relations` | List Relations | public |
| `POST` | `/api/v1/tasks/{task_ref}/relations` | Add Relation | public |
| `DELETE` | `/api/v1/tasks/{task_ref}/relations/{relation_id}` | Remove Relation | public |
| `GET` | `/api/v1/tasks/{task_ref}/requirements` | Get Requirements | public |
| `GET` | `/api/v1/tasks/{task_ref}/transitions` | Where this task may move next, per the lifecycle of its type | public |
| `GET` | `/api/v1/tasks/{task_ref}/verifications` | Attempts of the verification stage, newest first (CP-ADR-0067) | public |
| `POST` | `/api/v1/tasks/{task_ref}:claim` | Atomically claim a task (lease + fencing token) | public |
| `POST` | `/api/v1/tasks/{task_ref}:complete` | Complete Task | public |
| `POST` | `/api/v1/tasks/{task_ref}:migrate-type` | Move an open task to another version of its type (ADR-0048) | public |
| `POST` | `/api/v1/tasks/{task_ref}:start-run` | Start an execution attempt under a live claim | public |
| `GET` | `/api/v1/tools` | Tools this principal may use right now (bounded projection) | public |
| `GET` | `/api/v1/tools/{tool_ref}` | Full sanitized projection of one tool | public |
| `GET` | `/api/v1/views` | The views of packages the caller sees: a role of their audience and the right to read their source | public |
| `GET` | `/api/v1/views/{view_key}` | A view by key, its strings in the language asked; one the caller may not see is 404 | public |
| `POST` | `/api/v1/views/{view_key}:query` | The data one block of a view draws, as the caller may see it; a view or an instance the caller may not see is 404 | public |
| `GET` | `/api/v1/work/available` | Tasks the calling principal could claim right now (advisory) | public |
| `GET` | `/api/v1/workspace-types` | List Workspace Types | public |
| `POST` | `/api/v1/workspace-types` | Create Workspace Type | public |
| `GET` | `/api/v1/workspace-types/{type_id}` | Get Workspace Type | public |
| `PATCH` | `/api/v1/workspace-types/{type_id}` | Update Workspace Type | public |
| `POST` | `/api/v1/workspace-types/{type_id}:archive` | Archive Workspace Type | public |
| `GET` | `/api/v1/workspaces` | List Workspaces | public |
| `POST` | `/api/v1/workspaces` | Create Workspace | public |
| `GET` | `/api/v1/workspaces/tree` | Get Workspace Tree | public |
| `GET` | `/api/v1/workspaces/{workspace_id}` | Get Workspace | public |
| `PATCH` | `/api/v1/workspaces/{workspace_id}` | Update Workspace | public |
| `GET` | `/api/v1/workspaces/{workspace_id}/knowledge-packs` | Get Workspace Packs | public |
| `PUT` | `/api/v1/workspaces/{workspace_id}/knowledge-packs` | Set Workspace Packs | public |
| `GET` | `/api/v1/workspaces/{workspace_id}/members` | List Members | public |
| `POST` | `/api/v1/workspaces/{workspace_id}/members` | Add Member | public |
| `POST` | `/api/v1/workspaces/{workspace_id}/members/{principal_id}:remove` | Remove Member | public |
| `GET` | `/api/v1/workspaces/{workspace_id}/participants` | List Participants | public |
| `POST` | `/api/v1/workspaces/{workspace_id}:archive` | Archive Workspace | public |
| `POST` | `/api/v1/workspaces/{workspace_id}:move` | Move Workspace | public |
| `GET` | `/health/live` | Health Live | public |
| `GET` | `/health/ready` | Health Ready | public |
| `GET` | `/metrics` | Metrics Endpoint | internal network only |
<!-- /generated:api-control-plane -->

## IAM

<!-- generated:api-iam-service -->
_This section is generated from code; do not edit it by hand._

API version `0.1.0`, operations: 62.

| Method | Path | Description | Edge |
|---|---|---|---|
| `GET` | `/.well-known/jwks.json` | Jwks | `/iam/.well-known/jwks.json` |
| `GET` | `/api/v1/events` | List Events | internal network only |
| `POST` | `/api/v1/platform-access-tokens:exchange` | Exchange Platform Access Token | `/iam/api/v1/platform-access-tokens:exchange` |
| `POST` | `/api/v1/platform-access-tokens:introspect` | Introspect Platform Access Token | `/iam/api/v1/platform-access-tokens:introspect` |
| `POST` | `/api/v1/platform-access-tokens:revoke-self` | Revoke Presented Platform Access Token | `/iam/api/v1/platform-access-tokens:revoke-self` |
| `POST` | `/api/v1/tenants` | Create Tenant | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/agents` | Create Agent | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/agents/{agent_id}/platform-access-tokens` | Issue Agent Platform Access Token | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/agents/{agent_id}/platform-access-tokens/{credential_id}:revoke` | Revoke Agent Platform Access Token | internal network only |
| `GET` | `/api/v1/tenants/{tenant_id}/audiences` | List Audiences | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/audiences` | Create Audience | internal network only |
| `PATCH` | `/api/v1/tenants/{tenant_id}/audiences/{key}` | Update Audience | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/channel-assertions:exchange` | Exchange Channel Assertion | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/channel-link-intents` | Create Channel Link Intent | internal network only |
| `GET` | `/api/v1/tenants/{tenant_id}/channel-links` | List Channel Links | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/channel-links/{link_id}:revoke` | Revoke Channel Link | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/channel-links:confirm` | Confirm Channel Link | internal network only |
| `GET` | `/api/v1/tenants/{tenant_id}/channel-providers` | List Channel Providers | internal network only |
| `PUT` | `/api/v1/tenants/{tenant_id}/channel-providers/{channel}` | Configure Channel Provider | internal network only |
| `GET` | `/api/v1/tenants/{tenant_id}/external-identities` | Find External Identity | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/federation:authenticate` | Authenticate Federated Identity | `/iam/api/v1/tenants/{tenant_id}/federation:authenticate` |
| `POST` | `/api/v1/tenants/{tenant_id}/federation:exchange` | Exchange Federated Identity | `/iam/api/v1/tenants/{tenant_id}/federation:exchange` |
| `POST` | `/api/v1/tenants/{tenant_id}/groups` | Create Group | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/groups/{group_id}/members` | Add Group Member | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/identity-providers` | Create Identity Provider | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/legacy-credentials:import` | Import Legacy Credential | internal network only |
| `GET` | `/api/v1/tenants/{tenant_id}/platform-access-tokens` | List Platform Access Tokens | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/platform-access-tokens/{credential_id}:revoke` | Revoke Platform Access Token | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/platform-access-tokens/{credential_id}:rotate` | Rotate Platform Access Token | internal network only |
| `GET` | `/api/v1/tenants/{tenant_id}/principals` | List Principals | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/principals` | Create Principal | internal network only |
| `GET` | `/api/v1/tenants/{tenant_id}/principals/{principal_id}` | Get Principal | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/principals/{principal_id}/authentication-contexts` | Create Authentication Context | internal network only |
| `GET` | `/api/v1/tenants/{tenant_id}/principals/{principal_id}/external-identities` | List Principal External Identities | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/principals/{principal_id}/external-identities` | Link External Identity | internal network only |
| `DELETE` | `/api/v1/tenants/{tenant_id}/principals/{principal_id}/external-identities/{identity_id}` | Unlink Connection Identity | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/principals/{principal_id}/platform-access-tokens` | Issue Platform Access Token | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/principals/{principal_id}:disable` | Disable Principal | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/principals/{principal_id}:enable` | Enable Principal | internal network only |
| `GET` | `/api/v1/tenants/{tenant_id}/principals:by-email` | Find Principals By Email | internal network only |
| `GET` | `/api/v1/tenants/{tenant_id}/provisioning-sources` | List Provisioning Sources | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/provisioning-sources` | Register Provisioning Source | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/service-accounts` | Create Service Account | internal network only |
| `PATCH` | `/api/v1/tenants/{tenant_id}/service-accounts/{client_id}` | Update Service Account | internal network only |
| `POST` | `/api/v1/tenants/{tenant_id}/service-accounts/{client_id}:revoke` | Revoke Service Account | internal network only |
| `POST` | `/api/v1/tokens/exchange` | Exchange Token | `/iam/api/v1/tokens/exchange` |
| `GET` | `/healthz` | Health | `/iam/healthz` |
| `GET` | `/scim/v2/Groups` | Scim List Groups | `/iam/scim/v2/Groups` |
| `POST` | `/scim/v2/Groups` | Scim Create Group | `/iam/scim/v2/Groups` |
| `GET` | `/scim/v2/Groups/{group_id}` | Scim Get Group | `/iam/scim/v2/Groups/{group_id}` |
| `PUT` | `/scim/v2/Groups/{group_id}` | Scim Replace Group | `/iam/scim/v2/Groups/{group_id}` |
| `PATCH` | `/scim/v2/Groups/{group_id}` | Scim Patch Group | `/iam/scim/v2/Groups/{group_id}` |
| `DELETE` | `/scim/v2/Groups/{group_id}` | Scim Delete Group | `/iam/scim/v2/Groups/{group_id}` |
| `GET` | `/scim/v2/ResourceTypes` | Scim Resource Types | `/iam/scim/v2/ResourceTypes` |
| `GET` | `/scim/v2/Schemas` | Scim Schemas | `/iam/scim/v2/Schemas` |
| `GET` | `/scim/v2/ServiceProviderConfig` | Scim Service Provider Config | `/iam/scim/v2/ServiceProviderConfig` |
| `GET` | `/scim/v2/Users` | Scim List Users | `/iam/scim/v2/Users` |
| `POST` | `/scim/v2/Users` | Scim Create User | `/iam/scim/v2/Users` |
| `GET` | `/scim/v2/Users/{user_id}` | Scim Get User | `/iam/scim/v2/Users/{user_id}` |
| `PUT` | `/scim/v2/Users/{user_id}` | Scim Replace User | `/iam/scim/v2/Users/{user_id}` |
| `PATCH` | `/scim/v2/Users/{user_id}` | Scim Patch User | `/iam/scim/v2/Users/{user_id}` |
| `DELETE` | `/scim/v2/Users/{user_id}` | Scim Delete User | `/iam/scim/v2/Users/{user_id}` |
<!-- /generated:api-iam-service -->

## Memory Service

<!-- generated:api-memory-service -->
_This section is generated from code; do not edit it by hand._

API version `0.1.0`, operations: 37.

| Method | Path | Description | Edge |
|---|---|---|---|
| `POST` | `/api/brain/audit` | Brain Audit | internal network only |
| `POST` | `/api/brain/documents` | Brain Document Ingest | internal network only |
| `DELETE` | `/api/brain/documents/{natural_key}` | Brain Document Delete | internal network only |
| `POST` | `/api/brain/facts` | Write Fact | internal network only |
| `GET` | `/api/brain/health` | Brain Health | internal network only |
| `GET` | `/api/brain/nodes` | Brain Nodes | internal network only |
| `GET` | `/api/brain/nodes/{natural_key}` | Brain Node | internal network only |
| `DELETE` | `/api/brain/nodes/{natural_key}` | Brain Node Delete | internal network only |
| `POST` | `/api/brain/query` | Brain Query | internal network only |
| `POST` | `/api/brain/recall` | Brain Recall | internal network only |
| `POST` | `/api/brain/retain` | Brain Retain | internal network only |
| `POST` | `/api/brain/search` | Brain Search | internal network only |
| `GET` | `/api/brain/sources/{natural_key}` | Brain Source | internal network only |
| `GET` | `/api/brain/stats` | Brain Stats | internal network only |
| `GET` | `/api/brain/trace/{trace_id}` | Brain Trace | internal network only |
| `POST` | `/api/memory/consolidate` | Memory Consolidate | internal network only |
| `POST` | `/api/memory/context` | Memory Context | internal network only |
| `GET` | `/api/memory/context/trace/{trace_id}` | Memory Context Trace | internal network only |
| `POST` | `/api/memory/context/typed` | Memory Context Typed | internal network only |
| `POST` | `/api/memory/entities:query` | Memory Entities Query | internal network only |
| `GET` | `/api/memory/namespaces/{namespace}/kinds` | Memory Namespace Kinds | internal network only |
| `PUT` | `/api/memory/namespaces/{namespace}/kinds` | Memory Namespace Kinds Put | internal network only |
| `GET` | `/api/memory/observations` | Memory Observations List | internal network only |
| `POST` | `/api/memory/observations` | Memory Observe | internal network only |
| `GET` | `/api/memory/observations/{observation_id}` | Memory Observation Get | internal network only |
| `DELETE` | `/api/memory/observations/{observation_id}` | Memory Observation Delete | internal network only |
| `POST` | `/api/memory/observations:batch` | Memory Observe Batch | internal network only |
| `GET` | `/api/memory/packages` | Memory Packages List | internal network only |
| `POST` | `/api/memory/packages` | Memory Package Register | internal network only |
| `GET` | `/api/memory/packages/{name}` | Memory Package Get | internal network only |
| `POST` | `/api/memory/reconcile` | Memory Reconcile | internal network only |
| `POST` | `/audit` | Brain Audit | internal network only |
| `GET` | `/health` | Brain Health | internal network only |
| `GET` | `/healthz` | Healthz | internal network only |
| `POST` | `/recall` | Brain Recall | internal network only |
| `POST` | `/retain` | Brain Retain | internal network only |
| `POST` | `/search` | Brain Search | internal network only |
<!-- /generated:api-memory-service -->
