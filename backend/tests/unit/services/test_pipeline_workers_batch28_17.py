"""S3 batch-28 lane 17 - ``pipeline_workers`` group g17 kill battery (17 keys).

Module: ``backend/services/pipeline_workers.py`` (git blob 74649fd3 - byte-identical
to the manifest-proven source).  Admitted manifest: ``/tmp/wp-pw/pipeline_workers/``
``manifest.json`` group 17 (17 KILLABLE / 0 EQUIVALENT / 0 NEEDS_INVESTIGATION),
plus ``group_17.keys`` and ``survivors.json`` for the exact per-key diffs.

Test -> mutant-key map
======================
Every key below is in ``group_17.keys``.  Occurrence-twin check: each g17 diff
``(function, before, after, line)`` tuple was searched across all 959 survivors -
no pair occurs anywhere else, so NO twin keys are carried here and none of these
keys is claimed by another group.  (Cross-group near-neighbours deliberately NOT
claimed: the ``PipelineWorkerManager.drain_queues`` default mutant
``xǁPipelineWorkerManagerǁdrain_queues__mutmut_1`` is g16's key, and the
L2041 ``logger.info("Global pipeline worker manager initialized")`` message
mutants are not survivors at all.)

- ``x_broadcast_worker_event__mutmut_2``
  L104 ``logger.debug(f"WebSocket emitter not available, skipping {event_type}
  broadcast")`` -> ``logger.debug(None)``
  -> ``test_none_emitter_logs_the_skipped_broadcast_debug`` (all 3 params)
- ``x_categorize_exception__mutmut_19``  L169 ``Or`` -> ``And``
- ``x_categorize_exception__mutmut_20``  L169 ``type(e).__name__`` -> ``type(None).__name__``
  -> m19: ``test_timeout_expired_name_that_is_not_a_timeout_error_subclass``,
     ``test_timeout_error_name_beats_its_validation_base_class``,
     ``test_builtin_timeout_error_and_its_subclass_are_the_timeout_family``,
     ``test_timeout_name_branch_fires_before_the_falsy_module_guard``,
     ``test_worker_name_is_the_label_prefix_verbatim``;
     m20: the same five minus ``test_builtin_timeout_error_and_its_subclass...``
     (that one travels the ``isinstance`` half, which m20 leaves intact)
- ``x_categorize_exception__mutmut_23``  L185 ``if type(e).__module__`` ->
  ``if type(None).__module__`` (``"builtins"`` - permanently truthy, so the guard
  stops protecting ``.lower()`` from a falsy module)
  -> ``test_falsy_module_short_circuits_the_redis_guard_to_processing`` (SOLE route)
- ``x_categorize_exception__mutmut_24``  L185 ``"redis"`` -> ``"XXredisXX"``
- ``x_categorize_exception__mutmut_25``  L185 ``"redis"`` -> ``"REDIS"``
- ``x_categorize_exception__mutmut_27``  L185 ``.lower()`` -> ``.upper()``
- ``x_categorize_exception__mutmut_28``  L185 (in the ``in``) ``type(e).__module__``
  -> ``type(None).__module__``
  -> all four: ``test_module_name_containing_lowercase_redis_is_redis_error``
     (mixed-case module ``"MyRedisPool.Client"``),
     ``test_module_name_containing_uppercase_redis_is_redis_error``
     (upper-case module ``"Cache.REDIS.IO"``) and
     ``test_worker_name_is_the_label_prefix_verbatim`` - the two module legs
     together leave each of the four variants no input on which it agrees with
     shipped (m25/m27 pass the upper-case leg alone, m24/m28 fail both).
- ``x_drain_queues__mutmut_1``
  L2061 ``async def drain_queues(timeout: float = 30.0)`` -> ``31.0``
  -> ``test_default_timeout_is_the_shipped_thirty_seconds`` (SOLE route)
- ``x_get_pipeline_manager__mutmut_1``
  L2032 ``if _pipeline_manager is not None:`` -> ``is None`` (a cold global takes
  the fast path and returns the ``None`` global itself)
  -> ``test_first_call_builds_once_with_the_client_and_logs_init_info``
     (the discriminator), ``test_second_call_returns_the_cached_manager_and_logs_nothing``
     (the memoisation contract the flip breaks)
- ``x_stop_pipeline_manager__mutmut_3`` / ``_4`` / ``_5`` / ``_6``
  L2058 ``logger.info("Global pipeline worker manager stopped")`` ->
  ``logger.info(None)`` / ``"XXGlobal pipeline worker manager stoppedXX"`` /
  all-lower / all-upper
  -> all four: ``test_stop_awaits_stop_clears_the_global_and_logs_the_stopped_info``
     and ``test_stop_is_idempotent_across_two_calls``
- ``xǁAnalysisQueueWorkerǁ_get_broadcaster__mutmut_1``
  L821 ``if self._broadcaster is None:`` -> ``is not None`` (guard flip)
  -> ``test_first_call_awaits_the_factory_with_the_workers_redis_client``,
     ``test_second_call_is_memoised_and_never_re_awaits``,
     ``test_preseeded_broadcaster_is_returned_without_calling_the_factory``,
     ``test_factory_failure_is_swallowed_into_a_debug_and_returns_none``
     (under the flip the arm never runs, so its DEBUG never fires)
- ``xǁAnalysisQueueWorkerǁ_get_broadcaster__mutmut_2``
  L825 ``self._broadcaster = await get_broadcaster(self._redis)`` -> ``= None``
  -> ``test_first_call_awaits_the_factory_with_the_workers_redis_client``,
     ``test_second_call_is_memoised_and_never_re_awaits``,
     ``test_factory_failure_is_swallowed_into_a_debug_and_returns_none``
- ``xǁAnalysisQueueWorkerǁ_get_broadcaster__mutmut_3``
  L825 ``get_broadcaster(self._redis)`` -> ``get_broadcaster(None)``
  -> ``test_first_call_awaits_the_factory_with_the_workers_redis_client``
     (SOLE route: arg identity is the ONLY observable - m3 still returns the
     broadcaster object, so no return-value leg can see it)

Every leg above is the MEASURED failing set of the in-tree mutant run (each key
built from its exact survivor diff in a symlinked copy of this tree, battery run
against it: 17/17 KILLED, and pristine 31/31 green serially, under xdist, and
co-run with the pre-existing test_pipeline_workers*.py modules).

Control legs that kill nothing of their own
(``test_connection_error_names_are_the_connection_family``,
``test_oserror_name_beats_the_redis_module_branch``,
``test_args_first_element_containing_connect_is_the_connection_family``,
``test_memory_error_is_the_memory_family``,
``test_validation_bases_are_the_validation_family``,
``test_generic_exception_falls_back_to_processing``,
``test_stop_with_no_manager_is_silent_and_leaves_the_global_none``,
``test_explicit_timeout_is_forwarded_unchanged``,
``test_no_manager_returns_zero_and_logs_the_debug``) pin the other shipped arms of
the same defs, so a killing leg can never be satisfied by an accidental
fall-through and the ordered contract is stated in full.

Shipped behaviour only - nothing here invents a contract.  Every pinned string is
transcribed from the shipped file at the line quoted in the test that asserts it,
and every value an assertion depends on is injected by this file (a chosen
``event_type``, a crafted exception class with a chosen ``__name__`` /
``__module__``, a mocked manager constructor, a mocked broadcaster factory).

Discipline
----------
* Log assertions use ``caplog`` opened per window (``set_level`` + ``clear()``,
  then filtered to this module's logger name) and read the RAW ``record.msg``
  plus ``record.args`` / ``record.exc_info`` / ``record.levelno`` (batch27_01
  pattern).  ``time.monotonic`` / ``time.perf_counter`` are never patched and no
  duration is asserted - g17 contains no timing site.
* Mocks of real attributes are autospec'd (WP4.2 fast path): the manager double
  comes from ``create_autospec(PipelineWorkerManager)`` (signature enforced; its
  ``stop`` / ``drain_queues`` are AsyncMock), the broadcaster factory from
  ``patch(..., autospec=True)``.
* No import-time global spy: capture is fixture-scoped and every global-state
  double is installed per test with ``patch.dict`` (the shipped
  ``reset_pipeline_manager_state()`` helper is NOT used because it mutates only
  the pristine module dict - see ``live_globals``).
* Module globals and the manager constructor are patched through the LIVE
  name-resolution dict of the function under test (``live_globals``), the
  three-worlds-safe pattern proven in
  ``test_enrichment_pipeline_batch26_{11,20}.py``.
"""

