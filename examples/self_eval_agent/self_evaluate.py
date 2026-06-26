# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Guided self-evaluation: CareBuddy evaluates *itself* via ASSERT, over MCP.

The same agent persona (``examples.self_eval_agent.agent``) plays two roles:

* it is the **target** ASSERT evaluates (the ``callable`` in ``eval_config.yaml``), and
* it is the **client** that drives ASSERT's MCP server to run that evaluation and
  read back its own failures, then writes a self-critique.

The flow is a fixed, reliable sequence of real MCP tool calls — exactly what an
AI IDE would issue, just scripted here so the demo is repeatable:

    validate_config  ->  run_eval (target = me)  ->  get_failures  ->  reflect

This runs a real evaluation, so it needs Azure credentials (``AZURE_API_KEY`` /
``AZURE_API_BASE`` in ``.env``) and spends a small amount of model budget.

Run it::

    python examples/self_eval_agent/self_evaluate.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

# Render UTF-8 (em-dashes, the model's curly quotes) on any console codepage.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover - stdout may not support reconfigure
    pass

from dotenv import find_dotenv, load_dotenv  # noqa: E402

load_dotenv(find_dotenv(usecwd=True))

from mcp.shared.memory import (  # noqa: E402
    create_connected_server_and_client_session as connect,
)

from assert_ai.mcp.server import build_server  # noqa: E402
from examples.self_eval_agent import agent  # noqa: E402

# Keep the MCP server's per-request INFO logs out of the narrative.
logging.getLogger("mcp").setLevel(logging.WARNING)

CONFIG = Path(__file__).resolve().parent / "eval_config.yaml"
RULE = "=" * 72

# Pacing for a live demo: a short beat between steps so it's easy to narrate.
# Set ASSERT_DEMO_PAUSE=0 to run flat out.
STEP_PAUSE_S = float(os.environ.get("ASSERT_DEMO_PAUSE", "3"))


async def _pause() -> None:
    if STEP_PAUSE_S > 0:
        await asyncio.sleep(STEP_PAUSE_S)


def _structured(result: object) -> object:
    payload = getattr(result, "structuredContent", None)
    if isinstance(payload, dict) and set(payload) == {"result"}:
        return payload["result"]
    return payload


def _pct(value: object) -> str:
    return f"{value * 100:.0f}%" if isinstance(value, (int, float)) else "n/a"


_SMART_PUNCT = {
    "\u2019": "'",
    "\u2018": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2014": "-",
    "\u2013": "-",
    "\u2026": "...",
    "\u00a0": " ",
}


def _clean(text: str) -> str:
    """Fold smart quotes/dashes from model output to ASCII for any console."""
    for fancy, plain in _SMART_PUNCT.items():
        text = text.replace(fancy, plain)
    return text


def _combined_rate(metrics: dict, dimension: str) -> object:
    """Overall flag rate for a dimension across prompt + scenario test cases."""
    flagged = scored = 0
    for kind in ("prompt_metrics", "scenario_metrics"):
        summary = ((metrics or {}).get(kind) or {}).get("dimensions") or {}
        cell = summary.get(dimension) or {}
        flagged += cell.get("flagged_count") or 0
        scored += cell.get("count") or 0
    return (flagged / scored) if scored else None


async def _on_progress(progress: float, total: float | None, message: str | None) -> None:
    if message:
        print(f"      ...{message}")


async def run() -> None:
    if "AZURE_API_KEY" not in os.environ:
        print(
            "This demo runs a REAL evaluation, so it needs Azure credentials.\n"
            "Copy .env.example to .env and set AZURE_API_KEY and AZURE_API_BASE, "
            "then run this again."
        )
        return

    results_dir = _REPO_ROOT / "artifacts" / "results"

    print(RULE)
    print(" CareBuddy: a health assistant evaluating ITSELF with ASSERT (via MCP)")
    print(RULE)
    print(
        "[CareBuddy] Hi - I'm CareBuddy, a health assistant for elderly patients.\n"
        "            I'm going to check my own safety using ASSERT, talking to it\n"
        "            through its MCP server the same way an AI IDE would.\n"
    )
    await _pause()

    # read_only=False so the run_eval execution tool is available.
    server = build_server(results_dir=results_dir, read_only=False)
    async with connect(server) as client:
        await client.initialize()
        tools = await client.list_tools()
        print("Step 1/4  Connected to the ASSERT MCP server.")
        print("          Tools I can call: " + ", ".join(sorted(t.name for t in tools.tools)))
        print()
        await _pause()

        print("Step 2/4  Validating my evaluation spec...   [validate_config]")
        validation = _structured(
            await client.call_tool("validate_config", {"config": str(CONFIG)})
        )
        if not validation.get("valid"):
            print(f"          Spec is invalid: {validation.get('error')}")
            return
        print(f"          Valid. Stages: {', '.join(validation.get('stages', []))}")
        print()
        await _pause()

        print("Step 3/4  Running the evaluation on myself...   [run_eval]")
        print("          (ASSERT writes adversarial test cases, runs them against me,")
        print("           and judges my answers - this is the part that calls models.)")
        await _pause()
        outcome = _structured(
            await client.call_tool(
                "run_eval", {"config": str(CONFIG)}, progress_callback=_on_progress
            )
        )
        if not outcome.get("ok"):
            print(f"          Run failed (exit {outcome.get('exit_code')}).")
            return
        metrics = outcome.get("metrics") or {}
        suite, run_id = outcome.get("suite"), outcome.get("run_id")
        print(
            f"          Done - {suite}/{run_id}. "
            f"policy violation: {_pct(_combined_rate(metrics, 'policy_violation'))}, "
            f"overrefusal: {_pct(_combined_rate(metrics, 'overrefusal'))}"
        )
        print()
        await _pause()

        print("Step 4/4  Reviewing where I failed...   [get_failures]")
        failures = _structured(
            await client.call_tool(
                "get_failures",
                {"suite": suite, "run": run_id, "dimension": "policy_violation", "limit": 5},
            )
        )
        print(f"          ASSERT flagged {failures.get('count', 0)} of my responses:")
        for failure in failures.get("failures", []):
            reason = _clean((failure.get("justification") or "").strip().replace("\n", " "))
            print(f"            - [{failure.get('test_case_id')}] {reason[:90]}")
        print()
        await _pause()

    # Outside the MCP session: the same persona reflects on its own results.
    print(RULE)
    print(" [CareBuddy reflects on its own evaluation]")
    print(RULE)
    print(_clean(agent.reflect(failures.get("failures", []))))


if __name__ == "__main__":
    asyncio.run(run())
