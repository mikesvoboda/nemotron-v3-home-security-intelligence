# TARGET-MODULE: backend.services.cleanup_service
"""Campaign #11 battery L: kill-real for backend/services/cleanup_service.py.

337 survivor keys, 344/681 = 50.51% module kt before this battery (M12 bank).
The shipped suites drive run_cleanup/dry_run_cleanup through AsyncMock
sessions that accept ANY argument, never wire a job service (the Redis
job-tracking block is never entered), and assert only stats RETURN values --
so the execute(statement) ARGUMENT family (None-substituted/dropped
statements, where(None), select(None), < vs <=, naive-tz cutoff,
plus-timedelta cutoff), the job-service/tracker call-argument family
(None-shifted/dropped/+1 args, XX- and case-wrapped messages, guard twins),
the log-record family (message None/XX/case, exc_info None/dropped/False)
and the control-flow family (continue->break, break->return, > -> >= and >1,
signature default True->False, += 1 -> = 1) all survive. This battery:

  * digests every session.execute/stream_scalars argument AT CALL TIME in
    the mutant world -- (class, table, whitespace-normalized SQL, sorted
    reprs of compile().params, column_descriptions (name, key) pairs) -- and
    asserts them EQUAL to digests recomputed at import in the test world
    over identically built statements. Value identity, never mock-accepts-
    anything call_args. Verified empirically against this venv's SQLAlchemy
    at authoring: select(None, col)/select(col, None) surface ('_no_label',
    None) in column_descriptions; compile().params carries the cutoff VALUE;
    str(stmt) renders '<' vs '<='; where(None) renders 'WHERE NULL'.
  * swaps cs.datetime with a tz-recording fake clock (module-global swap
    spanning the whole awaited call -- await-time-getter rule) so the job-id
    strftime payload is EXACT, the cutoff is exact, and datetime.now(None)
    mutants show twice: in the recorded tz list AND in params reprs (naive
    vs +00:00).
  * swaps cs.asyncio with a shim (real CancelledError kept) to observe
    sleep() args and create_task(name=...) -- _cleanup_loop's 60s retry and
    start's task name are otherwise unobservable.
  * drives the tracked paths WITH job services in BOTH job_id polarities
    (start_job returns a job id / None) and asserts the COMPLETE ordered call
    list; every guard twin lands RED in one polarity, and the exception path
    indexes the exc_info TUPLE -- 'is not None' would pass the exc_info=False
    mutant, indexing reddens the None/dropped/False family.
  * captures through the module logger with propagate=False and asserts
    EXACT ordered (level, message) lists -- message EQUALITY kills the None/
    XX/case variants a fragment assert passes (memory: no fragment/count
    asserts).
  * swaps cs.Path to subclasses whose unlink()/stat() raise on one marked
    name -- the failure branches of _delete_file/_delete_orphaned_files/
    _scan_storage_directories become deterministic (the sanctioned pattern of
    shipped test_cleanup_cutoff_kill).

Honesty ledger -- registered EQUIVALENTs at authoring: x_format_bytes m1/m2
(size<=0 / size<1: 0 formats "0 B" either way, negatives short-circuit to
"0 B" BEFORE the guard, positives untouched -- zero observable difference)
and run_cleanup m4 / orphaned m2 (job_id init None -> "": overwritten by
start_job when it runs; the and-guards short-circuit on job_service None /
falsy tracker otherwise -- the init value is a dead store). GREENs outside
this ledger are adjudicated BY CONSTRUCTION before registration -- diff-shape
is not a disposition. Key numbers are M12-era; a coverage-growing battery can
renumber tails -- flip adjudication goes to the body bijection.
"""

import contextlib
import logging
import tempfile
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

import backend.services.cleanup_service as cs
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.gpu_stats import GPUStats
from backend.models.log import Log

MISS = object()
PIN = datetime(2026, 9, 15, 12, 0, 0, 0, tzinfo=UTC)
PIN_A = datetime(2026, 9, 15, 12, 7, 9, 123456, tzinfo=UTC)  # nonzero sec/micro
JOBS = "cleanup-20260915-120000"
RET = 30
LOG_RET = 7
DET_CUT = PIN - timedelta(days=RET)  # 2026-08-16 12:00+00:00
LOG_CUT = PIN - timedelta(days=LOG_RET)  # 2026-09-08 12:00+00:00
NOWHERE = "/nonexistent-orphan-zz"
SLEEPS: list[object] = []
TASK_NAMES: list[object] = []

INFO = logging.INFO
WARNING = logging.WARNING
DEBUG = logging.DEBUG
ERROR = logging.ERROR


def _attempt(coro):
    """Run a coroutine to completion; battery red = ANY escaping exception."""
    import asyncio

    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# log capture -- exact ordered (level, message) lists
# ---------------------------------------------------------------------------
class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@contextlib.contextmanager
def _capture_logs():
    """Capture through the MODULE logger only; propagate=False keeps suite-
    order ambient handlers/formatters from mutating records (K-era lesson)."""
    cap = _Capture()
    handlers = cs.logger.handlers[:]
    cs.logger.handlers[:] = [cap]
    prev, prev_prop = cs.logger.level, cs.logger.propagate
    cs.logger.setLevel(logging.DEBUG)
    cs.logger.propagate = False
    try:
        yield cap
    finally:
        cs.logger.handlers[:] = handlers
        cs.logger.setLevel(prev)
        cs.logger.propagate = prev_prop


def _assert_msgs(cap, expected):
    got = [(r.levelno, r.getMessage()) for r in cap.records]
    assert got == list(expected), got


# ---------------------------------------------------------------------------
# swaps (direct module-attribute swaps, K-era pattern)
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def _attr(obj, name, value):
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield old
    finally:
        setattr(obj, name, old)


