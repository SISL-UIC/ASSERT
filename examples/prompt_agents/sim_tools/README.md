# Health Assistant (simulated-tools Prompt Agent) — Clarity → ASSERT → ACS → ASSERT

A self-contained replication package that evaluates and governs the **simulated-tools**
health-assistant Prompt Agent. It runs the full loop: discover risks with **Clarity**,
measure a **baseline** with ASSERT, govern the failures with **ACS**, and **re-measure**
to prove the delta.

## The agent

The source of truth is
[`../health_assistant_simulated_tools.yaml`](../health_assistant_simulated_tools.yaml) — a
**Prompt Agent** target (hosted model + system prompt + a **fixed tool schema** whose
results are produced by an LLM simulator). A Prompt Agent cannot be governed in place, so
[`agent.py`](agent.py) **materializes** it as a callable:

- Same model + params as the YAML target (`azure/gpt-5.4-mini`, temperature 1.0).
- `SYSTEM_PROMPT` copied **byte-for-byte** from `target.system_prompt` (asserted in code).
- Same fixed toolset ([`../../agents/health_assistant_tools.yaml`](../../agents/health_assistant_tools.yaml):
  `lookup_medication`, `check_drug_interactions`, `assess_dosage`, `get_patient_profile`),
  with the same LLM simulator producing tool results, run in a real tool-call loop.
- A multi-turn `chat(message, history=None)` signature so scenario cases replay correctly.

The A/B is run on `target.callable`, **not** the YAML target. The YAML is the *spec*; the
callable is the baseline.

## Risks evaluated

Clarity discovered the failure modes from the system prompt + tool schema (see
[`Clarity Protocol/failures/failures.md`](Clarity%20Protocol/failures/failures.md)). The
tools raise the stakes — an `assess_dosage`/`lookup_medication` number can be presented as
a vetted patient-specific dose, and a `check_drug_interactions` result spun into "safe to
take together." But the harm is still the **prose** the model writes after the call, which
a pre/post-tool-call rule cannot see, so each gate is a **semantic ACS `output`
annotator**. Autonomous triage selected the top two:

| Risk | Clarity | Eval | ACS policy | Governed target |
|---|---|---|---|---|
| Tool-laundered actionable dosage | failure-01 (P1) | [`evals/dosage/`](evals/dosage/) | [`acs/harmful_medical_advice/`](acs/harmful_medical_advice/) | [`agent_guarded.py`](agent_guarded.py) |
| Unsafe interaction clearance / profile diagnosis | failure-02 (P1) | [`evals/interaction/`](evals/interaction/) | [`acs/harmful_medical_advice/`](acs/harmful_medical_advice/) | [`agent_guarded.py`](agent_guarded.py) |

[`agent_guarded.py`](agent_guarded.py) **imports the baseline from `agent.py`** and adds
only the ACS output gate (reusing the model-only annotator plus a **tool-laundered** clause
— *a number/flag returned by a tool does not license a case-applied dose, clearance, or
diagnosis* — and an interaction-clearance clause). On a `deny` it regenerates a safe reply
and re-gates. The A/B differs by nothing but the gate. Both risks share one manifest (same
behavior `harmful_medical_advice`); each eval disables the coupled built-in
`policy_violation` and grades the custom `harm_actionability` dimension plus `overrefusal`
(ASSERT #272).

## Results — baseline → ACS-governed (sample_size 25, prompt + scenario)

**Dosage** (`harm_actionability`):

| Split | Baseline | Governed | Delta |
|---|---|---|---|
| prompt | 0.0% | 4.0% | +4.0pp |
| scenario | 28.0% | 0.0% | **−28.0pp** |
| overrefusal (scenario) | 0.0% | 16.0% | +16.0pp |

**Interaction** (`harm_actionability`):

| Split | Baseline | Governed | Delta |
|---|---|---|---|
| prompt | 16.0% | 0.0% | **−16.0pp** |
| scenario | 52.0% | 16.0% | **−36.0pp** |
| overrefusal (scenario) | 0.0% | 4.0% | +4.0pp |

## Reading the deltas

- **Tool-laundered dosage is fully eliminated** on scenario (28%→0%) — the tool-laundering
  annotator clause is the winning fix: keeping the gate at the OUTPUT point and refusing to
  treat a tool's numeric field as a license for case-applied dosing. One iteration (reused
  the calibrated model-only annotator).
- **Interaction clearance drops 52%→16%.** The 16% residual is subtle multi-turn **soft
  practical reassurance / minimization** ("usually not a big issue", "better/safer fallback
  for you", hedged "most likely allergic") rather than explicit clearance — documented as
  the surviving band. Overrefusal stays essentially flat (+4pp).

## Replicate

```bash
python -m pip install -e ".[otel,acs]"     # opa must be on PATH
# Baselines
assert-ai run --config examples/prompt_agents/sim_tools/evals/dosage/eval_config.yaml
assert-ai run --config examples/prompt_agents/sim_tools/evals/interaction/eval_config.yaml
# Governed (reuses each baseline's cached test set — a true A/B)
assert-ai run --config examples/prompt_agents/sim_tools/evals/dosage/eval_config.governed.yaml --force-stage inference
assert-ai run --config examples/prompt_agents/sim_tools/evals/interaction/eval_config.governed.yaml --force-stage inference
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
