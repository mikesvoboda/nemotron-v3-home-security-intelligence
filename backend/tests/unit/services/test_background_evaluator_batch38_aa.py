"""Campaign #25 (batch-38, battery AA) - `backend/services.background_evaluator`.

# TARGET-MODULE: backend.services.background_evaluator

Harness contract (b30 sweep, /home/agent/runs/b30-sweep.py): NO pytest
fixtures, NO parametrize, NO monkeypatch - the sweep imports this file
directly and calls every module-level ``test_*`` with zero arguments in
ONE process, flipping os.environ[MUTANT_UNDER_TEST] per key. Everything
async is driven with asyncio.run INSIDE the test body. Seams are patched
through the TARGET MODULE's globals (be.time, be.asyncio.sleep,
be.get_session, be.get_job_status_service, be.BackgroundEvaluator) or
through constructor dependency injection (redis/gpu/queue/audit/tracker
fakes), always save/restore via the patched() contextmanager so a mid-test
assert failure cannot leak a patch into the next key's window.

Determinism strategy (the loop is real, the clock is not):
  * be.time is swapped for a scripted FakeTime - idle-duration math is
    exact (no wall floats in any assert; the >= boundary and the +/-
    polarity arms need scripted clocks to be observable AT all);
  * be.asyncio.sleep is swapped for a Sleeper - durations are RECORDED
    and script actions (raise / flip running / raise CancelledError) arm
    every loop exit; after a hard cap it raises a BaseException so an
    over-running mutant fails LOUD but never hangs the sweep;
  * the DB session is a recording fake: execute() returns scripted
    scalar_one_or_none results, expunge/commit/merge calls are recorded
    as ordered lists, and the WHOLE session sequence (2 sessions, 2
    commits, expunge identities) is asserted - a mutated statement object,
    a skipped commit or expunge(None) changes the record list;
  * JobTracker / JobStatusService fakes pin the call-site SIGNATURES
    (required parameters), so argument DELETIONS (the trailing-comma and
    drop-kwarg families) surface as TypeError instead of silently landing
    on a default, and every surviving call is compared as a whole tuple;
  * log records are captured from be.logger and asserted on the FULL
    msgs() sequence (msg-equality, never substring - XX-wrap, case flips
    and None-swap all die) plus the extra= attributes where present.

Honesty ledger: PENDING - EQUIV candidates will be REGISTERED BY
CONSTRUCTION here after the disposition sweep adjudicates every GREEN
(a construction claim is not a verdict claim; the sweep + probes are the
evidence).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import contextmanager
from typing import Any

from backend.services import background_evaluator as be

_REAL_SLEEP = asyncio.sleep


# ---------------------------------------------------------------------------
# capture / patch helpers (no fixtures - the sweep calls plain functions)
# ---------------------------------------------------------------------------


class RecordList(logging.Handler):
    """Captures EVERY record emitted through be.logger while active."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def one(self, msg: str) -> logging.LogRecord:
        hits = [r for r in self.records if r.getMessage() == msg]
        assert len(hits) == 1, (msg, [r.getMessage() for r in self.records])
        return hits[0]

    def msgs(self) -> list[str]:
        return [r.getMessage() for r in self.records]


@contextmanager
def logcap():
    cap = RecordList()
    old_level = be.logger.level
    be.logger.addHandler(cap)
    be.logger.setLevel(logging.DEBUG)
    try:
        yield cap
    finally:
        be.logger.removeHandler(cap)
        be.logger.setLevel(old_level)


@contextmanager
def patched(obj: Any, attr: str, value: Any):
    old = getattr(obj, attr)
    setattr(obj, attr, value)
    try:
        yield value
    finally:
        setattr(obj, attr, old)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


class LoopKill(BaseException):
    """Sleeper hard-cap kill: bypasses the loop's except-Exception arms so
    an over-running mutant TERMINATES (loudly) instead of hanging."""


# ---------------------------------------------------------------------------
# dependency fakes (constructor seam)
# ---------------------------------------------------------------------------


class FakeRedis:
    """llen over a scripted {queue_name: length} map; records EVERY
    requested name in order (a queue-name->None swap is visible even when
    the length lookup happens to match)."""

    def __init__(
        self, lens: dict[str, int] | None = None, raises: dict[str, Exception] | None = None
    ) -> None:
        self._lens = dict(lens or {})
        self._raises = dict(raises or {})
        self.names: list[Any] = []

    async def llen(self, name: Any) -> int:
        self.names.append(name)
        if isinstance(name, str) and name in self._raises:
            raise self._raises[name]
        return self._lens.get(name, 0)


class FakeGpu:
    """get_current_stats_async pops a scripted stats dict (last repeats);
    ('raise', exc) items raise."""

    def __init__(self, stats: list[Any] | None = None) -> None:
        self._stats = list(stats or [{}])
        self.calls = 0

    async def get_current_stats_async(self) -> Any:
        self.calls += 1
        item = self._stats.pop(0) if len(self._stats) > 1 else self._stats[0]
        if isinstance(item, tuple) and item and item[0] == "raise":
            raise item[1]
        return item


class FakeQueue:
    """dequeue pops scripted event ids (None = empty; exhausted = empty)."""

    def __init__(self, script: list[Any] | None = None) -> None:
        self._script = list(script or [])
        self.dequeues = 0

    async def dequeue(self) -> Any:
        self.dequeues += 1
        return self._script.pop(0) if self._script else None


class FakeAudit:
    """Records run_evaluation_llm_calls(audit, event) argument IDENTITIES."""

    def __init__(self, raises: Exception | None = None) -> None:
        self.calls: list[tuple[Any, Any]] = []
        self.raises = raises

    async def run_evaluation_llm_calls(self, audit: Any, event: Any) -> None:
        self.calls.append((audit, event))
        if self.raises is not None:
            raise self.raises


class FakeTracker:
    """JobTracker fake pinning the call-site signatures (required
    parameters turn the deletion mutants into TypeErrors)."""

    def __init__(self, cancelled: list[bool] | None = None) -> None:
        self.create_calls: list[Any] = []
        self.start_calls: list[tuple[Any, Any]] = []
        self.progress_calls: list[tuple[Any, Any, Any]] = []
        self.complete_calls: list[tuple[Any, Any]] = []
        self.fail_calls: list[tuple[Any, Any]] = []
        self.cancel_checks: list[Any] = []
        self._cancelled = list(cancelled or [])
        self._n = 0

    def create_job(self, job_type: str) -> str:
        self.create_calls.append(job_type)
        self._n += 1
        return f"tk-{self._n}"

    def start_job(self, job_id: str, message: str) -> None:
        self.start_calls.append((job_id, message))

    def update_progress(self, job_id: str, progress: Any, message: str) -> None:
        self.progress_calls.append((job_id, progress, message))

    def complete_job(self, job_id: str, result: Any = None) -> None:
        self.complete_calls.append((job_id, result))

    def fail_job(self, job_id: str, error: str) -> None:
        self.fail_calls.append((job_id, error))

    def is_cancelled(self, job_id: str) -> bool:
        self.cancel_checks.append(job_id)
        return self._cancelled.pop(0) if self._cancelled else False


