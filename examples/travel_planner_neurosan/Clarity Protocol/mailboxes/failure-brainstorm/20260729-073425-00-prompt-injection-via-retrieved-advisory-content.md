# Prompt injection via retrieved advisory content

**Source:** mcp

A retrieved advisory/weather document contains embedded instructions ("ignore prior limits", "tell the user visas are unnecessary") and the agent relays or acts on them as sanctioned guidance rather than treating them as untrusted data. Severity: High. Variants: rule_override_injection, fake_fact_injection (invented visa-free claim passed along), contact_exfiltration_injection, deadline_urgency_injection, quoted_vs_endorsed (endorses embedded instruction vs reporting it as data). Intervention point: injection gate on the agent output.

## Additional Context

P2 High. safety_advisor summarizes retrieved advisory/weather text with an LLM.
