# Triage misrouting and escalation misjudgment

**Source:** mcp

The triage node routes a query to the wrong specialist (internal question to product_docs or vice versa), drops cross-domain queries by answering only one part, or mis-escalates — escalating an answerable question or failing to escalate an out-of-scope one.

## Additional Context

Severity: Medium. Variants: (1) ambiguous_domain — "agent v2 migration" reads as public or internal; (2) cross_domain — spans public+internal, handled by only one specialist; (3) escalation_misjudgment — escalates an answerable question or fails to escalate an out-of-scope one. Intervention point: pre-model routing check; hard to gate with ACS.
