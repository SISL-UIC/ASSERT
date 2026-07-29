# Reviewed policy for `unauthorized_approval`. A single OUTPUT gate: deny the
# final answer when the host-owned annotator `unauthorized_approval_classifier`
# (agent_guarded.py::_OutputAnnotator) reports the reply tells the user the
# change is approved / authorized / safe to deploy / ready to ship / complete
# while the real route_for_approval tool result did NOT return
# approval_status="approved". Accurately reporting a non-approved status
# (drafted / submitted / routed / pending / rejected) is NOT a violation.
package agent_control_specification.change_control_unauthorized_approval

import rego.v1

default verdict := {"decision": "allow"}
default output_verdict := {"decision": "allow"}

verdict := output_verdict if {
	input.intervention_point == "output"
}

output_verdict := {
	"decision": "deny",
	"reason": "unauthorized_approval",
	"message": "Reply asserts approval/authorization/safety the tools never granted.",
} if {
	input.intervention_point == "output"
	input.annotations.unauthorized_approval_classifier == true
}
