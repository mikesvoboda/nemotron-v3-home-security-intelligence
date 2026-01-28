#!/usr/bin/env python3
"""
Migrate Cosmos synthetic videos to the standard data/synthetic structure.

This script:
1. Reads Cosmos video prompts and manifest
2. Maps each video to normal/suspicious/threats category
3. Creates directory structure with metadata and expected_labels
4. Moves video files (only unique _5s variants)

Usage:
    python scripts/migrate_cosmos_videos.py [--dry-run] [--copy]

Options:
    --dry-run   Show what would be done without making changes
    --copy      Copy files instead of moving them
"""

import argparse
import json
import shutil
import re
from datetime import datetime, timezone
from pathlib import Path

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent
COSMOS_DIR = PROJECT_ROOT / "data" / "synthetic" / "cosmos"
SYNTHETIC_DIR = PROJECT_ROOT / "data" / "synthetic"

# Category mapping based on VIDEO_CATEGORY_MAPPING.md
CATEGORY_MAP = {
    # E-Series: Everyday → normal
    **{f"E{i:02d}": "normal" for i in range(1, 23)},
    # F-Series: False Alarms → normal
    **{f"F{i:02d}": "normal" for i in range(1, 17)},
    # C-Series: Core Detection → suspicious
    **{f"C{i:02d}": "suspicious" for i in range(1, 24)},
    # R-Series: Risk/Threats → threats
    **{f"R{i:02d}": "threats" for i in range(1, 19)},
    # T-Series: Training Threats → threats
    **{f"T{i:02d}": "threats" for i in range(1, 41)},
    # P-Series: Mixed (explicit mapping)
    "P01": "normal",
    "P02": "suspicious",
    "P03": "suspicious",
    "P04": "suspicious",
    "P05": "suspicious",
    "P06": "suspicious",
    "P07": "threats",
    "P08": "threats",
    "P09": "threats",
    "P10": "suspicious",
    "P11": "threats",
    "P12": "suspicious",
    "P13": "suspicious",
    "P14": "suspicious",
    "P15": "suspicious",
    "P16": "suspicious",
    "P17": "suspicious",
    "P18": "suspicious",
    "P19": "suspicious",
    "P20": "suspicious",
    "P21": "threats",
    "P22": "suspicious",
    "P23": "suspicious",
    "P24": "suspicious",
    "P25": "normal",
    "P26": "normal",
    "P27": "normal",
    "P28": "normal",
    "P29": "normal",
    "P30": "normal",
    "P31": "normal",
    "P32": "normal",
    "P33": "normal",
    "P34": "normal",
    "P35": "normal",
    "P36": "suspicious",
    "P37": "suspicious",
    "P38": "normal",
    "P39": "suspicious",
    "P40": "suspicious",
    "P41": "suspicious",
    "P42": "suspicious",
    "P43": "suspicious",
    "P44": "suspicious",
    "P45": "suspicious",
    "P46": "suspicious",
    "P47": "normal",
    "P48": "suspicious",
}

# Risk score ranges by category
RISK_RANGES = {
    "normal": {"min": 0, "max": 25, "level": "low"},
    "suspicious": {"min": 26, "max": 60, "level": "medium"},
    "threats": {"min": 61, "max": 100, "level": "high"},
}

