#!/usr/bin/env python3
"""Analyze coverage of generated NeMo Data Designer scenarios.

This script analyzes the generated scenarios to identify coverage gaps,
distribution patterns, and quality metrics.

Usage:
    # Analyze scenarios from default location
    uv run python tools/nemo_data_designer/analyze_coverage.py

    # Analyze from custom path
    uv run python tools/nemo_data_designer/analyze_coverage.py \
        --input backend/tests/fixtures/synthetic/scenarios.parquet

    # Generate detailed report
    uv run python tools/nemo_data_designer/analyze_coverage.py --detailed

    # Export analysis to JSON
    uv run python tools/nemo_data_designer/analyze_coverage.py \
        --output coverage_analysis.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.nemo_data_designer.config import (
    COLUMN_TYPES,
    SAMPLER_COLUMNS,
    TOTAL_COLUMNS,
)

# Default input path
DEFAULT_INPUT_PATH = (
    PROJECT_ROOT / "backend" / "tests" / "fixtures" / "synthetic" / "scenarios.parquet"
)


def load_scenarios(input_path: Path) -> pd.DataFrame:
    """Load scenarios from parquet file.

    Args:
        input_path: Path to parquet file

    Returns:
        DataFrame with scenario data

    Raises:
        FileNotFoundError: If file does not exist
    """
    import pandas as pd

    if not input_path.exists():
        msg = f"Scenarios file not found: {input_path}"
        raise FileNotFoundError(msg)

    return pd.read_parquet(input_path)


def analyze_sampler_coverage(df: pd.DataFrame) -> dict[str, Any]:
    """Analyze coverage of sampler columns.

    Args:
        df: DataFrame with scenario data

    Returns:
        Dictionary with coverage analysis for each sampler column
    """
    coverage = {}

    for col in COLUMN_TYPES["samplers"]:
        if col not in df.columns:
            coverage[col] = {"error": "Column not found"}
            continue

        expected_values = SAMPLER_COLUMNS.get(col, {}).get("values", [])
        actual_values = df[col].unique().tolist()
        value_counts = df[col].value_counts().to_dict()

        # Calculate coverage metrics
        covered = [v for v in expected_values if v in actual_values]
        missing = [v for v in expected_values if v not in actual_values]
        coverage_pct = len(covered) / len(expected_values) * 100 if expected_values else 100

        # Calculate distribution evenness (coefficient of variation)
        counts = list(value_counts.values())
        if len(counts) > 1:
            mean_count = sum(counts) / len(counts)
            variance = sum((c - mean_count) ** 2 for c in counts) / len(counts)
            std_dev = variance**0.5
            cv = (std_dev / mean_count * 100) if mean_count > 0 else 0
        else:
            cv = 0

        coverage[col] = {
            "expected_values": expected_values,
            "actual_values": actual_values,
            "covered_values": covered,
            "missing_values": missing,
            "coverage_percent": round(coverage_pct, 1),
            "distribution": value_counts,
            "coefficient_of_variation": round(cv, 1),
            "min_count": min(counts) if counts else 0,
            "max_count": max(counts) if counts else 0,
        }

    return coverage


def analyze_cross_coverage(df: pd.DataFrame) -> dict[str, Any]:
    """Analyze cross-tabulation coverage between key columns.

    Args:
        df: DataFrame with scenario data

    Returns:
        Dictionary with cross-coverage analysis
    """
    cross = {}

    # Scenario type x Enrichment level
    if "scenario_type" in df.columns and "enrichment_level" in df.columns:
        combos = df.groupby(["scenario_type", "enrichment_level"]).size()
        cross["scenario_type_x_enrichment_level"] = {
            str(k): int(v) for k, v in combos.to_dict().items()
        }

        # Check for missing combinations
        expected_combos = [
            (st, el)
            for st in SAMPLER_COLUMNS["scenario_type"]["values"]
            for el in SAMPLER_COLUMNS["enrichment_level"]["values"]
        ]
        actual_combos = set(combos.index.tolist())
        missing = [c for c in expected_combos if c not in actual_combos]
        cross["scenario_type_x_enrichment_level_missing"] = [str(m) for m in missing]

    # Scenario type x Camera location
    if "scenario_type" in df.columns and "camera_location" in df.columns:
        combos = df.groupby(["scenario_type", "camera_location"]).size()
        cross["scenario_type_x_camera_location"] = {
            str(k): int(v) for k, v in combos.to_dict().items()
        }

    # Time of day x Day type
    if "time_of_day" in df.columns and "day_type" in df.columns:
        combos = df.groupby(["time_of_day", "day_type"]).size()
        cross["time_of_day_x_day_type"] = {str(k): int(v) for k, v in combos.to_dict().items()}

    return cross


def analyze_validation_quality(df: pd.DataFrame) -> dict[str, Any]:
    """Analyze validation column results.

    Args:
        df: DataFrame with scenario data

    Returns:
        Dictionary with validation quality metrics
    """
    validation = {}

    if "detection_schema_valid" in df.columns:
        valid_count = int(df["detection_schema_valid"].sum())
        validation["detection_schema"] = {
            "valid": valid_count,
            "invalid": len(df) - valid_count,
            "valid_percent": round(valid_count / len(df) * 100, 1),
        }

    if "temporal_consistency" in df.columns:
        valid_count = int(df["temporal_consistency"].sum())
        validation["temporal_consistency"] = {
            "valid": valid_count,
            "invalid": len(df) - valid_count,
            "valid_percent": round(valid_count / len(df) * 100, 1),
        }

    return validation


def analyze_complexity_distribution(df: pd.DataFrame) -> dict[str, Any]:
    """Analyze distribution of complexity scores.

    Args:
        df: DataFrame with scenario data

    Returns:
        Dictionary with complexity distribution metrics
    """
    complexity = {}

    if "complexity_score" in df.columns:
        scores = df["complexity_score"]
        complexity["statistics"] = {
            "min": float(scores.min()),
            "max": float(scores.max()),
            "mean": round(float(scores.mean()), 3),
            "median": round(float(scores.median()), 3),
            "std": round(float(scores.std()), 3),
        }

        # Bin into categories
        bins = [0, 0.25, 0.5, 0.75, 1.0]
        labels = ["low", "medium", "high", "very_high"]
        try:
            import pandas as pd

            binned = pd.cut(scores, bins=bins, labels=labels, include_lowest=True)
            complexity["distribution"] = binned.value_counts().to_dict()
        except Exception:
            complexity["distribution"] = "Unable to bin scores"

    return complexity


def analyze_judge_scores(df: pd.DataFrame) -> dict[str, Any]:
    """Analyze LLM-Judge score distribution.

    Args:
        df: DataFrame with scenario data

    Returns:
        Dictionary with judge score analysis
    """
    judge = {}

    judge_cols = COLUMN_TYPES.get("llm_judge", [])
    available_cols = [c for c in judge_cols if c in df.columns]

    if not available_cols:
        return {"error": "No LLM-Judge columns found"}

    for col in available_cols:
        scores = df[col]
        judge[col] = {
            "mean": round(float(scores.mean()), 2),
            "min": int(scores.min()),
            "max": int(scores.max()),
            "distribution": scores.value_counts().sort_index().to_dict(),
        }

    # Calculate aggregate score
    if len(available_cols) == 6:  # All judge columns present
        total_scores = df[available_cols].sum(axis=1)
        judge["aggregate"] = {
            "mean_total": round(float(total_scores.mean()), 2),
            "min_total": int(total_scores.min()),
            "max_total": int(total_scores.max()),
        }

    return judge


def analyze_embedding_coverage(df: pd.DataFrame) -> dict[str, Any]:
    """Analyze embedding column status.

    Args:
        df: DataFrame with scenario data

    Returns:
        Dictionary with embedding coverage info
    """
    embeddings = {}

    for col in COLUMN_TYPES.get("embedding", []):
        if col in df.columns:
            has_embeddings = df[col].notna().sum()
            if has_embeddings > 0:
                # Check dimension of first non-null embedding
                first_embedding = df[col].dropna().iloc[0] if has_embeddings > 0 else None
                dim = len(first_embedding) if first_embedding is not None else 0
                embeddings[col] = {
                    "populated": int(has_embeddings),
                    "empty": len(df) - int(has_embeddings),
                    "dimension": dim,
                }
            else:
                embeddings[col] = {"populated": 0, "empty": len(df), "dimension": 0}
        else:
            embeddings[col] = {"error": "Column not found"}

    return embeddings


def identify_coverage_gaps(coverage: dict[str, Any]) -> list[str]:
    """Identify significant coverage gaps.

    Args:
        coverage: Sampler coverage analysis

    Returns:
        List of gap descriptions
    """
    gaps = []

    for col, data in coverage.items():
        if "error" in data:
            gaps.append(f"Column '{col}' not found in data")
            continue

        # Check for missing values
        if data.get("missing_values"):
            gaps.append(f"{col}: Missing values {data['missing_values']}")

        # Check for highly uneven distribution (CV > 50%)
        cv = data.get("coefficient_of_variation", 0)
        if cv > 50:
            gaps.append(f"{col}: Highly uneven distribution (CV={cv}%)")

        # Check for low minimum counts
        min_count = data.get("min_count", 0)
        max_count = data.get("max_count", 0)
        if min_count > 0 and max_count > 0 and min_count < max_count / 10:
            gaps.append(
                f"{col}: Some values severely underrepresented (min={min_count}, max={max_count})"
            )

    return gaps


def generate_recommendations(
    analysis: dict[str, Any],
    gaps: list[str],
) -> list[str]:
    """Generate recommendations for improving coverage.

    Args:
        analysis: Full analysis dictionary
        gaps: List of identified gaps

    Returns:
        List of recommendations
    """
    recommendations = []

    total_scenarios = analysis.get("total_scenarios", 0)

    # Check total count
    if total_scenarios < 1500:
        recommendations.append(
            f"Increase total scenarios from {total_scenarios} to at least 1,500 for better coverage"
        )

    # Check for missing cross-coverage
    cross = analysis.get("cross_coverage", {})
    if cross.get("scenario_type_x_enrichment_level_missing"):
        missing = cross["scenario_type_x_enrichment_level_missing"]
        recommendations.append(
            f"Generate scenarios for missing type/enrichment combinations: {missing[:3]}..."
        )

    # Check validation quality
    validation = analysis.get("validation", {})
    schema_valid = validation.get("detection_schema", {}).get("valid_percent", 100)
    if schema_valid < 95:
        recommendations.append(f"Fix detection schema issues (only {schema_valid}% valid)")

    temporal_valid = validation.get("temporal_consistency", {}).get("valid_percent", 100)
    if temporal_valid < 95:
        recommendations.append(f"Fix temporal consistency issues (only {temporal_valid}% valid)")

    # Check embedding coverage
    embeddings = analysis.get("embeddings", {})
    for col, data in embeddings.items():
        if isinstance(data, dict) and data.get("populated", 0) == 0 and data.get("empty", 0) > 0:
            recommendations.append(f"Generate embeddings for '{col}' (currently empty)")

    # Add gap-based recommendations
    if gaps:
        recommendations.append(f"Address {len(gaps)} coverage gaps (see gaps section)")

    if not recommendations:
        recommendations.append("Coverage looks good! No major issues detected.")

    return recommendations


def run_analysis(
    df: pd.DataFrame,
    detailed: bool = False,  # noqa: ARG001 - reserved for future detailed mode
) -> dict[str, Any]:
    """Run full coverage analysis.

    Args:
        df: DataFrame with scenario data
        detailed: Whether to include detailed analysis

    Returns:
        Dictionary with complete analysis
    """
    analysis = {
        "version": "1.0",
        "total_scenarios": len(df),
        "total_columns": len(df.columns),
        "expected_columns": TOTAL_COLUMNS,
    }

    # Column inventory
    analysis["column_inventory"] = {
        col_type: [c for c in cols if c in df.columns] for col_type, cols in COLUMN_TYPES.items()
    }

    # Sampler coverage
    analysis["sampler_coverage"] = analyze_sampler_coverage(df)

    # Cross-coverage
    analysis["cross_coverage"] = analyze_cross_coverage(df)

    # Validation quality
    analysis["validation"] = analyze_validation_quality(df)

    # Complexity distribution
    analysis["complexity"] = analyze_complexity_distribution(df)

    # Judge scores
    analysis["judge_scores"] = analyze_judge_scores(df)

    # Embedding status
    analysis["embeddings"] = analyze_embedding_coverage(df)

    # Identify gaps
    gaps = identify_coverage_gaps(analysis["sampler_coverage"])
    analysis["coverage_gaps"] = gaps

    # Generate recommendations
    analysis["recommendations"] = generate_recommendations(analysis, gaps)

    return analysis


def print_analysis(analysis: dict[str, Any], detailed: bool = False) -> None:
    """Print analysis results to console.

    Args:
        analysis: Analysis dictionary
        detailed: Whether to print detailed output
    """
    print("=" * 70)
    print("NeMo Data Designer Coverage Analysis")
    print("=" * 70)

    print(f"\nTotal scenarios: {analysis['total_scenarios']}")
    print(f"Total columns: {analysis['total_columns']} (expected: {analysis['expected_columns']})")

    print("\n### Column Inventory")
    print("-" * 40)
    for col_type, cols in analysis["column_inventory"].items():
        expected = len(COLUMN_TYPES.get(col_type, []))
        actual = len(cols)
        status = "[OK]" if actual == expected else f"[MISSING {expected - actual}]"
        print(f"  {col_type}: {actual}/{expected} {status}")

    print("\n### Sampler Coverage")
    print("-" * 40)
    for col, data in analysis["sampler_coverage"].items():
        if "error" in data:
            print(f"  {col}: ERROR - {data['error']}")
        else:
            pct = data["coverage_percent"]
            cv = data["coefficient_of_variation"]
            status = "[OK]" if pct == 100 and cv < 50 else "[REVIEW]"
            print(f"  {col}: {pct}% coverage, CV={cv}% {status}")
            if detailed:
                print(f"    Distribution: {data['distribution']}")
                if data["missing_values"]:
                    print(f"    Missing: {data['missing_values']}")

    print("\n### Validation Quality")
    print("-" * 40)
    for name, data in analysis["validation"].items():
        pct = data.get("valid_percent", 0)
        status = "[OK]" if pct >= 95 else "[NEEDS ATTENTION]"
        print(f"  {name}: {pct}% valid {status}")

    print("\n### Complexity Distribution")
    print("-" * 40)
    if "statistics" in analysis["complexity"]:
        stats = analysis["complexity"]["statistics"]
        print(f"  Mean: {stats['mean']}, Median: {stats['median']}, Std: {stats['std']}")
    if "distribution" in analysis["complexity"]:
        print(f"  Distribution: {analysis['complexity']['distribution']}")

    print("\n### Coverage Gaps")
    print("-" * 40)
    gaps = analysis["coverage_gaps"]
    if gaps:
        for gap in gaps[:10]:  # Show first 10
            print(f"  - {gap}")
        if len(gaps) > 10:
            print(f"  ... and {len(gaps) - 10} more")
    else:
        print("  No significant gaps detected")

    print("\n### Recommendations")
    print("-" * 40)
    for rec in analysis["recommendations"]:
        print(f"  * {rec}")

    print()


def main() -> int:
    """Main entry point for CLI.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        description="Analyze coverage of generated NeMo Data Designer scenarios",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze scenarios from default location
  uv run python tools/nemo_data_designer/analyze_coverage.py

  # Analyze from custom path with detailed output
  uv run python tools/nemo_data_designer/analyze_coverage.py \\
      --input custom_scenarios.parquet --detailed

  # Export analysis to JSON
  uv run python tools/nemo_data_designer/analyze_coverage.py \\
      --output coverage_analysis.json
        """,
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help=f"Input parquet file (default: {DEFAULT_INPUT_PATH})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON file for analysis results",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Include detailed analysis output",
    )

    args = parser.parse_args()

    try:
        # Load scenarios
        print(f"Loading scenarios from {args.input}...")
        df = load_scenarios(args.input)

        # Run analysis
        analysis = run_analysis(df, detailed=args.detailed)

        # Print results
        print_analysis(analysis, detailed=args.detailed)

        # Export if requested
        if args.output:
            # nosemgrep: path-traversal-open - args.output is CLI argument, validated by argparse as Path
            with open(args.output, "w") as f:
                json.dump(analysis, f, indent=2, default=str)
            print(f"Analysis exported to {args.output}")

        # Return non-zero if there are significant gaps
        if len(analysis["coverage_gaps"]) > 5:
            print("\nWarning: Multiple coverage gaps detected")
            return 1

        return 0

    except FileNotFoundError as e:
        print(f"\nError: {e}", file=sys.stderr)
        print("\nRun generate_scenarios.py first to create scenarios:")
        print(
            "  uv run python tools/nemo_data_designer/generate_scenarios.py --generate --rows 1500 --full-columns --dry-run"
        )
        return 1
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
