"""Compare local pipeline outputs against NVIDIA ground truth.

This module provides tools to compare the local RT-DETRv2 + Nemotron detection
pipeline against NVIDIA vision ground truth to evaluate detection accuracy
and risk score alignment.

Comparison metrics include:
- Detection IoU (Intersection over Union) for matched detections
- Detection recall and precision
- Risk score alignment and deviation
- Risk level agreement rate

Usage:
    comparator = PipelineComparator()

    # Compare single detection sets
    iou = comparator.calculate_detection_iou(local_detections, nvidia_detections)

    # Compare risk scores
    alignment = comparator.calculate_risk_alignment(local_risk=65, nvidia_risk=70)

    # Generate comprehensive report
    report = comparator.generate_comparison_report(local_df, nvidia_df)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd

# IoU threshold for considering detections as matching
DEFAULT_IOU_THRESHOLD = 0.5

# Risk score deviation threshold for "alignment"
DEFAULT_RISK_DEVIATION_THRESHOLD = 15


@dataclass
class ComparisonConfig:
    """Configuration for pipeline comparison."""

    iou_threshold: float = DEFAULT_IOU_THRESHOLD
    risk_deviation_threshold: int = DEFAULT_RISK_DEVIATION_THRESHOLD


@dataclass
class DetectionMatch:
    """Represents a matched pair of detections."""

    local_detection: dict[str, Any]
    nvidia_detection: dict[str, Any]
    iou: float
    type_match: bool


@dataclass
class ComparisonReport:
    """Comprehensive comparison report between local and NVIDIA pipeline."""

    total_images: int = 0
    detection_metrics: dict[str, Any] = field(default_factory=dict)
    risk_metrics: dict[str, Any] = field(default_factory=dict)
    per_category_metrics: dict[str, dict[str, Any]] = field(default_factory=dict)
    failure_cases: list[dict[str, Any]] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for serialization."""
        return {
            "total_images": self.total_images,
            "detection_metrics": self.detection_metrics,
            "risk_metrics": self.risk_metrics,
            "per_category_metrics": self.per_category_metrics,
            "failure_cases": self.failure_cases,
            "generated_at": self.generated_at,
        }


