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
import re
import socket
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))


def _load_env_and_fix_database_url() -> None:
    """Load .env file and fix DATABASE_URL for local execution.

    When running outside containers, the DATABASE_URL uses container hostnames
    (e.g., 'postgres:5432') which don't resolve. This function:
    1. Loads .env from the project root
    2. Detects if running locally (hostname doesn't resolve)
    3. Converts container hostname to localhost for local execution
    4. Fixes port mapping (container port 5432/5433 -> host port 5432)
    """
    from dotenv import load_dotenv

    # Find project root (parent of scripts/)
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"

    if env_file.exists():
        load_dotenv(env_file)
        print(f"Loaded environment from {env_file}")

    # Check if DATABASE_URL needs transformation for local execution
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("Warning: DATABASE_URL not set in environment")
        return

    # Extract hostname and port from DATABASE_URL (format: protocol://user:pass@host:port/db)  # pragma: allowlist secret
    match = re.search(r"@([^:/@]+):(\d+)/", database_url)
    if not match:
        return

    hostname, port = match.groups()

    # Check if hostname resolves (i.e., we're inside container network)
    try:
        socket.gethostbyname(hostname)
        # Hostname resolves, we're in container network - no changes needed
        print(f"Database hostname '{hostname}' resolves - using container network")
    except socket.gaierror:
        # Hostname doesn't resolve - we're running locally
        # Replace container hostname with localhost
        new_url = database_url.replace(f"@{hostname}:", "@localhost:")

        # Fix port mapping: container internal ports often differ from host-exposed ports
        # Standard postgres is exposed on 5432, but .env might have different internal port
        # Try to detect the actual host port by checking what's listening
        host_port = _detect_postgres_port()
        if host_port and host_port != port:
            new_url = new_url.replace(f"@localhost:{port}/", f"@localhost:{host_port}/")
            print(f"Database hostname '{hostname}' doesn't resolve - using localhost:{host_port}")
        else:
            print(f"Database hostname '{hostname}' doesn't resolve - using localhost:{port}")

        os.environ["DATABASE_URL"] = new_url


def _detect_postgres_port() -> str | None:
    """Detect the actual postgres port on localhost.

    Checks common postgres ports to find which one is listening.

    Returns:
        The port number as string, or None if not detected
    """
    common_ports = ["5432", "5433", "5434"]

    for port in common_ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("localhost", int(port)))
            sock.close()
            if result == 0:
                return port
        except (OSError, ValueError):
            continue

    return None


# Load .env and fix DATABASE_URL before importing backend modules
_load_env_and_fix_database_url()

# Base path for camera images - check both container path and local path
_CONTAINER_CAMERA_PATH = "/cameras"
_LOCAL_CAMERA_PATH = os.environ.get("FOSCAM_BASE_PATH", "/export/foscam")

# Use container path if it exists (running in container), otherwise local path
if Path(_CONTAINER_CAMERA_PATH).exists():
    FOSCAM_BASE_PATH = _CONTAINER_CAMERA_PATH
else:
    FOSCAM_BASE_PATH = _LOCAL_CAMERA_PATH

from backend.core.database import get_session, init_db  # noqa: E402
from backend.models.alert import Alert, AlertRule, AlertSeverity, AlertStatus  # noqa: E402
from backend.models.audit import AuditAction, AuditLog  # noqa: E402
from backend.models.baseline import ActivityBaseline, ClassBaseline  # noqa: E402
from backend.models.camera import Camera  # noqa: E402
from backend.models.camera_calibration import CameraCalibration  # noqa: E402
from backend.models.detection import Detection  # noqa: E402
from backend.models.enrichment import (  # noqa: E402
    ActionResult,
    DemographicsResult,
    PoseResult,
    ReIDEmbedding,
    ThreatDetection,
)
from backend.models.entity import Entity  # noqa: E402
from backend.models.event import Event  # noqa: E402
from backend.models.event_audit import EventAudit  # noqa: E402
from backend.models.event_feedback import EventFeedback, FeedbackType  # noqa: E402
from backend.models.household import (  # noqa: E402
    HouseholdMember,
    MemberRole,
    PersonEmbedding,
    RegisteredVehicle,
    TrustLevel,
    VehicleType,
)
from backend.models.log import Log  # noqa: E402
from backend.models.notification_preferences import (  # noqa: E402
    CameraNotificationSetting,
    DayOfWeek,
    NotificationPreferences,
    NotificationSound,
    QuietHoursPeriod,
    RiskLevel,
)
from backend.models.scene_change import SceneChange, SceneChangeType  # noqa: E402
from backend.models.zone import Zone, ZoneShape, ZoneType  # noqa: E402
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

        # Count zones
        result = await session.execute(select(func.count()).select_from(Zone))
        counts["zones"] = result.scalar() or 0

        # Count household members
        result = await session.execute(select(func.count()).select_from(HouseholdMember))
        counts["household_members"] = result.scalar() or 0

        # Count registered vehicles
        result = await session.execute(select(func.count()).select_from(RegisteredVehicle))
        counts["registered_vehicles"] = result.scalar() or 0

        # Count event feedback
        result = await session.execute(select(func.count()).select_from(EventFeedback))
        counts["event_feedback"] = result.scalar() or 0

        # Count event audits
        result = await session.execute(select(func.count()).select_from(EventAudit))
        counts["event_audits"] = result.scalar() or 0

        # Count scene changes
        result = await session.execute(select(func.count()).select_from(SceneChange))
        counts["scene_changes"] = result.scalar() or 0

        # Count enrichment results
        result = await session.execute(select(func.count()).select_from(PoseResult))
        counts["pose_results"] = result.scalar() or 0

        result = await session.execute(select(func.count()).select_from(DemographicsResult))
        counts["demographics_results"] = result.scalar() or 0

        result = await session.execute(select(func.count()).select_from(ReIDEmbedding))
        counts["reid_embeddings"] = result.scalar() or 0

        result = await session.execute(select(func.count()).select_from(ActionResult))
        counts["action_results"] = result.scalar() or 0

        # Count camera calibrations
        result = await session.execute(select(func.count()).select_from(CameraCalibration))
        counts["camera_calibrations"] = result.scalar() or 0

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


