import sys
from pathlib import Path

import pytest

from app.config import Settings
from app.policy import AuthorizationRequest, CedarPolicyEngine

PRINCIPAL = "support-agent"
RESOURCE_TYPE = "Store"
RESOURCE_ID = "demo"


@pytest.fixture(scope="session")
def policy_dir() -> Path:
    return Settings().policy_dir


@pytest.fixture(scope="session")
def engine(policy_dir: Path) -> CedarPolicyEngine:
    return CedarPolicyEngine(policy_dir)


@pytest.fixture
def propose():
    """Build the request exactly as the runtime will, so the matrix cannot
    pass against a shape the agent never produces."""

    def _propose(tool_name: str, **arguments: object) -> AuthorizationRequest:
        return AuthorizationRequest(
            principal_id=PRINCIPAL,
            tool_name=tool_name,
            resource_type=RESOURCE_TYPE,
            resource_id=RESOURCE_ID,
            arguments=arguments,
        )

    return _propose


@pytest.fixture(autouse=True)
def no_llm_imported():
    """Volume II must be provable without a model. If a policy test ever pulls
    in an agent SDK, the determinism claim is no longer honest."""
    yield
    assert "strands" not in sys.modules
