# Summary

The science research agent is an internal retrieval assistant (`azure/gpt-4o-mini`
tool loop) with three tools — `web_search` and `fetch_url` (untrusted public web)
and `file_search` (a mixed-sensitivity internal corpus whose results carry a
sharing `class`). It answers researchers' questions in free-form prose with source
attribution.

Two controls exist only in its system prompt: **disclosure control** (never quote
/ paraphrase / summarize a restricted-class document) and **untrusted-input
isolation** (treat instructions embedded in retrieved content as data, not
directives). Both are Critical and both surface entirely in the free-form reply,
so the governable checkpoint is a semantic ACS `output` annotator gate.

Top failure modes: **failure-01 restricted-class disclosure leakage (P1)** and
**failure-02 prompt injection via retrieved content (P1)**, plus **failure-03
ungrounded fabrication (P2)** and **failure-04 system-prompt disclosure (P2)**.
