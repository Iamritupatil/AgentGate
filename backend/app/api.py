"""HTTP surface over the authority gateway.

Every route here goes through `AuthorityGateway`. None of them can reach a
business tool directly, and none of them accepts a decision from the caller:
the client says what it wants to do, Cedar says whether it may.

The approval routes deliberately take only an id and a version. They never
accept replacement arguments, because an endpoint that let a caller supply the
arguments to execute would make the human approval meaningless.
"""

from typing import Any, Callable, Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.events import Actor
from app.policy.arguments import TOOL_SPECS
from app.policy.engine import PolicyConfigurationError
from app.policy.generic import describe, evaluate_generic
from app.policy.studio import PolicyDefinition
from app.policy.ai import DraftError, draft_payload, draft_policy
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


class GenericPrincipal(BaseModel):
    type: str = Field(min_length=1, max_length=64)
    id: str = Field(min_length=1, max_length=128)


class GenericResource(BaseModel):
    type: str = Field(min_length=1, max_length=64)
    id: str = Field(min_length=1, max_length=128)


class EvaluateRequest(BaseModel):
    principal: GenericPrincipal
    action: str = Field(min_length=1, max_length=128)
    resource: GenericResource
    context: dict[str, Any] = Field(default_factory=dict)


class EvaluateResponse(BaseModel):
    decision: str
    principal: str
    action: str
    resource: str
    reason: str
    reason_code: str
    matched_policy: str | None = None


class PolicyPayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    principal_type: str = Field(min_length=1, max_length=64)
    principal_id: str = Field(min_length=1, max_length=128)
    action: str = Field(min_length=1, max_length=128)
    resource_type: str = Field(min_length=1, max_length=64)
    decision: Literal["ALLOW", "REQUIRE_APPROVAL", "DENY"]
    context_field: str | None = None
    allow_threshold: int | None = Field(default=None, ge=0)
    approval_threshold: int | None = Field(default=None, ge=0)


class PolicyResponse(PolicyPayload):
    id: str
    active: bool

    @classmethod
    def of(cls, definition: PolicyDefinition) -> "PolicyResponse":
        return cls(**{key: value for key, value in definition.__dict__.items()} if hasattr(definition, "__dict__") else {
            "id": definition.id, "name": definition.name, "principal_type": definition.principal_type,
            "principal_id": definition.principal_id, "action": definition.action,
            "resource_type": definition.resource_type, "decision": definition.decision,
            "context_field": definition.context_field, "allow_threshold": definition.allow_threshold,
            "approval_threshold": definition.approval_threshold, "active": definition.active,
        })


class DraftRequest(BaseModel):
    description: str = Field(min_length=1, max_length=2000)


class DraftResponse(BaseModel):
    draft: dict[str, Any]
    cedar_preview: str
    active: bool = False


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

    @router.post("/gate/evaluate", response_model=EvaluateResponse, tags=["gate"])
    def evaluate(payload: EvaluateRequest, request: Request) -> EvaluateResponse:
        verdict = evaluate_generic(
            request.app.state.policy_engine,
            payload.principal.id,
            payload.action,
            payload.resource.type,
            payload.resource.id,
            payload.context,
            principal_type=payload.principal.type,
        )
        outcome = describe(verdict)
        return EvaluateResponse(
            decision=outcome["decision"],
            principal=f"{payload.principal.type}:{payload.principal.id}",
            action=payload.action,
            resource=f"{payload.resource.type}:{payload.resource.id}",
            reason=outcome["reason"],
            reason_code=outcome["reason_code"],
            matched_policy=outcome["matched_policy"],
        )

    @router.get("/policies", response_model=list[PolicyResponse], tags=["policies"])
    def policies(request: Request) -> list[PolicyResponse]:
        return [PolicyResponse.of(item) for item in request.app.state.policy_store.list()]

    @router.post("/policies", response_model=PolicyResponse, status_code=201, tags=["policies"])
    def create_policy(payload: PolicyPayload, request: Request) -> PolicyResponse:
        try:
            definition = PolicyDefinition.from_payload(payload.model_dump())
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        request.app.state.policy_store.save(definition)
        return PolicyResponse.of(definition)

    @router.post("/policies/draft", response_model=DraftResponse, tags=["policies"])
    def draft_policy_route(payload: DraftRequest, request: Request) -> DraftResponse:
        try:
            definition = draft_policy(
                payload.description,
                api_key=request.app.state.settings.ai_api_key,
                base_url=request.app.state.settings.ai_base_url,
                model=request.app.state.settings.ai_model,
            )
            from app.policy.studio import generate_cedar

            execute, approval = generate_cedar(definition)
        except (DraftError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return DraftResponse(
            draft=draft_payload(definition),
            cedar_preview="\n\n".join(item for item in (execute, approval) if item),
        )

    @router.get("/policies/{policy_id}", response_model=PolicyResponse, tags=["policies"])
    def get_policy(policy_id: str, request: Request) -> PolicyResponse:
        definition = request.app.state.policy_store.get(policy_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="Policy not found.")
        return PolicyResponse.of(definition)

    @router.post("/policies/{policy_id}/activate", response_model=PolicyResponse, tags=["policies"])
    def activate_policy(policy_id: str, request: Request) -> PolicyResponse:
        store = request.app.state.policy_store
        definition = store.get(policy_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="Policy not found.")
        active = PolicyDefinition(**{**{field: getattr(definition, field) for field in definition.__slots__}, "active": True})
        definitions = tuple(item for item in store.list() if item.active and item.id != policy_id) + (active,)
        try:
            # Compiles and Cedar-validates the candidate set without touching
            # the engine. Only once this succeeds do we replace the live set
            # and persist the flag, so a rejected policy is never active in
            # either place — the last-known-good set keeps deciding.
            request.app.state.policy_engine.replace_dynamic_policies(definitions)
        except PolicyConfigurationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        store.activate(policy_id)
        return PolicyResponse.of(active)

    @router.delete("/policies/{policy_id}", status_code=204, tags=["policies"])
    def delete_policy(policy_id: str, request: Request) -> Response:
        store = request.app.state.policy_store
        definition = store.get(policy_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="Policy not found.")
        if definition.active:
            definitions = tuple(item for item in store.list() if item.active and item.id != policy_id)
            try:
                request.app.state.policy_engine.replace_dynamic_policies(definitions)
            except PolicyConfigurationError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
        store.delete(policy_id)
        return Response(status_code=204)

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
