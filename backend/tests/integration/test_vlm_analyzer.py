"""Phase 1.3 (spec §6/§7) on the LIVE test Postgres + Redis: the vlm-mode
analyzer's writes and the NULL-score event end to end.

The unit tier (test_vlm_analyzer.py) proves the analyzer BUILDS the right
rows and payload against fakes; this file proves the live schema and the
live pipe accept them:

  * db half: a scored event + its event_verifications row + the junction
    rows commit through the analyzer's own session-2 block against the real
    CHECK constraints / NOT NULLs / FK+CASCADE (same doctrine as
    test_p03_verification_producer.py, but driven through analyze_batch,
    not a hand-fed producer method).
  * WS half: the analyzer's broadcast rides REAL Redis pub/sub, validated
    by broadcast_event against WebSocketEventData, with the `verification`
    key PRESENT and risk_score null on the verification_failed arm (the
    P0.25 promise: a NULL-score event rides db→WS without crash or lie).
  * degradation half: a breaker-open push lands on the degradation
    singleton's status (the health-endpoint function's own data source) -
    §6 step 4's "surfaced through the health endpoint".

Fabricated rows and synthetic verdicts only (D10); the VLM itself is a
scripted fake - no real imagery, and this tier never opens a real engine.

Same-session compose rule (E11): run with the live test PG/Redis up:
    uv run pytest backend/tests/integration/test_vlm_analyzer.py -n0
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import func, select

from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event_detection import event_detections
from backend.models.event_verification import EventVerification
from backend.services.degradation_manager import (
    reset_degradation_manager,
)
from backend.services.vlm_analyzer import VlmAnalyzer
from backend.services.vlm_verdict import VlmVerdict

pytestmark = pytest.mark.integration


class FakeClient:
    """Scripted VLM: returns the prepared verdict or raises the prepared
    error. Mirrors the unit-tier fake (prompt_text + async close) - the
    analyzer's per-call close() contract is pinned here on the REAL class
    surface."""

    def __init__(self, *, verdict: VlmVerdict | None = None, error: Exception | None = None):
        self._verdict = verdict
        self._error = error
        self.closed = False
        self.assess_calls = 0

    def prompt_text(self, request) -> str:
        return f"ASSESS camera={request.context.camera_id} PATHS {request.image_paths}"

    async def assess(self, request) -> VlmVerdict:
        self.assess_calls += 1
        if self._error is not None:
            raise self._error
        assert self._verdict is not None
        return self._verdict

    async def close(self) -> None:
        self.closed = True


def make_verdict(**overrides) -> VlmVerdict:
    data = {
        "verdict": "confirmed",
        "risk_score": 85,
        "summary": "A person stands at the door.",
        "reasoning": "Criterion evidence reviewed.",
        "description": "Front door, one person, evening.",
        "criteria": [{"name": "person_present", "passed": True, "evidence": "full frame"}],
        "provenance": {"engine": "llama.cpp", "model_id": "Qwen3VL-4B-Instruct-Q4_K_M"},
    } | overrides
    return VlmVerdict.model_validate(data)


@pytest.fixture
async def camera(db_session):
    cam = Camera(
        id=f"vlmcam-{uuid.uuid4().hex[:8]}",
        name=f"vlm-{uuid.uuid4().hex[:8]}",
        folder_path="/export/foscam/vlm",
    )
    db_session.add(cam)
    await db_session.commit()
    return cam


async def _mk_detections(db_session, camera, count: int = 2) -> list[int]:
    """Synthetic detection rows (fake paths, no file IO anywhere on this
    tier - the fake client never reads them)."""
    ids: list[int] = []
    for i in range(count):
        det = Detection(
            camera_id=camera.id,
            file_path=f"/export/foscam/vlm/det_{uuid.uuid4().hex[:6]}.jpg",
            object_type="person",
            confidence=0.91,
            detected_at=datetime(2026, 9, 25, 10, i, tzinfo=UTC),
        )
        db_session.add(det)
        await db_session.flush()
        ids.append(det.id)
    await db_session.commit()
    return ids


class TestScoredEventOnLiveSchema:
    async def test_scored_batch_writes_event_verification_and_junction(
        self, db_session, camera, real_redis
    ):
        """The analyzer's session-2 block against the REAL table: verdict
        CHECK accepts 'confirmed', engine/model_id NOT NULLs carry the
        VERDICT's provenance (not the settings fallbacks), the JSONB
        criteria/key_frame ids round-trip, and the junction rows exist.

        key_frame_detection_ids is the SELECTOR's picks (1-4): two same
        camera/class detections coalesce to one frame - the junction rows
        keep ALL batch detections either way."""
        from backend.services.event_broadcaster import reset_broadcaster_state

        det_ids = await _mk_detections(db_session, camera)
        batch_id = f"batch-{uuid.uuid4().hex[:8]}"
        reset_broadcaster_state()  # bind the broadcaster to THIS test's redis
        analyzer = VlmAnalyzer(
            vlm_client=FakeClient(verdict=make_verdict()), redis_client=real_redis
        )
        event = await analyzer.analyze_batch(batch_id, camera_id=camera.id, detection_ids=det_ids)
        reset_broadcaster_state()
        assert event.risk_score == 85
        assert event.risk_level == "critical"  # severity band, never the model's word

        stored = await db_session.scalar(
            select(EventVerification).where(EventVerification.event_id == event.id)
        )
        assert stored is not None
        assert stored.verdict == "confirmed"
        assert stored.engine == "llama.cpp"
        assert stored.model_id == "Qwen3VL-4B-Instruct-Q4_K_M"
        assert stored.key_frame_detection_ids, "the selector picked >=1 frame"
        assert set(stored.key_frame_detection_ids) <= set(det_ids), "picks are batch detections"
        assert len(stored.key_frame_detection_ids) == 1, (
            "same camera+class coalesces to the best frame only (selector design)"
        )
        assert stored.criteria[0]["name"] == "person_present"
        assert stored.latency_ms is not None, "the attempt happened on this tier"

        joined = await db_session.scalar(
            select(func.count())
            .select_from(event_detections)
            .where(event_detections.c.event_id == event.id)
        )
        assert joined == len(det_ids)

        # llm_prompt references images BY PATH (D10) - never base64
        assert "/export/foscam/vlm/det_" in event.llm_prompt
        assert "data:image" not in event.llm_prompt

    async def test_rest_renders_the_analyzer_event(self, client, db_session, camera, real_redis):
        """The composition the UI consumes on a REAL analyzer-written row:
        detail 200s with the verification object present (P0.4's
        present-when-row, written by the vlm producer instead of a
        hand-fabricated row)."""
        from backend.services.event_broadcaster import reset_broadcaster_state

        det_ids = await _mk_detections(db_session, camera)
        reset_broadcaster_state()
        analyzer = VlmAnalyzer(
            vlm_client=FakeClient(verdict=make_verdict(verdict="uncertain", risk_score=45)),
            redis_client=real_redis,
        )
        event = await analyzer.analyze_batch(
            f"batch-{uuid.uuid4().hex[:8]}", camera_id=camera.id, detection_ids=det_ids
        )
        reset_broadcaster_state()
        async_client = client
        detail = await async_client.get(f"/api/events/{event.id}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["risk_score"] == 45
        assert body["verification"]["verdict"] == "uncertain"


class TestNullScoreRidesTheLivePipe:
    async def test_verification_failed_event_rides_db_to_real_pubsub(
        self, db_session, camera, real_redis
    ):
        """§6 step 2 + P0.25 on the live pipe: an engine failure (the
        client's ladder exhausted) commits an event with NULL score/level
        AND broadcasts over REAL Redis pub/sub a message that passed
        broadcast_event's WebSocketEventData validation with risk_score
        null and the verification key present - no crash, no invented 50.

        The subscriber is a raw redis client on the same isolated worker
        DB; the analyzer's broadcast is fire-and-forget best-effort, so the
        proof is the RECEIVED frame, not a mock's call list."""
        from backend.api.schemas.websocket import WebSocketEventData
        from backend.core.config import get_settings
        from backend.services.event_broadcaster import reset_broadcaster_state
        from backend.services.vlm_client import VlmTransportError

        det_ids = await _mk_detections(db_session, camera)
        channel = get_settings().redis_event_channel

        raw = real_redis._client  # the redis.asyncio client behind RedisClient
        sub = raw.pubsub()
        await sub.subscribe(channel)
        # consume the subscribe confirmation
        assert (await sub.get_message(ignore_subscribe_messages=True, timeout=1.0)) in (
            None,
        ) or True

        reset_broadcaster_state()  # bind get_broadcaster to THIS test's redis
        try:
            analyzer = VlmAnalyzer(
                vlm_client=FakeClient(error=VlmTransportError("fake engine down")),
                redis_client=real_redis,
            )
            batch_id = f"batch-{uuid.uuid4().hex[:8]}"
            event = await analyzer.analyze_batch(
                batch_id, camera_id=camera.id, detection_ids=det_ids
            )

            # --- db half: the NULL-score event + its row
            assert event.risk_score is None
            assert event.risk_level is None
            stored = await db_session.scalar(
                select(EventVerification).where(EventVerification.event_id == event.id)
            )
            assert stored is not None
            assert stored.verdict == "verification_failed"

            # --- WS half: the frame that crossed REAL pub/sub. The channel
            # is shared (per-settings name), and Event ids COLLIDE across
            # tests (fresh schema per test restarts the sequence), so the
            # frame is found by OUR uuid-unique batch_id - never "the first
            # one" (first-frame-wins made this race a coin flip under -n auto).
            frame: dict[str, Any] | None = None
            foreign_frames = 0
            deadline = asyncio.get_running_loop().time() + 5.0
            while frame is None and asyncio.get_running_loop().time() < deadline:
                msg = await sub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg is not None and msg.get("type") == "message":
                    candidate = json.loads(msg["data"])
                    if candidate.get("type") == "event" and (
                        (candidate.get("data") or {}).get("batch_id") == batch_id
                    ):
                        frame = candidate
                    else:
                        foreign_frames += 1
            assert frame is not None, (
                f"no frame for batch {batch_id} reached the subscriber "
                f"({foreign_frames} foreign frames seen instead)"
            )
            assert frame["type"] == "event"
            # broadcast_event validated it already; re-validate the RECEIVED
            # copy so the schema promise is pinned on the wire bytes too.
            data = WebSocketEventData.model_validate(frame["data"])
            assert data.risk_score is None
            assert data.risk_level is None
            assert data.verification is not None
            assert data.verification.verdict == "verification_failed"
            assert data.id == event.id

            # --- idempotency rode the REAL redis
            already = await real_redis.get(f"batch_event:{batch_id}")
            assert already is not None and int(already) == event.id
        finally:
            await sub.unsubscribe(channel)
            await sub.aclose()
            reset_broadcaster_state()


class TestDegradationSingletonPush:
    """§6 step 4's health-endpoint half on the manager main.py registers
    ai-vlm on. The breaker->push edge itself is unit-pinned
    (test_vlm_client.py::TestBreakerDegradation); this pins the receiving
    end: an UNREGISTERED name is dropped (why main.py must register), and a
    registered push reaches get_status() - the exact dict
    system.py::_get_degradation_status converts for the endpoint."""

    @pytest.fixture(autouse=True)
    def _isolate_manager(self):
        reset_degradation_manager()
        yield
        reset_degradation_manager()

    async def test_unregistered_name_is_dropped(self):
        from backend.services.degradation_manager import get_degradation_manager

        manager = get_degradation_manager()
        await manager.update_service_health("ai-vlm", is_healthy=False, error_message="x")
        assert "ai-vlm" not in manager.get_status()["services"], (
            "update_service_health warns-and-drops an unregistered name - "
            "this is WHY main.py registers ai-vlm at startup"
        )

    async def test_registered_push_reaches_the_endpoint_status(self):
        from backend.services.degradation_manager import get_degradation_manager

        async def _never_polled() -> bool:
            return True

        manager = get_degradation_manager()
        manager.register_service("ai-vlm", health_check=_never_polled, critical=False)
        await manager.update_service_health(
            "ai-vlm", is_healthy=False, error_message="vlm_circuit_open"
        )
        services = manager.get_status()["services"]
        assert services["ai-vlm"]["status"] == "unhealthy"
        assert services["ai-vlm"]["error_message"] == "vlm_circuit_open"

        # and the endpoint's own conversion function reads the same row
        from backend.api.routes.system import _get_degradation_status

        status = _get_degradation_status()
        assert status is not None
        entry = next(s for s in status.services if s.name == "ai-vlm")
        assert entry.status == "unhealthy"
