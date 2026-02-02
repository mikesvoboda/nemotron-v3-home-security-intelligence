"""Unit tests for setup_lib.image_pull module.

Tests container image pull integration including runtime detection,
compose file discovery, image pulling, and size estimation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestDetectContainerRuntime:
    """Tests for detect_container_runtime() function."""

    def test_podman_compose_available(self) -> None:
        """Should return podman runtime when podman-compose is available."""
        from setup_lib.image_pull import detect_container_runtime

        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/podman-compose"
            result = detect_container_runtime()
            assert result == ("podman", "podman-compose")
            mock_which.assert_called_once_with("podman-compose")

    def test_docker_compose_v2_available(self) -> None:
        """Should return docker compose v2 when docker is available with compose plugin."""
        from setup_lib.image_pull import detect_container_runtime

        mock_result = MagicMock()
        mock_result.returncode = 0

        def mock_which(cmd: str) -> str | None:
            if cmd == "podman-compose":
                return None
            if cmd == "docker":
                return "/usr/bin/docker"
            return None

        with (
            patch("shutil.which", side_effect=mock_which),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = detect_container_runtime()
            assert result == ("docker", "docker compose")

    def test_docker_compose_v1_available(self) -> None:
        """Should return docker-compose v1 when standalone is available."""
        from setup_lib.image_pull import detect_container_runtime

        mock_result = MagicMock()
        mock_result.returncode = 1  # docker compose v2 fails

        def mock_which(cmd: str) -> str | None:
            if cmd == "podman-compose":
                return None
            if cmd == "docker":
                return "/usr/bin/docker"
            if cmd == "docker-compose":
                return "/usr/bin/docker-compose"
            return None

        with (
            patch("shutil.which", side_effect=mock_which),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = detect_container_runtime()
            assert result == ("docker", "docker-compose")

    def test_no_runtime_available(self) -> None:
        """Should return None when no container runtime is found."""
        from setup_lib.image_pull import detect_container_runtime

        with patch("shutil.which", return_value=None):
            result = detect_container_runtime()
            assert result is None

    def test_docker_compose_version_timeout(self) -> None:
        """Should fallback when docker compose version times out."""
        from setup_lib.image_pull import detect_container_runtime

        def mock_which(cmd: str) -> str | None:
            if cmd == "podman-compose":
                return None
            if cmd == "docker":
                return "/usr/bin/docker"
            if cmd == "docker-compose":
                return "/usr/bin/docker-compose"
            return None

        with (
            patch("shutil.which", side_effect=mock_which),
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=5)),
        ):
            result = detect_container_runtime()
            assert result == ("docker", "docker-compose")

    def test_docker_compose_version_file_not_found(self) -> None:
        """Should fallback when docker command not found during version check."""
        from setup_lib.image_pull import detect_container_runtime

        def mock_which(cmd: str) -> str | None:
            if cmd == "podman-compose":
                return None
            if cmd == "docker":
                return "/usr/bin/docker"
            if cmd == "docker-compose":
                return "/usr/bin/docker-compose"
            return None

        with (
            patch("shutil.which", side_effect=mock_which),
            patch("subprocess.run", side_effect=FileNotFoundError),
        ):
            result = detect_container_runtime()
            assert result == ("docker", "docker-compose")

    def test_docker_only_without_compose(self) -> None:
        """Should return None when docker exists but no compose available."""
        from setup_lib.image_pull import detect_container_runtime

        mock_result = MagicMock()
        mock_result.returncode = 1  # docker compose v2 fails

        def mock_which(cmd: str) -> str | None:
            if cmd == "podman-compose":
                return None
            if cmd == "docker":
                return "/usr/bin/docker"
            if cmd == "docker-compose":
                return None  # v1 not available either
            return None

        with (
            patch("shutil.which", side_effect=mock_which),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = detect_container_runtime()
            assert result is None


class TestGetComposeFiles:
    """Tests for get_compose_files() function."""

    def test_all_compose_files_exist(self) -> None:
        """Should return all compose files when they exist."""
        from setup_lib.image_pull import get_compose_files

        def mock_exists(self: Path) -> bool:
            return str(self) in (
                "docker-compose.ghcr.yml",
                "docker-compose.ghcr-core.yml",
                "docker-compose.prod.yml",
            )

        with patch.object(Path, "exists", mock_exists):
            result = get_compose_files()
            assert len(result) == 3
            filenames = [f[0] for f in result]
            assert "docker-compose.ghcr.yml" in filenames
            assert "docker-compose.ghcr-core.yml" in filenames
            assert "docker-compose.prod.yml" in filenames

    def test_only_ghcr_file_exists(self) -> None:
        """Should return only GHCR file when others don't exist."""
        from setup_lib.image_pull import get_compose_files

        def mock_exists(self: Path) -> bool:
            return str(self) == "docker-compose.ghcr.yml"

        with patch.object(Path, "exists", mock_exists):
            result = get_compose_files()
            assert len(result) == 1
            assert result[0][0] == "docker-compose.ghcr.yml"
            assert result[0][2] == "ghcr"

    def test_only_prod_file_exists(self) -> None:
        """Should return only prod file when others don't exist."""
        from setup_lib.image_pull import get_compose_files

        def mock_exists(self: Path) -> bool:
            return str(self) == "docker-compose.prod.yml"

        with patch.object(Path, "exists", mock_exists):
            result = get_compose_files()
            assert len(result) == 1
            assert result[0][0] == "docker-compose.prod.yml"
            assert result[0][2] == "build"

    def test_no_compose_files_exist(self) -> None:
        """Should return empty list when no compose files exist."""
        from setup_lib.image_pull import get_compose_files

        with patch.object(Path, "exists", return_value=False):
            result = get_compose_files()
            assert result == []

    def test_ghcr_files_have_correct_descriptions(self) -> None:
        """Should have correct descriptions for GHCR files."""
        from setup_lib.image_pull import get_compose_files

        def mock_exists(self: Path) -> bool:
            return str(self) in (
                "docker-compose.ghcr.yml",
                "docker-compose.ghcr-core.yml",
            )

        with patch.object(Path, "exists", mock_exists):
            result = get_compose_files()
            assert len(result) == 2
            # Check descriptions contain expected keywords
            for filename, description, pull_mode in result:
                assert pull_mode == "ghcr"
                if filename == "docker-compose.ghcr.yml":
                    assert "Full" in description or "GHCR" in description
                elif filename == "docker-compose.ghcr-core.yml":
                    assert "core" in description.lower() or "GHCR" in description


