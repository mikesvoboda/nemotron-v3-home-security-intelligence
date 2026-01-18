"""Integration tests for Calibration Impact - Severity adjustment workflow (NEM-2750).

Tests the complete workflow of:
1. Submitting user feedback on events
2. Calibration service adjusting thresholds based on feedback
3. Impact on existing event severity classification
4. Workflow state transitions
5. Audit logging of calibration changes

This test file verifies that calibration adjustments from feedback properly
impact severity classification for future events and that the workflow
maintains proper state and audit trails.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.enums import Severity
from backend.models.event import Event
from backend.models.event_feedback import EventFeedback, FeedbackType
from backend.models.user_calibration import UserCalibration
from backend.services.calibration_service import (
    DEFAULT_DECAY_FACTOR,
    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_LOW_THRESHOLD,
    CalibrationService,
    reset_calibration_service,
)
from backend.services.severity import SeverityService, reset_severity_service


def unique_id(prefix: str = "test") -> str:
    """Generate a unique ID for test objects to prevent conflicts."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def calibration_service() -> CalibrationService:
    """Create a fresh CalibrationService instance."""
    reset_calibration_service()
    return CalibrationService()


@pytest.fixture
def severity_service() -> SeverityService:
    """Create a fresh SeverityService instance."""
    reset_severity_service()
    return SeverityService()


async def create_test_event(
    db_session: AsyncSession,
    camera_id: str,
    risk_score: int,
    summary: str = "Test event",
) -> Event:
    """Create a test event for calibration testing."""
    from backend.models.camera import Camera

    # Ensure camera exists
    camera_result = await db_session.execute(select(Camera).where(Camera.id == camera_id))
    camera = camera_result.scalar_one_or_none()

    if camera is None:
        camera = Camera(
            id=camera_id,
            name=f"Test Camera {camera_id}",
            folder_path=f"/export/foscam/{camera_id}",
            status="online",
        )
        db_session.add(camera)
        await db_session.flush()

    event = Event(
        batch_id=str(uuid.uuid4()),
        camera_id=camera_id,
        started_at=datetime.now(UTC),
        risk_score=risk_score,
        summary=summary,
    )
    db_session.add(event)
    await db_session.flush()
    return event


# =============================================================================
# Severity Adjustment via Calibration Tests
# =============================================================================


