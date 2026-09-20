"""Argument validation that runs before Cedar sees a request.

Cedar's schema would reject a malformed context, but relying on that would
turn a caller mistake into an engine error. Validating here keeps the failure
mode precise: bad input is INVALID_ARGUMENTS, never POLICY_ENGINE_ERROR.
"""

from dataclasses import dataclass
from typing import Mapping

TEXT = "text"
MONEY = "money"
OPTIONAL_TEXT = "optional_text"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """The exact Cedar action names a tool may reach, plus its typed input."""

    execute_action: str
    fields: Mapping[str, str]
    approval_action: str | None = None


TOOL_SPECS: Mapping[str, ToolSpec] = {
    "lookup_order": ToolSpec("lookup_order", {"order_id": TEXT}),
    "lookup_customer": ToolSpec("lookup_customer", {"customer_id": TEXT}),
    "refund_order": ToolSpec(
        "refund_order",
        {"order_id": TEXT, "amount": MONEY},
        approval_action="request_refund_approval",
    ),
    "send_email": ToolSpec("send_email", {"customer_id": TEXT, "subject": TEXT, "body": TEXT}),
    "export_customers": ToolSpec("export_customers", {}),
}

# Generic authorization actions are evaluated by the same Cedar engine but do
# not expose business-tool capabilities or a route to the demo store.
GENERIC_ACTION_SPECS: Mapping[str, ToolSpec] = {
    "read_logs": ToolSpec("read_logs", {"environment": OPTIONAL_TEXT}),
    "deploy_production": ToolSpec(
        "deploy_production", {"environment": OPTIONAL_TEXT}, approval_action="request_deploy_approval"
    ),
    "delete_production_database": ToolSpec("delete_production_database", {"environment": OPTIONAL_TEXT}),
    "refund_order": ToolSpec(
        "refund_order", {"order_id": TEXT, "amount": MONEY}, approval_action="request_refund_approval"
    ),
}


class InvalidArguments(ValueError):
    """Raised only inside this package; the engine converts it to a DENY."""


def normalize(spec: ToolSpec, arguments: Mapping[str, object]) -> dict[str, object]:
    """Return exactly the declared fields, correctly typed, or raise.

    Unknown keys are rejected rather than dropped: a caller passing an
    unexpected field is a caller whose intent we cannot authorize.
    """
    if not isinstance(arguments, Mapping):
        raise InvalidArguments("Arguments must be a mapping.")

    supplied = set(arguments)
    declared = set(spec.fields)
    if supplied - declared:
        raise InvalidArguments(f"Unexpected arguments: {sorted(supplied - declared)}.")
    required = {field for field, kind in spec.fields.items() if kind != OPTIONAL_TEXT}
    if required - supplied:
        raise InvalidArguments(f"Missing arguments: {sorted(required - supplied)}.")

    normalized: dict[str, object] = {}
    for field, kind in spec.fields.items():
        if kind == OPTIONAL_TEXT and field not in supplied:
            continue
        value = arguments[field]
        if kind == TEXT:
            if not isinstance(value, str) or not value.strip():
                raise InvalidArguments(f"{field} must be a nonempty string.")
            normalized[field] = value
        elif kind == OPTIONAL_TEXT:
            if field in supplied and (not isinstance(value, str) or not value.strip()):
                raise InvalidArguments(f"{field} must be a nonempty string when supplied.")
            if field in supplied:
                normalized[field] = value
        else:
            # bool is a subclass of int; `True` must never be spendable as ₹1.
            if type(value) is not int:
                raise InvalidArguments(f"{field} must be a whole-rupee integer.")
            if value < 0:
                raise InvalidArguments(f"{field} must not be negative.")
            normalized[field] = value
    return normalized