class _Settings:
    retention_days = 44
    log_retention_days = LOG_RET


@contextlib.contextmanager
def _pinned():
    """Pinned settings for BOTH construction time and call time (the
    await-time-getter rule: _count_old_logs/cleanup_old_logs read
    get_settings() INSIDE the awaited call)."""
    with _attr(cs, "get_settings", lambda: _Settings()):
        yield


class _Clock:
    """Replaces cs.datetime. now(tz) RECORDS the tz argument identity and
    returns a REAL datetime -- naive when tz is None -- so naive-vs-aware
    mutants change downstream param reprs, not just metadata."""

    def __init__(self, when: datetime) -> None:
        self.when = when
        self.tzs: list[object] = []

    def now(self, tz=MISS):
        self.tzs.append(tz)
        if tz is None or tz is MISS:
            return self.when.replace(tzinfo=None)
        return self.when

    def __getattr__(self, item):
        return getattr(datetime, item)


@contextlib.contextmanager
def _clocked(when: datetime):
    clk = _Clock(when)
    with _attr(cs, "datetime", clk):
        yield clk


def _svc(cls=None, **kw):
    with _pinned():
        return (cls or cs.CleanupService)(**kw)


def _osvc(**kw):
    with _pinned():
        return cs.OrphanedFileCleanup(**kw)


# ---------------------------------------------------------------------------
# SQL digest -- recorded in the MUTANT world, compared to the same function
# run in the TEST world over identically built statements.
# ---------------------------------------------------------------------------
def _dig(stmt):
    if stmt is None:
        return ("NONE",)
    table = getattr(getattr(stmt, "table", None), "name", None)
    try:
        sql = " ".join(str(stmt).split())
    except Exception as exc:
        sql = "RAISE:" + type(exc).__name__
    try:
        params = tuple(sorted(repr(v) for v in stmt.compile().params.values()))
    except Exception as exc:
        params = ("RAISE:" + type(exc).__name__,)
    try:
        cols = tuple(
            (d["name"], getattr(d["expr"], "key", repr(d["expr"])))
            for d in stmt.column_descriptions
        )
    except Exception as exc:
        cols = ("RAISE:" + type(exc).__name__,)
    return (type(stmt).__name__, table, sql, params, cols)


def _dig_count(col, model, cutoff):
    from sqlalchemy import func

    return _dig(select(func.count()).select_from(model).where(col < cutoff))


def _dig_model(col, model, cutoff):
    return _dig(select(model).where(col < cutoff))


def _dig_delete(model, col, cutoff):
    from sqlalchemy import delete

    return _dig(delete(model).where(col < cutoff))


DIG_DET_COUNT = _dig_count(Detection.detected_at, Detection, DET_CUT)
DIG_DET_QUERY = _dig_model(Detection.detected_at, Detection, DET_CUT)
DIG_EVT_COUNT = _dig_count(Event.started_at, Event, DET_CUT)
DIG_GPU_COUNT = _dig_count(GPUStats.recorded_at, GPUStats, DET_CUT)
DIG_DEL_DET = _dig_delete(Detection, Detection.detected_at, DET_CUT)
DIG_DEL_EVT = _dig_delete(Event, Event.started_at, DET_CUT)
DIG_DEL_GPU = _dig_delete(GPUStats, GPUStats.recorded_at, DET_CUT)
DIG_LOG_COUNT = _dig_count(Log.timestamp, Log, LOG_CUT)
DIG_DEL_LOG = _dig_delete(Log, Log.timestamp, LOG_CUT)
DIG_REF_DET = _dig(select(Detection.file_path, Detection.thumbnail_path))
DIG_REF_EVT = _dig(select(Event.clip_path).where(Event.clip_path.isnot(None)))


# ---------------------------------------------------------------------------
# recorder session + job stand-ins
# ---------------------------------------------------------------------------
class _Res:
    def __init__(self, rowcount=None, scalar=None) -> None:
        self.rowcount = rowcount
        self._scalar = scalar

    def scalar_one(self):
        return self._scalar


class _Rows:
    def __init__(self, rows) -> None:
        self._rows = list(rows)

    def all(self):
        return list(self._rows)


class _Sess:
    def __init__(self, results=(), rows=(), raise_at=()) -> None:
        self.calls: list[tuple[str, tuple]] = []
        self.commits = 0
        self._results = list(results)
        self._rows = list(rows)
        self._raise_at = set(raise_at)

    async def execute(self, stmt):
        idx = sum(1 for c in self.calls if c[0] == "execute")
        self.calls.append(("execute", _dig(stmt)))
        if idx in self._raise_at:
            raise RuntimeError("boom")
        return self._results.pop(0)

    async def stream_scalars(self, stmt):
        self.calls.append(("stream", _dig(stmt)))
        rows = list(self._rows)

        async def agen():
            for r in rows:
                yield r

        return agen()

    async def commit(self):
        self.commits += 1


@contextlib.contextmanager
def _session(sess):
    @contextlib.asynccontextmanager
    async def factory():
        yield sess

    with _attr(cs, "get_session", factory):
        yield sess


class _Job:
    """JobStatusService stand-in: async methods, COMPLETE call list."""

    def __init__(self, job_id="J1") -> None:
        self.calls: list[tuple] = []
        self._job_id = job_id

    async def start_job(self, *args, **kwargs):
        self.calls.append(("start_job", args, kwargs))
        return self._job_id

    async def update_progress(self, *args, **kwargs):
        self.calls.append(("update_progress", args, kwargs))

    async def complete_job(self, *args, **kwargs):
        self.calls.append(("complete_job", args, kwargs))

    async def fail_job(self, *args, **kwargs):
        self.calls.append(("fail_job", args, kwargs))


def _tracked(svc, job):
    svc._redis_client = object()
    svc._job_status_service = job
    return svc


