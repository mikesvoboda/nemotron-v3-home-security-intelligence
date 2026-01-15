#!/usr/bin/env python3
"""Seed the database with mock data for comprehensive UI testing.

This script seeds all data types needed for exhaustive UI testing:
- Events and Detections (core data)
- Entities (for /entities page)
- Alerts and AlertRules (for /alerts page)
- Audit Logs (for /audit page)
- Application Logs (for /logs page)
- Soft-deleted events (for /trash page)

Usage:
    # Seed everything with defaults
    uv run python scripts/seed-mock-events.py --all

    # Seed only events (legacy behavior)
    uv run python scripts/seed-mock-events.py --count 100

    # Seed specific data types
    uv run python scripts/seed-mock-events.py --entities 50
    uv run python scripts/seed-mock-events.py --alerts 30
    uv run python scripts/seed-mock-events.py --audit-logs 100
    uv run python scripts/seed-mock-events.py --logs 200
    uv run python scripts/seed-mock-events.py --trash 10

    # Clear all and reseed everything
    uv run python scripts/seed-mock-events.py --clear --all
"""

import asyncio
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.database import get_session, init_db
from backend.models.alert import Alert, AlertRule, AlertSeverity, AlertStatus
from backend.models.audit import AuditAction, AuditLog
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.entity import Entity
from backend.models.enums import EntityType
from backend.models.event import Event
from backend.models.log import Log
from sqlalchemy import delete, select

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
            camera_images = discover_camera_images(camera.folder_path)

            for j in range(num_detections):
                object_type = random.choice(OBJECT_TYPES)  # noqa: S311
                confidence = random.uniform(0.65, 0.98)  # noqa: S311

                # Generate mock bounding box
                bbox_x = random.randint(50, 400)  # noqa: S311
                bbox_y = random.randint(50, 300)  # noqa: S311
                bbox_width = random.randint(80, 200)  # noqa: S311
                bbox_height = random.randint(100, 250)  # noqa: S311

                # Use actual image path if available, otherwise use placeholder
                if camera_images:
                    file_path = random.choice(camera_images)  # noqa: S311
                else:
                    # Fallback to placeholder path (use container path format)
                    # Convert /export/foscam/... to /cameras/...
                    container_folder = camera.folder_path.replace("/export/foscam", "/cameras")
                    file_path = f"{container_folder}/placeholder_{j + 1}.jpg"

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
    camera_ids = [c.id for c in cameras] if cameras else ["unknown"]

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
            entity_metadata["cameras_seen"] = random.sample(
                camera_ids,
                min(len(camera_ids), random.randint(1, 3)),  # noqa: S311
            )

            # Optionally link to a detection
            primary_detection_id = None
            if detections and random.random() < 0.7:  # noqa: S311
                matching_detections = [d for d in detections if d.object_type == entity_type.value]
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
            # Set deleted_at to a random time in the past week
            days_ago = random.uniform(0, 7)  # noqa: S311
            event.deleted_at = datetime.now(UTC) - timedelta(days=days_ago)
            deleted_count += 1

        await session.commit()

    print(f"  Soft-deleted {deleted_count} events for trash")
    return deleted_count


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

        await session.commit()

    print("Cleared all seeded data")


async def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Seed mock data for comprehensive UI testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Seed everything with good defaults
  uv run python scripts/seed-mock-events.py --all

  # Seed only events (100 events)
  uv run python scripts/seed-mock-events.py --count 100

  # Clear and reseed everything
  uv run python scripts/seed-mock-events.py --clear --all

  # Seed specific data types
  uv run python scripts/seed-mock-events.py --entities 50 --alerts 30
""",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Number of mock events to create",
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
        "--all",
        action="store_true",
        help="Seed all data types with good defaults for UI testing",
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

    # Determine what to seed
    if args.all:
        # Good defaults for comprehensive UI testing
        events_count = args.count or 100
        entities_count = args.entities or 50
        alerts_count = args.alerts or 30
        audit_logs_count = args.audit_logs or 75
        logs_count = args.logs or 150
        trash_count = args.trash or 15
    else:
        events_count = args.count
        entities_count = args.entities
        alerts_count = args.alerts
        audit_logs_count = args.audit_logs
        logs_count = args.logs
        trash_count = args.trash

    # Check if anything was specified
    if not any(
        [events_count, entities_count, alerts_count, audit_logs_count, logs_count, trash_count]
    ):
        print("\nNo seeding options specified. Use --all or specify individual counts.")
        parser.print_help()
        return 1

    # Seed data in order (events first, as other data may reference them)
    total_created = {}

    if events_count:
        print(f"\nSeeding {events_count} events...")
        events, detections = await seed_mock_data(events_count)
        total_created["events"] = events
        total_created["detections"] = detections

    if entities_count:
        print(f"\nSeeding {entities_count} entities...")
        total_created["entities"] = await seed_entities(entities_count)

    if alerts_count:
        print(f"\nSeeding {alerts_count} alerts...")
        total_created["alerts"] = await seed_alerts(alerts_count)

    if audit_logs_count:
        print(f"\nSeeding {audit_logs_count} audit logs...")
        total_created["audit_logs"] = await seed_audit_logs(audit_logs_count)

    if logs_count:
        print(f"\nSeeding {logs_count} application logs...")
        total_created["logs"] = await seed_application_logs(logs_count)

    if trash_count:
        print(f"\nSoft-deleting {trash_count} events for trash...")
        total_created["trash"] = await seed_trash(trash_count)

    # Print summary
    print("\n" + "=" * 50)
    print("SEEDING COMPLETE")
    print("=" * 50)
    for data_type, count in total_created.items():
        print(f"  {data_type}: {count}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
