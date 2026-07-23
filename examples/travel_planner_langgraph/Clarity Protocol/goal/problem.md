# Problem

## What we are evaluating

`examples/travel_planner_langgraph/agent.py` — a multi-node LangGraph travel
planner. It classifies user intent, researches a trip with five tools, and emits
a final itinerary. The evaluation goal is to surface the ways this agent can
behave unsafely or incorrectly, so those risks can be measured with ASSERT and
(where they live at a tool boundary) governed with ACS.

## The agent, concretely

- **Graph:** `intent_classifier → research → itinerary_optimizer`, with a
  `clarification` branch when intent isn't `book_trip` or the destination is
  missing.
- **Tools (mock):** `search_flights(destination, max_price=5000)`,
  `search_hotels(city, max_nightly_rate=300)`, `check_weather(city)`,
  `check_travel_advisories(region)`, `validate_budget(flight_cost, hotel_cost,
  other_costs, budget=5000)`.
- **State:** carries `intent`, `destination`, `budget` extracted as JSON by the
  classifier.
- **Guardrails present in prompts only:** `itinerary_optimizer` is told "Never
  fabricate details"; `research` is told to "Use ALL available tools." Nothing
  enforces these at runtime.

## Why this matters

The agent hands users travel plans that carry a real budget commitment and real
safety implications (visa/health/region advisories). The docstring mentions a
`safety_advisor` node that does not actually exist in the graph, so safety
coverage depends entirely on the model choosing to call `check_travel_advisories`.
Budget adherence depends entirely on the model choosing to call — and honor —
`validate_budget`. Both are soft, prompt-level constraints with no runtime gate.

## Success criteria for this evaluation

1. Enumerate the agent's failure modes via structured brainstorming.
2. Let the human triage which to measure now.
3. Produce a measured ASSERT baseline per selected failure.
4. For a tool-boundary failure, govern it with ACS and prove the violation rate
   drops on a re-measure (the ACS delta).
