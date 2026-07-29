# Decision: Govern top-2 P1 failures with semantic ACS output gates

**Status:** decided

**Date:** 2026-07-29


## Context

Clarity discovery on the LangGraph travel-planner (agent.py) surfaced 4 failures; the two P1 Criticals — fabricated_trip_details (failure-01) and budget_overrun_presented_as_affordable (failure-02) — were measured with ASSERT. Baselines confirmed real failure surfaces: fabrication 44% prompt / 75% scenario; budget-overrun 8% / 12%. Both harms live in the agent's free-form reply, not in a tool argument, so a structural pre_tool_call gate cannot see them.


## Decision

Govern both risks with a semantic ACS `output` intervention point conditioned on an LLM annotator (fabrication_classifier / budget_overrun_classifier, azure/gpt-5.4-mini), with grounded regeneration + re-gate on deny (agent_guarded.py chat_governed). Committed policies at examples/travel_planner_langgraph/acs/<risk>/{manifest.yaml,policy/*.rego}.


## Rationale

Governed remeasure (true A/B, reused test set): fabrication 44%→0% prompt, 75%→4% scenario; budget-overrun 8%→0% prompt, 12%→8% scenario. Single-turn overrefusal also improved (16%→0%, 20%→8%) because regeneration grounds the reply instead of refusing. A structural gate was rejected because neither failure emits a gate-able tool argument.


## Alternatives Considered

Structural pre_tool_call argument gate (rejected: harm is free-form prose, not a tool arg). Blunt refusal fallback without regeneration (rejected: trades bad-event for overrefusal). Broad input-side gate on 'exact number' prompts (rejected: pre-empts legitimate planning, inflates overrefusal).


## Consequences

Scenario overrefusal rises (58.3%→76%, 60%→80%) — the known multi-turn tradeoff off already-high baselines. Offline `acs validate` cannot exercise annotator gates (handled 0/N is expected); gates are proven only by the governed remeasure delta. The gate fails OPEN on annotator error to avoid hard-blocking.
