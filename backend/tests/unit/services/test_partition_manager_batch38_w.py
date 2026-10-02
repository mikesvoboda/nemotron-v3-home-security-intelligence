# TARGET-MODULE: backend.services.partition_manager
"""Battery W — campaign #21 of the ladder (batch-38): kill-real coverage for
``backend/services/partition_manager.py`` (264 survivors at 63.9836% entering).

Harness-compatible by design (batch-30 single-process sweep): every test is a
module-level sync ``test_*()`` with no fixtures and no parametrize; coroutines
run through ``asyncio.run`` inside. The file is also collected by normal
pytest in the repo tree, so every seam swap restores in ``finally``.

What kills what:
* FAKE SESSION with a WHOLE-CALL-LIST mirror — every ``session.execute`` is
  recorded as the normalized tuple of its positional args (``TEXT:<sql>`` for
  a TextClause, the raw value otherwise, so ``text(...) -> None`` flips,
  ``{...} -> None`` flips, ``{"name"} -> {"XXnameXX"}/{"NAME"}`` key flips and
  the TRAILING-COMMA ARG DELETIONS (arg-count changes) all diverge); a
  scripted responder feeds per-call results and can RAISE (failure arms).
  Kills ``_check_partition_exists``/``_check_table_is_partitioned`` (2x6 keys),
  ``_create_partition`` (20: the FULL SQL string under the strftime format
  flips ``%y-%m-%d`` / ``%Y-%M-%D`` / ``XX…XX``, the ``=None`` date-strings and
  ``table_name = None``, plus the log record family), ``_drop_partition`` m6,
  ``_list_partitions`` (call args + the ``PartitionInfo`` field kwargs m28/29/
  30), ``ensure_partitions`` (the ``session/config/name -> None`` helper-call
  args, ``months_ahead`` ARG DELETION via a months_ahead=3 manager, the
  ``continue -> break`` twins on a 2-config + 2-partition script, the failure
  arm, ``created.append(None)``) and ``cleanup_old_partitions``/
  ``get_partition_stats`` (helper-call args + returned structures).
* LOG RECORD LISTS — a fake logger recording ``(level, msg, kwargs)`` compared
  as a WHOLE LIST: ``__init__`` (msg family, ``extra=None``, extra-deletion,
  key/case flips), ``_create_partition`` extra dict, ``ensure_partitions``
  (warning msg, error arm msg + the ``exc_info`` True→None/False/DELETED
  family, the final ``Created N partitions`` extra family), cleanup +
  ``run_maintenance`` (2-record list: msg flips, ``extra=None``/deletion, all
  five extra keys' XX/upper flips).
* FIXED-NOW + RAISING-NAIVE ``datetime`` — a fake module ``datetime`` (a real
  subclass; ``now(None)`` RAISES) stamps every mirror: kills the
  ``datetime.now(UTC) -> now(None)`` key in ``_get_partitions_to_create`` m3,
  the ``is_expired`` ``< -> <=`` key on the EXACT cutoff boundary, and pins
  the partition-count/name/sequence mirrors (``* 4 + 4 -> * 5 + 4``/``+ 5``,
  ``+ 1 -> + 2`` and the ``< -> <=``/``<=`` loop-bound twins via boundary-
  aligned explicit dates).
* WHOLE-DICT / WHOLE-LIST RETURNS — ``get_partition_pruning_hint`` (both-None
  dict, start-only/end-only polarities for the ``is None -> is not None``
  flips, month-boundary-exact ``end_date`` for ``<= -> <`` and the day-1→2
  walk, December-crossing for ``month == 12 -> 13`` ValueError),
  ``check_partition_balance`` (exact dicts incl. the ratio-EQUALS-3.0 polarity
  for ``<= -> <``, avg-exactly-1 for ``> 0 -> > 1``, a zero-row partition for
  ``> 0 -> >= 0`` and ones for ``> 1``, message polarities for
  ``and False``/``or True``), ``identify_partition_gaps`` (the Nov-20→Dec-2
  walk for the day-1→2 key, a max_date on a partition start for ``< -> <=``,
  December-crossing ValueError), ``recommend_retention_period`` (full
  table x flag matrix with mixed-case names), ``recommend_partition_interval``
  (the 1_000_000 / 1_000_001 boundaries + the ``recent`` string family),
  ``generate_partition_conversion_sql`` / ``generate_partition_indexes`` (the
  WHOLE statement lists incl. ``"" -> "XXXX"`` and the ``=None`` index names),
  ``get_partition_metadata``/``estimate_partition_size`` (exact floats kill
  the ``1024 -> 1025`` twins and the ``500 -> 501`` default flip).

Honesty ledger — dispositions registered EQUIVALENT (the sweep must show
GREEN on exactly these 30; anything else GREEN is a test gap). Each is a BODY
proof measured THIS session against the trampoline tree by construction probe
(``/home/agent/runs/b38-c21-probe-equiv.py`` + follow-ups, orig-vs-mutant
under the probe polarities):

* ``_calculate_partition_bounds`` m17/m18/m19, m40/m41/m42, m61/m62/m63,
  m83/m84/m85 (12) — deleting ONE of the positional ``0``s among
  ``datetime(y, m, d, 0, 0, 0, tzinfo=UTC)``: ``datetime``'s own defaults for
  hour/minute/second ARE 0 — reconstructed identical (probed equal on weekly/
  December/else shapes).
* ``_get_partitions_to_create`` m46/m59 (``tzinfo=UTC -> None``) and m50/m63
  (the ``tzinfo=UTC`` KWARG DELETION) and m54/m66 (day ``1 -> 2``) — the
  monthly walker consumes ``current_date`` ONLY via ``.year``/``.month`` and
  rebuilds a fresh aware stamp each iteration, so the day/tzinfo of the
  intermediate is unobservable (probed equal for monthly AND weekly configs
  under the fixed now).
* ``_parse_partition_bounds`` m34/m58 (``replace(" ", "T") ->
  replace("XX ", "T")``) and m36/m60 (``" " -> "t"``) — this interpreter's
  ``datetime.fromisoformat`` accepts BOTH the space- and ``t``-separated
  forms (measured: ``fromisoformat("2026-01-01 10:30:00")`` parses), so the
  space branch parses identically either way; m38/m62 (``strptime(...).
  replace(tzinfo=UTC) -> replace(tzinfo=None)``) — the guard two lines below
  (``if start.tzinfo is None: replace(tzinfo=UTC)``) re-normalizes
  immediately.
* ``_list_partitions`` m25 (``if start_date and end_date -> or``) —
  ``_parse_partition_bounds`` can only return BOTH-None or BOTH-set (a
  one-sided match raises inside its try → caught → ``(None, None)``), so the
  two gates accept the same rows (probed on valid/garbage/mixed row sets).
* ``check_partition_balance`` m15 (``or True``) / m17 (``> 0 -> >= 0``) /
  m19 (else ``0 -> 1``) — ``avg_rows`` is ``sum/len`` over counts FILTERED
  ``> 0``, hence STRICTLY POSITIVE: the guard is always True and the else
  arm unreachable; m28 (``if partitions … or True``) — non-empty by the early
  return above (probed across [1]…[1,1,1,9,3]).
* ``get_partition_metadata`` m20 — the ``avg_row_size_bytes=500`` KWARG
  DELETION: ``estimate_partition_size``'s own parameter default IS 500 —
  reconstructed identical.

All other 234 survivor keys have an explicit kill polarity in this battery.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import re
from typing import Any

from backend.services.partition_manager import (
    DEFAULT_PARTITION_CONFIGS,
    PartitionConfig,
    PartitionInfo,
    PartitionManager,
)

_TABLE = "detections"
_COL = "detected_at"
_NOW_Y, _NOW_MO, _NOW_D = 2026, 12, 15
_STAMP = dt.datetime(_NOW_Y, _NOW_MO, _NOW_D, 10, 30, 0, tzinfo=dt.UTC)


def _globals_of(fn: Any) -> dict[str, Any]:
    """Module globals of the REAL function (mutant-tree wrappers delegate)."""
    f = fn
    while hasattr(f, "__wrapped__"):
        f = f.__wrapped__
    return f.__globals__


_G = _globals_of(PartitionManager.run_maintenance)


def _swap(key: str, value: Any) -> Any:
    old = _G[key]

    def restore() -> None:
        _G[key] = old

    _G[key] = value
    return restore


class _Env:
    """A bundle of seam swaps with one finally-friendly close()."""

    def __init__(self, swappers: list[Any]) -> None:
        self._swappers = swappers

    def close(self) -> None:
        for s in reversed(self._swappers):
            s()


class _Logger:
    def __init__(self) -> None:
        self.records: list[Any] = []

    def info(self, msg: Any = None, **kw: Any) -> None:
        self.records.append(("info", msg, kw))

    def debug(self, msg: Any = None, **kw: Any) -> None:
        self.records.append(("debug", msg, kw))

    def warning(self, msg: Any = None, **kw: Any) -> None:
        self.records.append(("warning", msg, kw))

    def error(self, msg: Any = None, **kw: Any) -> None:
        self.records.append(("error", msg, kw))


class _FixedNow(dt.datetime):
    """Fake module ``datetime``: now(UTC) fixed at 2026-12-15T10:30, naive raises."""

    @classmethod
    def now(cls, tz: Any = None) -> Any:
        if tz is None:
            raise RuntimeError("naive now")
        return cls(_NOW_Y, _NOW_MO, _NOW_D, 10, 30, 0, tzinfo=tz)


def _norm_sql(t: Any) -> Any:
    if hasattr(t, "text"):
        return "TEXT:" + re.sub(r"\s+", " ", t.text).strip()
    return t


class _Res:
    def __init__(self, rows: Any = None, scalar: Any = None) -> None:
        self._rows = rows if rows is not None else []
        self._scalar = scalar

    def fetchall(self) -> Any:
        return self._rows

    def scalar_one_or_none(self) -> Any:
        return self._scalar


class _Sess:
    """Fake AsyncSession: whole-call spy + scripted responder + commit count."""

    def __init__(self, respond: Any = None) -> None:
        self.calls: list[Any] = []
        self.commits = 0
        self._respond = respond

    async def execute(self, *args: Any) -> Any:
        self.calls.append(tuple(_norm_sql(a) if a is not None else None for a in args))
        out = self._respond(args) if self._respond else _Res()
        if isinstance(out, BaseException):
            raise out
        return out

    async def commit(self) -> None:
        self.commits += 1


class _GS:
    """Fake ``get_session``: async CM handing out ONE shared session."""

    def __init__(self, sess: _Sess) -> None:
        self.sess = sess
        self.entered = 0

    def __call__(self) -> Any:
        return self

    async def __aenter__(self) -> Any:
        self.entered += 1
        return self.sess

    async def __aexit__(self, *args: Any) -> bool:
        del args
        return False


_SQL_EXISTS = "TEXT:SELECT relname FROM pg_class WHERE relname = :name AND relkind = 'r'"
_SQL_PART = "TEXT:SELECT relkind FROM pg_class WHERE relname = :name"
_SQL_LIST = (
    "TEXT:SELECT c.relname AS partition_name, pg_catalog.pg_get_expr(c.relpartbound, "
    "c.oid) AS bounds, (SELECT reltuples FROM pg_class WHERE relname = c.relname) AS "
    "row_count FROM pg_catalog.pg_class c JOIN pg_catalog.pg_inherits i ON c.oid = "
    "i.inhrelid JOIN pg_catalog.pg_class p ON i.inhparent = p.oid WHERE p.relname = "
    ":table_name AND c.relkind = 'r' ORDER BY c.relname"
)


def _kind_of(args: Any) -> str:
    """Classify a raw execute() first-arg for the responder."""
    t = getattr(args[0], "text", None) if args else None
    kind = "other"
    if isinstance(t, str):
        s = re.sub(r"\s+", " ", t).strip()
        if s.startswith("CREATE TABLE"):
            kind = "create"
        elif s.startswith("DROP TABLE"):
            kind = "drop"
        elif "pg_get_expr" in s:
            kind = "list"
        elif "relkind = 'r'" in s:
            kind = "exists"
        elif s.startswith("SELECT relkind"):
            kind = "part"
    return kind


def _mgr(**kw: Any) -> PartitionManager:
    return PartitionManager(**kw)


def _cfg(
    table: str = _TABLE, col: str = _COL, interval: str = "monthly", ret: int = 12
) -> PartitionConfig:
    return PartitionConfig(
        table_name=table, partition_column=col, partition_interval=interval, retention_months=ret
    )


def _info(name: str, start: dt.datetime, end: dt.datetime, rows: int = 0) -> PartitionInfo:
    return PartitionInfo(
        name=name, table_name=_TABLE, start_date=start, end_date=end, row_count=rows
    )


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _bounds(cfg: Any, date: dt.datetime) -> tuple[dt.datetime, dt.datetime]:
    """PLAIN-CODE mirror of _calculate_partition_bounds (orig algorithm)."""
    if cfg.partition_interval == "weekly":
        start = dt.datetime(date.year, date.month, date.day, tzinfo=dt.UTC) - dt.timedelta(
            days=date.weekday()
        )
        return start, start + dt.timedelta(days=7)
    start = dt.datetime(date.year, date.month, 1, tzinfo=dt.UTC)
    if date.month == 12:
        return start, dt.datetime(date.year + 1, 1, 1, tzinfo=dt.UTC)
    return start, dt.datetime(date.year, date.month + 1, 1, tzinfo=dt.UTC)


def _mm_name(table: str, d: dt.datetime) -> str:
    return f"{table}_y{d.year}m{d.month:02d}"


def _add_month(d: dt.datetime) -> dt.datetime:
    if d.month == 12:
        return dt.datetime(d.year + 1, 1, 1, tzinfo=dt.UTC)
    return dt.datetime(d.year, d.month + 1, 1, tzinfo=dt.UTC)


def _d(y: int, mo: int, d: int, h: int = 0) -> dt.datetime:
    return dt.datetime(y, mo, d, h, tzinfo=dt.UTC)


def _pstr(s: Any) -> Any:
    """Serialize a PartitionInfo for whole-list equality mirrors."""
    return (s.name, s.table_name, s.start_date, s.end_date, s.row_count)


def _bstr(p: Any) -> Any:
    """Serialize a created (name, start, end) triple."""
    return (p[0], p[1], p[2])


def _mm_walk(end: dt.datetime, start: dt.datetime) -> list[str]:
    """PLAIN-CODE month-name walk from ``start`` while month <= ``end``'s month."""
    out: list[str] = []
    cur = dt.datetime(start.year, start.month, 1, tzinfo=dt.UTC)
    while (cur.year, cur.month) <= (end.year, end.month):
        out.append(_mm_name("detections", cur))
        cur = _add_month(cur)
    return out


