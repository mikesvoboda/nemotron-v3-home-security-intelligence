"""Admin API routes for seeding test data (development only)."""

import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.database import get_db
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event

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


class ClearDataResponse(BaseModel):
    """Response schema for clear data endpoint."""

    cameras_cleared: int
    events_cleared: int
    detections_cleared: int


# --- Sample Data ---

SAMPLE_CAMERAS = [
    {
        "id": "front-door",
        "name": "Front Door",
        "folder_path": "/export/foscam/front_door",
        "status": "active",
    },
    {
        "id": "backyard",
        "name": "Backyard",
        "folder_path": "/export/foscam/backyard",
        "status": "active",
    },
    {
        "id": "garage",
        "name": "Garage",
        "folder_path": "/export/foscam/garage",
        "status": "inactive",
    },
    {
        "id": "driveway",
        "name": "Driveway",
        "folder_path": "/export/foscam/driveway",
        "status": "active",
    },
    {
        "id": "side-gate",
        "name": "Side Gate",
        "folder_path": "/export/foscam/side_gate",
        "status": "active",
    },
    {
        "id": "living-room",
        "name": "Living Room",
        "folder_path": "/export/foscam/living_room",
        "status": "inactive",
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


# --- Helper to check DEBUG mode ---


def require_debug_mode() -> None:
    """Raise 403 if DEBUG mode is not enabled."""
    settings = get_settings()
    if not settings.debug:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin endpoints are only available when DEBUG=true",
        )


# --- Endpoints ---


@router.post("/seed/cameras", response_model=SeedCamerasResponse)
async def seed_cameras(
    request: SeedCamerasRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Seed test cameras into the database.

    Only available when DEBUG=true.

    Args:
        request: Seed configuration (count, clear_existing, create_folders)
        db: Database session

    Returns:
        Summary of seeded cameras
    """
    require_debug_mode()

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
    cameras_to_create = SAMPLE_CAMERAS[: request.count]

    for camera_data in cameras_to_create:
        # Check if camera already exists
        result = await db.execute(select(Camera).where(Camera.id == camera_data["id"]))
        existing_camera = result.scalar_one_or_none()

        if existing_camera:
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

    return {
        "created": created,
        "cleared": cleared,
        "cameras": cameras_created,
    }


@router.post("/seed/events", response_model=SeedEventsResponse)
async def seed_events(
    request: SeedEventsRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Seed mock events and detections into the database.

    Only available when DEBUG=true. Requires cameras to exist first.

    Args:
        request: Seed configuration (count, clear_existing)
        db: Database session

    Returns:
        Summary of seeded events and detections
    """
    require_debug_mode()

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
        started_at = datetime.utcnow() - timedelta(hours=hours_ago)
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

    return {
        "events_created": events_created,
        "detections_created": detections_created,
        "events_cleared": events_cleared,
        "detections_cleared": detections_cleared,
    }


@router.delete("/seed/clear", response_model=ClearDataResponse)
async def clear_seeded_data(
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Clear all seeded data (cameras, events, detections).

    Only available when DEBUG=true.

    Args:
        db: Database session

    Returns:
        Summary of cleared data counts
    """
    require_debug_mode()

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
    await db.commit()

    return {
        "cameras_cleared": cameras_cleared,
        "events_cleared": events_cleared,
        "detections_cleared": detections_cleared,
    }