class FakeJobService:
    """JobStatusService (legacy) fake; start_job kwargs are recorded as a
    whole dict; the other methods pin positional signatures."""

    def __init__(self, job_id: Any = "js-1", start_raises: Exception | None = None) -> None:
        self.start_kwargs: list[dict[str, Any]] = []
        self.progress_calls: list[tuple[Any, Any, Any]] = []
        self.complete_calls: list[tuple[Any, Any]] = []
        self.fail_calls: list[tuple[Any, Any]] = []
        self._job_id = job_id
        self._start_raises = start_raises

    async def start_job(self, **kwargs: Any) -> Any:
        self.start_kwargs.append(dict(kwargs))
        if self._start_raises is not None:
            raise self._start_raises
        return self._job_id

    async def update_progress(self, job_id: str, progress: Any, message: str) -> None:
        self.progress_calls.append((job_id, progress, message))

    async def complete_job(self, job_id: str, result: Any = None) -> None:
        self.complete_calls.append((job_id, result))

    async def fail_job(self, job_id: str, error: str) -> None:
        self.fail_calls.append((job_id, error))


class Row:
    """Minimal ORM-shaped row (attribute bag)."""

    def __init__(self, **kw: Any) -> None:
        self.__dict__.update(kw)


def make_event(event_id: str = "evt-1") -> Row:
    return Row(id=event_id, llm_prompt="PROMPT", reasoning="REASONING")


def make_audit(event_id: str = "evt-1", score: float = 0.87) -> Row:
    return Row(id="aud-1", event_id=event_id, overall_quality_score=score)


# ---------------------------------------------------------------------------
# DB session fake (module-global seam: be.get_session)
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, scalar: Any) -> None:
        self._scalar = scalar

    def scalar_one_or_none(self) -> Any:
        return self._scalar


class FakeSession:
    """One async-session: records executed statement OBJECTS (compared
    lazily by tests via str()), pops scripted scalars, records
    expunge/commit/merge. __aexit__ never swallows."""

    def __init__(self, factory: FakeSessionFactory) -> None:
        self.factory = factory
        self.executed: list[Any] = []
        self.expunged: list[Any] = []
        self.merged: list[Any] = []

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    async def execute(self, stmt: Any) -> Any:
        self.executed.append(stmt)
        item = self.factory.scalars.pop(0) if self.factory.scalars else None
        if isinstance(item, tuple) and item and item[0] == "raise":
            raise item[1]
        return _FakeResult(item)

    def expunge(self, obj: Any) -> None:
        self.expunged.append(obj)

    async def merge(self, obj: Any) -> Any:
        self.merged.append(obj)
        return self.factory.merge_result if self.factory.merge_result is not None else obj


class FakeSessionFactory:
    """be.get_session replacement: hands out recording sessions and holds
    the scripted execute() scalars for the WHOLE process_one flow."""

    def __init__(self, scalars: list[Any] | None = None, merge_result: Any = None) -> None:
        self.scalars = list(scalars or [])
        self.merge_result = merge_result
        self.sessions: list[FakeSession] = []
        self.calls = 0

    def __call__(self) -> FakeSession:
        self.calls += 1
        session = FakeSession(self)
        self.sessions.append(session)
        return session

    @property
    def all_executed(self) -> list[Any]:
        out: list[Any] = []
        for s in self.sessions:
            out.extend(s.executed)
        return out

    @property
    def all_merged(self) -> list[Any]:
        out: list[Any] = []
        for s in self.sessions:
            out.extend(s.merged)
        return out


# ---------------------------------------------------------------------------
# time / sleep fakes (module-global seams: be.time, be.asyncio.sleep)
# ---------------------------------------------------------------------------


class FakeTime:
    """be.time replacement: time() pops scripted values (last repeats)."""

    def __init__(self, values: list[float]) -> None:
        self._values = list(values)
        self.calls = 0

    def time(self) -> float:
        self.calls += 1
        return self._values.pop(0) if len(self._values) > 1 else self._values[0]


class Sleeper:
    """be.asyncio.sleep replacement: records every delay (None INCLUDED -
    a sleep(None) mutant must die on the recorded list, not on a real
    TypeError) and runs a per-call script action: None = plain pass,
    ("raise", exc) = raise, callable = invoke (arm loop exits). After
    `cap` calls raises LoopKill so no mutant can spin forever."""

    def __init__(self, script: list[Any] | None = None, cap: int = 40) -> None:
        self.slept: list[Any] = []
        self._script = list(script or [])
        self._cap = cap

    async def __call__(self, delay: Any) -> None:
        self.slept.append(delay)
        if len(self.slept) > self._cap:
            raise LoopKill("sleeper cap exceeded - over-running mutant")
        if self._script:
            action = self._script.pop(0)
            if isinstance(action, tuple) and action and action[0] == "raise":
                raise action[1]
            if callable(action):
                action(self)
        await _REAL_SLEEP(0)


def make_mgr(
    redis: Any = None,
    gpu: Any = None,
    queue: Any = None,
    audit: Any = None,
    *,
    tracker: Any = None,
    enabled: bool = True,
    threshold: int = 20,
    duration: int = 5,
    poll: float = 5.0,
) -> be.BackgroundEvaluator:
    return be.BackgroundEvaluator(
        redis_client=redis if redis is not None else FakeRedis(),
        gpu_monitor=gpu if gpu is not None else FakeGpu(),
        evaluation_queue=queue if queue is not None else FakeQueue(),
        audit_service=audit if audit is not None else FakeAudit(),
        gpu_idle_threshold=threshold,
        idle_duration_required=duration,
        poll_interval=poll,
        enabled=enabled,
        job_tracker=tracker,
    )


# ---------------------------------------------------------------------------
# __init__ / _get_job_status_service / _is_job_cancelled
# ---------------------------------------------------------------------------


def test_init_stores_every_dependency_exactly() -> None:
    redis, gpu, queue, audit, tracker = (
        FakeRedis(),
        FakeGpu(),
        FakeQueue(),
        FakeAudit(),
        FakeTracker(),
    )
    mgr = make_mgr(
        redis,
        gpu,
        queue,
        audit,
        tracker=tracker,
        enabled=False,
        threshold=7,
        duration=11,
        poll=2.5,
    )
    assert mgr._redis is redis
    assert mgr._gpu_monitor is gpu
    assert mgr._evaluation_queue is queue
    assert mgr._audit_service is audit
    assert mgr._job_tracker is tracker
    assert mgr.gpu_idle_threshold == 7
    assert mgr.idle_duration_required == 11
    assert mgr.poll_interval == 2.5
    assert mgr.enabled is False
    assert mgr.running is False
    assert mgr._task is None
    assert mgr._idle_since is None
    # the cached-service sentinel is EXACTLY None (a "" sentinel would
    # make every legacy-branch `is None` check pre-hit the cache)
    assert mgr._job_status_service is None


