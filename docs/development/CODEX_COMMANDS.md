# AgentGate — Codex Commands and Build Prompts

## Purpose

Run these prompts **sequentially**. Do not ask Codex to build the whole project in one shot.

After every prompt:
1. inspect changed files;
2. run tests;
3. update `TODO.md`;
4. update `STATUS.md`;
5. append the work to `AGENTGATE_BOOK.md`;
6. commit only when the phase is coherent.

---

## Bootstrap Prompt

```text
Read:
- README.md
- docs/architecture/VISION_PLAN_ARCHITECTURE.md
- docs/development/BUILDER_ENGINEER_AGENT.md
- docs/development/RESEARCHER_AGENT.md
- docs/development/REVIEWER_AGENT.md

Create or update:
- TODO.md
- STATUS.md
- AGENTGATE_BOOK.md

In TODO.md create all volumes/phases from the architecture. Mark only Volume I / Phase 1 as IN_PROGRESS.

In STATUS.md describe exactly what exists now.

In AGENTGATE_BOOK.md create the volume/phase skeleton and record project initialization.

Do not implement product features yet.
```

---

## Prompt 1 — Scaffold

```text
Act as Builder Engineer.

Implement only Volume I / Phase 1:
- FastAPI backend
- /health
- centralized config
- backend tests
- React + Vite + TypeScript frontend
- minimal control-room shell
- .env.example
- dependency files

Do not add Cedar, Strands, refund logic, approval, LocalStack or OpenSearch.

Run backend tests and frontend build/typecheck.
Update TODO.md, STATUS.md and AGENTGATE_BOOK.md.
```

---

## Prompt 2 — Domain + Business Tools

```text
Act as Builder Engineer.

Implement Volume I / Phase 2:
- storage abstraction
- in-memory test implementation
- seeded demo data
- ORD-1001 = ₹799, paid, lost
- ORD-1002 = ₹8,499, paid, lost
- ORD-1003 = ₹25,000 demo case

Implement:
- lookup_order
- lookup_customer
- refund_order
- send_email as safe recorded demo action
- export_customers

Add invariants:
- no over-refund
- no double refund
- no unpaid refund
- successful refund mutates once

No Cedar or Strands yet.

Run tests and update the three shared project files.
```

---

## Prompt 3 — Cedar Research

```text
Act as Researcher Agent.

Research the current supported Cedar setup needed for AgentGate.

Determine:
- current Cedar policy/schema syntax
- local evaluation options compatible with Python
- principal/action/resource/context modeling
- numeric refund checks
- default-deny behavior
- version/runtime compatibility risks

Do not change product code.

Write findings to AGENTGATE_BOOK.md.
Create atomic Builder tasks in TODO.md.
Update STATUS.md with blockers or decisions.

Finish with a recommended implementation contract.
```

---

## Prompt 4 — Cedar Gate

```text
Act as Builder Engineer.

Implement Volume II / Phase 3 using the Researcher findings.

Required outcomes:
- lookup_order -> ALLOW
- lookup_customer -> ALLOW
- refund 799 -> ALLOW
- refund 2000 -> ALLOW
- refund 2001 -> REQUIRE_APPROVAL
- refund 8499 -> REQUIRE_APPROVAL
- refund 10000 -> REQUIRE_APPROVAL
- refund 10001 -> DENY
- refund 25000 -> DENY
- export_customers -> DENY

No LLM may participate in authorization.

Add unit tests for every boundary.
Run tests.
Update TODO.md, STATUS.md, AGENTGATE_BOOK.md.
```

---

## Prompt 5 — Reviewer Gate 1

```text
Act as Reviewer Agent.

Audit Volume I and II.

Check:
- domain invariants
- policy matrix
- default-deny
- boundary mistakes
- over-refund
- double refund
- denied-state mutation
- tests that can pass falsely

Run the test suite yourself.

For each defect add a TODO item with:
severity, reproduction, expected, actual, affected code, required fix, acceptance test.

Update STATUS.md and AGENTGATE_BOOK.md.

Return:
REVIEW_GATE_1=PASS
or
REVIEW_GATE_1=FAIL
```

---

## Prompt 6 — Fix Gate 1

```text
Act as Builder Engineer.

Fix every open P0/P1 defect from Review Gate 1.

For each:
- reproduce
- add/strengthen regression test
- fix root cause
- run focused test
- run relevant regression suite

Do not silence tests.

Update shared project files and mark fixes REVIEW for Reviewer re-test.
```

---

## Prompt 7 — Strands Research

```text
Act as Researcher Agent.

Research the current Strands Agents SDK APIs needed for:
- agent creation
- tool declaration/registration
- before-tool-call interception or supported equivalent
- cancelling/denying a tool call
- structured denial feedback
- human-in-the-loop interrupt
- persistence
- resume
- exact pending tool identity/arguments

Critical question:
Can we pause before a tool executes and later resume the same exact action safely?

Record exact current APIs, package/version, risks and fallback.
Update AGENTGATE_BOOK.md, TODO.md and STATUS.md.
Do not implement product code.
```

---

## Prompt 8 — Strands Agent

```text
Act as Builder Engineer.

Implement Volume III / Phase 4 using the Researcher findings.

Create the support agent and register exactly five tools.

System behavior:
- inspect relevant order before action
- use tools rather than inventing facts
- never claim success without tool success
- never attempt to bypass policy denial
- concise final responses

Do not place refund limits in the model prompt.

First prove basic agent invocation without policy interception.
Add construction/tool-registration tests that do not require live model calls.

Update shared project files.
```

