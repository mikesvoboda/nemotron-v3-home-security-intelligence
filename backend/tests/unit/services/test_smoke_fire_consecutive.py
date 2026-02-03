"""Unit tests for smoke/fire consecutive detection logic.

Tests cover:
- First detection: consecutive_count = 1, no alert
- Second detection within 5s: consecutive_count = 2, alert triggered
- Detection after 5s gap: consecutive_count resets to 1
- smoke_fire_consecutive_required configuration (default 2)
- Alert cooldown (60-120s) for duplicate alerts
- Multiple cameras tracking separate consecutive counts

These tests are written TDD-style and should FAIL until the consecutive
detection service is implemented (NEM-5298 Phase 5).

Strategy: 2 consecutive detections in 5-second window
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

# ===========================================================================
# Test: Module Import
# ===========================================================================


class TestSmokeFireConsecutiveImport:
    """Test that the consecutive detection module can be imported."""

    def test_service_import(self) -> None:
        """Test that SmokeFireConsecutiveTracker can be imported."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        assert SmokeFireConsecutiveTracker is not None

    def test_config_constants_exist(self) -> None:
        """Test that configuration constants exist."""
        from backend.services.smoke_fire_consecutive import (
            DEFAULT_CONSECUTIVE_REQUIRED,
            DEFAULT_CONSECUTIVE_WINDOW_SECONDS,
        )

        assert DEFAULT_CONSECUTIVE_REQUIRED == 2
        assert DEFAULT_CONSECUTIVE_WINDOW_SECONDS == 5


# ===========================================================================
# Test: First Detection
# ===========================================================================


class TestFirstDetection:
    """Tests for first detection behavior."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=True)
        redis._client = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_first_detection_returns_count_1(self, mock_redis: AsyncMock) -> None:
        """Test that first detection returns consecutive_count = 1."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        tracker = SmokeFireConsecutiveTracker(redis_client=mock_redis)

        result = await tracker.track_detection(
            camera_id="front_yard",
            detection_type="smoke",
            confidence=0.80,
        )

        assert result.consecutive_count == 1

    @pytest.mark.asyncio
    async def test_first_detection_no_alert(self, mock_redis: AsyncMock) -> None:
        """Test that first detection does not trigger alert."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        tracker = SmokeFireConsecutiveTracker(redis_client=mock_redis)

        result = await tracker.track_detection(
            camera_id="front_yard",
            detection_type="smoke",
            confidence=0.80,
        )

        assert result.should_alert is False

    @pytest.mark.asyncio
    async def test_first_detection_stores_in_redis(self, mock_redis: AsyncMock) -> None:
        """Test that first detection stores tracking data in Redis."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        tracker = SmokeFireConsecutiveTracker(redis_client=mock_redis)

        await tracker.track_detection(
            camera_id="front_yard",
            detection_type="smoke",
            confidence=0.80,
        )

        # Should store in Redis with TTL
        mock_redis.set.assert_called()

    @pytest.mark.asyncio
    async def test_first_fire_detection_returns_count_1(self, mock_redis: AsyncMock) -> None:
        """Test that first fire detection also returns count = 1."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        tracker = SmokeFireConsecutiveTracker(redis_client=mock_redis)

        result = await tracker.track_detection(
            camera_id="front_yard",
            detection_type="fire",
            confidence=0.85,
        )

        assert result.consecutive_count == 1


# ===========================================================================
# Test: Second Detection Within Window
# ===========================================================================


class TestSecondDetectionWithinWindow:
    """Tests for second detection within 5-second window."""

    @pytest.fixture
    def mock_redis_with_previous(self) -> AsyncMock:
        """Create a mock Redis client with previous detection."""
        redis = AsyncMock()
        # Return previous detection data (within 5s window)
        previous_data = {
            "detection_type": "smoke",
            "count": 1,
            "first_detection_time": time.time() - 2,  # 2 seconds ago
            "last_detection_time": time.time() - 2,
        }
        redis.get = AsyncMock(return_value=json.dumps(previous_data))
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=True)
        redis._client = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_second_detection_increments_count(
        self, mock_redis_with_previous: AsyncMock
    ) -> None:
        """Test that second detection within window increments count to 2."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        tracker = SmokeFireConsecutiveTracker(redis_client=mock_redis_with_previous)

        result = await tracker.track_detection(
            camera_id="front_yard",
            detection_type="smoke",
            confidence=0.82,
        )

        assert result.consecutive_count == 2

    @pytest.mark.asyncio
    async def test_second_detection_triggers_alert(
        self, mock_redis_with_previous: AsyncMock
    ) -> None:
        """Test that second detection within window triggers alert."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        tracker = SmokeFireConsecutiveTracker(redis_client=mock_redis_with_previous)

        result = await tracker.track_detection(
            camera_id="front_yard",
            detection_type="smoke",
            confidence=0.82,
        )

        assert result.should_alert is True

    @pytest.mark.asyncio
    async def test_third_detection_keeps_alerting(
        self, mock_redis_with_previous: AsyncMock
    ) -> None:
        """Test that third+ detections continue to alert."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        # Mock to return count=2 (already alerted)
        mock_redis_with_previous.get = AsyncMock(
            return_value=json.dumps(
                {
                    "detection_type": "smoke",
                    "count": 2,
                    "first_detection_time": time.time() - 3,
                    "last_detection_time": time.time() - 1,
                }
            )
        )

        tracker = SmokeFireConsecutiveTracker(redis_client=mock_redis_with_previous)

        result = await tracker.track_detection(
            camera_id="front_yard",
            detection_type="smoke",
            confidence=0.85,
        )

        assert result.consecutive_count == 3
        assert result.should_alert is True  # Continue alerting


