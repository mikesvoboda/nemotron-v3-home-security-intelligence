"""Unit tests for FeedbackProcessor service.

Tests cover:
- FeedbackProcessor initialization
- process_feedback method
- _update_camera_calibration method
- _get_or_create_calibration method
- Auto-adjustment logic based on FP rate
- Risk offset boundaries
- Singleton behavior

Related Linear issues: NEM-3022
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models.camera_calibration import CameraCalibration
from backend.models.event import Event
from backend.models.event_feedback import EventFeedback, FeedbackType
from backend.services.feedback_processor import (
    AUTO_ADJUST_MIN_FEEDBACK,
    HIGH_FP_RATE_THRESHOLD,
    LOW_FP_RATE_THRESHOLD,
    MAX_RISK_OFFSET,
    MIN_RISK_OFFSET,
    OFFSET_DECREASE_STEP,
    OFFSET_INCREASE_STEP,
    FeedbackProcessor,
    get_feedback_processor,
    reset_feedback_processor,
)

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# FeedbackProcessor Initialization Tests
# =============================================================================


class TestFeedbackProcessorInit:
    """Tests for FeedbackProcessor initialization."""

    def test_init_default_values(self) -> None:
        """Test initialization with default values."""
        processor = FeedbackProcessor()
        assert processor.min_feedback_for_adjustment == AUTO_ADJUST_MIN_FEEDBACK
        assert processor.high_fp_threshold == HIGH_FP_RATE_THRESHOLD
        assert processor.low_fp_threshold == LOW_FP_RATE_THRESHOLD

    def test_init_custom_values(self) -> None:
        """Test initialization with custom values."""
        processor = FeedbackProcessor(
            min_feedback_for_adjustment=30,
            high_fp_threshold=0.6,
            low_fp_threshold=0.15,
        )
        assert processor.min_feedback_for_adjustment == 30
        assert processor.high_fp_threshold == 0.6
        assert processor.low_fp_threshold == 0.15


# =============================================================================
# Constants Tests
# =============================================================================


class TestFeedbackProcessorConstants:
    """Tests for FeedbackProcessor constants."""

    def test_auto_adjust_min_feedback(self) -> None:
        """Test AUTO_ADJUST_MIN_FEEDBACK has sensible value."""
        assert AUTO_ADJUST_MIN_FEEDBACK >= 10
        assert AUTO_ADJUST_MIN_FEEDBACK <= 50

    def test_high_fp_rate_threshold(self) -> None:
        """Test HIGH_FP_RATE_THRESHOLD is reasonable."""
        assert HIGH_FP_RATE_THRESHOLD > 0.0
        assert HIGH_FP_RATE_THRESHOLD <= 1.0
        assert HIGH_FP_RATE_THRESHOLD > LOW_FP_RATE_THRESHOLD

    def test_low_fp_rate_threshold(self) -> None:
        """Test LOW_FP_RATE_THRESHOLD is reasonable."""
        assert LOW_FP_RATE_THRESHOLD >= 0.0
        assert LOW_FP_RATE_THRESHOLD < 1.0

    def test_risk_offset_bounds(self) -> None:
        """Test risk offset bounds are sensible."""
        assert MIN_RISK_OFFSET == -30
        assert MAX_RISK_OFFSET == 30
        assert MIN_RISK_OFFSET < MAX_RISK_OFFSET

    def test_offset_step_sizes(self) -> None:
        """Test offset step sizes are sensible."""
        assert OFFSET_DECREASE_STEP > 0
        assert OFFSET_INCREASE_STEP > 0
        # Decrease step should be larger (faster correction for over-alerting)
        assert OFFSET_DECREASE_STEP >= OFFSET_INCREASE_STEP


# =============================================================================
# get_or_create_calibration Tests
# =============================================================================


class TestGetOrCreateCalibration:
    """Tests for _get_or_create_calibration method."""

    @pytest.mark.asyncio
    async def test_creates_new_calibration_when_none_exists(self) -> None:
        """Test that a new calibration is created when none exists."""
        processor = FeedbackProcessor()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        calibration = await processor._get_or_create_calibration(mock_session, "front_door")

        assert calibration.camera_id == "front_door"
        assert calibration.total_feedback_count == 0
        assert calibration.false_positive_count == 0
        assert calibration.false_positive_rate == 0.0
        assert calibration.risk_offset == 0
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_existing_calibration(self) -> None:
        """Test that existing calibration is returned."""
        processor = FeedbackProcessor()

        existing_calibration = CameraCalibration(
            id=1,
            camera_id="front_door",
            total_feedback_count=10,
            false_positive_count=5,
            false_positive_rate=0.5,
            risk_offset=-10,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_calibration
        mock_session.execute.return_value = mock_result

        calibration = await processor._get_or_create_calibration(mock_session, "front_door")

        assert calibration is existing_calibration
        mock_session.add.assert_not_called()


# =============================================================================
# update_camera_calibration Tests
# =============================================================================


class TestUpdateCameraCalibration:
    """Tests for _update_camera_calibration method."""

    @pytest.mark.asyncio
    async def test_increments_total_feedback_count(self) -> None:
        """Test that total_feedback_count is incremented."""
        processor = FeedbackProcessor()

        calibration = CameraCalibration(
            id=1,
            camera_id="front_door",
            total_feedback_count=10,
            false_positive_count=3,
            false_positive_rate=0.3,
            risk_offset=0,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.return_value = mock_result

        mock_feedback = MagicMock(spec=EventFeedback)
        mock_feedback.feedback_type = FeedbackType.CORRECT

        await processor._update_camera_calibration("front_door", mock_feedback, mock_session)

        assert calibration.total_feedback_count == 11

    @pytest.mark.asyncio
    async def test_increments_fp_count_on_false_positive(self) -> None:
        """Test that false_positive_count is incremented for false positive feedback."""
        processor = FeedbackProcessor()

        calibration = CameraCalibration(
            id=1,
            camera_id="front_door",
            total_feedback_count=10,
            false_positive_count=3,
            false_positive_rate=0.3,
            risk_offset=0,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.return_value = mock_result

        mock_feedback = MagicMock(spec=EventFeedback)
        mock_feedback.feedback_type = FeedbackType.FALSE_POSITIVE

        await processor._update_camera_calibration("front_door", mock_feedback, mock_session)

        assert calibration.total_feedback_count == 11
        assert calibration.false_positive_count == 4

    @pytest.mark.asyncio
    async def test_does_not_increment_fp_count_on_correct(self) -> None:
        """Test that false_positive_count is not incremented for correct feedback."""
        processor = FeedbackProcessor()

        calibration = CameraCalibration(
            id=1,
            camera_id="front_door",
            total_feedback_count=10,
            false_positive_count=3,
            false_positive_rate=0.3,
            risk_offset=0,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.return_value = mock_result

        mock_feedback = MagicMock(spec=EventFeedback)
        mock_feedback.feedback_type = FeedbackType.CORRECT

        await processor._update_camera_calibration("front_door", mock_feedback, mock_session)

        assert calibration.false_positive_count == 3  # Unchanged

    @pytest.mark.asyncio
    async def test_updates_fp_rate(self) -> None:
        """Test that false_positive_rate is recalculated."""
        processor = FeedbackProcessor()

        calibration = CameraCalibration(
            id=1,
            camera_id="front_door",
            total_feedback_count=9,  # Will become 10
            false_positive_count=4,  # Will become 5
            false_positive_rate=0.444,  # Will become 0.5
            risk_offset=0,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.return_value = mock_result

        mock_feedback = MagicMock(spec=EventFeedback)
        mock_feedback.feedback_type = FeedbackType.FALSE_POSITIVE

        await processor._update_camera_calibration("front_door", mock_feedback, mock_session)

        assert calibration.total_feedback_count == 10
        assert calibration.false_positive_count == 5
        assert calibration.false_positive_rate == 0.5


# =============================================================================
# Auto-Adjustment Tests
# =============================================================================


class TestAutoAdjustment:
    """Tests for auto-adjustment logic based on FP rate."""

    @pytest.mark.asyncio
    async def test_decreases_offset_when_high_fp_rate(self) -> None:
        """Test that risk_offset decreases when FP rate is high."""
        processor = FeedbackProcessor()

        calibration = CameraCalibration(
            id=1,
            camera_id="front_door",
            total_feedback_count=19,  # Will become 20
            false_positive_count=10,  # Will become 11 (55% > 50%)
            false_positive_rate=0.526,
            risk_offset=0,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.return_value = mock_result

        mock_feedback = MagicMock(spec=EventFeedback)
        mock_feedback.feedback_type = FeedbackType.FALSE_POSITIVE

        await processor._update_camera_calibration("front_door", mock_feedback, mock_session)

        # After adjustment: 11/20 = 0.55 > 0.5, so offset should decrease
        assert calibration.risk_offset < 0
        assert calibration.risk_offset == -OFFSET_DECREASE_STEP

    @pytest.mark.asyncio
    async def test_increases_offset_when_low_fp_rate(self) -> None:
        """Test that risk_offset increases when FP rate is low."""
        processor = FeedbackProcessor()

        calibration = CameraCalibration(
            id=1,
            camera_id="front_door",
            total_feedback_count=19,  # Will become 20
            false_positive_count=1,  # Will stay 1 (5% < 10%)
            false_positive_rate=0.052,
            risk_offset=0,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.return_value = mock_result

        mock_feedback = MagicMock(spec=EventFeedback)
        mock_feedback.feedback_type = FeedbackType.CORRECT

        await processor._update_camera_calibration("front_door", mock_feedback, mock_session)

        # After adjustment: 1/20 = 0.05 < 0.1, so offset should increase
        assert calibration.risk_offset > 0
        assert calibration.risk_offset == OFFSET_INCREASE_STEP

    @pytest.mark.asyncio
    async def test_no_adjustment_when_insufficient_feedback(self) -> None:
        """Test that no adjustment happens with insufficient feedback."""
        processor = FeedbackProcessor()

        calibration = CameraCalibration(
            id=1,
            camera_id="front_door",
            total_feedback_count=18,  # Will become 19 (< 20)
            false_positive_count=10,  # High FP rate but not enough samples
            false_positive_rate=0.556,
            risk_offset=0,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.return_value = mock_result

        mock_feedback = MagicMock(spec=EventFeedback)
        mock_feedback.feedback_type = FeedbackType.FALSE_POSITIVE

        await processor._update_camera_calibration("front_door", mock_feedback, mock_session)

        # Should not adjust because total < 20
        assert calibration.risk_offset == 0

    @pytest.mark.asyncio
    async def test_offset_clamped_at_minimum(self) -> None:
        """Test that risk_offset is clamped at MIN_RISK_OFFSET."""
        processor = FeedbackProcessor()

        calibration = CameraCalibration(
            id=1,
            camera_id="front_door",
            total_feedback_count=100,
            false_positive_count=60,  # 60% FP rate
            false_positive_rate=0.6,
            risk_offset=-28,  # Close to minimum
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.return_value = mock_result

        mock_feedback = MagicMock(spec=EventFeedback)
        mock_feedback.feedback_type = FeedbackType.FALSE_POSITIVE

        await processor._update_camera_calibration("front_door", mock_feedback, mock_session)

        # Should be clamped at -30, not go lower
        assert calibration.risk_offset >= MIN_RISK_OFFSET
        assert calibration.risk_offset == max(-30, -28 - OFFSET_DECREASE_STEP)

    @pytest.mark.asyncio
    async def test_offset_clamped_at_maximum(self) -> None:
        """Test that risk_offset is clamped at MAX_RISK_OFFSET."""
        processor = FeedbackProcessor()

        calibration = CameraCalibration(
            id=1,
            camera_id="front_door",
            total_feedback_count=100,
            false_positive_count=5,  # 5% FP rate
            false_positive_rate=0.05,
            risk_offset=28,  # Close to maximum
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.return_value = mock_result

        mock_feedback = MagicMock(spec=EventFeedback)
        mock_feedback.feedback_type = FeedbackType.CORRECT

        await processor._update_camera_calibration("front_door", mock_feedback, mock_session)

        # Should be clamped at 30, not go higher
        assert calibration.risk_offset <= MAX_RISK_OFFSET
        assert calibration.risk_offset == min(30, 28 + OFFSET_INCREASE_STEP)

    @pytest.mark.asyncio
    async def test_no_adjustment_when_moderate_fp_rate(self) -> None:
        """Test that no adjustment happens with moderate FP rate."""
        processor = FeedbackProcessor()

        calibration = CameraCalibration(
            id=1,
            camera_id="front_door",
            total_feedback_count=99,  # Will become 100
            false_positive_count=30,  # Will become 31 (31% - moderate)
            false_positive_rate=0.303,
            risk_offset=5,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.return_value = mock_result

        mock_feedback = MagicMock(spec=EventFeedback)
        mock_feedback.feedback_type = FeedbackType.FALSE_POSITIVE

        await processor._update_camera_calibration("front_door", mock_feedback, mock_session)

        # 31% is between 10% and 50%, so no adjustment
        # (0.1 < 0.31 < 0.5)
        assert calibration.risk_offset == 5  # Unchanged


# =============================================================================
# process_feedback Tests
# =============================================================================


class TestProcessFeedback:
    """Tests for process_feedback method."""

    @pytest.mark.asyncio
    async def test_process_feedback_updates_calibration(self) -> None:
        """Test that process_feedback updates camera calibration."""
        processor = FeedbackProcessor()

        calibration = CameraCalibration(
            id=1,
            camera_id="front_door",
            total_feedback_count=5,
            false_positive_count=2,
            false_positive_rate=0.4,
            risk_offset=0,
        )

        # Mock event
        mock_event = MagicMock(spec=Event)
        mock_event.id = 1
        mock_event.camera_id = "front_door"
        mock_event.risk_score = 75

        # Mock feedback
        mock_feedback = MagicMock(spec=EventFeedback)
        mock_feedback.event_id = 1
        mock_feedback.feedback_type = FeedbackType.FALSE_POSITIVE
        mock_feedback.actual_identity = None

        # Setup mock session
        mock_session = AsyncMock()

        # First call: get event
        mock_event_result = MagicMock()
        mock_event_result.scalar_one_or_none.return_value = mock_event

        # Second call: get calibration
        mock_cal_result = MagicMock()
        mock_cal_result.scalar_one_or_none.return_value = calibration

        mock_session.execute.side_effect = [mock_event_result, mock_cal_result]

        await processor.process_feedback(mock_feedback, mock_session)

        # Calibration should be updated
        assert calibration.total_feedback_count == 6
        assert calibration.false_positive_count == 3

    @pytest.mark.asyncio
    async def test_process_feedback_handles_missing_event(self) -> None:
        """Test that process_feedback handles missing event gracefully."""
        processor = FeedbackProcessor()

        # Mock feedback
        mock_feedback = MagicMock(spec=EventFeedback)
        mock_feedback.event_id = 999  # Non-existent event
        mock_feedback.feedback_type = FeedbackType.FALSE_POSITIVE

        # Setup mock session - event not found
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # Should not raise, just return early
        await processor.process_feedback(mock_feedback, mock_session)

        # Only one call (get_event), no calibration update
        assert mock_session.execute.call_count == 1


# =============================================================================
# Singleton Tests
# =============================================================================


class TestFeedbackProcessorSingleton:
    """Tests for feedback processor singleton functions."""

    def test_get_feedback_processor_creates_singleton(self) -> None:
        """Test that get_feedback_processor creates and returns singleton."""
        reset_feedback_processor()
        processor1 = get_feedback_processor()
        processor2 = get_feedback_processor()

        assert processor1 is processor2
        reset_feedback_processor()

    def test_reset_feedback_processor_clears_cache(self) -> None:
        """Test that reset_feedback_processor clears the singleton."""
        processor1 = get_feedback_processor()
        reset_feedback_processor()
        processor2 = get_feedback_processor()

        assert processor1 is not processor2
        reset_feedback_processor()


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestFeedbackProcessorEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_first_feedback_creates_calibration(self) -> None:
        """Test that first feedback for a camera creates calibration."""
        processor = FeedbackProcessor()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        mock_feedback = MagicMock(spec=EventFeedback)
        mock_feedback.feedback_type = FeedbackType.FALSE_POSITIVE

        calibration = await processor._get_or_create_calibration(mock_session, "new_camera")
        await processor._update_camera_calibration("new_camera", mock_feedback, mock_session)

        # Calibration should exist with one feedback
        mock_session.add.assert_called()

    @pytest.mark.asyncio
    async def test_fp_rate_calculation_avoids_division_by_zero(self) -> None:
        """Test that FP rate calculation handles zero total feedback."""
        processor = FeedbackProcessor()

        calibration = CameraCalibration(
            id=1,
            camera_id="front_door",
            total_feedback_count=0,  # Will become 1
            false_positive_count=0,  # Will become 1
            false_positive_rate=0.0,
            risk_offset=0,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = calibration
        mock_session.execute.return_value = mock_result

        mock_feedback = MagicMock(spec=EventFeedback)
        mock_feedback.feedback_type = FeedbackType.FALSE_POSITIVE

        await processor._update_camera_calibration("front_door", mock_feedback, mock_session)

        # Should calculate 1/1 = 1.0 without error
        assert calibration.false_positive_rate == 1.0

    @pytest.mark.asyncio
    async def test_all_feedback_types_increment_total(self) -> None:
        """Test that all feedback types increment total_feedback_count."""
        processor = FeedbackProcessor()

        for feedback_type in [
            FeedbackType.CORRECT,
            FeedbackType.ACCURATE,
            FeedbackType.FALSE_POSITIVE,
            FeedbackType.MISSED_THREAT,
            FeedbackType.SEVERITY_WRONG,
        ]:
            calibration = CameraCalibration(
                id=1,
                camera_id="test_camera",
                total_feedback_count=5,
                false_positive_count=2,
                false_positive_rate=0.4,
                risk_offset=0,
            )

            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = calibration
            mock_session.execute.return_value = mock_result

            mock_feedback = MagicMock(spec=EventFeedback)
            mock_feedback.feedback_type = feedback_type

            await processor._update_camera_calibration("test_camera", mock_feedback, mock_session)

            assert calibration.total_feedback_count == 6, (
                f"Expected 6 for {feedback_type}, got {calibration.total_feedback_count}"
            )

    @pytest.mark.asyncio
    async def test_only_false_positive_increments_fp_count(self) -> None:
        """Test that only FALSE_POSITIVE feedback increments false_positive_count."""
        processor = FeedbackProcessor()

        non_fp_types = [
            FeedbackType.CORRECT,
            FeedbackType.ACCURATE,
            FeedbackType.MISSED_THREAT,
            FeedbackType.SEVERITY_WRONG,
        ]

        for feedback_type in non_fp_types:
            calibration = CameraCalibration(
                id=1,
                camera_id="test_camera",
                total_feedback_count=5,
                false_positive_count=2,
                false_positive_rate=0.4,
                risk_offset=0,
            )

            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = calibration
            mock_session.execute.return_value = mock_result

            mock_feedback = MagicMock(spec=EventFeedback)
            mock_feedback.feedback_type = feedback_type

            await processor._update_camera_calibration("test_camera", mock_feedback, mock_session)

            assert calibration.false_positive_count == 2, (
                f"FP count changed for {feedback_type}: {calibration.false_positive_count}"
            )
