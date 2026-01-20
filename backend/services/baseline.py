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

    from backend.api.schemas.baseline import (
        AnomalyEvent,
        CurrentDeviation,
        DailyPattern,
        DeviationInterpretation,
        HourlyPattern,
        ObjectBaseline,
    )

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

    async def get_hourly_patterns(
        self,
        camera_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> dict[str, HourlyPattern]:
        """Get hourly activity patterns for a camera.

        Returns activity patterns aggregated by hour (0-23).

        Args:
            camera_id: ID of the camera.
            session: Optional database session.

        Returns:
            Dictionary mapping hour string to HourlyPattern objects.
        """
        from backend.api.schemas.baseline import HourlyPattern

        async def _do_get(sess: AsyncSession) -> dict[str, HourlyPattern]:
            activity_stmt = select(ActivityBaseline).where(ActivityBaseline.camera_id == camera_id)
            result = await sess.execute(activity_stmt)
            baselines = result.scalars().all()

            # Aggregate by hour across all days
            hour_data: dict[int, list[ActivityBaseline]] = {}
            for baseline in baselines:
                if baseline.hour not in hour_data:
                    hour_data[baseline.hour] = []
                hour_data[baseline.hour].append(baseline)

            patterns: dict[str, HourlyPattern] = {}
            for hour, hour_baselines in hour_data.items():
                avg_counts = [b.avg_count for b in hour_baselines]
                avg_detections = sum(avg_counts) / len(avg_counts) if avg_counts else 0.0
                # Calculate standard deviation
                if len(avg_counts) > 1:
                    mean = avg_detections
                    variance = sum((x - mean) ** 2 for x in avg_counts) / len(avg_counts)
                    std_dev = math.sqrt(variance)
                else:
                    std_dev = 0.0
                total_samples = sum(b.sample_count for b in hour_baselines)

                patterns[str(hour)] = HourlyPattern(
                    avg_detections=round(avg_detections, 2),
                    std_dev=round(std_dev, 2),
                    sample_count=total_samples,
                )

            return patterns

        if session is not None:
            return await _do_get(session)
        else:
            async with get_session() as sess:
                return await _do_get(sess)

    async def get_daily_patterns(
        self,
        camera_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> dict[str, DailyPattern]:
        """Get daily activity patterns for a camera.

        Returns activity patterns aggregated by day of week.

        Args:
            camera_id: ID of the camera.
            session: Optional database session.

        Returns:
            Dictionary mapping day name to DailyPattern objects.
        """
        from backend.api.schemas.baseline import DailyPattern

        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

        async def _do_get(sess: AsyncSession) -> dict[str, DailyPattern]:
            activity_stmt = select(ActivityBaseline).where(ActivityBaseline.camera_id == camera_id)
            result = await sess.execute(activity_stmt)
            baselines = result.scalars().all()

            # Aggregate by day of week
            day_data: dict[int, list[ActivityBaseline]] = {}
            for baseline in baselines:
                if baseline.day_of_week not in day_data:
                    day_data[baseline.day_of_week] = []
                day_data[baseline.day_of_week].append(baseline)

            patterns: dict[str, DailyPattern] = {}
            for day_num, day_baselines in day_data.items():
                # Sum all activity for this day
                total_activity = sum(b.avg_count for b in day_baselines)
                total_samples = sum(b.sample_count for b in day_baselines)

                # Find peak hour for this day
                hour_activity: dict[int, float] = {}
                for b in day_baselines:
                    hour_activity[b.hour] = b.avg_count
                if hour_activity:
                    peak_hour = max(hour_activity.keys(), key=lambda h: hour_activity[h])
                else:
                    peak_hour = 12

                if 0 <= day_num < len(day_names):
                    patterns[day_names[day_num]] = DailyPattern(
                        avg_detections=round(total_activity, 2),
                        peak_hour=peak_hour,
                        total_samples=total_samples,
                    )

            return patterns

        if session is not None:
            return await _do_get(session)
        else:
            async with get_session() as sess:
                return await _do_get(sess)

    async def get_object_baselines(
        self,
        camera_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> dict[str, ObjectBaseline]:
        """Get object-specific baseline statistics for a camera.

        Returns baseline statistics for each detected object type.

        Args:
            camera_id: ID of the camera.
            session: Optional database session.

        Returns:
            Dictionary mapping object class to ObjectBaseline objects.
        """
        from backend.api.schemas.baseline import ObjectBaseline

        async def _do_get(sess: AsyncSession) -> dict[str, ObjectBaseline]:
            class_stmt = select(ClassBaseline).where(ClassBaseline.camera_id == camera_id)
            result = await sess.execute(class_stmt)
            baselines = result.scalars().all()

            # Aggregate by class
            class_data: dict[str, list[ClassBaseline]] = {}
            for baseline in baselines:
                if baseline.detection_class not in class_data:
                    class_data[baseline.detection_class] = []
                class_data[baseline.detection_class].append(baseline)

            object_baselines: dict[str, ObjectBaseline] = {}
            for detection_class, class_baselines in class_data.items():
                # Calculate average hourly frequency
                total_freq = sum(b.frequency for b in class_baselines)
                hours_covered = len(class_baselines)
                avg_hourly = total_freq / hours_covered if hours_covered > 0 else 0.0

                # Find peak hour for this class
                hour_freq: dict[int, float] = {}
                for b in class_baselines:
                    hour_freq[b.hour] = b.frequency
                peak_hour = max(hour_freq.keys(), key=lambda h: hour_freq[h]) if hour_freq else 12

                # Total detections (sum of sample counts)
                total_detections = sum(b.sample_count for b in class_baselines)

                object_baselines[detection_class] = ObjectBaseline(
                    avg_hourly=round(avg_hourly, 2),
                    peak_hour=peak_hour,
                    total_detections=total_detections,
                )

            return object_baselines

        if session is not None:
            return await _do_get(session)
        else:
            async with get_session() as sess:
                return await _do_get(sess)

    def _interpret_z_score(self, z_score: float) -> DeviationInterpretation:
        """Convert z-score to deviation interpretation.

        Args:
            z_score: The z-score value.

        Returns:
            DeviationInterpretation enum value.
        """
        from backend.api.schemas.baseline import DeviationInterpretation

        if z_score < -2.0:
            return DeviationInterpretation.FAR_BELOW_NORMAL
        if z_score < -1.0:
            return DeviationInterpretation.BELOW_NORMAL
        if z_score < 1.0:
            return DeviationInterpretation.NORMAL
        if z_score < 2.0:
            return DeviationInterpretation.SLIGHTLY_ABOVE_NORMAL
        if z_score < 3.0:
            return DeviationInterpretation.ABOVE_NORMAL
        return DeviationInterpretation.FAR_ABOVE_NORMAL

    async def get_current_deviation(
        self,
        camera_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> CurrentDeviation | None:
        """Get current activity deviation from baseline for a camera.

        Compares recent activity (current hour) against historical baseline.

        Args:
            camera_id: ID of the camera.
            session: Optional database session.

        Returns:
            CurrentDeviation object or None if insufficient data.
        """
        from backend.api.schemas.baseline import CurrentDeviation

        now = datetime.now(UTC)
        hour = now.hour
        day_of_week = now.weekday()

        async def _do_get(sess: AsyncSession) -> CurrentDeviation | None:
            # Get baseline for current hour and day
            activity_stmt = select(ActivityBaseline).where(
                ActivityBaseline.camera_id == camera_id,
                ActivityBaseline.hour == hour,
                ActivityBaseline.day_of_week == day_of_week,
            )
            result = await sess.execute(activity_stmt)
            baseline = result.scalar_one_or_none()

            if baseline is None or baseline.sample_count < self.min_samples:
                return None

            # Get all baselines for this hour to calculate standard deviation
            all_hour_stmt = select(ActivityBaseline).where(
                ActivityBaseline.camera_id == camera_id,
                ActivityBaseline.hour == hour,
            )
            all_result = await sess.execute(all_hour_stmt)
            all_baselines = all_result.scalars().all()

            if not all_baselines:
                return None

            # Calculate mean and std dev across all days for this hour
            avg_counts = [b.avg_count for b in all_baselines]
            mean = sum(avg_counts) / len(avg_counts)
            if len(avg_counts) > 1:
                variance = sum((x - mean) ** 2 for x in avg_counts) / len(avg_counts)
                std_dev = math.sqrt(variance)
            else:
                std_dev = mean * 0.1  # Assume 10% if only one sample

            # Calculate deviation score (z-score)
            current = baseline.avg_count
            z_score = (current - mean) / std_dev if std_dev > 0 else 0.0

            # Interpret the deviation using helper method
            interpretation = self._interpret_z_score(z_score)

            # Identify contributing factors
            factors: list[str] = []
            if z_score > 1.5:
                # Check class baselines for elevated counts
                class_stmt = select(ClassBaseline).where(
                    ClassBaseline.camera_id == camera_id,
                    ClassBaseline.hour == hour,
                )
                class_result = await sess.execute(class_stmt)
                class_baselines = class_result.scalars().all()

                for cb in class_baselines:
                    if cb.frequency > 2.0:  # Above average frequency
                        factors.append(f"{cb.detection_class}_count_elevated")

            if abs(z_score) > 1.0 and len(factors) == 0:
                factors.append("overall_activity_deviation")

            return CurrentDeviation(
                score=round(z_score, 2),
                interpretation=interpretation,
                contributing_factors=factors,
            )

        if session is not None:
            return await _do_get(session)
        else:
            async with get_session() as sess:
                return await _do_get(sess)

    async def get_baseline_established_date(
        self,
        camera_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> datetime | None:
        """Get the earliest baseline update date for a camera.

        Args:
            camera_id: ID of the camera.
            session: Optional database session.

        Returns:
            Datetime of earliest baseline or None if no data.
        """
        from sqlalchemy import func

        async def _do_get(sess: AsyncSession) -> datetime | None:
            # Get earliest activity baseline
            activity_stmt = select(func.min(ActivityBaseline.last_updated)).where(
                ActivityBaseline.camera_id == camera_id
            )
            activity_result = await sess.execute(activity_stmt)
            activity_min = activity_result.scalar()

            # Get earliest class baseline
            class_stmt = select(func.min(ClassBaseline.last_updated)).where(
                ClassBaseline.camera_id == camera_id
            )
            class_result = await sess.execute(class_stmt)
            class_min = class_result.scalar()

            # Return earliest of the two
            if activity_min is None and class_min is None:
                return None
            elif activity_min is None:
                return class_min
            elif class_min is None:
                return activity_min
            else:
                return min(activity_min, class_min)

        if session is not None:
            return await _do_get(session)
        else:
            async with get_session() as sess:
                return await _do_get(sess)

    async def get_recent_anomalies(
        self,
        camera_id: str,  # noqa: ARG002 - Reserved for future anomaly table query
        days: int = 7,  # noqa: ARG002 - Reserved for future anomaly table query
        *,
        session: AsyncSession | None = None,  # noqa: ARG002 - Reserved for future DB query
    ) -> list[AnomalyEvent]:
        """Get recent anomaly events for a camera.

        Note: This method returns a list of recent anomaly events based on
        stored detection data. In a full implementation, anomaly events
        would be stored when detected. For now, this returns an empty list
        as anomaly events are computed on-the-fly during detection.

        Args:
            camera_id: ID of the camera.
            days: Number of days to look back (default: 7).
            session: Optional database session.

        Returns:
            List of AnomalyEvent objects.
        """
        # Note: In a full implementation, we would store anomaly events
        # in a dedicated table when they're detected. For now, return empty
        # list as anomaly detection happens at detection time.
        #
        # Future implementation would query from an anomaly_events table:
        # SELECT * FROM anomaly_events
        # WHERE camera_id = :camera_id
        #   AND timestamp > NOW() - INTERVAL ':days days'
        # ORDER BY timestamp DESC
        return []

    async def get_activity_baselines_raw(
        self,
        camera_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[ActivityBaseline]:
        """Get all raw activity baseline records for a camera.

        Returns up to 168 entries (24 hours x 7 days).

        Args:
            camera_id: ID of the camera.
            session: Optional database session.

        Returns:
            List of ActivityBaseline records.
        """

        async def _do_get(sess: AsyncSession) -> list[ActivityBaseline]:
            activity_stmt = (
                select(ActivityBaseline)
                .where(ActivityBaseline.camera_id == camera_id)
                .order_by(ActivityBaseline.day_of_week, ActivityBaseline.hour)
            )
            result = await sess.execute(activity_stmt)
            return list(result.scalars().all())

        if session is not None:
            return await _do_get(session)
        else:
            async with get_session() as sess:
                return await _do_get(sess)

    async def get_class_baselines_raw(
        self,
        camera_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[ClassBaseline]:
        """Get all raw class baseline records for a camera.

        Args:
            camera_id: ID of the camera.
            session: Optional database session.

        Returns:
            List of ClassBaseline records.
        """

        async def _do_get(sess: AsyncSession) -> list[ClassBaseline]:
            class_stmt = (
                select(ClassBaseline)
                .where(ClassBaseline.camera_id == camera_id)
                .order_by(ClassBaseline.detection_class, ClassBaseline.hour)
            )
            result = await sess.execute(class_stmt)
            return list(result.scalars().all())

        if session is not None:
            return await _do_get(session)
        else:
            async with get_session() as sess:
                return await _do_get(sess)

    async def get_class_baselines_by_camera_hour(
        self,
        camera_id: str,
        hour: int,
        *,
        session: AsyncSession | None = None,
    ) -> dict[str, ClassBaseline]:
        """Get class baselines for a camera at a specific hour.

        Returns baselines as a dictionary keyed by "{camera_id}:{hour}:{class}"
        for easy lookup in the format_class_anomaly_context function.

        Args:
            camera_id: ID of the camera.
            hour: Hour of day (0-23).
            session: Optional database session.

        Returns:
            Dictionary mapping "{camera_id}:{hour}:{detection_class}" to ClassBaseline.
        """

        async def _do_get(sess: AsyncSession) -> dict[str, ClassBaseline]:
            class_stmt = select(ClassBaseline).where(
                ClassBaseline.camera_id == camera_id,
                ClassBaseline.hour == hour,
            )
            result = await sess.execute(class_stmt)
            baselines = result.scalars().all()

            return {
                f"{baseline.camera_id}:{baseline.hour}:{baseline.detection_class}": baseline
                for baseline in baselines
            }

        if session is not None:
            return await _do_get(session)
        else:
            async with get_session() as sess:
                return await _do_get(sess)

    def update_config(
        self,
        *,
        threshold_stdev: float | None = None,
        min_samples: int | None = None,
    ) -> None:
        """Update the service configuration.

        Args:
            threshold_stdev: New anomaly threshold in standard deviations.
            min_samples: New minimum samples required.

        Raises:
            ValueError: If invalid values are provided.
        """
        if threshold_stdev is not None:
            if threshold_stdev <= 0:
                raise ValueError("threshold_stdev must be positive")
            self.anomaly_threshold_std = threshold_stdev

        if min_samples is not None:
            if min_samples < 1:
                raise ValueError("min_samples must be at least 1")
            self.min_samples = min_samples

        logger.info(
            f"BaselineService config updated: threshold={self.anomaly_threshold_std}std, "
            f"min_samples={self.min_samples}"
        )


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
