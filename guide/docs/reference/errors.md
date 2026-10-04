
# Error codes

Machine error codes of all platform services: code, HTTP status, cause, and
what to do. This page is for a harness or integration developer and for an
engineer who investigates a denial from a log. Codes are a stable contract:
react to `code`, not to the message text.

## Error response formats

Services use different envelopes. The error code is always in one field:

| Service | Envelope | Code field |
|---|---|---|
| Control Plane | `{"error": {"code", "message", "details", "requestId"}}` | `error.code` |
| iam-service | standard FastAPI `{"detail": "<code>"}` (SCIM uses the SCIM format, see below) | `detail` |
| memory-service | `{"detail": "<text>"}`: human-readable text, no machine codes | HTTP status |

Example Control Plane response:

```json
{
  "error": {
    "code": "stale_claim",
    "message": "Presented claim is no longer live",
    "details": {"taskId": "<task-id>"},
    "requestId": "req_…"
  }
}
```

`requestId` matches the field in the service log; use it to find the entry
with the stack trace for `500 internal_error`.

### General response rules

| HTTP | Meaning | Retry? |
|---|---|---|
| 400, 422 | The request violates the contract or a business rule | No: fix the request |
| 401 | No valid credential | No: reissue the token |
| 403 | The credential is valid, but permissions are insufficient | No: grant the permissions |
| 404 | Not found, or not visible to this principal | No |
| 409 | State conflict (claim, version, idempotency) | Depends on the code: reread the state |
| 413 | Body too large | No |
| 428 | `If-Match` required | Retry with the header |
| 429 | Rate limit | Yes, with a delay |
| 502, 503 | A dependency is unavailable; no decision was made (fail closed) | Yes, with a delay and the same `Idempotency-Key` |

