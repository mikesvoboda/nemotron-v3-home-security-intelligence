"""Unit tests for setup_lib.linux_optimizer module.

Tests Linux AI workstation optimization functions including sysctl settings,
NVIDIA driver configuration, user limits, and kernel parameters.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestIsLinux:
    """Tests for is_linux() function."""

    def test_returns_true_on_linux(self) -> None:
        """Should return True when platform is Linux."""
        from setup_lib.linux_optimizer import is_linux

        with patch("platform.system", return_value="Linux"):
            assert is_linux() is True

    def test_returns_false_on_windows(self) -> None:
        """Should return False when platform is Windows."""
        from setup_lib.linux_optimizer import is_linux

        with patch("platform.system", return_value="Windows"):
            assert is_linux() is False

    def test_returns_false_on_macos(self) -> None:
        """Should return False when platform is Darwin (macOS)."""
        from setup_lib.linux_optimizer import is_linux

        with patch("platform.system", return_value="Darwin"):
            assert is_linux() is False


class TestIsRoot:
    """Tests for is_root() function."""

    def test_returns_true_when_root(self) -> None:
        """Should return True when running as root (euid=0)."""
        from setup_lib.linux_optimizer import is_root

        with patch("os.geteuid", return_value=0):
            assert is_root() is True

    def test_returns_false_when_not_root(self) -> None:
        """Should return False when not running as root."""
        from setup_lib.linux_optimizer import is_root

        with patch("os.geteuid", return_value=1000):
            assert is_root() is False


class TestWriteConfigFile:
    """Tests for write_config_file() function."""

    def test_writes_new_file_successfully(self, tmp_path: Path) -> None:
        """Should write new config file when it doesn't exist."""
        from setup_lib.linux_optimizer import write_config_file

        config_path = tmp_path / "test.conf"
        content = "test content"

        def mock_sudo(args: list[str], **kwargs):
            # Simulate sudo commands - actually perform the operations for testing
            if args[0] == "cp" and len(args) == 3:
                # cp source dest
                Path(args[1]).replace(Path(args[2]))
            elif args[0] == "mkdir":
                # mkdir -p path
                Path(args[2]).mkdir(parents=True, exist_ok=True)
            elif args[0] == "chmod":
                # chmod mode path
                pass  # Don't actually chmod in tests
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        with patch("setup_lib.linux_optimizer._run_sudo", side_effect=mock_sudo):
            success, modified = write_config_file(config_path, content)

            assert success is True
            assert modified is True
            assert config_path.read_text() == content

    def test_idempotent_when_content_unchanged(self, tmp_path: Path) -> None:
        """Should not modify file when content is identical."""
        from setup_lib.linux_optimizer import write_config_file

        config_path = tmp_path / "test.conf"
        content = "test content"
        config_path.write_text(content)

        success, modified = write_config_file(config_path, content)

        assert success is True
        assert modified is False

    def test_updates_file_when_content_different(self, tmp_path: Path) -> None:
        """Should update file when content differs."""
        from setup_lib.linux_optimizer import write_config_file

        config_path = tmp_path / "test.conf"
        config_path.write_text("old content")
        new_content = "new content"

        def mock_sudo(args: list[str], **kwargs):
            # Simulate sudo commands - actually perform the operations for testing
            if args[0] == "cp" and len(args) == 3:
                # cp source dest
                Path(args[1]).replace(Path(args[2]))
            elif args[0] == "mkdir":
                # mkdir -p path
                Path(args[2]).mkdir(parents=True, exist_ok=True)
            elif args[0] == "chmod":
                # chmod mode path
                pass  # Don't actually chmod in tests
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        with patch("setup_lib.linux_optimizer._run_sudo", side_effect=mock_sudo):
            success, modified = write_config_file(config_path, new_content)

            assert success is True
            assert modified is True
            assert config_path.read_text() == new_content

    def test_backs_up_existing_file(self, tmp_path: Path) -> None:
        """Should backup existing file when backup_dir is provided."""
        from setup_lib.linux_optimizer import write_config_file

        config_path = tmp_path / "test.conf"
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()
        old_content = "old content"
        config_path.write_text(old_content)

        def mock_sudo(args: list[str], **kwargs):
            # Simulate sudo commands - actually perform the operations for testing
            if args[0] == "cp" and len(args) == 3:
                # cp source dest
                Path(args[1]).replace(Path(args[2]))
            elif args[0] == "mkdir":
                # mkdir -p path
                Path(args[2]).mkdir(parents=True, exist_ok=True)
            elif args[0] == "chmod":
                # chmod mode path
                pass  # Don't actually chmod in tests
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        with patch("setup_lib.linux_optimizer._run_sudo", side_effect=mock_sudo):
            success, modified = write_config_file(config_path, "new content", backup_dir)

            assert success is True
            assert modified is True
            backup_path = backup_dir / "test.conf"
            assert backup_path.exists()
            assert backup_path.read_text() == old_content

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Should create parent directories if they don't exist."""
        from setup_lib.linux_optimizer import write_config_file

        config_path = tmp_path / "subdir" / "nested" / "test.conf"
        content = "test content"

        def mock_sudo(args: list[str], **kwargs):
            # Simulate sudo commands - actually perform the operations for testing
            if args[0] == "cp" and len(args) == 3:
                # cp source dest
                Path(args[1]).replace(Path(args[2]))
            elif args[0] == "mkdir":
                # mkdir -p path
                Path(args[2]).mkdir(parents=True, exist_ok=True)
            elif args[0] == "chmod":
                # chmod mode path
                pass  # Don't actually chmod in tests
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        with patch("setup_lib.linux_optimizer._run_sudo", side_effect=mock_sudo):
            success, modified = write_config_file(config_path, content)

            assert success is True
            assert modified is True
            assert config_path.read_text() == content

    def test_handles_permission_error(self) -> None:
        """Should handle permission error when sudo cp fails."""
        from setup_lib.linux_optimizer import write_config_file

        def mock_sudo_fail(args: list[str], **kwargs):
            if args[0] == "cp" and len(args) == 3 and args[2] == "/etc/test.conf":
                return subprocess.CompletedProcess(
                    args=args, returncode=1, stdout="", stderr="Permission denied"
                )
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        with patch("setup_lib.linux_optimizer._run_sudo", side_effect=mock_sudo_fail):
            success, modified = write_config_file(Path("/etc/test.conf"), "content")

            assert success is False
            assert modified is False

    def test_handles_os_error_on_write(self, tmp_path: Path) -> None:
        """Should handle OS error when tempfile creation fails."""
        from setup_lib.linux_optimizer import write_config_file

        config_path = tmp_path / "test.conf"

        with patch("tempfile.NamedTemporaryFile", side_effect=OSError("Disk full")):
            success, modified = write_config_file(config_path, "content")

            assert success is False
            assert modified is False


