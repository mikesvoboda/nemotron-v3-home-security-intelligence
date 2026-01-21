"""Zone anomaly detection service for real-time activity anomaly detection.

This module provides the ZoneAnomalyService that compares real-time zone activity
against learned baselines to detect anomalies.

Features:
    - Unusual time detection (activity at unexpected hours)
    - Unusual frequency detection (sudden bursts of activity)
    - Unusual dwell detection (extended presence in zone)
    - Severity mapping based on statistical deviation
    - WebSocket event emission for real-time alerts
    - Anomaly persistence and query methods

Related: NEM-3198 (Backend Anomaly Detection Service)
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from backend.core.config import get_settings
from backend.core.database import get_session
from backend.core.redis import get_redis
from backend.models.zone_anomaly import AnomalySeverity, AnomalyType, ZoneAnomaly

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.models.camera_zone import CameraZone
    from backend.models.detection import Detection
    from backend.models.zone_baseline import ZoneActivityBaseline

logger = logging.getLogger(__name__)


class ZoneAnomalyService:
    """Service for detecting anomalies in zone activity patterns.

    Compares real-time detections against learned baselines to identify
    unusual activity patterns and emit alerts.

    Attributes:
        DEFAULT_THRESHOLD: Standard deviations for anomaly detection (2.0).
        _redis: Optional Redis client for WebSocket event emission.
        _baseline_service: Service for fetching zone baselines.
        _frequency_tracker: In-memory tracker for recent detections per zone.
    """

    DEFAULT_THRESHOLD = 2.0

    def __init__(self, redis_client: Any | None = None) -> None:
        """Initialize the anomaly service.

        Args:
            redis_client: Optional Redis client for WebSocket events.
        """
        self._redis = redis_client
        self._baseline_service = ZoneBaselineService()
        self._frequency_tracker: dict[UUID, list[tuple[datetime, int]]] = defaultdict(list)

    def _deviation_to_severity(self, deviation: float) -> AnomalySeverity:
        """Map deviation magnitude to severity level.

        Args:
            deviation: Number of standard deviations from baseline.

        Returns:
            Severity level based on deviation magnitude.
            - >= 4.0: CRITICAL
            - >= 3.0: WARNING
            - else: INFO
        """
        if deviation >= 4.0:
            return AnomalySeverity.CRITICAL
        if deviation >= 3.0:
            return AnomalySeverity.WARNING
        return AnomalySeverity.INFO

    def _check_unusual_time(
        self,
        detection: Detection,
        zone: CameraZone,
        baseline: ZoneActivityBaseline,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> ZoneAnomaly | None:
        """Check if detection occurred at an unusual time.

        Args:
            detection: The detection to check.
            zone: The zone where detection occurred.
            baseline: The baseline for this zone.
            threshold: Standard deviation threshold.

        Returns:
            ZoneAnomaly if unusual time detected, None otherwise.
        """
        timestamp = getattr(detection, "detected_at", None) or getattr(detection, "timestamp", None)
        if timestamp is None:
            return None

        if not hasattr(baseline, "hourly_pattern") or len(baseline.hourly_pattern) < 24:
            return None

        hour = timestamp.hour
        expected_activity = baseline.hourly_pattern[hour]

        hourly_std = getattr(baseline, "hourly_std", [1.0] * 24)
        if len(hourly_std) < 24:
            hourly_std = [1.0] * 24
        std = hourly_std[hour] if hourly_std[hour] > 0 else 0.1

        # Unusual time detection: activity at an hour with low expected activity
        # If expected activity is high (>= 1.0), seeing activity is normal
        if expected_activity >= 1.0:
            return None

        # If expected activity is very low and std is also low, this is highly unusual
        if expected_activity < 0.1 and std < 0.1:
            deviation = 4.0
        elif std > 0:
            # Deviation measures how far from expected mean we are
            # actual=1 detection, expected=low activity
            deviation = (1.0 - expected_activity) / std
        else:
            deviation = 0.0

        if deviation < threshold:
            return None

        severity = self._deviation_to_severity(deviation)
        anomaly_id = str(uuid.uuid4())

        return ZoneAnomaly(
            id=anomaly_id,
            zone_id=zone.id,
            camera_id=zone.camera_id,
            anomaly_type=AnomalyType.UNUSUAL_TIME,
            severity=severity.value,
            title=f"Unusual activity at {timestamp.strftime('%H:%M')}",
            description=(
                f"Activity detected in {zone.name} at {timestamp.strftime('%H:%M')} "
                f"when typical activity is {expected_activity:.1f}."
            ),
            expected_value=expected_activity,
            actual_value=1.0,
            deviation=deviation,
            detection_id=getattr(detection, "id", None),
            thumbnail_url=getattr(detection, "thumbnail_path", None),
            timestamp=timestamp,
        )

    async def _check_unusual_frequency(
        self,
        detection: Detection,
        zone: CameraZone,
        baseline: ZoneActivityBaseline,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> ZoneAnomaly | None:
        """Check if detection frequency is unusually high.

        Args:
            detection: The detection to check.
            zone: The zone where detection occurred.
            baseline: The baseline for this zone.
            threshold: Standard deviation threshold.

        Returns:
            ZoneAnomaly if unusual frequency detected, None otherwise.
        """
        timestamp = getattr(detection, "detected_at", None) or getattr(detection, "timestamp", None)
        if timestamp is None:
            return None

        zone_uuid = uuid.UUID(zone.id) if isinstance(zone.id, str) else zone.id
        detection_id = getattr(detection, "id", id(detection))

        cutoff = timestamp - timedelta(hours=1)
        self._frequency_tracker[zone_uuid] = [
            (ts, did) for ts, did in self._frequency_tracker[zone_uuid] if ts > cutoff
        ]

        self._frequency_tracker[zone_uuid].append((timestamp, detection_id))

        current_rate = len(self._frequency_tracker[zone_uuid])

        typical_rate = getattr(baseline, "typical_crossing_rate", 10.0)
        typical_std = getattr(baseline, "typical_crossing_std", 5.0)
        if typical_std <= 0:
            typical_std = 1.0

        deviation = (current_rate - typical_rate) / typical_std
        if deviation < threshold:
            return None

        severity = self._deviation_to_severity(deviation)
        anomaly_id = str(uuid.uuid4())

        return ZoneAnomaly(
            id=anomaly_id,
            zone_id=zone.id,
            camera_id=zone.camera_id,
            anomaly_type=AnomalyType.UNUSUAL_FREQUENCY,
            severity=severity.value,
            title=f"High activity frequency in {zone.name}",
            description=(
                f"Detected {current_rate} crossings in the last hour, "
                f"typical is {typical_rate:.1f} (std: {typical_std:.1f})."
            ),
            expected_value=typical_rate,
            actual_value=float(current_rate),
            deviation=deviation,
            detection_id=getattr(detection, "id", None),
            thumbnail_url=getattr(detection, "thumbnail_path", None),
            timestamp=timestamp,
        )

    async def _check_unusual_dwell(
        self,
        detection: Detection,
        zone: CameraZone,
        baseline: ZoneActivityBaseline,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> ZoneAnomaly | None:
        """Check if dwell time is unusually long.

        Args:
            detection: The detection to check.
            zone: The zone where detection occurred.
            baseline: The baseline for this zone.
            threshold: Standard deviation threshold.

        Returns:
            ZoneAnomaly if unusual dwell detected, None otherwise.
        """
        enrichment = getattr(detection, "enrichment_data", None)
        if not enrichment or not isinstance(enrichment, dict):
            return None

        dwell_time = enrichment.get("dwell_time")
        if dwell_time is None:
            return None

        timestamp = getattr(detection, "detected_at", None) or getattr(detection, "timestamp", None)

        typical_dwell = getattr(baseline, "typical_dwell_time", 30.0)
        typical_std = getattr(baseline, "typical_dwell_std", 10.0)
        if typical_std <= 0:
            typical_std = 1.0

        deviation = (dwell_time - typical_dwell) / typical_std
        if deviation < threshold:
            return None

        severity = self._deviation_to_severity(deviation)
        anomaly_id = str(uuid.uuid4())

        return ZoneAnomaly(
            id=anomaly_id,
            zone_id=zone.id,
            camera_id=zone.camera_id,
            anomaly_type=AnomalyType.UNUSUAL_DWELL,
            severity=severity.value,
            title=f"Extended presence in {zone.name}",
            description=(
                f"Entity lingered for {dwell_time:.0f}s, "
                f"typical is {typical_dwell:.0f}s (std: {typical_std:.1f}s)."
            ),
            expected_value=typical_dwell,
            actual_value=dwell_time,
            deviation=deviation,
            detection_id=getattr(detection, "id", None),
            thumbnail_url=getattr(detection, "thumbnail_path", None),
            timestamp=timestamp,
        )

    async def check_detection(
        self,
        detection: Detection,
        zone: CameraZone,
        session: AsyncSession | None = None,
        threshold: float | None = None,
    ) -> ZoneAnomaly | None:
        """Check a detection for anomalies against zone baseline.

        This is the main entry point for anomaly detection. It runs all
        anomaly checks and returns the most severe anomaly found.

        Args:
            detection: The detection to check.
            zone: The zone where detection occurred.
            session: Optional database session.
            threshold: Optional override for default threshold.

        Returns:
            The most severe ZoneAnomaly found, or None.
        """
        if threshold is None:
            threshold = self.DEFAULT_THRESHOLD

        baseline = await self._baseline_service.get_baseline(zone.id, session=session)
        if baseline is None:
            return None

        if getattr(baseline, "sample_count", 0) == 0:
            return None

        anomalies: list[ZoneAnomaly] = []

        time_anomaly = self._check_unusual_time(detection, zone, baseline, threshold)
        if time_anomaly:
            anomalies.append(time_anomaly)

        freq_anomaly = await self._check_unusual_frequency(detection, zone, baseline, threshold)
        if freq_anomaly:
            anomalies.append(freq_anomaly)

        dwell_anomaly = await self._check_unusual_dwell(detection, zone, baseline, threshold)
        if dwell_anomaly:
            anomalies.append(dwell_anomaly)

        if not anomalies:
            return None

        severity_order = {
            AnomalySeverity.CRITICAL.value: 0,
            AnomalySeverity.WARNING.value: 1,
            AnomalySeverity.INFO.value: 2,
        }
        anomalies.sort(key=lambda a: severity_order.get(a.severity, 99))

        most_severe = anomalies[0]
        await self._persist_and_emit(most_severe, session=session)

        return most_severe

    async def _emit_websocket_event(self, anomaly: ZoneAnomaly) -> None:
        """Emit WebSocket event for an anomaly.

        Args:
            anomaly: The anomaly to broadcast.
        """
        try:
            redis = self._redis
            if redis is None:
                # get_redis() is an async generator, use anext() to get the client
                redis = await anext(get_redis())

            settings = get_settings()
            channel = getattr(settings, "redis_event_channel", "hsi:events")

            message = {
                "type": "zone.anomaly",
                "data": {
                    "id": str(anomaly.id),
                    "zone_id": str(anomaly.zone_id),
                    "camera_id": anomaly.camera_id,
                    "anomaly_type": anomaly.anomaly_type,
                    "severity": anomaly.severity,
                    "title": anomaly.title,
                    "description": anomaly.description,
                    "expected_value": anomaly.expected_value,
                    "actual_value": anomaly.actual_value,
                    "deviation": anomaly.deviation,
                    "detection_id": anomaly.detection_id,
                    "thumbnail_url": anomaly.thumbnail_url,
                    "timestamp": (anomaly.timestamp.isoformat() if anomaly.timestamp else None),
                },
            }

            if redis is not None:
                await redis.publish(channel, message)

        except Exception as e:
            logger.warning(f"Failed to emit WebSocket event for anomaly: {e}")

    async def _persist_and_emit(
        self, anomaly: ZoneAnomaly, session: AsyncSession | None = None
    ) -> None:
        """Persist anomaly to database and emit WebSocket event.

        Args:
            anomaly: The anomaly to persist.
            session: Optional database session.
        """
        if session is not None:
            session.add(anomaly)
        else:
            async with get_session() as new_session:
                new_session.add(anomaly)
                await new_session.commit()

        await self._emit_websocket_event(anomaly)

    async def get_anomalies_for_zone(
        self,
        zone_id: UUID | str,
        since: datetime | None = None,
        unacknowledged_only: bool = False,
        session: AsyncSession | None = None,
    ) -> list[ZoneAnomaly]:
        """Get anomalies for a specific zone.

        Args:
            zone_id: The zone ID.
            since: Optional start time filter.
            unacknowledged_only: If True, only return unacknowledged anomalies.
            session: Database session.

        Returns:
            List of anomalies for the zone.
        """
        query = select(ZoneAnomaly).where(ZoneAnomaly.zone_id == str(zone_id))

        if since is not None:
            query = query.where(ZoneAnomaly.timestamp >= since)

        if unacknowledged_only:
            query = query.where(ZoneAnomaly.acknowledged == False)  # noqa: E712

        query = query.order_by(ZoneAnomaly.timestamp.desc())

        if session is None:
            raise ValueError("session is required")
        result = await session.execute(query)
        return list(result.scalars().all())

    async def acknowledge_anomaly(
        self,
        anomaly_id: UUID | str,
        acknowledged_by: str | None = None,
        session: AsyncSession | None = None,
    ) -> ZoneAnomaly | None:
        """Acknowledge an anomaly.

        Args:
            anomaly_id: The anomaly ID.
            acknowledged_by: Optional user identifier.
            session: Database session.

        Returns:
            The updated anomaly, or None if not found.
        """
        if session is None:
            raise ValueError("session is required")
        query = select(ZoneAnomaly).where(ZoneAnomaly.id == str(anomaly_id))
        result = await session.execute(query)
        anomaly = result.scalar_one_or_none()

        if anomaly is None:
            return None

        anomaly.acknowledge(acknowledged_by)
        await session.commit()

        return anomaly

    async def get_anomaly_counts_by_zone(
        self,
        since: datetime | None = None,
        unacknowledged_only: bool = False,
        session: AsyncSession | None = None,
    ) -> dict[str, int]:
        """Get anomaly counts grouped by zone.

        Args:
            since: Optional start time filter.
            unacknowledged_only: If True, only count unacknowledged anomalies.
            session: Database session.

        Returns:
            Dictionary mapping zone_id to count.
        """
        query = select(ZoneAnomaly.zone_id, func.count(ZoneAnomaly.id).label("count"))

        if since is not None:
            query = query.where(ZoneAnomaly.timestamp >= since)

        if unacknowledged_only:
            query = query.where(ZoneAnomaly.acknowledged == False)  # noqa: E712

        query = query.group_by(ZoneAnomaly.zone_id)

        if session is None:
            raise ValueError("session is required")
        result = await session.execute(query)
        return {str(row[0]): int(row[1]) for row in result.all()}


class ZoneBaselineService:
    """Stub service for zone baselines.

    This service will be fully implemented in a separate task.
    For now, it provides the interface needed by ZoneAnomalyService.
    """

    async def get_baseline(
        self, zone_id: str, session: AsyncSession | None = None
    ) -> ZoneActivityBaseline | None:
        """Get baseline for a zone.

        Args:
            zone_id: The zone ID.
            session: Optional database session.

        Returns:
            The zone baseline, or None if not found.
        """
        from backend.models.zone_baseline import ZoneActivityBaseline

        if session is None:
            return None

        query = select(ZoneActivityBaseline).where(ZoneActivityBaseline.zone_id == zone_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()


_zone_anomaly_service: ZoneAnomalyService | None = None


def get_zone_anomaly_service() -> ZoneAnomalyService:
    """Get or create the singleton zone anomaly service.

    Returns:
        The ZoneAnomalyService singleton.
    """
    global _zone_anomaly_service  # noqa: PLW0603
    if _zone_anomaly_service is None:
        _zone_anomaly_service = ZoneAnomalyService()
    return _zone_anomaly_service


def reset_zone_anomaly_service() -> None:
    """Reset the singleton zone anomaly service.

    Useful for testing.
    """
    global _zone_anomaly_service  # noqa: PLW0603
    _zone_anomaly_service = None
