#!/usr/bin/env python3
"""
AI Pipeline Validation: Compare YOLO26 detections against expected labels.

This script:
1. Queries detections from the database
2. Maps detections to their expected_labels.json files
3. Compares actual vs expected detections
4. Generates detailed gap analysis
5. Calculates precision, recall, and F1 scores
"""

import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

# Database connection info
DB_USER = "security"
DB_NAME = "security"
CONTAINER_NAME = "fine8_188fe20254c51e93_postgres_1"

# Paths
SYNTHETIC_DATA_DIR = Path(
    "/home/msvoboda/.claude-squad/worktrees/msvoboda/fine8_188fe20254c51e93/data/synthetic"
)


def query_detections() -> list[dict[str, Any]]:
    """Query all detections from database."""
    query = """
    SELECT
        d.id,
        d.camera_id,
        d.file_path,
        d.object_type,
        d.confidence,
        d.bbox_x,
        d.bbox_y,
        d.bbox_width,
        d.bbox_height,
        d.detected_at
    FROM detections d
    ORDER BY d.detected_at DESC;
    """

    cmd = [
        "podman",
        "exec",
        CONTAINER_NAME,
        "psql",
        "-U",
        DB_USER,
        "-d",
        DB_NAME,
        "-t",
        "-A",
        "-F",
        "|",
        "-c",
        query,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    detections = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|")
        if len(parts) >= 10:
            detections.append(
                {
                    "id": int(parts[0]),
                    "camera_id": parts[1],
                    "file_path": parts[2],
                    "object_type": parts[3],
                    "confidence": float(parts[4]),
                    "bbox_x": int(parts[5]) if parts[5] else None,
                    "bbox_y": int(parts[6]) if parts[6] else None,
                    "bbox_width": int(parts[7]) if parts[7] else None,
                    "bbox_height": int(parts[8]) if parts[8] else None,
                    "detected_at": parts[9],
                }
            )

    return detections


def extract_scenario_from_path(file_path: str) -> str | None:
    """Extract scenario name from file path.

    Example:
    /cameras/test_normal_delivery/2026/01/31/delivery_driver_20260125_180409_normal_frame02.jpg
    -> delivery_driver_20260125_180409
    """
    pattern = r"/([a-z_0-9]+)_(?:normal|suspicious|threats)_frame\d+\.jpg"
    match = re.search(pattern, file_path)
    if match:
        return match.group(1)
    return None


def find_expected_labels_file(scenario: str) -> Path | None:
    """Find expected_labels.json for a scenario."""
    for category in ["normal", "suspicious", "threats"]:
        # Try exact match
        scenario_dir = SYNTHETIC_DATA_DIR / category / scenario
        labels_file = scenario_dir / "expected_labels.json"
        if labels_file.exists():
            return labels_file

        # Try pattern match (for scenarios with timestamps)
        pattern = scenario.rsplit("_", 1)[0]  # Remove timestamp
        for item in (SYNTHETIC_DATA_DIR / category).iterdir():
            if item.is_dir() and item.name.startswith(pattern):
                labels_file = item / "expected_labels.json"
                if labels_file.exists():
                    return labels_file

    return None


def load_expected_labels(labels_file: Path) -> dict[str, Any]:
    """Load expected labels from JSON file."""
    # nosemgrep: path-traversal-open - labels_file is validated to be under SYNTHETIC_DATA_DIR
    with open(labels_file) as f:
        return json.load(f)


def group_detections_by_scenario(
    detections: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Group detections by scenario."""
    grouped = defaultdict(list)

    for detection in detections:
        scenario = extract_scenario_from_path(detection["file_path"])
        if scenario:
            grouped[scenario].append(detection)

    return dict(grouped)


def compare_detections(actual: list[dict[str, Any]], expected: dict[str, Any]) -> dict[str, Any]:
    """Compare actual detections vs expected labels."""
    results = {
        "expected": expected.get("detections", []),
        "actual_summary": {},
        "missing": [],
        "extra": [],
        "low_confidence": [],
        "matched": [],
    }

    # Count actual detections by class
    actual_counts = defaultdict(int)
    actual_by_class = defaultdict(list)
    for det in actual:
        obj_type = det["object_type"]
        actual_counts[obj_type] += 1
        actual_by_class[obj_type].append(det)

    results["actual_summary"] = dict(actual_counts)

    # Check each expected detection
    for exp in expected.get("detections", []):
        exp_class = exp["class"]
        exp_min_conf = exp.get("min_confidence", 0.7)
        exp_count = exp.get("count", 1)

        actual_dets = actual_by_class.get(exp_class, [])
        high_conf_dets = [d for d in actual_dets if d["confidence"] >= exp_min_conf]

        if len(high_conf_dets) < exp_count:
            results["missing"].append(
                {
                    "class": exp_class,
                    "expected_count": exp_count,
                    "actual_count": len(high_conf_dets),
                    "min_confidence": exp_min_conf,
                }
            )
        elif len(high_conf_dets) >= exp_count:
            results["matched"].append(
                {
                    "class": exp_class,
                    "expected_count": exp_count,
                    "actual_count": len(high_conf_dets),
                    "confidences": [d["confidence"] for d in high_conf_dets],
                }
            )

        # Check for low confidence detections
        low_conf_dets = [d for d in actual_dets if d["confidence"] < exp_min_conf]
        if low_conf_dets:
            results["low_confidence"].extend(
                [
                    {
                        "class": exp_class,
                        "confidence": d["confidence"],
                        "min_required": exp_min_conf,
                        "detection_id": d["id"],
                    }
                    for d in low_conf_dets
                ]
            )

    # Find extra/unexpected detections
    expected_classes = {exp["class"] for exp in expected.get("detections", [])}
    for obj_type, count in actual_counts.items():
        if obj_type not in expected_classes:
            results["extra"].append(
                {
                    "class": obj_type,
                    "count": count,
                    "detections": actual_by_class[obj_type],
                }
            )

    return results


def calculate_metrics(all_results: dict[str, dict[str, Any]]) -> dict[str, float]:
    """Calculate aggregate precision, recall, F1."""
    true_positives = 0
    false_positives = 0
    false_negatives = 0

    for _scenario, result in all_results.items():
        # True positives: matched detections
        for match in result["matched"]:
            true_positives += match["expected_count"]

        # False negatives: missing detections
        for miss in result["missing"]:
            false_negatives += miss["expected_count"] - miss["actual_count"]

        # False positives: extra detections
        for extra in result["extra"]:
            false_positives += extra["count"]

    precision = (
        true_positives / (true_positives + false_positives)
        if (true_positives + false_positives) > 0
        else 0.0
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if (true_positives + false_negatives) > 0
        else 0.0
    )
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
    }


def main():
    """Main validation logic."""
    print("=" * 80)
    print("AI Pipeline Validation: YOLO26 Detection Analysis")
    print("=" * 80)
    print()

    # Step 1: Query detections
    print("[1/5] Querying detections from database...")
    detections = query_detections()
    print(f"Found {len(detections)} detections")
    print()

    # Step 2: Group by scenario
    print("[2/5] Grouping detections by scenario...")
    grouped = group_detections_by_scenario(detections)
    print(f"Found {len(grouped)} scenarios")
    print()

    # Step 3: Compare against expected labels
    print("[3/5] Comparing against expected labels...")
    all_results = {}
    scenarios_without_labels = []

    for scenario, dets in grouped.items():
        labels_file = find_expected_labels_file(scenario)
        if not labels_file:
            scenarios_without_labels.append(scenario)
            continue

        expected = load_expected_labels(labels_file)
        result = compare_detections(dets, expected)
        all_results[scenario] = result

    print(f"Validated {len(all_results)} scenarios")
    if scenarios_without_labels:
        print(f"Warning: {len(scenarios_without_labels)} scenarios without expected labels")
    print()

    # Step 4: Calculate metrics
    print("[4/5] Calculating metrics...")
    metrics = calculate_metrics(all_results)
    print()

    # Step 5: Generate report
    print("[5/5] Generating report...")
    print()

    print("=" * 80)
    print("SUMMARY METRICS")
    print("=" * 80)
    print(f"Precision:        {metrics['precision']:.2%}")
    print(f"Recall:           {metrics['recall']:.2%}")
    print(f"F1 Score:         {metrics['f1_score']:.2%}")
    print(f"True Positives:   {metrics['true_positives']}")
    print(f"False Positives:  {metrics['false_positives']}")
    print(f"False Negatives:  {metrics['false_negatives']}")
    print()

    # Detailed gaps
    print("=" * 80)
    print("DETAILED GAP ANALYSIS")
    print("=" * 80)
    print()

    missing_by_class = defaultdict(list)
    extra_by_class = defaultdict(list)
    low_conf_by_class = defaultdict(list)

    for scenario, result in all_results.items():
        for miss in result["missing"]:
            missing_by_class[miss["class"]].append({"scenario": scenario, **miss})
        for extra in result["extra"]:
            extra_by_class[extra["class"]].append({"scenario": scenario, **extra})
        for low in result["low_confidence"]:
            low_conf_by_class[low["class"]].append({"scenario": scenario, **low})

    if missing_by_class:
        print("MISSING DETECTIONS (False Negatives):")
        print("-" * 80)
        for obj_class, instances in missing_by_class.items():
            print(f"\n{obj_class.upper()} ({len(instances)} scenarios affected):")
            for inst in instances[:5]:  # Show first 5
                print(
                    f"  - {inst['scenario']}: Expected {inst['expected_count']}, got {inst['actual_count']}"
                )
        print()

    if extra_by_class:
        print("EXTRA DETECTIONS (False Positives):")
        print("-" * 80)
        for obj_class, instances in extra_by_class.items():
            print(f"\n{obj_class.upper()} ({len(instances)} scenarios affected):")
            for inst in instances[:5]:
                print(f"  - {inst['scenario']}: {inst['count']} unexpected detections")
        print()

    if low_conf_by_class:
        print("LOW CONFIDENCE DETECTIONS:")
        print("-" * 80)
        for obj_class, instances in low_conf_by_class.items():
            print(f"\n{obj_class.upper()} ({len(instances)} detections):")
            for inst in instances[:5]:
                print(
                    f"  - {inst['scenario']}: {inst['confidence']:.3f} (min: {inst['min_required']:.3f})"
                )
        print()

    # Save full results to JSON
    output_file = Path("/tmp/detection_validation_results.json")  # noqa: S108
    # nosemgrep: path-traversal-open - output_file is a fixed local path
    with open(output_file, "w") as f:
        json.dump(
            {
                "metrics": metrics,
                "scenarios": all_results,
                "summary": {
                    "total_scenarios": len(all_results),
                    "missing_by_class": {k: len(v) for k, v in missing_by_class.items()},
                    "extra_by_class": {k: len(v) for k, v in extra_by_class.items()},
                    "low_conf_by_class": {k: len(v) for k, v in low_conf_by_class.items()},
                },
            },
            f,
            indent=2,
        )

    print(f"Full results saved to: {output_file}")
    print()

    return metrics, missing_by_class, extra_by_class, low_conf_by_class


if __name__ == "__main__":
    main()
