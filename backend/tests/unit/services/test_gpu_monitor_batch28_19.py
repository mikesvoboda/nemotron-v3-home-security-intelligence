"""S3 batch-28 lane gm-19 - ``gpu_monitor`` group G16 kill battery (30 keys).

Module: ``backend/services/gpu_monitor.py`` (md5 2f122c85a072b7bd00c2e4b36cdc1cda,
verified identical to ``git show HEAD:backend/services/gpu_monitor.py``).
Admitted manifest: ``/tmp/wp-pw/gpu_monitor/manifest.json`` group idx 29
("G16 get_stats_from_db: compiled query shape + tz cutoff + error-log contract",
30 KILLABLE), ``group_29.keys`` and ``survivors.json``.  This file is that group's
manifest ``battery_file``, so all 30 keys are claimed here and nowhere else.

Key -> test map (all keys ``xǁGPUMonitorǁget_stats_from_db__mutmut_N``; L-numbers
are shipped ``backend/services/gpu_monitor.py`` lines)
==============================================================================
``select`` is replaced with a REAL spy (a closure that records the call and
forwards to the shipped ``sqlalchemy.select``), so a mutated call argument is
caught from the call side as well as from the compiled text.

* ``_2`` L1236 ``order_by(GPUStats.recorded_at.desc())`` -> ``order_by(None)``
  -> ``test_order_by_is_called_with_the_recorded_at_desc_expression`` (call-arg
     identity) and ``test_filtered_query_keeps_the_columns_order_and_predicates``
     (the ORDER BY clause disappears - measured: that mutant compiles with no
     ORDER BY at all).
* ``_3`` L1236 ``select(GPUStats)`` -> ``select(None)``
  -> ``test_select_is_called_with_the_gpu_stats_model`` (call-arg identity) and
     ``test_filtered_query_keeps_the_columns_order_and_predicates`` via the
     COLUMNS-CLAUSE assert.  audit correction #9: that assert is REQUIRED -
     measured, the ``select(None)`` statement still compiles with
     ``FROM gpu_stats`` / ``ORDER BY gpu_stats.recorded_at DESC`` / the ``>=``
     predicate / ``LIMIT :param_1``, so ONLY the columns clause distinguishes it.
* ``_6`` L1240 ``-`` -> ``+`` (measured: bound cutoff becomes 12:15, in the future)
  -> ``test_cutoff_param_is_frozen_now_minus_minutes_and_tz_aware``,
     ``test_zero_minutes_still_builds_a_tz_aware_cutoff_predicate``.
* ``_7`` L1240 ``datetime.now(UTC)`` -> ``datetime.now(None)`` (naive cutoff)
  -> ``test_cutoff_param_is_frozen_now_minus_minutes_and_tz_aware``,
     ``test_zero_minutes_still_builds_a_tz_aware_cutoff_predicate``.
* ``_10`` L1241 ``where(GPUStats.recorded_at >= cutoff)`` -> ``where(None)``
  (measured: the bound ``recorded_at_1`` parameter and the WHERE clause both
  disappear) -> ``test_cutoff_param_is_frozen_now_minus_minutes_and_tz_aware``,
  ``test_where_is_called_with_the_inclusive_cutoff_comparison``,
  ``test_filtered_query_keeps_the_columns_order_and_predicates``,
  ``test_zero_minutes_still_builds_a_tz_aware_cutoff_predicate``.
* ``_11`` L1241 ``>=`` -> ``>`` ->
  ``test_where_is_called_with_the_inclusive_cutoff_comparison`` (``str(
  stmt.whereclause)`` is ``"... >= :recorded_at_1"`` shipped vs ``"> :..."``) and
  the same text leg in the two tests above.
* ``_12`` L1244 ``is not`` -> ``is``.  mutmut's own snapshot
  (``spans_copy.json`` ``get_stats_from_db__mutmut_12``) shows the mutated site is
  ``if limit is not None:``; the bank's L1244 window carries both ``is not``
  sites, so BOTH gates are killed: gate-OFF leg
  ``test_no_filters_builds_a_bare_ordered_select`` (measured: the flipped limit
  gate yields a statement with NO LIMIT clause where shipped has none either - the
  minutes-gate flip raises ``now - None`` -> ``[]``), gate-ON leg
  ``test_limit_clause_carries_the_exact_limit_value`` (flipped: LIMIT clause
  absent) and ``test_zero_minutes_still_builds_a_tz_aware_cutoff_predicate``
  (minutes-gate flip: ``[]``).
* ``_13`` L1245 ``query = None`` / ``_14`` L1245 ``query.limit(None)`` (measured:
  compiles with NO LIMIT clause) / ``_16`` L1247 ``session.execute(None)``
  -> ``test_execute_receives_exactly_one_select_statement`` (``None`` can never
  satisfy the ``Select`` identity) plus the LIMIT-value and shape asserts.
* ``_18`` L1252 message -> ``None`` / ``_19`` L1252 ``extra`` -> ``None`` /
  ``_21`` L1252 ``extra=`` dropped
  -> ``test_database_failure_logs_the_exact_error_record``.  These three diffs are
  MULTI-LINE and the shared harness re-indents the AFTER text wrongly (its splice
  does not compile - "unparseable"), so they are additionally proven with
  hand-built mutants: ``/tmp/wp-pw/gm/probe19/manual_mutants.py``.
* ``_22``/``_23``/``_24`` L1253 message XX / lower / upper
  -> ``test_database_failure_logs_the_exact_error_record``.
* ``_25``/``_26`` L1255 ``"operation"`` KEY XX / upper -> same test (the record
  attribute disappears).  ``_27``/``_28`` L1255 VALUE
  ``"get_stats_from_database"`` XX / upper ->
  ``test_database_failure_extra_payload_is_verbatim`` - ``extra`` is not merged
  into the message, so VALUE mutants are invisible to attribute asserts and need
  the raw payload.
* ``_29``/``_30`` L1256 ``"minutes_filter"``, ``_31``/``_32`` L1257
  ``"limit_filter"``, ``_33``/``_34`` L1258 ``"error"``, ``_36``/``_37`` L1259
  ``"error_type"`` -> ``test_database_failure_logs_the_exact_error_record``.
* ``_35`` L1258 ``str(e)`` -> ``str(None)`` (measured: ``record.error`` becomes
  ``"None"``) and ``_38`` L1259 ``type(e)`` -> ``type(None)`` (``"NoneType"``)
  -> ``test_database_failure_logs_the_exact_error_record``.

Occurrence-twins, measured.  Inside the real ``get_stats_from_db`` block every key
has exactly one candidate except ``_12`` (two: the ``minutes`` and the ``limit``
gate, both killed above).  The same TEXT also occurs in the SIBLING function
``check_memory_pressure`` for ``_25``/``_26``/``_33``/``_34``/``_35``/``_36``/
``_37``/``_38`` and - once the shared harness' block window collapses (it
truncates at a multi-line signature's closing paren, see
``/tmp/wp-pw/gm/replay_fixed.py``) - file-wide for ``_6``/``_7``/``_11``; those
sibling occurrences are reddened by the G19 battery
``test_gpu_monitor_batch28_20.py``, and every true site (confirmed from mutmut's
snapshot in ``/tmp/wp-pw/gpu_monitor/mutant_copy.py``) is reddened HERE.

Shipped behaviour only - nothing here invents a contract.  Every pinned string is
transcribed from the shipped file at the line quoted in the test that asserts it,
and every value an assertion depends on is injected by this file (a frozen clock,
a crafted ``RuntimeError("db")``, two ``MagicMock`` rows, chosen
``minutes``/``limit`` values).

Discipline
----------
* Log assertions open a per-window ``caplog.set_level`` + ``caplog.clear()``
  filtered to this module's logger and read the RAW ``record.msg`` /
  ``record.levelno`` / ``record.args`` / ``record.exc_info``.
* The clock is frozen through a real module attribute of the module under test
  (``datetime``, imported at gpu_monitor.py:33) using a ``datetime`` subclass,
  installed per test - the manifest test_spec's "frozen clock".
  ``time.monotonic`` / ``time.perf_counter`` are never patched and no duration is
  asserted.
* Every patch site names a REAL module attribute and uses ``new=`` (a real spy /
  the frozen subclass / a local double) or ``autospec=True`` (WP4.2).  No
  import-time global spy: every double is installed inside a ``with`` block.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.sql.expression import Select

from backend.models.gpu_stats import GPUStats
from backend.services import gpu_monitor as M

LOG_NAME = M.logger.name  # "backend.services.gpu_monitor" (get_logger(__name__))

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shipped literals, transcribed from backend/services/gpu_monitor.py
# =============================================================================

# L1253: logger.error("Failed to retrieve GPU stats from database", extra={...})
DB_ERROR_MSG = "Failed to retrieve GPU stats from database"
# L1255: "operation": "get_stats_from_database"
DB_ERROR_OPERATION = "get_stats_from_database"

# The columns clause the shipped ``select(GPUStats)`` compiles from (column order
# per backend/models/gpu_stats.py:45-77).  audit correction #9: this assert is
# what distinguishes select(GPUStats) from select(None), whose compiled text keeps
# FROM / ORDER BY / the >= predicate / LIMIT.
COLUMNS_CLAUSE = (
    "SELECT gpu_stats.id, gpu_stats.recorded_at, gpu_stats.gpu_name, "
    "gpu_stats.gpu_utilization, gpu_stats.memory_used, gpu_stats.memory_total, "
    "gpu_stats.temperature, gpu_stats.power_usage, gpu_stats.inference_fps, "
    "gpu_stats.fan_speed, gpu_stats.sm_clock, gpu_stats.memory_bandwidth_utilization, "
    "gpu_stats.pstate, gpu_stats.throttle_reasons, gpu_stats.power_limit, "
    "gpu_stats.sm_clock_max, gpu_stats.compute_processes_count, "
    "gpu_stats.pcie_replay_counter, gpu_stats.temp_slowdown_threshold, "
    "gpu_stats.memory_clock, gpu_stats.memory_clock_max, gpu_stats.pcie_link_gen, "
    "gpu_stats.pcie_link_width, gpu_stats.pcie_tx_throughput, "
    "gpu_stats.pcie_rx_throughput, gpu_stats.encoder_utilization, "
    "gpu_stats.decoder_utilization, gpu_stats.bar1_used"
)
# L1236: .order_by(GPUStats.recorded_at.desc())
ORDER_BY_CLAUSE = "ORDER BY gpu_stats.recorded_at DESC"

# Frozen clock for this group's query-shape legs (L1240 ``datetime.now(UTC)``).
FROZEN_NOW = datetime(2026, 9, 27, 12, 0, 0, tzinfo=UTC)
# The fault injected into the error legs (``str(e)`` == "db").
DB_FAULT = "db"


# =============================================================================
# Clock seam
# =============================================================================


def frozen_datetime(moment: datetime) -> type[datetime]:
    """A ``datetime`` subclass whose ``now()`` returns `moment`.

    ``datetime`` is a real module attribute of the module under test, so replacing
    it with ``new=`` is a legitimate function-local seam.  ``now(None)`` stays
    faithful to CPython and returns a NAIVE value - which is precisely what makes
    the ``datetime.now(None)`` mutant observable instead of silent.
    """

    def now(cls: type[datetime], tz: object = None) -> datetime:
        return moment.astimezone(tz) if tz is not None else moment.replace(tzinfo=None)

    return type("FrozenDatetime", (datetime,), {"now": classmethod(now)})


# =============================================================================
# Observation helpers (batch27_01 pattern)
# =============================================================================


def win(caplog: pytest.LogCaptureFixture) -> None:
    """Open a capture window: DEBUG for this module's logger, empty buffer.

    ``set_level`` does NOT clear the buffer, so the ``clear()`` is load bearing.
    """
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()


def mine(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOG_NAME]


def at(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [r for r in mine(caplog) if r.levelno == level]


def only(caplog: pytest.LogCaptureFixture, level: int, msg: str) -> logging.LogRecord:
    """Exactly one record at ``level`` in the window, matching every field."""
    recs = at(caplog, level)
    assert len(recs) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record from {LOG_NAME}, "
        f"got {[(r.levelno, r.msg) for r in recs]!r}"
    )
    pin_record(recs[0], msg=msg, level=level)
    return recs[0]


def pin_record(r: logging.LogRecord, *, msg: str, level: int) -> None:
    """Assert the observable surface of one shipped log call.

    ``record.msg`` is the RAW message.  Both shipped sites in this group pass a
    plain message plus ``extra``, so ``args`` stays empty (a moved or dropped
    message argument lands IN ``msg``) and ``exc_info`` stays absent.
    """
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.getMessage() == msg, f"formatted text mutated: {r.getMessage()!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args: {r.args!r}"
    assert r.exc_info is None, f"exc_info present where shipped passes none: {r.exc_info!r}"


def silence(caplog: pytest.LogCaptureFixture) -> None:
    """No record at all from this module's logger (the success-path contract)."""
    assert mine(caplog) == [], f"success path logged: {[r.msg for r in mine(caplog)]!r}"