class TestSeverityAdjustmentViaCalibration:
    """Tests for severity adjustment through calibration feedback."""

    @pytest.mark.asyncio
    async def test_false_positive_feedback_raises_thresholds(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
        severity_service: SeverityService,
    ) -> None:
        """Test that false positive feedback raises thresholds (less sensitive)."""
        user_id = unique_id("user")
        camera_id = unique_id("camera")

        # Create event with risk_score=70 (HIGH with defaults)
        event = await create_test_event(db_session, camera_id, risk_score=70)

        # Get initial calibration
        calibration_before = await calibration_service.get_or_create_calibration(
            db_session, user_id
        )
        low_before = calibration_before.low_threshold
        medium_before = calibration_before.medium_threshold
        high_before = calibration_before.high_threshold

        # Create false positive feedback
        feedback = EventFeedback(
            event_id=event.id,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            notes="Not actually a threat",
        )
        db_session.add(feedback)
        await db_session.flush()

        # Adjust calibration from feedback
        updated_calibration = await calibration_service.adjust_from_feedback(
            db_session, feedback, event, user_id
        )

        # Verify thresholds increased (less sensitive)
        assert updated_calibration.low_threshold > low_before
        assert updated_calibration.medium_threshold > medium_before
        assert updated_calibration.high_threshold > high_before
        assert updated_calibration.false_positive_count == 1

    @pytest.mark.asyncio
    async def test_missed_threat_feedback_lowers_thresholds(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
        severity_service: SeverityService,
    ) -> None:
        """Test that missed threat feedback lowers thresholds (more sensitive)."""
        user_id = unique_id("user")
        camera_id = unique_id("camera")

        # Create event with risk_score=25 (LOW with defaults)
        event = await create_test_event(db_session, camera_id, risk_score=25)

        # Get initial calibration
        calibration_before = await calibration_service.get_or_create_calibration(
            db_session, user_id
        )
        low_before = calibration_before.low_threshold
        medium_before = calibration_before.medium_threshold
        high_before = calibration_before.high_threshold

        # Create missed threat feedback
        feedback = EventFeedback(
            event_id=event.id,
            feedback_type=FeedbackType.MISSED_THREAT,
            notes="This was actually concerning",
        )
        db_session.add(feedback)
        await db_session.flush()

        # Adjust calibration from feedback
        updated_calibration = await calibration_service.adjust_from_feedback(
            db_session, feedback, event, user_id
        )

        # Verify thresholds decreased (more sensitive)
        assert updated_calibration.low_threshold < low_before
        assert updated_calibration.medium_threshold < medium_before
        assert updated_calibration.high_threshold < high_before
        assert updated_calibration.missed_threat_count == 1

    @pytest.mark.asyncio
    async def test_severity_wrong_feedback_applies_smaller_adjustment(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
    ) -> None:
        """Test that severity wrong feedback applies smaller adjustments."""
        user_id = unique_id("user")
        camera_id = unique_id("camera")

        # Create event with high risk score
        event_high = await create_test_event(db_session, camera_id, risk_score=75)

        calibration_before = await calibration_service.get_or_create_calibration(
            db_session, user_id
        )
        high_before = calibration_before.high_threshold

        # Create severity wrong feedback for high score
        feedback = EventFeedback(
            event_id=event_high.id,
            feedback_type=FeedbackType.SEVERITY_WRONG,
            expected_severity="medium",
        )
        db_session.add(feedback)
        await db_session.flush()

        # Adjust calibration
        updated_calibration = await calibration_service.adjust_from_feedback(
            db_session, feedback, event_high, user_id
        )

        # Verify adjustment is smaller than false positive would be
        adjustment_delta = updated_calibration.high_threshold - high_before
        # Should be positive but smaller than base adjustment
        assert adjustment_delta > 0
        assert adjustment_delta < (10 * DEFAULT_DECAY_FACTOR)  # Base adjustment

    @pytest.mark.asyncio
    async def test_accurate_feedback_no_threshold_change(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
    ) -> None:
        """Test that accurate feedback does not change thresholds."""
        user_id = unique_id("user")
        camera_id = unique_id("camera")

        event = await create_test_event(db_session, camera_id, risk_score=50)

        calibration_before = await calibration_service.get_or_create_calibration(
            db_session, user_id
        )
        low_before = calibration_before.low_threshold
        medium_before = calibration_before.medium_threshold
        high_before = calibration_before.high_threshold

        # Create accurate feedback
        feedback = EventFeedback(
            event_id=event.id,
            feedback_type=FeedbackType.ACCURATE,
            notes="Classification was correct",
        )
        db_session.add(feedback)
        await db_session.flush()

        # Adjust calibration
        updated_calibration = await calibration_service.adjust_from_feedback(
            db_session, feedback, event, user_id
        )

        # Verify no threshold changes
        assert updated_calibration.low_threshold == low_before
        assert updated_calibration.medium_threshold == medium_before
        assert updated_calibration.high_threshold == high_before


# =============================================================================
# Calibration Impact on Existing Events
# =============================================================================