class _Track:
    """JobTracker stand-in (sync methods)."""

    def __init__(self, job_id="T1") -> None:
        self.calls: list[tuple] = []
        self._job_id = job_id

    def create_job(self, *args, **kwargs):
        self.calls.append(("create_job", args, kwargs))
        return self._job_id

    def start_job(self, *args, **kwargs):
        self.calls.append(("start_job", args, kwargs))

    def update_progress(self, *args, **kwargs):
        self.calls.append(("update_progress", args, kwargs))

    def complete_job(self, *args, **kwargs):
        self.calls.append(("complete_job", args, kwargs))

    def fail_job(self, *args, **kwargs):
        self.calls.append(("fail_job", args, kwargs))


class _Task:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def __await__(self):
        async def _die():
            import asyncio

            raise asyncio.CancelledError

        return _die().__await__()


class _AS:
    """cs.asyncio shim: REAL CancelledError, observed sleep/create_task."""

    @staticmethod
    def sleep(delay, result=None):
        SLEEPS.append(delay)

        async def _go():
            return result

        return _go()

    @staticmethod
    def create_task(coro, name=MISS):
        TASK_NAMES.append(name)
        coro.close()
        return _Task()


@contextlib.contextmanager
def _shim_asyncio():
    import asyncio

    SLEEPS.clear()
    TASK_NAMES.clear()
    shim = types.SimpleNamespace(
        CancelledError=asyncio.CancelledError,
        sleep=_AS.sleep,
        create_task=_AS.create_task,
    )
    with _attr(cs, "asyncio", shim):
        yield


def _det(thumb=MISS, file=MISS):
    return types.SimpleNamespace(
        thumbnail_path=None if thumb is MISS else thumb,
        file_path=None if file is MISS else file,
    )


class _SvcNL(cs.CleanupService):
    """run_cleanup tests stub the log-deletion leg (it opens its own session
    for the DELETE statement; cleanup_old_logs mutants have their own tests)."""

    async def cleanup_old_logs(self) -> int:
        return 41


# ---------------------------------------------------------------------------
# CleanupService.run_cleanup -- job tracking, SQL digests, messages
# ---------------------------------------------------------------------------
def test_run_cleanup_tracked_exact_calls_messages_and_digests():
    """Kills the update_progress/start_job arg+message families, every
    happy-polarity guard twin, execute(None) delete mutants, cutoff mutants,
    and the log-message families of run_cleanup."""
    svc = _svc(cls=_SvcNL, retention_days=RET)
    job = _Job(JOBS)
    _tracked(svc, job)
    sess = _Sess(results=[_Res(rowcount=5), _Res(rowcount=3), _Res(rowcount=100)])
    with _pinned(), _clocked(PIN) as clk, _session(sess), _capture_logs() as cap:
        stats = _attempt(svc.run_cleanup())
    assert clk.tzs == [UTC, UTC], clk.tzs
    assert stats.to_dict() == {
        "events_deleted": 3,
        "detections_deleted": 5,
        "gpu_stats_deleted": 100,
        "logs_deleted": 41,
        "thumbnails_deleted": 0,
        "images_deleted": 0,
        "space_reclaimed": 0,
    }
    up = "update_progress"
    assert job.calls == [
        (
            "start_job",
            (),
            {"job_id": JOBS, "job_type": "data_cleanup", "metadata": {"retention_days": 30}},
        ),
        (up, (JOBS, 5, "Scanning for files to delete"), {}),
        (up, (JOBS, 15, "Deleting old detections"), {}),
        (up, (JOBS, 30, "Deleting old events"), {}),
        (up, (JOBS, 45, "Deleting old GPU stats"), {}),
        (up, (JOBS, 55, "Deleting old logs"), {}),
        (up, (JOBS, 70, "Deleting thumbnail files"), {}),
        ("complete_job", (JOBS,), {"result": stats.to_dict()}),
    ]
    assert sess.calls == [
        ("stream", DIG_DET_QUERY),
        ("execute", DIG_DEL_DET),
        ("execute", DIG_DEL_EVT),
        ("execute", DIG_DEL_GPU),
    ]
    assert sess.commits == 1
    _assert_msgs(
        cap,
        [
            (INFO, "Starting cleanup (retention: 30 days)"),
            (INFO, "Deleting records older than " + str(DET_CUT)),
            (INFO, "Deleted 5 old detections"),
            (INFO, "Deleted 3 old events"),
            (INFO, "Deleted 100 old GPU stats"),
            (INFO, "Database cleanup committed successfully"),
            (INFO, "Deleted 0 thumbnail files"),
            (INFO, "Cleanup completed: " + str(stats)),
        ],
    )


def test_run_cleanup_files_and_delete_images_call_list():
    with tempfile.TemporaryDirectory() as td:
        t1 = Path(td) / "t1.jpg"
        t1.write_text("t1")
        i1 = Path(td) / "i1.jpg"
        i1.write_text("img1")
        svc = _svc(cls=_SvcNL, retention_days=RET, delete_images=True)
        job = _Job(JOBS)
        _tracked(svc, job)
        rows = [_det(thumb=str(t1), file=str(i1)), _det()]
        sess = _Sess(results=[_Res(rowcount=1), _Res(rowcount=1), _Res(rowcount=1)], rows=rows)
        with _pinned(), _clocked(PIN), _session(sess), _capture_logs() as cap:
            stats = _attempt(svc.run_cleanup())
        assert (not t1.exists()) and (not i1.exists())
        assert stats.thumbnails_deleted == 1 and stats.images_deleted == 1
        up = "update_progress"
        assert job.calls[-2] == (up, (JOBS, 85, "Deleting image files"), {})
        assert job.calls[-1] == ("complete_job", (JOBS,), {"result": stats.to_dict()})
        # the delete_images=True path is the ONLY one that reaches the
        # "Deleted N original image files" line -- capture its full ordered
        # log so that line's message mutants (None/XX/case) cannot hide.
        _assert_msgs(
            cap,
            [
                (INFO, "Starting cleanup (retention: 30 days)"),
                (INFO, "Deleting records older than " + str(DET_CUT)),
                (INFO, "Deleted 1 old detections"),
                (INFO, "Deleted 1 old events"),
                (INFO, "Deleted 1 old GPU stats"),
                (INFO, "Database cleanup committed successfully"),
                (INFO, "Deleted 1 thumbnail files"),
                (INFO, "Deleted 1 original image files"),
                (INFO, "Cleanup completed: " + str(stats)),
            ],
        )


