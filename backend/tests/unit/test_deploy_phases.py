"""Unit tests for deployment phase implementations.

Tests cover the three key fixes made in deploy_phases.py:
1. Alloy isolation with memlock pre-check
2. Service retry logic for application phase
3. Non-destructive repair in stop phase

Test Categories:
- Monitoring services list validation (alloy isolation)
- Infrastructure phase memlock handling
- Application phase retry logic
- Stop phase repair vs reset fallback
"""

from __future__ import annotations

import resource
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from setup_lib.deploy import DeployConfig
from setup_lib.deploy_phases import (
    _ALLOY_MEMLOCK_BYTES,
    _APP_SERVICES,
    _MONITORING_SERVICES,
    phase_application,
    phase_infrastructure,
    phase_stop,
)

# Mark as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_config() -> DeployConfig:
    """Create mock deployment configuration."""
    config = DeployConfig(
        project_root=Path("/test/project"),
        compose_file="docker-compose.prod.yml",
        compose_cmd=["podman", "compose"],
        env={
            "POSTGRES_PORT": "5432",
            "REDIS_PORT": "6379",
            "API_PORT": "8000",
            "AI_GATEWAY_PORT": "8090",
            "LLM_PORT": "8091",
        },
    )
    return config


# =============================================================================
# Monitoring Services List Tests
# =============================================================================


class TestMonitoringServicesList:
    """Tests for _MONITORING_SERVICES constant."""

    def test_alloy_not_in_monitoring_services_list(self) -> None:
        """Test that alloy is NOT in _MONITORING_SERVICES list.

        Alloy must be started separately due to memlock requirements.
        """
        assert "alloy" not in _MONITORING_SERVICES

    def test_monitoring_services_list_contains_expected_services(self) -> None:
        """Test that _MONITORING_SERVICES contains expected services."""
        expected = {
            "prometheus",
            "grafana",
            "loki",
            "tempo",
            "alertmanager",
            "node-exporter",
            "pyroscope",
            "blackbox-exporter",
            "json-exporter",
            "redis-exporter",
        }
        assert expected.issubset(set(_MONITORING_SERVICES))

    def test_monitoring_services_list_is_not_empty(self) -> None:
        """Test that _MONITORING_SERVICES is not empty."""
        assert len(_MONITORING_SERVICES) > 0


# =============================================================================
# Infrastructure Phase - Alloy Memlock Tests
# =============================================================================


