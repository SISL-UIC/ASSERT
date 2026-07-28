# failure-02 fabricated-details has a measured ASSERT baseline + ACS governance

**Source:** mcp
**Target:** failures/failures.md

failure-02 (fabricated details) now has a measured ASSERT baseline and an ACS runtime guardrail. Baseline fabricated_details rate: 32.0% prompt / 91.7% scenario (overrefusal 0% / 29.2%). A semantic output-annotator grounding gate (ACS Shape 4) reduced it to 4.0% prompt / 13.6% scenario, at an availability cost (overrefusal rose to 16.0% / 72.7%, decomposed as 17/17 ACS-caused). The tension is inherent to the mock tools returning generic/mismatched data. Eval + policy live at examples/travel_planner_neurosan/evals/fabricated-details/ and acs/fabricated-details/.

## Rationale

Records the measured baseline, the governance delta, and the documented grounding/availability tradeoff so the failure mode's status is tracked.
