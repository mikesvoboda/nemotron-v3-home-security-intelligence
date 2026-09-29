"""S3 batch-28 lane 02 - ``pipeline_workers`` groups g02 + g10 kill battery (102 keys).

Module: ``backend/services/pipeline_workers.py`` (git blob 74649fd3 - byte-identical
to the manifest-proven source).  Admitted manifest: ``/tmp/wp-pw/pipeline_workers/``
``manifest.json`` group 2 ("g02 analysis_item: ValueError skip + generic-exception
paths and analysis_failed broadcasts", 56 KILLABLE / 0 EQUIVALENT) and group 10
("g10 DetectionQueueWorker._run_loop", 45 KILLABLE / 1 EQUIVALENT), plus
``group_2.keys`` / ``group_10.keys`` and ``survivors.json`` for the exact per-key diffs.

The one upheld EQUIVALENT of g10 is NOT claimed here and needs no test::

    xǁDetectionQueueWorkerǁ_run_loop__mutmut_3   L367  `... | None = None` -> `= ""`

    The declared value is overwritten at L371 in streams mode before the only read
    (L396), which short-circuits on ``use_streams`` in legacy mode - a dead value.

Production refs: ``_process_analysis_item`` L975-1183 (the two handlers at
L1128-1149 and L1150-1183), ``DetectionQueueWorker._run_loop`` L363-452.

Module: ``backend/services/pipeline_workers.py``.  Admitted manifest:
``/tmp/wp-pw/pipeline_workers/manifest.json`` group 2 ("g02 analysis_item: ValueError
skip + generic-exception paths and analysis_failed broadcasts", 56 KILLABLE / 0
EQUIVALENT) and group 10 ("g10 DetectionQueueWorker._run_loop", 45 KILLABLE / 1
EQUIVALENT), with ``group_2.keys`` / ``group_10.keys`` and ``survivors.json`` for the
exact per-key diffs.  The manifest was adjudicated against blob ``74649fd3``; this lane
runs blob ``b3965679`` (md5 ``d6e3c91fc85bfaea19f0d907491eefbf``), where both driven
bodies are still the shipped code line for line - only their file position moved.

Line numbering - read this before trusting a cite
==================================================
The bank (``survivors.json`` / ``manifest.md``) cites ``74649fd3`` numbers and the two
functions moved by DIFFERENT amounts, so the two halves of this file differ too:

* PART A cites (per-test docstrings AND the PART A map below) are ``74649fd3`` numbers;
  the lane blob sits ``+3`` lower down - bank L1130 ``record_exception(e)`` is lane
  ``pipeline_workers.py:1133``.
* PART B cites are LANE-BLOB numbers (bank number ``+1``): bank L385 ``claim_interval``
  is lane ``pipeline_workers.py:386``.

The replay splices every key from its ``before`` TEXT, never its line, so the shift is
absorbed; the cites here exist so a reader can open the shipped statement.

The one upheld EQUIVALENT of g10 is NOT claimed here and needs no test
======================================================================
``xǁDetectionQueueWorkerǁ_run_loop__mutmut_3`` - lane L368
``stream_service: DetectionStreamService | None = None`` -> ``= ""``.  The binding is
re-WRITTEN unconditionally at L372 on the only path that can read it truthy (L371
``if use_streams:`` gates both the write and any truthy ``use_streams`` reaching L397),
and on the falsy side L397 short-circuits on ``use_streams`` before the
``stream_service is not None`` conjunct - so the declared value is never observed and
``""`` is behaviourally identical to ``None`` at every reachable read.  No
shipped-behaviour assert separates them; reported uncovered-by-design, not faked.

Production refs (lane blob ``b3965679``)
========================================
``AnalysisQueueWorker._process_analysis_item`` L978-1186 - validation L992-1008, the
``log_context``/span scope L1013-1016, the ``batch.analysis_started`` broadcast
L1029-1047, ``analyze_batch`` + success bookkeeping L1049-1129, the ``except
ValueError`` arm L1131-1152, the ``except Exception`` arm L1153-1186.
``DetectionQueueWorker._run_loop`` L364-453.
Test -> mutant-key map
======================
PART A - ``AnalysisQueueWorker._process_analysis_item`` (56 keys, group 2)
  A1 ``test_a_validation_value_error_is_skipped_not_counted_as_an_error``
     m181 (L1130 ``record_exception(e)`` -> ``(None)``), m182 (L1131 WARNING -> ``None``)
  A2 ``test_the_validation_skip_broadcasts_the_validation_failure_payload``
     m183 (L1135-1143 payload -> ``None``), m184/m185 (``batch_id`` rename),
     m186/m187 (``camera_id`` KEY rename), m188/m189 (``or`` -> ``and`` / ``""`` -> ``"XXXX"``),
     m190/m191/m192 (``error`` KEY rename / ``str(None)``), m193/m194/m195/m196
     (``error_type`` KEY rename / value None / XX-wrap / upper), m197 (``retryable`` KEY rename)
  A3 ``test_a_missing_camera_id_broadcasts_the_empty_string_placeholder``
     m183, m184, m185, m189, m193-m197 (second, ``camera_id is None`` route)
  A4 ``test_the_generic_handler_counts_exactly_one_error_per_failure``
     m203 (``+=`` -> ``=``), m204 (``+=`` -> ``-=``), m205 (``+= 1`` -> ``+= 2``)
  A5 ``test_the_generic_handler_reports_the_shipped_metric_label_and_the_exception``
     m207/m208 (L1152 label XX-wrap / upper), m209 (L1153 ``record_exception(None)``)
  A6 ``test_the_generic_handler_logs_one_error_record_with_a_real_traceback``
     m210/m212 (L1154 message -> ``None`` / dropped), m211/m214 (L1156 ``exc_info``
     -> ``None`` / ``False``), m213 (L1156 ``exc_info`` argument dropped)
  A7 ``test_a_plain_runtime_error_broadcasts_the_processing_error_payload``
     m215-m228 (the whole L1162 ``categorize_exception(...).replace(...)`` family),
     m231-m242 (the L1169-1177 payload family) - SOLE route to m215..m228
  A8 ``test_a_timeout_error_broadcasts_a_retryable_timeout_error_payload``
     m215, m220-m225, m229 (``retryable`` -> ``None``), m230 (``in`` -> ``not in``), m231-m242
  A9 ``test_a_connection_error_broadcasts_a_retryable_connection_error_payload``
     the same retryable family, seen from ``connection_error``
  A10 ``test_a_redis_module_error_broadcasts_a_retryable_redis_error_payload``
     the same family from ``redis_error``; the third value set for the L1162 family
  A11 ``test_a_long_failure_message_is_truncated_to_500_characters``
     m241 (``[:500]`` -> ``[:501]``) - SOLE route; m237 (third route)
  A12 ``test_a_broadcast_rejection_is_debugged_and_never_escapes`` (3 params)
     m216, m217, m218, m219, m222, m223 (measured second route: the broken L1162
     raises ``TypeError`` inside the inner ``try`` and lands on this DEBUG)
  A13 ``test_the_generic_failure_without_a_broadcaster_stays_silent_about_broadcasts``
     control for the L1159 gate (kills nothing of its own - measured)
  A14 ``test_a_validation_failure_without_a_broadcaster_skips_the_broadcast_and_the_debug``
     control for the L1133 gate (kills nothing of its own - measured)
  A15 ``test_the_validation_and_generic_arms_never_touch_the_success_stats`` (2 params)
     control: both handlers leave ``items_processed`` / ``last_processed_at`` alone
  A16 ``test_a_validation_failure_never_broadcasts_a_completed_batch``
     control: the ``analysis_completed`` broadcast belongs to the success arm only


PART B - ``DetectionQueueWorker._run_loop`` (45 KILLABLE + 1 upheld EQUIVALENT)
Cites below are LANE-BLOB numbers (bank number + 1).
  B1 ``test_streams_mode_announces_the_consumer_and_consumes_one_blocking_message``
     m8/m10/m12 (L373-374 banner message -> ``None`` / dropped / ``"XX..XX"``),
     m9/m11/m15/m16 (L375 ``extra`` -> ``None`` / dropped / the two KEY renames),
     m4/m5 (L369 ``consumer_name`` -> ``None`` / ``id(None)``), m7 (L372 factory
     argument -> ``None``), m34/m35/m37 (L411-413 ``consume_detections`` consumer
     -> ``None`` / ``count=None`` / dropped positional), m44 (L418 ``msg.raw_data``
     -> ``None``) and m45 (L419 ``acknowledge(msg.id)`` -> ``(None)``).
  B2 ``test_an_empty_streams_read_loops_again_without_processing_or_the_legacy_read``
     the ``if not messages: continue`` arm (L414-415 - no survivor sits there) plus the
     zero-clock claim gate; measured route to m4/m5 and m34/m35/m37.
  B3 ``test_the_claim_gate_fires_once_per_shipped_30_second_step``
     SOLE route to m25 (L386 ``claim_interval`` -> ``None``), m30 (L399 ``now`` ->
     ``None``), m31 (L400 ``-`` -> ``+``) and m32 (L400 ``>=`` -> ``>``).  A NON-ZERO
     clock baseline is what makes m31 observable at all.
  B4 ``test_a_stale_claimed_message_goes_to_the_dlq_or_is_reprocessed_and_acked``
     the L402-409 claimed-message arms (``should_move_to_dlq`` decides - no survivor
     sits there) + measured route to m25/m30/m31/m32 and m4/m5.
  B5 ``test_the_supervisor_heartbeat_beats_once_per_shipped_20_second_step``
     SOLE route to m21 (L381 ``last_heartbeat`` -> ``None``) and m22/m23 (L382
     ``heartbeat_interval`` -> ``None`` / ``21.0``); second route to m27.
  B6 ``test_the_supervisor_gate_never_runs_and_never_reads_the_clock_without_one``
     measured second route to m21 and m27 - the flipped gate reads the clock the
     shipped body never reads here, and the READ COUNT is the observable.
  B7 ``test_a_stream_capable_worker_without_a_stream_service_object_stays_legacy``
     SOLE route to m6 (L372 service -> ``None``) and m28 (L397 ``and`` -> ``or``);
     second route to m29 (L397 ``is not None`` -> ``is None``).
  B8 ``test_the_legacy_read_uses_the_worker_s_own_queue_and_poll_timeout``
     SOLE route to m17/m20 (L378 legacy banner -> ``None`` / upper), m46 (L422 the
     whole read -> ``item = None``), m48 (L424 ``timeout=None``), m49 (L423 queue-name
     argument dropped), m50 (L424 ``timeout`` argument dropped) and m53 (L430
     ``_process_detection_item(item)`` -> ``(None)``); second route to m51.
  B9 ``test_a_second_idle_legacy_read_loops_again_without_processing_or_leaving``
     SOLE route to m51 (L427 ``is None`` -> ``is not None``) and m52 (L428
     ``continue`` -> ``break``) - two consecutive idle passes are where shipped, the
     flip and the ``break`` take three different routes.
  B10 ``test_a_cancelled_pass_logs_the_cancelled_info_and_still_logs_the_exit_info``
     SOLE route to m54/m56/m57 (L433 cancelled message -> ``None`` / lower / upper)
     and m58 (L434 ``break`` -> ``return``, which skips the trailing exit INFO).
  B11 ``test_a_connection_failure_counts_one_error_logs_a_traceback_and_sleeps``
     SOLE route to m60 (L436 ``+=`` -> ``-=``), m62 (L437 ``state`` -> ``None``, read
     INSIDE the L440 ``record_pipeline_error`` window) and m63/m64/m65 (L439
     ``error_type`` -> ``None`` / ``categorize_exception(None, ...)`` / ``..., None)``);
     the FIRST-failure ``error_count`` is what kills m61 (``+= 2``).
  B12 ``test_the_loop_survives_two_connection_failures_and_reports_a_running_state``
     the ``+= 1`` accumulation across two failures (second measured route to
     m60/m61/m62/m63/m64/m65).
  B13 ``test_a_failed_streams_pass_reads_the_stream_again_on_the_next_iteration``
     control (measured: it kills nothing of its own - no survivor sits on the streams
     error arm's re-loop): a failed streams pass must not leave the loop, must not fall
     into the legacy read, and must leave the claim gate shut.

Measured result
---------------
Every key is replayed from its OWN survivor diff in a symlink shadow of this tree
(``replay_lib.py prove``: all occurrence-twins spliced, a key counted KILLED only when
EVERY candidate reddens a NAMED test and the pristine battery is green).  Counts and
per-key occurrence verdicts: ``/tmp/wp-pw/pipeline_workers/replay_g02g10.json``.  The
pristine battery is green serially (``-p no:randomly``) and under the repo's default
xdist + randomly addopts.

Shipped behaviour only - nothing here invents a contract.  Every pinned string is
transcribed from the shipped file at the line quoted in the test that asserts it, and
every value an assertion depends on is injected by this file (the exception, the
broadcast double, the queue name, the poll timeout, the clock script, the stream
messages, the supervisor).

Discipline
----------
* Log assertions use ``caplog`` opened per window (``set_level`` + ``clear()``, then
  filtered to this module's logger name) and read the RAW ``record.msg`` plus
  ``record.args`` / ``record.exc_info`` / ``record.levelno`` (batch27_01 pattern).
  ``record.exc_info`` is asserted ``None`` ONLY where the shipped call passes no
  ``exc_info`` argument - stdlib ``Logger._log`` guards every resolution behind
  ``if exc_info:``, so a falsy argument leaves the field ``None`` too.  The two sites
  that DO pass ``exc_info=True`` (the generic analysis ERROR at L1157-1160 and the
  loop ERROR at L441-445) are pinned with ``shipped_exc_info=True`` and their
  traceback is read by IDENTITY.  ``extra=`` payloads are recovered as "record
  attributes beyond the ``LogRecord`` core plus this module's ``ContextFilter``
  contributions" (g13's measured ``BASELINE_ATTRS``), which is how ``extra=None``, the
  dropped ``extra`` and the KEY renames become visible; inside the analysis scope the
  shipped ``log_context`` (L1013-1016) additionally merges ``camera_id`` /
  ``operation`` into every record, and the no-broadcaster controls pin that injection.
* Mocks of real attributes are autospec'd (WP4.2 fast path) - every ``patch`` of a
  ``backend.core.metrics`` / ``backend.core.telemetry`` re-export, of ``get_settings``,
  of ``get_detection_stream_service``, of ``record_pipeline_error`` and of
  ``asyncio.sleep`` is ``autospec=True`` or an ``autospec_of`` double installed with
  ``new=``; the stream service / supervisor / Redis client doubles come from
  ``create_autospec(...)``; the process-item stand-ins and the scripted queue / stream
  readers are INSTANCE attributes (a replay mutant re-sources the class, so a
  class-level patch would sail past it).  ``asyncio.sleep`` is patched as an attribute
  of the ``asyncio`` module, which is the object the shipped
  ``await asyncio.sleep(1.0)`` resolves through.
* PART B's clock is the module-level ``time_module`` alias (L33, read at L381, L385,
  L392 and L399) installed through ``live_globals`` (three-worlds safe) as either
  ``ConstantTimeModule`` - one frozen value, so NEITHER gate opens, which is what
  keeps a consume/legacy leg owned by its own keys - or ``ScriptedTimeModule``, which
  answers read ``i`` from an explicit script and repeats its last value.  The shipped
  module attribute is never ``patch``-ed, no ``time.monotonic`` / ``time.perf_counter``
  read is touched and no wall-clock duration is asserted: only the READ COUNT, which is
  the observable that catches a removed read, an added read and both gate flips.
* Loop termination is structural, not lucky: each PART B drive ends on a sentinel pass
  whose read raises ``asyncio.CancelledError``, so the shipped ``break`` (L434) exits
  the loop.  The pass index advances on the loop's OWN read (L401 claim / L411 consume
  / L422 BLPOP), never on a sleep - the streams arm and the idle legacy pass do not
  sleep - so a mutant that iterates past the script gets a loud ``AssertionError``
  inside the shipped ``try`` instead of riding the ini ``timeout = 5``.  The bounded
  sleep spy backstops the runaway cases (a L397 gate flip makes
  ``None.consume_detections`` fail every iteration): it stops the loop after a fixed
  budget and the pins then reject that ERROR surface.
"""

from __future__ import annotations

import asyncio
import builtins
import contextlib
import logging
import time as real_time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, create_autospec, patch

import pytest

from backend.core.config import Settings
from backend.core.redis import RedisClient
from backend.services import pipeline_workers as M
from backend.services.pipeline_workers import (
    AnalysisQueueWorker,
    DetectionQueueWorker,
    WorkerStats,
)
from backend.services.redis_streams import DetectionStreamMessage, DetectionStreamService
from backend.services.worker_supervisor import WorkerSupervisor

LOG_NAME = M.logger.name  # "backend.services.pipeline_workers" (get_logger(__name__))
MOD = "backend.services.pipeline_workers"
# backend.services.event_broadcaster.get_broadcaster is the real attribute the shipped
# function-local import resolves to (pipeline_workers.py:826), so this is the patch
# target; the import happens per call, so the patch is observed in every world.
FACTORY = "backend.services.event_broadcaster.get_broadcaster"

pytestmark = [pytest.mark.unit]

# The real asyncio.sleep, captured at import time so PART B's injected stub can yield
# control to the driven loop without recursing into itself.
_REAL_SLEEP = asyncio.sleep

# The shipped ``except asyncio.CancelledError`` sentinel (L432) that ends every drive.
CANCEL = asyncio.CancelledError


# =============================================================================
# Shipped literals, transcribed from backend/services/pipeline_workers.py
# =============================================================================

