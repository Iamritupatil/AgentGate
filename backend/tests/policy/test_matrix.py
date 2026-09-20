"""The complete policy boundary matrix.

This file is the acceptance evidence for Volume II. Every case runs through
the real Cedar engine. Nothing here constructs a model, and the expected
values are written out one by one rather than derived from the same arithmetic
the policies use.
"""

import pytest

from app.policy import GateDecision, ReasonCode

ALLOW = GateDecision.ALLOW
APPROVAL = GateDecision.REQUIRE_APPROVAL
DENY = GateDecision.DENY


MATRIX = [
        # Reads carry no authority risk in this demo.
        ("lookup_order", {"order_id": "ORD-1001"}, ALLOW, ReasonCode.EXECUTE_PERMITTED),
        ("lookup_customer", {"customer_id": "CUS-1001"}, ALLOW, ReasonCode.EXECUTE_PERMITTED),
        # Recorded-only email.
        (
            "send_email",
            {"customer_id": "CUS-1001", "subject": "Your refund", "body": "It is on the way."},
            ALLOW,
            ReasonCode.EXECUTE_PERMITTED,
        ),
        # The agent's own refund limit, and the rupee on either side of it.
        ("refund_order", {"order_id": "ORD-1001", "amount": 799}, ALLOW, ReasonCode.EXECUTE_PERMITTED),
        ("refund_order", {"order_id": "ORD-1001", "amount": 1999}, ALLOW, ReasonCode.EXECUTE_PERMITTED),
        ("refund_order", {"order_id": "ORD-1001", "amount": 2000}, ALLOW, ReasonCode.EXECUTE_PERMITTED),
        ("refund_order", {"order_id": "ORD-1002", "amount": 2001}, APPROVAL, ReasonCode.APPROVAL_PERMITTED),
        ("refund_order", {"order_id": "ORD-1002", "amount": 8499}, APPROVAL, ReasonCode.APPROVAL_PERMITTED),
        # The human ceiling, and the rupee that breaks through it.
        ("refund_order", {"order_id": "ORD-1002", "amount": 9999}, APPROVAL, ReasonCode.APPROVAL_PERMITTED),
        ("refund_order", {"order_id": "ORD-1002", "amount": 10000}, APPROVAL, ReasonCode.APPROVAL_PERMITTED),
        ("refund_order", {"order_id": "ORD-1003", "amount": 10001}, DENY, ReasonCode.NO_MATCHING_PERMIT),
        ("refund_order", {"order_id": "ORD-1003", "amount": 25000}, DENY, ReasonCode.NO_MATCHING_PERMIT),
        # Bulk data release is forbidden, not merely unpermitted.
        ("export_customers", {}, DENY, ReasonCode.EXPLICIT_FORBID),
]


@pytest.mark.parametrize(("tool", "arguments", "decision", "reason"), MATRIX)
def test_policy_matrix(engine, propose, tool, arguments, decision, reason):
    result = engine.evaluate(propose(tool, **arguments))
    assert result.decision is decision
    assert result.reason_code is reason


def test_every_declared_tool_appears_in_the_matrix():
    """A new tool must not be able to slip in without a stated decision."""
    from app.policy.arguments import TOOL_SPECS

    assert {case[0] for case in MATRIX} == set(TOOL_SPECS)


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("refund_order", {"order_id": "ORD-1001", "amount": True}),
        ("refund_order", {"order_id": "ORD-1001", "amount": False}),
        ("refund_order", {"order_id": "ORD-1001", "amount": 799.0}),
        ("refund_order", {"order_id": "ORD-1001", "amount": "799"}),
        ("refund_order", {"order_id": "ORD-1001", "amount": -799}),
        ("refund_order", {"order_id": "ORD-1001", "amount": None}),
        ("refund_order", {"order_id": "ORD-1001"}),
        ("refund_order", {"amount": 799}),
        ("refund_order", {"order_id": "", "amount": 799}),
        ("refund_order", {"order_id": "ORD-1001", "amount": 799, "approved": True}),
        ("lookup_order", {"order_id": 1001}),
        ("export_customers", {"confirm": "yes"}),
    ],
)
def test_malformed_arguments_deny_before_cedar(engine, propose, tool, arguments):
    """Bad input is a refusal, not an engine error and never an execution."""
    result = engine.evaluate(propose(tool, **arguments))
    assert result.decision is DENY
    assert result.reason_code is ReasonCode.INVALID_ARGUMENTS


@pytest.mark.parametrize(
    "tool",
    ["delete_customer", "refund_order ", "REFUND_ORDER", "request_refund_approval", "", "__init__"],
)
def test_unknown_tools_are_denied(engine, propose, tool):
    """Including the synthetic approval action: it exists to be asked about,
    never to be proposed as something to run."""
    result = engine.evaluate(propose(tool, order_id="ORD-1001", amount=799))
    assert result.decision is DENY
    assert result.reason_code is ReasonCode.UNKNOWN_ACTION


def test_amount_at_zero_is_authorized_but_the_domain_still_refuses_it(engine, propose):
    """Cedar owns authority; the domain owns business validity. A ₹0 refund is
    inside the agent's spending limit and is rejected as meaningless later."""
    from app.domain.errors import DomainError
    from app.domain.memory import InMemoryStore

    assert engine.evaluate(propose("refund_order", order_id="ORD-1001", amount=0)).decision is ALLOW
    with pytest.raises(DomainError):
        InMemoryStore().refund_order("ORD-1001", 0)


def test_denial_feedback_carries_no_route_around_the_policy(engine, propose):
    result = engine.evaluate(propose("refund_order", order_id="ORD-1003", amount=25000))
    feedback = result.as_denial_feedback()
    assert feedback == {
        "type": "policy_denial",
        "decision": "DENY",
        "reason_code": "NO_MATCHING_PERMIT",
        "retryable": False,
    }
    assert "2000" not in repr(feedback) and "10000" not in repr(feedback)


def test_determining_policy_is_named_for_the_audit_trail(engine, propose):
    allowed = engine.evaluate(propose("refund_order", order_id="ORD-1001", amount=799))
    assert allowed.determining_policies == ("allow_refund_within_agent_limit",)

    escalated = engine.evaluate(propose("refund_order", order_id="ORD-1002", amount=8499))
    assert escalated.determining_policies == ("allow_refund_approval_request",)

    forbidden = engine.evaluate(propose("export_customers"))
    assert forbidden.determining_policies == ("forbid_customer_export",)
