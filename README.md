# AgentGate

> **Let AI agents act without giving them unlimited authority.**

## Current implementation — Volumes I–II, plus the authority gateway

**Cedar decides.** The policy gate is implemented and runs for real. So does the
approval lifecycle, the timeline, the reset, and the Policy Test Bench — all over HTTP.

| Capability | State |
| --- | --- |
| Cedar policy engine, three-way gate | **Implemented** |
| Complete policy boundary matrix | **Implemented** — 54 checks |
| Non-bypassable gateway to business tools | **Implemented** at the application layer |
| Pending actions, approve / deny, exactly-once | **Implemented** — in-process storage |
| HTTP API over the gate | **Implemented** |
| Policy Test Bench endpoint | **Implemented** |
| Strands agent proposing tool calls | **Not implemented** |
| Native Strands interrupt / resume | **Not implemented** |
| Durable approval storage across restart | **Not implemented** |
| Control-room UI that runs scenarios | **Not implemented** — still previews |
| SAM / LocalStack, OpenSearch | **Not implemented** |

Two consequences worth stating plainly:

- **Nothing proposes a tool call on its own yet.** Every proposal is typed by an
  operator, and the timeline labels it `OPERATOR` rather than `AGENT` for that reason.
- **The approval path is the documented application-level fallback**, not native
  Strands resume. Its argument digest binds a gateway-issued proposal ID and a reset
  epoch. When Strands lands, the Strands tool-use ID and interrupt ID must be added to
  that envelope.

See [STATUS.md](STATUS.md) for verification evidence and [TODO.md](TODO.md) for what is
next. Sections below marked *planned* or *target* describe work that does not exist yet.

## The authority gate — Phase 3

[`policies/`](policies/) holds the authority model, outside the backend package:

- [`agentgate.cedarschema`](policies/agentgate.cedarschema) — five real actions plus the
  synthetic `request_refund_approval`. Refund amounts are Cedar `Long` values.
- [`execute.cedar`](policies/execute.cedar) — narrow permits for reads, recorded email
  and refunds up to ₹2,000; an explicit `forbid` for `export_customers`.
- [`request_approval.cedar`](policies/request_approval.cedar) — one permit, for refunds
  from ₹2,001 to ₹10,000.

Cedar answers only Allow or Deny. The third state is composed from two requests: the
real action first, then the synthetic approval action, and only for a refund that was
refused without an explicit forbid. An action that is explicitly forbidden never becomes
a question a human could say yes to.

Everything that can change state sits behind
[`AuthorityGateway`](backend/app/services/gateway.py), which is the only holder of the
business tools. There is no second path to `refund_order`, so no prompt, no malformed
argument and no direct call can reach one.

```text
POST /api/actions   {"tool": "refund_order", "arguments": {"order_id": "ORD-1002", "amount": 8499}}
  -> {"decision": "REQUIRE_APPROVAL", "executed": false, "pending_id": "pend-...",
      "determining_policies": ["allow_refund_approval_request"]}

POST /api/pending/pend-...   {"decision": "approve", "version": 1}
  -> {"decision": "ALLOW", "executed": true, "result": {"status": "refunded", ...}}
```

The approval endpoint accepts only an ID, a version and a decision. It never accepts
replacement arguments, because an endpoint that let the caller supply what to execute
would make the human approval meaningless.

## Internal business layer — Phase 2

[`BusinessTools`](backend/app/tools/business.py) provides `lookup_order`,
`lookup_customer`, `refund_order`, `send_email`, and `export_customers` against the
[`BusinessStore`](backend/app/domain/storage.py) interface. The current
[`InMemoryStore`](backend/app/domain/memory.py) is a single-process demo/test adapter.
These operations are not registered with an agent and are not reachable directly over
HTTP; every route goes through the gateway, where Cedar sees the call first.

The seed contains fictional customers and these paid, lost orders:

| Order | Total |
| --- | ---: |
| ORD-1001 | ₹799 |
| ORD-1002 | ₹8,499 |
| ORD-1003 | ₹25,000 |

Domain behavior:

