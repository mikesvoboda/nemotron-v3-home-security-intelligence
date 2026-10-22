"""Unit tests for backend.services.alerting.policy (B4.1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from backend.models.alert import AlertSeverityEnum
from backend.services.alerting.policy import (
    PolicyContext,
    SnoozeEntry,
    default_rule_from_settings,
    evaluate,
)
from backend.services.alerting.verdict import ResolvedVerdict


def _rule(**kw):
    base = {
        "id": "rule-1",
        "name": "Rule 1",
        "enabled": True,
        "severity": AlertSeverityEnum.MEDIUM,
        "risk_threshold": 60,
        "camera_ids": None,
        "excluded_camera_ids": None,
        "object_types": None,
        "min_confidence": None,
        "schedule": None,
        "alert_on_rejected": False,
        "threat_detection_enabled": False,
        "threat_types": None,
        "threat_min_severity": None,
        "threat_confidence_threshold": None,
        "dedup_key_template": "{camera_id}:{rule_id}",
        "cooldown_seconds": 300,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _ctx(**kw) -> PolicyContext:
    now = datetime(2026, 10, 21, 12, 0, 0, tzinfo=UTC)
    defaults = {
        "event_id": 1,
        "camera_id": "front_door",
        "timestamp": now,
        "household_tz": "UTC",
        "master_enabled": True,
        "risk_filters": ("critical", "high", "medium"),
        "camera_enabled": True,
        "camera_risk_threshold": 60,
        "detection_confidence_threshold": 0.5,
        "resolved": ResolvedVerdict(
            source="local",
            verdict="confirmed",
            risk_score=75,
            recognised=(),
            suppressed_by=None,
        ),
        "detections": ({"id": 10, "object_type": "person", "confidence": 0.92},),
        "threats": (),
        "rules": (_rule(),),
        "snoozes": (),
    }
    defaults.update(kw)
    return PolicyContext(**defaults)


def test_master_switch_off_blocks_all_rules() -> None:
    assert evaluate(_ctx(master_enabled=False)) == []


def test_suppressed_by_trusted_match_blocks_all_rules() -> None:
    resolved = ResolvedVerdict(
        source="local",
        verdict="confirmed",
        risk_score=90,
        recognised=("Alice",),
        suppressed_by="Alice (face)",
        face_status="trusted",
    )
    assert evaluate(_ctx(resolved=resolved)) == []


def test_rejected_verdict_suppressed_by_default_and_overridden_when_configured() -> None:
    rejected = ResolvedVerdict(
        source="local",
        verdict="rejected",
        risk_score=80,
        recognised=(),
        suppressed_by=None,
    )
    assert evaluate(_ctx(resolved=rejected, rules=(_rule(alert_on_rejected=False),))) == []
    matches = evaluate(_ctx(resolved=rejected, rules=(_rule(alert_on_rejected=True),)))
    assert len(matches) == 1
    assert matches[0].rule_id == "rule-1"


def test_detector_fallback_ignores_risk_threshold_and_uses_rule_severity() -> None:
    """F2 & F5: detector-sourced verdict with NULL score matches via detector rule
    and takes the rule's own severity."""
    det_verdict = ResolvedVerdict(
        source="detector",
        verdict=None,
        risk_score=None,
        recognised=(),
        suppressed_by=None,
    )
    rule = _rule(severity=AlertSeverityEnum.HIGH, risk_threshold=70)
    matches = evaluate(
        _ctx(
            resolved=det_verdict,
            rules=(rule,),
            detections=({"id": 1, "object_type": "person", "confidence": 0.85},),
        )
    )
    assert len(matches) == 1
    assert matches[0].effective_severity == AlertSeverityEnum.HIGH

    # Non-security-relevant class or below confidence threshold does not match detector rule
    assert (
        evaluate(
            _ctx(
                resolved=det_verdict,
                rules=(rule,),
                detections=({"id": 1, "object_type": "cat", "confidence": 0.99},),
            )
        )
        == []
    )


def test_effective_severity_escalates_with_event_risk_level() -> None:
    """F5: effective severity is the higher of the rule's severity and the event's risk level."""
    low_rule = _rule(severity=AlertSeverityEnum.LOW, risk_threshold=50)
    # Score 90 -> critical from SeverityService
    critical_verdict = ResolvedVerdict(
        source="local",
        verdict="confirmed",
        risk_score=90,
        recognised=(),
        suppressed_by=None,
    )
    matches = evaluate(_ctx(resolved=critical_verdict, rules=(low_rule,)))
    assert len(matches) == 1
    assert matches[0].effective_severity == AlertSeverityEnum.CRITICAL


