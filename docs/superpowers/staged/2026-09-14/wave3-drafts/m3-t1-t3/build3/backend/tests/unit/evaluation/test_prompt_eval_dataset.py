"""Unit tests for backend.evaluation.prompt_eval_dataset module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from backend.evaluation.prompt_eval_dataset import (
    PromptEvalSample,
    filter_samples_with_media,
    get_samples_by_category,
    get_samples_by_risk_level,
    get_scenario_summary,
    load_synthetic_eval_dataset,
)

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def sample_expected_labels() -> dict:
    """Sample expected_labels.json content."""
    return {
        "detections": [{"class": "person", "min_confidence": 0.8, "count": 1}],
        "face": {"detected": True, "count": 1, "visible": True},
        "risk": {
            "min_score": 0,
            "max_score": 25,
            "level": "low",
            "expected_factors": [],
        },
        "florence_caption": {
            "must_contain": ["person", "package"],
            "must_not_contain": ["suspicious"],
        },
    }


@pytest.fixture
def sample_scenario_spec() -> dict:
    """Sample scenario_spec.json content."""
    return {
        "id": "delivery_driver",
        "category": "normal",
        "name": "Package Delivery",
        "description": "A delivery driver bringing a package to the front door.",
        "scene": {"location": "front_porch", "camera_type": "doorbell"},
        "environment": {"time_of_day": "day", "weather": "clear"},
        "subjects": [{"type": "person", "role": "delivery_driver"}],
        "generation": {"format": "image", "count": 1},
    }


@pytest.fixture
def sample_metadata() -> dict:
    """Sample metadata.json content."""
    return {
        "generated_at": "2026-01-25T18:00:00Z",
        "generator": "nemo-data-designer",
        "version": "1.0.0",
    }


@pytest.fixture
def temp_synthetic_data_dir(
    sample_expected_labels: dict,
    sample_scenario_spec: dict,
    sample_metadata: dict,
) -> Generator[Path]:
    """Create a temporary synthetic data directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)

        # Create normal category with scenarios
        normal_dir = base_dir / "normal"
        normal_dir.mkdir()

        # Scenario 1: delivery_driver with media
        scenario1_dir = normal_dir / "delivery_driver_20260125_180349"
        scenario1_dir.mkdir()
        (scenario1_dir / "expected_labels.json").write_text(json.dumps(sample_expected_labels))
        (scenario1_dir / "scenario_spec.json").write_text(json.dumps(sample_scenario_spec))
        (scenario1_dir / "metadata.json").write_text(json.dumps(sample_metadata))

        # Create media directory with image
        media_dir = scenario1_dir / "media"
        media_dir.mkdir()
        (media_dir / "001.png").write_bytes(b"fake png data")

        # Scenario 2: pet_activity without media
        scenario2_dir = normal_dir / "pet_activity_20260125_180256"
        scenario2_dir.mkdir()
        pet_labels = {
            "risk": {
                "min_score": 0,
                "max_score": 10,
                "level": "low",
                "expected_factors": [],
            }
        }
        (scenario2_dir / "expected_labels.json").write_text(json.dumps(pet_labels))

        # Create suspicious category
        suspicious_dir = base_dir / "suspicious"
        suspicious_dir.mkdir()

        scenario3_dir = suspicious_dir / "casing_20260125_181140"
        scenario3_dir.mkdir()
        suspicious_labels = {
            "risk": {
                "min_score": 35,
                "max_score": 60,
                "level": "medium",
                "expected_factors": ["prolonged_observation", "unknown_person"],
            }
        }
        (scenario3_dir / "expected_labels.json").write_text(json.dumps(suspicious_labels))

        # Create media with video
        media_dir3 = scenario3_dir / "media"
        media_dir3.mkdir()
        (media_dir3 / "001.mp4").write_bytes(b"fake video data")

        # Create threats category
        threats_dir = base_dir / "threats"
        threats_dir.mkdir()

        scenario4_dir = threats_dir / "break_in_attempt_20260125_182000"
        scenario4_dir.mkdir()
        threat_labels = {
            "risk": {
                "min_score": 80,
                "max_score": 100,
                "level": "critical",
                "expected_factors": ["forced_entry", "unknown_person"],
            }
        }
        (scenario4_dir / "expected_labels.json").write_text(json.dumps(threat_labels))

        yield base_dir


