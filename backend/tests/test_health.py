import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_contract(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "status": "ok",
        "service": "AgentGate",
        "version": "0.1.0",
        "environment": "test",
        "phase": "authority",
        "policy_engine": "cedar",
    }


def test_factory_uses_configuration_without_cross_app_leakage(client):
    settings = Settings(_env_file=None, app_name="Isolated API", environment="production")
    with TestClient(create_app(settings)) as other_client:
        assert other_client.get("/health").json()["service"] == "Isolated API"
        assert other_client.get("/health").json()["environment"] == "production"
    assert client.get("/health").json()["service"] == "AgentGate"
    assert client.get("/health").json()["environment"] == "test"


def test_health_does_not_accept_mutation(client):
    assert client.post("/health", json={}).status_code == 405


@pytest.mark.parametrize(
    "path",
    [
        "/runs",
        "/refunds",
        "/reset",
        "/api/refunds",
        "/api/refund_order",
        "/api/tools/refund_order",
        "/api/tools/export_customers",
        "/api/store",
    ],
)
def test_there_is_no_route_that_reaches_a_tool_directly(client, path):
    """Business operations exist only behind `/api/actions`, where Cedar sees
    them. A route that called a tool by name would be a bypass."""
    assert client.post(path, json={}).status_code == 404


def test_the_api_surface_is_exactly_what_the_gate_needs(client):
    """New routes are a security decision, so they are listed here explicitly
    rather than accepted because the suite still passes."""
    assert set(client.get("/openapi.json").json()["paths"]) == {
        "/health",
        "/api/health",
        "/api/tools",
        "/api/actions",
        "/api/pending",
        "/api/pending/{pending_id}",
        "/api/timeline",
        "/api/state",
        "/api/reset",
        "/api/policy-test",
        "/api/gate/evaluate",
        "/api/policies",
        "/api/policies/{policy_id}",
        "/api/policies/{policy_id}/activate",
        "/api/policies/draft",
        "/api/policies/draft",
    }


def test_cors_allows_configured_frontend(client):
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_rejects_unconfigured_origin(client):
    response = client.options(
        "/health",
        headers={
            "Origin": "https://unconfigured.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cors_allows_preview_origins_by_pattern(tmp_path):
    """Vercel names every preview deployment differently, so a split deployment
    cannot enumerate the browser origins ahead of time."""
    settings = Settings(
        _env_file=None,
        environment="test",
        cors_origins=[],
        cors_origin_regex=r"https://agentgate-[a-z0-9]+\.vercel\.app",
        policy_store_path=tmp_path / "policies.json",
    )

    with TestClient(create_app(settings)) as client:
        allowed = client.options(
            "/health",
            headers={
                "Origin": "https://agentgate-7f3a1c.vercel.app",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert allowed.status_code == 200
        assert (
            allowed.headers["access-control-allow-origin"]
            == "https://agentgate-7f3a1c.vercel.app"
        )

        # The pattern is matched against the whole origin, so a lookalike host
        # that merely starts with an allowed one stays out.
        spoofed = client.options(
            "/health",
            headers={
                "Origin": "https://agentgate-7f3a1c.vercel.app.attacker.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert spoofed.status_code == 400
        assert "access-control-allow-origin" not in spoofed.headers