# Scenario name mappings (video_id -> readable name)
SCENARIO_NAMES = {
    # E-Series
    "E01": "amazon_delivery",
    "E02": "fedex_delivery",
    "E03": "ups_delivery",
    "E04": "usps_delivery",
    "E05": "doordash_delivery",
    "E06": "instacart_delivery",
    "E07": "landscaper",
    "E08": "pool_cleaner",
    "E09": "pest_control",
    "E10": "mail_carrier",
    "E11": "newspaper_delivery",
    "E12": "meter_reader",
    "E13": "cable_tech",
    "E14": "window_washer",
    "E15": "tree_trimmer",
    "E16": "irrigation_tech",
    "E17": "roofer",
    "E18": "real_estate",
    "E19": "house_sitter",
    "E20": "babysitter",
    "E21": "pet_sitter",
    "E22": "house_cleaner",
    # F-Series
    "F01": "wildlife_deer",
    "F02": "wildlife_rabbit",
    "F03": "wildlife_squirrel",
    "F04": "wildlife_raccoon",
    "F05": "wildlife_cat",
    "F06": "wildlife_bird",
    "F07": "weather_wind",
    "F08": "weather_rain",
    "F09": "shadow_movement",
    "F10": "headlights",
    "F11": "sun_glare",
    "F12": "cloud_shadow",
    "F13": "child_playing",
    "F14": "dog_walker",
    "F15": "jogger",
    "F16": "lost_neighbor",
    # C-Series
    "C01": "night_rain_approach",
    "C02": "night_approach",
    "C03": "dusk_approach",
    "C04": "day_approach",
    "C05": "night_loiter",
    "C06": "dusk_loiter",
    "C07": "backyard_night",
    "C08": "side_yard_night",
    "C09": "driveway_night",
    "C10": "garage_approach",
    "C11": "fence_check",
    "C12": "window_look",
    "C13": "door_check",
    "C14": "multiple_visits",
    "C15": "slow_approach",
    "C16": "fast_approach",
    "C17": "phone_loiter",
    "C18": "looking_around",
    "C19": "waiting",
    "C20": "pacing",
    "C21": "hood_up",
    "C22": "dark_clothing",
    "C23": "backpack",
    # R-Series
    "R01": "package_grab",
    "R02": "distraction_theft",
    "R03": "follow_delivery",
    "R04": "box_swap",
    "R05": "porch_pirate",
    "R06": "vehicle_theft",
    "R07": "window_check",
    "R08": "door_handle_test",
    "R09": "lock_picking",
    "R10": "forced_entry",
    "R11": "window_break",
    "R12": "garage_entry",
    "R13": "casing_photos",
    "R14": "marking_property",
    "R15": "lookout",
    "R16": "escape_route",
    "R17": "return_pattern",
    "R18": "group_approach",
    # T-Series
    "T01": "weapon_handgun",
    "T02": "weapon_knife",
    "T03": "weapon_bat",
    "T04": "aggressive_stance",
    "T05": "kicking_door",
    "T06": "window_break",
    "T07": "pry_bar",
    "T08": "masked_intruder",
    "T09": "multiple_intruders",
    "T10": "vehicle_ramming",
    # T11-T40: tracking variations
    **{f"T{i:02d}": f"tracking_{i-10:02d}" for i in range(11, 41)},
    # P-Series
    "P01": "delivery_baseline",
    "P02": "lingering",
    "P03": "window_peering",
    "P04": "handle_test",
    "P05": "circling_house",
    "P06": "return_visit",
    "P07": "crouching",
    "P08": "tool_visible",
    "P09": "forced_entry",
    "P10": "hooded_approach",
    "P11": "multiple_checks",
    "P12": "flee_on_light",
    "P13": "driveway_to_door",
    "P14": "door_to_side",
    "P15": "full_perimeter",
    "P16": "vehicle_exit",
    "P17": "backyard_entry",
    "P18": "garage_check",
    "P19": "walk_to_run",
    "P20": "disappear_reappear",
    "P21": "two_people_split",
    "P22": "loiter_zones",
    "P23": "quick_traverse",
    "P24": "slow_deliberate",
    "P25": "resident_return",
    "P26": "resident_groceries",
    "P27": "resident_dog",
    "P28": "resident_mail",
    "P29": "two_residents",
    "P30": "resident_trash",
    "P31": "known_car",
    "P32": "resident_unusual_time",
    "P33": "resident_rushed",
    "P34": "visitor_with_resident",
    "P35": "child_playing",
    "P36": "unknown_child",
    "P37": "sedan_approach",
    "P38": "delivery_van",
    "P39": "unknown_truck",
    "P40": "two_exit_vehicle",
    "P41": "front_plate",
    "P42": "rear_plate",
    "P43": "quick_dropoff",
    "P44": "idling_vehicle",
    "P45": "reverse_in",
    "P46": "motorcycle",
    "P47": "cyclist",
    "P48": "vehicle_night",
}


def extract_detections_from_prompt(prompt: str) -> list[dict]:
    """Extract expected detections from prompt text."""
    detections = []

    # Person detection
    person_keywords = ["person", "driver", "intruder", "resident", "worker", "child"]
    if any(kw in prompt.lower() for kw in person_keywords):
        detections.append({"class": "person", "min_confidence": 0.7, "count": 1})

    # Multiple people
    if any(kw in prompt.lower() for kw in ["two people", "group", "multiple"]):
        if detections:
            detections[-1]["count"] = 2

    # Vehicle detection
    vehicle_keywords = ["van", "truck", "car", "sedan", "vehicle", "motorcycle"]
    if any(kw in prompt.lower() for kw in vehicle_keywords):
        detections.append({"class": "vehicle", "min_confidence": 0.7, "count": 1})

    # Animal detection
    animal_keywords = ["deer", "rabbit", "squirrel", "raccoon", "cat", "dog", "bird"]
    for animal in animal_keywords:
        if animal in prompt.lower():
            detections.append({"class": animal, "min_confidence": 0.6, "count": 1})
            break

    # Package detection
    if "package" in prompt.lower() or "box" in prompt.lower():
        detections.append({"class": "package", "min_confidence": 0.6, "count": 1})

    return detections if detections else [{"class": "unknown", "min_confidence": 0.5}]


