import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        _env_file=None,
        app_name="AgentGate",
        environment="test",
        cors_origins=["http://localhost:5173"],
        policy_store_path=tmp_path / "policies.json",
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client
