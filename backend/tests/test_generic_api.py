import pytest


@pytest.fixture(autouse=True)
def clean(client):
    client.post("/api/reset")


def evaluate(client, principal, action, resource, context):
    return client.post(
        "/api/gate/evaluate",
        json={
            "principal": {"type": "Agent", "id": principal},
            "action": action,
            "resource": resource,
            "context": context,
        },
    )


def test_generic_refund_response_uses_cedar_decision(client):
    response = evaluate(
        client,
        "support-agent",
        "refund_order",
        {"type": "Order", "id": "ORD-1"},
        {"amount": 8499},
    )

    assert response.status_code == 200
    assert response.json() == {
        "decision": "REQUIRE_APPROVAL",
        "principal": "Agent:support-agent",
        "action": "refund_order",
        "resource": "Order:ORD-1",
        "reason": "The action is not autonomous, but human approval may be requested.",
        "reason_code": "APPROVAL_PERMITTED",
        "matched_policy": "allow_refund_approval_request",
    }


@pytest.mark.parametrize(
    ("principal", "action", "context", "decision"),
    [
        ("support-agent", "lookup_order", {"order_id": "ORD-1"}, "ALLOW"),
        ("support-agent", "refund_order", {"amount": 2000}, "ALLOW"),
        ("support-agent", "refund_order", {"amount": 10000}, "REQUIRE_APPROVAL"),
        ("support-agent", "refund_order", {"amount": 10001}, "DENY"),
        ("support-agent", "export_customers", {}, "DENY"),
        ("finance-agent", "refund_order", {"amount": 10000}, "ALLOW"),
        ("finance-agent", "refund_order", {"amount": 10001}, "REQUIRE_APPROVAL"),
        ("finance-agent", "refund_order", {"amount": 50001}, "DENY"),
        ("deployment-agent", "read_logs", {"environment": "production"}, "ALLOW"),
        ("deployment-agent", "deploy_production", {}, "REQUIRE_APPROVAL"),
        ("deployment-agent", "delete_production_database", {}, "DENY"),
        ("intern-agent", "refund_order", {"amount": 1}, "DENY"),
    ],
)
def test_generic_role_matrix(client, principal, action, context, decision):
    resource_type = "Environment" if action in {"read_logs", "deploy_production"} else "Database" if action == "delete_production_database" else "Order"
    response = evaluate(client, principal, action, {"type": resource_type, "id": "production" if resource_type != "Order" else "ORD-1"}, context)
    assert response.status_code == 200
    assert response.json()["decision"] == decision


def test_unknown_principal_and_action_default_to_deny(client):
    unknown_principal = evaluate(client, "unknown-agent", "lookup_order", {"type": "Order", "id": "ORD-1"}, {"order_id": "ORD-1"})
    unknown_action = evaluate(client, "support-agent", "launch_satellite", {"type": "Order", "id": "ORD-1"}, {})

    assert unknown_principal.json()["decision"] == "DENY"
    assert unknown_action.json()["decision"] == "DENY"
    assert unknown_action.json()["reason_code"] == "UNKNOWN_ACTION"
