# Cross-judge panel — same conclusion, four independent labs

Auto-generated from each suite's `judge_audit.json`. Panel: **Kimi-K2.6, DeepSeek-V4-Pro,
grok-4-20-reasoning, gpt-5.4** (route-aware, unfiltered). The deterministic marker metric is the
calibration guard; THIS panel carries the general claim. Conclusion: **text gate leaks on new
domains; the typed-feature gate holds — every lab agrees.**

## bank-mgr-targeted  (n=64)

| arm | Kimi-K2.6 | DeepSeek-V4-Pro | grok-4-20-reasoning | gpt-5.4 | majority | unanimity | pairwise |
|---|---|---|---|---|---|---|
| tgt-b2-text | 40/52 | 48/63 | 48/64 | 48/64 | **48/64** | 1.000 | 1.000 |
| tgt-t1-feature | 0/48 | 0/64 | 3/64 | 0/64 | **0/64** | 0.953 | 0.974 |

## bank-mgr-large  (n=144)

| arm | Kimi-K2.6 | DeepSeek-V4-Pro | grok-4-20-reasoning | gpt-5.4 | majority | unanimity | pairwise |
|---|---|---|---|---|---|---|
| large-b2-text | 60/98 | 73/144 | 75/144 | 72/144 | **71/144** | 0.951 | 0.971 |
| large-t1-feature | 1/86 | 1/143 | 4/142 | 1/143 | **0/143** | 0.951 | 0.971 |

## Fisher exact (majority-collapsed)
- targeted text vs feature: **p = 2.251e-21**
- large-n text vs feature: **p = 7.503e-27**

_Reproduce: `python validate_talk_numbers.py` (xjudge section)._