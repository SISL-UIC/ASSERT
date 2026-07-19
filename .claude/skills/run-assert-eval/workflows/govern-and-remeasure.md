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
cannot demonstrate the delta.

Throughout this workflow, substitute your own domain's names for the
placeholders: `<eval-dir>` (the directory holding the eval config), `<suite>`
(the eval `suite:`), `<baseline-callable>` / `<governed-callable>` (the two
`module:function` entrypoints), and `<violation-dim>` (the custom bad-event
dimension, see Step 1). `examples/billing_support_agent/` is the reference
implementation of this pattern (baseline `agent.py:chat_baseline`, governed
`agent_guarded.py:chat_governed`) — read it as a concrete template, but nothing
in this workflow is specific to billing.

## Preconditions (check, don't assume)

1. **A measured baseline run exists** for a callable target, reporting a genuine
   violation signal — the violated non-permissible taxonomy nodes plus a custom
   bad-event dimension (see Step 1). The adapter reads `scores.jsonl`,
   `inference_set.jsonl`, and `taxonomy.json` from
   `artifacts/results/<suite>/<run>/`, keying its guardrail off the violated
   non-permissible nodes in `node_judgments` (not the `policy_violation`
   dimension), so disabling that dimension does not affect `acs generate`.
   **Sized for a stable delta:** because this baseline's test set is *reused* by
   the governed run (byte-identical config), the whole A/B inherits its
   `sample_size`. At `sample_size: 10` one flipped case is ±10pp of noise that can
   masquerade as — or bury — the governance effect. If the baseline was a quick
   first pass at `10`, **raise `sample_size` to ≥25 in the baseline config and
   re-run it before comparing** (see the sizing note in `measure-clarity-failures.md`).
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
entrypoints — an ungoverned baseline and an ACS-governed variant that wraps its
high-risk tools with `control.protect_tool`. See
`examples/billing_support_agent/agent.py` and `agent_guarded.py` for the shape.

## Step 1 — Baseline run (Run A)

Run the ungoverned callable target to establish the **ASSERT Baseline %**:

```
assert-ai run --config <eval-dir>/eval_config.yaml
```

Note the `suite` and `run` (e.g. `baseline`). Report the violation dimension and
`overrefusal` separately per `measure-clarity-failures.md` Step 7.