- Money is a positive whole-rupee integer. Booleans, strings, floats, zero and negative refund amounts are rejected.
- A refund cannot exceed the paid order total. Unpaid orders cannot be refunded.
- Each order permits one refund, including a partial refund. Repeated calls or later partial top-ups fail without changing state.
- The order update and refund receipt commit together under one store lock. Concurrent requests cannot double-refund an order.
- `send_email` only records a local message with `status: recorded` and `delivered: false`; no network transport is used.
- Lookups and customer export return detached data. Stored records and snapshots are immutable.
- Internal `reset()` restores the initial fixtures and clears action records. It is
exposed as `POST /api/reset`, which also clears the timeline and bumps a reset epoch so
an approval captured beforehand cannot be replayed afterwards.

Business validity is separate from authority: the raw domain can refund a valid
₹25,000 order, and internal tests can export the fictional customers. The Cedar gate
denies those actions before these methods are reached. A ₹0 refund is inside the
policy's numeric range and is still rejected by the domain as meaningless; a test
asserts both halves.

The store is not durable and is not coordinated across processes. Reset restarts
local receipt counters; receipt IDs are not authorization tokens. Approval expiry,
session identity and replay protection across reset belong to later phases.

## Product vision

AgentGate is a deterministic control layer for AI agents.

AI agents can increasingly call APIs, modify databases, send emails, issue refunds, and perform other real-world actions. But giving an agent access to a tool should not mean giving it unlimited authority over that tool.

AgentGate intercepts consequential agent actions before execution and evaluates them against deterministic **Cedar policies**.

Every action receives one of three outcomes:

* **ALLOW** — execute immediately.
* **REQUIRE APPROVAL** — pause execution and ask a human.
* **DENY** — block the action completely.

The AI decides **what it wants to do**.

**Cedar decides what it is allowed to do.**

---

## Why AgentGate?

Traditional agent safety often depends on system prompts:

```text
Do not refund more than ₹2,000 without permission.
```

But prompts are probabilistic.

An agent may misunderstand them, ignore them, be manipulated through prompt injection, or simply make a bad decision.

AgentGate moves authorization **outside the model**.

```text
User Request
     │
     ▼
Strands Agent
     │
     │ proposes tool call
     ▼
 AgentGate
     │
     ▼
   Cedar
     │
 ┌───┼──────────────┐
 │   │              │
 ▼   ▼              ▼
ALLOW APPROVAL      DENY
 │      │             │
 ▼      ▼             ▼
Tool   Human        Block
runs   decision      action
```

The language model cannot override the policy engine.

---

# Demo (planned)

AgentGate currently focuses on one simple workflow:

## AI Customer Support Agent

The agent can use five tools:

```text
lookup_order()
lookup_customer()
refund_order()
send_email()
export_customers()
```

The demo uses three scenarios.

---

## Scenario 1 — Safe Action

A customer has a lost ₹799 order.

The agent investigates the order and proposes:

```text
refund_order(
    order_id="ORD-1001",
    amount=799
)
```

AgentGate evaluates the request:

```text
STRANDS
   │
   ▼
refund ₹799
   │
   ▼
CEDAR
   │
   ▼
ALLOW ✓
```

The refund executes automatically.

---

## Scenario 2 — Human Approval

A customer has a lost ₹8,499 order.

The agent proposes:

```text
refund_order(
    order_id="ORD-1002",
    amount=8499
)
```

The autonomous refund limit is ₹2,000.

Instead of executing the refund, AgentGate pauses the agent.

```text
┌─────────────────────────────────┐
│ HUMAN APPROVAL REQUIRED         │
│                                 │
│ Action: refund_order            │
│ Order: ORD-1002                 │
│ Amount: ₹8,499                  │
│                                 │
│ Autonomous limit: ₹2,000        │
│ Approval limit: ₹10,000         │
│                                 │
│ [ DENY ]            [ APPROVE ] │
└─────────────────────────────────┘
```

If the human approves, the exact pending tool call resumes and executes.

---

## Scenario 3 — Dangerous Action

The agent attempts:

```text
refund_order(
    order_id="ORD-1003",
    amount=25000
)
```

AgentGate responds:

```text
DENY ✕
```

The agent then attempts:

```text
export_customers()
```

AgentGate responds:

```text
DENY ✕
```

Neither operation touches the underlying business state.

---

# Policy Model (planned)

AgentGate uses deterministic Cedar policies.

For refunds:

| Refund amount    | Result         |
| ---------------- | -------------- |
| ₹0 – ₹2,000      | ALLOW          |
| ₹2,001 – ₹10,000 | HUMAN APPROVAL |
| Above ₹10,000    | DENY           |

Customer database export:

```text
DENY
```

Read-only order/customer lookups:

```text
ALLOW
```

The language model never decides these boundaries.

---

# Three-Way Authorization (planned)

Cedar naturally provides deterministic authorization decisions.

AgentGate creates the third **human approval** state using two policy checks.

For each proposed tool call:

```text
Can the agent execute this action?
```

If yes:

```text
ALLOW
```

Otherwise AgentGate asks:

```text
Can the agent request human approval for this action?
```

If yes:

```text
REQUIRE_APPROVAL
```

Otherwise:

```text
DENY
```

Conceptually:

```python
if can_execute(action):
    return ALLOW

if can_request_approval(action):
    return REQUIRE_APPROVAL

return DENY
```

No LLM is involved in this decision.

---

# Architecture (target)

AgentGate is built around the AWS open-source stack used by the First Commit / Bharat Builds hackathon.

```text
                    ┌─────────────────┐
                    │      User       │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   React / Vite  │
                    │  Control Room   │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   Python API    │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Strands Agent   │
                    └────────┬────────┘
                             │
                       proposed tool
                             │
                             ▼
                    ┌─────────────────┐
                    │    AgentGate    │
                    │ Tool Intercept  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │      Cedar      │
                    │ Policy Engine   │
                    └────────┬────────┘
                             │
                  ┌──────────┼──────────┐
                  │          │          │
                  ▼          ▼          ▼
               ALLOW      APPROVAL     DENY
                  │          │
                  │          ▼
                  │       Human
                  │          │
                  └────┬─────┘
                       │
                       ▼
               ┌────────────────┐
               │ Business Tools │
               └───────┬────────┘
                       │
                       ▼
             SAM CLI + LocalStack

                       │
                       ▼
                 OpenSearch
               Audit / History
```

---

# Technology (planned integrations)

## Strands Agents SDK

Strands powers the support agent and its tool-use loop.

Its job is to determine what actions would help accomplish the user's goal.

Strands does **not** determine whether those actions are authorized.

---

## Cedar

Cedar is AgentGate's deterministic policy engine.

It determines whether a proposed action can:

```text
EXECUTE
REQUEST HUMAN APPROVAL
or
BE DENIED
```

Authorization stays outside the language model.

---

## SAM CLI + LocalStack

The business actions are represented using an AWS-style local environment.

This allows AgentGate to demonstrate real action execution without requiring production infrastructure.

---

## OpenSearch

Agent actions and policy decisions can be indexed into OpenSearch.

Example event:

```json
{
  "agent": "support-agent",
  "action": "refund_order",
  "amount": 8499,
  "policy_decision": "REQUIRE_APPROVAL",
  "human_decision": "APPROVED",
  "executed": true
}
```

This creates a searchable audit trail of agent behavior.

---

# Policy Test Bench (planned)

AgentGate includes a deterministic policy test interface.

```text
AGENTGATE POLICY TESTS

lookup_order                 ALLOW ✓
refund ₹799                  ALLOW ✓
refund ₹8,499             APPROVAL ✓
refund ₹25,000                DENY ✓
export_customers              DENY ✓

──────────────────────────────────
5 / 5 POLICY TESTS PASSED
```

This demonstrates that the safety boundary works independently of the language model.

---

# Control Room (target experience)

The interface visualizes every important action.

Events are grouped by actor:

```text
AGENT
CEDAR
TOOL
HUMAN
```

Example:

```text
AGENT
Proposed refund_order
₹8,499

        ↓

CEDAR
Human approval required

        ↓

HUMAN
Approved

        ↓

TOOL
Refund completed
```

The goal is to make agent authorization understandable rather than invisible middleware.

---

# Project Structure

