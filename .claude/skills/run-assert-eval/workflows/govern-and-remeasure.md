# Workflow: govern-and-remeasure

Turn a measured ASSERT failure into a deployable **ACS** (Agent Control
Specification) policy, then re-run the same eval against the governed agent to
**prove the failure rate dropped** — the ACS delta. Log one row per domain in a
shareable ledger.

This is the governance half of the story and picks up where
`measure-clarity-failures.md` (Step 8) leaves off: Clarity discovered the risk,
ASSERT measured a baseline violation rate, and now ACS governs the failure at
runtime. It uses ASSERT's **native** ASSERT to ACS adapter (`assert-ai acs …`),
which derives the policy straight from the run's findings — no external `acs`
CLI and no separate checkout of the agent-governance-toolkit are needed.

> **Everything stays in-IDE.** ACS has no MCP server; the `assert-ai acs`
> subcommands are the in-IDE surface, driven the same way ASSERT already drives
> the rest of the pipeline. Do not hand the user off to a separate app.

## Why a callable target is required

ACS enforces at real tool-call boundaries (`pre_tool_call` / `post_tool_call`).
The `guard_target` input/output path alone does **not** enforce tool gates, so a
failure that lives at a tool call (for example, a high-risk action performed on
an unverified session) can only be governed by a real callable agent whose tool
functions are wrapped with `control.protect_tool`. A hosted-model Prompt Agent
target (simulated tools, gate in the system prompt) has nothing wrappable, so it
cannot demonstrate the delta. The reference implementation is
`examples/billing_support_agent/` (baseline `agent.py:chat_baseline`, governed
`agent_guarded.py:chat_governed`); use it as the pattern for a new domain.

## Preconditions (check, don't assume)

1. **A measured baseline run exists** for a callable target, reporting the
   `policy_violation` dimension (the Clarity to ASSERT configs already do). The
   adapter reads `scores.jsonl`, `inference_set.jsonl`, and `taxonomy.json` from
   `artifacts/results/<suite>/<run>/`.
2. **The ACS extra is installed**: `python -m pip install -e ".[acs]"` (pulls in
   the `agent-control-specification` SDK). Verify with `assert-ai acs --help`.
3. **`opa` is on PATH** (Open Policy Agent) — required to evaluate the generated
   Rego. Without it every verdict fails closed to `deny`.
4. **Provider creds exist** in `.env` for policy generation (`assert-ai acs
   generate` uses an LLM by default). NEVER read or print `.env`; reference
   variable NAMES only (AZURE_API_KEY, AZURE_API_BASE, …).

## Step 0 — Confirm a wrappable target

If the eval currently targets a hosted model, switch to a callable target first:
implement the agent as a Python tool loop with real tool functions (mirror the
declared toolset), emit OTel spans for `target.trace`, and expose two
entrypoints — an ungoverned baseline and an ACS-governed variant. See
`examples/billing_support_agent/agent.py` and `agent_guarded.py`.

## Step 1 — Baseline run (Run A)

Run the ungoverned callable target to establish the **ASSERT Baseline %**:

```
assert-ai run --config evals/<slug>/eval_config.baseline.yaml
```

Note the `suite` and `run` (e.g. `gpt54-baseline`). Report `policy_violation`
and `overrefusal` separately per `measure-clarity-failures.md` Step 7.

## Step 2 — Generate the ACS policy from the findings

```
assert-ai acs generate --suite <suite> --run gpt54-baseline \
  --out artifacts/acs/<suite>
```

Writes `manifest.yaml`, `policy/<slug>.rego`, and `report.md`. The generator
builds the guardrail from **structured findings signal only** (violated taxonomy
node, its permissibility, per-node rate, violated intervention points, violating
tool names) — raw transcript text is deliberately not sent to the model. For a
tool-gate failure the rules land at `pre_tool_call` / `post_tool_call`.

- Thresholds: `--min-rate` / `--min-count` to include only material findings.
- `--no-validate` to skip the built-in validation pass.

**Review the generated Rego and `report.md`** before trusting them (LLM-authored;
confirm the failure class is captured without over-denying permissible content).

## Step 3 — Validate the policy against known-bad findings

```
assert-ai acs validate --manifest artifacts/acs/<suite>/manifest.yaml \
  --suite <suite> --run gpt54-baseline
```

Reports how many known-bad examples the policy `handled` and `strongly blocked`.
Use `--require-block` in a gate to fail unless every known-bad example is
strongly blocked, or `--fail-on-allow` to fail if any is allowed.

## Step 4 — Governed run (Run B)