# PART A - cites here are the bank's blob-74649fd3 numbers (lane blob = +3).
# bank L1134: logger.warning(f"Skipping batch: {e}")            -> lane 1134
SKIP_WARNING_TPL = "Skipping batch: {}"
# bank L1155: record_pipeline_error("analysis_batch_error")     -> lane 1155
ANALYSIS_BATCH_ERROR = "analysis_batch_error"
# bank L1157-1160: logger.error(f"Failed to analyze batch: {e}", exc_info=True)
ANALYZE_FAILED_TPL = "Failed to analyze batch: {}"
# bank L1150 / L1184: logger.debug(f"Failed to broadcast batch.analysis_failed: {e}")
BROADCAST_FAILED_TPL = "Failed to broadcast batch.analysis_failed: {}"
# bank L1176: "error": str(e)[:500]                              -> lane 1176
ERROR_TRUNCATION = 500

# PART B - cites here are LANE-BLOB numbers (bank number + 1).
# L373-376: logger.info("DetectionQueueWorker loop started (Redis Streams mode)", extra=)
STREAMS_BANNER = "DetectionQueueWorker loop started (Redis Streams mode)"
# L378: logger.info("DetectionQueueWorker loop started")
LEGACY_BANNER = "DetectionQueueWorker loop started"
# L433: logger.info("DetectionQueueWorker loop cancelled")
CANCELLED_INFO = "DetectionQueueWorker loop cancelled"
# L441-445: logger.error(f"Error in DetectionQueueWorker loop: {e}", exc_info=True, extra=)
LOOP_ERROR_TPL = "Error in DetectionQueueWorker loop: {}"
# L450-453: logger.info("DetectionQueueWorker loop exited", extra={"items_processed": ...})
EXIT_INFO = "DetectionQueueWorker loop exited"
# L382: heartbeat_interval = 20.0 / L386: claim_interval = 30.0
HEARTBEAT_INTERVAL = 20.0
CLAIM_INTERVAL = 30.0
# L447: await asyncio.sleep(1.0)  # brief delay before retrying
ERROR_RETRY_DELAY = 1.0
# L401: await stream_service.claim_stale_messages(consumer_name, count=5)
CLAIM_COUNT = 5
# L404: await stream_service.move_to_dlq(msg, "max_delivery_exceeded")
DLQ_REASON = "max_delivery_exceeded"
# The delivery threshold the DLQ verdict is scripted against (L403 asks the service).
DLQ_THRESHOLD = 3
# L439 categorize_exception(<ConnectionError>, "detection") -> the L157-167 name tuple
# fires first, so the shipped label is f"{worker_name}_connection_error".
ERROR_LABEL = "detection_connection_error"
# L439 categorize_exception(<RuntimeError>, "detection") matches no tuple, no isinstance
# arm and no "redis" module substring, so it falls to the L190 default
# f"{worker_name}_processing_error" - the SECOND value the shipped label can take, which
# B13 pins so the label provably comes from the categorizer and not from a constant.
PROCESSING_LABEL = "detection_processing_error"
# WorkerState values as the shipped WorkerStats.to_dict() renders them (L212-219); a
# fresh WorkerStats starts STOPPED (L210).
STATE_STOPPED = "stopped"
STATE_RUNNING = "running"
STATE_ERROR = "error"
# Values injected by this file (never shipped values), so an argument mutation cannot
# alias a shipped default: PART B's queue name / poll timeout are this file's own, and
# PART A's batch / camera ids are the payload the shipped validator accepts.
BATCH_ID = "batch-9f3c-0001"
CAMERA_ID = "front_door"
PASS_CEILING = 40  # harness guard, far above any shipped count
# PART B's sleep budget: no shipped drive sleeps more than once or twice, and a mutant
# that sleeps past this is stopped rather than left to ride the ini timeout = 5.
SLEEP_LIMIT = 6


# =============================================================================
# Observation helpers (batch27_01 + g13 pattern)
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


def pin_record(r: logging.LogRecord, *, msg: str, level: int) -> None:
    """Assert the observable surface of one shipped f-string log call.

    ``record.msg`` is the RAW message.  Every shipped site claimed here is an
    already-interpolated f-string or a constant, so ``args`` must stay empty (a moved
    or dropped message argument lands IN ``msg``).
    """
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args for an f-string message: {r.args!r}"


def pin_no_exc_info(r: logging.LogRecord) -> None:
    # The shipped calls behind the WARNING/DEBUG surfaces (lines 1132, 1148, 1182,
    # 831) pass NO exc_info argument, and stdlib logging leaves the field None
    # unless the call passes it truthy (logging/__init__.py Logger._log:
    # `if exc_info:` guards every resolution).  The generic-arm ERROR at line
    # 1158 DOES pass exc_info=True - that surface is pinned explicitly in
    # test_the_generic_handler_logs_one_error_record_with_a_real_traceback, so
    # this pin is applied only where the shipped call omits the argument.
    assert r.exc_info is None, (
        f"exc_info present where the shipped call passes none: {r.exc_info!r}"
    )


def only(
    caplog: pytest.LogCaptureFixture,
    level: int,
    msg: str,
    *,
    shipped_exc_info: bool = False,
) -> logging.LogRecord:
    """Exactly one record at ``level`` in the window, matching every field.

    ``shipped_exc_info=True`` is used ONLY for the generic-arm ERROR, whose
    shipped call (line 1158) passes ``exc_info=True``; every other surface in
    this file ships without the argument and is pinned via ``pin_no_exc_info``.
    """
    recs = at(caplog, level)
    assert len(recs) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record from {LOG_NAME}, "
        f"got {[(r.levelno, r.msg) for r in recs]}"
    )
    pin_record(recs[0], msg=msg, level=level)
    if shipped_exc_info:
        assert recs[0].exc_info is not None, "the shipped ERROR passes exc_info=True"
    else:
        pin_no_exc_info(recs[0])
    return recs[0]


def pin_levels(
    caplog: pytest.LogCaptureFixture,
    msgs: list[str],
    level: int,
    *,
    shipped_exc_info: bool = False,
) -> None:
    """Pin the ordered, complete surface of ONE level for a whole leg."""
    recs = at(caplog, level)
    name = logging.getLevelName(level)
    assert [r.msg for r in recs] == msgs, (
        f"{name} surface mutated: {[r.msg for r in recs]} != {msgs}"
    )
    for r, msg in zip(recs, msgs, strict=True):
        pin_record(r, msg=msg, level=level)
        if shipped_exc_info:
            assert r.exc_info is not None, "the shipped ERROR passes exc_info=True"
        else:
            pin_no_exc_info(r)


def _baseline_attrs() -> frozenset[str]:
    """Attribute names that are NOT part of a shipped ``extra=`` payload.

    The union of (a) the fields ``logging.LogRecord.__init__`` always sets and (b) the
    fields this module's ``ContextFilter`` injects, MEASURED (the filter is
    idempotent, so running it over a record it has already seen adds exactly the
    injected names once).  ``message`` is excluded - the formatter sets it.
    """
    probe = logging.LogRecord("baseline.probe", logging.DEBUG, "f", 1, "probe", (), None)
    core = set(probe.__dict__)
    injected = set(M.logger.filter(probe).__dict__) - core
    return frozenset(core | injected | {"message"})


BASELINE_ATTRS = _baseline_attrs()


def shipped_extra(record: logging.LogRecord) -> dict[str, Any]:
    """The ``extra=`` dict the shipped call passed, as the record shows it.

    ``Logger.makeRecord`` copies ``extra`` into the record verbatim, so removing the
    baseline leaves precisely the shipped payload - which is how ``extra=None``, the
    dropped ``extra`` argument and the renamed keys become visible.
    """
    return {k: v for k, v in record.__dict__.items() if k not in BASELINE_ATTRS}


def live_globals(fn: Any) -> dict[str, Any]:
    """Name-resolution dict of the LIVE function object (three-worlds safe).

    * Pristine repo / shadow replay: ``fn.__globals__ is M.__dict__`` (identity path).
    * ep_plugin red-check lane: the variant body is exec'd into a snapshot COPY of the
      module dict - that copy is exactly the dict the variant body reads.
    * ``mutants/`` re-bank home: mutmut wraps functions in its trampoline, whose
      ``__globals__`` is mutmut's own dict while the shipped body sits behind
      ``__wrapped__`` with globals == ``M.__dict__``.
    """
    g = fn.__globals__
    if g is not M.__dict__:
        w = getattr(fn, "__wrapped__", None)
        if w is not None and w.__globals__ is M.__dict__:
            return M.__dict__
    return g


def pin_payloads(
    caplog: pytest.LogCaptureFixture,
    level: int,
    payloads: list[dict[str, Any]],
) -> None:
    """Pin the ``extra=`` payload of EVERY record at ``level``, in order.

    A count mismatch is itself a kill: a dropped or added record changes the surface, and
    ``extra=None`` / a dropped ``extra`` / a renamed KEY changes the payload.
    """
    recs = at(caplog, level)
    assert len(recs) == len(payloads), (
        f"expected {len(payloads)} {logging.getLevelName(level)} records, got {len(recs)}: "
        f"{[r.msg for r in recs]}"
    )
    for r, payload in zip(recs, payloads, strict=True):
        assert shipped_extra(r) == payload, (
            f"extra payload mutated on {r.msg!r}: {shipped_extra(r)!r} != {payload!r}"
        )


# =============================================================================
# Crafted exception classes (module identity is load-bearing for categorize L185)
# =============================================================================


class RedisModuleFailure(Exception):
    """No tuple match; mixed-case module carrying a lowercase ``redis`` (L185)."""


RedisModuleFailure.__name__ = "RedisModuleFailure"
RedisModuleFailure.__module__ = "MyRedisPool.Client"


# =============================================================================
# PART A fixtures/harness: AnalysisQueueWorker._process_analysis_item
# =============================================================================


def analysis_worker(broadcaster: Any = None) -> Any:
    """AnalysisQueueWorker with an injected analyzer and optional broadcaster.

    Nothing real is constructed: ``analyzer`` is a MagicMock so the shipped
    ``analyzer or NemotronAnalyzer(...)`` arm never runs, and ``_broadcaster`` is
    pre-seeded so the shipped ``_get_broadcaster`` returns it without touching its
    factory (the broadcaster double is this file's object, never a patched real one).
    """
    worker = AnalysisQueueWorker(
        redis_client=MagicMock(name="redis-client"),
        analyzer=MagicMock(name="analyzer"),
    )
    worker._broadcaster = broadcaster
    return worker


def broadcaster_double() -> Any:
    """A stand-in broadcaster whose three analysis broadcasts resolve immediately.

    The shipped code only ever does ``await broadcaster.<name>({...})`` (L1030, L1110,
    L1135, L1169), so each method is an ``AsyncMock``: one await record per shipped
    call and the payload dict readable back out of ``await_args_list``.  The
    broadcaster itself is this file's own object - never a patched real attribute - so
    plain construction is the honest install, and the shipped ``_get_broadcaster``
    returns it unchanged because ``_broadcaster`` is pre-seeded.
    """
    broad = MagicMock(name="broadcaster")
    for name in (
        "broadcast_batch_analysis_started",
        "broadcast_batch_analysis_completed",
        "broadcast_batch_analysis_failed",
    ):
        setattr(broad, name, AsyncMock(name=name, return_value=1))
    return broad


def valid_item(camera_id: str | None = CAMERA_ID) -> dict[str, Any]:
    """A payload the shipped ``validate_analysis_payload`` accepts (L990).

    ``batch_id`` / ``camera_id`` satisfy the schema's length and pattern rules
    (backend/api/schemas/queue.py:141-152), so the function reaches the analysis
    ``try`` with both names bound - which is what the failure payloads read.
    """
    item: dict[str, Any] = {"batch_id": BATCH_ID, "detection_ids": [1, 2, 3]}
    if camera_id is not None:
        item["camera_id"] = camera_id
    return item


@dataclass
class Failures:
    """The shipped module-level call sites one analysis failure can reach."""

    record_exception: Any
    record_pipeline_error: Any
    record_stage_latency: Any
    record_pipeline_stage_latency: Any


async def drive_failure(
    worker: Any,
    item: dict[str, Any],
    side_effect: Any,
) -> Failures:
    """Run ``_process_analysis_item`` with ``analyze_batch`` failing (L1053).

    The telemetry / metrics re-exports the shipped handler calls are replaced by
    ``autospec=True`` doubles for the window only; ``record_stage_latency`` and
    ``record_pipeline_stage_latency`` are the success-arm sites, so a leg that stays
    red on them proves the failure never reached the success path.

    Nothing is injected for the logging scope: the shipped body itself enters
    ``log_context(batch_id=..., camera_id=..., operation="analysis")`` at lines
    1013-1014 and the shipped ``ContextFilter`` (attached to this module's logger
    by ``get_logger``, backend/core/logging.py:1128-1129) merges those values
    into every record the handlers emit - the ``shipped_extra`` pins account for
    that shipped injection (see ``shipped_context_attrs``).
    """
    worker._analyzer.analyze_batch = MagicMock(name="analyze_batch", side_effect=side_effect)
    with (
        patch(f"{MOD}.record_exception", autospec=True) as rec_exc,
        patch(f"{MOD}.record_pipeline_error", autospec=True) as rec_err,
        patch(f"{MOD}.record_stage_latency", autospec=True) as rec_stage,
        patch(f"{MOD}.record_pipeline_stage_latency", autospec=True) as rec_latency,
    ):
        await worker._process_analysis_item(item)
    return Failures(rec_exc, rec_err, rec_stage, rec_latency)


def failure_payload(broadcaster: Any, index: int = 0) -> dict[str, Any]:
    """The single ``broadcast_batch_analysis_failed`` payload dict at ``index``.

    The shipped call is ``await broadcaster.broadcast_batch_analysis_failed({...})``
    (L1135 / L1169) - one positional - so the payload is read back out of ``args`` and
    returned for EXACT dict comparison by the caller.
    """
    calls = broadcaster.broadcast_batch_analysis_failed.await_args_list
    assert len(calls) > index, f"only {len(calls)} failure broadcast(s) were sent"
    call = calls[index]
    assert len(call.args) == 1 and not call.kwargs, (
        f"the payload is passed as one positional dict: {call!r}"
    )
    payload = call.args[0]
    assert isinstance(payload, dict), f"payload must be a dict, got {payload!r}"
    return payload


def pin_failed_at(payload: dict[str, Any]) -> dict[str, Any]:
    """``failed_at`` is a shipped ``datetime.now(UTC).isoformat()`` string (base lines 1142/L1176).

    Delegates to ``pin_iso_stamp`` (defined with the A17 block, shared with
    ``started_at`` L1039 and ``completed_at`` L1121): the value is a wall-clock
    reading, so it cannot be pinned by equality; it IS pinned as a tz-aware
    ISO-8601 string, and then removed from the COPY we return so the caller can
    compare the remaining five keys with EXACT dict equality (the key-set pins keep
    ``failed_at`` itself under test).
    """
    return pin_iso_stamp(payload, "failed_at")


# =============================================================================
# A1) the ValueError arm: skip, not error (m181, m182)
# =============================================================================


async def test_a_validation_value_error_is_skipped_not_counted_as_an_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1128-1131 - the ValueError handler records the exception, warns, and stops.

    ::

        except ValueError as e:
            # Batch not found or no detections - log warning but don't count as error
            record_exception(e)
            logger.warning(f"Skipping batch: {e}")

    ``record_exception`` is an autospec spy of the shipped re-export, so m181's
    ``record_exception(None)`` shows up as an argument-identity failure, and m182's
    ``logger.warning(None)`` shows up in the RAW ``record.msg``.  The error counter and
    the ERROR-level surface are the "don't count as error" half of the comment, so both
    are pinned too (they are what separates this arm from the one below).
    """
    err = ValueError("batch not found")
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster)
    win(caplog)

    seen = await drive_failure(worker, valid_item(), err)

    only(caplog, logging.WARNING, SKIP_WARNING_TPL.format(err))
    assert at(caplog, logging.ERROR) == [], "the ValueError arm must not log ERROR"
    assert seen.record_exception.call_args_list == [((err,), {})], (
        f"record_exception contract mutated: {seen.record_exception.call_args_list!r}"
    )
    assert seen.record_exception.call_args.args[0] is err, (
        "the shipped call records the caught exception itself"
    )
    assert seen.record_pipeline_error.call_args_list == [], (
        "a skipped batch is not a pipeline error: the ValueError arm never increments"
    )
    assert worker._stats.errors == 0, f"errors counter mutated: {worker._stats.errors}"
    assert seen.record_stage_latency.await_args_list == [], (
        "the skip returns before the latency telemetry"
    )


# =============================================================================
# A2/A3) the validation-failure broadcast payload (m183-m197)
# =============================================================================

# The exact shipped key set (L1136-1143); compared as a SET so every rename, the
# dropped ``retryable`` KEY and a None payload are all visible at once.
FAILED_KEYS = {"batch_id", "camera_id", "error", "error_type", "retryable", "failed_at"}


async def test_the_validation_skip_broadcasts_the_validation_failure_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1133-1144 - one ``batch.analysis_failed`` broadcast, payload pinned exactly.

    ::

        if broadcaster:
            try:
                await broadcaster.broadcast_batch_analysis_failed(
                    {
                        "batch_id": batch_id,
                        "camera_id": camera_id or "",
                        "error": str(e),
                        "error_type": "validation",
                        "retryable": False,
                        "failed_at": datetime.now(UTC).isoformat(),
                    }
                )

    The payload is read back out of the broadcast call and compared with EXACT dict
    equality after ``failed_at`` is validated, so all fifteen key/value mutants
    (m184-m197) and the whole-payload ``None`` (m183) each break this pin.  Two of them
    need a second look: ``camera_id`` is the injected truthy ``"front_door"`` here, so
    m188's ``camera_id and ""`` yields ``""`` and fails the pin, while m189's
    ``camera_id or "XXXX"`` still yields ``"front_door"`` and can only be caught from
    the falsy side - which is exactly what the leg below provides.
    """
    err = ValueError("batch not found")
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster)
    win(caplog)

    await drive_failure(worker, valid_item(camera_id=CAMERA_ID), err)

    payload = dict(failure_payload(broadcaster))
    rest = pin_failed_at(payload)
    assert rest == {
        "batch_id": BATCH_ID,
        "camera_id": CAMERA_ID,
        "error": "batch not found",
        "error_type": "validation",
        "retryable": False,
    }, f"validation-failure payload mutated: {payload!r}"
    # The KEY set is pinned independently so a rename names itself.
    assert set(failure_payload(broadcaster)) == FAILED_KEYS
    sent = broadcaster.broadcast_batch_analysis_failed.await_args_list
    assert len(sent) == 1, f"expected exactly 1 failure broadcast, got {len(sent)}"
    pin_levels(caplog, [SKIP_WARNING_TPL.format(err)], logging.WARNING)
    pin_levels(caplog, [], logging.DEBUG)