```text
agent-gate/
│
├── frontend/
│   ├── src/                 # React shell, styles and health client tests
│   ├── tests/               # Browser smoke checks
│   ├── package.json
│   └── package-lock.json
│
├── policies/                # The authority model. Cedar owns these decisions.
│   ├── agentgate.cedarschema
│   ├── execute.cedar         # Reads, recorded email, refunds up to Rs 2,000, export forbidden
│   ├── request_approval.cedar# The escalation band: Rs 2,001 to Rs 10,000
│   └── entities.json
│
├── backend/
│   ├── app/                 # Application factory, settings, /health, /api
│   │   ├── policy/          # Cedar adapter, argument specs and the three-way contract
│   │   ├── services/        # AuthorityGateway: the only door to a business mutation
│   │   ├── approvals/       # Pending actions, argument digest, exactly-once claim
│   │   ├── domain/          # Immutable models, seed, storage contract and memory adapter
│   │   └── tools/           # Five internal business operations (gateway-only)
│   ├── tests/
│   │   ├── policy/          # Boundary matrix, startup validation, fail-closed behaviour
│   │   └── gateway/         # Three scenarios and the attacks on the approval path
│   ├── pyproject.toml
│   └── uv.lock
│
├── 01_VISION_PLAN_ARCHITECTURE.md
├── 02_CODEX_COMMANDS.md
├── 03_BUILDER_ENGINEER_AGENT.md
├── 04_RESEARCHER_AGENT(1).md
├── 05_REVIEWER_AGENT(1).md
├── TODO.md
├── STATUS.md
├── AGENTGATE_BOOK.md
└── README.md
```

---

# Core Safety Invariants

Each invariant below names the test that holds it up. Where an invariant is only
partly enforced, that is stated rather than glossed.

### 1. Authorization happens before execution — **enforced**

`AuthorityGateway.propose` evaluates Cedar before any dispatch, and the gateway is the
only holder of the business tools. A test pins its entire public surface, so a new way
in has to be added deliberately.
`tests/gateway/test_approval_safety.py::test_the_gateway_does_not_expose_the_raw_tools`

### 2. The model cannot override Cedar — **enforced for the inputs that exist**

Tool arguments reach Cedar's `context.input` and go no further. A prompt-injection
payload in an email body changes no later decision.
`tests/gateway/test_approval_safety.py::test_injected_instructions_in_tool_arguments_change_nothing`

Not yet provable end to end: no agent runs, so nothing has attempted a bypass through a
model turn.

### 3. Denied actions cannot mutate state — **enforced**

Scenario C compares the entire store snapshot before and after, rather than checking
one field.
`tests/gateway/test_scenarios.py::test_scenario_c_refund_and_export_are_both_blocked`

### 4. Human approval applies only to the pending action — **enforced**

The digest binds the arguments, the proposal identity and the reset epoch. Two pending
refunds cannot be confused, and an approval captured before a reset authorizes nothing
after it.
`tests/gateway/test_approval_safety.py::test_an_approval_cannot_be_moved_to_a_different_order`

### 5. Approvals are idempotent — **enforced**

`claim` is one locked transition out of PENDING. Eight concurrent approvals produce
exactly one refund and one receipt.
`tests/gateway/test_approval_safety.py::test_concurrent_approvals_produce_exactly_one_refund`

### 6. Policy is deterministic — **enforced**

The full boundary matrix runs against the real engine with no model constructed. An
autouse fixture asserts `strands` was never imported, so the claim is enforced rather
than stated. Emptying the policy files turns every ALLOW into a DENY, which is what
proves no threshold is hiding in Python.
`tests/policy/test_matrix.py`, `tests/policy/test_engine.py::test_authority_lives_in_the_policy_files_not_in_python`

### 7. A tool success is never claimed unless the tool succeeded — **enforced**

An authorized call whose store operation fails is reported as a failure, and
`TOOL_EXECUTED` is appended only after the store returns a receipt.
`tests/gateway/test_scenarios.py::test_a_failed_tool_is_never_reported_as_a_success`

---

# What AgentGate Is Not

AgentGate is currently a hackathon prototype.

It is not intended to replace:

* enterprise IAM systems;
* AWS AgentCore Policy;
* complete agent security platforms;
* production fraud systems;
* production financial authorization systems.

The project demonstrates a simple pattern:

> **Keep agent reasoning probabilistic. Keep authority deterministic.**

---

# Local Development

AgentGate needs Node.js 24+, Python 3.12+, and `uv`. This workspace already has Node
and uv; uv can discover or provision the Python version declared in
`backend/.python-version`. Docker, cloud accounts and model API keys are not needed —
the authority gate is entirely local and involves no model.

Run the backend with a single worker. The approval store and the event log are
in-process, so a second worker would see neither.

Run these Windows PowerShell commands from this directory. `npm.cmd` avoids the
PowerShell script-execution restriction on `npm.ps1`; macOS/Linux users can use
`npm` for the equivalent commands.

Terminal 1 — backend:

```powershell
uv sync --project backend --locked
uv run --project backend --locked uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

Terminal 2 — frontend:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open [the control room](http://127.0.0.1:5173). The API health endpoint is
[localhost:8000/health](http://127.0.0.1:8000/health); API documentation is at
[localhost:8000/docs](http://127.0.0.1:8000/docs). Stop either server with Ctrl+C.

The control room does not run scenarios yet. To exercise the gate today, use the API
directly — for example, from `/docs`, or:

```powershell
$body = '{"tool":"refund_order","arguments":{"order_id":"ORD-1002","amount":8499}}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/actions -ContentType application/json -Body $body
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/policy-test
```

Both services run with defaults. Optional settings are documented in
[`backend/.env.example`](backend/.env.example) and
[`frontend/.env.example`](frontend/.env.example); copy each to `.env` in its own
directory if customization is needed. Backend environment files are resolved
relative to `backend/`, regardless of the working directory. Process environment
variables take precedence. Restart services after changing settings.

The UI requests `/api/health`; Vite forwards `/api/*` to `http://127.0.0.1:8000`.
`API_PROXY_TARGET` changes this local target; `VITE_API_BASE_URL` changes the
browser-facing API base. Keep secrets out of all `VITE_` variables.
The health indicator only confirms API liveness, and refreshes every 15 seconds.

`npm.cmd run build` creates `frontend/dist`. `npm.cmd run preview` serves it locally
on port 4173 using the same API proxy. Hosting the static output elsewhere requires
a corresponding reverse proxy or API base configuration; deployment is not part
of Phase 1.

---

# Testing

From the repository root, run the backend checks:

```powershell
uv run --project backend --locked pytest backend/tests
```

From `frontend/`, run the client tests and production build (which also typechecks):

```powershell
npm.cmd test
npm.cmd run build
```

With both servers running, run `npm.cmd run test:e2e` from `frontend/`. On Windows,
the browser checks use an existing Microsoft Edge installation. On other systems,
install Playwright Chromium with `npx playwright install chromium` first. Set
`PLAYWRIGHT_CHANNEL` to override the browser and `E2E_BASE_URL` to test a different
local frontend URL. Screenshots are written under ignored `artifacts/browser/`.

The current backend suite has 86 passing checks covering domain invariants,
concurrent refunds/emails, immutable snapshots, reset, failure atomicity,
API/config behavior and absence of public business endpoints. Frontend checks
cover rejection of unavailable or malformed health responses, live connectivity,
recovery, scenario previews and mobile layout. These do **not** certify Cedar
authorization, agent interception or approval safety yet.

Planned authorization tests in later phases will cover:

```text
lookup_order       → ALLOW

refund ₹799        → ALLOW
refund ₹2,000      → ALLOW

refund ₹2,001      → REQUIRE_APPROVAL
refund ₹8,499      → REQUIRE_APPROVAL
refund ₹10,000     → REQUIRE_APPROVAL

refund ₹10,001     → DENY
refund ₹25,000     → DENY

export_customers   → DENY
```

The most important invariant:

```text
DENIED ACTION
     ↓
ZERO STATE MUTATION
```

---

# Built For

**First Commit — Bharat Builds Tour 2026**

Built around:

* Strands Agents SDK
* Cedar
* SAM CLI
* LocalStack
