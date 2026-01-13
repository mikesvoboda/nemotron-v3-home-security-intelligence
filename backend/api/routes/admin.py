"""Admin API routes for seeding test data (development only).

SECURITY: Admin endpoints are protected by multiple layers:
1. DEBUG mode must be enabled (debug=True)
2. ADMIN_ENABLED must be explicitly set (admin_enabled=True)
3. Optional API key requirement (admin_api_key environment variable)

This defense-in-depth approach prevents accidental exposure in production.
"""

import random
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any  # Still used for cameras list in SeedCamerasResponse

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.audit import AuditAction
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.services.audit import get_db_audit_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# --- Request/Response Schemas ---


class SeedCamerasRequest(BaseModel):
    """Request schema for seeding cameras."""

    count: int = Field(default=6, ge=1, le=6, description="Number of cameras to create (1-6)")
    clear_existing: bool = Field(default=False, description="Remove existing cameras first")
    create_folders: bool = Field(default=False, description="Create camera folders on filesystem")


class SeedCamerasResponse(BaseModel):
    """Response schema for seed cameras endpoint."""

    created: int
    cleared: int
    cameras: list[dict[str, Any]]


class SeedEventsRequest(BaseModel):
    """Request schema for seeding events."""

    count: int = Field(default=15, ge=1, le=100, description="Number of events to create (1-100)")
    clear_existing: bool = Field(default=False, description="Remove existing events and detections")


class SeedEventsResponse(BaseModel):
    """Response schema for seed events endpoint."""

    events_created: int
    detections_created: int
    events_cleared: int
    detections_cleared: int


class ClearDataRequest(BaseModel):
    """Request schema for clearing data - requires confirmation."""

    confirm: str = Field(
        ...,
        description="Must be exactly 'DELETE_ALL_DATA' to confirm deletion",
    )


class ClearDataResponse(BaseModel):
    """Response schema for clear data endpoint."""

    cameras_cleared: int
    events_cleared: int
    detections_cleared: int


class OrphanCleanupRequest(BaseModel):
    """Request schema for orphan cleanup endpoint."""

    dry_run: bool = Field(
        default=True,
        description="If True, only report what would be deleted without actually deleting",
    )
    min_age_hours: int = Field(
        default=24,
        ge=1,
        le=720,
        description="Minimum age in hours before a file can be deleted (1-720)",
    )
    max_delete_gb: float = Field(
        default=10.0,
        ge=0.1,
        le=100.0,
        description="Maximum gigabytes to delete in one run (0.1-100)",
    )


class OrphanCleanupResponse(BaseModel):
    """Response schema for orphan cleanup endpoint."""

    scanned_files: int
    orphaned_files: int
    deleted_files: int
    deleted_bytes: int
    deleted_bytes_formatted: str
    failed_count: int
    failed_deletions: list[str]
    duration_seconds: float
    dry_run: bool
    skipped_young: int
    skipped_size_limit: int


# --- Sample Data ---


def _get_sample_cameras() -> list[dict[str, str]]:
    """Generate sample camera data using configured foscam_base_path.

    This ensures seeded cameras have folder_paths that are valid under
    the configured base path, avoiding 404 errors when serving snapshots.
    """
    settings = get_settings()
    base_path = settings.foscam_base_path

    return [
        {
            "id": "front-door",
            "name": "Front Door",
            "folder_path": f"{base_path}/front_door",
            "status": "online",
        },
        {
            "id": "backyard",
            "name": "Backyard",
            "folder_path": f"{base_path}/backyard",
            "status": "online",
        },
        {
            "id": "garage",
            "name": "Garage",
            "folder_path": f"{base_path}/garage",
            "status": "offline",
        },
        {
            "id": "driveway",
            "name": "Driveway",
            "folder_path": f"{base_path}/driveway",
            "status": "online",
        },
        {
            "id": "side-gate",
            "name": "Side Gate",
            "folder_path": f"{base_path}/side_gate",
            "status": "online",
        },
        {
            "id": "living-room",
            "name": "Living Room",
            "folder_path": f"{base_path}/living_room",
            "status": "offline",
        },
    ]


