"""Unit tests for GpuConfigService container restart functionality.

Tests the GPU configuration service's ability to:
- Apply GPU configuration changes
- Generate docker-compose override files
- Diff old and new configurations
- Restart only changed services
- Track restart progress in Redis
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.gpu_config_service import (
    ApplyResult,
    GpuAssignment,
    GpuConfigService,
    RestartStatus,
    ServiceRestartStatus,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_redis_client() -> AsyncMock:
    """Create a mock Redis client."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_docker_client() -> AsyncMock:
    """Create a mock Docker client."""
    client = AsyncMock()
    client.get_container_by_name = AsyncMock(return_value=None)
    client.get_container_status = AsyncMock(return_value="running")
    return client


@pytest.fixture
def gpu_config_service(
    mock_redis_client: AsyncMock,
    mock_docker_client: AsyncMock,
    tmp_path: Path,
) -> GpuConfigService:
    """Create a GpuConfigService instance for testing."""
    compose_file = tmp_path / "docker-compose.prod.yml"
    compose_file.write_text("version: '3.8'\nservices: {}")

    return GpuConfigService(
        redis_client=mock_redis_client,
        docker_client=mock_docker_client,
        compose_file_path=compose_file,
        project_root=tmp_path,
    )


@pytest.fixture
def sample_assignments() -> dict[str, GpuAssignment]:
    """Create sample GPU assignments for testing."""
    return {
        "ai-yolo26": GpuAssignment(
            service_name="ai-yolo26",
            gpu_index=0,
            vram_limit_mb=8192,
        ),
        "ai-llm": GpuAssignment(
            service_name="ai-llm",
            gpu_index=1,
            vram_limit_mb=16384,
        ),
    }


# ============================================================================
# ServiceRestartStatus Tests
# ============================================================================


class TestServiceRestartStatus:
    """Tests for ServiceRestartStatus dataclass."""

    def test_create_with_defaults(self) -> None:
        """Test creating ServiceRestartStatus with defaults."""
        status = ServiceRestartStatus(service_name="ai-yolo26")

        assert status.service_name == "ai-yolo26"
        assert status.status == RestartStatus.PENDING
        assert status.started_at is None
        assert status.completed_at is None
        assert status.error is None

    def test_create_with_all_fields(self) -> None:
        """Test creating ServiceRestartStatus with all fields."""
        now = datetime.now(UTC)
        status = ServiceRestartStatus(
            service_name="ai-yolo26",
            status=RestartStatus.RUNNING,
            started_at=now,
            completed_at=now,
            error=None,
        )

        assert status.service_name == "ai-yolo26"
        assert status.status == RestartStatus.RUNNING
        assert status.started_at == now
        assert status.completed_at == now

    def test_to_dict(self) -> None:
        """Test serializing ServiceRestartStatus to dict."""
        now = datetime.now(UTC)
        status = ServiceRestartStatus(
            service_name="ai-yolo26",
            status=RestartStatus.FAILED,
            started_at=now,
            completed_at=now,
            error="Connection refused",
        )

        data = status.to_dict()

        assert data["service_name"] == "ai-yolo26"
        assert data["status"] == "failed"
        assert data["started_at"] == now.isoformat()
        assert data["completed_at"] == now.isoformat()
        assert data["error"] == "Connection refused"

    def test_from_dict(self) -> None:
        """Test deserializing ServiceRestartStatus from dict."""
        now = datetime.now(UTC)
        data = {
            "service_name": "ai-llm",
            "status": "restarting",
            "started_at": now.isoformat(),
            "completed_at": None,
            "error": None,
        }

        status = ServiceRestartStatus.from_dict(data)

        assert status.service_name == "ai-llm"
        assert status.status == RestartStatus.RESTARTING
        assert status.started_at == now
        assert status.completed_at is None
        assert status.error is None

    def test_from_dict_with_null_timestamps(self) -> None:
        """Test deserializing with null timestamps."""
        data = {
            "service_name": "ai-yolo26",
            "status": "pending",
            "started_at": None,
            "completed_at": None,
        }

        status = ServiceRestartStatus.from_dict(data)

        assert status.started_at is None
        assert status.completed_at is None