def test_init_defaults_are_the_documented_constants() -> None:
    mgr = make_mgr()
    assert mgr.gpu_idle_threshold == 20
    assert mgr.idle_duration_required == 5
    assert mgr.poll_interval == 5.0
    assert mgr.enabled is True
    assert mgr._job_tracker is None


def test_get_job_status_service_is_created_once_and_cached() -> None:
    """Two legacy process_one rounds must share ONE JobStatusService.

    The factory hands out FRESH instances per call, so a cache-bypass
    mutant (always-call) or a cache-poison mutant (returns None / self)
    shows up as a second factory call and a short second round.
    """
    svc1, svc2 = FakeJobService(job_id="js-a"), FakeJobService(job_id="js-b")
    made: list[Any] = []

    def factory(redis_client: Any) -> FakeJobService:
        made.append(redis_client)
        return svc1 if len(made) == 1 else svc2

    redis = FakeRedis()
    queue = FakeQueue(["evt-1", "evt-2"])
    mgr = make_mgr(redis, queue=queue)
    sess = FakeSessionFactory(
        scalars=[make_event("evt-1"), make_audit("evt-1"), make_event("evt-2"), make_audit("evt-2")]
    )

    async def main() -> None:
        with (
            patched(be, "get_job_status_service", factory),
            patched(be, "get_session", sess),
            logcap(),
        ):
            assert await mgr.process_one() is True
            assert await mgr.process_one() is True

    run(main())
    assert len(made) == 1, "service factory must fire exactly once (cache)"
    assert [k["job_id"] for k in svc1.start_kwargs] == [
        "evaluation-evt-1",
        "evaluation-evt-2",
    ]
    assert [c[0] for c in svc1.complete_calls] == ["js-a", "js-a"]
    assert svc2.start_kwargs == [] and svc2.complete_calls == []


def test_is_job_cancelled_gates_on_tracker_and_id() -> None:
    tracker = FakeTracker(cancelled=[True, False])
    mgr = make_mgr(tracker=tracker)
    assert mgr._is_job_cancelled("job-9") is True
    assert mgr._is_job_cancelled("job-8") is False
    assert tracker.cancel_checks == ["job-9", "job-8"]
    # no job id -> no tracker call at all
    assert mgr._is_job_cancelled(None) is False
    assert tracker.cancel_checks == ["job-9", "job-8"]
    # no tracker -> False even with an id
    plain = make_mgr()
    assert plain._is_job_cancelled("job-7") is False


# ---------------------------------------------------------------------------
# _update_job_progress / _complete_job / _fail_job (tracker vs legacy)
# ---------------------------------------------------------------------------


def test_progress_prefers_tracker_and_skips_legacy() -> None:
    """Tracker wins when BOTH channels are configured - and when only the
    tracker OBJECT is set (id None) the legacy channel must still run."""
    tracker, svc = FakeTracker(), FakeJobService()
    mgr = make_mgr(tracker=tracker)
    run(mgr._update_job_progress("tk-9", svc, "js-1", 55, "mid"))
    assert tracker.progress_calls == [("tk-9", 55, "mid")]
    assert svc.progress_calls == []
    # tracker present but NO tracker id -> legacy branch
    tracker2, svc2 = FakeTracker(), FakeJobService()
    mgr2 = make_mgr(tracker=tracker2)
    run(mgr2._update_job_progress(None, svc2, "js-2", 12, "lo"))
    assert tracker2.progress_calls == []
    assert svc2.progress_calls == [("js-2", 12, "lo")]
    # neither channel -> silent no-op (no exception)
    run(mgr._update_job_progress(None, FakeJobService(), None, 1, "x"))


def test_progress_tracker_call_signature_is_exact() -> None:
    """Deletion arms (drop-job_id / drop-progress / trailing-comma) hit
    TypeError on the pinned fake signature; None-swaps die on the tuple."""
    tracker = FakeTracker()
    mgr = make_mgr(tracker=tracker)
    run(mgr._update_job_progress("tk-1", None, None, 33, "third"))
    assert tracker.progress_calls == [("tk-1", 33, "third")]


def test_legacy_progress_only_when_both_legacy_parts_exist() -> None:
    svc = FakeJobService()
    mgr = make_mgr()
    run(mgr._update_job_progress(None, svc, "js-3", 44, "four"))
    assert svc.progress_calls == [("js-3", 44, "four")]
    # service present but NO job id -> no call (the `and job_id` half)
    svc2 = FakeJobService()
    run(mgr._update_job_progress(None, svc2, None, 45, "five"))
    assert svc2.progress_calls == []
    # job id present but NO service -> no call (the `and job_service` half;
    # an or-gate mutant raises AttributeError on None.update_progress)
    run(mgr._update_job_progress(None, None, "js-4", 46, "six"))


def test_complete_job_channels_are_exact() -> None:
    tracker, svc = FakeTracker(), FakeJobService()
    mgr = make_mgr(tracker=tracker)
    result = {"event_id": "e1", "overall_quality_score": 0.9}
    run(mgr._complete_job("tk-c", svc, "js-c", result))
    assert tracker.complete_calls == [("tk-c", result)]
    assert svc.complete_calls == []
    # tracker id missing -> legacy receives the SAME result object
    tracker2, svc2 = FakeTracker(), FakeJobService()
    mgr2 = make_mgr(tracker=tracker2)
    run(mgr2._complete_job(None, svc2, "js-d", result))
    assert tracker2.complete_calls == []
    assert svc2.complete_calls == [("js-d", result)]
    # no channels at all -> silent
    run(mgr._complete_job(None, None, None, result))


def test_complete_job_legacy_signature_is_pinned() -> None:
    svc = FakeJobService()
    mgr = make_mgr()
    run(mgr._complete_job(None, svc, "js-e", {"a": 1}))
    assert svc.complete_calls == [("js-e", {"a": 1})]
    # result=None swap would record ("js-e", None) - assert it did not
    svc2 = FakeJobService()
    run(mgr._complete_job(None, svc2, "js-f", {"b": 2}))
    assert svc2.complete_calls == [("js-f", {"b": 2})]


def test_fail_job_channels_are_exact() -> None:
    tracker, svc = FakeTracker(), FakeJobService()
    mgr = make_mgr(tracker=tracker)
    run(mgr._fail_job("tk-f", svc, "js-f", "boom-tracker"))
    assert tracker.fail_calls == [("tk-f", "boom-tracker")]
    assert svc.fail_calls == []
    tracker2, svc2 = FakeTracker(), FakeJobService()
    mgr2 = make_mgr(tracker=tracker2)
    run(mgr2._fail_job(None, svc2, "js-g", "boom-legacy"))
    assert tracker2.fail_calls == []
    assert svc2.fail_calls == [("js-g", "boom-legacy")]
    run(mgr._fail_job(None, None, None, "nowhere"))


