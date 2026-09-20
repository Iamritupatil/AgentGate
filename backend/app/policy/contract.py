"""The authority boundary the rest of AgentGate depends on.

Nothing outside this package may infer a decision from a tool name, an amount
or a model response. Callers receive a `GateDecision` and act on it.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol


class GateDecision(str, Enum):
    """Cedar answers Allow or Deny; REQUIRE_APPROVAL is composed from two checks."""

    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


class ReasonCode(str, Enum):
    """Stable codes. The UI, the agent's denial feedback and the audit trail
    read these, never the engine's free-text diagnostics."""

    EXECUTE_PERMITTED = "EXECUTE_PERMITTED"
    APPROVAL_PERMITTED = "APPROVAL_PERMITTED"
    NO_MATCHING_PERMIT = "NO_MATCHING_PERMIT"
    EXPLICIT_FORBID = "EXPLICIT_FORBID"
    INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
    UNKNOWN_ACTION = "UNKNOWN_ACTION"
    UNKNOWN_PRINCIPAL_TYPE = "UNKNOWN_PRINCIPAL_TYPE"
    POLICY_ENGINE_ERROR = "POLICY_ENGINE_ERROR"


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    principal_id: str
    tool_name: str
    resource_type: str
    resource_id: str
    arguments: Mapping[str, object]
    generic: bool = False


@dataclass(frozen=True, slots=True)
class AuthorizationResult:
    decision: GateDecision
    reason_code: ReasonCode
    determining_policies: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def allows_execution(self) -> bool:
        """The only sanctioned way to ask 'may this run right now?'."""
        return self.decision is GateDecision.ALLOW

    def as_denial_feedback(self) -> dict[str, object]:
        """JSON-safe structured feedback handed back to the model on a block.

        Carries no hidden reasoning and no hint about how to retry around the
        policy, because the model must not be able to negotiate with it.
        """
        return {
            "type": "policy_denial",
            "decision": self.decision.value,
            "reason_code": self.reason_code.value,
            "retryable": False,
        }


class PolicyEngine(Protocol):
    def evaluate(self, request: AuthorizationRequest) -> AuthorizationResult:
        """Return a three-way decision, or DENY. Never raise."""
        ...
