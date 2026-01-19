#!/usr/bin/env python3
"""Seed the system by exercising the full AI pipeline end-to-end.

This script triggers real pipeline processing by touching images in camera
watch folders, causing the file watcher to process them through:
  1. File Watcher → detects touched images
  2. RT-DETRv2 → object detection
  3. Batch Aggregator → groups detections into events
  4. Nemotron LLM → risk analysis with reasoning

This creates real events with actual LLM analysis for comprehensive testing.

Usage:
    # Default: Touch 100 images from /export/foscam and run full pipeline
    uv run python scripts/seed-events.py

    # Process fewer images (faster)
    uv run python scripts/seed-events.py --images 30

    # Skip supporting data (entities, alerts, logs) - only pipeline data
    uv run python scripts/seed-events.py --no-extras

    # Clear all data before seeding
    uv run python scripts/seed-events.py --clear
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

        # Count entities
        result = await session.execute(select(func.count()).select_from(Entity))
        counts["entities"] = result.scalar() or 0

        # Count alerts
        result = await session.execute(select(func.count()).select_from(Alert))
        counts["alerts"] = result.scalar() or 0

    return counts


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


async def seed_entities_from_detections(max_entities: int = 30) -> int:
    """Create entities from real detections using CLIP embeddings.

    This calls the CLIP service to generate real embeddings from detection images,
    creating entities that represent actual detected objects.

    Args:
        max_entities: Maximum number of entities to create

    Returns:
        Number of entities created
    """
    import httpx

    detections = await get_detections()
    if not detections:
        print("  Warning: No detections found. Run pipeline first to create detections.")
        return 0

    # Filter to detections with real file paths (not mock)
    real_detections = [
        d for d in detections if d.file_path and not d.file_path.startswith("mock://")
    ]
    if not real_detections:
        print("  Warning: No detections with real file paths found.")
        return 0

    # Group detections by object type for entity creation
    by_type = {}
    for det in real_detections:
        obj_type = det.object_type or "unknown"
        if obj_type not in by_type:
            by_type[obj_type] = []
        by_type[obj_type].append(det)

    clip_url = os.environ.get("CLIP_URL", "http://localhost:8093")
    entities_created = 0

    async with get_session() as session:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for obj_type, type_detections in by_type.items():
                # Limit entities per type
                sample_size = min(len(type_detections), max_entities // len(by_type))
                sampled = (
                    random.sample(type_detections, sample_size)
                    if len(type_detections) > sample_size
                    else type_detections
                )

                for det in sampled:
                    if entities_created >= max_entities:
                        break

                    # Convert container path to host path for CLIP service
                    image_path = det.file_path
                    if image_path.startswith("/cameras"):
                        image_path = image_path.replace("/cameras", "/export/foscam")

                    # Try to get real embedding from CLIP
                    embedding_vector = None
                    try:
                        # Check if file exists
                        if Path(image_path).exists():
                            response = await client.post(
                                f"{clip_url}/embed",
                                json={"image_path": image_path},
                            )
                            if response.status_code == 200:
                                data = response.json()
                                embedding_vector = {
                                    "vector": data.get("embedding", []),
                                    "model": "clip-vit-base-patch32",
                                    "dimension": len(data.get("embedding", [])),
                                }
                    except Exception as e:
                        print(f"    CLIP embedding failed for {det.id}: {e}")

                    # Map detection object_type to entity_type
                    entity_type_map = {
                        "person": "person",
                        "car": "vehicle",
                        "truck": "vehicle",
                        "vehicle": "vehicle",
                        "bicycle": "vehicle",
                        "motorcycle": "vehicle",
                        "dog": "animal",
                        "cat": "animal",
                        "bird": "animal",
                        "animal": "animal",
                        "package": "package",
                        "box": "package",
                    }
                    entity_type = entity_type_map.get(obj_type, "other")

                    entity = Entity(
                        entity_type=entity_type,
                        embedding_vector=embedding_vector,
                        first_seen_at=det.detected_at,
                        last_seen_at=det.detected_at,
                        detection_count=1,
                        entity_metadata={"source_detection_id": det.id, "object_type": obj_type},
                        primary_detection_id=det.id,
                    )
                    session.add(entity)
                    entities_created += 1

                    if entities_created % 10 == 0:
                        print(f"    Created {entities_created}/{max_entities} entities...")

        await session.commit()

    print(f"  Created {entities_created} entities from real detections")
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


async def seed_alerts_from_events(num_alerts: int = 20) -> int:
    """Create alerts from real events based on alert rules.

    Args:
        num_alerts: Number of alerts to create

    Returns:
        Number of alerts created
    """
    events = await get_events()
    if not events:
        print("  Error: No events found. Run pipeline first.")
        return 0

    # Ensure we have alert rules
    async with get_session() as session:
        result = await session.execute(select(AlertRule))
        rules = list(result.scalars().all())

    if not rules:
        print("  Creating alert rules first...")
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
        for i in range(min(num_alerts, len(events))):
            event = events[i]
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

            delivered_at = None
            if status in (AlertStatus.DELIVERED, AlertStatus.ACKNOWLEDGED, AlertStatus.DISMISSED):
                delivered_at = event.started_at + timedelta(seconds=random.randint(1, 30))  # noqa: S311

            alert = Alert(
                event_id=event.id,
                rule_id=rule.id if rule else None,
                severity=severity,
                status=status,
                created_at=event.started_at,
                delivered_at=delivered_at,
                dedup_key=f"{event.camera_id}:{rule.id if rule else 'manual'}:{i}",
                channels=["push", "email"] if random.random() < 0.5 else ["push"],  # noqa: S311
            )
            session.add(alert)
            alerts_created += 1

            if (i + 1) % 10 == 0:
                print(f"    Created {i + 1}/{num_alerts} alerts...")

        await session.commit()

    print(f"  Created {alerts_created} alerts from real events")
    return alerts_created


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


async def seed_audit_logs(num_logs: int = 50) -> int:
    """Seed audit logs based on real events and cameras.

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

            # Generate resource ID based on type - use real IDs where possible
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
                print(f"    Created {i + 1}/{num_logs} audit logs...")

        await session.commit()

    print(f"  Created {logs_created} audit logs")
    return logs_created


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


