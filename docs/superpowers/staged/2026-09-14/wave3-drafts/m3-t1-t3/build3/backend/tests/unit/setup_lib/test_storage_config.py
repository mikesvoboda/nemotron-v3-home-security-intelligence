"""Unit tests for setup_lib.storage_config module.

Tests storage path validation, disk space checking, and directory creation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestCheckPathExists:
    """Tests for check_path_exists() function."""

    def test_existing_directory(self, tmp_path: Path) -> None:
        """Should return True for existing directory."""
        from setup_lib.storage_config import check_path_exists

        assert check_path_exists(str(tmp_path)) is True

    def test_existing_file(self, tmp_path: Path) -> None:
        """Should return True for existing file."""
        from setup_lib.storage_config import check_path_exists

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        assert check_path_exists(str(test_file)) is True

    def test_nonexistent_path(self) -> None:
        """Should return False for nonexistent path."""
        from setup_lib.storage_config import check_path_exists

        assert check_path_exists("/nonexistent/path/12345") is False


class TestCheckPathWritable:
    """Tests for check_path_writable() function."""

    def test_writable_directory(self, tmp_path: Path) -> None:
        """Should return True for writable directory."""
        from setup_lib.storage_config import check_path_writable

        assert check_path_writable(str(tmp_path)) is True

    def test_nonexistent_with_writable_parent(self, tmp_path: Path) -> None:
        """Should return True if parent is writable."""
        from setup_lib.storage_config import check_path_writable

        new_dir = tmp_path / "new_subdir"
        assert check_path_writable(str(new_dir)) is True

    def test_deeply_nested_nonexistent(self, tmp_path: Path) -> None:
        """Should check ancestor writability for deep paths."""
        from setup_lib.storage_config import check_path_writable

        deep_path = tmp_path / "a" / "b" / "c" / "d"
        assert check_path_writable(str(deep_path)) is True


class TestCreateDirectory:
    """Tests for create_directory() function."""

    def test_create_simple_directory(self, tmp_path: Path) -> None:
        """Should create a simple directory."""
        from setup_lib.storage_config import create_directory

        new_dir = tmp_path / "new_dir"
        assert create_directory(str(new_dir)) is True
        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_create_nested_directories(self, tmp_path: Path) -> None:
        """Should create nested directories."""
        from setup_lib.storage_config import create_directory

        nested = tmp_path / "a" / "b" / "c"
        assert create_directory(str(nested)) is True
        assert nested.exists()

    def test_idempotent_creation(self, tmp_path: Path) -> None:
        """Should succeed if directory already exists."""
        from setup_lib.storage_config import create_directory

        existing = tmp_path / "existing"
        existing.mkdir()
        assert create_directory(str(existing)) is True

    def test_permission_denied(self) -> None:
        """Should return False when mkdir raises PermissionError and sudo also fails."""
        from setup_lib.storage_config import create_directory

        mock_result = MagicMock()
        mock_result.returncode = 1  # sudo fails (e.g. no passwordless sudo)

        with (
            patch("pathlib.Path.mkdir", side_effect=PermissionError("denied")),
            patch("subprocess.run", return_value=mock_result),
        ):
            assert create_directory("/some/path") is False

    def test_permission_denied_sudo_success(self) -> None:
        """Should return True when mkdir raises PermissionError but sudo succeeds."""
        from setup_lib.storage_config import create_directory

        sudo_mkdir_result = MagicMock()
        sudo_mkdir_result.returncode = 0  # sudo mkdir succeeds

        sudo_chown_result = MagicMock()
        sudo_chown_result.returncode = 0

        with (
            patch("pathlib.Path.mkdir", side_effect=PermissionError("denied")),
            patch("subprocess.run", side_effect=[sudo_mkdir_result, sudo_chown_result]),
        ):
            assert create_directory("/some/path") is True


class TestGetFreeSpaceGb:
    """Tests for get_free_space_gb() function."""

    def test_existing_path(self, tmp_path: Path) -> None:
        """Should return free space for existing path."""
        from setup_lib.storage_config import get_free_space_gb

        free_gb = get_free_space_gb(str(tmp_path))
        assert free_gb > 0

    def test_nonexistent_path_uses_parent(self, tmp_path: Path) -> None:
        """Should check parent path if path doesn't exist."""
        from setup_lib.storage_config import get_free_space_gb

        nonexistent = tmp_path / "nonexistent"
        free_gb = get_free_space_gb(str(nonexistent))
        assert free_gb > 0

    def test_returns_zero_on_error(self) -> None:
        """Should return 0 on error."""
        from setup_lib.storage_config import get_free_space_gb

        with patch("shutil.disk_usage", side_effect=OSError("error")):
            assert get_free_space_gb("/") == 0.0

    def test_calculates_gb_correctly(self, tmp_path: Path) -> None:
        """Should convert bytes to GB correctly."""
        from setup_lib.storage_config import get_free_space_gb

        mock_usage = MagicMock()
        mock_usage.free = 100 * (1024**3)  # 100 GB in bytes

        with patch("shutil.disk_usage", return_value=mock_usage):
            free_gb = get_free_space_gb(str(tmp_path))
            assert free_gb == pytest.approx(100.0, rel=0.01)


