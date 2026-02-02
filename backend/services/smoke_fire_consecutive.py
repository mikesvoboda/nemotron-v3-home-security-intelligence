"""Consecutive smoke/fire detection tracking service.

This module provides tracking for consecutive smoke/fire detections to reduce
false positives. Smoke detection in particular can be triggered by steam, fog,
or other harmless conditions, so requiring multiple consecutive detections
within a time window helps filter out transient false positives.

Tracking Strategy:
- Store detection state in Redis with per-camera keys
- Count consecutive detections of the same type within time window
- Reset count when detection type changes or time window expires
- Trigger alert when consecutive count reaches threshold

Default Configuration:
- consecutive_required: 2 (second detection triggers alert)
- window_seconds: 5 (detections must be within 5 seconds)
- cooldown_seconds: 90 (60-120 range, prevents alert spam)

Redis Keys:
- smoke_fire:{camera_id}:tracking - JSON object with tracking state
- smoke_fire:{camera_id}:cooldown - Flag for alert cooldown
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from backend.core.logging import get_logger

logger = get_logger(__name__)

# Default configuration constants
DEFAULT_CONSECUTIVE_REQUIRED: int = 2
DEFAULT_CONSECUTIVE_WINDOW_SECONDS: int = 5
DEFAULT_COOLDOWN_SECONDS: int = 90  # Within 60-120 range

# Redis key prefix
REDIS_KEY_PREFIX: str = "smoke_fire"

# TTL for tracking keys (5 minutes)
TRACKING_KEY_TTL_SECONDS: int = 300


@dataclass(slots=True)
class TrackingResult:
    """Result from tracking a smoke/fire detection.

    Attributes:
        camera_id: Camera where detection occurred
        detection_type: Type of detection (smoke or fire)
        confidence: Detection confidence score
        consecutive_count: Number of consecutive detections
        should_alert: Whether an alert should be triggered
        first_detection_time: When the first detection in sequence occurred
    """

    camera_id: str
    detection_type: str
    confidence: float
    consecutive_count: int
    should_alert: bool
    first_detection_time: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def alert_severity(self) -> str:
        """Get the alert severity based on detection type.

        Fire is always CRITICAL severity.
        Smoke is HIGH severity.

        Returns:
            Severity string: 'critical' or 'high'
        """
        if self.detection_type == "fire":
            return "critical"
        return "high"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the tracking result
        """
        return {
            "camera_id": self.camera_id,
            "detection_type": self.detection_type,
            "confidence": self.confidence,
            "consecutive_count": self.consecutive_count,
            "should_alert": self.should_alert,
            "alert_severity": self.alert_severity,
            "first_detection_time": self.first_detection_time.isoformat(),
        }


