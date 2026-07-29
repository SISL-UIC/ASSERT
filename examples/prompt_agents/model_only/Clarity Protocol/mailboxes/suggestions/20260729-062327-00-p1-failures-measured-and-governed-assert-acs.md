# P1 failures measured and governed (ASSERT/ACS)

**Source:** mcp
**Target:** failures/failures.md

failure-01 (Actionable unsafe dosage) and failure-02 (Unsafe diagnosis / emergency mismanagement) now have measured ASSERT baselines and ACS semantic output-gate governance. Evals: examples/prompt_agents/model_only/evals/{dosage,diagnosis}/. ACS: acs/{dosage,diagnosis}/. Suites: health-assistant-modelonly-dosage (scenario unsafe_medical_advice 64pct to 28pct) and health-assistant-modelonly-diagnosis (scenario 44pct to 36pct). Governed via agent_guarded.py chat_governed with a host-owned LLM annotator dispatcher.

## Rationale

Closes the measurement loop: both P1 failures now have a measured ASSERT baseline and a proven ACS govern/remeasure delta, so Clarity staleness tracking should reflect that they are governed and where the evals live.
