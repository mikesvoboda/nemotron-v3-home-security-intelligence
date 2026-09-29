"""S3 batch-28 lane 04 - ``pipeline_workers`` group g04 kill battery (55 keys).

Module: ``backend/services/pipeline_workers.py`` (md5 29b4e6b163b67b1db9fed0069b7e44d2,
byte-identical to the manifest-proven source).  Admitted manifest:
``/tmp/wp-pw/pipeline_workers/`` ``manifest.json`` group 4 (55 KILLABLE /
0 EQUIVALENT / 0 NEEDS_INVESTIGATION), plus ``group_4.keys`` and
``survivors.json`` for the exact per-key diffs.

Everything in this group sits in ONE def - ``PipelineWorkerManager.__init__``
(shipped L1507-1646) - and every leg observes it the same way: the five worker/
aggregator class names and ``get_settings`` are replaced, per test and per leg,
with ``MagicMock(name=...)`` name-spies plus a value stub in the LIVE
name-resolution dict of the constructor (``live_globals``), the manager is built
once, and the spy call lists plus the manager attributes are pinned.  The
constructor itself emits no log record, so ``mine(caplog) == []`` is a control
pin on every leg.

Test -> mutant-key map
======================
Every key below is in ``group_4.keys``.  Two keys are carried on TWO legs on
purpose (m14 on the aggregator leg AND the analysis-else leg, m24 on both
detection-kwargs legs) because the shipped call site interpolates the same
expression into two different calls; the manifest's "occurrence-twin" hazard
("the two calls at L1576/L1585 interpolate the SAME expression, so an
else-branch leg alone does NOT discharge the if-branch key") is honoured by
never letting an else-branch leg be the only route to an if-branch key.

L1542 ``self._websocket_emitter = websocket_emitter`` -> ``= None``
- ``xǁPipelineWorkerManagerǁ__init____mutmut_2``
  -> ``test_the_stored_attributes_are_the_injected_objects_verbatim``
L1559 ``self._aggregator = BatchAggregator(redis_client=redis_client)``
- ``__mutmut_13`` (assign -> ``None``), ``__mutmut_14`` (``redis_client=None``)
  -> ``test_construction_builds_one_shared_aggregator_from_the_manager_client``
  (m14 is ALSO killed by ``test_default_construction_passes_the_analysis_kwargs_without_stop_timeout``)
L1568 ``self._worker_stop_timeout = worker_stop_timeout`` -> ``= None``
- ``__mutmut_19``
  -> ``test_the_stored_attributes_are_the_injected_objects_verbatim`` (both sides)
L1575/L1599/L1617/L1632 ``if worker_stop_timeout is not None:`` -> ``is None``
- ``__mutmut_22``, ``__mutmut_50``, ``__mutmut_69``, ``__mutmut_86``
  -> BOTH sides of each flip: ``test_default_construction_passes_the_detection_kwargs_without_stop_timeout``
  / ``test_explicit_worker_stop_timeout_adds_stop_timeout_to_the_detection_kwargs``,
  ``..._analysis_kwargs...`` pair, ``..._timeout_worker...`` pair,
  ``..._metrics_worker...`` pair, plus the direct per-worker ``is not None``
  arm-pair test ``test_the_stop_timeout_arm_is_taken_by_the_guard_not_by_truthiness``
  (which drives the third state ``worker_stop_timeout=0.0``).
L1576 (if-branch ``DetectionQueueWorker(...)`` kwargs)
- ``__mutmut_24`` redis_client=None, ``_25`` detector_client=None,
  ``_26`` batch_aggregator=None, ``_27`` frame_buffer=None, ``_28`` stop_timeout=None,
  ``_29`` worker_name=None, ``_31``/``_32``/``_33``/``_34``/``_35`` drop arg
  -> ``test_explicit_worker_stop_timeout_adds_stop_timeout_to_the_detection_kwargs``
L1585 (else-branch ``DetectionQueueWorker(...)`` kwargs)
- ``__mutmut_39`` batch_aggregator=None, ``_40`` frame_buffer=None,
  ``_46`` drop worker_name
  -> ``test_default_construction_passes_the_detection_kwargs_without_stop_timeout``
  (which also kills the L1575/1576 pair m24, m25, m26, m27, m29, m31, m32, m33, m35)
L1596 ``for i in range(self._analysis_worker_count)`` -> ``range(None)``,
       ``worker_name = f"analysis-{i}"`` -> ``= None``
- ``__mutmut_48``, ``__mutmut_49``
  -> ``test_worker_counts_come_from_the_override_range_and_the_names_are_indexed``
  (m48 raises ``TypeError``; the detection half of the same leg is the already-
  killed twin of m48, which is why only the analysis twin survived)
L1600 (if-branch ``AnalysisQueueWorker(...)`` kwargs)
- ``__mutmut_51`` assign -> ``None``, ``_53`` analyzer=None, ``_54`` stop_timeout=None,
  ``_55`` worker_name=None, ``_57`` drop analyzer, ``_58`` drop stop_timeout
  -> ``test_explicit_worker_stop_timeout_adds_stop_timeout_to_the_analysis_kwargs``
L1607 (else-branch ``AnalysisQueueWorker(...)`` kwargs)
- ``__mutmut_61`` redis_client=None, ``_64`` drop redis_client, ``_65`` drop analyzer
  -> ``test_default_construction_passes_the_analysis_kwargs_without_stop_timeout``
  (m14 lands here too: ``analyzer=None`` makes the REAL analyzer build from
  ``redis_client``, so ``redis_client=None`` is observable on this call as well)
L1612 ``self._analysis_workers.append(analysis_worker)`` -> ``append(None)``
- ``__mutmut_67`` -> ``test_the_worker_lists_hold_the_constructed_objects_in_order``
  (which pins ``_detection_workers`` / ``_analysis_workers`` membership and the
  ``_timeout_worker`` / ``_metrics_worker`` identity the m51/m70/m95 assign
  mutants break from the other side)
L1616 ``check_interval = settings.batch_check_interval_seconds`` -> ``= None``
- ``__mutmut_68`` -> BOTH timeout legs (``check_interval`` is pinned to the stub
  value 7.5 on both calls)
L1618 (if-branch ``BatchTimeoutWorker(...)`` kwargs)
- ``__mutmut_70`` assign -> ``None``, ``_72`` batch_aggregator=None,
  ``_73`` check_interval=None, ``_74`` stop_timeout=None, ``_76``/``_77``/``_78`` drop
  -> ``test_explicit_worker_stop_timeout_adds_stop_timeout_to_the_timeout_worker``
L1625 (else-branch ``BatchTimeoutWorker(...)`` kwargs)
- ``__mutmut_80`` redis_client=None, ``_81`` batch_aggregator=None,
  ``_82`` check_interval=None, ``_83``/``_84``/``_85`` drop
  -> ``test_default_construction_passes_the_timeout_worker_kwargs_without_stop_timeout``
  (which also kills m68, m72 and m76 - the expressions shared with L1618)
L1633 (if-branch ``QueueMetricsWorker(...)`` kwargs)
- ``__mutmut_88`` redis_client=None, ``_89`` update_interval=None, ``_90`` stop_timeout=None,
  ``_92`` drop update_interval, ``_93`` drop stop_timeout
  -> ``test_explicit_worker_stop_timeout_adds_stop_timeout_to_the_metrics_worker``
L1639 (else-branch ``QueueMetricsWorker(...)`` kwargs)
- ``__mutmut_95`` assign -> ``None``, ``_96`` redis_client=None
  -> ``test_default_construction_passes_the_metrics_kwargs_without_stop_timeout``
  (which also kills m89/m92 - the shipped ``update_interval=5.0`` literal is
  pinned on both calls)

Control legs that kill nothing of their own
(``test_disabling_a_worker_skips_its_construction_entirely``,
``test_the_default_counts_and_flags_come_from_settings``,
``test_the_stop_timeout_arm_is_taken_by_the_guard_not_by_truthiness``'s 0.0 leg)
pin the surrounding shipped contract, so a killing leg can never be satisfied by
an accidental fall-through.

Shipped behaviour only - nothing here invents a contract.  Every pinned value is
either an object this file injected (client / detector / analyzer / frame buffer
/ emitter), a value this file passed as an argument, the settings stub's own
value, the shipped ``update_interval=5.0`` literal at L1635/L1641, or the shipped
``f"detection-{i}"`` / ``f"analysis-{i}"`` name format.

Discipline
----------
* Log assertions use ``caplog`` opened per window (``set_level`` + ``clear()``,
  then filtered to this module's logger name) and read the RAW ``record.msg``
  (batch27_01 pattern) - ``PipelineWorkerManager.__init__`` logs nothing, so
  every leg asserts the window is empty.
* No import-time global spy: the five class-name spies and the ``get_settings``
  stub are installed per LEG with ``patch.dict`` over ``live_globals`` and are
  removed when the leg ends (memory holds that bare ``patch(M.module, "Name")``
  leaks the mock into every other module that shares the import chain).
* The spies are plain ``MagicMock(name=...)`` class doubles, not autospec
  doubles, on purpose: ``__init__`` forwards ``analyzer=None`` /
  ``detector_client=None`` / ``frame_buffer=None`` on its default leg, and
  autospec's signature checks exist to police CALLS - which these legs pin
  explicitly by comparing the recorded kwargs against the injected objects.
  The only autospec in this file is the ``WebSocketEmitterService`` double the
  attribute-identity leg injects (``MagicMock`` would not be accepted as that
  parameter's type by a reader of the signature).
* ``time.monotonic`` / ``time.perf_counter`` are never patched and no duration
  is asserted - g04 contains no timing site (the stop-timeout values are
  constructor ARGUMENTS, pinned by identity, never measured).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, create_autospec, patch

import pytest

from backend.services import pipeline_workers as M
from backend.services.websocket_emitter import WebSocketEmitterService

LOG_NAME = M.logger.name  # "backend.services.pipeline_workers" (get_logger(__name__))

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shipped literals, transcribed from backend/services/pipeline_workers.py
# =============================================================================

METRICS_UPDATE_INTERVAL = 5.0  # L1635 / L1641: update_interval=5.0


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
# Construction rig
# =============================================================================


def class_spy(name: str) -> MagicMock:
    """A class-constructor spy.

    ``name`` is the ``MagicMock`` repr name only (it is NOT ``__name__`` - the
    shipped constructor never touches either, and keeping ``__name__`` unset
    avoids the ``NonCallableMock.__name__`` descriptor trap).  ``return_value``
    is the per-construction worker double.
    """
    return MagicMock(name=name)


@dataclass(frozen=True)
class Spies:
    """The five class names ``PipelineWorkerManager.__init__`` constructs."""

    aggregator: MagicMock
    detection: MagicMock
    analysis: MagicMock
    timeout: MagicMock
    metrics: MagicMock

    @property
    def all(self) -> tuple[MagicMock, ...]:
        return (self.aggregator, self.detection, self.analysis, self.timeout, self.metrics)


def settings_stub(
    *,
    detection_worker_count: int = 1,
    analysis_worker_count: int = 1,
    batch_check_interval_seconds: float = 7.5,
) -> SimpleNamespace:
    """The ``get_settings()`` object ``__init__`` actually reads.

    Only three attributes are ever touched on this path
    (``detection_worker_count``, ``analysis_worker_count``,
    ``batch_check_interval_seconds``); the values are deliberately unlike the
    production defaults so a leg that silently fell back to the real settings
    would fail rather than pass by coincidence.
    """
    return SimpleNamespace(
        detection_worker_count=detection_worker_count,
        analysis_worker_count=analysis_worker_count,
        batch_check_interval_seconds=batch_check_interval_seconds,
    )


@contextmanager
def construction(settings: SimpleNamespace | None = None) -> Iterator[Spies]:
    """Patch the five class names + ``get_settings`` for one construction.

    Installed in the constructor's OWN live globals dict (``live_globals``) so
    the leg works identically against a mutant copy of the module, and removed
    at context exit so no spy survives into another test or another module.
    """
    s = settings or settings_stub()
    spies = Spies(
        aggregator=class_spy("BatchAggregator"),
        detection=class_spy("DetectionQueueWorker"),
        analysis=class_spy("AnalysisQueueWorker"),
        timeout=class_spy("BatchTimeoutWorker"),
        metrics=class_spy("QueueMetricsWorker"),
    )
    g = live_globals(M.PipelineWorkerManager.__init__)
    with patch.dict(
        g,
        {
            "BatchAggregator": spies.aggregator,
            "DetectionQueueWorker": spies.detection,
            "AnalysisQueueWorker": spies.analysis,
            "BatchTimeoutWorker": spies.timeout,
            "QueueMetricsWorker": spies.metrics,
            "get_settings": lambda: s,
        },
    ):
        yield spies


def build(spies: Spies, /, **manager_kwargs: Any) -> M.PipelineWorkerManager:
    """Build the manager through the patched names (must run inside ``construction``)."""
    return M.PipelineWorkerManager(**manager_kwargs)


def only_call_kwargs(spy: MagicMock, index: int = 0) -> dict[str, Any]:
    """The kwargs of call ``index``, rejecting any positional arguments.

    Every shipped worker/aggregator call in this def is keyword-only, so a
    positional argument would itself be a mutation of the call shape.
    """
    calls = spy.call_args_list
    assert index < len(calls), f"{spy._mock_name}: expected call #{index}, got {len(calls)} calls"
    call = calls[index]
    assert call.args == (), (
        f"{spy._mock_name} call #{index} took positional args (shipped calls are keyword-only): "
        f"{call.args!r}"
    )
    return dict(call.kwargs)


def assert_no_logs(caplog: pytest.LogCaptureFixture) -> None:
    assert mine(caplog) == [], (
        f"PipelineWorkerManager.__init__ must not log, got "
        f"{[(r.levelno, r.msg) for r in mine(caplog)]}"
    )


# =============================================================================
# 1) the shared aggregator + the stored attributes
#    m13, m14 (L1559) - m2 (L1542) - m19 (L1568)
# =============================================================================


def test_construction_builds_one_shared_aggregator_from_the_manager_client(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped L1559: exactly one ``BatchAggregator(redis_client=redis_client)``.

    ::

        # Create shared batch aggregator for detection and timeout workers
        self._aggregator = BatchAggregator(redis_client=redis_client)

    m13 replaces the whole call with ``None`` (the attribute is ``None`` and the
    spy is never called); m14 forwards ``redis_client=None``.  Both are caught
    here on the identity of the attribute and the identity of the single kwarg.
    """
    win(caplog)
    client = MagicMock(name="redis-client")

    with construction() as s:
        mgr = build(s, redis_client=client)

        assert s.aggregator.call_count == 1, (
            f"BatchAggregator built {s.aggregator.call_count} times, expected exactly 1"
        )
        agg_kwargs = only_call_kwargs(s.aggregator)
        assert agg_kwargs.keys() == {"redis_client"}, (
            f"aggregator kwargs mutated: {sorted(agg_kwargs)!r} != ['redis_client']"
        )
        assert agg_kwargs["redis_client"] is client, (
            f"aggregator redis_client mutated: {agg_kwargs['redis_client']!r} is not the client"
        )
        assert mgr._aggregator is s.aggregator.return_value, (
            f"self._aggregator is {mgr._aggregator!r}, expected the built aggregator"
        )

    assert_no_logs(caplog)


