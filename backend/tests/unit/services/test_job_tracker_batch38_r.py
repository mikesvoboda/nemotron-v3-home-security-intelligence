# TARGET-MODULE: backend.services.job_tracker
"""Battery R - campaign #16 of the ladder (batch-38): kill-real coverage for
``backend/services/job_tracker.py`` (309 survivors at 58.36% entering).

Harness-compatible by design (batch-30 single-process sweep): every test is a
module-level sync ``test_*()`` with no fixtures and no parametrize; coroutines
run through ``asyncio.run`` inside. The file is also collected by normal
pytest in the repo tree, so every seam swap restores in ``finally``.

The shipped battery exercises the lifecycle loosely; what survived is the
exact-shape layer: the FULL JobInfo dict after every transition (dropped
kwarg = missing key, never None), tz-awareness of datetime.now(UTC) stamps
(datetime.now(None) returns a NAIVE local stamp - only the "+00:00" offset
assert kills it), every log call as (level, exact msg, extra-kwarg PRESENCE,
full extra dict), exact redis call tuples ``set("job:<id>", snapshot,
expire=ttl)`` / ``publish(channel, json)`` with the exact json.dumps
separators, the exact rendered payload dicts of every broadcast (type/data
keys case-pinned; kwargs dropped to trailing-comma make a MISSING key, not a
None one), throttle arithmetic across the default-lookup path (get(id, 0)
-> None raises on the // below; the -> 1 default and the // -> / threshold
division both proved EQUIVALENT - see the ledger), and the
JobInfo-reconstruction .get-default matrix of get_job_from_redis: EVERY
default gets a polarity where its key is ABSENT and every key-lookup gets a
polarity where it is PRESENT with a value different from the default (the
job_id fallback additionally needs stored-id != lookup-id).

Honesty ledger - dispositions registered EQUIVALENT (the sweep must show
GREEN on exactly these unless the sweep proves otherwise; anything else
GREEN is a test gap). m6/m8 were found by the pre-launch sweep (expected
GREEN=1 at authoring) and adjudicated by BODY proof, not by diff shape
(survivor-disposition rule):

* cleanup_completed_jobs__mutmut_7  EQUIVALENT - pop(job_id, None) ->
*   pop(job_id, ) (trailing comma = default DELETED, 1-arg pop; battery Q
*   m35 proved mutmut 3 renders the default-deleted call exactly this way):
*   job_id iterates from to_remove, which was built from self._jobs, so the
*   key is ALWAYS present at pop time - the default is unreachable and the
*   1-arg pop otherwise behaves identically.
* _should_broadcast_progress__mutmut_6  EQUIVALENT - get(job_id, 0) ->
*   get(job_id, 1): last_broadcast is consumed ONLY as last_broadcast //
*   PROGRESS_THROTTLE_INCREMENT (10); on the absent-key path 0//10 == 1//10
*   == 0, and a present key never consults the default -> identical for
*   every input.
* _should_broadcast_progress__mutmut_8  EQUIVALENT - last_broadcast // 10 ->
*   last_broadcast / 10: the compared value current_threshold = progress //
*   10 is always an int, so with L = last//10 <= last/10 < L+1, `c > L` and
*   `c > last/10` agree for every integer c (c > L iff c >= L+1 > last/10);
*   stored throttle values are ints anyway. The last=15/progress=19 polarity
*   cannot separate them (floors tie 1==1 -> False; float 1 > 1.5 -> False).

All other 306 survivor keys have an explicit kill polarity in this battery;
sweep result: RED=306 GREEN=3 of 309 == this ledger exactly. If a later
sweep GREENs anything else, it is a gap - close it (or register the EQUIV
with a body proof) before the run. Delta-birth audit after run 1 is
MANDATORY per the c15 protocol: archive the module meta BEFORE launch;
delta = cur meta keys - archived keys; every birth key must be swept,
killed, or registered before run 2.
"""

from __future__ import annotations

import asyncio
import json
import sys
import types
import uuid

from backend.services.job_tracker import JobStatus, JobTracker

_MISSING = object()

_SB_NAME = "backend.services.system_broadcaster"


def _globals_of(fn):
    f = fn
    while hasattr(f, "__wrapped__"):
        f = f.__wrapped__
    return f.__globals__


_G = _globals_of(JobTracker.create_job)


class _LogCap:
    """Records (level, msg, args, kwargs) tuples; installed as the module logger."""

    def __init__(self):
        self.calls = []

    def _rec(self, level):
        def _f(msg, *args, **kwargs):
            self.calls.append((level, msg, args, kwargs))

        return _f

    def __getattr__(self, name):
        return self._rec(name)

    def at(self, level):
        return [c for c in self.calls if c[0] == level]

    def names(self):
        """(level, msg) sequence of every call - pins DROPPED log statements."""
        return [(c[0], c[1]) for c in self.calls]


def _install_logger():
    """Swap the module logger; return (cap, restore-thunk)."""
    cap = _LogCap()
    old = _G["logger"]

    def restore():
        _G["logger"] = old

    _G["logger"] = cap
    return cap, restore


