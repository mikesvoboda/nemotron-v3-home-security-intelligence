"""Unit tests for job_status (campaign #38, battery AN).

Complements the shipped test_job_status.py. Every test pins an OBSERVABLE the
shipped suite leaves free, so each mutation family in the 207-killable pool
dies on an equality assertion at the exact site the mutation edits. Per-key
disposition (2026-10-04, from c38-mutant-full.tsv, the FULL untruncated
inventory — the classifier's 150-char truncation HID four extra-drops and a
default-swap, re-extracted in-process before authoring): 207 DISTINGUISHED /
4 EQUIV ledger:
  * xǁJobStatusServiceǁ_add_to_active_registry__mutmut_5 and
    xǁJobStatusServiceǁ_add_to_completed_registry__mutmut_5 — ``datetime
    .now(UTC).timestamp()`` -> ``now(None).timestamp()`` is UNKILLABLE BY
    VALUE: a naive local wall-clock reinterpreted through ``.timestamp()``
    re-derives the SAME epoch under any host TZ (measured in this sandbox:
    EDT delta 3.1e-06 s); the zadd score is the only observable.
  * get_active_job_ids__mutmut_14 / get_completed_job_ids__mutmut_14 —
    ``job_ids[:limit] if job_ids else []`` -> ``if (job_ids) or True`` is a
    branch-degrade to the same slice/[] in both polarities.

The mutation inventory this file was written against:
  * log-extra key renames (``XXnameXX`` / ``NAME`` twins), whole-``extra``
    drops and message drops at 9 logger sites -> extras asserted as an exact
    KEY SET (module payload + the ambient keys the app ContextFilter injects
    into every record — measured at import) with every value pinned, and the
    message asserted by EQUALITY (fragment/`in` asserts pass XX/case twins);
  * boundary ``if removed > 0`` -> ``>= 0`` / ``> 1`` -> the removed==0 case
    asserts SILENCE and removed==1 asserts the record exists;
  * ``datetime.now(UTC)`` -> ``now(None)`` in the STATUS writers -> tz-
    awareness of the stored ISO string (``iso_aware``; value-based pins fail
    here, so the registry-score mutants above stay EQUIV);
  * ctor/kwarg None-twins and DROPPED call args (``zadd(key, )`` and friends
    — re-read as FULL diffs, several are legal-call drops invisible on
    instances) -> call-literal spies on the fake redis: every call recorded
    as (op, args..., kwargs...) and asserted by equality;
  * ``limit: int = 100`` -> ``101`` -> exercised at exactly 101 rows so
    ``[:100]`` vs ``[:101]`` diverges (an assertion at N=3 would pass both);
  * ``continue`` -> ``break`` in the list_jobs filter -> a row order where
    the first job is filter-excluded (break yields [], continue yields the
    matches);
  * zadd-score consistency: the list score must EQUAL ``created_at
    .timestamp()`` read BACK from the stored row (kills start_job's
    score-dict drops/None-twins without any wall-clock race).

All tests are module-level and sync (the disposition sweep calls them without
pytest); async paths run through asyncio.run. No fixture parameters anywhere
(b30-harness rule).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import pytest

import backend.services.job_status as js
from backend.services.job_status import (
    JobMetadata,
    JobState,
    JobStatusService,
    get_job_status_service,
    reset_job_status_service,
)

pytestmark = pytest.mark.unit


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Fake over the exact production surface job_status touches
# ---------------------------------------------------------------------------

JID = "J1"
KEY = "job:J1:status"
LIST_KEY = "job:status:list"
ACTIVE_KEY = "jobs:active"
DONE_KEY = "jobs:completed"
TTL = 3600


class Redis:
    """Call-recording fake. ``get`` reads the value store; zset ops read a
    parallel dict keyed by set name. Ops return POPPED values so one fake can
    serve several calls with different verdicts (cleanup tests)."""

    def __init__(self, store=None, zsets=None, zrem_score=None, zrem_rank=None, zrem_pop=None):
        self.store = dict(store or {})
        self.zsets = dict(zsets or {})
        self.calls = []  # (op, args..., ) tuples incl. kwargs as ('kw',...) tail
        self._zrem_score = _Seq(zrem_score, 0)
        self._zrem_rank = _Seq(zrem_rank, 0)
        self._zrem_pop = _Seq(zrem_pop, 0)

    async def get(self, key):
        self.calls.append(("get", key))
        return self.store.get(key)

    async def set(self, key, value, expire=None):
        self.calls.append(("set", key, value, expire))
        self.store[key] = value
        return True

    async def zadd(self, key, mapping):
        self.calls.append(("zadd", key, mapping))
        return 1

    async def zrangebyscore(self, key, min_score, max_score):
        self.calls.append(("zrangebyscore", key, min_score, max_score))
        return list(self.zsets.get(key, []))

    async def zremrangebyscore(self, key, min_score, max_score):
        self.calls.append(("zremrangebyscore", key, min_score, max_score))
        return self._zrem_score.next()

    async def zremrangebyrank(self, key, start, stop):
        self.calls.append(("zremrangebyrank", key, start, stop))
        return self._zrem_rank.next()

    async def zrem(self, key, *members):
        self.calls.append(("zrem", key, *members))
        return self._zrem_pop.next()


class _Seq:
    """Scalar spec -> that value every call; list spec -> popped in order."""

    def __init__(self, spec, default=0):
        self.vals = list(spec) if isinstance(spec, (list, tuple)) else None
        self.value = default if spec is None else spec

    def next(self):
        if self.vals:
            return self.vals.pop(0)
        return self.value


def svc(redis=None, **kw):
    return JobStatusService(redis or Redis(), **kw)


def row(
    job_id=JID,
    status="pending",
    progress=0,
    message=None,
    created_at=None,
    started_at=None,
    completed_at=None,
    result=None,
    error=None,
    extra=None,
):
    """A stored job dict exactly as to_dict() would write it."""
    return {
        "job_id": job_id,
        "job_type": "export",
        "status": status,
        "progress": progress,
        "message": message,
        "created_at": created_at or "2026-10-04T12:00:00+00:00",
        "started_at": started_at,
        "completed_at": completed_at,
        "result": result,
        "error": error,
        "extra": extra,
    }


def calls(redis, op):
    return [c for c in redis.calls if c[0] == op]


def only(redis, op):
    got = calls(redis, op)
    assert len(got) == 1, f"expected exactly one {op} call, got {got}"
    return got[0]


# ---------------------------------------------------------------------------
# Log capture (same proven machinery as c37: handler swap + ambient-key set)
# ---------------------------------------------------------------------------


class LogCap(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


_STANDARD_LOG_KEYS = set(vars(logging.LogRecord("x", 0, "f", 1, "m", None, None))) | {
    "message",
    "asctime",
    "taskName",
}


def log_extras(record):
    return {k: v for k, v in vars(record).items() if k not in _STANDARD_LOG_KEYS}


class LogSwap:
    """Attach a DEBUG capture handler to job_status.logger."""

    def __init__(self):
        self.cap = LogCap()

    def __enter__(self):
        self._saved = js.logger.level
        js.logger.addHandler(self.cap)
        js.logger.setLevel(logging.DEBUG)
        return self.cap

    def __exit__(self, *_exc):
        js.logger.removeHandler(self.cap)
        js.logger.setLevel(self._saved)
        return False


def _measure_ambient():
    with LogSwap() as cap:
        js.logger.info("c38an-ambient-control")
    assert len(cap.records) == 1, "log capture machinery is broken"
    return frozenset(log_extras(cap.records[0]))


AMBIENT_KEYS = _measure_ambient()
assert len(AMBIENT_KEYS) >= 4, f"ambient capture failed: {sorted(AMBIENT_KEYS)}"


def expect_extra(record, payload):
    """Extras == ambient keys + EXACTLY these payload keys, values as pinned."""
    extras = log_extras(record)
    assert set(extras) == set(AMBIENT_KEYS) | set(payload), (
        f"extra key-set drift: "
        f"+{sorted(set(extras) - set(AMBIENT_KEYS) - set(payload))} "
        f"-{sorted((set(AMBIENT_KEYS) | set(payload)) - set(extras))}"
    )
    for k, v in payload.items():
        assert extras[k] == v, f"extra {k}: {extras[k]!r} != {v!r}"


def iso_aware(iso_str):
    """now(UTC) stores an offset-bearing ISO string; now(None) does not."""
    assert isinstance(iso_str, str), f"timestamp not stored: {iso_str!r}"
    return datetime.fromisoformat(iso_str).tzinfo is not None


def rows(records):
    """(level, message) pairs in EMISSION ORDER."""
    return [(logging.getLevelName(r.levelno), r.getMessage()) for r in records]


def full_meta(job_id=JID, status=JobState.RUNNING, completed=True):
    """A JobMetadata with EVERY field populated (completed=True) — the shape
    to_dict/from_dict pins must round-trip so no None-twin survives equality."""
    created = datetime(2026, 10, 4, 12, 0, 0, tzinfo=UTC)
    started = datetime(2026, 10, 4, 12, 0, 5, tzinfo=UTC)
    done = datetime(2026, 10, 4, 12, 9, 0, tzinfo=UTC) if completed else None
    return JobMetadata(
        job_id=job_id,
        job_type="export",
        status=status,
        progress=66,
        message="halfway",
        created_at=created,
        started_at=started,
        completed_at=done,
        result={"ok": 1},
        error="boom",
        extra={"k": "v"},
    )


# =========================================================================
# JobMetadata.to_dict (7 keys: 22-27 XX/case renames, 20 `and False`)
# =========================================================================


def test_c38an_01_to_dict_full_equality_c38():
    m = full_meta()
    assert m.to_dict() == {
        "job_id": "J1",
        "job_type": "export",
        "status": "running",
        "progress": 66,
        "message": "halfway",
        "created_at": "2026-10-04T12:00:00+00:00",
        "started_at": "2026-10-04T12:00:05+00:00",
        # completed_at SET here: the `and False` degrade (m20) writes None.
        "completed_at": "2026-10-04T12:09:00+00:00",
        "result": {"ok": 1},
        # error SET even when completed: from_dict's error-lookup family
        # (m12 None-const, m51/52/53 key twins) only diverges on a NON-None value.
        "error": "boom",
        "extra": {"k": "v"},
    }


def test_c38an_02_to_dict_none_timestamps_c38():
    m = full_meta(completed=False)
    d = m.to_dict()
    assert d["completed_at"] is None
    assert d["started_at"] == "2026-10-04T12:00:05+00:00"
    assert d["error"] == "boom"
    assert d["status"] == "running"


# =========================================================================
# JobMetadata.from_dict (19 keys) — every field PRESENT kills every
# None/dropped-key/case-twin of the .get(...) lookups.
# =========================================================================


def test_c38an_03_from_dict_all_fields_c38():
    m = JobMetadata.from_dict(full_meta().to_dict())
    assert m.job_id == "J1"
    assert m.job_type == "export"
    assert m.status is JobState.RUNNING
    assert m.progress == 66
    assert m.message == "halfway"
    assert m.created_at == datetime(2026, 10, 4, 12, 0, 0, tzinfo=UTC)
    assert m.started_at == datetime(2026, 10, 4, 12, 0, 5, tzinfo=UTC)
    assert m.completed_at == datetime(2026, 10, 4, 12, 9, 0, tzinfo=UTC)
    assert m.result == {"ok": 1}
    assert m.error == "boom"
    assert m.extra == {"k": "v"}


def test_c38an_04_from_dict_absent_optionals_c38():
    data = {
        "job_id": "J2",
        "job_type": "cleanup",
        "status": "queued",
        "progress": 0,
        "created_at": "2026-10-04T13:00:00+00:00",
    }
    m = JobMetadata.from_dict(data)
    assert m.message is None
    assert m.started_at is None
    assert m.completed_at is None
    assert m.result is None
    assert m.error is None
    assert m.extra is None
    assert m.created_at == datetime(2026, 10, 4, 13, 0, 0, tzinfo=UTC)


# =========================================================================
# get_job_status (14 keys)
# =========================================================================


def test_c38an_05_get_job_status_happy_quiet_c38():
    r = Redis(store={KEY: row(status="running", progress=42, message="half")})
    s = svc(r)
    with LogSwap() as cap:
        m = run(s.get_job_status(JID))
    assert (m.job_id, m.status, m.progress, m.message) == ("J1", JobState.RUNNING, 42, "half")
    assert m.created_at == datetime(2026, 10, 4, 12, 0, 0, tzinfo=UTC)
    # the happy path must read EXACTLY job:J1:status (None/`job:None:` twins miss)
    assert only(r, "get") == ("get", KEY)
    assert rows(cap.records) == []


def test_c38an_06_get_job_status_parse_warning_c38():
    bad = row()
    del bad["job_id"]  # from_dict -> KeyError('job_id')
    r = Redis(store={KEY: bad})
    s = svc(r)
    with LogSwap() as cap:
        assert run(s.get_job_status(JID)) is None
    assert rows(cap.records) == [("WARNING", "Failed to parse job metadata")]
    expect_extra(cap.records[0], {"job_id": "J1", "error": "'job_id'"})


# =========================================================================
# start_job (22 keys)
# =========================================================================


def test_c38an_07_start_job_full_observables_c38():
    r = Redis()
    t0 = datetime.now(UTC)
    with LogSwap() as cap:
        got = run(svc(r).start_job("J1", "export", {"k": "v"}))
    t1 = datetime.now(UTC)
    assert got == "J1"

    op, key, data, expire = only(r, "set")
    assert (op, key, expire) == ("set", KEY, None)
    assert data["job_id"] == "J1"
    assert data["job_type"] == "export"
    assert data["status"] == "pending"
    assert data["progress"] == 0
    assert data["message"] is None
    assert data["started_at"] is None
    assert data["completed_at"] is None
    assert data["result"] is None
    assert data["error"] is None
    assert data["extra"] == {"k": "v"}
    assert iso_aware(data["created_at"]), "start timestamp lost tz-awareness"
    created = datetime.fromisoformat(data["created_at"])
    assert t0 <= created <= t1

    # list membership: exact key + {job_id: created_at.timestamp()} score
    zadds = calls(r, "zadd")
    assert [z[1] for z in zadds] == [LIST_KEY, ACTIVE_KEY]
    assert zadds[0][2] == {JID: created.timestamp()}

    # cleanup call with the DEFAULT max (mutant of the ctor default would move
    # this; the start list keeps it at the module default)
    assert only(r, "zremrangebyrank") == ("zremrangebyrank", LIST_KEY, 0, -10001)

    # active registry: key + single-member mapping (None/dropped twins die on
    # this pin or on the fake's required arg); tz-window bound on the score
    zact = zadds[1]
    assert zact[1] == ACTIVE_KEY
    assert set(zact[2]) == {JID}
    score = datetime.fromtimestamp(zact[2][JID], tz=UTC)
    assert t0 <= score <= t1

    assert rows(cap.records) == [("INFO", "Job created")]
    expect_extra(cap.records[0], {"job_id": "J1", "job_type": "export"})


# =========================================================================
# update_progress (19 keys)
# =========================================================================


def test_c38an_08_update_progress_pending_transition_c38():
    r = Redis(store={KEY: row(status="pending")})
    t0 = datetime.now(UTC)
    with LogSwap() as cap:
        run(svc(r).update_progress(JID, 42, "halfway"))
    t1 = datetime.now(UTC)
    op, key, data, expire = only(r, "set")
    assert (key, expire) == (KEY, None)
    assert data["progress"] == 42
    assert data["message"] == "halfway"
    assert data["status"] == "running"
    assert iso_aware(data["started_at"]), "started_at lost tz-awareness"
    st = datetime.fromisoformat(data["started_at"])
    assert t0 <= st <= t1
    assert rows(cap.records) == [("DEBUG", "Job progress updated")]
    expect_extra(cap.records[0], {"job_id": "J1", "progress": 42})


def test_c38an_09_update_progress_none_message_and_clamp_c38():
    r = Redis(
        store={
            KEY: row(
                status="running", progress=10, message="old", started_at="2026-10-04T12:00:05+00:00"
            )
        }
    )
    with LogSwap() as cap:
        run(svc(r).update_progress(JID, 150, None))
    op, key, data, expire = only(r, "set")
    assert data["progress"] == 100  # clamped
    assert data["message"] == "old"  # None message must NOT overwrite
    assert data["status"] == "running"
    assert data["started_at"] == "2026-10-04T12:00:05+00:00"  # no re-transition
    assert rows(cap.records) == [("DEBUG", "Job progress updated")]

    # clamp floor, same fake fresh
    r2 = Redis(store={KEY: row(status="running", progress=10)})
    with LogSwap():
        run(svc(r2).update_progress(JID, -5, "under"))
    _, _, data2, _ = only(r2, "set")
    assert data2["progress"] == 0
    assert data2["message"] == "under"


def test_c38an_10_update_progress_missing_raises_c38():
    r = Redis()
    with pytest.raises(KeyError), LogSwap() as cap:
        run(svc(r).update_progress(JID, 5, None))
    assert rows(cap.records) == []


# =========================================================================
# complete_job (22 keys) / fail_job (21) / cancel_job (24)
# =========================================================================


def _lifecycle(r, fn):
    t0 = datetime.now(UTC)
    with LogSwap() as cap:
        run(fn(svc(r)))
    t1 = datetime.now(UTC)
    return t0, t1, cap


def test_c38an_11_complete_job_full_c38():
    r = Redis(store={KEY: row(status="running", started_at="2026-10-04T12:00:05+00:00")})
    t0, t1, cap = _lifecycle(r, lambda s: s.complete_job(JID, {"ok": 1}))
    op, key, data, expire = only(r, "set")
    assert (key, expire) == (KEY, TTL)
    assert data["status"] == "completed"
    assert data["progress"] == 100
    assert data["result"] == {"ok": 1}
    assert data["message"] == "Completed successfully"
    assert iso_aware(data["completed_at"])
    done = datetime.fromisoformat(data["completed_at"])
    assert t0 <= done <= t1
    assert only(r, "zrem") == ("zrem", ACTIVE_KEY, JID)
    zc = only(r, "zadd")
    assert zc[1] == DONE_KEY and set(zc[2]) == {JID}
    score = datetime.fromtimestamp(zc[2][JID], tz=UTC)
    assert t0 <= score <= t1
    assert rows(cap.records) == [("INFO", "Job completed")]
    expect_extra(cap.records[0], {"job_id": "J1", "job_type": "export"})


def test_c38an_12_fail_job_full_c38():
    r = Redis(store={KEY: row(status="running")})
    t0, t1, cap = _lifecycle(r, lambda s: s.fail_job(JID, "boom"))
    op, key, data, expire = only(r, "set")
    assert (key, expire) == (KEY, TTL)
    assert data["status"] == "failed"
    assert data["error"] == "boom"
    assert data["message"] == "Failed: boom"
    assert iso_aware(data["completed_at"])
    assert t0 <= datetime.fromisoformat(data["completed_at"]) <= t1
    assert only(r, "zrem") == ("zrem", ACTIVE_KEY, JID)
    zc = only(r, "zadd")
    assert zc[1] == DONE_KEY and set(zc[2]) == {JID}
    assert rows(cap.records) == [("ERROR", "Job failed")]
    expect_extra(cap.records[0], {"job_id": "J1", "job_type": "export", "error": "boom"})


def test_c38an_13_cancel_job_full_c38():
    r = Redis(store={KEY: row(status="running")})
    t0, t1, cap = _lifecycle(r, lambda s: s.cancel_job(JID))
    op, key, data, expire = only(r, "set")
    assert (key, expire) == (KEY, TTL)
    assert data["status"] == "cancelled"
    assert iso_aware(data["completed_at"])
    assert t0 <= datetime.fromisoformat(data["completed_at"]) <= t1
    assert data["error"] == "Cancelled by user"
    assert data["message"] == "Job cancelled by user request"
    # untouched fields survive the rewrite (kills wrong-field writes)
    assert data["progress"] == 0
    assert data["created_at"] == "2026-10-04T12:00:00+00:00"
    assert data["job_id"] == "J1" and data["job_type"] == "export"
    assert only(r, "zrem") == ("zrem", ACTIVE_KEY, JID)
    zc = only(r, "zadd")
    assert zc[1] == DONE_KEY and set(zc[2]) == {JID}
    assert rows(cap.records) == [("INFO", "Job cancelled")]
    expect_extra(cap.records[0], {"job_id": "J1", "job_type": "export"})


def test_c38an_14_cancel_terminal_returns_false_quiet_c38():
    r = Redis(store={KEY: row(status="completed")})
    with LogSwap() as cap:
        assert run(svc(r).cancel_job(JID)) is False
    assert calls(r, "set") == []
    assert calls(r, "zrem") == []
    assert calls(r, "zadd") == []
    assert rows(cap.records) == []


# =========================================================================
# cleanup_completed_jobs (12) / cleanup_stale_active_jobs (12) /
# cleanup_job_status_list (14)
# =========================================================================


def test_c38an_15_cleanup_completed_removes_one_c38():
    r = Redis(zrem_score=1)
    with LogSwap() as cap:
        assert run(svc(r).cleanup_completed_jobs()) == 1
    op, key, lo, hi = only(r, "zremrangebyscore")
    assert (key, lo) == (DONE_KEY, "-inf")
    assert isinstance(hi, float)
    assert rows(cap.records) == [("INFO", "Cleaned up old completed job entries")]
    expect_extra(cap.records[0], {"removed_count": 1, "retention_seconds": 3600})


def test_c38an_16_cleanup_completed_zero_is_quiet_c38():
    r = Redis(zrem_score=0)
    with LogSwap() as cap:
        assert run(svc(r).cleanup_completed_jobs()) == 0
    assert rows(cap.records) == []


def test_c38an_17_cleanup_stale_removes_one_c38():
    r = Redis(zrem_score=1)
    with LogSwap() as cap:
        assert run(svc(r).cleanup_stale_active_jobs()) == 1
    op, key, lo, hi = only(r, "zremrangebyscore")
    assert (key, lo) == (ACTIVE_KEY, "-inf")
    assert rows(cap.records) == [("WARNING", "Removed stale active job entries (likely orphaned)")]
    expect_extra(cap.records[0], {"removed_count": 1, "stale_threshold_seconds": 7200})


def test_c38an_18_cleanup_stale_zero_is_quiet_c38():
    r = Redis(zrem_score=0)
    with LogSwap() as cap:
        assert run(svc(r).cleanup_stale_active_jobs()) == 0
    assert rows(cap.records) == []


def test_c38an_19_cleanup_list_explicit_max_c38():
    # removed pops 2 then 1: the removed==1 row is the discriminator for the
    # `removed > 1` twin (m15 — under it the second call logs NOTHING), and
    # two distinct max_entries pin the -(n+1) rank cutoff as a formula.
    r = Redis(zrem_rank=[2, 1])
    with LogSwap() as cap:
        assert run(svc(r).cleanup_job_status_list(max_entries=5)) == 2
        assert run(svc(r).cleanup_job_status_list(max_entries=1)) == 1
    assert calls(r, "zremrangebyrank") == [
        ("zremrangebyrank", LIST_KEY, 0, -6),
        ("zremrangebyrank", LIST_KEY, 0, -2),
    ]
    assert rows(cap.records) == [
        ("INFO", "Cleaned up old job status list entries"),
        ("INFO", "Cleaned up old job status list entries"),
    ]
    expect_extra(cap.records[0], {"removed_count": 2, "max_entries": 5, "sorted_set": LIST_KEY})
    expect_extra(cap.records[1], {"removed_count": 1, "max_entries": 1, "sorted_set": LIST_KEY})


def test_c38an_20_cleanup_list_default_and_quiet_c38():
    r = Redis(zrem_rank=0)
    with LogSwap() as cap:
        assert run(svc(r).cleanup_job_status_list()) == 0
    assert only(r, "zremrangebyrank") == ("zremrangebyrank", LIST_KEY, 0, -10001)
    assert rows(cap.records) == []


# =========================================================================
# get_active_job_ids / get_completed_job_ids (2 killable default-swap keys;
# the or-True twins are the ledger)
# =========================================================================


def test_c38an_21_id_getters_args_order_and_default_limit_c38():
    ids = [f"j{i}" for i in range(101)]
    r = Redis(zsets={ACTIVE_KEY: ids, DONE_KEY: ids})
    s = svc(r)
    with LogSwap() as cap:
        assert run(s.get_active_job_ids()) == ids[:100]  # 101 rows: 100 vs 101
        assert run(s.get_completed_job_ids()) == ids[:100]
        assert run(s.get_active_job_ids(limit=2)) == ids[:2]
    zrs = calls(r, "zrangebyscore")
    assert zrs[0] == ("zrangebyscore", ACTIVE_KEY, "-inf", "+inf")
    assert zrs[1] == ("zrangebyscore", DONE_KEY, "-inf", "+inf")
    assert rows(cap.records) == []


# =========================================================================
# list_jobs (14 keys)
# =========================================================================


def test_c38an_22_list_jobs_args_and_order_c38():
    r = Redis(
        zsets={LIST_KEY: ["B", "A"]},
        store={
            "job:B:status": row(job_id="B", status="running", progress=3),
            "job:A:status": row(job_id="A", status="completed", progress=9),
        },
    )
    s = svc(r)
    with LogSwap() as cap:
        out = run(s.list_jobs(None, 10))
    assert only(r, "zrangebyscore") == ("zrangebyscore", LIST_KEY, "-inf", "+inf")
    assert [m.job_id for m in out] == ["B", "A"]
    assert out[0].progress == 3 and out[1].status is JobState.COMPLETED
    assert rows(cap.records) == []


def test_c38an_23_list_jobs_filter_skips_not_stops_c38():
    # FIRST row fails the filter: continue -> [B, C]; break -> [].
    r = Redis(
        zsets={LIST_KEY: ["X", "B", "C", "D"]},
        store={
            "job:X:status": row(job_id="X", status="completed"),
            "job:B:status": row(job_id="B", status="running"),
            "job:C:status": row(job_id="C", status="running"),
            "job:D:status": row(job_id="D", status="running"),
        },
    )
    s = svc(r)
    with LogSwap():
        out = run(s.list_jobs(JobState.RUNNING, 2))
    assert [m.job_id for m in out] == ["B", "C"]  # limit honoured AFTER skips


def test_c38an_24_list_jobs_expired_entry_pruned_c38():
    r = Redis(
        zsets={LIST_KEY: ["GONE", "B"]}, store={"job:B:status": row(job_id="B", status="running")}
    )
    s = svc(r)
    with LogSwap() as cap:
        out = run(s.list_jobs(None, 10))
    assert [m.job_id for m in out] == ["B"]
    assert ("zrem", LIST_KEY, "GONE") in calls(r, "zrem")
    assert rows(cap.records) == []


# =========================================================================
# get_job_status_service singleton (1 key: JobStatusService(None))
# =========================================================================


def test_c38an_25_singleton_attaches_first_client_c38():
    reset_job_status_service()
    try:
        r1, r2 = Redis(), Redis()
        s1 = get_job_status_service(r1)
        assert isinstance(s1, JobStatusService)
        assert s1._redis is r1
        s2 = get_job_status_service(r2)
        assert s2 is s1 and s1._redis is r1  # second client IGNORED
    finally:
        reset_job_status_service()
