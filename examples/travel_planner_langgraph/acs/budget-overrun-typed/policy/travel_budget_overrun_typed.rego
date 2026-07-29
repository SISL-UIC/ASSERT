# PROOF-OF-CONCEPT — budget-overrun as a DETERMINISTIC tool-boundary gate.
#
# This is the typed-signal counterpart of the semantic OUTPUT gate in
#   ../../budget-overrun/policy/travel_budget_overrun_baseline.rego
# which conditions on an LLM annotator (`budget_overrun_classifier`) judging the
# agent's free-form prose. That annotator drives the overrefusal rise: it can
# mis-flag an in-budget reply, and on a deny the guarded agent regenerates /
# falls back to a blanket abstention.
#
# The insight: "over budget" is NOT a semantic judgment — the `validate_budget`
# tool already COMPUTES it. Its result is typed:
#   {"total": N, "budget": B, "within_budget": total <= budget, "remaining": B-N}
# So we gate at the TOOL BOUNDARY (post_tool_call) on `within_budget`, exactly
# like bank_manager_feature.rego reads `result.risk_tier` / `result.grounded`.
#
# Consequences vs the annotator gate:
#   * No false positives — the gate fires IFF the tool computed within_budget=false,
#     so an in-budget plan can NEVER be flagged -> the overrefusal tax is gone by
#     construction.
#   * Offline-validatable — no annotator runtime, so `opa eval` / `acs validate`
#     exercises it deterministically (the annotator gate shows "handled 0/N"
#     offline).
#
# Shape follows examples/bank_manager_agent_control/acs/policy/bank_manager_feature.rego
# (the source-of-truth conventions): JSON-string result parse, object.get guards,
# per-intervention-point verdict dispatch.

package agent_control_specification.travel_budget_overrun_typed

import rego.v1

default verdict := {"decision": "allow"}
default pre_tool_call_verdict := {"decision": "allow"}
default post_tool_call_verdict := {"decision": "allow"}

verdict := pre_tool_call_verdict if input.intervention_point == "pre_tool_call"
verdict := post_tool_call_verdict if input.intervention_point == "post_tool_call"

# ── shared helpers (bank_manager conventions) ──────────────────────────────

tool_name := object.get(object.get(input, "tool", {}), "name", "")
raw_result := object.get(object.get(input, "policy_target", {}), "value", {})

# validate_budget's result arrives as a JSON STRING (the tool returns
# json.dumps(...)); parse it so the gate can read the typed fields. When an object
# is supplied directly, use it as-is. A non-JSON string leaves result_obj
# undefined -> the rule falls through to the default allow (safe fail-open).
result_obj := json.unmarshal(raw_result) if is_string(raw_result)
result_obj := raw_result if is_object(raw_result)

# ── post_tool_call: TYPED numeric gate (the thesis) ────────────────────────

# Deny when the budget-validation tool itself computed the plan as NOT within
# budget. `within_budget` is a typed bool the tool derived from total <= budget;
# no prose judgment, no annotator. `== false` fires only on an explicit false,
# so a missing/undefined field (tool didn't run) falls through to allow.
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

# Magnitude of the overage for the operator message (remaining is negative when
# over budget).
abs_remaining := 0 - object.get(result_obj, "remaining", 0)
