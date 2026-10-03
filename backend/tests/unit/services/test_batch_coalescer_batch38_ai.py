# TARGET-MODULE: backend.services.batch_coalescer
"""Battery AI - campaign #33 backend/services/batch_coalescer.py (218 survivors).

The shipped suite drives redis/settings/metrics with MagicMocks and only
asserts identity or hasattr, and a MagicMock ABSORBS mutants (a dropped
key or renamed kwarg rides whatever the mock accepts). This battery
replaces every seam with a RECORDING fake:

  * FakeRedis records set/zadd/expire/delete/get/zrangebyscore as
    (args, kwargs) WHOLE - M30 capture #7: a DELETED kwarg is a MISSING
    key, invisible to .get-equality; a dropped positional shifts the
    tuple; None-substitutions pin by value. Key strings pinned exactly
    ("coalesce:candidate:{id}" vs "coalesce:candidates:{camera}").
  * get_settings is swapped: one settings object CARRIES the three
    coalesce_* attrs (7 / 3.5 / 0.25) - the getattr-name mutants
    (XX..XX / UPPER / getattr(None,...)) then read the WRONG default and
    bite; a bare object() settings pins the literal defaults
    10 / 5.0 / 0.15 (m15/m20/m33 None-defaults, m26/m39 numeric flips).
    The real Settings carries batch_coalescing_*, NEVER coalesce_* -
    without this swap the default-swap family is unkillable.
  * The Prometheus seams (record_batch_coalesce_candidates,
    record_batch_coalesced, record_batch_coalesce_detections_merged,
    set_batch_coalesce_merge_rate) are swapped to call recorders - the
    counter ARITHMETIC (+1 vs =1 vs -1 vs +2, += vs = vs -=) and the
    >0 / >=0 / >1 GUARD polarities die on the recorded call list. The
    always-true-guard twins (m82 >=0, m83 >1 on total_batches_processed)
    are killed by SEEDING _metrics.total_batches_processed to -2 so the
    post-increment value lands exactly on 0 / 1.
  * Log records captured through a real Handler on a swapped logger:
    whole-message equality plus the FULL flattened extra dict (every
    extra key name and value, so a rename or drop is a dict mismatch).
  * Boundary pins: combined_size == max_batch_size EXACTLY (2+3 on max
    5) is compatible (m7 >= would say no); confidence diff == tolerance
    EXACTLY (0.5 vs 0.75 on tol 0.25, binary-exact) is compatible
    (m13 not >= would say no).
  * merged_batch_id pinned as f"merged-{hex8}": prefix, length 15, and
    hex-only (m52 hex[:9] grows the length, m51/m61 None bite).
  * calculate_priority matrix: person@night P0 (kills the 'PERSON' /
    'NIGHT' / XX-literal flips), CAR@night P1 (kills the `not in
    person` flip - mutant says P0), known-face-before-weapons order.

Honesty ledger (registered EQUIVALENTS - value-identical by construction,
each re-proven by the disposition sweep):
  1. find_compatible_candidates m22 (raw_batch_id.decode('utf-8') ->
     decode('UTF-8')): Python's codec registry normalizes encoding names
     (case and -/_ are collapsed), so 'UTF-8' resolves to the SAME codec
     and bytes.decode('UTF-8') == bytes.decode('utf-8') for every input.
     The mutation is value-identical for all inputs - no battery can
     distinguish it, and this sweep proves it GREEN.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import datetime
from unittest.mock import patch

# ------------------------------------------------------------------ fakes


def run(coro):
    return asyncio.run(coro)


class Boom(Exception):
    pass


class HasAttrs:
    """Settings that actually CARRY the three coalesce_* attrs."""

    coalesce_max_batch_size = 7
    coalesce_window_seconds = 3.5
    coalesce_confidence_tolerance = 0.25


class Bare:
    """Settings WITHOUT any coalesce_* attr - getattr rides the literal."""


class FakeRedis:
    """Records every call as (args, kwargs) whole; get() serves self.store."""

    def __init__(self, store=None, zset=None):
        self.calls: list[tuple] = []
        self.store = dict(store or {})
        self.zset = zset if zset is not None else []

    async def set(self, *a, **k):
        self.calls.append(("set", a, k))

    async def zadd(self, *a, **k):
        self.calls.append(("zadd", a, k))

    async def expire(self, *a, **k):
        self.calls.append(("expire", a, k))

    async def delete(self, *a, **k):
        self.calls.append(("delete", a, k))

    async def get(self, *a, **k):
        self.calls.append(("get", a, k))
        key = a[0] if a and a[0] in self.store else None
        return self.store.get(key) if key is not None else None

    async def zrem(self, *a, **k):
        self.calls.append(("zrem", a, k))

    async def zrangebyscore(self, *a, **k):
        self.calls.append(("zrangebyscore", a, k))
        return list(self.zset)

    def names(self):
        return [c[0] for c in self.calls]


class Rec(list):
    """Call recorder: appends (args, kwargs) whole."""

    def __call__(self, *a, **k):
        self.append((a, k))


class Raiser:
    def __init__(self, exc):
        self.exc = exc

    def __call__(self, *a, **k):
        raise self.exc


_STD = set(vars(logging.LogRecord("n", 0, "p", 0, "m", (), None)).keys()) | {
    "message",
    "asctime",
    "taskName",
}


class LogRec:
    def __init__(self, levelno, msg, extra):
        self.levelno = levelno
        self.msg = msg
        self.extra = extra


@contextlib.contextmanager
def caplogger():
    """Swap a fresh real logger into the module; yield captured REAL
    LogRecords (rendered message + the FULL flattened extra dict, so a
    renamed or dropped extra key is a dict mismatch)."""
    import backend.services.batch_coalescer as m

    recs: list[LogRec] = []

    class H(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            extra = {k: v for k, v in record.__dict__.items() if k not in _STD}
            recs.append(LogRec(record.levelno, record.getMessage(), extra))

    lg = logging.getLogger("battery_ai_probe")
    lg.handlers.clear()
    lg.addHandler(H())
    lg.setLevel(logging.DEBUG)
    lg.propagate = False
    old = m.logger
    m.logger = lg
    try:
        yield recs
    finally:
        m.logger = old
        lg.handlers.clear()


def mk(
    batch_id="b-1", camera="cam-1", ids=(1,), types=("person",), conf=0.5, ts=None, priority=None
):
    from backend.services.batch_coalescer import CoalesceCandidate

    return CoalesceCandidate(
        batch_id=batch_id,
        camera_id=camera,
        detection_ids=list(ids),
        object_types=list(types),
        avg_confidence=conf,
        created_at=ts or datetime(2025, 1, 1, 12, 0, 0),
        priority=priority,
    )


def world(**kw):
    """Construct a BatchCoalescer with get_settings swapped."""
    import backend.services.batch_coalescer as m

    settings = kw.pop("settings", Bare())
    with patch.object(m, "get_settings", lambda: settings):
        return m.BatchCoalescer(**kw)


# ----------------------------------------------------------------- init


def test_init_settings_attrs():
    # the settings object CARRIES coalesce_* -> the getattr NAME mutants
    # (XX/UPPER/getattr(None,...)) read the wrong default and die here.
    c = world(redis_client=FakeRedis(), settings=HasAttrs())
    assert c.max_batch_size == 7
    assert c.coalesce_window_seconds == 3.5
    assert c.confidence_tolerance == 0.25


def test_init_literal_defaults():
    # bare settings (no coalesce_* attrs, like the REAL Settings) -> the
    # literal defaults 10 / 5.0 / 0.15 are pinned (None/6.0/1.15/11 die).
    c = world(redis_client=FakeRedis())
    assert c.max_batch_size == 10
    assert c.coalesce_window_seconds == 5.0
    assert c.confidence_tolerance == 0.15


def test_init_explicit_args_win():
    # explicit args beat getattr; the is-not-None POLARITY flips (is None,
    # and False, or True) hand the getattr branch instead and die here.
    c = world(
        redis_client=FakeRedis(),
        max_batch_size=4,
        coalesce_window_seconds=2.0,
        confidence_tolerance=0.5,
    )
    assert c.max_batch_size == 4
    assert c.coalesce_window_seconds == 2.0
    assert c.confidence_tolerance == 0.5


def test_init_no_args_or_true_bites():
    # m5/m17/m29 `or True` with an ABSENT arg: the ternary takes the arg
    # arm unconditionally and stores None instead of the default.
    c = world(redis_client=FakeRedis())
    assert c.max_batch_size == 10
    assert c.coalesce_window_seconds == 5.0
    assert c.confidence_tolerance == 0.15


def test_init_state_flags():
    r = FakeRedis()
    c = world(redis_client=r)
    assert c._redis is r
    assert c._redis_init_attempted is True  # m41 None, m42 inverted
    c2 = world()
    assert c2._redis is None
    assert c2._redis_init_attempted is False
    assert c2.get_metrics() == {
        "merges_attempted": 0,
        "merges_successful": 0,
        "total_batches_processed": 0,
        "total_batches_merged": 0,
        "total_inference_reduction": 0.0,
        "avg_inference_reduction_pct": 0.0,
    }


def test_init_debug_log():
    with caplogger() as recs:
        world(
            redis_client=FakeRedis(),
            max_batch_size=4,
            coalesce_window_seconds=2.0,
            confidence_tolerance=0.5,
        )
    assert len(recs) == 1
    assert recs[0].levelno == logging.DEBUG
    assert recs[0].msg == "BatchCoalescer initialized"
    assert recs[0].extra == {
        "max_batch_size": 4,
        "coalesce_window_seconds": 2.0,
        "confidence_tolerance": 0.5,
    }


# ------------------------------------------------------------- _get_redis


def test_get_redis_lazy_acquires_once():
    import backend.services.batch_coalescer as m

    c = world()
    assert c._redis_init_attempted is False  # m3: and-True guard skips it
    sentinel = object()
    calls = Rec()

    def acquire():
        calls.append(True)
        return sentinel

    with patch.object(m, "get_redis_client_sync", acquire):
        assert c._get_redis() is sentinel
        assert c._get_redis() is sentinel  # attempted now -> no 2nd acquire
    assert len(calls) == 1
    assert c._redis is sentinel
    assert c._redis_init_attempted is True


def test_get_redis_attempted_not_retried():
    import backend.services.batch_coalescer as m

    client = FakeRedis()
    c = world(redis_client=client)
    c._redis_init_attempted = False  # m1/m2 would lazy-acquire anyway
    calls = Rec()
    with patch.object(m, "get_redis_client_sync", lambda: calls.append(True)):
        assert c._get_redis() is client
    assert len(calls) == 0


def test_get_redis_failure_warns():
    import backend.services.batch_coalescer as m

    c = world()
    with caplogger() as recs, patch.object(m, "get_redis_client_sync", Raiser(Boom("nope"))):
        assert c._get_redis() is None
    assert recs[0].levelno == logging.WARNING
    assert recs[0].msg == "Failed to get Redis client: nope"


# ---------------------------------------------------------- is_compatible


def test_is_compatible_boundaries_and_negatives():
    c = world(max_batch_size=5, confidence_tolerance=0.25)
    a = mk(ids=(1, 2), conf=0.5)
    # combined == max EXACTLY (2+3 on 5): compatible; m7 >= says no.
    assert c.is_compatible(a, mk(ids=(3, 4, 5), conf=0.5)) is True
    # diff == tolerance EXACTLY (0.5 vs 0.75, tol 0.25): compatible;
    # m13 not >= says no.
    assert c.is_compatible(a, mk(ids=(1,), conf=0.75)) is True
    # over the line both ways:
    assert c.is_compatible(a, mk(ids=(1, 2, 3), conf=0.875)) is False  # 6 > 5
    assert c.is_compatible(mk(camera="cam-2"), a) is False
    assert c.is_compatible(mk(types=("car",)), a) is False
    # primary type is the MODE, not the first element:
    assert c.is_compatible(mk(types=("cat", "dog", "dog")), mk(types=("dog",))) is True


# -------------------------------------------------------- calculate_priority


def test_calculate_priority_matrix():
    import backend.services.batch_coalescer as m

    p = m.Priority
    c = world()
    assert c.calculate_priority(["gun"], 0.9) == p.P0_CRITICAL
    assert c.calculate_priority(["Gun"], 0.9) == p.P0_CRITICAL  # lower()
    assert c.calculate_priority(["smoke"], 0.9) == p.P0_CRITICAL
    assert c.calculate_priority(["person"], 0.9, "night") == p.P0_CRITICAL
    assert c.calculate_priority(["person"], 0.9, "day") == p.P2_NORMAL
    # car AT NIGHT stays P1 - the `person NOT in` flip answers P0 here:
    assert c.calculate_priority(["Car"], 0.9, "night") == p.P1_HIGH
    assert c.calculate_priority(["car"], 0.9, "day") == p.P1_HIGH
    assert c.calculate_priority(["cat"], 0.9) == p.P2_NORMAL
    # known face short-circuits BEFORE weapons:
    assert c.calculate_priority(["gun"], 0.9, "night", True) == p.P3_LOW


# ------------------------------------------------------ to_json / from_json


def test_to_json_full_shape():
    cand = mk(batch_id="j-1", camera="jc", ids=(4, 5), types=("person",), conf=0.75, priority=None)
    got = json.loads(cand.to_json())
    assert got == {
        "batch_id": "j-1",
        "camera_id": "jc",
        "detection_ids": [4, 5],
        "object_types": ["person"],
        "avg_confidence": 0.75,
        "created_at": cand.created_at.isoformat(),
        "priority": None,
    }
    import backend.services.batch_coalescer as m

    cand2 = mk(priority=m.Priority.P0_CRITICAL)
    assert json.loads(cand2.to_json())["priority"] == 4  # m16 drops to None


def test_from_json_full_shape():
    import backend.services.batch_coalescer as m
    from backend.services.batch_coalescer import CoalesceCandidate

    ts = datetime(2025, 6, 2, 8, 30, 0)
    payload = {
        "batch_id": "f-1",
        "camera_id": "fc",
        "detection_ids": [7, 8, 9],
        "object_types": ["car", "car"],
        "avg_confidence": 0.625,
        "created_at": ts.isoformat(),
        "priority": 3,
    }
    got = CoalesceCandidate.from_json(json.dumps(payload))
    assert got.batch_id == "f-1"
    assert got.camera_id == "fc"
    assert got.detection_ids == [7, 8, 9]
    assert got.object_types == ["car", "car"]
    assert got.avg_confidence == 0.625
    assert got.created_at == ts
    assert got.priority is m.Priority.P1_HIGH  # m9/m16/m30/m35/m36/m37 drop it
    # bytes ride the decode branch:
    got_b = CoalesceCandidate.from_json(json.dumps(payload).encode("utf-8"))
    assert got_b.batch_id == "f-1"
    # ABSENT priority key -> None (get-falsy), not a KeyError:
    del payload["priority"]
    got2 = CoalesceCandidate.from_json(json.dumps(payload))
    assert got2.priority is None
    # priority present but falsy -> None
    payload["priority"] = None
    got3 = CoalesceCandidate.from_json(json.dumps(payload))
    assert got3.priority is None


# -------------------------------------------------------- register_candidate


def test_register_candidate_full_calls():
    import backend.services.batch_coalescer as m

    cand = mk(
        batch_id="r-7",
        camera="cam-9",
        ids=(11, 12, 13),
        types=("person", "person"),
        conf=0.75,
        priority=m.Priority.P0_CRITICAL,
    )
    r = FakeRedis()
    c = world(redis_client=r)
    with caplogger() as recs:
        run(c.register_candidate(cand))
    assert r.names() == ["set", "zadd", "expire"]
    assert r.calls[0] == (
        "set",
        ("coalesce:candidate:r-7", cand.to_json()),
        {"expire": 600},
    )
    assert r.calls[1] == (
        "zadd",
        ("coalesce:candidates:cam-9", {"r-7": cand.created_at.timestamp()}),
        {},
    )
    assert r.calls[2] == (
        "expire",
        ("coalesce:candidates:cam-9", 600),
        {},
    )
    assert len(recs) == 1
    assert recs[0].levelno == logging.DEBUG
    assert recs[0].msg == "Registered coalesce candidate"
    assert recs[0].extra == {
        "batch_id": "r-7",
        "camera_id": "cam-9",
        "detection_count": 3,
    }


def test_register_candidate_no_redis_warns():
    c = world()  # redis None, init already flagged False -> lazy path!
    c._redis_init_attempted = True  # pin the no-redis BRANCH, not lazy
    with caplogger() as recs:
        run(c.register_candidate(mk()))
    assert recs[0].levelno == logging.WARNING
    assert recs[0].msg == "No Redis client, skipping candidate registration"


# ------------------------------------------------- find_compatible_candidates


def _find_world(zset, store):
    import backend.services.batch_coalescer as m

    r = FakeRedis(store=store, zset=zset)
    c = world(
        redis_client=r, coalesce_window_seconds=2.0, confidence_tolerance=0.25, max_batch_size=5
    )
    return r, c, m


def test_find_compatible_full():
    ts = datetime(2025, 1, 1, 12, 0, 0)
    me = mk(batch_id="b-7", camera="cam-9", ids=(1,), types=("person",), conf=0.75, ts=ts)
    ok1 = mk(batch_id="ok-1", camera="cam-9", ids=(1,), types=("person",), conf=0.5, ts=ts)
    bad1 = mk(batch_id="bad-1", camera="cam-9", ids=(1,), types=("car",), conf=0.5, ts=ts)
    ok2 = mk(batch_id="ok-2", camera="cam-9", ids=(1,), types=("person",), conf=0.625, ts=ts)
    store = {
        "coalesce:candidate:b-7": me.to_json(),
        "coalesce:candidate:ok-1": ok1.to_json(),
        "coalesce:candidate:bad-1": bad1.to_json(),
        "coalesce:candidate:ok-2": ok2.to_json(),
        # "gone-1" deliberately NOT stored -> data None skip
    }
    zset = ["b-7", "ok-1", "bad-1", b"ok-2", "gone-1"]
    r, c, m = _find_world(zset, store)
    metrics = Rec()
    with patch.object(m, "record_batch_coalesce_candidates", metrics):
        got = run(c.find_compatible_candidates(me))
    # window arithmetic + key pinned whole on the zrangebyscore call:
    t = ts.timestamp()
    zq = [q for q in r.calls if q[0] == "zrangebyscore"]
    assert zq == [
        (
            "zrangebyscore",
            ("coalesce:candidates:cam-9",),
            {"min_score": t - 2.0, "max_score": t + 2.0},
        )
    ]
    # bytes decoded by value; self skipped BEFORE its get; gone-1 (data
    # None) skipped:
    assert sorted(cd.batch_id for cd in got) == ["ok-1", "ok-2"]
    assert sorted(q[1][0] for q in r.calls if q[0] == "get") == [
        "coalesce:candidate:bad-1",
        "coalesce:candidate:gone-1",
        "coalesce:candidate:ok-1",
        "coalesce:candidate:ok-2",
    ]
    # evaluated: ok-1, bad-1, ok-2 (self skipped BEFORE counting, gone-1
    # skipped at data-None BEFORE counting); the recorder is POSITIONAL:
    assert metrics == [((3,), {})]


def test_find_compatible_zero_evaluated():
    # only SELF in the zset -> candidates_evaluated stays 0 -> NO metrics
    # call (m18 initial-1 and m45 >=0 both call anyway).
    ts = datetime(2025, 1, 1, 12, 0, 0)
    me = mk(batch_id="b-7", ts=ts)
    store = {"coalesce:candidate:b-7": me.to_json()}
    _r, c, m = _find_world(["b-7"], store)
    metrics = Rec()
    with patch.object(m, "record_batch_coalesce_candidates", metrics):
        got = run(c.find_compatible_candidates(me))
    assert got == []
    assert metrics == []


def test_find_compatible_single_evaluated():
    # exactly ONE evaluated -> metrics called with 1 (m29 -1 skips the
    # call, m30 +=2 says 2, m46 >1 skips the call).
    ts = datetime(2025, 1, 1, 12, 0, 0)
    me = mk(batch_id="b-7", ts=ts)
    ok1 = mk(batch_id="ok-1", ts=ts)
    store = {
        "coalesce:candidate:b-7": me.to_json(),
        "coalesce:candidate:ok-1": ok1.to_json(),
    }
    _r, c, m = _find_world(["b-7", "ok-1"], store)
    metrics = Rec()
    with patch.object(m, "record_batch_coalesce_candidates", metrics):
        got = run(c.find_compatible_candidates(me))
    assert [cd.batch_id for cd in got] == ["ok-1"]
    assert metrics == [((1,), {})]


def test_find_compatible_two_evaluated_count():
    # m28 `candidates_evaluated = 1` (not += 1): with TWO evaluated the
    # counter lands on 1, not 2.
    ts = datetime(2025, 1, 1, 12, 0, 0)
    me = mk(batch_id="b-7", ts=ts)
    ok1 = mk(batch_id="ok-1", ts=ts)
    bad1 = mk(batch_id="bad-1", types=("car",), ts=ts)
    store = {
        "coalesce:candidate:b-7": me.to_json(),
        "coalesce:candidate:ok-1": ok1.to_json(),
        "coalesce:candidate:bad-1": bad1.to_json(),
    }
    _r, c, m = _find_world(["b-7", "ok-1", "bad-1"], store)
    metrics = Rec()
    with patch.object(m, "record_batch_coalesce_candidates", metrics):
        run(c.find_compatible_candidates(me))
    assert metrics == [((2,), {})]


def test_find_parse_failure_warns():
    ts = datetime(2025, 1, 1, 12, 0, 0)
    me = mk(batch_id="b-7", ts=ts)
    store = {
        "coalesce:candidate:b-7": me.to_json(),
        "coalesce:candidate:boom-1": "{not json",
    }
    r, c, _m = _find_world(["b-7", "boom-1"], store)
    try:
        json.loads("{not json")
    except json.JSONDecodeError as exc:
        real_err = str(exc)
    with caplogger() as recs:
        got = run(c.find_compatible_candidates(me))
    assert got == []
    assert recs[0].levelno == logging.WARNING
    assert recs[0].msg == "Failed to parse candidate data"
    assert recs[0].extra == {"batch_id": "boom-1", "error": real_err}
    assert recs[0].extra["error"] != "None"


# --------------------------------------------------------- remove_candidates


def test_remove_candidates_with_camera():
    r = FakeRedis()
    c = world(redis_client=r)
    with caplogger() as recs:
        run(c.remove_candidates(["r1", "r2"], camera_id="camX"))
    assert r.names() == ["delete", "delete", "zrem"]
    assert r.calls[0] == ("delete", ("coalesce:candidate:r1",), {})
    assert r.calls[1] == ("delete", ("coalesce:candidate:r2",), {})
    assert r.calls[2] == ("zrem", ("coalesce:candidates:camX", "r1", "r2"), {})
    assert recs[0].levelno == logging.DEBUG
    assert recs[0].msg == "Removed coalesce candidates"
    assert recs[0].extra == {"batch_count": 2, "camera_count": 1}


def test_remove_candidates_reads_camera_from_redis():
    a = mk(batch_id="r1", camera="cam-a")
    b = mk(batch_id="r2", camera="cam-b")
    store = {
        "coalesce:candidate:r1": a.to_json(),
        "coalesce:candidate:r2": b.to_json(),
    }
    r = FakeRedis(store=store)
    c = world(redis_client=r)
    with caplogger() as recs:
        run(c.remove_candidates(["r1", "r2"]))
    # each id: get FIRST (camera lookup), then delete; then two zrem groups
    assert r.names() == ["get", "delete", "get", "delete", "zrem", "zrem"]
    assert r.calls[0] == ("get", ("coalesce:candidate:r1",), {})
    assert r.calls[2] == ("get", ("coalesce:candidate:r2",), {})
    zrem = {q[1][0]: q[1][1:] for q in r.calls if q[0] == "zrem"}
    assert zrem == {
        "coalesce:candidates:cam-a": ("r1",),
        "coalesce:candidates:cam-b": ("r2",),
    }
    assert recs[0].extra == {"batch_count": 2, "camera_count": 2}


# ------------------------------------------------------------ merge_batches


def test_merge_empty_exact_fields():
    c = world()
    res = run(c.merge_batches([]))
    assert (
        res.merged_batch_id,
        res.source_batch_ids,
        res.combined_detection_ids,
        res.detection_count_before,
        res.detection_count_after,
        res.merge_count,
    ) == ("", [], [], 0, 0, 0)
    assert c.get_metrics()["merges_attempted"] == 1
    assert c.get_metrics()["merges_successful"] == 0


def test_merge_single_exact_fields():
    c = world()
    s1 = mk(batch_id="s-1", ids=(9, 8))
    res = run(c.merge_batches([s1]))
    assert (
        res.merged_batch_id,
        res.source_batch_ids,
        res.combined_detection_ids,
        res.detection_count_before,
        res.detection_count_after,
        res.merge_count,
    ) == ("s-1", ["s-1"], [9, 8], 1, 1, 1)
    assert res.combined_detection_ids is not s1.detection_ids  # .copy()
    assert c.get_metrics()["merges_successful"] == 0


def _merge_world():
    import backend.services.batch_coalescer as m

    c = world()
    coalesced = Rec()
    detections = Rec()
    gauge = Rec()
    return c, m, coalesced, detections, gauge


def test_merge_main_path_full_observability():
    t0 = datetime(2025, 1, 1, 12, 0, 0)
    t1 = datetime(2025, 1, 1, 12, 0, 5)
    e0 = mk(batch_id="e-0", ids=(7, 8), ts=t1)  # LATER time
    e1 = mk(batch_id="e-1", ids=(1, 2, 3), ts=t0)  # EARLIER, first input
    c, m, coalesced, detections, gauge = _merge_world()
    with (
        caplogger() as recs,
        patch.object(m, "record_batch_coalesced", coalesced),
        patch.object(m, "record_batch_coalesce_detections_merged", detections),
        patch.object(m, "set_batch_coalesce_merge_rate", gauge),
    ):
        res = run(c.merge_batches([e0, e1]))
    assert res.source_batch_ids == ["e-1", "e-0"]  # temporal order
    assert res.combined_detection_ids == [1, 2, 3, 7, 8]
    assert res.detection_count_before == 2 and res.detection_count_after == 1
    assert res.merge_count == 2
    mid = res.merged_batch_id
    assert mid.startswith("merged-") and len(mid) == 15  # m52 hex[:9] -> 16
    int(mid[len("merged-") :], 16)  # hex-only
    assert coalesced == [((2,), {})]
    assert detections == [((2,), {})]  # additional = 5 - 3 (m78 + -> 8)
    assert gauge == [((100.0,), {})]  # merged/processed * 100 (m85/m86/m87)
    assert recs[0].levelno == logging.INFO
    assert recs[0].msg == "Merged batches"
    assert recs[0].extra == {
        "merged_batch_id": mid,
        "source_count": 2,
        "detection_count": 5,
        "additional_detections_merged": 2,
        "inference_reduction_pct": 50.0,
    }
    # ONE successful merge: avg must ride the division (m13/m15-m17 die)
    assert c.get_metrics() == {
        "merges_attempted": 1,
        "merges_successful": 1,
        "total_batches_processed": 2,
        "total_batches_merged": 2,
        "total_inference_reduction": 50.0,
        "avg_inference_reduction_pct": 50.0,
    }


def test_merge_additional_one_and_zero():
    t0 = datetime(2025, 1, 1, 12, 0, 0)
    # additional == 1 -> record(1) (m80 >1 SKIPS the call)
    c1, m, _c, detections, _g = _merge_world()
    with patch.object(m, "record_batch_coalesce_detections_merged", detections):
        run(c1.merge_batches([mk(ids=(1,), ts=t0), mk(ids=(2,), ts=t0)]))
    assert detections == [((1,), {})]
    # additional == 0 (second batch carries NO ids) -> NO call
    # (m79 >=0 calls with 0)
    c2, m, coalesced, detections2, _g = _merge_world()
    with (
        patch.object(m, "record_batch_coalesced", coalesced),
        patch.object(m, "record_batch_coalesce_detections_merged", detections2),
    ):
        run(c2.merge_batches([mk(ids=(1, 2), ts=t0), mk(ids=(), ts=t0)]))
    assert detections2 == []
    assert coalesced == [((2,), {})]


def test_merge_counter_arithmetic_sequence():
    # full sequence over a FRESH coalescer: attempted 4, successful 2,
    # processed/merged 5, reduction 50 + 66 2/3 - kills =1 (reset), -1
    # (sign), +2 (step), = (overwrite) on EVERY counter.
    t0 = datetime(2025, 1, 1, 12, 0, 0)
    c, m, _c, _d, _g = _merge_world()
    with caplogger():
        run(c.merge_batches([]))
        run(c.merge_batches([mk(ts=t0)]))
        run(c.merge_batches([mk(ids=(1,), ts=t0), mk(ids=(2,), ts=t0)]))
        run(c.merge_batches([mk(ids=(1, 2), ts=t0), mk(ids=(3, 4), ts=t0), mk(ids=(5,), ts=t0)]))
    exp_total = (2 - 1) / 2 * 100.0 + (3 - 1) / 3 * 100.0
    assert c.get_metrics() == {
        "merges_attempted": 4,
        "merges_successful": 2,
        "total_batches_processed": 5,
        "total_batches_merged": 5,
        "total_inference_reduction": exp_total,
        "avg_inference_reduction_pct": exp_total / 2,
    }


def test_merge_gauge_guard_zero_boundary():
    # seed processed=-2 so the post-increment value lands on EXACTLY 0:
    # pristine guard >0 skips the gauge; m82 >=0 calls it.
    t0 = datetime(2025, 1, 1, 12, 0, 0)
    c, m, _c, _d, gauge = _merge_world()
    c._metrics.total_batches_processed = -2
    with patch.object(m, "set_batch_coalesce_merge_rate", gauge):
        run(c.merge_batches([mk(ts=t0), mk(ids=(2,), ts=t0)]))
    assert gauge == []


def test_merge_gauge_guard_one_boundary():
    # seed -2, merge THREE -> processed EXACTLY 1: pristine calls the
    # gauge; m83 >1 skips it.
    t0 = datetime(2025, 1, 1, 12, 0, 0)
    c, m, _c, _d, gauge = _merge_world()
    c._metrics.total_batches_processed = -2
    with patch.object(m, "set_batch_coalesce_merge_rate", gauge):
        run(c.merge_batches([mk(ts=t0), mk(ids=(2,), ts=t0), mk(ids=(3,), ts=t0)]))
    # merged = 0 + 3 = 3, processed = 1 -> rate 300.0
    assert gauge == [((300.0,), {})]
