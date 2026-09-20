# AgentGate — Independent Final Release Audit

Auditor: independent release audit pass
Date: 2026-09-20
Commit audited: working tree at `2a7aee5` plus uncommitted feature work (28 modified/new files)

## 0. Auditor independence disclosure

Read this first, because it limits how much weight this report deserves.

- This audit ran in a session that had **earlier authored the three Cedar policy files**
  (`policies/agentgate.cedarschema`, `policies/execute.cedar`,
  `policies/request_approval.cedar`, written 19:01–19:02). A separate builder process
  then wrote the remaining ~28 files between 20:53 and 21:33 on top of them.
  I am therefore **not independent of the Cedar policy content**. I am independent of the
  Python/TypeScript implementation, the Policy Studio, the AI drafter, the MCP adapter
  and the deployment artifacts, all of which I read for the first time during this audit.
- All feature work is **uncommitted**. A full snapshot was taken before auditing.
- No P0/P1 finding below depends on the policy files I wrote. Every one is a defect in
  code written by the other process, demonstrated by black-box HTTP testing.

---

## 1. Verdict

**RELEASE_BLOCKED**

Three P0 authorization defects are reachable through the public, unauthenticated API.
One was demonstrated to execute a real ₹25,000 refund — the exact action the product's
own Scenario C promises is denied.

Public deployment is separately unverified: no EC2 instance, no public URL and no AWS
CLI exist in this workspace, so `PUBLIC_RELEASE_READY` was unreachable regardless.

---

## 2. Genuine evidence

### Architecture map (read from source, then confirmed by black-box testing)

```text
external caller
    |
    +-- POST /api/gate/evaluate ......... app/api.py::evaluate        (evaluate only, no execution)
    +-- POST /api/actions ............... app/api.py::propose
    +-- MCP stdio evaluate_action ....... app/mcp_server.py::evaluate (separate process)
                |
                v
        AuthorityGateway (app/services/gateway.py)     <-- sole holder of BusinessTools
                |
                v
        CedarPolicyEngine.evaluate (app/policy/engine.py)
                |
        arguments.normalize -> cedarpy.is_authorized(schema, execute set)
                |                          (+ second request against the approval set)
                v
        ALLOW / REQUIRE_APPROVAL / DENY
                |
        ALLOW ------------> BusinessTools (single mutation, receipt required)
        REQUIRE_APPROVAL -> InMemoryApprovalStore -> human -> claim() -> BusinessTools
        DENY -------------> event only, zero mutation
```

This map is **true** for the execution path. Two deviations were found, and both are
defects rather than design: the MCP adapter does not share the HTTP route's request
shaping (P1-1), and `engine.py` contains a Python-side override of a Cedar `forbid`
(P0-3).

### Source paths inspected

`backend/app/policy/{engine,contract,arguments,studio,ai}.py`,
`backend/app/{api,main,config,events,mcp_server}.py`,
`backend/app/services/gateway.py`, `backend/app/approvals/{models,store}.py`,
`backend/app/domain/{seed,memory}.py`, `backend/app/tools/business.py`,
`policies/*`, `frontend/src/{api.ts,ControlRoom.tsx,Workbench.tsx}`,
`frontend/tests/*`, `backend/tests/*`,
`deployment/{nginx-agentgate.conf,agentgate.service}`, `DEPLOY_EC2.md`, `MCP.md`,
`STATUS.md`, `TODO.md`, `AGENTGATE_BOOK.md`, `README.md`.

### Existing suites (run by me, from a clean state)

| Suite | Command | Result |
| --- | --- | --- |
| Backend | `backend/.venv/Scripts/python.exe -m pytest backend/tests` | **196 passed** |
| Frontend unit | `npm.cmd test` | **11 passed** |
| Typecheck + production build | `npm.cmd run build` | **pass** (263.51 kB js, 34.37 kB css) |
| Browser | `E2E_BASE_URL=http://127.0.0.1:4173 npm.cmd run test:e2e` | **14 passed** |

### Independent audit suite (new; values chosen to miss every fixture)

Run against an isolated backend on `127.0.0.1:8010` with an empty policy store.

