"""Unit tests for setup_lib.deploy_phases module.

Tests deployment phase implementations: stop, build, export,
infrastructure, application, and health check phases.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _no_shell_pipeline_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deploy reads PIPELINE_MODE from the shell too; keep these tests hermetic."""
    monkeypatch.delenv("PIPELINE_MODE", raising=False)


def _compose_args(mock_compose: MagicMock) -> list[tuple[str, ...]]:
    """The compose argv of every compose_run call (config argument dropped)."""
    return [tuple(c.args[1:]) for c in mock_compose.call_args_list]


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
            patch("setup_lib.deploy_phases.compose_run", autospec=True) as mock_compose,
            patch("subprocess.run", autospec=True) as mock_run,
            patch("setup_lib.deploy_phases._run_sudo", autospec=True),
            patch("setup_lib.deploy_phases.check_port_available", return_value=True, autospec=True),
            patch("time.sleep", autospec=True),
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
            patch("setup_lib.deploy_phases.compose_run", autospec=True),
            patch("subprocess.run", autospec=True) as mock_run,
            patch("setup_lib.deploy_phases._run_sudo", autospec=True),
            patch("setup_lib.deploy_phases.check_port_available", return_value=True, autospec=True),
            patch("time.sleep", autospec=True),
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
            patch("setup_lib.deploy_phases.compose_run", autospec=True),
            patch("subprocess.run", autospec=True) as mock_run,
            patch("setup_lib.deploy_phases._run_sudo", autospec=True),
            patch("setup_lib.deploy_phases.check_port_available", return_value=True, autospec=True),
            patch("time.sleep", autospec=True),
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
            patch("setup_lib.deploy_phases.compose_run", autospec=True),
            patch("subprocess.run", autospec=True) as mock_run,
            patch("setup_lib.deploy_phases._run_sudo", autospec=True),
            patch("setup_lib.deploy_phases.check_port_available", return_value=True, autospec=True),
            patch("time.sleep", autospec=True),
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
            patch("setup_lib.deploy_phases.compose_run", autospec=True),
            patch("subprocess.run", autospec=True) as mock_run,
            patch("setup_lib.deploy_phases._run_sudo", autospec=True),
            patch(
                "setup_lib.deploy_phases.check_port_available", return_value=False, autospec=True
            ),
            patch("time.sleep", autospec=True),
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            result = phase_stop(config)

            assert result.success is False
            assert "ports" in result.message.lower()

    def test_down_and_rm_are_plain_calls(self, tmp_path: Path) -> None:
        """Stop tears the stack down with plain `down`/`rm` and no profile.

        Deploy used to walk a profile off every _MODE_PLANS entry, because
        compose down/rm skip services whose profile is inactive and a leftover
        GPU model server must not keep holding the GPU. O1.3 (UR-18) moved
        ai-vlm into the default set, so there is no profile to activate: a plain
        `down` reaches it.

        The leftover-ai-llm worry that made the walk load-bearing stays
        handled: R8 S2b deleted that service from the compose file, and
        backend/services/container_orchestrator.py's RETIRED_LLM_SERVICES
        refuses to manage a leftover container of it.
        """
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_stop

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={"POSTGRES_PORT": "5432", "REDIS_PORT": "6379"},
        )

        with (
            patch("setup_lib.deploy_phases.compose_run", autospec=True) as mock_compose,
            patch("setup_lib.deploy_phases._ensure_rootless_storage", autospec=True),
            patch("subprocess.run", autospec=True) as mock_run,
            patch("setup_lib.deploy_phases._run_sudo", autospec=True),
            patch("setup_lib.deploy_phases.check_port_available", return_value=True, autospec=True),
            patch("time.sleep", autospec=True),
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            phase_stop(config)

        calls = _compose_args(mock_compose)
        assert calls == [("down",), ("rm", "-f")], (
            "deploy's teardown changed shape; it must reach the whole stack with "
            "no profile to activate"
        )
        assert not any("--profile" in args for args in calls), (
            "deploy still passes a compose profile; ai-vlm ships in the default set"
        )


class TestPhaseBuild:
    """Tests for phase_build() function."""

    def test_skips_when_skip_build(self, tmp_path: Path) -> None:
        """--skip-build returns immediately: no base build, no compose build.

        The socket probe IS still run -- deliberately, before this return: the
        docker-compose plugin needs podman.socket for the later infrastructure /
        application phases too, so skipping the build must not skip it. It is
        stubbed here because the probe shells out to `systemctl --user` on a host
        this test does not own (the rest of this class patches subprocess for the
        same reason); the pin is that it happens and that nothing builds.
        """
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_build

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            skip_build=True,
        )

        with (
            patch("setup_lib.deploy_phases._ensure_podman_socket", autospec=True) as socket_probe,
            patch("setup_lib.deploy_phases.compose_run", autospec=True) as mock_compose,
        ):
            result = phase_build(config)

        assert result.success is True
        assert "skip" in result.message.lower()
        socket_probe.assert_called_once_with(config)
        mock_compose.assert_not_called()

    def test_builds_base_then_app_then_model_server(self, tmp_path: Path) -> None:
        """Build order: base image, then app services, then the mode's model server.

        The order is the whole point -- backend's image FROM's the base, and the
        model server is the cached build last because nothing depends on it.

        R8 S2b: this was parametrized [vlm-default]/[legacy], where legacy walked
        the same order onto ai-llm. The legacy plan is deleted with the ai-llm
        services it named, so there is ONE plan and the ordering pin applies to it
        alone; a second mode adds a row back, it does not re-derive the order.
        """
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
            elif "ai-vlm" in args:
                call_order.append("vlm")
            elif "ai-llm" in args:
                call_order.append("retired-llm")
            return True

        with (
            patch("subprocess.run", side_effect=mock_subprocess_run, autospec=True),
            patch(
                "setup_lib.deploy_phases.compose_run", side_effect=mock_compose_run, autospec=True
            ),
        ):
            result = phase_build(config)

            assert result.success is True
            assert call_order == ["base", "app", "vlm"]

    def test_vlm_mode_builds_ai_vlm_and_never_ai_llm(self, tmp_path: Path) -> None:
        """vlm (the default): ai-vlm is built by name in a plain call, cached, for
        the GPU's arch.

        O1.3 (UR-18): ai-vlm is in the default compose set, so the call needs no
        --profile. The argv is pinned because a stale flag would keep working
        (compose ignores a profile no service declares) — the assertion is the
        only thing that notices.
        """
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_build

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={"CUDA_ARCHITECTURES": "86"},
        )

        with (
            patch("subprocess.run", autospec=True) as mock_run,
            patch("setup_lib.deploy_phases.compose_run", autospec=True) as mock_compose,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="built\n", stderr=""
            )
            mock_compose.return_value = True

            result = phase_build(config)

        assert result.success is True
        calls = _compose_args(mock_compose)
        assert not any("ai-llm" in args for args in calls), "vlm mode must never build ai-llm"
        vlm_calls = [args for args in calls if "ai-vlm" in args]
        assert vlm_calls == [("build", "--build-arg", "CUDA_ARCHITECTURES=86", "ai-vlm")]

    def test_vlm_mode_builds_ai_vlm_for_detected_arch(self, tmp_path: Path) -> None:
        """No CUDA_ARCHITECTURES in .env: ai-vlm gets the nvidia-smi-detected one."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_build

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={},
        )

        def mock_subprocess_run(cmd, **kwargs):
            stdout = "8.6\n" if "nvidia-smi" in cmd else "built\n"
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=stdout, stderr="")

        with (
            patch("subprocess.run", side_effect=mock_subprocess_run, autospec=True),
            patch("setup_lib.deploy_phases.compose_run", autospec=True) as mock_compose,
        ):
            mock_compose.return_value = True

            phase_build(config)

        vlm_calls = [args for args in _compose_args(mock_compose) if "ai-vlm" in args]
        assert len(vlm_calls) == 1
        assert "CUDA_ARCHITECTURES=86" in vlm_calls[0]

    # test_legacy_mode_builds_ai_llm_behind_its_profile is gone: its subject was
    # phase_build's legacy plan (--profile legacy build ai-llm, 58163f23f), and R8 S2b
    # deleted that plan with the ai-llm build context. The vlm-side twin of its exact
    # shape -- the model server build's full argv under its profile -- is
    # test_vlm_mode_builds_ai_vlm_and_never_ai_llm below, which also keeps the
    # "never builds the other model server" half as a negative.

    def test_fails_when_model_server_build_fails(self, tmp_path: Path) -> None:
        """A failed ai-vlm build fails the phase and names the service."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_build

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={"CUDA_ARCHITECTURES": "86"},
        )

        with (
            patch("subprocess.run", autospec=True) as mock_run,
            patch(
                "setup_lib.deploy_phases.compose_run",
                side_effect=lambda _cfg, *args, **_kw: "ai-vlm" not in args,
                autospec=True,
            ),
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="built\n", stderr=""
            )

            result = phase_build(config)

        assert result.success is False
        assert result.message == "ai-vlm build failed"

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
            patch("subprocess.run", autospec=True) as mock_run,
            patch("setup_lib.deploy_phases.compose_run", autospec=True) as mock_compose,
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

    def test_model_server_build_is_cached(self, tmp_path: Path) -> None:
        """The model server build is WITH cache; the app service builds are not.

        Retargeted at R8 S2b: this was test_ai_llm_uses_cache (the same property
        read off legacy's ai-llm). The property is the plan's, not the service's
        -- phase_build builds backend/frontend/ai-gateway --no-cache and the model
        server without it, because the model server is llama.cpp/llama-style at a
        pinned tag with no app code in it, so a cache-busting rebuild is pure
        minutes. ai-vlm is the model server now.
        """
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_build

        config = DeployConfig(project_root=tmp_path, compose_cmd=["podman", "compose"], env={})

        with (
            patch("subprocess.run", autospec=True) as mock_run,
            patch("setup_lib.deploy_phases.compose_run", autospec=True) as mock_compose,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="built\n", stderr=""
            )
            mock_compose.return_value = True

            phase_build(config)

            app_calls = [args for args in _compose_args(mock_compose) if "backend" in args]
            vlm_calls = [args for args in _compose_args(mock_compose) if "ai-vlm" in args]
            assert app_calls and "--no-cache" in app_calls[0]
            assert len(vlm_calls) == 1
            assert "--no-cache" not in vlm_calls[0]

    def test_fails_on_base_build_error(self, tmp_path: Path) -> None:
        """Should return failure when base image build fails."""
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_build

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={},
        )

        with patch("subprocess.run", autospec=True) as mock_run:
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
                "setup_lib.deploy_phases._get_compose_image",
                return_value="test-ai-gateway:latest",
                autospec=True,
            ),
            patch("subprocess.Popen", return_value=mock_proc, autospec=True) as mock_popen,
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

        with patch("setup_lib.deploy_phases._get_compose_image", return_value=None, autospec=True):
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
            patch("setup_lib.deploy_phases.compose_run", autospec=True) as mock_compose,
            patch(
                "setup_lib.deploy_phases._is_service_installed", return_value=False, autospec=True
            ),
            patch("time.sleep", autospec=True),
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
            patch("setup_lib.deploy_phases.compose_run", return_value=True, autospec=True),
            patch("setup_lib.deploy_phases._is_service_installed", autospec=True) as mock_installed,
            patch("setup_lib.deploy_phases._run_sudo", autospec=True) as mock_sudo,
            patch("time.sleep", autospec=True),
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
            patch("setup_lib.deploy_phases.compose_run", return_value=True, autospec=True),
            patch(
                "setup_lib.deploy_phases._is_service_installed", return_value=False, autospec=True
            ),
            patch("setup_lib.deploy_phases._run_sudo", autospec=True) as mock_sudo,
            patch("time.sleep", autospec=True),
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
            patch("setup_lib.deploy_phases.compose_run", return_value=True, autospec=True),
            patch(
                "setup_lib.deploy_phases._is_service_installed", return_value=False, autospec=True
            ),
            patch("time.sleep", autospec=True),
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

        with patch("setup_lib.deploy_phases.compose_run", return_value=False, autospec=True):
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

        with patch("setup_lib.deploy_phases.compose_run", autospec=True) as mock_compose:
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
            patch("setup_lib.deploy_phases.compose_run", return_value=False, autospec=True),
            patch("setup_lib.deploy_phases._check_gpu_available", return_value=True, autospec=True),
            patch(
                "setup_lib.deploy_phases._wait_container_running", return_value=False, autospec=True
            ),
            patch("builtins.print", autospec=True),
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
            patch(
                "setup_lib.deploy_phases.urllib.request.urlopen",
                side_effect=mock_urlopen,
                autospec=True,
            ),
            patch("setup_lib.deploy_phases.poll_endpoint", return_value=False, autospec=True),
            patch(
                "setup_lib.deploy_phases.generate_password",
                return_value="test-password-123",
                autospec=True,
            ),
            patch("subprocess.run", autospec=True) as mock_run,
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
            patch(
                "setup_lib.deploy_phases.urllib.request.urlopen",
                side_effect=mock_urlopen,
                autospec=True,
            ),
            patch("setup_lib.deploy_phases.poll_endpoint", return_value=False, autospec=True),
            patch("subprocess.run", autospec=True) as mock_run,
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
            patch(
                "setup_lib.deploy_phases.urllib.request.urlopen",
                side_effect=mock_urlopen,
                autospec=True,
            ),
            patch(
                "setup_lib.deploy_phases.generate_password",
                return_value="secure-pw-123",
                autospec=True,
            ),
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
                autospec=True,
            ),
            patch("setup_lib.deploy_phases.poll_endpoint", return_value=True, autospec=True),
            patch(
                "setup_lib.deploy_phases.check_service_health",
                return_value={
                    "status": "healthy",
                    "response_time_ms": 42,
                },
                autospec=True,
            ),
            patch("setup_lib.deploy_phases.compose_run", autospec=True),
            patch("setup_lib.deploy_phases.subprocess.run", autospec=True) as mock_run,
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
                autospec=True,
            ),
            patch("setup_lib.deploy_phases.poll_endpoint", return_value=False, autospec=True),
            patch("subprocess.run", autospec=True) as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            result = phase_health_check(config)

            assert result.success is False
            assert "degraded" in result.message

    @pytest.mark.parametrize(
        ("env", "polled", "not_polled"),
        [
            # vlm (default): ai-vlm's loopback port; AI_VLM_PORT unset -> compose's 8098
            ({"LLM_PORT": "8091"}, ("http://localhost:8098/health", 120), "8091"),
            (
                {"LLM_PORT": "8091", "AI_VLM_PORT": "18098"},
                ("http://localhost:18098/health", 120),
                "8091",
            ),
        ],
        ids=["vlm-default-port", "vlm-env-port"],
    )
    def test_polls_the_modes_model_server(
        self,
        tmp_path: Path,
        env: dict[str, str],
        polled: tuple[str, int],
        not_polled: str,
    ) -> None:
        """vlm mode polls ai-vlm (120s = its start_period), never the retired 30B.

        The third row (PIPELINE_MODE=legacy -> LLM_PORT:8091 on a 180s budget)
        is dropped at R8 S2b: the legacy plan is deleted, so that poll no longer
        exists to point at. The `not_polled` half of the assertion keeps its
        teeth -- the retired engine's port is still the thing asserted absent.
        """
        import urllib.error

        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_health_check

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={"API_PORT": "8000", "AI_GATEWAY_PORT": "8090", **env},
        )

        with (
            patch(
                "setup_lib.deploy_phases.urllib.request.urlopen",
                side_effect=urllib.error.URLError("skip"),
                autospec=True,
            ),
            patch(
                "setup_lib.deploy_phases.poll_endpoint", return_value=False, autospec=True
            ) as poll,
            patch("setup_lib.deploy_phases.subprocess.run", autospec=True) as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            phase_health_check(config)

        polls = [(c.args[0], c.kwargs["timeout"]) for c in poll.call_args_list]
        assert polled in polls
        assert not any(f":{not_polled}/" in url for url, _ in polls)


class TestRecoverCreatedContainers:
    """_recover_created_containers() restarts containers stuck in 'created'."""

    def _recover(self, tmp_path: Path, env: dict[str, str], names: list[str]) -> MagicMock:
        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import _recover_created_containers

        config = DeployConfig(project_root=tmp_path, compose_cmd=["podman", "compose"], env=env)
        stdout = "".join(f"{name}\n" for name in names)
        with (
            patch("setup_lib.deploy_phases.compose_run", return_value=True, autospec=True) as cr,
            patch("setup_lib.deploy_phases.subprocess.run", autospec=True) as mock_run,
            patch(
                "setup_lib.deploy_phases._wait_container_running", return_value=True, autospec=True
            ),
            patch("setup_lib.deploy_phases.time.sleep", autospec=True),
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=stdout, stderr=""
            )
            _recover_created_containers(config)
        return cr

    def test_restarts_created_ai_vlm_in_a_plain_call(self, tmp_path: Path) -> None:
        """A created ai-vlm is restarted by name, with no profile to pass."""
        cr = self._recover(tmp_path, {}, [f"{tmp_path.name}-ai-vlm-1"])

        assert _compose_args(cr) == [("up", "-d", "--no-build", "ai-vlm")]

    def test_never_starts_a_model_server_that_is_not_the_plans(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The guard that keeps another plan's model server down still fires.

        Retargeted at R8 S2b (was test_never_starts_ai_llm_in_vlm_mode). The
        intent -- a GPU model server this deploy did not choose is never started
        by the recovery pass -- is still worth a pin, but the shipped guard is
        `other_servers = {p.model_server for p in _MODE_PLANS.values()} -
        {plan.model_server}`, and with the legacy plan deleted that set is EMPTY
        by construction: with one plan there is no other server to skip, so the
        old test's assertion was no longer testing the guard at all.

        So the guard is exercised the way the S2b author meant it to be read: a
        second plan is installed (ai-llm, the plan R8 deleted, used here as the
        stand-in the guard exists for) and the pass must skip it while everything
        else still recovers. When a real second mode lands, this is the row that
        proves it inherits the protection.

        What actually keeps the retired ai-llm from coming back today is compose
        itself (no such service survives in docker-compose.prod.yml) plus
        backend/services/container_orchestrator.py's RETIRED_LLM_SERVICES, which
        refuses to manage a leftover container even when it is running.
        """
        from dataclasses import replace

        from setup_lib.deploy_phases import _MODE_PLANS

        monkeypatch.setitem(
            _MODE_PLANS,
            "hypothetical",
            replace(_MODE_PLANS["vlm"], model_server="ai-llm"),
        )

        cr = self._recover(
            tmp_path, {}, [f"{tmp_path.name}-ai-llm-1", f"{tmp_path.name}-backend-1"]
        )

        calls = _compose_args(cr)
        assert not any("ai-llm" in args for args in calls), "another plan's server must stay down"
        assert ("up", "-d", "--no-build", "backend") in calls

    def test_never_names_a_model_server_other_than_the_plan(self, tmp_path: Path) -> None:
        """No profile argv of any kind comes out of this pass any more.

        O1.3 (UR-18) took the plan's profile away, so every recovery call is
        plain: the pass reaches every stuck container -- including a pre-R8
        ai-llm, named like any other service -- and compose (which has no
        ai-llm service left) is what keeps the retired engine down, not this
        loop. Stable if a second plan ever lands: then ai-llm is skipped by the
        guard above and nothing here can emit a profile.
        """
        cr = self._recover(tmp_path, {}, [f"{tmp_path.name}-ai-llm-1", f"{tmp_path.name}-ai-vlm-1"])

        calls = _compose_args(cr)
        assert all("--profile" not in args for args in calls)
        assert not any("legacy" in args for args in calls)

    # test_legacy_mode_still_recovers_ai_llm is gone: its subject was the legacy plan
    # (a created ai-llm restarted through --profile legacy), and R8 S2b deleted that
    # plan -- DeployConfig.pipeline_mode now raises on "legacy", so the mode the test
    # constructed cannot be expressed. The recovery shape it exercised for a plan's own
    # model server stays pinned by test_restarts_created_ai_vlm_in_a_plain_call,
    # and "the plan I did not choose stays down" by the test above.


# ---------------------------------------------------------------------------
# SELinux camera root (A5500 box, 2026-09-28): an enforcing host + a usr_t
# camera root + a /cameras mount without :z = the backend can READ uploads but
# its inotify WATCH is denied, and the file watcher went blind. Deploy checks
# before (the shared setup_lib/selinux_check preflight) and after (the
# backend's own watch_mode on /api/system/pipeline). Warn-only: deploy never
# relabels a host path, it prints the command.
# ---------------------------------------------------------------------------

USR_T = "system_u:object_r:usr_t:s0"
BACKEND_CAMERA_COMPOSE = """\
services:
  backend:
    volumes:
      - ${{FOSCAM_BASE_PATH:-/export/foscam}}:/cameras{opts}
"""


class TestSelinuxCameraRootPreflight:
    """_preflight_selinux_camera_root(): the shared host check, run by deploy."""

    @staticmethod
    def _config(
        tmp_path: Path, env: dict[str, str] | None = None, compose: dict[str, str] | None = None
    ):
        """DeployConfig on tmp_path; ``compose`` = {file name: backend /cameras opts}."""
        from setup_lib.deploy import DeployConfig

        for name, opts in (compose or {}).items():
            (tmp_path / name).write_text(BACKEND_CAMERA_COMPOSE.format(opts=opts))
        return DeployConfig(
            project_root=tmp_path,
            compose_file="docker-compose.prod.yml",
            compose_cmd=["podman", "compose"],
            env=env or {},
        )

    def test_warns_with_the_fix_and_changes_nothing_on_the_host(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from setup_lib.deploy_phases import _preflight_selinux_camera_root

        config = self._config(
            tmp_path, {"FOSCAM_BASE_PATH": "/srv/cams"}, {"docker-compose.prod.yml": ""}
        )
        with (
            patch("setup_lib.deploy_phases._run_sudo", autospec=True) as sudo,
            patch("setup_lib.deploy_phases.subprocess.run", autospec=True) as run,
        ):
            verdict = _preflight_selinux_camera_root(
                config, selinux_enforcing=lambda: True, selinux_label=lambda _path: USR_T
            )

        out = capsys.readouterr().out
        assert verdict.verdict == "WARN"
        assert "WARNING" in out
        assert "docker-compose.prod.yml: ${FOSCAM_BASE_PATH:-/export/foscam}:/cameras" in out
        assert "sudo semanage fcontext -a -t container_file_t '/srv/cams(/.*)?'" in out
        assert "sudo restorecon -R /srv/cams" in out
        sudo.assert_not_called()
        run.assert_not_called()

    def test_reads_the_compose_file_deploy_uses(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # prod relabels; a bare ghcr file next to it is not what deploy runs.
        from setup_lib.deploy_phases import _preflight_selinux_camera_root

        config = self._config(
            tmp_path, compose={"docker-compose.prod.yml": ":z", "docker-compose.ghcr.yml": ":ro"}
        )
        verdict = _preflight_selinux_camera_root(
            config, selinux_enforcing=lambda: True, selinux_label=lambda _path: USR_T
        )

        out = capsys.readouterr().out
        assert verdict.verdict == "PASS"
        assert "WARNING" not in out
        assert "ghcr" not in out

    @pytest.mark.parametrize(
        ("env", "root"),
        [({}, "/export/foscam"), ({"FOSCAM_BASE_PATH": "/srv/cams"}, "/srv/cams")],
    )
    def test_the_label_is_read_from_foscam_base_path(
        self, tmp_path: Path, env: dict[str, str], root: str
    ) -> None:
        from setup_lib.deploy_phases import _preflight_selinux_camera_root

        asked: list[str] = []
        config = self._config(tmp_path, env, {"docker-compose.prod.yml": ""})
        _preflight_selinux_camera_root(
            config,
            selinux_enforcing=lambda: True,
            selinux_label=lambda path: asked.append(path) or USR_T,
        )
        assert asked == [root]

    def test_phase_infrastructure_runs_it_and_a_warn_never_fails_the_deploy(
        self, tmp_path: Path
    ) -> None:
        from setup_lib.deploy_phases import phase_infrastructure
        from setup_lib.selinux_check import CameraRootVerdict

        cams = tmp_path / "cams"
        cams.mkdir()
        config = self._config(tmp_path, {"FOSCAM_BASE_PATH": str(cams)})
        with (
            patch(
                "setup_lib.deploy_phases._preflight_selinux_camera_root",
                return_value=CameraRootVerdict("WARN", "would be denied"),
                autospec=True,
            ) as preflight,
            patch("setup_lib.deploy_phases.compose_run", return_value=True, autospec=True),
            patch(
                "setup_lib.deploy_phases._is_service_installed", return_value=False, autospec=True
            ),
            patch("setup_lib.deploy_phases._run_sudo", autospec=True) as sudo,
            patch("time.sleep", autospec=True),
        ):
            sudo.return_value = subprocess.CompletedProcess(args=[], returncode=0)
            result = phase_infrastructure(config)

        preflight.assert_called_once_with(config)
        assert result.success is True


class TestFileWatcherPostDeploy:
    """phase_health_check() reads the backend's own watch_mode: a refused
    inotify watch shows as polling-fallback on ANY host, whatever the compose."""

    @staticmethod
    def _health(
        tmp_path: Path, pipeline: dict | None, backend_ready: bool = True
    ) -> tuple[object, list[str]]:
        import urllib.error

        from setup_lib.deploy import DeployConfig
        from setup_lib.deploy_phases import phase_health_check

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={"API_PORT": "8000", "FOSCAM_BASE_PATH": "/srv/cams"},
        )
        probed: list[str] = []

        def fake_health(name: str, url: str, timeout: int = 60) -> dict:
            probed.append(url)
            data = pipeline if url.endswith("/api/system/pipeline") else {"status": "ok"}
            return {"name": name, "status": "healthy", "response_time_ms": 5, "data": data}

        with (
            patch(
                "setup_lib.deploy_phases.urllib.request.urlopen",
                side_effect=urllib.error.URLError("no network in unit tests"),
                autospec=True,
            ),
            patch(
                "setup_lib.deploy_phases.poll_endpoint",
                side_effect=lambda url, **_kw: backend_ready or "/api/" not in url,
                autospec=True,
            ),
            patch(
                "setup_lib.deploy_phases.check_service_health",
                side_effect=fake_health,
                autospec=True,
            ),
            patch("setup_lib.deploy_phases.subprocess.run", autospec=True) as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            result = phase_health_check(config)
        return result, probed

    @staticmethod
    def _pipeline(mode: str, reason: str | None = None) -> dict:
        return {"file_watcher": {"watch_mode": mode, "watch_fallback_reason": reason}}

    def test_polling_fallback_is_warned_with_the_reason(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        result, probed = self._health(tmp_path, self._pipeline("polling-fallback", "EACCES"))

        out = capsys.readouterr().out
        assert "http://localhost:8000/api/system/pipeline" in probed
        assert "WARNING" in out
        assert "polling-fallback" in out
        assert "EACCES" in out
        assert "sudo restorecon -R /srv/cams" in out
        # a warning, not a failed health check
        assert result.success is True

    def test_a_native_watch_prints_the_mode_and_no_warning(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._health(tmp_path, self._pipeline("native"))

        out = capsys.readouterr().out
        assert "File watcher: native" in out
        assert "WARNING" not in out

    def test_the_pipeline_is_not_probed_when_the_backend_is_not_ready(self, tmp_path: Path) -> None:
        _result, probed = self._health(tmp_path, None, backend_ready=False)

        assert not any(url.endswith("/api/system/pipeline") for url in probed)


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