async def seed_zones() -> int:
    """Seed realistic zones for each camera.

    Creates multiple zones per camera with realistic names and coordinates.

    Returns:
        Number of zones created
    """
    cameras = await get_cameras()
    if not cameras:
        print("  Error: No cameras found in database.")
        return 0

    # Zone templates for different camera types
    zone_templates = {
        "front": [
            {"name": "Front Door Entry", "zone_type": ZoneType.ENTRY_POINT, "priority": 2},
            {"name": "Driveway", "zone_type": ZoneType.DRIVEWAY, "priority": 1},
            {"name": "Front Sidewalk", "zone_type": ZoneType.SIDEWALK, "priority": 0},
            {"name": "Front Yard", "zone_type": ZoneType.YARD, "priority": 0},
        ],
        "dock": [
            {"name": "Dock Entry", "zone_type": ZoneType.ENTRY_POINT, "priority": 2},
            {"name": "Boat Parking", "zone_type": ZoneType.DRIVEWAY, "priority": 1},
            {"name": "Dock Walkway", "zone_type": ZoneType.SIDEWALK, "priority": 1},
        ],
        "beach": [
            {"name": "Beach Access Point", "zone_type": ZoneType.ENTRY_POINT, "priority": 2},
            {"name": "Yard Area", "zone_type": ZoneType.YARD, "priority": 0},
            {"name": "Pathway", "zone_type": ZoneType.SIDEWALK, "priority": 1},
        ],
        "kitchen": [
            {"name": "Kitchen Entry", "zone_type": ZoneType.ENTRY_POINT, "priority": 2},
            {"name": "Monitoring Area", "zone_type": ZoneType.OTHER, "priority": 1},
        ],
        "default": [
            {"name": "Primary Entry", "zone_type": ZoneType.ENTRY_POINT, "priority": 2},
            {"name": "Monitoring Zone", "zone_type": ZoneType.OTHER, "priority": 1},
        ],
    }

    # Colors for different zone types
    zone_colors = {
        ZoneType.ENTRY_POINT: "#EF4444",  # Red for entry points
        ZoneType.DRIVEWAY: "#3B82F6",  # Blue for driveways
        ZoneType.SIDEWALK: "#10B981",  # Green for sidewalks
        ZoneType.YARD: "#F59E0B",  # Amber for yards
        ZoneType.OTHER: "#8B5CF6",  # Purple for other
    }

    zones_created = 0

    async with get_session() as session:
        # Check for existing zones
        result = await session.execute(select(Zone))
        existing_zones = list(result.scalars().all())
        if existing_zones:
            print(f"  Found {len(existing_zones)} existing zones, skipping seed")
            return 0

        for camera in cameras:
            camera_name_lower = camera.name.lower() if camera.name else camera.id.lower()

            # Select zone template based on camera name
            if "front" in camera_name_lower:
                templates = zone_templates["front"]
            elif "dock" in camera_name_lower:
                templates = zone_templates["dock"]
            elif "beach" in camera_name_lower:
                templates = zone_templates["beach"]
            elif "kitchen" in camera_name_lower:
                templates = zone_templates["kitchen"]
            else:
                templates = zone_templates["default"]

            for i, template in enumerate(templates):
                # Generate normalized coordinates (0-1 range)
                # Create non-overlapping zones by stacking them vertically
                y_offset = i * 0.2
                coordinates = [
                    [0.1 + (i * 0.05), 0.1 + y_offset],
                    [0.4 + (i * 0.05), 0.1 + y_offset],
                    [0.4 + (i * 0.05), 0.3 + y_offset],
                    [0.1 + (i * 0.05), 0.3 + y_offset],
                ]

                zone = Zone(
                    id=f"{camera.id}_zone_{i}",
                    camera_id=camera.id,
                    name=template["name"],
                    zone_type=template["zone_type"],
                    coordinates=coordinates,
                    shape=ZoneShape.RECTANGLE,
                    color=zone_colors[template["zone_type"]],
                    enabled=True,
                    priority=template["priority"],
                )
                session.add(zone)
                zones_created += 1

            print(f"    Created {len(templates)} zones for camera: {camera.name or camera.id}")

        await session.commit()

    print(f"  Created {zones_created} total zones")
    return zones_created