# ============================================================================
# ApplyResult Tests
# ============================================================================


class TestApplyResult:
    """Tests for ApplyResult dataclass."""

    def test_create_with_defaults(self) -> None:
        """Test creating ApplyResult with minimal fields."""
        now = datetime.now(UTC)
        result = ApplyResult(
            success=True,
            operation_id="test-op-123",
            started_at=now,
        )

        assert result.success is True
        assert result.operation_id == "test-op-123"
        assert result.started_at == now
        assert result.completed_at is None
        assert result.changed_services == []
        assert result.service_statuses == {}
        assert result.error is None

    def test_to_dict(self) -> None:
        """Test serializing ApplyResult to dict."""
        now = datetime.now(UTC)
        result = ApplyResult(
            success=False,
            operation_id="op-456",
            started_at=now,
            completed_at=now,
            changed_services=["ai-yolo26", "ai-llm"],
            service_statuses={
                "ai-yolo26": ServiceRestartStatus(
                    service_name="ai-yolo26",
                    status=RestartStatus.FAILED,
                    error="Timeout",
                )
            },
            error="Partial failure",
        )

        data = result.to_dict()

        assert data["success"] is False
        assert data["operation_id"] == "op-456"
        assert data["started_at"] == now.isoformat()
        assert data["completed_at"] == now.isoformat()
        assert data["changed_services"] == ["ai-yolo26", "ai-llm"]
        assert "ai-yolo26" in data["service_statuses"]
        assert data["error"] == "Partial failure"


# ============================================================================
# GpuAssignment Tests
# ============================================================================


class TestGpuAssignment:
    """Tests for GpuAssignment dataclass."""

    def test_create_minimal(self) -> None:
        """Test creating GpuAssignment with minimal fields."""
        assignment = GpuAssignment(
            service_name="ai-yolo26",
            gpu_index=0,
        )

        assert assignment.service_name == "ai-yolo26"
        assert assignment.gpu_index == 0
        assert assignment.vram_limit_mb is None

    def test_create_with_vram_limit(self) -> None:
        """Test creating GpuAssignment with VRAM limit."""
        assignment = GpuAssignment(
            service_name="ai-llm",
            gpu_index=1,
            vram_limit_mb=24576,
        )

        assert assignment.service_name == "ai-llm"
        assert assignment.gpu_index == 1
        assert assignment.vram_limit_mb == 24576

    def test_to_dict(self) -> None:
        """Test serializing GpuAssignment to dict."""
        assignment = GpuAssignment(
            service_name="ai-florence",
            gpu_index=2,
            vram_limit_mb=8192,
        )

        data = assignment.to_dict()

        assert data["service_name"] == "ai-florence"
        assert data["gpu_index"] == 2
        assert data["vram_limit_mb"] == 8192


# ============================================================================
# GpuConfigService._diff_assignments Tests
# ============================================================================


