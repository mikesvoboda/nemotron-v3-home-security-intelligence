"""S3 batch-28 lane 05 - ``pipeline_workers`` group g05 kill battery (54 keys).

Module: ``backend/services/pipeline_workers.py`` (md5 29b4e6b163b67b1db9fed0069b7e44d2,
byte-identical to the manifest-proven source).  Admitted manifest:
``/tmp/wp-pw/pipeline_workers/`` ``manifest.json`` group 5 (54 KILLABLE /
0 EQUIVALENT / 0 NEEDS_INVESTIGATION), plus ``group_5.keys`` and
``survivors.json`` for the exact per-key diffs.

Everything in this group sits in ONE def - ``PipelineWorkerManager.start``
(shipped L1811-1882).  The legs drive the REAL ``start()`` on a REAL manager
whose five constructed collaborators are per-leg name-spies in the LIVE
name-resolution dict of ``__init__`` (``live_globals``), so ``_detection_workers``
/ ``_analysis_workers`` / ``_timeout_worker`` / ``_metrics_worker`` are doubles
with an awaitable ``start`` while the code under test stays shipped.  The
WebSocket side is observed through an autospec'd ``WebSocketEmitterService``
instance, i.e. through the shipped ``broadcast_worker_event`` helper rather than
by replacing it, so the four ``worker.started`` payloads are read as the shipped
payload dicts.

Two shipped details are pre-set rather than exercised, both declared in the
manifest as another group's keys:
* ``_signal_handlers_installed`` is set True on the legs that call ``start()``
  (installing real SIGTERM/SIGINT handlers on the test loop would leak past the
  test); the "installed only when the flag is False" contract itself is g16's and
  is stated here as a control leg only.
* the per-worker ``start()`` bodies are not entered - the doubles' ``start`` are
  ``AsyncMock``s, which is what makes "each worker's start awaited" observable.

Test -> mutant-key map
======================
Every key below is in ``group_5.keys``.

L1822 ``logger.warning("PipelineWorkerManager already running")`` -> ``None`` /
``"XX...XX"`` / all-lower / all-upper
- ``xǁPipelineWorkerManagerǁstart__mutmut_1`` / ``_2`` / ``_3`` / ``_4``
  -> ``test_an_already_running_manager_warns_once_and_starts_nothing``
L1825-1829 ``logger.info("Starting PipelineWorkerManager", extra={detection_workers, analysis_workers})``
- ``__mutmut_5`` (msg -> ``None``), ``_9`` (``XX...XX``), ``_10`` (lower),
  ``_11`` (upper), ``_6`` (``extra=None``), ``_8`` (drop ``extra``), ``_12``/``_13``
  (``"detection_workers"`` -> ``XX``/upper), ``_14``/``_15``
  (``"analysis_workers"`` -> ``XX``/upper)
  -> ``test_a_fresh_start_logs_the_two_infos_with_the_worker_counts``
  (2 detection + 1 analysis so the two counts differ; the message and BOTH extra
  KEY names are pinned)
L1853 ``logger.info("PipelineWorkerManager started all workers")`` -> ``None`` /
``"XX...XX"`` / lower / upper
- ``__mutmut_23`` / ``_24`` / ``_25`` / ``_26``
  -> ``test_the_second_info_announces_that_all_workers_started``
L1856-1862 the detection ``broadcast_worker_event`` call
- ``__mutmut_28`` emitter -> ``None``, ``_29`` ``"worker.started"`` -> ``None``,
  ``_30`` ``f"detection_worker_{i}"`` -> ``None``, ``_31`` ``"detection"`` -> ``None``,
  ``_36``/``_37`` (``worker.started`` XX/upper), ``_38``/``_39``
  (``detection`` XX/upper)
  -> ``test_each_detection_worker_broadcasts_its_own_started_event``
L1863-1869 the analysis call
- ``__mutmut_41`` / ``_42`` / ``_43`` / ``_44`` / ``_49`` / ``_50`` / ``_51`` / ``_52``
  -> ``test_each_analysis_worker_broadcasts_its_own_started_event``
L1870-1876 the timeout-singleton call
- ``__mutmut_53`` / ``_54`` / ``_55`` / ``_56`` / ``_61`` / ``_62`` / ``_63`` /
  ``_64`` / ``_65`` / ``_66``
  -> ``test_the_timeout_worker_broadcasts_the_singleton_started_event``
L1877-1883 the metrics-singleton call
- ``__mutmut_67`` / ``_68`` / ``_69`` / ``_70`` / ``_75`` / ``_76`` / ``_77`` /
  ``_78`` / ``_79`` / ``_80``
  -> ``test_the_metrics_worker_broadcasts_the_singleton_started_event``
  (the emitter-slot ``arg->None`` mutants are caught by the MISSING emit -
  ``broadcast_worker_event`` returns before emitting when ``emitter is None`` -
  which is why each leg pins the emit COUNT as well as the payload)

Control legs that state the surrounding shipped contract - the TaskGroup
fan-out, the ``enable_*`` gates, the cross-type ORDER and the literal
four-broadcast count, the None-emitter arm, and the absence of any extra payload
key - so a killing leg can never be satisfied by an accidental fall-through:
``test_a_fresh_start_awaits_the_start_of_every_enabled_worker``,
``test_a_disabled_worker_is_neither_started_nor_broadcast``,
``test_the_started_events_arrive_in_the_shipped_order_with_no_extra_payload_key``,
``test_exactly_four_started_broadcasts_arrive_in_the_shipped_order``,
``test_a_manager_without_an_emitter_skips_every_broadcast``,
``test_signal_handlers_are_installed_only_when_the_flag_says_so``.  (Measured:
none of the 54 keys has its ONLY route through one of these six - every key's
failing set includes at least one of the dedicated per-site legs above - though
several of them join the failing set redundantly, which only strengthens the
matrix.)

Shipped behaviour only - nothing here invents a contract.  Every pinned string is
transcribed from the shipped file at the line quoted in the test that asserts it:
the four log texts (L1822/L1826/L1853 + the helper's L104/L127), the shipped
``"worker.started"`` event key, the shipped ``f"detection_worker_{i}"`` /
``f"analysis_worker_{i}"`` / ``"timeout_worker"`` / ``"metrics_worker"`` names,
the four ``worker_type`` labels, and the payload key set
``{worker_name, worker_type, timestamp}`` at L122-126.

Discipline
----------
* Log assertions use ``caplog`` opened per window (``set_level`` + ``clear()``,
  then filtered to this module's logger name) and read the RAW ``record.msg``
  plus ``record.args`` / ``record.exc_info`` / ``record.levelno`` (batch27_01
  pattern).  The ``extra`` values are read off the record attributes the shipped
  ``extra=`` dict creates.
* Mocks of real attributes are autospec'd (WP4.2 fast path): the emitter is
  ``create_autospec(WebSocketEmitterService, instance=True)``, so ``emit`` is an
  AsyncMock with the shipped signature.  The collaborator spies replace
  ``__init__``'s LOCAL names (``patch.dict`` over the live globals dict) rather
  than module attributes, and the signal-handler spy is a
  ``patch.object(manager, ...)`` on the instance double - none of these is a
  convertible module-attribute patch site.
* No import-time global spy: every spy is installed per test and removed at exit.
* ``time.monotonic`` / ``time.perf_counter`` are never patched and no duration is
  asserted; the broadcast payload's ``timestamp`` is pinned only as a parseable
  ISO-8601 string (the shipped ``datetime.now(UTC).isoformat()``).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import pytest

from backend.core.websocket.event_types import WebSocketEventType
from backend.services import pipeline_workers as M
from backend.services.websocket_emitter import WebSocketEmitterService

LOG_NAME = M.logger.name  # "backend.services.pipeline_workers" (get_logger(__name__))

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shipped literals, transcribed from backend/services/pipeline_workers.py
# =============================================================================

# L1822: logger.warning("PipelineWorkerManager already running")
ALREADY_RUNNING_WARNING = "PipelineWorkerManager already running"
# L1826: logger.info("Starting PipelineWorkerManager", extra={...})
STARTING_INFO = "Starting PipelineWorkerManager"
# L1853: logger.info("PipelineWorkerManager started all workers")
STARTED_ALL_INFO = "PipelineWorkerManager started all workers"
# L1859/L1866/L1873/L1880: the event type handed to broadcast_worker_event
STARTED_EVENT = "worker.started"
# L127: logger.debug(f"Broadcast worker event: {event_type}")
BROADCAST_DEBUG = "Broadcast worker event: worker.started"
# L104: the None-emitter arm of the shipped helper
SKIP_EMITTER_DEBUG = "WebSocket emitter not available, skipping worker.started broadcast"
# L122-126: payload = {"worker_name": ..., "worker_type": ..., "timestamp": ...}
PAYLOAD_KEYS = {"worker_name", "worker_type", "timestamp"}


# =============================================================================
# Observation helpers (batch27_01 pattern)
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
    """Assert the observable surface of one shipped log call.

    ``record.msg`` is the RAW message.  Every shipped site in this group passes a
    plain (already-constant) message, so ``args`` must stay empty and
    ``exc_info`` must be absent; the ``extra`` dict lands on the record itself and
    is asserted separately.
    """
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args for a constant message: {r.args!r}"
    assert r.exc_info is None, (
        f"exc_info present where the shipped call passes none: {r.exc_info!r}"
    )


def only(
    caplog: pytest.LogCaptureFixture,
    level: int,
    msg: str,
) -> logging.LogRecord:
    """Exactly one record at ``level`` in the window, matching every field."""
    recs = at(caplog, level)
    assert len(recs) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record from {LOG_NAME}, "
        f"got {[(r.levelno, r.msg) for r in recs]}"
    )
    pin_record(recs[0], msg=msg, level=level)
    return recs[0]


def live_globals(fn: Any) -> dict[str, Any]:
    """Name-resolution dict of the LIVE function object (three-worlds safe).

    * Pristine repo: ``fn.__globals__ is M.__dict__`` (identity fast path).
    * ep_plugin red-check lane: the variant body is exec'd into a snapshot COPY
      of the module dict and carries no ``__wrapped__`` - that copy is exactly the
      dict the variant body reads, so return it.
    * ``mutants/`` re-bank home: mutmut 3.8 wraps every function in its
      trampoline, whose ``__globals__`` is mutmut's OWN module dict while the
      shipped implementation sits behind ``__wrapped__`` with globals ==
      ``M.__dict__``.  The identity guard fires only there.
    """
    g = fn.__globals__
    if g is not M.__dict__:
        w = getattr(fn, "__wrapped__", None)
        if w is not None and w.__globals__ is M.__dict__:
            return M.__dict__
    return g


# =============================================================================
# Construction rig: the manager is REAL, its collaborators are per-leg spies
# =============================================================================


def class_spy(name: str) -> MagicMock:
    """A class-constructor spy handing out a FRESH worker double per construction.

    Each double carries an ``AsyncMock`` ``start`` so ``start()``'s TaskGroup
    fan-out is observable as an await count, and a ``running`` flag.  ``name`` is
    the ``MagicMock`` repr name only.
    """
    made: list[MagicMock] = []

    def factory(*_args: Any, **_kwargs: Any) -> MagicMock:
        worker = MagicMock(name=f"{name}-instance")
        worker.start = AsyncMock(name=f"{name}.start")
        worker.running = True
        made.append(worker)
        return worker

    spy = MagicMock(name=name, side_effect=factory)
    spy.created = made  # type: ignore[attr-defined]
    return spy


@dataclass(frozen=True)
class Rig:
    """The doubles a leg builds its manager with."""

    aggregator: MagicMock
    detection: MagicMock
    analysis: MagicMock
    timeout: MagicMock
    metrics: MagicMock
    emitter: Any
    manager: M.PipelineWorkerManager

    @property
    def workers(self) -> list[MagicMock]:
        """Every collaborator double that ``start()`` fans a task out to."""
        return [
            *self.detection.created,  # type: ignore[attr-defined]
            *self.analysis.created,  # type: ignore[attr-defined]
            *([self.manager._timeout_worker] if self.manager._timeout_worker else []),
            *([self.manager._metrics_worker] if self.manager._metrics_worker else []),
        ]


@contextmanager
def spied_names() -> Iterator[dict[str, MagicMock]]:
    """Install the five class-name spies in ``__init__``'s live globals dict."""
    spies = {
        "BatchAggregator": MagicMock(name="BatchAggregator"),
        "DetectionQueueWorker": class_spy("DetectionQueueWorker"),
        "AnalysisQueueWorker": class_spy("AnalysisQueueWorker"),
        "BatchTimeoutWorker": class_spy("BatchTimeoutWorker"),
        "QueueMetricsWorker": class_spy("QueueMetricsWorker"),
    }
    with patch.dict(live_globals(M.PipelineWorkerManager.__init__), spies):
        yield spies


