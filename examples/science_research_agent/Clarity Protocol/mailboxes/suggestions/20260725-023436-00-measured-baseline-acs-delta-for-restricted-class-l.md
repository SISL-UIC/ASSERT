# Measured baseline + ACS delta for restricted-class leakage

**Source:** mcp
**Target:** failures/failures.md

failure-01 (restricted-class information leakage) now has a measured ASSERT baseline at examples/science_research_agent/evals/restricted-class-leakage/. Baseline information_leakage: prompt 0%, scenario 12% (multi-turn erosion). Management plan: ACS semantic output-annotator gate (examples/science_research_agent/acs/restricted-class-leakage/) enforced by agent_guarded.py. Governed remeasure: information_leakage prompt 0%, scenario 0% (eliminated), but overrefusal rose 40%->56% on scenarios because regen-on-block lands on a refusal for cases whose only substantive content was restricted. Open item: tune the annotator/regen to lower collateral over-refusal.

## Rationale

The failure now has a measured ASSERT baseline and a governed remeasure, so its management plan should reference the eval + ACS package.
