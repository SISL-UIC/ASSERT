# run-assert-eval skill

Take a developer from **"I don't know my risks"** to a **measured violation rate
per risk** — without leaving the coding assistant. Risk discovery is owned by
**Clarity** (microsoft/clarity-agent); measurement is owned by **ASSERT**
(responsibleai/ASSERT). This skill wires the two together.

## Files

| File | Purpose |
| --- | --- |
| `SKILL.md` | Claude Code skill entry (the canonical instructions). |
| `../../.github/prompts/run-assert-eval.prompt.md` | GitHub Copilot mirror. |
| `../../.cursor/rules/assert.mdc` | Cursor mirror. |
| `workflows/measure-clarity-failures.md` | The 8-step measurement workflow (parse → triage → configs → run → report → close loop). |
| `clarity_intake.py` | Dependency-free parser: Clarity failure docs → ASSERT candidate behaviors. |
| `tests/` | Pytest suite + real Clarity fixtures for the parser. |
| `SETUP-CHECKLIST.md` | One-time in-IDE MCP setup + end-to-end verification. |

Keep the three skill surfaces (`SKILL.md`, the Copilot prompt, the Cursor rule)
methodologically aligned when changing the flow.

## Architecture

1. **Discovery (Clarity, shipped):** the Clarity **MCP server** exposes tools —
   `run_clarity`, `write_protocol_document`, `record_failure`, `record_suggestion`,
   and others. `run_clarity` returns Clarity's real process guide inlined; the host
   agent conducts the clarifying conversation and persists findings. See
   `SETUP-CHECKLIST.md` to wire it up.
2. **Handoff (files, not JSON):** Clarity writes `.clarity-protocol/`. The
   measurement side reads `failures/failures.md` (index) and `failure-NN-*.md`
   (individual docs). Those files are the **source of truth**; the parser's JSON is
   a disposable cache.
3. **Measurement (this skill):** `clarity_intake.py` turns failure docs into
   candidate behaviors; `workflows/measure-clarity-failures.md` runs a **mandatory
   human triage gate**, generates **one atomic `eval_config.yaml` per selected
   failure**, runs them sequentially, and reports one behavior per column.

## The parser (`clarity_intake.py`)

```
python .claude/skills/run-assert-eval/clarity_intake.py .clarity-protocol
```

Per failure mode it emits a `CandidateBehavior`:
`{name, description, severity, priority, source_doc, candidate_dimensions,
multi_behavior, suggested_splits, warnings}`.

- **Severity → priority**: Critical→P1, High→P2, Medium→P3, Low→P4. Ranges (e.g.
  `Medium–Critical`) collapse to the **maximum** severity.
- **Dimensions**: the doc's **Variants** list → an `elicitation_variant` stratify
  dimension (highest value — each variant is a distinct route to the failure);
  **Failure Chain** conditions → an `interaction_condition` dimension.
- **Atomicity**: docs that bundle several independently testable behaviors are
  flagged `multi_behavior` with `suggested_splits` so triage can surface the split.
- **Tolerant**: unknown severity labels or missing headers degrade to a **flagged**
  candidate (`warnings` populated) — never a crash, never a silent drop.

Run the tests:

```
python -m pytest .claude/skills/run-assert-eval/tests/test_clarity_intake.py
```

## Worked example (one P1)

1. User: *"measure the risks Clarity found for my support bot."*
2. `.clarity-protocol/failures/failures.md` exists → the parser produces candidates.
   Top one is **`user_disengagement`** (P1) with an `elicitation_variant` dimension
   of 7 variants.
3. **Triage gate**: the skill lists candidates P1→P3 and asks which to measure. User
   picks **"P1s only"** → just `user_disengagement`.
4. The skill **asks the user for `sample_size`** (recommends `25`; `10` = quick
   look, `50`+ = tightest), then generates `evals/user-disengagement/eval_config.yaml`:
   `behavior.description` from the doc Summary, `test_set.stratify.dimensions`
   includes `elicitation_variant`, `test_set.prompt.sample_size` set to the user's
   choice (same for `scenario`),
   `judge.dimensions` = `policy_violation` + `overrefusal`.
5. **Confirm** → `assert-ai run` → results table: one `user_disengagement` column,
   `policy_violation` X% and `overrefusal` Y% (reported separately), 3–5 cited cases.
6. The skill offers `record_suggestion` back to Clarity: *"user_disengagement now has
   a measured baseline at evals/user-disengagement/."*

## Guarantees the skill enforces

- One atomic behavior per config — never bundle.
- The triage gate and the pre-run confirmation are **human** decisions; declining
  writes nothing and runs nothing.
- `.clarity-protocol/` files are authoritative; derived JSON is a cache.
- Discovery goes through Clarity's real MCP tools — no plain-language fallback, no
  shelling out to a `clarity cli` process, no separate app.
- Never read/print/commit `.env`, credential values, or `artifacts/`.
