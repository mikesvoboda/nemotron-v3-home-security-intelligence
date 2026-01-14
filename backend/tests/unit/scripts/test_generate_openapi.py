"""Unit tests for OpenAPI generation script with smart caching (NEM-2587).

Tests cover:
- Timer class for performance measurement
- File hashing and change detection
- Cache file reading/writing
- Spec regeneration decision logic
- Main entry point behavior

Expected Performance:
- Skip path (no changes): ~50-200ms
- Regeneration path: ~1-3s
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from types import ModuleType


# =============================================================================
# Module Import Helper
# =============================================================================

# The script has a hyphen in its name, so we need to import it dynamically
_SCRIPT_PATH = Path(__file__).parent.parent.parent.parent.parent / "scripts" / "generate-openapi.py"


def _get_module() -> ModuleType:
    """Import the generate-openapi.py module dynamically.

    The module has a hyphen in its filename, so it cannot be imported
    directly using the standard import statement.
    """
    spec = importlib.util.spec_from_file_location("generate_openapi", _SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_openapi"] = module
    spec.loader.exec_module(module)
    return module


# Import module at module load time
_module = _get_module()


# =============================================================================
# Timer Tests
# =============================================================================


class TestTimer:
    """Tests for Timer class."""

    def test_timer_elapsed_ms_returns_zero_before_start(self) -> None:
        """Test that elapsed_ms returns 0 if timer hasn't started."""
        timer = _module.Timer()
        assert timer.elapsed_ms == 0.0

    def test_timer_measures_elapsed_time(self) -> None:
        """Test that timer measures elapsed time correctly."""
        import time

        timer = _module.Timer()
        timer.start()
        time.sleep(0.001)  # 1ms to ensure some time passes

        # Elapsed time should be positive
        elapsed = timer.elapsed_ms
        assert elapsed > 0

    def test_timer_stop_freezes_elapsed_time(self) -> None:
        """Test that stopping timer freezes the elapsed time."""
        import time

        timer = _module.Timer()
        timer.start()
        time.sleep(0.01)  # 10ms
        timer.stop()

        elapsed1 = timer.elapsed_ms
        time.sleep(0.01)  # 10ms more
        elapsed2 = timer.elapsed_ms

        # Both should be the same after stop
        assert elapsed1 == elapsed2
        assert elapsed1 >= 10  # At least 10ms

    def test_timer_checkpoint_records_times(self) -> None:
        """Test that checkpoints record intermediate times."""
        timer = _module.Timer()
        timer.start()
        timer.checkpoint("first")
        timer.checkpoint("second")
        timer.stop()

        report = timer.format_report()
        assert "first:" in report
        assert "second:" in report
        assert "Total:" in report

    def test_timer_checkpoint_before_start_is_ignored(self) -> None:
        """Test that checkpoints before start are safely ignored."""
        timer = _module.Timer()
        timer.checkpoint("ignored")  # Should not raise

        timer.start()
        timer.stop()

        report = timer.format_report()
        assert "ignored" not in report


# =============================================================================
# Hashing Tests
# =============================================================================


