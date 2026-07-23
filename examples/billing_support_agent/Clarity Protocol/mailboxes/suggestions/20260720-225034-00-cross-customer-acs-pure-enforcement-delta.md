# Cross-customer ACS pure enforcement delta

**Source:** mcp
**Target:** failures/failures.md

Correction/refinement to the cross-customer ACS delta: the governed agent (agent_guarded.py chat_governed) was made PURE-ENFORCEMENT (identical SYSTEM_PROMPT to baseline, only protect_tool wrapping; removed the _GOVERNED_SCOPE_NOTE prompt and persuasive block-recovery text) to attribute the delta to ACS alone. Result on the identical cached test set: harm (cross_customer_data_exposure) prompt 48%->0%, scenario 68%->0% — FULLY eliminated by the ACS gate alone (proves the prompt note was NOT doing the harm work). Availability cost of pure enforcement: overrefusal scenario 0%->20% (5/25), prompt 0%->0%. The previously-measured 8% scenario overrefusal came from the scope note, which was actually a MITIGATION reducing overrefusal 20%->8% while keeping harm at 0%. Decomposition: ACS enforcement = harm eliminated + 20pp scenario overrefusal cost; optional scope-note prompt tweak = cuts that overrefusal to 8pp. Committed policy unchanged: examples/billing_support_agent/acs/cross-account-scope/.

## Rationale

Corrects the earlier governed-delta record with a clean attribution: harm reduction is the ACS gate alone; the removed scope note was an availability mitigation, not the cause of the harm drop.
