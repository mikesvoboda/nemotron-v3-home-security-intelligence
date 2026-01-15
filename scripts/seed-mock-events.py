#!/usr/bin/env python3
"""Seed the system by exercising the full AI pipeline end-to-end.

This script triggers real pipeline processing by copying images to camera
watch folders, causing the file watcher to process them through:
  1. File Watcher → detects new images
  2. RT-DETRv2 → object detection
  3. Batch Aggregator → groups detections into events
  4. Nemotron LLM → risk analysis with reasoning

This creates real events with actual LLM prompts for comprehensive testing.

Usage:
    # Default: Full pipeline + all supporting data (recommended for UI validation)
    uv run python scripts/seed-mock-events.py

    # Process more images
    uv run python scripts/seed-mock-events.py --images 50

    # Skip supporting data (entities, alerts, logs) - only pipeline data
    uv run python scripts/seed-mock-events.py --no-extras

    # Use mock data instead of real pipeline (legacy behavior)
    uv run python scripts/seed-mock-events.py --mock

    # Clear all data before seeding
    uv run python scripts/seed-mock-events.py --clear
"""

import asyncio
import os
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Base path for camera images
FOSCAM_BASE_PATH = os.environ.get("FOSCAM_BASE_PATH", "/export/foscam")

from backend.core.database import get_session, init_db  # noqa: E402
from backend.models.alert import Alert, AlertRule, AlertSeverity, AlertStatus  # noqa: E402
from backend.models.audit import AuditAction, AuditLog  # noqa: E402
from backend.models.baseline import ActivityBaseline, ClassBaseline  # noqa: E402
from backend.models.camera import Camera  # noqa: E402
from backend.models.detection import Detection  # noqa: E402
from backend.models.entity import Entity  # noqa: E402
from backend.models.enums import EntityType  # noqa: E402
from backend.models.event import Event  # noqa: E402
from backend.models.log import Log  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402


def find_camera_images(base_path: str = FOSCAM_BASE_PATH, limit: int = 500) -> list[Path]:
    """Find all camera images in the foscam directory structure.

    Returns a list of image paths, sorted by modification time (oldest first).
    """
    base = Path(base_path)
    if not base.exists():
        print(f"Warning: Camera base path {base_path} does not exist")
        return []

    images = []
    for pattern in ["**/*.jpg", "**/*.JPG", "**/*.png", "**/*.PNG"]:
        images.extend(base.glob(pattern))

    # Sort by mtime (oldest first) and limit
    images = sorted(images, key=lambda p: p.stat().st_mtime)[:limit]
    return images


def trigger_pipeline(num_images: int = 20, delay_between: float = 0.5) -> int:
    """Trigger the AI pipeline by touching existing camera images.

    This updates the mtime of existing images, causing the file watcher
    to detect them as "new" and process them through the full pipeline:
    File Watcher → RT-DETRv2 → Batch Aggregator → Nemotron LLM

    Args:
        num_images: Number of images to process
        delay_between: Seconds to wait between touching images (allows batching)

    Returns:
        Number of images touched
    """
    import time

    print(f"Finding camera images in {FOSCAM_BASE_PATH}...")
    all_images = find_camera_images(limit=num_images * 3)  # Get extra for variety

    if not all_images:
        print("Error: No camera images found. Check FOSCAM_BASE_PATH.")
        return 0

    # Select random subset if we have more than needed
    selected = random.sample(all_images, num_images) if len(all_images) > num_images else all_images

    print(f"Found {len(all_images)} images, will process {len(selected)}")
    print(f"\nTouching {len(selected)} images to trigger pipeline processing...")
    print("(Images will be processed: File Watcher → RT-DETRv2 → Batching → Nemotron)\n")

    touched = 0
    for i, img_path in enumerate(selected, 1):
        try:
            # Touch the file to update mtime
            img_path.touch()
            camera_name = img_path.parts[-4] if len(img_path.parts) >= 4 else "unknown"
            print(f"  [{i}/{len(selected)}] Touched: {camera_name}/{img_path.name}")
            touched += 1

            # Small delay to allow file watcher to pick up and batch appropriately
            if delay_between > 0 and i < len(selected):
                time.sleep(delay_between)

        except (OSError, PermissionError) as e:
            print(f"  [{i}/{len(selected)}] Failed: {img_path.name} - {e}")

    print(f"\nTriggered pipeline for {touched} images")

    return touched


async def wait_for_pipeline_completion(
    initial_event_count: int,
    expected_min_events: int = 5,
    timeout_seconds: int = 300,
    poll_interval: float = 5.0,
) -> tuple[int, int, bool]:
    """Wait for the AI pipeline to process images and create events.

    Polls the database for new events until either:
    - At least expected_min_events new events are created
    - Timeout is reached
    - No new events are created for 60 seconds (pipeline idle)

    Args:
        initial_event_count: Event count before triggering pipeline
        expected_min_events: Minimum new events to wait for
        timeout_seconds: Maximum wait time (default 5 minutes)
        poll_interval: Seconds between polling

    Returns:
        Tuple of (final_event_count, new_events_created, success)
    """
    import time

    print(f"\n{'=' * 50}")
    print("WAITING FOR PIPELINE COMPLETION")
    print(f"{'=' * 50}")
    print(f"Initial events: {initial_event_count}")
    print(f"Waiting for at least {expected_min_events} new events...")
    print(f"Timeout: {timeout_seconds}s | Poll interval: {poll_interval}s\n")

    start_time = time.time()
    last_count = initial_event_count
    last_change_time = start_time
    idle_timeout = 90  # Consider pipeline idle if no new events for 90 seconds

    while True:
        elapsed = time.time() - start_time
        time_since_last_change = time.time() - last_change_time

        # Get current event count
        events = await get_events()
        current_count = len(events)
        new_events = current_count - initial_event_count

        # Check if new events were created
        if current_count > last_count:
            last_change_time = time.time()
            print(f"  [{elapsed:.0f}s] Events: {current_count} (+{current_count - last_count} new)")
            last_count = current_count

        # Success condition: got enough events
        if new_events >= expected_min_events:
            print("\n✓ Pipeline completed successfully!")
            print(f"  Created {new_events} new events in {elapsed:.0f} seconds")
            return current_count, new_events, True

        # Timeout condition
        if elapsed >= timeout_seconds:
            print(f"\n⚠ Timeout reached after {timeout_seconds}s")
            print(f"  Created {new_events} events (expected at least {expected_min_events})")
            return current_count, new_events, new_events > 0

        # Idle condition: no new events for a while after some were created
        if new_events > 0 and time_since_last_change >= idle_timeout:
            print(f"\n✓ Pipeline appears idle (no new events for {idle_timeout}s)")
            print(f"  Created {new_events} new events in {elapsed:.0f} seconds")
            return current_count, new_events, True

        # Still waiting
        if int(elapsed) % 30 == 0 and int(elapsed) > 0:
            print(f"  [{elapsed:.0f}s] Waiting... ({new_events} events so far)")

        await asyncio.sleep(poll_interval)