def make_manager(
    spies: dict[str, MagicMock],
    *,
    detection_worker_count: int = 1,
    analysis_worker_count: int = 1,
    enable_detection_worker: bool = True,
    enable_analysis_worker: bool = True,
    enable_timeout_worker: bool = True,
    enable_metrics_worker: bool = True,
    with_emitter: bool = True,
) -> Rig:
    """Build a real ``PipelineWorkerManager`` through the spied names.

    ``_signal_handlers_installed`` is pre-set True so ``start()`` never touches
    the process-wide signal table (see the module docstring); the flag's own
    contract is g16's and is covered by a control leg.
    """
    emitter = create_autospec(WebSocketEmitterService, instance=True) if with_emitter else None
    manager = M.PipelineWorkerManager(
        redis_client=MagicMock(name="redis-client"),
        detector_client=MagicMock(name="detector-client"),
        analyzer=MagicMock(name="analyzer"),
        frame_buffer=MagicMock(name="frame-buffer"),
        websocket_emitter=emitter,
        detection_worker_count=detection_worker_count,
        analysis_worker_count=analysis_worker_count,
        enable_detection_worker=enable_detection_worker,
        enable_analysis_worker=enable_analysis_worker,
        enable_timeout_worker=enable_timeout_worker,
        enable_metrics_worker=enable_metrics_worker,
    )
    manager._signal_handlers_installed = True
    return Rig(
        aggregator=spies["BatchAggregator"],
        detection=spies["DetectionQueueWorker"],
        analysis=spies["AnalysisQueueWorker"],
        timeout=spies["BatchTimeoutWorker"],
        metrics=spies["QueueMetricsWorker"],
        emitter=emitter,
        manager=manager,
    )