class TestIsSsd:
    """Tests for is_ssd() function."""

    def test_ssd_detected(self, tmp_path: Path) -> None:
        """Should return True when ROTA=0 (non-rotational)."""
        from setup_lib.storage_config import is_ssd

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "0\n"

        with patch("subprocess.run", return_value=mock_result):
            assert is_ssd(str(tmp_path)) is True

    def test_hdd_detected(self, tmp_path: Path) -> None:
        """Should return False when ROTA=1 (rotational)."""
        from setup_lib.storage_config import is_ssd

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "1\n"

        with patch("subprocess.run", return_value=mock_result):
            assert is_ssd(str(tmp_path)) is False

    def test_lsblk_not_found(self, tmp_path: Path) -> None:
        """Should return None when lsblk not available."""
        from setup_lib.storage_config import is_ssd

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            assert is_ssd(str(tmp_path)) is None

    def test_lsblk_timeout(self, tmp_path: Path) -> None:
        """Should return None on timeout."""
        from setup_lib.storage_config import is_ssd

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 5)):
            assert is_ssd(str(tmp_path)) is None

    def test_lsblk_error(self, tmp_path: Path) -> None:
        """Should return None on lsblk error."""
        from setup_lib.storage_config import is_ssd

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            assert is_ssd(str(tmp_path)) is None

    def test_nonexistent_path(self) -> None:
        """Should return None for nonexistent path with no ancestor."""
        from setup_lib.storage_config import is_ssd

        # Mock Path to simulate no existing ancestor
        with patch("pathlib.Path.exists", return_value=False):
            result = is_ssd("/completely/fake/path")
            assert result is None


class TestValidateStoragePath:
    """Tests for validate_storage_path() function."""

    def test_valid_path_with_space(self, tmp_path: Path) -> None:
        """Should return valid for directory with sufficient space."""
        from setup_lib.storage_config import validate_storage_path

        mock_usage = MagicMock()
        mock_usage.free = 100 * (1024**3)  # 100 GB

        with patch("shutil.disk_usage", return_value=mock_usage):
            is_valid, message = validate_storage_path(str(tmp_path), 50, "Test path")
            assert is_valid is True
            assert "100.0 GB available" in message

    def test_nonexistent_path(self) -> None:
        """Should return invalid for nonexistent path."""
        from setup_lib.storage_config import validate_storage_path

        is_valid, message = validate_storage_path("/nonexistent/12345", 10, "Test")
        assert is_valid is False
        assert "does not exist" in message

    def test_insufficient_space(self, tmp_path: Path) -> None:
        """Should return invalid for insufficient space."""
        from setup_lib.storage_config import validate_storage_path

        mock_usage = MagicMock()
        mock_usage.free = 5 * (1024**3)  # 5 GB

        with patch("shutil.disk_usage", return_value=mock_usage):
            is_valid, message = validate_storage_path(str(tmp_path), 50, "Test")
            assert is_valid is False
            assert "Insufficient space" in message
            assert "50" in message

    def test_path_is_file(self, tmp_path: Path) -> None:
        """Should return invalid if path is a file."""
        from setup_lib.storage_config import validate_storage_path

        test_file = tmp_path / "file.txt"
        test_file.write_text("test")

        is_valid, message = validate_storage_path(str(test_file), 10, "Test")
        assert is_valid is False
        assert "not a directory" in message


