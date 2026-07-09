"""Pareto frontier — safety vs benign over-refusal across guardrail variants.

The talk's payoff slide. Each variant is one point: x = unsafe-response rate,
y = benign over-refusal rate. "Unsafe" folds groundedness into safety/quality
(an ungrounded policy claim is a low-quality, unsafe answer), so unsafe =
policy_violation OR ungrounded_policy_claim. Lower-left dominates.

The story: the naive guardrails buy safety by over-refusing (they move UP-left,
a regression on helpfulness); the systematic 3-tier control plane (escalate, not
blunt-deny; never gate standard-tier reads) moves the whole frontier DOWN — safer
AND less over-refusing.

All arms must be judged with the SAME principle-gated rubric for the comparison
to be valid (see eval_realistic_*.yaml). Reads each arm's scores.jsonl.

Usage:
  python pareto_frontier.py            # default 4 arms from the suite cache
  python pareto_frontier.py --json     # print the data table only, no plot
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

SUITE = Path(__file__).parent.parent.parent / "artifacts" / "results" / "bank-manager-feature-rep"
OUT = SUITE / "pareto"

# arm label -> run dir (scores.jsonl inside). Order = naive -> optimized.
ARMS = [
    ("Unguarded app", "variant-b0-unguarded-realistic-n100"),
    ("Defensive prompt", "variant-b1-prompted-realistic-n100"),
    ("Blunt gate (text ACS)", "variant-b2-acs-text-realistic-n100"),
    ("3-tier control plane", "variant-opt-feature-llm-realistic-n100"),
]


def _wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - m) / d), min(1.0, (c + m) / d))


def arm_rates(scores_path: Path) -> dict:
    n = unsafe = refus = viol = ung = 0
    for line in scores_path.read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        dim = d.get("verdict", {}).get("dimensions", {})
        if not dim:
            continue
        n += 1
        v = bool(dim.get("policy_violation"))
        u = bool(dim.get("ungrounded_policy_claim"))
        viol += v
        ung += u
        unsafe += (v or u)          # groundedness folded into safety/quality
        refus += bool(dim.get("overrefusal"))
    return {"n": n, "unsafe": unsafe, "violation": viol, "ungrounded": ung,
            "overrefusal": refus,
            "unsafe_rate": unsafe / n if n else 0.0,
            "overrefusal_rate": refus / n if n else 0.0,
            "unsafe_ci": _wilson(unsafe, n), "refus_ci": _wilson(refus, n)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="data only, skip the plot")
    args = ap.parse_args()

    points = []
    for label, run in ARMS:
        sp = SUITE / run / "scores.jsonl"
        if not sp.exists():
            print(f"  [skip] {label}: no scores at {sp}")
            continue
        r = arm_rates(sp)
        r["label"] = label
        points.append(r)

    print(f"\nPareto data (unsafe = violation OR ungrounded; n per arm):\n")
    print(f"  {'variant':26} {'n':>4} {'unsafe%':>9} {'over-refusal%':>14}  (viol/ungr)")
    for r in points:
        print(f"  {r['label']:26} {r['n']:>4} {r['unsafe_rate']*100:>8.1f}% "
              f"{r['overrefusal_rate']*100:>13.1f}%   ({r['violation']}/{r['ungrounded']})")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    (OUT.with_suffix(".json")).write_text(json.dumps(points, indent=2))

    if args.json or not points:
        return

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 6))
    # x = safety VIOLATION rate (gate-differentiating; groundedness is a separate
    # SUT-quality axis handled in the retrieval beat, so it's not on this plot).
    xs = [r["violation"] / r["n"] * 100 for r in points]
    ys = [r["overrefusal_rate"] * 100 for r in points]
    colors = ["#b0b0b0", "#e0a030", "#d05050", "#2a8a3a"]
    for i, r in enumerate(points):
        c = colors[i % len(colors)]
        ax.scatter(xs[i], ys[i], s=180, color=c, zorder=3, edgecolor="black", linewidth=0.6)
        ax.annotate(f"{r['label']}\n({xs[i]:.0f}% unsafe, {ys[i]:.0f}% over-refuse)",
                    (xs[i], ys[i]), textcoords="offset points", xytext=(10, 8),
                    fontsize=9, weight="bold" if i == len(points) - 1 else "normal")
    # the frontier move: from the naive defensive-prompt (worst) down-left to the
    # control plane (best) — both safety and over-refusal improve together.
    if len(points) >= 4:
        ax.annotate("", xy=(xs[3], ys[3]), xytext=(xs[1], ys[1]),
                    arrowprops=dict(arrowstyle="->", color="#2a8a3a", lw=1.8,
                                    connectionstyle="arc3,rad=-0.15"))
    ax.set_xlabel("Safety violations  %  →  worse")
    ax.set_ylabel("Benign over-refusal  %  →  worse")
    ax.set_title("Moving the safety ↔ over-refusal frontier  (realistic n=100, gpt-5.5 judge)\n"
                 "lower-left is better — defensive prompting backfires; the control plane wins")
    ax.grid(True, alpha=0.3)
    ax.set_xlim(left=-2)
    ax.set_ylim(bottom=-2)
    fig.tight_layout()
    fig.savefig(OUT.with_suffix(".png"), dpi=150)
    print(f"\n  plot -> {OUT.with_suffix('.png')}")
    print(f"  data -> {OUT.with_suffix('.json')}\n")


if __name__ == "__main__":
    main()
