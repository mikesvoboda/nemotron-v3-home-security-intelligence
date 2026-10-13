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
        "provenance": {"engine": "llama.cpp", "model_id": "Qwen3VL-8B-Instruct-Q4_K_M"},
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


# Spacing between synthetic detections in _mk_detections, in seconds. Chosen
# so the key-frame tests land on OPPOSITE sides of
# settings.key_frame_spread_seconds (default 10): the coalescing pair is
# count=2 at SPACING_S (=6 s, UNDER the threshold, so it coalesces to one
# frame), and every spanning case uses 2*SPACING_S (=12 s, OVER it, so ISS-005
# grants companion stills) whether by three rows a spacing apart or two rows
# two spacings apart. 6 and 12 straddle the default 10 with room on both sides,
# and the integer thresholds that keep ALL the key-frame tests green are exactly
# 6..11 (the config field is an int, gt=0, so that band is closed). Move it OUT
# of the band and the time-based canary below reddens ALONGSIDE one pair test,
# and WHICH pair test joins the canary names the broken side: under 6 the
# coalescing pair itself starts spanning (2 frames, not 1); at 12 or over the
# dwelling pair stops spanning. Pinning both sides is the point.
# `_mk_detections` takes `spacing_s` so one test can
# hold BOTH sides in a single batch — see
# test_the_spread_gate_is_time_based_not_file_based.
SPACING_S = 6


