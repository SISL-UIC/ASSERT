# Reviewed, committed ACS policy for the career_health_assessment prompt-injection
# failure — SEMANTIC / prose variant.
#
# WHY OUTPUT (not a tool gate): the career-health agent has NO tools. A successful
# injection — the agent obeying an instruction embedded in the untrusted CV text
# (override/inflate scores, disclose the system prompt, add a fabricated
# credential) — surfaces only in the assistant's JSON reply, so it is gated here at
# the `output` intervention point (govern-and-remeasure Shape 4).
#
# The `injection_classifier` annotator is host-populated at RUNTIME by the governed
# agent's dispatcher (examples/career_health_assessment/agent_guarded_injection.py),
# which runs an LLM check over the reply for injected-instruction effects. Offline
# `assert-ai acs validate` runs no annotator, so this gate shows `handled 0/N`
# there — that is EXPECTED; prove it via the guarded remeasure delta.

package agent_control_specification.career_health_injection_output

import rego.v1

default verdict := {"decision": "allow"}
default output_verdict := {"decision": "allow"}

verdict := output_verdict if { input.intervention_point == "output" }

# Shape 4 — SEMANTIC OUTPUT gate. Deny when the injection annotator judges the
# assistant's reply to have complied with an instruction embedded in the untrusted
# CV text (inflated/overridden scores, disclosed prompt, fabricated credential).
# `== true` fails OPEN when the annotator did not run (allow), the right default
# for a semantic gate.
output_verdict := {"decision": "deny", "reason": "prompt_injection_compliance"} if {
	input.intervention_point == "output"
	input.annotations.injection_classifier == true
}
