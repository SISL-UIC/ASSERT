# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""FastMCP server exposing ASSERT evaluation capabilities over MCP.

The server is intentionally thin: each tool delegates to a pure function in
:mod:`assert_ai.mcp._adapters`, which in turn wraps the existing programmatic
surface. This module owns only MCP concerns — tool registration, the configured
results directory, transport selection, and the console-script entry point.

Phase 1 ships read-only tools (no model calls, no cost):

* ``list_presets`` / ``show_preset`` — browse the built-in behavior & judge library
* ``list_suites`` / ``list_runs`` / ``get_run`` — inspect local eval artifacts

Execution tools (``run_eval`` and friends) land in a later phase behind a
``--read-only`` gate.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Sequence

from mcp.server.fastmcp import FastMCP

from assert_ai.mcp import _adapters

SERVER_NAME = "assert"

INSTRUCTIONS = (
    "ASSERT evaluation server. Use these tools to browse the built-in behavior "
    "and judge preset library, and to inspect local evaluation suites and runs "
    "(violation / overrefusal / judge-failure rates). ASSERT is a local-first, "
    "spec-driven evaluation pipeline for AI agents."
)

# Default location of evaluation artifacts, relative to the server's working
# directory. Matches the CLI's ``artifacts/results`` convention; override with
# ``--results-dir`` or the ``ASSERT_RESULTS_DIR`` environment variable so a host
# launching the server over stdio can point it at a specific project.
DEFAULT_RESULTS_SUBDIR = Path("artifacts") / "results"


def resolve_results_dir(raw: str | os.PathLike[str] | None) -> Path:
    """Resolve the results directory from a CLI/env value to an absolute path."""
    if raw is None or str(raw) == "":
        raw = os.environ.get("ASSERT_RESULTS_DIR") or DEFAULT_RESULTS_SUBDIR
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def build_server(*, results_dir: Path, read_only: bool = True) -> FastMCP:
    """Construct a FastMCP server bound to a results directory.

    ``read_only`` is accepted for forward compatibility. Phase 1 registers only
    read-only tools, so it currently has no gating effect; execution tools added
    in a later phase will be registered only when ``read_only`` is ``False``.
    """
    mcp = FastMCP(SERVER_NAME, instructions=INSTRUCTIONS)

    @mcp.tool()
    def list_presets(kind: str | None = None) -> list[dict[str, Any]]:
        """List built-in behavior and judge presets.

        Args:
            kind: Optional filter — ``"behavior"`` or ``"judge_preset"``.
        """
        return _adapters.list_presets(kind)

    @mcp.tool()
    def show_preset(name: str, kind: str | None = None) -> dict[str, Any]:
        """Show one preset's full definition by name.

        Args:
            name: Preset name (e.g. ``"grounding"`` or ``"prompt_injection"``).
            kind: Optional kind; auto-detected across kinds when omitted.
        """
        return _adapters.show_preset(name, kind)

    @mcp.tool()
    def list_suites() -> list[dict[str, Any]]:
        """List evaluation suites with headline status and per-run metrics."""
        return _adapters.list_suites(results_dir)

    @mcp.tool()
    def list_runs(suite: str) -> dict[str, Any]:
        """List runs for one suite, with each run's headline metrics.

        Args:
            suite: Suite id (directory name under the results directory).
        """
        return _adapters.list_runs(results_dir, suite)

    @mcp.tool()
    def get_run(suite: str, run: str) -> dict[str, Any]:
        """Get one run's metrics and status.

        Heavy per-test-case transcript rows are omitted; fetch those via
        resources in a later phase.

        Args:
            suite: Suite id.
            run: Run id (directory name under the suite).
        """
        return _adapters.get_run(results_dir, suite, run)

    @mcp.tool()
    def compare_runs(
        suite: str,
        run_a: str,
        run_b: str,
        metric: str = "policy_violation",
    ) -> dict[str, Any]:
        """Compare two runs in a suite to spot regressions.

        Returns per-run headline metrics, first-vs-last rate deltas
        (policy_violation / overrefusal / judge_failure), and per-behavior
        deltas for ``metric``.

        Args:
            suite: Suite id.
            run_a: Baseline run id.
            run_b: Comparison run id.
            metric: Judge dimension for the per-behavior delta table.
        """
        return _adapters.compare_runs(results_dir, suite, run_a, run_b, metric=metric)

    @mcp.tool()
    def get_failures(
        suite: str,
        run: str,
        dimension: str = "policy_violation",
        limit: int = 10,
    ) -> dict[str, Any]:
        """List the test cases a run flagged, with the judge's reasoning.

        Args:
            suite: Suite id.
            run: Run id.
            dimension: Judge dimension to filter on (e.g. ``policy_violation``,
                ``overrefusal``).
            limit: Maximum number of failing cases to return.
        """
        return _adapters.get_failures(results_dir, suite, run, dimension, limit)

    @mcp.resource(
        "assert://results/{suite}/{run}/transcript/{case_id}",
        mime_type="application/json",
        name="transcript",
        description="Full conversation transcript + judge verdict for one test case.",
    )
    def transcript_resource(suite: str, run: str, case_id: str) -> str:
        data = _adapters.get_transcript(results_dir, suite, run, case_id)
        return json.dumps(data, indent=2, default=str)

    @mcp.resource(
        "assert://library/{kind}/{name}",
        mime_type="application/json",
        name="preset",
        description="A built-in behavior or judge preset definition.",
    )
    def preset_resource(kind: str, name: str) -> str:
        return json.dumps(_adapters.show_preset(name, kind), indent=2, default=str)

    if not read_only:
        _register_execution_tools(mcp)

    return mcp


def _register_execution_tools(mcp: FastMCP) -> None:
    """Register tools that mutate state or spend model budget.

    Gated behind ``--allow-run`` (``read_only=False``) so an operator can expose
    a purely read-only server by default.
    """

    @mcp.tool()
    async def run_eval(
        config: str,
        force_stages: list[str] | None = None,
        overrides: list[str] | None = None,
        concurrency: int | None = None,
    ) -> dict[str, Any]:
        """Run an ASSERT evaluation from a YAML config and return its outcome.

        This spends model budget (the pipeline calls LLMs). Returns the exit
        code, the suite/run id, and headline metrics read back from the run.

        Args:
            config: Path to a YAML pipeline config.
            force_stages: Stage names to force-rerun (e.g. ``["judge"]``).
            overrides: ``key=value`` config overrides (e.g. ``["test_set.sample_size=10"]``).
            concurrency: Override inference/judge fan-out for this run.
        """
        # The runner drives async stages via its own ``loop.run_until_complete``;
        # offload to a worker thread so it gets a clean event loop instead of
        # colliding with the MCP server's running loop.
        return await asyncio.to_thread(
            _adapters.run_eval,
            config,
            force_stages=force_stages,
            overrides=overrides,
            concurrency=concurrency,
        )


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="assert-ai-mcp",
        description="Run the ASSERT MCP server (stdio transport).",
    )
    parser.add_argument(
        "--results-dir",
        default=None,
        help=(
            "Directory of evaluation artifacts to expose "
            "(default: $ASSERT_RESULTS_DIR or ./artifacts/results)."
        ),
    )
    parser.add_argument(
        "--allow-run",
        action="store_true",
        help=(
            "Enable execution tools (run_eval). These spend model budget; the "
            "server is read-only by default."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Console-script entry point: build the server and serve over stdio."""
    args = _parse_args(argv)
    results_dir = resolve_results_dir(args.results_dir)
    server = build_server(results_dir=results_dir, read_only=not args.allow_run)
    server.run()


if __name__ == "__main__":
    main()