| Audit phase | Cases | Result |
| --- | --- | --- |
| Generic authorization matrix (randomized resource IDs) | 28 | **27 pass, 1 FAIL** (P1-2) |
| Dynamic policy genuinely controls Cedar | 8 | pass |
| Studio threshold semantics vs. stated intent | 11 | **4 FAIL** (P0-3) |
| Cedar injection via `principal_id` | 4 | **FAIL — full bypass** (P0-1) |
| Rejected-policy atomicity | 6 | **FAIL — rejected policy active** (P0-2) |
| Approval security | 9 | **9 pass** |
| Business state / domain invariants | 11 | pass |
| Policy Test Bench perturbation | 3 | pass (5/5 → 3/5 → 5/5) |
| MCP vs HTTP parity (randomized) | 8 | **3 pass, 5 FAIL** (P1-1) |
| Malformed / hostile input | 14 | **14 pass** |
| External client (curl + PowerShell) | 4 | pass |
| Fresh process restart | 6 | pass |

### Headline HTTP evidence

```text
POST /api/gate/evaluate {"principal":{"type":"Agent","id":"support-agent"},"action":"refund_order",
                         "resource":{"type":"Order","id":"ORD-AUDIT-9"},"context":{"amount":7341}}
-> REQUIRE_APPROVAL / APPROVAL_PERMITTED / allow_refund_approval_request

POST /api/gate/evaluate {... "id":"finance-agent" ... "amount":7341}
-> ALLOW / EXECUTE_PERMITTED / allow_finance_refund_within_limit

POST /api/gate/evaluate {... "id":"unknown-agent" ... "amount":100}
-> DENY / NO_MATCHING_PERMIT / null
```

The support, finance, intern, deployment and unknown ladders were all correct at every
boundary (1, 1999, 2000, 2001, 9371, 10000, 10001, 999999 / 1, 9999, 10000, 10001,
41729, 50000, 50001), on randomly generated order IDs.

### Public EC2 result

**Not performed.** No public URL exists in the repository, no EC2 instance is referenced
anywhere, and the AWS CLI is not installed. Per audit rule 10, no deployment claim is
made.

---

## 3. Defects