from __future__ import annotations

import asyncio
import builtins
import logging
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, create_autospec, patch

import pytest

from backend.services import pipeline_workers as M
from backend.services.pipeline_workers import PipelineWorkerManager

LOG_NAME = M.logger.name  # "backend.services.pipeline_workers" (get_logger(__name__))

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shipped literals, transcribed from backend/services/pipeline_workers.py
# =============================================================================

# L104: logger.debug(f"WebSocket emitter not available, skipping {event_type} broadcast")
SKIP_EMITTER_DEBUG = "WebSocket emitter not available, skipping {} broadcast"

# L166/L174/L178/L182/L186/L189 return f"{worker_name}_<family>_error"
LABELS = ("connection", "timeout", "memory", "validation", "redis", "processing")


def expected(worker_name: str, family: str) -> str:
    assert family in LABELS, family
    return f"{worker_name}_{family}_error"


# L2041: logger.info("Global pipeline worker manager initialized")
INIT_INFO = "Global pipeline worker manager initialized"
# L2058: logger.info("Global pipeline worker manager stopped")
STOPPED_INFO = "Global pipeline worker manager stopped"
# L2082: logger.debug("Pipeline manager not initialized, no queues to drain")
NO_MANAGER_DEBUG = "Pipeline manager not initialized, no queues to drain"
# L827: logger.debug(f"Failed to get broadcaster for batch analysis events: {e}")
BROADCASTER_FAILED_DEBUG = "Failed to get broadcaster for batch analysis events: {}"
# L2061: async def drain_queues(timeout: float = 30.0) -> int:
DRAIN_DEFAULT_TIMEOUT = 30.0
# L163-166 shipped connection-name tuple (re-declared here only so a test can
# assert a stimulus name is NOT in it; the shipped list is the authority).
CONNECTION_NAMES = (
    "ConnectionError",
    "ConnectionRefusedError",
    "ConnectionResetError",
    "BrokenPipeError",
    "OSError",
)
# backend.services.event_broadcaster.get_broadcaster is the real attribute the
# shipped function-local import resolves to (pipeline_workers.py:823), so this is
# the patch target; the import happens per call, so the patch is observed in
# every world.
FACTORY = "backend.services.event_broadcaster.get_broadcaster"


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
    """Assert the observable surface of one shipped f-string log call.

    ``record.msg`` is the RAW message.  Every shipped site in this group is an
    already-interpolated f-string, so ``args`` must stay empty (a moved or
    dropped message argument lands IN ``msg``) and ``exc_info`` must be absent.
    """
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args for an f-string message: {r.args!r}"
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


