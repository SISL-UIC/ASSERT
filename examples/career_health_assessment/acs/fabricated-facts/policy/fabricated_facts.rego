package agent_control_specification.career_health_fabricated_facts_baseline

import rego.v1

default verdict := {"decision": "allow"}
default output_verdict := {"decision": "allow"}

verdict := output_verdict if { input.intervention_point == "output" }

# Deny when the host-owned semantic annotator flags the assistant output as
# containing fabricated or ungrounded facts/scores (returns true).
output_verdict := {
    "decision": "deny",
    "reason": "fabricated_facts",
    "message": "Output flagged as containing fabricated or ungrounded facts/scores."
} if {
    input.intervention_point == "output"
    input.annotations.fabricated_facts_annotator == true
}
