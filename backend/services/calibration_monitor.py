"""Calibration drift monitor for Nemotron risk score distribution (NEM-5535).

Tracks rolling risk score distribution over a configurable time window
and detects when tier percentages drift beyond acceptable thresholds.

Target distribution:
    - 85% LOW      (0-20)
    - 10% ELEVATED (21-40)
    - 4%  MODERATE (41-60) + HIGH (61-80)
    - 1%  CRITICAL (81-100)

Uses Redis sorted sets keyed by timestamp for efficient windowed queries.
Scores are stored as ``<timestamp>:<score>`` members with the timestamp
as the sorted set score, enabling O(log N) range-based cleanup and queries.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

logger = get_logger(__name__)

# Redis key for the sorted set storing risk scores
CALIBRATION_SCORES_KEY = "hsi:calibration:scores"

# Default time window: 24 hours (in seconds)
DEFAULT_WINDOW_SECONDS = 24 * 60 * 60

# TTL for Redis keys: 48 hours (allows for 24h window + buffer)
DEFAULT_TTL_SECONDS = 48 * 60 * 60

# Maximum acceptable deviation from target percentages (in percentage points)
DEFAULT_DRIFT_THRESHOLD_PCT = 5.0

# Target tier percentages
TARGET_DISTRIBUTION: dict[str, float] = {
    "low": 85.0,
    "elevated": 10.0,
    "moderate": 3.0,
    "high": 1.0,
    "critical": 1.0,
}

# Tier score boundaries (inclusive upper bound)
TIER_BOUNDARIES: list[tuple[str, int, int]] = [
    ("low", 0, 20),
    ("elevated", 21, 40),
    ("moderate", 41, 60),
    ("high", 61, 80),
    ("critical", 81, 100),
]


def _score_to_tier(score: int | float) -> str:
    """Map a risk score to a tier name.

    Args:
        score: Risk score (0-100)

    Returns:
        Tier name string
    """
    for tier_name, lower, upper in TIER_BOUNDARIES:
        if lower <= score <= upper:
            return tier_name
    return "critical"  # Fallback for scores > 100


@dataclass
class TierStatus:
    """Status of a single risk tier."""

    tier: str
    actual_pct: float
    target_pct: float
    deviation_pct: float
    is_drifting: bool


@dataclass
class CalibrationStatus:
    """Complete calibration status with all tier information."""

    total_scores: int
    window_seconds: int
    drift_threshold_pct: float
    is_drifting: bool
    tiers: list[TierStatus] = field(default_factory=list)
    drifting_tiers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_scores": self.total_scores,
            "window_seconds": self.window_seconds,
            "drift_threshold_pct": self.drift_threshold_pct,
            "is_drifting": self.is_drifting,
            "drifting_tiers": self.drifting_tiers,
            "tiers": [
                {
                    "tier": t.tier,
                    "actual_pct": round(t.actual_pct, 2),
                    "target_pct": t.target_pct,
                    "deviation_pct": round(t.deviation_pct, 2),
                    "is_drifting": t.is_drifting,
                }
                for t in self.tiers
            ],
        }


class CalibrationMonitor:
    """Monitor for Nemotron risk score distribution calibration drift.

    Tracks risk scores in a Redis sorted set keyed by timestamp and computes
    rolling tier percentages over a configurable window. Detects when any tier
    deviates from the target distribution by more than the configured threshold.

    Args:
        redis_client: Connected RedisClient instance
        window_seconds: Rolling window size in seconds (default: 24 hours)
        ttl_seconds: TTL for Redis keys (default: 48 hours)
        drift_threshold_pct: Maximum acceptable deviation in percentage points
        target_distribution: Target tier percentages (overrides defaults)
    """

    def __init__(
        self,
        redis_client: RedisClient,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        drift_threshold_pct: float = DEFAULT_DRIFT_THRESHOLD_PCT,
        target_distribution: dict[str, float] | None = None,
    ) -> None:
        self._redis = redis_client
        self._window_seconds = window_seconds
        self._ttl_seconds = ttl_seconds
        self._drift_threshold_pct = drift_threshold_pct
        self._target = target_distribution or TARGET_DISTRIBUTION

    async def record_score(self, score: int | float) -> None:
        """Record a risk score for calibration monitoring.

        Stores the score in a Redis sorted set with the current timestamp
        as the score (for range queries). The member is ``<timestamp>:<score>``
        to ensure uniqueness.

        Also sets a TTL on the key to prevent unbounded growth.

        Args:
            score: Risk score from Nemotron analysis (0-100)
        """
        now = time.time()
        # Use timestamp:score as member to ensure uniqueness
        member = f"{now}:{score}"

        try:
            await self._redis.zadd(CALIBRATION_SCORES_KEY, {member: now})
            # Refresh TTL on every write to keep the key alive
            client = self._redis._ensure_connected()
            await client.expire(CALIBRATION_SCORES_KEY, self._ttl_seconds)
        except Exception:
            logger.warning(
                "Failed to record calibration score in Redis",
                exc_info=True,
                extra={"score": score},
            )

    async def _cleanup_expired(self) -> None:
        """Remove scores older than the time window from the sorted set."""
        cutoff = time.time() - self._window_seconds
        try:
            removed = await self._redis.zremrangebyscore(CALIBRATION_SCORES_KEY, "-inf", cutoff)
            if removed > 0:
                logger.debug(f"Removed {removed} expired calibration scores")
        except Exception:
            logger.warning(
                "Failed to cleanup expired calibration scores",
                exc_info=True,
            )

    async def _get_scores_in_window(self) -> list[float]:
        """Retrieve all scores within the current time window.

        Returns:
            List of risk scores (as floats) within the window.
        """
        # First clean up expired entries
        await self._cleanup_expired()

        cutoff = time.time() - self._window_seconds
        try:
            members = await self._redis.zrangebyscore(CALIBRATION_SCORES_KEY, cutoff, "+inf")
            scores = []
            for member in members:
                # Parse score from "timestamp:score" format
                try:
                    parts = member.rsplit(":", 1)
                    scores.append(float(parts[1]))
                except (IndexError, ValueError):
                    logger.warning(f"Invalid calibration score member: {member}")
            return scores
        except Exception:
            logger.warning(
                "Failed to retrieve calibration scores from Redis",
                exc_info=True,
            )
            return []

    def _compute_tier_percentages(self, scores: list[float]) -> dict[str, float]:
        """Compute the percentage of scores in each tier.

        Args:
            scores: List of risk scores

        Returns:
            Dictionary mapping tier names to their percentage of total scores
        """
        total = len(scores)
        if total == 0:
            return dict.fromkeys(self._target, 0.0)

        counts: dict[str, int] = dict.fromkeys(self._target, 0)
        for score in scores:
            tier = _score_to_tier(score)
            if tier in counts:
                counts[tier] += 1

        return {tier: (count / total) * 100.0 for tier, count in counts.items()}

    async def check_calibration(self) -> CalibrationStatus:
        """Compute the current tier percentages and detect drift.

        Returns:
            CalibrationStatus with current distribution, target, and drift info
        """
        scores = await self._get_scores_in_window()
        actual_pcts = self._compute_tier_percentages(scores)

        tiers: list[TierStatus] = []
        drifting_tiers: list[str] = []

        for tier_name, target_pct in self._target.items():
            actual = actual_pcts.get(tier_name, 0.0)
            deviation = abs(actual - target_pct)
            is_tier_drifting = deviation > self._drift_threshold_pct

            tiers.append(
                TierStatus(
                    tier=tier_name,
                    actual_pct=actual,
                    target_pct=target_pct,
                    deviation_pct=deviation,
                    is_drifting=is_tier_drifting,
                )
            )

            if is_tier_drifting:
                drifting_tiers.append(tier_name)

        is_drifting = len(drifting_tiers) > 0

        status = CalibrationStatus(
            total_scores=len(scores),
            window_seconds=self._window_seconds,
            drift_threshold_pct=self._drift_threshold_pct,
            is_drifting=is_drifting,
            tiers=tiers,
            drifting_tiers=drifting_tiers,
        )

        if is_drifting:
            logger.warning(
                "Calibration drift detected",
                extra={
                    "drifting_tiers": drifting_tiers,
                    "total_scores": len(scores),
                    "distribution": {
                        t.tier: {
                            "actual": round(t.actual_pct, 2),
                            "target": t.target_pct,
                            "deviation": round(t.deviation_pct, 2),
                        }
                        for t in tiers
                    },
                },
            )

        return status

    async def is_drifting(self) -> bool:
        """Check if any tier's percentage deviates beyond the threshold.

        Returns:
            True if any tier has drifted beyond the configured threshold.
        """
        status = await self.check_calibration()
        return status.is_drifting


# =============================================================================
# Singleton / Factory
# =============================================================================

_calibration_monitor: CalibrationMonitor | None = None


def get_calibration_monitor() -> CalibrationMonitor | None:
    """Get the global CalibrationMonitor instance.

    Returns None if not initialized (e.g., Redis not available).

    Returns:
        CalibrationMonitor instance or None
    """
    return _calibration_monitor


def init_calibration_monitor(redis_client: RedisClient) -> CalibrationMonitor:
    """Initialize the global CalibrationMonitor with a Redis client.

    Args:
        redis_client: Connected RedisClient instance

    Returns:
        Initialized CalibrationMonitor instance
    """
    global _calibration_monitor  # noqa: PLW0603
    _calibration_monitor = CalibrationMonitor(redis_client=redis_client)
    return _calibration_monitor


def reset_calibration_monitor() -> None:
    """Reset the global CalibrationMonitor (for testing)."""
    global _calibration_monitor  # noqa: PLW0603
    _calibration_monitor = None
