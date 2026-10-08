"""Verdict-engine (ai-vlm) availability tracking — B1.4 / UR-18.

Why this exists
---------------
An unreachable ``ai-vlm`` turns every event into ``verification_failed`` while
the platform looks healthy: ``get_readiness`` computes ``ready``/HTTP status
from database, Redis and pipeline workers only (it never reads the AI status),
so the engine's state was visible nowhere a caller could branch on. This
module is the single source of truth that the readiness payload's
``verdict_engine`` field and the ``system.verdict_engine_status_changed``
WebSocket event both read from.

The DECIDE (package B1.4): source of truth for engine state
-----------------------------------------------------------
The package names three candidates; the probe result wins:

- **The health-probe result** (chosen). ``_check_shipped_ai_services_health``
  pings ``ai-vlm``'s ``/health`` on every readiness cache-miss and reports the
  engine's own answer — or the engine's own error string — in
  ``details["ai-vlm"]``. Immediate, engine-specific, and it answers in the
  same request the field is published on.
- The circuit breaker (rejected as the *state*): it opens only after
  ``failure_threshold`` (3) consecutive failures, so during the failure ramp
  it still reports closed exactly when events start failing verification —
  the UR-18 blind spot again. It is still consulted second-hand: an open
  circuit short-circuits the probe, and the cached error arrives here as the
  probe's own error string.
- The last successful assess (rejected): invisible to the readiness route and
  blank after every restart — it cannot answer "is it up *now*" from behind a
  15-second readiness cache.

Honest-state rule
-----------------
The probe pings ``/health``, which answers while generation is broken (the
worse UR-18 failure mode), so this state answers the narrower, defensible
question "is the engine reachable" — NOT "can it produce verdicts". A probe
that could not reach a verdict about the engine at all (timeout, missing
detail) is reported ``unknown`` with the reason it is unknown, never folded
into ``available``/``unavailable``.

``since`` is the TRANSITION time, stamped here per state change — not a
per-request timestamp — so it survives the readiness cache and answers "how
long has this been down?".

Usage:
    from backend.services.verdict_engine_status import get_verdict_engine_tracker

    snapshot = get_verdict_engine_tracker().observe(
        ai_status.details, message=ai_status.message
    )
    # snapshot.state / .since / .reason feed the readiness payload; a
    # state TRANSITION fires the WebSocket event fire-and-forget.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar

from backend.core.logging import get_logger
from backend.core.websocket.event_schemas import VerdictEngineState
from backend.core.websocket.event_types import WebSocketEventType

if TYPE_CHECKING:
    from backend.services.websocket_emitter import WebSocketEmitterService

logger = get_logger(__name__)

# The probe's own detail value for a reachable engine (system.py's
# _check_shipped_ai_services_health writes "healthy" or the error string).
_PROBE_OK = "healthy"

_INITIAL_REASON = "not probed yet"


@dataclass(frozen=True, slots=True)
class VerdictEngineStatusSnapshot:
    """Immutable view of the verdict engine's tracked state.

    Attributes:
        state: Current availability state
        since: When the state last TRANSITIONED (not when it was read)
        reason: The engine's own error string while unavailable, why the
            probe could not tell while unknown, None while available
    """

    state: VerdictEngineState
    since: datetime
    reason: str | None


def _derive_state(
    details: dict[str, Any] | None,
    message: str | None,
) -> tuple[VerdictEngineState, str | None]:
    """Map one AI-health probe result onto the engine's state.

    Args:
        details: The probe's per-service details (``details["ai-vlm"]`` is the
            engine's answer: "healthy" or its own error string), or None when
            the probe could not complete (e.g. the 2 s AI timeout path)
        message: The probe's aggregate message, used as the unknown-reason
            fallback so the payload still says WHY nothing is known

    Returns:
        Tuple of (state, reason)
    """
    if details is None:
        return (
            VerdictEngineState.UNKNOWN,
            message or "AI health probe did not report engine reachability",
        )
    vlm = details.get("ai-vlm")
    if vlm is None:
        return (
            VerdictEngineState.UNKNOWN,
            "AI health probe reported no ai-vlm detail",
        )
    if vlm == _PROBE_OK:
        return (VerdictEngineState.AVAILABLE, None)
    return (VerdictEngineState.UNAVAILABLE, str(vlm))


class VerdictEngineStatusTracker:
    """Tracks verdict-engine availability and emits events on transitions.

    Like :class:`backend.services.health_event_emitter.HealthEventEmitter`,
    events fire only on an actual state change, so a 15 s readiness cache and
    the probe storm behind it cannot flood WebSocket clients.

    ``observe`` is deliberately synchronous with no await inside: one event
    loop runs it to completion per probe, so no lock is needed for the state
    mutation itself. The WebSocket emission is fire-and-forget (the readiness
    response must not wait on broadcast latency), mirroring how /health
    launches ``_emit_health_status_changes`` as a background task.

    Attributes:
        _state: Current tracked state (starts UNKNOWN — nothing is known
            until the first probe, and pretending otherwise would be the
            exact dishonesty this package is fixing)
        _since: Transition timestamp of the current state
        _reason: Reason carried by the current state
        _emitter: WebSocket emitter service, when one has been wired up
    """

    # Which mechanism produced this state (the DECIDE, published for callers)
    SOURCE: ClassVar[str] = "health_probe"

    def __init__(self) -> None:
        """Initialize with the honest empty state: unprobed, hence unknown."""
        self._state: VerdictEngineState = VerdictEngineState.UNKNOWN
        self._since: datetime = datetime.now(UTC)
        self._reason: str | None = _INITIAL_REASON
        self._emitter: WebSocketEmitterService | None = None
        logger.debug("VerdictEngineStatusTracker initialized (state=unknown)")

    def set_emitter(self, emitter: WebSocketEmitterService) -> None:
        """Set the WebSocket emitter service.

        Args:
            emitter: WebSocket emitter service instance
        """
        self._emitter = emitter
        logger.debug("WebSocket emitter set for VerdictEngineStatusTracker")

    @property
    def snapshot(self) -> VerdictEngineStatusSnapshot:
        """Current tracked state as an immutable view.

        Returns:
            Snapshot of (state, since, reason)
        """
        return VerdictEngineStatusSnapshot(
            state=self._state,
            since=self._since,
            reason=self._reason,
        )

    def observe(
        self,
        details: dict[str, Any] | None,
        message: str | None = None,
    ) -> VerdictEngineStatusSnapshot:
        """Record one probe's verdict-engine state; emit on a TRANSITION.

        Called from the readiness route with the AI-health probe's details.
        A state change re-stamps ``since`` and fires
        ``system.verdict_engine_status_changed`` fire-and-forget; repeats of
        the same state only refresh the reason and stay silent.

        Args:
            details: Probe per-service details (None = probe could not tell)
            message: Probe aggregate message (unknown-reason fallback)

        Returns:
            The resulting snapshot to publish in the readiness payload
        """
        state, reason = _derive_state(details, message)
        previous = self._state

        if state is previous:
            # Same state: keep the transition time, keep quiet. The reason may
            # legitimately change while unavailable (different error text on
            # successive probes) — publishing it does not make it a new event.
            self._reason = reason
            return self.snapshot

        now = datetime.now(UTC)
        self._state = state
        self._since = now
        self._reason = reason

        logger.info(
            f"Verdict engine state changed: {previous.value} -> {state.value}",
            extra={
                "previous_state": previous.value,
                "new_state": state.value,
                "reason": reason,
                "source": self.SOURCE,
            },
        )
        self._schedule_transition_event(
            previous_state=previous,
            new_state=state,
            since=now,
            reason=reason,
        )
        return self.snapshot

    def _schedule_transition_event(
        self,
        previous_state: VerdictEngineState,
        new_state: VerdictEngineState,
        since: datetime,
        reason: str | None,
    ) -> None:
        """Fire the WebSocket event without making the probe wait.

        No running loop (startup probes, sync contexts) or a failed schedule
        only loses the push — the readiness payload still carries the state.
        """
        try:
            asyncio.get_running_loop().create_task(
                self._emit_transition(
                    previous_state=previous_state,
                    new_state=new_state,
                    since=since,
                    reason=reason,
                )
            )
        except RuntimeError:  # pragma: no cover - only outside an event loop
            logger.debug("No running loop; skipping verdict-engine WS event")

    async def _emit_transition(
        self,
        previous_state: VerdictEngineState,
        new_state: VerdictEngineState,
        since: datetime,
        reason: str | None,
    ) -> None:
        """Emit a system.verdict_engine_status_changed WebSocket event."""
        if self._emitter is None:
            # Same lazy wiring as _emit_health_status_changes: the route may
            # run before (or without) the WebSocket service being available.
            from backend.services.websocket_emitter import get_websocket_emitter_sync

            ws_emitter = get_websocket_emitter_sync()
            if ws_emitter is not None:
                self.set_emitter(ws_emitter)
        if self._emitter is None:
            logger.debug("No emitter configured, skipping verdict-engine event")
            return

        payload = {
            "state": new_state.value,
            "previous_state": previous_state.value,
            "since": since.isoformat(),
            "reason": reason,
            "source": self.SOURCE,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        try:
            await self._emitter.emit(
                WebSocketEventType.SYSTEM_VERDICT_ENGINE_STATUS_CHANGED,
                payload,
            )
        except Exception as e:
            logger.error(f"Failed to emit verdict-engine status event: {e}", exc_info=True)

    def reset(self) -> None:
        """Reset all tracked state.

        Warning: Only use this in tests or during system restart.
        """
        self._state = VerdictEngineState.UNKNOWN
        self._since = datetime.now(UTC)
        self._reason = _INITIAL_REASON
        logger.info("VerdictEngineStatusTracker state reset")


# =============================================================================
# Global Singleton Instance (same pattern as health_event_emitter)
# =============================================================================

_verdict_engine_tracker: VerdictEngineStatusTracker | None = None
_tracker_lock = threading.Lock()


def get_verdict_engine_tracker() -> VerdictEngineStatusTracker:
    """Get or create the process-wide verdict-engine status tracker.

    Thread-safe singleton pattern ensures one tracked state per process,
    matching backend.services.health_event_emitter's approach.

    Returns:
        The VerdictEngineStatusTracker singleton
    """
    global _verdict_engine_tracker  # noqa: PLW0603
    if _verdict_engine_tracker is None:
        with _tracker_lock:
            if _verdict_engine_tracker is None:
                _verdict_engine_tracker = VerdictEngineStatusTracker()
    return _verdict_engine_tracker