class TestRunCommand:
    """Tests for run_command() function."""

    def test_successful_command_returns_output(self) -> None:
        """Should return success and output for successful command."""
        from setup_lib.linux_optimizer import run_command

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="test output", returncode=0)

            success, output = run_command(["echo", "test"])

            assert success is True
            assert output == "test output"

    def test_failed_command_returns_error(self) -> None:
        """Should return failure and error message for failed command."""
        from setup_lib.linux_optimizer import run_command

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1, cmd=["test"], stderr="error message"
            )

            success, output = run_command(["test", "command"], check=True, verbose=False)

            assert success is False
            assert "error message" in output

    def test_command_not_found(self) -> None:
        """Should handle command not found error."""
        from setup_lib.linux_optimizer import run_command

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            success, output = run_command(["nonexistent"], verbose=False)

            assert success is False
            assert "Command not found" in output

    def test_verbose_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Should print command when verbose is True."""
        from setup_lib.linux_optimizer import run_command

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)

            run_command(["echo", "test"], verbose=True)

            captured = capsys.readouterr()
            assert "echo test" in captured.out

    def test_quiet_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Should not print command when verbose is False."""
        from setup_lib.linux_optimizer import run_command

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)

            run_command(["echo", "test"], verbose=False)

            captured = capsys.readouterr()
            assert "echo test" not in captured.out


class TestApplyNetworkOptimizations:
    """Tests for apply_network_optimizations() function."""

    def test_creates_network_config(self, tmp_path: Path) -> None:
        """Should create network sysctl config file."""
        from setup_lib.linux_optimizer import (
            SYSCTL_NETWORK_CONFIG,
            apply_network_optimizations,
        )

        with patch(
            "setup_lib.linux_optimizer.write_config_file",
            return_value=(True, True),
        ) as mock_write:
            result = apply_network_optimizations(tmp_path)

            assert result.success is True
            assert "configured" in result.message
            mock_write.assert_called_once()
            call_args = mock_write.call_args[0]
            assert call_args[0] == Path("/etc/sysctl.d/90-ai-network.conf")
            assert call_args[1] == SYSCTL_NETWORK_CONFIG

    def test_reports_already_applied(self, tmp_path: Path) -> None:
        """Should report when config already applied."""
        from setup_lib.linux_optimizer import apply_network_optimizations

        with patch(
            "setup_lib.linux_optimizer.write_config_file",
            return_value=(True, False),
        ):
            result = apply_network_optimizations(tmp_path)

            assert result.success is True
            assert "already applied" in result.message

    def test_reports_failure(self, tmp_path: Path) -> None:
        """Should report failure when write fails."""
        from setup_lib.linux_optimizer import apply_network_optimizations

        with patch(
            "setup_lib.linux_optimizer.write_config_file",
            return_value=(False, False),
        ):
            result = apply_network_optimizations(tmp_path)

            assert result.success is False
            assert "Failed" in result.message


class TestApplyMemoryOptimizations:
    """Tests for apply_memory_optimizations() function."""

    def test_creates_memory_config(self, tmp_path: Path) -> None:
        """Should create memory sysctl config file."""
        from setup_lib.linux_optimizer import (
            SYSCTL_MEMORY_CONFIG,
            apply_memory_optimizations,
        )

        with patch(
            "setup_lib.linux_optimizer.write_config_file",
            return_value=(True, True),
        ) as mock_write:
            result = apply_memory_optimizations(tmp_path)

            assert result.success is True
            assert "configured" in result.message
            mock_write.assert_called_once()
            call_args = mock_write.call_args[0]
            assert call_args[0] == Path("/etc/sysctl.d/90-ai-memory.conf")
            assert call_args[1] == SYSCTL_MEMORY_CONFIG

    def test_reports_already_applied(self, tmp_path: Path) -> None:
        """Should report when config already applied."""
        from setup_lib.linux_optimizer import apply_memory_optimizations

        with patch(
            "setup_lib.linux_optimizer.write_config_file",
            return_value=(True, False),
        ):
            result = apply_memory_optimizations(tmp_path)

            assert result.success is True
            assert "already applied" in result.message

    def test_reports_failure(self, tmp_path: Path) -> None:
        """Should report failure when write fails."""
        from setup_lib.linux_optimizer import apply_memory_optimizations

        with patch(
            "setup_lib.linux_optimizer.write_config_file",
            return_value=(False, False),
        ):
            result = apply_memory_optimizations(tmp_path)

            assert result.success is False
            assert "Failed" in result.message