def emit_calls(rig: Rig) -> list[tuple[Any, dict[str, Any]]]:
    """The shipped helper's ``emitter.emit(ws_event_type, payload)`` calls."""
    assert rig.emitter is not None, "this leg needs an emitter"
    out: list[tuple[Any, dict[str, Any]]] = []
    for call in rig.emitter.emit.await_args_list:
        assert not call.kwargs, (
            f"emitter.emit took keyword args, the shipped call is positional: {call!r}"
        )
        assert len(call.args) == 2, f"emitter.emit call shape mutated: {call!r}"
        out.append((call.args[0], call.args[1]))
    return out


def pin_payload(payload: Any, *, worker_name: str, worker_type: str) -> None:
    """Pin the shipped payload dict at broadcast_worker_event L122-126.

    ::

        payload = {
            "worker_name": worker_name,
            "worker_type": worker_type,
            "timestamp": datetime.now(UTC).isoformat(),
            **extra_fields,
        }

    The key SET is pinned too: ``start()`` passes no ``**extra_fields``, so an
    added key (or a missing one) is a payload mutation, and the timestamp must be
    the shipped ISO-8601 text.
    """
    assert isinstance(payload, dict), f"emit payload is not a dict: {payload!r}"
    assert set(payload) == PAYLOAD_KEYS, f"payload key set mutated: {sorted(payload)!r}"
    assert "reason" not in payload, "start() passes no extra fields, so 'reason' must be absent"
    assert payload["worker_name"] == worker_name, (
        f"payload worker_name mutated: {payload['worker_name']!r} != {worker_name!r}"
    )
    assert payload["worker_type"] == worker_type, (
        f"payload worker_type mutated: {payload['worker_type']!r} != {worker_type!r}"
    )
    stamp = payload["timestamp"]
    assert isinstance(stamp, str), f"timestamp must be the ISO text, got {stamp!r}"
    assert datetime.fromisoformat(stamp).tzinfo is UTC, f"naive timestamp: {stamp!r}"


