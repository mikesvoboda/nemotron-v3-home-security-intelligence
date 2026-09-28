"""S3 batch-28 lane gm12 - ``gpu_monitor`` groups G09 + G22 + G17 battery (13 keys).

Module: ``backend/services/gpu_monitor.py`` (md5 2f122c85a072b7bd00c2e4b36cdc1cda,
byte-identical to HEAD).  Admitted manifest groups:

* group 17 ``G09 _parse_vram_metric_line negative index``  -> ``group_17.keys`` (1)
* group 18 ``G22 get_stats_history inclusive cutoff``      -> ``group_18.keys`` (1)
* group 19 ``G17 _calculate_inference_fps``                -> ``group_19.keys`` (11)

Every one of the 13 keys is KILLABLE, is claimed by no other group, and splices
cleanly (``splice-group_19.json`` reports the one occurrence-twin key in the
set - ``_calculate_inference_fps__mutmut_5`` - with 4 candidates, ALL of which
this battery reddens; see the twin note below).

Key -> test map
===============
``_parse_vram_metric_line__mutmut_7`` (L769 ``float(parts[-1])`` -> ``float(parts[+1])``)
  -> ``test_three_token_bytes_line_reads_the_trailing_value_token`` (SOLE route).
     Shipped: 9.0 / (1024*1024) = 8.58306884765625e-06; mutant reads the VALUE
     token -> 1048576.0 / (1024*1024) = 1.0.

``get_stats_history__mutmut_11`` (L973 ``>= cutoff_time`` -> ``> cutoff_time``)
  -> ``test_sixty_minute_cutoff_is_inclusive_at_the_boundary`` (SOLE route).

``_calculate_inference_fps`` (``group_19.keys``, 11 keys):
* ``__mutmut_2`` L994 ``- timedelta`` -> ``+``, ``__mutmut_3`` ``now(UTC)`` ->
  ``now(None)``, ``__mutmut_5`` ``60`` -> ``61`` (TWIN, 4 candidates),
  ``__mutmut_11`` L996 ``>=`` -> ``>``
  -> ``test_count_query_shape_and_cutoff_are_the_shipped_sixty_second_window``
     (compiled SQL text + bound parameter identity).
* ``__mutmut_7`` L995 ``session.execute(None)``
  -> same test (the captured statement must compile to the shipped SELECT).
* ``__mutmut_8`` ``.where(None)``, ``__mutmut_9`` ``select(None)``,
  ``__mutmut_10`` ``func.count(None)``
  -> same test (columns clause / predicate presence).
* ``__mutmut_16`` ternary forced-then, ``__mutmut_21`` else ``0.0`` -> ``1.0``
  -> ``test_negative_and_missing_counts_collapse_to_exactly_zero_fps``.
* ``__mutmut_22`` L1001 ``logger.warning(None)``
  -> ``test_database_failure_warns_with_the_exception_text_and_returns_none``.

Occurrence-twin note (``__mutmut_5``, ``number:60 -> 61``)
---------------------------------------------------------
The bank cites L994 but the ``60`` token appears four times inside this def, and
mutmut numbers its metas in source order - the harness proves ALL FOUR:
occ0 = L979 docstring "the last 60 seconds" -> killed by the ``__doc__`` assert,
occ1 = L993 comment "# Count detections in last 60 seconds" -> killed by the
module-source assert, occ2 = L994 ``timedelta(seconds=60)`` -> killed by the bound
cutoff parameter assert, occ3 = L999 ``count / 60.0`` -> killed by the FPS return
assert.  No leg is decorative.

Discipline
----------
* Shipped behaviour only; the ``session`` double is an ``AsyncMock`` standing for
  the SQLAlchemy async session, and the frozen clock is the seam the admitted
  manifest test_spec names for G17/G22.
* Log assertions read the RAW ``record.msg`` inside a ``set_level`` + ``clear()``
  window filtered to this module's logger.
* ``time.monotonic``/``time.perf_counter`` are never patched; the only clock seam
  is ``freeze_time`` on the two manifest-named windows.
* No import-time global spies; no ``scope="session"`` fixtures.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from freezegun import freeze_time

import backend.services.gpu_monitor as M

LOG_NAME = M.logger.name  # "backend.services.gpu_monitor" (get_logger(__name__))

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shipped literals, transcribed from backend/services/gpu_monitor.py
# =============================================================================

# L979 (docstring): "Counts detections processed in the last 60 seconds and calculates"
DOC_WINDOW_PHRASE = "last 60 seconds"

# L993 (comment): "# Count detections in last 60 seconds"
COMMENT_WINDOW_LINE = "# Count detections in last 60 seconds"


def _shipped_source() -> str:
    """Text of the shipped module THIS world was built from.

    Pristine world: ``Path(M.__file__)`` verbatim.  Instrumented (mutmut-bank)
    world: ``M.__file__`` is the GENERATED file carrying every mutant copy as
    an extra def - the shipped comment appears once per copy (24x), so a raw
    ``count == 1`` read can never be green there and would attribute a false
    kill to every key whose selection set reaches this module.  The
    instrumented file is generated verbatim from the shipped file, which sits
    at the same path minus the ``mutants/`` component (the proven ``_PRISTINE``
    recipe from the detector_client batch-28 batteries).
    """
    p = Path(M.__file__)
    parts = p.parts
    if "mutants" in parts:
        i = len(parts) - 1 - parts[::-1].index("mutants")
        p = Path(*parts[:i], *parts[i + 1 :])
    return p.read_text(encoding="utf-8")


# L994-L996 shipped statement, compiled by the DEFAULT dialect (lower-case
# keywords - audit correction #3).  Captured from a pristine compile:
#   'SELECT count(detections.id) AS count_1 \nFROM detections \n'
#   'WHERE detections.detected_at >= :detected_at_1'
SQL_COUNT_CLAUSE = "count(detections.id)"
SQL_FROM = "from detections"
SQL_PREDICATE = "detections.detected_at >= :detected_at_1"
SQL_INCLUSIVE_TOKEN = " >= "

# L1001: logger.warning(f"Failed to calculate inference FPS: {e}")
FPS_WARNING = "Failed to calculate inference FPS: db"

# Frozen reference instant for the two windows that need a deterministic clock.
FROZEN_UTC = datetime(2026, 5, 4, 5, 6, 7, tzinfo=UTC)
FROZEN_ISO = "2026-05-04 05:06:07+00:00"


# =============================================================================
# Observation helpers (batch27_01 pattern)
# =============================================================================


def win(caplog: pytest.LogCaptureFixture) -> None:
    """Open a capture window: DEBUG for this module's logger, empty buffer."""
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()