class TestApplySysctlChanges:
    """Tests for apply_sysctl_changes() function."""

    def test_applies_sysctl_successfully(self) -> None:
        """Should run sysctl --system successfully."""
        from setup_lib.linux_optimizer import apply_sysctl_changes

        with patch(
            "setup_lib.linux_optimizer.run_command",
            return_value=(True, "output"),
        ) as mock_run:
            result = apply_sysctl_changes()

            assert result.success is True
            assert "applied" in result.message
            mock_run.assert_called_once_with(["sysctl", "--system"], check=False)

    def test_reports_failure(self) -> None:
        """Should report failure when sysctl fails."""
        from setup_lib.linux_optimizer import apply_sysctl_changes

        with patch(
            "setup_lib.linux_optimizer.run_command",
            return_value=(False, "error"),
        ):
            result = apply_sysctl_changes()

            assert result.success is False
            assert "Failed" in result.message


class TestApplyNvidiaOptimizations:
    """Tests for apply_nvidia_optimizations() function."""

    def test_creates_nvidia_config_and_enables_persistence(self, tmp_path: Path) -> None:
        """Should create NVIDIA config and enable persistence daemon."""
        from setup_lib.linux_optimizer import apply_nvidia_optimizations

        with (
            patch(
                "setup_lib.linux_optimizer.write_config_file",
                return_value=(True, True),
            ),
            patch("setup_lib.linux_optimizer.run_command") as mock_run,
            patch("shutil.which", return_value="/usr/bin/nvidia-smi"),
        ):
            mock_run.return_value = (True, "enabled")

            result = apply_nvidia_optimizations(tmp_path)

            assert result.success is True
            assert result.requires_reboot is True

    def test_enables_persistence_daemon_when_not_enabled(self, tmp_path: Path) -> None:
        """Should enable nvidia-persistenced when not already enabled."""
        from setup_lib.linux_optimizer import apply_nvidia_optimizations

        with (
            patch(
                "setup_lib.linux_optimizer.write_config_file",
                return_value=(True, True),
            ),
            patch("setup_lib.linux_optimizer.run_command") as mock_run,
            patch("shutil.which", return_value="/usr/bin/nvidia-smi"),
        ):
            # First call: is-enabled returns "disabled", then enable succeeds
            mock_run.side_effect = [
                (False, "disabled"),  # is-enabled
                (True, ""),  # enable
                (True, ""),  # start
                (True, ""),  # nvidia-smi -pm 1
            ]

            result = apply_nvidia_optimizations(tmp_path)

            assert result.success is True
            # Verify enable was called
            calls = mock_run.call_args_list
            assert any("enable" in str(c) for c in calls)

    def test_skips_persistence_when_already_enabled(self, tmp_path: Path) -> None:
        """Should skip enabling persistence daemon when already enabled."""
        from setup_lib.linux_optimizer import apply_nvidia_optimizations

        with (
            patch(
                "setup_lib.linux_optimizer.write_config_file",
                return_value=(True, True),
            ),
            patch("setup_lib.linux_optimizer.run_command") as mock_run,
            patch("shutil.which", return_value="/usr/bin/nvidia-smi"),
        ):
            # is-enabled returns "enabled", so no enable call needed
            mock_run.side_effect = [
                (True, "enabled"),  # is-enabled
                (True, ""),  # nvidia-smi -pm 1
            ]

            result = apply_nvidia_optimizations(tmp_path)

            assert result.success is True

    def test_handles_missing_nvidia_smi(self, tmp_path: Path) -> None:
        """Should handle missing nvidia-smi gracefully."""
        from setup_lib.linux_optimizer import apply_nvidia_optimizations

        with (
            patch(
                "setup_lib.linux_optimizer.write_config_file",
                return_value=(True, True),
            ),
            patch("setup_lib.linux_optimizer.run_command") as mock_run,
            patch("shutil.which", return_value=None),  # nvidia-smi not found
        ):
            mock_run.return_value = (True, "enabled")

            result = apply_nvidia_optimizations(tmp_path)

            assert result.success is True

    def test_reports_failure_on_write_error(self, tmp_path: Path) -> None:
        """Should report failure when config write fails."""
        from setup_lib.linux_optimizer import apply_nvidia_optimizations

        with patch(
            "setup_lib.linux_optimizer.write_config_file",
            return_value=(False, False),
        ):
            result = apply_nvidia_optimizations(tmp_path)

            assert result.success is False
            assert result.requires_reboot is True

    def test_no_reboot_when_config_unchanged(self, tmp_path: Path) -> None:
        """Should not require reboot when config is unchanged."""
        from setup_lib.linux_optimizer import apply_nvidia_optimizations

        with (
            patch(
                "setup_lib.linux_optimizer.write_config_file",
                return_value=(True, False),  # Success but not modified
            ),
            patch("setup_lib.linux_optimizer.run_command") as mock_run,
            patch("shutil.which", return_value="/usr/bin/nvidia-smi"),
        ):
            mock_run.return_value = (True, "enabled")

            result = apply_nvidia_optimizations(tmp_path)

            assert result.success is True
            assert result.requires_reboot is False


