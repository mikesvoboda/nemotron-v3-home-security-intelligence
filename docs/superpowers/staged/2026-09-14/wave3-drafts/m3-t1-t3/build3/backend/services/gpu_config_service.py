"""GPU Configuration Service for managing AI service GPU assignments.

This module provides the GpuConfigService class that handles GPU configuration
management including loading assignments from database, generating docker-compose
override files, diffing configurations, and restarting affected services.

Features:
- Load GPU assignments from database
- Generate docker-compose.gpu-override.yml files
- Diff old and new configurations to find changed services
- Restart only changed services via podman-compose
- Track restart progress in Redis
- Support for both Docker and Podman

Usage:
    from backend.services.gpu_config_service import GpuConfigService

    # Create service with dependencies
    service = GpuConfigService(
        redis_client=redis_client,
        docker_client=docker_client,
        compose_file_path="/path/to/docker-compose.prod.yml",
    )

    # Apply GPU configuration changes
    result = await service.apply_gpu_config()

    # Check container status
    status = await service.get_container_status(["ai-yolo26", "ai-llm"])

    # Or use simple file writing API:
    service = GpuConfigService(config_dir=Path("config"))
    assignments = [
        GpuAssignment(service_name="ai-llm", gpu_index=0),
        GpuAssignment(service_name="ai-enrichment", gpu_index=1, vram_budget_override=3.5),
    ]
    override_path, assignments_path = await service.write_config_files(
        assignments=assignments,
        strategy="vram_based",
    )
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.core.docker_client import DockerClient
    from backend.core.redis import RedisClient

logger = get_logger(__name__)


# Redis key prefix for GPU config operations
REDIS_GPU_CONFIG_PREFIX = "gpu_config"


class RestartStatus(StrEnum):
    """Status values for service restart operations."""

    PENDING = auto()  # Waiting to be restarted
    RESTARTING = auto()  # Currently restarting
    RUNNING = auto()  # Successfully restarted and running
    FAILED = auto()  # Restart failed


@dataclass(slots=True)
class ServiceRestartStatus:
    """Status of a single service restart operation.

    Attributes:
        service_name: Name of the service (e.g., 'ai-yolo26')
        status: Current restart status
        started_at: When the restart started (None if pending)
        completed_at: When the restart completed (None if not done)
        error: Error message if failed
    """

    service_name: str
    status: RestartStatus = RestartStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "service_name": self.service_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ServiceRestartStatus:
        """Create from dictionary."""
        started_at = None
        if data.get("started_at"):
            started_at = datetime.fromisoformat(data["started_at"])

        completed_at = None
        if data.get("completed_at"):
            completed_at = datetime.fromisoformat(data["completed_at"])

        return cls(
            service_name=data["service_name"],
            status=RestartStatus(data["status"]),
            started_at=started_at,
            completed_at=completed_at,
            error=data.get("error"),
        )


@dataclass(slots=True)
class ApplyResult:
    """Result of applying GPU configuration changes.

    Attributes:
        success: Whether the overall operation succeeded
        operation_id: Unique identifier for tracking this operation
        started_at: When the operation started
        completed_at: When the operation completed (None if still running)
        changed_services: List of services that were changed
        service_statuses: Per-service restart statuses
        error: Overall error message if failed
    """

    success: bool
    operation_id: str
    started_at: datetime
    completed_at: datetime | None = None
    changed_services: list[str] = field(default_factory=list)
    service_statuses: dict[str, ServiceRestartStatus] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "operation_id": self.operation_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "changed_services": self.changed_services,
            "service_statuses": {
                name: status.to_dict() for name, status in self.service_statuses.items()
            },
            "error": self.error,
        }


@dataclass
class GpuAssignment:
    """Represents a GPU assignment for a service.

    Attributes:
        service_name: Name of the AI service (e.g., 'ai-yolo26', 'ai-llm')
        gpu_index: Index of the GPU assigned (0-based)
        vram_limit_mb: Optional VRAM limit in megabytes
        vram_budget_override: Optional VRAM budget override in GB (alias for vram_limit_mb)
    """

    service_name: str
    gpu_index: int
    vram_limit_mb: int | None = None
    vram_budget_override: float | None = None

    def __post_init__(self) -> None:
        """Sync vram_limit_mb and vram_budget_override fields."""
        # If vram_budget_override is set but vram_limit_mb is not, convert GB to MB
        if self.vram_budget_override is not None and self.vram_limit_mb is None:
            self.vram_limit_mb = int(self.vram_budget_override * 1024)
        # If vram_limit_mb is set but vram_budget_override is not, convert MB to GB
        elif self.vram_limit_mb is not None and self.vram_budget_override is None:
            self.vram_budget_override = self.vram_limit_mb / 1024.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "service_name": self.service_name,
            "gpu_index": self.gpu_index,
            "vram_limit_mb": self.vram_limit_mb,
            "vram_budget_override": self.vram_budget_override,
        }


class GpuConfigService:
    """Service for managing GPU configuration and container restarts.

    This service handles the complete workflow for applying GPU configuration
    changes to AI service containers:

    1. Load current GPU assignments from configuration
    2. Generate docker-compose override file with GPU settings
    3. Diff against previous config to find changed services
    4. Restart only changed services via podman-compose
    5. Track restart progress in Redis

    The service supports both Docker and Podman, using podman-compose for
    container operations when available, falling back to docker-compose.

    Simple file-writing API (for routes):
        service = GpuConfigService(config_dir=Path("config"))
        await service.write_config_files(assignments, strategy)

    Full orchestration API (for background tasks):
        service = GpuConfigService(redis_client=redis, docker_client=docker)
        result = await service.apply_gpu_config(assignments)
    """

    # Default compose file paths
    DEFAULT_COMPOSE_FILE = "docker-compose.prod.yml"
    OVERRIDE_FILE_NAME = "docker-compose.gpu-override.yml"

    # Subprocess timeout for compose commands
    COMPOSE_TIMEOUT = 120.0  # 2 minutes

    # Redis key TTL for operation status (1 hour)
    OPERATION_STATUS_TTL = 3600

    def __init__(
        self,
        redis_client: RedisClient | None = None,
        docker_client: DockerClient | None = None,
        compose_file_path: str | Path | None = None,
        project_root: str | Path | None = None,
        config_dir: Path | None = None,
    ) -> None:
        """Initialize the GPU configuration service.

        Args:
            redis_client: RedisClient for progress tracking and caching.
                If None, progress tracking is disabled.
            docker_client: DockerClient for container operations.
                If None, uses subprocess for compose commands.
            compose_file_path: Path to the main docker-compose file.
                Defaults to docker-compose.prod.yml in project root.
            project_root: Path to the project root directory.
                Used for locating compose files and override output.
            config_dir: Directory for config files (simple API). Defaults to 'config'.
        """
        self._redis = redis_client
        self._docker_client = docker_client

        # Determine project root
        if project_root:
            self._project_root = Path(project_root)
        else:
            # Default to parent of backend directory
            self._project_root = Path(__file__).parent.parent.parent

        # Set compose file path
        if compose_file_path:
            self._compose_file = Path(compose_file_path)
        else:
            self._compose_file = self._project_root / self.DEFAULT_COMPOSE_FILE

        # Config directory for simple file writing API
        self.config_dir = config_dir if config_dir is not None else Path("config")
        self.override_file = self.config_dir / "docker-compose.gpu-override.yml"
        self.assignments_file = self.config_dir / "gpu-assignments.yml"

        # Override file for full orchestration API is in project root
        self._override_file = self._project_root / self.OVERRIDE_FILE_NAME

        # Current assignments cache
        self._current_assignments: dict[str, GpuAssignment] = {}

        logger.info(
            "GpuConfigService initialized",
            extra={
                "compose_file": str(self._compose_file),
                "override_file": str(self._override_file),
                "config_dir": str(self.config_dir),
                "redis_enabled": redis_client is not None,
            },
        )

    # =========================================================================
    # Simple File Writing API (used by routes)
    # =========================================================================

    def generate_override_content(self, assignments: list[GpuAssignment]) -> str:
        """Generate docker-compose.gpu-override.yml content.

        Creates a docker-compose override file that pins services to specific
        GPUs using the NVIDIA container runtime.

        Args:
            assignments: List of GPU assignments for services.

        Returns:
            YAML content string with header comment and services configuration.
        """
        services: dict[str, dict] = {}

        for assignment in assignments:
            service_config: dict = {
                "deploy": {
                    "resources": {
                        "reservations": {
                            "devices": [
                                {
                                    "driver": "nvidia",
                                    "device_ids": [str(assignment.gpu_index)],
                                    "capabilities": ["gpu"],
                                }
                            ]
                        }
                    }
                }
            }

            if assignment.vram_budget_override is not None:
                service_config["environment"] = [
                    f"VRAM_BUDGET_GB={assignment.vram_budget_override}"
                ]

            services[assignment.service_name] = service_config

        content: dict = {"services": services}

        header = "# Auto-generated by GPU Config Service - DO NOT EDIT MANUALLY\n"
        yaml_content: str = yaml.dump(content, default_flow_style=False, sort_keys=False)
        return header + yaml_content

    def generate_assignments_content(
        self,
        assignments: list[GpuAssignment],
        strategy: str,
    ) -> str:
        """Generate human-readable gpu-assignments.yml.

        Args:
            assignments: List of GPU assignments for services.
            strategy: The assignment strategy used (e.g., 'manual', 'vram_based').

        Returns:
            YAML content string with header comment and assignment details.
        """
        data: dict = {
            "generated_at": datetime.now(UTC).isoformat(),
            "strategy": strategy,
            "assignments": {
                a.service_name: {
                    "gpu": a.gpu_index,
                    "vram_budget": a.vram_budget_override,
                }
                for a in assignments
            },
        }

        header = "# Auto-generated - for reference only\n"
        yaml_content: str = yaml.dump(data, default_flow_style=False, sort_keys=False)
        return header + yaml_content

    async def write_config_files(
        self,
        assignments: list[GpuAssignment],
        strategy: str,
    ) -> tuple[Path, Path]:
        """Write both config files to disk.

        Creates the config directory if it doesn't exist, then writes:
        1. docker-compose.gpu-override.yml - For docker-compose/podman-compose
        2. gpu-assignments.yml - Human-readable reference file

        Args:
            assignments: List of GPU assignments for services.
            strategy: The assignment strategy used.

        Returns:
            Tuple of (override_file_path, assignments_file_path).

        Raises:
            OSError: If directory creation or file writing fails.
        """
        logger.info(
            f"Writing GPU config files: strategy={strategy}, assignments={len(assignments)}"
        )

        # Create config directory if missing
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Write override file
        override_content = self.generate_override_content(assignments)
        self.override_file.write_text(override_content)
        logger.debug(f"Wrote override file: {self.override_file}")

        # Write assignments file
        assignments_content = self.generate_assignments_content(assignments, strategy)
        self.assignments_file.write_text(assignments_content)
        logger.debug(f"Wrote assignments file: {self.assignments_file}")

        logger.info(
            f"GPU config files written successfully: {self.override_file}, {self.assignments_file}"
        )

        return self.override_file, self.assignments_file

    # =========================================================================
    # Full Orchestration API
    # =========================================================================

    async def apply_gpu_config(
        self,
        new_assignments: dict[str, GpuAssignment] | None = None,
    ) -> ApplyResult:
        """Apply GPU configuration changes by restarting affected services.

        Full workflow:
        1. Load current assignments if new_assignments not provided
        2. Generate docker-compose.gpu-override.yml
        3. Diff against previous config to find changed services
        4. Restart only changed services (not all)
        5. Track restart progress in Redis

        Args:
            new_assignments: New GPU assignments to apply. If None, loads
                from the current configuration source.

        Returns:
            ApplyResult with operation details and per-service status.
        """
        operation_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)

        result = ApplyResult(
            success=False,
            operation_id=operation_id,
            started_at=started_at,
        )

        try:
            # Load new assignments if not provided
            if new_assignments is None:
                new_assignments = await self._load_assignments()

            # Get previous assignments
            old_assignments = self._current_assignments.copy()

            # Find which services changed
            changed_services = self._diff_assignments(old_assignments, new_assignments)
            result.changed_services = changed_services

            if not changed_services:
                logger.info(
                    "No GPU configuration changes detected",
                    extra={"operation_id": operation_id},
                )
                result.success = True
                result.completed_at = datetime.now(UTC)
                return result

            logger.info(
                f"GPU configuration changes detected for {len(changed_services)} services",
                extra={
                    "operation_id": operation_id,
                    "changed_services": changed_services,
                },
            )

            # Generate override file
            await self._generate_override_file(new_assignments)

            # Initialize service statuses
            for service_name in changed_services:
                result.service_statuses[service_name] = ServiceRestartStatus(
                    service_name=service_name,
                    status=RestartStatus.PENDING,
                )

            # Persist initial status to Redis
            await self._persist_operation_status(result)

            # Restart each changed service
            all_success = True
            for service_name in changed_services:
                service_status = result.service_statuses[service_name]
                service_status.status = RestartStatus.RESTARTING
                service_status.started_at = datetime.now(UTC)
                await self._persist_operation_status(result)

                success = await self._recreate_service(service_name)

                if success:
                    service_status.status = RestartStatus.RUNNING
                    service_status.completed_at = datetime.now(UTC)
                else:
                    service_status.status = RestartStatus.FAILED
                    service_status.completed_at = datetime.now(UTC)
                    service_status.error = f"Failed to restart service {service_name}"
                    all_success = False

                await self._persist_operation_status(result)

            # Update current assignments cache on success
            if all_success:
                self._current_assignments = new_assignments.copy()

            result.success = all_success
            result.completed_at = datetime.now(UTC)
            await self._persist_operation_status(result)

            return result

        except Exception as e:
            logger.error(
                f"Failed to apply GPU configuration: {e}",
                extra={"operation_id": operation_id},
                exc_info=True,
            )
            result.error = str(e)
            result.completed_at = datetime.now(UTC)
            await self._persist_operation_status(result)
            return result

    async def get_container_status(
        self,
        service_names: list[str],
    ) -> dict[str, str | None]:
        """Get the current status of containers for the specified services.

        Args:
            service_names: List of service names to check.

        Returns:
            Dictionary mapping service name to container status string
            (e.g., 'running', 'exited', 'starting') or None if not found.
        """
        if self._docker_client is None:
            logger.warning("Docker client not available for container status check")
            return dict.fromkeys(service_names, None)

        result: dict[str, str | None] = {}

        for service_name in service_names:
            try:
                container = await self._docker_client.get_container_by_name(service_name)
                if container:
                    result[service_name] = await self._docker_client.get_container_status(
                        container.id
                    )
                else:
                    result[service_name] = None
            except Exception as e:
                logger.warning(
                    f"Failed to get container status for {service_name}: {e}",
                    extra={"service_name": service_name},
                )
                result[service_name] = None

        return result

    async def get_operation_status(self, operation_id: str) -> ApplyResult | None:
        """Get the status of a GPU configuration operation.

        Args:
            operation_id: The operation ID to look up.

        Returns:
            ApplyResult if found, None otherwise.
        """
        if self._redis is None:
            return None

        try:
            key = f"{REDIS_GPU_CONFIG_PREFIX}:operation:{operation_id}"
            data = await self._redis.get(key)
            if data is None:
                return None

            return self._result_from_dict(data)
        except Exception as e:
            logger.error(f"Failed to get operation status: {e}")
            return None

    def _diff_assignments(
        self,
        old: dict[str, GpuAssignment],
        new: dict[str, GpuAssignment],
    ) -> list[str]:
        """Determine which services changed between old and new assignments.

        Args:
            old: Previous GPU assignments by service name.
            new: New GPU assignments by service name.

        Returns:
            List of service names that changed.
        """
        changed: list[str] = []

        # Check for added or modified services
        for service_name, new_assignment in new.items():
            old_assignment = old.get(service_name)
            if old_assignment is None or (
                old_assignment.gpu_index != new_assignment.gpu_index
                or old_assignment.vram_limit_mb != new_assignment.vram_limit_mb
            ):
                changed.append(service_name)

        # Check for removed services
        for service_name in old:
            if service_name not in new:
                changed.append(service_name)

        return changed

    # =========================================================================
    # Internal Methods
    # =========================================================================

    async def _load_assignments(self) -> dict[str, GpuAssignment]:
        """Load GPU assignments from the configuration source.

        Returns:
            Dictionary of service name to GpuAssignment.
        """
        return {}

    async def _generate_override_file(
        self,
        assignments: dict[str, GpuAssignment],
    ) -> None:
        """Generate docker-compose.gpu-override.yml with GPU assignments.

        Args:
            assignments: GPU assignments by service name.
        """
        override_content = self._build_override_content(assignments)
        self._override_file.write_text(override_content)

        logger.info(
            f"Generated GPU override file: {self._override_file}",
            extra={"services": list(assignments.keys())},
        )

    def _build_override_content(
        self,
        assignments: dict[str, GpuAssignment],
    ) -> str:
        """Build the docker-compose override YAML content.

        Args:
            assignments: GPU assignments by service name.

        Returns:
            YAML content string for the override file.
        """
        services: dict[str, Any] = {}

        for service_name, assignment in assignments.items():
            service_config: dict[str, Any] = {
                "environment": [
                    f"NVIDIA_VISIBLE_DEVICES={assignment.gpu_index}",
                ],
            }

            if assignment.vram_limit_mb is not None:
                service_config["deploy"] = {
                    "resources": {
                        "reservations": {
                            "devices": [
                                {
                                    "driver": "nvidia",
                                    "device_ids": [str(assignment.gpu_index)],
                                    "capabilities": ["gpu"],
                                }
                            ]
                        }
                    }
                }

            services[service_name] = service_config

        override_doc = {
            "version": "3.8",
            "services": services,
        }

        header = (
            "# GPU Configuration Override\n"
            "# Generated by GpuConfigService\n"
            f"# Generated at: {datetime.now(UTC).isoformat()}\n"
            "#\n"
            "# This file is auto-generated. Do not edit manually.\n"
            "#\n"
        )

        yaml_content: str = yaml.dump(override_doc, default_flow_style=False, sort_keys=False)
        return header + yaml_content

    async def _recreate_service(self, service_name: str) -> bool:
        """Restart a single service via podman-compose or docker-compose.

        Args:
            service_name: Name of the service to restart.

        Returns:
            True if restart succeeded, False otherwise.
        """
        logger.info(
            f"Restarting service via compose: {service_name}",
            extra={"service_name": service_name},
        )

        compose_cmd = await self._get_compose_command()
        if compose_cmd is None:
            logger.error("Neither podman-compose nor docker-compose found")
            return False

        cmd = [
            compose_cmd,
            "-f",
            str(self._compose_file),
            "-f",
            str(self._override_file),
            "up",
            "-d",
            "--force-recreate",
            "--no-deps",
            service_name,
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._project_root),
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.COMPOSE_TIMEOUT,
                )
            except TimeoutError:
                logger.error(
                    f"Compose command timed out for {service_name}",
                    extra={
                        "service_name": service_name,
                        "timeout": self.COMPOSE_TIMEOUT,
                    },
                )
                process.kill()
                await process.wait()
                return False

            if process.returncode == 0:
                logger.info(
                    f"Successfully restarted {service_name}",
                    extra={
                        "service_name": service_name,
                        "returncode": 0,
                        "stdout": stdout.decode().strip()[:500],
                    },
                )
                return True
            else:
                logger.error(
                    f"Failed to restart {service_name}: exit code {process.returncode}",
                    extra={
                        "service_name": service_name,
                        "returncode": process.returncode,
                        "stderr": stderr.decode().strip()[:500],
                    },
                )
                return False

        except FileNotFoundError:
            logger.error(
                f"Compose command not found: {compose_cmd}",
                extra={"compose_cmd": compose_cmd},
            )
            return False
        except Exception as e:
            logger.error(
                f"Error restarting {service_name}: {e}",
                extra={"service_name": service_name},
                exc_info=True,
            )
            return False

    async def _get_compose_command(self) -> str | None:
        """Determine which compose command is available.

        Returns:
            Command string ('podman-compose' or 'docker-compose') or None.
        """
        for cmd in ["podman-compose", "docker-compose", "docker compose"]:
            try:
                if " " in cmd:
                    parts = cmd.split()
                    process = await asyncio.create_subprocess_exec(
                        *parts,
                        "--version",
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                else:
                    process = await asyncio.create_subprocess_exec(
                        cmd,
                        "--version",
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                await process.wait()
                if process.returncode == 0:
                    logger.debug(f"Using compose command: {cmd}")
                    return cmd
            except FileNotFoundError:
                continue

        return None

    async def _persist_operation_status(self, result: ApplyResult) -> None:
        """Persist operation status to Redis for progress tracking.

        Args:
            result: The ApplyResult to persist.
        """
        if self._redis is None:
            return

        try:
            key = f"{REDIS_GPU_CONFIG_PREFIX}:operation:{result.operation_id}"
            await self._redis.set(
                key,
                result.to_dict(),
                expire=self.OPERATION_STATUS_TTL,
            )
        except Exception as e:
            logger.warning(
                f"Failed to persist operation status to Redis: {e}",
                extra={"operation_id": result.operation_id},
            )

    def _result_from_dict(self, data: dict[str, Any]) -> ApplyResult:
        """Create ApplyResult from dictionary.

        Args:
            data: Dictionary data from Redis.

        Returns:
            ApplyResult instance.
        """
        started_at = datetime.fromisoformat(data["started_at"])
        completed_at = None
        if data.get("completed_at"):
            completed_at = datetime.fromisoformat(data["completed_at"])

        service_statuses: dict[str, ServiceRestartStatus] = {}
        for name, status_data in data.get("service_statuses", {}).items():
            service_statuses[name] = ServiceRestartStatus.from_dict(status_data)

        return ApplyResult(
            success=data["success"],
            operation_id=data["operation_id"],
            started_at=started_at,
            completed_at=completed_at,
            changed_services=data.get("changed_services", []),
            service_statuses=service_statuses,
            error=data.get("error"),
        )

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_current_assignments(self) -> dict[str, GpuAssignment]:
        """Get the currently cached GPU assignments.

        Returns:
            Dictionary of service name to GpuAssignment.
        """
        return self._current_assignments.copy()

    def set_current_assignments(self, assignments: dict[str, GpuAssignment]) -> None:
        """Set the current GPU assignments cache.

        Args:
            assignments: New assignments to cache.
        """
        self._current_assignments = assignments.copy()
