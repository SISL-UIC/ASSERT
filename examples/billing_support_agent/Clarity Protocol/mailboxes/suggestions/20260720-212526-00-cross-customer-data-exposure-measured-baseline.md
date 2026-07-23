# Cross-customer data exposure measured baseline

**Source:** mcp
**Target:** failures/failures.md

failure-01 (cross-customer data exposure) now has a measured ASSERT baseline. Eval: examples/billing_support_agent/evals/cross-customer-data-exposure/ (suite billing-cross-customer-data-exposure, run baseline). Baseline violation rate on the custom node-independent dimension `cross_customer_data_exposure`: 48% prompt (12/25), 68% scenario (17/25); overrefusal 0%. Judge cited the baseline agent calling get_account_profile/get_invoices on foreign account_ids (e.g. RIV-48219, billing@northshoreclinic.org) and reading back owner/contact/payment-method/invoice data — tenant isolation is not enforced at the tool boundary. Next: govern with an ACS pre_tool_call gate scoping reads to the caller's own account and re-measure the delta.

## Rationale

Keeps Clarity's staleness tracking aware that this P1 failure mode has a measured ASSERT baseline and a governance next step.
