"""B1.4 (UR-18): the verdict-engine tracker — state, since, and the WS event.

The tracker is the DECIDE's home: probe result is the source of truth (see
backend/services/verdict_engine_status.py's module docstring for why not the
circuit breaker or the last successful assess). These unit tests pin its
three promises directly, without the readiness route:

1. honest three-state derivation — probe said up / probe said down / probe
   could not tell (details None from the AI-timeout path, or a missing
   ai-vlm key) -> available / unavailable / unknown, never a guessed default;
2. `since` is the TRANSITION time: re-stamped on a state change, preserved
   while the state repeats (the reason may change without becoming an event);
3. exactly one system.verdict_engine_status_changed event per transition,
   fire-and-forget, carrying {state, previous_state, since, reason, source}
   — and NO event on repeats (the readiness cache refreshes every 10 s; a
   per-probe event would flood /ws/system subscribers).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from backend.core.websocket.event_schemas import VerdictEngineState
from backend.core.websocket.event_types import WebSocketEventType
from backend.services.verdict_engine_status import (
    VerdictEngineStatusTracker,
    get_verdict_engine_tracker,
)

if TYPE_CHECKING:
    from unittest.mock import MagicMock

_DOWN_DETAILS = {"yolo26": "healthy", "ai-vlm": "ConnectError: connection refused"}
_UP_DETAILS = {"yolo26": "healthy", "ai-vlm": "healthy"}


@pytest.fixture
def tracker() -> VerdictEngineStatusTracker:
    """Fresh tracker per test (not the singleton — these tests own lifecycle)."""
    return VerdictEngineStatusTracker()


@pytest.fixture
def ws_emitter() -> MagicMock:
    """Mock WebSocket emitter: .emit awaited, not returned."""
    emitter = AsyncMock()
    emitter.emit = AsyncMock()
    return emitter


class TestStateDerivation:
    """The probe's words become the state — including when it has none."""

    def test_initial_state_is_unknown_not_assumed(
        self, tracker: VerdictEngineStatusTracker
    ) -> None:
        """Before any probe the honest answer is unknown. Defaulting to
        available would be the UR-18 dishonesty in a new place."""
        snap = tracker.snapshot
        assert snap.state == VerdictEngineState.UNKNOWN
        assert snap.reason == "not probed yet"

    def test_probe_says_healthy(self, tracker: VerdictEngineStatusTracker) -> None:
        snap = tracker.observe(_UP_DETAILS, message="AI services operational")
        assert snap.state == VerdictEngineState.AVAILABLE
        assert snap.reason is None

    def test_probe_carries_the_engine_error(self, tracker: VerdictEngineStatusTracker) -> None:
        """The reason is the engine's own error string from details, not a
        paraphrase — an operator reading the payload sees what ai-vlm said."""
        snap = tracker.observe(_DOWN_DETAILS, message="ai-vlm service unavailable")
        assert snap.state == VerdictEngineState.UNAVAILABLE
        assert snap.reason == "ConnectError: connection refused"

    def test_timeout_probe_is_unknown_with_its_message(
        self, tracker: VerdictEngineStatusTracker
    ) -> None:
        """The AI-timeout path returns details=None (system.py
        _check_ai_health_with_timeout): the probe could not reach the engine
        OR the probe itself failed — claiming unavailable would blame the
        engine for what might be our own 2 s budget."""
        snap = tracker.observe(None, message="AI services health check timed out after 2.0s")
        assert snap.state == VerdictEngineState.UNKNOWN
        assert "timed out" in (snap.reason or "")

    def test_missing_vlm_key_is_unknown(self, tracker: VerdictEngineStatusTracker) -> None:
        """A probe result without the ai-vlm detail says nothing about the
        engine — unknown, with a reason that says so."""
        snap = tracker.observe({"yolo26": "healthy"}, message="AI services operational")
        assert snap.state == VerdictEngineState.UNKNOWN
        assert "ai-vlm" in (snap.reason or "")


class TestTransitionSemantics:
    """since is the transition time; repeats are not events."""

    def test_repeat_preserves_since_and_refreshes_reason(
        self, tracker: VerdictEngineStatusTracker
    ) -> None:
        first = tracker.observe(_DOWN_DETAILS)
        later_reason = {"yolo26": "healthy", "ai-vlm": "ConnectTimeout: 3s"}
        second = tracker.observe(later_reason)
        assert second.state == VerdictEngineState.UNAVAILABLE
        assert second.since == first.since, "how long has this been down? must not reset"
        assert second.reason == "ConnectTimeout: 3s", "reason keeps the latest error"

    def test_transition_restamps_since(self, tracker: VerdictEngineStatusTracker) -> None:
        down = tracker.observe(_DOWN_DETAILS)
        up = tracker.observe(_UP_DETAILS)
        assert up.state == VerdictEngineState.AVAILABLE
        assert up.since > down.since

    def test_reset_restores_honest_empty_state(self, tracker: VerdictEngineStatusTracker) -> None:
        tracker.observe(_UP_DETAILS)
        tracker.reset()
        assert tracker.snapshot.state == VerdictEngineState.UNKNOWN


class TestTransitionEvents:
    """One WS event per transition — that is the package's third clause."""

    @pytest.mark.asyncio
    async def test_transition_emits_event_with_the_decided_shape(
        self, tracker: VerdictEngineStatusTracker, ws_emitter: MagicMock
    ) -> None:
        tracker.set_emitter(ws_emitter)
        snap = tracker.observe(_DOWN_DETAILS)
        await asyncio.sleep(0)  # let the fire-and-forget task run

        ws_emitter.emit.assert_awaited_once()
        event_type, payload = ws_emitter.emit.await_args.args
        assert event_type == WebSocketEventType.SYSTEM_VERDICT_ENGINE_STATUS_CHANGED
        assert payload["state"] == "unavailable"
        assert payload["previous_state"] == "unknown"
        assert payload["reason"] == "ConnectError: connection refused"
        assert payload["source"] == "health_probe"
        assert datetime.fromisoformat(payload["since"]) == snap.since

    @pytest.mark.asyncio
    async def test_repeat_emits_nothing(
        self, tracker: VerdictEngineStatusTracker, ws_emitter: MagicMock
    ) -> None:
        tracker.set_emitter(ws_emitter)
        tracker.observe(_DOWN_DETAILS)
        await asyncio.sleep(0)
        assert ws_emitter.emit.await_count == 1, "the first transition must emit"
        ws_emitter.emit.reset_mock()  # clears counts WITHOUT touching calls made after

        tracker.observe(_DOWN_DETAILS)  # same state again (a cache refresh)
        await asyncio.sleep(0)
        ws_emitter.emit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_emit_failure_does_not_break_the_probe(
        self, tracker: VerdictEngineStatusTracker, ws_emitter: MagicMock
    ) -> None:
        """A broken WebSocket must never fail the readiness probe — the event
        is fire-and-forget and its exception is swallowed by design."""
        ws_emitter.emit = AsyncMock(side_effect=RuntimeError("ws down"))
        tracker.set_emitter(ws_emitter)

        snap = tracker.observe(_DOWN_DETAILS)
        await asyncio.sleep(0)  # the task raises inside; must not surface
        assert snap.state == VerdictEngineState.UNAVAILABLE  # observe() already returned fine


class TestSingleton:
    """The route and any future caller must share ONE tracked state."""

    def test_get_verdict_engine_tracker_is_process_singleton(self) -> None:
        assert get_verdict_engine_tracker() is get_verdict_engine_tracker()