# =============================================================================
# Fixtures (no import-time spies)
# =============================================================================


@pytest.fixture(autouse=True)
def clean_pipeline_manager_globals() -> Iterator[None]:
    """Cold global manager state before every test, restored afterwards.

    ``_pipeline_manager`` / ``_pipeline_manager_lock`` are module globals that
    persist across tests on an xdist worker; a pre-warmed global would let other
    modules' cached-manager fast path see the doubles this file builds.
    """
    g = live_globals(M.get_pipeline_manager)
    saved = (g.get("_pipeline_manager"), g.get("_pipeline_manager_lock"))
    g["_pipeline_manager"] = None
    g["_pipeline_manager_lock"] = None
    try:
        yield
    finally:
        g["_pipeline_manager"] = saved[0]
        g["_pipeline_manager_lock"] = saved[1]


# =============================================================================
# 1) the already-running arm (L1821-1823)
#    m1 (msg -> None), m2 (XX), m3 (lower), m4 (upper)
# =============================================================================


async def test_an_already_running_manager_warns_once_and_starts_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1821-1823 - ``if self._running:`` warns and returns.

    ::

        if self._running:
            logger.warning("PipelineWorkerManager already running")
            return

    The WARNING's text is the only observable of the whole call, so the four
    surviving variants (``None`` / ``XX...XX`` / lower / upper) are all caught by
    ``record.msg``.  The absence pins are the manifest's "creates no tasks / no
    broadcasts" leg: under a leg that fell through instead of returning, the
    worker starts, the two INFOs and the four broadcasts would all appear.
    """
    win(caplog)

    with spied_names() as spies:
        rig = make_manager(spies, detection_worker_count=1, analysis_worker_count=1)
        rig.manager._running = True

        assert await rig.manager.start() is None

        only(caplog, logging.WARNING, ALREADY_RUNNING_WARNING)
        assert at(caplog, logging.INFO) == [], (
            "the already-running arm returns before the Starting INFO"
        )
        for worker in rig.workers:
            assert worker.start.await_count == 0, (
                f"a worker was started by the already-running arm: {worker.start.await_count}"
            )
        assert rig.emitter.emit.await_count == 0, (
            f"the already-running arm broadcast {rig.emitter.emit.await_count} events"
        )


# =============================================================================
# 2) the two INFOs of a fresh start (L1825-1830, L1853)
#    m5/m9/m10/m11 + m6/m8 + m12/m13 + m14/m15 ; m23/m24/m25/m26
# =============================================================================


async def test_a_fresh_start_logs_the_two_infos_with_the_worker_counts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1825-1830 - the INFO message AND both ``extra`` key names.

    ::

        logger.info(
            "Starting PipelineWorkerManager",
            extra={
                "detection_workers": len(self._detection_workers),
                "analysis_workers": len(self._analysis_workers),
            },
        )

    2 detection + 1 analysis makes the two counts distinct, so a renamed key
    (``"XXdetection_workersXX"`` / ``"DETECTION_WORKERS"`` / the analysis pair)
    cannot be satisfied by reading the other attribute, and m6 (``extra=None``) /
    m8 (drop ``extra``) show up as missing attributes rather than wrong values.
    """
    win(caplog)

    with spied_names() as spies:
        rig = make_manager(spies, detection_worker_count=2, analysis_worker_count=1)
        await rig.manager.start()

    infos = at(caplog, logging.INFO)
    assert len(infos) >= 1, (
        f"a fresh start logged no INFO at all: {[(r.msg) for r in mine(caplog)]}"
    )
    first = infos[0]
    pin_record(first, msg=STARTING_INFO, level=logging.INFO)
    assert hasattr(first, "detection_workers"), (
        f"the Starting INFO lost its detection_workers extra: {sorted(vars(first))!r}"
    )
    assert hasattr(first, "analysis_workers"), (
        f"the Starting INFO lost its analysis_workers extra: {sorted(vars(first))!r}"
    )
    assert first.detection_workers == 2, (
        f"detection_workers extra mutated: {first.detection_workers!r} != 2"
    )
    assert first.analysis_workers == 1, (
        f"analysis_workers extra mutated: {first.analysis_workers!r} != 1"
    )
    assert first.detection_workers == len(rig.manager._detection_workers)
    assert first.analysis_workers == len(rig.manager._analysis_workers)


