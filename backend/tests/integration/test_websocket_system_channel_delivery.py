"""Live-delivery regression for the system channel (#6940, owner ruling 47).

The fix under test is one lifespan line: ``backend/main.py`` attaches the
system broadcaster to the global WebSocket emitter
(``await get_websocket_emitter(system_broadcaster=system_broadcaster)``).
Without it, ``_dispatch_event`` sends every default-channel-"system" event
into its final ``else`` -- "No broadcaster available" logged, ``emit()``
still returns True -- so every system-channel producer wired to the emitter
(health changes and verdict-engine transitions today; system errors are wired
to the emitter but have no production caller) is dropped with a warning and the
frontend's ``/ws/system`` listeners never fire.

Why this test is a NEW file with its own fixture instead of a case in
``test_websocket.py``: that file's lifespan fixtures patch
``backend.main.get_system_broadcaster`` to a MagicMock, which splits the
broadcaster in two -- the lifespan (and after #6940, the emitter) holds the
mock while the ROUTE resolves the real module singleton from
``backend.api.routes.websocket`` -- so a client connected through those
fixtures can never receive an emitted event, no matter what the emitter is
wired to. This fixture reuses the same fast-boot patch set (imported, not
copied) and then rebinds ``backend.main.get_system_broadcaster`` back to the
real factory, so lifespan, emitter singleton, and route all converge on the
one real singleton under test. Everything else stays mocked exactly as the
existing fixtures mock it.

Trigger is the production entry point, not a hand-built emit: the verdict
tracker's ``observe({"ai-vlm": ...})`` maps an unhealthy probe to an
UNKNOWN -> UNAVAILABLE transition and fires
``system.verdict_engine_status_changed`` fire-and-forget. ``observe`` is
called on the TestClient portal loop so the tracker's
``get_running_loop().create_task`` lands the dispatch on the same loop the
websocket handler runs on.
"""

import contextlib
import os
import tempfile
from collections.abc import Generator
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from backend.services.system_broadcaster import get_system_broadcaster
from backend.services.verdict_engine_status import get_verdict_engine_tracker
from backend.services.websocket_emitter import reset_emitter_state
from backend.tests.integration.test_websocket import (
    _apply_common_lifespan_patches,
    _get_common_lifespan_mocks,
)

# A verdict transition is a single in-process memory hop (emitter ->
# broadcaster -> websocket.send_text), so it arrives long before this bound.
# The cap exists only to turn a runaway skip loop into an assertion instead of
# a hang. It is NOT a timing guarantee: the broadcaster's 5s tick pushes TWO
# frames per client (system_broadcaster.py broadcast_status +
# broadcast_performance), so 20 periodic frames would span ~10 ticks (~50s) --
# past @pytest.mark.timeout below. A run slow enough to hit the cap fails on
# the timeout mark first, which is the same verdict, just a different message.
_MAX_FRAMES_TO_SKIP = 20


