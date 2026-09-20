# Status

Last updated: 2026-09-20T18:05:00+05:30
Current volume: Volumes II and V built; parts of III and IV built
Current phase: The three demo scenarios run end to end through the UI. Review Gate 1 not yet run.

## Working

- **Cedar owns authority.** `policies/` holds the schema, the execute policy set, the
  approval policy set and the entity graph. `CedarPolicyEngine` parses and validates all
  of it at startup and answers one proposed tool call at a time with ALLOW,
  REQUIRE_APPROVAL or DENY. No model participates in any decision.
- The complete policy matrix passes: lookups and recorded email ALLOW; refund 0..2000
  ALLOW; 2001..10000 REQUIRE_APPROVAL; above 10000 DENY; `export_customers` explicitly
  forbidden. Both rupees either side of both limits are covered.
- **The gate is non-bypassable in the application.** `AuthorityGateway` is the only
  holder of `BusinessTools`. Its public surface is pinned by a test, the tools reference
  is name-mangled, and dispatch is an explicit table rather than `getattr`.
- **Approval is exactly-once.** A frozen `PendingAction` recomputes its own digest, so a
  record with rewritten arguments cannot be constructed. `claim` is one locked
  PENDING-to-CLAIMED transition guarded by version and digest. Eight concurrent
  approvals produce exactly one refund.
- **HTTP surface over the gate**: `/api/actions`, `/api/pending`, `/api/pending/{id}`,
  `/api/timeline`, `/api/state`, `/api/reset`, `/api/policy-test`, `/api/tools`, plus
  `/health`. No route reaches a business tool directly.
- The Policy Test Bench endpoint evaluates all five required cases through the real
  engine, derives its own pass count, and mutates nothing.
- The timeline records AGENT / OPERATOR / CEDAR / HUMAN / TOOL. `TOOL_EXECUTED` is
  appended only after the store returns a receipt.
- Everything from Volumes I: FastAPI factory, typed `/health`, immutable domain models,
  deterministic seeds for ORD-1001/1002/1003, `InMemoryStore` with atomic single-refund
  semantics, and the five business tools.
- **The control room runs the demo.** Scenario A/B/C buttons propose real tool calls,
  the timeline renders live events with actor labels, the approval card approves or
  denies one exact action, Reset restores the demo, and the Policy Test Bench reports
  5/5 from real evaluations. 11 browser tests drive these exact clicks.

## Broken or Missing

- **No agent.** Strands is not installed and Phase 4 has not run. Nothing in the system
  currently proposes a tool call on its own; every proposal is typed by an operator, and
  the timeline labels it `OPERATOR` for exactly that reason.
- **No native Strands interrupt/resume.** The approval path is the documented
  application-level fallback. The digest envelope binds a gateway-issued `proposal_id`
  and a reset `epoch` instead of a Strands tool-use ID and interrupt ID. When Strands
  lands, both must be added and `DIGEST_VERSION` incremented.
- **The approval store is in-process.** V4-P6B's restart and session-restoration
  criterion is not met and is not claimed. A process restart loses all pending actions.
- No SAM/LocalStack, no OpenSearch.
- PowerShell blocks `npm.ps1`; Windows commands must use `npm.cmd`.
- Docker engine access and AWS SAM CLI were unavailable in earlier probes and were not
  rechecked; neither is a prerequisite for anything built so far.

## Tests

- command: `.\backend\.venv\Scripts\python.exe -m pytest backend/tests`
  result: PASS - 178 tests. Breakdown: 54 policy, 47 gateway/API, 45 business tools,
  23 storage/model, 9 health/config.
- command: `$env:E2E_BASE_URL='http://127.0.0.1:4173'; npm.cmd run test:e2e`
  result: PASS - 11 browser checks against the live API. Covers all three scenarios
  through the UI, approve and deny, OPERATOR-not-AGENT attribution, the 5/5 bench with
  zero business mutation, reset, offline handling and the mobile approval card.
- command: `.\backend\.venv\Scripts\python.exe -m pytest backend/tests/policy`
  result: PASS - 54 checks covering the full boundary matrix, malformed and hostile
  arguments, unknown actions, startup validation failures, engine-error fail-closed
  behaviour, `Long` overflow, and principal/resource scoping.