class TestPromptAndConfigureStorage:
    """Tests for prompt_and_configure_storage() function."""

    def test_existing_directories(self, tmp_path: Path) -> None:
        """Should accept existing directories."""
        from setup_lib.storage_config import prompt_and_configure_storage

        foscam_dir = tmp_path / "foscam"
        ai_dir = tmp_path / "ai_models"
        foscam_dir.mkdir()
        ai_dir.mkdir()

        inputs = iter([str(foscam_dir), str(ai_dir)])

        with (
            patch("builtins.input", lambda _: next(inputs)),
            patch("builtins.print"),
        ):
            result = prompt_and_configure_storage({})
            assert result["foscam_base_path"] == str(foscam_dir)
            assert result["ai_models_path"] == str(ai_dir)

    def test_uses_defaults_on_empty_input(self) -> None:
        """Should use defaults when user presses Enter."""
        from setup_lib.storage_config import prompt_and_configure_storage

        inputs = iter(["", ""])

        with (
            patch("builtins.input", lambda _: next(inputs)),
            patch("builtins.print"),
            patch("setup_lib.storage_config.check_path_exists", return_value=True),
            patch("setup_lib.storage_config.get_free_space_gb", return_value=100.0),
        ):
            result = prompt_and_configure_storage({})
            assert result["foscam_base_path"] == "/export/foscam"
            assert result["ai_models_path"] == "/export/ai_models"

    def test_creates_directory_on_confirm(self, tmp_path: Path) -> None:
        """Should create directory when user confirms."""
        from setup_lib.storage_config import prompt_and_configure_storage

        new_foscam = tmp_path / "new_foscam"
        new_ai = tmp_path / "new_ai"

        inputs = iter([str(new_foscam), "y", str(new_ai), "y"])

        with (
            patch("builtins.input", lambda _: next(inputs)),
            patch("builtins.print"),
        ):
            result = prompt_and_configure_storage({})
            assert new_foscam.exists()
            assert new_ai.exists()

    def test_skips_creation_on_decline(self, tmp_path: Path) -> None:
        """Should not create directory when user declines."""
        from setup_lib.storage_config import prompt_and_configure_storage

        new_foscam = tmp_path / "new_foscam"
        new_ai = tmp_path / "new_ai"

        inputs = iter([str(new_foscam), "n", str(new_ai), "n"])

        with (
            patch("builtins.input", lambda _: next(inputs)),
            patch("builtins.print"),
        ):
            result = prompt_and_configure_storage({})
            assert not new_foscam.exists()
            assert not new_ai.exists()

    def test_warns_on_low_disk_space(self, tmp_path: Path) -> None:
        """Should warn when disk space is low."""
        from setup_lib.storage_config import prompt_and_configure_storage

        foscam_dir = tmp_path / "foscam"
        ai_dir = tmp_path / "ai_models"
        foscam_dir.mkdir()
        ai_dir.mkdir()

        inputs = iter([str(foscam_dir), str(ai_dir)])
        printed_lines: list[str] = []

        def mock_print(*args: object) -> None:
            printed_lines.append(" ".join(str(a) for a in args))

        mock_usage = MagicMock()
        mock_usage.free = 5 * (1024**3)  # 5 GB (low)

        with (
            patch("builtins.input", lambda _: next(inputs)),
            patch("builtins.print", mock_print),
            patch("shutil.disk_usage", return_value=mock_usage),
        ):
            prompt_and_configure_storage({})

        warning_found = any("Warning" in line or "Low disk space" in line for line in printed_lines)
        assert warning_found

    def test_shows_ssd_status(self, tmp_path: Path) -> None:
        """Should show SSD/HDD status for AI models path."""
        from setup_lib.storage_config import prompt_and_configure_storage

        ai_dir = tmp_path / "ai_models"
        ai_dir.mkdir()

        inputs = iter([str(tmp_path), str(ai_dir)])
        printed_lines: list[str] = []

        def mock_print(*args: object) -> None:
            printed_lines.append(" ".join(str(a) for a in args))

        with (
            patch("builtins.input", lambda _: next(inputs)),
            patch("builtins.print", mock_print),
            patch("setup_lib.storage_config.is_ssd", return_value=True),
        ):
            prompt_and_configure_storage({})

        ssd_found = any("SSD detected" in line for line in printed_lines)
        assert ssd_found

    def test_uses_config_defaults(self, tmp_path: Path) -> None:
        """Should use paths from config as defaults."""
        from setup_lib.storage_config import prompt_and_configure_storage

        custom_foscam = str(tmp_path / "custom_foscam")
        custom_ai = str(tmp_path / "custom_ai")

        inputs = iter(["", "y", "", "y"])

        with (
            patch("builtins.input", lambda _: next(inputs)),
            patch("builtins.print"),
        ):
            result = prompt_and_configure_storage(
                {
                    "foscam_base_path": custom_foscam,
                    "ai_models_path": custom_ai,
                }
            )
            assert result["foscam_base_path"] == custom_foscam
            assert result["ai_models_path"] == custom_ai


class TestConstants:
    """Tests for module constants."""

    def test_min_camera_space(self) -> None:
        """Should have reasonable minimum camera space."""
        from setup_lib.storage_config import MIN_CAMERA_SPACE_GB

        assert MIN_CAMERA_SPACE_GB >= 5
        assert MIN_CAMERA_SPACE_GB <= 100

    def test_min_ai_models_space(self) -> None:
        """Should have reasonable minimum AI models space."""
        from setup_lib.storage_config import MIN_AI_MODELS_SPACE_GB

        assert MIN_AI_MODELS_SPACE_GB >= 20
        assert MIN_AI_MODELS_SPACE_GB <= 200
