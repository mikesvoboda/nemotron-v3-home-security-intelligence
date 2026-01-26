"""Integration tests for multimodal pipeline evaluation.

This module tests the multimodal evaluation pipeline that compares
local YOLO26 + Nemotron detections against NVIDIA vision ground truth.

Tests are organized into:
- TestDetectionAlignment: Tests for detection IoU and object matching
- TestRiskScoreAlignment: Tests for risk score and level agreement
- TestPipelineComparator: Tests for comparison report generation

These tests use mock mode by default and can be run against real
images when the multimodal pytest marker is used with actual test images.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from tools.nemo_data_designer.multimodal.ground_truth_generator import (
    GroundTruthConfig,
    MultimodalGroundTruthGenerator,
)

# Import multimodal components
from tools.nemo_data_designer.multimodal.image_analyzer import (
    NVIDIAVisionAnalyzer,
    VisionAnalysisResult,
    VisionAnalyzerConfig,
)
from tools.nemo_data_designer.multimodal.pipeline_comparator import (
    ComparisonReport,
    PipelineComparator,
)

if TYPE_CHECKING:
    import pandas as pd


# Path to synthetic test images
SYNTHETIC_IMAGES_DIR = Path(__file__).parent.parent / "fixtures" / "synthetic" / "images"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_vision_analyzer() -> NVIDIAVisionAnalyzer:
    """Create a vision analyzer in mock mode for testing without API calls."""
    config = VisionAnalyzerConfig(mock_mode=True, cache_enabled=False)
    return NVIDIAVisionAnalyzer(config=config)


@pytest.fixture
def pipeline_comparator() -> PipelineComparator:
    """Create a pipeline comparator with default config."""
    return PipelineComparator()


@pytest.fixture
def sample_local_detections() -> list[dict[str, Any]]:
    """Sample detections from local YOLO26 pipeline."""
    return [
        {
            "type": "person",
            "confidence": 0.92,
            "bbox": [30, 20, 15, 40],  # x, y, width, height as percentages
        },
        {
            "type": "car",
            "confidence": 0.88,
            "bbox": [60, 50, 25, 20],
        },
    ]


@pytest.fixture
def sample_nvidia_detections() -> list[dict[str, Any]]:
    """Sample detections from NVIDIA vision ground truth."""
    return [
        {
            "type": "person",
            "confidence": 0.95,
            "bbox": [32, 18, 14, 42],  # Similar but not exact
        },
        {
            "type": "car",
            "confidence": 0.90,
            "bbox": [58, 48, 27, 22],  # Similar but not exact
        },
    ]


@pytest.fixture
def multimodal_fixtures(mock_vision_analyzer: NVIDIAVisionAnalyzer) -> dict[str, Any]:
    """Comprehensive fixture set for multimodal testing.

    Returns a dictionary with:
    - analyzer: Mock vision analyzer
    - comparator: Pipeline comparator
    - sample_detections: Local and NVIDIA detection pairs
    - sample_risk_scores: Local and NVIDIA risk score pairs
    """
    return {
        "analyzer": mock_vision_analyzer,
        "comparator": PipelineComparator(),
        "sample_detections": {
            "local": [
                {"type": "person", "confidence": 0.92, "bbox": [30, 20, 15, 40]},
            ],
            "nvidia": [
                {"type": "person", "confidence": 0.95, "bbox": [32, 18, 14, 42]},
            ],
        },
        "sample_risk_scores": {
            "local": 65,
            "nvidia": 70,
        },
    }


# =============================================================================
# Detection Alignment Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.multimodal
class TestDetectionAlignment:
    """Test local detection alignment with NVIDIA vision."""

    def test_detection_iou_above_threshold(
        self,
        pipeline_comparator: PipelineComparator,
        sample_local_detections: list[dict[str, Any]],
        sample_nvidia_detections: list[dict[str, Any]],
    ) -> None:
        """Local YOLO26 should achieve >= 70% IoU with NVIDIA."""
        iou = pipeline_comparator.calculate_detection_iou(
            sample_local_detections,
            sample_nvidia_detections,
        )

        # IoU should be above 70% for similar detections
        assert iou >= 0.70, f"Detection IoU {iou:.2%} below 70% threshold"

    def test_detects_same_object_types(
        self,
        pipeline_comparator: PipelineComparator,
        sample_local_detections: list[dict[str, Any]],
        sample_nvidia_detections: list[dict[str, Any]],
    ) -> None:
        """Should detect same object categories as NVIDIA."""
        metrics = pipeline_comparator.calculate_detection_metrics(
            sample_local_detections,
            sample_nvidia_detections,
        )

        # Should have matched all detections
        assert metrics["matched_count"] == len(sample_nvidia_detections)
        assert metrics["recall"] == 1.0, "All NVIDIA detections should be matched"

    def test_empty_detections_handling(
        self,
        pipeline_comparator: PipelineComparator,
    ) -> None:
        """Should handle empty detection lists gracefully."""
        # No detections in either -> perfect match
        iou = pipeline_comparator.calculate_detection_iou([], [])
        assert iou == 1.0

        # Local has detections, NVIDIA doesn't -> IoU 0
        iou = pipeline_comparator.calculate_detection_iou(
            [{"type": "person", "bbox": [0, 0, 10, 10]}],
            [],
        )
        assert iou == 0.0

        # NVIDIA has detections, local doesn't -> IoU 0
        iou = pipeline_comparator.calculate_detection_iou(
            [],
            [{"type": "person", "bbox": [0, 0, 10, 10]}],
        )
        assert iou == 0.0

    def test_mismatched_object_types(
        self,
        pipeline_comparator: PipelineComparator,
    ) -> None:
        """Different object types should not match even with overlapping boxes."""
        local = [{"type": "person", "bbox": [10, 10, 20, 20]}]
        nvidia = [{"type": "car", "bbox": [10, 10, 20, 20]}]

        iou = pipeline_comparator.calculate_detection_iou(local, nvidia)
        # Different types shouldn't match
        assert iou == 0.0

    def test_object_type_normalization(
        self,
        pipeline_comparator: PipelineComparator,
    ) -> None:
        """Object types should be normalized for comparison."""
        # 'human' and 'person' should be treated as the same
        local = [{"type": "person", "bbox": [10, 10, 20, 20]}]
        nvidia = [{"type": "human", "bbox": [10, 10, 20, 20]}]

        iou = pipeline_comparator.calculate_detection_iou(local, nvidia)
        assert iou == 1.0, "Normalized types should match"

    def test_detection_metrics_precision_recall(
        self,
        pipeline_comparator: PipelineComparator,
    ) -> None:
        """Precision and recall should be correctly calculated."""
        # Local has 3 detections, NVIDIA has 2, 2 match
        local = [
            {"type": "person", "bbox": [10, 10, 20, 20]},
            {"type": "car", "bbox": [50, 50, 20, 20]},
            {"type": "dog", "bbox": [80, 80, 10, 10]},  # Extra local detection
        ]
        nvidia = [
            {"type": "person", "bbox": [12, 12, 18, 18]},
            {"type": "car", "bbox": [52, 52, 18, 18]},
        ]

        metrics = pipeline_comparator.calculate_detection_metrics(local, nvidia)

        # Precision: 2 matches / 3 local = 0.67
        assert abs(metrics["precision"] - 2 / 3) < 0.01
        # Recall: 2 matches / 2 nvidia = 1.0
        assert metrics["recall"] == 1.0


# =============================================================================
# Risk Score Alignment Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.multimodal
class TestRiskScoreAlignment:
    """Test end-to-end risk score alignment."""

    def test_risk_score_within_threshold(
        self,
        pipeline_comparator: PipelineComparator,
    ) -> None:
        """Risk scores should be within 15 points of NVIDIA assessment."""
        alignment = pipeline_comparator.calculate_risk_alignment(
            local_risk=65,
            nvidia_risk=70,
        )

        assert alignment["aligned"], f"Deviation {alignment['deviation']} exceeds threshold"
        assert alignment["deviation"] <= 15

    def test_risk_score_exact_match(
        self,
        pipeline_comparator: PipelineComparator,
    ) -> None:
        """Exact risk score matches should have zero deviation."""
        alignment = pipeline_comparator.calculate_risk_alignment(
            local_risk=50,
            nvidia_risk=50,
        )

        assert alignment["deviation"] == 0
        assert alignment["direction"] == "exact"
        assert alignment["aligned"]

    def test_risk_score_over_estimation(
        self,
        pipeline_comparator: PipelineComparator,
    ) -> None:
        """Over-estimation should be correctly identified."""
        alignment = pipeline_comparator.calculate_risk_alignment(
            local_risk=80,
            nvidia_risk=60,
        )

        assert alignment["direction"] == "over"
        assert alignment["deviation"] == 20
        assert not alignment["aligned"]

    def test_risk_score_under_estimation(
        self,
        pipeline_comparator: PipelineComparator,
    ) -> None:
        """Under-estimation should be correctly identified."""
        alignment = pipeline_comparator.calculate_risk_alignment(
            local_risk=40,
            nvidia_risk=70,
        )

        assert alignment["direction"] == "under"
        assert alignment["deviation"] == 30
        assert not alignment["aligned"]

    def test_risk_level_agreement(
        self,
        pipeline_comparator: PipelineComparator,
    ) -> None:
        """Risk levels (low/medium/high/critical) should agree."""
        # Both should be 'low'
        agreement = pipeline_comparator.calculate_risk_level_agreement(
            local_risk=15,
            nvidia_risk=20,
        )
        assert agreement["agreement"]
        assert agreement["local_level"] == "low"
        assert agreement["nvidia_level"] == "low"

        # Both should be 'high'
        agreement = pipeline_comparator.calculate_risk_level_agreement(
            local_risk=75,
            nvidia_risk=80,
        )
        assert agreement["agreement"]
        assert agreement["local_level"] == "high"

    def test_risk_level_disagreement(
        self,
        pipeline_comparator: PipelineComparator,
    ) -> None:
        """Different risk levels should be correctly identified."""
        # local=low, nvidia=medium
        agreement = pipeline_comparator.calculate_risk_level_agreement(
            local_risk=20,
            nvidia_risk=40,
        )
        assert not agreement["agreement"]
        assert agreement["local_level"] == "low"
        assert agreement["nvidia_level"] == "medium"

    def test_risk_level_boundaries(
        self,
        pipeline_comparator: PipelineComparator,
    ) -> None:
        """Risk level boundaries should be correctly applied."""
        # Score 25 should be 'low', 26 should be 'medium'
        agreement_25 = pipeline_comparator.calculate_risk_level_agreement(25, 25)
        assert agreement_25["local_level"] == "low"

        agreement_26 = pipeline_comparator.calculate_risk_level_agreement(26, 26)
        assert agreement_26["local_level"] == "medium"

        # Score 55 should be 'medium', 56 should be 'high'
        agreement_55 = pipeline_comparator.calculate_risk_level_agreement(55, 55)
        assert agreement_55["local_level"] == "medium"

        agreement_56 = pipeline_comparator.calculate_risk_level_agreement(56, 56)
        assert agreement_56["local_level"] == "high"


# =============================================================================
# Vision Analyzer Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.multimodal
class TestVisionAnalyzer:
    """Tests for the NVIDIA Vision Analyzer."""

    @pytest.mark.asyncio
    async def test_mock_mode_generates_valid_result(
        self,
        mock_vision_analyzer: NVIDIAVisionAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Mock mode should generate valid VisionAnalysisResult."""
        # Create a test image file
        test_image = tmp_path / "normal" / "test.jpg"
        test_image.parent.mkdir(parents=True, exist_ok=True)
        test_image.write_bytes(b"fake image data")

        result = await mock_vision_analyzer.analyze_image(test_image)

        assert isinstance(result, VisionAnalysisResult)
        assert result.description
        assert isinstance(result.detected_objects, list)
        assert isinstance(result.risk_assessment, dict)
        assert "risk_score" in result.risk_assessment
        assert "risk_level" in result.risk_assessment

    @pytest.mark.asyncio
    async def test_mock_mode_uses_path_category(
        self,
        mock_vision_analyzer: NVIDIAVisionAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Mock mode should use path to determine category."""
        # Create test images in different categories
        normal_image = tmp_path / "normal" / "test.jpg"
        threat_image = tmp_path / "threat" / "test.jpg"
        normal_image.parent.mkdir(parents=True, exist_ok=True)
        threat_image.parent.mkdir(parents=True, exist_ok=True)
        normal_image.write_bytes(b"fake normal image")
        threat_image.write_bytes(b"fake threat image")

        normal_result = await mock_vision_analyzer.analyze_image(normal_image)
        threat_result = await mock_vision_analyzer.analyze_image(threat_image)

        # Normal should have low risk, threat should have high risk
        assert normal_result.risk_assessment["risk_score"] < 30
        assert threat_result.risk_assessment["risk_score"] >= 70

    @pytest.mark.asyncio
    async def test_invalid_image_format_raises(
        self,
        mock_vision_analyzer: NVIDIAVisionAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Invalid image format should raise ValueError."""
        invalid_file = tmp_path / "test.txt"
        invalid_file.write_text("not an image")

        with pytest.raises(ValueError, match="Unsupported image format"):
            await mock_vision_analyzer.analyze_image(invalid_file)

    @pytest.mark.asyncio
    async def test_missing_image_raises(
        self,
        mock_vision_analyzer: NVIDIAVisionAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Missing image should raise FileNotFoundError."""
        missing_image = tmp_path / "nonexistent.jpg"

        with pytest.raises(FileNotFoundError):
            await mock_vision_analyzer.analyze_image(missing_image)

    @pytest.mark.asyncio
    async def test_batch_analysis(
        self,
        mock_vision_analyzer: NVIDIAVisionAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Batch analysis should process multiple images."""
        # Create multiple test images
        images = []
        for i in range(3):
            img_path = tmp_path / f"image_{i}.jpg"
            img_path.write_bytes(f"image {i} data".encode())
            images.append(img_path)

        results = await mock_vision_analyzer.analyze_batch(images)

        assert len(results) == 3
        for result in results:
            assert isinstance(result, VisionAnalysisResult)


# =============================================================================
# Ground Truth Generator Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.multimodal
class TestGroundTruthGenerator:
    """Tests for the multimodal ground truth generator."""

    @pytest.mark.asyncio
    async def test_discover_images_by_category(
        self,
        mock_vision_analyzer: NVIDIAVisionAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Should discover images organized by category."""
        # Create directory structure
        for category in ["normal", "suspicious", "threat", "edge_case"]:
            cat_dir = tmp_path / category
            cat_dir.mkdir()
            # Create 2 images per category
            (cat_dir / f"{category}_1.jpg").write_bytes(b"image1")
            (cat_dir / f"{category}_2.jpg").write_bytes(b"image2")

        generator = MultimodalGroundTruthGenerator(tmp_path, mock_vision_analyzer)
        images = generator.discover_images()

        assert len(images) == 4
        for category in ["normal", "suspicious", "threat", "edge_case"]:
            assert category in images
            assert len(images[category]) == 2

    @pytest.mark.asyncio
    async def test_generate_ground_truth_creates_dataframe(
        self,
        mock_vision_analyzer: NVIDIAVisionAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Ground truth generation should produce a valid DataFrame."""
        # Create test images
        normal_dir = tmp_path / "normal"
        normal_dir.mkdir()
        (normal_dir / "test.jpg").write_bytes(b"test image")

        generator = MultimodalGroundTruthGenerator(
            tmp_path,
            mock_vision_analyzer,
            config=GroundTruthConfig(use_cache=False),
        )
        df = await generator.generate_ground_truth()

        assert len(df) == 1
        assert "image_path" in df.columns
        assert "category" in df.columns
        assert "nvidia_risk_score" in df.columns
        assert df.iloc[0]["category"] == "normal"

    @pytest.mark.asyncio
    async def test_export_ground_truth_parquet(
        self,
        mock_vision_analyzer: NVIDIAVisionAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Should export ground truth to parquet format."""
        # Create test images
        normal_dir = tmp_path / "images" / "normal"
        normal_dir.mkdir(parents=True)
        (normal_dir / "test.jpg").write_bytes(b"test image")

        generator = MultimodalGroundTruthGenerator(
            tmp_path / "images",
            mock_vision_analyzer,
            config=GroundTruthConfig(use_cache=False),
        )
        await generator.generate_ground_truth()

        output_path = tmp_path / "output.parquet"
        generator.export_ground_truth(output_path)

        assert output_path.exists()

    @pytest.mark.asyncio
    async def test_summary_statistics(
        self,
        mock_vision_analyzer: NVIDIAVisionAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Summary should provide correct statistics."""
        # Create images in different categories
        for category in ["normal", "threat"]:
            cat_dir = tmp_path / category
            cat_dir.mkdir()
            (cat_dir / "test.jpg").write_bytes(b"test")

        generator = MultimodalGroundTruthGenerator(
            tmp_path,
            mock_vision_analyzer,
            config=GroundTruthConfig(use_cache=False),
        )
        await generator.generate_ground_truth()
        summary = generator.get_summary()

        assert summary["total_images"] == 2
        assert "normal" in summary["category_counts"]
        assert "threat" in summary["category_counts"]


# =============================================================================
# Comparison Report Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.multimodal
class TestComparisonReport:
    """Tests for comparison report generation."""

    @pytest.fixture
    def sample_dataframes(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Create sample DataFrames for testing."""
        import json

        import pandas as pd

        local_results = pd.DataFrame(
            [
                {
                    "image_path": "/test/image1.jpg",
                    "detections": json.dumps([{"type": "person", "bbox": [30, 20, 15, 40]}]),
                    "risk_score": 65,
                },
                {
                    "image_path": "/test/image2.jpg",
                    "detections": json.dumps([{"type": "car", "bbox": [50, 50, 20, 20]}]),
                    "risk_score": 25,
                },
            ]
        )

        nvidia_ground_truth = pd.DataFrame(
            [
                {
                    "image_path": "/test/image1.jpg",
                    "nvidia_detected_objects": json.dumps(
                        [{"type": "person", "bbox": [32, 18, 14, 42]}]
                    ),
                    "nvidia_risk_score": 70,
                    "category": "suspicious",
                },
                {
                    "image_path": "/test/image2.jpg",
                    "nvidia_detected_objects": json.dumps(
                        [{"type": "car", "bbox": [52, 52, 18, 18]}]
                    ),
                    "nvidia_risk_score": 20,
                    "category": "normal",
                },
            ]
        )

        return local_results, nvidia_ground_truth

    def test_generate_comparison_report(
        self,
        pipeline_comparator: PipelineComparator,
        sample_dataframes: tuple[pd.DataFrame, pd.DataFrame],
    ) -> None:
        """Should generate a valid comparison report."""
        local_results, nvidia_ground_truth = sample_dataframes

        report = pipeline_comparator.generate_comparison_report(
            local_results,
            nvidia_ground_truth,
        )

        assert isinstance(report, ComparisonReport)
        assert report.total_images == 2
        assert "average_iou" in report.detection_metrics
        assert "alignment_rate" in report.risk_metrics

    def test_per_category_metrics(
        self,
        pipeline_comparator: PipelineComparator,
        sample_dataframes: tuple[pd.DataFrame, pd.DataFrame],
    ) -> None:
        """Should calculate per-category metrics."""
        local_results, nvidia_ground_truth = sample_dataframes

        report = pipeline_comparator.generate_comparison_report(
            local_results,
            nvidia_ground_truth,
        )

        assert "suspicious" in report.per_category_metrics
        assert "normal" in report.per_category_metrics
        assert report.per_category_metrics["suspicious"]["count"] == 1
        assert report.per_category_metrics["normal"]["count"] == 1

    def test_failure_case_tracking(
        self,
        pipeline_comparator: PipelineComparator,
    ) -> None:
        """Should track failure cases where alignment fails."""
        import json

        import pandas as pd

        # Create a case with high risk deviation
        local_results = pd.DataFrame(
            [
                {
                    "image_path": "/test/failure.jpg",
                    "detections": json.dumps([]),
                    "risk_score": 90,  # Very different from NVIDIA
                },
            ]
        )

        nvidia_ground_truth = pd.DataFrame(
            [
                {
                    "image_path": "/test/failure.jpg",
                    "nvidia_detected_objects": json.dumps(
                        [{"type": "person", "bbox": [30, 30, 10, 10]}]
                    ),
                    "nvidia_risk_score": 20,  # Low risk in NVIDIA
                    "category": "normal",
                },
            ]
        )

        report = pipeline_comparator.generate_comparison_report(
            local_results,
            nvidia_ground_truth,
        )

        assert len(report.failure_cases) > 0
        failure = report.failure_cases[0]
        assert failure["risk_deviation"] == 70

    def test_generate_summary_text(
        self,
        pipeline_comparator: PipelineComparator,
        sample_dataframes: tuple[pd.DataFrame, pd.DataFrame],
    ) -> None:
        """Should generate readable summary text."""
        local_results, nvidia_ground_truth = sample_dataframes

        report = pipeline_comparator.generate_comparison_report(
            local_results,
            nvidia_ground_truth,
        )

        summary = pipeline_comparator.generate_summary(report)

        assert "Pipeline Comparison Summary" in summary
        assert "Total Images Compared: 2" in summary
        assert "Detection Metrics:" in summary
        assert "Risk Score Metrics:" in summary

    def test_report_to_dict_serializable(
        self,
        pipeline_comparator: PipelineComparator,
        sample_dataframes: tuple[pd.DataFrame, pd.DataFrame],
    ) -> None:
        """Report should be serializable to dictionary."""
        import json

        local_results, nvidia_ground_truth = sample_dataframes

        report = pipeline_comparator.generate_comparison_report(
            local_results,
            nvidia_ground_truth,
        )

        report_dict = report.to_dict()

        # Should be JSON serializable
        json_str = json.dumps(report_dict)
        assert json_str
        parsed = json.loads(json_str)
        assert parsed["total_images"] == 2