# ===========================================================================
# Test: Detection After Gap
# ===========================================================================


class TestDetectionAfterGap:
    """Tests for detection after 5-second gap."""

    @pytest.fixture
    def mock_redis_with_old_detection(self) -> AsyncMock:
        """Create a mock Redis client with old detection (>5s)."""
        redis = AsyncMock()
        # Return previous detection data that is too old
        old_data = {
            "detection_type": "smoke",
            "count": 1,
            "first_detection_time": time.time() - 10,  # 10 seconds ago
            "last_detection_time": time.time() - 10,
        }
        redis.get = AsyncMock(return_value=json.dumps(old_data))
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=True)
        redis._client = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_detection_after_gap_resets_count(
        self, mock_redis_with_old_detection: AsyncMock
    ) -> None:
        """Test that detection after 5s gap resets count to 1."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        tracker = SmokeFireConsecutiveTracker(redis_client=mock_redis_with_old_detection)

        result = await tracker.track_detection(
            camera_id="front_yard",
            detection_type="smoke",
            confidence=0.78,
        )

        assert result.consecutive_count == 1

    @pytest.mark.asyncio
    async def test_detection_after_gap_no_alert(
        self, mock_redis_with_old_detection: AsyncMock
    ) -> None:
        """Test that detection after gap does not trigger alert."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        tracker = SmokeFireConsecutiveTracker(redis_client=mock_redis_with_old_detection)

        result = await tracker.track_detection(
            camera_id="front_yard",
            detection_type="smoke",
            confidence=0.78,
        )

        assert result.should_alert is False

    @pytest.mark.asyncio
    async def test_detection_exactly_at_5s_boundary(self) -> None:
        """Test detection exactly at 5-second boundary."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        redis = AsyncMock()
        # Exactly 5 seconds ago
        boundary_data = {
            "detection_type": "smoke",
            "count": 1,
            "first_detection_time": time.time() - 5.0,
            "last_detection_time": time.time() - 5.0,
        }
        redis.get = AsyncMock(return_value=json.dumps(boundary_data))
        redis.set = AsyncMock(return_value=True)
        redis._client = AsyncMock()

        tracker = SmokeFireConsecutiveTracker(redis_client=redis)

        result = await tracker.track_detection(
            camera_id="front_yard",
            detection_type="smoke",
            confidence=0.80,
        )

        # At exactly 5s, should still be within window
        # (window is <= 5s, not < 5s)
        assert result.consecutive_count == 2

    @pytest.mark.asyncio
    async def test_detection_just_after_5s(self) -> None:
        """Test detection just after 5-second window expires."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        redis = AsyncMock()
        # 5.1 seconds ago (just outside window)
        expired_data = {
            "detection_type": "smoke",
            "count": 1,
            "first_detection_time": time.time() - 5.1,
            "last_detection_time": time.time() - 5.1,
        }
        redis.get = AsyncMock(return_value=json.dumps(expired_data))
        redis.set = AsyncMock(return_value=True)
        redis._client = AsyncMock()

        tracker = SmokeFireConsecutiveTracker(redis_client=redis)

        result = await tracker.track_detection(
            camera_id="front_yard",
            detection_type="smoke",
            confidence=0.80,
        )

        # Just after 5s, should reset
        assert result.consecutive_count == 1


