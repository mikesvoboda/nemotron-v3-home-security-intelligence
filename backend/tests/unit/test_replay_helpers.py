"""Unit tests for replay helper utilities (NEM-3339).

Tests the reusable utilities in backend.tests.utils.replay_helpers module
for historical event replay testing infrastructure.
"""

import pytest

from backend.tests.utils.replay_helpers import (
    DistributionTargets,
    ReplayResult,
    ReplayStatistics,
    calculate_replay_statistics,
    classify_risk_level,
    create_mock_replay_result,
    generate_replay_report,
    generate_sample_results,
    validate_distribution,
)


class TestClassifyRiskLevel:
    """Tests for the classify_risk_level function."""

    @pytest.mark.parametrize(
        "score,expected_level",
        [
            (0, "low"),
            (10, "low"),
            (39, "low"),
            (40, "medium"),
            (50, "medium"),
            (69, "medium"),
            (70, "high"),
            (80, "high"),
            (89, "high"),
            (90, "critical"),
            (95, "critical"),
            (100, "critical"),
        ],
    )
    def test_risk_level_thresholds(self, score, expected_level):
        """Test that scores are classified at correct thresholds."""
        assert classify_risk_level(score) == expected_level

    def test_boundary_values(self):
        """Test exact boundary values."""
        assert classify_risk_level(39) == "low"
        assert classify_risk_level(40) == "medium"
        assert classify_risk_level(69) == "medium"
        assert classify_risk_level(70) == "high"
        assert classify_risk_level(89) == "high"
        assert classify_risk_level(90) == "critical"


class TestReplayResult:
    """Tests for the ReplayResult dataclass."""

    def test_score_decreased(self):
        """Test score_decreased property."""
        result = ReplayResult(
            event_id=1,
            camera_id="cam1",
            original_risk_score=70,
            original_risk_level="high",
            new_risk_score=30,
            new_risk_level="low",
            score_diff=40,
            detection_count=1,
            object_types="person",
        )
        assert result.score_decreased is True
        assert result.score_increased is False

    def test_score_increased(self):
        """Test score_increased property."""
        result = ReplayResult(
            event_id=1,
            camera_id="cam1",
            original_risk_score=30,
            original_risk_level="low",
            new_risk_score=70,
            new_risk_level="high",
            score_diff=40,
            detection_count=1,
            object_types="person",
        )
        assert result.score_decreased is False
        assert result.score_increased is True

    def test_score_unchanged(self):
        """Test when score is unchanged."""
        result = ReplayResult(
            event_id=1,
            camera_id="cam1",
            original_risk_score=50,
            original_risk_level="medium",
            new_risk_score=50,
            new_risk_level="medium",
            score_diff=0,
            detection_count=1,
            object_types="person",
        )
        assert result.score_decreased is False
        assert result.score_increased is False

    def test_no_original_score(self):
        """Test when original score is None."""
        result = ReplayResult(
            event_id=1,
            camera_id="cam1",
            original_risk_score=None,
            original_risk_level=None,
            new_risk_score=50,
            new_risk_level="medium",
            score_diff=0,
            detection_count=1,
            object_types="person",
        )
        assert result.score_decreased is False
        assert result.score_increased is False

    def test_level_changed(self):
        """Test level_changed property."""
        changed = ReplayResult(
            event_id=1,
            camera_id="cam1",
            original_risk_score=70,
            original_risk_level="high",
            new_risk_score=30,
            new_risk_level="low",
            score_diff=40,
            detection_count=1,
            object_types="person",
        )
        assert changed.level_changed is True

        unchanged = ReplayResult(
            event_id=2,
            camera_id="cam1",
            original_risk_score=45,
            original_risk_level="medium",
            new_risk_score=55,
            new_risk_level="medium",
            score_diff=10,
            detection_count=1,
            object_types="person",
        )
        assert unchanged.level_changed is False

    def test_is_downgrade(self):
        """Test is_downgrade property."""
        downgrade = ReplayResult(
            event_id=1,
            camera_id="cam1",
            original_risk_score=80,
            original_risk_level="high",
            new_risk_score=30,
            new_risk_level="low",
            score_diff=50,
            detection_count=1,
            object_types="person",
        )
        assert downgrade.is_downgrade is True
        assert downgrade.is_upgrade is False

    def test_is_upgrade(self):
        """Test is_upgrade property."""
        upgrade = ReplayResult(
            event_id=1,
            camera_id="cam1",
            original_risk_score=30,
            original_risk_level="low",
            new_risk_score=85,
            new_risk_level="high",
            score_diff=55,
            detection_count=1,
            object_types="person",
        )
        assert upgrade.is_upgrade is True
        assert upgrade.is_downgrade is False