| ID | Severity | Problem | Reproduction | Impact | Required Fix |
| -- | -------- | ------- | ------------ | ------ | ------------ |
| P0-1 | P0 | `studio.generate_cedar()` interpolates `principal_id` into Cedar source with no escaping or charset validation. A crafted id closes the policy and appends an unconstrained `permit`. | `POST /api/policies` with `principal_id` = `a",action,resource);permit(principal,action,resource);permit(principal,action==AgentGate::Action::"nope",resource);//` then `POST /api/policies/{id}/activate` | **Total authorization bypass.** Observed: `unknown-agent` refund ₹99,999 → ALLOW (`policy9`); `POST /api/actions` refund ₹25,000 on ORD-1003 → `executed: true`, business state mutated. Unauthenticated, and port 80 is public in the documented deployment. | Reject `principal_id` not matching a strict identifier charset (e.g. `^[A-Za-z0-9][A-Za-z0-9._@-]{0,63}$`) in `validate_definition`, and escape on render. Regression test: a quote/semicolon id is refused. |
| P0-2 | P0 | `CedarPolicyEngine._set_dynamic_policies()` assigns `self._execute` / `self._approval` **before** calling `_validate()`, and never rolls back on failure. | Activate a policy whose generated Cedar parses but fails schema validation. Server returns **HTTP 500**, store records `active: false` — yet the new policies are live. | A policy the server **explicitly rejected** governs authorization. Combined with P0-1, this is how the universal permit survived a "failed" activation. Directly violates the stated requirement that an invalid policy must never replace the last-known-good set. UI and API both report the wrong active policy set. | Build and validate a candidate `PolicySet` into locals; assign only after both parse and validate succeed. Return 422, not 500. Regression test: a rejected activation leaves every prior decision identical. |
| P0-3 | P0 | `engine.py` contains `studio_threshold_override`, which discards an explicit Cedar `forbid` when the determining policy id starts `studio_` and ends `_threshold_deny`. Authorization decided by a **string suffix in Python**, outside Cedar. | Activate Studio policy support-agent / refund_order / Order, allow=100, approval=500. Evaluate ₹2,500. | Policy says DENY; system returns **REQUIRE_APPROVAL** and offers a human an Approve button that executes. Breaks the documented invariant that an explicit forbid is never escalated to a human. Measured mismatches at ₹2,500 / ₹3,000 / ₹9,000 / ₹10,000. | Remove the override. Express the Studio band in Cedar without an unbounded `forbid` (emit no forbid and let default-deny apply, scoping the studio permits instead), so a `forbid` always means DENY. Regression test over the full band. |
| P1-1 | P1 | MCP adapter is not at parity with HTTP. `api.py::evaluate` injects `order_id` from the resource id for `refund_order`; `mcp_server.evaluate` does not. | 8 randomized requests through both paths. | **5/8 mismatches, 2 at decision level**: HTTP ALLOW vs MCP DENY; HTTP REQUIRE_APPROVAL vs MCP DENY. Three further cases agree on DENY for the *wrong reason* (`INVALID_ARGUMENTS` rather than a real policy). `test_mcp.py` covers only `deploy_production`, the one family the shim never touches, so it passes while the adapter is broken. | Move request construction into one shared function used by both the HTTP route and the MCP adapter. Extend the parity test to refund cases and unknown principal/action. |
| P1-2 | P1 | `principal.type` is accepted by the API, echoed in the response, and **never used**; the engine hardcodes `AgentGate::Agent`. | `POST /api/gate/evaluate` with `{"type":"Wizard","id":"support-agent"}`, amount 1500. | Returns `ALLOW` with `"principal":"Wizard:support-agent"`. The response asserts a decision about a principal type that was never evaluated. Any caller distinguishing Agent from Human/Service gets a silently wrong answer. | Validate `principal.type` against the schema's declared entity types and DENY otherwise, or pass it through to the Cedar request. |
| P1-3 | P1 | "AI policy drafting" performs no AI as shipped. `ai_api_key` is unset in `config.py`, `.env.example` and the environment, so `draft_policy` always uses `_local_draft`, a keyword/regex matcher. `_provider_draft` also swallows all provider errors via a bare `except Exception: pass`. | `POST /api/policies/draft` with the audit's sentence: "Infrastructure agents may restart staging automatically. Restarting production requires human approval. Destroying a production cluster must always be denied." | **HTTP 422** — "The description did not identify a supported AgentGate action." The drafter also emits at most one policy, so a three-clause sentence is inexpressible. STATUS.md lines 5 and 46 call AI drafts "implemented". | Describe it as deterministic structured parsing, not AI, everywhere it is claimed. The safety flow itself is correct and should be kept. |
| P1-4 | P1 | STATUS.md contains claims contradicted by testing. | Read STATUS.md against the results above. | Line 45, "activates only after Cedar validation" — **false** (P0-2). Reviewer block claims MCP parity passed — **false** (P1-1). Line 68 says 178 backend tests; lines 95 and 162 say 196. Line 40 says 13 browser tests; actual is 14. | Correct each claim. A release file that overstates is itself a release risk. |
| P2-1 | P2 | Policy Studio cannot author new actions or resource types; the vocabulary is fixed to 8 schema actions and 4 entity types. | `POST /api/policies` with `action=rotate_signing_keys`, `resource_type=SecurityInfrastructure` → **422**. | The audit's own genericness test is unsatisfiable. "Generic authorization service" is overstated: it is generic over principals and thresholds, not over the action/resource vocabulary. | State the limitation plainly, or generate the Cedar schema from the declared action set. |
| P2-2 | P2 | `POST /api/reset` does not clear Studio policies, and `complete-demo.spec.ts` activates one on every run. | Live instance held 5 active policies; one browser run took it to 6; `/api/reset` left it at 6; persisted to `backend/data/policies.json`. | Unbounded growth of **live authorization state** caused by running tests. Four of the five were identical duplicates. | Make reset restore the baseline policy set, or have the e2e test delete what it creates. |
| P2-3 | P2 | `ControlRoom.tsx` hardcodes `AUTONOMOUS_LIMIT = 2000` and `APPROVAL_LIMIT = 10000` for the approval sidebar. | Activate a Studio policy with different thresholds; the sidebar still shows ₹2,000 / ₹10,000. | The UI states limits the backend may no longer enforce — the exact "UI disagrees with backend" failure. Decisions themselves are backend-derived; only these two labels are local. | Derive the displayed limits from the API, or label them as the built-in baseline. |
| P2-4 | P2 | In `generate_cedar`, when `allow_threshold` is set the `decision` field is ignored — a policy authored `DENY` with a threshold emits a `permit`. | Create a policy with decision=DENY, allow_threshold=100. | The activated policy does the opposite of what the form says. | Reject the combination, or honour `decision`. |
| P2-5 | P2 | `POST /api/policies` performs only structural validation; Cedar validation happens at activate, where failure is a 500. | Create `action=read_logs, resource_type=Store` → 201. | "Validate a policy before activating it" is only half implemented; invalid policies are stored and fail later. | Generate and Cedar-validate at create time; return 422. |
| P2-6 | P2 | `DEPLOY_EC2.md` step 5 documents `http://PUBLIC_IP/docs`, and the Integrate tab links `/docs`, but the Nginx config proxies only `/api/`; `location /` falls through to `try_files ... /index.html`. | Read `deployment/nginx-agentgate.conf` against `DEPLOY_EC2.md`. | The documented verification step returns the SPA, not FastAPI docs. Broken link in the shipped UI. | Proxy `/docs` and `/openapi.json`, or remove both claims. |
| P2-7 | P2 | `DEPLOY_EC2.md` uses `pip install -e backend`, but `backend/pyproject.toml` declares `[tool.uv] package = false` and has no `[build-system]`. | Read both files. | The documented install path is untested and may fail on a clean instance. | Ship a `requirements.txt` and `pip install -r`, or test the editable install. |
| P3-1 | P3 | `deployment/agentgate.service` uses `Restart=on-failure`, which does not restart after a clean exit. | Read the unit file. | A backend that exits 0 stays down; this is the 502 condition. | Use `Restart=always`. |
| P3-2 | P3 | `test_health.py` lists `/api/policies/draft` twice in a set literal; `PolicyResponse.of` has a dead `__dict__` branch that can never run on a `slots=True` dataclass. | Read the files. | Cosmetic and misleading. | Tidy. |
| P3-3 | P3 | An unknown resource type returns `POLICY_ENGINE_ERROR`. | `resource.type = "Nonsense"`. | Fail-closed and correct, but the reason code misattributes a caller error to the engine. | Add `UNKNOWN_RESOURCE_TYPE`. |
| P3-4 | P3 | No API-level test exercises `UNPAID_ORDER`; all three seeded orders are `paid`. | Read `seed.py`. | The invariant is unit-tested but not reachable through the demo. | Seed one unpaid order, or note the gap. |