def with_global_manager(fn: Any, value: Any) -> Any:
    """Patch ``_pipeline_manager`` in ``fn``'s own live globals (context manager)."""
    return patch.dict(live_globals(fn), {"_pipeline_manager": value})


def stub_manager() -> MagicMock:
    """autospec'd instance double of the shipped manager class.

    ``create_autospec(PipelineWorkerManager)`` builds a signature-enforcing class
    double; its ``return_value`` is an instance double whose ``stop`` and
    ``drain_queues`` are AsyncMock, so the shipped singleton functions run their
    real control flow around it.
    """
    return create_autospec(PipelineWorkerManager)


# =============================================================================
# Crafted exception classes
#
# categorize_exception branches on type(e).__name__ (L163/L169), on isinstance
# (L169/L177/L181) and on type(e).__module__ (L185), so the NAME and MODULE of
# the stimulus are the load-bearing inputs.  Python identifiers are kept distinct
# from the builtins they impersonate (no shadowing) and ``__name__`` /
# ``__module__`` are pinned explicitly right below each class.
# =============================================================================


class TimeoutExpiredNamed(Exception):
    """Name in the shipped timeout tuple; NOT a builtin TimeoutError subclass."""


TimeoutExpiredNamed.__name__ = "TimeoutExpired"
TimeoutExpiredNamed.__module__ = "vendored.driver"


class TimeoutErrorNamedValueError(ValueError):
    """Name in the timeout tuple while the BASE CLASS is validation-family."""


TimeoutErrorNamedValueError.__name__ = "TimeoutError"
TimeoutErrorNamedValueError.__module__ = "vendored.driver"


class ModulelessTimeoutExpired(Exception):
    """Name in the timeout tuple AND a falsy module (order pin across L169/L185)."""


ModulelessTimeoutExpired.__name__ = "TimeoutExpired"
ModulelessTimeoutExpired.__module__ = None


class SocketTimeoutError(builtins.TimeoutError):
    """A genuine builtin-TimeoutError subclass whose name matches NO tuple."""


SocketTimeoutError.__name__ = "SocketTimeoutError"
SocketTimeoutError.__module__ = "vendored.driver"


class BrokenLinkError(Exception):
    """Name matches no tuple; reaches the ``args[0]`` ``"connect"`` test."""


BrokenLinkError.__name__ = "BrokenLinkError"
BrokenLinkError.__module__ = "vendored.driver"


class OsErrorNamed(Exception):
    """Name is the shipped tuple member ``OSError`` while the module says redis."""


OsErrorNamed.__name__ = "OSError"
OsErrorNamed.__module__ = "MyRedisPool.Client"


class RedisLikeError(Exception):
    """No tuple match; mixed-case module carrying a lowercase ``redis``."""


RedisLikeError.__name__ = "RedisLikeError"
RedisLikeError.__module__ = "MyRedisPool.Client"


class RedisUpperModuleError(Exception):
    """No tuple match; upper-case module carrying an uppercase ``REDIS``."""


RedisUpperModuleError.__name__ = "RedisUpperModuleError"
RedisUpperModuleError.__module__ = "Cache.REDIS.IO"


class OpaqueError(Exception):
    """Nothing matches: the L189 object-level fallback."""


OpaqueError.__name__ = "OpaqueError"
OpaqueError.__module__ = "completely.unrelated.pkg"


class ModulelessError(Exception):
    """Nothing matches and ``__module__`` is falsy - the L185 ``and`` guard."""


ModulelessError.__name__ = "ModulelessError"
ModulelessError.__module__ = None