class SmokeFireConsecutiveTracker:
    """Tracks consecutive smoke/fire detections using Redis.

    This service maintains state for consecutive detection counting
    per camera, enabling noise filtering for smoke/fire alerts.

    Attributes:
        redis: Redis client for state storage
        consecutive_required: Number of consecutive detections required
        window_seconds: Time window for consecutive detections
        cooldown_seconds: Cooldown period after alert
    """

    def __init__(
        self,
        redis_client: Any,
        consecutive_required: int = DEFAULT_CONSECUTIVE_REQUIRED,
        window_seconds: int = DEFAULT_CONSECUTIVE_WINDOW_SECONDS,
        cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
    ) -> None:
        """Initialize the consecutive tracker.

        Args:
            redis_client: Redis client instance
            consecutive_required: Number of consecutive detections to trigger alert
            window_seconds: Time window for consecutive detection counting
            cooldown_seconds: Cooldown period after alert (60-120 range)
        """
        self.redis = redis_client
        self.consecutive_required = consecutive_required
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds

    def _tracking_key(self, camera_id: str) -> str:
        """Get Redis key for tracking state.

        Args:
            camera_id: Camera identifier

        Returns:
            Redis key string
        """
        return f"{REDIS_KEY_PREFIX}:{camera_id}:tracking"

    def _cooldown_key(self, camera_id: str) -> str:
        """Get Redis key for cooldown state.

        Args:
            camera_id: Camera identifier

        Returns:
            Redis key string
        """
        return f"{REDIS_KEY_PREFIX}:{camera_id}:cooldown"

    async def _get_tracking_state(self, camera_id: str) -> dict[str, Any] | None:
        """Get tracking state from Redis.

        Args:
            camera_id: Camera identifier

        Returns:
            Tracking state dictionary or None if not found
        """
        key = self._tracking_key(camera_id)
        data = await self.redis.get(key)
        if data is None:
            return None

        try:
            # Handle both string and already-parsed data
            if isinstance(data, str):
                # Try to parse as JSON
                try:
                    parsed = json.loads(data)
                    return dict(parsed) if isinstance(parsed, dict) else None
                except json.JSONDecodeError:
                    # Invalid JSON, return None
                    return None
            return dict(data) if isinstance(data, dict) else None
        except Exception as e:
            logger.warning(f"Failed to parse tracking state: {e}")
            return None

    async def _set_tracking_state(
        self,
        camera_id: str,
        detection_type: str,
        count: int,
        first_detection_time: float,
        last_detection_time: float,
    ) -> None:
        """Set tracking state in Redis.

        Args:
            camera_id: Camera identifier
            detection_type: Type of detection (smoke or fire)
            count: Current consecutive count
            first_detection_time: Timestamp of first detection
            last_detection_time: Timestamp of last detection
        """
        key = self._tracking_key(camera_id)
        state = {
            "detection_type": detection_type,
            "count": count,
            "first_detection_time": first_detection_time,
            "last_detection_time": last_detection_time,
        }
        await self.redis.set(key, json.dumps(state), expire=TRACKING_KEY_TTL_SECONDS)

    async def _is_in_cooldown(self, camera_id: str) -> bool:
        """Check if camera is in cooldown period.

        Args:
            camera_id: Camera identifier

        Returns:
            True if in cooldown, False otherwise
        """
        key = self._cooldown_key(camera_id)
        exists = await self.redis.exists(key)
        return bool(exists == 1)

    async def _set_cooldown(self, camera_id: str) -> None:
        """Set cooldown flag for camera.

        Args:
            camera_id: Camera identifier
        """
        key = self._cooldown_key(camera_id)
        await self.redis.set(key, "1", expire=self.cooldown_seconds)

    async def track_detection(
        self,
        camera_id: str,
        detection_type: str,
        confidence: float,
    ) -> TrackingResult:
        """Track a smoke/fire detection and determine if alert should trigger.

        This method:
        1. Checks existing tracking state for the camera
        2. Increments count if same type within window, else resets
        3. Checks cooldown to suppress duplicate alerts
        4. Returns result with should_alert flag

        Args:
            camera_id: Camera identifier
            detection_type: Type of detection ('smoke' or 'fire')
            confidence: Detection confidence score

        Returns:
            TrackingResult with consecutive count and alert status
        """
        current_time = time.time()
        first_detection_time = datetime.now(UTC)

        # Get existing tracking state
        state = await self._get_tracking_state(camera_id)

        consecutive_count = 1
        should_alert = False

        if state is not None:
            prev_type = state.get("detection_type")
            prev_count = state.get("count", 0)
            prev_last_time = state.get("last_detection_time", 0)
            prev_first_time = state.get("first_detection_time", current_time)

            # Check if same detection type and within time window
            time_since_last = current_time - prev_last_time

            # Add small epsilon (10ms) to handle timing precision in tests
            # This accounts for execution time between time.time() calls
            window_with_epsilon = self.window_seconds + 0.01

            if prev_type == detection_type and time_since_last <= window_with_epsilon:
                # Continue the sequence
                consecutive_count = prev_count + 1
                first_detection_time = datetime.fromtimestamp(prev_first_time, tz=UTC)
            # else: Different type or outside window - reset to 1

        # Update tracking state
        await self._set_tracking_state(
            camera_id=camera_id,
            detection_type=detection_type,
            count=consecutive_count,
            first_detection_time=first_detection_time.timestamp(),
            last_detection_time=current_time,
        )

        # Determine if we should alert
        if consecutive_count >= self.consecutive_required:
            # Check cooldown
            in_cooldown = await self._is_in_cooldown(camera_id)
            if not in_cooldown:
                should_alert = True
                # Set cooldown to prevent rapid-fire alerts
                await self._set_cooldown(camera_id)
            # else: Alert suppressed by cooldown

        logger.debug(
            "Tracked smoke/fire detection",
            extra={
                "camera_id": camera_id,
                "detection_type": detection_type,
                "confidence": confidence,
                "consecutive_count": consecutive_count,
                "should_alert": should_alert,
            },
        )

        return TrackingResult(
            camera_id=camera_id,
            detection_type=detection_type,
            confidence=confidence,
            consecutive_count=consecutive_count,
            should_alert=should_alert,
            first_detection_time=first_detection_time,
        )

    async def get_consecutive_count(self, camera_id: str) -> int:
        """Get current consecutive count for a camera.

        Args:
            camera_id: Camera identifier

        Returns:
            Current consecutive count (0 if no tracking state)
        """
        state = await self._get_tracking_state(camera_id)
        if state is None:
            return 0
        return int(state.get("count", 0))

    async def reset_tracking(self, camera_id: str) -> None:
        """Reset tracking state for a camera.

        Args:
            camera_id: Camera identifier
        """
        key = self._tracking_key(camera_id)
        await self.redis.delete(key)


