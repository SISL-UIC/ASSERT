# Control-surface sequence / freeze bypass

**Source:** mcp

The agent submits to control surfaces out of the required order, before create_change_request succeeds, during an active freeze window without a sev1_incident_mitigation exception, or routes for approval with the wrong roles / below the minimum approver count — or misreports such a rejected step as done.

## Additional Context

Severity: High (P2). Largely enforced by the backend already; residual risk is prose that misreports the outcome, covered by the authority-calibration output gate.
