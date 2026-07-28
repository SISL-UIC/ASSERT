from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib
import numpy as np
import yaml

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parent
ARTIFACTS_ROOT = ROOT.parent
REPO_ROOT = ARTIFACTS_ROOT.parent
DATA_PATH = ROOT / "comparison_data.csv"
REPORT_PATH = ROOT / "report.md"
PLOTS_DIR = ROOT / "plots"

SOURCE_KEYS = ("v1", "v2")
SOURCE_LABELS = {"v1": "Skill-v1", "v2": "Skill-v2"}
SOURCE_COLORS = {"v1": "#315D80", "v2": "#D4553F"}
ADVERSARIAL_COLORS = ("#D8E3E8", "#86A9B7", "#E1B866", "#D9784A", "#9E3D36")
METRICS_PATHS = {
    "v1": ARTIFACTS_ROOT / "harm-template-experiment-skill-v1" / "analysis" / "metrics.json",
    "v2": ARTIFACTS_ROOT / "harm-template-experiment-skill-v2" / "analysis" / "metrics.json",
}
HARMS = (
    "violent_content",
    "relationship_entanglement",
    "imminent_crisis_management",
)
HARM_LABELS = {
    "violent_content": "Violent\ncontent",
    "relationship_entanglement": "Relationship\nentanglement",
    "imminent_crisis_management": "Imminent crisis\nmanagement",
}

BACKGROUND = "#FBFAF6"
GRID = "#D9D6CD"
TEXT = "#17212B"
MUTED = "#5F6872"
ADVERSARIAL_RANGES = ("0-20", "21-40", "41-60", "61-80", "81-100")
CSV_FIELDS = (
    "source_key",
    "source_label",
    "source_report",
    "embedded_experiment",
    "methodology_version",
    "harm",
    "source_configs",
    "total_dimensions",
    "repeated_removed",
    "unique_dimensions",
    "relevant_unique_dimensions",
    "perfect_relevance_dimensions",
    "uniqueness_rate",
    "relevant_unique_rate",
    "perfect_relevance_rate",
    "run_counts",
    "mean_dimensions",
    "population_variance",
    "sample_variance",
    "embedding_diversity",
    "llm_pair_diversity",
    "llm_direct_diversity",
    "relevance_mean",
    "relevance_min",
    "within_run_redundant_pairs",
    "adversarial_mean",
    "adversarial_population_variance",
    "adversarial_sample_variance",
    "adversarial_min",
    "adversarial_max",
    "adversarial_0_20_count",
    "adversarial_0_20_rate",
    "adversarial_21_40_count",
    "adversarial_21_40_rate",
    "adversarial_41_60_count",
    "adversarial_41_60_rate",
    "adversarial_61_80_count",
    "adversarial_61_80_rate",
    "adversarial_81_100_count",
    "adversarial_81_100_rate",
    "coverage_score",
    "coverage_rationale",
    "coverage_gap_count",
    "coverage_high_priority_gap_count",
    "coverage_medium_priority_gap_count",
    "coverage_low_priority_gap_count",
    "coverage_weak_points_json",
)


