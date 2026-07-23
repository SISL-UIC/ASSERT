# Fabricated travel details (ungrounded flights, hotels, prices)

**Source:** mcp

`itinerary_optimizer` is instructed "Never fabricate details — use only information from prior messages," but nothing enforces grounding. When research returns thin or no tool results (e.g. the model didn't call a tool, or the tool result was sparse), the optimizer can invent flight numbers, hotel names, nightly rates, and totals that never appeared in any tool output. This is a semantic/content failure with no structural field to gate on — it needs an annotator-based check, not a tool gate. Failure chain: research under-calls tools -> optimizer fills gaps with plausible fabrication -> user receives a confident but ungrounded plan.

## Additional Context

Severity: High. Semantic failure — would require an output annotator gate rather than a deterministic tool gate.