# =============================================================================
# Monitors and doubles
# =============================================================================


@pytest.fixture
def monitor() -> Iterator[M.GPUMonitor]:
    """A mock-mode GPUMonitor: pynvml import fails, nvidia-smi absent.

    ``sys.modules["pynvml"] = None`` is the interpreter's OWN ImportError trigger,
    so the ctor takes its shipped ImportError arm and never touches a GPU.
    """
    with (
        patch.dict("sys.modules", {"pynvml": None}),
        patch("backend.services.gpu_monitor.shutil.which", return_value=None, autospec=True),
    ):
        yield M.GPUMonitor()


def session_ctx(
    rows: list[object], *, boom: Exception | None = None
) -> tuple[MagicMock, AsyncMock]:
    """``(get_session double, session double)`` for the shipped ``async with`` body.

    ``session.execute`` is an ``AsyncMock`` that records the statement it was
    handed; ``result.scalars().all()`` yields `rows`, or ``execute`` raises `boom`.
    """
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    if boom is None:
        session.execute.return_value = result
    else:
        session.execute.side_effect = boom
    get_session = MagicMock(name="get_session")
    get_session.return_value = session
    return get_session, session


def select_spy(into: list[tuple[object, ...]]):
    """A real spy around the shipped ``sqlalchemy.select`` (records call args)."""

    def _spy(*args: object, **kwargs: object):
        into.append(args)
        return select(*args, **kwargs)

    return _spy