class SmokeFireConsecutiveService:
    """Service for processing smoke/fire detections with consecutive tracking.

    This service wraps the SmokeFireConsecutiveTracker and provides
    a higher-level interface for processing detections and creating alerts.
    """

    def __init__(
        self,
        redis_client: Any = None,
        consecutive_required: int = DEFAULT_CONSECUTIVE_REQUIRED,
    ) -> None:
        """Initialize the service.

        Args:
            redis_client: Redis client instance
            consecutive_required: Number of consecutive detections required
        """
        self.redis = redis_client
        self.tracker = SmokeFireConsecutiveTracker(
            redis_client=redis_client,
            consecutive_required=consecutive_required,
        )

    async def process_smoke_fire_detection(
        self,
        camera_id: str,
        detection_id: int,
        smoke_fire_type: str,
        confidence: float,
    ) -> TrackingResult:
        """Process a smoke/fire detection for consecutive tracking.

        Args:
            camera_id: Camera identifier
            detection_id: Detection database ID
            smoke_fire_type: Type of detection ('smoke' or 'fire')
            confidence: Detection confidence score

        Returns:
            TrackingResult with alert status
        """
        result = await self.tracker.track_detection(
            camera_id=camera_id,
            detection_type=smoke_fire_type,
            confidence=confidence,
        )

        if result.should_alert:
            logger.info(
                "Smoke/fire alert triggered",
                extra={
                    "camera_id": camera_id,
                    "detection_id": detection_id,
                    "smoke_fire_type": smoke_fire_type,
                    "confidence": confidence,
                    "consecutive_count": result.consecutive_count,
                    "severity": result.alert_severity,
                },
            )

        return result


def get_smoke_fire_tracker(redis_client: Any) -> SmokeFireConsecutiveTracker:
    """Factory function to create a SmokeFireConsecutiveTracker.

    Args:
        redis_client: Redis client instance

    Returns:
        Configured SmokeFireConsecutiveTracker instance
    """
    return SmokeFireConsecutiveTracker(redis_client=redis_client)