async def _mk_detections(
    db_session,
    camera,
    count: int = 2,
    *,
    object_type: str = "person",
    spacing_s: int = SPACING_S,
) -> list[int]:
    """Synthetic detection rows (fake paths, no file IO anywhere on this
    tier - the fake client never reads them).

    `object_type` and `spacing_s` exist so one test can build TWO pairs in the
    same batch: the selector keys pairs on `(camera_id, object_type)`, so a
    second class is a second independent pair, and `spacing_s` decides whether
    THAT pair spans the threshold. Both are keyword-only and defaulted, so the
    two original callers see identical data.

    Rows land `spacing_s` apart (default `SPACING_S`, deliberately INSIDE
    `settings.key_frame_spread_seconds`, default 10, ISS-005). The key-frame
    assertion in TestScoredEventOnLiveSchema is a coalescing claim, and the
    span is what decides it: a (camera, class) pair whose members are more
    than the threshold apart is a DWELLING pair, and ISS-005 lets it spend a
    spare slot on its temporally farthest distinct still - so 2 members on
    distinct files yield 2 key frames by design. The original fixture spaced
    rows a MINUTE apart (60 s >> 10 s), which is exactly the spanning case,
    while asserting the non-spanning outcome; that is why the nightly turned
    red here and why the fix is the fixture's clocks, not the `== 1`. Keep
    `SPACING_S * (count - 1)` under the threshold, or the pair spans and the
    count legitimately rises - see
    TestScoredEventOnLiveSchema.test_a_dwelling_pair_widens_the_key_frames_on_the_live_pipe
    below, which pins the spanning side on purpose."""
    ids: list[int] = []
    for i in range(count):
        det = Detection(
            camera_id=camera.id,
            file_path=f"/export/foscam/vlm/det_{uuid.uuid4().hex[:6]}.jpg",
            object_type=object_type,
            confidence=0.91,
            detected_at=datetime(2026, 9, 25, 10, 0, i * spacing_s, tzinfo=UTC),
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
        assert stored.model_id == "Qwen3VL-8B-Instruct-Q4_K_M"
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

    async def test_a_dwelling_pair_widens_the_key_frames_on_the_live_pipe(
        self, db_session, camera, real_redis
    ):
        """The OTHER side of the spread threshold, on the real schema. The
        coalescing test above proves a pair INSIDE `key_frame_spread_seconds`
        collapses to one frame; this proves a DWELLING pair (3 rows, 2 x
        SPACING_S = 12 s apart > the 10 s default) is granted ISS-005's spare
        slots — the same analyzer call, the same table, only the clocks
        differ. Without this half, a future "fix" that disabled spread
        entirely would leave the coalescing test green and silently drop the
        dwelling behaviour the spec §2 asks for.

        The count is the SELECTOR's, capped at MAX_KEY_FRAMES=4; 3 distinct
        files across one dwelling pair all fit, so the expectation is 3 (not
        ">= 2", which would also pass a broken selector that picks 2)."""
        from backend.core.config import get_settings
        from backend.services.event_broadcaster import reset_broadcaster_state

        settings = get_settings()
        # Precondition the whole point rests on: the pair spans the threshold.
        assert settings.key_frame_spread_seconds < 2 * SPACING_S, (
            f"fixture no longer spans: 2*{SPACING_S} s vs threshold "
            f"{settings.key_frame_spread_seconds} s — move SPACING_S or skip "
            "this assertion, but do NOT leave a vacuous dwelling case"
        )

        det_ids = await _mk_detections(db_session, camera, count=3)
        reset_broadcaster_state()
        analyzer = VlmAnalyzer(
            vlm_client=FakeClient(verdict=make_verdict()), redis_client=real_redis
        )
        event = await analyzer.analyze_batch(
            f"batch-{uuid.uuid4().hex[:8]}", camera_id=camera.id, detection_ids=det_ids
        )
        reset_broadcaster_state()
        stored = await db_session.scalar(
            select(EventVerification).where(EventVerification.event_id == event.id)
        )
        assert stored is not None
        assert set(stored.key_frame_detection_ids) <= set(det_ids)
        assert len(stored.key_frame_detection_ids) == 3, (
            f"a dwelling pair should widen to its distinct stills, got "
            f"{stored.key_frame_detection_ids}"
        )

    async def test_the_spread_gate_is_time_based_not_file_based(
        self, db_session, camera, real_redis
    ):
        """Which half of the eligibility gate actually fires, on the live pipe.

        The gate is one OR'd condition
        (`len(distinct_files) < 2 or span <= spread_seconds`), and the test
        above cannot tell the two halves apart: its pair has BOTH distinct
        files and a spanning clock, so it is eligible either way and its count
        is identical under a mutant that deletes either clause. This batch
        separates them by putting TWO pairs in one batch — pairs key on
        `(camera_id, object_type)`, so a second class is a second independent
        pair:

        * `person`, 2 rows `2 x SPACING_S` apart -> spans (12 s > 10) -> ISS-005
          grants its second still;
        * `car`, 2 rows `SPACING_S` apart -> does NOT span (6 s <= 10), but has
          two distinct files just like the person pair.

        Correct code: person rep + car rep + the person pair's companion =
        **3**, and the car pair gets nothing, because its clock does not span.
        Delete the span clause and the car pair is eligible on file diversity
        ALONE, so it takes a companion too: **4**. The totals differ only if
        the time comparison is what gated the grant, which is the whole claim.
        3 vs 4 also stays inside MAX_KEY_FRAMES=4, so the cap cannot mask it.

        Both pairs are `count=2`. That is load-bearing: with the person pair at
        `count=3` (the shape this test first shipped) both pairs exhaust their
        slots either way and the total is 4 under the correct code AND under
        the mutant — only the IDENTITY of the 4th pick differs. Measured on the
        real selector: 3-row person pair -> `n=4` correct vs `n=4` mutant;
        2-row person pair -> `n=3` vs `n=4`. The count is asserted anyway, and
        the per-pair identity below is asserted too, so a mutant that only
        swaps WHICH still fills the last slot is caught even where a count
        would not be.

        The other clause is NOT claimed covered. Removing `len(distinct_files)
        < 2` instead leaves every test in this file green (measured: 6 passed)
        because `_spread_companions` already refuses a candidate whose file is
        in `shown` — that clause is unreachable through this output, at any
        shape. So the time half is the only half the integration tier can see,
        and it is the half §2's dwelling rule is about."""
        from backend.core.config import get_settings
        from backend.services.event_broadcaster import reset_broadcaster_state

        settings = get_settings()
        thr = settings.key_frame_spread_seconds
        # Both halves of the design, preconditioned: one pair spans, one does
        # not, and the in-span pair is not accidentally the one with fewer
        # files (if it were, a file-only gate would look identical to a
        # time-only gate and the test would prove nothing).
        assert thr < 2 * SPACING_S, f"person pair must span: {2 * SPACING_S} s vs {thr} s"
        assert thr >= SPACING_S, f"car pair must NOT span: {SPACING_S} s vs {thr} s"

        person_ids = await _mk_detections(
            db_session, camera, count=2, object_type="person", spacing_s=2 * SPACING_S
        )
        car_ids = await _mk_detections(db_session, camera, count=2, object_type="car")
        det_ids = [*person_ids, *car_ids]
        reset_broadcaster_state()
        analyzer = VlmAnalyzer(
            vlm_client=FakeClient(verdict=make_verdict()), redis_client=real_redis
        )
        event = await analyzer.analyze_batch(
            f"batch-{uuid.uuid4().hex[:8]}", camera_id=camera.id, detection_ids=det_ids
        )
        reset_broadcaster_state()
        stored = await db_session.scalar(
            select(EventVerification).where(EventVerification.event_id == event.id)
        )
        assert stored is not None
        picks = set(stored.key_frame_detection_ids)
        assert picks <= set(det_ids)
        assert len(picks) == 3, (
            f"expected 2 reps + 1 spanning-pair companion = 3, got {len(picks)}: "
            f"{sorted(picks)} — 4 means the in-span car pair spread too, i.e. the "
            "eligibility gate stopped comparing clocks"
        )
        # The grant went to the DWELLING pair, not to whichever pair came
        # second: pinning the companion's identity is what stops a selector
        # that fills slots by arrival order from passing on count alone.
        # car_ids[1] is the pair's REPRESENTATIVE: equal confidence, so
        # _rank_key breaks the tie on recency and the later row wins. Referring
        # to it positionally rather than by max(id) keeps the assertion honest
        # if detection ids ever stop being issued in insert order.
        assert picks == set(person_ids) | {car_ids[1]}, (
            f"expected both dwelling-pair stills plus the car representative "
            f"{car_ids[1]}, got {sorted(picks)} — car_ids[0] in the picks means "
            "the in-span pair spread on file diversity instead of on time"
        )

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
