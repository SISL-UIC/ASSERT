# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Replay the ASSERT MCP demo as an agent would see it — no IDE required.

Seeds the deterministic demo data (a clean ``baseline`` and a ``regressed`` run)
and then drives the MCP server over the SDK's in-memory transport, printing the
agent's-eye view of each tool/resource call. Use it to rehearse the demo or to
sanity-check the server without wiring up Claude Desktop / Cursor / Copilot.

Usage::

    python scripts/demo_walkthrough_mcp.py
    python scripts/demo_walkthrough_mcp.py --results-dir artifacts/results

Output is ASCII-only so it renders in any terminal.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Make both this repo (for ``assert_ai``) and this scripts dir (for the seed
# module) importable regardless of how the script is launched.
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from demo_seed_mcp import SUITE_ID, seed  # noqa: E402

from assert_ai.mcp.server import build_server  # noqa: E402
from mcp.shared.memory import (  # noqa: E402
    create_connected_server_and_client_session as connect,
)

# The FastMCP server logs every request at INFO; quiet it so the narrative reads
# cleanly.
logging.getLogger("mcp").setLevel(logging.WARNING)


def _structured(result: object) -> object:
    payload = getattr(result, "structuredContent", None)
    if isinstance(payload, dict) and set(payload) == {"result"}:
        return payload["result"]
    return payload


def _pct(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "n/a"
    return f"{value * 100:.0f}%"


async def _walk(results_dir: Path) -> None:
    server = build_server(results_dir=results_dir, read_only=False)
    async with connect(server) as client:
        await client.initialize()

        tools = await client.list_tools()
        print("Tools available to the agent:")
        print("  " + ", ".join(sorted(tool.name for tool in tools.tools)))
        print()

        print('AGENT> "List my evaluation suites."   [list_suites]')
        for suite in _structured(await client.call_tool("list_suites", {})):
            if suite["suite_id"] == SUITE_ID:
                print(
                    f'  - {suite["suite_id"]}: {suite["behavior_name"]} '
                    f'({suite["run_count"]} runs)'
                )
        print()

        print('AGENT> "Did anything regress, baseline vs regressed?"   [compare_runs]')
        comparison = _structured(
            await client.call_tool(
                "compare_runs",
                {"suite": SUITE_ID, "run_a": "baseline", "run_b": "regressed"},
            )
        )
        delta = comparison["headline_deltas"]["policy_violation_rate"]
        print(
            f'  policy violation: {_pct(delta["first"])} -> {_pct(delta["last"])} '
            f'(change +{_pct(delta["delta"])})'
        )
        for row in comparison["behavior_deltas"]:
            print(
                f'    - {row["behavior"]:<20} '
                f'{_pct(row["first_rate"])} -> {_pct(row["last_rate"])}'
            )
        print()

        print('AGENT> "Which cases failed, and why?"   [get_failures]')
        failures = _structured(
            await client.call_tool(
                "get_failures",
                {"suite": SUITE_ID, "run": "regressed", "dimension": "policy_violation"},
            )
        )
        for failure in failures["failures"]:
            reason = (failure["justification"] or "")[:72]
            print(f'    - {failure["test_case_id"]} ({failure["behavior"]}): {reason}...')
        print()

        print('AGENT> "Show me the worst failing transcript."   [transcript resource]')
        transcript = await client.read_resource(
            f"assert://results/{SUITE_ID}/regressed/transcript/outside-01"
        )
        data = json.loads(transcript.contents[0].text)
        for event in data["events"]:
            print(f'    {event["role"].upper()}: {event["content"]}')
        print(
            f'    JUDGE: policy_violation='
            f'{data["verdict"]["dimensions"]["policy_violation"]}'
        )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Replay the ASSERT MCP demo.")
    parser.add_argument(
        "--results-dir",
        default="artifacts/results",
        help="Results root to seed and read (default: ./artifacts/results).",
    )
    args = parser.parse_args(argv)

    results_dir = Path(args.results_dir).expanduser().resolve()
    print("=" * 70)
    print(" Seeding demo data (no model calls, no API keys)")
    print("=" * 70)
    seed(results_dir)
    print(f"Seeded suite '{SUITE_ID}' (baseline + regressed) under {results_dir}\n")

    print("=" * 70)
    print(" Agent's-eye walkthrough over the MCP protocol")
    print("=" * 70)
    asyncio.run(_walk(results_dir))


if __name__ == "__main__":
    main()
