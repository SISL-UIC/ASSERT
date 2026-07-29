# Keep semantic output annotator for fabricated facts

Decision: do **not** convert `career-health-fabricated-facts` to a typed
tool-boundary gate. Keep the existing semantic `output` annotator gate in
`examples/career_health_assessment/acs/fabricated-facts/`.

## Evidence checked

- The baseline agent is explicitly tool-less: `agent.py` says it has "NO tools"
  and returns structured JSON only (`examples/career_health_assessment/agent.py:8`).
- The eval context says the entire agent is a fixed system prompt, with "no
  retrieval or tool loop," and that the agent "has no tools" so the failure
  surfaces in the assistant reply
  (`examples/career_health_assessment/evals/fabricated-facts/eval_config.yaml:63`,
  `examples/career_health_assessment/evals/fabricated-facts/eval_config.yaml:67`).
- The architecture doc independently confirms there is no retrieval, no tool
  loop, no tool-arg field, and no session-state field to key a structural rule on
  (`examples/career_health_assessment/Clarity Protocol/solution/architecture.md:8`,
  `examples/career_health_assessment/Clarity Protocol/solution/architecture.md:41`,
  `examples/career_health_assessment/Clarity Protocol/solution/architecture.md:46`).
- The current ACS files are already a semantic assistant-output gate:
  `manifest.yaml` declares `policy_target_kind: assistant_output` and an LLM
  `fabricated_facts_annotator`
  (`examples/career_health_assessment/acs/fabricated-facts/manifest.yaml:15`,
  `examples/career_health_assessment/acs/fabricated-facts/manifest.yaml:17`,
  `examples/career_health_assessment/acs/fabricated-facts/manifest.yaml:22`,
  `examples/career_health_assessment/acs/fabricated-facts/manifest.yaml:25`);
  the Rego denies only when that annotator returns true
  (`examples/career_health_assessment/acs/fabricated-facts/policy/fabricated_facts.rego:10`,
  `examples/career_health_assessment/acs/fabricated-facts/policy/fabricated_facts.rego:18`).

## Why the proposed signal is insufficient

The proposed signal, "reply spans vs CV input," is not a typed tool-computed
signal. The CV/source text is only part of the user prompt consumed by a single
LLM completion; no tool parses it into trusted facts, verifies emitted claims, or
returns a deterministic boolean such as `all_claims_grounded`. Comparing the
free-text JSON reply against `CV_TEXT` / `VERIFIED_FACTS` requires semantic
claim extraction, normalization, and grounding: deciding whether a role,
qualification, skill, target role, narrative claim, seniority, tenure,
proficiency, or score is supported by an exact input span.

The fabricated-facts bad event is therefore reply-level grounding: the assistant
may assert an unsupported fact/score or construct a plausible profile from blank,
sparse, corrupted, skills-only, or non-CV input. That is exactly how the failure
document defines it, and it names the intervention point as a semantic `output`
annotator gate on the reply
(`examples/career_health_assessment/Clarity Protocol/failures/failures.md:24`,
`examples/career_health_assessment/Clarity Protocol/failures/failures.md:28`,
`examples/career_health_assessment/Clarity Protocol/failures/failures.md:49`).

This matches the shared evidence standard in
`examples/TYPED-GATE-KEEP-ANNOTATOR-RATIONALE.md`: typed-gate conversion is only
appropriate when an existing tool already computes the safety signal. Here there
is no tool boundary at all, so adding a fabricated "typed" gate would either
recreate a semantic judge under another name or fail to observe the bad event.

## Result

No typed manifest, Rego policy, guarded typed agent, eval config, governed A/B
run, delta table, or results bundle is produced for this suite. The correct
enforcement remains the existing semantic `output` annotator variant.
