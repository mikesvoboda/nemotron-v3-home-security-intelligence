"""Unit tests for setup_lib.deploy module.

Tests deployment configuration, compose command detection, compose runner,
env file parsing, and deployment orchestration.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest


class TestDeployConfig:
    """Tests for DeployConfig dataclass."""

    def test_default_values(self, tmp_path: Path) -> None:
        """Should have sensible defaults for all optional fields."""
        from setup_lib.deploy import DeployConfig

        config = DeployConfig(project_root=tmp_path)

        assert config.compose_file == "docker-compose.prod.yml"
        assert config.compose_cmd == []
        assert config.destroy_volumes is False
        assert config.skip_build is False
        assert config.skip_export is False
        assert config.force_export is False
        assert config.verbose is False
        assert config.env == {}
        assert config._export_process is None

    def test_env_loading(self, tmp_path: Path) -> None:
        """Should accept env dict and make it accessible."""
        from setup_lib.deploy import DeployConfig

        env = {"API_PORT": "8000", "REDIS_PORT": "6379"}
        config = DeployConfig(project_root=tmp_path, env=env)

        assert config.env == env
        assert config.env["API_PORT"] == "8000"

    def test_custom_compose_file(self, tmp_path: Path) -> None:
        """Should accept a custom compose file name."""
        from setup_lib.deploy import DeployConfig

        config = DeployConfig(project_root=tmp_path, compose_file="docker-compose.test.yml")

        assert config.compose_file == "docker-compose.test.yml"


class TestDeployResult:
    """Tests for DeployResult dataclass."""

    def test_success_result(self) -> None:
        """Should store success state and message."""
        from setup_lib.deploy import DeployResult

        result = DeployResult(success=True, message="All good")

        assert result.success is True
        assert result.message == "All good"

    def test_failure_result(self) -> None:
        """Should store failure state and message."""
        from setup_lib.deploy import DeployResult

        result = DeployResult(success=False, message="Something broke")

        assert result.success is False
        assert result.message == "Something broke"


class TestDeployPhase:
    """Tests for DeployPhase dataclass."""

    def test_required_default(self) -> None:
        """Should default to required=True."""
        from setup_lib.deploy import DeployPhase, DeployResult

        phase = DeployPhase(
            name="test",
            description="Test phase",
            func=lambda _: DeployResult(True, "ok"),
        )

        assert phase.required is True

    def test_optional_phase(self) -> None:
        """Should accept required=False."""
        from setup_lib.deploy import DeployPhase, DeployResult

        phase = DeployPhase(
            name="test",
            description="Test phase",
            func=lambda _: DeployResult(True, "ok"),
            required=False,
        )

        assert phase.required is False


class TestDetectComposeCommand:
    """Tests for detect_compose_command() function."""

    def test_detects_podman_compose_native(self) -> None:
        """Should return ['podman', 'compose'] when native compose works."""
        from setup_lib.deploy import detect_compose_command

        with (
            patch(
                "shutil.which",
                side_effect=lambda cmd: "/usr/bin/podman" if cmd == "podman" else None,
            ),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="podman compose version 1.0", stderr=""
            )

            result = detect_compose_command()

            assert result == ["podman", "compose"]

    def test_detects_podman_compose_external(self) -> None:
        """Should return ['podman-compose'] when native fails but external works."""
        from setup_lib.deploy import detect_compose_command

        def which_side_effect(cmd):
            if cmd == "podman":
                return "/usr/bin/podman"
            if cmd == "podman-compose":
                return "/usr/bin/podman-compose"
            return None

        with (
            patch("shutil.which", side_effect=which_side_effect),
            patch("subprocess.run") as mock_run,
        ):
            # First call (podman compose version) fails, second (podman-compose --version) succeeds
            mock_run.side_effect = [
                subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="error"),
                subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="podman-compose 1.0", stderr=""
                ),
            ]

            result = detect_compose_command()

            assert result == ["/usr/bin/podman-compose"]

    def test_raises_when_none_found(self) -> None:
        """Should raise RuntimeError when no compose command is available."""
        from setup_lib.deploy import detect_compose_command

        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="No compose command found"):
                detect_compose_command()


class TestComposeRun:
    """Tests for compose_run() function."""

    def test_capture_mode(self, tmp_path: Path) -> None:
        """Should return CompletedProcess when capture=True."""
        from setup_lib.deploy import DeployConfig, compose_run

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="output", stderr=""
            )

            result = compose_run(config, "ps", capture=True)

            assert isinstance(result, subprocess.CompletedProcess)
            assert result.returncode == 0
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["capture_output"] is True

    def test_passthrough_mode(self, tmp_path: Path) -> None:
        """Should return bool when capture=False (default)."""
        from setup_lib.deploy import DeployConfig, compose_run

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            result = compose_run(config, "up", "-d")

            assert result is True

    def test_returns_false_on_failure(self, tmp_path: Path) -> None:
        """Should return False when command fails in passthrough mode."""
        from setup_lib.deploy import DeployConfig, compose_run

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="error"
            )

            result = compose_run(config, "up", "-d")

            assert result is False

    def test_verbose_prints_command(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Should print command when verbose=True."""
        from setup_lib.deploy import DeployConfig, compose_run

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            verbose=True,
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            compose_run(config, "ps")

            captured = capsys.readouterr()
            assert "podman compose" in captured.out

    def test_returns_false_on_file_not_found(self, tmp_path: Path) -> None:
        """Should return False when command binary not found."""
        from setup_lib.deploy import DeployConfig, compose_run

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["nonexistent"],
        )

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = compose_run(config, "ps")

            assert result is False

    def test_capture_returns_error_on_file_not_found(self, tmp_path: Path) -> None:
        """Should return CompletedProcess with returncode=1 on FileNotFoundError in capture mode."""
        from setup_lib.deploy import DeployConfig, compose_run

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["nonexistent"],
        )

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = compose_run(config, "ps", capture=True)

            assert isinstance(result, subprocess.CompletedProcess)
            assert result.returncode == 1

    def test_env_merged_into_command(self, tmp_path: Path) -> None:
        """Should merge config.env into subprocess environment."""
        from setup_lib.deploy import DeployConfig, compose_run

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={"CUSTOM_VAR": "value"},
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            compose_run(config, "ps")

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["env"]["CUSTOM_VAR"] == "value"


