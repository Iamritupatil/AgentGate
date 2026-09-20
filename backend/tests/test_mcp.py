import json
import subprocess
import sys
from pathlib import Path


def test_mcp_tool_returns_same_decision_as_http(client):
    request = {
        "principal": {"type": "Agent", "id": "deployment-agent"},
        "action": "deploy_production",
        "resource": {"type": "Environment", "id": "production"},
        "context": {},
    }
    http_result = client.post("/api/gate/evaluate", json=request).json()
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "evaluate_action", "arguments": request}},
    ]
    environment = {
    "PYTHONPATH": str(Path(__file__).parents[1]),
    "AGENTGATE_POLICY_STORE_PATH": str(
        client.app.state.settings.policy_store_path
    ),
}
    process = subprocess.run(
        [sys.executable, "-m", "app.mcp_server"],
        input="\n".join(json.dumps(message) for message in messages) + "\n",
        text=True,
        capture_output=True,
        env={**__import__("os").environ, **environment},
        check=True,
    )
    response = json.loads(process.stdout.splitlines()[-1])
    assert response["result"]["structuredContent"]["decision"] == http_result["decision"]
    assert response["result"]["structuredContent"]["matched_policy"] == http_result["matched_policy"]