async def verify_pipeline_data() -> dict[str, int]:
    """Verify that pipeline-generated data exists in the database.

    Returns:
        Dictionary with counts of various data types
    """
    from sqlalchemy import func

    counts = {}

    async with get_session() as session:
        # Count events
        result = await session.execute(select(func.count()).select_from(Event))
        counts["events"] = result.scalar() or 0

        # Count detections
        result = await session.execute(select(func.count()).select_from(Detection))
        counts["detections"] = result.scalar() or 0

        # Count events by risk level
        result = await session.execute(
            select(Event.risk_level, func.count())
            .where(Event.deleted_at.is_(None))
            .group_by(Event.risk_level)
        )
        risk_levels = dict(result.fetchall())
        counts["events_critical"] = risk_levels.get("critical", 0)
        counts["events_high"] = risk_levels.get("high", 0)
        counts["events_medium"] = risk_levels.get("medium", 0)
        counts["events_low"] = risk_levels.get("low", 0)

        # Count events by camera
        result = await session.execute(
            select(Event.camera_id, func.count())
            .where(Event.deleted_at.is_(None))
            .group_by(Event.camera_id)
        )
        cameras = dict(result.fetchall())
        counts["cameras_with_events"] = len(cameras)

        # Count activity baselines
        result = await session.execute(select(func.count()).select_from(ActivityBaseline))
        counts["activity_baselines"] = result.scalar() or 0

        # Count class baselines
        result = await session.execute(select(func.count()).select_from(ClassBaseline))
        counts["class_baselines"] = result.scalar() or 0

    return counts


# Mock AI summaries for different risk levels
MOCK_SUMMARIES = {
    "low": [
        "Routine activity detected. Family member arriving home from work.",
        "Delivery driver dropped off package at front door. Normal delivery activity.",
        "Neighborhood cat passing through the backyard. No security concern.",
        "Mail carrier delivering daily mail. Expected activity.",
        "Landscaping crew performing scheduled yard maintenance.",
    ],
    "medium": [
        "Unknown vehicle parked briefly in driveway. Driver appeared to check phone before leaving.",
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
        "Activity matches expected patterns for this time of day. Subject identified as household member based on familiar clothing and behavior patterns. No indicators of suspicious intent.",
        "Standard delivery behavior observed. Driver followed normal package delivery protocol. Vehicle matches common delivery service markings.",
        "Animal activity only. No human presence detected. Motion was brief and consistent with wildlife patterns.",
    ],
    "medium": [
        "While the individual's behavior is not overtly threatening, the combination of unfamiliar face, hesitant approach, and departure without interaction warrants attention. Recommend reviewing footage if activity repeats.",
        "Vehicle presence was brief but unexplained. No clear legitimate purpose identified. Pattern does not match delivery or visitor behavior. Logging for pattern analysis.",
        "Unusual timing raises baseline concern. Activity itself appears benign but occurs outside normal hours for this type of movement.",
    ],
    "high": [
        "Multiple risk indicators present: unknown individual, suspicious behavior pattern (checking handles), and evasive movement when approached by passerby. High probability of criminal intent.",
        "Subject exhibited classic pre-surveillance behavior: slow approach, extended observation, photographing security features. Strong indicators of potential targeting.",
        "Coordinated approach by multiple unknowns suggests planning. Behavior inconsistent with legitimate visitors or delivery personnel. Immediate review recommended.",
    ],
}

OBJECT_TYPES = ["person", "vehicle", "animal", "package"]

# Cache for discovered camera images
_camera_images_cache: dict[str, list[str]] = {}


def discover_camera_images(camera_folder_path: str, use_container_path: bool = True) -> list[str]:
    """Discover actual image files in a camera folder.

    Args:
        camera_folder_path: Path to camera folder (e.g., /export/foscam/front_door)
        use_container_path: If True, convert paths to container format (/cameras/...)
                           for use with Docker/Podman deployments.

    Returns:
        List of image file paths found in the camera folder.
        Paths are converted to container format if use_container_path=True.
    """
    cache_key = f"{camera_folder_path}:{use_container_path}"
    if cache_key in _camera_images_cache:
        return _camera_images_cache[cache_key]

    images = []
    camera_path = Path(camera_folder_path)

    if camera_path.exists():
        # Search for jpg/png images recursively (Foscam stores in subdirs)
        for pattern in ["**/*.jpg", "**/*.JPG", "**/*.png", "**/*.PNG"]:
            images.extend(str(p) for p in camera_path.glob(pattern))

    # Sort by modification time (newest first) and limit to prevent memory issues
    images = sorted(images, key=lambda x: Path(x).stat().st_mtime, reverse=True)[:500]

    # Convert host paths to container paths for Docker/Podman deployments
    # /export/foscam/... -> /cameras/...
    if use_container_path:
        images = [img.replace("/export/foscam", "/cameras") for img in images]

    _camera_images_cache[cache_key] = images
    return images


# Entity metadata templates
ENTITY_METADATA_TEMPLATES = {
    "person": [
        {"clothing_color": "dark", "height_estimate": "tall", "build": "medium"},
        {"clothing_color": "light", "height_estimate": "average", "build": "slim"},
        {"clothing_color": "red", "height_estimate": "short", "build": "heavy"},
        {"clothing_color": "blue", "height_estimate": "tall", "build": "athletic"},
    ],
    "vehicle": [
        {"color": "black", "type": "sedan", "make": "unknown"},
        {"color": "white", "type": "SUV", "make": "Toyota"},
        {"color": "silver", "type": "truck", "make": "Ford"},
        {"color": "red", "type": "sports", "make": "unknown"},
    ],
    "animal": [
        {"species": "cat", "color": "orange"},
        {"species": "dog", "color": "brown", "size": "large"},
        {"species": "raccoon", "size": "medium"},
        {"species": "deer", "size": "large"},
    ],
    "package": [
        {"carrier": "UPS", "size": "medium"},
        {"carrier": "FedEx", "size": "small"},
        {"carrier": "USPS", "size": "large"},
        {"carrier": "Amazon", "size": "medium"},
    ],
}

