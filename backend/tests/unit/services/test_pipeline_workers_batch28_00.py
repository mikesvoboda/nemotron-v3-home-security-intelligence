r"""S3 batch-28 lane 00 - ``pipeline_workers`` group g00 kill battery (62 keys).

Module: ``backend/services/pipeline_workers.py``.  Admitted manifest:
``/tmp/wp-pw/pipeline_workers/`` ``manifest.json`` group 0 (62 KILLABLE / 0 EQUIVALENT /
0 NEEDS_INVESTIGATION), plus ``group_0.keys`` and ``survivors.json`` for the exact
per-key diffs.  That manifest was proven against git blob 74649fd3 (2268 lines); the
lane source this battery now runs on is the post-VLM-Phase-1 file (2271 lines), which
differs from it by the two hunks of 4bfd6fa4 only - one import line INSERTED at L68 and
the one-line analyzer default at old L799 REPLACED by the three-line mode-built form at
L800-L802.  Every ``L``/``Shipped:`` citation below is to the LIVE file, so pre-shift
numbers map old->new as: N (N <= 67) -> N, 68 <= N <= 798 -> N+1, N >= 800 -> N+3 (old
L799 itself is the replaced statement, whose live position is L802).  Neither hunk
touches any statement this group owns, so the 62 keys, their diffs and their killing
legs are unchanged - only their coordinates moved.

Target: ``AnalysisQueueWorker._process_analysis_item`` (shipped L978-L1187), the part
this group owns: the SECURITY validation arm (L987-L1008), the ``log_context`` + OTel
span instrumentation (L1013-L1026) and the ``batch.analysis_started`` publish
(L1028-L1047).  The success-arm stats/telemetry and the ``batch.analysis_completed``
publish are group g01 and live in ``test_pipeline_workers_batch28_00b.py``; the two
files share one observation contract (``win`` / ``mine`` / ``at`` / ``only`` /
``surface`` / ``levels`` / ``extras`` / ``surface_extras`` / ``patch_global`` /
``instrumentation``) so a leg's failure output always shows the whole shipped surface
the mutant moved.

Test -> mutant-key map
======================
Occurrence-twin check: every g00 diff ``(function, before, after, line)`` tuple was
searched across all 959 survivors - no pair occurs anywhere else, so this group carries
no twin keys and no g00 key is claimed by another group.  (Cross-group near-neighbours
deliberately NOT claimed: the L999-L1001-shaped mutants on ``_run_loop`` L960-L969 and on
the inner ``except Exception`` arm L1153-L1160 belong to g02, and the twin of L999
``self._stats.errors += 1`` at L1154 is g02's key.)

- L999 ``self._stats.errors += 1``: ``m8`` ``= 1``, ``m9`` ``-= 1``, ``m10`` ``+= 2``
  -> ``test_two_rejected_payloads_increment_the_error_stat_once_each`` - one reject
  leaves ``errors == 1`` under BOTH shipped and ``m8``, so the leg asserts after the
  FIRST reject (kills m9/m10) and after the SECOND (ships ``2``, kills m8).
- L1000 ``record_pipeline_error("invalid_analysis_payload")``: ``m11`` arg -> ``None``,
  ``m12`` ``"XXinvalid_analysis_payloadXX"``, ``m13`` ``"INVALID_ANALYSIS_PAYLOAD"``
  -> ``test_a_rejected_payload_reports_the_shipped_invalid_analysis_payload_label``.
- L1001-L1007 the SECURITY ERROR: ``m14`` msg -> ``None``, ``m16`` msg DROPPED (leaves
  ``logger.error(extra=...)`` - a keyword-only call that raises ``TypeError`` for the
  missing required ``msg``, so the ERROR vanishes and the def dies), ``m15``
  ``extra=None``, ``m17`` extra DROPPED, ``m18``/``m19`` ``"raw_item"`` ->
  ``"XXraw_itemXX"``/``"RAW_ITEM"``, ``m20`` ``str(None)``, ``m21`` ``[:501]``,
  ``m22``/``m23`` ``"error"`` -> ``"XXerrorXX"``/``"ERROR"``, ``m24`` ``str(None)``
  -> SOLE route: ``test_a_rejected_payload_logs_the_security_error_with_both_extras``
  (message character-for-character, ``raw_item`` cut to EXACTLY 500 chars of
  ``str(item)``, ``error == str(e)``, plus ``levels``/``extras`` - one ERROR, one
  ``raw_item``+``error`` field, nothing else - so a vanished record is as loud as a
  mutated field).
- L1014 ``log_context(batch_id=..., camera_id=..., operation="analysis")``: ``m25``
  batch -> ``None``, ``m26`` camera -> ``None``, ``m27`` operation -> ``None``, ``m28``
  batch DROPPED, ``m29`` camera DROPPED, ``m30`` operation DROPPED, ``m31``
  ``"XXanalysisXX"``, ``m32`` ``"ANALYSIS"`` -> the exact-kwargs pin inside
  ``test_a_valid_payload_opens_the_shipped_log_and_span_contexts`` (camera-bearing
  payload - the SOLE route to m26, since the schema's own ``camera_id`` default is
  ``None`` and a cameraless payload cannot separate ``camera_id=None`` from shipped)
  and ``test_a_cameraless_batch_reports_camera_id_none_to_log_context``.
- L1015 ``tracer.start_as_current_span("analysis_processing")``: ``m33`` -> ``None``,
  ``m34`` ``"XXanalysis_processingXX"``, ``m35`` ``"ANALYSIS_PROCESSING"`` -> the span
  name captured off the tracer double in both legs above.
- L1018-L1022 ``span_attrs``: ``m37``/``m38`` ``"batch_id"`` renames, ``m39``/``m40``
  ``"detection_count"`` renames, ``m41`` ternary forced False, ``m43`` else-branch ``1``,
  ``m44``-``m47`` the four ``pipeline_stage`` renames/values ->
  ``test_a_camera_batch_adds_the_four_shipped_span_attributes`` (three ids -> count
  ``3``), ``test_an_empty_detection_list_reports_zero_span_count`` (``[]`` -> count
  ``0``; read as a PAIR with the three-id leg, that is what kills m41 AND m43) and the
  cameraless leg (``camera_id`` ABSENT).
- L1023 ``if camera_id is not None:`` -> ``is None`` (``m48``); L1024
  ``span_attrs["camera_id"] = camera_id``: ``m49`` -> ``None``, ``m50``/``m51`` the two
  renames -> the camera-bearing leg pins the COMPLETE spread-kwargs dict (a renamed key
  is both a missing and an unexpected entry; ``m49`` puts ``None`` where CAM is
  required) and the cameraless leg pins the 3-key dict (under ``m48`` it grows a
  ``camera_id=None`` kwarg, which shipped omits).
- L1026 ``logger.info(f"Processing analysis for batch {batch_id}")`` -> ``None``
  (``m52``) -> every valid-payload leg (``only(caplog, INFO, ...)``).
- L1029 ``detection_count = len(detection_ids) if detection_ids else 0``: ``m53``
  ``= None``, ``m54`` ternary forced False, ``m56`` else ``1`` -> the started-payload
  count pin in BOTH detection-list shapes (3 and 0) - the pair separates all three
  variants from shipped's ``3``/``0``.
- L1030 ``broadcaster = await self._get_broadcaster()`` -> ``= None`` (``m57``) ->
  ``test_the_started_broadcast_carries_exactly_the_five_shipped_keys`` (under m57 the
  await-count is 0, so the publish is simply missing) while
  ``test_a_worker_without_a_broadcaster_skips_both_publishes`` pins the negative half of
  the same shipped gate, so the killing leg cannot be satisfied by an accidental None.
- L1033-L1040 the ``batch.analysis_started`` payload: ``m58`` payload -> ``None``,
  ``m59``/``m60`` ``batch_id`` renames, ``m61``/``m62`` ``camera_id`` renames, ``m63``
  ``Or`` -> ``And``, ``m64`` ``or "XXXX"``, ``m65``/``m66`` ``detection_count`` renames,
  ``m67``/``m68`` ``queue_position`` renames, ``m69`` ``queue_position: 1``,
  ``m70``/``m71`` ``started_at`` renames ->
  ``test_the_started_broadcast_carries_exactly_the_five_shipped_keys`` (param
  ``camera_id`` present/absent - the pair gives both arms of shipped's
  ``camera_id or ""``, which is what separates m63 (``camera_id and ""`` -> ``""`` for a
  REAL camera) and m64 (``or "XXXX"`` -> ``"XXXX"`` for an absent one) from shipped).
- L1039 ``datetime.now(UTC).isoformat()`` -> ``datetime.now(None)`` (``m72``) ->
  ``test_the_started_timestamp_is_the_shipped_utc_isoformat`` (SOLE route: shipped
  renders a timezone-AWARE UTC string, ``datetime.now(None)`` renders the naive local
  string with no offset and no tzinfo - so the ISO text is pinned directly, and the
  ``tzinfo is not None`` half holds whatever the host timezone is).

Shipped-behaviour facts the legs rely on
========================================
* ``AnalysisQueuePayload`` (``backend/api/schemas/queue.py:132-171``) requires only
  ``batch_id`` (``min_length=1``, no null bytes/newlines), so ``""`` is the shipped
  rejection stimulus and the REAL ``validate_analysis_payload`` - not a double - is what
  raises on it: the pinned ERROR text is the shipped validator's own message, read back
  off the shipped wrapper (queue.py:264-267).
* ``camera_id`` defaults to ``None`` and is pattern-locked, so a MISSING key (never an
  explicit ``None``) is the way a falsy camera reaches L1023/L1036.
* ``time.monotonic`` / ``time.perf_counter`` are never patched anywhere in this file, and
  ``datetime`` is never patched either: no g00 key needs a scripted clock, so every
  timestamp assertion here is about shipped FORM (a UTC-aware ISO string) rather than
  about an exact instant.  No leg depends on the host timezone.
* The lazy broadcaster factory (``backend.services.event_broadcaster.get_broadcaster``,
  imported function-locally at L826) is patched ``autospec=True`` for the whole
  instrumentation window and answers ``None``, so a leg that wants "no broadcaster"
  gets the shipped ``_get_broadcaster`` failure state WITHOUT constructing a real
  broadcaster, and a leg with a seeded ``_broadcaster`` never reaches the factory at all
  (L824 returns a warm instance).

Discipline (batch28_17 / batch28_06 pattern)
--------------------------------------------
* ``caplog`` windows opened per leg (``set_level`` + ``clear()``, filtered to this
  module's logger), RAW ``record.msg`` / ``record.args`` / ``record.exc_info`` reads,
  and per window the COMPLETE surface: ``levels`` (level -> count), ``extras`` (level ->
  the sorted set of the shipped ``extra=`` fields present, read off
  ``record.__dict__``), ``surface``/``surface_extras`` (nothing outside the shipped
  surface), and ``site`` (the log call site from ``record.lineno``, which makes a
  message RELOCATED to another shipped log line as loud as a mutated one).  Shipped
  ``extra=`` payloads are read as RAW record attributes.
* Every collaborator the shipped def reaches as ``self._*`` (the analyzer, the
  broadcaster, the redis client) is a constructor- or instance-injected double: the
  analyzer from ``create_autospec(VlmAnalyzer, instance=True)``, so a mutated
  ``analyze_batch`` kwarg is a ``TypeError`` inside the shipped body, and the broadcaster
  from ``create_autospec(EventBroadcaster, instance=True)``, so its publishes are
  signature-enforcing AsyncMocks.
* Every module-level name the shipped def resolves globally is patched INSIDE the
  ``with`` window through ``patch.object`` on the LIVE name-resolution dict of the
  function under test (``live_globals`` / ``patch_global`` - three-worlds safe) with
  ``autospec=True`` for real callables; ``tracer`` is an object swap (``new_callable`` -
  an na form: the shipped value is a tracer INSTANCE, not a signature to enforce).  No
  import-time spy and no module-global edit anywhere: nothing leaks past the windows.
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
from functools import cache
from typing import Any
from unittest.mock import MagicMock, call, create_autospec, patch

import pytest

from backend.api.schemas.queue import validate_analysis_payload as REAL_VALIDATE
from backend.services import pipeline_workers as M
from backend.services.event_broadcaster import EventBroadcaster
from backend.services.vlm_analyzer import VlmAnalyzer

LOG_NAME = M.logger.name  # "backend.services.pipeline_workers" (get_logger(__name__))

pytestmark = [pytest.mark.unit]


# =============================================================================
# World-aware re-anchor for the ``where=`` lineno pins (2026-09-27)
# =============================================================================
# In the pristine tree each shipped logger call fires at exactly the line
# transcribed below.  In mutmut's mutant home the module under import is the
# INSTRUMENTED trampoline file: every mutated function is duplicated (orig + one
# copy per mutant), so the shipped statement legitimately fires at one of
# several shifted lines.  A record from a trampoline copy IS still the shipped
# call -- a copy differs from the shipped text ONLY at the mutant's own line --
# so the honest mutation-detecting fact is: the record fired at a line that
# currently holds THIS EXACT shipped call block.  A mutation that moves,
# rewords or reshapes the call breaks the block match at the executed line and
# still reddens here; mutations elsewhere in the function are caught by the
# msg/level/args/exc_info/extras pins, which are untouched.  ``inspect.getsource
# (M)`` reads whichever file M was imported from, so both worlds re-anchor.
_LOG_CALL_BLOCKS: dict[int, tuple[str, ...]] = {
    1001: (
        "logger.error(",
        'f"SECURITY: Rejecting invalid analysis queue payload: {e}",',
        "extra={",
        '"raw_item": str(item)[:500],  # Truncate to prevent log injection',
        '"error": str(e),',
        "},",
        ")",
    ),
    1026: ('logger.info(f"Processing analysis for batch {batch_id}")',),
    1044: (
        "logger.debug(",
        'f"Failed to broadcast batch.analysis_started: {broadcast_err}",',
        'extra={"batch_id": batch_id},',
        ")",
    ),
}


@cache
def _shipped_linenos(start: int) -> frozenset[int]:
    """Every line (1-based) of M's loaded source holding the shipped call block.

    One line in the pristine world; one per trampoline copy in the mutant home.
    The assertion below guards transcription drift: if the block cannot be found
    at all, the pins are stale and must fail LOUD, not silently pass.
    """
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

# L1000: record_pipeline_error("invalid_analysis_payload")
INVALID_LABEL = "invalid_analysis_payload"
# L1002: f"SECURITY: Rejecting invalid analysis queue payload: {e}"
SECURITY_MSG = "SECURITY: Rejecting invalid analysis queue payload: {}"
# L1004: "raw_item": str(item)[:500],  # Truncate to prevent log injection
RAW_ITEM_KEY = "raw_item"
RAW_ITEM_LIMIT = 500
# L1005: "error": str(e)
ERROR_KEY = "error"
# L1014: log_context(batch_id=..., camera_id=..., operation="analysis")
OPERATION = "analysis"
# L1015: tracer.start_as_current_span("analysis_processing")
SPAN_NAME = "analysis_processing"
# L1021: "pipeline_stage": "analysis"
PIPELINE_STAGE_ATTR = "analysis"
# L1026: logger.info(f"Processing analysis for batch {batch_id}")
PROCESSING_INFO = "Processing analysis for batch {}"
# L1045: f"Failed to broadcast batch.analysis_started: {broadcast_err}"
STARTED_FAILED_DEBUG = "Failed to broadcast batch.analysis_started: {}"
# L1034-L1040: the batch.analysis_started payload's shipped key set
STARTED_KEYS = {"batch_id", "camera_id", "detection_count", "queue_position", "started_at"}
# L826: from backend.services.event_broadcaster import get_broadcaster (per call)
FACTORY = "backend.services.event_broadcaster.get_broadcaster"


# =============================================================================
# Stimulus payloads (values chosen so every arg->None / rename / drop differs)
# =============================================================================

BATCH = "batch-550e8400-e29b-41d4"
CAM = "cam-front-door-01"
IDS = [11, 22, 33]


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


# ``batch_id=""`` violates the shipped min_length=1 (queue.py:141-146), and the extra
# ``junk`` value makes str(item) 600+ chars so the [:500] truncation window is real.
JUNK = "Z" * 600
BAD_ITEM = {"batch_id": "", "camera_id": CAM, "detection_ids": list(IDS), "junk": JUNK}


def shipped_rejection(item: dict[str, Any]) -> str:
    """``str`` of the ValueError the SHIPPED validator raises for ``item``.

    ``validate_analysis_payload`` (queue.py:250-267) wraps every adapter failure in
    ``ValueError(f"Invalid analysis queue payload: {e}")``, which is exactly the ``e``
    the shipped ``except ValueError`` at L998 binds - so the ERROR text and
    ``extra["error"]`` pinned below are the shipped gate's own words, not a script.
    """
    with pytest.raises(ValueError) as caught:
        REAL_VALIDATE(item)
    return str(caught.value)


# =============================================================================
# Observation helpers (batch28_17 pattern)
# =============================================================================


def win(caplog: pytest.LogCaptureFixture) -> None:
    """Open a capture window: DEBUG for this module's logger, empty buffer.

    ``set_level`` does NOT clear the buffer, so the ``clear()`` is load-bearing.
    """
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()


def mine(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOG_NAME]


def at(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [r for r in mine(caplog) if r.levelno == level]


def msg_table(caplog: pytest.LogCaptureFixture) -> str:
    """Every record this window captured, as ``(levelname, lineno, msg)``.

    Printed in every log assertion below: a survivor that renames a key, moves a message
    to another line or loses a record has to be readable in the failure text, not only
    in the pass/fail bit.
    """
    return (
        "\n".join(
            f"  ({logging.getLevelName(r.levelno)}) L{r.lineno}: {r.msg!r}" for r in mine(caplog)
        )
        or "  <none>"
    )


# logging's OWN record attributes (the "Attributes" table in the logging docs).
# Everything else on ``record.__dict__`` was injected by ``extra=`` - which is what
# makes a renamed ("XXbatch_idXX") or upper-cased ("BATCH_ID") shipped field, and an
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


def pin_site(caplog: pytest.LogCaptureFixture, msg: str, lineno: int) -> logging.LogRecord:
    """The window's only record carrying ``msg`` must fire at shipped's call site.

    ``record.lineno`` is the line of the ``logger.*`` call, so it is a genuine runtime
    observable (no source-structure claim): a message that moved out of its shipped call
    site reddens here, which is the second, independent way an ``XX``-wrapped or renamed
    duplicate of a shipped line is caught.
    """
    recs = [r for r in mine(caplog) if r.msg == msg]
    assert len(recs) == 1, f"expected exactly 1 record {msg!r}, window was:\n{msg_table(caplog)}"
    assert recs[0].lineno == lineno, (
        f"log call site mutated: {msg!r} shipped at L{lineno}, fired at L{recs[0].lineno}; "
        f"window was:\n{msg_table(caplog)}"
    )
    return recs[0]


def levels(caplog: pytest.LogCaptureFixture) -> dict[str, int]:
    """The window's COMPLETE level surface: level name -> record count."""
    out: dict[str, int] = {}
    for r in mine(caplog):
        out[logging.getLevelName(r.levelno)] = out.get(logging.getLevelName(r.levelno), 0) + 1
    return out


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
    """level name -> the union of the shipped ``extra=`` OWN fields at that level.

    A renamed (``"XXbatch_idXX"``) or upper-cased (``"BATCH_ID"``) shipped field shows up
    as an unexpected name and a lost one as a missing name, even in a leg that reads no
    values; ``extra=None`` and a dropped ``extra=`` collapse the set to empty.
    """
    out: dict[str, set[str]] = {}
    for r in mine(caplog):
        out.setdefault(logging.getLevelName(r.levelno), set()).update(shipped_extras(r) - baseline)
    return out


