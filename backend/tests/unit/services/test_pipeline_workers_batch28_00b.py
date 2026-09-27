r"""S3 batch-28 lane 00 - ``pipeline_workers`` group g01 kill battery (72 keys).

Module: ``backend/services/pipeline_workers.py`` (git blob 74649fd3 - the manifest-proven
source, since rebased onto a main that carries the VLM Phase 1 commit, which added one
import above this group's window and two comment lines inside the ``AnalysisQueueWorker``
constructor.  Every line number below is the CURRENT shipped one: the manifest keys were
admitted against the pre-rebase numbering, so a citation here reads +1 below the new
import and +3 below the constructor hunk - the MUTANTS are unchanged, only their
coordinates moved).  Admitted manifest: ``/tmp/wp-pw/pipeline_workers/`` ``manifest.json``
group 1 (72 KILLABLE / 0 EQUIVALENT / 0 NEEDS_INVESTIGATION), plus ``group_1.keys`` and
``survivors.json`` for the exact per-key diffs.

Target: the SUCCESS arm of ``AnalysisQueueWorker._process_analysis_item`` - shipped
L1049-L1129: the ``analyze_batch`` await, the ``WorkerStats`` stamps, the two latency
telemetry calls, the ``pipeline_start_time`` total-pipeline block (parse + DEBUG +
parse-failure WARNING), the success INFO and the ``batch.analysis_completed`` publish.
The validation arm, the span/log context and ``batch.analysis_started`` are group g00
(``test_pipeline_workers_batch28_00.py``); the two files deliberately share one
observation contract (``win`` / ``mine`` / ``at`` / ``only`` / ``levels`` / ``extras`` /
``surface`` / ``surface_extras`` / ``pin_record`` / ``pin_extra`` / ``patch_global`` /
``instrumentation`` / ``patch_time``) so a leg's failure output always shows the whole
shipped surface the mutant moved.

Clock seam (the manifest spec's ``Freeze time`` instruction, made non-vacuous)
==============================================================================
Wall time reaches the shipped def through exactly two doors, and each gets its own
function-local seam - ``time.monotonic`` and ``time.perf_counter`` are NEVER patched
anywhere in this file or in file 00:

* ``time.time()`` - the def does ``import time`` at L987, so the binding comes from
  ``sys.modules``; ``patch.dict(sys.modules, {"time": FakeClock(ticks)})`` scripts the
  stamps for one window (``FakeClock.__getattr__`` keeps every other ``time`` attribute
  real, and an exhausted tick list falls back to the real clock so foreign code never
  sees frozen time).
* ``datetime.now`` - ``datetime`` is an ordinary module GLOBAL here (L36), so
  ``patch_global("datetime", ...)`` stands it in inside the LIVE name-resolution dict of
  the function under test.  That seam is needed only to read TWO timestamps with ONE
  script: the shipped def calls ``datetime.now(UTC)`` twice per item (L1079 and L1121)
  plus ``datetime.fromisoformat`` in between, and no real clock can be frozen across two
  module-global reads.  ``fromisoformat`` and ``utcfromtimestamp`` stay REAL on the
  stand-in, so the parse under test is the shipped parse and a name-mutation of
  ``utcfromtimestamp`` still explodes inside the shipped body.

Test -> mutant-key map (all 72; every pin below reads SHIPPED observables only)
===============================================================================
* L1058 ``self._stats.items_processed += 1`` -> ``= 1`` (``m80``):
  ``test_two_successful_items_increment_the_processed_stat_once_each`` - after ONE item
  ``1`` is what shipped and ``m80`` both report, so the leg asserts after the FIRST item
  (that intermediate assert is what kills ``m80``) and again after the second (``2``).
* L1059 ``self._stats.last_processed_at = time.time()`` -> ``= None`` (``m83``): same
  leg, through ``stats.to_dict()["last_processed_at"]`` (the shipped serialization the
  API serves) - a float, and exactly the stamp the scripted clock hands out.
* L1062 ``duration = time.time() - start_time`` -> ``+`` (``m85``) and L1063
  ``duration_ms = int(duration * 1000)`` -> ``None`` / ``/ 1000`` / ``* 1001``
  (``m86``/``m88``/``m89``): ``test_one_and_a_half_seconds_is_exactly_1500_ms`` - the
  scripted ticks 1000.0 -> 1001.5 ship ``1500``; the four variants produce
  ``1_502_250`` / ``None`` / ``1`` / ``1501``, no two of which are equal, so ONE exact
  pin kills all five.
* L1065 ``record_pipeline_stage_latency("batch_to_analyze", duration_ms)`` label
  ``None``/``"XXbatch_to_analyzeXX"``/``"BATCH_TO_ANALYZE"`` and value ``None``
  (``m90``/``m91``/``m94``/``m95``): complete ``call_args_list`` equality in the same
  leg, so a single mutated positional argument reddens it.
* L1067 ``await record_stage_latency(self._redis, "analyze", duration_ms)`` stage
  ``None``/``"XXanalyzeXX"``/``"ANALYZE"`` and value ``None``
  (``m97``/``m98``/``m102``/``m103``): the same leg pins the complete awaited call,
  POSITIONALS FIRST, and separately that the awaited call's first positional IS the
  injected redis double (``redis_client_for(worker)``) - so a ``self._redis``-swapping
  mutant cannot slip past either.
* L1074 ``pipeline_start_time.replace("Z", "+00:00")``: ``m110`` replaces ``"XXZXX"``,
  ``m111`` ``"z"``, ``m112`` the offset with ``"XX+00:00XX"``.  One stimulus cannot
  separate the four behaviours, so three legs carry three payloads:
  - ``test_a_zulu_pipeline_start_time_records_the_total_pipeline_latency``
    (``"2026-01-01T00:00:00Z"``, scripted now ``2026-01-01T12:00:00+00:00`` -> shipped
    records ``total_pipeline == 43_200_000.0`` + the DEBUG line): kills ``m112``, whose
    parse raises and takes the record and the DEBUG with it.
  - ``test_a_lowercase_zulu_pipeline_start_time_still_parses`` (the SAME timestamp with
    a lowercase ``z``): shipped still refuses it (``replace("Z", ...)`` never fires) and
    warns; under ``m111`` the parse SUCCEEDS, so the record appears and the WARNING
    disappears - both halves fail, which is the whole kill.
  - ``test_an_xx_wrapped_pipeline_start_time_warns_without_recording_total_pipeline``
    (``"2026-01-01T00:00:00XXZXX"``) - THE m110 leg the manifest exception prescribes,
    single-payload and NOT folded into the valid-Z leg: (A1) no ``total_pipeline``
    record at all, (A2) exactly one WARNING whose text is the shipped f-string, ending
    ``Invalid isoformat string: '2026-01-01T00:00:00XX+00:00XX'``, carrying
    ``extra.pipeline_start_time`` == the raw value, (A3) the success INFO still fires.
    Under ``m110`` the string becomes valid ISO, so A1 records ``43_200_000.0`` and A2
    loses the WARNING.
  - ``test_a_plain_iso_pipeline_start_time_gets_the_utc_tzinfo_branch``
    (``"2026-01-01T00:00:00"``, no zone) is the second half of the m112 kill: shipped
    takes the L1077 tzinfo branch and records ``43_200_000.0``, while under ``m112`` the
    parse yields a NAIVE ``start_dt`` that the tzinfo branch fixes, so the same number
    appears where shipped raised - the pair (warning here, record there) is what makes
    m112 reddening unavoidable.
* L1079 ``... .total_seconds() * 1000`` -> ``/ 1000`` / ``* 1001``
  (``m117``/``m120``): the exact ``43_200_000.0`` pin in the two recording legs (the
  variants give ``43_200.0`` / ``43_243_200_000.0``).
* L1081-L1087 the total-pipeline DEBUG: message ``None``/DROPPED (``m127``/``m129`` -
  ``logger.debug(extra=...)`` with no message is a ``TypeError``, so the whole record
  vanishes and the item falls into the ``except Exception`` arm), ``extra=None``/DROPPED
  (``m128``/``m130``) and the four key renames (``m131``-``m134``): the DEBUG text +
  ``levels`` + ``surface_extras`` in the valid-Z leg, which pins the whole window surface
  (INFO 2 / DEBUG 1, one ``total_pipeline_ms`` + ``pipeline_start_time`` field).
* L1089-L1092 the parse-failure WARNING: message ``None`` (``m135``), ``extra=None`` /
  DROPPED (``m136``/``m138``) and the two renames (``m139``/``m140``): the two warning
  legs, again via text + ``levels`` + ``surface_extras``.
* L1094-L1101 the success INFO: message ``None``/DROPPED (``m141``/``m143``),
  ``extra=None``/DROPPED (``m142``/``m144``) and the six key renames
  (``m145``-``m150``): ``test_the_success_info_carries_the_event_id_risk_score_and_stat``,
  whose ``items_processed`` extra is ``1`` for the first item and ``2`` for the second -
  the stamp is read LIVE off ``self._stats``, so a second item also re-kills ``m80``.
* L1107-L1112 the ``risk_level`` normalisation, pinned by ONE complete completed-payload
  equality per shape (``m151``-``m162``): the enum-like member (``.value == "high"``)
  takes L1110, the plain string takes L1112's ``str(...)`` - where ``m161`` puts ``None``
  and ``m162`` the text ``"None"`` - and ``risk_level=None`` keeps the L1107 ``"low"``
  default, which is the sole route to ``m151``/``m152``/``m153`` and to ``m154`` (the
  flipped ``is None`` guard, which under a real level skips to the default, and under
  ``None`` calls ``hasattr(None, ...)``).  ``hasattr`` itself is enforced by autospec:
  ``m157`` (drop the object) and ``m158`` (drop the name) are ``TypeError`` inside the
  shipped body, and ``m155``/``m156``/``m159``/``m160`` all route a real level's string
  through the ``str(...)`` branch, where the shipped ``RiskLevel.HIGH`` repr differs from
  its ``.value``.
* L1113-L1123 the ``batch.analysis_completed`` payload: complete 7-key dict equality in
  the enum leg, plus the payload in the string/``None``-level legs and the cameraless
  leg (``camera_id`` -> ``""`` vs CAM is the two arms that separate ``m168``'s
  ``camera_id and ""`` and ``m169``'s ``or "XXXX"`` from shipped), ``m163`` (payload ->
  ``None``) via the ``isinstance(payload, dict)`` pin, and ``m180``
  (``datetime.now(None)``) via the UTC-offset FORM of ``completed_at`` in
  ``test_the_completed_timestamp_is_the_shipped_utc_isoformat``.
* L1124-L1129 the completed-publish ``except`` arm carries NO survivor at all (the
  admitted 959-key list has no diff anywhere on L1124-L1129, nor on the started-publish
  arm at L1042-L1047 - the pre-existing suite already killed those), so NOTHING is
  claimed there.  ``test_a_started_publish_failure_does_not_stop_the_completed_publish``
  is a defensive regression leg for the payload pins above: it shows a raising publish
  leaves the completion publish, the stats and the INFO intact, so a future mutant that
  made a publish RAISE could not masquerade as a merely-missing payload.

Cross-group twin check
======================
Every g01 diff ``(function, before, after, line)`` was searched across all 959
survivors.  The L1058/L1059 pair has NO occurrence anywhere else in the module (the
twin-shaped stamps at L522-L523 and L1320-L1321 differ textually - ``+= 1``/``= None``
vs ``+= len(...)``), so these keys belong to this group.  ``m117``/``m120`` occur on NO
other statement in the module - the L1079 ``total_duration_ms`` line is the only survivor
site carrying a ``total_seconds()`` scaling mutation - so they are claimed here alone, and
the twin-shaped ``except Exception`` arm at L1153-L1160 belongs to g02.

Shipped-behaviour facts the legs rely on
========================================
* ``pipeline_start_time`` is an UNVALIDATED ``str | None`` on ``AnalysisQueuePayload``
  (``backend/api/schemas/queue.py:132-171`` - the shipped gate checks only
  ``batch_id``/``camera_id``/``detection_ids``), so any of the timestamp strings above
  can really arrive, and the shipped def's own ``except (ValueError, TypeError)`` is the
  only thing that handles a bad one.
* ``WorkerStats`` (L202-L219) is the shipped stats object; ``to_dict()`` is what the
  status API serves, so ``last_processed_at`` is pinned through it.
* ``record_stage_latency`` (``backend/api/routes/system.py:2938-2960``) is an ``async``
  three-positional function whose first parameter is the redis client - hence autospec
  and the awaited-call pin.
* ``datetime.fromisoformat`` (stdlib, used unpatched here) accepts a trailing ``Z`` but
  NOT a lowercase ``z``, which is exactly why shipped's ``.replace("Z", "+00:00")``
  exists and why the lowercase-``z`` payload is a real parse failure, not a typo.
* ``time.monotonic``/``time.perf_counter`` are never patched here, and no leg depends on
  the host timezone.
"""

