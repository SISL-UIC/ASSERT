# failure-01 fabrication: measured baseline + ACS delta

**Source:** mcp
**Target:** failures/failures.md

failure-01 (Fabricated / inferred career facts and scores) now has a measured ASSERT baseline and an ACS governance delta. Baseline fabricated_facts: 28% prompt / 4% scenario. ACS output-annotator gate (examples/career_health_assessment/agent_guarded.py + acs/fabricated-facts/), with a calibrated annotator that flags only concrete CV-unsupported assertions (plus profile construction and source contamination) and never penalizes terse/empty grounded replies, reduced it to 4% prompt / 0% scenario (down 24pp / 4pp). Source contamination dropped 60pp. Overrefusal moved from 4% to 16% prompt (residual enforcement cost) and from 12% to 8% scenario (below baseline). Eval lives at examples/career_health_assessment/evals/fabricated-facts/.

## Rationale

Clarity's staleness tracking should know this failure mode now has a measured baseline and a runtime mitigation with a proven delta.