class TestPromptEvalSample:
    """Tests for PromptEvalSample dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a basic sample."""
        sample = PromptEvalSample(
            scenario_id="test_001",
            category="normal",
            media_path=None,
            expected_risk_range=(0, 25),
            expected_risk_level="low",
            expected_factors=[],
        )

        assert sample.scenario_id == "test_001"
        assert sample.category == "normal"
        assert sample.media_path is None
        assert sample.expected_risk_range == (0, 25)
        assert sample.expected_risk_level == "low"
        assert sample.expected_factors == []

    def test_has_media_without_path(self) -> None:
        """Test has_media property when no media path."""
        sample = PromptEvalSample(
            scenario_id="test_001",
            category="normal",
            media_path=None,
            expected_risk_range=(0, 25),
            expected_risk_level="low",
            expected_factors=[],
        )

        assert sample.has_media is False

    def test_has_media_with_nonexistent_path(self, tmp_path: Path) -> None:
        """Test has_media property when path doesn't exist."""
        sample = PromptEvalSample(
            scenario_id="test_001",
            category="normal",
            media_path=tmp_path / "nonexistent.png",
            expected_risk_range=(0, 25),
            expected_risk_level="low",
            expected_factors=[],
        )

        assert sample.has_media is False

    def test_has_media_with_valid_path(self, tmp_path: Path) -> None:
        """Test has_media property when path exists."""
        media_file = tmp_path / "test.png"
        media_file.write_bytes(b"fake image")

        sample = PromptEvalSample(
            scenario_id="test_001",
            category="normal",
            media_path=media_file,
            expected_risk_range=(0, 25),
            expected_risk_level="low",
            expected_factors=[],
        )

        assert sample.has_media is True

    def test_media_type_image(self, tmp_path: Path) -> None:
        """Test media_type property for images."""
        for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
            media_file = tmp_path / f"test{ext}"
            media_file.write_bytes(b"fake image")

            sample = PromptEvalSample(
                scenario_id="test_001",
                category="normal",
                media_path=media_file,
                expected_risk_range=(0, 25),
                expected_risk_level="low",
                expected_factors=[],
            )

            assert sample.media_type == "image", f"Failed for extension {ext}"

    def test_media_type_video(self, tmp_path: Path) -> None:
        """Test media_type property for videos."""
        for ext in [".mp4", ".avi", ".mov", ".mkv", ".webm"]:
            media_file = tmp_path / f"test{ext}"
            media_file.write_bytes(b"fake video")

            sample = PromptEvalSample(
                scenario_id="test_001",
                category="normal",
                media_path=media_file,
                expected_risk_range=(0, 25),
                expected_risk_level="low",
                expected_factors=[],
            )

            assert sample.media_type == "video", f"Failed for extension {ext}"

    def test_media_type_unknown(self, tmp_path: Path) -> None:
        """Test media_type property for unknown types."""
        media_file = tmp_path / "test.txt"
        media_file.write_text("not media")

        sample = PromptEvalSample(
            scenario_id="test_001",
            category="normal",
            media_path=media_file,
            expected_risk_range=(0, 25),
            expected_risk_level="low",
            expected_factors=[],
        )

        assert sample.media_type == "unknown"

    def test_media_type_none(self) -> None:
        """Test media_type property when no media."""
        sample = PromptEvalSample(
            scenario_id="test_001",
            category="normal",
            media_path=None,
            expected_risk_range=(0, 25),
            expected_risk_level="low",
            expected_factors=[],
        )

        assert sample.media_type is None

    def test_get_scenario_name_from_spec(self) -> None:
        """Test getting scenario name from spec."""
        sample = PromptEvalSample(
            scenario_id="test_001",
            category="normal",
            media_path=None,
            expected_risk_range=(0, 25),
            expected_risk_level="low",
            expected_factors=[],
            scenario_spec={"name": "Test Scenario Name"},
        )

        assert sample.get_scenario_name() == "Test Scenario Name"

    def test_get_scenario_name_fallback(self) -> None:
        """Test fallback to scenario_id when name not in spec."""
        sample = PromptEvalSample(
            scenario_id="test_001",
            category="normal",
            media_path=None,
            expected_risk_range=(0, 25),
            expected_risk_level="low",
            expected_factors=[],
        )

        assert sample.get_scenario_name() == "test_001"

    def test_get_scenario_description(self) -> None:
        """Test getting scenario description."""
        sample = PromptEvalSample(
            scenario_id="test_001",
            category="normal",
            media_path=None,
            expected_risk_range=(0, 25),
            expected_risk_level="low",
            expected_factors=[],
            scenario_spec={"description": "A test scenario description"},
        )

        assert sample.get_scenario_description() == "A test scenario description"

    def test_default_factory_fields(self) -> None:
        """Test that factory fields default to empty collections."""
        sample = PromptEvalSample(
            scenario_id="test_001",
            category="normal",
            media_path=None,
            expected_risk_range=(0, 25),
            expected_risk_level="low",
            expected_factors=[],
        )

        assert sample.scenario_spec == {}
        assert sample.metadata == {}
        assert sample.expected_labels == {}