def statement_of(session: AsyncMock) -> object:
    """The single object the shipped code handed to ``session.execute``."""
    assert session.execute.await_count == 1, (
        f"session.execute call count mutated: {session.execute.await_count}"
    )
    return session.execute.await_args[0][0]


def text_of(stmt: object) -> str:
    return str(stmt.compile())


def params_of(stmt: object) -> dict[str, object]:
    return dict(stmt.compile().params)


def cutoff_of(stmt: object) -> datetime:
    """The bound cutoff parameter (``where(None)`` leaves none, which is a KILL)."""
    params = params_of(stmt)
    found = [v for v in params.values() if isinstance(v, datetime)]
    assert len(found) == 1, f"cutoff parameter missing / not unique: {params!r}"
    return found[0]


# =============================================================================
# SUCCESS path: the compiled query shape (L1234-L1248)
# =============================================================================


async def test_filtered_query_keeps_the_columns_order_and_predicates(monitor, caplog):
    """minutes=15 + limit=3 -> the shipped SELECT keeps all five shape features.

    Columns clause (kills ``select(None)`` - audit correction #9), FROM clause,
    ``ORDER BY gpu_stats.recorded_at DESC`` (kills ``order_by(None)``), the
    inclusive ``>=`` predicate (kills ``where(None)`` and ``>=``->``>``) and a
    LIMIT clause (kills ``query = None`` / ``query.limit(None)`` via the shape and
    ``session.execute(None)`` via ``statement_of``).
    """
    rows = [MagicMock(name="row-1"), MagicMock(name="row-2")]
    get_session, session = session_ctx(rows)
    win(caplog)
    with (
        patch.object(M, "get_session", new=get_session),
        patch.object(M, "datetime", new=frozen_datetime(FROZEN_NOW)),
    ):
        out = await monitor.get_stats_from_db(minutes=15, limit=3)

    assert out == rows, f"rows not returned verbatim: {out!r}"
    text = text_of(statement_of(session))
    assert COLUMNS_CLAUSE in text, f"columns clause mutated: {text[:90]!r}"
    assert "NULL AS anon_1" not in text, f"select(None) columns present: {text[:90]!r}"
    assert "FROM gpu_stats" in text, f"FROM clause mutated: {text[:90]!r}"
    assert ORDER_BY_CLAUSE in text, f"ORDER BY clause mutated: {text!r}"
    assert " >= " in str(statement_of(session).whereclause), (
        f"cutoff operator mutated: {str(statement_of(session).whereclause)!r}"
    )
    assert "LIMIT" in text, f"LIMIT clause mutated: {text[-60:]!r}"
    silence(caplog)