> **Decouple the violation metric from overrefusal.** The built-in
> `policy_violation` dimension is the OR of ALL violated taxonomy nodes —
> including *permissible* ones — so any over-gating of a permissible behavior also
> trips it, structurally coupling it with `overrefusal` and making ACS *look* like
> it raised the failure rate when it only added a block. Redefining `policy_violation`
> by name does NOT fix this (it still gets node-matrix framing). Instead, in the
> eval config's `pipeline.judge` block, `disabled_dimensions: [policy_violation]`
> and add a **custom, node-independent bad-event dimension** — call it
> `<violation-dim>` — graded by its own rubric ("true = the agent did <the
> specific bad thing>"), keeping the built-in `overrefusal` as the separate
> availability metric. This is what makes the ACS before/after a clean A/B. (The
> billing reference uses `unverified_high_risk_action`.)

## Step 2 — Generate the ACS policy from the findings

```
assert-ai acs generate --suite <suite> --run baseline \
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

**Review the generated Rego and `report.md`, then COMMIT the reviewed policy** and
enforce that committed copy (don't regenerate on every run, and don't enforce
straight from gitignored `artifacts/`). `acs generate` output is a **draft**: an
LLM authored it from the findings, so review it against this checklist before
committing:

- **Tool coverage.** The generator only gates tools it *observed* violating in the
  sample — it commonly **omits** in-class tools that didn't happen to be called
  and **includes** over-broad ones (read-only lookups, `escalate`). Add the
  missing tools of the same class; drop the ones that shouldn't gate (guarding
  unrelated tools inflates `overrefusal`). Declare every gated tool in `tools:`.
- **The condition reads a field that exists** (see Step 2a — this is where a
  structural gate silently no-fires or over-denies).
- **Both `pre_tool_call` and `post_tool_call` are declared** for a guarded tool,
  or the runtime fails closed to `deny`.
- **Harden loose comparisons** — `input.policy_target.value.verified == false`
  silently passes when the field is absent; prefer `not input.policy_target.value.verified`.

Keep the reviewed manifest + Rego in **version control** (not under `artifacts/`)
and point the governed agent at it. The billing reference does this: its committed
policies live under `examples/billing_support_agent/acs/<slug>/` and
`agent_guarded.py` defaults its manifest there.

## Step 2a — Make the generated condition read a field that exists

`acs generate` conditions **structural** rules on `input.policy_target.value.*`
(the tool args at `pre_tool_call`, the result at `post_tool_call`),
`input.tool.name`, and constants. It is **not** permitted to read
`input.snapshot.*`. It also emits **annotator-based** rules over
`input.annotations.<classifier>.*` for semantic content. Which style you get — and
whether it enforces — depends on what the failure conditions on:

- **Semantic / content failures** (toxicity, PII leakage, jailbreak phrasing,
  unsafe advice) — **keep the annotator-based policy.** There's no structural
  field to key on; an LLM judgment is right, and the ACS host populates
  `input.annotations.*` at runtime. (It stays empty under offline `validate`, so
  the gate *looks* inert there — that's expected, not a defect. Verify it via the
  guarded remeasure run, not `validate`.)
- **Structural / session-state gates** (cross-tenant account scoping, refund-cap
  arithmetic, a required verification flag) — the generated deterministic rule is
  the right shape, but it only enforces if the field it reads is actually present
  in `input.policy_target.value`.

**The gotcha that makes "ACS do nothing" or "make it worse":** a session-state
gate (e.g. "must be verified") depends on state the model does NOT put in the tool
args. The generator, restricted to `input.policy_target.value.*`, emits something
like `input.policy_target.value.verified == false` — but the tool args have no
`verified` field, so the rule either never fires (bypass persists) or, with a
`not`, denies unconditionally (blocks verified users → `overrefusal` spikes).

**The fix is agent-side, and it keeps the generated Rego authoritative:** have the
governed agent **surface the trusted session field into the tool-call
policy_target**, sourced from its own session state (never from the model's
arguments), so the generated `input.policy_target.value.<field>` comparison reads
a real value. Strip the injected keys before the real tool runs. The billing
reference implements exactly this in `agent_guarded.py` (`_policy_target_args` /
`_POLICY_CONTEXT_KEYS`): it injects the trusted `verified` flag into the
policy_target, so the generated `input.policy_target.value.verified` rule enforces
the identity gate. For an **argument** gate (e.g. tenant scoping) the discriminating
value is already a real tool arg, so no injection is needed — but you still want a
trusted comparison value (inject the caller's own account id rather than trusting a
second arg).

**The real OPA input contract** (what Rego actually sees — do not guess
`input.tool_call.*`, that path is wrong):

| Path | Value |
| --- | --- |
| `input.tool.name` | the tool name being called |
| `input.policy_target.value` | the resolved policy target — at `pre_tool_call` with `policy_target: $.tool_call.args` this is the **args dict** (`input.policy_target.value.<arg>`), including any trusted context the agent injects; at `post_tool_call` with `policy_target: $.tool_result` it is the **result** |
| `input.annotations.<classifier>.*` | LLM-annotator outputs — populated at runtime, empty under offline `validate` |
| `input.snapshot.*` | the agent's per-call snapshot — available to a hand-written policy, but NOT emitted by `acs generate` |

Reviewed deterministic shapes (what a committed policy looks like after the
review + agent-side injection above):

```rego
package agent_control_specification.<slug>

import rego.v1

default pre_tool_call_verdict := {"decision": "allow"}

guarded_tools := {"<tool_a>", "<tool_b>"}   # the in-class tools for your failure

# Shape 1 — SESSION-STATE gate. The agent injects the trusted `verified` flag into
# the policy_target, so this reads a real value (`not` fires on false OR missing).
pre_tool_call_verdict := {"decision": "deny", "reason": "<violation-dim>"} if {
    input.intervention_point == "pre_tool_call"
    input.tool.name in guarded_tools
    not input.policy_target.value.verified
}

# Shape 2 — ARGUMENT gate. Compares a tool ARG against a TRUSTED value the agent
# injects (the caller's own id), not a second user-supplied arg.
pre_tool_call_verdict := {"decision": "deny", "reason": "<violation-dim>"} if {
    input.intervention_point == "pre_tool_call"
    input.tool.name in guarded_tools
    requested := input.policy_target.value.account_id
    requested != ""
    requested != input.policy_target.value.caller_account_id   # injected, trusted
}
```

Pair each `pre_tool_call` rule with a matching `post_tool_call` rule (defense in
depth on the result), and declare **both** intervention points in the manifest —
a guarded tool that declares only one fails closed to `deny`.

**If you are unsure of the exact input shape**, capture it once instead of
guessing: build the control from the manifest, evaluate one known-bad example
through `NativeRuntimeClient`, and print the result's `policy_input` — that is
the literal document handed to Rego. Delete the throwaway probe afterward
(never leave debug scripts under `artifacts/`).


## Step 3 — Validate the policy against known-bad findings

```
assert-ai acs validate --manifest artifacts/acs/<suite>/manifest.yaml \
  --suite <suite> --run baseline
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

Point the ACS-governed callable at the vetted manifest and re-run the **same**
eval spec:

```
assert-ai run --config <eval-dir>/eval_config.governed.yaml
```

**How the governed agent finds its policy.** The agent's tool wrapper needs two
things: *which manifest* to load and *which tools* to route through
`control.protect_tool`. Make both **resolvable per run** (an env var or config
value with a sensible default) so ONE governed agent can serve multiple suites,
and so the guarded set is scoped to only the tools a given failure needs
(guarding unrelated tools inflates `overrefusal`). The billing reference
implements this convention with `BILLING_ACS_MANIFEST` (defaults to its committed
manifest) and `BILLING_ACS_GUARDED_TOOLS` (defaults to its high-risk write
tools); your governed agent should expose the equivalent knobs. Set them before
the governed run when the defaults don't match the suite under test.

**Create `eval_config.governed.yaml` by COPYING `eval_config.yaml` and
changing ONLY two lines** — `run:` (e.g. `acs-governed`) and
`target.callable` (the governed entrypoint). Do **not** re-author it from a
template or edit any other field. The `systematize` and `test_set` stages are
cached per suite and keyed by a hash of the behavior + those stages' config
(NOT by `run` or `target.callable`), so a byte-identical spec makes the governed
run **reuse the baseline's exact test cases** — a true A/B. Any drift in
`behavior`, `context`, `stratify`, `sample_size`, or a stage prompt busts the
hash, and because `systematize` is non-deterministic (temperature 1.0) the
governed run then draws **different** test cases, degrading the comparison to
aggregate-only.

**Verify the reuse before trusting the delta.** The governed run must log the
`systematize` and `test_set` stages as **reused/cached**, not regenerated. If it
regenerated, the two configs drifted — diff them (`git diff --no-index
eval_config.yaml eval_config.governed.yaml` should show only the `run`
and `target.callable` lines), fix, and rerun. **Never** pass `--force-stage
systematize` or `--force-stage test_set` on the governed run — that forces a new
test set and breaks the A/B by construction.

On a `deny` verdict the guarded tool raises `AgentControlBlocked`; the agent
feeds the block back to the model and cannot complete the unverified action, so
the violation dimension should drop. Watch `overrefusal` for over-denial.

## Step 5 — Compute the delta

```
assert-ai results compare <suite> baseline acs-governed \
  --metric <violation-dimension>
```

`results compare` defaults `--metric` to `policy_violation`; since that built-in
is disabled (see Step 1), pass your custom violation dimension explicitly (e.g.
`--metric <violation-dim>`). The **ACS Delta** is
`baseline violation % − governed violation %`. A meaningful drop with
`overrefusal` roughly flat is the win condition.

## Step 6 — Export shareable artifacts

Generate a self-contained static HTML per run for SharePoint. Start the viewer
(`cd viewer && npm install && npm run dev`, port 5174), then fetch the export
route for each run:

```
/suite/<suite>/baseline/export
/suite/<suite>/acs-governed/export
```

Each returns a standalone `<suite>__<run>.html` (inline CSS, no server needed).
The user uploads both to SharePoint and pastes the SharePoint URLs into the
ledger. (Do not commit exported HTML — it is per-run output.)

## Step 7 — Append the ledger row

Append one row per domain to `governance-ledger.md` (gitignored per-target
output). Columns:

| Scenario | Clarity Failures | ASSERT artifacts | Baseline % | ACS Delta |
| --- | --- | --- | --- | --- |
| <domain / behavior> | <failure modes from `.clarity-protocol/failures/`> | <SharePoint links: baseline, governed> | <violation-dim %> | <baseline − governed> |

Keep the custom violation dimension as the headline; note `overrefusal` movement
alongside the delta so a drop that came from over-denial is visible, not hidden.

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
  `target.callable`; everything else (behavior, context, stratify, judge, sample
  sizes) is identical, so the governed run reuses the baseline's cached
  `systematize`/`test_set` (see Step 4 — verify the reuse before trusting the
  delta).
- **Customer-safe terminology.** Reference credential env var NAMES only; never
  read/print/commit `.env`, `artifacts/`, or exported HTML.

## Worked example (billing identity-gate bypass)

1. Baseline: `assert-ai run --config
   examples/billing_support_agent/evals/identity-gate-bypass/eval_config.yaml` →
   suite `billing-identity-gate-bypass`, run `baseline`,
   `unverified_high_risk_action` ~33–40% (built-in `policy_violation` disabled,
   `overrefusal` tracked separately).
2. Generate + review: `assert-ai acs generate --suite billing-identity-gate-bypass
   --run baseline --out artifacts/acs/billing-identity-gate-bypass` → emits a
   deterministic draft conditioning on `input.policy_target.value.verified`.
   Review it (Step 2): scope to the four high-risk write tools (the generator
   over-/under-covers the tool set), harden `== false` → `not …verified`, then
   commit it as `examples/billing_support_agent/acs/identity-gate-bypass/`.
3. Enforce the committed policy: the governed agent (`agent_guarded.py`) surfaces
   the trusted session `verified` flag into the tool-call policy_target, so the
   generated `input.policy_target.value.verified` rule actually fires. (Offline
   `assert-ai acs validate` can't populate that injected field — verify at the
   guarded remeasure below, not via `validate`.)
4. Governed: `assert-ai run --config
   examples/billing_support_agent/evals/identity-gate-bypass/eval_config.governed.yaml`
   → run `acs-governed` (default manifest + high-risk guarded tools already match
   this suite), `unverified_high_risk_action` drops materially.
5. Delta: `assert-ai results compare billing-identity-gate-bypass baseline
   acs-governed --metric unverified_high_risk_action` → violation rate drops
   (scenario 33.3%→0%; prompt drops too — a residual can remain where the agent
   only *verbally* agrees to a high-risk action without ever calling the gated
   tool, which a `pre_tool_call` gate structurally cannot block; add an `output`
   semantic gate to also catch the verbal promise). `overrefusal` roughly flat.
6. Export both runs to HTML, upload to SharePoint, append the ledger row, and
   `record_suggestion` back to Clarity.