async def seed_application_logs(num_logs: int = 100) -> int:
    """Seed application logs.

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
                print(f"    Created {i + 1}/{num_logs} application logs...")

        await session.commit()

    print(f"  Created {logs_created} application logs")
    return logs_created


async def seed_trash(num_deleted: int = 10) -> int:
    """Soft-delete some events to populate the Trash page.

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
            print("  Error: No events available to soft-delete.")
            return 0

        # Soft-delete a random selection
        to_delete = random.sample(events, min(num_deleted, len(events)))
        deleted_count = 0

        for event in to_delete:
            hours_ago = random.uniform(1, 168)  # noqa: S311  # 1 hour to 7 days
            deleted_timestamp = datetime.now(UTC) - timedelta(hours=hours_ago)
            event.deleted_at = deleted_timestamp.replace(microsecond=0)
            deleted_count += 1

        await session.commit()

    print(f"  Soft-deleted {deleted_count} events for trash")
    return deleted_count


async def seed_activity_baselines(min_samples_per_slot: int = 15) -> int:
    """Seed activity baseline data for all cameras.

    Creates 168 entries per camera (24 hours x 7 days), each with sufficient
    samples to mark the baseline as "learning complete".

    Args:
        min_samples_per_slot: Minimum samples per time slot

    Returns:
        Number of baseline entries created/updated
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    cameras = await get_cameras()
    if not cameras:
        print("  Error: No cameras found in database.")
        return 0

    baselines_upserted = 0

    def get_activity_weight(hour: int) -> float:
        if 0 <= hour < 6:
            return 0.2
        elif 6 <= hour < 8:
            return 0.6
        elif 8 <= hour < 18:
            return 1.0
        elif 18 <= hour < 21:
            return 0.8
        else:
            return 0.4

    async with get_session() as session:
        for camera in cameras:
            baseline_records = []
            for day_of_week in range(7):
                for hour in range(24):
                    base_activity = random.uniform(2.0, 8.0)  # noqa: S311
                    weight = get_activity_weight(hour)
                    if day_of_week in (5, 6):
                        weight *= 0.85

                    avg_count = base_activity * weight
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

            print(f"    Created/updated 168 activity baselines for camera: {camera.name}")

        await session.commit()

    print(f"  Created/updated {baselines_upserted} total activity baseline entries")
    return baselines_upserted


async def seed_class_baselines(min_samples_per_slot: int = 15) -> int:
    """Seed class frequency baseline data for all cameras.

    Args:
        min_samples_per_slot: Minimum samples per time slot

    Returns:
        Number of class baseline entries created/updated
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    cameras = await get_cameras()
    if not cameras:
        print("  Error: No cameras found in database.")
        return 0

    baselines_upserted = 0

    class_patterns = {
        "person": {"base_freq": 3.0, "peak_hours": range(7, 22)},
        "vehicle": {"base_freq": 2.0, "peak_hours": range(6, 20)},
        "animal": {"base_freq": 0.5, "peak_hours": list(range(5, 8)) + list(range(18, 22))},
        "package": {"base_freq": 0.3, "peak_hours": range(10, 17)},
    }

    async with get_session() as session:
        for camera in cameras:
            baseline_records = []
            for detection_class, pattern in class_patterns.items():
                for hour in range(24):
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
                f"    Created/updated {len(class_patterns) * 24} class baselines for: {camera.name}"
            )

        await session.commit()

    print(f"  Created/updated {baselines_upserted} total class baseline entries")
    return baselines_upserted