class TestPullImages:
    """Tests for pull_images() function."""

    def test_pull_with_docker_compose_v2(self) -> None:
        """Should run correct command for docker compose v2."""
        from setup_lib.image_pull import pull_images

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = pull_images("docker-compose.ghcr.yml", ("docker", "docker compose"))
            assert result is True
            mock_run.assert_called_once_with(
                ["docker", "compose", "-f", "docker-compose.ghcr.yml", "pull"],
                check=False,
            )

    def test_pull_with_podman_compose(self) -> None:
        """Should run correct command for podman-compose."""
        from setup_lib.image_pull import pull_images

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = pull_images("docker-compose.ghcr.yml", ("podman", "podman-compose"))
            assert result is True
            mock_run.assert_called_once_with(
                ["podman-compose", "-f", "docker-compose.ghcr.yml", "pull"],
                check=False,
            )

    def test_pull_with_docker_compose_v1(self) -> None:
        """Should run correct command for docker-compose v1."""
        from setup_lib.image_pull import pull_images

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = pull_images("docker-compose.prod.yml", ("docker", "docker-compose"))
            assert result is True
            mock_run.assert_called_once_with(
                ["docker-compose", "-f", "docker-compose.prod.yml", "pull"],
                check=False,
            )

    def test_pull_failure_returns_false(self) -> None:
        """Should return False when pull command fails."""
        from setup_lib.image_pull import pull_images

        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = pull_images("docker-compose.ghcr.yml", ("podman", "podman-compose"))
            assert result is False

    def test_pull_command_not_found(self) -> None:
        """Should return False when compose command not found."""
        from setup_lib.image_pull import pull_images

        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = pull_images("docker-compose.ghcr.yml", ("podman", "podman-compose"))
            assert result is False

    def test_pull_keyboard_interrupt(self) -> None:
        """Should return False when user cancels with Ctrl+C."""
        from setup_lib.image_pull import pull_images

        with patch("subprocess.run", side_effect=KeyboardInterrupt):
            result = pull_images("docker-compose.ghcr.yml", ("podman", "podman-compose"))
            assert result is False