# Log components and messages
LOG_COMPONENTS = ["api", "detector", "aggregator", "llm", "watcher", "websocket", "scheduler"]
LOG_MESSAGES = {
    "DEBUG": [
        "Processing request with params: {}",
        "Cache hit for key: detection_{}",
        "Loaded model weights from cache",
        "WebSocket client connected: {}",
        "Batch window started for camera {}",
    ],
    "INFO": [
        "Successfully processed detection batch",
        "Event created with risk score {}",
        "Model inference completed in {}ms",
        "Camera {} status changed to online",
        "Scheduled cleanup completed: {} items removed",
    ],
    "WARNING": [
        "Slow inference detected: {}ms (threshold: 500ms)",
        "High memory usage: {}% of available",
        "Rate limit approaching for endpoint {}",
        "Retry attempt {} for external service",
        "Cache miss rate elevated: {}%",
    ],
    "ERROR": [
        "Failed to connect to Redis: {}",
        "Model inference timeout after {}ms",
        "Database connection pool exhausted",
        "WebSocket broadcast failed: {}",
        "File not found: {}",
    ],
    "CRITICAL": [
        "System out of memory - emergency cleanup initiated",
        "Database connection lost - attempting recovery",
        "GPU memory exhausted - model unloaded",
        "Service health check failed - restarting",
    ],
}

# Audit action templates
AUDIT_ACTIONS = [
    (AuditAction.EVENT_REVIEWED, "event", "Event marked as reviewed"),
    (AuditAction.EVENT_DISMISSED, "event", "Event dismissed by user"),
    (AuditAction.SETTINGS_CHANGED, "settings", "System settings updated"),
    (AuditAction.AI_REEVALUATED, "event", "AI re-evaluation triggered"),
    (AuditAction.RULE_CREATED, "alert_rule", "New alert rule created"),
    (AuditAction.RULE_UPDATED, "alert_rule", "Alert rule updated"),
    (AuditAction.CAMERA_UPDATED, "camera", "Camera settings modified"),
    (AuditAction.MEDIA_EXPORTED, "export", "Media export completed"),
    (AuditAction.NOTIFICATION_TEST, "notification", "Test notification sent"),
    (AuditAction.CLEANUP_EXECUTED, "system", "Data cleanup executed"),
]


async def get_cameras() -> list[Camera]:
    """Get all cameras from the database."""
    async with get_session() as session:
        result = await session.execute(select(Camera))
        return list(result.scalars().all())


async def get_events() -> list[Event]:
    """Get all non-deleted events from the database."""
    async with get_session() as session:
        result = await session.execute(select(Event).where(Event.deleted_at.is_(None)))
        return list(result.scalars().all())


async def get_detections() -> list[Detection]:
    """Get all detections from the database."""
    async with get_session() as session:
        result = await session.execute(select(Detection))
        return list(result.scalars().all())


async def seed_mock_data(num_events: int = 15) -> tuple[int, int]:
    """Seed mock events and detections.

    Args:
        num_events: Number of mock events to create

    Returns:
        Tuple of (events_created, detections_created)
    """
    cameras = await get_cameras()
    if not cameras:
        print("Error: No cameras found in database. Run seed-cameras.py first.")
        return 0, 0

    print(f"Found {len(cameras)} cameras")

    events_created = 0
    detections_created = 0

    async with get_session() as session:
        for i in range(num_events):
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

            # Discover real images for this camera
            # Convert container path (/cameras/...) to host path (/export/foscam/...)
            host_folder_path = camera.folder_path.replace("/cameras", "/export/foscam")
            camera_images = discover_camera_images(host_folder_path)

            for j in range(num_detections):
                object_type = random.choice(OBJECT_TYPES)  # noqa: S311
                confidence = random.uniform(0.65, 0.98)  # noqa: S311

                # Generate mock bounding box
                bbox_x = random.randint(50, 400)  # noqa: S311
                bbox_y = random.randint(50, 300)  # noqa: S311
                bbox_width = random.randint(80, 200)  # noqa: S311
                bbox_height = random.randint(100, 250)  # noqa: S311

                # Use actual image path if available, otherwise use mock placeholder
                # Bug fix for NEM-2665: Use a clear mock indicator that won't trigger
                # thumbnail generation failures
                if camera_images:
                    file_path = random.choice(camera_images)  # noqa: S311
                else:
                    # Fallback to a mock:// URI scheme that indicates this is mock data
                    # This prevents thumbnail generation from failing on non-existent files
                    # Format: mock://camera_name/detection_index.jpg
                    file_path = f"mock://{camera.id}/detection_{i}_{j + 1}.jpg"

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
                session.add(detection)
                await session.flush()  # Get the ID
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
                reviewed=random.random() < 0.3,  # noqa: S311  # 30% reviewed
            )
            session.add(event)
            events_created += 1

            print(
                f"  Created event {i + 1}/{num_events}: {risk_level.upper()} ({risk_score}) on {camera.name}"
            )

        await session.commit()

    return events_created, detections_created