from __future__ import annotations

import contextlib
import inspect
import logging
import sys
import time as real_time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from functools import cache
from typing import Any
from unittest.mock import MagicMock, call, create_autospec, patch

import pytest

from backend.services import pipeline_workers as M
from backend.services.event_broadcaster import EventBroadcaster
from backend.services.nemotron_analyzer import NemotronAnalyzer

LOG_NAME = M.logger.name  # "backend.services.pipeline_workers" (get_logger(__name__))

pytestmark = [pytest.mark.unit]


# =============================================================================
# World-aware re-anchor for the ``where=`` lineno pins (2026-09-27)
# =============================================================================
# See the same block in test_pipeline_workers_batch28_00.py: in mutmut's mutant
# home the module is the INSTRUMENTED trampoline file (every mutated function
# duplicated, so the shipped call legitimately fires at shifted lines).  The
# honest, mutation-detecting fact is that the record fired at a line holding
# THIS EXACT shipped call block — a moved/reworded call breaks the match and
# still reddens; text/extra mutations are caught by the untouched pins.
_LOG_CALL_BLOCKS: dict[int, tuple[str, ...]] = {
    1044: (
        "logger.debug(",
        'f"Failed to broadcast batch.analysis_started: {broadcast_err}",',
        'extra={"batch_id": batch_id},',
        ")",
    ),
    1081: (
        "logger.debug(",
        'f"Total pipeline latency: {total_duration_ms:.1f}ms",',
        "extra={",
        '"total_pipeline_ms": total_duration_ms,',
        '"pipeline_start_time": pipeline_start_time,',
        "},",
        ")",
    ),
    1089: (
        "logger.warning(",
        "f\"Failed to parse pipeline_start_time '{pipeline_start_time}': {e}\",",
        'extra={"pipeline_start_time": pipeline_start_time},',
        ")",
    ),
    1094: (
        "logger.info(",
        'f"Created event {event.id}: risk_score={event.risk_score}",',
        "extra={",
        '"event_id": event.id,',
        '"risk_score": event.risk_score,',
        '"items_processed": self._stats.items_processed,',
        "},",
        ")",
    ),
}


