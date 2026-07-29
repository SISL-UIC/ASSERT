# Decision: Govern top-2 P1 failures with semantic ACS output gates

**Status:** decided

**Date:** 2026-07-29


## Context

Clarity enumerated four failure modes for the neurosan travel planner; the two P1 Criticals (fabricated trip details, budget overrun presented as affordable) were triaged for ASSERT measurement and ACS governance. Both are semantic free-form-output failures (the harm is in the prose the itinerary_optimizer writes, not a tool argument).


## Decision

Govern the top-2 P1 failures with an ACS semantic `output` LLM-annotator gate (Shape 4), one atomic eval per risk, and prove the fix via an ASSERT baseline→governed remeasure delta.


## Rationale

There is no structural tool-argument field that decides either failure (fabrication and false-affordability are judgments over the final reply), so a deterministic pre_tool_call gate cannot decide them; an LLM annotator over the reply + tool evidence is the correct gate. Offline acs validate cannot run annotators, so the delta is the proof.


## Alternatives Considered

Structural pre_tool_call gate on validate_budget (rejected: the itinerary_optimizer hard-codes the cost inputs, so the tool args don't reflect the presented plan, and fabrication has no tool-arg signal at all).


## Consequences

Governed agent must supply the runtime annotator dispatcher and regenerate-and-re-gate on deny; strict grounding may raise overrefusal on multi-turn scenarios (documented tradeoff).
