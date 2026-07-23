---
name: run-assert-eval
description: >
  Run an ASSERT evaluation starting from Clarity-discovered risks. Use when the
  user wants to evaluate, test, or check an AI agent, LLM app, or model against
  requirements/policies (e.g. "evaluate my agent for budget violations", "test
  that the support bot never gives legal advice"). Drives the real Clarity MCP
  tools (run_clarity) in-IDE to discover risks, then generates one atomic
  eval_config.yaml per selected risk, runs the pipeline, and reports
  pass/violation rates with trace-cited failure examples.
---

# Run an ASSERT evaluation

## When to use

The user wants evidence of how their agent or model actually behaves. Not for
fixing the agent — this skill finds and reports failures.

This skill has two entry modes:

- **Run mode** — no usable results exist yet. Risks come from **Clarity** (Steps 1-2):
  either an existing `.clarity-protocol/` directory or a fresh discovery run driven
  through the **Clarity MCP server** (`run_clarity`), in-IDE. Then turn each selected
  risk into an atomic config, run the pipeline (Steps 3-5), and report (Step 6).
- **Results Q&A mode** — judged artifacts already exist under
  `artifacts/results/<suite>/<run>/` and the user asks a *question* about them
  ("what are the highlights?", "top 3 examples of the worst failure mode?", "why
  did case X fail?"). Skip to Step 6 and answer THAT question from the artifacts —
  do not re-run, and do not fall back to the full canned report unless asked.

### Clarity is required for Run mode — no non-Clarity fallback

Risks that seed an eval MUST come from Clarity (an existing `.clarity-protocol/`
or a fresh discovery run via the Clarity MCP `run_clarity` tool). Do **not**
substitute a plain-language description, and do **not** imitate Clarity's
questioning from your own head — instead, `run_clarity` returns Clarity's real
process guide inlined, and you follow *that* to conduct the clarifying loop. An
eval spec that skips Clarity's captured risks produces inaccurate, low-signal
results. If the Clarity MCP tools are not available, STOP and help the user set
them up (see `SETUP-CHECKLIST.md`) rather than proceeding.

### Copilot vs. the local viewer

Copilot is for *answering questions* and *synthesis* — direct answers,
failure-mode clustering, cited examples, next actions — with no clicking. The
bundled local viewer is for *visual exploration* — forest plots, baseline compare,
facet grouping, and stepping through a transcript with the judge's citations
highlighted. Answer in chat when the user asks "what / why / which"; hand off to
the viewer (Step 7) when they want to *see*, *read a full transcript*, *compare
runs*, or *watch a live run*.

## Preconditions (check, don't assume)

1. **ASSERT installed**: `assert-ai --help` succeeds. If not, guide install:
   ```
   python -m pip install -e ".[otel,langgraph]"
   ```

2. **Clarity MCP server available** (required for Run mode): the `clarity-agent`
   MCP tools (`run_clarity`, `write_protocol_document`, `record_failure`,
   `record_suggestion`, …) are callable in this session. Clarity is the
   risk-discovery engine — the skill drives its real MCP tools, it does not
   reimplement it. If the tools are missing, the server is not wired up yet: guide
   the user through `SETUP-CHECKLIST.md` (install `clarity-agent` with the `[mcp]`
   extra, run `clarity embed .` to generate `.vscode/mcp.json`, reload MCP servers)
   and confirm the LLM provider is configured (`clarity doctor` — Clarity supports
   GitHub Copilot, Anthropic, OpenAI, Azure AI, and Gemini).

   If the Clarity MCP tools cannot be made available, STOP and help the user
   resolve it. Do not proceed with a non-Clarity path.

3. **Provider creds exist** in `.env`. NEVER read or print `.env`. If a run fails
   with an auth error, tell the user which variable NAMES are required
   (AZURE_API_KEY, AZURE_API_BASE, OPENAI_API_KEY, GITHUB_TOKEN, ANTHROPIC_API_KEY,
   etc.) — never their values.

## Steps

### 1. Discover risks with Clarity (required front door)

Risks come from Clarity's real engine, driven through the **Clarity MCP server** —
never from a plain-language guess and never by imitating Clarity from your own head.

- **If a `.clarity-protocol/` directory already exists** in the workspace, use it
  directly as the risk source — skip straight to reading its output below.
- **Otherwise run discovery via the Clarity MCP tools:**
  1. Call **`run_clarity`**. It returns Clarity's real process guide inlined as text.
  2. Follow that guide to ask the user the clarifying questions **in chat** — this
     is Clarity's genuine multi-perspective flow, surfaced through you as the host
     agent (Copilot agent mode supports MCP *tools*, so drive the loop yourself
     rather than expecting a separate chat UI).
  3. Persist what you learn with **`write_protocol_document`** and
     **`record_failure`**. Continue until the failure-analysis process has written
     `.clarity-protocol/failures/failures.md`.

Read Clarity's output to enumerate risks:

- **`.clarity-protocol/failures/failures.md`** — the failure modes, causal chains,
  and management plans. Each distinct failure mode is one candidate ASSERT behavior.
- **`.clarity-protocol/summary.md`, `goal/requirements.md`, `solution/architecture.md`**
  — target/context for the eval's `context` field.

**For the full measurement path** — parse → triage → one atomic config per selected
failure → sequential runs → report → close the loop — follow
`workflows/measure-clarity-failures.md`. Use the intake parser
(`clarity_intake.py`) to convert `failures.md` into candidate behaviors with
severity→priority mapping and variant-derived stratify dimensions.

Clarity records severity/management-plan signal (the parser maps Critical→P1,
High→P2, Medium→P3, ranges→max). Order and annotate by what Clarity actually
captured; do not fabricate priorities.

### 2. Triage — choose which risks to measure now

Clarity intentionally over-produces (whole-lifecycle threat modeling). Do NOT
auto-generate an eval for every failure mode. Surface the enumerated list (ordered
by Clarity's severity signal) and ask the user which to measure now (e.g.
"top-severity only?", or named picks). Carry only the selected risks forward.

### 3. Turn each selected risk into an atomic config

ASSERT performs best with **one atomic behavior per eval**. Never bundle multiple
risks into one config — bundling makes `policy_violation` a fuzzy logical-OR and
hides per-behavior signal.

- **1 selected risk** → generate one config and run once.
- **N selected risks** → generate N atomic `eval_config.yaml` files and run them
  sequentially, one per behavior.

For each selected risk, map the Clarity failure mode → `behavior.name` +
`behavior.description`, and use its context for `context`:

```
assert-ai init --model <litellm-model> --describe "<failure mode + how it arises + target context>" --non-interactive -o eval_config.yaml
```

- **If the user has an existing config** to extend, use `--from <path>` instead of
  generating from scratch.
- After generation, show the user the generated `behavior.description`, `context`,
  and `pipeline.judge` dimensions. Confirm before running.

### 4. Identify the target shape

Help the user set the right target in the config:

- **Framework agent** (LangGraph, CrewAI, etc.) with a Python entry function:
  use `target.callable` WITH `target.trace` so the judge can cite tool calls and routing.
- **Hosted model** with a system prompt and optional tools:
  use `target.model` and `target.tools`.
- **Pre-collected traces** (no live inference needed):
  use `assert-ai judge-traces --traces <path> --config <path>`.

### 5. Run the pipeline

```
assert-ai run --config eval_config.yaml --output json
```

This is long-running (systematize -> test_set -> inference -> judge). Stream status
to the user as each stage completes. For N configs, run them sequentially and track
each `suite`/`run`.

- To re-run from a specific stage: `--force-stage <stage>`
- Note the `suite` and `run` names from the config for Step 6.

### 6. Report results — never collapse to one number

**Read only structured artifacts.** Aggregate from the pre-computed, schema'd files —
never trawl raw Phoenix/OpenTelemetry traces to reconstruct an answer (that bulk,
unguided trace-reading is exactly what the viewer's evidence drawer is for). Reading
the `inference_set.jsonl` row for a *specific case the judge already cited* is fine;
bulk trace trawling is not.

1. **Headline rates**: run `assert-ai results status <suite> <run>` for per-dimension
   flagged rates (split into prompt and scenario). Report the violation dimension and
   `overrefusal` SEPARATELY — they are two different problems. Note: the built-in
   `policy_violation` ORs over ALL violated taxonomy nodes (permissible included), so
   it couples with `overrefusal`; for a clean ACS A/B disable it and grade a custom
   bad-event dimension (see `workflows/govern-and-remeasure.md`).

2. **Top failing cases**: read `scores.jsonl` from `artifacts/results/<suite>/<run>/`.
   For each dimension with failures, pull 3-5 representative cases with:
   - The test case description (what was tested)
   - `verdict.dimensions` — which dimensions failed
   - `verdict.dimension_justifications` — the judge's rationale with cited evidence
   - `verdict.node_judgments` — which behavior categories were violated, with reasoning

3. **Cost and timing**: read `metrics.json` for token usage and elapsed time per stage.
   This file contains cost metadata only, not score roll-ups.

For **Results Q&A mode**, answer the user's specific question from these same artifacts
(e.g. rank dimensions by flagged rate for "top failure mode", then quote
`dimension_justifications` for the cited examples). Don't emit the full template unless asked.

### 7. Hand off to the local viewer

After reporting, point the user to the bundled viewer for anything visual or
self-directed — it went through extensive design iteration and owns the exploration
surface Copilot should not replicate:

```
cd viewer && npm install && npm run dev   # then open http://localhost:5174
```

Select the suite and run for forest plots, per-dimension breakdowns, facet grouping,
the permissible vs. not-permissible policy-violation split (a viewer-only breakdown),
and a transcript drawer with the judge's `[N]` citations highlighted on the cited turns.
Suggest it specifically when the user wants to:

- **read a full transcript** or **see the trace** for a case → viewer evidence drawer
- **compare against a baseline** → viewer compare view (or `assert-ai results compare <suite> <runA> <runB>`)
- **watch a run in progress** → viewer live run monitor (`manifest.json`-driven)

See `docs/guides/use-local-viewer.md` for the full layout.

### 8. Govern the failure and re-measure (ACS)

When a run surfaces `policy_violation` failures and the user wants to **fix and
prove it**, don't stop at prompt-tweaking. Generate a deployable **ACS** (Agent
Control Specification) policy from the findings and re-run the same eval against
the governed agent to show the failure rate dropped — the ACS delta. This uses
ASSERT's native `assert-ai acs generate` / `validate` adapter (no external `acs`
CLI). It requires a **callable** target whose high-risk tools can be wrapped
(`control.protect_tool`); a hosted-model Prompt Agent target has nothing
wrappable. Follow `workflows/govern-and-remeasure.md` for the full loop
(baseline → `acs generate` → `acs validate` → governed run → `results compare` →
export each run to standalone HTML → append `governance-ledger.md`). Reference implementation:
`examples/billing_support_agent/` (baseline + governed entrypoints).

## Output format

Present a short summary with this structure:

**Headline metrics** (per dimension):
- Policy violation rate: X% (N/M cases)
- Overrefusal rate: X% (N/M cases)
- [any custom dimensions]: X%

**Top failing cases** (3-5 per dimension):
For each failure:
- Requirement cited: [behavior category from taxonomy]
- Action cited: [specific turn or tool call from judge rationale]
- Judge rationale: [verbatim from dimension_justifications]

**Suggested next step**: one concrete action (e.g. "tighten the system prompt
around X behavior", "add a dimension for Y", or **govern the failure with ACS and
re-measure to prove the rate dropped** — see Step 8 and
`workflows/govern-and-remeasure.md`).

## Guardrails

- **Clarity is the required risk source** — for Run mode, risks come from Clarity (existing `.clarity-protocol/` or a fresh discovery run via the `run_clarity` MCP tool). Never substitute a plain-language guess or imitate Clarity's questioning from your own head; if the MCP tools can't be made available, stop and help fix it (`SETUP-CHECKLIST.md`).
- **Drive the real Clarity MCP tools in-IDE** — use `run_clarity` / `write_protocol_document` / `record_failure` for discovery and `record_suggestion` to close the loop; never hand the user off to a separate Clarity app and never shell out to a `clarity cli` process.
- **Close the loop** — after a run, offer `record_suggestion` (or `record_decision`) back into `.clarity-protocol/` noting the failure mode now has a measured baseline and where the eval lives, so Clarity's staleness tracking stays aware of it.
- **Govern with ACS, don't just prompt-tweak** — to fix and *prove* it, generate an ACS policy from the findings (`assert-ai acs generate`), **review and commit** it (scope the gated tools, tighten conditions), and re-run the same eval against the governed callable to show the delta; needs a wrappable callable target (`workflows/govern-and-remeasure.md`). Whenever a gate needs a value the model doesn't put in the tool args — a trusted session flag (verification), a trusted comparison value (the caller's own id), a trusted numeric cap, or a running total / prior-call fact — the governed agent must surface that scalar from its **session state** into the tool-call **policy_target** so the generated `input.policy_target.value.*` rule actually fires. ACS evaluates each call in isolation, so multi-call constraints (running totals, ordering, rate limits) are handled by that same injection, not by encoding history in Rego. Free-form content failures (unsafe advice, PII in prose, a verbal-only high-risk promise) and inbound prompt-injection instead use an **annotator-based** gate at the `output`/`input` point, proven by the remeasure delta since offline `validate` can't run annotators. Never hand-drive an external `acs` CLI for this loop.
- **Organize by domain across runs** — this workflow is run repeatedly for different agents/domains, so keep materials namespaced. (a) Prefix every eval **suite name** with a domain slug (`<domain>-<risk>`, e.g. `billing-cross-customer-data-exposure`, `science-<risk>`); because `artifacts/results/<suite>/` and `artifacts/acs/<suite>/` are keyed by suite, domain-prefixed names coexist without overwriting. (b) **`.clarity-protocol/` is single-domain scratch** at the repo root (not namespaced) — the next `run_clarity` overwrites the prior domain's `failures/`, `goal/`, `solution/`. Before starting discovery for a *new* domain, **move the finished protocol into that domain's example folder** as `examples/<domain>/Clarity Protocol/`, colocated with the agent it describes. (c) **Keep each example self-contained so anyone can replicate the run from its folder alone** — see "Per-example replication package" below.
- **Per-example replication package** — every domain you evaluate must end up as a single self-contained folder under `examples/<domain>/` containing everything needed to reproduce its Clarity → ASSERT → ACS → ASSERT run, laid out identically across domains:
  - `agent.py` (+ any real runtime deps it imports, e.g. `tools.py` / `mock_tools.py`) — the shared baseline.
  - `agent_guarded*.py` — the governed target(s); each **imports** the baseline from `agent.py` and adds only the ACS enforcement, so the A/B differs by nothing but the gate.
  - `README.md` — what the agent does, the risks evaluated, and the baseline → governed deltas.
  - `Clarity Protocol/` — the colocated Clarity risk-discovery protocol for this domain.
  - `evals/<risk>/eval_config.yaml` + `evals/<risk>/eval_config.governed.yaml` — one baseline/governed pair per risk (governed is a byte-identical copy differing only in `run:` and `target.callable`).
  - `acs/<risk>/manifest.yaml` + `acs/<risk>/policy/*.rego` — the reviewed, committed policy the governed agent enforces.
  `examples/billing_support_agent/` and `examples/travel_planner_langgraph/` are the canonical shape; align every other domain to it.
- **One atomic behavior per config** — split N selected risks into N configs run sequentially; never bundle.
- **Triage before running** — never auto-generate an eval for every Clarity failure mode; ask which to measure now.
- **Don't invent metrics** — only report what's in the artifacts.
- **Don't trawl raw traces to answer questions** — answer from `results status`, `scores.jsonl`, and `metrics.json`; hand off to the viewer for visual trace/transcript exploration.
- **Hand off, don't reimplement the viewer** — for visual drill-down, baseline compare, or live monitoring, point to the local viewer rather than reproducing it in chat.
- **Don't read, print, or commit** `.env`, credential values, `artifacts/`, traces, `.venv`, or logs.
- **Reference env variable NAMES only** (AZURE_API_KEY, AZURE_API_BASE, azure_ad_token, GITHUB_TOKEN, ANTHROPIC_API_KEY) — never values.
- **Don't commit artifacts** to the repository.