async def test_select_is_called_with_the_gpu_stats_model(monitor):
    """L1236 ``select(GPUStats)``: the entity identity is the direct pin for
    ``select(None)`` (mut_3) - the spy forwards to the real ``select``, so the
    statement the shipped code builds is still the shipped one."""
    calls: list[tuple[object, ...]] = []
    get_session, _session = session_ctx([])
    with (
        patch.object(M, "get_session", new=get_session),
        patch.object(M, "select", new=select_spy(calls)),
        patch.object(M, "datetime", new=frozen_datetime(FROZEN_NOW)),
    ):
        await monitor.get_stats_from_db()

    assert calls == [(GPUStats,)], f"select() call args mutated: {calls!r}"


async def test_order_by_is_called_with_the_recorded_at_desc_expression(monitor):
    """L1236 ``.order_by(GPUStats.recorded_at.desc())``: the ORDER BY expression
    identity is the direct pin for ``order_by(None)`` (mut_2)."""
    order_calls: list[tuple[object, ...]] = []
    real_select = M.select

    def spy_select(*args: object, **kwargs: object):
        stmt = real_select(*args, **kwargs)
        real_order_by = stmt.order_by

        def spy_order_by(*a: object, **k: object):
            order_calls.append(a)
            return real_order_by(*a, **k)

        stmt.order_by = spy_order_by  # instance-level seam on the built statement
        return stmt

    get_session, _session = session_ctx([])
    with (
        patch.object(M, "get_session", new=get_session),
        patch.object(M, "select", new=spy_select),
        patch.object(M, "datetime", new=frozen_datetime(FROZEN_NOW)),
    ):
        await monitor.get_stats_from_db()

    assert len(order_calls) == 1, f"order_by call count mutated: {order_calls!r}"
    (arg,) = order_calls[0]
    # NB: identity, never ``arg != None`` - comparing a SQLAlchemy column with
    # ``!=`` builds a BinaryExpression whose ``bool()`` raises TypeError.
    assert arg is not None, "order_by(None) - the ORDER BY expression was dropped"
    assert str(arg) == "gpu_stats.recorded_at DESC", f"order_by arg mutated: {arg!r}"