def build_rows(
    metrics_paths: dict[str, Path] | None = None,
) -> dict[tuple[str, str], dict[str, object]]:
    paths = metrics_paths or METRICS_PATHS
    if set(paths) != set(SOURCE_KEYS):
        raise ValueError(
            f"Expected metrics paths for {list(SOURCE_KEYS)}, found {sorted(paths)}"
        )

    parsed: dict[tuple[str, str], dict[str, object]] = {}
    for source in SOURCE_KEYS:
        metrics_path = paths[source]
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        methodology = metrics["methodology"]
        harm_results = metrics["harm_results"]
        unique_metrics = metrics["global_unique_metrics"]
        run_results = metrics["run_results"]

        for harm in HARMS:
            harm_result = harm_results[harm]
            unique_result = unique_metrics[harm]
            perfect_relevance = next(
                item
                for item in unique_result["relevance_threshold_metrics"]
                if item["threshold_percent"] == 100
            )
            adversarial = harm_result["adversarial"]
            weak_coverage_points = list(
                harm_result["coverage"].get("weak_coverage_points", [])
            )
            distribution = {
                item["range"]: item for item in adversarial["distribution"]
            }
            if set(distribution) != set(ADVERSARIAL_RANGES):
                raise ValueError(
                    f"Unexpected adversarial ranges for {source}/{harm}: "
                    f"{sorted(distribution)}"
                )
            parsed[(source, harm)] = {
                "source_key": source,
                "source_label": SOURCE_LABELS[source],
                "source_report": metrics_path.with_name("report.md")
                .relative_to(REPO_ROOT)
                .as_posix(),
                "embedded_experiment": methodology["experiment_dir"],
                "methodology_version": methodology["version"],
                "harm": harm,
                "source_configs": int(metrics["totals"]["source_config_count"]),
                "total_dimensions": int(unique_result["total_dimension_count"]),
                "repeated_removed": int(
                    unique_result["repeated_dimension_count_removed"]
                ),
                "unique_dimensions": int(unique_result["unique_dimension_count"]),
                "relevant_unique_dimensions": int(
                    unique_result["relevant_unique_dimension_count"]
                ),
                "perfect_relevance_dimensions": int(
                    perfect_relevance["exact_score_count"]
                ),
                "uniqueness_rate": float(unique_result["unique_over_total_ratio"]),
                "relevant_unique_rate": float(
                    unique_result["relevant_unique_over_unique_ratio"]
                ),
                "perfect_relevance_rate": float(
                    perfect_relevance["exact_score_ratio_over_unique"]
                ),
                "run_counts": tuple(harm_result["run_dimension_counts"]),
                "mean_dimensions": float(harm_result["average_dimension_count"]),
                "population_variance": float(
                    harm_result["population_variance_dimension_count"]
                ),
                "sample_variance": float(
                    harm_result["sample_variance_dimension_count"]
                ),
                "embedding_diversity": float(
                    harm_result["union_embedding_pairwise_diversity"]
                ),
                "llm_pair_diversity": float(
                    harm_result["union_llm_pairwise_diversity"]
                ),
                "llm_direct_diversity": float(
                    harm_result["union_llm_direct_diversity"]
                ),
                "relevance_mean": float(harm_result["relevance"]["mean"]),
                "relevance_min": int(harm_result["relevance"]["minimum"]),
                "within_run_redundant_pairs": sum(
                    int(values["redundant_pair_count"])
                    for values in run_results[harm].values()
                ),
                "adversarial_mean": float(adversarial["mean"]),
                "adversarial_population_variance": float(
                    adversarial["population_variance"]
                ),
                "adversarial_sample_variance": float(
                    adversarial["sample_variance"]
                ),
                "adversarial_min": int(adversarial["minimum"]),
                "adversarial_max": int(adversarial["maximum"]),
                "adversarial_distribution_counts": tuple(
                    int(distribution[score_range]["count"])
                    for score_range in ADVERSARIAL_RANGES
                ),
                "adversarial_distribution_rates": tuple(
                    float(distribution[score_range]["ratio"])
                    for score_range in ADVERSARIAL_RANGES
                ),
                "coverage_score": int(harm_result["coverage"]["score"]),
                "coverage_rationale": str(harm_result["coverage"]["rationale"]),
                "coverage_weak_points": weak_coverage_points,
                "coverage_gap_count": len(weak_coverage_points),
                "coverage_high_priority_gap_count": sum(
                    point["priority"] == "high" for point in weak_coverage_points
                ),
                "coverage_medium_priority_gap_count": sum(
                    point["priority"] == "medium" for point in weak_coverage_points
                ),
                "coverage_low_priority_gap_count": sum(
                    point["priority"] == "low" for point in weak_coverage_points
                ),
            }

    expected = {(source, harm) for source in SOURCE_KEYS for harm in HARMS}
    if set(parsed) != expected:
        raise ValueError(f"Expected rows {sorted(expected)}, found {sorted(parsed)}")
    return parsed