class TestUpdateGrubParameters:
    """Tests for _update_grub_parameters() function."""

    def test_updates_grub_with_new_params(self, tmp_path: Path) -> None:
        """Should add new kernel parameters to GRUB config."""
        from setup_lib.linux_optimizer import _update_grub_parameters

        grub_path = Path("/etc/default/grub")
        grub_content = 'GRUB_CMDLINE_LINUX="quiet splash"\n'
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=grub_content),
            patch("setup_lib.linux_optimizer.run_command") as mock_run,
            patch("setup_lib.linux_optimizer._run_sudo") as mock_sudo,
            patch("shutil.copy2"),
        ):
            mock_sudo.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            mock_run.return_value = (True, "")

            result = _update_grub_parameters(backup_dir, {"iommu": "pt"})

            assert result.success is True
            assert result.requires_reboot is True
            assert mock_sudo.called
            assert "iommu=pt" in result.message

    def test_skips_existing_params(self, tmp_path: Path) -> None:
        """Should not add parameters that already exist."""
        from setup_lib.linux_optimizer import _update_grub_parameters

        grub_content = 'GRUB_CMDLINE_LINUX="quiet splash iommu=pt"\n'
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=grub_content),
        ):
            result = _update_grub_parameters(backup_dir, {"iommu": "pt"})

            assert result.success is True
            assert result.requires_reboot is False
            assert "already present" in result.message

    def test_handles_missing_grub_config(self, tmp_path: Path) -> None:
        """Should report failure when GRUB config doesn't exist."""
        from setup_lib.linux_optimizer import _update_grub_parameters

        with patch.object(Path, "exists", return_value=False):
            result = _update_grub_parameters(tmp_path, {"iommu": "pt"})

            assert result.success is False
            assert "not found" in result.message

    def test_handles_invalid_grub_format(self, tmp_path: Path) -> None:
        """Should report failure when GRUB config is malformed."""
        from setup_lib.linux_optimizer import _update_grub_parameters

        grub_content = "# Invalid GRUB config without CMDLINE_LINUX\n"
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=grub_content),
            patch("shutil.copy2"),
        ):
            result = _update_grub_parameters(backup_dir, {"iommu": "pt"})

            assert result.success is False
            assert "Could not parse" in result.message

    def test_regenerates_grub_config_efi(self, tmp_path: Path) -> None:
        """Should regenerate GRUB config for EFI systems."""
        from setup_lib.linux_optimizer import _update_grub_parameters

        grub_content = 'GRUB_CMDLINE_LINUX="quiet"\n'
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=grub_content),
            patch.object(Path, "is_dir", return_value=True),  # /sys/firmware/efi exists
            patch("setup_lib.linux_optimizer.run_command") as mock_run,
            patch("setup_lib.linux_optimizer._run_sudo") as mock_sudo,
            patch("shutil.copy2"),
        ):
            mock_sudo.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            mock_run.return_value = (True, "")

            result = _update_grub_parameters(backup_dir, {"iommu": "pt"})

            assert result.success is True
            # Should use EFI grub path
            mock_run.assert_called()
            call_args = mock_run.call_args[0][0]
            assert "grub2-mkconfig" in call_args

    def test_handles_grub_regeneration_failure(self, tmp_path: Path) -> None:
        """Should report failure when GRUB regeneration fails."""
        from setup_lib.linux_optimizer import _update_grub_parameters

        grub_content = 'GRUB_CMDLINE_LINUX="quiet"\n'
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=grub_content),
            patch.object(Path, "write_text"),
            patch.object(Path, "is_dir", return_value=False),
            patch("setup_lib.linux_optimizer.run_command") as mock_run,
            patch("setup_lib.linux_optimizer._run_sudo") as mock_sudo,
            patch("shutil.copy2"),
        ):
            mock_sudo.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            mock_run.return_value = (False, "grub2-mkconfig failed")

            result = _update_grub_parameters(backup_dir, {"iommu": "pt"})

            assert result.success is False
            assert "Failed to regenerate" in result.message


class TestApplyKernelParameters:
    """Tests for apply_kernel_parameters() function."""

    def test_applies_safe_kernel_params(self, tmp_path: Path) -> None:
        """Should apply safe kernel parameters without mitigations=off."""
        from setup_lib.linux_optimizer import apply_kernel_parameters

        grub_content = 'GRUB_CMDLINE_LINUX="quiet"\n'

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=grub_content),
            patch.object(Path, "is_dir", return_value=False),
            patch("setup_lib.linux_optimizer.run_command") as mock_run,
            patch("setup_lib.linux_optimizer._run_sudo") as mock_sudo,
            patch("shutil.copy2"),
        ):
            mock_sudo.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            mock_run.return_value = (True, "")

            result = apply_kernel_parameters(tmp_path)

            assert result.success is True
            # Verify _run_sudo was called with cp command
            assert mock_sudo.called
            # Verify the temp file contained the right parameters by checking the result message
            assert "iommu=pt" in result.message
            assert "init_on_alloc=0" in result.message
            assert "transparent_hugepage=madvise" in result.message
            # Should NOT include mitigations=off (that's separate)
            assert "mitigations=off" not in result.message


