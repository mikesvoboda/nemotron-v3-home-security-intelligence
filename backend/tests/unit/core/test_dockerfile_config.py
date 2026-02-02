"""Tests to validate Dockerfile configuration constraints.

This module tests critical deployment constraints such as worker count
limits required for SQLite + in-process background services architecture.

Note: The project uses consolidated multi-stage Dockerfiles with dev/prod targets
instead of separate Dockerfile and Dockerfile.prod files.
"""

import re
from pathlib import Path

import pytest


class TestDockerfileConfig:
    """Tests for consolidated Dockerfile configuration (multi-stage with dev/prod targets)."""

    @pytest.fixture
    def dockerfile_path(self) -> Path:
        """Get the path to the consolidated Dockerfile."""
        # Navigate from tests/unit/core/ to backend/Dockerfile
        return Path(__file__).parent.parent.parent.parent / "Dockerfile"

    @pytest.fixture
    def dockerfile_content(self, dockerfile_path: Path) -> str:
        """Read the Dockerfile content."""
        if not dockerfile_path.exists():
            pytest.skip(f"Dockerfile not found at {dockerfile_path}")
        return dockerfile_path.read_text()

    def test_dockerfile_exists(self, dockerfile_path: Path) -> None:
        """Test that the consolidated Dockerfile exists."""
        assert dockerfile_path.exists(), f"Dockerfile not found at {dockerfile_path}"

    def test_has_multi_stage_targets(self, dockerfile_content: str) -> None:
        """Test that Dockerfile has both dev and prod targets."""
        assert "AS dev" in dockerfile_content or "as dev" in dockerfile_content, (
            "Dockerfile should have a 'dev' target stage"
        )
        assert "AS prod" in dockerfile_content or "as prod" in dockerfile_content, (
            "Dockerfile should have a 'prod' target stage"
        )

    def test_single_uvicorn_worker_in_prod(self, dockerfile_content: str) -> None:
        """Test that production target uses single uvicorn worker.

        This is critical because:
        - SQLite doesn't handle concurrent write access from multiple processes well
        - Background services (FileWatcher, PipelineWorkerManager) run in FastAPI lifespan
        - Multiple workers would duplicate these services causing race conditions

        See: backend/services/pipeline_workers.py for details on single-instance requirement.
        """
        # Find the CMD line that starts uvicorn with --workers flag
        # This should be in the prod target section
        cmd_pattern = r'CMD\s*\[.*uvicorn.*--workers["\s,]+(\d+)'
        match = re.search(cmd_pattern, dockerfile_content)

        assert match is not None, (
            "Could not find uvicorn CMD with --workers flag in Dockerfile. "
            'Expected format: CMD ["uvicorn", ..., "--workers", "N"] in prod target'
        )

        workers = int(match.group(1))
        assert workers == 1, (
            f"Dockerfile prod target uses --workers {workers}, but must use --workers 1. "
            "Multiple workers cause duplicate background services and SQLite contention. "
            "See Dockerfile comments for details."
        )

    def test_dockerfile_has_worker_constraint_documentation(self, dockerfile_content: str) -> None:
        """Test that Dockerfile documents the single worker constraint.

        The single worker requirement exists because background services
        (FileWatcher, PipelineWorkerManager, SystemBroadcaster) run in the
        FastAPI lifespan context. Multiple workers would duplicate these services.
        """
        # Check for documentation about the constraint
        required_terms = [
            "single",
            "worker",
            "background",  # Documents the background services reason
        ]

        content_lower = dockerfile_content.lower()
        for term in required_terms:
            assert term.lower() in content_lower, (
                f"Dockerfile should document the '{term}' constraint. "
                "Add comments explaining why single worker is required."
            )

    def test_no_multiple_workers_in_uncommented_lines(self, dockerfile_content: str) -> None:
        """Test that no uncommented line has --workers with value > 1."""
        lines = dockerfile_content.split("\n")
        for i, line in enumerate(lines, 1):
            # Skip comment lines
            if line.strip().startswith("#"):
                continue

            # Check for --workers with value > 1
            workers_match = re.search(r"--workers[\"'\s,]+(\d+)", line)
            if workers_match:
                workers = int(workers_match.group(1))
                assert workers <= 1, (
                    f"Line {i} has --workers {workers}. "
                    "Production Dockerfile must use --workers 1 for SQLite deployments."
                )

    def test_no_dockerfile_prod_exists(self, dockerfile_path: Path) -> None:
        """Test that separate Dockerfile.prod does NOT exist (consolidated into single file)."""
        dockerfile_prod_path = dockerfile_path.parent / "Dockerfile.prod"
        assert not dockerfile_prod_path.exists(), (
            f"Found {dockerfile_prod_path} but project uses consolidated Dockerfile "
            "with multi-stage targets (dev/prod). Remove the separate Dockerfile.prod file."
        )

    def test_proxy_headers_enabled_in_prod(self, dockerfile_content: str) -> None:
        """Test that production target enables proxy headers for nginx reverse proxy.

        This is critical for:
        - Client IP passed through X-Forwarded-For headers from nginx
        - Correct IP-based rate limiting (uses actual client IP, not nginx IP)
        - Security logging with correct client addresses
        - HSTS and other headers respecting protocol from X-Forwarded-Proto

        When nginx reverse proxies requests, it sets:
        - X-Forwarded-For: client IP
        - X-Forwarded-Proto: request protocol (http/https)
        - X-Forwarded-Host: original host header

        Without --proxy-headers flag, uvicorn ignores these headers.
        """
        # Find the CMD line in prod target that starts uvicorn
        cmd_pattern = r'CMD\s*\[.*uvicorn.*--workers\s*["\']?1'

        # Check if the uvicorn command includes --proxy-headers
        assert "--proxy-headers" in dockerfile_content, (
            "Dockerfile prod target CMD must include '--proxy-headers' flag. "
            "This enables uvicorn to trust X-Forwarded-* headers from nginx proxy. "
            'Expected format: CMD ["uvicorn", ..., "--proxy-headers", "--forwarded-allow-ips", "*"]'
        )

    def test_forwarded_allow_ips_configured_in_prod(self, dockerfile_content: str) -> None:
        """Test that --forwarded-allow-ips is set to '*' for nginx proxy compatibility.

        The --forwarded-allow-ips parameter tells uvicorn which IPs are trusted
        to set X-Forwarded-* headers. Using '*' means trust all IPs that can
        reach the application, which is safe in containerized environments where
        only nginx reverse proxy can reach the backend container.
        """
        assert "--forwarded-allow-ips" in dockerfile_content, (
            "Dockerfile prod target CMD must include '--forwarded-allow-ips' flag. "
            'Expected format: --forwarded-allow-ips "*"'
        )

        # Verify it's set to '*' (or another reasonable value)
        forwarded_pattern = r'--forwarded-allow-ips["\s,]+([^\s,\]"\']+)'
        match = re.search(forwarded_pattern, dockerfile_content)

        assert match is not None, (
            "Could not find value for --forwarded-allow-ips in Dockerfile. "
            'Expected format: --forwarded-allow-ips "*"'
        )

        forwarded_ips = match.group(1)
        # Accept '*' or valid CIDR ranges for trusted proxy IPs
        # Valid examples: '*', '127.0.0.1', '172.16.0.0/12', '10.0.0.0/8'
        is_valid = forwarded_ips == "*" or (
            "/" in forwarded_ips
            or forwarded_ips.startswith("10.")
            or forwarded_ips.startswith("172.")
            or forwarded_ips.startswith("192.")
        )
        assert is_valid, (
            f"--forwarded-allow-ips has value '{forwarded_ips}'. "
            "Should be '*' or a valid CIDR range for trusted proxy IPs."
        )
