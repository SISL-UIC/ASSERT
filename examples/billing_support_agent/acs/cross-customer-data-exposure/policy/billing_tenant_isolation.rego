# Deterministic tenant-isolation policy: an account-scoped tool may only touch the
# authenticated caller's account. Denies any call whose account_id differs from
# input.snapshot.caller_account_id. Conditions only on structural fields present in
# the real OPA input, so it validates offline and enforces without an LLM call.
package agent_control_specification.billing_tenant_isolation

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

# Every tool that accepts an account_id and could reach another tenant's data.
account_scoped_tools := {
	"get_account_profile",
	"get_invoices",
	"update_payment_method",
	"change_plan",
	"cancel_plan",
	"issue_refund",
}

# pre_tool_call: block a call that targets an account_id other than the caller's.
pre_tool_call_verdict := {
	"decision": "deny",
	"reason": "cross_account_access",
	"message": "Cross-account access denied: the requested account_id is not the authenticated caller's.",
} if {
	input.intervention_point == "pre_tool_call"
	input.tool.name in account_scoped_tools
	requested := input.policy_target.value.account_id
	requested != ""
	requested != input.snapshot.caller_account_id
}

# post_tool_call: defense in depth — deny if a tool returned another account's data.
post_tool_call_verdict := {
	"decision": "deny",
	"reason": "cross_account_access",
	"message": "Cross-account data returned; denied.",
} if {
	input.intervention_point == "post_tool_call"
	input.tool.name in account_scoped_tools
	returned := input.policy_target.value.account_id
	returned != ""
	returned != input.snapshot.caller_account_id
}
