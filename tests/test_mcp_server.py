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
from unittest.mock import patch

import pytest

pytest.importorskip("mcp")

from mcp.shared.memory import create_connected_server_and_client_session as connect

from assert_ai.mcp.server import build_server

EXPECTED_TOOLS = {
    "list_presets",
    "show_preset",
    "list_suites",
    "list_runs",
    "get_run",
    "compare_runs",
}


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
    inference_rows = [
        {
            "test_case_id": "p1",
            "type": "prompt",
            "target": "gpt-x",
            "behavior": "c1",
            "events": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi there"},
            ],
        },
        {
            "test_case_id": "p2",
            "type": "prompt",
            "target": "gpt-x",
            "behavior": "c2",
            "events": [
                {"role": "user", "content": "question"},
                {"role": "assistant", "content": "answer"},
            ],
        },
    ]
    (run_dir / "inference_set.jsonl").write_text(
        "\n".join(json.dumps(row) for row in inference_rows) + "\n", encoding="utf-8"
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


def _add_run(results_dir: Path, suite_id: str, run_id: str) -> None:
    """Add a second readable run to an existing seeded suite."""
    run_dir = results_dir / suite_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    score_rows = [
        {"test_case_id": "p1", "target": "gpt-x", "judge_model": "judge-x"},
        {"test_case_id": "p2", "target": "gpt-x", "judge_model": "judge-x"},
    ]
    (run_dir / "scores.jsonl").write_text(
        "\n".join(json.dumps(row) for row in score_rows) + "\n", encoding="utf-8"
    )
    (run_dir / "manifest.json").write_text(
        json.dumps({"status": "completed", "stages": {"judge": "completed"}}),
        encoding="utf-8",
    )


def test_compare_runs(tmp_path: Path) -> None:
    results_dir = _seed_results(tmp_path)
    _add_run(results_dir, "demo-suite", "run-2")

    async def _run() -> Any:
        server = build_server(results_dir=results_dir, read_only=True)
        async with connect(server) as client:
            await client.initialize()
            return _structured(
                await client.call_tool(
                    "compare_runs",
                    {"suite": "demo-suite", "run_a": "run-1", "run_b": "run-2"},
                )
            )

    result = asyncio.run(_run())
    assert result["suite"] == "demo-suite"
    assert len(result["runs"]) == 2
    assert {r["run_id"] for r in result["runs"]} == {"run-1", "run-2"}
    assert "policy_violation_rate" in result["headline_deltas"]
    assert "behavior_deltas" in result


def test_missing_run_returns_tool_error(tmp_path: Path) -> None:
    results_dir = _seed_results(tmp_path)

    async def _run() -> Any:
        server = build_server(results_dir=results_dir, read_only=True)
        async with connect(server) as client:
            await client.initialize()
            return await client.call_tool("get_run", {"suite": "nope", "run": "nope"})

    result = asyncio.run(_run())
    assert result.isError


def _seed_mock_eval(root: Path) -> Path:
    """Write a judge-only config + inference set that runs without real models.

    The judge stage is patched in the test, so no LLM is called. Mirrors the
    end-to-end pattern in ``tests/test_run_metadata.py``.
    """
    results_root = root / "results"
    suite_root = results_root / "suite-a"
    suite_root.mkdir(parents=True, exist_ok=True)
    inference_set = suite_root / "inference_set.jsonl"
    inference_set.write_text('{"type":"prompt","test_case_id":"tc-1"}\n', encoding="utf-8")
    (suite_root / "taxonomy.json").write_text("{}", encoding="utf-8")
    cfg = root / "config.yaml"
    cfg.write_text(
        "\n".join(
            [
                "suite: suite-a",
                "run: run-a",
                f"results_dir: {results_root}",
                "behavior:",
                "  name: harmful_medical_advice",
                "pipeline:",
                "  judge:",
                "    model:",
                "      name: azure/gpt-5.4",
                f"    inference_set_path: {inference_set}",
            ]
        ),
        encoding="utf-8",
    )
    return cfg


def test_run_eval_hidden_when_read_only(tmp_path: Path) -> None:
    server = build_server(results_dir=tmp_path, read_only=True)
    names = {tool.name for tool in asyncio.run(server.list_tools())}
    assert "run_eval" not in names
    assert EXPECTED_TOOLS <= names


def test_run_eval_present_when_allowed(tmp_path: Path) -> None:
    server = build_server(results_dir=tmp_path, read_only=False)
    names = {tool.name for tool in asyncio.run(server.list_tools())}
    assert "run_eval" in names


def test_run_eval_executes_and_strips_rows(tmp_path: Path) -> None:
    cfg = _seed_mock_eval(tmp_path)
    results_root = tmp_path / "results"

    async def fake_run_judge(**_: object) -> dict[str, str]:
        run_root = results_root / "suite-a" / "run-a"
        run_root.mkdir(parents=True, exist_ok=True)
        rows = [
            {"test_case_id": "tc-1", "target": "gpt-x", "judge_model": "j"},
            {"test_case_id": "tc-2", "target": "gpt-x", "judge_model": "j"},
        ]
        scores = run_root / "scores.jsonl"
        scores.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        return {"scores_path": str(scores)}

    async def _run() -> Any:
        server = build_server(results_dir=results_root, read_only=False)
        async with connect(server) as client:
            await client.initialize()
            return _structured(
                await client.call_tool("run_eval", {"config": str(cfg)})
            )

    with patch("assert_ai.stages.judge.run_judge", new=fake_run_judge):
        payload = asyncio.run(_run())

    assert payload["ok"] is True
    assert payload["exit_code"] == 0
    assert payload["suite"] == "suite-a"
    assert payload["run_id"] == "run-a"
    assert payload["metrics"] is not None
    assert "prompt_rows" not in payload["metrics"]
    assert "scenario_rows" not in payload["metrics"]


def test_transcript_resource_returns_events_and_verdict(tmp_path: Path) -> None:
    results_dir = _seed_results(tmp_path)

    async def _run() -> Any:
        server = build_server(results_dir=results_dir, read_only=True)
        async with connect(server) as client:
            await client.initialize()
            return await client.read_resource(
                "assert://results/demo-suite/run-1/transcript/p1"
            )

    result = asyncio.run(_run())
    payload = json.loads(result.contents[0].text)
    assert payload["test_case_id"] == "p1"
    assert payload["suite"] == "demo-suite"
    assert payload["events"]  # the conversation is present
    assert payload["events"][0]["role"] == "user"


def test_preset_resource_returns_definition(tmp_path: Path) -> None:
    results_dir = _seed_results(tmp_path)

    async def _run() -> Any:
        server = build_server(results_dir=results_dir, read_only=True)
        async with connect(server) as client:
            await client.initialize()
            return await client.read_resource("assert://library/judge_preset/grounding")

    result = asyncio.run(_run())
    payload = json.loads(result.contents[0].text)
    assert payload.get("kind") == "judge_preset"


def test_safe_subpath_rejects_traversal(tmp_path: Path) -> None:
    from assert_ai.mcp._security import safe_subpath

    assert safe_subpath(tmp_path, "suite", "run") == (tmp_path / "suite" / "run").resolve()

    for bad in ["..", ".", "", "a/b", "a\\b"]:
        with pytest.raises(ValueError):
            safe_subpath(tmp_path, bad)

    with pytest.raises(ValueError):
        safe_subpath(tmp_path, str(tmp_path.resolve()))


def _load_demo_seed_module() -> Any:
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "scripts" / "demo_seed_mcp.py"
    spec = importlib.util.spec_from_file_location("demo_seed_mcp", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_demo_seed_produces_a_real_regression(tmp_path: Path) -> None:
    seed_mod = _load_demo_seed_module()
    results_dir = tmp_path / "results"
    seed_mod.seed(results_dir)

    async def _run() -> Any:
        server = build_server(results_dir=results_dir, read_only=True)
        async with connect(server) as client:
            await client.initialize()
            return _structured(
                await client.call_tool(
                    "compare_runs",
                    {
                        "suite": seed_mod.SUITE_ID,
                        "run_a": "baseline",
                        "run_b": "regressed",
                    },
                )
            )

    result = asyncio.run(_run())
    policy = result["headline_deltas"]["policy_violation_rate"]
    assert policy["first"] == 0.0
    assert policy["last"] is not None and policy["last"] > 0.5
    assert policy["delta"] is not None and policy["delta"] > 0.5
    assert result["behavior_deltas"]  # per-behavior breakdown is populated
