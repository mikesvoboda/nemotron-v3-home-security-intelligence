#!/usr/bin/env python3
"""Seed the database with mock events and detections for UI testing."""

import asyncio
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.database import get_session, init_db
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from sqlalchemy import select

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


async def get_cameras() -> list[Camera]:
    """Get all cameras from the database."""
    async with get_session() as session:
        result = await session.execute(select(Camera))
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

            for j in range(num_detections):
                object_type = random.choice(OBJECT_TYPES)  # noqa: S311
                confidence = random.uniform(0.65, 0.98)  # noqa: S311

                # Generate mock bounding box
                bbox_x = random.randint(50, 400)  # noqa: S311
                bbox_y = random.randint(50, 300)  # noqa: S311
                bbox_width = random.randint(80, 200)  # noqa: S311
                bbox_height = random.randint(100, 250)  # noqa: S311

                # Use actual image path if available
                file_path = (
                    f"/app/data/cameras/{camera.folder_path.split('/')[-1]}/capture_00{j + 1}.jpg"
                )

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


async def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Seed mock events and detections for UI testing")
    parser.add_argument(
        "--count",
        type=int,
        default=15,
        help="Number of mock events to create (default: 15)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing events and detections before seeding",
    )

    args = parser.parse_args()

    print("Initializing database...")
    await init_db()

    if args.clear:
        print("Clearing existing events and detections...")
        async with get_session() as session:
            from sqlalchemy import delete

            await session.execute(delete(Event))
            await session.execute(delete(Detection))
            await session.commit()
        print("Cleared existing data")

    print(f"\nSeeding {args.count} mock events...")
    events, detections = await seed_mock_data(args.count)

    print(f"\nCreated {events} events with {detections} detections")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
