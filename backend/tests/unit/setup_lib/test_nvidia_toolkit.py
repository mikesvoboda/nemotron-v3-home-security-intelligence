"""Unit tests for setup_lib.nvidia_toolkit module.

Tests NVIDIA Container Toolkit detection, installation, and runtime
configuration for Docker and Podman across various Linux distributions.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestIsToolkitInstalled:
    """Tests for is_toolkit_installed() function."""

    def test_toolkit_installed_nvidia_ctk_exists(self) -> None:
        """Should return True when nvidia-ctk is found in PATH."""
        from setup_lib.nvidia_toolkit import is_toolkit_installed

        with patch("shutil.which", return_value="/usr/bin/nvidia-ctk"):
            result = is_toolkit_installed()
            assert result is True

    def test_toolkit_not_installed(self) -> None:
        """Should return False when nvidia-ctk is not found."""
        from setup_lib.nvidia_toolkit import is_toolkit_installed

        with patch("shutil.which", return_value=None):
            result = is_toolkit_installed()
            assert result is False

    def test_checks_nvidia_ctk_binary(self) -> None:
        """Should check specifically for nvidia-ctk."""
        from setup_lib.nvidia_toolkit import is_toolkit_installed

        with patch("shutil.which") as mock_which:
            mock_which.return_value = None
            is_toolkit_installed()
            mock_which.assert_called_once_with("nvidia-ctk")


class TestGetToolkitVersion:
    """Tests for get_toolkit_version() function."""

    def test_get_version_success(self) -> None:
        """Should parse version from nvidia-ctk --version output."""
        from setup_lib.nvidia_toolkit import get_toolkit_version

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "NVIDIA Container Toolkit CLI version 1.14.3"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            version = get_toolkit_version()
            assert version == "1.14.3"

    def test_get_version_alternate_format(self) -> None:
        """Should parse version from alternate output format."""
        from setup_lib.nvidia_toolkit import get_toolkit_version

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "nvidia-ctk version 1.15.0"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            version = get_toolkit_version()
            assert version == "1.15.0"

    def test_get_version_two_part(self) -> None:
        """Should parse two-part version numbers."""
        from setup_lib.nvidia_toolkit import get_toolkit_version

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "version 1.14"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            version = get_toolkit_version()
            assert version == "1.14"

    def test_get_version_not_installed(self) -> None:
        """Should return None when nvidia-ctk is not installed."""
        from setup_lib.nvidia_toolkit import get_toolkit_version

        with patch("subprocess.run", side_effect=FileNotFoundError):
            version = get_toolkit_version()
            assert version is None

    def test_get_version_command_fails(self) -> None:
        """Should return None when command returns non-zero exit."""
        from setup_lib.nvidia_toolkit import get_toolkit_version

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            version = get_toolkit_version()
            assert version is None

    def test_get_version_timeout(self) -> None:
        """Should return None on timeout."""
        from setup_lib.nvidia_toolkit import get_toolkit_version

        with patch("subprocess.run", side_effect=TimeoutError):
            version = get_toolkit_version()
            assert version is None

    def test_get_version_permission_error(self) -> None:
        """Should return None on permission error."""
        from setup_lib.nvidia_toolkit import get_toolkit_version

        with patch("subprocess.run", side_effect=PermissionError):
            version = get_toolkit_version()
            assert version is None

    def test_get_version_malformed_output(self) -> None:
        """Should return None for unexpected output format."""
        from setup_lib.nvidia_toolkit import get_toolkit_version

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "unexpected output without version"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            version = get_toolkit_version()
            assert version is None


class TestIsDockerInstalled:
    """Tests for is_docker_installed() function."""

    def test_docker_installed(self) -> None:
        """Should return True when docker is found in PATH."""
        from setup_lib.nvidia_toolkit import is_docker_installed

        with patch("shutil.which", return_value="/usr/bin/docker"):
            result = is_docker_installed()
            assert result is True

    def test_docker_not_installed(self) -> None:
        """Should return False when docker is not found."""
        from setup_lib.nvidia_toolkit import is_docker_installed

        with patch("shutil.which", return_value=None):
            result = is_docker_installed()
            assert result is False

    def test_checks_docker_binary(self) -> None:
        """Should check specifically for docker."""
        from setup_lib.nvidia_toolkit import is_docker_installed

        with patch("shutil.which") as mock_which:
            mock_which.return_value = None
            is_docker_installed()
            mock_which.assert_called_once_with("docker")


class TestIsPodmanInstalled:
    """Tests for is_podman_installed() function."""

    def test_podman_installed(self) -> None:
        """Should return True when podman is found in PATH."""
        from setup_lib.nvidia_toolkit import is_podman_installed

        with patch("shutil.which", return_value="/usr/bin/podman"):
            result = is_podman_installed()
            assert result is True

    def test_podman_not_installed(self) -> None:
        """Should return False when podman is not found."""
        from setup_lib.nvidia_toolkit import is_podman_installed

        with patch("shutil.which", return_value=None):
            result = is_podman_installed()
            assert result is False

    def test_checks_podman_binary(self) -> None:
        """Should check specifically for podman."""
        from setup_lib.nvidia_toolkit import is_podman_installed

        with patch("shutil.which") as mock_which:
            mock_which.return_value = None
            is_podman_installed()
            mock_which.assert_called_once_with("podman")


class TestGetDetectedRuntimes:
    """Tests for get_detected_runtimes() function."""

    def test_both_runtimes_available(self) -> None:
        """Should return both docker and podman when available."""
        from setup_lib.nvidia_toolkit import get_detected_runtimes

        with (
            patch("setup_lib.nvidia_toolkit.is_docker_installed", return_value=True),
            patch("setup_lib.nvidia_toolkit.is_podman_installed", return_value=True),
        ):
            runtimes = get_detected_runtimes()
            assert "docker" in runtimes
            assert "podman" in runtimes
            assert len(runtimes) == 2

    def test_only_docker_available(self) -> None:
        """Should return only docker when podman is not installed."""
        from setup_lib.nvidia_toolkit import get_detected_runtimes

        with (
            patch("setup_lib.nvidia_toolkit.is_docker_installed", return_value=True),
            patch("setup_lib.nvidia_toolkit.is_podman_installed", return_value=False),
        ):
            runtimes = get_detected_runtimes()
            assert runtimes == ["docker"]

    def test_only_podman_available(self) -> None:
        """Should return only podman when docker is not installed."""
        from setup_lib.nvidia_toolkit import get_detected_runtimes

        with (
            patch("setup_lib.nvidia_toolkit.is_docker_installed", return_value=False),
            patch("setup_lib.nvidia_toolkit.is_podman_installed", return_value=True),
        ):
            runtimes = get_detected_runtimes()
            assert runtimes == ["podman"]

    def test_no_runtimes_available(self) -> None:
        """Should return empty list when no runtimes are installed."""
        from setup_lib.nvidia_toolkit import get_detected_runtimes

        with (
            patch("setup_lib.nvidia_toolkit.is_docker_installed", return_value=False),
            patch("setup_lib.nvidia_toolkit.is_podman_installed", return_value=False),
        ):
            runtimes = get_detected_runtimes()
            assert runtimes == []


class TestGetToolkitInstallationSummary:
    """Tests for get_toolkit_installation_summary() function."""

    def test_summary_with_all_installed(self) -> None:
        """Should return complete summary when everything is installed."""
        from setup_lib.nvidia_toolkit import get_toolkit_installation_summary

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=True),
            patch("setup_lib.nvidia_toolkit.get_toolkit_version", return_value="1.14.3"),
            patch("setup_lib.nvidia_toolkit.is_docker_installed", return_value=True),
            patch("setup_lib.nvidia_toolkit.is_podman_installed", return_value=True),
        ):
            summary = get_toolkit_installation_summary()

            assert summary["toolkit_installed"] is True
            assert summary["toolkit_version"] == "1.14.3"
            assert summary["docker_available"] is True
            assert summary["podman_available"] is True

    def test_summary_toolkit_not_installed(self) -> None:
        """Should return None version when toolkit not installed."""
        from setup_lib.nvidia_toolkit import get_toolkit_installation_summary

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=False),
            patch("setup_lib.nvidia_toolkit.is_docker_installed", return_value=True),
            patch("setup_lib.nvidia_toolkit.is_podman_installed", return_value=False),
        ):
            summary = get_toolkit_installation_summary()

            assert summary["toolkit_installed"] is False
            assert summary["toolkit_version"] is None
            assert summary["docker_available"] is True
            assert summary["podman_available"] is False

    def test_summary_no_runtimes(self) -> None:
        """Should show no runtimes when none are installed."""
        from setup_lib.nvidia_toolkit import get_toolkit_installation_summary

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=True),
            patch("setup_lib.nvidia_toolkit.get_toolkit_version", return_value="1.14.3"),
            patch("setup_lib.nvidia_toolkit.is_docker_installed", return_value=False),
            patch("setup_lib.nvidia_toolkit.is_podman_installed", return_value=False),
        ):
            summary = get_toolkit_installation_summary()

            assert summary["docker_available"] is False
            assert summary["podman_available"] is False


class TestGetInstallCommand:
    """Tests for get_install_command() function."""

    def test_fedora_command(self) -> None:
        """Should return dnf install command for Fedora."""
        from setup_lib.nvidia_toolkit import get_install_command

        cmd = get_install_command("fedora")
        assert cmd is not None
        assert "dnf" in cmd
        assert "nvidia-container-toolkit" in cmd

    def test_debian_command(self) -> None:
        """Should return apt install command for Debian."""
        from setup_lib.nvidia_toolkit import get_install_command

        cmd = get_install_command("debian")
        assert cmd is not None
        assert "apt" in cmd
        assert "nvidia-container-toolkit" in cmd

    def test_arch_command(self) -> None:
        """Should return pacman install command for Arch."""
        from setup_lib.nvidia_toolkit import get_install_command

        cmd = get_install_command("arch")
        assert cmd is not None
        assert "pacman" in cmd
        assert "nvidia-container-toolkit" in cmd

    def test_unknown_distro_returns_none(self) -> None:
        """Should return None for unknown distributions."""
        from setup_lib.nvidia_toolkit import get_install_command

        cmd = get_install_command("unknown")
        assert cmd is None

    def test_empty_distro_returns_none(self) -> None:
        """Should return None for empty distribution family."""
        from setup_lib.nvidia_toolkit import get_install_command

        cmd = get_install_command("")
        assert cmd is None


class TestInstallToolkit:
    """Tests for install_toolkit() function."""

    def test_install_success(self) -> None:
        """Should return True when installation succeeds."""
        from setup_lib.nvidia_toolkit import install_toolkit

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = install_toolkit("fedora")
            assert result is True

    def test_install_failure(self) -> None:
        """Should return False when installation fails."""
        from setup_lib.nvidia_toolkit import install_toolkit

        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = install_toolkit("fedora")
            assert result is False

    def test_install_unknown_distro(self) -> None:
        """Should return False for unknown distribution."""
        from setup_lib.nvidia_toolkit import install_toolkit

        result = install_toolkit("unknown")
        assert result is False

    def test_install_os_error(self) -> None:
        """Should return False and handle OS errors."""
        from setup_lib.nvidia_toolkit import install_toolkit

        with patch("subprocess.run", side_effect=OSError("Permission denied")):
            result = install_toolkit("fedora")
            assert result is False


class TestConfigureDockerRuntime:
    """Tests for configure_docker_runtime() function."""

    def test_configure_success(self) -> None:
        """Should return True when configuration succeeds."""
        from setup_lib.nvidia_toolkit import configure_docker_runtime

        mock_result = MagicMock()
        mock_result.returncode = 0

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=True),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            result = configure_docker_runtime()
            assert result is True
            # Verify correct command is used
            call_args = mock_run.call_args[0][0]
            assert "nvidia-ctk" in call_args
            assert "runtime" in call_args
            assert "configure" in call_args
            assert "--runtime=docker" in call_args

    def test_configure_failure(self) -> None:
        """Should return False when configuration fails."""
        from setup_lib.nvidia_toolkit import configure_docker_runtime

        mock_result = MagicMock()
        mock_result.returncode = 1

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=True),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = configure_docker_runtime()
            assert result is False

    def test_configure_toolkit_not_installed(self) -> None:
        """Should return False when toolkit is not installed."""
        from setup_lib.nvidia_toolkit import configure_docker_runtime

        with patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=False):
            result = configure_docker_runtime()
            assert result is False

    def test_configure_permission_error(self) -> None:
        """Should return False on permission error."""
        from setup_lib.nvidia_toolkit import configure_docker_runtime

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=True),
            patch("subprocess.run", side_effect=PermissionError),
        ):
            result = configure_docker_runtime()
            assert result is False

    def test_configure_timeout(self) -> None:
        """Should return False on timeout."""
        import subprocess

        from setup_lib.nvidia_toolkit import configure_docker_runtime

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=True),
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 60)),
        ):
            result = configure_docker_runtime()
            assert result is False


class TestConfigurePodmanRuntime:
    """Tests for configure_podman_runtime() function."""

    def test_configure_success(self) -> None:
        """Should return True when CDI generation succeeds."""
        from setup_lib.nvidia_toolkit import configure_podman_runtime

        mock_result = MagicMock()
        mock_result.returncode = 0

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=True),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            result = configure_podman_runtime()
            assert result is True
            # Verify correct command is used
            call_args = mock_run.call_args[0][0]
            assert "nvidia-ctk" in call_args
            assert "cdi" in call_args
            assert "generate" in call_args

    def test_configure_failure(self) -> None:
        """Should return False when CDI generation fails."""
        from setup_lib.nvidia_toolkit import configure_podman_runtime

        mock_result = MagicMock()
        mock_result.returncode = 1

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=True),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = configure_podman_runtime()
            assert result is False

    def test_configure_toolkit_not_installed(self) -> None:
        """Should return False when toolkit is not installed."""
        from setup_lib.nvidia_toolkit import configure_podman_runtime

        with patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=False):
            result = configure_podman_runtime()
            assert result is False


class TestConfigureRuntimes:
    """Tests for configure_runtimes() function."""

    def test_configure_both_runtimes(self) -> None:
        """Should configure both runtimes when available."""
        from setup_lib.nvidia_toolkit import configure_runtimes

        with (
            patch(
                "setup_lib.nvidia_toolkit.get_detected_runtimes", return_value=["docker", "podman"]
            ),
            patch("setup_lib.nvidia_toolkit.configure_docker_runtime", return_value=True),
            patch("setup_lib.nvidia_toolkit.configure_podman_runtime", return_value=True),
        ):
            results = configure_runtimes()
            assert results["docker"] is True
            assert results["podman"] is True

    def test_configure_only_docker(self) -> None:
        """Should only configure docker when podman is not available."""
        from setup_lib.nvidia_toolkit import configure_runtimes

        with (
            patch("setup_lib.nvidia_toolkit.get_detected_runtimes", return_value=["docker"]),
            patch(
                "setup_lib.nvidia_toolkit.configure_docker_runtime", return_value=True
            ) as mock_docker,
            patch("setup_lib.nvidia_toolkit.configure_podman_runtime") as mock_podman,
        ):
            results = configure_runtimes()
            assert results == {"docker": True}
            mock_docker.assert_called_once()
            mock_podman.assert_not_called()

    def test_configure_only_podman(self) -> None:
        """Should only configure podman when docker is not available."""
        from setup_lib.nvidia_toolkit import configure_runtimes

        with (
            patch("setup_lib.nvidia_toolkit.get_detected_runtimes", return_value=["podman"]),
            patch("setup_lib.nvidia_toolkit.configure_docker_runtime") as mock_docker,
            patch(
                "setup_lib.nvidia_toolkit.configure_podman_runtime", return_value=True
            ) as mock_podman,
        ):
            results = configure_runtimes()
            assert results == {"podman": True}
            mock_podman.assert_called_once()
            mock_docker.assert_not_called()

    def test_configure_no_runtimes(self) -> None:
        """Should return empty dict when no runtimes are available."""
        from setup_lib.nvidia_toolkit import configure_runtimes

        with patch("setup_lib.nvidia_toolkit.get_detected_runtimes", return_value=[]):
            results = configure_runtimes()
            assert results == {}

    def test_configure_partial_failure(self) -> None:
        """Should report partial success when one runtime fails."""
        from setup_lib.nvidia_toolkit import configure_runtimes

        with (
            patch(
                "setup_lib.nvidia_toolkit.get_detected_runtimes", return_value=["docker", "podman"]
            ),
            patch("setup_lib.nvidia_toolkit.configure_docker_runtime", return_value=True),
            patch("setup_lib.nvidia_toolkit.configure_podman_runtime", return_value=False),
        ):
            results = configure_runtimes()
            assert results["docker"] is True
            assert results["podman"] is False


class TestRestartDockerDaemon:
    """Tests for restart_docker_daemon() function."""

    def test_restart_success(self) -> None:
        """Should return True when restart succeeds."""
        from setup_lib.nvidia_toolkit import restart_docker_daemon

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = restart_docker_daemon()
            assert result is True
            call_args = mock_run.call_args[0][0]
            assert "systemctl" in call_args
            assert "restart" in call_args
            assert "docker" in call_args

    def test_restart_failure(self) -> None:
        """Should return False when restart fails."""
        from setup_lib.nvidia_toolkit import restart_docker_daemon

        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = restart_docker_daemon()
            assert result is False

    def test_restart_permission_error(self) -> None:
        """Should return False on permission error."""
        from setup_lib.nvidia_toolkit import restart_docker_daemon

        with patch("subprocess.run", side_effect=PermissionError):
            result = restart_docker_daemon()
            assert result is False

    def test_restart_systemctl_not_found(self) -> None:
        """Should return False when systemctl is not found."""
        from setup_lib.nvidia_toolkit import restart_docker_daemon

        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = restart_docker_daemon()
            assert result is False


class TestVerifyGpuPassthrough:
    """Tests for verify_gpu_passthrough() function."""

    def test_verify_docker_success(self) -> None:
        """Should return True when Docker GPU test succeeds."""
        from setup_lib.nvidia_toolkit import verify_gpu_passthrough

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = verify_gpu_passthrough("docker")
            assert result is True
            call_args = mock_run.call_args[0][0]
            assert "docker" in call_args
            assert "--gpus" in call_args

    def test_verify_podman_success(self) -> None:
        """Should return True when Podman GPU test succeeds."""
        from setup_lib.nvidia_toolkit import verify_gpu_passthrough

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = verify_gpu_passthrough("podman")
            assert result is True
            call_args = mock_run.call_args[0][0]
            assert "podman" in call_args
            assert "--device" in call_args

    def test_verify_docker_failure(self) -> None:
        """Should return False when Docker GPU test fails."""
        from setup_lib.nvidia_toolkit import verify_gpu_passthrough

        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = verify_gpu_passthrough("docker")
            assert result is False

    def test_verify_invalid_runtime(self) -> None:
        """Should return False for invalid runtime."""
        from setup_lib.nvidia_toolkit import verify_gpu_passthrough

        result = verify_gpu_passthrough("invalid")
        assert result is False

    def test_verify_timeout(self) -> None:
        """Should return False on timeout."""
        import subprocess

        from setup_lib.nvidia_toolkit import verify_gpu_passthrough

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 120)):
            result = verify_gpu_passthrough("docker")
            assert result is False


class TestPromptAndInstallToolkit:
    """Tests for prompt_and_install_toolkit() function."""

    def test_already_installed(self) -> None:
        """Should return True immediately if toolkit is already installed."""
        from setup_lib.nvidia_toolkit import prompt_and_install_toolkit

        with patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=True):
            result = prompt_and_install_toolkit()
            assert result is True

    def test_no_distro_family(self) -> None:
        """Should return False when distro family is not provided."""
        from setup_lib.nvidia_toolkit import prompt_and_install_toolkit

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=False),
            patch("builtins.print"),
        ):
            result = prompt_and_install_toolkit(config={})
            assert result is False

    def test_unsupported_distro(self) -> None:
        """Should return False for unsupported distribution."""
        from setup_lib.nvidia_toolkit import prompt_and_install_toolkit

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=False),
            patch("builtins.print"),
        ):
            result = prompt_and_install_toolkit(config={"distro_family": "unknown"})
            assert result is False

    def test_user_declines(self) -> None:
        """Should return False when user declines installation."""
        from setup_lib.nvidia_toolkit import prompt_and_install_toolkit

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=False),
            patch("builtins.input", return_value="n"),
            patch("builtins.print"),
        ):
            result = prompt_and_install_toolkit(config={"distro_family": "fedora"})
            assert result is False

    def test_user_accepts_success(self) -> None:
        """Should return True when user accepts and install succeeds."""
        from setup_lib.nvidia_toolkit import prompt_and_install_toolkit

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=False),
            patch("builtins.input", return_value="y"),
            patch("setup_lib.nvidia_toolkit.install_toolkit", return_value=True),
            patch("builtins.print"),
        ):
            result = prompt_and_install_toolkit(config={"distro_family": "fedora"})
            assert result is True

    def test_user_accepts_failure(self) -> None:
        """Should return False when user accepts but install fails."""
        from setup_lib.nvidia_toolkit import prompt_and_install_toolkit

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=False),
            patch("builtins.input", return_value="y"),
            patch("setup_lib.nvidia_toolkit.install_toolkit", return_value=False),
            patch("builtins.print"),
        ):
            result = prompt_and_install_toolkit(config={"distro_family": "fedora"})
            assert result is False

    def test_auto_install_skips_prompt(self) -> None:
        """Should skip user prompt when auto_install is True."""
        from setup_lib.nvidia_toolkit import prompt_and_install_toolkit

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=False),
            patch("builtins.input") as mock_input,
            patch("setup_lib.nvidia_toolkit.install_toolkit", return_value=True),
            patch("builtins.print"),
        ):
            result = prompt_and_install_toolkit(
                config={"distro_family": "fedora", "auto_install": True}
            )
            assert result is True
            mock_input.assert_not_called()

    def test_case_insensitive_yes(self) -> None:
        """Should accept various forms of 'yes'."""
        from setup_lib.nvidia_toolkit import prompt_and_install_toolkit

        for response in ["Y", "yes", "YES", "Yes"]:
            with (
                patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=False),
                patch("builtins.input", return_value=response),
                patch("setup_lib.nvidia_toolkit.install_toolkit", return_value=True),
                patch("builtins.print"),
            ):
                result = prompt_and_install_toolkit(config={"distro_family": "fedora"})
                assert result is True, f"Failed for response: {response}"


class TestPromptAndConfigureRuntimes:
    """Tests for prompt_and_configure_runtimes() function."""

    def test_toolkit_not_installed(self) -> None:
        """Should return False when toolkit is not installed."""
        from setup_lib.nvidia_toolkit import prompt_and_configure_runtimes

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=False),
            patch("builtins.print"),
        ):
            result = prompt_and_configure_runtimes()
            assert result is False

    def test_no_runtimes_detected(self) -> None:
        """Should return False when no runtimes are detected."""
        from setup_lib.nvidia_toolkit import prompt_and_configure_runtimes

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=True),
            patch("setup_lib.nvidia_toolkit.get_detected_runtimes", return_value=[]),
            patch("builtins.print"),
        ):
            result = prompt_and_configure_runtimes()
            assert result is False

    def test_user_declines(self) -> None:
        """Should return False when user declines configuration."""
        from setup_lib.nvidia_toolkit import prompt_and_configure_runtimes

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=True),
            patch("setup_lib.nvidia_toolkit.get_detected_runtimes", return_value=["docker"]),
            patch("builtins.input", return_value="n"),
            patch("builtins.print"),
        ):
            result = prompt_and_configure_runtimes()
            assert result is False

    def test_user_accepts_success(self) -> None:
        """Should return True when user accepts and configuration succeeds."""
        from setup_lib.nvidia_toolkit import prompt_and_configure_runtimes

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=True),
            patch("setup_lib.nvidia_toolkit.get_detected_runtimes", return_value=["docker"]),
            patch("builtins.input", return_value="y"),
            patch("setup_lib.nvidia_toolkit.configure_runtimes", return_value={"docker": True}),
            patch("setup_lib.nvidia_toolkit.restart_docker_daemon", return_value=True),
            patch("builtins.print"),
        ):
            result = prompt_and_configure_runtimes()
            assert result is True

    def test_auto_install_skips_prompt(self) -> None:
        """Should skip user prompt when auto_install is True."""
        from setup_lib.nvidia_toolkit import prompt_and_configure_runtimes

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=True),
            patch("setup_lib.nvidia_toolkit.get_detected_runtimes", return_value=["docker"]),
            patch("builtins.input") as mock_input,
            patch("setup_lib.nvidia_toolkit.configure_runtimes", return_value={"docker": True}),
            patch("setup_lib.nvidia_toolkit.restart_docker_daemon", return_value=True),
            patch("builtins.print"),
        ):
            result = prompt_and_configure_runtimes(config={"auto_install": True})
            assert result is True
            mock_input.assert_not_called()

    def test_docker_restart_on_success(self) -> None:
        """Should restart Docker after successful configuration."""
        from setup_lib.nvidia_toolkit import prompt_and_configure_runtimes

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=True),
            patch("setup_lib.nvidia_toolkit.get_detected_runtimes", return_value=["docker"]),
            patch("setup_lib.nvidia_toolkit.configure_runtimes", return_value={"docker": True}),
            patch(
                "setup_lib.nvidia_toolkit.restart_docker_daemon", return_value=True
            ) as mock_restart,
            patch("builtins.print"),
        ):
            prompt_and_configure_runtimes(config={"auto_install": True})
            mock_restart.assert_called_once()

    def test_no_docker_restart_on_failure(self) -> None:
        """Should not restart Docker if configuration failed."""
        from setup_lib.nvidia_toolkit import prompt_and_configure_runtimes

        with (
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=True),
            patch("setup_lib.nvidia_toolkit.get_detected_runtimes", return_value=["docker"]),
            patch("setup_lib.nvidia_toolkit.configure_runtimes", return_value={"docker": False}),
            patch("setup_lib.nvidia_toolkit.restart_docker_daemon") as mock_restart,
            patch("builtins.print"),
        ):
            prompt_and_configure_runtimes(config={"auto_install": True})
            mock_restart.assert_not_called()


class TestSetupNvidiaContainerToolkit:
    """Tests for setup_nvidia_container_toolkit() function."""

    def test_unsupported_platform(self) -> None:
        """Should return False for unsupported platforms."""
        from setup_lib.nvidia_toolkit import setup_nvidia_container_toolkit

        with (
            patch("setup_lib.platform_detect.get_platform_info", return_value=None),
            patch("builtins.print"),
        ):
            result = setup_nvidia_container_toolkit()
            assert result is False

    def test_non_linux_platform(self) -> None:
        """Should return False for non-Linux platforms."""
        from setup_lib.nvidia_toolkit import setup_nvidia_container_toolkit

        platform_info = {
            "platform": "windows",
            "distro": None,
            "package_manager": "winget",
            "is_wsl": False,
        }

        with (
            patch("setup_lib.platform_detect.get_platform_info", return_value=platform_info),
            patch("builtins.print"),
        ):
            result = setup_nvidia_container_toolkit()
            assert result is False

    def test_unknown_distro_family(self) -> None:
        """Should return False for unknown distribution family."""
        from setup_lib.nvidia_toolkit import setup_nvidia_container_toolkit

        platform_info = {
            "platform": "linux",
            "distro": {"id": "gentoo"},
            "package_manager": "emerge",
            "is_wsl": False,
        }

        with (
            patch("setup_lib.platform_detect.get_platform_info", return_value=platform_info),
            patch("setup_lib.platform_detect.get_distro_family", return_value="unknown"),
            patch("builtins.print"),
        ):
            result = setup_nvidia_container_toolkit()
            assert result is False

    def test_toolkit_already_installed(self) -> None:
        """Should succeed when toolkit is already installed."""
        from setup_lib.nvidia_toolkit import setup_nvidia_container_toolkit

        platform_info = {
            "platform": "linux",
            "distro": {"id": "fedora"},
            "package_manager": "dnf",
            "is_wsl": False,
        }

        with (
            patch("setup_lib.platform_detect.get_platform_info", return_value=platform_info),
            patch("setup_lib.platform_detect.get_distro_family", return_value="fedora"),
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=True),
            patch("setup_lib.nvidia_toolkit.get_toolkit_version", return_value="1.14.3"),
            patch("setup_lib.nvidia_toolkit.get_detected_runtimes", return_value=["docker"]),
            patch("setup_lib.nvidia_toolkit.prompt_and_configure_runtimes", return_value=True),
            patch("builtins.print"),
        ):
            result = setup_nvidia_container_toolkit()
            assert result is True

    def test_full_setup_success(self) -> None:
        """Should complete full setup successfully."""
        from setup_lib.nvidia_toolkit import setup_nvidia_container_toolkit

        platform_info = {
            "platform": "linux",
            "distro": {"id": "fedora"},
            "package_manager": "dnf",
            "is_wsl": False,
        }

        with (
            patch("setup_lib.platform_detect.get_platform_info", return_value=platform_info),
            patch("setup_lib.platform_detect.get_distro_family", return_value="fedora"),
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=False),
            patch("setup_lib.nvidia_toolkit.prompt_and_install_toolkit", return_value=True),
            patch("setup_lib.nvidia_toolkit.get_detected_runtimes", return_value=["docker"]),
            patch("setup_lib.nvidia_toolkit.prompt_and_configure_runtimes", return_value=True),
            patch("builtins.print"),
        ):
            result = setup_nvidia_container_toolkit(auto_install=True)
            assert result is True

    def test_install_fails(self) -> None:
        """Should return False when installation fails."""
        from setup_lib.nvidia_toolkit import setup_nvidia_container_toolkit

        platform_info = {
            "platform": "linux",
            "distro": {"id": "fedora"},
            "package_manager": "dnf",
            "is_wsl": False,
        }

        with (
            patch("setup_lib.platform_detect.get_platform_info", return_value=platform_info),
            patch("setup_lib.platform_detect.get_distro_family", return_value="fedora"),
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=False),
            patch("setup_lib.nvidia_toolkit.prompt_and_install_toolkit", return_value=False),
            patch("builtins.print"),
        ):
            result = setup_nvidia_container_toolkit()
            assert result is False

    def test_no_runtimes_still_succeeds(self) -> None:
        """Should succeed even when no runtimes are detected."""
        from setup_lib.nvidia_toolkit import setup_nvidia_container_toolkit

        platform_info = {
            "platform": "linux",
            "distro": {"id": "fedora"},
            "package_manager": "dnf",
            "is_wsl": False,
        }

        with (
            patch("setup_lib.platform_detect.get_platform_info", return_value=platform_info),
            patch("setup_lib.platform_detect.get_distro_family", return_value="fedora"),
            patch("setup_lib.nvidia_toolkit.is_toolkit_installed", return_value=True),
            patch("setup_lib.nvidia_toolkit.get_toolkit_version", return_value="1.14.3"),
            patch("setup_lib.nvidia_toolkit.get_detected_runtimes", return_value=[]),
            patch("builtins.print"),
        ):
            result = setup_nvidia_container_toolkit()
            assert result is True


class TestPrintToolkitInfo:
    """Tests for print_toolkit_info() function."""

    def test_print_with_toolkit_installed(self) -> None:
        """Should print info when toolkit is installed."""
        from setup_lib.nvidia_toolkit import print_toolkit_info

        summary = {
            "toolkit_installed": True,
            "toolkit_version": "1.14.3",
            "docker_available": True,
            "podman_available": False,
            "docker_configured": False,
            "podman_configured": False,
        }

        with (
            patch(
                "setup_lib.nvidia_toolkit.get_toolkit_installation_summary", return_value=summary
            ),
            patch("setup_lib.nvidia_toolkit.get_detected_runtimes", return_value=["docker"]),
            patch("builtins.print") as mock_print,
        ):
            print_toolkit_info()
            # Verify print was called
            assert mock_print.call_count > 0

    def test_print_without_toolkit(self) -> None:
        """Should print info when toolkit is not installed."""
        from setup_lib.nvidia_toolkit import print_toolkit_info

        summary = {
            "toolkit_installed": False,
            "toolkit_version": None,
            "docker_available": False,
            "podman_available": False,
            "docker_configured": False,
            "podman_configured": False,
        }

        with (
            patch(
                "setup_lib.nvidia_toolkit.get_toolkit_installation_summary", return_value=summary
            ),
            patch("setup_lib.nvidia_toolkit.get_detected_runtimes", return_value=[]),
            patch("builtins.print") as mock_print,
        ):
            print_toolkit_info()
            assert mock_print.call_count > 0
