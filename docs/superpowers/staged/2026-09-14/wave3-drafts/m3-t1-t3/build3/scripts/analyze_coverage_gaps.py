#!/usr/bin/env python3
"""Analyze AI pipeline coverage gaps across all datasets.

Compares existing samples against the full AI pipeline requirements to
identify coverage gaps for exhaustive testing.

Usage:
    uv run python scripts/analyze_coverage_gaps.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SYNTHETIC_DIR = PROJECT_ROOT / "data" / "synthetic"

# ============================================================================
# AI PIPELINE REQUIREMENTS
# Based on the AI models and enrichment pipeline
# ============================================================================

# YOLO26 Object Detection - 9 security-relevant classes
YOLO_CLASSES = {"person", "car", "truck", "bus", "motorcycle", "bicycle", "dog", "cat", "bird"}

# Extended vehicle types from Vehicle Classifier
VEHICLE_TYPES = {
    "sedan",
    "suv",
    "truck",
    "van",
    "pickup",
    "hatchback",
    "coupe",
    "wagon",
    "convertible",
    "minivan",
    "motorcycle",
}

# X-CLIP Action Recognition - security-relevant actions
ACTION_TYPES = {
    # Normal actions
    "walking",
    "running",
    "delivering",
    "waving",
    "ringing_doorbell",
    "parking",
    "unloading",
    "gardening",
    "playing",
    # Suspicious actions
    "loitering",
    "looking_around",
    "hiding",
    "climbing",
    "pacing",
    "circling",
    "casing",
    "photographing",
    # Threat actions
    "fighting",
    "breaking_window",
    "picking_lock",
    "forced_entry",
    "weapon_use",
    "vandalism",
    "theft",
    "assault",
}

# Threat Detection - weapon types
WEAPON_TYPES = {"knife", "gun", "bat", "crowbar", "pry_bar", "hammer", "tool", "stick", "pipe"}

# Pet Classification
PET_TYPES = {"dog", "cat", "bird", "raccoon", "deer", "coyote", "squirrel", "rabbit", "skunk"}

# Risk Levels
RISK_LEVELS = {"low", "medium", "high", "critical"}

# Time of Day
TIME_OF_DAY = {"day", "night", "dawn", "dusk"}

# Weather Conditions
WEATHER_CONDITIONS = {"clear", "rain", "snow", "fog", "cloudy", "windy"}

# Scene Locations
SCENE_LOCATIONS = {
    "front_door",
    "driveway",
    "sidewalk",
    "backyard",
    "side_yard",
    "garage",
    "porch",
    "street",
    "parking_lot",
}

# Categories
CATEGORIES = {"normal", "suspicious", "threats"}


def load_all_samples() -> list[dict]:
    """Load all samples from synthetic and external directories."""
    samples = []

    for category in CATEGORIES:
        category_dir = SYNTHETIC_DIR / category
        if not category_dir.exists():
            continue

        for sample_dir in category_dir.iterdir():
            if not sample_dir.is_dir():
                continue

            labels_path = sample_dir / "expected_labels.json"
            if not labels_path.exists():
                continue

            try:
                labels = json.loads(labels_path.read_text())
                labels["_path"] = str(sample_dir)
                labels["_category_dir"] = category
                samples.append(labels)
            except json.JSONDecodeError:
                continue

    # Also check external subdirectory
    external_dir = SYNTHETIC_DIR / "external"
    if external_dir.exists():
        for category in CATEGORIES:
            category_dir = external_dir / category
            if not category_dir.exists():
                continue

            for sample_dir in category_dir.iterdir():
                if not sample_dir.is_dir():
                    continue

                labels_path = sample_dir / "expected_labels.json"
                if not labels_path.exists():
                    continue

                try:
                    labels = json.loads(labels_path.read_text())
                    labels["_path"] = str(sample_dir)
                    labels["_category_dir"] = category
                    labels["_source"] = "external"
                    samples.append(labels)
                except json.JSONDecodeError:
                    continue

    return samples


def analyze_coverage(samples: list[dict]) -> dict:
    """Analyze coverage across all AI pipeline requirements."""
    coverage = {
        "total_samples": len(samples),
        "by_source": defaultdict(int),
        "by_category": defaultdict(int),
        # Detection coverage
        "detection_classes": defaultdict(int),
        "yolo_classes_covered": set(),
        "yolo_classes_missing": set(),
        # Vehicle coverage
        "vehicle_types": defaultdict(int),
        "vehicle_types_missing": set(),
        # Action coverage
        "actions": defaultdict(int),
        "actions_covered": set(),
        "actions_missing": set(),
        # Weapon coverage (CRITICAL gap area)
        "weapons": defaultdict(int),
        "weapons_covered": set(),
        "weapons_missing": set(),
        "weapon_samples": [],  # Track which samples have weapons
        # Pet/Animal coverage
        "animals": defaultdict(int),
        "animals_covered": set(),
        "animals_missing": set(),
        # Risk level coverage
        "risk_levels": defaultdict(int),
        "risk_levels_missing": set(),
        # Scene coverage
        "time_of_day": defaultdict(int),
        "weather": defaultdict(int),
        "locations": defaultdict(int),
        # Enrichment model testing
        "face_detection_samples": 0,
        "pose_suspicious_samples": 0,
        "night_samples": 0,
        "thermal_samples": 0,
    }

    # Weapon keywords to search for in prompts and factors
    weapon_keywords = {
        "bat": ["bat", "baseball bat"],
        "gun": ["gun", "firearm", "pistol", "rifle", "handgun"],
        "knife": ["knife", "blade"],
        "crowbar": ["crowbar"],
        "pry_bar": ["pry bar", "prybar", "pry_bar"],
        "hammer": ["hammer"],
        "tool": ["tool", "burglary tool"],
        "pipe": ["pipe"],
        "stick": ["stick"],
    }

    for sample in samples:
        source = sample.get("source", "unknown")
        category = sample.get("category", sample.get("_category_dir", "unknown"))

        coverage["by_source"][source] += 1
        coverage["by_category"][category] += 1

        # Detection classes
        for det in sample.get("detections", []):
            cls = det.get("class", det.get("type", "unknown"))
            coverage["detection_classes"][cls] += 1

            if cls in YOLO_CLASSES:
                coverage["yolo_classes_covered"].add(cls)
            if cls in VEHICLE_TYPES:
                coverage["vehicle_types"][cls] += 1
            if cls in WEAPON_TYPES:
                coverage["weapons"][cls] += 1
                coverage["weapons_covered"].add(cls)
                coverage["weapon_samples"].append(sample.get("_path", "unknown"))
            if cls in PET_TYPES:
                coverage["animals"][cls] += 1
                coverage["animals_covered"].add(cls)

        # Action
        action = sample.get("action", {})
        action_name = action.get("action", "unknown")
        coverage["actions"][action_name] += 1
        if action_name != "unknown":
            coverage["actions_covered"].add(action_name)

        # Risk level
        risk = sample.get("risk", {})
        risk_level = risk.get("level", "unknown")
        coverage["risk_levels"][risk_level] += 1

        # Scene info
        scene = sample.get("scene", {})
        coverage["time_of_day"][scene.get("time_of_day", "unknown")] += 1
        coverage["weather"][scene.get("weather", "unknown")] += 1
        coverage["locations"][scene.get("location", "unknown")] += 1

        # Enrichment model tests
        face = sample.get("face", {})
        if face.get("detected"):
            coverage["face_detection_samples"] += 1

        pose = sample.get("pose", {})
        if pose.get("is_suspicious"):
            coverage["pose_suspicious_samples"] += 1

        if scene.get("time_of_day") == "night":
            coverage["night_samples"] += 1

        # Check for thermal/FLIR samples
        if "thermal" in str(sample.get("_path", "")).lower():
            coverage["thermal_samples"] += 1

        # Check for weapons in threats.types, risk.expected_factors, and validation.prompt_excerpt
        sample_text = ""
        threats_section = sample.get("threats", {})
        if isinstance(threats_section, dict):
            threat_types = threats_section.get("types", [])
            if isinstance(threat_types, list):
                sample_text += " ".join(str(t) for t in threat_types) + " "

        risk_factors = sample.get("risk", {}).get("expected_factors", [])
        if isinstance(risk_factors, list):
            sample_text += " ".join(str(f) for f in risk_factors) + " "

        validation = sample.get("validation", {})
        if isinstance(validation, dict):
            sample_text += validation.get("prompt_excerpt", "") + " "

        sample_text = sample_text.lower()

        for weapon_type, keywords in weapon_keywords.items():
            for keyword in keywords:
                if keyword.lower() in sample_text:
                    coverage["weapons"][weapon_type] += 1
                    coverage["weapons_covered"].add(weapon_type)
                    if sample.get("_path") not in coverage["weapon_samples"]:
                        coverage["weapon_samples"].append(sample.get("_path", "unknown"))
                    break

    # Calculate missing items
    coverage["yolo_classes_missing"] = YOLO_CLASSES - coverage["yolo_classes_covered"]
    coverage["weapons_missing"] = WEAPON_TYPES - coverage["weapons_covered"]
    coverage["animals_missing"] = PET_TYPES - coverage["animals_covered"]
    coverage["actions_missing"] = ACTION_TYPES - coverage["actions_covered"]
    coverage["risk_levels_missing"] = RISK_LEVELS - set(coverage["risk_levels"].keys())
    coverage["vehicle_types_missing"] = VEHICLE_TYPES - set(coverage["vehicle_types"].keys())

    return coverage


def print_coverage_report(coverage: dict) -> None:
    """Print a formatted coverage report."""
    print("=" * 70)
    print("AI PIPELINE COVERAGE ANALYSIS")
    print("=" * 70)

    print(f"\n📊 TOTAL SAMPLES: {coverage['total_samples']}")

    print("\n📁 By Source:")
    for source, count in sorted(coverage["by_source"].items()):
        print(f"   {source}: {count}")

    print("\n📂 By Category:")
    for cat, count in sorted(coverage["by_category"].items()):
        print(f"   {cat}: {count}")

    # YOLO Detection Classes
    print("\n" + "=" * 70)
    print("🎯 YOLO26 OBJECT DETECTION COVERAGE")
    print("=" * 70)
    covered = len(coverage["yolo_classes_covered"])
    total = len(YOLO_CLASSES)
    print(f"   Coverage: {covered}/{total} ({100 * covered / total:.1f}%)")
    print(f"   ✅ Covered: {sorted(coverage['yolo_classes_covered'])}")
    if coverage["yolo_classes_missing"]:
        print(f"   ❌ MISSING: {sorted(coverage['yolo_classes_missing'])}")

    print("\n   Detection class counts:")
    for cls, count in sorted(coverage["detection_classes"].items(), key=lambda x: -x[1])[:15]:
        marker = "✅" if cls in YOLO_CLASSES else "  "
        print(f"   {marker} {cls}: {count}")

    # X-CLIP Action Recognition
    print("\n" + "=" * 70)
    print("🎬 X-CLIP ACTION RECOGNITION COVERAGE")
    print("=" * 70)
    covered = len(coverage["actions_covered"])
    total = len(ACTION_TYPES)
    print(f"   Coverage: {covered}/{total} ({100 * covered / total:.1f}%)")
    print(f"   ✅ Covered: {sorted(coverage['actions_covered'])}")
    if coverage["actions_missing"]:
        print(f"   ❌ MISSING: {sorted(coverage['actions_missing'])}")

    # Weapons detection coverage - critical gap area
    print("\n" + "=" * 70)
    print("⚠️  WEAPON DETECTION COVERAGE (CRITICAL)")
    print("=" * 70)
    covered = len(coverage["weapons_covered"])
    total = len(WEAPON_TYPES)
    print(f"   Coverage: {covered}/{total} ({100 * covered / total:.1f}%)")
    print(f"   ✅ Covered: {sorted(coverage['weapons_covered'])}")
    if coverage["weapons_missing"]:
        print(f"   ❌ MISSING: {sorted(coverage['weapons_missing'])}")

    # Animals/Pets
    print("\n" + "=" * 70)
    print("🐾 PET/ANIMAL CLASSIFICATION COVERAGE")
    print("=" * 70)
    covered = len(coverage["animals_covered"])
    total = len(PET_TYPES)
    print(f"   Coverage: {covered}/{total} ({100 * covered / total:.1f}%)")
    print(f"   ✅ Covered: {sorted(coverage['animals_covered'])}")
    if coverage["animals_missing"]:
        print(f"   ❌ MISSING: {sorted(coverage['animals_missing'])}")

    # Vehicle Types
    print("\n" + "=" * 70)
    print("🚗 VEHICLE CLASSIFICATION COVERAGE")
    print("=" * 70)
    covered = len(set(coverage["vehicle_types"].keys()))
    total = len(VEHICLE_TYPES)
    print(f"   Coverage: {covered}/{total} ({100 * covered / total:.1f}%)")
    if coverage["vehicle_types_missing"]:
        print(f"   ❌ MISSING: {sorted(coverage['vehicle_types_missing'])}")

    # Risk Levels
    print("\n" + "=" * 70)
    print("🎲 RISK LEVEL COVERAGE")
    print("=" * 70)
    for level in ["low", "medium", "high", "critical"]:
        count = coverage["risk_levels"].get(level, 0)
        marker = "✅" if count > 0 else "❌"
        print(f"   {marker} {level}: {count}")

    # Scene Coverage
    print("\n" + "=" * 70)
    print("🌅 SCENE CONTEXT COVERAGE")
    print("=" * 70)

    print("\n   Time of Day:")
    for tod, count in sorted(coverage["time_of_day"].items(), key=lambda x: -x[1]):
        marker = "✅" if count > 0 else "❌"
        print(f"   {marker} {tod}: {count}")

    print("\n   Weather:")
    for weather, count in sorted(coverage["weather"].items(), key=lambda x: -x[1]):
        print(f"      {weather}: {count}")

    # Enrichment Models
    print("\n" + "=" * 70)
    print("🔍 ENRICHMENT MODEL TESTING")
    print("=" * 70)
    print(f"   Face Detection samples: {coverage['face_detection_samples']}")
    print(f"   Suspicious Pose samples: {coverage['pose_suspicious_samples']}")
    print(f"   Night samples: {coverage['night_samples']}")
    print(f"   Thermal/FLIR samples: {coverage['thermal_samples']}")

    # Summary
    print("\n" + "=" * 70)
    print("📋 COVERAGE SUMMARY")
    print("=" * 70)

    gaps = []
    if coverage["yolo_classes_missing"]:
        gaps.append(f"YOLO classes: {sorted(coverage['yolo_classes_missing'])}")
    if coverage["weapons_missing"]:
        gaps.append(f"Weapons (CRITICAL): {sorted(coverage['weapons_missing'])}")
    if coverage["animals_missing"]:
        gaps.append(f"Animals: {sorted(coverage['animals_missing'])}")
    if coverage["actions_missing"]:
        gaps.append(f"Actions: {len(coverage['actions_missing'])} missing")
    if coverage["vehicle_types_missing"]:
        gaps.append(f"Vehicle types: {sorted(coverage['vehicle_types_missing'])}")

    if gaps:
        print("\n   ⚠️  GAPS REQUIRING ATTENTION:")
        for gap in gaps:
            print(f"   - {gap}")
    else:
        print("\n   ✅ All major categories covered!")

    print("\n" + "=" * 70)


def main() -> int:
    """Main entry point."""
    samples = load_all_samples()

    if not samples:
        print("No samples found!")
        return 1

    coverage = analyze_coverage(samples)
    print_coverage_report(coverage)

    # Write detailed report
    report_path = PROJECT_ROOT / "data" / "synthetic" / "coverage_analysis.json"

    # Convert sets to lists for JSON serialization
    serializable = {}
    for key, value in coverage.items():
        if isinstance(value, set):
            serializable[key] = sorted(value)
        elif isinstance(value, defaultdict):
            serializable[key] = dict(value)
        else:
            serializable[key] = value

    report_path.write_text(json.dumps(serializable, indent=2))
    print(f"\nDetailed report saved to: {report_path}")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
