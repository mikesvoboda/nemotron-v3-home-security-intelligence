"""Dataset converters for external datasets.

This module provides utilities for converting external datasets
to the expected_labels.json format used by the AI evaluation pipeline.

Example Usage:
    >>> from scripts.dataset_converters import CCPDConverter
    >>> converter = CCPDConverter()
    >>> converter.convert(
    ...     source_path=Path("data/external/ccpd/raw"),
    ...     output_path=Path("data/external/ccpd/converted"),
    ... )
"""

from __future__ import annotations

import json
import logging
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ConvertedSample:
    """A converted sample ready for expected_labels.json format."""

    scenario_id: str
    category: str  # normal, suspicious, threats
    source_path: Path
    expected_labels: dict[str, Any]
    scenario_spec: dict[str, Any]


# Risk level mappings for external dataset annotations
RISK_MAPPINGS: dict[str, tuple[str, int, int, str]] = {
    # Kinetics actions -> (category, min_score, max_score, level)
    # Threatening actions
    "punching_person_(boxing)": ("threats", 70, 90, "high"),
    "wrestling": ("threats", 60, 80, "high"),
    "slapping": ("threats", 65, 85, "high"),
    "kicking_person": ("threats", 70, 90, "high"),
    "headbutting": ("threats", 75, 95, "critical"),
    "throwing_axe": ("threats", 85, 100, "critical"),
    "throwing_ball": ("normal", 0, 15, "low"),
    "shooting_goal_(soccer)": ("normal", 0, 15, "low"),
    # Suspicious actions
    "climbing_a_rope": ("suspicious", 30, 50, "medium"),
    "climbing_ladder": ("suspicious", 25, 45, "medium"),
    "climbing_tree": ("suspicious", 20, 40, "low"),
    "crawling_baby": ("normal", 0, 10, "low"),
    "opening_door": ("normal", 0, 20, "low"),
    "opening_present": ("normal", 0, 10, "low"),
    "opening_bottle": ("normal", 0, 10, "low"),
    "picking_fruit": ("normal", 0, 15, "low"),
    "picking_up": ("normal", 0, 15, "low"),
    # Normal activities
    "walking_the_dog": ("normal", 0, 15, "low"),
    "walking_through_snow": ("normal", 0, 10, "low"),
    "jogging": ("normal", 0, 15, "low"),
    "running_on_treadmill": ("normal", 0, 10, "low"),
    "riding_a_bike": ("normal", 0, 15, "low"),
    "riding_scooter": ("normal", 0, 15, "low"),
    "getting_out_of_car": ("normal", 0, 20, "low"),
    "parking_car": ("normal", 0, 15, "low"),
    "delivering_mail": ("normal", 0, 20, "low"),
    "mowing_lawn": ("normal", 0, 10, "low"),
    "gardening": ("normal", 0, 10, "low"),
    "watering_plants": ("normal", 0, 10, "low"),
    # ShanghaiTech anomalies
    "loitering": ("suspicious", 30, 50, "medium"),
    "wrong_direction": ("suspicious", 20, 40, "low"),
    "running_in_crowd": ("suspicious", 25, 45, "medium"),
    "jumping_fence": ("suspicious", 40, 60, "medium"),
    "fighting": ("threats", 70, 90, "high"),
    "throwing_object": ("suspicious", 35, 55, "medium"),
    "stealing": ("threats", 75, 95, "critical"),
    "vandalism": ("threats", 65, 85, "high"),
    # COCO objects - context-dependent
    "person": ("normal", 0, 30, "low"),
    "car": ("normal", 0, 20, "low"),
    "truck": ("normal", 0, 20, "low"),
    "bicycle": ("normal", 0, 15, "low"),
    "motorcycle": ("normal", 0, 20, "low"),
    "dog": ("normal", 0, 15, "low"),
    "cat": ("normal", 0, 15, "low"),
    "bird": ("normal", 0, 10, "low"),
    # Vehicles with plates
    "vehicle_with_plate": ("normal", 0, 25, "low"),
    "unknown_vehicle": ("suspicious", 20, 40, "low"),
    # Night/thermal
    "person_night": ("suspicious", 25, 45, "medium"),
    "vehicle_night": ("normal", 10, 30, "low"),
}


def get_risk_mapping(
    annotation: str,
    time_of_day: str = "day",
    context: dict[str, Any] | None = None,
) -> tuple[str, int, int, str]:
    """Get risk mapping for an annotation with context.

    Args:
        annotation: The annotation label (action, object, etc.)
        time_of_day: 'day' or 'night'
        context: Additional context (location, etc.)

    Returns:
        Tuple of (category, min_score, max_score, level)
    """
    # Normalize annotation
    annotation_lower = annotation.lower().replace(" ", "_")

    # Check for direct mapping
    if annotation_lower in RISK_MAPPINGS:
        category, min_score, max_score, level = RISK_MAPPINGS[annotation_lower]

        # Adjust for night context
        if time_of_day == "night" and category == "normal":
            min_score = min(min_score + 10, 100)
            max_score = min(max_score + 15, 100)
            if max_score > 30:
                level = "low"
            if max_score > 50:
                category = "suspicious"
                level = "medium"

        return (category, min_score, max_score, level)

    # Default mapping for unknown annotations
    logger.warning("Unknown annotation: %s, using default mapping", annotation)
    return ("normal", 0, 30, "low")


