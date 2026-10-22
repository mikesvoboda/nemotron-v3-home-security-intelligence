"""Pure alerting policy evaluation (B4.1 / docs/uplevel/4n-alerting.md).

Decides which rules match an event, computes effective severity and dedup keys,
and applies household schedule windows (ruling 139) and activity snoozes with
critical break-through. Pure: no I/O.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

from backend.models.alert import AlertSeverityEnum
from backend.services.alerting.verdict import ResolvedVerdict
from backend.services.severity import get_severity_service

logger = logging.getLogger(__name__)

DEFAULT_RULE_ID = "default"
SECURITY_RELEVANT_CLASSES = frozenset({"person", "vehicle"})

SEVERITY_PRIORITY: dict[str, int] = {
    AlertSeverityEnum.LOW.value: 1,
    AlertSeverityEnum.MEDIUM.value: 2,
    AlertSeverityEnum.HIGH.value: 3,
    AlertSeverityEnum.CRITICAL.value: 4,
}

THREAT_SEVERITY_PRIORITY: dict[str, int] = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

DAY_NAMES = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


@dataclass(frozen=True, slots=True)
class SnoozeEntry:
    """An active activity snooze on (camera_id, object_type)."""

    camera_id: str
    object_type: str
    until: datetime


@dataclass(frozen=True, slots=True)
class PolicyContext:
    """All inputs needed to evaluate alerting policy purely (no I/O)."""

    event_id: int
    camera_id: str
    timestamp: datetime
    resolved: ResolvedVerdict
    household_tz: str = "UTC"
    master_enabled: bool = True
    risk_filters: Sequence[str] = ("critical", "high", "medium")
    camera_enabled: bool = True
    camera_risk_threshold: int = 60
    detection_confidence_threshold: float = 0.5
    detections: Sequence[Any] = ()
    threats: Sequence[Any] = ()
    rules: Sequence[Any] = ()
    snoozes: Sequence[SnoozeEntry] = ()
    mode: str = "home"
    armed: bool = True
    camera_name: str | None = None
    external_source: str | None = None


@dataclass(frozen=True, slots=True)
class RuleMatch:
    """One matched rule with its effective severity, activity key, and dedup key."""

    rule: Any
    rule_id: str | None
    rule_name: str
    effective_severity: AlertSeverityEnum
    activity_key: tuple[str, str]
    dedup_key: str
    matched_conditions: tuple[str, ...]
    cooldown_seconds: int = 300
    raised_while_unarmed: bool = False


def default_rule_from_settings(
    *,
    camera_id: str,  # noqa: ARG001
    camera_enabled: bool = True,
    camera_risk_threshold: int = 60,
    risk_filters: Sequence[str] = ("critical", "high", "medium"),
) -> Any:
    """Construct the synthetic default rule reading today's camera settings."""
    return SimpleNamespace(
        id=None,
        name="default",
        is_default_rule=True,
        enabled=camera_enabled,
        severity=AlertSeverityEnum.MEDIUM,
        risk_threshold=camera_risk_threshold,
        risk_filters=tuple(risk_filters),
        camera_ids=None,
        excluded_camera_ids=None,
        object_types=None,
        min_confidence=None,
        schedule=None,
        alert_on_rejected=False,
        alert_on_rejected_modes=None,
        sources=("camera",),
        threat_detection_enabled=False,
        threat_types=None,
        threat_min_severity=None,
        threat_confidence_threshold=None,
        dedup_key_template="{camera_id}:default",
        cooldown_seconds=300,
    )


def _det_attr(det: Any, key: str) -> Any:
    if isinstance(det, Mapping):
        return det.get(key)
    return getattr(det, key, None)


def _severity_enum(val: Any) -> AlertSeverityEnum:
    if isinstance(val, AlertSeverityEnum):
        return val
    raw = str(getattr(val, "value", val)).lower()
    for member in AlertSeverityEnum:
        if member.value == raw:
            return member
    return AlertSeverityEnum.MEDIUM


def _higher_severity(a: AlertSeverityEnum, b: AlertSeverityEnum) -> AlertSeverityEnum:
    if SEVERITY_PRIORITY.get(b.value, 0) > SEVERITY_PRIORITY.get(a.value, 0):
        return b
    return a