async def seed_household_members() -> tuple[int, int]:
    """Seed household members and their person embeddings.

    Creates realistic household members with associated embeddings.

    Returns:
        Tuple of (members_created, embeddings_created)
    """
    import hashlib
    import struct

    # Household member templates
    members_data = [
        {
            "name": "Mike Svoboda",
            "role": MemberRole.RESIDENT,
            "trusted_level": TrustLevel.FULL,
            "typical_schedule": {
                "monday": {"start": "07:00", "end": "22:00"},
                "tuesday": {"start": "07:00", "end": "22:00"},
                "wednesday": {"start": "07:00", "end": "22:00"},
                "thursday": {"start": "07:00", "end": "22:00"},
                "friday": {"start": "07:00", "end": "23:00"},
                "saturday": {"start": "08:00", "end": "23:00"},
                "sunday": {"start": "08:00", "end": "22:00"},
            },
            "notes": "Primary resident and homeowner",
        },
        {
            "name": "Family Member",
            "role": MemberRole.FAMILY,
            "trusted_level": TrustLevel.FULL,
            "typical_schedule": None,
            "notes": "Regular family visitor",
        },
        {
            "name": "Lawn Care Service",
            "role": MemberRole.SERVICE_WORKER,
            "trusted_level": TrustLevel.PARTIAL,
            "typical_schedule": {
                "tuesday": {"start": "09:00", "end": "12:00"},
                "friday": {"start": "09:00", "end": "12:00"},
            },
            "notes": "Weekly lawn maintenance",
        },
        {
            "name": "Package Delivery",
            "role": MemberRole.FREQUENT_VISITOR,
            "trusted_level": TrustLevel.MONITOR,
            "typical_schedule": {
                "monday": {"start": "10:00", "end": "18:00"},
                "tuesday": {"start": "10:00", "end": "18:00"},
                "wednesday": {"start": "10:00", "end": "18:00"},
                "thursday": {"start": "10:00", "end": "18:00"},
                "friday": {"start": "10:00", "end": "18:00"},
            },
            "notes": "Regular delivery personnel",
        },
    ]

    members_created = 0
    embeddings_created = 0

    async with get_session() as session:
        # Check for existing members
        result = await session.execute(select(HouseholdMember))
        existing_members = list(result.scalars().all())
        if existing_members:
            print(f"  Found {len(existing_members)} existing household members, skipping seed")
            return 0, 0

        for member_data in members_data:
            member = HouseholdMember(
                name=member_data["name"],
                role=member_data["role"],
                trusted_level=member_data["trusted_level"],
                typical_schedule=member_data["typical_schedule"],
                notes=member_data["notes"],
            )
            session.add(member)
            await session.flush()  # Get the ID
            members_created += 1

            # Generate 2-3 mock embeddings per member (simulating different appearances)
            num_embeddings = random.randint(2, 3)  # noqa: S311
            for j in range(num_embeddings):
                # Generate a deterministic mock 512-dim embedding
                seed = f"{member_data['name']}_{j}".encode()
                hash_bytes = hashlib.sha512(seed).digest()
                # Create 512 floats from the hash (repeating as needed)
                embedding_values = []
                for k in range(512):
                    byte_offset = (k * 4) % 64
                    val = struct.unpack("f", hash_bytes[byte_offset : byte_offset + 4])[0]
                    # Normalize to reasonable range
                    embedding_values.append((val % 2) - 1)

                # Serialize as bytes (numpy-style)
                embedding_bytes = struct.pack(f"{len(embedding_values)}f", *embedding_values)

                person_embedding = PersonEmbedding(
                    member_id=member.id,
                    embedding=embedding_bytes,
                    confidence=0.85 + random.uniform(0, 0.15),  # noqa: S311
                )
                session.add(person_embedding)
                embeddings_created += 1

            print(f"    Created member: {member_data['name']} with {num_embeddings} embeddings")

        await session.commit()

    print(f"  Created {members_created} household members with {embeddings_created} embeddings")
    return members_created, embeddings_created


async def seed_registered_vehicles() -> int:
    """Seed registered vehicles.

    Creates realistic vehicle registrations.

    Returns:
        Number of vehicles created
    """
    # Get household members to link some vehicles
    async with get_session() as session:
        result = await session.execute(select(HouseholdMember))
        members = list(result.scalars().all())

        # Check for existing vehicles
        result = await session.execute(select(RegisteredVehicle))
        existing_vehicles = list(result.scalars().all())
        if existing_vehicles:
            print(f"  Found {len(existing_vehicles)} existing vehicles, skipping seed")
            return 0

    vehicles_data = [
        {
            "description": "Silver Tesla Model 3",
            "license_plate": "ABC 1234",
            "vehicle_type": VehicleType.CAR,
            "color": "Silver",
            "trusted": True,
        },
        {
            "description": "Black Ford F-150",
            "license_plate": "XYZ 5678",
            "vehicle_type": VehicleType.TRUCK,
            "color": "Black",
            "trusted": True,
        },
        {
            "description": "White Honda CR-V",
            "license_plate": "DEF 9012",
            "vehicle_type": VehicleType.SUV,
            "color": "White",
            "trusted": True,
        },
        {
            "description": "UPS Delivery Van",
            "license_plate": None,
            "vehicle_type": VehicleType.VAN,
            "color": "Brown",
            "trusted": False,  # Monitor but don't suppress alerts
        },
    ]

    vehicles_created = 0

    async with get_session() as session:
        for i, vehicle_data in enumerate(vehicles_data):
            # Link first few vehicles to household members if available
            owner_id = None
            if members and i < len(members):
                owner_id = members[i].id

            vehicle = RegisteredVehicle(
                description=vehicle_data["description"],
                license_plate=vehicle_data["license_plate"],
                vehicle_type=vehicle_data["vehicle_type"],
                color=vehicle_data["color"],
                owner_id=owner_id,
                trusted=vehicle_data["trusted"],
            )
            session.add(vehicle)
            vehicles_created += 1
            print(f"    Created vehicle: {vehicle_data['description']}")

        await session.commit()

    print(f"  Created {vehicles_created} registered vehicles")
    return vehicles_created


