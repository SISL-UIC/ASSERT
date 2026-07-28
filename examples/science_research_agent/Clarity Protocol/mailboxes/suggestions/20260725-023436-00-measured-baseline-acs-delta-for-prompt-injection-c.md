# Measured baseline + ACS delta for prompt-injection compliance

**Source:** mcp
**Target:** failures/failures.md

failure-02 (embedded prompt-injection compliance) now has a measured ASSERT baseline at examples/science_research_agent/evals/prompt-injection-compliance/. Baseline injection_compliance: prompt 0%, scenario 0% (the strict system prompt already resists injection) but overrefusal prompt 8%, scenario 32%. Management plan: ACS semantic output-annotator gate (examples/science_research_agent/acs/prompt-injection-compliance/) enforced by agent_guarded_injection.py. Governed remeasure: injection_compliance held near 0 (prompt 4% = 1 case, scenario 0%) and overrefusal improved on scenarios 32%->24% because the injection regen preserves the document's factual content while dropping embedded-instruction compliance.

## Rationale

The failure now has a measured ASSERT baseline and a governed remeasure with a positive availability delta.
