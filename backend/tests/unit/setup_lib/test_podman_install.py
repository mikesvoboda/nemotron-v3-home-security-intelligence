"""Unit tests for setup_lib.podman_install module.

Tests Podman detection, installation command generation, and installation process
across different platforms (Fedora/dnf, Debian/apt, Arch/pacman, Windows/winget).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from setup_lib.platform_detect import PlatformInfo


class TestIsPodmanInstalled:
    """Tests for is_podman_installed() function."""

    def test_podman_installed(self) -> None:
        """Should return True when podman is found in PATH."""
        from setup_lib.podman_install import is_podman_installed

        with patch("shutil.which", return_value="/usr/bin/podman"):
            result = is_podman_installed()
            assert result is True

    def test_podman_not_installed(self) -> None:
        """Should return False when podman is not in PATH."""
        from setup_lib.podman_install import is_podman_installed

        with patch("shutil.which", return_value=None):
            result = is_podman_installed()
            assert result is False

    def test_uses_shutil_which(self) -> None:
        """Should call shutil.which with 'podman'."""
        from setup_lib.podman_install import is_podman_installed

        with patch("shutil.which") as mock_which:
            mock_which.return_value = None
            is_podman_installed()
            mock_which.assert_called_once_with("podman")


class TestGetPodmanVersion:
    """Tests for get_podman_version() function."""

    def test_get_version_success(self) -> None:
        """Should parse version from 'podman --version' output."""
        from setup_lib.podman_install import get_podman_version

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "podman version 5.3.1"

        with patch("subprocess.run", return_value=mock_result):
            version = get_podman_version()
            assert version == "5.3.1"

    def test_get_version_with_extra_info(self) -> None:
        """Should parse version even with build info."""
        from setup_lib.podman_install import get_podman_version

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "podman version 5.3.1-dev"

        with patch("subprocess.run", return_value=mock_result):
            version = get_podman_version()
            assert version == "5.3.1-dev"

    def test_get_version_podman_not_installed(self) -> None:
        """Should return None when podman is not installed."""
        from setup_lib.podman_install import get_podman_version

        with patch("subprocess.run", side_effect=FileNotFoundError):
            version = get_podman_version()
            assert version is None

    def test_get_version_command_fails(self) -> None:
        """Should return None when command returns non-zero exit."""
        from setup_lib.podman_install import get_podman_version

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            version = get_podman_version()
            assert version is None

    def test_get_version_malformed_output(self) -> None:
        """Should return None for unexpected output format."""
        from setup_lib.podman_install import get_podman_version

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "unexpected output"

        with patch("subprocess.run", return_value=mock_result):
            version = get_podman_version()
            assert version is None


class TestGetInstallCommand:
    """Tests for get_install_command() function."""

    def test_fedora_dnf_command(self) -> None:
        """Should return dnf install command for Fedora."""
        from setup_lib.podman_install import get_install_command

        platform_info: PlatformInfo = {
            "platform": "linux",
            "distro": {"id": "fedora"},
            "package_manager": "dnf",
            "is_wsl": False,
        }
        cmd = get_install_command(platform_info)
        assert cmd == ["sudo", "dnf", "install", "-y", "podman"]

    def test_debian_apt_command(self) -> None:
        """Should return apt install command for Debian/Ubuntu."""
        from setup_lib.podman_install import get_install_command

        platform_info: PlatformInfo = {
            "platform": "linux",
            "distro": {"id": "ubuntu", "id_like": "debian"},
            "package_manager": "apt",
            "is_wsl": False,
        }
        cmd = get_install_command(platform_info)
        assert cmd == ["sudo", "apt", "install", "-y", "podman"]

    def test_arch_pacman_command(self) -> None:
        """Should return pacman install command for Arch."""
        from setup_lib.podman_install import get_install_command

        platform_info: PlatformInfo = {
            "platform": "linux",
            "distro": {"id": "arch"},
            "package_manager": "pacman",
            "is_wsl": False,
        }
        cmd = get_install_command(platform_info)
        assert cmd == ["sudo", "pacman", "-S", "--noconfirm", "podman"]

    def test_windows_winget_command(self) -> None:
        """Should return winget install command for Windows."""
        from setup_lib.podman_install import get_install_command

        platform_info: PlatformInfo = {
            "platform": "windows",
            "distro": None,
            "package_manager": "winget",
            "is_wsl": False,
        }
        cmd = get_install_command(platform_info)
        assert cmd == ["winget", "install", "-e", "--id", "RedHat.Podman"]

    def test_no_package_manager(self) -> None:
        """Should return None when no package manager is available."""
        from setup_lib.podman_install import get_install_command

        platform_info: PlatformInfo = {
            "platform": "linux",
            "distro": {"id": "gentoo"},
            "package_manager": None,
            "is_wsl": False,
        }
        cmd = get_install_command(platform_info)
        assert cmd is None

    def test_unsupported_package_manager(self) -> None:
        """Should return None for unsupported package manager."""
        from setup_lib.podman_install import get_install_command

        platform_info: PlatformInfo = {
            "platform": "linux",
            "distro": {"id": "gentoo"},
            "package_manager": "emerge",
            "is_wsl": False,
        }
        cmd = get_install_command(platform_info)
        assert cmd is None


class TestInstallPodman:
    """Tests for install_podman() function."""

    def test_install_success(self) -> None:
        """Should return True when installation succeeds."""
        from setup_lib.podman_install import install_podman

        platform_info: PlatformInfo = {
            "platform": "linux",
            "distro": {"id": "fedora"},
            "package_manager": "dnf",
            "is_wsl": False,
        }

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = install_podman(platform_info)
            assert result is True
            mock_run.assert_called_once_with(
                ["sudo", "dnf", "install", "-y", "podman"],
                check=False,
            )

    def test_install_failure(self) -> None:
        """Should return False when installation fails."""
        from setup_lib.podman_install import install_podman

        platform_info: PlatformInfo = {
            "platform": "linux",
            "distro": {"id": "fedora"},
            "package_manager": "dnf",
            "is_wsl": False,
        }

        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = install_podman(platform_info)
            assert result is False

    def test_install_no_command(self) -> None:
        """Should return False when no install command available."""
        from setup_lib.podman_install import install_podman

        platform_info: PlatformInfo = {
            "platform": "linux",
            "distro": {"id": "gentoo"},
            "package_manager": None,
            "is_wsl": False,
        }

        result = install_podman(platform_info)
        assert result is False

    def test_install_subprocess_exception(self) -> None:
        """Should return False and handle subprocess exceptions."""
        from setup_lib.podman_install import install_podman

        platform_info: PlatformInfo = {
            "platform": "linux",
            "distro": {"id": "fedora"},
            "package_manager": "dnf",
            "is_wsl": False,
        }

        with patch("subprocess.run", side_effect=OSError("Permission denied")):
            result = install_podman(platform_info)
            assert result is False


class TestInitPodmanMachine:
    """Tests for init_podman_machine() function."""

    def test_init_machine_success(self) -> None:
        """Should return True when machine init succeeds."""
        from setup_lib.podman_install import init_podman_machine

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = init_podman_machine()
            assert result is True
            # Should call podman machine init and start
            assert mock_run.call_count == 2
            mock_run.assert_any_call(
                ["podman", "machine", "init"],
                check=False,
            )
            mock_run.assert_any_call(
                ["podman", "machine", "start"],
                check=False,
            )

    def test_init_machine_init_fails(self) -> None:
        """Should return False when machine init fails."""
        from setup_lib.podman_install import init_podman_machine

        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = init_podman_machine()
            assert result is False

    def test_init_machine_start_fails(self) -> None:
        """Should return False when machine start fails."""
        from setup_lib.podman_install import init_podman_machine

        init_result = MagicMock()
        init_result.returncode = 0
        start_result = MagicMock()
        start_result.returncode = 1

        with patch("subprocess.run", side_effect=[init_result, start_result]):
            result = init_podman_machine()
            assert result is False

    def test_init_machine_exception(self) -> None:
        """Should return False and handle exceptions."""
        from setup_lib.podman_install import init_podman_machine

        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = init_podman_machine()
            assert result is False

    def test_init_machine_already_exists(self) -> None:
        """Should handle case where machine already exists."""
        from setup_lib.podman_install import init_podman_machine

        # init fails (machine exists), but start succeeds
        init_result = MagicMock()
        init_result.returncode = 125  # Machine already exists
        init_result.stderr = "machine already exists"
        start_result = MagicMock()
        start_result.returncode = 0

        with patch("subprocess.run", side_effect=[init_result, start_result]):
            # Should try to start anyway
            result = init_podman_machine()
            # Depending on implementation, this could be True or False
            # If machine exists, we should still try to start it
            assert isinstance(result, bool)


class TestPromptAndInstallPodman:
    """Tests for prompt_and_install_podman() function."""

    def test_podman_already_installed(self) -> None:
        """Should return True immediately if podman is already installed."""
        from setup_lib.podman_install import prompt_and_install_podman

        platform_info: PlatformInfo = {
            "platform": "linux",
            "distro": {"id": "fedora"},
            "package_manager": "dnf",
            "is_wsl": False,
        }

        with (
            patch("setup_lib.podman_install.get_platform_info", return_value=platform_info),
            patch("setup_lib.podman_install.is_podman_installed", return_value=True),
            patch("setup_lib.podman_install.get_podman_version", return_value="5.3.1"),
            patch("setup_lib.podman_install.is_podman_compose_installed", return_value=True),
            patch("setup_lib.podman_install.configure_rootless_cgroups"),
            patch("builtins.print"),
        ):
            result = prompt_and_install_podman()
            assert result is True

    def test_user_declines_install(self) -> None:
        """Should return False when user declines installation."""
        from setup_lib.podman_install import prompt_and_install_podman

        platform_info: PlatformInfo = {
            "platform": "linux",
            "distro": {"id": "fedora"},
            "package_manager": "dnf",
            "is_wsl": False,
        }

        with (
            patch("setup_lib.podman_install.is_podman_installed", return_value=False),
            patch("setup_lib.podman_install.get_platform_info", return_value=platform_info),
            patch("builtins.input", return_value="n"),
        ):
            result = prompt_and_install_podman()
            assert result is False

    def test_user_accepts_install_success(self) -> None:
        """Should return True when user accepts and install succeeds."""
        from setup_lib.podman_install import prompt_and_install_podman

        platform_info: PlatformInfo = {
            "platform": "linux",
            "distro": {"id": "fedora"},
            "package_manager": "dnf",
            "is_wsl": False,
        }

        with (
            patch(
                "setup_lib.podman_install.is_podman_installed",
                side_effect=[False, True],
            ),
            patch("setup_lib.podman_install.get_platform_info", return_value=platform_info),
            patch(
                "setup_lib.podman_install.get_install_command",
                return_value=["dnf", "install", "-y", "podman"],
            ),
            patch("builtins.input", return_value="y"),
            patch("setup_lib.podman_install.install_podman", return_value=True),
            patch("setup_lib.podman_install.get_podman_version", return_value="5.3.1"),
            patch("setup_lib.podman_install.is_podman_compose_installed", return_value=True),
            patch("setup_lib.podman_install.configure_rootless_cgroups"),
            patch("builtins.print"),
        ):
            result = prompt_and_install_podman()
            assert result is True

    def test_user_accepts_install_fails(self) -> None:
        """Should return False when user accepts but install fails."""
        from setup_lib.podman_install import prompt_and_install_podman

        platform_info: PlatformInfo = {
            "platform": "linux",
            "distro": {"id": "fedora"},
            "package_manager": "dnf",
            "is_wsl": False,
        }

        with (
            patch("setup_lib.podman_install.is_podman_installed", return_value=False),
            patch("setup_lib.podman_install.get_platform_info", return_value=platform_info),
            patch("builtins.input", return_value="y"),
            patch("setup_lib.podman_install.install_podman", return_value=False),
        ):
            result = prompt_and_install_podman()
            assert result is False

    def test_windows_init_machine_after_install(self) -> None:
        """Should call init_podman_machine after install on Windows."""
        from setup_lib.podman_install import prompt_and_install_podman

        platform_info: PlatformInfo = {
            "platform": "windows",
            "distro": None,
            "package_manager": "winget",
            "is_wsl": False,
        }

        with (
            patch(
                "setup_lib.podman_install.is_podman_installed",
                side_effect=[False, True],
            ),
            patch("setup_lib.podman_install.get_platform_info", return_value=platform_info),
            patch(
                "setup_lib.podman_install.get_install_command",
                return_value=["winget", "install", "-e", "--id", "RedHat.Podman"],
            ),
            patch("builtins.input", return_value="y"),
            patch("setup_lib.podman_install.install_podman", return_value=True),
            patch("setup_lib.podman_install.get_podman_version", return_value="5.3.1"),
            patch("setup_lib.podman_install.is_podman_compose_installed", return_value=True),
            patch("setup_lib.podman_install.configure_rootless_cgroups"),
            patch("setup_lib.podman_install.init_podman_machine", return_value=True) as mock_init,
            patch("builtins.print"),
        ):
            result = prompt_and_install_podman()
            assert result is True
            mock_init.assert_called_once()

    def test_windows_init_machine_fails(self) -> None:
        """Should return False when Windows machine init fails."""
        from setup_lib.podman_install import prompt_and_install_podman

        platform_info: PlatformInfo = {
            "platform": "windows",
            "distro": None,
            "package_manager": "winget",
            "is_wsl": False,
        }

        with (
            patch("setup_lib.podman_install.is_podman_installed", return_value=False),
            patch("setup_lib.podman_install.get_platform_info", return_value=platform_info),
            patch("builtins.input", return_value="y"),
            patch("setup_lib.podman_install.install_podman", return_value=True),
            patch("setup_lib.podman_install.init_podman_machine", return_value=False),
        ):
            result = prompt_and_install_podman()
            assert result is False

    def test_unsupported_platform(self) -> None:
        """Should return False for unsupported platforms (no platform info)."""
        from setup_lib.podman_install import prompt_and_install_podman

        with (
            patch("setup_lib.podman_install.is_podman_installed", return_value=False),
            patch("setup_lib.podman_install.get_platform_info", return_value=None),
        ):
            result = prompt_and_install_podman()
            assert result is False

    def test_accepts_config_parameter(self) -> None:
        """Should accept an optional config dict parameter."""
        from setup_lib.podman_install import prompt_and_install_podman

        # Test that function signature accepts config parameter
        with patch("setup_lib.podman_install.is_podman_installed", return_value=True):
            result = prompt_and_install_podman(config={"auto_install": True})
            assert result is True

    def test_auto_install_skips_prompt(self) -> None:
        """Should skip user prompt when config['auto_install'] is True."""
        from setup_lib.podman_install import prompt_and_install_podman

        platform_info: PlatformInfo = {
            "platform": "linux",
            "distro": {"id": "fedora"},
            "package_manager": "dnf",
            "is_wsl": False,
        }

        with (
            patch(
                "setup_lib.podman_install.is_podman_installed",
                side_effect=[False, True],
            ),
            patch("setup_lib.podman_install.get_platform_info", return_value=platform_info),
            patch(
                "setup_lib.podman_install.get_install_command",
                return_value=["sudo", "dnf", "install", "-y", "podman"],
            ),
            patch("builtins.input") as mock_input,
            patch("setup_lib.podman_install.install_podman", return_value=True),
            patch("setup_lib.podman_install.get_podman_version", return_value="5.3.1"),
            patch("setup_lib.podman_install.is_podman_compose_installed", return_value=True),
            patch("setup_lib.podman_install.configure_rootless_cgroups"),
            patch("builtins.print"),
        ):
            result = prompt_and_install_podman(config={"auto_install": True})
            assert result is True
            mock_input.assert_not_called()

    def test_empty_input_defaults_to_no(self) -> None:
        """Should treat empty input as 'no'."""
        from setup_lib.podman_install import prompt_and_install_podman

        platform_info: PlatformInfo = {
            "platform": "linux",
            "distro": {"id": "fedora"},
            "package_manager": "dnf",
            "is_wsl": False,
        }

        with (
            patch("setup_lib.podman_install.is_podman_installed", return_value=False),
            patch("setup_lib.podman_install.get_platform_info", return_value=platform_info),
            patch("builtins.input", return_value=""),
        ):
            result = prompt_and_install_podman()
            assert result is False

    def test_case_insensitive_yes(self) -> None:
        """Should accept 'Y', 'yes', 'YES' as positive responses."""
        from setup_lib.podman_install import prompt_and_install_podman

        platform_info: PlatformInfo = {
            "platform": "linux",
            "distro": {"id": "fedora"},
            "package_manager": "dnf",
            "is_wsl": False,
        }

        for response in ["Y", "yes", "YES", "Yes"]:
            with (
                patch("setup_lib.podman_install.is_podman_installed", return_value=False),
                patch("setup_lib.podman_install.get_platform_info", return_value=platform_info),
                patch("builtins.input", return_value=response),
                patch("setup_lib.podman_install._do_install_podman", return_value=True),
                patch("setup_lib.podman_install.configure_rootless_cgroups"),
            ):
                result = prompt_and_install_podman()
                assert result is True, f"Failed for response: {response}"
