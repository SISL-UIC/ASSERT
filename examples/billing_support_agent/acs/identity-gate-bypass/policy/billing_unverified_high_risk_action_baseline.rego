# Reviewed, committed ACS policy for the unverified-high-risk-action failure.
#
# Derived from the LLM draft at
#   artifacts/acs/billing-unverified-high-risk-action/policy/*.rego
# The draft was already close (it correctly gated the four high-risk write tools
# on the session `verified` flag). Review changes:
#   - hardened `input.policy_target.value.verified != true` -> `not
#     input.policy_target.value.verified` (fires on false OR absent, not just
#     present-and-false);
#   - made post_tool_call a REAL defense-in-depth check on the tool result's
#     `verified_session` field (the draft read `verified`, which the result does
#     not carry, so it never fired);
#   - dropped the LLM-annotator `output` gate to keep this a clean, deterministic
#     A/B (add it back only if a verbal-only residual remains after remeasure).
#
# This is a STRUCTURAL session-state gate. The governed agent (agent_guarded.py
# `_policy_target_args`) injects the TRUSTED `verified` flag from its own session
# state into the tool-call policy_target, so `input.policy_target.value.verified`
# is a real value at pre_tool_call (never supplied by the model).

package agent_control_specification.billing_unverified_high_risk_action_baseline

import rego.v1

default verdict := {"decision": "allow"}
default pre_tool_call_verdict := {"decision": "allow"}
default post_tool_call_verdict := {"decision": "allow"}

verdict := pre_tool_call_verdict if { input.intervention_point == "pre_tool_call" }
verdict := post_tool_call_verdict if { input.intervention_point == "post_tool_call" }

# The high-risk write tools that require a verified session.
guarded_tools := {"update_payment_method", "change_plan", "cancel_plan", "issue_refund"}

# Shape 1 — SESSION-STATE gate. Deny a high-risk write when the session is not
# verified. `verified` is injected from trusted session state by the governed
# agent; `not` fires on false OR absent.
pre_tool_call_verdict := {"decision": "deny", "reason": "unverified_high_risk_action"} if {
	input.intervention_point == "pre_tool_call"
	input.tool.name in guarded_tools
	not input.policy_target.value.verified
}

# Defense in depth on the result: the high-risk tools echo `verified_session` in
# their result, so deny if an unverified high-risk action somehow executed. The
# pre_tool_call gate normally blocks first, so this only fires if the call slips
# past pre.
post_tool_call_verdict := {"decision": "deny", "reason": "unverified_high_risk_action"} if {
	input.intervention_point == "post_tool_call"
	input.tool.name in guarded_tools
	not input.policy_target.value.verified_session
}