async def seed_entities(num_entities: int = 30) -> int:
    """Seed mock entities for the Entities page.

    Args:
        num_entities: Number of entities to create

    Returns:
        Number of entities created
    """
    detections = await get_detections()
    if not detections:
        print("Warning: No detections found. Entities will not have primary detections.")

    cameras = await get_cameras()
    # Use camera names (not IDs) for cameras_seen field - Bug fix for NEM-2666
    camera_names = [c.name for c in cameras] if cameras else ["unknown"]

    entities_created = 0

    async with get_session() as session:
        for i in range(num_entities):
            # Choose entity type with weighted distribution
            type_roll = random.random()  # noqa: S311
            if type_roll < 0.6:
                entity_type = EntityType.PERSON
            elif type_roll < 0.8:
                entity_type = EntityType.VEHICLE
            elif type_roll < 0.9:
                entity_type = EntityType.ANIMAL
            else:
                entity_type = EntityType.PACKAGE

            # Generate timestamps (spread over last 7 days)
            days_ago = random.uniform(0, 7)  # noqa: S311
            first_seen = datetime.now(UTC) - timedelta(days=days_ago)
            # Last seen between first_seen and now
            hours_since_first = random.uniform(0, days_ago * 24)  # noqa: S311
            last_seen = first_seen + timedelta(hours=hours_since_first)

            # Detection count (repeat visitors have higher counts)
            is_repeat = random.random() < 0.3  # noqa: S311
            detection_count = random.randint(5, 25) if is_repeat else random.randint(1, 4)  # noqa: S311

            # Generate mock embedding vector (512 dimensions for CLIP)
            embedding_vector = {
                "vector": [random.uniform(-1, 1) for _ in range(512)],  # noqa: S311
                "model": "clip-vit-base-patch32",
                "dimension": 512,
            }

            # Get metadata template
            metadata_templates = ENTITY_METADATA_TEMPLATES.get(entity_type.value, [{}])
            entity_metadata = random.choice(metadata_templates).copy()  # noqa: S311
            # Use camera names for cameras_seen field - Bug fix for NEM-2666
            entity_metadata["cameras_seen"] = random.sample(
                camera_names,
                min(len(camera_names), random.randint(1, 3)),  # noqa: S311
            )

            # Link to a detection for thumbnail (map entity types to detection object_types)
            # Detection object_types: car, truck, vehicle, bicycle, person, animal, bird, package
            # Entity types: person, vehicle, animal, package, other
            entity_to_detection_types = {
                "person": ["person"],
                "vehicle": ["car", "truck", "vehicle", "bicycle"],
                "animal": ["animal", "bird"],
                "package": ["package"],
                "other": [],  # No matching detections for "other" type
            }
            matching_object_types = entity_to_detection_types.get(entity_type.value, [])

            primary_detection_id = None
            if detections and matching_object_types:
                # Filter to detections with real file paths and matching object types
                matching_detections = [
                    d
                    for d in detections
                    if d.object_type in matching_object_types
                    and d.file_path
                    and not d.file_path.startswith("mock://")
                ]
                if matching_detections:
                    primary_detection_id = random.choice(matching_detections).id  # noqa: S311

            entity = Entity(
                entity_type=entity_type.value,
                embedding_vector=embedding_vector,
                first_seen_at=first_seen,
                last_seen_at=last_seen,
                detection_count=detection_count,
                entity_metadata=entity_metadata,
                primary_detection_id=primary_detection_id,
            )
            session.add(entity)
            entities_created += 1

            if (i + 1) % 10 == 0:
                print(f"  Created {i + 1}/{num_entities} entities...")

        await session.commit()

    print(f"  Created {entities_created} entities")
    return entities_created


async def seed_alert_rules(num_rules: int = 5) -> list[str]:
    """Seed alert rules.

    Args:
        num_rules: Number of alert rules to create

    Returns:
        List of created rule IDs
    """
    cameras = await get_cameras()
    camera_ids = [c.id for c in cameras] if cameras else []

    rule_templates = [
        {
            "name": "High Risk Alert",
            "description": "Alert when risk score exceeds 70",
            "severity": AlertSeverity.HIGH,
            "risk_threshold": 70,
            "object_types": None,
        },
        {
            "name": "Critical Person Detection",
            "description": "Alert on critical-risk person detections",
            "severity": AlertSeverity.CRITICAL,
            "risk_threshold": 85,
            "object_types": ["person"],
        },
        {
            "name": "Nighttime Activity",
            "description": "Alert on any activity between 11 PM and 5 AM",
            "severity": AlertSeverity.MEDIUM,
            "risk_threshold": 30,
            "schedule": {"start_time": "23:00", "end_time": "05:00"},
        },
        {
            "name": "Vehicle Alert",
            "description": "Alert on unknown vehicle detections",
            "severity": AlertSeverity.MEDIUM,
            "risk_threshold": 50,
            "object_types": ["vehicle"],
        },
        {
            "name": "Front Door Monitor",
            "description": "Alert on all front door activity",
            "severity": AlertSeverity.LOW,
            "risk_threshold": 20,
            "camera_ids": [cid for cid in camera_ids if "front" in cid.lower()][:1],
        },
    ]

    rule_ids = []

    async with get_session() as session:
        for i in range(min(num_rules, len(rule_templates))):
            template = rule_templates[i]
            rule = AlertRule(
                name=template["name"],
                description=template["description"],
                enabled=True,
                severity=template["severity"],
                risk_threshold=template.get("risk_threshold"),
                object_types=template.get("object_types"),
                camera_ids=template.get("camera_ids"),
                schedule=template.get("schedule"),
                cooldown_seconds=300,
            )
            session.add(rule)
            await session.flush()
            rule_ids.append(rule.id)
            print(f"  Created alert rule: {rule.name}")

        await session.commit()

    return rule_ids


