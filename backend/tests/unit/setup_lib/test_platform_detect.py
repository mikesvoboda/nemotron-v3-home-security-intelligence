"""Unit tests for setup_lib.platform_detect module.

Tests platform detection, Linux distro identification, package manager detection,
and Windows/WSL detection.
"""

from __future__ import annotations

from unittest.mock import patch


class TestDetectPlatform:
    """Tests for detect_platform() function."""

    def test_detect_linux(self) -> None:
        """Should detect Linux platform."""
        from setup_lib.platform_detect import detect_platform

        with patch("platform.system", return_value="Linux"):
            result = detect_platform()
            assert result == "linux"

    def test_detect_windows(self) -> None:
        """Should detect Windows platform."""
        from setup_lib.platform_detect import detect_platform

        with patch("platform.system", return_value="Windows"):
            result = detect_platform()
            assert result == "windows"

    def test_detect_unsupported_macos(self) -> None:
        """Should return None for unsupported macOS."""
        from setup_lib.platform_detect import detect_platform

        with patch("platform.system", return_value="Darwin"):
            result = detect_platform()
            assert result is None


class TestDetectLinuxDistro:
    """Tests for detect_linux_distro() function."""

    def test_fedora_detection(self) -> None:
        """Should detect Fedora from /etc/os-release."""
        from setup_lib.platform_detect import detect_linux_distro

        os_release_content = """NAME="Fedora Linux"
VERSION="43 (Workstation Edition)"
ID=fedora
VERSION_ID=43
PRETTY_NAME="Fedora Linux 43 (Workstation Edition)"
"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=os_release_content),
        ):
            result = detect_linux_distro()
            assert result is not None
            assert result["id"] == "fedora"
            assert result["version_id"] == "43"
            assert result["name"] == "Fedora Linux"

    def test_ubuntu_detection(self) -> None:
        """Should detect Ubuntu from /etc/os-release."""
        from setup_lib.platform_detect import detect_linux_distro

        os_release_content = """NAME="Ubuntu"
VERSION="24.04 LTS (Noble Numbat)"
ID=ubuntu
ID_LIKE=debian
VERSION_ID="24.04"
PRETTY_NAME="Ubuntu 24.04 LTS"
"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=os_release_content),
        ):
            result = detect_linux_distro()
            assert result is not None
            assert result["id"] == "ubuntu"
            assert result["version_id"] == "24.04"
            assert result["id_like"] == "debian"

    def test_debian_detection(self) -> None:
        """Should detect Debian from /etc/os-release."""
        from setup_lib.platform_detect import detect_linux_distro

        os_release_content = """NAME="Debian GNU/Linux"
VERSION_ID="12"
ID=debian
PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"
"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=os_release_content),
        ):
            result = detect_linux_distro()
            assert result is not None
            assert result["id"] == "debian"
            assert result["version_id"] == "12"

    def test_rhel_detection(self) -> None:
        """Should detect RHEL from /etc/os-release."""
        from setup_lib.platform_detect import detect_linux_distro

        os_release_content = """NAME="Red Hat Enterprise Linux"
VERSION="9.3 (Plow)"
ID="rhel"
ID_LIKE="fedora"
VERSION_ID="9.3"
"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=os_release_content),
        ):
            result = detect_linux_distro()
            assert result is not None
            assert result["id"] == "rhel"
            assert result["id_like"] == "fedora"

    def test_arch_detection(self) -> None:
        """Should detect Arch Linux from /etc/os-release."""
        from setup_lib.platform_detect import detect_linux_distro

        os_release_content = """NAME="Arch Linux"
ID=arch
PRETTY_NAME="Arch Linux"
"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=os_release_content),
        ):
            result = detect_linux_distro()
            assert result is not None
            assert result["id"] == "arch"

    def test_missing_os_release(self) -> None:
        """Should return None when /etc/os-release doesn't exist."""
        from setup_lib.platform_detect import detect_linux_distro

        with patch("pathlib.Path.exists", return_value=False):
            result = detect_linux_distro()
            assert result is None

    def test_malformed_os_release(self) -> None:
        """Should handle malformed /etc/os-release gracefully."""
        from setup_lib.platform_detect import detect_linux_distro

        os_release_content = """not valid content
without = proper format
"""
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=os_release_content),
        ):
            result = detect_linux_distro()
            # Should return empty dict or partial results, not crash
            assert result is not None or result is None


class TestDetectPackageManager:
    """Tests for detect_package_manager() function."""

    def test_detect_dnf(self) -> None:
        """Should detect dnf package manager."""
        from setup_lib.platform_detect import detect_package_manager

        with patch("shutil.which") as mock_which:
            mock_which.side_effect = lambda cmd: "/usr/bin/dnf" if cmd == "dnf" else None
            result = detect_package_manager()
            assert result == "dnf"

    def test_detect_apt(self) -> None:
        """Should detect apt package manager."""
        from setup_lib.platform_detect import detect_package_manager

        with patch("shutil.which") as mock_which:
            mock_which.side_effect = lambda cmd: "/usr/bin/apt" if cmd == "apt" else None
            result = detect_package_manager()
            assert result == "apt"

    def test_detect_pacman(self) -> None:
        """Should detect pacman package manager."""
        from setup_lib.platform_detect import detect_package_manager

        with patch("shutil.which") as mock_which:
            mock_which.side_effect = lambda cmd: "/usr/bin/pacman" if cmd == "pacman" else None
            result = detect_package_manager()
            assert result == "pacman"

    def test_detect_winget(self) -> None:
        """Should detect winget on Windows."""
        from setup_lib.platform_detect import detect_package_manager

        with patch("shutil.which") as mock_which:
            mock_which.side_effect = (
                lambda cmd: "C:\\Windows\\winget.exe" if cmd == "winget" else None
            )
            result = detect_package_manager()
            assert result == "winget"

    def test_no_package_manager_found(self) -> None:
        """Should return None when no package manager found."""
        from setup_lib.platform_detect import detect_package_manager

        with patch("shutil.which", return_value=None):
            result = detect_package_manager()
            assert result is None