# ===========================================================================
# Test: Configuration
# ===========================================================================


class TestConsecutiveConfiguration:
    """Tests for configurable consecutive_required."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock(return_value=True)
        redis._client = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_default_consecutive_required_is_2(self, mock_redis: AsyncMock) -> None:
        """Test that default consecutive_required is 2."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        tracker = SmokeFireConsecutiveTracker(redis_client=mock_redis)

        assert tracker.consecutive_required == 2

    @pytest.mark.asyncio
    async def test_custom_consecutive_required(self, mock_redis: AsyncMock) -> None:
        """Test setting custom consecutive_required."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        tracker = SmokeFireConsecutiveTracker(
            redis_client=mock_redis,
            consecutive_required=3,
        )

        assert tracker.consecutive_required == 3

    @pytest.mark.asyncio
    async def test_alert_only_at_configured_threshold(self, mock_redis: AsyncMock) -> None:
        """Test that alert triggers only at configured threshold."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        # Set threshold to 3
        tracker = SmokeFireConsecutiveTracker(
            redis_client=mock_redis,
            consecutive_required=3,
        )

        # Mock previous count at 2
        mock_redis.get = AsyncMock(
            return_value=json.dumps(
                {
                    "detection_type": "smoke",
                    "count": 2,
                    "first_detection_time": time.time() - 2,
                    "last_detection_time": time.time() - 1,
                }
            )
        )

        result = await tracker.track_detection(
            camera_id="front_yard",
            detection_type="smoke",
            confidence=0.80,
        )

        # Count = 3, which meets threshold
        assert result.consecutive_count == 3
        assert result.should_alert is True

    @pytest.mark.asyncio
    async def test_custom_window_seconds(self, mock_redis: AsyncMock) -> None:
        """Test setting custom window_seconds."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        tracker = SmokeFireConsecutiveTracker(
            redis_client=mock_redis,
            window_seconds=10,  # Custom 10-second window
        )

        assert tracker.window_seconds == 10


# ===========================================================================
# Test: Multiple Cameras
# ===========================================================================


class TestMultipleCameras:
    """Tests for tracking separate cameras."""

    @pytest.fixture
    def mock_redis_multi_camera(self) -> AsyncMock:
        """Create a mock Redis client for multi-camera testing."""
        redis = AsyncMock()
        # Different cameras have different states
        redis.get = AsyncMock(side_effect=lambda _key: None)  # No previous detections
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=True)
        redis._client = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_cameras_tracked_independently(self, mock_redis_multi_camera: AsyncMock) -> None:
        """Test that different cameras have independent counts."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        tracker = SmokeFireConsecutiveTracker(redis_client=mock_redis_multi_camera)

        # First detection on camera A
        result_a = await tracker.track_detection(
            camera_id="front_yard",
            detection_type="smoke",
            confidence=0.80,
        )

        # First detection on camera B
        result_b = await tracker.track_detection(
            camera_id="back_yard",
            detection_type="smoke",
            confidence=0.78,
        )

        # Both should be count = 1 (independent)
        assert result_a.consecutive_count == 1
        assert result_b.consecutive_count == 1

    @pytest.mark.asyncio
    async def test_camera_redis_key_format(self, mock_redis_multi_camera: AsyncMock) -> None:
        """Test that Redis keys include camera_id."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        tracker = SmokeFireConsecutiveTracker(redis_client=mock_redis_multi_camera)

        await tracker.track_detection(
            camera_id="front_yard",
            detection_type="smoke",
            confidence=0.80,
        )

        # Redis set should have been called with a key containing camera_id
        call_args = str(mock_redis_multi_camera.set.call_args)
        assert "front_yard" in call_args or "smoke_fire" in call_args


# ===========================================================================
# Test: Detection Type Matching
# ===========================================================================


class TestDetectionTypeMatching:
    """Tests for matching detection types in consecutive tracking."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock(return_value=True)
        redis._client = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_smoke_then_fire_resets_count(self, mock_redis: AsyncMock) -> None:
        """Test that switching from smoke to fire resets count."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        # Previous detection was smoke
        mock_redis.get = AsyncMock(
            return_value=json.dumps(
                {
                    "detection_type": "smoke",
                    "count": 1,
                    "first_detection_time": time.time() - 2,
                    "last_detection_time": time.time() - 2,
                }
            )
        )

        tracker = SmokeFireConsecutiveTracker(redis_client=mock_redis)

        # Now detect fire
        result = await tracker.track_detection(
            camera_id="front_yard",
            detection_type="fire",  # Different type
            confidence=0.90,
        )

        # Should reset count since type changed
        assert result.consecutive_count == 1

    @pytest.mark.asyncio
    async def test_same_type_continues_count(self, mock_redis: AsyncMock) -> None:
        """Test that same detection type continues count."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        # Previous detection was smoke
        mock_redis.get = AsyncMock(
            return_value=json.dumps(
                {
                    "detection_type": "smoke",
                    "count": 1,
                    "first_detection_time": time.time() - 2,
                    "last_detection_time": time.time() - 2,
                }
            )
        )

        tracker = SmokeFireConsecutiveTracker(redis_client=mock_redis)

        # Now detect smoke again
        result = await tracker.track_detection(
            camera_id="front_yard",
            detection_type="smoke",  # Same type
            confidence=0.82,
        )

        # Should continue count
        assert result.consecutive_count == 2


