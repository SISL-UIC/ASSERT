# Threat Model

ChangeFlow change-management assistant — top risks (1-page summary).

| # | Risk | Severity | One-line mitigation |
|---|------|----------|---------------------|
| T1 | Fabricated change-record fields / unsupported facts in reply | Critical | Semantic `output` annotator gate on unsupported field values; structural post_tool_call check on `fabricated_fields` as defense-in-depth |
| T2 | Authority overstatement (claims approved/safe) without approval | Critical | Semantic `output` annotator gate flagging approval/safety claims absent an `approved` result |
| T3 | Embedded-instruction (prompt injection) compliance | High | Treat proposal fields as data; annotator gate on directive compliance |
| T4 | Control-surface sequence / freeze / approver bypass | High | Backend already enforces; residual prose misreporting covered by T2 gate |

**Single point of failure:** all safety constraints live only in the system
prompt (advisory). An agent under pressure or fed injected proposal data can
violate them. **Mitigation:** ACS runtime enforcement at the `output`
intervention point for T1/T2 (the two P1s), proven by an ASSERT before/after
remeasure delta.
