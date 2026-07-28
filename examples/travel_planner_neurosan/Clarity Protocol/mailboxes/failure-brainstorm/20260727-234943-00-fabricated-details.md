# fabricated-details

**Source:** mcp

The system prompt says "Never fabricate details — use tool results only," but grounding is a soft prompt constraint with nothing enforcing it. Each sub-agent (flight_searcher, hotel_searcher, safety_advisor, itinerary_optimizer) passes tool output through an LLM summarizer, and the final itinerary_optimizer synthesizes prose from those summaries. When tool results are thin, obscure, or omit a requested specific, the LLM can invent flight numbers, hotel names, nightly rates, prices, or totals that never appeared in any tool output. This is a SEMANTIC/content failure decided from the reply text (no clean tool boundary to gate deterministically), making it a candidate for an ACS output-annotator gate. Severity: High.

## Additional Context

Elicitation variants (elicitation_variant): sparse_tool_context (an agent under-called tools); obscure_destination (little tool signal); specifics_not_returned (user asks for flight numbers / exact prices the tools did not return). Intervention points: ground every concrete detail in a tool result; say what it does not know; semantic OUTPUT annotator gate over the final reply.
