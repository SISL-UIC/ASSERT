# Budget-overrun: typed tool-boundary gate vs. semantic output annotator (A/B)

Proof-of-concept converting the neuro-san `budget-overrun` governance from a
**semantic `output` annotator gate** (`../budget-overrun/`, conditioned on
`budget_overrun_classifier`) to a **deterministic `post_tool_call` typed gate**
that reads the `validate_budget` tool's computed `within_budget` bool.

## Why this is possible

The neuro-san pipeline calls the same `validate_budget` tool as the LangGraph
travel planner. That tool returns `{"total": N, "budget": B, "within_budget":
total <= budget, "remaining": B - N}`. The typed gate therefore keys on that
field at the tool boundary instead of asking an LLM annotator to judge final
prose.

## Files

| File | Role |
|---|---|
| `policy/travel_neurosan_budget_overrun_typed.rego` | Deterministic gate on `within_budget == false`. No annotator. |
| `manifest.yaml` | Declares `pre_tool_call` + `post_tool_call` on `validate_budget`; **no `annotators:` block**. |
| `../../agent_guarded_budget_typed.py` | Runtime enforcement via `control.protect_tool`; on a tool-confirmed overage, remediation states the real total/budget/overage. |
| `../../evals/budget-overrun/eval_config.typed.yaml` | Governed config, differs from `eval_config.governed.yaml` only in `run:` + `target.callable`. |

## A/B results (sample_size 25 prompt + 25 scenario; judge azure/gpt-5.4)

Joined table below uses the 47 test cases scored in all three runs (25 prompt +
22 scenario). Three scenario rows had target-runtime errors in at least one
governed run and are excluded from the joined percentages.

| Run | prompt `budget_overrun` | scenario `budget_overrun` | prompt `overrefusal` | scenario `overrefusal` |
|---|---:|---:|---:|---:|
| baseline (ungoverned) | 4.0% | 22.7% | 0.0% | 13.6% |
| annotator `output` gate | 4.0% | 13.6% | 12.0% | 72.7% |
| **typed `post_tool_call` gate** | **0.0%** | **9.1%** | **0.0%** | **50.0%** |

**Headline:** the typed gate improves the bad-event rate relative to both
baseline and the semantic annotator (scenario 22.7% → 13.6% → 9.1%; prompt 4.0%
→ 4.0% → 0.0%). It also removes the annotator's prompt overrefusal, but still
adds scenario overrefusal versus baseline because neuro-san calls
`validate_budget` on most scenario turns, including follow-up turns where the user
asks for formatting, arithmetic, or language edits.

## Overrefusal decomposition

For baseline→typed `overrefusal` flips, 9 cases flipped false→true. All 9 had a
typed ACS intervention (the final answer differed from the raw
`itinerary_optimizer` answer and the `validate_budget` result had
`within_budget:false`). **0 flips were baseline variance with no ACS
intervention.**

That differs from the LangGraph pilot: here the tool signal is present and
reliable, but the neuro-san pipeline hard-codes a `validate_budget` call on every
turn. The deterministic gate correctly fires on the typed result; the remaining
availability cost is therefore caused by applying the budget remediation to too
many scenario follow-up turns, not by annotator stochasticity.

## Offline validation

The typed policy is deterministic and was exercised offline:

- `opa eval` over-budget result (`within_budget:false`) → `deny reason=budget_overrun`
- `opa eval` in-budget result (`within_budget:true`) → `allow`
- `opa eval` `pre_tool_call` → `allow`
- ACS SDK `control.protect_tool("validate_budget", execute)` → deny/allow paths both exercised with base Python 3.12.

## Reproduce

```powershell
& "C:\Users\t-alexngo\AppData\Local\Programs\Python\Python312-arm64\Scripts\assert-ai.exe" run --config examples\travel_planner_neurosan\evals\budget-overrun\eval_config.typed.yaml --force-stage inference
```