def pin_record(
    r: logging.LogRecord,
    *,
    msg: str,
    level: int,
    where: str,
) -> None:
    """Assert the observable surface of one shipped log call.

    ``record.msg`` is the RAW message and ``where`` is the raw call site.  Every shipped
    site in this group is an already-interpolated f-string, so ``args`` must stay empty
    (a moved or dropped message argument lands IN ``msg``) and ``exc_info`` must be
    absent.
    """
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

    Looked up BY message rather than by level count, because a fully successful item
    legitimately logs two INFO lines (L1026 ``Processing analysis for batch ...`` and
    L1094 ``Created event ...``) - so "one INFO" is not a shipped fact; ``levels`` pins
    the count surface separately.  A mutation that turns a message into ``None`` still
    reddens here: the lookup finds zero records for the shipped text and the failure
    prints the whole window, ``(20, None)`` included.
    """
    recs = [r for r in at(caplog, level) if r.msg == msg]
    assert len(recs) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record {msg!r} from {LOG_NAME} "
        f"at L{where}, window was:\n{msg_table(caplog)}"
    )
    pin_record(recs[0], msg=msg, level=level, where=where)
    return recs[0]


def surface(caplog: pytest.LogCaptureFixture, *allowed: int) -> None:
    """No record at any level outside ``allowed`` (the COMPLETE level-surface pin)."""
    stray = sorted(
        {logging.getLevelName(r.levelno) for r in mine(caplog) if r.levelno not in allowed}
    )
    assert not stray, (
        f"unexpected {stray} record(s) from {LOG_NAME}, window was:\n{msg_table(caplog)}"
    )


def surface_extras(
    caplog: pytest.LogCaptureFixture, baseline: set[str], **per_level: set[str]
) -> None:
    """The COMPLETE extra surface: level name -> the exact shipped ``extra=`` key set.

    ``WARNING`` / ``INFO`` keys may be given without a keyword (names are legal).  A
    level that shipped logs with no ``extra=`` must appear as an explicit ``set()``.
    """
    got = extras(caplog, baseline)
    for name, want in per_level.items():
        assert got.get(name, set()) == want, (
            f"{name} extra-surface mutated: shipped carries {sorted(want)}, "
            f"window carried {sorted(got.get(name, set()))}; window was:\n{msg_table(caplog)}"
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


# =============================================================================
# The instrumentation stack every leg drives
# =============================================================================


def span_cm(span: Any) -> MagicMock:
    """A FRESH ``MagicMock`` usable as ``start_as_current_span(name)``'s return value.

    Built per call because a MagicMock's ``__enter__``/``__exit__`` are themselves
    shared mocks: one fixture-wide context manager would let a variant body that
    entered the span twice still look like a single entry to the ``with`` statement.
    """
    cm = MagicMock(name="span-cm")
    cm.__enter__ = MagicMock(return_value=span)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class FakeClock:
    """A scripted wall clock, injected through the documented seam (see ``instrumented``).

    The shipped def reads wall time ONLY through ``time.time()`` (L987's function-local
    ``import time``, L989 the start stamp, L1059/L1062 the two stamps that produce
    ``duration_ms``), and that import binds from ``sys.modules`` - so this object is
    installed as ``sys.modules["time"]`` for the window and never reaches an import-time
    ``from time import ...`` binding (``from datetime import ...`` is exactly that, which
    is why the datetime seam is a separate global patch).
    """

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
        return getattr(self.real, name)  # monotonic/perf_counter/sleep stay real - never scripted


def script_dt(now: Any, patched: list[Any]) -> MagicMock:
    """A stand-in for the module-global ``datetime`` whose ``now`` answers ``now``.

    ``classmethod`` is an ordinary global to the shipped def (L11), so patching it is the
    documented seam for the two ``datetime.now(UTC)`` reads inside ONE item (L1079's
    total-pipeline difference and L1113's ``completed_at`` stamp - the real wall clock
    cannot be frozen across two module-global reads).  ``utcfromtimestamp`` is aliased to
    the REAL function so a name-mutation of it still explodes inside the shipped body
    instead of being quietly absorbed by a generic stand-in.
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
def instrumentation(*, clock: list[float] | None = None, now: Any = None) -> Iterator[Doppels]:
    """Patch every module-level callee of the shipped def in the LIVE world.

    ``autospec=True`` on every real callable target (WP4.2 fast path); ``tracer`` and
    ``datetime`` are object swaps (``new_callable`` - an na form: both shipped values are
    objects, not signatures to enforce).  ``validate_analysis_payload`` is deliberately
    NOT patched here at all: the legs drive the REAL shipped security gate, which is the
    only way the pinned ERROR text is the shipped validator's own message.  The
    broadcaster factory answers ``None``, so the shipped lazy getter's failure arm is
    reachable without constructing a real broadcaster.

    ``clock`` scripts the ``time.time`` ticks (``sys.modules["time"]``) and ``now`` the
    two in-item ``datetime.now(UTC)`` reads; both windows are strictly function-local.
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
                patch_global("datetime", new_callable=lambda: script_dt(now, patched)),
            )
            scripted["datetime"] = patched
            scripted["dt"] = dt
        if clock is not None:
            fake = FakeClock(clock)
            stack.enter_context(patch.dict(sys.modules, {"time": fake}))
            scripted["clock"] = fake
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
    """The ``Event`` the shipped ``analyze_batch`` await yields.

    Only the fields the shipped def actually reads are populated (L1095-L1099 and
    L1108-L1119); the rest of the ORM model is irrelevant to this group.
    """
    event = MagicMock(name="event")
    event.id = "evt-9f8e7d6c"
    event.risk_score = 77
    event.risk_level = risk_level
    return event


def broadcaster_double() -> Any:
    """autospec'd instance double of the shipped broadcaster (publishes are AsyncMocks)."""
    return create_autospec(EventBroadcaster, instance=True)


