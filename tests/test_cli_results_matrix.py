# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from assert_ai.cli import cli


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _score_row(policy_violation: bool) -> dict[str, Any]:
    return {
        "judge_status": "ok",
        "target": "test-target",
        "judge_model": "test-judge",
        "verdict": {
            "dimensions": {
                "policy_violation": policy_violation,
                "overrefusal": False,
            },
            "node_judgments": [],
        },
    }


def _make_run(
    results_root: Path,
    suite_id: str,
    run_id: str,
    behavior_name: str | None,
    policy_violations: list[bool],
) -> None:
    run_dir = results_root / suite_id / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps({"status": "completed", "stages": {"judge": "completed"}}),
        encoding="utf-8",
    )
    (run_dir / "config.yaml").write_text(
        "\n".join([
            "behavior:",
            f"  name: {behavior_name}",
        ]) if behavior_name is not None else "behavior: {}\n",
        encoding="utf-8",
    )
    _write_jsonl(run_dir / "scores.jsonl", [_score_row(value) for value in policy_violations])


def test_results_matrix_json_renders_two_behaviors_by_two_arms(tmp_path: Path) -> None:
    results_root = tmp_path / "results"
    _make_run(results_root, "behavior-a", "behavior-a-baseline", "behavior_a", [True, False])
    _make_run(results_root, "behavior-a", "behavior-a-prompted", "behavior_a", [False, False])
    _make_run(results_root, "behavior-b", "behavior-b-baseline", "behavior_b", [True, True])
    _make_run(results_root, "behavior-b", "behavior-b-prompted", "behavior_b", [False, True])

    result = CliRunner().invoke(
        cli,
        [
            "results",
            "matrix",
            "behavior-a/behavior-a-baseline",
            "behavior-a/behavior-a-prompted",
            "behavior-b/behavior-b-baseline",
            "behavior-b/behavior-b-prompted",
            "--results-dir",
            str(results_root),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "metric": "policy_violation",
        "behaviors": ["behavior_a", "behavior_b"],
        "arms": ["baseline", "prompted"],
        "cells": {
            "behavior_a": {"baseline": 0.5, "prompted": 0.0},
            "behavior_b": {"baseline": 1.0, "prompted": 0.5},
        },
    }


def test_results_matrix_missing_cell_renders_null_and_dash(tmp_path: Path) -> None:
    results_root = tmp_path / "results"
    _make_run(results_root, "behavior-a", "behavior-a-baseline", "behavior_a", [True])
    _make_run(results_root, "behavior-a", "behavior-a-prompted", "behavior_a", [False])
    _make_run(results_root, "behavior-b", "behavior-b-baseline", "behavior_b", [False])

    args = [
        "results",
        "matrix",
        "behavior-a/behavior-a-baseline",
        "behavior-a/behavior-a-prompted",
        "behavior-b/behavior-b-baseline",
        "--results-dir",
        str(results_root),
    ]
    runner = CliRunner()

    json_result = runner.invoke(cli, [*args, "--json"])
    assert json_result.exit_code == 0, json_result.output
    payload = json.loads(json_result.output)
    assert payload["cells"]["behavior_b"]["prompted"] is None

    text_result = runner.invoke(cli, [*args, "--no-color"])
    assert text_result.exit_code == 0, text_result.output
    assert "behavior_b" in text_result.output
    assert "-" in text_result.output


def test_results_matrix_suite_auto_expand_matches_explicit_args(tmp_path: Path) -> None:
    results_root = tmp_path / "results"
    _make_run(results_root, "suite-a", "suite-a-baseline", "behavior_a", [True, False])
    _make_run(results_root, "suite-a", "suite-a-prompted", "behavior_a", [False, False])

    runner = CliRunner()
    explicit = runner.invoke(
        cli,
        [
            "results",
            "matrix",
            "suite-a/suite-a-baseline",
            "suite-a/suite-a-prompted",
            "--results-dir",
            str(results_root),
            "--json",
        ],
    )
    expanded = runner.invoke(
        cli,
        [
            "results",
            "matrix",
            "--suite",
            "suite-a",
            "--results-dir",
            str(results_root),
            "--json",
        ],
    )

    assert explicit.exit_code == 0, explicit.output
    assert expanded.exit_code == 0, expanded.output
    assert json.loads(explicit.output) == json.loads(expanded.output)


def test_results_matrix_repeated_suite_expands_multiple_suites_with_known_arm_order(tmp_path: Path) -> None:
    results_root = tmp_path / "results"
    _make_run(results_root, "suite-a", "suite-a-acs", "behavior_a", [False])
    _make_run(results_root, "suite-a", "suite-a-baseline", "behavior_a", [True])
    _make_run(results_root, "suite-b", "suite-b-prompted", "behavior_b", [True, False])
    _make_run(results_root, "suite-b", "suite-b-acs", "behavior_b", [False, False])
    _make_run(results_root, "suite-b", "suite-b-baseline", "behavior_b", [True, True])

    result = CliRunner().invoke(
        cli,
        [
            "results",
            "matrix",
            "--suite",
            "suite-a",
            "--suite",
            "suite-b",
            "--results-dir",
            str(results_root),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["behaviors"] == ["behavior_a", "behavior_b"]
    assert payload["arms"] == ["baseline", "prompted", "acs"]
    assert payload["cells"] == {
        "behavior_a": {"baseline": 1.0, "prompted": None, "acs": 0.0},
        "behavior_b": {"baseline": 1.0, "prompted": 0.5, "acs": 0.0},
    }


def test_results_matrix_behavior_name_falls_back_to_suite_id(tmp_path: Path) -> None:
    results_root = tmp_path / "results"
    _make_run(results_root, "fallback-suite", "fallback-suite-baseline", None, [True])
    _make_run(results_root, "fallback-suite", "fallback-suite-prompted", None, [False])

    result = CliRunner().invoke(
        cli,
        [
            "results",
            "matrix",
            "fallback-suite/fallback-suite-baseline",
            "fallback-suite/fallback-suite-prompted",
            "--results-dir",
            str(results_root),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["behaviors"] == ["fallback-suite"]