class TestFileHashing:
    """Tests for file hashing functions."""

    def test_hash_file_produces_sha256(self, tmp_path: Path) -> None:
        """Test that _hash_file produces a valid SHA256 hash."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        result = _module._hash_file(test_file)

        # SHA256 produces 64 hex characters
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

        # Verify it's the correct hash
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert result == expected

    def test_hash_file_different_content_different_hash(self, tmp_path: Path) -> None:
        """Test that different content produces different hashes."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content 1")
        file2.write_text("content 2")

        hash1 = _module._hash_file(file1)
        hash2 = _module._hash_file(file2)

        assert hash1 != hash2

    def test_hash_file_same_content_same_hash(self, tmp_path: Path) -> None:
        """Test that same content produces same hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        content = "same content"
        file1.write_text(content)
        file2.write_text(content)

        hash1 = _module._hash_file(file1)
        hash2 = _module._hash_file(file2)

        assert hash1 == hash2


class TestApiFileDiscovery:
    """Tests for API file discovery."""

    def test_get_api_files_finds_python_files(self, tmp_path: Path) -> None:
        """Test that _get_api_files finds Python files in API directories."""
        # Create mock API directory structure
        for dir_name in _module.API_DIRECTORIES[:1]:  # Just test first directory
            dir_path = tmp_path / dir_name
            dir_path.mkdir(parents=True)
            (dir_path / "routes.py").write_text("# routes")
            (dir_path / "schemas.py").write_text("# schemas")
            (dir_path / "README.md").write_text("# readme")  # Should be ignored

        files = _module._get_api_files(tmp_path)

        # Should find only .py files
        assert len(files) == 2
        assert all(f.suffix == ".py" for f in files)

    def test_get_api_files_returns_sorted_list(self, tmp_path: Path) -> None:
        """Test that _get_api_files returns files in sorted order."""
        # Create files in non-alphabetical order
        dir_path = tmp_path / _module.API_DIRECTORIES[0]
        dir_path.mkdir(parents=True)
        (dir_path / "z_last.py").write_text("")
        (dir_path / "a_first.py").write_text("")
        (dir_path / "m_middle.py").write_text("")

        files = _module._get_api_files(tmp_path)

        # Should be sorted
        assert files == sorted(files)

    def test_get_api_files_handles_missing_directories(self, tmp_path: Path) -> None:
        """Test that _get_api_files handles missing directories gracefully."""
        # Don't create any directories
        files = _module._get_api_files(tmp_path)

        assert files == []


class TestComputeApiHash:
    """Tests for compute_api_hash function."""

    def test_compute_api_hash_produces_sha256(self, tmp_path: Path) -> None:
        """Test that compute_api_hash produces valid SHA256."""
        # Create minimal structure
        dir_path = tmp_path / _module.API_DIRECTORIES[0]
        dir_path.mkdir(parents=True)
        (dir_path / "test.py").write_text("test content")

        result = _module.compute_api_hash(tmp_path)

        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_compute_api_hash_changes_with_content(self, tmp_path: Path) -> None:
        """Test that hash changes when file content changes."""
        dir_path = tmp_path / _module.API_DIRECTORIES[0]
        dir_path.mkdir(parents=True)
        test_file = dir_path / "test.py"

        test_file.write_text("original content")
        hash1 = _module.compute_api_hash(tmp_path)

        test_file.write_text("modified content")
        hash2 = _module.compute_api_hash(tmp_path)

        assert hash1 != hash2

    def test_compute_api_hash_changes_with_new_file(self, tmp_path: Path) -> None:
        """Test that hash changes when a new file is added."""
        dir_path = tmp_path / _module.API_DIRECTORIES[0]
        dir_path.mkdir(parents=True)
        (dir_path / "existing.py").write_text("existing")

        hash1 = _module.compute_api_hash(tmp_path)

        (dir_path / "new_file.py").write_text("new content")
        hash2 = _module.compute_api_hash(tmp_path)

        assert hash1 != hash2

    def test_compute_api_hash_includes_file_path(self, tmp_path: Path) -> None:
        """Test that hash includes file path (detects renames)."""
        dir_path = tmp_path / _module.API_DIRECTORIES[0]
        dir_path.mkdir(parents=True)

        # Create file with name "a.py"
        (dir_path / "a.py").write_text("content")
        hash1 = _module.compute_api_hash(tmp_path)

        # Remove and create with different name but same content
        (dir_path / "a.py").unlink()
        (dir_path / "b.py").write_text("content")
        hash2 = _module.compute_api_hash(tmp_path)

        # Hash should be different because file path is included
        assert hash1 != hash2


# =============================================================================
# Cache Tests
# =============================================================================


class TestCacheOperations:
    """Tests for cache reading and writing."""

    def test_read_cached_hash_returns_none_when_missing(self, tmp_path: Path) -> None:
        """Test that read_cached_hash returns None when cache doesn't exist."""
        result = _module.read_cached_hash(tmp_path)
        assert result is None

    def test_read_cached_hash_returns_valid_hash(self, tmp_path: Path) -> None:
        """Test that read_cached_hash returns valid hash from cache."""
        valid_hash = "a" * 64
        cache_path = tmp_path / _module.CACHE_FILE
        cache_path.write_text(valid_hash + "\n")

        result = _module.read_cached_hash(tmp_path)
        assert result == valid_hash

    def test_read_cached_hash_rejects_invalid_hash(self, tmp_path: Path) -> None:
        """Test that read_cached_hash rejects invalid hash values."""
        cache_path = tmp_path / _module.CACHE_FILE

        # Too short
        cache_path.write_text("abc\n")
        assert _module.read_cached_hash(tmp_path) is None

        # Invalid characters
        cache_path.write_text("g" * 64 + "\n")  # 'g' is not hex
        assert _module.read_cached_hash(tmp_path) is None

        # Too long
        cache_path.write_text("a" * 100 + "\n")
        assert _module.read_cached_hash(tmp_path) is None

    def test_write_cached_hash_creates_file(self, tmp_path: Path) -> None:
        """Test that write_cached_hash creates cache file."""
        test_hash = "b" * 64
        _module.write_cached_hash(tmp_path, test_hash)

        cache_path = tmp_path / _module.CACHE_FILE
        assert cache_path.exists()
        assert cache_path.read_text().strip() == test_hash

    def test_write_cached_hash_overwrites_existing(self, tmp_path: Path) -> None:
        """Test that write_cached_hash overwrites existing cache."""
        cache_path = tmp_path / _module.CACHE_FILE
        cache_path.write_text("old_value\n")

        new_hash = "c" * 64
        _module.write_cached_hash(tmp_path, new_hash)

        assert cache_path.read_text().strip() == new_hash