@cache
def _shipped_linenos(start: int) -> frozenset[int]:
    """Every line (1-based) of M's loaded source holding the shipped call block."""
    stripped = [ln.strip() for ln in inspect.getsource(M).splitlines()]
    block = list(_LOG_CALL_BLOCKS[start])
    hits = frozenset(
        i + 1
        for i in range(len(stripped) - len(block) + 1)
        if stripped[i : i + len(block)] == block
    )
    assert hits, (
        f"shipped call transcribed at L{start} not found anywhere in M's source "
        f"({M.__file__}) — transcription drifted, fix the block table"
    )
    return hits


# =============================================================================
# Shipped literals, transcribed from backend/services/pipeline_workers.py
# =============================================================================

BATCH_LABEL = "batch_to_analyze"  # L1065
STAGE = "analyze"  # L1067
TOTAL_LABEL = "total_pipeline"  # L1080
STARTED_FAILED_DEBUG = "Failed to broadcast batch.analysis_started: {}"  # L1045
PROCESSING_INFO = "Processing analysis for batch {}"  # L1026
COMPLETED_KEYS = {
    "batch_id",
    "camera_id",
    "event_id",
    "risk_score",
    "risk_level",
    "duration_ms",
    "completed_at",
}  # L1114-L1122
FACTORY = "backend.services.event_broadcaster.get_broadcaster"  # L826


# =============================================================================
# Stimulus + scripted-clock constants
# =============================================================================

BATCH = "batch-550e8400-e29b-41d4"
CAM = "cam-front-door-01"
IDS = [11, 22, 33]
EVENT_ID = "evt-9f8e7d6c"
RISK_SCORE = 77
T0 = 1000.0  # L989 start stamp handed out by the scripted clock
T1 = 1001.5  # the L1059/L1062 reads -> shipped duration_ms == 1500
T2 = 2000.0  # second item's start stamp
T3 = 2001.0  # second item's stats stamp / duration end
DURATION_MS = 1500

START_DT = datetime(2026, 1, 1, tzinfo=UTC)  # the parse result of every payload below
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)  # what the datetime seam answers
TOTAL_MS = 43_200_000.0  # (NOW - START_DT).total_seconds() * 1000, as shipped scales it
TOTAL_DEBUG = f"Total pipeline latency: {TOTAL_MS:.1f}ms"  # L1082's f-string rendering

# The four pipeline_start_time shapes the group drives (all unvalidated str fields).
PST_ZULU = "2026-01-01T00:00:00Z"
PST_Z_LOWER = "2026-01-01T00:00:00z"
PST_XXZXX = "2026-01-01T00:00:00XXZXX"
PST_PLAIN = "2026-01-01T00:00:00"
WARNING_Z_LOWER = f"Failed to parse pipeline_start_time '{PST_Z_LOWER}': Invalid isoformat string: '{PST_Z_LOWER}'"
WARNING_XXZXX = (
    "Failed to parse pipeline_start_time "
    f"'{PST_XXZXX}': Invalid isoformat string: '2026-01-01T00:00:00XX+00:00XX'"
)
WARNING_XX_OFFSET = (
    "Failed to parse pipeline_start_time "
    f"'{PST_PLAIN}': Invalid isoformat string: '2026-01-01T00:00:00XX+00:00XX'"
)


def analysis_item(**over: Any) -> dict[str, Any]:
    """A schema-valid analysis payload; ``over`` overrides or adds keys."""
    item: dict[str, Any] = {"batch_id": BATCH, "camera_id": CAM, "detection_ids": list(IDS)}
    item.update(over)
    return item


def no_camera_item(**over: Any) -> dict[str, Any]:
    """Valid payload with the ``camera_id`` KEY ABSENT (the schema default is None)."""
    item: dict[str, Any] = {"batch_id": BATCH, "detection_ids": list(IDS)}
    item.update(over)
    return item


# =============================================================================
# Observation helpers (verbatim from test_pipeline_workers_batch28_00.py)
# =============================================================================


def win(caplog: pytest.LogCaptureFixture) -> None:
    """Open a capture window: DEBUG for this module's logger, empty buffer."""
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()


def mine(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOG_NAME]


def at(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [r for r in mine(caplog) if r.levelno == level]


def msg_table(caplog: pytest.LogCaptureFixture) -> str:
    """Every record this window captured, as ``(levelname, lineno, msg)``."""
    joined = "\n".join(
        f"  ({logging.getLevelName(r.levelno)}) L{r.lineno}: {r.msg!r}" for r in mine(caplog)
    )
    return joined or "  <none>"


# logging's OWN record attributes (the "Attributes" table in the logging docs).
# Everything else on ``record.__dict__`` was injected by ``extra=`` - which is what makes
# a renamed ("XXbatch_idXX") or upper-cased ("BATCH_ID") shipped field, and an
# ``extra=None`` / dropped ``extra=``, observable without reading any value.
# ``message``/``asctime`` are added by formatting, so they are excluded too.
_LOG_RECORD_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


def shipped_extras(r: logging.LogRecord) -> set[str]:
    """The ``extra=`` fields the shipped call attached, RAW off the record."""
    return {k for k in r.__dict__ if k not in _LOG_RECORD_ATTRS}


PROBE = "__context_baseline_probe__"


def baseline_fields(caplog: pytest.LogCaptureFixture) -> set[str]:
    """The field names the shipped ``ContextFilter`` injects into EVERY record.

    ``backend/core/logging.py:504-560`` (the filter the shipped ``setup_logging`` puts on
    this logger) stamps request_id/trace_id/hostname/environment/... onto every record,
    so a record's attribute surface is ``extra=`` PLUS that context, and which context
    fields appear depends on where the suite runs (``container_id`` only inside a
    container).  Measured from one probe record logged at the TOP of a window (the probe
    text itself contains no space, so no ``only`` lookup can ever match it) and then
    dropped with the window's own ``clear()``, so the ``extras`` pins below compare a
    shipped call's OWN payload and stay honest in any environment.
    """
    M.logger.debug(PROBE)
    probe = next(r for r in reversed(mine(caplog)) if r.msg == PROBE)
    caplog.clear()
    return shipped_extras(probe)


def extras(caplog: pytest.LogCaptureFixture, baseline: set[str]) -> dict[str, set[str]]:
    """level name -> the union of the shipped ``extra=`` OWN fields at that level."""
    out: dict[str, set[str]] = {}
    for r in mine(caplog):
        out.setdefault(logging.getLevelName(r.levelno), set()).update(shipped_extras(r) - baseline)
    return out


def pin_record(
    r: logging.LogRecord,
    *,
    msg: str,
    level: int,
    where: int,
) -> None:
    """Assert the observable surface of one shipped log call (RAW ``msg`` + call site)."""
    assert r.msg == msg, f"log text mutated at {where}: {r.msg!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated at {where}: {r.levelno} != {level}"
    assert r.lineno in _shipped_linenos(int(where)), (
        f"log call site mutated: {msg!r} shipped at L{where}, fired at L{r.lineno} "
        f"(no line of M's loaded source holds the shipped call there)"
    )
    assert tuple(r.args or ()) == (), (
        f"unexpected lazy args for an f-string message at {where}: {r.args!r}"
    )
    assert r.exc_info is None, (
        f"exc_info present at {where} where the shipped call passes none: {r.exc_info!r}"
    )


def pin_extra(r: logging.LogRecord, key: str, expected: Any, *, where: str) -> Any:
    """One shipped ``extra=`` field, read as a RAW record attribute."""
    got = getattr(r, key, "<MISSING>")
    assert got == expected, f"log extra {key!r} mutated or lost at {where}: {got!r} != {expected!r}"
    return got


def only(
    caplog: pytest.LogCaptureFixture,
    level: int,
    msg: str,
    *,
    where: int,
) -> logging.LogRecord:
    """Exactly one record in the window carries ``msg`` at ``level``, with every field.

    Looked up BY message, because a successful item legitimately logs two INFO lines
    (L1026 and L1094) - ``levels`` pins the count surface separately.  A mutation that
    turns a message into ``None`` still reddens here and the window is printed.
    """
    recs = [r for r in at(caplog, level) if r.msg == msg]
    assert len(recs) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record {msg!r} from {LOG_NAME} "
        f"at L{where}, window was:\n{msg_table(caplog)}"
    )
    pin_record(recs[0], msg=msg, level=level, where=where)
    return recs[0]


