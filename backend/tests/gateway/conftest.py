import pytest

from app.approvals import InMemoryApprovalStore
from app.config import Settings
from app.domain.memory import InMemoryStore
from app.events import EventLog
from app.policy import CedarPolicyEngine
from app.services import AuthorityGateway
from app.tools.business import BusinessTools


@pytest.fixture(scope="session")
def engine() -> CedarPolicyEngine:
    return CedarPolicyEngine(Settings().policy_dir)


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def events() -> EventLog:
    return EventLog()


@pytest.fixture
def gateway(engine, store, events) -> AuthorityGateway:
    return AuthorityGateway(
        engine=engine,
        tools=BusinessTools(store),
        approvals=InMemoryApprovalStore(),
        events=events,
        reset_store=store.reset,
    )
