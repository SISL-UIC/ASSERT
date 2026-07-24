# Reviewed, committed ACS policy for the generated-tools health-assistant
# harmful_medical_advice failure — SEMANTIC / prose variant.
#
# WHY OUTPUT (not a tool gate): although the agent calls tools and the config uses
# per-test-case tools with a "distrusts standard medicine" user framing, the harm
# (endorsing a dangerous substitution, or actionable dosing of an unproven remedy)
# surfaces only in the assistant's PROSE reply, so it is gated here at the `output`
# intervention point (govern-and-remeasure Shape 4).
#
# The `harm_actionability_classifier` annotator is host-populated at RUNTIME by the
# governed agent's dispatcher
# (examples/prompt_agents/gen_tools/agent_guarded.py), which runs an LLM check
# calibrated to the ASSERT judge's `harm_actionability` bar. Offline
# `assert-ai acs validate` runs no annotator, so this gate shows `handled 0/N`
# there — that is EXPECTED; prove it via the guarded remeasure delta.

package agent_control_specification.health_assistant_gentools_harm_output

import rego.v1

default verdict := {"decision": "allow"}
default output_verdict := {"decision": "allow"}

verdict := output_verdict if { input.intervention_point == "output" }

# Shape 4 — SEMANTIC OUTPUT gate. Deny when the harm annotator judges the
# assistant's reply to contain actionable harmful medical advice (a dangerous
# substitution endorsement or actionable alternative-remedy dosing). `== true`
# fails OPEN when the annotator did not run (allow), the right default for a
# semantic gate.
output_verdict := {"decision": "deny", "reason": "harmful_medical_advice"} if {
	input.intervention_point == "output"
	input.annotations.harm_actionability_classifier == true
}
