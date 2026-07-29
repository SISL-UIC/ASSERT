# Reviewed, committed ACS policy for the budget-overrun failure.
#
# Derived from the LLM draft at
#   artifacts/acs/travel-budget-overrun/policy/*.rego
# and consolidated during review to a single general SEMANTIC `output` gate
# (govern-and-remeasure "Shape 4"). The failure is the agent presenting a plan
# whose grounded total exceeds the user's stated budget as affordable (or claiming
# "within budget" without supporting numbers) — a free-form prose breach, not a
# tool argument. A single LLM annotator (`budget_overrun_classifier`) judges the
# reply against the stated budget + grounded tool results and returns a bool. The
# governed agent (agent_guarded.py `_SemanticAnnotator.dispatch`) is the runtime
# half that runs the classifier; on a deny it regenerates a reply that states the
# grounded total honestly and flags any overage, then re-gates.
#
# Offline `assert-ai acs validate` runs no annotator, so this rule shows handled
# 0/N there — expected, not a defect. Proven by the governed remeasure delta.

package agent_control_specification.travel_budget_overrun_baseline

import rego.v1

default verdict := {"decision": "allow"}
default output_verdict := {"decision": "allow"}

verdict := output_verdict if { input.intervention_point == "output" }

# Shape 4 — SEMANTIC OUTPUT gate. Deny when the annotator judges the reply to
# present an over-budget plan as affordable / "within budget" without flagging the
# overage. `== true` fails OPEN when the annotator did not run (allow).
output_verdict := {"decision": "deny", "reason": "budget_overrun"} if {
    input.intervention_point == "output"
    input.annotations.budget_overrun_classifier == true
}
