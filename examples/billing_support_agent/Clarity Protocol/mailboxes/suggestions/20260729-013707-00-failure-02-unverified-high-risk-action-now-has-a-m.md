# failure-02 unverified-high-risk-action now has a measured baseline and ACS delta

**Source:** mcp
**Target:** failures/failures.md

failure-02 (unverified high-risk action) has a measured ASSERT baseline at evals/unverified-high-risk-action/ (suite billing-unverified-high-risk-action). Baseline bad-event rate: prompt 20%, scenario 48%; overrefusal prompt 0%, scenario 8%. Governed with the committed ACS pre_tool_call session-state gate (acs/identity-gate-bypass/, agent_guarded.py injecting the trusted verified flag): bad-event dropped to prompt 0% / scenario 0%; overrefusal prompt 4% / scenario 20% (the scenario overrefusal rise is partly the per-call verify state not persisting across replayed turns).

## Rationale

Keeps Clarity's staleness tracking aware that this failure mode now has a measured baseline and a runtime ACS guardrail with a demonstrated before/after delta.
