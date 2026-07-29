# Reviewed, committed ACS policy for the fabricated-details failure.
#
# Derived from the LLM draft at
#   artifacts/acs/travel-neurosan-fabricated-details/policy/*.rego
# but consolidated during review to a single general SEMANTIC `output` gate
# (govern-and-remeasure "Shape 4"). The real failure is a FAITHFULNESS breach in
# the agent's free-form REPLY (a flight/hotel/price/total the tool results do not
# support — including presenting the fixed Tokyo/Japan mock data as another city's
# specifics), so a single LLM annotator (`fabrication_classifier`) judges the reply
# against the conversation + tool results and returns a bool. The governed agent
# (agent_guarded.py `_SemanticAnnotator.dispatch`) is the runtime half that runs the
# classifier; on a deny it regenerates a grounded reply and re-gates.
#
# Offline `assert-ai acs validate` runs no annotator, so this rule shows handled
# 0/N there — that is expected, not a defect. It is proven by the governed
# remeasure delta.

package agent_control_specification.travel_neurosan_fabricated_details_baseline

import rego.v1

default verdict := {"decision": "allow"}
default output_verdict := {"decision": "allow"}

verdict := output_verdict if { input.intervention_point == "output" }

# Shape 4 — SEMANTIC OUTPUT gate. Deny when the annotator judges the assistant's
# reply to assert concrete trip details not grounded in the tool results. `== true`
# fails OPEN when the annotator did not run (allow), the right default for a
# semantic gate.
output_verdict := {"decision": "deny", "reason": "fabricated_details"} if {
    input.intervention_point == "output"
    input.annotations.fabrication_classifier == true
}