async def test_a_missing_camera_id_broadcasts_the_empty_string_placeholder(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1138 - ``"camera_id": camera_id or ""`` with a ``None`` camera.

    The payload key stays present and its value becomes the empty string: m188's
    ``camera_id and ""`` yields ``None and ""`` -> ``None`` (not ``""``) and m189's
    ``camera_id or "XXXX"`` yields ``"XXXX"``, so this leg - where ``camera_id`` IS
    falsy - is the leg that reads the ``or`` from the other side.  The second value set
    (``error_type``/``retryable`` unchanged, different message) restates the KEY set.
    """
    err = ValueError("no detections for this batch")
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster)
    win(caplog)

    await drive_failure(worker, valid_item(camera_id=None), err)

    payload = dict(failure_payload(broadcaster))
    rest = pin_failed_at(payload)
    assert rest == {
        "batch_id": BATCH_ID,
        "camera_id": "",
        "error": "no detections for this batch",
        "error_type": "validation",
        "retryable": False,
    }, f"validation-failure payload mutated: {payload!r}"
    assert set(failure_payload(broadcaster)) == FAILED_KEYS
    sent = broadcaster.broadcast_batch_analysis_failed.await_args_list
    assert len(sent) == 1, f"expected exactly 1 failure broadcast, got {len(sent)}"
    pin_levels(caplog, [SKIP_WARNING_TPL.format(err)], logging.WARNING)


# =============================================================================
# A4-A6) the generic-Exception handler: counter, metric, record, ERROR log
# =============================================================================


async def test_the_generic_handler_counts_exactly_one_error_per_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1150-1151 - ``self._stats.errors += 1`` on every generic failure.

    Two calls, counted from the shipped default ``WorkerStats.errors = 0``: 1 then 2.
    ``= 1`` (m203) can only produce 1-then-1 and ``+= 2`` (m205) only 2-then-4, so the
    second pin kills both as well as ``-= 1`` (m204, which gives -1 then -2).
    """
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster)
    assert worker._stats.errors == 0, "WorkerStats starts at zero errors (L207)"
    win(caplog)

    await drive_failure(worker, valid_item(), RuntimeError("first boom"))
    assert worker._stats.errors == 1, f"first failure counted {worker._stats.errors} errors"
    await drive_failure(worker, valid_item(), RuntimeError("second boom"))
    assert worker._stats.errors == 2, (
        f"the counter must accumulate +1 per failure, got {worker._stats.errors}"
    )
    assert len(broadcaster.broadcast_batch_analysis_failed.await_args_list) == 2
    assert at(caplog, logging.WARNING) == [], "the generic arm warns nothing"


async def test_the_generic_handler_reports_the_shipped_metric_label_and_the_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1152-1153 - ``record_pipeline_error("analysis_batch_error")`` + ``record_exception(e)``.

    Both names are ``from backend.core.metrics/telemetry import`` re-exports the shipped
    module holds directly, so the patch lands on the binding the handler resolves
    through.  The label is pinned character-for-character (m207's XX-wrap and m208's
    upper-case rewrite both fail it) and the exception by IDENTITY (m209's ``None``).
    """
    err = RuntimeError("model refused the batch")
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster)
    win(caplog)

    seen = await drive_failure(worker, valid_item(), err)

    assert seen.record_pipeline_error.call_args_list == [((ANALYSIS_BATCH_ERROR,), {})], (
        f"metric label mutated: {seen.record_pipeline_error.call_args_list!r}"
    )
    assert seen.record_exception.call_args_list == [((err,), {})], (
        f"record_exception contract mutated: {seen.record_exception.call_args_list!r}"
    )
    assert seen.record_exception.call_args.args[0] is err
    assert worker._stats.items_processed == 0, "a failed analysis processes nothing"


async def test_the_generic_handler_logs_one_error_record_with_a_real_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1154-1157 - exactly one ERROR record, message + ``exc_info=True``.

    ::

        logger.error(
            f"Failed to analyze batch: {e}",
            exc_info=True,
        )

    ``record.msg`` kills the ``None`` (m210) and the dropped message (m212, which makes
    the call raise ``TypeError: logger.error() missing 1 required positional argument``
    out of the handler).  ``record.exc_info`` kills m211 (``exc_info=None``) and m214
    (``exc_info=False``) - logging treats a falsy ``exc_info`` as "no traceback" - and
    m213 (the argument dropped, which also lands on falsy).  The exception object
    inside ``exc_info`` is pinned by identity.
    """
    err = RuntimeError("gpu went away")
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster)
    win(caplog)

    await drive_failure(worker, valid_item(), err)

    rec = only(caplog, logging.ERROR, ANALYZE_FAILED_TPL.format(err), shipped_exc_info=True)
    assert rec.exc_info is not None, "the shipped call passes exc_info=True"
    assert rec.exc_info[1] is err, f"traceback carries the wrong exception: {rec.exc_info!r}"
    pin_levels(caplog, [], logging.WARNING)
    pin_levels(caplog, [], logging.DEBUG)


# =============================================================================
# A7-A11) the analysis_failed payload for generic errors (m215-m242)
# =============================================================================


async def test_a_plain_runtime_error_broadcasts_the_processing_error_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1159-1178 - ``error_type`` from L1162, ``retryable`` from L1164-1168.

    ::

        error_type = categorize_exception(e, "analysis").replace("analysis_", "")
        retryable = error_type in ("timeout_error", "connection_error", "redis_error")
        await broadcaster.broadcast_batch_analysis_failed(
            {"batch_id": batch_id, "camera_id": camera_id or "", "error": str(e)[:500],
             "error_type": error_type, "retryable": retryable,
             "failed_at": datetime.now(UTC).isoformat()}
        )

    A plain ``RuntimeError`` with a truthy camera categorises to
    ``"analysis_processing_error"``, so shipped sends ``error_type="processing_error"``
    and ``retryable=False``.  Every L1162 mutant is measured HERE because this is the
    only leg whose shipped run reaches the broadcast with a value that distinguishes
    the whole ``replace(...)`` / ``categorize_exception(...)`` family from the shipped
    string: ``error_type = None`` (m215), the four broken ``.replace`` call forms
    (m216-m219, which raise ``TypeError`` and are also caught by leg A12), the four
    broken ``categorize_exception`` call forms (m220-m223), the two worker-name
    rewrites (m224/m225, which relabel to ``XXanalysisXX_...`` / ``ANALYSIS_...``) and
    the two replace-needle rewrites (m226/m227, which leave the ``analysis_`` prefix
    on) plus the replacement rewrite (m228, ``XXXXprocessing_error``).  The payload KEY
    family (m231-m242) is pinned by exact dict equality plus an independent key-set
    check, and ``camera_id`` is truthy here so m236's ``camera_id and ""`` -> ``""`` is
    visible.  ``error`` is ``str(e)`` un-truncated (short message, m240/m241 pinned
    against the exact text).
    """
    err = RuntimeError("inference failed on frame 7")
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster)
    win(caplog)

    await drive_failure(worker, valid_item(camera_id=CAMERA_ID), err)

    raw = failure_payload(broadcaster)
    payload = dict(raw)
    rest = pin_failed_at(payload)
    assert rest == {
        "batch_id": BATCH_ID,
        "camera_id": CAMERA_ID,
        "error": "inference failed on frame 7",
        "error_type": "processing_error",
        "retryable": False,
    }, f"generic-failure payload mutated: {payload!r}"
    pin_levels(caplog, [ANALYZE_FAILED_TPL.format(err)], logging.ERROR, shipped_exc_info=True)
    pin_levels(caplog, [], logging.DEBUG)


async def test_a_timeout_error_broadcasts_a_retryable_timeout_error_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1164-1168 - ``timeout_error`` IS in the retryable tuple -> ``True``.

    ``builtins.TimeoutError`` categorises to ``analysis_timeout_error`` (L169), so
    shipped sends ``error_type="timeout_error"`` with ``retryable=True``.  ``retryable =
    None`` (m229) fails the value pin and ``in`` -> ``not in`` (m230) flips it to False;
    the same two mutants also break the two legs below, whose families are the other
    two tuple members - the three legs together leave neither a passing input.
    """
    err = builtins.TimeoutError("analyze_batch exceeded its deadline")
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster)
    win(caplog)

    await drive_failure(worker, valid_item(camera_id=CAMERA_ID), err)

    raw = failure_payload(broadcaster)
    payload = dict(raw)
    rest = pin_failed_at(payload)
    assert rest == {
        "batch_id": BATCH_ID,
        "camera_id": CAMERA_ID,
        "error": "analyze_batch exceeded its deadline",
        "error_type": "timeout_error",
        "retryable": True,
    }, f"timeout payload mutated: {payload!r}"
    pin_levels(caplog, [ANALYZE_FAILED_TPL.format(err)], logging.ERROR, shipped_exc_info=True)


async def test_a_generic_failure_without_a_camera_broadcasts_the_empty_string_placeholder(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped base line 1172 - ``"camera_id": camera_id or ""`` with a ``None`` camera.

    The generic-arm twin of the validation-arm leg above: every other generic leg
    injects a TRUTHY camera, so ``camera_id or "XXXX"`` (m237) still yields the
    camera there and is only distinguishable from the shipped ``or ""`` from the
    falsy side - which is exactly what this leg provides: shipped sends ``""``,
    m237 sends ``"XXXX"``.  ``camera_id and ""`` (m236) yields ``None`` on this
    input too, and the full exact-dict pin re-reads the whole L1170-1175 family
    from the second value set.
    """
    err = RuntimeError("model node unreachable")
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster)
    win(caplog)

    await drive_failure(worker, valid_item(camera_id=None), err)

    raw = failure_payload(broadcaster)
    payload = dict(raw)
    rest = pin_failed_at(payload)
    assert rest == {
        "batch_id": BATCH_ID,
        "camera_id": "",
        "error": "model node unreachable",
        "error_type": "processing_error",
        "retryable": False,
    }, f"no-camera generic payload mutated: {payload!r}"
    pin_levels(caplog, [ANALYZE_FAILED_TPL.format(err)], logging.ERROR, shipped_exc_info=True)


async def test_a_connection_error_broadcasts_a_retryable_connection_error_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Second retryable family: ``ConnectionError`` -> ``connection_error`` / ``True``.

    The name is the first member of the shipped connection tuple (L156-162), so
    ``categorize_exception`` returns ``analysis_connection_error`` and the payload
    carries the stripped family.  Distinct camera/batch values are not needed (the
    payload is fully pinned from the same injected item), but the distinct MESSAGE makes
    an accidental fall-through to another leg's expectation impossible.
    """
    err = builtins.ConnectionError("redis connection reset by peer")
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster)
    win(caplog)

    await drive_failure(worker, valid_item(camera_id=CAMERA_ID), err)

    raw = failure_payload(broadcaster)
    payload = dict(raw)
    rest = pin_failed_at(payload)
    assert rest == {
        "batch_id": BATCH_ID,
        "camera_id": CAMERA_ID,
        "error": "redis connection reset by peer",
        "error_type": "connection_error",
        "retryable": True,
    }, f"connection payload mutated: {payload!r}"
    pin_levels(caplog, [ANALYZE_FAILED_TPL.format(err)], logging.ERROR, shipped_exc_info=True)


async def test_a_redis_module_error_broadcasts_a_retryable_redis_error_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Third retryable family: a ``redis``-flavoured MODULE -> ``redis_error`` / ``True``.

    ``RedisModuleFailure.__module__`` is the mixed-case ``"MyRedisPool.Client"``, which
    L185 lower-cases and substring-matches, so shipped sends ``error_type="redis_error"``
    and ``retryable=True``.  This is also the third value set for the L1162 family:
    m226's padded needle and m227's upper-case needle both fail to strip the
    ``analysis_`` prefix here, and m228's ``"XXXX"`` replacement yields
    ``XXXXredis_error``.
    """
    err = RedisModuleFailure("cluster slot migration in progress")
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster)
    win(caplog)

    await drive_failure(worker, valid_item(camera_id=CAMERA_ID), err)

    raw = failure_payload(broadcaster)
    payload = dict(raw)
    rest = pin_failed_at(payload)
    assert rest == {
        "batch_id": BATCH_ID,
        "camera_id": CAMERA_ID,
        "error": "cluster slot migration in progress",
        "error_type": "redis_error",
        "retryable": True,
    }, f"redis payload mutated: {payload!r}"
    pin_levels(caplog, [ANALYZE_FAILED_TPL.format(err)], logging.ERROR, shipped_exc_info=True)


async def test_a_long_failure_message_is_truncated_to_500_characters(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1173 - ``"error": str(e)[:500]  # Truncate long error messages``.

    A 600-character message is the only input on which ``[:500]`` and ``[:501]`` differ,
    so the length pin (exactly the shipped 500) is the SOLE route to m241, and the
    exact-text pin (the first 500 characters of this file's own 600-char message) is
    what makes ``str(None)`` (m240 -> ``"None"``) impossible.  The ERROR record keeps
    the FULL message - truncation happens in the payload only - which is pinned too.
    """
    long_message = "Z" * 600
    err = RuntimeError(long_message)
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster)
    win(caplog)

    await drive_failure(worker, valid_item(camera_id=CAMERA_ID), err)

    raw = failure_payload(broadcaster)
    payload = dict(raw)
    pin_failed_at(payload)
    assert len(payload["error"]) == ERROR_TRUNCATION, (
        f"the payload error must be truncated to {ERROR_TRUNCATION} chars, "
        f"got {len(payload['error'])}"
    )
    assert payload["error"] == long_message[:ERROR_TRUNCATION]
    assert payload["error_type"] == "processing_error"
    assert payload["retryable"] is False
    assert payload["batch_id"] == BATCH_ID
    assert payload["camera_id"] == CAMERA_ID
    assert set(raw) == FAILED_KEYS
    # The log line keeps the whole message: only the broadcast payload is truncated.
    assert only(
        caplog, logging.ERROR, ANALYZE_FAILED_TPL.format(long_message), shipped_exc_info=True
    ).msg.endswith(long_message)


# =============================================================================
# A12-A14) the broadcast-failure DEBUG arm and the two broadcaster gates
# =============================================================================