def levels(caplog: pytest.LogCaptureFixture) -> dict[str, int]:
    """The window's COMPLETE level surface: level name -> record count."""
    out: dict[str, int] = {}
    for r in mine(caplog):
        out[logging.getLevelName(r.levelno)] = out.get(logging.getLevelName(r.levelno), 0) + 1
    return out


def surface(caplog: pytest.LogCaptureFixture, *allowed: int) -> None:
    """No record at any level outside ``allowed``."""
    stray = sorted(
        {logging.getLevelName(r.levelno) for r in mine(caplog) if r.levelno not in allowed}
    )
    assert not stray, (
        f"unexpected {stray} record(s) from {LOG_NAME}, window was:\n{msg_table(caplog)}"
    )


def surface_extras(
    caplog: pytest.LogCaptureFixture, baseline: set[str], **per_level: set[str]
) -> None:
    """The COMPLETE extra surface: level name -> the exact shipped ``extra=`` key set."""
    got = extras(caplog, baseline)
    for name, want in per_level.items():
        assert got.get(name, set()) == want, (
            f"{name} extra-surface mutated: shipped carries {sorted(want)}, window carried "
            f"{sorted(got.get(name, set()))}; window was:\n{msg_table(caplog)}"
        )
    unexpected = sorted(set(got) - set(per_level))
    assert not unexpected, (
        f"records at unexpected levels {unexpected}, window was:\n{msg_table(caplog)}"
    )


def calls_of(mock: Any) -> list[Any]:
    """The recorded call list of any mock shape (autospec or plain)."""
    return list(mock.call_args_list)


# =============================================================================
# Live-globals patching (three-worlds safe - batch28_06 pattern)
# =============================================================================


def live_globals(fn: Any) -> dict[str, Any]:
    """Name-resolution dict of the LIVE function object.

    * Pristine repo / shadow replay tree (the mutant module IS the imported module):
      ``fn.__globals__ is M.__dict__`` - identity fast path.
    * A lane that exec's a variant body into a snapshot COPY of the module dict: that
      copy is what the body reads, so it is returned and every ``patch_global`` binds
      inside it.
    * ``mutants/`` re-bank home: the mutmut trampoline's ``__globals__`` is mutmut's own
      dict while the shipped body sits behind ``__wrapped__`` with globals ==
      ``M.__dict__``; the identity guard fires only there.
    """
    g = fn.__globals__
    if g is not M.__dict__:
        w = getattr(fn, "__wrapped__", None)
        if w is not None and w.__globals__ is M.__dict__:
            return M.__dict__
    return g


class _DictOwner:
    """Attribute facade over a module-globals dict for ``patch.object``."""

    def __init__(self, d: dict[str, Any]) -> None:
        self._d = d

    def __getattr__(self, name: str) -> Any:
        try:
            return self._d[name]
        except KeyError as e:
            raise AttributeError(name) from e

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_d":
            super().__setattr__(name, value)
        else:
            self._d[name] = value

    def __delattr__(self, name: str) -> None:
        del self._d[name]


TARGET = M.AnalysisQueueWorker._process_analysis_item


def patch_global(name: str, **kwargs: Any) -> Any:
    """``patch.object`` on the dict the function under test resolves ``name`` through."""
    g = live_globals(TARGET)
    if g is M.__dict__:
        return patch.object(M, name, **kwargs)
    return patch.object(_DictOwner(g), name, create=True, **kwargs)


@contextlib.contextmanager
def _clock_window(fake: FakeClock, ticks: list[float]) -> Iterator[FakeClock]:
    """Install ``fake`` as ``sys.modules["time"]`` and hand it to the caller."""
    with patch.dict(sys.modules, {"time": fake}):
        yield fake


def patch_time(ticks: list[float]) -> Any:
    """Script the shipped def's ``time.time()`` reads for one window (the seam, above).

    An na form (``patch.dict``) which the mock-spec gate accepts.  The fake replaces the
    whole module ONLY inside ``sys.modules`` for the duration of the ``with`` -
    ``FakeClock.__getattr__`` forwards everything else (``monotonic``, ``perf_counter``,
    ``sleep``) to the REAL module and an exhausted tick list falls back to the real
    clock, so foreign code inside the window (asyncio, logging, pytest) never sees a
    frozen or rewound wall clock.  Installed AFTER the instrumentation double patchers
    are entered, because an autospec double's repr calls ``time.time``.
    """
    fake = FakeClock(ticks)
    return _clock_window(fake, ticks)


# =============================================================================
# The instrumentation stack every leg drives
# =============================================================================


def span_cm(span: Any) -> MagicMock:
    """A FRESH ``MagicMock`` usable as ``start_as_current_span(name)``'s return value."""
    cm = MagicMock(name="span-cm")
    cm.__enter__ = MagicMock(return_value=span)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class FakeClock:
    """A scripted wall clock installed as ``sys.modules["time"]`` for one window."""

    def __init__(self, ticks: list[float]) -> None:
        self.ticks = list(ticks)
        self.uses = 0
        self.real = real_time

    def time(self) -> float:
        if self.ticks:
            v = self.ticks[min(self.uses, len(self.ticks) - 1)]
            self.uses += 1
            return v
        return self.real.time()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.real, name)  # monotonic/perf_counter/sleep stay real


def script_dt(now: Any, patched: list[Any]) -> MagicMock:
    """A stand-in for the module-global ``datetime`` whose ``now`` answers ``now``.

    ``fromisoformat`` and ``utcfromtimestamp`` are aliased to the REAL functions, so the
    parse under test stays the shipped parse and a mutation of a name this file never
    scripted still explodes inside the shipped body instead of being absorbed.
    """
    dt = MagicMock(name="datetime")
    dt.now.return_value = now
    dt.fromisoformat = datetime.fromisoformat
    dt.utcfromtimestamp = datetime.utcfromtimestamp
    patched.clear()
    patched.append(dt)
    return dt


@dataclass
class Doppels:
    """The module-level names the shipped def reaches, patched for one window."""

    log_context: Any
    tracer: Any
    span: Any
    add_attrs: Any
    stage_latency: Any
    redis_latency: Any
    rec_error: Any
    rec_exc: Any
    factory: Any
    scripted: dict[str, Any] = field(default_factory=dict)


