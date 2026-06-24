# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Integration tests for the ASSERT MCP server.

These drive the server through the MCP SDK's in-memory client/server transport
(a real ``initialize`` + ``tools/list`` + ``tools/call`` round-trip), so they
exercise the actual protocol surface an IDE/agent would use — not just the
adapter functions. Following the repo convention (no ``pytest-asyncio``), each
test wraps its async interaction in ``asyncio.run``.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from mcp.shared.memory import create_connected_server_and_client_session as connect

from assert_ai.mcp.server import build_server

EXPECTED_TOOLS = {"list_presets", "show_preset", "list_suites", "list_runs", "get_run"}


def _seed_results(root: Path, suite_id: str = "demo-suite", run_id: str = "run-1") -> Path:
    """Lay out a minimal but readable suite/run under ``<root>/artifacts/results``.

    ``load_suite_summary`` needs ``suite.json`` or ``taxonomy.json``;
    ``load_run_summary`` needs ``scores.jsonl`` + a judge-stage manifest. The two
    score rows omit ``tester_model`` so they land in ``prompt_rows`` — letting us
    assert those heavy rows are stripped from tool output.
    """
    results_dir = root / "artifacts" / "results"
    suite_dir = results_dir / suite_id
    run_dir = suite_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    (suite_dir / "suite.json").write_text(
        json.dumps({"created_at": "2026-01-01T00:00:00Z"}), encoding="utf-8"
    )
    (suite_dir / "taxonomy.json").write_text(
        json.dumps(
            {
                "behavior": {"name": "Demo behavior"},
                "behavior_categories": [{"name": "c1"}, {"name": "c2"}],
            }
        ),
        encoding="utf-8",
    )
    (suite_dir / "test_set.jsonl").write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                {"type": "prompt", "test_case_id": "p1"},
                {"type": "prompt", "test_case_id": "p2"},
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    score_rows = [
        {"test_case_id": "p1", "target": "gpt-x", "judge_model": "judge-x"},
        {"test_case_id": "p2", "target": "gpt-x", "judge_model": "judge-x"},
    ]
    (run_dir / "scores.jsonl").write_text(
        "\n".join(json.dumps(row) for row in score_rows) + "\n", encoding="utf-8"
    )
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "stages": {"judge": "completed"},
                "started_at": "2026-01-01T00:00:00Z",
                "ended_at": "2026-01-01T00:05:00Z",
            }
        ),
        encoding="utf-8",
    )
    return results_dir


def _structured(result: Any) -> Any:
    """Extract the structured payload from a ``CallToolResult``.

    FastMCP wraps non-object return types (e.g. a ``list``) in a
    ``{"result": ...}`` envelope; dict returns are passed through directly.
    """
    payload = result.structuredContent
    if isinstance(payload, dict) and set(payload.keys()) == {"result"}:
        return payload["result"]
    return payload


def test_lists_expected_tools(tmp_path: Path) -> None:
    results_dir = _seed_results(tmp_path)

    async def _run() -> set[str]:
        server = build_server(results_dir=results_dir, read_only=True)
        async with connect(server) as client:
            await client.initialize()
            tools = await client.list_tools()
            return {tool.name for tool in tools.tools}

    assert asyncio.run(_run()) == EXPECTED_TOOLS


def test_list_and_show_presets(tmp_path: Path) -> None:
    results_dir = _seed_results(tmp_path)

    async def _run() -> tuple[Any, Any]:
        server = build_server(results_dir=results_dir, read_only=True)
        async with connect(server) as client:
            await client.initialize()
            presets = _structured(
                await client.call_tool("list_presets", {"kind": "judge_preset"})
            )
            grounding = _structured(
                await client.call_tool("show_preset", {"name": "grounding"})
            )
            return presets, grounding

    presets, grounding = asyncio.run(_run())
    assert isinstance(presets, list) and presets
    assert all("name" in preset and "kind" in preset for preset in presets)
    assert {preset["name"] for preset in presets} >= {"grounding"}
    assert grounding.get("kind") == "judge_preset"


def test_get_run_and_list_suites_strip_heavy_rows(tmp_path: Path) -> None:
    results_dir = _seed_results(tmp_path)

    async def _run() -> tuple[Any, Any]:
        server = build_server(results_dir=results_dir, read_only=True)
        async with connect(server) as client:
            await client.initialize()
            suites = _structured(await client.call_tool("list_suites", {}))
            run = _structured(
                await client.call_tool(
                    "get_run", {"suite": "demo-suite", "run": "run-1"}
                )
            )
            return suites, run

    suites, run = asyncio.run(_run())

    assert any(suite["suite_id"] == "demo-suite" for suite in suites)
    for suite in suites:
        for nested_run in suite.get("runs", []):
            assert "prompt_rows" not in nested_run
            assert "scenario_rows" not in nested_run

    assert run["run_id"] == "run-1"
    assert "prompt_rows" not in run
    assert "scenario_rows" not in run
    assert "status" in run


def test_missing_run_returns_tool_error(tmp_path: Path) -> None:
    results_dir = _seed_results(tmp_path)

    async def _run() -> Any:
        server = build_server(results_dir=results_dir, read_only=True)
        async with connect(server) as client:
            await client.initialize()
            return await client.call_tool("get_run", {"suite": "nope", "run": "nope"})

    result = asyncio.run(_run())
    assert result.isError
