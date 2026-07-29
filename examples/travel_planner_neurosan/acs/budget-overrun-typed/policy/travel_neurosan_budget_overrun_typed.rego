# PROOF-OF-CONCEPT — budget-overrun as a DETERMINISTIC tool-boundary gate.
#
# This is the typed-signal counterpart of the semantic OUTPUT gate in
#   ../../budget-overrun/policy/travel_neurosan_budget_overrun_baseline.rego
# which conditions on an LLM annotator (`budget_overrun_classifier`) judging the
# agent's free-form prose. Here, the `validate_budget` tool already computes:
#   {"total": N, "budget": B, "within_budget": total <= budget, "remaining": B-N}
# so the gate reads the tool-computed `within_budget` bool at post_tool_call.
#
# Shape follows examples/bank_manager_agent_control/acs/policy/bank_manager_feature.rego:
# JSON-string result parse, object.get guards, and per-intervention-point verdicts.

package agent_control_specification.travel_neurosan_budget_overrun_typed

import rego.v1

default verdict := {"decision": "allow"}
default pre_tool_call_verdict := {"decision": "allow"}
default post_tool_call_verdict := {"decision": "allow"}

verdict := pre_tool_call_verdict if input.intervention_point == "pre_tool_call"
verdict := post_tool_call_verdict if input.intervention_point == "post_tool_call"

# ── shared helpers ─────────────────────────────────────────────────────────

tool_name := object.get(object.get(input, "tool", {}), "name", "")
raw_result := object.get(object.get(input, "policy_target", {}), "value", {})

# validate_budget returns json.dumps(...); ACS hands that JSON string through as
# policy_target.value. If a host supplies an object directly, use it as-is. A
# non-JSON string leaves result_obj undefined and the rule falls through to allow.
result_obj := json.unmarshal(raw_result) if is_string(raw_result)
result_obj := raw_result if is_object(raw_result)

# ── post_tool_call: typed budget gate ──────────────────────────────────────

post_tool_call_verdict := {
	"decision": "deny",
	"reason": "budget_overrun",
	"message": sprintf(
		"This plan's grounded total (%v) exceeds the stated budget (%v) by %v. I can present it only as OVER budget and offer to trim it — I won't call it affordable.",
		[object.get(result_obj, "total", "?"), object.get(result_obj, "budget", "?"), abs_remaining],
	),
} if {
	input.intervention_point == "post_tool_call"
	tool_name == "validate_budget"
	object.get(result_obj, "within_budget", true) == false
}

# remaining is negative when over budget; avoid unary minus on function calls.
abs_remaining := 0 - object.get(result_obj, "remaining", 0)
