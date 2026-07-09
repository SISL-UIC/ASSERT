# Beat 3 in CI — ASSERT evals as an AI-safety regression gate

This directory shows the third beat of the demo — **the control plane, enforced in
CI** — as a pull-request gate: an eval regression fails the build the same way a unit
test does.

## Where this really ships: a standalone repo (not this clone)

The realistic way to adopt this is **not** to fork ASSERT and run the gate from inside
a clone. Real teams keep their agent in **their own repository** and add ASSERT as a
dependency. So the full, runnable version of this beat lives in a standalone repo:

**→ [`responsibleai/assert-ci-banking-demo`](https://github.com/responsibleai/assert-ci-banking-demo)**
&nbsp;*(publishing shortly — the canonical CI shipping vehicle)*

There, the banking agent is its own project that simply does:

```bash
pip install "assert-ai[acs,langgraph,otel]"
```

and wires ASSERT into `.github/workflows/`. That is the shape we recommend: your agent
repo, your CI, ASSERT as a pip dependency — no ASSERT checkout required.

### What the standalone repo demonstrates

A five-job pipeline (lint → unit tests → **AI Safety Regression** → build → deploy),
where the safety job is the gate:

- It replays a committed ASSERT run and compares it to the **unguarded production
  baseline** with a paired statistical test (per-axis paired t-test, Holm-Bonferroni
  across axes).
- It **passes only if the change significantly *improves* `policy_violation` without
  regressing `overrefusal`** — an improvement gate, not just a fixed threshold.
- On a PR it posts a decision table (baseline vs current, Δpp, p-value, verdict). If the
  gate fails, **build is skipped and the PR is blocked.**

Two demo PRs make the beat concrete, both measured against the same unguarded baseline
(`policy_violation` 54%, `overrefusal` 19%):

| PR | Change | `policy_violation` vs baseline | Gate |
|----|--------|-------------------------------|------|
| Defensive **system-prompt** | prompt-only hardening | 54% → 62% (no significant improvement) | ❌ **FAIL** |
| **Control plane** (ASSERT + ACS) | typed-feature gate | 54% → 17% (improved; over-refusal 19% → 8%) | ✅ **PASS** |

The story mirrors the live demo: **prompting alone doesn't clear the safety bar; the
structural control plane does — and CI enforces it.**

## What's in this directory (offline evidence)

You can show the beat without the standalone repo or any network, straight from these
pre-generated artifacts:

| File | What it shows |
|---|---|
| [`sample-pages/PASS.html`](sample-pages/PASS.html) · `PASS_pr_comment.md` · `PASS_gate_report.json` | The gate **passing** (control plane improves the baseline → merge allowed). |
| [`sample-pages/FAIL.html`](sample-pages/FAIL.html) · `FAIL_pr_comment.md` · `FAIL_gate_report.json` | The gate **blocking a PR** (a regression that drops the control plane). |
| [`sample-pages/CROSS_JUDGE.md`](sample-pages/CROSS_JUDGE.md) | A multi-judge panel agreeing the text gate leaks while the feature gate holds. |
| [`assert-ci.yml`](assert-ci.yml) | Reference workflow (the shape the standalone repo implements). |
| [`ci_gate.py`](ci_gate.py) · [`pareto_baseline.json`](pareto_baseline.json) | The regression-gate script + its committed baseline. |

## Why a standalone repo is the better shipping vehicle

- **Matches how teams actually work** — the agent is a normal project that `pip install`s
  `assert-ai`; nobody develops inside a cloned eval framework.
- **CI is the natural home for the control-plane beat** — a gate belongs in the target
  repo's `.github/workflows/`, next to the code it guards.
- **Deterministic demo** — the standalone repo commits pre-computed ASSERT artifacts, so
  every CI run is reproducible with no live LLM calls.

This `examples/ci/` directory stays in ASSERT as the in-repo reference and pointer; the
standalone repo is where you copy the pattern into your own agent project.
