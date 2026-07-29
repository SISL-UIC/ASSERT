# Budget-overrun: typed tool-boundary gate vs. semantic output annotator (A/B)

Proof-of-concept converting the `budget-overrun` governance from a **semantic
`output` annotator gate** (`../budget-overrun/`, conditioned on
`budget_overrun_classifier`) to a **deterministic `post_tool_call` typed gate**
that reads the `validate_budget` tool's computed `within_budget` bool.

## Why this is possible

"Over budget" is not a prose judgment — the `validate_budget` tool already
computes it: `{"total": N, "budget": B, "within_budget": total <= budget,
"remaining": B - N}`. So the gate keys on that typed field at the tool boundary
(the same shape as `bank_manager_feature.rego`'s `risk_tier` / `grounded` gates
and `azure_doc_qa` internal-doc-disclosure), instead of asking an LLM to judge
the final reply.

## Files

| File | Role |
|---|---|
| `policy/travel_budget_overrun_typed.rego` | Deterministic gate on `within_budget == false`. No annotator. |
| `manifest.yaml` | Declares `pre`/`post_tool_call` on the `validate_budget` result; **no `annotators:` block**. |
| `../../agent_guarded_budget_typed.py` | Runtime half. Enforces via `control.protect_tool` (same contract as billing); on a tool-confirmed overage, does **deterministic** remediation stating the real numbers — no LLM judge, no blanket fallback. |
| `../../evals/budget-overrun/eval_config.typed.yaml` | Governed config, differs from `eval_config.governed.yaml` only in `run:` + `target.callable`. |

## A/B results (sample_size 25 prompt + 25 scenario; judge azure/gpt-5.4)

| Run | prompt `budget_overrun` | scenario `budget_overrun` | prompt `overrefusal` | scenario `overrefusal` |
|---|---|---|---|---|
| baseline (ungoverned) | 8% | 12% | 20% | 60% |
| annotator `output` gate | 0% | 8% | 8% | **80%** (+20pp) |
| **typed `post_tool_call` gate** | 0% | **4%** | 16% | **60%** (0pp) |

**Headline:** the typed gate eliminates the annotator's **+20pp scenario
overrefusal tax** (held at the baseline 60% vs the annotator's 80%) *while cutting
the bad event further* (scenario 4% vs 8%).

**Overrefusal decomposition** (govern-and-remeasure Step 5a): of the 8 cases that
flipped `overrefusal` false→true vs baseline under the typed gate, **0** carried
the gate's remediation text — i.e. every flip is baseline-agent stochastic
variance from re-running inference, not caused by the gate. The typed gate's own
overrefusal contribution is ~0.

## Offline validation (the annotator gate can't do this)

The typed policy needs no annotator runtime, so it is exercised deterministically
by `opa eval` / `assert-ai acs validate`:

- over-budget result (`within_budget:false`) → `deny reason=budget_overrun`
- in-budget result (`within_budget:true`) → `allow`
- any other tool → `allow`

The semantic `output` gate shows "handled 0/N" offline because no classifier runs.

## Reproduce

```
# governed typed run (reuses the baseline test_set cache for a clean join)
assert-ai run --config examples/travel_planner_langgraph/evals/budget-overrun/eval_config.typed.yaml --force-stage inference
```