def _parse_time_seconds(time_str: str, *, end_inclusive_minute: bool = False) -> int:
    parts = time_str.strip().split(":")
    hour = int(parts[0])
    minute = int(parts[1])
    second = int(parts[2]) if len(parts) > 2 else 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        raise ValueError(f"out of range time: {time_str}")
    base = hour * 3600 + minute * 60 + second
    if end_inclusive_minute:
        # Ruling 139: schedule includes its end minute in full (`start <= now < end + 1 minute`)
        return hour * 3600 + (minute + 1) * 60
    return base


def check_schedule_window(
    schedule: Mapping[str, Any] | None,
    current_time: datetime,
    household_tz: str = "UTC",
) -> bool:
    """Evaluate a rule schedule in household local time with end-minute inclusion (ruling 139)."""
    if not schedule:
        return True

    tz_name = schedule.get("timezone") or household_tz or "UTC"
    try:
        tz = ZoneInfo(str(tz_name))
    except Exception:
        logger.warning(f"Invalid timezone {tz_name}, using UTC")
        tz = ZoneInfo("UTC")

    if current_time.tzinfo is None:
        utc_time = current_time.replace(tzinfo=UTC)
    else:
        utc_time = current_time
    local_time = utc_time.astimezone(tz)

    days = schedule.get("days")
    if days and len(days) > 0:
        current_day = DAY_NAMES[local_time.weekday()]
        normalized_days = [str(d).lower() for d in days]
        if current_day not in normalized_days:
            return False

    start_time_str = schedule.get("start_time")
    end_time_str = schedule.get("end_time")
    if start_time_str and end_time_str:
        try:
            start_sec = _parse_time_seconds(str(start_time_str), end_inclusive_minute=False)
            end_sec_excl = _parse_time_seconds(str(end_time_str), end_inclusive_minute=True)
            now_sec = local_time.hour * 3600 + local_time.minute * 60 + local_time.second
            start_raw = _parse_time_seconds(str(start_time_str), end_inclusive_minute=False)
            end_raw = _parse_time_seconds(str(end_time_str), end_inclusive_minute=False)
            if start_raw > end_raw:
                # Overnight window wraps across midnight with the same 1-minute inclusion
                if not (now_sec >= start_sec or now_sec < end_sec_excl):
                    return False
            elif not (start_sec <= now_sec < end_sec_excl):
                return False
        except (ValueError, IndexError) as exc:
            logger.warning(f"Error parsing schedule time: {exc}")
            return True

    return True


def _check_threat(rule: Any, threats: Sequence[Any]) -> bool:
    if not getattr(rule, "threat_detection_enabled", False):
        return False
    if not threats:
        return False
    rule_types = getattr(rule, "threat_types", None)
    allowed_types = {str(t).lower() for t in rule_types} if rule_types else None
    min_sev = getattr(rule, "threat_min_severity", None)
    min_prio = THREAT_SEVERITY_PRIORITY.get(str(min_sev).lower(), 0) if min_sev else 0
    min_conf = getattr(rule, "threat_confidence_threshold", None)

    for t in threats:
        t_type = _det_attr(t, "threat_type")
        if allowed_types and (not t_type or str(t_type).lower() not in allowed_types):
            continue
        t_sev = _det_attr(t, "severity")
        t_prio = THREAT_SEVERITY_PRIORITY.get(str(t_sev).lower(), 0) if t_sev else 0
        if t_prio < min_prio:
            continue
        t_conf = _det_attr(t, "confidence")
        if min_conf is not None and (t_conf is None or float(t_conf) < float(min_conf)):
            continue
        return True
    return False


def _primary_object_type(detections: Sequence[Any], rule_object_types: Sequence[str] | None) -> str:
    if rule_object_types:
        allowed = {t.lower() for t in rule_object_types}
        for d in detections:
            ot = _det_attr(d, "object_type")
            if ot and str(ot).lower() in allowed:
                return str(ot).lower()
    for d in detections:
        ot = _det_attr(d, "object_type")
        if ot:
            return str(ot).lower()
    return "unknown"


def _build_dedup_key(
    rule: Any,
    camera_id: str,
    object_type: str,
) -> str:
    rule_key = getattr(rule, "id", None) or DEFAULT_RULE_ID
    template = getattr(rule, "dedup_key_template", None) or "{camera_id}:{rule_id}"
    try:
        return str(template).format(
            camera_id=camera_id,
            rule_id=rule_key,
            object_type=object_type,
        )
    except KeyError:
        return f"{camera_id}:{rule_key}"