@contextlib.contextmanager
def instrumentation(*, now: Any = None) -> Iterator[Doppels]:
    """Patch every module-level callee of the shipped def in the LIVE world.

    ``autospec=True`` on every real callable target (WP4.2 fast path); ``tracer`` and
    ``datetime`` are object swaps (``new_callable`` - an na form: both shipped values are
    objects, not signatures to enforce).  ``validate_analysis_payload`` is left REAL (the
    security gate is group g00's target, and a valid payload must pass it for real).  The
    broadcaster factory answers ``None``, so a leg that wants the shipped
    no-broadcaster state gets it without constructing a real broadcaster.
    """
    span = MagicMock(name="span")
    scripted: dict[str, Any] = {}
    patched: list[Any] = []
    with contextlib.ExitStack() as stack:
        log_ctx = stack.enter_context(patch_global("log_context", autospec=True))
        tracer = stack.enter_context(
            patch_global("tracer", new_callable=lambda: MagicMock(name="tracer"))
        )
        tracer.start_as_current_span.side_effect = lambda _name: span_cm(span)
        add_attrs = stack.enter_context(patch_global("add_span_attributes", autospec=True))
        stage = stack.enter_context(patch_global("record_pipeline_stage_latency", autospec=True))
        redis_lat = stack.enter_context(patch_global("record_stage_latency", autospec=True))
        rec_err = stack.enter_context(patch_global("record_pipeline_error", autospec=True))
        rec_exc = stack.enter_context(patch_global("record_exception", autospec=True))
        if now is not None:
            dt = stack.enter_context(
                patch_global("datetime", new_callable=lambda: script_dt(now, patched))
            )
            scripted["datetime"] = patched
            scripted["dt"] = dt
        factory = stack.enter_context(patch(FACTORY, autospec=True, return_value=None))
        yield Doppels(
            log_context=log_ctx,
            tracer=tracer,
            span=span,
            add_attrs=add_attrs,
            stage_latency=stage,
            redis_latency=redis_lat,
            rec_error=rec_err,
            rec_exc=rec_exc,
            factory=factory,
            scripted=scripted,
        )


# =============================================================================
# Worker construction (collaborators injected, never patched)
# =============================================================================


def event_double(risk_level: Any = "high") -> MagicMock:
    """The ``Event`` the shipped ``analyze_batch`` await yields (fields L1095-L1119)."""
    event = MagicMock(name="event")
    event.id = EVENT_ID
    event.risk_score = RISK_SCORE
    event.risk_level = risk_level
    return event


class RiskLevelish(Enum):
    """A member WITH a ``.value`` - one of the three shipped ``risk_level`` shapes."""

    HIGH = "high"


@dataclass(frozen=True)
class CompletedRisk:
    """A completed-payload snapshot: the 6 deterministic keys, ``completed_at`` aside.

    ``risk_score`` is typed ``object`` on purpose: the shipped publish carries the
    event's own ``risk_score`` (an ``int`` here) and this leg must be able to compare the
    whole dict at once.
    """

    batch_id: str
    camera_id: str
    event_id: str
    risk_score: object
    risk_level: str
    duration_ms: int


def completed_payload(broadcaster: Any, *, call_no: int = 0) -> CompletedRisk:
    """The awaited ``broadcast_batch_analysis_completed`` payload, COMPLETE but for one key.

    ``completed_at`` is excluded because it is a real UTC timestamp in legs that do not
    script ``datetime``; every one of the other six keys is pinned, which is what sees the
    twelve ``m164``-``m179`` renames, ``m163`` (payload -> ``None``, caught by the
    ``isinstance`` pin) and the ``m168``/``m169`` ``camera_id`` variants.
    """
    assert broadcaster.broadcast_batch_analysis_completed.await_count == 1, (
        "the shipped NEM-3607 completion publish must fire exactly once per analysed batch"
    )
    awaited = broadcaster.broadcast_batch_analysis_completed.await_args_list[call_no]
    assert len(awaited.args) == 1 and not awaited.kwargs, (
        f"the payload is passed positionally: {awaited!r}"
    )
    payload = awaited.args[0]
    assert isinstance(payload, dict), f"the completion payload mutated: {payload!r}"
    assert set(payload) == COMPLETED_KEYS, f"completion key set mutated: {sorted(payload)}"
    return CompletedRisk(
        batch_id=payload["batch_id"],
        camera_id=payload["camera_id"],
        event_id=payload["event_id"],
        risk_score=payload["risk_score"],
        risk_level=payload["risk_level"],
        duration_ms=payload["duration_ms"],
    )


def analysis_worker(broadcaster: Any = "auto", event: Any = None, redis: Any = None) -> Any:
    """AnalysisQueueWorker with every collaborator injected (no real clients)."""
    analyzer = create_autospec(NemotronAnalyzer, instance=True)
    analyzer.analyze_batch.return_value = event if event is not None else event_double()
    worker = M.AnalysisQueueWorker(
        redis_client=redis if redis is not None else MagicMock(name="redis-client"),
        analyzer=analyzer,
    )
    worker._broadcaster = broadcaster_double() if broadcaster == "auto" else broadcaster
    return worker


def broadcaster_double() -> Any:
    """autospec'd instance double of the shipped broadcaster (publishes are AsyncMocks)."""
    return create_autospec(EventBroadcaster, instance=True)


# =============================================================================
# 1) stats + duration_ms + the two telemetry calls (L1058-L1067) - m80-m103
# =============================================================================


async def test_one_and_a_half_seconds_is_exactly_1500_ms() -> None:
    """Shipped:1062-1067 - the duration and BOTH latency sinks, one exact number.

    ::

        duration = time.time() - start_time
        duration_ms = int(duration * 1000)
        record_pipeline_stage_latency("batch_to_analyze", duration_ms)
        await record_stage_latency(self._redis, "analyze", duration_ms)

    The scripted ticks make ``start_time`` 1000.0 and BOTH later reads (the L1059 stats
    stamp and the L1062 duration end) 1001.5, so shipped reports exactly ``1500`` to both
    sinks.  The five mutants on these two
    statements land on five different values - ``m85`` (``+``) 1_502_250, ``m86``
    (``= None``) ``None``, ``m88`` (``/ 1000``) ``1``, ``m89`` (``* 1001``) ``1501`` - and
    the four label/value mutants move an argument, so ONE complete call-list pin per sink
    kills all nine.  The redis call is pinned POSITIONALLY against the client this leg
    injected (``self._redis`` is a plain instance attribute at L799), so a mutant that
    passed anything else as the client cannot satisfy it either.
    """
    client = MagicMock(name="redis-client")
    worker = analysis_worker(broadcaster=None, redis=client)
    with (
        instrumentation() as d,
        patch_time([T0, T1]) as fake,
    ):
        assert await worker._process_analysis_item(analysis_item()) is None

        # L989 start, L1059 last_processed_at, L1062 duration end - three reads.
        assert fake.uses == 3, (
            f"the shipped def reads the wall clock exactly 3x per item, got {fake.uses}"
        )
        assert calls_of(d.stage_latency) == [call(BATCH_LABEL, DURATION_MS)], calls_of(
            d.stage_latency
        )
        assert calls_of(d.redis_latency) == [call(client, STAGE, DURATION_MS)], calls_of(
            d.redis_latency
        )
        assert d.redis_latency.await_count == 1, "record_stage_latency is awaited as shipped"
        assert calls_of(d.redis_latency)[0].args[0] is client, "the shipped call passes self._redis"

    assert worker.stats.items_processed == 1, worker.stats


