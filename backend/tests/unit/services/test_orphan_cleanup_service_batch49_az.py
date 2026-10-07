"""Campaign #49 (batch-49, battery AZ) - `backend.services.orphan_cleanup_service`.

# TARGET-MODULE: backend.services.orphan_cleanup_service

The module sat at 187 survivors / 371 keys (49.5957%) - the largest lifecycle
surface in the bank. The shipped test file (test_orphan_cleanup_service.py)
drives every METHOD (that is why 184 keys already die) but asserts BEHAVIOR
(statistics counters, "a warning was emitted") and never the exact message
TEXT, the exact call ARGS/kwARGS, or the emitted SQL text - so the whole
None-swap / XX-wrap / case-flip / lowercase / drop-argument mutant families
survived: the message arms (None + XX + lower + UPPER per call site), the
arg/kwargs arms, the statement-None / where-None / != SQL arms, the
stats-counter (=1 / +=2 / -=) arms and the arithmetic arms (/3600, *3601,
*91, >= vs >, sleep-61).

Harness contract (b30 sweep, /home/agent/runs/b30-sweep.py): NO pytest
fixtures, NO parametrize, NO monkeypatch - the sweep imports this file
directly and calls every module-level ``test_*`` with zero arguments in ONE
process, flipping os.environ[MUTANT_UNDER_TEST] per key. Async entry points
are driven with asyncio.run INSIDE the test body; seams are patched through
the TARGET MODULE's globals (oc.get_settings, oc.get_session, oc.datetime)
and the shared asyncio module (oc.asyncio IS the same module object as the
global asyncio - the module binds `import asyncio`) plus INSTANCE
attributes (svc._cleanup_loop, svc._scan_clip_files, svc._is_orphan via
MethodType) with attribute save/restore through _Patcher so a mid-test
assert failure cannot leak a patch into the next key's window.
Self-provisioned temp dirs (tempfile.mkdtemp) instead of the tmp_path
fixture (the sweep passes no fixtures). Singleton tests call
reset_orphan_cleanup_service() in a FINALLY so a failed assert cannot
poison a later key's module state.

KILL CONSTRUCTIONS (why each family bites its keys, not just its shipped run):

  * CollectorCtx + MESSAGE EQUALITY on r.getMessage() with the full
    interpolated literal (drives use fixed inputs, so every {value} is
    known). The None-swap ("None"), "XXmsgXX", lowercase and UPPERCASE arms
    all die to equality - never a substring or level-only census (the
    fragment-count family is a documented survivor cause). Structured-extra
    arms die to record.<key> attribute reads (event_type / error): a
    renamed key lands under a different attribute (getattr default None
    mismatch), a dropped extra= or str(None) mismatches the value.
  * RecordingTracker has a FIXED positional signature - an arg DROP is a
    TypeError at the stub, a None-swap/reorder/kwargs-swallow breaks the
    (name, args, kwargs) tuple equality. Positional values are DISTINCT
    (job id "J-42", progress 45/90, message text) so no arm can alias.
  * FakeSession records the compiled PostgreSQL text (literal_binds) of
    EVERY statement and answers by first-matching needle; LIST equality of
    the query trace kills `!=` (renders `!=`), `where(None)` (renders the
    WHERE-stripped select), `select(None)` (renders SELECT NULL) and the
    run_cleanup m50 str(None) ARG swap - that last one survives the stats
    arithmetic in shipped (deletion uses the original path!) but replaces
    the id
    queries with clip_path = 'None' queries: the trace is the only surface
    that sees it.
  * Lifecycle order: the exact (INFO-level) message SEQUENCE of
    start/stop/_cleanup_loop is asserted as one list - dropped legs shrink
    it, renamed/case text breaks it, `break`->`return` (m14 of
    _cleanup_loop) skips the final "loop stopped" INFO.
  * Numeric arms at the arithmetic boundary: sleep arg EQUALS
    scan_interval_hours * 3600 (kills /3600 and *3601 and None), the age
    boundary driven at the EXACT threshold second (kills >= vs >) and at
    3600*24+12 s vs /3601 (the only divergence of the +-1 divisor),
    progress driven at TWO files (the *91 arm AGREES on file 1 and
    diverges on file 2 - single-file asserts pass it), retry sleep EQUALS
    60 (None raises TypeError at the stub, 61 mismatches).
  * __init__ getattr arms need settings WITHOUT the attrs to be READ:
    StrippedSettings (clips_directory only) forces the fallback arms live,
    so default 24->25, ->None and the trailing-comma 2-arg getattr
    (AttributeError on the missing attr) all bite; getattr(obj->None) arms
    return the DEFAULT silently there, so the PRESENT-settings twin (26/27/
    False, values that differ from every shipped default) is the second
    drive - getattr(None, ..., 26) yields 24 and mismatches. The clock
    stub now(tz) RAISES TypeError on now(None) - UTC-ness pinned
    env-independently, no TZ games.

LEDGER CANDIDATE (pre-adjudicated, env-independent proof; disposition is
CONFIRMED only if the key SURVIVES this battery's run - adjudication rule:
body-diff + sweep, never tolerance):
  * run_cleanup m2 `job_id: str | None = ""` - DEAD INITIALIZER. job_id
    is unconditionally RE-ASSIGNED by `job_id = self._job_tracker.
    create_job(...)` whenever the tracker branch runs; every READ of
    job_id sits inside `if self._job_tracker and job_id:` which
    short-circuits on the falsy tracker BEFORE reading job_id. So when the
    initializer value survives (tracker None) nothing ever reads it; when
    read, it was already overwritten. Same shape as the vlm analyze_batch
    m41/m43 dead initializers (M51 EQUIV precedent, env-independent). The
    battery still drives BOTH worlds (create_job -> "" with a live
    tracker; tracker absent) so a future refactor that makes the value
    observable trips a DRIVE, not the ledger.
  * _extract_event_id_from_path m12 `r"event..." -> r"EVENT..."` under
    `re.IGNORECASE` - SEMANTIC CLONE. The flag is on the SAME re.search
    call in shipped and mutant (body-diff changes only the literal's
    case), so the compiled matcher is identical for every input string:
    no environment can separate the two. Witness test
    test_event_id_patterns_are_case_invariant pins every shipped case
    combo so a future removal of IGNORECASE trips a DRIVE, not the
    ledger.

Key numbers cited in comments (m14, m2, m50...) are the b49-era tree
spellings (371 keys, /home/agent/runs/b49-survivor-diffs.txt); if this
battery grows covered lines the generation RENUMBERS and every disposition
is adjudicated by KEY NAME + BODY, never by number (renumber pitfall).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shutil
import tempfile
import types
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.dialects import postgresql

from backend.services import orphan_cleanup_service as oc

JOB_TYPE = "orphan_cleanup"  # oc.JOB_TYPE_ORPHAN_CLEANUP read via the pins
TS = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_MISSING_TZ = object()


# ---------------------------------------------------------------------------
# Harness helpers (b30-clean: no fixtures, no monkeypatch, no parametrize)
# ---------------------------------------------------------------------------


class _Patcher:
    """Minimal attribute save/restore (no monkeypatch in the b30 harness)."""

    def __init__(self, *triples: tuple[Any, str, Any]) -> None:
        self.triples = triples
        self.saved: list[tuple[Any, str, Any]] = []

    def __enter__(self) -> None:
        for obj, attr, value in self.triples:
            self.saved.append((obj, attr, getattr(obj, attr)))
            setattr(obj, attr, value)

    def __exit__(self, *exc: Any) -> bool:
        for obj, attr, value in reversed(self.saved):
            setattr(obj, attr, value)
        return False


class StubSettings:
    """Settings twin whose values DIFFER from every shipped default
    (26/27/False) - the getattr READS its settings object."""

    clips_directory = "data/clips"
    orphan_cleanup_scan_interval_hours = 26
    orphan_cleanup_age_threshold_hours = 27
    orphan_cleanup_enabled = False


class StrippedSettings:
    """Twin WITHOUT the three orphan_cleanup_* attrs: forces the getattr
    FALLBACK arms live and makes the 2-arg-getattr and getattr(None,...)
    arms observable - the real Settings shadows both."""

    clips_directory = "data/clips"


class Clock:
    """datetime twin: now() REQUIRES a tz argument (raises TypeError on the
    now(None) arm - pins UTC-ness env-independently)."""

    @staticmethod
    def now(tz: Any = _MISSING_TZ) -> datetime:
        if tz is _MISSING_TZ or tz is None:
            raise TypeError("clock requires a tz argument")
        return TS


class LogCollector(logging.Handler):
    """Collects records off oc.logger (DEBUG level, propagation off)."""

    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class CollectorCtx:
    def __init__(self) -> None:
        self.collector = LogCollector()
        self._old_level = 0
        self._old_propagate = False

    def __enter__(self) -> LogCollector:
        self._old_level = oc.logger.level
        self._old_propagate = oc.logger.propagate
        oc.logger.addHandler(self.collector)
        oc.logger.setLevel(logging.DEBUG)
        oc.logger.propagate = False
        return self.collector

    def __exit__(self, *exc: Any) -> bool:
        oc.logger.removeHandler(self.collector)
        oc.logger.setLevel(self._old_level)
        oc.logger.propagate = self._old_propagate
        return False


def info_msgs(records: list[logging.LogRecord]) -> list[str]:
    return [r.getMessage() for r in records if r.levelno == logging.INFO]


class RecordingTracker:
    """JobTracker twin with a FIXED positional signature - a dropped arg is
    a TypeError at the call; a reorder or None-swap breaks tuple equality.
    create_job returns the configured job id (drives pick truthy/falsy)."""

    def __init__(self, job_id: str = "J-42") -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self._id = job_id

    def create_job(self, job_type: str) -> str:
        self.calls.append(("create_job", (job_type,), {}))
        return self._id

    def start_job(self, job_id: str, message: str | None = None) -> None:
        self.calls.append(("start_job", (job_id,), {"message": message}))

    def update_progress(self, job_id: str, progress: int, message: str | None = None) -> None:
        self.calls.append(("update_progress", (job_id, progress), {"message": message}))

    def complete_job(self, job_id: str, result: Any = None) -> None:
        self.calls.append(("complete_job", (job_id,), {"result": result}))

    def fail_job(self, job_id: str, error: str) -> None:
        self.calls.append(("fail_job", (job_id, error), {}))


class FakeResult:
    def __init__(self, row: Any) -> None:
        self._row = row

    def scalar_one_or_none(self) -> Any:
        return self._row


class FakeSession:
    """Session twin keyed by SQL-text needles. execute() records the
    compiled statement (literal_binds) then answers by FIRST matching
    needle (insertion order); an Exception value raises at execute time;
    unmatched queries answer None."""

    def __init__(self, table: dict[str, Any]) -> None:
        self.table = table
        self.sqls: list[str] = []

    async def execute(self, stmt: Any) -> FakeResult:
        sql = str(
            stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        )
        self.sqls.append(sql)
        for needle, outcome in self.table.items():
            if needle and needle in sql:
                if isinstance(outcome, Exception):
                    raise outcome
                return FakeResult(outcome)
        return FakeResult(None)

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class BoomGen:
    """get_session replacement that PROVES no session was opened."""

    def __init__(self) -> None:
        self.count = 0

    def __call__(self) -> BoomGen:
        self.count += 1
        raise AssertionError("get_session must not be called in this drive")


class StatBoomPath(Path):
    """Path twin with a clean str form whose stat() raises OSError - pins
    the age-error leg with a deterministic message (a real missing file
    would leak the random tmpdir into the expected text)."""

    def stat(self) -> os.stat_result:  # type: ignore[override]
        raise OSError("stat boom")


class ExistsBoomPath(Path):
    """Path twin whose exists() raises - drives _delete_file's except arm
    with a deterministic path in the warning text."""

    def exists(self) -> bool:  # type: ignore[override]
        raise RuntimeError("perm")


class GlobDir:
    """Clips-dir twin: exists() True, glob() raises the configured error."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    def exists(self) -> bool:
        return True

    def glob(self, pattern: str) -> list[Path]:
        raise self.error