class TestApplyDisableMitigations:
    """Tests for apply_disable_mitigations() function."""

    def test_disables_cpu_mitigations(self, tmp_path: Path) -> None:
        """Should add mitigations=off to kernel parameters."""
        from setup_lib.linux_optimizer import apply_disable_mitigations

        grub_content = 'GRUB_CMDLINE_LINUX="quiet"\n'

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=grub_content),
            patch.object(Path, "is_dir", return_value=False),
            patch("setup_lib.linux_optimizer.run_command") as mock_run,
            patch("setup_lib.linux_optimizer._run_sudo") as mock_sudo,
            patch("shutil.copy2"),
        ):
            mock_sudo.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            mock_run.return_value = (True, "")

            result = apply_disable_mitigations(tmp_path)

            assert result.success is True
            assert result.requires_reboot is True
            # Verify _run_sudo was called with cp command
            assert mock_sudo.called
            # Verify the result message contains mitigations=off
            assert "mitigations=off" in result.message


class TestDisableUnnecessaryServices:
    """Tests for disable_unnecessary_services() function."""

    def test_disables_services(self) -> None:
        """Should disable unnecessary services."""
        from setup_lib.linux_optimizer import disable_unnecessary_services

        with patch("setup_lib.linux_optimizer.run_command") as mock_run:
            # First call is is-enabled (returns "enabled"), then disable, then stop
            mock_run.side_effect = [
                (True, "enabled"),  # is-enabled bluetooth
                (True, ""),  # disable bluetooth
                (True, ""),  # stop bluetooth
                (True, "enabled"),  # is-enabled cups
                (True, ""),  # disable cups
                (True, ""),  # stop cups
                (True, "enabled"),  # is-enabled cups-browsed
                (True, ""),  # disable cups-browsed
                (True, ""),  # stop cups-browsed
                (True, "enabled"),  # is-enabled avahi-daemon
                (True, ""),  # disable avahi-daemon
                (True, ""),  # stop avahi-daemon
                (True, "enabled"),  # is-enabled ModemManager
                (True, ""),  # disable ModemManager
                (True, ""),  # stop ModemManager
            ]

            result = disable_unnecessary_services()

            assert result.success is True
            assert "Disabled" in result.message

    def test_skips_already_disabled_services(self) -> None:
        """Should skip services that are already disabled."""
        from setup_lib.linux_optimizer import disable_unnecessary_services

        with patch("setup_lib.linux_optimizer.run_command") as mock_run:
            mock_run.return_value = (True, "disabled")

            result = disable_unnecessary_services()

            assert result.success is True
            assert "already disabled" in result.message

    def test_handles_missing_services(self) -> None:
        """Should handle services that don't exist."""
        from setup_lib.linux_optimizer import disable_unnecessary_services

        with patch("setup_lib.linux_optimizer.run_command") as mock_run:
            mock_run.return_value = (False, "not-found")

            result = disable_unnecessary_services()

            assert result.success is True


class TestApplyUserLimits:
    """Tests for apply_user_limits() function."""

    def test_creates_limits_config(self, tmp_path: Path) -> None:
        """Should create user limits config file."""
        from setup_lib.linux_optimizer import LIMITS_CONFIG, apply_user_limits

        with patch(
            "setup_lib.linux_optimizer.write_config_file",
            return_value=(True, True),
        ) as mock_write:
            result = apply_user_limits(tmp_path)

            assert result.success is True
            assert "configured" in result.message
            mock_write.assert_called_once()
            call_args = mock_write.call_args[0]
            assert call_args[0] == Path("/etc/security/limits.d/90-ai-workstation.conf")
            assert call_args[1] == LIMITS_CONFIG

    def test_reports_failure(self, tmp_path: Path) -> None:
        """Should report failure when write fails."""
        from setup_lib.linux_optimizer import apply_user_limits

        with patch(
            "setup_lib.linux_optimizer.write_config_file",
            return_value=(False, False),
        ):
            result = apply_user_limits(tmp_path)

            assert result.success is False


class TestApplyAiEnvironment:
    """Tests for apply_ai_environment() function."""

    def test_creates_environment_script(self, tmp_path: Path) -> None:
        """Should create AI environment script."""
        from setup_lib.linux_optimizer import AI_ENV_SCRIPT, apply_ai_environment

        with (
            patch(
                "setup_lib.linux_optimizer.write_config_file",
                return_value=(True, True),
            ) as mock_write,
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "chmod"),
        ):
            result = apply_ai_environment(tmp_path)

            assert result.success is True
            assert "configured" in result.message
            mock_write.assert_called_once()
            call_args = mock_write.call_args[0]
            assert call_args[0] == Path("/etc/profile.d/ai-workstation.sh")
            assert call_args[1] == AI_ENV_SCRIPT

    def test_makes_script_executable(self, tmp_path: Path) -> None:
        """Should make environment script executable."""
        from setup_lib.linux_optimizer import apply_ai_environment

        with (
            patch(
                "setup_lib.linux_optimizer.write_config_file",
                return_value=(True, True),
            ),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "chmod") as mock_chmod,
            patch(
                "setup_lib.linux_optimizer._run_sudo",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ) as mock_sudo,
        ):
            apply_ai_environment(tmp_path)

            # chmod is called via _run_sudo, not directly
            mock_chmod.assert_not_called()
            # Verify _run_sudo was called with chmod
            sudo_calls = [str(call) for call in mock_sudo.call_args_list]
            assert any("chmod" in call for call in sudo_calls)


