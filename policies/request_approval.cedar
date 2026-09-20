// Escalation authority. Evaluated only after execution was denied, and only
// for actions that have a defined human-approval path.
//
// An Allow here means "a human may be asked", never "this may execute".
// Anything outside this band stays a flat DENY: there is no approval path for
// a refund above the hard ceiling.

@id("allow_refund_approval_request")
permit (
  principal == AgentGate::Agent::"support-agent",
  action == AgentGate::Action::"request_refund_approval",
  resource == AgentGate::Store::"demo"
)
when {
  context.input.amount > 2000 &&
  context.input.amount <= 10000
};
