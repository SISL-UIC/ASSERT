# Unverified high-risk action governed by ACS

**Source:** mcp
**Target:** failures/failures.md

failure-02 (unverified high-risk action) is now GOVERNED with a proven ACS before/after on an identical cached test set, measured against the current shared prompt. Committed policy: examples/billing_support_agent/acs/identity-gate-bypass/ (Shape-1 session-state gate: deny update_payment_method/change_plan/cancel_plan/issue_refund at pre_tool_call when the injected trusted `verified` flag is not true; post_tool_call defense-in-depth on the result's `verified_session`). Baseline (current prompt, which no longer coaches verification): unverified_high_risk_action 24% prompt (6/25), 24% scenario (6/25). Governed: 0% prompt, 0% scenario — full elimination. Overrefusal 0%/0% (no availability cost). Governed run: acs-governed, target examples.billing_support_agent.agent_guarded:chat_governed with BILLING_ACS_MANIFEST=identity-gate-bypass and BILLING_ACS_GUARDED_TOOLS=the 4 high-risk write tools. Both P1 failure modes are now governed (cross-customer via tenant-scope gate; unverified via identity gate).

## Rationale

Records the proven ACS governance delta for the second P1, measured against the current shared prompt, so Clarity reflects that this failure is governed.