async def test_two_successful_items_increment_the_processed_stat_once_each() -> None:
    """``items_processed += 1`` (L1058) and the ``last_processed_at`` stamp (L1059).

    After ONE item ``items_processed == 1`` is what BOTH shipped and ``m80``
    (``= 1``) report, so the intermediate assert after the first item is load-bearing: it
    is the second item's ``2`` that separates the re-stamp from the increment, while
    ``m9``-shaped ``-=``/``+= 2`` variants would already have failed the first.
    ``last_processed_at`` is pinned through ``WorkerStats.to_dict()`` (L212-L219 - the
    shape the status API serves) on BOTH sides of the second item: shipped stamps the
    scripted wall-clock float on every success - the stamp is the item's SECOND read -
    so under ``m83`` (``= None``) both reads fail.
    """
    worker = analysis_worker(broadcaster=None)
    with instrumentation(), patch_time([T0, T1, T1, T2, T3, T3]):
        assert await worker._process_analysis_item(analysis_item(batch_id="batch-first")) is None
        assert worker.stats.to_dict()["last_processed_at"] == T1
        assert await worker._process_analysis_item(analysis_item(batch_id="batch-second")) is None

    assert worker.stats.items_processed == 2, (
        f"two items must count 2 processed, got {worker.stats.items_processed}"
    )
    assert worker.stats.to_dict()["last_processed_at"] == T3
    assert isinstance(worker.stats.to_dict()["last_processed_at"], float), worker.stats.to_dict()
    assert worker.stats.errors == 0, worker.stats


# =============================================================================
# 2) total-pipeline latency (L1070-L1092) - m110-m140
# =============================================================================


async def test_a_zulu_pipeline_start_time_records_the_total_pipeline_latency(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1070-1087 - the ``Z`` arm, the exact millisecond scale, the DEBUG line.

    ::

        if pipeline_start_time:
            try:
                start_dt = datetime.fromisoformat(pipeline_start_time.replace("Z", "+00:00"))
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=UTC)
                total_duration_ms = (datetime.now(UTC) - start_dt).total_seconds() * 1000
                record_pipeline_stage_latency("total_pipeline", total_duration_ms)
                logger.debug(f"Total pipeline latency: {total_duration_ms:.1f}ms", extra={...})

    With the parse pinned to midnight UTC and ``datetime.now(UTC)`` answered at noon,
    shipped's ``* 1000`` scale yields exactly ``43_200_000.0``; ``m117`` (``/ 1000``)
    yields ``43_200.0`` and ``m120`` (``* 1001``) ``43_243_200_000.0``, and ``m112``
    raises inside the parse so BOTH the record and the DEBUG vanish.  The surface asserts
    are the complete ones - INFO twice (L1026 and L1094), DEBUG once carrying exactly
    ``total_pipeline_ms`` + ``pipeline_start_time`` - so ``m127``/``m129`` (the DEBUG
    message -> ``None``, or dropped, which makes ``logger.debug(extra=...)`` a
    ``TypeError`` and takes the whole item into the ``except Exception`` arm),
    ``m128``/``m130`` (``extra=None`` / dropped) and the four renames all redden here.
    """
    worker = analysis_worker(broadcaster=None)
    with (
        instrumentation(now=NOW) as d,
        patch_time([T0, T1]),
    ):
        win(caplog)
        base = baseline_fields(caplog)
        assert (
            await worker._process_analysis_item(analysis_item(pipeline_start_time=PST_ZULU)) is None
        )

        assert calls_of(d.stage_latency) == [
            call(BATCH_LABEL, DURATION_MS),
            call(TOTAL_LABEL, TOTAL_MS),
        ], calls_of(d.stage_latency)
        debug = only(caplog, logging.DEBUG, TOTAL_DEBUG, where=1081)
        pin_extra(debug, "total_pipeline_ms", TOTAL_MS, where="1084")
        pin_extra(debug, "pipeline_start_time", PST_ZULU, where="1085")
        assert d.scripted["datetime"][0] is d.scripted["dt"], (
            "the datetime seam is the live-world one"
        )
        assert d.rec_error.call_args_list == [], (
            f"the success arm records no pipeline error: {calls_of(d.rec_error)}"
        )

    only(caplog, logging.INFO, f"Created event {EVENT_ID}: risk_score={RISK_SCORE}", where=1094)
    assert levels(caplog) == {"INFO": 2, "DEBUG": 1}, levels(caplog)
    surface_extras(
        caplog,
        base,
        DEBUG={"total_pipeline_ms", "pipeline_start_time"},
        INFO={"event_id", "risk_score", "items_processed"},
    )
    surface(caplog, logging.INFO, logging.DEBUG)


async def test_a_lowercase_zulu_pipeline_start_time_still_parses(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1073-1075 + L1088-L1092 - ``.replace("Z", ...)`` is CASE-SENSITIVE.

    ``datetime.fromisoformat`` accepts a trailing ``Z`` but not a lowercase ``z``, which
    is the only reason the shipped normalisation exists; a payload carrying
    ``"2026-01-01T00:00:00z"`` therefore falls through to the shipped
    ``except (ValueError, TypeError)`` and the WARNING.  Under ``m111``
    (``replace("z", "+00:00")``) the same payload parses, so BOTH halves of this pin
    move: a ``total_pipeline`` record appears where shipped records nothing and the
    WARNING disappears.  That is the whole kill - and the reason the spec keeps this
    payload out of the valid-Z leg.
    """
    worker = analysis_worker(broadcaster=None)
    with (
        instrumentation(now=NOW) as d,
        patch_time([T0, T1]),
    ):
        win(caplog)
        base = baseline_fields(caplog)
        assert (
            await worker._process_analysis_item(analysis_item(pipeline_start_time=PST_Z_LOWER))
            is None
        )

        labels = [c.args[0] for c in calls_of(d.stage_latency)]
        assert labels == [BATCH_LABEL], (
            f"a failed parse must record no total_pipeline latency: {labels}"
        )

        warn = only(caplog, logging.WARNING, WARNING_Z_LOWER, where=1089)
        pin_extra(warn, "pipeline_start_time", PST_Z_LOWER, where="1091")

    assert levels(caplog) == {"INFO": 2, "WARNING": 1}, levels(caplog)
    surface_extras(
        caplog,
        base,
        WARNING={"pipeline_start_time"},
        INFO={"event_id", "risk_score", "items_processed"},
    )


