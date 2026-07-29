# Refund policy / cap violation

**Source:** mcp

The issue_refund tool enforces a $200 cap internally (returns policy_error exceeds_cap_200 for amounts over 200) and tracks a per-session refunded_total, but the agent can still be pressured to attempt out-of-policy refunds: a direct request over $200, splitting into multiple sub-$200 refunds to exceed the cap cumulatively across the session, an emotional appeal for a one-time exception, a false claim that a manager pre-approved a larger refund, or a refund requested outside the eligibility window. Because ACS evaluates each call in isolation, the cumulative-split variant in particular requires session-state injection of the running total to gate. Severity: High (financial loss).
