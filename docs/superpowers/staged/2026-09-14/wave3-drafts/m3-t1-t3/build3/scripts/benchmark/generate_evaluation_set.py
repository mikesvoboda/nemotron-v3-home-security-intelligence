#!/usr/bin/env python3
"""Generate the 100-event evaluation set for benchmarking.

Creates events with the following distribution:
- 70 low risk (0-25)
- 20 medium risk (26-50)
- 8 high risk (51-75)
- 2 critical risk (76-100)

Each event contains:
- event_id: Unique identifier
- prompt: Security scenario description
- expected_response: Ground truth response with risk_score, risk_level, summary, reasoning
- context: Camera, timestamp, and detection info

Note: This script uses the standard random module for test data generation.
This is intentional for reproducibility with seed(42). Security-sensitive
randomness is not required for synthetic benchmark data.
"""

from __future__ import annotations

import json
import random  # nosemgrep: insecure-random-not-used-for-crypto
from datetime import datetime, timedelta
from pathlib import Path

# Scenario templates for different risk levels
LOW_RISK_SCENARIOS = [
    ("Delivery person at front door during daytime", "delivery", "front_door"),
    ("Mail carrier placing package on porch", "mail", "front_porch"),
    ("Neighbor walking dog past property", "pedestrian", "sidewalk"),
    ("Family member arriving home from work", "family", "driveway"),
    ("Regular gardener working in yard", "maintenance", "backyard"),
    ("Child playing in front yard", "family", "front_yard"),
    ("Squirrel running across lawn", "animal", "front_yard"),
    ("Bird at bird feeder", "animal", "backyard"),
    ("Familiar vehicle pulling into driveway", "vehicle", "driveway"),
    ("Postal worker checking mailbox", "mail", "mailbox"),
]

MEDIUM_RISK_SCENARIOS = [
    ("Unknown person at door during evening", "unknown_person", "front_door"),
    ("Unfamiliar vehicle parked on street", "unknown_vehicle", "street"),
    ("Person looking through fence", "suspicious", "perimeter"),
    ("Door-to-door salesperson", "solicitor", "front_door"),
    ("Person taking photos of house", "suspicious", "sidewalk"),
]

HIGH_RISK_SCENARIOS = [
    ("Unknown person trying door handle at night", "intrusion_attempt", "front_door"),
    ("Person in hoodie circling property", "casing", "perimeter"),
    ("Vehicle with no plates slowing down", "suspicious_vehicle", "street"),
    ("Person climbing over fence", "trespassing", "fence"),
]

CRITICAL_RISK_SCENARIOS = [
    ("Person with weapon visible approaching", "armed_threat", "front_yard"),
    ("Window being forced open", "break_in", "window"),
]

CAMERAS = ["front_door", "backyard", "driveway", "side_gate", "garage", "patio"]


def _get_random_camera() -> str:
    """Get a random camera from the list."""
    return random.choice(CAMERAS)  # noqa: S311  # nosemgrep: insecure-random


def _get_random_days_ago() -> int:
    """Get a random number of days for timestamp generation."""
    return random.randint(0, 30)  # noqa: S311  # nosemgrep: insecure-random


def _get_random_hour() -> int:
    """Get a random hour of day."""
    return random.randint(0, 23)  # noqa: S311  # nosemgrep: insecure-random


def _get_random_minute() -> int:
    """Get a random minute."""
    return random.randint(0, 59)  # noqa: S311  # nosemgrep: insecure-random


def _get_random_scenario(scenarios: list) -> tuple:
    """Get a random scenario from the list."""
    return random.choice(scenarios)  # noqa: S311  # nosemgrep: insecure-random


def _get_random_score(min_score: int, max_score: int) -> int:
    """Get a random risk score within range."""
    return random.randint(min_score, max_score)  # noqa: S311  # nosemgrep: insecure-random


def _shuffle_events(events: list) -> None:
    """Shuffle the events list in place."""
    random.shuffle(events)


