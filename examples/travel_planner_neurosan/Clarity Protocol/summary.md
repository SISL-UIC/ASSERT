# Summary

`travel_planner_neurosan` is a custom-instrumented (manual OpenTelemetry span)
multi-agent travel planner used to show that any custom orchestration can feed
ASSERT's judge. Its safety guarantees — budget adherence, grounding, surfacing
safety/visa/health advisories, injection resistance — are prompt-only and
unenforced, so it can commit the failures its prompt forbids.

Clarity discovery enumerated five failure modes: **budget overrun** (High, T1),
**fabricated details** (High, T2), **omitted safety advisories** (Medium, T3),
**prompt injection via tool content** (Medium, T4), and **silent wrong-destination
default** (Low, T5). Budget overrun is a structural tool-boundary failure (clean
ACS `pre_tool_call` gate); the rest are semantic reply-level failures
(output-annotator gates or, for T5, no clean gate).

The measurement plan: ASSERT baselines for the triaged risks, then an ACS runtime
guardrail on the highest-value structural risk (budget overrun) with a governed
re-run to prove the failure-rate delta.
