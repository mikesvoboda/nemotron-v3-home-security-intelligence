"""Unit tests for setup_lib/deploy_phases.py — pre-flight validation phase.

Tests cover:
- Missing podman CLI detection
- Missing podman socket detection
- Missing required env vars (POSTGRES_PASSWORD, REDIS_PASSWORD)
- GPU detection warnings (non-blocking)
- All checks passing returns success
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from setup_lib.deploy import DeployConfig
from setup_lib.deploy_phases import phase_validate


def _make_config(**env_overrides: str) -> DeployConfig:
    """Create a DeployConfig with sensible defaults for testing."""
    env = {
        "POSTGRES_PASSWORD": "test-pass",  # pragma: allowlist secret
        "REDIS_PASSWORD": "test-pass",  # pragma: allowlist secret
        "PODMAN_SOCKET": "/tmp/claude/test-podman.sock",  # noqa: S108
    }
    env.update(env_overrides)
    return DeployConfig(
        project_root=Path("/tmp/claude/fake-project"),  # noqa: S108
        env=env,
    )


class TestPhaseValidate:
    """Tests for phase_validate() pre-flight checks."""

    @patch("setup_lib.deploy_phases.subprocess.run")
    @patch("setup_lib.deploy_phases.Path.exists", return_value=True)
    @patch("setup_lib.deploy_phases.shutil.which", return_value="/usr/bin/podman")
    def test_all_checks_pass(
        self, mock_which: MagicMock, mock_exists: MagicMock, mock_run: MagicMock
    ) -> None:
        """All pre-flight checks pass when podman, socket, env vars, and GPU are present."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="NVIDIA RTX A5500\n", stderr=""
        )
        config = _make_config()
        result = phase_validate(config)
        assert result.success is True
        assert "passed" in result.message.lower()

    @patch("setup_lib.deploy_phases.subprocess.run")
    @patch("setup_lib.deploy_phases.Path.exists", return_value=True)
    @patch("setup_lib.deploy_phases.shutil.which", return_value=None)
    def test_missing_podman_cli_fails(
        self, mock_which: MagicMock, mock_exists: MagicMock, mock_run: MagicMock
    ) -> None:
        """Validation fails when podman CLI is not in PATH."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="GPU\n", stderr=""
        )
        config = _make_config()
        result = phase_validate(config)
        assert result.success is False
        assert "podman CLI not found" in result.message

    @patch("setup_lib.deploy_phases.subprocess.run")
    @patch("setup_lib.deploy_phases.Path.exists", return_value=False)
    @patch("setup_lib.deploy_phases.shutil.which", return_value="/usr/bin/podman")
    def test_missing_podman_socket_fails(
        self, mock_which: MagicMock, mock_exists: MagicMock, mock_run: MagicMock
    ) -> None:
        """Validation fails when podman socket does not exist."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="GPU\n", stderr=""
        )
        config = _make_config()
        result = phase_validate(config)
        assert result.success is False
        assert "Podman socket not found" in result.message

    @patch("setup_lib.deploy_phases.subprocess.run")
    @patch("setup_lib.deploy_phases.Path.exists", return_value=True)
    @patch("setup_lib.deploy_phases.shutil.which", return_value="/usr/bin/podman")
    def test_missing_postgres_password_fails(
        self, mock_which: MagicMock, mock_exists: MagicMock, mock_run: MagicMock
    ) -> None:
        """Validation fails when POSTGRES_PASSWORD is not set."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="GPU\n", stderr=""
        )
        config = _make_config(POSTGRES_PASSWORD="")
        result = phase_validate(config)
        assert result.success is False
        assert "POSTGRES_PASSWORD" in result.message

    @patch("setup_lib.deploy_phases.subprocess.run")
    @patch("setup_lib.deploy_phases.Path.exists", return_value=True)
    @patch("setup_lib.deploy_phases.shutil.which", return_value="/usr/bin/podman")
    def test_missing_redis_password_fails(
        self, mock_which: MagicMock, mock_exists: MagicMock, mock_run: MagicMock
    ) -> None:
        """Validation fails when REDIS_PASSWORD is not set."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="GPU\n", stderr=""
        )
        config = _make_config(REDIS_PASSWORD="")
        result = phase_validate(config)
        assert result.success is False
        assert "REDIS_PASSWORD" in result.message

    @patch("setup_lib.deploy_phases.subprocess.run")
    @patch("setup_lib.deploy_phases.Path.exists", return_value=True)
    @patch("setup_lib.deploy_phases.shutil.which", return_value="/usr/bin/podman")
    def test_missing_gpu_warns_but_passes(
        self, mock_which: MagicMock, mock_exists: MagicMock, mock_run: MagicMock
    ) -> None:
        """Missing GPU produces warning but validation still succeeds."""
        mock_run.side_effect = FileNotFoundError("nvidia-smi not found")
        config = _make_config()
        result = phase_validate(config)
        assert result.success is True
        assert "passed" in result.message.lower()

    @patch("setup_lib.deploy_phases.subprocess.run")
    @patch("setup_lib.deploy_phases.Path.exists", return_value=True)
    @patch("setup_lib.deploy_phases.shutil.which", return_value="/usr/bin/podman")
    def test_nvidia_smi_returns_no_gpus_warns_but_passes(
        self, mock_which: MagicMock, mock_exists: MagicMock, mock_run: MagicMock
    ) -> None:
        """nvidia-smi returning no GPUs warns but still passes."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr=""
        )
        config = _make_config()
        result = phase_validate(config)
        assert result.success is True

    @patch("setup_lib.deploy_phases.subprocess.run")
    @patch("setup_lib.deploy_phases.Path.exists", return_value=True)
    @patch("setup_lib.deploy_phases.shutil.which", return_value=None)
    def test_multiple_errors_reported(
        self, mock_which: MagicMock, mock_exists: MagicMock, mock_run: MagicMock
    ) -> None:
        """Multiple validation errors are all reported in the message."""
        mock_run.side_effect = FileNotFoundError("nvidia-smi not found")
        # Missing podman + missing socket + missing passwords
        config = _make_config(POSTGRES_PASSWORD="", REDIS_PASSWORD="")
        result = phase_validate(config)
        assert result.success is False
        # All errors should be joined in the message
        assert "podman CLI" in result.message
        assert "POSTGRES_PASSWORD" in result.message
        assert "REDIS_PASSWORD" in result.message
