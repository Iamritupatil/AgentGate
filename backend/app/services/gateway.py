"""The single door between a proposed action and a business mutation.

Everything that can change state lives behind this class. The agent runtime,
the HTTP API and the test bench all call `propose`; none of them holds a
reference to the raw tools. That is what makes the policy non-bypassable:
there is no second path to `refund_order`, so no prompt, no malformed argument
and no direct call can reach one.

Three decisions, three outcomes, and only one of them touches the store:

    ALLOW             execute now, then report what the store actually returned
    REQUIRE_APPROVAL  persist the exact action and stop; no mutation
    DENY              record the block and stop; no mutation
"""

import uuid
from dataclasses import asdict, dataclass
from threading import Lock
from typing import Any, Callable, Mapping

from app.approvals.models import PendingAction, PendingStatus, digest_for
from app.approvals.store import ApprovalError, InMemoryApprovalStore
from app.domain.errors import DomainError
from app.events import Actor, EventLog, EventType
from app.policy.contract import (
    AuthorizationRequest,
    AuthorizationResult,
    GateDecision,
    PolicyEngine,
    ReasonCode,
)
from app.tools.business import BusinessTools

PRINCIPAL_ID = "support-agent"
RESOURCE_TYPE = "Store"
RESOURCE_ID = "demo"

# Refusals for an id we cannot resolve still belong on the timeline; they have
# no run to belong to.
UNATTRIBUTED_RUN = "unattributed"


@dataclass(frozen=True, slots=True)
class Outcome:
    """What actually happened. `executed` is true only when the store
    committed, so a caller can never report a refund that did not occur."""

    decision: GateDecision
    reason_code: str
    executed: bool = False
    result: dict[str, Any] | None = None
    pending_id: str | None = None
    determining_policies: tuple[str, ...] = ()
    error: dict[str, str] | None = None

    @property
    def requires_approval(self) -> bool:
        return self.decision is GateDecision.REQUIRE_APPROVAL