def _is_snoozed(
    camera_id: str,
    object_type: str,
    now: datetime,
    snoozes: Sequence[SnoozeEntry],
) -> bool:
    now_utc = now.replace(tzinfo=UTC) if now.tzinfo is None else now
    for s in snoozes:
        s_until = s.until.replace(tzinfo=UTC) if s.until.tzinfo is None else s.until
        if (
            s.camera_id == camera_id
            and s.object_type.lower() == object_type.lower()
            and s_until > now_utc
        ):
            return True
    return False


def _rejected_override_covers_mode(rule: Any, mode: str) -> bool:
    """Return whether `rule`'s rejected-verdict override covers `mode` (4n-arming.md)."""
    modes = getattr(rule, "alert_on_rejected_modes", None)
    if modes is not None:
        return len(modes) > 0 and str(mode).lower() in {str(m).lower() for m in modes}
    return bool(getattr(rule, "alert_on_rejected", False))


def _check_verdict_and_severity(
    rule: Any,
    ctx: PolicyContext,
    matching_detections: Sequence[Any],
    matched_conditions: list[str],
    *,
    is_default: bool,
) -> AlertSeverityEnum | None:
    if ctx.resolved.suppressed_by is not None or (
        ctx.resolved.verdict == "rejected" and not _rejected_override_covers_mode(rule, ctx.mode)
    ):
        return None

    rule_sev = _severity_enum(getattr(rule, "severity", AlertSeverityEnum.MEDIUM))

    if ctx.resolved.source == "detector" or ctx.resolved.risk_score is None:
        qualifying = [
            d
            for d in matching_detections
            if _det_attr(d, "object_type")
            and str(_det_attr(d, "object_type")).lower() in SECURITY_RELEVANT_CLASSES
            and _det_attr(d, "confidence") is not None
            and float(_det_attr(d, "confidence")) >= float(ctx.detection_confidence_threshold)
        ]
        if not qualifying:
            return None
        matched_conditions.append(f"detector_fallback >= {ctx.detection_confidence_threshold}")
        return rule_sev

    score = int(ctx.resolved.risk_score)
    event_sev_val = get_severity_service().risk_score_to_severity(score).value
    event_sev = _severity_enum(event_sev_val)

    if is_default:
        allowed_filters = getattr(rule, "risk_filters", ctx.risk_filters)
        if allowed_filters and event_sev.value not in allowed_filters:
            return None

    threshold = getattr(rule, "risk_threshold", None)
    if threshold is not None:
        if score < int(threshold):
            return None
        matched_conditions.append(f"risk_score >= {threshold}")

    return _higher_severity(rule_sev, event_sev)


def _match_detections_and_filters(
    rule: Any,
    ctx: PolicyContext,
    matched_conditions: list[str],
) -> list[Any] | None:
    object_types = getattr(rule, "object_types", None)
    matching_detections = list(ctx.detections)
    if object_types and len(object_types) > 0:
        rule_types_lower = [str(t).lower() for t in object_types]
        matching_detections = [
            d
            for d in ctx.detections
            if _det_attr(d, "object_type")
            and str(_det_attr(d, "object_type")).lower() in rule_types_lower
        ]
        if not matching_detections:
            return None
        matched_conditions.append(f"object_type in {object_types}")

    min_confidence = getattr(rule, "min_confidence", None)
    if min_confidence is not None:
        pool = matching_detections if object_types else list(ctx.detections)
        confident = [
            d
            for d in pool
            if _det_attr(d, "confidence") is not None
            and float(_det_attr(d, "confidence")) >= float(min_confidence)
        ]
        if not confident:
            return None
        matched_conditions.append(f"confidence >= {min_confidence}")

    if getattr(rule, "threat_detection_enabled", False):
        if not _check_threat(rule, ctx.threats):
            return None
        matched_conditions.append("threat_detected")

    schedule = getattr(rule, "schedule", None)
    if schedule:
        if not check_schedule_window(schedule, ctx.timestamp, ctx.household_tz):
            return None
        matched_conditions.append("within_schedule")

    return matching_detections


