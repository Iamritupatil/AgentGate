// Execution authority. Evaluated first for every proposed tool call.
//
// Cedar is default-deny: an action with no matching permit is denied without
// any policy being listed here. Permits are narrow on purpose so a future tool
// cannot inherit authority by accident.

@id("allow_reads")
permit (
  principal == AgentGate::Agent::"support-agent",
  action in [
    AgentGate::Action::"lookup_order",
    AgentGate::Action::"lookup_customer"
  ],
  resource == AgentGate::Store::"demo"
);

// `send_email` is authorized only while it stays a locally recorded demo
// action that sends nothing over a network. Wiring a real mail provider
// invalidates this permit and requires a new explicit policy decision.
@id("allow_recorded_email")
permit (
  principal == AgentGate::Agent::"support-agent",
  action == AgentGate::Action::"send_email",
  resource == AgentGate::Store::"demo"
);

@id("allow_refund_within_agent_limit")
permit (
  principal == AgentGate::Agent::"support-agent",
  action == AgentGate::Action::"refund_order",
  resource == AgentGate::Store::"demo"
)
when {
  context.input.amount >= 0 &&
  context.input.amount <= 2000
};

// Refunds above the agent limit are denied here by the absence of a permit,
// which is what leaves room for the approval check to run.

// Bulk customer export is forbidden outright so the decision diagnostics name
// the security intent instead of reporting a missing permit.
@id("forbid_customer_export")
forbid (
  principal,
  action == AgentGate::Action::"export_customers",
  resource
);