class TestLoadSyntheticEvalDataset:
    """Tests for load_synthetic_eval_dataset function."""

    def test_loads_real_data(self) -> None:
        """Test loading actual synthetic data from data/synthetic/."""
        # This test uses the real data directory
        samples = load_synthetic_eval_dataset()

        # Should load at least some samples if data exists
        # If no data exists, should return empty list gracefully
        assert isinstance(samples, list)

        if samples:
            # Verify sample structure
            sample = samples[0]
            assert isinstance(sample, PromptEvalSample)
            assert isinstance(sample.scenario_id, str)
            assert isinstance(sample.category, str)
            assert isinstance(sample.expected_risk_range, tuple)
            assert len(sample.expected_risk_range) == 2
            assert isinstance(sample.expected_risk_level, str)
            assert isinstance(sample.expected_factors, list)

    def test_loads_from_temp_directory(self, temp_synthetic_data_dir: Path) -> None:
        """Test loading from a temporary test directory."""
        samples = load_synthetic_eval_dataset(data_dir=temp_synthetic_data_dir)

        assert len(samples) == 4

        # Verify categories
        categories = {s.category for s in samples}
        assert categories == {"normal", "suspicious", "threats"}

    def test_filters_by_category(self, temp_synthetic_data_dir: Path) -> None:
        """Test filtering by specific categories."""
        samples = load_synthetic_eval_dataset(
            data_dir=temp_synthetic_data_dir,
            categories=["normal"],
        )

        assert len(samples) == 2
        assert all(s.category == "normal" for s in samples)

    def test_filters_by_multiple_categories(self, temp_synthetic_data_dir: Path) -> None:
        """Test filtering by multiple categories."""
        samples = load_synthetic_eval_dataset(
            data_dir=temp_synthetic_data_dir,
            categories=["normal", "suspicious"],
        )

        assert len(samples) == 3
        categories = {s.category for s in samples}
        assert categories == {"normal", "suspicious"}

    def test_handles_nonexistent_directory(self) -> None:
        """Test graceful handling of nonexistent directory."""
        samples = load_synthetic_eval_dataset(data_dir=Path("/nonexistent/path/to/data"))

        assert samples == []

    def test_handles_empty_directory(self, tmp_path: Path) -> None:
        """Test handling of empty directory."""
        samples = load_synthetic_eval_dataset(data_dir=tmp_path)

        assert samples == []

    def test_skips_directories_without_labels(self, tmp_path: Path) -> None:
        """Test that directories without expected_labels.json are skipped."""
        category_dir = tmp_path / "normal"
        category_dir.mkdir()

        scenario_dir = category_dir / "incomplete_scenario"
        scenario_dir.mkdir()

        # Only create scenario_spec, not expected_labels
        (scenario_dir / "scenario_spec.json").write_text('{"name": "test"}')

        samples = load_synthetic_eval_dataset(data_dir=tmp_path)

        assert samples == []

    def test_handles_invalid_json(self, tmp_path: Path) -> None:
        """Test handling of invalid JSON files."""
        category_dir = tmp_path / "normal"
        category_dir.mkdir()

        scenario_dir = category_dir / "bad_json_scenario"
        scenario_dir.mkdir()

        # Write invalid JSON
        (scenario_dir / "expected_labels.json").write_text("not valid json {")

        samples = load_synthetic_eval_dataset(data_dir=tmp_path)

        assert samples == []

    def test_loads_scenario_spec(self, temp_synthetic_data_dir: Path) -> None:
        """Test that scenario_spec is loaded correctly."""
        samples = load_synthetic_eval_dataset(
            data_dir=temp_synthetic_data_dir,
            categories=["normal"],
        )

        # Find the sample with scenario_spec
        sample_with_spec = next(
            (s for s in samples if s.scenario_spec),
            None,
        )

        assert sample_with_spec is not None
        assert "name" in sample_with_spec.scenario_spec
        assert sample_with_spec.scenario_spec["name"] == "Package Delivery"

    def test_loads_metadata(self, temp_synthetic_data_dir: Path) -> None:
        """Test that metadata is loaded correctly."""
        samples = load_synthetic_eval_dataset(
            data_dir=temp_synthetic_data_dir,
            categories=["normal"],
        )

        # Find the sample with metadata
        sample_with_metadata = next(
            (s for s in samples if s.metadata),
            None,
        )

        assert sample_with_metadata is not None
        assert "generator" in sample_with_metadata.metadata

    def test_finds_media_files(self, temp_synthetic_data_dir: Path) -> None:
        """Test that media files are found correctly."""
        samples = load_synthetic_eval_dataset(data_dir=temp_synthetic_data_dir)

        # Count samples with media
        samples_with_media = [s for s in samples if s.media_path is not None]

        # We created media for 2 scenarios (delivery_driver and casing)
        assert len(samples_with_media) == 2

    def test_extracts_risk_information(self, temp_synthetic_data_dir: Path) -> None:
        """Test that risk information is extracted correctly."""
        samples = load_synthetic_eval_dataset(data_dir=temp_synthetic_data_dir)

        # Find the threat scenario
        threat_sample = next(s for s in samples if s.category == "threats")

        assert threat_sample.expected_risk_range == (80, 100)
        assert threat_sample.expected_risk_level == "critical"
        assert "forced_entry" in threat_sample.expected_factors

    def test_extracts_expected_factors(self, temp_synthetic_data_dir: Path) -> None:
        """Test that expected factors are extracted correctly."""
        samples = load_synthetic_eval_dataset(data_dir=temp_synthetic_data_dir)

        # Find the suspicious scenario
        suspicious_sample = next(s for s in samples if s.category == "suspicious")

        assert isinstance(suspicious_sample.expected_factors, list)
        assert "prolonged_observation" in suspicious_sample.expected_factors
        assert "unknown_person" in suspicious_sample.expected_factors