def evaluate_rule(
    rule: Any,
    ctx: PolicyContext,
) -> tuple[bool, list[str], AlertSeverityEnum]:
    """Evaluate a single rule against PolicyContext (ignoring master switch and snooze)."""
    is_default = bool(getattr(rule, "is_default_rule", False))
    if not getattr(rule, "enabled", True) or (is_default and not ctx.camera_enabled):
        return (False, [], AlertSeverityEnum.LOW)

    event_source = "external" if ctx.resolved.source == "external" else "camera"
    raw_sources = getattr(rule, "sources", None) or ["camera"]
    rule_sources = {str(s).lower() for s in raw_sources}
    object_types = getattr(rule, "object_types", None)
    if event_source not in rule_sources or (
        event_source == "external"
        and (bool(object_types) or getattr(rule, "min_confidence", None) is not None)
    ):
        return (False, [], AlertSeverityEnum.LOW)

    excluded = getattr(rule, "excluded_camera_ids", None)
    camera_ids = getattr(rule, "camera_ids", None)
    if (excluded and ctx.camera_id in excluded) or (
        camera_ids and len(camera_ids) > 0 and ctx.camera_id not in camera_ids
    ):
        return (False, [], AlertSeverityEnum.LOW)

    matched_conditions: list[str] = []
    if camera_ids and len(camera_ids) > 0:
        matched_conditions.append(f"camera_id in {camera_ids}")

    matching_detections = _match_detections_and_filters(rule, ctx, matched_conditions)
    if matching_detections is None:
        return (False, [], AlertSeverityEnum.LOW)

    effective_severity = _check_verdict_and_severity(
        rule,
        ctx,
        matching_detections,
        matched_conditions,
        is_default=is_default,
    )
    if effective_severity is None:
        return (False, [], AlertSeverityEnum.LOW)

    if not matched_conditions:
        matched_conditions.append("no_conditions (always matches)")

    return (True, matched_conditions, effective_severity)


def evaluate(ctx: PolicyContext) -> list[RuleMatch]:
    """Evaluate all rules in PolicyContext and return matching RuleMatch items."""
    if not ctx.master_enabled:
        return []
    if ctx.resolved.suppressed_by is not None:
        return []

    matches: list[RuleMatch] = []
    for rule in ctx.rules:
        matched, conditions, effective_severity = evaluate_rule(rule, ctx)
        if not matched:
            continue

        # Arming gate (B4.7 / 4n-arming.md): a rule match on an unarmed camera survives
        # only when its effective severity is critical, and the alert is marked raised_while_unarmed.
        raised_while_unarmed = False
        if not ctx.armed:
            if effective_severity != AlertSeverityEnum.CRITICAL:
                continue
            raised_while_unarmed = True

        if ctx.resolved.source == "external":
            ext_src = str(ctx.external_source or "external").strip() or "external"
            obj_type = f"external:{ext_src}"
        else:
            obj_type = _primary_object_type(ctx.detections, getattr(rule, "object_types", None))
        activity_key = (ctx.camera_id, obj_type)

        # Snooze check: critical effective severity skips snooze (break-through)
        if effective_severity != AlertSeverityEnum.CRITICAL and _is_snoozed(
            ctx.camera_id, obj_type, ctx.timestamp, ctx.snoozes
        ):
            continue

        rule_id = getattr(rule, "id", None)
        rule_name = str(getattr(rule, "name", None) or DEFAULT_RULE_ID)
        dedup_key = _build_dedup_key(rule, ctx.camera_id, obj_type)
        cooldown = getattr(rule, "cooldown_seconds", None)
        cooldown_seconds = 300 if cooldown is None else int(cooldown)

        matches.append(
            RuleMatch(
                rule=rule,
                rule_id=rule_id,
                rule_name=rule_name,
                effective_severity=effective_severity,
                activity_key=activity_key,
                dedup_key=dedup_key,
                matched_conditions=tuple(conditions),
                cooldown_seconds=cooldown_seconds,
                raised_while_unarmed=raised_while_unarmed,
            )
        )

    matches.sort(
        key=lambda m: SEVERITY_PRIORITY.get(m.effective_severity.value, 0),
        reverse=True,
    )
    return matches


def arming_suppression_reason(ctx: PolicyContext) -> str | None:
    """Return the arming suppression explanation when arming is the reason no alert was created."""
    if ctx.armed or not ctx.master_enabled or ctx.resolved.suppressed_by is not None:
        return None
    would_match = evaluate(replace(ctx, armed=True))
    if not would_match:
        return None
    mode_label = (ctx.mode or "home").capitalize()
    cam_label = ctx.camera_name or ctx.camera_id
    return f"{mode_label} leaves out {cam_label} (arming)"