class DatasetConverter(ABC):
    """Base class for dataset converters.

    Subclasses implement convert() to transform external dataset formats
    into the expected_labels.json format used by the evaluation pipeline.
    """

    dataset_name: str = "unknown"
    source_format: str = "unknown"

    def __init__(self, verbose: bool = False):
        """Initialize converter.

        Args:
            verbose: Enable verbose logging
        """
        self.verbose = verbose
        if verbose:
            logging.getLogger(__name__).setLevel(logging.DEBUG)

    @abstractmethod
    def convert(
        self,
        source_path: Path,
        output_path: Path,
        limit: int | None = None,
    ) -> list[ConvertedSample]:
        """Convert source dataset to expected_labels.json format.

        Args:
            source_path: Path to raw dataset directory
            output_path: Path to output converted samples
            limit: Maximum number of samples to convert

        Returns:
            List of converted samples
        """
        raise NotImplementedError

    def to_expected_labels(
        self,
        detections: list[dict[str, Any]],
        risk_category: str,
        risk_min: int,
        risk_max: int,
        risk_level: str,
        risk_factors: list[str] | None = None,
        actions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create expected_labels.json content.

        Args:
            detections: List of detection dictionaries
            risk_category: Category (normal, suspicious, threats)
            risk_min: Minimum expected risk score
            risk_max: Maximum expected risk score
            risk_level: Risk level (low, medium, high, critical)
            risk_factors: Optional list of risk factor descriptions
            actions: Optional list of action detections

        Returns:
            Expected labels dictionary
        """
        labels: dict[str, Any] = {
            "source": self.dataset_name,
            "category": risk_category,
            "detections": detections,
            "risk": {
                "min_score": risk_min,
                "max_score": risk_max,
                "level": risk_level,
                "expected_factors": risk_factors or [],
            },
        }

        if actions:
            labels["actions"] = actions

        return labels

    def to_scenario_spec(
        self,
        scenario_id: str,
        category: str,
        name: str,
        description: str,
        location: str = "unknown",
        camera_type: str = "security_camera",
        time_of_day: str = "day",
        weather: str = "clear",
        media_format: str = "image",
        duration_sec: float | None = None,
    ) -> dict[str, Any]:
        """Create scenario_spec.json content.

        Args:
            scenario_id: Unique scenario identifier
            category: Category (normal, suspicious, threats)
            name: Human-readable scenario name
            description: Detailed scenario description
            location: Scene location
            camera_type: Type of camera view
            time_of_day: day, night, dawn, dusk
            weather: Weather conditions
            media_format: image or video
            duration_sec: Video duration if applicable

        Returns:
            Scenario specification dictionary
        """
        spec: dict[str, Any] = {
            "id": scenario_id,
            "category": category,
            "name": name,
            "description": description,
            "source": self.dataset_name,
            "scene": {
                "location": location,
                "camera_type": camera_type,
                "resolution": "varies",
            },
            "environment": {
                "time_of_day": time_of_day,
                "weather": weather,
            },
            "generation": {
                "format": media_format,
            },
        }

        if duration_sec is not None:
            spec["generation"]["duration_sec"] = duration_sec

        return spec

    def write_sample(
        self,
        sample: ConvertedSample,
        output_path: Path,
        copy_media: bool = True,
    ) -> Path:
        """Write a converted sample to disk.

        Args:
            sample: Converted sample to write
            output_path: Base output directory
            copy_media: Whether to copy source media

        Returns:
            Path to sample directory
        """
        # Create sample directory
        sample_dir = output_path / sample.category / sample.scenario_id
        sample_dir.mkdir(parents=True, exist_ok=True)

        # Write expected_labels.json
        labels_path = sample_dir / "expected_labels.json"
        labels_path.write_text(json.dumps(sample.expected_labels, indent=2))

        # Write scenario_spec.json
        spec_path = sample_dir / "scenario_spec.json"
        spec_path.write_text(json.dumps(sample.scenario_spec, indent=2))

        # Copy media if requested
        if copy_media and sample.source_path.exists():
            media_dir = sample_dir / "media"
            media_dir.mkdir(exist_ok=True)
            dest_path = media_dir / sample.source_path.name
            shutil.copy2(sample.source_path, dest_path)

        # Write metadata
        metadata_path = sample_dir / "metadata.json"
        metadata = {
            "converted_at": datetime.now().isoformat(),
            "converter": self.__class__.__name__,
            "source_dataset": self.dataset_name,
            "source_path": str(sample.source_path),
        }
        metadata_path.write_text(json.dumps(metadata, indent=2))

        return sample_dir

    def get_conversion_stats(self, samples: list[ConvertedSample]) -> dict[str, Any]:
        """Get statistics about converted samples.

        Args:
            samples: List of converted samples

        Returns:
            Statistics dictionary
        """
        by_category: dict[str, int] = {}
        by_risk_level: dict[str, int] = {}

        for sample in samples:
            by_category[sample.category] = by_category.get(sample.category, 0) + 1
            level = sample.expected_labels.get("risk", {}).get("level", "unknown")
            by_risk_level[level] = by_risk_level.get(level, 0) + 1

        return {
            "total_samples": len(samples),
            "by_category": by_category,
            "by_risk_level": by_risk_level,
            "dataset": self.dataset_name,
        }


# Export converters (implemented in separate files)
__all__ = [
    "RISK_MAPPINGS",
    "ConvertedSample",
    "DatasetConverter",
    "get_risk_mapping",
]