def _now_weekly_seq(n: int) -> list[Any]:
    """PLAIN-CODE mirror of the weekly walker from the fixed now (2026-12-15)."""
    out: list[Any] = []
    cur = _STAMP
    for _ in range(n):
        start = dt.datetime(cur.year, cur.month, cur.day, tzinfo=dt.UTC) - dt.timedelta(
            days=cur.weekday()
        )
        end = start + dt.timedelta(days=7)
        iso = cur.isocalendar()
        out.append((f"gpu_stats_y{iso[0]}w{iso[1]:02d}", start, end))
        cur = end
    return out


def _mm_seq(n: int) -> list[Any]:
    """PLAIN-CODE mirror of the monthly walker from the fixed now: n+1 triples."""
    out: list[Any] = []
    cur = _STAMP
    for _ in range(n + 1):
        out.append((_mm_name("detections", cur), *_bounds(_cfg(), cur)))
        cur = _add_month(dt.datetime(cur.year, cur.month, 1, tzinfo=dt.UTC))
    return out


_VALID_ROW = (
    "p1",
    "FOR VALUES FROM ('2026-01-01T10:30:00') TO ('2026-02-01T10:30:00')",
    100,
)
_VALID_ROW2 = ("p2", "FOR VALUES FROM ('2026-02-01') TO ('2026-03-01')", 0)
_GARBAGE_ROW = ("p3", "FOR VALUES FROM ('2026-01-01') TO ('broken", 5)


