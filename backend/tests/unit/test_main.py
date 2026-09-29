"""Unit tests for main.py initialization functions.

Tests cover:
- init_circuit_breakers() pre-registration of known service circuit breakers
- Signal handling for graceful shutdown (SIGTERM/SIGINT)
- Shutdown event coordination
"""

from __future__ import annotations

import asyncio
import signal
from unittest.mock import MagicMock, patch

import pytest

from backend.services.circuit_breaker import (
    _get_registry,
    reset_circuit_breaker_registry,
)


@pytest.fixture(autouse=True)
def reset_global_registry():
    """Reset global registry before and after each test."""
    reset_circuit_breaker_registry()
    yield
    reset_circuit_breaker_registry()


class TestInitCircuitBreakers:
    """Tests for init_circuit_breakers() function."""

    def test_pre_registers_known_services(self) -> None:
        """Test that init_circuit_breakers registers all known services."""
        from backend.main import init_circuit_breakers

        breaker_names = init_circuit_breakers()

        # Should return all 3 known services. R8 S2b (2026-09-29) deleted the
        # Nemotron analyzer, so its breaker row is gone with it.
        assert len(breaker_names) == 3
        assert sorted(breaker_names) == ["postgresql", "redis", "yolo26"]

    def test_circuit_breakers_appear_in_registry(self) -> None:
        """Test that circuit breakers are registered in global registry."""
        from backend.main import init_circuit_breakers

        init_circuit_breakers()

        registry = _get_registry()
        all_status = registry.get_all_status()

        assert "yolo26" in all_status
        assert "postgresql" in all_status
        assert "redis" in all_status

    def test_ai_service_config_has_lower_threshold(self) -> None:
        """Test that the AI service has a more aggressive (lower) threshold.

        Retargeted on R8 S2b (2026-09-29): this class used to assert the pair
        yolo26 + nemotron shared the AI-service threshold, and nemotron's row
        was deleted with the analyzer. The intent - an AI-service breaker trips
        faster than the tolerant infrastructure config - is still what
        init_circuit_breakers() does, so it is now asserted as the relationship
        between yolo26 and the infrastructure rows rather than as two rows of
        one config.
        """
        from backend.main import init_circuit_breakers

        init_circuit_breakers()

        registry = _get_registry()
        all_status = registry.get_all_status()

        # The AI service uses the aggressive config: failure_threshold=5
        yolo26_config = all_status["yolo26"]["config"]
        assert yolo26_config["failure_threshold"] == 5

        # ...and strictly lower than the generic infrastructure config
        for infra_name in ("postgresql", "redis"):
            infra_config = all_status[infra_name]["config"]
            assert yolo26_config["failure_threshold"] < infra_config["failure_threshold"], (
                f"{infra_name} must not trip faster than the AI service"
            )

    def test_infrastructure_service_config_has_higher_threshold(self) -> None:
        """Test that infrastructure services have higher failure threshold."""
        from backend.main import init_circuit_breakers

        init_circuit_breakers()

        registry = _get_registry()
        all_status = registry.get_all_status()

        # Infrastructure services should have failure_threshold=10
        postgresql_config = all_status["postgresql"]["config"]
        redis_config = all_status["redis"]["config"]
        assert postgresql_config["failure_threshold"] == 10
        assert redis_config["failure_threshold"] == 10

    def test_all_circuit_breakers_start_closed(self) -> None:
        """Test that all circuit breakers start in CLOSED state."""
        from backend.main import init_circuit_breakers

        init_circuit_breakers()

        registry = _get_registry()
        all_status = registry.get_all_status()

        for name, status in all_status.items():
            assert status["state"] == "closed", f"{name} should be in closed state"

    def test_idempotent_registration(self) -> None:
        """Test that calling init_circuit_breakers multiple times is safe."""
        from backend.main import init_circuit_breakers

        # Call multiple times
        first_result = init_circuit_breakers()
        second_result = init_circuit_breakers()

        # Should return same names
        assert first_result == second_result

        # Registry should still have exactly 3 circuit breakers (R8 S2b took
        # the nemotron row down from 4)
        registry = _get_registry()
        all_status = registry.get_all_status()
        assert len(all_status) == 3


@pytest.fixture
def reset_signal_handler_state():
    """Reset signal handler state before and after each test."""
    from backend.main import reset_signal_handlers

    reset_signal_handlers()
    yield
    reset_signal_handlers()


