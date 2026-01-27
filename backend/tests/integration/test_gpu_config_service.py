"""Integration tests for GpuConfigService with real Redis.

These tests verify the GpuConfigService behavior against a real Redis instance,
covering scenarios that require external dependencies:
- Redis-based operation status tracking
- Progress persistence across service calls
- Operation TTL expiration

Uses the real_redis fixture from conftest.py for actual Redis connections.

IMPORTANT: These tests must be run serially (-n0) due to shared Redis state.
Run with:

    uv run pytest backend/tests/integration/test_gpu_config_service.py -n0
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from backend.services.gpu_config_service import (
    REDIS_GPU_CONFIG_PREFIX,
    ApplyResult,
    GpuConfigService,
    RestartStatus,
    ServiceRestartStatus,
)

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

# Mark as integration tests
pytestmark = pytest.mark.integration


# =============================================================================
# Fixtures
# =============================================================================


def _unique_operation_id() -> str:
    """Generate a unique operation ID for test isolation."""
    return f"test_{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def gpu_config_service(real_redis: RedisClient) -> GpuConfigService:
    """Create a GpuConfigService with real Redis and no Docker client."""
    return GpuConfigService(
        redis_client=real_redis,
        docker_client=None,  # Not needed for status tracking tests
        compose_file_path="/tmp/docker-compose.test.yml",  # noqa: S108
    )


@pytest.fixture
async def cleanup_redis_keys(real_redis: RedisClient):
    """Clean up test keys after test completion."""
    yield

    # Cleanup after test - delete all GPU config keys
    client = real_redis._ensure_connected()
    keys = []
    async for key in client.scan_iter(match=f"{REDIS_GPU_CONFIG_PREFIX}*", count=100):
        keys.append(key)
    if keys:
        await client.delete(*keys)


# =============================================================================
# Operation Status Persistence Tests
# =============================================================================


class TestOperationStatusPersistence:
    """Tests for operation status tracking in Redis."""

    @pytest.mark.asyncio
    async def test_persist_and_retrieve_operation(
        self,
        gpu_config_service: GpuConfigService,
        real_redis: RedisClient,
        cleanup_redis_keys: None,
    ) -> None:
        """Verify operation status is persisted to and retrieved from Redis."""
        operation_id = _unique_operation_id()

        # Create an ApplyResult
        result = ApplyResult(
            success=True,
            operation_id=operation_id,
            started_at=datetime.now(UTC),
            changed_services=["ai-yolo26", "ai-llm"],
            service_statuses={
                "ai-yolo26": ServiceRestartStatus(
                    service_name="ai-yolo26",
                    status=RestartStatus.RUNNING,
                ),
                "ai-llm": ServiceRestartStatus(
                    service_name="ai-llm",
                    status=RestartStatus.RESTARTING,
                ),
            },
        )

        # Persist to Redis
        await gpu_config_service._persist_operation_status(result)

        # Retrieve and verify
        loaded = await gpu_config_service.get_operation_status(operation_id)

        assert loaded is not None
        assert loaded.operation_id == operation_id
        assert loaded.success is True
        assert loaded.changed_services == ["ai-yolo26", "ai-llm"]
        assert len(loaded.service_statuses) == 2
        assert loaded.service_statuses["ai-yolo26"].status == RestartStatus.RUNNING
        assert loaded.service_statuses["ai-llm"].status == RestartStatus.RESTARTING

    @pytest.mark.asyncio
    async def test_operation_not_found_returns_none(
        self,
        gpu_config_service: GpuConfigService,
        cleanup_redis_keys: None,
    ) -> None:
        """Verify non-existent operation returns None."""
        result = await gpu_config_service.get_operation_status("nonexistent-op-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_operation_with_error_status(
        self,
        gpu_config_service: GpuConfigService,
        cleanup_redis_keys: None,
    ) -> None:
        """Verify failed operation with error is persisted correctly."""
        operation_id = _unique_operation_id()

        result = ApplyResult(
            success=False,
            operation_id=operation_id,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            changed_services=["ai-yolo26"],
            service_statuses={
                "ai-yolo26": ServiceRestartStatus(
                    service_name="ai-yolo26",
                    status=RestartStatus.FAILED,
                    error="GPU not available",
                ),
            },
            error="One or more services failed to restart",
        )

        await gpu_config_service._persist_operation_status(result)

        loaded = await gpu_config_service.get_operation_status(operation_id)

        assert loaded is not None
        assert loaded.success is False
        assert loaded.error == "One or more services failed to restart"
        assert loaded.service_statuses["ai-yolo26"].status == RestartStatus.FAILED
        assert loaded.service_statuses["ai-yolo26"].error == "GPU not available"


# =============================================================================
# Multi-Service Status Tests
# =============================================================================


class TestMultiServiceStatus:
    """Tests for tracking multiple services in an operation."""

    @pytest.mark.asyncio
    async def test_track_multiple_services_different_statuses(
        self,
        gpu_config_service: GpuConfigService,
        cleanup_redis_keys: None,
    ) -> None:
        """Verify multiple services with different statuses are tracked."""
        operation_id = _unique_operation_id()

        result = ApplyResult(
            success=False,  # Partial success
            operation_id=operation_id,
            started_at=datetime.now(UTC),
            changed_services=["ai-yolo26", "ai-llm", "ai-pose"],
            service_statuses={
                "ai-yolo26": ServiceRestartStatus(
                    service_name="ai-yolo26",
                    status=RestartStatus.RUNNING,
                    started_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC),
                ),
                "ai-llm": ServiceRestartStatus(
                    service_name="ai-llm",
                    status=RestartStatus.RUNNING,
                    started_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC),
                ),
                "ai-pose": ServiceRestartStatus(
                    service_name="ai-pose",
                    status=RestartStatus.FAILED,
                    started_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC),
                    error="Container exited with code 1",
                ),
            },
        )

        await gpu_config_service._persist_operation_status(result)

        loaded = await gpu_config_service.get_operation_status(operation_id)

        assert loaded is not None
        assert len(loaded.service_statuses) == 3

        # Check each service status
        assert loaded.service_statuses["ai-yolo26"].status == RestartStatus.RUNNING
        assert loaded.service_statuses["ai-llm"].status == RestartStatus.RUNNING
        assert loaded.service_statuses["ai-pose"].status == RestartStatus.FAILED
        assert loaded.service_statuses["ai-pose"].error == "Container exited with code 1"


# =============================================================================
# TTL Expiration Tests
# =============================================================================


class TestOperationTTL:
    """Tests for operation key expiration."""

    @pytest.mark.asyncio
    async def test_operation_persists_within_ttl(
        self,
        gpu_config_service: GpuConfigService,
        cleanup_redis_keys: None,
    ) -> None:
        """Verify operation is accessible within TTL window."""
        operation_id = _unique_operation_id()

        result = ApplyResult(
            success=True,
            operation_id=operation_id,
            started_at=datetime.now(UTC),
            changed_services=[],
        )

        await gpu_config_service._persist_operation_status(result)

        # Wait a short time
        await asyncio.sleep(0.1)

        # Should still exist
        loaded = await gpu_config_service.get_operation_status(operation_id)
        assert loaded is not None
        assert loaded.operation_id == operation_id
