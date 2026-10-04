
# Operator guide

This section is for the person who manages work in Control Plane: assigns tasks to people
and agents, claims tasks personally, monitors runs, decides approvals, and hands work off
between harnesses. It describes the working surfaces and everyday workflows.

## Who the operator is

An operator is a Control Plane human principal (kind `human`) with a binding that grants
permissions on tasks, claims, runs, approvals, and reading events. Unlike an agent, a person
can hold `approvals.decide` and `admin`: it is a person who decides gates and changes
configuration.

The operator's main rule: **the authoritative state lives in Control Plane**. Tasks, claims,
runs, approvals, checkpoints, artifacts, and events are the single source of truth.
Conversations with an assistant, repository files, and local notes are not. If a transcript
says one thing and Control Plane says another, Control Plane is right.

## Surfaces

| Surface | What it is for | How it talks to Control Plane |
|---|---|---|
| [MCP plugin for Claude Code](mcp-plugin.md) | working on tasks directly from a repository: claim a task, do it in code, record evidence, hand it off | the `control-plane-mcp` MCP server (`cp_*` tools) |
| [Console](console.md) | visibility into a working organization: the pulse and Waiting for you, where work comes from, processes, rules, agents; management actions, packages, people and roles | sign-in through the organization's OIDC IdP and IAM federation; to the core, a short-lived token of the person |
| [Assistant](assistant.md) | a conversation from the console panel and from Telegram: questions about what is on screen, assignments, approval decisions, your own work | the person's own container ([personal workspace](../workplace/index.md)); to the core, the person's PAT; every mutation requires confirmation |

All of them are clients of the same API under the same human identity. You can assign a
task to the assistant, claim it in Claude Code and complete it there, and decide the
approval in the console: the server sees one principal and one set of rules.

```mermaid
flowchart TB
    H(("Operator"))
    H --> P["Claude Code + plugin<br/>control-plane-operator"]
    P -- "MCP → control-plane-mcp<br/>PAT → IAM exchange" --> CP["Control Plane"]
    H --> K["Console<br/>(browser)"]
    K -- "sign-in: OIDC IdP → IAM federation" --> CP
    K -- "assistant panel" --> A["Assistant<br/>(the person's container)"]
    H -- "Telegram" --> A
    A -- "person's PAT → IAM exchange" --> CP
    R["Runner (agents)"] -- "Agent PAT" --> CP
```

## Decisions only a person makes

Regardless of the surface, an assistant or an interface must not, without an explicit
decision by a person:

- create or change tasks, or add and remove relations;
- write or edit comments (they speak on the person's behalf);
- claim a task or start a run;
- prepare a handoff;
- approve or reject approvals;
- complete a task or a run.

This is an interface rule, not a security boundary: the server checks permissions, tenant
isolation, versions, and the fencing token on every call regardless. But it is exactly what
distinguishes an operator harness from an autonomous runner, which claims tasks on its own.

## How to get started

1. Get a human principal and a binding from your administrator (see
   [Tenants and principals](../iam/principals.md)).
2. To work from a repository, issue a PAT and set up the
   [MCP plugin](mcp-plugin.md).
3. To see the whole organization, make decisions, and manage it, open the
   [console](console.md) (`/console/`).
4. For questions and assignments, open the [assistant](assistant.md) in the console
   (⌘J / Ctrl+J). The same conversation continues in Telegram.
5. Read [Everyday workflows](workflows.md).

## See also

- [Console](console.md)
- [Key concepts](../overview/concepts.md)
- [Work model](../control-plane/work-model.md)
- [Approvals](../control-plane/approvals.md)
- [Agents and runner](../runner/index.md)