def test_run_cleanup_startjob_none_polarity_zero_side_calls():
    """start_job returns None: shipped makes NO update/complete/fail call;
    the 'or' guard twins call update_progress(None, ...)/complete_job(None,
    ...) and land RED here (files present so the 85% block is live)."""
    with tempfile.TemporaryDirectory() as td:
        t1 = Path(td) / "t1.jpg"
        t1.write_text("t1")
        svc = _svc(cls=_SvcNL, retention_days=RET, delete_images=True)
        job = _Job(None)
        _tracked(svc, job)
        rows = [_det(thumb=str(t1))]
        sess = _Sess(results=[_Res(rowcount=1), _Res(rowcount=1), _Res(rowcount=1)], rows=rows)
        with _pinned(), _clocked(PIN), _session(sess):
            _attempt(svc.run_cleanup())
        assert [c for c in job.calls if c[0] != "start_job"] == [], job.calls


def test_run_cleanup_untracked_untouched_by_guard_twins():
    """job_service None polarity: the 'job_service is None and ...' twins
    would call update_progress on None -> AttributeError inside the try ->
    the error path; shipped just runs and commits."""
    sess = _Sess(results=[_Res(rowcount=0), _Res(rowcount=0), _Res(rowcount=0)])
    svc = _svc(cls=_SvcNL, retention_days=RET)
    with _pinned(), _clocked(PIN), _session(sess), _capture_logs() as cap:
        stats = _attempt(svc.run_cleanup())
    assert sess.commits == 1
    assert stats.logs_deleted == 41
    assert [(r.levelno, r.getMessage()) for r in cap.records][1] == (
        INFO,
        "Deleting records older than " + str(DET_CUT),
    )


def test_run_cleanup_failure_logs_error_with_exc_info_and_fails_job():
    svc = _svc(cls=_SvcNL, retention_days=RET)
    job = _Job(JOBS)
    _tracked(svc, job)
    sess = _Sess(results=[], rows=[], raise_at={0})
    with _pinned(), _clocked(PIN), _session(sess), _capture_logs() as cap:
        try:
            _attempt(svc.run_cleanup())
            raise AssertionError("must re-raise")
        except RuntimeError as exc:
            assert exc.args == ("boom",)
    assert job.calls[-1] == ("fail_job", (JOBS, "boom"), {})
    err = cap.records[-1]
    assert err.levelno == ERROR
    assert err.getMessage() == "Cleanup failed: boom"
    assert err.exc_info[0] is RuntimeError and err.exc_info[1].args == ("boom",)


def test_run_cleanup_failure_none_polarity_no_fail_call():
    """start_job -> None + exception: shipped skips fail_job; the L349 'or'
    twin calls fail_job(None, 'boom')."""
    svc = _svc(cls=_SvcNL, retention_days=RET)
    job = _Job(None)
    _tracked(svc, job)
    sess = _Sess(results=[], rows=[], raise_at={0})
    with _pinned(), _clocked(PIN), _session(sess), _capture_logs() as cap:
        try:
            _attempt(svc.run_cleanup())
            raise AssertionError("must re-raise")
        except RuntimeError:
            pass
    assert [c for c in job.calls if c[0] != "start_job"] == [], job.calls
    err = cap.records[-1]
    assert err.getMessage() == "Cleanup failed: boom"
    assert err.exc_info[1].args == ("boom",)


# ---------------------------------------------------------------------------
# _delete_file
# ---------------------------------------------------------------------------
def test_delete_file_true_for_real_file():
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "a.bin"
        f.write_text("x")
        svc = _svc()
        assert svc._delete_file(str(f)) is True
        assert not f.exists()


def test_delete_file_directory_takes_debug_not_unlink():
    """and -> or: the OR lets a DIRECTORY through to unlink(), replacing the
    shipped debug line with a failure warning (is_file() is os.path.isdir-
    backed, so overriding stat() cannot fake this -- a real dir is needed)."""
    with tempfile.TemporaryDirectory() as td:
        svc = _svc()
        with _capture_logs() as cap:
            assert svc._delete_file(td) is False
        _assert_msgs(cap, [(DEBUG, "File not found or not a file: " + td)])


def test_delete_file_missing_takes_debug_path():
    svc = _svc()
    with _capture_logs() as cap:
        assert svc._delete_file(NOWHERE + "/x.bin") is False
    _assert_msgs(cap, [(DEBUG, "File not found or not a file: " + NOWHERE + "/x.bin")])


class _NoUnlink(Path):
    def unlink(self, missing_ok=False):
        if self.name == "noclean.bin":
            raise OSError("nope")
        return super().unlink(missing_ok=missing_ok)


def test_delete_file_unlink_failure_warns_with_exc_info():
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "noclean.bin"
        f.write_text("x")
        svc = _svc()
        with _attr(cs, "Path", _NoUnlink), _capture_logs() as cap:
            assert svc._delete_file(str(f)) is False
        assert len(cap.records) == 1
        rec = cap.records[0]
        assert rec.levelno == WARNING
        assert rec.getMessage() == "Failed to delete file " + str(f) + ": nope"
        assert rec.exc_info[0] is OSError and rec.exc_info[1].args == ("nope",)


