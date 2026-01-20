"""FeedbackProcessor service for processing user feedback and updating camera calibration.

This service processes user feedback on security events to improve future analysis
by adjusting per-camera risk calibration. When users report false positives or
confirm alerts, this information is used to automatically tune the camera's
risk offset.

Key behaviors:
1. Each feedback submission updates the camera's calibration record
2. False positive feedback increments false_positive_count
3. FP rate is recalculated after each feedback
4. When enough feedback is collected (>= 20 samples):
   - High FP rate (> 50%): decrease risk_offset by 5 (max -30)
   - Low FP rate (< 10%): increase risk_offset by 2 (max +30)
5. Risk offset bounds: -30 to +30

Implements NEM-3022: Implement camera calibration model and feedback-driven risk adjustment.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.camera_calibration import CameraCalibration
from backend.models.event import Event
from backend.models.event_feedback import EventFeedback, FeedbackType

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Minimum feedback samples before auto-adjustment kicks in
AUTO_ADJUST_MIN_FEEDBACK = 20

# FP rate thresholds for auto-adjustment
HIGH_FP_RATE_THRESHOLD = 0.5  # > 50% FP rate triggers decrease
LOW_FP_RATE_THRESHOLD = 0.1  # < 10% FP rate triggers increase

# Risk offset bounds
MIN_RISK_OFFSET = -30
MAX_RISK_OFFSET = 30

# Step sizes for offset adjustment
OFFSET_DECREASE_STEP = 5  # Larger step for over-alerting cameras
OFFSET_INCREASE_STEP = 2  # Smaller step for under-alerting cameras


# =============================================================================
# FeedbackProcessor Service
# =============================================================================


class FeedbackProcessor:
    """Process user feedback to improve future analysis.

    This service handles the feedback processing workflow:
    1. Receive feedback on an event
    2. Look up the associated event to get camera_id
    3. Update the camera's calibration record with feedback metrics
    4. Auto-adjust risk_offset based on FP rate trends

    The calibration adjustments help the system learn from user corrections:
    - Too many false positives? Reduce scores for that camera
    - Very few false positives? Slightly increase scores (may be under-alerting)

    Attributes:
        min_feedback_for_adjustment: Minimum feedback count before auto-adjustment
        high_fp_threshold: FP rate above which offset is decreased
        low_fp_threshold: FP rate below which offset is increased
    """

    def __init__(
        self,
        min_feedback_for_adjustment: int = AUTO_ADJUST_MIN_FEEDBACK,
        high_fp_threshold: float = HIGH_FP_RATE_THRESHOLD,
        low_fp_threshold: float = LOW_FP_RATE_THRESHOLD,
    ) -> None:
        """Initialize FeedbackProcessor with configuration.

        Args:
            min_feedback_for_adjustment: Minimum feedback samples before auto-adjustment
            high_fp_threshold: FP rate threshold for triggering offset decrease
            low_fp_threshold: FP rate threshold for triggering offset increase
        """
        self.min_feedback_for_adjustment = min_feedback_for_adjustment
        self.high_fp_threshold = high_fp_threshold
        self.low_fp_threshold = low_fp_threshold

    async def process_feedback(self, feedback: EventFeedback, session: AsyncSession) -> None:
        """Process a single feedback submission.

        This is the main entry point for feedback processing. It:
        1. Looks up the associated event
        2. Updates camera calibration based on feedback

        Args:
            feedback: The EventFeedback to process
            session: SQLAlchemy async session
        """
        # Get the event to find camera_id
        event = await self._get_event(feedback.event_id, session)
        if event is None:
            logger.warning(f"Cannot process feedback: Event {feedback.event_id} not found")
            return

        # Update camera calibration
        await self._update_camera_calibration(event.camera_id, feedback, session)

        logger.info(
            f"Processed {feedback.feedback_type} feedback for event {feedback.event_id} "
            f"(camera: {event.camera_id})"
        )

    async def _get_event(self, event_id: int, session: AsyncSession) -> Event | None:
        """Get an event by ID.

        Args:
            event_id: The event ID to look up
            session: SQLAlchemy async session

        Returns:
            Event if found, None otherwise
        """
        stmt = select(Event).where(Event.id == event_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_or_create_calibration(
        self, session: AsyncSession, camera_id: str
    ) -> CameraCalibration:
        """Get or create a calibration record for a camera.

        If no calibration exists for the camera, creates a new one with
        default values.

        Args:
            session: SQLAlchemy async session
            camera_id: Camera ID to get/create calibration for

        Returns:
            CameraCalibration record
        """
        stmt = select(CameraCalibration).where(CameraCalibration.camera_id == camera_id)
        result = await session.execute(stmt)
        calibration = result.scalar_one_or_none()

        if calibration is None:
            calibration = CameraCalibration(
                camera_id=camera_id,
                total_feedback_count=0,
                false_positive_count=0,
                false_positive_rate=0.0,
                risk_offset=0,
                model_weights={},
                suppress_patterns=[],
            )
            session.add(calibration)
            await session.flush()
            logger.info(f"Created new calibration record for camera {camera_id}")

        return calibration

    async def _update_camera_calibration(
        self,
        camera_id: str,
        feedback: EventFeedback,
        session: AsyncSession,
    ) -> None:
        """Update camera-specific calibration based on feedback.

        This method:
        1. Gets or creates the calibration record
        2. Increments feedback counts
        3. Recalculates FP rate
        4. Auto-adjusts risk_offset if enough samples exist

        Args:
            camera_id: Camera ID to update calibration for
            feedback: The feedback to process
            session: SQLAlchemy async session
        """
        calibration = await self._get_or_create_calibration(session, camera_id)

        # Increment total feedback count
        calibration.total_feedback_count += 1

        # Increment FP count if this is a false positive
        if feedback.feedback_type == FeedbackType.FALSE_POSITIVE:
            calibration.false_positive_count += 1

        # Recalculate FP rate
        calibration.false_positive_rate = (
            calibration.false_positive_count / calibration.total_feedback_count
        )

        # Auto-adjust offset if we have enough feedback
        if calibration.total_feedback_count >= self.min_feedback_for_adjustment:
            self._auto_adjust_offset(calibration)

        logger.debug(
            f"Updated calibration for camera {camera_id}: "
            f"total={calibration.total_feedback_count}, "
            f"fp_count={calibration.false_positive_count}, "
            f"fp_rate={calibration.false_positive_rate:.2f}, "
            f"offset={calibration.risk_offset}"
        )

    def _auto_adjust_offset(self, calibration: CameraCalibration) -> None:
        """Auto-adjust risk offset based on FP rate.

        The adjustment logic:
        - If FP rate > 50%: Camera over-alerts, decrease offset by 5
        - If FP rate < 10%: Camera under-alerts, increase offset by 2

        The asymmetric step sizes reflect that:
        - Over-alerting (false positives) is more disruptive to users
        - Under-alerting is less immediately obvious but still needs correction

        Args:
            calibration: CameraCalibration record to adjust
        """
        if calibration.false_positive_rate > self.high_fp_threshold:
            # Camera over-alerts, reduce scores
            new_offset = calibration.risk_offset - OFFSET_DECREASE_STEP
            calibration.risk_offset = max(MIN_RISK_OFFSET, new_offset)
            logger.info(
                f"High FP rate ({calibration.false_positive_rate:.1%}) for camera "
                f"{calibration.camera_id}, decreased offset to {calibration.risk_offset}"
            )
        elif calibration.false_positive_rate < self.low_fp_threshold:
            # Camera under-alerts, increase scores
            new_offset = calibration.risk_offset + OFFSET_INCREASE_STEP
            calibration.risk_offset = min(MAX_RISK_OFFSET, new_offset)
            logger.info(
                f"Low FP rate ({calibration.false_positive_rate:.1%}) for camera "
                f"{calibration.camera_id}, increased offset to {calibration.risk_offset}"
            )


# =============================================================================
# Singleton Instance
# =============================================================================

_feedback_processor: FeedbackProcessor | None = None


def get_feedback_processor() -> FeedbackProcessor:
    """Get the singleton FeedbackProcessor instance.

    Returns:
        FeedbackProcessor singleton instance
    """
    global _feedback_processor  # noqa: PLW0603
    if _feedback_processor is None:
        _feedback_processor = FeedbackProcessor()
    return _feedback_processor


def reset_feedback_processor() -> None:
    """Reset the singleton FeedbackProcessor instance.

    Useful for testing to ensure clean state.
    """
    global _feedback_processor  # noqa: PLW0603
    _feedback_processor = None