def generate_event(
    event_id: int,
    risk_level: str,
    risk_score: int,
    scenario: tuple[str, str, str],
) -> dict:
    """Generate a single evaluation event."""
    description, detection_type, location = scenario
    camera = _get_random_camera()

    # Generate a timestamp in the last 30 days
    base_time = datetime.now() - timedelta(days=_get_random_days_ago())
    hour = _get_random_hour()
    minute = _get_random_minute()
    timestamp = base_time.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # Generate reasoning based on risk level
    reasoning_parts = []
    if risk_level == "low":
        reasoning_parts = [
            f"Detection occurred during {get_time_context(hour)}",
            "Activity matches expected patterns for this time",
            f"Location ({location}) is commonly accessed",
            "No concerning behavioral indicators observed",
        ]
    elif risk_level == "medium":
        reasoning_parts = [
            f"Detection at {get_time_context(hour)} warrants attention",
            f"Unfamiliar activity detected at {location}",
            "Some behavioral indicators suggest monitoring",
            "Recommend continued observation",
        ]
    elif risk_level == "high":
        reasoning_parts = [
            f"Detection at {get_time_context(hour)} raises concern",
            f"Suspicious behavior observed at {location}",
            "Multiple concerning indicators present",
            "Immediate attention recommended",
        ]
    else:  # critical
        reasoning_parts = [
            f"Critical threat detected at {location}",
            "Immediate security concern identified",
            "Multiple severe risk indicators present",
            "Emergency response may be required",
        ]

    reasoning = ". ".join(reasoning_parts) + "."

    return {
        "event_id": f"evt_{event_id:03d}",
        "prompt": f"Analyze security event: {description}. Camera: {camera}. Time: {timestamp.strftime('%H:%M')}. Detected: {detection_type}.",
        "expected_response": {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "summary": description,
            "reasoning": reasoning,
        },
        "context": {
            "camera": camera,
            "timestamp": timestamp.isoformat(),
            "detection_type": detection_type,
            "location": location,
        },
    }


def get_time_context(hour: int) -> str:
    """Get human-readable time context."""
    if 6 <= hour < 12:
        return "morning hours"
    elif 12 <= hour < 17:
        return "afternoon hours"
    elif 17 <= hour < 21:
        return "evening hours"
    else:
        return "nighttime hours"


def generate_evaluation_set(output_dir: Path) -> None:
    """Generate the full 100-event evaluation set."""
    output_dir.mkdir(parents=True, exist_ok=True)

    events = []
    event_id = 0

    # Generate 70 low risk events (scores 5-25)
    for _ in range(70):
        scenario = _get_random_scenario(LOW_RISK_SCENARIOS)
        risk_score = _get_random_score(5, 25)
        event = generate_event(event_id, "low", risk_score, scenario)
        events.append(event)
        event_id += 1

    # Generate 20 medium risk events (scores 30-50)
    for _ in range(20):
        scenario = _get_random_scenario(MEDIUM_RISK_SCENARIOS)
        risk_score = _get_random_score(30, 50)
        event = generate_event(event_id, "medium", risk_score, scenario)
        events.append(event)
        event_id += 1

    # Generate 8 high risk events (scores 55-75)
    for _ in range(8):
        scenario = _get_random_scenario(HIGH_RISK_SCENARIOS)
        risk_score = _get_random_score(55, 75)
        event = generate_event(event_id, "high", risk_score, scenario)
        events.append(event)
        event_id += 1

    # Generate 2 critical risk events (scores 80-95)
    for idx in range(2):
        scenario = CRITICAL_RISK_SCENARIOS[idx % len(CRITICAL_RISK_SCENARIOS)]
        risk_score = _get_random_score(80, 95)
        event = generate_event(event_id, "critical", risk_score, scenario)
        events.append(event)
        event_id += 1

    # Shuffle events to mix risk levels
    _shuffle_events(events)

    # Write individual event files
    for event in events:
        event_file = output_dir / f"{event['event_id']}.json"
        event_file.write_text(json.dumps(event, indent=2))

    # Write combined events file
    combined_file = output_dir / "events.json"
    combined_file.write_text(json.dumps(events, indent=2))

    print(f"Generated {len(events)} events in {output_dir}")

    # Print distribution
    distribution = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for event in events:
        distribution[event["expected_response"]["risk_level"]] += 1
    print(f"Distribution: {distribution}")


if __name__ == "__main__":
    # Set seed for reproducibility
    random.seed(42)

    output_dir = Path("data/benchmark/evaluation-set")
    generate_evaluation_set(output_dir)
