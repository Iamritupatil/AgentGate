"""Cedar-backed three-way authority gate.

The engine owns two responsibilities and no others: prove at startup that the
policy set is well formed, and answer one proposed tool call at a time. It
never touches business state, and it never asks a model anything.

Fail-closed is absolute. Every path that is not an explicit Cedar Allow ends
in DENY, including parse failures, engine exceptions and evaluation
diagnostics that report an error alongside an Allow.
"""

from dataclasses import dataclass
from pathlib import Path

from cedarpy import Decision, Entities, PolicySet, Schema, is_authorized, validate_policies

from app.policy.arguments import TOOL_SPECS, InvalidArguments, ToolSpec, normalize
from app.policy.contract import (
    AuthorizationRequest,
    AuthorizationResult,
    GateDecision,
    ReasonCode,
)

SCHEMA_FILE = "agentgate.cedarschema"
EXECUTE_FILE = "execute.cedar"
APPROVAL_FILE = "request_approval.cedar"
ENTITIES_FILE = "entities.json"

NAMESPACE = "AgentGate"


class PolicyConfigurationError(RuntimeError):
    """Raised at startup only. A malformed policy set must stop the process
    rather than degrade into a gate that quietly denies everything."""


@dataclass(frozen=True, slots=True)
class _CedarOutcome:
    allowed: bool
    determining_policies: tuple[str, ...]
    errors: tuple[str, ...]


class CedarPolicyEngine:
    """Implements `PolicyEngine`. Construct once at startup and share it."""

    def __init__(self, policy_dir: Path) -> None:
        self._policy_dir = Path(policy_dir)
        schema_text = self._read(SCHEMA_FILE)
        execute_text = self._read(EXECUTE_FILE)
        approval_text = self._read(APPROVAL_FILE)
        entities_text = self._read(ENTITIES_FILE)

        try:
            self._schema = Schema.from_str(schema_text)
        except Exception as error:
            raise PolicyConfigurationError(f"{SCHEMA_FILE} is not a valid Cedar schema: {error}") from error

        self._execute = self._parse(execute_text, EXECUTE_FILE)
        self._approval = self._parse(approval_text, APPROVAL_FILE)

        # Validation is what makes a typo in an action name a startup failure
        # instead of a silent permanent DENY at demo time.
        self._validate(execute_text, EXECUTE_FILE, schema_text)
        self._validate(approval_text, APPROVAL_FILE, schema_text)

        try:
            self._entities = Entities.from_json_str(entities_text, self._schema)
        except Exception as error:
            raise PolicyConfigurationError(f"{ENTITIES_FILE} is not a valid Cedar entity set: {error}") from error

    def _read(self, name: str) -> str:
        path = self._policy_dir / name
        try:
            return path.read_text(encoding="utf-8")
        except OSError as error:
            raise PolicyConfigurationError(f"Cannot read policy file {path}: {error}") from error

    def _parse(self, text: str, name: str) -> PolicySet:
        try:
            return PolicySet.from_str(text)
        except Exception as error:
            raise PolicyConfigurationError(f"{name} contains unparsable Cedar policy: {error}") from error

    def _validate(self, text: str, name: str, schema_text: str) -> None:
        try:
            result = validate_policies(text, schema_text)
        except Exception as error:
            raise PolicyConfigurationError(f"{name} could not be validated: {error}") from error
        if not result.validation_passed:
            raise PolicyConfigurationError(f"{name} failed schema validation: {list(result.errors)}")

    def evaluate(self, request: AuthorizationRequest) -> AuthorizationResult:
        """Answer one proposed tool call. This method does not raise."""
        spec = TOOL_SPECS.get(request.tool_name)
        if spec is None:
            return AuthorizationResult(GateDecision.DENY, ReasonCode.UNKNOWN_ACTION)

        try:
            arguments = normalize(spec, request.arguments)
        except InvalidArguments as error:
            return AuthorizationResult(GateDecision.DENY, ReasonCode.INVALID_ARGUMENTS, errors=(str(error),))

        execution = self._authorize(spec.execute_action, request, arguments)
        if execution is None:
            return AuthorizationResult(GateDecision.DENY, ReasonCode.POLICY_ENGINE_ERROR)
        if execution.allowed:
            return AuthorizationResult(
                GateDecision.ALLOW,
                ReasonCode.EXECUTE_PERMITTED,
                execution.determining_policies,
            )

        # Execution was refused. A tool with no approval path stops here, and
        # so does an explicit forbid: `export_customers` must never become a
        # question we put to a human.
        denial_reason = (
            ReasonCode.EXPLICIT_FORBID if execution.determining_policies else ReasonCode.NO_MATCHING_PERMIT
        )
        if spec.approval_action is None or execution.determining_policies:
            return AuthorizationResult(GateDecision.DENY, denial_reason, execution.determining_policies)

        escalation = self._authorize(spec.approval_action, request, arguments, policies=self._approval)
        if escalation is None:
            return AuthorizationResult(GateDecision.DENY, ReasonCode.POLICY_ENGINE_ERROR)
        if escalation.allowed:
            return AuthorizationResult(
                GateDecision.REQUIRE_APPROVAL,
                ReasonCode.APPROVAL_PERMITTED,
                escalation.determining_policies,
            )
        return AuthorizationResult(GateDecision.DENY, denial_reason, execution.determining_policies)

    def _authorize(
        self,
        action: str,
        request: AuthorizationRequest,
        arguments: dict[str, object],
        policies: PolicySet | None = None,
    ) -> _CedarOutcome | None:
        """Run one Cedar request. Returns None when the engine could not give
        a trustworthy answer, which the caller turns into DENY."""
        cedar_request = {
            "principal": {"type": f"{NAMESPACE}::Agent", "id": request.principal_id},
            "action": f'{NAMESPACE}::Action::"{action}"',
            "resource": {"type": f"{NAMESPACE}::{request.resource_type}", "id": request.resource_id},
            "context": {"input": arguments},
        }
        try:
            response = is_authorized(
                cedar_request,
                policies if policies is not None else self._execute,
                self._entities,
                self._schema,
            )
        except Exception:
            return None

        errors = tuple(str(item) for item in response.diagnostics.errors)
        if errors:
            # A policy that errored during evaluation did not participate in
            # the decision, so an Allow here is not a decision we can trust.
            return None

        annotations = response.diagnostics.id_annotations_by_reason
        determining = tuple(
            annotations.get(reason, reason) for reason in response.diagnostics.reasons
        )
        return _CedarOutcome(response.decision is Decision.Allow, determining, errors)


def load_policy_engine(policy_dir: Path) -> CedarPolicyEngine:
    return CedarPolicyEngine(policy_dir)
