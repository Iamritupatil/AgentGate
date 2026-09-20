# AgentGate Engineering Book

This file records decisions and evidence without rewriting project history.

## Project Initialization

### State on 2026-09-19

- Present: product README and four agent/build instruction documents.
- Absent: application code, dependency manifests, policies, tests, shared status/task files, and a usable workspace-root Git worktree.
- Created in this initialization: `TODO.md`, `STATUS.md`, and `AGENTGATE_BOOK.md`.
- Current build phase: Volume I, Phase 1.
- No product feature was implemented by the Researcher Agent.

## Volume I - Foundation

### Phase 1 - Repository/runtime scaffold

#### Goal

Create a minimal backend/frontend scaffold with truthful runtime and test evidence.

#### Design

Pending Builder implementation. Python 3.10 is the compatibility floor shared by current Strands 1.56.0 and cedarpy 4.12.0. The existing README's Python 3.12+ statement should be reconciled with the actual supported/tested baseline.

#### Implementation

Not started.

#### Files Changed

- Shared coordination files only: `TODO.md`, `STATUS.md`, `AGENTGATE_BOOK.md`.

#### Commands Run

- `python --version`
- `node --version`
- `npm.cmd --version`
- `docker --version`
- `docker info --format '{{.ServerVersion}}'`
- `sam --version`
- Shared-file structural/encoding audit (task field counts, active-status count, mojibake scan)

#### Tests

- Environment probes recorded in `STATUS.md`; no product tests exist.
- Shared-file audit passed: 18/18 tasks have all required fields, exactly one task is `IN_PROGRESS`, and the new files contain no mojibake markers.

#### Failures Encountered

- PowerShell execution policy blocked `npm.ps1`; `npm.cmd` works.
- Docker client exists but engine access failed.
- SAM CLI is absent.
- Workspace root is not a usable Git worktree.

#### Fixes

Pending Builder implementation. Use `npm.cmd` in Windows instructions unless execution policy is deliberately changed.

#### Reviewer Feedback

Not reviewed.

#### Final State

IN_PROGRESS.

#### Lessons

Do not make Docker, SAM, Cedar, or Strands prerequisites for the Phase 1 health shell.

### Phase 2 - Domain data and business tools

Status: Not started. See `V1-P2`.

## Volume II - Deterministic Authority

### Phase 3 - Cedar schema, policies, and three-way gate

