"""Generate ground truth from curated test images using NVIDIA vision.

This module provides functionality to generate ground truth datasets from
curated security camera images by analyzing them with NVIDIA's vision models.

The generator:
1. Discovers images organized by category (normal/, suspicious/, threat/, edge_case/)
2. Analyzes each image with NVIDIA vision API
3. Creates a structured DataFrame with ground truth data
4. Exports to parquet format for use in evaluation

Usage:
    generator = MultimodalGroundTruthGenerator(
        image_dir=Path("backend/tests/fixtures/synthetic/images"),
        analyzer=NVIDIAVisionAnalyzer()
    )
    ground_truth_df = await generator.generate_ground_truth()
    generator.export_ground_truth(Path("ground_truth.parquet"))
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd

from tools.nemo_data_designer.multimodal.image_analyzer import (
    NVIDIAVisionAnalyzer,
    VisionAnalysisResult,
)

# Supported image formats
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

# Valid category directories
VALID_CATEGORIES = {"normal", "suspicious", "threat", "edge_case"}


@dataclass
class GroundTruthConfig:
    """Configuration for ground truth generation."""

    max_concurrency: int = 5
    use_cache: bool = True
    include_raw_response: bool = False
    categories: set[str] = field(default_factory=lambda: VALID_CATEGORIES.copy())


class MultimodalGroundTruthGenerator:
    """Generate ground truth dataset from images using NVIDIA vision.

    This class scans a directory of curated test images organized by category,
    analyzes each image with NVIDIA's vision API, and produces a structured
    ground truth dataset for evaluating the local detection pipeline.

    Directory structure expected:
        images/
            normal/
                image1.jpg
                image2.jpg
            suspicious/
                suspect1.jpg
            threat/
                threat1.jpg
            edge_case/
                costume1.jpg

    Example:
        >>> async with NVIDIAVisionAnalyzer() as analyzer:
        ...     generator = MultimodalGroundTruthGenerator(images_dir, analyzer)
        ...     df = await generator.generate_ground_truth()
        ...     generator.export_ground_truth(Path("output.parquet"))
    """

    def __init__(
        self,
        image_dir: Path,
        analyzer: NVIDIAVisionAnalyzer,
        config: GroundTruthConfig | None = None,
    ) -> None:
        """Initialize the ground truth generator.

        Args:
            image_dir: Directory containing categorized test images.
            analyzer: NVIDIA vision analyzer instance.
            config: Optional configuration for generation behavior.
        """
        self.image_dir = Path(image_dir)
        self.analyzer = analyzer
        self.config = config or GroundTruthConfig()
        self._ground_truth_df: pd.DataFrame | None = None

    def discover_images(self) -> dict[str, list[Path]]:
        """Discover images organized by category in the image directory.

        Returns:
            Dictionary mapping category names to lists of image paths.

        Raises:
            FileNotFoundError: If the image directory doesn't exist.
        """
        if not self.image_dir.exists():
            raise FileNotFoundError(f"Image directory not found: {self.image_dir}")

        images_by_category: dict[str, list[Path]] = {}

        for category in self.config.categories:
            category_dir = self.image_dir / category
            if not category_dir.exists():
                images_by_category[category] = []
                continue

            images = [
                f
                for f in category_dir.iterdir()
                if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
            ]
            images_by_category[category] = sorted(images)

        return images_by_category

    def _result_to_record(
        self,
        image_path: Path,
        category: str,
        result: VisionAnalysisResult,
    ) -> dict[str, Any]:
        """Convert a VisionAnalysisResult to a flat dictionary record.

        Args:
            image_path: Path to the analyzed image.
            category: Category of the image (normal, suspicious, etc.).
            result: Analysis result from NVIDIA vision.

        Returns:
            Flat dictionary suitable for DataFrame row.
        """
        # Extract risk assessment fields
        risk = result.risk_assessment or {}
        risk_score = risk.get("risk_score", 50)
        risk_level = risk.get("risk_level", "medium")
        risk_reasoning = risk.get("reasoning", "")
        concerning_factors = risk.get("concerning_factors", [])
        mitigating_factors = risk.get("mitigating_factors", [])

        # Extract scene attributes
        scene = result.scene_attributes or {}
        lighting = scene.get("lighting", "unknown")
        weather = scene.get("weather", "unknown")
        activity_level = scene.get("activity_level", "unknown")
        location_type = scene.get("location_type", "unknown")

        # Build record
        record: dict[str, Any] = {
            # Image metadata
            "image_path": str(image_path),
            "image_name": image_path.name,
            "category": category,
            # Scene description
            "nvidia_vision_description": result.description,
            # Detected objects (stored as JSON string for parquet compatibility)
            "nvidia_detected_objects": json.dumps(result.detected_objects),
            "nvidia_object_count": len(result.detected_objects),
            # Risk assessment
            "nvidia_risk_score": risk_score,
            "nvidia_risk_level": risk_level,
            "nvidia_risk_reasoning": risk_reasoning,
            "nvidia_concerning_factors": json.dumps(concerning_factors),
            "nvidia_mitigating_factors": json.dumps(mitigating_factors),
            # Scene attributes
            "nvidia_lighting": lighting,
            "nvidia_weather": weather,
            "nvidia_activity_level": activity_level,
            "nvidia_location_type": location_type,
            # Metadata
            "generated_at": datetime.now(UTC).isoformat(),
        }

        # Optionally include raw response for debugging
        if self.config.include_raw_response:
            record["nvidia_raw_response"] = result.raw_response

        return record

    async def generate_ground_truth(self) -> pd.DataFrame:
        """Generate ground truth for all images in the directory.

        Scans the image directory, analyzes each image with NVIDIA vision,
        and returns a DataFrame with structured ground truth data.

        Returns:
            DataFrame with columns:
            - image_path: Absolute path to the image
            - image_name: Filename
            - category: Category from directory name
            - nvidia_vision_description: Scene description
            - nvidia_detected_objects: JSON list of detected objects
            - nvidia_object_count: Number of detected objects
            - nvidia_risk_score: Risk score (0-100)
            - nvidia_risk_level: Risk level (low/medium/high/critical)
            - nvidia_risk_reasoning: Explanation of risk assessment
            - nvidia_concerning_factors: JSON list of concerns
            - nvidia_mitigating_factors: JSON list of mitigating factors
            - nvidia_lighting: Lighting condition
            - nvidia_weather: Weather condition
            - nvidia_activity_level: Activity level
            - nvidia_location_type: Location type
            - generated_at: ISO timestamp of generation

        Raises:
            ImportError: If pandas is not installed.
        """
        try:
            import pandas as pd
        except ImportError as e:
            raise ImportError(
                "pandas is required for ground truth generation. Install with: uv sync --extra nemo"
            ) from e

        # Discover images
        images_by_category = self.discover_images()

        # Flatten to list of (category, path) tuples
        all_images: list[tuple[str, Path]] = []
        for category, paths in images_by_category.items():
            for path in paths:
                all_images.append((category, path))

        if not all_images:
            print(
                f"Warning: No images found in {self.image_dir}. "
                "Ensure images are organized in category subdirectories."
            )
            # Return empty DataFrame with expected schema
            self._ground_truth_df = pd.DataFrame(
                columns=[
                    "image_path",
                    "image_name",
                    "category",
                    "nvidia_vision_description",
                    "nvidia_detected_objects",
                    "nvidia_object_count",
                    "nvidia_risk_score",
                    "nvidia_risk_level",
                    "nvidia_risk_reasoning",
                    "nvidia_concerning_factors",
                    "nvidia_mitigating_factors",
                    "nvidia_lighting",
                    "nvidia_weather",
                    "nvidia_activity_level",
                    "nvidia_location_type",
                    "generated_at",
                ]
            )
            return self._ground_truth_df

        # Analyze images with concurrency control
        semaphore = asyncio.Semaphore(self.config.max_concurrency)

        async def analyze_image(category: str, path: Path) -> dict[str, Any]:
            async with semaphore:
                try:
                    result = await self.analyzer.analyze_image(
                        path,
                        use_cache=self.config.use_cache,
                    )
                    return self._result_to_record(path, category, result)
                except Exception as e:
                    print(f"Error analyzing {path}: {e}")
                    # Return a partial record with error info
                    return {
                        "image_path": str(path),
                        "image_name": path.name,
                        "category": category,
                        "nvidia_vision_description": f"ERROR: {e}",
                        "nvidia_detected_objects": "[]",
                        "nvidia_object_count": 0,
                        "nvidia_risk_score": -1,
                        "nvidia_risk_level": "error",
                        "nvidia_risk_reasoning": str(e),
                        "nvidia_concerning_factors": "[]",
                        "nvidia_mitigating_factors": "[]",
                        "nvidia_lighting": "unknown",
                        "nvidia_weather": "unknown",
                        "nvidia_activity_level": "unknown",
                        "nvidia_location_type": "unknown",
                        "generated_at": datetime.now(UTC).isoformat(),
                    }

        # Run analysis tasks
        tasks = [analyze_image(cat, path) for cat, path in all_images]
        records = await asyncio.gather(*tasks)

        # Create DataFrame
        self._ground_truth_df = pd.DataFrame(records)

        print(
            f"Generated ground truth for {len(self._ground_truth_df)} images "
            f"across {len(images_by_category)} categories"
        )

        return self._ground_truth_df

    def export_ground_truth(
        self,
        output_path: Path,
        format: str = "parquet",
    ) -> None:
        """Export ground truth to file.

        Args:
            output_path: Path for the output file.
            format: Output format ('parquet', 'csv', or 'json').

        Raises:
            ValueError: If no ground truth has been generated.
            ValueError: If format is not supported.
        """
        if self._ground_truth_df is None:
            raise ValueError("No ground truth generated. Call generate_ground_truth() first.")

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "parquet":
            self._ground_truth_df.to_parquet(output_path, index=False)
        elif format == "csv":
            self._ground_truth_df.to_csv(output_path, index=False)
        elif format == "json":
            self._ground_truth_df.to_json(output_path, orient="records", indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}. Use 'parquet', 'csv', or 'json'.")

        print(f"Exported ground truth to {output_path}")

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the generated ground truth.

        Returns:
            Dictionary with summary statistics.

        Raises:
            ValueError: If no ground truth has been generated.
        """
        if self._ground_truth_df is None:
            raise ValueError("No ground truth generated. Call generate_ground_truth() first.")

        df = self._ground_truth_df

        # Count by category
        category_counts = df["category"].value_counts().to_dict()

        # Risk score statistics
        valid_scores = df[df["nvidia_risk_score"] >= 0]["nvidia_risk_score"]
        risk_stats = {
            "mean": float(valid_scores.mean()) if len(valid_scores) > 0 else 0.0,
            "std": float(valid_scores.std()) if len(valid_scores) > 0 else 0.0,
            "min": float(valid_scores.min()) if len(valid_scores) > 0 else 0.0,
            "max": float(valid_scores.max()) if len(valid_scores) > 0 else 0.0,
        }

        # Risk level distribution
        risk_level_counts = df["nvidia_risk_level"].value_counts().to_dict()

        # Object count statistics
        object_stats = {
            "mean": float(df["nvidia_object_count"].mean()),
            "total": int(df["nvidia_object_count"].sum()),
        }

        # Error count
        error_count = int((df["nvidia_risk_score"] < 0).sum())

        return {
            "total_images": len(df),
            "category_counts": category_counts,
            "risk_score_stats": risk_stats,
            "risk_level_distribution": risk_level_counts,
            "object_count_stats": object_stats,
            "error_count": error_count,
        }