def _resp_list(rows: Any) -> Any:
    def respond(args: Any) -> Any:
        if _kind_of(args) == "list":
            return _Res(rows=rows)
        return _Res()

    return respond


# ---------------------------------------------------------------------------
# PartitionInfo.is_expired
# ---------------------------------------------------------------------------


def test_is_expired() -> None:
    """Whole truth table at the EXACT retention cutoffs (fixed now)."""
    restore = _swap("datetime", _FixedNow)
    try:
        info = _info("p", _d(2025, 12, 1), _STAMP - dt.timedelta(days=360))  # == cutoff EXACTLY
        assert info.is_expired(12) is False  # m7 (<=) would return True
        assert _info("p", _d(2025, 12, 1), _STAMP - dt.timedelta(days=361)).is_expired(12) is True
        assert _info("p", _d(2026, 1, 1), _STAMP - dt.timedelta(days=359)).is_expired(12) is False
        assert _info("p", _d(2025, 1, 1), _STAMP - dt.timedelta(days=400)).is_expired(12) is True
        assert _info("p", _d(2026, 1, 1), _STAMP - dt.timedelta(days=100)).is_expired(1) is True
        assert _info("p", _d(2026, 10, 1), _STAMP - dt.timedelta(days=29)).is_expired(1) is False
        assert _info("p", _d(2026, 10, 1), _STAMP - dt.timedelta(days=31)).is_expired(1) is True
        assert _info("p", _d(2025, 1, 1), _d(2025, 2, 1)).is_expired(0) is True
        assert _info("p", _d(2026, 10, 1), _d(2026, 12, 20)).is_expired(0) is False
    finally:
        restore()


# ---------------------------------------------------------------------------
# __init__ log record
# ---------------------------------------------------------------------------


def _init_env() -> tuple[_Env, _Logger]:
    log = _Logger()
    env = _Env([_swap("logger", log)])
    return env, log


def test_init_log() -> None:
    """The __init__ info record is compared as a WHOLE (level, msg, kwargs)."""
    env, log = _init_env()
    try:
        mgr = _mgr()
        assert mgr.months_ahead == 2
        assert log.records == [
            (
                "info",
                "PartitionManager initialized",
                {
                    "extra": {
                        "tables": [c.table_name for c in DEFAULT_PARTITION_CONFIGS],
                        "months_ahead": 2,
                    }
                },
            )
        ]
        log.records.clear()
        cfgs = [_cfg("t1"), _cfg("t2")]
        mgr2 = _mgr(configs=cfgs, months_ahead=3)
        assert mgr2.configs is cfgs
        assert log.records == [
            (
                "info",
                "PartitionManager initialized",
                {"extra": {"tables": ["t1", "t2"], "months_ahead": 3}},
            )
        ]
        log.records.clear()
        mgr3 = _mgr(configs=[])
        assert mgr3.configs == list(DEFAULT_PARTITION_CONFIGS)  # `or`-default still live
        assert log.records[0][2]["extra"]["tables"] == [
            c.table_name for c in DEFAULT_PARTITION_CONFIGS
        ]
    finally:
        env.close()


# ---------------------------------------------------------------------------
# _sanitize_table_name (defensive: every survivor arm)
# ---------------------------------------------------------------------------


def test_sanitize() -> None:
    mgr = _mgr()
    assert mgr._sanitize_table_name("detections") == "detections"
    assert mgr._sanitize_table_name("MiXeD_Case9") == "mixed_case9"
    assert mgr._sanitize_table_name('dro"p;tab-le') == "droptable"
    assert mgr._sanitize_table_name("!!!") == "unknown"


# ---------------------------------------------------------------------------
# _generate_partition_name
# ---------------------------------------------------------------------------