Status: Built and self-verified; independent Review Gate 1 outstanding.
See [Phase 3 build evidence](#phase-3-build-evidence) and `V2-P3A` through `V2-P3C`.

## Volume III - Agent Runtime

### Phase 4 - Strands agent

Status: Research contract complete; implementation not started. See `V3-P4`.

### Phase 5 - Intercept every tool call

Status: Split. The application-level interception point is built and attacked
(`AuthorityGateway`); the Strands intervention that must call it is not, because
Phase 4 has not run. See [Authority gateway build evidence](#phase-3b-build-evidence),
`V3-P5A` and `V3-P5B`.

## Volume IV - Human Control

### Phase 6 - Pause, approve, deny, resume, and idempotency

Status: The pending record and the exactly-once approve/deny transaction are built
and attacked. Native Strands resume and durable storage are not, so the
restart/session-restoration criterion is not met. See
[Authority gateway build evidence](#phase-3b-build-evidence), `V4-P6A` and `V4-P6B`.

## Volume V - Experience

### Phase 7 - Control-room UI

Status: Not started. See `V5-P7`.

### Phase 8 - Policy Test Bench

Status: Backend built; `POST /api/policy-test` runs all five cases through the real
engine and derives its own pass count. The frontend component is not started.
See [Authority gateway build evidence](#phase-3b-build-evidence) and `V5-P8`.

## Volume VI - Local AWS and Audit

### Phase 9 - SAM and LocalStack

Status: Not researched because the core is not green. Docker engine is unavailable and SAM CLI is missing locally. See `V6-P9`.

### Phase 10 - OpenSearch

Status: DEFERRED because the core is not green. See `V6-P10`.

## Volume VII - Review and Hardening

### Phase 11 - Adversarial review

Status: Not started. See `V7-P11`.

### Phase 12 - Fix loop and regression

Status: Not started. See `V7-P12`.

## Volume VIII - Submission

### Phase 13 - Documentation and README

Status: Not started. See `V8-P13`.

### Phase 14 - Reset, rehearse, and record

Status: Not started. See `V8-P14`.

---

### Research Note - Cedar local authorization for AgentGate

#### Question

What current Cedar policy/schema syntax, Python-local evaluator, request model, and two-check policy design should AgentGate use to produce ALLOW, REQUIRE_APPROVAL, and DENY deterministically?

#### Current Project Context

AgentGate is documentation-only and is about to enter Volume I. The future policy layer must support two deterministic Cedar checks, run locally on Windows/Python, validate at startup, and remain independent of the LLM. Required outcomes are lookup ALLOW; refund 0..2000 ALLOW; refund 2001..10000 REQUIRE_APPROVAL; larger refund DENY; export DENY.

#### Sources Checked

Checked 2026-09-19:

- [Cedar authorization algorithm](https://docs.cedarpolicy.com/auth/authorization.html) - official; default deny, forbid precedence, diagnostics.
- [Cedar policy syntax](https://docs.cedarpolicy.com/policies/syntax-policy.html) - official; `permit`, `forbid`, scope, `when`, `unless`.
- [Cedar schema](https://docs.cedarpolicy.com/schema/schema.html) - official; Cedar and JSON schema formats, typed action applicability/context.
- [Cedar data types](https://docs.cedarpolicy.com/policies/syntax-datatypes.html) and [operators](https://docs.cedarpolicy.com/policies/syntax-operators.html) - official; `Long` integer range and numeric comparisons.
- [Cedar Rust repository](https://github.com/cedar-policy/cedar) - official engine/CLI source.
- [cedarpy 4.12.0](https://pypi.org/project/cedarpy/) - maintained third-party Python binding; wraps Cedar engine 4.12.0, supports Windows x86_64 and Python 3.10-3.14, but explicitly is not supported by AWS or the Cedar team.
- [Strands Cedar Authorization](https://strandsagents.com/docs/user-guide/concepts/agents/interventions/cedar-authorization/) - official Strands integration and mapping; useful reference but exposes only two-state `Proceed | Deny` in Python.

#### Findings

1. Cedar itself returns only `Allow` or `Deny`. AgentGate's third state must remain the documented two-request composition.
2. Cedar is default-deny: absent a matching permit, the result is Deny. Any matching `forbid` overrides permits. Use an explicit forbid for `export_customers` so diagnostics state the security intent; retain default deny for unknown actions and over-limit refunds.
3. Refund amounts must be Cedar `Long` values. Application validation must reject booleans, strings, floats, missing values, and negative values before request construction. Do not represent money as float.
4. Cedar-format schemas are currently recommended by Cedar docs and are more readable than JSON for this small model.
5. The current Python-local practical option is `cedarpy==4.12.0`. It provides `PolicySet.from_str`, `Schema.from_str`, `validate_policies`, `is_authorized`, `Decision`, and diagnostics. It has current Windows wheels but is third-party.
6. The official Cedar repository offers the Rust crate and CLI, but not an official Python runtime binding. A subprocess to a pinned `cedar-policy-cli` binary is the safest fallback if cedarpy installation/support becomes a problem, at the cost of packaging and process overhead.
7. Strands' vended `CedarAuthorization` maps tool input into `context.input` and validates generated schemas, but its Python `before_tool_call` contract returns only `Proceed | Deny`; it cannot on its own express AgentGate's approval state.
8. The written architecture does not specify `send_email`. Because Phase 2 explicitly defines it as a safe recorded demo action, the smallest coherent prototype policy is an explicit ALLOW while it remains internal-only. Switching to a real email provider invalidates that decision.

Proposed minimal Cedar schema shape:

```cedar
namespace AgentGate {
  entity Agent;
  entity Store;

  action lookup_order appliesTo {
    principal: Agent,
    resource: Store,
    context: { input: { order_id: String } }
  };

  action lookup_customer appliesTo {
    principal: Agent,
    resource: Store,
    context: { input: { customer_id: String } }
  };

  action refund_order appliesTo {
    principal: Agent,
    resource: Store,
    context: { input: { order_id: String, amount: Long } }
  };

  action request_refund_approval appliesTo {
    principal: Agent,
    resource: Store,
    context: { input: { order_id: String, amount: Long } }
  };

  action send_email appliesTo {
    principal: Agent,
    resource: Store,
    context: { input: { customer_id: String, subject: String, body: String } }
  };

  action export_customers appliesTo {
    principal: Agent,
    resource: Store,
    context: { input: {} }
  };
}
```

Proposed policy behavior:

```cedar
permit (
  principal == AgentGate::Agent::"support-agent",
  action in [
    AgentGate::Action::"lookup_order",
    AgentGate::Action::"lookup_customer",
    AgentGate::Action::"send_email"
  ],
  resource == AgentGate::Store::"demo"
);

permit (
  principal == AgentGate::Agent::"support-agent",
  action == AgentGate::Action::"refund_order",
  resource == AgentGate::Store::"demo"
)
when {
  context.input.amount >= 0 &&
  context.input.amount <= 2000
};

permit (
  principal == AgentGate::Agent::"support-agent",
  action == AgentGate::Action::"request_refund_approval",
  resource == AgentGate::Store::"demo"
)
when {
  context.input.amount > 2000 &&
  context.input.amount <= 10000
};

forbid (
  principal,
  action == AgentGate::Action::"export_customers",
  resource
);
```

#### Recommended Approach

Pin `cedarpy==4.12.0` (or receive the exact pin through `strands-agents[cedar]==1.56.0` and assert it in the lock), parse policies once with `PolicySet.from_str`, parse the Cedar schema with `Schema.from_str`, and fail application startup if `validate_policies` fails.

For each proposed tool call:

1. Normalize and validate the input into canonical typed values.
2. Evaluate the actual tool action against the execute policy set.
3. If allowed, return ALLOW.
4. If denied and the tool is `refund_order`, evaluate the same principal/resource/context with action `request_refund_approval` against the approval policy set.
5. If the second request is allowed, return REQUIRE_APPROVAL; otherwise return DENY.
6. Any exception, Cedar evaluation error, unknown tool/action, or invalid input returns DENY with a stable reason code.

Rejected alternatives:

- LLM classification or prompt limits: nondeterministic and violates the architecture.
- One large Python `if amount` gate presented as Cedar: does not prove Cedar owns authority.
- A broad permit plus refund forbids: easier to accidentally permit new tools; explicit narrow permits are safer.
- Vended Strands `CedarAuthorization` as the entire three-way engine: only models Proceed/Deny.
- AWS Verified Permissions for the core: adds network/cloud setup without improving the local demo.
- Calling the Cedar CLI per request as the primary path: avoidable packaging/latency complexity for a hackathon prototype.

#### API / Interface Contract

Builder should expose this application-owned boundary (names may vary only mechanically):

```python
class GateDecision(str, Enum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"

@dataclass(frozen=True)
class AuthorizationRequest:
    principal_id: str
    tool_name: str
    resource_type: str
    resource_id: str
    arguments: Mapping[str, object]

@dataclass(frozen=True)
class AuthorizationResult:
    decision: GateDecision
    reason_code: str
    determining_policies: tuple[str, ...]
    errors: tuple[str, ...]

class PolicyEngine(Protocol):
    def evaluate(self, request: AuthorizationRequest) -> AuthorizationResult: ...
```

Mandatory mappings:

- principal: `AgentGate::Agent::"support-agent"`
- resource: `AgentGate::Store::"demo"` for the prototype
- actual tool name -> same-named execute action
- denied `refund_order` -> synthetic action `request_refund_approval`
- arguments -> `context.input`
- amount -> Python `int` excluding `bool`, then Cedar `Long`

Stable reason codes should include: `EXECUTE_PERMITTED`, `APPROVAL_PERMITTED`, `NO_MATCHING_PERMIT`, `EXPLICIT_FORBID`, `INVALID_ARGUMENTS`, `UNKNOWN_ACTION`, and `POLICY_ENGINE_ERROR`.

Acceptance test: the complete matrix in `V2-P3C` passes without constructing or invoking an LLM, and replacing policies with an empty set makes every action DENY.

#### Risks

- Third-party Python binding support and wheel availability. Mitigation: exact pin, lock hashes, install smoke test on the demo Windows machine.
- Policy errors can be ignored during evaluation and change outcomes. Mitigation: schema validation at startup plus fail closed on non-empty Cedar diagnostics errors.
- Two checks can drift if they build different context. Mitigation: construct one immutable normalized request and replace only the action for the second check.
- A future real `send_email` would be over-permitted by the demo policy. Mitigation: keep it recorded-only and make that invariant a test.

#### Fallback

Package a pinned official `cedar-policy-cli` release and call it through a small adapter using JSON request/entity files. Keep the same `PolicyEngine` interface so only the adapter changes. If neither local engine can be made reliable, stop the Cedar phase; do not substitute Python thresholds while claiming Cedar enforcement.

#### Tasks for Builder

- `V2-P3A` - Cedar evaluator adapter and startup validation.
- `V2-P3B` - Typed schema and two policy sets.
- `V2-P3C` - Complete boundary/default-deny/error matrix.

---

### Research Note - Strands interception, denial, pause, and exact resume

#### Question

Can AgentGate intercept a current Strands Python tool call before execution, deny it with structured feedback, pause for human approval, and later resume that same exact call safely?

#### Current Project Context

AgentGate will run one support agent with five tools behind a Python API. The approval flow must pause an 8499 refund before mutation, expose the exact pending action to a UI, and execute it at most once after approval. A 25000 refund and customer export must never mutate or leak state.

#### Sources Checked

Checked 2026-09-19:

- [strands-agents 1.56.0](https://pypi.org/project/strands-agents/1.56.0/) - official PyPI release, published 2026-09-15; Python 3.10+.
- [Python quickstart](https://strandsagents.com/docs/user-guide/quickstart/python/) - official `Agent`, `@tool`, and registration usage.
- [Interventions](https://strandsagents.com/docs/user-guide/concepts/agents/interventions/) - official typed `Proceed`, `Deny`, `Guide`, `Confirm`, `Transform` contract and fail-closed error behavior.
- [BeforeToolCallEvent API](https://strandsagents.com/docs/api/python/strands.hooks.events/) - official `tool_use`, `selected_tool`, `invocation_state`, and `cancel_tool` fields.
- [Interrupts](https://strandsagents.com/docs/user-guide/concepts/interrupts/) - official interrupt ID/reason/response and resume semantics.
- [Human in the Loop](https://strandsagents.com/docs/user-guide/concepts/agents/interventions/human-in-the-loop/) - official ready-made `HumanInTheLoop`, interrupt/resume mode, and session guidance.
- [Tool executors](https://strandsagents.com/docs/user-guide/concepts/tools/executors/) - official concurrent default and `SequentialToolExecutor`.
- [Session management](https://strandsagents.com/docs/user-guide/concepts/agents/session-management/) - official `SnapshotSessionManager`, `LocalFileStorage`, persisted interrupt state, and single-live-writer constraint.
- [Agent API](https://strandsagents.com/docs/api/python/strands.agent.agent/) - official constructor/tool registration and programmatic `agent.tool.<name>` surface.
- [Custom tools and ToolContext](https://strandsagents.com/docs/user-guide/concepts/tools/custom-tools/) - official `@tool(context=True)` injection of the complete tool-use object and invocation state.
- [Strands Cedar Authorization](https://strandsagents.com/docs/user-guide/concepts/agents/interventions/cedar-authorization/) - official two-state Cedar handler.

#### Findings

1. Yes: Strands can pause before a specific tool executes and resume that logical tool execution. `BeforeToolCallEvent` exposes the complete `tool_use` object (name, input, and provider tool-use identity). A hook can call `event.interrupt(name, reason=...)`; the returned `AgentResult` has `stop_reason == "interrupt"` and interrupt objects with unique IDs. Passing `interruptResponse` with that ID re-enters the interrupted hook/tool path.
2. The higher-level current API is an `InterventionHandler.before_tool_call` returning `Proceed`, `Deny`, or `Confirm`. `Deny(reason=...)` cancels execution and gives the model an error result. `Confirm(prompt=...)` uses native interrupt/resume.
3. AgentGate needs one custom intervention because the policy result is three-way. The vended `CedarAuthorization` is useful reference code but returns only `Proceed | Deny`; separately stacking it before an approval handler would short-circuit on the direct-execution deny and never reach approval.
4. Strands defaults to concurrent execution. Under concurrent execution, other non-interrupted tool calls from the same model turn may execute while one call is interrupted. This conflicts with a simple, auditable one-pending-action demo. Configure `SequentialToolExecutor()` explicitly.
5. Per-tool interrupt splits the tool batch across cycles; `AfterToolsEvent` may fire more than once. Event recording must be idempotent and keyed by tool-use/event identity, not append blindly.
6. `SnapshotSessionManager(session_id=..., storage=LocalFileStorage(...))` is the recommended new single-agent persistence path and stores interrupt state. It assumes one live writer per `(session_id, agent_id)` conversation.
7. Native session state is not a transactional business approval ledger. It does not by itself protect duplicate HTTP approval, concurrent approve/deny, stale approval after reset, or crash timing around mutation.
8. Strands exposes programmatic direct tool calls through `agent.tool.<name>(...)`. The application must assume this surface can bypass orchestration-level interventions and make each registered mutating tool call an application-owned gated service rather than a raw repository mutator.
9. `HumanInTheLoop(enable_trust=True)` is inappropriate: trust can bypass later prompts to the same tool and violates approval scoping to one exact action.
10. A decorated tool can request the framework-owned `ToolContext` with `@tool(context=True)`. `tool_context.tool_use["toolUseId"]` lets the registered wrapper consume an application-side one-time capability for precisely the call that the intervention authorized.
11. Current package churn is high. Pin 1.56.0 and add a characterization test around interrupt payloads/resume before relying on undocumented object details.

#### Recommended Approach

Use `strands-agents[cedar]==1.56.0`, `SequentialToolExecutor()`, one agent instance per conversation, and `SnapshotSessionManager` with a unique session ID. Implement an application-owned `AgentGateIntervention(InterventionHandler)` registered first.

For every `before_tool_call`:

1. Copy and normalize `event.tool_use` without mutating it.
2. Emit idempotent `TOOL_PROPOSED` keyed by run ID + tool-use ID.
3. Call the Phase 3 `PolicyEngine`.
4. ALLOW: issue a one-time execution capability for the exact canonical digest and return `Proceed()`.
5. DENY: return `Deny(reason=<structured JSON-safe policy feedback>)` before tool execution.
6. REQUIRE_APPROVAL: persist the immutable pending record, then return a native `Confirm`/interrupt whose reason contains the pending ID, tool-use ID, tool name, exact arguments, digest, and policy reason.
7. On a matching approval response, atomically claim the pending record, issue one one-time capability for the same digest, and let the original call continue. A denial/stale/mismatch returns `Deny` and creates no capability.
8. Define registered mutating tools with `@tool(context=True)`. The wrapper reads `tool_context.tool_use["toolUseId"]` and atomically consumes the server-side capability for that ID and canonical digest before invoking the raw business service. A direct call without a capability fails closed.

Use native interrupt/resume for agent continuity, but keep the authorization and exactly-once source of truth in an AgentGate approval store. A SQLite-backed adapter is the smallest durable demo option because it provides uniqueness and atomic compare-and-set without a separate service; keep an in-memory locked adapter for unit tests.

Rejected alternatives:

- Raw `BeforeToolCallEvent.cancel_tool` for the whole design: supported, but typed interventions communicate intent and precedence more clearly.
- `HumanInTheLoop` on every sensitive tool: does not encode Cedar's dynamic ALLOW/APPROVAL/DENY split by amount.
- `enable_trust=True`: grants broader session-level trust than one pending action.
- Default concurrent executor: makes batch pause behavior harder to explain and allows unrelated calls to execute during another call's interrupt.
- Treating the UI's pending payload as executable truth: permits argument substitution/replay.
- Executing the saved tool by name from the approval endpoint: can diverge from the interrupted agent call and creates a second execution path.
- Session snapshots as the only idempotency mechanism: no atomic business transition guarantee.

#### API / Interface Contract

Agent construction:

```python
agent = Agent(
    model=model,
    tools=[
        lookup_order,
        lookup_customer,
        refund_order,
        send_email,
        export_customers,
    ],
    interventions=[agentgate_intervention],
    tool_executor=SequentialToolExecutor(),
    session_manager=SnapshotSessionManager(
        session_id=session_id,
        storage=LocalFileStorage(session_directory),
    ),
)
```

Registered mutation boundary:

```python
@tool(context=True)
def refund_order(
    order_id: str,
    amount: int,
    tool_context: ToolContext,
) -> dict:
    tool_use_id = tool_context.tool_use["toolUseId"]
    capability_store.consume_exactly_once(
        tool_use_id=tool_use_id,
        tool_name="refund_order",
        arguments={"order_id": order_id, "amount": amount},
    )
    return refund_service.refund_once(
        operation_id=tool_use_id,
        order_id=order_id,
        amount=amount,
    )
```

`consume_exactly_once` must canonicalize and compare the same versioned digest used by the intervention. The raw `refund_service` must not be registered as a Strands tool.

Pending action minimum shape:

```text
pending_action_id: UUID
run_id: string
session_id: string
strands_tool_use_id: string
interrupt_id: string
tool_name: string
arguments: canonical JSON object
arguments_sha256: lowercase hex SHA-256
policy_reason_code: string
status: PENDING | CLAIMED | EXECUTED | DENIED | EXPIRED
version: integer
created_at / decided_at / executed_at: UTC timestamps
```

Canonical digest input must include a versioned envelope, not only arguments:

```json
{"v":1,"session_id":"...","tool_use_id":"...","tool_name":"refund_order","arguments":{"amount":8499,"order_id":"ORD-1002"}}
```

Serialize with UTF-8, sorted keys, and compact separators before SHA-256. Approval APIs accept only `pending_action_id`, expected `version`, and decision; they never accept replacement tool arguments.

Structured denial feedback must be JSON-safe and include at least:

```json
{
  "type": "policy_denial",
  "decision": "DENY",
  "reason_code": "NO_MATCHING_PERMIT",
  "tool_name": "refund_order",
  "retryable": false
}
```

Builder characterization/acceptance tests:

- `BeforeToolCallEvent` exposes and preserves the provider tool-use ID/name/input under pinned 1.56.0.
- 799 returns `Proceed` and registered tool executes once.
- 8499 returns interrupt before mutation; restart restores it; matching approval resumes the same tool-use ID/digest and executes once.
- Denial response cancels and returns structured feedback.
- 25000 and export return `Deny` and never enter the raw mutator.
- Duplicate, concurrent, stale, altered, wrong-session, and post-reset approval attempts execute zero additional mutations.
- `agent.tool.refund_order(...)` without an exact one-time capability cannot mutate.
- A model turn proposing multiple tools remains sequential and does not execute a later mutation past an interrupted/denied earlier call.

#### Risks

- Interrupt reason/response structure may evolve across Strands releases. Mitigation: exact pin and characterization tests.
- A crash after business mutation but before marking EXECUTED can cause ambiguity. Mitigation: make refund idempotent on a unique operation/pending ID and commit mutation plus execution record atomically where possible.
- File snapshot and approval DB paths can diverge after reset. Mitigation: reset both under one application-level reset lock and increment a reset/session epoch included in the digest.
- Multiple API workers violate the session manager's single-writer assumption. Mitigation: one demo worker; document it and reject overlapping runs per session.
- Direct access to raw tool functions creates bypasses. Mitigation: private raw services plus capability-consuming registered wrappers and security tests.

#### Fallback

If the pinned native interrupt cannot be restored reliably across HTTP requests, do not reconstruct or replay model output. Persist the exact proposed action, cancel the Strands call before execution, and let the approval endpoint execute that saved action through the same one-time-capability gateway. Clearly label this as an application-level resume rather than native Strands resume. Preserve tool-use ID, canonical digest, idempotency, and zero-mutation denial invariants.

#### Tasks for Builder

- `V3-P4` - pinned agent construction and exact tool registration.
- `V3-P5A` - fail-closed three-way intervention and timeline events.
- `V3-P5B` - capability-protected registered tool boundary.
- `V4-P6A` - immutable pending-action persistence.
- `V4-P6B` - atomic approve/deny/native-resume lifecycle and adversarial tests.

---

<a id="phase-1-build-evidence"></a>

## Volume I — Phase 1 build evidence (2026-09-19)

### Goal

Implement the first scaffold increment from `02_CODEX_COMMANDS.md`: FastAPI,
`/health`, centralized settings, backend tests, React/Vite/TypeScript, a minimal
control-room shell, environment examples and dependency files.

### Design

The backend uses `create_app(settings)` to isolate configuration and future runtime
composition. Pydantic settings read a backend-relative `.env` with `AGENTGATE_`
variables. `/health` reports API liveness with a typed, non-cacheable response;
it makes no policy/agent readiness claim. CORS accepts only configured local origins.

The frontend uses a Vite `/api` proxy for both development and built preview.
The health client rejects non-2xx, invalid JSON, wrong shape and network errors,
applies a five-second timeout and supports cancellation. The UI rechecks every
15 seconds and supports manual retry. Scenario choices edit local prompt text;
outcome labels are intended targets, Run is disabled, and the timeline is empty.

### Implementation

FastAPI application factory and health schema; validated settings; pytest/httpx
checks; React control room with accessible scenario buttons, editable prompt,
planned authority diagram, connection feedback, keyboard focus and mobile layout.
Added actual health-client unit tests and four Playwright checks of the running
production build. No Cedar, Strands, business mutation or approval code was added.

### Files Changed

- `backend/app/{__init__,config,main}.py`, `backend/tests/`.
- `backend/pyproject.toml`, `backend/uv.lock`, `backend/.python-version`, `backend/.env.example`.
- `frontend/src/`, `frontend/tests/control-room.spec.ts`, `frontend/playwright.config.ts`.
- `frontend/package.json`, `frontend/package-lock.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/index.html`, `frontend/.env.example`.
- `.gitignore`, `README.md`, `TODO.md`, `STATUS.md`, this appended book entry.
- Ignored verification output: `artifacts/browser/` desktop/mobile PNGs.

### Commands Run

From the root unless indicated otherwise:

```powershell
uv sync --project backend
.\backend\.venv\Scripts\python.exe -m pytest backend/tests
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

From `frontend/`:

```powershell
npm.cmd install --no-fund --no-audit
npm.cmd install --save-dev --save-exact @playwright/test --no-fund --no-audit
npm.cmd run build
npm.cmd test
npm.cmd run preview
$env:E2E_BASE_URL = 'http://127.0.0.1:4173'
npm.cmd run test:e2e
npm.cmd run typecheck
```

Also checked API health directly and through the Vite preview proxy; inspected the
desktop and mobile screenshot artifacts. Network/package operations and Python
access required sandbox escalation; no machine execution-policy change was made.

### Tests

- Backend: **14 passed**. Health contract/cache behavior, factory isolation,
  environment and file overrides, invalid config, CORS origin handling, absent
  future action endpoints, and refusal of POST to `/health`.
- Frontend unit: **10 passed**. Live response consumption, HTTP/network failures,
  malformed/HTML response rejection, cache bypass and cancellation propagation.
- Browser: **4 passed**, headless installed Microsoft Edge, production build on
  port 4173 with real backend on 8000. Confirmed scenario selection, custom prompt,
  disabled Run/no mutations, live health, offline/retry recovery, malformed health,
  and 390px viewport without horizontal overflow.
- Typecheck and production build: **PASS**. Browser test source was included in a
  final typecheck after it was added.
- Visual inspection: 1440px desktop and 390px mobile screenshots render correctly.
- These are scaffold checks, not business-invariant or authorization tests.

### Failures Encountered

1. Sandbox network/cache restrictions blocked initial npm metadata and uv Python
   discovery/download. With normal access uv found existing Python 3.12.10, created
   only the project venv and installed dependencies. The normal sandbox could not
   launch that user-installed interpreter, so backend tests/server used escalation.
2. In-app browser bootstrap failed before navigation (`sandboxPolicy` metadata
   missing). Read its troubleshooting instructions, then used the separate installed
   Edge browser for local Playwright checks.
3. Backend tests report two upstream deprecation warnings: Starlette's httpx
   TestClient path and an AnyIO portal alias. Tests pass; warnings remain visible.
4. Existing root Git inspection failed and no local `.git` was present. No commit
   was created and no clean Git diff claim is made.
5. Shared files received research additions during this build. Their 18-task IDs,
   research notes, future contracts and deferred OpenSearch status were preserved;
   updated only the Phase 1 status/evidence and current runtime facts.

### Fixes and runtime decisions

Use `npm.cmd` in Windows instructions. Keep Python >=3.12 as the project baseline;
the library compatibility floor of 3.10 from the research notes does not change
the project's tested runtime. Resolve original document paths at the root. The
README now clearly distinguishes current scaffold behavior from target features.

Verified versions: Python 3.12.10, uv 0.12.5, Node 24.18.0, npm 11.16.0,
FastAPI 0.141.1, Pydantic 2.13.5, pydantic-settings 2.15.0, Uvicorn 0.53.0,
pytest 9.1.1, React 19.3.0, Vite 8.3.0, TypeScript 7.0.2, Vitest 5.0.1,
Playwright 1.63.0. Resolved dependencies are captured by `uv.lock` and
`package-lock.json`.

### Phase 1 sources and implementation contract

Checked [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/),
[FastAPI settings](https://fastapi.tiangolo.com/advanced/settings/),
[Vite setup](https://vite.dev/guide/) and
[React app setup](https://react.dev/learn/build-a-react-app-from-scratch).
Use `TestClient`/pytest for the app factory, `BaseSettings` for config, and Vite
for the React client. `GET /health` returns `status`, `service`, `version`,
`environment`, `phase`; only a validated actual response can display connected.

### Reviewer Feedback

No independent reviewer gate has run. Phase 1 is marked **REVIEW**, with builder
acceptance evidence ready. Gate 1 belongs after the domain and Cedar phases.

### Final State

Phase 1 implementation and builder verification complete. All remaining phases
retain their existing statuses. Next: `V1-P2` domain data and business tools.
The application is not release-ready and cannot execute the three demo scenarios.

### Lessons

Verify interpreters with normal user access before assuming a missing runtime.
Test connection failure as well as success. Keep phase previews visibly distinct
from actual policy outcomes. Preserve concurrent research entries when reconciling
shared tracking files.

---

<a id="phase-2-build-evidence"></a>

## Volume I — Phase 2 build evidence (2026-09-19)

### Goal

Implement `V1-P2`: a storage abstraction, in-memory adapter, deterministic demo
fixtures, exactly five business tools and the refund invariants. The user approved
Phase 2 after the Phase 1 handoff. Cedar and Strands integration remain later phases.

### Design

`BusinessStore` is a typed protocol; `BusinessTools` depends on that protocol rather
than a concrete adapter. The adapter stores one immutable `StoreSnapshot` of frozen
records. All reads, refunds, email recording and reset acquire the same per-store
lock. A refund validates the existing order and constructs both its updated record
and receipt before swapping the whole snapshot in one assignment.

Money is an exact positive integer in whole INR; booleans, floats, strings, zero and
negative refunds are invalid. An order must be paid and the amount must not exceed
its total. This narrow demo allows one refund per order, including a partial refund;
later top-ups are rejected. These are business rules, not policy thresholds. Internal
tests deliberately demonstrate that a valid 8499/25000 refund is possible at the
domain layer, which the later authority layer must mediate.

`send_email` records a message locally and returns `status=recorded`,
`delivered=false`. Customer export is exercised directly in domain tests, returns
detached dictionaries and is not an HTTP route. No raw business method is registered
with Strands. OpenAPI still has only `/health` as an application path.

### Implementation

- Frozen customer/order/refund/email records; stable `DomainError.code` values.
- Validated `SeedData`; duplicate identifiers, orphan orders and existing unrecorded
  refunds are rejected. Fresh fixtures use fictional `agentgate.example` addresses.
- Seed orders `ORD-1001=799`, `ORD-1002=8499`, `ORD-1003=25000`, each paid/lost.
- `BusinessStore` and thread-safe `InMemoryStore` with atomic refund/record/reset.
- Exactly five internal methods: `lookup_order`, `lookup_customer`, `refund_order`,
  `send_email`, `export_customers`. Reset and inspection belong to storage.
- Error paths return no fabricated success; unexpected storage exceptions propagate.
- Reset restores the exact configured seed (including custom test fixtures), clears
  email/refund records and restarts local receipt counters.

### Files Changed

- `backend/app/domain/{__init__,errors,models,seed,storage,memory}.py`.
- `backend/app/tools/{__init__,business}.py`.
- `backend/tests/test_business_tools.py`, `backend/tests/test_domain_storage.py`.
- `backend/tests/test_health.py` adds exposure regression checks.
- `README.md`, `TODO.md`, `STATUS.md` and this appended entry.
- No dependency, frontend or API implementation changes.

### Commands Run

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_business_tools.py
.\backend\.venv\Scripts\python.exe -m pytest backend/tests
```

Also read current architecture/build constraints, task/status history and existing
source; inspected internal imports/call sites and checked tracking-file structure.
Existing Python sandbox limitations required the already-used escalation path for
pytest; no runtime or package installation was required.

### Tests

- Before implementation: focused test collection failed with `ModuleNotFoundError:
  app.domain`, establishing the missing domain layer.
- After implementation: **45/45 business-tool tests pass**.
- Full regression: **86/86 backend tests pass**: 45 business, 23 storage/model,
  13 health/API and 5 configuration checks.
- The eight-contender refund test uses independent tool instances over one store:
  exactly one success, seven `ALREADY_REFUNDED` results, one receipt and one change.
- Concurrent refunds on separate orders preserve all three receipts with unique IDs.
  Concurrent recorded messages preserve all bodies and unique IDs. Concurrent
  reset/refund ends with a consistent order/receipt snapshot.
- Invalid, over-limit, unpaid, duplicate and missing-record operations leave complete
  snapshots unchanged. Injected receipt-construction failure also changes nothing.
- Frozen snapshots survive later writes; modified lookup/export dictionaries cannot
  alter storage. Separate store instances do not share mutable state.
- Email test blocks socket connection attempts and confirms only local recording.
- API checks verify unimplemented refund/export/reset routes remain inaccessible and
  the OpenAPI application surface remains health-only.
- Frontend checks were not rerun: no frontend or API implementation changed. Phase 1
  build, typecheck, unit and browser results remain historical evidence above.

### Failures Encountered

The expected initial missing-module collection failure was resolved by implementing
the domain package. No failing product assertion remained. The two existing upstream
Starlette/httpx/AnyIO deprecation warnings remain visible and unchanged.

### Fixes

Implemented the absent business layer behind the storage protocol. Put invariant
checks and mutation in the same storage critical section, so separate tool wrappers
cannot introduce a check/use race. Commit immutable state only after all validation
and receipt construction succeeds.

### Reviewer Feedback

No independent review has run. Marked `V1-P2` REVIEW with acceptance evidence.
Review Gate 1 remains scheduled after the Phase 3 Cedar policy matrix is complete.

### Final State

Phase 2 builder implementation and verification complete. Foundation domain tests
are green. Next: Phase 3 deterministic authority using the existing research notes.
The UI still previews scenarios; agent execution and approvals are not implemented.

### Lessons and limits

Keep whole-rupee business validation distinct from Cedar permissions: a policy's
numeric range does not make zero a valid refund or authorize a raw domain call.
Immutable state plus one lock makes atomicity easy to inspect for a small in-memory
demo. This is neither multi-process coordination nor durable storage. Reset reuses
local receipt numbers; future approval/session identity must invalidate old pending
actions across reset instead of treating these receipt IDs as capabilities.

<a id="phase-3-build-evidence"></a>

## Volume II — Phase 3 build evidence (2026-09-20)

### Goal

Make Cedar the thing that decides. Three states — ALLOW, REQUIRE_APPROVAL,
DENY — produced deterministically, with no model involved and no threshold
living in Python.

### Design

The Researcher's contract was followed without modification, because a spike
against the real engine confirmed every part of it. The one structural choice
worth stating: `PolicyEngine` is the *three-way* boundary the application
consumes, and the two Cedar requests live inside `CedarPolicyEngine`. Callers
never see the composition, so no caller can perform half of it.

Layers, in the order a request passes through them:

1. `app/policy/arguments.py` — per-tool argument specs. Validation happens
   here so that bad input is `INVALID_ARGUMENTS`, not an engine error. Unknown
   keys are rejected rather than dropped: a caller passing an unexpected field
   is a caller whose intent we cannot authorize.
2. `app/policy/engine.py` — parses and validates at startup, then answers one
   proposed call at a time. Execute check first; only a `refund_order` that
   was refused without an explicit forbid gets the second, approval check.
3. `policies/` — the schema, the two policy sets and the entity graph, outside
   the backend package so they read as the product's authority document rather
   than as code that happens to be data.

### Implementation

- `policies/agentgate.cedarschema` — five real actions plus the synthetic
  `request_refund_approval`. Money is a Cedar `Long`.
- `policies/execute.cedar` — narrow permits for reads, recorded email and
  refunds in 0..2000; an explicit `forbid` for `export_customers`.
- `policies/request_approval.cedar` — one permit, for refunds in 2001..10000.
- `policies/entities.json` — the one agent and the one store.
- `backend/app/policy/{contract,arguments,engine}.py`.
- `backend/app/config.py` — `policy_dir`, defaulting to the repository-root
  `policies/`.

Policies carry `@id("...")` annotations. cedarpy surfaces these through
`diagnostics.id_annotations_by_reason`, so the audit trail names
`allow_refund_within_agent_limit` rather than `policy1`.

### Commands

```text
uv add "cedarpy==4.12.0"
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/policy
.\backend\.venv\Scripts\python.exe -m pytest backend/tests
```

### Tests

54 policy checks, all passing.

- The full boundary matrix: lookups, recorded email, 799, 1999, 2000, 2001,
  8499, 9999, 10000, 10001, 25000, export. Both rupees either side of both
  limits are covered, and the expected values are written out one by one
  rather than derived from the same arithmetic the policies use.
- Malformed input: `True`, `False`, `799.0`, `"799"`, `-799`, `None`, missing
  fields, an extra `approved` field, a numeric `order_id`. All
  `INVALID_ARGUMENTS`, all before Cedar sees anything.
- Unknown tools, including `request_refund_approval` itself: the synthetic
  action exists to be asked about, never to be proposed as something to run.
- Startup failure on an unparsable policy, an undeclared action name, a policy
  type error, a malformed schema and a missing file.
- Fail-closed: a crashing evaluator, and an `Allow` returned alongside
  non-empty Cedar diagnostics errors, both become DENY.
- Amounts that overflow Cedar's `Long` become DENY rather than an exception.
- Authority is scoped: a different principal or a different store gets DENY
  for a refund the real agent could have made.

### Verification that the tests are real

Two checks, because a matrix that passes for the wrong reason is worse than no
matrix:

1. Emptying both policy files turns every previously allowed action into DENY.
   If any ALLOW had survived, a threshold would be hiding in Python.
2. Changing the agent limit from 2000 to 3000 in `execute.cedar` fails the
   matrix at the 2001 case. The file was restored and the suite re-run.

An autouse fixture asserts `strands` is never in `sys.modules` after a policy
test, so the "no LLM participates" claim is enforced rather than stated.

### Failures encountered

None in the policy layer. The Researcher's proposed schema and policy shapes
validated against cedarpy 4.12.0 on the first spike.

### Lessons

- `validate_policies` earns its place. A policy that names
  `AgentGate::Action::"refund_orders"` parses cleanly and would have become a
  permanent, silent DENY. Schema validation turns it into a startup crash.
- Cedar reports `Deny` with an empty `reasons` list for a missing permit and a
  populated one for a forbid. That difference is what separates
  `NO_MATCHING_PERMIT` from `EXPLICIT_FORBID` without inspecting policy text.
- An explicit forbid must not be escalated to a human. The gate checks for
  determining policies before it considers the approval path, so
  `export_customers` can never become a question someone might say yes to.

---

<a id="phase-3b-build-evidence"></a>

## Volume III/IV — Authority gateway build evidence (2026-09-20)

### Goal

Turn three decisions into three safe outcomes, and give them an HTTP surface.
Phases 4 and 5 need Strands and a model provider; the safety properties do
not, so they were built and attacked first.

### Design

`AuthorityGateway` is the single door between a proposed action and a business
mutation. It is the only holder of `BusinessTools`. The agent runtime, the API
and the test bench all call `propose`; none of them can reach a tool.

The reference is name-mangled (`self.__tools`) and dispatch is an explicit
dict rather than `getattr`, so a tool name can never select an arbitrary
attribute of the gateway. A test pins the gateway's entire public surface, so
adding a public method is a deliberate decision rather than an accident.

Approval is exactly-once by construction:

- `PendingAction` is frozen and recomputes its own digest on construction, so
  a record whose arguments were rewritten cannot be built at all.
- `claim` is a single locked `PENDING -> CLAIMED` transition guarded by
  version and digest. Everything downstream of it has already won.
- `reset` bumps an epoch that is inside the digest envelope, so an approval
  captured before a reset cannot authorize anything after one.
- `approve` re-evaluates the policy before claiming. A human may only confirm
  an escalation the policy still permits.

### Implementation

- `backend/app/events.py` — the timeline. `OPERATOR` was added alongside
  `AGENT` so a call typed by a person is never credited to a model that has
  not run.
- `backend/app/approvals/{models,store}.py`.
- `backend/app/services/gateway.py`.
- `backend/app/api.py` — `/api/actions`, `/api/pending`,
  `/api/pending/{id}`, `/api/timeline`, `/api/state`, `/api/reset`,
  `/api/policy-test`, `/api/tools`.
- `backend/app/main.py` — composition; a malformed policy set now stops
  startup.

### Tests

47 gateway and API checks, all passing.

- The three scenarios, asserted against the store rather than against what the
  gateway says about itself. A decision is only trustworthy if the order's
  `refunded_amount` agrees with it.
- Eight concurrent approvals produce exactly one refund and one receipt.
- Double approval, approve-after-deny, stale version, invented ID, and
  post-reset replay all execute nothing.
- Two pending actions cannot be confused: approving one leaves the other
  PENDING and its order untouched.
- The approval endpoint ignores `tool` and `arguments` fields in the body.
- A prompt-injection payload in an email body changes no later decision.
- A tool that fails is reported as a failure even when Cedar allowed it.
- The Policy Test Bench changes no business state and creates no pending
  actions.

### Live verification

A real uvicorn process on 127.0.0.1:8000, driven over HTTP, not TestClient:

```text
refund ORD-1001 799    -> ALLOW, executed, RFD-0001
refund ORD-1002 8499   -> REQUIRE_APPROVAL, ORD-1002 still at 0
approve pend-...       -> executed, RFD-0002
approve pend-... again -> DENY / ALREADY_DECIDED
refund ORD-1003 25000  -> DENY / NO_MATCHING_PERMIT
export_customers       -> DENY / EXPLICIT_FORBID
policy-test            -> 5 / 5
```

Frontend: 11 unit checks, TypeScript and production build, and 4 browser
checks against the live API all pass.

### Failures encountered

`approve` raised `ApprovalError` for an unknown pending ID instead of
returning a verdict. A test written for the post-reset replay case caught it.
The gateway's public methods now answer caller input with a decision and never
raise, so the API cannot turn a refused approval into a 500.

Three Phase 1 tests failed once the gate existed, all correctly: the health
contract's `phase`, an assertion that no gate routes existed, and the pinned
public surface of the gateway. Each was updated to describe the new system
rather than relaxed. The route test was replaced with one that lists the
entire expected API surface, so a new route is a decision rather than
something the suite quietly tolerates.

The frontend rejected the new health payload, because `fetchHealth` validated
`phase === 'foundation'` exactly. That strictness is the right behaviour; the
contract was updated on both sides, and the UI copy claiming Cedar was still
unimplemented was corrected.

### Deviations from the research contract

The digest envelope binds a gateway-issued `proposal_id` and a reset `epoch`
instead of a Strands tool-use ID and interrupt ID, because no agent runtime
exists yet. When Strands lands, both must be added and `DIGEST_VERSION`
incremented. This is the documented application-level path, not native Strands
resume, and it is not described as such anywhere.

The approval store is in-process. The restart and session-restoration
acceptance criterion in V4-P6B is therefore not met, and is not claimed.

### Lessons

- Writing the adversarial test first found the design flaw. The post-reset
  replay test failed on an exception rather than a verdict, which is exactly
  the shape of bug that becomes a 500 in front of a judge.
- Attributing a proposal to `AGENT` when a person typed it would have been a
  small lie that the whole demo rests on. The actor is now a parameter.
- The gate's public surface is a security boundary, so it is asserted in a
  test. Every method added to it since has had to justify itself.

<a id="phase-7-build-evidence"></a>

## Volume V — Control room build evidence (2026-09-20)

### Goal

Make the three scenarios runnable by a person in a browser, truthfully. The demo is the
product, and until now the gate was only reachable with curl.

### Design

Each scenario is a fixed sequence of proposed tool calls declared in `App.tsx`. No model
picks them, so the UI says so on screen and the timeline labels them `OPERATOR`. The
calls are shown before you run them, so the audience sees exactly what Cedar will be
asked.

The scenario loop is sequential and breaks on `REQUIRE_APPROVAL`. A call that pauses for
a human must not be overtaken by the next one in the list.

Every rendered outcome is read back from `/api/state` and `/api/timeline` after each
action. Nothing is inferred from the response the UI just received, so the screen cannot
claim a refund the store did not commit. The state strip under the timeline exists
purely so that any claim above it can be checked against the store.

### Implementation

- `frontend/src/api.ts` — typed client for the whole gate surface.
- `frontend/src/App.tsx` — scenario runner, live timeline with actor chips, approval
  card, reset, and the Policy Test Bench panel.
- `frontend/src/styles.css` — timeline, approval card, state strip, bench.
- `backend/app/api.py` — `/api/health` added; see failures below.

### Tests

11 browser checks against the real API, all passing. They are the exact clicks the demo
makes, so a green run means the demo works:

- Scenario A executes and ORD-1001 reads refunded ₹799.
- Scenario B shows the approval card, ORD-1002 still reads untouched, then Approve
  executes it once and the card disappears.
- Scenario B denied leaves ORD-1002 untouched.
- Scenario C shows both blocks with their reason codes and all orders untouched.
- Proposals render as OPERATOR; a test asserts no AGENT chip exists anywhere.
- The bench reports 5/5 and refunds nothing.
- Reset clears the timeline and the refunds.
- Offline disables Run and the bench; refresh restores them; an invalid health payload
  cannot turn the indicator green.
- The approval card is usable at 390px.

### Failures encountered

**Every gate call 404'd from the browser while `/health` worked.** The Vite proxy
rewrote `/api/*` to `/*`, which suited a backend whose only route was `/health` and
silently broke everything under `/api`. Fixed by dropping the rewrite and adding
`/api/health` to the router, so the browser path and the API path are the same string.
The root `/health` stays for process checks.

**Scenario B's approval passed alone and failed in the full suite.** Playwright's
`fullyParallel: false` only serialises tests within a file; two spec files still ran on
two workers, and one file's `reset` wiped the other's run mid-test. `workers: 1` is now
pinned in the config with the reason written next to it. This is the same single-writer
constraint the backend already has, showing up in the test layer.

Two failures were ambiguous selectors rather than product bugs: `getByText('EXPLICIT_FORBID')`
matched both the policy-checked row and the blocked row, and `getByRole('button', {name: 'Deny'})`
matched Scenario C's card as well as the approval button.

### Lessons

- A proxy rewrite is invisible until a second route exists. The health endpoint kept
  working, which made it look like a backend routing problem rather than a proxy one.
- Reading state back after every action costs one request and removes a whole class of
  lie from the UI.
- Showing the proposed calls before running them turned out to be the clearest part of
  the screen: the audience sees the arguments Cedar is about to judge.

---

<a id="site-build-evidence"></a>

## Volume V — Product site build evidence (2026-09-20)

### Goal

Replace the Framer-hosted landing page with real code in this repository, and bring the
control room onto the same design language, so the site and the demo look like one
product rather than a marketing page next to a prototype.

### Design

The Framer project's Control Room panel was the reference. Its language: a black console
bar, three columns, square corners, uppercase micro-labels with wide tracking, numbered
navigation, monospace for tool names and codes, and three state colours carried
everywhere — green allow, amber approval, red deny.

The control room was rebuilt to that spec: black bar, 216px rail with numbered sections
and the scenario picker, a centre column with a tally row and a tool-call table, a black
policy-evaluation block, and a right-hand decision column that holds either the pending
approval or the authority path.

The landing page is a React component in this repo, not an export. The sky, clouds and
grid are CSS, so the page carries no image assets and renders offline — worth doing for a
demo machine whose network cannot be relied on.

Routing is hash-based (`/` site, `#/control` demo) because the frontend is a static
bundle; a path router would need server rewrites that the preview server and most static
hosts do not give for free.

### Implementation

- `frontend/src/Landing.tsx` — nav, hero, problem, scenarios, how-it-works, policy
  limits, closing, footer, and a `ConsolePanel` mockup reused in two sections.
- `frontend/src/landing.css`.
- `frontend/src/ControlRoom.tsx` — the former `App.tsx`, rebuilt to the console design.
- `frontend/src/styles.css` — rewritten for the new layout.
- `frontend/src/main.tsx` — hash router.

### Failures encountered

**Every dark button rendered black-on-black.** `.site a { color: inherit }` is one class
plus one element, which outranks `.cta-dark`, so the white text lost. Fixed by scoping
the button rules to `.site .cta-dark`. Worth remembering: a base `a { color: inherit }`
rule quietly outranks every single-class button style under it.

**The actor labels nearly disappeared in the redesign.** The reference panel has no
timeline, and the first rebuild dropped the AGENT/CEDAR/HUMAN/TOOL chips with it — which
the Definition of Done requires and which is the clearest evidence that a human sat
between Cedar and the tool. They came back as a compact trail under each table row, which
suits the design better than the old timeline did.

Two test failures were strict-mode violations rather than product bugs: `.actor-tool`
matches every executed row, and `:has(code:text-is(...))` did not resolve inside a plain
selector string, so the ledger helper moved to Playwright's `filter({ hasText })`.

### Tests

13 browser checks, all passing against the live API: the landing page and its route into
the demo, all three scenarios, approve and deny, the actor trail reaching HUMAN and TOOL,
OPERATOR-not-AGENT attribution, the 5/5 bench with zero mutation, reset, offline
handling, and both routes at 390px with no horizontal scroll.

### Lessons

- Rebuilding the dashboard against the marketing mockup improved the dashboard. The
  tally row and the decision column say more, in less space, than the panel grid did.
- Drawing the sky in CSS took about as long as wiring an image pipeline would have, and
  removed a whole class of demo-day failure.

---
