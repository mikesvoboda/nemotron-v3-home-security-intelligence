"""Tests to validate Dockerfile configuration constraints.

This module tests critical deployment constraints such as worker count
limits required for SQLite + in-process background services architecture.
"""

import re
from pathlib import Path

import pytest


class TestDockerfileProdConfig:
    """Tests for production Dockerfile configuration."""

    @pytest.fixture
    def dockerfile_prod_path(self) -> Path:
        """Get the path to Dockerfile.prod."""
        # Navigate from tests/unit/ to backend/Dockerfile.prod
        return Path(__file__).parent.parent.parent / "Dockerfile.prod"

    @pytest.fixture
    def dockerfile_prod_content(self, dockerfile_prod_path: Path) -> str:
        """Read the production Dockerfile content."""
        if not dockerfile_prod_path.exists():
            pytest.skip(f"Dockerfile.prod not found at {dockerfile_prod_path}")
        return dockerfile_prod_path.read_text()

    def test_dockerfile_prod_exists(self, dockerfile_prod_path: Path) -> None:
        """Test that Dockerfile.prod exists."""
        assert dockerfile_prod_path.exists(), f"Dockerfile.prod not found at {dockerfile_prod_path}"

    def test_single_uvicorn_worker(self, dockerfile_prod_content: str) -> None:
        """Test that production Dockerfile uses single uvicorn worker.

        This is critical because:
        - SQLite doesn't handle concurrent write access from multiple processes well
        - Background services (FileWatcher, PipelineWorkerManager) run in FastAPI lifespan
        - Multiple workers would duplicate these services causing race conditions

        See: backend/services/pipeline_workers.py for details on single-instance requirement.
        """
        # Find the CMD line that starts uvicorn
        cmd_pattern = r'CMD\s*\[.*uvicorn.*--workers["\s,]+(\d+)'
        match = re.search(cmd_pattern, dockerfile_prod_content)

        assert match is not None, (
            "Could not find uvicorn CMD with --workers flag in Dockerfile.prod. "
            'Expected format: CMD ["uvicorn", ..., "--workers", "N"]'
        )

        workers = int(match.group(1))
        assert workers == 1, (
            f"Dockerfile.prod uses --workers {workers}, but must use --workers 1. "
            "Multiple workers cause duplicate background services and SQLite contention. "
            "See Dockerfile.prod comments for details."
        )

    def test_dockerfile_has_worker_constraint_documentation(
        self, dockerfile_prod_content: str
    ) -> None:
        """Test that Dockerfile.prod documents the single worker constraint."""
        # Check for documentation about the constraint
        required_terms = [
            "SQLite",
            "single",
            "worker",
        ]

        content_lower = dockerfile_prod_content.lower()
        for term in required_terms:
            assert term.lower() in content_lower, (
                f"Dockerfile.prod should document the '{term}' constraint. "
                "Add comments explaining why single worker is required."
            )

    def test_no_multiple_workers_anywhere(self, dockerfile_prod_content: str) -> None:
        """Test that no uncommented line has --workers with value > 1."""
        lines = dockerfile_prod_content.split("\n")
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


class TestDockerfileDevConfig:
    """Tests for development Dockerfile configuration (if exists)."""

    @pytest.fixture
    def dockerfile_dev_path(self) -> Path:
        """Get the path to Dockerfile (dev)."""
        return Path(__file__).parent.parent.parent / "Dockerfile"

    def test_dev_dockerfile_worker_count_if_exists(self, dockerfile_dev_path: Path) -> None:
        """Test that development Dockerfile also respects worker constraint if it exists."""
        if not dockerfile_dev_path.exists():
            pytest.skip("Development Dockerfile not found")

        content = dockerfile_dev_path.read_text()
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # Skip comment lines
            if line.strip().startswith("#"):
                continue

            # Check for --workers with value > 1
            workers_match = re.search(r"--workers[\"'\s,]+(\d+)", line)
            if workers_match:
                workers = int(workers_match.group(1))
                assert workers <= 1, (
                    f"Line {i} in Dockerfile has --workers {workers}. "
                    "SQLite deployments must use --workers 1."
                )
