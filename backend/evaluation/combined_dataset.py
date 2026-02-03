"""Combined dataset loader for synthetic and external evaluation data.

This module provides utilities for loading both synthetic scenarios and
converted external datasets into a unified format for AI pipeline evaluation.

Example Usage:
    >>> from backend.evaluation.combined_dataset import load_combined_dataset
    >>> samples = load_combined_dataset(
    ...     include_synthetic=True,
    ...     include_external=["ccpd", "flir"],
    ...     categories=["normal", "suspicious"],
    ... )
    >>> print(f"Loaded {len(samples)} total samples")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.evaluation.prompt_eval_dataset import (
    PromptEvalSample,
    load_synthetic_eval_dataset,
)

logger = logging.getLogger(__name__)

# Default paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_SYNTHETIC_DIR = PROJECT_ROOT / "data" / "synthetic"
DEFAULT_EXTERNAL_DIR = PROJECT_ROOT / "data" / "external"

# Available external datasets
EXTERNAL_DATASETS = ["ccpd", "coco", "kinetics", "shanghaitech", "flir"]


def load_external_dataset(
    dataset_name: str,
    external_dir: Path | None = None,
    categories: list[str] | None = None,
) -> list[PromptEvalSample]:
    """Load a converted external dataset.

    Args:
        dataset_name: Name of the external dataset (ccpd, coco, etc.)
        external_dir: Base directory for external datasets
        categories: Optional category filter

    Returns:
        List of PromptEvalSample objects
    """
    if external_dir is None:
        external_dir = DEFAULT_EXTERNAL_DIR

    converted_dir = external_dir / dataset_name / "converted"
    if not converted_dir.exists():
        logger.debug("External dataset not found: %s", converted_dir)
        return []

    # Use the same loader but point to converted directory
    samples = load_synthetic_eval_dataset(
        data_dir=converted_dir,
        categories=categories,
    )

    # Tag samples with their source
    for sample in samples:
        sample.metadata["external_source"] = dataset_name

    logger.info("Loaded %d samples from external dataset: %s", len(samples), dataset_name)
    return samples


def load_combined_dataset(
    include_synthetic: bool = True,
    include_external: list[str] | None = None,
    categories: list[str] | None = None,
    synthetic_dir: Path | None = None,
    external_dir: Path | None = None,
) -> list[PromptEvalSample]:
    """Load combined synthetic and external evaluation samples.

    This function provides a unified interface for loading evaluation data
    from multiple sources, enabling comprehensive AI pipeline testing.

    Args:
        include_synthetic: Whether to include synthetic scenarios
        include_external: List of external datasets to include.
            None means include all available, empty list means none.
        categories: Optional category filter (normal, suspicious, threats)
        synthetic_dir: Path to synthetic data directory
        external_dir: Path to external datasets directory

    Returns:
        Combined list of PromptEvalSample objects from all sources

    Example:
        >>> # Load everything
        >>> all_samples = load_combined_dataset()
        >>>
        >>> # Load only synthetic + CCPD for license plate testing
        >>> plate_samples = load_combined_dataset(
        ...     include_external=["ccpd"],
        ...     categories=["normal"],
        ... )
        >>>
        >>> # Load only external datasets
        >>> external_only = load_combined_dataset(
        ...     include_synthetic=False,
        ...     include_external=["flir", "kinetics"],
        ... )
    """
    samples: list[PromptEvalSample] = []

    # Load synthetic data
    if include_synthetic:
        synthetic_samples = load_synthetic_eval_dataset(
            data_dir=synthetic_dir or DEFAULT_SYNTHETIC_DIR,
            categories=categories,
        )
        for sample in synthetic_samples:
            sample.metadata["source_type"] = "synthetic"
        samples.extend(synthetic_samples)
        logger.info("Loaded %d synthetic samples", len(synthetic_samples))

    # Load external datasets
    if include_external is None:
        # Load all available
        include_external = EXTERNAL_DATASETS
    elif not include_external:
        # Empty list = no external
        include_external = []

    for dataset_name in include_external:
        if dataset_name not in EXTERNAL_DATASETS:
            logger.warning("Unknown external dataset: %s", dataset_name)
            continue

        external_samples = load_external_dataset(
            dataset_name=dataset_name,
            external_dir=external_dir or DEFAULT_EXTERNAL_DIR,
            categories=categories,
        )
        for sample in external_samples:
            sample.metadata["source_type"] = "external"
        samples.extend(external_samples)

    logger.info("Loaded %d total samples (combined)", len(samples))
    return samples


def get_combined_summary(samples: list[PromptEvalSample]) -> dict[str, Any]:
    """Get summary statistics for combined dataset.

    Args:
        samples: List of PromptEvalSample objects

    Returns:
        Summary statistics dictionary
    """
    if not samples:
        return {
            "total_samples": 0,
            "by_source": {},
            "by_category": {},
            "by_risk_level": {},
            "with_media": 0,
        }

    by_source: dict[str, int] = {}
    by_category: dict[str, int] = {}
    by_risk_level: dict[str, int] = {}
    with_media = 0

    for sample in samples:
        # Source
        source = sample.metadata.get("external_source", "synthetic")
        by_source[source] = by_source.get(source, 0) + 1

        # Category
        by_category[sample.category] = by_category.get(sample.category, 0) + 1

        # Risk level
        by_risk_level[sample.expected_risk_level] = (
            by_risk_level.get(sample.expected_risk_level, 0) + 1
        )

        # Media
        if sample.has_media:
            with_media += 1

    return {
        "total_samples": len(samples),
        "by_source": by_source,
        "by_category": by_category,
        "by_risk_level": by_risk_level,
        "with_media": with_media,
    }


def filter_by_source(
    samples: list[PromptEvalSample],
    sources: list[str],
) -> list[PromptEvalSample]:
    """Filter samples by source (synthetic or external dataset name).

    Args:
        samples: List of samples to filter
        sources: List of source names to include

    Returns:
        Filtered list of samples
    """
    result = []
    for sample in samples:
        source = sample.metadata.get("external_source", "synthetic")
        if source in sources:
            result.append(sample)
    return result


def filter_by_detection_type(
    samples: list[PromptEvalSample],
    detection_types: list[str],
) -> list[PromptEvalSample]:
    """Filter samples that contain specific detection types.

    Args:
        samples: List of samples to filter
        detection_types: Detection types to look for (e.g., ["person", "vehicle"])

    Returns:
        Samples containing any of the specified detection types
    """
    result = []
    for sample in samples:
        detections = sample.expected_labels.get("detections", [])
        for det in detections:
            if det.get("type") in detection_types:
                result.append(sample)
                break
    return result


def filter_by_risk_range(
    samples: list[PromptEvalSample],
    min_score: int = 0,
    max_score: int = 100,
) -> list[PromptEvalSample]:
    """Filter samples by expected risk score range.

    Args:
        samples: List of samples to filter
        min_score: Minimum expected risk score
        max_score: Maximum expected risk score

    Returns:
        Samples within the specified risk range
    """
    result = []
    for sample in samples:
        sample_min, sample_max = sample.expected_risk_range
        # Include if ranges overlap
        if sample_max >= min_score and sample_min <= max_score:
            result.append(sample)
    return result


def get_samples_for_model(
    samples: list[PromptEvalSample],
    model_name: str,
) -> list[PromptEvalSample]:
    """Get samples relevant for testing a specific AI model.

    Args:
        samples: List of all samples
        model_name: Name of the AI model to test

    Returns:
        Filtered samples relevant for the model
    """
    # Model-specific filtering
    model_filters: dict[str, dict[str, Any]] = {
        "yolo": {"detection_types": ["person", "vehicle", "animal"]},
        "face_detector": {"detection_types": ["person"]},
        "plate_detector": {"detection_types": ["license_plate", "vehicle"]},
        "action_recognizer": {"has_actions": True},
        "pose_estimator": {"detection_types": ["person"]},
        "threat_detector": {"risk_min": 40},
        "vehicle_classifier": {"detection_types": ["vehicle"]},
        "pet_classifier": {"detection_types": ["animal"]},
        "depth_estimator": {},  # All samples
        "florence": {},  # All samples
        "clip": {},  # All samples
        "nemotron": {},  # All samples
    }

    filters = model_filters.get(model_name.lower(), {})

    result = samples

    # Apply detection type filter
    if "detection_types" in filters:
        result = filter_by_detection_type(result, filters["detection_types"])

    # Apply risk filter
    if "risk_min" in filters:
        result = filter_by_risk_range(result, min_score=filters["risk_min"])

    # Apply action filter
    if filters.get("has_actions"):
        result = [s for s in result if s.expected_labels.get("actions")]

    return result
