# travel_planner_neurosan — Clarity → ASSERT → ACS → remeasure

A custom-instrumented (manual OpenTelemetry span) multi-agent travel planner, used
as a self-contained worked example of the full ASSERT governance loop: **Clarity**
discovers the risks, **ASSERT** measures a baseline, **ACS** governs the failure at
runtime, and ASSERT re-measures to prove the delta. No agent framework — just
OpenTelemetry spans that ASSERT's judge understands.

```
coordinator → intent_classifier → flight_searcher / hotel_searcher / safety_advisor
                                → itinerary_optimizer
```

Tools are simulated (`examples/phoenix_auto_trace/_tools.py`). The safety-relevant
guarantees (budget adherence, grounding) live only in prompts, so the agent can
commit the failures its prompt forbids.

## Risks evaluated

Clarity discovery (see `Clarity Protocol/failures/failures.md`) enumerated five
failure modes; two P2/High risks were triaged for measurement:

| Risk | Gate type | Where it's enforced |
|---|---|---|
| **Budget overrun** — presents an over-budget itinerary | Structural (deterministic) | `pre_tool_call` on `validate_budget` |
| **Fabricated details** — ungrounded flights/hotels/prices | Semantic (LLM annotator) | `output` grounding gate |

Each risk is one atomic eval. The built-in `policy_violation` is disabled and a
custom, node-independent bad-event dimension is graded, keeping `overrefusal`
separate. The governed config is byte-identical to the baseline except `run:` and
`target.callable`, so the cached `systematize` + `test_set` are reused for a true
A/B (both governed runs logged *"Reused artifact v0001"*).

Run config: `sample_size 25` (prompt + scenario), `max_turns 6`, target model
`azure/gpt-4o-mini`, judge `azure/gpt-5.4`, annotator `azure/gpt-5.4-mini`.

## Results — the ACS deltas

### Budget overrun (structural `pre_tool_call` gate) — clean win

| Dimension | Baseline | Governed | Delta |
|---|---|---|---|
| `budget_overrun` (prompt) | 12.5% | 4.0% | **−8.5pp** |
| `budget_overrun` (scenario) | 25.0% | 16.0% | **−9.0pp** |
| `overrefusal` (prompt) | 0.0% | 0.0% | flat |
| `overrefusal` (scenario) | 29.2% | 32.0% | +2.8pp (noise) |

The "select an over-budget flight/hotel as a plan component" category dropped
**33.3% → 0%**. Over-budget plans are blocked at the `validate_budget` boundary
with `overrefusal` essentially flat — declining a genuinely infeasible over-budget
trip is not overrefusal. The gate injects the trusted session `budget` and a
cheapest-plan cost floor that scales with trip length
(`agent_guarded.py::_cost_floor`), so it fires only when even the cheapest plan
exceeds the budget. Offline `assert-ai acs validate` confirms the deterministic
`deny`.

### Fabricated details (semantic `output` annotator gate) — large drop, availability cost

| Dimension | Baseline | Governed | Delta |
|---|---|---|---|
| `fabricated_details` (prompt) | 32.0% | 0.0% | **−32.0pp** |
| `fabricated_details` (scenario) | 91.7% | 32.0% | **−59.7pp** |
| `overrefusal` (prompt) | 0.0% | 16.0% | +16.0pp |
| `overrefusal` (scenario) | 29.2% | 72.0% | +42.8pp |

The grounding annotator (strict prompt, `regen` fallback) cut fabrication
dramatically — a 91.7% → 32% collapse on multi-turn scenarios and 32% → 0% on
single-turn prompts — at a real availability cost. A decomposition of the
newly-over-refused rows (governed `overrefusal=true`, baseline `false`) found the
rise is essentially all **ACS-caused** (the gate's regenerate remediation is
present), not baseline variance. The cost is inherent to this agent: its mock
tools return generic/mismatched data (e.g. always `LAX → <dest>` flights, fixed
Tokyo hotels for every city), so for an obscure destination the honestly-grounded
answer is often a partial decline the judge scores as `overrefusal`. This is the
documented strict-grounding tension (`workflows/govern-and-remeasure.md`, Step 5a).

> **Scenario fabrication is high-variance.** Two runs of this same governed
> remediation scored scenario `fabricated_details` at 13.6% and 32.0% (overrefusal
> stayed ~72%). These cases sit right on the judge's *mismatched-tool-data*
> boundary — the annotator treats a tool-returned specific as grounded, but the
> judge treats presenting a Tokyo hotel as a Monterrey option as fabrication — so
> cases flip run-to-run. Sophistication in the remediation (surgical redaction,
> judge-tier annotator, context-aware general guidance) was measured and did **not**
> beat this simple `regen`; the genuine fix is the agent's tools returning
> destination-appropriate data (a product change, outside a pure ACS A/B), not more
> gate tuning. To rebalance availability, switch the fallback
> (`NEUROSAN_ACS_FALLBACK_MODE=blunt|regen`).

*Rates are computed on scored rows; a small number of rows were dropped as target
errors (transient Azure connection errors, plus a now-fixed null-budget crash in
`classify_intent` when the intent LLM omitted the budget).*

## Layout

```
agent.py                     # shared baseline (manual-OTel pipeline, run_pipeline)
agent_guarded.py             # budget structural gate (validate_budget pre_tool_call)
agent_guarded_output.py      # fabrication semantic gate (output annotator + regen)
Clarity Protocol/            # the Clarity risk-discovery protocol for this domain
evals/<risk>/eval_config.yaml            # baseline
evals/<risk>/eval_config.governed.yaml   # governed (only run + target.callable differ)
acs/<risk>/manifest.yaml + policy/*.rego # reviewed, committed ACS policy
```

## Reproduce

```bash
pip install -e ".[otel,acs]"          # plus opa on PATH
# Budget (structural)
assert-ai run --config examples/travel_planner_neurosan/evals/budget-overrun/eval_config.yaml
assert-ai acs validate --manifest examples/travel_planner_neurosan/acs/budget-overrun/manifest.yaml \
  --suite travel-neurosan-budget-overrun --run baseline
assert-ai run --config examples/travel_planner_neurosan/evals/budget-overrun/eval_config.governed.yaml
assert-ai results compare travel-neurosan-budget-overrun baseline acs-governed --metric budget_overrun
# Fabrication (semantic)
assert-ai run --config examples/travel_planner_neurosan/evals/fabricated-details/eval_config.yaml
assert-ai run --config examples/travel_planner_neurosan/evals/fabricated-details/eval_config.governed.yaml
assert-ai results compare travel-neurosan-fabricated-details baseline acs-governed --metric fabricated_details
```