class TestLoadEnv:
    """Tests for load_env() function."""

    def test_parses_key_value(self, tmp_path: Path) -> None:
        """Should parse KEY=VALUE lines from .env file."""
        from setup_lib.deploy import load_env

        env_file = tmp_path / ".env"
        env_file.write_text("API_PORT=8000\nREDIS_PORT=6379\n")

        result = load_env(tmp_path)

        assert result == {"API_PORT": "8000", "REDIS_PORT": "6379"}

    def test_skips_comments_and_blanks(self, tmp_path: Path) -> None:
        """Should skip comment lines and empty lines."""
        from setup_lib.deploy import load_env

        env_file = tmp_path / ".env"
        env_file.write_text("# This is a comment\n\nAPI_PORT=8000\n\n# Another comment\n")

        result = load_env(tmp_path)

        assert result == {"API_PORT": "8000"}

    def test_handles_quoted_values(self, tmp_path: Path) -> None:
        """Should strip surrounding quotes from values."""
        from setup_lib.deploy import load_env

        env_file = tmp_path / ".env"
        env_file.write_text("DB_NAME=\"mydb\"\nDB_USER='admin'\n")

        result = load_env(tmp_path)

        assert result["DB_NAME"] == "mydb"
        assert result["DB_USER"] == "admin"

    def test_returns_empty_on_missing_file(self, tmp_path: Path) -> None:
        """Should return empty dict when .env file doesn't exist."""
        from setup_lib.deploy import load_env

        result = load_env(tmp_path)

        assert result == {}

    def test_skips_lines_without_equals(self, tmp_path: Path) -> None:
        """Should skip lines without = separator."""
        from setup_lib.deploy import load_env

        env_file = tmp_path / ".env"
        env_file.write_text("VALID=yes\nINVALID_LINE\n")

        result = load_env(tmp_path)

        assert result == {"VALID": "yes"}

    def test_handles_value_with_equals(self, tmp_path: Path) -> None:
        """Should handle values that contain = signs."""
        from setup_lib.deploy import load_env

        env_file = tmp_path / ".env"
        env_file.write_text(
            "DATABASE_URL=postgres://user:pass@host/db?opt=val\n"  # pragma: allowlist secret
        )

        result = load_env(tmp_path)

        assert (
            result["DATABASE_URL"]
            == "postgres://user:pass@host/db?opt=val"  # pragma: allowlist secret
        )


class TestRunDeploy:
    """Tests for run_deploy() function."""

    def test_all_phases_pass(self, tmp_path: Path) -> None:
        """Should return True when all phases succeed."""
        from setup_lib.deploy import DeployConfig, DeployPhase, DeployResult, run_deploy

        config = DeployConfig(project_root=tmp_path)

        mock_phases = [
            DeployPhase(name="one", description="Phase 1", func=lambda _: DeployResult(True, "ok")),
            DeployPhase(name="two", description="Phase 2", func=lambda _: DeployResult(True, "ok")),
        ]

        with patch("setup_lib.deploy_phases.DEPLOY_PHASES", mock_phases):
            result = run_deploy(config)

            assert result is True

    def test_required_phase_fails(self, tmp_path: Path) -> None:
        """Should return False and stop when a required phase fails."""
        from setup_lib.deploy import DeployConfig, DeployPhase, DeployResult, run_deploy

        calls = []

        def phase_ok(c):
            calls.append("ok")
            return DeployResult(True, "ok")

        def phase_fail(c):
            calls.append("fail")
            return DeployResult(False, "broken")

        def phase_after(c):
            calls.append("after")
            return DeployResult(True, "ok")

        config = DeployConfig(project_root=tmp_path)

        mock_phases = [
            DeployPhase(name="one", description="Phase 1", func=phase_ok, required=True),
            DeployPhase(name="two", description="Phase 2", func=phase_fail, required=True),
            DeployPhase(name="three", description="Phase 3", func=phase_after, required=True),
        ]

        with patch("setup_lib.deploy_phases.DEPLOY_PHASES", mock_phases):
            result = run_deploy(config)

            assert result is False
            assert calls == ["ok", "fail"]

    def test_optional_phase_fails_continues(self, tmp_path: Path) -> None:
        """Should continue when an optional phase fails."""
        from setup_lib.deploy import DeployConfig, DeployPhase, DeployResult, run_deploy

        calls = []

        def phase_ok(c):
            calls.append("ok")
            return DeployResult(True, "ok")

        def phase_fail_optional(c):
            calls.append("fail_optional")
            return DeployResult(False, "skipped")

        config = DeployConfig(project_root=tmp_path)

        mock_phases = [
            DeployPhase(name="one", description="Phase 1", func=phase_ok, required=True),
            DeployPhase(
                name="two", description="Phase 2", func=phase_fail_optional, required=False
            ),
            DeployPhase(name="three", description="Phase 3", func=phase_ok, required=True),
        ]

        with patch("setup_lib.deploy_phases.DEPLOY_PHASES", mock_phases):
            result = run_deploy(config)

            assert result is True
            assert calls == ["ok", "fail_optional", "ok"]
