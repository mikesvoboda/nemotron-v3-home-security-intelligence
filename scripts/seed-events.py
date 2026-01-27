#!/usr/bin/env python3
"""Seed the system by exercising the full AI pipeline end-to-end.

This script triggers real pipeline processing by touching images in camera
watch folders, causing the file watcher to process them through:
  1. File Watcher → detects touched images
  2. YOLO26 → object detection
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
import json
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

    # Extract hostname from DATABASE_URL (format: protocol://user:pass@host:port/db)  # pragma: allowlist secret
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
        os.environ["DATABASE_URL"] = new_url
        print(f"Database hostname '{hostname}' doesn't resolve - using localhost:{port}")


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

# Phase 2: Zones & Spatial imports
from backend.models.area import Area, camera_areas  # noqa: E402
from backend.models.audit import AuditAction, AuditLog  # noqa: E402
from backend.models.baseline import ActivityBaseline, ClassBaseline  # noqa: E402
from backend.models.camera import Camera  # noqa: E402
from backend.models.camera_calibration import CameraCalibration  # noqa: E402
from backend.models.camera_zone import CameraZone, CameraZoneShape, CameraZoneType  # noqa: E402
from backend.models.detection import Detection  # noqa: E402

# Phase 3: AI Enrichment imports
from backend.models.enrichment import (  # noqa: E402
    ActionResult,
    DemographicsResult,
    PoseResult,
    ReIDEmbedding,
    ThreatDetection,
)
from backend.models.entity import Entity  # noqa: E402
from backend.models.event import Event  # noqa: E402

# Phase 5 imports
from backend.models.event_feedback import EventFeedback, FeedbackType  # noqa: E402
from backend.models.experiment_result import ExperimentResult  # noqa: E402

# Phase 4: Jobs & Exports imports
from backend.models.export_job import ExportJob, ExportJobStatus, ExportType  # noqa: E402
from backend.models.household import (  # noqa: E402
    HouseholdMember,
    MemberRole,
    PersonEmbedding,
    RegisteredVehicle,
    TrustLevel,
    VehicleType,
)

# Phase 1: Foundation layer imports
from backend.models.household_org import Household  # noqa: E402
from backend.models.job import Job, JobStatus  # noqa: E402
from backend.models.job_attempt import JobAttempt, JobAttemptStatus  # noqa: E402
from backend.models.job_log import JobLog, LogLevel  # noqa: E402
from backend.models.job_transition import JobTransition, JobTransitionTrigger  # noqa: E402
from backend.models.log import Log  # noqa: E402
from backend.models.notification_preferences import (  # noqa: E402
    CameraNotificationSetting,
    DayOfWeek,
    NotificationPreferences,
    NotificationSound,
    QuietHoursPeriod,
    RiskLevel,
)
from backend.models.prometheus_alert import PrometheusAlert, PrometheusAlertStatus  # noqa: E402
from backend.models.prompt_config import PromptConfig  # noqa: E402
from backend.models.prompt_version import AIModel, PromptVersion  # noqa: E402
from backend.models.property import Property  # noqa: E402
from backend.models.scene_change import SceneChange, SceneChangeType  # noqa: E402
from backend.models.user_calibration import UserCalibration  # noqa: E402

# Phase 6 imports
from backend.models.zone_anomaly import AnomalySeverity, AnomalyType, ZoneAnomaly  # noqa: E402
from backend.models.zone_baseline import ZoneActivityBaseline  # noqa: E402
from backend.models.zone_household_config import ZoneHouseholdConfig  # noqa: E402
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
    File Watcher → YOLO26 → Batch Aggregator → Nemotron LLM

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
    print("(Images will be processed: File Watcher → YOLO26 → Batching → Nemotron)\n")

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


# =============================================================================
# PHASE 1: FOUNDATION LAYER (Properties, Households, Notifications)
# =============================================================================


async def seed_households(num_households: int = 3) -> list[int]:
    """Create households (top-level org units, e.g., 'Smith Family').

    Households are the top-level organizational units that own properties,
    have members, and register vehicles.

    Args:
        num_households: Number of households to create

    Returns:
        List of created household IDs
    """
    household_templates = [
        {"name": "Smith Family"},
        {"name": "Johnson Family"},
        {"name": "Williams Family"},
        {"name": "Garcia Family"},
        {"name": "Brown Family"},
    ]

    household_ids: list[int] = []

    async with get_session() as session:
        for i in range(min(num_households, len(household_templates))):
            template = household_templates[i]

            household = Household(name=template["name"])
            session.add(household)
            await session.flush()
            household_ids.append(household.id)
            print(f"  Created household: {household.name} ({household.id})")

        await session.commit()

    return household_ids


async def seed_properties(household_ids: list[int], num_properties: int = 4) -> list[int]:
    """Create properties (physical locations) for households.

    Each household can have multiple properties (main house, beach house, etc.).

    Args:
        household_ids: List of household IDs to assign properties to
        num_properties: Number of properties to create

    Returns:
        List of created property IDs
    """
    if not household_ids:
        print("  Warning: No households found. Create households first.")
        return []

    property_templates = [
        {
            "name": "Main Residence",
            "address": "123 Oak Street, Suburbia, CA 94102",
            "timezone": "America/Los_Angeles",
            "household_idx": 0,
        },
        {
            "name": "Lake House",
            "address": "456 Lakeview Drive, Mountain View, CA 94043",
            "timezone": "America/Los_Angeles",
            "household_idx": 0,
        },
        {
            "name": "Beach Cottage",
            "address": "789 Ocean Boulevard, Santa Cruz, CA 95060",
            "timezone": "America/Los_Angeles",
            "household_idx": 1,
        },
        {
            "name": "City Apartment",
            "address": "101 Market Street, San Francisco, CA 94105",
            "timezone": "America/Los_Angeles",
            "household_idx": 1,
        },
    ]

    property_ids: list[int] = []

    async with get_session() as session:
        for i in range(min(num_properties, len(property_templates))):
            template = property_templates[i]
            # Map to actual household, cycling if needed
            household_idx = template["household_idx"] % len(household_ids)
            household_id = household_ids[household_idx]

            prop = Property(
                household_id=household_id,
                name=template["name"],
                address=template["address"],
                timezone=template["timezone"],
            )
            session.add(prop)
            await session.flush()
            property_ids.append(prop.id)
            print(f"  Created property: {prop.name} ({prop.id}) for household {household_id}")

        await session.commit()

    return property_ids


async def seed_household_members(household_ids: list[int], num_members: int = 8) -> list[int]:
    """Create family members with names, roles, and trust levels.

    Args:
        household_ids: List of household IDs to assign members to
        num_members: Number of members to create

    Returns:
        List of created member IDs (integers)
    """
    if not household_ids:
        print("  Warning: No households found. Create households first.")
        return []

    member_templates = [
        # Smith Family members
        {
            "name": "John Smith",
            "role": MemberRole.RESIDENT,
            "trust": TrustLevel.FULL,
            "household_idx": 0,
        },
        {
            "name": "Jane Smith",
            "role": MemberRole.RESIDENT,
            "trust": TrustLevel.FULL,
            "household_idx": 0,
        },
        {
            "name": "Tommy Smith",
            "role": MemberRole.FAMILY,
            "trust": TrustLevel.FULL,
            "household_idx": 0,
        },
        # Johnson Family members
        {
            "name": "Michael Johnson",
            "role": MemberRole.RESIDENT,
            "trust": TrustLevel.FULL,
            "household_idx": 1,
        },
        {
            "name": "Sarah Johnson",
            "role": MemberRole.RESIDENT,
            "trust": TrustLevel.FULL,
            "household_idx": 1,
        },
        {
            "name": "Emily Johnson",
            "role": MemberRole.FAMILY,
            "trust": TrustLevel.FULL,
            "household_idx": 1,
        },
        # Williams Family members
        {
            "name": "David Williams",
            "role": MemberRole.RESIDENT,
            "trust": TrustLevel.FULL,
            "household_idx": 2,
        },
        {
            "name": "Lisa Williams",
            "role": MemberRole.RESIDENT,
            "trust": TrustLevel.FULL,
            "household_idx": 2,
        },
        # Service workers
        {
            "name": "Rosa Martinez",
            "role": MemberRole.SERVICE_WORKER,
            "trust": TrustLevel.PARTIAL,
            "household_idx": 0,
            "notes": "Housekeeper, Mon-Fri",
        },
        {
            "name": "Carlos Garcia",
            "role": MemberRole.SERVICE_WORKER,
            "trust": TrustLevel.PARTIAL,
            "household_idx": 1,
            "notes": "Gardener, Sat",
        },
    ]

    member_ids = []

    async with get_session() as session:
        for i in range(min(num_members, len(member_templates))):
            template = member_templates[i]
            # Map to actual household, cycling if needed
            household_idx = template["household_idx"] % len(household_ids)
            household_id = household_ids[household_idx]

            member = HouseholdMember(
                household_id=household_id,
                name=template["name"],
                role=template["role"],
                trusted_level=template["trust"],
                notes=template.get("notes"),
            )
            session.add(member)
            await session.flush()
            member_ids.append(member.id)
            print(
                f"  Created member: {member.name} ({member.role.value}) - {member.trusted_level.value}"
            )

        await session.commit()

    return member_ids


async def seed_registered_vehicles(household_ids: list[int], num_vehicles: int = 5) -> list[int]:
    """Create known vehicles (plate, make, model, color).

    Links to households for 'family car arriving' scenarios.

    Args:
        household_ids: List of household IDs to assign vehicles to
        num_vehicles: Number of vehicles to create

    Returns:
        List of created vehicle IDs (integers)
    """
    if not household_ids:
        print("  Warning: No households found. Create households first.")
        return []

    vehicle_templates = [
        {
            "description": "Silver Toyota Camry 2022",
            "license_plate": "ABC-1234",
            "color": "Silver",
            "vehicle_type": VehicleType.CAR,
            "household_idx": 0,
        },
        {
            "description": "Blue Honda CR-V 2021",
            "license_plate": "XYZ-5678",
            "color": "Blue",
            "vehicle_type": VehicleType.SUV,
            "household_idx": 0,
        },
        {
            "description": "Black Ford F-150 2023",
            "license_plate": "DEF-9012",
            "color": "Black",
            "vehicle_type": VehicleType.TRUCK,
            "household_idx": 1,
        },
        {
            "description": "White Tesla Model 3 2024",
            "license_plate": "GHI-3456",
            "color": "White",
            "vehicle_type": VehicleType.CAR,
            "household_idx": 1,
        },
        {
            "description": "Red Harley-Davidson Street Glide",
            "license_plate": "JKL-7890",
            "color": "Red",
            "vehicle_type": VehicleType.MOTORCYCLE,
            "household_idx": 2,
        },
    ]

    vehicle_ids: list[int] = []

    async with get_session() as session:
        for i in range(min(num_vehicles, len(vehicle_templates))):
            template = vehicle_templates[i]
            # Map to actual household, cycling if needed
            household_idx = template["household_idx"] % len(household_ids)
            household_id = household_ids[household_idx]

            vehicle = RegisteredVehicle(
                household_id=household_id,
                description=template["description"],
                license_plate=template["license_plate"],
                color=template["color"],
                vehicle_type=template["vehicle_type"],
            )
            session.add(vehicle)
            await session.flush()
            vehicle_ids.append(vehicle.id)
            print(f"  Created vehicle: {vehicle.license_plate} - {vehicle.description}")

        await session.commit()

    return vehicle_ids


async def seed_notification_preferences() -> int:
    """Create global notification preferences (singleton table).

    Creates the single global NotificationPreferences row that controls
    notification behavior across the system.

    Returns:
        1 if created, 0 if already exists
    """
    async with get_session() as session:
        # Check if already exists
        result = await session.execute(
            select(NotificationPreferences).where(NotificationPreferences.id == 1)
        )
        existing = result.scalar_one_or_none()

        if existing:
            print("  Global notification preferences already exist")
            return 0

        # Create with realistic settings
        pref = NotificationPreferences(
            id=1,
            enabled=True,
            sound=NotificationSound.ALERT.value,
            risk_filters=[RiskLevel.CRITICAL.value, RiskLevel.HIGH.value, RiskLevel.MEDIUM.value],
        )
        session.add(pref)
        await session.commit()

    print("  Created global notification preferences")
    return 1


async def seed_quiet_hours() -> int:
    """Create quiet hours periods (e.g., 11pm-7am weekdays).

    Creates global quiet hour periods for muting notifications.

    Returns:
        Number of quiet hour periods created
    """
    from datetime import time

    quiet_hour_templates = [
        # Standard overnight quiet hours
        {
            "start_time": "23:00",
            "end_time": "07:00",
            "days": [
                DayOfWeek.MONDAY.value,
                DayOfWeek.TUESDAY.value,
                DayOfWeek.WEDNESDAY.value,
                DayOfWeek.THURSDAY.value,
                DayOfWeek.FRIDAY.value,
            ],
            "label": "Weeknight sleep",
        },
        # Weekend late night
        {
            "start_time": "00:00",
            "end_time": "09:00",
            "days": [DayOfWeek.SATURDAY.value, DayOfWeek.SUNDAY.value],
            "label": "Weekend sleep",
        },
        # Afternoon nap time
        {
            "start_time": "14:00",
            "end_time": "15:30",
            "days": [DayOfWeek.SATURDAY.value, DayOfWeek.SUNDAY.value],
            "label": "Nap time",
        },
    ]

    created = 0

    async with get_session() as session:
        for template in quiet_hour_templates:
            start_parts = template["start_time"].split(":")
            end_parts = template["end_time"].split(":")

            quiet_hours = QuietHoursPeriod(
                label=template["label"],
                start_time=time(int(start_parts[0]), int(start_parts[1])),
                end_time=time(int(end_parts[0]), int(end_parts[1])),
                days=template["days"],
            )
            session.add(quiet_hours)
            created += 1

        await session.commit()

    print(f"  Created {created} quiet hour periods")
    return created


async def seed_camera_notification_settings() -> int:
    """Per-camera notification settings.

    Creates notification settings for each camera with varying risk thresholds.
    Schema: camera_id (unique), enabled, risk_threshold (0-100).

    Returns:
        Number of camera notification settings created
    """
    cameras = await get_cameras()
    if not cameras:
        print("  Warning: No cameras found.")
        return 0

    created = 0

    async with get_session() as session:
        for camera in cameras:
            # Check if setting already exists for this camera
            existing = await session.execute(
                select(CameraNotificationSetting).where(
                    CameraNotificationSetting.camera_id == camera.id
                )
            )
            if existing.scalar_one_or_none():
                continue

            # Determine threshold based on camera name patterns
            camera_name_lower = camera.name.lower() if camera.name else ""

            if "front" in camera_name_lower or "door" in camera_name_lower:
                # Front door - low threshold = notifies more (more sensitive)
                risk_threshold = 30
            elif "back" in camera_name_lower or "yard" in camera_name_lower:
                # Backyard - medium threshold
                risk_threshold = 50
            elif "garage" in camera_name_lower:
                # Garage - high threshold = only high-risk events
                risk_threshold = 70
            else:
                # Default - medium threshold
                risk_threshold = 50

            setting = CameraNotificationSetting(
                camera_id=camera.id,
                enabled=True,
                risk_threshold=risk_threshold,
            )
            session.add(setting)
            created += 1

        await session.commit()

    print(f"  Created {created} camera notification settings")
    return created


async def seed_person_embeddings(member_ids: list[int]) -> int:
    """Create face embeddings for known household members.

    Generates placeholder 512-dim vectors for person recognition.
    Stores as serialized bytes (actual model uses LargeBinary).

    Args:
        member_ids: List of household member IDs (integers)

    Returns:
        Number of person embeddings created
    """
    import pickle

    if not member_ids:
        print("  Warning: No household members found.")
        return 0

    created = 0

    async with get_session() as session:
        for member_id in member_ids:
            # Generate a placeholder embedding (512-dim random vector)
            # Serialize to bytes since the model uses LargeBinary
            embedding_vector = [random.uniform(-1, 1) for _ in range(512)]  # noqa: S311
            embedding_bytes = pickle.dumps(embedding_vector)

            person_embedding = PersonEmbedding(
                member_id=member_id,
                embedding=embedding_bytes,
                confidence=random.uniform(0.7, 0.99),  # noqa: S311
            )
            session.add(person_embedding)
            created += 1

        await session.commit()

    print(f"  Created {created} person embeddings")
    return created


async def seed_foundation_layer() -> tuple[dict[str, int], dict[str, list]]:
    """Seed all foundation layer data (Phase 1).

    Creates households, properties, members, vehicles, and notifications.
    Hierarchy: Household (top-level) -> Properties, Members, Vehicles

    Returns:
        Tuple of (counts dict, ids dict for use in Phase 2)
    """
    counts: dict[str, int] = {}
    ids: dict[str, list] = {}

    print("\n  Step 1: Creating households (top-level org)...")
    household_ids = await seed_households(num_households=3)
    counts["households"] = len(household_ids)
    ids["household_ids"] = household_ids

    print("\n  Step 2: Creating properties...")
    property_ids = await seed_properties(household_ids, num_properties=4)
    counts["properties"] = len(property_ids)
    ids["property_ids"] = property_ids

    print("\n  Step 3: Creating household members...")
    member_ids = await seed_household_members(household_ids, num_members=8)
    counts["household_members"] = len(member_ids)
    ids["member_ids"] = member_ids

    print("\n  Step 4: Creating registered vehicles...")
    vehicle_ids = await seed_registered_vehicles(household_ids, num_vehicles=5)
    counts["registered_vehicles"] = len(vehicle_ids)
    ids["vehicle_ids"] = vehicle_ids

    print("\n  Step 5: Creating notification preferences...")
    counts["notification_preferences"] = await seed_notification_preferences()

    print("\n  Step 6: Creating quiet hours...")
    counts["quiet_hours"] = await seed_quiet_hours()

    print("\n  Step 7: Creating camera notification settings...")
    counts["camera_notification_settings"] = await seed_camera_notification_settings()

    print("\n  Step 8: Creating person embeddings...")
    counts["person_embeddings"] = await seed_person_embeddings(member_ids)

    return counts, ids


# =============================================================================
# PHASE 2: ZONES & SPATIAL LAYER
# =============================================================================


async def seed_camera_zones(zones_per_camera: int = 3) -> list[str]:
    """Create detection zones for each camera.

    Types: 'driveway', 'entry_point', 'sidewalk', 'yard'.
    Each zone has polygon coordinates (normalized 0-1 for any resolution).

    Args:
        zones_per_camera: Number of zones to create per camera

    Returns:
        List of created zone IDs
    """
    cameras = await get_cameras()
    if not cameras:
        print("  Warning: No cameras found.")
        return []

    # Realistic polygon templates for different zone types
    zone_templates = [
        {
            "name": "Driveway",
            "zone_type": CameraZoneType.DRIVEWAY,
            "shape": CameraZoneShape.POLYGON,
            # Trapezoid receding into distance
            "coordinates": [[0.2, 0.9], [0.4, 0.5], [0.6, 0.5], [0.8, 0.9]],
            "color": "#EF4444",  # Red
            "priority": 2,
        },
        {
            "name": "Front Door",
            "zone_type": CameraZoneType.ENTRY_POINT,
            "shape": CameraZoneShape.RECTANGLE,
            # Rectangle around door area
            "coordinates": [[0.3, 0.2], [0.7, 0.2], [0.7, 0.7], [0.3, 0.7]],
            "color": "#F59E0B",  # Amber
            "priority": 3,
        },
        {
            "name": "Sidewalk",
            "zone_type": CameraZoneType.SIDEWALK,
            "shape": CameraZoneShape.POLYGON,
            # Horizontal strip at bottom
            "coordinates": [[0.0, 0.85], [1.0, 0.85], [1.0, 0.95], [0.0, 0.95]],
            "color": "#3B82F6",  # Blue
            "priority": 1,
        },
        {
            "name": "Front Yard",
            "zone_type": CameraZoneType.YARD,
            "shape": CameraZoneShape.POLYGON,
            # Large area covering yard
            "coordinates": [[0.0, 0.3], [1.0, 0.3], [1.0, 0.8], [0.0, 0.8]],
            "color": "#10B981",  # Green
            "priority": 0,
        },
        {
            "name": "Perimeter Edge",
            "zone_type": CameraZoneType.OTHER,
            "shape": CameraZoneShape.POLYGON,
            # Edge strip for perimeter detection
            "coordinates": [[0.0, 0.5], [0.1, 0.5], [0.1, 1.0], [0.0, 1.0]],
            "color": "#8B5CF6",  # Purple
            "priority": 1,
        },
    ]

    zone_ids = []

    async with get_session() as session:
        for camera in cameras:
            # Select subset of zones for this camera
            selected_templates = zone_templates[:zones_per_camera]

            for template in selected_templates:
                zone_id = str(uuid.uuid4())
                zone = CameraZone(
                    id=zone_id,
                    camera_id=camera.id,
                    name=f"{template['name']} ({camera.name[:20]})",
                    zone_type=template["zone_type"],
                    shape=template["shape"],
                    coordinates=template["coordinates"],
                    color=template["color"],
                    priority=template["priority"],
                    enabled=True,
                )
                session.add(zone)
                zone_ids.append(zone_id)

            print(f"  Created {len(selected_templates)} zones for camera: {camera.name}")

        await session.commit()

    return zone_ids


async def seed_areas(property_ids: list[str]) -> list[int]:
    """Create logical areas within properties.

    E.g., 'Front Yard', 'Backyard', 'Side Gate', 'Interior'.

    Args:
        property_ids: List of property IDs to create areas for

    Returns:
        List of created area IDs
    """
    if not property_ids:
        print("  Warning: No properties found.")
        return []

    area_templates = [
        {"name": "Front Yard", "description": "Main entrance and lawn area", "color": "#10B981"},
        {"name": "Backyard", "description": "Rear outdoor space", "color": "#3B82F6"},
        {"name": "Driveway", "description": "Vehicle parking and access", "color": "#EF4444"},
        {"name": "Side Gate", "description": "Secondary access point", "color": "#F59E0B"},
        {"name": "Garage", "description": "Vehicle storage area", "color": "#6366F1"},
        {"name": "Pool Area", "description": "Swimming pool and deck", "color": "#06B6D4"},
    ]

    area_ids = []

    async with get_session() as session:
        # Get property objects to get their integer IDs
        result = await session.execute(select(Property).where(Property.id.in_(property_ids)))
        properties = list(result.scalars().all())

        for prop in properties:
            # Each property gets 3-5 areas
            num_areas = min(random.randint(3, 5), len(area_templates))  # noqa: S311
            selected_areas = random.sample(area_templates, num_areas)

            for template in selected_areas:
                area = Area(
                    property_id=prop.id,
                    name=template["name"],
                    description=template["description"],
                    color=template["color"],
                )
                session.add(area)
                await session.flush()
                area_ids.append(area.id)

            print(f"  Created {num_areas} areas for property: {prop.name}")

        await session.commit()

    return area_ids


async def seed_camera_areas(area_ids: list[int]) -> int:
    """Link cameras to areas (many-to-many).

    A camera can cover multiple areas, an area can have multiple cameras.

    Args:
        area_ids: List of area IDs to link

    Returns:
        Number of camera-area links created
    """
    cameras = await get_cameras()
    if not cameras or not area_ids:
        print("  Warning: No cameras or areas found.")
        return 0

    created = 0

    async with get_session() as session:
        # Get areas with their property information
        result = await session.execute(select(Area).where(Area.id.in_(area_ids)))
        areas = list(result.scalars().all())

        for camera in cameras:
            # Each camera covers 1-3 random areas
            num_areas = min(random.randint(1, 3), len(areas))  # noqa: S311
            selected_areas = random.sample(areas, num_areas)

            for area in selected_areas:
                # Insert into association table
                await session.execute(
                    camera_areas.insert().values(camera_id=camera.id, area_id=area.id)
                )
                created += 1

        await session.commit()

    print(f"  Created {created} camera-area links")
    return created


async def seed_camera_calibrations() -> int:
    """Create camera calibration data for risk adjustment.

    Stores feedback-derived adjustments for each camera.

    Returns:
        Number of calibration records created
    """
    cameras = await get_cameras()
    if not cameras:
        print("  Warning: No cameras found.")
        return 0

    created = 0

    async with get_session() as session:
        for camera in cameras:
            # Check if calibration already exists for this camera
            existing = await session.execute(
                select(CameraCalibration).where(CameraCalibration.camera_id == camera.id)
            )
            if existing.scalar_one_or_none():
                continue

            # Generate realistic calibration data
            total_feedback = random.randint(20, 100)  # noqa: S311
            fp_count = int(total_feedback * random.uniform(0.1, 0.4))  # noqa: S311
            fp_rate = fp_count / total_feedback if total_feedback > 0 else 0.0

            # Calculate risk offset based on FP rate
            if fp_rate > 0.3:
                risk_offset = random.randint(-20, -10)  # noqa: S311
            elif fp_rate < 0.15:
                risk_offset = random.randint(5, 15)  # noqa: S311
            else:
                risk_offset = random.randint(-5, 5)  # noqa: S311

            calibration = CameraCalibration(
                camera_id=camera.id,
                total_feedback_count=total_feedback,
                false_positive_count=fp_count,
                false_positive_rate=round(fp_rate, 3),
                risk_offset=risk_offset,
                model_weights={"pose_model": round(random.uniform(0.5, 1.0), 2)},  # noqa: S311
                suppress_patterns=[],
                avg_model_score=round(random.uniform(40, 70), 1),  # noqa: S311
                avg_user_suggested_score=round(random.uniform(35, 65), 1),  # noqa: S311
            )
            session.add(calibration)
            created += 1

        await session.commit()

    print(f"  Created {created} camera calibration records")
    return created


async def seed_user_calibration() -> int:
    """Create user calibration data for personalized risk thresholds.

    Returns:
        Number of user calibration records created
    """
    # Create calibration for default user
    user_id = "default_user"

    async with get_session() as session:
        # Check if calibration already exists
        result = await session.execute(
            select(UserCalibration).where(UserCalibration.user_id == user_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            print("  User calibration already exists, skipping")
            return 0

        # Create with some feedback history
        calibration = UserCalibration(
            user_id=user_id,
            low_threshold=30,
            medium_threshold=60,
            high_threshold=85,
            decay_factor=0.1,
            correct_count=random.randint(50, 100),  # noqa: S311
            false_positive_count=random.randint(5, 20),  # noqa: S311
            missed_threat_count=random.randint(0, 5),  # noqa: S311
            severity_wrong_count=random.randint(2, 10),  # noqa: S311
        )
        session.add(calibration)
        await session.commit()

    print("  Created 1 user calibration record")
    return 1


async def seed_zone_household_configs(
    zone_ids: list[str], member_ids: list[str], vehicle_ids: list[str]
) -> int:
    """Create per-zone rules for household recognition.

    E.g., 'In driveway zone, suppress alerts for known family members'.

    Args:
        zone_ids: List of camera zone IDs
        member_ids: List of household member IDs (strings but contain integers)
        vehicle_ids: List of registered vehicle IDs

    Returns:
        Number of zone household configs created
    """
    if not zone_ids:
        print("  Warning: No zones found.")
        return 0

    created = 0

    async with get_session() as session:
        # Get member and vehicle integer IDs
        if member_ids:
            result = await session.execute(
                select(HouseholdMember).where(HouseholdMember.id.in_(member_ids))
            )
            members = list(result.scalars().all())
            member_int_ids = [m.id for m in members]
        else:
            member_int_ids = []

        if vehicle_ids:
            result = await session.execute(
                select(RegisteredVehicle).where(RegisteredVehicle.id.in_(vehicle_ids))
            )
            vehicles = list(result.scalars().all())
            vehicle_int_ids = [v.id for v in vehicles]
        else:
            vehicle_int_ids = []

        # Configure a subset of zones with household rules
        for zone_id in zone_ids[:10]:  # Configure up to 10 zones
            # Random subset of allowed members and vehicles
            allowed_members = (
                random.sample(member_int_ids, min(3, len(member_int_ids))) if member_int_ids else []
            )
            allowed_vehicles = (
                random.sample(vehicle_int_ids, min(2, len(vehicle_int_ids)))
                if vehicle_int_ids
                else []
            )

            # Optional owner (first allowed member)
            owner_id = allowed_members[0] if allowed_members else None

            config = ZoneHouseholdConfig(
                zone_id=zone_id,
                owner_id=owner_id,
                allowed_member_ids=allowed_members,
                allowed_vehicle_ids=allowed_vehicles,
                access_schedules=[
                    {
                        "member_ids": allowed_members[:2]
                        if len(allowed_members) >= 2
                        else allowed_members,
                        "cron_expression": "0 9-17 * * 1-5",
                        "description": "Weekday business hours",
                    }
                ]
                if allowed_members
                else [],
            )
            session.add(config)
            created += 1

        await session.commit()

    print(f"  Created {created} zone household configs")
    return created


async def seed_zones_spatial_layer(
    property_ids: list[str], member_ids: list[str], vehicle_ids: list[str]
) -> dict[str, int]:
    """Seed all zones & spatial layer data (Phase 2).

    Creates camera zones, areas, calibrations, and zone-household configs.

    Args:
        property_ids: List of property IDs from Phase 1
        member_ids: List of household member IDs from Phase 1
        vehicle_ids: List of vehicle IDs from Phase 1

    Returns:
        Dictionary with counts of created items
    """
    counts = {}

    print("\n  Step 1: Creating camera zones...")
    zone_ids = await seed_camera_zones(zones_per_camera=3)
    counts["camera_zones"] = len(zone_ids)

    print("\n  Step 2: Creating areas...")
    area_ids = await seed_areas(property_ids)
    counts["areas"] = len(area_ids)

    print("\n  Step 3: Creating camera-area links...")
    counts["camera_areas"] = await seed_camera_areas(area_ids)

    print("\n  Step 4: Creating camera calibrations...")
    counts["camera_calibrations"] = await seed_camera_calibrations()

    print("\n  Step 5: Creating user calibration...")
    counts["user_calibration"] = await seed_user_calibration()

    print("\n  Step 6: Creating zone household configs...")
    counts["zone_household_configs"] = await seed_zone_household_configs(
        zone_ids, member_ids, vehicle_ids
    )

    return counts


# =============================================================================
# PHASE 3: AI ENRICHMENT LAYER
# =============================================================================


async def seed_demographics_results() -> int:
    """Create demographic analysis for person detections.

    Only for detections where object_type='person'.

    Returns:
        Number of demographics results created
    """
    detections = await get_detections()
    person_detections = [d for d in detections if d.object_type == "person"]

    if not person_detections:
        print("  Warning: No person detections found.")
        return 0

    created = 0
    age_ranges = ["0-10", "11-20", "21-30", "31-40", "41-50", "51-60", "61-70", "71-80", "81+"]
    age_weights = [0.05, 0.15, 0.25, 0.20, 0.15, 0.10, 0.05, 0.03, 0.02]
    genders = ["male", "female", "unknown"]
    gender_weights = [0.48, 0.48, 0.04]

    async with get_session() as session:
        for detection in person_detections:
            # Check if demographics already exist for this detection
            result = await session.execute(
                select(DemographicsResult).where(DemographicsResult.detection_id == detection.id)
            )
            if result.scalar_one_or_none():
                continue

            # Weighted random selection
            age_range = random.choices(age_ranges, weights=age_weights, k=1)[0]  # noqa: S311
            gender = random.choices(genders, weights=gender_weights, k=1)[0]  # noqa: S311

            demographics = DemographicsResult(
                detection_id=detection.id,
                age_range=age_range,
                age_confidence=round(random.uniform(0.6, 0.95), 2),  # noqa: S311
                gender=gender,
                gender_confidence=round(random.uniform(0.7, 0.98), 2),  # noqa: S311
            )
            session.add(demographics)
            created += 1

        await session.commit()

    print(f"  Created {created} demographics results")
    return created


async def seed_pose_results() -> int:
    """Create pose keypoint data for person detections.

    17-point skeleton in COCO format.

    Returns:
        Number of pose results created
    """
    detections = await get_detections()
    person_detections = [d for d in detections if d.object_type == "person"]

    if not person_detections:
        print("  Warning: No person detections found.")
        return 0

    created = 0
    pose_classes = ["standing", "crouching", "bending_over", "arms_raised", "sitting", "lying_down"]
    pose_weights = [0.50, 0.10, 0.15, 0.10, 0.10, 0.05]

    async with get_session() as session:
        for detection in person_detections:
            # Check if pose result already exists
            result = await session.execute(
                select(PoseResult).where(PoseResult.detection_id == detection.id)
            )
            if result.scalar_one_or_none():
                continue

            pose_class = random.choices(pose_classes, weights=pose_weights, k=1)[0]  # noqa: S311

            # Generate 17 COCO keypoints [[x, y, confidence], ...]
            # Nose, left_eye, right_eye, left_ear, right_ear, left_shoulder, right_shoulder,
            # left_elbow, right_elbow, left_wrist, right_wrist, left_hip, right_hip,
            # left_knee, right_knee, left_ankle, right_ankle
            keypoints = []
            for _ in range(17):
                x = round(random.uniform(0.2, 0.8), 3)  # noqa: S311
                y = round(random.uniform(0.1, 0.9), 3)  # noqa: S311
                conf = round(random.uniform(0.5, 0.99), 3)  # noqa: S311
                keypoints.append([x, y, conf])

            # Suspicious if crouching (possible prowling) or arms_raised (possible threat)
            is_suspicious = pose_class in ("crouching", "arms_raised") and random.random() < 0.3  # noqa: S311

            pose_result = PoseResult(
                detection_id=detection.id,
                keypoints=keypoints,
                pose_class=pose_class,
                confidence=round(random.uniform(0.6, 0.95), 2),  # noqa: S311
                is_suspicious=is_suspicious,
            )
            session.add(pose_result)
            created += 1

        await session.commit()

    print(f"  Created {created} pose results")
    return created


async def seed_action_results() -> int:
    """Create action recognition results for person detections.

    Returns:
        Number of action results created
    """
    detections = await get_detections()
    person_detections = [d for d in detections if d.object_type == "person"]

    if not person_detections:
        print("  Warning: No person detections found.")
        return 0

    created = 0
    actions = [
        "walking",
        "running",
        "loitering",
        "climbing",
        "carrying_object",
        "using_phone",
        "looking_around",
        "approaching_door",
    ]
    action_weights = [0.30, 0.10, 0.15, 0.05, 0.15, 0.10, 0.10, 0.05]
    suspicious_actions = {"loitering", "climbing", "looking_around"}

    async with get_session() as session:
        for detection in person_detections:
            # Check if action result already exists
            result = await session.execute(
                select(ActionResult).where(ActionResult.detection_id == detection.id)
            )
            if result.scalar_one_or_none():
                continue

            action = random.choices(actions, weights=action_weights, k=1)[0]  # noqa: S311
            confidence = round(random.uniform(0.55, 0.95), 2)  # noqa: S311

            # Generate all scores
            all_scores = {}
            for a in actions:
                if a == action:
                    all_scores[a] = confidence
                else:
                    all_scores[a] = round(random.uniform(0.05, confidence - 0.1), 2)  # noqa: S311

            is_suspicious = action in suspicious_actions and random.random() < 0.4  # noqa: S311

            action_result = ActionResult(
                detection_id=detection.id,
                action=action,
                confidence=confidence,
                is_suspicious=is_suspicious,
                all_scores=all_scores,
            )
            session.add(action_result)
            created += 1

        await session.commit()

    print(f"  Created {created} action results")
    return created


async def seed_threat_detections() -> int:
    """Create threat detection results.

    Only creates threats for a small percentage of detections to be realistic.

    Returns:
        Number of threat detections created
    """
    detections = await get_detections()

    if not detections:
        print("  Warning: No detections found.")
        return 0

    created = 0
    threat_types = ["gun", "knife", "grenade", "explosive", "weapon", "other"]
    threat_weights = [0.25, 0.35, 0.05, 0.05, 0.20, 0.10]
    severities = ["critical", "high", "medium", "low"]
    severity_weights = [0.10, 0.25, 0.40, 0.25]

    async with get_session() as session:
        # Only create threats for ~5% of detections
        threat_sample_size = max(1, len(detections) // 20)
        sampled_detections = random.sample(detections, min(threat_sample_size, len(detections)))

        for detection in sampled_detections:
            threat_type = random.choices(threat_types, weights=threat_weights, k=1)[0]  # noqa: S311
            severity = random.choices(severities, weights=severity_weights, k=1)[0]  # noqa: S311

            # More severe threats get higher confidence
            if severity == "critical":
                confidence = round(random.uniform(0.80, 0.99), 2)  # noqa: S311
            elif severity == "high":
                confidence = round(random.uniform(0.65, 0.85), 2)  # noqa: S311
            else:
                confidence = round(random.uniform(0.45, 0.70), 2)  # noqa: S311

            # Generate realistic bounding box
            x1 = round(random.uniform(0.1, 0.7), 3)  # noqa: S311
            y1 = round(random.uniform(0.1, 0.7), 3)  # noqa: S311
            x2 = round(x1 + random.uniform(0.05, 0.2), 3)  # noqa: S311
            y2 = round(y1 + random.uniform(0.05, 0.2), 3)  # noqa: S311

            threat = ThreatDetection(
                detection_id=detection.id,
                threat_type=threat_type,
                confidence=confidence,
                severity=severity,
                bbox=[x1, y1, x2, y2],
            )
            session.add(threat)
            created += 1

        await session.commit()

    print(f"  Created {created} threat detections")
    return created


async def seed_scene_changes() -> int:
    """Create scene change detection records.

    Returns:
        Number of scene changes created
    """
    cameras = await get_cameras()
    if not cameras:
        print("  Warning: No cameras found.")
        return 0

    created = 0
    change_types = [
        SceneChangeType.VIEW_BLOCKED,
        SceneChangeType.ANGLE_CHANGED,
        SceneChangeType.VIEW_TAMPERED,
        SceneChangeType.UNKNOWN,
    ]
    change_weights = [0.30, 0.35, 0.20, 0.15]

    async with get_session() as session:
        # Create 1-3 scene changes per camera
        for camera in cameras:
            num_changes = random.randint(1, 3)  # noqa: S311
            for _ in range(num_changes):
                change_type = random.choices(change_types, weights=change_weights, k=1)[0]  # noqa: S311

                # Lower similarity score = more different from baseline
                if change_type == SceneChangeType.VIEW_BLOCKED:
                    similarity_score = round(random.uniform(0.1, 0.4), 3)  # noqa: S311
                elif change_type == SceneChangeType.VIEW_TAMPERED:
                    similarity_score = round(random.uniform(0.2, 0.5), 3)  # noqa: S311
                elif change_type == SceneChangeType.ANGLE_CHANGED:
                    similarity_score = round(random.uniform(0.3, 0.6), 3)  # noqa: S311
                else:
                    similarity_score = round(random.uniform(0.4, 0.7), 3)  # noqa: S311

                # Random detection time in past 7 days
                hours_ago = random.uniform(0, 168)  # noqa: S311
                detected_at = datetime.now(UTC) - timedelta(hours=hours_ago)

                # 30% are acknowledged
                acknowledged = random.random() < 0.3  # noqa: S311
                acknowledged_at = (
                    detected_at + timedelta(hours=random.uniform(0.5, 24))  # noqa: S311
                    if acknowledged
                    else None
                )

                scene_change = SceneChange(
                    camera_id=camera.id,
                    change_type=change_type,
                    similarity_score=similarity_score,
                    detected_at=detected_at,
                    acknowledged=acknowledged,
                    acknowledged_at=acknowledged_at,
                    file_path=f"/cameras/{camera.id}/scene_change_{uuid.uuid4().hex[:8]}.jpg",
                )
                session.add(scene_change)
                created += 1

        await session.commit()

    print(f"  Created {created} scene changes")
    return created


async def seed_reid_embeddings() -> int:
    """Create re-identification embeddings for tracking across cameras.

    512-dim vectors for person appearance matching.

    Returns:
        Number of re-id embeddings created
    """
    import hashlib

    detections = await get_detections()
    person_detections = [d for d in detections if d.object_type == "person"]

    if not person_detections:
        print("  Warning: No person detections found.")
        return 0

    created = 0

    async with get_session() as session:
        for detection in person_detections:
            # Check if embedding already exists
            result = await session.execute(
                select(ReIDEmbedding).where(ReIDEmbedding.detection_id == detection.id)
            )
            if result.scalar_one_or_none():
                continue

            # Generate 512-dim random embedding
            embedding = [round(random.uniform(-1, 1), 6) for _ in range(512)]  # noqa: S311

            # Generate hash for similarity lookups
            embedding_str = ",".join(f"{v:.6f}" for v in embedding)
            embedding_hash = hashlib.sha256(embedding_str.encode()).hexdigest()

            reid = ReIDEmbedding(
                detection_id=detection.id,
                embedding=embedding,
                embedding_hash=embedding_hash,
            )
            session.add(reid)
            created += 1

        await session.commit()

    print(f"  Created {created} re-id embeddings")
    return created


async def seed_ai_enrichment_layer() -> dict[str, int]:
    """Seed all AI enrichment layer data (Phase 3).

    Creates demographics, poses, actions, threats, scene changes, and re-id embeddings.

    Returns:
        Dictionary with counts of created items
    """
    counts = {}

    print("\n  Step 1: Creating demographics results...")
    counts["demographics_results"] = await seed_demographics_results()

    print("\n  Step 2: Creating pose results...")
    counts["pose_results"] = await seed_pose_results()

    print("\n  Step 3: Creating action results...")
    counts["action_results"] = await seed_action_results()

    print("\n  Step 4: Creating threat detections...")
    counts["threat_detections"] = await seed_threat_detections()

    print("\n  Step 5: Creating scene changes...")
    counts["scene_changes"] = await seed_scene_changes()

    print("\n  Step 6: Creating re-id embeddings...")
    counts["reid_embeddings"] = await seed_reid_embeddings()

    return counts


# =============================================================================
# PHASE 4: JOBS & EXPORTS LAYER
# =============================================================================


async def seed_jobs(num_jobs: int = 20) -> tuple[int, list[str]]:
    """Create background job records with realistic state distribution.

    State distribution: 70% completed, 15% failed, 10% running, 5% pending

    Args:
        num_jobs: Number of jobs to create

    Returns:
        Tuple of (count, list of job IDs)
    """
    job_types = [
        "video_export",
        "report_generation",
        "batch_analysis",
        "model_inference",
        "cleanup",
        "notification_digest",
    ]

    queue_names = ["default", "high_priority", "low_priority", "export"]

    created = 0
    job_ids: list[str] = []

    async with get_session() as session:
        for i in range(num_jobs):
            job_id = str(uuid.uuid4())

            # Generate created_at first, all other timestamps must be after this
            created_at = datetime.now(UTC) - timedelta(hours=random.randint(24, 72))  # noqa: S311

            # Determine status based on distribution
            rand = random.random()  # noqa: S311
            if rand < 0.70:
                status = JobStatus.COMPLETED.value
                # started_at is 1-6 hours after created_at
                started_at = created_at + timedelta(hours=random.randint(1, 6))  # noqa: S311
                completed_at = started_at + timedelta(minutes=random.randint(5, 30))  # noqa: S311
                progress = 100
                result = {"processed": random.randint(100, 1000), "success": True}  # noqa: S311
                error_message = None
            elif rand < 0.85:
                status = JobStatus.FAILED.value
                # started_at is 1-6 hours after created_at
                started_at = created_at + timedelta(hours=random.randint(1, 6))  # noqa: S311
                completed_at = started_at + timedelta(minutes=random.randint(5, 15))  # noqa: S311
                progress = random.randint(10, 90)  # noqa: S311
                result = None
                error_message = random.choice(  # noqa: S311
                    [
                        "GPU OOM at frame 73",
                        "Connection timeout to AI service",
                        "Invalid input file format",
                        "Rate limit exceeded",
                    ]
                )
            elif rand < 0.95:
                status = JobStatus.RUNNING.value
                # started_at is 1-3 hours after created_at
                started_at = created_at + timedelta(hours=random.randint(1, 3))  # noqa: S311
                completed_at = None
                progress = random.randint(10, 80)  # noqa: S311
                result = None
                error_message = None
            else:
                status = JobStatus.QUEUED.value
                started_at = None
                completed_at = None
                progress = 0
                result = None
                error_message = None

            job = Job(
                id=job_id,
                job_type=random.choice(job_types),  # noqa: S311
                status=status,
                queue_name=random.choice(queue_names),  # noqa: S311
                priority=random.randint(0, 4),  # noqa: S311
                created_at=created_at,
                started_at=started_at,
                completed_at=completed_at,
                progress_percent=progress,
                current_step=f"Step {i + 1}" if status == JobStatus.RUNNING.value else None,
                result=result,
                error_message=error_message,
                attempt_number=1 if status != JobStatus.FAILED.value else random.randint(1, 3),  # noqa: S311
                max_attempts=3,
            )
            session.add(job)
            job_ids.append(job_id)
            created += 1

        await session.commit()

    print(f"  Created {created} jobs")
    return created, job_ids


async def seed_job_attempts(job_ids: list[str], attempts_per_job: int = 2) -> int:
    """Create job attempt history showing retry behavior.

    Args:
        job_ids: List of job IDs to create attempts for
        attempts_per_job: Average number of attempts per job

    Returns:
        Number of job attempts created
    """
    from uuid import uuid4

    created = 0

    async with get_session() as session:
        # Get jobs to understand their status
        result = await session.execute(select(Job).where(Job.id.in_(job_ids)))
        jobs = list(result.scalars().all())

        for job in jobs:
            # Determine number of attempts based on job status
            if job.status == JobStatus.COMPLETED.value:
                num_attempts = random.randint(1, attempts_per_job)  # noqa: S311
            elif job.status == JobStatus.FAILED.value:
                num_attempts = random.randint(2, 3)  # noqa: S311
            else:
                num_attempts = 1

            for attempt_num in range(1, num_attempts + 1):
                # Determine attempt status
                is_last = attempt_num == num_attempts
                if job.status == JobStatus.COMPLETED.value and is_last:
                    attempt_status = JobAttemptStatus.SUCCEEDED
                    error_msg = None
                elif job.status == JobStatus.FAILED.value and is_last:
                    attempt_status = JobAttemptStatus.FAILED
                    error_msg = job.error_message
                elif job.status == JobStatus.RUNNING.value:
                    attempt_status = JobAttemptStatus.STARTED
                    error_msg = None
                elif not is_last:
                    attempt_status = JobAttemptStatus.FAILED
                    error_msg = "Transient error, will retry"
                else:
                    attempt_status = JobAttemptStatus.STARTED
                    error_msg = None

                started_at = (job.started_at or datetime.now(UTC)) - timedelta(
                    minutes=(num_attempts - attempt_num) * 5
                )
                ended_at = (
                    started_at + timedelta(minutes=random.randint(1, 10))  # noqa: S311
                    if attempt_status != JobAttemptStatus.STARTED
                    else None
                )

                attempt = JobAttempt(
                    id=uuid4(),
                    job_id=uuid.UUID(job.id),
                    attempt_number=attempt_num,
                    started_at=started_at,
                    ended_at=ended_at,
                    status=attempt_status,
                    worker_id=f"worker-{random.randint(1, 4)}",  # noqa: S311
                    error_message=error_msg,
                )
                session.add(attempt)
                created += 1

        await session.commit()

    print(f"  Created {created} job attempts")
    return created


async def seed_job_transitions(job_ids: list[str]) -> int:
    """Create job state machine transitions.

    Args:
        job_ids: List of job IDs to create transitions for

    Returns:
        Number of job transitions created
    """
    created = 0

    async with get_session() as session:
        result = await session.execute(select(Job).where(Job.id.in_(job_ids)))
        jobs = list(result.scalars().all())

        for job in jobs:
            transitions: list[tuple[str, str, JobTransitionTrigger]] = []

            # Build transition history based on current status
            # Use "created" as the initial state since from_status cannot be null
            if job.status == JobStatus.QUEUED.value:
                transitions = [("created", JobStatus.QUEUED.value, JobTransitionTrigger.SYSTEM)]
            elif job.status == JobStatus.RUNNING.value:
                transitions = [
                    ("created", JobStatus.QUEUED.value, JobTransitionTrigger.SYSTEM),
                    (JobStatus.QUEUED.value, JobStatus.RUNNING.value, JobTransitionTrigger.WORKER),
                ]
            elif job.status == JobStatus.COMPLETED.value:
                transitions = [
                    ("created", JobStatus.QUEUED.value, JobTransitionTrigger.SYSTEM),
                    (JobStatus.QUEUED.value, JobStatus.RUNNING.value, JobTransitionTrigger.WORKER),
                    (
                        JobStatus.RUNNING.value,
                        JobStatus.COMPLETED.value,
                        JobTransitionTrigger.WORKER,
                    ),
                ]
            elif job.status == JobStatus.FAILED.value:
                # Add retry transitions for failed jobs
                transitions = [
                    ("created", JobStatus.QUEUED.value, JobTransitionTrigger.SYSTEM),
                    (JobStatus.QUEUED.value, JobStatus.RUNNING.value, JobTransitionTrigger.WORKER),
                ]
                if job.attempt_number and job.attempt_number > 1:
                    transitions.append(
                        (
                            JobStatus.RUNNING.value,
                            JobStatus.QUEUED.value,
                            JobTransitionTrigger.RETRY,
                        )
                    )
                    transitions.append(
                        (
                            JobStatus.QUEUED.value,
                            JobStatus.RUNNING.value,
                            JobTransitionTrigger.WORKER,
                        )
                    )
                transitions.append(
                    (JobStatus.RUNNING.value, JobStatus.FAILED.value, JobTransitionTrigger.WORKER)
                )
            elif job.status == JobStatus.CANCELLED.value:
                transitions = [
                    ("created", JobStatus.QUEUED.value, JobTransitionTrigger.SYSTEM),
                    (JobStatus.QUEUED.value, JobStatus.CANCELLED.value, JobTransitionTrigger.USER),
                ]

            # Create transitions with proper timestamps
            base_time = job.created_at or datetime.now(UTC)
            for idx, (from_status, to_status, trigger) in enumerate(transitions):
                transition = JobTransition(
                    id=uuid.uuid4(),
                    job_id=job.id,
                    from_status=from_status,
                    to_status=to_status,
                    transitioned_at=base_time + timedelta(seconds=idx * 30),
                    triggered_by=trigger,
                    metadata={"source": "seed_script"},
                )
                session.add(transition)
                created += 1

        await session.commit()

    print(f"  Created {created} job transitions")
    return created


async def seed_job_logs(job_ids: list[str], logs_per_job: int = 5) -> int:
    """Create structured job execution logs.

    Args:
        job_ids: List of job IDs to create logs for
        logs_per_job: Average number of logs per job

    Returns:
        Number of job logs created
    """
    from uuid import uuid7

    log_messages = {
        LogLevel.INFO: [
            "Starting export for camera {camera}, 2h timerange",
            "Connecting to database",
            "Initializing GPU memory pool",
            "Processing batch {batch} of {total}",
            "Export completed successfully",
        ],
        LogLevel.DEBUG: [
            "Processed {count}/{total} frames",
            "Memory usage: {mem}MB",
            "GPU utilization: {gpu}%",
            "Queue depth: {depth}",
        ],
        LogLevel.WARNING: [
            "High memory usage detected",
            "Slow query detected: {ms}ms",
            "Retrying after transient error",
        ],
        LogLevel.ERROR: [
            "GPU OOM at frame {frame}, retrying with smaller batch",
            "Connection timeout to AI service",
            "Failed to process frame: {error}",
        ],
    }

    created = 0

    async with get_session() as session:
        result = await session.execute(select(Job).where(Job.id.in_(job_ids)))
        jobs = list(result.scalars().all())

        for job in jobs:
            # Determine number of logs based on job status
            num_logs = random.randint(logs_per_job - 2, logs_per_job + 2)  # noqa: S311
            if job.status == JobStatus.FAILED.value:
                num_logs += 2  # More logs for failed jobs

            base_time = job.started_at or job.created_at or datetime.now(UTC)

            for i in range(num_logs):
                # Determine log level
                if job.status == JobStatus.FAILED.value and i == num_logs - 1:
                    level = LogLevel.ERROR
                else:
                    rand = random.random()  # noqa: S311
                    if rand < 0.5:
                        level = LogLevel.INFO
                    elif rand < 0.8:
                        level = LogLevel.DEBUG
                    elif rand < 0.95:
                        level = LogLevel.WARNING
                    else:
                        level = LogLevel.ERROR

                messages = log_messages[level]
                message_template = random.choice(messages)  # noqa: S311

                # Fill in placeholders
                message = message_template.format(
                    camera="front_door",
                    batch=random.randint(1, 10),  # noqa: S311
                    total=10,
                    count=random.randint(10, 100),  # noqa: S311
                    mem=random.randint(500, 2000),  # noqa: S311
                    gpu=random.randint(50, 95),  # noqa: S311
                    depth=random.randint(0, 20),  # noqa: S311
                    ms=random.randint(100, 5000),  # noqa: S311
                    frame=random.randint(1, 100),  # noqa: S311
                    error="Invalid frame data",
                )

                log = JobLog(
                    id=uuid7(),
                    job_id=uuid.UUID(job.id),
                    attempt_number=job.attempt_number or 1,
                    timestamp=base_time + timedelta(seconds=i * 10),
                    level=level,
                    message=message,
                    context={"step": i + 1, "total_steps": num_logs},
                )
                session.add(log)
                created += 1

        await session.commit()

    print(f"  Created {created} job logs")
    return created


async def seed_export_jobs(num_exports: int = 10) -> int:
    """Create video/data export job records.

    Args:
        num_exports: Number of export jobs to create

    Returns:
        Number of export jobs created
    """
    from uuid import uuid7

    export_formats = ["csv", "json", "parquet", "mp4", "zip"]

    created = 0

    async with get_session() as session:
        # Get cameras for realistic exports
        result = await session.execute(select(Camera).limit(5))
        cameras = list(result.scalars().all())
        camera_ids = [c.id for c in cameras] if cameras else ["camera_1", "camera_2"]

        for i in range(num_exports):
            # Determine status with realistic distribution
            rand = random.random()  # noqa: S311
            is_pending = False
            if rand < 0.60:
                status = ExportJobStatus.COMPLETED
                progress = 100
                completed_at = datetime.now(UTC) - timedelta(hours=random.randint(1, 24))  # noqa: S311
                error = None
                output_path = f"/exports/export_{i}.{random.choice(export_formats)}"  # noqa: S311
                file_size = random.randint(1024 * 1024, 1024 * 1024 * 500)  # noqa: S311
            elif rand < 0.75:
                status = ExportJobStatus.FAILED
                progress = random.randint(10, 80)  # noqa: S311
                completed_at = datetime.now(UTC) - timedelta(hours=random.randint(1, 12))  # noqa: S311
                error = random.choice(  # noqa: S311
                    [
                        "Disk space exceeded",
                        "Invalid time range",
                        "Camera not available",
                    ]
                )
                output_path = None
                file_size = None
            elif rand < 0.90:
                status = ExportJobStatus.RUNNING
                progress = random.randint(10, 80)  # noqa: S311
                completed_at = None
                error = None
                output_path = None
                file_size = None
            else:
                status = ExportJobStatus.PENDING
                is_pending = True
                progress = 0
                completed_at = None
                error = None
                output_path = None
                file_size = None

            export_type = random.choice(list(ExportType))  # noqa: S311
            start_time = datetime.now(UTC) - timedelta(days=random.randint(1, 30))  # noqa: S311
            end_time = start_time + timedelta(hours=random.randint(1, 24))  # noqa: S311

            # Store filter params as JSON
            import json

            filter_params_data = {
                "time_range_start": start_time.isoformat(),
                "time_range_end": end_time.isoformat(),
                "camera_ids": random.sample(
                    camera_ids,
                    k=min(len(camera_ids), random.randint(1, 3)),  # noqa: S311
                ),
            }

            # Generate created_at first for proper timestamp ordering
            created_at = datetime.now(UTC) - timedelta(hours=random.randint(24, 48))  # noqa: S311
            started_at = (
                created_at + timedelta(minutes=random.randint(1, 30))  # noqa: S311
                if not is_pending
                else None
            )

            export_job = ExportJob(
                id=str(uuid7()),
                status=status,
                export_type=export_type.value,
                export_format=random.choice(export_formats),  # noqa: S311
                progress_percent=progress,
                current_step=f"Processing {progress}%"
                if status == ExportJobStatus.RUNNING
                else None,
                processed_items=int(progress * 10) if progress > 0 else 0,
                total_items=1000,
                created_at=created_at,
                started_at=started_at,
                completed_at=completed_at,
                output_path=output_path,
                output_size_bytes=file_size,
                error_message=error,
                filter_params=json.dumps(filter_params_data),
            )
            session.add(export_job)
            created += 1

        await session.commit()

    print(f"  Created {created} export jobs")
    return created


async def seed_jobs_exports_layer() -> dict[str, int]:
    """Seed all jobs & exports layer data (Phase 4).

    Creates jobs, job attempts, job transitions, job logs, and export jobs.

    Returns:
        Dictionary with counts of created items
    """
    counts: dict[str, int] = {}

    print("\n  Step 1: Creating jobs...")
    job_count, job_ids = await seed_jobs()
    counts["jobs"] = job_count

    print("\n  Step 2: Creating job attempts...")
    counts["job_attempts"] = await seed_job_attempts(job_ids)

    print("\n  Step 3: Creating job transitions...")
    counts["job_transitions"] = await seed_job_transitions(job_ids)

    print("\n  Step 4: Creating job logs...")
    counts["job_logs"] = await seed_job_logs(job_ids)

    print("\n  Step 5: Creating export jobs...")
    counts["export_jobs"] = await seed_export_jobs()

    return counts


# =============================================================================
# PHASE 5: EXPERIMENTATION & FEEDBACK LAYER
# =============================================================================


async def seed_prompt_configs(num_configs: int = 5) -> list[int]:
    """Create prompt configuration templates.

    Creates configurations for each AI model with realistic parameters.

    Args:
        num_configs: Number of configs to create (up to number of models)

    Returns:
        List of created config IDs
    """
    # Sample system prompts for different models
    nemotron_prompt = """You are a security AI analyzing camera footage. Evaluate threats objectively.

