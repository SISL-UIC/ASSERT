# Threat Model — Career Health Assessment Agent

Concise ranked summary. Full detail in `failures/failures.md`.

## Single point of failure

The **system prompt is the entire control surface** — there are no tools, no
retrieval, no code-level validation. Every guarantee (evidence-grounding, untrusted-
input isolation, bounded narrative, non-disclosure) rests on the model honoring the
prompt. Any elicitation that gets the model to deviate has nothing downstream to
catch it. This is why a runtime **ACS output gate** is the meaningful mitigation.

## Top risks

| # | Threat | Severity | One-line mitigation |
|---|--------|----------|---------------------|
| T1 | Fabricated / inferred career facts & scores | Critical | ACS output annotator: deny reply asserting facts/scores not in the CV; regenerate grounded |
| T2 | Prompt injection via untrusted CV_TEXT | Critical | ACS input/output annotator: deny reply that complied with an injected instruction |
| T3 | Unbounded readiness / personality claims | High | ACS output annotator: flag categorical readiness/personality claims or missing disclaimer |
| T4 | Hidden prompt / policy disclosure | High | ACS output annotator: deny system-prompt/policy disclosure |
| T5 | Human / empathy / credential misrepresentation | Medium-High | ACS output annotator: detect human/credential/empathy claims |

## Recommended first A/B

T1 and T2 — highest severity, most elicitable, and each maps cleanly to a semantic
output/input annotator gate proven by the guarded remeasure delta.
