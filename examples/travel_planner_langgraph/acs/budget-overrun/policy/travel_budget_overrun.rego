# Reviewed, committed ACS policy for the budget-overrun failure.
#
# Derived from the LLM draft at
#   artifacts/acs/travel-budget-overrun/policy/*.rego
# The draft fell back to a SEMANTIC output-annotator gate because `acs generate`
# was given no tool inventory ("No tools emitted" in report.md). Budget overrun
# is actually a STRUCTURAL tool-boundary failure — the discriminating value
# (requested price cap vs. the user's budget) is present at the search tool call
# — so this reviewed policy replaces the annotator gate with a deterministic
# `pre_tool_call` numeric-threshold gate (govern-and-remeasure Shape 3), which is
# also testable offline via `assert-ai acs validate`.
#
# The governed agent (agent_guarded.py `_policy_target_args`) injects the TRUSTED
# `budget_cap` — sourced from the graph's own session state, never from the
# model's tool arguments — plus the EFFECTIVE requested amount (defaulting to the
# tool's own default when the model omitted it) into the tool-call policy_target,
# so `input.policy_target.value.budget_cap` / `.max_price` / `.max_nightly_rate`
# are real values at pre_tool_call.

package agent_control_specification.travel_budget_overrun

import rego.v1

default verdict := {"decision": "allow"}
default pre_tool_call_verdict := {"decision": "allow"}
default post_tool_call_verdict := {"decision": "allow"}

verdict := pre_tool_call_verdict if { input.intervention_point == "pre_tool_call" }
verdict := post_tool_call_verdict if { input.intervention_point == "post_tool_call" }

# Shape 3 — NUMERIC / THRESHOLD gate. Deny a flight search whose requested
# max_price exceeds the user's trusted budget cap. `is_number` guards are
# required so a missing/string field makes the rule no-fire (allow) rather than
# error; the `cap > 0` guard means a request with no stated budget is never
# gated (avoids inflating overrefusal).
pre_tool_call_verdict := {"decision": "deny", "reason": "budget_overrun"} if {
	input.intervention_point == "pre_tool_call"
	input.tool.name == "search_flights"
	cap := input.policy_target.value.budget_cap
	is_number(cap)
	cap > 0
	amount := input.policy_target.value.max_price
	is_number(amount)
	amount > cap
}

# Deny a hotel search whose requested max_nightly_rate exceeds the user's trusted
# budget cap (a per-night rate above the entire trip budget is definitionally
# unaffordable).
pre_tool_call_verdict := {"decision": "deny", "reason": "budget_overrun"} if {
	input.intervention_point == "pre_tool_call"
	input.tool.name == "search_hotels"
	cap := input.policy_target.value.budget_cap
	is_number(cap)
	cap > 0
	amount := input.policy_target.value.max_nightly_rate
	is_number(amount)
	amount > cap
}

# post_tool_call is declared (defense-in-depth point) so the guarded tools have
# BOTH intervention points and do not fail closed to deny. The search tools'
# results carry no structural budget field to re-check, so this stays a
# permissive default-allow; the pre_tool_call gate is the enforcement.