def write_comparison_data(
    rows: dict[tuple[str, str], dict[str, object]],
    output_path: Path = DATA_PATH,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for source in SOURCE_KEYS:
            for harm in HARMS:
                source_row = rows[(source, harm)]
                serialized = {
                    field: source_row[field]
                    for field in CSV_FIELDS
                    if field in source_row
                }
                serialized["run_counts"] = "/".join(
                    str(value) for value in source_row["run_counts"]
                )
                serialized["coverage_weak_points_json"] = json.dumps(
                    source_row["coverage_weak_points"], separators=(",", ":")
                )
                counts = source_row["adversarial_distribution_counts"]
                rates = source_row["adversarial_distribution_rates"]
                for score_range, count, rate in zip(
                    ADVERSARIAL_RANGES, counts, rates, strict=True
                ):
                    field_suffix = score_range.replace("-", "_")
                    serialized[f"adversarial_{field_suffix}_count"] = count
                    serialized[f"adversarial_{field_suffix}_rate"] = rate
                writer.writerow(serialized)
    try:
        display_path = output_path.relative_to(ROOT)
    except ValueError:
        display_path = output_path
    print(f"wrote {display_path}")


def aggregate_sources(
    rows: dict[tuple[str, str], dict[str, object]],
) -> dict[str, dict[str, float]]:
    totals: dict[str, dict[str, float]] = {}
    for source in SOURCE_KEYS:
        source_rows = [rows[(source, harm)] for harm in HARMS]
        total_dimensions = sum(int(row["total_dimensions"]) for row in source_rows)
        unique_dimensions = sum(int(row["unique_dimensions"]) for row in source_rows)
        relevant_dimensions = sum(
            int(row["relevant_unique_dimensions"]) for row in source_rows
        )
        perfect_dimensions = sum(
            int(row["perfect_relevance_dimensions"]) for row in source_rows
        )
        totals[source] = {
            "source_configs": int(source_rows[0]["source_configs"]),
            "dimensions": total_dimensions,
            "repeated": sum(int(row["repeated_removed"]) for row in source_rows),
            "unique": unique_dimensions,
            "relevant": relevant_dimensions,
            "perfect": perfect_dimensions,
            "unique_rate": unique_dimensions / total_dimensions * 100,
            "relevant_rate": relevant_dimensions / unique_dimensions * 100,
            "perfect_rate": perfect_dimensions / unique_dimensions * 100,
            "embedding": sum(
                float(row["embedding_diversity"]) for row in source_rows
            )
            / len(HARMS),
            "llm_pair": sum(
                float(row["llm_pair_diversity"]) for row in source_rows
            )
            / len(HARMS),
            "llm_direct": sum(
                float(row["llm_direct_diversity"]) for row in source_rows
            )
            / len(HARMS),
            "relevance": sum(float(row["relevance_mean"]) for row in source_rows)
            / len(HARMS),
            "adversarial": sum(
                float(row["adversarial_mean"]) * int(row["total_dimensions"])
                for row in source_rows
            )
            / total_dimensions,
            "coverage": sum(float(row["coverage_score"]) for row in source_rows)
            / len(HARMS),
        }
    return totals


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    def cell(value: object) -> str:
        return " ".join(str(value).split()).replace("|", "\\|")

    lines = [
        "| " + " | ".join(cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend(
        "| " + " | ".join(cell(value) for value in row) + " |" for row in rows
    )
    return "\n".join(lines)


def harm_label(harm: str) -> str:
    return HARM_LABELS[harm].replace("\n", " ")


def write_report(
    rows: dict[tuple[str, str], dict[str, object]],
    output_path: Path = REPORT_PATH,
) -> None:
    totals = aggregate_sources(rows)
    v1 = totals["v1"]
    v2 = totals["v2"]
    overall_rows = [
        ["Source configs", f"{v1['source_configs']:.0f}", f"{v2['source_configs']:.0f}", f"{v2['source_configs'] - v1['source_configs']:+.0f}"],
        ["Dimension instances", f"{v1['dimensions']:.0f}", f"{v2['dimensions']:.0f}", f"{v2['dimensions'] - v1['dimensions']:+.0f}"],
        ["Repeated dimensions removed", f"{v1['repeated']:.0f}", f"{v2['repeated']:.0f}", f"{v2['repeated'] - v1['repeated']:+.0f}"],
        ["Globally unique dimensions", f"{v1['unique']:.0f}", f"{v2['unique']:.0f}", f"{v2['unique'] - v1['unique']:+.0f}"],
        ["Relevant unique dimensions", f"{v1['relevant']:.0f}", f"{v2['relevant']:.0f}", f"{v2['relevant'] - v1['relevant']:+.0f}"],
        ["Perfect-relevance unique dimensions", f"{v1['perfect']:.0f}", f"{v2['perfect']:.0f}", f"{v2['perfect'] - v1['perfect']:+.0f}"],
        ["Unique / total", f"{v1['unique_rate']:.1f}%", f"{v2['unique_rate']:.1f}%", f"{v2['unique_rate'] - v1['unique_rate']:+.1f} pp"],
        ["Relevance@75 / unique", f"{v1['relevant_rate']:.1f}%", f"{v2['relevant_rate']:.1f}%", f"{v2['relevant_rate'] - v1['relevant_rate']:+.1f} pp"],
        ["Relevance@100 / unique", f"{v1['perfect_rate']:.1f}%", f"{v2['perfect_rate']:.1f}%", f"{v2['perfect_rate'] - v1['perfect_rate']:+.1f} pp"],
        ["Macro embedding diversity", f"{v1['embedding']:.4f}", f"{v2['embedding']:.4f}", f"{v2['embedding'] - v1['embedding']:+.4f}"],
        ["Macro LLM pair diversity", f"{v1['llm_pair']:.4f}", f"{v2['llm_pair']:.4f}", f"{v2['llm_pair'] - v1['llm_pair']:+.4f}"],
        ["Macro LLM direct diversity", f"{v1['llm_direct']:.4f}", f"{v2['llm_direct']:.4f}", f"{v2['llm_direct'] - v1['llm_direct']:+.4f}"],
        ["Macro relevance (0-4)", f"{v1['relevance']:.4f}", f"{v2['relevance']:.4f}", f"{v2['relevance'] - v1['relevance']:+.4f}"],
        ["All-dimension adversarial mean (0-100)", f"{v1['adversarial']:.4f}", f"{v2['adversarial']:.4f}", f"{v2['adversarial'] - v1['adversarial']:+.4f}"],
        ["Macro scenario-space coverage (0-100)", f"{v1['coverage']:.4f}", f"{v2['coverage']:.4f}", f"{v2['coverage'] - v1['coverage']:+.4f}"],
    ]

    dimension_rows = []
    relevance_rows = []
    diversity_rows = []
    adversarial_rows = []
    distribution_rows = []
    coverage_rows = []
    run_rows = []
    coverage_details = []
    coverage_gap_rows = []
    coverage_suggestion_sections = []
    for harm in HARMS:
        left = rows[("v1", harm)]
        right = rows[("v2", harm)]
        label = harm_label(harm)
        dimension_rows.append(
            [
                label,
                left["total_dimensions"],
                right["total_dimensions"],
                f"{int(right['total_dimensions']) - int(left['total_dimensions']):+d}",
                left["unique_dimensions"],
                right["unique_dimensions"],
                f"{int(right['unique_dimensions']) - int(left['unique_dimensions']):+d}",
                left["relevant_unique_dimensions"],
                right["relevant_unique_dimensions"],
            ]
        )
        relevance_rows.append(
            [
                label,
                f"{float(left['uniqueness_rate']) * 100:.1f}%",
                f"{float(right['uniqueness_rate']) * 100:.1f}%",
                f"{(float(right['uniqueness_rate']) - float(left['uniqueness_rate'])) * 100:+.1f} pp",
                f"{float(left['relevant_unique_rate']) * 100:.1f}%",
                f"{float(right['relevant_unique_rate']) * 100:.1f}%",
                f"{(float(right['relevant_unique_rate']) - float(left['relevant_unique_rate'])) * 100:+.1f} pp",
                f"{float(left['perfect_relevance_rate']) * 100:.1f}%",
                f"{float(right['perfect_relevance_rate']) * 100:.1f}%",
                f"{(float(right['perfect_relevance_rate']) - float(left['perfect_relevance_rate'])) * 100:+.1f} pp",
            ]
        )
        for metric, field in (
            ("Embedding diversity", "embedding_diversity"),
            ("LLM pair diversity", "llm_pair_diversity"),
            ("LLM direct diversity", "llm_direct_diversity"),
            ("Relevance mean (0-4)", "relevance_mean"),
        ):
            left_value = float(left[field])
            right_value = float(right[field])
            diversity_rows.append(
                [label, metric, f"{left_value:.4f}", f"{right_value:.4f}", f"{right_value - left_value:+.4f}"]
            )
        for source, row in (("v1", left), ("v2", right)):
            adversarial_rows.append(
                [
                    label,
                    SOURCE_LABELS[source],
                    f"{float(row['adversarial_mean']):.4f}",
                    f"{float(row['adversarial_population_variance']):.4f}",
                    f"{float(row['adversarial_sample_variance']):.4f}",
                    row["adversarial_min"],
                    row["adversarial_max"],
                ]
            )
            distribution_rows.append(
                [label, SOURCE_LABELS[source]]
                + [
                    f"{count} ({float(rate) * 100:.1f}%)"
                    for count, rate in zip(
                        row["adversarial_distribution_counts"],
                        row["adversarial_distribution_rates"],
                        strict=True,
                    )
                ]
            )
        coverage_rows.append(
            [
                label,
                left["coverage_score"],
                right["coverage_score"],
                f"{int(right['coverage_score']) - int(left['coverage_score']):+d}",
            ]
        )
        coverage_details.append(
            f"### {label}\n\n"
            f"- **{SOURCE_LABELS['v1']} ({left['coverage_score']}):** "
            f"{' '.join(str(left['coverage_rationale']).split())}\n"
            f"- **{SOURCE_LABELS['v2']} ({right['coverage_score']}):** "
            f"{' '.join(str(right['coverage_rationale']).split())}"
        )
        for source, row in (("v1", left), ("v2", right)):
            weak_points = row["coverage_weak_points"]
            if not weak_points:
                continue
            dimensions = []
            for weak_point in weak_points:
                dimension = weak_point["suggested_dimension"]
                dimensions.append(dimension)
                coverage_gap_rows.append(
                    [
                        label,
                        SOURCE_LABELS[source],
                        weak_point["priority"],
                        weak_point["gap_type"],
                        weak_point["weak_coverage_point"],
                        dimension["name"],
                    ]
                )
            suggestion_yaml = yaml.safe_dump(
                {
                    "pipeline": {
                        "test_set": {"stratify": {"dimensions": dimensions}}
                    }
                },
                sort_keys=False,
                allow_unicode=False,
            ).strip()
            coverage_suggestion_sections.append(
                f"### {label} - {SOURCE_LABELS[source]}\n\n"
                f"```yaml\n{suggestion_yaml}\n```"
            )
        run_rows.append(
            [
                label,
                "/".join(str(value) for value in left["run_counts"]),
                "/".join(str(value) for value in right["run_counts"]),
                f"{float(left['population_variance']):.4f}",
                f"{float(right['population_variance']):.4f}",
                left["within_run_redundant_pairs"],
                right["within_run_redundant_pairs"],
            ]
        )

    source_lines = []
    for source in SOURCE_KEYS:
        row = rows[(source, HARMS[0])]
        report_target = Path(str(row["source_report"])).relative_to("artifacts")
        source_lines.append(
            f"- **{SOURCE_LABELS[source]}:** "
            f"[`{row['embedded_experiment']}`](../{report_target.as_posix()}), "
            f"methodology `{row['methodology_version']}`."
        )
    coverage_detail_text = "\n\n".join(coverage_details)
    if coverage_gap_rows:
        coverage_gap_text = (
            markdown_table(
                [
                    "Harm",
                    "Source",
                    "Priority",
                    "Gap type",
                    "Weak coverage point",
                    "Suggested dimension",
                ],
                coverage_gap_rows,
            )
            + "\n\n"
            + "\n\n".join(coverage_suggestion_sections)
        )
    else:
        coverage_gap_text = (
            "No structured weak points are present in the current source artifacts. "
            "Regenerate both analyses with methodology `3.3.0` or later to populate "
            "this section."
        )

    report = f"""# Harm-template experiment comparison

This report is generated directly from the two current `metrics.json` artifacts.
Counts are summed across harms where stated; macro averages are unweighted across
the three harms. Every delta is Skill-v2 minus Skill-v1.

## Sources

{chr(10).join(source_lines)}

## Overall comparison

{markdown_table(["Measure", "Skill-v1", "Skill-v2", "Delta"], overall_rows)}

![Overall Skill-v1 and Skill-v2 comparison](plots/overall_comparison.png)

The score panel normalizes metrics to their own scales for the shared axis; labels
above bars show original values. The overall adversarial mean is weighted across
all dimension instances, while overall scenario coverage is a macro average over
the three harm-level judgments.

## Dimension counts by harm

{markdown_table(
    ["Harm", "V1 total", "V2 total", "Delta", "V1 unique", "V2 unique", "Delta", "V1 relevant unique", "V2 relevant unique"],
    dimension_rows,
)}

![Dimension counts by harm for Skill-v1 and Skill-v2](plots/coverage_by_harm.png)

## Relevance rates

{markdown_table(
    ["Harm", "V1 unique / total", "V2 unique / total", "Delta", "V1 relevant / unique", "V2 relevant / unique", "Delta", "V1 perfect / unique", "V2 perfect / unique", "Delta"],
    relevance_rows,
)}

![Relevance rates by harm for Skill-v1 and Skill-v2](plots/relevance_rates.png)

## Diversity and mean relevance

{markdown_table(["Harm", "Metric", "Skill-v1", "Skill-v2", "Delta"], diversity_rows)}

![Diversity and mean relevance by harm](plots/diversity_and_relevance.png)

## Expected adversarial pressure

These are prospective `0-100` judgments of how strongly cases along each
dimension may pressure a model into harmful output, not observed attack-success
rates. Variances describe the complete generated dimension set for each harm.

{markdown_table(
    ["Harm", "Source", "Mean", "Population variance", "Sample variance", "Minimum", "Maximum"],
    adversarial_rows,
)}

{markdown_table(["Harm", "Source", *ADVERSARIAL_RANGES], distribution_rows)}

Distribution cells show `count (share of that harm's dimensions)`.

![Adversarial mean, variance, and score distributions](plots/adversarial_pressure.png)

## Canonical harm scenario-space coverage

Coverage is a grounded `0-100` judgment of the conceptual scenario space
expressible by each union of dimensions after discounting duplication and gaps.
It is not a literal fraction of every possible prompt or executed test-case
coverage.

{markdown_table(["Harm", "Skill-v1", "Skill-v2", "Delta"], coverage_rows)}

![Canonical harm scenario-space coverage](plots/scenario_space_coverage.png)

{coverage_detail_text}

## Prioritized weak coverage points

Each item is grounded in the canonical harm definition and includes a proposed
dimension. YAML blocks are shaped for insertion or adaptation at
`pipeline.test_set.stratify.dimensions`.

{coverage_gap_text}

## Run consistency

{markdown_table(
    ["Harm", "V1 run counts", "V2 run counts", "V1 population variance", "V2 population variance", "V1 redundant pairs", "V2 redundant pairs"],
    run_rows,
)}

![Run counts, population variance, and redundant pairs](plots/run_consistency.png)

## Interpretation and limitations

- Skill-v2 has more dimension instances and broader canonical scenario-space
  coverage for every harm, but count alone is not evidence of test quality.
- Adversarial pressure, coverage, diversity, and relevance are LLM judgments, not
  ground truth. The source reports retain prompts, model deployment, and raw
  judgments for audit.
- Adversarial means compare generated dimension instances and therefore weight
  repeated concepts. Distribution tables expose that shape rather than reducing
  the comparison to a mean alone.
- With three generation runs per harm, run-count variance is descriptive and
  unstable. Adversarial variance describes dimensions, not generation-run
  consistency.
"""
    output_path.write_text(report, encoding="utf-8")
    try:
        display_path = output_path.relative_to(ROOT)
    except ValueError:
        display_path = output_path
    print(f"wrote {display_path}")


def configure_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": BACKGROUND,
            "axes.facecolor": BACKGROUND,
            "axes.edgecolor": GRID,
            "axes.labelcolor": TEXT,
            "axes.titlecolor": TEXT,
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "text.color": TEXT,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
        }
    )


def style_axis(axis: plt.Axes) -> None:
    axis.grid(axis="y", color=GRID, linewidth=0.8, alpha=0.8)
    axis.set_axisbelow(True)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["left"].set_color(GRID)
    axis.spines["bottom"].set_color(GRID)


def add_grouped_bars(
    axis: plt.Axes,
    categories: list[str],
    values: dict[str, list[float]],
    *,
    formatter,
    ylim: tuple[float, float],
    title: str,
    ylabel: str = "",
    raw_labels: dict[str, list[str]] | None = None,
) -> None:
    positions = np.arange(len(categories))
    width = 0.36
    for index, source in enumerate(SOURCE_KEYS):
        offset = (index - 0.5) * width
        bars = axis.bar(
            positions + offset,
            values[source],
            width,
            color=SOURCE_COLORS[source],
            label=SOURCE_LABELS[source],
        )
        labels = raw_labels[source] if raw_labels else [formatter(value) for value in values[source]]
        axis.bar_label(bars, labels=labels, padding=3, fontsize=8, color=TEXT)

    axis.set_xticks(positions, categories)
    axis.set_ylim(*ylim)
    axis.set_title(title, fontsize=12, fontweight="bold", pad=12)
    axis.set_ylabel(ylabel)
    style_axis(axis)


def save_figure(figure: plt.Figure, filename: str) -> None:
    output_path = PLOTS_DIR / filename
    figure.savefig(output_path, dpi=180, bbox_inches="tight", facecolor=BACKGROUND)
    plt.close(figure)
    print(f"wrote {output_path.relative_to(ROOT)}")


def make_overall_plot(rows: dict[tuple[str, str], dict[str, object]]) -> None:
    totals = aggregate_sources(rows)

    figure, axes = plt.subplots(1, 3, figsize=(17, 6), constrained_layout=True)
    count_fields = ("source_configs", "dimensions", "repeated", "unique", "relevant", "perfect")
    add_grouped_bars(
        axes[0],
        ["Source\nconfigs", "Dimension\ninstances", "Repeated\nremoved", "Globally\nunique", "Relevant\nunique", "Perfect\nrelevance"],
        {source: [totals[source][field] for field in count_fields] for source in SOURCE_KEYS},
        formatter=lambda value: f"{value:.0f}",
        ylim=(0, 88),
        title="Counts",
        ylabel="Count",
    )

    rate_fields = ("unique_rate", "relevant_rate", "perfect_rate")
    add_grouped_bars(
        axes[1],
        ["Unique /\ntotal", "Relevance@75 /\nunique", "Relevance@100 /\nunique"],
        {source: [totals[source][field] for field in rate_fields] for source in SOURCE_KEYS},
        formatter=lambda value: f"{value:.1f}%",
        ylim=(0, 112),
        title="Rates",
        ylabel="Percent",
    )

    score_fields = ("embedding", "llm_pair", "relevance", "adversarial", "coverage")
    raw_scores = {source: [totals[source][field] for field in score_fields] for source in SOURCE_KEYS}
    normalized_scores = {
        source: [
            raw_scores[source][0] * 100,
            raw_scores[source][1] * 100,
            raw_scores[source][2] / 4 * 100,
            raw_scores[source][3],
            raw_scores[source][4],
        ]
        for source in SOURCE_KEYS
    }
    add_grouped_bars(
        axes[2],
        [
            "Embedding\ndiversity",
            "LLM pair\ndiversity",
            "Relevance\nmean",
            "Adversarial\nmean",
            "Scenario\ncoverage",
        ],
        normalized_scores,
        formatter=lambda value: f"{value:.1f}%",
        ylim=(0, 108),
        title="Scores normalized to their scale",
        ylabel="Percent of scale",
        raw_labels={source: [f"{value:.4f}" for value in raw_scores[source]] for source in SOURCE_KEYS},
    )

    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.05))
    figure.suptitle("Overall comparison", fontsize=18, fontweight="bold", y=1.03)
    save_figure(figure, "overall_comparison.png")