@pytest.fixture
def live_broadcaster_client(request: pytest.FixtureRequest) -> Generator[TestClient]:
    """TestClient whose lifespan attaches the REAL system broadcaster.

    Boots the real lifespan with the tier's standard fast-boot patch set
    (``_apply_common_lifespan_patches``), then rebinds the lifespan's
    ``get_system_broadcaster`` to the real factory. Auth is forced off at
    the settings layer (``API_KEY_ENABLED=false``) so the websocket
    middleware passes connections with no credential -- the same default
    posture production runs in for LAN/loopback dev, and it keeps this
    test independent of the API-key fixtures.
    """
    from backend.core.config import get_settings
    from backend.main import app

    original_env = {
        key: os.environ.get(key)
        for key in (
            "API_KEY_ENABLED",
            "API_KEYS",
            "WEBSOCKET_TOKEN",
            "RATE_LIMIT_ENABLED",
            "HSI_RUNTIME_ENV_PATH",
        )
    }

    # A generator fixture's post-yield block never runs when SETUP fails, so
    # process-state restore must live in a finalizer registered BEFORE the
    # first mutation -- otherwise a mid-setup failure strands
    # API_KEY_ENABLED=false / RATE_LIMIT_ENABLED=false / the cleared settings
    # cache / a mutated tracker on the worker for every later test.
    def _restore_process_state() -> None:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()
        with contextlib.suppress(Exception):
            get_verdict_engine_tracker().reset()
        reset_emitter_state()

    request.addfinalizer(_restore_process_state)

    tmpdir = tempfile.mkdtemp()
    os.environ["API_KEY_ENABLED"] = "false"  # pragma: allowlist secret
    os.environ.pop("API_KEYS", None)
    os.environ.pop("WEBSOCKET_TOKEN", None)
    # The websocket rate leg counts against Redis; the tier's AsyncMock redis
    # only emulates the pipeline shape the BULK tier uses. Opt out -- the
    # route's check_websocket_rate_limit returns True before touching Redis.
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    os.environ["HSI_RUNTIME_ENV_PATH"] = str(Path(tmpdir) / "runtime.env")
    get_settings.cache_clear()

    mocks = _get_common_lifespan_mocks()

    # The lifespan's mocked redis feeds the REAL broadcaster (injected at
    # startup, not via the module global): subscribe_dedicated must hand
    # back an AsyncMock, not the default MagicMock child, because the
    # shutdown path awaits pubsub.unsubscribe()/close() and catches only
    # (ConnectionError, TimeoutError, OSError) -- an un-awaitable child
    # would raise TypeError and crash lifespan teardown.
    mocks["redis_client"].subscribe_dedicated = AsyncMock(return_value=AsyncMock())
    # connect()'s initial system_status frame carries queue counts straight
    # into send_json: the AsyncMock default (MagicMock children) is not JSON-
    # serializable, and the TypeError it provokes escapes connect()'s caught
    # exception set -- the handler then never reaches its receive loop and
    # the client hangs. The real client returns ints; give the mock that
    # shape (health_check's MagicMock return is already discarded).
    mocks["redis_client"].get_queue_length = AsyncMock(return_value=0)
    # The broadcaster's 5s loop also broadcasts performance: the helper's
    # collector mock's auto-child collect_all() is a plain MagicMock, and
    # awaiting it raises TypeError inside the loop task -- which then
    # re-raises through stop_broadcasting's (CancelledError-only) await of
    # the task at teardown. Any run with connections alive past the first
    # tick hits this, so the collector gets an awaitable returning a
    # model_dump-shaped stub; performance frames are {}.
    mocks["performance_collector"].collect_all = AsyncMock(
        return_value=MagicMock(model_dump=MagicMock(return_value={}))
    )

    async def mock_init_db() -> None:
        """Skip real database init; _get_system_status degrades on RuntimeError."""

    # A brand-live singleton can carry state left by earlier tests in this
    # worker; start from the documented empty state and hand the emitter
    # slot back empty when done (same hook the unit tier autouses).
    tracker = get_verdict_engine_tracker()
    tracker.reset()

    with ExitStack() as stack:
        _apply_common_lifespan_patches(stack, mocks, mock_init_db)
        # GPU/Cleanup are already mocked by the helper; restated here as
        # constructor stand-ins returning those same mocks (re-autospecing
        # an already-patched attr raises InvalidSpecError, and passing the
        # mock itself as new= would hand the lifespan an auto-child instead
        # of the configured mock) so this file's boot posture is stated
        # where it runs: exactly one lifespan service is real -- the
        # broadcaster.
        # (kwargs accepted because the lifespan constructs
        # GPUMonitor(broadcaster=None).)
        stack.enter_context(patch("backend.main.GPUMonitor", new=lambda **_: mocks["gpu_monitor"]))
        stack.enter_context(
            patch("backend.main.CleanupService", new=lambda **_: mocks["cleanup_service"])
        )
        # Rebind AFTER the helper's autospec-mock patch: the lifespan calls
        # this exact module attribute, so the last patch wins and the
        # lifespan creates/starts/attaches the REAL singleton -- which the
        # /ws/system route already resolves via the same factory.
        stack.enter_context(
            patch("backend.main.get_system_broadcaster", new=get_system_broadcaster)
        )

        client = stack.enter_context(TestClient(app))
        yield client
    # ExitStack unwinds here (lifespan shutdown + every patch reverted); the
    # request finalizer registered above then restores env/settings/tracker/
    # emitter -- one restore path, exercised whether setup or the test fails.


def _next_event(session: Any, event_type: str) -> dict[str, Any]:
    """Read frames until one carries ``event_type``; return the message.

    Skips the initial ``system_status`` frame ``connect()`` sends and any
    5s-interval periodic frames; the emitter's per-event envelope uses the
    dotted event name, which the periodic loop never produces.
    """
    for _ in range(_MAX_FRAMES_TO_SKIP):
        message = session.receive_json()
        if message.get("type") == event_type:
            return message
    raise AssertionError(
        f"no {event_type!r} frame within {_MAX_FRAMES_TO_SKIP} frames "
        f"(blocking receive means this is a hang -> pytest-timeout failure)"
    )


class TestSystemBroadcasterLiveDelivery:
    """#6940: system-channel events reach real /ws/system clients."""

    @pytest.mark.timeout(30)
    def test_system_broadcaster_verdict_transition_reaches_ws_system_clients(
        self, live_broadcaster_client: TestClient
    ) -> None:
        """A real verdict-engine transition, delivered over /ws/system.

        Fails without the lifespan's
        ``get_websocket_emitter(system_broadcaster=...)`` attach: the event
        then dies in _dispatch_event's final else (warning logged, no
        delivery) and the receive blocks until pytest-timeout fires.
        """
        client = live_broadcaster_client
        tracker = get_verdict_engine_tracker()
        assert tracker.snapshot.state.value == "unknown"

        with (
            client.websocket_connect("/ws/system") as first,
            client.websocket_connect("/ws/system") as second,
        ):
            # connect() pushes one system_status frame per client up front.
            assert first.receive_json()["type"] == "system_status"
            assert second.receive_json()["type"] == "system_status"

            # Production trigger, on the loop the handler runs on: an
            # unhealthy AI-vlm probe maps to UNAVAILABLE and schedules the
            # transition event fire-and-forget.
            snapshot = client.portal.call(tracker.observe, {"ai-vlm": "probe exploded"})
            assert snapshot.state.value == "unavailable"

            for name, session in (("first", first), ("second", second)):
                event = _next_event(session, "system.verdict_engine_status_changed")
                data = event["data"]
                assert data["state"] == "unavailable", name
                assert data["previous_state"] == "unknown", name
                assert data["source"] == "health_probe", name
