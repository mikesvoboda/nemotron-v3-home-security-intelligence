#!/usr/bin/env python3
"""FLIR ADAS Thermal Dataset converter.

Converts FLIR thermal/night imagery to expected_labels.json format.

FLIR ADAS structure:
    FLIR_ADAS/
    ├── train/
    │   ├── thermal_8_bit/    # Thermal images
    │   ├── RGB/              # RGB images (optional)
    │   └── thermal_annotations.json
    └── val/
        ├── thermal_8_bit/
        └── thermal_annotations.json

Annotation format (COCO-style JSON):
{
    "images": [...],
    "annotations": [...],
    "categories": [
        {"id": 1, "name": "person"},
        {"id": 2, "name": "bike"},
        {"id": 3, "name": "car"},
        {"id": 17, "name": "dog"},
        {"id": 18, "name": "skateboard"},
        {"id": 91, "name": "other_vehicle"}
    ]
}

Usage:
    uv run scripts/dataset_converters/flir_converter.py \
        --input data/external/flir/raw/FLIR_ADAS \
        --output data/external/flir/converted
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

# FLIR category mappings to our detection types
FLIR_CATEGORY_MAP = {
    1: ("person", "pedestrian"),
    2: ("bicycle", "cyclist"),
    3: ("car", "vehicle"),
    17: ("dog", "animal"),
    18: ("skateboard", "object"),
    91: ("other_vehicle", "vehicle"),
}


class FLIRConverter(DatasetConverter):
    """Converter for FLIR ADAS Thermal dataset."""

    dataset_name = "flir"
    source_format = "coco_json"

    def convert(
        self,
        source_path: Path,
        output_path: Path,
        limit: int | None = None,
    ) -> list[ConvertedSample]:
        """Convert FLIR dataset to expected_labels.json format.

        Args:
            source_path: Path to FLIR ADAS directory
            output_path: Path to output converted samples
            limit: Maximum number of samples to convert

        Returns:
            List of converted samples
        """
        samples: list[ConvertedSample] = []

        # Process train and val splits
        for split in ["train", "val"]:
            split_path = source_path / split
            if not split_path.exists():
                logger.warning("Split not found: %s", split_path)
                continue

            # Load annotations
            ann_file = split_path / "thermal_annotations.json"
            if not ann_file.exists():
                logger.warning("Annotations not found: %s", ann_file)
                continue

            annotations = json.loads(ann_file.read_text())
            images = {img["id"]: img for img in annotations.get("images", [])}
            categories = {cat["id"]: cat["name"] for cat in annotations.get("categories", [])}

            # Group annotations by image
            ann_by_image: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for ann in annotations.get("annotations", []):
                ann_by_image[ann["image_id"]].append(ann)

            logger.info(
                "Processing %s split: %d images, %d annotations",
                split,
                len(images),
                len(annotations.get("annotations", [])),
            )

            # Process each image
            for img_id, img_info in images.items():
                if limit and len(samples) >= limit:
                    break

                img_annotations = ann_by_image.get(img_id, [])
                if not img_annotations:
                    continue  # Skip images without annotations

                # Find image file
                img_filename = img_info.get("file_name", "")
                thermal_dir = split_path / "thermal_8_bit"
                img_path = thermal_dir / img_filename

                if not img_path.exists():
                    # Try without subdirectory
                    img_path = thermal_dir / Path(img_filename).name
                    if not img_path.exists():
                        continue

                # Convert annotations
                sample = self._convert_image(
                    img_id=img_id,
                    img_info=img_info,
                    img_path=img_path,
                    annotations=img_annotations,
                    categories=categories,
                    split=split,
                )

                if sample:
                    samples.append(sample)
                    self.write_sample(sample, output_path, copy_media=True)

            if limit and len(samples) >= limit:
                break

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
        categories: dict[int, str],
        split: str,
    ) -> ConvertedSample | None:
        """Convert a single image with its annotations.

        Args:
            img_id: Image ID
            _img_info: Image metadata (unused, for interface consistency)
            img_path: Path to image file
            annotations: List of annotations for this image
            categories: Category ID to name mapping
            split: Dataset split (train/val)

        Returns:
            Converted sample or None if conversion fails
        """
        detections: list[dict[str, Any]] = []
        has_person = False
        has_vehicle = False
        has_animal = False

        for ann in annotations:
            cat_id = ann.get("category_id")
            cat_name = categories.get(cat_id, "unknown")
            bbox = ann.get("bbox", [])  # [x, y, width, height]

            if len(bbox) != 4:
                continue

            # Get our mapping
            if cat_id in FLIR_CATEGORY_MAP:
                obj_type, detection_type = FLIR_CATEGORY_MAP[cat_id]
            else:
                obj_type = cat_name
                detection_type = "object"

            # Track what we detected
            if detection_type == "pedestrian":
                has_person = True
            elif detection_type == "vehicle":
                has_vehicle = True
            elif detection_type == "animal":
                has_animal = True

            # Convert bbox from [x, y, w, h] to [x1, y1, x2, y2]
            x, y, w, h = bbox
            detection = {
                "type": obj_type,
                "detection_class": detection_type,
                "confidence_min": 0.6,
                "confidence_max": 0.9,
                "bounding_box": {
                    "x1": int(x),
                    "y1": int(y),
                    "x2": int(x + w),
                    "y2": int(y + h),
                },
                "attributes": {
                    "thermal": True,
                    "flir_category_id": cat_id,
                },
            }
            detections.append(detection)

        # Determine risk category based on detections
        # Night/thermal footage with people is elevated risk
        if has_person:
            category = "suspicious"
            risk_min = 25
            risk_max = 50
            risk_level = "medium"
            risk_factors = ["person_at_night", "thermal_detection"]
        elif has_vehicle:
            category = "normal"
            risk_min = 10
            risk_max = 30
            risk_level = "low"
            risk_factors = ["vehicle_at_night"]
        elif has_animal:
            category = "normal"
            risk_min = 5
            risk_max = 20
            risk_level = "low"
            risk_factors = ["animal_at_night"]
        else:
            category = "normal"
            risk_min = 0
            risk_max = 15
            risk_level = "low"
            risk_factors = ["thermal_activity"]

        # Create expected labels
        expected_labels = self.to_expected_labels(
            detections=detections,
            risk_category=category,
            risk_min=risk_min,
            risk_max=risk_max,
            risk_level=risk_level,
            risk_factors=risk_factors,
        )

        # Create description based on detections
        detection_types = [d["type"] for d in detections]
        detection_counts = {t: detection_types.count(t) for t in set(detection_types)}
        desc_parts = [f"{count} {obj_type}(s)" for obj_type, count in detection_counts.items()]
        desc = (
            f"Night/thermal scene showing {', '.join(desc_parts)}. "
            "Thermal imagery from FLIR ADAS dataset."
        )

        # Create scenario spec
        scenario_id = f"flir_{split}_{img_id:06d}"
        scenario_spec = self.to_scenario_spec(
            scenario_id=scenario_id,
            category=category,
            name=f"Thermal {', '.join(detection_counts.keys())}",
            description=desc,
            location="street",
            camera_type="thermal_camera",
            time_of_day="night",
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
        description="Convert FLIR ADAS dataset to expected_labels.json format"
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to FLIR ADAS directory",
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
        logger.info("FLIR ADAS requires manual download from:")
        logger.info("  https://www.flir.com/oem/adas/adas-dataset-form/")
        return 1

    converter = FLIRConverter(verbose=args.verbose)
    samples = converter.convert(args.input, args.output, args.limit)

    logger.info("Converted %d samples", len(samples))
    return 0


if __name__ == "__main__":
    sys.exit(main())