async def test_the_second_info_announces_that_all_workers_started(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1853 - the INFO between the TaskGroup and the broadcasts.

    The four survivors on that line are the message variants, so the text is
    pinned character-for-character, and its POSITION (the second INFO, after the
    fan-out and before the first broadcast) is pinned by the record sequence.
    """
    win(caplog)

    with spied_names() as spies:
        rig = make_manager(spies, detection_worker_count=1, analysis_worker_count=1)
        await rig.manager.start()

    infos = at(caplog, logging.INFO)
    assert len(infos) == 2, f"expected exactly 2 INFOs, got {[r.msg for r in infos]}"
    pin_record(infos[0], msg=STARTING_INFO, level=logging.INFO)
    pin_record(infos[1], msg=STARTED_ALL_INFO, level=logging.INFO)
    assert at(caplog, logging.WARNING) == [], "a fresh start must not warn"


# =============================================================================
# 3) the TaskGroup fan-out (L1840-1851) - control legs
# =============================================================================


async def test_a_fresh_start_awaits_the_start_of_every_enabled_worker(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1840-1851 - one task per enabled worker, and ``running`` flips.

    Control leg: it is what proves the broadcast legs below really started
    workers (so an emit cannot come from an unrelated path), and it states the
    ``self._running = True`` side effect the already-running leg depends on.
    """
    win(caplog)

    with spied_names() as spies:
        rig = make_manager(spies, detection_worker_count=2, analysis_worker_count=2)
        assert rig.manager.running is False
        await rig.manager.start()

        assert rig.manager.running is True, "_running must be True after a fresh start"
        assert rig.manager.accepting is True, "start() does not touch the accepting flag"
        for worker in rig.workers:
            assert worker.start.await_count == 1, (
                f"{worker._mock_name} start awaited {worker.start.await_count} times, expected 1"
            )
        assert len(rig.detection.created) == 2 and len(rig.analysis.created) == 2


async def test_a_disabled_worker_is_neither_started_nor_broadcast(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped ``if self._timeout_worker:`` / ``if self._metrics_worker:`` gates.

    With the two singletons disabled the emits are exactly the loop-type ones,
    which is what makes the singleton legs below (one emit each, named) the only
    route to their keys.
    """
    win(caplog)

    with spied_names() as spies:
        rig = make_manager(
            spies,
            detection_worker_count=1,
            analysis_worker_count=1,
            enable_timeout_worker=False,
            enable_metrics_worker=False,
        )
        await rig.manager.start()

        assert rig.manager._timeout_worker is None
        assert rig.manager._metrics_worker is None
        emits = emit_calls(rig)
        assert len(emits) == 2, f"expected 2 emits (detection + analysis), got {len(emits)}"
        assert [p["worker_type"] for _e, p in emits] == ["detection", "analysis"]
        assert rig.emitter.emit.await_count == 2


async def test_signal_handlers_are_installed_only_when_the_flag_says_so(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1834-1836 - the ``if not self._signal_handlers_installed:`` guard.

    Control leg for g16's key (the manifest assigns the signal-handler contract
    there).  The method is spied AUTOSPEC'd on the INSTANCE (WP4.2 fast path:
    signature enforced), so no process-wide signal handler is ever installed by
    this file and the shipped zero-argument signature is policed.
    """
    win(caplog)

    with spied_names() as spies:
        rig = make_manager(spies)
        rig.manager._signal_handlers_installed = False
        with patch.object(rig.manager, "_install_signal_handlers", autospec=True) as install:
            await rig.manager.start()
        assert install.call_count == 1, (
            f"start() installed signal handlers {install.call_count} times, expected 1"
        )


# =============================================================================
# 4) the four worker.started broadcasts (L1855-1883)
# =============================================================================


async def test_each_detection_worker_broadcasts_its_own_started_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1855-1862 - one WORKER_STARTED emit per detection worker.

    ::

        for i, _detection_worker in enumerate(self._detection_workers):
            await broadcast_worker_event(
                self._websocket_emitter,
                "worker.started",
                f"detection_worker_{i}",
                "detection",
            )

    The emits are read at the emitter, i.e. AFTER the shipped helper has mapped
    ``"worker.started"`` to ``WebSocketEventType.WORKER_STARTED`` and built the
    payload:

    * ``_28`` (emitter -> ``None``) makes the helper log the skip DEBUG and emit
      NOTHING -> the count pin fails;
    * ``_29`` / ``_36`` / ``_37`` (the event type -> ``None`` / XX / upper) miss
      the helper's ``event_type_map`` -> the helper warns and emits nothing;
    * ``_30`` (name -> ``None``) and ``_38`` / ``_39`` (``"detection"`` -> XX /
      upper) land in the payload and fail the value pins;
    * ``_31`` (``"detection"`` -> ``None``) fails the ``worker_type`` pin.
    """
    win(caplog)

    with spied_names() as spies:
        rig = make_manager(
            spies,
            detection_worker_count=2,
            analysis_worker_count=0,
            enable_analysis_worker=False,
            enable_timeout_worker=False,
            enable_metrics_worker=False,
        )
        await rig.manager.start()

        emits = emit_calls(rig)
        assert len(emits) == 2, (
            f"expected one WORKER_STARTED emit per detection worker (2), got {len(emits)}"
        )
        for index, (event_type, payload) in enumerate(emits):
            assert event_type is WebSocketEventType.WORKER_STARTED, (
                f"emit #{index} event type mutated: {event_type!r}"
            )
            pin_payload(payload, worker_name=f"detection_worker_{index}", worker_type="detection")

    debugs = at(caplog, logging.DEBUG)
    assert len(debugs) == 2, (
        f"one helper DEBUG per broadcast expected (2 emits), got {[r.msg for r in debugs]}"
    )
    for rec in debugs:
        pin_record(rec, msg=BROADCAST_DEBUG, level=logging.DEBUG)
    assert at(caplog, logging.WARNING) == [], (
        "an unknown mapped event type would warn - the shipped call must not"
    )


async def test_each_analysis_worker_broadcasts_its_own_started_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1863-1869 - the analysis loop, ``f"analysis_worker_{i}"`` / ``"analysis"``.

    Kills ``_41`` (emitter -> None), ``_42`` (event type -> None), ``_43``
    (worker name -> None), ``_44`` (``"analysis"`` -> None) and the XX/upper
    variants ``_49``/``_50`` (event type) and ``_51``/``_52`` (worker type).
    """
    win(caplog)

    with spied_names() as spies:
        rig = make_manager(
            spies,
            detection_worker_count=0,
            analysis_worker_count=2,
            enable_detection_worker=False,
            enable_timeout_worker=False,
            enable_metrics_worker=False,
        )
        await rig.manager.start()

        emits = emit_calls(rig)
        assert len(emits) == 2, f"expected 2 analysis emits, got {len(emits)}"
        for index, (event_type, payload) in enumerate(emits):
            assert event_type is WebSocketEventType.WORKER_STARTED, (
                f"emit #{index} event type mutated: {event_type!r}"
            )
            pin_payload(payload, worker_name=f"analysis_worker_{index}", worker_type="analysis")

    assert at(caplog, logging.WARNING) == [], (
        "an unmapped event type would warn - the shipped call must not"
    )


async def test_the_timeout_worker_broadcasts_the_singleton_started_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1870-1876 - the literal ``"timeout_worker"`` / ``"timeout"`` pair.

    Kills ``_53``-``_56`` (each positional argument -> ``None``) and the six
    string variants ``_61``/``_62`` (event type), ``_63``/``_64`` (worker name),
    ``_65``/``_66`` (worker type).  The manager is built with every loop-type
    worker disabled, so this leg's emit list is exactly the singleton's.
    """
    win(caplog)

    with spied_names() as spies:
        rig = make_manager(
            spies,
            enable_detection_worker=False,
            enable_analysis_worker=False,
            enable_metrics_worker=False,
        )
        await rig.manager.start()

        emits = emit_calls(rig)
        assert len(emits) == 1, f"expected exactly the timeout singleton emit, got {len(emits)}"
        event_type, payload = emits[0]
        assert event_type is WebSocketEventType.WORKER_STARTED, (
            f"event type mutated: {event_type!r}"
        )
        pin_payload(payload, worker_name="timeout_worker", worker_type="timeout")

    assert at(caplog, logging.WARNING) == []


async def test_the_metrics_worker_broadcasts_the_singleton_started_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1877-1883 - the literal ``"metrics_worker"`` / ``"metrics"`` pair.

    Kills ``_67``-``_70`` and the six string variants ``_75``/``_76`` (event
    type), ``_77``/``_78`` (worker name), ``_79``/``_80`` (worker type).
    """
    win(caplog)

    with spied_names() as spies:
        rig = make_manager(
            spies,
            enable_detection_worker=False,
            enable_analysis_worker=False,
            enable_timeout_worker=False,
        )
        await rig.manager.start()

        emits = emit_calls(rig)
        assert len(emits) == 1, f"expected exactly the metrics singleton emit, got {len(emits)}"
        event_type, payload = emits[0]
        assert event_type is WebSocketEventType.WORKER_STARTED, (
            f"event type mutated: {event_type!r}"
        )
        pin_payload(payload, worker_name="metrics_worker", worker_type="metrics")

    assert at(caplog, logging.WARNING) == []


async def test_the_started_events_arrive_in_the_shipped_order_with_no_extra_payload_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The full cross-type sequence: 2 detection, 1 analysis, timeout, metrics.

    The manifest's order leg - ``detection_worker_0``/``detection``,
    ``detection_worker_1``/``detection``, ``analysis_worker_0``/``analysis``,
    ``timeout_worker``/``timeout``, ``metrics_worker``/``metrics`` - with every
    payload limited to the three shipped keys.  Order is load-bearing here and
    nowhere else, so this leg is stated even though the four per-type legs above
    already pin each site's own values.
    """
    win(caplog)

    with spied_names() as spies:
        rig = make_manager(spies, detection_worker_count=2, analysis_worker_count=1)
        await rig.manager.start()

        emits = emit_calls(rig)
        assert len(emits) == 5, f"expected 5 WORKER_STARTED emits, got {len(emits)}"
        assert [(p["worker_name"], p["worker_type"]) for _event, p in emits] == [
            ("detection_worker_0", "detection"),
            ("detection_worker_1", "detection"),
            ("analysis_worker_0", "analysis"),
            ("timeout_worker", "timeout"),
            ("metrics_worker", "metrics"),
        ], "the started-broadcast sequence mutated"
        for _event, payload in emits:
            assert set(payload) == PAYLOAD_KEYS, f"payload key set mutated: {sorted(payload)!r}"
            assert "reason" not in payload


async def test_exactly_four_started_broadcasts_arrive_in_the_shipped_order(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The manifest's verbatim order leg: one worker each -> EXACTLY 4 emits.

    ``detection_worker_0``/``detection``, ``analysis_worker_0``/``analysis``,
    ``timeout_worker``/``timeout``, ``metrics_worker``/``metrics`` - the shipped
    default configuration (1 detection, 1 analysis, both singletons on, emitter
    present), each payload limited to the three shipped keys with no ``reason``.
    ``test_the_started_events_arrive_in_the_shipped_order_with_no_extra_payload_key``
    above runs the same sequence with 2 detection workers to also pin the
    ``f"detection_worker_{i}"`` interpolation; this leg is the literal
    four-broadcast reading, so the COUNT is the whole assertion's subject.
    """
    win(caplog)

    with spied_names() as spies:
        rig = make_manager(spies)
        await rig.manager.start()

        emits = emit_calls(rig)
        assert len(emits) == 4, (
            f"the shipped default rig must broadcast exactly 4 worker.started events, got {len(emits)}"
        )
        sequence = [
            ("detection_worker_0", "detection"),
            ("analysis_worker_0", "analysis"),
            ("timeout_worker", "timeout"),
            ("metrics_worker", "metrics"),
        ]
        for (name, wtype), (event_type, payload) in zip(sequence, emits, strict=True):
            assert event_type is WebSocketEventType.WORKER_STARTED, (
                f"{name}: event type mutated: {event_type!r}"
            )
            pin_payload(payload, worker_name=name, worker_type=wtype)

    assert len(at(caplog, logging.INFO)) == 2, "the two start INFOs and nothing more"


async def test_a_manager_without_an_emitter_skips_every_broadcast(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The None-emitter arm of the shipped helper, stated as the mirror of ``_28``.

    ``websocket_emitter=None`` is the shipped default, and the helper's
    ``if emitter is None:`` arm (L103-105) is what an emitter-slot mutant turns
    EVERY call into - one skip DEBUG per call and 0 emits.  Pinning that shape
    here is what makes the emit-count pins in the four legs above the
    discriminator rather than an accident of the double.

    The default rig is 1 detection + 1 analysis + timeout + metrics = 4 calls.
    """
    win(caplog)

    with spied_names() as spies:
        rig = make_manager(
            spies,
            detection_worker_count=1,
            analysis_worker_count=1,
            with_emitter=False,
        )
        await rig.manager.start()

        assert rig.manager._websocket_emitter is None
        assert at(caplog, logging.WARNING) == []
        assert len(at(caplog, logging.INFO)) == 2, "the two start INFOs still fire"

    debugs = [r.msg for r in at(caplog, logging.DEBUG)]
    assert debugs == [SKIP_EMITTER_DEBUG] * 4, (
        f"every call must fall into the helper's None-emitter arm: {debugs!r}"
    )