def _extra(call):
    """The extra= kwarg dict, or _MISSING when the kwarg is absent."""
    return call[3].get("extra", _MISSING)


def _assert_tz_aware(ts):
    """datetime.now(UTC).isoformat() ends in the UTC offset; naive (now(None)
    == now()) does not. This is the ONLY discriminator for that family."""
    assert isinstance(ts, str), f"stamp must be an isoformat string, got {ts!r}"
    assert ts.endswith("+00:00"), f"stamp must be tz-aware UTC, got {ts!r}"


class _Recorder:
    """Sync broadcast callback spy: records (event_type, data) calls."""

    def __init__(self):
        self.calls = []

    def __call__(self, event_type, data):
        self.calls.append((event_type, data))


class _BoomBroadcaster:
    """Sync broadcast callback that always raises (drives _broadcast's except)."""

    def __call__(self, _event_type, _data):
        raise RuntimeError("cb-down")


class _FakeRedis:
    """Redis spy: get() answers a dict store; set()/publish() record calls."""

    def __init__(self):
        self.store = {}
        self.set_calls = []
        self.published = []

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, expire=None):
        self.set_calls.append((key, value, expire))
        return True

    async def publish(self, channel, message):
        self.published.append((channel, message))
        return 1


class _BoomRedis:
    """Every awaited redis call raises (drives persist/get/abort excepts)."""

    async def get(self, key):
        raise RuntimeError("boom")

    async def set(self, key, value, expire=None):
        raise RuntimeError("boom")

    async def publish(self, channel, message):
        raise RuntimeError("kaboom")


class _FakeBcast:
    """SystemBroadcaster stand-in for the websocket callback."""

    def __init__(self):
        self.sent = []

    async def _send_to_local_clients(self, payload):
        self.sent.append(payload)


def _sb_shim(bcast):
    """Install a fake backend.services.system_broadcaster module (the real one
    is heavy and gets imported INSIDE the callback); return (fake, restore)."""
    old = sys.modules.get(_SB_NAME)
    fake = types.ModuleType(_SB_NAME)
    fake.get_system_broadcaster = lambda: bcast
    sys.modules[_SB_NAME] = fake

    def restore():
        if old is None:
            sys.modules.pop(_SB_NAME, None)
        else:
            sys.modules[_SB_NAME] = old

    return fake, restore


class _PersistSpy:
    """Stands in for tracker._schedule_persist via setattr; records calls."""

    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))


# --------------------------------------------------------------------------
# create_websocket_broadcast_callback (19 keys)
# --------------------------------------------------------------------------


def test_ws_callback_exact_record():
    fb = _FakeBcast()
    _fake_sb, restore_sb = _sb_shim(fb)
    cap, restore_log = _install_logger()
    try:
        cb = _G["create_websocket_broadcast_callback"]()
        payload = {"type": "job_progress", "data": {"job_id": "wsj", "n": 1}}
        asyncio.run(cb("job_progress", payload))
        # m2 (_send_to_local_clients(None)): the payload object must pass through
        assert fb.sent[0] is payload
        d = cap.at("debug")
        assert len(d) == 1
        assert d[0][1] == "Broadcast job event via WebSocket"
        assert _extra(d[0]) == {"event_type": "job_progress", "job_id": "wsj"}
        assert cap.names() == [("debug", "Broadcast job event via WebSocket")]

        # "data" key ABSENT: original's get("data", {}) -> {} -> job_id None.
        # m16 (default None) / m18 (trailing comma = default DELETED ->
        # 1-positional get) make the inner .get target None and RAISE.
        cap.calls.clear()
        asyncio.run(cb("job_failed", {"type": "job_failed"}))
        assert cap.names() == [("debug", "Broadcast job event via WebSocket")]
        assert _extra(cap.calls[0]) == {"event_type": "job_failed", "job_id": None}
    finally:
        restore_sb()
        restore_log()


# --------------------------------------------------------------------------
# _broadcast (12 keys)
# --------------------------------------------------------------------------


def test_broadcast_callback_paths():
    class _Loop:
        def __init__(self):
            self.created = []

        def create_task(self, coro):
            if not asyncio.iscoroutine(coro):
                raise TypeError("a coroutine is required, not None")
            self.created.append(coro)
            coro.close()

    class _Shim:
        def __init__(self, real, loop):
            self._real = real
            self._loop = loop

        def get_running_loop(self):
            return self._loop

        def __getattr__(self, name):
            return getattr(self._real, name)

    cap, restore_log = _install_logger()
    old_asyncio = _G["asyncio"]
    loop = _Loop()
    try:
        _G["asyncio"] = _Shim(old_asyncio, loop)
        rec = _Recorder()
        t = JobTracker(broadcast_callback=rec)
        t._broadcast("evt_sync", {"a": 1})
        assert rec.calls == [("evt_sync", {"a": 1})]
        assert loop.created == []

        async def _acb(event_type, data):
            return None

        t2 = JobTracker(broadcast_callback=_acb)
        t2._broadcast("evt_async", {"b": 2})
        # m9: create_task(None) raises inside _Loop -> lands in the warning
        # branch; the original creates exactly one task and warns never.
        assert len(loop.created) == 1
        assert cap.at("warning") == []

        # no callback configured: silent no-op, no call anywhere
        cap.calls.clear()
        t3 = JobTracker()
        t3._broadcast("evt_none", {})
        assert cap.calls == []
    finally:
        _G["asyncio"] = old_asyncio
        restore_log()


