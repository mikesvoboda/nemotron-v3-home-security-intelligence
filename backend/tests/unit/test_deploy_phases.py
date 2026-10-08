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
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from setup_lib.deploy import DeployConfig
from setup_lib.deploy_phases import (
    _ALLOY_MEMLOCK_BYTES,
    _MODE_PLANS,
    _MONITORING_SERVICES,
    _mode_plan,
    phase_application,
    phase_infrastructure,
    phase_stop,
)

# Mark as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def _no_shell_pipeline_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deploy reads PIPELINE_MODE from the shell too; keep these tests hermetic."""
    monkeypatch.delenv("PIPELINE_MODE", raising=False)


@pytest.fixture
def mock_config(tmp_path: Path) -> DeployConfig:
    """Create mock deployment configuration with writable project root."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    config = DeployConfig(
        project_root=project_root,
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

    @patch("setup_lib.deploy_phases.compose_run", autospec=True)
    @patch("setup_lib.deploy_phases.resource.getrlimit", autospec=True)
    @patch("setup_lib.deploy_phases.time.sleep", autospec=True)
    @patch("setup_lib.deploy_phases._is_service_installed", autospec=True)
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

        # Verify: alloy should NOT be started (check args, not str(c) which includes test name)
        alloy_calls = [
            c for c in mock_compose_run.call_args_list if len(c.args) > 0 and "alloy" in c.args
        ]
        assert len(alloy_calls) == 0, "alloy should not be started when memlock is low"

        # Verify: result should still succeed (alloy failure doesn't block)
        assert result.success is True

    @patch("setup_lib.deploy_phases.compose_run", autospec=True)
    @patch("setup_lib.deploy_phases.resource.getrlimit", autospec=True)
    @patch("setup_lib.deploy_phases.time.sleep", autospec=True)
    @patch("setup_lib.deploy_phases._is_service_installed", autospec=True)
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

    @patch("setup_lib.deploy_phases.compose_run", autospec=True)
    @patch("setup_lib.deploy_phases.resource.getrlimit", autospec=True)
    @patch("setup_lib.deploy_phases.time.sleep", autospec=True)
    @patch("setup_lib.deploy_phases._is_service_installed", autospec=True)
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

    @patch("setup_lib.deploy_phases.compose_run", autospec=True)
    @patch("setup_lib.deploy_phases.resource.getrlimit", autospec=True)
    @patch("setup_lib.deploy_phases.time.sleep", autospec=True)
    @patch("setup_lib.deploy_phases._is_service_installed", autospec=True)
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

    @patch("setup_lib.deploy_phases.compose_run", autospec=True)
    @patch("setup_lib.deploy_phases.resource.getrlimit", autospec=True)
    @patch("setup_lib.deploy_phases.time.sleep", autospec=True)
    @patch("setup_lib.deploy_phases._is_service_installed", autospec=True)
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

    @pytest.fixture(autouse=True)
    def _gpu_present(self):
        """The real pre-flight reads /dev/nvidia0 and shells out to dpkg without it."""
        with patch(
            "setup_lib.deploy_phases._check_gpu_available", return_value=True, autospec=True
        ):
            yield

    def test_vlm_app_services_are_gateway_backend_frontend_and_ai_vlm(
        self, mock_config: DeployConfig
    ) -> None:
        """vlm (default): the retired 30B is not an app service; the VLM is."""
        assert set(_mode_plan(mock_config).app_services) == {
            "ai-gateway",
            "backend",
            "frontend",
            "ai-vlm",
        }

    def test_vlm_app_services_start_ai_vlm_last(self, mock_config: DeployConfig) -> None:
        """ai-vlm is a leaf (backend reaches it by URL, nothing depends_on it), so
        it starts after the gateway -> backend -> frontend chain it is not part of."""
        assert _mode_plan(mock_config).app_services == (
            "ai-gateway",
            "backend",
            "frontend",
            "ai-vlm",
        )

    # test_legacy_app_services_start_with_ai_llm is gone: its subject was the legacy
    # plan's dependency order (ai-llm first, because backend waits on it via
    # service_healthy). R8 S2b deleted that plan -- setup_lib/deploy_phases.py's
    # _MODE_PLANS has the one "vlm" entry and DeployConfig.pipeline_mode raises on
    # "legacy" -- so the tuple this test asserted cannot be constructed any more.
    # The property it expresses ("app_services are in the order the retry loop must
    # walk them") stays pinned for the surviving plan by
    # test_vlm_app_services_start_ai_vlm_last above.

    @patch("setup_lib.deploy_phases.compose_run", autospec=True)
    def test_vlm_wait_call_starts_ai_vlm_by_name_and_never_ai_llm(
        self,
        mock_compose_run: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """The one `up --wait` names ai-vlm in a plain call, sized for the VLM.

        O1.3 (UR-18): ai-vlm is in the default compose set now, so the call
        carries no --profile. 180s: ai-vlm's own healthy-or-unhealthy verdict
        lands by start_period 120s + 3 x 10s retries = 150s; the 30B's 300s is
        legacy's number.
        """
        mock_compose_run.return_value = True

        phase_application(mock_config)

        (wait_call,) = [c for c in mock_compose_run.call_args_list if "--wait" in c.args]
        assert wait_call.args[1:] == (
            "up",
            "-d",
            "--no-build",
            "--wait",
            "--wait-timeout",
            "180",
            "ai-gateway",
            "backend",
            "frontend",
            "ai-vlm",
        )

    # test_legacy_wait_call_keeps_the_30b_budget_under_profile_legacy is gone: it pinned
    # legacy's `up --wait` argv (--profile legacy, 300s for the 30B to load, ai-llm
    # first). R8 S2b deleted the plan that produced it, so no call like that can be
    # emitted. Its property -- "the one --wait call is named exactly, with its
    # budget and service order verbatim" -- has a vlm twin already
    # (test_vlm_wait_call_starts_ai_vlm_by_name_and_never_ai_llm above), so
    # nothing is lost but the 300s/ai-llm row.

    @patch("setup_lib.deploy_phases._wait_container_running", autospec=True)
    @patch("setup_lib.deploy_phases.compose_run", autospec=True)
    def test_vlm_retry_path_passes_no_profile_and_never_names_ai_llm(
        self,
        mock_compose_run: Mock,
        mock_wait_running: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """Per-service retries reach ai-vlm in plain calls, never ai-llm.

        A stale `--profile vlm` here would still work (compose ignores a profile
        no service declares), which is exactly why the argv is pinned: the only
        thing that catches the leftover flag is this assertion.
        """
        mock_compose_run.side_effect = lambda _cfg, *args, **_kw: "--wait" not in args
        mock_wait_running.return_value = True

        phase_application(mock_config)

        calls = [c.args[1:] for c in mock_compose_run.call_args_list]
        assert not any("ai-llm" in args for args in calls)
        assert not any("--profile" in args for args in calls), (
            "deploy still passes a compose profile; ai-vlm ships in the default set"
        )
        retries = [args for args in calls if "--wait" not in args]
        assert retries == [
            ("up", "-d", "--no-build", svc)
            for svc in ("ai-gateway", "backend", "frontend", "ai-vlm")
        ]

    @patch("setup_lib.deploy_phases.compose_run", autospec=True)
    def test_start_message_names_the_model_server_and_its_budget(
        self,
        mock_compose_run: Mock,
        mock_config: DeployConfig,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The progress line must not promise a 5-minute 30B load in vlm mode."""
        mock_compose_run.return_value = True

        phase_application(mock_config)

        out = capsys.readouterr().out
        assert "up to 180s for ai-vlm" in out
        assert "5min" not in out

    @patch("setup_lib.deploy_phases.compose_run", autospec=True)
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

    @patch("setup_lib.deploy_phases.compose_run", autospec=True)
    def test_application_phase_scopes_to_app_services_only(
        self,
        mock_compose_run: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """Test that compose --wait only targets app services, not alloy."""
        mock_compose_run.return_value = True

        phase_application(mock_config)

        # Verify: the --wait call includes app services
        wait_call = next(c for c in mock_compose_run.call_args_list if "--wait" in c.args)
        for svc in _mode_plan(mock_config).app_services:
            assert svc in wait_call.args, f"{svc} should be in --wait call"

        # Verify: alloy is NOT in the --wait call
        assert "alloy" not in wait_call.args, "alloy should not be re-started in phase 5"

    @patch("setup_lib.deploy_phases._wait_container_running", autospec=True)
    @patch("setup_lib.deploy_phases.compose_run", autospec=True)
    def test_application_phase_retries_services_when_compose_wait_fails(
        self,
        mock_compose_run: Mock,
        mock_wait_running: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """Test application phase retries services individually when --wait fails."""

        def compose_run_side_effect(config, *args, **kwargs):
            return "--wait" not in args  # Initial --wait fails, retries succeed

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
            if any(svc in c.args for svc in _mode_plan(mock_config).app_services)
            and "up" in c.args
            and "-d" in c.args
            and "--wait" not in c.args
        ]
        assert len(retry_calls) == 4, "Should retry all 4 app services"

    @patch("setup_lib.deploy_phases._wait_container_running", autospec=True)
    @patch("setup_lib.deploy_phases.compose_run", autospec=True)
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
            for svc in _mode_plan(mock_config).app_services:
                if svc in args and "up" in args and "-d" in args:
                    retried_services.add(svc)
                    return True
            return True

        mock_compose_run.side_effect = compose_run_side_effect
        mock_wait_running.return_value = True

        result = phase_application(mock_config)

        expected_services = set(_mode_plan(mock_config).app_services)
        assert retried_services == expected_services

    @pytest.mark.parametrize("mode", list(_MODE_PLANS))
    @patch("setup_lib.deploy_phases._wait_container_running", autospec=True)
    @patch("setup_lib.deploy_phases.compose_run", autospec=True)
    def test_application_phase_reports_stuck_services(
        self,
        mock_compose_run: Mock,
        mock_wait_running: Mock,
        mock_config: DeployConfig,
        mode: str,
    ) -> None:
        """Test that a stuck model server is reported but phase still succeeds.

        R8 S2b: this walked ["vlm" -> ai-vlm, "legacy" -> ai-llm]; the legacy row
        is gone with its plan, so the server under test is read from the plan
        itself and any future plan is covered by the same row-generation.
        """
        server = _MODE_PLANS[mode].model_server

        def compose_run_side_effect(config, *args, **kwargs):
            return "--wait" not in args

        mock_config.env["PIPELINE_MODE"] = mode
        mock_compose_run.side_effect = compose_run_side_effect
        # The mode's model server doesn't reach running, others do
        mock_wait_running.side_effect = lambda svc, timeout=60: svc != server  # noqa: ARG005

        result = phase_application(mock_config)

        # Phase still succeeds (degraded is OK, deployment continues)
        assert result.success is True
        assert server in result.message


class TestApplicationPhaseGpuPreflight:
    """The missing-GPU warning names the GPU services this mode actually starts."""

    @patch("setup_lib.deploy_phases.compose_run", return_value=True, autospec=True)
    @patch("setup_lib.deploy_phases.subprocess.run", autospec=True)
    @patch("setup_lib.deploy_phases._check_gpu_available", return_value=False, autospec=True)
    def test_vlm_warning_names_ai_vlm_not_ai_llm(
        self,
        mock_gpu: Mock,
        mock_subprocess_run: Mock,
        mock_compose_run: Mock,
        mock_config: DeployConfig,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Driver installed but /dev/nvidia0 missing: the vlm stack's GPU services."""
        mock_subprocess_run.return_value = MagicMock(returncode=0, stdout="ii nvidia-driver-580")

        phase_application(mock_config)

        out = capsys.readouterr().out
        assert "GPU services (ai-vlm, ai-gateway)" in out
        assert "ai-llm" not in out


# =============================================================================
# Stop Phase - Non-Destructive Repair Tests
# =============================================================================


class TestStopPhaseNonDestructiveRepair:
    """Tests for non-destructive repair logic in phase_stop."""

    @patch("setup_lib.deploy_phases.compose_run", autospec=True)
    @patch("setup_lib.deploy_phases.subprocess.run", autospec=True)
    @patch("setup_lib.deploy_phases.time.sleep", autospec=True)
    @patch("setup_lib.deploy_phases.check_port_available", autospec=True)
    @patch("setup_lib.deploy_phases._run_sudo", autospec=True)
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

    @patch("setup_lib.deploy_phases.compose_run", autospec=True)
    @patch("setup_lib.deploy_phases.subprocess.run", autospec=True)
    @patch("setup_lib.deploy_phases.time.sleep", autospec=True)
    @patch("setup_lib.deploy_phases.check_port_available", autospec=True)
    @patch("setup_lib.deploy_phases._run_sudo", autospec=True)
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

    @patch("setup_lib.deploy_phases.compose_run", autospec=True)
    @patch("setup_lib.deploy_phases.subprocess.run", autospec=True)
    @patch("setup_lib.deploy_phases.time.sleep", autospec=True)
    @patch("setup_lib.deploy_phases.check_port_available", autospec=True)
    @patch("setup_lib.deploy_phases._run_sudo", autospec=True)
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

    @patch("setup_lib.deploy_phases.compose_run", autospec=True)
    @patch("setup_lib.deploy_phases.subprocess.run", autospec=True)
    @patch("setup_lib.deploy_phases.time.sleep", autospec=True)
    @patch("setup_lib.deploy_phases.check_port_available", autospec=True)
    @patch("setup_lib.deploy_phases._run_sudo", autospec=True)
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

    @patch("setup_lib.deploy_phases.compose_run", autospec=True)
    @patch("setup_lib.deploy_phases.subprocess.run", autospec=True)
    @patch("setup_lib.deploy_phases.time.sleep", autospec=True)
    @patch("setup_lib.deploy_phases.check_port_available", autospec=True)
    @patch("setup_lib.deploy_phases._run_sudo", autospec=True)
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

    @patch("setup_lib.deploy_phases.compose_run", autospec=True)
    @patch("setup_lib.deploy_phases.resource.getrlimit", autospec=True)
    @patch("setup_lib.deploy_phases.time.sleep", autospec=True)
    @patch("setup_lib.deploy_phases._is_service_installed", autospec=True)
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

    @patch("setup_lib.deploy_phases._wait_container_running", autospec=True)
    @patch("setup_lib.deploy_phases.compose_run", autospec=True)
    def test_application_phase_retry_logic_is_resilient(
        self,
        mock_compose_run: Mock,
        mock_wait_running: Mock,
        mock_config: DeployConfig,
    ) -> None:
        """Test that application phase retry logic handles various failure modes."""

        def compose_run_side_effect(config, *args, **kwargs):
            return "--wait" not in args  # Initial --wait fails, retries succeed

        mock_compose_run.side_effect = compose_run_side_effect
        mock_wait_running.return_value = True

        # Execute
        result = phase_application(mock_config)

        # Verify: should eventually succeed despite initial failures
        assert result.success is True


# =============================================================================
# Mode plans vs docker-compose.prod.yml (read, never run)
# =============================================================================


@pytest.fixture(scope="module")
def services() -> dict:
    """docker-compose.prod.yml's services block (parsed, never run)."""
    import yaml

    compose = Path(__file__).resolve().parents[3] / "docker-compose.prod.yml"
    return yaml.safe_load(compose.read_text(encoding="utf-8"))["services"]


class TestModePlansMatchCompose:
    """_MODE_PLANS restates compose facts; pin them so a compose edit cannot
    silently strand deploy (a service that moved out of the default set would
    make deploy's plain `up` skip it; a moved start_period would desync the
    budgets)."""

    @pytest.mark.parametrize("mode", list(_MODE_PLANS))
    def test_model_server_is_in_the_default_compose_set(self, services: dict, mode: str) -> None:
        """Every plan's model server is profile-free, and deploy passes no profile.

        O1.3 (UR-18): ai-vlm used to sit behind profile `vlm`, and every compose
        call deploy made carried that profile because podman-compose drops a
        service whose profile is inactive before it resolves command-line
        targets. The shipped verdict engine now starts with the default `up`, so
        the plan carries no profile at all and no call needs one.

        Parametrized off ``_MODE_PLANS`` itself rather than a written-out list:
        the drift this catches is a plan whose model server gained a
        ``profiles:`` block deploy does not pass (every plain call then starts
        nothing) and a new plan with no compose row at all.
        """
        plan = _MODE_PLANS[mode]
        assert not services[plan.model_server].get("profiles"), (
            f"{plan.model_server} is profile-gated again: deploy names it in a "
            "plain call, which silently starts nothing"
        )
        assert not hasattr(plan, "profile"), (
            "the deploy plan still carries a compose profile; with the model "
            "server in the default set it must pass none"
        )

    @pytest.mark.parametrize("mode", list(_MODE_PLANS))
    def test_app_services_exist_and_none_is_profiled(self, services: dict, mode: str) -> None:
        """Same read from the other side: everything deploy names by hand exists,
        and none of it is hidden behind a profile deploy does not pass."""
        plan = _MODE_PLANS[mode]
        for svc in plan.app_services:
            assert svc in services, f"{svc} missing from docker-compose.prod.yml"
            assert not services[svc].get("profiles"), f"{svc} is profiled"

    def test_vlm_budgets_follow_ai_vlm_start_period(self, services: dict) -> None:
        """Health poll = start_period; --wait covers start_period + interval x retries."""
        hc = services["ai-vlm"]["healthcheck"]
        start, interval = int(hc["start_period"].rstrip("s")), int(hc["interval"].rstrip("s"))
        plan = _MODE_PLANS["vlm"]
        assert plan.health_timeout == start
        assert plan.wait_timeout >= start + interval * hc["retries"]

    # test_legacy_wait_is_ai_llm_start_period is gone: it cross-checked legacy's
    # wait_timeout against ai-llm's compose start_period (300s), and both sides of
    # that equality were deleted at R8 S2b -- the plan with it, the service behind
    # it. The budget-vs-compose cross-check it was one half of is the vlm-shaped
    # test above, which pins ai-vlm's health poll to start_period and the --wait
    # budget to start_period + interval x retries.
