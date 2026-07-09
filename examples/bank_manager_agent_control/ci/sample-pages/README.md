# CI sample pages — ready for slides

Pre-generated, reproducible evidence for the talk's "shipped in CI" + cross-judge beats.

| File | What it shows |
|---|---|
| `PASS_pr_comment.md` / `PASS_gate_report.json` | The guardrail CI gate **passing** — unguarded → 3-tier control plane: `policy_violation` 55%→18% (Improved, p<1e-6). Merge allowed. |
| `FAIL_pr_comment.md` / `FAIL_gate_report.json` | The same gate **blocking a PR** — a regression that drops the control plane: `policy_violation` 18%→55% (Regressed). PR fails. |
| `CROSS_JUDGE.md` | 4-lab panel (Kimi-K2.6, DeepSeek-V4-Pro, grok-4-20-reasoning, gpt-5.4) — all agree text gate leaks, feature gate holds. |

PASS/FAIL pages generated with the official `responsibleai/assert-action` `compare_runs.py`
(n=97 paired, Holm-Bonferroni α=0.05). Cross-judge from each suite's `judge_audit.json`.
Reproduce all figures: `python validate_talk_numbers.py`.
