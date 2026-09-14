"""Unit tests for setup_lib.deploy_phases module.

Tests deployment phase implementations: stop, build, export,
infrastructure, application, and health check phases.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestPhaseStop:
    """Tests for phase_stop() function."""

    def test_runs_compose_down(self, tmp_path: Path) -> None:
        """Should run compose down to stop containers."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_stop

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={"POSTGRES_PORT": "5432", "REDIS_PORT": "6379"},
        )

        with (
            patch("setup_lib.deploy_phases.compose_run") as mock_compose,
            patch("subprocess.run") as mock_run,
            patch("setup_lib.deploy_phases._run_sudo"),
            patch("setup_lib.deploy_phases.check_port_available", return_value=True),
            patch("time.sleep"),
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            result = phase_stop(config)

            assert result.success is True
            # Verify compose down was called
            compose_calls = [str(c) for c in mock_compose.call_args_list]
            assert any("down" in c for c in compose_calls)

    def test_kills_rootlessport(self, tmp_path: Path) -> None:
        """Should kill orphaned rootlessport processes."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_stop

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={"POSTGRES_PORT": "5432", "REDIS_PORT": "6379"},
        )

        with (
            patch("setup_lib.deploy_phases.compose_run"),
            patch("subprocess.run") as mock_run,
            patch("setup_lib.deploy_phases._run_sudo"),
            patch("setup_lib.deploy_phases.check_port_available", return_value=True),
            patch("time.sleep"),
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            phase_stop(config)

            # Verify pkill was called for rootlessport
            run_calls = mock_run.call_args_list
            pkill_calls = [c for c in run_calls if "pkill" in str(c)]
            assert len(pkill_calls) > 0

    def test_destroys_volumes_when_requested(self, tmp_path: Path) -> None:
        """Should run podman volume prune when destroy_volumes=True."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_stop

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            destroy_volumes=True,
            env={"POSTGRES_PORT": "5432", "REDIS_PORT": "6379"},
        )

        with (
            patch("setup_lib.deploy_phases.compose_run"),
            patch("subprocess.run") as mock_run,
            patch("setup_lib.deploy_phases._run_sudo"),
            patch("setup_lib.deploy_phases.check_port_available", return_value=True),
            patch("time.sleep"),
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            phase_stop(config)

            run_calls = mock_run.call_args_list
            prune_calls = [c for c in run_calls if "prune" in str(c)]
            assert len(prune_calls) > 0

    def test_skips_volumes_when_not_requested(self, tmp_path: Path) -> None:
        """Should NOT run podman volume prune when destroy_volumes=False."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_stop

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            destroy_volumes=False,
            env={"POSTGRES_PORT": "5432", "REDIS_PORT": "6379"},
        )

        with (
            patch("setup_lib.deploy_phases.compose_run"),
            patch("subprocess.run") as mock_run,
            patch("setup_lib.deploy_phases._run_sudo"),
            patch("setup_lib.deploy_phases.check_port_available", return_value=True),
            patch("time.sleep"),
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            phase_stop(config)

            run_calls = mock_run.call_args_list
            prune_calls = [c for c in run_calls if "prune" in str(c)]
            assert len(prune_calls) == 0

    def test_fails_when_ports_still_in_use(self, tmp_path: Path) -> None:
        """Should return failure when ports are still in use after cleanup."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_stop

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={"POSTGRES_PORT": "5432", "REDIS_PORT": "6379"},
        )

        with (
            patch("setup_lib.deploy_phases.compose_run"),
            patch("subprocess.run") as mock_run,
            patch("setup_lib.deploy_phases._run_sudo"),
            patch("setup_lib.deploy_phases.check_port_available", return_value=False),
            patch("time.sleep"),
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            result = phase_stop(config)

            assert result.success is False
            assert "ports" in result.message.lower()


class TestPhaseBuild:
    """Tests for phase_build() function."""

    def test_skips_when_skip_build(self, tmp_path: Path) -> None:
        """Should return immediate success when skip_build=True."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_build

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            skip_build=True,
        )

        result = phase_build(config)

        assert result.success is True
        assert "skip" in result.message.lower()

    def test_builds_base_then_app_then_llm(self, tmp_path: Path) -> None:
        """Should build base image, then app services, then ai-llm in order."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_build

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={"CUDA_ARCHITECTURES": "86"},
        )

        call_order = []

        def mock_subprocess_run(cmd, **kwargs):
            # Only track the base image build; ignore socket/systemctl calls
            if "base.Dockerfile" in str(cmd):
                call_order.append("base")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="built\n", stderr="")

        def mock_compose_run(cfg, *args, **kwargs):
            if "backend" in args:
                call_order.append("app")
            elif "ai-llm" in args:
                call_order.append("llm")
            return True

        with (
            patch("subprocess.run", side_effect=mock_subprocess_run),
            patch("setup_lib.deploy_phases.compose_run", side_effect=mock_compose_run),
        ):
            result = phase_build(config)

            assert result.success is True
            assert call_order == ["base", "app", "llm"]

    def test_app_services_use_no_cache(self, tmp_path: Path) -> None:
        """Should use --no-cache for backend/frontend/ai-gateway builds."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_build

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={},
        )

        with (
            patch("subprocess.run") as mock_run,
            patch("setup_lib.deploy_phases.compose_run") as mock_compose,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="built\n", stderr=""
            )
            mock_compose.return_value = True

            phase_build(config)

            # Find the call that builds backend/frontend/ai-gateway
            app_calls = [c for c in mock_compose.call_args_list if "backend" in str(c)]
            assert len(app_calls) == 1
            assert "--no-cache" in str(app_calls[0])

    def test_ai_llm_uses_cache(self, tmp_path: Path) -> None:
        """Should NOT use --no-cache for ai-llm build."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_build

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={},
        )

        with (
            patch("subprocess.run") as mock_run,
            patch("setup_lib.deploy_phases.compose_run") as mock_compose,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="built\n", stderr=""
            )
            mock_compose.return_value = True

            phase_build(config)

            # Find the call that builds ai-llm
            llm_calls = [
                c
                for c in mock_compose.call_args_list
                if "ai-llm" in str(c) and "backend" not in str(c)
            ]
            assert len(llm_calls) == 1
            assert "--no-cache" not in str(llm_calls[0])

    def test_fails_on_base_build_error(self, tmp_path: Path) -> None:
        """Should return failure when base image build fails."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_build

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={},
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="build error"
            )

            result = phase_build(config)

            assert result.success is False
            assert "base" in result.message.lower()


class TestPhaseExport:
    """Tests for phase_export() function."""

    def test_skips_when_all_models_cached(self, tmp_path: Path) -> None:
        """Should skip export when all models have cached files."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import CORE_MODELS, phase_export

        triton_cache = tmp_path / "triton"
        for model in CORE_MODELS:
            model_dir = triton_cache / model / "1"
            model_dir.mkdir(parents=True)
            (model_dir / "model.onnx").write_text("fake")

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={"AI_MODELS_PATH": str(tmp_path)},
        )

        result = phase_export(config)

        assert result.success is True
        assert "cached" in result.message.lower()

    def test_starts_background_export(self, tmp_path: Path) -> None:
        """Should start export in background when models are missing."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_export

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={"AI_MODELS_PATH": str(tmp_path), "GPU_AI_SERVICES": "1"},
        )

        mock_proc = MagicMock()
        mock_proc.pid = 12345

        with (
            patch(
                "setup_lib.deploy_phases._get_compose_image", return_value="test-ai-gateway:latest"
            ),
            patch("subprocess.Popen", return_value=mock_proc) as mock_popen,
        ):
            result = phase_export(config)

            assert result.success is True
            assert config._export_process is mock_proc
            assert "background" in result.message.lower()
            mock_popen.assert_called_once()

    def test_fails_when_ai_gateway_image_not_found(self, tmp_path: Path) -> None:
        """Should fail when ai-gateway image cannot be resolved."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_export

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={"AI_MODELS_PATH": str(tmp_path)},
        )

        with patch("setup_lib.deploy_phases._get_compose_image", return_value=None):
            result = phase_export(config)

        assert result.success is False
        assert "ai-gateway" in result.message.lower()
        assert "image" in result.message.lower()


