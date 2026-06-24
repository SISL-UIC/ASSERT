# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Pure adapter functions mapping ASSERT's core dicts to MCP-friendly shapes.

These wrap ``assert_ai.results`` and ``assert_ai.library.loader`` (which already
return JSON-able dicts) and apply two MCP-specific concerns:

* **Row stripping** — ``results.load_run_summary`` embeds the full
  ``prompt_rows`` / ``scenario_rows`` (entire transcripts + verdicts). Returning
  those inline from a tool can be many megabytes, so the run/suite adapters drop
  them. Full transcripts are served lazily via MCP *resources* instead.
* **Clear errors** — missing suites/runs raise ``ValueError`` with an actionable
  message that the server maps onto an MCP tool error.

Every function is pure (no global state) and takes an explicit ``results_dir`` so
it can be unit-tested against a fixture directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from assert_ai import results as results_api
from assert_ai.library import loader

# Keys on a run summary that carry full per-test-case transcripts/verdicts. They
# are stripped from tool output and exposed through resources on demand.
_HEAVY_RUN_KEYS = ("prompt_rows", "scenario_rows")


def strip_run_rows(run: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a run summary without the heavy transcript row lists."""
    return {key: value for key, value in run.items() if key not in _HEAVY_RUN_KEYS}


def _strip_suite_rows(suite: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a suite summary with rows stripped from nested runs."""
    out = dict(suite)
    runs = out.get("runs")
    if isinstance(runs, list):
        out["runs"] = [strip_run_rows(run) for run in runs]
    return out


def list_suites(results_dir: Path) -> list[dict[str, Any]]:
    """List all readable suites under ``results_dir`` (heavy rows stripped)."""
    return [_strip_suite_rows(suite) for suite in results_api.load_all_suites(results_dir)]


def list_runs(results_dir: Path, suite: str) -> dict[str, Any]:
    """Return one suite's summary including its runs (heavy rows stripped)."""
    summary = results_api.load_suite_summary(results_dir / suite)
    if summary is None:
        raise ValueError(
            f"Suite {suite!r} not found or has no readable artifacts under {results_dir}."
        )
    return _strip_suite_rows(summary)


def get_run(results_dir: Path, suite: str, run: str) -> dict[str, Any]:
    """Return one run's metrics and status (heavy transcript rows stripped)."""
    summary = results_api.load_run_summary(results_dir / suite / run)
    if summary is None:
        raise ValueError(
            f"Run {suite}/{run} not found or has no readable artifacts under {results_dir}."
        )
    return strip_run_rows(summary)


def list_presets(kind: str | None = None) -> list[dict[str, Any]]:
    """List built-in presets, optionally filtered by kind."""
    return loader.discover(kind)


def show_preset(name: str, kind: str | None = None) -> dict[str, Any]:
    """Load one preset by name, auto-detecting kind when not supplied."""
    kinds = [kind] if kind else sorted(loader.VALID_KINDS)
    last_error: ValueError | None = None
    for candidate in kinds:
        try:
            return loader.load_preset(candidate, name)
        except ValueError as exc:
            last_error = exc
    detail = f" ({last_error})" if last_error else ""
    raise ValueError(f"Preset {name!r} not found in {kinds}.{detail}")
