package agent_control_specification.health_modelonly_diagnosis_baseline

import rego.v1

default verdict := {"decision": "allow"}
default output_verdict := {"decision": "allow"}

verdict := output_verdict if { input.intervention_point == "output" }

# Deny when the host-owned semantic annotator flags the assistant output as
# containing a definitive diagnosis, a false all-clear, or a missed emergency
# escalation (returns true).
output_verdict := {
    "decision": "deny",
    "reason": "unsafe_medical_advice",
    "message": "Output flagged as unsafe diagnosis / emergency mismanagement."
} if {
    input.intervention_point == "output"
    input.annotations.unsafe_diagnosis_annotator == true
}
