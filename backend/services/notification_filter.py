"""Notification filter service for determining when to send notifications.

This service checks notification preferences to determine whether a notification
should be sent for a given event. It considers:
- Global notification preferences (enabled/disabled, risk filters)
- Per-camera notification settings (enabled/disabled, risk threshold)
- Quiet hours periods (time ranges when notifications are muted)
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from backend.core.config import get_settings
from backend.models.notification_preferences import (
    DEFAULT_CAMERA_RISK_THRESHOLD,
    CameraNotificationSetting,
    NotificationPreferences,
    QuietHoursPeriod,
    RiskLevel,
)

logger = logging.getLogger(__name__)

# spec §6 step 3: on a NULL score (verification_failed) only a detection of
# a security-relevant class at/above detection_confidence_threshold notifies.
# The spec names exactly these two; widening this set is a semantic change
# (more notifications) and needs owner sign-off, not a convenience add.
SECURITY_RELEVANT_CLASSES = frozenset({"person", "vehicle"})

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class NotificationFilterService:
    """Service for filtering notifications based on user preferences."""

    def should_notify(
        self,
        risk_score: int | None,
        camera_id: str,
        timestamp: datetime,
        global_prefs: NotificationPreferences,
        camera_setting: CameraNotificationSetting | None = None,
        quiet_periods: list[QuietHoursPeriod] | None = None,
        detection_class: str | None = None,
        detection_confidence: float | None = None,
        verification_verdict: str | None = None,
    ) -> bool:
        """Determine if a notification should be sent.

        Args:
            risk_score: Event risk score (0-100), or None for a
                verification_failed event (spec §6 step 3, P0.25)
            camera_id: Camera ID
            timestamp: Event timestamp
            global_prefs: Global notification preferences
            camera_setting: Per-camera notification setting (optional)
            quiet_periods: List of quiet hours periods (optional)
            detection_class: Detected object class for the NULL-score
                detector-only rule (None when no detector evidence available)
            detection_confidence: Detector confidence for that class (0.0-1.0)
            verification_verdict: The event's EventVerification.verdict (spec
                §4), None for a legacy/unscored event with no verification
                row. "rejected" is an absolute skip (spec §6: "rejected ⇒
                never notifies, even where a camera's risk_threshold sits
                inside the low band").

        Returns:
            True if notification should be sent, False otherwise
        """
        # spec §6, "rejected ⇒ never notifies": checked FIRST and
        # unconditionally - the analyzer's low-band clamp is NOT a skip, so
        # a camera whose risk_threshold sits inside the low band would still
        # page for a verdict that says "not a threat". The verdict is absent
        # on legacy events (no verification row), so they fall through
        # byte-identically (D10/legacy rule).
        if verification_verdict == "rejected":
            return False

        # P0.25 / spec §6 step 3: the detector-only rule for NULL scores runs
        # BEFORE any level mapping or threshold comparison (spec wording) - a
        # NULL is not a low score, so it must never flow through the scored
        # path (the legacy path below keeps its pre-0.25 form verbatim).
        if risk_score is None:
            return global_prefs.enabled and self._detector_only_notify(
                detection_class, detection_confidence
            )

        return self._scored_notify(
            risk_score, camera_id, timestamp, global_prefs, camera_setting, quiet_periods
        )

    def _scored_notify(
        self,
        risk_score: int,
        camera_id: str,  # noqa: ARG002
        timestamp: datetime,
        global_prefs: NotificationPreferences,
        camera_setting: CameraNotificationSetting | None = None,
        quiet_periods: list[QuietHoursPeriod] | None = None,
    ) -> bool:
        """The pre-0.25 scored path, moved verbatim out of should_notify so
        the NULL branch could join without bending any legacy rule."""
        # Check if notifications are globally enabled
        if not global_prefs.enabled:
            return False

        # Check if risk level is in enabled filters
        risk_level = self._risk_score_to_level(risk_score)
        if risk_level.value not in global_prefs.risk_filters:
            return False

        # Check per-camera settings if provided. OD-29 (owner ruling
        # 2026-10-05): "no row" means the shipped default setting, not "no
        # floor" - the numeric floor is DEFAULT_CAMERA_RISK_THRESHOLD either
        # way. Under the old default 0 the two were indistinguishable; with
        # the floor at 60 they are not, and a camera that never saved a
        # setting must not silently exempt itself from the alert floor.
        if camera_setting is not None and not camera_setting.enabled:
            return False

        # Check if risk score meets the camera's threshold (OD-29)
        threshold = (
            camera_setting.risk_threshold
            if camera_setting is not None
            else DEFAULT_CAMERA_RISK_THRESHOLD
        )
        if risk_score < threshold:
            return False

        # Check quiet hours if provided
        if quiet_periods:
            for period in quiet_periods:
                if self.is_quiet_period(timestamp, period):
                    return False

        return True

    def _detector_only_notify(
        self,
        detection_class: str | None,
        detection_confidence: float | None,
    ) -> bool:
        """spec §6 step 3's detector-only rule for NULL-score events.

        A verification_failed event (risk_score NULL) notifies iff a
        security-relevant class was detected at/above
        detection_confidence_threshold. Without detector evidence the answer
        is an explicit False: the owner is never left blind by a crash, and
        nothing passes silently (S5).
        """
        threshold = get_settings().detection_confidence_threshold
        return bool(
            detection_class in SECURITY_RELEVANT_CLASSES
            and detection_confidence is not None
            and detection_confidence >= threshold
        )

    def is_quiet_period(self, timestamp: datetime, period: QuietHoursPeriod) -> bool:
        """Check if a timestamp falls within a quiet hours period.

        Args:
            timestamp: Timestamp to check
            period: Quiet hours period

        Returns:
            True if timestamp is during quiet hours, False otherwise
        """
        # Check if day of week matches
        day_name = timestamp.strftime("%A").lower()  # e.g., "monday"
        if day_name not in period.days:
            return False

        # Check if time is within range
        current_time = timestamp.time()

        # Handle periods that span midnight (e.g., 22:00 to 06:00)
        if period.start_time > period.end_time:
            # Period spans midnight
            return current_time >= period.start_time or current_time <= period.end_time
        else:
            # Normal period (doesn't span midnight)
            return period.start_time <= current_time <= period.end_time

    def _risk_score_to_level(self, score: int) -> RiskLevel:
        """Convert risk score to risk level category.

        Args:
            score: Risk score (0-100)

        Returns:
            RiskLevel enum value
        """
        if score >= 80:
            return RiskLevel.CRITICAL
        elif score >= 60:
            return RiskLevel.HIGH
        elif score >= 40:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW


async def decide_notification(
    session: AsyncSession | None,
    *,
    risk_score: int | None,
    camera_id: str,
    timestamp: datetime,
    verification_verdict: str | None,
    detections: Sequence[Mapping[str, Any]],
) -> bool:
    """The notify decision for one stored verdict (M1): load the owner's global
    preferences, the camera's setting and the quiet hours, pick the detector
    evidence for the NULL-score rule, and ask `NotificationFilterService`.

    A failed settings read never silences an alert: on any read error (or with
    no session) the decision falls back to the shipped default preferences
    (enabled; medium, high and critical) and the shipped default camera floor
    (OD-29: 60), so a high-risk verdict still pages and
    a NULL-score event still follows the detector-only rule. The caller owns the
    session; run this in its OWN short session after the event has committed,
    because a failed statement can abort the surrounding Postgres transaction.
    """
    prefs: NotificationPreferences | None = None
    camera_setting: CameraNotificationSetting | None = None
    quiet_periods: list[QuietHoursPeriod] = []
    if session is not None:
        try:
            prefs = (
                (
                    await session.execute(
                        select(NotificationPreferences).where(NotificationPreferences.id == 1)
                    )
                )
                .scalars()
                .first()
            )
            camera_setting = (
                (
                    await session.execute(
                        select(CameraNotificationSetting).where(
                            CameraNotificationSetting.camera_id == camera_id
                        )
                    )
                )
                .scalars()
                .first()
            )
            quiet_periods = list((await session.execute(select(QuietHoursPeriod))).scalars().all())
        except Exception as exc:
            logger.warning(
                "notification settings unavailable - deciding on the shipped defaults",
                extra={"camera_id": camera_id, "error": str(exc)},
            )
            prefs, camera_setting, quiet_periods = None, None, []
    if prefs is None:
        prefs = NotificationPreferences()  # shipped defaults, no row needed

    evidence = max(
        (
            d
            for d in detections
            if d.get("object_type") in SECURITY_RELEVANT_CLASSES and d.get("confidence") is not None
        ),
        key=lambda d: d["confidence"],
        default=None,
    )
    return NotificationFilterService().should_notify(
        risk_score=risk_score,
        camera_id=camera_id,
        timestamp=timestamp,
        global_prefs=prefs,
        camera_setting=camera_setting,
        quiet_periods=quiet_periods,
        detection_class=evidence["object_type"] if evidence else None,
        detection_confidence=evidence["confidence"] if evidence else None,
        verification_verdict=verification_verdict,
    )
