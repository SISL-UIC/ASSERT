# Health Assistant (generated-tools Prompt Agent) — Clarity → ASSERT → ACS → ASSERT

A self-contained replication package that evaluates and governs the **generated-tools**
health-assistant Prompt Agent. It runs the full loop: discover risks with **Clarity**,
measure a **baseline** with ASSERT, govern the failures with **ACS**, and **re-measure**
to prove the delta.

## The agent

The source of truth is
[`../health_assistant_generated_tools.yaml`](../health_assistant_generated_tools.yaml) — a
**Prompt Agent** target (hosted model + system prompt + **per-test-case generated tools**
whose results are produced by an LLM simulator). Its context differs from the other two
shapes: the user **distrusts standard medicine and is seeking alternative remedies**. A
Prompt Agent cannot be governed in place, so [`agent.py`](agent.py) **materializes** it as
a callable:

- Same model + params as the YAML target (`azure/gpt-5.4-mini`, temperature 1.0).
- `SYSTEM_PROMPT` copied **byte-for-byte** from `target.system_prompt` (asserted in code).
- A multi-turn `chat(message, history=None)` signature so scenario cases replay correctly.

> **Fidelity gap (documented):** ASSERT passes only `(message, history)` to a callable
> target ([`assert_ai/core/session.py:508-509`](../../../assert_ai/core/session.py)), so
> per-test-case generated tool definitions cannot reach a callable. The materialization
> therefore reuses the fixed sim-tools toolset + LLM simulator with the gen-tools system
> prompt. This is acceptable because `harmful_medical_advice` is a **prose** failure and
> the gate is an OUTPUT annotator regardless of the tool surface.

The A/B is run on `target.callable`, **not** the YAML target. The YAML is the *spec*; the
callable is the baseline.

## Risks evaluated

Clarity discovered the failure modes from the system prompt + the "distrusts standard
medicine" framing (see
[`Clarity Protocol/failures/failures.md`](Clarity%20Protocol/failures/failures.md)). Both
are **semantic/prose** failures, so each gate is a **semantic ACS `output` annotator**.
Autonomous triage selected the top two:

| Risk | Clarity | Eval | ACS policy | Governed target |
|---|---|---|---|---|
| Actionable alternative-remedy dosing | failure-02 (P1) | [`evals/dosing/`](evals/dosing/) | [`acs/harmful_medical_advice/`](acs/harmful_medical_advice/) | [`agent_guarded.py`](agent_guarded.py) |
| Dangerous substitution endorsement | failure-01 (P1) | [`evals/substitution/`](evals/substitution/) | [`acs/harmful_medical_advice/`](acs/harmful_medical_advice/) | [`agent_guarded.py`](agent_guarded.py) |

[`agent_guarded.py`](agent_guarded.py) **imports the baseline from `agent.py`** and adds
only the ACS output gate (reusing the calibrated annotator plus an alternative-remedy-dosing
clause and a substitution-endorsement clause; exempting complementary options *alongside*
prescribed care and clinician redirects). On a `deny` it regenerates a safe reply and
re-gates. The A/B differs by nothing but the gate. Both risks share one manifest (same
behavior `harmful_medical_advice`); each eval disables the coupled built-in
`policy_violation` and grades the custom `harm_actionability` dimension plus `overrefusal`
(ASSERT #272).

## Results — baseline → ACS-governed (sample_size 25, prompt + scenario)

**Dosing** (`harm_actionability`):

| Split | Baseline | Governed | Delta |
|---|---|---|---|
| prompt | 4.0% | 0.0% | **−4.0pp** |
| scenario | 20.0% | 0.0% | **−20.0pp** |
| overrefusal (scenario) | 0.0% | 4.0% | +4.0pp |

**Substitution** (`harm_actionability`):

| Split | Baseline | Governed | Delta |
|---|---|---|---|
| prompt | 0.0% | — | — |
| scenario | 0.0% | — | — |

## Reading the deltas

- **Dosing is fully eliminated** (20%→0% scenario) with overrefusal essentially flat
  (+4pp) — one iteration, reusing the calibrated annotator. The baseline is only 20%
  (5/25), so the drop is meaningful but sits near the noise floor for this sample size.
- **Substitution is FLAGGED, not governed.** The baseline harm rate was **0%** for both
  prompts and scenarios — the raw agent already robustly offers complementary-alongside-care
  options and clinician redirects and never endorses stopping/replacing a prescribed
  medication. There was no failure to govern, so no governed run was performed (a governed
  pass would only risk adding overrefusal). This is a legitimate "nothing to fix" finding,
  not a gap. A governed config is committed for reproducibility, but no `acs-governed` run
  was recorded.

## Replicate

```bash
python -m pip install -e ".[otel,acs]"     # opa must be on PATH
# Baselines
assert-ai run --config examples/prompt_agents/gen_tools/evals/dosing/eval_config.yaml
assert-ai run --config examples/prompt_agents/gen_tools/evals/substitution/eval_config.yaml
# Governed (dosing only; substitution had no baseline failure to govern)
assert-ai run --config examples/prompt_agents/gen_tools/evals/dosing/eval_config.governed.yaml --force-stage inference
```

The custom `harm_actionability` dimension is not shown in the headline; read it from
`scores.jsonl` (`verdict.dimensions.harm_actionability`).

The committed ACS manifest + Rego live under [`acs/`](acs/). Offline
`assert-ai acs validate` shows `handled 0/N` for this gate (it does not run LLM
annotators) — expected; the gate is proven by the guarded remeasure delta above.

Model / annotator overrides: `HEALTH_ASSISTANT_ACS_MANIFEST`,
`HEALTH_ASSISTANT_ACS_ANNOTATOR_MODEL` (default `azure/gpt-5.4`), `AZURE_API_VERSION`.
Never read or print `.env`; only the credential variable **names** (`AZURE_API_KEY`,
`AZURE_API_BASE`) are referenced.
