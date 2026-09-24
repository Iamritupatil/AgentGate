# AgentGate

> **Reasoning can be probabilistic. Authority should be deterministic.**

AgentGate is a deterministic authorization layer for AI agents and applications.

AI systems can increasingly issue refunds, deploy software, send messages, modify databases, and call APIs that affect real business systems.

AgentGate places a deterministic policy boundary between a proposed action and execution.

The caller proposes:

- **who** is acting,
- **what** action they want to perform,
- **which resource** they want to affect,
- and the **context** surrounding the request.

AgentGate evaluates that request using **Cedar** and returns one of three outcomes:

```text
ALLOW
REQUIRE_APPROVAL
DENY
```

The caller can reason however it wants.

It does not get to decide its own authority.

---

## Live

### Application

https://agentgate-sable.vercel.app/#/control

### Repository

https://github.com/iamritupatil/AgentGate

### Public API

```text
https://agentgate-sable.vercel.app/api
```

---

# Why AgentGate?

Giving an AI system access to a tool often gives it far more authority than it actually needs.

A support workflow may legitimately need access to:

```text
lookup_order
lookup_customer
refund_order
send_email
```

A deployment workflow may need access to:

```text
read_logs
deploy_production
delete_production_database
```

But tool access alone does not answer questions like:

```text
Can this agent refund ₹799 automatically?

Can it refund ₹8,499?

Should a human approve it first?

Can it refund ₹25,000?

Can it export the entire customer database?

Can a deployment agent deploy to production?

Can it delete the production database?
```

These are **authorization decisions**, not reasoning decisions.

Putting those rules only inside a system prompt is not enough.

```text
"Never refund more than ₹2,000 without permission."
```

A model can misunderstand instructions, be manipulated by prompt injection, or simply make a bad decision.

AgentGate moves authority **outside the model** and into deterministic policies.

---

# Core Principle

```text
AI / application decides what it wants to do.

AgentGate decides what it is allowed to do.

Cedar makes the authorization decision.
```

The language model does not get to override the policy engine.

---

# Architecture

## Current deployed architecture

```text
External caller / React Control Room
               │
               │ HTTPS
               ▼
             Vercel
               │
               │ /api/*
               ▼
         AWS EC2 backend
               │
               ▼
            FastAPI
               │
               ▼
       AuthorityGateway
               │
               ▼
             Cedar
        ┌──────┼──────────┐
        │      │          │
        ▼      ▼          ▼
      ALLOW  APPROVAL    DENY
        │      │
        │      ▼
        │    Human
        │   decision
        │      │
        └──┬───┘
           ▼
     Business action
```

The browser only talks to the HTTPS Vercel origin.

Vercel proxies `/api/*` server-side to the FastAPI service running on Amazon EC2.

This keeps the frontend same-origin and avoids exposing an insecure HTTP backend directly to browser code.

---

# What AgentGate Does

AgentGate currently provides:

- deterministic Cedar authorization;
- `ALLOW`, `REQUIRE_APPROVAL`, and `DENY`;
- a generic HTTP authorization API;
- a human approval workflow;
- exact-action approval binding;
- business-action interception through an authority gateway;
- Policy Studio;
- Policy Playground;
- Policy Test Bench;
- an audit/timeline view;
- an MCP adapter;
- a React/Vite Control Room;
- a FastAPI backend;
- public deployment with Vercel + AWS EC2.

---

# Generic Authorization API

AgentGate exposes a generic authorization endpoint:

```text
POST /api/gate/evaluate
```

A caller sends:

```json
{
  "principal": {
    "type": "Agent",
    "id": "deployment-agent"
  },
  "action": "deploy_production",
  "resource": {
    "type": "Environment",
    "id": "production"
  },
  "context": {
    "environment": "prod"
  }
}
```

A successful authorization response can look like:

```json
{
  "decision": "REQUIRE_APPROVAL",
  "principal": "Agent:deployment-agent",
  "action": "deploy_production",
  "resource": "Environment:production",
  "reason_code": "APPROVAL_PERMITTED",
  "matched_policy": "allow_deploy_approval_request"
}
```