class TestGetSamplesByCategory:
    """Tests for get_samples_by_category function."""

    def test_groups_correctly(self) -> None:
        """Test that samples are grouped by category."""
        samples = [
            PromptEvalSample(
                scenario_id="normal_1",
                category="normal",
                media_path=None,
                expected_risk_range=(0, 25),
                expected_risk_level="low",
                expected_factors=[],
            ),
            PromptEvalSample(
                scenario_id="normal_2",
                category="normal",
                media_path=None,
                expected_risk_range=(0, 25),
                expected_risk_level="low",
                expected_factors=[],
            ),
            PromptEvalSample(
                scenario_id="suspicious_1",
                category="suspicious",
                media_path=None,
                expected_risk_range=(35, 60),
                expected_risk_level="medium",
                expected_factors=[],
            ),
        ]

        grouped = get_samples_by_category(samples)

        assert len(grouped) == 2
        assert len(grouped["normal"]) == 2
        assert len(grouped["suspicious"]) == 1
        assert grouped["normal"][0].scenario_id == "normal_1"

    def test_empty_list(self) -> None:
        """Test handling of empty sample list."""
        grouped = get_samples_by_category([])

        assert grouped == {}

    def test_single_category(self) -> None:
        """Test with samples from single category."""
        samples = [
            PromptEvalSample(
                scenario_id="normal_1",
                category="normal",
                media_path=None,
                expected_risk_range=(0, 25),
                expected_risk_level="low",
                expected_factors=[],
            ),
        ]

        grouped = get_samples_by_category(samples)

        assert len(grouped) == 1
        assert "normal" in grouped