async def test_where_is_called_with_the_inclusive_cutoff_comparison(monitor):
    """L1241 ``query.where(GPUStats.recorded_at >= cutoff_time)``.

    The bound comparison is captured at the ``where`` call: shipped renders
    ``gpu_stats.recorded_at >= :recorded_at_1`` (kills ``where(None)`` - nothing is
    passed - and ``>=`` -> ``>``, whose render loses the ``=``) and its right side
    is the frozen-minus-15-minute tz-aware cutoff.
    """
    where_calls: list[tuple[object, ...]] = []
    real_select = M.select

    def spy_select(*args: object, **kwargs: object):
        stmt = real_select(*args, **kwargs)
        real_where = stmt.where

        def spy_where(*a: object, **k: object):
            where_calls.append(a)
            return real_where(*a, **k)

        stmt.where = spy_where
        return stmt

    get_session, _session = session_ctx([])
    with (
        patch.object(M, "get_session", new=get_session),
        patch.object(M, "select", new=spy_select),
        patch.object(M, "datetime", new=frozen_datetime(FROZEN_NOW)),
    ):
        await monitor.get_stats_from_db(minutes=15, limit=3)

    assert len(where_calls) == 1, f"where() call count mutated: {where_calls!r}"
    (clause,) = where_calls[0]
    # identity, not ``clause != None`` (see the order_by note above)
    assert clause is not None, "where(None) - the cutoff predicate was dropped"
    rendered = str(clause)
    assert rendered == "gpu_stats.recorded_at >= :recorded_at_1", (
        f"cutoff comparison mutated: {rendered!r}"
    )
    right = clause.right.value
    assert right == FROZEN_NOW - timedelta(minutes=15), f"cutoff value mutated: {right!r}"
    assert right.tzinfo is not None, f"cutoff is naive (datetime.now(None)): {right!r}"