The same endpoint can be called from:

- an AI agent;
- a backend service;
- a workflow engine;
- an internal automation system;
- an MCP client;
- Postman;
- curl;
- or any application capable of making an HTTP request.

---

# Three-Way Authorization

Cedar itself provides deterministic authorization.

AgentGate composes a third human-approval state by separating two questions:

```text
1. Can this action execute?

2. If not, is this action eligible to request human approval?
```

Conceptually:

```python
if can_execute(action):
    return ALLOW

if can_request_approval(action):
    return REQUIRE_APPROVAL

return DENY
```

A hard-denied action does not become approvable.

---

# Example: Deployment Authority

## Production deployment

Request:

```json
{
  "principal": {
    "type": "Agent",
    "id": "deployment-agent"
  },
  "action": "deploy_production",
  "resource": {
    "type": "Environment",
    "id": "production"
  },
  "context": {}
}
```

Result:

```text
REQUIRE_APPROVAL
```

## Destructive production action

Change the requested operation to:

```text
delete_production_database
```

Result:

```text
DENY
```

The caller may ask for the action.

It cannot grant itself the authority to perform it.

---

# Example: Refund Authority

The demo includes a support-agent refund policy.

| Refund amount | Decision |
| ---: | --- |
| Up to ₹2,000 | `ALLOW` |
| ₹2,001 – ₹10,000 | `REQUIRE_APPROVAL` |
| Above ₹10,000 | `DENY` |

The same separation applies:

```text
Agent proposes action
        │
        ▼
      Cedar
        │
  ┌─────┼─────────┐
  ▼     ▼         ▼
ALLOW APPROVAL   DENY
```

---

# Human Approval

Some actions should not be fully autonomous but also should not be permanently forbidden.

Example:

```text
support-agent
refund_order
₹8,499
```

AgentGate returns:

```text
REQUIRE_APPROVAL
```

The action does not execute immediately.

Instead, AgentGate creates a pending action.

The pending record binds the approval to the action being reviewed.

The approval endpoint accepts a decision and version for that pending action.

It does not allow the caller to replace the original action arguments during approval.

Conceptually:

```text
PROPOSED ACTION
      │
      ▼
CEDAR: REQUIRE_APPROVAL
      │
      ▼
PENDING ACTION CREATED
      │
      ▼
HUMAN APPROVES
      │
      ▼
EXACT PENDING ACTION EXECUTES
```

This matters because a human approval should authorize **the action they actually reviewed**, not a later modified request.

---

# Approval Safety

AgentGate is designed around several approval-safety properties.

## Approval is action-bound

Approval is tied to the pending proposal rather than granting broad future authority.

## Arguments are bound

The approval path does not accept replacement execution arguments.

## Exactly-once claim

A pending action is claimed before execution so concurrent approval attempts cannot intentionally execute the same approved mutation multiple times.

## Reset isolation

Demo reset state is separated so an approval captured before a reset cannot simply be replayed against a new demo state.

---

# Authority Gateway

Protected business mutations sit behind the `AuthorityGateway`.

The gateway is the application-layer boundary between:

```text
requested action
       │
       ▼
     Cedar
       │
       ▼
authorization result
       │
       ▼
possible execution
```

The goal is to prevent a second application path from bypassing the policy check and directly invoking a protected business mutation.

---

# Business Demo

The demo contains fictional customers and orders.

Example orders:

| Order | Total |
| --- | ---: |
| `ORD-1001` | ₹799 |
| `ORD-1002` | ₹8,499 |
| `ORD-1003` | ₹25,000 |

Supported internal demo operations include:

```text
lookup_order
lookup_customer
refund_order
send_email
export_customers
```

The business layer independently validates domain rules.

Examples include:

- refund values must be valid;
- a refund cannot exceed the paid order total;
- unpaid orders cannot be refunded;
- repeated refunds cannot mutate the same order twice;
- denied operations do not reach the protected mutation.

