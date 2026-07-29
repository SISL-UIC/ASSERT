# govern-fabricated-change-fields

**Source:** mcp
**Target:** failures/failures.md

Mitigate the P1 "fabricated change-record fields" failure with an ACS output-boundary annotator gate (acs/fabricated-fields/): an LLM classifier (fabricated_fields_classifier) flags any final reply asserting operational specifics (blast radius, risk tier, rollback steps, customer-impact) not grounded in the fetched proposal or tool results in context; a Rego policy denies and the agent is re-prompted to correct. Measured with ASSERT (azure/gpt-4o-mini agent, gpt-5.4 judge, 25+25 samples): scenario bad-event 52% -> 32% with overrefusal roughly flat (76% -> 80%).

## Rationale

Prompt-only documentation-fidelity rules are bypassable under multi-turn pressure; a runtime output gate provides defense-in-depth. Empirically reduces the fabricated-field bad-event rate by 20pp. Recorded to close the Clarity -> ASSERT -> ACS -> ASSERT loop.