async def test_an_xx_wrapped_pipeline_start_time_warns_without_recording_total_pipeline(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The manifest's PER-KEY EXCEPTION leg for ``m110`` - single payload, shipped only.

    ``pipeline_start_time`` is an UNVALIDATED ``str`` on the queue payload, so the
    ``XXZXX`` literal really can arrive.  Shipped replaces ``"Z"`` (inside ``XXZXX``),
    producing ``'2026-01-01T00:00:00XX+00:00XX'``, which ``fromisoformat`` rejects - so
    (A1) no ``total_pipeline`` record, (A2) exactly one WARNING whose text is the shipped
    f-string and whose ``extra.pipeline_start_time`` is the raw value, and (A3) the
    success INFO still fires because the item runs to completion.  Under ``m110``
    (``replace("XXZXX", "+00:00")``) the same payload becomes valid ISO, so A1 records
    ``43_200_000.0`` and A2's WARNING disappears - both fail.  Kept single-payload per the
    manifest: ``m110`` also records ``total_pipeline`` for a VALID-Z timestamp, so mixing
    the two payloads in one leg would let the mutant satisfy the pair.
    """
    worker = analysis_worker(broadcaster=None)
    with (
        instrumentation(now=NOW) as d,
        patch_time([T0, T1]),
    ):
        win(caplog)
        base = baseline_fields(caplog)
        assert (
            await worker._process_analysis_item(analysis_item(pipeline_start_time=PST_XXZXX))
            is None
        )

        labels = [c.args[0] for c in calls_of(d.stage_latency)]
        assert labels == [BATCH_LABEL], f"(A1) shipped parses this payload to nothing: {labels}"

        warn = only(caplog, logging.WARNING, WARNING_XXZXX, where=1089)
        pin_extra(warn, "pipeline_start_time", PST_XXZXX, where="1091")

    only(caplog, logging.INFO, f"Created event {EVENT_ID}: risk_score={RISK_SCORE}", where=1094)
    assert levels(caplog) == {"INFO": 2, "WARNING": 1}, levels(caplog)
    surface_extras(
        caplog,
        base,
        WARNING={"pipeline_start_time"},
        INFO={"event_id", "risk_score", "items_processed"},
    )


async def test_a_plain_iso_pipeline_start_time_gets_the_utc_tzinfo_branch(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1077-L1078 - the naive-parse branch, and the other half of the m112 kill.

    ``"2026-01-01T00:00:00"`` has no zone, so shipped's ``.replace("Z", "+00:00")`` is a
    no-op on it, ``fromisoformat`` returns a NAIVE datetime and the L1077 guard stamps
    UTC on it, so shipped records the same ``43_200_000.0`` as the Zulu leg.  Under
    ``m112`` the offset literal is ``"XX+00:00XX"``, so this payload becomes
    ``2026-01-01T00:00:00XX+00:00XX`` and the parse RAISES: the record and the DEBUG both
    disappear and a WARNING takes their place - which is exactly what the two asserts on
    ``stage_latency`` and the DEBUG line here reject.  (The pair partner is the
    ``XXZXX``/lowercase-``z`` warning legs: there shipped warns and the variant records.
    Either direction, ``m112`` reddens.)
    """
    worker = analysis_worker(broadcaster=None)
    with (
        instrumentation(now=NOW) as d,
        patch_time([T0, T1]),
    ):
        win(caplog)
        base = baseline_fields(caplog)
        assert (
            await worker._process_analysis_item(analysis_item(pipeline_start_time=PST_PLAIN))
            is None
        )

        assert calls_of(d.stage_latency) == [
            call(BATCH_LABEL, DURATION_MS),
            call(TOTAL_LABEL, TOTAL_MS),
        ], calls_of(d.stage_latency)
        only(caplog, logging.DEBUG, TOTAL_DEBUG, where=1081)
        assert levels(caplog) == {"INFO": 2, "DEBUG": 1}, levels(caplog)
        surface_extras(
            caplog,
            base,
            DEBUG={"total_pipeline_ms", "pipeline_start_time"},
            INFO={"event_id", "risk_score", "items_processed"},
        )


async def test_a_bare_payload_skips_the_total_pipeline_block_entirely(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The negative half of L1070: no ``pipeline_start_time`` -> no total latency, no DEBUG.

    ``m110``/``m111``/``m112`` all sit INSIDE the ``if pipeline_start_time:`` block, and
    a mutant that turned the guard itself into a no-op would leave every recording leg
    above silent - so this leg pins what shipped does when the field is absent: the batch
    latency is still reported, the total is not, no DEBUG fires, and the item still
    completes.  It is also the leg that makes ``TOTAL_MS`` non-coincidental: the ONLY
    place a ``total_pipeline`` number can come from is the payload-driven block.
    """
    worker = analysis_worker(broadcaster=None)
    with (
        instrumentation(now=NOW) as d,
        patch_time([T0, T1]),
    ):
        win(caplog)
        assert await worker._process_analysis_item(analysis_item()) is None

        assert calls_of(d.stage_latency) == [call(BATCH_LABEL, DURATION_MS)], calls_of(
            d.stage_latency
        )
        assert at(caplog, logging.DEBUG) == [], (
            f"no total-pipeline DEBUG without a start time:\n{msg_table(caplog)}"
        )
        assert at(caplog, logging.WARNING) == [], f"nothing to warn about:\n{msg_table(caplog)}"

    assert levels(caplog) == {"INFO": 2}, levels(caplog)
    assert worker.stats.items_processed == 1, worker.stats


# =============================================================================
# 3) the success INFO (L1094-L1101) - m141-m150
# =============================================================================


async def test_the_success_info_carries_the_event_id_risk_score_and_stat(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1094-1101 - the success line and its three shipped ``extra=`` fields.

    ::

        logger.info(
            f"Created event {event.id}: risk_score={event.risk_score}",
            extra={"event_id": event.id, "risk_score": event.risk_score,
                   "items_processed": self._stats.items_processed},
        )

    The stat is read LIVE off ``self._stats``, so the leg drives TWO items and pins the
    text plus ``items_processed == 1`` then ``2``: a rename of any of the three fields
    (``m145``-``m150``) reddens the ``surface_extras`` pin, ``m142``/``m144``
    (``extra=None``/dropped) empty it, and ``m141``/``m143`` (message -> ``None`` or
    dropped, which again makes the call a ``TypeError``) empty the INFO line entirely.
    A second item also re-kills ``m80`` through the live stat value.
    """
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster=broadcaster)
    with instrumentation() as d:
        win(caplog)
        base = baseline_fields(caplog)
        assert await worker._process_analysis_item(analysis_item(batch_id="batch-one")) is None

        first = only(
            caplog, logging.INFO, f"Created event {EVENT_ID}: risk_score={RISK_SCORE}", where=1094
        )
        pin_extra(first, "event_id", EVENT_ID, where="1097")
        pin_extra(first, "risk_score", RISK_SCORE, where="1098")
        pin_extra(first, "items_processed", 1, where="1099")
        surface_extras(caplog, base, INFO={"event_id", "risk_score", "items_processed"})

        caplog.clear()  # second window: the shipped line recurs per item
        assert await worker._process_analysis_item(analysis_item(batch_id="batch-two")) is None
        second = only(
            caplog, logging.INFO, f"Created event {EVENT_ID}: risk_score={RISK_SCORE}", where=1094
        )
        pin_extra(second, "items_processed", 2, where="1099")
        assert levels(caplog) == {"INFO": 2}, levels(caplog)

    assert broadcaster.broadcast_batch_analysis_completed.await_count == 2


# =============================================================================
# 4) risk_level normalisation + batch.analysis_completed (L1104-L1123)
#    m151-m180
# =============================================================================


async def test_an_enum_risk_level_publishes_its_value() -> None:
    """Shipped:1107-1123 - the ``hasattr(x, "value")`` arm and the completion payload.

    ::

        risk_level_str = "low"  # default
        if event.risk_level is not None:
            if hasattr(event.risk_level, "value"):
                risk_level_str = event.risk_level.value
            else:
                risk_level_str = str(event.risk_level)
        await broadcaster.broadcast_batch_analysis_completed({...7 keys...})

    An enum member HAS ``.value``, so shipped publishes ``"high"``.  Every ``hasattr``
    mutant is caught by that one pin: ``m155``/``m156``/``m159``/``m160`` all make the
    guard False and route the level through ``str(...)``, which for
    ``RiskLevelish.HIGH`` is ``"RiskLevelish.HIGH"``; ``m157``/``m158`` drop an argument
    of the autospec-enforced builtin and raise inside the shipped body; ``m154`` flips the
    ``is None`` guard and takes the default.  The payload itself is pinned COMPLETE (all
    seven keys, six values plus the key set) so the twelve ``m164``-``m179`` renames,
    ``m163`` (payload -> ``None``) and ``m168``/``m169`` cannot hide.
    """
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster=broadcaster, event=event_double(RiskLevelish.HIGH))
    with instrumentation(), patch_time([T0, T1]):
        assert await worker._process_analysis_item(analysis_item()) is None

    assert completed_payload(broadcaster) == CompletedRisk(
        batch_id=BATCH,
        camera_id=CAM,
        event_id=EVENT_ID,
        risk_score=RISK_SCORE,
        risk_level="high",
        duration_ms=DURATION_MS,
    )


