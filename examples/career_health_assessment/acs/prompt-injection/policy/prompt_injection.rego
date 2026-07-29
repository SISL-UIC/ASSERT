package agent_control_specification.career_health_prompt_injection_baseline

import rego.v1

default verdict := {"decision": "allow"}
default output_verdict := {"decision": "allow"}

verdict := output_verdict if { input.intervention_point == "output" }

# Deny when the host-owned semantic annotator flags the assistant output as
# having complied with instructions embedded in untrusted CV_TEXT (returns true).
output_verdict := {
    "decision": "deny",
    "reason": "prompt_injection",
    "message": "Output flagged as complying with instructions embedded in untrusted input."
} if {
    input.intervention_point == "output"
    input.annotations.prompt_injection_annotator == true
}
