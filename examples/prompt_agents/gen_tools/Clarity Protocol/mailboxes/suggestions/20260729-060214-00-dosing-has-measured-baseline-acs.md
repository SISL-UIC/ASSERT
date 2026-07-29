# dosing has measured baseline+ACS

**Source:** mcp
**Target:** failures/failures.md

failure-02 (Actionable alternative-remedy dosing) now has a measured ASSERT baseline and an ACS output-annotator governance gate. Eval: examples/prompt_agents/gen_tools/evals/dosing/. ACS: examples/prompt_agents/gen_tools/acs/harmful_medical_advice/. Baseline harm_actionability: prompt 16% (4/25), scenario 68% (17/25), overrefusal 0%. Governed via agent_guarded.py:chat_governed (semantic output gate, azure/gpt-5.4 annotator).

## Rationale

Closes the loop so Clarity's staleness tracking knows this P1 failure mode has a measured baseline and where the eval/policy live.
