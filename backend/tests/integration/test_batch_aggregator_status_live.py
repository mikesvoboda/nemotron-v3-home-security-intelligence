"""Live-batch witness for ``_get_batch_aggregator_status`` (UR-48 lane defect).

Every prior test of ``GET /api/system/pipeline`` reaches the reader on a stack
with NO live batch — so both early returns fire — or through a fake that answers
a LIST key with a JSON string, a shape real Redis cannot return. That is why
``"batch_aggregator": null`` for a live batch ships under green CI. This file is
the reproduction the claim commit promised, against a REAL Redis, driving
production code on both ends: ``BatchAggregator.add_detection`` opens the batch,
``_get_batch_aggregator_status`` reads it.

Cite note: this commit edits both ``system.py`` and ``vlm_analyzer.py``, so
every line number from those two files cited below is at the un-cured base
``7a2aa8ca8``, where each one names its exact site. (The cure adds comment
lines inside the reader, so at the merged head those sites sit 26-32 lines
lower depending on depth — the def shifts +26, the ``except RedisError`` +32 —
which is why the base numbers are kept.) Cites into ``batch_aggregator.py``
and ``core/redis.py`` are live — this commit does not touch those files.

The two stacked mismatches inside ``_get_batch_aggregator_status``
(``backend/api/routes/system.py:4042`` at the base):

1. **LIST read with GET.** The writer appends to ``batch:<id>:detections`` with
   RPUSH — a LIST (``backend/services/batch_aggregator.py:23``). The reader asks
   for it with ``pipe.get`` (:4089). GET on a LIST raises
   ``ResponseError: WRONGTYPE`` (⊂ RedisError), swallowed at :4130 into
   ``return None`` — the ONLY shape this function yields on an exception, since
   both no-batch paths return a well-formed object via
   ``_build_empty_batch_response``. A ``null`` with a batch alive IS the proof
   the read raised.
2. **JSON-scalar read with a bare float().** Masked by #1. ``add_detection``
   rewrites ``batch:<id>:last_activity`` through the ``RedisClient.set`` wrapper
   (:641), which always ``json.dumps`` (:1228-1229), so it sits on disk as
   ``'"<float>"'``; ``float(last_activity_str)`` at :4107 raises ValueError,
   caught per-batch at :4119, dropping that batch. Cure #1 ALONE therefore
   returns a tidy ``active_batches: 0`` with the live batch missing — which is
   why the fix is both edits.

Run serially, like the other real-Redis specs:
    uv run pytest backend/tests/integration/test_batch_aggregator_status_live.py -n0
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import pytest

from backend.api.routes.system import _get_batch_aggregator_status
from backend.services.batch_aggregator import BatchAggregator

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

pytestmark = pytest.mark.integration


def _camera_id() -> str:
    """A per-test camera id so runs never share a batch pointer."""
    return f"cam-witness-{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def opened_batches(real_redis: RedisClient) -> AsyncIterator[list[tuple[str, str]]]:
    """Yield a list the test appends (camera_id, batch_id) to; delete exactly those keys.

    Exact-key teardown, not a ``batch:*`` sweep: this tier's real_redis database
    can hold other tests' batches, and a broad sweep would delete theirs.
    """
    created: list[tuple[str, str]] = []
    yield created
    client = real_redis._ensure_connected()
    keys: list[str] = []
    for camera_id, batch_id in created:
        keys.extend(
            [
                f"batch:{camera_id}:current",
                f"batch:{batch_id}:camera_id",
                f"batch:{batch_id}:started_at",
                f"batch:{batch_id}:last_activity",
                f"batch:{batch_id}:detections",
                f"batch:{batch_id}:pipeline_start_time",
            ]
        )
    if keys:
        await client.delete(*keys)


@pytest.fixture(autouse=True)
def no_vlm_wake(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralize the fire-and-forget engine wake (not the code under test)."""
    from backend.services import vlm_client

    async def _noop() -> None:
        return None

    monkeypatch.setattr(vlm_client, "wake_ai_vlm", _noop)


async def _open_live_batch(
    real_redis: RedisClient,
    opened_batches: list[tuple[str, str]],
    n_detections: int = 3,
) -> tuple[str, str]:
    """Drive the production writer to open one batch holding n detections.

    Confidence 0.3 / no threat/smoke args keeps ``should_bypass_batch`` False so
    the NORMAL batching path runs — the path a real camera detection takes.
    """
    aggregator = BatchAggregator(real_redis)
    camera_id = _camera_id()
    batch_id: str | None = None
    for i in range(n_detections):
        batch_id = await aggregator.add_detection(
            camera_id=camera_id,
            detection_id=900_000 + i,
            _file_path=f"/path/to/witness-{i}.jpg",  # metadata only — never opened
            confidence=0.3,
            object_type="person",
        )
    assert batch_id is not None
    opened_batches.append((camera_id, batch_id))
    return camera_id, batch_id