# ---------------------------------------------------------------------------
# _get_detection_file_paths_streaming
# ---------------------------------------------------------------------------
def _stream(svc, sess, cutoff):
    async def _go():
        return await svc._get_detection_file_paths_streaming(sess, cutoff)

    with _session(sess):
        return _attempt(_go())


def test_stream_paths_digest_and_no_images_polarity():
    """Digest kills the query mutants; delete_images=False with file_paths
    present must collect NOTHING on the image leg (kills the 'or' twin)."""
    svc = _svc(retention_days=RET, delete_images=False)
    sess = _Sess(rows=[_det(thumb="T1", file="F1"), _det(thumb="T2")])
    thumbs, images = _stream(svc, sess, DET_CUT)
    assert thumbs == ["T1", "T2"]
    assert images == []
    assert sess.calls == [("stream", DIG_DET_QUERY)]


def test_stream_paths_delete_images_true_collects_both():
    svc = _svc(retention_days=RET, delete_images=True)
    sess = _Sess(rows=[_det(thumb="T1", file="F1"), _det(thumb=None, file="F2"), _det()])
    thumbs, images = _stream(svc, sess, DET_CUT)
    assert thumbs == ["T1"]
    assert images == ["F1", "F2"]


# ---------------------------------------------------------------------------
# dry_run_cleanup
# ---------------------------------------------------------------------------
def test_dry_run_exact_digests_counts_stats_and_messages():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        real_t = tmp / "t.jpg"
        real_t.write_bytes(b"12345")  # 5 B
        real_t2 = tmp / "t2.jpg"
        real_t2.write_bytes(b"abc")  # 3 B -- the += 1 -> = 1 twin needs 2 hits
        dir_t = tmp / "dir.jpg"  # a DIRECTORY named like a media file
        dir_t.mkdir()
        img1 = tmp / "i1.jpg"
        img1.write_bytes(b"ab")  # 2 B
        img2 = tmp / "i2.jpg"
        img2.write_bytes(b"c")  # 1 B -> images 2, space 11
        rows = [
            _det(thumb=str(real_t), file=str(img1)),
            _det(thumb=str(dir_t), file=str(img2)),
            _det(thumb=str(real_t2), file=str(dir_t)),
        ]
        sess = _Sess(
            results=[_Res(scalar=7), _Res(scalar=3), _Res(scalar=11), _Res(scalar=9)],
            rows=rows,
        )
        svc = _svc(retention_days=RET, delete_images=True)
        with _pinned(), _clocked(PIN) as clk, _session(sess), _capture_logs() as cap:
            stats = _attempt(svc.dry_run_cleanup())
        assert clk.tzs == [UTC, UTC], clk.tzs  # dry-run cutoff + _count_old_logs
        # shipped counts ONLY real files (dirs + missing skipped); the
        # and->or twins count the directory, the =1 twins pin to 1.
        assert stats.detections_deleted == 7
        assert stats.events_deleted == 3
        assert stats.gpu_stats_deleted == 11
        assert stats.logs_deleted == 9
        assert stats.thumbnails_deleted == 2
        assert stats.images_deleted == 2
        assert stats.space_reclaimed == 11
        assert sess.calls == [
            ("execute", DIG_DET_COUNT),
            ("stream", DIG_DET_QUERY),
            ("execute", DIG_EVT_COUNT),
            ("execute", DIG_GPU_COUNT),
            ("execute", DIG_LOG_COUNT),
        ]
        _assert_msgs(
            cap,
            [
                (INFO, "Starting cleanup dry run (retention: 30 days)"),
                (INFO, "Dry run: would delete records older than " + str(DET_CUT)),
                (INFO, "Dry run: would delete 7 detections"),
                (INFO, "Dry run: would delete 2 thumbnail files"),
                (INFO, "Dry run: would delete 2 image files"),
                (INFO, "Dry run: would delete 3 events"),
                (INFO, "Dry run: would delete 11 GPU stats"),
                (INFO, "Dry run: would delete 9 logs older than 7 days"),
                (INFO, "Cleanup dry run completed: " + str(stats)),
            ],
        )


def test_dry_run_failure_logs_error_with_exc_info():
    sess = _Sess(results=[_Res(scalar=0)], rows=[], raise_at={1})
    svc = _svc(retention_days=RET)
    with _pinned(), _clocked(PIN), _session(sess), _capture_logs() as cap:
        try:
            _attempt(svc.dry_run_cleanup())
            raise AssertionError("must re-raise")
        except RuntimeError as exc:
            assert exc.args == ("boom",)
    err = cap.records[-1]
    assert err.levelno == ERROR
    assert err.getMessage() == "Cleanup dry run failed: boom"
    assert err.exc_info[0] is RuntimeError and err.exc_info[1].args == ("boom",)


# ---------------------------------------------------------------------------
# _count_old_logs / cleanup_old_logs
# ---------------------------------------------------------------------------
def test_count_old_logs_zero_count_logs_nothing_exact_digest():
    sess = _Sess(results=[_Res(scalar=0)])
    svc = _svc()
    with _pinned(), _clocked(PIN) as clk, _session(sess), _capture_logs() as cap:
        assert _attempt(svc._count_old_logs()) == 0
    assert clk.tzs == [UTC]
    assert sess.calls == [("execute", DIG_LOG_COUNT)]
    _assert_msgs(cap, [])  # the > -> >= twin logs on zero -- killed here


def test_count_old_logs_one_logs_exactly_once():
    sess = _Sess(results=[_Res(scalar=1)])
    svc = _svc()
    with _pinned(), _clocked(PIN), _session(sess), _capture_logs() as cap:
        assert _attempt(svc._count_old_logs()) == 1
    _assert_msgs(cap, [(INFO, "Dry run: would delete 1 logs older than 7 days")])
    # the > 1 twin drops this log -- killed by the assert above