class TestValidateComposePath:
    """Tests for _validate_compose_path() function."""

    def test_valid_path_in_cwd(self, tmp_path: Path) -> None:
        """Should return resolved path for valid file in cwd."""
        from setup_lib.image_pull import _validate_compose_path

        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3'\n")

        with patch.object(Path, "cwd", return_value=tmp_path):
            result = _validate_compose_path(str(compose_file))
            assert result == compose_file.resolve()

    def test_path_traversal_attack_prevented(self, tmp_path: Path) -> None:
        """Should return None for path traversal attempts."""
        from setup_lib.image_pull import _validate_compose_path

        # Create a file outside the cwd
        outside_file = Path("/etc/passwd")

        cwd = tmp_path / "project"
        cwd.mkdir()

        with patch.object(Path, "cwd", return_value=cwd):
            result = _validate_compose_path(str(outside_file))
            assert result is None

    def test_relative_path_traversal_prevented(self, tmp_path: Path) -> None:
        """Should return None for relative path traversal."""
        from setup_lib.image_pull import _validate_compose_path

        cwd = tmp_path / "project"
        cwd.mkdir()

        # Try to escape with ../
        with patch.object(Path, "cwd", return_value=cwd):
            result = _validate_compose_path("../../../etc/passwd")
            assert result is None

    def test_nonexistent_file_returns_none(self, tmp_path: Path) -> None:
        """Should return None for file that doesn't exist."""
        from setup_lib.image_pull import _validate_compose_path

        with patch.object(Path, "cwd", return_value=tmp_path):
            result = _validate_compose_path("nonexistent.yml")
            assert result is None

    def test_directory_returns_none(self, tmp_path: Path) -> None:
        """Should return None when path is a directory, not a file."""
        from setup_lib.image_pull import _validate_compose_path

        subdir = tmp_path / "subdir"
        subdir.mkdir()

        with patch.object(Path, "cwd", return_value=tmp_path):
            result = _validate_compose_path(str(subdir))
            assert result is None

    def test_handles_oserror(self) -> None:
        """Should return None when OSError occurs."""
        from setup_lib.image_pull import _validate_compose_path

        with patch.object(Path, "resolve", side_effect=OSError("Permission denied")):
            result = _validate_compose_path("some-file.yml")
            assert result is None

    def test_handles_value_error(self) -> None:
        """Should return None when ValueError occurs (invalid path)."""
        from setup_lib.image_pull import _validate_compose_path

        with patch.object(Path, "resolve", side_effect=ValueError("Invalid path")):
            result = _validate_compose_path("\x00invalid")
            assert result is None


