"""GPU configuration API routes for multi-GPU support (F-176, F-178, F-182).

R2a row 36 retired F-177 (POST /gpu-config/detect), F-179 (PUT /gpu-config),
F-180 (GET /gpu-config/services), F-181 (POST /gpu-config/apply, GET /gpu-config/status),
and F-183 (POST /gpu-config/import, POST /gpu-config/rollback).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.gpu_config import (
    AiServiceInfo,
    AiServicesResponse,
    GpuAssignment,
    GpuAssignmentStrategy,
    GpuConfigAssignmentChange,
    GpuConfigExportData,
    GpuConfigPreviewResponse,
    GpuConfigResponse,
    GpuConfigVersionDetail,
    GpuConfigVersionDiffResponse,
    GpuConfigVersionListResponse,
    GpuConfigVersionSummary,
    GpuDeviceResponse,
    GpuDevicesResponse,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.gpu_config import (
    GpuConfiguration,
    GpuConfigurationVersion,
    SystemSetting,
)
from backend.services.gpu_detection_service import (
    AI_SERVICE_VRAM_REQUIREMENTS_MB,
    GpuDevice,
    get_gpu_detection_service,
)

logger = get_logger(__name__)

# Router with /api/system prefix to match frontend expectations
router = APIRouter(prefix="/api/system", tags=["gpu-config"])

# Constants
GPU_STRATEGY_SETTING_KEY = "gpu_assignment_strategy"
DEFAULT_STRATEGY = GpuAssignmentStrategy.MANUAL


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
    result = await db.execute(select(func.max(GpuConfiguration.updated_at)))
    return result.scalar_one_or_none()


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
        for service in services:
            assignments.append(
                GpuAssignment(
                    service=service,
                    gpu_index=0,
                    vram_budget_override=None,
                )
            )

    elif strategy == GpuAssignmentStrategy.VRAM_BASED:
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
        if len(gpus) >= 2:
            largest_gpu = max(gpus, key=lambda g: g.vram_total_mb)
            second_gpu = next(g for g in gpus if g.index != largest_gpu.index)

            for service in services:
                assignments.append(
                    GpuAssignment(
                        service=service,
                        gpu_index=second_gpu.index,
                        vram_budget_override=None,
                    )
                )
        else:
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

        def get_compute_score(gpu: GpuDevice) -> float:
            if gpu.compute_capability:
                try:
                    return float(gpu.compute_capability)
                except ValueError:
                    pass
            return 0.0

        sorted_gpus = sorted(gpus, key=get_compute_score, reverse=True)
        fastest_gpu = sorted_gpus[0]

        critical_services = ["ai-yolo26"]

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
                other_gpu = sorted_gpus[-1] if len(sorted_gpus) > 1 else fastest_gpu
                assignments.append(
                    GpuAssignment(
                        service=service,
                        gpu_index=other_gpu.index,
                        vram_budget_override=None,
                    )
                )

    elif strategy == GpuAssignmentStrategy.BALANCED:
        gpu_usage: dict[int, int] = {g.index: 0 for g in gpus}

        sorted_services = sorted(
            services,
            key=lambda s: AI_SERVICE_VRAM_REQUIREMENTS_MB.get(s, 0),
            reverse=True,
        )

        for service in sorted_services:
            vram_needed = AI_SERVICE_VRAM_REQUIREMENTS_MB.get(service, 0)

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
    """List all detected GPU devices."""
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
    """Get the current GPU configuration."""
    try:
        strategy = await _get_current_strategy(db)
        assignments = await _get_assignments_from_db(db)
        updated_at = await _get_latest_config_update_time(db)

        if not assignments:
            for service in AI_SERVICE_VRAM_REQUIREMENTS_MB:
                assignments.append(
                    GpuAssignment(
                        service=service,
                        gpu_index=0,
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
    """Preview auto-assignment for a given strategy."""
    try:
        detection_service = get_gpu_detection_service()
        gpus = await detection_service.detect_gpus()

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

AI_SERVICE_METADATA: dict[str, dict[str, str]] = {
    "ai-yolo26": {
        "display_name": "Object Detector (YOLO26)",
        "description": "YOLO26m TensorRT real-time object detection",
    },
}


@router.get(
    "/ai-services",
    response_model=AiServicesResponse,
    summary="List available AI services",
    description="Returns all AI services with their VRAM requirements.",
)
async def list_ai_services() -> AiServicesResponse:
    """List all available AI services for GPU assignment."""
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


# =============================================================================
# Version History Endpoints (NEM-4945)
# =============================================================================


async def _get_next_version_number(db: AsyncSession) -> int:
    """Get the next version number for a new configuration version."""
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
    """Save a new configuration version to the database."""
    version_number = await _get_next_version_number(db)

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
    """Compute the differences between two sets of assignments."""
    changes: list[GpuConfigAssignmentChange] = []

    old_by_service = {a["service"]: a for a in old_assignments}
    new_by_service = {a["service"]: a for a in new_assignments}

    all_services = set(old_by_service.keys()) | set(new_by_service.keys())

    for service in sorted(all_services):
        old_a = old_by_service.get(service)
        new_a = new_by_service.get(service)

        if old_a is None and new_a is not None:
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
    """List GPU configuration version history."""
    try:
        count_result = await db.execute(select(func.count()).select_from(GpuConfigurationVersion))
        total_count = count_result.scalar_one()

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
    """Get details of a specific configuration version."""
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
    """Compare two configuration versions."""
    try:
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
# Export Endpoint (NEM-4945)
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
    """Export GPU configuration."""
    try:
        if version_id:
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

        strategy = await _get_current_strategy(db)
        assignments = await _get_assignments_from_db(db)

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
