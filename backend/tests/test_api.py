"""The three scenarios over HTTP, plus the routes an attacker would try.

The control room talks to these endpoints, so anything provable here is
provable in the demo.
"""

import pytest


@pytest.fixture(autouse=True)
def clean(client):
    client.post("/api/reset")
    yield


def order(client, order_id: str) -> dict:
    orders = client.get("/api/state").json()["orders"]
    return next(item for item in orders if item["order_id"] == order_id)


def test_scenario_a_over_http(client):
    response = client.post(
        "/api/actions", json={"tool": "refund_order", "arguments": {"order_id": "ORD-1001", "amount": 799}}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "ALLOW"
    assert body["executed"] is True
    assert order(client, "ORD-1001")["refunded_amount"] == 799


def test_scenario_b_over_http(client):
    parked = client.post(
        "/api/actions",
        json={"tool": "refund_order", "arguments": {"order_id": "ORD-1002", "amount": 8499}},
    ).json()

    assert parked["decision"] == "REQUIRE_APPROVAL"
    assert parked["executed"] is False
    assert order(client, "ORD-1002")["refunded_amount"] == 0

    pending = client.get("/api/pending").json()
    assert len(pending) == 1
    assert pending[0]["pending_id"] == parked["pending_id"]
    assert pending[0]["arguments"] == {"order_id": "ORD-1002", "amount": 8499}

    approved = client.post(
        f"/api/pending/{parked['pending_id']}", json={"decision": "approve", "version": 1}
    ).json()

    assert approved["executed"] is True
    assert order(client, "ORD-1002")["refunded_amount"] == 8499
    assert client.get("/api/pending").json() == []


def test_scenario_b_denied_over_http(client):
    parked = client.post(
        "/api/actions",
        json={"tool": "refund_order", "arguments": {"order_id": "ORD-1002", "amount": 8499}},
    ).json()

    denied = client.post(
        f"/api/pending/{parked['pending_id']}", json={"decision": "deny", "version": 1}
    ).json()

    assert denied["decision"] == "DENY"
    assert denied["executed"] is False
    assert order(client, "ORD-1002")["refunded_amount"] == 0


def test_scenario_c_over_http(client):
    refund = client.post(
        "/api/actions",
        json={"tool": "refund_order", "arguments": {"order_id": "ORD-1003", "amount": 25000}},
    ).json()
    export = client.post("/api/actions", json={"tool": "export_customers", "arguments": {}}).json()

    assert refund["decision"] == "DENY" and refund["pending_id"] is None
    assert export["decision"] == "DENY" and export["result"] is None
    assert export["reason_code"] == "EXPLICIT_FORBID"
    assert order(client, "ORD-1003")["refunded_amount"] == 0
    assert client.get("/api/state").json()["refunds"] == []


def test_double_approval_over_http_refunds_once(client):
    parked = client.post(
        "/api/actions",
        json={"tool": "refund_order", "arguments": {"order_id": "ORD-1002", "amount": 8499}},
    ).json()
    pending_id = parked["pending_id"]

    first = client.post(f"/api/pending/{pending_id}", json={"decision": "approve", "version": 1}).json()
    second = client.post(f"/api/pending/{pending_id}", json={"decision": "approve", "version": 1}).json()

    assert first["executed"] is True
    assert second["executed"] is False
    assert len(client.get("/api/state").json()["refunds"]) == 1


def test_the_approval_endpoint_ignores_supplied_arguments(client):
    """An approval carries no arguments. Extra fields in the body must not
    become the thing that executes."""
    parked = client.post(
        "/api/actions",
        json={"tool": "refund_order", "arguments": {"order_id": "ORD-1002", "amount": 8499}},
    ).json()

    response = client.post(
        f"/api/pending/{parked['pending_id']}",
        json={
            "decision": "approve",
            "version": 1,
            "arguments": {"order_id": "ORD-1003", "amount": 25000},
            "tool": "export_customers",
        },
    )

    assert response.json()["executed"] is True
    assert order(client, "ORD-1002")["refunded_amount"] == 8499
    assert order(client, "ORD-1003")["refunded_amount"] == 0


def test_an_unknown_tool_is_refused_not_executed(client):
    response = client.post("/api/actions", json={"tool": "delete_everything", "arguments": {}})

    assert response.status_code == 200
    assert response.json()["decision"] == "DENY"
    assert response.json()["reason_code"] == "UNKNOWN_ACTION"


def test_a_malformed_amount_is_refused(client):
    response = client.post(
        "/api/actions",
        json={"tool": "refund_order", "arguments": {"order_id": "ORD-1001", "amount": "799"}},
    ).json()

    assert response["decision"] == "DENY"
    assert response["reason_code"] == "INVALID_ARGUMENTS"
    assert order(client, "ORD-1001")["refunded_amount"] == 0


def test_the_timeline_shows_who_proposed_the_call(client):
    """A person typing into the control room is an OPERATOR. Nothing here may
    be attributed to a model that has not run."""
    client.post("/api/actions", json={"tool": "lookup_order", "arguments": {"order_id": "ORD-1001"}})

    timeline = client.get("/api/timeline").json()
    proposed = next(event for event in timeline if event["type"] == "TOOL_PROPOSED")

    assert proposed["actor"] == "OPERATOR"
    assert "AGENT" not in [event["actor"] for event in timeline]


def test_the_policy_test_bench_reports_real_evaluations(client):
    result = client.post("/api/policy-test").json()

    assert result["total"] == 5
    assert result["passed"] == 5
    assert result["all_passed"] is True
    assert [case["actual"] for case in result["cases"]] == [
        "ALLOW",
        "ALLOW",
        "REQUIRE_APPROVAL",
        "DENY",
        "DENY",
    ]


def test_the_policy_test_bench_changes_no_business_state(client):
    """A bench that refunded ₹799 to prove it may refund ₹799 would be worse
    than useless."""
    before = client.get("/api/state").json()

    client.post("/api/policy-test")

    assert client.get("/api/state").json() == before
    assert client.get("/api/pending").json() == []


def test_reset_restores_the_demo(client):
    client.post(
        "/api/actions", json={"tool": "refund_order", "arguments": {"order_id": "ORD-1001", "amount": 799}}
    )
    client.post(
        "/api/actions",
        json={"tool": "refund_order", "arguments": {"order_id": "ORD-1002", "amount": 8499}},
    )

    client.post("/api/reset")

    assert order(client, "ORD-1001")["refunded_amount"] == 0
    assert client.get("/api/state").json()["refunds"] == []
    assert client.get("/api/pending").json() == []
    assert client.get("/api/timeline").json() == []


def test_tools_endpoint_lists_capability_not_authority(client):
    tools = client.get("/api/tools").json()

    assert set(tools) == {
        "lookup_order",
        "lookup_customer",
        "refund_order",
        "send_email",
        "export_customers",
    }
    assert tools["refund_order"] == ["amount", "order_id"]