def analysis_worker(broadcaster: Any = "auto", event: Any = None) -> Any:
    """AnalysisQueueWorker with every collaborator injected (no real clients).

    The analyzer is an autospec'd INSTANCE double of the shipped class, so the shipped
    ``analyze_batch(batch_id=..., camera_id=..., detection_ids=...)`` call is
    signature-enforced (a mutated keyword is a ``TypeError`` inside the shipped body)
    and is an ``AsyncMock`` the leg can read.  ``broadcaster`` is installed on the
    INSTANCE - an instance attribute beats the class attribute in every world, so a
    replay mutant of ``_process_analysis_item`` still lands on it through
    ``_get_broadcaster`` (L824: a warm ``_broadcaster`` is returned untouched).  Pass
    ``None`` for the shipped no-broadcaster state.
    """
    analyzer = create_autospec(VlmAnalyzer, instance=True)
    analyzer.analyze_batch.return_value = event if event is not None else event_double()
    worker = M.AnalysisQueueWorker(
        redis_client=MagicMock(name="redis-client"),
        analyzer=analyzer,
    )
    worker._broadcaster = broadcaster_double() if broadcaster == "auto" else broadcaster
    return worker


# =============================================================================
# 1) the SECURITY reject arm (L998-L1008) - m8-m24
# =============================================================================


