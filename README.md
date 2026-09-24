# AgentGate

> **Reasoning can be probabilistic. Authority should be deterministic.**

AgentGate is a deterministic authorization layer for AI agents and applications.

AI systems can increasingly issue refunds, deploy software, send messages, modify databases, and call APIs that affect real business systems.

AgentGate places a policy boundary between a proposed action and execution.

The caller proposes:

- **who** is acting,
- **what** action they want to perform,
- **which resource** they want to affect,
- and the **context** surrounding the request.

AgentGate evaluates that request using **Cedar** and returns one of three outcomes:

```text
ALLOW
REQUIRE_APPROVAL
DENY