def mine(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOG_NAME]


def at(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [r for r in mine(caplog) if r.levelno == level]


def pin_record(r: logging.LogRecord, *, msg: str, level: int) -> None:
    """Assert the observable surface of one shipped f-string log call."""
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.getMessage() == msg, f"formatted text mutated: {r.getMessage()!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args: {r.args!r}"
    assert r.exc_info is None, f"exc_info present where shipped passes none: {r.exc_info!r}"


def only(caplog: pytest.LogCaptureFixture, level: int, msg: str) -> logging.LogRecord:
    """Exactly one record at ``level`` in the window, matching every field."""
    recs = at(caplog, level)
    assert len(recs) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record from {LOG_NAME}, "
        f"got {[(r.levelno, r.msg) for r in recs]}"
    )
    pin_record(recs[0], msg=msg, level=level)
    return recs[0]


# =============================================================================
# Monitor harness
# =============================================================================


@pytest.fixture
def monitor() -> M.GPUMonitor:
    """A mock-mode GPUMonitor (pynvml import fails, nvidia-smi absent)."""
    with (
        patch.dict("sys.modules", {"pynvml": None}),
        patch("backend.services.gpu_monitor.shutil.which", return_value=None, autospec=True),
    ):
        yield M.GPUMonitor()


def session_returning(scalar_value):
    """An AsyncMock session whose ``execute`` answers with ``scalar()`` -> value."""
    result = MagicMock()
    result.scalar.return_value = scalar_value
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    return session


# =============================================================================
# G09 - L760-L780 _parse_vram_metric_line (group_17, 1 key)
# =============================================================================


def test_three_token_bytes_line_reads_the_trailing_value_token(monitor, caplog):
    """L768-L769 ``value = float(parts[-1])`` (negative index).

    A Prometheus line with THREE whitespace tokens - name, value, timestamp -
    separates ``parts[-1]`` from ``parts[1]``.  Shipped picks the trailing
    timestamp token 9.0 and the "bytes" unit leg converts it; the
    ``drop_unary:Minus`` mutant picks the value token 1048576.0.

    9.0 / (1024 * 1024) == 8.58306884765625e-06 (shipped)
    1048576.0 / (1024 * 1024) == 1.0 (mutant)
    """
    win(caplog)
    line = 'yolo_vram_bytes_total{gpu="0"} 1048576 9'
    assert monitor._parse_vram_metric_line(line) == 8.58306884765625e-06
    assert mine(caplog) == []


def test_two_token_bytes_line_is_the_same_negative_index_leg(monitor, caplog):
    """Two-token form of the same conversion (``parts[-1]`` == ``parts[1]`` here,
    so this leg pins the unit arithmetic rather than the index - the shipped
    ``1048576`` bytes -> 1.0 MB result the three-token leg differs from)."""
    win(caplog)
    assert monitor._parse_vram_metric_line("vram_bytes_used 1048576") == 1.0
    assert mine(caplog) == []


