"""P0.25 null-safety: every consumer of a NULL risk_score, before any NULL exists.

Spec 0.3 (next step, F4-approved) starts emitting ``risk_score=None`` on
verification failure - replacing today's silent default-50. These tests
define what a NULL score MUST do at every live-path consumer, TDD-first:

  WebSocketEventData   None validates (schema today: required, ge=0 - a NULL
                       payload would raise at the boundary, not the consumer)
  requires_ack         None ⇒ no ack (today: TypeError - `data.get(..., 0)`'s
                       default is defeated by a present-but-None key)
  notification_filter  §6 step 3 detector-only rule, evaluated BEFORE the
                       level mapping and the camera threshold: notify iff a
                       security-relevant class was detected at/above
                       detection_confidence_threshold; never a crash, never a
                       silent pass.

The second class tests are GREEN PINS - they lock NULL-safety that already
exists so a later refactor cannot silently remove it (0.25's job is "every
live consumer", not "fix things that are broken"): analytics SQL filter,
ExperimentResult non-NULL columns, calibration caller guard (also pinned by
test_calibration_service.py::test_handles_null_risk_score), audit consistency
guard (also pinned in test_pipeline_quality_audit_service.py).
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from backend.models.notification_preferences import (
    CameraNotificationSetting,
    NotificationPreferences,
)
from backend.services.event_broadcaster import requires_ack
from backend.services.notification_filter import NotificationFilterService

pytestmark = pytest.mark.unit


def _event_payload(**overrides) -> dict:
    data = {
        "id": 1,
        "event_id": 1,
        "batch_id": "batch_1",
        "camera_id": "front_door",
        "risk_score": 42,
        "risk_level": "low",
        "summary": "s",
        "reasoning": "r",
    } | overrides
    return {"type": "event", "data": data}


class TestWebSocketEventDataAcceptsNull:
    """spec §4: WebSocketEventData.risk_score/risk_level become Optional so a
    verification_failed broadcast can carry them without lying about a score."""

    def test_null_score_and_level_validate(self) -> None:
        from backend.api.schemas.websocket import WebSocketEventData

        m = WebSocketEventData.model_validate(
            _event_payload(risk_score=None, risk_level=None)["data"]
        )
        assert m.risk_score is None
        assert m.risk_level is None

    def test_scored_payload_still_validates(self) -> None:
        """The change must not regress scored events (legacy byte-identical:
        every scored payload behaves exactly as before)."""
        from backend.api.schemas.websocket import WebSocketEventData

        m = WebSocketEventData.model_validate(_event_payload()["data"])
        assert m.risk_score == 42
        assert m.risk_level is not None

    def test_out_of_range_score_still_refused(self) -> None:
        from backend.api.schemas.websocket import WebSocketEventData

        with pytest.raises(ValidationError):
            WebSocketEventData.model_validate(_event_payload(risk_score=101)["data"])


class TestRequiresAckNullSafe:
    def test_null_score_does_not_ack_and_does_not_crash(self) -> None:
        """Today this raises: `data.get("risk_score", 0)` returns None for a
        PRESENT-None key (the default applies only when absent) and
        `None >= 80` is a TypeError - a verification_failed event would kill
        the subscriber loop. §6: unverified events do not require ack."""
        assert requires_ack(_event_payload(risk_score=None)) is False

    def test_null_score_with_critical_level_still_acks(self) -> None:
        """§6 keeps the level arm: NULL score + critical level still acks."""
        assert requires_ack(_event_payload(risk_score=None, risk_level="critical")) is True

    def test_absent_score_behaves_as_before(self) -> None:
        p = _event_payload()
        del p["data"]["risk_score"]
        assert requires_ack(p) is False


class TestNotificationFilterDetectorOnlyRule:
    """§6 step 3, spec-quoted: notification_filter evaluates the
    detector-only rule BEFORE any threshold comparison; NULL + security class
    ≥ detection_confidence_threshold ⇒ notify; NULL + below ⇒ suppress;
    never a crash and never a silent pass."""

    def _prefs(self) -> NotificationPreferences:
        p = NotificationPreferences()
        p.enabled = True
        p.risk_filters = ["low", "medium", "high", "critical"]
        return p

    def _camera(self, threshold: int = 0) -> CameraNotificationSetting:
        c = CameraNotificationSetting()
        c.enabled = True
        c.risk_threshold = threshold
        return c

    def test_null_with_strong_person_detection_notifies(self, monkeypatch) -> None:
        import backend.services.notification_filter as nf

        monkeypatch.setattr(
            nf,
            "get_settings",
            lambda: SimpleNamespace(detection_confidence_threshold=0.40),
            raising=False,
        )
        service = NotificationFilterService()
        assert (
            service.should_notify(
                risk_score=None,
                camera_id="front_door",
                timestamp=datetime(2026, 1, 7, 12, 0),
                global_prefs=self._prefs(),
                camera_setting=self._camera(threshold=90),  # threshold must NOT veto
                detection_class="person",
                detection_confidence=0.9,
            )
            is True
        )

    def test_null_with_weak_person_detection_suppresses(self) -> None:
        service = NotificationFilterService()
        assert (
            service.should_notify(
                risk_score=None,
                camera_id="front_door",
                timestamp=datetime(2026, 1, 7, 12, 0),
                global_prefs=self._prefs(),
                detection_class="person",
                detection_confidence=0.10,
            )
            is False
        )

    def test_null_with_strong_nonsecurity_class_suppresses(self) -> None:
        service = NotificationFilterService()
        assert (
            service.should_notify(
                risk_score=None,
                camera_id="front_door",
                timestamp=datetime(2026, 1, 7, 12, 0),
                global_prefs=self._prefs(),
                detection_class="dog",
                detection_confidence=0.99,
            )
            is False
        )

    def test_null_without_detector_evidence_suppresses(self) -> None:
        """No class/confidence available ⇒ suppress (an explicit False),
        never a crash - and never a silent True past the global switch."""
        service = NotificationFilterService()
        assert (
            service.should_notify(
                risk_score=None,
                camera_id="front_door",
                timestamp=datetime(2026, 1, 7, 12, 0),
                global_prefs=self._prefs(),
            )
            is False
        )

    def test_null_respects_global_disable(self) -> None:
        p = self._prefs()
        p.enabled = False
        service = NotificationFilterService()
        assert (
            service.should_notify(
                risk_score=None,
                camera_id="front_door",
                timestamp=datetime(2026, 1, 7, 12, 0),
                global_prefs=p,
                detection_class="person",
                detection_confidence=0.99,
            )
            is False
        )

    def test_scored_path_unchanged(self) -> None:
        """Byte-identical legacy: a scored event behaves exactly as before
        (low score, empty risk_filters ⇒ suppress)."""
        p = NotificationPreferences()
        p.enabled = True
        p.risk_filters = ["critical"]
        service = NotificationFilterService()
        assert (
            service.should_notify(
                risk_score=30,
                camera_id="front_door",
                timestamp=datetime(2026, 1, 7, 12, 0),
                global_prefs=p,
            )
            is False
        )


class TestArithmeticSitesAreAlreadyNullSafe_PINS:
    """The ledger's counting erratum claimed all four arithmetic-only sites
    'TypeError on a NULL score'. Direct reads disprove that (2026-09-25):
    all four are already NULL-safe, by different mechanisms. Pinned so the
    mechanism is never mistaken for sloppiness - and never removed."""

    def test_analytics_histogram_sql_excludes_null_scores(self) -> None:
        """`Event.risk_score / bucket_size` is SQL-side arithmetic - NULL
        propagates as NULL in SQL (no TypeError) - and the query filters
        `Event.risk_score.isnot(None)` outright, so NULL rows never reach a
        bucket. Captured from the route's own compiled statement."""
        import asyncio
        from datetime import date
        from unittest.mock import AsyncMock

        from backend.api.routes.analytics import get_risk_score_distribution

        db = AsyncMock()
        result = MagicMock()
        result.all.return_value = []
        db.execute.return_value = result
        asyncio.run(
            get_risk_score_distribution(
                start_date=date(2026, 1, 1), end_date=date(2026, 1, 7), bucket_size=10, db=db
            )
        )
        stmt = db.execute.call_args[0][0]
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()
        assert "risk_score is not null" in compiled

    def test_experiment_result_score_columns_are_notnull(self) -> None:
        """`abs(v1_risk_score - v2_risk_score)` can only see what the schema
        stores - and both columns are nullable=False at the DB level, so a
        verification-failed NULL (on events) can never reach this property
        through the table. A future experiment runner that wants NULL rows
        changes the schema first, and this pin fails."""
        from backend.models.experiment_result import ExperimentResult

        t = ExperimentResult.__table__
        assert t.c.v1_risk_score.nullable is False
        assert t.c.v2_risk_score.nullable is False
        row = ExperimentResult(
            experiment_name="x",
            camera_id="front_door",
            v1_risk_score=50,
            v2_risk_score=45,
            v1_latency_ms=150.0,
            v2_latency_ms=180.0,
            experiment_version="shadow",
        )
        assert row.calculated_score_diff == 5

    def test_calibration_adjustment_guard_is_caller_side(self) -> None:
        """`risk_score / 50.0` sits in calculate_adjustment(), whose ONLY
        production caller (adjust_from_feedback flow) returns early on
        `risk_score is None` with a warning (calibration_service.py:250) -
        behavior pinned by test_calibration_service.py::test_handles_null_
        risk_score; this pin locks the caller-side guard itself so neither
        side drifts alone. (Signal-based here rather than re-running the
        async flow: the guard is one line, its absence is the defect.)"""
        import inspect

        from backend.services import calibration_service

        src = inspect.getsource(calibration_service.CalibrationService.adjust_from_feedback)
        assert "risk_score is None" in src

    def test_audit_consistency_diff_requires_both_scores(self) -> None:
        """pipeline_quality_audit_service computes the consistency diff ONLY
        when both audit.consistency_risk_score and event.risk_score are non-
        None (`is not None and` at :313) - a NULL event score skips the
        branch; behavior pinned in test_pipeline_quality_audit_service.py,
        source pin here so removing the guard trips a unit-tier test."""
        import inspect

        from backend.services import pipeline_quality_audit_service

        src = inspect.getsource(pipeline_quality_audit_service)
        assert "audit.consistency_risk_score is not None and event.risk_score is not None" in src