async def _keys_for(real_redis: RedisClient, camera_id: str, batch_id: str) -> dict[str, str]:
    """Read the raw on-disk value of each metadata key the production writer made."""
    client = real_redis._ensure_connected()
    names = {
        "current": f"batch:{camera_id}:current",
        "camera_id": f"batch:{batch_id}:camera_id",
        "started_at": f"batch:{batch_id}:started_at",
        "last_activity": f"batch:{batch_id}:last_activity",
    }
    out: dict[str, str] = {}
    for field, key in names.items():
        value = await client.get(key)
        assert isinstance(value, str), f"{key} missing - the writer did not create it"
        out[field] = value
    return out


async def test_writer_stores_detections_as_a_list_and_last_activity_as_json(
    real_redis: RedisClient, opened_batches: list[tuple[str, str]]
) -> None:
    """Premise pin: the exact on-disk shapes that force BOTH halves of the cure.

    Not a symptom test — it pins the shapes the reader must tolerate, and it is
    what makes mismatch #2's "masked by #1" claim checkable rather than prose:

    - detections is a LIST (RPUSH), so any ``GET`` of it raises WRONGTYPE;
    - last_activity is a JSON-quoted scalar because add_detection writes it
      through the ``set`` wrapper, while started_at is written RAW through the
      internal client by the same call — one call, two serializers.

    If someone "fixes" this by moving the writer to JSON strings, this pin goes
    red on purpose: that alternative needs a key migration for batches alive
    across an upgrade, and it must be discussed, not slipped in.
    """
    camera_id, batch_id = await _open_live_batch(real_redis, opened_batches, n_detections=2)
    client = real_redis._ensure_connected()

    assert await client.type(f"batch:{batch_id}:detections") == "list"
    assert await client.llen(f"batch:{batch_id}:detections") == 2

    raw = await _keys_for(real_redis, camera_id, batch_id)
    assert raw["current"] == batch_id, "batch pointer is written raw"
    # started_at goes through the raw client (batch_aggregator.py:427) -> a bare
    # float literal on disk; last_activity goes through the JSON wrapper (:641).
    assert not raw["started_at"].startswith('"'), f"unexpected quote: {raw['started_at']!r}"
    assert raw["last_activity"].startswith('"'), (
        f"expected a JSON-quoted scalar, got {raw['last_activity']!r}"
    )
    assert isinstance(json.loads(raw["last_activity"]), str)
    float(raw["started_at"])  # parses as-is -> system.py:4106 is not a raising site
    # The two scalars are written 2 lines apart by one method yet differ: the
    # quoted one is what system.py:4107's bare float() chokes on. If the wrapper
    # ever stops JSON-serializing, this pin goes red and the cure must be
    # re-read, because half of it would no longer be needed.
    with pytest.raises(ValueError, match="could not convert string to float"):
        float(raw["last_activity"])


async def test_live_batch_is_reported_by_the_status_reader(
    real_redis: RedisClient, opened_batches: list[tuple[str, str]]
) -> None:
    """The symptom pin: a live batch must survive the reader intact.

    Four states this distinguishes, and the message names which one you are in:
      un-cured        -> status is None (WRONGTYPE swallowed at :4130)
      cure #2 only    -> status is None (the LIST read still raises)
      cure #1 only    -> status is well-formed, but this batch is absent
      both cures      -> green
    """
    camera_id, batch_id = await _open_live_batch(real_redis, opened_batches, n_detections=3)

    # Re-arm both scalars with ages far from now and distinct from each other,
    # each through the SAME writer production uses: started_at raw (:427),
    # last_activity through the set wrapper so it lands JSON-quoted (:641) and
    # cure #2 stays load-bearing here. The near-now values add_detection leaves
    # would pass an age assert even if the reader ignored both keys and fell back
    # to current_time (system.py:4106-4107); these do not.
    past = time.time() - 120.0
    await real_redis._ensure_connected().set(f"batch:{batch_id}:started_at", str(past), ex=600)
    await real_redis.set(f"batch:{batch_id}:last_activity", str(time.time() - 60.0), expire=600)

    status = await _get_batch_aggregator_status(real_redis)

    assert status is not None, (
        "reader returned None with a live batch present: the GET-on-a-LIST "
        "WRONGTYPE path (system.py:4089 -> :4130) is firing"
    )
    by_id = {b.batch_id: b for b in status.batches}
    assert batch_id in by_id, (
        f"live batch {batch_id} is absent although the reader produced a "
        f"well-formed response (active_batches={status.active_batches}): the "
        "detections read succeeded but the JSON-quoted last_activity scalar "
        "raised at system.py:4107 and the per-batch handler dropped it (:4119)"
    )
    info = by_id[batch_id]
    assert info.camera_id == camera_id
    assert info.detection_count == 3
    # The reader must echo the ages WRITTEN, not now-relative fallbacks: started
    # 120s ago and last active 60s ago cannot both report ~0, which is exactly
    # what the `else current_time` / `else started_at` fallbacks at
    # system.py:4106-4107 emit if the scalars are never read. The two tolerances
    # are disjoint, so a swap of the two scalars reddens too.
    assert abs(info.age_seconds - 120.0) < 5.0, f"age_seconds={info.age_seconds!r}"
    assert abs(info.last_activity_seconds - 60.0) < 5.0, (
        f"last_activity_seconds={info.last_activity_seconds!r}"
    )