# ===========================================================================
# Test: TrackingResult Dataclass
# ===========================================================================


class TestTrackingResult:
    """Tests for TrackingResult dataclass."""

    def test_tracking_result_fields(self) -> None:
        """Test that TrackingResult has required fields."""
        from backend.services.smoke_fire_consecutive import TrackingResult

        result = TrackingResult(
            camera_id="front_yard",
            detection_type="smoke",
            confidence=0.80,
            consecutive_count=2,
            should_alert=True,
            first_detection_time=datetime.now(UTC),
        )

        assert result.camera_id == "front_yard"
        assert result.detection_type == "smoke"
        assert result.confidence == 0.80
        assert result.consecutive_count == 2
        assert result.should_alert is True

    def test_tracking_result_to_dict(self) -> None:
        """Test that TrackingResult can be serialized."""
        from backend.services.smoke_fire_consecutive import TrackingResult

        result = TrackingResult(
            camera_id="front_yard",
            detection_type="fire",
            confidence=0.88,
            consecutive_count=2,
            should_alert=True,
            first_detection_time=datetime.now(UTC),
        )

        data = result.to_dict()

        assert data["camera_id"] == "front_yard"
        assert data["detection_type"] == "fire"
        assert data["consecutive_count"] == 2
        assert data["should_alert"] is True


# ===========================================================================
# Test: Alert Cooldown
# ===========================================================================


