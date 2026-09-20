"""The three demo scenarios, proved against business state rather than
against what the gateway says about itself.

Every assertion here ends at the store: a decision is only trustworthy if the
order's `refunded_amount` agrees with it.
"""

from app.domain.errors import DomainError
from app.events import Actor, EventType
from app.policy import GateDecision

RUN = "run-1"


def refunded(store, order_id: str) -> int:
    return store.lookup_order(order_id).refunded_amount


def test_scenario_a_small_refund_executes_once(gateway, store):
    """₹799 is inside the agent's own limit, so no human is involved."""
    lookup = gateway.propose(RUN, "lookup_order", {"order_id": "ORD-1001"})
    assert lookup.decision is GateDecision.ALLOW
    assert lookup.result["amount"] == 799

    outcome = gateway.propose(RUN, "refund_order", {"order_id": "ORD-1001", "amount": 799})
    assert outcome.decision is GateDecision.ALLOW
    assert outcome.executed is True
    assert outcome.result["status"] == "refunded"
    assert refunded(store, "ORD-1001") == 799
    assert len(store.snapshot().refunds) == 1


def test_scenario_b_large_refund_pauses_then_resumes_exactly_once(gateway, store):
    """₹8,499 is the centrepiece: the agent proposes, nothing moves, a human
    decides, and only then does the money move — once."""
    outcome = gateway.propose(RUN, "refund_order", {"order_id": "ORD-1002", "amount": 8499})
    assert outcome.decision is GateDecision.REQUIRE_APPROVAL
    assert outcome.executed is False
    assert outcome.pending_id is not None
    assert refunded(store, "ORD-1002") == 0, "parking an action must not move money"

    approved = gateway.approve(outcome.pending_id, expected_version=1)
    assert approved.executed is True
    assert refunded(store, "ORD-1002") == 8499
    assert len(store.snapshot().refunds) == 1


def test_scenario_b_denied_by_a_human_changes_nothing(gateway, store):
    outcome = gateway.propose(RUN, "refund_order", {"order_id": "ORD-1002", "amount": 8499})
    denied = gateway.deny(outcome.pending_id, expected_version=1)

    assert denied.decision is GateDecision.DENY
    assert denied.executed is False
    assert refunded(store, "ORD-1002") == 0
    assert store.snapshot().refunds == ()


def test_scenario_c_refund_and_export_are_both_blocked(gateway, store):
    """₹25,000 has no approval path at all, and the export is forbidden."""
    before = store.snapshot()

    refund = gateway.propose(RUN, "refund_order", {"order_id": "ORD-1003", "amount": 25000})
    assert refund.decision is GateDecision.DENY
    assert refund.pending_id is None, "a hard denial must not become a question for a human"

    export = gateway.propose(RUN, "export_customers", {})
    assert export.decision is GateDecision.DENY
    assert export.result is None
    assert export.reason_code == "EXPLICIT_FORBID"

    assert store.snapshot() == before


def test_the_timeline_tells_the_truth_about_a_block(gateway, events):
    gateway.propose(RUN, "export_customers", {})
    types = [event.type for event in events.events(RUN)]

    assert types == [EventType.TOOL_PROPOSED, EventType.POLICY_CHECKED, EventType.TOOL_BLOCKED]
    assert EventType.TOOL_EXECUTED not in types
    assert [event.actor for event in events.events(RUN)][0] is Actor.AGENT


def test_the_timeline_records_every_actor_in_the_approval_path(gateway, events):
    outcome = gateway.propose(RUN, "refund_order", {"order_id": "ORD-1002", "amount": 8499})
    gateway.approve(outcome.pending_id, expected_version=1)

    actors = [event.actor for event in events.events(RUN)]
    types = [event.type for event in events.events(RUN)]

    assert Actor.AGENT in actors and Actor.CEDAR in actors
    assert Actor.HUMAN in actors and Actor.TOOL in actors
    assert types.index(EventType.HUMAN_DECIDED) < types.index(EventType.TOOL_EXECUTED)


def test_a_failed_tool_is_never_reported_as_a_success(gateway, store):
    """The order is already refunded, so the second authorized call must come
    back as a failure even though Cedar allowed it."""
    gateway.propose(RUN, "refund_order", {"order_id": "ORD-1001", "amount": 799})
    second = gateway.propose(RUN, "refund_order", {"order_id": "ORD-1001", "amount": 1})

    assert second.decision is GateDecision.ALLOW, "policy did permit the attempt"
    assert second.executed is False, "but the store refused it"
    assert second.error["code"] == "ALREADY_REFUNDED"
    assert refunded(store, "ORD-1001") == 799


def test_reset_restores_fixtures_and_clears_the_timeline(gateway, store, events):
    gateway.propose(RUN, "refund_order", {"order_id": "ORD-1001", "amount": 799})
    assert refunded(store, "ORD-1001") == 799

    gateway.reset()

    assert refunded(store, "ORD-1001") == 0
    assert store.snapshot().refunds == ()
    assert events.events() == ()


def test_unknown_order_fails_without_claiming_success(gateway):
    outcome = gateway.propose(RUN, "lookup_order", {"order_id": "ORD-9999"})
    assert outcome.executed is False
    assert outcome.error["code"] == "NOT_FOUND"
