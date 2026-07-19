# Workflow: measure-clarity-failures

Turn Clarity-discovered failure modes into measured ASSERT violation rates —
one atomic behavior at a time, with a human in the loop at every gate.

This workflow is the measurement half of the Clarity → ASSERT story. Discovery
is owned by the **Clarity MCP server** (`clarity-agent`, shipped by
microsoft/clarity-agent); measurement is owned by this skill. The handoff is
**files, not JSON**: Clarity writes `.clarity-protocol/failures/`, and this
workflow reads it.

> **Discovery is agent-driven, not scripted.** The Clarity MCP `run_clarity`
> tool returns the relevant process guide inlined as text; **you** (the host
> agent) ask the user the clarifying questions in chat and persist what you learn
> with `write_protocol_document` / `record_failure`. Do not reimplement Clarity's
> questioning and do not shell out to a separate app — drive its real MCP tools.

## Entry conditions

Trigger this workflow when the user asks to **measure / test / quantify** risks
or failures for their agent, model, or app.

1. **If `.clarity-protocol/failures/failures.md` exists** → go to **Step 1 (Parse)**.
2. **If it does not exist** → run discovery first:
   - Call the Clarity MCP tool **`run_clarity`**. Follow the inlined process
     guide's clarifying questions *with the user in chat*.
   - Persist findings via **`write_protocol_document`** and **`record_failure`**.
   - Continue until the failure-analysis process has produced
     `failures/failures.md`, then proceed to Step 1.
   - If the `clarity-agent` MCP tools are **not available** in this session, stop
     and point the user at the in-IDE setup checklist (`SETUP-CHECKLIST.md`):
     `clarity embed`, reload MCP servers, confirm `run_clarity` is callable. Do
     **not** substitute a plain-language risk guess — that produces low-signal evals.

## Step 1 — Parse

Run the intake parser (`clarity_intake.py`) on the protocol directory:

```
python .claude/skills/run-assert-eval/clarity_intake.py .clarity-protocol
```

It emits, per failure mode, a **candidate behavior**:
`{name, description, severity, priority, source_doc, candidate_dimensions,
multi_behavior, suggested_splits, warnings}`.

- `priority` maps `Critical→P1`, `High→P2`, `Medium→P3`, `Low→P4`. Severity
  **ranges collapse to the maximum** (e.g. `Medium–Critical → Critical → P1`).
- `candidate_dimensions` are mined from the doc's **Variants** (highest-value:
  the `elicitation_variant` dimension) and **Failure Chain** conditions
  (`interaction_condition`).
- `multi_behavior: true` + `suggested_splits` flags a doc that **bundles** several
  independently testable behaviors (see Step 4 atomicity).
- The JSON is a **disposable cache** — `.clarity-protocol/` remains the source of
  truth. Never treat the JSON as authoritative or commit it as such.

Parsing is tolerant: docs with unknown severity labels or missing headers arrive
**flagged** (`warnings` populated), never dropped. Surface those warnings during
triage so the user knows what needs manual attention.

## Step 2 — Mandatory human triage gate (never skip)

Clarity **intentionally over-produces** (whole-lifecycle threat modeling).
Auto-running every risk is a bug, not a feature.

Present the candidate list **sorted P1 → P3**, each row showing:

- name, priority, one-line summary
- any atomicity split (`suggested_splits`)
- any parse warnings

Ask the user **which to measure now**. Offer **"P1s only"** as the default
suggestion, plus named picks. **Do not generate or run anything until the user
answers.** Declining at this gate must result in **zero files written and zero
runs**.

## Step 3 — Confirm scope, then generate one config per selected behavior

For **each** selected behavior, produce its **own** `eval_config.yaml` under its
own directory: `evals/<failure-slug>/eval_config.yaml`. Never bundle.

Config generation, in order of preference:

1. **Domain template first.** Check the ASSERT `examples/` directory for a vetted
   config matching the risk type; copy it as the base and adapt.
2. **Otherwise** generate from the schema (or `assert-ai init --describe "<text>"`
   if the installed version accepts a description seed and output path — verify
   with `assert-ai init --help`).

Fill from the candidate behavior (real schema field names):

| Config field | Source |
| --- | --- |
| `behavior.name` | candidate `name` (short, specific) |
| `behavior.description` | candidate `description` (the doc **Summary**, tightened to a *testable* statement) |
| `context` | Clarity `summary.md` / `goal/requirements.md` / `solution/architecture.md` |
| `pipeline.test_set.stratify.dimensions` | `candidate_dimensions` — **include the `elicitation_variant` dimension** derived from the doc's Variants |
| `pipeline.test_set.prompt.sample_size` | **small for the first run (e.g. 10)** so results arrive fast |
| `pipeline.test_set.scenario.sample_size` | small for the first run (e.g. 10) |
| `pipeline.inference.target` | the target shape (see below) |
| `pipeline.judge.preset` + `dimensions` | keep the violation metric **and** `overrefusal` as **separate** dimensions (see the coupling note below) |