def test_unitless_metric_is_assumed_megabytes(monitor, caplog):
    """Audit correction #4 anchor: with no "bytes"/"gb" unit in the line the
    shipped code assumes MB and returns the RAW value (1048576.0), not 1.0.  This
    is a control leg - both shipped and the mutant agree here - and it is what
    stops the three-token expectation above from being a "1.0" expectation."""
    win(caplog)
    assert monitor._parse_vram_metric_line("x{a} 1048576") == 1048576.0
    assert mine(caplog) == []


def test_gigabyte_unit_multiplies_by_a_thousand_and_twenty_four(monitor, caplog):
    """L777-L778 ``if "gb" in line_lower: return value * 1024``."""
    win(caplog)
    assert monitor._parse_vram_metric_line("vram_used_gb 2") == 2048.0
    assert mine(caplog) == []


def test_short_line_and_unparseable_value_both_return_zero(monitor, caplog):
    """L766-L767 ``len(parts) < 2 -> 0.0`` and L770-L771 ``ValueError -> 0.0``."""
    win(caplog)
    assert monitor._parse_vram_metric_line("lonely") == 0.0
    assert monitor._parse_vram_metric_line("") == 0.0
    assert monitor._parse_vram_metric_line("metric_name not_a_number") == 0.0
    assert mine(caplog) == []


# =============================================================================
# G22 - L958-L974 get_stats_history (group_18, 1 key)
# =============================================================================


def test_sixty_minute_cutoff_is_inclusive_at_the_boundary(monitor, caplog):
    """L972-L974 ``stats["recorded_at"] >= cutoff_time`` (>=, not >).

    Frozen at T0 with three seeded entries: e1 EXACTLY at T0-60min (the boundary),
    e1b one second newer, e2 one minute older.  Shipped keeps the boundary entry,
    so the window holds TWO; the ``>`` twin drops it and returns ONE.
    """
    win(caplog)
    e_boundary = {"gpu_name": "boundary", "recorded_at": FROZEN_UTC - timedelta(minutes=60)}
    e_inside = {
        "gpu_name": "inside",
        "recorded_at": FROZEN_UTC - timedelta(minutes=60) + timedelta(seconds=1),
    }
    e_outside = {"gpu_name": "outside", "recorded_at": FROZEN_UTC - timedelta(minutes=61)}
    monitor._stats_history.extend([e_boundary, e_inside, e_outside])

    with freeze_time(FROZEN_ISO):
        result = monitor.get_stats_history(60)

    assert len(result) == 2, f"boundary entry dropped by an exclusive cutoff: {result}"
    # newest first (L974 reversed)
    assert result[0] is e_inside
    assert result[1] is e_boundary
    assert mine(caplog) == []


def test_no_minutes_returns_the_whole_history_newest_first(monitor, caplog):
    """L967-L969 ``minutes is None`` -> the full deque reversed, no filtering."""
    win(caplog)
    first = {"gpu_name": "first", "recorded_at": FROZEN_UTC - timedelta(hours=5)}
    second = {"gpu_name": "second", "recorded_at": FROZEN_UTC - timedelta(hours=4)}
    monitor._stats_history.extend([first, second])

    result = monitor.get_stats_history()

    assert [e["gpu_name"] for e in result] == ["second", "first"]
    assert result[0] is second
    assert result[1] is first
    assert mine(caplog) == []


def test_empty_history_returns_an_empty_list_for_both_shapes(monitor, caplog):
    """Control leg: an untouched history is ``[]`` whether or not minutes is given."""
    win(caplog)
    assert monitor.get_stats_history() == []
    assert monitor.get_stats_history(60) == []
    assert mine(caplog) == []


# =============================================================================
# G17 - L976-L1002 _calculate_inference_fps (group_19, 11 keys)
# =============================================================================