!!! warning "Authentication denials are deliberately indistinguishable"
    A malformed, expired, or revoked token, a foreign issuer or audience, a
    disabled principal, a missing binding: the client always sees the same
    response (`401 invalid_credentials` from Control Plane, `401 invalid_token`
    from IAM and SDK services). Different codes would turn the endpoint into
    an oracle about other people's credentials. The exact reason is written
    only to the audit trail and the log; see [Audit reasons](#audit-reasons).

## Control Plane

Codes of `DomainError` and of the `control-plane` API handlers. Status by
error class: `ValidationError` 422, `BadRequestError` 400, `ConflictError`
409, `AuthorizationError` 403, `AuthenticationError` 401, `UpstreamError`
502, `DependencyUnavailableError` 503.

### General request errors

| Code | HTTP | Cause | What to do |
|---|---|---|---|
| `custom_fields_invalid` | 422 | `customFields` do not pass the JSON Schema of the task type, template, or workspace. | Check the fields against the schema (`details`). |
| `empty_update` | 422 | PATCH without fields. | Pass at least one field. |
| `if_match_required` | 428 | The operation requires the `If-Match` header (optimistic locking). | Read the entity and pass its `ETag` of the form `"task-<version>"`. |
| `internal_error` | 500 | Unhandled server error; the stack trace is only in the log. | Find the log entry by `requestId`. |
| `invalid_document` | 422 | The field must be a JSON object. | Pass an object. |
| `invalid_field` | 422 | The field is passed in an invalid form (for example, `null` where `{}` is required). | See `details.field`. |
| `invalid_if_match` | 400 | `If-Match` is not in the `"<entity>-<version>"` format. | Pass the `ETag` value unchanged. |
| `invalid_json_schema` | 422 | Invalid JSON Schema (for example, a `$ref` not into the same document). | Keep only local `$ref`s. |
| `invalid_limit` | 422 | `limit` is out of the allowed range. | Reduce `limit`. |
| `invalid_priority` | 422 | Unknown priority. | `critical`, `high`, `medium`, `low`. |
| `invalid_request` | 400 | The body or parameters do not match the API contract (pydantic errors, up to 20 in `details.errors`). | Fix the request using `details.errors[].loc`. |
| `invalid_sort` | 422 | Unknown `sort` value. | Use a supported sort key. |
| `invalid_status` | 422 | Unknown status value in a filter or body. | Check against the statuses of the task type / entity. |
| `invalid_status_category` | 422 | Unknown status category in a filter. | `backlog`, `active`, `blocked`, `terminal_success`, `terminal_cancelled`. |
| `method_not_allowed` | 405 | The route does not support the method. | Check the method against OpenAPI (`/openapi.json`). |
| `non_canonical_value` | 422 | An invalid value in a canonical document (for example, a floating-point number). | Pass integers or strings. |
| `not_found` | 404 | The entity is not found or not visible to the caller (including another tenant). | Check the id and the token's tenant. |
| `payload_too_deep` | 422 | The JSON document is nested deeper than the limit. | Simplify the structure. |
| `payload_too_large` | 422 | A string or document is longer than the limit. | Shorten the value. |
| `rate_limited` | 429 | Request limit exceeded. | Retry with a delay. |
| `request_too_large` | 413 | The body is larger than `CP_MAX_BODY_BYTES` (for knowledge snapshots, `CP_KNOWLEDGE_SNAPSHOT_MAX_BODY_BYTES`). | Reduce the body or raise the limit. |
| `secret_material_rejected` | 422 | A value that looks like a secret was found in the configuration or fields. | Keep the secret outside the core and pass an opaque `secretRef`. |
| `unavailable` | 503 | The service is temporarily not ready. | Retry later; check `/health/ready`. |
| `version_conflict` | 409 | The version in `If-Match` is stale: someone else changed the entity. | Reread the entity and retry with the new version. |

### Authentication and authorization

| Code | HTTP | Cause | What to do |
|---|---|---|---|
| `already_bootstrapped` | 409 | The tenant is already initialized. | No repeated bootstrap is needed. |
| `authorization_unavailable` | 503 | The decision of the external PDP could not be obtained (SDK). | Check that the PDP is available. |
| `bootstrap_disabled` | 403 | `CP_BOOTSTRAP_TOKEN` is not set, so bootstrap is off. | Set the token and restart the API. |
| `decision_unavailable` | 503 | The external decision (PDP) is unavailable; the request was not executed (fail closed). | Check the PDP and `CP_POLICY_BASE_URL`; retry. |
| `delegation_required` | 403 | No active delegation allows acting on behalf of this principal. | Create a delegation (`delegations.manage`). |
| `entitlement_unavailable` | 503 | The licensing service is unavailable and the cache is stale. | Check the service; retry. |
| `iam_identity_bound_elsewhere` | 409 | The IAM identity is already linked to another tenant. | Use a separate identity per tenant. |
| `insufficient_scope` | 403 | The token scope does not cover the operation (SDK check). | Exchange the PAT with the required scope. |
| `invalid_credentials` | 401 | No credential, or it is invalid: malformed, expired, foreign issuer/audience, revoked, missing or disabled binding. The reason is written only to the audit trail. | Reissue the token by exchanging the PAT; check the binding and `CP_IAM_ISSUER`. |
| `invalid_delegation` | 422 | The delegation is invalid (for example, `agentPrincipalId` is not an agent). | Fix the delegation parties. |
| `invalid_display_name` | 422 | Empty `displayName`. | Set a name. |
| `invalid_kind` | 422 | Unknown principal kind. | `human`, `agent`, `service`. |
| `invalid_permissions` | 422 | Unknown permissions, or a non-admin creates an admin key. | Check against the list of permissions. |
| `invalid_requirement` | 422 | Invalid reference in requirements (skill `name` or `name@version`). | Fix `requirements`. |
| `not_eligible` | 403 | The principal does not meet the task requirements (role/capability/skill) or cannot decide this approval. | Assign the required role/capability or choose another executor. |
| `not_entitled` | 403 | The product or feature is not licensed (entitlement). | Grant a license or disable `CP_ENTITLEMENT_ENABLED`. |
| `permission_denied` | 403 | A permission is missing (`details.required`), or the PDP denied (`details.reasonCode`, `decisionId`). | Grant the permission in the binding or a role in the external PDP; check the token scope. |
| `permission_escalation` | 403 | An attempt to grant permissions the calling credential does not have. | Grant only your own permissions, or act as an administrator. |
| `permissions_not_allowed_for_kind` | 422 | `admin` or `approvals.decide` for a principal of kind `agent`/`service`. | Remove the human-only permissions. |
| `policy_unavailable` | 503 | `CP_AUTHZ_MODE=policy`: the external PDP did not answer, there is no decision; the request is not executed (fail closed). | Restore the PDP or switch back to `CP_AUTHZ_MODE=local`. |
| `principal_not_active` | 403, 422 | The principal is not active (403 on sign-in, 422 when binding an identity). | Activate the principal. |
| `unknown_requirement` | 422 | A role or capability from the requirements is not found in the task scope. | Create the role in the task's workspace. |
| `verification_unavailable` | 503 | Nothing to verify the token with: JWKS has been unavailable longer than `CP_IAM_JWKS_STALE_AFTER_SECONDS`, or the revocation source is unavailable. | Check that `iam-service` is reachable from the container. |

### Disabling and enabling a principal { #principal-disable-enable }

`POST /api/v1/principals/{principal_id}:disable` and `:enable` (CP-ADR-0077). The gate
`POST /api/v1/authz:check` returns the same denials for the `disable` and `enable` actions on
the `principal` resource: the response's `reason.code` carries the endpoint's code.

| Code | HTTP | Cause | What to do |
|---|---|---|---|
| `permission_denied` | 403 | The `principals.write` permission is missing. | Grant the permission in the binding. |
| `principal_kind_not_disableable`, `principal_kind_not_enableable` | 422 | The target is a service account (`service`). | A service is switched off by its installer. |
| `cannot_disable_self` | 409 | An attempt to disable yourself. | Another person with the permissions disables you. |
| `permission_escalation` | 403 | `:disable`: the target has `admin` in an unrevoked binding or API key, and the caller has no `admin` (`details.missing=["admin"]`). `:enable`: the permissions of the target's live keys and unrevoked bindings exceed the caller's (`details.missing`). | Act as an administrator. |
| `use_agent_retire` | 409 | `:disable`: the target is the principal of a registry agent (`details.agent`). | Retire the agent with `POST /api/v1/agents/{key}:retire`. |
| `use_agent_publish` | 409 | `:enable`: the target is the principal of a registry agent in any status (`details.agent`, `details.agentStatus`). | Bring the agent back by publishing a revision. |

Repeating the call on an already disabled (`:disable`) or already active (`:enable`) principal
returns `200` without changes.

### Idempotency

| Code | HTTP | Cause | What to do |
|---|---|---|---|
| `idempotency_in_flight` | 409 | The same request is still running and the wait timed out (`CP_IDEMPOTENCY_WAIT_TIMEOUT_SECONDS`). | Retry later with the same key. |
| `idempotency_key_required` | 400, 422 | The operation requires `Idempotency-Key` (1..200 characters). 400 for skill invocations, 422 for runs and child handles. | Pass a unique key for each logical operation. |
| `idempotency_key_reuse` | 409 | The key already names another skill invocation. | Use a new key for a new invocation. |
| `idempotency_key_reused` | 409 | The key was already used with a different body or a different principal. | Generate a new key. |
| `invalid_idempotency_key` | 422 | The key has an invalid length. | 1..200 characters. |

### Sessions and claims

| Code | HTTP | Cause | What to do |
|---|---|---|---|
| `claim_expired` | 409 | The claim lease has expired. | Claim the task again. |
| `claim_holder_mismatch` | 403 | Another principal holds the claim. | Do not write to someone else's task; `claims.manage` is for an administrator. |
| `claim_not_active` | 409 | The claim is not active (released or stale). | Reread the context; claim the task again. |
| `claim_not_expired` | 409 | Reclaim of a live claim. | Wait for it to expire or release the claim. |
| `invalid_harness` | 422 | `harness.type` is not in the client identifier format. | Lowercase letters, digits, `.`, `_`, `-`. |
| `invalid_ttl` | 422 | TTL outside the `CP_*_TTL_MIN/MAX_SECONDS` bounds. | Request a TTL within the allowed range. |
| `session_expired` | 409 | The session lease has expired. | Open a new session, then claim the task again. |
| `session_not_active` | 409 | The claim's session is no longer alive. | Open a session and reread the context. |
| `session_owner_mismatch` | 403 | The session belongs to another principal. | Use your own session. |
| `stale_claim` | 409 | Fencing rejected the operation: the process no longer owns the task (the claim was taken over, is stale, or `fencingToken` is wrong). | Stop writing, reread the context (`/api/v1/harness/context`), and claim the task again if needed. |
| `task_already_claimed` | 409 | The task already has an active claim. | Choose another task or wait for release. |
| `task_claimed` | 409 | Changing a task with an active claim without `claimId` and `fencingToken`. | Pass the `claimId` and `fencingToken` of your claim. |
| `task_not_claimable` | 422 | The task status does not allow a claim. | Move the task to a working status. |
| `task_not_ready` | 409 | Blocking dependencies (`blocks`/`depends_on`) are not complete. | Complete the dependencies. |
| `unsupported_protocol_version` | 422 | The harness protocol version is not supported. | Use `control-harness/2` (`1` and `2` are supported). |

### Runs and execution

| Code | HTTP | Cause | What to do |
|---|---|---|---|
| `action_already_finished` | 409 | The action is already finished. | Do not finish it again. |
| `agent_revision_mismatch` | 422 | `:start-run`: the revision does not belong to the caller's agent, or a principal without an agent passed it. | Pass a revision of your own agent (`GET /agents/me`) or omit the field. |
| `agent_revision_required` | 422 | `:start-run` from a principal linked to an agent without `agentRevisionId`. | Pass a revision of your own agent (`GET /agents/me`). |
| `artifact_mismatch` | 422 | The run does not belong to the specified task. | Check `taskId` and `runId`. |
| `budget_exceeded` | 409 | The run exceeded its duration budget. | Finish the run; increase `maxDurationSeconds` for a new one. |
| `invalid_action` | 422 | Empty action name. | Set `action`. |
| `invalid_budget` | 422 | The budget is not positive. | `maxDurationSeconds > 0`. |
| `invalid_checkpoint` | 422 | Empty checkpoint `kind`. | Set `kind`. |
| `invalid_handoff` | 422 | A handoff to a human requires `reason=human_harness_handoff` and `kind=handoff`. | Fix the handoff fields. |
| `invalid_name` | 422 | Empty artifact name. | Set `name`. |
| `invalid_type` | 422 | Empty artifact type. | Set `type`. |
| `run_already_active` | 409 | The claim already has a running run. | Finish the current run. |
| `run_cancel_requested` | 409 | The run accepted cooperative cancellation and cannot start new actions. | Finish the run. |
| `run_holder_mismatch` | 403 | The operation requires the run holder (or `claims.manage`). | Act as the principal that holds the run. |
| `run_id_required` | 403 | The caller executes a restricted child run and must specify `runId`. | Pass `runId`. |
| `run_in_progress` | 409 | The task has an active run. | Finish the run with `:succeed`, `:fail`, or `:cancel`. |
| `run_not_active` | 409 | The run is not in the `running` state. | Reread the run; start a new one. |
| `run_owner_mismatch` | 403 | The run belongs to another principal. | Act with your own run. |
| `run_version_conflict` | 409 | `expectedRunVersion` does not match. | Reread the run. |
| `task_not_runnable` | 422 | The task status does not allow starting a run. | Move the task to a working status. |
| `tool_not_authorized` | 403 | The skill or tool is not allowed for this run. | Assign the skill to the principal or the task. |
| `unsafe_handoff_payload` | 422 | The handoff checkpoint contains absolute local paths or sensitive keys. | Remove the paths and secrets. |

### Run controls

| Code | HTTP | Cause | What to do |
|---|---|---|---|
| `control_message_out_of_order` | 409 | There is an earlier accepted control message without an outcome. | Acknowledge the previous one first. |
| `control_message_terminal` | 409 | The message is already resolved. | Do not acknowledge it again. |
| `control_message_version_conflict` | 409 | `expectedMessageVersion` does not match. | Reread the message. |
| `invalid_control_message` | 422 | A field is not allowed for the operation (for example, `directive` instead of `reason`). | Fix the body. |
| `invalid_control_operation` | 422 | Unknown operation. | `queue`, `steer`, `redirect`, `request_cancel`, `force_cancel`. |
| `invalid_control_status` | 422 | Unknown acknowledgment status. | `applied`, `rejected`, `superseded`. |
| `unsafe_control_payload` | 422 | The message contains absolute local paths. | Remove the paths. |

### Child runs (child handles)

| Code | HTTP | Cause | What to do |
|---|---|---|---|
| `child_depth_exceeded` | 422 | The nesting depth of child runs is exceeded. | Simplify the decomposition. |
| `child_grant_exceeded` | 403 | The run is limited by a child handle that does not grant this permission. | Widen the grant when issuing the handle (within the parent's limits). |
| `child_grant_exceeds_parent` | 422 | The requested grant exceeds the parent's ceiling. | Narrow the grant. |
| `child_handle_expired` | 409 | The child handle has expired. | Issue a new one. |
| `child_handle_revoked` | 409 | The child handle was revoked. | Issue a new one. |
| `child_result_too_large` | 422 | The run has too many artifacts for the result. | List the ones you need in `output.artifactRefs`. |
| `child_run_already_bound` | 409 | The handle already has a running run. | Wait for it to finish. |
| `invalid_cancellation_policy` | 422 | Unknown cancellation policy. | Check against the API. |
| `invalid_child_expiry` | 422 | `expiresInSeconds` exceeds the limit. | Reduce the lifetime. |
| `invalid_child_grant` | 422 | Only permissions, capabilities, skills are allowed in a grant. | Fix the grant. |
| `invalid_child_handle_ref` | 422 | A handle id or a `ch1_…` token was expected. | Pass a valid reference. |
| `invalid_child_handle_token` | 422 | The token is not in the `ch1_<id>_<secret>` format. | Pass the token unchanged. |
| `invalid_child_result` | 422 | `artifactRefs` must be artifact ids. | Fix the result. |
| `invalid_correlation_id` | 422 | `correlationId` does not match `^[A-Za-z0-9._:-]{1,128}$`. | Fix the value. |

### Tasks, relations, comments, types

| Code | HTTP | Cause | What to do |
|---|---|---|---|
| `comment_mismatch` | 422 | The artifact does not belong to the comment's task. | Check the references. |
| `dependency_cycle` | 422 | The relation would create a dependency cycle. | Revise the dependency graph. |
| `external_reference_conflict` | 409 | The external identifier is already linked to another entity. | Check `externalSystem`/`externalId`. |
| `invalid_comment_body` | 422 | Empty comment text. | Provide text. |
| `invalid_entity_reference` | 422 | Invalid `entityId`. | Fix the value. |
| `invalid_entity_type` | 422 | Unknown entity type. | Check against the API. |
| `invalid_external_lookup` | 422 | Either `entityType`+`entityId` or `externalSystem`+`externalId` is required. | Fix the request. |
| `invalid_external_reference` | 422 | Invalid length of an external reference field. | Shorten the value. |
| `invalid_lifecycle_schema` | 422 | The task type lifecycle is invalid. | See `details.path`. |
| `invalid_planned_dates` | 422 | `startDate` is later than `dueDate`. | Fix the dates. |
| `invalid_relation` | 422 | A relation of a task to itself. | Specify another task. |
| `invalid_relation_type` | 422 | Unknown relation type. | `parent`, `blocks`, `depends_on`, `spawned_by`, `related_to`. |
| `invalid_task_execution` | 422 | The task's `execution` description is invalid (skill, version, input paths). | See `details`; pin the skill version. |
| `invalid_template` | 422 | The project template is invalid (for example, too many default views). | Fix the template. |
| `invalid_template_reference` | 422 | `templateVersion` without `templateKey`/`templateId`. | Specify the template. |
| `invalid_title` | 422 | Empty task title. | Set `title`. |
| `invalid_transition` | 422 | The task type does not declare this status transition. | Take the allowed transitions from `GET /tasks/{ref}/transitions`. |
| `not_comment_author` | 403 | Only the author can edit a comment. | — |
| `relation_exists` | 409 | This relation already exists. | — |
| `status_not_in_lifecycle` | 422 | The type's lifecycle does not declare the status. | Use the type's statuses. |
| `system_task_type_required` | 422 | The tenant must keep an active version of the system task type. | Do not retire the system type. |
| `task_already_completed` | 409 | The task is already completed. | — |
| `task_cancelled` | 422 | A cancelled task cannot be completed. | Create a new task. |
| `template_deprecated` | 422 | A deprecated template cannot be used for a new project. | Use the active version. |

### Goals, acceptance, and evidence (work graph)

| Code | HTTP | Cause | What to do |
|---|---|---|---|
| `duplicate_check_key` | 422 | A repeated check key in acceptance. | Make the keys unique. |
| `duplicate_evidence` | 422 | Repeated evidence. | Remove the duplicate. |
| `goal_abandoned` | 422 | Work cannot be linked to an abandoned goal. | Choose an active goal. |
| `goal_cycle` | 422 | The new parent is a descendant of this goal. | Choose another parent. |
| `goal_too_deep` | 422 | The goal hierarchy is deeper than the limit. | Reduce nesting. |
| `goal_workspace_mismatch` | 422 | The task's goal is from another workspace. | Relink or unlink the goal. |
| `invalid_acceptance` | 422 | Invalid acceptance criteria. | See `details.field`. |
| `invalid_desired_state` | 422 | Invalid desired state of the goal. | See `details.field`. |
| `invalid_evidence` | 422 | Invalid evidence. | See `details.field`. |
| `invalid_goal_status` | 422 | Unknown goal status. | Check against the API. |
| `invalid_origin` | 422 | Invalid `origin`. | See `details.field`. |
| `unknown_acceptance_check` | 422 | Evidence refers to a check that is not in acceptance. | Check the check keys. |

### Workspaces, projects, configuration

| Code | HTTP | Cause | What to do |
|---|---|---|---|
| `child_type_not_allowed` | 422 | The parent does not allow the child workspace type. | Check `allowedChildTypes`. |
| `governance_not_in_settings` | 422 | Governance is set only through a versioned configuration revision. | Use a revision. |
| `governance_weakened` | 422 | The new hierarchy weakens an ancestor's governance. | — |
| `invalid_config` | 422 | Invalid project configuration. | See `details`. |
| `invalid_governance` | 422 | Invalid governance section. | See `details.path`. |
| `invalid_project_request` | 422 | `workspaceId` or `workspaceSlug` is required. | Fix the request. |
| `invalid_workspace_type` | 422 | Invalid `allowedChildTypes`. | Type keys or `*`. |
| `project_archived` | 422 | An archived project does not activate configuration revisions. | — |
| `project_exists` | 409 | The workspace already has a project profile. | — |
| `setting_locked` | 422 | The hierarchy would lock settings that the project already overrides. | Remove the overrides. |
| `system_type_immutable` | 422 | The system workspace type must accept any child types. | — |
| `unknown_config_section` | 422 | Unknown configuration section. | Remove the section. |
| `unknown_governance_field` | 422 | Unknown governance field. | Remove the field. |
| `workspace_archived` | 422 | An archived workspace does not accept a project profile. | Unarchive it or choose another. |
| `workspace_cycle` | 422 | Moving a workspace under its own descendant. | Choose another parent. |
| `workspace_has_active_children` | 422 | The workspace has active children. | Archive or move the children. |
| `workspace_has_active_project` | 422 | The workspace has an active project. | Archive the project first. |
| `workspace_slug_conflict` | 409 | A sibling workspace with this slug already exists. | Choose another slug. |
| `workspace_type_archived` | 422 | The workspace type is archived. | Choose an active type. |
| `workspace_type_exists` | 409 | A type with this key already exists. | — |
| `workspace_type_in_use` | 422 | Active workspaces use the type. | Move them to another type. |

### Approvals

| Code | HTTP | Cause | What to do |
|---|---|---|---|
| `approval_already_decided` | 409 | The approval is no longer `pending`. | — |
| `approval_already_used` | 409 | The approval already authorized an invocation of this skill version. | Request a new approval. |
| `approval_required` | 409 | The task is waiting for a decision on a gate approval. | Wait for the human decision. |
| `credential_inactive` | 403 | The credential used to make the decision is no longer active. | Make the decision again. |
| `invalid_action_input` | 422 | The input of an outcome action does not pass the schema. | See the message. |
| `invalid_approval` | 422 | Exactly one of `requiredRoleId` and `assignedPrincipalId` is required. | Fix the request. |
| `invalid_approval_schema` | 422 | Unsupported expression in the approval outcome schema. | See `details`. |
| `outcome_not_replayable` | 409 | Only a failed or stuck outcome can be replayed. | — |

### Catalog, skills, and invocations

| Code | HTTP | Cause | What to do |
|---|---|---|---|
| `capability_exists` | 409 | A capability with this name already exists. | — |
| `execution_already_invoked` | 409 | The run has already made its execution invocation. | — |
| `invalid_executor_endpoint` | 422 | Invalid executor endpoint. | Check against the allowed origins. |
| `invalid_protocol` | 422 | Unknown skill protocol, or the executor declared an invalid one. | `http`, `local`, `mcp`. |
| `invalid_skill_contract` | 422 | The skill contract is invalid. | See `details.field`. |
| `invalid_skill_inputs` | 400 | The inputs do not match the skill's input schema. | Fix `inputs`. |
| `invalid_status_transition` | 409 | A skill status changes only `active → deprecated → disabled`. | — |
| `invocation_mismatch` | 422 | The run does not belong to the invocation's task. | Check the references. |
| `invocation_terminal` | 409 | The invocation is already finished. | — |
| `role_slug_conflict` | 409 | A role with this slug already exists in this scope. | Choose another slug. |
| `skill_disabled` | 422 | A disabled skill cannot be assigned. | — |
| `skill_exists` | 409 | A skill with this name and version already exists. | Publish a new version. |
| `skill_not_invocable` | 409 | The core cannot invoke this skill version (the protocol is not `http`/`local`/`mcp`). | Publish a version with a supported protocol. |
| `skill_permission_denied` | 403 | The caller lacks the permissions the skill requires. | Grant the skill's `requiredPermissions`. |
| `skill_side_effect_not_authorized` | 403 | A skill with `external_write` requires an approved gate on the task. | Get an approval. |
| `skill_version_immutable` | 409 | A published skill version cannot be changed. | Publish a new version. |
| `stale_invocation_lease` | 409 | The executor no longer holds the invocation lease. | Stop working on the invocation. |
| `task_terminal` | 409 | A skill with `external_write` cannot act for a closed task. | — |
| `unsupported_skill_condition` | 422 | Skill conditions of this kind are not supported yet. | Remove the condition. |

### Tool search

| Code | HTTP | Cause | What to do |
|---|---|---|---|
| `invalid_tool_query` | 422 | The tool search query is too long. | Shorten it. |
| `invalid_tool_schema` | 422 | A tool's input schema must be an object. | Fix the schema. |

### Events and operations

| Code | HTTP | Cause | What to do |
|---|---|---|---|
| `cursor_below_journal_floor` | 422 | The cursor is older than the retained part of the log. | Rebuild the state from the start of the available log. |
| `cursor_must_not_advance` | 422 | A rebuild can only move the cursor backward. | — |
| `invalid_cursor` | 422 | Invalid event or page cursor. | Pass the cursor unchanged. |
| `retention_blocked_by_consumer` | 409 | No consumer cursor: delivery is not confirmed, so the log cannot be pruned. | Wait for the consumers. |
| `unsupported_cursor_version` | 422 | The server does not support the cursor version. | Start reading again. |

### Memory and knowledge

| Code | HTTP | Cause | What to do |
|---|---|---|---|
| `invalid_context_request` | 422 | Invalid context request (for example, `maxTokens ≤ 0`). | Fix the request. |
| `memory_disabled` | 503 | The memory provider is not configured (`CP_CONTEXT_PROVIDER=none`). | Enable the `http` provider. |
| `memory_unavailable` | 502 | memory-service did not process the request (5xx, transport, 401/403 for the core identity); `details.memoryStatus`, `details.retryable`. | Check memory and the core credential (`CP_CONTEXT_AUTH`). |
| `observation_invalid` | 422 | The observation is invalid (for example, `source` does not match the pattern). | See the message. |
| `pack_invalid` | 422 | Memory rejected the knowledge pack manifest. | Fix the manifest. |
| `pack_version_conflict` | 409 | This pack version is already registered with different content. | Publish a new version. |
| `pack_version_required` | 422 | Knowledge packs are enabled with a pinned `name@version` reference. | Specify the version. |
| `snapshot_invalid` | 422 | Memory rejected the source snapshot. | Fix the snapshot. |
| `snapshot_stale` | 409 | Memory already has a newer snapshot of this source. | Send the current snapshot. |
| `workspace_not_root` | 422 | Knowledge packs are set on the root workspace of the tree. | Specify the root workspace. |
### Client library and CLI codes

These codes come not from the server but from `control_plane_client` (used by
the runner, the CLI, the MCP server, connectors) before or instead of calling
the server. They arrive as `ControlPlaneError.code`.

| Code | Cause | What to do |
|---|---|---|
| `transport_error` | Network error: the request may or may not have been executed. | Retry only with the same `Idempotency-Key` (the client does this itself for idempotent commands). |
| `iam_url_required` | `CONTROL_PLANE_IAM_URL` is not set when an IAM credential is created explicitly. | Set the IAM address. |
| `iam_tenant_required` | `CONTROL_PLANE_IAM_URL` is set, but `CONTROL_PLANE_IAM_TENANT` is not. | Set the tenant. |
| `iam_unreachable` | IAM is unavailable during PAT exchange. | Check the network and the IAM address. |
| `iam_invalid_token` | IAM rejected the PAT (401): revoked, expired, unknown. | Reissue the PAT (`iam auth login` or issuance by an administrator). |
| `iam_audience_not_allowed` | IAM returned 403 on exchange: the audience or scope is outside the PAT ceiling. | Check the PAT's audiences and `scopeCeiling` against `CONTROL_PLANE_IAM_AUDIENCE`/`…_SCOPES`. |
| `iam_exchange_failed` | Another IAM denial during exchange (≥ 400). | See the IAM log. |
| `iam_exchange_malformed` | The exchange response lacks `accessToken`/`expiresIn` or has an empty token. | Check the IAM version. |
| `iam_not_authenticated` | The machine has no PAT for this IAM URL + tenant pair (or an explicitly passed PAT is empty). | Sign in or put the PAT into the store. |
| `iam_credential_ambiguous` | The store has several credentials for one IAM URL + tenant pair, and the process has not declared itself. | Set `IAM_PRINCIPAL=<principal-id>` for the process. |
| `iam_environment_mode_required` | `IAM_PLATFORM_ACCESS_TOKEN` is set without `IAM_CREDENTIAL_MODE=environment` (or `ci`). | Add the mode: an inherited variable must not silently replace the account. |
| `iam_credentials_file_permissions` | `~/.config/iam/credentials.json` is accessible to users other than the owner. | `chmod 600`. |
| `iam_credentials_file_unreadable` | The credentials file cannot be read or is not JSON. | Restore the file. |
| `not_configured` | MCP server: no `CONTROL_PLANE_SERVER` and no `.control-plane/config.json`. | Set the server. |
| `not_authenticated` | MCP server: neither an IAM identity nor a legacy key. | Configure IAM (`iam auth login`). |
| `invalid_harness_configuration` | `CONTROL_PLANE_HARNESS_TYPE` is not in the identifier format. | Fix the value. |

The client maps server codes to typed exceptions:
`stale_claim` → `StaleClaimError`; `task_already_claimed`, `task_claimed`,
`claim_not_expired` → `ClaimConflictError`; `task_not_ready` →
`TaskNotReadyError`; `approval_required` → `ApprovalRequiredError`;
`not_eligible` → `NotEligibleError`; `session_expired`,
`session_not_active` → `SessionExpiredError`; `version_conflict` →
`VersionConflictError`; `idempotency_key_reused`, `idempotency_in_flight` →
`IdempotencyConflictError`; `budget_exceeded` → `BudgetExceededError`;
`run_not_active` → `RunNotActiveError`; `task_cancelled` →
`CancelledError`; `invalid_credentials` → `AuthenticationError`;
`permission_denied` → `PermissionDeniedError`; `not_found` →
`NotFoundError`. The rest map by HTTP status.

## iam-service

The response is `{"detail": "<code>"}`.

### Tokens and exchange

| Code | HTTP | Endpoint | Cause | What to do |
|---|---|---|---|---|
| `invalid_token` | 401 | PAT: `…:exchange`, introspect, self-revoke | The PAT is unknown, has a wrong secret, is revoked or expired; the tenant, membership, or principal is inactive. The exact reason is in the audit trail. | Reissue the PAT; check the principal status. |
| `audience_not_allowed` | 403 | PAT exchange, client credentials, federation | The audience is not in the credential's list or is not active in the tenant. | Issue a PAT for the required audience; register the audience in IAM. |
| `scope_not_allowed` | 403 | exchange | The requested scopes are outside the credential ceiling or the audience's `allowedScopes`. A common cause is a scope without the prefix (`read` instead of `control-plane:read`). | Request scopes with the audience prefix within the ceiling. |
| `invalid_client` | 401 | `POST /api/v1/tokens/exchange` | Unknown or revoked client, wrong secret, inactive membership/principal. | Reissue the service account. |
| `human_principal_required` | 422 | federation, authentication context, PAT issuance for a human | The operation is available only to a principal of kind `human`. | — |

### PAT issuance and management

| Code | HTTP | Cause | What to do |
|---|---|---|---|
| `idempotency_key_required` | 400 | PAT issuance without the `Idempotency-Key` header. | Pass a unique key. |
| `authentication_context_required` | 403 | There is no authentication context for the human. | Create a context (`POST …/principals/{id}/authentication-contexts`) and issue right away. |
| `authentication_context_expired` | 403 | The context is older than `IAM_PAT_MAX_AUTHENTICATION_AGE_SECONDS` (300 s). | Create a fresh context. |
| `principal_kind_not_allowed` | 422 | A PAT is issued only to `human` and `agent`, not to `service_account`. | Use client credentials for services; set up a service agent with kind `agent`. |
| `invalid_scope_ceiling` | 422 | The PAT ceiling is wider than the `allowedScopes` of its audiences. | Narrow `scopeCeiling`. |
| `expiry_too_long` | 422 | The lifetime exceeds `IAM_PAT_MAX_TTL_SECONDS` (365 days). | Reduce `expiresInSeconds`. |
| `unknown_audience` | 422 | The audience of the PAT (or service account) is not registered or not active in the tenant. | Register the audience. |
| `principal_not_found` | 404 | No such principal. | — |
| `principal_not_active` | 409 | The principal is not active. | Activate it. |
| `credential_not_found` | 404 | No credential to rotate/revoke. | — |
| `credential_not_active` | 409 | Rotation of a revoked or expired PAT. | Issue a new one: rotation does not extend the lifetime. |
| `credential_conflict` | 409 | A concurrent write of the same credential. | Retry with the same `Idempotency-Key`. |
| `credential_exists` | 409 | Migrating a legacy key that has already been migrated. | — |
| `invalid_credential_material` | 422 | Legacy key migration: wrong prefix or hash. | — |
| `compatibility_window_too_long` | 422 | The window of a migrated legacy key exceeds `IAM_LEGACY_CREDENTIAL_MAX_TTL_SECONDS`. | Reduce the lifetime. |

### Tenant administration

| Code | HTTP | Cause |
|---|---|---|
| `unauthorized` | 401 | A bootstrap endpoint without a valid `X-IAM-Bootstrap-Token` (the `Authorization: Bearer` header does not work). |
| `tenant_not_found` | 404 | No tenant. |
| `tenant_id_exists` | 409 | A tenant with the given `id` already exists. |
| `tenant_slug_exists` | 409 | A tenant with this slug already exists. |
| `audience_exists` | 409 | The audience is already registered. |
| `audience_not_found` | 404 | No audience (PATCH). |
| `invalid_scope` | 422 | An empty scope or one longer than 120 characters in the audience's `allowedScopes`. |
| `service_account_not_found` | 404 | No service account. |
| `group_not_found`, `group_exists`, `group_membership_exists` | 404, 409, 409 | Groups. |
| `group_is_federated` | 409 | The group is managed by federation. |
| `identity_provider_not_found`, `identity_provider_exists` | 404, 409 | Identity provider. |
| `identity_provider_managed` | 409 | The external identity cannot be linked manually: its issuer is served by an active provider with the `read_only` profile. |
| `invalid_issuer` | 422 | Invalid provider issuer. |
| `external_identity_exists` | 409 | The external identity is already linked. |
| `service_account_required`, `service_principal_required` | 422 | The SCIM source must be a service account. |
| `provisioning_source_exists` | 409 | The SCIM source is already registered. |
| `population_managed_by_directory` | 409 | The principal population is managed by the directory (SCIM). |

### Disabling and enabling people { #iam-people }

`POST /api/v1/tenants/{tenant_id}/principals/{principal_id}:disable` and `:enable` (scope
`iam:people`).

| Code | HTTP | Cause |
|---|---|---|
| `human_principal_required` | 422 | With `iam:people`, only people are disabled and enabled. |
| `self_disable_forbidden`, `self_enable_forbidden` | 409 | An attempt to disable or enable yourself. |
| `people_admin_protected` | 403 | `:disable`: the target is a member of the `people-admins` group; only the IAM bootstrap disables it, the caller's membership does not count. `:enable`: the target belongs to an IAM privilege group (for example, `people-admins`) that the caller is not a member of; a member of the same group or the IAM bootstrap enables it. |
| `principal_paused` | 409 | `:enable`: the principal is paused by another process; `:enable` does not lift that. |
| `principal_provisioned` | 409 | `:enable`: the person was disabled by the SCIM source; only that source enables them (`active: true`). |
| `principal_status_not_enableable` | 409 | `:enable`: a principal cannot be enabled from this status. |
| `principal_conflict` | 409 | `:enable`: the principal's status changed concurrently; re-read and retry. |
| `idempotency_key_required` | 400 | `:enable` with a token and without the `Idempotency-Key` header (the bootstrap token does not need the key). |
| `idempotency_key_reused` | 409 | `:enable`: the caller has already used this `Idempotency-Key` for another principal. |

### Identity federation

| Code | HTTP | Cause |
|---|---|---|
| `invalid_token`, `invalid_signature`, `token_expired`, `invalid_issuer`, `invalid_audience`, `unknown_signing_key`, `unsupported_algorithm`, `missing_subject_claim` | 401 | The upstream provider's token (external IdP) failed verification. |
| `step_up_required` | 403 | Stronger authentication is required (`acr`/`amr`). |
| `identity_disabled`, `principal_disabled`, `principal_not_in_tenant` | 403 | The external identity or principal is disabled or not in the tenant. |
| `external_identity_conflict` | 409 | Conflict when linking an external identity. |
| `identity_provider_unavailable` | 503 | The provider's JWKS is unavailable. |

### SCIM

SCIM endpoints respond in the SCIM format (`scimType`): `invalidFilter`,
`invalidValue`, `invalidSyntax`, `uniqueness` (400/404/409), 412 on an
`If-Match` mismatch, 401 without a token or with a token not for
`IAM_SCIM_AUDIENCE`, 403 without the `IAM_SCIM_SCOPE` scope or without an
active provisioning source, 502/503 when the upstream provider is
unavailable.

## Console: people { #console-people }

The console flows "Settings" → "People and roles" and the person page (add, disable,
enable a person) are orchestration by the console BFF over IAM and the core. The response
takes one of two forms.

- **Rejection of the request body**: an immediate `422` in the Control Plane envelope
  `{"error": {"code"}}`; the flow does not start: `invalid_person` ("Add"),
  `invalid_permissions` ("Enable").
- **Flow report**: `200`, with the denial inside the report:
    - "Disable" and "Enable": the top-level `error` field is
      `{"service": "iam"|"cp", "status", "code", "missing"?}`, and the step fields (`iam`, `cp`,
      plus `binding` for enabling) show where the flow stopped (`failed`);
    - "Add": there is no top-level `error`; the denial is in the flow step with `status: "failed"`:
      `steps[i].error = {"status", "code", "missing"?}`, without `service`.

Besides the IAM and core codes (see [above](#principal-disable-enable) and
[iam-service](#iam-people)), the BFF returns its own:

| Code | HTTP | Cause | What to do |
|---|---|---|---|
| `iam_login_closed` | 403 | "Enable": the core participant is active, but IAM sign-in is closed (partial disabling), and the caller has no `admin`. Only an administrator can reopen sign-in, and not when IAM responds with `principal_provisioned` (disabled by HR sync, SCIM) or `principal_paused` (paused in IAM): an administrator gets these denials too. | Repeat "Enable" as an administrator. |
| `iam_principal_unknown` | 409 | "Enable": the core principal has no binding rows with this console's IAM, so there is nothing to put a new binding on. | Enable through the core API: `:enable`, then the binding `POST /api/v1/principals/{principal_id}/iam-bindings` with explicit permissions. |
| `invalid_permissions` | 422 | "Enable": the permissions of the new binding are not a non-empty list of core permissions. A direct response, not a report. | Choose the previous permissions or a set. |
| `invalid_person` | 422 | "Add": the request body is unusable: an empty or too long field, an invalid e-mail, workspace, or roles, permissions not given as a list. A direct response, not a report. | Fill in the form. |
| `permission_escalation` | 403 | "Add" and "Enable": the chosen permissions exceed the caller's (`missing`). Checked before IAM. | Choose a narrower set or act as an administrator. |
| `person_disabled` | 409 | "Add": the person with this e-mail is disabled, their IAM account is not active, or it is already bound to a disabled core participant. | Bring them back with the "Enable" button. |
| `identity_disabled` | 409 | "Add": the IdP identity is disabled in IAM. | Sort out the identity in IAM. |
| `identity_mismatch` | 409 | "Add": the IdP identity from the form does not match the one already linked to this person, or the IAM principal found by the IdP identity or by the person's record is not a human (`kind` is not `human`). | Check the IdP identifier. |
| `identity_bound_elsewhere` | 409 | "Add": the IAM account is already bound to another active core participant, or the IdP identity is linked to a principal outside the tenant. | Sort out the link in IAM and the core. |
| `identity_unverifiable` | 501, 502 | "Add": IAM does not allow reading the IdP links; the flow is stopped. | Check the IAM version and its response. |
| `lookup_incomplete` | 409 | "Add": the list of core participants is too long to check them all; the console refuses so as not to create a duplicate. | A limitation of the current console version. |

## platform-auth-sdk codes (resource services)

The common deny contract of all resource services that use the SDK. The
client receives only the code; Control Plane carries SDK codes into its own
envelope as is (except `invalid_token`, which becomes `invalid_credentials`).

| Code | HTTP | Cause |
|---|---|---|
| `invalid_token` | 401 | Any token defect (including revocation). |
| `insufficient_scope` | 403 | The token scope does not cover the operation. |
| `not_entitled` | 403 | No license for the product or feature. |
| `permission_denied` | 403 | The domain policy does not allow the operation. |
| `verification_unavailable` | 503 | Nothing to verify the token with (no keys, JWKS stale, revocation source unavailable). |
| `entitlement_unavailable` | 503 | No entitlement decision, the cache is stale. |
| `authorization_unavailable` | 503 | No decision from the external PDP. |
| `denied` | 403 | A base denial without details. |

### Audit reasons {#audit-reasons}

These strings are not returned to the client: they are visible in the audit
trail and the log of the resource service. Use them to investigate
`401 invalid_credentials` / `invalid_token`.

| Reason | Source | Meaning |
|---|---|---|
| `missing_authorization`, `malformed_authorization`, `missing_token` | SDK | No `Authorization: Bearer …` header, or it is malformed. |
| `malformed_token`, `unsupported_algorithm`, `invalid_token` | SDK | The token cannot be parsed or the signature is invalid. |
| `expired` | SDK | `exp` has passed. |
| `issuer_mismatch` | SDK | `iss` does not equal the expected issuer (for example, after changing `TAIMEN_PUBLIC_URL`). |
| `audience_mismatch`, `audience_not_exact` | SDK | The token was issued for another audience, or `aud` is a list. |
| `missing_required_claim`, `missing_exp`, `missing_credential_id` | SDK | A required claim is missing. |
| `unknown_key_id` | SDK | `kid` is not found in JWKS (IAM key rotation). |
| `jwks_stale`, `public_key_not_configured`, `verifier_not_configured` | SDK | Nothing to verify with (→ `verification_unavailable`). |
| `revocation_source_unavailable` | SDK | The revocation source is unavailable beyond the stale window. |
| `credential_revoked` | SDK, IAM | The credential is revoked. |
| `token_ttl_exceeds_revocation_window` | SDK | The token lives longer than the allowed revocation window. |
| `service_credentials_not_configured`, `service_token_exchange_failed`, `service_token_malformed` | SDK | The service's own service account is not configured, or the exchange failed. |
| `quota_reserve_unavailable` | SDK | The entitlement quota reserve is unavailable. |
| `binding_not_found` | Control Plane | No `iam_principal_bindings` row for the pair (issuer, IAM principal). |
| `binding_disabled` | Control Plane | The binding is disabled or revoked. |
| `credential_expired`, `tenant_not_active`, `membership_not_active`, `principal_not_active` | IAM | Reasons for a PAT exchange denial. |

## memory-service

Responses are `{"detail": "<text in Russian>"}`; there are no machine codes,
so rely on the status.

| HTTP | When |
|---|---|
| 400 | Invalid request: the namespace in the query and in the body differ, `namespace` and `scope.namespace` point to different bases, an invalid filter; the knowledge base is not allowed in Console. |
| 401 | Missing or invalid Bearer (`Требуется корректный Authorization: Bearer <key>`, "a valid Authorization: Bearer <key> is required"). |
| 403 | No permissions on the namespace (read/write); no permissions on global statistics; the service scope (`memory:service`) is required for kind packages; the route is available only to the core identity (`CB_CORE_ONLY`/`CB_CORE_IDENTITIES`); the namespace is outside the principal's visibility (policy); a cross-origin request in Console. |
| 404 | Node, source, observation, or trace not found. |
| 409 | Conflict (for example, the source snapshot is older than the stored one). |
| 413 | The observation batch is larger than `CB_OBSERVATIONS_MAX_BATCH`. |
| 429 | Demo showcase request limit. |
| 500 | Internal engine error. |
| 503 | The database is unavailable; IAM token verification is unavailable (JWKS/IAM configuration); the external visibility PDP (if enabled) is unavailable, so visibility is undetermined. |

Control Plane translates memory responses into its own codes:
`memory_unavailable` (502), `snapshot_invalid`, `snapshot_stale`,
`pack_invalid`, `pack_version_conflict`.

## See also

- [Authentication and access: troubleshooting](../troubleshooting/auth.md)
- [Execution and runner: troubleshooting](../troubleshooting/runner.md)
- [Execution: claims and runs](../control-plane/execution.md)
- [Permissions and scopes](permissions.md)
- [Credentials and PAT](../iam/credentials.md)
- [Control Plane API](../control-plane/api.md)