class TestReplayStatistics:
    """Tests for the ReplayStatistics dataclass."""

    def test_percentage_calculations(self):
        """Test percentage calculation properties."""
        stats = ReplayStatistics(
            total_events=100,
            low_count=55,
            medium_count=35,
            high_count=10,
            mean_score=45.0,
            median_score=42.0,
            std_dev=15.0,
            mean_score_diff=20.0,
            scores_decreased_count=60,
            scores_increased_count=20,
            scores_unchanged_count=20,
        )
        import pytest

        assert stats.low_percentage == pytest.approx(55.0)
        assert stats.medium_percentage == pytest.approx(35.0)
        assert stats.high_percentage == pytest.approx(10.0)

    def test_zero_events(self):
        """Test percentages with zero total events."""
        stats = ReplayStatistics(
            total_events=0,
            low_count=0,
            medium_count=0,
            high_count=0,
            mean_score=0.0,
            median_score=0.0,
            std_dev=0.0,
            mean_score_diff=0.0,
            scores_decreased_count=0,
            scores_increased_count=0,
            scores_unchanged_count=0,
        )
        assert stats.low_percentage == 0
        assert stats.medium_percentage == 0
        assert stats.high_percentage == 0


class TestDistributionTargets:
    """Tests for the DistributionTargets dataclass."""

    def test_default_values(self):
        """Test default target values."""
        targets = DistributionTargets()
        assert targets.low_min == 50.0
        assert targets.low_max == 60.0
        assert targets.medium_min == 30.0
        assert targets.medium_max == 40.0
        assert targets.high_min == 15.0
        assert targets.high_max == 20.0

    def test_custom_values(self):
        """Test custom target values."""
        targets = DistributionTargets(
            low_min=40.0,
            low_max=50.0,
            medium_min=25.0,
            medium_max=35.0,
            high_min=20.0,
            high_max=30.0,
        )
        assert targets.low_min == 40.0
        assert targets.high_max == 30.0

    def test_is_in_range_methods(self):
        """Test range check methods."""
        targets = DistributionTargets()

        # LOW range: 50-60
        assert targets.is_low_in_range(50.0) is True
        assert targets.is_low_in_range(55.0) is True
        assert targets.is_low_in_range(60.0) is True
        assert targets.is_low_in_range(49.9) is False
        assert targets.is_low_in_range(60.1) is False

        # MEDIUM range: 30-40
        assert targets.is_medium_in_range(35.0) is True
        assert targets.is_medium_in_range(29.9) is False

        # HIGH range: 15-20
        assert targets.is_high_in_range(17.5) is True
        assert targets.is_high_in_range(14.9) is False