> **Built-in `policy_violation` couples with `overrefusal`.** The built-in
> `policy_violation` dimension is the logical-OR over ALL violated taxonomy nodes
> — including *permissible* ones — so over-gating a permissible behavior also trips
> it, and it can never be fully separate from `overrefusal`. For a plain baseline
> that's usually fine, but for a clean ACS before/after A/B (see
> `govern-and-remeasure.md`) `disabled_dimensions: [policy_violation]` and add a
> custom, node-independent bad-event dimension (e.g. `unverified_high_risk_action`)
> graded by its own rubric, keeping the built-in `overrefusal`.

> `stratify.dimensions` entries are `{name, description}`. Fold the parser's
> `values` list into each dimension's `description` (e.g. "Values: variant A;
> variant B; …") so the stratifier samples across the elicitation routes.

**Target shape:**
- Framework agent (LangGraph, CrewAI, …) with a Python entry function →
  `pipeline.inference.target.callable` **with** `target.trace` (so the judge can
  cite tool calls and routing). **The callable MUST accept a `history` parameter**
  (`def chat(message, history=None)`) — ASSERT detects multi-turn support by the
  presence of that parameter, and a history-less callable silently receives only
  the latest turn, breaking multi-turn scenario cases (prior verification/context
  is dropped, inflating both the violation and `overrefusal` rates).
- Hosted model + system prompt (+ optional tools) → `target.model` / `target.tools`.
- Pre-collected traces → `assert-ai judge-traces --traces <path> --config <path>`.

## Step 4 — Atomicity (enforce)

**One atomic behavior per `eval_config.yaml`.** Bundling makes `policy_violation`
a fuzzy logical-OR and masks per-behavior signal.

- A single Clarity failure mode is usually one behavior → one config.
- If a doc is flagged `multi_behavior` (e.g. failure-07 "operational **and**
  security risks" spanning cost overruns and prompt injection), **split** it into
  multiple candidates, name each specifically, and show the split in the triage
  list so the user chooses per split behavior.
- N selected behaviors → **N configs**, never one merged config.

## Step 5 — Confirm before running

For each generated config, show the user: `behavior.name`, `behavior.description`,
the stratify `dimensions`, the `target`, and the `judge` settings. Apply any
requested edits. **Run only on explicit go-ahead.**

## Step 6 — Run sequentially

```
assert-ai run --config evals/<slug>/eval_config.yaml
```

Run one at a time. Stream stage status (systematize → test_set → inference →
judge). If one run fails, **report it and continue** with the remaining configs.
Note each `suite`/`run` for the report.

## Step 7 — Report

One results table, **one behavior per column, one experiment per row**, with:

- `policy_violation` and `overrefusal` rates reported **separately** (two
  different problems).
- Cited failure examples pulled from the run artifacts
  (`assert-ai results status <suite> <run>`, then `scores.jsonl` for
  `verdict.dimension_justifications`). Do **not** trawl raw traces.
- For each behavior, note the **source Clarity doc** and its intervention points
  ("a fix would target: …").

Offer next steps: raise `sample_size`, add a dimension, apply an ACS guardrail at
the failing checkpoint, or **re-measure after a fix** to prove the rate dropped.

## Step 8 — Close the loop in Clarity

After a run, offer to write the outcome back into `.clarity-protocol/` via the
Clarity MCP tool **`record_suggestion`** (or **`record_decision`**): note that the
failure mode now has a **measured baseline** and where the eval lives
(`evals/<slug>/`). This keeps Clarity's staleness tracking aware of the eval.

## Constraints (all mandatory)

- **One atomic behavior per config.** Never bundle.
- **Triage gate + pre-run confirmation are human decisions.** Never auto-run all
  discovered risks. Declining writes nothing and runs nothing.
- **`.clarity-protocol/` files are the source of truth.** Parser JSON is a
  disposable cache, never authoritative.
- **Do not modify clarity-agent source.** Consume its MCP server as shipped; if a
  capability is missing, note it as an upstream proposal.
- **Do not edit inside the Clarity-managed `AGENTS.md` block.**
- **Tolerant parsing.** Unknown severity labels or headers degrade to flagged
  candidates — never crash, never silently drop.
- **Customer-safe terminology.** Reference credential env var **NAMES** only
  (AZURE_API_KEY, AZURE_API_BASE, OPENAI_API_KEY, GITHUB_TOKEN, ANTHROPIC_API_KEY,
  azure_ad_token) — never values. Never read/print/commit `.env` or `artifacts/`.

## Worked example (one P1)

1. User: "measure the risks Clarity found for my support bot."
2. `failures.md` exists → parse. Top candidate is **`user_disengagement`** (P1),
   with an `elicitation_variant` dimension of 7 variants (challenging disposition,
   wrong calibration, happy-path attachment, cultural aversion, verbosity, unused
   protocol, alert fatigue).
3. Triage: user picks **P1s only** → just `user_disengagement`.
4. Generate `evals/user-disengagement/eval_config.yaml`: `behavior.description`
   from the doc Summary, `stratify.dimensions` includes `elicitation_variant`
   (7 values folded into its description), `prompt.sample_size: 10`,
   `judge.dimensions` = `policy_violation` + `overrefusal`.
5. Confirm → `assert-ai run` → results table: one `user_disengagement` column,
   `policy_violation` X% and `overrefusal` Y%, 3–5 cited examples.
6. Offer `record_suggestion` back to Clarity: "user_disengagement now has a
   measured baseline at evals/user-disengagement/."
