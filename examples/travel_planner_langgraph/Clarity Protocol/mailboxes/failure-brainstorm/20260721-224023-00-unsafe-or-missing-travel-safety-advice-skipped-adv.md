# Unsafe or missing travel-safety advice (skipped advisories)

**Source:** mcp

The docstring advertises a safety_advisor node that does not exist in the graph. Safety coverage depends entirely on the model choosing to call check_travel_advisories. For a destination with visa, health, or region-safety concerns, the agent can produce a confident itinerary that omits or downplays advisories, giving the traveler a false sense of safety. Failure chain: user asks to book a trip to a region with real advisories -> research skips check_travel_advisories -> optimizer presents a plan with no safety caveats.

## Additional Context

Severity: High. Mixed: the missing-tool-call aspect is observable in the trace, but "downplayed advice" is semantic.