async def seed_notification_preferences() -> int:
    """Seed notification preferences (singleton).

    Returns:
        1 if created, 0 if already exists
    """
    async with get_session() as session:
        # Check for existing preferences
        result = await session.execute(select(NotificationPreferences))
        existing = result.scalar_one_or_none()
        if existing:
            print("  Found existing notification preferences, skipping seed")
            return 0

        prefs = NotificationPreferences(
            id=1,
            enabled=True,
            sound=NotificationSound.DEFAULT.value,
            risk_filters=[
                RiskLevel.CRITICAL.value,
                RiskLevel.HIGH.value,
                RiskLevel.MEDIUM.value,
            ],
        )
        session.add(prefs)
        await session.commit()

    print("  Created notification preferences (singleton)")
    return 1


async def seed_quiet_hours() -> int:
    """Seed quiet hours periods.

    Returns:
        Number of quiet hours periods created
    """
    from datetime import time as time_type

    async with get_session() as session:
        # Check for existing quiet hours
        result = await session.execute(select(QuietHoursPeriod))
        existing = list(result.scalars().all())
        if existing:
            print(f"  Found {len(existing)} existing quiet hours periods, skipping seed")
            return 0

    quiet_hours_data = [
        {
            "label": "Night Quiet Hours",
            "start_time": time_type(23, 0),  # 11 PM
            "end_time": time_type(6, 0),  # 6 AM (wraps midnight)
            "days": [day.value for day in DayOfWeek],  # All days
        },
        {
            "label": "Work Hours",
            "start_time": time_type(9, 0),  # 9 AM
            "end_time": time_type(17, 0),  # 5 PM
            "days": [
                DayOfWeek.MONDAY.value,
                DayOfWeek.TUESDAY.value,
                DayOfWeek.WEDNESDAY.value,
                DayOfWeek.THURSDAY.value,
                DayOfWeek.FRIDAY.value,
            ],
        },
    ]

    periods_created = 0

    async with get_session() as session:
        for period_data in quiet_hours_data:
            period = QuietHoursPeriod(
                label=period_data["label"],
                start_time=period_data["start_time"],
                end_time=period_data["end_time"],
                days=period_data["days"],
            )
            session.add(period)
            periods_created += 1
            print(f"    Created quiet hours: {period_data['label']}")

        await session.commit()

    print(f"  Created {periods_created} quiet hours periods")
    return periods_created


async def seed_camera_notification_settings() -> int:
    """Seed per-camera notification settings.

    Returns:
        Number of camera settings created
    """
    cameras = await get_cameras()
    if not cameras:
        print("  Error: No cameras found in database.")
        return 0

    async with get_session() as session:
        # Check for existing settings
        result = await session.execute(select(CameraNotificationSetting))
        existing = list(result.scalars().all())
        if existing:
            print(f"  Found {len(existing)} existing camera notification settings, skipping seed")
            return 0

    settings_created = 0

    async with get_session() as session:
        for camera in cameras:
            # Different thresholds based on camera location
            camera_name_lower = camera.name.lower() if camera.name else camera.id.lower()
            if "front" in camera_name_lower or "entry" in camera_name_lower:
                risk_threshold = 30  # Lower threshold for entry points
            elif "kitchen" in camera_name_lower:
                risk_threshold = 70  # Higher threshold for indoor
            else:
                risk_threshold = 50  # Default

            setting = CameraNotificationSetting(
                camera_id=camera.id,
                enabled=True,
                risk_threshold=risk_threshold,
            )
            session.add(setting)
            settings_created += 1

        await session.commit()

    print(f"  Created {settings_created} camera notification settings")
    return settings_created


