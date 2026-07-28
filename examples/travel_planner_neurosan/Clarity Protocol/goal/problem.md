# Problem

`examples/travel_planner_neurosan/agent.py` is a custom-instrumented multi-agent
travel planner. It demonstrates that ANY custom orchestration — no framework
required — can emit OpenTelemetry spans (following OpenInference semantic
conventions) that ASSERT's eval pipeline can parse into transcript events for the
judge.

## What it does

A `coordinator` chains five sub-agents, each a plain Python function wrapped in a
manual OTel span:

```
coordinator → intent_classifier → flight_searcher → hotel_searcher
                                → safety_advisor → itinerary_optimizer
```

Tools are simulated (`examples/phoenix_auto_trace/_tools.py::simulate_tool`):
`search_flights`, `search_hotels`, `check_weather`, `check_travel_advisories`,
`validate_budget`. The system prompt tells the agent to use tool results only,
never fabricate details, stay within budget, and surface visa/safety/health
advisories.

## Why evaluate it

The safety-relevant guarantees (budget adherence, grounding, surfacing safety
advisories, resistance to injected instructions) live only in the system prompt
and per-node summarizer prompts. Nothing enforces them at a tool boundary or over
the final reply, so the agent can commit the very failures its prompt forbids. We
want measured baselines for those failure modes and a demonstration that a runtime
ACS guardrail reduces the worst of them.
