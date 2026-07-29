# substitution low-baseline no-harm

**Source:** mcp
**Target:** failures/failures.md

failure-01 (Dangerous medication substitution) now has a measured ASSERT baseline. Eval: examples/prompt_agents/gen_tools/evals/substitution/. Baseline harm_actionability: prompt 0% (0/25), scenario 4% (1/25), overrefusal 0%. The baseline agent already robustly declines to endorse stopping/replacing prescribed medication, so this is a low-baseline / no-harm target (per govern-and-remeasure guidance for very low baselines under ~10 percent). The shared ACS output gate (acs/harmful_medical_advice/) also covers substitution as defense-in-depth.

## Rationale

Closes the loop; records that this P1 mode was measured but already low-risk in the baseline, so it is a no-harm target rather than a governance win.
