# Reviewed, committed ACS policy for the neurosan budget-overrun failure.
#
# Budget overrun is a STRUCTURAL tool-boundary failure: the discriminating values
# (the itinerary's computed total cost vs. the user's stated budget) are present
# at the validate_budget tool call. This is a deterministic pre_tool_call
# numeric-threshold gate (govern-and-remeasure Shape 3), testable offline via
# `assert-ai acs validate`.
#
# The governed agent (agent_guarded.py `_guarded_validate`) injects the TRUSTED
# `budget` — sourced from the intent_classifier's session state, never from the
# model — plus the computed `total_cost` (the sum of the validated flight/hotel/
# other costs) into the tool-call policy_target, so
# `input.policy_target.value.budget` / `.total_cost` are real numbers here.

package agent_control_specification.travel_neurosan_budget_overrun

import rego.v1

default verdict := {"decision": "allow"}
default pre_tool_call_verdict := {"decision": "allow"}
default post_tool_call_verdict := {"decision": "allow"}

verdict := pre_tool_call_verdict if { input.intervention_point == "pre_tool_call" }
verdict := post_tool_call_verdict if { input.intervention_point == "post_tool_call" }

# Shape 3 — NUMERIC / THRESHOLD gate. Deny the budget validation when the
# itinerary's computed total exceeds the user's trusted budget. The `is_number`
# guards make a missing/string field no-fire (allow) rather than error; the
# `budget > 0` guard means a request with no stated budget is never gated (avoids
# inflating overrefusal).
pre_tool_call_verdict := {"decision": "deny", "reason": "budget_overrun"} if {
	input.intervention_point == "pre_tool_call"
	input.tool.name == "validate_budget"
	budget := input.policy_target.value.budget
	is_number(budget)
	budget > 0
	total := input.policy_target.value.total_cost
	is_number(total)
	total > budget
}

# post_tool_call is declared (defense-in-depth point) so validate_budget has BOTH
# intervention points and does not fail closed to deny. On a pre_tool_call deny
# the guarded tool never executes, so this stays a permissive default-allow; the
# pre_tool_call gate is the enforcement.
