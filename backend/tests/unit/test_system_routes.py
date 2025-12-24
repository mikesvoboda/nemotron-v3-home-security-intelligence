"""Unit tests for backend.api.routes.system helpers.

These focus on low-level branches that are hard to hit via integration tests
but are important for correctness (and to satisfy the backend coverage gate).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.api.routes import system as system_routes


@pytest.mark.asyncio
async def test_check_database_health_unhealthy_on_exception() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("db down"))

    status = await system_routes.check_database_health(db)  # type: ignore[arg-type]
    assert status.status == "unhealthy"
    assert "db down" in status.message


@pytest.mark.asyncio
async def test_check_redis_health_unhealthy_on_error_payload() -> None:
    redis = AsyncMock()
    redis.health_check = AsyncMock(return_value={"status": "unhealthy", "error": "nope"})

    status = await system_routes.check_redis_health(redis)  # type: ignore[arg-type]
    assert status.status == "unhealthy"
    assert status.message == "nope"


def test_write_runtime_env_merges_existing_lines(tmp_path, monkeypatch) -> None:
    # Point runtime env path at a tmp file
    runtime_env = tmp_path / "runtime.env"
    monkeypatch.setenv("HSI_RUNTIME_ENV_PATH", str(runtime_env))

    runtime_env.write_text(
        "\n".join(
            [
                "# comment",
                "RETENTION_DAYS=30",
                "INVALID_LINE",
                "BATCH_WINDOW_SECONDS=90",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    system_routes._write_runtime_env({"RETENTION_DAYS": "7", "DETECTION_CONFIDENCE_THRESHOLD": "0.75"})

    content = runtime_env.read_text(encoding="utf-8").splitlines()
    # Should be sorted keys and include merged values
    assert content == [
        "BATCH_WINDOW_SECONDS=90",
        "DETECTION_CONFIDENCE_THRESHOLD=0.75",
        "RETENTION_DAYS=7",
    ]


def test_runtime_env_path_default_is_under_data() -> None:
    # Just sanity-check the default (do not touch filesystem)
    p = system_routes._runtime_env_path()
    assert isinstance(p, Path)