class TestGetShutdownEvent:
    """Tests for get_shutdown_event() function."""

    def test_returns_asyncio_event(self, reset_signal_handler_state: None) -> None:
        """Test that get_shutdown_event returns an asyncio.Event."""
        from backend.main import get_shutdown_event

        event = get_shutdown_event()

        assert isinstance(event, asyncio.Event)
        assert not event.is_set()

    def test_returns_same_event_on_multiple_calls(self, reset_signal_handler_state: None) -> None:
        """Test that get_shutdown_event returns the same event on multiple calls."""
        from backend.main import get_shutdown_event

        event1 = get_shutdown_event()
        event2 = get_shutdown_event()

        assert event1 is event2

    def test_event_can_be_set(self, reset_signal_handler_state: None) -> None:
        """Test that the shutdown event can be set."""
        from backend.main import get_shutdown_event

        event = get_shutdown_event()
        assert not event.is_set()

        event.set()
        assert event.is_set()


class TestInstallSignalHandlers:
    """Tests for install_signal_handlers() function."""

    @pytest.mark.asyncio
    async def test_installs_sigterm_handler(self, reset_signal_handler_state: None) -> None:
        """Test that SIGTERM handler is installed."""
        from backend.main import install_signal_handlers

        mock_loop = MagicMock()
        captured_handlers: dict[signal.Signals, MagicMock] = {}

        def capture_handler(sig: signal.Signals, handler: MagicMock) -> None:
            captured_handlers[sig] = handler

        mock_loop.add_signal_handler = capture_handler

        with patch("asyncio.get_running_loop", return_value=mock_loop, autospec=True):
            install_signal_handlers()

        assert signal.SIGTERM in captured_handlers

    @pytest.mark.asyncio
    async def test_installs_sigint_handler(self, reset_signal_handler_state: None) -> None:
        """Test that SIGINT handler is installed."""
        from backend.main import install_signal_handlers

        mock_loop = MagicMock()
        captured_handlers: dict[signal.Signals, MagicMock] = {}

        def capture_handler(sig: signal.Signals, handler: MagicMock) -> None:
            captured_handlers[sig] = handler

        mock_loop.add_signal_handler = capture_handler

        with patch("asyncio.get_running_loop", return_value=mock_loop, autospec=True):
            install_signal_handlers()

        assert signal.SIGINT in captured_handlers

    @pytest.mark.asyncio
    async def test_handler_sets_shutdown_event(self, reset_signal_handler_state: None) -> None:
        """Test that signal handler sets the shutdown event."""
        from backend.main import get_shutdown_event, install_signal_handlers

        mock_loop = MagicMock()
        captured_handlers: dict[signal.Signals, MagicMock] = {}

        def capture_handler(sig: signal.Signals, handler: MagicMock) -> None:
            captured_handlers[sig] = handler

        mock_loop.add_signal_handler = capture_handler

        with patch("asyncio.get_running_loop", return_value=mock_loop, autospec=True):
            install_signal_handlers()

        # Get the shutdown event
        event = get_shutdown_event()
        assert not event.is_set()

        # Call the SIGTERM handler - the logger is imported inside the function
        # so we patch at the source module
        with patch("backend.core.logging.get_logger", autospec=True):
            captured_handlers[signal.SIGTERM]()

        # Event should be set
        assert event.is_set()

    @pytest.mark.asyncio
    async def test_idempotent_installation(self, reset_signal_handler_state: None) -> None:
        """Test that calling install_signal_handlers multiple times is safe."""
        from backend.main import install_signal_handlers

        mock_loop = MagicMock()
        call_count = 0

        def count_handler(sig: signal.Signals, handler: MagicMock) -> None:
            nonlocal call_count
            call_count += 1

        mock_loop.add_signal_handler = count_handler

        with patch("asyncio.get_running_loop", return_value=mock_loop, autospec=True):
            install_signal_handlers()
            install_signal_handlers()
            install_signal_handlers()

        # Should only install handlers once (2 handlers: SIGTERM and SIGINT)
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_handles_not_implemented_error(self, reset_signal_handler_state: None) -> None:
        """Test that NotImplementedError is handled gracefully (e.g., Windows)."""
        from backend.main import install_signal_handlers

        mock_loop = MagicMock()
        mock_loop.add_signal_handler.side_effect = NotImplementedError(
            "Signals not supported on Windows"
        )

        with patch("asyncio.get_running_loop", return_value=mock_loop, autospec=True):
            # Should not raise
            install_signal_handlers()

    @pytest.mark.asyncio
    async def test_handles_runtime_error(self, reset_signal_handler_state: None) -> None:
        """Test that RuntimeError is handled gracefully (e.g., not main thread)."""
        from backend.main import install_signal_handlers

        with patch(
            "asyncio.get_running_loop",
            side_effect=RuntimeError("no running event loop"),
            autospec=True,
        ):
            # Should not raise
            install_signal_handlers()