async def seed_camera_calibrations() -> int:
    """Seed camera calibration records.

    Creates calibration records that simulate learned behavior from feedback.

    Returns:
        Number of calibration records created
    """
    cameras = await get_cameras()
    if not cameras:
        print("  Error: No cameras found in database.")
        return 0

    async with get_session() as session:
        # Check for existing calibrations
        result = await session.execute(select(CameraCalibration))
        existing = list(result.scalars().all())
        if existing:
            print(f"  Found {len(existing)} existing camera calibrations, skipping seed")
            return 0

    calibrations_created = 0

    async with get_session() as session:
        for camera in cameras:
            # Simulate varying levels of feedback per camera
            total_feedback = random.randint(20, 100)  # noqa: S311
            fp_count = int(total_feedback * random.uniform(0.1, 0.4))  # noqa: S311
            fp_rate = fp_count / total_feedback if total_feedback > 0 else 0.0

            # Calculate risk offset based on FP rate
            if fp_rate > 0.3:
                risk_offset = random.randint(-15, -5)  # noqa: S311  # High FP rate = reduce scores
            elif fp_rate < 0.15:
                risk_offset = random.randint(0, 10)  # noqa: S311  # Low FP rate = slight increase
            else:
                risk_offset = 0

            calibration = CameraCalibration(
                camera_id=camera.id,
                total_feedback_count=total_feedback,
                false_positive_count=fp_count,
                false_positive_rate=round(fp_rate, 4),
                risk_offset=risk_offset,
                model_weights={},
                suppress_patterns=[],
                avg_model_score=random.uniform(40.0, 70.0),  # noqa: S311
                avg_user_suggested_score=random.uniform(30.0, 60.0),  # noqa: S311
            )
            session.add(calibration)
            calibrations_created += 1
            print(
                f"    Created calibration for {camera.name or camera.id}: "
                f"offset={risk_offset}, fp_rate={fp_rate:.2%}"
            )

        await session.commit()

    print(f"  Created {calibrations_created} camera calibrations")
    return calibrations_created


async def seed_event_feedback(num_feedback: int = 30) -> int:
    """Seed event feedback records.

    Args:
        num_feedback: Number of feedback records to create

    Returns:
        Number of feedback records created
    """
    events = await get_events()
    if not events:
        print("  Error: No events found. Run pipeline first.")
        return 0

    # Get events without feedback
    async with get_session() as session:
        result = await session.execute(select(EventFeedback.event_id))
        existing_event_ids = set(result.scalars().all())

    available_events = [e for e in events if e.id not in existing_event_ids]
    if not available_events:
        print("  All events already have feedback, skipping seed")
        return 0

    # Feedback distribution (realistic)
    feedback_weights = [
        (FeedbackType.CORRECT, 0.45),
        (FeedbackType.FALSE_POSITIVE, 0.30),
        (FeedbackType.SEVERITY_WRONG, 0.15),
        (FeedbackType.MISSED_THREAT, 0.10),
    ]
    severity_levels = ["low", "medium", "high", "critical"]

    feedback_created = 0

    async with get_session() as session:
        sample_events = random.sample(
            available_events, min(num_feedback, len(available_events))
        )

        for event in sample_events:
            # Weighted random feedback type
            roll = random.random()  # noqa: S311
            cumulative = 0
            feedback_type = FeedbackType.CORRECT
            for ft, weight in feedback_weights:
                cumulative += weight
                if roll < cumulative:
                    feedback_type = ft
                    break

            # For severity_wrong, include expected severity
            expected_severity = None
            notes = None
            if feedback_type == FeedbackType.SEVERITY_WRONG:
                # Pick a different severity than the event's current level
                current_level = event.risk_level or "medium"
                other_levels = [s for s in severity_levels if s != current_level]
                expected_severity = random.choice(other_levels)  # noqa: S311
                notes = f"Expected {expected_severity} but got {current_level}"
            elif feedback_type == FeedbackType.FALSE_POSITIVE:
                notes = "No actual threat detected"
            elif feedback_type == FeedbackType.MISSED_THREAT:
                notes = "Suspicious activity was not flagged appropriately"

            feedback = EventFeedback(
                event_id=event.id,
                feedback_type=feedback_type.value,
                notes=notes,
                expected_severity=expected_severity,
            )
            session.add(feedback)
            feedback_created += 1

            if feedback_created % 10 == 0:
                print(f"    Created {feedback_created}/{num_feedback} feedback records...")

        await session.commit()

    print(f"  Created {feedback_created} event feedback records")
    return feedback_created