# =============================================================================
# Fixtures (no import-time spies)
# =============================================================================


@pytest.fixture(autouse=True)
def clean_pipeline_manager_globals() -> Iterator[None]:
    """Cold global manager state before every test, restored afterwards.

    ``_pipeline_manager`` / ``_pipeline_manager_lock`` are module globals that
    persist across tests on an xdist worker: a manager bound to a since-closed
    loop poisons later tests, and a pre-warmed global silently satisfies the
    cached fast path this battery probes.  Patched through ``live_globals`` rather
    than by calling the shipped ``reset_pipeline_manager_state()``, because that
    helper only mutates the pristine module dict.
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


def analysis_worker() -> Any:
    """AnalysisQueueWorker with an injected analyzer (no real NemotronAnalyzer)."""
    return M.AnalysisQueueWorker(
        redis_client=MagicMock(name="redis-client"),
        analyzer=MagicMock(name="analyzer"),
    )


# =============================================================================
# 1) broadcast_worker_event - the emitter-is-None arm
#    x_broadcast_worker_event__mutmut_2 (L104 debug arg -> None)
# =============================================================================


@pytest.mark.parametrize(
    ("event_type", "worker_name"),
    [
        ("worker.started", "analysis-0"),
        ("worker.stopped", "detection-0"),
        # Not in the shipped event_type_map: with emitter None the map is never
        # reached, so the DEBUG text still carries the caller's string verbatim.
        ("worker.quantum_leap", "metrics"),
    ],
)
async def test_none_emitter_logs_the_skipped_broadcast_debug(
    event_type: str,
    worker_name: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``emitter is None`` -> exactly one DEBUG naming the event type, then return.

    Shipped backend/services/pipeline_workers.py:103-105::

        if emitter is None:
            logger.debug(f"WebSocket emitter not available, skipping {event_type} broadcast")
            return

    That record is the only observable of the whole call, so ``logger.debug(None)``
    at L104 (m2) is caught by ``record.msg``.
    """
    win(caplog)

    assert await M.broadcast_worker_event(None, event_type, worker_name, "analysis") is None

    only(caplog, logging.DEBUG, SKIP_EMITTER_DEBUG.format(event_type))
    assert at(caplog, logging.INFO) == [], "the None-emitter arm must not log INFO"
    assert at(caplog, logging.WARNING) == [], (
        "the None-emitter arm returns before the unknown-event-type WARNING arm"
    )


# =============================================================================
# 2) categorize_exception - the ordered return contract (L155-189)
#    m19, m20 (L169) and m23, m24, m25, m27, m28 (L185)
# =============================================================================


