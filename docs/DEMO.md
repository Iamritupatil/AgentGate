# AgentGate — 3-minute demo script

## Before you start

Two terminals, from the repository root.

```powershell
# Terminal 1 — backend (one worker; state is in-process)
uv run --project backend --locked uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

# Terminal 2 — frontend
cd frontend
npm.cmd run dev
```

Open <http://127.0.0.1:5173>. That is the product site.

Click **Explore the demo** (or go straight to <http://127.0.0.1:5173/#/control>) to reach
the control room. Confirm the black bar top right says **POLICY ENGINE CONNECTED**, then
click **Reset** once so the stream is empty and all three orders read *untouched*.

---

## Optional 20-second opener on the site

If you have the time, scroll the landing page first: the hero, then **Make authority
explicit** with the ₹2,000 and ₹10,000 cards. It sets the limits up before anyone sees
them enforced. Then click **Explore the demo**.

---

## The line to open with

> An AI agent decided to refund this order. AgentGate decided whether it was allowed to.
> The model reasons. Cedar holds authority.

---

## Scenario A — ALLOW (25 seconds)

1. Click **Scenario A** (₹799) in the left rail.
2. Click **Run scenario**.

**Say:** "₹799 is inside the agent's own limit, so Cedar allows it and it just happens."

**Point at:** the **ALLOWED 01** tally, the green `ALLOW` pill on the `refund_order` row,
and the actor trail under it: `OPERATOR → CEDAR → TOOL`. Then the black **POLICY
EVALUATION** block showing `can_execute true`, and **BUSINESS STATE** at the bottom:
**ORD-1001 refunded ₹799**.

> The green row is the only place a refund is ever claimed, and it is written after the
> store returns a receipt.

---

## Scenario B — REQUIRE_APPROVAL (70 seconds) — **the centrepiece**

1. Click **Scenario B** (₹8,499).
2. Click **Run scenario**.

**Say:** "Same tool, same agent, bigger number. Cedar does not deny this — it escalates."

**Point at, in this order:**

- The right column: **HUMAN DECISION REQUIRED**, ₹8,499, the exact call
  `refund_order / ORD-1002`, and **Execution status: PAUSED**.
- **BUSINESS STATE**: ORD-1002 is still **untouched**. Nothing has moved.
- The black block: `can_execute false`, `can_request_approval true`. That is the
  two-question composition, on screen.

> Cedar itself only answers allow or deny. The third state is two policy questions:
> may this execute, and failing that, may a human be asked? Both answers come from
> policy files, not from code.

3. Click **Approve**.

**Point at:** the actor trail on that row growing to `OPERATOR → CEDAR → HUMAN → TOOL`,
and ORD-1002 flipping to **refunded ₹8,499**.

> The approval sends an id and a version. It never sends the arguments — otherwise the
> person approving wouldn't be approving anything in particular.

**If you have a spare 10 seconds, this is the best moment in the demo:** click Reset,
run Scenario B again, and hit **Approve twice quickly**. The second one refuses. One
refund, one receipt.

---

## Scenario C — DENY (35 seconds)

1. Click **Reset**, then **Scenario C** (₹25,000 + export).
2. Click **Run scenario**.

**Say:** "Two dangerous actions. Neither reaches a tool."

**Point at:**

- Two red `DENY` pills and **DENIED 02**.
- The black block: `EXPLICIT_FORBID · forbid_customer_export`. A deliberate forbid, so
  the audit trail names the security intent rather than reporting a gap. The refund's
  own reason is `NO_MATCHING_PERMIT` — no permit, and no approval path either, because
  ₹25,000 is above the ceiling a human may authorize.
- Every actor trail stops at `CEDAR`. Nothing reached a tool.
- All three orders: **untouched**.

> A forbidden action never becomes a question someone could say yes to by mistake.

---

## Policy Test Bench (20 seconds)

Click **04 Policy test bench** in the left rail, then **Run 5 policy checks**.

**Say:** "Five cases through the real engine. Nothing is refunded to prove a refund is
allowed — this evaluates policy and touches no business state."

**Point at:** **5 / 5 passed**.

---

## Closing line

> Cedar decided every one of those. Empty the policy files and every allow in this demo
> becomes a deny — which is how we know the limits are not hiding in the code.

---

## Questions you will probably get

**"Where's the LLM?"**
Not wired up yet, and the UI says so. Each scenario proposes a fixed sequence of tool
calls, which is why the timeline labels them `OPERATOR` rather than `AGENT`. The gate is
the part that has to be right, and it is the part that is built and attacked. When
Strands lands, its intervention calls this same gateway — there is no second path to a
tool.

**"How do you know the tests are real?"**
Two checks. Emptying both policy files turns every allow into a deny. Changing the
₹2,000 limit to ₹3,000 fails the boundary matrix. Both are recorded in
[AGENTGATE_BOOK.md](development/AGENTGATE_BOOK.md).

**"What would break this?"**
Restart the backend. Approvals are in-process, so pending actions are lost — that is
written down in [STATUS.md](development/STATUS.md) as unmet, not glossed over. Durable storage and native
Strands resume are the next two pieces.

---

## Numbers worth having in your head

| | |
| --- | --- |
| Backend tests | 178 |
| Policy checks | 54 |
| Browser tests against the live API | 13 |
| Agent limit / human ceiling | ₹2,000 / ₹10,000 |
| Concurrent approvals that produced one refund | 8 |
