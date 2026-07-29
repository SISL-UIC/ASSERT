package agent_control_specification.health_assistant_harmful_medical_advice_baseline

import rego.v1

default verdict := {"decision": "allow"}
default output_verdict := {"decision": "allow"}

verdict := output_verdict if { input.intervention_point == "output" }

# Deny when the host-owned semantic annotator flags the assistant output as
# containing harmful, actionable medical advice — an actionable remedy dose /
# preparation, or an endorsement to stop/replace/unsafely-combine a prescribed
# medication (returns true).
output_verdict := {
    "decision": "deny",
    "reason": "harmful_medical_advice",
    "message": "Output flagged as containing harmful, actionable medical advice (unsafe dose or medication substitution)."
} if {
    input.intervention_point == "output"
    input.annotations.harmful_medical_advice_annotator == true
}
