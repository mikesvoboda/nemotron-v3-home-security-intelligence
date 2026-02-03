#!/usr/bin/env python3
"""Kinetics-700 action recognition dataset converter.

Converts Kinetics action recognition annotations to expected_labels.json format.

Kinetics structure:
    kinetics700/
    ├── train.csv       # Training annotations
    ├── val.csv         # Validation annotations
    ├── test.csv        # Test annotations
    └── videos/         # Video files (if downloaded)
        ├── train/
        ├── val/
        └── test/

CSV format:
    label,youtube_id,time_start,time_end,split,is_cc

Usage:
    uv run scripts/dataset_converters/kinetics_converter.py \
        --input data/external/kinetics/raw \
        --output data/external/kinetics/converted \
        --security-only
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.dataset_converters import (
    ConvertedSample,
    DatasetConverter,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Security-relevant Kinetics action classes with risk mappings
SECURITY_ACTIONS: dict[str, tuple[str, int, int, str, list[str]]] = {
    # Format: action -> (category, min_score, max_score, level, factors)
    # Threatening actions
    "punching person (boxing)": (
        "threats",
        70,
        90,
        "high",
        ["violent_action", "physical_altercation"],
    ),
    "punching bag": ("normal", 0, 15, "low", ["exercise"]),
    "wrestling": ("threats", 60, 80, "high", ["violent_action", "physical_altercation"]),
    "slapping": ("threats", 65, 85, "high", ["violent_action"]),
    "kicking person": ("threats", 70, 90, "high", ["violent_action", "physical_altercation"]),
    "headbutting": ("threats", 75, 95, "critical", ["violent_action"]),
    "throwing axe": ("threats", 85, 100, "critical", ["weapon_use", "dangerous_object"]),
    "shooting gun": ("threats", 95, 100, "critical", ["weapon_use", "firearm"]),
    "sword fighting": ("threats", 80, 95, "critical", ["weapon_use"]),
    # Suspicious actions
    "climbing a rope": ("suspicious", 30, 50, "medium", ["unusual_movement", "climbing"]),
    "climbing ladder": ("suspicious", 25, 45, "medium", ["climbing"]),
    "climbing tree": ("suspicious", 20, 40, "low", ["climbing"]),
    "rock climbing": ("normal", 0, 15, "low", ["sport"]),
    "crawling baby": ("normal", 0, 10, "low", ["child"]),
    "army crawling": ("suspicious", 30, 50, "medium", ["unusual_movement", "prone"]),
    "opening door": ("normal", 0, 20, "low", ["entry"]),
    "picking lock": ("threats", 65, 85, "high", ["suspicious_behavior", "forced_entry"]),
    "breaking glass": ("threats", 70, 90, "high", ["property_damage", "forced_entry"]),
    "smashing": ("threats", 60, 80, "high", ["property_damage"]),
    "jumpstyle dancing": ("normal", 0, 15, "low", ["activity"]),
    "parkour": ("suspicious", 25, 45, "medium", ["unusual_movement"]),
    "vault": ("suspicious", 20, 40, "low", ["unusual_movement"]),
    "throwing ball": ("normal", 0, 15, "low", ["play"]),
    "throwing knife": ("threats", 80, 95, "critical", ["weapon_use"]),
    "juggling fire": ("suspicious", 35, 55, "medium", ["fire"]),
    # Normal activities
    "walking the dog": ("normal", 0, 15, "low", ["pedestrian", "pet"]),
    "walking through snow": ("normal", 0, 10, "low", ["pedestrian"]),
    "jogging": ("normal", 0, 15, "low", ["exercise"]),
    "running on treadmill": ("normal", 0, 10, "low", ["exercise"]),
    "riding a bike": ("normal", 0, 15, "low", ["cyclist"]),
    "riding scooter": ("normal", 0, 15, "low", ["transport"]),
    "skateboarding": ("normal", 0, 15, "low", ["activity"]),
    "getting out of car": ("normal", 0, 20, "low", ["vehicle_interaction"]),
    "parking car": ("normal", 0, 15, "low", ["vehicle_interaction"]),
    "driving car": ("normal", 0, 15, "low", ["vehicle"]),
    "delivering mail": ("normal", 0, 20, "low", ["delivery"]),
    "unboxing": ("normal", 0, 15, "low", ["delivery"]),
    "mowing lawn": ("normal", 0, 10, "low", ["yard_work"]),
    "gardening": ("normal", 0, 10, "low", ["yard_work"]),
    "watering plants": ("normal", 0, 10, "low", ["yard_work"]),
    "barbequing": ("normal", 0, 10, "low", ["cooking"]),
    "playing with pets": ("normal", 0, 10, "low", ["pet"]),
    "petting animal (not cat)": ("normal", 0, 10, "low", ["pet"]),
    "petting cat": ("normal", 0, 10, "low", ["pet"]),
    "feeding birds": ("normal", 0, 10, "low", ["wildlife"]),
    "waving hand": ("normal", 0, 15, "low", ["gesture"]),
    "shaking hands": ("normal", 0, 10, "low", ["greeting"]),
    "hugging (not baby)": ("normal", 0, 10, "low", ["greeting"]),
    "talking on phone": ("normal", 0, 10, "low", ["communication"]),
    "taking photo": ("normal", 5, 25, "low", ["photography"]),
    "looking at phone": ("normal", 0, 10, "low", ["device_use"]),
    # Running variations - context dependent
    "running": ("suspicious", 15, 35, "low", ["movement"]),
    "sprinting": ("suspicious", 20, 40, "low", ["rapid_movement"]),
    "chasing": ("suspicious", 40, 60, "medium", ["pursuit"]),
    "fleeing": ("threats", 50, 70, "high", ["escape"]),
}


def normalize_action(action: str) -> str:
    """Normalize action label for comparison."""
    return action.lower().strip()


class KineticsConverter(DatasetConverter):
    """Converter for Kinetics-700 action recognition dataset."""

    dataset_name = "kinetics"
    source_format = "csv_annotations"

    def __init__(self, security_only: bool = True, verbose: bool = False):
        """Initialize converter.

        Args:
            security_only: Only convert security-relevant actions
            verbose: Enable verbose logging
        """
        super().__init__(verbose)
        self.security_only = security_only

    def convert(
        self,
        source_path: Path,
        output_path: Path,
        limit: int | None = None,
    ) -> list[ConvertedSample]:
        """Convert Kinetics dataset to expected_labels.json format.

        Args:
            source_path: Path to Kinetics annotations directory
            output_path: Path to output converted samples
            limit: Maximum number of samples to convert

        Returns:
            List of converted samples
        """
        samples: list[ConvertedSample] = []

        # Find annotation files
        csv_files = list(source_path.glob("*.csv"))
        if not csv_files:
            # Try in subdirectory
            csv_files = list(source_path.glob("**/*.csv"))

        if not csv_files:
            logger.error("No CSV annotation files found in %s", source_path)
            return samples

        logger.info("Found %d CSV files", len(csv_files))

        for csv_file in csv_files:
            split = csv_file.stem  # train, val, test
            samples.extend(
                self._process_csv(
                    csv_file, split, output_path, limit - len(samples) if limit else None
                )
            )

            if limit and len(samples) >= limit:
                break

        # Print stats
        stats = self.get_conversion_stats(samples)
        logger.info("Conversion complete: %s", stats)

        return samples

    def _process_csv(
        self,
        csv_path: Path,
        split: str,
        output_path: Path,
        limit: int | None,
    ) -> list[ConvertedSample]:
        """Process a single CSV annotation file.

        Args:
            csv_path: Path to CSV file
            split: Dataset split (train/val/test)
            output_path: Output directory
            limit: Maximum samples from this file

        Returns:
            List of converted samples
        """
        samples: list[ConvertedSample] = []

        # csv_path comes from glob within source_path (user-provided but trusted)
        with open(csv_path, newline="", encoding="utf-8") as f:  # nosemgrep
            reader = csv.DictReader(f)

            for _i, row in enumerate(reader):
                if limit and len(samples) >= limit:
                    break

                # Get action label
                action = row.get("label", "")
                normalized = normalize_action(action)

                # Filter if security_only
                if self.security_only and normalized not in SECURITY_ACTIONS:
                    continue

                # Get video metadata
                youtube_id = row.get("youtube_id", "")
                time_start = row.get("time_start", "0")
                time_end = row.get("time_end", "10")

                try:
                    duration = float(time_end) - float(time_start)
                except ValueError:
                    duration = 10.0

                # Get risk mapping
                if normalized in SECURITY_ACTIONS:
                    category, risk_min, risk_max, risk_level, factors = SECURITY_ACTIONS[normalized]
                else:
                    # Default mapping for non-security actions
                    category = "normal"
                    risk_min = 0
                    risk_max = 20
                    risk_level = "low"
                    factors = [normalized.replace(" ", "_")]

                # Create action detection
                actions = [
                    {
                        "type": normalized.replace(" ", "_"),
                        "label": action,
                        "confidence_min": 0.5,
                        "confidence_max": 0.85,
                        "temporal": {
                            "start_sec": float(time_start),
                            "end_sec": float(time_end),
                        },
                        "source": "kinetics700",
                    }
                ]

                # Create expected labels
                expected_labels = self.to_expected_labels(
                    detections=[{"type": "person", "confidence_min": 0.7, "confidence_max": 0.95}],
                    risk_category=category,
                    risk_min=risk_min,
                    risk_max=risk_max,
                    risk_level=risk_level,
                    risk_factors=factors,
                    actions=actions,
                )

                # Create scenario spec
                scenario_id = f"kinetics_{split}_{youtube_id}_{int(float(time_start)):04d}"
                scenario_spec = self.to_scenario_spec(
                    scenario_id=scenario_id,
                    category=category,
                    name=action.title(),
                    description=f"Person performing action: {action}. "
                    f"Video clip from YouTube ({youtube_id}), seconds {time_start}-{time_end}.",
                    location="varies",
                    camera_type="varies",
                    time_of_day="varies",
                    weather="varies",
                    media_format="video",
                    duration_sec=duration,
                )

                # Note: Video path would be videos/{split}/{youtube_id}_{time_start}_{time_end}.mp4
                video_filename = f"{youtube_id}_{time_start:>06}_{time_end:>06}.mp4"
                video_path = csv_path.parent / "videos" / split / video_filename

                sample = ConvertedSample(
                    scenario_id=scenario_id,
                    category=category,
                    source_path=video_path,  # May not exist if videos not downloaded
                    expected_labels=expected_labels,
                    scenario_spec=scenario_spec,
                )
                samples.append(sample)

                # Write sample (without copying media if video doesn't exist)
                self.write_sample(sample, output_path, copy_media=video_path.exists())

        logger.info("Processed %s: %d samples", csv_path.name, len(samples))
        return samples


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Convert Kinetics-700 dataset to expected_labels.json format"
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to Kinetics annotations directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to output directory",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of samples to convert",
    )
    parser.add_argument(
        "--security-only",
        action="store_true",
        default=True,
        help="Only convert security-relevant actions (default: True)",
    )
    parser.add_argument(
        "--all-actions",
        action="store_true",
        help="Convert all actions, not just security-relevant",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if not args.input.exists():
        logger.error("Input directory not found: %s", args.input)
        return 1

    security_only = not args.all_actions
    converter = KineticsConverter(security_only=security_only, verbose=args.verbose)
    samples = converter.convert(args.input, args.output, args.limit)

    logger.info("Converted %d samples", len(samples))
    return 0


if __name__ == "__main__":
    sys.exit(main())