# =============================================================================
# Regeneration Decision Tests
# =============================================================================


class TestSpecNeedsRegeneration:
    """Tests for spec_needs_regeneration function."""

    def test_needs_regeneration_when_no_cache(self, tmp_path: Path) -> None:
        """Test that regeneration is needed when no cache exists."""
        # Create minimal API structure
        dir_path = tmp_path / _module.API_DIRECTORIES[0]
        dir_path.mkdir(parents=True)
        (dir_path / "test.py").write_text("test")

        needs_regen, reason = _module.spec_needs_regeneration(tmp_path)

        assert needs_regen is True
        assert "No cached hash" in reason

    def test_needs_regeneration_when_files_changed(self, tmp_path: Path) -> None:
        """Test that regeneration is needed when API files changed."""
        # Create API structure
        dir_path = tmp_path / _module.API_DIRECTORIES[0]
        dir_path.mkdir(parents=True)
        test_file = dir_path / "test.py"
        test_file.write_text("original")

        # Write the current hash first (simulates first run)
        current_hash = _module.compute_api_hash(tmp_path)
        _module.write_cached_hash(tmp_path, current_hash)

        # Modify the file
        test_file.write_text("modified content")

        # Now the hash should be different
        needs_regen, reason = _module.spec_needs_regeneration(tmp_path)

        assert needs_regen is True
        assert "changed" in reason

    def test_no_regeneration_when_cache_matches(self, tmp_path: Path) -> None:
        """Test that regeneration is skipped when cache matches current state."""
        # Create API structure
        dir_path = tmp_path / _module.API_DIRECTORIES[0]
        dir_path.mkdir(parents=True)
        (dir_path / "test.py").write_text("content")

        # Write current hash to cache
        current_hash = _module.compute_api_hash(tmp_path)
        _module.write_cached_hash(tmp_path, current_hash)

        needs_regen, reason = _module.spec_needs_regeneration(tmp_path)

        assert needs_regen is False
        assert "No changes detected" in reason


# =============================================================================
# Format Spec Tests
# =============================================================================


class TestFormatSpec:
    """Tests for format_spec function."""

    def test_format_spec_produces_valid_json(self) -> None:
        """Test that format_spec produces valid JSON."""
        import json

        spec = {"openapi": "3.0.0", "info": {"title": "Test API"}}
        result = _module.format_spec(spec)

        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed == spec

    def test_format_spec_sorts_keys(self) -> None:
        """Test that format_spec sorts keys for deterministic output."""
        spec = {"z": 1, "a": 2, "m": 3}
        result = _module.format_spec(spec)

        # Keys should appear in sorted order
        assert result.index('"a"') < result.index('"m"') < result.index('"z"')

    def test_format_spec_ends_with_newline(self) -> None:
        """Test that format_spec adds trailing newline."""
        spec = {"test": "value"}
        result = _module.format_spec(spec)

        assert result.endswith("\n")


# =============================================================================
# Main Function Tests
# =============================================================================