@pytest.mark.asyncio
@freeze_time(FROZEN_ISO)
async def test_count_query_shape_and_cutoff_are_the_shipped_sixty_second_window(monitor, caplog):
    """L993-L999: the shipped SELECT, its bound cutoff, and the FPS arithmetic.

    * ``captured.compile()`` text: the shipped columns clause
      ``count(detections.id)``, ``from detections``, the inclusive predicate
      ``detections.detected_at >= :detected_at_1`` - killing ``select(None)``
      (renders ``NULL AS anon_1``), ``func.count(None)`` (renders ``count(*)``),
      ``.where(None)`` (renders ``WHERE NULL``, no predicate), ``>=`` -> ``>``
      and ``session.execute(None)`` (a None arg cannot compile at all).
    * the bound parameter equals the frozen instant MINUS exactly 60 seconds and
      is tz-aware - killing ``Subtract`` -> ``Add``, ``now(UTC)`` -> ``now(None)``
      and the L994 ``60`` -> ``61`` twin.
    * the return value is ``12 / 60.0`` exactly - killing the L999 ``60`` twin.
    * the docstring and the L993 comment both still say "60 seconds" - killing
      the docstring and comment ``60`` twins (see the module docstring map).
    """
    win(caplog)
    session = session_returning(12)

    fps = await monitor._calculate_inference_fps(session)

    assert fps == 0.2, f"FPS arithmetic mutated: {fps!r} != 0.2"
    assert session.execute.await_count == 1
    statement = session.execute.await_args.args[0]
    compiled = statement.compile()
    text = str(compiled).lower()
    assert SQL_COUNT_CLAUSE in text, f"columns clause mutated: {text!r}"
    assert SQL_FROM in text, f"FROM clause mutated: {text!r}"
    assert SQL_PREDICATE in text, f"predicate mutated: {text!r}"
    assert SQL_INCLUSIVE_TOKEN in text, f"cutoff comparison is no longer inclusive: {text!r}"
    assert compiled.params == {"detected_at_1": FROZEN_UTC - timedelta(seconds=60)}, (
        f"cutoff parameter mutated: {compiled.params!r}"
    )
    param = compiled.params["detected_at_1"]
    assert param.tzinfo is not None, f"cutoff lost its tzinfo: {param!r}"
    assert mine(caplog) == []


@pytest.mark.asyncio
async def test_sixty_second_window_is_stated_in_docstring_and_comment(monitor):
    """The two remaining ``number:60 -> 61`` occurrence twins (L979 docstring,
    L993 comment).

    ``__doc__`` is compiled from the source that was actually imported, and the
    comment is read from ``M.__file__`` (NOT via ``inspect.getsource``/linecache,
    which can hand back a stale same-size copy).  Both therefore observe the text
    of the module THIS world loaded.
    """
    doc = M.GPUMonitor._calculate_inference_fps.__doc__ or ""
    assert "Counts detections processed in the last 60 seconds and calculates" in doc, (
        f"docstring window mutated: {doc.splitlines()[1:4]!r}"
    )

    module_source = _shipped_source()
    assert module_source.count(COMMENT_WINDOW_LINE) == 1, (
        "the shipped L993 window comment is not present exactly once in the "
        "shipped source of the imported module"
    )


@pytest.mark.asyncio
@freeze_time(FROZEN_ISO)
async def test_negative_and_missing_counts_collapse_to_exactly_zero_fps(monitor, caplog):
    """L998-L999 ``count = result.scalar() or 0`` / ``count / 60.0 if count >= 0 else 0.0``.

    scalar -> ``-5``: shipped takes the ELSE branch and returns EXACTLY 0.0.  The
    forced-condition twin returns ``-5 / 60.0`` and the ``else 0.0 -> 1.0`` twin
    returns 1.0 - both die on the exact equality.  ``scalar() -> None`` is
    normalised by ``or 0`` to the same 0.0.
    """
    win(caplog)
    assert await monitor._calculate_inference_fps(session_returning(-5)) == 0.0
    assert await monitor._calculate_inference_fps(session_returning(None)) == 0.0
    assert await monitor._calculate_inference_fps(session_returning(0)) == 0.0
    assert await monitor._calculate_inference_fps(session_returning(60)) == 1.0
    assert mine(caplog) == []


@pytest.mark.asyncio
@freeze_time(FROZEN_ISO)
async def test_database_failure_warns_with_the_exception_text_and_returns_none(monitor, caplog):
    """L1000-L1002 ``except Exception as e: logger.warning(f"Failed to calculate inference FPS: {e}"); return None``.

    ``logger.warning(None)`` (mutmut_22) loses the text; the count + exact text +
    the ``None`` return are the kill.
    """
    win(caplog)
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=RuntimeError("db"))

    fps = await monitor._calculate_inference_fps(session)

    assert fps is None
    only(caplog, logging.WARNING, "Failed to calculate inference FPS: db")
    assert session.execute.await_count == 1


@pytest.mark.asyncio
@freeze_time(FROZEN_ISO)
async def test_statement_is_executed_exactly_once_and_its_scalar_is_read_once(monitor, caplog):
    """Control leg: the shipped single round-trip.  Pins the execute count and the
    ``scalar()`` read so a killing leg above can only be about the statement or
    the arithmetic, never about a re-executed query."""
    win(caplog)
    result = MagicMock()
    result.scalar.return_value = 30
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    fps = await monitor._calculate_inference_fps(session)

    assert fps == 0.5
    assert session.execute.await_count == 1
    assert result.scalar.call_count == 1
    assert mine(caplog) == []