def make_coverage_plot(rows: dict[tuple[str, str], dict[str, object]]) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(16, 5.5), constrained_layout=True)
    categories = [HARM_LABELS[harm] for harm in HARMS]
    metrics = (
        ("total_dimensions", "Total dimensions", (0, 31)),
        ("unique_dimensions", "Unique dimensions", (0, 27)),
        ("relevant_unique_dimensions", "Relevant unique dimensions", (0, 27)),
    )
    for axis, (field, title, ylim) in zip(axes, metrics, strict=True):
        add_grouped_bars(
            axis,
            categories,
            {source: [float(rows[(source, harm)][field]) for harm in HARMS] for source in SOURCE_KEYS},
            formatter=lambda value: f"{value:.0f}",
            ylim=ylim,
            title=title,
            ylabel="Count",
        )

    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.06))
    figure.suptitle("Dimension counts by harm", fontsize=18, fontweight="bold", y=1.03)
    save_figure(figure, "coverage_by_harm.png")


def make_relevance_rates_plot(rows: dict[tuple[str, str], dict[str, object]]) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(16, 5.5), constrained_layout=True)
    categories = [HARM_LABELS[harm] for harm in HARMS]
    metrics = (
        ("uniqueness_rate", "Unique / total"),
        ("relevant_unique_rate", "Relevance@75 / unique"),
        ("perfect_relevance_rate", "Relevance@100 / unique"),
    )
    for axis, (field, title) in zip(axes, metrics, strict=True):
        add_grouped_bars(
            axis,
            categories,
            {
                source: [float(rows[(source, harm)][field]) * 100 for harm in HARMS]
                for source in SOURCE_KEYS
            },
            formatter=lambda value: f"{value:.1f}%",
            ylim=(0, 112),
            title=title,
            ylabel="Percent",
        )

    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.06))
    figure.suptitle("Relevance rates by harm", fontsize=18, fontweight="bold", y=1.03)
    save_figure(figure, "relevance_rates.png")


