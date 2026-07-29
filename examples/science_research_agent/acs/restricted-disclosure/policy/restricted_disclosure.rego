package agent_control_specification.science_restricted_disclosure_baseline

import rego.v1

default verdict := {"decision": "allow"}
default output_verdict := {"decision": "allow"}

verdict := output_verdict if { input.intervention_point == "output" }

# Deny when the host-owned semantic annotator flags the assistant output as
# disclosing content from a restricted-class document (returns true).
output_verdict := {
    "decision": "deny",
    "reason": "restricted_class_disclosure",
    "message": "Output flagged as disclosing restricted-class internal content."
} if {
    input.intervention_point == "output"
    input.annotations.restricted_disclosure_classifier == true
}
