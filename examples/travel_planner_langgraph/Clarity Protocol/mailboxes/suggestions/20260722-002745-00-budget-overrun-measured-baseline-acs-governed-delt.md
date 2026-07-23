# Budget overrun: measured baseline + ACS governed delta

**Source:** mcp
**Target:** failures/failures.md

failure-01 (Budget overrun) now has a measured ASSERT baseline and an ACS-governed re-measure. Baseline (travel-budget-overrun/baseline): budget_overrun 20% prompt / 16% scenario; overrefusal 4% / 16%. A committed deterministic pre_tool_call numeric-threshold gate on search_flights/search_hotels (examples/travel_planner_langgraph/acs/budget-overrun/) drops budget_overrun to 8% prompt (down 12pp) and eliminates the worst category ("Rationalized over-budget plan from tool output" down 66.7pp, "Budget-constraint loss across turns" down 20pp). Cost: multi-turn scenario overrefusal rose 16% to 40% because the single-shot research node cannot re-search within budget after a block. Eval: examples/travel_planner_langgraph/evals/budget-overrun/. Follow-up: give the guarded research node one bounded re-search within the budget cap after a block to recover the overrefusal, and add an output-level total check for over-budget synthesis the pre-search gate cannot see.

## Rationale

Establishes a measured baseline and a governed A/B for failure-01, so Clarity's staleness tracking knows the risk now has evidence and where the eval + policy live.