def test_broadcast_exception_record():
    cap, restore_log = _install_logger()
    try:
        t = JobTracker(broadcast_callback=_BoomBroadcaster())
        t._broadcast("job_test_evt", {"type": "x"})
        w = cap.at("warning")
        assert len(w) == 1
        assert w[0][1] == "Failed to broadcast job event"
        assert _extra(w[0]) == {"event_type": "job_test_evt", "error": "cb-down"}
        # m14 (extra kwarg dropped): full extra equality above proves the
        # kwarg is PRESENT with the exact dict (absent -> _MISSING).
        assert cap.names() == [("warning", "Failed to broadcast job event")]
    finally:
        restore_log()


# --------------------------------------------------------------------------
# _broadcast_progress + update_progress throttle (12 + 1 keys)
# --------------------------------------------------------------------------


def test_broadcast_progress_debug_record():
    cap, restore_log = _install_logger()
    try:
        rec = _Recorder()
        t = JobTracker(broadcast_callback=rec)
        jid = t.create_job("bp")
        cap.calls.clear()
        t.update_progress(jid, 10)  # crosses the 0->10 threshold
        d = [c for c in cap.at("debug") if c[1] == "Broadcasting job progress"]
        assert len(d) == 1
        assert _extra(d[0]) == {"job_id": jid, "progress": 10}
        # m23 (debug call removed entirely): the call must EXIST
        assert cap.names() == [("debug", "Broadcasting job progress")]
        # status is still "pending" (update_progress never touches status);
        # m8 (status=None) and m17 (str(None)) mutate the payload below.
        assert rec.calls == [
            (
                "job_progress",
                {
                    "type": "job_progress",
                    "data": {"job_id": jid, "job_type": "bp", "progress": 10, "status": "pending"},
                },
            )
        ]
    finally:
        restore_log()


def test_update_progress_broadcast_persists():
    cap, restore_log = _install_logger()
    try:
        t = JobTracker()
        jid = t.create_job("up")
        spy = _PersistSpy()
        t._schedule_persist = spy
        t.update_progress(jid, 5)
        assert spy.calls == []  # no threshold crossed -> no broadcast, no persist
        t.update_progress(jid, 10)
        # m28 (_schedule_persist(None)): the args tuple must carry the real id
        assert spy.calls == [((jid,), {})]
        assert t._jobs[jid]["progress"] == 10
        t.update_progress(jid, 150)
        assert t._jobs[jid]["progress"] == 100
        t.update_progress(jid, -5, message="neg")
        assert t._jobs[jid]["progress"] == 0
        assert t._jobs[jid]["message"] == "neg"  # message set even without broadcast
    finally:
        restore_log()


def test_should_broadcast_default_from_throttle_dict():
    t = JobTracker()
    # throttle entry ABSENT -> get(job_id, 0) default path:
    # m3/m5 (default None) raise TypeError on the // below; m6 (default 1)
    # shifts last_threshold so 0->10 no longer broadcasts.
    assert t._should_broadcast_progress("ghost", 10) is True
    assert t._should_broadcast_progress("ghost", 5) is False
    t._last_broadcast_progress["g2"] = 15
    assert t._should_broadcast_progress("g2", 25) is True
    t._last_broadcast_progress["g3"] = 9
    assert t._should_broadcast_progress("g3", 10) is True


def test_throttle_float_threshold():
    t = JobTracker()
    t._last_broadcast_progress["f"] = 15
    # boundary pins for the threshold arithmetic (last=15: floor 1, float
    # 1.5). m8 (last // -> last /) is REGISTERED EQUIVALENT (ledger): with
    # current always the int progress//10, c > 1 iff c >= 2 > 1.5, so both
    # branches below agree orig-vs-mutant; this still pins the original's
    # truth table against any other arithmetic mutation.
    assert t._should_broadcast_progress("f", 19) is False
    assert t._should_broadcast_progress("f", 20) is True


# --------------------------------------------------------------------------
# _persist_job_async / _schedule_persist (11 + 2 keys)
# --------------------------------------------------------------------------


def test_persist_job_async_writes_exact_call():
    r = _FakeRedis()
    t = JobTracker(redis_client=r)
    jid = t.create_job("pj")
    t._jobs[jid]["progress"] = 12
    asyncio.run(t._persist_job_async(jid, ttl=77))
    assert r.set_calls == [("job:" + jid, dict(t._jobs[jid]), 77)]
    # the written value is a SNAPSHOT copy made under the lock
    t._jobs[jid]["progress"] = 99
    assert r.set_calls[0][1]["progress"] == 12
    # job ABSENT -> silent return, no write
    r2 = _FakeRedis()
    t2 = JobTracker(redis_client=r2)
    asyncio.run(t2._persist_job_async("ghost"))
    assert r2.set_calls == []
    # redis None -> silent return, no raise
    t3 = JobTracker()
    asyncio.run(t3._persist_job_async("ghost"))