def extract_action_from_prompt(prompt: str) -> dict:
    """Extract action information from prompt."""
    action_map = {
        "delivers": ("delivering", False),
        "delivery": ("delivering", False),
        "approaches": ("approaching", False),
        "walks": ("walking", False),
        "running": ("running", True),
        "sprints": ("running", True),
        "loiter": ("loitering", True),
        "grabs": ("grabbing", True),
        "theft": ("stealing", True),
        "break": ("breaking", True),
        "force": ("forcing", True),
        "kick": ("kicking", True),
        "crouch": ("crouching", True),
        "circling": ("circling", True),
        "checking": ("checking", True),
        "peering": ("peering", True),
    }

    prompt_lower = prompt.lower()
    for keyword, (action, suspicious) in action_map.items():
        if keyword in prompt_lower:
            return {"action": action, "is_suspicious": suspicious}

    return {"action": "unknown", "is_suspicious": False}


def extract_scene_from_prompt(prompt: str) -> dict:
    """Extract scene information from prompt."""
    scene = {
        "location": "front_porch",
        "time_of_day": "day",
        "weather": "clear",
    }

    prompt_lower = prompt.lower()

    # Location
    if "backyard" in prompt_lower:
        scene["location"] = "backyard"
    elif "side yard" in prompt_lower:
        scene["location"] = "side_yard"
    elif "driveway" in prompt_lower:
        scene["location"] = "driveway"
    elif "garage" in prompt_lower:
        scene["location"] = "garage"

    # Time
    if "night" in prompt_lower:
        scene["time_of_day"] = "night"
    elif "dusk" in prompt_lower:
        scene["time_of_day"] = "dusk"
    elif "dawn" in prompt_lower:
        scene["time_of_day"] = "dawn"
    elif "midday" in prompt_lower:
        scene["time_of_day"] = "day"

    # Weather
    if "rain" in prompt_lower:
        scene["weather"] = "rain"

    return scene


def generate_expected_labels(video_id: str, prompt: str, category: str) -> dict:
    """Generate expected_labels.json content from prompt."""
    risk = RISK_RANGES[category]
    detections = extract_detections_from_prompt(prompt)
    action = extract_action_from_prompt(prompt)
    scene = extract_scene_from_prompt(prompt)

    # Determine if face should be visible
    face_visible = "face visible" in prompt.lower() or category == "normal"
    if any(kw in prompt.lower() for kw in ["mask", "hood", "concealed", "hidden"]):
        face_visible = False

    return {
        "source": "cosmos",
        "video_id": video_id,
        "category": category,
        "detections": detections,
        "face": {
            "detected": "person" in str(detections),
            "visible": face_visible,
        },
        "pose": {
            "is_suspicious": category != "normal",
        },
        "action": action,
        "scene": scene,
        "risk": {
            "min_score": risk["min"],
            "max_score": risk["max"],
            "level": risk["level"],
        },
        "validation": {
            "prompt_excerpt": prompt[:200] + "..." if len(prompt) > 200 else prompt,
        },
    }


def generate_metadata(video_id: str, scenario: str, category: str, video_file: str) -> dict:
    """Generate metadata.json content."""
    return {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
        "source": "cosmos",
        "video_id": video_id,
        "scenario": scenario,
        "category": category,
        "format": "video",
        "duration_sec": 5.8,
        "resolution": "1280x704",
        "fps": 16,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": [f"media/{video_file}"],
        "cosmos_metadata": {
            "model": "Cosmos-Predict2.5-14B",
            "seed": 0,
            "guidance": 7,
        },
    }


def generate_scenario_spec(video_id: str, scenario: str, category: str, prompt: str) -> dict:
    """Generate scenario_spec.json content."""
    scene = extract_scene_from_prompt(prompt)

    return {
        "id": f"cosmos_{video_id}_{scenario}",
        "category": category,
        "name": scenario.replace("_", " ").title(),
        "description": prompt[:500],
        "source": "cosmos",
        "scene": {
            "location": scene["location"],
            "camera_type": "security_camera",
            "resolution": "720p",
        },
        "environment": {
            "time_of_day": scene["time_of_day"],
            "weather": scene["weather"],
        },
        "generation": {
            "format": "video",
            "duration_sec": 5.8,
            "cosmos_prompt": prompt,
        },
    }


