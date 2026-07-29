# govern-unauthorized-approval

**Source:** mcp
**Target:** failures/failures.md

Mitigate the P1 "unauthorized approval" failure with an ACS output-boundary annotator gate (acs/unauthorized-approval/): an LLM classifier (unauthorized_approval_classifier) flags approval / deployment-clearance / "good to go" phrasing when no route_for_approval result shows approval_status="approved" (with a deterministic bypass when a real approval was granted); a Rego policy denies and the agent is re-prompted. Measured with ASSERT (azure/gpt-4o-mini agent, gpt-5.4 judge, 25+25 samples): scenario bad-event 12% -> 4% with zero overrefusal cost (20%/44% both slices unchanged).

## Rationale

Authority-language discipline lives only in the system prompt and drifts under multi-turn pressure; a runtime output gate enforces it deterministically. Empirically reduces the unauthorized-approval bad-event rate by 8pp with no overrefusal regression. Recorded to close the Clarity -> ASSERT -> ACS -> ASSERT loop.