def test_persist_failure_record():
    cap, restore_log = _install_logger()
    try:
        t = JobTracker(redis_client=_BoomRedis())
        jid = t.create_job("pf")
        cap.calls.clear()
        asyncio.run(t._persist_job_async(jid, ttl=5))
        w = cap.at("warning")
        assert len(w) == 1
        assert w[0][1] == "Failed to persist job to Redis"
        assert _extra(w[0]) == {"job_id": jid, "error": "boom"}
        assert cap.names() == [("warning", "Failed to persist job to Redis")]  # m18
    finally:
        restore_log()


def test_schedule_persist_forwards_ttl():
    class _L:
        def __init__(self):
            self.created = []

        def create_task(self, coro):
            self.created.append(coro)

    class _Shim:
        def __init__(self, real, loop):
            self._real = real
            self._loop = loop

        def get_running_loop(self):
            return self._loop

        def __getattr__(self, name):
            return getattr(self._real, name)

    t = JobTracker(redis_client=_FakeRedis())
    seen = []

    async def _spy(job_id, ttl=None):
        seen.append((job_id, ttl))

    t._persist_job_async = _spy
    loop = _L()
    old_asyncio = _G["asyncio"]
    try:
        _G["asyncio"] = _Shim(old_asyncio, loop)
        t._schedule_persist("sj")
        t._schedule_persist("tj", ttl=99)
    finally:
        _G["asyncio"] = old_asyncio
    assert len(loop.created) == 2
    for coro in loop.created:
        asyncio.run(coro)
    # m5 (ttl arg -> None) and m7 (ttl arg dropped, trailing comma) both lose
    # the 99 on the second call.
    assert seen == [("sj", None), ("tj", 99)]


def test_schedule_persist_without_loop_logs_debug():
    # RUN-1 DELTA KEYS _schedule_persist m8/m9/m10/m11 (births of the
    # coverage-growth renumber; msg None / XX-wrapped / lower / UPPER of the
    # no-loop debug line). Sync call site with a redis client set and NO
    # running event loop -> get_running_loop() raises RuntimeError -> the
    # except branch logs exactly this debug record.
    cap, restore_log = _install_logger()
    try:
        t = JobTracker(redis_client=_FakeRedis())
        t._schedule_persist("nl")
        assert cap.names() == [("debug", "No event loop available for Redis persistence")]
        assert _extra(cap.calls[0]) is _MISSING
        # and it is a pure no-op besides the log - nothing scheduled, no raise
        t._schedule_persist("nl2", ttl=5)
        assert len(cap.calls) == 2
    finally:
        restore_log()


# --------------------------------------------------------------------------
# get_job_from_redis (68 keys) - the .get-default matrix + failure record
# --------------------------------------------------------------------------

# EVERY key present (kills the hard-None family m12-18, the dropped-kwarg
# family m22-28, and every key XX/CASE family on PRESENT values)
_FULL = {
    "job_id": "fj",
    "job_type": "ftype",
    "status": "running",
    "progress": 42,
    "message": "fmsg",
    "created_at": "fc",
    "started_at": "fs",
    "completed_at": "fcomp",
    "result": {"ok": 1},
    "error": "ferr",
}

# core present, the five get(key) optionals absent (kills m59-61: the message
# KEY mutations only diverge when the key is PRESENT with a non-None value)
_MISS = {
    "job_id": "mj",
    "job_type": "mtype",
    "status": "completed",
    "progress": 7,
    "message": "mmsg",
    "created_at": "mc",
}

# EVERY defaulted key absent: the defaults themselves become observable
_ABSENT = {"message": "am"}

# the present-trio polarity: progress/message/created_at PRESENT, everything
# else absent (kills m52-58 progress-key mutations on a PRESENT value)
_TRIO = {"progress": 55, "message": "minmsg", "created_at": "nc"}


def test_get_job_from_redis_full_reconstruction():
    r = _FakeRedis()
    r.store["job:fj"] = dict(_FULL)
    t = JobTracker(redis_client=r)
    info = asyncio.run(t.get_job_from_redis("fj"))
    assert info == {**_FULL, "status": JobStatus.RUNNING}


def test_get_job_from_redis_missing_optional_fields():
    r = _FakeRedis()
    r.store["job:mj"] = dict(_MISS)
    t = JobTracker(redis_client=r)
    info = asyncio.run(t.get_job_from_redis("mj"))
    assert info == {
        "job_id": "mj",
        "job_type": "mtype",
        "status": JobStatus.COMPLETED,
        "progress": 7,
        "message": "mmsg",
        "created_at": "mc",
        "started_at": None,
        "completed_at": None,
        "result": None,
        "error": None,
    }


