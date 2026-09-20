"""Validated policy definitions and Cedar generation for Policy Studio.

Every value that reaches `generate_cedar` is interpolated into Cedar source text,
so every one of them is constrained to a literal-safe alphabet here. A policy id
or principal id carrying a quote could close the policy and append another one,
which would be a policy injection with the authority of the whole gate.
"""

import json
import os
import re
import tempfile
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from app.policy.arguments import GENERIC_ACTION_SPECS, TOOL_SPECS

Decision = Literal["ALLOW", "REQUIRE_APPROVAL", "DENY"]
ALLOWED_RESOURCE_TYPES = {"Store", "Order", "Environment", "Database"}
APPROVAL_ACTIONS = {
    "refund_order": "request_refund_approval",
    "deploy_production": "request_deploy_approval",
}

# Cedar entity ids are quoted strings. Nothing outside this alphabet may reach
# the generated source, because there is no escaping that makes an arbitrary
# string safe to paste into a policy.
PRINCIPAL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]{0,63}$")
# Policy ids become `@id("studio_<id>_...")` annotations, which the engine reads
# back. A crafted id must not be able to impersonate another policy's name.
POLICY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


@dataclass(frozen=True, slots=True)
class PolicyDefinition:
    id: str
    name: str
    principal_type: str
    principal_id: str
    action: str
    resource_type: str
    decision: Decision
    context_field: str | None = None
    allow_threshold: int | None = None
    approval_threshold: int | None = None
    active: bool = False

    @classmethod
    def from_payload(cls, payload: dict[str, object], *, active: bool = False) -> "PolicyDefinition":
        definition = cls(
            id=str(payload.get("id") or f"pol-{uuid.uuid4().hex[:12]}"),
            name=str(payload.get("name", "")).strip(),
            principal_type=str(payload.get("principal_type", "")).strip(),
            principal_id=str(payload.get("principal_id", "")).strip(),
            action=str(payload.get("action", "")).strip(),
            resource_type=str(payload.get("resource_type", "")).strip(),
            decision=payload.get("decision", "DENY"),  # type: ignore[arg-type]
            context_field=str(payload["context_field"]).strip() if payload.get("context_field") else None,
            allow_threshold=payload.get("allow_threshold") if type(payload.get("allow_threshold")) is int else None,
            approval_threshold=payload.get("approval_threshold") if type(payload.get("approval_threshold")) is int else None,
            active=active,
        )
        validate_definition(definition)
        return definition


def validate_definition(definition: PolicyDefinition) -> None:
    if not all((definition.name, definition.principal_type, definition.principal_id, definition.action, definition.resource_type)):
        raise ValueError("Policy name, principal, action and resource are required.")
    if definition.principal_type != "Agent":
        raise ValueError("Only Agent principals are supported by this Cedar schema.")
    if not PRINCIPAL_ID.fullmatch(definition.principal_id):
        raise ValueError(
            "Principal id must be 1-64 characters of letters, digits, dot, underscore, at or hyphen."
        )
    if not POLICY_ID.fullmatch(definition.id):
        raise ValueError(
            "Policy id must be 1-64 characters of letters, digits, dot, underscore or hyphen."
        )
    if definition.resource_type not in ALLOWED_RESOURCE_TYPES:
        raise ValueError("Resource type is not declared by the Cedar schema.")
    if definition.action not in {**TOOL_SPECS, **GENERIC_ACTION_SPECS}:
        raise ValueError("Action is not declared by AgentGate.")
    if definition.decision not in {"ALLOW", "REQUIRE_APPROVAL", "DENY"}:
        raise ValueError("Decision must be ALLOW, REQUIRE_APPROVAL or DENY.")
    if definition.context_field and definition.context_field not in {"amount", "environment", "order_id", "customer_id"}:
        raise ValueError("Context field is not declared by the action schema.")
    thresholds = (definition.allow_threshold, definition.approval_threshold)
    if any(value is not None and value < 0 for value in thresholds):
        raise ValueError("Thresholds must be nonnegative whole numbers.")
    if definition.approval_threshold is not None and definition.allow_threshold is None:
        raise ValueError("An approval threshold requires an allow threshold.")
    if definition.approval_threshold is not None and definition.approval_threshold < definition.allow_threshold:
        raise ValueError("Approval threshold must be at least the allow threshold.")
    if definition.context_field is not None and definition.context_field != "amount" and any(value is not None for value in thresholds):
        raise ValueError("Thresholds are supported only for numeric amount context.")
    if definition.decision == "REQUIRE_APPROVAL" and definition.action not in APPROVAL_ACTIONS:
        raise ValueError("This action has no declared Cedar approval action.")


