"""Unit tests for CalibrationMonitor service (NEM-5535).

Tests the score distribution tracking, tier classification,
drift detection, and Redis-backed windowed queries.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.metrics import _score_to_tier, observe_risk_score_distribution
from backend.services.calibration_monitor import (
    CALIBRATION_SCORES_KEY,
    DEFAULT_TTL_SECONDS,
    CalibrationMonitor,
    CalibrationStatus,
    TierStatus,
    get_calibration_monitor,
    init_calibration_monitor,
    reset_calibration_monitor,
)
from backend.services.calibration_monitor import (
    _score_to_tier as monitor_score_to_tier,
)

# =============================================================================
# Tier Classification Tests
# =============================================================================


class TestScoreToTier:
    """Tests for _score_to_tier mapping function."""

    @pytest.mark.parametrize(
        ("score", "expected_tier"),
        [
            (0, "low"),
            (10, "low"),
            (20, "low"),
            (21, "elevated"),
            (30, "elevated"),
            (40, "elevated"),
            (41, "moderate"),
            (50, "moderate"),
            (60, "moderate"),
            (61, "high"),
            (70, "high"),
            (80, "high"),
            (81, "critical"),
            (90, "critical"),
            (100, "critical"),
        ],
    )
    def test_score_to_tier_boundaries(self, score: int, expected_tier: str) -> None:
        """Test that scores map to correct tiers at boundaries."""
        assert monitor_score_to_tier(score) == expected_tier

    @pytest.mark.parametrize(
        ("score", "expected_tier"),
        [
            (0, "low"),
            (20, "low"),
            (21, "elevated"),
            (40, "elevated"),
            (41, "moderate"),
            (60, "moderate"),
            (61, "high"),
            (80, "high"),
            (81, "critical"),
            (100, "critical"),
        ],
    )
    def test_metrics_score_to_tier_consistency(self, score: int, expected_tier: str) -> None:
        """Test that metrics._score_to_tier matches calibration_monitor._score_to_tier."""
        assert _score_to_tier(score) == expected_tier
        assert _score_to_tier(score) == monitor_score_to_tier(score)


# =============================================================================
# CalibrationMonitor Unit Tests
# =============================================================================


class TestCalibrationMonitor:
    """Tests for CalibrationMonitor class."""

    def _make_redis_mock(self) -> MagicMock:
        """Create a mock RedisClient with async methods."""
        redis = MagicMock()
        redis.zadd = AsyncMock(return_value=1)
        redis.zrangebyscore = AsyncMock(return_value=[])
        redis.zremrangebyscore = AsyncMock(return_value=0)
        # Mock the internal _ensure_connected for expire calls
        inner_client = AsyncMock()
        redis._ensure_connected = MagicMock(return_value=inner_client)
        return redis

    @pytest.mark.asyncio
    async def test_record_score_calls_zadd(self) -> None:
        """Test that record_score adds a score to the Redis sorted set."""
        redis = self._make_redis_mock()
        monitor = CalibrationMonitor(redis_client=redis)

        await monitor.record_score(25)

        redis.zadd.assert_called_once()
        call_args = redis.zadd.call_args
        assert call_args[0][0] == CALIBRATION_SCORES_KEY
        # The mapping should have a key like "timestamp:25"
        mapping = call_args[0][1]
        assert len(mapping) == 1
        member = next(iter(mapping.keys()))
        assert member.endswith(":25")

    @pytest.mark.asyncio
    async def test_record_score_sets_ttl(self) -> None:
        """Test that record_score refreshes TTL on the Redis key."""
        redis = self._make_redis_mock()
        monitor = CalibrationMonitor(redis_client=redis)

        await monitor.record_score(50)

        inner_client = redis._ensure_connected()
        inner_client.expire.assert_called_once_with(CALIBRATION_SCORES_KEY, DEFAULT_TTL_SECONDS)

    @pytest.mark.asyncio
    async def test_record_score_handles_redis_error(self) -> None:
        """Test that record_score gracefully handles Redis errors."""
        redis = self._make_redis_mock()
        redis.zadd = AsyncMock(side_effect=Exception("Connection refused"))
        monitor = CalibrationMonitor(redis_client=redis)

        # Should not raise
        await monitor.record_score(50)

    @pytest.mark.asyncio
    async def test_check_calibration_empty_window(self) -> None:
        """Test check_calibration with no scores returns zeros."""
        redis = self._make_redis_mock()
        monitor = CalibrationMonitor(redis_client=redis)

        status = await monitor.check_calibration()

        assert status.total_scores == 0
        assert len(status.tiers) == 5
        # All tiers should show 0% actual
        for tier in status.tiers:
            assert tier.actual_pct == 0.0

    @pytest.mark.asyncio
    async def test_check_calibration_target_distribution(self) -> None:
        """Test check_calibration with a distribution matching the target."""
        redis = self._make_redis_mock()
        now = time.time()

        # Create 100 scores matching the target distribution:
        # 85 low (0-20), 10 elevated (21-40), 3 moderate (41-60),
        # 1 high (61-80), 1 critical (81-100)
        members = []
        for i in range(85):
            members.append(f"{now + i}:{10}")  # low
        for i in range(10):
            members.append(f"{now + 85 + i}:{30}")  # elevated
        for i in range(3):
            members.append(f"{now + 95 + i}:{50}")  # moderate
        members.append(f"{now + 98}:{70}")  # high
        members.append(f"{now + 99}:{90}")  # critical

        redis.zrangebyscore = AsyncMock(return_value=members)
        monitor = CalibrationMonitor(redis_client=redis)

        status = await monitor.check_calibration()

        assert status.total_scores == 100
        assert not status.is_drifting
        assert status.drifting_tiers == []

        # Check tier percentages
        tier_map = {t.tier: t for t in status.tiers}
        assert tier_map["low"].actual_pct == 85.0
        assert tier_map["elevated"].actual_pct == 10.0
        assert tier_map["moderate"].actual_pct == 3.0
        assert tier_map["high"].actual_pct == 1.0
        assert tier_map["critical"].actual_pct == 1.0

    @pytest.mark.asyncio
    async def test_check_calibration_detects_drift(self) -> None:
        """Test that drift is detected when tier percentages deviate beyond threshold."""
        redis = self._make_redis_mock()
        now = time.time()

        # Create 100 scores with heavy drift: 50% low instead of 85%
        members = []
        for i in range(50):
            members.append(f"{now + i}:{10}")  # low
        for i in range(30):
            members.append(f"{now + 50 + i}:{30}")  # elevated (30% vs 10% target)
        for i in range(15):
            members.append(f"{now + 80 + i}:{50}")  # moderate (15% vs 3% target)
        for i in range(3):
            members.append(f"{now + 95 + i}:{70}")  # high (3% vs 1% target)
        for i in range(2):
            members.append(f"{now + 98 + i}:{90}")  # critical (2% vs 1% target)

        redis.zrangebyscore = AsyncMock(return_value=members)
        monitor = CalibrationMonitor(redis_client=redis)

        status = await monitor.check_calibration()

        assert status.total_scores == 100
        assert status.is_drifting
        # low tier has 50% vs 85% target = 35% deviation
        assert "low" in status.drifting_tiers
        # elevated tier has 30% vs 10% target = 20% deviation
        assert "elevated" in status.drifting_tiers
        # moderate tier has 15% vs 3% target = 12% deviation
        assert "moderate" in status.drifting_tiers

    @pytest.mark.asyncio
    async def test_is_drifting_returns_bool(self) -> None:
        """Test that is_drifting returns a simple boolean."""
        redis = self._make_redis_mock()
        monitor = CalibrationMonitor(redis_client=redis)

        result = await monitor.is_drifting()
        # With empty window, all tiers at 0% will drift from target
        # (low target is 85%, actual is 0%, deviation is 85%)
        # But with 0 scores, deviation is target itself
        # Actually with 0 scores: actual_pct is 0, target is 85 for low,
        # deviation is 85 > 5 threshold -> drifting
        # This is correct because having no data is a form of drift.
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_custom_drift_threshold(self) -> None:
        """Test with a custom drift threshold."""
        redis = self._make_redis_mock()
        now = time.time()

        # 90 low, 10 elevated => low is at 90% vs 85% target = 5% deviation
        members = []
        for i in range(90):
            members.append(f"{now + i}:{10}")
        for i in range(10):
            members.append(f"{now + 90 + i}:{30}")

        redis.zrangebyscore = AsyncMock(return_value=members)

        # With default threshold of 5%, low (5% dev) is right at boundary
        # and other tiers (moderate=0% vs 3%, high=0% vs 1%, critical=0% vs 1%)
        # would not drift since they are small deviations
        # But moderate/high/critical deviations are < 5%, so only the zero vs non-zero matters

        # With threshold of 10%, 5% deviation is not drifting
        monitor = CalibrationMonitor(redis_client=redis, drift_threshold_pct=10.0)
        status = await monitor.check_calibration()

        # low: 90% vs 85% = 5% deviation < 10% threshold -> not drifting
        # elevated: 10% vs 10% = 0% deviation -> not drifting
        # moderate: 0% vs 3% = 3% deviation < 10% threshold -> not drifting
        # high: 0% vs 1% = 1% deviation < 10% threshold -> not drifting
        # critical: 0% vs 1% = 1% deviation < 10% threshold -> not drifting
        assert not status.is_drifting

    @pytest.mark.asyncio
    async def test_cleanup_expired_scores(self) -> None:
        """Test that expired scores are cleaned up."""
        redis = self._make_redis_mock()
        redis.zremrangebyscore = AsyncMock(return_value=5)
        monitor = CalibrationMonitor(redis_client=redis, window_seconds=3600)

        await monitor._cleanup_expired()

        redis.zremrangebyscore.assert_called_once()
        call_args = redis.zremrangebyscore.call_args
        assert call_args[0][0] == CALIBRATION_SCORES_KEY
        assert call_args[0][1] == "-inf"
        # The cutoff should be approximately now - 3600

    @pytest.mark.asyncio
    async def test_get_scores_in_window_parses_members(self) -> None:
        """Test score extraction from Redis sorted set members."""
        redis = self._make_redis_mock()
        now = time.time()
        redis.zrangebyscore = AsyncMock(
            return_value=[
                f"{now}:15",
                f"{now + 1}:42.5",
                f"{now + 2}:88",
            ]
        )
        monitor = CalibrationMonitor(redis_client=redis)

        scores = await monitor._get_scores_in_window()

        assert len(scores) == 3
        assert scores[0] == 15.0
        assert scores[1] == 42.5
        assert scores[2] == 88.0

    @pytest.mark.asyncio
    async def test_get_scores_handles_malformed_members(self) -> None:
        """Test that malformed members are skipped gracefully."""
        redis = self._make_redis_mock()
        now = time.time()
        redis.zrangebyscore = AsyncMock(
            return_value=[
                f"{now}:15",
                "malformed_entry",  # no colon
                f"{now + 2}:88",
            ]
        )
        monitor = CalibrationMonitor(redis_client=redis)

        scores = await monitor._get_scores_in_window()

        # Should get 2 valid scores, skipping the malformed one
        assert len(scores) == 2
        assert scores[0] == 15.0
        assert scores[1] == 88.0

    def test_compute_tier_percentages_empty(self) -> None:
        """Test tier percentage computation with empty scores."""
        redis = self._make_redis_mock()
        monitor = CalibrationMonitor(redis_client=redis)

        pcts = monitor._compute_tier_percentages([])
        assert all(v == 0.0 for v in pcts.values())

    def test_compute_tier_percentages_all_low(self) -> None:
        """Test tier percentage computation with all low scores."""
        redis = self._make_redis_mock()
        monitor = CalibrationMonitor(redis_client=redis)

        scores = [5.0, 10.0, 15.0, 20.0]
        pcts = monitor._compute_tier_percentages(scores)

        assert pcts["low"] == 100.0
        assert pcts["elevated"] == 0.0
        assert pcts["moderate"] == 0.0
        assert pcts["high"] == 0.0
        assert pcts["critical"] == 0.0

    def test_compute_tier_percentages_spread(self) -> None:
        """Test tier percentage computation with spread scores."""
        redis = self._make_redis_mock()
        monitor = CalibrationMonitor(redis_client=redis)

        # 2 low, 2 elevated, 2 moderate, 2 high, 2 critical = 10 total
        scores = [10.0, 15.0, 25.0, 35.0, 45.0, 55.0, 65.0, 75.0, 85.0, 95.0]
        pcts = monitor._compute_tier_percentages(scores)

        assert pcts["low"] == 20.0
        assert pcts["elevated"] == 20.0
        assert pcts["moderate"] == 20.0
        assert pcts["high"] == 20.0
        assert pcts["critical"] == 20.0


# =============================================================================
# Singleton/Factory Tests
# =============================================================================


class TestCalibrationMonitorSingleton:
    """Tests for the singleton/factory functions."""

    def setup_method(self) -> None:
        """Reset the global monitor before each test."""
        reset_calibration_monitor()

    def teardown_method(self) -> None:
        """Reset the global monitor after each test."""
        reset_calibration_monitor()

    def test_get_calibration_monitor_returns_none_by_default(self) -> None:
        """Test that get_calibration_monitor returns None before initialization."""
        assert get_calibration_monitor() is None

    def test_init_calibration_monitor_returns_instance(self) -> None:
        """Test that init_calibration_monitor creates and returns an instance."""
        redis = MagicMock()
        monitor = init_calibration_monitor(redis)

        assert isinstance(monitor, CalibrationMonitor)
        assert get_calibration_monitor() is monitor

    def test_reset_calibration_monitor(self) -> None:
        """Test that reset_calibration_monitor clears the global instance."""
        redis = MagicMock()
        init_calibration_monitor(redis)
        assert get_calibration_monitor() is not None

        reset_calibration_monitor()
        assert get_calibration_monitor() is None


# =============================================================================
# CalibrationStatus Tests
# =============================================================================


class TestCalibrationStatus:
    """Tests for CalibrationStatus dataclass."""

    def test_to_dict(self) -> None:
        """Test CalibrationStatus.to_dict produces valid dictionary."""
        status = CalibrationStatus(
            total_scores=100,
            window_seconds=86400,
            drift_threshold_pct=5.0,
            is_drifting=True,
            tiers=[
                TierStatus(
                    tier="low",
                    actual_pct=80.0,
                    target_pct=85.0,
                    deviation_pct=5.0,
                    is_drifting=False,
                ),
                TierStatus(
                    tier="elevated",
                    actual_pct=20.0,
                    target_pct=10.0,
                    deviation_pct=10.0,
                    is_drifting=True,
                ),
            ],
            drifting_tiers=["elevated"],
        )

        d = status.to_dict()

        assert d["total_scores"] == 100
        assert d["is_drifting"] is True
        assert d["drifting_tiers"] == ["elevated"]
        assert len(d["tiers"]) == 2
        assert d["tiers"][0]["tier"] == "low"
        assert d["tiers"][1]["is_drifting"] is True


# =============================================================================
# Prometheus Metrics Integration Tests
# =============================================================================


class TestRiskScoreDistributionMetrics:
    """Tests for the observe_risk_score_distribution function."""

    def test_observe_risk_score_distribution_does_not_raise(self) -> None:
        """Test that observing a score does not raise."""
        # Should not raise for any valid score
        observe_risk_score_distribution(0)
        observe_risk_score_distribution(50)
        observe_risk_score_distribution(100)

    @pytest.mark.parametrize("score", [0, 20, 21, 40, 41, 60, 61, 80, 81, 100])
    def test_observe_risk_score_distribution_boundary_scores(self, score: int) -> None:
        """Test that boundary scores are recorded without error."""
        observe_risk_score_distribution(score)