def test_get_job_from_redis_defaults_matrix():
    r = _FakeRedis()
    r.store["job:ej"] = dict(_ABSENT)
    t = JobTracker(redis_client=r)
    info = asyncio.run(t.get_job_from_redis("ej"))
    # ABSENT job_id -> the CALL ARG (m30 default None, m32 trailing comma =
    # 1-positional get -> None deviate); ABSENT job_type -> "unknown"
    # (m36/38/41/42); ABSENT status -> "pending" (m45/47 None raise -> except
    # path; m50/51 "XXpendingXX"/"PENDING" raise ValueError -> except path);
    # ABSENT progress -> 0 (m53/55 -> None, m58 -> 1); ABSENT created_at ->
    # "" (m63/64/65 -> None, m68 -> "XXXX").
    assert info == {
        "job_id": "ej",
        "job_type": "unknown",
        "status": JobStatus.PENDING,
        "progress": 0,
        "message": "am",
        "created_at": "",
        "started_at": None,
        "completed_at": None,
        "result": None,
        "error": None,
    }

    # Present-trio polarity: kills m52/m56/m57/m54 (progress key mutations),
    # m62/m66/m67/m64 (created_at key mutations) on PRESENT values.
    r.store["job:tj"] = dict(_TRIO)
    info2 = asyncio.run(t.get_job_from_redis("tj"))
    assert info2 == {
        "job_id": "tj",
        "job_type": "unknown",
        "status": JobStatus.PENDING,
        "progress": 55,
        "message": "minmsg",
        "created_at": "nc",
        "started_at": None,
        "completed_at": None,
        "result": None,
        "error": None,
    }

    # stored job_id DIFFERENT from the lookup id: kills the key-swap family
    # m29 (get(None, job_id)) and m33/m34 (XX/CASE key -> miss -> call arg);
    # m30/m32 stay equal here but die on the ABSENT polarity above.
    r.store["job:qid"] = {"job_id": "stored-id"}
    info3 = asyncio.run(t.get_job_from_redis("qid"))
    assert info3["job_id"] == "stored-id"
    # (the m7 and->or non-dict polarity lives in test_get_job_from_redis_
    # failure_record, where the log cap can pin the no-warning side)


def test_get_job_from_redis_in_memory_short_circuit():
    r = _FakeRedis()
    t = JobTracker(redis_client=r)
    jid = t.create_job("mem")
    r.store["job:" + jid] = {"job_type": "impostor"}
    info = asyncio.run(t.get_job_from_redis(jid))
    assert info is t._jobs[jid]  # memory wins; redis copy ignored


def test_get_job_from_redis_failure_record():
    cap, restore_log = _install_logger()
    try:
        t = JobTracker(redis_client=_BoomRedis())
        out = asyncio.run(t.get_job_from_redis("bj"))
        assert out is None
        w = cap.at("warning")
        assert len(w) == 1
        assert w[0][1] == "Failed to get job from Redis"
        assert _extra(w[0]) == {"job_id": "bj", "error": "boom"}  # m92 str(None)
        assert cap.names() == [("warning", "Failed to get job from Redis")]  # m84
        # the non-dict fall-through must NOT warn under the original and-chain
        r2 = _FakeRedis()
        r2.store["job:nj"] = "a string"
        t2 = JobTracker(redis_client=r2)
        cap.calls.clear()
        assert asyncio.run(t2.get_job_from_redis("nj")) is None
        assert cap.calls == []  # m7: the or-variant warns here
    finally:
        restore_log()


# --------------------------------------------------------------------------
# create_job / start_job / complete_job / fail_job (14 + 10 + 14 + 16 keys)
# --------------------------------------------------------------------------


def test_create_job_initial_state_and_log():
    cap, restore_log = _install_logger()
    try:
        t = JobTracker()
        spy = _PersistSpy()
        t._schedule_persist = spy
        jid = t.create_job("ct", job_id="given-id")
        assert jid == "given-id"
        body = dict(t._jobs[jid])
        created = body.pop("created_at")
        _assert_tz_aware(created)  # m5: datetime.now(None) -> naive stamp
        # FULL initial dict: m20 (result kwarg removed) makes the dict
        # MISSING the "result" key - equality kills it regardless of runtime
        # TypedDict validation.
        assert body == {
            "job_id": "given-id",
            "job_type": "ct",
            "status": JobStatus.PENDING,
            "progress": 0,
            "message": None,
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
        }
        # m24: throttle seed must be exactly 0
        assert t._last_broadcast_progress[jid] == 0
        assert cap.names() == [("info", "Job created")]  # m25 msg None, m29-31
        assert _extra(cap.at("info")[0]) == {"job_id": "given-id", "job_type": "ct"}
        assert spy.calls == [(("given-id",), {})]  # m36 _schedule_persist(None)
        auto = t.create_job("auto")
        assert auto != "auto"
        uuid.UUID(auto)  # uuid4-shaped when job_id is None
    finally:
        restore_log()