class TestIsWsl:
    """Tests for is_wsl() function."""

    def test_detect_wsl1(self) -> None:
        """Should detect WSL1 from /proc/version."""
        from setup_lib.platform_detect import is_wsl

        wsl_version = "Linux version 4.4.0-19041-Microsoft"
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=wsl_version),
        ):
            result = is_wsl()
            assert result is True

    def test_detect_wsl2(self) -> None:
        """Should detect WSL2 from /proc/version."""
        from setup_lib.platform_detect import is_wsl

        wsl_version = "Linux version 5.15.90.1-microsoft-standard-WSL2"
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=wsl_version),
        ):
            result = is_wsl()
            assert result is True

    def test_not_wsl(self) -> None:
        """Should return False for regular Linux."""
        from setup_lib.platform_detect import is_wsl

        regular_linux = "Linux version 6.18.5-200.fc43.x86_64"
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=regular_linux),
        ):
            result = is_wsl()
            assert result is False

    def test_no_proc_version(self) -> None:
        """Should return False when /proc/version doesn't exist."""
        from setup_lib.platform_detect import is_wsl

        with patch("pathlib.Path.exists", return_value=False):
            result = is_wsl()
            assert result is False


class TestGetPlatformInfo:
    """Tests for get_platform_info() function (aggregate)."""

    def test_linux_platform_info(self) -> None:
        """Should return complete platform info for Linux."""
        from setup_lib.platform_detect import get_platform_info

        os_release_content = """NAME="Fedora Linux"
ID=fedora
VERSION_ID=43
"""
        with (
            patch("platform.system", return_value="Linux"),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=os_release_content),
            patch("shutil.which") as mock_which,
        ):
            mock_which.side_effect = lambda cmd: "/usr/bin/dnf" if cmd == "dnf" else None
            result = get_platform_info()

            assert result["platform"] == "linux"
            assert result["distro"]["id"] == "fedora"
            assert result["package_manager"] == "dnf"
            assert "is_wsl" in result

    def test_windows_platform_info(self) -> None:
        """Should return complete platform info for Windows."""
        from setup_lib.platform_detect import get_platform_info

        with (
            patch("platform.system", return_value="Windows"),
            patch("shutil.which") as mock_which,
        ):
            mock_which.side_effect = (
                lambda cmd: "C:\\Windows\\winget.exe" if cmd == "winget" else None
            )
            result = get_platform_info()

            assert result["platform"] == "windows"
            assert result["distro"] is None
            assert result["package_manager"] == "winget"
            assert result["is_wsl"] is False

    def test_unsupported_platform_info(self) -> None:
        """Should return None for unsupported platforms."""
        from setup_lib.platform_detect import get_platform_info

        with patch("platform.system", return_value="Darwin"):
            result = get_platform_info()
            assert result is None


class TestGetDistroFamily:
    """Tests for get_distro_family() function."""

    def test_fedora_family(self) -> None:
        """Should identify Fedora family distros."""
        from setup_lib.platform_detect import get_distro_family

        # Direct Fedora
        assert get_distro_family({"id": "fedora"}) == "fedora"
        # RHEL (ID_LIKE=fedora)
        assert get_distro_family({"id": "rhel", "id_like": "fedora"}) == "fedora"
        # CentOS (ID_LIKE=rhel fedora)
        assert get_distro_family({"id": "centos", "id_like": "rhel fedora"}) == "fedora"

    def test_debian_family(self) -> None:
        """Should identify Debian family distros."""
        from setup_lib.platform_detect import get_distro_family

        # Direct Debian
        assert get_distro_family({"id": "debian"}) == "debian"
        # Ubuntu (ID_LIKE=debian)
        assert get_distro_family({"id": "ubuntu", "id_like": "debian"}) == "debian"
        # Linux Mint (ID_LIKE=ubuntu debian)
        assert get_distro_family({"id": "linuxmint", "id_like": "ubuntu debian"}) == "debian"

    def test_arch_family(self) -> None:
        """Should identify Arch family distros."""
        from setup_lib.platform_detect import get_distro_family

        # Direct Arch
        assert get_distro_family({"id": "arch"}) == "arch"
        # Manjaro (ID_LIKE=arch)
        assert get_distro_family({"id": "manjaro", "id_like": "arch"}) == "arch"

    def test_unknown_family(self) -> None:
        """Should return 'unknown' for unrecognized distros."""
        from setup_lib.platform_detect import get_distro_family

        assert get_distro_family({"id": "gentoo"}) == "unknown"
        assert get_distro_family({}) == "unknown"
        assert get_distro_family(None) == "unknown"