---

## Prompt 9 — Intercept Every Tool Call

```text
Act as Builder Engineer.

Implement Volume III / Phase 5.

Flow:
1. capture tool + input
2. emit TOOL_PROPOSED
3. evaluate Cedar
4. emit POLICY_CHECKED
5. ALLOW -> execute
6. DENY -> cancel before execution and return structured denial feedback
7. REQUIRE_APPROVAL -> persist pending approval; do not execute

Critical tests:
- ₹799 executes
- ₹25,000 does not execute
- export does not execute
- denied state is unchanged
- no unguarded mutation path exists

Update TODO.md, STATUS.md and AGENTGATE_BOOK.md.
```

---

## Prompt 10 — Human Approval

```text
Act as Builder Engineer.

Implement Volume IV / Phase 6.

Requirements:
- unique pending action id
- exact tool name/arguments persisted
- API exposes pending approval
- Approve executes exact pending action once
- Deny executes nothing
- duplicate approval cannot duplicate mutation
- old approval cannot authorize future action
- timeline records request and human decision

Use native Strands interrupt/resume if Researcher confirmed it is reliable.
Otherwise use the documented safe fallback while preserving all safety invariants.

Tests:
- pause on ₹8,499
- approve
- deny
- duplicate approve
- stale/replayed approval
- state restoration

Update shared files.
```

---

## Prompt 11 — Reviewer Gate 2

```text
Act as Reviewer Agent.

Attack the runtime through Volume IV.

Try:
- prompt-induced bypass
- direct tool invocation
- malformed args
- ₹2000/₹2001
- ₹10000/₹10001
- duplicate approval
- replay approval id
- approve after reset
- concurrent approve/deny
- double refund
- export bypass

Run tests yourself.

Create Builder defects for every flaw.

Gate passes only if no P0/P1 remains and the three core scenarios are demonstrably safe.

Update STATUS.md and AGENTGATE_BOOK.md.
```

---

## Prompt 12 — Fix Gate 2

```text
Act as Builder Engineer.

Fix all open Gate 2 P0/P1 issues in severity order.

For every issue:
reproduce -> regression test -> root-cause fix -> focused tests -> full relevant regression.

Do not add features.

Update shared project files and request re-review.
```

---

## Prompt 13 — Control-Room UI

```text
Act as Builder Engineer.

Implement Volume V / Phase 7.

Desktop-first control room:
- Scenario A/B/C preset buttons
- prompt input
- Run
- Reset
- live execution timeline
- actor labels: AGENT / CEDAR / HUMAN / TOOL
- ALLOW / APPROVAL / DENY states
- tool arguments
- policy reason
- approval card
- final business-state result

Do not add auth, billing, settings, complex landing pages.

Make Scenario B the visual centerpiece.

Run frontend build/typecheck.
Update shared project files.
```

---

## Prompt 14 — Policy Test Bench

```text
Act as Builder Engineer.

Implement Volume V / Phase 8.

Add one-click real policy tests:
- lookup_order -> ALLOW
- refund ₹799 -> ALLOW
- refund ₹8,499 -> REQUIRE_APPROVAL
- refund ₹25,000 -> DENY
- export_customers -> DENY

Display 5/5 PASS only from actual policy evaluation.

Never hardcode a passing result in the frontend.

Test and update shared project files.
```

---

## Prompt 15 — SAM + LocalStack

```text
Act as Researcher Agent first.

Research the minimum reliable SAM CLI + LocalStack setup that materially improves the AgentGate demo.

Define:
- exact emulated service/action
- minimal template
- local commands
- setup risks
- fallback

Create Builder tasks only after research.

Then Builder Engineer implements only the approved minimum.

Do not add services for appearances.
```

---

## Prompt 16 — OpenSearch Stretch Gate

```text
Read STATUS.md first.

If ANY core scenario, approval flow, policy test, backend test or frontend build is failing:
STOP. Do not implement OpenSearch.

If core is fully green:
Research and implement a minimal audit index containing:
- run id
- actor
- tool
- argument summary
- policy decision
- human decision
- executed boolean
- timestamp

Add simple search for denied/approved actions.

OpenSearch must never destabilize the core.
```

---

## Prompt 17 — Final Reviewer

```text
Act as Reviewer Agent.

Run the release audit:
- backend tests
- frontend typecheck/build
- complete policy matrix
- Scenario A
- Scenario B approve and deny
- Scenario C
- reset
- approval replay
- denied-mutation checks
- Policy Test Bench
- README truthfulness

Create defects for anything broken or misleading.

Return exactly one verdict:
RELEASE_READY
or
RELEASE_BLOCKED
```

---

## Prompt 18 — Fix Loop

```text
Act as Builder Engineer.

If RELEASE_BLOCKED:
fix release-blocking defects only.

For each:
reproduce -> regression test -> fix -> full relevant tests -> mark REVIEW.

Request Reviewer re-test.

Repeat until Reviewer returns RELEASE_READY.

Do not add features in this loop.
```

---

## Prompt 19 — Submission Freeze

```text
Feature freeze.

Prepare:
- accurate README
- architecture documentation
- setup commands
- AI-tool disclosure
- demo reset script
- exact 3-minute demo script
- screenshots if useful

TODO.md:
- DONE only for implemented work
- DEFERRED for nonessential unfinished ideas

STATUS.md must show all submission-critical checks.

AGENTGATE_BOOK.md must contain the full build history by volumes and phases.

Run release verification one last time.

Do not add features.
```