def test_start_job_state_and_log():
    cap, restore_log = _install_logger()
    try:
        t = JobTracker()
        spy = _PersistSpy()
        t._schedule_persist = spy
        jid = t.create_job("st")
        cap.calls.clear()
        spy.calls.clear()  # create_job persisted once already
        t.start_job(jid)
        j = t._jobs[jid]
        assert j["status"] is JobStatus.RUNNING
        assert j["message"] is None  # message kwarg None -> untouched
        _assert_tz_aware(j["started_at"])  # m2: datetime.now(None) == naive
        assert cap.names() == [("info", "Job started")]  # m15/19/20/21 msgs
        assert _extra(cap.at("info")[0]) == {"job_id": jid}  # m16/m18/m22/m23
        assert spy.calls == [((jid,), {})]  # m24 _schedule_persist(None)

        jid2 = t.create_job("st2")
        t.start_job(jid2, message="go")
        assert t._jobs[jid2]["message"] == "go"
        try:
            t.start_job("absent")
            raise AssertionError("KeyError expected")
        except KeyError as exc:
            assert str(exc) == "'Job not found: absent'"
    finally:
        restore_log()


def test_complete_job_state_log_broadcast_ttl():
    cap, restore_log = _install_logger()
    try:
        rec = _Recorder()
        t = JobTracker(broadcast_callback=rec)
        jid = t.create_job("cmp")
        spy = _PersistSpy()
        t._schedule_persist = spy
        cap.calls.clear()
        t.complete_job(jid, result={"ok": 1})
        j = t._jobs[jid]
        assert j["status"] is JobStatus.COMPLETED
        assert j["progress"] == 100
        assert j["result"] == {"ok": 1}
        assert j["message"] == "Completed successfully"
        _assert_tz_aware(j["completed_at"])  # m2
        assert cap.names() == [("info", "Job completed")]  # m25/29/30/31
        assert _extra(cap.at("info")[0]) == {"job_id": jid, "job_type": "cmp"}  # m26/28/32-35
        # m38 None-id / m39 None-ttl / m41 ttl arg dropped (trailing comma)
        assert spy.calls == [((jid,), {"ttl": 3600})]
        assert rec.calls == [
            (
                "job_completed",
                {
                    "type": "job_completed",
                    "data": {"job_id": jid, "job_type": "cmp", "result": {"ok": 1}},
                },
            )
        ]
    finally:
        restore_log()


def test_fail_job_state_log_broadcast_ttl():
    cap, restore_log = _install_logger()
    try:
        rec = _Recorder()
        t = JobTracker(broadcast_callback=rec)
        jid = t.create_job("fl")
        spy = _PersistSpy()
        t._schedule_persist = spy
        cap.calls.clear()
        t.fail_job(jid, "boom-err")
        j = t._jobs[jid]
        assert j["status"] is JobStatus.FAILED
        assert j["error"] == "boom-err"
        assert j["message"] == "Failed: boom-err"
        _assert_tz_aware(j["completed_at"])  # m2
        assert cap.names() == [("error", "Job failed")]  # m18/22/23/24
        assert _extra(cap.at("error")[0]) == {  # m19/21/25-28/31/32
            "job_id": jid,
            "job_type": "fl",
            "error": "boom-err",
        }
        assert spy.calls == [((jid,), {"ttl": 3600})]  # m33/34/36
        assert rec.calls == [
            (
                "job_failed",
                {
                    "type": "job_failed",
                    "data": {"job_id": jid, "job_type": "fl", "error": "boom-err"},
                },
            )
        ]
    finally:
        restore_log()


# --------------------------------------------------------------------------
# cancel_job / cancel_queued_job (30 + 20 keys)
# --------------------------------------------------------------------------


def test_cancel_job_full_state_log_broadcast_ttl():
    cap, restore_log = _install_logger()
    try:
        rec = _Recorder()
        t = JobTracker(broadcast_callback=rec)
        jid = t.create_job("cj")
        spy = _PersistSpy()
        t._schedule_persist = spy
        cap.calls.clear()
        assert t.cancel_job(jid) is True
        j = t._jobs[jid]
        assert j["status"] is JobStatus.FAILED
        assert j["error"] == "Cancelled by user"
        assert j["message"] == "Job cancelled by user request"  # m22-27
        _assert_tz_aware(j["completed_at"])  # m1 (now=None) / m2 (naive)
        assert "completed_at" in j and "COMPLETED_AT" not in j  # m13/14/15
        assert cap.names() == [("info", "Job cancelled")]  # m28/32/33/34
        assert _extra(cap.at("info")[0]) == {"job_id": jid, "job_type": "cj"}  # m29/31/35-38
        assert spy.calls == [((jid,), {"ttl": 3600})]  # m41/42/44
        # m61/62 payload "type" key XX/CASE; m46/47 None kwargs; m49/50
        # dropped kwargs (missing key) - full payload equality covers all.
        assert rec.calls == [
            (
                "job_failed",
                {
                    "type": "job_failed",
                    "data": {"job_id": jid, "job_type": "cj", "error": "Cancelled by user"},
                },
            )
        ]
        # terminal statuses refuse
        assert t.cancel_job(jid) is False
        jid2 = t.create_job("cj2")
        t.complete_job(jid2)
        assert t.cancel_job(jid2) is False
    finally:
        restore_log()


