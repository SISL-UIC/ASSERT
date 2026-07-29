# Summary

A **model-only** health-assistant Prompt Agent (`azure/gpt-4o-mini` + a fixed
system prompt, **no tools**) that answers general wellness, medication-info, and
scheduling questions. Its prompt hard-forbids two things — **dosage
recommendations** and **diagnoses** — and requires redirecting specific medical
questions to a professional.

Because the agent has no tools, every safety failure surfaces in its free-form
reply, so each governable checkpoint is the **assistant output**. Clarity
discovery surfaced four failure modes; the two Critical (P1) ones are:

1. **Actionable unsafe dosage / medication advice** (failure-01) — the model
   emits a concrete, self-administerable dose / titration / drug-combination.
2. **Unsafe diagnosis / emergency mismanagement** (failure-02) — the model gives
   a definitive diagnosis, a false all-clear, or misses a red-flag emergency.

Both are governed by a semantic ACS `output` annotator gate (Shape 4): an LLM
annotator flags the harmful reply and the agent regenerates a safe, still-helpful
answer and re-gates it — measured baseline → governed to prove the delta.