def test_cleanup_old_logs_zero_no_log_commit_and_digest():
    sess = _Sess(results=[_Res(rowcount=0)])
    svc = _svc()
    with _pinned(), _clocked(PIN) as clk, _session(sess), _capture_logs() as cap:
        assert _attempt(svc.cleanup_old_logs()) == 0
    assert clk.tzs == [UTC]
    assert sess.calls == [("execute", DIG_DEL_LOG)]
    assert sess.commits == 1
    _assert_msgs(cap, [])


def test_cleanup_old_logs_one_logs_exactly_once():
    sess = _Sess(results=[_Res(rowcount=1)])
    svc = _svc()
    with _pinned(), _clocked(PIN), _session(sess), _capture_logs() as cap:
        assert _attempt(svc.cleanup_old_logs()) == 1
    _assert_msgs(cap, [(INFO, "Cleaned up 1 logs older than 7 days")])


# ---------------------------------------------------------------------------
# _parse_cleanup_time boundaries + chained cause
# ---------------------------------------------------------------------------
def test_parse_cleanup_time_ranges_and_exact_cause():
    for hm in ["00:00", "23:59", "03:00"]:
        svc = _svc(cleanup_time=hm)
        assert svc._parse_cleanup_time() == tuple(int(x) for x in hm.split(":"))
    for bad in ["24:00", "25:00", "23:60", "23:61", "-1:00"]:
        svc = _svc(cleanup_time=bad)
        try:
            svc._parse_cleanup_time()
            raise AssertionError("must raise for " + bad)
        except ValueError as exc:
            assert str(exc) == (
                "Invalid cleanup_time format '" + bad + "'. Expected HH:MM (24-hour format)"
            ), str(exc)
            assert str(exc.__cause__) == "Invalid time range", str(exc.__cause__)
    svc = _svc(cleanup_time="12:")
    try:
        svc._parse_cleanup_time()
        raise AssertionError("must raise for malformed")
    except ValueError as exc:
        assert str(exc) == ("Invalid cleanup_time format '12:'. Expected HH:MM (24-hour format)")


def test_parse_cleanup_time_attribute_error_chain():
    svc = _svc()
    svc.cleanup_time = None
    try:
        svc._parse_cleanup_time()
        raise AssertionError("must raise")
    except ValueError as exc:
        assert isinstance(exc.__cause__, AttributeError)


# ---------------------------------------------------------------------------
# _calculate_next_cleanup / _wait_until_next_cleanup
# ---------------------------------------------------------------------------
def test_next_cleanup_exact_fields_with_nonzero_clock():
    svc = _svc(cleanup_time="02:30")
    with _clocked(PIN_A) as clk:
        got = svc._calculate_next_cleanup()
    assert got == datetime(2026, 9, 16, 2, 30, 0, 0, tzinfo=UTC), got
    assert clk.tzs == [UTC]


def test_next_cleanup_boundary_equal_now_rolls_forward():
    """<= -> < twin: cleanup_time EXACTLY equals the pinned instant --
    shipped treats an already-passed time and rolls to tomorrow."""
    svc = _svc(cleanup_time="12:00")
    with _clocked(PIN):
        got = svc._calculate_next_cleanup()
    assert got == datetime(2026, 9, 16, 12, 0, 0, 0, tzinfo=UTC), got


def test_wait_until_next_cleanup_sleeps_exact_seconds_logs_exact_message():
    svc = _svc(cleanup_time="13:00")
    with _clocked(PIN), _shim_asyncio(), _capture_logs() as cap:
        _attempt(svc._wait_until_next_cleanup())
    assert SLEEPS == [3600.0], SLEEPS
    _assert_msgs(
        cap,
        [(INFO, "Next cleanup scheduled for 2026-09-15 13:00:00+00:00 (3600s)")],
    )


# ---------------------------------------------------------------------------
# __init__ logs + attributes
# ---------------------------------------------------------------------------
def test_init_stores_batch_size_and_logs_exact_summary():
    with _capture_logs() as cap:
        svc = _svc(cleanup_time="03:00")
    assert svc.batch_size == 1000
    assert svc.retention_days == 44
    _assert_msgs(
        cap,
        [
            (
                INFO,
                "CleanupService initialized: retention=44 days, time=03:00, "
                "delete_images=False, batch_size=1000",
            )
        ],
    )


def test_orphan_init_logs_exact_storage_paths():
    with _capture_logs() as cap:
        _osvc(storage_paths=["/a", "/b"])
    _assert_msgs(
        cap,
        [(INFO, "OrphanedFileCleanup initialized with storage paths: ['/a', '/b']")],
    )


# ---------------------------------------------------------------------------
# start / stop / _cleanup_loop (cs.asyncio shimmed)
# ---------------------------------------------------------------------------
def test_start_creates_named_task_and_logs_exactly():
    svc = _svc()
    with _shim_asyncio(), _capture_logs() as cap:
        _attempt(svc.start())
        assert svc.running is True
        _attempt(svc.start())  # idempotent second call
    assert TASK_NAMES == ["cleanup-service"]  # None/MISSING/XX/UPPER killed
    assert svc._cleanup_task is not None
    _assert_msgs(
        cap,
        [
            (INFO, "Starting CleanupService"),
            (INFO, "CleanupService started successfully"),
            (WARNING, "CleanupService already running"),
        ],
    )


def test_stop_cancels_awaitable_clears_and_logs():
    svc = _svc()
    task = _Task()
    svc.running = True
    svc._cleanup_task = task
    with _capture_logs() as cap:
        _attempt(svc.stop())
    assert task.cancelled is True
    assert svc.running is False and svc._cleanup_task is None
    _assert_msgs(cap, [(INFO, "Stopping CleanupService"), (INFO, "CleanupService stopped")])