class PipelineComparator:
    """Compare local detection/risk pipeline against NVIDIA vision.

    This class provides methods to evaluate how well the local RT-DETRv2 +
    Nemotron pipeline matches NVIDIA's vision model analysis, which serves
    as ground truth.

    Comparison dimensions:
    - Detection accuracy: IoU between detected bounding boxes
    - Object type matching: Whether the same objects are detected
    - Risk score alignment: Deviation between risk scores
    - Risk level agreement: Whether categorical risk levels match

    Example:
        >>> comparator = PipelineComparator()
        >>> iou = comparator.calculate_detection_iou(local_dets, nvidia_dets)
        >>> print(f"Detection IoU: {iou:.2%}")
    """

    def __init__(self, config: ComparisonConfig | None = None) -> None:
        """Initialize the pipeline comparator.

        Args:
            config: Optional configuration for comparison thresholds.
        """
        self.config = config or ComparisonConfig()

    @staticmethod
    def _normalize_bbox(
        bbox: dict[str, Any] | list[int | float],
    ) -> tuple[float, float, float, float]:
        """Normalize a bounding box to (x, y, width, height) format.

        Args:
            bbox: Bounding box in dict or list format.

        Returns:
            Tuple of (x, y, width, height) as floats.
        """
        if isinstance(bbox, dict):
            return (
                float(bbox.get("x", 0)),
                float(bbox.get("y", 0)),
                float(bbox.get("width", 0)),
                float(bbox.get("height", 0)),
            )
        elif isinstance(bbox, list | tuple) and len(bbox) == 4:
            return (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
        else:
            return (0.0, 0.0, 0.0, 0.0)

    @staticmethod
    def _calculate_box_iou(
        box1: tuple[float, float, float, float],
        box2: tuple[float, float, float, float],
    ) -> float:
        """Calculate Intersection over Union between two bounding boxes.

        Both boxes should be in (x, y, width, height) format.

        Args:
            box1: First bounding box.
            box2: Second bounding box.

        Returns:
            IoU value between 0 and 1.
        """
        # Convert to (x1, y1, x2, y2) format
        x1_1, y1_1 = box1[0], box1[1]
        x2_1, y2_1 = box1[0] + box1[2], box1[1] + box1[3]

        x1_2, y1_2 = box2[0], box2[1]
        x2_2, y2_2 = box2[0] + box2[2], box2[1] + box2[3]

        # Calculate intersection
        inter_x1 = max(x1_1, x1_2)
        inter_y1 = max(y1_1, y1_2)
        inter_x2 = min(x2_1, x2_2)
        inter_y2 = min(y2_1, y2_2)

        inter_width = max(0, inter_x2 - inter_x1)
        inter_height = max(0, inter_y2 - inter_y1)
        inter_area = inter_width * inter_height

        # Calculate union
        area1 = box1[2] * box1[3]
        area2 = box2[2] * box2[3]
        union_area = area1 + area2 - inter_area

        # Avoid division by zero
        if union_area <= 0:
            return 0.0

        return inter_area / union_area

    @staticmethod
    def _normalize_object_type(obj_type: str) -> str:
        """Normalize object type for comparison.

        Maps various detection labels to a common set.
        """
        type_mapping = {
            "person": "person",
            "human": "person",
            "man": "person",
            "woman": "person",
            "child": "person",
            "car": "car",
            "automobile": "car",
            "vehicle": "car",
            "truck": "truck",
            "pickup": "truck",
            "van": "truck",
            "dog": "dog",
            "cat": "cat",
            "bicycle": "bicycle",
            "bike": "bicycle",
            "motorcycle": "motorcycle",
            "motorbike": "motorcycle",
            "bus": "bus",
        }
        return type_mapping.get(obj_type.lower(), obj_type.lower())

    def calculate_detection_iou(
        self,
        local_detections: list[dict[str, Any]],
        nvidia_detections: list[dict[str, Any]],
    ) -> float:
        """Calculate average Intersection over Union for matched detections.

        Uses greedy matching: for each NVIDIA detection, find the local detection
        with highest IoU that matches the object type, then compute average IoU
        across all matched pairs.

        Args:
            local_detections: List of detections from local RT-DETRv2 pipeline.
                Each detection should have 'type'/'object_type' and 'bbox' fields.
            nvidia_detections: List of detections from NVIDIA vision.
                Each detection should have 'type' and 'bbox' fields.

        Returns:
            Average IoU across matched detections (0-1).
            Returns 0 if no detections to compare.
        """
        if not nvidia_detections:
            return 1.0 if not local_detections else 0.0

        if not local_detections:
            return 0.0

        # Track which local detections have been matched
        used_local: set[int] = set()
        matched_ious: list[float] = []

        for nvidia_det in nvidia_detections:
            nvidia_type = self._normalize_object_type(
                nvidia_det.get("type", nvidia_det.get("object_type", "unknown"))
            )
            nvidia_bbox = self._normalize_bbox(nvidia_det.get("bbox", [0, 0, 0, 0]))

            best_iou = 0.0
            best_idx = -1

            for idx, local_det in enumerate(local_detections):
                if idx in used_local:
                    continue

                local_type = self._normalize_object_type(
                    local_det.get("type", local_det.get("object_type", "unknown"))
                )
                local_bbox = self._normalize_bbox(local_det.get("bbox", [0, 0, 0, 0]))

                # Only match same object types
                if local_type != nvidia_type:
                    continue

                iou = self._calculate_box_iou(local_bbox, nvidia_bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_idx = idx

            if best_idx >= 0:
                used_local.add(best_idx)
                matched_ious.append(best_iou)
            else:
                # No matching local detection found for this NVIDIA detection
                matched_ious.append(0.0)

        return sum(matched_ious) / len(matched_ious) if matched_ious else 0.0

    def calculate_detection_metrics(
        self,
        local_detections: list[dict[str, Any]],
        nvidia_detections: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Calculate comprehensive detection metrics.

        Args:
            local_detections: Local pipeline detections.
            nvidia_detections: NVIDIA ground truth detections.

        Returns:
            Dictionary with:
            - average_iou: Mean IoU across matched detections
            - precision: Proportion of local detections that match NVIDIA
            - recall: Proportion of NVIDIA detections matched by local
            - f1_score: Harmonic mean of precision and recall
            - local_count: Number of local detections
            - nvidia_count: Number of NVIDIA detections
            - matched_count: Number of successfully matched pairs
        """
        if not nvidia_detections and not local_detections:
            return {
                "average_iou": 1.0,
                "precision": 1.0,
                "recall": 1.0,
                "f1_score": 1.0,
                "local_count": 0,
                "nvidia_count": 0,
                "matched_count": 0,
            }

        # Match detections and compute IoU
        matches: list[DetectionMatch] = []
        used_local: set[int] = set()

        for nvidia_det in nvidia_detections:
            nvidia_type = self._normalize_object_type(
                nvidia_det.get("type", nvidia_det.get("object_type", "unknown"))
            )
            nvidia_bbox = self._normalize_bbox(nvidia_det.get("bbox", [0, 0, 0, 0]))

            best_match: DetectionMatch | None = None
            best_iou = self.config.iou_threshold
            best_idx = -1

            for idx, local_det in enumerate(local_detections):
                if idx in used_local:
                    continue

                local_type = self._normalize_object_type(
                    local_det.get("type", local_det.get("object_type", "unknown"))
                )
                local_bbox = self._normalize_bbox(local_det.get("bbox", [0, 0, 0, 0]))

                iou = self._calculate_box_iou(local_bbox, nvidia_bbox)
                type_match = local_type == nvidia_type

                if iou >= best_iou:
                    best_iou = iou
                    best_idx = idx
                    best_match = DetectionMatch(
                        local_detection=local_det,
                        nvidia_detection=nvidia_det,
                        iou=iou,
                        type_match=type_match,
                    )

            if best_match is not None and best_idx >= 0:
                used_local.add(best_idx)
                matches.append(best_match)

        # Calculate metrics
        matched_count = len(matches)
        nvidia_count = len(nvidia_detections)
        local_count = len(local_detections)

        average_iou = sum(m.iou for m in matches) / matched_count if matched_count > 0 else 0.0

        # Precision: of local detections, how many matched NVIDIA
        precision = matched_count / local_count if local_count > 0 else 0.0

        # Recall: of NVIDIA detections, how many were matched by local
        recall = matched_count / nvidia_count if nvidia_count > 0 else 0.0

        # F1 score
        f1_score = (
            2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        )

        return {
            "average_iou": average_iou,
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "local_count": local_count,
            "nvidia_count": nvidia_count,
            "matched_count": matched_count,
        }

    def calculate_risk_alignment(
        self,
        local_risk: int,
        nvidia_risk: int,
    ) -> dict[str, Any]:
        """Calculate risk score alignment metrics.

        Args:
            local_risk: Risk score from local Nemotron pipeline (0-100).
            nvidia_risk: Risk score from NVIDIA vision (0-100).

        Returns:
            Dictionary with:
            - local_score: The local risk score
            - nvidia_score: The NVIDIA risk score
            - deviation: Absolute difference between scores
            - aligned: Whether deviation is within threshold
            - direction: 'over' if local > nvidia, 'under' if local < nvidia, 'exact' if equal
        """
        deviation = abs(local_risk - nvidia_risk)
        aligned = deviation <= self.config.risk_deviation_threshold

        if local_risk > nvidia_risk:
            direction = "over"
        elif local_risk < nvidia_risk:
            direction = "under"
        else:
            direction = "exact"

        return {
            "local_score": local_risk,
            "nvidia_score": nvidia_risk,
            "deviation": deviation,
            "aligned": aligned,
            "direction": direction,
        }

    @staticmethod
    def _score_to_level(score: int) -> str:
        """Convert a numeric risk score to a risk level."""
        if score < 0:
            return "error"
        elif score <= 25:
            return "low"
        elif score <= 55:
            return "medium"
        elif score <= 85:
            return "high"
        else:
            return "critical"

    def calculate_risk_level_agreement(
        self,
        local_risk: int,
        nvidia_risk: int,
    ) -> dict[str, Any]:
        """Calculate whether risk levels agree.

        Args:
            local_risk: Risk score from local pipeline.
            nvidia_risk: Risk score from NVIDIA vision.

        Returns:
            Dictionary with level agreement details.
        """
        local_level = self._score_to_level(local_risk)
        nvidia_level = self._score_to_level(nvidia_risk)

        return {
            "local_level": local_level,
            "nvidia_level": nvidia_level,
            "agreement": local_level == nvidia_level,
        }

    def _parse_detections_from_row(self, row: dict[str, Any], column: str) -> list[dict[str, Any]]:
        """Parse detections from a DataFrame row, handling JSON strings."""
        dets = row.get(column, "[]")
        if isinstance(dets, str):
            parsed: list[dict[str, Any]] = json.loads(dets)
            return parsed
        return dets if dets else []

    def _aggregate_detection_metrics(self, all_metrics: list[dict[str, Any]]) -> dict[str, Any]:
        """Aggregate detection metrics across all images."""
        if not all_metrics:
            return {}
        n = len(all_metrics)
        return {
            "average_iou": sum(m["average_iou"] for m in all_metrics) / n,
            "average_precision": sum(m["precision"] for m in all_metrics) / n,
            "average_recall": sum(m["recall"] for m in all_metrics) / n,
            "average_f1": sum(m["f1_score"] for m in all_metrics) / n,
            "total_local_detections": sum(m["local_count"] for m in all_metrics),
            "total_nvidia_detections": sum(m["nvidia_count"] for m in all_metrics),
            "total_matched": sum(m["matched_count"] for m in all_metrics),
            "iou_threshold_met_rate": sum(
                1 for m in all_metrics if m["average_iou"] >= self.config.iou_threshold
            )
            / n,
        }

    def _aggregate_risk_metrics(
        self,
        all_alignments: list[dict[str, Any]],
        all_levels: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Aggregate risk alignment metrics across all images."""
        if not all_alignments:
            return {}
        n = len(all_alignments)
        return {
            "average_deviation": sum(a["deviation"] for a in all_alignments) / n,
            "max_deviation": max(a["deviation"] for a in all_alignments),
            "min_deviation": min(a["deviation"] for a in all_alignments),
            "alignment_rate": sum(1 for a in all_alignments if a["aligned"]) / n,
            "over_estimate_rate": sum(1 for a in all_alignments if a["direction"] == "over") / n,
            "under_estimate_rate": sum(1 for a in all_alignments if a["direction"] == "under") / n,
            "level_agreement_rate": sum(1 for a in all_levels if a["agreement"]) / len(all_levels),
        }

    def generate_comparison_report(
        self,
        local_results: pd.DataFrame,
        nvidia_ground_truth: pd.DataFrame,
    ) -> ComparisonReport:
        """Generate comprehensive comparison report.

        Args:
            local_results: DataFrame with local pipeline results.
                Expected columns: image_path, detections (JSON), risk_score
            nvidia_ground_truth: DataFrame with NVIDIA ground truth.
                Expected columns: image_path, nvidia_detected_objects (JSON),
                nvidia_risk_score, category

        Returns:
            ComparisonReport with aggregate and per-image metrics.
        """
        try:
            import pandas as pd
        except ImportError as e:
            raise ImportError(
                "pandas is required for report generation. Install with: uv sync --extra nemo"
            ) from e

        # Handle empty DataFrames
        if len(local_results) == 0 or len(nvidia_ground_truth) == 0:
            return ComparisonReport(total_images=0)

        # Check if required columns exist
        if "image_path" not in local_results.columns:
            return ComparisonReport(total_images=0)
        if "image_path" not in nvidia_ground_truth.columns:
            return ComparisonReport(total_images=0)

        # Merge on image path
        merged = pd.merge(
            local_results,
            nvidia_ground_truth,
            on="image_path",
            how="inner",
            suffixes=("_local", "_nvidia"),
        )

        report = ComparisonReport(total_images=len(merged))

        if len(merged) == 0:
            return report

        # Aggregate detection metrics
        all_detection_metrics: list[dict[str, Any]] = []
        all_risk_alignments: list[dict[str, Any]] = []
        all_level_agreements: list[dict[str, Any]] = []
        failure_cases: list[dict[str, Any]] = []

        # Per-category accumulators
        category_metrics: dict[str, list[dict[str, Any]]] = {}

        for _, row in merged.iterrows():
            # Parse detections
            local_dets = self._parse_detections_from_row(row, "detections")
            nvidia_dets = self._parse_detections_from_row(row, "nvidia_detected_objects")

            # Get risk scores
            local_risk = int(row.get("risk_score", 50))
            nvidia_risk = int(row.get("nvidia_risk_score", 50))

            # Calculate metrics
            det_metrics = self.calculate_detection_metrics(local_dets, nvidia_dets)
            risk_alignment = self.calculate_risk_alignment(local_risk, nvidia_risk)
            level_agreement = self.calculate_risk_level_agreement(local_risk, nvidia_risk)

            all_detection_metrics.append(det_metrics)
            all_risk_alignments.append(risk_alignment)
            all_level_agreements.append(level_agreement)

            # Track by category
            category = row.get("category", "unknown")
            if category not in category_metrics:
                category_metrics[category] = []
            category_metrics[category].append(
                {
                    "detection": det_metrics,
                    "risk_alignment": risk_alignment,
                    "level_agreement": level_agreement,
                }
            )

            # Track failure cases
            if (
                not risk_alignment["aligned"]
                or det_metrics["average_iou"] < self.config.iou_threshold
            ):
                failure_cases.append(
                    {
                        "image_path": row.get("image_path"),
                        "category": category,
                        "detection_iou": det_metrics["average_iou"],
                        "risk_deviation": risk_alignment["deviation"],
                        "local_risk": local_risk,
                        "nvidia_risk": nvidia_risk,
                        "local_detections": len(local_dets),
                        "nvidia_detections": len(nvidia_dets),
                    }
                )

        # Aggregate detection metrics
        report.detection_metrics = self._aggregate_detection_metrics(all_detection_metrics)

        # Aggregate risk metrics
        report.risk_metrics = self._aggregate_risk_metrics(
            all_risk_alignments, all_level_agreements
        )

        # Per-category aggregation
        for category, metrics_list in category_metrics.items():
            if not metrics_list:
                continue

            cat_det = [m["detection"] for m in metrics_list]
            cat_risk = [m["risk_alignment"] for m in metrics_list]
            cat_level = [m["level_agreement"] for m in metrics_list]

            report.per_category_metrics[category] = {
                "count": len(metrics_list),
                "average_iou": sum(m["average_iou"] for m in cat_det) / len(cat_det),
                "average_risk_deviation": sum(m["deviation"] for m in cat_risk) / len(cat_risk),
                "risk_alignment_rate": sum(1 for m in cat_risk if m["aligned"]) / len(cat_risk),
                "level_agreement_rate": sum(1 for m in cat_level if m["agreement"])
                / len(cat_level),
            }

        report.failure_cases = failure_cases

        return report

    def generate_summary(self, report: ComparisonReport) -> str:
        """Generate a human-readable summary of the comparison report.

        Args:
            report: Comparison report to summarize.

        Returns:
            Formatted string summary.
        """
        lines = [
            "=" * 60,
            "Pipeline Comparison Summary",
            "=" * 60,
            f"Total Images Compared: {report.total_images}",
            "",
            "Detection Metrics:",
            f"  Average IoU: {report.detection_metrics.get('average_iou', 0):.2%}",
            f"  Precision: {report.detection_metrics.get('average_precision', 0):.2%}",
            f"  Recall: {report.detection_metrics.get('average_recall', 0):.2%}",
            f"  F1 Score: {report.detection_metrics.get('average_f1', 0):.2%}",
            f"  IoU Threshold Met: {report.detection_metrics.get('iou_threshold_met_rate', 0):.2%}",
            "",
            "Risk Score Metrics:",
            f"  Average Deviation: {report.risk_metrics.get('average_deviation', 0):.1f} points",
            f"  Alignment Rate (within {self.config.risk_deviation_threshold} points): {report.risk_metrics.get('alignment_rate', 0):.2%}",
            f"  Level Agreement Rate: {report.risk_metrics.get('level_agreement_rate', 0):.2%}",
            "",
            "Per-Category Metrics:",
        ]

        for category, metrics in report.per_category_metrics.items():
            lines.extend(
                [
                    f"  {category.upper()}:",
                    f"    Count: {metrics.get('count', 0)}",
                    f"    Avg IoU: {metrics.get('average_iou', 0):.2%}",
                    f"    Avg Risk Deviation: {metrics.get('average_risk_deviation', 0):.1f}",
                    f"    Risk Alignment: {metrics.get('risk_alignment_rate', 0):.2%}",
                ]
            )

        lines.extend(
            [
                "",
                f"Failure Cases: {len(report.failure_cases)}",
            ]
        )

        if report.failure_cases[:5]:
            lines.append("  Top failures:")
            for case in report.failure_cases[:5]:
                lines.append(
                    f"    - {case.get('image_path', 'unknown')}: "
                    f"IoU={case.get('detection_iou', 0):.2f}, "
                    f"Risk Dev={case.get('risk_deviation', 0)}"
                )

        lines.append("=" * 60)

        return "\n".join(lines)