class TestInfrastructurePhaseAlloyMemlock:
    """Tests for alloy memlock pre-check in phase_infrastructure."""

    @patch("setup_lib.deploy_phases.compose_run")
    @patch("setup_lib.deploy_phases.resource.getrlimit")
    @patch("setup_lib.deploy_phases.time.sleep")
    @patch("setup_lib.deploy_phases._is_service_installed")
    def test_alloy_skipped_when_memlock_below_threshold(
        self,
        mock_is_installed: Mock,
        mock_sleep: Mock,
        mock_getrlimit: Mock,
        mock_compose_run: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """Test that alloy is skipped when memlock limit is below 8GB."""
        # Setup: memlock limit is 4GB (below threshold)
        mock_getrlimit.return_value = (4 * 1024**3, 16 * 1024**3)  # soft=4GB, hard=16GB
        mock_compose_run.return_value = True
        mock_is_installed.return_value = False

        # Execute
        result = phase_infrastructure(mock_config)

        # Verify: alloy should NOT be started
        alloy_calls = [c for c in mock_compose_run.call_args_list if "alloy" in str(c)]
        assert len(alloy_calls) == 0, "alloy should not be started when memlock is low"

        # Verify: result should still succeed (alloy failure doesn't block)
        assert result.success is True

    @patch("setup_lib.deploy_phases.compose_run")
    @patch("setup_lib.deploy_phases.resource.getrlimit")
    @patch("setup_lib.deploy_phases.time.sleep")
    @patch("setup_lib.deploy_phases._is_service_installed")
    def test_alloy_started_when_memlock_sufficient(
        self,
        mock_is_installed: Mock,
        mock_sleep: Mock,
        mock_getrlimit: Mock,
        mock_compose_run: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """Test that alloy is started when memlock limit is sufficient."""
        # Setup: memlock limit is 16GB (above threshold)
        mock_getrlimit.return_value = (16 * 1024**3, 64 * 1024**3)  # soft=16GB
        mock_compose_run.return_value = True
        mock_is_installed.return_value = False

        # Execute
        result = phase_infrastructure(mock_config)

        # Verify: alloy should be started
        alloy_calls = [
            c for c in mock_compose_run.call_args_list if len(c.args) > 0 and "alloy" in c.args
        ]
        assert len(alloy_calls) == 1, "alloy should be started when memlock is sufficient"

        # Verify: the call includes "up -d alloy"
        alloy_call_args = alloy_calls[0].args
        assert "up" in alloy_call_args
        assert "-d" in alloy_call_args
        assert "alloy" in alloy_call_args

        # Verify: result should succeed
        assert result.success is True

    @patch("setup_lib.deploy_phases.compose_run")
    @patch("setup_lib.deploy_phases.resource.getrlimit")
    @patch("setup_lib.deploy_phases.time.sleep")
    @patch("setup_lib.deploy_phases._is_service_installed")
    def test_alloy_started_when_memlock_is_infinity(
        self,
        mock_is_installed: Mock,
        mock_sleep: Mock,
        mock_getrlimit: Mock,
        mock_compose_run: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """Test that alloy is started when memlock limit is RLIM_INFINITY."""
        # Setup: memlock limit is unlimited
        mock_getrlimit.return_value = (
            resource.RLIM_INFINITY,
            resource.RLIM_INFINITY,
        )
        mock_compose_run.return_value = True
        mock_is_installed.return_value = False

        # Execute
        result = phase_infrastructure(mock_config)

        # Verify: alloy should be started (INFINITY bypasses threshold check)
        alloy_calls = [
            c for c in mock_compose_run.call_args_list if len(c.args) > 0 and "alloy" in c.args
        ]
        assert len(alloy_calls) == 1

        # Verify: result should succeed
        assert result.success is True

    @patch("setup_lib.deploy_phases.compose_run")
    @patch("setup_lib.deploy_phases.resource.getrlimit")
    @patch("setup_lib.deploy_phases.time.sleep")
    @patch("setup_lib.deploy_phases._is_service_installed")
    def test_alloy_failure_does_not_block_infrastructure_phase(
        self,
        mock_is_installed: Mock,
        mock_sleep: Mock,
        mock_getrlimit: Mock,
        mock_compose_run: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """Test that alloy failure doesn't block phase_infrastructure."""
        # Setup: memlock sufficient, but alloy start fails
        mock_getrlimit.return_value = (16 * 1024**3, 64 * 1024**3)
        mock_is_installed.return_value = False

        def compose_run_side_effect(config, *args, **kwargs):
            # Core services succeed, alloy fails
            return "alloy" not in args

        mock_compose_run.side_effect = compose_run_side_effect

        # Execute
        result = phase_infrastructure(mock_config)

        # Verify: phase should still succeed despite alloy failure
        assert result.success is True

    @patch("setup_lib.deploy_phases.compose_run")
    @patch("setup_lib.deploy_phases.resource.getrlimit")
    @patch("setup_lib.deploy_phases.time.sleep")
    @patch("setup_lib.deploy_phases._is_service_installed")
    def test_alloy_memlock_threshold_matches_compose_config(
        self,
        mock_is_installed: Mock,
        mock_sleep: Mock,
        mock_getrlimit: Mock,
        mock_compose_run: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """Test that _ALLOY_MEMLOCK_BYTES constant is 8GB (8589934592 bytes)."""
        # Verify the threshold constant
        assert _ALLOY_MEMLOCK_BYTES == 8_589_934_592  # 8 GB

        # Verify boundary: 8GB - 1 byte should skip alloy
        mock_getrlimit.return_value = (_ALLOY_MEMLOCK_BYTES - 1, 16 * 1024**3)
        mock_compose_run.return_value = True
        mock_is_installed.return_value = False

        result = phase_infrastructure(mock_config)

        alloy_calls = [
            c for c in mock_compose_run.call_args_list if len(c.args) > 0 and "alloy" in c.args
        ]
        assert len(alloy_calls) == 0, "alloy should be skipped at threshold - 1 byte"


# =============================================================================
# Application Phase - Service Retry Tests
# =============================================================================


class TestApplicationPhaseServiceRetry:
    """Tests for individual service retry logic in phase_application."""

    def test_app_services_constant_has_all_critical_services(self) -> None:
        """Test that _APP_SERVICES contains all critical application services."""
        expected = {"backend", "frontend", "ai-gateway", "ai-llm"}
        assert set(_APP_SERVICES) == expected

    def test_app_services_starts_with_ai_llm(self) -> None:
        """Test that ai-llm is first in _APP_SERVICES (backend depends on it)."""
        assert _APP_SERVICES[0] == "ai-llm"

    @patch("setup_lib.deploy_phases.compose_run")
    def test_application_phase_succeeds_when_compose_wait_succeeds(
        self,
        mock_compose_run: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """Test application phase succeeds when initial compose --wait succeeds."""
        # Setup: compose --wait succeeds immediately
        mock_compose_run.return_value = True

        # Execute
        result = phase_application(mock_config)

        # Verify: should succeed without retries
        assert result.success is True
        assert result.message == "Application services started"

        # Verify: only one compose call (the initial --wait)
        compose_calls = mock_compose_run.call_args_list
        wait_calls = [c for c in compose_calls if "--wait" in c.args]
        assert len(wait_calls) == 1

    @patch("setup_lib.deploy_phases.compose_run")
    def test_application_phase_scopes_to_app_services_only(
        self,
        mock_compose_run: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """Test that compose --wait only targets app services, not alloy."""
        mock_compose_run.return_value = True

        phase_application(mock_config)

        # Verify: the --wait call includes app services
        wait_call = [c for c in mock_compose_run.call_args_list if "--wait" in c.args][0]
        for svc in _APP_SERVICES:
            assert svc in wait_call.args, f"{svc} should be in --wait call"

        # Verify: alloy is NOT in the --wait call
        assert "alloy" not in wait_call.args, "alloy should not be re-started in phase 5"

    @patch("setup_lib.deploy_phases._wait_container_running")
    @patch("setup_lib.deploy_phases.compose_run")
    def test_application_phase_retries_services_when_compose_wait_fails(
        self,
        mock_compose_run: Mock,
        mock_wait_running: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """Test application phase retries services individually when --wait fails."""

        def compose_run_side_effect(config, *args, **kwargs):
            if "--wait" in args:
                return False  # Initial --wait fails
            return True  # Individual retries succeed

        mock_compose_run.side_effect = compose_run_side_effect
        mock_wait_running.return_value = True  # All containers reach running

        result = phase_application(mock_config)

        # Verify: should succeed after retries
        assert result.success is True

        # Verify: retries for critical services were attempted
        compose_calls = mock_compose_run.call_args_list
        retry_calls = [
            c
            for c in compose_calls
            if any(svc in c.args for svc in _APP_SERVICES)
            and "up" in c.args
            and "-d" in c.args
            and "--wait" not in c.args
        ]
        assert len(retry_calls) == 4, "Should retry all 4 app services"

    @patch("setup_lib.deploy_phases._wait_container_running")
    @patch("setup_lib.deploy_phases.compose_run")
    def test_application_phase_retries_all_critical_services(
        self,
        mock_compose_run: Mock,
        mock_wait_running: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """Test that all critical services are retried individually."""
        retried_services = set()

        def compose_run_side_effect(config, *args, **kwargs):
            if "--wait" in args:
                return False  # Initial --wait fails
            for svc in _APP_SERVICES:
                if svc in args and "up" in args and "-d" in args:
                    retried_services.add(svc)
                    return True
            return True

        mock_compose_run.side_effect = compose_run_side_effect
        mock_wait_running.return_value = True

        result = phase_application(mock_config)

        expected_services = set(_APP_SERVICES)
        assert retried_services == expected_services

    @patch("setup_lib.deploy_phases._wait_container_running")
    @patch("setup_lib.deploy_phases.compose_run")
    def test_application_phase_reports_stuck_services(
        self,
        mock_compose_run: Mock,
        mock_wait_running: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """Test that stuck services are reported but phase still succeeds."""

        def compose_run_side_effect(config, *args, **kwargs):
            if "--wait" in args:
                return False
            return True

        mock_compose_run.side_effect = compose_run_side_effect
        # ai-llm doesn't reach running, others do
        mock_wait_running.side_effect = lambda svc, timeout=60: svc != "ai-llm"

        result = phase_application(mock_config)

        # Phase still succeeds (degraded is OK, deployment continues)
        assert result.success is True
        assert "ai-llm" in result.message


# =============================================================================
# Stop Phase - Non-Destructive Repair Tests
# =============================================================================


class TestStopPhaseNonDestructiveRepair:
    """Tests for non-destructive repair logic in phase_stop."""

    @patch("setup_lib.deploy_phases.compose_run")
    @patch("setup_lib.deploy_phases.subprocess.run")
    @patch("setup_lib.deploy_phases.time.sleep")
    @patch("setup_lib.deploy_phases.check_port_available")
    @patch("setup_lib.deploy_phases._run_sudo")
    def test_stop_phase_skips_repair_when_storage_is_healthy(
        self,
        mock_run_sudo: Mock,
        mock_check_port: Mock,
        mock_sleep: Mock,
        mock_subprocess_run: Mock,
        mock_compose_run: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """Test that repair is skipped when podman system check succeeds."""

        # Setup: system check succeeds (rc=0)
        def subprocess_run_side_effect(*args, **kwargs):
            cmd = args[0] if args else []
            if "podman" in cmd and "system" in cmd and "check" in cmd:
                result = MagicMock()
                result.returncode = 0
                result.stderr = ""
                return result
            # Other subprocess calls
            result = MagicMock()
            result.returncode = 0
            return result

        mock_subprocess_run.side_effect = subprocess_run_side_effect
        mock_compose_run.return_value = True
        mock_check_port.return_value = True

        # Execute
        result = phase_stop(mock_config)

        # Verify: repair should NOT be attempted
        repair_calls = [
            c
            for c in mock_subprocess_run.call_args_list
            if len(c.args) > 0 and "--repair" in " ".join(c.args[0])
        ]
        assert len(repair_calls) == 0, "repair should not run when storage is healthy"

        # Verify: reset should NOT be attempted
        reset_calls = [
            c
            for c in mock_subprocess_run.call_args_list
            if len(c.args) > 0 and "system" in c.args[0] and "reset" in c.args[0]
        ]
        assert len(reset_calls) == 0, "reset should not run when storage is healthy"

        # Verify: phase succeeds
        assert result.success is True

    @patch("setup_lib.deploy_phases.compose_run")
    @patch("setup_lib.deploy_phases.subprocess.run")
    @patch("setup_lib.deploy_phases.time.sleep")
    @patch("setup_lib.deploy_phases.check_port_available")
    @patch("setup_lib.deploy_phases._run_sudo")
    def test_stop_phase_tries_repair_before_reset_on_corruption(
        self,
        mock_run_sudo: Mock,
        mock_check_port: Mock,
        mock_sleep: Mock,
        mock_subprocess_run: Mock,
        mock_compose_run: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """Test that non-destructive repair is tried before reset."""
        # Setup: system check fails, repair succeeds
        check_call_count = 0

        def subprocess_run_side_effect(*args, **kwargs):
            nonlocal check_call_count
            cmd = args[0] if args else []

            # system check (without --repair)
            if "podman" in cmd and "system" in cmd and "check" in cmd and "--repair" not in cmd:
                check_call_count += 1
                result = MagicMock()
                result.returncode = 1  # Corruption detected
                result.stderr = "storage corruption detected"
                return result

            # system check --repair
            if "podman" in cmd and "--repair" in cmd:
                result = MagicMock()
                result.returncode = 0  # Repair succeeds
                return result

            # Other commands
            result = MagicMock()
            result.returncode = 0
            return result

        mock_subprocess_run.side_effect = subprocess_run_side_effect
        mock_compose_run.return_value = True
        mock_check_port.return_value = True

        # Execute
        result = phase_stop(mock_config)

        # Verify: repair was attempted
        repair_calls = [
            c
            for c in mock_subprocess_run.call_args_list
            if len(c.args) > 0 and "--repair" in " ".join(c.args[0])
        ]
        assert len(repair_calls) == 1, "repair should be attempted once"

        # Verify: reset should NOT be called (repair succeeded)
        reset_calls = [
            c
            for c in mock_subprocess_run.call_args_list
            if len(c.args) > 0 and "system" in c.args[0] and "reset" in c.args[0]
        ]
        assert len(reset_calls) == 0, "reset should not run when repair succeeds"

        # Verify: phase succeeds
        assert result.success is True

    @patch("setup_lib.deploy_phases.compose_run")
    @patch("setup_lib.deploy_phases.subprocess.run")
    @patch("setup_lib.deploy_phases.time.sleep")
    @patch("setup_lib.deploy_phases.check_port_available")
    @patch("setup_lib.deploy_phases._run_sudo")
    def test_stop_phase_falls_back_to_reset_when_repair_fails(
        self,
        mock_run_sudo: Mock,
        mock_check_port: Mock,
        mock_sleep: Mock,
        mock_subprocess_run: Mock,
        mock_compose_run: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """Test that reset is used as fallback when repair fails."""

        # Setup: system check fails, repair fails, reset succeeds
        def subprocess_run_side_effect(*args, **kwargs):
            cmd = args[0] if args else []

            # system check (without --repair)
            if "podman" in cmd and "system" in cmd and "check" in cmd and "--repair" not in cmd:
                result = MagicMock()
                result.returncode = 1  # Corruption detected
                result.stderr = "storage corruption detected"
                return result

            # system check --repair (fails)
            if "podman" in cmd and "--repair" in cmd:
                result = MagicMock()
                result.returncode = 1  # Repair fails
                result.stderr = "repair failed"
                return result

            # system reset (succeeds)
            if "podman" in cmd and "reset" in cmd:
                result = MagicMock()
                result.returncode = 0
                return result

            # Other commands
            result = MagicMock()
            result.returncode = 0
            return result

        mock_subprocess_run.side_effect = subprocess_run_side_effect
        mock_compose_run.return_value = True
        mock_check_port.return_value = True

        # Execute
        result = phase_stop(mock_config)

        # Verify: repair was attempted
        repair_calls = [
            c
            for c in mock_subprocess_run.call_args_list
            if len(c.args) > 0 and "--repair" in " ".join(c.args[0])
        ]
        assert len(repair_calls) == 1, "repair should be attempted"

        # Verify: reset was called as fallback
        reset_calls = [
            c
            for c in mock_subprocess_run.call_args_list
            if len(c.args) > 0 and "system" in c.args[0] and "reset" in c.args[0]
        ]
        assert len(reset_calls) == 1, "reset should be called when repair fails"

        # Verify: systemctl restart podman.socket was called after reset
        socket_restart_calls = [
            c
            for c in mock_subprocess_run.call_args_list
            if len(c.args) > 0
            and "systemctl" in c.args[0]
            and "restart" in c.args[0]
            and "podman.socket" in c.args[0]
        ]
        assert len(socket_restart_calls) == 1, "podman.socket should be restarted after reset"

        # Verify: phase succeeds
        assert result.success is True

    @patch("setup_lib.deploy_phases.compose_run")
    @patch("setup_lib.deploy_phases.subprocess.run")
    @patch("setup_lib.deploy_phases.time.sleep")
    @patch("setup_lib.deploy_phases.check_port_available")
    @patch("setup_lib.deploy_phases._run_sudo")
    def test_stop_phase_skips_repair_on_unrecognized_command_podman4(
        self,
        mock_run_sudo: Mock,
        mock_check_port: Mock,
        mock_sleep: Mock,
        mock_subprocess_run: Mock,
        mock_compose_run: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """Test that repair is skipped when podman check is unrecognized (Podman 4.x)."""

        # Setup: system check returns "unrecognized command" (Podman 4.x)
        def subprocess_run_side_effect(*args, **kwargs):
            cmd = args[0] if args else []

            # system check not supported (Podman 4.x)
            if "podman" in cmd and "system" in cmd and "check" in cmd:
                result = MagicMock()
                result.returncode = 125  # Command error
                result.stderr = "unrecognized command `podman system check`"
                return result

            # Other commands
            result = MagicMock()
            result.returncode = 0
            return result

        mock_subprocess_run.side_effect = subprocess_run_side_effect
        mock_compose_run.return_value = True
        mock_check_port.return_value = True

        # Execute
        result = phase_stop(mock_config)

        # Verify: repair should NOT be attempted (command doesn't exist)
        repair_calls = [
            c
            for c in mock_subprocess_run.call_args_list
            if len(c.args) > 0 and "--repair" in " ".join(c.args[0])
        ]
        assert len(repair_calls) == 0, "repair should not run on Podman 4.x (unrecognized command)"

        # Verify: reset should NOT be called
        reset_calls = [
            c
            for c in mock_subprocess_run.call_args_list
            if len(c.args) > 0 and "system" in c.args[0] and "reset" in c.args[0]
        ]
        assert len(reset_calls) == 0, "reset should not run on unrecognized command"

        # Verify: phase succeeds
        assert result.success is True

    @patch("setup_lib.deploy_phases.compose_run")
    @patch("setup_lib.deploy_phases.subprocess.run")
    @patch("setup_lib.deploy_phases.time.sleep")
    @patch("setup_lib.deploy_phases.check_port_available")
    @patch("setup_lib.deploy_phases._run_sudo")
    def test_stop_phase_repair_preserves_images_reset_destroys_them(
        self,
        mock_run_sudo: Mock,
        mock_check_port: Mock,
        mock_sleep: Mock,
        mock_subprocess_run: Mock,
        mock_compose_run: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """Test that repair uses --repair --force (preserves images)."""

        # Setup: corruption detected, repair succeeds
        def subprocess_run_side_effect(*args, **kwargs):
            cmd = args[0] if args else []

            # system check fails
            if "podman" in cmd and "system" in cmd and "check" in cmd and "--repair" not in cmd:
                result = MagicMock()
                result.returncode = 1
                result.stderr = "corruption"
                return result

            # repair succeeds
            if "podman" in cmd and "--repair" in cmd:
                result = MagicMock()
                result.returncode = 0
                # Verify correct flags
                assert "--repair" in cmd
                assert "--force" in cmd
                assert "--reset" not in cmd
                return result

            result = MagicMock()
            result.returncode = 0
            return result

        mock_subprocess_run.side_effect = subprocess_run_side_effect
        mock_compose_run.return_value = True
        mock_check_port.return_value = True

        # Execute
        phase_stop(mock_config)

        # Verify: repair was called with correct flags
        repair_calls = [
            c
            for c in mock_subprocess_run.call_args_list
            if len(c.args) > 0
            and "--repair" in " ".join(c.args[0])
            and "--force" in " ".join(c.args[0])
        ]
        assert len(repair_calls) == 1


# =============================================================================
# Integration Tests - Combined Behavior
# =============================================================================


class TestDeployPhasesIntegration:
    """Integration tests for combined deploy phase behavior."""

    @patch("setup_lib.deploy_phases.compose_run")
    @patch("setup_lib.deploy_phases.resource.getrlimit")
    @patch("setup_lib.deploy_phases.time.sleep")
    @patch("setup_lib.deploy_phases._is_service_installed")
    def test_infrastructure_phase_completes_without_alloy(
        self,
        mock_is_installed: Mock,
        mock_sleep: Mock,
        mock_getrlimit: Mock,
        mock_compose_run: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """Test that infrastructure phase completes successfully without alloy."""
        # Setup: low memlock (alloy skipped), all other services succeed
        mock_getrlimit.return_value = (64 * 1024 * 1024, 128 * 1024 * 1024)  # 64MB
        mock_compose_run.return_value = True
        mock_is_installed.return_value = False

        # Execute
        result = phase_infrastructure(mock_config)

        # Verify: phase succeeds
        assert result.success is True

        # Verify: core services were started
        compose_calls = mock_compose_run.call_args_list
        postgres_calls = [c for c in compose_calls if len(c.args) > 0 and "postgres" in c.args]
        assert len(postgres_calls) > 0, "postgres should be started"

        redis_calls = [c for c in compose_calls if len(c.args) > 0 and "redis" in c.args]
        assert len(redis_calls) > 0, "redis should be started"

        # Verify: monitoring services were started
        monitoring_started = False
        for call_args in compose_calls:
            if any(svc in call_args.args for svc in _MONITORING_SERVICES):
                monitoring_started = True
                break
        assert monitoring_started, "monitoring services should be started"

    @patch("setup_lib.deploy_phases._wait_container_running")
    @patch("setup_lib.deploy_phases.compose_run")
    def test_application_phase_retry_logic_is_resilient(
        self,
        mock_compose_run: Mock,
        mock_wait_running: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """Test that application phase retry logic handles various failure modes."""

        def compose_run_side_effect(config, *args, **kwargs):
            if "--wait" in args:
                return False  # Initial --wait fails
            return True  # Individual retries succeed

        mock_compose_run.side_effect = compose_run_side_effect
        mock_wait_running.return_value = True

        # Execute
        result = phase_application(mock_config)

        # Verify: should eventually succeed despite initial failures
        assert result.success is True