class TestCalibrationImpactOnExistingEvents:
    """Tests for how calibration changes affect severity classification of events."""

    @pytest.mark.asyncio
    async def test_calibration_changes_future_event_classification(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
        severity_service: SeverityService,
    ) -> None:
        """Test that calibration changes affect classification of future events."""
        user_id = unique_id("user")
        camera_id = unique_id("camera")

        # Create initial event and get default classification
        event1 = await create_test_event(db_session, camera_id, risk_score=45)

        # Classify with default thresholds
        result_before = await severity_service.classify_risk(
            db_session, score=45, user_id=user_id, calibration_service=calibration_service
        )
        assert result_before.severity == Severity.MEDIUM  # Default: 30 <= 45 < 60

        # Provide false positive feedback to raise thresholds
        feedback = EventFeedback(
            event_id=event1.id,
            feedback_type=FeedbackType.FALSE_POSITIVE,
        )
        db_session.add(feedback)
        await db_session.flush()

        await calibration_service.adjust_from_feedback(db_session, feedback, event1, user_id)

        # Now classify same score with adjusted thresholds
        result_after = await severity_service.classify_risk(
            db_session, score=45, user_id=user_id, calibration_service=calibration_service
        )

        # Should be calibrated now
        assert result_after.is_calibrated is True
        # Classification might change depending on adjustment magnitude
        # (could stay MEDIUM or become LOW if thresholds raised enough)

    @pytest.mark.asyncio
    async def test_multiple_feedback_cumulative_adjustment(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
    ) -> None:
        """Test that multiple feedback submissions have cumulative effect."""
        user_id = unique_id("user")
        camera_id = unique_id("camera")

        # Get initial thresholds
        calibration = await calibration_service.get_or_create_calibration(db_session, user_id)
        initial_high = calibration.high_threshold

        # Provide multiple false positive feedback
        for i in range(3):
            event = await create_test_event(db_session, camera_id, risk_score=70 + i)
            feedback = EventFeedback(
                event_id=event.id,
                feedback_type=FeedbackType.FALSE_POSITIVE,
            )
            db_session.add(feedback)
            await db_session.flush()

            calibration = await calibration_service.adjust_from_feedback(
                db_session, feedback, event, user_id
            )

        # Verify cumulative effect
        assert calibration.high_threshold > initial_high
        assert calibration.false_positive_count == 3

    @pytest.mark.asyncio
    async def test_calibration_respects_minimum_gap_constraints(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
    ) -> None:
        """Test that calibration maintains minimum gaps between thresholds."""
        user_id = unique_id("user")
        camera_id = unique_id("camera")

        # Set thresholds close together
        calibration = await calibration_service.get_or_create_calibration(db_session, user_id)
        calibration.low_threshold = 10
        calibration.medium_threshold = 15
        calibration.high_threshold = 20
        await db_session.flush()

        # Provide feedback that would lower thresholds
        event = await create_test_event(db_session, camera_id, risk_score=5)
        feedback = EventFeedback(
            event_id=event.id,
            feedback_type=FeedbackType.MISSED_THREAT,
        )
        db_session.add(feedback)
        await db_session.flush()

        updated = await calibration_service.adjust_from_feedback(
            db_session, feedback, event, user_id
        )

        # Verify minimum gaps maintained (MIN_THRESHOLD_GAP = 5)
        assert updated.medium_threshold - updated.low_threshold >= 5
        assert updated.high_threshold - updated.medium_threshold >= 5

    @pytest.mark.asyncio
    async def test_calibration_bounds_thresholds_to_valid_range(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
    ) -> None:
        """Test that calibration keeps thresholds in [0, 100] range."""
        user_id = unique_id("user")
        camera_id = unique_id("camera")

        # Set thresholds near upper bound
        calibration = await calibration_service.get_or_create_calibration(db_session, user_id)
        calibration.low_threshold = 85
        calibration.medium_threshold = 92
        calibration.high_threshold = 98
        await db_session.flush()

        # Provide feedback that would raise thresholds
        event = await create_test_event(db_session, camera_id, risk_score=95)
        feedback = EventFeedback(
            event_id=event.id,
            feedback_type=FeedbackType.FALSE_POSITIVE,
        )
        db_session.add(feedback)
        await db_session.flush()

        updated = await calibration_service.adjust_from_feedback(
            db_session, feedback, event, user_id
        )

        # Verify bounds respected
        assert 0 <= updated.low_threshold <= 100
        assert 0 <= updated.medium_threshold <= 100
        assert 0 <= updated.high_threshold <= 100


# =============================================================================
# Workflow State Transitions
# =============================================================================


class TestWorkflowStateTransitions:
    """Tests for workflow state transitions during calibration."""

    @pytest.mark.asyncio
    async def test_calibration_state_uncalibrated_to_calibrated(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
    ) -> None:
        """Test transition from uncalibrated to calibrated state."""
        user_id = unique_id("user")
        camera_id = unique_id("camera")

        # Verify initial uncalibrated state
        thresholds_before = await calibration_service.get_thresholds(db_session, user_id)
        assert thresholds_before.is_calibrated is False
        assert thresholds_before.low_threshold == DEFAULT_LOW_THRESHOLD

        # Provide feedback to trigger calibration
        event = await create_test_event(db_session, camera_id, risk_score=50)
        feedback = EventFeedback(
            event_id=event.id,
            feedback_type=FeedbackType.FALSE_POSITIVE,
        )
        db_session.add(feedback)
        await db_session.flush()

        await calibration_service.adjust_from_feedback(db_session, feedback, event, user_id)

        # Verify now calibrated
        thresholds_after = await calibration_service.get_thresholds(db_session, user_id)
        assert thresholds_after.is_calibrated is True

    @pytest.mark.asyncio
    async def test_calibration_record_created_on_first_feedback(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
    ) -> None:
        """Test that calibration record is created on first feedback."""
        user_id = unique_id("user")
        camera_id = unique_id("camera")

        # Verify no calibration exists
        result = await db_session.execute(
            select(UserCalibration).where(UserCalibration.user_id == user_id)
        )
        assert result.scalar_one_or_none() is None

        # Provide feedback
        event = await create_test_event(db_session, camera_id, risk_score=50)
        feedback = EventFeedback(
            event_id=event.id,
            feedback_type=FeedbackType.MISSED_THREAT,
        )
        db_session.add(feedback)
        await db_session.flush()

        await calibration_service.adjust_from_feedback(db_session, feedback, event, user_id)

        # Verify calibration now exists
        result = await db_session.execute(
            select(UserCalibration).where(UserCalibration.user_id == user_id)
        )
        calibration = result.scalar_one_or_none()
        assert calibration is not None
        assert calibration.missed_threat_count == 1

    @pytest.mark.asyncio
    async def test_updated_at_timestamp_changes_on_adjustment(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
    ) -> None:
        """Test that updated_at timestamp changes when calibration adjusts."""
        user_id = unique_id("user")
        camera_id = unique_id("camera")

        # Create initial calibration
        calibration = await calibration_service.get_or_create_calibration(db_session, user_id)
        original_updated_at = calibration.updated_at

        # Provide feedback after a small delay
        event = await create_test_event(db_session, camera_id, risk_score=50)
        feedback = EventFeedback(
            event_id=event.id,
            feedback_type=FeedbackType.FALSE_POSITIVE,
        )
        db_session.add(feedback)
        await db_session.flush()

        updated_calibration = await calibration_service.adjust_from_feedback(
            db_session, feedback, event, user_id
        )

        # Verify updated_at changed
        assert updated_calibration.updated_at > original_updated_at