class AuthorityGateway:
    def __init__(
        self,
        engine: PolicyEngine,
        tools: BusinessTools,
        approvals: InMemoryApprovalStore,
        events: EventLog,
        reset_store: Callable[[], None],
        snapshot_store: Callable[[], Any] | None = None,
    ) -> None:
        self._engine = engine
        # Name-mangled on purpose. A caller reaching for `gateway._tools` to
        # "just run the refund" would reintroduce the bypass this class exists
        # to prevent.
        self.__tools = tools
        self._approvals = approvals
        self._events = events
        self._reset_store = reset_store
        self._snapshot_store = snapshot_store
        self._epoch = 0
        self._lock = Lock()

    # -- read side ----------------------------------------------------------

    def evaluate_only(self, tool_name: str, arguments: Mapping[str, object]) -> AuthorizationResult:
        """Ask what the policy would say, and change nothing at all.

        The Policy Test Bench runs on this: it must exercise the real engine
        without refunding anything to find out.
        """
        return self._engine.evaluate(
            AuthorizationRequest(PRINCIPAL_ID, tool_name, RESOURCE_TYPE, RESOURCE_ID, arguments)
        )

    def pending_actions(self) -> tuple[PendingAction, ...]:
        return self._approvals.pending()

    def timeline(self, run_id: str | None = None) -> tuple[Any, ...]:
        return self._events.events(run_id)

    def business_state(self) -> dict[str, Any]:
        """The store's own view, so a timeline claim can be checked against it."""
        if self._snapshot_store is None:
            return {}
        snapshot = self._snapshot_store()
        return {
            "orders": [asdict(order) for order in snapshot.orders],
            "refunds": [asdict(refund) for refund in snapshot.refunds],
            "emails": [asdict(email) for email in snapshot.emails],
        }

    # -- proposal -----------------------------------------------------------

    def propose(
        self,
        run_id: str,
        tool_name: str,
        arguments: Mapping[str, object],
        proposed_by: Actor = Actor.AGENT,
    ) -> Outcome:
        """Submit one proposed tool call for a decision.

        `proposed_by` is recorded as-is. A call typed by a person must not
        appear on the timeline as something the model decided to do.
        """
        proposal_id = f"prop-{uuid.uuid4().hex[:12]}"
        self._events.append(
            run_id,
            proposed_by,
            EventType.TOOL_PROPOSED,
            proposal_id=proposal_id,
            tool=tool_name,
            arguments=dict(arguments),
        )

        verdict = self._engine.evaluate(
            AuthorizationRequest(PRINCIPAL_ID, tool_name, RESOURCE_TYPE, RESOURCE_ID, arguments)
        )
        self._events.append(
            run_id,
            Actor.CEDAR,
            EventType.POLICY_CHECKED,
            proposal_id=proposal_id,
            tool=tool_name,
            decision=verdict.decision.value,
            reason_code=verdict.reason_code.value,
            determining_policies=list(verdict.determining_policies),
        )

        if verdict.decision is GateDecision.ALLOW:
            return self._execute(run_id, proposal_id, tool_name, arguments, verdict)
        if verdict.decision is GateDecision.REQUIRE_APPROVAL:
            return self._park(run_id, proposal_id, tool_name, arguments, verdict)
        return self._block(run_id, proposal_id, tool_name, verdict)

    def _block(
        self, run_id: str, proposal_id: str, tool_name: str, verdict: AuthorizationResult
    ) -> Outcome:
        self._events.append(
            run_id,
            Actor.CEDAR,
            EventType.TOOL_BLOCKED,
            proposal_id=proposal_id,
            tool=tool_name,
            reason_code=verdict.reason_code.value,
            feedback=verdict.as_denial_feedback(),
        )
        return Outcome(
            GateDecision.DENY,
            verdict.reason_code.value,
            determining_policies=verdict.determining_policies,
        )

    def _park(
        self,
        run_id: str,
        proposal_id: str,
        tool_name: str,
        arguments: Mapping[str, object],
        verdict: AuthorizationResult,
    ) -> Outcome:
        """Persist the exact action and stop. Nothing has changed yet."""
        with self._lock:
            epoch = self._epoch
        canonical = dict(arguments)
        pending = PendingAction(
            pending_id=f"pend-{uuid.uuid4().hex[:12]}",
            run_id=run_id,
            proposal_id=proposal_id,
            epoch=epoch,
            tool_name=tool_name,
            arguments=canonical,
            arguments_sha256=digest_for(
                epoch=epoch,
                run_id=run_id,
                proposal_id=proposal_id,
                tool_name=tool_name,
                arguments=canonical,
            ),
            policy_reason_code=verdict.reason_code.value,
        )
        self._approvals.create(pending)
        self._events.append(
            run_id,
            Actor.CEDAR,
            EventType.APPROVAL_REQUESTED,
            proposal_id=proposal_id,
            pending_id=pending.pending_id,
            tool=tool_name,
            arguments=canonical,
            reason_code=verdict.reason_code.value,
        )
        return Outcome(
            GateDecision.REQUIRE_APPROVAL,
            verdict.reason_code.value,
            pending_id=pending.pending_id,
            determining_policies=verdict.determining_policies,
        )

    # -- human decision -----------------------------------------------------

    def approve(self, pending_id: str, expected_version: int) -> Outcome:
        """Execute one exact pending action, at most once, ever."""
        try:
            action = self._approvals.get(pending_id)
        except ApprovalError as error:
            # An id the store does not recognise — invented, or left over from
            # before a reset — is a refusal, not an exception. Raising here
            # would hand the caller an error to interpret instead of a verdict.
            return self._refuse(UNATTRIBUTED_RUN, pending_id, error.code)

        # A human may only confirm an escalation the policy still permits. If
        # the rules changed under the pending action, this is now a refusal.
        recheck = self._engine.evaluate(
            AuthorizationRequest(
                PRINCIPAL_ID, action.tool_name, RESOURCE_TYPE, RESOURCE_ID, action.arguments
            )
        )
        if recheck.decision is not GateDecision.REQUIRE_APPROVAL:
            self._events.append(
                action.run_id,
                Actor.CEDAR,
                EventType.TOOL_BLOCKED,
                pending_id=pending_id,
                tool=action.tool_name,
                reason_code=ReasonCode.NO_MATCHING_PERMIT.value,
                note="Policy no longer permits this escalation.",
            )
            return Outcome(
                GateDecision.DENY, ReasonCode.NO_MATCHING_PERMIT.value, pending_id=pending_id
            )

        with self._lock:
            current_epoch = self._epoch
        if action.epoch != current_epoch:
            return self._refuse(action.run_id, pending_id, "STALE_EPOCH")

        try:
            claimed = self._approvals.claim(pending_id, expected_version, action.arguments_sha256)
        except ApprovalError as error:
            return self._refuse(action.run_id, pending_id, error.code)

        self._events.append(
            claimed.run_id,
            Actor.HUMAN,
            EventType.HUMAN_DECIDED,
            pending_id=pending_id,
            tool=claimed.tool_name,
            decision="APPROVED",
        )
        outcome = self._execute(
            claimed.run_id, claimed.proposal_id, claimed.tool_name, claimed.arguments, recheck
        )
        self._approvals.settle(
            pending_id, PendingStatus.EXECUTED if outcome.executed else PendingStatus.FAILED
        )
        return Outcome(
            GateDecision.ALLOW if outcome.executed else GateDecision.DENY,
            outcome.reason_code,
            executed=outcome.executed,
            result=outcome.result,
            pending_id=pending_id,
            determining_policies=recheck.determining_policies,
            error=outcome.error,
        )

    def deny(self, pending_id: str, expected_version: int) -> Outcome:
        try:
            action = self._approvals.get(pending_id)
        except ApprovalError as error:
            return self._refuse(UNATTRIBUTED_RUN, pending_id, error.code)
        try:
            self._approvals.deny(pending_id, expected_version)
        except ApprovalError as error:
            return self._refuse(action.run_id, pending_id, error.code)
        self._events.append(
            action.run_id,
            Actor.HUMAN,
            EventType.HUMAN_DECIDED,
            pending_id=pending_id,
            tool=action.tool_name,
            decision="DENIED",
        )
        return Outcome(GateDecision.DENY, "HUMAN_DENIED", pending_id=pending_id)

    def _refuse(self, run_id: str, pending_id: str, code: str) -> Outcome:
        self._events.append(
            run_id,
            Actor.CEDAR,
            EventType.TOOL_BLOCKED,
            pending_id=pending_id,
            reason_code=code,
        )
        return Outcome(GateDecision.DENY, code, pending_id=pending_id)

    # -- execution ----------------------------------------------------------

    def _execute(
        self,
        run_id: str,
        proposal_id: str,
        tool_name: str,
        arguments: Mapping[str, object],
        verdict: AuthorizationResult,
    ) -> Outcome:
        """Run the tool. Reached only from an authorized path."""
        # An explicit table, not getattr: a tool name is never allowed to
        # select an arbitrary attribute of this object.
        dispatch: dict[str, Callable[..., Any]] = {
            "lookup_order": self.__tools.lookup_order,
            "lookup_customer": self.__tools.lookup_customer,
            "refund_order": self.__tools.refund_order,
            "send_email": self.__tools.send_email,
            "export_customers": self.__tools.export_customers,
        }
        call = dispatch.get(tool_name)
        if call is None:
            return self._block(run_id, proposal_id, tool_name, verdict)

        try:
            result = call(**arguments)
        except DomainError as error:
            self._events.append(
                run_id,
                Actor.TOOL,
                EventType.TOOL_FAILED,
                proposal_id=proposal_id,
                tool=tool_name,
                code=error.code,
                message=str(error),
            )
            return Outcome(
                GateDecision.ALLOW,
                verdict.reason_code.value,
                executed=False,
                determining_policies=verdict.determining_policies,
                error={"code": error.code, "message": str(error)},
            )

        payload = result if isinstance(result, dict) else {"records": result}
        self._events.append(
            run_id,
            Actor.TOOL,
            EventType.TOOL_EXECUTED,
            proposal_id=proposal_id,
            tool=tool_name,
            result=payload,
        )
        return Outcome(
            GateDecision.ALLOW,
            verdict.reason_code.value,
            executed=True,
            result=payload,
            determining_policies=verdict.determining_policies,
        )

    # -- lifecycle ----------------------------------------------------------

    def reset(self) -> None:
        """Restore fixtures and invalidate every outstanding capability.

        The epoch bump is what stops an approval captured before a reset from
        authorizing anything afterwards.
        """
        with self._lock:
            self._epoch += 1
        self._reset_store()
        self._approvals.reset()
        self._events.reset()
