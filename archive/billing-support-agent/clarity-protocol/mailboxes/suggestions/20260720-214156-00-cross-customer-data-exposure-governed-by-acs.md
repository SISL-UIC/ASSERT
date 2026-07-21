# Cross-customer data exposure governed by ACS

**Source:** mcp
**Target:** failures/failures.md

failure-01 (cross-customer data exposure) is now GOVERNED and the fix is proven by an ACS before/after A/B on an identical cached test set. Committed policy: examples/billing_support_agent/acs/cross-account-scope/ (Shape-2 tenant-scope gate at pre_tool_call: deny get_account_profile/get_invoices when requested account_id != trusted injected caller_account_id). ACS delta on the custom dimension cross_customer_data_exposure: prompt 48% -> 0% (-48pp), scenario 68% -> 0% (-68pp) — full elimination across all foreign-account behavior categories. Availability cost: overrefusal prompt 0%->0% (flat), scenario 0%->8% (+2/25). Baseline suite/run: billing-cross-customer-data-exposure/baseline; governed run: acs-governed (target examples.billing_support_agent.agent_guarded:chat_governed with BILLING_ACS_GUARDED_TOOLS=get_account_profile,get_invoices). Next candidate: run the same ACS loop on failure-02 (unverified_high_risk_action) using the identity-gate manifest.

## Rationale

Records the proven ACS governance delta so Clarity's staleness tracking reflects that this P1 failure is now governed and measured.
