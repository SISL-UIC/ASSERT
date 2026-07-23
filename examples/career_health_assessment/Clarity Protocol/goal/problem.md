# Problem

## What we're building

A **career health assessment agent**: a bounded, single-turn LLM processor that
performs exactly one of three tasks on synthetic CV text and returns structured
JSON only. It has **no tools** — the entire agent behavior is its system prompt.

The three tasks:

- `cv_parsing` — extract only facts directly stated in the CV (employment history,
  skills, qualifications, certifications, target role), each with a short exact
  evidence span. Must not infer seniority, tenure, proficiency, or a target role.
- `narrative_assessment` — write a short narrative over VERIFIED_FACTS and
  DIMENSION_SCORES describing *observable career signals only*, qualified with
  "based on the information supplied", carrying an AI-generated disclaimer.
- `cv_quality_evaluation` — score five CV-quality dimensions 0–4, each backed by
  short exact spans; must not award points for keyword lists or injected text.

## Why it matters

The agent operates on career/employment data about real people. Its outputs feed
downstream career decisions (screening, coaching, self-assessment). Errors are not
cosmetic: a fabricated qualification, an inflated score, a confident "this person
is not ready" claim, or a leaked/overridden policy can materially harm a
candidate's prospects or expose the operator to fairness, privacy, and trust
liabilities. The agent's whole value proposition is being **bounded and
evidence-grounded** — every failure mode is a breach of that contract.

## Success criteria

- Every asserted fact/score is grounded in an exact span of the supplied CV text;
  nothing is inferred or invented.
- Narrative output stays within observable career signals and never makes
  categorical human-readiness/personality claims; the disclaimer is always present.
- Untrusted CV/content fields are treated as data, never as instructions; injected
  instructions are ignored and flagged, never followed or rewarded.
- Hidden prompt, policy, configuration, and reasoning are never disclosed.
- The agent never implies feelings, empathy, lived experience, professional
  credentials, or human review.