@pytest.mark.parametrize(
    ("schedule", "ts", "household_tz", "expected"),
    [
        # Ruling 139: 23:59:30 matches an all-day 00:00..23:59 window (end + 1 minute inclusive)
        (
            {"start_time": "00:00", "end_time": "23:59"},
            datetime(2026, 10, 21, 23, 59, 30, tzinfo=UTC),
            "UTC",
            True,
        ),
        # Ruling 139: 00:00:00 the next day matches an all-day rule
        (
            {"start_time": "00:00", "end_time": "23:59"},
            datetime(2026, 10, 22, 0, 0, 0, tzinfo=UTC),
            "UTC",
            True,
        ),
        # Ruling 139: instant after the end minute (17:01:00 for 09:00..17:00) does NOT match,
        # while 17:00:30 DOES match
        (
            {"start_time": "09:00", "end_time": "17:00"},
            datetime(2026, 10, 21, 17, 0, 30, tzinfo=UTC),
            "UTC",
            True,
        ),
        (
            {"start_time": "09:00", "end_time": "17:00"},
            datetime(2026, 10, 21, 17, 1, 0, tzinfo=UTC),
            "UTC",
            False,
        ),
        # Overnight window wraps across midnight with same 1-minute inclusion
        (
            {"start_time": "22:00", "end_time": "06:00"},
            datetime(2026, 10, 21, 6, 0, 45, tzinfo=UTC),
            "UTC",
            True,
        ),
        (
            {"start_time": "22:00", "end_time": "06:00"},
            datetime(2026, 10, 21, 6, 1, 0, tzinfo=UTC),
            "UTC",
            False,
        ),
        # Household timezone conversion (20:00 UTC Sunday == 05:00 Monday in Asia/Tokyo)
        (
            {"days": ["monday"], "start_time": "04:00", "end_time": "06:00"},
            datetime(2026, 10, 4, 20, 0, 0, tzinfo=UTC),
            "Asia/Tokyo",
            True,
        ),
    ],
)
def test_schedule_boundary_in_household_time(
    schedule: dict, ts: datetime, household_tz: str, expected: bool
) -> None:
    matches = evaluate(
        _ctx(
            timestamp=ts,
            household_tz=household_tz,
            rules=(_rule(schedule=schedule),),
        )
    )
    assert (len(matches) == 1) is expected


def test_snooze_suppresses_matching_activity_unless_critical() -> None:
    now = datetime(2026, 10, 21, 12, 0, 0, tzinfo=UTC)
    snooze = SnoozeEntry(
        camera_id="front_door",
        object_type="person",
        until=now + timedelta(hours=1),
    )
    # High severity alert is suppressed by active snooze on same (camera_id, object_type)
    assert (
        evaluate(
            _ctx(
                timestamp=now,
                snoozes=(snooze,),
                rules=(_rule(severity=AlertSeverityEnum.HIGH),),
            )
        )
        == []
    )
    # Critical effective severity breaks through snooze
    crit_matches = evaluate(
        _ctx(
            timestamp=now,
            snoozes=(snooze,),
            rules=(_rule(severity=AlertSeverityEnum.CRITICAL),),
        )
    )
    assert len(crit_matches) == 1


def test_default_rule_respects_camera_settings_and_excluded_cameras() -> None:
    # Disabled camera produces no default rule match
    default_disabled = default_rule_from_settings(
        camera_id="back_yard",
        camera_enabled=False,
        camera_risk_threshold=60,
        risk_filters=("critical", "high", "medium"),
    )
    assert (
        evaluate(_ctx(camera_id="back_yard", camera_enabled=False, rules=(default_disabled,))) == []
    )

    # Excluded camera on a rule skips that camera
    rule_excl = _rule(excluded_camera_ids=["front_door"])
    assert evaluate(_ctx(camera_id="front_door", rules=(rule_excl,))) == []


def test_threat_detection_filters_and_dedup_key_templates() -> None:
    threat_rule = _rule(
        id="rule-threat",
        threat_detection_enabled=True,
        threat_types=["weapon", "intrusion"],
        threat_min_severity="high",
        threat_confidence_threshold=0.85,
        object_types=["person"],
        min_confidence=0.80,
        camera_ids=["front_door"],
        dedup_key_template="{camera_id}:{object_type}:{rule_id}",
    )

    # No threats -> no match
    assert evaluate(_ctx(rules=(threat_rule,), threats=())) == []

    # Threat with wrong type, low severity, or low confidence -> no match
    assert (
        evaluate(
            _ctx(
                rules=(threat_rule,),
                threats=(
                    {"threat_type": "smoke", "severity": "critical", "confidence": 0.99},
                    {"threat_type": "weapon", "severity": "medium", "confidence": 0.99},
                    {"threat_type": "weapon", "severity": "high", "confidence": 0.70},
                ),
            )
        )
        == []
    )

    # Matching threat + matching camera_ids, object_types, and min_confidence -> matches
    matches = evaluate(
        _ctx(
            rules=(threat_rule,),
            detections=(SimpleNamespace(id=10, object_type="person", confidence=0.92),),
            threats=(SimpleNamespace(threat_type="weapon", severity="critical", confidence=0.95),),
        )
    )
    assert len(matches) == 1
    assert matches[0].dedup_key == "front_door:person:rule-threat"
    assert "camera_id in ['front_door']" in matches[0].matched_conditions
    assert "object_type in ['person']" in matches[0].matched_conditions
    assert "confidence >= 0.8" in matches[0].matched_conditions
    assert "threat_detected" in matches[0].matched_conditions

    # Invalid template placeholder falls back to "{camera_id}:{rule_id}"
    bad_tpl_rule = _rule(id="r-bad", dedup_key_template="{camera_id}:{nonexistent_key}")
    bad_matches = evaluate(_ctx(rules=(bad_tpl_rule,)))
    assert len(bad_matches) == 1
    assert bad_matches[0].dedup_key == "front_door:r-bad"