def test_generate_partition_name() -> None:
    """ISO-week family incl. the Jan-1-2027 -> 2026w53 back-weeking (m7 [1]->[2])."""
    mgr = _mgr()
    assert mgr._generate_partition_name(_cfg(), _d(2026, 1, 15)) == "detections_y2026m01"
    assert mgr._generate_partition_name(_cfg(), _d(2026, 12, 15)) == "detections_y2026m12"
    assert mgr._generate_partition_name(_cfg(), _d(2027, 1, 1)) == "detections_y2027m01"
    w = _cfg("gpu_stats", "recorded_at", "weekly")
    assert mgr._generate_partition_name(w, _STAMP) == "gpu_stats_y2026w51"
    assert mgr._generate_partition_name(w, _d(2026, 12, 14)) == "gpu_stats_y2026w51"
    assert mgr._generate_partition_name(w, _d(2026, 12, 21)) == "gpu_stats_y2026w52"
    # name year is the GREGORIAN year (2027) while the week is the ISO one (53):
    # m7 (isocalendar()[1] -> [2]) would produce w05 from weekday() == 5.
    assert mgr._generate_partition_name(w, _d(2027, 1, 1)) == "gpu_stats_y2027w53"


# ---------------------------------------------------------------------------
# _calculate_partition_bounds
# ---------------------------------------------------------------------------


def test_calculate_partition_bounds() -> None:
    """Exact tuples; a PLAIN-CODE mirror guards the whole input domain."""
    mgr = _mgr()
    m = _cfg()
    w = _cfg("gpu_stats", "recorded_at", "weekly")
    dates = [_d(2026, 1, 1), _d(2026, 6, 17), _d(2026, 12, 15), _d(2026, 12, 31), _d(2027, 2, 28)]
    for date in dates:
        for cfg in (m, w):
            assert mgr._calculate_partition_bounds(cfg, date) == _bounds(cfg, date)
    assert mgr._calculate_partition_bounds(w, _d(2026, 12, 15)) == (
        _d(2026, 12, 14),
        _d(2026, 12, 21),
    )
    assert mgr._calculate_partition_bounds(w, _d(2026, 12, 14)) == (
        _d(2026, 12, 14),
        _d(2026, 12, 21),
    )
    assert mgr._calculate_partition_bounds(m, _d(2026, 12, 31)) == (_d(2026, 12, 1), _d(2027, 1, 1))
    assert mgr._calculate_partition_bounds(m, _d(2026, 2, 10)) == (_d(2026, 2, 1), _d(2026, 3, 1))


# ---------------------------------------------------------------------------
# _get_partitions_to_create (fixed now)
# ---------------------------------------------------------------------------


def test_get_partitions_to_create_monthly() -> None:
    """Whole monthly sequence (kills *4/+4/+1/+2/loop-bound/3-key names)."""
    restore = _swap("datetime", _FixedNow)
    try:
        mgr = _mgr()
        m = _cfg()
        for n in (0, 1, 2, 3):
            assert [_bstr(p) for p in mgr._get_partitions_to_create(m, n)] == [
                _bstr(p) for p in _mm_seq(n)
            ]
        got = mgr._get_partitions_to_create(m, 2)
        assert [p[0] for p in got] == [
            "detections_y2026m12",
            "detections_y2027m01",
            "detections_y2027m02",
        ]
        assert got[0][1] == _d(2026, 12, 1) and got[0][2] == _d(2027, 1, 1)
        assert got[2][1] == _d(2027, 2, 1) and got[2][2] == _d(2027, 3, 1)
    finally:
        restore()


def test_get_partitions_to_create_weekly() -> None:
    """Whole weekly sequence (kills *4 -> *5 and +4 -> +5 loop counts)."""
    restore = _swap("datetime", _FixedNow)
    try:
        mgr = _mgr()
        w = _cfg("gpu_stats", "recorded_at", "weekly")
        for n in (0, 1, 2):
            assert [_bstr(p) for p in mgr._get_partitions_to_create(w, n)] == [
                _bstr(p) for p in _now_weekly_seq(n * 4 + 4)
            ]
    finally:
        restore()


def test_get_partitions_to_create_december() -> None:
    """December-anchored walker crosses into (2027, 1, 1) exactly once per month."""
    restore = _swap("datetime", _FixedNow)
    try:
        mgr = _mgr()

        class _FixedDec(_FixedNow):
            @classmethod
            def now(cls, tz: Any = None) -> Any:
                if tz is None:
                    raise RuntimeError("naive now")
                return cls(2026, 12, 1, 0, 0, 0, tzinfo=tz)

        _G["datetime"] = _FixedDec
        m = _cfg()
        got = mgr._get_partitions_to_create(m, 2)
        assert [_bstr(p) for p in got] == [
            ("detections_y2026m12", _d(2026, 12, 1), _d(2027, 1, 1)),
            ("detections_y2027m01", _d(2027, 1, 1), _d(2027, 2, 1)),
            ("detections_y2027m02", _d(2027, 2, 1), _d(2027, 3, 1)),
        ]
    finally:
        restore()


# ---------------------------------------------------------------------------
# _check_partition_exists / _check_table_is_partitioned (whole call-list)
# ---------------------------------------------------------------------------


def _resp_exists(scalar: Any) -> Any:
    def respond(args: Any) -> Any:
        if _kind_of(args) == "exists":
            return _Res(scalar=scalar)
        return _Res()

    return respond


def _resp_part(scalar: Any) -> Any:
    def respond(args: Any) -> Any:
        if _kind_of(args) == "part":
            return _Res(scalar=scalar)
        return _Res()

    return respond


def test_check_partition_exists() -> None:
    """Whole execute() call-list + both truth arms."""
    for scalar, want in ((None, False), ("detections_y2026m12", True), (0, True), (b"", True)):
        sess = _Sess(respond=_resp_exists(scalar))
        got = _run(
            PartitionManager.__new__(PartitionManager)._check_partition_exists(
                sess, "detections_y2026m12"
            )
        )
        assert got is want
        assert sess.calls == [(_SQL_EXISTS, {"name": "detections_y2026m12"})]


def test_check_table_is_partitioned() -> None:
    """Whole execute() call-list + every scalar arm."""
    mgr = PartitionManager.__new__(PartitionManager)
    for scalar, want in ((None, False), (b"p", True), (b"r", False), ("p", True), ("r", False)):
        sess = _Sess(respond=_resp_part(scalar))
        assert _run(mgr._check_table_is_partitioned(sess, "detections")) is want
        assert sess.calls == [(_SQL_PART, {"name": "detections"})]


# ---------------------------------------------------------------------------
# _create_partition / _drop_partition (whole SQL + whole log record)
# ---------------------------------------------------------------------------