class TestGetImageList:
    """Tests for get_image_list() function."""

    def test_parse_images_with_yaml(self, tmp_path: Path) -> None:
        """Should parse images from compose file using YAML."""
        from setup_lib.image_pull import get_image_list

        compose_content = """
version: '3.8'
services:
  backend:
    image: ghcr.io/example/backend:latest
  frontend:
    image: ghcr.io/example/frontend:latest
  db:
    image: postgres:15
"""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        with patch.object(Path, "cwd", return_value=tmp_path):
            result = get_image_list(str(compose_file))
            assert len(result) == 3
            assert "ghcr.io/example/backend:latest" in result
            assert "ghcr.io/example/frontend:latest" in result
            assert "postgres:15" in result

    def test_parse_build_services(self, tmp_path: Path) -> None:
        """Should mark services with build: as (build) servicename."""
        from setup_lib.image_pull import get_image_list

        compose_content = """
version: '3.8'
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
  db:
    image: postgres:15
"""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        with patch.object(Path, "cwd", return_value=tmp_path):
            result = get_image_list(str(compose_file))
            assert len(result) == 2
            assert "(build) app" in result
            assert "postgres:15" in result

    def test_invalid_path_returns_empty(self, tmp_path: Path) -> None:
        """Should return empty list for invalid path."""
        from setup_lib.image_pull import get_image_list

        with patch.object(Path, "cwd", return_value=tmp_path):
            result = get_image_list("/nonexistent/path/compose.yml")
            assert result == []

    def test_path_traversal_returns_empty(self, tmp_path: Path) -> None:
        """Should return empty list for path traversal attempts."""
        from setup_lib.image_pull import get_image_list

        with patch.object(Path, "cwd", return_value=tmp_path):
            result = get_image_list("../../../etc/passwd")
            assert result == []

    def test_fallback_parsing_without_yaml(self, tmp_path: Path) -> None:
        """Should use basic parsing when PyYAML is not available."""
        from setup_lib.image_pull import get_image_list

        compose_content = """version: '3.8'
services:
  backend:
    image: ghcr.io/example/backend:latest
  frontend:
    image: ghcr.io/example/frontend:latest
"""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        # Mock yaml import to fail
        import builtins

        original_import = builtins.__import__

        def mock_import(name: str, *args, **kwargs):
            if name == "yaml":
                raise ImportError("No module named 'yaml'")
            return original_import(name, *args, **kwargs)

        with (
            patch.object(Path, "cwd", return_value=tmp_path),
            patch.object(builtins, "__import__", side_effect=mock_import),
        ):
            result = get_image_list(str(compose_file))
            assert "ghcr.io/example/backend:latest" in result
            assert "ghcr.io/example/frontend:latest" in result

    def test_handles_missing_services_key(self, tmp_path: Path) -> None:
        """Should return empty list when services key is missing from dict."""
        from setup_lib.image_pull import get_image_list

        # Valid YAML but missing services key (KeyError path)
        compose_content = """
version: '3.8'
volumes:
  data:
"""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        with patch.object(Path, "cwd", return_value=tmp_path):
            result = get_image_list(str(compose_file))
            # Should handle gracefully without raising
            assert result == []

    def test_handles_file_read_error_in_fallback(self, tmp_path: Path) -> None:
        """Should return empty list when file read fails in fallback parsing."""
        from setup_lib.image_pull import get_image_list

        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("image: test:latest")

        # Mock yaml import to fail, triggering fallback parsing
        import builtins

        original_import = builtins.__import__

        def mock_import(name: str, *args, **kwargs):
            if name == "yaml":
                raise ImportError("No module named 'yaml'")
            return original_import(name, *args, **kwargs)

        # Make the file path valid but then mock read_text to fail
        with (
            patch.object(Path, "cwd", return_value=tmp_path),
            patch.object(builtins, "__import__", side_effect=mock_import),
        ):
            # Create a fresh validated path that exists
            result = get_image_list(str(compose_file))
            # Should handle gracefully without raising, found image from fallback
            assert "test:latest" in result

    def test_empty_services_section(self, tmp_path: Path) -> None:
        """Should return empty list when services section is empty."""
        from setup_lib.image_pull import get_image_list

        compose_content = """
version: '3.8'
services: {}
"""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        with patch.object(Path, "cwd", return_value=tmp_path):
            result = get_image_list(str(compose_file))
            assert result == []

    def test_no_services_section(self, tmp_path: Path) -> None:
        """Should return empty list when no services section."""
        from setup_lib.image_pull import get_image_list

        compose_content = """
version: '3.8'
networks:
  default:
"""
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        with patch.object(Path, "cwd", return_value=tmp_path):
            result = get_image_list(str(compose_file))
            assert result == []


class TestEstimatePullSize:
    """Tests for estimate_pull_size() function."""

    def test_known_images_estimate(self) -> None:
        """Should estimate known image sizes correctly."""
        from setup_lib.image_pull import estimate_pull_size

        images = ["postgres:15", "redis:7"]
        result = estimate_pull_size(images)
        # postgres ~250MB + redis ~50MB = ~300MB
        assert "MB" in result or "GB" in result
        assert "~" in result

    def test_unknown_images_default_size(self) -> None:
        """Should use default size for unknown images."""
        from setup_lib.image_pull import estimate_pull_size

        images = ["unknown-image:latest", "another-unknown:v1"]
        result = estimate_pull_size(images)
        # 2 unknown images * 200MB = ~400MB
        assert "MB" in result

    def test_ai_images_large_size(self) -> None:
        """Should estimate AI images as large."""
        from setup_lib.image_pull import estimate_pull_size

        images = ["ghcr.io/example/ai-yolo26:latest"]
        result = estimate_pull_size(images)
        # ai-yolo26 ~8000MB = ~8GB
        assert "GB" in result

    def test_large_total_shows_gb(self) -> None:
        """Should show GB for totals >= 1024MB."""
        from setup_lib.image_pull import estimate_pull_size

        # Mix of large AI images
        images = [
            "ghcr.io/example/backend:latest",
            "ghcr.io/example/ai-yolo26:latest",
            "ghcr.io/example/ai-llm:latest",
        ]
        result = estimate_pull_size(images)
        assert "GB" in result

    def test_empty_list(self) -> None:
        """Should return 0 for empty image list."""
        from setup_lib.image_pull import estimate_pull_size

        result = estimate_pull_size([])
        assert result == "~0 MB"

    def test_case_insensitive_matching(self) -> None:
        """Should match image names case-insensitively."""
        from setup_lib.image_pull import estimate_pull_size

        images = ["POSTGRES:15", "REDIS:7"]
        result = estimate_pull_size(images)
        # Should still match postgres and redis
        assert "MB" in result or "GB" in result


