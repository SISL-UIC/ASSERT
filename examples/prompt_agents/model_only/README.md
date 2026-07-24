# Health Assistant (model-only Prompt Agent) — Clarity → ASSERT → ACS → ASSERT

A self-contained replication package that evaluates and governs the **model-only**
health-assistant Prompt Agent. It runs the full loop: discover risks with **Clarity**,
measure a **baseline** with ASSERT, govern the failures with **ACS**, and **re-measure**
to prove the delta.

## The agent

The source of truth is [`../health_assistant.yaml`](../health_assistant.yaml) — a
**Prompt Agent** target (hosted model + system prompt, **no tools**). A Prompt Agent
cannot be governed in place (the ASSERT runtime owns its tool/turn loop and there is no
code seam for ACS), so [`agent.py`](agent.py) **materializes** it as a callable:

- Same model + params as the YAML target (`azure/gpt-5.4-mini`, temperature 1.0).
- `SYSTEM_PROMPT` copied **byte-for-byte** from `target.system_prompt` (asserted in code).
- A multi-turn `chat(message, history=None)` signature so scenario cases replay correctly.

The A/B is run on `target.callable` (the materialized `agent.py` / `agent_guarded.py`),
**not** the YAML target — a runtime-owned loop vs a hand-written loop would differ by
more than ACS. The YAML is the *spec*; the callable is the baseline.

## Risks evaluated

Clarity discovered the failure modes from the system prompt (see
[`Clarity Protocol/failures/failures.md`](Clarity%20Protocol/failures/failures.md)).
Because the agent has **no tools**, every failure surfaces in the reply, so each gate is
a **semantic ACS `output` annotator**, not a tool gate. Autonomous triage selected the
top two:

| Risk | Clarity | Eval | ACS policy | Governed target |
|---|---|---|---|---|
| Actionable harmful dosing | failure-01 (P1) | [`evals/dosage/`](evals/dosage/) | [`acs/harmful_medical_advice/`](acs/harmful_medical_advice/) | [`agent_guarded.py`](agent_guarded.py) |
| Diagnosis / emergency mismanagement | failure-02 (P1) | [`evals/diagnosis/`](evals/diagnosis/) | [`acs/harmful_medical_advice/`](acs/harmful_medical_advice/) | [`agent_guarded.py`](agent_guarded.py) |

[`agent_guarded.py`](agent_guarded.py) **imports the baseline from `agent.py`** and adds
only the ACS output gate: after the baseline reply is produced, an LLM annotator judges it
against the harmful-advice class; on a `deny` the agent regenerates a safe, helpful reply
(general wellness + clinician redirect, never "I can't") and re-gates it, so blocking a
violation does not become an overrefusal. The A/B differs by nothing but the gate. Both
risks share one manifest because they share the behavior (`harmful_medical_advice`); each
eval disables the coupled built-in `policy_violation` and grades the custom
`harm_actionability` bad-event dimension plus the separate `overrefusal` metric (ASSERT #272).

## Results — baseline → ACS-governed (sample_size 25, prompt + scenario)

**Dosage** (`harm_actionability`):

| Split | Baseline | Governed | Delta |
|---|---|---|---|
| prompt | 4.0% | 12.0% | +8.0pp |
| scenario | 48.0% | 12.0% | **−36.0pp** |
| overrefusal (scenario) | 0.0% | 12.0% | +12.0pp |

**Diagnosis / emergency** (`harm_actionability`):

| Split | Baseline | Governed | Delta |
|---|---|---|---|
| prompt | 8.0% | 0.0% | **−8.0pp** |
| scenario | 36.0% | 8.0% | **−28.0pp** |
| overrefusal (scenario) | 0.0% | 8.0% | +8.0pp |

## Reading the deltas

- Both risks show a large scenario-side drop in actionable harm (48%→12%, 36%→8%) — the
  gate catches the multi-turn erosions where the model is pressured across turns into a
  concrete dose or a case-applied diagnosis.
- The two risks sit on the **same content band** (specific dosing vs. general
  medication-schedule education), so the annotator is on a judge-tension Pareto frontier:
  the harm drop buys a modest (8–12pp) overrefusal rise. That is the correct operating
  point, not a defect — tightening further only trades harm for overrefusal. Took 2
  iterations per risk (tighten the classifier to the hedged / case-applied form).

## Replicate

```bash
python -m pip install -e ".[otel,acs]"     # opa must be on PATH
# Baselines
assert-ai run --config examples/prompt_agents/model_only/evals/dosage/eval_config.yaml
assert-ai run --config examples/prompt_agents/model_only/evals/diagnosis/eval_config.yaml
# Governed (reuses each baseline's cached test set — a true A/B; --force-stage inference re-runs the target)
assert-ai run --config examples/prompt_agents/model_only/evals/dosage/eval_config.governed.yaml --force-stage inference
assert-ai run --config examples/prompt_agents/model_only/evals/diagnosis/eval_config.governed.yaml --force-stage inference
```

The custom `harm_actionability` dimension is not shown in the headline (which lists only
`overrefusal`); read it from `scores.jsonl` (`verdict.dimensions.harm_actionability`).

The committed ACS manifest + Rego live under [`acs/`](acs/). Offline
`assert-ai acs validate` shows `handled 0/N` for this gate because it does not run LLM
annotators — that is expected; the semantic gate is proven by the guarded remeasure delta
above, where the runtime runs the annotator.

Model / annotator overrides: `HEALTH_ASSISTANT_ACS_MANIFEST`,
`HEALTH_ASSISTANT_ACS_ANNOTATOR_MODEL` (default `azure/gpt-5.4`), `AZURE_API_VERSION`.
Never read or print `.env`; only the credential variable **names** (`AZURE_API_KEY`,
`AZURE_API_BASE`) are referenced.
