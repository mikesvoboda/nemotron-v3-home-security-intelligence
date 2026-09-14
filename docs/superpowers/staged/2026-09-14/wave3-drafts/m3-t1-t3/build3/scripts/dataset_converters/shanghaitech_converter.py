#!/usr/bin/env python3
"""ShanghaiTech Campus Anomaly Detection dataset converter.

Converts ShanghaiTech anomaly detection surveillance footage
to expected_labels.json format.

ShanghaiTech structure:
    ShanghaiTech/
    ├── training/
    │   └── videos/       # Normal videos only
    └── testing/
        ├── videos/       # Videos with anomalies
        └── ground_truth/ # Pixel-level masks + frame labels

Ground truth format:
    - {video_id}.mat: MATLAB file with 'gt' variable
    - gt is binary array: 0=normal, 1=anomaly for each frame

Usage:
    uv run scripts/dataset_converters/shanghaitech_converter.py \
        --input data/external/shanghaitech/raw/ShanghaiTech \
        --output data/external/shanghaitech/converted
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.dataset_converters import ConvertedSample, DatasetConverter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Anomaly type mappings based on ShanghaiTech documentation
# The dataset includes: biking, skateboarding, wrong direction, loitering, etc.
ANOMALY_DESCRIPTIONS = {
    "01": "Campus entrance area with pedestrian anomalies",
    "02": "Walkway with skateboarding and biking anomalies",
    "03": "Plaza area with loitering and running anomalies",
    "04": "Corridor with wrong-direction walking",
    "05": "Outdoor area with jumping and fighting anomalies",
    "06": "Indoor area with throwing objects",
    "07": "Stairway with unusual movements",
    "08": "Building entrance with suspicious activities",
    "09": "Parking area with vehicle anomalies",
    "10": "Pathway with chasing and fleeing",
    "11": "Garden area with vandalism",
    "12": "Gate area with unauthorized access attempts",
    "13": "Street view with traffic anomalies",
}


class ShanghaiTechConverter(DatasetConverter):
    """Converter for ShanghaiTech Campus Anomaly Detection dataset."""

    dataset_name = "shanghaitech"
    source_format = "avi_with_mat_gt"

    def convert(
        self,
        source_path: Path,
        output_path: Path,
        limit: int | None = None,
    ) -> list[ConvertedSample]:
        """Convert ShanghaiTech dataset to expected_labels.json format.

        Args:
            source_path: Path to ShanghaiTech directory
            output_path: Path to output converted samples
            limit: Maximum number of samples to convert

        Returns:
            List of converted samples
        """
        samples: list[ConvertedSample] = []

        # Process training videos (all normal)
        training_path = source_path / "training" / "videos"
        if training_path.exists():
            samples.extend(self._process_training(training_path, output_path, limit))

        # Process testing videos (with anomalies)
        testing_path = source_path / "testing"
        if testing_path.exists():
            remaining = (limit - len(samples)) if limit else None
            samples.extend(self._process_testing(testing_path, output_path, remaining))

        # Print stats
        stats = self.get_conversion_stats(samples)
        logger.info("Conversion complete: %s", stats)

        return samples

    def _process_training(
        self,
        videos_path: Path,
        output_path: Path,
        limit: int | None,
    ) -> list[ConvertedSample]:
        """Process training videos (all normal).

        Args:
            videos_path: Path to training videos
            output_path: Output directory
            limit: Maximum samples

        Returns:
            List of converted samples
        """
        samples: list[ConvertedSample] = []

        video_files = sorted(videos_path.glob("*.avi"))
        logger.info("Found %d training videos", len(video_files))

        for _i, video_path in enumerate(video_files):
            if limit and len(samples) >= limit:
                break

            video_id = video_path.stem

            # All training videos are normal
            expected_labels = self.to_expected_labels(
                detections=[{"type": "person", "confidence_min": 0.6, "confidence_max": 0.9}],
                risk_category="normal",
                risk_min=0,
                risk_max=20,
                risk_level="low",
                risk_factors=["normal_activity"],
            )

            scenario_id = f"shanghaitech_train_{video_id}"
            scenario_spec = self.to_scenario_spec(
                scenario_id=scenario_id,
                category="normal",
                name=f"Normal Campus Activity {video_id}",
                description="Normal pedestrian activity on university campus. "
                "Used as baseline for anomaly detection training.",
                location="campus",
                camera_type="surveillance_camera",
                time_of_day="day",
                weather="clear",
                media_format="video",
            )

            sample = ConvertedSample(
                scenario_id=scenario_id,
                category="normal",
                source_path=video_path,
                expected_labels=expected_labels,
                scenario_spec=scenario_spec,
            )
            samples.append(sample)
            self.write_sample(sample, output_path, copy_media=True)

        logger.info("Processed %d training videos", len(samples))
        return samples

    def _process_testing(
        self,
        testing_path: Path,
        output_path: Path,
        limit: int | None,
    ) -> list[ConvertedSample]:
        """Process testing videos with anomaly ground truth.

        Args:
            testing_path: Path to testing directory
            output_path: Output directory
            limit: Maximum samples

        Returns:
            List of converted samples
        """
        samples: list[ConvertedSample] = []

        videos_path = testing_path / "videos"
        gt_path = testing_path / "ground_truth"

        if not videos_path.exists():
            logger.warning("Testing videos not found: %s", videos_path)
            return samples

        video_files = sorted(videos_path.glob("*.avi"))
        logger.info("Found %d testing videos", len(video_files))

        for video_path in video_files:
            if limit and len(samples) >= limit:
                break

            video_id = video_path.stem

            # Try to load ground truth
            gt_file = gt_path / f"{video_id}.mat" if gt_path.exists() else None
            anomaly_info = (
                self._load_ground_truth(gt_file) if gt_file and gt_file.exists() else None
            )

            # Determine category and risk based on ground truth
            if anomaly_info and anomaly_info["has_anomaly"]:
                # Video contains anomalies
                anomaly_ratio = anomaly_info["anomaly_frames"] / max(
                    anomaly_info["total_frames"], 1
                )

                if anomaly_ratio > 0.3:
                    category = "threats"
                    risk_min = 60
                    risk_max = 85
                    risk_level = "high"
                    risk_factors = ["anomaly_detected", "extended_anomaly"]
                else:
                    category = "suspicious"
                    risk_min = 35
                    risk_max = 60
                    risk_level = "medium"
                    risk_factors = ["anomaly_detected"]

                # Add temporal info
                temporal_info = {
                    "anomaly_start_frame": anomaly_info.get("first_anomaly_frame", 0),
                    "anomaly_end_frame": anomaly_info.get("last_anomaly_frame", 0),
                    "anomaly_ratio": round(anomaly_ratio, 3),
                }
            else:
                # No ground truth or no anomaly
                category = "suspicious"  # Testing set, assume some risk
                risk_min = 20
                risk_max = 40
                risk_level = "low"
                risk_factors = ["unverified_activity"]
                temporal_info = None

            # Create detections
            detections = [{"type": "person", "confidence_min": 0.6, "confidence_max": 0.9}]

            # Add anomaly action if detected
            actions = None
            if anomaly_info and anomaly_info["has_anomaly"]:
                actions = [
                    {
                        "type": "anomaly",
                        "label": "Anomalous Activity",
                        "confidence_min": 0.5,
                        "confidence_max": 0.8,
                        "temporal": temporal_info,
                    }
                ]

            expected_labels = self.to_expected_labels(
                detections=detections,
                risk_category=category,
                risk_min=risk_min,
                risk_max=risk_max,
                risk_level=risk_level,
                risk_factors=risk_factors,
                actions=actions,
            )

            # Get description based on scene number
            scene_num = video_id.split("_")[0] if "_" in video_id else video_id[:2]
            scene_desc = ANOMALY_DESCRIPTIONS.get(
                scene_num, "Campus surveillance footage with potential anomalies"
            )

            scenario_id = f"shanghaitech_test_{video_id}"
            scenario_spec = self.to_scenario_spec(
                scenario_id=scenario_id,
                category=category,
                name=f"Campus Anomaly Test {video_id}",
                description=f"{scene_desc}. Testing video for anomaly detection evaluation.",
                location="campus",
                camera_type="surveillance_camera",
                time_of_day="day",
                weather="clear",
                media_format="video",
            )

            sample = ConvertedSample(
                scenario_id=scenario_id,
                category=category,
                source_path=video_path,
                expected_labels=expected_labels,
                scenario_spec=scenario_spec,
            )
            samples.append(sample)
            self.write_sample(sample, output_path, copy_media=True)

        logger.info("Processed %d testing videos", len(samples))
        return samples

    def _load_ground_truth(self, gt_file: Path) -> dict[str, Any] | None:
        """Load ground truth from MATLAB file.

        Args:
            gt_file: Path to .mat file

        Returns:
            Ground truth info dict or None
        """
        try:
            from scipy.io import loadmat

            mat_data = loadmat(str(gt_file))
            gt = mat_data.get("gt", np.array([]))

            if gt.size == 0:
                return None

            gt_flat = gt.flatten()
            total_frames = len(gt_flat)
            anomaly_frames = int(np.sum(gt_flat))
            has_anomaly = anomaly_frames > 0

            # Find first and last anomaly frame
            anomaly_indices = np.where(gt_flat == 1)[0]
            first_anomaly = int(anomaly_indices[0]) if len(anomaly_indices) > 0 else 0
            last_anomaly = int(anomaly_indices[-1]) if len(anomaly_indices) > 0 else 0

            return {
                "has_anomaly": has_anomaly,
                "total_frames": total_frames,
                "anomaly_frames": anomaly_frames,
                "first_anomaly_frame": first_anomaly,
                "last_anomaly_frame": last_anomaly,
            }

        except Exception as e:
            logger.warning("Failed to load ground truth %s: %s", gt_file, e)
            return None


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Convert ShanghaiTech dataset to expected_labels.json format"
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to ShanghaiTech directory",
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
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if not args.input.exists():
        logger.error("Input directory not found: %s", args.input)
        return 1

    converter = ShanghaiTechConverter(verbose=args.verbose)
    samples = converter.convert(args.input, args.output, args.limit)

    logger.info("Converted %d samples", len(samples))
    return 0


if __name__ == "__main__":
    sys.exit(main())