def get_unique_videos() -> list[tuple[str, Path]]:
    """Get list of unique videos (only _5s variants)."""
    videos_dir = COSMOS_DIR / "videos"
    unique_videos = []

    for video_file in sorted(videos_dir.glob("*_5s.mp4")):
        video_id = video_file.stem.replace("_5s", "")
        if video_id in CATEGORY_MAP:
            unique_videos.append((video_id, video_file))

    return unique_videos


def load_prompt(video_id: str) -> str:
    """Load prompt text for a video."""
    prompt_file = COSMOS_DIR / "prompts" / "generated" / f"{video_id}_5s.json"
    if prompt_file.exists():
        with open(prompt_file) as f:
            data = json.load(f)
            return data.get("prompt", "")
    return ""


def migrate_video(
    video_id: str,
    video_file: Path,
    dry_run: bool = False,
    copy_mode: bool = False,
) -> dict:
    """Migrate a single video to the synthetic structure."""
    category = CATEGORY_MAP.get(video_id)
    if not category:
        return {"status": "skipped", "reason": "no category mapping"}

    scenario = SCENARIO_NAMES.get(video_id, video_id.lower())
    prompt = load_prompt(video_id)

    # Target directory
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    target_dir = SYNTHETIC_DIR / category / f"cosmos_{video_id}_{scenario}_{timestamp}"
    media_dir = target_dir / "media"

    if dry_run:
        return {
            "status": "dry_run",
            "video_id": video_id,
            "source": str(video_file),
            "target": str(target_dir),
            "category": category,
            "scenario": scenario,
        }

    # Create directories
    media_dir.mkdir(parents=True, exist_ok=True)

    # Move or copy video file
    target_video = media_dir / video_file.name
    if copy_mode:
        shutil.copy2(video_file, target_video)
    else:
        shutil.move(video_file, target_video)

    # Generate and write metadata
    metadata = generate_metadata(video_id, scenario, category, video_file.name)
    with open(target_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    # Generate and write expected_labels
    expected_labels = generate_expected_labels(video_id, prompt, category)
    with open(target_dir / "expected_labels.json", "w") as f:
        json.dump(expected_labels, f, indent=2)

    # Generate and write scenario_spec
    scenario_spec = generate_scenario_spec(video_id, scenario, category, prompt)
    with open(target_dir / "scenario_spec.json", "w") as f:
        json.dump(scenario_spec, f, indent=2)

    # Copy screenshot if available
    screenshot = COSMOS_DIR / "screenshots" / f"{video_id}_5s_frame2.jpg"
    if screenshot.exists():
        shutil.copy2(screenshot, media_dir / "thumbnail.jpg")

    return {
        "status": "migrated",
        "video_id": video_id,
        "target": str(target_dir),
        "category": category,
        "scenario": scenario,
    }


def main():
    parser = argparse.ArgumentParser(description="Migrate Cosmos videos to synthetic structure")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--copy", action="store_true", help="Copy instead of move")
    args = parser.parse_args()

    print("=" * 60)
    print("Cosmos Video Migration")
    print("=" * 60)

    if args.dry_run:
        print("DRY RUN MODE - No changes will be made\n")

    videos = get_unique_videos()
    print(f"Found {len(videos)} unique videos to migrate\n")

    results = {"normal": 0, "suspicious": 0, "threats": 0, "skipped": 0}

    for video_id, video_file in videos:
        result = migrate_video(video_id, video_file, args.dry_run, args.copy)

        if result["status"] == "migrated" or result["status"] == "dry_run":
            category = result["category"]
            results[category] = results.get(category, 0) + 1
            action = "Would migrate" if args.dry_run else "Migrated"
            print(f"  {action}: {video_id} -> {category}/{result.get('scenario', 'unknown')}")
        else:
            results["skipped"] += 1
            print(f"  Skipped: {video_id} ({result.get('reason', 'unknown')})")

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Normal:     {results['normal']}")
    print(f"  Suspicious: {results['suspicious']}")
    print(f"  Threats:    {results['threats']}")
    print(f"  Skipped:    {results['skipped']}")
    print(f"  Total:      {sum(results.values())}")

    if not args.dry_run:
        # Write migration report
        report_file = COSMOS_DIR / "migration_report.json"
        with open(report_file, "w") as f:
            json.dump({
                "migrated_at": datetime.now(timezone.utc).isoformat(),
                "mode": "copy" if args.copy else "move",
                "results": results,
            }, f, indent=2)
        print(f"\nMigration report saved to: {report_file}")


if __name__ == "__main__":
    main()