MOCK_SUMMARIES = {
    "low": [
        "Routine activity detected. Family member arriving home from work.",
        "Delivery driver dropped off package at front door. Normal delivery activity.",
        "Neighborhood cat passing through the backyard. No security concern.",
        "Mail carrier delivering daily mail. Expected activity.",
        "Landscaping crew performing scheduled yard maintenance.",
    ],
    "medium": [
        "Unknown vehicle parked briefly in driveway. Driver appeared to check phone.",
        "Unrecognized person approached front door but left without ringing bell.",
        "Motion detected at unusual hour. Appears to be neighbor retrieving item.",
        "Unknown individual walking slowly past property, looking at houses.",
        "Vehicle made U-turn in driveway. Could not identify occupants.",
    ],
    "high": [
        "Suspicious individual observed checking door handles on parked vehicles.",
        "Person wearing hood lingering near side gate for extended period.",
        "Multiple unknown individuals approaching property from different directions.",
        "Person photographing house and property from sidewalk.",
        "Individual attempted to open gate latch before walking away quickly.",
    ],
}

MOCK_REASONING = {
    "low": [
        "Activity matches expected patterns for this time of day. No indicators of threat.",
        "Standard delivery behavior observed. Driver followed normal protocol.",
        "Animal activity only. No human presence detected. Motion was brief.",
    ],
    "medium": [
        "While not overtly threatening, the combination of unfamiliar face and hesitant "
        "approach warrants attention. Recommend reviewing if activity repeats.",
        "Vehicle presence was brief but unexplained. Pattern does not match delivery.",
        "Unusual timing raises baseline concern. Activity appears benign but unusual.",
    ],
    "high": [
        "Multiple risk indicators present: unknown individual, suspicious behavior pattern, "
        "evasive movement. High probability of criminal intent.",
        "Subject exhibited classic pre-surveillance behavior: slow approach, extended "
        "observation, photographing security features. Immediate review recommended.",
        "Coordinated approach by multiple unknowns suggests planning. Behavior inconsistent "
        "with legitimate visitors.",
    ],
}

OBJECT_TYPES = ["person", "vehicle", "animal", "package"]


# --- Security: Admin Access Control ---


def require_admin_access(x_admin_api_key: str | None = Header(default=None)) -> None:
    """Validate admin endpoint access with defense-in-depth security.

    SECURITY: This function enforces multiple layers of protection:
    1. DEBUG mode must be enabled (debug=True)
    2. ADMIN_ENABLED must be explicitly set (admin_enabled=True)
    3. If admin_api_key is configured, the request must include matching X-Admin-API-Key header

    Args:
        x_admin_api_key: Optional API key from request header

    Raises:
        HTTPException: 403 if any security check fails
    """
    settings = get_settings()

    # Layer 1: DEBUG mode must be enabled
    if not settings.debug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin endpoints are only available when DEBUG=true",
        )

    # Layer 2: ADMIN_ENABLED must be explicitly set
    if not settings.admin_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin endpoints require ADMIN_ENABLED=true. "
            "This is a separate flag from DEBUG for defense-in-depth security.",
        )

    # Layer 3: If admin API key is configured, validate it
    if settings.admin_api_key:
        if not x_admin_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Admin API key required. Provide X-Admin-API-Key header.",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        # Use constant-time comparison to prevent timing attacks
        if not secrets.compare_digest(x_admin_api_key, settings.admin_api_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin API key.",
                headers={"WWW-Authenticate": "ApiKey"},
            )


# --- Endpoints ---


