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
from assert_ai.core.io import load_jsonl
from assert_ai.library import loader
from assert_ai.mcp._security import safe_subpath

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


def compare_runs(
    results_dir: Path,
    suite: str,
    run_a: str,
    run_b: str,
    metric: str = "policy_violation",
) -> dict[str, Any]:
    """Compare two runs in a suite: headline rate deltas + per-behavior deltas.

    Returns only computed deltas/metrics — no heavy transcript rows.
    """
    return results_api.compute_run_comparison(
        results_dir, suite, [run_a, run_b], metric=metric
    )


def get_failures(
    results_dir: Path,
    suite: str,
    run: str,
    dimension: str = "policy_violation",
    limit: int = 10,
) -> dict[str, Any]:
    """Return a run's flagged test cases for ``dimension`` with judge rationale."""
    return results_api.collect_failures(
        results_dir, suite, run, dimension=dimension, limit=limit
    )


def validate_config(config: str) -> dict[str, Any]:
    """Validate a YAML config without running it.

    Loads and resolves the config exactly as a run would (``load_config`` +
    ``load_runtime_context``) but executes no stages and spends no budget.
    Returns ``{"valid": True, ...}`` with a small summary, or
    ``{"valid": False, "error": ...}`` with the validation message.

    Raises:
        ValueError: if ``config`` does not point at an existing file.
    """
    config_path = Path(config).expanduser()
    if not config_path.is_file():
        raise ValueError(f"Config file not found: {config_path}")

    # Imported lazily: pulls in the config/stages machinery only when needed.
    from assert_ai.config import ConfigError, load_config, load_runtime_context
    from assert_ai.stages import STAGES

    resolved = config_path.resolve()
    try:
        raw = load_config(resolved)
        ctx = load_runtime_context(raw, resolved, stage_modules=STAGES)
    except (ConfigError, ValueError) as exc:
        return {"valid": False, "config": str(resolved), "error": str(exc)}

    suite_root = ctx.get("suite_root")
    return {
        "valid": True,
        "config": str(resolved),
        "suite": Path(suite_root).name if suite_root else None,
        "run_id": ctx.get("run_id"),
        "stages": [name for name, _ in ctx.get("stages", [])],
    }


def get_transcript(
    results_dir: Path, suite: str, run: str, case_id: str
) -> dict[str, Any]:
    """Return one test case's full conversation transcript and judge verdict.

    Reads the run's ``inference_set.jsonl`` (events = the conversation) and joins
    the matching ``scores.jsonl`` verdict. Suite/run are validated against path
    traversal before any file access.

    Raises:
        ValueError: on traversal, a missing inference set, or an unknown case id.
    """
    run_dir = safe_subpath(results_dir, suite, run)
    inference_path = run_dir / "inference_set.jsonl"
    if not inference_path.is_file():
        raise ValueError(f"No inference_set.jsonl for {suite}/{run}.")

    match: dict[str, Any] | None = None
    for row in load_jsonl(inference_path):
        if row.get("test_case_id") == case_id:
            match = row
            break
    if match is None:
        raise ValueError(f"Test case {case_id!r} not found in {suite}/{run}.")

    verdict: Any = None
    scores_path = run_dir / "scores.jsonl"
    if scores_path.is_file():
        for row in load_jsonl(scores_path):
            if row.get("test_case_id") == case_id:
                verdict = row.get("verdict")
                break

    return {
        "suite": suite,
        "run": run,
        "test_case_id": case_id,
        "type": match.get("type"),
        "behavior": match.get("behavior"),
        "target": match.get("target"),
        "events": match.get("events"),
        "llm_calls": match.get("llm_calls"),
        "verdict": verdict,
    }


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


def run_eval(
    config: str,
    *,
    force_stages: list[str] | None = None,
    overrides: list[str] | None = None,
    concurrency: int | None = None,
) -> dict[str, Any]:
    """Run an evaluation pipeline from a YAML config and summarize the outcome.

    Delegates to ``runner.run_pipeline_result`` (imported lazily so the
    read-only server stays light) and reads back the just-written run summary so
    the caller gets headline metrics, not just an exit code. Heavy transcript
    rows are stripped from the returned metrics.

    Raises:
        ValueError: if ``config`` does not point at an existing file.
    """
    config_path = Path(config).expanduser()
    if not config_path.is_file():
        raise ValueError(f"Config file not found: {config_path}")

    # Imported here rather than at module load: the runner pulls in heavy
    # dependencies (litellm, stages) that a read-only server never needs.
    from assert_ai import runner

    result = runner.run_pipeline_result(
        config=str(config_path),
        force_stages=force_stages,
        overrides=overrides,
        concurrency=concurrency,
    )

    payload: dict[str, Any] = {
        "exit_code": result.exit_code,
        "ok": result.exit_code == 0,
        "suite": result.suite,
        "run_id": result.run_id,
        "run_root": result.run_root,
        "metrics": None,
    }
    if result.run_root:
        summary = results_api.load_run_summary(Path(result.run_root))
        if summary is not None:
            payload["metrics"] = strip_run_rows(summary)
    return payload
