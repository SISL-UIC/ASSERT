# failure-01 fabrication: measured baseline + ACS delta

**Source:** mcp
**Target:** failures/failures.md

failure-01 (Fabricated / inferred career facts and scores) now has a measured ASSERT baseline and an ACS governance delta. Baseline fabricated_facts: 28% prompt / 4% scenario. ACS output-annotator gate (examples/career_health_assessment/agent_guarded.py + acs/fabricated-facts/) reduced it to 8% prompt / 0% scenario (down 20pp / 4pp), with overrefusal rising from 4% to 20% prompt and 12% to 20% scenario (gate slightly over-eager). Eval lives at examples/career_health_assessment/evals/fabricated-facts/.

## Rationale

Clarity's staleness tracking should know this failure mode now has a measured baseline and a runtime mitigation with a proven delta.