class TestGetSamplesByRiskLevel:
    """Tests for get_samples_by_risk_level function."""

    def test_groups_by_risk_level(self) -> None:
        """Test that samples are grouped by risk level."""
        samples = [
            PromptEvalSample(
                scenario_id="test_1",
                category="normal",
                media_path=None,
                expected_risk_range=(0, 25),
                expected_risk_level="low",
                expected_factors=[],
            ),
            PromptEvalSample(
                scenario_id="test_2",
                category="suspicious",
                media_path=None,
                expected_risk_range=(35, 60),
                expected_risk_level="medium",
                expected_factors=[],
            ),
            PromptEvalSample(
                scenario_id="test_3",
                category="normal",
                media_path=None,
                expected_risk_range=(0, 20),
                expected_risk_level="low",
                expected_factors=[],
            ),
        ]

        grouped = get_samples_by_risk_level(samples)

        assert len(grouped) == 2
        assert len(grouped["low"]) == 2
        assert len(grouped["medium"]) == 1


class TestFilterSamplesWithMedia:
    """Tests for filter_samples_with_media function."""

    def test_filters_samples_with_media(self, tmp_path: Path) -> None:
        """Test filtering to only samples with media."""
        media_file = tmp_path / "test.png"
        media_file.write_bytes(b"fake image")

        samples = [
            PromptEvalSample(
                scenario_id="with_media",
                category="normal",
                media_path=media_file,
                expected_risk_range=(0, 25),
                expected_risk_level="low",
                expected_factors=[],
            ),
            PromptEvalSample(
                scenario_id="without_media",
                category="normal",
                media_path=None,
                expected_risk_range=(0, 25),
                expected_risk_level="low",
                expected_factors=[],
            ),
        ]

        filtered = filter_samples_with_media(samples)

        assert len(filtered) == 1
        assert filtered[0].scenario_id == "with_media"

    def test_filters_by_media_type(self, tmp_path: Path) -> None:
        """Test filtering by specific media type."""
        image_file = tmp_path / "test.png"
        image_file.write_bytes(b"fake image")

        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake video")

        samples = [
            PromptEvalSample(
                scenario_id="image_sample",
                category="normal",
                media_path=image_file,
                expected_risk_range=(0, 25),
                expected_risk_level="low",
                expected_factors=[],
            ),
            PromptEvalSample(
                scenario_id="video_sample",
                category="normal",
                media_path=video_file,
                expected_risk_range=(0, 25),
                expected_risk_level="low",
                expected_factors=[],
            ),
        ]

        image_only = filter_samples_with_media(samples, media_type="image")
        video_only = filter_samples_with_media(samples, media_type="video")

        assert len(image_only) == 1
        assert image_only[0].scenario_id == "image_sample"

        assert len(video_only) == 1
        assert video_only[0].scenario_id == "video_sample"


class TestGetScenarioSummary:
    """Tests for get_scenario_summary function."""

    def test_empty_samples(self) -> None:
        """Test summary of empty sample list."""
        summary = get_scenario_summary([])

        assert summary["total_samples"] == 0
        assert summary["by_category"] == {}
        assert summary["by_risk_level"] == {}
        assert summary["with_media"] == 0
        assert summary["media_types"] == {}

    def test_full_summary(self, tmp_path: Path) -> None:
        """Test full summary with various samples."""
        image_file = tmp_path / "test.png"
        image_file.write_bytes(b"fake image")

        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake video")

        samples = [
            PromptEvalSample(
                scenario_id="normal_1",
                category="normal",
                media_path=image_file,
                expected_risk_range=(0, 25),
                expected_risk_level="low",
                expected_factors=[],
            ),
            PromptEvalSample(
                scenario_id="normal_2",
                category="normal",
                media_path=None,
                expected_risk_range=(0, 25),
                expected_risk_level="low",
                expected_factors=[],
            ),
            PromptEvalSample(
                scenario_id="suspicious_1",
                category="suspicious",
                media_path=video_file,
                expected_risk_range=(35, 60),
                expected_risk_level="medium",
                expected_factors=[],
            ),
        ]

        summary = get_scenario_summary(samples)

        assert summary["total_samples"] == 3
        assert summary["by_category"] == {"normal": 2, "suspicious": 1}
        assert summary["by_risk_level"] == {"low": 2, "medium": 1}
        assert summary["with_media"] == 2
        assert summary["media_types"] == {"image": 1, "video": 1}
