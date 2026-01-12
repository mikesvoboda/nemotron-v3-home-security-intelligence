"""Calibration service for adaptive threshold adjustment based on user feedback.

This module provides the CalibrationService class for adjusting risk thresholds
based on user feedback (false positives and missed detections).

Algorithm:
    - On False Positive Feedback: Raise thresholds (less sensitive)
      new_threshold = old_threshold + (decay_factor * adjustment)
    - On Missed Detection Feedback: Lower thresholds (more sensitive)
      new_threshold = old_threshold - (decay_factor * adjustment)

Constraints:
    - Thresholds must stay in range [0, 100]
    - Ordering must be maintained: low < medium < high
    - Adjustment should be gradual (default decay_factor=0.1)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import TYPE_CHECKING, NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logging import get_logger
from backend.models.event_feedback import EventFeedback, FeedbackType
from backend.models.user_calibration import UserCalibration

if TYPE_CHECKING:
    from backend.models.event import Event

logger = get_logger(__name__)

# Default thresholds for new calibrations
DEFAULT_LOW_THRESHOLD = 30
DEFAULT_MEDIUM_THRESHOLD = 60
DEFAULT_HIGH_THRESHOLD = 85
DEFAULT_DECAY_FACTOR = 0.1

# Minimum gaps between thresholds to maintain ordering
MIN_THRESHOLD_GAP = 5


@dataclass(frozen=True, slots=True)
class ThresholdAdjustment:
    """Result of calculating threshold adjustments.

    Attributes:
        low_delta: Change to apply to low_threshold
        medium_delta: Change to apply to medium_threshold
        high_delta: Change to apply to high_threshold
        feedback_type: Type of feedback that triggered the adjustment
        original_risk_score: The risk score of the event being adjusted for
    """

    low_delta: int
    medium_delta: int
    high_delta: int
    feedback_type: FeedbackType
    original_risk_score: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "low_delta": self.low_delta,
            "medium_delta": self.medium_delta,
            "high_delta": self.high_delta,
            "feedback_type": self.feedback_type.value,
            "original_risk_score": self.original_risk_score,
        }


class CalibrationThresholds(NamedTuple):
    """Calibration thresholds for severity classification.

    Attributes:
        low_threshold: Upper bound for LOW severity (exclusive).
            Scores < low_threshold are LOW.
        medium_threshold: Upper bound for MEDIUM severity (exclusive).
            Scores >= low_threshold and < medium_threshold are MEDIUM.
        high_threshold: Upper bound for HIGH severity (exclusive).
            Scores >= medium_threshold and < high_threshold are HIGH.
            Scores >= high_threshold are CRITICAL.
        is_calibrated: True if the user has provided any feedback, False otherwise.
    """

    low_threshold: int
    medium_threshold: int
    high_threshold: int
    is_calibrated: bool


class CalibrationService:
    """Service for calibrating risk thresholds based on user feedback.

    This service provides methods for:
    - Creating default calibrations for new users
    - Adjusting thresholds based on feedback
    - Resetting calibrations to defaults

    The adjustment algorithm uses the event's risk score to determine
    which threshold(s) should be adjusted and by how much.
    """

    def __init__(
        self,
        default_low: int = DEFAULT_LOW_THRESHOLD,
        default_medium: int = DEFAULT_MEDIUM_THRESHOLD,
        default_high: int = DEFAULT_HIGH_THRESHOLD,
        default_decay: float = DEFAULT_DECAY_FACTOR,
    ) -> None:
        """Initialize the calibration service.

        Args:
            default_low: Default low threshold for new calibrations
            default_medium: Default medium threshold for new calibrations
            default_high: Default high threshold for new calibrations
            default_decay: Default decay factor for new calibrations
        """
        self.default_low = default_low
        self.default_medium = default_medium
        self.default_high = default_high
        self.default_decay = default_decay

    async def get_or_create_calibration(
        self,
        db: AsyncSession,
        user_id: str = "default",
    ) -> UserCalibration:
        """Get existing calibration or create a new one with defaults.

        Args:
            db: Database session
            user_id: User identifier (defaults to "default" for single-user systems)

        Returns:
            UserCalibration instance for the user
        """
        stmt = select(UserCalibration).where(UserCalibration.user_id == user_id)
        result = await db.execute(stmt)
        calibration = result.scalar_one_or_none()

        if calibration is not None:
            return calibration

        # Create new calibration with defaults
        calibration = UserCalibration(
            user_id=user_id,
            low_threshold=self.default_low,
            medium_threshold=self.default_medium,
            high_threshold=self.default_high,
            decay_factor=self.default_decay,
            false_positive_count=0,
            missed_detection_count=0,
        )
        db.add(calibration)
        await db.flush()

        logger.info(
            "Created new calibration",
            extra={"user_id": user_id, "thresholds": self._get_thresholds_dict(calibration)},
        )

        return calibration

    async def get_thresholds(
        self,
        db: AsyncSession,
        user_id: str = "default",
    ) -> CalibrationThresholds:
        """Get calibration thresholds for a user.

        Returns the user's personalized thresholds if they exist,
        otherwise returns default thresholds with is_calibrated=False.

        This method does NOT create a calibration record if one doesn't exist.

        Args:
            db: Database session
            user_id: User identifier (defaults to "default")

        Returns:
            CalibrationThresholds with threshold values and calibration status
        """
        stmt = select(UserCalibration).where(UserCalibration.user_id == user_id)
        result = await db.execute(stmt)
        calibration = result.scalar_one_or_none()

        if calibration is None:
            return CalibrationThresholds(
                low_threshold=self.default_low,
                medium_threshold=self.default_medium,
                high_threshold=self.default_high,
                is_calibrated=False,
            )

        # User has calibration - check if they've provided any feedback
        is_calibrated = (
            calibration.false_positive_count > 0 or calibration.missed_detection_count > 0
        )

        return CalibrationThresholds(
            low_threshold=calibration.low_threshold,
            medium_threshold=calibration.medium_threshold,
            high_threshold=calibration.high_threshold,
            is_calibrated=is_calibrated,
        )

    def get_default_thresholds(self) -> CalibrationThresholds:
        """Get the default calibration thresholds.

        Returns:
            CalibrationThresholds with default values and is_calibrated=False
        """
        return CalibrationThresholds(
            low_threshold=self.default_low,
            medium_threshold=self.default_medium,
            high_threshold=self.default_high,
            is_calibrated=False,
        )

    async def adjust_from_feedback(
        self,
        db: AsyncSession,
        feedback: EventFeedback,
        event: Event,
        user_id: str = "default",
    ) -> UserCalibration:
        """Adjust thresholds based on user feedback.

        For FALSE_POSITIVE: Event was marked high-risk but user says benign
            -> Raise thresholds (less sensitive)

        For MISSED_DETECTION: Event was marked low-risk but user says concerning
            -> Lower thresholds (more sensitive)

        Args:
            db: Database session
            feedback: The feedback provided by the user
            event: The event the feedback is about
            user_id: User identifier

        Returns:
            Updated UserCalibration instance
        """
        calibration = await self.get_or_create_calibration(db, user_id)

        risk_score = event.risk_score
        if risk_score is None:
            logger.warning(
                "Cannot adjust calibration for event without risk score",
                extra={"event_id": event.id, "feedback_type": feedback.feedback_type.value},
            )
            return calibration

        # Calculate the adjustment
        adjustment = self.calculate_adjustment(
            feedback_type=feedback.feedback_type,
            risk_score=risk_score,
            decay_factor=calibration.decay_factor,
        )

        # Store old thresholds for logging
        old_thresholds = self._get_thresholds_dict(calibration)

        # Apply adjustments with constraint enforcement
        new_low, new_medium, new_high = self._apply_adjustment(
            calibration.low_threshold,
            calibration.medium_threshold,
            calibration.high_threshold,
            adjustment,
        )

        calibration.low_threshold = new_low
        calibration.medium_threshold = new_medium
        calibration.high_threshold = new_high
        calibration.updated_at = datetime.now(UTC)

        # Update feedback counts
        if feedback.feedback_type == FeedbackType.FALSE_POSITIVE:
            calibration.false_positive_count += 1
        else:
            calibration.missed_detection_count += 1

        await db.flush()

        logger.info(
            "Adjusted calibration from feedback",
            extra={
                "user_id": user_id,
                "feedback_type": feedback.feedback_type.value,
                "event_id": event.id,
                "risk_score": risk_score,
                "old_thresholds": old_thresholds,
                "new_thresholds": self._get_thresholds_dict(calibration),
                "adjustment": adjustment.to_dict(),
            },
        )

        return calibration

    async def reset_calibration(
        self,
        db: AsyncSession,
        user_id: str = "default",
    ) -> UserCalibration:
        """Reset calibration to default values.

        Args:
            db: Database session
            user_id: User identifier

        Returns:
            Reset UserCalibration instance
        """
        calibration = await self.get_or_create_calibration(db, user_id)

        old_thresholds = self._get_thresholds_dict(calibration)

        calibration.low_threshold = self.default_low
        calibration.medium_threshold = self.default_medium
        calibration.high_threshold = self.default_high
        calibration.decay_factor = self.default_decay
        calibration.false_positive_count = 0
        calibration.missed_detection_count = 0
        calibration.updated_at = datetime.now(UTC)

        await db.flush()

        logger.info(
            "Reset calibration to defaults",
            extra={
                "user_id": user_id,
                "old_thresholds": old_thresholds,
                "new_thresholds": self._get_thresholds_dict(calibration),
            },
        )

        return calibration

    def calculate_adjustment(
        self,
        feedback_type: FeedbackType,
        risk_score: int,
        decay_factor: float = DEFAULT_DECAY_FACTOR,
    ) -> ThresholdAdjustment:
        """Calculate the threshold adjustment for given feedback.

        The adjustment is calculated based on:
        1. The feedback type (false positive vs missed detection)
        2. The risk score of the event
        3. The decay factor controlling adjustment magnitude

        For FALSE_POSITIVE (event was high-risk but benign):
            - Raise all thresholds to make the system less sensitive
            - Adjustment magnitude based on how high the risk score was

        For MISSED_DETECTION (event was low-risk but concerning):
            - Lower all thresholds to make the system more sensitive
            - Adjustment magnitude based on how low the risk score was

        Args:
            feedback_type: Type of feedback
            risk_score: The risk score of the event
            decay_factor: Factor controlling adjustment magnitude (0.0-1.0)

        Returns:
            ThresholdAdjustment with deltas for each threshold
        """
        # Base adjustment scaled by decay factor
        # Use a base value of 10 that gets scaled by decay factor
        base_adjustment = int(10 * decay_factor)

        # Ensure minimum adjustment of 1 (unless decay_factor is 0)
        if decay_factor > 0 and base_adjustment < 1:
            base_adjustment = 1

        if feedback_type == FeedbackType.FALSE_POSITIVE:
            # Event was flagged as high-risk but user says benign
            # Raise thresholds to be less sensitive
            # Higher risk scores mean larger upward adjustment needed
            score_factor = max(1.0, risk_score / 50.0)
            adjustment = int(base_adjustment * score_factor)

            return ThresholdAdjustment(
                low_delta=adjustment,
                medium_delta=adjustment,
                high_delta=adjustment,
                feedback_type=feedback_type,
                original_risk_score=risk_score,
            )
        else:
            # FeedbackType.MISSED_DETECTION
            # Event was flagged as low-risk but user says concerning
            # Lower thresholds to be more sensitive
            # Lower risk scores mean larger downward adjustment needed
            score_factor = max(1.0, (100 - risk_score) / 50.0)
            adjustment = int(base_adjustment * score_factor)

            return ThresholdAdjustment(
                low_delta=-adjustment,
                medium_delta=-adjustment,
                high_delta=-adjustment,
                feedback_type=feedback_type,
                original_risk_score=risk_score,
            )

    def _apply_adjustment(
        self,
        low: int,
        medium: int,
        high: int,
        adjustment: ThresholdAdjustment,
    ) -> tuple[int, int, int]:
        """Apply adjustment while maintaining constraints.

        Constraints:
        1. All thresholds must be in range [0, 100]
        2. Ordering must be maintained: low < medium < high
        3. Minimum gap between thresholds: MIN_THRESHOLD_GAP

        Args:
            low: Current low threshold
            medium: Current medium threshold
            high: Current high threshold
            adjustment: The adjustment to apply

        Returns:
            Tuple of (new_low, new_medium, new_high)
        """
        # Apply raw adjustments
        new_low = low + adjustment.low_delta
        new_medium = medium + adjustment.medium_delta
        new_high = high + adjustment.high_delta

        # Clamp to valid range [0, 100]
        new_low = max(0, min(100, new_low))
        new_medium = max(0, min(100, new_medium))
        new_high = max(0, min(100, new_high))

        # Enforce ordering constraints with minimum gaps
        # Start from low and propagate constraints upward
        new_medium = max(new_low + MIN_THRESHOLD_GAP, new_medium)

        new_high = max(new_medium + MIN_THRESHOLD_GAP, new_high)

        # If high threshold pushed above 100, push everything down
        if new_high > 100:
            overflow = new_high - 100
            new_high = 100
            new_medium = max(MIN_THRESHOLD_GAP, new_medium - overflow)

            # Recalculate if medium constraint was violated
            new_medium = min(new_high - MIN_THRESHOLD_GAP, new_medium)

            # Propagate down to low
            new_low = min(new_medium - MIN_THRESHOLD_GAP, new_low)

        # Ensure low doesn't go below 0
        if new_low < 0:
            underflow = -new_low
            new_low = 0
            new_medium = min(100 - MIN_THRESHOLD_GAP, new_medium + underflow)

            # Recalculate if medium constraint was violated
            new_medium = max(new_low + MIN_THRESHOLD_GAP, new_medium)

            # Propagate up to high
            new_high = max(new_medium + MIN_THRESHOLD_GAP, new_high)

        # Final clamp to ensure all values are in range
        new_low = max(0, min(100 - 2 * MIN_THRESHOLD_GAP, new_low))
        new_medium = max(MIN_THRESHOLD_GAP, min(100 - MIN_THRESHOLD_GAP, new_medium))
        new_high = max(2 * MIN_THRESHOLD_GAP, min(100, new_high))

        return (new_low, new_medium, new_high)

    def _get_thresholds_dict(self, calibration: UserCalibration) -> dict:
        """Get thresholds as a dictionary for logging."""
        return {
            "low": calibration.low_threshold,
            "medium": calibration.medium_threshold,
            "high": calibration.high_threshold,
        }


# =============================================================================
# Singleton Pattern
# =============================================================================


@lru_cache(maxsize=1)
def get_calibration_service() -> CalibrationService:
    """Get a cached CalibrationService instance.

    Returns:
        CalibrationService instance
    """
    return CalibrationService()


def reset_calibration_service() -> None:
    """Clear the cached CalibrationService instance.

    Call this after changing configuration or for testing.
    """
    get_calibration_service.cache_clear()