@router.post(
    "/seed/cameras",
    response_model=SeedCamerasResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Cameras created successfully"},
        401: {"description": "Unauthorized - Admin API key required"},
        403: {"description": "Forbidden - Debug mode or admin not enabled"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def seed_cameras(
    request: SeedCamerasRequest,
    db: AsyncSession = Depends(get_db),
    _admin: None = Depends(require_admin_access),
) -> SeedCamerasResponse:
    """Seed test cameras into the database.

    SECURITY: Requires DEBUG=true AND ADMIN_ENABLED=true.
    If ADMIN_API_KEY is set, requires X-Admin-API-Key header.

    Args:
        request: Seed configuration (count, clear_existing, create_folders)
        db: Database session
        _admin: Admin access validation (via dependency)

    Returns:
        Summary of seeded cameras
    """

    cleared = 0
    created = 0
    cameras_created: list[dict[str, Any]] = []

    # Clear existing cameras if requested
    if request.clear_existing:
        result = await db.execute(select(Camera))
        existing = result.scalars().all()
        cleared = len(existing)

        if cleared > 0:
            await db.execute(delete(Camera))
            await db.commit()

    # Seed cameras
    cameras_to_create = _get_sample_cameras()[: request.count]

    # Batch load existing camera IDs to avoid N+1 queries
    camera_ids_to_check = [c["id"] for c in cameras_to_create]
    existing_result = await db.execute(select(Camera.id).where(Camera.id.in_(camera_ids_to_check)))
    existing_ids = {row[0] for row in existing_result.all()}

    for camera_data in cameras_to_create:
        # Check if camera already exists using batch-loaded set
        if camera_data["id"] in existing_ids:
            continue

        # Create camera folder if requested
        if request.create_folders:
            folder_path = Path(camera_data["folder_path"])
            try:
                folder_path.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass  # Continue even if folder creation fails

        # Create camera in database
        camera = Camera(
            id=camera_data["id"],
            name=camera_data["name"],
            folder_path=camera_data["folder_path"],
            status=camera_data["status"],
        )
        db.add(camera)
        created += 1
        cameras_created.append(
            {
                "id": camera.id,
                "name": camera.name,
                "folder_path": camera.folder_path,
                "status": camera.status,
            }
        )

    await db.commit()

    return SeedCamerasResponse(
        created=created,
        cleared=cleared,
        cameras=cameras_created,
    )


@router.post(
    "/seed/events",
    response_model=SeedEventsResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Events and detections created successfully"},
        400: {"description": "Bad request - No cameras found"},
        401: {"description": "Unauthorized - Admin API key required"},
        403: {"description": "Forbidden - Debug mode or admin not enabled"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def seed_events(
    request: SeedEventsRequest,
    db: AsyncSession = Depends(get_db),
    _admin: None = Depends(require_admin_access),
) -> SeedEventsResponse:
    """Seed mock events and detections into the database.

    SECURITY: Requires DEBUG=true AND ADMIN_ENABLED=true.
    If ADMIN_API_KEY is set, requires X-Admin-API-Key header.
    Requires cameras to exist first.

    Args:
        request: Seed configuration (count, clear_existing)
        db: Database session
        _admin: Admin access validation (via dependency)

    Returns:
        Summary of seeded events and detections
    """

    events_cleared = 0
    detections_cleared = 0
    events_created = 0
    detections_created = 0

    # Clear existing data if requested
    if request.clear_existing:
        events_result = await db.execute(select(Event))
        events_cleared = len(events_result.scalars().all())

        detections_result = await db.execute(select(Detection))
        detections_cleared = len(detections_result.scalars().all())

        await db.execute(delete(Event))
        await db.execute(delete(Detection))
        await db.commit()

    # Get cameras
    result = await db.execute(select(Camera))
    cameras = result.scalars().all()

    if not cameras:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No cameras found. Seed cameras first with POST /api/admin/seed/cameras",
        )

    # Create events
    for _ in range(request.count):
        # Pick a random camera
        camera = random.choice(cameras)  # noqa: S311

        # Determine risk level with weighted distribution
        risk_roll = random.random()  # noqa: S311
        if risk_roll < 0.5:
            risk_level = "low"
            risk_score = random.randint(5, 33)  # noqa: S311
        elif risk_roll < 0.85:
            risk_level = "medium"
            risk_score = random.randint(34, 66)  # noqa: S311
        else:
            risk_level = "high"
            risk_score = random.randint(67, 95)  # noqa: S311

        # Generate timestamps (spread over last 24 hours)
        hours_ago = random.uniform(0, 24)  # noqa: S311
        started_at = datetime.now(UTC) - timedelta(hours=hours_ago)
        duration_seconds = random.randint(10, 180)  # noqa: S311
        ended_at = started_at + timedelta(seconds=duration_seconds)

        # Create batch ID
        batch_id = str(uuid.uuid4())[:8]

        # Create 1-5 detections for this event
        num_detections = random.randint(1, 5)  # noqa: S311
        detection_ids = []

        for j in range(num_detections):
            object_type = random.choice(OBJECT_TYPES)  # noqa: S311
            confidence = random.uniform(0.65, 0.98)  # noqa: S311

            # Generate mock bounding box
            bbox_x = random.randint(50, 400)  # noqa: S311
            bbox_y = random.randint(50, 300)  # noqa: S311
            bbox_width = random.randint(80, 200)  # noqa: S311
            bbox_height = random.randint(100, 250)  # noqa: S311

            # Use mock image path
            folder_name = camera.folder_path.split("/")[-1]
            file_path = f"/app/data/cameras/{folder_name}/capture_00{j + 1}.jpg"

            detection = Detection(
                camera_id=camera.id,
                file_path=file_path,
                file_type="image/jpeg",
                detected_at=started_at + timedelta(seconds=j * 2),
                object_type=object_type,
                confidence=round(confidence, 2),
                bbox_x=bbox_x,
                bbox_y=bbox_y,
                bbox_width=bbox_width,
                bbox_height=bbox_height,
            )
            db.add(detection)
            await db.flush()  # Get the ID
            detection_ids.append(str(detection.id))
            detections_created += 1

        # Create event
        summary = random.choice(MOCK_SUMMARIES[risk_level])  # noqa: S311
        reasoning = random.choice(MOCK_REASONING[risk_level])  # noqa: S311

        event = Event(
            batch_id=batch_id,
            camera_id=camera.id,
            started_at=started_at,
            ended_at=ended_at,
            risk_score=risk_score,
            risk_level=risk_level,
            summary=summary,
            reasoning=reasoning,
            detection_ids=",".join(detection_ids),
            reviewed=random.random() < 0.3,  # noqa: S311
        )
        db.add(event)
        events_created += 1

    await db.commit()

    return SeedEventsResponse(
        events_created=events_created,
        detections_created=detections_created,
        events_cleared=events_cleared,
        detections_cleared=detections_cleared,
    )


@router.delete(
    "/seed/clear",
    response_model=ClearDataResponse,
    responses={
        400: {"description": "Bad request - Confirmation required"},
        401: {"description": "Unauthorized - Admin API key required"},
        403: {"description": "Forbidden - Debug mode or admin not enabled"},
        500: {"description": "Internal server error"},
    },
)
async def clear_seeded_data(
    body: ClearDataRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: None = Depends(require_admin_access),
) -> ClearDataResponse:
    """Clear all seeded data (cameras, events, detections).

    SECURITY: Requires DEBUG=true AND ADMIN_ENABLED=true.
    If ADMIN_API_KEY is set, requires X-Admin-API-Key header.
    Requires JSON body confirmation to prevent accidental data deletion:
    {"confirm": "DELETE_ALL_DATA"}

    Args:
        body: Request body with confirmation string
        request: FastAPI request for audit logging
        db: Database session
        _admin: Admin access validation (via dependency)

    Returns:
        Summary of cleared data counts

    Raises:
        HTTPException: 400 if confirmation string is incorrect
    """
    # Validate confirmation string
    if body.confirm != "DELETE_ALL_DATA":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Confirmation required: body must contain {"confirm": "DELETE_ALL_DATA"}',
        )

    # Count existing data
    events_result = await db.execute(select(Event))
    events_cleared = len(events_result.scalars().all())

    detections_result = await db.execute(select(Detection))
    detections_cleared = len(detections_result.scalars().all())

    cameras_result = await db.execute(select(Camera))
    cameras_cleared = len(cameras_result.scalars().all())

    # Delete in order (respecting foreign keys)
    await db.execute(delete(Event))
    await db.execute(delete(Detection))
    await db.execute(delete(Camera))

    # Log deletion to audit log
    try:
        await get_db_audit_service().log_action(
            db=db,
            action=AuditAction.DATA_CLEARED,
            resource_type="admin",
            actor="admin",
            details={
                "cameras_cleared": cameras_cleared,
                "events_cleared": events_cleared,
                "detections_cleared": detections_cleared,
            },
            request=request,
        )
    except Exception as e:
        logger.warning(
            "Audit log write failed",
            extra={
                "action": AuditAction.DATA_CLEARED.value,
                "resource_id": None,
                "resource_type": "admin",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
        )

    await db.commit()

    return ClearDataResponse(
        cameras_cleared=cameras_cleared,
        events_cleared=events_cleared,
        detections_cleared=detections_cleared,
    )


@router.post(
    "/cleanup/orphans",
    response_model=OrphanCleanupResponse,
    responses={
        200: {"description": "Orphan cleanup completed successfully"},
        401: {"description": "Unauthorized - Admin API key required"},
        403: {"description": "Forbidden - Debug mode or admin not enabled"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def cleanup_orphans(
    request: OrphanCleanupRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: None = Depends(require_admin_access),
) -> OrphanCleanupResponse:
    """Manually trigger orphaned file cleanup.

    Scans camera upload directories for files that have no corresponding
    database records and optionally deletes them.

    SECURITY: Requires DEBUG=true AND ADMIN_ENABLED=true.
    If ADMIN_API_KEY is set, requires X-Admin-API-Key header.

    Safety features:
    - dry_run=True by default (no actual deletions)
    - min_age_hours threshold prevents deleting files being processed
    - max_delete_gb limits total deletion per run

    Args:
        request: Cleanup configuration (dry_run, min_age_hours, max_delete_gb)
        http_request: FastAPI request for audit logging
        _admin: Admin access validation (via dependency)

    Returns:
        Summary of cleanup operation with statistics
    """
    from backend.jobs.orphan_cleanup_job import OrphanCleanupJob
    from backend.services.job_tracker import get_job_tracker

    # Get job tracker for progress tracking
    job_tracker = get_job_tracker()

    # Create and run cleanup job
    job = OrphanCleanupJob(
        min_age_hours=request.min_age_hours,
        dry_run=request.dry_run,
        max_delete_gb=request.max_delete_gb,
        job_tracker=job_tracker,
    )

    # Run the cleanup
    report = await job.run()

    # Log to audit
    try:
        await get_db_audit_service().log_action(
            db=db,
            action=AuditAction.DATA_CLEARED,
            resource_type="orphan_cleanup",
            actor="admin",
            details={
                "dry_run": request.dry_run,
                "scanned_files": report.scanned_files,
                "orphaned_files": report.orphaned_files,
                "deleted_files": report.deleted_files,
                "deleted_bytes": report.deleted_bytes,
            },
            request=http_request,
        )
    except Exception as e:
        logger.warning(
            "Audit log write failed",
            extra={
                "action": AuditAction.DATA_CLEARED.value,
                "resource_id": None,
                "resource_type": "orphan_cleanup",
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
        )

    return OrphanCleanupResponse(
        scanned_files=report.scanned_files,
        orphaned_files=report.orphaned_files,
        deleted_files=report.deleted_files,
        deleted_bytes=report.deleted_bytes,
        deleted_bytes_formatted=report._format_bytes(report.deleted_bytes),
        failed_count=len(report.failed_deletions),
        failed_deletions=report.failed_deletions[:50],  # Limit to 50
        duration_seconds=report.duration_seconds,
        dry_run=report.dry_run,
        skipped_young=report.skipped_young,
        skipped_size_limit=report.skipped_size_limit,
    )