class TestCalculateReplayStatistics:
    """Tests for calculate_replay_statistics function."""

    def test_empty_results(self):
        """Test with empty results list."""
        stats = calculate_replay_statistics([])
        assert stats.total_events == 0
        assert stats.mean_score == 0.0
        assert stats.low_percentage == 0

    def test_single_result(self):
        """Test with single result."""
        result = create_mock_replay_result(new_score=30)
        stats = calculate_replay_statistics([result])

        assert stats.total_events == 1
        assert stats.low_count == 1
        assert stats.medium_count == 0
        assert stats.high_count == 0
        assert stats.mean_score == 30.0
        assert stats.std_dev == 0.0  # No deviation with single value

    def test_multiple_results(self):
        """Test with multiple results."""
        results = [
            create_mock_replay_result(event_id=1, new_score=25),  # LOW
            create_mock_replay_result(event_id=2, new_score=35),  # LOW
            create_mock_replay_result(event_id=3, new_score=50),  # MEDIUM
            create_mock_replay_result(event_id=4, new_score=60),  # MEDIUM
            create_mock_replay_result(event_id=5, new_score=75),  # HIGH
        ]
        stats = calculate_replay_statistics(results)

        assert stats.total_events == 5
        assert stats.low_count == 2
        assert stats.medium_count == 2
        assert stats.high_count == 1
        assert stats.low_percentage == 40.0
        assert stats.mean_score == 49.0  # (25+35+50+60+75)/5

    def test_score_change_tracking(self):
        """Test tracking of score changes."""
        results = [
            ReplayResult(
                event_id=1,
                camera_id="cam1",
                original_risk_score=70,
                original_risk_level="high",
                new_risk_score=30,
                new_risk_level="low",
                score_diff=40,
                detection_count=1,
                object_types="person",
            ),
            ReplayResult(
                event_id=2,
                camera_id="cam1",
                original_risk_score=30,
                original_risk_level="low",
                new_risk_score=70,
                new_risk_level="high",
                score_diff=40,
                detection_count=1,
                object_types="person",
            ),
            ReplayResult(
                event_id=3,
                camera_id="cam1",
                original_risk_score=50,
                original_risk_level="medium",
                new_risk_score=50,
                new_risk_level="medium",
                score_diff=0,
                detection_count=1,
                object_types="person",
            ),
        ]
        stats = calculate_replay_statistics(results)

        assert stats.scores_decreased_count == 1
        assert stats.scores_increased_count == 1
        assert stats.scores_unchanged_count == 1


class TestValidateDistribution:
    """Tests for validate_distribution function."""

    def test_valid_distribution(self):
        """Test validation with valid distribution."""
        stats = ReplayStatistics(
            total_events=100,
            low_count=55,
            medium_count=35,
            high_count=10,
            mean_score=45.0,
            median_score=42.0,
            std_dev=15.0,
            mean_score_diff=20.0,
            scores_decreased_count=60,
            scores_increased_count=20,
            scores_unchanged_count=20,
        )
        is_valid, messages = validate_distribution(stats)

        # LOW 55% is in range, MEDIUM 35% is in range
        # HIGH 10% is below target minimum (15%), but not a failure in non-strict mode
        # A warning message is added but is_valid stays True
        assert is_valid is True
        assert any("HIGH" in m and "below target" in m for m in messages)

    def test_invalid_low_percentage(self):
        """Test validation fails when LOW is too low."""
        stats = ReplayStatistics(
            total_events=100,
            low_count=30,  # 30% - below target 50-60%
            medium_count=30,
            high_count=40,
            mean_score=55.0,
            median_score=58.0,
            std_dev=20.0,
            mean_score_diff=10.0,
            scores_decreased_count=30,
            scores_increased_count=50,
            scores_unchanged_count=20,
        )
        is_valid, messages = validate_distribution(stats)

        assert is_valid is False
        assert any("LOW" in m and "below target" in m for m in messages)

    def test_strict_mode(self):
        """Test strict validation mode."""
        stats = ReplayStatistics(
            total_events=100,
            low_count=55,
            medium_count=25,  # 25% - below target 30-40%
            high_count=20,
            mean_score=50.0,
            median_score=48.0,
            std_dev=18.0,
            mean_score_diff=15.0,
            scores_decreased_count=50,
            scores_increased_count=30,
            scores_unchanged_count=20,
        )

        # Non-strict mode: passes
        is_valid_normal, _ = validate_distribution(stats, strict=False)
        # In non-strict mode, MEDIUM below target isn't a failure
        # But LOW is in range, so it passes
        assert is_valid_normal is True

        # Strict mode: fails on MEDIUM
        is_valid_strict, _messages = validate_distribution(stats, strict=True)
        assert is_valid_strict is False

    def test_custom_targets(self):
        """Test validation with custom targets."""
        custom_targets = DistributionTargets(
            low_min=40.0,
            low_max=50.0,
            medium_min=30.0,
            medium_max=40.0,
            high_min=20.0,
            high_max=30.0,
        )
        stats = ReplayStatistics(
            total_events=100,
            low_count=45,  # 45% - in custom range
            medium_count=30,  # 30% - in range
            high_count=25,  # 25% - in custom range
            mean_score=50.0,
            median_score=48.0,
            std_dev=20.0,
            mean_score_diff=15.0,
            scores_decreased_count=50,
            scores_increased_count=30,
            scores_unchanged_count=20,
        )
        is_valid, _messages = validate_distribution(stats, targets=custom_targets)

        assert is_valid is True


