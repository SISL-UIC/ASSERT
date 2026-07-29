# Architecture

## Components

- **LangGraph state machine** (`agent.py`). Nodes: `intent_classifier` →
  conditional → `research` → `itinerary_optimizer` → conditional → END, with a
  `clarification` branch. Model: `AzureChatOpenAI`, deployment from
  `ASSERT_AZURE_DEPLOYMENT` (default `gpt-4o-mini`).
- **Mock tools** (`examples/phoenix_auto_trace/_tools.py::simulate_tool`):
  `search_flights`, `search_hotels`, `check_weather`, `check_travel_advisories`,
  `validate_budget`. Deterministic canned JSON; they accept any args and do NOT
  enforce budget, grounding, or advisory completeness.
- **Callable target** `chat_sync(message, history=None)` with OpenTelemetry trace
  capture (`auto_trace.py`) so the judge can see tool calls and routing.

## Trust boundary

The three safety constraints (grounding, budget, advisories) are enforced **only
by system-prompt text**. The graph does not verify that the itinerary's details
came from a tool, that the total is within budget, or that advisories are
present/accurate. So the harm surface is the agent's **free-form final reply**: it
can assert fabricated specifics, claim an over-budget plan fits, or omit/invent
safety facts — none of which any tool result or graph edge prevents.

## Threat model

```mermaid
flowchart TD
    U[Traveler] -->|trip request / pressure| IC[intent_classifier]
    IC -->|book_trip + destination| R[research: 5 mock tools]
    IC -->|else| C[clarification]
    R --> IO[itinerary_optimizer]
    IO -->|final reply free-form| U
    subgraph Harm surface (prose, unenforced)
      F1[Fabricated flight/hotel/cost details]
      F2[Over-budget plan claimed affordable]
      F3[Omitted / invented visa-safety-health advisories]
    end
    IO -.-> F1
    IO -.-> F2
    IO -.-> F3
```

Top risks: fabricated itinerary details (Critical), budget overrun presented as
affordable (Critical), omitted/fabricated safety advisories (High). All are
free-form-text failures → an ACS **`output` (annotator) gate** is the enforcement
point, not a tool-argument gate.
