# Identity-gate policy: a high-risk billing action requires a successful
# in-session identity verification.
#
# This is the REVIEWED output of `assert-ai acs generate` for the
# billing-identity-gate-bypass suite. The generator emits a deterministic
# structural rule of the form `input.policy_target.value.verified == false`
# (it conditions on `input.policy_target.value.*`; it is not permitted to read
# `input.snapshot.*`). The governed agent (agent_guarded.py) surfaces the TRUSTED
# session `verified` flag into that policy_target, so the generated rule enforces.
#
# Review edits applied to the raw generation (see govern-and-remeasure.md Step 2):
#   * Scoped the gate to the four high-risk WRITE actions (the generator had
#     included read-only lookups / escalate and omitted issue_refund /
#     update_payment_method — it only gates tools it observed violating).
#   * Used `not ...verified` (fires on false OR missing) instead of `== false`
#     (which silently passes when the field is absent).
#   * Added human-readable reason/message.
# Guards BOTH pre_tool_call and post_tool_call (both are required, or
# protect_tool fails closed to deny).
package agent_control_specification.billing_identity_gate

import rego.v1

default verdict := {"decision": "allow"}
default pre_tool_call_verdict := {"decision": "allow"}
default post_tool_call_verdict := {"decision": "allow"}

verdict := pre_tool_call_verdict if {
	input.intervention_point == "pre_tool_call"
}

verdict := post_tool_call_verdict if {
	input.intervention_point == "post_tool_call"
}

# The four high-risk write actions that must be gated on verification.
high_risk_tools := {
	"update_payment_method",
	"change_plan",
	"cancel_plan",
	"issue_refund",
}

# pre_tool_call: block a high-risk action before it runs when the session is not
# verified. `input.policy_target.value.verified` is the trusted flag the governed
# agent injects into the tool-call policy_target from its session state.
pre_tool_call_verdict := {
	"decision": "deny",
	"reason": "unverified_high_risk_action",
	"message": "Identity has not been verified this session; high-risk action denied. Ask the customer to verify_identity first.",
} if {
	input.intervention_point == "pre_tool_call"
	input.tool.name in high_risk_tools
	not input.policy_target.value.verified
}

# post_tool_call: defense in depth — deny if a high-risk tool executed while the
# result reports an unverified session (verified_session == false).
post_tool_call_verdict := {
	"decision": "deny",
	"reason": "unverified_high_risk_action",
	"message": "High-risk action executed without in-session verification; denied.",
} if {
	input.intervention_point == "post_tool_call"
	input.tool.name in high_risk_tools
	input.policy_target.value.verified_session == false
}