class TestPhaseInfrastructure:
    """Tests for phase_infrastructure() function."""

    def test_starts_postgres_redis_go2rtc(self, tmp_path: Path) -> None:
        """Should start core infrastructure services."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_infrastructure

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
        )

        with (
            patch("setup_lib.deploy_phases.compose_run") as mock_compose,
            patch("setup_lib.deploy_phases._is_service_installed", return_value=False),
            patch("time.sleep"),
        ):
            mock_compose.return_value = True

            result = phase_infrastructure(config)

            assert result.success is True
            # Check that first compose_run call includes postgres, redis, go2rtc
            first_call = mock_compose.call_args_list[0]
            call_str = str(first_call)
            assert "postgres" in call_str
            assert "redis" in call_str
            assert "go2rtc" in call_str

    def test_restarts_dcgm_if_installed(self, tmp_path: Path) -> None:
        """Should restart dcgm-exporter when installed."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import DCGM_SERVICE_NAME, phase_infrastructure

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
        )

        with (
            patch("setup_lib.deploy_phases.compose_run", return_value=True),
            patch("setup_lib.deploy_phases._is_service_installed") as mock_installed,
            patch("setup_lib.deploy_phases._run_sudo") as mock_sudo,
            patch("time.sleep"),
        ):
            mock_installed.side_effect = lambda name: name == DCGM_SERVICE_NAME
            mock_sudo.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            phase_infrastructure(config)

            # Verify restart was called for dcgm
            sudo_calls = [str(c) for c in mock_sudo.call_args_list]
            assert any("restart" in c and DCGM_SERVICE_NAME in c for c in sudo_calls)

    def test_skips_dcgm_if_not_installed(self, tmp_path: Path) -> None:
        """Should skip dcgm-exporter restart when not installed."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_infrastructure

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
        )

        with (
            patch("setup_lib.deploy_phases.compose_run", return_value=True),
            patch("setup_lib.deploy_phases._is_service_installed", return_value=False),
            patch("setup_lib.deploy_phases._run_sudo") as mock_sudo,
            patch("time.sleep"),
        ):
            phase_infrastructure(config)

            # _run_sudo should not be called for restart
            sudo_calls = [str(c) for c in mock_sudo.call_args_list]
            assert not any("restart" in c for c in sudo_calls)

    def test_waits_for_export_process(self, tmp_path: Path) -> None:
        """Should wait for background export process to complete."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_infrastructure

        mock_proc = MagicMock()
        mock_proc.returncode = 0

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
        )
        config._export_process = mock_proc

        with (
            patch("setup_lib.deploy_phases.compose_run", return_value=True),
            patch("setup_lib.deploy_phases._is_service_installed", return_value=False),
            patch("time.sleep"),
        ):
            phase_infrastructure(config)

            mock_proc.wait.assert_called_once()

    def test_fails_on_core_infra_error(self, tmp_path: Path) -> None:
        """Should return failure when core infrastructure fails to start."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_infrastructure

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
        )

        with patch("setup_lib.deploy_phases.compose_run", return_value=False):
            result = phase_infrastructure(config)

            assert result.success is False


class TestPhaseApplication:
    """Tests for phase_application() function."""

    def test_starts_all_services(self, tmp_path: Path) -> None:
        """Should run compose up for all services."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_application

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
        )

        with patch("setup_lib.deploy_phases.compose_run") as mock_compose:
            mock_compose.return_value = True

            result = phase_application(config)

            assert result.success is True
            mock_compose.assert_called_once()
            call_str = str(mock_compose.call_args)
            assert "up" in call_str
            assert "--no-build" in call_str

    def test_degraded_on_compose_error(self, tmp_path: Path) -> None:
        """Should return success (degraded) when compose up fails but retries proceed."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_application

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
        )

        with (
            patch("setup_lib.deploy_phases.compose_run", return_value=False),
            patch("setup_lib.deploy_phases._check_gpu_available", return_value=True),
            patch("setup_lib.deploy_phases._wait_container_running", return_value=False),
            patch("builtins.print"),
        ):
            result = phase_application(config)

            # phase_application always returns success (degraded is OK)
            assert result.success is True
            assert "may still be initializing" in result.message


class TestPhaseHealthCheck:
    """Tests for phase_health_check() function."""

    def test_registers_admin_on_first_deploy(self, tmp_path: Path) -> None:
        """Should register admin user when setup_required=True."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_health_check

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={"API_PORT": "8000", "AI_GATEWAY_PORT": "8090", "LLM_PORT": "8091"},
        )

        setup_response = MagicMock()
        setup_response.read.return_value = json.dumps({"setup_required": True}).encode()
        setup_response.status = 200

        register_response = MagicMock()
        register_response.read.return_value = b'{"id": 1}'
        register_response.status = 200

        call_count = 0

        def mock_urlopen(req_or_url, **kwargs):
            nonlocal call_count
            call_count += 1
            if isinstance(req_or_url, str) and "setup-status" in req_or_url:
                return setup_response
            if hasattr(req_or_url, "method") and req_or_url.method == "POST":
                return register_response
            # Health check polls
            raise Exception("not ready")

        with (
            patch("setup_lib.deploy_phases.urllib.request.urlopen", side_effect=mock_urlopen),
            patch("setup_lib.deploy_phases.poll_endpoint", return_value=False),
            patch("setup_lib.deploy_phases.generate_password", return_value="test-password-123"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            phase_health_check(config)

            # Verify admin registration POST was attempted
            assert call_count >= 2  # setup-status + register

    def test_skips_admin_when_not_required(self, tmp_path: Path) -> None:
        """Should not register admin when setup_required=False."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_health_check

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={"API_PORT": "8000", "AI_GATEWAY_PORT": "8090", "LLM_PORT": "8091"},
        )

        setup_response = MagicMock()
        setup_response.read.return_value = json.dumps({"setup_required": False}).encode()
        setup_response.status = 200

        post_called = False

        def mock_urlopen(req_or_url, **kwargs):
            nonlocal post_called
            if isinstance(req_or_url, str) and "setup-status" in req_or_url:
                return setup_response
            if hasattr(req_or_url, "method") and req_or_url.method == "POST":
                post_called = True
                return MagicMock()
            raise Exception("not ready")

        with (
            patch("setup_lib.deploy_phases.urllib.request.urlopen", side_effect=mock_urlopen),
            patch("setup_lib.deploy_phases.poll_endpoint", return_value=False),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            phase_health_check(config)

            assert post_called is False

    def test_saves_password_to_secrets(self, tmp_path: Path) -> None:
        """Should save admin password to secrets dir with 0o600 permissions."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import _auto_register_admin

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={"API_PORT": "8000"},
        )

        setup_response = MagicMock()
        setup_response.read.return_value = json.dumps({"setup_required": True}).encode()

        register_response = MagicMock()
        register_response.read.return_value = b'{"id": 1}'

        def mock_urlopen(req_or_url, **kwargs):
            if isinstance(req_or_url, str) and "setup-status" in req_or_url:
                return setup_response
            return register_response

        with (
            patch("setup_lib.deploy_phases.urllib.request.urlopen", side_effect=mock_urlopen),
            patch("setup_lib.deploy_phases.generate_password", return_value="secure-pw-123"),
        ):
            _auto_register_admin(config)

            pw_file = tmp_path / "secrets" / "admin-password.txt"
            assert pw_file.exists()
            assert pw_file.read_text() == "secure-pw-123"
            # Check permissions (0o600)
            assert oct(pw_file.stat().st_mode)[-3:] == "600"

    def test_returns_healthy_when_all_services_up(self, tmp_path: Path) -> None:
        """Should return success when all health checks pass."""
        import urllib.error

        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_health_check

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={"API_PORT": "8000", "AI_GATEWAY_PORT": "8090", "LLM_PORT": "8091"},
        )

        with (
            patch(
                "setup_lib.deploy_phases.urllib.request.urlopen",
                side_effect=urllib.error.URLError("skip"),
            ),
            patch("setup_lib.deploy_phases.poll_endpoint", return_value=True),
            patch(
                "setup_lib.deploy_phases.check_service_health",
                return_value={
                    "status": "healthy",
                    "response_time_ms": 42,
                },
            ),
            patch("setup_lib.deploy_phases.compose_run"),
            patch("setup_lib.deploy_phases.subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            result = phase_health_check(config)

            assert result.success is True
            assert "healthy" in result.message

    def test_returns_degraded_when_services_down(self, tmp_path: Path) -> None:
        """Should return degraded when some health checks fail."""
        import urllib.error

        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_health_check

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={"API_PORT": "8000", "AI_GATEWAY_PORT": "8090", "LLM_PORT": "8091"},
        )

        with (
            patch(
                "setup_lib.deploy_phases.urllib.request.urlopen",
                side_effect=urllib.error.URLError("skip"),
            ),
            patch("setup_lib.deploy_phases.poll_endpoint", return_value=False),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            result = phase_health_check(config)

            assert result.success is False
            assert "degraded" in result.message


class TestDeployPhasesRegistry:
    """Tests for the DEPLOY_PHASES registry."""

    def test_all_phases_registered(self) -> None:
        """Should have all expected phases registered."""
        from setup_lib.deploy_phases import DEPLOY_PHASES

        phase_names = [p.name for p in DEPLOY_PHASES]
        assert "stop" in phase_names
        assert "build" in phase_names
        assert "export" in phase_names
        assert "infrastructure" in phase_names
        assert "application" in phase_names
        assert "health_check" in phase_names

    def test_health_check_is_optional(self) -> None:
        """Should mark health_check as optional."""
        from setup_lib.deploy_phases import DEPLOY_PHASES

        health_phase = next(p for p in DEPLOY_PHASES if p.name == "health_check")
        assert health_phase.required is False

    def test_other_phases_are_required(self) -> None:
        """Should mark all non-health-check phases as required.

        prune_images is intentionally optional — it is a best-effort disk
        cleanup step that must not block a deployment if it fails.
        """
        from setup_lib.deploy_phases import DEPLOY_PHASES

        optional_phases = {"health_check", "prune_images"}
        for phase in DEPLOY_PHASES:
            if phase.name not in optional_phases:
                assert phase.required is True, f"Phase {phase.name} should be required"
