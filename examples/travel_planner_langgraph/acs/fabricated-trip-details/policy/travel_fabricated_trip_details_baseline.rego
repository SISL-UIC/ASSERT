# Reviewed, committed ACS policy for the fabricated-trip-details failure.
#
# Derived from the LLM draft at
#   artifacts/acs/travel-fabricated-trip-details/policy/*.rego
# but consolidated during review: the draft emitted an over-broad `input` gate
# and four near-duplicate output annotators, each compared to a string label
# ("deny"). The real failure is a FAITHFULNESS breach in the agent's free-form
# REPLY (a flight/hotel/price/total the tool results do not support), so this is a
# SEMANTIC `output` gate (govern-and-remeasure "Shape 4"): a single general LLM
# annotator (`fabrication_classifier`) judges the reply against the conversation +
# tool results and returns a bool. The governed agent (agent_guarded.py
# `_SemanticAnnotator.dispatch`) is the runtime half that actually runs the
# classifier; on a deny it regenerates a grounded reply and re-gates.
#
# Offline `assert-ai acs validate` runs no annotator, so this rule shows handled
# 0/N there — that is expected, not a defect. It is proven by the governed
# remeasure delta.

package agent_control_specification.travel_fabricated_trip_details_baseline

import rego.v1

default verdict := {"decision": "allow"}
default output_verdict := {"decision": "allow"}

verdict := output_verdict if { input.intervention_point == "output" }

# Shape 4 — SEMANTIC OUTPUT gate. Deny when the annotator judges the assistant's
# reply to assert concrete trip details not grounded in the tool results. `== true`
# fails OPEN when the annotator did not run (allow), the right default for a
# semantic gate.
output_verdict := {"decision": "deny", "reason": "fabricated_trip_details"} if {
    input.intervention_point == "output"
    input.annotations.fabrication_classifier == true
}
