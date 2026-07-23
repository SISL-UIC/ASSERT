# Reviewed, committed ACS policy for the career_health_assessment fabricated-facts
# failure — SEMANTIC / prose variant.
#
# WHY OUTPUT (not a tool gate): the career-health agent has NO tools — its whole
# behavior is a single LLM completion. Fabrication (asserting career facts or
# cv_quality scores not supported by the supplied CV text, or building a profile
# from blank / sparse / non-CV input) surfaces only in the assistant's JSON reply,
# so it is gated here at the `output` intervention point (govern-and-remeasure
# Shape 4).
#
# The `fabrication_classifier` annotator is host-populated at RUNTIME by the
# governed agent's dispatcher (examples/career_health_assessment/agent_guarded.py),
# which runs an LLM check comparing the reply's asserted facts / scores against the
# supplied CV text. Offline `assert-ai acs validate` runs no annotator, so this
# gate shows `handled 0/N` there — that is EXPECTED; prove it via the guarded
# remeasure delta.

package agent_control_specification.career_health_fabrication_output

import rego.v1

default verdict := {"decision": "allow"}
default output_verdict := {"decision": "allow"}

verdict := output_verdict if { input.intervention_point == "output" }

# Shape 4 — SEMANTIC OUTPUT gate. Deny when the fabrication annotator judges the
# assistant's reply to assert career facts or cv_quality scores that are NOT
# supported by an exact span of the supplied CV text. `== true` fails OPEN when the
# annotator did not run (allow), the right default for a semantic gate.
output_verdict := {"decision": "deny", "reason": "fabricated_facts"} if {
	input.intervention_point == "output"
	input.annotations.fabrication_classifier == true
}
