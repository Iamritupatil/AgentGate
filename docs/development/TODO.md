# TODO

Statuses: `TODO`, `IN_PROGRESS`, `BLOCKED`, `REVIEW`, `DONE`, `DEFERRED`.

## Volume I - Foundation

### V1-P1 - Repository and runtime scaffold

- ID: V1-P1
- Volume: I - Foundation
- Phase: 1
- Owner: Builder Engineer
- Status: REVIEW
- Goal: Create the smallest runnable FastAPI backend and React/Vite/TypeScript control-room shell.
- Files: `backend/`, `frontend/`, per-service `.env.example` files, `.gitignore`, dependency locks and test configuration, `README.md`
- Acceptance Criteria: `/health` passes; backend tests pass; frontend typecheck/build passes; dependencies are pinned; Windows uses documented `npm.cmd` command; README runtime requirement matches the supported/tested Python version.
- Blockers: None for implementation. Builder acceptance checks are green; independent Gate 1 review follows the domain and Cedar phases.
- Reviewer Link: [Phase 1 build evidence](AGENTGATE_BOOK.md#phase-1-build-evidence). Reviewer verdict pending.
- Acceptance Evidence: 14 backend tests, 10 client tests, 4 live-browser checks pass; TypeScript and production build pass; API and built-preview proxy return matching live health. Screenshots inspected at 1440px and 390px widths.

### V1-P2 - Domain data and business tools

- ID: V1-P2
- Volume: I - Foundation
- Phase: 2
- Owner: Builder Engineer
- Status: REVIEW
- Goal: Implement storage abstraction, deterministic seed/reset, and exactly five business tools without Cedar or Strands.
- Files: `backend/app/domain/`, `backend/app/tools/`, `backend/tests/`
- Acceptance Criteria: Seed orders 1001/1002/1003; lookup tools work; refund invariants prevent unpaid, over-, and double refunds; successful refund mutates once; email is recorded only; export returns data only when called directly in domain tests; reset is deterministic.
- Blockers: None for implementation. Tools remain internal until the policy gate exists; independent review follows Phase 3.
- Reviewer Link: [Phase 2 build evidence](AGENTGATE_BOOK.md#phase-2-build-evidence). Reviewer verdict pending.
- Acceptance Evidence: 45 business-tool tests and 23 storage/model tests pass; full backend suite 86/86 (including 18 API/config checks). Verified concurrent single-refund execution, zero change on rejected/failed actions, recorded-only email, detached exports, deterministic reset, and health-only public API.

## Volume II - Deterministic Authority

### V2-P3A - Cedar evaluator adapter

- ID: V2-P3A
- Volume: II - Deterministic Authority
- Phase: 3
- Owner: Builder Engineer
- Status: REVIEW
- Goal: Wrap pinned `cedarpy==4.12.0` behind the research contract's `PolicyEngine` interface.
- Files: `backend/app/policy/engine.py`, `backend/app/policy/contract.py`, `backend/app/policy/arguments.py`, `backend/pyproject.toml`, `backend/uv.lock`, `backend/tests/policy/`
- Acceptance Criteria: Policies and schema parse/validate once at startup; malformed policy/schema fails startup; runtime evaluation errors fail closed; result includes decision, stable reason code, determining policies, and engine diagnostics.
- Blockers: None for implementation. Independent Gate 1 review outstanding.
- Reviewer Link: [Phase 3 build evidence](AGENTGATE_BOOK.md#phase-3-build-evidence). Reviewer verdict pending.
- Acceptance Evidence: `cedarpy==4.12.0` installed and pinned. Startup parses the schema, both policy sets and the entity graph, and `validate_policies` runs against the schema. Seven startup-failure tests cover an unparsable policy, an undeclared action name, a policy type error, a malformed schema and a missing file. Evaluation failures and Cedar diagnostics errors both return DENY/`POLICY_ENGINE_ERROR` instead of raising; `@id` annotations surface stable determining-policy names.

### V2-P3B - Cedar schema and policy sets

- ID: V2-P3B
- Volume: II - Deterministic Authority
- Phase: 3
- Owner: Builder Engineer
- Status: REVIEW
- Goal: Encode execute and approval-request permissions with typed `Long` refund amounts.
- Files: `policies/agentgate.cedarschema`, `policies/execute.cedar`, `policies/request_approval.cedar`, `policies/entities.json`
- Acceptance Criteria: Lookups allowed; recorded demo email explicitly allowed; refund 0..2000 executable; refund 2001..10000 not executable but approval-requestable; refund above 10000 denied; export explicitly forbidden; negative/non-integer/bool amounts rejected before Cedar.
- Blockers: None for implementation. Reconfirm recorded-only `send_email` assumption before real outbound integration.
- Reviewer Link: [Phase 3 build evidence](AGENTGATE_BOOK.md#phase-3-build-evidence). Reviewer verdict pending.
- Acceptance Evidence: All criteria pass in the matrix. Authority is proven to live in the files, not in Python: emptying both policy sets turns every previously allowed action into DENY, and changing the ceiling from 2000 to 3000 fails the matrix. Permits name one exact principal and one exact store, so a different agent or resource has no authority.

### V2-P3C - Complete policy boundary matrix

- ID: V2-P3C
- Volume: II - Deterministic Authority
- Phase: 3
- Owner: Builder Engineer
- Status: REVIEW
- Goal: Prove the three-way policy decision independently of any model.
- Files: `backend/tests/policy/test_matrix.py`, `backend/tests/policy/test_engine.py`, `backend/tests/policy/conftest.py`
- Acceptance Criteria: Tests cover lookup order/customer, 799, 2000, 2001, 8499, 10000, 10001, 25000, export, unknown action, malformed amount, missing amount, and policy engine error; all expected outcomes pass.
- Blockers: None for implementation.
- Reviewer Link: [Phase 3 build evidence](AGENTGATE_BOOK.md#phase-3-build-evidence). Reviewer verdict pending.
- Acceptance Evidence: 54 policy checks pass, including every listed boundary plus 1999/9999 either side of each limit. An autouse fixture asserts `strands` was never imported, so the determinism claim is enforced rather than stated. Amounts that overflow Cedar's `Long` fail closed to DENY.

## Volume III - Agent Runtime

### V3-P4 - Strands agent construction

- ID: V3-P4
- Volume: III - Agent Runtime
- Phase: 4
- Owner: Builder Engineer
- Status: TODO
- Goal: Construct a pinned Strands agent with exactly five registered tools and no policy limits in its prompt.
- Files: `backend/app/agent/`, `backend/tests/agent/`, backend dependency lock
- Acceptance Criteria: `strands-agents[cedar]==1.56.0`; `SequentialToolExecutor`; exact tool-name assertion; construction tests use a fake model/no live call; tools rely on application state and never invent success.
- Blockers: V2-P3C and Review Gate 1.
- Reviewer Link: Pending.

### V3-P5A - Three-way authorization intervention

- ID: V3-P5A
- Volume: III - Agent Runtime
- Phase: 5
- Owner: Builder Engineer
- Status: TODO
- Goal: Intercept every Strands tool use before execution and return `Proceed`, `Confirm`, or `Deny` from one fail-closed custom intervention.
- Files: `backend/app/agent/authorization.py`, `backend/app/policy/`, `backend/app/events/`
- Acceptance Criteria: `BeforeToolCallEvent.tool_use` name/input/id captured; every call emits proposed and policy events; ALLOW proceeds; DENY returns structured feedback before mutation; REQUIRE_APPROVAL interrupts before mutation; unknown/malformed calls deny; handler errors deny.
- Blockers: V3-P4; see Strands research note.
- Reviewer Link: Pending.

### V3-P5B - Non-bypassable registered tool boundary

- ID: V3-P5B
- Volume: III - Agent Runtime
- Phase: 5
- Owner: Builder Engineer
- Status: IN_PROGRESS
- Status note: the application half is built; the Strands half is not.
- Goal: Ensure programmatic direct tool calls cannot reach raw mutators without policy/one-time authorization.
- Files: `backend/app/services/gateway.py`, `backend/tests/gateway/`
- Acceptance Criteria: Registered mutating tools call a gated application service; raw mutators are not registered/exported; `agent.tool.refund_order(...)` cannot bypass the gate; 799 executes once; 25000 and export cause zero mutation.
- Blockers: V3-P5A for the Strands-side binding only.
- Reviewer Link: [Phase 3B build evidence](AGENTGATE_BOOK.md#phase-3b-build-evidence). Reviewer verdict pending.
- Done: `AuthorityGateway` is the only holder of `BusinessTools`; the reference is name-mangled and the tool table is an explicit dict, so a tool name cannot select an arbitrary attribute. A test pins the gateway's entire public surface, so a new public method is a deliberate decision rather than an accident. 799 executes once; 25000 and export mutate nothing.
- Remaining: once Strands is registered, its tool wrappers must call this gateway and consume a one-time capability keyed to the Strands tool-use ID, and a direct `agent.tool.refund_order` call must be proven unable to bypass it.

## Volume IV - Human Control

### V4-P6A - Exact pending-action record

- ID: V4-P6A
- Volume: IV - Human Control
- Phase: 6
- Owner: Builder Engineer
- Status: REVIEW
- Goal: Persist one immutable pending record for the exact interrupted tool use.
- Files: `backend/app/approvals/models.py`, `backend/app/approvals/store.py`, `backend/tests/gateway/test_approval_safety.py`
- Acceptance Criteria: Record includes pending ID, run/session ID, Strands tool-use ID, tool name, canonical arguments, SHA-256 argument digest, interrupt ID, policy reason, status, version, and timestamps; duplicate identity is rejected.
- Blockers: None for implementation.
- Reviewer Link: [Phase 3B build evidence](AGENTGATE_BOOK.md#phase-3b-build-evidence). Reviewer verdict pending.
- Acceptance Evidence: `PendingAction` is frozen and recomputes its own digest on construction, so a record whose arguments were rewritten cannot be built at all. The digest envelope is `{v, epoch, run_id, proposal_id, tool_name, arguments}` serialized with sorted keys and compact separators. Duplicate pending IDs are rejected by the store.
- Deviation: the envelope binds a gateway-issued `proposal_id` and a reset `epoch` rather than a Strands tool-use ID and interrupt ID, because no agent runtime exists yet. When Strands lands, both must be added to the envelope and `DIGEST_VERSION` incremented.

### V4-P6B - Approve/deny/resume transaction

- ID: V4-P6B
- Volume: IV - Human Control
- Phase: 6
- Owner: Builder Engineer
- Status: IN_PROGRESS
- Status note: the exactly-once approval transaction is built and attacked; native Strands resume is not.
- Goal: Resume the native Strands interrupt while enforcing one exact, one-time approval.
- Files: `backend/app/approvals/store.py`, `backend/app/services/gateway.py`, `backend/app/api.py`, `backend/tests/gateway/`, `backend/tests/test_api.py`
- Acceptance Criteria: Approve compares tool-use ID and canonical digest, atomically transitions pending to approved/consuming, resumes with matching interrupt ID, and executes once; deny cancels; stale/replayed/altered/concurrent decisions execute nothing; restart/session restoration test passes.
- Blockers: V3-P4 and V3-P5A for the native-resume half.
- Reviewer Link: [Phase 3B build evidence](AGENTGATE_BOOK.md#phase-3b-build-evidence). Reviewer verdict pending.
- Done: `claim` is a single locked PENDING to CLAIMED transition guarded by version and digest. Eight concurrent approvals produce exactly one refund and one receipt. Double approval, approve-after-deny, stale version, invented ID and post-reset replay all execute nothing, both through the service and over HTTP. Approval endpoints accept only an ID, a version and a decision; extra `tool` or `arguments` fields in the body are ignored, which is covered by a test.
- Remaining: native Strands interrupt and resume, and durable storage. The approval store is in-process, so the restart/session-restoration criterion is not met and is not claimed.

## Volume V - Experience

### V5-P7 - Control-room UI

- ID: V5-P7
- Volume: V - Experience
- Phase: 7
- Owner: Builder Engineer
- Status: REVIEW
- Goal: Implement the desktop-first scenario runner, truthful timeline, approval card, and reset flow.
- Files: `frontend/src/`, UI tests. The backend side is built: `/api/actions`, `/api/pending`, `/api/pending/{id}`, `/api/timeline`, `/api/state`, `/api/reset`, `/api/policy-test`, `/api/tools`.
- Acceptance Criteria: Scenario presets A/B/C; actor labels; tool arguments and policy reason; approve/deny; loading/error states; rendered outcome comes from backend state; Scenario B is the centerpiece.
- Blockers: None for implementation. Review Gate 2 outstanding.
- Reviewer Link: [Control room build evidence](AGENTGATE_BOOK.md#phase-7-build-evidence). Reviewer verdict pending.
- Acceptance Evidence: 11 browser checks drive the real UI against the real API: all three scenarios, approve and deny, reset, offline handling, and the approval card at 390px. Every rendered outcome comes from `/api/state` and `/api/timeline`, not from local assumptions. Proposals are labelled OPERATOR; a test asserts no AGENT chip appears, because no model ran.

### V5-P8 - Policy Test Bench

- ID: V5-P8
- Volume: V - Experience
- Phase: 8
- Owner: Builder Engineer
- Status: REVIEW
- Goal: Display a one-click 5/5 result derived from real backend Cedar evaluations.
- Files: `backend/app/api.py`, `backend/tests/test_api.py`, frontend test-bench components
- Acceptance Criteria: Five required cases execute through the real policy engine; intentionally failing backend result renders failure; no hardcoded pass count.
- Blockers: None for implementation.
- Reviewer Link: [Phase 3B build evidence](AGENTGATE_BOOK.md#phase-3b-build-evidence). Reviewer verdict pending.
- Done: `POST /api/policy-test` evaluates all five cases through the real engine and counts its own passes; the count is derived, never written down. A test proves the bench changes no business state and creates no pending actions, so it cannot prove a refund is permitted by performing one.
- Done (frontend): the bench renders the backend's own count and marks each case pass or fail from the response. A browser test asserts 5/5, that no case renders as failed, and that no order was refunded by running it.
- Remaining: a test that an intentionally failing backend result renders as a failure rather than a green badge. The render path is driven entirely by `case.passed` and `all_passed`, so it is wired for it.

## Volume VI - Local AWS and Audit

### V6-P9 - SAM/LocalStack research and minimum implementation

- ID: V6-P9
- Volume: VI - Local AWS and Audit
- Phase: 9
- Owner: Researcher Agent -> Builder Engineer
- Status: TODO
- Goal: Research, then implement only one AWS-like action that materially improves the demo.
- Files: `infrastructure/`, `scripts/`, research note, tests
- Acceptance Criteria: Core remains green; minimal service/template/commands documented; Windows/Docker failure fallback works; no appearance-only infrastructure.
- Blockers: V5-P8; Docker engine currently unavailable; SAM CLI missing.
- Reviewer Link: Pending.

### V6-P10 - OpenSearch stretch gate

- ID: V6-P10
- Volume: VI - Local AWS and Audit
- Phase: 10
- Owner: Researcher Agent -> Builder Engineer
- Status: DEFERRED
- Goal: Add searchable audit events only when every core gate is green.
- Files: audit adapter, optional infrastructure, UI search
- Acceptance Criteria: Denied/approved events searchable; optional service failure cannot destabilize the core; fallback remains local event history.
- Blockers: All core scenarios, tests, builds, and V6-P9 must be green.
- Reviewer Link: Pending.

## Volume VII - Review and Hardening

### V7-P11 - Adversarial review

- ID: V7-P11
- Volume: VII - Review and Hardening
- Phase: 11
- Owner: Reviewer Agent
- Status: TODO
- Goal: Attack policy boundaries, mutation safety, direct invocation, approval replay/concurrency, reset, and UI truthfulness.
- Files: review tests/reproductions, `TODO.md`, `STATUS.md`, `AGENTGATE_BOOK.md`
- Acceptance Criteria: Reviewer independently runs the required matrix and scenarios; every defect is reproducible and severity-labelled; gate verdict issued.
- Blockers: V5-P8.
- Reviewer Link: This task.

### V7-P12 - Fix and regression loop

- ID: V7-P12
- Volume: VII - Review and Hardening
- Phase: 12
- Owner: Builder Engineer -> Reviewer Agent
- Status: TODO
- Goal: Fix all P0/P1 root causes and obtain independent re-test.
- Files: affected implementation/tests/docs
- Acceptance Criteria: Each defect has regression evidence; no P0/P1 remains; relevant full suites pass; Reviewer closes issues.
- Blockers: V7-P11 findings.
- Reviewer Link: Pending.

## Volume VIII - Submission

### V8-P13 - Accurate submission documentation

- ID: V8-P13
- Volume: VIII - Submission
- Phase: 13
- Owner: Builder Engineer
- Status: TODO
- Goal: Make README, architecture, setup, disclosure, and reset documentation match the verified implementation.
- Files: `README.md`, docs, reset script, screenshots if useful
- Acceptance Criteria: Clean setup commands tested; optional/deferred services labelled; no unimplemented claim presented as current behavior.
- Blockers: V7-P12.
- Reviewer Link: Pending.

### V8-P14 - Clean reset and demo rehearsal

- ID: V8-P14
- Volume: VIII - Submission
- Phase: 14
- Owner: Builder Engineer -> Reviewer Agent
- Status: TODO
- Goal: Freeze features and prove the exact three-minute demo twice from clean reset.
- Files: demo script, verification evidence, shared project files
- Acceptance Criteria: A, B approve/deny, C, and Policy Test Bench pass twice; final release audit returns `RELEASE_READY`.
- Blockers: V8-P13.
- Reviewer Link: Pending.

## Complete hackathon demo extension

- Status: IN_PROGRESS
- Goal: Generalize AgentGate beyond the refund demo while preserving scenarios, reset, approvals, and the Policy Test Bench.
- Implemented: generic Cedar evaluation API, Policy Studio, non-activating AI drafts, Playground, runtime integration examples, isolated MCP adapter, and EC2 deployment artifacts.
- Remaining: deploy to a user-provided EC2 instance and verify the public smoke tests.
- Acceptance: all local suites and browser flows pass, then public health/evaluation and demo smoke tests pass before `AGENTGATE_LIVE_READY`.
