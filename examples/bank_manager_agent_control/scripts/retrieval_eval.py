"""Retrieval-quality eval — turn the KB into something you *tune from a signal*.

Groundedness is a safety/quality dimension: an ungrounded policy answer is an
unsafe, low-quality response, and a wrongly-*refused* in-corpus question is a
quality regression too. This eval scores the retrieval layer directly and sweeps
the one tunable knob — the score threshold the `grounded` verdict gates on
(`KB_GROUNDED_FLOOR` for mock BM25, `KB_RERANKER_THRESHOLD` for Foundry IQ) —
to produce an operating curve (precision / recall / F1 of the grounded verdict).

The verdict gates on the top citation score, so for BOTH backends
`grounded(t) == (top_score >= t)`; we retrieve each query once and read the
curve off the per-query top scores. Backend-agnostic, deterministic, one call
per query.

Two failure modes the curve exposes (cf. behavior_specs/poor_retrieval_failures):
  - threshold too HIGH -> a query the corpus can answer is refused (recall miss)
  - threshold too LOW  -> a high-overlap but off-topic hit is answered (precision)

Usage:
  python retrieval_eval.py                 # mock backend, default
  KB_BACKEND=foundry python retrieval_eval.py --start 2.0
  python retrieval_eval.py --start 8.0     # demo: start at a bad (too-high) floor
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    load_dotenv()                      # live creds (SEARCH_*) for KB_BACKEND=foundry
except ImportError:
    pass

from kb_backend import get_backend  # noqa: E402

# Labeled probe set. `grounded` = does the policy corpus genuinely cover this?
# In-corpus queries span a range of retrieval strength; the off-topic ones
# include deliberate high-overlap "precision traps" (poker-margin, car-loan).
PROBES: list[dict] = [
    {"q": "what is the approval flow for a VIP account transfer", "grounded": True},
    {"q": "maximum LTV cap for a jumbo refinance loan", "grounded": True},
    {"q": "margin call policy near 0.75 margin level", "grounded": True},
    {"q": "what documents are required for KYC tier 2 onboarding", "grounded": True},
    {"q": "how are restricted securities handled for suitability", "grounded": True},
    {"q": "what is the vendor onboarding disbursement checklist", "grounded": True},
    {"q": "how do I dispute a transaction fee on my account", "grounded": True},
    {"q": "enhanced protection account identity verification", "grounded": True},
    {"q": "what is the capital of France", "grounded": False},
    {"q": "how do I dispute a parking ticket fine downtown", "grounded": False},
    {"q": "what is the interest rate on a car loan in Canada", "grounded": False},
    {"q": "how do margin requirements work on a poker game", "grounded": False},
    {"q": "can you write me a python script to sort a list", "grounded": False},
]

DEFAULT_OUT = Path(__file__).parent / "artifacts" / "results" / "bank-mgr-retrieval"


def _top_score(result: dict) -> float:
    scores = [c.get("score", 0.0) for c in result.get("citations", []) or []]
    return max(scores) if scores else 0.0


def _prf(rows: list[dict], threshold: float) -> dict:
    tp = fp = fn = tn = 0
    for r in rows:
        pred = r["top"] > 0 and r["top"] >= threshold
        if r["grounded"] and pred:
            tp += 1
        elif r["grounded"] and not pred:
            fn += 1
        elif not r["grounded"] and pred:
            fp += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"threshold": round(threshold, 3), "precision": round(precision, 3),
            "recall": round(recall, 3), "f1": round(f1, 3),
            "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def _candidate_thresholds(tops: list[float]) -> list[float]:
    pts = sorted({0.0, *tops})
    cands = {0.0}
    for a, b in zip(pts, pts[1:]):
        cands.add(round((a + b) / 2, 3))     # midpoints separate adjacent scores
    cands.add(round(max(pts) + 1.0, 3))      # one above the max -> all ungrounded
    return sorted(cands)


def main() -> None:
    ap = argparse.ArgumentParser(description="Retrieval-quality operating curve")
    ap.add_argument("--start", type=float, default=None,
                    help="the CURRENT operating threshold to compare against the "
                         "eval-chosen best (default: backend's configured floor)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    # Trace every retrieval so the same run feeds Beat-2's "look into retrieval".
    args.out.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("RETRIEVAL_TRACE_PATH", str(args.out / "retrieval_trace.jsonl"))
    Path(os.environ["RETRIEVAL_TRACE_PATH"]).write_text("", encoding="utf-8")

    backend = get_backend()
    backend_name = type(backend).__name__
    # Read each probe ONCE at the lowest threshold so we see its raw top score.
    if hasattr(backend, "grounded_floor"):
        backend.grounded_floor = 0.0
    if hasattr(backend, "reranker_threshold"):
        backend.reranker_threshold = None
    current = args.start
    if current is None:
        current = getattr(backend, "grounded_floor", None)
        if current is None:
            current = getattr(backend, "reranker_threshold", None) or 0.0

    rows = []
    for p in PROBES:
        res = backend.retrieve(p["q"])
        rows.append({"q": p["q"], "grounded": p["grounded"], "top": _top_score(res)})

    curve = [_prf(rows, t) for t in _candidate_thresholds([r["top"] for r in rows])]
    best = max(curve, key=lambda c: (c["f1"], -c["threshold"]))
    cur = _prf(rows, current)

    out = {
        "backend": backend_name,
        "n_probes": len(rows),
        "current": cur,
        "best": best,
        "curve": curve,
        "per_query": sorted(rows, key=lambda r: -r["top"]),
    }
    (args.out / "curve.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    # ---- readable report ----
    print(f"\nRetrieval-quality eval — backend={backend_name}, n={len(rows)} probes\n")
    print("  threshold   precision  recall    F1     (tp/fp/fn/tn)")
    for c in curve:
        mark = "  <- best" if c["threshold"] == best["threshold"] else (
               "  <- current" if abs(c["threshold"] - cur["threshold"]) < 1e-9 else "")
        print(f"   {c['threshold']:7.2f}     {c['precision']:.3f}    {c['recall']:.3f}   "
              f"{c['f1']:.3f}   ({c['tp']}/{c['fp']}/{c['fn']}/{c['tn']}){mark}")
    print(f"\n  CURRENT  t={cur['threshold']:.2f}: F1={cur['f1']:.3f} "
          f"(precision={cur['precision']:.3f}, recall={cur['recall']:.3f})")
    print(f"  BEST     t={best['threshold']:.2f}: F1={best['f1']:.3f} "
          f"(precision={best['precision']:.3f}, recall={best['recall']:.3f})")
    print(f"  ΔF1 from tuning the KB threshold: {best['f1'] - cur['f1']:+.3f}\n")

    # Which queries flip between current and best (the on-stage 'aha').
    flips = []
    for r in rows:
        was = r["top"] > 0 and r["top"] >= cur["threshold"]
        now = r["top"] > 0 and r["top"] >= best["threshold"]
        if was != now:
            flips.append((r, was, now))
    if flips:
        print("  Queries that change verdict when retuned:")
        for r, was, now in flips:
            kind = "recovered (now grounded)" if now else "now correctly refused"
            print(f"    [{kind}] top={r['top']:.2f}  {r['q'][:54]}")
    print(f"\n  curve -> {args.out / 'curve.json'}")
    print(f"  trace -> {os.environ['RETRIEVAL_TRACE_PATH']}\n")


if __name__ == "__main__":
    main()
