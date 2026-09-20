"""Application composition.

The policy engine is built once, at startup, and a malformed policy set stops
the process here rather than degrading into a gate that silently denies
everything at demo time.
"""

from typing import Literal

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse

from app import __version__
from app.api import build_router
from app.approvals import InMemoryApprovalStore
from app.config import Settings
from app.domain.memory import InMemoryStore
from app.events import EventLog
from app.policy import load_policy_engine
from app.policy.studio import PolicyStore
from app.services import AuthorityGateway
from app.tools.business import BusinessTools


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str
    environment: Literal["development", "test", "production"]
    phase: Literal["authority"] = "authority"
    policy_engine: Literal["cedar"] = "cedar"


def build_gateway(settings: Settings, engine=None) -> AuthorityGateway:
    store = InMemoryStore()
    policy_engine = engine if engine is not None else load_policy_engine(settings.policy_dir)
    return AuthorityGateway(
        engine=policy_engine,
        tools=BusinessTools(store),
        approvals=InMemoryApprovalStore(),
        events=EventLog(),
        reset_store=store.reset,
        snapshot_store=store.snapshot,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Allow isolated configuration for tests and future runtime composition."""
    config = settings if settings is not None else Settings()
    
    application = FastAPI(
    title=config.app_name,
    version=__version__,
    description="Cedar decides what the agent is allowed to do.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url="/api/redoc",
)
   
    application.state.settings = config
    policy_store = PolicyStore(config.policy_store_path)
    policy_engine = load_policy_engine(
        config.policy_dir,
        tuple(item for item in policy_store.list() if item.active),
    )
    application.state.gateway = build_gateway(config, policy_engine)
    application.state.policy_engine = policy_engine
    application.state.policy_store = policy_store
    application.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_origin_regex=config.cors_origin_regex,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Accept", "Content-Type"],
    )

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    def health(response: Response) -> HealthResponse:
        """Report process liveness, not readiness of future integrations."""
        response.headers["Cache-Control"] = "no-store"
        return HealthResponse(
            service=config.app_name,
            version=__version__,
            environment=config.environment,
        )

    application.include_router(build_router(health))
    return application


app = create_app()