class TestResetSignalHandlers:
    """Tests for reset_signal_handlers() function."""

    def test_resets_shutdown_event(self) -> None:
        """Test that reset_signal_handlers clears the shutdown event."""
        from backend.main import get_shutdown_event, reset_signal_handlers

        # Create and set the event
        event1 = get_shutdown_event()
        event1.set()

        # Reset
        reset_signal_handlers()

        # New event should be created
        event2 = get_shutdown_event()
        assert event2 is not event1
        assert not event2.is_set()

    @pytest.mark.asyncio
    async def test_allows_reinstallation_of_handlers(self) -> None:
        """Test that after reset, handlers can be installed again."""
        from backend.main import install_signal_handlers, reset_signal_handlers

        mock_loop = MagicMock()
        call_count = 0

        def count_handler(sig: signal.Signals, handler: MagicMock) -> None:
            nonlocal call_count
            call_count += 1

        mock_loop.add_signal_handler = count_handler

        with patch("asyncio.get_running_loop", return_value=mock_loop, autospec=True):
            install_signal_handlers()
            assert call_count == 2  # SIGTERM and SIGINT

            reset_signal_handlers()

            install_signal_handlers()
            assert call_count == 4  # Should install again after reset


class TestSelectPreloadCandidates:
    """Item 24 / item 1 (owner ruling 2026-09-27, ">= + cfg.preload reader"):
    the boot sweep must honor the per-row `preload:` flag it used to ignore.

    The old inline predicate was `cfg.enabled and not cfg.available`, and
    `available` only flips True AFTER a load (model_zoo.py:734, init False at
    :495) — so at boot it selected EVERY enabled row when the flag was on, and
    nothing when off. `cfg.preload` was parsed (`model_zoo.py:497`) and read by
    nobody, which made models.yml's `preload: true` row (smoke-fire-yolov8n,
    "CRITICAL: never evict, preload at startup") decorative.
    """

    @staticmethod
    def _cfg(name, *, enabled=True, preload=False, available=False):
        from backend.services.model_zoo import ModelConfig

        async def _noop(_path):  # never invoked by the selector
            return None

        return ModelConfig(
            name=name,
            path=f"model-zoo/{name}",
            category="detection",
            vram_mb=100,
            load_fn=_noop,
            enabled=enabled,
            available=available,
            preload=preload,
        )

    def test_flag_off_selects_nothing(self) -> None:
        """CPU/dev-box lazy posture: flag off => zero rows, legs degrade honestly."""
        from backend.main import select_preload_candidates

        zoo = {"m": self._cfg("m", preload=True)}
        assert select_preload_candidates(zoo, preload_enabled=False) == []

    def test_flag_on_selects_only_preload_rows(self) -> None:
        from backend.main import select_preload_candidates

        zoo = {
            "resident": self._cfg("resident", preload=True),
            "lazy": self._cfg("lazy", preload=False),
            "disabled_but_flagged": self._cfg("disabled_but_flagged", enabled=False, preload=True),
        }
        assert select_preload_candidates(zoo, preload_enabled=True) == ["resident"]

    def test_already_loaded_row_not_reselected(self) -> None:
        from backend.main import select_preload_candidates

        zoo = {"loaded": self._cfg("loaded", preload=True, available=True)}
        assert select_preload_candidates(zoo, preload_enabled=True) == []

    def test_lifespan_uses_the_helper_not_the_old_predicate(self) -> None:
        """The helper is the single selection point; the lifespan must call it
        rather than keep the `enabled and not available` inline predicate."""
        from pathlib import Path

        src = Path("backend/main.py").read_text()
        assert "select_preload_candidates(" in src, "lifespan does not use the helper"
        assert "if cfg.enabled and not cfg.available" not in src, (
            "the old availability-shaped predicate is still in the sweep"
        )