async def test_cutoff_param_is_frozen_now_minus_minutes_and_tz_aware(monitor, caplog):
    """L1240/L1241 through the executed statement: the BOUND cutoff is
    frozen-now MINUS the requested minutes and is UTC-aware.

    Kills Subtract->Add (measured: the parameter becomes 12:15), the
    ``datetime.now(None)`` variant (parameter becomes naive) and ``where(None)``
    (no datetime parameter is bound at all).
    """
    get_session, session = session_ctx([])
    win(caplog)
    with (
        patch.object(M, "get_session", new=get_session),
        patch.object(M, "datetime", new=frozen_datetime(FROZEN_NOW)),
    ):
        await monitor.get_stats_from_db(minutes=15, limit=3)

    cutoff = cutoff_of(statement_of(session))
    assert cutoff == FROZEN_NOW - timedelta(minutes=15), (
        f"cutoff arithmetic mutated: {cutoff!r} != {FROZEN_NOW - timedelta(minutes=15)!r}"
    )
    assert cutoff.tzinfo is not None, f"cutoff lost its timezone: {cutoff!r}"
    assert cutoff.utcoffset() == timedelta(0), f"cutoff offset mutated: {cutoff!r}"
    assert cutoff < FROZEN_NOW, f"cutoff is in the future (Subtract->Add): {cutoff!r}"
    silence(caplog)


async def test_limit_clause_carries_the_exact_limit_value(monitor):
    """L1244/L1245: with ``limit=7`` the shipped code adds ``LIMIT`` with the
    exact value.

    Kills the gate flip (flipped: no LIMIT clause when a limit IS given),
    ``query = None`` (no statement at all) and ``query.limit(None)`` (measured:
    compiles with NO LIMIT clause).
    """
    get_session, session = session_ctx([])
    with (
        patch.object(M, "get_session", new=get_session),
        patch.object(M, "datetime", new=frozen_datetime(FROZEN_NOW)),
    ):
        await monitor.get_stats_from_db(minutes=15, limit=7)

    stmt = statement_of(session)
    text = text_of(stmt)
    assert "LIMIT" in text, f"LIMIT clause missing with limit=7: {text[-60:]!r}"
    assert params_of(stmt).get("param_1") == 7, f"LIMIT value mutated: {params_of(stmt)!r}"


async def test_no_filters_builds_a_bare_ordered_select(monitor, caplog):
    """minutes=None + limit=None (the shipped defaults): NO WHERE and NO LIMIT,
    rows returned, nothing logged.

    This is the gate-OFF leg for ``is not`` -> ``is`` (mut_12): under the flip the
    shipped defaults make ``minutes`` run ``now - None`` (TypeError -> ``[]``) and
    make ``limit`` compile a statement WITHOUT the LIMIT clause - both reddened.
    """
    rows = [MagicMock(name="row-1")]
    get_session, session = session_ctx(rows)
    win(caplog)
    with (
        patch.object(M, "get_session", new=get_session),
        patch.object(M, "datetime", new=frozen_datetime(FROZEN_NOW)),
    ):
        out = await monitor.get_stats_from_db()

    assert out == rows, f"unfiltered retrieval diverted to the error path: {out!r}"
    stmt = statement_of(session)
    text = text_of(stmt)
    assert "WHERE" not in text, f"WHERE clause present with minutes=None: {text[-90:]!r}"
    assert "LIMIT" not in text, f"LIMIT clause present with limit=None: {text[-90:]!r}"
    assert ORDER_BY_CLAUSE in text, f"ORDER BY clause mutated: {text[:90]!r}"
    silence(caplog)


async def test_zero_minutes_still_builds_a_tz_aware_cutoff_predicate(monitor, caplog):
    """``minutes=0`` is NOT None: shipped keeps the cutoff predicate (an INCLUSIVE
    ``>=`` on frozen-now) and still returns the rows.

    The minutes-gate twin of mut_12 drops the whole block here (and the shipped
    ``now - 0`` is exactly frozen-now), so this row makes that twin observable
    alongside the limit-gate leg above.
    """
    rows = [MagicMock(name="row-1"), MagicMock(name="row-2")]
    get_session, session = session_ctx(rows)
    win(caplog)
    with (
        patch.object(M, "get_session", new=get_session),
        patch.object(M, "datetime", new=frozen_datetime(FROZEN_NOW)),
    ):
        out = await monitor.get_stats_from_db(minutes=0)

    assert out == rows, f"minutes=0 diverted to the error path: {out!r}"
    stmt = statement_of(session)
    assert cutoff_of(stmt) == FROZEN_NOW, f"zero-minute cutoff mutated: {params_of(stmt)!r}"
    assert cutoff_of(stmt).tzinfo is not None, "zero-minute cutoff is naive"
    assert " >= " in str(stmt.whereclause), f"cutoff operator mutated: {str(stmt.whereclause)!r}"
    silence(caplog)


