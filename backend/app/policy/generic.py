"""Shared request-shaping for generic external callers.

`POST /api/gate/evaluate` and the MCP adapter must return the same decision
for the same {principal, action, resource, context}. This module is the one
place a generic external shape becomes an `AuthorizationRequest` and a
decision becomes a plain payload, so there is exactly one implementation of
that shaping for both transports to share. Two separate implementations is
how a caller ends up ALLOWed over one transport and DENYed over the other for
an identical request — which is precisely the defect this module replaces.
"""

from typing import Any, Mapping

from app.policy.contract import AuthorizationRequest, AuthorizationResult, GateDecision, PolicyEngine, ReasonCode

REASON_TEXT: Mapping[str, str] = {
    "EXECUTE_PERMITTED": "The action is permitted for this principal and resource.",
    "APPROVAL_PERMITTED": "The action is not autonomous, but human approval may be requested.",
    "EXPLICIT_FORBID": "An explicit Cedar forbid blocks this action.",
    "NO_MATCHING_PERMIT": "No Cedar permit matches this request.",
    "UNKNOWN_ACTION": "The action is not declared by AgentGate.",
    "UNKNOWN_PRINCIPAL_TYPE": "The principal type is not declared by the Cedar schema.",
    "INVALID_ARGUMENTS": "The request context does not match the declared action inputs.",
    "POLICY_ENGINE_ERROR": "Cedar could not produce a trustworthy decision.",
}

# The Cedar schema declares exactly one principal entity type. Every generic
# caller states a `principal.type`; a type this schema never declared is not
# something the engine can honestly evaluate, so it is refused here rather
# than silently evaluated as if it had said "Agent".
SUPPORTED_PRINCIPAL_TYPES = frozenset({"Agent"})


def build_request(
    principal_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    context: Mapping[str, Any],
) -> AuthorizationRequest:
    """Shape one generic external call into the request the engine expects.

    `order_id` is backfilled from the resource id for `refund_order` so a
    caller who names the order once, as the resource, is not made to repeat
    it inside `context` as well.
    """
    arguments: dict[str, Any] = dict(context)
    if action == "refund_order" and "order_id" not in arguments:
        arguments["order_id"] = resource_id
    return AuthorizationRequest(
        principal_id=principal_id,
        tool_name=action,
        resource_type=resource_type,
        resource_id=resource_id,
        arguments=arguments,
        generic=True,
    )


def evaluate_generic(
    engine: PolicyEngine,
    principal_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    context: Mapping[str, Any],
    principal_type: str = "Agent",
) -> AuthorizationResult:
    if principal_type not in SUPPORTED_PRINCIPAL_TYPES:
        return AuthorizationResult(GateDecision.DENY, ReasonCode.UNKNOWN_PRINCIPAL_TYPE)
    return engine.evaluate(build_request(principal_id, action, resource_type, resource_id, context))


def describe(result: AuthorizationResult) -> dict[str, Any]:
    """The plain-payload half of a generic decision: reason text, reason
    code and the matched policy name, independent of the transport."""
    return {
        "decision": result.decision.value,
        "reason_code": result.reason_code.value,
        "reason": REASON_TEXT.get(result.reason_code.value, "The request was denied."),
        "matched_policy": result.determining_policies[0] if result.determining_policies else None,
    }