class TestInstallVerificationScript:
    """Tests for install_verification_script() function."""

    def test_installs_script(self) -> None:
        """Should install verification script."""
        from setup_lib.linux_optimizer import install_verification_script

        with (
            patch.object(Path, "exists", return_value=False),
            patch.object(Path, "write_text"),
            patch.object(Path, "chmod") as mock_chmod,
            patch(
                "setup_lib.linux_optimizer._run_sudo",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ),
        ):
            result = install_verification_script()

            assert result.success is True
            assert "installed" in result.message
            mock_chmod.assert_not_called()  # chmod is called via _run_sudo, not directly

    def test_skips_if_already_installed(self) -> None:
        """Should skip if script already installed with same content."""
        from setup_lib.linux_optimizer import VERIFY_SCRIPT, install_verification_script

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "read_text", return_value=VERIFY_SCRIPT):
                result = install_verification_script()

                assert result.success is True
                assert "already installed" in result.message

    def test_handles_permission_error(self) -> None:
        """Should handle permission error when sudo cp fails."""
        from setup_lib.linux_optimizer import install_verification_script

        with (
            patch.object(Path, "exists", return_value=False),
            patch(
                "setup_lib.linux_optimizer._run_sudo",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="", stderr="Permission denied"
                ),
            ),
        ):
            result = install_verification_script()

            assert result.success is False