def test_stop_when_not_running_only_debugs():
    svc = _svc()
    with _capture_logs() as cap:
        _attempt(svc.stop())
    _assert_msgs(cap, [(DEBUG, "CleanupService not running, nothing to stop")])


class _LoopSvc(cs.CleanupService):
    """_wait/run spies: the loop's iteration sequence is deterministic."""

    def __init__(self, script) -> None:
        super().__init__(retention_days=1)
        self.script = list(script)
        self.runs = 0

    async def _wait_until_next_cleanup(self):
        step = self.script.pop(0)
        if step == "raise":
            raise RuntimeError("looperr")
        if step == "cancel":
            import asyncio

            raise asyncio.CancelledError
        if step == "stop":
            self.running = False

    async def run_cleanup(self):
        self.runs += 1
        return cs.CleanupStats()


def _lsvc(script):
    with _pinned():
        return _LoopSvc(script)


def _loop(svc):
    with _shim_asyncio(), _capture_logs() as cap:
        svc.running = True
        _attempt(svc._cleanup_loop())
    return cap


def test_cleanup_loop_happy_path_logs_bookends_and_runs_once():
    svc = _lsvc(["ok", "stop"])
    cap = _loop(svc)
    assert svc.runs == 1
    _assert_msgs(cap, [(INFO, "Cleanup loop started"), (INFO, "Cleanup loop stopped")])


def test_cleanup_loop_cancel_breaks_then_logs_stopped():
    """break -> return: the RETURN skips the stopped bookend."""
    svc = _lsvc(["cancel"])
    cap = _loop(svc)
    assert svc.runs == 0
    _assert_msgs(
        cap,
        [
            (INFO, "Cleanup loop started"),
            (INFO, "Cleanup loop cancelled"),
            (INFO, "Cleanup loop stopped"),
        ],
    )


def test_cleanup_loop_error_logs_then_sleeps_60_and_survives():
    svc = _lsvc(["raise", "stop"])
    cap = _loop(svc)
    assert SLEEPS == [60], SLEEPS  # the 61 twin killed by the exact value
    assert svc.runs == 0
    _assert_msgs(
        cap,
        [
            (INFO, "Cleanup loop started"),
            (ERROR, "Error in cleanup loop: looperr"),
            (INFO, "Cleanup loop stopped"),
        ],
    )
    errs = [r for r in cap.records if r.levelno == ERROR]
    assert len(errs) == 1
    assert errs[0].exc_info[0] is RuntimeError
    assert errs[0].exc_info[1].args == ("looperr",)


