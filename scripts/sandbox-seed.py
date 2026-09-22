#!/usr/bin/env python3
# ruff: noqa: E501
"""Offline mock-data seeder for the sandbox dev stack (no GPU, no AI services).

The project's scripts/seed-events.py exercises the real AI pipeline, which
needs YOLO26 + Nemotron. This script fabricates the same *shape* of data
directly through the SQLAlchemy models instead, so the dashboard renders a
populated event feed in a GPU-less sandbox.

Imagery: reuses the committed camera-style fixtures in
backend/tests/fixtures/images/pipeline_test/ (real Foscam alarm captures +
labeled test images). Nothing is downloaded; thumbnails resolve because the
detection file_path points at those files on disk.

Everything created is tagged for clean teardown:
  - events use batch_id prefix "sandbox-"
  - cameras are the four fixed sandbox cameras

Usage:
    uv run python scripts/sandbox-seed.py           # seed (skips if already seeded)
    uv run python scripts/sandbox-seed.py --clear   # wipe sandbox data first, re-seed
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, select  # noqa: E402

from backend.core.database import get_session, init_db  # noqa: E402
from backend.models.alert import Alert, AlertRule, AlertSeverity, AlertStatus  # noqa: E402
from backend.models.camera import Camera  # noqa: E402
from backend.models.camera_zone import CameraZone  # noqa: E402
from backend.models.detection import Detection  # noqa: E402
from backend.models.event import Event  # noqa: E402
from backend.models.event_detection import EventDetection  # noqa: E402
from backend.models.plate_read import PlateRead  # noqa: E402
from backend.models.property import Property  # noqa: E402

FIXTURES = ROOT / "backend/tests/fixtures/images/pipeline_test"
BATCH_PREFIX = "sandbox-"

# (camera_id, name)
CAMERAS = [
    ("front_door", "Front Door"),
    ("driveway", "Driveway"),
    ("backyard", "Backyard"),
    ("garage", "Garage"),
]

# Scenario per fixture image:
#   camera, object_type(s), confidence, minutes-ago, risk score,
#   summary, reasoning, [flagged], [reviewed], [trashed]
def scenarios(now: datetime) -> list[dict]:
    def ago(minutes: int) -> datetime:
        return now - timedelta(minutes=minutes)

    return [
        {
            "file": "test_person_house_front.jpg",
            "camera": "front_door", "objects": "person", "conf": 0.94,
            "at": ago(38), "risk": 12,
            "summary": "Resident approached the front door carrying groceries.",
            "reasoning": "Person walked directly to the door without scanning the surroundings; gait and approach vector match the known resident pattern. No tools, no concealment, daylight.",
        },
        {
            "file": "test_person_porch_1.jpg",
            "camera": "front_door", "objects": "person", "conf": 0.91,
            "at": ago(95), "risk": 47,
            "summary": "Unfamiliar person stood on the front porch and looked through the window.",
            "reasoning": "Subject matched no registered household member. Dwelled ~40 s on the porch, face directed at the living-room window, then left without knocking. Consistent with scouting behaviour.",
            "flags": {"recommend_review": True},
        },
        {
            "file": "test_person_porch_cat.jpg",
            "camera": "front_door", "objects": "person,cat", "conf": 0.88,
            "at": ago(150), "risk": 8,
            "summary": "Resident returned a cat to the porch.",
            "reasoning": "Known resident with a registered pet; brief interaction, immediate re-entry.",
            "reviewed": True,
        },
        {
            "file": "test_person_walking_dog.jpg",
            "camera": "backyard", "objects": "person,dog", "conf": 0.93,
            "at": ago(220), "risk": 5,
            "summary": "Household member walked the dog in the backyard.",
            "reasoning": "Registered resident and registered pet, routine evening activity.",
        },
        {
            "file": "test_pet_cat_porch_tabby.jpg",
            "camera": "front_door", "objects": "cat", "conf": 0.86,
            "at": ago(290), "risk": 3,
            "summary": "Cat crossed the front porch.",
            "reasoning": "Neighborhood cat, no human present, no interaction with property.",
        },
        {
            "file": "test_pet_dog_grass_brown.jpg",
            "camera": "backyard", "objects": "dog", "conf": 0.89,
            "at": ago(360), "risk": 4,
            "summary": "Dog playing in the backyard.",
            "reasoning": "Registered pet, normal play behaviour.",
        },
        {
            "file": "test_pet_dog_yard_labrador.jpg",
            "camera": "backyard", "objects": "dog", "conf": 0.9,
            "at": ago(430), "risk": 4,
            "summary": "Labrador resting in the backyard.",
            "reasoning": "Registered pet at rest; no concern.",
        },
        {
            "file": "test_vehicle_car_house.jpg",
            "camera": "driveway", "objects": "car", "conf": 0.95,
            "at": ago(60), "risk": 9,
            "summary": "Registered vehicle parked in the driveway.",
            "reasoning": "Plate matched registered household vehicle (ABC1234, Silver Toyota Camry).",
            "plate": "ABC1234",
        },
        {
            "file": "test_vehicle_sedan_road.jpg",
            "camera": "driveway", "objects": "car", "conf": 0.92,
            "at": ago(135), "risk": 15,
            "summary": "Sedan passed the driveway without stopping.",
            "reasoning": "Vehicle transited the field of view at low speed and did not park; street traffic.",
            "plate": "XYZ5678",
        },
        {
            "file": "test_vehicle_compact_building.jpg",
            "camera": "garage", "objects": "car", "conf": 0.9,
            "at": ago(205), "risk": 55,
            "summary": "Unrecognized compact vehicle stopped beside the garage.",
            "reasoning": "Plate did not match any registered vehicle. Vehicle remained stationary for >3 min adjacent to the garage entry with occupant visible inside.",
            "plate": "QQZ4410",
            "flags": {"recommend_review": True},
        },
        {
            "file": "MDAlarm_20250805-220848.jpg",
            "camera": "backyard", "objects": "person", "conf": 0.78,
            "at": ago(520), "risk": 68,
            "summary": "Person moved along the rear fence line at night.",
            "reasoning": "IR capture, night hours. Subject followed the fence line away from the house, pausing at the side gate. High-contrast face unavailable. Motion alarm trigger.",
            "alert": True,
        },
        {
            "file": "HMDAlarm_20260101-103424.jpg",
            "camera": "driveway", "objects": "person,car", "conf": 0.83,
            "at": ago(700), "risk": 91,
            "summary": "Unknown person peered into a parked vehicle's window in the driveway.",
            "reasoning": "Subject approached an unattended registered vehicle, cupped hands against the window, and left quickly when the camera IR illuminated. Vehicle-break-in precursor behaviour; risk raised to critical.",
            "alert": True, "flagged": True,
        },
        {
            "file": "HMDAlarm_20260101-171020.jpg",
            "camera": "front_door", "objects": "person,package", "conf": 0.87,
            "at": ago(1440), "risk": 18,
            "summary": "Delivery courier dropped a package at the front door.",
            "reasoning": "Uniformed courier, marked van visible at curb, drop-and-go pattern.",
        },
        {
            "file": "MDAlarm_20260101-143519.jpg",
            "camera": "garage", "objects": "person", "conf": 0.8,
            "at": ago(2880), "risk": 34,
            "summary": "Person briefly entered the garage driveway area and left.",
            "reasoning": "Daylight, brief presence near the garage door; no attempted entry observed.",
            "reviewed": True,
        },
        {
            "file": "test_person_walking_dog.jpg",
            "camera": "backyard", "objects": "person,dog", "conf": 0.92,
            "at": ago(4320), "risk": 6,
            "summary": "Household member walked the dog in the backyard.",
            "reasoning": "Registered resident and registered pet.",
            "trashed": True,
        },
    ]


def risk_level(score: int) -> str:
    # Mirrors the CASE expression in backend/models/event.py
    if score <= 29:
        return "low"
    if score <= 59:
        return "medium"
    if score <= 84:
        return "high"
    return "critical"


# Plausible pixel-space bbox on a 1920x1080 frame, varied by index.
BBOXES = [
    (760, 310, 420, 690), (640, 280, 500, 720), (820, 330, 380, 650),
    (500, 400, 620, 540), (900, 260, 440, 760),
]


async def clear(session) -> None:
    """Delete previously seeded sandbox data (children first)."""
    event_ids = (await session.execute(
        select(Event.id).where(Event.batch_id.like(f"{BATCH_PREFIX}%"))
    )).scalars().all()
    if event_ids:
        await session.execute(delete(EventDetection).where(EventDetection.event_id.in_(event_ids)))
        await session.execute(delete(Alert).where(Alert.event_id.in_(event_ids)))
        await session.execute(delete(Event).where(Event.id.in_(event_ids)))
    await session.execute(delete(AlertRule).where(AlertRule.name.in_(
        ["High-risk activity", "Critical: possible break-in", "Unrecognized vehicle"]
    )))
    cam_ids = [c for c, _ in CAMERAS]
    await session.execute(delete(PlateRead).where(PlateRead.camera_id.in_(cam_ids)))
    await session.execute(delete(CameraZone).where(CameraZone.camera_id.in_(cam_ids)))
    await session.execute(delete(Detection).where(Detection.camera_id.in_(cam_ids)))
    await session.execute(delete(Camera).where(Camera.id.in_(cam_ids)))
    await session.commit()
    print("cleared previous sandbox data")


async def seed(session) -> dict[str, int]:
    counts: dict[str, int] = {}
    now = datetime.now(UTC)

    # Attach to the first seeded property if the config layer ran (nullable FK; fine without).
    property_id = (await session.execute(select(Property.id).limit(1))).scalar_one_or_none()

    # ---- cameras ----------------------------------------------------------
    for cam_id, name in CAMERAS:
        session.add(Camera(
            id=cam_id, name=name,
            folder_path=f"/export/foscam/{name}",
            status="online", ingestion_mode="ftp",
            property_id=property_id,
            last_seen_at=now - timedelta(minutes=30),
        ))
    counts["cameras"] = len(CAMERAS)

    # ---- zones ------------------------------------------------------------
    zone_specs = [
        ("front_door", "Entry Walkway", "entry_point", "#4CAF50"),
        ("front_door", "Porch", "entry_point", "#FF9800"),
        ("driveway", "Driveway Pad", "driveway", "#2196F3"),
        ("backyard", "Perimeter Fence", "yard", "#F44336"),
        ("garage", "Garage Door", "other", "#4CAF50"),
    ]
    for cam, zname, ztype, color in zone_specs:
        session.add(CameraZone(
            id=str(uuid.uuid4()), camera_id=cam, name=zname,
            zone_type=ztype,
            # API schema wants [[x, y], …] pairs, not {"x":…,"y":…} dicts
            coordinates=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
            shape="rectangle", color=color, enabled=True, priority=0,
        ))
    counts["camera_zones"] = len(zone_specs)

    # ---- detections + events (one event per scenario) ---------------------
    alerts = 0
    plates = 0
    for i, sc in enumerate(scenarios(now)):
        img = FIXTURES / sc["file"]
        if not img.exists():
            print(f"  skip {sc['file']}: fixture missing")
            continue
        x, y, w, h = BBOXES[i % len(BBOXES)]
        det = Detection(
            camera_id=sc["camera"], file_path=str(img), file_type="jpg",
            detected_at=sc["at"], object_type=sc["objects"].split(",")[0],
            confidence=sc["conf"],
            bbox_x=x, bbox_y=y, bbox_width=w, bbox_height=h,
            media_type="image",
        )
        session.add(det)
        await session.flush()  # need det.id for the junction rows

        event = Event(
            batch_id=f"{BATCH_PREFIX}{sc['camera']}-{sc['at']:%Y%m%d%H%M}",
            camera_id=sc["camera"],
            started_at=sc["at"], ended_at=sc["at"] + timedelta(seconds=45),
            risk_score=sc["risk"], risk_level=risk_level(sc["risk"]),
            summary=sc["summary"], reasoning=sc["reasoning"],
            object_types=sc["objects"],
            reviewed=sc.get("reviewed", False),
            flagged=sc.get("flagged", False),
            deleted_at=now - timedelta(days=1) if sc.get("trashed") else None,
            recommended_action="Review footage and confirm household recognition." if sc["risk"] >= 60 else None,
        )
        session.add(event)
        await session.flush()
        session.add(EventDetection(event_id=event.id, detection_id=det.id))

        if sc.get("alert"):
            session.add(Alert(
                event_id=event.id,
                severity=AlertSeverity.CRITICAL if sc["risk"] >= 85 else AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                dedup_key=f"{BATCH_PREFIX}alert-{event.id}",
                is_high_priority=sc["risk"] >= 85,
            ))
            alerts += 1

        if sc.get("plate"):
            session.add(PlateRead(
                camera_id=sc["camera"], timestamp=sc["at"],
                plate_text=sc["plate"], raw_text=sc["plate"],
                detection_confidence=sc["conf"], ocr_confidence=0.91,
                # API schema wants [x1, y1, x2, y2] (list[float]), not a polygon
                bbox=[700.0, 620.0, 1180.0, 740.0],
                image_quality_score=0.82,
            ))
            plates += 1

    counts["detections"] = len(scenarios(now))
    counts["events"] = len(scenarios(now))
    counts["alerts"] = alerts
    counts["plate_reads"] = plates

    # ---- alert rules (drives the Alerts configuration view) ----------------
    rule_specs = [
        ("High-risk activity", "Raise an alert when risk score reaches 60", 60, None, AlertSeverity.HIGH),
        ("Critical: possible break-in", "Immediate alert on critical events", 85, None, AlertSeverity.CRITICAL),
        ("Unrecognized vehicle", "Alert on vehicles not matching registered plates", 40, ["car"], AlertSeverity.MEDIUM),
    ]
    for name, desc, threshold, objects, sev in rule_specs:
        session.add(AlertRule(
            name=name, description=desc, enabled=True,
            severity=sev, risk_threshold=threshold,
            object_types=objects,
            # Response schema requires a list here (null -> 500-swallowed-empty).
            channels=["webhook"],
            dedup_key_template=f"sandbox:{name}",
            cooldown_seconds=1800,
        ))
    counts["alert_rules"] = len(rule_specs)

    await session.commit()
    return counts


async def seed_admin(session) -> str | None:
    """Ensure an admin exists (SetupGuard blocks all API routes without one).

    Mirrors scripts/seed-events.py seed_admin_user, which seeds admin/admin
    when the users table is empty. No-op when any user exists.
    """
    from sqlalchemy import func as sa_func

    from backend.models.user import User
    from backend.services.auth_service import AuthService

    count = (await session.execute(select(sa_func.count(User.id)))).scalar() or 0
    if count > 0:
        return None
    session.add(User(
        id=str(uuid.uuid4()),
        username="admin",
        email="admin@localhost",
        password_hash=AuthService().hash_password("admin"),
        is_active=True,
        is_admin=True,
    ))
    await session.commit()
    return "admin / admin (username / password)"


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clear", action="store_true", help="wipe sandbox data before seeding")
    args = parser.parse_args()

    await init_db()
    async with get_session() as session:
        if args.clear:
            await clear(session)
        creds = await seed_admin(session)
        already = (await session.execute(
            select(Event.id).where(Event.batch_id.like(f"{BATCH_PREFIX}%")).limit(1)
        )).scalar_one_or_none()
        if already:
            print("sandbox data already seeded — use --clear to re-seed")
            if creds:
                print(f"admin created: {creds}")
            return 0
        counts = await seed(session)

    print("\nseeded:")
    for k, v in counts.items():
        print(f"  {k:14s} {v}")
    print(f"  images from     {FIXTURES.relative_to(ROOT)}")
    if creds:
        print(f"\nadmin login created: {creds}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
