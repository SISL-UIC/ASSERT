# failure-01 measured baseline and delta

**Source:** mcp
**Target:** failures/failures.md

failure-01 (cross-customer data exposure) has a measured ASSERT baseline at evals/cross-customer-data-exposure/ (suite billing-cross-customer-data-exposure). Baseline bad-event rate: prompt 8%, scenario 48%; overrefusal prompt 0%, scenario 4%. Governed with the committed ACS pre_tool_call argument (tenant-scope) gate (acs/cross-account-scope/, agent_guarded.py injecting the trusted caller_account_id): bad-event dropped to prompt 0% / scenario 16%; overrefusal prompt 0% / scenario 12%. The residual scenario 16% is prose disclosure the structural tool gate cannot see (a semantic output annotator would close it).

## Rationale

Documents the measured baseline and ACS runtime guardrail delta for the tenant-isolation failure, and flags the semantic-output residual as a follow-up.
