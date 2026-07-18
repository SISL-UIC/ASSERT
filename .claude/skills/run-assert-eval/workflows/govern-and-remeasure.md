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
- `--model azure/<deployment>` (e.g. `azure/gpt-5.4`) so litellm uses the Azure
  path. `assert-ai acs` loads the project `.env` automatically (same as
  `assert-ai run`) — do NOT hand-export credentials into the shell.

**Review the generated Rego and `report.md`** before trusting them (LLM-authored;
confirm the failure class is captured without over-denying permissible content).

## Step 2a — Choose the right policy style for the failure

`assert-ai acs generate` emits an **annotator-based** Rego: it conditions on
`input.annotations.<classifier>.*` fields produced by LLM annotators at each tool
step. Which style you want depends on what the failure conditions on:

- **Semantic / content failures** (toxicity, PII leakage, jailbreak phrasing,
  unsafe advice) — **keep the annotator-based policy.** There's no structural
  field to key on; an LLM judgment is exactly right, and the ACS host populates
  `input.annotations.*` at runtime.
- **Structural / argument-based gates** (cross-tenant account scoping, refund-cap
  arithmetic, verification-state gate) — **prefer a deterministic Rego** that
  conditions on the tool arguments or session state. It's a plain comparison, so
  it validates reliably and enforces without an extra per-step model call.

Two caveats specific to annotator-based policies, so they aren't mistaken for
broken:

1. **Offline `validate` reports `handled 0/N`** — nothing populates
   `input.annotations.*` during `assert-ai acs validate`, so an argument-based
   gate *looks* inert even though it would fire at runtime. If the gate is really
   structural, that's the signal to switch to deterministic Rego (this is what
   sent Run 2 down a reverse-engineering path).
2. A per-tool-step LLM call adds latency and non-determinism — fine for semantic
   gates, wasteful for a gate that's just `account_id != caller`.

**The real OPA input contract** (what Rego actually sees — do not guess
`input.tool_call.*`, that path is wrong):

| Path | Value |
| --- | --- |
| `input.tool.name` | the tool name being called |
| `input.policy_target.value` | the resolved policy target — at `pre_tool_call` with `policy_target: $.tool_call.args` this is the **args dict** (`input.policy_target.value.account_id`); at `post_tool_call` with `policy_target: $.tool_result` it is the **result** (a string under offline `validate`, a dict at runtime) |
| `input.annotations.<classifier>.*` | LLM-annotator outputs — populated at runtime, empty under offline `validate` |
| snapshot fields | whatever the host passes in `_snapshot(state)` (e.g. `caller_account_id`, `verified`), surfaced per the manifest's snapshot wiring |

Deterministic template (cross-tenant account scoping — adapt the tool set and
condition for your failure):

```rego
package assert_guardrails

account_scoped_tools := {
    "get_account_profile", "get_invoices", "issue_refund",
    "change_plan", "cancel_plan", "update_payment_method",
}

# pre_tool_call: deny an account-scoped call whose account_id is not the caller.
deny contains msg if {
    input.tool.name in account_scoped_tools
    requested := input.policy_target.value.account_id
    requested != ""
    requested != "ACME-1001"   # the authenticated caller (or a snapshot field)
    msg := sprintf("cross-account access denied: %v != caller", [requested])
}
```

**If you are unsure of the exact input shape**, capture it once instead of
guessing: build the control from the manifest, evaluate one known-bad example
through `NativeRuntimeClient`, and print the result's `policy_input` — that is
the literal document handed to Rego. Delete the throwaway probe afterward
(never leave debug scripts under `artifacts/`).


## Step 3 — Validate the policy against known-bad findings

```
assert-ai acs validate --manifest artifacts/acs/<suite>/manifest.yaml \
  --suite <suite> --run gpt54-baseline
```

Reports how many known-bad examples the policy `handled` and `strongly blocked`.
Use `--require-block` in a gate to fail unless every known-bad example is
strongly blocked, or `--fail-on-allow` to fail if any is allowed.

**Offline `validate` only exercises deterministic rules.** It wires no annotator
dispatcher, so `input.annotations.*` is never populated and **annotator-based
rules cannot fire here** — they show up as `handled 0/N`. When the effective
policy conditions on annotators, `validate` prints a `Note:` saying so; that
`0/N` is **expected, not a defect**. Only a **deterministic** gate (on
`input.policy_target.value` / `input.tool.name`) is truly testable offline. An
annotator/semantic gate is validated **only** by the guarded remeasure run
(Step 4/5), where the ACS host runs the annotators and the violation rate should
drop. So: `--require-block`/`--fail-on-allow` are meaningful gates for
deterministic policies; for annotator policies, treat the remeasure delta as the
real pass/fail signal.

## Step 4 — Governed run (Run B)

Point the ACS-governed callable at the generated manifest and re-run the **same**
eval spec. The reference agent resolves the manifest from `BILLING_ACS_MANIFEST`
or the default `artifacts/acs/<suite>/manifest.yaml`:

```
assert-ai run --config evals/<slug>/eval_config.governed.yaml
```

**Create `eval_config.governed.yaml` by COPYING `eval_config.baseline.yaml` and
changing ONLY two lines** — `run:` (e.g. `gpt54-acs-governed`) and
`target.callable` (the governed entrypoint). Do **not** re-author it from a
template or edit any other field. The `systematize` and `test_set` stages are
cached per suite and keyed by a hash of the behavior + those stages' config
(NOT by `run` or `target.callable`), so a byte-identical spec makes the governed
run **reuse the baseline's exact test cases** — a true A/B. Any drift in
`behavior`, `stratify`, `sample_size`, or a stage prompt busts the hash, and
because `systematize` is non-deterministic (temperature 1.0) the governed run
then draws **different** test cases, degrading the comparison to aggregate-only.

**Verify the reuse before trusting the delta.** The governed run must log the
`systematize` and `test_set` stages as **reused/cached**, not regenerated. If it
regenerated, the two configs drifted — diff them (`git diff --no-index
eval_config.baseline.yaml eval_config.governed.yaml` should show only the `run`
and `target.callable` lines), fix, and rerun. **Never** pass `--force-stage
systematize` or `--force-stage test_set` on the governed run — that forces a new
test set and breaks the A/B by construction.

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
  is identical, so the governed run reuses the baseline's cached
  `systematize`/`test_set` (see Step 4 — verify the reuse before trusting the
  delta).
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