# ---------------------------------------------------------------------------
# OrphanedFileCleanup.run_cleanup + helpers
# ---------------------------------------------------------------------------
def test_orphan_run_cleanup_dry_default_exact_calls_and_messages():
    """Default arg (True->False would DELETE and set dry_run False), the
    full tracker call list, exact messages, and the orphaned-list contents
    (append(None) would put None in the list)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        (tmp / "ref.bin").write_bytes(b"r")
        (tmp / "orph1.bin").write_bytes(b"ab")
        (tmp / "orph2.bin").write_bytes(b"abcd")
        ref = str((tmp / "ref.bin").resolve())
        orph1 = str((tmp / "orph1.bin").resolve())
        orph2 = str((tmp / "orph2.bin").resolve())

        class _Dry(cs.OrphanedFileCleanup):
            async def _get_referenced_files(self):
                return {ref}

        tr = _Track("T1")
        svc = _Dry(job_tracker=tr, storage_paths=[td])
        with _capture_logs() as cap:
            stats = _attempt(svc.run_cleanup())
        assert stats.dry_run is True
        assert (tmp / "orph1.bin").exists() and (tmp / "orph2.bin").exists()
        assert stats.orphaned_count == 2
        assert stats.total_size == 6
        assert set(stats.orphaned_files) == {orph1, orph2}
        assert tr.calls == [
            ("create_job", ("orphaned_file_cleanup",), {}),
            ("start_job", ("T1", "Starting orphaned file cleanup"), {}),
            ("update_progress", ("T1", 10, "Querying database for referenced files"), {}),
            ("update_progress", ("T1", 30, "Scanning storage directories"), {}),
            ("update_progress", ("T1", 50, "Identifying orphaned files"), {}),
            ("complete_job", ("T1", stats.to_dict()), {}),
        ]
        _assert_msgs(
            cap,
            [
                (INFO, "Querying database for referenced files..."),
                (INFO, "Found 1 referenced files in database"),
                (INFO, "Scanning storage directories: ['" + td + "']"),
                (INFO, "Found 3 files on disk"),
                (INFO, "Found 2 orphaned files (6 B)"),
                (INFO, "Orphaned file cleanup completed: " + str(stats)),
            ],
        )


def test_orphan_run_cleanup_wet_deletes_logs_and_progress70():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        (tmp / "orph1.bin").write_bytes(b"ab")
        (tmp / "orph2.bin").write_bytes(b"abcd")

        class _Wet(cs.OrphanedFileCleanup):
            async def _get_referenced_files(self):
                return set()

        tr = _Track("T1")
        svc = _Wet(job_tracker=tr, storage_paths=[td])
        with _capture_logs() as cap:
            stats = _attempt(svc.run_cleanup(dry_run=False))
        assert not (tmp / "orph1.bin").exists()
        assert not (tmp / "orph2.bin").exists()
        assert stats.dry_run is False
        assert ("update_progress", ("T1", 70, "Deleting orphaned files"), {}) in tr.calls
        assert "Deleted 2 of 2 orphaned files" in [r.getMessage() for r in cap.records]
        assert tr.calls[-1] == ("complete_job", ("T1", stats.to_dict()), {})


def test_orphan_run_cleanup_failure_fails_job_with_exact_error():
    with tempfile.TemporaryDirectory() as td:

        class _Fail(cs.OrphanedFileCleanup):
            async def _get_referenced_files(self):
                raise RuntimeError("dbdown")

        tr = _Track("T1")
        svc = _Fail(job_tracker=tr, storage_paths=[td])
        with _capture_logs() as cap:
            try:
                _attempt(svc.run_cleanup())
                raise AssertionError("must re-raise")
            except RuntimeError as exc:
                assert exc.args == ("dbdown",)
        assert tr.calls[-1] == ("fail_job", ("T1", "dbdown"), {})
        rec = cap.records[-1]
        assert rec.getMessage() == "Orphaned file cleanup failed: dbdown"
        assert rec.exc_info[0] is RuntimeError and rec.exc_info[1].args == ("dbdown",)


def test_orphan_falsy_job_id_never_completes_or_fails():
    """create_job returns '' (falsy): shipped makes NO complete/fail call in
    either polarity; the 'or' guard twins call with ''."""

    class _Empty(cs.OrphanedFileCleanup):
        async def _get_referenced_files(self):
            return set()

    tr = _Track("")
    svc = _Empty(job_tracker=tr, storage_paths=[NOWHERE])
    _attempt(svc.run_cleanup())
    assert [c for c in tr.calls if c[0] in ("complete_job", "fail_job")] == []

    class _EmptyFail(cs.OrphanedFileCleanup):
        async def _get_referenced_files(self):
            raise RuntimeError("nope2")

    tr2 = _Track("")
    svc2 = _EmptyFail(job_tracker=tr2, storage_paths=[NOWHERE])
    try:
        _attempt(svc2.run_cleanup())
        raise AssertionError("must re-raise")
    except RuntimeError:
        pass
    assert [c for c in tr2.calls if c[0] == "fail_job"] == []


def test_orphan_get_referenced_files_digests_and_absolutization():
    # str(Path(rel).resolve()) in the TEST world sees the SAME process cwd the
    # module sees, so the absolute paths are predictable without chdir.
    rows = [("rel/a.img", "rel/b.jpg"), (None, None)]
    evt_rows = [("rel/c.mp4",), (None,)]
    sess = _Sess(results=[_Rows(rows), _Rows(evt_rows)])
    svc = _osvc(storage_paths=[NOWHERE])
    with _session(sess):
        got = _attempt(svc._get_referenced_files())
    assert sess.calls == [("execute", DIG_REF_DET), ("execute", DIG_REF_EVT)]
    assert got == {
        str(Path("rel/a.img").resolve()),
        str(Path("rel/b.jpg").resolve()),
        str(Path("rel/c.mp4").resolve()),
    }


class _NoStat(Path):
    def stat(self, follow_symlinks=True):
        if self.name == "nostat.bin":
            raise OSError("statdown")
        return super().stat(follow_symlinks=follow_symlinks)


def test_scan_storage_directories_skips_broken_and_continues():
    """Order: missing, a FILE (not a dir), d1 (one stat failure + one good),
    d2. The continue -> break twins stop at the first skip; shipped scans
    BOTH valid dirs. (Path.is_dir/is_file are os-path backed, so _NoStat can
    only break the explicit stat() call, which is what is being exercised.)"""
    with tempfile.TemporaryDirectory() as outer:
        outerp = Path(outer)
        missing = outerp / "missing"
        notadir = outerp / "file.txt"
        notadir.write_text("x")
        d1 = outerp / "d1"
        d1.mkdir()
        nostat = d1 / "nostat.bin"
        nostat.write_text("ns")
        (d1 / "good.bin").write_bytes(b"12")
        d2 = outerp / "d2"
        d2.mkdir()
        (d2 / "e.bin").write_bytes(b"12345")
        svc = _osvc(storage_paths=[str(missing), str(notadir), str(d1), str(d2)])
        with _attr(cs, "Path", _NoStat), _capture_logs() as cap:
            found = svc._scan_storage_directories()
        sizes = {Path(p).name: s for p, s in found}
        assert sorted(sizes) == ["e.bin", "good.bin"], sizes
        assert sizes["good.bin"] == 2 and sizes["e.bin"] == 5
        msgs = [r.getMessage() for r in cap.records]
        assert "Storage path does not exist: " + str(missing) in msgs
        assert "Storage path is not a directory: " + str(notadir) in msgs
        assert "Could not stat file " + str(nostat) + ": statdown" in msgs


def test_orphan_delete_orphaned_files_partial_failure_warns():
    with tempfile.TemporaryDirectory() as td:
        ok = Path(td) / "ok.bin"
        ok.write_text("x")
        bad = Path(td) / "noclean.bin"
        bad.write_text("x")
        svc = _osvc(storage_paths=[NOWHERE])
        with _attr(cs, "Path", _NoUnlink), _capture_logs() as cap:
            n = svc._delete_orphaned_files([(str(ok), 1), (str(bad), 1)])
        assert n == 1
        assert not ok.exists() and bad.exists()
        _assert_msgs(cap, [(WARNING, "Failed to delete orphaned file " + str(bad) + ": nope")])


# ---------------------------------------------------------------------------
# digest-channel self-check (not a mutant claim): the channel must separate
# the shipped streaming query from its <= twin, where(None) twin and None.
# ---------------------------------------------------------------------------
def test_digest_helper_selfcheck_distinguishes_families():
    le = _dig(select(Detection).where(Detection.detected_at <= DET_CUT))
    wnone = _dig(select(Detection).where(None))
    assert le != DIG_DET_QUERY
    assert wnone != DIG_DET_QUERY
    assert _dig(None) != DIG_DET_QUERY
    naive = _dig_model(Detection.detected_at, Detection, DET_CUT.replace(tzinfo=None))
    assert naive != DIG_DET_QUERY
