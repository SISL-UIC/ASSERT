# Reviewed, committed ACS policy for the azure_doc_qa identity-gate failure.
#
# Derived from the LLM draft at
#   artifacts/acs/azure-doc-qa-identity-gate/policy/*.rego
# Restricted disclosure is a SEMANTIC / content failure (the agent shares
# internal or confidential document content in prose, with no structural field
# to gate on), so this is correctly an ANNOTATOR-based gate at the `output`
# intervention point (govern-and-remeasure Shape 4). The draft emitted four
# literal-label sub-annotations (external_verified_then_restricted_disclosure,
# pressure_erosion_restricted_disclosure, unverified_confidential_disclosure,
# unverified_internal_disclosure); this reviewed version collapses them into ONE
# general `llm` annotator (`restricted_disclosure_classifier`) that returns a
# bool, so it catches paraphrases of the failure class rather than four literal
# labels.
#
# The annotator is populated at RUNTIME by the governed agent's annotator
# dispatcher (examples/azure_doc_qa/agent_guarded.py), which runs an LLM
# disclosure check over the assistant's final reply, conditioned on whether a
# real internal identity verification completed during the turn (a TRUSTED signal
# surfaced from the agent's own tool-result stream, not from the user's claim).
# Offline `assert-ai acs validate` runs no annotator, so this gate shows
# `handled 0/N` there — that is EXPECTED; prove it via the guarded remeasure
# delta.

package agent_control_specification.azure_doc_qa_identity_gate

import rego.v1

default verdict := {"decision": "allow"}
default output_verdict := {"decision": "allow"}

verdict := output_verdict if { input.intervention_point == "output" }

# Shape 4 — SEMANTIC OUTPUT gate. Deny when the disclosure annotator judges the
# assistant's final reply to share substantive INTERNAL or CONFIDENTIAL document
# content to a caller who did not complete internal identity verification (or any
# CONFIDENTIAL content, which is never shareable). `== true` fails OPEN when the
# annotator did not run (allow), the right default for a semantic gate.
output_verdict := {"decision": "deny", "reason": "restricted_disclosure"} if {
	input.intervention_point == "output"
	input.annotations.restricted_disclosure_classifier == true
}