Authorization and business validity are intentionally separate concerns.

---

# Demo Scenarios

## Scenario A — Safe Action

```text
Order: ORD-1001
Refund: ₹799
```

Decision:

```text
ALLOW
```

The refund executes immediately.

---

## Scenario B — Human Approval

```text
Order: ORD-1002
Refund: ₹8,499
```

Decision:

```text
REQUIRE_APPROVAL
```

The action pauses until a human approves or denies it.

After approval, the exact pending action executes.

---

## Scenario C — Hard Boundary

```text
Order: ORD-1003
Refund: ₹25,000
```

Decision:

```text
DENY
```

AgentGate also blocks sensitive operations such as:

```text
export_customers
```

Denied operations do not mutate the underlying business state.

---

# Control Room

The Control Room is the interactive demo UI for AgentGate.

It shows:

- current API/policy-engine connectivity;
- scenario selection;
- live authorization decisions;
- pending approvals;
- human approve/deny actions;
- business-state changes;
- the event timeline;
- Policy Studio;
- Policy Playground;
- integration examples;
- and the Policy Test Bench.

The scenario runner currently proposes a fixed sequence of actions from the operator interface.

It does **not** currently use an autonomous Strands agent to decide which demo action to propose.

That distinction is intentional and documented.

---

# Timeline

AgentGate records important authorization and execution events.

Events are attributed to actors such as:

```text
OPERATOR
CEDAR
HUMAN
TOOL
```

Example:

```text
OPERATOR
Proposed refund_order
₹8,499

        │
        ▼

CEDAR
REQUIRE_APPROVAL

        │
        ▼

HUMAN
APPROVED

        │
        ▼

TOOL
Refund executed
```

The purpose of the timeline is to make authorization visible instead of hiding it inside middleware.

---

# Policy Playground

The Policy Playground allows arbitrary authorization requests to be evaluated against the live backend.

A request contains:

```text
principal
action
resource
context
```

Example principals can include:

```text
support-agent
finance-agent
deployment-agent
unknown-agent
```

Example actions can include:

```text
refund_order
read_logs
deploy_production
delete_production_database
```

The Playground does not decide locally whether a request should pass.

It sends the request to the backend and displays the authorization result.

---

# Policy Studio

Policy Studio provides a UI for creating, previewing, saving, and activating authorization policies.

A policy can describe fields such as:

```text
name
principal
action
resource
decision
context field
allow threshold
approval threshold
```

The workflow is intentionally human-controlled:

```text
Describe / build policy
        │
        ▼
      Draft
        │
        ▼
     Preview
        │
        ▼
Human activates
        │
        ▼
 Policy becomes active
```

A generated draft does not automatically become authority.

---

# Natural-Language Policy Drafting

Policy Studio can also draft a structured policy from a natural-language description.

Example:

```text
Support agents may refund up to ₹2,000 automatically.
Between ₹2,000 and ₹10,000 ask me for approval.
Deny anything higher.
```

AgentGate turns that description into a structured draft and Cedar-oriented preview.

The draft must still be explicitly activated by a human.

The backend can use a configured model provider for drafting when provider credentials are available.

The **authorization decision itself remains deterministic and is performed by Cedar**, not by the language model.

---

# Policy Test Bench

AgentGate includes a built-in policy test interface.

Example cases:

```text
lookup_order             → ALLOW
refund ₹799              → ALLOW
refund ₹8,499            → REQUIRE_APPROVAL
refund ₹25,000           → DENY
export_customers         → DENY
```

The test bench exercises the backend authorization path rather than calculating answers in the frontend.

---

# MCP

AgentGate also exposes the authorization gate through an MCP adapter.

The MCP path uses the same authorization concepts as the HTTP API:

```json
{
  "principal": {
    "type": "Agent",
    "id": "deployment-agent"
  },
  "action": "deploy_production",
  "resource": {
    "type": "Environment",
    "id": "production"
  },
  "context": {}
}
```

The MCP adapter is not intended to define a second, independent policy system.