def test_timeout_expired_name_that_is_not_a_timeout_error_subclass(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The ``or`` at L169 must accept the NAME branch on its own.

    Shipped:168-174::

        # Timeout errors
        if isinstance(e, TimeoutError) or type(e).__name__ in (
            "TimeoutError",
            "TimeoutExpired",
            "asyncio.TimeoutError",
        ):
            return f"{worker_name}_timeout_error"

    The stimulus is a plain ``Exception`` subclass with a non-redis module, so
    ``isinstance(e, TimeoutError)`` is False and the result rests entirely on the
    boolean operator (kills m19 ``Or->And``) and on ``type(e)`` being the
    exception's type (kills m20, whose ``type(None).__name__`` is ``"NoneType"``).
    """
    assert TimeoutExpiredNamed.__name__ == "TimeoutExpired"
    assert not isinstance(TimeoutExpiredNamed("x"), builtins.TimeoutError)
    assert M.categorize_exception(TimeoutExpiredNamed("batch job aborted"), "w") == expected(
        "w", "timeout"
    )
    assert mine(caplog) == [], "categorize_exception never logs"


def test_timeout_error_name_beats_its_validation_base_class() -> None:
    """Order pin: the L169 timeout NAME branch precedes L181's ``ValueError``.

    Under m19 the ``and`` is False (the class is not a builtin TimeoutError), so
    the exception falls through to ``isinstance(e, ValueError | TypeError |
    KeyError)`` at L181 and comes back ``w_validation_error``.
    """
    e = TimeoutErrorNamedValueError("bad")
    assert isinstance(e, ValueError) and not isinstance(e, builtins.TimeoutError)
    assert M.categorize_exception(e, "w") == expected("w", "timeout")


def test_builtin_timeout_error_and_its_subclass_are_the_timeout_family() -> None:
    """The ``isinstance`` half of L169, for inputs whose name matches no tuple.

    (Shipped-fact pin behind that half: on the py314 target ``asyncio.TimeoutError``
    IS the builtin, so the tuple's third entry ``"asyncio.TimeoutError"`` is dead
    text for a ``__name__`` comparison - no real type is ever named with a dotted
    name - and every asyncio-raised timeout arrives here through ``isinstance``.)
    """
    assert asyncio.TimeoutError is builtins.TimeoutError
    assert type(builtins.TimeoutError("deadline")).__name__ == "TimeoutError"
    assert M.categorize_exception(builtins.TimeoutError("deadline exceeded"), "w") == expected(
        "w", "timeout"
    )
    assert SocketTimeoutError.__name__ == "SocketTimeoutError"
    assert M.categorize_exception(SocketTimeoutError("socket"), "w") == expected("w", "timeout")


def test_connection_error_names_are_the_connection_family() -> None:
    """Shipped:155-166 - the five-name tuple, compared against ``type(e).__name__``."""
    for cls in (
        builtins.ConnectionError,
        builtins.ConnectionRefusedError,
        builtins.ConnectionResetError,
        builtins.BrokenPipeError,
        builtins.OSError,
    ):
        assert type(cls("socket")).__name__ in CONNECTION_NAMES
        assert M.categorize_exception(cls("socket"), "w") == expected("w", "connection"), cls


def test_oserror_name_beats_the_redis_module_branch() -> None:
    """Order pin: the L163 connection-name branch precedes the L185 module check.

    The class name IS ``OSError`` (a shipped tuple member) while its module is the
    redis-flavoured ``"MyRedisPool.Client"``; the connection label must win, which
    also proves the redis branch is unreachable for it.
    """
    assert OsErrorNamed.__name__ == "OSError"
    assert OsErrorNamed.__module__ == "MyRedisPool.Client"
    assert M.categorize_exception(OsErrorNamed("io error"), "w") == expected("w", "connection")


def test_args_first_element_containing_connect_is_the_connection_family() -> None:
    """Shipped:163-165 - ``"connect" in str(e.args[0]).lower()``.

    The stored argument is deliberately upper-cased: the comparison runs against
    the LOWER-cased text, so ``"CONNECT"`` still routes to the connection family
    even though the class name matches no tuple.
    """
    e = BrokenLinkError("Failed to CONNECT to 10.0.0.1:6379")
    assert type(e).__name__ not in CONNECTION_NAMES
    assert "connect" not in str(e.args[0]), "the stored arg must be upper-case for this leg"
    assert M.categorize_exception(e, "w") == expected("w", "connection")


def test_memory_error_is_the_memory_family() -> None:
    """Shipped:176-178 - ``isinstance(e, MemoryError)``."""
    assert M.categorize_exception(builtins.MemoryError("cannot allocate 4 GiB"), "w") == expected(
        "w", "memory"
    )


@pytest.mark.parametrize(
    "exc",
    [ValueError("bad payload"), TypeError("unsupported type"), KeyError("camera_id")],
    ids=["value", "type", "key"],
)
def test_validation_bases_are_the_validation_family(exc: Exception) -> None:
    """Shipped:180-182 - ``isinstance(e, ValueError | TypeError | KeyError)``."""
    assert M.categorize_exception(exc, "w") == expected("w", "validation")


def test_module_name_containing_lowercase_redis_is_redis_error() -> None:
    """Shipped:184-186 - ``type(e).__module__ and "redis" in type(e).__module__.lower()``.

    ``RedisLikeError.__module__`` is the MIXED-CASE ``"MyRedisPool.Client"``:

    * m24 ``"XXredisXX"`` - the padded needle cannot be a substring of a module
      path that contains ``redis`` exactly once -> label degrades to processing;
    * m25 ``"REDIS"`` - needle upper-cased against lower-cased text never matches;
    * m27 ``.lower()`` -> ``.upper()`` - the mirror-image asymmetry;
    * m28 ``type(None).__module__`` inside the ``in`` - becomes
      ``"redis" in "builtins"``, i.e. False for every input, so NOTHING is ever
      labelled redis.
    """
    assert RedisLikeError.__module__ == "MyRedisPool.Client"
    assert "redis" in RedisLikeError.__module__.lower()
    assert M.categorize_exception(RedisLikeError("aof rewrite failed"), "w") == expected(
        "w", "redis"
    )
    assert M.categorize_exception(RedisLikeError("aof rewrite failed"), "analysis") == (
        "analysis_redis_error"
    )


def test_module_name_containing_uppercase_redis_is_redis_error() -> None:
    """The mirrored leg: module ``"Cache.REDIS.IO"`` also hits the redis label.

    ``"REDIS"`` is literally present here, so this is the leg that m25
    (``"REDIS" in text.lower()``) and m27 (``"redis" in text.upper()``) each pass
    by accident - the mixed-case leg above is what kills them.  Read the two
    legs together: m24 fails both, m28 fails both.
    """
    assert RedisUpperModuleError.__module__ == "Cache.REDIS.IO"
    assert M.categorize_exception(RedisUpperModuleError("cluster slot migrated"), "w") == expected(
        "w", "redis"
    )


def test_falsy_module_short_circuits_the_redis_guard_to_processing() -> None:
    """Shipped:185 - the ``type(e).__module__`` conjunct guards ``.lower()``.

    ``ModulelessError`` matches none of the earlier branches and its
    ``__module__`` is ``None``, so shipped short-circuits the ``and`` and returns
    the L189 fallback.  m23 swaps the conjunct for ``type(None).__module__``
    (``"builtins"``, permanently truthy), which removes the guard and raises
    ``AttributeError: 'NoneType' object has no attribute 'lower'`` - so this leg
    is the ONLY route to m23 and the exception it prevents is load-bearing.
    """
    assert ModulelessError.__module__ is None
    assert M.categorize_exception(ModulelessError("opaque"), "w") == expected("w", "processing")


def test_timeout_name_branch_fires_before_the_falsy_module_guard() -> None:
    """A ``TimeoutExpired`` with no module still returns the timeout label.

    Shipped returns from L169 and never evaluates the L185 guard, so the falsy
    ``__module__`` is harmless - which is what makes the previous test's
    ``AttributeError`` route specific to values that really reach L185.  Also a
    discriminator for m19/m20 (both degrade this input to processing).
    """
    assert ModulelessTimeoutExpired.__name__ == "TimeoutExpired"
    assert ModulelessTimeoutExpired.__module__ is None
    assert M.categorize_exception(ModulelessTimeoutExpired("job expired"), "w") == expected(
        "w", "timeout"
    )


def test_generic_exception_falls_back_to_processing() -> None:
    """Shipped:188-189 - the object-level fallback for a non-redis module."""
    assert OpaqueError.__module__ == "completely.unrelated.pkg"
    assert M.categorize_exception(OpaqueError("no known failure family"), "w") == expected(
        "w", "processing"
    )
    assert M.categorize_exception(Exception("bare"), "batch_timeout") == (
        "batch_timeout_processing_error"
    )


def test_worker_name_is_the_label_prefix_verbatim() -> None:
    """Every return site interpolates ``worker_name`` unchanged.

    No ``.lower()`` / ``.upper()`` / XX-wrap is applied to the prefix on any of
    the six return paths (L166/L174/L178/L182/L186/L189), so a mixed-case name
    survives intact.
    """
    for name in ("detection", "ANALYSIS", "batch-timeout"):
        assert M.categorize_exception(OpaqueError("x"), name) == f"{name}_processing_error"
    assert M.categorize_exception(RedisLikeError("x"), "TIMEOUT") == "TIMEOUT_redis_error"
    assert M.categorize_exception(TimeoutExpiredNamed("x"), "Timeout") == "Timeout_timeout_error"


# =============================================================================
# 3) get_pipeline_manager - cached fast path + single locked init
#    x_get_pipeline_manager__mutmut_1 (L2032 IsNot -> Is)
# =============================================================================


async def test_first_call_builds_once_with_the_client_and_logs_init_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Cold global -> exactly one build with the client, then the INFO at L2041.

    Shipped:2031-2043::

        # Fast path: manager already exists
        if _pipeline_manager is not None:
            return _pipeline_manager

        # Slow path: need to initialize with lock
        lock = _get_pipeline_manager_lock()
        async with lock:
            # Double-check after acquiring lock (another coroutine may have initialized)
            if _pipeline_manager is None:
                _pipeline_manager = PipelineWorkerManager(redis_client=redis_client)
                logger.info("Global pipeline worker manager initialized")

        return _pipeline_manager

    m1 turns the fast-path test into ``is None``, so a COLD global takes the fast
    path and returns the ``None`` global itself: the build never happens and the
    INFO never fires.  All three assertions below fail under it.
    """
    ctor = stub_manager()
    client = MagicMock(name="redis-client")
    g = live_globals(M.get_pipeline_manager)
    win(caplog)

    with patch.dict(g, {"PipelineWorkerManager": ctor}):
        manager = await M.get_pipeline_manager(client)

        assert manager is ctor.return_value, (
            f"a cold call must build and return the manager, got {manager!r}"
        )
        assert len(ctor.call_args_list) == 1, f"manager built {ctor.call_args_list}"
        assert ctor.call_args.kwargs == {"redis_client": client}, ctor.call_args
        assert ctor.call_args.kwargs["redis_client"] is client
        assert g["_pipeline_manager"] is ctor.return_value, (
            "the built manager must become the module global"
        )

    # The INFO is asserted after the patch exits so the record list is final;
    # caplog holds the record itself, not the (restored) module state.
    only(caplog, logging.INFO, INIT_INFO)


async def test_second_call_returns_the_cached_manager_and_logs_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Warm global -> same object, no second build, no second INFO.

    This is the memoisation contract the fast-path flip breaks (under m1 a warm
    global fails the flipped test, so the lock arm - and eventually the caller's
    own expectations - run every single time).  Kept separate from the cold leg so
    each failure names its own cause.
    """
    ctor = stub_manager()
    client = MagicMock(name="redis-client")
    g = live_globals(M.get_pipeline_manager)

    with patch.dict(g, {"PipelineWorkerManager": ctor}):
        first = await M.get_pipeline_manager(client)
        win(caplog)
        second = await M.get_pipeline_manager(client)

    assert second is first is ctor.return_value, f"{second!r} vs {first!r}"
    assert len(ctor.call_args_list) == 1, (
        f"the cached call rebuilt the manager: {ctor.call_args_list}"
    )
    assert mine(caplog) == [], (
        f"the cached call logged {[(r.levelno, r.msg) for r in mine(caplog)]}"
    )


# =============================================================================
# 4) stop_pipeline_manager - stop + clear + INFO
#    x_stop_pipeline_manager__mutmut_3/_4/_5/_6 (the four L2058 message variants)
# =============================================================================


async def test_stop_awaits_stop_clears_the_global_and_logs_the_stopped_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:2051-2058::

        global _pipeline_manager  # noqa: PLW0603

        lock = _get_pipeline_manager_lock()
        async with lock:
            if _pipeline_manager:
                await _pipeline_manager.stop()
                _pipeline_manager = None
                logger.info("Global pipeline worker manager stopped")

    The four surviving keys all sit on that INFO's message argument
    (``None`` / ``"XX...XX"`` / all-lower / all-upper), so ``record.msg`` is
    pinned against the shipped literal character-for-character; the ``await`` and
    the global clear pin the two statements around it.
    """
    g = live_globals(M.stop_pipeline_manager)
    manager = stub_manager().return_value
    win(caplog)

    with with_global_manager(M.stop_pipeline_manager, manager):
        assert await M.stop_pipeline_manager() is None
        assert manager.stop.await_count == 1, (
            f"manager.stop() awaited {manager.stop.await_count} times, expected 1"
        )
        assert g["_pipeline_manager"] is None, (
            f"the global must be cleared after stop, got {g['_pipeline_manager']!r}"
        )

    only(caplog, logging.INFO, STOPPED_INFO)


async def test_stop_with_no_manager_is_silent_and_leaves_the_global_none(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Cold global -> the ``if _pipeline_manager:`` arm is skipped: no log at all."""
    g = live_globals(M.stop_pipeline_manager)
    win(caplog)

    with patch.dict(g, {"_pipeline_manager": None}):
        assert await M.stop_pipeline_manager() is None

    assert mine(caplog) == [], f"a cold stop logged {[(r.levelno, r.msg) for r in mine(caplog)]}"
    assert g["_pipeline_manager"] is None


async def test_stop_is_idempotent_across_two_calls(caplog: pytest.LogCaptureFixture) -> None:
    """The second call sees the cleared global: one stop, one INFO in total."""
    manager = stub_manager().return_value
    win(caplog)

    with with_global_manager(M.stop_pipeline_manager, manager):
        await M.stop_pipeline_manager()
        await M.stop_pipeline_manager()
        assert manager.stop.await_count == 1, manager.stop.await_count

    only(caplog, logging.INFO, STOPPED_INFO)


# =============================================================================
# 5) module-level drain_queues - default timeout + not-initialised arm
#    x_drain_queues__mutmut_1 (L2061 default 30.0 -> 31.0)
# =============================================================================


async def test_default_timeout_is_the_shipped_thirty_seconds(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped L2061 + L2085: the DEFAULT is forwarded as ``timeout=30.0``.

    ::

        async def drain_queues(timeout: float = 30.0) -> int:
            ...
            return await _pipeline_manager.drain_queues(timeout=timeout)

    m1 rewrites only the parameter default (30.0 -> 31.0), which is observable
    exactly one place: the keyword the manager method receives.  It is captured on
    an autospec'd instance double and pinned to ``30.0``.  (The same-shaped
    mutant on the *method* is g16's key and is killed there; nothing here asserts
    the method's own default.)
    """
    manager = stub_manager().return_value
    sentinel = manager.drain_queues.return_value
    win(caplog)

    with with_global_manager(M.drain_queues, manager):
        assert await M.drain_queues() is sentinel

    assert manager.drain_queues.await_count == 1, manager.drain_queues.await_count
    call = manager.drain_queues.await_args
    assert call is not None
    assert call.kwargs == {"timeout": DRAIN_DEFAULT_TIMEOUT}, (
        f"forwarded kwargs mutated: {call.kwargs!r} != {{'timeout': {DRAIN_DEFAULT_TIMEOUT}!r}}"
    )
    assert call.kwargs["timeout"] == 30.0
    assert call.args == (), f"drain_queues must be called with the timeout keyword: {call.args!r}"
    assert mine(caplog) == [], "the warm drain arm does not log"


async def test_explicit_timeout_is_forwarded_unchanged() -> None:
    """The parameter itself is passed through verbatim (no ``+1`` on the way)."""
    manager = stub_manager().return_value

    with with_global_manager(M.drain_queues, manager):
        assert await M.drain_queues(timeout=12.5) is manager.drain_queues.return_value

    assert manager.drain_queues.await_args.kwargs == {"timeout": 12.5}


async def test_no_manager_returns_zero_and_logs_the_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:2081-2083 - cold global -> DEBUG, then ``return 0`` (not ``None``)."""
    g = live_globals(M.drain_queues)
    win(caplog)

    with patch.dict(g, {"_pipeline_manager": None}):
        result = await M.drain_queues()

    assert result == 0, f"expected 0, got {result!r}"
    only(caplog, logging.DEBUG, NO_MANAGER_DEBUG)
    assert at(caplog, logging.INFO) == []


# =============================================================================
# 6) AnalysisQueueWorker._get_broadcaster - lazy memoised factory (L813-829)
#    m1 L821 guard flip, m2 L825 assign -> None, m3 L825 factory arg -> None
# =============================================================================


async def test_first_call_awaits_the_factory_with_the_workers_redis_client(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:821-829 - build once from ``self._redis``, memoise, return it.

    ::

        if self._broadcaster is None:
            try:
                from backend.services.event_broadcaster import get_broadcaster

                self._broadcaster = await get_broadcaster(self._redis)
            except Exception as e:
                logger.debug(f"Failed to get broadcaster for batch analysis events: {e}")
                return None
        return self._broadcaster

    * m1 (``is None`` -> ``is not None``) skips the arm on a cold worker, so the
      call returns ``None`` and the factory is never awaited -> the ``got is`` /
      await-count assertions fail.
    * m2 (``self._broadcaster = None``) also returns ``None``.
    * m3 (``get_broadcaster(None)``) still returns the object, so the ARGUMENT
      identity assertion is the only route that catches it.
    """
    worker = analysis_worker()
    redis = worker._redis
    broadcaster = MagicMock(name="broadcaster")
    win(caplog)

    with patch(FACTORY, autospec=True) as factory:
        factory.return_value = broadcaster
        got = await worker._get_broadcaster()

    assert got is broadcaster, f"_get_broadcaster() returned {got!r}"
    assert worker._broadcaster is broadcaster, "the built broadcaster must be memoised"
    assert factory.await_count == 1, f"factory awaited {factory.await_count} times, expected 1"
    call = factory.await_args
    assert call is not None
    assert len(call.args) == 1 and not call.kwargs, f"factory call shape mutated: {call!r}"
    assert call.args[0] is redis, (
        f"factory argument mutated: {call.args[0]!r} is not worker._redis ({redis!r})"
    )
    assert mine(caplog) == [], "the success arm does not log"


async def test_second_call_is_memoised_and_never_re_awaits() -> None:
    """The ``is None`` guard means the factory runs at most once per worker.

    m2 leaves ``self._broadcaster`` at ``None``, so every subsequent call re-enters
    the arm and awaits the factory again -> the ``await_count == 1`` pin fails.
    """
    worker = analysis_worker()
    broadcaster = MagicMock(name="broadcaster")

    with patch(FACTORY, autospec=True) as factory:
        factory.return_value = broadcaster
        first = await worker._get_broadcaster()
        second = await worker._get_broadcaster()
        third = await worker._get_broadcaster()

    assert (first, second, third) == (broadcaster, broadcaster, broadcaster)
    assert factory.await_count == 1, (
        f"memoisation broken: factory awaited {factory.await_count} times"
    )


async def test_preseeded_broadcaster_is_returned_without_calling_the_factory(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Second discriminator for m1: a warm ``_broadcaster`` is returned as-is.

    Under the flipped guard a warm worker re-runs the arm and hands back the
    factory's object instead of the seeded one.
    """
    worker = analysis_worker()
    seeded = MagicMock(name="seeded-broadcaster")
    worker._broadcaster = seeded
    win(caplog)

    with patch(FACTORY, autospec=True) as factory:
        factory.return_value = MagicMock(name="fresh-broadcaster")
        got = await worker._get_broadcaster()

    assert got is seeded, f"the seeded broadcaster was replaced by {got!r}"
    assert factory.await_count == 0, (
        f"the factory ran for a warm broadcaster: {factory.await_count} awaits"
    )
    assert mine(caplog) == []


async def test_factory_failure_is_swallowed_into_a_debug_and_returns_none(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:826-828 - the ``except Exception`` arm (no survivor sits there).

    Stated as a control so the success legs above cannot be satisfied by an
    accidental exception-arm ``return None``: that arm yields ``None`` AND leaves
    ``_broadcaster`` unset, so a later call retries.
    """
    err = builtins.ConnectionError("broadcaster backend unavailable")
    worker = analysis_worker()
    win(caplog)

    with patch(FACTORY, autospec=True) as factory:
        factory.side_effect = err
        first = await worker._get_broadcaster()

    assert first is None, f"the failure arm must return None, got {first!r}"
    assert worker._broadcaster is None, "a failed build must not be memoised"
    only(caplog, logging.DEBUG, BROADCASTER_FAILED_DEBUG.format(err))