def _principal(definition: PolicyDefinition) -> str:
    return f'AgentGate::{definition.principal_type}::"{definition.principal_id}"'


def _action(name: str) -> str:
    return f'AgentGate::Action::"{name}"'


def _resource(definition: PolicyDefinition) -> str:
    return f'AgentGate::{definition.resource_type}'


def generate_cedar(definition: PolicyDefinition) -> tuple[str, str]:
    validate_definition(definition)
    resource = _resource(definition)
    scope = f"principal == {_principal(definition)}, action == {_action(definition.action)}, resource"
    condition = f"resource is {resource}"
    execute: list[str] = []
    approval: list[str] = []
    if definition.allow_threshold is None and definition.decision == "ALLOW":
        execute.append(f'@id("studio_{definition.id}_allow")\npermit ({scope}) when {{ {condition} }};')
    elif definition.allow_threshold is None and definition.decision == "DENY":
        execute.append(f'@id("studio_{definition.id}_deny")\nforbid ({scope}) when {{ {condition} }};')
    elif definition.allow_threshold is None:
        approval_action = APPROVAL_ACTIONS[definition.action]
        approval.append(
            f'@id("studio_{definition.id}_approval")\npermit (principal == {_principal(definition)}, action == {_action(approval_action)}, resource) when {{ {condition} }};'
        )

    if definition.allow_threshold is not None:
        amount = f"context.input.{definition.context_field}"
        execute.append(
            f'@id("studio_{definition.id}_threshold_allow")\npermit ({scope}) when {{ {condition} && {amount} <= {definition.allow_threshold} }};'
        )
        if definition.approval_threshold is not None:
            approval_action = APPROVAL_ACTIONS.get(definition.action)
            if approval_action is None:
                raise ValueError("Thresholded policies require a declared approval action.")
            approval.append(
                f'@id("studio_{definition.id}_threshold_approval")\npermit (principal == {_principal(definition)}, action == {_action(approval_action)}, resource) when {{ {condition} && {amount} > {definition.allow_threshold} && {amount} <= {definition.approval_threshold} }};'
            )
            # No forbid is emitted above the approval threshold. Cedar is
            # default-deny, so the absence of a permit in both the execute
            # and the approval set already denies it; an unconditional
            # forbid here would also fire inside the approval band itself
            # (allow_threshold < amount <= approval_threshold), which is
            # exactly the bug this comment replaces. An explicit forbid must
            # always mean DENY, never something a human can be asked about.
    return "\n\n".join(execute), "\n\n".join(approval)


class PolicyStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._policies: dict[str, PolicyDefinition] = {}
        if self.path.exists():
            try:
                records = json.loads(self.path.read_text(encoding="utf-8"))
                for record in records:
                    definition = PolicyDefinition.from_payload(record, active=bool(record.get("active", False)))
                    self._policies[definition.id] = definition
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                self._policies = {}

    def list(self) -> list[PolicyDefinition]:
        return list(self._policies.values())

    def get(self, policy_id: str) -> PolicyDefinition | None:
        return self._policies.get(policy_id)

    def save(self, definition: PolicyDefinition) -> PolicyDefinition:
        validate_definition(definition)
        self._policies[definition.id] = definition
        self._flush()
        return definition

    def activate(self, policy_id: str) -> PolicyDefinition | None:
        definition = self._policies.get(policy_id)
        if definition is None:
            return None
        activated = PolicyDefinition(**{**asdict(definition), "active": True})
        self._policies[policy_id] = activated
        self._flush()
        return activated

    def delete(self, policy_id: str) -> bool:
        removed = self._policies.pop(policy_id, None) is not None
        if removed:
            self._flush()
        return removed

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="policies-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump([asdict(item) for item in self._policies.values()], handle, indent=2)
                handle.write("\n")
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
