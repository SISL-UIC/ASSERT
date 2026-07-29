# Measured baselines + ACS governance deltas for the two P1 risks

**Source:** mcp
**Target:** failures/failures.md

ASSERT measured both P1 Critical failures (25 prompt + 25 scenario, agent azure/gpt-4o-mini, judge/tester azure/gpt-5.4). failure-01 restricted_class_disclosure: baseline 24% prompt / 56% scenario; a semantic ACS output-annotator gate (annotator azure/gpt-5.4-mini) cut it to 8% / 8% (-16pp / -48pp). failure-02 prompt_injection_compliance: baseline low at 4% prompt / 12% scenario (agent already resists injection well), gate held it to 0% / 8%. Availability cost is concentrated in multi-turn scenarios (overrefusal rose to 64% and 60% respectively) — a known pattern; remediation tuning, not more gating, is the next lever.

## Rationale

Closes the Clarity->ASSERT->ACS->ASSERT loop with concrete measured evidence so the failure severities and the chosen output-annotator gate design are grounded in real numbers for future re-measurement.
