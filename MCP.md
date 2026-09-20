# AgentGate MCP Adapter

The adapter is isolated from the FastAPI process and uses the same Cedar-backed evaluator as `POST /api/gate/evaluate`.

## Launch locally

From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = (Resolve-Path backend).Path
Get-Content .\mcp-request.json | .\backend\.venv\Scripts\python.exe -m app.mcp_server
```

The adapter speaks line-delimited JSON-RPC over stdin/stdout. It exposes one MCP tool, `evaluate_action`, with `principal`, `action`, `resource`, and `context` arguments.

A minimal request sequence is:

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"evaluate_action","arguments":{"principal":{"type":"Agent","id":"deployment-agent"},"action":"deploy_production","resource":{"type":"Environment","id":"production"},"context":{}}}}
```

The final result contains `decision`, `reason`, and `matched_policy`. Use the same request body against `/api/gate/evaluate` to compare the complete HTTP response. The adapter has no separate policy files, thresholds, or business execution path; if it cannot start, the core HTTP app is unaffected.