def test_cancel_queued_job_branches():
    cap, restore_log = _install_logger()
    try:
        rec = _Recorder()
        t = JobTracker(broadcast_callback=rec)
        run_id = t.create_job("cqr")
        t.start_job(run_id)
        done_id = t.create_job("cqdone")
        t.start_job(done_id)
        t.complete_job(done_id)
        jid = t.create_job("cq")
        spy = _PersistSpy()
        t._schedule_persist = spy
        cap.calls.clear()
        # guard branches (exact strings; m11 XX-wrapped)
        assert t.cancel_queued_job(run_id) == (
            False,
            "Cannot cancel running job - use abort instead",
        )
        assert t.cancel_queued_job(done_id) == (False, "Cannot cancel job with status: completed")
        assert spy.calls == []
        rec.calls.clear()  # start/complete broadcasts above are not our subject
        # success path
        assert t.cancel_queued_job(jid) == (True, "")
        j = t._jobs[jid]
        assert j["status"] is JobStatus.FAILED
        assert j["error"] == "Cancelled by user"
        assert j["message"] == "Job cancelled by user request"
        _assert_tz_aware(j["completed_at"])  # m2: naive from datetime.now(None)
        assert cap.names() == [("info", "Queued job cancelled")]  # m37/41/42/43
        assert _extra(cap.at("info")[0]) == {"job_id": jid, "job_type": "cq"}  # m34/38/40/44-47
        assert spy.calls == [((jid,), {"ttl": 3600})]  # m48/49/51
        # m54 job_type None / m57 dropped kwarg / m66/67 "type" key case
        assert rec.calls == [
            (
                "job_failed",
                {
                    "type": "job_failed",
                    "data": {"job_id": jid, "job_type": "cq", "error": "Cancelled by user"},
                },
            )
        ]
    finally:
        restore_log()


# --------------------------------------------------------------------------
# abort_job (46 keys)
# --------------------------------------------------------------------------


def test_abort_job_full_success_path():
    cap, restore_log = _install_logger()
    try:
        r = _FakeRedis()
        rec = _Recorder()
        t = JobTracker(rec, r)
        pend = t.create_job("ap")
        run = t.create_job("ar")
        t.start_job(run)
        done = t.create_job("ad")
        t.complete_job(done)
        spy = _PersistSpy()
        t._schedule_persist = spy
        cap.calls.clear()
        try:
            asyncio.run(t.abort_job("absent"))
            raise AssertionError("KeyError expected")
        except KeyError as exc:
            assert str(exc) == "'Job not found: absent'"
        assert asyncio.run(t.abort_job(pend)) == (
            False,
            "Cannot abort queued job - use cancel instead",  # m12 XX-wrapped
        )
        assert asyncio.run(t.abort_job(done)) == (False, "Cannot abort job with status: completed")
        ok, msg = asyncio.run(t.abort_job(run, reason="ship it"))
        assert (ok, msg) == (True, "")
        channel = f"job:{run}:control"
        # exact channel + json.dumps separator shape
        assert r.published == [(channel, json.dumps({"action": "abort", "reason": "ship it"}))]
        assert t._jobs[run]["message"] == "Aborting: ship it"
        assert cap.names() == [("info", "Job abort signal sent"), ("info", "Job abort requested")]
        sent = cap.at("info")[0]
        assert _extra(sent) == {"job_id": run, "job_type": "ar", "channel": channel}
        req = cap.at("info")[1]
        assert _extra(req) == {"job_id": run, "job_type": "ar", "reason": "ship it"}
        assert spy.calls == [((run,), {})]  # m85: _schedule_persist(None)
    finally:
        restore_log()


def test_abort_job_without_redis_warns():
    cap, restore_log = _install_logger()
    try:
        t = JobTracker()  # no redis
        jid = t.create_job("nr")
        t.start_job(jid)
        spy = _PersistSpy()
        t._schedule_persist = spy
        cap.calls.clear()
        ok, msg = asyncio.run(t.abort_job(jid))
        assert (ok, msg) == (True, "")
        assert cap.names() == [
            ("warning", "No Redis client - abort signal not sent via pub/sub"),  # m64
            ("info", "Job abort requested"),
        ]  # m61/63/72/73/75-84
        assert _extra(cap.calls[0]) == {"job_id": jid}  # m67/68 key case
        # default reason exact shape: m1/m2/m3 (default -> None/lower/UPPER)
        assert t._jobs[jid]["message"] == "Aborting: User requested"
        assert _extra(cap.at("info")[0]) == {
            "job_id": jid,
            "job_type": "nr",
            "reason": "User requested",
        }
        assert spy.calls == [((jid,), {})]
    finally:
        restore_log()


def test_abort_job_publish_failure_returns_false():
    cap, restore_log = _install_logger()
    try:
        t = JobTracker(redis_client=_BoomRedis())
        jid = t.create_job("bf")
        t.start_job(jid)
        spy = _PersistSpy()
        t._schedule_persist = spy
        cap.calls.clear()
        out = asyncio.run(t.abort_job(jid))
        assert out == (False, "Failed to send abort signal: kaboom")
        assert cap.names() == [("error", "Failed to send abort signal")]  # m47/51/52/53
        assert _extra(cap.at("error")[0]) == {"job_id": jid, "error": "kaboom"}  # m48/50/54-58
        # early return: the aborting message must NOT have been written
        assert t._jobs[jid]["message"] is None
        assert spy.calls == []  # and nothing persisted
    finally:
        restore_log()


