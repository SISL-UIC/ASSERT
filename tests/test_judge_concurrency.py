# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""The judge stage must not be throttled by a target-protecting inference limit."""

import unittest

from assert_ai.config import ConfigError, load_runtime_context
from assert_ai.core.config_model import (
    DEFAULT_INFERENCE_CONCURRENCY,
    EvaluationConfig,
    InferenceConfig,
    JudgeConfig,
    ModelConfig,
)
from assert_ai.stages import STAGES


def _evaluation(
    inference_concurrency: int,
    judge_concurrency: int | None = None,
    judge_n: int = 1,
):
    return EvaluationConfig(
        judge=JudgeConfig(
            model=ModelConfig(name="azure/gpt-5.4"),
            concurrency=judge_concurrency,
            n=judge_n,
        ),
        inference=InferenceConfig(concurrency=inference_concurrency),
    )


class JudgeConcurrencyTest(unittest.TestCase):
    def test_low_inference_concurrency_does_not_serialize_the_judge(self) -> None:
        # inference.concurrency=1 protects a target that can't be driven in
        # parallel. The judge only reads transcripts off disk, so it keeps
        # the normal default.
        self.assertEqual(
            _evaluation(1).judge_concurrency, DEFAULT_INFERENCE_CONCURRENCY
        )

    def test_high_inference_concurrency_is_still_inherited(self) -> None:
        self.assertEqual(_evaluation(24).judge_concurrency, 24)

    def test_explicit_judge_concurrency_wins(self) -> None:
        self.assertEqual(_evaluation(24, judge_concurrency=2).judge_concurrency, 2)
        self.assertEqual(_evaluation(1, judge_concurrency=32).judge_concurrency, 32)

    def test_default_is_divided_by_judge_n(self) -> None:
        # core/judge.py fires judge.n concurrent calls per row INSIDE the stage
        # semaphore, so the derived default must account for them or a
        # deployment throttled to 1 would see n x fan-out calls in flight.
        self.assertEqual(_evaluation(1, judge_n=3).judge_concurrency, 3)
        self.assertEqual(_evaluation(24, judge_n=3).judge_concurrency, 8)
        self.assertEqual(_evaluation(1, judge_n=25).judge_concurrency, 1)

    def test_explicit_judge_concurrency_is_not_divided_by_judge_n(self) -> None:
        self.assertEqual(
            _evaluation(1, judge_concurrency=6, judge_n=3).judge_concurrency, 6
        )

    def test_judge_concurrency_must_be_positive(self) -> None:
        with self.assertRaisesRegex(ValueError, "judge.concurrency must be > 0"):
            JudgeConfig(model=ModelConfig(name="m"), concurrency=0)

    def test_evaluation_without_judge_still_resolves(self) -> None:
        evaluation = EvaluationConfig(inference=InferenceConfig(concurrency=3))
        self.assertEqual(evaluation.judge_concurrency, DEFAULT_INFERENCE_CONCURRENCY)


class JudgeConcurrencyConfigParsingTest(unittest.TestCase):
    def _context(self, judge_extra: dict) -> EvaluationConfig:
        raw = {
            "suite": "s",
            "run": "r",
            "behavior": {"name": "b", "description": "d"},
            "default_model": {"name": "azure/gpt-5.4"},
            "pipeline": {
                "inference": {
                    "concurrency": 1,
                    "target": {"system_prompt": "p"},
                },
                "judge": {
                    "dimensions": {
                        "policy_violation": {
                            "description": "d",
                            "rubric": "true = x\nfalse = y",
                        }
                    },
                    **judge_extra,
                },
            },
        }
        ctx = load_runtime_context(raw, "eval_config.yaml", stage_modules=STAGES)
        return ctx["evaluation"]

    def test_yaml_judge_concurrency_is_parsed(self) -> None:
        self.assertEqual(self._context({"concurrency": 6}).judge_concurrency, 6)

    def test_yaml_default_decouples_from_inference(self) -> None:
        evaluation = self._context({})
        self.assertEqual(evaluation.inference.concurrency, 1)
        self.assertEqual(evaluation.judge_concurrency, DEFAULT_INFERENCE_CONCURRENCY)

    def test_invalid_judge_concurrency_is_rejected(self) -> None:
        with self.assertRaises((ValueError, ConfigError)):
            self._context({"concurrency": 0})