async def test_execute_receives_exactly_one_select_statement(monitor):
    """L1247 ``await session.execute(query)``: the executed argument is a real
    ``Select``.  ``None`` - produced by ``query = None`` (mut_13) or by
    ``session.execute(None)`` (mut_16) - fails this identity even though the mock
    was still awaited exactly once."""
    get_session, session = session_ctx([])
    with (
        patch.object(M, "get_session", new=get_session),
        patch.object(M, "datetime", new=frozen_datetime(FROZEN_NOW)),
    ):
        await monitor.get_stats_from_db(minutes=15, limit=3)

    assert session.execute.await_count == 1, (
        f"execute call count mutated: {session.execute.await_count}"
    )
    (arg,) = session.execute.await_args[0]
    assert isinstance(arg, Select), f"session.execute got a non-Select: {arg!r}"


async def test_success_paths_never_log_and_always_return_the_rows(monitor, caplog):
    """All three shipped filter combinations return the rows and log NOTHING, so a
    mutant diverted into the except arm is caught twice over (return value AND the
    absence of records) on every combination."""
    win(caplog)
    for kwargs in ({"minutes": 15, "limit": 3}, {}, {"limit": 1}, {"minutes": 7}):
        rows = [MagicMock(name="row")]
        get_session, session = session_ctx(rows)
        with (
            patch.object(M, "get_session", new=get_session),
            patch.object(M, "datetime", new=frozen_datetime(FROZEN_NOW)),
        ):
            out = await monitor.get_stats_from_db(**kwargs)
        assert out == rows, f"{kwargs} diverted to the error path: {out!r}"
        assert isinstance(statement_of(session), Select), f"{kwargs}: executed arg not a Select"
        silence(caplog)


# =============================================================================
# ERROR path: the NEM-1123 error-log contract (L1250-L1262)
# =============================================================================


async def test_database_failure_logs_the_exact_error_record(monitor, caplog):
    """``execute`` raises ``RuntimeError("db")`` -> ``[]`` plus exactly ONE ERROR.

    Pins the message text (kills msg->None and the XX/lower/upper variants) and
    every ``extra`` entry as a RECORD ATTRIBUTE: a renamed key moves the value to
    another attribute (the asserted attribute disappears), ``extra=None`` and the
    dropped ``extra`` kwarg leave NO attribute, and the ``str(None)`` /
    ``type(None)`` value mutants change the value.
    """
    get_session, _session = session_ctx([], boom=RuntimeError(DB_FAULT))
    win(caplog)
    with (
        patch.object(M, "get_session", new=get_session),
        patch.object(M, "datetime", new=frozen_datetime(FROZEN_NOW)),
    ):
        out = await monitor.get_stats_from_db(minutes=15, limit=3)

    assert out == [], f"error path must return an empty list: {out!r}"
    rec = only(caplog, logging.ERROR, DB_ERROR_MSG)
    assert len(mine(caplog)) == 1, f"extra records: {[r.msg for r in mine(caplog)]!r}"
    assert rec.operation == "get_stats_from_database", (  # L1255
        f'extra["operation"] key mutated: {getattr(rec, "operation", "<missing>")!r}'
    )
    assert rec.minutes_filter == 15, (  # L1256
        f'extra["minutes_filter"] mutated: {getattr(rec, "minutes_filter", "<missing>")!r}'
    )
    assert rec.limit_filter == 3, (  # L1257
        f'extra["limit_filter"] mutated: {getattr(rec, "limit_filter", "<missing>")!r}'
    )
    assert rec.error == DB_FAULT, (  # L1258 str(e)
        f'extra["error"] mutated: {getattr(rec, "error", "<missing>")!r}'
    )
    assert rec.error_type == "RuntimeError", (  # L1259 type(e).__name__
        f'extra["error_type"] mutated: {getattr(rec, "error_type", "<missing>")!r}'
    )


