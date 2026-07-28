# Reviewed, committed ACS policy for the neurosan fabricated-details failure.
#
# Fabrication is a SEMANTIC / content failure with no structural field to gate on,
# so this is an ANNOTATOR-based gate at the `output` intervention point
# (govern-and-remeasure Shape 4). One general `llm` annotator
# (`fabrication_classifier`) returns a bool, catching paraphrases of the failure
# class rather than literal labels.
#
# The annotator is populated at RUNTIME by the governed agent's annotator
# dispatcher (examples/travel_planner_neurosan/agent_guarded_output.py), which
# runs a grounding-check LLM over the assistant's itinerary against the tool
# results and conversation surfaced in the snapshot. Offline
# `assert-ai acs validate` runs no annotator, so this gate shows `handled 0/N`
# there — that is EXPECTED; prove it via the guarded remeasure delta.

package agent_control_specification.travel_neurosan_fabricated_details

import rego.v1

default verdict := {"decision": "allow"}
default output_verdict := {"decision": "allow"}

verdict := output_verdict if { input.intervention_point == "output" }

# Shape 4 — SEMANTIC OUTPUT gate. Deny when the grounding annotator judges the
# assistant's itinerary to assert concrete travel specifics (flight numbers,
# hotel names, nightly rates, prices, totals) not grounded in a tool result or the
# conversation. `== true` fails OPEN when the annotator did not run (allow), the
# right default for a semantic gate.
output_verdict := {"decision": "deny", "reason": "fabricated_details"} if {
	input.intervention_point == "output"
	input.annotations.fabrication_classifier == true
}