def test_fail_job_legacy_signature_is_pinned() -> None:
    svc = FakeJobService()
    mgr = make_mgr()
    run(mgr._fail_job(None, svc, "js-h", "kaput"))
    assert svc.fail_calls == [("js-h", "kaput")]
    # error None-swap must NOT sneak through as a recorded None
    svc2 = FakeJobService()
    run(mgr._fail_job(None, svc2, "js-i", "second"))
    assert svc2.fail_calls == [("js-i", "second")]


# ---------------------------------------------------------------------------
# is_gpu_idle / _are_queues_empty / can_process_evaluation
# ---------------------------------------------------------------------------


def test_is_gpu_idle_boundary_and_log_are_exact() -> None:
    mgr = make_mgr(gpu=FakeGpu([{"gpu_utilization": 20}]))
    with logcap() as cap:
        assert run(mgr.is_gpu_idle()) is True
    assert cap.msgs() == ["GPU utilization: 20%, threshold: 20%, idle: True"]
    mgr2 = make_mgr(gpu=FakeGpu([{"gpu_utilization": 21}]))
    with logcap() as cap2:
        assert run(mgr2.is_gpu_idle()) is False
    assert cap2.msgs() == ["GPU utilization: 21%, threshold: 20%, idle: False"]
    mgr3 = make_mgr(gpu=FakeGpu([{"gpu_utilization": 15}]), threshold=30)
    with logcap() as cap3:
        assert run(mgr3.is_gpu_idle()) is True
    assert cap3.msgs() == ["GPU utilization: 15%, threshold: 30%, idle: True"]


def test_is_gpu_idle_missing_utilization_is_not_idle() -> None:
    mgr = make_mgr(gpu=FakeGpu([{}, {"other": 1}]))
    with logcap() as cap:
        assert run(mgr.is_gpu_idle()) is False
    assert cap.msgs() == ["GPU utilization data unavailable, assuming not idle"]
    with logcap() as cap2:
        assert run(mgr.is_gpu_idle()) is False
    assert cap2.msgs() == ["GPU utilization data unavailable, assuming not idle"]
    # utilization EXPLICITLY None hits the same arm
    mgr2 = make_mgr(gpu=FakeGpu([{"gpu_utilization": None}]))
    with logcap() as cap3:
        assert run(mgr2.is_gpu_idle()) is False
    assert cap3.msgs() == ["GPU utilization data unavailable, assuming not idle"]


def test_is_gpu_idle_monitor_failure_is_not_idle() -> None:
    mgr = make_mgr(gpu=FakeGpu([("raise", RuntimeError("nvidia-smi gone"))]))
    with logcap() as cap:
        assert run(mgr.is_gpu_idle()) is False
    assert cap.msgs() == ["Failed to check GPU idle status: nvidia-smi gone"]


def test_queues_empty_requires_both_names_in_order() -> None:
    redis = FakeRedis()
    mgr = make_mgr(redis)
    with logcap() as cap:
        assert run(mgr._are_queues_empty()) is True
    assert cap.msgs() == []
    assert redis.names == ["detection_queue", "analysis_queue"]


def test_queues_nonempty_short_circuit_first_check() -> None:
    redis = FakeRedis({"detection_queue": 1})
    mgr = make_mgr(redis)
    with logcap() as cap:
        assert run(mgr._are_queues_empty()) is False
    assert cap.msgs() == ["Detection queue has 1 items, skipping evaluation"]
    assert redis.names == ["detection_queue"], "must not peek at analysis"


def test_queues_analysis_gate_is_one_item() -> None:
    redis = FakeRedis({"analysis_queue": 1})
    mgr = make_mgr(redis)
    with logcap() as cap:
        assert run(mgr._are_queues_empty()) is False
    assert cap.msgs() == ["Analysis queue has 1 items, skipping evaluation"]
    assert redis.names == ["detection_queue", "analysis_queue"]
    # detection_len==1 must ALREADY block (a >1 mutant would not)
    redis2 = FakeRedis({"detection_queue": 1})
    mgr2 = make_mgr(redis2)
    with logcap():
        assert run(mgr2._are_queues_empty()) is False


def test_queue_check_errors_are_conservative() -> None:
    bad = RuntimeError("redis down")
    redis = FakeRedis({}, raises={"detection_queue": bad})
    mgr = make_mgr(redis)
    with logcap() as cap:
        assert run(mgr._are_queues_empty()) is False
    assert cap.msgs() == ["Failed to check queue status: redis down"]
    assert redis.names == ["detection_queue"]
    redis2 = FakeRedis({}, raises={"analysis_queue": bad})
    mgr2 = make_mgr(redis2)
    with logcap() as cap2:
        assert run(mgr2._are_queues_empty()) is False
    assert cap2.msgs() == ["Failed to check queue status: redis down"]
    assert redis2.names == ["detection_queue", "analysis_queue"]


def test_can_process_checks_queues_before_gpu() -> None:
    redis, gpu = FakeRedis({"detection_queue": 3}), FakeGpu([{"gpu_utilization": 1}])
    mgr = make_mgr(redis, gpu)
    with logcap():
        assert run(mgr.can_process_evaluation()) is False
    assert gpu.calls == 0, "queues block BEFORE the GPU is consulted"
    # all clear -> True, gpu consulted exactly once
    redis2, gpu2 = FakeRedis(), FakeGpu([{"gpu_utilization": 5}])
    mgr2 = make_mgr(redis2, gpu2)
    with logcap():
        assert run(mgr2.can_process_evaluation()) is True
    assert gpu2.calls == 1
    assert redis2.names == ["detection_queue", "analysis_queue"]
    # idle queues + busy GPU -> False
    gpu3 = FakeGpu([{"gpu_utilization": 90}])
    mgr3 = make_mgr(FakeRedis(), gpu3)
    with logcap():
        assert run(mgr3.can_process_evaluation()) is False


# ---------------------------------------------------------------------------
# singleton gateway
# ---------------------------------------------------------------------------