async def seed_alerts(num_alerts: int = 20) -> int:
    """Seed mock alerts for the Alerts page.

    Args:
        num_alerts: Number of alerts to create

    Returns:
        Number of alerts created
    """
    events = await get_events()
    if not events:
        print("Error: No events found. Run event seeding first.")
        return 0

    # Ensure we have alert rules
    async with get_session() as session:
        result = await session.execute(select(AlertRule))
        rules = list(result.scalars().all())

    if not rules:
        print("Creating alert rules first...")
        rule_ids = await seed_alert_rules()
        async with get_session() as session:
            result = await session.execute(select(AlertRule).where(AlertRule.id.in_(rule_ids)))
            rules = list(result.scalars().all())

    alerts_created = 0
    status_weights = [
        (AlertStatus.PENDING, 0.3),
        (AlertStatus.DELIVERED, 0.3),
        (AlertStatus.ACKNOWLEDGED, 0.25),
        (AlertStatus.DISMISSED, 0.15),
    ]

    async with get_session() as session:
        for i in range(num_alerts):
            event = random.choice(events)  # noqa: S311
            rule = random.choice(rules) if rules else None  # noqa: S311

            # Weighted random status
            status_roll = random.random()  # noqa: S311
            cumulative = 0
            status = AlertStatus.PENDING
            for s, weight in status_weights:
                cumulative += weight
                if status_roll < cumulative:
                    status = s
                    break

            # Match severity to event risk level
            if event.risk_score and event.risk_score >= 85:
                severity = AlertSeverity.CRITICAL
            elif event.risk_score and event.risk_score >= 60:
                severity = AlertSeverity.HIGH
            elif event.risk_score and event.risk_score >= 30:
                severity = AlertSeverity.MEDIUM
            else:
                severity = AlertSeverity.LOW

            # Generate timestamps
            hours_ago = random.uniform(0, 48)  # noqa: S311
            created_at = datetime.now(UTC) - timedelta(hours=hours_ago)
            delivered_at = None
            if status in (AlertStatus.DELIVERED, AlertStatus.ACKNOWLEDGED, AlertStatus.DISMISSED):
                delivered_at = created_at + timedelta(seconds=random.randint(1, 30))  # noqa: S311

            alert = Alert(
                event_id=event.id,
                rule_id=rule.id if rule else None,
                severity=severity,
                status=status,
                created_at=created_at,
                delivered_at=delivered_at,
                dedup_key=f"{event.camera_id}:{rule.id if rule else 'manual'}:{i}",
                channels=["push", "email"] if random.random() < 0.5 else ["push"],  # noqa: S311
            )
            session.add(alert)
            alerts_created += 1

            if (i + 1) % 10 == 0:
                print(f"  Created {i + 1}/{num_alerts} alerts...")

        await session.commit()

    print(f"  Created {alerts_created} alerts")
    return alerts_created


async def seed_audit_logs(num_logs: int = 50) -> int:
    """Seed mock audit logs for the Audit page.

    Args:
        num_logs: Number of audit logs to create

    Returns:
        Number of audit logs created
    """
    events = await get_events()
    cameras = await get_cameras()

    logs_created = 0
    actors = ["system", "admin", "user@local", "api_client", "scheduler"]
    ip_addresses = ["127.0.0.1", "192.168.1.100", "10.0.0.50", None]

    async with get_session() as session:
        for i in range(num_logs):
            action_template = random.choice(AUDIT_ACTIONS)  # noqa: S311
            action, resource_type, description = action_template

            # Generate resource ID based on type
            resource_id = None
            if resource_type == "event" and events:
                resource_id = str(random.choice(events).id)  # noqa: S311
            elif resource_type == "camera" and cameras:
                resource_id = random.choice(cameras).id  # noqa: S311
            elif resource_type == "alert_rule":
                resource_id = str(uuid.uuid4())
            elif resource_type in ("settings", "system", "notification", "export"):
                resource_id = resource_type

            # Generate timestamp (spread over last 7 days)
            days_ago = random.uniform(0, 7)  # noqa: S311
            timestamp = datetime.now(UTC) - timedelta(days=days_ago)

            # Status - mostly success
            status = "success" if random.random() < 0.9 else "failure"  # noqa: S311

            audit_log = AuditLog(
                timestamp=timestamp,
                action=action.value,
                resource_type=resource_type,
                resource_id=resource_id,
                actor=random.choice(actors),  # noqa: S311
                ip_address=random.choice(ip_addresses),  # noqa: S311
                user_agent="Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0"
                if random.random() < 0.7  # noqa: S311
                else None,
                details={"description": description, "changes": {"field": "value"}},
                status=status,
            )
            session.add(audit_log)
            logs_created += 1

            if (i + 1) % 20 == 0:
                print(f"  Created {i + 1}/{num_logs} audit logs...")

        await session.commit()

    print(f"  Created {logs_created} audit logs")
    return logs_created


async def seed_application_logs(num_logs: int = 100) -> int:
    """Seed mock application logs for the Logs page.

    Args:
        num_logs: Number of application logs to create

    Returns:
        Number of logs created
    """
    cameras = await get_cameras()
    camera_ids = [c.id for c in cameras] if cameras else [None]

    logs_created = 0
    # Weight levels: mostly INFO, fewer DEBUG, some warnings, few errors
    level_weights = [
        ("DEBUG", 0.15),
        ("INFO", 0.50),
        ("WARNING", 0.20),
        ("ERROR", 0.12),
        ("CRITICAL", 0.03),
    ]

    async with get_session() as session:
        for i in range(num_logs):
            # Weighted random level
            level_roll = random.random()  # noqa: S311
            cumulative = 0
            level = "INFO"
            for lv, weight in level_weights:
                cumulative += weight
                if level_roll < cumulative:
                    level = lv
                    break

            component = random.choice(LOG_COMPONENTS)  # noqa: S311
            message_template = random.choice(LOG_MESSAGES[level])  # noqa: S311

            # Fill in template placeholders
            message = message_template.format(
                random.randint(1, 1000),  # noqa: S311
                random.randint(100, 5000),  # noqa: S311
                f"cam_{random.randint(1, 10)}",  # noqa: S311
            )

            # Generate timestamp (spread over last 24 hours)
            hours_ago = random.uniform(0, 24)  # noqa: S311
            timestamp = datetime.now(UTC) - timedelta(hours=hours_ago)

            log = Log(
                timestamp=timestamp,
                level=level,
                component=component,
                message=message,
                camera_id=random.choice(camera_ids) if random.random() < 0.5 else None,  # noqa: S311
                duration_ms=random.randint(1, 2000) if random.random() < 0.3 else None,  # noqa: S311
                source="backend",
                extra={"request_id": str(uuid.uuid4())[:8]} if random.random() < 0.4 else None,  # noqa: S311
            )
            session.add(log)
            logs_created += 1

            if (i + 1) % 50 == 0:
                print(f"  Created {i + 1}/{num_logs} application logs...")

        await session.commit()

    print(f"  Created {logs_created} application logs")
    return logs_created