async def test_database_failure_extra_payload_is_verbatim(monitor, caplog):
    """The ``extra`` DICT as the logger receives it.

    ``extra`` entries never reach the message, so the VALUE mutants
    (``"get_stats_from_database"`` -> XX / upper) are invisible to attribute
    asserts; a handler attached to the shipped logger captures the payload and
    pins every shipped key AND value.
    """
    payloads: list[dict[str, object]] = []

    class _Grab(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if record.name == LOG_NAME:
                payloads.append(dict(record.__dict__))

    handler = _Grab()
    win(caplog)
    get_session, _session = session_ctx([], boom=RuntimeError(DB_FAULT))
    M.logger.addHandler(handler)
    try:
        with (
            patch.object(M, "get_session", new=get_session),
            patch.object(M, "datetime", new=frozen_datetime(FROZEN_NOW)),
        ):
            out = await monitor.get_stats_from_db(minutes=15, limit=3)
    finally:
        M.logger.removeHandler(handler)

    assert out == []
    assert len(payloads) == 1, f"expected exactly one payload: {payloads!r}"
    payload = payloads[0]
    assert payload["operation"] == DB_ERROR_OPERATION, (
        f'extra["operation"] value mutated: {payload.get("operation")!r}'
    )
    assert payload["minutes_filter"] == 15, f"extra mutated: {payload.get('minutes_filter')!r}"
    assert payload["limit_filter"] == 3, f"extra mutated: {payload.get('limit_filter')!r}"
    assert payload["error"] == DB_FAULT, f"extra mutated: {payload.get('error')!r}"
    assert payload["error_type"] == "RuntimeError", f"extra mutated: {payload.get('error_type')!r}"


async def test_error_record_fields_are_none_when_no_filters_were_given(monitor, caplog):
    """The shipped defaults on the error path: the same message, with
    ``minutes_filter`` / ``limit_filter`` None (so those two entries are pinned for
    BOTH of their shipped values across the group) and the fault text/type intact."""
    get_session, _session = session_ctx([], boom=ValueError("nope"))
    win(caplog)
    with (
        patch.object(M, "get_session", new=get_session),
        patch.object(M, "datetime", new=frozen_datetime(FROZEN_NOW)),
    ):
        out = await monitor.get_stats_from_db()

    assert out == []
    rec = only(caplog, logging.ERROR, DB_ERROR_MSG)
    assert rec.minutes_filter is None, (  # L1256
        f"minutes_filter is not None: {getattr(rec, 'minutes_filter', '<missing>')!r}"
    )
    assert rec.limit_filter is None, (  # L1257
        f"limit_filter is not None: {getattr(rec, 'limit_filter', '<missing>')!r}"
    )
    assert rec.error == "nope", f'extra["error"] mutated: {getattr(rec, "error", "<missing>")!r}'
    assert rec.error_type == "ValueError", (  # L1259
        f'extra["error_type"] mutated: {getattr(rec, "error_type", "<missing>")!r}'
    )


async def test_session_open_failure_uses_the_same_error_contract(monitor, caplog):
    """A failure inside ``async with get_session()`` - before any query exists -
    reaches the SAME except-block contract: ``[]`` + one ERROR with the shipped
    message and its five extras.  This is a second, independent route to
    L1252-L1262 so a killing leg cannot be satisfied by an incidental fall-through.
    """
    get_session = MagicMock(name="get_session")
    ctx = AsyncMock()
    ctx.__aenter__.side_effect = OSError("conn down")
    ctx.__aexit__.return_value = None
    get_session.return_value = ctx
    win(caplog)
    with patch.object(M, "get_session", new=get_session):
        out = await monitor.get_stats_from_db(minutes=5, limit=2)

    assert out == []
    rec = only(caplog, logging.ERROR, DB_ERROR_MSG)
    assert rec.operation == "get_stats_from_database"
    assert rec.minutes_filter == 5
    assert rec.limit_filter == 2
    assert rec.error == "conn down", (
        f'extra["error"] mutated: {getattr(rec, "error", "<missing>")!r}'
    )
    assert rec.error_type == "OSError", (
        f'extra["error_type"] mutated: {getattr(rec, "error_type", "<missing>")!r}'
    )
