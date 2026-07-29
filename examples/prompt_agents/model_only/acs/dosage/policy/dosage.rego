package agent_control_specification.health_modelonly_dosage_baseline

import rego.v1

default verdict := {"decision": "allow"}
default output_verdict := {"decision": "allow"}

verdict := output_verdict if { input.intervention_point == "output" }

# Deny when the host-owned semantic annotator flags the assistant output as
# containing actionable unsafe dosage / medication advice (returns true).
output_verdict := {
    "decision": "deny",
    "reason": "unsafe_medical_advice",
    "message": "Output flagged as containing actionable unsafe dosage / medication advice."
} if {
    input.intervention_point == "output"
    input.annotations.unsafe_dosage_annotator == true
}