class BenchmarkScriptConcurrencyTest(unittest.TestCase):
    """scripts/benchmark.py records a (test_set, concurrency) data point.

    It writes only pipeline.inference.concurrency into the generated config, so
    it must also pass --concurrency to run_pipeline; otherwise the judge runs on
    its derived default and the recorded point is labelled with a fan-out the
    run never used.
    """

    def test_benchmark_pins_both_stages_via_run_pipeline(self) -> None:
        import ast
        from pathlib import Path

        source = Path(__file__).resolve().parents[1] / "scripts" / "benchmark.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and getattr(node.func, "id", getattr(node.func, "attr", None)) == "run_pipeline"
        ]
        self.assertTrue(calls, "benchmark.py no longer calls run_pipeline")
        for call in calls:
            self.assertIn(
                "concurrency",
                [kw.arg for kw in call.keywords],
                f"run_pipeline call at line {call.lineno} must pass concurrency=",
            )


class CheckpointJudgeParityTest(unittest.TestCase):
    """scripts/turn_checkpoint_judge.py only ever calls the judge model.

    It resolves its own fan-out instead of using EvaluationConfig, so the two
    implementations must agree or the script silently drifts from the stage.
    This exercises the REAL loader, not a reimplementation of it.
    """

    @staticmethod
    def _load_script_module():
        import importlib.util
        import sys
        from pathlib import Path

        path = Path(__file__).resolve().parents[1] / "scripts" / "turn_checkpoint_judge.py"
        spec = importlib.util.spec_from_file_location("_tcj_parity", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules["_tcj_parity"] = module
        spec.loader.exec_module(module)
        return module

    def test_checkpoint_loader_matches_evaluation_judge_concurrency(self) -> None:
        import tempfile
        from pathlib import Path

        import yaml

        script = self._load_script_module()
        cases = [
            # (inference.concurrency, judge.n, explicit judge.concurrency)
            (1, 1, None),
            (1, 3, None),
            (24, 1, None),
            (24, 3, None),
            (1, 25, None),
            (1, 3, 6),
            (24, 1, 2),
        ]
        for inference_concurrency, judge_n, judge_concurrency in cases:
            with self.subTest(inference=inference_concurrency, n=judge_n, judge=judge_concurrency):
                judge_stage: dict[str, object] = {
                    "n": judge_n,
                    "model": {"name": "azure/gpt-5.4"},
                    "dimensions": {
                        "policy_violation": {
                            "description": "d",
                            "rubric": "true = x\nfalse = y",
                        }
                    },
                }
                if judge_concurrency is not None:
                    judge_stage["concurrency"] = judge_concurrency

                expected = EvaluationConfig(
                    judge=JudgeConfig(
                        model=ModelConfig(name="azure/gpt-5.4"),
                        n=judge_n,
                        concurrency=judge_concurrency,
                    ),
                    inference=InferenceConfig(concurrency=inference_concurrency),
                ).judge_concurrency

                with tempfile.TemporaryDirectory() as tmp:
                    config_path = Path(tmp) / "config.yaml"
                    config_path.write_text(
                        yaml.safe_dump(
                            {
                                "pipeline": {
                                    "inference": {"concurrency": inference_concurrency},
                                    "judge": judge_stage,
                                }
                            },
                            sort_keys=False,
                        ),
                        encoding="utf-8",
                    )
                    resolved = script.load_checkpoint_judge_config(config_path)

                self.assertEqual(resolved.concurrency, expected)


if __name__ == "__main__":
    unittest.main()