async def seed_event_audits(num_audits: int = 30) -> int:
    """Seed event audit records tracking AI pipeline performance.

    Args:
        num_audits: Number of audit records to create

    Returns:
        Number of audit records created
    """
    events = await get_events()
    if not events:
        print("  Error: No events found. Run pipeline first.")
        return 0

    # Get events without audits
    async with get_session() as session:
        result = await session.execute(select(EventAudit.event_id))
        existing_event_ids = set(result.scalars().all())

    available_events = [e for e in events if e.id not in existing_event_ids]
    if not available_events:
        print("  All events already have audits, skipping seed")
        return 0

    audits_created = 0

    async with get_session() as session:
        sample_events = random.sample(available_events, min(num_audits, len(available_events)))

        for event in sample_events:
            # Realistic model flags - most events have RT-DETR, others vary
            audit = EventAudit(
                event_id=event.id,
                has_rtdetr=True,  # Always have RT-DETR
                has_florence=random.random() < 0.3,  # noqa: S311
                has_clip=random.random() < 0.5,  # noqa: S311
                has_violence=random.random() < 0.2,  # noqa: S311
                has_clothing=random.random() < 0.4,  # noqa: S311
                has_vehicle=random.random() < 0.3,  # noqa: S311
                has_pet=random.random() < 0.1,  # noqa: S311
                has_weather=random.random() < 0.2,  # noqa: S311
                has_image_quality=random.random() < 0.4,  # noqa: S311
                has_zones=random.random() < 0.6,  # noqa: S311
                has_baseline=random.random() < 0.5,  # noqa: S311
                has_cross_camera=random.random() < 0.2,  # noqa: S311
                prompt_length=random.randint(2000, 8000),  # noqa: S311
                prompt_token_estimate=random.randint(500, 2000),  # noqa: S311
                enrichment_utilization=random.uniform(0.3, 0.9),  # noqa: S311
                # Quality scores (1-5 scale)
                context_usage_score=random.uniform(3.0, 5.0),  # noqa: S311
                reasoning_coherence_score=random.uniform(3.0, 5.0),  # noqa: S311
                risk_justification_score=random.uniform(2.5, 5.0),  # noqa: S311
                consistency_score=random.uniform(3.0, 5.0),  # noqa: S311
                overall_quality_score=random.uniform(3.0, 5.0),  # noqa: S311
            )
            session.add(audit)
            audits_created += 1

            if audits_created % 10 == 0:
                print(f"    Created {audits_created}/{num_audits} audit records...")

        await session.commit()

    print(f"  Created {audits_created} event audit records")
    return audits_created


async def seed_scene_changes(num_changes: int = 10) -> int:
    """Seed scene change records for tampering detection.

    Args:
        num_changes: Number of scene change records to create

    Returns:
        Number of scene change records created
    """
    cameras = await get_cameras()
    if not cameras:
        print("  Error: No cameras found in database.")
        return 0

    async with get_session() as session:
        # Check for existing scene changes
        result = await session.execute(select(SceneChange))
        existing = list(result.scalars().all())
        if existing:
            print(f"  Found {len(existing)} existing scene changes, skipping seed")
            return 0

    # Scene change types with weights
    change_type_weights = [
        (SceneChangeType.ANGLE_CHANGED, 0.4),
        (SceneChangeType.VIEW_BLOCKED, 0.3),
        (SceneChangeType.VIEW_TAMPERED, 0.1),
        (SceneChangeType.UNKNOWN, 0.2),
    ]

    changes_created = 0

    async with get_session() as session:
        for i in range(num_changes):
            camera = random.choice(cameras)  # noqa: S311

            # Weighted random change type
            roll = random.random()  # noqa: S311
            cumulative = 0
            change_type = SceneChangeType.UNKNOWN
            for ct, weight in change_type_weights:
                cumulative += weight
                if roll < cumulative:
                    change_type = ct
                    break

            # SSIM score - lower = more different
            # Most changes have moderate similarity (0.3-0.7)
            similarity = random.uniform(0.2, 0.8)  # noqa: S311

            # Spread detected_at over past 7 days
            days_ago = random.uniform(0, 7)  # noqa: S311
            detected_at = datetime.now(UTC) - timedelta(days=days_ago)

            # Some are acknowledged
            acknowledged = random.random() < 0.4  # noqa: S311
            acknowledged_at = (
                detected_at + timedelta(hours=random.uniform(0.5, 24))  # noqa: S311
                if acknowledged
                else None
            )

            scene_change = SceneChange(
                camera_id=camera.id,
                detected_at=detected_at,
                change_type=change_type,
                similarity_score=round(similarity, 4),
                acknowledged=acknowledged,
                acknowledged_at=acknowledged_at,
            )
            session.add(scene_change)
            changes_created += 1

        await session.commit()

    print(f"  Created {changes_created} scene change records")
    return changes_created