class TestMainFunction:
    """Tests for main entry point."""

    def test_main_rejects_path_outside_project(self, tmp_path: Path) -> None:
        """Test that main rejects output paths outside project directory."""
        args = argparse.Namespace(
            check=False,
            force=False,
            verbose=False,
            output=Path("/etc/passwd"),  # Outside project
        )

        stdout = io.StringIO()

        with patch.object(_module, "Path") as mock_path_class:
            # Mock __file__ to be in tmp_path
            mock_path_class.return_value.parent.parent.resolve.return_value = tmp_path
            # Make the output path resolve to something outside
            mock_path_class.return_value.resolve.return_value = Path("/etc/passwd")

            result = _module.main(args, stdout)

        assert result == 1
        assert "ERROR" in stdout.getvalue()

    def test_main_skips_when_no_changes(self, tmp_path: Path) -> None:
        """Test that main skips regeneration when no changes detected."""
        args = argparse.Namespace(
            check=False,
            force=False,
            verbose=False,
            output=Path("docs/openapi.json"),
        )

        stdout = io.StringIO()

        # Create output file
        output_path = tmp_path / "docs" / "openapi.json"
        output_path.parent.mkdir(parents=True)
        output_path.write_text('{"test": "spec"}\n')

        with (
            patch.object(_module, "Path") as mock_path_class,
            patch.object(_module, "spec_needs_regeneration") as mock_check,
        ):
            # Setup path mocking
            mock_path_class.return_value.parent.parent.resolve.return_value = tmp_path

            def resolve_side_effect():
                return output_path

            mock_path_class.return_value.resolve = resolve_side_effect

            # Mock: no regeneration needed
            mock_check.return_value = (False, "No changes")

            result = _module.main(args, stdout)

        assert result == 0
        assert "[SKIP]" in stdout.getvalue()

    def test_main_check_mode_fails_when_spec_missing(self, tmp_path: Path) -> None:
        """Test that --check fails when spec file doesn't exist."""
        args = argparse.Namespace(
            check=True,
            force=False,
            verbose=False,
            output=Path("docs/openapi.json"),
        )

        stdout = io.StringIO()

        with patch.object(_module, "Path") as mock_path_class:
            mock_path_class.return_value.parent.parent.resolve.return_value = tmp_path
            mock_resolved = tmp_path / "docs" / "openapi.json"

            def resolve_side_effect():
                return mock_resolved

            mock_path_class.return_value.resolve = resolve_side_effect

            result = _module.main(args, stdout)

        assert result == 1
        assert "does not exist" in stdout.getvalue()

    def test_main_force_bypasses_cache(self, tmp_path: Path) -> None:
        """Test that --force flag bypasses cache check."""
        args = argparse.Namespace(
            check=False,
            force=True,
            verbose=False,
            output=Path("docs/openapi.json"),
        )

        stdout = io.StringIO()

        mock_spec = {"openapi": "3.1.0", "info": {"title": "Test"}}

        with (
            patch.object(_module, "Path") as mock_path_class,
            patch.object(_module, "get_openapi_spec") as mock_get_spec,
            patch.object(_module, "spec_needs_regeneration") as mock_check,
            patch.object(_module, "compute_api_hash") as mock_hash,
            patch.object(_module, "write_cached_hash"),
            patch("builtins.open", create=True) as mock_open,
        ):
            # Setup path mocking
            mock_path_class.return_value.parent.parent.resolve.return_value = tmp_path
            output_path = tmp_path / "docs" / "openapi.json"
            output_path.parent.mkdir(parents=True)

            def resolve_side_effect():
                return output_path

            mock_path_class.return_value.resolve = resolve_side_effect

            mock_get_spec.return_value = mock_spec
            mock_hash.return_value = "a" * 64
            mock_open.return_value.__enter__ = MagicMock()
            mock_open.return_value.__exit__ = MagicMock()

            result = _module.main(args, stdout)

        # spec_needs_regeneration should NOT be called when --force is used
        mock_check.assert_not_called()
        # Should still generate
        mock_get_spec.assert_called_once()

    def test_main_verbose_shows_timing(self, tmp_path: Path) -> None:
        """Test that --verbose flag shows timing information."""
        args = argparse.Namespace(
            check=False,
            force=False,
            verbose=True,
            output=Path("docs/openapi.json"),
        )

        stdout = io.StringIO()

        with (
            patch.object(_module, "Path") as mock_path_class,
            patch.object(_module, "spec_needs_regeneration") as mock_check,
        ):
            mock_path_class.return_value.parent.parent.resolve.return_value = tmp_path
            output_path = tmp_path / "docs" / "openapi.json"
            output_path.parent.mkdir(parents=True)
            output_path.write_text("{}\n")

            def resolve_side_effect():
                return output_path

            mock_path_class.return_value.resolve = resolve_side_effect

            mock_check.return_value = (False, "No changes")

            result = _module.main(args, stdout)

        assert result == 0
        output = stdout.getvalue()
        assert "Timing:" in output
        assert "Total:" in output


