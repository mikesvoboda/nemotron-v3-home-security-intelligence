"""Repository for Alert and AlertRule entity database operations.

This module provides repositories for managing alerts and alert rules.

Example:
    async with get_session() as session:
        repo = AlertRepository(session)
        alerts = await repo.get_by_status("pending")

        rule_repo = AlertRuleRepository(session)
        enabled_rules = await rule_repo.get_enabled_rules()
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.models import Alert, AlertRule, AlertSeverity, AlertStatus
from backend.repositories.base import Repository

if TYPE_CHECKING:
    from collections.abc import Sequence


class AlertRepository(Repository[Alert]):
    """Repository for Alert entity database operations.

    Provides CRUD operations inherited from Repository base class plus
    alert-specific query methods.

    Attributes:
        model_class: Set to Alert for type inference and query construction.

    Example:
        async with get_session() as session:
            repo = AlertRepository(session)

            # Get alert by ID
            alert = await repo.get_by_id("alert-uuid")

            # Get pending alerts
            pending = await repo.get_by_status(AlertStatus.PENDING)

            # Get alerts for an event
            alerts = await repo.get_by_event_id(123)
    """

    model_class = Alert

    async def get_by_event_id(
        self,
        event_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Alert]:
        """Get alerts for a specific event with pagination.

        Args:
            event_id: The event ID to filter by.
            limit: Maximum number of alerts to return (default: 100).
            offset: Number of alerts to skip (default: 0).

        Returns:
            A sequence of alerts associated with the event.
        """
        stmt = (
            select(Alert)
            .where(Alert.event_id == event_id)
            .order_by(Alert.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_rule_id(
        self,
        rule_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Alert]:
        """Get alerts triggered by a specific rule with pagination.

        Args:
            rule_id: The alert rule ID to filter by.
            limit: Maximum number of alerts to return (default: 100).
            offset: Number of alerts to skip (default: 0).

        Returns:
            A sequence of alerts triggered by the rule.
        """
        stmt = (
            select(Alert)
            .where(Alert.rule_id == rule_id)
            .order_by(Alert.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_status(
        self,
        status: AlertStatus | str,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Alert]:
        """Get alerts with a specific status with pagination.

        Args:
            status: The status to filter by (e.g., AlertStatus.PENDING or "pending").
            limit: Maximum number of alerts to return (default: 100).
            offset: Number of alerts to skip (default: 0).

        Returns:
            A sequence of alerts with the specified status.
        """
        status_value = status.value if isinstance(status, AlertStatus) else status
        stmt = (
            select(Alert)
            .where(Alert.status == status_value)
            .order_by(Alert.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_severity(
        self,
        severity: AlertSeverity | str,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Alert]:
        """Get alerts with a specific severity with pagination.

        Args:
            severity: The severity to filter by (e.g., AlertSeverity.HIGH or "high").
            limit: Maximum number of alerts to return (default: 100).
            offset: Number of alerts to skip (default: 0).

        Returns:
            A sequence of alerts with the specified severity.
        """
        severity_value = severity.value if isinstance(severity, AlertSeverity) else severity
        stmt = (
            select(Alert)
            .where(Alert.severity == severity_value)
            .order_by(Alert.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_dedup_key(
        self,
        dedup_key: str,
        since: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Alert]:
        """Get alerts with a specific dedup key with pagination, optionally filtered by time.

        Useful for checking if an alert has already been triggered recently
        to prevent duplicate alerts.

        Args:
            dedup_key: The deduplication key to search for.
            since: Optional datetime to only return alerts created after this time.
                   If None, returns all alerts with the dedup_key.
            limit: Maximum number of alerts to return (default: 100).
            offset: Number of alerts to skip (default: 0).

        Returns:
            A sequence of alerts matching the dedup key.
        """
        stmt = select(Alert).where(Alert.dedup_key == dedup_key)
        if since:
            stmt = stmt.where(Alert.created_at >= since)
        stmt = stmt.order_by(Alert.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_recent(self, limit: int = 100) -> Sequence[Alert]:
        """Get the most recent alerts.

        Args:
            limit: Maximum number of alerts to return (default: 100).

        Returns:
            A sequence of the most recent alerts.
        """
        stmt = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_undelivered(self) -> Sequence[Alert]:
        """Get all alerts that haven't been delivered yet.

        Returns:
            A sequence of alerts with status=PENDING and delivered_at=NULL.
        """
        stmt = (
            select(Alert)
            .where(Alert.status == AlertStatus.PENDING.value, Alert.delivered_at.is_(None))
            .order_by(Alert.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def mark_delivered(self, alert_id: str) -> Alert | None:
        """Mark an alert as delivered.

        Args:
            alert_id: The ID of the alert to mark as delivered.

        Returns:
            The updated Alert if found, None if the alert doesn't exist.
        """
        alert = await self.get_by_id(alert_id)
        if alert is None:
            return None

        alert.status = AlertStatus.DELIVERED
        alert.delivered_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(alert)
        return alert

    async def mark_acknowledged(self, alert_id: str) -> Alert | None:
        """Mark an alert as acknowledged.

        Args:
            alert_id: The ID of the alert to acknowledge.

        Returns:
            The updated Alert if found, None if the alert doesn't exist.
        """
        alert = await self.get_by_id(alert_id)
        if alert is None:
            return None

        alert.status = AlertStatus.ACKNOWLEDGED
        await self.session.flush()
        await self.session.refresh(alert)
        return alert

    async def mark_dismissed(self, alert_id: str) -> Alert | None:
        """Mark an alert as dismissed.

        Args:
            alert_id: The ID of the alert to dismiss.

        Returns:
            The updated Alert if found, None if the alert doesn't exist.
        """
        alert = await self.get_by_id(alert_id)
        if alert is None:
            return None

        alert.status = AlertStatus.DISMISSED
        await self.session.flush()
        await self.session.refresh(alert)
        return alert

    async def check_duplicate(self, dedup_key: str, cooldown_seconds: int) -> bool:
        """Check if an alert with the same dedup_key was triggered within cooldown period.

        Args:
            dedup_key: The deduplication key to check.
            cooldown_seconds: The cooldown period in seconds.

        Returns:
            True if a duplicate alert exists within the cooldown period, False otherwise.
        """
        since = datetime.now(UTC) - timedelta(seconds=cooldown_seconds)
        recent_alerts = await self.get_by_dedup_key(dedup_key, since=since)
        return len(recent_alerts) > 0


class AlertRuleRepository(Repository[AlertRule]):
    """Repository for AlertRule entity database operations.

    Provides CRUD operations inherited from Repository base class plus
    alert rule-specific query methods.

    Attributes:
        model_class: Set to AlertRule for type inference and query construction.

    Example:
        async with get_session() as session:
            repo = AlertRuleRepository(session)

            # Get rule by ID
            rule = await repo.get_by_id("rule-uuid")

            # Get all enabled rules
            enabled = await repo.get_enabled_rules()

            # Get rules by severity
            high_severity = await repo.get_by_severity(AlertSeverity.HIGH)
    """

    model_class = AlertRule

    async def get_enabled_rules(self) -> Sequence[AlertRule]:
        """Get all enabled alert rules.

        Returns:
            A sequence of alert rules where enabled=True.
        """
        stmt = select(AlertRule).where(AlertRule.enabled == True).order_by(AlertRule.created_at)  # noqa: E712
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_name(self, name: str) -> AlertRule | None:
        """Find an alert rule by its name.

        Args:
            name: The name of the alert rule.

        Returns:
            The AlertRule if found, None otherwise.
        """
        stmt = select(AlertRule).where(AlertRule.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_severity(self, severity: AlertSeverity | str) -> Sequence[AlertRule]:
        """Get all alert rules with a specific severity.

        Args:
            severity: The severity to filter by (e.g., AlertSeverity.HIGH or "high").

        Returns:
            A sequence of alert rules with the specified severity.
        """
        severity_value = severity.value if isinstance(severity, AlertSeverity) else severity
        stmt = (
            select(AlertRule)
            .where(AlertRule.severity == severity_value)
            .order_by(AlertRule.created_at)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def set_enabled(self, rule_id: str, enabled: bool) -> AlertRule | None:
        """Enable or disable an alert rule.

        Args:
            rule_id: The ID of the rule to update.
            enabled: True to enable, False to disable.

        Returns:
            The updated AlertRule if found, None if the rule doesn't exist.
        """
        rule = await self.get_by_id(rule_id)
        if rule is None:
            return None

        rule.enabled = enabled
        await self.session.flush()
        await self.session.refresh(rule)
        return rule

    async def get_rules_for_camera(self, camera_id: str) -> Sequence[AlertRule]:
        """Get all enabled alert rules that apply to a specific camera.

        A rule applies to a camera if:
        - The rule is enabled AND
        - camera_ids is NULL/empty (applies to all cameras) OR camera_id is in camera_ids

        Args:
            camera_id: The camera ID to check.

        Returns:
            A sequence of applicable alert rules.
        """
        stmt = (
            select(AlertRule)
            .where(
                AlertRule.enabled == True,  # noqa: E712
                (AlertRule.camera_ids.is_(None))
                | (AlertRule.camera_ids == [])
                | (AlertRule.camera_ids.contains([camera_id])),
            )
            .order_by(AlertRule.severity.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
