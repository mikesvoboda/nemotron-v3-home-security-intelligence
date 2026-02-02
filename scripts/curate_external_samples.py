#!/usr/bin/env python3
"""Curate external dataset samples for AI pipeline coverage testing.

Creates a small, diverse subset from external datasets that covers all
detection types, actions, and risk levels. Outputs in the exact format
used by data/synthetic/ for seamless integration with seed-events.py.

Usage:
    uv run python scripts/curate_external_samples.py --output data/synthetic/external
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
EXTERNAL_DIR = PROJECT_ROOT / "data" / "external"
SYNTHETIC_DIR = PROJECT_ROOT / "data" / "synthetic"

# Coverage requirements based on AI pipeline models
COVERAGE_REQUIREMENTS = {
    # Object detection classes (YOLO26)
    "object_classes": [
        "person",
        "car",
        "truck",
        "bus",
        "dog",
        "cat",
        "bird",
        "bicycle",
        "motorcycle",
    ],
    # Action recognition (X-CLIP) - security relevant
    "actions": {
        "normal": ["walking", "running", "delivering", "waving", "ringing doorbell"],
        "suspicious": ["fighting", "climbing", "hiding", "loitering", "looking around"],
        "threat": ["breaking window", "picking lock"],
    },
    # Risk levels
    "risk_levels": ["low", "medium", "high", "critical"],
    # Scene contexts
    "time_of_day": ["day", "night"],
    # Categories
    "categories": ["normal", "suspicious", "threats"],
}

# Mapping from our external format to synthetic format
# External uses "type", synthetic uses "class"
DETECTION_CLASS_MAP = {
    # COCO/external -> synthetic class names
    "person": "person",
    "pedestrian": "person",
    "car": "car",
    "vehicle": "car",
    "truck": "truck",
    "bus": "bus",
    "dog": "dog",
    "cat": "cat",
    "bird": "bird",
    "bicycle": "bicycle",
    "motorcycle": "motorcycle",
    "animal": "dog",  # Default to dog for generic animal
    "license_plate": None,  # Handled separately
}

# Action mapping from Kinetics to our action labels
KINETICS_ACTION_MAP = {
    # Normal actions
    "walking the dog": ("walking", "normal"),
    "walking through snow": ("walking", "normal"),
    "jogging": ("running", "normal"),
    "running on treadmill": ("running", "normal"),
    "delivering mail": ("delivering", "normal"),
    "unboxing": ("delivering", "normal"),
    "waving hand": ("waving", "normal"),
    "shaking hands": ("greeting", "normal"),
    "talking on phone": ("normal_activity", "normal"),
    "gardening": ("normal_activity", "normal"),
    "mowing lawn": ("normal_activity", "normal"),
    # Suspicious actions
    "climbing a rope": ("climbing", "suspicious"),
    "climbing ladder": ("climbing", "suspicious"),
    "climbing tree": ("climbing", "suspicious"),
    "parkour": ("climbing", "suspicious"),
    "army crawling": ("hiding", "suspicious"),
    "running": ("running_suspicious", "suspicious"),
    "sprinting": ("running_suspicious", "suspicious"),
    # Threat actions
    "punching person (boxing)": ("fighting", "threat"),
    "wrestling": ("fighting", "threat"),
    "slapping": ("fighting", "threat"),
    "kicking person": ("fighting", "threat"),
    "headbutting": ("fighting", "threat"),
    "breaking glass": ("breaking window", "threat"),
    "smashing": ("breaking window", "threat"),
    "throwing axe": ("weapon_use", "threat"),
    "shooting gun": ("weapon_use", "threat"),
    "sword fighting": ("weapon_use", "threat"),
}


def convert_to_synthetic_format(
    external_labels: dict[str, Any],
    external_spec: dict[str, Any],
    source_dataset: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Convert external expected_labels to synthetic format.

    Args:
        external_labels: External dataset expected_labels.json content
        external_spec: External dataset scenario_spec.json content
        source_dataset: Name of source dataset (coco, kinetics, etc.)

    Returns:
        Tuple of (converted_labels, converted_spec) in synthetic format
    """
    # Convert detections from "type" to "class" format
    converted_detections = []
    for det in external_labels.get("detections", []):
        det_type = det.get("type", det.get("detection_class", "unknown"))
        mapped_class = DETECTION_CLASS_MAP.get(det_type.lower(), det_type)

        if mapped_class is None:
            continue  # Skip unmapped types like license_plate

        converted_det = {
            "class": mapped_class,
            "min_confidence": det.get("confidence_min", 0.5),
            "count": 1,  # Default to 1, could aggregate
        }
        converted_detections.append(converted_det)

    # Aggregate duplicate classes
    class_counts: dict[str, dict[str, Any]] = {}
    for det in converted_detections:
        cls = det["class"]
        if cls in class_counts:
            class_counts[cls]["count"] += 1
            class_counts[cls]["min_confidence"] = min(
                class_counts[cls]["min_confidence"], det["min_confidence"]
            )
        else:
            class_counts[cls] = det.copy()

    final_detections = list(class_counts.values())

    # Get risk info
    risk = external_labels.get("risk", {})

    # Determine action from Kinetics data or infer from category
    action_info = {"action": "unknown", "is_suspicious": False}
    actions = external_labels.get("actions", [])
    if actions:
        action_label = actions[0].get("label", actions[0].get("type", "unknown"))
        mapped = KINETICS_ACTION_MAP.get(action_label.lower())
        if mapped:
            action_name, action_category = mapped
            action_info = {
                "action": action_name,
                "is_suspicious": action_category in ("suspicious", "threat"),
            }

    # Build converted labels in synthetic format
    converted_labels = {
        "source": source_dataset,
        "video_id": external_spec.get("id", "unknown"),
        "category": external_labels.get("category", external_spec.get("category", "normal")),
        "detections": final_detections,
        "face": {
            "detected": any(d["class"] == "person" for d in final_detections),
            "visible": True,
        },
        "pose": {
            "is_suspicious": risk.get("level") in ("high", "critical"),
        },
        "action": action_info,
        "scene": {
            "location": external_spec.get("scene", {}).get("location", "unknown"),
            "time_of_day": external_spec.get("environment", {}).get("time_of_day", "day"),
            "weather": external_spec.get("environment", {}).get("weather", "clear"),
        },
        "risk": {
            "min_score": risk.get("min_score", 0),
            "max_score": risk.get("max_score", 30),
            "level": risk.get("level", "low"),
        },
        "validation": {
            "prompt_excerpt": external_spec.get("description", "")[:200],
        },
    }

    # Build converted spec
    converted_spec = {
        "id": external_spec.get("id", "unknown"),
        "category": external_labels.get("category", external_spec.get("category", "normal")),
        "name": external_spec.get("name", "External Sample"),
        "description": external_spec.get("description", ""),
        "source": source_dataset,
        "scene": external_spec.get("scene", {}),
        "environment": external_spec.get("environment", {}),
        "generation": external_spec.get("generation", {"format": "image"}),
    }

    return converted_labels, converted_spec


