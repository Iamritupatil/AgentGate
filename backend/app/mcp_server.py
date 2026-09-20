"""Minimal stdio MCP adapter for AgentGate authorization.

This adapter owns no policy logic. It constructs the normal application once
and calls the same PolicyEngine used by POST /api/gate/evaluate, through the
same request-shaping module, so a request answered here and the identical
request answered over HTTP are guaranteed to agree.
"""

import json
import sys
from typing import Any

from app.config import Settings
from app.main import create_app
from app.policy.generic import describe, evaluate_generic


TOOL = {
    "name": "evaluate_action",
    "description": "Evaluate an action with AgentGate Cedar policies.",
    "inputSchema": {
        "type": "object",
        "required": ["principal", "action", "resource", "context"],
        "properties": {
            "principal": {"type": "object"},
            "action": {"type": "string"},
            "resource": {"type": "object"},
            "context": {"type": "object"},
        },
    },
}


def evaluate(arguments: dict[str, Any], engine: Any) -> dict[str, Any]:
    principal = arguments["principal"]
    resource = arguments["resource"]
    result = evaluate_generic(
        engine,
        principal["id"],
        arguments["action"],
        resource["type"],
        resource["id"],
        arguments.get("context", {}),
        principal_type=principal.get("type", "Agent"),
    )
    outcome = describe(result)
    # Field name kept as `reason` for backward compatibility with existing
    # MCP callers; it carries the stable reason code, not the prose text.
    return {
        "decision": outcome["decision"],
        "reason": outcome["reason_code"],
        "matched_policy": outcome["matched_policy"],
    }


def handle_message(message: dict[str, Any], engine: Any) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": request_id,
            "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "agentgate", "version": "0.1.0"},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": [TOOL]}}
    if method == "tools/call":
        try:
            result = evaluate(message.get("params", {}).get("arguments", {}), engine)
            return {"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": json.dumps(result)}], "structuredContent": result}}
        except Exception as error:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": str(error)}}
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}


def main() -> None:
    application = create_app(Settings())
    for line in sys.stdin:
        if not line.strip():
            continue
        response = handle_message(json.loads(line), application.state.policy_engine)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