class TestAlertCooldown:
    """Tests for alert cooldown to prevent duplicate alerts."""

    @pytest.fixture
    def mock_redis_with_cooldown(self) -> AsyncMock:
        """Create a mock Redis client with cooldown tracking."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock(return_value=True)
        redis.exists = AsyncMock(return_value=0)
        redis._client = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_alert_sets_cooldown(self, mock_redis_with_cooldown: AsyncMock) -> None:
        """Test that triggering an alert sets a cooldown."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        # Set up to trigger alert (count=2)
        mock_redis_with_cooldown.get = AsyncMock(
            return_value=json.dumps(
                {
                    "detection_type": "smoke",
                    "count": 1,
                    "first_detection_time": time.time() - 2,
                    "last_detection_time": time.time() - 2,
                }
            )
        )

        tracker = SmokeFireConsecutiveTracker(redis_client=mock_redis_with_cooldown)

        await tracker.track_detection(
            camera_id="front_yard",
            detection_type="smoke",
            confidence=0.80,
        )

        # Should have set a cooldown key in Redis
        # The implementation should call set with a cooldown key
        assert mock_redis_with_cooldown.set.call_count >= 1

    @pytest.mark.asyncio
    async def test_alert_suppressed_during_cooldown(
        self, mock_redis_with_cooldown: AsyncMock
    ) -> None:
        """Test that alerts are suppressed during cooldown period."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        # Cooldown is active
        mock_redis_with_cooldown.exists = AsyncMock(return_value=1)

        # Set up consecutive count that would normally trigger alert
        mock_redis_with_cooldown.get = AsyncMock(
            return_value=json.dumps(
                {
                    "detection_type": "smoke",
                    "count": 1,
                    "first_detection_time": time.time() - 2,
                    "last_detection_time": time.time() - 2,
                }
            )
        )

        tracker = SmokeFireConsecutiveTracker(redis_client=mock_redis_with_cooldown)

        result = await tracker.track_detection(
            camera_id="front_yard",
            detection_type="smoke",
            confidence=0.80,
        )

        # Count should increment but alert should be suppressed
        assert result.consecutive_count == 2
        assert result.should_alert is False  # Suppressed by cooldown

    @pytest.mark.asyncio
    async def test_cooldown_duration_configurable(
        self, mock_redis_with_cooldown: AsyncMock
    ) -> None:
        """Test that cooldown duration is configurable."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        tracker = SmokeFireConsecutiveTracker(
            redis_client=mock_redis_with_cooldown,
            cooldown_seconds=120,  # 2 minutes
        )

        assert tracker.cooldown_seconds == 120

    @pytest.mark.asyncio
    async def test_default_cooldown_is_60_to_120_seconds(
        self, mock_redis_with_cooldown: AsyncMock
    ) -> None:
        """Test that default cooldown is between 60-120 seconds."""
        from backend.services.smoke_fire_consecutive import SmokeFireConsecutiveTracker

        tracker = SmokeFireConsecutiveTracker(redis_client=mock_redis_with_cooldown)

        # Default should be in the 60-120 second range
        assert 60 <= tracker.cooldown_seconds <= 120


# ===========================================================================
# Test: Integration with Alert Creation
# ===========================================================================


class TestConsecutiveAlertIntegration:
    """Tests for integration with alert creation."""

    @pytest.mark.asyncio
    async def test_should_alert_returns_severity(self) -> None:
        """Test that should_alert result includes severity."""
        from backend.services.smoke_fire_consecutive import TrackingResult

        result = TrackingResult(
            camera_id="front_yard",
            detection_type="fire",
            confidence=0.90,
            consecutive_count=2,
            should_alert=True,
            first_detection_time=datetime.now(UTC),
        )

        # Fire should have CRITICAL severity
        assert result.alert_severity == "critical"

    @pytest.mark.asyncio
    async def test_smoke_alert_has_high_severity(self) -> None:
        """Test that smoke alert has HIGH severity."""
        from backend.services.smoke_fire_consecutive import TrackingResult

        result = TrackingResult(
            camera_id="front_yard",
            detection_type="smoke",
            confidence=0.80,
            consecutive_count=2,
            should_alert=True,
            first_detection_time=datetime.now(UTC),
        )

        # Smoke should have HIGH severity (fire is CRITICAL)
        assert result.alert_severity == "high"

    @pytest.mark.asyncio
    async def test_fire_alert_has_critical_severity(self) -> None:
        """Test that fire alert has CRITICAL severity."""
        from backend.services.smoke_fire_consecutive import TrackingResult

        result = TrackingResult(
            camera_id="front_yard",
            detection_type="fire",
            confidence=0.85,
            consecutive_count=2,
            should_alert=True,
            first_detection_time=datetime.now(UTC),
        )

        assert result.alert_severity == "critical"
