#!/usr/bin/env python3
"""Validate converted external datasets.

Verifies that all converted samples have valid expected_labels.json
and checks media file integrity.

Usage:
    uv run scripts/validate_external_datasets.py --all
    uv run scripts/validate_external_datasets.py --dataset ccpd
    uv run scripts/validate_external_datasets.py --coverage-report
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_EXTERNAL = PROJECT_ROOT / "data" / "external"
DATA_SYNTHETIC = PROJECT_ROOT / "data" / "synthetic"


@dataclass
class ValidationResult:
    """Result of validating a single sample."""

    sample_path: Path
    is_valid: bool
    has_expected_labels: bool
    has_scenario_spec: bool
    has_media: bool
    errors: list[str]


@dataclass
class DatasetStats:
    """Statistics for a validated dataset."""

    dataset_name: str
    total_samples: int
    valid_samples: int
    invalid_samples: int
    by_category: dict[str, int]
    by_risk_level: dict[str, int]
    missing_labels: int
    missing_spec: int
    missing_media: int
    errors: list[str]


def validate_expected_labels(labels_path: Path) -> tuple[bool, list[str]]:
    """Validate expected_labels.json structure.

    Args:
        labels_path: Path to expected_labels.json

    Returns:
        Tuple of (is_valid, list of errors)
    """
    errors: list[str] = []

    try:
        data = json.loads(labels_path.read_text())
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]

    # Required fields
    if "detections" not in data:
        errors.append("Missing 'detections' field")

    if "risk" not in data:
        errors.append("Missing 'risk' field")
    else:
        risk = data["risk"]
        if "min_score" not in risk:
            errors.append("Missing 'risk.min_score'")
        if "max_score" not in risk:
            errors.append("Missing 'risk.max_score'")
        if "level" not in risk:
            errors.append("Missing 'risk.level'")

        # Validate score ranges
        min_score = risk.get("min_score", 0)
        max_score = risk.get("max_score", 100)
        if not (0 <= min_score <= max_score <= 100):
            errors.append(f"Invalid score range: {min_score}-{max_score}")

        # Validate level
        valid_levels = {"low", "medium", "high", "critical"}
        level = risk.get("level", "")
        if level not in valid_levels:
            errors.append(f"Invalid risk level: {level}")

    # Validate detections
    detections = data.get("detections", [])
    for i, det in enumerate(detections):
        if "type" not in det:
            errors.append(f"Detection {i}: missing 'type'")

    return len(errors) == 0, errors


def validate_scenario_spec(spec_path: Path) -> tuple[bool, list[str]]:
    """Validate scenario_spec.json structure.

    Args:
        spec_path: Path to scenario_spec.json

    Returns:
        Tuple of (is_valid, list of errors)
    """
    errors: list[str] = []

    try:
        data = json.loads(spec_path.read_text())
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]

    # Required fields
    required = ["id", "category", "name", "description"]
    for field in required:
        if field not in data:
            errors.append(f"Missing '{field}' field")

    # Validate category
    valid_categories = {"normal", "suspicious", "threats"}
    category = data.get("category", "")
    if category and category not in valid_categories:
        errors.append(f"Invalid category: {category}")

    return len(errors) == 0, errors


def validate_sample(sample_dir: Path) -> ValidationResult:
    """Validate a single converted sample.

    Args:
        sample_dir: Path to sample directory

    Returns:
        ValidationResult
    """
    errors: list[str] = []

    # Check expected_labels.json
    labels_path = sample_dir / "expected_labels.json"
    has_labels = labels_path.exists()
    labels_valid = False
    if has_labels:
        labels_valid, label_errors = validate_expected_labels(labels_path)
        errors.extend(label_errors)

    # Check scenario_spec.json
    spec_path = sample_dir / "scenario_spec.json"
    has_spec = spec_path.exists()
    spec_valid = False
    if has_spec:
        spec_valid, spec_errors = validate_scenario_spec(spec_path)
        errors.extend(spec_errors)

    # Check media
    media_dir = sample_dir / "media"
    has_media = media_dir.exists() and any(media_dir.iterdir()) if media_dir.exists() else False

    # Overall validity
    is_valid = has_labels and labels_valid and has_spec and spec_valid

    return ValidationResult(
        sample_path=sample_dir,
        is_valid=is_valid,
        has_expected_labels=has_labels and labels_valid,
        has_scenario_spec=has_spec and spec_valid,
        has_media=has_media,
        errors=errors,
    )


def validate_dataset(dataset_path: Path) -> DatasetStats:
    """Validate all samples in a dataset.

    Args:
        dataset_path: Path to dataset directory (e.g., data/external/ccpd/converted)

    Returns:
        DatasetStats
    """
    dataset_name = dataset_path.parent.name
    logger.info("Validating dataset: %s", dataset_name)

    results: list[ValidationResult] = []
    by_category: dict[str, int] = defaultdict(int)
    by_risk_level: dict[str, int] = defaultdict(int)

    # Find all sample directories
    categories = ["normal", "suspicious", "threats"]
    for category in categories:
        category_dir = dataset_path / category
        if not category_dir.exists():
            continue

        for sample_dir in sorted(category_dir.iterdir()):
            if not sample_dir.is_dir():
                continue

            result = validate_sample(sample_dir)
            results.append(result)
            by_category[category] += 1

            # Get risk level
            labels_path = sample_dir / "expected_labels.json"
            if labels_path.exists():
                try:
                    data = json.loads(labels_path.read_text())
                    level = data.get("risk", {}).get("level", "unknown")
                    by_risk_level[level] += 1
                except json.JSONDecodeError:
                    by_risk_level["unknown"] += 1

    # Aggregate stats
    valid = [r for r in results if r.is_valid]
    invalid = [r for r in results if not r.is_valid]
    all_errors = [e for r in invalid for e in r.errors]

    return DatasetStats(
        dataset_name=dataset_name,
        total_samples=len(results),
        valid_samples=len(valid),
        invalid_samples=len(invalid),
        by_category=dict(by_category),
        by_risk_level=dict(by_risk_level),
        missing_labels=sum(1 for r in results if not r.has_expected_labels),
        missing_spec=sum(1 for r in results if not r.has_scenario_spec),
        missing_media=sum(1 for r in results if not r.has_media),
        errors=all_errors[:10],  # Limit errors shown
    )


def generate_coverage_report(
    external_stats: list[DatasetStats],
    synthetic_stats: DatasetStats | None = None,
) -> dict[str, Any]:
    """Generate combined coverage report.

    Args:
        external_stats: Stats from external datasets
        synthetic_stats: Stats from synthetic dataset

    Returns:
        Coverage report dictionary
    """
    report: dict[str, Any] = {
        "external_datasets": {},
        "combined_coverage": {
            "total_samples": 0,
            "by_category": defaultdict(int),
            "by_risk_level": defaultdict(int),
            "by_source": {},
        },
    }

    # Add external datasets
    for stats in external_stats:
        report["external_datasets"][stats.dataset_name] = {
            "total": stats.total_samples,
            "valid": stats.valid_samples,
            "by_category": stats.by_category,
            "by_risk_level": stats.by_risk_level,
        }
        report["combined_coverage"]["total_samples"] += stats.valid_samples
        report["combined_coverage"]["by_source"][stats.dataset_name] = stats.valid_samples
        for cat, count in stats.by_category.items():
            report["combined_coverage"]["by_category"][cat] += count
        for level, count in stats.by_risk_level.items():
            report["combined_coverage"]["by_risk_level"][level] += count

    # Add synthetic
    if synthetic_stats:
        report["synthetic_dataset"] = {
            "total": synthetic_stats.total_samples,
            "valid": synthetic_stats.valid_samples,
            "by_category": synthetic_stats.by_category,
            "by_risk_level": synthetic_stats.by_risk_level,
        }
        report["combined_coverage"]["total_samples"] += synthetic_stats.valid_samples
        report["combined_coverage"]["by_source"]["synthetic"] = synthetic_stats.valid_samples
        for cat, count in synthetic_stats.by_category.items():
            report["combined_coverage"]["by_category"][cat] += count
        for level, count in synthetic_stats.by_risk_level.items():
            report["combined_coverage"]["by_risk_level"][level] += count

    # Convert defaultdicts to regular dicts
    report["combined_coverage"]["by_category"] = dict(report["combined_coverage"]["by_category"])
    report["combined_coverage"]["by_risk_level"] = dict(
        report["combined_coverage"]["by_risk_level"]
    )

    return report


def print_stats(stats: DatasetStats) -> None:
    """Print dataset statistics."""
    print(f"\n{'=' * 60}")
    print(f"Dataset: {stats.dataset_name}")
    print(f"{'=' * 60}")
    print(f"Total samples: {stats.total_samples}")
    print(
        f"Valid samples: {stats.valid_samples} ({stats.valid_samples / max(stats.total_samples, 1) * 100:.1f}%)"
    )
    print(f"Invalid samples: {stats.invalid_samples}")
    print("\nBy category:")
    for cat, count in sorted(stats.by_category.items()):
        print(f"  {cat}: {count}")
    print("\nBy risk level:")
    for level, count in sorted(stats.by_risk_level.items()):
        print(f"  {level}: {count}")
    print("\nMissing files:")
    print(f"  expected_labels.json: {stats.missing_labels}")
    print(f"  scenario_spec.json: {stats.missing_spec}")
    print(f"  media: {stats.missing_media}")
    if stats.errors:
        print("\nSample errors (first 10):")
        for error in stats.errors:
            print(f"  - {error}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Validate converted external datasets")
    parser.add_argument(
        "--dataset",
        choices=["ccpd", "coco", "kinetics", "shanghaitech", "flir"],
        help="Specific dataset to validate",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all external datasets",
    )
    parser.add_argument(
        "--include-synthetic",
        action="store_true",
        help="Include synthetic dataset in validation",
    )
    parser.add_argument(
        "--coverage-report",
        action="store_true",
        help="Generate combined coverage report",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file for coverage report (JSON)",
    )

    args = parser.parse_args()

    if not args.dataset and not args.all and not args.coverage_report:
        parser.print_help()
        return 1

    external_stats: list[DatasetStats] = []

    # Validate specific dataset
    if args.dataset:
        converted_path = DATA_EXTERNAL / args.dataset / "converted"
        if not converted_path.exists():
            logger.error("Converted directory not found: %s", converted_path)
            return 1
        stats = validate_dataset(converted_path)
        external_stats.append(stats)
        print_stats(stats)

    # Validate all external datasets
    elif args.all or args.coverage_report:
        datasets = ["ccpd", "coco", "kinetics", "shanghaitech", "flir"]
        for dataset in datasets:
            converted_path = DATA_EXTERNAL / dataset / "converted"
            if converted_path.exists():
                stats = validate_dataset(converted_path)
                external_stats.append(stats)
                print_stats(stats)

    # Validate synthetic dataset
    synthetic_stats = None
    if args.include_synthetic or args.coverage_report:
        if DATA_SYNTHETIC.exists():
            # Create pseudo-converted path for synthetic
            synthetic_stats = validate_dataset(DATA_SYNTHETIC)
            print_stats(synthetic_stats)

    # Generate coverage report
    if args.coverage_report:
        report = generate_coverage_report(external_stats, synthetic_stats)

        print("\n" + "=" * 60)
        print("COMBINED COVERAGE REPORT")
        print("=" * 60)
        print(f"\nTotal samples: {report['combined_coverage']['total_samples']}")
        print("\nBy source:")
        for source, count in sorted(report["combined_coverage"]["by_source"].items()):
            print(f"  {source}: {count}")
        print("\nBy category:")
        for cat, count in sorted(report["combined_coverage"]["by_category"].items()):
            print(f"  {cat}: {count}")
        print("\nBy risk level:")
        for level, count in sorted(report["combined_coverage"]["by_risk_level"].items()):
            print(f"  {level}: {count}")

        if args.output:
            args.output.write_text(json.dumps(report, indent=2))
            logger.info("Coverage report written to: %s", args.output)

    # Check if any validation failed
    failed = any(s.invalid_samples > 0 for s in external_stats)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