def make_diversity_relevance_plot(rows: dict[tuple[str, str], dict[str, object]]) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(16, 5.5), constrained_layout=True)
    categories = [HARM_LABELS[harm] for harm in HARMS]
    metrics = (
        ("embedding_diversity", "Embedding diversity", (0, 0.6), "Score (0-1)"),
        ("llm_pair_diversity", "LLM pair diversity", (0, 1.08), "Score (0-1)"),
        ("relevance_mean", "Relevance mean", (0, 4.35), "Score (0-4)"),
    )
    for axis, (field, title, ylim, ylabel) in zip(axes, metrics, strict=True):
        add_grouped_bars(
            axis,
            categories,
            {source: [float(rows[(source, harm)][field]) for harm in HARMS] for source in SOURCE_KEYS},
            formatter=lambda value: f"{value:.4f}",
            ylim=ylim,
            title=title,
            ylabel=ylabel,
        )

    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.06))
    figure.suptitle("Diversity and mean relevance", fontsize=18, fontweight="bold", y=1.03)
    save_figure(figure, "diversity_and_relevance.png")


def make_adversarial_plot(rows: dict[tuple[str, str], dict[str, object]]) -> None:
    figure = plt.figure(figsize=(16, 10), constrained_layout=True)
    grid = figure.add_gridspec(2, 2, height_ratios=(0.9, 1.25))
    categories = [HARM_LABELS[harm] for harm in HARMS]

    mean_axis = figure.add_subplot(grid[0, 0])
    add_grouped_bars(
        mean_axis,
        categories,
        {
            source: [float(rows[(source, harm)]["adversarial_mean"]) for harm in HARMS]
            for source in SOURCE_KEYS
        },
        formatter=lambda value: f"{value:.1f}",
        ylim=(0, 105),
        title="Mean expected adversarial pressure",
        ylabel="Score (0-100)",
    )

    variance_axis = figure.add_subplot(grid[0, 1])
    variance_values = {
        source: [
            float(rows[(source, harm)]["adversarial_population_variance"])
            for harm in HARMS
        ]
        for source in SOURCE_KEYS
    }
    variance_limit = max(
        value for source_values in variance_values.values() for value in source_values
    )
    add_grouped_bars(
        variance_axis,
        categories,
        variance_values,
        formatter=lambda value: f"{value:.1f}",
        ylim=(0, variance_limit * 1.18),
        title="Population variance of adversarial scores",
        ylabel="Variance",
    )

    distribution_axis = figure.add_subplot(grid[1, :])
    labels = [
        f"{HARM_LABELS[harm].replace(chr(10), ' ')} · {SOURCE_LABELS[source]}"
        for harm in HARMS
        for source in SOURCE_KEYS
    ]
    positions = np.arange(len(labels))
    left = np.zeros(len(labels))
    for range_index, (score_range, color) in enumerate(
        zip(ADVERSARIAL_RANGES, ADVERSARIAL_COLORS, strict=True)
    ):
        rates = []
        counts = []
        for harm in HARMS:
            for source in SOURCE_KEYS:
                row = rows[(source, harm)]
                rates.append(
                    float(row["adversarial_distribution_rates"][range_index]) * 100
                )
                counts.append(int(row["adversarial_distribution_counts"][range_index]))
        bars = distribution_axis.barh(
            positions,
            rates,
            left=left,
            color=color,
            label=score_range,
            edgecolor=BACKGROUND,
            linewidth=0.8,
        )
        distribution_axis.bar_label(
            bars,
            labels=[str(count) if rate >= 5 else "" for count, rate in zip(counts, rates)],
            label_type="center",
            fontsize=8,
            color=TEXT,
        )
        left += np.array(rates)
    distribution_axis.set_yticks(positions, labels)
    distribution_axis.invert_yaxis()
    distribution_axis.set_xlim(0, 100)
    distribution_axis.set_xlabel("Share of dimensions")
    distribution_axis.set_title(
        "Adversarial-score distribution (segment labels are dimension counts)",
        fontsize=12,
        fontweight="bold",
        pad=12,
    )
    distribution_axis.xaxis.set_major_formatter(lambda value, _: f"{value:.0f}%")
    distribution_axis.grid(axis="x", color=GRID, linewidth=0.8, alpha=0.8)
    distribution_axis.set_axisbelow(True)
    distribution_axis.spines["top"].set_visible(False)
    distribution_axis.spines["right"].set_visible(False)
    distribution_axis.spines["left"].set_color(GRID)
    distribution_axis.spines["bottom"].set_color(GRID)
    distribution_axis.legend(
        title="Score range", loc="lower center", bbox_to_anchor=(0.5, -0.24), ncol=5, frameon=False
    )

    mean_axis.legend(loc="upper left", ncol=2, frameon=False)
    figure.suptitle("Expected adversarial pressure", fontsize=18, fontweight="bold", y=1.03)
    save_figure(figure, "adversarial_pressure.png")


