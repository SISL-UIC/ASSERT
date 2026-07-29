# Summary

Custom-instrumented (manual OTel span) multi-agent travel planner
(`examples/travel_planner_neurosan/agent.py`, callable `chat(message,
history=None)`). A `coordinator` runs `intent_classifier` → `flight_searcher` /
`hotel_searcher` / `safety_advisor` → `itinerary_optimizer`, using five simulated
tools that return fixed Tokyo/Japan data for every destination. Three safety
constraints (grounding, budget adherence, advisory accuracy) live only in the
system prompt and are unenforced, so the model can be pressured across each.

Clarity discovery enumerated the failure modes in `failures/failures.md`. Top two
by priority (both P1 Critical): **fabricated trip details** and **budget overrun
presented as affordable** — both are semantic free-form-output failures, governed
by an ACS `output` LLM-annotator gate and proven by an ASSERT before/after delta.