class TestDiffAssignments:
    """Tests for GpuConfigService._diff_assignments method."""

    def test_no_changes(self, gpu_config_service: GpuConfigService) -> None:
        """Test diff with identical assignments."""
        old = {
            "ai-yolo26": GpuAssignment("ai-yolo26", 0),
            "ai-llm": GpuAssignment("ai-llm", 1),
        }
        new = {
            "ai-yolo26": GpuAssignment("ai-yolo26", 0),
            "ai-llm": GpuAssignment("ai-llm", 1),
        }

        changed = gpu_config_service._diff_assignments(old, new)

        assert changed == []

    def test_gpu_index_change(self, gpu_config_service: GpuConfigService) -> None:
        """Test diff detects GPU index changes."""
        old = {
            "ai-yolo26": GpuAssignment("ai-yolo26", 0),
        }
        new = {
            "ai-yolo26": GpuAssignment("ai-yolo26", 1),  # Changed from 0 to 1
        }

        changed = gpu_config_service._diff_assignments(old, new)

        assert changed == ["ai-yolo26"]

    def test_vram_limit_change(self, gpu_config_service: GpuConfigService) -> None:
        """Test diff detects VRAM limit changes."""
        old = {
            "ai-llm": GpuAssignment("ai-llm", 0, vram_limit_mb=8192),
        }
        new = {
            "ai-llm": GpuAssignment("ai-llm", 0, vram_limit_mb=16384),  # Changed
        }

        changed = gpu_config_service._diff_assignments(old, new)

        assert changed == ["ai-llm"]

    def test_service_added(self, gpu_config_service: GpuConfigService) -> None:
        """Test diff detects new services."""
        old = {
            "ai-yolo26": GpuAssignment("ai-yolo26", 0),
        }
        new = {
            "ai-yolo26": GpuAssignment("ai-yolo26", 0),
            "ai-llm": GpuAssignment("ai-llm", 1),  # New service
        }

        changed = gpu_config_service._diff_assignments(old, new)

        assert "ai-llm" in changed
        assert len(changed) == 1

    def test_service_removed(self, gpu_config_service: GpuConfigService) -> None:
        """Test diff detects removed services."""
        old = {
            "ai-yolo26": GpuAssignment("ai-yolo26", 0),
            "ai-llm": GpuAssignment("ai-llm", 1),
        }
        new = {
            "ai-yolo26": GpuAssignment("ai-yolo26", 0),
            # ai-llm removed
        }

        changed = gpu_config_service._diff_assignments(old, new)

        assert "ai-llm" in changed
        assert len(changed) == 1

    def test_multiple_changes(self, gpu_config_service: GpuConfigService) -> None:
        """Test diff with multiple types of changes."""
        old = {
            "ai-yolo26": GpuAssignment("ai-yolo26", 0),
            "ai-llm": GpuAssignment("ai-llm", 1),
            "ai-florence": GpuAssignment("ai-florence", 2),
        }
        new = {
            "ai-yolo26": GpuAssignment("ai-yolo26", 1),  # Changed
            # ai-llm removed
            "ai-florence": GpuAssignment("ai-florence", 2),  # Unchanged
            "ai-clip": GpuAssignment("ai-clip", 3),  # Added
        }

        changed = gpu_config_service._diff_assignments(old, new)

        assert len(changed) == 3
        assert "ai-yolo26" in changed  # Modified
        assert "ai-llm" in changed  # Removed
        assert "ai-clip" in changed  # Added
        assert "ai-florence" not in changed  # Unchanged

    def test_empty_to_populated(self, gpu_config_service: GpuConfigService) -> None:
        """Test diff from empty to populated assignments."""
        old: dict[str, GpuAssignment] = {}
        new = {
            "ai-yolo26": GpuAssignment("ai-yolo26", 0),
        }

        changed = gpu_config_service._diff_assignments(old, new)

        assert changed == ["ai-yolo26"]

    def test_populated_to_empty(self, gpu_config_service: GpuConfigService) -> None:
        """Test diff from populated to empty assignments."""
        old = {
            "ai-yolo26": GpuAssignment("ai-yolo26", 0),
        }
        new: dict[str, GpuAssignment] = {}

        changed = gpu_config_service._diff_assignments(old, new)

        assert changed == ["ai-yolo26"]


# ============================================================================
# GpuConfigService._build_override_content Tests
# ============================================================================