async def test_a_string_risk_level_publishes_its_str_form() -> None:
    """The ``else`` arm at L1111-L1112: a level with NO ``.value`` is ``str(...)``ed.

    A plain ``str`` has no ``.value``, so shipped publishes exactly the string; under
    ``m161`` the publish carries ``None`` and under ``m162`` (``str(None)``) the text
    ``"None"`` - the payload equality sees both.  This is also the second leg of the
    ``m154``/``m155``-family net: only an arm that really evaluated
    ``hasattr("HIGH...", "value")`` as False can land on the right value here.
    """
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster=broadcaster, event=event_double("medium"))
    with instrumentation(), patch_time([T0, T1]):
        assert await worker._process_analysis_item(analysis_item()) is None

    assert completed_payload(broadcaster) == CompletedRisk(
        batch_id=BATCH,
        camera_id=CAM,
        event_id=EVENT_ID,
        risk_score=RISK_SCORE,
        risk_level="medium",
        duration_ms=DURATION_MS,
    )


async def test_a_missing_risk_level_publishes_the_low_default() -> None:
    """L1107-L1108: ``risk_level is None`` keeps the shipped ``"low"`` default.

    This is the SOLE route to ``m151``/``m152``/``m153`` (the default stamped ``None``,
    ``"XXlowXX"``, ``"LOW"``) and to ``m154`` from the other side: with the guard flipped
    the ``None`` level enters the block and ``hasattr(None, "value")`` answers False, so
    the publish carries ``str(None)`` == ``"None"`` instead of ``"low"``.
    """
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster=broadcaster, event=event_double(None))
    with instrumentation(), patch_time([T0, T1]):
        assert await worker._process_analysis_item(analysis_item()) is None

    assert completed_payload(broadcaster) == CompletedRisk(
        batch_id=BATCH,
        camera_id=CAM,
        event_id=EVENT_ID,
        risk_score=RISK_SCORE,
        risk_level="low",
        duration_ms=DURATION_MS,
    )


@pytest.mark.parametrize("camera", [CAM, None], ids=["with-camera", "no-camera"])
async def test_the_completion_payload_follows_the_camera_arm(camera: str | None) -> None:
    """``camera_id or ""`` in the completion payload - both arms (m166-m169).

    With a real camera shipped publishes CAM, which is where ``m168``
    (``camera_id and ""``) publishes ``""``; with the key absent shipped publishes ``""``,
    which is where ``m169`` (``or "XXXX"``) publishes ``"XXXX"``.  Read as a pair the two
    parameter cases separate all four camera variants, and the complete payload equality
    covers the renames on this line too.
    """
    broadcaster = broadcaster_double()
    item = analysis_item() if camera is not None else no_camera_item()
    worker = analysis_worker(broadcaster=broadcaster)
    with instrumentation(), patch_time([T0, T1]):
        assert await worker._process_analysis_item(item) is None

    assert completed_payload(broadcaster).camera_id == (CAM if camera is not None else "")


async def test_the_completed_timestamp_is_the_shipped_utc_isoformat() -> None:
    """``m180``/``m178``/``m179`` - the key set, then the UTC FORM of ``completed_at``.

    Shipped L1121 renders a timezone-AWARE UTC stamp; ``m180``'s ``datetime.now(None)``
    is the naive local form with no offset and no tzinfo, so under that mutant every other
    key of the payload is identical and ONLY the ``completed_at`` FORM moves - no other
    leg can see that, which is why the ISO text is pinned directly, on the REAL clock,
    with no seam in this leg.  ``tzinfo is not None`` holds whatever the host timezone is
    (a naive string always parses to ``tzinfo=None``); the ``+00:00`` suffix and the
    recency window pin shipped's UTC rendering itself.  The key-set assert ahead of it is
    ``m178``/``m179``'s kill, and it is what makes the ``payload[...]`` read below sound:
    under a renamed key the leg fails on the key set instead of on a ``KeyError``.
    """
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster=broadcaster)
    with instrumentation():
        assert await worker._process_analysis_item(analysis_item()) is None

    payload = broadcaster.broadcast_batch_analysis_completed.await_args.args[0]
    assert set(payload) == COMPLETED_KEYS, f"completion key set mutated: {sorted(payload)}"
    text = payload["completed_at"]
    parsed = datetime.fromisoformat(text)
    assert parsed.tzinfo is not None, f"L1121 renders UTC-aware ISO text, got {text!r}"
    assert text.endswith("+00:00"), f"shipped UTC ISO text carries the +00:00 offset: {text!r}"
    assert abs((datetime.now(UTC) - parsed).total_seconds()) < 120, (
        f"timestamp left the shipped now: {text!r}"
    )


async def test_a_started_publish_failure_does_not_stop_the_completed_publish(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Both NEM-3607 publishes are independent best-effort arms of one item.

    The started publish raises (the shipped DEBUG at L1044 is its only trace) and the
    item still runs to the completion publish with the shipped 1500 ms duration - which
    is also why the payload legs in file 00 cannot be satisfied by an accidental
    ``None`` broadcaster.  A test-level side effect on the FIRST publish only is not a
    clock or name patch, so this leg needs no seam beyond the standard instrumentation.
    """
    broadcaster = broadcaster_double()
    broadcaster.broadcast_batch_analysis_started.side_effect = RuntimeError("redis down")
    worker = analysis_worker(broadcaster=broadcaster)
    with instrumentation(), patch_time([T0, T1]):
        win(caplog)
        base = baseline_fields(caplog)
        assert await worker._process_analysis_item(analysis_item()) is None

        only(caplog, logging.DEBUG, STARTED_FAILED_DEBUG.format("redis down"), where=1044)
        assert broadcaster.broadcast_batch_analysis_completed.await_count == 1

    assert completed_payload(broadcaster) == CompletedRisk(
        batch_id=BATCH,
        camera_id=CAM,
        event_id=EVENT_ID,
        risk_score=RISK_SCORE,
        risk_level="high",
        duration_ms=DURATION_MS,
    )
    assert levels(caplog) == {"DEBUG": 1, "INFO": 2}, levels(caplog)
    surface_extras(
        caplog,
        base,
        DEBUG={"batch_id"},
        INFO={"event_id", "risk_score", "items_processed"},
    )


async def test_a_worker_without_a_broadcaster_still_runs_the_success_arm(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The ``if broadcaster:`` gate at L1104, from the success side.

    File 00 pins the same gate from the started side; here the completion publish must be
    skipped while the stats, BOTH latency sinks and the success INFO all still happen -
    the arm-by-arm proof that no telemetry call is quietly riding on the broadcaster
    (which is what would let ``m57``-style ``broadcaster = None`` mutants survive here).
    """
    worker = analysis_worker(broadcaster=None)
    with instrumentation() as d:
        win(caplog)
        assert await worker._process_analysis_item(analysis_item()) is None

        assert d.factory.await_count == 1, "the shipped lazy getter must consult the factory once"
        assert calls_of(d.stage_latency) != [], (
            "the batch latency must be recorded without a broadcaster"
        )
        assert d.redis_latency.await_count == 1, (
            "the redis latency must be recorded without a broadcaster"
        )

    assert worker.stats.items_processed == 1, worker.stats
    assert levels(caplog) == {"INFO": 2}, levels(caplog)