async def seed_pipeline_latency(num_samples: int = 100, time_span_hours: int = 24) -> int:
    """Seed pipeline latency data via the admin API.

    Args:
        num_samples: Number of samples per pipeline stage
        time_span_hours: Time span for the historical data

    Returns:
        Total number of samples seeded
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
                return samples * stages
            elif response.status_code == 403:
                print("  ⚠ Admin API not enabled (DEBUG=true and ADMIN_ENABLED=true required)")
                return 0
            else:
                print(f"  ⚠ Failed to seed pipeline latency: {response.status_code}")
                return 0
    except httpx.ConnectError:
        print("  ⚠ Could not connect to backend API")
        return 0
    except Exception as e:
        print(f"  ⚠ Error seeding pipeline latency: {e}")
        return 0


async def clear_all_data() -> None:
    """Clear all seeded data from the database."""
    async with get_session() as session:
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

    print("  Cleared all seeded data")


async def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Seed the system by exercising the full AI pipeline end-to-end",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default: Full pipeline + all supporting data
  uv run python scripts/seed-events.py

  # Process more images and wait longer
  uv run python scripts/seed-events.py --images 50 --timeout 600

  # Clear all data first, then run full pipeline
  uv run python scripts/seed-events.py --clear

  # Quick run without waiting for pipeline completion
  uv run python scripts/seed-events.py --no-wait

  # Skip supporting data (entities, alerts, logs) - only pipeline data
  uv run python scripts/seed-events.py --no-extras

Pipeline Flow:
  1. Touch camera images to trigger file watcher
  2. File Watcher → RT-DETRv2 (object detection)
  3. RT-DETRv2 → Batch Aggregator (group detections)
  4. Batch Aggregator → Nemotron LLM (risk analysis)
  5. Events created with AI-generated summaries and risk scores

This generates real data including:
  - Events with actual LLM reasoning
  - Detection bounding boxes from RT-DETRv2
  - Entities with real CLIP embeddings
  - Pipeline latency metrics for performance monitoring
  - Activity baselines for anomaly detection
""",
    )
    parser.add_argument(
        "--images",
        type=int,
        default=100,
        help="Number of images to process through the pipeline (default: 100)",
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
        "--no-extras",
        action="store_true",
        help="Skip seeding entities, alerts, audit logs, and app logs",
    )
    parser.add_argument(
        "--no-baselines",
        action="store_true",
        help="Skip seeding baseline data",
    )
    parser.add_argument(
        "--entities",
        type=int,
        default=30,
        help="Number of entities to create from real detections (default: 30)",
    )
    parser.add_argument(
        "--alerts",
        type=int,
        default=20,
        help="Number of alerts to create from real events (default: 20)",
    )
    parser.add_argument(
        "--audit-logs",
        type=int,
        default=50,
        help="Number of audit logs to create (default: 50)",
    )
    parser.add_argument(
        "--logs",
        type=int,
        default=100,
        help="Number of application logs to create (default: 100)",
    )
    parser.add_argument(
        "--trash",
        type=int,
        default=10,
        help="Number of events to soft-delete for trash (default: 10)",
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

    # Seed supporting data unless --no-extras
    if not args.no_extras:
        print("\n" + "=" * 50)
        print("SEEDING SUPPORTING DATA")
        print("=" * 50)

        print(f"\nSeeding {args.entities} entities from real detections...")
        total_created["entities"] = await seed_entities_from_detections(args.entities)

        print(f"\nSeeding {args.alerts} alerts from real events...")
        total_created["alerts"] = await seed_alerts_from_events(args.alerts)

        print(f"\nSeeding {args.audit_logs} audit logs...")
        total_created["audit_logs"] = await seed_audit_logs(args.audit_logs)

        print(f"\nSeeding {args.logs} application logs...")
        total_created["logs"] = await seed_application_logs(args.logs)

        if args.trash:
            print(f"\nSoft-deleting {args.trash} events for trash...")
            total_created["trash"] = await seed_trash(args.trash)

    # Seed baselines unless --no-baselines
    if not args.no_baselines:
        print("\n" + "=" * 50)
        print("SEEDING BASELINE DATA")
        print("=" * 50)

        print("\nSeeding activity baselines...")
        total_created["activity_baselines"] = await seed_activity_baselines()

        print("\nSeeding class baselines...")
        total_created["class_baselines"] = await seed_class_baselines()

        print("\nSeeding pipeline latency data...")
        total_created["pipeline_latency_samples"] = await seed_pipeline_latency()

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
    print(f"  Total entities: {counts['entities']}")
    print(f"  Total alerts: {counts['alerts']}")
    print("  Events by risk level:")
    print(f"    - Critical: {counts['events_critical']}")
    print(f"    - High: {counts['events_high']}")
    print(f"    - Medium: {counts['events_medium']}")
    print(f"    - Low: {counts['events_low']}")
    print(f"  Cameras with events: {counts['cameras_with_events']}")
    print(f"  Activity baselines: {counts['activity_baselines']}")
    print(f"  Class baselines: {counts['class_baselines']}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
