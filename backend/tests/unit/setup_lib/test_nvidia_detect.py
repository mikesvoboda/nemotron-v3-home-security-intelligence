"""Unit tests for setup_lib.nvidia_detect module.

Tests NVIDIA GPU detection, driver version checks, and installation
command generation for various Linux distributions.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestIsNvidiaGpuPresent:
    """Tests for is_nvidia_gpu_present() function."""

    def test_gpu_present_nvidia_smi_exists(self) -> None:
        """Should return True when nvidia-smi exists and runs successfully."""
        from setup_lib.nvidia_detect import is_nvidia_gpu_present

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = is_nvidia_gpu_present()
            assert result is True
            mock_run.assert_called_once()
            # Verify we're checking nvidia-smi
            call_args = mock_run.call_args
            assert "nvidia-smi" in call_args[0][0]

    def test_gpu_not_present_nvidia_smi_fails(self) -> None:
        """Should return False when nvidia-smi fails."""
        from setup_lib.nvidia_detect import is_nvidia_gpu_present

        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = is_nvidia_gpu_present()
            assert result is False

    def test_gpu_not_present_nvidia_smi_not_found(self) -> None:
        """Should return False when nvidia-smi is not installed."""
        from setup_lib.nvidia_detect import is_nvidia_gpu_present

        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = is_nvidia_gpu_present()
            assert result is False

    def test_gpu_not_present_permission_error(self) -> None:
        """Should return False on permission errors."""
        from setup_lib.nvidia_detect import is_nvidia_gpu_present

        with patch("subprocess.run", side_effect=PermissionError):
            result = is_nvidia_gpu_present()
            assert result is False


class TestGetGpuInfo:
    """Tests for get_gpu_info() function."""

    def test_get_single_gpu_info(self) -> None:
        """Should parse single GPU info from nvidia-smi."""
        from setup_lib.nvidia_detect import get_gpu_info

        # nvidia-smi output for GPU name
        name_output = "NVIDIA GeForce RTX 4090\n"
        # nvidia-smi output for VRAM
        memory_output = "24564\n"

        def mock_run_side_effect(cmd: list[str], **kwargs: object) -> MagicMock:
            mock_result = MagicMock()
            mock_result.returncode = 0
            if "gpu_name" in cmd[0] if isinstance(cmd, str) else "gpu_name" in " ".join(cmd):
                mock_result.stdout = name_output
            elif (
                "memory.total" in cmd[0]
                if isinstance(cmd, str)
                else "memory.total" in " ".join(cmd)
            ):
                mock_result.stdout = memory_output
            return mock_result

        with patch("subprocess.run", side_effect=mock_run_side_effect):
            result = get_gpu_info()
            assert result is not None
            assert len(result) == 1
            assert result[0]["name"] == "NVIDIA GeForce RTX 4090"
            assert result[0]["vram_mb"] == 24564

    def test_get_multiple_gpu_info(self) -> None:
        """Should parse multiple GPU info from nvidia-smi."""
        from setup_lib.nvidia_detect import get_gpu_info

        # nvidia-smi output for multiple GPUs
        name_output = "NVIDIA GeForce RTX 4090\nNVIDIA GeForce RTX 3080\n"
        memory_output = "24564\n10240\n"

        def mock_run_side_effect(cmd: list[str], **kwargs: object) -> MagicMock:
            mock_result = MagicMock()
            mock_result.returncode = 0
            cmd_str = cmd[0] if isinstance(cmd, str) else " ".join(cmd)
            if "gpu_name" in cmd_str:
                mock_result.stdout = name_output
            elif "memory.total" in cmd_str:
                mock_result.stdout = memory_output
            return mock_result

        with patch("subprocess.run", side_effect=mock_run_side_effect):
            result = get_gpu_info()
            assert result is not None
            assert len(result) == 2
            assert result[0]["name"] == "NVIDIA GeForce RTX 4090"
            assert result[0]["vram_mb"] == 24564
            assert result[1]["name"] == "NVIDIA GeForce RTX 3080"
            assert result[1]["vram_mb"] == 10240

    def test_get_gpu_info_nvidia_smi_fails(self) -> None:
        """Should return None when nvidia-smi fails."""
        from setup_lib.nvidia_detect import get_gpu_info

        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = get_gpu_info()
            assert result is None

    def test_get_gpu_info_no_nvidia_smi(self) -> None:
        """Should return None when nvidia-smi is not installed."""
        from setup_lib.nvidia_detect import get_gpu_info

        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = get_gpu_info()
            assert result is None

    def test_get_gpu_info_strips_whitespace(self) -> None:
        """Should strip whitespace from GPU names."""
        from setup_lib.nvidia_detect import get_gpu_info

        name_output = "  NVIDIA GeForce RTX 4090  \n"
        memory_output = "24564\n"

        def mock_run_side_effect(cmd: list[str], **kwargs: object) -> MagicMock:
            mock_result = MagicMock()
            mock_result.returncode = 0
            cmd_str = cmd[0] if isinstance(cmd, str) else " ".join(cmd)
            if "gpu_name" in cmd_str:
                mock_result.stdout = name_output
            elif "memory.total" in cmd_str:
                mock_result.stdout = memory_output
            return mock_result

        with patch("subprocess.run", side_effect=mock_run_side_effect):
            result = get_gpu_info()
            assert result is not None
            assert result[0]["name"] == "NVIDIA GeForce RTX 4090"


class TestGetDriverVersion:
    """Tests for get_driver_version() function."""

    def test_get_driver_version_success(self) -> None:
        """Should return driver version from nvidia-smi."""
        from setup_lib.nvidia_detect import get_driver_version

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "560.35.03\n"

        with patch("subprocess.run", return_value=mock_result):
            result = get_driver_version()
            assert result == "560.35.03"

    def test_get_driver_version_strips_whitespace(self) -> None:
        """Should strip whitespace from driver version."""
        from setup_lib.nvidia_detect import get_driver_version

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "  535.183.01  \n"

        with patch("subprocess.run", return_value=mock_result):
            result = get_driver_version()
            assert result == "535.183.01"

    def test_get_driver_version_nvidia_smi_fails(self) -> None:
        """Should return None when nvidia-smi fails."""
        from setup_lib.nvidia_detect import get_driver_version

        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = get_driver_version()
            assert result is None

    def test_get_driver_version_no_nvidia_smi(self) -> None:
        """Should return None when nvidia-smi is not installed."""
        from setup_lib.nvidia_detect import get_driver_version

        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = get_driver_version()
            assert result is None

    def test_get_driver_version_uses_correct_command(self) -> None:
        """Should use the correct nvidia-smi query command."""
        from setup_lib.nvidia_detect import get_driver_version

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "560.35.03\n"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            get_driver_version()
            call_args = mock_run.call_args
            cmd = call_args[0][0]
            assert "nvidia-smi" in cmd
            assert "--query-gpu=driver_version" in cmd
            assert "--format=csv,noheader" in cmd


class TestIsDriverVersionSufficient:
    """Tests for is_driver_version_sufficient() function."""

    def test_driver_version_sufficient_exact(self) -> None:
        """Should return True when driver version equals minimum."""
        from setup_lib.nvidia_detect import is_driver_version_sufficient

        assert is_driver_version_sufficient("535.0") is True
        assert is_driver_version_sufficient("535.0.0") is True
        assert is_driver_version_sufficient("535.00.00") is True

    def test_driver_version_sufficient_above(self) -> None:
        """Should return True when driver version is above minimum."""
        from setup_lib.nvidia_detect import is_driver_version_sufficient

        assert is_driver_version_sufficient("560.35.03") is True
        assert is_driver_version_sufficient("545.29.06") is True
        assert is_driver_version_sufficient("536.0") is True

    def test_driver_version_insufficient_below(self) -> None:
        """Should return False when driver version is below minimum."""
        from setup_lib.nvidia_detect import is_driver_version_sufficient

        assert is_driver_version_sufficient("530.41.03") is False
        assert is_driver_version_sufficient("525.147.05") is False
        assert is_driver_version_sufficient("470.256.02") is False
        assert is_driver_version_sufficient("450.0") is False

    def test_driver_version_invalid_format(self) -> None:
        """Should return False for invalid version formats."""
        from setup_lib.nvidia_detect import is_driver_version_sufficient

        assert is_driver_version_sufficient("") is False
        assert is_driver_version_sufficient("invalid") is False
        assert is_driver_version_sufficient("abc.def.ghi") is False

    def test_driver_version_none(self) -> None:
        """Should return False when version is None."""
        from setup_lib.nvidia_detect import is_driver_version_sufficient

        assert is_driver_version_sufficient(None) is False  # type: ignore[arg-type]

    def test_driver_version_custom_minimum(self) -> None:
        """Should compare against custom minimum when provided."""
        from setup_lib.nvidia_detect import is_driver_version_sufficient

        # Default minimum is 535
        assert is_driver_version_sufficient("530.0", minimum_major=525) is True
        assert is_driver_version_sufficient("524.99.99", minimum_major=525) is False


class TestGetDriverInstallCommand:
    """Tests for get_driver_install_command() function."""

    def test_fedora_install_command(self) -> None:
        """Should return correct command for Fedora."""
        from setup_lib.nvidia_detect import get_driver_install_command

        result = get_driver_install_command("fedora")
        assert result is not None
        assert "dnf" in result
        assert "akmod-nvidia" in result

    def test_debian_install_command(self) -> None:
        """Should return correct command for Debian family."""
        from setup_lib.nvidia_detect import get_driver_install_command

        result = get_driver_install_command("debian")
        assert result is not None
        assert "apt" in result
        assert "nvidia-driver" in result

    def test_ubuntu_specific_command(self) -> None:
        """Should return Ubuntu-specific command when specified."""
        from setup_lib.nvidia_detect import get_driver_install_command

        # Ubuntu can use ubuntu-drivers or apt
        result = get_driver_install_command("debian", is_ubuntu=True)
        assert result is not None
        # Either ubuntu-drivers or apt is acceptable
        assert "ubuntu-drivers" in result or "apt" in result

    def test_arch_install_command(self) -> None:
        """Should return correct command for Arch family."""
        from setup_lib.nvidia_detect import get_driver_install_command

        result = get_driver_install_command("arch")
        assert result is not None
        assert "pacman" in result
        assert "nvidia" in result

    def test_unknown_distro_returns_none(self) -> None:
        """Should return None for unknown distribution family."""
        from setup_lib.nvidia_detect import get_driver_install_command

        result = get_driver_install_command("unknown")
        assert result is None

    def test_empty_distro_returns_none(self) -> None:
        """Should return None for empty distribution family."""
        from setup_lib.nvidia_detect import get_driver_install_command

        result = get_driver_install_command("")
        assert result is None


class TestIsContainerToolkitInstalled:
    """Tests for is_container_toolkit_installed() function."""

    def test_toolkit_installed_nvidia_ctk_exists(self) -> None:
        """Should return True when nvidia-ctk is found."""
        from setup_lib.nvidia_detect import is_container_toolkit_installed

        with patch("shutil.which", return_value="/usr/bin/nvidia-ctk"):
            result = is_container_toolkit_installed()
            assert result is True

    def test_toolkit_not_installed(self) -> None:
        """Should return False when nvidia-ctk is not found."""
        from setup_lib.nvidia_detect import is_container_toolkit_installed

        with patch("shutil.which", return_value=None):
            result = is_container_toolkit_installed()
            assert result is False

    def test_toolkit_checks_nvidia_ctk(self) -> None:
        """Should check for nvidia-ctk specifically."""
        from setup_lib.nvidia_detect import is_container_toolkit_installed

        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/nvidia-ctk"
            is_container_toolkit_installed()
            mock_which.assert_called_with("nvidia-ctk")


class TestGetToolkitInstallCommand:
    """Tests for get_toolkit_install_command() function."""

    def test_fedora_toolkit_command(self) -> None:
        """Should return correct toolkit command for Fedora."""
        from setup_lib.nvidia_detect import get_toolkit_install_command

        result = get_toolkit_install_command("fedora")
        assert result is not None
        assert "dnf" in result
        assert "nvidia-container-toolkit" in result

    def test_debian_toolkit_command(self) -> None:
        """Should return correct toolkit command for Debian family."""
        from setup_lib.nvidia_detect import get_toolkit_install_command

        result = get_toolkit_install_command("debian")
        assert result is not None
        assert "apt" in result
        assert "nvidia-container-toolkit" in result

    def test_arch_toolkit_command(self) -> None:
        """Should return correct toolkit command for Arch family."""
        from setup_lib.nvidia_detect import get_toolkit_install_command

        result = get_toolkit_install_command("arch")
        assert result is not None
        assert "pacman" in result
        assert "nvidia-container-toolkit" in result

    def test_unknown_distro_toolkit_returns_none(self) -> None:
        """Should return None for unknown distribution family."""
        from setup_lib.nvidia_detect import get_toolkit_install_command

        result = get_toolkit_install_command("unknown")
        assert result is None


class TestPromptAndCheckNvidia:
    """Tests for prompt_and_check_nvidia() function."""

    def test_prompt_returns_valid_config(self) -> None:
        """Should return valid config dict with GPU info."""
        from setup_lib.nvidia_detect import prompt_and_check_nvidia

        mock_gpu_info = [{"name": "NVIDIA GeForce RTX 4090", "vram_mb": 24564}]

        with (
            patch("setup_lib.nvidia_detect.is_nvidia_gpu_present", return_value=True),
            patch("setup_lib.nvidia_detect.get_gpu_info", return_value=mock_gpu_info),
            patch("setup_lib.nvidia_detect.get_driver_version", return_value="560.35.03"),
            patch("setup_lib.nvidia_detect.is_driver_version_sufficient", return_value=True),
            patch("setup_lib.nvidia_detect.is_container_toolkit_installed", return_value=True),
            patch("builtins.print"),  # Suppress output
        ):
            config: dict[str, object] = {}
            result = prompt_and_check_nvidia(config)

            assert result is True
            assert config.get("gpu_detected") is True
            assert config.get("gpu_name") == "NVIDIA GeForce RTX 4090"
            assert config.get("gpu_vram_mb") == 24564
            assert config.get("driver_version") == "560.35.03"

    def test_prompt_no_gpu_detected(self) -> None:
        """Should handle no GPU detected gracefully."""
        from setup_lib.nvidia_detect import prompt_and_check_nvidia

        with (
            patch("setup_lib.nvidia_detect.is_nvidia_gpu_present", return_value=False),
            patch("builtins.print"),  # Suppress output
        ):
            config: dict[str, object] = {}
            result = prompt_and_check_nvidia(config)

            assert result is False
            assert config.get("gpu_detected") is False

    def test_prompt_driver_needs_upgrade(self) -> None:
        """Should indicate when driver needs upgrade."""
        from setup_lib.nvidia_detect import prompt_and_check_nvidia

        mock_gpu_info = [{"name": "NVIDIA GeForce RTX 3080", "vram_mb": 10240}]

        with (
            patch("setup_lib.nvidia_detect.is_nvidia_gpu_present", return_value=True),
            patch("setup_lib.nvidia_detect.get_gpu_info", return_value=mock_gpu_info),
            patch("setup_lib.nvidia_detect.get_driver_version", return_value="470.256.02"),
            patch("setup_lib.nvidia_detect.is_driver_version_sufficient", return_value=False),
            patch("builtins.print"),  # Suppress output
        ):
            config: dict[str, object] = {}
            result = prompt_and_check_nvidia(config)

            # Returns True (GPU exists) but marks driver as needing upgrade
            assert config.get("gpu_detected") is True
            assert config.get("driver_needs_upgrade") is True

    def test_prompt_toolkit_not_installed(self) -> None:
        """Should indicate when container toolkit needs installation."""
        from setup_lib.nvidia_detect import prompt_and_check_nvidia

        mock_gpu_info = [{"name": "NVIDIA GeForce RTX 4090", "vram_mb": 24564}]

        with (
            patch("setup_lib.nvidia_detect.is_nvidia_gpu_present", return_value=True),
            patch("setup_lib.nvidia_detect.get_gpu_info", return_value=mock_gpu_info),
            patch("setup_lib.nvidia_detect.get_driver_version", return_value="560.35.03"),
            patch("setup_lib.nvidia_detect.is_driver_version_sufficient", return_value=True),
            patch("setup_lib.nvidia_detect.is_container_toolkit_installed", return_value=False),
            patch("builtins.print"),  # Suppress output
        ):
            config: dict[str, object] = {}
            result = prompt_and_check_nvidia(config)

            assert config.get("gpu_detected") is True
            assert config.get("toolkit_installed") is False


class TestParseDriverVersion:
    """Tests for _parse_driver_version() helper function."""

    def test_parse_full_version(self) -> None:
        """Should parse full version string into tuple."""
        from setup_lib.nvidia_detect import _parse_driver_version

        result = _parse_driver_version("560.35.03")
        assert result == (560, 35, 3)

    def test_parse_two_part_version(self) -> None:
        """Should handle two-part version string."""
        from setup_lib.nvidia_detect import _parse_driver_version

        result = _parse_driver_version("560.35")
        assert result == (560, 35, 0)

    def test_parse_single_number(self) -> None:
        """Should handle single number version."""
        from setup_lib.nvidia_detect import _parse_driver_version

        result = _parse_driver_version("560")
        assert result == (560, 0, 0)

    def test_parse_invalid_version(self) -> None:
        """Should return None for invalid version."""
        from setup_lib.nvidia_detect import _parse_driver_version

        assert _parse_driver_version("invalid") is None
        assert _parse_driver_version("") is None
        assert _parse_driver_version("abc.def") is None

    def test_parse_version_with_leading_zeros(self) -> None:
        """Should handle version with leading zeros in minor/patch."""
        from setup_lib.nvidia_detect import _parse_driver_version

        result = _parse_driver_version("535.183.01")
        assert result == (535, 183, 1)


class TestMinimumDriverVersion:
    """Tests for MINIMUM_DRIVER_VERSION constant."""

    def test_minimum_version_is_535(self) -> None:
        """Minimum driver version should be 535 for CUDA 12.1 compatibility."""
        from setup_lib.nvidia_detect import MINIMUM_DRIVER_VERSION

        assert MINIMUM_DRIVER_VERSION == 535


class TestGetNvidiaDetectionSummary:
    """Tests for get_nvidia_detection_summary() function."""

    def test_summary_with_gpu(self) -> None:
        """Should return comprehensive summary when GPU detected."""
        from setup_lib.nvidia_detect import get_nvidia_detection_summary

        mock_gpu_info = [{"name": "NVIDIA GeForce RTX 4090", "vram_mb": 24564}]

        with (
            patch("setup_lib.nvidia_detect.is_nvidia_gpu_present", return_value=True),
            patch("setup_lib.nvidia_detect.get_gpu_info", return_value=mock_gpu_info),
            patch("setup_lib.nvidia_detect.get_driver_version", return_value="560.35.03"),
            patch("setup_lib.nvidia_detect.is_driver_version_sufficient", return_value=True),
            patch("setup_lib.nvidia_detect.is_container_toolkit_installed", return_value=True),
        ):
            result = get_nvidia_detection_summary()

            assert result["gpu_present"] is True
            assert result["gpus"] == mock_gpu_info
            assert result["driver_version"] == "560.35.03"
            assert result["driver_sufficient"] is True
            assert result["toolkit_installed"] is True

    def test_summary_without_gpu(self) -> None:
        """Should return minimal summary when no GPU detected."""
        from setup_lib.nvidia_detect import get_nvidia_detection_summary

        with patch("setup_lib.nvidia_detect.is_nvidia_gpu_present", return_value=False):
            result = get_nvidia_detection_summary()

            assert result["gpu_present"] is False
            assert result["gpus"] is None
            assert result["driver_version"] is None
            assert result["driver_sufficient"] is False
            assert result["toolkit_installed"] is False