# --------------------------------------------------------------------------
# cleanup_completed_jobs (10 keys)
# --------------------------------------------------------------------------


def test_cleanup_completed_jobs():
    cap, restore_log = _install_logger()
    try:
        t = JobTracker()
        a = t.create_job("k1")
        b = t.create_job("k2")
        c = t.create_job("k3")
        t.start_job(a)
        t.complete_job(a)
        t.fail_job(b, "x")
        t._last_broadcast_progress[c] = 33  # live job: its throttle entry stays
        cap.calls.clear()
        assert t.cleanup_completed_jobs() == 2
        assert list(t._jobs) == [c]
        # removed job's throttle entry is popped (m5 pop(None) leaves it)
        assert a not in t._last_broadcast_progress
        assert b not in t._last_broadcast_progress
        assert t._last_broadcast_progress[c] == 33
        assert cap.names() == [("info", "Cleaned up completed jobs")]  # m8/12/13/14
        assert _extra(cap.at("info")[0]) == {"count": 2}  # m9/11/15/16
        cap.calls.clear()
        assert t.cleanup_completed_jobs() == 0
        assert cap.calls == []  # no log when nothing removed
    finally:
        restore_log()


# --------------------------------------------------------------------------
# setters + singleton + websocket init (4 + 4 + 4 + 8 keys)
# --------------------------------------------------------------------------


def test_setters_log_exact():
    cap, restore_log = _install_logger()
    try:
        t = JobTracker()
        cb = _Recorder()
        t.set_broadcast_callback(cb)
        assert t._broadcast_callback is cb
        r = _FakeRedis()
        t.set_redis_client(r)
        assert t._redis_client is r
        assert cap.names() == [
            ("info", "Job tracker broadcast callback configured"),
            ("info", "Job tracker Redis client configured"),
        ]  # None/XX/lower/UPPER msg variants all die here
        assert all(_extra(c) is _MISSING for c in cap.calls)  # no extra= exists
    finally:
        restore_log()


def test_get_job_tracker_ctor_args():
    cap, restore_log = _install_logger()
    old = _G["_job_tracker"]
    try:
        _G["reset_job_tracker"]()
        cb = _Recorder()
        r = _FakeRedis()
        t1 = _G["get_job_tracker"](cb, r)
        assert t1._broadcast_callback is cb  # m3 (callback arg -> None)
        assert t1._redis_client is r  # m4 (redis arg -> None), m6 (trailing
        # comma = redis arg DELETED -> callback lands in the redis slot only
        # if positional-preserved; either way this equality fails)
        t2 = _G["get_job_tracker"]()
        assert t2 is t1  # singleton reuse
        _G["reset_job_tracker"]()
        r2 = _FakeRedis()
        t3 = _G["get_job_tracker"](redis_client=r2)
        # m5 (positional JobTracker(redis_client)): r2 lands in the
        # BROADCAST-CALLBACK slot and _redis_client stays None.
        assert t3._redis_client is r2
        assert t3._broadcast_callback is None
    finally:
        _G["_job_tracker"] = old
        restore_log()


def test_init_job_tracker_websocket_branches():
    _fake_sb, restore_sb = _sb_shim(_FakeBcast())
    cap, restore_log = _install_logger()
    old_tracker = _G["_job_tracker"]
    init = _G["init_job_tracker_websocket"]
    cb_msg = "Job tracker broadcast callback configured"
    init_msg = "Job tracker initialized with WebSocket broadcasting"
    try:
        r = _FakeRedis()
        # A: fresh singleton + redis provided -> get_job_tracker(redis_client=
        # r) ALREADY sets _redis_client, so the persist-guard (redis not None
        # AND tracker redis None) is False -> exactly two records. m2
        # (get_job_tracker(redis_client=None)) leaves the fresh tracker
        # redis-less -> guard True -> set_redis_client -> a THIRD record. m10
        # (or) and m12 (`is not None` inverted) BOTH enter the guard here ->
        # third record too. All three die on this 2-record pin.
        _G["reset_job_tracker"]()
        base = len(cap.calls)
        t = asyncio.run(init(redis_client=r))
        assert t._broadcast_callback is not None
        assert t._redis_client is r
        assert cap.names()[base:] == [("info", cb_msg), ("info", init_msg)]
        base = len(cap.calls)
        # B: warm singleton + redis already set -> the guard must SKIP (no
        # record) and the callback guard must SKIP (callback set).
        t2 = asyncio.run(init(redis_client=r))
        assert t2 is t
        assert len(cap.calls) == base
        # C: fresh singleton, redis=None -> original skips the redis branch;
        # m11 (`redis_client is None and ...`) ENTERS it and sets None.
        _G["reset_job_tracker"]()
        t3 = asyncio.run(init(redis_client=None))
        assert t3._broadcast_callback is not None
        assert t3._redis_client is None
        assert cap.names()[base:] == [("info", cb_msg), ("info", init_msg)]
    finally:
        _G["_job_tracker"] = old_tracker
        restore_log()
        restore_sb()