class TestAiServiceHealthMonitorConfigs:
    """The monitor must never probe or restart the retired Nemotron LLM.

    Observed on the A5500 box (2026-09-28): the backend's ServiceHealthMonitor
    probed `nemotron`, found it down (it is retired - spec rev 5), and ran
    "Attempting restart (attempt 1/3)" against `ai-llm`. The restart failed
    ONLY because the podman socket was unreachable; with that access the
    backend would have started the 30B LLM on the same 24 GB GPU ai-vlm needs.
    The monitor's list carries no nemotron at all, in every restart branch
    (docker / shell scripts / restart disabled). R8 (2026-09-29) removed the
    legacy arm the earlier form of this class pinned byte-for-byte: one mode
    now, and the pair it pinned was the incident.

    ai-vlm stays OUT of this probe-poll monitor on purpose: ledger 1.3 chose
    breaker-push health for it (see the registration comment in main.py and
    test_vlm_client's source pin), so the monitor lists YOLO26 only.
    """

    @staticmethod
    def _settings(restart: str):
        from backend.core.config import OrchestratorSettings, Settings

        branches = {
            # (orchestrator.enabled, ai_restart_enabled)
            "docker": (True, True),
            "shell": (False, True),
            "disabled": (True, False),
        }
        orchestrator_enabled, restart_enabled = branches[restart]
        # No pipeline_mode kwarg: the default IS the shipped mode.
        return Settings(
            _env_file=None,
            orchestrator=OrchestratorSettings(enabled=orchestrator_enabled),
            ai_restart_enabled=restart_enabled,
            use_ai_gateway=True,
            ai_gateway_url="http://ai-gateway:8090",
            yolo26_url="http://ai-gateway:8090/yolo26",
            # R8 S2b: nemotron_url is DELETED from Settings (extra="ignore", so
            # passing it was silently dropped - a vacuous pin). The monitor's
            # one survivor endpoint is ai-vlm, so the list is now built with the
            # real successor URL and the assertions below still have to prove the
            # monitor probes/restarts neither it nor port 8091.
            ai_vlm_url="http://ai-vlm:8098",
        )

    @pytest.mark.parametrize("restart", ["docker", "shell", "disabled"])
    def test_never_monitors_or_restarts_nemotron(self, restart: str) -> None:
        from backend.main import build_ai_service_health_configs

        configs = build_ai_service_health_configs(self._settings(restart))

        assert [c.name for c in configs] == ["yolo26"], (
            "must monitor YOLO26 only - no nemotron (retired), and no "
            "ai-vlm (breaker-push health by the ledger 1.3 choice)"
        )
        for cfg in configs:
            assert "ai-llm" not in (cfg.restart_cmd or ""), cfg
            assert "start_llm" not in (cfg.restart_cmd or ""), cfg
            assert "8091" not in cfg.health_url, cfg
            # The ai-vlm URL this settings object now carries must not leak into
            # the probe list either: ai-vlm is breaker-push, not monitored.
            assert "ai-vlm" not in cfg.health_url, cfg
            assert "8098" not in cfg.health_url, cfg

    @pytest.mark.parametrize(
        ("restart", "yolo26_cmd"),
        [
            ("docker", "docker restart ai-gateway"),
            ("shell", "ai/start_detector.sh"),
            ("disabled", None),
        ],
    )
    def test_the_yolo26_entry_is_byte_stable(self, restart: str, yolo26_cmd: str | None) -> None:
        """The one entry this list keeps, pinned byte-for-byte per restart
        branch — the retire must not disturb the surviving service."""
        from backend.main import build_ai_service_health_configs
        from backend.services.service_managers import ServiceConfig

        configs = build_ai_service_health_configs(self._settings(restart))

        assert configs == [
            ServiceConfig(
                name="yolo26",
                health_url="http://ai-gateway:8090/health",
                restart_cmd=yolo26_cmd,
                health_timeout=5.0,
                max_retries=3,
                backoff_base=5.0,
            ),
        ]

    def test_lifespan_builds_the_monitor_from_the_helper(self) -> None:
        """The helper is the single place the monitor's list is decided; the
        lifespan must use it, and no inline nemotron ServiceConfig may come
        back to bypass the retired-engine rule."""
        from pathlib import Path

        src = Path("backend/main.py").read_text()
        assert "build_ai_service_health_configs(settings)" in src, (
            "lifespan does not build the monitor list through the helper"
        )
        assert src.count('name="nemotron"') == 0, (
            "an inline nemotron ServiceConfig is back - the retired engine "
            "would be probed and restarted again"
        )