class TestGenerateReplayReport:
    """Tests for generate_replay_report function."""

    def test_report_structure(self):
        """Test that report has correct structure."""
        stats = ReplayStatistics(
            total_events=50,
            low_count=25,
            medium_count=18,
            high_count=7,
            mean_score=42.0,
            median_score=40.0,
            std_dev=16.0,
            mean_score_diff=22.0,
            scores_decreased_count=35,
            scores_increased_count=10,
            scores_unchanged_count=5,
        )
        report = generate_replay_report(stats, experiment_name="test_experiment")

        # Check top-level keys
        assert report["experiment_name"] == "test_experiment"
        assert report["total_events"] == 50

        # Check distribution section
        assert "distribution" in report
        assert "low" in report["distribution"]
        assert "medium" in report["distribution"]
        assert "high" in report["distribution"]

        # Check each distribution category
        assert report["distribution"]["low"]["count"] == 25
        assert report["distribution"]["low"]["percentage"] == 50.0
        assert "target_range" in report["distribution"]["low"]
        assert "in_range" in report["distribution"]["low"]

        # Check score metrics
        assert "score_metrics" in report
        assert report["score_metrics"]["mean"] == 42.0
        assert report["score_metrics"]["median"] == 40.0

        # Check comparison metrics
        assert "comparison_metrics" in report
        assert report["comparison_metrics"]["scores_decreased"] == 35

        # Check validation
        assert "validation" in report
        assert "passed" in report["validation"]
        assert "messages" in report["validation"]

    def test_report_without_validation(self):
        """Test report generation without validation."""
        stats = ReplayStatistics(
            total_events=50,
            low_count=25,
            medium_count=18,
            high_count=7,
            mean_score=42.0,
            median_score=40.0,
            std_dev=16.0,
            mean_score_diff=22.0,
            scores_decreased_count=35,
            scores_increased_count=10,
            scores_unchanged_count=5,
        )
        report = generate_replay_report(stats, include_validation=False)

        assert "validation" not in report


class TestCreateMockReplayResult:
    """Tests for create_mock_replay_result helper."""

    def test_default_values(self):
        """Test mock with default values."""
        result = create_mock_replay_result()

        assert result.event_id == 1
        assert result.camera_id == "cam1"
        assert result.original_risk_score == 50
        assert result.new_risk_score == 30
        assert result.object_types == "person"

    def test_custom_values(self):
        """Test mock with custom values."""
        result = create_mock_replay_result(
            event_id=42,
            camera_id="front_door",
            original_score=80,
            new_score=25,
            object_types="cat",
            detection_count=3,
        )

        assert result.event_id == 42
        assert result.camera_id == "front_door"
        assert result.original_risk_score == 80
        assert result.original_risk_level == "high"
        assert result.new_risk_score == 25
        assert result.new_risk_level == "low"
        assert result.object_types == "cat"
        assert result.detection_count == 3
        assert result.score_diff == 55


class TestGenerateSampleResults:
    """Tests for generate_sample_results helper."""

    def test_default_distribution(self):
        """Test generating results with default distribution."""
        results = generate_sample_results(count=100)

        stats = calculate_replay_statistics(results)

        # Default is 55% low, 35% medium, 10% high
        assert stats.low_count == 55
        assert stats.medium_count == 35
        assert stats.high_count == 10

    def test_custom_distribution(self):
        """Test generating results with custom distribution."""
        results = generate_sample_results(count=100, low_pct=60.0, medium_pct=30.0)

        stats = calculate_replay_statistics(results)

        # 60% low, 30% medium, 10% high
        assert stats.low_count == 60
        assert stats.medium_count == 30
        assert stats.high_count == 10

    def test_small_sample(self):
        """Test with small sample size."""
        results = generate_sample_results(count=10, low_pct=50.0, medium_pct=30.0)

        assert len(results) == 10
        stats = calculate_replay_statistics(results)
        assert stats.total_events == 10
