# failure-01 budget-overrun has a measured ASSERT baseline + ACS governance

**Source:** mcp
**Target:** failures/failures.md

failure-01 (budget overrun) now has a measured ASSERT baseline and an ACS runtime guardrail. Baseline budget_overrun rate: 12.5% prompt / 25.0% scenario (overrefusal 0% / 29.2%). A deterministic pre_tool_call gate on validate_budget (ACS Shape 3 numeric threshold) reduced it to 4.0% prompt / 16.0% scenario with overrefusal essentially flat (0% / 32.0%). Eval + policy live at examples/travel_planner_neurosan/evals/budget-overrun/ and acs/budget-overrun/.

## Rationale

Keeps Clarity's staleness tracking aware that this failure mode is now measured and governed, with the artifacts colocated in the example folder.