class TestBuildOverrideContent:
    """Tests for GpuConfigService._build_override_content method."""

    def test_single_service(self, gpu_config_service: GpuConfigService) -> None:
        """Test generating override content for single service."""
        assignments = {
            "ai-yolo26": GpuAssignment("ai-yolo26", 0),
        }

        content = gpu_config_service._build_override_content(assignments)

        assert "version: '3.8'" in content
        assert "ai-yolo26:" in content
        assert "NVIDIA_VISIBLE_DEVICES=0" in content

    def test_multiple_services(self, gpu_config_service: GpuConfigService) -> None:
        """Test generating override content for multiple services."""
        assignments = {
            "ai-yolo26": GpuAssignment("ai-yolo26", 0),
            "ai-llm": GpuAssignment("ai-llm", 1),
        }

        content = gpu_config_service._build_override_content(assignments)

        assert "ai-yolo26:" in content
        assert "ai-llm:" in content
        assert "NVIDIA_VISIBLE_DEVICES=0" in content
        assert "NVIDIA_VISIBLE_DEVICES=1" in content

    def test_with_vram_limit(self, gpu_config_service: GpuConfigService) -> None:
        """Test generating override content with VRAM limit."""
        assignments = {
            "ai-llm": GpuAssignment("ai-llm", 0, vram_limit_mb=16384),
        }

        content = gpu_config_service._build_override_content(assignments)

        assert "ai-llm:" in content
        assert "deploy:" in content
        assert "resources:" in content
        assert "reservations:" in content
        assert "devices:" in content

    def test_header_comment(self, gpu_config_service: GpuConfigService) -> None:
        """Test that override content includes header comment."""
        assignments = {"ai-yolo26": GpuAssignment("ai-yolo26", 0)}

        content = gpu_config_service._build_override_content(assignments)

        assert "# GPU Configuration Override" in content
        assert "# Generated by GpuConfigService" in content
        assert "# This file is auto-generated" in content


# ============================================================================
# GpuConfigService._recreate_service Tests
# ============================================================================


class TestRecreateService:
    """Tests for GpuConfigService._recreate_service method."""

    @pytest.mark.asyncio
    async def test_successful_restart(
        self,
        gpu_config_service: GpuConfigService,
    ) -> None:
        """Test successful service restart."""
        with (
            patch.object(gpu_config_service, "_get_compose_command", return_value="podman-compose"),
            patch("asyncio.create_subprocess_exec") as mock_exec,
        ):
            # Mock successful subprocess
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate = AsyncMock(return_value=(b"Success", b""))
            mock_exec.return_value = mock_process

            result = await gpu_config_service._recreate_service("ai-yolo26")

            assert result is True
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_failed_restart(
        self,
        gpu_config_service: GpuConfigService,
    ) -> None:
        """Test failed service restart."""
        with (
            patch.object(gpu_config_service, "_get_compose_command", return_value="podman-compose"),
            patch("asyncio.create_subprocess_exec") as mock_exec,
        ):
            # Mock failed subprocess
            mock_process = AsyncMock()
            mock_process.returncode = 1
            mock_process.communicate = AsyncMock(return_value=(b"", b"Error: container not found"))
            mock_exec.return_value = mock_process

            result = await gpu_config_service._recreate_service("ai-yolo26")

            assert result is False

    @pytest.mark.asyncio
    async def test_no_compose_command(
        self,
        gpu_config_service: GpuConfigService,
    ) -> None:
        """Test restart when no compose command is available."""
        with patch.object(gpu_config_service, "_get_compose_command", return_value=None):
            result = await gpu_config_service._recreate_service("ai-yolo26")

            assert result is False

    @pytest.mark.asyncio
    async def test_timeout(
        self,
        gpu_config_service: GpuConfigService,
    ) -> None:
        """Test restart timeout handling."""
        with (
            patch.object(gpu_config_service, "_get_compose_command", return_value="podman-compose"),
            patch("asyncio.create_subprocess_exec") as mock_exec,
            patch("asyncio.wait_for", side_effect=TimeoutError),
        ):
            mock_process = AsyncMock()
            mock_process.kill = AsyncMock()
            mock_process.wait = AsyncMock()
            mock_exec.return_value = mock_process

            result = await gpu_config_service._recreate_service("ai-yolo26")

            assert result is False
            mock_process.kill.assert_called_once()