Point the ACS-governed callable at the generated manifest and re-run the **same**
eval spec. The reference agent resolves the manifest from `BILLING_ACS_MANIFEST`
or the default `artifacts/acs/<suite>/manifest.yaml`:

```
assert-ai run --config evals/<slug>/eval_config.governed.yaml
```

`eval_config.governed.yaml` is identical to the baseline except `run:`
(e.g. `gpt54-acs-governed`) and `target.callable` (the governed entrypoint).
On a `deny` verdict the guarded tool raises `AgentControlBlocked`; the agent
feeds the block back to the model and cannot complete the unverified action, so
`policy_violation` should drop. Watch `overrefusal` for over-denial.

## Step 5 — Compute the delta

```
assert-ai results compare <suite> gpt54-baseline gpt54-acs-governed
```

The **ACS Delta** is `baseline policy_violation % − governed policy_violation %`.
A meaningful drop with `overrefusal` roughly flat is the win condition.

## Step 6 — Export shareable artifacts

Generate a self-contained static HTML per run for SharePoint. Start the viewer
(`cd viewer && npm install && npm run dev`, port 5174), then fetch the export
route for each run:

```
/suite/<suite>/gpt54-baseline/export
/suite/<suite>/gpt54-acs-governed/export
```

Each returns a standalone `<suite>__<run>.html` (inline CSS, no server needed).
The user uploads both to SharePoint and pastes the SharePoint URLs into the
ledger. (Do not commit exported HTML — it is per-run output.)

## Step 7 — Append the ledger row

Append one row per domain to `governance-ledger.md` (gitignored per-target
output). Columns:

| Scenario | Clarity Failures | ASSERT artifacts | Baseline % | ACS Delta |
| --- | --- | --- | --- | --- |
| <domain / behavior> | <failure modes from `.clarity-protocol/failures/`> | <SharePoint links: baseline, governed> | <policy_violation %> | <baseline − governed> |

Keep `policy_violation` as the headline; note `overrefusal` movement alongside
the delta so a drop that came from over-denial is visible, not hidden.

## Step 8 — Close the loop in Clarity

Offer to write the outcome back into `.clarity-protocol/` via the Clarity MCP
tool `record_suggestion` (or `record_decision`): the failure mode is now governed
by an ACS policy at `artifacts/acs/<suite>/`, baseline `X%` dropped to `Y%`.

## Constraints (all mandatory)

- **Tool gates need a full ACS host.** Wrap high-risk tools with
  `control.protect_tool`; `guard_target` alone (input/output) will not move a
  tool-gate failure rate.
- **Guard both tool points.** A guarded high-risk tool must declare BOTH
  `pre_tool_call` AND `post_tool_call`, or it fails closed to `deny`.
- **Native adapter only.** Use `assert-ai acs generate` / `validate`; do not
  hand-drive an external `acs` CLI for this loop.
- **Review generated policy.** The Rego is LLM-authored from findings — read it
  and `report.md` before deploying.
- **Apples-to-apples A/B.** Baseline and governed runs differ only in `run:` and
  `target.callable`; everything else (behavior, stratify, judge, sample sizes)
  is identical.
- **Customer-safe terminology.** Reference credential env var NAMES only; never
  read/print/commit `.env`, `artifacts/`, or exported HTML.

## Worked example (billing identity-verification bypass)

1. Baseline: `assert-ai run --config
   evals/identity-verification-bypass/eval_config.baseline.yaml` →
   suite `billing-support-identity-verification-bypass`, run `gpt54-baseline`,
   `policy_violation` 40%.
2. Generate: `assert-ai acs generate --suite
   billing-support-identity-verification-bypass --run gpt54-baseline --out
   artifacts/acs/billing-support-identity-verification-bypass` → manifest + Rego
   guarding `change_plan` / `cancel_plan` / `issue_refund` /
   `update_payment_method` at `pre_tool_call`.
3. Validate: `assert-ai acs validate --manifest … --suite … --run gpt54-baseline`
   → known-bad examples strongly blocked.
4. Governed: `assert-ai run --config
   evals/identity-verification-bypass/eval_config.governed.yaml` → run
   `gpt54-acs-governed`, `policy_violation` 5%.
5. Delta: `assert-ai results compare billing-support-identity-verification-bypass
   gpt54-baseline gpt54-acs-governed` → 40% → 5% (ACS Delta 35 points),
   `overrefusal` flat.
6. Export both runs to HTML, upload to SharePoint, append the ledger row, and
   `record_suggestion` back to Clarity.
