# Summary

The science research agent (`examples/science_research_agent/agent.py`) is a
retrieval agent with three tools — public web search, URL fetch, and an internal
file index whose results carry a sharing `class`. It runs a bounded LiteLLM tool
loop behind a system prompt that encodes the disclosure rules and trust model.

It sits on a confidentiality boundary: `file_search` can return restricted-class
documents (`restricted_results`, `partner_notes`, `contacts`, `private_notes`)
that must never reach the reply, while retrieved web/document bodies are an
untrusted injection channel. The consequential risks are (1) leaking
restricted-class content, (2) complying with instructions embedded in retrieved
content, (3) ungrounded/fabricated attribution, and (4) the trade-off failure of
collateral over-refusal. Harm for the confidentiality risks is decided in the
model's free-form reply, so the natural governance point is the agent output.