### Not defects (checked and cleared)

- Approval lifecycle: approve, deny, double-approve, replay, tampered body, cross-action,
  post-reset and 8-way concurrency — **9/9 correct**, exactly one refund under race.
- Denied actions mutate nothing; a denied export returns `result: null`.
- Malformed input: 14/14 either 422 at the schema boundary or DENY. Never permissive.
- Prompt-injection strings used as action names → `UNKNOWN_ACTION` / DENY.
- The production bundle contains **zero** `localhost` / `127.0.0.1` occurrences.
- No `.env` is present or committed; no secrets in tracked files.
- The backend binds `127.0.0.1:8000`; port 8000 is not publicly exposed by the documented
  security group.
- The Policy Test Bench is genuine (proven by perturbation, see §4).
- `AuthorityGateway` remains the only holder of `BusinessTools`.

---

## 4. Hardcoding assessment

**Are policy decisions hardcoded?**
No, with one serious exception. No `if amount <= 2000` exists in any production
authorization path; the thresholds live only in `policies/*.cedar`. Emptying the policy
files turns every ALLOW into DENY (existing test, re-verified). **The exception is
P0-3**: `engine.py` decides, in Python, to discard a Cedar `forbid` based on a policy-id
string suffix. That is authorization logic outside Cedar and it changes real outcomes.