Assess each detection based on:
1. Object type and behavior
2. Time of day context
3. Location within property
4. Unusual patterns or movements

Rate risk on scale 0-100 where:
- 0-30: Low risk (normal activity)
- 31-60: Medium risk (unusual but not threatening)
- 61-85: High risk (potential threat)
- 86-100: Critical risk (immediate danger)

Respond with JSON containing: risk_score, risk_level, summary, reasoning."""

    florence_config = {"queries": ["<DETECT>", "<CAPTION>", "<DETAILED_CAPTION>"]}

    yolo_config = {
        "classes": ["person", "car", "truck", "dog", "cat", "bicycle", "package", "backpack"],
        "confidence_threshold": 0.35,
    }

    xclip_config = {
        "action_classes": [
            "walking",
            "running",
            "standing",
            "sitting",
            "loitering",
            "climbing",
            "fighting",
            "falling",
        ]
    }

    fashion_clip_config = {
        "clothing_categories": [
            "hoodie",
            "mask",
            "uniform",
            "casual",
            "formal",
            "backpack",
            "hat",
            "gloves",
        ]
    }

    configs = [
        {
            "model": "nemotron",
            "system_prompt": nemotron_prompt,
            "temperature": 0.7,
            "max_tokens": 2048,
        },
        {
            "model": "florence-2",
            "system_prompt": json.dumps(florence_config),
            "temperature": 0.3,
            "max_tokens": 512,
        },
        {
            "model": "yolo-world",
            "system_prompt": json.dumps(yolo_config),
            "temperature": 0.0,
            "max_tokens": 256,
        },
        {
            "model": "x-clip",
            "system_prompt": json.dumps(xclip_config),
            "temperature": 0.0,
            "max_tokens": 256,
        },
        {
            "model": "fashion-clip",
            "system_prompt": json.dumps(fashion_clip_config),
            "temperature": 0.0,
            "max_tokens": 256,
        },
    ]

    config_ids: list[int] = []

    async with get_session() as session:
        for _, config in enumerate(configs[:num_configs]):
            # Check if config already exists for this model
            result = await session.execute(
                select(PromptConfig).where(PromptConfig.model == config["model"])
            )
            existing = result.scalar_one_or_none()
            if existing:
                print(f"  PromptConfig for {config['model']} already exists, skipping")
                config_ids.append(existing.id)
                continue

            prompt_config = PromptConfig(
                model=config["model"],
                system_prompt=config["system_prompt"],
                temperature=config["temperature"],
                max_tokens=config["max_tokens"],
                version=1,
            )
            session.add(prompt_config)
            await session.flush()
            config_ids.append(prompt_config.id)
            print(f"  Created prompt config: {config['model']} (id={prompt_config.id})")

        await session.commit()

    return config_ids


async def seed_prompt_versions(versions_per_model: int = 4) -> int:
    """Create version history for prompt configurations.

    Creates multiple versions for each AI model to enable rollback and A/B testing.

    Args:
        versions_per_model: Number of versions per model

    Returns:
        Number of prompt versions created
    """
    import json

    # Sample config evolutions per model
    version_templates = {
        AIModel.NEMOTRON: [
            {
                "config": {
                    "system_prompt": "Initial risk assessment prompt v1.0",
                    "temperature": 0.8,
                },
                "change": "Initial prompt version",
            },
            {
                "config": {
                    "system_prompt": "Added time-of-day context awareness",
                    "temperature": 0.7,
                },
                "change": "Added temporal context for better risk assessment",
            },
            {
                "config": {
                    "system_prompt": "Improved threat classification accuracy",
                    "temperature": 0.7,
                },
                "change": "Refined threat categorization based on feedback",
            },
            {
                "config": {
                    "system_prompt": "Production-ready v2.0 with calibration support",
                    "temperature": 0.65,
                },
                "change": "Production release with user feedback integration",
            },
        ],
        AIModel.FLORENCE2: [
            {"config": {"queries": ["<DETECT>"]}, "change": "Initial detection queries"},
            {"config": {"queries": ["<DETECT>", "<CAPTION>"]}, "change": "Added captioning"},
            {
                "config": {"queries": ["<DETECT>", "<CAPTION>", "<DETAILED_CAPTION>"]},
                "change": "Added detailed captions",
            },
            {
                "config": {"queries": ["<DETECT>", "<DETAILED_CAPTION>", "<OCR>"]},
                "change": "Added OCR support",
            },
        ],
        AIModel.YOLO_WORLD: [
            {
                "config": {"classes": ["person", "car"], "confidence_threshold": 0.5},
                "change": "Basic detection",
            },
            {
                "config": {"classes": ["person", "car", "dog", "cat"], "confidence_threshold": 0.4},
                "change": "Added animals",
            },
            {
                "config": {
                    "classes": ["person", "car", "dog", "cat", "package"],
                    "confidence_threshold": 0.35,
                },
                "change": "Added package detection",
            },
            {
                "config": {
                    "classes": ["person", "car", "truck", "dog", "cat", "bicycle", "package"],
                    "confidence_threshold": 0.35,
                },
                "change": "Full class set",
            },
        ],
        AIModel.XCLIP: [
            {"config": {"action_classes": ["walking", "running"]}, "change": "Basic actions"},
            {
                "config": {"action_classes": ["walking", "running", "standing", "sitting"]},
                "change": "Added static poses",
            },
            {
                "config": {
                    "action_classes": ["walking", "running", "standing", "sitting", "loitering"]
                },
                "change": "Added suspicious behavior",
            },
            {
                "config": {
                    "action_classes": [
                        "walking",
                        "running",
                        "standing",
                        "sitting",
                        "loitering",
                        "climbing",
                        "fighting",
                    ]
                },
                "change": "Full action set",
            },
        ],
        AIModel.FASHION_CLIP: [
            {
                "config": {"clothing_categories": ["hoodie", "mask"]},
                "change": "Suspicious clothing",
            },
            {
                "config": {"clothing_categories": ["hoodie", "mask", "uniform"]},
                "change": "Added uniforms",
            },
            {
                "config": {
                    "clothing_categories": ["hoodie", "mask", "uniform", "casual", "formal"]
                },
                "change": "Added general clothing",
            },
            {
                "config": {
                    "clothing_categories": [
                        "hoodie",
                        "mask",
                        "uniform",
                        "casual",
                        "formal",
                        "backpack",
                    ]
                },
                "change": "Added accessories",
            },
        ],
    }

    created = 0

    async with get_session() as session:
        for model in AIModel:
            templates = version_templates.get(model, [])[:versions_per_model]

            for version_num, template in enumerate(templates, start=1):
                # Check if version already exists
                result = await session.execute(
                    select(PromptVersion).where(
                        PromptVersion.model == model,
                        PromptVersion.version == version_num,
                    )
                )
                if result.scalar_one_or_none():
                    continue

                is_active = version_num == len(templates)  # Latest version is active

                prompt_version = PromptVersion(
                    model=model,
                    version=version_num,
                    config_json=json.dumps(template["config"]),
                    change_description=template["change"],
                    is_active=is_active,
                    created_at=datetime.now(UTC)
                    - timedelta(days=(len(templates) - version_num) * 7),
                    created_by="system",
                )
                session.add(prompt_version)
                created += 1

        await session.commit()

    print(f"  Created {created} prompt versions")
    return created


async def seed_event_feedback(feedback_rate: float = 0.3) -> int:
    """Create user feedback on events.

    Creates feedback for a percentage of events to simulate user engagement.

    Args:
        feedback_rate: Percentage of events to add feedback to (0-1)

    Returns:
        Number of feedback records created
    """
    events = await get_events()
    if not events:
        print("  Warning: No events found.")
        return 0

    # Limit to events without feedback
    events_to_feedback = int(len(events) * feedback_rate)
    if events_to_feedback == 0:
        events_to_feedback = min(10, len(events))

    # Feedback type distribution: 70% correct, 15% severity_wrong, 10% false_positive, 5% missed
    feedback_weights = [0.35, 0.35, 0.10, 0.15, 0.05]
    feedback_types = list(FeedbackType)

    severity_levels = ["low", "medium", "high", "critical"]

    created = 0

    async with get_session() as session:
        # Get events without feedback
        result = await session.execute(
            select(Event)
            .outerjoin(EventFeedback)
            .where(EventFeedback.id.is_(None))
            .limit(events_to_feedback)
        )
        events_without_feedback = list(result.scalars().all())

        for event in events_without_feedback:
            feedback_type = random.choices(feedback_types, weights=feedback_weights, k=1)[0]  # noqa: S311

            # Generate expected_severity only for SEVERITY_WRONG
            expected_severity = None
            notes = None
            if feedback_type == FeedbackType.SEVERITY_WRONG:
                # Pick a different severity than the event's current
                current_severity = getattr(event, "severity", "medium")
                other_severities = [s for s in severity_levels if s != current_severity]
                expected_severity = random.choice(other_severities)  # noqa: S311
                notes = f"Should have been {expected_severity}, not {current_severity}"
            elif feedback_type == FeedbackType.FALSE_POSITIVE:
                notes = random.choice(  # noqa: S311
                    [
                        "This was just my neighbor",
                        "Regular delivery person",
                        "Family member coming home",
                        "Just a shadow",
                    ]
                )
            elif feedback_type == FeedbackType.MISSED_THREAT:
                notes = random.choice(  # noqa: S311
                    [
                        "Someone was lurking in background",
                        "Suspicious vehicle was parked",
                        "Person was checking doors",
                    ]
                )

            feedback = EventFeedback(
                event_id=event.id,
                feedback_type=feedback_type.value,
                notes=notes,
                expected_severity=expected_severity,
                created_at=datetime.now(UTC) - timedelta(hours=random.randint(1, 48)),  # noqa: S311
            )
            session.add(feedback)
            created += 1

        await session.commit()

    print(f"  Created {created} event feedback records")
    return created


async def seed_prometheus_alerts(num_alerts: int = 25) -> int:
    """Create Prometheus alert records.

    Creates alerts with realistic distributions of status and severity.

    Args:
        num_alerts: Number of alerts to create

    Returns:
        Number of alerts created
    """
    import hashlib

    alert_templates = [
        {
            "alertname": "HighCPU",
            "severity": "warning",
            "summary": "High CPU usage detected on {instance}",
            "description": "CPU usage has been above 80% for 5 minutes",
        },
        {
            "alertname": "GPUMemoryPressure",
            "severity": "critical",
            "summary": "GPU memory pressure on {instance}",
            "description": "GPU memory usage exceeded 90%",
        },
        {
            "alertname": "DiskSpaceLow",
            "severity": "warning",
            "summary": "Disk space low on {instance}",
            "description": "Less than 10% disk space remaining",
        },
        {
            "alertname": "AIServiceUnhealthy",
            "severity": "critical",
            "summary": "AI service {service} is unhealthy",
            "description": "Service health check failed for 3 consecutive attempts",
        },
        {
            "alertname": "HighLatency",
            "severity": "warning",
            "summary": "High latency in {service}",
            "description": "P95 latency exceeded 5 seconds",
        },
        {
            "alertname": "ErrorRateSpike",
            "severity": "critical",
            "summary": "Error rate spike in {service}",
            "description": "Error rate exceeded 5% in the last 5 minutes",
        },
        {
            "alertname": "CameraOffline",
            "severity": "warning",
            "summary": "Camera {camera} is offline",
            "description": "No frames received from camera for 5 minutes",
        },
        {
            "alertname": "DatabaseConnectionPool",
            "severity": "warning",
            "summary": "Database connection pool exhausted",
            "description": "All database connections are in use",
        },
    ]

    instances = ["ai-yolo26:8095", "ai-llm:8091", "ai-florence:8092", "backend:8000"]
    services = ["yolo26", "nemotron", "florence", "clip", "backend"]
    cameras = ["front_door", "backyard", "garage", "driveway"]

    created = 0

    async with get_session() as session:
        for i in range(num_alerts):
            template = random.choice(alert_templates)  # noqa: S311
            instance = random.choice(instances)  # noqa: S311
            service = random.choice(services)  # noqa: S311
            camera = random.choice(cameras)  # noqa: S311

            # Generate fingerprint using SHA-256 (truncated for compatibility)
            fingerprint_data = f"{template['alertname']}-{instance}-{i}"
            fingerprint = hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]

            # Determine status (70% resolved, 30% firing)
            is_firing = random.random() < 0.30  # noqa: S311
            status = PrometheusAlertStatus.FIRING if is_firing else PrometheusAlertStatus.RESOLVED

            starts_at = datetime.now(UTC) - timedelta(hours=random.randint(1, 72))  # noqa: S311
            ends_at = None if is_firing else starts_at + timedelta(minutes=random.randint(5, 120))  # noqa: S311

            labels = {
                "alertname": template["alertname"],
                "severity": template["severity"],
                "instance": instance,
                "service": service,
                "camera": camera,
                "job": "security-monitoring",
            }

            annotations = {
                "summary": template["summary"].format(
                    instance=instance, service=service, camera=camera
                ),
                "description": template["description"],
                "runbook_url": f"https://docs.example.com/runbooks/{template['alertname'].lower()}",
            }

            alert = PrometheusAlert(
                fingerprint=fingerprint,
                status=status,
                labels=labels,
                annotations=annotations,
                starts_at=starts_at,
                ends_at=ends_at,
                received_at=starts_at + timedelta(seconds=random.randint(1, 30)),  # noqa: S311
            )
            session.add(alert)
            created += 1

        await session.commit()

    print(f"  Created {created} Prometheus alerts")
    return created


async def seed_experiment_results(num_results: int = 50) -> int:
    """Create A/B test comparison results.

    Creates experiment results comparing V1 and V2 prompt performance.

    Args:
        num_results: Number of experiment results to create

    Returns:
        Number of experiment results created
    """
    cameras = await get_cameras()
    camera_ids = [c.id for c in cameras] if cameras else ["front_door", "backyard", "garage"]

    experiment_configs = [
        {
            "name": "nemotron_prompt_v2",
            "versions": ["shadow", "ab_test_10pct", "ab_test_30pct", "ab_test_50pct"],
        },
        {"name": "risk_scoring_calibration", "versions": ["shadow", "ab_test_25pct"]},
        {"name": "context_window_optimization", "versions": ["shadow", "ab_test_50pct"]},
    ]

    risk_levels = ["low", "medium", "high", "critical"]

    created = 0

    async with get_session() as session:
        events = await get_events()
        event_ids = [e.id for e in events] if events else [None]

        for i in range(num_results):
            config = random.choice(experiment_configs)  # noqa: S311
            version = random.choice(config["versions"])  # noqa: S311
            camera_id = random.choice(camera_ids)  # noqa: S311

            # Generate correlated but different V1/V2 scores
            v1_score = random.randint(10, 90)  # noqa: S311
            # V2 score is similar but with some variation
            v2_score = max(0, min(100, v1_score + random.randint(-15, 15)))  # noqa: S311

            v1_level = risk_levels[min(v1_score // 25, 3)]
            v2_level = risk_levels[min(v2_score // 25, 3)]

            # Latencies with V2 being slightly slower on average
            v1_latency = random.uniform(200, 800)  # noqa: S311
            v2_latency = v1_latency * random.uniform(0.9, 1.3)  # noqa: S311

            # Optionally link to an event
            event_id = random.choice(event_ids) if random.random() > 0.3 else None  # noqa: S311

            experiment_result = ExperimentResult(
                experiment_name=config["name"],
                experiment_version=version,
                camera_id=camera_id,
                batch_id=f"batch_{i // 10}",
                event_id=event_id,
                created_at=datetime.now(UTC) - timedelta(hours=random.randint(1, 168)),  # noqa: S311
                v1_risk_score=v1_score,
                v1_risk_level=v1_level,
                v1_latency_ms=round(v1_latency, 2),
                v2_risk_score=v2_score,
                v2_risk_level=v2_level,
                v2_latency_ms=round(v2_latency, 2),
                score_diff=abs(v1_score - v2_score),
            )
            session.add(experiment_result)
            created += 1

        await session.commit()

    print(f"  Created {created} experiment results")
    return created


async def seed_experimentation_feedback_layer() -> dict[str, int]:
    """Seed all experimentation & feedback layer data (Phase 5).

    Creates prompt configs, versions, event feedback, Prometheus alerts,
    and experiment results.

    Returns:
        Dictionary with counts of created items
    """
    counts: dict[str, int] = {}

    print("\n  Step 1: Creating prompt configs...")
    config_ids = await seed_prompt_configs()
    counts["prompt_configs"] = len(config_ids)

    print("\n  Step 2: Creating prompt versions...")
    counts["prompt_versions"] = await seed_prompt_versions()

    print("\n  Step 3: Creating event feedback...")
    counts["event_feedback"] = await seed_event_feedback()

    print("\n  Step 4: Creating Prometheus alerts...")
    counts["prometheus_alerts"] = await seed_prometheus_alerts()

    print("\n  Step 5: Creating experiment results...")
    counts["experiment_results"] = await seed_experiment_results()

    return counts


# =============================================================================
# PHASE 6: ZONE MONITORING LAYER
# =============================================================================


async def seed_zone_activity_baselines() -> int:
    """Create per-zone activity baseline statistics.

    Generates one baseline per zone with aggregated hourly/daily patterns.
    The new schema stores arrays of hourly (24 values) and daily (7 values)
    patterns instead of individual rows per hour/day/class.

    Returns:
        Number of zone activity baselines created
    """

    from sqlalchemy.exc import ProgrammingError

    # Check if table exists with expected schema
    try:
        async with get_session() as session:
            # Try a simple query to verify table and columns exist
            result = await session.execute(select(ZoneActivityBaseline).limit(1))
            result.scalar_one_or_none()
    except (ProgrammingError, Exception) as e:
        if "does not exist" in str(e):
            print(
                "  Warning: zone_activity_baselines table/columns do not exist (migration needed)"
            )
            return 0
        raise

    # Get existing camera zones
    async with get_session() as session:
        result = await session.execute(select(CameraZone))
        zones = list(result.scalars().all())

    if not zones:
        print("  Warning: No camera zones found.")
        return 0

    created = 0

    async with get_session() as session:
        for zone in zones:
            # Check if baseline already exists for this zone
            existing = await session.execute(
                select(ZoneActivityBaseline).where(ZoneActivityBaseline.zone_id == zone.id)
            )
            if existing.scalar_one_or_none():
                continue

            # Generate hourly activity pattern (24 values)
            # Higher activity during day (6am-6pm), lower at night
            hourly_pattern = []
            hourly_std = []
            for hour in range(24):
                if 6 <= hour < 9 or 17 <= hour < 20:  # Rush hours
                    base = 5.0 * random.uniform(0.8, 1.2)  # noqa: S311
                elif 9 <= hour < 17:  # Daytime
                    base = 3.0 * random.uniform(0.8, 1.2)  # noqa: S311
                elif hour >= 20 or hour < 6:  # Night
                    base = 0.5 * random.uniform(0.8, 1.2)  # noqa: S311
                else:
                    base = 1.5 * random.uniform(0.8, 1.2)  # noqa: S311
                hourly_pattern.append(round(base, 2))
                hourly_std.append(round(base * random.uniform(0.2, 0.4), 2))  # noqa: S311

            # Generate daily activity pattern (7 values, Monday=0 to Sunday=6)
            # Slightly less activity on weekends
            daily_pattern = []
            daily_std = []
            for day in range(7):
                if day >= 5:  # Weekend
                    base = 8.0 * random.uniform(0.8, 1.0)  # noqa: S311
                else:  # Weekday
                    base = 10.0 * random.uniform(0.9, 1.1)  # noqa: S311
                daily_pattern.append(round(base, 2))
                daily_std.append(round(base * random.uniform(0.15, 0.3), 2))  # noqa: S311

            # Entity class distribution
            entity_class_distribution = {
                "person": random.randint(40, 60),  # noqa: S311
                "vehicle": random.randint(20, 35),  # noqa: S311
                "animal": random.randint(5, 15),  # noqa: S311
            }

            # Calculate daily count statistics
            mean_daily = sum(hourly_pattern) * random.uniform(0.9, 1.1)  # noqa: S311
            std_daily = mean_daily * random.uniform(0.2, 0.35)  # noqa: S311
            min_daily = max(0, int(mean_daily - 2 * std_daily))
            max_daily = int(mean_daily + 3 * std_daily)

            baseline = ZoneActivityBaseline(
                zone_id=zone.id,
                camera_id=zone.camera_id,
                hourly_pattern=hourly_pattern,
                hourly_std=hourly_std,
                daily_pattern=daily_pattern,
                daily_std=daily_std,
                entity_class_distribution=entity_class_distribution,
                mean_daily_count=round(mean_daily, 2),
                std_daily_count=round(std_daily, 2),
                min_daily_count=min_daily,
                max_daily_count=max_daily,
                typical_crossing_rate=round(random.uniform(5.0, 15.0), 2),  # noqa: S311
                typical_crossing_std=round(random.uniform(2.0, 5.0), 2),  # noqa: S311
                typical_dwell_time=round(random.uniform(20.0, 60.0), 2),  # noqa: S311
                typical_dwell_std=round(random.uniform(8.0, 20.0), 2),  # noqa: S311
                sample_count=random.randint(30, 90),  # noqa: S311
                last_updated=datetime.now(UTC) - timedelta(hours=random.randint(1, 48)),  # noqa: S311
            )
            session.add(baseline)
            created += 1

        await session.commit()

    print(f"  Created {created} zone activity baselines")
    return created


async def seed_zone_anomalies(num_anomalies: int = 20) -> int:
    """Create zone anomaly detection records.

    Generates anomalies of various types and severities linked to zones.

    Args:
        num_anomalies: Number of anomalies to create

    Returns:
        Number of zone anomalies created
    """
    from uuid import uuid4

    from sqlalchemy.exc import ProgrammingError

    # Check if table exists with expected schema
    try:
        async with get_session() as session:
            # Try a simple query to verify table and columns exist
            result = await session.execute(select(ZoneAnomaly).limit(1))
            result.scalar_one_or_none()
    except (ProgrammingError, Exception) as e:
        if "does not exist" in str(e):
            print("  Warning: zone_anomalies table/columns do not exist (migration needed)")
            return 0
        raise

    # Get existing camera zones
    async with get_session() as session:
        result = await session.execute(select(CameraZone))
        zones = list(result.scalars().all())

    if not zones:
        print("  Warning: No camera zones found.")
        return 0

    # Get some detections for linking (optional)
    detections = await get_detections()
    detection_ids = [d.id for d in detections] if detections else []

    anomaly_templates = {
        AnomalyType.UNUSUAL_TIME.value: [
            {
                "title": "Activity at unusual hour",
                "description": "Person detected at 3 AM in {zone_name}",
            },
            {
                "title": "Late night vehicle",
                "description": "Vehicle detected after midnight in {zone_name}",
            },
            {
                "title": "Early morning movement",
                "description": "Activity detected before dawn in {zone_name}",
            },
        ],
        AnomalyType.UNUSUAL_FREQUENCY.value: [
            {"title": "Activity spike", "description": "Unusually high activity in {zone_name}"},
            {
                "title": "No activity anomaly",
                "description": "Expected activity missing in {zone_name}",
            },
            {
                "title": "Pattern disruption",
                "description": "Normal activity pattern disrupted in {zone_name}",
            },
        ],
        AnomalyType.UNUSUAL_DWELL.value: [
            {
                "title": "Extended presence",
                "description": "Person lingering in {zone_name} for extended time",
            },
            {"title": "Loitering detected", "description": "Prolonged presence in {zone_name}"},
        ],
        AnomalyType.UNUSUAL_ENTITY.value: [
            {"title": "Unknown person", "description": "Unrecognized individual in {zone_name}"},
            {
                "title": "Unexpected vehicle",
                "description": "Unknown vehicle detected in {zone_name}",
            },
        ],
    }

    created = 0

    async with get_session() as session:
        for _ in range(num_anomalies):
            zone = random.choice(zones)  # noqa: S311
            anomaly_type = random.choice(list(AnomalyType))  # noqa: S311
            templates = anomaly_templates.get(
                anomaly_type.value,
                [{"title": "Unknown anomaly", "description": "Anomaly in {zone_name}"}],
            )
            template = random.choice(templates)  # noqa: S311

            # Severity distribution: 60% info, 30% warning, 10% critical
            severity_rand = random.random()  # noqa: S311
            if severity_rand < 0.6:
                severity = AnomalySeverity.INFO.value
            elif severity_rand < 0.9:
                severity = AnomalySeverity.WARNING.value
            else:
                severity = AnomalySeverity.CRITICAL.value

            # Generate expected/actual/deviation values
            expected_value = random.uniform(2, 10)  # noqa: S311
            actual_value = expected_value * random.uniform(0.1, 3.0)  # noqa: S311
            deviation = abs(actual_value - expected_value) / max(expected_value, 0.1)

            # Random acknowledgment status
            acknowledged = random.random() < 0.3  # noqa: S311
            acknowledged_at = (
                datetime.now(UTC) - timedelta(hours=random.randint(1, 24))  # noqa: S311
                if acknowledged
                else None
            )
            acknowledged_by = "default_user" if acknowledged else None

            # Generate unique ID
            anomaly_id = str(uuid4())

            # Optionally link to a detection
            detection_id = (
                random.choice(detection_ids)  # noqa: S311
                if detection_ids and random.random() > 0.5  # noqa: S311
                else None
            )

            zone_name = zone.name or f"Zone {zone.id[:8]}"

            anomaly = ZoneAnomaly(
                id=anomaly_id,
                zone_id=zone.id,
                camera_id=zone.camera_id,
                anomaly_type=anomaly_type.value,
                severity=severity,
                title=template["title"],
                description=template["description"].format(zone_name=zone_name),
                expected_value=round(expected_value, 2),
                actual_value=round(actual_value, 2),
                deviation=round(deviation, 2),
                detection_id=detection_id,
                acknowledged=acknowledged,
                acknowledged_at=acknowledged_at,
                acknowledged_by=acknowledged_by,
                timestamp=datetime.now(UTC) - timedelta(hours=random.randint(1, 72)),  # noqa: S311
            )
            session.add(anomaly)
            created += 1

        await session.commit()

    print(f"  Created {created} zone anomalies")
    return created


async def seed_zone_monitoring_layer() -> dict[str, int]:
    """Seed all zone monitoring layer data (Phase 6).

    Creates zone activity baselines and zone anomalies.

    Returns:
        Dictionary with counts of created items
    """
    counts: dict[str, int] = {}

    print("\n  Step 1: Creating zone activity baselines...")
    counts["zone_activity_baselines"] = await seed_zone_activity_baselines()

    print("\n  Step 2: Creating zone anomalies...")
    counts["zone_anomalies"] = await seed_zone_anomalies()

    return counts


async def clear_all_data() -> None:
    """Clear all seeded data from the database."""
    async with get_session() as session:
        # Clear in reverse dependency order

        # Phase 6: Zone Monitoring
        print("  Clearing zone anomalies...")
        await session.execute(delete(ZoneAnomaly))

        print("  Clearing zone activity baselines...")
        await session.execute(delete(ZoneActivityBaseline))

        # Phase 5: Experimentation & Feedback
        print("  Clearing experiment results...")
        await session.execute(delete(ExperimentResult))

        print("  Clearing Prometheus alerts...")
        await session.execute(delete(PrometheusAlert))

        print("  Clearing event feedback...")
        await session.execute(delete(EventFeedback))

        print("  Clearing prompt versions...")
        await session.execute(delete(PromptVersion))

        print("  Clearing prompt configs...")
        await session.execute(delete(PromptConfig))

        # Phase 4: Jobs & Exports - clear first (no FK dependencies from other tables)
        print("  Clearing export jobs...")
        await session.execute(delete(ExportJob))

        print("  Clearing job logs...")
        await session.execute(delete(JobLog))

        print("  Clearing job transitions...")
        await session.execute(delete(JobTransition))

        print("  Clearing job attempts...")
        await session.execute(delete(JobAttempt))

        print("  Clearing jobs...")
        await session.execute(delete(Job))

        # Phase 3: AI Enrichment - clear first due to FK dependencies on detections
        print("  Clearing re-id embeddings...")
        await session.execute(delete(ReIDEmbedding))

        print("  Clearing action results...")
        await session.execute(delete(ActionResult))

        print("  Clearing threat detections...")
        await session.execute(delete(ThreatDetection))

        print("  Clearing pose results...")
        await session.execute(delete(PoseResult))

        print("  Clearing demographics results...")
        await session.execute(delete(DemographicsResult))

        print("  Clearing scene changes...")
        await session.execute(delete(SceneChange))

        # Phase 2: Zones & Spatial
        print("  Clearing zone household configs...")
        await session.execute(delete(ZoneHouseholdConfig))

        print("  Clearing user calibration...")
        await session.execute(delete(UserCalibration))

        print("  Clearing camera calibrations...")
        await session.execute(delete(CameraCalibration))

        print("  Clearing camera-area links...")
        await session.execute(camera_areas.delete())

        print("  Clearing areas...")
        await session.execute(delete(Area))

        print("  Clearing camera zones...")
        await session.execute(delete(CameraZone))

        # Phase 1: Foundation layer
        print("  Clearing person embeddings...")
        await session.execute(delete(PersonEmbedding))

        print("  Clearing camera notification settings...")
        await session.execute(delete(CameraNotificationSetting))

        print("  Clearing quiet hours...")
        await session.execute(delete(QuietHoursPeriod))

        print("  Clearing notification preferences...")
        await session.execute(delete(NotificationPreferences))

        print("  Clearing registered vehicles...")
        await session.execute(delete(RegisteredVehicle))

        print("  Clearing household members...")
        await session.execute(delete(HouseholdMember))

        print("  Clearing households...")
        await session.execute(delete(Household))

        print("  Clearing properties...")
        await session.execute(delete(Property))

        # Original tables
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
  # Full platform exercise - DEFAULT (all tables seeded)
  uv run python scripts/seed-events.py --images 100

  # Minimal mode - just pipeline data (old behavior)
  uv run python scripts/seed-events.py --images 100 --minimal

  # Config only - setup without heavy AI data
  uv run python scripts/seed-events.py --config-only

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
  2. File Watcher → YOLO26 (object detection)
  3. YOLO26 → Batch Aggregator (group detections)
  4. Batch Aggregator → Nemotron LLM (risk analysis)
  5. Events created with AI-generated summaries and risk scores

This generates real data including:
  - Events with actual LLM reasoning
  - Detection bounding boxes from YOLO26
  - Entities with real CLIP embeddings
  - Pipeline latency metrics for performance monitoring
  - Activity baselines for anomaly detection
  - Foundation data (properties, households, notifications)
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
        "--minimal",
        action="store_true",
        help="Minimal mode - just pipeline data (old behavior, skips foundation layer)",
    )
    parser.add_argument(
        "--config-only",
        action="store_true",
        help="Config only mode - seed configuration data without running AI pipeline",
    )

    args = parser.parse_args()

    # Determine seeding mode
    mode = "full"
    if args.minimal:
        mode = "minimal"
    elif args.config_only:
        mode = "config-only"

    print(f"Initializing database... (mode: {mode})")
    await init_db()

    if args.clear:
        print("\nClearing existing data...")
        await clear_all_data()

    total_created = {}

    # Store IDs for use across phases
    foundation_ids = {"property_ids": [], "household_ids": [], "member_ids": [], "vehicle_ids": []}

    # ==========================================================================
    # PHASE 1: FOUNDATION LAYER (unless --minimal)
    # ==========================================================================
    if not args.minimal:
        print("\n" + "=" * 50)
        print("SEEDING FOUNDATION LAYER (Phase 1)")
        print("=" * 50)
        print("Creating properties, households, members, vehicles, notifications...")

        foundation_counts, foundation_ids = await seed_foundation_layer()
        total_created.update(foundation_counts)

    # ==========================================================================
    # PHASE 2: ZONES & SPATIAL LAYER (unless --minimal)
    # ==========================================================================
    if not args.minimal:
        print("\n" + "=" * 50)
        print("SEEDING ZONES & SPATIAL LAYER (Phase 2)")
        print("=" * 50)
        print("Creating zones, areas, calibrations, zone-household configs...")

        zones_counts = await seed_zones_spatial_layer(
            property_ids=foundation_ids.get("property_ids", []),
            member_ids=foundation_ids.get("member_ids", []),
            vehicle_ids=foundation_ids.get("vehicle_ids", []),
        )
        total_created.update(zones_counts)

    # ==========================================================================
    # AI PIPELINE (unless --config-only)
    # ==========================================================================
    if not args.config_only:
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
                print("  Check that AI services (YOLO26, Nemotron) are running")
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

        # ==========================================================================
        # PHASE 3: AI ENRICHMENT LAYER (unless --minimal, requires detections)
        # ==========================================================================
        if not args.minimal:
            print("\n" + "=" * 50)
            print("SEEDING AI ENRICHMENT LAYER (Phase 3)")
            print("=" * 50)
            print("Creating demographics, poses, actions, threats, scene changes, re-id...")

            enrichment_counts = await seed_ai_enrichment_layer()
            total_created.update(enrichment_counts)

        # ==========================================================================
        # PHASE 4: JOBS & EXPORTS LAYER (unless --minimal)
        # ==========================================================================
        if not args.minimal:
            print("\n" + "=" * 50)
            print("SEEDING JOBS & EXPORTS LAYER (Phase 4)")
            print("=" * 50)
            print("Creating jobs, job attempts, job transitions, job logs, export jobs...")

            jobs_counts = await seed_jobs_exports_layer()
            total_created.update(jobs_counts)

        # ==========================================================================
        # PHASE 5: EXPERIMENTATION & FEEDBACK LAYER (unless --minimal)
        # ==========================================================================
        if not args.minimal:
            print("\n" + "=" * 50)
            print("SEEDING EXPERIMENTATION & FEEDBACK LAYER (Phase 5)")
            print("=" * 50)
            print("Creating prompt configs, versions, feedback, alerts, experiments...")

            experimentation_counts = await seed_experimentation_feedback_layer()
            total_created.update(experimentation_counts)

        # ==========================================================================
        # PHASE 6: ZONE MONITORING LAYER (unless --minimal)
        # ==========================================================================
        if not args.minimal:
            print("\n" + "=" * 50)
            print("SEEDING ZONE MONITORING LAYER (Phase 6)")
            print("=" * 50)
            print("Creating zone activity baselines, zone anomalies...")

            zone_monitoring_counts = await seed_zone_monitoring_layer()
            total_created.update(zone_monitoring_counts)

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
    else:
        print("\n--config-only specified, skipping AI pipeline")

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

    # Print foundation layer stats if seeded
    if not args.minimal:
        print("  Foundation layer (Phase 1):")
        print(f"    - Properties: {total_created.get('properties', 0)}")
        print(f"    - Households: {total_created.get('households', 0)}")
        print(f"    - Household members: {total_created.get('household_members', 0)}")
        print(f"    - Registered vehicles: {total_created.get('registered_vehicles', 0)}")
        print(f"    - Notification preferences: {total_created.get('notification_preferences', 0)}")
        print(f"    - Quiet hours: {total_created.get('quiet_hours', 0)}")
        print(
            f"    - Camera notification settings: {total_created.get('camera_notification_settings', 0)}"
        )
        print(f"    - Person embeddings: {total_created.get('person_embeddings', 0)}")
        print("  Zones & Spatial layer (Phase 2):")
        print(f"    - Camera zones: {total_created.get('camera_zones', 0)}")
        print(f"    - Areas: {total_created.get('areas', 0)}")
        print(f"    - Camera-area links: {total_created.get('camera_areas', 0)}")
        print(f"    - Camera calibrations: {total_created.get('camera_calibrations', 0)}")
        print(f"    - User calibration: {total_created.get('user_calibration', 0)}")
        print(f"    - Zone household configs: {total_created.get('zone_household_configs', 0)}")
        print("  AI Enrichment layer (Phase 3):")
        print(f"    - Demographics results: {total_created.get('demographics_results', 0)}")
        print(f"    - Pose results: {total_created.get('pose_results', 0)}")
        print(f"    - Action results: {total_created.get('action_results', 0)}")
        print(f"    - Threat detections: {total_created.get('threat_detections', 0)}")
        print(f"    - Scene changes: {total_created.get('scene_changes', 0)}")
        print(f"    - Re-ID embeddings: {total_created.get('reid_embeddings', 0)}")
        print("  Jobs & Exports layer (Phase 4):")
        print(f"    - Jobs: {total_created.get('jobs', 0)}")
        print(f"    - Job attempts: {total_created.get('job_attempts', 0)}")
        print(f"    - Job transitions: {total_created.get('job_transitions', 0)}")
        print(f"    - Job logs: {total_created.get('job_logs', 0)}")
        print(f"    - Export jobs: {total_created.get('export_jobs', 0)}")
        print("  Experimentation & Feedback layer (Phase 5):")
        print(f"    - Prompt configs: {total_created.get('prompt_configs', 0)}")
        print(f"    - Prompt versions: {total_created.get('prompt_versions', 0)}")
        print(f"    - Event feedback: {total_created.get('event_feedback', 0)}")
        print(f"    - Prometheus alerts: {total_created.get('prometheus_alerts', 0)}")
        print(f"    - Experiment results: {total_created.get('experiment_results', 0)}")
        print("  Zone Monitoring layer (Phase 6):")
        print(f"    - Zone activity baselines: {total_created.get('zone_activity_baselines', 0)}")
        print(f"    - Zone anomalies: {total_created.get('zone_anomalies', 0)}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