def test_should_notify_skips_verdict_rejected_before_any_threshold() -> None:
    """§6's row "rejected ⇒ never notifies, even where a camera's
    risk_threshold sits inside the low band": the analyzer clamps the
    clamp-band score to <= low_max, but a clamp is NOT a skip - a camera
    with threshold 10 inside the low band would still page the owner for a
    verdict that says "not a threat". The skip therefore runs BEFORE the
    scored path's threshold comparisons (mirroring the NULL branch's
    ordering), keyed on the event's verification verdict."""
    from datetime import datetime

    from backend.models.notification_preferences import (
        CameraNotificationSetting,
        NotificationPreferences,
    )
    from backend.services.notification_filter import NotificationFilterService

    service = NotificationFilterService()
    prefs = NotificationPreferences(
        enabled=True, risk_filters=["low", "medium", "high", "critical"]
    )
    camera = CameraNotificationSetting(enabled=True, risk_threshold=10)
    ts = datetime(2026, 9, 25, 12, 0)

    # the exact §6 scenario: score in the low band, camera threshold inside it
    assert (
        service.should_notify(
            risk_score=15,
            camera_id="cam",
            timestamp=ts,
            global_prefs=prefs,
            camera_setting=camera,
            verification_verdict="rejected",
        )
        is False
    )
    # the same scored event with a non-rejected verdict still notifies
    assert (
        service.should_notify(
            risk_score=15,
            camera_id="cam",
            timestamp=ts,
            global_prefs=prefs,
            camera_setting=camera,
            verification_verdict="confirmed",
        )
        is True
    )
    # uncertainty notifies through the normal threshold (§6: "uncertain
    # keeps the model's score ... notifies through the normal threshold")
    assert (
        service.should_notify(
            risk_score=85,
            camera_id="cam",
            timestamp=ts,
            global_prefs=prefs,
            camera_setting=camera,
            verification_verdict="uncertain",
        )
        is True
    )
    # legacy events carry NO verdict - byte-identical behavior (D10 rule).
    assert (
        service.should_notify(
            risk_score=15,
            camera_id="cam",
            timestamp=ts,
            global_prefs=prefs,
            camera_setting=camera,
        )
        is True
    )
    # rejected is UNCONDITIONAL and first: the spec's rule is absolute
    # ("never notifies"), so it outranks even the NULL-score detector-only
    # rule - person evidence at threshold cannot page for a verdict that
    # says "not a threat". (In production a rejected event is scored, not
    # NULL - this pins the precedence should the two ever co-occur.)
    assert (
        service.should_notify(
            risk_score=None,
            camera_id="cam",
            timestamp=ts,
            global_prefs=prefs,
            camera_setting=camera,
            detection_class="person",
            detection_confidence=0.99,
            verification_verdict="rejected",
        )
        is False
    )