async def seed_trash(num_deleted: int = 10) -> int:
    """Soft-delete some events to populate the Trash page.

    Bug fix for NEM-2664: Ensure all trashed events have a valid deleted_at
    timestamp within the last 7 days.

    Args:
        num_deleted: Number of events to soft-delete

    Returns:
        Number of events soft-deleted
    """
    async with get_session() as session:
        # Get non-deleted events
        result = await session.execute(
            select(Event).where(Event.deleted_at.is_(None)).limit(num_deleted * 2)
        )
        events = list(result.scalars().all())

        if not events:
            print("Error: No events available to soft-delete.")
            return 0

        # Soft-delete a random selection
        to_delete = random.sample(events, min(num_deleted, len(events)))
        deleted_count = 0

        for event in to_delete:
            # Bug fix for NEM-2664: Set deleted_at to a valid timestamp
            # Generate a random time within the last 7 days (minimum 1 hour ago)
            hours_ago = random.uniform(1, 168)  # noqa: S311  # 1 hour to 7 days
            deleted_timestamp = datetime.now(UTC) - timedelta(hours=hours_ago)
            # Ensure the timestamp is valid and timezone-aware
            event.deleted_at = deleted_timestamp.replace(microsecond=0)
            deleted_count += 1
            print(f"    Soft-deleted event {event.id} (deleted_at: {event.deleted_at})")

        await session.commit()

    print(f"  Soft-deleted {deleted_count} events for trash")
    return deleted_count


async def seed_activity_baselines(min_samples_per_slot: int = 15) -> int:
    """Seed activity baseline data for all cameras to ensure learning is complete.

    Creates 168 entries per camera (24 hours x 7 days), each with sufficient
    samples to mark the baseline as "learning complete" (requires 134+ slots
    with 10+ samples each).

    Uses UPSERT to handle cases where the pipeline has already created some baselines.

    Args:
        min_samples_per_slot: Minimum samples per time slot (default 15, above the 10 required)

    Returns:
        Number of baseline entries created/updated
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    cameras = await get_cameras()
    if not cameras:
        print("Error: No cameras found in database. Run seed-cameras.py first.")
        return 0

    baselines_upserted = 0

    # Activity patterns - simulate realistic activity throughout the day
    # Higher activity during daytime hours (7am-9pm), lower at night
    def get_activity_weight(hour: int) -> float:
        if 0 <= hour < 6:
            return 0.2  # Very low overnight
        elif 6 <= hour < 8:
            return 0.6  # Morning ramp-up
        elif 8 <= hour < 18:
            return 1.0  # Daytime peak
        elif 18 <= hour < 21:
            return 0.8  # Evening
        else:
            return 0.4  # Late evening

    async with get_session() as session:
        for camera in cameras:
            # Build all baseline records for this camera
            baseline_records = []
            for day_of_week in range(7):
                for hour in range(24):
                    # Generate realistic activity counts based on time patterns
                    base_activity = random.uniform(2.0, 8.0)  # noqa: S311
                    weight = get_activity_weight(hour)
                    # Weekends have slightly different patterns
                    if day_of_week in (5, 6):  # Saturday, Sunday
                        weight *= 0.85  # Less activity on weekends

                    avg_count = base_activity * weight
                    # Add some randomness
                    avg_count *= random.uniform(0.8, 1.2)  # noqa: S311

                    baseline_records.append(
                        {
                            "camera_id": camera.id,
                            "hour": hour,
                            "day_of_week": day_of_week,
                            "avg_count": round(avg_count, 2),
                            "sample_count": min_samples_per_slot + random.randint(0, 20),  # noqa: S311
                            "last_updated": datetime.now(UTC),
                        }
                    )

            # Use PostgreSQL UPSERT (INSERT ON CONFLICT UPDATE)
            stmt = pg_insert(ActivityBaseline).values(baseline_records)
            stmt = stmt.on_conflict_do_update(
                index_elements=["camera_id", "hour", "day_of_week"],
                set_={
                    "avg_count": stmt.excluded.avg_count,
                    "sample_count": stmt.excluded.sample_count,
                    "last_updated": stmt.excluded.last_updated,
                },
            )
            await session.execute(stmt)
            baselines_upserted += len(baseline_records)

            print(f"  Created/updated 168 activity baselines for camera: {camera.name}")

        await session.commit()

    print(f"  Created/updated {baselines_upserted} total activity baseline entries")
    return baselines_upserted


async def seed_pipeline_latency(num_samples: int = 100, time_span_hours: int = 24) -> int:
    """Seed pipeline latency data via the admin API.

    This calls the backend API to populate the in-memory PipelineLatencyTracker
    with realistic latency samples for UI testing.

    Args:
        num_samples: Number of samples per pipeline stage
        time_span_hours: Time span for the historical data

    Returns:
        Total number of samples seeded (samples * stages)
    """
    import httpx

    backend_url = os.environ.get("BACKEND_URL", "http://localhost:8000")
    api_key = os.environ.get("ADMIN_API_KEY", "")

    headers = {}
    if api_key:
        headers["X-Admin-API-Key"] = api_key

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{backend_url}/api/admin/seed/pipeline-latency",
                json={
                    "num_samples": num_samples,
                    "time_span_hours": time_span_hours,
                },
                headers=headers,
            )

            if response.status_code == 200:
                data = response.json()
                stages = len(data.get("stages_seeded", []))
                samples = data.get("samples_per_stage", 0)
                print(f"  Seeded {samples} samples for {stages} pipeline stages")
                print(f"  Stages: {', '.join(data.get('stages_seeded', []))}")
                return samples * stages
            elif response.status_code == 403:
                print("  ⚠ Admin API not enabled (DEBUG=true and ADMIN_ENABLED=true required)")
                print("  Pipeline latency will be empty until real pipeline processes images")
                return 0
            else:
                print(f"  ⚠ Failed to seed pipeline latency: {response.status_code}")
                print(f"    Response: {response.text[:200]}")
                return 0
    except httpx.ConnectError:
        print("  ⚠ Could not connect to backend API")
        print("  Pipeline latency will be empty until real pipeline processes images")
        return 0
    except Exception as e:
        print(f"  ⚠ Error seeding pipeline latency: {e}")
        return 0


async def seed_class_baselines(min_samples_per_slot: int = 15) -> int:
    """Seed class frequency baseline data for all cameras.

    Creates baseline entries for common object classes (person, vehicle, animal, package)
    across all hours for each camera. This enables class-based anomaly detection.

    Uses UPSERT to handle cases where the pipeline has already created some baselines.

    Args:
        min_samples_per_slot: Minimum samples per time slot (default 15)

    Returns:
        Number of class baseline entries created/updated
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    cameras = await get_cameras()
    if not cameras:
        print("Error: No cameras found in database. Run seed-cameras.py first.")
        return 0

    baselines_upserted = 0

    # Detection classes with typical frequency patterns
    class_patterns = {
        "person": {"base_freq": 3.0, "peak_hours": range(7, 22)},
        "vehicle": {"base_freq": 2.0, "peak_hours": range(6, 20)},
        "animal": {"base_freq": 0.5, "peak_hours": list(range(5, 8)) + list(range(18, 22))},
        "package": {"base_freq": 0.3, "peak_hours": range(10, 17)},
    }

    async with get_session() as session:
        for camera in cameras:
            # Build all baseline records for this camera
            baseline_records = []
            for detection_class, pattern in class_patterns.items():
                for hour in range(24):
                    # Higher frequency during peak hours
                    if hour in pattern["peak_hours"]:
                        frequency = pattern["base_freq"] * random.uniform(0.8, 1.5)  # noqa: S311
                    else:
                        frequency = pattern["base_freq"] * random.uniform(0.1, 0.4)  # noqa: S311

                    baseline_records.append(
                        {
                            "camera_id": camera.id,
                            "detection_class": detection_class,
                            "hour": hour,
                            "frequency": round(frequency, 4),
                            "sample_count": min_samples_per_slot + random.randint(0, 15),  # noqa: S311
                            "last_updated": datetime.now(UTC),
                        }
                    )

            # Use PostgreSQL UPSERT (INSERT ON CONFLICT UPDATE)
            stmt = pg_insert(ClassBaseline).values(baseline_records)
            stmt = stmt.on_conflict_do_update(
                index_elements=["camera_id", "detection_class", "hour"],
                set_={
                    "frequency": stmt.excluded.frequency,
                    "sample_count": stmt.excluded.sample_count,
                    "last_updated": stmt.excluded.last_updated,
                },
            )
            await session.execute(stmt)
            baselines_upserted += len(baseline_records)

            print(
                f"  Created/updated {len(class_patterns) * 24} class baselines for camera: {camera.name}"
            )

        await session.commit()

    print(f"  Created/updated {baselines_upserted} total class baseline entries")
    return baselines_upserted