async def seed_enrichment_results() -> dict[str, int]:
    """Seed enrichment results for detections.

    Creates pose, demographics, reid, and action results for person detections.

    Returns:
        Dictionary with counts of each enrichment type created
    """
    import hashlib

    detections = await get_detections()
    if not detections:
        print("  Error: No detections found. Run pipeline first.")
        return {}

    # Filter to person detections
    person_detections = [d for d in detections if d.object_type == "person"]
    if not person_detections:
        print("  Warning: No person detections found for enrichment")
        return {}

    # Sample a subset for enrichment
    sample_size = min(50, len(person_detections))
    sampled_detections = random.sample(person_detections, sample_size)

    results = {"pose": 0, "demographics": 0, "reid": 0, "action": 0, "threat": 0}

    # Pose classes
    pose_classes = ["standing", "crouching", "bending_over", "arms_raised", "sitting", "unknown"]
    suspicious_poses = {"crouching", "bending_over"}

    # Age ranges and genders
    age_ranges = ["0-10", "11-20", "21-30", "31-40", "41-50", "51-60", "61-70", "71-80", "81+"]
    genders = ["male", "female"]

    # Actions
    actions = [
        "walking normally",
        "running",
        "standing still",
        "carrying object",
        "entering area",
        "leaving area",
    ]
    suspicious_actions = ["climbing", "loitering", "looking around suspiciously"]

    async with get_session() as session:
        # Check for existing enrichment results
        result = await session.execute(select(PoseResult.detection_id))
        existing_pose_ids = set(result.scalars().all())

        result = await session.execute(select(DemographicsResult.detection_id))
        existing_demo_ids = set(result.scalars().all())

        result = await session.execute(select(ReIDEmbedding.detection_id))
        existing_reid_ids = set(result.scalars().all())

        result = await session.execute(select(ActionResult.detection_id))
        existing_action_ids = set(result.scalars().all())

        for detection in sampled_detections:
            # Skip if already has enrichment
            if detection.id in existing_pose_ids:
                continue

            # Pose result (80% of detections)
            if random.random() < 0.8 and detection.id not in existing_pose_ids:  # noqa: S311
                pose_class = random.choice(pose_classes)  # noqa: S311
                # Generate mock keypoints (17 COCO keypoints)
                keypoints = [
                    [random.uniform(0.1, 0.9), random.uniform(0.1, 0.9), random.uniform(0.5, 1.0)]  # noqa: S311
                    for _ in range(17)
                ]
                pose = PoseResult(
                    detection_id=detection.id,
                    keypoints=keypoints,
                    pose_class=pose_class,
                    confidence=random.uniform(0.7, 0.99),  # noqa: S311
                    is_suspicious=pose_class in suspicious_poses,
                )
                session.add(pose)
                results["pose"] += 1

            # Demographics result (60% of detections)
            if random.random() < 0.6 and detection.id not in existing_demo_ids:  # noqa: S311
                demo = DemographicsResult(
                    detection_id=detection.id,
                    age_range=random.choice(age_ranges),  # noqa: S311
                    age_confidence=random.uniform(0.6, 0.95),  # noqa: S311
                    gender=random.choice(genders),  # noqa: S311
                    gender_confidence=random.uniform(0.7, 0.99),  # noqa: S311
                )
                session.add(demo)
                results["demographics"] += 1

            # ReID embedding (70% of detections)
            if random.random() < 0.7 and detection.id not in existing_reid_ids:  # noqa: S311
                # Generate mock 512-dim embedding
                embedding = [random.uniform(-1, 1) for _ in range(512)]  # noqa: S311
                embedding_str = str(embedding).encode()
                embedding_hash = hashlib.sha256(embedding_str).hexdigest()[:16]

                reid = ReIDEmbedding(
                    detection_id=detection.id,
                    embedding=embedding,
                    embedding_hash=embedding_hash,
                )
                session.add(reid)
                results["reid"] += 1

            # Action result (50% of detections)
            if random.random() < 0.5 and detection.id not in existing_action_ids:  # noqa: S311
                # Mostly normal actions, occasionally suspicious
                if random.random() < 0.1:  # noqa: S311
                    action = random.choice(suspicious_actions)  # noqa: S311
                    is_suspicious = True
                else:
                    action = random.choice(actions)  # noqa: S311
                    is_suspicious = False

                # Generate all_scores dict
                all_scores = {a: random.uniform(0, 0.3) for a in actions + suspicious_actions}  # noqa: S311
                all_scores[action] = random.uniform(0.7, 0.99)  # noqa: S311

                action_result = ActionResult(
                    detection_id=detection.id,
                    action=action,
                    confidence=all_scores[action],
                    is_suspicious=is_suspicious,
                    all_scores=all_scores,
                )
                session.add(action_result)
                results["action"] += 1

        await session.commit()

    print(f"  Created enrichment results: {results}")
    return results


async def clear_all_data() -> None:
    """Clear all seeded data from the database."""
    async with get_session() as session:
        # Clear enrichment results first (FK dependencies)
        print("  Clearing enrichment results...")
        await session.execute(delete(PoseResult))
        await session.execute(delete(ThreatDetection))
        await session.execute(delete(DemographicsResult))
        await session.execute(delete(ReIDEmbedding))
        await session.execute(delete(ActionResult))

        print("  Clearing alerts...")
        await session.execute(delete(Alert))

        print("  Clearing alert rules...")
        await session.execute(delete(AlertRule))

        print("  Clearing entities...")
        await session.execute(delete(Entity))

        print("  Clearing event feedback...")
        await session.execute(delete(EventFeedback))

        print("  Clearing event audits...")
        await session.execute(delete(EventAudit))

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

        print("  Clearing zones...")
        await session.execute(delete(Zone))

        print("  Clearing scene changes...")
        await session.execute(delete(SceneChange))

        print("  Clearing camera calibrations...")
        await session.execute(delete(CameraCalibration))

        print("  Clearing camera notification settings...")
        await session.execute(delete(CameraNotificationSetting))

        print("  Clearing quiet hours periods...")
        await session.execute(delete(QuietHoursPeriod))

        print("  Clearing notification preferences...")
        await session.execute(delete(NotificationPreferences))

        # Clear household data (person embeddings deleted by cascade)
        print("  Clearing registered vehicles...")
        await session.execute(delete(RegisteredVehicle))

        print("  Clearing household members...")
        await session.execute(delete(HouseholdMember))

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

