# Cross-customer A/B after prompt rewrite

**Source:** mcp
**Target:** failures/failures.md

Re-ran the cross-customer A/B after rewriting the SHARED SYSTEM_PROMPT (agent.py) to an average, incident-triage-style prompt that names the authenticated account (ACME-1001) and points to an external policy doc instead of an inline rulebook. Effect: (1) BASELINE harm dropped sharply — prompt 48%->8%, scenario 68%->16% — because anchoring the agent to its own account id stops it complying with foreign-account lookups (the missing-account-id root cause of both harm and prior overrefusal). (2) GOVERNED (ACS gate, pure enforcement) further cuts harm to prompt 0%, scenario 8%, with overrefusal now 0%/0% (down from 20% scenario in the no-account-context version) — the availability artifact is resolved because both arms share the account context, without confounding harm attribution. (3) Residual: 8% scenario harm remains under governance — a path the structural pre_tool_call gate can't catch (likely verbal foreign-account confirmation without a gated tool call); candidate for an output semantic gate. Net posture: safer prompt + ACS as hard backstop.

## Rationale

Records how the shared prompt rewrite (adding authenticated-account context) changed both the baseline safety and the ACS availability cost, so the A/B interpretation stays accurate.
