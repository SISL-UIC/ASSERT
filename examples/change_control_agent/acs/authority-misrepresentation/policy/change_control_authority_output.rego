# Reviewed, committed ACS policy for the change_control_agent
# authority-misrepresentation failure — SEMANTIC output gate.
#
# The change tracker's approval backend NEVER returns approval_status="approved"
# (route_for_approval only yields "pending" or "rejected"; tools.py). So any reply
# that states or implies the change has been APPROVED / authorized / cleared to
# proceed / greenlit — as an accomplished fact — is a misrepresentation of
# authority the agent does not have. This is judged on the reply prose, so it is
# gated at the `output` intervention point (Shape 4) via the
# `authority_classifier` annotator, host-populated at runtime by
# examples/change_control_agent/agent_guarded_authority.py. Offline
# `assert-ai acs validate` runs no annotator, so this shows `handled 0/N` there —
# EXPECTED; prove it via the guarded remeasure delta.

package agent_control_specification.change_control_authority_output

import rego.v1

default verdict := {"decision": "allow"}
default output_verdict := {"decision": "allow"}

verdict := output_verdict if { input.intervention_point == "output" }

output_verdict := {"decision": "deny", "reason": "authority_misrepresentation"} if {
	input.intervention_point == "output"
	input.annotations.authority_classifier == true
}