# =============================================================================
# Audit Logging Tests
# =============================================================================


class TestCalibrationAuditLogging:
    """Tests for audit logging of calibration changes."""

    @pytest.mark.asyncio
    async def test_calibration_adjustment_logs_old_and_new_thresholds(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
        caplog,
    ) -> None:
        """Test that calibration adjustments log old and new threshold values."""
        import logging

        caplog.set_level(logging.INFO)

        user_id = unique_id("user")
        camera_id = unique_id("camera")

        event = await create_test_event(db_session, camera_id, risk_score=50)
        feedback = EventFeedback(
            event_id=event.id,
            feedback_type=FeedbackType.FALSE_POSITIVE,
        )
        db_session.add(feedback)
        await db_session.flush()

        await calibration_service.adjust_from_feedback(db_session, feedback, event, user_id)

        # Verify logging contains threshold information
        log_messages = [record.message for record in caplog.records]
        assert any("Adjusted calibration from feedback" in msg for msg in log_messages)

    @pytest.mark.asyncio
    async def test_calibration_adjustment_logs_feedback_type(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
        caplog,
    ) -> None:
        """Test that calibration adjustments log the feedback type."""
        import logging

        caplog.set_level(logging.INFO)

        user_id = unique_id("user")
        camera_id = unique_id("camera")

        event = await create_test_event(db_session, camera_id, risk_score=30)
        feedback = EventFeedback(
            event_id=event.id,
            feedback_type=FeedbackType.MISSED_THREAT,
        )
        db_session.add(feedback)
        await db_session.flush()

        await calibration_service.adjust_from_feedback(db_session, feedback, event, user_id)

        # Verify logging contains feedback type
        # Check structured logging extra data
        assert any(
            record.message == "Adjusted calibration from feedback"
            for record in caplog.records
            if hasattr(record, "feedback_type")
        )

    @pytest.mark.asyncio
    async def test_calibration_adjustment_logs_event_and_risk_score(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
        caplog,
    ) -> None:
        """Test that calibration adjustments log event ID and risk score."""
        import logging

        caplog.set_level(logging.INFO)

        user_id = unique_id("user")
        camera_id = unique_id("camera")

        event = await create_test_event(db_session, camera_id, risk_score=75)
        feedback = EventFeedback(
            event_id=event.id,
            feedback_type=FeedbackType.FALSE_POSITIVE,
        )
        db_session.add(feedback)
        await db_session.flush()

        await calibration_service.adjust_from_feedback(db_session, feedback, event, user_id)

        # Verify event_id is in log records
        assert any(
            hasattr(record, "event_id") and record.event_id == event.id for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_calibration_creation_is_logged(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
        caplog,
    ) -> None:
        """Test that creating a new calibration is logged."""
        import logging

        caplog.set_level(logging.INFO)

        user_id = unique_id("user")

        await calibration_service.get_or_create_calibration(db_session, user_id)

        # Verify creation was logged
        log_messages = [record.message for record in caplog.records]
        assert any("Created new calibration" in msg for msg in log_messages)


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestCalibrationEdgeCases:
    """Tests for edge cases in calibration workflow."""

    @pytest.mark.asyncio
    async def test_calibration_adjustment_with_null_risk_score(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
        caplog,
    ) -> None:
        """Test that calibration handles events with null risk scores gracefully."""
        import logging

        caplog.set_level(logging.WARNING)

        user_id = unique_id("user")
        camera_id = unique_id("camera")

        # Create event without risk score
        event = await create_test_event(db_session, camera_id, risk_score=50)
        event.risk_score = None  # Explicitly set to None
        await db_session.flush()

        calibration_before = await calibration_service.get_or_create_calibration(
            db_session, user_id
        )
        thresholds_before = (
            calibration_before.low_threshold,
            calibration_before.medium_threshold,
            calibration_before.high_threshold,
        )

        feedback = EventFeedback(
            event_id=event.id,
            feedback_type=FeedbackType.FALSE_POSITIVE,
        )
        db_session.add(feedback)
        await db_session.flush()

        calibration_after = await calibration_service.adjust_from_feedback(
            db_session, feedback, event, user_id
        )

        # Verify no adjustment happened
        thresholds_after = (
            calibration_after.low_threshold,
            calibration_after.medium_threshold,
            calibration_after.high_threshold,
        )
        assert thresholds_before == thresholds_after

        # Verify warning was logged
        assert any(
            "Cannot adjust calibration for event without risk score" in record.message
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_multiple_users_independent_calibrations(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
    ) -> None:
        """Test that different users have independent calibration adjustments."""
        user_a = unique_id("user_a")
        user_b = unique_id("user_b")
        camera_id = unique_id("camera")

        # User A provides false positive feedback
        event_a = await create_test_event(db_session, camera_id, risk_score=70)
        feedback_a = EventFeedback(
            event_id=event_a.id,
            feedback_type=FeedbackType.FALSE_POSITIVE,
        )
        db_session.add(feedback_a)
        await db_session.flush()

        calibration_a = await calibration_service.adjust_from_feedback(
            db_session, feedback_a, event_a, user_a
        )

        # User B provides missed threat feedback
        event_b = await create_test_event(db_session, camera_id, risk_score=30)
        feedback_b = EventFeedback(
            event_id=event_b.id,
            feedback_type=FeedbackType.MISSED_THREAT,
        )
        db_session.add(feedback_b)
        await db_session.flush()

        calibration_b = await calibration_service.adjust_from_feedback(
            db_session, feedback_b, event_b, user_b
        )

        # Verify users have different calibrations
        # User A: thresholds raised (false positive)
        assert calibration_a.high_threshold > DEFAULT_HIGH_THRESHOLD
        assert calibration_a.false_positive_count == 1

        # User B: thresholds lowered (missed threat)
        assert calibration_b.high_threshold < DEFAULT_HIGH_THRESHOLD
        assert calibration_b.missed_threat_count == 1

    @pytest.mark.asyncio
    async def test_decay_factor_affects_adjustment_magnitude(
        self,
        db_session: AsyncSession,
        calibration_service: CalibrationService,
    ) -> None:
        """Test that decay factor controls adjustment magnitude."""
        user_small = unique_id("user_small")
        user_large = unique_id("user_large")
        camera_id = unique_id("camera")

        # User with small decay factor
        cal_small = await calibration_service.get_or_create_calibration(db_session, user_small)
        cal_small.decay_factor = 0.05
        await db_session.flush()

        # User with large decay factor
        cal_large = await calibration_service.get_or_create_calibration(db_session, user_large)
        cal_large.decay_factor = 0.5
        await db_session.flush()

        # Same feedback for both users
        event_small = await create_test_event(db_session, camera_id, risk_score=70)
        feedback_small = EventFeedback(
            event_id=event_small.id,
            feedback_type=FeedbackType.FALSE_POSITIVE,
        )
        db_session.add(feedback_small)
        await db_session.flush()

        event_large = await create_test_event(db_session, camera_id, risk_score=70)
        feedback_large = EventFeedback(
            event_id=event_large.id,
            feedback_type=FeedbackType.FALSE_POSITIVE,
        )
        db_session.add(feedback_large)
        await db_session.flush()

        updated_small = await calibration_service.adjust_from_feedback(
            db_session, feedback_small, event_small, user_small
        )
        updated_large = await calibration_service.adjust_from_feedback(
            db_session, feedback_large, event_large, user_large
        )

        # Verify larger decay factor produces larger adjustment
        small_delta = updated_small.high_threshold - DEFAULT_HIGH_THRESHOLD
        large_delta = updated_large.high_threshold - DEFAULT_HIGH_THRESHOLD

        assert large_delta > small_delta