async def clear_all_data() -> None:
    """Clear all seeded data from the database."""
    async with get_session() as session:
        # Order matters due to foreign key constraints
        print("  Clearing alerts...")
        await session.execute(delete(Alert))

        print("  Clearing alert rules...")
        await session.execute(delete(AlertRule))

        print("  Clearing entities...")
        await session.execute(delete(Entity))

        print("  Clearing audit logs...")
        await session.execute(delete(AuditLog))

        print("  Clearing application logs...")
        await session.execute(delete(Log))

        print("  Clearing events...")
        await session.execute(delete(Event))

        print("  Clearing detections...")
        await session.execute(delete(Detection))

        print("  Clearing activity baselines...")
        await session.execute(delete(ActivityBaseline))

        print("  Clearing class baselines...")
        await session.execute(delete(ClassBaseline))

        await session.commit()

    print("Cleared all seeded data")


async def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Seed the system by exercising the full AI pipeline end-to-end",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default: Full pipeline + all supporting data (recommended for UI validation)
  uv run python scripts/seed-mock-events.py

  # Process more images and wait longer
  uv run python scripts/seed-mock-events.py --images 50 --timeout 600

  # Clear all data first, then run full pipeline
  uv run python scripts/seed-mock-events.py --clear

  # Quick run without waiting for pipeline completion
  uv run python scripts/seed-mock-events.py --no-wait

  # Skip supporting data (entities, alerts, logs) - only pipeline data
  uv run python scripts/seed-mock-events.py --no-extras

  # Legacy: Use mock data instead of real pipeline (for testing without AI)
  uv run python scripts/seed-mock-events.py --mock

Pipeline Flow:
  1. Touch camera images to trigger file watcher
  2. File Watcher → RT-DETRv2 (object detection)
  3. RT-DETRv2 → Batch Aggregator (group detections)
  4. Batch Aggregator → Nemotron LLM (risk analysis)
  5. Events created with AI-generated summaries and risk scores
  6. Pipeline latency telemetry recorded for monitoring

This generates real data including:
  - Events with actual LLM reasoning
  - Detection bounding boxes from RT-DETRv2
  - Pipeline latency metrics for performance monitoring
  - Activity baselines for anomaly detection

By default, also seeds supporting data for full UI testing:
  - Entities (persons, vehicles) for the Entities page
  - Alerts for the Alerts page
  - Audit logs for the Audit Log page
  - Application logs for the Logs page
  - Soft-deleted events for the Trash page