- command: policy mutation check (manual)
  result: PASS - changing the agent limit from 2000 to 3000 in `execute.cedar` fails the
  matrix at the 2001 case. File restored and suite re-run green.
- command: empty-policy check (automated)
  result: PASS - emptying both policy sets turns every previously allowed action into
  DENY, proving no threshold lives in Python.
- command: live HTTP run against `uvicorn` on 127.0.0.1:8000
  result: PASS - refund 799 ALLOW/executed; refund 8499 REQUIRE_APPROVAL with ORD-1002
  unchanged; approve executes once; second approve returns DENY/ALREADY_DECIDED; refund
  25000 DENY/NO_MATCHING_PERMIT; export DENY/EXPLICIT_FORBID; policy bench 5/5.
- command: `npm.cmd test` (frontend)
  result: PASS - 11 health-client tests, including rejection of the previous
  `phase=foundation` payload.
- command: `npm.cmd run build` (frontend)
  result: PASS - TypeScript check and Vite production bundle.


## Open P0/P1 Defects

- None known. Independent review has not run. Builder self-verification is not a
  security clearance, and the three safety claims that matter most — non-bypassable
  gate, exactly-once approval, zero mutation on denial — have only been attacked by the
  engineer who wrote them.

## Decisions

- `cedarpy==4.12.0` pinned and added to `backend/pyproject.toml` and `uv.lock`. The
  Researcher's proposed schema and policy shapes validated against it unmodified.
- Policies carry `@id("...")` annotations so the audit trail names
  `allow_refund_within_agent_limit` rather than `policy1`.
- A refund of ₹0 is authorized by Cedar and rejected by the domain as meaningless. This
  follows the existing Phase 2 decision that Cedar owns authority and the domain owns
  business validity. A test asserts both halves.
- An explicit `forbid` is never escalated to a human. The gate checks for determining
  policies before considering the approval path, so `export_customers` cannot become a
  question someone might say yes to.
- Cedar diagnostics errors alongside an `Allow` are treated as untrustworthy and become
  DENY, because that Allow was decided by an incomplete policy set.
- The gateway's public methods never raise on caller input; an unknown pending ID is a
  verdict, not an exception, so the API cannot turn a refused approval into a 500.
- `Actor.OPERATOR` was added so a tool call typed by a person is never recorded as
  something the model decided to do.
- `send_email` remains ALLOW only while it stays recorded-only. A test asserts
  `delivered: false`, and the permit carries a comment saying the permit is void if a
  real provider is wired in.

## Risks

- The three headline safety properties have not been independently reviewed. Review
  Gate 1 should cover Volumes I and II together, and should re-run the mutation and
  empty-policy checks rather than trusting this file.
- `cedarpy` is maintained outside the AWS/Cedar team. It is pinned; a
  `cedar-policy-cli` subprocess fallback behind the same `PolicyEngine` interface
  remains the documented escape hatch.
- Strands is fast-moving (1.56.0 on 2026-09-15). Pin it and write characterization tests
  before building the UI on its interrupt behaviour.
- In-process state means a single worker. Multiple API workers would break both the
  approval store and the event log; this must be documented in the run instructions and
  enforced before any deployment.
- Adding a public method to `AuthorityGateway` widens the attack surface. The pinned
  surface test makes that visible, but only if reviewers read why it failed rather than
  updating the list.

## Next Action

The demo is submittable: rehearse it twice from a clean reset using `DEMO.md`.

After submission, Review Gate 1 over Volumes I and II. The Reviewer should independently
re-run the policy matrix, the empty-policy check and the boundary mutation check, then
attack the gateway's exactly-once and zero-mutation claims. Phase 4 (Strands) follows,
and its intervention must delegate to the existing `AuthorityGateway` rather than
introducing a second execution path.

## Latest Review

Gate: Not started
Verdict: Not reviewed
Tests executed: Builder verification only - 178 backend checks, 11 frontend unit checks,
11 browser checks against the live API, typecheck and production build, plus a live HTTP
run of all three scenarios. No independent reviewer gate yet.
P0: 0
P1: 0
P2: 0
Next required action: Review Gate 1 covering foundation and authority.

## Latest Commit

- `AgentGate/` is now its own Git repository. See `git log` for the current hash.
