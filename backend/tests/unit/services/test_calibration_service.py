"""Unit tests for calibration service.

Tests cover:
- CalibrationService initialization
- get_or_create_calibration method
- adjust_from_feedback method
- reset_calibration method
- calculate_adjustment method
- Threshold constraint enforcement
- Edge cases at boundaries
- Singleton behavior
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models.event_feedback import FeedbackType
from backend.services.calibration_service import (
    DEFAULT_DECAY_FACTOR,
    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_LOW_THRESHOLD,
    DEFAULT_MEDIUM_THRESHOLD,
    MIN_THRESHOLD_GAP,
    CalibrationService,
    CalibrationThresholds,
    ThresholdAdjustment,
    get_calibration_service,
    reset_calibration_service,
)

# =============================================================================
# CalibrationService Initialization Tests
# =============================================================================


class TestCalibrationServiceInit:
    """Tests for CalibrationService initialization."""

    def test_init_default_values(self) -> None:
        """Test initialization with default values."""
        service = CalibrationService()
        assert service.default_low == DEFAULT_LOW_THRESHOLD
        assert service.default_medium == DEFAULT_MEDIUM_THRESHOLD
        assert service.default_high == DEFAULT_HIGH_THRESHOLD
        assert service.default_decay == DEFAULT_DECAY_FACTOR

    def test_init_custom_values(self) -> None:
        """Test initialization with custom values."""
        service = CalibrationService(
            default_low=20,
            default_medium=50,
            default_high=80,
            default_decay=0.2,
        )
        assert service.default_low == 20
        assert service.default_medium == 50
        assert service.default_high == 80
        assert service.default_decay == 0.2


# =============================================================================
# ThresholdAdjustment Tests
# =============================================================================


class TestThresholdAdjustment:
    """Tests for ThresholdAdjustment dataclass."""

    def test_create_adjustment(self) -> None:
        """Test creating a threshold adjustment."""
        adjustment = ThresholdAdjustment(
            low_delta=5,
            medium_delta=5,
            high_delta=5,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            original_risk_score=75,
        )
        assert adjustment.low_delta == 5
        assert adjustment.medium_delta == 5
        assert adjustment.high_delta == 5
        assert adjustment.feedback_type == FeedbackType.FALSE_POSITIVE
        assert adjustment.original_risk_score == 75

    def test_adjustment_to_dict(self) -> None:
        """Test conversion to dictionary."""
        adjustment = ThresholdAdjustment(
            low_delta=-3,
            medium_delta=-3,
            high_delta=-3,
            feedback_type=FeedbackType.MISSED_THREAT,
            original_risk_score=25,
        )
        result = adjustment.to_dict()
        assert result == {
            "low_delta": -3,
            "medium_delta": -3,
            "high_delta": -3,
            "feedback_type": "missed_threat",
            "original_risk_score": 25,
        }

    def test_adjustment_is_frozen(self) -> None:
        """Test that ThresholdAdjustment is immutable."""
        adjustment = ThresholdAdjustment(
            low_delta=5,
            medium_delta=5,
            high_delta=5,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            original_risk_score=75,
        )
        with pytest.raises(AttributeError):
            adjustment.low_delta = 10  # type: ignore[misc]


# =============================================================================
# CalibrationThresholds Tests
# =============================================================================


class TestCalibrationThresholds:
    """Tests for CalibrationThresholds NamedTuple."""

    def test_create_thresholds(self) -> None:
        """Test creating calibration thresholds."""
        thresholds = CalibrationThresholds(
            low_threshold=30,
            medium_threshold=60,
            high_threshold=85,
            is_calibrated=True,
        )
        assert thresholds.low_threshold == 30
        assert thresholds.medium_threshold == 60
        assert thresholds.high_threshold == 85
        assert thresholds.is_calibrated is True

    def test_thresholds_not_calibrated(self) -> None:
        """Test thresholds with is_calibrated=False."""
        thresholds = CalibrationThresholds(
            low_threshold=DEFAULT_LOW_THRESHOLD,
            medium_threshold=DEFAULT_MEDIUM_THRESHOLD,
            high_threshold=DEFAULT_HIGH_THRESHOLD,
            is_calibrated=False,
        )
        assert thresholds.is_calibrated is False

    def test_thresholds_immutable(self) -> None:
        """Test that CalibrationThresholds is immutable (NamedTuple)."""
        thresholds = CalibrationThresholds(
            low_threshold=30,
            medium_threshold=60,
            high_threshold=85,
            is_calibrated=True,
        )
        with pytest.raises(AttributeError):
            thresholds.low_threshold = 40  # type: ignore[misc]


# =============================================================================
# get_thresholds and get_default_thresholds Tests
# =============================================================================


class TestGetThresholds:
    """Tests for get_thresholds and get_default_thresholds methods."""

    @pytest.mark.asyncio
    async def test_get_thresholds_returns_defaults_when_no_calibration(self) -> None:
        """Test that get_thresholds returns defaults when no calibration exists."""
        service = CalibrationService()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        thresholds = await service.get_thresholds(mock_session, "new_user")

        assert thresholds.low_threshold == DEFAULT_LOW_THRESHOLD
        assert thresholds.medium_threshold == DEFAULT_MEDIUM_THRESHOLD
        assert thresholds.high_threshold == DEFAULT_HIGH_THRESHOLD
        assert thresholds.is_calibrated is False

    @pytest.mark.asyncio
    async def test_get_thresholds_returns_calibrated_values(self) -> None:
        """Test that get_thresholds returns user's calibrated values."""
        service = CalibrationService()

        from backend.models.user_calibration import UserCalibration

        calibration = UserCalibration(
            id=1,
            user_id="test_user",
            low_threshold=25,
            medium_threshold=55,
            high_threshold=80,
            decay_factor=0.15,
            false_positive_count=3,
            missed_detection_count=2,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.return_value = mock_result

        thresholds = await service.get_thresholds(mock_session, "test_user")

        assert thresholds.low_threshold == 25
        assert thresholds.medium_threshold == 55
        assert thresholds.high_threshold == 80
        assert thresholds.is_calibrated is True

    @pytest.mark.asyncio
    async def test_get_thresholds_not_calibrated_when_no_feedback(self) -> None:
        """Test that is_calibrated=False when user has no feedback."""
        service = CalibrationService()

        from backend.models.user_calibration import UserCalibration

        calibration = UserCalibration(
            id=1,
            user_id="test_user",
            low_threshold=30,
            medium_threshold=60,
            high_threshold=85,
            decay_factor=0.1,
            false_positive_count=0,
            missed_detection_count=0,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.return_value = mock_result

        thresholds = await service.get_thresholds(mock_session, "test_user")

        # User has calibration record but no feedback, so not calibrated
        assert thresholds.is_calibrated is False

    def test_get_default_thresholds(self) -> None:
        """Test get_default_thresholds returns default values."""
        service = CalibrationService()

        thresholds = service.get_default_thresholds()

        assert thresholds.low_threshold == DEFAULT_LOW_THRESHOLD
        assert thresholds.medium_threshold == DEFAULT_MEDIUM_THRESHOLD
        assert thresholds.high_threshold == DEFAULT_HIGH_THRESHOLD
        assert thresholds.is_calibrated is False

    def test_get_default_thresholds_with_custom_service(self) -> None:
        """Test get_default_thresholds uses service's configured defaults."""
        service = CalibrationService(
            default_low=20,
            default_medium=50,
            default_high=80,
        )

        thresholds = service.get_default_thresholds()

        assert thresholds.low_threshold == 20
        assert thresholds.medium_threshold == 50
        assert thresholds.high_threshold == 80
        assert thresholds.is_calibrated is False


# =============================================================================
# calculate_adjustment Tests
# =============================================================================


class TestCalculateAdjustment:
    """Tests for calculate_adjustment method."""

    def test_false_positive_raises_thresholds(self) -> None:
        """Test that FALSE_POSITIVE feedback results in positive deltas."""
        service = CalibrationService()
        adjustment = service.calculate_adjustment(
            feedback_type=FeedbackType.FALSE_POSITIVE,
            risk_score=75,
            decay_factor=0.1,
        )
        assert adjustment.low_delta > 0
        assert adjustment.medium_delta > 0
        assert adjustment.high_delta > 0
        assert adjustment.feedback_type == FeedbackType.FALSE_POSITIVE

    def test_missed_detection_lowers_thresholds(self) -> None:
        """Test that MISSED_DETECTION feedback results in negative deltas."""
        service = CalibrationService()
        adjustment = service.calculate_adjustment(
            feedback_type=FeedbackType.MISSED_THREAT,
            risk_score=25,
            decay_factor=0.1,
        )
        assert adjustment.low_delta < 0
        assert adjustment.medium_delta < 0
        assert adjustment.high_delta < 0
        assert adjustment.feedback_type == FeedbackType.MISSED_THREAT

    def test_higher_risk_score_larger_false_positive_adjustment(self) -> None:
        """Test that higher risk scores lead to larger adjustments for false positives."""
        service = CalibrationService()
        low_adj = service.calculate_adjustment(
            feedback_type=FeedbackType.FALSE_POSITIVE,
            risk_score=50,
            decay_factor=0.1,
        )
        high_adj = service.calculate_adjustment(
            feedback_type=FeedbackType.FALSE_POSITIVE,
            risk_score=90,
            decay_factor=0.1,
        )
        assert high_adj.low_delta >= low_adj.low_delta

    def test_lower_risk_score_larger_missed_detection_adjustment(self) -> None:
        """Test that lower risk scores lead to larger adjustments for missed detections."""
        service = CalibrationService()
        high_score_adj = service.calculate_adjustment(
            feedback_type=FeedbackType.MISSED_THREAT,
            risk_score=50,
            decay_factor=0.1,
        )
        low_score_adj = service.calculate_adjustment(
            feedback_type=FeedbackType.MISSED_THREAT,
            risk_score=10,
            decay_factor=0.1,
        )
        # Lower scores should result in larger magnitude (more negative)
        assert low_score_adj.low_delta <= high_score_adj.low_delta

    def test_zero_decay_factor_no_adjustment(self) -> None:
        """Test that zero decay factor results in no adjustment."""
        service = CalibrationService()
        adjustment = service.calculate_adjustment(
            feedback_type=FeedbackType.FALSE_POSITIVE,
            risk_score=75,
            decay_factor=0.0,
        )
        assert adjustment.low_delta == 0
        assert adjustment.medium_delta == 0
        assert adjustment.high_delta == 0

    def test_high_decay_factor_large_adjustment(self) -> None:
        """Test that higher decay factor results in larger adjustment."""
        service = CalibrationService()
        low_decay = service.calculate_adjustment(
            feedback_type=FeedbackType.FALSE_POSITIVE,
            risk_score=75,
            decay_factor=0.1,
        )
        high_decay = service.calculate_adjustment(
            feedback_type=FeedbackType.FALSE_POSITIVE,
            risk_score=75,
            decay_factor=0.5,
        )
        assert high_decay.low_delta > low_decay.low_delta

    @pytest.mark.parametrize(
        ("feedback_type", "expected_sign"),
        [
            (FeedbackType.FALSE_POSITIVE, 1),
            (FeedbackType.MISSED_THREAT, -1),
        ],
    )
    def test_adjustment_direction_by_feedback_type(
        self,
        feedback_type: FeedbackType,
        expected_sign: int,
    ) -> None:
        """Test adjustment direction based on feedback type."""
        service = CalibrationService()
        adjustment = service.calculate_adjustment(
            feedback_type=feedback_type,
            risk_score=50,
            decay_factor=0.1,
        )
        if expected_sign > 0:
            assert adjustment.low_delta > 0
        else:
            assert adjustment.low_delta < 0


# =============================================================================
# _apply_adjustment Tests (Constraint Enforcement)
# =============================================================================


class TestApplyAdjustment:
    """Tests for _apply_adjustment method (constraint enforcement)."""

    def test_basic_adjustment_applied(self) -> None:
        """Test that basic adjustments are applied correctly."""
        service = CalibrationService()
        adjustment = ThresholdAdjustment(
            low_delta=5,
            medium_delta=5,
            high_delta=5,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            original_risk_score=75,
        )
        new_low, new_medium, new_high = service._apply_adjustment(30, 60, 85, adjustment)
        assert new_low == 35
        assert new_medium == 65
        assert new_high == 90

    def test_negative_adjustment_applied(self) -> None:
        """Test that negative adjustments are applied correctly."""
        service = CalibrationService()
        adjustment = ThresholdAdjustment(
            low_delta=-5,
            medium_delta=-5,
            high_delta=-5,
            feedback_type=FeedbackType.MISSED_THREAT,
            original_risk_score=25,
        )
        new_low, new_medium, new_high = service._apply_adjustment(30, 60, 85, adjustment)
        assert new_low == 25
        assert new_medium == 55
        assert new_high == 80

    def test_clamped_at_zero(self) -> None:
        """Test that low threshold is clamped at 0."""
        service = CalibrationService()
        adjustment = ThresholdAdjustment(
            low_delta=-50,
            medium_delta=-50,
            high_delta=-50,
            feedback_type=FeedbackType.MISSED_THREAT,
            original_risk_score=10,
        )
        new_low, _new_medium, _new_high = service._apply_adjustment(10, 40, 70, adjustment)
        assert new_low >= 0

    def test_clamped_at_100(self) -> None:
        """Test that high threshold is clamped at 100."""
        service = CalibrationService()
        adjustment = ThresholdAdjustment(
            low_delta=50,
            medium_delta=50,
            high_delta=50,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            original_risk_score=90,
        )
        _new_low, _new_medium, new_high = service._apply_adjustment(50, 75, 90, adjustment)
        assert new_high <= 100

    def test_ordering_maintained_low_medium(self) -> None:
        """Test that low < medium ordering is maintained."""
        service = CalibrationService()
        adjustment = ThresholdAdjustment(
            low_delta=40,
            medium_delta=0,
            high_delta=0,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            original_risk_score=50,
        )
        new_low, new_medium, _new_high = service._apply_adjustment(30, 35, 85, adjustment)
        assert new_low < new_medium
        assert new_low + MIN_THRESHOLD_GAP <= new_medium

    def test_ordering_maintained_medium_high(self) -> None:
        """Test that medium < high ordering is maintained."""
        service = CalibrationService()
        adjustment = ThresholdAdjustment(
            low_delta=0,
            medium_delta=40,
            high_delta=0,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            original_risk_score=50,
        )
        _new_low, new_medium, new_high = service._apply_adjustment(30, 60, 65, adjustment)
        assert new_medium < new_high
        assert new_medium + MIN_THRESHOLD_GAP <= new_high

    def test_minimum_gap_enforced(self) -> None:
        """Test that minimum gap between thresholds is enforced."""
        service = CalibrationService()
        adjustment = ThresholdAdjustment(
            low_delta=30,
            medium_delta=0,
            high_delta=-20,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            original_risk_score=50,
        )
        new_low, new_medium, new_high = service._apply_adjustment(30, 60, 85, adjustment)

        # Verify minimum gaps
        assert new_medium >= new_low + MIN_THRESHOLD_GAP
        assert new_high >= new_medium + MIN_THRESHOLD_GAP

    def test_extreme_positive_adjustment(self) -> None:
        """Test handling of extreme positive adjustment."""
        service = CalibrationService()
        adjustment = ThresholdAdjustment(
            low_delta=100,
            medium_delta=100,
            high_delta=100,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            original_risk_score=100,
        )
        new_low, new_medium, new_high = service._apply_adjustment(30, 60, 85, adjustment)

        # All constraints should still be satisfied
        assert 0 <= new_low <= 100
        assert 0 <= new_medium <= 100
        assert 0 <= new_high <= 100
        assert new_low < new_medium < new_high

    def test_extreme_negative_adjustment(self) -> None:
        """Test handling of extreme negative adjustment."""
        service = CalibrationService()
        adjustment = ThresholdAdjustment(
            low_delta=-100,
            medium_delta=-100,
            high_delta=-100,
            feedback_type=FeedbackType.MISSED_THREAT,
            original_risk_score=0,
        )
        new_low, new_medium, new_high = service._apply_adjustment(30, 60, 85, adjustment)

        # All constraints should still be satisfied
        assert 0 <= new_low <= 100
        assert 0 <= new_medium <= 100
        assert 0 <= new_high <= 100
        assert new_low < new_medium < new_high


# =============================================================================
# get_or_create_calibration Tests
# =============================================================================


class TestGetOrCreateCalibration:
    """Tests for get_or_create_calibration method."""

    @pytest.mark.asyncio
    async def test_creates_new_calibration(self) -> None:
        """Test that a new calibration is created when none exists."""
        service = CalibrationService()

        # Mock database session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        calibration = await service.get_or_create_calibration(mock_session, "test_user")

        assert calibration.user_id == "test_user"
        assert calibration.low_threshold == DEFAULT_LOW_THRESHOLD
        assert calibration.medium_threshold == DEFAULT_MEDIUM_THRESHOLD
        assert calibration.high_threshold == DEFAULT_HIGH_THRESHOLD
        assert calibration.decay_factor == DEFAULT_DECAY_FACTOR
        assert calibration.false_positive_count == 0
        assert calibration.missed_detection_count == 0

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_existing_calibration(self) -> None:
        """Test that existing calibration is returned."""
        service = CalibrationService()

        # Create mock existing calibration
        from backend.models.user_calibration import UserCalibration

        existing_calibration = UserCalibration(
            id=1,
            user_id="test_user",
            low_threshold=25,
            medium_threshold=55,
            high_threshold=80,
            decay_factor=0.15,
            false_positive_count=5,
            missed_detection_count=3,
        )

        # Mock database session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_calibration
        mock_session.execute.return_value = mock_result

        calibration = await service.get_or_create_calibration(mock_session, "test_user")

        assert calibration is existing_calibration
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_default_user_id(self) -> None:
        """Test that default user_id is 'default'."""
        service = CalibrationService()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        calibration = await service.get_or_create_calibration(mock_session)

        assert calibration.user_id == "default"


# =============================================================================
# adjust_from_feedback Tests
# =============================================================================


class TestAdjustFromFeedback:
    """Tests for adjust_from_feedback method."""

    @pytest.mark.asyncio
    async def test_adjusts_on_false_positive(self) -> None:
        """Test that thresholds are raised on false positive feedback."""
        service = CalibrationService()

        # Create mock calibration
        from backend.models.user_calibration import UserCalibration

        calibration = UserCalibration(
            id=1,
            user_id="test_user",
            low_threshold=30,
            medium_threshold=60,
            high_threshold=85,
            decay_factor=0.1,
            false_positive_count=0,
            missed_detection_count=0,
        )

        # Mock database session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.return_value = mock_result

        # Create mock feedback and event
        from backend.models.event import Event
        from backend.models.event_feedback import EventFeedback

        mock_event = MagicMock(spec=Event)
        mock_event.id = 1
        mock_event.risk_score = 75

        mock_feedback = MagicMock(spec=EventFeedback)
        mock_feedback.feedback_type = FeedbackType.FALSE_POSITIVE

        result = await service.adjust_from_feedback(
            mock_session, mock_feedback, mock_event, "test_user"
        )

        # Thresholds should be raised (less sensitive)
        assert result.low_threshold >= 30
        assert result.medium_threshold >= 60
        assert result.high_threshold >= 85
        assert result.false_positive_count == 1
        assert result.missed_detection_count == 0

    @pytest.mark.asyncio
    async def test_adjusts_on_missed_detection(self) -> None:
        """Test that thresholds are lowered on missed detection feedback."""
        service = CalibrationService()

        from backend.models.user_calibration import UserCalibration

        calibration = UserCalibration(
            id=1,
            user_id="test_user",
            low_threshold=30,
            medium_threshold=60,
            high_threshold=85,
            decay_factor=0.1,
            false_positive_count=0,
            missed_detection_count=0,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.return_value = mock_result

        from backend.models.event import Event
        from backend.models.event_feedback import EventFeedback

        mock_event = MagicMock(spec=Event)
        mock_event.id = 1
        mock_event.risk_score = 25

        mock_feedback = MagicMock(spec=EventFeedback)
        mock_feedback.feedback_type = FeedbackType.MISSED_THREAT

        result = await service.adjust_from_feedback(
            mock_session, mock_feedback, mock_event, "test_user"
        )

        # Thresholds should be lowered (more sensitive)
        assert result.low_threshold <= 30
        assert result.medium_threshold <= 60
        assert result.high_threshold <= 85
        assert result.false_positive_count == 0
        assert result.missed_detection_count == 1

    @pytest.mark.asyncio
    async def test_handles_null_risk_score(self) -> None:
        """Test that events without risk scores don't cause adjustments."""
        service = CalibrationService()

        from backend.models.user_calibration import UserCalibration

        calibration = UserCalibration(
            id=1,
            user_id="test_user",
            low_threshold=30,
            medium_threshold=60,
            high_threshold=85,
            decay_factor=0.1,
            false_positive_count=0,
            missed_detection_count=0,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.return_value = mock_result

        from backend.models.event import Event
        from backend.models.event_feedback import EventFeedback

        mock_event = MagicMock(spec=Event)
        mock_event.id = 1
        mock_event.risk_score = None  # No risk score

        mock_feedback = MagicMock(spec=EventFeedback)
        mock_feedback.feedback_type = FeedbackType.FALSE_POSITIVE

        result = await service.adjust_from_feedback(
            mock_session, mock_feedback, mock_event, "test_user"
        )

        # Thresholds should remain unchanged
        assert result.low_threshold == 30
        assert result.medium_threshold == 60
        assert result.high_threshold == 85
        assert result.false_positive_count == 0
        assert result.missed_detection_count == 0


# =============================================================================
# reset_calibration Tests
# =============================================================================


class TestResetCalibration:
    """Tests for reset_calibration method."""

    @pytest.mark.asyncio
    async def test_resets_to_defaults(self) -> None:
        """Test that calibration is reset to default values."""
        service = CalibrationService()

        from backend.models.user_calibration import UserCalibration

        calibration = UserCalibration(
            id=1,
            user_id="test_user",
            low_threshold=20,
            medium_threshold=50,
            high_threshold=80,
            decay_factor=0.2,
            false_positive_count=10,
            missed_detection_count=5,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.return_value = mock_result

        result = await service.reset_calibration(mock_session, "test_user")

        assert result.low_threshold == DEFAULT_LOW_THRESHOLD
        assert result.medium_threshold == DEFAULT_MEDIUM_THRESHOLD
        assert result.high_threshold == DEFAULT_HIGH_THRESHOLD
        assert result.decay_factor == DEFAULT_DECAY_FACTOR
        assert result.false_positive_count == 0
        assert result.missed_detection_count == 0

    @pytest.mark.asyncio
    async def test_creates_if_not_exists(self) -> None:
        """Test that reset creates calibration if none exists."""
        service = CalibrationService()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await service.reset_calibration(mock_session, "new_user")

        assert result.user_id == "new_user"
        assert result.low_threshold == DEFAULT_LOW_THRESHOLD
        mock_session.add.assert_called_once()


# =============================================================================
# Singleton Tests
# =============================================================================


class TestCalibrationSingleton:
    """Tests for calibration service singleton functions."""

    def test_get_calibration_service_creates_singleton(self) -> None:
        """Test that get_calibration_service creates and returns singleton."""
        reset_calibration_service()
        service1 = get_calibration_service()
        service2 = get_calibration_service()

        assert service1 is service2
        reset_calibration_service()

    def test_reset_calibration_service_clears_cache(self) -> None:
        """Test that reset_calibration_service clears the singleton."""
        service1 = get_calibration_service()
        reset_calibration_service()
        service2 = get_calibration_service()

        assert service1 is not service2
        reset_calibration_service()


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_thresholds_at_boundary_low(self) -> None:
        """Test adjustments when low threshold is at 0."""
        service = CalibrationService()
        adjustment = ThresholdAdjustment(
            low_delta=-10,
            medium_delta=-10,
            high_delta=-10,
            feedback_type=FeedbackType.MISSED_THREAT,
            original_risk_score=5,
        )
        new_low, new_medium, new_high = service._apply_adjustment(5, 35, 65, adjustment)

        assert new_low >= 0
        assert new_low < new_medium < new_high

    def test_thresholds_at_boundary_high(self) -> None:
        """Test adjustments when high threshold is near 100."""
        service = CalibrationService()
        adjustment = ThresholdAdjustment(
            low_delta=10,
            medium_delta=10,
            high_delta=10,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            original_risk_score=95,
        )
        new_low, new_medium, new_high = service._apply_adjustment(70, 85, 95, adjustment)

        assert new_high <= 100
        assert new_low < new_medium < new_high

    def test_very_small_decay_factor(self) -> None:
        """Test with very small decay factor."""
        service = CalibrationService()
        adjustment = service.calculate_adjustment(
            feedback_type=FeedbackType.FALSE_POSITIVE,
            risk_score=75,
            decay_factor=0.01,
        )
        # Should still result in at least minimal adjustment
        assert adjustment.low_delta >= 0

    def test_decay_factor_at_max(self) -> None:
        """Test with maximum decay factor."""
        service = CalibrationService()
        adjustment = service.calculate_adjustment(
            feedback_type=FeedbackType.FALSE_POSITIVE,
            risk_score=100,
            decay_factor=1.0,
        )
        # Should result in significant adjustment
        assert adjustment.low_delta > 0

    @pytest.mark.parametrize(
        ("low", "medium", "high"),
        [
            (0, MIN_THRESHOLD_GAP, 2 * MIN_THRESHOLD_GAP),
            (100 - 2 * MIN_THRESHOLD_GAP, 100 - MIN_THRESHOLD_GAP, 100),
        ],
    )
    def test_extreme_starting_thresholds(
        self,
        low: int,
        medium: int,
        high: int,
    ) -> None:
        """Test adjustments with extreme starting thresholds."""
        service = CalibrationService()

        # Test positive adjustment
        pos_adjustment = ThresholdAdjustment(
            low_delta=10,
            medium_delta=10,
            high_delta=10,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            original_risk_score=80,
        )
        new_low, new_medium, new_high = service._apply_adjustment(low, medium, high, pos_adjustment)
        assert new_low < new_medium < new_high
        assert 0 <= new_low <= 100
        assert 0 <= new_high <= 100

        # Test negative adjustment
        neg_adjustment = ThresholdAdjustment(
            low_delta=-10,
            medium_delta=-10,
            high_delta=-10,
            feedback_type=FeedbackType.MISSED_THREAT,
            original_risk_score=20,
        )
        new_low2, new_medium2, new_high2 = service._apply_adjustment(
            low, medium, high, neg_adjustment
        )
        assert new_low2 < new_medium2 < new_high2
        assert 0 <= new_low2 <= 100
        assert 0 <= new_high2 <= 100


# =============================================================================
# Constants Tests
# =============================================================================


class TestCalibrationConstants:
    """Tests for calibration constants."""

    def test_default_thresholds_ordering(self) -> None:
        """Test that default thresholds are properly ordered."""
        assert DEFAULT_LOW_THRESHOLD < DEFAULT_MEDIUM_THRESHOLD < DEFAULT_HIGH_THRESHOLD

    def test_default_thresholds_in_range(self) -> None:
        """Test that default thresholds are in valid range."""
        assert 0 <= DEFAULT_LOW_THRESHOLD <= 100
        assert 0 <= DEFAULT_MEDIUM_THRESHOLD <= 100
        assert 0 <= DEFAULT_HIGH_THRESHOLD <= 100

    def test_default_decay_factor_in_range(self) -> None:
        """Test that default decay factor is in valid range."""
        assert 0.0 <= DEFAULT_DECAY_FACTOR <= 1.0

    def test_min_threshold_gap_positive(self) -> None:
        """Test that minimum threshold gap is positive."""
        assert MIN_THRESHOLD_GAP > 0

    def test_default_thresholds_have_sufficient_gaps(self) -> None:
        """Test that default thresholds have sufficient gaps."""
        assert DEFAULT_MEDIUM_THRESHOLD - DEFAULT_LOW_THRESHOLD >= MIN_THRESHOLD_GAP
        assert DEFAULT_HIGH_THRESHOLD - DEFAULT_MEDIUM_THRESHOLD >= MIN_THRESHOLD_GAP