def test_create_partition() -> None:
    """Full CREATE TABLE string (strftime family) + whole info record."""
    log = _Logger()
    env = _Env([_swap("logger", log)])
    try:
        sess = _Sess()
        mgr = PartitionManager.__new__(PartitionManager)
        _run(
            mgr._create_partition(
                sess, _cfg(), "detections_y2026m12", _d(2026, 12, 1), _d(2027, 1, 1)
            )
        )
        expected_sql = (
            "TEXT:CREATE TABLE IF NOT EXISTS detections_y2026m12 PARTITION OF detections "
            "FOR VALUES FROM ('2026-12-01') TO ('2027-01-01')"
        )
        assert sess.calls == [(expected_sql,)]
        assert log.records == [
            (
                "info",
                "Created partition detections_y2026m12",
                {
                    "extra": {
                        "table": "detections",
                        "partition": "detections_y2026m12",
                        "start": "2026-12-01",
                        "end": "2027-01-01",
                    }
                },
            )
        ]
    finally:
        env.close()


def test_drop_partition() -> None:
    log = _Logger()
    env = _Env([_swap("logger", log)])
    try:
        sess = _Sess()
        mgr = PartitionManager.__new__(PartitionManager)
        _run(mgr._drop_partition(sess, "detections_y2025m01"))
        assert sess.calls == [("TEXT:DROP TABLE IF EXISTS detections_y2025m01",)]
        assert log.records == [("info", "Dropped partition detections_y2025m01", {})]
    finally:
        env.close()


# ---------------------------------------------------------------------------
# _list_partitions / _parse_partition_bounds
# ---------------------------------------------------------------------------


def test_list_partitions() -> None:
    """Whole execute() call-list + whole returned rows (field kwargs m28-m30)."""
    mgr = PartitionManager.__new__(PartitionManager)
    rows = [_VALID_ROW, _GARBAGE_ROW, _VALID_ROW2]
    sess = _Sess(respond=_resp_list(rows))
    got = _run(mgr._list_partitions(sess, _cfg()))
    assert [_pstr(p) for p in got] == [
        (
            "p1",
            "detections",
            dt.datetime(2026, 1, 1, 10, 30, tzinfo=dt.UTC),
            dt.datetime(2026, 2, 1, 10, 30, tzinfo=dt.UTC),
            100,
        ),
        ("p2", "detections", _d(2026, 2, 1), _d(2026, 3, 1), 0),
    ]
    assert sess.calls == [(_SQL_LIST, {"table_name": "detections"})]


def test_parse_partition_bounds() -> None:
    """Every parse shape + the failure arm's WHOLE warning record."""
    log = _Logger()
    env = _Env([_swap("logger", log)])
    try:
        mgr = PartitionManager.__new__(PartitionManager)
        assert mgr._parse_partition_bounds("FOR VALUES FROM ('2026-01-01') TO ('2026-02-01')") == (
            _d(2026, 1, 1),
            _d(2026, 2, 1),
        )
        assert mgr._parse_partition_bounds(
            "FOR VALUES FROM ('2026-01-01T10:30:00') TO ('2026-02-01T22:15:00')"
        ) == (
            dt.datetime(2026, 1, 1, 10, 30, tzinfo=dt.UTC),
            dt.datetime(2026, 2, 1, 22, 15, tzinfo=dt.UTC),
        )
        assert mgr._parse_partition_bounds(
            "FOR VALUES FROM ('2026-01-01 10:30:00') TO ('2026-02-01 22:15:00')"
        ) == (
            dt.datetime(2026, 1, 1, 10, 30, tzinfo=dt.UTC),
            dt.datetime(2026, 2, 1, 22, 15, tzinfo=dt.UTC),
        )
        # NO match at all: the ``and`` gate falls through, NO warning record.
        assert mgr._parse_partition_bounds("garbage") == (None, None)
        assert log.records == []
        log.records.clear()
        # ONE-SIDED match: same fall-through with NO record. Under m15 (and -> or)
        # the block IS entered and ``to_match.group(1)`` raises AttributeError ->
        # an EXTRA warning record (the kill polarity).
        assert mgr._parse_partition_bounds("FROM ('2026-01-01') TO ('broken") == (None, None)
        assert log.records == []
        log.records.clear()
        # Regexes match but the DATES are invalid -> exception arm's WHOLE record.
        assert mgr._parse_partition_bounds("FROM ('2026-13-45') TO ('2026-14-99')") == (None, None)
        assert log.records == [
            (
                "warning",
                "Failed to parse partition bounds: FROM ('2026-13-45') TO ('2026-14-99')",
                {"exc_info": True},
            )
        ]
    finally:
        env.close()


# ---------------------------------------------------------------------------
# ensure_partitions (whole session-call list + whole log-record list)
# ---------------------------------------------------------------------------

_CREATE_M12 = (
    "TEXT:CREATE TABLE IF NOT EXISTS detections_y2026m12 PARTITION OF detections "
    "FOR VALUES FROM ('2026-12-01') TO ('2027-01-01')"
)
_CREATE_M01 = (
    "TEXT:CREATE TABLE IF NOT EXISTS detections_y2027m01 PARTITION OF detections "
    "FOR VALUES FROM ('2027-01-01') TO ('2027-02-01')"
)
_CREATE_M02 = (
    "TEXT:CREATE TABLE IF NOT EXISTS detections_y2027m02 PARTITION OF detections "
    "FOR VALUES FROM ('2027-02-01') TO ('2027-03-01')"
)
_CREATE_M03 = (
    "TEXT:CREATE TABLE IF NOT EXISTS detections_y2027m03 PARTITION OF detections "
    "FOR VALUES FROM ('2027-03-01') TO ('2027-04-01')"
)


def _created_info(partition: str, start: str, end: str, table: str = "detections") -> tuple:
    return (
        "info",
        f"Created partition {partition}",
        {"extra": {"table": table, "partition": partition, "start": start, "end": end}},
    )


def _resp_simple(part_scalar: Any = "p", exists_names: Any = (), fail_create: Any = None) -> Any:
    def respond(args: Any) -> Any:
        kind = _kind_of(args)
        params = args[1] if len(args) > 1 and isinstance(args[1], dict) else {}
        if kind == "part":
            return _Res(scalar=part_scalar if params.get("name") == "detections" else None)
        if kind == "exists":
            return _Res(scalar="x" if params.get("name") in exists_names else None)
        if kind == "create":
            return fail_create if fail_create is not None else _Res()
        return _Res()

    return respond


def test_ensure_partitions_creates_all() -> None:
    """Happy path: whole call list, whole log list, commit count, return list."""
    mgr = _mgr(configs=[_cfg()], months_ahead=0)
    log = _Logger()
    sess = _Sess(respond=_resp_simple())
    env = _Env(
        [_swap("logger", log), _swap("get_session", _GS(sess)), _swap("datetime", _FixedNow)]
    )
    try:
        created = _run(mgr.ensure_partitions())
        assert created == ["detections_y2026m12"]
        assert sess.calls == [
            (_SQL_PART, {"name": "detections"}),
            (_SQL_EXISTS, {"name": "detections_y2026m12"}),
            (_CREATE_M12,),
        ]
        assert sess.commits == 1
        assert log.records == [
            _created_info("detections_y2026m12", "2026-12-01", "2027-01-01"),
            ("info", "Created 1 partitions", {"extra": {"partitions": ["detections_y2026m12"]}}),
        ]
    finally:
        env.close()


