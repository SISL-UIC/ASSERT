from __future__ import annotations

import importlib.util
import csv
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("generate_report_plots.py")
SPEC = importlib.util.spec_from_file_location("generate_report_plots", MODULE_PATH)
assert SPEC and SPEC.loader
plots = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plots)


class ComparisonDataTests(unittest.TestCase):
    def test_build_rows_includes_adversarial_distribution_and_coverage(self) -> None:
        rows = plots.build_rows()
        violent_v2 = rows[("v2", "violent_content")]

        self.assertEqual(violent_v2["methodology_version"], "3.2.0")
        self.assertEqual(violent_v2["adversarial_mean"], 48.555556)
        self.assertEqual(
            violent_v2["adversarial_population_variance"], 268.098765
        )
        self.assertEqual(
            violent_v2["adversarial_sample_variance"], 278.410256
        )
        self.assertEqual(violent_v2["adversarial_min"], 18)
        self.assertEqual(violent_v2["adversarial_max"], 76)
        self.assertEqual(
            violent_v2["adversarial_distribution_counts"],
            (2, 7, 11, 7, 0),
        )
        self.assertEqual(violent_v2["coverage_score"], 87)
        self.assertIn(
            "every canonical non-permissible family",
            violent_v2["coverage_rationale"],
        )

    def test_report_includes_both_new_metrics(self) -> None:
        rows = plots.build_rows()
        rows[("v2", "violent_content")]["coverage_weak_points"] = [
            {
                "gap_id": "violence_manifestation_type",
                "gap_type": "missing_scenario_family",
                "priority": "high",
                "weak_coverage_point": "Violence families are not separated.",
                "canonical_basis": "Canonical violent-content families.",
                "current_coverage_evidence": "Severity currently combines them.",
                "why_it_matters": "Each family has a distinct boundary.",
                "suggested_dimension": {
                    "name": "violence_manifestation_type",
                    "description": "The violent-content family under test.",
                    "levels": [
                        {"name": "threat", "definition": "A threat."},
                        {"name": "incitement", "definition": "Incitement."},
                    ],
                },
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "report.md"
            plots.write_report(rows, output_path)
            report = output_path.read_text(encoding="utf-8")

        self.assertIn("## Expected adversarial pressure", report)
        self.assertIn("Population variance", report)
        self.assertIn("0-20", report)
        self.assertIn("81-100", report)
        self.assertIn("## Canonical harm scenario-space coverage", report)
        self.assertIn("| Violent content | 72 | 87 | +15 |", report)
        self.assertIn("every canonical non-permissible family", report)
        self.assertIn("plots/adversarial_pressure.png", report)
        self.assertIn("plots/scenario_space_coverage.png", report)
        self.assertIn("## Prioritized weak coverage points", report)
        self.assertIn("violence_manifestation_type", report)
        self.assertIn("The violent-content family under test.", report)

    def test_comparison_csv_preserves_weak_point_suggestions(self) -> None:
        rows = plots.build_rows()
        rows[("v2", "violent_content")]["coverage_weak_points"] = [
            {
                "gap_id": "violence_manifestation_type",
                "priority": "high",
                "suggested_dimension": {
                    "name": "violence_manifestation_type",
                    "description": "The violent-content family under test.",
                    "levels": [
                        {"name": "threat", "definition": "A threat."},
                        {"name": "incitement", "definition": "Incitement."},
                    ],
                },
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "comparison.csv"
            plots.write_comparison_data(rows, output_path)
            with output_path.open(encoding="utf-8") as handle:
                saved_rows = list(csv.DictReader(handle))

        violent_v2 = next(
            row
            for row in saved_rows
            if row["source_key"] == "v2" and row["harm"] == "violent_content"
        )
        weak_points = json.loads(violent_v2["coverage_weak_points_json"])
        self.assertEqual(weak_points[0]["priority"], "high")
        self.assertEqual(
            weak_points[0]["suggested_dimension"]["name"],
            "violence_manifestation_type",
        )


if __name__ == "__main__":
    unittest.main()