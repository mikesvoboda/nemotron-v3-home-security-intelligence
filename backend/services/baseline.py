"""Baseline activity service for anomaly detection.

This service manages baseline activity models for detecting anomalous behavior
patterns. It tracks activity rates by hour and day-of-week per camera, as well
as class-specific frequencies (e.g., "vehicles after midnight are rare").

Features:
    - Exponential moving average with configurable decay factor
    - Rolling 30-day window for baseline calculations
    - Anomaly detection with configurable thresholds
    - Lightweight updates using SQL upserts

Usage:
    from backend.services.baseline import BaselineService, get_baseline_service

    service = get_baseline_service()

    # Update baseline when a detection occurs
    await service.update_baseline("camera_1", "person", detection_time)

    # Check if a detection is anomalous
    is_anomaly, score = await service.is_anomalous("camera_1", "vehicle", detection_time)
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select, update

from backend.core.database import get_session
from backend.core.logging import get_logger, sanitize_error
from backend.models.baseline import ActivityBaseline, ClassBaseline

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Keep sanitize_error imported for future use, suppress unused import warning
_ = sanitize_error

logger = get_logger(__name__)

# Global singleton
_baseline_service: BaselineService | None = None


class BaselineService:
    """Service for managing baseline activity models.

    This service tracks activity patterns per camera and detection class,
    using exponential moving averages with decay to handle seasonal drift.
    It provides anomaly detection by comparing current activity against
    historical baselines.

    Attributes:
        decay_factor: Exponential decay factor for EWMA (default: 0.1).
            Higher values give more weight to recent observations.
        window_days: Rolling window size in days (default: 30).
        anomaly_threshold_std: Number of standard deviations for anomaly
            detection (default: 2.0).
        min_samples: Minimum samples required before anomaly detection
            is reliable (default: 10).
    """

    def __init__(
        self,
        decay_factor: float = 0.1,
        window_days: int = 30,
        anomaly_threshold_std: float = 2.0,
        min_samples: int = 10,
    ) -> None:
        """Initialize the baseline service.

        Args:
            decay_factor: Exponential decay factor (0 < decay_factor <= 1).
                Higher values weight recent data more heavily.
            window_days: Rolling window size in days for considering data.
            anomaly_threshold_std: Standard deviations from mean for anomaly.
            min_samples: Minimum samples needed for reliable anomaly detection.
        """
        if not 0 < decay_factor <= 1:
            raise ValueError("decay_factor must be between 0 (exclusive) and 1 (inclusive)")
        if window_days < 1:
            raise ValueError("window_days must be at least 1")
        if anomaly_threshold_std < 0:
            raise ValueError("anomaly_threshold_std must be non-negative")
        if min_samples < 1:
            raise ValueError("min_samples must be at least 1")

        self.decay_factor = decay_factor
        self.window_days = window_days
        self.anomaly_threshold_std = anomaly_threshold_std
        self.min_samples = min_samples

        logger.info(
            f"BaselineService initialized: decay={decay_factor}, "
            f"window={window_days}d, threshold={anomaly_threshold_std}std, "
            f"min_samples={min_samples}"
        )

    def _calculate_time_decay(self, last_updated: datetime, now: datetime) -> float:
        """Calculate time-based decay factor.

        Uses exponential decay based on the number of days since last update.
        This ensures older baselines contribute less to the current estimate.

        Args:
            last_updated: Timestamp of last baseline update.
            now: Current timestamp.

        Returns:
            Decay multiplier between 0 and 1.
        """
        # Ensure both datetimes are timezone-aware or both are naive
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        days_elapsed = (now - last_updated).total_seconds() / 86400.0

        # If outside window, return 0 (baseline is stale)
        if days_elapsed > self.window_days:
            return 0.0

        # Exponential decay: e^(-lambda * t) where lambda = -ln(decay_factor)
        # This gives decay_factor^days_elapsed
        return math.exp(-days_elapsed * math.log(1 / self.decay_factor))

    async def update_baseline(
        self,
        camera_id: str,
        detection_class: str,
        timestamp: datetime,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        """Update baseline statistics for a detection.

        Updates both the activity baseline (per camera/hour/day-of-week) and
        the class baseline (per camera/class/hour). Uses exponential moving
        average with time decay.

        Transaction Contract:
            - If session is None: Creates a new session and commits automatically.
            - If session is provided: Caller MUST commit the transaction.
              Changes are added to the session but NOT committed, allowing
              callers to batch multiple operations in a single transaction.

        Example:
            # Auto-commit mode (no session passed):
            await service.update_baseline("cam1", "person", timestamp)

            # Manual commit mode (session passed):
            async with get_session() as session:
                await service.update_baseline("cam1", "person", ts, session=session)
                await service.update_baseline("cam1", "vehicle", ts, session=session)
                await session.commit()  # Caller MUST commit!

        Args:
            camera_id: ID of the camera that captured the detection.
            detection_class: The detected object class (e.g., "person").
            timestamp: Timestamp of the detection.
            session: Optional database session. If provided, caller is
                responsible for committing the transaction.
        """
        hour = timestamp.hour
        day_of_week = timestamp.weekday()
        now = datetime.now(UTC)

        async def _do_update(sess: AsyncSession) -> None:
            # Update activity baseline
            await self._update_activity_baseline(sess, camera_id, hour, day_of_week, now)

            # Update class baseline
            await self._update_class_baseline(sess, camera_id, detection_class, hour, now)

        if session is not None:
            await _do_update(session)
        else:
            async with get_session() as sess:
                await _do_update(sess)
                await sess.commit()

        logger.debug(
            f"Updated baselines for camera={camera_id}, class={detection_class}, "
            f"hour={hour}, day={day_of_week}"
        )

    async def _update_activity_baseline(
        self,
        session: AsyncSession,
        camera_id: str,
        hour: int,
        day_of_week: int,
        now: datetime,
    ) -> None:
        """Update or create activity baseline entry.

        Uses SELECT + UPDATE/INSERT pattern for updates.

        Note:
            This method does NOT commit the transaction. The caller
            (update_baseline) is responsible for managing commits.
        """
        # Try to get existing baseline
        stmt = select(ActivityBaseline).where(
            ActivityBaseline.camera_id == camera_id,
            ActivityBaseline.hour == hour,
            ActivityBaseline.day_of_week == day_of_week,
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Calculate decayed average using exponential weighted moving average
            decay = self._calculate_time_decay(existing.last_updated, now)
            if decay > 0:
                # Each detection is treated as +1 observation
                new_avg = decay * existing.avg_count + (1 - decay) * 1.0
                new_count = existing.sample_count + 1
            else:
                # Baseline is stale, reset
                new_avg = 1.0
                new_count = 1

            # Update existing record
            update_stmt = (
                update(ActivityBaseline)
                .where(ActivityBaseline.id == existing.id)
                .values(avg_count=new_avg, sample_count=new_count, last_updated=now)
            )
            await session.execute(update_stmt)
        else:
            # Create new baseline
            new_baseline = ActivityBaseline(
                camera_id=camera_id,
                hour=hour,
                day_of_week=day_of_week,
                avg_count=1.0,
                sample_count=1,
                last_updated=now,
            )
            session.add(new_baseline)

    async def _update_class_baseline(
        self,
        session: AsyncSession,
        camera_id: str,
        detection_class: str,
        hour: int,
        now: datetime,
    ) -> None:
        """Update or create class baseline entry.

        Uses SELECT + UPDATE/INSERT pattern for updates.

        Note:
            This method does NOT commit the transaction. The caller
            (update_baseline) is responsible for managing commits.
        """
        # Try to get existing baseline
        stmt = select(ClassBaseline).where(
            ClassBaseline.camera_id == camera_id,
            ClassBaseline.detection_class == detection_class,
            ClassBaseline.hour == hour,
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Calculate decayed frequency
            decay = self._calculate_time_decay(existing.last_updated, now)
            if decay > 0:
                # EWMA for frequency
                new_freq = decay * existing.frequency + (1 - decay) * 1.0
                new_count = existing.sample_count + 1
            else:
                # Baseline is stale, reset
                new_freq = 1.0
                new_count = 1

            # Update existing record
            update_stmt = (
                update(ClassBaseline)
                .where(ClassBaseline.id == existing.id)
                .values(frequency=new_freq, sample_count=new_count, last_updated=now)
            )
            await session.execute(update_stmt)
        else:
            # Create new baseline
            new_baseline = ClassBaseline(
                camera_id=camera_id,
                detection_class=detection_class,
                hour=hour,
                frequency=1.0,
                sample_count=1,
                last_updated=now,
            )
            session.add(new_baseline)

    async def get_activity_rate(
        self,
        camera_id: str,
        hour: int,
        day_of_week: int,
        *,
        session: AsyncSession | None = None,
    ) -> float:
        """Get the baseline activity rate for a camera at a specific time slot.

        Returns the exponentially weighted moving average of activity for the
        given camera, hour, and day-of-week combination.

        Args:
            camera_id: ID of the camera.
            hour: Hour of day (0-23).
            day_of_week: Day of week (0=Monday, 6=Sunday).
            session: Optional database session.

        Returns:
            Activity rate (average count). Returns 0.0 if no baseline exists.
        """

        async def _do_get(sess: AsyncSession) -> float:
            stmt = select(ActivityBaseline).where(
                ActivityBaseline.camera_id == camera_id,
                ActivityBaseline.hour == hour,
                ActivityBaseline.day_of_week == day_of_week,
            )
            result = await sess.execute(stmt)
            baseline = result.scalar_one_or_none()

            if baseline is None:
                return 0.0

            # Apply time decay to the stored average
            now = datetime.now(UTC)
            decay = self._calculate_time_decay(baseline.last_updated, now)
            return float(baseline.avg_count * decay)

        if session is not None:
            return await _do_get(session)
        else:
            async with get_session() as sess:
                return await _do_get(sess)

    async def get_class_frequency(
        self,
        camera_id: str,
        detection_class: str,
        hour: int,
        *,
        session: AsyncSession | None = None,
    ) -> float:
        """Get the baseline frequency for a detection class at a specific hour.

        Returns the exponentially weighted moving average frequency for the
        given camera, class, and hour combination.

        Args:
            camera_id: ID of the camera.
            detection_class: The object class (e.g., "person", "vehicle").
            hour: Hour of day (0-23).
            session: Optional database session.

        Returns:
            Class frequency (normalized). Returns 0.0 if no baseline exists.
        """

        async def _do_get(sess: AsyncSession) -> float:
            stmt = select(ClassBaseline).where(
                ClassBaseline.camera_id == camera_id,
                ClassBaseline.detection_class == detection_class,
                ClassBaseline.hour == hour,
            )
            result = await sess.execute(stmt)
            baseline = result.scalar_one_or_none()

            if baseline is None:
                return 0.0

            # Apply time decay to the stored frequency
            now = datetime.now(UTC)
            decay = self._calculate_time_decay(baseline.last_updated, now)
            return float(baseline.frequency * decay)

        if session is not None:
            return await _do_get(session)
        else:
            async with get_session() as sess:
                return await _do_get(sess)

    async def is_anomalous(
        self,
        camera_id: str,
        detection_class: str,
        timestamp: datetime,
        *,
        session: AsyncSession | None = None,
    ) -> tuple[bool, float]:
        """Check if a detection is anomalous based on historical baselines.

        Compares the current detection against the baseline frequency for
        this class at this time. A detection is considered anomalous if
        it occurs at a time when this class is rarely seen.

        The anomaly score is calculated as:
        - 0.0: Detection matches baseline (class frequently seen at this time)
        - 1.0: Detection is rare (class never/rarely seen at this time)

        Args:
            camera_id: ID of the camera.
            detection_class: The detected object class.
            timestamp: Timestamp of the detection.
            session: Optional database session.

        Returns:
            Tuple of (is_anomalous: bool, anomaly_score: float).
            - is_anomalous: True if the detection exceeds the anomaly threshold.
            - anomaly_score: Value between 0.0 (normal) and 1.0 (highly anomalous).
        """
        hour = timestamp.hour

        async def _do_check(sess: AsyncSession) -> tuple[bool, float]:
            # Get class baseline for this hour
            class_stmt = select(ClassBaseline).where(
                ClassBaseline.camera_id == camera_id,
                ClassBaseline.detection_class == detection_class,
                ClassBaseline.hour == hour,
            )
            class_result = await sess.execute(class_stmt)
            class_baseline = class_result.scalar_one_or_none()

            # Get all class baselines for this camera/hour to compute relative frequency
            all_classes_stmt = select(ClassBaseline).where(
                ClassBaseline.camera_id == camera_id,
                ClassBaseline.hour == hour,
            )
            all_result = await sess.execute(all_classes_stmt)
            all_baselines = all_result.scalars().all()

            now = datetime.now(UTC)

            # If no baselines exist, we can't determine anomaly (return neutral)
            if not all_baselines:
                logger.debug(
                    f"No baselines for camera={camera_id}, hour={hour}. Cannot determine anomaly."
                )
                return (False, 0.5)  # Neutral score - insufficient data

            # Calculate total frequency across all classes at this hour
            total_frequency = 0.0
            class_frequency = 0.0
            total_samples = 0

            for baseline in all_baselines:
                decay = self._calculate_time_decay(baseline.last_updated, now)
                decayed_freq = baseline.frequency * decay
                total_frequency += decayed_freq
                total_samples += baseline.sample_count

                if baseline.detection_class == detection_class:
                    class_frequency = decayed_freq

            # If we don't have enough samples, return uncertain
            if total_samples < self.min_samples:
                logger.debug(
                    f"Insufficient samples ({total_samples} < {self.min_samples}) "
                    f"for camera={camera_id}, hour={hour}. Cannot determine anomaly."
                )
                return (False, 0.5)  # Neutral score - insufficient data

            # Calculate relative frequency (0.0 to 1.0)
            relative_frequency = class_frequency / total_frequency if total_frequency > 0 else 0.0

            # Anomaly score is inversely proportional to frequency.
            # Rare classes at this hour have high anomaly scores.
            # We also consider if this class has ever been seen at this hour.
            if class_baseline is None:
                # Class never seen at this hour - highly anomalous
                anomaly_score = 1.0
            elif class_frequency == 0.0:
                # Class baseline exists but decayed to zero - highly anomalous
                anomaly_score = 0.95
            else:
                # Score based on relative frequency
                # Low frequency = high anomaly score
                anomaly_score = max(0.0, min(1.0, 1.0 - relative_frequency))

            # Determine if anomalous based on threshold
            # Using a simpler threshold: anomaly if score > (1 - 1/threshold_std)
            # This maps the threshold to a reasonable cutoff
            is_anomaly = anomaly_score > (1.0 - 1.0 / (self.anomaly_threshold_std + 1))

            logger.debug(
                f"Anomaly check: camera={camera_id}, class={detection_class}, "
                f"hour={hour}, relative_freq={relative_frequency:.4f}, "
                f"anomaly_score={anomaly_score:.4f}, is_anomaly={is_anomaly}"
            )

            return (is_anomaly, anomaly_score)

        if session is not None:
            return await _do_check(session)
        else:
            async with get_session() as sess:
                return await _do_check(sess)

    async def get_camera_baseline_summary(
        self,
        camera_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> dict:
        """Get a summary of baseline data for a camera.

        Returns summary statistics including:
        - Total activity baselines
        - Total class baselines
        - Most common classes
        - Peak activity hours

        Args:
            camera_id: ID of the camera.
            session: Optional database session.

        Returns:
            Dictionary with baseline summary information.
        """

        async def _do_get(sess: AsyncSession) -> dict:
            # Count activity baselines
            activity_stmt = select(ActivityBaseline).where(ActivityBaseline.camera_id == camera_id)
            activity_result = await sess.execute(activity_stmt)
            activity_baselines = activity_result.scalars().all()

            # Count class baselines
            class_stmt = select(ClassBaseline).where(ClassBaseline.camera_id == camera_id)
            class_result = await sess.execute(class_stmt)
            class_baselines = class_result.scalars().all()

            # Aggregate class frequencies
            class_totals: dict[str, float] = {}
            for class_baseline in class_baselines:
                if class_baseline.detection_class not in class_totals:
                    class_totals[class_baseline.detection_class] = 0.0
                class_totals[class_baseline.detection_class] += class_baseline.frequency

            # Find peak hours
            hour_totals: dict[int, float] = {}
            for activity_baseline in activity_baselines:
                if activity_baseline.hour not in hour_totals:
                    hour_totals[activity_baseline.hour] = 0.0
                hour_totals[activity_baseline.hour] += activity_baseline.avg_count

            # Sort classes by frequency
            sorted_classes = sorted(class_totals.items(), key=lambda x: x[1], reverse=True)[:5]

            # Sort hours by activity
            sorted_hours = sorted(hour_totals.items(), key=lambda x: x[1], reverse=True)[:5]

            return {
                "camera_id": camera_id,
                "activity_baseline_count": len(activity_baselines),
                "class_baseline_count": len(class_baselines),
                "unique_classes": len(class_totals),
                "top_classes": [{"class": c, "total_frequency": f} for c, f in sorted_classes],
                "peak_hours": [{"hour": h, "total_activity": a} for h, a in sorted_hours],
            }

        if session is not None:
            return await _do_get(session)
        else:
            async with get_session() as sess:
                return await _do_get(sess)


def get_baseline_service() -> BaselineService:
    """Get or create the global baseline service singleton.

    Returns:
        The global BaselineService instance.
    """
    global _baseline_service  # noqa: PLW0603
    if _baseline_service is None:
        _baseline_service = BaselineService()
    return _baseline_service


def reset_baseline_service() -> None:
    """Reset the global baseline service singleton.

    Useful for testing to ensure a clean state.
    """
    global _baseline_service  # noqa: PLW0603
    _baseline_service = None