def test_ensure_partitions_months_ahead() -> None:
    """months_ahead=3 flows into the walker (kills the arg-DELETION to the default 2)."""
    mgr = _mgr(configs=[_cfg()], months_ahead=3)
    log = _Logger()
    sess = _Sess(respond=_resp_simple())
    env = _Env(
        [_swap("logger", log), _swap("get_session", _GS(sess)), _swap("datetime", _FixedNow)]
    )
    try:
        created = _run(mgr.ensure_partitions())
        assert created == [
            "detections_y2026m12",
            "detections_y2027m01",
            "detections_y2027m02",
            "detections_y2027m03",
        ]
        assert sess.calls == [
            (_SQL_PART, {"name": "detections"}),
            (_SQL_EXISTS, {"name": "detections_y2026m12"}),
            (_CREATE_M12,),
            (_SQL_EXISTS, {"name": "detections_y2027m01"}),
            (_CREATE_M01,),
            (_SQL_EXISTS, {"name": "detections_y2027m02"}),
            (_CREATE_M02,),
            (_SQL_EXISTS, {"name": "detections_y2027m03"}),
            (_CREATE_M03,),
        ]
        assert log.records[-1] == (
            "info",
            "Created 4 partitions",
            {
                "extra": {
                    "partitions": [
                        "detections_y2026m12",
                        "detections_y2027m01",
                        "detections_y2027m02",
                        "detections_y2027m03",
                    ]
                }
            },
        )
    finally:
        env.close()


def test_ensure_partitions_skips_unpartitioned() -> None:
    """First config skipped -> ``continue`` must still process the second (m8 break)."""
    mgr = _mgr(configs=[_cfg("events", "occurred_at"), _cfg()], months_ahead=0)
    log = _Logger()
    sess = _Sess(respond=_resp_simple())
    env = _Env(
        [_swap("logger", log), _swap("get_session", _GS(sess)), _swap("datetime", _FixedNow)]
    )
    try:
        created = _run(mgr.ensure_partitions())
        assert created == ["detections_y2026m12"]
        assert sess.calls == [
            (_SQL_PART, {"name": "events"}),
            (_SQL_PART, {"name": "detections"}),
            (_SQL_EXISTS, {"name": "detections_y2026m12"}),
            (_CREATE_M12,),
        ]
        assert log.records == [
            ("warning", "Table events is not partitioned, skipping", {}),
            _created_info("detections_y2026m12", "2026-12-01", "2027-01-01"),
            ("info", "Created 1 partitions", {"extra": {"partitions": ["detections_y2026m12"]}}),
        ]
    finally:
        env.close()


def test_ensure_partitions_existing_skipped() -> None:
    """First partition exists -> ``continue`` must still create the next (m18 break)."""
    mgr = _mgr(configs=[_cfg()], months_ahead=1)
    log = _Logger()
    sess = _Sess(respond=_resp_simple(exists_names={"detections_y2026m12"}))
    env = _Env(
        [_swap("logger", log), _swap("get_session", _GS(sess)), _swap("datetime", _FixedNow)]
    )
    try:
        created = _run(mgr.ensure_partitions())
        assert created == ["detections_y2027m01"]
        assert sess.calls == [
            (_SQL_PART, {"name": "detections"}),
            (_SQL_EXISTS, {"name": "detections_y2026m12"}),
            (_SQL_EXISTS, {"name": "detections_y2027m01"}),
            (_CREATE_M01,),
        ]
        assert log.records == [
            _created_info("detections_y2027m01", "2027-01-01", "2027-02-01"),
            ("info", "Created 1 partitions", {"extra": {"partitions": ["detections_y2027m01"]}}),
        ]
    finally:
        env.close()


def test_ensure_partitions_create_failure() -> None:
    """Failure arm: whole error record (msg text + exc_info) and empty return."""
    mgr = _mgr(configs=[_cfg()], months_ahead=0)
    log = _Logger()
    sess = _Sess(respond=_resp_simple(fail_create=RuntimeError("boom")))
    env = _Env(
        [_swap("logger", log), _swap("get_session", _GS(sess)), _swap("datetime", _FixedNow)]
    )
    try:
        created = _run(mgr.ensure_partitions())
        assert created == []
        assert log.records == [
            ("error", "Failed to create partition detections_y2026m12: boom", {"exc_info": True})
        ]
    finally:
        env.close()


# ---------------------------------------------------------------------------
# cleanup_old_partitions
# ---------------------------------------------------------------------------


def _resp_cleanup(rows: Any, fail_drop: Any = None) -> Any:
    def respond(args: Any) -> Any:
        kind = _kind_of(args)
        if kind == "list":
            return _Res(rows=rows)
        if kind == "drop":
            return fail_drop if fail_drop is not None else _Res()
        return _Res()

    return respond


_EXPIRED_ROW = ("p_old", "FOR VALUES FROM ('2025-11-01') TO ('2025-12-01')", 7)
_FRESH_ROW = ("p2", "FOR VALUES FROM ('2026-02-01') TO ('2026-03-01')", 5)


def test_cleanup_old_partitions() -> None:
    mgr = _mgr(configs=[_cfg()], months_ahead=0)
    log = _Logger()
    sess = _Sess(respond=_resp_cleanup([_EXPIRED_ROW, _FRESH_ROW, _GARBAGE_ROW]))
    env = _Env(
        [_swap("logger", log), _swap("get_session", _GS(sess)), _swap("datetime", _FixedNow)]
    )
    try:
        dropped = _run(mgr.cleanup_old_partitions())
        assert dropped == ["p_old"]
        assert sess.calls == [
            (_SQL_LIST, {"table_name": "detections"}),
            ("TEXT:DROP TABLE IF EXISTS p_old",),
        ]
        assert sess.commits == 1
        assert log.records == [
            ("info", "Dropped partition p_old", {}),
            ("info", "Dropped 1 old partitions", {"extra": {"partitions": ["p_old"]}}),
        ]
    finally:
        env.close()


def test_cleanup_drop_failure() -> None:
    mgr = _mgr(configs=[_cfg()], months_ahead=0)
    log = _Logger()
    sess = _Sess(respond=_resp_cleanup([_EXPIRED_ROW], fail_drop=RuntimeError("nope")))
    env = _Env(
        [_swap("logger", log), _swap("get_session", _GS(sess)), _swap("datetime", _FixedNow)]
    )
    try:
        dropped = _run(mgr.cleanup_old_partitions())
        assert dropped == []
        assert log.records == [
            ("error", "Failed to drop partition p_old: nope", {"exc_info": True})
        ]
    finally:
        env.close()


