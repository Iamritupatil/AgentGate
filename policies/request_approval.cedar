// Escalation authority. Evaluated only after execution was denied, and only
// for actions that have a defined human-approval path.
//
// An Allow here means "a human may be asked", never "this may execute".
// Anything outside these bands stays a flat DENY: there is no approval path
// for a refund above a role's hard ceiling.

@id("allow_refund_approval_request")
permit (
  principal == AgentGate::Agent::"support-agent",
  action == AgentGate::Action::"request_refund_approval",
  resource
)
when {
  (resource == AgentGate::Store::"demo" || resource is AgentGate::Order) &&
  context.input.amount > 2000 &&
  context.input.amount <= 10000
};

@id("allow_finance_refund_approval_request")
permit (
  principal == AgentGate::Agent::"finance-agent",
  action == AgentGate::Action::"request_refund_approval",
  resource
)
when {
  (resource == AgentGate::Store::"demo" || resource is AgentGate::Order) &&
  context.input.amount > 10000 &&
  context.input.amount <= 50000
};

// A production deploy is never autonomous and never forbidden: it is always a
// question for a human.
@id("allow_deploy_approval_request")
permit (
  principal == AgentGate::Agent::"deployment-agent",
  action == AgentGate::Action::"request_deploy_approval",
  resource
);