def test_singleton_factory_passes_every_argument() -> None:
    be.reset_background_evaluator()
    redis, gpu, queue, audit = FakeRedis(), FakeGpu(), FakeQueue(), FakeAudit()
    mgr = be.get_background_evaluator(
        redis,
        gpu,
        queue,
        audit,
        gpu_idle_threshold=7,
        idle_duration_required=11,
        poll_interval=2.5,
        enabled=False,
    )
    assert isinstance(mgr, be.BackgroundEvaluator)
    assert mgr._redis is redis
    assert mgr._gpu_monitor is gpu
    assert mgr._evaluation_queue is queue
    assert mgr._audit_service is audit
    assert mgr.gpu_idle_threshold == 7
    assert mgr.idle_duration_required == 11
    assert mgr.poll_interval == 2.5
    assert mgr.enabled is False
    again = be.get_background_evaluator(FakeRedis(), FakeGpu(), FakeQueue(), FakeAudit())
    assert again is mgr, "second call must return the SAME singleton"
    be.reset_background_evaluator()
    fresh = be.get_background_evaluator(FakeRedis(), FakeGpu(), FakeQueue(), FakeAudit())
    assert fresh is not mgr, "reset must drop the cached singleton"
    assert fresh.gpu_idle_threshold == 20, "defaults apply on a fresh singleton"
    be.reset_background_evaluator()


def stmt_text(stmt: Any) -> str:
    """Render a statement for shape asserts: the SQL text enumerates the
    SELECTed columns, so a dropped undefer() (deferred column falls out
    of the SELECT) and a flipped WHERE both die on this string."""
    return str(stmt)


# ---------------------------------------------------------------------------
# process_one - queue-empty and the full tracker path
# ---------------------------------------------------------------------------


def test_process_one_empty_queue_is_silent_false() -> None:
    mgr = make_mgr(queue=FakeQueue([]))
    sess = FakeSessionFactory()
    with patched(be, "get_session", sess), logcap() as cap:
        assert run(mgr.process_one()) is False
    assert cap.msgs() == []
    assert sess.calls == 0


def _tracker_happy():
    """One full tracker-mode round with EVERY observable recorded."""
    event, audit_row = make_event("evt-1"), make_audit("evt-1", 0.87)
    tracker = FakeTracker()
    audit_svc = FakeAudit()
    queue = FakeQueue(["evt-1"])
    made: list[Any] = []
    sess = FakeSessionFactory(scalars=[event, audit_row])

    def factory(redis_client: Any) -> FakeJobService:
        made.append(redis_client)
        return FakeJobService()

    mgr = make_mgr(queue=queue, audit=audit_svc, tracker=tracker)
    with (
        patched(be, "get_session", sess),
        patched(be, "get_job_status_service", factory),
        logcap() as cap,
    ):
        outcome = run(mgr.process_one())
    return outcome, tracker, audit_svc, sess, made, cap, event, audit_row


def test_process_one_tracker_happy_path_every_observable() -> None:
    outcome, tracker, audit_svc, sess, made, cap, event, audit_row = _tracker_happy()
    assert outcome is True
    assert made == [], "tracker mode must never build the legacy service"
    assert tracker.create_calls == ["evaluation"]
    assert tracker.start_calls == [("tk-1", "Processing evaluation for event evt-1")]
    assert tracker.progress_calls == [
        ("tk-1", 10, "Fetching event data"),
        ("tk-1", 25, "Fetching audit record"),
        ("tk-1", 40, "Running AI evaluation"),
    ]
    assert tracker.complete_calls == [
        ("tk-1", {"event_id": "evt-1", "overall_quality_score": 0.87})
    ]
    assert tracker.fail_calls == []
    # LLM call ran on the EXPUNGED pair (identities, not stand-ins)
    assert audit_svc.calls == [(audit_row, event)]
    # two sessions; the read session expunges BOTH rows (identity, not a
    # stand-in), the write session merges the audit exactly once
    assert sess.calls == 2
    assert sess.sessions[0].expunged == [event, audit_row]
    assert len(sess.sessions[0].expunged) == 2, "expunge() must fire twice"
    assert sess.all_merged == [audit_row]
    # statements keep BOTH undeferred columns and the identity WHEREs
    s0, s1 = (stmt_text(st) for st in sess.all_executed)
    assert "events.llm_prompt" in s0 and "events.reasoning" in s0
    assert "WHERE events.id = :" in s0 and "!=" not in s0
    assert "WHERE event_audits.event_id = :" in s1 and "!=" not in s1
    # whole log sequence, both records carry their extra= fields
    assert cap.msgs() == [
        "Processing background evaluation for event evt-1",
        "Completed background evaluation for event evt-1",
    ]
    r0 = cap.one("Processing background evaluation for event evt-1")
    assert r0.levelno == logging.INFO
    assert r0.event_id == "evt-1"
    r1 = cap.one("Completed background evaluation for event evt-1")
    assert r1.event_id == "evt-1"
    assert r1.overall_quality_score == 0.87


def test_process_one_legacy_happy_path_every_observable() -> None:
    event, audit_row = make_event("evt-2"), make_audit("evt-2", 0.5)
    svc = FakeJobService(job_id="js-9")
    made: list[Any] = []
    audit_svc = FakeAudit()
    queue = FakeQueue(["evt-2"])
    sess = FakeSessionFactory(scalars=[event, audit_row])

    def factory(redis_client: Any) -> FakeJobService:
        made.append(redis_client)
        return svc

    mgr = make_mgr(queue=queue, audit=audit_svc)
    with (
        patched(be, "get_session", sess),
        patched(be, "get_job_status_service", factory),
        logcap() as cap,
    ):
        assert run(mgr.process_one()) is True
    assert made == [mgr._redis]
    assert svc.start_kwargs == [
        {
            "job_id": "evaluation-evt-2",
            "job_type": "background_evaluation",
            "metadata": {"event_id": "evt-2"},
        }
    ]
    assert svc.progress_calls == [
        ("js-9", 10, "Fetching event data"),
        ("js-9", 25, "Fetching audit record"),
        ("js-9", 40, "Running AI evaluation"),
    ]
    assert svc.complete_calls == [("js-9", {"event_id": "evt-2", "overall_quality_score": 0.5})]
    assert svc.fail_calls == []
    assert audit_svc.calls == [(audit_row, event)]
    assert sess.calls == 2
    assert sess.all_merged == [audit_row]
    assert cap.msgs() == [
        "Processing background evaluation for event evt-2",
        "Completed background evaluation for event evt-2",
    ]
    s0, _s1 = (stmt_text(st) for st in sess.all_executed)
    assert "llm_prompt" in s0 and "reasoning" in s0, "same reads, legacy mode"


def test_process_one_cancelled_job_returns_true_without_work() -> None:
    tracker = FakeTracker(cancelled=[True])
    queue = FakeQueue(["evt-3"])
    audit_svc = FakeAudit()
    sess = FakeSessionFactory()
    mgr = make_mgr(queue=queue, audit=audit_svc, tracker=tracker)
    with patched(be, "get_session", sess), logcap() as cap:
        assert run(mgr.process_one()) is True
    assert tracker.progress_calls == []
    assert tracker.complete_calls == []
    assert tracker.fail_calls == []
    assert audit_svc.calls == []
    assert sess.calls == 0
    assert cap.msgs() == [
        "Processing background evaluation for event evt-3",
        "Job tk-1 was cancelled, skipping event evt-3",
    ]