# ============================================================================
# GpuConfigService._get_compose_command Tests
# ============================================================================


class TestGetComposeCommand:
    """Tests for GpuConfigService._get_compose_command method."""

    @pytest.mark.asyncio
    async def test_podman_compose_available(
        self,
        gpu_config_service: GpuConfigService,
    ) -> None:
        """Test when podman-compose is available."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.wait = AsyncMock()
            mock_exec.return_value = mock_process

            result = await gpu_config_service._get_compose_command()

            assert result == "podman-compose"

    @pytest.mark.asyncio
    async def test_docker_compose_fallback(
        self,
        gpu_config_service: GpuConfigService,
    ) -> None:
        """Test fallback to docker-compose when podman-compose unavailable."""
        call_count = 0

        async def mock_exec(*args: Any, **kwargs: Any) -> AsyncMock:
            nonlocal call_count
            call_count += 1
            mock_process = AsyncMock()
            # First call (podman-compose) fails, second (docker-compose) succeeds
            mock_process.returncode = 0 if call_count >= 2 else 1
            mock_process.wait = AsyncMock()
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=mock_exec):
            # First call raises FileNotFoundError, second succeeds
            result = await gpu_config_service._get_compose_command()

            # Should find one of the compose commands
            assert result in ["podman-compose", "docker-compose", "docker compose", None]

    @pytest.mark.asyncio
    async def test_no_compose_available(
        self,
        gpu_config_service: GpuConfigService,
    ) -> None:
        """Test when no compose command is available."""
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            result = await gpu_config_service._get_compose_command()

            assert result is None


# ============================================================================
# GpuConfigService.apply_gpu_config Tests
# ============================================================================


class TestApplyGpuConfig:
    """Tests for GpuConfigService.apply_gpu_config method."""

    @pytest.mark.asyncio
    async def test_no_changes(
        self,
        gpu_config_service: GpuConfigService,
        sample_assignments: dict[str, GpuAssignment],
    ) -> None:
        """Test apply_gpu_config when no changes detected."""
        # Set current assignments to match new
        gpu_config_service.set_current_assignments(sample_assignments)

        result = await gpu_config_service.apply_gpu_config(sample_assignments)

        assert result.success is True
        assert result.changed_services == []
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_successful_apply(
        self,
        gpu_config_service: GpuConfigService,
        sample_assignments: dict[str, GpuAssignment],
    ) -> None:
        """Test successful GPU config application."""
        # Mock successful restart
        with patch.object(
            gpu_config_service, "_recreate_service", return_value=True
        ) as mock_restart:
            result = await gpu_config_service.apply_gpu_config(sample_assignments)

            assert result.success is True
            assert len(result.changed_services) == 2
            assert "ai-yolo26" in result.changed_services
            assert "ai-llm" in result.changed_services
            assert mock_restart.call_count == 2

    @pytest.mark.asyncio
    async def test_partial_failure(
        self,
        gpu_config_service: GpuConfigService,
        sample_assignments: dict[str, GpuAssignment],
    ) -> None:
        """Test apply_gpu_config with partial restart failure."""
        call_count = 0

        async def mock_restart(service_name: str) -> bool:
            nonlocal call_count
            call_count += 1
            # First service succeeds, second fails
            return call_count == 1

        with patch.object(gpu_config_service, "_recreate_service", side_effect=mock_restart):
            result = await gpu_config_service.apply_gpu_config(sample_assignments)

            assert result.success is False
            # One service should be RUNNING, one FAILED
            statuses = list(result.service_statuses.values())
            running = [s for s in statuses if s.status == RestartStatus.RUNNING]
            failed = [s for s in statuses if s.status == RestartStatus.FAILED]
            assert len(running) == 1
            assert len(failed) == 1

    @pytest.mark.asyncio
    async def test_redis_persistence(
        self,
        gpu_config_service: GpuConfigService,
        mock_redis_client: AsyncMock,
        sample_assignments: dict[str, GpuAssignment],
    ) -> None:
        """Test that operation status is persisted to Redis."""
        with patch.object(gpu_config_service, "_recreate_service", return_value=True):
            await gpu_config_service.apply_gpu_config(sample_assignments)

            # Redis.set should have been called multiple times for status updates
            assert mock_redis_client.set.call_count >= 1

    @pytest.mark.asyncio
    async def test_exception_handling(
        self,
        gpu_config_service: GpuConfigService,
        sample_assignments: dict[str, GpuAssignment],
    ) -> None:
        """Test apply_gpu_config handles exceptions gracefully."""
        with patch.object(
            gpu_config_service,
            "_generate_override_file",
            side_effect=Exception("File write failed"),
        ):
            result = await gpu_config_service.apply_gpu_config(sample_assignments)

            assert result.success is False
            assert result.error is not None
            assert "File write failed" in result.error


# ============================================================================
# GpuConfigService.get_container_status Tests
# ============================================================================


class TestGetContainerStatus:
    """Tests for GpuConfigService.get_container_status method."""

    @pytest.mark.asyncio
    async def test_get_status_with_containers(
        self,
        gpu_config_service: GpuConfigService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test getting container status when containers exist."""
        mock_container = MagicMock()
        mock_container.id = "container123"
        mock_docker_client.get_container_by_name = AsyncMock(return_value=mock_container)
        mock_docker_client.get_container_status = AsyncMock(return_value="running")

        result = await gpu_config_service.get_container_status(["ai-yolo26", "ai-llm"])

        assert result["ai-yolo26"] == "running"
        assert result["ai-llm"] == "running"

    @pytest.mark.asyncio
    async def test_get_status_container_not_found(
        self,
        gpu_config_service: GpuConfigService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test getting container status when container not found."""
        mock_docker_client.get_container_by_name = AsyncMock(return_value=None)

        result = await gpu_config_service.get_container_status(["ai-yolo26"])

        assert result["ai-yolo26"] is None

    @pytest.mark.asyncio
    async def test_get_status_no_docker_client(
        self,
        mock_redis_client: AsyncMock,
        tmp_path: Path,
    ) -> None:
        """Test getting container status when docker client unavailable."""
        compose_file = tmp_path / "docker-compose.prod.yml"
        compose_file.write_text("version: '3.8'\nservices: {}")

        service = GpuConfigService(
            redis_client=mock_redis_client,
            docker_client=None,  # No docker client
            compose_file_path=compose_file,
            project_root=tmp_path,
        )

        result = await service.get_container_status(["ai-yolo26"])

        assert result["ai-yolo26"] is None

    @pytest.mark.asyncio
    async def test_get_status_exception_handling(
        self,
        gpu_config_service: GpuConfigService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test get_container_status handles exceptions gracefully."""
        mock_docker_client.get_container_by_name = AsyncMock(
            side_effect=Exception("Connection failed")
        )

        result = await gpu_config_service.get_container_status(["ai-yolo26"])

        assert result["ai-yolo26"] is None


# ============================================================================
# GpuConfigService.get_operation_status Tests
# ============================================================================


class TestGetOperationStatus:
    """Tests for GpuConfigService.get_operation_status method."""

    @pytest.mark.asyncio
    async def test_get_existing_operation(
        self,
        gpu_config_service: GpuConfigService,
        mock_redis_client: AsyncMock,
    ) -> None:
        """Test getting status of existing operation."""
        now = datetime.now(UTC)
        mock_redis_client.get = AsyncMock(
            return_value={
                "success": True,
                "operation_id": "op-123",
                "started_at": now.isoformat(),
                "completed_at": now.isoformat(),
                "changed_services": ["ai-yolo26"],
                "service_statuses": {},
                "error": None,
            }
        )

        result = await gpu_config_service.get_operation_status("op-123")

        assert result is not None
        assert result.operation_id == "op-123"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_get_nonexistent_operation(
        self,
        gpu_config_service: GpuConfigService,
        mock_redis_client: AsyncMock,
    ) -> None:
        """Test getting status of nonexistent operation."""
        mock_redis_client.get = AsyncMock(return_value=None)

        result = await gpu_config_service.get_operation_status("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_operation_no_redis(
        self,
        tmp_path: Path,
    ) -> None:
        """Test getting operation status when Redis unavailable."""
        compose_file = tmp_path / "docker-compose.prod.yml"
        compose_file.write_text("version: '3.8'\nservices: {}")

        service = GpuConfigService(
            redis_client=None,  # No Redis
            compose_file_path=compose_file,
            project_root=tmp_path,
        )

        result = await service.get_operation_status("op-123")

        assert result is None


# ============================================================================
# GpuConfigService Utility Methods Tests
# ============================================================================


class TestUtilityMethods:
    """Tests for GpuConfigService utility methods."""

    def test_get_current_assignments(
        self,
        gpu_config_service: GpuConfigService,
        sample_assignments: dict[str, GpuAssignment],
    ) -> None:
        """Test get_current_assignments returns copy."""
        gpu_config_service.set_current_assignments(sample_assignments)

        result = gpu_config_service.get_current_assignments()

        assert result == sample_assignments
        # Verify it's a copy, not the same object
        assert result is not gpu_config_service._current_assignments

    def test_set_current_assignments(
        self,
        gpu_config_service: GpuConfigService,
        sample_assignments: dict[str, GpuAssignment],
    ) -> None:
        """Test set_current_assignments stores a copy."""
        gpu_config_service.set_current_assignments(sample_assignments)

        # Modify original
        sample_assignments["new-service"] = GpuAssignment("new-service", 3)

        # Verify stored copy is unchanged
        assert "new-service" not in gpu_config_service._current_assignments


# ============================================================================
# Integration-style Tests
# ============================================================================


class TestGpuConfigServiceIntegration:
    """Integration-style tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_full_apply_workflow(
        self,
        gpu_config_service: GpuConfigService,
        sample_assignments: dict[str, GpuAssignment],
        tmp_path: Path,
    ) -> None:
        """Test complete apply workflow from empty to configured."""
        with patch.object(gpu_config_service, "_recreate_service", return_value=True):
            # Apply initial configuration
            result = await gpu_config_service.apply_gpu_config(sample_assignments)

            assert result.success is True
            assert len(result.changed_services) == 2

            # Verify override file was created
            override_file = tmp_path / "docker-compose.gpu-override.yml"
            assert override_file.exists()
            content = override_file.read_text()
            assert "ai-yolo26:" in content
            assert "ai-llm:" in content

            # Verify current assignments updated
            current = gpu_config_service.get_current_assignments()
            assert "ai-yolo26" in current
            assert "ai-llm" in current

    @pytest.mark.asyncio
    async def test_incremental_change_workflow(
        self,
        gpu_config_service: GpuConfigService,
        sample_assignments: dict[str, GpuAssignment],
    ) -> None:
        """Test incremental configuration changes."""
        with patch.object(gpu_config_service, "_recreate_service", return_value=True):
            # Apply initial configuration
            result1 = await gpu_config_service.apply_gpu_config(sample_assignments)
            assert result1.success is True

            # Change only one service
            modified = gpu_config_service.get_current_assignments()
            modified["ai-yolo26"] = GpuAssignment("ai-yolo26", 2)  # Changed GPU

            result2 = await gpu_config_service.apply_gpu_config(modified)

            assert result2.success is True
            # Only the modified service should be restarted
            assert result2.changed_services == ["ai-yolo26"]