@pytest.mark.parametrize(
    "err",
    [
        RuntimeError("analyzer exploded"),
        builtins.TimeoutError("analyze_batch deadline"),
        ValueError("batch has no detections"),
    ],
    ids=["generic", "timeout", "validation"],
)
async def test_a_broadcast_rejection_is_debugged_and_never_escapes(
    err: Exception,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1145-1149 / 1179-1183 - a rejected broadcast becomes one DEBUG.

    ::

        except Exception as broadcast_err:
            logger.debug(
                f"Failed to broadcast batch.analysis_failed: {broadcast_err}",
                extra={"batch_id": batch_id},
            )

    Both handlers are covered (``ValueError`` takes the validation arm, the others the
    generic arm), so the DEBUG text and its ``extra`` payload are pinned for each.  The
    leg is also the measured second route to the six L1162 mutants whose shipped-call
    form breaks (m216/m217/m218/m219/m222/m223): under those mutants the
    ``TypeError``/``NameError`` raised while building ``error_type`` is caught by THIS
    handler, so the DEBUG fires and the ERROR payload broadcast never happens - which
    the DEBUG text plus the shipped DEBUG-level count below reject.
    """
    rejection = builtins.ConnectionError("websocket emitter unreachable")
    broadcaster = broadcaster_double()
    broadcaster.broadcast_batch_analysis_failed = AsyncMock(
        name="broadcast_batch_analysis_failed", side_effect=rejection
    )
    worker = analysis_worker(broadcaster)
    win(caplog)

    await drive_failure(worker, valid_item(camera_id=CAMERA_ID), err)

    rec = only(caplog, logging.DEBUG, BROADCAST_FAILED_TPL.format(rejection))
    # The shipped call passes extra={"batch_id": batch_id} (base lines 1147-1148 /
    # 1181-1182); the shipped ContextFilter (backend/core/logging.py:571-577, on
    # this module's logger via get_logger at 1128-1129) then merges the shipped
    # log_context of lines 1013-1014 - camera_id + operation - into the record
    # because the shipped call did not set those keys.  Both are shipped output.
    assert shipped_extra(rec) == {
        "batch_id": BATCH_ID,
        "camera_id": CAMERA_ID,
        "operation": "analysis",
    }, f"DEBUG extra mutated: {shipped_extra(rec)!r}"
    assert broadcaster.broadcast_batch_analysis_failed.await_count == 1, (
        "the broadcast is attempted exactly once - the handler never retries"
    )
    # The rejection is swallowed: the arm's own log is unchanged (a WARNING for the
    # skip, an ERROR for a generic failure) and nothing else reaches WARNING.
    if isinstance(err, ValueError):
        pin_levels(caplog, [SKIP_WARNING_TPL.format(err)], logging.WARNING)
        pin_levels(caplog, [], logging.ERROR)
    else:
        pin_levels(caplog, [], logging.WARNING)
        pin_levels(caplog, [ANALYZE_FAILED_TPL.format(err)], logging.ERROR, shipped_exc_info=True)


async def test_the_generic_failure_without_a_broadcaster_stays_silent_about_broadcasts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1159 - ``if broadcaster:`` gates the generic-arm broadcast.

    Control leg (measured: it kills nothing of its own, because no survivor sits on
    L1159).  Stated so leg A7's payload pin cannot be satisfied by an accidental
    always-broadcast: with ``_broadcaster`` ``None`` the shipped code sends NOTHING and
    logs no DEBUG, while the counter, the metric and the ERROR record are unchanged.
    """
    err = RuntimeError("analyzer unavailable")
    broadcaster = broadcaster_double()
    worker = analysis_worker(None)
    worker._analyzer.analyze_batch = MagicMock(name="analyze_batch", side_effect=err)
    win(caplog)

    with (
        # the shipped _get_broadcaster (base lines 826-831) awaits the factory;
        # a None-returning double keeps the shipped ``if broadcaster:`` gate
        # closed WITHOUT the real factory's await-error DEBUG (base line 831),
        # so the "no DEBUG" pin below tests the GATE, not the factory.
        patch(FACTORY, new=AsyncMock(name="get_broadcaster", return_value=None)),
        patch(f"{MOD}.record_pipeline_error", autospec=True) as rec_err,
    ):
        await worker._process_analysis_item(valid_item(camera_id=CAMERA_ID))

    assert broadcaster.broadcast_batch_analysis_failed.await_count == 0, (
        "a worker with no broadcaster must not attempt a broadcast"
    )
    assert worker._stats.errors == 1
    assert rec_err.call_args_list == [((ANALYSIS_BATCH_ERROR,), {})]
    pin_levels(caplog, [ANALYZE_FAILED_TPL.format(err)], logging.ERROR, shipped_exc_info=True)
    pin_levels(caplog, [], logging.DEBUG)


async def test_a_validation_failure_without_a_broadcaster_skips_the_broadcast_and_the_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1133 - the same gate on the validation arm: WARNING only, no DEBUG.

    Second control leg (measured: kills nothing of its own).  With the gate open the
    ValueError arm performs exactly one observable - the ``Skipping batch`` WARNING -
    which is what separates it from every other arm in this handler.
    """
    err = ValueError("batch not found")
    worker = analysis_worker(None)
    worker._analyzer.analyze_batch = MagicMock(name="analyze_batch", side_effect=err)
    win(caplog)

    with (
        # shipped gate stays closed WITHOUT the factory await-error DEBUG
        # (base lines 826-831) - see the note in the leg above.
        patch(FACTORY, new=AsyncMock(name="get_broadcaster", return_value=None)),
        patch(f"{MOD}.record_exception", autospec=True) as rec_exc,
        patch(f"{MOD}.record_pipeline_error", autospec=True) as rec_err,
    ):
        await worker._process_analysis_item(valid_item())

    assert rec_exception_only_none(rec_exc) is False, "the skip still records the exception"
    assert rec_exc.call_args.args[0] is err
    assert rec_err.call_args_list == [], "the ValueError arm never counts a pipeline error"
    assert worker._stats.errors == 0
    pin_levels(caplog, [SKIP_WARNING_TPL.format(err)], logging.WARNING)
    pin_levels(caplog, [], logging.DEBUG)
    pin_levels(caplog, [], logging.ERROR)


def rec_exception_only_none(rec_exc: Any) -> bool:
    """True only if the spy recorded a lone ``None`` argument (m181's signature)."""
    calls = rec_exc.call_args_list
    return len(calls) == 1 and calls[0].args == (None,)


# =============================================================================
# A15/A16) success-arm isolation controls
# =============================================================================


@pytest.mark.parametrize(
    "err",
    [ValueError("batch not found"), RuntimeError("analyzer exploded")],
    ids=["validation-arm", "generic-arm"],
)
async def test_the_validation_and_generic_arms_never_touch_the_success_stats(
    err: Exception,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Control: neither handler touches ``items_processed`` / ``last_processed_at``.

    Both handlers sit after the success bookkeeping at L1055-1056, so a leg that ended
    in the success arm would show ``items_processed == 1`` and a non-``None``
    ``last_processed_at``.  Pinning them at the shipped defaults (L206-208) is what
    makes the payload legs above impossible to satisfy by falling through the ``try``.
    """
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster)
    win(caplog)

    seen = await drive_failure(worker, valid_item(camera_id=CAMERA_ID), err)

    assert worker._stats.items_processed == 0
    assert worker._stats.last_processed_at is None, (
        f"last_processed_at is only stamped on success, got {worker._stats.last_processed_at!r}"
    )
    assert seen.record_stage_latency.await_args_list == []
    assert seen.record_pipeline_stage_latency.call_args_list == []
    assert broadcaster.broadcast_batch_analysis_completed.await_args_list == []


async def test_a_validation_failure_never_broadcasts_a_completed_batch(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Control: ``batch.analysis_completed`` is the success arm's broadcast alone.

    The started/completed pair (L1030 / L1110) never runs for a failure, so the ONLY
    broadcast a skipped batch sends is the ``analysis_failed`` one pinned in A2/A3 -
    the ``await_count`` pair below states that split explicitly.
    """
    err = ValueError("batch not found")
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster)
    win(caplog)

    await drive_failure(worker, valid_item(), err)

    assert broadcaster.broadcast_batch_analysis_failed.await_count == 1
    # shipped lines 1031-1034: a truthy broadcaster DOES broadcast
    # analysis_started BEFORE analyze_batch, exactly once, on every leg.
    assert broadcaster.broadcast_batch_analysis_started.await_count == 1, (
        "analysis_started is broadcast once, before analyze_batch, before the failure"
    )
    # batch.analysis_completed is the success arm's broadcast ONLY (base lines
    # 1105-1111) - a skipped batch must never reach it.
    assert broadcaster.broadcast_batch_analysis_completed.await_count == 0
    pin_levels(caplog, [SKIP_WARNING_TPL.format(err)], logging.WARNING)


# =============================================================================
# A17-A21) the THREE SUCCESS-PATH SITES and the payload-validation arm that the
#          occurrence twins of m184-m192 / m203-m205 / m232-m237 are text-bound to
# =============================================================================
#
# ``mutmut`` groups occurrence-twins by TEXT, not by role, and the g02 statements
# ``"batch_id": batch_id,`` (m184/m185 in the validation payload, m232/m233 in the
# generic payload) and ``"camera_id": camera_id or "",`` (m186-m189 / m234-m237)
# occur verbatim at THREE FURTHER shipped sites, all of them on the SUCCESS path:
#
#   * the span-attribute dict ``span_attrs`` - L1019 (``"batch_id"`` only);
#   * the ``batch.analysis_started`` payload - L1035 (``"batch_id"``) and L1036
#     (``"camera_id"``);
#   * the ``batch.analysis_completed`` payload - L1115 (``"batch_id"``) and L1116
#     (``"camera_id"``).
#
# The replay harness is twin-sound: a key counts as KILLED only when EVERY
# candidate reddens a NAMED test (a sibling candidate could otherwise fake the
# kill).  So the twelve keys must be read at those three sites as well as at the
# two failure payloads - no splice can be steered to the validation payload alone.
# The success-arm payloads are group g01's SUBJECT (``test_pipeline_workers_
# batch28_00b.py`` pins ``event_id``/``risk_score``/``risk_level``/``duration_ms``
# and the risk-level normalisation); what is re-read here is only the two KEY/VALUE
# statements the twins are bound to, plus the surfaces needed to make those reads
# non-accidental.  Every value below was MEASURED on the shipped source.
#
# The same applies to two keys of the SECURITY arm: ``"error": str(e),`` at L1005
# is occurrence 0 of m190/m191/m192 and ``self._stats.errors += 1`` at L999 is
# occurrence 0 of m203/m204/m205 - which is what leg A21 drives.

# L1002 / L1004 / L1000 - the SECURITY arm's surface.
SECURITY_REJECT_TPL = "SECURITY: Rejecting invalid analysis queue payload: {}"
SECURITY_LABEL = "invalid_analysis_payload"
RAW_TRUNCATION = 500  # L1004 `str(item)[:500]`

# L1026 / L1095 - the two INFO surfaces of the analysis scope.
ANALYZING_INFO_TPL = "Processing analysis for batch {}"
CREATED_EVENT_TPL = "Created event {}: risk_score={}"

# L1044-1047 / L1126-1129 - the two best-effort publish-failure DEBUG arms.
STARTED_FAILED_TPL = "Failed to broadcast batch.analysis_started: {}"
COMPLETED_FAILED_TPL = "Failed to broadcast batch.analysis_completed: {}"

# L1019-1021 / L1037-1038 - the shipped constants of the two dicts.
PIPELINE_STAGE = "analysis"
QUEUE_POSITION = 0
DETECTION_COUNT = 3  # len(DETECTION_IDS) as valid_item() builds them

# L1034-1040 / L1114-1122 - the two shipped key sets, pinned independently.
STARTED_KEYS = {"batch_id", "camera_id", "detection_count", "queue_position", "started_at"}
COMPLETED_KEYS = {
    "batch_id",
    "camera_id",
    "event_id",
    "risk_score",
    "risk_level",
    "duration_ms",
    "completed_at",
}

# The event the analyzer returns: the two fields the success INFO (L1094-1097) and
# the completed payload (L1113-1122) read.  ``risk_level`` is a PLAIN STRING, so the
# shipped normalisation takes the ``str(...)`` branch (L1112) - the enum/None branches
# are g01's subject, not re-tested here.
EVENT_ID = 771
RISK_SCORE = 0.82
RISK_LABEL = "high"


@dataclass
class EventStub:
    """``event.id`` / ``event.risk_score`` / ``event.risk_level`` as read at L1094-1112."""

    id: int
    risk_score: float
    risk_level: Any


@dataclass
class Success:
    """The shipped module-level call sites a SUCCESSFUL analysis reaches."""

    add_span_attributes: Any
    record_pipeline_stage_latency: Any
    record_stage_latency: Any
    record_exception: Any
    record_pipeline_error: Any


def pin_iso_stamp(payload: dict[str, Any], key: str) -> dict[str, Any]:
    """Validate one shipped ``datetime.now(UTC).isoformat()`` stamp and return a COPY
    of ``payload`` without it.

    The value is a wall-clock reading, so it cannot be pinned by equality; it IS
    pinned as a tz-aware ISO-8601 string, and the caller then compares the remaining
    keys with EXACT dict equality (the key-set pins keep the stamp key itself under
    test).  Used for ``failed_at`` (L1145/L1179), ``started_at`` (L1039) and
    ``completed_at`` (L1121).
    """
    assert key in payload, f"{key} key missing: {sorted(payload)}"
    stamp = payload[key]
    assert isinstance(stamp, str), f"{key} must be an ISO string, got {stamp!r}"
    assert datetime.fromisoformat(stamp).tzinfo is not None, (
        f"{key} must carry the shipped UTC timezone: {stamp!r}"
    )
    rest = dict(payload)
    del rest[key]
    return rest


def broadcast_payload(broadcaster: Any, name: str, index: int = 0) -> dict[str, Any]:
    """The payload dict awaited on ``broadcaster.<name>`` at ``index``.

    The shipped calls are all ``await broadcaster.<name>({...})`` with ONE positional
    (L1033, L1113, L1138, L1172), so the dict is read back out of ``args``.  The
    VALUES-bearing asserts run before the count asserts so that an occurrence-twin
    which does change the call count can never mask a value pin.
    """
    calls = getattr(broadcaster, name).await_args_list
    assert index < len(calls), f"{name} sent {len(calls)} payload(s), need index {index}"
    one = calls[index]
    assert len(one.args) == 1 and not one.kwargs, (
        f"{name} passes its payload as one positional dict: {one!r}"
    )
    payload = one.args[0]
    assert isinstance(payload, dict), f"{name} payload must be a dict, got {payload!r}"
    return payload


async def drive_success(
    worker: Any,
    item: dict[str, Any],
    *,
    rejects: dict[str, Exception] | None = None,
) -> Success:
    """Run ``_process_analysis_item`` to completion (L1049-1129).

    The analyzer's ``analyze_batch`` is an ``AsyncMock`` standing in for the LLM call
    and returns this file's own event stub, so the success arm runs its real
    bookkeeping: the stamps, both latency telemetry calls, the success INFO and the
    ``batch.analysis_completed`` publish.  ``rejects`` names a broadcast method whose
    double RAISES, which is how the two best-effort DEBUG arms (L1042-1047,
    L1124-1129) are reached.  Every patched name is a shipped module-level re-export
    on an ``autospec`` window that closes when the drive returns.
    """
    broadcaster = worker._broadcaster
    for name, rejection in (rejects or {}).items():
        setattr(broadcaster, name, AsyncMock(name=name, side_effect=rejection))
    worker._analyzer.analyze_batch = AsyncMock(
        name="analyze_batch",
        return_value=EventStub(id=EVENT_ID, risk_score=RISK_SCORE, risk_level=RISK_LABEL),
    )
    with (
        patch(f"{MOD}.record_exception", autospec=True) as rec_exc,
        patch(f"{MOD}.record_pipeline_error", autospec=True) as rec_err,
        patch(f"{MOD}.record_stage_latency", autospec=True) as rec_stage,
        patch(f"{MOD}.record_pipeline_stage_latency", autospec=True) as rec_latency,
        patch(f"{MOD}.add_span_attributes", autospec=True) as span,
    ):
        await worker._process_analysis_item(item)
    return Success(span, rec_latency, rec_stage, rec_exc, rec_err)


def pin_success_bookkeeping(seen: Success, worker: Any, broadcaster: Any) -> None:
    """Pin what the success arm does AROUND the two payload dicts (L1058-1067).

    ``record_stage_latency`` is awaited with the worker's own Redis client and the
    shipped ``"analyze"`` stage name; ``record_pipeline_stage_latency`` is called with
    the shipped ``"batch_to_analyze"`` tracker key.  ``duration_ms`` is a real
    elapsed-time reading, so only its TYPE is pinned at the call boundary - and no
    ``monotonic``/``perf_counter`` read is patched anywhere.
    """
    assert seen.record_exception.call_args_list == [], "a success records no exception"
    assert seen.record_pipeline_error.call_args_list == [], "a success is no pipeline error"
    tracker = seen.record_pipeline_stage_latency.call_args_list
    assert len(tracker) == 1, (
        f"exactly one in-memory latency tracker write per analysed batch, got {tracker!r}"
    )
    assert tracker[0].args[0] == "batch_to_analyze", f"tracker key mutated: {tracker[0]!r}"
    assert not tracker[0].kwargs and isinstance(tracker[0].args[1], int), (
        f"the tracker takes the duration as a positional int: {tracker[0]!r}"
    )
    stage_calls = seen.record_stage_latency.await_args_list
    assert len(stage_calls) == 1, (
        f"exactly one Redis stage-latency write per analysed batch, got {stage_calls!r}"
    )
    assert stage_calls[0].args[0] is worker._redis, (
        "the Redis-side latency write carries the worker's own client"
    )
    assert stage_calls[0].args[1] == "analyze", f"stage name mutated: {stage_calls[0]!r}"
    assert isinstance(stage_calls[0].args[2], int), (
        f"duration_ms must reach the tracker as an int: {stage_calls[0]!r}"
    )
    assert worker._stats.items_processed == 1, (
        f"one analysed batch is one processed item, got {worker._stats.items_processed}"
    )
    assert worker._stats.errors == 0, f"a success counts no error, got {worker._stats.errors}"
    assert worker._stats.last_processed_at is not None, "last_processed_at is stamped on success"
    assert broadcaster.broadcast_batch_analysis_failed.await_args_list == [], (
        "a success never broadcasts analysis_failed"
    )


@pytest.mark.parametrize(
    ("item_camera", "payload_camera", "span_attrs"),
    [
        (
            CAMERA_ID,
            CAMERA_ID,
            {
                "batch_id": BATCH_ID,
                "detection_count": DETECTION_COUNT,
                "pipeline_stage": PIPELINE_STAGE,
                "camera_id": CAMERA_ID,
            },
        ),
        (
            None,
            "",
            {
                "batch_id": BATCH_ID,
                "detection_count": DETECTION_COUNT,
                "pipeline_stage": PIPELINE_STAGE,
            },
        ),
    ],
    ids=["with-camera", "without-camera"],
)
async def test_the_analysis_started_broadcast_carries_the_shipped_started_payload(
    item_camera: str | None,
    payload_camera: str,
    span_attrs: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped L1017-1041 - the span attributes and the ``analysis_started`` payload.

    ::

        span_attrs: dict[str, str | int | float | bool] = {
            "batch_id": batch_id,                                  # L1019
            "detection_count": len(detection_ids) if detection_ids else 0,
            "pipeline_stage": "analysis",
        }
        ...
        await broadcaster.broadcast_batch_analysis_started(
            {
                "batch_id": batch_id,                              # L1035
                "camera_id": camera_id or "",                      # L1036
                "detection_count": detection_count,
                "queue_position": 0,
                "started_at": datetime.now(UTC).isoformat(),
            }
        )

    ``m184``/``m185``/``m232``/``m233`` (the ``"batch_id"`` KEY rename) and
    ``m186``-``m189``/``m234``-``m237`` (the ``"camera_id"`` KEY rename, the
    ``or``->``and`` boolop and the ``""``->``"XXXX"`` placeholder) have occurrence
    candidates HERE and at L1019, so those candidates can only redden on this pin.
    Both camera polarities are driven because the two ``camera_id`` VALUE mutants
    read differently from each side: ``camera_id and ""`` yields ``""`` where shipped
    yields ``"front_door"`` (the with-camera param) while ``camera_id or "XXXX"``
    yields ``"XXXX"`` where shipped yields ``""`` (the without-camera param).  The
    span kwargs are pinned as a complete set, which is also what makes the shipped
    ``if camera_id is not None:`` guard at L1023-1024 observable, and the DEBUG level
    is pinned empty so a payload whose construction RAISES cannot pass as merely
    missing (see A19).
    """
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster)
    win(caplog)

    seen = await drive_success(worker, valid_item(camera_id=item_camera))

    started = dict(broadcast_payload(broadcaster, "broadcast_batch_analysis_started"))
    rest = pin_iso_stamp(started, "started_at")
    assert rest == {
        "batch_id": BATCH_ID,
        "camera_id": payload_camera,
        "detection_count": DETECTION_COUNT,
        "queue_position": QUEUE_POSITION,
    }, f"analysis_started payload mutated: {started!r}"
    assert set(broadcast_payload(broadcaster, "broadcast_batch_analysis_started")) == (
        STARTED_KEYS
    ), "analysis_started key set mutated"
    assert seen.add_span_attributes.call_args_list == [call(**span_attrs)], (
        f"span attributes mutated: {seen.add_span_attributes.call_args_list!r}"
    )
    assert broadcaster.broadcast_batch_analysis_started.await_count == 1, (
        "analysis_started is broadcast exactly once, before analyze_batch"
    )
    assert worker._analyzer.analyze_batch.await_args_list == [
        call(batch_id=BATCH_ID, camera_id=item_camera, detection_ids=[1, 2, 3])
    ], f"the shipped analyze_batch call mutated: {worker._analyzer.analyze_batch.await_args_list!r}"
    pin_success_bookkeeping(seen, worker, broadcaster)
    pin_levels(
        caplog,
        [
            ANALYZING_INFO_TPL.format(BATCH_ID),
            CREATED_EVENT_TPL.format(EVENT_ID, RISK_SCORE),
        ],
        logging.INFO,
    )
    pin_payloads(
        caplog,
        logging.INFO,
        [
            {"batch_id": BATCH_ID, "camera_id": item_camera, "operation": "analysis"},
            {
                "event_id": EVENT_ID,
                "risk_score": RISK_SCORE,
                "items_processed": 1,
                "batch_id": BATCH_ID,
                "camera_id": item_camera,
                "operation": "analysis",
            },
        ],
    )
    pin_levels(caplog, [], logging.WARNING)
    pin_levels(caplog, [], logging.DEBUG)
    pin_levels(caplog, [], logging.ERROR)


@pytest.mark.parametrize(
    ("item_camera", "payload_camera"),
    [(CAMERA_ID, CAMERA_ID), (None, "")],
    ids=["with-camera", "without-camera"],
)
async def test_the_completed_broadcast_carries_the_shipped_completed_payload(
    item_camera: str | None,
    payload_camera: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped L1113-1122 - the ``batch.analysis_completed`` payload.

    ::

        await broadcaster.broadcast_batch_analysis_completed(
            {
                "batch_id": batch_id,                              # L1115
                "camera_id": camera_id or "",                      # L1116
                "event_id": event.id,
                "risk_score": event.risk_score,
                "risk_level": risk_level_str,
                "duration_ms": duration_ms,
                "completed_at": datetime.now(UTC).isoformat(),
            }
        )

    The two KEY statements at L1115/L1116 are occurrence candidates of
    ``m184``/``m185``/``m232``/``m233`` and ``m186``-``m189``/``m234``-``m237``, so
    these twelve keys are only fully killed once this site is read too.  The three
    remaining value keys come from this file's own event stub through the shipped
    normalisation (``"high"`` has no ``.value``, so L1112's ``str(...)`` branch yields
    ``"high"``) and ``duration_ms``/``completed_at`` are validated as an int and a
    tz-aware ISO stamp before the EXACT comparison of the rest - the g01 keys on those
    two fields are ``_00b``'s subject, and nothing here asserts a wall-clock duration.
    """
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster)
    win(caplog)

    seen = await drive_success(worker, valid_item(camera_id=item_camera))

    completed = dict(broadcast_payload(broadcaster, "broadcast_batch_analysis_completed"))
    assert isinstance(completed["duration_ms"], int), (
        f"duration_ms must be the shipped int, got {completed.get('duration_ms')!r}"
    )
    rest = pin_iso_stamp(completed, "completed_at")
    del rest["duration_ms"]
    assert rest == {
        "batch_id": BATCH_ID,
        "camera_id": payload_camera,
        "event_id": EVENT_ID,
        "risk_score": RISK_SCORE,
        "risk_level": RISK_LABEL,
    }, f"analysis_completed payload mutated: {completed!r}"
    assert set(broadcast_payload(broadcaster, "broadcast_batch_analysis_completed")) == (
        COMPLETED_KEYS
    ), "analysis_completed key set mutated"
    assert broadcaster.broadcast_batch_analysis_completed.await_count == 1, (
        "the completion publish fires exactly once, after the success INFO"
    )
    assert broadcaster.broadcast_batch_analysis_started.await_count == 1
    pin_success_bookkeeping(seen, worker, broadcaster)
    pin_levels(
        caplog,
        [
            ANALYZING_INFO_TPL.format(BATCH_ID),
            CREATED_EVENT_TPL.format(EVENT_ID, RISK_SCORE),
        ],
        logging.INFO,
    )
    pin_levels(caplog, [], logging.WARNING)
    pin_levels(caplog, [], logging.DEBUG)
    pin_levels(caplog, [], logging.ERROR)


async def test_the_analysis_started_broadcast_cannot_stop_the_analysis(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped L1042-1047 - a rejected ``analysis_started`` becomes one DEBUG.

    ::

        except Exception as broadcast_err:
            # Log but don't fail - status broadcasts are best-effort
            logger.debug(
                f"Failed to broadcast batch.analysis_started: {broadcast_err}",
                extra={"batch_id": batch_id},
            )

    Site shield for A17 (no g02 survivor sits on this arm - the admitted list has no
    diff at L1042-1047, which is why the pre-existing suite already holds it): it
    proves A17's "DEBUG level is empty" pin is a real observation rather than an
    accident of a broadcast that never raised.  When the publish DOES raise the run
    still completes - the ``started_at`` payload is attempted once, the completion
    publish still fires and the stats are the success ones.  The record also carries
    the shipped ``log_context`` injection (L1013-1014 merged by the module's
    ``ContextFilter``), which the two failure-arm legs already pin.
    """
    rejection = builtins.ConnectionError("websocket emitter unreachable")
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster)
    win(caplog)

    seen = await drive_success(
        worker,
        valid_item(camera_id=CAMERA_ID),
        rejects={"broadcast_batch_analysis_started": rejection},
    )

    rec = only(caplog, logging.DEBUG, STARTED_FAILED_TPL.format(rejection))
    assert shipped_extra(rec) == {
        "batch_id": BATCH_ID,
        "camera_id": CAMERA_ID,
        "operation": "analysis",
    }, f"started-rejection extra mutated: {shipped_extra(rec)!r}"
    assert broadcaster.broadcast_batch_analysis_started.await_count == 1, (
        "the started publish is attempted exactly once - the arm never retries"
    )
    started = dict(broadcast_payload(broadcaster, "broadcast_batch_analysis_started"))
    assert set(started) == STARTED_KEYS, f"started key set mutated: {sorted(started)}"
    assert broadcaster.broadcast_batch_analysis_completed.await_count == 1, (
        "a lost started event does not cancel the analysis"
    )
    pin_success_bookkeeping(seen, worker, broadcaster)
    pin_levels(
        caplog,
        [
            ANALYZING_INFO_TPL.format(BATCH_ID),
            CREATED_EVENT_TPL.format(EVENT_ID, RISK_SCORE),
        ],
        logging.INFO,
    )


async def test_a_completed_broadcast_rejection_is_debugged_and_never_escapes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped L1124-1129 - a rejected completion becomes one DEBUG, nothing else.

    ::

        except Exception as broadcast_err:
            logger.debug(
                f"Failed to broadcast batch.analysis_completed: {broadcast_err}",
                extra={"batch_id": batch_id, "event_id": event.id},
            )

    Site shield for A18: it shows a completion publish that RAISES lands on this
    DEBUG with its own two-key ``extra`` (plus the shipped ``log_context`` merge)
    rather than vanishing, so A18's empty-DEBUG pin distinguishes "the shipped dict
    was sent" from "building it failed".  The failure is swallowed: the item is still
    counted processed and the success INFO still fires.
    """
    rejection = builtins.ConnectionError("subscriber queue full")
    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster)
    win(caplog)

    seen = await drive_success(
        worker,
        valid_item(camera_id=CAMERA_ID),
        rejects={"broadcast_batch_analysis_completed": rejection},
    )

    rec = only(caplog, logging.DEBUG, COMPLETED_FAILED_TPL.format(rejection))
    assert shipped_extra(rec) == {
        "batch_id": BATCH_ID,
        "event_id": EVENT_ID,
        "camera_id": CAMERA_ID,
        "operation": "analysis",
    }, f"completed-rejection extra mutated: {shipped_extra(rec)!r}"
    assert broadcaster.broadcast_batch_analysis_completed.await_count == 1, (
        "the completion publish is attempted exactly once"
    )
    assert broadcaster.broadcast_batch_analysis_started.await_count == 1
    pin_success_bookkeeping(seen, worker, broadcaster)
    # The success INFO (L1094-1101) precedes the publish it shields, so it fires first.
    pin_levels(
        caplog,
        [
            ANALYZING_INFO_TPL.format(BATCH_ID),
            CREATED_EVENT_TPL.format(EVENT_ID, RISK_SCORE),
        ],
        logging.INFO,
    )
    pin_levels(caplog, [], logging.WARNING)
    pin_levels(caplog, [], logging.ERROR)


async def test_a_rejected_payload_is_security_logged_counted_and_returns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped L992-1008 - the payload-validation arm, before any broadcast exists.

    ::

        except ValueError as e:
            self._stats.errors += 1                            # L999
            record_pipeline_error("invalid_analysis_payload")   # L1000
            logger.error(
                f"SECURITY: Rejecting invalid analysis queue payload: {e}",
                extra={
                    "raw_item": str(item)[:500],  # L1004
                    "error": str(e),                             # L1005
                },
            )
            return

    This arm is occurrence 0 of ``m190``/``m191``/``m192`` (the ``"error"`` KEY rename
    and ``str(None)``) and of ``m203``/``m204``/``m205`` (``+=`` -> ``=``, ``-=`` and
    ``+= 2``), so those candidates can only redden here.  Two rejections are driven on
    one worker because a per-call count is the only observable that separates
    ``errors += 1`` from ``errors = 1`` / ``+= 2``; the second one is what pins the
    accumulation.  The expected message text is captured by calling the shipped
    ``validate_analysis_payload`` DIRECTLY, outside the driven body, so no splice of
    ``_process_analysis_item`` can move the expectation while ``str(e)`` is what is
    under test.  Nothing is broadcast: the arm returns before ``_get_broadcaster``.
    """
    bad: dict[str, Any] = {"detection_ids": [1, 2, 3]}
    with pytest.raises(ValueError) as caught:
        M.validate_analysis_payload(dict(bad))
    expected = str(caught.value)
    assert expected, "the shipped validator's own message is the pin's input"

    broadcaster = broadcaster_double()
    worker = analysis_worker(broadcaster)
    win(caplog)

    with (
        patch(f"{MOD}.record_pipeline_error", autospec=True) as rec_err,
        patch(f"{MOD}.record_exception", autospec=True) as rec_exc,
    ):
        await worker._process_analysis_item(dict(bad))
        assert worker._stats.errors == 1, (
            f"the first rejection counted {worker._stats.errors} errors, not 1"
        )
        await worker._process_analysis_item(dict(bad))

    assert worker._stats.errors == 2, (
        f"the counter must accumulate +1 per rejection, got {worker._stats.errors}"
    )
    assert rec_err.call_args_list == [((SECURITY_LABEL,), {}), ((SECURITY_LABEL,), {})], (
        f"metric label mutated: {rec_err.call_args_list!r}"
    )
    assert rec_exc.call_args_list == [], (
        "the SECURITY arm records the rejection through the error counter only"
    )
    text = SECURITY_REJECT_TPL.format(expected)
    pin_levels(caplog, [text, text], logging.ERROR)
    pin_payloads(
        caplog,
        logging.ERROR,
        [
            {"raw_item": str(bad)[:RAW_TRUNCATION], "error": expected},
            {"raw_item": str(bad)[:RAW_TRUNCATION], "error": expected},
        ],
    )
    pin_levels(caplog, [], logging.WARNING)
    pin_levels(caplog, [], logging.DEBUG)
    assert broadcaster.broadcast_batch_analysis_started.await_args_list == [], (
        "an unvalidated payload never reaches the broadcaster"
    )
    assert broadcaster.broadcast_batch_analysis_failed.await_args_list == []
    assert broadcaster.broadcast_batch_analysis_completed.await_args_list == []
    assert worker._stats.items_processed == 0
    assert worker._analyzer.analyze_batch.call_args_list == [], (
        "an unvalidated payload never reaches the analyzer"
    )


# =============================================================================
# PART B harness: ``DetectionQueueWorker._run_loop`` (lane L364-453)
# =============================================================================


def autospec_of(target: Any) -> Any:
    """One double, visibly ``create_autospec``'d from a shipped callable (WP4.2)."""
    return create_autospec(target)


def install_clock(fn: Any, clock: Any) -> Callable[[], None]:
    """Install a scripted ``time_module`` alias into ``fn``'s own live globals.

    The alias is the shipped module-level binding (L33 ``import time as time_module``),
    read by this loop at L381 / L385 / L392 / L399.  Writing it through
    ``live_globals`` reaches the dict the LIVE function object resolves in, which is the
    pristine module dict on the normal path, the snapshot COPY in the ep_plugin red-check
    lane, and - behind the mutmut trampoline - ``M.__dict__`` again via ``__wrapped__``.
    ``patch``-ing the shipped attribute would miss worlds where the variant body was
    re-sourced; nothing here ever touches the real ``time`` module,
    ``time.monotonic`` or ``time.perf_counter``.
    """
    g = live_globals(fn)
    saved = g.get("time_module")
    g["time_module"] = clock

    def restore() -> None:
        g["time_module"] = saved

    return restore


class ConstantTimeModule:
    """The ``time_module`` alias pinned to ONE value, so no gate can open.

    Every read answers the same float, so ``now - last`` is ``0.0`` and neither the
    20-second heartbeat (L393) nor the 30-second claim gate (L400) can fire.  That is
    what keeps the streams / legacy legs owned by their own keys instead of drifting into
    the claim legs.  The read COUNT is still counted and pinned - it is the observable
    that catches a removed read, an added read and the two gate flips.
    """

    def __init__(self, value: float = 1000.0, *_ignored: float) -> None:
        self.value = value
        self.reads = 0

    def time(self) -> float:
        self.reads += 1
        return self.value

    def __getattr__(self, name: str) -> Any:
        return getattr(real_time, name)


class ScriptedTimeModule:
    """The ``time_module`` alias answering from an explicit per-read script.

    Read ``i`` answers ``steps[i]`` and any later read repeats the last value, so a leg
    can step the clock by exactly the shipped heartbeat / claim period per iteration and
    still pin the total read count.
    """

    def __init__(self, *steps: float) -> None:
        self._steps = steps
        self.reads = 0

    def time(self) -> float:
        i = self.reads
        self.reads += 1
        return self._steps[i] if i < len(self._steps) else self._steps[-1]

    def __getattr__(self, name: str) -> Any:
        return getattr(real_time, name)


@dataclass
class Pass:
    """One scripted iteration of the shipped loop.

    ``item`` is what the BLPOP read returns (a dict for a real item, ``None`` for an
    idle timeout), ``messages`` what ``consume_detections`` returns, and ``claims`` what
    ``claim_stale_messages`` returns - where ``None`` means THIS pass must not ask the
    claim gate at all, so the stub raises inside the shipped ``try`` and the leg's
    zero-error pins see it.  ``raises`` replaces the advancing read's result with a
    failure: a plain ``Exception`` for the error arm (L435-448), ``asyncio.CancelledError``
    as the sentinel that ends the drive through the shipped ``break`` (L434).
    """

    item: Any = None
    messages: list[Any] = field(default_factory=list)
    claims: list[Any] | None = None
    raises: BaseException | None = None


@dataclass
class Run:
    """One scripted drive, its clock script, and everything it observed.

    The shipped body performs its driving read exactly ONCE per iteration (L401 claim,
    L411 consume, L422 BLPOP), so the pass index advances on THAT read - never on a
    sleep, because the streams arm and the idle legacy pass never sleep.  A mutant that
    iterates past the script gets a loud ``AssertionError`` inside the shipped ``try``.
    """

    passes: list[Pass]
    clock: list[float] = field(default_factory=lambda: [1000.0])
    clock_kind: Any = ConstantTimeModule
    use_streams: bool = False
    build_service: bool = True
    supervisor: Any = None
    queue_name: str = "detection_queue-b28"
    poll_timeout: int = 7
    dlq_verdicts: dict[str, bool] = field(default_factory=dict)
    acked: list[str] = field(default_factory=list)
    moved: list[tuple[str, str]] = field(default_factory=list)
    processed: list[Any] = field(default_factory=list)
    sleeps: list[float] = field(default_factory=list)
    states_at_error_call: list[str] = field(default_factory=list)
    clock_module: Any = None
    calls: int = 0

    def clock_reads(self) -> int:
        """``time_module.time()`` reads the shipped body actually made."""
        assert self.clock_module is not None, "the drive has not run yet"
        return self.clock_module.reads

    def next_pass(self) -> Pass:
        self.calls += 1
        index = self.calls - 1
        if index >= len(self.passes):
            raise AssertionError(
                f"the loop entered iteration {index + 1} of a {len(self.passes)}-pass script"
            )
        return self.passes[index]

    def in_flight_pass(self) -> Pass:
        """The pass currently in flight, as seen BEFORE its own advancing read.

        The shipped claim gate (L400) runs before this iteration's consume read (L411),
        so the number of COMPLETED advancing reads is the index of the pass in flight.
        """
        if 0 <= self.calls < len(self.passes):
            return self.passes[self.calls]
        raise AssertionError(f"the claim gate fired outside the {len(self.passes)}-pass script")


def make_worker(run: Run) -> Any:
    """Attribute-only ``self`` for the real coroutine, on an autospec'd instance.

    ``create_autospec(DetectionQueueWorker)`` enforces every method signature and its
    ``_run_loop`` AsyncMock is NEVER awaited - every leg calls the shipped function
    object directly.  Only the attributes the loop resolves through ``self`` are
    installed, carrying the values the pins assert: ``_redis`` is an autospec'd
    ``RedisClient`` whose ``get_from_queue`` serves the item script, ``_queue_name`` /
    ``_poll_timeout`` are this file's own values (deliberately NOT the shipped defaults,
    so an argument mutation cannot alias them), ``_worker_name`` is the shipped
    constructor default (L242), ``_stats`` a real shipped ``WorkerStats()`` and
    ``_process_detection_item`` an INSTANCE attribute standing in for the processor - an
    instance attribute beats the class attribute in every world, including a replay
    mutant's re-sourced class.
    """

    async def fake_process(item: Any) -> None:
        await _REAL_SLEEP(0)
        run.processed.append(item)

    worker = create_autospec(DetectionQueueWorker).return_value
    redis = create_autospec(RedisClient).return_value

    async def fake_get_from_queue(*args: Any, **kwargs: Any) -> Any:
        if run.calls > PASS_CEILING:
            raise RuntimeError("the loop iterated more times than any shipped path can")
        scripted_pass = run.next_pass()
        await _REAL_SLEEP(0)
        if scripted_pass.raises is not None:
            raise scripted_pass.raises
        return scripted_pass.item

    redis.get_from_queue.side_effect = fake_get_from_queue
    worker._redis = redis
    worker._supervisor = run.supervisor
    worker._worker_name = "detection"
    worker._queue_name = run.queue_name
    worker._poll_timeout = run.poll_timeout
    worker._running = True
    worker._stats = WorkerStats()
    worker._process_detection_item = fake_process
    return worker


def make_stream_service(run: Run) -> Any:
    """autospec'd ``DetectionStreamService`` instance serving the stream script.

    ``consume_detections`` advances the pass index (it is the iteration's own read);
    ``claim_stale_messages`` does NOT (the shipped gate at L400 runs before that read and
    answers from the in-flight pass' ``claims`` field, raising when the pass forbids it).
    ``should_move_to_dlq`` answers from ``run.dlq_verdicts`` keyed by message id, so an
    unexpected message is a loud ``AssertionError`` rather than a silent mock default.
    """
    service = create_autospec(DetectionStreamService).return_value
    service._max_delivery_count = DLQ_THRESHOLD

    async def fake_claim(*args: Any, **kwargs: Any) -> list[Any]:
        scripted_pass = run.in_flight_pass()
        if scripted_pass.claims is None:
            raise AssertionError(
                "claim_stale_messages ran on a pass whose shipped clock cannot open the "
                "30-second claim gate"
            )
        await _REAL_SLEEP(0)
        return list(scripted_pass.claims)

    async def fake_consume(*args: Any, **kwargs: Any) -> list[Any]:
        if run.calls > PASS_CEILING:
            raise RuntimeError("the loop iterated more times than any shipped path can")
        scripted_pass = run.next_pass()
        await _REAL_SLEEP(0)
        if scripted_pass.raises is not None:
            raise scripted_pass.raises
        return list(scripted_pass.messages)

    async def fake_should_move(message: DetectionStreamMessage) -> bool:
        await _REAL_SLEEP(0)
        if message.id not in run.dlq_verdicts:
            raise AssertionError(f"no DLQ verdict scripted for {message.id!r}")
        return run.dlq_verdicts[message.id]

    async def fake_move(message: DetectionStreamMessage, reason: str = "") -> str:
        run.moved.append((message.id, reason))
        return "dlq-entry-id"

    async def fake_acknowledge(message_id: str) -> bool:
        run.acked.append(message_id)
        return True

    service.claim_stale_messages.side_effect = fake_claim
    service.consume_detections.side_effect = fake_consume
    service.should_move_to_dlq.side_effect = fake_should_move
    service.move_to_dlq.side_effect = fake_move
    service.acknowledge.side_effect = fake_acknowledge
    return service


def message(msg_id: str, raw_data: dict[str, Any]) -> DetectionStreamMessage:
    """A REAL shipped ``DetectionStreamMessage`` carrying the ``raw_data`` the loop reads.

    ``id`` and ``raw_data`` are the only two attributes ``_run_loop`` touches (L406,
    L418-419); the other dataclass fields are required by ``__init__``
    (redis_streams.py:154-176), so they carry this file's inert values and no double
    stands in for the shipped object.  The payload dict is carried BY REFERENCE, never
    copied, so a leg can pin by IDENTITY that the shipped ``msg.raw_data`` object is the
    one handed to the processor - the strongest form of the m44 (``raw_data -> None``)
    pin.
    """
    return DetectionStreamMessage(
        id=msg_id,
        camera_id="cam-b28",
        detection_id=7,
        file_path="/var/lib/b28/frame.jpg",
        raw_data=raw_data,
    )


def supervisor_double() -> Any:
    """autospec'd instance double of the shipped ``WorkerSupervisor``."""
    return create_autospec(WorkerSupervisor).return_value


@contextlib.asynccontextmanager
async def scripted(run: Run) -> Any:
    """Drive the shipped loop through the leg's whole script, then hand out the spies.

    Yields a ``Doubles`` namespace INSIDE the patch window (the stats and state pins are
    taken there).  Every double is autospec'd from the shipped callable and installed
    with ``new=``; ``asyncio.sleep`` is patched as an attribute of the ``asyncio`` module,
    which is the object the shipped ``await asyncio.sleep(1.0)`` (L447) resolves through.
    The sleep spy records the delay and STOPS a runaway loop after a bounded budget: the
    two L397 gate mutants make ``None.consume_detections`` raise on every iteration, and a
    bounded drive whose log surface the pins then reject is what keeps such a mutant away
    from the ini ``timeout = 5``.
    """
    worker = make_worker(run)
    # build_service=False drives the SHIPPED `stream_service is None` state inside
    # streams mode (L368 declares None, L372 writes whatever the factory hands back), so
    # the factory must answer None - an autospec'd mock would be non-None.
    service = make_stream_service(run) if (run.use_streams and run.build_service) else None

    sleep_double = autospec_of(_REAL_SLEEP)

    async def spy_sleep(delay: float, *_args: Any, **_kwargs: Any) -> None:
        run.sleeps.append(delay)
        if len(run.sleeps) > SLEEP_LIMIT or run.calls > PASS_CEILING:
            worker._running = False

    sleep_double.side_effect = spy_sleep

    settings = create_autospec(Settings, instance=True)
    settings.use_redis_streams = run.use_streams
    get_settings = autospec_of(M.get_settings)
    get_settings.return_value = settings

    factory = autospec_of(M.get_detection_stream_service)
    factory.return_value = service

    record_error = autospec_of(M.record_pipeline_error)
    # L437 writes the ERROR state and L448 restores RUNNING, so the ONLY place that write
    # is observable is inside the L440 record_pipeline_error call between them.  It is
    # read through the shipped WorkerStats.to_dict() - which is also what makes m62
    # (state = None) raise right there instead of passing silently.
    record_error.side_effect = lambda _error_type: run.states_at_error_call.append(
        worker._stats.to_dict()["state"]
    )

    clock = run.clock_kind(*run.clock)
    run.clock_module = clock
    restore = install_clock(M.DetectionQueueWorker._run_loop, clock)
    try:
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(M, "get_settings", new=get_settings))
            stack.enter_context(patch.object(M, "get_detection_stream_service", new=factory))
            stack.enter_context(patch.object(M, "record_pipeline_error", new=record_error))
            stack.enter_context(patch.object(asyncio, "sleep", new=sleep_double))
            await M.DetectionQueueWorker._run_loop(worker)
            yield Doubles(
                worker=worker,
                run=run,
                service=service,
                factory=factory,
                record_pipeline_error=record_error,
                sleep=sleep_double,
            )
    finally:
        restore()


@dataclass
class Doubles:
    """Everything one drive left behind, read after the loop returned."""

    worker: Any
    run: Run
    service: Any
    factory: Any
    record_pipeline_error: Any
    sleep: Any


def consumer_name_of(worker: Any) -> str:
    """The shipped ``f"detection-worker-{id(self)}"`` (L369) for THIS worker object."""
    return f"detection-worker-{id(worker)}"


def pin_streams_info(
    caplog: pytest.LogCaptureFixture,
    *,
    msgs: list[str],
    payloads: list[dict[str, Any]],
) -> None:
    """Pin the ordered INFO surface AND every ``extra=`` payload in one place."""
    pin_levels(caplog, msgs, logging.INFO)
    pin_payloads(caplog, logging.INFO, payloads)


# =============================================================================
# B1) streams mode: the banner family, the consumer_name family, the factory,
#     the consume-call family, the message routing (m4, m5, m7-m12, m15, m16,
#     m34, m35, m37, m44, m45)
# =============================================================================


async def test_streams_mode_announces_the_consumer_and_consumes_one_blocking_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:364-419 + L450 in STREAMS mode (``use_redis_streams`` True).

    ::

        settings = get_settings()                                    # L366
        use_streams = settings.use_redis_streams                     # L367
        stream_service: DetectionStreamService | None = None         # L368
        consumer_name = f"detection-worker-{id(self)}"               # L369
        if use_streams:                                              # L371
            stream_service = await get_detection_stream_service(self._redis)  # L372
            logger.info(                                             # L373-376
                "DetectionQueueWorker loop started (Redis Streams mode)",
                extra={"consumer_name": consumer_name},
            )
        ...
                if use_streams and stream_service is not None:       # L397
                    ...
                    messages = await stream_service.consume_detections(
                        consumer_name, count=1, block=True           # L411-413
                    )
                    ...
                    for msg in messages:
                        await self._process_detection_item(msg.raw_data)   # L418
                        await stream_service.acknowledge(msg.id)           # L419

    The banner exists ONLY in this mode, so its message (m8 ``None`` / m10 dropped /
    m12 ``"XX..XX"``) and its payload (m9 ``extra=None`` / m11 dropped / m15
    ``"XXconsumer_nameXX"`` / m16 ``"CONSUMER_NAME"``) can only die here.  The payload
    VALUE is the shipped ``f"detection-worker-{id(worker)}"``, which is also what makes
    m4 (``consumer_name = None``) and m5 (``id(None)`` -> a foreign id) visible; the same
    value is re-pinned as ``consume_detections``' positional (m34 ``None``, m37 dropped)
    with ``count=1`` (m35 ``None``) and ``block=True``.  The factory argument is pinned
    by IDENTITY (m7 ``None``).  Each message's ``raw_data`` must reach the processor and
    its ``id`` must reach ``acknowledge`` - m44's ``None`` argument and m45's dropped id
    cannot satisfy those pins.  The legacy read is pinned absent, which is what stops a
    silently-legacy drive (m2/m6/m28/m29 all turn this into one) from satisfying the leg.
    """
    first_raw = {"camera_id": "cam-front", "detection_id": 101, "file_path": "/f/1.jpg"}
    second_raw = {"camera_id": "cam-back", "detection_id": 102, "file_path": "/f/2.jpg"}
    run = Run(
        passes=[
            Pass(messages=[message("11-0", first_raw)]),
            Pass(messages=[message("12-0", second_raw)]),
            Pass(raises=CANCEL()),
        ],
        clock=[1000.0],
        use_streams=True,
        supervisor=None,
    )
    win(caplog)

    async with scripted(run) as d:
        stats = d.worker._stats.to_dict()

    name = consumer_name_of(d.worker)
    assert d.factory.await_count == 1, f"the stream service was built {d.factory.await_count} times"
    assert d.factory.await_args is not None
    assert d.factory.await_args.args == (d.worker._redis,), (
        f"get_detection_stream_service argument mutated: {d.factory.await_args!r}"
    )
    assert not d.factory.await_args.kwargs, (
        f"the factory takes one positional: {d.factory.await_args!r}"
    )

    service = d.service
    assert service is not None
    consume_calls = service.consume_detections.await_args_list
    assert consume_calls == [
        call(name, count=1, block=True),
        call(name, count=1, block=True),
        call(name, count=1, block=True),
    ], f"consume_detections mutated: {consume_calls!r}"
    assert service.claim_stale_messages.await_count == 0, (
        "the 30-second claim gate must stay shut while the clock does not advance"
    )
    assert run.processed == [first_raw, second_raw], (
        f"_process_detection_item / msg.raw_data mutated: {run.processed!r}"
    )
    assert run.processed[0] is first_raw and run.processed[1] is second_raw, (
        "the shipped call forwards the message's OWN raw_data object, not a copy"
    )
    assert run.acked == ["11-0", "12-0"], f"acknowledge(msg.id) mutated: {run.acked!r}"
    assert run.moved == [], "nothing is over the delivery limit here"
    assert d.worker._redis.get_from_queue.await_count == 0, (
        "streams mode must never touch the legacy BLPOP arm"
    )
    assert stats == {
        "items_processed": 0,
        "errors": 0,
        "last_processed_at": None,
        "state": STATE_STOPPED,
    }, f"the shipped WorkerStats.to_dict() surface mutated: {stats!r}"

    pin_streams_info(
        caplog,
        msgs=[STREAMS_BANNER, CANCELLED_INFO, EXIT_INFO],
        payloads=[{"consumer_name": name}, {}, {"items_processed": 0}],
    )
    pin_levels(caplog, [], logging.ERROR)
    pin_levels(caplog, [], logging.WARNING)
    pin_levels(caplog, [], logging.DEBUG)
    assert run.sleeps == [], "the streams arm never sleeps"
    assert run.clock_reads() == 5, (
        "L381 + L385 baselines plus one L399 gate read in each of the three iterations "
        "(the sentinel pass pays its gate read before its read raises): "
        f"{run.clock_reads()}"
    )


# =============================================================================
# B2) the ``if not messages: continue`` arm (no survivor sits there) + measured
#     second routes to m4/m5 and m34/m35/m37
# =============================================================================


async def test_an_empty_streams_read_loops_again_without_processing_or_the_legacy_read(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:414-415 - an empty stream read re-loops WITHOUT falling into the BLPOP arm.

    Three empty reads, then the sentinel.  The arm matters to this battery because it is
    a second, independently-valued route to the consumer-name family (m4/m5 - the banner
    carries a DIFFERENT worker's id here) and to the consume-call family (m34/m35/m37 -
    four identical call records, so a dropped or ``None``-ed argument cannot hide behind a
    sibling call).  It also states that entering the streams arm is not enough: an empty
    read must process nothing, acknowledge nothing, claim nothing and above all must not
    read the legacy queue - the conjunct at L397 keeps the two arms disjoint.
    """
    run = Run(
        passes=[
            Pass(messages=[]),
            Pass(messages=[]),
            Pass(messages=[]),
            Pass(raises=CANCEL()),
        ],
        clock=[1000.0],
        use_streams=True,
        supervisor=None,
    )
    win(caplog)

    async with scripted(run) as d:
        stats = d.worker._stats.to_dict()

    name = consumer_name_of(d.worker)
    assert d.service is not None
    assert d.service.consume_detections.await_count == 4, (
        "one consume read per scripted pass, the sentinel pass included"
    )
    assert d.service.consume_detections.await_args_list == [call(name, count=1, block=True)] * 4, (
        f"consume_detections mutated: {d.service.consume_detections.await_args_list!r}"
    )
    assert d.service.claim_stale_messages.await_count == 0
    assert run.processed == [], "an empty read must not process anything"
    assert run.acked == [] and run.moved == []
    assert d.worker._redis.get_from_queue.await_count == 0, (
        "streams mode must never fall into the legacy BLPOP arm"
    )
    assert stats["errors"] == 0 and stats["items_processed"] == 0
    pin_streams_info(
        caplog,
        msgs=[STREAMS_BANNER, CANCELLED_INFO, EXIT_INFO],
        payloads=[{"consumer_name": name}, {}, {"items_processed": 0}],
    )
    assert run.sleeps == []
    assert run.clock_reads() == 6, (
        "the L381 + L385 baselines plus one L399 read per iteration on the frozen clock: "
        f"{run.clock_reads()}"
    )


# =============================================================================
# B3) the stale-claim gate - SOLE route to m25, m30, m31, m32
# =============================================================================


async def test_the_claim_gate_fires_once_per_shipped_30_second_step(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:385-408 - claim stale messages once per 30.0 s of alias clock.

    ::

        last_claim_check = time_module.time()                      # L385
        claim_interval = 30.0                                      # L386
        ...
                    now = time_module.time()                       # L399
                    if now - last_claim_check >= claim_interval:   # L400
                        claimed = await stream_service.claim_stale_messages(
                            consumer_name, count=5                 # L401
                        )
                        ...
                        last_claim_check = now                     # L408

    A supervisor IS installed, because ``now = time_module.time()`` occurs TWICE in the
    loop (L392 heartbeat and L399 claim) and the replay splices both occurrence-twins:
    with no supervisor the L392 twin would be dead and m30 could not be proven killed.
    Every heartbeat read is held at ``0.0`` so ``now - last_heartbeat`` stays ``0.0`` and
    the 20-second arm never beats - that keeps this leg owned by the claim gate (B5 owns
    the heartbeat) while still paying the L392 read.  The claim baseline is ``1000.0``.
    The eight reads are ``0.0 (L381) -> 1000.0 (L385) -> 0.0/1000.0 (pass 1 L392/L399) ->
    0.0/1030.0 (pass 2) -> 0.0/1045.0 (pass 3)``:

    * A NON-ZERO claim baseline is load-bearing: at ``last_claim_check == 0.0`` the
      shipped difference and m31's ``now + last_claim_check`` coincide and m31 is simply
      unobservable.  Pass 1 reads ``1000.0`` again (``elapsed`` 0.0): shipped does NOT
      claim, m31 DOES (``1000.0 + 1000.0 >= 30.0``).
    * Pass 2 reads ``1030.0`` - ``elapsed`` EXACTLY the shipped ``30.0``, the ``>=``
      boundary: shipped CLAIMS here and writes ``last_claim_check = 1030.0``, m32's ``>``
      does not.
    * Pass 3 (the sentinel, whose gate read lands before its read raises) reads
      ``1045.0`` - ``elapsed`` 15.0 from the 1030.0 shipped just wrote, so shipped stays
      shut.  m32, whose baseline is still the original 1000.0, sees ``45.0 > 30.0`` and
      claims HERE instead - the same call count as shipped but a different schedule,
      which is why B4 restates this clock with a DIFFERENT payload per pass.
    * m31 claims on all three passes.
    * m25 (``claim_interval = None``) and m30 (``now = None``) make the comparison raise
      ``TypeError`` inside the shipped ``try``, which the zero-error and zero-sleep pins
      reject.
    The claim ARGUMENTS are pinned exactly (the shipped ``count=5``), and every pass
    answers ``claims=[]`` so the consume arm still runs and the INFO surface stays
    ``[banner, cancelled, exited]``.
    """
    supervisor = supervisor_double()
    run = Run(
        passes=[
            Pass(messages=[], claims=[]),
            Pass(messages=[], claims=[]),
            Pass(raises=CANCEL(), claims=[]),
        ],
        clock=[0.0, 1000.0, 0.0, 1000.0, 0.0, 1030.0, 0.0, 1045.0],
        clock_kind=ScriptedTimeModule,
        use_streams=True,
        supervisor=supervisor,
    )
    win(caplog)

    async with scripted(run) as d:
        stats = d.worker._stats.to_dict()

    name = consumer_name_of(d.worker)
    assert supervisor.record_heartbeat.call_args_list == [], (
        "every heartbeat read is held at 0.0, so the 20-second arm must never beat here "
        f"(B5 owns those keys): {supervisor.record_heartbeat.call_args_list!r}"
    )
    assert d.service is not None
    assert d.service.claim_stale_messages.await_args_list == [call(name, count=CLAIM_COUNT)], (
        f"claim gate contract mutated: {d.service.claim_stale_messages.await_args_list!r}"
    )
    assert d.service.consume_detections.await_count == 3, (
        "one consume read per iteration INCLUDING the sentinel pass, whose read raises"
    )
    assert d.worker._redis.get_from_queue.await_count == 0
    assert run.acked == [] and run.processed == []
    assert stats == {
        "items_processed": 0,
        "errors": 0,
        "last_processed_at": None,
        "state": STATE_STOPPED,
    }, f"the claim gate must not error: {stats!r}"
    assert d.record_pipeline_error.call_count == 0, (
        "the shipped comparison runs on floats - a None operand would raise TypeError "
        "into the error arm, which is what m25/m30 do"
    )
    pin_streams_info(
        caplog,
        msgs=[STREAMS_BANNER, CANCELLED_INFO, EXIT_INFO],
        payloads=[{"consumer_name": name}, {}, {"items_processed": 0}],
    )
    pin_levels(caplog, [], logging.ERROR)
    assert run.sleeps == []
    assert run.clock_reads() == 8, (
        "L381 + L385 baselines, one L392 heartbeat-gate read and one L399 claim-gate "
        f"read per iteration (3 iterations): {run.clock_reads()}"
    )


# =============================================================================
# B4) what a claim yields must be ROUTED - plus measured second routes to
#     m25/m30/m31/m32 and m4/m5
# =============================================================================


async def test_a_stale_claimed_message_goes_to_the_dlq_or_is_reprocessed_and_acked(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:402-408 - ``should_move_to_dlq`` decides between the DLQ and reprocessing.

    ::

                        claimed = await stream_service.claim_stale_messages(
                            consumer_name, count=5                      # L401
                        )
                        for msg in claimed:
                            if await stream_service.should_move_to_dlq(msg):
                                await stream_service.move_to_dlq(msg, "max_delivery_exceeded")
                            else:
                                await self._process_detection_item(msg.raw_data)
                                await stream_service.acknowledge(msg.id)
                        last_claim_check = now                          # L408

    No survivor sits on this arm's own routing (the manifest's g10 sites are the gate,
    the consume call and the message fields), so this leg is stated as the ROUTING control
    that makes the claim legs non-vacuous: entering the arm is not enough, what the claim
    returns must be dispatched correctly.  It is also a measured second route to the gate
    family - the two-step clock (``1000 -> 1040 -> 1070``) makes shipped claim exactly
    TWICE while m32 claims once and m31 three times, and the two claims carry DIFFERENT
    payloads, so a mutant that mis-times the gate cannot reuse this script's answer.  The
    DLQ message's ``raw_data`` must NOT be processed and its id must NOT be acknowledged;
    the stale message's must be both - each pinned by identity and exact call args,
    including the shipped ``"max_delivery_exceeded"`` reason.
    """
    dlq_raw = {"camera_id": "cam-stale", "detection_id": 900}
    dlq_message = message("90-0", dlq_raw)
    stale_raw = {"camera_id": "cam-recover", "detection_id": 901, "file_path": "/f/9.jpg"}
    stale_message = message("91-0", stale_raw)
    supervisor = supervisor_double()
    run = Run(
        passes=[
            Pass(messages=[], claims=[]),
            Pass(messages=[], claims=[dlq_message, stale_message]),
            Pass(raises=CANCEL(), claims=[]),
        ],
        clock=[0.0, 1000.0, 0.0, 1000.0, 0.0, 1040.0, 0.0, 1070.0],
        clock_kind=ScriptedTimeModule,
        use_streams=True,
        supervisor=supervisor,
        dlq_verdicts={"90-0": True, "91-0": False},
    )
    win(caplog)

    async with scripted(run) as d:
        stats = d.worker._stats.to_dict()

    name = consumer_name_of(d.worker)
    assert supervisor.record_heartbeat.call_args_list == [], (
        "the heartbeat reads are inert here too - this leg is about claim ROUTING"
    )
    assert d.service is not None
    assert d.service.claim_stale_messages.await_args_list == [
        call(name, count=CLAIM_COUNT),
        call(name, count=CLAIM_COUNT),
    ], f"the claim gate fired on the wrong schedule: {d.service.claim_stale_messages!r}"
    assert run.moved == [("90-0", DLQ_REASON)], f"DLQ routing mutated: {run.moved!r}"
    assert run.processed == [stale_raw], f"claimed-message processing mutated: {run.processed!r}"
    assert run.processed[0] is stale_raw, "the shipped call forwards the raw_data object"
    assert run.acked == ["91-0"], f"acknowledge after a claim mutated: {run.acked!r}"
    assert d.service.should_move_to_dlq.await_args_list == [
        call(dlq_message),
        call(stale_message),
    ], (
        f"the DLQ verdict was not asked per message: {d.service.should_move_to_dlq.await_args_list!r}"
    )
    assert d.service.consume_detections.await_count == 3
    assert d.worker._redis.get_from_queue.await_count == 0
    assert stats["errors"] == 0, f"a routed claim must not error: {stats!r}"
    pin_streams_info(
        caplog,
        msgs=[STREAMS_BANNER, CANCELLED_INFO, EXIT_INFO],
        payloads=[{"consumer_name": name}, {}, {"items_processed": 0}],
    )
    pin_levels(caplog, [], logging.ERROR)
    assert run.sleeps == []
    assert run.clock_reads() == 8, run.clock_reads()


# =============================================================================
# B5) the heartbeat gate - SOLE route to m21, m22, m23
# =============================================================================


async def test_the_supervisor_heartbeat_beats_once_per_shipped_20_second_step(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:380-395 - one ``record_heartbeat(worker_name)`` per 20.0 s of clock.

    ::

        last_heartbeat = time_module.time()                        # L381
        heartbeat_interval = 20.0                                  # L382
        while self._running:
            try:
                if self._supervisor is not None:                   # L391
                    now = time_module.time()                       # L392
                    if now - last_heartbeat >= heartbeat_interval: # L393
                        self._supervisor.record_heartbeat(self._worker_name)
                        last_heartbeat = now                       # L395

    LEGACY mode, so the claim gate's reads cannot blur the count.  The alias walks
    ``0.0 (L381) -> 0.0 (L385) -> 20.0 (L392) -> 40.0 (L392) -> 60.0 (L392)``: every
    gated pass advances EXACTLY 20.0 s from the previous beat, so shipped's ``>=`` fires
    in all three iterations (the sentinel pass pays its gate read before its read raises)
    - ``[detection, detection, detection]``.  m23 (``21.0``) cannot keep pace with a 20 s
    step: pass 1 is short (20.0 >= 21.0 False), pass 2 beats from the UNMOVED baseline
    (40.0 - 0.0), pass 3 is short again - exactly ONE beat, a different call list.  (A
    coarser script whose first gate already sat past 21.0 would let m23 beat once and
    match shipped; that is precisely the vacuity this script is built to avoid.)  m21
    (``last_heartbeat = None``) and m22 (``heartbeat_interval = None``) raise
    ``TypeError`` inside the shipped ``try`` on the first gated pass and turn every
    iteration into the error arm, which the zero-error and zero-sleep pins reject.  The
    call argument is the shipped constructor's worker name (L242 / L262).
    """
    supervisor = supervisor_double()
    run = Run(
        passes=[Pass(item=None), Pass(item=None), Pass(raises=CANCEL())],
        clock=[0.0, 0.0, 20.0, 40.0, 60.0],
        clock_kind=ScriptedTimeModule,
        use_streams=False,
        supervisor=supervisor,
    )
    win(caplog)

    async with scripted(run) as d:
        stats = d.worker._stats.to_dict()

    assert supervisor.record_heartbeat.call_args_list == [
        call("detection"),
        call("detection"),
        call("detection"),
    ], f"heartbeat contract mutated: {supervisor.record_heartbeat.call_args_list!r}"
    assert run.clock_reads() == 5, (
        "the L381 + L385 baselines plus one L392 gate read in each of the three "
        f"iterations (legacy mode short-circuits L397 on use_streams, so there is no "
        f"L399 read): {run.clock_reads()}"
    )
    assert d.record_pipeline_error.call_count == 0, (
        "the heartbeat gate must never error: the shipped comparison runs on floats"
    )
    assert stats["errors"] == 0, f"the heartbeat gate must not error: {stats!r}"
    assert run.processed == [], "idle passes process nothing"
    pin_streams_info(
        caplog,
        msgs=[LEGACY_BANNER, CANCELLED_INFO, EXIT_INFO],
        payloads=[{}, {}, {"items_processed": 0}],
    )
    pin_levels(caplog, [], logging.ERROR)
    assert run.sleeps == []


# =============================================================================
# B6) m27 from the other side: no supervisor means the gate body never runs
# =============================================================================


async def test_the_supervisor_gate_never_runs_and_never_reads_the_clock_without_one(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:391 - ``if self._supervisor is not None:`` with NO supervisor.

    Three idle legacy passes read the alias exactly TWICE - the L381 and L385 baselines -
    because the gate body is skipped every iteration (legacy mode short-circuits L397 on
    ``use_streams``, so L399 is never reached either).  The flip (m27) runs the arm for a
    ``None`` supervisor, so the read count grows by one per iteration and this leg goes
    red; the zero-beat and zero-error pins state the rest of that arm's absence.  This is
    the measured second route to m21 as well: under the flip the L392 read happens with
    ``last_heartbeat`` never written, so a ``None`` baseline is read - a shape the shipped
    body never reaches.
    """
    run = Run(
        passes=[Pass(item=None), Pass(item=None), Pass(raises=CANCEL())],
        clock=[123.0],
        use_streams=False,
        supervisor=None,
    )
    win(caplog)

    async with scripted(run) as d:
        stats = d.worker._stats.to_dict()

    assert run.clock_reads() == 2, (
        f"a None supervisor must not read the heartbeat clock: {run.clock_reads()} reads"
    )
    assert d.record_pipeline_error.call_count == 0
    assert stats["errors"] == 0, f"stats mutated: {stats!r}"
    assert run.processed == [] and run.sleeps == []
    pin_streams_info(
        caplog,
        msgs=[LEGACY_BANNER, CANCELLED_INFO, EXIT_INFO],
        payloads=[{}, {}, {"items_processed": 0}],
    )
    pin_levels(caplog, [], logging.ERROR)


# =============================================================================
# B7) SOLE route to m6 (service -> None) and m28 (`and` -> `or`)
# =============================================================================


async def test_a_stream_capable_worker_without_a_stream_service_object_stays_legacy(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:397 - ``if use_streams and stream_service is not None:`` decides the arm.

    The one drive where the two conjuncts DISAGREE: ``use_streams`` is True (the STREAMS
    banner fired at L373 and the factory was awaited at L372) but what the factory
    returned was ``None`` - a reachable shipped state, since L368 declares ``None`` and
    L372 writes whatever the factory hands back.  The shipped conjunction is therefore
    False and every iteration must read the LEGACY queue.

    * m6 (``stream_service = None``) is the same shipped state written unconditionally:
      it is only visible because THIS drive's factory answer is ``None``, and the leg
      pins the factory call itself, so the mutant cannot dodge it by not building.
    * m28 (``and`` -> ``or``): ``True or ...`` is True, so the mutant enters the streams
      arm and calls ``None.consume_detections(...)`` - an ``AttributeError`` on every
      iteration.  Its ERROR records, its ``errors`` counter and its ``sleep(1.0)`` per
      failed pass are exactly what the pins here forbid, and the bounded sleep spy keeps
      that drive from riding the ini timeout.
    * m29 (``is not None`` -> ``is None``) takes the same arm for the same reason, so it
      is measured here as a second route.
    The shipped path is pinned positively too: two BLPOP records carrying this worker's
    OWN queue name and poll timeout, the item processed, the legacy banner ABSENT (this
    drive is in streams mode) and the streams banner present.
    """
    item = {"camera_id": "cam-legacy", "detection_id": 201, "file_path": "/f/2.jpg"}
    run = Run(
        passes=[Pass(item=item), Pass(raises=CANCEL())],
        clock=[1000.0],
        use_streams=True,
        build_service=False,
        supervisor=None,
        queue_name="detection_queue-b28",
        poll_timeout=7,
    )
    win(caplog)

    async with scripted(run) as d:
        stats = d.worker._stats.to_dict()

    name = consumer_name_of(d.worker)
    assert d.factory.await_count == 1, "L372 runs whenever use_streams is truthy"
    assert d.service is None, "this drive's factory answer is None by construction"
    assert d.worker._redis.get_from_queue.await_args_list == [
        call("detection_queue-b28", timeout=7),
        call("detection_queue-b28", timeout=7),
    ], (
        "the no-service drive must stay on the legacy queue: "
        f"{d.worker._redis.get_from_queue.await_args_list!r}"
    )
    assert run.processed == [item] and run.processed[0] is item, (
        f"the legacy item must still be processed: {run.processed!r}"
    )
    assert stats == {
        "items_processed": 0,
        "errors": 0,
        "last_processed_at": None,
        "state": STATE_STOPPED,
    }, f"a no-service streams drive must not error: {stats!r}"
    assert d.record_pipeline_error.call_count == 0, (
        "the shipped conjunction never enters the streams arm here"
    )
    pin_streams_info(
        caplog,
        msgs=[STREAMS_BANNER, CANCELLED_INFO, EXIT_INFO],
        payloads=[{"consumer_name": name}, {}, {"items_processed": 0}],
    )
    pin_levels(caplog, [], logging.ERROR)
    assert run.sleeps == [], "no failed pass means no L447 sleep"


# =============================================================================
# B8) SOLE route to m17/m20 (legacy banner) and the BLPOP family
#     m46, m48, m49, m50, m53
# =============================================================================


async def test_the_legacy_read_uses_the_worker_s_own_queue_and_poll_timeout(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:377-378 + L420-430 with ``use_redis_streams`` False.

    ::

        else:
            logger.info("DetectionQueueWorker loop started")           # L378
        ...
            else:
                # Legacy list-based queue (BLPOP)
                item = await self._redis.get_from_queue(               # L422-425
                    self._queue_name,
                    timeout=self._poll_timeout,
                )
                if item is None:                                       # L427
                    continue                                           # L428
                await self._process_detection_item(item)               # L430

    Three scripted passes: item / idle / second item, then the sentinel.  The BLPOP call
    list is pinned to three identical ``call(queue_name, timeout=poll_timeout)`` records
    carrying THIS file's injected attribute values, so m49 (queue name dropped), m50 (the
    ``timeout`` keyword dropped) and m48 (``timeout=None``) all show up, and m46 (the
    whole read replaced by ``item = None``) empties the list entirely.  m53's ``None``
    argument cannot satisfy the identity pin on the processed item.  The legacy banner
    text is pinned because ONLY this mode reaches L378 - m17 (``None``) and m20 (upper
    case) die here - and the streams banner is pinned absent.  ``continue``/``break`` and
    the ``is None`` flip are NOT what this leg decides: its single idle pass is satisfied
    by all three, which is why B9 exists.
    """
    first = {"camera_id": "cam-a", "detection_id": 11, "file_path": "/f/a.jpg"}
    second = {"camera_id": "cam-b", "detection_id": 12, "file_path": "/f/b.jpg"}
    run = Run(
        passes=[Pass(item=first), Pass(item=None), Pass(item=second), Pass(raises=CANCEL())],
        clock=[700.0],
        use_streams=False,
        supervisor=None,
        queue_name="detection_queue-b28",
        poll_timeout=7,
    )
    win(caplog)

    async with scripted(run) as d:
        stats = d.worker._stats.to_dict()

    assert d.worker._redis.get_from_queue.await_count == 4, (
        f"one BLPOP read per iteration: {d.worker._redis.get_from_queue.await_count}"
    )
    assert d.worker._redis.get_from_queue.await_args_list == [
        call("detection_queue-b28", timeout=7),
        call("detection_queue-b28", timeout=7),
        call("detection_queue-b28", timeout=7),
        call("detection_queue-b28", timeout=7),
    ], f"the BLPOP call shape mutated: {d.worker._redis.get_from_queue.await_args_list!r}"
    assert run.processed == [first, second], f"_process_detection_item mutated: {run.processed!r}"
    assert run.processed[0] is first and run.processed[1] is second, (
        "the shipped call hands the queue item over unchanged, by identity"
    )
    assert d.factory.await_count == 0, "legacy mode must not build the stream service"
    assert stats == {
        "items_processed": 0,
        "errors": 0,
        "last_processed_at": None,
        "state": STATE_STOPPED,
    }, f"stats mutated: {stats!r}"

    pin_streams_info(
        caplog,
        msgs=[LEGACY_BANNER, CANCELLED_INFO, EXIT_INFO],
        payloads=[{}, {}, {"items_processed": 0}],
    )
    pin_levels(caplog, [], logging.ERROR)
    pin_levels(caplog, [], logging.WARNING)
    pin_levels(caplog, [], logging.DEBUG)
    assert run.sleeps == [], "neither the item nor the idle legacy pass sleeps"
    assert run.clock_reads() == 2, (
        "exactly the L381 + L385 baselines: no supervisor means no L392 read, and legacy "
        f"mode short-circuits L397 on use_streams so there is no L399 read: "
        f"{run.clock_reads()}"
    )


# =============================================================================
# B9) SOLE route to m51 (`is None` -> `is not None`) and m52 (`continue` -> `break`)
# =============================================================================


async def test_a_second_idle_legacy_read_loops_again_without_processing_or_leaving(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:427-428 - two CONSECUTIVE idle passes prove the ``continue`` survived.

    ::

        item = await self._redis.get_from_queue(...)   # -> None, twice
        if item is None:                              # L427
            continue                                  # L428

    With ONE idle pass the shipped ``continue``, m52's ``break`` and even m51's flipped
    test are hard to separate, so this leg scripts two of them:

    * shipped: pass 1 idle -> loop, pass 2 idle -> loop, pass 3 item -> processed.  Three
      BLPOP records, one processed item.
    * m52 (``continue`` -> ``break``): the loop leaves on the FIRST idle pass - one BLPOP
      record, no processed item, and the sentinel read never happens.
    * m51 (``is None`` -> ``is not None``): an idle pass falls THROUGH to
      ``_process_detection_item(None)`` (a ``None`` in the processed list) and then the
      item pass SKIPS processing - two ``None``-shaped defects, and the call count also
      differs because pass 3's ``continue`` re-loops into the sentinel.
    The shipped banner/cancelled/exited INFO triple and the zero-error surface are pinned
    in every case, and this is a measured second route to m17/m20 at a different worker
    object.
    """
    item = {"camera_id": "cam-c", "detection_id": 13, "file_path": "/f/c.jpg"}
    run = Run(
        passes=[Pass(item=None), Pass(item=None), Pass(item=item), Pass(raises=CANCEL())],
        clock=[800.0],
        use_streams=False,
        supervisor=None,
        queue_name="detection_queue-b28",
        poll_timeout=7,
    )
    win(caplog)

    async with scripted(run) as d:
        stats = d.worker._stats.to_dict()

    assert d.worker._redis.get_from_queue.await_count == 4, (
        "an idle pass must loop back and read again: "
        f"{d.worker._redis.get_from_queue.await_count} reads"
    )
    assert run.processed == [item], (
        f"an idle pass must process NOTHING and the item pass must process the item: "
        f"{run.processed!r}"
    )
    assert run.processed[0] is item
    assert stats["errors"] == 0, f"idle reads are not errors: {stats!r}"
    assert d.record_pipeline_error.call_count == 0
    pin_streams_info(
        caplog,
        msgs=[LEGACY_BANNER, CANCELLED_INFO, EXIT_INFO],
        payloads=[{}, {}, {"items_processed": 0}],
    )
    pin_levels(caplog, [], logging.ERROR)
    assert run.sleeps == [], "the idle arm never sleeps - only the error arm does"


# =============================================================================
# B10) SOLE route to m54/m56/m57 (cancelled message) and m58 (`break` -> `return`)
# =============================================================================


async def test_a_cancelled_pass_logs_the_cancelled_info_and_still_logs_the_exit_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:432-434 + L450 - ``except asyncio.CancelledError``: INFO, then ``break``.

    ::

        except asyncio.CancelledError:
            logger.info("DetectionQueueWorker loop cancelled")     # L433
            break                                                  # L434
        ...
        logger.info(
            "DetectionQueueWorker loop exited",                    # L450-452
            extra={"items_processed": self._stats.items_processed},
        )

    The ordered INFO triple ``[legacy banner, cancelled, exited]`` is the whole contract
    and it is what kills the three message mutants at L433 - m54 (``None``), m56 (lower
    case), m57 (upper case) - and m58: replacing the ``break`` with ``return`` skips the
    L450 exit INFO entirely, so the surface loses its third record and its
    ``items_processed`` payload.  Nothing else happens on this drive - no processing, no
    sleep, no error, no ERROR record - which is what stops the other legs' surfaces from
    re-explaining this arm.
    """
    run = Run(
        passes=[Pass(raises=CANCEL())],
        clock=[1800.0],
        use_streams=False,
        supervisor=None,
    )
    win(caplog)

    async with scripted(run) as d:
        stats = d.worker._stats.to_dict()

    pin_streams_info(
        caplog,
        msgs=[LEGACY_BANNER, CANCELLED_INFO, EXIT_INFO],
        payloads=[{}, {}, {"items_processed": 0}],
    )
    pin_levels(caplog, [], logging.ERROR)
    pin_levels(caplog, [], logging.WARNING)
    pin_levels(caplog, [], logging.DEBUG)
    assert d.worker._redis.get_from_queue.await_count == 1
    assert run.processed == []
    assert run.sleeps == [], "the break skips everything after the handler"
    assert stats == {
        "items_processed": 0,
        "errors": 0,
        "last_processed_at": None,
        "state": STATE_STOPPED,
    }, f"a cancelled read changed the stats: {stats!r}"
    assert d.record_pipeline_error.call_count == 0, "a cancellation is not an error"
    assert run.clock_reads() == 2, run.clock_reads()


# =============================================================================
# B11/B12) the ``except Exception`` arm - SOLE route to m60, m62, m63, m64, m65
# =============================================================================


async def test_a_connection_failure_counts_one_error_logs_a_traceback_and_sleeps(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:435-448 - one failure end to end.

    ::

        except Exception as e:
            self._stats.errors += 1                                  # L436
            self._stats.state = WorkerState.ERROR                    # L437
            error_type = categorize_exception(e, "detection")         # L439
            record_pipeline_error(error_type)                        # L440
            logger.error(
                f"Error in DetectionQueueWorker loop: {e}",          # L442
                exc_info=True,                                       # L443
                extra={"error_count": self._stats.errors, "error_type": error_type},
            )                                                        # L444
            await asyncio.sleep(1.0)                                 # L447
            self._stats.state = WorkerState.RUNNING                  # L448

    7 keys live here.  The ERROR payload's ``error_count`` is the FIRST failure's count,
    which is exactly 1 under the shipped ``+= 1`` and 2 under m61 (``+= 2``) - the final
    ``stats`` value would NOT separate those two, so the payload is the pin.  m60
    (``-= 1``) shows up as ``-1``.  ``record_pipeline_error`` is pinned with the EXACT
    shipped label ``"detection_connection_error"``: m63 (``error_type = None``) hands
    over ``None``, m64 (``categorize_exception(None, "detection")``) the
    ``"detection_processing_error"`` a ``None`` exception falls through to, and m65
    (``(e, None)``) the ``"None_connection_error"`` a ``None`` worker name produces.
    ``state`` is read INSIDE the L440 call - the only place L437 is observable, and m62
    (``state = None``) makes the shipped ``to_dict()`` raise ``AttributeError`` right
    there.  The ERROR record is pinned with ``exc_info=True`` and its traceback by
    IDENTITY, and the sleep with the shipped ``1.0``.
    """
    err = builtins.ConnectionError("detection queue connection reset by peer")
    run = Run(
        passes=[Pass(raises=err), Pass(raises=CANCEL())],
        clock=[900.0],
        use_streams=False,
        supervisor=None,
    )
    win(caplog)

    async with scripted(run) as d:
        stats = d.worker._stats.to_dict()
        states = list(run.states_at_error_call)

    assert states == [STATE_ERROR], (
        f"the L437 ERROR state must be live inside record_pipeline_error: {states!r}"
    )
    assert stats == {
        "items_processed": 0,
        "errors": 1,
        "last_processed_at": None,
        "state": STATE_RUNNING,
    }, f"stats mutated: {stats!r}"
    assert d.record_pipeline_error.call_args_list == [call(ERROR_LABEL)], (
        f"record_pipeline_error mutated: {d.record_pipeline_error.call_args_list!r}"
    )
    assert run.processed == [], "a failing pass processes nothing"
    pin_streams_info(
        caplog,
        msgs=[LEGACY_BANNER, CANCELLED_INFO, EXIT_INFO],
        payloads=[{}, {}, {"items_processed": 0}],
    )
    pin_levels(caplog, [LOOP_ERROR_TPL.format(err)], logging.ERROR, shipped_exc_info=True)
    pin_payloads(caplog, logging.ERROR, [{"error_count": 1, "error_type": ERROR_LABEL}])
    record = at(caplog, logging.ERROR)[0]
    assert record.exc_info is not None, "the shipped ERROR call passes exc_info=True"
    assert record.exc_info[0] is type(err), f"exc_info type mutated: {record.exc_info[0]!r}"
    assert record.exc_info[1] is err, f"exc_info value mutated: {record.exc_info[1]!r}"
    pin_levels(caplog, [], logging.WARNING)
    pin_levels(caplog, [], logging.DEBUG)
    assert run.sleeps == [ERROR_RETRY_DELAY], "the failed pass sleeps the shipped 1.0 s (L447)"
    assert run.clock_reads() == 2, "the error arm reads no clock at all"


async def test_the_loop_survives_two_connection_failures_and_reports_a_running_state(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Second, independently-valued route: two failures, then a real item.

    This is the leg that pins the error arm's SURVIVAL contract - the state must be back
    to ``running``, the loop must re-read the queue and process what it returns - so the
    ``+= 1`` family cannot be satisfied by a drive that only ever fails once.  Two
    failures give a SECOND value for ``error_count`` (2) and for ``errors``, which is what
    separates m60's ``-= 1`` (-1 then -2) and m61's ``+= 2`` (2 then 4) from shipped
    (1 then 2); the two failures carry different messages, and both are
    ``connection_error`` for a different reason (the L157-167 name tuple vs the
    ``"connect"`` in ``args[0]`` fallback), so a categorizer mutation cannot be explained
    by one input.
    """
    first = builtins.ConnectionError("detection stream read reset")
    second = builtins.ConnectionError("detection pool exhausted, cannot CONNECT")
    item = {"camera_id": "cam-after", "detection_id": 44, "file_path": "/f/after.jpg"}
    run = Run(
        passes=[Pass(raises=first), Pass(raises=second), Pass(item=item), Pass(raises=CANCEL())],
        clock=[1500.0],
        use_streams=False,
        supervisor=None,
        queue_name="detection_queue-b28",
        poll_timeout=7,
    )
    win(caplog)

    async with scripted(run) as d:
        stats = d.worker._stats.to_dict()
        states = list(run.states_at_error_call)

    assert states == [STATE_ERROR, STATE_ERROR], f"state at the metric call: {states!r}"
    assert stats == {
        "items_processed": 0,
        "errors": 2,
        "last_processed_at": None,
        "state": STATE_RUNNING,
    }, f"stats mutated: {stats!r}"
    assert d.record_pipeline_error.call_args_list == [call(ERROR_LABEL), call(ERROR_LABEL)], (
        f"record_pipeline_error mutated: {d.record_pipeline_error.call_args_list!r}"
    )
    assert run.processed == [item] and run.processed[0] is item, (
        f"the pass after a failure must process the item it reads: {run.processed!r}"
    )
    assert d.worker._redis.get_from_queue.await_args_list == [
        call("detection_queue-b28", timeout=7),
        call("detection_queue-b28", timeout=7),
        call("detection_queue-b28", timeout=7),
        call("detection_queue-b28", timeout=7),
    ], "the loop must re-read the queue after a failure"
    pin_streams_info(
        caplog,
        msgs=[LEGACY_BANNER, CANCELLED_INFO, EXIT_INFO],
        payloads=[{}, {}, {"items_processed": 0}],
    )
    pin_levels(
        caplog,
        [LOOP_ERROR_TPL.format(first), LOOP_ERROR_TPL.format(second)],
        logging.ERROR,
        shipped_exc_info=True,
    )
    pin_payloads(
        caplog,
        logging.ERROR,
        [
            {"error_count": 1, "error_type": ERROR_LABEL},
            {"error_count": 2, "error_type": ERROR_LABEL},
        ],
    )
    pin_levels(caplog, [], logging.WARNING)
    pin_levels(caplog, [], logging.DEBUG)
    assert run.sleeps == [ERROR_RETRY_DELAY, ERROR_RETRY_DELAY], run.sleeps


# =============================================================================
# B13) control: a failed STREAMS pass re-reads the stream (measured: this leg
#      kills nothing of its own - no survivor sits on the streams error arm)
# =============================================================================


async def test_a_failed_streams_pass_reads_the_stream_again_on_the_next_iteration(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Control on the streams arm: L435-448 must not leave the loop or the arm.

    Stated because the legacy legs above pin the error arm's re-loop; the streams arm
    takes the SAME handler, and a failure there must (a) not exit the loop, (b) not fall
    into the BLPOP arm, (c) leave the 30-second claim gate shut on the failed pass (the
    clock is frozen, so the extra iteration costs a gate read but no claim), and (d)
    still process the item the NEXT iteration returns.  Measured: this leg kills nothing
    on its own - no g10 survivor sits on the streams error path - and is kept as the
    non-vacuity guard for the streams legs' ``errors == 0`` pins.
    """
    err = RuntimeError("detection stream read refused")
    item = {"camera_id": "cam-post", "detection_id": 55, "file_path": "/f/post.jpg"}
    run = Run(
        passes=[Pass(raises=err), Pass(messages=[message("77-0", item)]), Pass(raises=CANCEL())],
        clock=[1600.0],
        use_streams=True,
        supervisor=None,
    )
    win(caplog)

    async with scripted(run) as d:
        stats = d.worker._stats.to_dict()

    name = consumer_name_of(d.worker)
    assert d.service is not None
    assert d.service.consume_detections.await_count == 3, (
        "the loop must re-read the stream after a failure"
    )
    assert d.service.claim_stale_messages.await_count == 0, (
        "the frozen clock cannot open the claim gate on any pass"
    )
    assert d.worker._redis.get_from_queue.await_count == 0, (
        "a failed streams pass must not fall into the legacy BLPOP arm"
    )
    assert run.processed == [item] and run.processed[0] is item
    assert run.acked == ["77-0"], f"acknowledge mutated: {run.acked!r}"
    assert stats == {
        "items_processed": 0,
        "errors": 1,
        "last_processed_at": None,
        "state": STATE_RUNNING,
    }, f"stats mutated: {stats!r}"
    # The label here is the L190 DEFAULT branch, not the L157-167 connection tuple the
    # two legacy error legs pin - the second value the shipped label can take, so the
    # metric call provably reads the categorizer rather than a constant.
    assert d.record_pipeline_error.call_args_list == [call(PROCESSING_LABEL)]
    pin_streams_info(
        caplog,
        msgs=[STREAMS_BANNER, CANCELLED_INFO, EXIT_INFO],
        payloads=[{"consumer_name": name}, {}, {"items_processed": 0}],
    )
    pin_levels(caplog, [LOOP_ERROR_TPL.format(err)], logging.ERROR, shipped_exc_info=True)
    pin_payloads(caplog, logging.ERROR, [{"error_count": 1, "error_type": PROCESSING_LABEL}])
    assert run.sleeps == [ERROR_RETRY_DELAY], run.sleeps
    assert run.clock_reads() == 5, (
        f"the L381 + L385 baselines plus one L399 read per iteration: {run.clock_reads()}"
    )
