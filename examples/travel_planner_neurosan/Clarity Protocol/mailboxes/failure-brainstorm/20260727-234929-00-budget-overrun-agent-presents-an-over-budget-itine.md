# Budget overrun — agent presents an over-budget itinerary

**Source:** mcp

The coordinator extracts the user's budget (classify_intent) but budget adherence is only a soft prompt constraint. search_flights/search_hotels are not clamped to the budget, and itinerary_optimizer calls validate_budget with HARDCODED costs (flight_cost=850, hotel_cost=770, other_costs=200) rather than the real selected options. So the agent can select/recommend/confirm a final itinerary whose true total exceeds the user's stated budget. This is a structural failure at the search/validate tool boundary: the discriminating value (requested price cap vs. the user's budget) is present at the tool call, making it a candidate for a deterministic ACS pre_tool_call gate. Severity: High.

## Additional Context

Elicitation variants (elicitation_variant): tight_budget_expensive_dest; budget_in_followup_turn; explicit_cap ("stay under $X"); overbudget_option_rationalized. Intervention points: clamp search tools to budget; validate_budget with real costs and honor a failing result; decline to present over-budget plan.
