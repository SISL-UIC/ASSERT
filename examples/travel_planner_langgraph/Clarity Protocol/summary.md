# Summary

The travel-planning assistant (LangGraph, `examples/travel_planner_langgraph`)
plans trips by routing a request through an `intent_classifier`, a tool-calling
`research` node (flights, hotels, weather, advisories, budget), and an
`itinerary_optimizer` that writes the final plan. Its three safety promises —
never fabricate details, keep the plan within budget, and surface visa/safety/
health advisories — live only in the system prompt, so the model can be pressured
across each one. Because the harm shows up in the agent's free-form reply (not in
a tool argument), the natural governance point is an ACS `output` annotator gate
that judges the reply and, on a violation, regenerates a grounded, in-budget
answer and re-gates it.