# ---------------------------------------------------------------------------
# get_partition_stats
# ---------------------------------------------------------------------------


def test_get_partition_stats() -> None:
    mgr = _mgr(configs=[_cfg()], months_ahead=0)
    sess = _Sess(respond=_resp_list([_FRESH_ROW, _EXPIRED_ROW]))
    env = _Env([_swap("get_session", _GS(sess)), _swap("datetime", _FixedNow)])
    try:
        stats = _run(mgr.get_partition_stats())
        assert stats == {
            "detections": [
                {
                    "name": "p2",
                    "start_date": "2026-02-01T00:00:00+00:00",
                    "end_date": "2026-03-01T00:00:00+00:00",
                    "row_count": 5,
                    "is_expired": False,
                },
                {
                    "name": "p_old",
                    "start_date": "2025-11-01T00:00:00+00:00",
                    "end_date": "2025-12-01T00:00:00+00:00",
                    "row_count": 7,
                    "is_expired": True,
                },
            ]
        }
        assert sess.calls == [(_SQL_LIST, {"table_name": "detections"})]
    finally:
        env.close()


# ---------------------------------------------------------------------------
# run_maintenance (2-anchor log list + exact result dict)
# ---------------------------------------------------------------------------


def test_run_maintenance() -> None:
    mgr = _mgr(configs=[_cfg()], months_ahead=0)
    log = _Logger()
    simple = _resp_simple()

    def respond(args: Any) -> Any:
        if _kind_of(args) == "list":
            return _Res(rows=[_FRESH_ROW])
        return simple(args)

    sess = _Sess(respond=respond)
    gs = _GS(sess)
    env = _Env([_swap("logger", log), _swap("get_session", gs), _swap("datetime", _FixedNow)])
    try:
        result = _run(mgr.run_maintenance())
        assert result == {
            "created": ["detections_y2026m12"],
            "dropped": [],
            "total_created": 1,
            "total_dropped": 0,
            "partition_counts": {"detections": 1},
        }
        assert gs.entered == 3
        assert sess.commits == 2
        assert log.records == [
            ("info", "Starting partition maintenance", {}),
            _created_info("detections_y2026m12", "2026-12-01", "2027-01-01"),
            ("info", "Created 1 partitions", {"extra": {"partitions": ["detections_y2026m12"]}}),
            (
                "info",
                "Partition maintenance completed",
                {
                    "extra": {
                        "partitions_created": ["detections_y2026m12"],
                        "partitions_dropped": [],
                        "total_created": 1,
                        "total_dropped": 0,
                        "partition_counts": {"detections": 1},
                    }
                },
            ),
        ]
    finally:
        env.close()


# ---------------------------------------------------------------------------
# generate_partition_conversion_sql / generate_partition_indexes
# ---------------------------------------------------------------------------


def test_generate_partition_conversion_sql() -> None:
    mgr = PartitionManager.__new__(PartitionManager)
    cfg = _cfg("My Table", "Detected At")
    assert mgr.generate_partition_conversion_sql(cfg) == [
        "-- Step 1: Rename existing table",
        "ALTER TABLE mytable RENAME TO mytable_old;",
        "",
        "-- Step 2: Create new partitioned table with same structure",
        "CREATE TABLE mytable (LIKE mytable_old INCLUDING ALL) PARTITION BY RANGE (detectedat);",
        "",
        "-- Step 3: Create initial partitions (run partition manager after)",
        "-- The PartitionManager.ensure_partitions() will create needed partitions",
        "",
        "-- Step 4: Migrate data (run in batches for large tables)",
        "INSERT INTO mytable SELECT * FROM mytable_old;",
        "",
        "-- Step 5: Drop old table after verification",
        "-- DROP TABLE mytable_old;  -- Uncomment after verification",
    ]


def test_generate_partition_indexes() -> None:
    mgr = PartitionManager.__new__(PartitionManager)
    cfg = _cfg()
    assert mgr.generate_partition_indexes(cfg, "detections_y2026m12") == [
        "CREATE INDEX IF NOT EXISTS idx_detections_y2026m12_detected_at "
        "ON detections_y2026m12 USING btree (detected_at);"
    ]
    assert mgr.generate_partition_indexes(cfg, "detections_y2026m12", include_brin=True) == [
        "CREATE INDEX IF NOT EXISTS idx_detections_y2026m12_detected_at "
        "ON detections_y2026m12 USING btree (detected_at);",
        "CREATE INDEX IF NOT EXISTS idx_detections_y2026m12_detected_at_brin "
        "ON detections_y2026m12 USING brin (detected_at);",
    ]


# ---------------------------------------------------------------------------
# get_partition_pruning_hint
# ---------------------------------------------------------------------------


def test_pruning_hint_no_dates() -> None:
    mgr = PartitionManager.__new__(PartitionManager)
    assert mgr.get_partition_pruning_hint("detections", "detected_at", None, None) == {
        "table": "detections",
        "column": "detected_at",
        "all_partitions": True,
        "partitions": [],
        "message": "No date filter - all partitions will be scanned",
    }


def test_pruning_hint_start_only() -> None:
    """end=None must WALK (kills the ``is None -> is not None`` and or-flip keys)."""
    restore = _swap("datetime", _FixedNow)
    try:
        mgr = PartitionManager.__new__(PartitionManager)
        hint = mgr.get_partition_pruning_hint("detections", "detected_at", _d(2026, 11, 20), None)
        # default end = fixed now + 365d = 2027-12-15 -> Nov-2026 .. Dec-2027.
        assert hint["partitions"] == _mm_walk(_d(2027, 12, 15), _d(2026, 11, 1))
        assert hint["partition_count"] == 14
        assert hint["message"] == "Query will scan 14 partition(s)"
        assert hint["all_partitions"] is False
    finally:
        restore()


def test_pruning_hint_end_only() -> None:
    """start=None takes the 2020-01-01 default walk (the mirror kills key flips)."""
    restore = _swap("datetime", _FixedNow)
    try:
        mgr = PartitionManager.__new__(PartitionManager)
        hint = mgr.get_partition_pruning_hint("detections", "detected_at", None, _d(2026, 3, 10))
        assert hint["partitions"] == _mm_walk(_d(2026, 3, 10), _d(2020, 1, 1))
        assert hint["partition_count"] == 75
        assert hint["message"] == "Query will scan 75 partition(s)"
        assert hint["all_partitions"] is False
        assert hint["table"] == "detections" and hint["column"] == "detected_at"
    finally:
        restore()


