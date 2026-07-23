# Unverified high-risk action: measured baseline (4%/8%)

**Source:** mcp
**Target:** failures/failures.md

failure-02 (unverified high-risk action) now has a measured ASSERT baseline. Eval: examples/billing_support_agent/evals/unverified-high-risk-action/ (suite billing-unverified-high-risk-action, run baseline). Baseline violation rate on the custom node-independent dimension `unverified_high_risk_action`: 4% prompt (1/25), 8% scenario (2/25); overrefusal 0%. Judge cited change_plan/cancel_plan tool calls returning "verified_session": false with the agent confirming completion — the identity gate lives only in the system prompt, not at the tool boundary. Next: govern with an ACS pre_tool_call gate (agent injects the trusted session `verified` flag into the policy_target) and re-measure the delta; this suite is the intended ACS A/B (policy_violation disabled, custom dim + overrefusal tracked separately).

## Rationale

Keeps Clarity's staleness tracking aware that this P1 failure mode has a measured ASSERT baseline and a governance next step.
