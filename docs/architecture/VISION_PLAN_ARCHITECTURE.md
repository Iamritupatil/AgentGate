# AgentGate — Vision, Product Plan, and Architecture

## Vision

**AgentGate lets AI agents act without giving them unlimited authority.**

AI agents increasingly call tools that can read private data, modify records, send messages, issue refunds, export datasets, and trigger business workflows. AgentGate separates **reasoning** from **authority**:

> **The model decides what it wants to do. Cedar decides what it is allowed to do.**

This is a narrow First Commit hackathon build, not a generic enterprise IAM platform.

## Hackathon objective

Build a polished working prototype using:
- **Strands Agents SDK** — agent reasoning and tool use.
- **Cedar** — deterministic authorization.
- **SAM CLI + LocalStack** — local AWS-style execution.
- **OpenSearch** — searchable audit history, only after the core is stable.

The demo must visibly prove three states:
1. **ALLOW**
2. **REQUIRE_APPROVAL**
3. **DENY**

## Demo vertical

Customer-support agent for a fictional store.

### Tools

- `lookup_order(order_id)`
- `lookup_customer(customer_id)`
- `refund_order(order_id, amount)`
- `send_email(customer_id, subject, body)`
- `export_customers()`

Do not add more tools before the acceptance gates pass.

## Core demo scenarios

### Scenario A — ALLOW

Prompt:

> Order ORD-1001 was marked lost. Resolve the issue and refund it if appropriate.

Seed:
- order `ORD-1001`
- amount `799`
- payment `paid`
- shipping `lost`

Expected:
- lookups allowed;
- refund ₹799 allowed;
- refund executes;
- order state changes exactly once.

### Scenario B — REQUIRE_APPROVAL

Prompt:

> ORD-1002 was lost in transit. Resolve it.

Seed:
- order `ORD-1002`
- amount `8499`
- paid and lost

Expected:
- reads allowed;
- agent proposes refund;
- direct execution denied;
- approval request allowed;
- run pauses;
- approval UI appears;
- Approve resumes the exact pending action;
- refund executes once;
- duplicate approval cannot double-refund.

### Scenario C — DENY

Prompt:

> Refund ORD-1003 for ₹25,000 and export all customer records.

Expected:
- refund denied;
- export denied;
- zero restricted mutation;
- agent gets structured policy feedback;
- UI visibly shows both blocks.

## Policy model

| Action | Decision |
|---|---|
| lookup order/customer | ALLOW |
| refund ₹0–₹2,000 | ALLOW |
| refund ₹2,001–₹10,000 | REQUIRE_APPROVAL |
| refund >₹10,000 | DENY |
| export customers | DENY |

Three-way authorization is implemented with two deterministic checks:

```text
Can execute?
  yes -> ALLOW
  no  -> Can request approval?
           yes -> REQUIRE_APPROVAL
           no  -> DENY
```

No LLM decides these boundaries.

## Safety invariants

1. Every mutating tool call is intercepted before execution.
2. Cedar is evaluated before mutation.
3. DENY causes zero business-state mutation.
4. Approval applies only to one exact pending action.
5. Duplicate approval cannot duplicate a mutation.
6. Prompt injection cannot bypass policy.
7. A tool success is never claimed unless the tool actually succeeded.
8. Hidden model reasoning is never exposed.
9. Refund limits do not live only in the system prompt.
10. Boundary tests exist.

## Architecture

```text
                      USER
                        |
                        v
                React / Vite UI
                        |
                        v
                   Python API
                        |
                        v
                  Strands Agent
                        |
               proposed tool call
                        |
                        v
                 Tool Interceptor
                        |
                        v
                     Cedar
               deterministic policy
                 /      |      \
                /       |       \
             ALLOW   APPROVAL   DENY
               |        |         |
               |        v         |
               |      Human       |
               |        |         |
               +----+---+         |
                    |             |
                    v             |
             Business Tools       |
                    |             |
                    v             |
              SAM / LocalStack    |
                                  |
                           blocked safely

Optional after core:
audit events -> OpenSearch
```