**Does `/api/gate/evaluate` actually use Cedar?**
Yes. Every decision returned a real determining policy id from Cedar diagnostics
(`allow_refund_within_agent_limit`, `allow_finance_refund_approval_request`,
`forbid_intern_refunds`, and so on). Removing a policy changes the answer. It calls the
same `CedarPolicyEngine` instance as `/api/actions`.

**Does Policy Studio really change authorization?**
Yes — genuinely. A brand-new principal (`audit-agent-7391`, absent from every fixture)
went DENY → created (still DENY) → activated → REQUIRE_APPROVAL with matched policy
`studio_pol-7b9db6e2eebd_approval`, survived a process restart, and left neighbouring
actions and other principals untouched. **But** it cannot author new actions or resource
types (P2-1), its thresholds do not mean what the form says (P0-3, P2-4), and it is the
vector for P0-1 and P0-2.

**Does AI draft require activation?**
Yes, and this part is correct: drafting returns `active: false`, creates no stored
policy, and changes no decision until an explicit `POST /policies/{id}/activate`.
**But no AI is involved** (P1-3).

**Does MCP share the same evaluator?**
It shares the `CedarPolicyEngine`, but **not** the request construction, so decisions
diverge (P1-1). It also defaults to a different policy store file than the HTTP process
unless `AGENTGATE_POLICY_STORE_PATH` is aligned — a second divergence source.

**Is the Policy Test Bench genuine?**
Yes, proven by perturbation: baseline 5/5 → activated a real Cedar policy forbidding
support-agent refunds on `Store` → the bench reported **3/5, `all_passed: false`**, naming
the two flipped cases → deleted the policy → back to 5/5. The count is derived, and the
bench mutates no business state and creates no pending actions.

**Does the UI reflect real backend state?**
Yes for decisions, refunds, reason codes, policy names and the timeline — all rendered
from `/api/timeline`, `/api/state` and the evaluate response. An API failure shows an
error banner and disables Run; an invalid health payload cannot turn the status green.
The exception is the two approval-limit labels (P2-3).

---

## 5. Demo readiness

| Capability | Status | Note |
| --- | --- | --- |
| Generic external API | **PASS** | curl and PowerShell verified; full boundary ladder correct |
| Custom policy (Policy Studio) | **FAIL** | works, but P0-1, P0-2, P0-3 and P2-1 |
| AI policy draft | **FAIL** | no AI; the audit sentence is rejected (P1-3) |
| Policy Playground | **PASS** | renders the backend response verbatim |
| MCP | **FAIL** | decision-level divergence from HTTP (P1-1) |
| Human approval | **PASS** | 9/9 adversarial checks; exactly-once under 8-way race |
| Hard deny | **PASS** | baseline denies correct, **but** defeatable via P0-1 |
| Test Bench | **PASS** | genuine, proven by perturbation |
| EC2 / public deployment | **NOT VERIFIED** | no instance, no URL, no AWS CLI |
| 3-minute demo path (A / B / C / Bench) | **PASS** | 14/14 browser tests; verified after a cold restart |

**The scripted three-scenario demo is solid and would present well.** The release is
blocked by what an audience member with a laptop could do to the Policy Studio endpoint,
not by the demo path itself.

---

## 6. Recommended fix order

1. P0-1 — charset-validate and escape `principal_id` (smallest change, highest impact).
2. P0-2 — make policy activation atomic; 422 instead of 500.
3. P0-3 — delete `studio_threshold_override`; express the band in Cedar.
4. P1-1 — share one request builder between HTTP and MCP; widen the parity test.
5. P1-2 — validate or actually use `principal.type`.
6. P1-3 and P1-4 — correct STATUS.md and every "AI" claim.
7. P2s as time allows; P2-2 before any further e2e runs.

Re-run after each: `pytest backend/tests`, the independent audit scripts, `npm.cmd test`,
`npm.cmd run build`, `npm.cmd run test:e2e`.
