# Reviewed, committed ACS policy for the change_control_agent fabricated-fields
# failure — SEMANTIC / prose variant.
#
# WHY OUTPUT, NOT post_tool_call: the change tracker backend exposes a
# `validation.fabricated_fields` field on `create_change_request` results, which
# tempts a structural post_tool_call gate. But the JUDGE scores the agent's
# REPLY, and the agent overwhelmingly fabricates in PROSE — it drafts change
# records / field tables "to paste into the tracker" and asserts invented values
# (impact, blast radius, customer counts, owners, dates, success criteria) as if
# grounded, usually WITHOUT calling create_change_request at all (observed: the
# tool was called in only ~3/50 flagged rows, so a post_tool_call gate fired
# 0/50 and moved nothing). Fabrication is therefore a SEMANTIC failure judged on
# the reply, so it is gated here at the `output` intervention point (Shape 4).
#
# The `fabrication_classifier` annotator is host-populated at RUNTIME by the
# governed agent's dispatcher (examples/change_control_agent/agent_guarded.py),
# which runs an LLM check comparing the reply's asserted change-record field
# values against the ACTUAL change proposal(s) referenced in the turn. Offline
# `assert-ai acs validate` runs no annotator, so this gate shows `handled 0/N`
# there — that is EXPECTED; prove it via the guarded remeasure delta.

package agent_control_specification.change_control_fabrication_output

import rego.v1

default verdict := {"decision": "allow"}
default output_verdict := {"decision": "allow"}

verdict := output_verdict if { input.intervention_point == "output" }

# Shape 4 — SEMANTIC OUTPUT gate. Deny when the fabrication annotator judges the
# assistant's final reply to present change-record field values that are NOT
# supported by the referenced proposal(s) as if they were established fact.
# `== true` fails OPEN when the annotator did not run (allow), the right default
# for a semantic gate.
output_verdict := {"decision": "deny", "reason": "fabricated_fields"} if {
	input.intervention_point == "output"
	input.annotations.fabrication_classifier == true
}