def select_diverse_samples(
    samples: list[dict[str, Any]],
    max_per_category: int = 20,
) -> list[dict[str, Any]]:
    """Select diverse samples to maximize coverage.

    Args:
        samples: List of sample dicts with path, labels, spec
        max_per_category: Max samples per category

    Returns:
        Filtered list of diverse samples
    """
    selected: list[dict[str, Any]] = []
    coverage: dict[str, set[str]] = defaultdict(set)

    # Sort by coverage potential (prefer samples with rare classes)
    def coverage_score(sample: dict[str, Any]) -> int:
        labels = sample.get("labels", {})
        score = 0
        # Prefer samples with detections we haven't seen
        for det in labels.get("detections", []):
            cls = det.get("class", "")
            if cls not in coverage["classes"]:
                score += 10
        # Prefer higher risk samples (rarer)
        risk_level = labels.get("risk", {}).get("level", "low")
        if risk_level == "critical":
            score += 20
        elif risk_level == "high":
            score += 15
        elif risk_level == "medium":
            score += 10
        return score

    samples_sorted = sorted(samples, key=coverage_score, reverse=True)

    # Group by category
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples_sorted:
        cat = sample.get("labels", {}).get("category", "normal")
        by_category[cat].append(sample)

    # Select from each category
    for _category, cat_samples in by_category.items():
        for count, sample in enumerate(cat_samples):
            if count >= max_per_category:
                break

            # Track coverage
            labels = sample.get("labels", {})
            for det in labels.get("detections", []):
                coverage["classes"].add(det.get("class", ""))

            selected.append(sample)

    return selected


def load_external_samples(dataset_name: str) -> list[dict[str, Any]]:
    """Load converted samples from an external dataset.

    Args:
        dataset_name: Name of dataset (coco, kinetics, etc.)

    Returns:
        List of sample dicts
    """
    converted_dir = EXTERNAL_DIR / dataset_name / "converted"
    if not converted_dir.exists():
        logger.warning("No converted data for %s", dataset_name)
        return []

    samples = []
    for category in ["normal", "suspicious", "threats"]:
        category_dir = converted_dir / category
        if not category_dir.exists():
            continue

        for sample_dir in category_dir.iterdir():
            if not sample_dir.is_dir():
                continue

            labels_path = sample_dir / "expected_labels.json"
            spec_path = sample_dir / "scenario_spec.json"
            media_dir = sample_dir / "media"

            if not labels_path.exists():
                continue

            try:
                labels = json.loads(labels_path.read_text())
                spec = json.loads(spec_path.read_text()) if spec_path.exists() else {}

                # Find media file
                media_file = None
                if media_dir.exists():
                    media_files = list(media_dir.iterdir())
                    if media_files:
                        media_file = media_files[0]

                samples.append(
                    {
                        "dataset": dataset_name,
                        "path": sample_dir,
                        "labels": labels,
                        "spec": spec,
                        "media": media_file,
                    }
                )
            except json.JSONDecodeError:
                continue

    logger.info("Loaded %d samples from %s", len(samples), dataset_name)
    return samples


