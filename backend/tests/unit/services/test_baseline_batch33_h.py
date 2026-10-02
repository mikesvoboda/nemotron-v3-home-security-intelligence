# TARGET-MODULE: backend.services.baseline
"""Campaign #8 battery H: kill-real for backend/services/baseline.py survivors.

Campaign #8 (mutation ladder, 2026-09-30). 368 survivor keys, 51.96% module kt
before this battery. The shipped test_baseline.py suite mocks the AsyncSession
wholesale (AsyncMock everywhere), so EVERY statement-shape mutant -- the
select/update predicate flips, the EWMA arithmetic, the constructor args, the
ORDER BY columns, func.min, the dict-key literals -- survives: a mock happily
accepts ``session.execute(None)`` and never compiles SQL. This battery drives
REAL SQLAlchemy statements against an in-memory SQLite database (StaticPool so
every connection sees the same schema) through a tiny async facade. aiosqlite
is absent from both trees and the service only ever ``await``s the session, so
the facade is the sanctioned shim (same pattern as the config_service
batteries).

Controlled inputs: ``datetime.now`` is pinned to NOW = 2026-09-15 08:00 UTC
(hour 8, Tuesday -> day_of_week 1) by swapping the ``datetime`` attribute of
the module under test. Seeded ``last_updated`` deltas control time decay:
NOW-1d -> decay == 0.1 exactly at the service default decay_factor 0.1
(decay is PER DAY: factor ** days_elapsed); NOW-2d -> 0.01; NOW-31d -> outside the 30-day window -> 0.0 (stale reset);
same row as NOW -> decay == 1.0 exactly.

Honesty ledger -- keys this battery does NOT kill (all must sweep GREEN with
this battery loaded; registered EQUIVALENT only after the sweep proves it):
  * ``_update_activity_baseline__mutmut_25`` /
    ``_update_class_baseline__mutmut_25``: ``(1 - decay) * 1.0`` ->
    ``(1 - decay) / 1.0`` -- identity on every float.
  * ``is_anomalous__mutmut_28``, ``get_current_deviation__mutmut_2``:
    ``datetime.now(UTC)`` -> ``datetime.now(None)`` -- those ``now`` values
    flow ONLY into _calculate_time_decay, which normalises naive -> UTC, so
    no observable channel distinguishes them (sweep-proven GREEN).
    ``update_baseline__mutmut_4`` is NOT in this family: the spy-arg test
    pins the tz-aware ``now`` forwarded to the sub-updaters -> RED.
  * ``is_anomalous__mutmut_36``: ``class_frequency = 0.0`` init -> 1.0 -- the
    loop OVERWRITES class_frequency whenever the queried class appears among
    the summed rows (which is exactly when class_baseline is not None and
    rel matters); when the class never appears, class_baseline is None and
    the 1.0-score branch fires first. init value never observable.
  * ``is_anomalous__mutmut_62``: rel ternary else ``0.0`` -> 1.0 -- the else
    needs total_frequency == 0, which forces every decayed summand (and
    hence class_frequency) to 0.0, and the ``elif cf == 0.0`` branch returns
    0.95 before relative_frequency is ever read by the score.
  * ``get_current_deviation__mutmut_63``: ``z_score > 1.5`` -> ``>= 1.5`` --
    the max possible |z| over n same-hour rows is sqrt(n-1) (population
    std), so z == 1.5 needs a float needle only (n <= 3 caps at 1.414; n=4
    admits 1.732 -- the pinned 1.73 main case has z strictly off 1.5). The
    battery pins z on BOTH sides (0.0, -1.0, 1.73); exactly-1.5 is not
    reachable with representable seeds -- sweep must confirm GREEN.
  * ``get_hourly_patterns__mutmut_16`` (``if avg_counts`` ->
    ``(avg_counts or True)``), ``__mutmut_19`` (else-branch ``0.0`` ->
    ``1.0``), ``__mutmut_20`` (``len > 1`` -> ``>= 1``: the len == 1 path
    computes variance (x-x)**2/1 = 0 -> std 0.0 == the else value), ``get_daily_patterns__mutmut_42`` (guard upper bound
    ``< len(day_names)`` -> ``<= len(day_names)``, reachable only with
    day_of_week == 7, which the model CHECK constraint forbids),
    ``get_object_baselines__mutmut_18/__mutmut_20/__mutmut_22``
    (``hours_covered > 0`` family; len() of the grouped list is >= 1 by
    construction), ``__mutmut_27`` (``if hour_freq`` -> ``(hour_freq or
    True)``) and ``__mutmut_33`` (peak-hour else branch ``12`` -> ``1.0``);
    the guard lists are never empty on any path that reaches them.
  * ``is_anomalous__mutmut_78``: ``min(1.0, 1.0 - rel)`` -> ``min(2.0, ...)``
    -- relative_frequency is in [0, 1] because the queried class is always a
    member of the summed set with non-negative decayed frequencies, so
    1 - rel <= 1 and the cap never binds. (NUMBERING NOTE: this key number
    is the pre-run census; battery H's own coverage growth re-enumerated
    ``is_anomalous``'s mutant tail at generation, and the post-run bank
    carries this same mutation -- name-normalized byte-identical body -- as
    ``is_anomalous__mutmut_80``, while the NEW ``__mutmut_78`` slot is a
    single-argument ``min(1.0 - rel)`` that TypeErrors -> killed.)
  * ``get_current_deviation__mutmut_63``: ``z_score > 1.5`` -> ``>= 1.5`` --
    the z-score is shape-determined (scale-free) for the small row sets that
    satisfy the slot lookup, and no representable hour-group yields exactly
    1.5.
  * ``_calculate_time_decay`` and ``__init__`` message keys ARE killed here
    (message equality + init log capture) -- no registration.

Harness contract: module-level zero-arg test functions only (b30-sweep calls
them directly, no pytest), no fixtures, no parametrize, no patch.object (the
only patching is the module ``datetime`` swap and a spy subclass, so the
WP4.2 autospec ratchet is satisfied trivially).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.services.baseline as baseline_mod
from backend.models.baseline import ActivityBaseline, ClassBaseline

NOW = datetime(2026, 9, 15, 8, 0, 0, tzinfo=UTC)  # hour=8, day_of_week=1 (Tue)
TOL = 1e-9


class _DT(datetime):
    """datetime with a frozen ``now``; the module calls ``datetime.now(UTC)``."""

    @staticmethod
    def now(tz=None):
        return NOW if tz is not None else NOW.replace(tzinfo=None)


class _Result:
    """Wraps a sync SQLAlchemy result so it satisfies the async service API."""

    def __init__(self, inner):
        self._inner = inner

    def scalars(self):
        return _Result(self._inner.scalars())

    def all(self):
        return list(self._inner.all())

    def scalar_one_or_none(self):
        return self._inner.scalar_one_or_none()

    def scalar(self):
        return self._inner.scalar()


class _Sess:
    """Async facade over a sync SQLite Session; the service only awaits calls."""

    def __init__(self, inner):
        self._inner = inner

    async def execute(self, stmt, *args, **kwargs):
        return _Result(self._inner.execute(stmt, *args, **kwargs))

    def add(self, obj):
        self._inner.add(obj)


_REAL_DT = datetime


def _run(coro):
    """Drive a service coroutine with ``datetime`` pinned; restore after.

    The swap is scoped so a pytest session that also runs the shipped
    test_baseline.py never observes the frozen clock outside one of these
    calls (a leaked _DT would fake-red a later shipped test under -x).
    """
    baseline_mod.datetime = _DT
    try:
        return asyncio.run(coro)
    finally:
        baseline_mod.datetime = _REAL_DT


def _dt(v):
    """Raw text() SQL hands SQLite DATETIME back as str; normalise."""
    if isinstance(v, str):
        return datetime.fromisoformat(v)
    return v


def _mk_env():
    """Fresh SQLite env: returns (service, session-facade, sync session)."""
    eng = sa.create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    tables = [ActivityBaseline.__table__, ClassBaseline.__table__]
    # metadata.create_all (sa.create_all is not a public top-level in 2.x);
    # cameras table omitted: JSONB column, FKs unenforced without a PRAGMA
    ActivityBaseline.metadata.create_all(eng, tables=tables)
    inner = sessionmaker(bind=eng)()
    return baseline_mod.BaselineService(), _Sess(inner), inner


def _mk_svc(**kw):
    svc, s, inner = _mk_env()
    if kw:
        svc = baseline_mod.BaselineService(**kw)
    return svc, s, inner


def _act(cam, hour, dow, avg, cnt, lu):
    return ActivityBaseline(
        camera_id=cam,
        hour=hour,
        day_of_week=dow,
        avg_count=avg,
        sample_count=cnt,
        last_updated=lu,
    )


def _cls(cam, klass, hour, freq, cnt, lu):
    return ClassBaseline(
        camera_id=cam,
        detection_class=klass,
        hour=hour,
        frequency=freq,
        sample_count=cnt,
        last_updated=lu,
    )


def _act_rows(inner):
    """All activity rows as (camera, hour, dow, avg_count-or-None, count-or-None, lu).

    Raw column reads so NULLed values (from values(...)=None mutants) are
    distinguishable from ORM defaults.
    """
    q = sa.text(
        "SELECT camera_id, hour, day_of_week, avg_count, sample_count, last_updated"
        " FROM activity_baselines ORDER BY id"
    )
    return [(r[0], r[1], r[2], r[3], r[4], _dt(r[5])) for r in inner.execute(q)]


def _cls_rows(inner):
    q = sa.text(
        "SELECT camera_id, detection_class, hour, frequency, sample_count, last_updated"
        " FROM class_baselines ORDER BY id"
    )
    return [(r[0], r[1], r[2], r[3], r[4], _dt(r[5])) for r in inner.execute(q)]


class _ListHandler(logging.Handler):
    """Battery D/F/G idiom: collect records, ride the shipped ContextFilter."""

    def __init__(self, sink: list) -> None:
        super().__init__()
        self.sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        self.sink.append(record)


class LogCapture:
    def __init__(self) -> None:
        self.logger = logging.getLogger("backend.services.baseline")

    def __enter__(self) -> LogCapture:
        self.records: list[logging.LogRecord] = []
        self._handler = _ListHandler(self.records)
        found = [f for f in self.logger.filters if type(f).__name__ == "ContextFilter"]
        assert len(found) == 1, f"logger must carry exactly one ContextFilter, got {found}"
        self._handler.addFilter(found[0])
        self.logger.addHandler(self._handler)
        self._old_level = self.logger.level
        self.logger.setLevel(logging.DEBUG)
        return self

    def __exit__(self, *exc: object) -> None:
        self.logger.removeHandler(self._handler)
        self.logger.setLevel(self._old_level)

    @property
    def msgs(self) -> list:
        return [r.getMessage() for r in self.records]


# ---------------------------------------------------------------- tests --


def test_init_validation_messages():
    # XX-message mutants __init__ 7/12/17/22: equality on every message.
    for kw, msg in (
        ({"decay_factor": 0.0}, "decay_factor must be between 0 (exclusive) and 1 (inclusive)"),
        ({"window_days": 0}, "window_days must be at least 1"),
        ({"anomaly_threshold_std": -0.1}, "anomaly_threshold_std must be non-negative"),
        ({"min_samples": 0}, "min_samples must be at least 1"),
    ):
        try:
            baseline_mod.BaselineService(**kw)
        except ValueError as exc:
            assert str(exc) == msg, (kw, str(exc))
        else:
            raise AssertionError(f"no ValueError for {kw}")


def test_init_info_log_message():
    # __init__ mutmut_28: the f-string becomes None -> no record at all.
    with LogCapture() as cap:
        baseline_mod.BaselineService(
            decay_factor=0.5, window_days=7, anomaly_threshold_std=1.5, min_samples=3
        )
    assert (
        "BaselineService initialized: decay=0.5, window=7d, threshold=1.5std, "
        "min_samples=3" in cap.msgs
    ), cap.msgs


def test_calculate_time_decay_via_activity_rate():
    # _calculate_time_decay mutmut_10: /86400.0 -> /86401.0 shifts a 1h-old
    # row's decay by ~2.7e-7 -- visible in the product at 3.0 avg (diff 8e-7).
    svc, s, inner = _mk_svc()
    inner.add(_act("cam1", 8, 1, 3.0, 4, NOW - timedelta(days=1)))
    inner.commit()
    got = _run(svc.get_activity_rate("cam1", 8, 1, session=s))
    assert abs(got - 0.3) <= TOL, got


def test_interpret_z_score_boundaries():
    # mutmut_1/4/7/9/11: each ``<`` -> ``<=`` fires exactly at its boundary.
    svc, _s, _inner = _mk_svc()
    pins = [
        (-2.0, "below_normal"),
        (-1.0, "normal"),
        (1.0, "slightly_above_normal"),
        (2.0, "above_normal"),
        (3.0, "far_above_normal"),
    ]
    for z, want in pins:
        got = svc._interpret_z_score(z)
        assert got.value == want, (z, got)
    assert svc._interpret_z_score(-2.5).value == "far_below_normal"
    assert svc._interpret_z_score(0.0).value == "normal"
    assert svc._interpret_z_score(3.5).value == "far_above_normal"


def test_update_baseline_forwards_exact_args():
    # update_baseline mutmut_6..9 and 16..19: each sub-call argument swapped
    # for None. Spy subclass records the real call; NO patch.object.
    svc, s, inner = _mk_svc()
    calls: list[tuple] = []

    class _Spy(baseline_mod.BaselineService):
        async def _update_activity_baseline(self, sess, cam, hour, dow, now):
            calls.append(("act", sess, cam, hour, dow, now))

        async def _update_class_baseline(self, sess, cam, klass, hour, now):
            calls.append(("cls", sess, cam, klass, hour, now))

    spy = _Spy()
    ts = datetime(2026, 9, 13, 15, 30, 0, tzinfo=UTC)  # hour 15, dow 6 (Sun)
    with LogCapture() as cap:
        _run(spy.update_baseline("cam1", "person", ts, session=s))
    assert len(calls) == 2, calls
    act = next(c for c in calls if c[0] == "act")
    cls_ = next(c for c in calls if c[0] == "cls")
    assert act[1] is s and act[2] == "cam1" and act[3] == 15 and act[4] == 6, act
    assert act[5] is NOW, act
    assert cls_[1] is s and cls_[2] == "cam1" and cls_[3] == "person", cls_
    assert cls_[4] == 15 and cls_[5] is NOW, cls_
    # mutmut_28: debug f-string -> None.
    assert "Updated baselines for camera=cam1, class=person, hour=15, day=6" in cap.msgs, cap.msgs


def test_update_baseline_db_effects():
    # update_baseline mutmut_1 (hour=None), mutmut_2 (day_of_week=None),
    # mutmut_3 (now=None): all invisible to the mocked shipped suite; here the
    # slot INSERT is pinned exactly, so a None/None-keyed duplicate row fails.
    svc, s, inner = _mk_svc()
    seed_lu = NOW - timedelta(days=1)
    inner.add(_act("cam1", 8, 1, 3.0, 4, seed_lu))
    inner.add(_cls("cam1", "person", 8, 3.0, 4, seed_lu))
    inner.commit()
    ts = datetime(2026, 9, 13, 15, 30, 0, tzinfo=UTC)
    _run(svc.update_baseline("cam1", "person", ts, session=s))
    inner.flush()
    naive_now = NOW.replace(tzinfo=None)
    assert _act_rows(inner) == [
        ("cam1", 8, 1, 3.0, 4, seed_lu.replace(tzinfo=None)),
        ("cam1", 15, 6, 1.0, 1, naive_now),
    ], _act_rows(inner)
    assert _cls_rows(inner) == [
        ("cam1", "person", 8, 3.0, 4, seed_lu.replace(tzinfo=None)),
        ("cam1", "person", 15, 1.0, 1, naive_now),
    ], _cls_rows(inner)


# -- _update_activity_baseline / _update_class_baseline families ----------


def _act_decoys():
    """Fresh objects per test (ORM instances are session-bound)."""
    return [
        _act("cam2", 15, 6, 5.0, 7, NOW - timedelta(days=2)),  # camera != / drop
        _act("cam1", 9, 6, 7.0, 2, NOW - timedelta(days=2)),  # hour != / drop
        _act("cam1", 15, 3, 9.0, 2, NOW - timedelta(days=2)),  # dow != / drop
    ]


def test_uab_fresh_insert_exact():
    # mutmut_47..62: ctor arg None / arg drop / 2.0 / 2 / add(None).
    svc, s, inner = _mk_svc()
    for d in _act_decoys():
        inner.add(d)
    inner.commit()
    _run(svc._update_activity_baseline(s, "cam1", 15, 6, NOW))
    inner.flush()
    naive_now = NOW.replace(tzinfo=None)
    got = [r for r in _act_rows(inner) if r[:3] == ("cam1", 15, 6)]
    assert got == [("cam1", 15, 6, 1.0, 1, naive_now)], got
    # decoys untouched
    assert len(_act_rows(inner)) == 4, _act_rows(inner)


def test_uab_existing_ewma_exact():
    # select family 1..14, EWMA 20..31 (25 registered), update 36..46,
    # boundary __21; exact values: decay 0.1 -> 3.0*0.1 + 0.9 = 1.2, cnt 5.
    svc, s, inner = _mk_svc()
    target = _act("cam1", 15, 6, 3.0, 4, NOW - timedelta(days=1))
    inner.add(target)
    for d in _act_decoys():
        inner.add(d)
    inner.commit()
    _run(svc._update_activity_baseline(s, "cam1", 15, 6, NOW))
    inner.flush()
    naive_now = NOW.replace(tzinfo=None)
    rows = _act_rows(inner)
    assert len(rows) == 4, rows
    hit = [r for r in rows if r[:3] == ("cam1", 15, 6)]
    assert len(hit) == 1, hit
    got = hit[0]
    assert isinstance(got[3], float) and abs(got[3] - 1.2) <= TOL, got
    assert got[4] == 5 and got[5] == naive_now, got
    # decoys byte-identical (kills where(id != existing.id) and predicate !=)
    dl = NOW.replace(tzinfo=None) - timedelta(days=2)
    assert ("cam2", 15, 6, 5.0, 7, dl) in rows, rows
    assert ("cam1", 9, 6, 7.0, 2, dl) in rows, rows
    assert ("cam1", 15, 3, 9.0, 2, dl) in rows, rows


def test_uab_stale_reset_exact():
    # decay == 0.0 (outside window): else-branch 1.0/1; kills 32..35 and the
    # ``decay >= 0`` flip __20 (EWMA would give cnt 43, not 1).
    svc, s, inner = _mk_svc()
    stale_lu = NOW - timedelta(days=31)
    inner.add(_act("cam1", 15, 6, 3.0, 42, stale_lu))
    inner.commit()
    _run(svc._update_activity_baseline(s, "cam1", 15, 6, NOW))
    inner.flush()
    rows = _act_rows(inner)
    assert len(rows) == 1, rows
    got = rows[0]
    assert got[:3] == ("cam1", 15, 6), got
    assert isinstance(got[3], float) and abs(got[3] - 1.0) <= TOL, got
    assert got[4] == 1, got


def _cls_decoys():
    return [
        _cls("cam2", "person", 15, 5.0, 7, NOW - timedelta(days=2)),  # camera
        _cls("cam1", "car", 15, 7.0, 2, NOW - timedelta(days=2)),  # class
        _cls("cam1", "person", 9, 9.0, 2, NOW - timedelta(days=2)),  # hour
    ]


def test_ucb_fresh_insert_exact():
    svc, s, inner = _mk_svc()
    for d in _cls_decoys():
        inner.add(d)
    inner.commit()
    _run(svc._update_class_baseline(s, "cam1", "person", 15, NOW))
    inner.flush()
    naive_now = NOW.replace(tzinfo=None)
    got = [r for r in _cls_rows(inner) if r[0] == "cam1" and r[2] == 15 and r[1] == "person"]
    assert got == [("cam1", "person", 15, 1.0, 1, naive_now)], got
    assert len(_cls_rows(inner)) == 4, _cls_rows(inner)


def test_ucb_existing_ewma_exact():
    svc, s, inner = _mk_svc()
    inner.add(_cls("cam1", "person", 15, 3.0, 4, NOW - timedelta(days=1)))
    for d in _cls_decoys():
        inner.add(d)
    inner.commit()
    _run(svc._update_class_baseline(s, "cam1", "person", 15, NOW))
    inner.flush()
    naive_now = NOW.replace(tzinfo=None)
    rows = _cls_rows(inner)
    assert len(rows) == 4, rows
    hit = [r for r in rows if r[:3] == ("cam1", "person", 15)]
    assert len(hit) == 1, hit
    got = hit[0]
    assert isinstance(got[3], float) and abs(got[3] - 1.2) <= TOL, got
    assert got[4] == 5 and got[5] == naive_now, got
    dl = NOW.replace(tzinfo=None) - timedelta(days=2)
    assert ("cam2", "person", 15, 5.0, 7, dl) in rows, rows
    assert ("cam1", "car", 15, 7.0, 2, dl) in rows, rows
    assert ("cam1", "person", 9, 9.0, 2, dl) in rows, rows


def test_ucb_stale_reset_exact():
    svc, s, inner = _mk_svc()
    stale_lu = NOW - timedelta(days=31)
    inner.add(_cls("cam1", "person", 15, 3.0, 42, stale_lu))
    inner.commit()
    _run(svc._update_class_baseline(s, "cam1", "person", 15, NOW))
    inner.flush()
    rows = _cls_rows(inner)
    assert len(rows) == 1, rows
    got = rows[0]
    assert got[:3] == ("cam1", "person", 15), got
    assert isinstance(got[3], float) and abs(got[3] - 1.0) <= TOL, got
    assert got[4] == 1, got


# -- get_activity_rate / get_class_frequency select families --------------


def test_get_activity_rate_predicate_exact():
    # select family 1..13 (+10/11 != flips, +3..7 drops, +13 execute(None)):
    # two same-slot rows under different cameras make every wrong-predicate
    # form either raise MultipleResultsFound or read the wrong row (9.0).
    svc, s, inner = _mk_svc()
    inner.add(_act("cam1", 8, 1, 3.0, 4, NOW - timedelta(days=1)))
    inner.add(_act("cam2", 8, 1, 9.0, 5, NOW - timedelta(days=1)))
    inner.add(_act("cam1", 9, 1, 5.0, 3, NOW - timedelta(days=1)))
    inner.add(_act("cam1", 8, 2, 7.0, 3, NOW - timedelta(days=1)))
    inner.commit()
    got = _run(svc.get_activity_rate("cam1", 8, 1, session=s))
    assert abs(got - 0.3) <= TOL, got
    # absent slot -> 0.0 (else-arm of `baseline is None`)
    assert _run(svc.get_activity_rate("cam1", 8, 3, session=s)) == 0.0
    assert _run(svc.get_activity_rate("camX", 8, 1, session=s)) == 0.0


def test_get_class_frequency_predicate_exact():
    svc, s, inner = _mk_svc()
    inner.add(_cls("cam1", "person", 8, 3.0, 4, NOW - timedelta(days=1)))
    inner.add(_cls("cam2", "person", 8, 9.0, 5, NOW - timedelta(days=1)))
    inner.add(_cls("cam1", "car", 8, 5.0, 3, NOW - timedelta(days=1)))
    inner.add(_cls("cam1", "person", 9, 7.0, 3, NOW - timedelta(days=1)))
    inner.commit()
    got = _run(svc.get_class_frequency("cam1", "person", 8, session=s))
    assert abs(got - 0.3) <= TOL, got
    assert _run(svc.get_class_frequency("cam1", "bike", 8, session=s)) == 0.0
    assert _run(svc.get_class_frequency("cam1", "person", 7, session=s)) == 0.0


# -- get_camera_baseline_summary -------------------------------------------


def test_camera_baseline_summary_exact():
    # select families (both stmts: mutmut_1..13/10/11/13), aggregation init
    # 18/19 and 24/25 (init 1.0 / += -> =), top-slice 37/48 ([:5] -> [:6]),
    # dict-key renames 61/62/67/68. 6 classes + 6 hours exercise everything:
    # the 6th class must NOT leak into top_classes, totals use += (b=20
    # double-counts h8), and every key/value is pinned.
    svc, s, inner = _mk_svc()
    rows = [
        _act("cam1", 8, 1, 5.0, 2, NOW),
        _act("cam1", 8, 2, 15.0, 3, NOW),
        _act("cam1", 9, 1, 30.0, 1, NOW),
        _act("cam1", 10, 1, 25.0, 4, NOW),
        _act("cam1", 11, 1, 20.0, 1, NOW),
        _act("cam1", 12, 1, 10.0, 1, NOW),
        _act("cam1", 13, 1, 5.0, 1, NOW),
        _cls("cam1", "a", 8, 1.0, 1, NOW),
        _cls("cam1", "b", 8, 20.0, 1, NOW),
        _cls("cam1", "b", 9, 10.0, 1, NOW),
        _cls("cam1", "c", 8, 9.0, 1, NOW),
        _cls("cam1", "d", 8, 8.0, 1, NOW),
        _cls("cam1", "e", 8, 7.0, 1, NOW),
        _cls("cam1", "f", 8, 6.0, 1, NOW),
        _cls("cam2", "z", 8, 99.0, 1, NOW),
    ]
    for r in rows:
        inner.add(r)
    inner.commit()
    got = _run(svc.get_camera_baseline_summary("cam1", session=s))
    assert got == {
        "camera_id": "cam1",
        "activity_baseline_count": 7,
        "class_baseline_count": 7,
        "unique_classes": 6,
        "top_classes": [
            {"class": "b", "total_frequency": 30.0},
            {"class": "c", "total_frequency": 9.0},
            {"class": "d", "total_frequency": 8.0},
            {"class": "e", "total_frequency": 7.0},
            {"class": "f", "total_frequency": 6.0},
        ],
        "peak_hours": [
            {"hour": 9, "total_activity": 30.0},
            {"hour": 10, "total_activity": 25.0},
            {"hour": 8, "total_activity": 20.0},
            {"hour": 11, "total_activity": 20.0},
            {"hour": 12, "total_activity": 10.0},
        ],
    }, got
    # empty camera: counts zero, lists empty (kills init-1.0 + = mutants
    # partially; the empty path also kills select(None) on both stmts)
    empty = _run(svc.get_camera_baseline_summary("camNOPE", session=s))
    assert empty == {
        "camera_id": "camNOPE",
        "activity_baseline_count": 0,
        "class_baseline_count": 0,
        "unique_classes": 0,
        "top_classes": [],
        "peak_hours": [],
    }, empty


# -- get_hourly / get_daily / get_object patterns --------------------------


def test_hourly_patterns_exact():
    # mutmut SQL family 1..6; __24 variance len->(len*len); __27 (x-mean)**2
    # -> (x+mean)**2; rounding 47/49/51/52 (round(None)/round->None/1-arg/3).
    # Values chosen so round(...,2) != round(...,3) != the raw value.
    svc, s, inner = _mk_svc()
    inner.add(_act("cam1", 8, 1, 45.674, 2, NOW))
    inner.add(_act("cam1", 8, 2, 45.682, 3, NOW))
    inner.add(_act("cam1", 9, 1, 7.0, 4, NOW))
    inner.add(_act("cam2", 8, 1, 123.456789, 9, NOW))
    inner.commit()
    got = _run(svc.get_hourly_patterns("cam1", session=s))
    assert sorted(got.keys()) == ["8", "9"], sorted(got.keys())
    h8 = got["8"]
    assert h8.avg_detections == 45.68, h8
    assert h8.std_dev == 0.0, h8  # round(0.004, 2)
    assert h8.sample_count == 5, h8
    h9 = got["9"]
    assert (h9.avg_detections, h9.std_dev, h9.sample_count) == (7.0, 0.0, 4), h9
    assert _run(svc.get_hourly_patterns("camNOPE", session=s)) == {}


def test_hourly_patterns_std_nonzero():
    # kills __27 (x+mean)**2 (std would be 7.07) and __24 (len->len*len over
    # 3 rows: std 0.8165 -> round 0.82); round-3 kills need .005 halves.
    svc, s, inner = _mk_svc()
    inner.add(_act("cam1", 8, 1, 10.0, 1, NOW))
    inner.add(_act("cam1", 8, 2, 20.005, 1, NOW))
    inner.add(_act("cam1", 8, 3, 30.0, 1, NOW))
    inner.commit()
    got = _run(svc.get_hourly_patterns("cam1", session=s))
    h8 = got["8"]
    assert h8.avg_detections == 20.0, h8  # round(20.001666.., 2)
    assert h8.std_dev == 8.16, h8  # round(sqrt(66.667), 2); len^2 -> 4.71, (x+mean)^2 -> 40.82
    assert h8.sample_count == 3, h8


def test_daily_patterns_exact():
    # day_names XX/CASE renames 6..15 hit indices 2..6 (wed..sun) -- every one
    # of those days gets a row so its key presence pins the name; __36
    # key=None / __38 key-drop on peak max(); __42 guard (registered);
    # rounding 51/53/54 (12.345: round(2)=12.34 != round(3)=12.345).
    svc, s, inner = _mk_svc()
    inner.add(_act("cam1", 9, 0, 10.005, 2, NOW))
    inner.add(_act("cam1", 5, 0, 20.005, 1, NOW))
    inner.add(_act("cam1", 3, 2, 5.01, 7, NOW))
    inner.add(_act("cam1", 12, 3, 12.345, 2, NOW))
    inner.add(_act("cam1", 20, 5, 3.14, 1, NOW))
    inner.add(_act("cam1", 1, 6, 2.5, 4, NOW))
    inner.add(_act("cam2", 1, 1, 99.0, 1, NOW))
    inner.commit()
    got = _run(svc.get_daily_patterns("cam1", session=s))
    assert sorted(got.keys()) == [
        "monday",
        "saturday",
        "sunday",
        "thursday",
        "wednesday",
    ], sorted(got.keys())
    mon = got["monday"]
    assert mon.avg_detections == 30.01, mon  # round(30.01, 2) != round(...,3)
    assert mon.peak_hour == 5, mon
    assert mon.total_samples == 3, mon
    wed = got["wednesday"]
    assert (wed.avg_detections, wed.peak_hour, wed.total_samples) == (5.01, 3, 7), wed
    thu = got["thursday"]
    # 12.345 float is 12.3450000000000006 -> round(2) = 12.35
    assert (thu.avg_detections, thu.peak_hour, thu.total_samples) == (12.35, 12, 2), thu
    sat = got["saturday"]
    assert (sat.avg_detections, sat.peak_hour, sat.total_samples) == (3.14, 20, 1), sat
    sun = got["sunday"]
    assert (sun.avg_detections, sun.peak_hour, sun.total_samples) == (2.5, 1, 4), sun
    assert _run(svc.get_daily_patterns("camNOPE", session=s)) == {}


def test_daily_patterns_peak_tie():
    # __36 (key=None) and __38 (key dropped) both degrade to max(hours) --
    # they pick 7 on this tie where the value-keyed max keeps first-seen 3.
    # (Non-tie data already kills them: monday's peak is hour 5, max-of-keys
    # would answer 9.)
    svc, s, inner = _mk_svc()
    inner.add(_act("cam1", 3, 4, 5.0, 1, NOW))
    inner.add(_act("cam1", 7, 4, 5.0, 1, NOW))
    inner.commit()
    got = _run(svc.get_daily_patterns("cam1", session=s))
    assert got["friday"].peak_hour == 3, got  # max keeps first-seen on ties
    assert got["friday"].avg_detections == 10.0, got
    assert got["friday"].total_samples == 2, got


def test_object_baselines_exact():
    # SQL family 1..6; ternary 18/20/22 (registered); peak 27 (registered),
    # 29 key=None, 31 key-drop, 33 else (registered); __47 round(2)->round(3).
    # 7.0/4.0 = 1.75 exactly representable; 1.005/1.01/1.02 -> mean 1.011666.
    svc, s, inner = _mk_svc()
    inner.add(_cls("cam1", "person", 8, 7.0, 2, NOW))
    inner.add(_cls("cam1", "person", 9, 4.0, 3, NOW))
    inner.add(_cls("cam1", "car", 8, 1.005, 1, NOW))
    inner.add(_cls("cam1", "car", 9, 1.01, 1, NOW))
    inner.add(_cls("cam1", "car", 10, 1.02, 1, NOW))
    inner.add(_cls("cam2", "z", 8, 99.0, 9, NOW))
    inner.commit()
    got = _run(svc.get_object_baselines("cam1", session=s))
    assert sorted(got.keys()) == ["car", "person"], sorted(got.keys())
    p = got["person"]
    assert (p.avg_hourly, p.peak_hour, p.total_detections) == (5.5, 8, 5), p
    c = got["car"]
    assert (c.avg_hourly, c.peak_hour, c.total_detections) == (1.01, 10, 3), c
    assert _run(svc.get_object_baselines("camNOPE", session=s)) == {}


# -- is_anomalous ----------------------------------------------------------


# Decay at default decay_factor 0.1 is PER DAY: NOW-1d -> 0.1, NOW-2d ->
# 0.01, same-instant -> 1.0, NOW-31d -> 0.0 (outside window; the guard is
# days > window_days == 30). Seed geometry: hour 8 holds ONLY person (tf ==
# cf == 1.2, rel 1.0) so every class_stmt mis-selection raises
# MultipleResultsFound (dropped predicates match cam2 rows too) while the
# `== -> !=` flips stay equivalent THERE -- they die in the ghost test,
# where cf == 0 makes class_baseline the sole output channel. hour 8 total
# samples 12 > default min_samples 10; cam2 at hour 8 totals 13 (> 10), so
# the all_classes `camera !=` flip -- which sums cam2 instead -- cannot hide
# behind the bail guard. hour 9 mixes 0.01/0.1 decays for the ternary pins.
def _anom_rows():
    return [
        _cls("cam1", "person", 8, 12.0, 12, NOW - timedelta(days=1)),  # d=0.1
        _cls("cam1", "person", 9, 30.0, 5, NOW - timedelta(days=2)),  # d=0.01
        _cls("cam1", "car", 9, 60.0, 5, NOW - timedelta(days=1)),  # d=0.1
        _cls("cam2", "person", 8, 50.0, 9, NOW - timedelta(days=1)),
        _cls("cam2", "car", 8, 40.0, 4, NOW - timedelta(days=1)),
        _cls("cam2", "person", 10, 800.0, 9, NOW - timedelta(days=1)),
    ]


def _anom_seed(inner):
    for r in _anom_rows():
        inner.add(r)
    inner.commit()


def test_is_anomalous_no_baselines():
    # absent hour: debug message (mutmut_30) + neutral (False, 0.5); every
    # stmt=None / select(None) / execute(None) mutant either raises or lands
    # here while the main-path tests pin the real numbers.
    svc, s, inner = _mk_svc()
    _anom_seed(inner)
    ts = datetime(2026, 9, 15, 20, 0, 0, tzinfo=UTC)  # hour 20: empty
    with LogCapture() as cap:
        got = _run(svc.is_anomalous("cam1", "person", ts, session=s))
    assert got == (False, 0.5), got
    assert "No baselines for camera=cam1, hour=20. Cannot determine anomaly." in cap.msgs, cap.msgs
    assert _run(
        svc.is_anomalous("camNOPE", "person", datetime(2026, 9, 15, 8, 0, tzinfo=UTC), session=s)
    ) == (False, 0.5)


def test_is_anomalous_main_path():
    # hour 8 holds ONLY cam1/person: tf == cf == 12*0.1 == 1.2 -> rel 1.0 ->
    # score 0.0; default threshold 2.0 -> cut 2/3 -> (False, 0.0) pinned plus
    # the exact debug line (__89). Kill channels: __1 hour=None empties the
    # lookups -> (False, 0.5); class_stmt dropped predicates __5..__8 also
    # match the cam2 hour-8 rows -> MultipleResultsFound; stmt=None /
    # select(None) / execute(None) __2/__9/__14 raise or come back empty;
    # all_classes dropped __17..__21 raise MultipleResultsFound; the camera
    # flip __22 sums the cam2 set (total_samples 13 -> no bail, cf stays 0,
    # tf 8.7 -> score 0.95 != 0.0); accumulators __34/__36/__38 and the
    # += -> = flips __46/__48 move tf off 1.2 (rel != 1 -> score != 0.0);
    # __46's =-flip leaves tf == 0.0?? no -- with ONE row += and = agree, so
    # __46/__48 die in the hour-9 two-row test instead; cut-arithmetic
    # looseners 83/84/86 keep False here (score 0) and are killed by the
    # score-1.0 / 0.95 tests (cut 4/3, 5/3, 1/3 -> False != True).
    svc, s, inner = _mk_svc()
    _anom_seed(inner)
    ts = datetime(2026, 9, 15, 8, 0, 0, tzinfo=UTC)
    with LogCapture() as cap:
        got = _run(svc.is_anomalous("cam1", "person", ts, session=s))
    assert got == (False, 0.0), got
    hits = [r for r in cap.msgs if r.startswith("Anomaly check:")]
    assert len(hits) == 1, cap.msgs
    assert hits[0] == (
        "Anomaly check: camera=cam1, class=person, hour=8, "
        "relative_freq=1.0000, anomaly_score=0.0000, is_anomaly=False"
    ), hits


def test_is_anomalous_insufficient_samples():
    # min_samples=13 > hour-8 total 12 -> bail + the exact "12 < 13" message
    # pin (kills __53 + __38 init + __48 =-flip via interpolation); cam2 at
    # hour 8 (total 13) proves the camera predicate on all_classes (a flipped
    # or dropped camera reads the 13-sample set -> no bail, different score).
    svc, s, inner = _mk_svc(min_samples=13)
    _anom_seed(inner)
    ts = datetime(2026, 9, 15, 8, 0, 0, tzinfo=UTC)
    with LogCapture() as cap:
        got = _run(svc.is_anomalous("cam1", "person", ts, session=s))
    assert got == (False, 0.5), got
    bail = [r for r in cap.msgs if r.startswith("Insufficient samples")]
    assert bail == [
        "Insufficient samples (12 < 13) for camera=cam1, hour=8. Cannot determine anomaly."
    ], cap.msgs


def test_is_anomalous_threshold_boundary():
    # cf == tf (only class at hour 21, same-instant -> decay 1.0): rel 1.0,
    # score = 0.0 EXACTLY == cut for threshold 0.0 -> original False
    # (0.0 > 0.0 is False), the >= flip __82 returns True.
    svc, s, inner = _mk_svc(anomaly_threshold_std=0.0)
    inner.add(_cls("onlyc", "person", 21, 2.0, 20, NOW))
    inner.commit()
    ts = datetime(2026, 9, 15, 21, 0, 0, tzinfo=UTC)
    got = _run(svc.is_anomalous("onlyc", "person", ts, session=s))
    assert got == (False, 0.0), got


def test_is_anomalous_fresh_class():
    # hour 9 unseen class: class_baseline None -> score 1.0 > cut 2/3 True.
    # hour-9 seen-but-minority: cf = 30*0.01 = 0.3, tf = 6.3, rel = 1/21,
    # score = 20/21 (kills the __52 guard at total 10 vs min 10: the <=
    # mutant bails to (False, 0.5); kills __59 rel*tf -> negative -> 0.0).
    svc, s, inner = _mk_svc()
    _anom_seed(inner)
    ts = datetime(2026, 9, 15, 9, 0, 0, tzinfo=UTC)
    assert _run(svc.is_anomalous("cam1", "ghost", ts, session=s)) == (True, 1.0)
    got2 = _run(svc.is_anomalous("cam1", "person", ts, session=s))
    assert got2[0] is True, got2
    assert abs(got2[1] - 20.0 / 21.0) <= 1e-9, got2


def test_is_anomalous_ghost_predicates():
    # cf == 0.0 geometry makes class_baseline the only output channel: score
    # must be exactly 1.0, so every class_stmt mis-selection either raises
    # MultipleResultsFound (dropped predicates match 2+ rows) or answers
    # 0.95 (a flipped predicate finds a row -> class_baseline is not None ->
    # cf == 0.0 elif). The `hour != hour` flip __12 instead matches cam2's
    # hour-10 person row (cf 0 -> score 0.95 != 1.0).
    svc, s, inner = _mk_svc()
    _anom_seed(inner)
    got = _run(
        svc.is_anomalous("cam1", "ghost", datetime(2026, 9, 15, 8, 0, 0, tzinfo=UTC), session=s)
    )
    assert got == (True, 1.0), got


def test_is_anomalous_decayed_zero():
    # stale rows (> 30-day window) -> decay 0.0 -> total_frequency 0.0 and
    # class_frequency 0.0 -> the cf == 0.0 elif answers 0.95. The
    # relative_frequency division is SKIPPED (guard tf > 0 False), so the
    # guard flips __57/__58/__60 take the division with tf == 0 ->
    # ZeroDivisionError; the else-value __62 (1.0) is unreachable when tf
    # == 0 forces cf == 0 too -- EQUIVALENT by construction (ledger); __67
    # (elif cf == 1.0) misses -> else 1 - 0.0 = 1.0 != 0.95.
    svc, s, inner = _mk_svc()
    inner.add(_cls("cam1", "person", 8, 3.0, 50, NOW - timedelta(days=31)))
    inner.add(_cls("cam1", "car", 8, 6.0, 50, NOW - timedelta(days=31)))
    inner.commit()
    ts = datetime(2026, 9, 15, 8, 0, 0, tzinfo=UTC)
    got = _run(svc.is_anomalous("cam1", "person", ts, session=s))
    assert got[0] is True, got
    assert abs(got[1] - 0.95) <= TOL, got


def test_is_anomalous_low_total_frequency():
    # 0 < tf <= 1 geometry: decayed 0.03 + 0.07 = 0.1 (comfortably under 1
    # in float) -> the __61 `tf > 1` flip takes the else arm: rel 0.0 ->
    # score 1.0 != the pinned ~0.7. Original: rel = 0.03/0.1 = 0.3, score
    # 0.7 which lies BETWEEN cut 2/3 (original True) and the __88 cut 0.75
    # (mutant False). total_samples 11 > default min 10.
    svc, s, inner = _mk_svc()
    inner.add(_cls("cam1", "person", 8, 0.3, 6, NOW - timedelta(days=1)))
    inner.add(_cls("cam1", "car", 8, 0.7, 5, NOW - timedelta(days=1)))
    inner.commit()
    ts = datetime(2026, 9, 15, 8, 0, 0, tzinfo=UTC)
    got = _run(svc.is_anomalous("cam1", "person", ts, session=s))
    assert got[0] is True, got
    assert abs(got[1] - 0.7) <= 1e-9, got


def test_is_anomalous_classfreq_one():
    # cf == 1.0 EXACTLY (same-instant row, decay 1.0): the `elif cf == 1.0`
    # mutant __67 hijacks to 0.95; original: tf = 1.0 + 0.3 = 1.3, rel =
    # 1/1.3, score = 3/13 ~ 0.2308 < cut 2/3 -> False.
    svc, s, inner = _mk_svc()
    inner.add(_cls("cam1", "person", 8, 1.0, 5, NOW))
    inner.add(_cls("cam1", "car", 8, 3.0, 5, NOW - timedelta(days=1)))
    inner.commit()
    ts = datetime(2026, 9, 15, 8, 0, 0, tzinfo=UTC)
    got = _run(svc.is_anomalous("cam1", "person", ts, session=s))
    assert got[0] is False, got
    assert abs(got[1] - 3.0 / 13.0) <= TOL, got


# -- get_current_deviation --------------------------------------------------


def _dev_rows():
    return [
        _act("cam1", 8, 1, 9.0, 12, NOW),  # the slot row (hour 8, dow 1), outlier
        _act("cam1", 8, 2, 1.0, 3, NOW),
        _act("cam1", 8, 3, 1.0, 3, NOW),
        _act("cam1", 8, 4, 1.0, 3, NOW),
        _act("cam1", 9, 1, 123.4, 12, NOW),  # hour != decoy
        _act("cam2", 8, 1, 99.0, 12, NOW),  # camera != decoy
        _act("cam2", 8, 2, 77.0, 12, NOW),
        _cls("cam1", "person", 8, 2.5, 3, NOW),  # > 2.0 -> factor
        _cls("cam1", "car", 8, 2.0, 3, NOW),  # == 2.0 -> NOT a factor (76)
        _cls("cam1", "bike", 8, 9.0, 3, NOW),  # > 2.0 -> factor
        _cls("cam2", "person", 8, 50.0, 3, NOW),  # camera decoy
        _cls("cam1", "person", 9, 100.0, 3, NOW),  # hour decoy
    ]


def _dev_seed(inner):
    for r in _dev_rows():
        inner.add(r)
    inner.commit()


def test_current_deviation_exact():
    # 4-row group [9, 1, 1, 1] over hour 8: mean 3.0 (exact), variance
    # (36+4+4+4)/4 = 12.0 (exact), std sqrt(12), z = 6/sqrt(12) = 1.7321 =
    # sqrt(3) > 1.5 -> class branch runs; classes 2.5/9.0 elevated, 2.0 not
    # (__76 >= flip would add "car_count_elevated"; __77 >3.0 would drop
    # "person"); __64 (>2.5) skips the branch -> [overall_activity_deviation]
    # != the pinned pair. Score round pins 95..98 (round(1.7321,2)=1.73;
    # round(3)=1.7321; 1-arg=2; round(None) raises). min_samples boundary:
    # slot count 12 == min 12 -- the <= flip (__21) returns None. Statement
    # families 5..31: any predicate None/drop/!=/stmt None/execute(None)
    # changes the group -> different z or MultipleResultsFound.
    svc, s, inner = _mk_svc(min_samples=12)
    _dev_seed(inner)
    got = _run(svc.get_current_deviation("cam1", session=s))
    assert got is not None
    assert got.score == 1.73, got.score
    assert got.interpretation.value == "slightly_above_normal", got
    assert got.contributing_factors == [
        "person_count_elevated",
        "bike_count_elevated",
    ], got.contributing_factors


def test_current_deviation_insufficient():
    # slot row sample_count 12 with min_samples 13 -> None, while the main
    # test (min 12 == 12) is not None -- the pair pins both directions of the
    # < / <= guard (__21).
    svc, s, inner = _mk_svc(min_samples=13)
    _dev_seed(inner)
    assert _run(svc.get_current_deviation("cam1", session=s)) is None
    # absent camera
    svc2, s2, _i2 = _mk_svc(min_samples=12)
    _dev_seed(_i2)
    assert _run(svc2.get_current_deviation("camNOPE", session=s2)) is None


def test_current_deviation_negative_z():
    # slot row is the LOW day: [2, 10, 18] -> mean 10.0, std sqrt(42.667)=
    # 6.532, z = -8/6.532 = -1.2247 -> BELOW_NORMAL; class branch skipped
    # (z < 1.5) so the hour-8 class row must NOT contribute; |z| > 1.0 with
    # empty factors -> overall_activity_deviation (kills __55 *: z=-52.3,
    # __56 +mean: (2+10)/6.532=+1.837 -> +1.84, __79 or, __83/84 len
    # conditions, __86/87 name renames).
    svc, s, inner = _mk_svc(min_samples=12)
    rows = [
        _act("cam1", 8, 1, 2.0, 12, NOW),
        _act("cam1", 8, 2, 10.0, 3, NOW),
        _act("cam1", 8, 3, 18.0, 3, NOW),
    ]
    for r in rows:
        inner.add(r)
    inner.add(_cls("cam1", "person", 8, 50.0, 3, NOW))  # must NOT be read
    inner.commit()
    got = _run(svc.get_current_deviation("cam1", session=s))
    assert got is not None
    assert got.score == -1.22, got.score
    assert got.interpretation.value == "below_normal", got
    assert got.contributing_factors == ["overall_activity_deviation"], got


def test_current_deviation_z_exactly_one():
    # 2-row group [2.0, 10.0]: mean 6.0, std 4.0, z = -1.0 EXACTLY ->
    # interpretation NORMAL; abs(z) > 1.0 is False -> factors [] -- the >=
    # flip (__81) appends overall_activity_deviation. Also kills __36
    # (mean*len=12 -> z=-2.5), __39 (len>2 -> std=mean*0.1=0.6 -> z=-6.67),
    # __41 (variance*len -> std 5.657 -> -0.71), __44 ((x+mean)^2 -> std
    # 12.649 -> -0.32), __45 (**3 -> variance 0 -> std 0 -> z=0.0).
    svc, s, inner = _mk_svc(min_samples=12)
    inner.add(_act("cam1", 8, 1, 2.0, 12, NOW))
    inner.add(_act("cam1", 8, 2, 10.0, 3, NOW))
    inner.commit()
    got = _run(svc.get_current_deviation("cam1", session=s))
    assert got is not None
    assert got.score == -1.0, got.score
    assert got.interpretation.value == "normal", got
    assert got.contributing_factors == [], got


def test_current_deviation_zero_std():
    # all-day rows equal -> variance 0 -> std_dev == 0.0 -> ternary else 0.0:
    # __54 ((...) or True) and __57 (std >= 0) ZeroDivisionError; __59 (else
    # 1.0) gives score 1.0 / slightly_above_normal vs the pinned 0.0/normal.
    svc, s, inner = _mk_svc(min_samples=12)
    inner.add(_act("cam1", 8, 1, 2.0, 12, NOW))
    inner.add(_act("cam1", 8, 2, 2.0, 3, NOW))
    inner.commit()
    got = _run(svc.get_current_deviation("cam1", session=s))
    assert got is not None
    assert got.score == 0.0, got.score
    assert got.interpretation.value == "normal", got
    assert got.contributing_factors == [], got


# -- raw getters / established date / update_config ------------------------


def test_activity_baselines_raw_order_exact():
    # order_by family 2/3/4/5 (None-first drops the dow key -> hour order;
    # None-second keeps dow-only; hour-only / dow-only single keys), where
    # 6/8 (WHERE NULL -> []; != -> foreign rows), select(None) 7 ([None]),
    # stmt None 1 / execute None 10 raise. Crafted so EVERY order differs.
    svc, s, inner = _mk_svc()
    rows = [
        _act("cam2", 0, 0, 1.0, 1, NOW),  # foreign camera
        _act("cam1", 5, 2, 2.0, 1, NOW),  # (2,5)
        _act("cam1", 1, 3, 3.0, 1, NOW),  # (3,1)
        _act("cam1", 2, 0, 4.0, 1, NOW),  # (0,2)
        _act("cam1", 4, 2, 5.0, 1, NOW),  # (2,4) shares dow w/ (2,5)
        _act("cam2", 7, 6, 6.0, 1, NOW),  # foreign decoy #2
    ]
    for r in rows:
        inner.add(r)
    inner.commit()
    got = [(b.day_of_week, b.hour) for b in _run(svc.get_activity_baselines_raw("cam1", session=s))]
    assert got == [(0, 2), (2, 4), (2, 5), (3, 1)], got
    # hour-only order (4/5 mutants): [1, 2, 4, 5] != pinned; dow-only (3):
    # [(0,2),(2,5),(2,4),(3,1)] with stable-sort... pinned seq already
    # differs from both. Empty camera -> [].
    assert _run(svc.get_activity_baselines_raw("camNOPE", session=s)) == []


def test_class_baselines_raw_order_exact():
    svc, s, inner = _mk_svc()
    rows = [
        _cls("cam1", "b", 1, 1.0, 1, NOW),  # (b,1)
        _cls("cam1", "b", 0, 2.0, 1, NOW),  # (b,0) shares class w/ (b,1)
        _cls("cam1", "a", 5, 3.0, 1, NOW),  # (a,5)
        _cls("cam1", "c", 2, 4.0, 1, NOW),  # (c,2)
        _cls("cam2", "a", 9, 5.0, 1, NOW),  # foreign
    ]
    for r in rows:
        inner.add(r)
    inner.commit()
    got = [
        (b.detection_class, b.hour) for b in _run(svc.get_class_baselines_raw("cam1", session=s))
    ]
    assert got == [("a", 5), ("b", 0), ("b", 1), ("c", 2)], got
    assert _run(svc.get_class_baselines_raw("camNOPE", session=s)) == []


def test_baseline_established_date_four_quadrants():
    # (activity_min, class_min) all four None-arms: both set (min of two,
    # activity earlier), class-only, activity-only, neither (None). Predicate
    # None (2/10 -> WHERE NULL -> all-None -> wrong in quadrants 1-3), !=
    # (5/13 -> foreign mins), select(None)/func.min(None) (3/4/11/12 -> None
    # scalar everywhere), stmt None / execute(None) raise.
    a_early = NOW - timedelta(days=40)
    a_late = NOW - timedelta(days=5)
    c_mid = NOW - timedelta(days=20)
    svc, s, inner = _mk_svc()
    inner.add(_act("cam1", 8, 1, 1.0, 1, a_early))
    inner.add(_cls("cam1", "person", 8, 1.0, 1, c_mid))
    inner.add(_act("cam2", 8, 1, 1.0, 1, NOW - timedelta(days=60)))  # foreign
    inner.add(_cls("cam2", "person", 8, 1.0, 1, NOW - timedelta(days=70)))
    inner.commit()
    got = _run(svc.get_baseline_established_date("cam1", session=s))
    naive = got.replace(tzinfo=None) if got.tzinfo else got
    assert naive == a_early.replace(tzinfo=None), got  # min wins activity side
    # class-only camera
    s2 = _mk_env()
    svc2, sess2, inner2 = s2
    inner2.add(_cls("onlyc", "x", 1, 1.0, 1, c_mid))
    inner2.commit()
    got2 = _run(svc2.get_baseline_established_date("onlyc", session=sess2))
    assert (got2.replace(tzinfo=None) if got2.tzinfo else got2) == c_mid.replace(tzinfo=None), got2
    # activity-only camera
    svc3, sess3, inner3 = _mk_env()
    inner3.add(_act("onlya", 1, 1, 1.0, 1, a_early))
    inner3.commit()
    got3 = _run(svc3.get_baseline_established_date("onlya", session=sess3))
    assert (got3.replace(tzinfo=None) if got3.tzinfo else got3) == a_early.replace(tzinfo=None), (
        got3
    )
    # empty camera -> None
    assert _run(svc.get_baseline_established_date("camNOPE", session=s)) is None


def test_update_config_boundaries_and_log():
    # mutmut_3 (<=1 vs <=0): threshold 0.5 legal for the original, rejected
    # (wrongly) by the mutant; mutmut_9 (min_samples <=1): 1 legal; mutmut_10
    # (<2): 1 legal -- pin accepted then applied; mutmut_5/12 message XX;
    # mutmut_15 info log -> None.
    svc, _s, _i = _mk_svc()
    svc.update_config(threshold_stdev=0.5, min_samples=1)
    assert svc.anomaly_threshold_std == 0.5
    assert svc.min_samples == 1
    for kw, msg in (
        ({"threshold_stdev": 0}, "threshold_stdev must be positive"),
        ({"threshold_stdev": -1.0}, "threshold_stdev must be positive"),
        ({"min_samples": 0}, "min_samples must be at least 1"),
        ({"min_samples": -3}, "min_samples must be at least 1"),
    ):
        try:
            svc.update_config(**kw)
        except ValueError as exc:
            assert str(exc) == msg, (kw, str(exc))
        else:
            raise AssertionError(f"no ValueError for {kw}")
    # no-op update still logs (mutmut_15)
    with LogCapture() as cap:
        svc.update_config()
    assert "BaselineService config updated: threshold=0.5std, min_samples=1" in cap.msgs, cap.msgs