def test_event_not_found_completes_skipped_in_tracker_mode() -> None:
    tracker = FakeTracker()
    queue = FakeQueue(["evt-4"])
    audit_svc = FakeAudit()
    sess = FakeSessionFactory(scalars=[None])
    svc_holder: list[FakeJobService] = []

    def factory(redis_client: Any) -> FakeJobService:
        svc = FakeJobService()
        svc_holder.append(svc)
        return svc

    mgr = make_mgr(queue=queue, audit=audit_svc, tracker=tracker)
    with (
        patched(be, "get_session", sess),
        patched(be, "get_job_status_service", factory),
        logcap() as cap,
    ):
        assert run(mgr.process_one()) is True
    assert tracker.complete_calls == [("tk-1", {"skipped": True, "reason": "event_not_found"})]
    assert tracker.fail_calls == []
    assert audit_svc.calls == []
    assert sess.calls == 1 and sess.all_merged == []
    assert cap.msgs() == [
        "Processing background evaluation for event evt-4",
        "Event evt-4 not found in database, skipping evaluation",
    ]
    rec = cap.one("Event evt-4 not found in database, skipping evaluation")
    assert rec.levelno == logging.WARNING
    assert rec.event_id == "evt-4"


def test_event_not_found_fails_the_legacy_job() -> None:
    svc = FakeJobService(job_id="js-nf")
    queue = FakeQueue(["evt-5"])
    sess = FakeSessionFactory(scalars=[None])

    def factory(redis_client: Any) -> FakeJobService:
        return svc

    mgr = make_mgr(queue=queue)
    with (
        patched(be, "get_session", sess),
        patched(be, "get_job_status_service", factory),
        logcap() as cap,
    ):
        assert run(mgr.process_one()) is True
    assert svc.progress_calls == [("js-nf", 10, "Fetching event data")]
    assert svc.fail_calls == [("js-nf", "Event evt-5 not found")]
    assert svc.complete_calls == []
    assert cap.msgs() == [
        "Processing background evaluation for event evt-5",
        "Event evt-5 not found in database, skipping evaluation",
    ]


def test_audit_missing_fails_job_and_keeps_progress_prefix() -> None:
    event = make_event("evt-6")
    tracker = FakeTracker()
    queue = FakeQueue(["evt-6"])
    audit_svc = FakeAudit()
    sess = FakeSessionFactory(scalars=[event, None])
    mgr = make_mgr(queue=queue, audit=audit_svc, tracker=tracker)
    with patched(be, "get_session", sess), logcap() as cap:
        assert run(mgr.process_one()) is True
    assert tracker.progress_calls == [
        ("tk-1", 10, "Fetching event data"),
        ("tk-1", 25, "Fetching audit record"),
    ]
    assert tracker.fail_calls == [("tk-1", "No audit record for event evt-6")]
    assert tracker.complete_calls == []
    assert audit_svc.calls == []
    assert sess.calls == 1
    assert cap.msgs() == [
        "Processing background evaluation for event evt-6",
        "No audit record for event evt-6, skipping evaluation",
    ]
    rec = cap.one("No audit record for event evt-6, skipping evaluation")
    assert rec.levelno == logging.WARNING
    assert rec.event_id == "evt-6"


def test_llm_failure_lands_in_the_except_path() -> None:
    event, audit_row = make_event("evt-7"), make_audit("evt-7")
    tracker = FakeTracker()
    audit_svc = FakeAudit(raises=RuntimeError("llm down"))
    queue = FakeQueue(["evt-7"])
    sess = FakeSessionFactory(scalars=[event, audit_row])
    mgr = make_mgr(queue=queue, audit=audit_svc, tracker=tracker)
    with patched(be, "get_session", sess), logcap() as cap:
        assert run(mgr.process_one()) is True
    assert tracker.fail_calls == [("tk-1", "llm down")]
    assert tracker.complete_calls == []
    # the write session was NEVER opened (the LLM call died first)
    assert sess.calls == 1
    assert cap.msgs() == [
        "Processing background evaluation for event evt-7",
        "Failed to process evaluation for event evt-7: llm down",
    ]
    rec = cap.one("Failed to process evaluation for event evt-7: llm down")
    assert rec.levelno == logging.ERROR
    assert rec.event_id == "evt-7"
    assert rec.error == "llm down"
    assert rec.exc_info is not None, "the except path must log with exc_info"


def test_session_red_failure_also_reaches_the_except_path() -> None:
    """execute() raising (a mutated statement the fake can still see)
    fails the job with the SAME except-path shape."""
    tracker = FakeTracker()
    queue = FakeQueue(["evt-8"])
    sess = FakeSessionFactory(scalars=[("raise", RuntimeError("db gone"))])
    mgr = make_mgr(queue=queue, tracker=tracker)
    with patched(be, "get_session", sess), logcap() as cap:
        assert run(mgr.process_one()) is True
    assert tracker.fail_calls == [("tk-1", "db gone")]
    assert tracker.progress_calls == [("tk-1", 10, "Fetching event data")]
    assert cap.msgs() == [
        "Processing background evaluation for event evt-8",
        "Failed to process evaluation for event evt-8: db gone",
    ]
    assert cap.one("Failed to process evaluation for event evt-8: db gone").exc_info is not None


# ---------------------------------------------------------------------------
# _run_loop - the scripted-clock engine (idle math, exits, error arms)
# ---------------------------------------------------------------------------


def stopper(mgr: Any):
    def _stop(_sleeper: Any) -> None:
        mgr.running = False

    return _stop


def test_run_loop_arms_the_timer_then_processes_exactly_at_the_boundary() -> None:
    """Scripted clock 100 -> 105 with required=5: pass 1 arms the idle
    timer and WAITS (0 < 5), pass 2 hits `>= 5` EXACTLY and processes
    once. Kills `>=`->`>` (would wait: 0 dequeues) and `now - _idle_since`
    -> `+` (200 >= 5 processes on pass 1: 2 dequeues)."""
    gpu = FakeGpu([{"gpu_utilization": 5}])
    queue = FakeQueue(["evt-L1"])
    tracker = FakeTracker(cancelled=[True])  # process_one returns True fast
    mgr = make_mgr(gpu=gpu, queue=queue, tracker=tracker, duration=5, poll=1.0)
    sess = FakeSessionFactory()
    mgr.running = True
    clock, sleeper = FakeTime([100.0, 105.0]), Sleeper([None, stopper(mgr)])

    async def main() -> None:
        await mgr._run_loop()

    with (
        patched(be, "time", clock),
        patched(be.asyncio, "sleep", sleeper),
        patched(be, "get_session", sess),
        logcap() as cap,
    ):
        run(main())
    assert mgr._idle_since == 100.0
    assert sleeper.slept == [1.0, 1.0]
    assert queue.dequeues == 1
    assert tracker.start_calls == [("tk-1", "Processing evaluation for event evt-L1")]
    assert cap.msgs().count("GPU became idle, starting idle timer") == 1