async def test_no_live_batch_returns_a_well_formed_empty_object(
    real_redis: RedisClient, opened_batches: list[tuple[str, str]]
) -> None:
    """Control: the no-batch path is a well-formed object, not null.

    The existing tier suite covers only paths like this one (and a ``None``
    dependency), which is why a green suite never saw the break. This control is
    what makes the ``is not None`` above meaningful: the reader does have a
    correct non-null shape available for an empty stack, so a null on a POPULATED
    stack is a bug rather than a design choice.

    A foreign ``batch:*:current`` in this worker db narrows the claim, it does
    not excuse it. That happens only under ``nightly-full-gate.yml:139``, which
    runs this tier unfiltered so ``test_concurrency.py`` - the tier's only other
    real-Redis batch writer, and one that leaves its pointers behind - can share
    a db with this file; the per-PR Services job never sees it (run
    ``38701617347`` ran this test with no pointer present). Skipping there would
    report green without having checked anything, the exact failure mode this
    file exists to fix, so the narrowed branch still demands the non-null shape
    that the cure is about. Only the clean-stack branch can also demand zeros.
    """
    client = real_redis._ensure_connected()
    foreign = [k async for k in client.scan_iter(match="batch:*:current", count=100)]
    if foreign:
        status = await _get_batch_aggregator_status(real_redis)
        assert status is not None, (
            f"reader returned null with foreign batches {foreign} on the stack - "
            "the shipped defect this file reproduces"
        )
        return

    status = await _get_batch_aggregator_status(real_redis)
    assert status is not None
    assert status.active_batches == 0
    assert status.batches == []


async def test_null_is_reserved_for_the_unavailable_stack() -> None:
    """Control: ``None`` is the Redis-unavailable shape (system.py:4056-4057).

    Pinned so the null in the endpoint's own response model stays a signal: the
    tests above assert non-null WITH a live batch, and this asserts null with NO
    stack at all. Together they leave no path where a live batch may be null.
    """
    assert await _get_batch_aggregator_status(None) is None


async def test_the_analyzer_finds_the_batch_detections_it_was_handed(
    real_redis: RedisClient,
    opened_batches: list[tuple[str, str]],
    integration_db: str,
) -> None:
    """The third broken reader: ``vlm_analyzer.py:493`` does the same GET-on-a-LIST.

    ``analyze_batch`` falls back to Redis for the batch's detection ids when the
    queue payload did not carry them (:492-494), reading the LIST key through the
    ``get`` wrapper and then ``json.loads``-ing it. Against real Redis the GET
    raises WRONGTYPE and the call dies with a redis ResponseError instead of its
    own documented ValueError — the caller's ``except ValueError`` retry logic
    would treat it as success-shaped noise. Un-cured, this goes red on the
    ResponseError; cured, the read succeeds and the (empty-in-this-db) id list
    reaches the analyzer's own documented refusal.

    integration_db is here because the leg's next step queries Detection; the
    assertion is about the Redis read, which happens BEFORE that query.
    """
    from backend.services.vlm_analyzer import VlmAnalyzer

    camera_id, batch_id = await _open_live_batch(real_redis, opened_batches, n_detections=2)
    analyzer = VlmAnalyzer(redis_client=real_redis)

    # The read SUCCEEDED only if the LRANGE returned the seeded ids, which then
    # miss the (empty) Detection table and hit the no-DB-rows refusal at
    # vlm_analyzer.py:515. The empty-list refusal (:496) is deliberately NOT
    # accepted: it also fires when the read returns [] for the WRONG reason (a
    # mis-keyed LRANGE), so accepting it let a wrong-key mutant survive. A redis
    # ResponseError propagates past pytest.raises and reddens the un-cured state.
    with pytest.raises(ValueError, match="No detections found"):
        await analyzer.analyze_batch(batch_id=batch_id, camera_id=camera_id)