async def test_a_rejected_payload_logs_the_security_error_with_both_extras(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:998-1008 - the reject arm's ERROR, pinned field by field.

    ::

        except ValueError as e:
            self._stats.errors += 1
            record_pipeline_error("invalid_analysis_payload")
            logger.error(
                f"SECURITY: Rejecting invalid analysis queue payload: {e}",
                extra={
                    "raw_item": str(item)[:500],  # Truncate to prevent log injection
                    "error": str(e),
                },
            )
            return

    The validator is the REAL shipped one (the security gate under test IS the schema),
    so ``e`` here is the shipped wrapper's own message.  ``m14``/``m16`` are caught by
    the message pin (``None``, or the record vanishing entirely - ``logger.error`` with
    ``extra=`` and no message raises ``TypeError`` for the missing required ``msg``,
    which escapes the ``except ValueError`` body), ``m15``/``m17`` and the four key
    renames by the RAW record attributes, and ``m20``/``m24`` (``str(None)``) plus
    ``m21`` (``[:501]``) by the values: ``str(BAD_ITEM)`` is 600+ chars, so both the
    exact text and the exact length pin separate 500 from 501 and from ``"None"``.  The
    ``levels``/``extras`` asserts are the COMPLETE surface: one ERROR carrying exactly
    ``raw_item`` + ``error``, which is what makes a DROPPED record (m16) as loud as a
    mutated field.
    """
    reason = shipped_rejection(BAD_ITEM)
    worker = analysis_worker(broadcaster=None)
    win(caplog)
    base = baseline_fields(caplog)

    assert await worker._process_analysis_item(BAD_ITEM) is None

    err = only(caplog, logging.ERROR, SECURITY_MSG.format(reason), where=1001)
    pin_extra(err, RAW_ITEM_KEY, str(BAD_ITEM)[:RAW_ITEM_LIMIT], where=1003)
    assert len(getattr(err, RAW_ITEM_KEY)) == RAW_ITEM_LIMIT, (
        f"a 600+ char item must be cut to exactly {RAW_ITEM_LIMIT} chars, got {len(getattr(err, RAW_ITEM_KEY))}"
    )
    pin_extra(err, ERROR_KEY, reason, where=1005)
    assert levels(caplog) == {"ERROR": 1}, levels(caplog)
    assert extras(caplog, base) == {"ERROR": {RAW_ITEM_KEY, ERROR_KEY}}, extras(caplog, base)
    assert worker._analyzer.analyze_batch.await_count == 0, (
        "a rejected payload must reach no analyzer"
    )
    assert worker.stats.items_processed == 0, worker.stats
    assert len(JUNK) > RAW_ITEM_LIMIT, "the stimulus must really exceed the truncation window"


async def test_two_rejected_payloads_increment_the_error_stat_once_each() -> None:
    """``self._stats.errors += 1`` at L999 counts once per rejection.

    One reject leaves ``errors == 1`` under shipped AND under ``m8`` (``= 1``), so a
    single call cannot separate them; TWO rejects ship ``2`` and expose the re-stamp.
    ``m9`` (``-= 1`` -> ``-1``) and ``m10`` (``+= 2`` -> ``2`` after one call) are
    already caught by the first intermediate assert.
    """
    worker = analysis_worker(broadcaster=None)

    assert await worker._process_analysis_item(BAD_ITEM) is None
    assert worker.stats.errors == 1, (
        f"one reject must count exactly 1 error, got {worker.stats.errors}"
    )
    assert await worker._process_analysis_item(BAD_ITEM) is None

    assert worker.stats.errors == 2, f"two rejects must count 2 errors, got {worker.stats.errors}"
    assert worker.stats.items_processed == 0, worker.stats
    assert worker.stats.last_processed_at is None, "the reject arm returns before the L1059 stamp"


async def test_a_rejected_payload_reports_the_shipped_invalid_analysis_payload_label() -> None:
    """L1000 is reached once per rejection with the exact shipped label (m11/m12/m13).

    The argument is a Prometheus ``error_type`` LABEL, so all three variants (``None``,
    the ``XX`` wrap, the upper-case rename) change shipped behaviour: the counter series
    an operator queries.  The double is the patched module-level
    ``record_pipeline_error``, i.e. exactly where the shipped def resolves the name.
    """
    worker = analysis_worker(broadcaster=None)
    with instrumentation() as d:
        assert await worker._process_analysis_item(BAD_ITEM) is None

        assert calls_of(d.rec_error) == [call(INVALID_LABEL)], calls_of(d.rec_error)
        assert d.rec_exc.call_args_list == [], "the reject arm records no span exception"


# =============================================================================
# 2) log_context + span + span attributes + the processing INFO (L1013-L1026)
#    m25-m35, m37-m52
# =============================================================================


async def test_a_valid_payload_opens_the_shipped_log_and_span_contexts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1013-1016 - the two context managers, with their shipped arguments.

    ::

        with (
            log_context(batch_id=batch_id, camera_id=camera_id, operation="analysis"),
            tracer.start_as_current_span("analysis_processing"),
        ):

    Both values come from the payload this file chose (``batch_id`` AND ``camera_id``
    are non-``None``), so a ``None``-ed or DROPPED keyword - ``log_context`` is a real
    ``**kwargs`` signature, hence the COMPLETE-dict pin - and a mutated span name are
    the only ways these pins can fail.  The L1026 INFO is asserted here too, so a leg
    that opens the contexts but loses the log (``m52``) is caught as well.
    """
    worker = analysis_worker(broadcaster=None)
    with instrumentation() as d:
        win(caplog)
        assert await worker._process_analysis_item(analysis_item()) is None

        assert len(d.log_context.call_args_list) == 1, d.log_context.call_args_list
        lc = d.log_context.call_args_list[0]
        assert lc.args == (), f"log_context is keyword-only as shipped: {lc.args!r}"
        assert lc.kwargs == {"batch_id": BATCH, "camera_id": CAM, "operation": OPERATION}, lc.kwargs

        # -- the span name (m33/m34/m35) ----------------------------------------
        assert calls_of(d.tracer.start_as_current_span) == [call(SPAN_NAME)], calls_of(
            d.tracer.start_as_current_span
        )

    only(caplog, logging.INFO, PROCESSING_INFO.format(BATCH), where=1026)
    # A complete item logs TWO INFO lines as shipped - L1026 (this group) and L1094
    # ``Created event ...`` (group g01's line), so INFO:2 is the shipped surface here.
    assert levels(caplog) == {"INFO": 2}, levels(caplog)


async def test_a_camera_batch_adds_the_four_shipped_span_attributes() -> None:
    """Shipped:1018-1026 - the span attribute dict, then the INFO.

    ::

        span_attrs = {
            "batch_id": batch_id,
            "detection_count": len(detection_ids) if detection_ids else 0,
            "pipeline_stage": "analysis",
        }
        if camera_id is not None:
            span_attrs["camera_id"] = camera_id
        add_span_attributes(**span_attrs)
        logger.info(f"Processing analysis for batch {batch_id}")

    ``add_span_attributes(**span_attrs)`` SPREADS the dict, so a renamed key is both a
    missing and an unexpected keyword and a ``None``-ed value arrives as ``None``: the
    COMPLETE kwargs dict is the only pin that sees both.  Three detection ids put ``3``
    in the dict, which ``m41`` (ternary forced False) cannot produce, and the
    ``camera_id`` entry is present because ``camera_id`` is not ``None`` - which
    ``m49``/``m50``/``m51`` each break.
    """
    worker = analysis_worker(broadcaster=None)
    with instrumentation() as d:
        assert await worker._process_analysis_item(analysis_item()) is None

        assert len(d.add_attrs.call_args_list) == 1, d.add_attrs.call_args_list
        aa = d.add_attrs.call_args_list[0]
        assert aa.args == (), f"add_span_attributes is keyword-only as shipped: {aa.args!r}"
        assert aa.kwargs == {
            "batch_id": BATCH,
            "detection_count": len(IDS),
            "pipeline_stage": PIPELINE_STAGE_ATTR,
            "camera_id": CAM,
        }, aa.kwargs


async def test_an_empty_detection_list_reports_zero_span_count() -> None:
    """The ``else 0`` half of L1020: ``detection_ids=[]`` -> span count ``0``.

    ``validate_detection_ids`` (queue.py:187-212) documents ``[]`` as valid ("Empty list
    is valid"), so an empty list really does reach L1020 where
    ``len(detection_ids) if detection_ids else 0`` short-circuits to ``0``.  Read as a
    PAIR with the three-id leg above, this is what kills both ``m41``
    (``if (detection_ids) and False`` -> always ``0``, so the three-id leg dies) and
    ``m43`` (else-branch ``1`` -> this leg dies).
    """
    worker = analysis_worker(broadcaster=None)
    with instrumentation() as d:
        assert await worker._process_analysis_item(analysis_item(detection_ids=[])) is None

        assert d.add_attrs.call_args_list[0].kwargs == {
            "batch_id": BATCH,
            "detection_count": 0,
            "pipeline_stage": PIPELINE_STAGE_ATTR,
            "camera_id": CAM,
        }, d.add_attrs.call_args_list[0].kwargs


async def test_a_cameraless_batch_reports_camera_id_none_to_log_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A payload without ``camera_id``: the schema's ``None`` default reaches L1014.

    ``camera_id: str | None = Field(default=None, ...)`` (queue.py:147-152) and the
    shipped def forwards ``validated.camera_id`` unchanged, so ``log_context`` must see
    ``camera_id=None`` and ``add_span_attributes`` must NOT receive a ``camera_id``
    keyword at all, because L1023's guard excludes ``None``.  Under ``m48``'s flipped
    guard this dict GROWS a ``camera_id=None`` kwarg, which is what kills it here; the
    camera-bearing leg above is the one that kills its ``m49``-shaped siblings.
    """
    worker = analysis_worker(broadcaster=None)
    with instrumentation() as d:
        win(caplog)
        assert await worker._process_analysis_item(no_camera_item()) is None

        assert d.log_context.call_args_list[0].kwargs == {
            "batch_id": BATCH,
            "camera_id": None,
            "operation": OPERATION,
        }, d.log_context.call_args_list[0].kwargs
        assert d.add_attrs.call_args_list[0].kwargs == {
            "batch_id": BATCH,
            "detection_count": len(IDS),
            "pipeline_stage": PIPELINE_STAGE_ATTR,
        }, d.add_attrs.call_args_list[0].kwargs

    only(caplog, logging.INFO, PROCESSING_INFO.format(BATCH), where=1026)
    assert levels(caplog) == {"INFO": 2}, levels(caplog)  # L1026 + g01's L1094


async def test_the_analyzer_is_awaited_with_the_three_validated_fields() -> None:
    """Shipped:1052-1056 - the analyzer call carries the payload's own values.

    The analyzer double is autospec'd against the shipped signature, so a mutated or
    dropped keyword is a ``TypeError`` INSIDE the shipped body - which its own
    ``except Exception`` (L1153) would swallow into an error path, taking the telemetry
    and both publishes with it.  The exact-kwarg pin keeps that kill specific and gives
    a second independent route to the two ``camera_id`` mutants (``m26``, ``m48``).
    """
    worker = analysis_worker(broadcaster=None)
    with instrumentation():
        assert await worker._process_analysis_item(analysis_item()) is None

    assert worker._analyzer.analyze_batch.await_count == 1
    awaited = worker._analyzer.analyze_batch.await_args
    assert awaited is not None
    assert awaited.args == (), f"the shipped call is keyword-only: {awaited.args!r}"
    assert awaited.kwargs == {"batch_id": BATCH, "camera_id": CAM, "detection_ids": list(IDS)}, (
        awaited.kwargs
    )


# =============================================================================
# 3) batch.analysis_started (L1028-L1047) - m53-m72
# =============================================================================


@pytest.mark.parametrize("camera", [CAM, None], ids=["with-camera", "no-camera"])
async def test_the_started_broadcast_carries_exactly_the_five_shipped_keys(
    camera: str | None,
) -> None:
    """Shipped:1033-1041 - the complete ``broadcast_batch_analysis_started`` payload.

    ::

        await broadcaster.broadcast_batch_analysis_started(
            {
                "batch_id": batch_id,
                "camera_id": camera_id or "",
                "detection_count": detection_count,
                "queue_position": 0,  # We don't track queue position currently
                "started_at": datetime.now(UTC).isoformat(),
            }
        )

    The dict is built inside the call, so COMPLETE DICT EQUALITY on the awaited
    positional argument is the only observable: it sees every key rename (a renamed key
    is both a missing AND an unexpected entry), ``m58`` (payload -> ``None``), ``m69``
    (``queue_position: 1``) and the ten ``m59``-``m71`` renames.  The two parameter
    cases are the two arms of shipped's ``camera_id or ""``: with a real camera shipped
    yields CAM (``m63``'s ``camera_id and ""`` yields ``""`` there) and without one
    shipped yields ``""`` (``m64``'s ``or "XXXX"`` yields ``"XXXX"`` there).
    ``m57`` (the broadcaster assignment collapsing to ``None``) kills here too - under it
    the await-count below is 0 - and it is why the negative control
    ``test_a_worker_without_a_broadcaster_skips_both_publishes`` exists separately.
    """
    broadcaster = broadcaster_double()
    item = analysis_item() if camera is not None else no_camera_item()
    worker = analysis_worker(broadcaster=broadcaster)
    with instrumentation():
        assert await worker._process_analysis_item(item) is None

    assert broadcaster.broadcast_batch_analysis_started.await_count == 1, (
        "the shipped NEM-3607 publish must fire once per analysed batch"
    )
    awaited = broadcaster.broadcast_batch_analysis_started.await_args
    assert awaited is not None
    assert len(awaited.args) == 1 and not awaited.kwargs, (
        f"the payload is passed positionally: {awaited!r}"
    )
    payload = awaited.args[0]
    assert isinstance(payload, dict), f"the publish payload mutated: {payload!r}"
    assert set(payload) == STARTED_KEYS, f"payload key set mutated: {sorted(payload)}"
    assert payload["batch_id"] == BATCH, payload
    assert payload["camera_id"] == (CAM if camera is not None else ""), payload
    assert payload["queue_position"] == 0, payload


async def test_the_started_count_follows_the_detection_list() -> None:
    """``detection_count`` at L1029 in the started payload: 3 ids -> ``3``, ``[]`` -> ``0``.

    L1029 is a SEPARATE statement from the L1020 span attribute, so its own mutants need
    their own pair of stimuli: shipped reports ``3``/``0``, ``m53`` (``= None``) reports
    ``None`` twice, ``m54`` (ternary forced False) reports ``0`` twice and ``m56``
    (else-branch ``1``) reports ``1`` for the empty list.  No single call separates the
    three variants from shipped, so both shapes are driven in one leg.
    """
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster=broadcaster)
    with instrumentation():
        assert await worker._process_analysis_item(analysis_item()) is None
        assert await worker._process_analysis_item(analysis_item(detection_ids=[])) is None

    counts = [
        c.args[0]["detection_count"]
        for c in broadcaster.broadcast_batch_analysis_started.await_args_list
    ]
    assert counts == [len(IDS), 0], f"detection_count mutated: {counts}"


async def test_the_started_timestamp_is_the_shipped_utc_isoformat() -> None:
    """``m72`` - ``datetime.now(None).isoformat()`` loses the UTC offset, not the instant.

    Shipped L1039 renders a timezone-AWARE UTC datetime, e.g.
    ``"2026-09-27T10:11:12.345678+00:00"``.  ``datetime.now(None)`` is the naive
    local-time form and renders with NO offset suffix and no tzinfo, so under ``m72``
    every other field of the payload is untouched and only the timestamp's FORM moves -
    no other assertion in this file can see that, which is why the ISO text is pinned
    directly here.  ``tzinfo is not None`` holds whatever the host timezone is (a naive
    string always parses to ``tzinfo=None``); the ``+00:00`` suffix and the recency
    window pin the shipped UTC rendering itself.  No clock is patched in this leg.
    """
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster=broadcaster)
    with instrumentation():
        assert await worker._process_analysis_item(analysis_item()) is None

    payload = broadcaster.broadcast_batch_analysis_started.await_args.args[0]
    text = payload["started_at"]
    parsed = datetime.fromisoformat(text)
    assert parsed.tzinfo is not None, f"L1039 renders UTC-aware ISO text, got {text!r}"
    assert text.endswith("+00:00"), f"shipped UTC ISO text carries the +00:00 offset: {text!r}"
    assert abs((datetime.now(UTC) - parsed).total_seconds()) < 120, (
        f"timestamp left the shipped now: {text!r}"
    )


async def test_a_started_broadcast_failure_is_swallowed_into_a_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1042-1047 - a publish failure is DEBUG-only and analysis still runs.

    Stated because it is the arm that makes the payload pins above non-vacuous: the
    publish sits in its own ``try``, so a mutation that makes the publish RAISE would
    otherwise look like a merely-missing payload.  Here the shipped DEBUG text, its
    ``batch_id`` extra and the surviving INFO are pinned and the analyzer must still be
    reached - so ``m52`` (the INFO going ``None``) reddens this leg too, and nothing can
    hide behind the ``except``.
    """
    broadcaster = broadcaster_double()
    broadcaster.broadcast_batch_analysis_started.side_effect = RuntimeError("redis down")
    worker = analysis_worker(broadcaster=broadcaster)
    with instrumentation() as d:
        win(caplog)
        base = baseline_fields(caplog)
        assert await worker._process_analysis_item(analysis_item()) is None

        debug = only(caplog, logging.DEBUG, STARTED_FAILED_DEBUG.format("redis down"), where=1044)
        pin_extra(debug, "batch_id", BATCH, where=1044)
        only(caplog, logging.INFO, PROCESSING_INFO.format(BATCH), where=1026)
        assert levels(caplog) == {"DEBUG": 1, "INFO": 2}, levels(caplog)
        # The INFO trio belongs to g01's L1094 line; it is asserted here because this
        # leg pins the whole surface of a partially-failed item - the DEBUG arm must not
        # smuggle a field in or take one out of the line beside it.
        surface_extras(
            caplog,
            base,
            DEBUG={"batch_id"},
            INFO={"event_id", "risk_score", "items_processed"},
        )
        assert worker._analyzer.analyze_batch.await_count == 1, (
            "a best-effort publish failure must not skip analysis"
        )
        assert d.rec_exc.call_args_list == [], "the publish arm records no span exception"


async def test_a_worker_without_a_broadcaster_skips_both_publishes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The shipped gate at L1031/L1104: no broadcaster -> no publish, analysis completes.

    With the lazy getter genuinely unavailable - the shipped factory-failure state,
    where ``_get_broadcaster`` leaves ``_broadcaster`` at ``None`` (L829-L831) - BOTH
    NEM-3607 publishes must be skipped while the analysis still runs, the stats still
    advance and the telemetry still records.  This is the negative half of the gate the
    payload legs above pin positively, so ``m57`` (``broadcaster = None``) cannot be
    satisfied by an accidental ``None`` anywhere else in the battery.
    """
    worker = analysis_worker(broadcaster=None)
    with instrumentation() as d:
        win(caplog)
        assert await worker._process_analysis_item(analysis_item()) is None

        assert d.factory.await_count == 1, "the shipped lazy getter must consult the factory once"
        assert worker._analyzer.analyze_batch.await_count == 1, "the analysis must still run"
        assert calls_of(d.stage_latency) != [], "telemetry does not depend on the broadcaster"
        assert d.rec_error.call_args_list == [], (
            f"unexpected pipeline-error labels: {calls_of(d.rec_error)}"
        )

    assert worker.stats.items_processed == 1, worker.stats
    only(caplog, logging.INFO, PROCESSING_INFO.format(BATCH), where=1026)