def test_run_loop_waits_below_the_duration_and_resets_when_busy() -> None:
    """100 -> 104.9 is idle 4.9 < 5: NO processing, and the third pass
    (busy GPU) runs the reset branch: timer cleared + reset line logged
    (an `is None` gate mutant never logs; the cold-start test below shows
    it must NOT log when nothing was armed)."""
    gpu = FakeGpu([{"gpu_utilization": 5}, {"gpu_utilization": 5}, {"gpu_utilization": 99}])
    queue = FakeQueue(["evt-L3"])
    tracker = FakeTracker()
    mgr = make_mgr(gpu=gpu, queue=queue, tracker=tracker, duration=5, poll=1.0)
    mgr.running = True
    clock, sleeper = FakeTime([100.0, 104.9]), Sleeper([None, None, stopper(mgr)])

    async def main() -> None:
        await mgr._run_loop()

    with (
        patched(be, "time", clock),
        patched(be.asyncio, "sleep", sleeper),
        logcap() as cap,
    ):
        run(main())
    assert queue.dequeues == 0
    assert tracker.start_calls == []
    assert mgr._idle_since is None, "a busy GPU must RESET the idle timer"
    assert sleeper.slept == [1.0, 1.0, 1.0]
    assert cap.msgs() == [
        "Background evaluator loop started",
        "GPU utilization: 5%, threshold: 20%, idle: True",
        "GPU became idle, starting idle timer",
        "GPU idle for 0.0s, waiting for 5s",
        "GPU utilization: 5%, threshold: 20%, idle: True",
        "GPU idle for 4.9s, waiting for 5s",
        "GPU utilization: 99%, threshold: 20%, idle: False",
        "GPU no longer idle, resetting timer",
        "Background evaluator loop stopped",
    ]


def test_run_loop_reset_branch_is_silent_on_a_cold_start() -> None:
    """Busy GPU with NO timer armed: the reset branch's `is not None`
    half keeps the reset line silent (the `is None` mutant logs here)."""
    gpu = FakeGpu([{"gpu_utilization": 99}])
    mgr = make_mgr(gpu=gpu, poll=1.0)
    mgr.running = True
    sleeper = Sleeper([None, stopper(mgr)])

    async def main() -> None:
        await mgr._run_loop()

    with (
        patched(be, "time", FakeTime([0.0])),
        patched(be.asyncio, "sleep", sleeper),
        logcap() as cap,
    ):
        run(main())
    assert cap.msgs() == [
        "Background evaluator loop started",
        "GPU utilization: 99%, threshold: 20%, idle: False",
        "GPU utilization: 99%, threshold: 20%, idle: False",
        "Background evaluator loop stopped",
    ]
    assert mgr._idle_since is None


def test_run_loop_disabled_flag_skips_checks_but_keeps_polling() -> None:
    """enabled=False: can_process is never consulted (GPU untouched), the
    idle timer stays None, polling continues at poll_interval."""
    gpu = FakeGpu([{"gpu_utilization": 1}])
    mgr = make_mgr(gpu=gpu, enabled=False, poll=3.0)
    mgr.running = True
    sleeper = Sleeper([None, None, stopper(mgr)])

    async def main() -> None:
        await mgr._run_loop()

    with (
        patched(be, "time", FakeTime([0.0])),
        patched(be.asyncio, "sleep", sleeper),
        logcap() as cap,
    ):
        run(main())
    assert gpu.calls == 0
    assert sleeper.slept == [3.0, 3.0, 3.0]
    assert mgr._idle_since is None
    assert cap.msgs() == [
        "Background evaluator loop started",
        "Background evaluator loop stopped",
    ]


def test_run_loop_processed_and_empty_queue_debug_lines_pair() -> None:
    """duration=0 processes on the FIRST pass: round 1 takes a real event
    (processed=True -> 'continuing loop'), round 2 finds the queue empty
    ('queue is empty') - each EXACTLY once across three passes."""
    gpu = FakeGpu([{"gpu_utilization": 0}])
    queue = FakeQueue(["evt-P", None])
    tracker = FakeTracker(cancelled=[True])
    mgr = make_mgr(gpu=gpu, queue=queue, tracker=tracker, duration=0, poll=1.0)
    sess = FakeSessionFactory()
    mgr.running = True
    clock, sleeper = FakeTime([0.0, 0.0]), Sleeper([None, stopper(mgr)])

    async def main() -> None:
        await mgr._run_loop()

    with (
        patched(be, "time", clock),
        patched(be.asyncio, "sleep", sleeper),
        patched(be, "get_session", sess),
        logcap() as cap,
    ):
        run(main())
    assert cap.msgs().count("Processed one evaluation, continuing loop") == 1
    assert cap.msgs().count("Evaluation queue is empty") == 1
    assert cap.msgs().count("GPU became idle, starting idle timer") == 1
    assert sleeper.slept == [1.0, 1.0]


def test_run_loop_survives_errors_and_continues() -> None:
    """The error arm: the poll sleep raises a plain Exception on pass 1 -
    the loop LOGS it with exc_info, sleeps poll_interval again and runs
    on (a bare re-raise would escape run(); an arm that stops sleeping
    would trip the sleeper cap = LoopKill BaseException)."""
    gpu = FakeGpu([{"gpu_utilization": 99}])
    mgr = make_mgr(gpu=gpu, poll=4.0)
    mgr.running = True
    sleeper = Sleeper([("raise", RuntimeError("stats exploded")), stopper(mgr)])

    async def main() -> None:
        await mgr._run_loop()

    with (
        patched(be, "time", FakeTime([0.0])),
        patched(be.asyncio, "sleep", sleeper),
        logcap() as cap,
    ):
        run(main())
    assert sleeper.slept == [4.0, 4.0], "error arm sleeps, then the normal poll"
    err = cap.one("Error in background evaluator loop: stats exploded")
    assert err.levelno == logging.ERROR
    assert err.exc_info is not None
    assert cap.msgs() == [
        "Background evaluator loop started",
        "GPU utilization: 99%, threshold: 20%, idle: False",
        "Error in background evaluator loop: stats exploded",
        "Background evaluator loop stopped",
    ]


def test_run_loop_error_arm_writes_the_traceback_and_the_poll_arg() -> None:
    """The error arm's OWN sleep: a sleep(NONE) mutant must die on the
    recorded delay, and exc_info=False / dropped would leave
    record.exc_info None (the True mutant keeps the traceback object)."""
    gpu = FakeGpu([{"gpu_utilization": 99}])
    mgr = make_mgr(gpu=gpu, poll=2.0)
    mgr.running = True
    sleeper = Sleeper([("raise", ValueError("boom2")), stopper(mgr)])

    async def main() -> None:
        await mgr._run_loop()

    with (
        patched(be, "time", FakeTime([0.0])),
        patched(be.asyncio, "sleep", sleeper),
        logcap() as cap,
    ):
        run(main())
    assert sleeper.slept == [2.0, 2.0]
    err = cap.one("Error in background evaluator loop: boom2")
    assert err.exc_info is not None and err.exc_info[0] is ValueError


