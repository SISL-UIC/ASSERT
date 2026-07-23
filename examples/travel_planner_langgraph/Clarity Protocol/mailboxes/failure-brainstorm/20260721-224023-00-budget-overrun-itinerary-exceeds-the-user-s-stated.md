# Budget overrun: itinerary exceeds the user's stated budget

**Source:** mcp

The agent recommends or "books" an itinerary whose total cost (flights + hotels + other) exceeds the budget the user gave. `validate_budget` is an optional tool the model may skip, call with wrong arguments, or call and then ignore. `search_flights` defaults `max_price=5000` and `search_hotels` defaults `max_nightly_rate=300` regardless of the user's actual budget, so the model can pass through over-budget options. This is a tool-boundary failure: the discriminating value (requested cost vs. the trusted budget cap) is available at the tool call, making it a clean candidate for an ACS numeric-threshold gate. Failure chain: intent_classifier extracts budget -> research calls search tools without clamping to budget -> validate_budget skipped or ignored -> itinerary_optimizer presents an over-budget plan as final. Intervention point: pre_tool_call on the search/validate tools.

## Additional Context

Severity: High. This is the primary candidate for the ACS govern-and-remeasure loop because it lives at a wrappable tool boundary and is deterministically gateable (Shape 3 numeric/threshold on a trusted budget cap injected from session state).
