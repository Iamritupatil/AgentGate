"""HTTP surface over the authority gateway.

Every route here goes through `AuthorityGateway`. None of them can reach a
business tool directly, and none of them accepts a decision from the caller:
the client says what it wants to do, Cedar says whether it may.

The approval routes deliberately take only an id and a version. They never
accept replacement arguments, because an endpoint that let a caller supply the
arguments to execute would make the human approval meaningless.
"""

from typing import Any, Callable, Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from app.events import Actor
from app.policy.arguments import TOOL_SPECS
from app.services import AuthorityGateway, Outcome

DEFAULT_RUN = "demo"


class ProposeRequest(BaseModel):
    tool: str = Field(min_length=1, max_length=64)
    arguments: dict[str, Any] = Field(default_factory=dict)
    run_id: str = Field(default=DEFAULT_RUN, min_length=1, max_length=64)


class DecisionRequest(BaseModel):
    decision: Literal["approve", "deny"]
    version: int = Field(ge=1)


class OutcomeResponse(BaseModel):
    decision: str
    reason_code: str
    executed: bool
    result: dict[str, Any] | None = None
    pending_id: str | None = None
    determining_policies: list[str] = Field(default_factory=list)
    error: dict[str, str] | None = None

    @classmethod
    def of(cls, outcome: Outcome) -> "OutcomeResponse":
        return cls(
            decision=outcome.decision.value,
            reason_code=outcome.reason_code,
            executed=outcome.executed,
            result=outcome.result,
            pending_id=outcome.pending_id,
            determining_policies=list(outcome.determining_policies),
            error=outcome.error,
        )


class PendingResponse(BaseModel):
    pending_id: str
    run_id: str
    tool: str
    arguments: dict[str, Any]
    arguments_sha256: str
    policy_reason_code: str
    version: int
    created_at: str


class EventResponse(BaseModel):
    sequence: int
    run_id: str
    actor: str
    type: str
    detail: dict[str, Any]
    at: str


class BenchCase(BaseModel):
    name: str
    tool: str
    arguments: dict[str, Any]
    expected: str
    actual: str
    passed: bool
    determining_policies: list[str] = Field(default_factory=list)


class BenchResult(BaseModel):
    passed: int
    total: int
    all_passed: bool
    cases: list[BenchCase]


# The five cases the submission promises. They are declared here and evaluated
# through the real engine; the count below is counted, never written down.
BENCH_CASES: tuple[tuple[str, str, dict[str, Any], str], ...] = (
    ("Look up an order", "lookup_order", {"order_id": "ORD-1001"}, "ALLOW"),
    ("Refund ₹799", "refund_order", {"order_id": "ORD-1001", "amount": 799}, "ALLOW"),
    ("Refund ₹8,499", "refund_order", {"order_id": "ORD-1002", "amount": 8499}, "REQUIRE_APPROVAL"),
    ("Refund ₹25,000", "refund_order", {"order_id": "ORD-1003", "amount": 25000}, "DENY"),
    ("Export all customers", "export_customers", {}, "DENY"),
)


def gateway_of(request: Request) -> AuthorityGateway:
    return request.app.state.gateway


def build_router(health: Callable[[Response], Any]) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["authority"])

    # The browser reaches the API under /api, so liveness lives here too. The
    # root /health stays for process and infrastructure checks.
    router.add_api_route("/health", health, methods=["GET"], tags=["system"])

    @router.get("/tools")
    def tools() -> dict[str, list[str]]:
        """What the agent is even able to propose. Not what it may do."""
        return {name: sorted(spec.fields) for name, spec in TOOL_SPECS.items()}

    @router.post("/actions", response_model=OutcomeResponse)
    def propose(payload: ProposeRequest, request: Request) -> OutcomeResponse:
        outcome = gateway_of(request).propose(
            payload.run_id,
            payload.tool,
            payload.arguments,
            # Typed by a person in the control room, so it is not attributed
            # to the model.
            proposed_by=Actor.OPERATOR,
        )
        return OutcomeResponse.of(outcome)

    @router.get("/pending", response_model=list[PendingResponse])
    def pending(request: Request) -> list[PendingResponse]:
        gateway = gateway_of(request)
        return [
            PendingResponse(
                pending_id=action.pending_id,
                run_id=action.run_id,
                tool=action.tool_name,
                arguments=dict(action.arguments),
                arguments_sha256=action.arguments_sha256,
                policy_reason_code=action.policy_reason_code,
                version=action.version,
                created_at=action.created_at.isoformat(),
            )
            for action in gateway.pending_actions()
        ]

    @router.post("/pending/{pending_id}", response_model=OutcomeResponse)
    def decide(pending_id: str, payload: DecisionRequest, request: Request) -> OutcomeResponse:
        gateway = gateway_of(request)
        decide_call = gateway.approve if payload.decision == "approve" else gateway.deny
        return OutcomeResponse.of(decide_call(pending_id, payload.version))

    @router.get("/timeline", response_model=list[EventResponse])
    def timeline(request: Request, run_id: str | None = None) -> list[EventResponse]:
        return [
            EventResponse(
                sequence=event.sequence,
                run_id=event.run_id,
                actor=event.actor.value,
                type=event.type.value,
                detail=event.detail,
                at=event.at.isoformat(),
            )
            for event in gateway_of(request).timeline(run_id)
        ]

    @router.get("/state")
    def state(request: Request) -> dict[str, Any]:
        """Business state as the store holds it. This is what makes a claim in
        the timeline checkable."""
        return gateway_of(request).business_state()

    @router.post("/reset")
    def reset(request: Request) -> dict[str, str]:
        gateway_of(request).reset()
        return {"status": "reset"}

    @router.post("/policy-test", response_model=BenchResult)
    def policy_test(request: Request) -> BenchResult:
        """The Policy Test Bench. Each case is evaluated by the real engine,
        with no business mutation, and the pass count is derived from the
        results rather than asserted."""
        gateway = gateway_of(request)
        cases: list[BenchCase] = []
        for name, tool, arguments, expected in BENCH_CASES:
            verdict = gateway.evaluate_only(tool, arguments)
            cases.append(
                BenchCase(
                    name=name,
                    tool=tool,
                    arguments=arguments,
                    expected=expected,
                    actual=verdict.decision.value,
                    passed=verdict.decision.value == expected,
                    determining_policies=list(verdict.determining_policies),
                )
            )
        passed = sum(1 for case in cases if case.passed)
        return BenchResult(
            passed=passed, total=len(cases), all_passed=passed == len(cases), cases=cases
        )

    return router
