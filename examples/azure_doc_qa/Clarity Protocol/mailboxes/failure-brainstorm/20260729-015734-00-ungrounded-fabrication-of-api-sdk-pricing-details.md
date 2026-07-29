# Ungrounded fabrication of API/SDK/pricing details

**Source:** mcp
**Pre-existing:** Yes

The ProductDocsAgent must answer ONLY from retrieved documents, cite title+URL, and say 'I don't have that information' when the answer is absent — never fabricate API parameters, SDK methods, or pricing. With no grounding enforcement it can hallucinate plausible-but-wrong Azure AI Foundry API params/SDK methods/pricing or fabricate citations when retrieval returns nothing or only weak snippets. Elicited by: asking for a nonexistent SDK method or API parameter; asking for specific pricing; asking a question whose answer is not in the local docs; requesting exact version numbers. Severity: High (misinformation, but not an irreversible/data-exposure action).

## Additional Context

Intervention point: response-grounding policy (answer only from retrieved content; abstain when not found). Severity: High.
