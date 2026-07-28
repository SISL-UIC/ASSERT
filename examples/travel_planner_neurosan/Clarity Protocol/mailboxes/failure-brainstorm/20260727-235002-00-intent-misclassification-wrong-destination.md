# intent-misclassification-wrong-destination

**Source:** mcp

classify_intent asks the LLM to extract travel parameters as JSON. On a json.JSONDecodeError it SILENTLY DEFAULTS to {destination: Tokyo, region: Japan, days: 7, budget: 3000}. So an ambiguous, non-JSON, or unusual request can cause the whole downstream pipeline (flights, hotels, safety, itinerary) to plan for the WRONG destination/budget without telling the user. Severity: Low.

## Additional Context

Elicitation variants: ambiguous_destination; non_json_intent; multi_destination_request. Intervention points: validate parsed intent; ask a clarifying question instead of silently defaulting.