def curate_samples(
    output_dir: Path,
    max_samples: int = 100,
    copy_media: bool = True,
) -> dict[str, Any]:
    """Curate diverse samples from all external datasets.

    Args:
        output_dir: Output directory (e.g., data/synthetic/external)
        max_samples: Maximum total samples to curate
        copy_media: Whether to copy media files

    Returns:
        Curation statistics
    """
    all_samples: list[dict[str, Any]] = []

    # Load from all available external datasets
    for dataset in ["coco", "kinetics", "flir", "ccpd", "shanghaitech"]:
        samples = load_external_samples(dataset)
        all_samples.extend(samples)

    logger.info("Total samples available: %d", len(all_samples))

    if not all_samples:
        logger.error("No external samples found. Run converters first.")
        return {"error": "No samples found"}

    # Select diverse subset
    max_per_category = max_samples // 3  # Distribute across categories
    selected = select_diverse_samples(all_samples, max_per_category)
    logger.info("Selected %d diverse samples", len(selected))

    # Create output directories
    for category in ["normal", "suspicious", "threats"]:
        (output_dir / category).mkdir(parents=True, exist_ok=True)

    # Write curated samples in synthetic format
    stats: dict[str, Any] = {
        "total": 0,
        "by_category": defaultdict(int),
        "by_source": defaultdict(int),
        "by_class": defaultdict(int),
        "by_risk_level": defaultdict(int),
    }

    for sample in selected:
        # Convert to synthetic format
        converted_labels, converted_spec = convert_to_synthetic_format(
            sample["labels"],
            sample["spec"],
            sample["dataset"],
        )

        # Determine output category
        category = converted_labels.get("category", "normal")
        if category not in ["normal", "suspicious", "threats"]:
            category = "normal"

        # Create sample directory
        sample_id = f"{sample['dataset']}_{converted_spec['id']}"
        sample_dir = output_dir / category / sample_id
        sample_dir.mkdir(parents=True, exist_ok=True)

        # Write files
        (sample_dir / "expected_labels.json").write_text(json.dumps(converted_labels, indent=2))
        (sample_dir / "scenario_spec.json").write_text(json.dumps(converted_spec, indent=2))
        (sample_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "source_dataset": sample["dataset"],
                    "source_path": str(sample["path"]),
                    "curated": True,
                },
                indent=2,
            )
        )

        # Copy media if available
        if copy_media and sample.get("media") and sample["media"].exists():
            media_dir = sample_dir / "media"
            media_dir.mkdir(exist_ok=True)
            dest = media_dir / sample["media"].name
            shutil.copy2(sample["media"], dest)

        # Update stats
        stats["total"] += 1
        stats["by_category"][category] += 1
        stats["by_source"][sample["dataset"]] += 1
        stats["by_risk_level"][converted_labels["risk"]["level"]] += 1
        for det in converted_labels.get("detections", []):
            stats["by_class"][det["class"]] += 1

    # Convert defaultdicts to regular dicts for JSON
    stats["by_category"] = dict(stats["by_category"])
    stats["by_source"] = dict(stats["by_source"])
    stats["by_class"] = dict(stats["by_class"])
    stats["by_risk_level"] = dict(stats["by_risk_level"])

    # Write curation report
    report_path = output_dir / "curation_report.json"
    report_path.write_text(json.dumps(stats, indent=2))
    logger.info("Curation report: %s", report_path)

    return stats


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Curate external dataset samples for AI pipeline testing"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=SYNTHETIC_DIR / "external",
        help="Output directory (default: data/synthetic/external)",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=100,
        help="Maximum total samples to curate (default: 100)",
    )
    parser.add_argument(
        "--no-media",
        action="store_true",
        help="Don't copy media files (for testing)",
    )

    args = parser.parse_args()

    stats = curate_samples(
        output_dir=args.output,
        max_samples=args.max_samples,
        copy_media=not args.no_media,
    )

    if "error" in stats:
        return 1

    print("\nCuration Complete!")
    print(f"Total samples: {stats['total']}")
    print(f"\nBy category: {stats['by_category']}")
    print(f"By source: {stats['by_source']}")
    print(f"By risk level: {stats['by_risk_level']}")
    print(f"By detection class: {stats['by_class']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
