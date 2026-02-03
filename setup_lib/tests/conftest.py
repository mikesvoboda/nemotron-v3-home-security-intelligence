"""Pytest configuration and fixtures for setup_lib tests."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def env_file_path(tmp_path: Path) -> Path:
    """Provide a path for a test .env file."""
    return tmp_path / ".env"


@pytest.fixture
def secrets_dir(tmp_path: Path) -> Path:
    """Provide a path for Docker secrets directory."""
    return tmp_path / "secrets"


@pytest.fixture
def mock_subprocess() -> Generator[MagicMock]:
    """Mock subprocess.run for Docker commands."""
    with patch("setup_lib.credentials.subprocess.run") as mock_run:
        # Default: commands succeed
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
        yield mock_run


@pytest.fixture
def clean_env() -> Generator[None]:
    """Ensure environment variables are clean for tests."""
    env_vars = [
        "POSTGRES_PASSWORD",
        "REDIS_PASSWORD",
        "MQTT_PASSWORD",
        "API_KEY",
        "DATABASE_URL",
    ]
    # Save original values
    original = {var: os.environ.get(var) for var in env_vars}

    # Clear variables
    for var in env_vars:
        os.environ.pop(var, None)

    yield

    # Restore original values
    for var, value in original.items():
        if value is not None:
            os.environ[var] = value
        else:
            os.environ.pop(var, None)