# =============================================================================
# Integration-style Tests
# =============================================================================


class TestEndToEndScenarios:
    """Higher-level tests for realistic scenarios."""

    def test_first_run_generates_spec(self, tmp_path: Path) -> None:
        """Test that first run (no cache) generates the spec."""
        # Create API structure
        dir_path = tmp_path / _module.API_DIRECTORIES[0]
        dir_path.mkdir(parents=True)
        (dir_path / "routes.py").write_text("from fastapi import APIRouter")

        # First run: should need regeneration
        needs_regen, _ = _module.spec_needs_regeneration(tmp_path)
        assert needs_regen is True

        # Simulate successful generation
        current_hash = _module.compute_api_hash(tmp_path)
        _module.write_cached_hash(tmp_path, current_hash)

        # Cache should now exist
        assert (tmp_path / _module.CACHE_FILE).exists()
        assert _module.read_cached_hash(tmp_path) == current_hash

    def test_second_run_skips_regeneration(self, tmp_path: Path) -> None:
        """Test that second run with no changes skips regeneration."""
        # Create API structure
        dir_path = tmp_path / _module.API_DIRECTORIES[0]
        dir_path.mkdir(parents=True)
        (dir_path / "routes.py").write_text("from fastapi import APIRouter")

        # First run
        current_hash = _module.compute_api_hash(tmp_path)
        _module.write_cached_hash(tmp_path, current_hash)

        # Second run: should skip
        needs_regen, reason = _module.spec_needs_regeneration(tmp_path)
        assert needs_regen is False
        assert "No changes" in reason

    def test_file_modification_triggers_regeneration(self, tmp_path: Path) -> None:
        """Test that modifying an API file triggers regeneration."""
        # Create API structure
        dir_path = tmp_path / _module.API_DIRECTORIES[0]
        dir_path.mkdir(parents=True)
        routes_file = dir_path / "routes.py"
        routes_file.write_text("original content")

        # First run
        current_hash = _module.compute_api_hash(tmp_path)
        _module.write_cached_hash(tmp_path, current_hash)

        # Modify file
        routes_file.write_text("modified content")

        # Should need regeneration
        needs_regen, reason = _module.spec_needs_regeneration(tmp_path)
        assert needs_regen is True
        assert "changed" in reason

    def test_new_file_triggers_regeneration(self, tmp_path: Path) -> None:
        """Test that adding a new API file triggers regeneration."""
        # Create API structure
        dir_path = tmp_path / _module.API_DIRECTORIES[0]
        dir_path.mkdir(parents=True)
        (dir_path / "routes.py").write_text("routes")

        # First run
        current_hash = _module.compute_api_hash(tmp_path)
        _module.write_cached_hash(tmp_path, current_hash)

        # Add new file
        (dir_path / "new_endpoint.py").write_text("new endpoint")

        # Should need regeneration
        needs_regen, reason = _module.spec_needs_regeneration(tmp_path)
        assert needs_regen is True
        assert "changed" in reason

    def test_non_api_file_does_not_trigger_regeneration(self, tmp_path: Path) -> None:
        """Test that changes to non-API files don't trigger regeneration."""
        # Create API structure
        dir_path = tmp_path / _module.API_DIRECTORIES[0]
        dir_path.mkdir(parents=True)
        (dir_path / "routes.py").write_text("routes")

        # First run
        current_hash = _module.compute_api_hash(tmp_path)
        _module.write_cached_hash(tmp_path, current_hash)

        # Create non-API file (in a different directory)
        other_dir = tmp_path / "other"
        other_dir.mkdir(parents=True)
        (other_dir / "unrelated.py").write_text("unrelated")

        # Should NOT need regeneration
        needs_regen, _ = _module.spec_needs_regeneration(tmp_path)
        assert needs_regen is False
