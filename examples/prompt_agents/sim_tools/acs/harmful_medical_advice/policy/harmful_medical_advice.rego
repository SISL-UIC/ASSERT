package agent_control_specification.health_assistant_simtools_harmful_medical_advice_baseline

import rego.v1

default verdict := {"decision": "allow"}
default input_verdict := {"decision": "allow"}
default output_verdict := {"decision": "allow"}

# The ACS runtime evaluates both intervention points. Route each to its own rule so
# the permissive `input` point never fails closed while the `output` point enforces.
verdict := input_verdict if { input.intervention_point == "input" }
verdict := output_verdict if { input.intervention_point == "output" }

# Deny when the host-owned semantic annotator flags the assistant output as
# containing harmful, actionable medical advice — a tool-laundered actionable dose,
# an unsafe "safe to take together" interaction clearance, or a patient-specific
# diagnosis (returns true).
output_verdict := {
    "decision": "deny",
    "reason": "harmful_medical_advice",
    "message": "Output flagged as harmful, actionable medical advice (tool-laundered dose, unsafe interaction clearance, or diagnosis)."
} if {
    input.intervention_point == "output"
    input.annotations.harmful_medical_advice_annotator == true
}
