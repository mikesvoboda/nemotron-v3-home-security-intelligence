"""GPU configuration API routes for multi-GPU support.

This module provides endpoints for:
1. GPU detection and listing (GET /api/system/gpus)
2. GPU configuration management (GET/PUT /api/system/gpu-config)
3. Configuration application and service restart (POST /api/system/gpu-config/apply)
4. Apply status monitoring (GET /api/system/gpu-config/status)
5. GPU re-detection (POST /api/system/gpu-config/detect)
6. Strategy preview (GET /api/system/gpu-config/preview)

The frontend GPU configuration panel uses these endpoints to:
- Display detected GPUs with VRAM capacity
- Configure service-to-GPU assignments
- Apply configuration and monitor service restarts
- Preview auto-assignment strategies

Related Issues:
    - NEM-3318: Implement GPU configuration API routes
    - NEM-3292: Multi-GPU Support Epic

Design Document:
    See docs/plans/2025-01-23-multi-gpu-support-design.md
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.gpu_config import (
    AiServiceInfo,
    AiServicesResponse,
    GpuApplyResponse,
    GpuAssignment,
    GpuAssignmentStrategy,
    GpuConfigAssignmentChange,
    GpuConfigExportData,
    GpuConfigImportRequest,
    GpuConfigImportResponse,
    GpuConfigImportValidation,
    GpuConfigPreviewResponse,
    GpuConfigResponse,
    GpuConfigRollbackRequest,
    GpuConfigRollbackResponse,
    GpuConfigStatusResponse,
    GpuConfigUpdateRequest,
    GpuConfigUpdateResponse,
    GpuConfigVersionDetail,
    GpuConfigVersionDiffResponse,
    GpuConfigVersionListResponse,
    GpuConfigVersionSummary,
    GpuDeviceResponse,
    GpuDevicesResponse,
    ServiceHealthResponse,
    ServiceHealthStatus,
    ServiceStatus,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.core.redis import RedisClient, get_redis_client_sync
from backend.models.gpu_config import (
    GpuConfiguration,
    GpuConfigurationVersion,
    SystemSetting,
)
from backend.models.gpu_config import (
    GpuDevice as GpuDeviceModel,
)
from backend.services.gpu_config_service import (
    REDIS_GPU_CONFIG_PREFIX,
    ApplyResult,
    GpuConfigService,
    RestartStatus,
    ServiceRestartStatus,
)
from backend.services.gpu_config_service import (
    GpuAssignment as GpuAssignmentDataclass,
)
from backend.services.gpu_detection_service import (
    AI_SERVICE_VRAM_REQUIREMENTS_MB,
    GpuDevice,
    get_gpu_detection_service,
)

logger = get_logger(__name__)

# Router with /api/system prefix to match frontend expectations
router = APIRouter(prefix="/api/system", tags=["gpu-config"])

# Redis key for current apply operation ID
# The actual operation status is stored via GpuConfigService._persist_operation_status
REDIS_CURRENT_OPERATION_KEY = f"{REDIS_GPU_CONFIG_PREFIX}:current_operation_id"

# Fallback in-memory state for when Redis is unavailable (development mode)
# NOTE: This is ONLY used when Redis is not configured. In production, always use Redis.
_apply_state_fallback: dict[str, object] = {
    "in_progress": False,
    "operation_id": None,
    "services_pending": [],
    "services_completed": [],
    "service_statuses": [],
    "last_updated": None,
}

# Constants
GPU_STRATEGY_SETTING_KEY = "gpu_assignment_strategy"
DEFAULT_STRATEGY = GpuAssignmentStrategy.MANUAL


# =============================================================================
# Redis State Helpers
# =============================================================================


async def _get_redis_client() -> RedisClient | None:
    """Get Redis client if available.

    Returns:
        RedisClient if initialized, None otherwise.
    """
    return get_redis_client_sync()


async def _get_current_operation_id(redis: RedisClient | None) -> str | None:
    """Get the current apply operation ID from Redis.

    Args:
        redis: Redis client (may be None)

    Returns:
        Operation ID if an operation is in progress, None otherwise.
    """
    if redis is None:
        return _apply_state_fallback.get("operation_id")  # type: ignore[return-value]

    try:
        return await redis.get(REDIS_CURRENT_OPERATION_KEY)
    except Exception as e:
        logger.warning(f"Failed to get current operation ID from Redis: {e}")
        return None


async def _set_current_operation_id(redis: RedisClient | None, operation_id: str | None) -> None:
    """Set the current apply operation ID in Redis.

    Args:
        redis: Redis client (may be None)
        operation_id: Operation ID to set, or None to clear
    """
    if redis is None:
        _apply_state_fallback["operation_id"] = operation_id
        _apply_state_fallback["in_progress"] = operation_id is not None
        return

    try:
        if operation_id is None:
            await redis.delete(REDIS_CURRENT_OPERATION_KEY)
        else:
            # Set with 1 hour TTL to auto-cleanup stuck operations
            await redis.set(REDIS_CURRENT_OPERATION_KEY, operation_id, expire=3600)
    except Exception as e:
        logger.warning(f"Failed to set current operation ID in Redis: {e}")


# =============================================================================
# Helper Functions
# =============================================================================


def _gpu_device_to_response(device: GpuDevice) -> GpuDeviceResponse:
    """Convert GpuDevice dataclass to GpuDeviceResponse schema."""
    return GpuDeviceResponse(
        index=device.index,
        name=device.name,
        vram_total_mb=device.vram_total_mb,
        vram_used_mb=device.vram_used_mb,
        compute_capability=device.compute_capability,
    )


async def _get_current_strategy(db: AsyncSession) -> GpuAssignmentStrategy:
    """Get the current GPU assignment strategy from system settings."""
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == GPU_STRATEGY_SETTING_KEY)
    )
    setting = result.scalar_one_or_none()

    if setting and "strategy" in setting.value:
        strategy_value = setting.value["strategy"]
        try:
            return GpuAssignmentStrategy(strategy_value)
        except ValueError:
            logger.warning(f"Invalid strategy value in settings: {strategy_value}")

    return DEFAULT_STRATEGY


async def _set_current_strategy(db: AsyncSession, strategy: GpuAssignmentStrategy) -> None:
    """Set the current GPU assignment strategy in system settings."""
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == GPU_STRATEGY_SETTING_KEY)
    )
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = {"strategy": strategy.value}
    else:
        new_setting = SystemSetting(
            key=GPU_STRATEGY_SETTING_KEY,
            value={"strategy": strategy.value},
        )
        db.add(new_setting)


async def _get_assignments_from_db(db: AsyncSession) -> list[GpuAssignment]:
    """Get all GPU assignments from the database."""
    result = await db.execute(select(GpuConfiguration).where(GpuConfiguration.enabled.is_(True)))
    configs = result.scalars().all()

    assignments = []
    for config in configs:
        assignments.append(
            GpuAssignment(
                service=config.service_name,
                gpu_index=config.gpu_index,
                vram_budget_override=config.vram_budget_override,
                # Affinity constraints with defaults if None (NEM-4944)
                exclusive_gpu=config.exclusive_gpu if config.exclusive_gpu is not None else False,
                priority_weight=config.priority_weight
                if config.priority_weight is not None
                else 50,
                incompatible_with=config.incompatible_with,
            )
        )

    return assignments


async def _get_latest_config_update_time(db: AsyncSession) -> datetime | None:
    """Get the most recent configuration update timestamp."""
    from sqlalchemy import func

    result = await db.execute(select(func.max(GpuConfiguration.updated_at)))
    return result.scalar_one_or_none()


def _validate_vram_assignments(
    assignments: list[GpuAssignment],
    gpus: list[GpuDevice],
) -> list[str]:
    """Validate VRAM assignments and return warnings for over-budget GPUs.

    Args:
        assignments: List of service-to-GPU assignments
        gpus: List of detected GPUs

    Returns:
        List of warning messages for any VRAM overages
    """
    warnings: list[str] = []

    # Build GPU VRAM map
    gpu_vram: dict[int, int] = {gpu.index: gpu.vram_total_mb for gpu in gpus}

    # Calculate VRAM usage per GPU
    gpu_usage: dict[int, int] = {gpu.index: 0 for gpu in gpus}

    for assignment in assignments:
        if assignment.gpu_index is None:
            continue

        if assignment.gpu_index not in gpu_vram:
            warnings.append(
                f"Service '{assignment.service}' assigned to non-existent GPU {assignment.gpu_index}"
            )
            continue

        # Use override if specified, otherwise use default requirement
        if assignment.vram_budget_override is not None:
            vram_mb = int(assignment.vram_budget_override * 1024)  # GB to MB
        else:
            vram_mb = AI_SERVICE_VRAM_REQUIREMENTS_MB.get(assignment.service, 0)

        gpu_usage[assignment.gpu_index] += vram_mb

    # Check for overages
    for gpu_index, used_mb in gpu_usage.items():
        total_mb = gpu_vram.get(gpu_index, 0)
        if used_mb > total_mb > 0:
            over_mb = used_mb - total_mb
            warnings.append(
                f"GPU {gpu_index} is over budget by {over_mb} MB "
                f"(assigned: {used_mb} MB, available: {total_mb} MB)"
            )

    return warnings


def _validate_affinity_constraints(assignments: list[GpuAssignment]) -> list[str]:
    """Validate GPU affinity constraints and return warnings for violations.

    Checks for:
    1. Exclusive GPU violations: services marked exclusive sharing a GPU
    2. Incompatibility violations: services marked as incompatible on same GPU

    Args:
        assignments: List of service-to-GPU assignments

    Returns:
        List of warning messages for any affinity constraint violations
    """
    warnings: list[str] = []

    # Build map of GPU index to assigned services
    gpu_services: dict[int, list[GpuAssignment]] = {}
    for assignment in assignments:
        if assignment.gpu_index is not None:
            if assignment.gpu_index not in gpu_services:
                gpu_services[assignment.gpu_index] = []
            gpu_services[assignment.gpu_index].append(assignment)

    # Check exclusive GPU constraints
    for gpu_index, services in gpu_services.items():
        exclusive_services = [s for s in services if s.exclusive_gpu]
        if exclusive_services:
            for exclusive in exclusive_services:
                other_services = [s for s in services if s.service != exclusive.service]
                if other_services:
                    other_names = [s.service for s in other_services]
                    warnings.append(
                        f"Service '{exclusive.service}' requires exclusive GPU but shares "
                        f"GPU {gpu_index} with: {', '.join(other_names)}"
                    )

    # Check incompatibility constraints
    for gpu_index, services in gpu_services.items():
        for assignment in services:
            if assignment.incompatible_with:
                for incompatible_service in assignment.incompatible_with:
                    # Check if incompatible service is on the same GPU
                    for other in services:
                        if other.service == incompatible_service:
                            warnings.append(
                                f"Service '{assignment.service}' is incompatible with "
                                f"'{incompatible_service}' but both are on GPU {gpu_index}"
                            )

    return warnings


async def _save_assignments_to_db(
    db: AsyncSession,
    assignments: list[GpuAssignment],
    strategy: GpuAssignmentStrategy,
) -> None:
    """Save GPU assignments to the database."""
    # Get existing configurations
    result = await db.execute(select(GpuConfiguration))
    existing = {config.service_name: config for config in result.scalars().all()}

    for assignment in assignments:
        if assignment.service in existing:
            # Update existing
            config = existing[assignment.service]
            config.gpu_index = assignment.gpu_index
            config.strategy = strategy.value
            config.vram_budget_override = assignment.vram_budget_override
            config.enabled = True
            # Update affinity constraints (NEM-4944)
            config.exclusive_gpu = assignment.exclusive_gpu
            config.priority_weight = assignment.priority_weight
            config.incompatible_with = assignment.incompatible_with
        else:
            # Create new
            config = GpuConfiguration(
                service_name=assignment.service,
                gpu_index=assignment.gpu_index,
                strategy=strategy.value,
                vram_budget_override=assignment.vram_budget_override,
                enabled=True,
                # Affinity constraints (NEM-4944)
                exclusive_gpu=assignment.exclusive_gpu,
                priority_weight=assignment.priority_weight,
                incompatible_with=assignment.incompatible_with,
            )
            db.add(config)


async def _update_gpu_devices_in_db(
    db: AsyncSession,
    devices: list[GpuDevice],
) -> None:
    """Update GPU devices in the database."""
    # Get existing devices
    result = await db.execute(select(GpuDeviceModel))
    existing = {device.gpu_index: device for device in result.scalars().all()}

    now = datetime.now(UTC)

    for device in devices:
        if device.index in existing:
            # Update existing
            db_device = existing[device.index]
            db_device.name = device.name
            db_device.vram_total_mb = device.vram_total_mb
            db_device.vram_available_mb = device.vram_available_mb
            db_device.compute_capability = device.compute_capability
            db_device.last_seen_at = now
        else:
            # Create new
            db_device = GpuDeviceModel(
                gpu_index=device.index,
                name=device.name,
                vram_total_mb=device.vram_total_mb,
                vram_available_mb=device.vram_available_mb,
                compute_capability=device.compute_capability,
                last_seen_at=now,
            )
            db.add(db_device)


def _calculate_auto_assignments(
    strategy: GpuAssignmentStrategy,
    gpus: list[GpuDevice],
    services: list[str] | None = None,
) -> tuple[list[GpuAssignment], list[str]]:
    """Calculate GPU assignments based on the given strategy.

    Args:
        strategy: Assignment strategy to use
        gpus: List of detected GPUs
        services: List of service names (defaults to AI_SERVICE_VRAM_REQUIREMENTS_MB keys)

    Returns:
        Tuple of (assignments, warnings)
    """
    if not gpus:
        return [], ["No GPUs detected - cannot calculate auto-assignments"]

    if services is None:
        services = list(AI_SERVICE_VRAM_REQUIREMENTS_MB.keys())

    assignments: list[GpuAssignment] = []
    warnings: list[str] = []

    if strategy == GpuAssignmentStrategy.MANUAL:
        # For manual, just return current assignments or defaults
        for service in services:
            assignments.append(
                GpuAssignment(
                    service=service,
                    gpu_index=0,  # Default to first GPU
                    vram_budget_override=None,
                )
            )

    elif strategy == GpuAssignmentStrategy.VRAM_BASED:
        # Assign largest models to GPU with most VRAM
        sorted_gpus = sorted(gpus, key=lambda g: g.vram_total_mb, reverse=True)
        sorted_services = sorted(
            services,
            key=lambda s: AI_SERVICE_VRAM_REQUIREMENTS_MB.get(s, 0),
            reverse=True,
        )

        gpu_remaining: dict[int, int] = {g.index: g.vram_total_mb for g in sorted_gpus}

        for service in sorted_services:
            vram_needed = AI_SERVICE_VRAM_REQUIREMENTS_MB.get(service, 0)
            assigned = False

            # Find GPU with enough VRAM
            for gpu in sorted_gpus:
                if gpu_remaining[gpu.index] >= vram_needed:
                    assignments.append(
                        GpuAssignment(
                            service=service,
                            gpu_index=gpu.index,
                            vram_budget_override=None,
                        )
                    )
                    gpu_remaining[gpu.index] -= vram_needed
                    assigned = True
                    break

            if not assigned:
                # Assign to GPU with most remaining space
                best_gpu = max(sorted_gpus, key=lambda g: gpu_remaining[g.index])
                assignments.append(
                    GpuAssignment(
                        service=service,
                        gpu_index=best_gpu.index,
                        vram_budget_override=None,
                    )
                )
                warnings.append(
                    f"Service '{service}' assigned to GPU {best_gpu.index} "
                    f"but may exceed VRAM budget"
                )

    elif strategy == GpuAssignmentStrategy.ISOLATION_FIRST:
        # LLM gets dedicated GPU, others share
        if len(gpus) >= 2:
            # LLM on largest GPU
            largest_gpu = max(gpus, key=lambda g: g.vram_total_mb)
            second_gpu = next(g for g in gpus if g.index != largest_gpu.index)

            for service in services:
                if service == "ai-llm":
                    assignments.append(
                        GpuAssignment(
                            service=service,
                            gpu_index=largest_gpu.index,
                            vram_budget_override=None,
                        )
                    )
                else:
                    assignments.append(
                        GpuAssignment(
                            service=service,
                            gpu_index=second_gpu.index,
                            vram_budget_override=None,
                        )
                    )
        else:
            # Only one GPU - everything goes there
            for service in services:
                assignments.append(
                    GpuAssignment(
                        service=service,
                        gpu_index=gpus[0].index,
                        vram_budget_override=None,
                    )
                )
            warnings.append(
                "Only one GPU detected - isolation strategy not possible, "
                "all services assigned to GPU 0"
            )

    elif strategy == GpuAssignmentStrategy.LATENCY_OPTIMIZED:
        # Critical path models (detector) on fastest GPU (highest compute capability)
        # Assume higher compute capability = faster
        def get_compute_score(gpu: GpuDevice) -> float:
            if gpu.compute_capability:
                try:
                    return float(gpu.compute_capability)
                except ValueError:
                    pass
            return 0.0

        sorted_gpus = sorted(gpus, key=get_compute_score, reverse=True)
        fastest_gpu = sorted_gpus[0]

        critical_services = ["ai-yolo26", "ai-enrichment"]

        for service in services:
            if service in critical_services:
                assignments.append(
                    GpuAssignment(
                        service=service,
                        gpu_index=fastest_gpu.index,
                        vram_budget_override=None,
                    )
                )
            else:
                # Non-critical services on other GPUs if available
                other_gpu = sorted_gpus[-1] if len(sorted_gpus) > 1 else fastest_gpu
                assignments.append(
                    GpuAssignment(
                        service=service,
                        gpu_index=other_gpu.index,
                        vram_budget_override=None,
                    )
                )

    elif strategy == GpuAssignmentStrategy.BALANCED:
        # Distribute VRAM evenly across GPUs
        gpu_usage: dict[int, int] = {g.index: 0 for g in gpus}

        sorted_services = sorted(
            services,
            key=lambda s: AI_SERVICE_VRAM_REQUIREMENTS_MB.get(s, 0),
            reverse=True,
        )

        for service in sorted_services:
            vram_needed = AI_SERVICE_VRAM_REQUIREMENTS_MB.get(service, 0)

            # Find GPU with least usage
            min_gpu = min(gpus, key=lambda g: gpu_usage[g.index])
            assignments.append(
                GpuAssignment(
                    service=service,
                    gpu_index=min_gpu.index,
                    vram_budget_override=None,
                )
            )
            gpu_usage[min_gpu.index] += vram_needed

    return assignments, warnings


# =============================================================================
# API Endpoints
# =============================================================================


@router.get(
    "/gpus",
    response_model=GpuDevicesResponse,
    summary="List detected GPUs",
    description="Returns all GPUs detected on the system with hardware specs and utilization.",
    responses={
        500: {"description": "GPU detection failed"},
    },
)
async def list_gpus() -> GpuDevicesResponse:
    """List all detected GPU devices.

    Calls the GPU detection service to scan for available GPUs using pynvml
    or nvidia-smi fallback. Returns hardware specifications including VRAM
    capacity and current utilization.

    Returns:
        GpuDevicesResponse containing list of detected GPUs
    """
    try:
        service = get_gpu_detection_service()
        devices = await service.detect_gpus()

        return GpuDevicesResponse(gpus=[_gpu_device_to_response(device) for device in devices])

    except Exception as e:
        logger.warning(f"GPU detection failed: {e}")
        return GpuDevicesResponse(gpus=[])


@router.get(
    "/gpu-config",
    response_model=GpuConfigResponse,
    summary="Get GPU configuration",
    description="Returns current GPU assignment strategy and service-to-GPU mappings.",
    responses={
        500: {"description": "Failed to load configuration"},
    },
)
async def get_gpu_config(
    db: AsyncSession = Depends(get_db),
) -> GpuConfigResponse:
    """Get the current GPU configuration.

    Loads the current assignment strategy from system settings and all
    service-to-GPU assignments from the gpu_configurations table.

    Args:
        db: Database session

    Returns:
        GpuConfigResponse with current strategy and assignments
    """
    try:
        strategy = await _get_current_strategy(db)
        assignments = await _get_assignments_from_db(db)
        updated_at = await _get_latest_config_update_time(db)

        # If no assignments exist, create defaults for all known services
        if not assignments:
            for service in AI_SERVICE_VRAM_REQUIREMENTS_MB:
                assignments.append(
                    GpuAssignment(
                        service=service,
                        gpu_index=0,  # Default to first GPU
                        vram_budget_override=None,
                    )
                )

        return GpuConfigResponse(
            strategy=strategy,
            assignments=assignments,
            updated_at=updated_at,
        )

    except Exception as e:
        logger.exception("Failed to load GPU configuration")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load GPU configuration: {e}",
        ) from e


@router.put(
    "/gpu-config",
    response_model=GpuConfigUpdateResponse,
    summary="Update GPU configuration",
    description="Updates GPU assignments. Does not apply changes - use /apply endpoint.",
    responses={
        400: {"description": "Invalid configuration"},
        500: {"description": "Failed to save configuration"},
    },
)
async def update_gpu_config(
    request: GpuConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> GpuConfigUpdateResponse:
    """Update GPU configuration.

    Saves the new strategy and/or assignments to the database. Validates
    that VRAM budgets don't exceed GPU capacity and returns warnings for
    any over-budget assignments.

    Note: This endpoint does NOT apply the configuration or restart services.
    Use POST /gpu-config/apply after updating to apply changes.

    Args:
        request: Configuration update request
        db: Database session

    Returns:
        GpuConfigUpdateResponse with success status and warnings
    """
    try:
        warnings: list[str] = []

        # Get current strategy if not specified
        strategy = request.strategy
        if strategy is None:
            strategy = await _get_current_strategy(db)

        # Get current assignments if not specified
        assignments = request.assignments
        if assignments is None:
            assignments = await _get_assignments_from_db(db)

        # Validate VRAM assignments
        detection_service = get_gpu_detection_service()
        gpus = await detection_service.detect_gpus()
        vram_warnings = _validate_vram_assignments(assignments, gpus)
        warnings.extend(vram_warnings)

        # Validate affinity constraints (NEM-4944)
        affinity_warnings = _validate_affinity_constraints(assignments)
        warnings.extend(affinity_warnings)

        # Save strategy
        await _set_current_strategy(db, strategy)

        # Save assignments
        await _save_assignments_to_db(db, assignments, strategy)

        # Save version history (NEM-4945)
        await _save_version(
            db,
            strategy=strategy.value if hasattr(strategy, "value") else str(strategy),
            assignments=assignments,
            description="Configuration update",
            created_by="user",
        )

        await db.commit()

        logger.info(
            f"GPU configuration updated: strategy={strategy}, "
            f"assignments={len(assignments)}, warnings={len(warnings)}"
        )

        return GpuConfigUpdateResponse(
            success=True,
            warnings=warnings,
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception("Failed to save GPU configuration")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save GPU configuration: {e}",
        ) from e


@router.post(
    "/gpu-config/apply",
    response_model=GpuApplyResponse,
    summary="Apply GPU configuration",
    description="Applies current config and restarts affected services.",
    responses={
        409: {"description": "Apply operation already in progress"},
        500: {"description": "Failed to apply configuration"},
    },
)
async def apply_gpu_config(
    db: AsyncSession = Depends(get_db),
) -> GpuApplyResponse:
    """Apply GPU configuration and restart affected services.

    Generates the docker-compose GPU override file using the current
    configuration and triggers restarts for services whose assignments
    have changed.

    This endpoint returns immediately with the initial status. Use
    GET /gpu-config/status to poll for completion.

    **State Persistence (NEM-3547):**
    Apply operation status is persisted to Redis (when available) to survive
    server restarts and work across multiple backend replicas. Falls back to
    in-memory state for development environments without Redis.

    **Service Restart Behavior (NEM-3548):**
    Currently, service restarts are SIMULATED for MVP development safety.
    The config files are written correctly, but containers are not actually
    restarted. This is intentional to prevent disruption during development.

    To enable real container restarts, the GpuConfigService needs to be
    initialized with a docker_client and the apply_gpu_config method should
    be called instead of write_config_files. The _recreate_service method
    in GpuConfigService contains the actual podman-compose/docker-compose
    restart logic.

    Args:
        db: Database session

    Returns:
        GpuApplyResponse with initial apply status
    """
    global _apply_state_fallback  # noqa: PLW0603

    redis = await _get_redis_client()
    current_op_id = await _get_current_operation_id(redis)

    if current_op_id is not None:
        # Check if the operation is actually still in progress
        config_service = GpuConfigService(redis_client=redis)
        existing_result = await config_service.get_operation_status(current_op_id)
        if existing_result and existing_result.completed_at is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="GPU configuration apply already in progress",
            )
        # Operation completed, clear the stale ID
        await _set_current_operation_id(redis, None)

    try:
        # Get current configuration
        strategy = await _get_current_strategy(db)
        assignments = await _get_assignments_from_db(db)

        if not assignments:
            return GpuApplyResponse(
                success=True,
                warnings=["No GPU assignments configured"],
                restarted_services=[],
                service_statuses=[],
            )

        # Convert to dataclass format for config service
        config_assignments = [
            GpuAssignmentDataclass(
                service_name=a.service,
                gpu_index=a.gpu_index if a.gpu_index is not None else 0,
                vram_budget_override=a.vram_budget_override,
            )
            for a in assignments
            if a.gpu_index is not None
        ]

        # Create config service with Redis for state persistence
        config_service = GpuConfigService(redis_client=redis)

        # Generate docker-compose override file
        await config_service.write_config_files(
            assignments=config_assignments,
            strategy=strategy.value,
        )

        service_names = [a.service for a in assignments]

        # Create ApplyResult for Redis persistence
        import uuid

        operation_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)

        result = ApplyResult(
            success=False,
            operation_id=operation_id,
            started_at=started_at,
            changed_services=service_names,
            service_statuses={
                name: ServiceRestartStatus(
                    service_name=name,
                    status=RestartStatus.PENDING,
                )
                for name in service_names
            },
        )

        # Store current operation ID
        await _set_current_operation_id(redis, operation_id)

        # Persist initial status to Redis
        await config_service._persist_operation_status(result)

        # =====================================================================
        # SIMULATED RESTART (NEM-3548)
        # =====================================================================
        # Currently, we simulate service restarts for MVP development safety.
        # Config files are written correctly but containers are NOT restarted.
        #
        # To enable REAL container restarts:
        # 1. Initialize GpuConfigService with docker_client parameter
        # 2. Call config_service.apply_gpu_config() instead of write_config_files()
        # 3. The _recreate_service() method contains real restart logic using
        #    podman-compose or docker-compose subprocess calls
        #
        # This simulation is intentional for development environments to prevent
        # accidentally restarting production AI services during testing.
        # =====================================================================

        # Simulate immediate completion
        for service_name in service_names:
            result.service_statuses[service_name].status = RestartStatus.RUNNING
            result.service_statuses[service_name].completed_at = datetime.now(UTC)

        result.success = True
        result.completed_at = datetime.now(UTC)

        # Persist final status to Redis
        await config_service._persist_operation_status(result)

        # Clear current operation since it's complete
        await _set_current_operation_id(redis, None)

        # Update fallback state for development mode
        _apply_state_fallback = {
            "in_progress": False,
            "operation_id": None,
            "services_pending": [],
            "services_completed": service_names.copy(),
            "service_statuses": [
                ServiceStatus(
                    service=name,
                    status="running",
                    message="Configuration applied (simulated - containers not restarted)",
                )
                for name in service_names
            ],
            "last_updated": datetime.now(UTC),
        }

        logger.info(
            f"GPU configuration applied (simulated): strategy={strategy}, services={service_names}"
        )

        return GpuApplyResponse(
            success=True,
            warnings=[
                "Service restarts are simulated in development mode. "
                "Config files written but containers not restarted."
            ],
            restarted_services=service_names,
            service_statuses=[
                ServiceStatus(
                    service=name,
                    status="running",
                    message="Configuration applied (simulated)",
                )
                for name in service_names
            ],
        )

    except HTTPException:
        raise
    except Exception as e:
        await _set_current_operation_id(redis, None)
        logger.exception("Failed to apply GPU configuration")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply GPU configuration: {e}",
        ) from e


@router.get(
    "/gpu-config/status",
    response_model=GpuConfigStatusResponse,
    summary="Get apply operation status",
    description="Returns current status of GPU configuration apply operation.",
)
async def get_gpu_config_status() -> GpuConfigStatusResponse:
    """Get the status of the current or last apply operation.

    Returns the progress of service restarts after applying GPU configuration.
    Use this endpoint to poll for completion after calling POST /gpu-config/apply.

    **State Persistence (NEM-3547):**
    Status is retrieved from Redis (when available) to support multi-replica
    deployments and survive server restarts. Falls back to in-memory state
    for development environments without Redis.

    Returns:
        GpuConfigStatusResponse with apply operation status
    """
    redis = await _get_redis_client()
    current_op_id = await _get_current_operation_id(redis)

    # Try to get status from Redis first
    if current_op_id is not None and redis is not None:
        config_service = GpuConfigService(redis_client=redis)
        result = await config_service.get_operation_status(current_op_id)
        if result:
            # Convert ApplyResult to response format
            services_pending = []
            services_completed = []
            service_statuses = []

            for name, status in result.service_statuses.items():
                if status.status in (RestartStatus.PENDING, RestartStatus.RESTARTING):
                    services_pending.append(name)
                elif status.status == RestartStatus.RUNNING:
                    services_completed.append(name)
                elif status.status == RestartStatus.FAILED:
                    services_completed.append(name)  # Mark as completed but failed

                service_statuses.append(
                    ServiceStatus(
                        service=name,
                        status=status.status.value,
                        message=status.error if status.error else None,
                    )
                )

            return GpuConfigStatusResponse(
                in_progress=result.completed_at is None,
                services_pending=services_pending,
                services_completed=services_completed,
                service_statuses=service_statuses,
            )

    # Fallback to in-memory state for development mode
    pending: list[str] = list(_apply_state_fallback.get("services_pending", []))  # type: ignore[call-overload]
    completed: list[str] = list(_apply_state_fallback.get("services_completed", []))  # type: ignore[call-overload]
    statuses: list[ServiceStatus] = list(_apply_state_fallback.get("service_statuses", []))  # type: ignore[call-overload]
    return GpuConfigStatusResponse(
        in_progress=bool(_apply_state_fallback.get("in_progress", False)),
        services_pending=pending,
        services_completed=completed,
        service_statuses=statuses,
    )


@router.post(
    "/gpu-config/detect",
    response_model=GpuDevicesResponse,
    summary="Re-detect GPUs",
    description="Triggers a fresh GPU scan and updates the database.",
    responses={
        500: {"description": "GPU detection failed"},
    },
)
async def detect_gpus(
    db: AsyncSession = Depends(get_db),
) -> GpuDevicesResponse:
    """Re-scan for GPU devices and update the database.

    Forces a fresh GPU scan using pynvml or nvidia-smi fallback and
    updates the gpu_devices table with the detected hardware.

    Useful when GPUs are added or removed from the system.

    Args:
        db: Database session

    Returns:
        GpuDevicesResponse with newly detected GPUs
    """
    try:
        service = get_gpu_detection_service()
        devices = await service.detect_gpus()

        # Update database
        await _update_gpu_devices_in_db(db, devices)
        await db.commit()

        logger.info(f"GPU detection completed: {len(devices)} GPUs found")

        return GpuDevicesResponse(gpus=[_gpu_device_to_response(device) for device in devices])

    except Exception as e:
        await db.rollback()
        logger.exception("GPU detection failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GPU detection failed: {e}",
        ) from e


@router.get(
    "/gpu-config/preview",
    response_model=GpuConfigPreviewResponse,
    summary="Preview auto-assignment",
    description="Preview what assignments would result from a given strategy.",
    responses={
        400: {"description": "Invalid strategy"},
        500: {"description": "Preview generation failed"},
    },
)
async def preview_gpu_config(
    strategy: GpuAssignmentStrategy = Query(
        ...,
        description="Assignment strategy to preview",
    ),
) -> GpuConfigPreviewResponse:
    """Preview auto-assignment for a given strategy.

    Calculates what the GPU assignments would be if the specified strategy
    were applied, without actually changing the configuration.

    Args:
        strategy: Strategy to preview (from query parameter)

    Returns:
        GpuConfigPreviewResponse with proposed assignments and warnings
    """
    try:
        # Detect current GPUs
        detection_service = get_gpu_detection_service()
        gpus = await detection_service.detect_gpus()

        # Calculate assignments for the strategy
        assignments, warnings = _calculate_auto_assignments(strategy, gpus)

        return GpuConfigPreviewResponse(
            strategy=strategy,
            proposed_assignments=assignments,
            warnings=warnings,
        )

    except Exception as e:
        logger.exception("Failed to generate strategy preview")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate strategy preview: {e}",
        ) from e


# =============================================================================
# AI Services Endpoints
# =============================================================================

# Service display names and descriptions for UI
AI_SERVICE_METADATA: dict[str, dict[str, str]] = {
    "ai-llm": {
        "display_name": "LLM (Nemotron)",
        "description": "Nemotron LLM for risk analysis and enrichment",
    },
    "ai-yolo26": {
        "display_name": "Object Detector (YOLO26)",
        "description": "YOLO26m TensorRT real-time object detection",
    },
    "ai-enrichment": {
        "display_name": "Enrichment Models",
        "description": "Age, gender, and ReID models",
    },
    "ai-florence": {
        "display_name": "Florence-2",
        "description": "Florence-2 vision-language model",
    },
    "ai-clip": {
        "display_name": "CLIP",
        "description": "CLIP image-text embedding model",
    },
}


@router.get(
    "/ai-services",
    response_model=AiServicesResponse,
    summary="List available AI services",
    description="Returns all AI services with their VRAM requirements.",
)
async def list_ai_services() -> AiServicesResponse:
    """List all available AI services for GPU assignment.

    Returns service metadata including VRAM requirements, enabling
    the frontend to dynamically build the assignment UI.

    Returns:
        AiServicesResponse containing list of AI services
    """
    services = []
    for name, vram_mb in AI_SERVICE_VRAM_REQUIREMENTS_MB.items():
        metadata = AI_SERVICE_METADATA.get(name, {})
        services.append(
            AiServiceInfo(
                name=name,
                display_name=metadata.get("display_name", name),
                vram_required_mb=vram_mb,
                vram_required_gb=vram_mb / 1024,
                description=metadata.get("description"),
            )
        )

    return AiServicesResponse(services=services)


@router.get(
    "/gpu-config/services",
    response_model=ServiceHealthResponse,
    summary="Get AI service health status",
    description="Returns health status of all AI services including GPU assignments.",
)
async def get_service_health(
    db: AsyncSession = Depends(get_db),
) -> ServiceHealthResponse:
    """Get health status of all AI services.

    Returns service status including container status, health check result,
    GPU assignment, and restart status if currently restarting.

    Args:
        db: Database session

    Returns:
        ServiceHealthResponse with status of all AI services
    """
    try:
        # Get current GPU assignments from database
        assignments = await _get_assignments_from_db(db)
        assignment_map = {a.service: a.gpu_index for a in assignments}

        # Check for in-progress operations from Redis or fallback
        redis = await _get_redis_client()
        current_op_id = await _get_current_operation_id(redis)

        in_progress = False
        services_pending: list[str] = []
        services_completed: list[str] = []

        if current_op_id is not None and redis is not None:
            config_service = GpuConfigService(redis_client=redis)
            result = await config_service.get_operation_status(current_op_id)
            if result:
                in_progress = result.completed_at is None
                for name, svc_status in result.service_statuses.items():
                    if svc_status.status in (RestartStatus.PENDING, RestartStatus.RESTARTING):
                        services_pending.append(name)
                    else:
                        services_completed.append(name)
        else:
            # Fallback to in-memory state
            in_progress = bool(_apply_state_fallback.get("in_progress", False))
            services_pending = list(_apply_state_fallback.get("services_pending", []))  # type: ignore[call-overload]
            services_completed = list(_apply_state_fallback.get("services_completed", []))  # type: ignore[call-overload]

        # Build service health status list
        services = []
        for service_name in AI_SERVICE_VRAM_REQUIREMENTS_MB:
            # Get restart status from apply state if applicable
            restart_status = None
            if in_progress:
                if service_name in services_pending:
                    restart_status = "pending"
                elif service_name in services_completed:
                    restart_status = "completed"

            # Determine health based on apply state
            # In a full implementation, this would query Docker/Podman for actual status
            if restart_status == "pending":
                health = "starting"
                container_status = "restarting"
            elif in_progress:
                health = "unknown"
                container_status = "restarting"
            else:
                health = "healthy"
                container_status = "running"

            services.append(
                ServiceHealthStatus(
                    name=service_name,
                    status=container_status,
                    health=health,
                    gpu_index=assignment_map.get(service_name),
                    restart_status=restart_status,
                )
            )

        return ServiceHealthResponse(services=services)

    except Exception as e:
        logger.exception("Failed to get service health")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get service health: {e}",
        ) from e


# =============================================================================
# Version History Endpoints (NEM-4945)
# =============================================================================


async def _get_next_version_number(db: AsyncSession) -> int:
    """Get the next version number for a new configuration version.

    Args:
        db: Database session

    Returns:
        Next version number (1 if no versions exist)
    """
    result = await db.execute(select(func.max(GpuConfigurationVersion.version_number)))
    max_version = result.scalar_one_or_none()
    return (max_version or 0) + 1


async def _save_version(
    db: AsyncSession,
    strategy: str,
    assignments: list[GpuAssignment],
    description: str | None = None,
    created_by: str | None = None,
) -> GpuConfigurationVersion:
    """Save a new configuration version to the database.

    Args:
        db: Database session
        strategy: Assignment strategy
        assignments: List of service-to-GPU assignments
        description: Optional description of changes
        created_by: Who created this version

    Returns:
        The newly created GpuConfigurationVersion
    """
    version_number = await _get_next_version_number(db)

    # Convert assignments to JSON-serializable format
    assignments_json = [
        {
            "service": a.service,
            "gpu_index": a.gpu_index,
            "vram_budget_override": a.vram_budget_override,
        }
        for a in assignments
    ]

    version = GpuConfigurationVersion(
        version_number=version_number,
        strategy=strategy,
        assignments=assignments_json,
        description=description,
        created_by=created_by,
    )
    db.add(version)

    return version


def _compute_diff(
    old_assignments: list[dict],
    new_assignments: list[dict],
) -> list[GpuConfigAssignmentChange]:
    """Compute the differences between two sets of assignments.

    Args:
        old_assignments: Assignments from the older version
        new_assignments: Assignments from the newer version

    Returns:
        List of assignment changes
    """
    changes: list[GpuConfigAssignmentChange] = []

    old_by_service = {a["service"]: a for a in old_assignments}
    new_by_service = {a["service"]: a for a in new_assignments}

    all_services = set(old_by_service.keys()) | set(new_by_service.keys())

    for service in sorted(all_services):
        old_a = old_by_service.get(service)
        new_a = new_by_service.get(service)

        if old_a is None and new_a is not None:
            # Added
            changes.append(
                GpuConfigAssignmentChange(
                    service=service,
                    change_type="added",
                    old_gpu_index=None,
                    new_gpu_index=new_a.get("gpu_index"),
                    old_vram_override=None,
                    new_vram_override=new_a.get("vram_budget_override"),
                )
            )
        elif old_a is not None and new_a is None:
            # Removed
            changes.append(
                GpuConfigAssignmentChange(
                    service=service,
                    change_type="removed",
                    old_gpu_index=old_a.get("gpu_index"),
                    new_gpu_index=None,
                    old_vram_override=old_a.get("vram_budget_override"),
                    new_vram_override=None,
                )
            )
        elif old_a is not None and new_a is not None:
            # Check if modified
            if old_a.get("gpu_index") != new_a.get("gpu_index") or old_a.get(
                "vram_budget_override"
            ) != new_a.get("vram_budget_override"):
                changes.append(
                    GpuConfigAssignmentChange(
                        service=service,
                        change_type="modified",
                        old_gpu_index=old_a.get("gpu_index"),
                        new_gpu_index=new_a.get("gpu_index"),
                        old_vram_override=old_a.get("vram_budget_override"),
                        new_vram_override=new_a.get("vram_budget_override"),
                    )
                )

    return changes


@router.get(
    "/gpu-config/history",
    response_model=GpuConfigVersionListResponse,
    summary="List configuration version history",
    description="Returns paginated list of GPU configuration versions.",
    responses={
        500: {"description": "Failed to load version history"},
    },
)
async def list_config_versions(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum versions to return"),
    offset: int = Query(default=0, ge=0, description="Number of versions to skip"),
) -> GpuConfigVersionListResponse:
    """List GPU configuration version history.

    Returns a paginated list of configuration versions ordered by creation time
    (newest first). Each version includes a summary with strategy, description,
    and timestamp.

    Args:
        db: Database session
        limit: Maximum number of versions to return (1-100)
        offset: Number of versions to skip for pagination

    Returns:
        GpuConfigVersionListResponse with version summaries and total count
    """
    try:
        # Get total count
        count_result = await db.execute(select(func.count()).select_from(GpuConfigurationVersion))
        total_count = count_result.scalar_one()

        # Get versions
        result = await db.execute(
            select(GpuConfigurationVersion)
            .order_by(desc(GpuConfigurationVersion.version_number))
            .limit(limit)
            .offset(offset)
        )
        versions = result.scalars().all()

        version_summaries = [
            GpuConfigVersionSummary(
                id=v.id,
                version_number=v.version_number,
                strategy=v.strategy,
                description=v.description,
                created_at=v.created_at,
                created_by=v.created_by,
                assignment_count=len(v.assignments) if v.assignments else 0,
            )
            for v in versions
        ]

        return GpuConfigVersionListResponse(
            versions=version_summaries,
            total_count=total_count,
        )

    except Exception as e:
        logger.exception("Failed to load version history")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load version history: {e}",
        ) from e


@router.get(
    "/gpu-config/history/{version_id}",
    response_model=GpuConfigVersionDetail,
    summary="Get configuration version details",
    description="Returns full details of a specific configuration version.",
    responses={
        404: {"description": "Version not found"},
        500: {"description": "Failed to load version"},
    },
)
async def get_config_version(
    version_id: str,
    db: AsyncSession = Depends(get_db),
) -> GpuConfigVersionDetail:
    """Get details of a specific configuration version.

    Returns the full configuration including all assignments for a given
    version ID.

    Args:
        version_id: Unique version identifier
        db: Database session

    Returns:
        GpuConfigVersionDetail with full configuration data
    """
    try:
        result = await db.execute(
            select(GpuConfigurationVersion).where(GpuConfigurationVersion.id == version_id)
        )
        version = result.scalar_one_or_none()

        if version is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Configuration version {version_id} not found",
            )

        # Convert assignments JSON to GpuAssignment objects
        assignments = [
            GpuAssignment(
                service=a["service"],
                gpu_index=a.get("gpu_index"),
                vram_budget_override=a.get("vram_budget_override"),
            )
            for a in (version.assignments or [])
        ]

        return GpuConfigVersionDetail(
            id=version.id,
            version_number=version.version_number,
            strategy=version.strategy,
            description=version.description,
            created_at=version.created_at,
            created_by=version.created_by,
            assignment_count=len(assignments),
            assignments=assignments,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to load version")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load version: {e}",
        ) from e


@router.get(
    "/gpu-config/history/diff",
    response_model=GpuConfigVersionDiffResponse,
    summary="Compare two configuration versions",
    description="Returns the differences between two configuration versions.",
    responses={
        404: {"description": "Version not found"},
        500: {"description": "Failed to compute diff"},
    },
)
async def diff_config_versions(
    from_version: int = Query(..., description="Source version number"),
    to_version: int = Query(..., description="Target version number"),
    db: AsyncSession = Depends(get_db),
) -> GpuConfigVersionDiffResponse:
    """Compare two configuration versions.

    Returns the differences between two versions including strategy changes
    and assignment changes (added, removed, modified).

    Args:
        from_version: Source version number
        to_version: Target version number
        db: Database session

    Returns:
        GpuConfigVersionDiffResponse with changes between versions
    """
    try:
        # Get both versions
        result = await db.execute(
            select(GpuConfigurationVersion).where(
                GpuConfigurationVersion.version_number.in_([from_version, to_version])
            )
        )
        versions = {v.version_number: v for v in result.scalars().all()}

        if from_version not in versions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {from_version} not found",
            )
        if to_version not in versions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {to_version} not found",
            )

        old_version = versions[from_version]
        new_version = versions[to_version]

        strategy_changed = old_version.strategy != new_version.strategy
        assignment_changes = _compute_diff(
            old_version.assignments or [],
            new_version.assignments or [],
        )

        return GpuConfigVersionDiffResponse(
            from_version=from_version,
            to_version=to_version,
            strategy_changed=strategy_changed,
            old_strategy=old_version.strategy if strategy_changed else None,
            new_strategy=new_version.strategy if strategy_changed else None,
            assignment_changes=assignment_changes,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to compute diff")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute diff: {e}",
        ) from e


# =============================================================================
# Export/Import Endpoints (NEM-4945)
# =============================================================================


@router.get(
    "/gpu-config/export",
    response_model=GpuConfigExportData,
    summary="Export current GPU configuration",
    description="Exports current configuration in a format suitable for backup/restore.",
    responses={
        500: {"description": "Failed to export configuration"},
    },
)
async def export_gpu_config(
    db: AsyncSession = Depends(get_db),
    version_id: str | None = Query(None, description="Export specific version (default: current)"),
) -> GpuConfigExportData:
    """Export GPU configuration.

    Exports the current configuration (or a specific version) in JSON format
    that can be saved and later imported. Includes strategy, assignments,
    and metadata.

    Args:
        db: Database session
        version_id: Optional version ID to export (default: current config)

    Returns:
        GpuConfigExportData with exportable configuration
    """
    try:
        if version_id:
            # Export specific version
            result = await db.execute(
                select(GpuConfigurationVersion).where(GpuConfigurationVersion.id == version_id)
            )
            version = result.scalar_one_or_none()

            if version is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Version {version_id} not found",
                )

            assignments = [
                GpuAssignment(
                    service=a["service"],
                    gpu_index=a.get("gpu_index"),
                    vram_budget_override=a.get("vram_budget_override"),
                )
                for a in (version.assignments or [])
            ]

            return GpuConfigExportData(
                export_version="1.0",
                exported_at=datetime.now(UTC),
                strategy=version.strategy,
                assignments=assignments,
                source_version=version.version_number,
                description=version.description,
            )

        # Export current configuration
        strategy = await _get_current_strategy(db)
        assignments = await _get_assignments_from_db(db)

        # Get current version number if any
        result = await db.execute(select(func.max(GpuConfigurationVersion.version_number)))
        current_version = result.scalar_one_or_none()

        return GpuConfigExportData(
            export_version="1.0",
            exported_at=datetime.now(UTC),
            strategy=strategy.value,
            assignments=assignments,
            source_version=current_version,
            description="Current configuration export",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to export configuration")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export configuration: {e}",
        ) from e


@router.post(
    "/gpu-config/import",
    response_model=GpuConfigImportResponse,
    summary="Import GPU configuration",
    description="Imports a previously exported configuration with validation.",
    responses={
        400: {"description": "Invalid configuration"},
        500: {"description": "Failed to import configuration"},
    },
)
async def import_gpu_config(
    request: GpuConfigImportRequest,
    db: AsyncSession = Depends(get_db),
) -> GpuConfigImportResponse:
    """Import GPU configuration.

    Validates and imports a configuration from export data. Optionally applies
    the configuration immediately (restarting services).

    Args:
        request: Import request with configuration data
        db: Database session

    Returns:
        GpuConfigImportResponse with import result
    """
    try:
        config = request.config
        warnings: list[str] = []
        errors: list[str] = []

        # Validate export version
        if config.export_version != "1.0":
            errors.append(f"Unsupported export version: {config.export_version}")

        # Validate strategy
        try:
            strategy = GpuAssignmentStrategy(config.strategy)
        except ValueError:
            errors.append(f"Invalid strategy: {config.strategy}")
            strategy = GpuAssignmentStrategy.MANUAL

        # Validate assignments
        known_services = set(AI_SERVICE_VRAM_REQUIREMENTS_MB.keys())
        valid_assignments: list[GpuAssignment] = []

        for assignment in config.assignments:
            if assignment.service not in known_services:
                warnings.append(f"Service '{assignment.service}' not found - will be skipped")
            else:
                valid_assignments.append(assignment)

        # Validate VRAM budgets
        detection_service = get_gpu_detection_service()
        gpus = await detection_service.detect_gpus()
        vram_warnings = _validate_vram_assignments(valid_assignments, gpus)
        warnings.extend(vram_warnings)

        if not valid_assignments:
            errors.append("No valid assignments in configuration")

        validation = GpuConfigImportValidation(
            valid=len(errors) == 0,
            warnings=warnings,
            errors=errors,
        )

        if not validation.valid:
            return GpuConfigImportResponse(
                success=False,
                validation=validation,
                new_version=None,
                applied=False,
            )

        # Save the configuration
        await _set_current_strategy(db, strategy)
        await _save_assignments_to_db(db, valid_assignments, strategy)

        # Create version record
        description = request.description or config.description or "Imported configuration"
        version = await _save_version(
            db,
            strategy=strategy.value,
            assignments=valid_assignments,
            description=description,
            created_by="import",
        )

        await db.commit()

        new_version_summary = GpuConfigVersionSummary(
            id=version.id,
            version_number=version.version_number,
            strategy=version.strategy,
            description=version.description,
            created_at=version.created_at,
            created_by=version.created_by,
            assignment_count=len(valid_assignments),
        )

        # Apply if requested
        applied = False
        if request.apply_immediately:
            # Trigger apply (reuse existing apply logic)
            # For now, just write config files
            config_assignments = [
                GpuAssignmentDataclass(
                    service_name=a.service,
                    gpu_index=a.gpu_index if a.gpu_index is not None else 0,
                    vram_budget_override=a.vram_budget_override,
                )
                for a in valid_assignments
                if a.gpu_index is not None
            ]

            redis = await _get_redis_client()
            config_service = GpuConfigService(redis_client=redis)
            await config_service.write_config_files(
                assignments=config_assignments,
                strategy=strategy.value,
            )
            applied = True

        logger.info(
            f"GPU configuration imported: version={version.version_number}, "
            f"assignments={len(valid_assignments)}, applied={applied}"
        )

        return GpuConfigImportResponse(
            success=True,
            validation=validation,
            new_version=new_version_summary,
            applied=applied,
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception("Failed to import configuration")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import configuration: {e}",
        ) from e


@router.post(
    "/gpu-config/rollback",
    response_model=GpuConfigRollbackResponse,
    summary="Rollback to previous configuration",
    description="Restores a previous configuration version.",
    responses={
        404: {"description": "Version not found"},
        500: {"description": "Failed to rollback"},
    },
)
async def rollback_gpu_config(
    request: GpuConfigRollbackRequest,
    db: AsyncSession = Depends(get_db),
) -> GpuConfigRollbackResponse:
    """Rollback to a previous configuration version.

    Restores the configuration from a specific version, creating a new
    version record for the rollback. Optionally applies the configuration
    immediately.

    Args:
        request: Rollback request with version ID
        db: Database session

    Returns:
        GpuConfigRollbackResponse with rollback result
    """
    try:
        # Get the version to rollback to
        result = await db.execute(
            select(GpuConfigurationVersion).where(GpuConfigurationVersion.id == request.version_id)
        )
        target_version = result.scalar_one_or_none()

        if target_version is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {request.version_id} not found",
            )

        # Get current version number
        current_version_result = await db.execute(
            select(func.max(GpuConfigurationVersion.version_number))
        )
        current_version_number = current_version_result.scalar_one_or_none() or 0

        # Parse strategy
        try:
            strategy = GpuAssignmentStrategy(target_version.strategy)
        except ValueError:
            strategy = GpuAssignmentStrategy.MANUAL

        # Convert assignments
        assignments = [
            GpuAssignment(
                service=a["service"],
                gpu_index=a.get("gpu_index"),
                vram_budget_override=a.get("vram_budget_override"),
            )
            for a in (target_version.assignments or [])
        ]

        # Apply the configuration
        await _set_current_strategy(db, strategy)
        await _save_assignments_to_db(db, assignments, strategy)

        # Create new version record for the rollback
        description = request.description or f"Rollback to version {target_version.version_number}"
        new_version = await _save_version(
            db,
            strategy=target_version.strategy,
            assignments=assignments,
            description=description,
            created_by="rollback",
        )

        await db.commit()

        # Apply if requested
        applied = False
        if request.apply_immediately:
            config_assignments = [
                GpuAssignmentDataclass(
                    service_name=a.service,
                    gpu_index=a.gpu_index if a.gpu_index is not None else 0,
                    vram_budget_override=a.vram_budget_override,
                )
                for a in assignments
                if a.gpu_index is not None
            ]

            redis = await _get_redis_client()
            config_service = GpuConfigService(redis_client=redis)
            await config_service.write_config_files(
                assignments=config_assignments,
                strategy=strategy.value,
            )
            applied = True

        new_version_summary = GpuConfigVersionSummary(
            id=new_version.id,
            version_number=new_version.version_number,
            strategy=new_version.strategy,
            description=new_version.description,
            created_at=new_version.created_at,
            created_by=new_version.created_by,
            assignment_count=len(assignments),
        )

        logger.info(
            f"GPU configuration rolled back: from_version={current_version_number}, "
            f"to_version={target_version.version_number}, new_version={new_version.version_number}"
        )

        return GpuConfigRollbackResponse(
            success=True,
            rolled_back_from=current_version_number,
            rolled_back_to=target_version.version_number,
            new_version=new_version_summary,
            applied=applied,
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception("Failed to rollback configuration")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rollback configuration: {e}",
        ) from e
