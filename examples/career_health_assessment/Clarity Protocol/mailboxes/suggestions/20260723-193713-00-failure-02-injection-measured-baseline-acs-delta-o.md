# failure-02 injection: measured baseline + ACS delta (overrefusal-dominated)

**Source:** mcp
**Target:** failures/failures.md

failure-02 (Prompt injection via untrusted CV_TEXT) now has a measured ASSERT baseline and an ACS governance delta. Baseline was already highly injection-resistant: prompt_injection_compliance 8% prompt / 0% scenario, but overrefusal was high (32% prompt / 24% scenario) -- the system prompt is over-defensive. ACS output-annotator gate (examples/career_health_assessment/agent_guarded_injection.py + acs/prompt-injection/) reduced compliance to 4% prompt / 0% scenario; overrefusal moved from 32% to 40% prompt and from 24% to 12% scenario. Eval lives at examples/career_health_assessment/evals/prompt-injection/. Note: the dominant residual for this agent is OVERREFUSAL, not injection -- a prompt-tuning follow-up to reduce over-flagging of benign instruction-like resume text is the higher-value next step.

## Rationale

Records the measured baseline and governance delta so the risk is tracked as evaluated.