def test_pruning_hint_range_and_boundaries() -> None:
    """Nov->Dec walk (m18-style Dec crossing), the EXACT ``<=`` boundary, day-1->2."""
    mgr = PartitionManager.__new__(PartitionManager)
    hint = mgr.get_partition_pruning_hint(
        "detections", "detected_at", _d(2026, 11, 20), _d(2026, 12, 2)
    )
    assert hint == {
        "table": "detections",
        "column": "detected_at",
        "all_partitions": False,
        "partitions": ["detections_y2026m11", "detections_y2026m12"],
        "partition_count": 2,
        "message": "Query will scan 2 partition(s)",
    }
    exact = mgr.get_partition_pruning_hint(
        "detections", "detected_at", _d(2026, 12, 15), _d(2027, 1, 1)
    )
    # ``<=`` keeps the month whose 1st IS the end_date (m24's ``<`` drops m01).
    assert (
        exact["partitions"] == ["detections_y2026m12", "detections_y2027m01"]
        and exact["partition_count"] == 2
    )
    noon = mgr.get_partition_pruning_hint(
        "detections", "detected_at", _d(2026, 12, 15), _d(2027, 1, 1, 12)
    )
    assert noon["partitions"] == ["detections_y2026m12", "detections_y2027m01"]
    day2 = mgr.get_partition_pruning_hint(
        "detections", "detected_at", _d(2026, 1, 15), _d(2026, 2, 1, 12)
    )
    assert day2["partitions"] == ["detections_y2026m01", "detections_y2026m02"]


# ---------------------------------------------------------------------------
# recommend_partition_interval / recommend_retention_period
# ---------------------------------------------------------------------------


def test_recommend_partition_interval() -> None:
    mgr = PartitionManager.__new__(PartitionManager)
    assert mgr.recommend_partition_interval(1_000_001, "recent") == "weekly"
    assert mgr.recommend_partition_interval(1_000_000, "recent") == "monthly"
    assert mgr.recommend_partition_interval(1_000_000, "historical") == "monthly"
    assert mgr.recommend_partition_interval(1_000_001, "historical") == "monthly"
    assert mgr.recommend_partition_interval(1_000_001, "RECENT") == "monthly"
    assert mgr.recommend_partition_interval(1_000_001, "XXrecentXX") == "monthly"
    assert mgr.recommend_partition_interval(500_000, "recent") == "monthly"
    assert (
        mgr.recommend_partition_interval(2_000_000) == "weekly"
    )  # default query_pattern IS "recent"
    assert mgr.recommend_partition_interval(10_000_000, "random") == "monthly"


def test_recommend_retention_period() -> None:
    mgr = PartitionManager.__new__(PartitionManager)
    for name in ("audit_logs", "Events", "AUDIT_LOGS", "alerts", "Alerts", "events"):
        assert mgr.recommend_retention_period(name, True) == 24
    assert mgr.recommend_retention_period("detections", True) == 12
    assert mgr.recommend_retention_period("Metrics", True) == 12
    assert mgr.recommend_retention_period("detections", False) == 6
    assert mgr.recommend_retention_period("Events", False) == 6
    assert mgr.recommend_retention_period("gpu_stats", False) == 3
    assert mgr.recommend_retention_period("Metrics", False) == 3
    assert mgr.recommend_retention_period("LOGS", False) == 3
    assert mgr.recommend_retention_period("metrics") == 3


# ---------------------------------------------------------------------------
# check_partition_balance / identify_partition_gaps
# ---------------------------------------------------------------------------


def _bal(counts: Any) -> list[PartitionInfo]:
    out = []
    for i, c in enumerate(counts):
        start = dt.datetime(2026, i + 1, 1, tzinfo=dt.UTC)
        out.append(_info(f"p{i}", start, _add_month(start), c))
    return out


def test_check_partition_balance() -> None:
    mgr = PartitionManager.__new__(PartitionManager)
    assert mgr.check_partition_balance([]) == {
        "balanced": True,
        "variance": 0.0,
        "message": "No partitions to analyze",
    }
    assert mgr.check_partition_balance(_bal([0, 0])) == {
        "balanced": True,
        "variance": 0.0,
        "message": "No row count data available",
    }
    assert mgr.check_partition_balance(_bal([1])) == {
        "balanced": True,
        "variance": 1.0,
        "average_rows": 1,
        "max_rows": 1,
        "min_rows": 1,
        "largest_partition": "p0",
        "message": "Partitions are balanced",
    }
    assert mgr.check_partition_balance(_bal([1, 1, 1, 9])) == {
        "balanced": True,
        "variance": 3.0,
        "average_rows": 3,
        "max_rows": 9,
        "min_rows": 1,
        "largest_partition": "p3",
        "message": "Partitions are balanced",
    }
    assert mgr.check_partition_balance(_bal([1, 1, 1, 10])) == {
        "balanced": False,
        "variance": 10 / 3.25,
        "average_rows": 3,
        "max_rows": 10,
        "min_rows": 1,
        "largest_partition": "p3",
        "message": "Partition imbalance detected",
    }


def test_identify_partition_gaps() -> None:
    mgr = PartitionManager.__new__(PartitionManager)
    m = _cfg()
    assert mgr.identify_partition_gaps(m, []) == []
    existing = [
        _info("detections_y2026m11", _d(2026, 11, 1), _d(2026, 12, 1)),
        _info("partial", _d(2026, 11, 20), _d(2026, 12, 2)),
    ]
    assert mgr.identify_partition_gaps(m, existing) == ["detections_y2026m12"]
    at_start = [
        _info("detections_y2026m11", _d(2026, 11, 1), _d(2026, 12, 1)),
        _info("partial", _d(2026, 11, 20), _d(2026, 12, 1)),
    ]
    assert mgr.identify_partition_gaps(m, at_start) == []
    janfeb = [
        _info("detections_y2026m01", _d(2026, 1, 1), _d(2026, 2, 1)),
        _info("partial", _d(2026, 1, 15), _d(2026, 2, 1, 12)),
    ]
    assert mgr.identify_partition_gaps(m, janfeb) == ["detections_y2026m02"]


# ---------------------------------------------------------------------------
# get_partition_metadata / estimate_partition_size
# ---------------------------------------------------------------------------


def test_estimate_partition_size() -> None:
    mgr = PartitionManager.__new__(PartitionManager)
    assert mgr.estimate_partition_size(1000) == 600000 / 1048576
    assert mgr.estimate_partition_size(1000, 250) == 300000 / 1048576
    assert mgr.estimate_partition_size(0) == 0.0
    assert mgr.estimate_partition_size(1, 500) == 600 / 1048576


def test_get_partition_metadata() -> None:
    mgr = PartitionManager.__new__(PartitionManager)
    p = _info("p1", _d(2026, 1, 1), _d(2026, 2, 1), 100)
    assert mgr.get_partition_metadata(p) == {
        "name": "p1",
        "table_name": "detections",
        "start_date": "2026-01-01T00:00:00+00:00",
        "end_date": "2026-02-01T00:00:00+00:00",
        "row_count": 100,
        "days_covered": 31,
        "size_estimate_mb": 60000 / 1048576,
    }