class TestRunOptimizations:
    """Tests for run_optimizations() function."""

    def test_requires_linux(self) -> None:
        """Should fail on non-Linux platforms."""
        from setup_lib.linux_optimizer import run_optimizations

        with patch("setup_lib.linux_optimizer.is_linux", return_value=False):
            success, requires_reboot = run_optimizations()

            assert success is False
            assert requires_reboot is False

    def test_uses_sudo_when_not_root(self) -> None:
        """Should proceed with sudo when not running as root."""
        from setup_lib.linux_optimizer import run_optimizations

        with (
            patch("setup_lib.linux_optimizer.is_linux", return_value=True),
            patch("setup_lib.linux_optimizer.is_root", return_value=False),
            # Mock all phase functions to avoid actual sudo calls
            patch("setup_lib.linux_optimizer.OPTIMIZATION_PHASES", []),
            patch("setup_lib.linux_optimizer.apply_sysctl_changes"),
            patch("setup_lib.linux_optimizer.install_verification_script"),
        ):
            success, requires_reboot = run_optimizations(dry_run=True)

            assert success is True

    def test_dry_run_shows_phases(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Should show phases without applying in dry run mode."""
        from setup_lib.linux_optimizer import run_optimizations

        with (
            patch("setup_lib.linux_optimizer.is_linux", return_value=True),
            patch("setup_lib.linux_optimizer.is_root", return_value=True),
        ):
            success, requires_reboot = run_optimizations(dry_run=True)

            assert success is True
            captured = capsys.readouterr()
            assert "DRY RUN" in captured.out

    def test_runs_specified_phases_only_dry_run(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Should only show specified phases in dry run mode."""
        from setup_lib.linux_optimizer import run_optimizations

        with (
            patch("setup_lib.linux_optimizer.is_linux", return_value=True),
            patch("setup_lib.linux_optimizer.is_root", return_value=True),
        ):
            success, requires_reboot = run_optimizations(phases=["network"], dry_run=True)

            assert success is True
            captured = capsys.readouterr()
            assert "DRY RUN" in captured.out
            # Should mention network phase
            assert "network" in captured.out.lower()

    def test_includes_mitigations_when_requested_dry_run(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Should include mitigations phase in dry run when explicitly requested."""
        from setup_lib.linux_optimizer import run_optimizations

        with (
            patch("setup_lib.linux_optimizer.is_linux", return_value=True),
            patch("setup_lib.linux_optimizer.is_root", return_value=True),
        ):
            success, requires_reboot = run_optimizations(include_mitigations=True, dry_run=True)

            assert success is True
            captured = capsys.readouterr()
            assert "DRY RUN" in captured.out
            # Should mention mitigations phase
            assert "mitigations" in captured.out.lower()

    def test_phases_with_reboot_flag(self) -> None:
        """Should detect phases that require reboot."""
        from setup_lib.linux_optimizer import MITIGATIONS_PHASE, OPTIMIZATION_PHASES

        # Check that nvidia and kernel phases would require reboot when modified
        nvidia_phase = next(p for p in OPTIMIZATION_PHASES if p.name == "nvidia")
        kernel_phase = next(p for p in OPTIMIZATION_PHASES if p.name == "kernel")
        assert nvidia_phase is not None
        assert kernel_phase is not None

        # Mitigations phase is separate and requires reboot
        assert MITIGATIONS_PHASE.name == "mitigations"


class TestPromptAndRunOptimizations:
    """Tests for prompt_and_run_optimizations() function."""

    def test_skips_on_non_linux(self) -> None:
        """Should skip silently on non-Linux platforms."""
        from setup_lib.linux_optimizer import prompt_and_run_optimizations

        with patch("setup_lib.linux_optimizer.is_linux", return_value=False):
            result = prompt_and_run_optimizations()

            assert result is True

    def test_user_declines_optimizations(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Should skip when user declines."""
        from setup_lib.linux_optimizer import prompt_and_run_optimizations

        with (
            patch("setup_lib.linux_optimizer.is_linux", return_value=True),
            patch("builtins.input", return_value="n"),
        ):
            result = prompt_and_run_optimizations()

            assert result is True
            captured = capsys.readouterr()
            assert "Skipping" in captured.out

    def test_user_accepts_optimizations_no_root_uses_sudo(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Should proceed with sudo when user accepts but not root."""
        from setup_lib.linux_optimizer import prompt_and_run_optimizations

        with (
            patch("setup_lib.linux_optimizer.is_linux", return_value=True),
            patch("setup_lib.linux_optimizer.is_root", return_value=False),
            # First input: "y" for optimizations, second: "n" for mitigations
            patch("builtins.input", side_effect=["y", "n"]),
            patch("setup_lib.linux_optimizer.run_optimizations", return_value=(True, False)),
        ):
            result = prompt_and_run_optimizations()

            assert result is True
            captured = capsys.readouterr()
            assert "sudo" in captured.out

    def test_handles_eof_on_main_prompt(self) -> None:
        """Should handle EOF gracefully on main prompt."""
        from setup_lib.linux_optimizer import prompt_and_run_optimizations

        with (
            patch("setup_lib.linux_optimizer.is_linux", return_value=True),
            patch("builtins.input", side_effect=EOFError()),
        ):
            result = prompt_and_run_optimizations()

            assert result is True

    def test_handles_keyboard_interrupt_on_main_prompt(self) -> None:
        """Should handle keyboard interrupt gracefully on main prompt."""
        from setup_lib.linux_optimizer import prompt_and_run_optimizations

        with (
            patch("setup_lib.linux_optimizer.is_linux", return_value=True),
            patch("builtins.input", side_effect=KeyboardInterrupt()),
        ):
            result = prompt_and_run_optimizations()

            assert result is True

    def test_user_accepts_with_mitigations(self) -> None:
        """Should run with mitigations disabled when user accepts both prompts."""
        from setup_lib.linux_optimizer import prompt_and_run_optimizations

        with (
            patch("setup_lib.linux_optimizer.is_linux", return_value=True),
            patch("setup_lib.linux_optimizer.is_root", return_value=True),
            patch("builtins.input", side_effect=["y", "y", "n"]),  # accept, mitigations, no reboot
            patch(
                "setup_lib.linux_optimizer.run_optimizations",
                return_value=(True, True),
            ) as mock_run,
        ):
            result = prompt_and_run_optimizations()

            assert result is True
            mock_run.assert_called_once_with(include_mitigations=True)

    def test_user_declines_mitigations(self) -> None:
        """Should run without mitigations when user declines second prompt."""
        from setup_lib.linux_optimizer import prompt_and_run_optimizations

        with (
            patch("setup_lib.linux_optimizer.is_linux", return_value=True),
            patch("setup_lib.linux_optimizer.is_root", return_value=True),
            patch("builtins.input", side_effect=["y", "n"]),  # accept, no mitigations
            patch(
                "setup_lib.linux_optimizer.run_optimizations",
                return_value=(True, False),
            ) as mock_run,
        ):
            result = prompt_and_run_optimizations()

            assert result is True
            mock_run.assert_called_once_with(include_mitigations=False)

    def test_handles_eof_on_mitigations_prompt(self) -> None:
        """Should handle EOF on mitigations prompt."""
        from setup_lib.linux_optimizer import prompt_and_run_optimizations

        with (
            patch("setup_lib.linux_optimizer.is_linux", return_value=True),
            patch("setup_lib.linux_optimizer.is_root", return_value=True),
            patch("builtins.input", side_effect=["y", EOFError()]),
            patch(
                "setup_lib.linux_optimizer.run_optimizations",
                return_value=(True, False),
            ) as mock_run,
        ):
            result = prompt_and_run_optimizations()

            assert result is True
            mock_run.assert_called_once_with(include_mitigations=False)

    def test_prompts_for_reboot_when_required(self) -> None:
        """Should prompt for reboot when changes require it."""
        from setup_lib.linux_optimizer import prompt_and_run_optimizations

        with (
            patch("setup_lib.linux_optimizer.is_linux", return_value=True),
            patch("setup_lib.linux_optimizer.is_root", return_value=True),
            patch("builtins.input", side_effect=["y", "n", "y"]),  # accept, no mitigations, reboot
            patch(
                "setup_lib.linux_optimizer.run_optimizations",
                return_value=(True, True),  # requires reboot
            ),
            patch("setup_lib.linux_optimizer.run_command") as mock_reboot,
        ):
            mock_reboot.return_value = (True, "")

            result = prompt_and_run_optimizations()

            assert result is True
            mock_reboot.assert_called_once_with(["reboot"])

    def test_handles_eof_on_reboot_prompt(self) -> None:
        """Should handle EOF on reboot prompt."""
        from setup_lib.linux_optimizer import prompt_and_run_optimizations

        with (
            patch("setup_lib.linux_optimizer.is_linux", return_value=True),
            patch("setup_lib.linux_optimizer.is_root", return_value=True),
            patch("builtins.input", side_effect=["y", "n", EOFError()]),
            patch(
                "setup_lib.linux_optimizer.run_optimizations",
                return_value=(True, True),
            ),
            patch("setup_lib.linux_optimizer.run_command") as mock_reboot,
        ):
            result = prompt_and_run_optimizations()

            assert result is True
            mock_reboot.assert_not_called()


class TestOptimizationPhases:
    """Tests for OPTIMIZATION_PHASES configuration."""

    def test_phases_defined(self) -> None:
        """Should have all expected optimization phases defined."""
        from setup_lib.linux_optimizer import OPTIMIZATION_PHASES

        phase_names = [p.name for p in OPTIMIZATION_PHASES]
        assert "network" in phase_names
        assert "memory" in phase_names
        assert "nvidia" in phase_names
        assert "kernel" in phase_names
        assert "services" in phase_names
        assert "limits" in phase_names
        assert "environment" in phase_names

    def test_mitigations_phase_separate(self) -> None:
        """Should have mitigations phase separate from default phases."""
        from setup_lib.linux_optimizer import MITIGATIONS_PHASE, OPTIMIZATION_PHASES

        phase_names = [p.name for p in OPTIMIZATION_PHASES]
        assert "mitigations" not in phase_names
        assert MITIGATIONS_PHASE.name == "mitigations"


class TestGetPhaseDescriptions:
    """Tests for get_phase_descriptions() function."""

    def test_returns_all_phases(self) -> None:
        """Should return descriptions for all phases."""
        from setup_lib.linux_optimizer import OPTIMIZATION_PHASES, get_phase_descriptions

        descriptions = get_phase_descriptions()

        assert len(descriptions) == len(OPTIMIZATION_PHASES)
        for name, desc in descriptions:
            assert isinstance(name, str)
            assert isinstance(desc, str)
            assert len(name) > 0
            assert len(desc) > 0


class TestOptimizationResult:
    """Tests for OptimizationResult dataclass."""

    def test_default_values(self) -> None:
        """Should have sensible defaults."""
        from setup_lib.linux_optimizer import OptimizationResult

        result = OptimizationResult(success=True, message="Test")

        assert result.success is True
        assert result.message == "Test"
        assert result.requires_reboot is False

    def test_reboot_flag(self) -> None:
        """Should accept requires_reboot flag."""
        from setup_lib.linux_optimizer import OptimizationResult

        result = OptimizationResult(success=True, message="Test", requires_reboot=True)

        assert result.requires_reboot is True


class TestConfigurationContent:
    """Tests for configuration content constants."""

    def test_sysctl_network_config_has_required_settings(self) -> None:
        """Should have required network buffer settings."""
        from setup_lib.linux_optimizer import SYSCTL_NETWORK_CONFIG

        assert "net.core.rmem_max" in SYSCTL_NETWORK_CONFIG
        assert "net.core.wmem_max" in SYSCTL_NETWORK_CONFIG
        assert "268435456" in SYSCTL_NETWORK_CONFIG  # 256MB
        assert "bbr" in SYSCTL_NETWORK_CONFIG  # congestion control

    def test_sysctl_memory_config_has_required_settings(self) -> None:
        """Should have required memory settings."""
        from setup_lib.linux_optimizer import SYSCTL_MEMORY_CONFIG

        assert "kernel.numa_balancing" in SYSCTL_MEMORY_CONFIG
        assert "vm.swappiness" in SYSCTL_MEMORY_CONFIG
        assert "vm.max_map_count" in SYSCTL_MEMORY_CONFIG
        assert "2097152" in SYSCTL_MEMORY_CONFIG  # max_map_count value

    def test_nvidia_config_has_required_options(self) -> None:
        """Should have required NVIDIA driver options."""
        from setup_lib.linux_optimizer import NVIDIA_MODPROBE_CONFIG

        assert "NVreg_EnablePCIERelaxedOrderingMode" in NVIDIA_MODPROBE_CONFIG
        assert "NVreg_PreserveVideoMemoryAllocations" in NVIDIA_MODPROBE_CONFIG
        assert "NVreg_DynamicPowerManagement" in NVIDIA_MODPROBE_CONFIG

    def test_limits_config_has_required_settings(self) -> None:
        """Should have required user limits settings."""
        from setup_lib.linux_optimizer import LIMITS_CONFIG

        assert "memlock" in LIMITS_CONFIG
        assert "unlimited" in LIMITS_CONFIG
        assert "nofile" in LIMITS_CONFIG
        assert "nproc" in LIMITS_CONFIG

    def test_ai_env_script_has_required_exports(self) -> None:
        """Should have required environment variable exports."""
        from setup_lib.linux_optimizer import AI_ENV_SCRIPT

        assert "CUDA_DEVICE_ORDER" in AI_ENV_SCRIPT
        assert "PYTORCH_CUDA_ALLOC_CONF" in AI_ENV_SCRIPT
        assert "OMP_NUM_THREADS" in AI_ENV_SCRIPT
        assert "NCCL_P2P_DISABLE" in AI_ENV_SCRIPT

    def test_verify_script_checks_all_components(self) -> None:
        """Should check all optimization components."""
        from setup_lib.linux_optimizer import VERIFY_SCRIPT

        assert "Kernel Parameters" in VERIFY_SCRIPT
        assert "Network Buffers" in VERIFY_SCRIPT
        assert "Memory Settings" in VERIFY_SCRIPT
        assert "NVIDIA Settings" in VERIFY_SCRIPT
        assert "CPU Governor" in VERIFY_SCRIPT
        assert "Vulnerability Mitigations" in VERIFY_SCRIPT


class TestLogFunctions:
    """Tests for logging helper functions."""

    def test_log_info_prints_green(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Should print info message in green."""
        from setup_lib.linux_optimizer import GREEN, NC, log_info

        log_info("Test message")

        captured = capsys.readouterr()
        assert GREEN in captured.out
        assert NC in captured.out
        assert "[INFO]" in captured.out
        assert "Test message" in captured.out

    def test_log_warn_prints_yellow(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Should print warning message in yellow."""
        from setup_lib.linux_optimizer import NC, YELLOW, log_warn

        log_warn("Test warning")

        captured = capsys.readouterr()
        assert YELLOW in captured.out
        assert NC in captured.out
        assert "[WARN]" in captured.out
        assert "Test warning" in captured.out

    def test_log_error_prints_red(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Should print error message in red."""
        from setup_lib.linux_optimizer import NC, RED, log_error

        log_error("Test error")

        captured = capsys.readouterr()
        assert RED in captured.out
        assert NC in captured.out
        assert "[ERROR]" in captured.out
        assert "Test error" in captured.out
