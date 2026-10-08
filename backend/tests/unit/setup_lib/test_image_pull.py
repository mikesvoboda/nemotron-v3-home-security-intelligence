"""Unit tests for setup_lib.image_pull module.

Runtime detection and the single-install-path image briefing. O1.2 (UR-17)
retired the GHCR pre-built compose surface, so the module no longer discovers
compose files, estimates private-registry pulls, or pulls anything — these
tests pin what is left and pin the retirement itself (no private-registry
advice comes back).
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch


class TestDetectContainerRuntime:
    """Tests for detect_container_runtime() function."""

    def test_podman_compose_available(self) -> None:
        """Should return podman runtime when podman-compose is available."""
        from setup_lib.image_pull import detect_container_runtime

        with patch("shutil.which", autospec=True) as mock_which:
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
            patch("shutil.which", side_effect=mock_which, autospec=True),
            patch("subprocess.run", return_value=mock_result, autospec=True),
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
            patch("shutil.which", side_effect=mock_which, autospec=True),
            patch("subprocess.run", return_value=mock_result, autospec=True),
        ):
            result = detect_container_runtime()
            assert result == ("docker", "docker-compose")

    def test_no_runtime_available(self) -> None:
        """Should return None when no container runtime is found."""
        from setup_lib.image_pull import detect_container_runtime

        with patch("shutil.which", return_value=None, autospec=True):
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
            patch("shutil.which", side_effect=mock_which, autospec=True),
            patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=5),
                autospec=True,
            ),
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
            patch("shutil.which", side_effect=mock_which, autospec=True),
            patch("subprocess.run", side_effect=FileNotFoundError, autospec=True),
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
            patch("shutil.which", side_effect=mock_which, autospec=True),
            patch("subprocess.run", return_value=mock_result, autospec=True),
        ):
            result = detect_container_runtime()
            assert result is None


class TestPromptAndPullImages:
    """Tests for prompt_and_pull_images() — the single-path briefing."""

    def test_no_runtime_detected_prints_install_help(self, capsys) -> None:
        from setup_lib.image_pull import prompt_and_pull_images

        with patch(
            "setup_lib.image_pull.detect_container_runtime", return_value=None, autospec=True
        ):
            prompt_and_pull_images({})

        out = capsys.readouterr().out
        assert "No container runtime detected" in out
        assert "prod.yml" not in out  # no path advice without a runtime to run it

    def test_names_the_one_compose_stack(self, capsys) -> None:
        from setup_lib.image_pull import prompt_and_pull_images

        with patch(
            "setup_lib.image_pull.detect_container_runtime",
            return_value=("podman", "podman-compose"),
            autospec=True,
        ):
            prompt_and_pull_images({})

        out = capsys.readouterr().out
        assert "docker-compose.prod.yml" in out
        assert "podman-compose -f docker-compose.prod.yml build" in out
        assert "only compose stack" in out

    def test_docker_runtime_shows_docker_commands(self, capsys) -> None:
        from setup_lib.image_pull import prompt_and_pull_images

        with patch(
            "setup_lib.image_pull.detect_container_runtime",
            return_value=("docker", "docker compose"),
            autospec=True,
        ):
            prompt_and_pull_images({})

        out = capsys.readouterr().out
        assert "docker compose -f docker-compose.prod.yml build" in out

    def test_skip_pull_still_shows_the_build_command(self, capsys) -> None:
        from setup_lib.image_pull import prompt_and_pull_images

        with patch(
            "setup_lib.image_pull.detect_container_runtime",
            return_value=("docker", "docker compose"),
            autospec=True,
        ):
            prompt_and_pull_images({"skip_pull": True})

        out = capsys.readouterr().out
        assert "docker compose -f docker-compose.prod.yml build" in out

    def test_retirement_is_pinned_no_private_registry_advice(self, capsys) -> None:
        """O1.2 (UR-17): the private-registry pull flow is gone — no login
        advice, no compose-file menu, and never waits on stdin."""
        from setup_lib.image_pull import prompt_and_pull_images

        with (
            patch(
                "setup_lib.image_pull.detect_container_runtime",
                return_value=("podman", "podman-compose"),
                autospec=True,
            ),
            patch("builtins.input", side_effect=AssertionError("prompted on stdin"), autospec=True),
        ):
            prompt_and_pull_images({})

        out = capsys.readouterr().out
        assert "login" not in out
        assert "GHCR" not in out and "ghcr" not in out
        assert "Available deployment modes" not in out

    def test_removed_helpers_stay_removed(self) -> None:
        import pytest
        from setup_lib import image_pull

        for gone in ("get_compose_files", "pull_images", "get_image_list", "estimate_pull_size"):
            assert not hasattr(image_pull, gone), (
                f"{gone} came back — the ghcr pull path is retired"
            )

        with pytest.raises(ImportError):
            from setup_lib.image_pull import estimate_pull_size  # noqa: F401