class SpyBroadcaster:
    """Sync recorder; payload TYPE is validated AT CALL TIME so an arg
    str(None)-swap raises exactly at the broadcast instead of masquerading
    in later stats equality."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, Any]] = []

    def __call__(self, event_type: Any, data: Any) -> None:
        if not isinstance(event_type, str) or not isinstance(data, dict):
            raise AssertionError(f"non-str broadcast args: {event_type!r} {data!r}")
        self.calls.append((event_type, data))


def _mk_service(
    clips: Path | None = None,
    *,
    tracker: Any = None,
    cb: Any = None,
    age: int = 24,
    interval: int = 24,
    enabled: bool = True,
) -> Any:
    """Service twin WITHOUT __init__ (the __init__ keys have their own
    drives): attributes set directly, no settings read, no log line."""
    svc = oc.OrphanedFileCleanupService.__new__(oc.OrphanedFileCleanupService)
    svc.scan_interval_hours = interval
    svc.age_threshold_hours = age
    svc.clips_directory = clips if clips is not None else Path("/nonexistent-az-dummy")
    svc.enabled = enabled
    svc._job_tracker = tracker
    svc._broadcast_callback = cb
    svc._cleanup_task = None
    svc.running = False
    return svc


def _mk_clips(names: dict[str, int], age_seconds: float) -> str:
    """Create clip files mtime-adjusted RELATIVE TO TS (the Clock stub's
    now) - drives that do NOT patch oc.datetime must use real-now ages."""
    d = tempfile.mkdtemp()
    for name, size in names.items():
        p = Path(d) / name
        p.write_bytes(b"x" * size)
        os.utime(p, (TS.timestamp() - age_seconds, TS.timestamp() - age_seconds))
    return d


def _rm(path: str) -> None:
    with contextlib.suppress(OSError):
        shutil.rmtree(path, ignore_errors=True)


def _stats_dict(scn: int, orp: int, del_: int, young: int, space: int) -> dict[str, int]:
    return {
        "files_scanned": scn,
        "orphans_found": orp,
        "files_deleted": del_,
        "files_skipped_young": young,
        "space_reclaimed": space,
    }


def _repr_of(scn: int, orp: int, del_: int, young: int, space: int) -> str:
    return (
        f"<OrphanedFileCleanupStats(scanned={scn}, orphans={orp}, "
        f"deleted={del_}, skipped_young={young}, space={space} bytes)>"
    )


# ---------------------------------------------------------------------------
# get_orphan_cleanup_service: the singleton FORWARDS every kwarg verbatim
# ---------------------------------------------------------------------------


def test_singleton_forwards_every_kwarg_verbatim() -> None:
    """m3-m8 (value -> None) and m9-m14 (arg dropped) on the constructor
    call inside the singleton: every passed value differs from BOTH
    fallback oracles - the StubSettings getattr value (26/27/False/
    data/clips) AND the shipped getattr default (24/24/True) that the
    getattr(None, ...) arms would hand back. enabled rides True here
    (stub False, default True - the row-1 lesson: driving enabled=False
    while the stub is False too made the None/drop arms invisible).
    ANY drop or None-swap at the call site falls through to a different
    value and the attr asserts mismatch."""
    d = tempfile.mkdtemp()
    tr, cb = RecordingTracker(), SpyBroadcaster()
    try:
        with _Patcher((oc, "get_settings", StubSettings)):
            oc.reset_orphan_cleanup_service()
            try:
                svc = oc.get_orphan_cleanup_service(
                    scan_interval_hours=3,
                    age_threshold_hours=5,
                    clips_directory=d,
                    enabled=True,
                    job_tracker=tr,
                    broadcast_callback=cb,
                )
            finally:
                oc.reset_orphan_cleanup_service()
    finally:
        _rm(d)
    assert svc.scan_interval_hours == 3, svc.scan_interval_hours
    assert svc.age_threshold_hours == 5, svc.age_threshold_hours
    assert svc.clips_directory == Path(d), svc.clips_directory
    assert svc.enabled is True, svc.enabled
    assert svc._job_tracker is tr, svc._job_tracker
    assert svc._broadcast_callback is cb, svc._broadcast_callback


def test_singleton_is_created_once_and_reset_replaces_it() -> None:
    """`if _orphan_cleanup_service is None` identity contract: a second
    call returns the SAME object (a re-construction would re-apply
    defaults and lose scan_interval_hours=7); after reset the NEXT call
    builds a fresh instance (defaults 24 via the stub)."""
    d = tempfile.mkdtemp()
    try:
        with _Patcher((oc, "get_settings", StubSettings)):
            oc.reset_orphan_cleanup_service()
            try:
                first = oc.get_orphan_cleanup_service(scan_interval_hours=7, clips_directory=d)
                second = oc.get_orphan_cleanup_service()
                assert second is first, "second call must return the SAME singleton"
                assert second.scan_interval_hours == 7, "singleton was re-constructed"
                oc.reset_orphan_cleanup_service()
                third = oc.get_orphan_cleanup_service()
                assert third is not first, "reset must drop the singleton"
                assert third.scan_interval_hours == 26, third.scan_interval_hours
            finally:
                oc.reset_orphan_cleanup_service()
    finally:
        _rm(d)


# ---------------------------------------------------------------------------
# __init__: getattr arms driven from BOTH settings twins
# ---------------------------------------------------------------------------


def test_init_stripped_settings_yields_shipped_defaults() -> None:
    """settings WITHOUT the attrs: the getattr DEFAULTS are the live
    values - kills default 24->25, default ->None and the trailing-comma
    2-arg getattr (AttributeError on the missing attr). getattr(obj->None)
    arms return the SAME default here - the other twin catches them."""
    with _Patcher((oc, "get_settings", StrippedSettings)):
        svc = oc.OrphanedFileCleanupService()
    assert svc.scan_interval_hours == 24, svc.scan_interval_hours
    assert svc.age_threshold_hours == 24, svc.age_threshold_hours
    assert svc.enabled is True, svc.enabled
    assert svc.clips_directory == Path("data/clips"), svc.clips_directory


def test_init_present_settings_beats_shipped_defaults() -> None:
    """settings WITH attrs (26/27/False, all != shipped defaults): the
    getattr must READ settings - getattr(settings->None, ..., default)
    yields the shipped 24/24/True and mismatches."""
    with _Patcher((oc, "get_settings", StubSettings)):
        svc = oc.OrphanedFileCleanupService()
    assert svc.scan_interval_hours == 26, svc.scan_interval_hours
    assert svc.age_threshold_hours == 27, svc.age_threshold_hours
    assert svc.enabled is False, svc.enabled


def test_init_explicit_arguments_beat_settings() -> None:
    """Every explicit value differs from BOTH twins - the `x if x is not
    None else ...` ternaries take the explicit side; also pins the
    bookkeeping attrs and that __init__ spawns nothing."""
    d = tempfile.mkdtemp()
    tr, cb = RecordingTracker(), SpyBroadcaster()
    try:
        with _Patcher((oc, "get_settings", StubSettings)):
            svc = oc.OrphanedFileCleanupService(
                scan_interval_hours=2,
                age_threshold_hours=3,
                clips_directory=d,
                enabled=False,
                job_tracker=tr,
                broadcast_callback=cb,
            )
    finally:
        _rm(d)
    assert svc.scan_interval_hours == 2, svc.scan_interval_hours
    assert svc.age_threshold_hours == 3, svc.age_threshold_hours
    assert svc.clips_directory == Path(d), svc.clips_directory
    assert svc.enabled is False, svc.enabled
    assert svc._job_tracker is tr
    assert svc._broadcast_callback is cb
    assert svc.running is False
    assert svc._cleanup_task is None


def test_init_logs_the_resolved_configuration_exactly() -> None:
    """m51: the multi-part f-string is the observable - full-message
    equality on the joined literal with the interpolated values fixed by
    the explicit drive."""
    with CollectorCtx() as log, _Patcher((oc, "get_settings", StubSettings)):
        oc.OrphanedFileCleanupService(
            scan_interval_hours=7, age_threshold_hours=9, clips_directory="data/z", enabled=False
        )
    expected = (
        "OrphanedFileCleanupService initialized: "
        "interval=7h, age_threshold=9h, "
        "clips_dir=data/z, enabled=False"
    )
    infos = info_msgs(log.records)
    assert infos == [expected], infos


# ---------------------------------------------------------------------------
# _scan_clip_files (four log-only survivors)
# ---------------------------------------------------------------------------


def test_scan_missing_directory_logs_the_exact_debug_and_returns_empty() -> None:
    parent = tempfile.mkdtemp()
    missing = Path(parent) / "nope"
    _rm(parent)
    svc = _mk_service(missing)
    with CollectorCtx() as log:
        files = svc._scan_clip_files()
    assert files == [], files
    assert len(log.records) == 1, [r.getMessage() for r in log.records]
    assert log.records[0].levelno == logging.DEBUG
    assert log.records[0].getMessage() == f"Clips directory does not exist: {missing}"


def test_scan_found_count_debug_is_exact() -> None:
    d = _mk_clips({"a.mp4": 10, "b.webm": 20, "c.mkv": 30}, 3600)
    try:
        svc = _mk_service(Path(d))
        with CollectorCtx() as log:
            files = svc._scan_clip_files()
        assert len(files) == 3, files
        deb = [r for r in log.records if r.levelno == logging.DEBUG]
        assert len(deb) == 1, [r.getMessage() for r in log.records]
        assert deb[0].getMessage() == f"Found 3 clip files in {Path(d)}", deb[0].getMessage()
    finally:
        _rm(d)


def test_scan_permission_error_logs_the_exact_warning() -> None:
    svc = _mk_service()
    svc.clips_directory = GlobDir(PermissionError("nope"))
    with CollectorCtx() as log:
        files = svc._scan_clip_files()
    assert files == [], files
    warns = [r for r in log.records if r.levelno == logging.WARNING]
    assert len(warns) == 1, [r.getMessage() for r in log.records]
    assert warns[0].getMessage() == "Permission denied scanning clips directory: nope"


def test_scan_generic_error_logs_the_exact_warning() -> None:
    svc = _mk_service()
    svc.clips_directory = GlobDir(RuntimeError("gg"))
    with CollectorCtx() as log:
        files = svc._scan_clip_files()
    assert files == [], files
    warns = [r for r in log.records if r.levelno == logging.WARNING]
    assert len(warns) == 1, [r.getMessage() for r in log.records]
    assert warns[0].getMessage() == "Error scanning clips directory: gg"


# ---------------------------------------------------------------------------
# _is_file_old_enough
# ---------------------------------------------------------------------------


def test_age_exact_boundary_is_deletable() -> None:
    """>= vs > at the EXACT threshold second (age == 10h, threshold 10):
    shipped True, _is_file_old_enough m7 False."""
    d = _mk_clips({"b.mp4": 5}, 10 * 3600)
    try:
        svc = _mk_service(Path(d), age=10)
        with _Patcher((oc, "datetime", Clock)):
            assert svc._is_file_old_enough(Path(d) / "b.mp4") is True
    finally:
        _rm(d)


def test_age_one_hour_young_is_not_deletable() -> None:
    """-/+3600 -> *3600 swaps a 1h-old file against threshold 10 into True
    (12,960,000 "hours"); equality on False is the pin."""
    d = _mk_clips({"b.mp4": 5}, 3600)
    try:
        svc = _mk_service(Path(d), age=10)
        with _Patcher((oc, "datetime", Clock)):
            assert svc._is_file_old_enough(Path(d) / "b.mp4") is False
    finally:
        _rm(d)


def test_age_divisor_is_3600_not_3601() -> None:
    """File 3600*24+12 s old vs threshold 24: True shipped (24.00333h),
    False under /3601 (23.99667h) - the ONLY divergence the +-1 divisor
    allows, and the exact place the _is_file_old_enough m6 arm is
    observable."""
    d = _mk_clips({"b.mp4": 5}, 24 * 3600 + 12)
    try:
        svc = _mk_service(Path(d), age=24)
        with _Patcher((oc, "datetime", Clock)):
            assert svc._is_file_old_enough(Path(d) / "b.mp4") is True
    finally:
        _rm(d)


def test_age_clock_requires_utc_argument() -> None:
    """_is_file_old_enough m5 datetime.now(->None): the Clock stub raises TypeError when
    called without a tz - if the shipped UTC-ness is mutated the drive
    ERRORS (TypeError is NOT in the caught OSError tuple, so it propagates
    and reddens) instead of silently reading a naive timestamp."""
    d = _mk_clips({"b.mp4": 5}, 100 * 3600)
    try:
        svc = _mk_service(Path(d), age=24)
        with _Patcher((oc, "datetime", Clock)):
            assert svc._is_file_old_enough(Path(d) / "b.mp4") is True
    finally:
        _rm(d)


def test_age_stat_error_logs_the_exact_debug_and_is_false() -> None:
    """OSError leg: message equality with BOTH the path (StatBoomPath
    keeps it deterministic) and the exception text."""
    svc = _mk_service(age=1)
    p = StatBoomPath("/nonexistent-az/b.mp4")
    with CollectorCtx() as log:
        assert svc._is_file_old_enough(p) is False
    assert len(log.records) == 1, [r.getMessage() for r in log.records]
    assert log.records[0].levelno == logging.DEBUG
    assert log.records[0].getMessage() == f"Could not check file age for {p}: stat boom"


# ---------------------------------------------------------------------------
# _extract_event_id_from_path
# ---------------------------------------------------------------------------


def test_event_id_patterns_are_case_invariant() -> None:
    """m12: the pattern r"event..." -> r"EVENT..." under re.IGNORECASE
    STOPS matching lowercase subjects - every shipped-identical case combo
    is asserted, including the lower-case subjects the m12 arm cannot
    match."""
    svc = _mk_service()
    assert svc._extract_event_id_from_path("/clips/event_123.mp4") == 123
    assert svc._extract_event_id_from_path("/clips/clip_event_456.webm") == 456
    assert svc._extract_event_id_from_path("/clips/clip_EVENT_999.mp4") == 999
    assert svc._extract_event_id_from_path("/clips/event-77.mp4") == 77
    assert svc._extract_event_id_from_path("/clips/789_clip.mp4") == 789
    assert svc._extract_event_id_from_path("/clips/42.mp4") == 42
    assert svc._extract_event_id_from_path("/clips/noclip_here.mp4") is None


# ---------------------------------------------------------------------------
# _is_orphan + _check_file_not_in_database: the SQL trace is the pin
# ---------------------------------------------------------------------------


def test_is_orphan_unknown_id_falls_back_to_clip_path_query_with_the_real_path() -> None:
    """No event id in the name -> _check_file_not_in_database(file_path).
    The recorded query carries the REAL path (the file_path->None arm
    renders `IS NULL`); the debug line is equality-pinned."""
    fs = FakeSession({})
    svc = _mk_service()
    path = "/clipsdir/random_name.mp4"
    with _Patcher((oc, "get_session", lambda: fs)), CollectorCtx() as log:
        got = asyncio.run(svc._is_orphan(path))
    assert got is True, got
    assert fs.sqls == [
        "SELECT events.id \nFROM events \nWHERE events.clip_path = '/clipsdir/random_name.mp4'"
    ], fs.sqls
    assert any(
        r.levelno == logging.DEBUG
        and r.getMessage() == f"Could not extract event ID from {path}, checking clip_path"
        for r in log.records
    ), [r.getMessage() for r in log.records]


def test_is_orphan_missing_event_logs_the_exact_debug() -> None:
    fs = FakeSession({"WHERE events.id = 77": None})
    svc = _mk_service()
    path = "/x/event_77.mp4"
    with _Patcher((oc, "get_session", lambda: fs)), CollectorCtx() as log:
        got = asyncio.run(svc._is_orphan(path))
    assert got is True
    assert fs.sqls == ["SELECT events.id \nFROM events \nWHERE events.id = 77"], fs.sqls
    assert any(
        r.levelno == logging.DEBUG
        and r.getMessage() == f"Event 77 not found - file is orphan: {path}"
        for r in log.records
    ), [r.getMessage() for r in log.records]


def test_is_orphan_event_exists_file_unreferenced_queries_both_in_order() -> None:
    """Two statements with EXACT text in EXACT order (id lookup, then
    clip_path lookup); True verdict; exact debug text."""
    fs = FakeSession({"WHERE events.clip_path = ": None, "WHERE events.id = 7": 7})
    svc = _mk_service()
    path = "/x/event_7.mp4"
    with _Patcher((oc, "get_session", lambda: fs)), CollectorCtx() as log:
        got = asyncio.run(svc._is_orphan(path))
    assert got is True
    assert fs.sqls == [
        "SELECT events.id \nFROM events \nWHERE events.id = 7",
        "SELECT events.id \nFROM events \nWHERE events.clip_path = '/x/event_7.mp4'",
    ], fs.sqls
    assert any(
        r.levelno == logging.DEBUG
        and r.getMessage() == f"File not referenced by event 7 - orphan: {path}"
        for r in log.records
    ), [r.getMessage() for r in log.records]


def test_is_orphan_referenced_file_is_not_orphan_and_warns_nothing() -> None:
    """The False arm: the clip_path query FINDS the row; exact two-query
    trace; no WARNING or above."""
    fs = FakeSession({"WHERE events.clip_path = ": 9, "WHERE events.id = 7": 7})
    svc = _mk_service()
    with _Patcher((oc, "get_session", lambda: fs)), CollectorCtx() as log:
        got = asyncio.run(svc._is_orphan("/x/event_7.mp4"))
    assert got is False
    assert len(fs.sqls) == 2, fs.sqls
    assert fs.sqls[1] == (
        "SELECT events.id \nFROM events \nWHERE events.clip_path = '/x/event_7.mp4'"
    )
    assert not [r for r in log.records if r.levelno >= logging.WARNING]


def test_is_orphan_session_error_logs_the_exact_error_and_keeps_the_file() -> None:
    fs = FakeSession({"\nFROM events": RuntimeError("db boom")})
    svc = _mk_service()
    path = "/x/event_7.mp4"
    with _Patcher((oc, "get_session", lambda: fs)), CollectorCtx() as log:
        got = asyncio.run(svc._is_orphan(path))
    assert got is False
    errs = [r for r in log.records if r.levelno >= logging.ERROR]
    assert len(errs) == 1, [r.getMessage() for r in log.records]
    assert errs[0].getMessage() == f"Error checking orphan status for {path}: db boom"


def test_check_file_not_in_database_true_and_sql_trace() -> None:
    fs = FakeSession({})
    svc = _mk_service()
    with _Patcher((oc, "get_session", lambda: fs)):
        assert asyncio.run(svc._check_file_not_in_database("/p/clip_a.mp4")) is True
    assert fs.sqls == [
        "SELECT events.id \nFROM events \nWHERE events.clip_path = '/p/clip_a.mp4'"
    ], fs.sqls


def test_check_file_not_in_database_false_when_referenced() -> None:
    fs = FakeSession({"WHERE events.clip_path = ": 1})
    svc = _mk_service()
    with _Patcher((oc, "get_session", lambda: fs)):
        assert asyncio.run(svc._check_file_not_in_database("/p/clip_b.mp4")) is False


def test_check_file_not_in_database_error_logs_exact_and_is_false() -> None:
    """_check_file_not_in_database m7 logger.error(->None): the exact
    interpolated message is the pin."""
    fs = FakeSession({"\nFROM events": RuntimeError("db down")})
    svc = _mk_service()
    with _Patcher((oc, "get_session", lambda: fs)), CollectorCtx() as log:
        assert asyncio.run(svc._check_file_not_in_database("/p/clip_c.mp4")) is False
    errs = [r for r in log.records if r.levelno >= logging.ERROR]
    assert len(errs) == 1, [r.getMessage() for r in log.records]
    assert errs[0].getMessage() == "Error checking database for /p/clip_c.mp4: db down"


# ---------------------------------------------------------------------------
# _delete_file (two log-only survivors)
# ---------------------------------------------------------------------------


def test_delete_file_success_logs_exact_debug_and_reports_size() -> None:
    d = _mk_clips({"gone.mp4": 123}, 10)
    try:
        svc = _mk_service(Path(d))
        target = Path(d) / "gone.mp4"
        with CollectorCtx() as log:
            ok, size = svc._delete_file(target)
        assert (ok, size) == (True, 123)
        assert not target.exists()
        assert len(log.records) == 1, [r.getMessage() for r in log.records]
        assert log.records[0].levelno == logging.DEBUG
        assert log.records[0].getMessage() == f"Deleted orphan file: {target} ({123} bytes)", (
            log.records[0].getMessage()
        )
    finally:
        _rm(d)


def test_delete_file_error_logs_exact_warning() -> None:
    svc = _mk_service()
    p = ExistsBoomPath("/nonexistent-az/q.mp4")
    with CollectorCtx() as log:
        assert svc._delete_file(p) == (False, 0)
    warns = [r for r in log.records if r.levelno == logging.WARNING]
    assert len(warns) == 1, [r.getMessage() for r in log.records]
    assert warns[0].getMessage() == f"Failed to delete file {p}: perm"


# ---------------------------------------------------------------------------
# _broadcast + _broadcast_completion
# ---------------------------------------------------------------------------


def test_broadcast_sync_callback_receives_args_verbatim() -> None:
    """The callback IS the product: args identity, no warning emitted."""
    cb = SpyBroadcaster()
    svc = _mk_service(cb=cb)
    payload = {"type": "t", "data": {"k": 1}}
    with CollectorCtx() as log:
        svc._broadcast("evt_x", payload)
    assert cb.calls == [("evt_x", payload)], cb.calls
    assert not [r for r in log.records if r.levelno >= logging.WARNING]


def test_broadcast_async_callback_without_loop_is_run_to_completion() -> None:
    """No running loop -> asyncio.run(result) executes the coroutine.
    _broadcast m10 asyncio.run(->None) raises TypeError -> caught ->
    WARNING emitted and the coroutine never runs (seen stays empty)."""
    seen: list[tuple[Any, Any]] = []

    async def cb(event_type: Any, data: Any) -> None:
        seen.append((event_type, data))

    svc = _mk_service(cb=cb)
    with CollectorCtx() as log:
        svc._broadcast("evt_a", {"n": 1})  # SYNC drive: no running loop
    assert seen == [("evt_a", {"n": 1})], seen
    assert not [r for r in log.records if r.levelno >= logging.WARNING]


def test_broadcast_async_callback_with_loop_is_scheduled_as_task() -> None:
    """Running-loop branch: loop.create_task(result) - one await yields
    the task its first step; the callback really ran."""
    seen: list[tuple[Any, Any]] = []

    async def cb(event_type: Any, data: Any) -> None:
        seen.append((event_type, data))

    svc = _mk_service(cb=cb)

    async def drive() -> None:
        svc._broadcast("evt_b", {"n": 2})
        await asyncio.sleep(0)

    asyncio.run(drive())
    assert seen == [("evt_b", {"n": 2})], seen


def test_broadcast_callback_exception_logs_exact_warning_and_extras() -> None:
    """The full warning surface: message EQUALITY + record.event_type +
    record.error - key renames (attribute vanishes), dropped extra=
    (AttributeError -> getattr default None mismatch), XX/case message
    text and the str(None) error value ALL mismatch."""

    def cb(event_type: Any, data: Any) -> None:
        raise RuntimeError("cb boom")

    svc = _mk_service(cb=cb)
    with CollectorCtx() as log:
        svc._broadcast("evt_f", {"z": 3})
    warns = [r for r in log.records if r.levelno == logging.WARNING]
    assert len(warns) == 1, [r.getMessage() for r in log.records]
    assert warns[0].getMessage() == "Failed to broadcast orphan cleanup event"
    assert getattr(warns[0], "event_type", None) == "evt_f"
    assert getattr(warns[0], "error", None) == "cb boom"


def test_broadcast_completion_payload_is_the_shipped_shape() -> None:
    """Full payload shape: event type, the "type" KEY and value, nested
    data["stats"] dict equality, and the timestamp KEY plus its UTC-ISO
    shape (renamed key -> KeyError on data["timestamp"]; a naive datetime
    -> no +00:00 suffix; now(->None) on the REAL datetime yields a NAIVE
    stamp - the suffix equality is what sees it, env-independent)."""
    cb = SpyBroadcaster()
    svc = _mk_service(cb=cb)
    stats = oc.OrphanedFileCleanupStats()
    stats.files_scanned, stats.orphans_found = 3, 2
    stats.files_deleted, stats.files_skipped_young, stats.space_reclaimed = 2, 1, 456
    with CollectorCtx() as log:
        svc._broadcast_completion(stats)
    warns = [r for r in log.records if r.levelno >= logging.WARNING]
    assert not warns, [r.getMessage() for r in warns]
    assert len(cb.calls) == 1, cb.calls
    event_type, payload = cb.calls[0]
    assert event_type == "orphan_cleanup_completed", event_type
    assert payload["type"] == "orphan_cleanup_completed", payload
    data = payload["data"]
    assert data["stats"] == _stats_dict(3, 2, 2, 1, 456), data
    ts = data["timestamp"]
    assert isinstance(ts, str) and ts.endswith("+00:00"), ts
    assert datetime.fromisoformat(ts).utcoffset().total_seconds() == 0


# ---------------------------------------------------------------------------
# Lifecycle: start / stop / async-context order pins
# ---------------------------------------------------------------------------


def test_start_when_already_running_logs_exact_warning_and_does_nothing() -> None:
    svc = _mk_service()
    svc.running = True
    with CollectorCtx() as log:
        asyncio.run(svc.start())
    assert svc.running is True
    assert svc._cleanup_task is None
    warns = [r for r in log.records if r.levelno == logging.WARNING]
    assert len(warns) == 1, [r.getMessage() for r in log.records]
    assert warns[0].getMessage() == "OrphanedFileCleanupService already running"
    assert info_msgs(log.records) == [], info_msgs(log.records)


def test_start_when_disabled_logs_exact_info_and_stays_stopped() -> None:
    svc = _mk_service(enabled=False)
    with CollectorCtx() as log:
        asyncio.run(svc.start())
    assert svc.running is False
    assert svc._cleanup_task is None
    assert info_msgs(log.records) == ["OrphanedFileCleanupService is disabled, not starting"], (
        info_msgs(log.records)
    )


def test_start_success_logs_both_info_lines_in_order_and_spawns_task() -> None:
    """Exact INFO ORDER; the spawned task really runs the (stubbed) loop
    and is cancellable - a dropped create_task leaves _cleanup_task None,
    dropped/renamed INFO shrinks/breaks the list."""
    svc = _mk_service()
    entered: list[bool] = []

    async def stub_loop() -> None:
        entered.append(True)
        await asyncio.sleep(3600)

    async def drive() -> None:
        svc._cleanup_loop = stub_loop  # type: ignore[method-assign]
        await svc.start()
        await asyncio.sleep(0)
        assert svc.running is True
        assert svc._cleanup_task is not None
        svc._cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await svc._cleanup_task

    with CollectorCtx() as log:
        asyncio.run(drive())
    assert entered == [True], entered
    assert info_msgs(log.records) == [
        "Starting OrphanedFileCleanupService",
        "OrphanedFileCleanupService started successfully",
    ], info_msgs(log.records)


def test_stop_when_not_running_logs_exact_debug_and_touches_nothing() -> None:
    svc = _mk_service()
    with CollectorCtx() as log:
        asyncio.run(svc.stop())
    assert svc.running is False
    assert svc._cleanup_task is None
    deb = [r for r in log.records if r.levelno == logging.DEBUG]
    assert len(deb) == 1, [r.getMessage() for r in log.records]
    assert deb[0].getMessage() == "OrphanedFileCleanupService not running, nothing to stop"
    assert info_msgs(log.records) == [], info_msgs(log.records)


def test_stop_cancels_the_task_and_logs_both_info_lines_in_order() -> None:
    """running=True with a live task: INFO order pinned; the task REALLY
    gets cancelled (cancelled() True); _cleanup_task cleared to None."""
    svc = _mk_service()

    async def drive() -> None:
        task = asyncio.create_task(asyncio.sleep(3600))  # cancelled by svc.stop() in this drive
        svc.running = True
        svc._cleanup_task = task
        await svc.stop()
        assert svc.running is False
        assert svc._cleanup_task is None
        assert task.cancelled()

    with CollectorCtx() as log:
        asyncio.run(drive())
    assert info_msgs(log.records) == [
        "Stopping OrphanedFileCleanupService",
        "OrphanedFileCleanupService stopped",
    ], info_msgs(log.records)


def test_aenter_starts_and_aexit_stops_the_service() -> None:
    """The async-context pair: a dropped `await self.stop()` leaves
    running True / a live task; a dropped `await self.start()` never
    spawns it. (Mutants on these two-line methods, if the run births any,
    die here.)"""
    svc = _mk_service()

    async def stub_loop() -> None:
        await asyncio.sleep(3600)

    async def drive() -> tuple[bool, bool]:
        svc._cleanup_loop = stub_loop  # type: ignore[method-assign]
        async with svc as ctx:
            spawned = ctx._cleanup_task is not None
            await asyncio.sleep(0)
        return spawned, ctx.running

    spawned, running_after = asyncio.run(drive())
    assert spawned is True
    assert running_after is False


# ---------------------------------------------------------------------------
# _cleanup_loop
# ---------------------------------------------------------------------------


def test_cleanup_loop_happy_path_waits_the_exact_interval_and_stops_clean() -> None:
    """One cleanup, sleep EXACTLY scan_interval_hours * 3600 = 86400
    (/3600 -> 0.0067, *3601 -> 86424, None -> TypeError at the stub) and
    the exact INFO order started -> next-in -> stopped."""
    svc = _mk_service(interval=24)
    sleeps: list[Any] = []

    async def fake_sleep(secs: Any) -> None:
        sleeps.append(secs)
        svc.running = False

    async def stub_cleanup() -> None:
        pass

    async def drive() -> None:
        svc.running = True
        await svc._cleanup_loop()

    svc.run_cleanup = stub_cleanup  # type: ignore[method-assign]
    with _Patcher((asyncio, "sleep", fake_sleep)), CollectorCtx() as log:
        asyncio.run(drive())
    assert sleeps == [86400], sleeps
    assert info_msgs(log.records) == [
        "Orphan cleanup loop started",
        "Next orphan cleanup in 24 hours",
        "Orphan cleanup loop stopped",
    ], info_msgs(log.records)
    del svc.run_cleanup


def test_cleanup_loop_cancellation_logs_cancelled_then_stopped() -> None:
    """CancelledError arm (cancelled mid-cleanup, so the wait leg never
    logs): the `break` must still reach the final stopped INFO (m14
    break->return SKIPS it - the three-line INFO list is the kill) and the
    exact cancelled line is equality-pinned."""
    svc = _mk_service()

    async def stub_cleanup() -> None:
        raise asyncio.CancelledError

    async def drive() -> None:
        svc.running = True
        await svc._cleanup_loop()

    svc.run_cleanup = stub_cleanup  # type: ignore[method-assign]
    with CollectorCtx() as log:
        asyncio.run(drive())
    assert info_msgs(log.records) == [
        "Orphan cleanup loop started",
        "Orphan cleanup loop cancelled",
        "Orphan cleanup loop stopped",
    ], info_msgs(log.records)
    del svc.run_cleanup


def test_cleanup_loop_error_retries_after_sixty_with_exact_error() -> None:
    """Exception arm: ERROR message equality with str(e), exc_info a live
    exception tuple (logging normalizes True -> the sys.exc_info triple;
    ->None / trailing-comma drop / ->False all record exc_info None),
    sleep EXACTLY 60 (None raises at the stub, 61 mismatches), then the
    stopped INFO."""
    svc = _mk_service()
    sleeps: list[Any] = []
    state = {"first": True}

    async def fake_sleep(secs: Any) -> None:
        sleeps.append(secs)
        svc.running = False

    async def stub_cleanup() -> None:
        if state["first"]:
            state["first"] = False
            raise RuntimeError("loop boom")

    async def drive() -> None:
        svc.running = True
        await svc._cleanup_loop()

    svc.run_cleanup = stub_cleanup  # type: ignore[method-assign]
    with _Patcher((asyncio, "sleep", fake_sleep)), CollectorCtx() as log:
        asyncio.run(drive())
    assert sleeps == [60], sleeps
    errs = [r for r in log.records if r.levelno >= logging.ERROR]
    assert len(errs) == 1, [r.getMessage() for r in log.records]
    assert errs[0].getMessage() == "Error in orphan cleanup loop: loop boom"
    assert errs[0].exc_info is not None and errs[0].exc_info[0] is RuntimeError, errs[0].exc_info
    assert info_msgs(log.records) == [
        "Orphan cleanup loop started",
        "Orphan cleanup loop stopped",
    ], info_msgs(log.records)
    del svc.run_cleanup


# ---------------------------------------------------------------------------
# run_cleanup drives
# ---------------------------------------------------------------------------


def test_run_cleanup_no_files_completes_job_and_broadcasts_the_exact_pair() -> None:
    """Empty directory leg: create/start with exact job kwargs, NO
    progress, complete with the full zero-stats dict, completion broadcast
    with the full payload, INFO order [starting, no-clip-files]."""
    d = tempfile.mkdtemp()
    tr, cb = RecordingTracker("J-42"), SpyBroadcaster()
    try:
        svc = _mk_service(Path(d), tracker=tr, cb=cb, age=24)
        with CollectorCtx() as log:
            stats = asyncio.run(svc.run_cleanup())
        assert stats.to_dict() == _stats_dict(0, 0, 0, 0, 0), stats.to_dict()
        assert tr.calls[:2] == [
            ("create_job", (JOB_TYPE,), {}),
            ("start_job", ("J-42",), {"message": "Starting orphan cleanup scan"}),
        ], tr.calls
        completes = [c for c in tr.calls if c[0] == "complete_job"]
        assert completes == [("complete_job", ("J-42",), {"result": _stats_dict(0, 0, 0, 0, 0)})], (
            completes
        )
        assert not [c for c in tr.calls if c[0] in ("update_progress", "fail_job")]
        assert info_msgs(log.records) == [
            "Starting orphan cleanup (age_threshold: 24h)",
            "No clip files found to check",
        ], info_msgs(log.records)
        assert len(cb.calls) == 1, cb.calls
        event_type, payload = cb.calls[0]
        assert event_type == "orphan_cleanup_completed"
        assert payload["data"]["stats"] == stats.to_dict()
    finally:
        _rm(d)


def test_run_cleanup_no_files_falsy_job_id_skips_complete() -> None:
    """The `if self._job_tracker and job_id:` guard on the EARLY complete
    with job_id falsy: shipped calls create/start only; every `and`->`or`
    arm adds complete_job("", ...) - the call-name census is the kill."""
    d = tempfile.mkdtemp()
    tr, cb = RecordingTracker(""), SpyBroadcaster()
    try:
        svc = _mk_service(Path(d), tracker=tr, cb=cb, age=24)
        asyncio.run(svc.run_cleanup())
        names = [c[0] for c in tr.calls]
        assert names == ["create_job", "start_job"], names
        assert len(cb.calls) == 1, cb.calls
    finally:
        _rm(d)


def test_run_cleanup_empty_job_id_with_files_skips_progress_and_complete() -> None:
    """Same guards in the loop/complete legs: two young files with
    create_job -> "". Shipped: create/start only (progress and complete
    guards falsy); `and`->`or` arms add update_progress x2 + complete_job.
    Clock-patched so TS-relative mtimes decide age."""
    d = _mk_clips({"y1.mp4": 10, "y2.mp4": 20}, 60)
    tr = RecordingTracker("")
    try:
        svc = _mk_service(Path(d), tracker=tr, age=24)
        boom = BoomGen()
        with _Patcher((oc, "get_session", boom), (oc, "datetime", Clock)):
            stats = asyncio.run(svc.run_cleanup())
        names = [c[0] for c in tr.calls]
        assert names == ["create_job", "start_job"], names
        assert stats.to_dict()["files_skipped_young"] == 2, stats.to_dict()
        assert boom.count == 0, "young files must not touch the database"
    finally:
        _rm(d)


def test_run_cleanup_young_files_progress_counters_exact() -> None:
    """Two young files through the truthy-job-id path: progress 45 THEN 90
    EXACTLY (the *91 arm agrees on file 1 and diverges on file 2 - a
    single-file drive passes it), messages "1/2" then "2/2", skipped
    counter +1 each (the =1 arm -> 1, the +=2 arm -> 4), complete with the
    exact dict, INFO order with the full stats repr."""
    d = _mk_clips({"y1.mp4": 10, "y2.mp4": 20}, 60)
    tr = RecordingTracker("J-9")
    try:
        svc = _mk_service(Path(d), tracker=tr, age=24)
        boom = BoomGen()
        with (
            _Patcher((oc, "get_session", boom), (oc, "datetime", Clock)),
            CollectorCtx() as log,
        ):
            stats = asyncio.run(svc.run_cleanup())
        prog = [c for c in tr.calls if c[0] == "update_progress"]
        assert prog == [
            ("update_progress", ("J-9", 45), {"message": "Checking file 1/2"}),
            ("update_progress", ("J-9", 90), {"message": "Checking file 2/2"}),
        ], prog
        complete = [c for c in tr.calls if c[0] == "complete_job"]
        assert complete == [("complete_job", ("J-9",), {"result": _stats_dict(2, 0, 0, 2, 0)})], (
            complete
        )
        assert stats.to_dict() == _stats_dict(2, 0, 0, 2, 0), stats.to_dict()
        assert boom.count == 0
        assert info_msgs(log.records) == [
            "Starting orphan cleanup (age_threshold: 24h)",
            f"Orphan cleanup completed: {_repr_of(2, 0, 0, 2, 0)}",
        ], info_msgs(log.records)
    finally:
        _rm(d)


def test_run_cleanup_deletes_two_old_orphans_with_exact_stats_and_queries() -> None:
    """The core drive: two old event-missing orphans deleted. FULL stats
    equality (=1 / +=2 / -= arms), completion-payload stats equality, and
    the recorded-SQL TRACE (sorted - glob order is not contractual): the
    _is_orphan(str(->None)) arm keeps stats identical in shipped
    arithmetic but queries clip_path = 'None' - only the trace sees it.
    Real-now ages (threshold 1h vs 27.8h-old files) - no clock patch."""
    d = _mk_clips({"event_1.mp4": 100, "event_2.mp4": 100}, 100_000)
    cb = SpyBroadcaster()
    fs = FakeSession({"WHERE events.id = ": None})
    try:
        svc = _mk_service(Path(d), cb=cb, age=1)
        with _Patcher((oc, "get_session", lambda: fs)), CollectorCtx() as log:
            stats = asyncio.run(svc.run_cleanup())
        assert stats.to_dict() == _stats_dict(2, 2, 2, 0, 200), stats.to_dict()
        assert sorted(fs.sqls) == sorted(
            [
                "SELECT events.id \nFROM events \nWHERE events.id = 1",
                "SELECT events.id \nFROM events \nWHERE events.id = 2",
            ]
        ), fs.sqls
        payload = cb.calls[0][1]
        assert payload["data"]["stats"] == stats.to_dict(), payload
        assert info_msgs(log.records)[-1] == (
            f"Orphan cleanup completed: {_repr_of(2, 2, 2, 0, 200)}"
        ), info_msgs(log.records)
    finally:
        _rm(d)


def test_run_cleanup_per_file_error_is_isolated_with_exact_warning() -> None:
    """The per-file except arm: file A's _is_orphan raises -> exact WARN
    (path + str(e)); file B still deleted; PARTIAL stats (continue, not
    break - run_cleanup m48 break would stop the loop and lose file B... which comes
    FIRST in glob order for `break` too, so stats are the order-proof:
    break-after-poison sees either 1 or 2 scanned depending on glob order,
    equality on the exact dict pins both orders)."""
    d = _mk_clips({"poison.mp4": 70, "event_3.mp4": 30}, 100_000)
    fs = FakeSession({"WHERE events.id = ": None})
    try:
        svc = _mk_service(Path(d), age=1)
        original = oc.OrphanedFileCleanupService._is_orphan

        async def wrapped(self: Any, file_path: str) -> bool:
            if "poison" in file_path:
                raise RuntimeError("boom")
            with _Patcher((oc, "get_session", lambda: fs)):
                return await original(self, file_path)

        svc._is_orphan = types.MethodType(wrapped, svc)  # type: ignore[method-assign]
        with CollectorCtx() as log:
            stats = asyncio.run(svc.run_cleanup())
        assert stats.to_dict() == _stats_dict(2, 1, 1, 0, 30), stats.to_dict()
        warns = [r for r in log.records if r.levelno == logging.WARNING]
        assert len(warns) == 1, [r.getMessage() for r in log.records]
        assert warns[0].getMessage() == f"Error processing file {d}/poison.mp4: boom"
    finally:
        _rm(d)


def test_run_cleanup_scan_failure_fails_the_job_and_reraises() -> None:
    """Critical-failure arm: scan raises -> ERROR equality with exc_info a
    live exception tuple (True normalizes to the sys.exc_info triple; the
    None/dropped/False arms record None), fail_job EXACTLY (job_id,
    str(e)) - str(None) sends "None", the drop arms TypeError at the
    stub - complete NEVER, broadcast NEVER, original error re-raised."""
    tr = RecordingTracker("J-E")

    def boom() -> list[Path]:
        raise RuntimeError("scan boom")

    svc = _mk_service(tracker=tr, cb=SpyBroadcaster(), age=24)
    svc._scan_clip_files = boom  # type: ignore[method-assign]
    raised = None
    with CollectorCtx() as log:
        try:
            asyncio.run(svc.run_cleanup())
        except RuntimeError as e:
            raised = e
    assert raised is not None and str(raised) == "scan boom", raised
    names = [c[0] for c in tr.calls]
    assert names == ["create_job", "start_job", "fail_job"], names
    assert tr.calls[-1] == ("fail_job", ("J-E", "scan boom"), {}), tr.calls[-1]
    errs = [r for r in log.records if r.levelno >= logging.ERROR]
    assert len(errs) == 1, [r.getMessage() for r in log.records]
    assert errs[0].getMessage() == "Orphan cleanup failed: scan boom"
    assert errs[0].exc_info is not None and errs[0].exc_info[0] is RuntimeError, errs[0].exc_info


def test_run_cleanup_falsy_job_id_critical_skips_fail_job() -> None:
    """The `and`->`or` arm on the FAIL guard with job_id falsy: shipped
    never calls fail_job (guard falsy); the or-arm calls
    fail_job("", ...) - name census is the kill. The error still
    re-raises."""
    tr = RecordingTracker("")

    def boom() -> list[Path]:
        raise RuntimeError("zap")

    svc = _mk_service(tracker=tr, age=24)
    svc._scan_clip_files = boom  # type: ignore[method-assign]
    raised = None
    with contextlib.suppress(RuntimeError), CollectorCtx():
        try:
            asyncio.run(svc.run_cleanup())
        except RuntimeError as e:
            raised = e
    assert raised is not None and str(raised) == "zap", raised
    names = [c[0] for c in tr.calls]
    assert names == ["create_job", "start_job"], names


def test_run_cleanup_without_tracker_broadcasts_once_and_deletes() -> None:
    """tracker None: zero job calls, completion broadcast STILL fires
    (outside every tracker guard); real-now ages, orphan deleted."""
    d = _mk_clips({"e9.mp4": 50}, 100_000)
    cb = SpyBroadcaster()
    fs = FakeSession({"WHERE events.id = ": None})
    try:
        svc = _mk_service(Path(d), cb=cb, age=1)
        with _Patcher((oc, "get_session", lambda: fs)):
            stats = asyncio.run(svc.run_cleanup())
        assert stats.files_deleted == 1, stats
        assert len(cb.calls) == 1, cb.calls
        assert cb.calls[0][0] == "orphan_cleanup_completed"
        assert cb.calls[0][1]["data"]["stats"] == stats.to_dict()
    finally:
        _rm(d)


def test_run_cleanup_young_only_broadcasts_exactly_once() -> None:
    """Broadcast-position witness: young-only run reaches the END-of-loop
    completion (not the early-return one) - exactly one payload, correct
    type, and no DB touched (BoomGen proves the age filter ran first)."""
    d = _mk_clips({"young_one.mp4": 10}, 60)
    cb = SpyBroadcaster()
    try:
        svc = _mk_service(Path(d), cb=cb, age=24)
        boom = BoomGen()
        with _Patcher((oc, "get_session", boom), (oc, "datetime", Clock)):
            asyncio.run(svc.run_cleanup())
        assert boom.count == 0, boom.count
        assert len(cb.calls) == 1, cb.calls
        assert cb.calls[0][1]["type"] == "orphan_cleanup_completed"
    finally:
        _rm(d)