This generates comprehensive data including:
  - Events with actual LLM reasoning
  - Detection bounding boxes from RT-DETRv2
  - Entities with real CLIP embeddings
  - Pipeline latency metrics for performance monitoring
  - Activity baselines for anomaly detection
  - Zones for spatial context per camera
  - Household members with person embeddings
  - Registered vehicles with trust levels
  - Notification preferences and quiet hours
  - Camera calibrations with feedback data
  - Event feedback and AI audit records
  - Enrichment results (pose, demographics, reid, action)
  - Scene change records for tampering detection
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
    parser.add_argument(
        "--no-household",
        action="store_true",
        help="Skip seeding household members, vehicles, and trust data",
    )
    parser.add_argument(
        "--no-spatial",
        action="store_true",
        help="Skip seeding zones, scene changes, and spatial context",
    )
    parser.add_argument(
        "--no-enrichment",
        action="store_true",
        help="Skip seeding enrichment results (pose, demographics, etc.)",
    )
    parser.add_argument(
        "--event-feedback",
        type=int,
        default=30,
        help="Number of event feedback records to create (default: 30)",
    )
    parser.add_argument(
        "--event-audits",
        type=int,
        default=30,
        help="Number of event audit records to create (default: 30)",
    )
    parser.add_argument(
        "--scene-changes",
        type=int,
        default=10,
        help="Number of scene change records to create (default: 10)",
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

    # Seed spatial context unless --no-spatial
    if not args.no_spatial:
        print("\n" + "=" * 50)
        print("SEEDING SPATIAL CONTEXT DATA")
        print("=" * 50)

        print("\nSeeding zones for each camera...")
        total_created["zones"] = await seed_zones()

        print(f"\nSeeding {args.scene_changes} scene change records...")
        total_created["scene_changes"] = await seed_scene_changes(args.scene_changes)

    # Seed household data unless --no-household
    if not args.no_household:
        print("\n" + "=" * 50)
        print("SEEDING HOUSEHOLD & TRUST DATA")
        print("=" * 50)

        print("\nSeeding household members...")
        members, embeddings = await seed_household_members()
        total_created["household_members"] = members
        total_created["person_embeddings"] = embeddings

        print("\nSeeding registered vehicles...")
        total_created["registered_vehicles"] = await seed_registered_vehicles()

        print("\nSeeding notification preferences...")
        total_created["notification_preferences"] = await seed_notification_preferences()

        print("\nSeeding quiet hours periods...")
        total_created["quiet_hours_periods"] = await seed_quiet_hours()

        print("\nSeeding camera notification settings...")
        total_created["camera_notification_settings"] = await seed_camera_notification_settings()

        print("\nSeeding camera calibrations...")
        total_created["camera_calibrations"] = await seed_camera_calibrations()

    # Seed event feedback and audits (requires events)
    if not args.no_extras:
        print("\n" + "=" * 50)
        print("SEEDING EVENT FEEDBACK & AUDIT DATA")
        print("=" * 50)

        print(f"\nSeeding {args.event_feedback} event feedback records...")
        total_created["event_feedback"] = await seed_event_feedback(args.event_feedback)

        print(f"\nSeeding {args.event_audits} event audit records...")
        total_created["event_audits"] = await seed_event_audits(args.event_audits)

    # Seed enrichment results unless --no-enrichment
    if not args.no_enrichment:
        print("\n" + "=" * 50)
        print("SEEDING ENRICHMENT RESULTS")
        print("=" * 50)

        print("\nSeeding enrichment results (pose, demographics, reid, action)...")
        enrichment_results = await seed_enrichment_results()
        total_created["enrichment_pose"] = enrichment_results.get("pose", 0)
        total_created["enrichment_demographics"] = enrichment_results.get("demographics", 0)
        total_created["enrichment_reid"] = enrichment_results.get("reid", 0)
        total_created["enrichment_action"] = enrichment_results.get("action", 0)

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

    print("\n  Core Pipeline Data:")
    print(f"    Events: {counts['events']}")
    print(f"    Detections: {counts['detections']}")
    print(f"    Entities: {counts['entities']}")
    print(f"    Alerts: {counts['alerts']}")

    print("\n  Events by risk level:")
    print(f"    Critical: {counts['events_critical']}")
    print(f"    High: {counts['events_high']}")
    print(f"    Medium: {counts['events_medium']}")
    print(f"    Low: {counts['events_low']}")
    print(f"    Cameras with events: {counts['cameras_with_events']}")

    print("\n  Baseline Data:")
    print(f"    Activity baselines: {counts['activity_baselines']}")
    print(f"    Class baselines: {counts['class_baselines']}")

    print("\n  Spatial Context:")
    print(f"    Zones: {counts['zones']}")
    print(f"    Scene changes: {counts['scene_changes']}")

    print("\n  Household & Trust:")
    print(f"    Household members: {counts['household_members']}")
    print(f"    Registered vehicles: {counts['registered_vehicles']}")
    print(f"    Camera calibrations: {counts['camera_calibrations']}")

    print("\n  Feedback & Audit:")
    print(f"    Event feedback: {counts['event_feedback']}")
    print(f"    Event audits: {counts['event_audits']}")

    print("\n  Enrichment Results:")
    print(f"    Pose results: {counts['pose_results']}")
    print(f"    Demographics results: {counts['demographics_results']}")
    print(f"    ReID embeddings: {counts['reid_embeddings']}")
    print(f"    Action results: {counts['action_results']}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