def make_scenario_coverage_plot(
    rows: dict[tuple[str, str], dict[str, object]],
) -> None:
    figure, axis = plt.subplots(figsize=(10, 5.8), constrained_layout=True)
    add_grouped_bars(
        axis,
        [HARM_LABELS[harm] for harm in HARMS],
        {
            source: [float(rows[(source, harm)]["coverage_score"]) for harm in HARMS]
            for source in SOURCE_KEYS
        },
        formatter=lambda value: f"{value:.0f}",
        ylim=(0, 105),
        title="Canonical harm scenario-space coverage",
        ylabel="Coverage score (0-100)",
    )
    axis.legend(loc="upper center", ncol=2, frameon=False)
    save_figure(figure, "scenario_space_coverage.png")


def make_run_consistency_plot(rows: dict[tuple[str, str], dict[str, object]]) -> None:
    figure = plt.figure(figsize=(16, 9.5), constrained_layout=True)
    grid = figure.add_gridspec(2, 3, height_ratios=(1, 0.9))
    run_positions = np.arange(1, 4)

    for column, harm in enumerate(HARMS):
        axis = figure.add_subplot(grid[0, column])
        for source in SOURCE_KEYS:
            values = rows[(source, harm)]["run_counts"]
            axis.plot(
                run_positions,
                values,
                marker="o",
                linewidth=2.2,
                markersize=7,
                color=SOURCE_COLORS[source],
                label=SOURCE_LABELS[source],
            )
            for x_value, y_value in zip(run_positions, values, strict=True):
                axis.annotate(
                    str(y_value),
                    (x_value, y_value),
                    xytext=(0, 8),
                    textcoords="offset points",
                    ha="center",
                    fontsize=9,
                    color=SOURCE_COLORS[source],
                )
        axis.set_xticks(run_positions, ["Run 1", "Run 2", "Run 3"])
        axis.set_ylim(0, 11.5)
        axis.set_ylabel("Dimension count")
        axis.set_title(HARM_LABELS[harm].replace("\n", " "), fontsize=12, fontweight="bold", pad=12)
        style_axis(axis)

    categories = [HARM_LABELS[harm] for harm in HARMS]
    variance_axis = figure.add_subplot(grid[1, :2])
    add_grouped_bars(
        variance_axis,
        categories,
        {
            source: [float(rows[(source, harm)]["population_variance"]) for harm in HARMS]
            for source in SOURCE_KEYS
        },
        formatter=lambda value: f"{value:.4f}",
        ylim=(0, 0.78),
        title="Population variance of run counts",
        ylabel="Variance",
    )

    redundant_axis = figure.add_subplot(grid[1, 2])
    add_grouped_bars(
        redundant_axis,
        categories,
        {
            source: [float(rows[(source, harm)]["within_run_redundant_pairs"]) for harm in HARMS]
            for source in SOURCE_KEYS
        },
        formatter=lambda value: f"{value:.0f}",
        ylim=(0, 1.25),
        title="Within-run redundant pairs",
        ylabel="Pair count",
    )

    figure.axes[0].legend(loc="upper center", ncol=2, frameon=False)
    figure.suptitle("Run consistency", fontsize=18, fontweight="bold", y=1.03)
    save_figure(figure, "run_consistency.png")


def main() -> None:
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    configure_style()
    rows = build_rows()
    write_comparison_data(rows)
    make_overall_plot(rows)
    make_coverage_plot(rows)
    make_relevance_rates_plot(rows)
    make_diversity_relevance_plot(rows)
    make_adversarial_plot(rows)
    make_scenario_coverage_plot(rows)
    make_run_consistency_plot(rows)
    write_report(rows)


if __name__ == "__main__":
    main()