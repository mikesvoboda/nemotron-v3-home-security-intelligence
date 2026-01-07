"""Alert rules evaluation engine.

This module provides the core engine for evaluating alert rules against events
and detections. The engine supports multiple condition types and uses AND logic
to combine conditions within a rule.

Condition Types:
    - risk_threshold: Alert when event risk_score >= threshold
    - object_types: Alert when specific objects detected
    - camera_ids: Only apply rule to specific cameras
    - time_range: Only apply during certain hours
    - zone_ids: Only apply when detection is in specific zones
    - min_confidence: Minimum detection confidence threshold

Usage:
    from backend.services.alert_engine import AlertRuleEngine

    engine = AlertRuleEngine(session, redis_client)
    triggered_rules = await engine.evaluate_event(event, detections)

    for triggered in triggered_rules:
        print(f"Rule {triggered.rule.name} triggered with severity {triggered.severity}")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logging import get_logger
from backend.core.time_utils import utc_now_naive
from backend.models import Alert, AlertRule, AlertSeverity, AlertStatus, Detection, Event
from backend.services.batch_fetch import batch_fetch_detections

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

logger = get_logger(__name__)


# Severity priority for determining which rule takes precedence
SEVERITY_PRIORITY = {
    AlertSeverity.LOW: 0,
    AlertSeverity.MEDIUM: 1,
    AlertSeverity.HIGH: 2,
    AlertSeverity.CRITICAL: 3,
}

# Day name mapping for schedule evaluation
DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


@dataclass(slots=True)
class TriggeredRule:
    """Result of a rule evaluation that matched."""

    rule: AlertRule
    severity: AlertSeverity
    matched_conditions: list[str] = field(default_factory=list)
    dedup_key: str = ""


@dataclass(slots=True)
class EvaluationResult:
    """Complete result of evaluating all rules against an event."""

    triggered_rules: list[TriggeredRule] = field(default_factory=list)
    skipped_rules: list[tuple[AlertRule, str]] = field(default_factory=list)  # (rule, reason)
    highest_severity: AlertSeverity | None = None

    @property
    def has_triggers(self) -> bool:
        """Return True if any rules triggered."""
        return len(self.triggered_rules) > 0


class AlertRuleEngine:
    """Engine for evaluating alert rules against events and detections.

    This engine:
    - Loads all enabled rules from the database
    - Evaluates each rule's conditions against event/detection data
    - Uses AND logic within rules (all conditions must match)
    - Supports multiple rules triggering for the same event
    - Tracks which rule has highest severity for precedence
    - Respects cooldown periods using dedup_key
    """

    def __init__(self, session: AsyncSession, redis_client: RedisClient | None = None):
        """Initialize the alert rule engine.

        Args:
            session: SQLAlchemy async session for database operations
            redis_client: Optional Redis client for cooldown tracking
        """
        self.session = session
        self.redis_client = redis_client

    async def evaluate_event(
        self,
        event: Event,
        detections: list[Detection] | None = None,
        current_time: datetime | None = None,
    ) -> EvaluationResult:
        """Evaluate all enabled rules against an event.

        Args:
            event: The event to evaluate rules against
            detections: Optional list of detections associated with the event.
                       If not provided, will fetch from database using event.detection_ids.
            current_time: Optional override for current time (for testing)

        Returns:
            EvaluationResult with list of triggered rules and evaluation metadata
        """
        if current_time is None:
            current_time = utc_now_naive()

        # Load detections if not provided
        if detections is None:
            detections = await self._load_event_detections(event)

        # Load all enabled rules
        rules = await self._get_enabled_rules()

        result = EvaluationResult()

        for rule in rules:
            try:
                matches, conditions = await self._evaluate_rule(
                    rule, event, detections, current_time
                )

                if matches:
                    # Check cooldown before adding to triggered list
                    dedup_key = self._build_dedup_key(rule, event, detections)
                    is_in_cooldown = await self._check_cooldown(rule, dedup_key, current_time)

                    if is_in_cooldown:
                        result.skipped_rules.append((rule, "in_cooldown"))
                        continue

                    triggered = TriggeredRule(
                        rule=rule,
                        severity=rule.severity,
                        matched_conditions=conditions,
                        dedup_key=dedup_key,
                    )
                    result.triggered_rules.append(triggered)

                    # Track highest severity
                    if result.highest_severity is None or SEVERITY_PRIORITY.get(
                        rule.severity, 0
                    ) > SEVERITY_PRIORITY.get(result.highest_severity, 0):
                        result.highest_severity = rule.severity

            except Exception as e:
                logger.error(f"Error evaluating rule {rule.id}: {e}")
                result.skipped_rules.append((rule, f"evaluation_error: {e}"))

        # Sort triggered rules by severity (highest first)
        result.triggered_rules.sort(
            key=lambda t: SEVERITY_PRIORITY.get(t.severity, 0), reverse=True
        )

        return result

    async def _get_enabled_rules(self) -> list[AlertRule]:
        """Load all enabled alert rules from the database."""
        stmt = select(AlertRule).where(AlertRule.enabled.is_(True))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _load_event_detections(self, event: Event) -> list[Detection]:
        """Load detections for an event from the database."""
        if not event.detection_ids:
            return []

        # Parse detection_ids (stored as JSON array string)
        try:
            detection_id_list = json.loads(event.detection_ids)
            if not isinstance(detection_id_list, list):
                return []
        except (json.JSONDecodeError, TypeError):
            return []

        if not detection_id_list:
            return []

        # Use batch fetching to handle large detection lists efficiently
        return await batch_fetch_detections(self.session, detection_id_list)

    async def _batch_load_detections_for_events(
        self,
        events: list[Event],
    ) -> dict[int, list[Detection]]:
        """Batch load detections for multiple events in a single query.

        This prevents N+1 queries when testing rules against multiple events.
        Uses selectinload pattern: collect all detection IDs, load in one query,
        then map back to events.

        Args:
            events: List of events to load detections for

        Returns:
            Dictionary mapping event.id to list of Detection objects
        """
        # Collect all detection IDs from all events
        all_detection_ids: list[int] = []
        event_detection_map: dict[int, list[int]] = {}

        for event in events:
            if not event.detection_ids:
                event_detection_map[event.id] = []
                continue

            try:
                detection_id_list = json.loads(event.detection_ids)
                if isinstance(detection_id_list, list):
                    int_ids = [int(d) for d in detection_id_list]
                    event_detection_map[event.id] = int_ids
                    all_detection_ids.extend(int_ids)
                else:
                    event_detection_map[event.id] = []
            except (json.JSONDecodeError, TypeError, ValueError):
                event_detection_map[event.id] = []

        if not all_detection_ids:
            return {event.id: [] for event in events}

        # Use batch fetching to handle large detection lists efficiently
        all_detections = await batch_fetch_detections(
            self.session, all_detection_ids, order_by_time=False
        )

        # Create lookup by detection ID
        detection_by_id = {d.id: d for d in all_detections}

        # Map detections back to events
        result_map: dict[int, list[Detection]] = {}
        for event in events:
            detection_ids = event_detection_map.get(event.id, [])
            result_map[event.id] = [
                detection_by_id[did] for did in detection_ids if did in detection_by_id
            ]

        return result_map

    async def _evaluate_rule(
        self,
        rule: AlertRule,
        event: Event,
        detections: list[Detection],
        current_time: datetime,
    ) -> tuple[bool, list[str]]:
        """Evaluate a single rule against an event.

        All conditions must match (AND logic).

        Returns:
            Tuple of (matches, list of matched condition descriptions)
        """
        matched_conditions: list[str] = []

        # Check risk threshold
        if rule.risk_threshold is not None:
            if event.risk_score is None or event.risk_score < rule.risk_threshold:
                return False, []
            matched_conditions.append(f"risk_score >= {rule.risk_threshold}")

        # Check camera IDs
        if rule.camera_ids:
            if event.camera_id not in rule.camera_ids:
                return False, []
            matched_conditions.append(f"camera_id in {rule.camera_ids}")

        # Check object types
        if rule.object_types:
            if not self._check_object_types(rule.object_types, detections):
                return False, []
            matched_conditions.append(f"object_type in {rule.object_types}")

        # Check minimum confidence
        if rule.min_confidence is not None:
            if not self._check_min_confidence(rule.min_confidence, detections):
                return False, []
            matched_conditions.append(f"confidence >= {rule.min_confidence}")

        # Check zone IDs
        if rule.zone_ids:
            # Zone matching would require detection zone data
            # For now, we'll skip this if zones are specified but no zone data exists
            # This could be enhanced later when zone detection is implemented
            logger.debug(f"Zone condition in rule {rule.id} - zone matching not yet implemented")

        # Check schedule
        if rule.schedule:
            if not self._check_schedule(rule.schedule, current_time):
                return False, []
            matched_conditions.append("within_schedule")

        # If we get here, all conditions matched (or no conditions were specified)
        # A rule with no conditions always matches
        if not matched_conditions:
            matched_conditions.append("no_conditions (always matches)")

        return True, matched_conditions

    def _check_object_types(self, required_types: list[str], detections: list[Detection]) -> bool:
        """Check if any detection has a matching object type."""
        if not detections:
            return False

        required_types_lower = [t.lower() for t in required_types]
        for detection in detections:
            if detection.object_type and detection.object_type.lower() in required_types_lower:
                return True
        return False

    def _check_min_confidence(self, min_confidence: float, detections: list[Detection]) -> bool:
        """Check if any detection meets the minimum confidence threshold."""
        if not detections:
            return False

        for detection in detections:
            if detection.confidence is not None and detection.confidence >= min_confidence:
                return True
        return False

    def _check_schedule(self, schedule: dict, current_time: datetime) -> bool:
        """Check if current time falls within the schedule.

        Schedule format:
        {
            "days": ["monday", "tuesday", ...],  # Empty/null = all days
            "start_time": "22:00",  # HH:MM format
            "end_time": "06:00",    # HH:MM format
            "timezone": "UTC"       # Timezone (default: UTC)
        }

        If start_time > end_time, schedule spans midnight (e.g., 22:00-06:00).
        """
        if not schedule:
            return True  # No schedule means always active

        # Get timezone
        tz_name = schedule.get("timezone", "UTC")
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            logger.warning(f"Invalid timezone {tz_name}, using UTC")
            tz = ZoneInfo("UTC")

        # Convert current time to the schedule's timezone
        local_time = current_time.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)

        # Check day of week
        days = schedule.get("days")
        if days and len(days) > 0:
            current_day = DAY_NAMES[local_time.weekday()]
            if current_day.lower() not in [d.lower() for d in days]:
                return False

        # Check time range
        start_time_str = schedule.get("start_time")
        end_time_str = schedule.get("end_time")

        if start_time_str and end_time_str:
            try:
                start_time = self._parse_time(start_time_str)
                end_time = self._parse_time(end_time_str)
                current_time_only = local_time.time()

                if start_time <= end_time:
                    # Normal range (e.g., 09:00-17:00)
                    if not (start_time <= current_time_only <= end_time):
                        return False
                elif not (current_time_only >= start_time or current_time_only <= end_time):
                    # Overnight range (e.g., 22:00-06:00)
                    return False
            except (ValueError, AttributeError) as e:
                logger.warning(f"Error parsing schedule time: {e}")
                return True  # If parsing fails, allow the rule

        return True

    def _parse_time(self, time_str: str) -> time:
        """Parse a time string in HH:MM format."""
        parts = time_str.split(":")
        return time(int(parts[0]), int(parts[1]))

    def _build_dedup_key(
        self,
        rule: AlertRule,
        event: Event,
        detections: list[Detection],
    ) -> str:
        """Build a deduplication key using the rule's template.

        Template variables:
        - {camera_id}: The event's camera ID
        - {rule_id}: The rule's ID
        - {object_type}: First detected object type (or "unknown")
        """
        template = rule.dedup_key_template or "{camera_id}:{rule_id}"

        # Get primary object type from detections
        object_type = "unknown"
        if detections and detections[0].object_type:
            object_type = detections[0].object_type

        try:
            return template.format(
                camera_id=event.camera_id,
                rule_id=str(rule.id),
                object_type=object_type,
            )
        except KeyError as e:
            logger.warning(f"Invalid dedup_key_template variable: {e}")
            return f"{event.camera_id}:{rule.id}"

    async def _check_cooldown(
        self,
        rule: AlertRule,
        dedup_key: str,
        current_time: datetime,
    ) -> bool:
        """Check if the rule is in cooldown for this dedup_key.

        Returns True if in cooldown (should skip), False if not in cooldown.
        """
        cooldown_seconds = rule.cooldown_seconds or 300
        # Strip timezone for naive DB column comparison
        cutoff_time = (current_time - timedelta(seconds=cooldown_seconds)).replace(tzinfo=None)

        # Check database for recent alerts with this dedup_key and rule
        # Use with_for_update() to lock the rows during check-then-insert operation
        # This prevents TOCTOU race conditions where concurrent requests could both
        # pass the cooldown check before either inserts.
        # skip_locked=True allows non-blocking behavior for concurrent queries on
        # different dedup_keys.
        stmt = (
            select(Alert)
            .where(Alert.dedup_key == dedup_key)
            .where(Alert.rule_id == rule.id)
            .where(Alert.created_at >= cutoff_time)
            .limit(1)
            .with_for_update(skip_locked=True)
        )

        result = await self.session.execute(stmt)
        existing_alert = result.scalar_one_or_none()

        return existing_alert is not None

    async def create_alerts_for_event(
        self,
        event: Event,
        triggered_rules: list[TriggeredRule],
    ) -> list[Alert]:
        """Create alert records for all triggered rules.

        Args:
            event: The event that triggered the rules
            triggered_rules: List of rules that matched

        Returns:
            List of created Alert objects
        """
        alerts = []

        for triggered in triggered_rules:
            alert = Alert(
                event_id=event.id,
                rule_id=triggered.rule.id,
                severity=triggered.severity,
                status=AlertStatus.PENDING,
                dedup_key=triggered.dedup_key,
                channels=triggered.rule.channels or [],
                alert_metadata={
                    "matched_conditions": triggered.matched_conditions,
                    "rule_name": triggered.rule.name,
                },
            )
            self.session.add(alert)
            alerts.append(alert)

        await self.session.flush()
        return alerts

    async def test_rule_against_events(
        self,
        rule: AlertRule,
        events: list[Event],
        current_time: datetime | None = None,
    ) -> list[dict]:
        """Test a rule against a list of historical events.

        This is useful for testing rule configuration before enabling.
        Uses batch loading to prevent N+1 queries when loading detections.

        Args:
            rule: The rule to test
            events: List of events to test against
            current_time: Optional override for schedule testing

        Returns:
            List of test results with match status and details
        """
        if current_time is None:
            current_time = utc_now_naive()

        # Batch load all detections in a single query to prevent N+1
        detections_by_event = await self._batch_load_detections_for_events(events)

        results = []
        for event in events:
            detections = detections_by_event.get(event.id, [])
            matches, conditions = await self._evaluate_rule(rule, event, detections, current_time)

            results.append(
                {
                    "event_id": event.id,
                    "camera_id": event.camera_id,
                    "risk_score": event.risk_score,
                    "object_types": [d.object_type for d in detections if d.object_type],
                    "matches": matches,
                    "matched_conditions": conditions,
                    "started_at": event.started_at.isoformat() if event.started_at else None,
                }
            )

        return results


# Convenience function for getting engine instance
async def get_alert_engine(
    session: AsyncSession,
    redis_client: RedisClient | None = None,
) -> AlertRuleEngine:
    """Get an AlertRuleEngine instance.

    Args:
        session: Database session
        redis_client: Optional Redis client

    Returns:
        AlertRuleEngine instance
    """
    return AlertRuleEngine(session, redis_client)
