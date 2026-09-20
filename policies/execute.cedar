// Execution authority. Evaluated first for every proposed action.
//
// Cedar is default-deny: an action with no matching permit is denied without
// any policy being listed here. Permits are narrow on purpose so a future tool
// cannot inherit authority by accident.
//
// Every principal below is a role, not a person. A principal that appears in
// no policy at all has no authority anywhere in AgentGate, which is why an
// unknown agent is denied without anything being written down about it.

// ---------------------------------------------------------------------------
// support-agent — the customer-support role the demo runs as.
// ---------------------------------------------------------------------------

@id("allow_reads")
permit (
  principal == AgentGate::Agent::"support-agent",
  action in [
    AgentGate::Action::"lookup_order",
    AgentGate::Action::"lookup_customer"
  ],
  resource
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
  resource
)
when {
  (resource == AgentGate::Store::"demo" || resource is AgentGate::Order) &&
  context.input.amount >= 0 &&
  context.input.amount <= 2000
};

// Refunds above the agent limit are denied here by the absence of a permit,
// which is what leaves room for the approval check to run.

// ---------------------------------------------------------------------------
// finance-agent — a higher spending authority over the same action.
// ---------------------------------------------------------------------------

@id("allow_finance_refund_within_limit")
permit (
  principal == AgentGate::Agent::"finance-agent",
  action == AgentGate::Action::"refund_order",
  resource
)
when {
  (resource == AgentGate::Store::"demo" || resource is AgentGate::Order) &&
  context.input.amount >= 0 &&
  context.input.amount <= 10000
};

// ---------------------------------------------------------------------------
// intern-agent — a known role with no refund authority of any kind.
//
// This is an explicit forbid rather than a missing permit so the audit trail
// names the intent, and so the refund can never become a question a human is
// asked to say yes to.
// ---------------------------------------------------------------------------

@id("forbid_intern_refunds")
forbid (
  principal == AgentGate::Agent::"intern-agent",
  action == AgentGate::Action::"refund_order",
  resource
);

// ---------------------------------------------------------------------------
// deployment-agent — the same three-way shape on operational actions, to show
// the gate is not a refund calculator.
// ---------------------------------------------------------------------------

@id("allow_deployment_read_logs")
permit (
  principal == AgentGate::Agent::"deployment-agent",
  action == AgentGate::Action::"read_logs",
  resource
);

// `deploy_production` has no execute permit anywhere. That absence is what
// sends it to the approval check in request_approval.cedar.

// ---------------------------------------------------------------------------
// Forbidden outright, for every principal.
// ---------------------------------------------------------------------------

// Bulk customer export is forbidden outright so the decision diagnostics name
// the security intent instead of reporting a missing permit.
@id("forbid_customer_export")
forbid (
  principal,
  action == AgentGate::Action::"export_customers",
  resource
);

// Dropping a production database is the one operational action with no route
// to yes: no permit, no approval path, and an explicit forbid so nobody can
// add one by accident.
@id("forbid_production_database_deletion")
forbid (
  principal,
  action == AgentGate::Action::"delete_production_database",
  resource
);
