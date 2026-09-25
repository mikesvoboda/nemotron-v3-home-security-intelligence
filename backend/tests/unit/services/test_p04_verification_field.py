"""P0.4 (spec §4): the `verification` field on Event REST + WS payloads.

Contract being pinned:
  * A verified event carries a populated `verification` object on both the
    REST EventResponse and the WebSocket event payload (so consumers branch
    on the verdict).
  * A LEGACY event carries NO `verification` key at all - "Legacy events
    have no verification row" (§4). Absent, not null: every existing byte of
    a legacy payload stays byte-identical.
  * The notification filter consumes ONLY `risk_score` - never a derived
    level, and never anything derived from a verification row - so a
    verification can never silently feed notifications (§6 step 3's owner
    rule: on a NULL score ONLY the detector evidence decides).
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from datetime import UTC, datetime

import pytest

from backend.api.schemas.events import EventResponse
from backend.api.schemas.websocket import WebSocketEventData
from backend.services import notification_filter as notification_filter_module
from backend.services.notification_filter import NotificationFilterService

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 25, 12, 0, 0, tzinfo=UTC)


def _verified_dict() -> dict:
    """A verification dict exactly as the API renders it (snake_case - the
    repo's payload convention, shared REST + WS via schemas/
    event_verification.py)."""
    return {
        "verdict": "confirmed",
        "scene_description": "Person at front door carrying a parcel",
        "criteria": [{"name": "person_present", "passed": True, "evidence": "front porch"}],
        "key_frame_detection_ids": [11, 12],
        "engine": "llama.cpp",
        "model_id": "qwen3-vl-4b",
        "latency_ms": 1400,
        "created_at": "2026-09-25T12:00:00+00:00",
    }


# =============================================================================
# REST: EventResponse.verification
# =============================================================================


class TestEventResponseVerification:
    def _base(self, **extra) -> EventResponse:
        return EventResponse(
            id=1,
            camera_id="front_door",
            started_at=NOW,
            risk_score=75,
            **extra,
        )

    def test_legacy_event_serializes_without_verification_key(self):
        """Absent, not null (spec §4). This is THE byte-identity rule: what a
        legacy consumer sees must not change at all."""
        dumped = self._base().model_dump(mode="json", exclude_none=True)
        assert "verification" not in dumped

    def test_legacy_exhaustive_dump_unchanged_shape(self):
        """Even the exclude_none=False dump keeps the legacy key set the same
        modulo the single new None field - and the DEFAULT response dump path
        (exclude_none=True, the routes' convention) drops it."""
        dumped = self._base().model_dump(mode="json")
        assert dumped.get("verification") is None
        assert "verification" not in self._base().model_dump(mode="json", exclude_none=True)

    def test_verified_event_serializes_populated_verification(self):
        response = self._base(verification=_verified_dict())
        dumped = response.model_dump(mode="json", exclude_none=True)
        assert dumped["verification"]["verdict"] == "confirmed"
        assert dumped["verification"]["key_frame_detection_ids"] == [11, 12]
        assert dumped["verification"]["latency_ms"] == 1400

    def test_verification_field_exists(self):
        assert "verification" in EventResponse.model_fields


# =============================================================================
# WebSocket: WebSocketEventData.verification
# =============================================================================


class TestWebSocketEventDataVerification:
    def _base(self, **extra) -> dict:
        return {
            "id": 1,
            "event_id": 1,
            "batch_id": "batch_abc123",
            "camera_id": "cam-uuid",
            "risk_score": 75,
            "risk_level": "high",
            "summary": "Person detected at front door",
            "reasoning": "Approaching entrance during evening hours",
            "started_at": "2026-09-25T12:00:00",
            **extra,
        }

    def test_legacy_payload_validates_and_dumps_without_verification(self):
        """The broadcaster pipe (WebSocketEventData.model_validate ->
        model_dump(mode="json")) must emit legacy payloads byte-identically -
        no verification key."""
        data = WebSocketEventData.model_validate(self._base())
        dumped = data.model_dump(mode="json")
        assert "verification" not in dumped
        assert dumped["risk_score"] == 75

    def test_null_score_legacy_payload_still_validates(self):
        """P0.25 interplay: an unverified event (NULL score) validates and
        still carries no verification key until 0.3 writes rows."""
        data = WebSocketEventData.model_validate(self._base(risk_score=None, risk_level=None))
        assert "verification" not in data.model_dump(mode="json")

    def test_verified_payload_carries_verification_through_validation(self):
        data = WebSocketEventData.model_validate(self._base(verification=_verified_dict()))
        dumped = data.model_dump(mode="json")
        assert dumped["verification"]["verdict"] == "confirmed"
        assert dumped["verification"]["model_id"] == "qwen3-vl-4b"

    def test_verification_field_exists(self):
        assert "verification" in WebSocketEventData.model_fields


# =============================================================================
# Notification filter pin (AST): a verification can never feed notifications
#
# The rule under test is a DATAFLOW rule ("should_notify's scored path
# consumes only risk_score"), and the dangerous failure mode is a future
# edit that quietly lets a derived/verification value route a notification.
# Behavior tests cannot pin absence; a structural test can. (The repo's
# contracts tier bans xfail/skip; this is neither - it is the only shape
# that can pin a negative.)
# =============================================================================


def _parse(obj) -> ast.Module:
    """Parse a function/method's source into an AST (methods come dedented
    with class-body indentation - dedent before parsing)."""
    return ast.parse(textwrap.dedent(inspect.getsource(obj)))


def _names_and_attrs(tree: ast.AST) -> tuple[set[str], set[str]]:
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    return names, attrs


class TestNotificationFilterConsumesOnlyRiskScore:
    """Spec §6: a NULL-score (verification_failed) notification is decided by
    DETECTOR evidence only; the scored path decides on risk_score only.
    Nothing from a verification (verdict, level, criteria...) may reach
    either decision. The pins below fail if any of that ever changes."""

    # Anything naming a verification-derived value (or detector evidence in
    # the scored path). risk_level is NOT in this set: the scored path may
    # derive it FROM risk_score (pin below); what it may never do is derive
    # it from, or read, anything a verification emits.
    FORBIDDEN = ("verdict", "verification", "criteria", "scene_description")

    def test_should_notify_takes_no_derived_level_input(self):
        """The entry point's inputs are the score + detector evidence +
        plumbing. A derived level (risk_level) is NOT an input: the filter
        consumes event.risk_score and derives level internally from it, so a
        level produced anywhere else (a verification, say) cannot ride in."""
        import inspect as _inspect

        params = set(_inspect.signature(NotificationFilterService.should_notify).parameters)
        assert "risk_score" in params
        for banned in ("risk_level", "verdict", "verification", *self.FORBIDDEN):
            assert banned not in params, f"{banned} must not be an input"

    def test_scored_path_call_receives_only_risk_score_score(self):
        """The call should_notify makes into _scored_notify may reference
        risk_score as its score input - and must reference NO detector or
        verification value (camera/timestamp/prefs plumbing aside)."""
        tree = _parse(NotificationFilterService.should_notify)
        calls = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "_scored_notify"
        ]
        assert calls, "should_notify must delegate to _scored_notify"
        for call in calls:
            arg_names: set[str] = set()
            for arg in list(call.args) + [kw.value for kw in call.keywords]:
                arg_names |= {n.id for n in ast.walk(arg) if isinstance(n, ast.Name)}
            assert "risk_score" in arg_names, "scored path must consume risk_score"
            for banned in (
                "detection_class",
                "detection_confidence",
                "risk_level",
                *self.FORBIDDEN,
            ):
                assert banned not in arg_names, f"{banned} must not feed the scored path"

    def test_scored_path_body_is_risk_score_only(self):
        """Inside _scored_notify: risk_score drives everything; the level is
        derived from the score by _risk_score_to_level(risk_score) and from
        nothing else; no detector or verification input at all."""
        tree = _parse(NotificationFilterService._scored_notify)
        names, _attrs = _names_and_attrs(tree)
        assert "risk_score" in names
        for banned in ("detection_class", "detection_confidence", *self.FORBIDDEN):
            assert banned not in names
        # the ONLY level source is the score-derived mapper, called with risk_score
        level_calls = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "_risk_score_to_level"
        ]
        assert level_calls
        for call in level_calls:
            arg_names = {
                n.id
                for a in list(call.args) + [kw.value for kw in call.keywords]
                for n in ast.walk(a)
                if isinstance(n, ast.Name)
            }
            assert arg_names == {"risk_score"}, "level must derive from risk_score alone"
        # ...and a local named risk_level may ONLY ever be bound from that
        # mapper - no other source of a level enters the scored path.
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "risk_level":
                        assert (
                            isinstance(node.value, ast.Call)
                            and isinstance(node.value.func, ast.Attribute)
                            and node.value.func.attr == "_risk_score_to_level"
                        ), "risk_level must be bound only from _risk_score_to_level"

    def test_mapper_input_is_the_score(self):
        """_risk_score_to_level's own input surface: exactly one positional
        argument (the score) - no level/verification passthrough parameter."""
        params = [
            p
            for p in inspect.signature(NotificationFilterService._risk_score_to_level).parameters
            if p != "self"
        ]
        assert params == ["score"], params

    def test_detector_branch_reads_no_score_no_verification(self):
        """The NULL-score branch consumes detector class/confidence + the
        settings threshold only - never risk_score, never a level, never a
        camera risk_threshold, never a verification value."""
        tree = _parse(NotificationFilterService._detector_only_notify)
        names, attrs = _names_and_attrs(tree)
        assert "risk_score" not in names
        assert "risk_level" not in names
        assert "risk_threshold" not in attrs
        for banned in self.FORBIDDEN:
            assert banned not in names and banned not in attrs

    def test_module_has_no_level_from_verification(self):
        """File-level guard: nothing in the module maps a verification
        (row/verdict) to a risk level."""
        tree = ast.parse(inspect.getsource(notification_filter_module))
        _, attrs = _names_and_attrs(tree)
        assert "verification" not in attrs