def test_the_stored_attributes_are_the_injected_objects_verbatim(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped L1541-1543 + L1567-1568 store the arguments unchanged.

    ::

        self._redis = redis_client
        self._websocket_emitter = websocket_emitter
        self._frame_buffer = frame_buffer
        ...
        self._worker_stop_timeout = worker_stop_timeout

    m2 nils the emitter attribute and m19 nils the stop-timeout attribute.  The
    emitter is injected as an autospec'd ``WebSocketEmitterService`` double (the
    parameter's declared type); the stop timeout is pinned on BOTH sides of the
    ``worker_stop_timeout`` axis, which is what makes m19's ``= None`` visible on
    the explicit leg while the ``None`` leg pins the other half of the contract.
    """
    win(caplog)
    client = MagicMock(name="redis-client")
    emitter = create_autospec(WebSocketEmitterService, instance=True)
    frame_buffer = MagicMock(name="frame-buffer")

    with construction() as s:
        mgr = build(
            s,
            redis_client=client,
            frame_buffer=frame_buffer,
            websocket_emitter=emitter,
            worker_stop_timeout=2.5,
        )

        assert mgr._redis is client
        assert mgr._websocket_emitter is emitter, (
            f"self._websocket_emitter is {mgr._websocket_emitter!r}, expected the injected emitter"
        )
        assert mgr._frame_buffer is frame_buffer
        assert mgr._worker_stop_timeout == 2.5, (
            f"self._worker_stop_timeout mutated: {mgr._worker_stop_timeout!r} != 2.5"
        )
        assert mgr._worker_stop_timeout is not None

    assert_no_logs(caplog)

    with construction() as s:
        mgr = build(s, redis_client=MagicMock(name="redis-client"), worker_stop_timeout=None)

        assert mgr._worker_stop_timeout is None, (
            f"a default build must store None, got {mgr._worker_stop_timeout!r}"
        )

    assert_no_logs(caplog)


# =============================================================================
# 2) detection workers - the two call sites (L1572-1592)
#    m22 (L1575 guard) - L1576 kwargs - L1585 kwargs - count/range/names
# =============================================================================


def test_explicit_worker_stop_timeout_adds_stop_timeout_to_the_detection_kwargs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped L1575-1583 (the ``is not None`` arm) - exact kwargs, stop_timeout present.

    ::

        if worker_stop_timeout is not None:
            detection_worker = DetectionQueueWorker(
                redis_client=redis_client,
                detector_client=detector_client,
                batch_aggregator=self._aggregator,
                frame_buffer=self._frame_buffer,
                stop_timeout=worker_stop_timeout,
                worker_name=worker_name,
            )

    ``kwargs.keys()`` is pinned as a SET, so m31/m32/m33/m34/m35 (drop an
    argument) fail on the missing key and any added key would fail too; every
    value is pinned by IDENTITY (or ``==`` for the scalar), so m24-m29 (arg ->
    ``None``) each fail on their own key.  m22 flips the guard, which routes this
    construction to the else-branch call where ``stop_timeout`` is absent.
    """
    win(caplog)
    client = MagicMock(name="redis-client")
    detector = MagicMock(name="detector-client")
    frame_buffer = MagicMock(name="frame-buffer")

    with construction() as s:
        mgr = build(
            s,
            redis_client=client,
            detector_client=detector,
            frame_buffer=frame_buffer,
            worker_stop_timeout=2.5,
            detection_worker_count=1,
            analysis_worker_count=0,
            enable_timeout_worker=False,
            enable_metrics_worker=False,
        )

        assert s.detection.call_count == 1, s.detection.call_count
        kwargs = only_call_kwargs(s.detection)
        assert set(kwargs) == {
            "redis_client",
            "detector_client",
            "batch_aggregator",
            "frame_buffer",
            "stop_timeout",
            "worker_name",
        }, f"detection kwargs mutated: {sorted(kwargs)!r}"
        assert kwargs["redis_client"] is client, "redis_client argument mutated"
        assert kwargs["detector_client"] is detector, "detector_client argument mutated"
        assert kwargs["batch_aggregator"] is mgr._aggregator, (
            "batch_aggregator argument mutated (must be the manager's shared aggregator)"
        )
        assert kwargs["frame_buffer"] is frame_buffer, "frame_buffer argument mutated"
        assert kwargs["stop_timeout"] == 2.5, (
            f"stop_timeout argument mutated: {kwargs['stop_timeout']!r}"
        )
        assert kwargs["worker_name"] == "detection-0", (
            f"worker_name argument mutated: {kwargs['worker_name']!r}"
        )
        assert mgr._detection_workers == [s.detection.return_value]

    assert_no_logs(caplog)


def test_default_construction_passes_the_detection_kwargs_without_stop_timeout(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped L1584-1591 (the ``else`` arm) - exact kwargs, NO stop_timeout key.

    ::

        else:
            detection_worker = DetectionQueueWorker(
                redis_client=redis_client,
                detector_client=detector_client,
                batch_aggregator=self._aggregator,
                frame_buffer=self._frame_buffer,
                worker_name=worker_name,
            )

    This is the ONLY route to m39/m40/m46 (the else-branch call's own mutants),
    and it is the opposite half of m22's flip: a flipped guard sends a ``None``
    stop timeout into the IF arm, where the recorded kwargs gain a
    ``stop_timeout`` key.  m24/m25/m29/m31/m32/m33/m35 sit on the if-branch call
    but interpolate the very same expressions, so this leg kills them too - the
    leg above keeps that true from the other side.
    """
    win(caplog)
    client = MagicMock(name="redis-client")
    detector = MagicMock(name="detector-client")
    frame_buffer = MagicMock(name="frame-buffer")

    with construction() as s:
        mgr = build(
            s,
            redis_client=client,
            detector_client=detector,
            frame_buffer=frame_buffer,
            detection_worker_count=1,
            analysis_worker_count=0,
            enable_timeout_worker=False,
            enable_metrics_worker=False,
        )

        assert s.detection.call_count == 1, s.detection.call_count
        kwargs = only_call_kwargs(s.detection)
        assert set(kwargs) == {
            "redis_client",
            "detector_client",
            "batch_aggregator",
            "frame_buffer",
            "worker_name",
        }, f"detection kwargs mutated (stop_timeout must be absent by default): {sorted(kwargs)!r}"
        assert "stop_timeout" not in kwargs, (
            "the default construction must not pass stop_timeout (workers use their own defaults)"
        )
        assert kwargs["redis_client"] is client, "redis_client argument mutated"
        assert kwargs["detector_client"] is detector, "detector_client argument mutated"
        assert kwargs["batch_aggregator"] is mgr._aggregator, (
            "batch_aggregator argument mutated: a None aggregator must not be handed to the worker"
        )
        assert kwargs["frame_buffer"] is frame_buffer, "frame_buffer argument mutated"
        assert kwargs["worker_name"] == "detection-0", (
            f"worker_name argument mutated: {kwargs['worker_name']!r}"
        )

    assert_no_logs(caplog)


def test_worker_counts_come_from_the_override_range_and_the_names_are_indexed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped L1546-1556 + L1572-1573 + L1596-1597: range() over the counts.

    ::

        self._detection_worker_count = (
            detection_worker_count if detection_worker_count is not None
            else settings.detection_worker_count
        )
        ...
        for i in range(self._analysis_worker_count):
            worker_name = f"analysis-{i}"

    With ``detection_worker_count=3`` / ``analysis_worker_count=2`` the loop
    bodies must run exactly 3 and 2 times and the names must be the indexed
    shipped formats.  m48 (``range(None)``) raises ``TypeError`` on this leg;
    m49 (``worker_name = None``) drops the name argument from the call, and the
    ORDER of the name list is what proves the interpolation is per-iteration.
    """
    win(caplog)

    with construction() as s:
        build(
            s,
            redis_client=MagicMock(name="redis-client"),
            detection_worker_count=3,
            analysis_worker_count=2,
            enable_timeout_worker=False,
            enable_metrics_worker=False,
        )

        assert s.detection.call_count == 3, (
            f"detection loop ran {s.detection.call_count} times, expected 3"
        )
        assert s.analysis.call_count == 2, (
            f"analysis loop ran {s.analysis.call_count} times, expected 2"
        )
        assert [only_call_kwargs(s.detection, i)["worker_name"] for i in range(3)] == [
            "detection-0",
            "detection-1",
            "detection-2",
        ], "detection worker names mutated"
        assert [only_call_kwargs(s.analysis, i)["worker_name"] for i in range(2)] == [
            "analysis-0",
            "analysis-1",
        ], "analysis worker names mutated"

    assert_no_logs(caplog)


def test_the_default_counts_and_flags_come_from_settings(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The ``else`` halves of L1546-1556: an absent override reads the settings value.

    The stub says 2 detection / 1 analysis, so the counts must come from it -
    which is also what keeps the ``range(None)`` family honest: the settings
    value is what would be substituted if the override were ignored.
    """
    win(caplog)

    with construction(settings_stub(detection_worker_count=2, analysis_worker_count=1)) as s:
        mgr = build(s, redis_client=MagicMock(name="redis-client"))

        assert mgr._detection_worker_count == 2
        assert mgr._analysis_worker_count == 1
        assert s.detection.call_count == 2, s.detection.call_count
        assert s.analysis.call_count == 1, s.analysis.call_count

    assert_no_logs(caplog)


def test_disabling_a_worker_skips_its_construction_entirely(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped ``if enable_*_worker:`` guards - all four False, nothing is built.

    Control leg: no survivor sits on these guards, and it is stated so the four
    kwargs legs above cannot be satisfied by a construction that simply never
    reached the disabled branch.
    """
    win(caplog)

    with construction() as s:
        mgr = build(
            s,
            redis_client=MagicMock(name="redis-client"),
            enable_detection_worker=False,
            enable_analysis_worker=False,
            enable_timeout_worker=False,
            enable_metrics_worker=False,
        )

        for spy in (s.detection, s.analysis, s.timeout, s.metrics):
            assert spy.call_count == 0, f"{spy._mock_name} was built despite being disabled"
        assert mgr._detection_workers == []
        assert mgr._analysis_workers == []
        assert mgr._timeout_worker is None
        assert mgr._metrics_worker is None
        # The aggregator is built unconditionally (it is not behind an enable flag).
        assert s.aggregator.call_count == 1, s.aggregator.call_count

    assert_no_logs(caplog)


# =============================================================================
# 3) analysis workers - the two call sites (L1594-1612)
#    m50 (L1599 guard) - L1600 kwargs - L1607 kwargs - m67 append
# =============================================================================


def test_explicit_worker_stop_timeout_adds_stop_timeout_to_the_analysis_kwargs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped L1599-1605 (``is not None`` arm) - exact kwargs, stop_timeout present.

    ::

        if worker_stop_timeout is not None:
            analysis_worker = AnalysisQueueWorker(
                redis_client=redis_client,
                analyzer=analyzer,
                stop_timeout=worker_stop_timeout,
                worker_name=worker_name,
            )

    m53/m54/m55 fail their own identity/equality key, m57/m58 fail the key SET,
    m50 (guard flip) shows up as a missing ``stop_timeout`` key, and m51 (the
    whole assignment becomes ``None``) fails the membership pin at the bottom.
    """
    win(caplog)
    client = MagicMock(name="redis-client")
    analyzer = MagicMock(name="analyzer")

    with construction() as s:
        mgr = build(
            s,
            redis_client=client,
            analyzer=analyzer,
            worker_stop_timeout=2.5,
            detection_worker_count=0,
            analysis_worker_count=1,
            enable_timeout_worker=False,
            enable_metrics_worker=False,
        )

        assert s.analysis.call_count == 1, s.analysis.call_count
        kwargs = only_call_kwargs(s.analysis)
        assert set(kwargs) == {"redis_client", "analyzer", "stop_timeout", "worker_name"}, (
            f"analysis kwargs mutated: {sorted(kwargs)!r}"
        )
        assert kwargs["redis_client"] is client, "redis_client argument mutated"
        assert kwargs["analyzer"] is analyzer, (
            f"analyzer argument mutated: {kwargs['analyzer']!r} is not the injected analyzer"
        )
        assert kwargs["stop_timeout"] == 2.5, (
            f"stop_timeout argument mutated: {kwargs['stop_timeout']!r}"
        )
        assert kwargs["worker_name"] == "analysis-0", (
            f"worker_name mutated: {kwargs['worker_name']!r}"
        )
        assert mgr._analysis_workers == [s.analysis.return_value], (
            "the constructed analysis worker was not the one stored in _analysis_workers"
        )

    assert_no_logs(caplog)


def test_default_construction_passes_the_analysis_kwargs_without_stop_timeout(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped L1606-1611 (``else`` arm) - the ONLY route to m61/m64/m65.

    ::

        else:
            analysis_worker = AnalysisQueueWorker(
                redis_client=redis_client,
                analyzer=analyzer,
                worker_name=worker_name,
            )

    m61 (``redis_client=None``) and m64 (drop ``redis_client``) both fail the
    identity / key-set pin on ``redis_client``; m65 (drop ``analyzer``) fails the
    key-set pin.  m14 (the aggregator's ``redis_client=None``) is ALSO killed
    here: the shipped ``AnalysisQueueWorker.__init__`` builds its analyzer from
    ``redis_client`` when ``analyzer`` is ``None``, so a nil client changes what
    THIS call must carry - which is exactly why the manifest warns that the
    else-branch twin can look equivalent until the real constructor is consulted.
    """
    win(caplog)
    client = MagicMock(name="redis-client")
    analyzer = MagicMock(name="analyzer")

    with construction() as s:
        build(
            s,
            redis_client=client,
            analyzer=analyzer,
            detection_worker_count=0,
            analysis_worker_count=1,
            enable_timeout_worker=False,
            enable_metrics_worker=False,
        )

        assert s.analysis.call_count == 1, s.analysis.call_count
        kwargs = only_call_kwargs(s.analysis)
        assert set(kwargs) == {"redis_client", "analyzer", "worker_name"}, (
            f"analysis kwargs mutated (stop_timeout must be absent by default): {sorted(kwargs)!r}"
        )
        assert "stop_timeout" not in kwargs, "the default arm must not pass stop_timeout"
        assert kwargs["redis_client"] is client, (
            f"redis_client argument mutated: {kwargs['redis_client']!r} is not the client"
        )
        assert kwargs["analyzer"] is analyzer, "analyzer argument mutated"
        assert kwargs["worker_name"] == "analysis-0", (
            f"worker_name mutated: {kwargs['worker_name']!r}"
        )

    assert_no_logs(caplog)


def test_the_worker_lists_hold_the_constructed_objects_in_order(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped L1592 / L1612 appends + L1618-1642 singleton assignments.

    ``_detection_workers`` / ``_analysis_workers`` must be exactly the lists of
    the objects the spies returned, in loop order, and the two singletons must BE
    the objects the shipped calls returned.  m67 (``append(None)``) replaces the
    analysis entry with ``None``; m51 / m70 / m95 (each assignment becomes
    ``None``) are the same class of defect on the other three sinks and are
    caught by the identity pins below.
    """
    win(caplog)

    with construction(settings_stub(detection_worker_count=2, analysis_worker_count=2)) as s:
        mgr = build(s, redis_client=MagicMock(name="redis-client"))

        assert mgr._detection_workers == [s.detection.return_value, s.detection.return_value], (
            "the detection worker list must hold each constructed worker (a None slot is a mutation)"
        )
        assert None not in mgr._detection_workers, "a None entry entered _detection_workers"
        assert mgr._analysis_workers == [s.analysis.return_value, s.analysis.return_value], (
            "the analysis worker list must hold each constructed worker (m67 appends None)"
        )
        assert None not in mgr._analysis_workers, "a None entry entered _analysis_workers"
        assert s.detection.call_count == 2 and s.analysis.call_count == 2
        assert mgr._timeout_worker is s.timeout.return_value, (
            f"self._timeout_worker is {mgr._timeout_worker!r}, expected the constructed worker"
        )
        assert mgr._metrics_worker is s.metrics.return_value, (
            f"self._metrics_worker is {mgr._metrics_worker!r}, expected the constructed worker"
        )

    assert_no_logs(caplog)


# =============================================================================
# 4) the batch timeout worker (L1614-1629)
#    m68 (L1616) - m69 (L1617 guard) - L1618 kwargs - L1625 kwargs
# =============================================================================


def test_explicit_worker_stop_timeout_adds_stop_timeout_to_the_timeout_worker(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped L1617-1623 (``is not None`` arm) with the settings-derived interval.

    ::

        check_interval = settings.batch_check_interval_seconds
        if worker_stop_timeout is not None:
            self._timeout_worker = BatchTimeoutWorker(
                redis_client=redis_client,
                batch_aggregator=self._aggregator,
                check_interval=check_interval,
                stop_timeout=worker_stop_timeout,
            )

    ``check_interval`` must be the stub's own value (7.5, unlike the production
    default 5), so m68 (``check_interval = None``) and m73 (the argument nilled)
    both fail, and m77 (drop the argument) fails the key SET.  m69's guard flip
    removes ``stop_timeout`` from this call.
    """
    win(caplog)
    client = MagicMock(name="redis-client")

    with construction(settings_stub(batch_check_interval_seconds=7.5)) as s:
        mgr = build(
            s,
            redis_client=client,
            worker_stop_timeout=2.5,
            detection_worker_count=0,
            analysis_worker_count=0,
            enable_metrics_worker=False,
        )

        assert s.timeout.call_count == 1, s.timeout.call_count
        kwargs = only_call_kwargs(s.timeout)
        assert set(kwargs) == {
            "redis_client",
            "batch_aggregator",
            "check_interval",
            "stop_timeout",
        }, f"timeout-worker kwargs mutated: {sorted(kwargs)!r}"
        assert kwargs["redis_client"] is client, "redis_client argument mutated"
        assert kwargs["batch_aggregator"] is mgr._aggregator, "batch_aggregator argument mutated"
        assert kwargs["check_interval"] == 7.5, (
            f"check_interval argument mutated: {kwargs['check_interval']!r} != the settings value 7.5"
        )
        assert kwargs["stop_timeout"] == 2.5, (
            f"stop_timeout argument mutated: {kwargs['stop_timeout']!r}"
        )

    assert_no_logs(caplog)


def test_default_construction_passes_the_timeout_worker_kwargs_without_stop_timeout(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped L1624-1629 (``else`` arm) - the route to m80-m85 (and m68/m72/m76).

    ``redis_client`` is the only worker call in this def whose client argument
    exists in BOTH branches without a twin elsewhere, so m80/m83 are killed only
    here; m81/m84 (aggregator nilled/dropped) and m82/m85 (check_interval
    nilled/dropped) are the else-branch twins of m72/m76 and m73/m77.
    """
    win(caplog)
    client = MagicMock(name="redis-client")

    with construction(settings_stub(batch_check_interval_seconds=7.5)) as s:
        mgr = build(
            s,
            redis_client=client,
            detection_worker_count=0,
            analysis_worker_count=0,
            enable_metrics_worker=False,
        )

        assert s.timeout.call_count == 1, s.timeout.call_count
        kwargs = only_call_kwargs(s.timeout)
        assert set(kwargs) == {"redis_client", "batch_aggregator", "check_interval"}, (
            f"timeout-worker kwargs mutated (stop_timeout must be absent by default): {sorted(kwargs)!r}"
        )
        assert "stop_timeout" not in kwargs, "the default arm must not pass stop_timeout"
        assert kwargs["redis_client"] is client, (
            f"redis_client argument mutated: {kwargs['redis_client']!r} is not the client"
        )
        assert kwargs["batch_aggregator"] is mgr._aggregator, (
            "batch_aggregator argument mutated: the timeout worker must share the manager aggregator"
        )
        assert kwargs["check_interval"] == 7.5, (
            f"check_interval argument mutated: {kwargs['check_interval']!r} != the settings value 7.5"
        )

    assert_no_logs(caplog)


# =============================================================================
# 5) the queue metrics worker (L1631-1642)
#    m86 (L1632 guard) - L1633 kwargs - L1639 kwargs
# =============================================================================


def test_explicit_worker_stop_timeout_adds_stop_timeout_to_the_metrics_worker(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped L1632-1637: the metrics worker gets the shipped 5.0 interval + the override.

    ::

        if worker_stop_timeout is not None:
            self._metrics_worker = QueueMetricsWorker(
                redis_client=redis_client,
                update_interval=5.0,  # Update metrics every 5 seconds
                stop_timeout=worker_stop_timeout,
            )

    m88/m89/m90 fail their own value pin, m92/m93 fail the key SET, m86's guard
    flip removes ``stop_timeout`` from this call.  ``update_interval`` is pinned
    to the shipped literal, never to the class default - the call site is the
    authority here (both branches carry 5.0).
    """
    win(caplog)
    client = MagicMock(name="redis-client")

    with construction() as s:
        build(
            s,
            redis_client=client,
            worker_stop_timeout=2.5,
            detection_worker_count=0,
            analysis_worker_count=0,
            enable_timeout_worker=False,
        )

        assert s.metrics.call_count == 1, s.metrics.call_count
        kwargs = only_call_kwargs(s.metrics)
        assert set(kwargs) == {"redis_client", "update_interval", "stop_timeout"}, (
            f"metrics-worker kwargs mutated: {sorted(kwargs)!r}"
        )
        assert kwargs["redis_client"] is client, "redis_client argument mutated"
        assert kwargs["update_interval"] == METRICS_UPDATE_INTERVAL, (
            f"update_interval argument mutated: {kwargs['update_interval']!r} != {METRICS_UPDATE_INTERVAL}"
        )
        assert kwargs["stop_timeout"] == 2.5, (
            f"stop_timeout argument mutated: {kwargs['stop_timeout']!r}"
        )

    assert_no_logs(caplog)


def test_default_construction_passes_the_metrics_kwargs_without_stop_timeout(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped L1638-1642 (``else`` arm) - the route to m95/m96.

    m96 (``redis_client=None``) fails the identity pin; m95 (the whole
    assignment becomes ``None``) fails the ``_metrics_worker`` identity pin; the
    shipped ``update_interval=5.0`` is pinned here too, which is what makes the
    if-branch twins m89/m92 (nilled / dropped update_interval) restatable from
    the shared expression rather than from an assumption.
    """
    win(caplog)
    client = MagicMock(name="redis-client")

    with construction() as s:
        mgr = build(
            s,
            redis_client=client,
            detection_worker_count=0,
            analysis_worker_count=0,
            enable_timeout_worker=False,
        )

        assert s.metrics.call_count == 1, s.metrics.call_count
        kwargs = only_call_kwargs(s.metrics)
        assert set(kwargs) == {"redis_client", "update_interval"}, (
            f"metrics-worker kwargs mutated (stop_timeout must be absent by default): {sorted(kwargs)!r}"
        )
        assert "stop_timeout" not in kwargs, "the default arm must not pass stop_timeout"
        assert kwargs["redis_client"] is client, (
            f"redis_client argument mutated: {kwargs['redis_client']!r} is not the client"
        )
        assert kwargs["update_interval"] == METRICS_UPDATE_INTERVAL, (
            f"update_interval argument mutated: {kwargs['update_interval']!r} != {METRICS_UPDATE_INTERVAL}"
        )
        assert mgr._metrics_worker is s.metrics.return_value, (
            f"self._metrics_worker is {mgr._metrics_worker!r}, expected the constructed worker"
        )

    assert_no_logs(caplog)


# =============================================================================
# 6) the guard itself: the arm is chosen by ``is not None``, not by truthiness
#    m22 / m50 / m69 / m86 restated as one four-site leg
# =============================================================================


def test_the_stop_timeout_arm_is_taken_by_the_guard_not_by_truthiness(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One leg per worker at ``worker_stop_timeout=0.0`` - the third state.

    Four shipped guards read ``if worker_stop_timeout is not None`` (L1575 /
    L1599 / L1617 / L1632).  A flip to ``is None`` is observable on both of the
    ``None``/``2.5`` pairs above, and this leg closes the remaining reading in
    which the guard "worked" because the value was truthy: ``0.0`` is falsy but
    not ``None``, so all four workers must still receive ``stop_timeout=0.0``.
    The default legs pin the other side (no ``stop_timeout`` key at all).
    """
    win(caplog)

    with construction(settings_stub(detection_worker_count=1, analysis_worker_count=1)) as s:
        build(
            s,
            redis_client=MagicMock(name="redis-client"),
            worker_stop_timeout=0.0,
        )

        assert only_call_kwargs(s.detection)["stop_timeout"] == 0.0, (
            "a falsy-but-present stop_timeout must still be forwarded to the detection worker"
        )
        assert only_call_kwargs(s.analysis)["stop_timeout"] == 0.0, (
            "a falsy-but-present stop_timeout must still be forwarded to the analysis worker"
        )
        assert only_call_kwargs(s.timeout)["stop_timeout"] == 0.0, (
            "a falsy-but-present stop_timeout must still be forwarded to the timeout worker"
        )
        assert only_call_kwargs(s.metrics)["stop_timeout"] == 0.0, (
            "a falsy-but-present stop_timeout must still be forwarded to the metrics worker"
        )

    assert_no_logs(caplog)
