"""Alert deduplication service.

This module provides functionality for checking and managing alert deduplication
to prevent alert fatigue. Alerts with the same dedup_key within a cooldown window
are considered duplicates.

Deduplication Key Format:
    The dedup_key is constructed from event characteristics:
    - camera_id: The camera that detected the event
    - object_type: The type of object detected (person, vehicle, etc.)
    - zone: The zone where detection occurred (if available)

    Example: "front_door:person:entry_zone"

Usage:
    from backend.services.alert_dedup import AlertDeduplicationService

    dedup_service = AlertDeduplicationService(session)

    # Check if an alert would be a duplicate
    result = await dedup_service.check_duplicate(
        dedup_key="front_door:person:entry_zone",
        cooldown_seconds=300
    )

    if result.is_duplicate:
        print(f"Duplicate of alert {result.existing_alert_id}")
    else:
        # Create the alert
        alert = await dedup_service.create_alert_if_not_duplicate(...)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Alert, AlertRule, AlertSeverity, AlertStatus

# Constants for dedup_key validation
MAX_DEDUP_KEY_LENGTH = 512
# Use ASCII-only pattern to prevent unicode injection
DEDUP_KEY_ALLOWED_CHARS_PATTERN = (
    r"^[a-zA-Z0-9_\-\.\:]+$"  # ASCII alphanumeric, underscores, hyphens, dots, colons
)


def validate_dedup_key(dedup_key: str) -> str:
    """Validate and normalize a dedup_key.

    Args:
        dedup_key: The deduplication key to validate

    Returns:
        The normalized dedup_key (stripped of leading/trailing whitespace)

    Raises:
        ValueError: If the dedup_key is invalid (empty, too long, or contains
            invalid characters)
    """
    import re

    # Check for None
    if dedup_key is None:
        raise ValueError("dedup_key cannot be None")

    # Normalize by stripping whitespace
    normalized = str(dedup_key).strip()

    # Check for empty string
    if not normalized:
        raise ValueError("dedup_key cannot be empty or whitespace-only")

    # Check length
    if len(normalized) > MAX_DEDUP_KEY_LENGTH:
        raise ValueError(
            f"dedup_key exceeds maximum length of {MAX_DEDUP_KEY_LENGTH} characters "
            f"(got {len(normalized)})"
        )

    # Check for valid characters (alphanumeric, underscores, hyphens, dots, colons)
    if not re.match(DEDUP_KEY_ALLOWED_CHARS_PATTERN, normalized):
        raise ValueError(
            f"dedup_key contains invalid characters. "
            f"Only alphanumeric characters, underscores, hyphens, dots, and colons are allowed. "
            f"Got: {normalized[:50]}{'...' if len(normalized) > 50 else ''}"
        )

    return normalized


@dataclass
class DedupResult:
    """Result of a deduplication check."""

    is_duplicate: bool
    existing_alert: Alert | None = None
    seconds_until_cooldown_expires: int | None = None

    @property
    def existing_alert_id(self) -> str | None:
        """Get the ID of the existing alert if duplicate."""
        return self.existing_alert.id if self.existing_alert else None


def build_dedup_key(
    camera_id: str,
    object_type: str | None = None,
    zone: str | None = None,
) -> str:
    """Build a deduplication key from event characteristics.

    Args:
        camera_id: The camera that detected the event
        object_type: The type of object detected (e.g., "person", "vehicle")
        zone: The zone where detection occurred (optional)

    Returns:
        A dedup key string in format: "camera_id:object_type:zone"
        Components that are None are omitted.

    Example:
        >>> build_dedup_key("front_door", "person", "entry_zone")
        "front_door:person:entry_zone"
        >>> build_dedup_key("front_door", "person")
        "front_door:person"
        >>> build_dedup_key("front_door")
        "front_door"
    """
    parts = [camera_id]
    if object_type:
        parts.append(object_type)
    if zone:
        parts.append(zone)
    return ":".join(parts)


class AlertDeduplicationService:
    """Service for managing alert deduplication.

    This service checks whether an alert with the same dedup_key exists
    within a cooldown window and provides methods for creating alerts
    with automatic deduplication.
    """

    def __init__(self, session: AsyncSession):
        """Initialize the deduplication service.

        Args:
            session: SQLAlchemy async session for database operations
        """
        self.session = session

    async def check_duplicate(
        self,
        dedup_key: str,
        cooldown_seconds: int = 300,
    ) -> DedupResult:
        """Check if an alert with the same dedup_key exists within cooldown.

        Args:
            dedup_key: The deduplication key to check
            cooldown_seconds: Number of seconds for the cooldown window

        Returns:
            DedupResult indicating whether a duplicate exists and details

        Raises:
            ValueError: If dedup_key is invalid (empty, too long, or contains
                invalid characters)
        """
        # Validate and normalize the dedup_key
        dedup_key = validate_dedup_key(dedup_key)

        cutoff_time = datetime.now(UTC) - timedelta(seconds=cooldown_seconds)

        # Find the most recent alert with this dedup_key within the cooldown window
        stmt = (
            select(Alert)
            .where(Alert.dedup_key == dedup_key)
            .where(Alert.created_at >= cutoff_time)
            .order_by(Alert.created_at.desc())
            .limit(1)
        )

        result = await self.session.execute(stmt)
        existing_alert = result.scalar_one_or_none()

        if existing_alert:
            # Calculate seconds until cooldown expires
            alert_age = (datetime.now(UTC) - existing_alert.created_at).total_seconds()
            seconds_remaining = max(0, int(cooldown_seconds - alert_age))

            return DedupResult(
                is_duplicate=True,
                existing_alert=existing_alert,
                seconds_until_cooldown_expires=seconds_remaining,
            )

        return DedupResult(is_duplicate=False)

    async def get_cooldown_for_rule(self, rule_id: str | None) -> int:
        """Get the cooldown seconds for a given rule.

        Args:
            rule_id: The alert rule ID, or None for default cooldown

        Returns:
            Cooldown in seconds (default 300 if no rule or rule not found)
        """
        if rule_id is None:
            return 300  # Default cooldown

        stmt = select(AlertRule).where(AlertRule.id == rule_id)
        result = await self.session.execute(stmt)
        rule = result.scalar_one_or_none()

        if rule:
            return int(rule.cooldown_seconds)

        return 300  # Default if rule not found

    async def create_alert_if_not_duplicate(
        self,
        event_id: int,
        dedup_key: str,
        severity: AlertSeverity = AlertSeverity.MEDIUM,
        rule_id: str | None = None,
        channels: list[str] | None = None,
        alert_metadata: dict | None = None,
        cooldown_seconds: int | None = None,
    ) -> tuple[Alert, bool]:
        """Create an alert if no duplicate exists within the cooldown window.

        This method atomically checks for duplicates and creates a new alert
        if none exists.

        Args:
            event_id: The event ID that triggered this alert
            dedup_key: The deduplication key
            severity: Alert severity level
            rule_id: Optional alert rule ID that matched
            channels: Notification channels to deliver to
            alert_metadata: Additional context for the alert
            cooldown_seconds: Override cooldown (uses rule's cooldown if None)

        Returns:
            Tuple of (Alert, is_new) where is_new is True if a new alert was
            created, False if returning an existing duplicate.

        Raises:
            ValueError: If dedup_key is invalid (empty, too long, or contains
                invalid characters)
        """
        # Validate and normalize the dedup_key
        dedup_key = validate_dedup_key(dedup_key)

        # Determine cooldown
        if cooldown_seconds is None:
            cooldown_seconds = await self.get_cooldown_for_rule(rule_id)

        # Check for duplicates (dedup_key already validated)
        dedup_result = await self.check_duplicate(dedup_key, cooldown_seconds)

        if dedup_result.is_duplicate and dedup_result.existing_alert:
            return dedup_result.existing_alert, False

        # Create new alert
        alert = Alert(
            event_id=event_id,
            rule_id=rule_id,
            severity=severity,
            status=AlertStatus.PENDING,
            dedup_key=dedup_key,
            channels=channels or [],
            alert_metadata=alert_metadata or {},
        )

        self.session.add(alert)
        await self.session.flush()

        return alert, True

    async def get_recent_alerts_for_key(
        self,
        dedup_key: str,
        hours: int = 24,
        limit: int = 10,
    ) -> list[Alert]:
        """Get recent alerts with the same dedup_key.

        Useful for viewing alert history for a specific event pattern.

        Args:
            dedup_key: The deduplication key to search for
            hours: Number of hours to look back
            limit: Maximum number of alerts to return

        Returns:
            List of alerts matching the dedup_key, ordered by most recent first

        Raises:
            ValueError: If dedup_key is invalid (empty, too long, or contains
                invalid characters)
        """
        # Validate and normalize the dedup_key
        dedup_key = validate_dedup_key(dedup_key)

        cutoff_time = datetime.now(UTC) - timedelta(hours=hours)

        stmt = (
            select(Alert)
            .where(Alert.dedup_key == dedup_key)
            .where(Alert.created_at >= cutoff_time)
            .order_by(Alert.created_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_duplicate_stats(
        self,
        hours: int = 24,
    ) -> dict[str, int | float]:
        """Get statistics on duplicate alerts within a time window.

        Args:
            hours: Number of hours to analyze

        Returns:
            Dictionary with statistics:
            - total_alerts: Total alerts created
            - unique_dedup_keys: Number of unique dedup keys
            - potential_duplicates: Alerts that were likely suppressed
        """
        cutoff_time = datetime.now(UTC) - timedelta(hours=hours)

        # Get total alerts
        total_stmt = select(Alert).where(Alert.created_at >= cutoff_time)
        total_result = await self.session.execute(total_stmt)
        total_alerts = len(list(total_result.scalars().all()))

        # Get unique dedup keys
        unique_stmt = select(Alert.dedup_key).where(Alert.created_at >= cutoff_time).distinct()
        unique_result = await self.session.execute(unique_stmt)
        unique_keys = len(list(unique_result.scalars().all()))

        return {
            "total_alerts": total_alerts,
            "unique_dedup_keys": unique_keys,
            "dedup_ratio": round(unique_keys / total_alerts, 2) if total_alerts > 0 else 0.0,
        }
