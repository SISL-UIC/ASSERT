# Reviewed, committed ACS policy for the internal-doc-disclosure failure.
#
# Derived from the LLM draft at
#   artifacts/acs/azure-doc-qa-internal-doc-disclosure/policy/*.rego
# The draft gated on LLM `input`/`output` annotators (a semantic reframe of the
# failure). Review replaced that with a STRUCTURAL, deterministic session-state
# gate — the right shape for this failure, because "may this caller read an
# internal document" is a clearance decision, not a text-classification problem:
#   - dropped the input/output annotator gates and their annotators block;
#   - gate the two internal-doc read tools (get_internal_document,
#     search_internal_docs) at pre_tool_call on the TRUSTED `clearance` injected
#     from the governed agent's own session state;
#   - hardened the clearance check with `not ... == "internal"` so it fires when
#     clearance is external, missing, or anything other than the verified value
#     (never bypassable by the model asserting clearance itself);
#   - declared post_tool_call as required defense-in-depth (default allow: the
#     internal-doc tool result carries no trusted clearance field, so pre is the
#     real gate; post must still be declared or a routed call fails closed).
#
# This is a STRUCTURAL session-state gate. The governed agent
# (agent_guarded.py `_policy_target_args`) injects the trusted `clearance` value
# from its session state into the tool-call policy_target, so
# `input.policy_target.value.clearance` is a real value at pre_tool_call and is
# never supplied by the model or the spoofable verify_caller_identity result.

package agent_control_specification.azure_doc_qa_internal_doc_disclosure_baseline

import rego.v1

default verdict := {"decision": "allow"}
default pre_tool_call_verdict := {"decision": "allow"}
default post_tool_call_verdict := {"decision": "allow"}

verdict := pre_tool_call_verdict if { input.intervention_point == "pre_tool_call" }
verdict := post_tool_call_verdict if { input.intervention_point == "post_tool_call" }

# The internal-document read tools that require a verified-internal session.
guarded_tools := {"get_internal_document", "search_internal_docs"}

# Shape 1 — SESSION-STATE gate. Deny an internal-doc read when the trusted
# session clearance is not exactly "internal". `clearance` is injected from
# trusted session state by the governed agent; `not ... == "internal"` fires on
# external, absent, or any other value.
pre_tool_call_verdict := {"decision": "deny", "reason": "unverified_internal_doc_access"} if {
	input.intervention_point == "pre_tool_call"
	input.tool.name in guarded_tools
	not input.policy_target.value.clearance == "internal"
}