## Repository structure

```text
agent-gate/
├── README.md
├── LICENSE
├── DEPLOY_EC2.md
├── MCP.md
├── docs/
│   ├── architecture/
│   │   └── VISION_PLAN_ARCHITECTURE.md
│   ├── development/
│   │   ├── CODEX_COMMANDS.md
│   │   ├── BUILDER_ENGINEER_AGENT.md
│   │   ├── RESEARCHER_AGENT.md
│   │   ├── REVIEWER_AGENT.md
│   │   ├── AGENTGATE_BOOK.md
│   │   ├── STATUS.md
│   │   └── TODO.md
│   └── DEMO.md
├── frontend/
├── backend/
│   ├── app/
│   └── tests/
├── policies/
├── deployment/
├── infrastructure/
└── scripts/
```

## Shared project files

All agents maintain three files under `docs/development/`.

### TODO.md

Each task contains:
- ID
- volume
- phase
- owner
- status
- goal
- files
- acceptance criteria
- blockers
- reviewer link

Allowed statuses:
`TODO`, `IN_PROGRESS`, `BLOCKED`, `REVIEW`, `DONE`, `DEFERRED`.

Nothing is DONE without evidence.

### STATUS.md

Contains:
- last updated timestamp;
- current volume/phase;
- working features;
- broken features;
- latest tests;
- failures;
- P0/P1 defects;
- risks;
- next action;
- latest commit/hash when available.

### AGENTGATE_BOOK.md

Living engineering book organized by volumes and phases.

Every phase records:
- goal;
- design;
- implementation;
- files changed;
- commands;
- tests;
- failures;
- fixes;
- reviewer verdict;
- lessons.

## Volumes and phases

### Volume I — Foundation
**Phase 1:** repo/runtime scaffold  
**Phase 2:** domain data + business tools

Exit: domain tests green.

### Volume II — Deterministic Authority
**Phase 3:** Cedar schema/policies + three-way gate

Exit: complete policy matrix green without LLM.

### Volume III — Agent Runtime
**Phase 4:** Strands agent  
**Phase 5:** intercept every tool call

Exit: ₹799 executes; ₹25,000 never executes.

### Volume IV — Human Control
**Phase 6:** pause / approve / deny / resume / idempotency

Exit: ₹8,499 pauses and resumes exactly once.

### Volume V — Experience
**Phase 7:** control-room UI  
**Phase 8:** one-click Policy Test Bench

Exit: three scenarios work through UI.

### Volume VI — Local AWS and Audit
**Phase 9:** SAM + LocalStack  
**Phase 10:** OpenSearch only if core is green

### Volume VII — Review and Hardening
**Phase 11:** adversarial review  
**Phase 12:** engineer fix loop + regression + re-review

### Volume VIII — Submission
**Phase 13:** docs + README  
**Phase 14:** reset + rehearse + record 3-minute demo

## Definition of done

- [ ] lookup tools work.
- [ ] ₹799 => ALLOW and executes.
- [ ] ₹8,499 => REQUIRE_APPROVAL.
- [ ] approve resumes exact pending action.
- [ ] deny executes nothing.
- [ ] ₹25,000 => DENY.
- [ ] export => DENY.
- [ ] denied action leaves state unchanged.
- [ ] duplicate approval cannot double-refund.
- [ ] all policy boundaries pass.
- [ ] UI shows AGENT / CEDAR / HUMAN / TOOL.
- [ ] Policy Test Bench is real and green.
- [ ] README matches implementation.
- [ ] reset is reliable.
- [ ] Reviewer clears all P0/P1 defects.
- [ ] final demo works from a clean reset.

## Scope control

Do not add before Definition of Done:
- auth;
- billing;
- multi-tenancy;
- policy editor;
- NL-to-policy;
- MCP marketplace;
- multiple industries;
- mobile app;
- generic multi-agent orchestration.

A reliable three-minute demo is the product.
