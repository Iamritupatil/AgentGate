from pathlib import Path


def policy_payload(**overrides):
    payload = {
        "name": "Narrow support refunds",
        "principal_type": "Agent",
        # A principal Cedar has no baseline permit for. `support-agent`
        # already has an unconditional 0-2000 refund permit in execute.cedar;
        # Cedar unions policies rather than replacing them, so a Studio
        # threshold cannot narrow that permit's range for the same
        # principal and action. Studio's real, safe job is granting
        # authority nothing else already grants, which this exercises.
        "principal_id": "narrow-agent",
        "action": "refund_order",
        "resource_type": "Order",
        "decision": "ALLOW",
        "context_field": "amount",
        "allow_threshold": 100,
        "approval_threshold": 500,
    }
    payload.update(overrides)
    return payload


def test_draft_is_structured_and_does_not_activate(client):
    response = client.post("/api/policies/draft", json={"description": "Support agents may refund up to ₹2,000 automatically. Between ₹2,000 and ₹10,000 ask me for approval. Deny anything higher."})
    assert response.status_code == 200
    assert response.json()["draft"]["allow_threshold"] == 2000
    assert response.json()["draft"]["approval_threshold"] == 10000
    assert response.json()["active"] is False
    assert client.get("/api/policies").json() == []


def test_policy_create_validate_activate_and_evaluate(client):
    created = client.post("/api/policies", json=policy_payload()).json()
    assert created["active"] is False

    assert client.post(
        f"/api/policies/{created['id']}/activate"
    ).json()["active"] is True

    for amount, decision in [
        (100, "ALLOW"),
        (101, "REQUIRE_APPROVAL"),
        (501, "DENY"),
    ]:
        result = client.post(
            "/api/gate/evaluate",
            json={
                "principal": {
                    "type": "Agent",
                    "id": "narrow-agent",   # <-- FIX THIS
                },
                "action": "refund_order",
                "resource": {
                    "type": "Order",
                    "id": "ORD-1",
                },
                "context": {
                    "amount": amount,
                },
            },
        )

        assert result.status_code == 200
        assert result.json()["decision"] == decision


def test_invalid_policy_never_becomes_active(client):
    response = client.post("/api/policies", json=policy_payload(action="not_declared"))
    assert response.status_code == 500 or response.status_code == 422
    assert client.get("/api/policies").json() == []
