#!/usr/bin/env python3
"""COCO (Common Objects in Context) dataset converter.

Converts COCO object detection annotations to expected_labels.json format.

COCO structure:
    coco/
    ├── val2017/              # Validation images
    ├── train2017/            # Training images (large)
    └── annotations/
        ├── instances_val2017.json
        └── instances_train2017.json

COCO annotation format:
{
    "images": [{"id": int, "file_name": str, "width": int, "height": int}],
    "annotations": [{"id": int, "image_id": int, "category_id": int, "bbox": [x,y,w,h]}],
    "categories": [{"id": int, "name": str, "supercategory": str}]
}

Usage:
    uv run scripts/dataset_converters/coco_converter.py \
        --input data/external/coco/raw \
        --output data/external/coco/converted \
        --split val2017
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.dataset_converters import ConvertedSample, DatasetConverter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# COCO categories relevant for security
SECURITY_CATEGORIES = {
    # People
    1: ("person", "pedestrian", "normal", 0, 30),
    # Vehicles
    2: ("bicycle", "vehicle", "normal", 0, 20),
    3: ("car", "vehicle", "normal", 0, 25),
    4: ("motorcycle", "vehicle", "normal", 0, 25),
    6: ("bus", "vehicle", "normal", 0, 20),
    7: ("train", "vehicle", "normal", 0, 15),
    8: ("truck", "vehicle", "normal", 0, 25),
    # Animals
    16: ("bird", "animal", "normal", 0, 15),
    17: ("cat", "animal", "normal", 0, 15),
    18: ("dog", "animal", "normal", 0, 20),
    19: ("horse", "animal", "normal", 0, 20),
    20: ("sheep", "animal", "normal", 0, 15),
    21: ("cow", "animal", "normal", 0, 15),
    22: ("elephant", "animal", "normal", 0, 20),
    23: ("bear", "animal", "suspicious", 30, 50),  # Bears near homes = suspicious
    24: ("zebra", "animal", "normal", 0, 15),
    25: ("giraffe", "animal", "normal", 0, 15),
    # Objects of interest
    27: ("backpack", "object", "normal", 0, 25),
    28: ("umbrella", "object", "normal", 0, 10),
    31: ("handbag", "object", "normal", 0, 20),
    32: ("tie", "object", "normal", 0, 10),
    33: ("suitcase", "object", "normal", 0, 25),
    # Sports equipment (context matters)
    34: ("frisbee", "object", "normal", 0, 10),
    35: ("skis", "object", "normal", 0, 15),
    36: ("snowboard", "object", "normal", 0, 15),
    37: ("sports ball", "object", "normal", 0, 10),
    38: ("kite", "object", "normal", 0, 10),
    39: ("baseball bat", "object", "suspicious", 20, 40),  # Potential weapon
    40: ("baseball glove", "object", "normal", 0, 10),
    41: ("skateboard", "object", "normal", 0, 15),
    42: ("surfboard", "object", "normal", 0, 15),
    43: ("tennis racket", "object", "normal", 0, 15),
    # Items that could indicate package/delivery
    73: ("laptop", "object", "normal", 10, 30),
    74: ("mouse", "object", "normal", 0, 10),
    75: ("remote", "object", "normal", 0, 10),
    76: ("keyboard", "object", "normal", 0, 15),
    77: ("cell phone", "object", "normal", 0, 15),
    # Potential tools (scissors is COCO category 87)
    87: ("scissors", "object", "suspicious", 15, 35),
    # Knife is COCO category 49
    49: ("knife", "object", "suspicious", 25, 45),
}

# Categories to skip entirely
SKIP_CATEGORIES = {
    # Indoor items not relevant for outdoor security
    # Note: 49 (knife) and 87 (scissors) are NOT skipped - they're security-relevant
    44,
    45,
    46,
    47,
    48,
    50,
    51,
    52,
    53,
    54,
    55,
    56,
    57,
    58,
    59,
    60,
    61,
    62,
    63,
    64,
    65,
    66,
    67,
    68,
    69,
    70,
    71,
    72,
    78,
    79,
    80,
    81,
    82,
    83,
    84,
    85,
    86,
    87,
    88,
    89,
    90,
}


class COCOConverter(DatasetConverter):
    """Converter for COCO object detection dataset."""

    dataset_name = "coco"
    source_format = "coco_json"

    def __init__(
        self,
        security_only: bool = True,
        min_detections: int = 1,
        verbose: bool = False,
    ):
        """Initialize converter.

        Args:
            security_only: Only include security-relevant categories
            min_detections: Minimum detections per image to include
            verbose: Enable verbose logging
        """
        super().__init__(verbose)
        self.security_only = security_only
        self.min_detections = min_detections

    def convert(
        self,
        source_path: Path,
        output_path: Path,
        limit: int | None = None,
        split: str = "val2017",
    ) -> list[ConvertedSample]:
        """Convert COCO dataset to expected_labels.json format.

        Args:
            source_path: Path to COCO raw directory
            output_path: Path to output converted samples
            limit: Maximum number of samples to convert
            split: Dataset split (val2017 or train2017)

        Returns:
            List of converted samples
        """
        samples: list[ConvertedSample] = []

        # Find annotation file
        ann_file = source_path / "annotations" / f"instances_{split}.json"
        if not ann_file.exists():
            logger.error("Annotation file not found: %s", ann_file)
            return samples

        # Find images directory
        images_dir = source_path / split
        if not images_dir.exists():
            images_dir = source_path / "images" / split
            if not images_dir.exists():
                logger.error("Images directory not found for split: %s", split)
                return samples

        # Load annotations - ann_file is constructed from source_path (trusted)
        logger.info("Loading COCO annotations from %s", ann_file)
        with open(ann_file, encoding="utf-8") as f:  # nosemgrep
            coco_data = json.load(f)

        images = {img["id"]: img for img in coco_data.get("images", [])}
        categories = {cat["id"]: cat for cat in coco_data.get("categories", [])}

        # Group annotations by image
        ann_by_image: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for ann in coco_data.get("annotations", []):
            cat_id = ann.get("category_id")
            if self.security_only and cat_id not in SECURITY_CATEGORIES:
                continue
            if cat_id in SKIP_CATEGORIES:
                continue
            ann_by_image[ann["image_id"]].append(ann)

        logger.info(
            "Processing %d images with %d relevant annotations",
            len(ann_by_image),
            sum(len(anns) for anns in ann_by_image.values()),
        )

        # Process each image
        for img_id, img_annotations in ann_by_image.items():
            if limit and len(samples) >= limit:
                break

            if len(img_annotations) < self.min_detections:
                continue

            img_info = images.get(img_id)
            if not img_info:
                continue

            # Find image file
            img_filename = img_info.get("file_name", "")
            img_path = images_dir / img_filename
            if not img_path.exists():
                continue

            sample = self._convert_image(
                img_id=img_id,
                _img_info=img_info,
                img_path=img_path,
                annotations=img_annotations,
                categories=categories,
                split=split,
            )

            if sample:
                samples.append(sample)
                self.write_sample(sample, output_path, copy_media=True)

        # Print stats
        stats = self.get_conversion_stats(samples)
        logger.info("Conversion complete: %s", stats)

        return samples

    def _convert_image(
        self,
        img_id: int,
        _img_info: dict[str, Any],
        img_path: Path,
        annotations: list[dict[str, Any]],
        categories: dict[int, dict[str, Any]],
        split: str,
    ) -> ConvertedSample | None:
        """Convert a single image with its annotations.

        Args:
            img_id: Image ID
            img_info: Image metadata
            img_path: Path to image file
            annotations: List of annotations for this image
            categories: Category ID to info mapping
            split: Dataset split

        Returns:
            Converted sample or None
        """
        detections: list[dict[str, Any]] = []
        max_risk = 0
        risk_factors: list[str] = []

        for ann in annotations:
            cat_id = ann.get("category_id")
            bbox = ann.get("bbox", [])  # [x, y, width, height]

            if len(bbox) != 4:
                continue

            # Get category info
            cat_info = categories.get(cat_id, {})
            cat_name = cat_info.get("name", "unknown")

            # Get security mapping
            if cat_id in SECURITY_CATEGORIES:
                obj_type, det_class, _, risk_min, risk_max = SECURITY_CATEGORIES[cat_id]
                max_risk = max(max_risk, risk_max)
            else:
                obj_type = cat_name
                det_class = "object"
                risk_min = 0
                risk_max = 20

            # Convert bbox
            x, y, w, h = bbox
            detection = {
                "type": obj_type,
                "detection_class": det_class,
                "confidence_min": 0.5,
                "confidence_max": 0.9,
                "bounding_box": {
                    "x1": int(x),
                    "y1": int(y),
                    "x2": int(x + w),
                    "y2": int(y + h),
                },
                "coco_category_id": cat_id,
            }
            detections.append(detection)

            # Track risk factors
            if det_class not in risk_factors:
                risk_factors.append(det_class)

        # Determine category based on max risk
        if max_risk >= 40:
            category = "suspicious"
            risk_level = "medium"
            risk_min_final = 25
            risk_max_final = max_risk
        elif max_risk >= 25:
            category = "normal"
            risk_level = "low"
            risk_min_final = 10
            risk_max_final = max_risk
        else:
            category = "normal"
            risk_level = "low"
            risk_min_final = 0
            risk_max_final = max(20, max_risk)

        # Create expected labels
        expected_labels = self.to_expected_labels(
            detections=detections,
            risk_category=category,
            risk_min=risk_min_final,
            risk_max=risk_max_final,
            risk_level=risk_level,
            risk_factors=risk_factors,
        )

        # Create description
        det_types = [d["type"] for d in detections]
        det_counts = {t: det_types.count(t) for t in set(det_types)}
        desc_parts = [f"{count} {obj}" for obj, count in det_counts.items()]

        scenario_id = f"coco_{split}_{img_id:012d}"
        scenario_spec = self.to_scenario_spec(
            scenario_id=scenario_id,
            category=category,
            name=f"COCO Scene {img_id}",
            description=f"Scene containing {', '.join(desc_parts)}. "
            "From COCO object detection dataset.",
            location="varies",
            camera_type="photograph",
            time_of_day="varies",
            weather="varies",
            media_format="image",
        )

        return ConvertedSample(
            scenario_id=scenario_id,
            category=category,
            source_path=img_path,
            expected_labels=expected_labels,
            scenario_spec=scenario_spec,
        )


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Convert COCO dataset to expected_labels.json format"
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to COCO raw directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to output directory",
    )
    parser.add_argument(
        "--split",
        default="val2017",
        help="Dataset split (default: val2017)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of samples to convert",
    )
    parser.add_argument(
        "--all-categories",
        action="store_true",
        help="Include all categories, not just security-relevant",
    )
    parser.add_argument(
        "--min-detections",
        type=int,
        default=1,
        help="Minimum detections per image (default: 1)",
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

    converter = COCOConverter(
        security_only=not args.all_categories,
        min_detections=args.min_detections,
        verbose=args.verbose,
    )
    samples = converter.convert(args.input, args.output, args.limit, args.split)

    logger.info("Converted %d samples", len(samples))
    return 0


if __name__ == "__main__":
    sys.exit(main())
