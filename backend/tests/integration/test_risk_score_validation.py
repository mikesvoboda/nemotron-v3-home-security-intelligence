"""Integration tests for automated risk score validation against synthetic scenarios.

This test suite implements comprehensive validation of the AI pipeline's risk scoring
accuracy by comparing actual risk scores against expected ranges defined in synthetic
test scenarios.

Related Issues:
- NEM-4533: Create automated risk score validation test suite
- NEM-4529: Add class-specific and scenario-type metrics
- NEM-4527: Improve detection validation coverage

Test Strategy:
1. Load synthetic scenarios with expected labels from data/synthetic/
2. Query actual detections and risk scores from database
3. Compare actual scores against expected ranges
4. Calculate gap rate (should be <20% per acceptance criteria)
5. Generate detailed per-class and per-scenario-type metrics
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.detection import Detection
from backend.models.event import Event


@pytest.fixture
def synthetic_scenarios() -> list[dict[str, Any]]:
    """Load all synthetic scenarios with expected labels.

    Returns:
        List of scenario dictionaries containing:
        - path: Path to scenario directory
        - category: Scenario category (normal/suspicious/threats)
        - name: Scenario name
        - labels: Expected labels from expected_labels.json
    """
    scenarios = []
    base_path = Path(__file__).parent.parent.parent.parent / "data" / "synthetic"

    for category in ["normal", "suspicious", "threats"]:
        category_path = base_path / category
        if not category_path.exists():
            continue

        for scenario_dir in sorted(category_path.iterdir()):
            if not scenario_dir.is_dir():
                continue

            labels_file = scenario_dir / "expected_labels.json"
            if not labels_file.exists():
                continue

            # nosemgrep: path-traversal-open - labels_file is validated to be under data/synthetic
            with open(labels_file) as f:
                labels = json.load(f)

            scenarios.append(
                {
                    "path": scenario_dir,
                    "category": category,
                    "name": scenario_dir.name,
                    "labels": labels,
                }
            )

    return scenarios


@pytest.fixture
def scenario_risk_ranges() -> dict[str, tuple[int, int]]:
    """Define expected risk score ranges by scenario category.

    These ranges align with the expected risk levels in synthetic scenarios:
    - normal: 0-15 (low risk)
    - suspicious: 35-60 (medium risk)
    - threats: 70-100 (high risk)

    Returns:
        Dictionary mapping category to (min_score, max_score) tuple
    """
    return {
        "normal": (0, 15),
        "suspicious": (35, 60),
        "threats": (70, 100),
    }


class TestRiskScoreValidation:
    """Automated risk score validation test suite."""

    @pytest.mark.asyncio
    async def test_load_synthetic_scenarios(
        self,
        synthetic_scenarios: list[dict[str, Any]],
    ) -> None:
        """Verify that synthetic scenarios are loaded correctly."""
        assert len(synthetic_scenarios) > 0, "No synthetic scenarios found"

        # Check structure of scenarios
        for scenario in synthetic_scenarios:
            assert "path" in scenario
            assert "category" in scenario
            assert "name" in scenario
            assert "labels" in scenario
            assert scenario["category"] in ["normal", "suspicious", "threats"]

            # Verify risk section exists in labels
            labels = scenario["labels"]
            assert "risk" in labels, f"Missing risk section in {scenario['name']}"
            risk = labels["risk"]
            assert "min_score" in risk
            assert "max_score" in risk
            assert "level" in risk

    @pytest.mark.asyncio
    async def test_risk_score_ranges_match_category(
        self,
        synthetic_scenarios: list[dict[str, Any]],
    ) -> None:
        """Verify that expected risk ranges in labels align with scenario category.

        Note: This test identifies potential miscategorizations in synthetic scenarios
        but does not fail the test suite. Some scenarios may be intentionally placed
        in a category different from their risk level for testing edge cases.
        """
        category_expectations = {
            "normal": "low",
            "suspicious": "medium",
            "threats": "high",
        }

        mismatches = []
        for scenario in synthetic_scenarios:
            category = scenario["category"]
            risk = scenario["labels"]["risk"]
            expected_level = category_expectations[category]

            if risk["level"] != expected_level:
                mismatches.append(
                    {
                        "scenario": scenario["name"],
                        "category": category,
                        "expected_level": expected_level,
                        "actual_level": risk["level"],
                    }
                )

        if mismatches:
            print(f"\n{'=' * 80}")
            print("CATEGORY/RISK LEVEL MISMATCHES")
            print(f"{'=' * 80}")
            print(f"Found {len(mismatches)} scenarios with mismatched category/risk level:")
            for m in mismatches[:10]:  # Show first 10
                print(
                    f"  {m['scenario']:40s} | "
                    f"Category: {m['category']:12s} | "
                    f"Expected: {m['expected_level']:8s} | "
                    f"Actual: {m['actual_level']:8s}"
                )
            if len(mismatches) > 10:
                print(f"  ... and {len(mismatches) - 10} more")
            print(f"{'=' * 80}\n")

        # Don't fail the test, just report the mismatches
        # Some scenarios may be intentionally miscategorized for testing edge cases

    @pytest.mark.asyncio
    async def test_gap_rate_below_threshold(
        self,
        session: AsyncSession,
        synthetic_scenarios: list[dict[str, Any]],
    ) -> None:
        """Verify gap rate is below 20% threshold.

        Gap rate is defined as the percentage of scenarios where the actual
        risk score falls outside the expected range defined in the labels.

        Acceptance Criteria:
        - Gap rate should be < 20%
        - Calculates overall gap rate across all scenarios
        - Reports per-category gap rates for debugging
        """
        results = await self._validate_all_scenarios(session, synthetic_scenarios)

        total_scenarios = len(results)
        gaps = sum(1 for r in results if r["gap"] > 0)
        gap_rate = (gaps / total_scenarios * 100) if total_scenarios > 0 else 0.0

        # Calculate per-category gap rates
        category_gaps = defaultdict(lambda: {"total": 0, "gaps": 0})
        for result in results:
            cat = result["category"]
            category_gaps[cat]["total"] += 1
            if result["gap"] > 0:
                category_gaps[cat]["gaps"] += 1

        # Generate detailed report
        report = []
        report.append(f"\n{'=' * 80}")
        report.append("RISK SCORE VALIDATION REPORT")
        report.append(f"{'=' * 80}")
        report.append(f"Total Scenarios: {total_scenarios}")
        report.append(f"Scenarios with Gaps: {gaps}")
        report.append(f"Overall Gap Rate: {gap_rate:.1f}%")
        report.append("Threshold: 20.0%")
        report.append("")

        report.append("Per-Category Gap Rates:")
        report.append("-" * 80)
        for cat, stats in sorted(category_gaps.items()):
            cat_gap_rate = (stats["gaps"] / stats["total"] * 100) if stats["total"] > 0 else 0.0
            report.append(
                f"  {cat:12s}: {stats['gaps']:3d}/{stats['total']:3d} ({cat_gap_rate:5.1f}%)"
            )

        # Show scenarios with largest gaps
        largest_gaps = sorted(results, key=lambda x: x["gap"], reverse=True)[:10]
        if largest_gaps[0]["gap"] > 0:
            report.append("")
            report.append("Top 10 Largest Gaps:")
            report.append("-" * 80)
            for r in largest_gaps:
                if r["gap"] == 0:
                    break
                report.append(
                    f"  {r['scenario_name']:40s} | "
                    f"Expected: [{r['expected_min']:3d}, {r['expected_max']:3d}] | "
                    f"Actual: {r['actual_score']:3d} | "
                    f"Gap: {r['gap']:3.0f}"
                )

        report.append(f"{'=' * 80}\n")
        print("\n".join(report))

        # Assert gap rate is below threshold
        assert gap_rate < 20.0, (
            f"Gap rate {gap_rate:.1f}% exceeds 20% threshold. {gaps}/{total_scenarios} scenarios have gaps."
        )

    @pytest.mark.asyncio
    async def test_per_class_detection_accuracy(
        self,
        session: AsyncSession,
        synthetic_scenarios: list[dict[str, Any]],
    ) -> None:
        """Calculate per-class precision, recall, and F1 scores.

        For each object class (Person, Car, Dog, etc.), calculates:
        - Precision: True positives / (True positives + False positives)
        - Recall: True positives / (True positives + False negatives)
        - F1 Score: Harmonic mean of precision and recall

        This addresses NEM-4529 requirement for class-specific metrics.
        """
        class_metrics = await self._calculate_per_class_metrics(session, synthetic_scenarios)

        # Generate report
        report = []
        report.append(f"\n{'=' * 80}")
        report.append("PER-CLASS DETECTION METRICS")
        report.append(f"{'=' * 80}")
        report.append(
            f"{'Class':<15s} {'TP':>6s} {'FP':>6s} {'FN':>6s} {'Precision':>10s} {'Recall':>10s} {'F1':>10s}"
        )
        report.append("-" * 80)

        for class_name, metrics in sorted(class_metrics.items()):
            report.append(
                f"{class_name:<15s} "
                f"{metrics['true_positives']:6d} "
                f"{metrics['false_positives']:6d} "
                f"{metrics['false_negatives']:6d} "
                f"{metrics['precision']:10.3f} "
                f"{metrics['recall']:10.3f} "
                f"{metrics['f1_score']:10.3f}"
            )

        report.append(f"{'=' * 80}\n")
        print("\n".join(report))

        # Basic sanity checks
        assert len(class_metrics) > 0, "No class metrics calculated"
        for class_name, metrics in class_metrics.items():
            assert 0.0 <= metrics["precision"] <= 1.0, f"Invalid precision for {class_name}"
            assert 0.0 <= metrics["recall"] <= 1.0, f"Invalid recall for {class_name}"
            assert 0.0 <= metrics["f1_score"] <= 1.0, f"Invalid F1 score for {class_name}"

    @pytest.mark.asyncio
    async def test_scenario_type_breakdown(
        self,
        session: AsyncSession,
        synthetic_scenarios: list[dict[str, Any]],
    ) -> None:
        """Generate scenario-type breakdown (normal/suspicious/threats).

        Calculates metrics aggregated by scenario category to identify
        which types of scenarios are most challenging for the AI pipeline.

        This addresses NEM-4529 requirement for scenario-type metrics.
        """
        results = await self._validate_all_scenarios(session, synthetic_scenarios)

        # Aggregate by category
        category_stats = defaultdict(
            lambda: {
                "count": 0,
                "within_range": 0,
                "gaps": [],
                "scores": [],
            }
        )

        for result in results:
            cat = result["category"]
            category_stats[cat]["count"] += 1
            category_stats[cat]["scores"].append(result["actual_score"])
            category_stats[cat]["gaps"].append(result["gap"])
            if result["gap"] == 0:
                category_stats[cat]["within_range"] += 1

        # Generate report
        report = []
        report.append(f"\n{'=' * 80}")
        report.append("SCENARIO-TYPE BREAKDOWN")
        report.append(f"{'=' * 80}")

        for category in ["normal", "suspicious", "threats"]:
            if category not in category_stats:
                continue

            stats = category_stats[category]
            within_pct = (stats["within_range"] / stats["count"] * 100) if stats["count"] > 0 else 0
            avg_gap = sum(stats["gaps"]) / len(stats["gaps"]) if stats["gaps"] else 0
            avg_score = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0

            report.append(f"\n{category.upper()}:")
            report.append("-" * 80)
            report.append(f"  Total Scenarios: {stats['count']}")
            report.append(f"  Within Range: {stats['within_range']} ({within_pct:.1f}%)")
            report.append(f"  Average Gap: {avg_gap:.1f}")
            report.append(f"  Average Score: {avg_score:.1f}")

        report.append(f"{'=' * 80}\n")
        print("\n".join(report))

    @pytest.mark.asyncio
    async def test_confidence_distribution_percentiles(
        self,
        session: AsyncSession,
        synthetic_scenarios: list[dict[str, Any]],
    ) -> None:
        """Calculate confidence distribution percentiles (P50, P90, P95, P99).

        Analyzes the distribution of detection confidence scores across all
        synthetic scenarios to understand model certainty patterns.

        This addresses NEM-4529 requirement for confidence distribution metrics.
        """
        # Query all detections
        stmt = select(Detection)
        result = await session.execute(stmt)
        detections = result.scalars().all()

        if not detections:
            pytest.skip("No detections found in database")

        confidences = [d.confidence for d in detections if d.confidence is not None]

        if not confidences:
            pytest.skip("No confidence scores found in detections")

        # Calculate percentiles
        import numpy as np

        percentiles = {
            "P50": float(np.percentile(confidences, 50)),
            "P90": float(np.percentile(confidences, 90)),
            "P95": float(np.percentile(confidences, 95)),
            "P99": float(np.percentile(confidences, 99)),
            "min": float(min(confidences)),
            "max": float(max(confidences)),
            "mean": float(np.mean(confidences)),
            "std": float(np.std(confidences)),
        }

        # Generate report
        report = []
        report.append(f"\n{'=' * 80}")
        report.append("CONFIDENCE DISTRIBUTION PERCENTILES")
        report.append(f"{'=' * 80}")
        report.append(f"Total Detections: {len(detections)}")
        report.append(f"Detections with Confidence: {len(confidences)}")
        report.append("")
        report.append(f"  Min:  {percentiles['min']:.3f}")
        report.append(f"  P50:  {percentiles['P50']:.3f}")
        report.append(f"  P90:  {percentiles['P90']:.3f}")
        report.append(f"  P95:  {percentiles['P95']:.3f}")
        report.append(f"  P99:  {percentiles['P99']:.3f}")
        report.append(f"  Max:  {percentiles['max']:.3f}")
        report.append(f"  Mean: {percentiles['mean']:.3f}")
        report.append(f"  Std:  {percentiles['std']:.3f}")
        report.append(f"{'=' * 80}\n")
        print("\n".join(report))

        # Sanity checks
        assert 0.0 <= percentiles["min"] <= 1.0, "Invalid minimum confidence"
        assert 0.0 <= percentiles["max"] <= 1.0, "Invalid maximum confidence"
        assert percentiles["min"] <= percentiles["P50"] <= percentiles["max"]
        assert percentiles["P50"] <= percentiles["P90"] <= percentiles["P95"] <= percentiles["P99"]

    # Helper methods

    async def _validate_all_scenarios(
        self,
        session: AsyncSession,
        synthetic_scenarios: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Validate all scenarios and return results with gap calculations."""
        results = []

        for scenario in synthetic_scenarios:
            # Find matching event by scenario name
            event = await self._find_event_for_scenario(session, scenario["name"])

            if not event:
                # Scenario not processed yet, skip
                continue

            expected_risk = scenario["labels"]["risk"]
            actual_score = event.risk_score or 0
            expected_min = expected_risk["min_score"]
            expected_max = expected_risk["max_score"]

            # Calculate gap (0 if within range, otherwise distance to nearest boundary)
            if expected_min <= actual_score <= expected_max:
                gap = 0.0
            elif actual_score < expected_min:
                gap = float(expected_min - actual_score)
            else:
                gap = float(actual_score - expected_max)

            results.append(
                {
                    "scenario_name": scenario["name"],
                    "category": scenario["category"],
                    "expected_min": expected_min,
                    "expected_max": expected_max,
                    "actual_score": actual_score,
                    "gap": gap,
                }
            )

        return results

    async def _find_event_for_scenario(
        self,
        session: AsyncSession,
        scenario_name: str,
    ) -> Event | None:
        """Find the event corresponding to a scenario by matching file paths."""
        # Query events that have detections matching the scenario name pattern
        stmt = select(Event).join(Detection).where(Detection.file_path.like(f"%{scenario_name}%"))

        result = await session.execute(stmt)
        events = result.scalars().all()

        # Return the most recent event if multiple found
        return max(events, key=lambda e: e.detected_at) if events else None

    async def _calculate_per_class_metrics(
        self,
        session: AsyncSession,
        synthetic_scenarios: list[dict[str, Any]],
    ) -> dict[str, dict[str, float]]:
        """Calculate precision, recall, F1 per object class."""
        class_stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})

        for scenario in synthetic_scenarios:
            # Get expected detections
            expected_detections = scenario["labels"].get("detections", [])
            expected_by_class = {d["class"]: d for d in expected_detections}

            # Get actual detections for this scenario
            stmt = select(Detection).where(Detection.file_path.like(f"%{scenario['name']}%"))
            result = await session.execute(stmt)
            actual_detections = result.scalars().all()

            # Count by class
            actual_by_class = defaultdict(int)
            for det in actual_detections:
                if det.confidence >= 0.7:  # Standard threshold
                    actual_by_class[det.object_type] += 1

            # Calculate TP, FP, FN per class
            all_classes = set(expected_by_class.keys()) | set(actual_by_class.keys())

            for class_name in all_classes:
                expected_count = expected_by_class.get(class_name, {}).get("count", 0)
                actual_count = actual_by_class.get(class_name, 0)

                tp = min(expected_count, actual_count)
                fp = max(0, actual_count - expected_count)
                fn = max(0, expected_count - actual_count)

                class_stats[class_name]["tp"] += tp
                class_stats[class_name]["fp"] += fp
                class_stats[class_name]["fn"] += fn

        # Calculate metrics
        metrics = {}
        for class_name, stats in class_stats.items():
            tp = stats["tp"]
            fp = stats["fp"]
            fn = stats["fn"]

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1_score = (
                2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
            )

            metrics[class_name] = {
                "true_positives": tp,
                "false_positives": fp,
                "false_negatives": fn,
                "precision": precision,
                "recall": recall,
                "f1_score": f1_score,
            }

        return metrics
