"""Shared dispatcher for the ONE global ``bounded_gather`` slot.

WHY THIS EXISTS (MEASURED 2026-09-26)
-------------------------------------
``backend.services.enrichment_pipeline.bounded_gather`` is a single module-level
name, and two kill-battery files each installed their OWN recording spy over it
AT IMPORT TIME, each capturing ``_ORIGINAL = M.bounded_gather`` at ITS import
time:

* ``test_enrichment_pipeline_batch26_02.py`` records the ``limit`` kwarg shape
  (shapes #209/#211 — ``limit=5`` deleted/6, callee default 10);
* ``test_enrichment_pipeline_batch26_05.py`` records the gather partition —
  task names (read off the ``_ep_task`` attribute of the scheduled awaitables),
  ``limit``, ``task_timeout``, ``return_exceptions``.

pytest imports EVERY test module during collection, so the last import wins the
slot, and whichever file lost sees one of two failures:

* an empty recording list (its spy was clobbered, so nothing ever reaches it), or
* a spy-shaped "original" — the loser's ``_ORIGINAL`` captured the OTHER file's
  spy, which recurses/records into the wrong list.

Under file-grouped runs the two files never interleave, so this stayed invisible
until mutmut's ``Found 1296 new tests, rerunning stats collection`` phase, which
runs every test id in SET order — i.e. interleaved — in one process. That abort
reproduces deterministically from the module-scope ordering above.

THE FIX
-------
The slot is installed ONCE with a dispatcher that holds the PRISTINE original,
and each battery file registers a recorder instead of replacing the function.
The dispatcher calls every ACTIVE recorder (active = "a test from that file is
running") and then delegates to the pristine original, so behaviour is unchanged
for shipped code and for every mutant body that resolves the name from the
module dict.

Contract the batteries rely on:

* ``install_bg_dispatcher(M)`` is idempotent — the first caller wins and later
  callers are no-ops, so import order between the batteries no longer matters.
* ``_is_bg_dispatcher`` marks the installed dispatcher and ``_bg_real`` carries
  the pristine function, so signature/default pins
  (``inspect.signature(...).parameters["limit"].default == 10``) resolve the
  REAL callee through the tag rather than an import-time capture that another
  file may have poisoned.
* ``register_recorder(fn)`` appends to this module's live registry; the
  dispatcher iterates the CURRENT registry contents at CALL time, and every
  recorder gates on the battery's own ACTIVE flag. Nothing is ever
  snapshot-captured, so a recorder installed after the dispatcher still fires.
* Activation is per test (a function-scope autouse fixture in each battery
  flips its flag), which keeps the recordings each file asserts on as exact as
  they were when the file owned the slot alone.
"""

from __future__ import annotations

from typing import Any

# Registry of ``(recorder, state)`` pairs. A recorder is called as
# ``recorder(coros_list, kwargs)`` at gather time; ``state["active"]`` is the
# owning battery's per-test gate.
_RECORDERS: list[tuple[Any, dict[str, bool]]] = []


def install_bg_dispatcher(module: Any) -> Any:
    """Idempotently install the dispatcher over ``module.bounded_gather``.

    Returns the function now occupying the slot. The pristine callee is captured
    ONLY by the call that actually installs the dispatcher, so the first battery
    to import (in any order) pins the real implementation for everyone.
    """
    current = module.bounded_gather
    if getattr(current, "_is_bg_dispatcher", False):
        return current
    real = current

    async def _bg_dispatcher(coros: Any, /, *args: Any, **kw: Any) -> Any:
        """Fan out to every ACTIVE recorder, then delegate to the real callee.

        Forwarding is argument-faithful — ``coros`` plus whatever the caller
        passed (positionally or by keyword) goes to the pristine callee
        untouched, so neither the shipped call sites (L2678/L2688/L2808/L2846,
        which pass ``limit``/``task_timeout``/``return_exceptions`` by keyword)
        nor a mutant body behaves differently.  Recorders see EXACTLY the
        keyword arguments the call site passed, so ``kw.get("task_timeout")``
        stays ``None`` for a gather that omitted the kwarg instead of being
        filled in with the callee's default.  A recorder that raises is skipped,
        with the failure parked in its state, rather than changing shipped
        behaviour mid-test.
        """
        items = list(coros)
        record_kwargs = dict(kw)
        if args and "limit" not in record_kwargs:
            # the callee declares ``limit`` keyword-only, so a positional extra
            # can only come from a non-shipped call; report it as the limit
            record_kwargs["limit"] = args[0]
        for recorder, state in tuple(_RECORDERS):
            if not state["active"]:
                continue
            try:
                recorder(items, record_kwargs)
            except Exception as exc:
                # a broken recorder must not alter shipped behaviour: park it and
                # let the owning battery's gate fixture surface it as a failure
                state["errors"].append(exc)
        return await real(items, *args, **kw)

    _bg_dispatcher._is_bg_dispatcher = True  # type: ignore[attr-defined]
    _bg_dispatcher._bg_real = real  # type: ignore[attr-defined]
    module.bounded_gather = _bg_dispatcher
    return _bg_dispatcher


def register_recorder(recorder: Any) -> dict[str, Any]:
    """Attach ``recorder(coros_list, kwargs)`` to the dispatcher.

    Returns the state dict, whose ``active`` key the owning battery flips for
    the duration of each of its own tests and whose ``errors`` list captures any
    exception the recorder raises (so a harness bug shows up as a test failure
    via :func:`recorder_errors` instead of a silent gap in the recordings).
    """
    state: dict[str, Any] = {"active": False, "errors": []}
    _RECORDERS.append((recorder, state))
    return state


def bg_real(module: Any) -> Any:
    """The pristine ``bounded_gather`` the dispatcher delegates to.

    Falls back to whatever occupies the slot when no dispatcher has been
    installed yet (which cannot happen for a battery that calls
    :func:`install_bg_dispatcher` at import time, but keeps the helper honest).
    """
    current = module.bounded_gather
    return getattr(current, "_bg_real", current)


def recorder_errors(state: dict[str, Any]) -> list[Any]:
    """Recorder exceptions captured since the last clear (then clears them)."""
    errors = list(state["errors"])
    state["errors"].clear()
    return errors
