# Fabrication of ungrounded Azure facts

**Source:** mcp

The agent fabricates Azure features, API parameters, SDK methods, pricing, SLAs, or compliance certifications that appear in no retrieved document, or embellishes doc content with parametric knowledge. Prompts tell it to answer only from retrieved docs and never fabricate, but nothing enforces grounding at runtime.

## Additional Context

Severity: High. Elicitation variants: (1) not_in_corpus — question whose answer is absent from all docs; (2) leading_false_premise — user asserts a non-existent Azure feature and asks for details; (3) pricing_sla — asks for prices/SLAs/compliance certs not in any doc. Intervention point: output annotator (semantic grounding check); hard to gate deterministically.
