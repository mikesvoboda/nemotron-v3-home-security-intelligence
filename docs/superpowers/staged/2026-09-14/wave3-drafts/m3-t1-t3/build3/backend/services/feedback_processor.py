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

Enhanced features (NEM-3332):
- Creates/updates household members from actual_identity feedback
- Records model failures to adjust model weights for specific cameras
- Updates avg_user_suggested_score from suggested_score feedback
- Returns event with detections for downstream processing

Implements:
- NEM-3022: Implement camera calibration model and feedback-driven risk adjustment
- NEM-3332: Build FeedbackProcessor service
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.camera_calibration import CameraCalibration
from backend.models.event import Event
from backend.models.event_feedback import EventFeedback, FeedbackType
from backend.models.household import HouseholdMember, MemberRole, TrustLevel

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

# Model weight adjustment constants
MODEL_WEIGHT_DECAY = 0.1  # How much to reduce weight on each failure
MIN_MODEL_WEIGHT = 0.1  # Minimum model weight (never disable completely)
DEFAULT_MODEL_WEIGHT = 1.0  # Default weight for models with no failures


# =============================================================================
# FeedbackProcessor Service
# =============================================================================


class FeedbackProcessor:
    """Process user feedback to improve future analysis.

    This service handles the feedback processing workflow:
    1. Receive feedback on an event
    2. Look up the associated event to get camera_id (with detections loaded)
    3. Update the camera's calibration record with feedback metrics
    4. Auto-adjust risk_offset based on FP rate trends
    5. Process actual_identity to create/update household members
    6. Record model failures to adjust model weights

    The calibration adjustments help the system learn from user corrections:
    - Too many false positives? Reduce scores for that camera
    - Very few false positives? Slightly increase scores (may be under-alerting)
    - Specific models failing? Reduce their influence for that camera

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

    async def process_feedback(
        self, feedback: EventFeedback, session: AsyncSession
    ) -> Event | None:
        """Process a single feedback submission.

        This is the main entry point for feedback processing. It:
        1. Looks up the associated event with detections
        2. Updates camera calibration based on feedback
        3. Creates/updates household members if actual_identity is provided
        4. Records model failures for analysis

        Args:
            feedback: The EventFeedback to process
            session: SQLAlchemy async session

        Returns:
            The Event with detections loaded, or None if event not found
        """
        # Get the event with detections to find camera_id
        event = await self._get_event_with_detections(feedback.event_id, session)
        if event is None:
            logger.warning(f"Cannot process feedback: Event {feedback.event_id} not found")
            return None

        # Update camera calibration
        calibration = await self._update_camera_calibration(event.camera_id, feedback, session)

        # Process model failures if provided
        if feedback.model_failures:
            self._record_model_failures(calibration, feedback.model_failures)

        # Process actual_identity for household member creation/update
        actual_identity = getattr(feedback, "actual_identity", None)
        if actual_identity and actual_identity.strip():
            await self._process_household_member(actual_identity.strip(), session)

        logger.info(
            f"Processed {feedback.feedback_type} feedback for event {feedback.event_id} "
            f"(camera: {event.camera_id})"
        )

        return event

    async def _get_event_with_detections(
        self, event_id: int, session: AsyncSession
    ) -> Event | None:
        """Get an event by ID with detections eagerly loaded.

        Uses selectinload to efficiently load the detections relationship,
        avoiding N+1 query issues.

        Args:
            event_id: The event ID to look up
            session: SQLAlchemy async session

        Returns:
            Event with detections loaded if found, None otherwise
        """
        stmt = select(Event).options(selectinload(Event.detections)).where(Event.id == event_id)
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
    ) -> CameraCalibration:
        """Update camera-specific calibration based on feedback.

        This method:
        1. Gets or creates the calibration record
        2. Increments feedback counts
        3. Recalculates FP rate
        4. Updates avg_user_suggested_score if provided
        5. Auto-adjusts risk_offset if enough samples exist

        Args:
            camera_id: Camera ID to update calibration for
            feedback: The feedback to process
            session: SQLAlchemy async session

        Returns:
            Updated CameraCalibration record
        """
        calibration = await self._get_or_create_calibration(session, camera_id)

        # Track previous count for running average calculation
        previous_count = calibration.total_feedback_count

        # Increment total feedback count
        calibration.total_feedback_count += 1

        # Increment FP count if this is a false positive
        if feedback.feedback_type == FeedbackType.FALSE_POSITIVE:
            calibration.false_positive_count += 1

        # Recalculate FP rate
        calibration.false_positive_rate = (
            calibration.false_positive_count / calibration.total_feedback_count
        )

        # Update avg_user_suggested_score if provided
        suggested_score = getattr(feedback, "suggested_score", None)
        if suggested_score is not None:
            self._update_avg_suggested_score(calibration, suggested_score, previous_count)

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

        return calibration

    def _update_avg_suggested_score(
        self,
        calibration: CameraCalibration,
        suggested_score: int,
        previous_count: int,
    ) -> None:
        """Update the running average of user-suggested scores.

        Uses incremental mean formula: new_avg = (old_avg * n + new_value) / (n + 1)

        Args:
            calibration: CameraCalibration to update
            suggested_score: New suggested score from user
            previous_count: Feedback count before this submission
        """
        if calibration.avg_user_suggested_score is None:
            # First suggested score
            calibration.avg_user_suggested_score = float(suggested_score)
        else:
            # Incremental mean update
            old_avg = calibration.avg_user_suggested_score
            new_count = previous_count + 1
            calibration.avg_user_suggested_score = (
                old_avg * previous_count + suggested_score
            ) / new_count

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

    def _record_model_failures(
        self,
        calibration: CameraCalibration,
        model_failures: list[str],
    ) -> None:
        """Record model failures by adjusting model weights.

        When a user reports specific AI models that failed, we reduce
        those models' influence for this camera by decreasing their weight.

        Args:
            calibration: CameraCalibration to update
            model_failures: List of model names that failed
        """
        if not model_failures:
            return

        # Ensure model_weights is a mutable dict
        if calibration.model_weights is None:
            calibration.model_weights = {}

        for model_name in model_failures:
            current_weight = calibration.model_weights.get(model_name, DEFAULT_MODEL_WEIGHT)
            new_weight = max(MIN_MODEL_WEIGHT, current_weight - MODEL_WEIGHT_DECAY)
            calibration.model_weights[model_name] = new_weight

            logger.debug(
                f"Reduced weight for model '{model_name}' on camera "
                f"{calibration.camera_id}: {current_weight:.2f} -> {new_weight:.2f}"
            )

    async def _process_household_member(
        self,
        identity_name: str,
        session: AsyncSession,
    ) -> HouseholdMember:
        """Process actual_identity to create or find a household member.

        When a user identifies a person in feedback (e.g., "Mike (neighbor)"),
        this method:
        1. Searches for an existing member with matching name
        2. Creates a new member if none exists
        3. New members default to FREQUENT_VISITOR role with PARTIAL trust

        Args:
            identity_name: The identity string from feedback (e.g., "Mike (neighbor)")
            session: SQLAlchemy async session

        Returns:
            The found or created HouseholdMember
        """
        # Extract the base name (before any parenthetical notes)
        base_name = identity_name.split("(")[0].strip()

        # Search for existing member with case-insensitive match
        stmt = select(HouseholdMember).where(
            func.lower(HouseholdMember.name) == func.lower(base_name)
        )
        result = await session.execute(stmt)
        existing_member = result.scalar_one_or_none()

        if existing_member:
            logger.debug(f"Found existing household member: {existing_member.name}")
            return existing_member

        # Create new household member with defaults
        new_member = HouseholdMember(
            name=base_name,
            role=MemberRole.FREQUENT_VISITOR,
            trusted_level=TrustLevel.PARTIAL,
            notes=f"Auto-created from feedback identity: {identity_name}",
        )
        session.add(new_member)
        await session.flush()

        logger.info(
            f"Created new household member '{base_name}' from feedback identity '{identity_name}'"
        )

        return new_member


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