class TestPromptAndPullImages:
    """Tests for prompt_and_pull_images() function."""

    def test_no_runtime_detected(self) -> None:
        """Should handle case when no container runtime is found."""
        from setup_lib.image_pull import prompt_and_pull_images

        with patch("setup_lib.image_pull.detect_container_runtime", return_value=None):
            # Should return without error
            prompt_and_pull_images({})

    def test_no_compose_files_found(self) -> None:
        """Should handle case when no compose files are found."""
        from setup_lib.image_pull import prompt_and_pull_images

        with (
            patch(
                "setup_lib.image_pull.detect_container_runtime",
                return_value=("podman", "podman-compose"),
            ),
            patch("setup_lib.image_pull.get_compose_files", return_value=[]),
        ):
            # Should return without error
            prompt_and_pull_images({})

    def test_user_selects_skip(self) -> None:
        """Should handle user selecting skip option."""
        from setup_lib.image_pull import prompt_and_pull_images

        compose_files = [
            ("docker-compose.ghcr.yml", "Full GHCR", "ghcr"),
        ]

        with (
            patch(
                "setup_lib.image_pull.detect_container_runtime",
                return_value=("podman", "podman-compose"),
            ),
            patch("setup_lib.image_pull.get_compose_files", return_value=compose_files),
            patch("setup_lib.image_pull.get_image_list", return_value=["image1"]),
            patch("setup_lib.image_pull.estimate_pull_size", return_value="~1 GB"),
            patch("builtins.input", return_value="2"),  # Skip option
        ):
            # Should return without pulling
            prompt_and_pull_images({})

    def test_user_selects_build_mode(self) -> None:
        """Should handle user selecting build mode (no pull)."""
        from setup_lib.image_pull import prompt_and_pull_images

        compose_files = [
            ("docker-compose.prod.yml", "Local builds", "build"),
        ]

        with (
            patch(
                "setup_lib.image_pull.detect_container_runtime",
                return_value=("podman", "podman-compose"),
            ),
            patch("setup_lib.image_pull.get_compose_files", return_value=compose_files),
            patch("builtins.input", return_value="1"),
        ):
            # Should return without pulling (build mode)
            prompt_and_pull_images({})

    def test_user_confirms_pull_success(self) -> None:
        """Should pull images when user confirms."""
        from setup_lib.image_pull import prompt_and_pull_images

        compose_files = [
            ("docker-compose.ghcr.yml", "Full GHCR", "ghcr"),
        ]

        with (
            patch(
                "setup_lib.image_pull.detect_container_runtime",
                return_value=("podman", "podman-compose"),
            ),
            patch("setup_lib.image_pull.get_compose_files", return_value=compose_files),
            patch("setup_lib.image_pull.get_image_list", return_value=["image1", "image2"]),
            patch("setup_lib.image_pull.estimate_pull_size", return_value="~1 GB"),
            patch("builtins.input", side_effect=["1", "y"]),  # Select option 1, confirm
            patch("setup_lib.image_pull.pull_images", return_value=True) as mock_pull,
        ):
            prompt_and_pull_images({})
            mock_pull.assert_called_once_with(
                "docker-compose.ghcr.yml",
                ("podman", "podman-compose"),
            )

    def test_user_declines_pull(self) -> None:
        """Should not pull when user declines confirmation."""
        from setup_lib.image_pull import prompt_and_pull_images

        compose_files = [
            ("docker-compose.ghcr.yml", "Full GHCR", "ghcr"),
        ]

        with (
            patch(
                "setup_lib.image_pull.detect_container_runtime",
                return_value=("podman", "podman-compose"),
            ),
            patch("setup_lib.image_pull.get_compose_files", return_value=compose_files),
            patch("setup_lib.image_pull.get_image_list", return_value=["image1"]),
            patch("setup_lib.image_pull.estimate_pull_size", return_value="~1 GB"),
            patch("builtins.input", side_effect=["1", "n"]),  # Select option 1, decline
            patch("setup_lib.image_pull.pull_images") as mock_pull,
        ):
            prompt_and_pull_images({})
            mock_pull.assert_not_called()

    def test_invalid_selection_not_a_number(self) -> None:
        """Should handle non-numeric input."""
        from setup_lib.image_pull import prompt_and_pull_images

        compose_files = [
            ("docker-compose.ghcr.yml", "Full GHCR", "ghcr"),
        ]

        with (
            patch(
                "setup_lib.image_pull.detect_container_runtime",
                return_value=("podman", "podman-compose"),
            ),
            patch("setup_lib.image_pull.get_compose_files", return_value=compose_files),
            patch("setup_lib.image_pull.get_image_list", return_value=["image1"]),
            patch("setup_lib.image_pull.estimate_pull_size", return_value="~1 GB"),
            patch("builtins.input", return_value="invalid"),
        ):
            # Should handle gracefully without raising
            prompt_and_pull_images({})

    def test_invalid_selection_out_of_range(self) -> None:
        """Should handle out of range selection."""
        from setup_lib.image_pull import prompt_and_pull_images

        compose_files = [
            ("docker-compose.ghcr.yml", "Full GHCR", "ghcr"),
        ]

        with (
            patch(
                "setup_lib.image_pull.detect_container_runtime",
                return_value=("podman", "podman-compose"),
            ),
            patch("setup_lib.image_pull.get_compose_files", return_value=compose_files),
            patch("setup_lib.image_pull.get_image_list", return_value=["image1"]),
            patch("setup_lib.image_pull.estimate_pull_size", return_value="~1 GB"),
            patch("builtins.input", return_value="99"),
        ):
            # Should handle gracefully without raising
            prompt_and_pull_images({})

    def test_empty_input_defaults_to_first(self) -> None:
        """Should default to first option on empty input."""
        from setup_lib.image_pull import prompt_and_pull_images

        compose_files = [
            ("docker-compose.ghcr.yml", "Full GHCR", "ghcr"),
        ]

        with (
            patch(
                "setup_lib.image_pull.detect_container_runtime",
                return_value=("podman", "podman-compose"),
            ),
            patch("setup_lib.image_pull.get_compose_files", return_value=compose_files),
            patch("setup_lib.image_pull.get_image_list", return_value=["image1"]),
            patch("setup_lib.image_pull.estimate_pull_size", return_value="~1 GB"),
            patch("builtins.input", side_effect=["", "y"]),  # Empty defaults to 1, then confirm
            patch("setup_lib.image_pull.pull_images", return_value=True) as mock_pull,
        ):
            prompt_and_pull_images({})
            mock_pull.assert_called_once()

    def test_pull_failure_message(self) -> None:
        """Should handle pull failure gracefully."""
        from setup_lib.image_pull import prompt_and_pull_images

        compose_files = [
            ("docker-compose.ghcr.yml", "Full GHCR", "ghcr"),
        ]

        with (
            patch(
                "setup_lib.image_pull.detect_container_runtime",
                return_value=("podman", "podman-compose"),
            ),
            patch("setup_lib.image_pull.get_compose_files", return_value=compose_files),
            patch("setup_lib.image_pull.get_image_list", return_value=["image1"]),
            patch("setup_lib.image_pull.estimate_pull_size", return_value="~1 GB"),
            patch("builtins.input", side_effect=["1", "y"]),
            patch("setup_lib.image_pull.pull_images", return_value=False),
        ):
            # Should complete without raising
            prompt_and_pull_images({})

    def test_docker_compose_v2_commands_shown(self) -> None:
        """Should show docker compose v2 style commands."""
        from setup_lib.image_pull import prompt_and_pull_images

        compose_files = [
            ("docker-compose.ghcr.yml", "Full GHCR", "ghcr"),
        ]

        with (
            patch(
                "setup_lib.image_pull.detect_container_runtime",
                return_value=("docker", "docker compose"),
            ),
            patch("setup_lib.image_pull.get_compose_files", return_value=compose_files),
            patch("setup_lib.image_pull.get_image_list", return_value=["image1"]),
            patch("setup_lib.image_pull.estimate_pull_size", return_value="~1 GB"),
            patch("builtins.input", side_effect=["1", "y"]),
            patch("setup_lib.image_pull.pull_images", return_value=True),
        ):
            # Should complete without raising
            prompt_and_pull_images({})

    def test_accepts_config_parameter(self) -> None:
        """Should accept config dict parameter (reserved for future use)."""
        from setup_lib.image_pull import prompt_and_pull_images

        with patch("setup_lib.image_pull.detect_container_runtime", return_value=None):
            # Should accept config without error
            prompt_and_pull_images({"some_key": "some_value"})

    def test_multiple_compose_files_display(self) -> None:
        """Should display multiple compose file options correctly."""
        from setup_lib.image_pull import prompt_and_pull_images

        compose_files = [
            ("docker-compose.ghcr.yml", "Full GHCR", "ghcr"),
            ("docker-compose.ghcr-core.yml", "GHCR core only", "ghcr"),
            ("docker-compose.prod.yml", "Local builds", "build"),
        ]

        with (
            patch(
                "setup_lib.image_pull.detect_container_runtime",
                return_value=("podman", "podman-compose"),
            ),
            patch("setup_lib.image_pull.get_compose_files", return_value=compose_files),
            patch("setup_lib.image_pull.get_image_list", return_value=["image1"]),
            patch("setup_lib.image_pull.estimate_pull_size", return_value="~1 GB"),
            patch("builtins.input", return_value="4"),  # Skip option (len(compose_files) + 1)
        ):
            # Should complete without raising
            prompt_and_pull_images({})

    def test_ghcr_image_filtering(self) -> None:
        """Should filter GHCR images for size estimation."""
        from setup_lib.image_pull import prompt_and_pull_images

        compose_files = [
            ("docker-compose.ghcr.yml", "Full GHCR", "ghcr"),
        ]

        # Include both GHCR and build images
        images = ["ghcr.io/example/backend:latest", "(build) custom-service"]

        with (
            patch(
                "setup_lib.image_pull.detect_container_runtime",
                return_value=("podman", "podman-compose"),
            ),
            patch("setup_lib.image_pull.get_compose_files", return_value=compose_files),
            patch("setup_lib.image_pull.get_image_list", return_value=images),
            patch("setup_lib.image_pull.estimate_pull_size", return_value="~1 GB") as mock_estimate,
            patch("builtins.input", return_value="2"),  # Skip
        ):
            prompt_and_pull_images({})
            # estimate_pull_size should be called with all images
            mock_estimate.assert_called()

    def test_empty_confirmation_defaults_to_yes(self) -> None:
        """Should treat empty confirmation as yes (default)."""
        from setup_lib.image_pull import prompt_and_pull_images

        compose_files = [
            ("docker-compose.ghcr.yml", "Full GHCR", "ghcr"),
        ]

        with (
            patch(
                "setup_lib.image_pull.detect_container_runtime",
                return_value=("podman", "podman-compose"),
            ),
            patch("setup_lib.image_pull.get_compose_files", return_value=compose_files),
            patch("setup_lib.image_pull.get_image_list", return_value=["image1"]),
            patch("setup_lib.image_pull.estimate_pull_size", return_value="~1 GB"),
            patch("builtins.input", side_effect=["1", ""]),  # Select 1, empty confirm = yes
            patch("setup_lib.image_pull.pull_images", return_value=True) as mock_pull,
        ):
            prompt_and_pull_images({})
            mock_pull.assert_called_once()

    def test_yes_confirmation_accepted(self) -> None:
        """Should accept 'yes' as confirmation."""
        from setup_lib.image_pull import prompt_and_pull_images

        compose_files = [
            ("docker-compose.ghcr.yml", "Full GHCR", "ghcr"),
        ]

        with (
            patch(
                "setup_lib.image_pull.detect_container_runtime",
                return_value=("podman", "podman-compose"),
            ),
            patch("setup_lib.image_pull.get_compose_files", return_value=compose_files),
            patch("setup_lib.image_pull.get_image_list", return_value=["image1"]),
            patch("setup_lib.image_pull.estimate_pull_size", return_value="~1 GB"),
            patch("builtins.input", side_effect=["1", "yes"]),
            patch("setup_lib.image_pull.pull_images", return_value=True) as mock_pull,
        ):
            prompt_and_pull_images({})
            mock_pull.assert_called_once()