It reuses the AgentGate authorization boundary.

See:

```text
MCP.md
```

---

# AWS Usage

AgentGate was built for **First Commit — Bharat Builds Tour 2026**.

## Build It — Cedar

AgentGate uses **Cedar** as the deterministic authorization engine.

Cedar evaluates authority over:

```text
principal
action
resource
context
```

Authorization stays outside the language model.

## Ship It — Amazon EC2

The AgentGate FastAPI backend is deployed on **Amazon EC2**.

The EC2 backend runs the application components responsible for:

```text
FastAPI
AuthorityGateway
Cedar authorization
approval workflow
Policy Studio backend
business demo state
MCP implementation
```

The React/Vite frontend is deployed separately on Vercel.

---

# Public Request Flow

```text
Browser / Postman / external client
              │
              ▼
         Vercel HTTPS
              │
              ▼
            /api/*
              │
              ▼
        Amazon EC2
              │
              ▼
           FastAPI
              │
              ▼
      AuthorityGateway
              │
              ▼
            Cedar
              │
        authorization
              │
              ▼
     execute / pause / deny
```

This is the same public path used by the deployed application and external API tests.

---

# Technology Stack

## Authorization

```text
Cedar
```

## Backend

```text
Python
FastAPI
Pydantic
Uvicorn
```

## Frontend

```text
React
TypeScript
Vite
```

## Infrastructure

```text
Amazon EC2
Vercel
```

## Integration

```text
HTTP API
MCP
Postman
curl
external application clients
```

---

# Repository Structure

```text
AgentGate/
│
├── backend/
│   ├── app/
│   │   ├── api.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── mcp_server.py
│   │   │
│   │   ├── approvals/
│   │   ├── domain/
│   │   ├── policy/
│   │   ├── services/
│   │   └── tools/
│   │
│   ├── tests/
│   ├── pyproject.toml
│   └── uv.lock
│
├── frontend/
│   ├── src/
│   │   ├── api.ts
│   │   ├── ControlRoom.tsx
│   │   ├── Workbench.tsx
│   │   └── ...
│   │
│   ├── tests/
│   ├── package.json
│   ├── vite.config.ts
│   └── vercel.json
│
├── policies/
│   ├── agentgate.cedarschema
│   ├── execute.cedar
│   ├── request_approval.cedar
│   └── entities.json
│
├── deployment/
│   ├── agentgate.service
│   └── nginx-agentgate.conf
│
├── docs/
│   └── ...
│
├── DEPLOY_EC2.md
├── MCP.md
├── README.md
└── LICENSE
```

---

# Local Development

## Requirements

AgentGate uses:

```text
Python 3.12+
Node.js
uv
npm
```

---

## Backend

From the repository root:

```powershell
uv sync --project backend --locked
```

Start FastAPI:

```powershell
uv run --project backend --locked uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Or, when using the local backend virtual environment on Windows:

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Health endpoint:

```text
http://127.0.0.1:8000/api/health
```

FastAPI documentation:

```text
http://127.0.0.1:8000/api/docs
```

---

## Frontend

In another terminal:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open:

```text
http://127.0.0.1:5173/#/control
```

During local development, Vite proxies:

```text
/api/*
```

to the backend running on:

```text
http://127.0.0.1:8000
```

---

# Public API Examples

## Health

```bash
curl https://agentgate-sable.vercel.app/api/health
```

---

## Evaluate a Production Deployment

```bash
curl -X POST https://agentgate-sable.vercel.app/api/gate/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "principal": {
      "type": "Agent",
      "id": "deployment-agent"
    },
    "action": "deploy_production",
    "resource": {
      "type": "Environment",
      "id": "production"
    },
    "context": {}
  }'
```

Expected decision:

```text
REQUIRE_APPROVAL
```

---

## Evaluate a Destructive Production Action

```bash
curl -X POST https://agentgate-sable.vercel.app/api/gate/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "principal": {
      "type": "Agent",
      "id": "deployment-agent"
    },
    "action": "delete_production_database",
    "resource": {
      "type": "Database",
      "id": "production"
    },
    "context": {}
  }'
```

Expected decision:

```text
DENY
```

---

## Evaluate a Support Refund

```bash
curl -X POST https://agentgate-sable.vercel.app/api/gate/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "principal": {
      "type": "Agent",
      "id": "support-agent"
    },
    "action": "refund_order",
    "resource": {
      "type": "Order",
      "id": "ORD-1002"
    },
    "context": {
      "amount": 8499
    }
  }'
```

Expected decision:

```text
REQUIRE_APPROVAL
```

---

# Testing

## Backend

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -q
```

or:

```powershell
uv run --project backend --locked pytest backend/tests
```

---

## Frontend Build

```powershell
cd frontend
npm.cmd run build
```

---

## Frontend Tests

```powershell
npm.cmd test
```

---

## Browser Tests

With the required services available:

```powershell
npm.cmd run test:e2e
```

---

# Security Invariants Demonstrated

## 1. Authorization Before Execution

Protected business mutations go through the authority gateway before execution.

```text
proposed action
      │
      ▼
    Cedar
      │
      ▼
authorization
      │
      ▼
execution
```

---

## 2. Default Deny

Unknown authority should not be inherited accidentally.

An unknown principal or action without an applicable permit falls through to denial.

```text
no matching authority
        │
        ▼
       DENY
```

---

## 3. Human Approval Does Not Replace Policy

Only actions explicitly eligible for escalation may enter the approval path.

A hard-denied operation cannot simply be approved by a human through the normal approval flow.

---

## 4. Approval Is Scoped to the Pending Action

Approval does not grant broad or permanent authority.

It applies to the action that was actually proposed and reviewed.

---

## 5. Denied Actions Do Not Mutate Protected State

An authorization denial stops before the protected business operation.

---

## 6. AI Does Not Make the Authorization Decision

AI may:

```text
reason
propose an action
draft a policy
```

AI does not decide:

```text
whether it is authorized to execute that action
```

That boundary belongs to Cedar.

---

# Current Scope

AgentGate is a hackathon prototype demonstrating deterministic authorization for AI-driven and application-driven actions.

## Implemented

```text
Cedar authorization
ALLOW / REQUIRE_APPROVAL / DENY
generic authorization API
human approval workflow
action-bound approvals
authority gateway
Control Room
Policy Playground
Policy Studio
policy drafting
Policy Test Bench
business-state demo
audit timeline
MCP adapter
Amazon EC2 backend deployment
Vercel frontend deployment
```

## Not Currently Implemented

```text
autonomous Strands Agents SDK execution loop
native Strands interrupt/resume
durable distributed approval storage
OpenSearch audit storage
SAM CLI / LocalStack execution environment
production-grade identity/authentication
multi-node distributed state
```

These are future integrations, not current capabilities.

---

# Future Work

Possible next steps include:

- connect an autonomous agent runtime;
- add native agent pause/resume semantics;
- add durable approval storage;
- add authenticated principals and users;
- add organization/workspace separation;
- add signed policy versions;
- add durable audit/event storage;
- add distributed execution support;
- add OpenSearch-backed audit exploration;
- add production deployment adapters;
- add richer Cedar policy templates;
- add policy simulation before activation.

---

# What AgentGate Is Not

AgentGate is not intended to replace:

- enterprise IAM systems;
- AWS AgentCore Policy;
- production fraud systems;
- production financial authorization systems;
- complete agent-security platforms.

It demonstrates a focused pattern:

> **An AI can decide what it wants to do without being allowed to decide what it is permitted to do.**

---

# Built For

**First Commit — Bharat Builds Tour 2026**

AWS technology used in the working project:

```text
Cedar
Amazon EC2
```

Application stack:

```text
FastAPI
React
Vite
TypeScript
Python
MCP
Vercel
```

---

# Final Principle

```text
Reasoning can be probabilistic.

Authority should be deterministic.
```

**AgentGate**