def test_run_loop_cancellation_logs_and_breaks_cleanly() -> None:
    """CancelledError on the sleep: exit through the break - the STOPPED
    line must STILL log (a return-instead-of-break skips it; a bare
    re-raise would surface out of asyncio.run)."""
    gpu = FakeGpu([{"gpu_utilization": 99}])
    mgr = make_mgr(gpu=gpu, poll=1.0)
    mgr.running = True
    sleeper = Sleeper([("raise", asyncio.CancelledError())])

    async def main() -> None:
        await mgr._run_loop()

    with (
        patched(be, "time", FakeTime([0.0])),
        patched(be.asyncio, "sleep", sleeper),
        logcap() as cap,
    ):
        run(main())
    assert cap.msgs() == [
        "Background evaluator loop started",
        "GPU utilization: 99%, threshold: 20%, idle: False",
        "Background evaluator loop cancelled",
        "Background evaluator loop stopped",
    ]


def test_run_loop_polls_the_configured_interval_and_none_is_fatal() -> None:
    """The normal-arm sleep receives EXACTLY poll_interval (the None-swap
    and drop mutants record None/missing - the real loop would die on
    sleep(None) at the first non-idle pass)."""
    gpu = FakeGpu([{"gpu_utilization": 99}])
    mgr = make_mgr(gpu=gpu, poll=7.5)
    mgr.running = True
    sleeper = Sleeper([None, stopper(mgr)])

    async def main() -> None:
        await mgr._run_loop()

    with patched(be, "time", FakeTime([0.0])), patched(be.asyncio, "sleep", sleeper):
        run(main())
    assert sleeper.slept == [7.5, 7.5]


def test_run_loop_cannot_be_driven_without_the_sleep_patch() -> None:
    """Sanity guard for the harness itself: with the REAL asyncio.sleep a
    poll_interval of 0.05 is what a shipped-code control run would pay -
    this test just proves the patched shape above is load-bearing."""
    mgr = make_mgr(gpu=FakeGpu([{"gpu_utilization": 99}]), poll=0.001)

    async def main() -> None:
        mgr.running = True

        async def tiny_sleep(_d: float) -> None:
            mgr.running = False
            await _REAL_SLEEP(0)

        with patched(be.asyncio, "sleep", tiny_sleep):
            await mgr._run_loop()

    run(main())
    assert mgr.running is False


# ---------------------------------------------------------------------------
# start / stop lifecycle
# ---------------------------------------------------------------------------


def test_start_creates_a_named_task_and_flips_running() -> None:
    mgr = make_mgr(poll=1.0)

    async def main() -> None:
        with logcap() as cap:
            await mgr.start()
            task = mgr._task
            assert task is not None
            assert task.get_name() == "background-evaluator"
            assert mgr.running is True
            assert not task.done()
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        assert cap.msgs() == ["Starting background evaluator", "Background evaluator started"]

    run(main())


def test_start_twice_is_a_no_op() -> None:
    mgr = make_mgr(poll=1.0)

    async def main() -> None:
        await mgr.start()
        first = mgr._task
        with logcap() as cap:
            await mgr.start()
        assert mgr._task is first, "a second start must not replace the task"
        assert cap.msgs() == ["BackgroundEvaluator already running"]
        first.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await first

    run(main())


def test_start_when_disabled_touches_nothing() -> None:
    mgr = make_mgr(enabled=False)

    async def main() -> None:
        with logcap() as cap:
            await mgr.start()
        assert mgr.running is False
        assert mgr._task is None
        assert cap.msgs() == ["BackgroundEvaluator is disabled, not starting"]

    run(main())


class FakeTask:
    """Stand-in with a recording cancel() - a DONE task must never be
    cancelled, so both gate arms (`self._task or` and the flipped
    `not done()`) become observable on the cancel count, not just the
    cleared fields."""

    def __init__(self, done: bool = False) -> None:
        self.cancels = 0
        self._done = done

    def done(self) -> bool:
        return self._done

    def cancel(self) -> None:
        self.cancels += 1
        self._done = True

    def __await__(self):
        async def _immediate() -> None:
            return None

        return _immediate().__await__()


def test_stop_cancels_a_live_parked_task() -> None:
    """A genuinely PENDING task: the `task and not done()` gate must
    cancel it. (The real-task variant runs via asyncio in the sibling
    test below; this shape pins the OBSERVABLE cancel.)"""
    mgr = make_mgr()
    task = FakeTask(done=False)
    mgr.running = True
    mgr._task = task
    mgr._idle_since = 123.45
    with logcap() as cap:
        run(mgr.stop())
    assert task.cancels == 1, "a live task must be cancelled"
    assert mgr.running is False
    assert mgr._idle_since is None
    assert mgr._task is None
    assert cap.msgs() == ["Stopping background evaluator", "Background evaluator stopped"]


def test_stop_on_a_done_task_skips_the_cancel_branch() -> None:
    """A COMPLETED task: the `not done()` half must SKIP cancel() (the
    `or` mutant and the flipped gate both cancel - observable count 0)."""
    mgr = make_mgr()
    task = FakeTask(done=True)
    mgr.running = True
    mgr._task = task
    with logcap() as cap:
        run(mgr.stop())
    assert task.cancels == 0, "a done task must not be cancelled"
    assert mgr._task is None and mgr.running is False
    assert cap.msgs() == ["Stopping background evaluator", "Background evaluator stopped"]


def test_stop_cancels_a_real_pending_task_end_to_end() -> None:
    """The asyncio-shaped version: a parked event-wait task, stopped
    through the real stop() - the task ends CANCELLED and state clears."""
    mgr = make_mgr(poll=30.0)

    async def main() -> None:
        gate = asyncio.Event()

        async def parked() -> None:
            await gate.wait()

        mgr.running = True
        task = asyncio.create_task(parked())
        mgr._task = task
        with logcap() as cap:
            await mgr.stop()
        assert task.cancelled(), "stop() must cancel a pending task"
        assert mgr._task is None and mgr.running is False
        assert cap.msgs() == [
            "Stopping background evaluator",
            "Background evaluator stopped",
        ]

    run(main())


def test_stop_when_not_running_is_silent() -> None:
    mgr = make_mgr()

    async def main() -> None:
        with logcap() as cap:
            await mgr.stop()
        assert cap.msgs() == ["BackgroundEvaluator not running, nothing to stop"]
        assert mgr._task is None and mgr._idle_since is None

    run(main())