""",
    )
    parser.add_argument(
        "--images",
        type=int,
        default=30,
        help="Number of images to process through the pipeline (default: 30)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.3,
        help="Delay between touching images in seconds (default: 0.3)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Max seconds to wait for pipeline completion (default: 300)",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Don't wait for pipeline completion (trigger and exit immediately)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock data instead of real pipeline (legacy, for testing without AI services)",
    )
    parser.add_argument(
        "--no-extras",
        action="store_true",
        help="Skip seeding entities, alerts, audit logs, and app logs (seeded by default)",
    )
    parser.add_argument(
        "--no-baselines",
        action="store_true",
        help="Skip seeding baseline data (baselines are seeded by default)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Number of mock events (only with --mock)",
    )
    parser.add_argument(
        "--entities",
        type=int,
        default=None,
        help="Number of entities to create",
    )
    parser.add_argument(
        "--alerts",
        type=int,
        default=None,
        help="Number of alerts to create",
    )
    parser.add_argument(
        "--audit-logs",
        type=int,
        default=None,
        help="Number of audit logs to create",
    )
    parser.add_argument(
        "--logs",
        type=int,
        default=None,
        help="Number of application logs to create",
    )
    parser.add_argument(
        "--trash",
        type=int,
        default=None,
        help="Number of events to soft-delete for trash",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing data before seeding",
    )

    args = parser.parse_args()

    print("Initializing database...")
    await init_db()

    if args.clear:
        print("\nClearing existing data...")
        await clear_all_data()

    total_created = {}

    # Default behavior: trigger real pipeline and wait for completion
    if not args.mock:
        # Get initial event count
        initial_events = await get_events()
        initial_count = len(initial_events)

        print("\n" + "=" * 50)
        print("TRIGGERING REAL AI PIPELINE")
        print("=" * 50)
        print(f"Current events in database: {initial_count}")

        touched = trigger_pipeline(num_images=args.images, delay_between=args.delay)
        total_created["images_triggered"] = touched

        # Wait for pipeline completion unless --no-wait
        if not args.no_wait and touched > 0:
            # Expect roughly 1 event per 2-3 images processed (due to batching)
            expected_events = max(5, touched // 3)
            _final_count, new_events, success = await wait_for_pipeline_completion(
                initial_event_count=initial_count,
                expected_min_events=expected_events,
                timeout_seconds=args.timeout,
            )
            total_created["events_created"] = new_events

            if not success:
                print("\n⚠ Warning: Pipeline may not have completed fully")
                print("  Check that AI services (RT-DETR, Nemotron) are running")
        elif args.no_wait:
            print("\n--no-wait specified, skipping pipeline completion wait")
            print("Events will be created asynchronously as pipeline processes images")

        # Seed extras by default (unless --no-extras is specified)
        if not args.no_extras:
            print("\nSeeding supporting data...")
            entities_count = args.entities or 30
            alerts_count = args.alerts or 20
            audit_logs_count = args.audit_logs or 50
            logs_count = args.logs or 100
            trash_count = args.trash or 10

            # Check if events exist - alerts and trash need events to link to
            current_events = await get_events()
            if not current_events:
                print("\n⚠ No events found after pipeline phase.")
                print("  Seeding mock events so alerts/trash can be created...")
                mock_event_count = args.count or 50
                events, detections = await seed_mock_data(mock_event_count)
                total_created["mock_events"] = events
                total_created["mock_detections"] = detections

            print(f"\nSeeding {entities_count} entities...")
            total_created["entities"] = await seed_entities(entities_count)

            print(f"\nSeeding {alerts_count} alerts...")
            total_created["alerts"] = await seed_alerts(alerts_count)

            print(f"\nSeeding {audit_logs_count} audit logs...")
            total_created["audit_logs"] = await seed_audit_logs(audit_logs_count)

            print(f"\nSeeding {logs_count} application logs...")
            total_created["logs"] = await seed_application_logs(logs_count)

            if trash_count:
                print(f"\nSoft-deleting {trash_count} events for trash...")
                total_created["trash"] = await seed_trash(trash_count)

    else:
        # Legacy mock data mode
        print("\n" + "=" * 50)
        print("SEEDING MOCK DATA (legacy mode)")
        print("=" * 50)

        events_count = args.count or 100
        entities_count = args.entities or 50
        alerts_count = args.alerts or 30
        audit_logs_count = args.audit_logs or 75
        logs_count = args.logs or 150
        trash_count = args.trash or 15

        print(f"\nSeeding {events_count} mock events...")
        events, detections = await seed_mock_data(events_count)
        total_created["events"] = events
        total_created["detections"] = detections

        print(f"\nSeeding {entities_count} entities...")
        total_created["entities"] = await seed_entities(entities_count)

        print(f"\nSeeding {alerts_count} alerts...")
        total_created["alerts"] = await seed_alerts(alerts_count)

        print(f"\nSeeding {audit_logs_count} audit logs...")
        total_created["audit_logs"] = await seed_audit_logs(audit_logs_count)

        print(f"\nSeeding {logs_count} application logs...")
        total_created["logs"] = await seed_application_logs(logs_count)

        if trash_count:
            print(f"\nSoft-deleting {trash_count} events for trash...")
            total_created["trash"] = await seed_trash(trash_count)

    # Seed baselines by default (unless --no-baselines is used)
    # This ensures "learning complete" status for analytics dashboards
    if not args.no_baselines:
        print("\n" + "=" * 50)
        print("SEEDING BASELINE DATA (for 'Learning Complete' status)")
        print("=" * 50)

        print("\nSeeding activity baselines (168 time slots per camera)...")
        total_created["activity_baselines"] = await seed_activity_baselines()

        print("\nSeeding class baselines (4 classes x 24 hours per camera)...")
        total_created["class_baselines"] = await seed_class_baselines()

        print("\nSeeding pipeline latency data (for monitoring charts)...")
        total_created["pipeline_latency_samples"] = await seed_pipeline_latency(
            num_samples=100, time_span_hours=24
        )

    # Print summary
    print("\n" + "=" * 50)
    print("SEEDING COMPLETE")
    print("=" * 50)
    for data_type, count in total_created.items():
        print(f"  {data_type}: {count}")

    # Final verification
    print("\n" + "=" * 50)
    print("DATA VERIFICATION")
    print("=" * 50)
    counts = await verify_pipeline_data()
    print(f"  Total events: {counts['events']}")
    print(f"  Total detections: {counts['detections']}")
    print("  Events by risk level:")
    print(f"    - Critical: {counts['events_critical']}")
    print(f"    - High: {counts['events_high']}")
    print(f"    - Medium: {counts['events_medium']}")
    print(f"    - Low: {counts['events_low']}")
    print(f"  Cameras with events: {counts['cameras_with_events']}")
    print(f"  Activity baselines: {counts['activity_baselines']}")
    print(f"  Class baselines: {counts['class_baselines']}")

    # Check for UI readiness
    print("\n" + "=" * 50)
    print("UI READINESS CHECK")
    print("=" * 50)
    issues = []

    if counts["events"] == 0:
        issues.append("❌ No events - Events page will be empty")
    else:
        print(f"✓ Events: {counts['events']} events available")

    if counts["detections"] == 0:
        issues.append("❌ No detections - Detection analytics will be empty")
    else:
        print(f"✓ Detections: {counts['detections']} detections available")

    if counts["activity_baselines"] < 134:
        issues.append("⚠ Activity baselines incomplete - 'Still Learning' may show")
    else:
        print(f"✓ Activity baselines: Learning complete ({counts['activity_baselines']} entries)")

    if counts["class_baselines"] == 0:
        issues.append("⚠ No class baselines - Class frequency charts will be empty")
    else:
        print(f"✓ Class baselines: {counts['class_baselines']} entries")

    if counts["cameras_with_events"] == 0:
        issues.append("❌ No cameras with events - Camera analytics will be empty")
    else:
        print(f"✓ Cameras with data: {counts['cameras_with_events']} cameras")

    if issues:
        print("\nIssues found:")
        for issue in issues:
            print(f"  {issue}")
        return 1

    print("\n✓ All UI components should have data!")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
