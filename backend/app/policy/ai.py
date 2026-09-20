"""Natural-language policy drafting with an optional OpenAI-compatible provider."""

import json
import re
from dataclasses import asdict
from urllib.request import Request, urlopen

from app.policy.studio import PolicyDefinition


class DraftError(ValueError):
    pass


def _local_draft(description: str) -> PolicyDefinition:
    text = description.lower()
    principal_id = "support-agent" if "support" in text else "deployment-agent" if "deploy" in text or "production" in text else "finance-agent" if "finance" in text else ""
    if not principal_id:
        raise DraftError("Describe a support, finance, or deployment agent.")
    if "delete" in text and "database" in text:
        return PolicyDefinition(
            id="draft", name="Generated destructive production policy", principal_type="Agent",
            principal_id=principal_id, action="delete_production_database", resource_type="Database",
            decision="DENY",
        )
    if "read" in text and "log" in text:
        return PolicyDefinition(
            id="draft", name="Generated production log policy", principal_type="Agent",
            principal_id=principal_id, action="read_logs", resource_type="Environment", decision="ALLOW",
        )
    if "deploy" in text:
        return PolicyDefinition(
            id="draft", name="Generated production deployment policy", principal_type="Agent",
            principal_id=principal_id, action="deploy_production", resource_type="Environment",
            decision="REQUIRE_APPROVAL",
        )
    if "refund" in text:
        amounts = [int(value.replace(",", "")) for value in re.findall(r"(?:₹|rs\.?\s*|\$)?\s*(\d[\d,]*)", text)]
        if len(amounts) < 2:
            raise DraftError("Include an automatic refund limit and an approval ceiling.")
        return PolicyDefinition(
            id="draft", name="Generated refund policy", principal_type="Agent",
            principal_id=principal_id, action="refund_order", resource_type="Order", decision="ALLOW",
            context_field="amount", allow_threshold=amounts[0], approval_threshold=amounts[-1],
        )
    raise DraftError("The description did not identify a supported AgentGate action.")


def _provider_draft(description: str, api_key: str, base_url: str, model: str) -> PolicyDefinition:
    body = json.dumps({
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "Return only JSON with name, principal_type, principal_id, action, resource_type, decision, context_field, allow_threshold, approval_threshold. Never activate a policy."},
            {"role": "user", "content": description},
        ],
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    request = Request(
        base_url.rstrip("/") + "/chat/completions", data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST",
    )
    with urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))
    content = payload["choices"][0]["message"]["content"]
    return PolicyDefinition.from_payload(json.loads(content))


def draft_policy(description: str, *, api_key: str | None = None, base_url: str = "https://api.openai.com/v1", model: str = "gpt-4o-mini") -> PolicyDefinition:
    if not description.strip():
        raise DraftError("Describe the policy first.")
    if api_key:
        try:
            return _provider_draft(description, api_key, base_url, model)
        except Exception:
            pass
    return _local_draft(description)


def draft_payload(definition: PolicyDefinition) -> dict[str, object]:
    return asdict(definition)
