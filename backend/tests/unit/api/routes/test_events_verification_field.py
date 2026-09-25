"""P0.4 (spec §4) route-side seam: how events.py RENDERS the verification
object (the end-to-end REST/DB path lives in
backend/tests/integration/test_p04_event_verifications.py).

Pinned here:
  * `verification` is a selectable sparse fieldset field (NEM-1434) - and the
    field-list doc string the endpoint advertises names it.
  * verification_payload's presence rule at the row level: no rows (legacy)
    -> None -> the schema's exclude_if drops the KEY; rows -> the newest one
    (a repair path stacking rows must not resurrect a stale verdict).
  * A MagicMock event (the repo's unit-test habit for route code) renders NO
    verification - only a real row collection does.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.api.routes.events import VALID_EVENT_LIST_FIELDS
from backend.api.schemas.event_verification import verification_payload

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 25, 12, 0, 0, tzinfo=UTC)


def _row(row_id: int, verdict: str = "confirmed", created_at=NOW):
    """An EventVerification-shaped row (the payload schema reads attributes;
    the real model is pinned in tests/unit/models/test_event_verification.py)."""
    return SimpleNamespace(
        id=row_id,
        verdict=verdict,
        scene_description="Person at front door",
        criteria=[{"name": "person_present", "passed": True, "evidence": "porch"}],
        key_frame_detection_ids=[11, 12],
        engine="llama.cpp",
        model_id="qwen3-vl-4b",
        latency_ms=1400,
        created_at=created_at,
    )


class TestFieldSelection:
    def test_verification_is_a_selectable_list_field(self):
        assert "verification" in VALID_EVENT_LIST_FIELDS

    def test_endpoint_advertisement_names_verification(self):
        """The fields Query description is the API's contract text: the
        selectable list there must match the allowlist (drift = the pin
        fails)."""
        import inspect

        from backend.api.routes import events as events_module

        src = inspect.getsource(events_module)
        # the description lists the selectable fields verbatim
        assert "thumbnail_url, verification" in src


class TestVerificationPayloadPresence:
    def test_legacy_event_no_rows_is_none(self):
        event = SimpleNamespace(verifications=[])
        assert verification_payload(event) is None

    def test_mocked_event_never_fabricates_a_payload(self):
        """MagicMock.verifications is truthy but not a row collection - the
        isinstance guard keeps the key ABSENT instead of validating junk."""
        event = MagicMock()
        assert verification_payload(event) is None

    def test_verified_event_renders_payload(self):
        event = SimpleNamespace(verifications=[_row(1)])
        payload = verification_payload(event)
        assert payload is not None
        assert payload.verdict == "confirmed"
        assert payload.model_id == "qwen3-vl-4b"

    def test_newest_row_wins_when_rows_stack(self):
        older = _row(1, verdict="rejected", created_at=datetime(2026, 9, 25, 11, 0, tzinfo=UTC))
        newer = _row(2, verdict="confirmed", created_at=NOW)
        payload = verification_payload(SimpleNamespace(verifications=[older, newer]))
        assert payload.verdict == "confirmed"

    def test_payload_is_the_same_object_shape_as_the_ws_schema(self):
        """§3 drift doctrine: REST and WS render ONE object (spec §4)."""
        from backend.api.schemas.websocket import WebSocketEventData

        event = SimpleNamespace(verifications=[_row(1)])
        payload = verification_payload(event)
        ws = WebSocketEventData.model_validate(
            {
                "id": 1,
                "event_id": 1,
                "batch_id": "b",
                "camera_id": "cam",
                "risk_score": 75,
                "risk_level": "high",
                "summary": "s",
                "reasoning": "r",
                "started_at": "2026-09-25T12:00:00",
                "verification": payload,
            }
        )
        assert ws.verification is not None
        assert ws.verification.verdict == "confirmed"
