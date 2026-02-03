#!/usr/bin/env python3
"""CCPD (Chinese City Parking Dataset) converter.

Converts CCPD license plate dataset to expected_labels.json format.

CCPD filename format:
    025-95_113-154&383_386&473-386&473_177&454_154&383_363&402-0_0_22_27_27_33_16-37-15.jpg

Fields (separated by -):
1. Area ratio of license plate
2. Tilt degrees (horizontal, vertical)
3. Bounding box coordinates (x1&y1_x2&y2)
4. Four corner vertices
5. License plate characters (7 indices)
6. Brightness
7. Blurriness

Usage:
    uv run scripts/dataset_converters/ccpd_converter.py \
        --input data/external/ccpd/raw \
        --output data/external/ccpd/converted
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

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

# Chinese province abbreviations
PROVINCES = [
    "皖",
    "沪",
    "津",
    "渝",
    "冀",
    "晋",
    "蒙",
    "辽",
    "吉",
    "黑",
    "苏",
    "浙",
    "京",
    "闽",
    "赣",
    "鲁",
    "豫",
    "鄂",
    "湘",
    "粤",
    "桂",
    "琼",
    "川",
    "贵",
    "云",
    "藏",
    "陕",
    "甘",
    "青",
    "宁",
    "新",
    "警",
    "学",
    "O",
]

# Alphanumeric characters (excluding I and O)
ALPHANUMERIC = [
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    "J",
    "K",
    "L",
    "M",
    "N",
    "P",
    "Q",
    "R",
    "S",
    "T",
    "U",
    "V",
    "W",
    "X",
    "Y",
    "Z",
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "O",
]


def parse_ccpd_filename(filename: str) -> dict[str, Any] | None:
    """Parse CCPD filename to extract annotations.

    Args:
        filename: CCPD filename without extension

    Returns:
        Parsed annotation dictionary or None if parsing fails
    """
    try:
        parts = filename.split("-")
        if len(parts) < 7:
            return None

        # Parse bounding box (field 3)
        bbox_str = parts[2]
        bbox_parts = bbox_str.split("_")
        if len(bbox_parts) != 2:
            return None

        tl = bbox_parts[0].split("&")
        br = bbox_parts[1].split("&")

        x1, y1 = int(tl[0]), int(tl[1])
        x2, y2 = int(br[0]), int(br[1])

        # Parse license plate characters (field 5)
        plate_indices = parts[4].split("_")
        if len(plate_indices) != 7:
            return None

        # Convert indices to characters
        plate_chars = []
        for i, idx_str in enumerate(plate_indices):
            idx = int(idx_str)
            if i == 0:  # Province
                plate_chars.append(PROVINCES[idx] if idx < len(PROVINCES) else "?")
            else:  # Alphanumeric
                plate_chars.append(ALPHANUMERIC[idx] if idx < len(ALPHANUMERIC) else "?")

        plate_text = "".join(plate_chars)

        # Parse quality metrics
        brightness = int(parts[5]) if len(parts) > 5 else 50
        blurriness = int(parts[6]) if len(parts) > 6 else 50

        return {
            "bbox": [x1, y1, x2, y2],
            "plate_text": plate_text,
            "brightness": brightness,
            "blurriness": blurriness,
        }

    except (ValueError, IndexError) as e:
        logger.debug("Failed to parse %s: %s", filename, e)
        return None


class CCPDConverter(DatasetConverter):
    """Converter for CCPD license plate dataset."""

    dataset_name = "ccpd"
    source_format = "ccpd_filename"

    def convert(
        self,
        source_path: Path,
        output_path: Path,
        limit: int | None = None,
    ) -> list[ConvertedSample]:
        """Convert CCPD dataset to expected_labels.json format.

        Args:
            source_path: Path to CCPD raw directory
            output_path: Path to output converted samples
            limit: Maximum number of samples to convert

        Returns:
            List of converted samples
        """
        samples: list[ConvertedSample] = []

        # Find all CCPD subdirectories
        ccpd_dirs = [
            "ccpd_base",
            "ccpd_blur",
            "ccpd_challenge",
            "ccpd_db",
            "ccpd_fn",
            "ccpd_rotate",
            "ccpd_tilt",
            "ccpd_weather",
        ]

        image_paths: list[Path] = []
        for ccpd_dir in ccpd_dirs:
            dir_path = source_path / ccpd_dir
            if dir_path.exists():
                image_paths.extend(dir_path.glob("*.jpg"))

        # Also check root for images
        image_paths.extend(source_path.glob("*.jpg"))

        logger.info("Found %d images in CCPD dataset", len(image_paths))

        # Apply limit
        if limit:
            image_paths = image_paths[:limit]

        for i, img_path in enumerate(image_paths):
            if i % 1000 == 0:
                logger.info("Processing %d/%d", i, len(image_paths))

            # Parse filename
            annotation = parse_ccpd_filename(img_path.stem)
            if not annotation:
                continue

            # Determine scenario category based on context
            # Most CCPD images are normal parking scenarios
            category = "normal"
            risk_min = 0
            risk_max = 25
            risk_level = "low"
            risk_factors = ["vehicle_with_plate"]

            # Adjust for quality issues that might affect detection
            if annotation["brightness"] < 20:
                category = "suspicious"
                risk_min = 15
                risk_max = 35
                risk_level = "low"
                risk_factors.append("low_visibility")
            elif annotation["blurriness"] > 80:
                risk_factors.append("motion_blur")

            # Create detection entry
            x1, y1, x2, y2 = annotation["bbox"]
            detections = [
                {
                    "type": "vehicle",
                    "confidence_min": 0.7,
                    "confidence_max": 0.95,
                    "attributes": {
                        "has_plate": True,
                        "plate_text": annotation["plate_text"],
                        "plate_region": "CN",
                    },
                },
                {
                    "type": "license_plate",
                    "confidence_min": 0.6,
                    "confidence_max": 0.9,
                    "bounding_box": {
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2,
                    },
                    "attributes": {
                        "text": annotation["plate_text"],
                        "region": "CN",
                    },
                },
            ]

            # Create expected labels
            expected_labels = self.to_expected_labels(
                detections=detections,
                risk_category=category,
                risk_min=risk_min,
                risk_max=risk_max,
                risk_level=risk_level,
                risk_factors=risk_factors,
            )

            # Determine time of day based on brightness
            time_of_day = "day" if annotation["brightness"] > 30 else "night"

            # Create scenario spec
            scenario_id = f"ccpd_{img_path.stem[:20]}_{i:05d}"
            scenario_spec = self.to_scenario_spec(
                scenario_id=scenario_id,
                category=category,
                name=f"Vehicle with Plate {annotation['plate_text']}",
                description=f"Parked vehicle with visible license plate {annotation['plate_text']}. "
                f"Brightness: {annotation['brightness']}, Blur: {annotation['blurriness']}.",
                location="parking_lot",
                camera_type="parking_camera",
                time_of_day=time_of_day,
                weather="varies",
                media_format="image",
            )

            sample = ConvertedSample(
                scenario_id=scenario_id,
                category=category,
                source_path=img_path,
                expected_labels=expected_labels,
                scenario_spec=scenario_spec,
            )
            samples.append(sample)

        # Write samples
        logger.info("Writing %d converted samples", len(samples))
        for sample in samples:
            self.write_sample(sample, output_path, copy_media=True)

        # Print stats
        stats = self.get_conversion_stats(samples)
        logger.info("Conversion complete: %s", stats)

        return samples


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Convert CCPD dataset to expected_labels.json format"
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to CCPD raw directory",
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

    converter = CCPDConverter(verbose=args.verbose)
    samples = converter.convert(args.input, args.output, args.limit)

    logger.info("Converted %d samples", len(samples))
    return 0


if __name__ == "__main__":
    sys.exit(main())
