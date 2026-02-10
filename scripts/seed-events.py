#!/usr/bin/env python3
"""Seed the system by exercising the full AI pipeline end-to-end.

DEFAULT BEHAVIOR: Uses synthetic video data from data/synthetic/ for controlled
end-to-end testing with known expected outcomes. Use --existing-data to revert
to legacy behavior of touching images in /export/foscam.

This script processes data through the full pipeline:
  1. File Watcher → detects new images
  2. YOLO26 → object detection
  3. Batch Aggregator → groups detections into events
  4. Nemotron LLM → risk analysis with reasoning

Synthetic data provides:
  - Known expected labels for validation
  - Repeatable test scenarios across categories (normal, suspicious, threats)
  - Detection accuracy and risk score calibration metrics

Usage:
    # Default: Process 10 scenarios per category (~30 total)
    uv run python scripts/seed-events.py

    # Process all available synthetic scenarios
    uv run python scripts/seed-events.py --all

    # Process specific number of scenarios per category
    uv run python scripts/seed-events.py --scenarios 20

    # Process only specific categories
    uv run python scripts/seed-events.py --categories normal,suspicious

    # Parallel mode: Process all categories simultaneously (faster but
    # may cause cross-camera contamination inflating normal event scores)
    uv run python scripts/seed-events.py --parallel

    # Validate results against expected labels
    uv run python scripts/seed-events.py --validate

    # Legacy mode: Touch images from /export/foscam
    uv run python scripts/seed-events.py --existing-data --images 100

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
import shutil
import socket
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))


def _load_env_and_fix_database_url() -> None:
    """Load .env file and fix DATABASE_URL for local execution.

    When running outside containers, the DATABASE_URL uses container hostnames
    (e.g., 'postgres:5432') which don't resolve. This function:
    1. Loads .env from the project root
    2. Checks for DATABASE_URL_EXTERNAL (explicit local config)
    3. Detects if running locally (hostname doesn't resolve)
    4. Converts container hostname to localhost for local execution
    5. Uses POSTGRES_EXTERNAL_PORT if set (for port mapping differences)
    """
    from dotenv import load_dotenv

    # Find project root (parent of scripts/)
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"

    if env_file.exists():
        load_dotenv(env_file)
        print(f"Loaded environment from {env_file}")

    # Check for explicit external DATABASE_URL first
    external_url = os.environ.get("DATABASE_URL_EXTERNAL")
    if external_url:
        os.environ["DATABASE_URL"] = external_url
        print("Using DATABASE_URL_EXTERNAL for local execution")
        return

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
        # Check for external port override (container may expose different port)
        external_port = os.environ.get(
            "POSTGRES_EXTERNAL_PORT", os.environ.get("POSTGRES_PORT", "5432")
        )

        # Replace container hostname with localhost and optionally fix port
        new_url = database_url.replace(f"@{hostname}:", "@localhost:")
        if port != external_port:
            new_url = new_url.replace(f"@localhost:{port}/", f"@localhost:{external_port}/")
            print(
                f"Database hostname '{hostname}' doesn't resolve - "
                f"using localhost:{external_port} (mapped from container port {port})"
            )
        else:
            print(f"Database hostname '{hostname}' doesn't resolve - using localhost:{port}")
        os.environ["DATABASE_URL"] = new_url


# Service container-to-localhost port mappings
# Format: container_hostname -> (container_port, localhost_port)
_SERVICE_PORT_MAPPINGS = {
    "ai-clip": (8093, int(os.environ.get("CLIP_PORT", "8093"))),
    "ai-yolo26": (8095, int(os.environ.get("YOLO26_PORT", "8095"))),
    "ai-florence": (8092, int(os.environ.get("FLORENCE_PORT", "8092"))),
    "ai-llm": (8091, int(os.environ.get("LLM_PORT", "8091"))),
    "ai-enrichment": (8094, int(os.environ.get("ENRICHMENT_PORT", "8094"))),
    "ai-enrichment-light": (8096, int(os.environ.get("ENRICHMENT_LIGHT_PORT", "8096"))),
    "backend": (8000, int(os.environ.get("API_PORT", "8000"))),
}


def _fix_service_url(env_var: str, default_url: str) -> str:
    """Fix service URL for local execution.

    When running outside containers, service URLs use container hostnames
    (e.g., 'http://ai-clip:8093') which don't resolve. This function:
    1. Gets the URL from environment or uses default
    2. Checks if it uses a container hostname
    3. Translates to localhost if hostname doesn't resolve
    """
    url = os.environ.get(env_var, default_url)
    if not url:
        return default_url

    # Extract hostname from URL
    match = re.search(r"://([^:/@]+)(?::(\d+))?", url)
    if not match:
        return url

    hostname = match.group(1)
    port = match.group(2)

    # Skip if already localhost
    if hostname in ("localhost", "127.0.0.1"):
        return url

    # Check if hostname resolves
    try:
        socket.gethostbyname(hostname)
        return url  # Resolves, we're in container network
    except socket.gaierror:
        # Doesn't resolve - translate to localhost
        if hostname in _SERVICE_PORT_MAPPINGS:
            _, localhost_port = _SERVICE_PORT_MAPPINGS[hostname]
            new_url = url.replace(f"://{hostname}", "://localhost")
            if port and port != str(localhost_port):
                new_url = new_url.replace(f":{port}", f":{localhost_port}")
            return new_url
        else:
            # Unknown service, just replace hostname with localhost
            return url.replace(f"://{hostname}", "://localhost")


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

# Synthetic data path (relative to project root)
_PROJECT_ROOT = Path(__file__).parent.parent
SYNTHETIC_DATA_PATH = _PROJECT_ROOT / "data" / "synthetic"

# Synthetic scenario categories
SYNTHETIC_CATEGORIES = ["normal", "suspicious", "threats"]

# =============================================================================
# COCO CLASS NAME ALIASES
# =============================================================================
# Scenario expected_labels use abstract class names (e.g., "vehicle", "package")
# but YOLO26 produces COCO class names (e.g., "car", "truck", "backpack").
# This mapping lets validation accept any COCO equivalent for an abstract class.
COCO_CLASS_ALIASES: dict[str, list[str]] = {
    "vehicle": ["car", "truck", "bus", "motorcycle"],
    "package": ["backpack", "suitcase", "handbag"],
}
# Build reverse lookup: COCO name -> abstract class (for reporting)
COCO_ALIAS_REVERSE: dict[str, str] = {}
for _abstract, _coco_names in COCO_CLASS_ALIASES.items():
    for _coco in _coco_names:
        COCO_ALIAS_REVERSE[_coco] = _abstract

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
from backend.models.event_detection import EventDetection  # noqa: E402

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
from backend.models.llm_interaction import LLMInteraction  # noqa: E402
from backend.models.log import Log  # noqa: E402
from backend.models.notification_preferences import (  # noqa: E402
    CameraNotificationSetting,
    DayOfWeek,
    NotificationPreferences,
    NotificationSound,
    QuietHoursPeriod,
    RiskLevel,
)
from backend.models.plate_read import PlateRead  # noqa: E402
from backend.models.prometheus_alert import PrometheusAlert, PrometheusAlertStatus  # noqa: E402
from backend.models.prompt_config import PromptConfig  # noqa: E402
from backend.models.prompt_version import AIModel, PromptVersion  # noqa: E402
from backend.models.property import Property  # noqa: E402
from backend.models.scene_change import SceneChange, SceneChangeType  # noqa: E402
from backend.models.user import User  # noqa: E402
from backend.models.user_calibration import UserCalibration  # noqa: E402

# Phase 6 imports
from backend.models.zone_anomaly import AnomalySeverity, AnomalyType, ZoneAnomaly  # noqa: E402
from backend.models.zone_baseline import ZoneActivityBaseline  # noqa: E402
from backend.models.zone_household_config import ZoneHouseholdConfig  # noqa: E402
from backend.services.auth_service import hash_password  # noqa: E402
from sqlalchemy import delete, func, select  # noqa: E402


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


# =============================================================================
# SYNTHETIC DATA SEEDING FUNCTIONS
# =============================================================================


@dataclass
class SyntheticScenario:
    """Represents a synthetic test scenario from data/synthetic/."""

    path: Path
    category: str
    video_id: str
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)
    expected_labels: dict[str, Any] = field(default_factory=dict)
    scenario_spec: dict[str, Any] = field(default_factory=dict)
    video_path: Path | None = None
    image_path: Path | None = None  # For COCO-based scenarios with .jpg/.png images
    assigned_camera_id: str | None = None  # Runtime camera chosen for scenario injection


@dataclass
class ValidationResult:
    """Results of validating pipeline output against expected labels."""

    scenario: SyntheticScenario
    success: bool
    event_id: uuid.UUID | None = None
    actual_risk_score: int | None = None
    expected_risk_range: tuple[int, int] | None = None
    detection_matches: dict[str, bool] = field(default_factory=dict)
    enrichment_results: dict[str, bool] = field(default_factory=dict)
    enrichment_errors: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    # Enrichment quality metrics (Fix #6)
    prompt_template: str | None = None
    prompt_length: int | None = None
    enrichment_sections_present: list[str] = field(default_factory=list)
    llm_latency_ms: float | None = None
    # Separated accuracy dimensions
    event_matched: bool = False  # Was any event matched to this scenario?
    detection_correct: bool = False  # Did YOLO detect the expected classes?
    scoring_correct: bool = False  # Is risk_score in expected range?
    scoring_for_detected: bool = False  # Is score reasonable for what was actually detected?
    reasoning_quality_ok: bool = False  # Is LLM reasoning substantial and non-generic?
    actual_classes: set[str] = field(default_factory=set)  # What YOLO actually detected
    expected_classes: list[str] = field(default_factory=list)  # What was expected
    detection_errors: list[str] = field(default_factory=list)  # Detection-specific errors
    scoring_errors: list[str] = field(default_factory=list)  # Scoring-specific errors
    reasoning_errors: list[str] = field(default_factory=list)  # Reasoning-specific quality issues
    camera_name: str | None = None  # Which camera the event was on


def _safe_read_json(file_path: Path, base_path: Path) -> dict[str, Any] | None:
    """Safely read a JSON file, validating it's within the expected base path.

    Args:
        file_path: Path to the JSON file to read
        base_path: Expected base directory (path must be under this)

    Returns:
        Parsed JSON dict, or None if validation fails or file can't be read
    """
    try:
        # Resolve to absolute path and verify it's under base_path
        resolved = file_path.resolve()
        base_resolved = base_path.resolve()

        if not str(resolved).startswith(str(base_resolved)):
            return None

        with resolved.open() as f:  # nosemgrep: path-traversal-open
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _safe_write_json(file_path: Path, data: dict[str, Any], base_path: Path) -> bool:
    """Safely write a JSON file, validating it's within the expected base path.

    Args:
        file_path: Path to write the JSON file to
        data: Dictionary to serialize to JSON
        base_path: Expected base directory (path must be under this)

    Returns:
        True if write succeeded, False otherwise
    """
    try:
        # Resolve to absolute path and verify it's under base_path
        resolved = file_path.resolve()
        base_resolved = base_path.resolve()

        if not str(resolved).startswith(str(base_resolved)):
            return False

        resolved.parent.mkdir(parents=True, exist_ok=True)
        with resolved.open("w") as f:  # nosemgrep: path-traversal-open
            json.dump(data, f, indent=2)
        return True
    except OSError:
        return False


def discover_synthetic_scenarios(
    categories: list[str] | None = None,
    source_filter: str | None = None,
    per_category_limit: int | None = None,
) -> list[SyntheticScenario]:
    """Discover all synthetic scenarios in data/synthetic/.

    Args:
        categories: Optional list of categories to filter (normal, suspicious, threats)
        source_filter: Optional source filter (e.g., "cosmos" for Cosmos-generated videos)
        per_category_limit: Optional limit on scenarios with video per category (None = unlimited)

    Returns:
        List of SyntheticScenario objects with loaded metadata
    """
    scenarios = []

    if not SYNTHETIC_DATA_PATH.exists():
        print(f"Warning: Synthetic data path {SYNTHETIC_DATA_PATH} does not exist")
        return scenarios

    target_categories = categories or SYNTHETIC_CATEGORIES

    for category in target_categories:
        category_path = SYNTHETIC_DATA_PATH / category
        if not category_path.exists():
            continue

        # Count only scenarios with actual video files toward the limit
        category_with_video_count = 0
        for scenario_dir in sorted(category_path.iterdir()):
            if not scenario_dir.is_dir():
                continue

            # Filter by source if specified
            if source_filter and not scenario_dir.name.startswith(f"{source_filter}_"):
                continue

            # Load metadata files using safe read functions
            metadata_path = scenario_dir / "metadata.json"
            expected_labels_path = scenario_dir / "expected_labels.json"
            scenario_spec_path = scenario_dir / "scenario_spec.json"

            if not metadata_path.exists():
                continue

            # Use safe read to validate paths are within SYNTHETIC_DATA_PATH
            metadata = _safe_read_json(metadata_path, SYNTHETIC_DATA_PATH)
            if metadata is None:
                print(f"Warning: Failed to load metadata for {scenario_dir.name}")
                continue

            expected_labels = _safe_read_json(expected_labels_path, SYNTHETIC_DATA_PATH) or {}
            scenario_spec = _safe_read_json(scenario_spec_path, SYNTHETIC_DATA_PATH) or {}

            # Find media file (video or image)
            media_path = scenario_dir / "media"
            video_path = None
            image_path = None
            if media_path.exists():
                videos = list(media_path.glob("*.mp4"))
                if videos:
                    video_path = videos[0]
                else:
                    # Fall back to image files (COCO-based scenarios)
                    images = list(media_path.glob("*.jpg")) + list(media_path.glob("*.png"))
                    if images:
                        image_path = images[0]

            has_media = video_path is not None or image_path is not None

            # When there's a limit, only include scenarios with actual media files
            if per_category_limit:
                if not has_media:
                    continue  # Skip scenarios without media when limiting
                if category_with_video_count >= per_category_limit:
                    break  # Got enough for this category
                category_with_video_count += 1

            scenario = SyntheticScenario(
                path=scenario_dir,
                category=category,
                video_id=metadata.get("video_id", scenario_dir.name),
                name=scenario_spec.get("name", scenario_dir.name),
                metadata=metadata,
                expected_labels=expected_labels,
                scenario_spec=scenario_spec,
                video_path=video_path,
                image_path=image_path,
            )
            scenarios.append(scenario)

    return scenarios


def extract_video_frames(
    video_path: Path,
    output_dir: Path,
    num_frames: int = 5,
    format_pattern: str = "frame_%03d.jpg",
) -> list[Path]:
    """Extract frames from a video file using ffmpeg.

    Args:
        video_path: Path to the video file
        output_dir: Directory to save extracted frames
        num_frames: Number of frames to extract (evenly distributed)
        format_pattern: Pattern for output filenames

    Returns:
        List of paths to extracted frame images
    """
    if not video_path.exists():
        print(f"Warning: Video not found: {video_path}")
        return []

    output_dir.mkdir(parents=True, exist_ok=True)

    # Get video duration using ffprobe
    try:
        probe_cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video_path),
        ]
        result = subprocess.run(probe_cmd, check=False, capture_output=True, text=True, timeout=30)
        probe_data = json.loads(result.stdout)
        duration = float(probe_data["format"]["duration"])
    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError) as e:
        print(f"Warning: Failed to probe video duration: {e}")
        duration = 5.0  # Default to 5 seconds

    # Calculate frame extraction interval
    if num_frames > 1:
        interval = duration / (num_frames + 1)  # Evenly space frames
    else:
        interval = duration / 2  # Single frame from middle

    extracted_frames = []

    for i in range(num_frames):
        timestamp = interval * (i + 1)
        output_path = output_dir / format_pattern.replace("%03d", f"{i + 1:03d}")

        try:
            extract_cmd = [
                "ffmpeg",
                "-y",  # Overwrite
                "-ss",
                f"{timestamp:.2f}",
                "-i",
                str(video_path),
                "-vframes",
                "1",
                "-q:v",
                "2",  # High quality JPEG
                str(output_path),
            ]
            subprocess.run(
                extract_cmd,
                capture_output=True,
                timeout=30,
                check=True,
            )

            if output_path.exists():
                extracted_frames.append(output_path)

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            print(f"Warning: Failed to extract frame at {timestamp:.2f}s: {e}")

    return extracted_frames


def get_test_camera_for_category(category: str) -> str:
    """Map scenario category to existing test camera directory.

    Args:
        category: Scenario category (normal, suspicious, threats)

    Returns:
        Test camera folder name that exists in /export/foscam
    """
    category_to_camera = {
        "normal": "test_normal_delivery",
        "suspicious": "test_suspicious_casing",
        "threats": "test_threat_breakin",
        "cosmos": "test_normal_delivery",  # Default for cosmos scenarios
    }
    return category_to_camera.get(category, "test_normal_delivery")


def _slugify_camera_token(value: str, max_len: int = 28) -> str:
    """Create a filesystem-safe short token for camera IDs."""
    token = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    if not token:
        # nosemgrep: hardcoded-password - fallback label, not a credential
        token = "scenario"  # noqa: S105
    return token[:max_len]


def get_test_camera_for_scenario(
    scenario: SyntheticScenario,
    camera_strategy: str,
) -> str:
    """Resolve camera ID for a scenario based on strategy.

    Strategies:
      - scenario (default): one synthetic camera per scenario for clean event isolation
      - category: shared per-category test camera (legacy behavior)
    """
    if camera_strategy == "category":
        return get_test_camera_for_category(scenario.category)

    # Semantic routing first: keep scenario intent aligned with camera label
    # so timeline/event context remains coherent in demos.
    semantic_text = " ".join(
        [
            scenario.video_id or "",
            scenario.name or "",
            str(scenario.metadata.get("scenario", "")),
            str(scenario.scenario_spec.get("id", "")),
            str(scenario.scenario_spec.get("name", "")),
            str(scenario.scenario_spec.get("description", "")),
        ]
    ).lower()
    if scenario.category == "threats":
        if any(k in semantic_text for k in ["weapon", "gun", "knife", "armed", "firearm"]):
            return "test_threat_weapon"
        if any(k in semantic_text for k in ["package", "porch", "delivery theft"]):
            return "test_threat_package_theft"
        if any(k in semantic_text for k in ["break", "forced entry", "door handle", "intrud"]):
            return "test_threat_breakin"

    # Scenario-isolated mode without creating new top-level camera folders:
    # choose from pre-existing test cameras to avoid permission issues on /export/foscam.
    camera_pool_by_category: dict[str, list[str]] = {
        "normal": [
            "test_normal_delivery",
            "test_normal_pet",
            "test_normal_resident",
            "test_normal_vehicle",
        ],
        "suspicious": [
            "test_suspicious_casing",
            "test_suspicious_loitering",
        ],
        "threats": [
            "test_threat_breakin",
            "test_threat_package_theft",
            "test_threat_weapon",
        ],
    }
    pool = camera_pool_by_category.get(scenario.category, [get_test_camera_for_category("normal")])
    idx = abs(hash(scenario.video_id)) % len(pool)
    return pool[idx]


def _evaluate_reasoning_quality(
    summary: str | None,
    reasoning: str | None,
    llm_prompt: str | None,
) -> tuple[bool, list[str]]:
    """Evaluate whether reasoning content is substantial enough for demos."""
    issues: list[str] = []

    summary_text = (summary or "").strip()
    reasoning_text = (reasoning or "").strip()
    prompt_text = (llm_prompt or "").strip()
    summary_lower = summary_text.lower()
    reasoning_lower = reasoning_text.lower()

    # Generic low-value language that looks weak in demos.
    generic_markers = [
        "no threat indicators detected",
        "routine household environment",
        "normal object detections",
        "routine delivery activity with no suspicious indicators",
    ]
    if any(marker in summary_lower for marker in generic_markers):
        issues.append("Summary is generic and not scenario-specific")

    if len(summary_text) < 40:
        issues.append("Summary too short")

    if len(reasoning_text) < 140:
        issues.append("Reasoning too short")

    if len(prompt_text) < 400:
        issues.append("LLM prompt missing or too short")

    # If reasoning exists but is effectively identical to summary, it's weak signal.
    if reasoning_lower and summary_lower and reasoning_lower == summary_lower:
        issues.append("Reasoning duplicates summary")

    return len(issues) == 0, issues


_HARD_THREAT_CLASSES = {
    "gun",
    "firearm",
    "handgun",
    "pistol",
    "revolver",
    "rifle",
    "shotgun",
    "long gun",
    "knife",
    "machete",
    "crowbar",
    "pry bar",
    "bolt cutters",
}

_THREAT_REASONING_MARKERS = (
    "weapon",
    "gun",
    "knife",
    "armed",
    "firearm",
    "break-in",
    "forced entry",
    "intrusion",
    "burglary",
    "vandalism",
    "package theft",
)


def _evaluate_threat_evidence(
    *,
    expected: dict[str, Any],
    actual_classes: set[str],
    context_sources: dict[str, bool],
    enrichment_snapshot: dict[str, Any],
    combined_text: str,
    actual_score: int | None,
) -> tuple[bool, list[str]]:
    """Validate threat scenarios against concrete upstream evidence.

    For threat scenarios we require at least one strong evidence channel so
    weak/hallucinated reasoning does not pass validation.
    """
    issues: list[str] = []
    threat_expected = expected.get("threats")
    if not threat_expected:
        return True, issues

    has_threat_expected = bool(threat_expected.get("has_threat", False))
    if not has_threat_expected:
        return True, issues

    actual_lower = {c.lower() for c in actual_classes}
    expected_threat_classes = {
        str(d.get("class", "")).lower()
        for d in expected.get("detections", [])
        if str(d.get("class", "")).lower() in _HARD_THREAT_CLASSES
    }

    has_detected_threat_class = bool(actual_lower & _HARD_THREAT_CLASSES)
    has_expected_threat_class = bool(actual_lower & expected_threat_classes)

    has_threat_context = bool(
        context_sources.get("has_violence", False)
        or context_sources.get("has_threat", False)
        or enrichment_snapshot.get("threat_results")
        or enrichment_snapshot.get("violence_result")
    )

    has_high_risk_threat_reasoning = (actual_score is not None and actual_score >= 60) and any(
        marker in combined_text for marker in _THREAT_REASONING_MARKERS
    )

    if expected_threat_classes:
        # Weapon-specific scenarios must show weapon-class evidence or dedicated threat context.
        evidence_ok = has_expected_threat_class or has_threat_context
        if not evidence_ok:
            issues.append(
                "Expected weapon-threat evidence missing: no expected threat class detected and "
                "no threat/violence enrichment context available"
            )
        return evidence_ok, issues

    # Non-weapon threat scenarios can pass with strong threat context or high-risk threat reasoning.
    evidence_ok = has_detected_threat_class or has_threat_context or has_high_risk_threat_reasoning
    if not evidence_ok:
        issues.append(
            "Threat scenario missing concrete evidence: no threat class, no threat/violence context, "
            "and no high-risk threat reasoning"
        )
    return evidence_ok, issues



async def ensure_synthetic_camera(camera_name: str = "test_normal_delivery") -> Camera:
    """Ensure a synthetic camera exists in the database.

    Args:
        camera_name: Name for the synthetic camera (should be existing test camera)

    Returns:
        Camera object (existing or newly created)
    """
    async with get_session() as session:
        # Check if camera exists by ID or name (ID is the folder name)
        result = await session.execute(
            select(Camera).where((Camera.id == camera_name) | (Camera.name == camera_name))
        )
        camera = result.scalars().first()

        if camera:
            return camera

        # Create new synthetic camera using the factory method
        camera = Camera.from_folder_name(
            folder_name=camera_name,
            folder_path=f"/export/foscam/{camera_name}",
        )
        session.add(camera)
        await session.commit()
        await session.refresh(camera)

        print(f"Created synthetic camera: {camera_name} (ID: {camera.id})")
        return camera


async def _fix_selinux_context(file_path: Path) -> None:
    """Fix SELinux context for a single file so containers can read it.

    Files copied from temp directories (e.g., ffmpeg-extracted frames) inherit
    the creating process's unconfined_u SELinux user context. Podman containers
    running as appuser cannot read files with unconfined_u even when Unix
    permissions allow it. The -F flag forces restorecon to reset the context
    even when it considers it "customized by admin".
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "restorecon",
            "-F",
            str(file_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=5)
    except (TimeoutError, FileNotFoundError, OSError):
        pass  # Best-effort; batch fix at end will catch stragglers


async def seed_synthetic_scenarios(
    scenarios: list[SyntheticScenario],
    frames_per_video: int = 5,
    delay_between: float = 0.5,
    watch_folder: Path | None = None,
    camera_strategy: str = "scenario",
) -> tuple[int, list[Path]]:
    """Process synthetic scenarios through the AI pipeline.

    Extracts frames from videos, places them in the watch folder, and
    triggers the file watcher to process them through the full pipeline.

    Args:
        scenarios: List of synthetic scenarios to process
        frames_per_video: Number of frames to extract from each video
        delay_between: Delay between frame extractions (seconds)
        watch_folder: Custom watch folder (defaults to temp dir under FOSCAM_BASE_PATH)

    Returns:
        Tuple of (frames_processed, list of frame paths)
    """
    processed_frames = []
    total_extracted = 0

    # Group scenarios by category to use appropriate test cameras
    now = datetime.now()

    for i, scenario in enumerate(scenarios, 1):
        has_video = scenario.video_path and scenario.video_path.exists()
        has_image = scenario.image_path and scenario.image_path.exists()

        if not has_video and not has_image:
            print(f"  [{i}/{len(scenarios)}] Skipped: {scenario.name} (no media)")
            continue

        # Resolve camera assignment for this scenario.
        # Default is per-scenario camera isolation to reduce cross-scenario coalescing.
        camera_name = get_test_camera_for_scenario(scenario, camera_strategy)
        scenario.assigned_camera_id = camera_name
        camera = await ensure_synthetic_camera(camera_name)

        # Use existing test camera folder structure
        scenario_watch_folder = watch_folder
        if scenario_watch_folder is None:
            scenario_watch_folder = (
                Path(FOSCAM_BASE_PATH)
                / camera_name
                / str(now.year)
                / f"{now.month:02d}"
                / f"{now.day:02d}"
            )

        scenario_watch_folder.mkdir(parents=True, exist_ok=True)

        if has_video:
            # Video-based scenario: extract frames from video
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                frames = extract_video_frames(
                    scenario.video_path,
                    temp_path,
                    num_frames=frames_per_video,
                )

                if not frames:
                    print(f"  [{i}/{len(scenarios)}] Skipped: {scenario.name} (extraction failed)")
                    continue

                # Copy frames to watch folder with scenario-specific naming
                for j, frame_path in enumerate(frames, 1):
                    dest_name = f"{scenario.video_id}_{scenario.category}_frame{j:02d}.jpg"
                    dest_path = scenario_watch_folder / dest_name

                    shutil.copy2(frame_path, dest_path)
                    processed_frames.append(dest_path)
                    total_extracted += 1

                    # Fix SELinux context BEFORE touching to trigger file watcher.
                    # Files copied from temp dirs inherit unconfined_u context which
                    # is unreadable by the container's appuser. Must use -F to force
                    # reset even "customized" contexts.
                    await _fix_selinux_context(dest_path)

                    # Touch to trigger file watcher
                    dest_path.touch()
        else:
            # Image-based scenario (COCO): copy image directly to watch folder
            suffix = scenario.image_path.suffix
            dest_name = f"{scenario.video_id}_{scenario.category}_img{suffix}"
            dest_path = scenario_watch_folder / dest_name

            shutil.copy2(scenario.image_path, dest_path)
            processed_frames.append(dest_path)
            total_extracted += 1

            # Fix SELinux context BEFORE touching (same reason as above)
            await _fix_selinux_context(dest_path)

            # Touch to trigger file watcher
            dest_path.touch()

        if has_video:
            print(
                f"  [{i}/{len(scenarios)}] Extracted frames: {scenario.name} ({scenario.category})"
            )
        else:
            print(f"  [{i}/{len(scenarios)}] Copied image: {scenario.name} ({scenario.category})")

        # Small delay between scenarios (use asyncio.sleep in async context)
        if delay_between > 0 and i < len(scenarios):
            await asyncio.sleep(delay_between)

    print(f"\nProcessed {total_extracted} media files from {len(scenarios)} scenarios")

    # Safety-net SELinux fix: re-run restorecon -F on all directories in case
    # any per-file fixes above were missed. The -F flag forces reset even for
    # contexts that restorecon considers "customized by admin" (unconfined_u).
    if processed_frames:
        try:
            parent_dirs = {str(p.parent) for p in processed_frames}
            for parent_dir in parent_dirs:
                proc = await asyncio.create_subprocess_exec(
                    "restorecon",
                    "-F",
                    "-R",
                    parent_dir,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(proc.wait(), timeout=30)
            print(f"  Fixed SELinux context for {len(parent_dirs)} directories")
        except (TimeoutError, FileNotFoundError, OSError) as e:
            print(f"  Warning: Could not fix SELinux context: {e}")

    return total_extracted, processed_frames


def _is_score_reasonable_for_detected(
    actual_classes: set[str],
    actual_score: int,
    category: str,
) -> bool:
    """Check if the risk score is reasonable given what was actually detected.

    This provides a "scoring-only" validation that ignores detection accuracy.
    For example, if YOLO detected only "person" in a normal scene, a score of
    5 is reasonable even if the scenario expected "car".

    The logic uses broad, permissive ranges based on what was detected:
    - person only, in any category: 0-100 (person can be anything)
    - vehicles only: 0-40 (vehicles alone are rarely high-risk)
    - animals only: 0-20 (animals are almost never concerning)
    - person + vehicle: 0-100 (depends on context)
    - nothing detected: 0-15 (no detections = low risk)
    """
    if not actual_classes:
        return actual_score <= 15

    person_present = "person" in actual_classes
    vehicle_classes = {"car", "truck", "bus", "motorcycle", "bicycle"}
    animal_classes = {"dog", "cat", "bird", "horse", "cow", "sheep", "bear"}
    has_vehicles = bool(actual_classes & vehicle_classes)
    has_animals = bool(actual_classes & animal_classes)

    # If person is detected, almost any score could be reasonable
    if person_present:
        return True

    # Vehicles only - low to moderate risk
    if has_vehicles and not has_animals:
        return actual_score <= 50

    # Animals only - very low risk
    if has_animals and not has_vehicles:
        return actual_score <= 25

    # Mixed objects without person - moderate risk
    return actual_score <= 50


async def validate_synthetic_results(
    scenarios: list[SyntheticScenario],
    timeout_seconds: int = 30,
) -> list[ValidationResult]:
    """Validate pipeline results against expected labels.

    Compares actual events created by the pipeline against the expected
    labels defined in each scenario's expected_labels.json. Validates
    four independent accuracy dimensions:

    1. Event Matching: Was an event created and matched to this scenario?
    2. Detection Accuracy: Did YOLO detect the expected object classes?
    3. Scoring Accuracy: Is the LLM risk score in the expected range?
    4. Scoring for Detected: Is the score reasonable for what was actually
       detected (regardless of whether detection matched expectations)?
    5. Enrichment Coverage: Did enrichment models provide data?

    The overall "success" requires all dimensions to pass, but each is
    tracked independently so the report can show where failures occur.

    Args:
        scenarios: List of scenarios that were processed
        timeout_seconds: How long to wait for events to appear

    Returns:
        List of ValidationResult objects
    """

    results = []

    async with get_session() as session:
        # Pre-fetch all recent events and their detections once, instead of
        # re-querying per scenario. This also allows better matching.
        from sqlalchemy.orm import undefer

        cutoff = datetime.now(UTC) - timedelta(hours=1)
        result = await session.execute(
            select(Event)
            .options(undefer(Event.reasoning), undefer(Event.llm_prompt))
            .where(Event.started_at >= cutoff)
            .where(Event.deleted_at.is_(None))
            .order_by(Event.started_at.desc())
            .limit(500)
        )
        all_recent_events = list(result.scalars().all())

        # Pre-fetch detections for all events
        event_detection_map: dict[uuid.UUID, list[Detection]] = {}
        for event in all_recent_events:
            det_result = await session.execute(
                select(Detection)
                .join(EventDetection, EventDetection.detection_id == Detection.id)
                .where(EventDetection.event_id == event.id)
            )
            event_detection_map[event.id] = list(det_result.scalars().all())

        # Pre-fetch LLMInteractions for all events
        llm_interaction_map: dict[uuid.UUID, LLMInteraction | None] = {}
        for event in all_recent_events:
            llm_int_result = await session.execute(
                select(LLMInteraction).where(LLMInteraction.event_id == event.id)
            )
            llm_interaction_map[event.id] = llm_int_result.scalars().first()

        # Track which events have been used, to avoid reusing them
        used_event_ids: set[uuid.UUID] = set()

        for scenario in scenarios:
            expected = scenario.expected_labels
            if not expected:
                results.append(
                    ValidationResult(
                        scenario=scenario,
                        success=False,
                        errors=["No expected labels defined"],
                    )
                )
                continue

            # --- Improved event matching ---
            # Match events to scenarios using the camera that the scenario
            # was placed into, then by risk level, then by detection overlap.
            # This avoids all scenarios matching the same single event.
            expected_camera = scenario.assigned_camera_id or get_test_camera_for_category(
                scenario.category
            )
            expected_risk_level = expected.get("risk", {}).get("level")
            expected_det_classes = {d.get("class", "") for d in expected.get("detections", [])}

            matched_event = None
            best_score = -1

            for event in all_recent_events:
                if event.id in used_event_ids:
                    continue

                score = 0

                # Camera match (strongest signal)
                if event.camera_id and expected_camera in str(event.camera_id):
                    score += 10

                # Risk level match
                if event.risk_level == expected_risk_level:
                    score += 5

                # Detection class overlap
                event_dets = event_detection_map.get(event.id, [])
                event_classes = {d.object_type for d in event_dets if d.object_type}
                # Expand expected classes through COCO aliases
                expanded_expected = set()
                for ec in expected_det_classes:
                    expanded_expected.add(ec)
                    if ec in COCO_CLASS_ALIASES:
                        expanded_expected.update(COCO_CLASS_ALIASES[ec])
                overlap = len(event_classes & expanded_expected)
                score += overlap * 2

                if score > best_score:
                    best_score = score
                    matched_event = event

            # If no events exist at all for this camera, try any unmatched event
            if matched_event is None:
                for event in all_recent_events:
                    if event.id not in used_event_ids:
                        matched_event = event
                        break

            if not matched_event:
                results.append(
                    ValidationResult(
                        scenario=scenario,
                        success=False,
                        event_matched=False,
                        errors=[f"No matching event found for {scenario.video_id}"],
                        expected_classes=list(expected_det_classes),
                    )
                )
                continue

            # Mark event as used so other scenarios don't reuse it
            used_event_ids.add(matched_event.id)

            # Validate risk score range (Nemotron)
            errors = []
            detection_errors_list: list[str] = []
            scoring_errors_list: list[str] = []
            enrichment_results = {}
            enrichment_errors = []
            risk_config = expected.get("risk", {})
            expected_range = (risk_config.get("min_score", 0), risk_config.get("max_score", 100))
            actual_score = matched_event.risk_score or 0

            risk_valid = expected_range[0] <= actual_score <= expected_range[1]
            if not risk_valid:
                scoring_errors_list.append(
                    f"Risk score {actual_score} outside expected range {expected_range}"
                )

            # Get detections for this event (already pre-fetched)
            event_detections = event_detection_map.get(matched_event.id, [])
            detection_ids = [d.id for d in event_detections]

            # --- Detection class validation (YOLO26) ---
            # Uses COCO_CLASS_ALIASES so abstract names like "vehicle" match
            # any of the COCO equivalents (car, truck, bus, motorcycle).
            detection_matches = {}
            actual_classes = {d.object_type for d in event_detections if d.object_type}
            for det_spec in expected.get("detections", []):
                det_class = det_spec.get("class", "unknown")
                min_conf = det_spec.get("min_confidence", 0)

                # Build the set of acceptable COCO class names for this expected class
                acceptable_classes = {det_class}
                if det_class in COCO_CLASS_ALIASES:
                    acceptable_classes = set(COCO_CLASS_ALIASES[det_class])

                # Check if any acceptable class was detected
                matched_classes = acceptable_classes & actual_classes
                class_found = len(matched_classes) > 0

                if class_found and min_conf > 0:
                    # Validate confidence across all matching COCO classes
                    class_dets = [d for d in event_detections if d.object_type in matched_classes]
                    max_confidence = max((d.confidence or 0 for d in class_dets), default=0)
                    class_found = max_confidence >= min_conf
                    if not class_found:
                        detection_errors_list.append(
                            f"Detection '{det_class}' (matched: {matched_classes}) "
                            f"confidence {max_confidence:.2f} below threshold {min_conf}"
                        )
                elif not class_found:
                    if det_class in COCO_CLASS_ALIASES:
                        detection_errors_list.append(
                            f"Expected detection class '{det_class}' "
                            f"(accepts: {COCO_CLASS_ALIASES[det_class]}) not found "
                            f"in actual classes {actual_classes}"
                        )
                    else:
                        detection_errors_list.append(
                            f"Expected detection class '{det_class}' not found "
                            f"in actual classes {actual_classes}"
                        )
                detection_matches[det_class] = class_found

            # Determine if detection was correct (all expected classes found)
            detection_correct = all(detection_matches.values()) if detection_matches else True

            # Determine if score is reasonable for what was actually detected
            scoring_for_detected = _is_score_reasonable_for_detected(
                actual_classes, actual_score, scenario.category
            )

            # =================================================================
            # ENRICHMENT VALIDATION (via LLMInteraction + Event fields)
            # =================================================================
            # The real-time pipeline generates enrichment data in-memory for
            # the Nemotron prompt -- it does NOT necessarily persist to
            # per-detection DB tables (PoseResult, ActionResult, etc.).
            # Phase 3 seeding creates synthetic records there, but the
            # pipeline's own enrichment is transient.
            #
            # Instead we validate enrichment evidence from:
            #  1. LLMInteraction.context_sources  (which enrichment was available)
            #  2. LLMInteraction.enrichment_snapshot (frozen enrichment data)
            #  3. Event.summary / Event.reasoning (does LLM mention signals?)
            #  4. Event.llm_prompt (does the prompt contain enrichment sections?)
            # =================================================================

            # Load LLMInteraction for this event (already pre-fetched)
            llm_interaction = llm_interaction_map.get(matched_event.id)

            # Combine text fields for keyword searching
            llm_prompt_text = (matched_event.llm_prompt or "").lower()
            summary_text = (matched_event.summary or "").lower()
            reasoning_text = (matched_event.reasoning or "").lower()
            combined_text = f"{summary_text} {reasoning_text} {llm_prompt_text}"

            # Extract context_sources from LLMInteraction (if available)
            context_sources: dict[str, bool] = {}
            enrichment_snapshot: dict[str, Any] = {}
            if llm_interaction:
                context_sources = llm_interaction.context_sources or {}
                enrichment_snapshot = llm_interaction.enrichment_snapshot or {}

            # --- Enrichment: Pose validation ---
            pose_expected = expected.get("pose")
            if pose_expected:
                # Check if pose data was available in the LLM context
                has_pose_context = context_sources.get("has_pose", False)
                pose_in_prompt = "pose" in llm_prompt_text or "posture" in llm_prompt_text
                pose_in_snapshot = "pose_results" in enrichment_snapshot

                pose_ok = has_pose_context or pose_in_prompt or pose_in_snapshot
                enrichment_results["pose"] = pose_ok
                if not pose_ok:
                    enrichment_errors.append(
                        "No pose enrichment evidence in LLM context "
                        "(context_sources.has_pose=False, no pose in prompt or snapshot)"
                    )

            # --- Enrichment: Threat evidence quality ---
            threat_ok, threat_issues = _evaluate_threat_evidence(
                expected=expected,
                actual_classes=actual_classes,
                context_sources=context_sources,
                enrichment_snapshot=enrichment_snapshot,
                combined_text=combined_text,
                actual_score=actual_score,
            )
            if "threats" in expected:
                enrichment_results["threat"] = threat_ok
                enrichment_errors.extend(threat_issues)

            # --- Enrichment: Re-ID context ---
            if event_detections:
                person_dets = [d for d in event_detections if d.object_type == "person"]
                if person_dets:
                    has_reid_context = context_sources.get("has_person_reid", False)
                    reid_in_prompt = "re-id" in llm_prompt_text or "reid" in llm_prompt_text
                    reid_in_snapshot = bool(enrichment_snapshot.get("person_reid_matches"))

                    has_reid = has_reid_context or reid_in_prompt or reid_in_snapshot
                    enrichment_results["reid"] = has_reid
                    if not has_reid:
                        enrichment_errors.append(
                            "No re-ID enrichment evidence in LLM context "
                            "(context_sources.has_person_reid=False)"
                        )

            # --- Enrichment: Action recognition ---
            action_expected = expected.get("action")
            if action_expected:
                has_action_context = context_sources.get("has_action", False)
                action_in_prompt = "action" in llm_prompt_text
                action_in_snapshot = "action_results" in enrichment_snapshot

                action_ok = has_action_context or action_in_prompt or action_in_snapshot
                enrichment_results["action"] = action_ok
                if not action_ok:
                    enrichment_errors.append(
                        "No action enrichment evidence in LLM context "
                        "(context_sources.has_action=False, no action in prompt or snapshot)"
                    )

            # --- Enrichment: Demographics / Face ---
            face_expected = expected.get("face")
            if face_expected and face_expected.get("detected"):
                has_faces_context = context_sources.get("has_faces", False)
                face_in_prompt = "face" in llm_prompt_text or "demographic" in llm_prompt_text
                faces_in_snapshot = bool(enrichment_snapshot.get("faces"))

                enrichment_results["demographics"] = (
                    has_faces_context or face_in_prompt or faces_in_snapshot
                )
                if not enrichment_results["demographics"]:
                    enrichment_errors.append(
                        "Face expected but no face/demographics enrichment evidence in LLM context"
                    )

            # --- Florence caption validation ---
            # Check event summary for expected keywords (Florence captions
            # contribute to the LLM summary, not stored separately)
            caption_expected = expected.get("florence_caption")
            if caption_expected and matched_event.summary:
                caption_ok = True

                must_contain = caption_expected.get("must_contain", [])
                for keyword in must_contain:
                    if keyword.lower() not in summary_text:
                        caption_ok = False
                        enrichment_errors.append(f"Florence caption missing keyword '{keyword}'")

                must_not_contain = caption_expected.get("must_not_contain", [])
                for keyword in must_not_contain:
                    if keyword.lower() in summary_text:
                        caption_ok = False
                        enrichment_errors.append(
                            f"Florence caption contains unwanted keyword '{keyword}'"
                        )

                enrichment_results["florence"] = caption_ok

            # --- Enrichment quality metrics (Fix #6) ---
            # Extract which prompt template was used, prompt size, and
            # which enrichment sections were present in the prompt.
            prompt_template_used: str | None = None
            prompt_length: int | None = None
            enrichment_sections_present: list[str] = []
            llm_latency_ms: float | None = None

            if llm_interaction:
                # Determine template from context_sources
                cs = llm_interaction.context_sources or {}
                enrichment_available = cs.get("enrichment_available", False)
                context_available = cs.get("context_available", False)
                if enrichment_available and context_available:
                    # Check for model_zoo indicators
                    has_vision = cs.get("has_vision_extraction", False)
                    has_pose = cs.get("has_pose", False)
                    has_action = cs.get("has_action", False)
                    if has_vision or has_pose or has_action:
                        prompt_template_used = "model_zoo"
                    elif cs.get("has_faces", False) or cs.get("has_license_plates", False):
                        prompt_template_used = "full_enriched"
                    else:
                        prompt_template_used = "enriched"
                else:
                    prompt_template_used = "basic"

                # Prompt length from the event's stored prompt
                if matched_event.llm_prompt:
                    prompt_length = len(matched_event.llm_prompt)

                # Which enrichment sections were populated
                for src_key, src_val in cs.items():
                    if src_key.startswith("has_") and src_val:
                        enrichment_sections_present.append(src_key)

                # LLM latency from the LLMInteraction created_at vs event ended_at
                if llm_interaction.created_at and matched_event.ended_at:
                    delta = (llm_interaction.created_at - matched_event.ended_at).total_seconds()
                    if delta > 0:
                        llm_latency_ms = delta * 1000

            # --- Reasoning quality validation ---
            reasoning_quality_ok, reasoning_errors = _evaluate_reasoning_quality(
                matched_event.summary,
                matched_event.reasoning,
                matched_event.llm_prompt,
            )

            # Combine all errors for backward-compatible 'errors' field
            all_errors = (
                detection_errors_list + scoring_errors_list + enrichment_errors + reasoning_errors
            )

            # End-to-end success requires all dimensions to pass
            end_to_end_success = (
                detection_correct
                and risk_valid
                and len(enrichment_errors) == 0
                and reasoning_quality_ok
            )

            results.append(
                ValidationResult(
                    scenario=scenario,
                    success=end_to_end_success,
                    event_id=matched_event.id,
                    actual_risk_score=actual_score,
                    expected_risk_range=expected_range,
                    detection_matches=detection_matches,
                    enrichment_results=enrichment_results,
                    enrichment_errors=enrichment_errors,
                    errors=all_errors,
                    prompt_template=prompt_template_used,
                    prompt_length=prompt_length,
                    enrichment_sections_present=enrichment_sections_present,
                    llm_latency_ms=llm_latency_ms,
                    # Separated accuracy dimensions
                    event_matched=True,
                    detection_correct=detection_correct,
                    scoring_correct=risk_valid,
                    scoring_for_detected=scoring_for_detected,
                    reasoning_quality_ok=reasoning_quality_ok,
                    actual_classes=actual_classes,
                    expected_classes=[
                        d.get("class", "unknown") for d in expected.get("detections", [])
                    ],
                    detection_errors=detection_errors_list,
                    scoring_errors=scoring_errors_list,
                    reasoning_errors=reasoning_errors,
                    camera_name=str(matched_event.camera_id) if matched_event.camera_id else None,
                )
            )

    return results


def _find_weak_reasoning_results(results: list[ValidationResult]) -> list[ValidationResult]:
    """Identify scenarios that should be retried with alternate synthetic events."""
    weak: list[ValidationResult] = []
    for result in results:
        if not result.success:
            weak.append(result)
            continue
        if not result.event_matched:
            weak.append(result)
            continue
        if not result.scoring_correct:
            weak.append(result)
            continue
        if not result.reasoning_quality_ok:
            weak.append(result)
    return weak


def _select_retry_scenarios(
    all_available: list[SyntheticScenario],
    weak_results: list[ValidationResult],
    used_video_ids: set[str],
    max_per_category: int = 2,
) -> list[SyntheticScenario]:
    """Pick alternate scenarios from the same categories as weak results."""
    by_category_needed: dict[str, int] = {}
    for result in weak_results:
        cat = result.scenario.category
        by_category_needed[cat] = by_category_needed.get(cat, 0) + 1

    selected: list[SyntheticScenario] = []
    selected_ids: set[str] = set()
    for category, needed in sorted(by_category_needed.items()):
        budget = min(max_per_category, needed)
        candidates = [
            s
            for s in all_available
            if s.category == category
            and s.video_id not in used_video_ids
            and s.video_id not in selected_ids
            and (
                (s.video_path and s.video_path.exists()) or (s.image_path and s.image_path.exists())
            )
        ]
        if not candidates:
            continue
        random.shuffle(candidates)
        picks = candidates[:budget]
        selected.extend(picks)
        selected_ids.update(s.video_id for s in picks)

    return selected


def generate_validation_report(
    results: list[ValidationResult],
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Generate a validation report from synthetic scenario results.

    The report separates accuracy into independent dimensions:
    - Event Matching: How many scenarios had events created?
    - Detection Accuracy: Of matched events, how many had correct YOLO classes?
    - Scoring Accuracy: Of matched events, how many had risk scores in range?
    - Scoring for Detected: Of matched events, how many had reasonable scores
      for what was actually detected (ignoring detection class mismatches)?
    - Enrichment Coverage: Did enrichment models provide data?
    - End-to-End Accuracy: All dimensions correct simultaneously.

    Args:
        results: List of validation results
        output_path: Optional path to save JSON report

    Returns:
        Report dictionary with summary statistics
    """
    total = len(results)
    passed = sum(1 for r in results if r.success)
    failed = total - passed

    # --- Separated accuracy dimensions ---
    events_matched = sum(1 for r in results if r.event_matched)
    matched_results = [r for r in results if r.event_matched]

    detection_correct = sum(1 for r in matched_results if r.detection_correct)
    scoring_correct = sum(1 for r in matched_results if r.scoring_correct)
    scoring_for_detected = sum(1 for r in matched_results if r.scoring_for_detected)
    enrichment_all_pass = sum(
        1 for r in matched_results if r.enrichment_results and all(r.enrichment_results.values())
    )

    accuracy_dimensions = {
        "event_matching": {
            "matched": events_matched,
            "total": total,
            "rate": f"{(events_matched / total * 100):.1f}%" if total > 0 else "N/A",
            "description": "Scenarios that produced at least one pipeline event",
        },
        "detection_accuracy": {
            "correct": detection_correct,
            "total": len(matched_results),
            "rate": f"{(detection_correct / len(matched_results) * 100):.1f}%"
            if matched_results
            else "N/A",
            "description": "YOLO detected the expected object classes",
        },
        "scoring_accuracy": {
            "correct": scoring_correct,
            "total": len(matched_results),
            "rate": f"{(scoring_correct / len(matched_results) * 100):.1f}%"
            if matched_results
            else "N/A",
            "description": "LLM risk score within expected range (for expected detections)",
        },
        "scoring_for_detected": {
            "correct": scoring_for_detected,
            "total": len(matched_results),
            "rate": f"{(scoring_for_detected / len(matched_results) * 100):.1f}%"
            if matched_results
            else "N/A",
            "description": "LLM risk score reasonable for what YOLO actually detected",
        },
        "enrichment_coverage": {
            "all_pass": enrichment_all_pass,
            "total": len(matched_results),
            "rate": f"{(enrichment_all_pass / len(matched_results) * 100):.1f}%"
            if matched_results
            else "N/A",
            "description": "All expected enrichment models provided data",
        },
        "end_to_end": {
            "passed": passed,
            "total": total,
            "rate": f"{(passed / total * 100):.1f}%" if total > 0 else "N/A",
            "description": "Correct detection + correct score + enrichment (all dimensions)",
        },
    }

    # --- Per-category accuracy breakdown ---
    by_category: dict[str, dict[str, Any]] = {}
    for result in results:
        cat = result.scenario.category
        if cat not in by_category:
            by_category[cat] = {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "events_matched": 0,
                "detection_correct": 0,
                "scoring_correct": 0,
                "scoring_for_detected": 0,
            }
        by_category[cat]["total"] += 1
        if result.success:
            by_category[cat]["passed"] += 1
        else:
            by_category[cat]["failed"] += 1
        if result.event_matched:
            by_category[cat]["events_matched"] += 1
            if result.detection_correct:
                by_category[cat]["detection_correct"] += 1
            if result.scoring_correct:
                by_category[cat]["scoring_correct"] += 1
            if result.scoring_for_detected:
                by_category[cat]["scoring_for_detected"] += 1

    # --- Camera distribution ---
    camera_counts: dict[str, int] = {}
    for result in matched_results:
        cam = result.camera_name or "unknown"
        camera_counts[cam] = camera_counts.get(cam, 0) + 1

    # Risk score calibration
    risk_calibration = []
    for result in results:
        if result.actual_risk_score is not None and result.expected_risk_range:
            risk_calibration.append(
                {
                    "scenario": result.scenario.video_id,
                    "category": result.scenario.category,
                    "actual": result.actual_risk_score,
                    "expected_min": result.expected_risk_range[0],
                    "expected_max": result.expected_risk_range[1],
                    "in_range": result.expected_risk_range[0]
                    <= result.actual_risk_score
                    <= result.expected_risk_range[1],
                    "actual_classes": sorted(result.actual_classes)
                    if result.actual_classes
                    else [],
                    "expected_classes": result.expected_classes,
                    "scoring_for_detected": result.scoring_for_detected,
                }
            )

    # Enrichment accuracy by service
    enrichment_services = ["pose", "threat", "reid", "action", "demographics", "florence"]
    by_service: dict[str, dict[str, int]] = {}
    for svc in enrichment_services:
        tested = sum(1 for r in results if svc in r.enrichment_results)
        svc_passed = sum(1 for r in results if r.enrichment_results.get(svc, False))
        if tested > 0:
            by_service[svc] = {
                "tested": tested,
                "passed": svc_passed,
                "failed": tested - svc_passed,
            }

    # --- Detection class mismatch analysis ---
    # Show which expected classes were most commonly missed
    missed_class_counts: dict[str, int] = {}
    detected_class_counts: dict[str, int] = {}
    for result in matched_results:
        for cls_name, matched in result.detection_matches.items():
            if not matched:
                missed_class_counts[cls_name] = missed_class_counts.get(cls_name, 0) + 1
        for cls in result.actual_classes:
            detected_class_counts[cls] = detected_class_counts.get(cls, 0) + 1

    detection_analysis = {
        "most_missed_classes": dict(sorted(missed_class_counts.items(), key=lambda x: -x[1])[:10]),
        "most_detected_classes": dict(
            sorted(detected_class_counts.items(), key=lambda x: -x[1])[:10]
        ),
    }

    # Failed scenarios details (include separated error types)
    failures = []
    for result in results:
        if not result.success:
            failure_entry: dict[str, Any] = {
                "scenario": result.scenario.video_id,
                "name": result.scenario.name,
                "category": result.scenario.category,
                "event_matched": result.event_matched,
                "errors": result.errors,
                "enrichment_errors": result.enrichment_errors,
            }
            if result.event_matched:
                failure_entry["detection_correct"] = result.detection_correct
                failure_entry["scoring_correct"] = result.scoring_correct
                failure_entry["scoring_for_detected"] = result.scoring_for_detected
                failure_entry["actual_classes"] = sorted(result.actual_classes)
                failure_entry["expected_classes"] = result.expected_classes
                failure_entry["detection_errors"] = result.detection_errors
                failure_entry["scoring_errors"] = result.scoring_errors
                failure_entry["camera"] = result.camera_name
            failures.append(failure_entry)

    # =================================================================
    # Enrichment quality metrics (Fix #6)
    # =================================================================
    # Collect prompt template distribution, average prompt size,
    # enrichment section coverage, and LLM inference latency.
    template_counts: dict[str, int] = {}
    prompt_lengths: list[int] = []
    section_counts: dict[str, int] = {}
    latencies: list[float] = []

    for result in results:
        if result.prompt_template:
            template_counts[result.prompt_template] = (
                template_counts.get(result.prompt_template, 0) + 1
            )
        if result.prompt_length is not None:
            prompt_lengths.append(result.prompt_length)
        for section in result.enrichment_sections_present:
            section_counts[section] = section_counts.get(section, 0) + 1
        if result.llm_latency_ms is not None:
            latencies.append(result.llm_latency_ms)

    enrichment_quality: dict[str, Any] = {
        "prompt_template_distribution": template_counts,
        "prompt_size": {
            "count": len(prompt_lengths),
            "avg_chars": int(sum(prompt_lengths) / len(prompt_lengths)) if prompt_lengths else 0,
            "min_chars": min(prompt_lengths) if prompt_lengths else 0,
            "max_chars": max(prompt_lengths) if prompt_lengths else 0,
            "estimated_avg_tokens": int(sum(prompt_lengths) / len(prompt_lengths) / 4)
            if prompt_lengths
            else 0,
        },
        "enrichment_sections_coverage": {
            section: {
                "count": count,
                "pct": f"{count / total * 100:.1f}%" if total > 0 else "N/A",
            }
            for section, count in sorted(section_counts.items(), key=lambda x: -x[1])
        },
        "llm_latency_ms": {
            "count": len(latencies),
            "avg": round(sum(latencies) / len(latencies), 1) if latencies else 0,
            "min": round(min(latencies), 1) if latencies else 0,
            "max": round(max(latencies), 1) if latencies else 0,
            "p50": round(sorted(latencies)[len(latencies) // 2], 1) if latencies else 0,
        },
    }

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {
            "total_scenarios": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{(passed / total * 100):.1f}%" if total > 0 else "N/A",
        },
        "accuracy_dimensions": accuracy_dimensions,
        "by_category": by_category,
        "camera_distribution": camera_counts,
        "detection_analysis": detection_analysis,
        "enrichment_accuracy": by_service,
        "enrichment_quality": enrichment_quality,
        "risk_calibration": risk_calibration,
        "failures": failures,
    }

    if output_path:
        # Use safe write to validate path is within SYNTHETIC_DATA_PATH or PROJECT_ROOT
        if _safe_write_json(output_path, report, _PROJECT_ROOT):
            print(f"\nValidation report saved to: {output_path}")
        else:
            print(f"\nWarning: Could not save validation report to {output_path}")

    return report


def print_validation_summary(report: dict[str, Any]) -> None:
    """Print a formatted validation summary to stdout.

    Displays separated accuracy dimensions so that detection accuracy,
    scoring accuracy, and enrichment coverage are independently visible.
    This prevents detection issues (e.g., YOLO model problems) from
    obscuring LLM scoring accuracy.
    """
    summary = report.get("summary", {})

    print("\n" + "=" * 60)
    print("SYNTHETIC DATA VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total scenarios: {summary.get('total_scenarios', 0)}")

    # --- Accuracy Dimensions (the key improvement) ---
    dims = report.get("accuracy_dimensions", {})
    if dims:
        print("\n" + "-" * 60)
        print("ACCURACY BY DIMENSION")
        print("-" * 60)
        dim_order = [
            "event_matching",
            "detection_accuracy",
            "scoring_accuracy",
            "scoring_for_detected",
            "enrichment_coverage",
            "end_to_end",
        ]
        dim_labels = {
            "event_matching": "Event Matching",
            "detection_accuracy": "Detection Accuracy (YOLO)",
            "scoring_accuracy": "Scoring Accuracy (LLM)",
            "scoring_for_detected": "Scoring for Detected",
            "enrichment_coverage": "Enrichment Coverage",
            "end_to_end": "End-to-End (all correct)",
        }
        for dim_key in dim_order:
            dim = dims.get(dim_key, {})
            if not dim:
                continue
            label = dim_labels.get(dim_key, dim_key)
            # Use the correct numerator key (different dims use different names)
            numerator = dim.get(
                "correct", dim.get("matched", dim.get("passed", dim.get("all_pass", 0)))
            )
            denominator = dim.get("total", 0)
            rate = dim.get("rate", "N/A")
            desc = dim.get("description", "")
            print(f"  {label + ':':<32} {numerator:>4}/{denominator:<4} ({rate})")
            if dim_key == "scoring_for_detected":
                print(f"    ^-- {desc}")
        print()

    # --- Per-category breakdown with separated dimensions ---
    print("-" * 60)
    print("BY CATEGORY")
    print("-" * 60)
    for category, stats in report.get("by_category", {}).items():
        total_cat = stats.get("total", 0)
        matched = stats.get("events_matched", 0)
        det_ok = stats.get("detection_correct", 0)
        score_ok = stats.get("scoring_correct", 0)
        score_det = stats.get("scoring_for_detected", 0)
        e2e = stats.get("passed", 0)

        print(f"  {category}:")
        print(f"    Events matched:      {matched}/{total_cat}")
        if matched > 0:
            print(f"    Detection correct:   {det_ok}/{matched}")
            print(f"    Scoring correct:     {score_ok}/{matched}")
            print(f"    Scoring for detected:{score_det}/{matched}")
        print(f"    End-to-end:          {e2e}/{total_cat}")

    # --- Camera distribution ---
    camera_dist = report.get("camera_distribution", {})
    if camera_dist:
        print(f"\n{'-' * 60}")
        print("CAMERA DISTRIBUTION")
        print(f"{'-' * 60}")
        for cam, count in sorted(camera_dist.items(), key=lambda x: -x[1]):
            print(f"  {cam}: {count} events")
        if len(camera_dist) == 1:
            print("  WARNING: Only 1 camera producing events.")
            print("  Check that frames are being placed in the correct")
            print("  camera directories for each category.")

    # --- Detection analysis ---
    det_analysis = report.get("detection_analysis", {})
    if det_analysis:
        missed = det_analysis.get("most_missed_classes", {})
        detected = det_analysis.get("most_detected_classes", {})
        if missed:
            print(f"\n{'-' * 60}")
            print("DETECTION ANALYSIS")
            print(f"{'-' * 60}")
            print("  Most commonly missed expected classes:")
            for cls, count in list(missed.items())[:5]:
                print(f"    - {cls}: missed {count} times")
            if detected:
                print("  Most commonly detected classes:")
                for cls, count in list(detected.items())[:5]:
                    print(f"    - {cls}: detected {count} times")

    # Enrichment accuracy by service
    enrichment = report.get("enrichment_accuracy", {})
    if enrichment:
        print(f"\n{'-' * 60}")
        print("ENRICHMENT SERVICE ACCURACY")
        print(f"{'-' * 60}")
        print(f"  {'Service':<15} {'Tested':>7} {'Passed':>7} {'Failed':>7} {'Rate':>8}")
        print(f"  {'-' * 46}")
        for svc, stats in enrichment.items():
            rate = (
                f"{(stats['passed'] / stats['tested'] * 100):.1f}%"
                if stats["tested"] > 0
                else "N/A"
            )
            print(
                f"  {svc:<15} {stats['tested']:>7} {stats['passed']:>7} {stats['failed']:>7} {rate:>8}"
            )

    # Enrichment quality metrics (Fix #6)
    eq = report.get("enrichment_quality", {})
    if eq:
        print(f"\n{'-' * 60}")
        print("ENRICHMENT QUALITY METRICS")
        print(f"{'-' * 60}")

        # Prompt template distribution
        templates = eq.get("prompt_template_distribution", {})
        if templates:
            print("  Prompt templates used:")
            for tpl, count in sorted(templates.items(), key=lambda x: -x[1]):
                print(f"    - {tpl}: {count}")

        # Prompt size
        ps = eq.get("prompt_size", {})
        if ps.get("count", 0) > 0:
            print(
                f"  Prompt size: avg {ps['avg_chars']} chars "
                f"(~{ps['estimated_avg_tokens']} tokens), "
                f"min {ps['min_chars']}, max {ps['max_chars']}"
            )

        # Enrichment sections coverage
        sections = eq.get("enrichment_sections_coverage", {})
        if sections:
            print("  Enrichment sections present:")
            for section, info in list(sections.items())[:10]:
                print(f"    - {section}: {info['count']} events ({info['pct']})")

        # LLM latency
        lat = eq.get("llm_latency_ms", {})
        if lat.get("count", 0) > 0:
            print(
                f"  LLM latency: avg {lat['avg']}ms, "
                f"p50 {lat['p50']}ms, min {lat['min']}ms, max {lat['max']}ms"
            )

    # --- Failure summary ---
    failures = report.get("failures", [])
    if failures:
        # Categorize failures by type
        no_event = [f for f in failures if not f.get("event_matched", False)]
        det_only = [
            f
            for f in failures
            if f.get("event_matched")
            and not f.get("detection_correct", True)
            and f.get("scoring_correct", True)
        ]
        score_only = [
            f
            for f in failures
            if f.get("event_matched")
            and f.get("detection_correct", True)
            and not f.get("scoring_correct", True)
        ]
        both_fail = [
            f
            for f in failures
            if f.get("event_matched")
            and not f.get("detection_correct", True)
            and not f.get("scoring_correct", True)
        ]
        enrich_only = [
            f
            for f in failures
            if f.get("event_matched")
            and f.get("detection_correct", True)
            and f.get("scoring_correct", True)
        ]

        print(f"\n{'-' * 60}")
        print(f"FAILURE BREAKDOWN ({len(failures)} total)")
        print(f"{'-' * 60}")
        if no_event:
            print(f"  No event created:              {len(no_event)}")
        if det_only:
            print(f"  Detection mismatch only:       {len(det_only)}")
        if score_only:
            print(f"  Scoring mismatch only:         {len(score_only)}")
        if both_fail:
            print(f"  Detection + scoring mismatch:  {len(both_fail)}")
        if enrich_only:
            print(f"  Enrichment-only failures:      {len(enrich_only)}")

        # Show sample failures from each type
        for label, group in [
            ("No event created", no_event),
            ("Detection mismatch", det_only + both_fail),
            ("Scoring mismatch", score_only),
            ("Enrichment failures", enrich_only),
        ]:
            if group:
                print(f"\n  Sample {label} failures:")
                for fail in group[:3]:
                    errors = fail.get("errors", []) + fail.get("enrichment_errors", [])
                    print(f"    - {fail['scenario']}: {', '.join(errors[:2])}")
                if len(group) > 3:
                    print(f"    ... and {len(group) - 3} more")


async def wait_for_pipeline_completion(
    initial_event_count: int,
    expected_min_events: int = 5,
    timeout_seconds: int = 300,
    poll_interval: float = 5.0,
    expected_camera_ids: set[str] | None = None,
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
        expected_camera_ids: Optional set of camera IDs expected to produce events.
            When provided, wait logic requires event coverage across these cameras
            and avoids idle-exit while unlinked detections are still pending.

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
    last_unlinked_count: int | None = None
    last_unlinked_change_time = start_time

    while True:
        elapsed = time.time() - start_time
        time_since_last_change = time.time() - last_change_time

        # Get current event count
        events = await get_events()
        current_count = len(events)
        new_events = current_count - initial_event_count

        cameras_with_events: set[str] = set()
        pending_unlinked_detections = 0
        if expected_camera_ids:
            async with get_session() as session:
                camera_event_rows = await session.execute(
                    select(Event.camera_id, func.count())
                    .where(Event.deleted_at.is_(None))
                    .where(Event.camera_id.in_(sorted(expected_camera_ids)))
                    .group_by(Event.camera_id)
                )
                cameras_with_events = {camera_id for camera_id, _count in camera_event_rows}

                # Detections not yet linked to any event for expected cameras.
                # These are a stronger signal than event-count idle when batches are still draining.
                unlinked_rows = await session.execute(
                    select(func.count())
                    .select_from(Detection)
                    .outerjoin(
                        EventDetection,
                        EventDetection.detection_id == Detection.id,
                    )
                    .where(Detection.camera_id.in_(sorted(expected_camera_ids)))
                    .where(EventDetection.event_id.is_(None))
                )
                pending_unlinked_detections = int(unlinked_rows.scalar() or 0)

            if pending_unlinked_detections != last_unlinked_count:
                last_unlinked_count = pending_unlinked_detections
                last_unlinked_change_time = time.time()

        camera_coverage_ok = not expected_camera_ids or expected_camera_ids.issubset(
            cameras_with_events
        )
        missing_cameras = (
            sorted(expected_camera_ids - cameras_with_events) if expected_camera_ids else []
        )

        # Check if new events were created
        if current_count > last_count:
            last_change_time = time.time()
            print(f"  [{elapsed:.0f}s] Events: {current_count} (+{current_count - last_count} new)")
            last_count = current_count

        # Success condition: got enough events
        if new_events >= expected_min_events and camera_coverage_ok:
            print("\n✓ Pipeline completed successfully!")
            print(f"  Created {new_events} new events in {elapsed:.0f} seconds")
            return current_count, new_events, True

        # Timeout condition
        if elapsed >= timeout_seconds:
            print(f"\n⚠ Timeout reached after {timeout_seconds}s")
            print(f"  Created {new_events} events (expected at least {expected_min_events})")
            if expected_camera_ids:
                print(f"  Missing cameras with events: {', '.join(missing_cameras) or 'none'}")
                print(f"  Unlinked detections remaining: {pending_unlinked_detections}")
            return current_count, new_events, new_events > 0 and camera_coverage_ok

        # Idle condition: no new events for a while after some were created
        if new_events > 0 and time_since_last_change >= idle_timeout:
            # Resilient default: do not declare idle complete while expected cameras
            # are still missing or detections remain unlinked.
            unlinked_stalled = (
                expected_camera_ids
                and pending_unlinked_detections > 0
                and (time.time() - last_unlinked_change_time) >= idle_timeout
            )
            if expected_camera_ids and (not camera_coverage_ok or pending_unlinked_detections > 0):
                if camera_coverage_ok and unlinked_stalled:
                    print(
                        "\n⚠ Pipeline unlinked detections appear stalled; "
                        "continuing to next stage with partial linkage"
                    )
                    print(
                        f"  Remaining unlinked detections: {pending_unlinked_detections} "
                        f"(unchanged for >= {idle_timeout}s)"
                    )
                    print(f"  Created {new_events} new events in {elapsed:.0f} seconds")
                    return current_count, new_events, True
                if int(elapsed) % 30 == 0:
                    print(
                        f"  [{elapsed:.0f}s] Still draining pipeline: "
                        f"missing_cameras={missing_cameras}, "
                        f"unlinked_detections={pending_unlinked_detections}"
                    )
                await asyncio.sleep(poll_interval)
                continue
            print(f"\n✓ Pipeline appears idle (no new events for {idle_timeout}s)")
            print(f"  Created {new_events} new events in {elapsed:.0f} seconds")
            return current_count, new_events, True

        # Still waiting
        if int(elapsed) % 30 == 0 and int(elapsed) > 0:
            if expected_camera_ids:
                print(
                    f"  [{elapsed:.0f}s] Waiting... ({new_events} events so far, "
                    f"missing_cameras={missing_cameras}, "
                    f"unlinked_detections={pending_unlinked_detections})"
                )
            else:
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

        # Count plate reads
        result = await session.execute(select(func.count()).select_from(PlateRead))
        counts["plate_reads"] = result.scalar() or 0

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

    clip_url = _fix_service_url("CLIP_URL", "http://localhost:8093")
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
                        # Validate and resolve the image path to prevent path traversal
                        img_path = Path(image_path).resolve()
                        allowed_base = Path("/export/foscam").resolve()

                        # Ensure the path is within the allowed directory
                        if not str(img_path).startswith(str(allowed_base)):
                            print(f"    Skipping {det.id}: path outside allowed directory")
                            continue

                        if img_path.exists() and img_path.is_file():
                            import base64

                            with img_path.open("rb") as f:
                                image_b64 = base64.b64encode(f.read()).decode("utf-8")
                            response = await client.post(
                                f"{clip_url}/embed",
                                json={"image": image_b64},
                            )
                            if response.status_code == 200:
                                data = response.json()
                                embedding_vector = {
                                    "vector": data.get("embedding", []),
                                    "model": "siglip2-base-patch16-224",
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


async def seed_plate_reads(num_reads: int = 60) -> int:
    """Create license plate detection records.

    Generates realistic plate reads across cameras with a mix of known
    (registered household) and unknown plates, varied confidence scores,
    and quality conditions.

    Args:
        num_reads: Total number of plate reads to create

    Returns:
        Number of plate reads created
    """
    cameras = await get_cameras()
    if not cameras:
        print("  Warning: No cameras found. Create cameras first.")
        return 0

    # Known plates from seed_registered_vehicles templates
    known_plates = ["ABC1234", "XYZ5678", "DEF9012", "GHI3456", "JKL7890"]
    # Unknown plates for variety
    unknown_plates = [
        "MNO2468",
        "PQR1357",
        "STU8024",
        "VWX9135",
        "YZA4680",
        "BCD7531",
        "EFG2864",
        "HIJ9753",
        "KLM0642",
        "NOP3197",
    ]
    all_plates = known_plates + unknown_plates

    created = 0

    async with get_session() as session:
        for _ in range(num_reads):
            camera = random.choice(cameras)  # noqa: S311

            # Weighted toward known plates (more frequent visitors)
            if random.random() < 0.6:  # noqa: S311
                plate_text = random.choice(known_plates)  # noqa: S311
            else:
                plate_text = random.choice(unknown_plates)  # noqa: S311

            # Vary time distribution over past 7 days
            hours_ago = random.uniform(0.1, 168)  # noqa: S311
            timestamp = datetime.now(UTC) - timedelta(hours=hours_ago)

            # Generate realistic confidence scores
            detection_confidence = round(random.uniform(0.65, 0.99), 3)  # noqa: S311
            # OCR confidence correlates with quality
            base_ocr = random.uniform(0.50, 0.98)  # noqa: S311
            is_blurry = random.random() < 0.12  # noqa: S311
            is_enhanced = random.random() < 0.20  # noqa: S311
            quality_score = round(random.uniform(0.3, 0.95), 3)  # noqa: S311

            # Blurry images have lower OCR confidence
            if is_blurry:
                base_ocr *= 0.7
                quality_score = min(quality_score, 0.5)
            # Enhanced images slightly lower quality but OCR stays reasonable
            if is_enhanced:
                quality_score = min(quality_score, 0.6)

            ocr_confidence = round(min(base_ocr, 0.99), 3)

            # Generate bounding box in image coordinates
            x1 = round(random.uniform(100, 500), 1)  # noqa: S311
            y1 = round(random.uniform(200, 600), 1)  # noqa: S311
            x2 = round(x1 + random.uniform(80, 200), 1)  # noqa: S311
            y2 = round(y1 + random.uniform(30, 80), 1)  # noqa: S311

            # raw_text may include dash formatting
            raw_plate = (
                plate_text[:3] + "-" + plate_text[3:] if len(plate_text) >= 6 else plate_text
            )

            plate_read = PlateRead(
                camera_id=camera.id,
                timestamp=timestamp,
                plate_text=plate_text,
                raw_text=raw_plate,
                detection_confidence=detection_confidence,
                ocr_confidence=ocr_confidence,
                bbox=[x1, y1, x2, y2],
                image_quality_score=quality_score,
                is_enhanced=is_enhanced,
                is_blurry=is_blurry,
            )
            session.add(plate_read)
            created += 1

        await session.commit()

    print(
        f"  Created {created} plate reads ({len(known_plates)} known plates, {len(unknown_plates)} unknown)"
    )
    return created


async def seed_cost_tracking_data(days: int = 30) -> int:
    """Seed historical cost tracking data for the Cost Analytics Dashboard.

    Populates the CostTracker's in-memory daily usage with synthetic
    historical data so the cost trend charts have data to display.

    Args:
        days: Number of days of historical data to generate

    Returns:
        Number of daily records seeded
    """
    from backend.services.cost_tracker import get_cost_tracker

    tracker = get_cost_tracker()
    today = datetime.now(UTC).date()
    seeded = 0

    for day_offset in range(days, 0, -1):
        target_date = today - timedelta(days=day_offset)

        # Simulate varying daily activity
        base_events = random.randint(20, 80)  # noqa: S311
        base_detections = base_events * random.randint(3, 8)  # noqa: S311

        # Weekend vs weekday variation
        is_weekend = target_date.weekday() >= 5
        if is_weekend:
            base_events = int(base_events * 0.6)
            base_detections = int(base_detections * 0.6)

        # LLM usage (Nemotron)
        for _ in range(base_events):
            input_tokens = random.randint(200, 800)  # noqa: S311
            output_tokens = random.randint(100, 400)  # noqa: S311
            duration = random.uniform(0.5, 3.0)  # noqa: S311
            record = tracker.track_llm_usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model="nemotron",
                duration_seconds=duration,
            )
            # Override the date to the historical day
            if target_date in tracker._daily_usage:
                usage = tracker._daily_usage[target_date]
            else:
                from backend.services.cost_tracker import DailyUsage

                usage = DailyUsage(date=target_date)
                tracker._daily_usage[target_date] = usage
            usage.total_input_tokens += input_tokens
            usage.total_output_tokens += output_tokens
            usage.total_gpu_seconds += duration
            usage.total_estimated_cost_usd += record.estimated_cost_usd
            usage.event_count += 1

        # Detection usage (YOLO26, Florence, CLIP)
        for model in ["yolo26", "florence", "clip"]:
            count = base_detections if model == "yolo26" else base_detections // 3
            duration = count * random.uniform(0.01, 0.05)  # noqa: S311
            tracker.track_detection_usage(
                model=model,
                duration_seconds=duration,
                images_processed=count,
            )

        seeded += 1

    print(f"  Seeded {seeded} days of cost tracking data")
    return seeded


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

    backend_url = _fix_service_url("BACKEND_URL", "http://localhost:8000")
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


async def seed_admin_user() -> bool:
    """Ensure a default admin user exists.

    The SetupGuardMiddleware returns HTTP 503 on all API endpoints until at
    least one user row exists in the database.  This function creates a
    default admin user (admin / admin@localhost / admin) when the users
    table is empty so the middleware unblocks immediately.

    The operation is idempotent -- if any user already exists, it is a no-op.

    Returns:
        True if a new admin user was created, False if one already existed.
    """
    from sqlalchemy import func as sa_func

    async with get_session() as session:
        result = await session.execute(select(sa_func.count(User.id)))
        count = result.scalar() or 0

        if count > 0:
            print("  Admin user already exists -- skipping creation")
            return False

        password_hashed = hash_password("admin")
        user = User(
            id=str(uuid.uuid4()),
            username="admin",
            email="admin@localhost",
            password_hash=password_hashed,
            is_active=True,
            is_admin=True,
        )
        session.add(user)
        await session.commit()

        print(f"  Created default admin user (username=admin, id={user.id})")
        return True


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

    stgcn_config = {
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
            "model": "stgcn-plus-plus",
            "system_prompt": json.dumps(stgcn_config),
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
        AIModel.XCLIP: [  # Note: STGCN replaces XCLIP but enum still has XCLIP for backward compatibility
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


# =============================================================================
# PHASE 7: METRICS SEEDING
# =============================================================================
# These functions exercise Prometheus metrics to ensure dashboard panels
# show data after seeding. Metrics are recorded directly into the Prometheus
# client, so they will be available on the /metrics endpoint.


async def seed_face_recognition_metrics(num_samples: int = 50) -> dict[str, int]:
    """Generate face detection events with quality scores.

    Seeds:
    - hsi_face_detections_total (Counter)
    - hsi_face_quality_score (Histogram)
    - hsi_face_embeddings_generated_total (Counter)
    - hsi_face_matches_total (Counter)
    - hsi_face_recognition_confidence (Histogram) - NEM-3979
    - hsi_face_embedding_duration_seconds (Histogram) - NEM-3979

    Args:
        num_samples: Number of face detection samples to generate

    Returns:
        Dictionary with counts of seeded metrics
    """
    from backend.core.metrics import (
        FACE_DETECTIONS_TOTAL,
        FACE_EMBEDDING_DURATION_SECONDS,
        FACE_EMBEDDINGS_GENERATED_TOTAL,
        FACE_MATCHES_TOTAL,
        FACE_QUALITY_SCORE,
        FACE_RECOGNITION_CONFIDENCE,
    )

    cameras = await get_cameras()
    camera_ids = [c.id for c in cameras] if cameras else ["cam_default"]

    counts = {
        "face_detections": 0,
        "face_quality_scores": 0,
        "face_embeddings": 0,
        "face_matches": 0,
        "face_recognition_confidences": 0,
        "face_embedding_durations": 0,
    }

    # Generate face detections across cameras
    for _ in range(num_samples):
        camera_id = random.choice(camera_ids)  # noqa: S311
        # 70% known, 30% unknown faces
        match_status = "known" if random.random() < 0.7 else "unknown"  # noqa: S311

        FACE_DETECTIONS_TOTAL.labels(camera_id=camera_id, match_status=match_status).inc()
        counts["face_detections"] += 1

        # Quality score between 0.3 and 0.98 (realistic face quality range)
        quality = random.uniform(0.3, 0.98)  # noqa: S311
        FACE_QUALITY_SCORE.observe(quality)
        counts["face_quality_scores"] += 1

        # 80% of detections generate embeddings
        if random.random() < 0.8:  # noqa: S311
            FACE_EMBEDDINGS_GENERATED_TOTAL.labels(match_status=match_status).inc()
            counts["face_embeddings"] += 1

            # NEM-3979: Record embedding generation duration (10ms to 500ms typical range)
            duration = random.uniform(0.01, 0.5)  # noqa: S311
            FACE_EMBEDDING_DURATION_SECONDS.labels(camera_id=camera_id).observe(duration)
            counts["face_embedding_durations"] += 1

        # Known faces match to a person_id
        if match_status == "known":
            person_id = f"person_{random.randint(1, 5)}"  # noqa: S311
            FACE_MATCHES_TOTAL.labels(person_id=person_id).inc()
            counts["face_matches"] += 1

            # NEM-3979: Record recognition confidence (0.3 to 0.99 realistic range)
            confidence = random.uniform(0.3, 0.99)  # noqa: S311
            FACE_RECOGNITION_CONFIDENCE.labels(camera_id=camera_id).observe(confidence)
            counts["face_recognition_confidences"] += 1

    print(f"  Seeded {counts['face_detections']} face detections")
    print(f"  Seeded {counts['face_quality_scores']} face quality scores")
    print(f"  Seeded {counts['face_embeddings']} face embeddings")
    print(f"  Seeded {counts['face_matches']} face matches")
    print(f"  Seeded {counts['face_recognition_confidences']} face recognition confidences")
    print(f"  Seeded {counts['face_embedding_durations']} face embedding durations")
    return counts


async def seed_action_recognition_metrics(num_samples: int = 40) -> dict[str, int]:
    """Simulate loitering, falls, aggression detection.

    Seeds:
    - hsi_action_recognition_total (Counter)
    - hsi_action_recognition_confidence (Histogram)
    - hsi_action_recognition_duration_seconds (Histogram)
    - hsi_loitering_alerts_total (Counter)
    - hsi_loitering_dwell_time_seconds (Histogram)

    Args:
        num_samples: Number of action recognition samples to generate

    Returns:
        Dictionary with counts of seeded metrics
    """
    from backend.core.metrics import (
        ACTION_RECOGNITION_CONFIDENCE,
        ACTION_RECOGNITION_DURATION_SECONDS,
        ACTION_RECOGNITION_TOTAL,
        LOITERING_ALERTS_TOTAL,
        LOITERING_DWELL_TIME_SECONDS,
    )

    cameras = await get_cameras()
    camera_ids = [c.id for c in cameras] if cameras else ["cam_default"]

    # Realistic action types with their relative frequencies
    action_types = [
        ("walking", 0.35),
        ("loitering", 0.20),
        ("running", 0.15),
        ("standing", 0.15),
        ("falling", 0.05),
        ("fighting", 0.05),
        ("vandalism", 0.03),
        ("package_delivery", 0.02),
    ]

    counts = {
        "action_recognitions": 0,
        "action_confidences": 0,
        "action_durations": 0,
        "loitering_alerts": 0,
        "dwell_times": 0,
    }

    for _ in range(num_samples):
        camera_id = random.choice(camera_ids)  # noqa: S311

        # Select action type based on weighted probability
        rand = random.random()  # noqa: S311
        cumulative = 0
        action_type = "walking"  # default
        for action, prob in action_types:
            cumulative += prob
            if rand < cumulative:
                action_type = action
                break

        # Record action detection
        ACTION_RECOGNITION_TOTAL.labels(action_type=action_type, camera_id=camera_id).inc()
        counts["action_recognitions"] += 1

        # Confidence score (0.5 to 0.99)
        confidence = random.uniform(0.5, 0.99)  # noqa: S311
        ACTION_RECOGNITION_CONFIDENCE.labels(action_type=action_type).observe(confidence)
        counts["action_confidences"] += 1

        # Inference duration (50ms to 2s)
        duration = random.uniform(0.05, 2.0)  # noqa: S311
        ACTION_RECOGNITION_DURATION_SECONDS.observe(duration)
        counts["action_durations"] += 1

        # For loitering actions, generate alerts and dwell times
        if action_type == "loitering":
            zone_id = f"zone_{random.randint(1, 5)}"  # noqa: S311
            LOITERING_ALERTS_TOTAL.labels(camera_id=camera_id, zone_id=zone_id).inc()
            counts["loitering_alerts"] += 1

            # Dwell time: 30 seconds to 30 minutes
            dwell = random.uniform(30, 1800)  # noqa: S311
            LOITERING_DWELL_TIME_SECONDS.labels(camera_id=camera_id).observe(dwell)
            counts["dwell_times"] += 1

    print(f"  Seeded {counts['action_recognitions']} action recognitions")
    print(f"  Seeded {counts['loitering_alerts']} loitering alerts")
    print(f"  Seeded {counts['dwell_times']} dwell time observations")
    return counts


async def seed_circuit_breaker_metrics(num_samples: int = 20) -> dict[str, int]:
    """Exercise circuit breaker state transitions.

    Seeds:
    - hsi_circuit_breaker_state (Gauge)
    - hsi_circuit_breaker_trips_total (Counter)
    - circuit_breaker_state (Gauge) - legacy metric
    - circuit_breaker_failures_total (Counter) - NEM-3983
    - circuit_breaker_state_changes_total (Counter) - NEM-3983
    - circuit_breaker_calls_total (Counter) - NEM-3983
    - circuit_breaker_rejected_total (Counter) - NEM-3983

    Args:
        num_samples: Number of state transitions to simulate

    Returns:
        Dictionary with counts of seeded metrics
    """
    from backend.services.circuit_breaker import (
        CIRCUIT_BREAKER_CALLS_TOTAL,
        CIRCUIT_BREAKER_FAILURES_TOTAL,
        CIRCUIT_BREAKER_REJECTED_TOTAL,
        CIRCUIT_BREAKER_STATE,
        CIRCUIT_BREAKER_STATE_CHANGES_TOTAL,
        HSI_CIRCUIT_BREAKER_STATE,
        HSI_CIRCUIT_BREAKER_TRIPS_TOTAL,
    )

    # Simulated services that might have circuit breakers
    services = ["nemotron_llm", "yolo26", "clip_service", "redis_cache", "postgres_db"]

    counts = {
        "state_updates": 0,
        "trips": 0,
        "failures": 0,
        "state_changes": 0,
        "successful_calls": 0,
        "failed_calls": 0,
        "rejected_calls": 0,
    }

    for service in services:
        # Set initial closed state (0) for both metric sets
        HSI_CIRCUIT_BREAKER_STATE.labels(service=service).set(0)
        CIRCUIT_BREAKER_STATE.labels(service=service).set(0)
        counts["state_updates"] += 1

    # Simulate some circuit breaker activity
    for _ in range(num_samples):
        service = random.choice(services)  # noqa: S311

        # Simulate calls through the circuit breaker (NEM-3983)
        num_calls = random.randint(5, 20)  # noqa: S311
        for _ in range(num_calls):
            # 85% success rate when circuit is closed
            if random.random() < 0.85:  # noqa: S311
                CIRCUIT_BREAKER_CALLS_TOTAL.labels(service=service, result="success").inc()
                counts["successful_calls"] += 1
            else:
                CIRCUIT_BREAKER_CALLS_TOTAL.labels(service=service, result="failure").inc()
                CIRCUIT_BREAKER_FAILURES_TOTAL.labels(service=service).inc()
                counts["failed_calls"] += 1
                counts["failures"] += 1

        # Occasionally trip a breaker (20% chance)
        if random.random() < 0.2:  # noqa: S311
            # Track previous state for state change metric
            prev_state = "closed"

            # Open state
            HSI_CIRCUIT_BREAKER_STATE.labels(service=service).set(1)
            CIRCUIT_BREAKER_STATE.labels(service=service).set(1)
            HSI_CIRCUIT_BREAKER_TRIPS_TOTAL.labels(service=service).inc()
            CIRCUIT_BREAKER_STATE_CHANGES_TOTAL.labels(
                service=service, from_state=prev_state, to_state="open"
            ).inc()
            counts["state_updates"] += 1
            counts["trips"] += 1
            counts["state_changes"] += 1

            # Simulate some rejected calls while open (NEM-3983)
            rejected = random.randint(1, 5)  # noqa: S311
            for _ in range(rejected):
                CIRCUIT_BREAKER_REJECTED_TOTAL.labels(service=service).inc()
                counts["rejected_calls"] += 1

            # 50% chance to transition to half-open
            if random.random() < 0.5:  # noqa: S311
                HSI_CIRCUIT_BREAKER_STATE.labels(service=service).set(2)
                CIRCUIT_BREAKER_STATE.labels(service=service).set(2)
                CIRCUIT_BREAKER_STATE_CHANGES_TOTAL.labels(
                    service=service, from_state="open", to_state="half_open"
                ).inc()
                counts["state_updates"] += 1
                counts["state_changes"] += 1

                # 70% chance to recover to closed
                if random.random() < 0.7:  # noqa: S311
                    HSI_CIRCUIT_BREAKER_STATE.labels(service=service).set(0)
                    CIRCUIT_BREAKER_STATE.labels(service=service).set(0)
                    CIRCUIT_BREAKER_STATE_CHANGES_TOTAL.labels(
                        service=service, from_state="half_open", to_state="closed"
                    ).inc()
                    counts["state_updates"] += 1
                    counts["state_changes"] += 1

    # Ensure most breakers end up closed (healthy state)
    for service in services:
        if random.random() < 0.9:  # noqa: S311
            HSI_CIRCUIT_BREAKER_STATE.labels(service=service).set(0)
            CIRCUIT_BREAKER_STATE.labels(service=service).set(0)

    print(f"  Seeded {counts['state_updates']} circuit breaker state updates")
    print(f"  Seeded {counts['trips']} circuit breaker trips")
    print(f"  Seeded {counts['failures']} circuit breaker failures")
    print(f"  Seeded {counts['state_changes']} circuit breaker state changes")
    print(f"  Seeded {counts['successful_calls']} successful calls")
    print(f"  Seeded {counts['failed_calls']} failed calls")
    print(f"  Seeded {counts['rejected_calls']} rejected calls")
    return counts


async def seed_ab_testing_metrics(num_samples: int = 50) -> dict[str, int]:
    """Seed A/B testing and shadow prompt experiment metrics (NEM-3980).

    Seeds:
    - hsi_ab_rollout_analysis_total (Counter)
    - hsi_ab_rollout_avg_latency_ms (Gauge)
    - hsi_ab_rollout_avg_risk_score (Gauge)
    - hsi_ab_rollout_feedback_total (Counter)
    - hsi_ab_rollout_fp_rate (Gauge)

    Args:
        num_samples: Number of experiment samples to generate

    Returns:
        Dictionary with counts of seeded metrics
    """
    from backend.core.metrics import (
        AB_ROLLOUT_ANALYSIS_TOTAL,
        AB_ROLLOUT_AVG_LATENCY_MS,
        AB_ROLLOUT_AVG_RISK_SCORE,
        AB_ROLLOUT_FEEDBACK_TOTAL,
        AB_ROLLOUT_FP_RATE,
    )

    # A/B test groups
    groups = ["control", "treatment"]

    counts = {
        "analyses": 0,
        "latency_updates": 0,
        "risk_score_updates": 0,
        "feedback_submissions": 0,
        "fp_rate_updates": 0,
    }

    # Simulate experiment analyses for each group
    for _ in range(num_samples):
        group = random.choice(groups)  # noqa: S311

        # Record an analysis event
        AB_ROLLOUT_ANALYSIS_TOTAL.labels(group=group).inc()
        counts["analyses"] += 1

    # Set realistic gauge values for each group
    for group in groups:
        # Control group typically has slightly higher latency than treatment
        base_latency = 450 if group == "control" else 380
        latency_variance = random.uniform(-50, 50)  # noqa: S311
        AB_ROLLOUT_AVG_LATENCY_MS.labels(group=group).set(base_latency + latency_variance)
        counts["latency_updates"] += 1

        # Risk scores: control group baseline, treatment may differ
        base_risk = 55 if group == "control" else 52
        risk_variance = random.uniform(-5, 5)  # noqa: S311
        AB_ROLLOUT_AVG_RISK_SCORE.labels(group=group).set(base_risk + risk_variance)
        counts["risk_score_updates"] += 1

        # False positive rates: treatment should be lower if experiment is successful
        base_fp_rate = 0.12 if group == "control" else 0.08
        fp_variance = random.uniform(-0.02, 0.02)  # noqa: S311
        AB_ROLLOUT_FP_RATE.labels(group=group).set(max(0, base_fp_rate + fp_variance))
        counts["fp_rate_updates"] += 1

    # Generate feedback submissions
    feedback_samples = num_samples // 5  # 20% of samples have feedback
    for _ in range(feedback_samples):
        group = random.choice(groups)  # noqa: S311

        # 15% of feedback indicates false positive, 85% correct
        is_false_positive = random.random() < 0.15  # noqa: S311
        feedback_type = "false_positive" if is_false_positive else "correct"
        AB_ROLLOUT_FEEDBACK_TOTAL.labels(group=group, feedback_type=feedback_type).inc()
        counts["feedback_submissions"] += 1

    print(f"  Seeded {counts['analyses']} A/B rollout analyses")
    print(f"  Seeded {counts['latency_updates']} latency gauge updates")
    print(f"  Seeded {counts['risk_score_updates']} risk score gauge updates")
    print(f"  Seeded {counts['fp_rate_updates']} false positive rate updates")
    print(f"  Seeded {counts['feedback_submissions']} feedback submissions")
    return counts


async def seed_cache_metrics(num_samples: int = 100) -> dict[str, int]:
    """Generate cache hit/miss events.

    Seeds:
    - hsi_cache_hits_total (Counter)
    - hsi_cache_misses_total (Counter)

    Args:
        num_samples: Number of cache operations to simulate

    Returns:
        Dictionary with counts of seeded metrics
    """
    from backend.core.metrics import CACHE_HITS_TOTAL, CACHE_MISSES_TOTAL

    # Cache types in the system
    cache_types = ["detection", "embedding", "event", "baseline", "config"]

    counts = {
        "cache_hits": 0,
        "cache_misses": 0,
    }

    for _ in range(num_samples):
        cache_type = random.choice(cache_types)  # noqa: S311

        # Simulate realistic cache hit rate (70-90% depending on cache type)
        hit_rates = {
            "detection": 0.75,
            "embedding": 0.85,
            "event": 0.70,
            "baseline": 0.90,
            "config": 0.95,
        }
        hit_rate = hit_rates.get(cache_type, 0.8)

        if random.random() < hit_rate:  # noqa: S311
            CACHE_HITS_TOTAL.labels(cache_type=cache_type).inc()
            counts["cache_hits"] += 1
        else:
            CACHE_MISSES_TOTAL.labels(cache_type=cache_type).inc()
            counts["cache_misses"] += 1

    print(f"  Seeded {counts['cache_hits']} cache hits")
    print(f"  Seeded {counts['cache_misses']} cache misses")
    return counts


async def seed_dlq_metrics(num_items: int = 15) -> dict[str, int]:
    """Add items to dead letter queue for visualization.

    Seeds:
    - hsi_dlq_depth (Gauge)
    - hsi_queue_items_moved_to_dlq_total (Counter)

    Args:
        num_items: Number of DLQ items to simulate

    Returns:
        Dictionary with counts of seeded metrics
    """
    from backend.core.metrics import DLQ_DEPTH, QUEUE_ITEMS_MOVED_TO_DLQ_TOTAL

    # Queue names that can have DLQs
    queue_names = ["detection_queue", "analysis_queue", "notification_queue", "export_queue"]

    counts = {
        "dlq_depth_updates": 0,
        "items_moved_to_dlq": 0,
    }

    # Reasons for DLQ movement
    dlq_reasons = ["max_retries", "timeout", "invalid_payload", "service_unavailable"]

    # Distribute items across queues
    for queue_name in queue_names:
        # Random DLQ depth (0 to 10 items)
        depth = random.randint(0, min(10, num_items // len(queue_names) + 2))  # noqa: S311
        DLQ_DEPTH.labels(queue_name=queue_name).set(depth)
        counts["dlq_depth_updates"] += 1

        # Simulate historical items moved to DLQ
        moved = random.randint(0, num_items // len(queue_names))  # noqa: S311
        for _ in range(moved):
            reason = random.choice(dlq_reasons)  # noqa: S311
            QUEUE_ITEMS_MOVED_TO_DLQ_TOTAL.labels(queue_name=queue_name, reason=reason).inc()
            counts["items_moved_to_dlq"] += 1

    print(f"  Seeded {counts['dlq_depth_updates']} DLQ depth updates")
    print(f"  Seeded {counts['items_moved_to_dlq']} items moved to DLQ")
    return counts


async def seed_rum_metrics(num_samples: int = 50) -> dict[str, int]:
    """Simulate frontend performance events (Real User Monitoring).

    Seeds:
    - hsi_rum_page_load_time_seconds (Histogram)
    - hsi_rum_fcp_seconds (First Contentful Paint)
    - hsi_rum_lcp_seconds (Largest Contentful Paint)
    - hsi_rum_cls (Cumulative Layout Shift)
    - hsi_rum_fid_seconds (First Input Delay)
    - hsi_rum_inp_seconds (Interaction to Next Paint)
    - hsi_rum_ttfb_seconds (Time to First Byte)
    - hsi_rum_metrics_total (Counter)

    Args:
        num_samples: Number of RUM events to simulate

    Returns:
        Dictionary with counts of seeded metrics
    """
    from backend.core.metrics import (
        RUM_CLS,
        RUM_FCP_SECONDS,
        RUM_FID_SECONDS,
        RUM_INP_SECONDS,
        RUM_LCP_SECONDS,
        RUM_METRICS_TOTAL,
        RUM_PAGE_LOAD_TIME_SECONDS,
        RUM_TTFB_SECONDS,
    )

    # Common page paths
    paths = ["/", "/events", "/cameras", "/settings", "/alerts", "/analytics", "/timeline"]

    # Rating based on performance thresholds
    def get_rating(value: float, good: float, poor: float) -> str:
        if value <= good:
            return "good"
        elif value <= poor:
            return "needs-improvement"
        else:
            return "poor"

    counts = {
        "page_loads": 0,
        "fcp": 0,
        "lcp": 0,
        "cls": 0,
        "fid": 0,
        "inp": 0,
        "ttfb": 0,
    }

    for _ in range(num_samples):
        path = random.choice(paths)  # noqa: S311

        # Page Load Time: 1-15 seconds (good < 3s, poor > 6s)
        page_load = random.uniform(1.0, 15.0)  # noqa: S311
        rating = get_rating(page_load, 3.0, 6.0)
        RUM_PAGE_LOAD_TIME_SECONDS.labels(path=path, rating=rating).observe(page_load)
        RUM_METRICS_TOTAL.labels(metric_name="page_load", rating=rating).inc()
        counts["page_loads"] += 1

        # FCP: 0.5-6 seconds (good < 1.8s, poor > 3s)
        fcp = random.uniform(0.5, 6.0)  # noqa: S311
        rating = get_rating(fcp, 1.8, 3.0)
        RUM_FCP_SECONDS.labels(path=path, rating=rating).observe(fcp)
        RUM_METRICS_TOTAL.labels(metric_name="FCP", rating=rating).inc()
        counts["fcp"] += 1

        # LCP: 0.5-10 seconds (good < 2.5s, poor > 4s)
        lcp = random.uniform(0.5, 10.0)  # noqa: S311
        rating = get_rating(lcp, 2.5, 4.0)
        RUM_LCP_SECONDS.labels(path=path, rating=rating).observe(lcp)
        RUM_METRICS_TOTAL.labels(metric_name="LCP", rating=rating).inc()
        counts["lcp"] += 1

        # Cumulative Layout Shift: range 0-1, good when below 0.1, poor when above 0.25
        cls = random.uniform(0, 1.0)  # noqa: S311
        rating = get_rating(cls, 0.1, 0.25)
        RUM_CLS.labels(path=path, rating=rating).observe(cls)
        RUM_METRICS_TOTAL.labels(metric_name="CLS", rating=rating).inc()
        counts["cls"] += 1

        # FID: 0.01-2 seconds (good < 0.1s, poor > 0.3s)
        fid = random.uniform(0.01, 2.0)  # noqa: S311
        rating = get_rating(fid, 0.1, 0.3)
        RUM_FID_SECONDS.labels(path=path, rating=rating).observe(fid)
        RUM_METRICS_TOTAL.labels(metric_name="FID", rating=rating).inc()
        counts["fid"] += 1

        # INP: 0.05-2 seconds (good < 0.2s, poor > 0.5s)
        inp = random.uniform(0.05, 2.0)  # noqa: S311
        rating = get_rating(inp, 0.2, 0.5)
        RUM_INP_SECONDS.labels(path=path, rating=rating).observe(inp)
        RUM_METRICS_TOTAL.labels(metric_name="INP", rating=rating).inc()
        counts["inp"] += 1

        # TTFB: 0.1-5 seconds (good < 0.8s, poor > 1.8s)
        ttfb = random.uniform(0.1, 5.0)  # noqa: S311
        rating = get_rating(ttfb, 0.8, 1.8)
        RUM_TTFB_SECONDS.labels(path=path, rating=rating).observe(ttfb)
        RUM_METRICS_TOTAL.labels(metric_name="TTFB", rating=rating).inc()
        counts["ttfb"] += 1

    print(f"  Seeded {counts['page_loads']} page load metrics")
    print(f"  Seeded {counts['lcp']} LCP metrics")
    print(f"  Seeded {counts['fcp']} FCP metrics")
    print(f"  Seeded {counts['cls']} CLS metrics")
    return counts


async def seed_reid_metrics(num_samples: int = 30) -> dict[str, int]:
    """Simulate person re-identification events.

    Seeds:
    - hsi_tracks_reidentified_total (Counter)

    Note: Some Re-ID metrics (hsi_reid_matches_total, hsi_reid_attempts_total,
    hsi_cross_camera_handoffs_total) are referenced in Grafana dashboards but
    may not be defined in the metrics module yet. This function seeds what's available.

    Args:
        num_samples: Number of re-ID events to simulate

    Returns:
        Dictionary with counts of seeded metrics
    """
    from backend.core.metrics import TRACKS_REIDENTIFIED_TOTAL

    cameras = await get_cameras()
    camera_ids = [c.id for c in cameras] if cameras else ["cam_default"]

    counts = {
        "tracks_reidentified": 0,
    }

    for _ in range(num_samples):
        camera_id = random.choice(camera_ids)  # noqa: S311
        TRACKS_REIDENTIFIED_TOTAL.labels(camera_id=camera_id).inc()
        counts["tracks_reidentified"] += 1

    print(f"  Seeded {counts['tracks_reidentified']} track re-identifications")
    return counts


async def seed_track_metrics(num_samples: int = 40) -> dict[str, int]:
    """Simulate object tracking metrics across cameras.

    Seeds:
    - hsi_tracks_created_total (Counter)
    - hsi_tracks_lost_total (Counter)
    - hsi_track_duration_seconds (Histogram)
    - hsi_track_active_count (Gauge)

    Args:
        num_samples: Number of track lifecycle events to simulate

    Returns:
        Dictionary with counts of seeded metrics
    """
    from backend.core.metrics import (
        TRACK_ACTIVE_COUNT,
        TRACK_DURATION_SECONDS,
        TRACKS_CREATED_TOTAL,
        TRACKS_LOST_TOTAL,
    )

    cameras = await get_cameras()
    camera_ids = [c.id for c in cameras] if cameras else ["cam_default"]
    object_classes = ["person", "vehicle", "animal", "package"]
    loss_reasons = ["timeout", "out_of_frame", "occlusion"]

    counts = {
        "tracks_created": 0,
        "tracks_lost": 0,
        "track_durations": 0,
        "track_active_updates": 0,
    }

    # Initialize active track counts per camera
    active_tracks_per_camera: dict[str, int] = dict.fromkeys(camera_ids, 0)

    for _ in range(num_samples):
        camera_id = random.choice(camera_ids)  # noqa: S311
        object_class = random.choice(object_classes)  # noqa: S311

        # Simulate track creation (labels: camera_id, object_class)
        TRACKS_CREATED_TOTAL.labels(camera_id=camera_id, object_class=object_class).inc()
        counts["tracks_created"] += 1
        active_tracks_per_camera[camera_id] += 1

        # 80% of tracks are eventually lost (completed naturally)
        if random.random() < 0.8:  # noqa: S311
            # Track duration: 1 second to 10 minutes (labels: camera_id, entity_type)
            duration = random.uniform(1.0, 600.0)  # noqa: S311
            TRACK_DURATION_SECONDS.labels(camera_id=camera_id, entity_type=object_class).observe(
                duration
            )
            counts["track_durations"] += 1

            # Track lost (labels: camera_id, object_class, reason)
            reason = random.choice(loss_reasons)  # noqa: S311
            TRACKS_LOST_TOTAL.labels(
                camera_id=camera_id, object_class=object_class, reason=reason
            ).inc()
            counts["tracks_lost"] += 1
            active_tracks_per_camera[camera_id] = max(0, active_tracks_per_camera[camera_id] - 1)

    # Set final active track counts per camera
    for camera_id, active_count in active_tracks_per_camera.items():
        # Add some realistic baseline of active tracks
        final_count = active_count + random.randint(0, 3)  # noqa: S311
        TRACK_ACTIVE_COUNT.labels(camera_id=camera_id).set(final_count)
        counts["track_active_updates"] += 1

    print(f"  Seeded {counts['tracks_created']} track creations")
    print(f"  Seeded {counts['tracks_lost']} track losses")
    print(f"  Seeded {counts['track_durations']} track durations")
    return counts


async def seed_zone_metrics(num_samples: int = 50) -> dict[str, int]:
    """Simulate zone monitoring metrics.

    Seeds:
    - hsi_zone_crossings_total (Counter)
    - hsi_zone_intrusions_total (Counter)
    - hsi_zone_occupancy (Gauge)
    - hsi_zone_dwell_time_seconds (Histogram)

    Args:
        num_samples: Number of zone events to simulate

    Returns:
        Dictionary with counts of seeded metrics
    """
    from backend.core.metrics import (
        ZONE_CROSSINGS_TOTAL,
        ZONE_DWELL_TIME_SECONDS,
        ZONE_INTRUSIONS_TOTAL,
        ZONE_OCCUPANCY,
    )

    cameras = await get_cameras()
    camera_ids = [c.id for c in cameras] if cameras else ["cam_default"]

    # Generate zone IDs based on cameras
    zone_ids = [f"zone_{cam_id[:8]}_{i}" for cam_id in camera_ids for i in range(1, 4)]
    if not zone_ids:
        zone_ids = ["zone_default_1", "zone_default_2"]

    directions = ["enter", "exit"]
    entity_types = ["person", "vehicle", "animal", "package"]
    severities = ["low", "medium", "high", "critical"]
    severity_weights = [0.60, 0.25, 0.10, 0.05]

    counts = {
        "zone_crossings": 0,
        "zone_intrusions": 0,
        "zone_occupancy_updates": 0,
        "zone_dwell_times": 0,
    }

    # Track occupancy per zone
    zone_occupancy: dict[str, int] = dict.fromkeys(zone_ids, 0)

    for _ in range(num_samples):
        zone_id = random.choice(zone_ids)  # noqa: S311
        entity_type = random.choice(entity_types)  # noqa: S311

        # Zone crossing events (labels: zone_id, direction, entity_type)
        direction = random.choice(directions)  # noqa: S311
        ZONE_CROSSINGS_TOTAL.labels(
            zone_id=zone_id, direction=direction, entity_type=entity_type
        ).inc()
        counts["zone_crossings"] += 1

        # Update occupancy based on direction
        if direction == "enter":
            zone_occupancy[zone_id] += 1
        else:
            zone_occupancy[zone_id] = max(0, zone_occupancy[zone_id] - 1)

        # 15% of crossings are intrusions (unauthorized zone entry)
        if random.random() < 0.15:  # noqa: S311
            severity = random.choices(severities, weights=severity_weights, k=1)[0]  # noqa: S311
            ZONE_INTRUSIONS_TOTAL.labels(zone_id=zone_id, severity=severity).inc()
            counts["zone_intrusions"] += 1

        # Record dwell time for some crossings (entry events that eventually exit)
        if direction == "enter" and random.random() < 0.6:  # noqa: S311
            # Dwell time: 5 seconds to 30 minutes
            dwell_time = random.uniform(5.0, 1800.0)  # noqa: S311
            ZONE_DWELL_TIME_SECONDS.labels(zone_id=zone_id).observe(dwell_time)
            counts["zone_dwell_times"] += 1

    # Set final occupancy for all zones
    for zone_id, occupancy in zone_occupancy.items():
        # Add some realistic baseline occupancy
        final_occupancy = max(0, occupancy + random.randint(-1, 2))  # noqa: S311
        ZONE_OCCUPANCY.labels(zone_id=zone_id).set(final_occupancy)
        counts["zone_occupancy_updates"] += 1

    print(f"  Seeded {counts['zone_crossings']} zone crossings")
    print(f"  Seeded {counts['zone_intrusions']} zone intrusions")
    print(f"  Seeded {counts['zone_dwell_times']} zone dwell times")
    return counts


async def seed_worker_metrics(num_samples: int = 20) -> dict[str, int]:
    """Simulate pipeline worker metrics.

    Seeds:
    - hsi_worker_restarts_total (Counter)
    - hsi_worker_crashes_total (Counter)
    - hsi_worker_max_restarts_exceeded_total (Counter)
    - hsi_worker_status (Gauge)
    - hsi_worker_active_count (Gauge)
    - hsi_worker_busy_count (Gauge)
    - hsi_worker_idle_count (Gauge)
    - hsi_pipeline_worker_state (Gauge)
    - hsi_pipeline_worker_uptime_seconds (Gauge)

    Args:
        num_samples: Number of worker events to simulate

    Returns:
        Dictionary with counts of seeded metrics
    """
    from backend.core.metrics import (
        PIPELINE_WORKER_STATE,
        PIPELINE_WORKER_UPTIME_SECONDS,
        WORKER_ACTIVE_COUNT,
        WORKER_BUSY_COUNT,
        WORKER_CRASHES_TOTAL,
        WORKER_IDLE_COUNT,
        WORKER_MAX_RESTARTS_EXCEEDED_TOTAL,
        WORKER_RESTARTS_TOTAL,
        WORKER_STATUS,
    )

    # Worker names in the pipeline
    worker_names = [
        "file_watcher",
        "yolo_detector",
        "batch_aggregator",
        "nemotron_analyzer",
        "event_creator",
        "notification_sender",
    ]
    # Worker types for different categories
    worker_types = ["detection", "analysis", "notification", "export"]
    # Restart reasons
    restart_reasons = ["scheduled", "config_change", "error_recovery", "health_check_failed"]
    # Exit codes for crashes
    exit_codes = ["1", "137", "139", "255"]

    counts = {
        "worker_restarts": 0,
        "worker_crashes": 0,
        "worker_status_updates": 0,
        "worker_pool_updates": 0,
    }

    # Set all workers to running initially (status 1)
    for worker in worker_names:
        WORKER_STATUS.labels(worker_name=worker).set(1)  # 1 = running
        PIPELINE_WORKER_STATE.labels(worker_name=worker).set(1)  # 1 = running
        # Uptime: 1 hour to 7 days
        uptime = random.uniform(3600, 604800)  # noqa: S311
        PIPELINE_WORKER_UPTIME_SECONDS.labels(worker_name=worker).set(uptime)
        counts["worker_status_updates"] += 1

    # Simulate some worker events
    for _ in range(num_samples):
        worker = random.choice(worker_names)  # noqa: S311
        worker_type = random.choice(worker_types)  # noqa: S311

        # 30% chance of restart (labels: worker_name, worker_type, reason)
        if random.random() < 0.3:  # noqa: S311
            reason = random.choice(restart_reasons)  # noqa: S311
            WORKER_RESTARTS_TOTAL.labels(
                worker_name=worker, worker_type=worker_type, reason=reason
            ).inc()
            counts["worker_restarts"] += 1

        # 5% chance of crash (labels: worker_name, worker_type, exit_code)
        if random.random() < 0.05:  # noqa: S311
            exit_code = random.choice(exit_codes)  # noqa: S311
            WORKER_CRASHES_TOTAL.labels(
                worker_name=worker, worker_type=worker_type, exit_code=exit_code
            ).inc()
            counts["worker_crashes"] += 1

            # 10% of crashes exceed max restarts (labels: worker_name)
            if random.random() < 0.1:  # noqa: S311
                WORKER_MAX_RESTARTS_EXCEEDED_TOTAL.labels(worker_name=worker).inc()

    # Set worker pool metrics (aggregate counts)
    total_workers = len(worker_names)
    busy_count = random.randint(1, total_workers - 1)  # noqa: S311
    idle_count = total_workers - busy_count
    WORKER_ACTIVE_COUNT.set(total_workers)
    WORKER_BUSY_COUNT.set(busy_count)
    WORKER_IDLE_COUNT.set(idle_count)
    counts["worker_pool_updates"] = 3

    print(f"  Seeded {counts['worker_restarts']} worker restarts")
    print(f"  Seeded {counts['worker_crashes']} worker crashes")
    print(f"  Seeded {counts['worker_status_updates']} worker status updates")
    return counts


async def seed_gpu_metrics(num_samples: int = 30) -> dict[str, int]:
    """Simulate GPU usage metrics.

    Seeds:
    - hsi_gpu_seconds_total (Counter)

    Args:
        num_samples: Number of GPU usage events to simulate

    Returns:
        Dictionary with counts of seeded metrics
    """
    from backend.core.metrics import GPU_SECONDS_TOTAL

    # AI models that use GPU
    models = ["yolo26", "nemotron", "clip", "florence", "reid"]

    counts = {
        "gpu_seconds": 0,
    }

    for _ in range(num_samples):
        model = random.choice(models)  # noqa: S311
        # GPU time: 0.1 to 5 seconds per inference
        gpu_time = random.uniform(0.1, 5.0)  # noqa: S311
        GPU_SECONDS_TOTAL.labels(model=model).inc(gpu_time)
        counts["gpu_seconds"] += 1

    print(f"  Seeded {counts['gpu_seconds']} GPU usage samples")
    return counts


async def seed_detection_metrics(num_samples: int = 50) -> dict[str, int]:
    """Simulate detection processing metrics.

    Seeds:
    - hsi_detection_queue_depth (Gauge)
    - hsi_detection_confidence (Histogram)
    - hsi_detections_processed_total (Counter)
    - hsi_detections_by_class_total (Counter)
    - hsi_detections_filtered_low_confidence_total (Counter)

    Args:
        num_samples: Number of detection events to simulate

    Returns:
        Dictionary with counts of seeded metrics
    """
    from backend.core.metrics import (
        DETECTION_CONFIDENCE,
        DETECTION_QUEUE_DEPTH,
        DETECTIONS_BY_CLASS_TOTAL,
        DETECTIONS_FILTERED_LOW_CONFIDENCE_TOTAL,
        DETECTIONS_PROCESSED_TOTAL,
    )

    cameras = await get_cameras()
    camera_ids = [c.id for c in cameras] if cameras else ["cam_default"]

    object_classes = ["person", "car", "truck", "dog", "cat", "bicycle", "package", "bird"]
    class_weights = [0.40, 0.20, 0.10, 0.08, 0.07, 0.05, 0.07, 0.03]

    counts = {
        "detections_processed": 0,
        "detection_confidences": 0,
        "detections_by_class": 0,
        "detections_filtered": 0,
        "queue_depth_updates": 0,
    }

    for _ in range(num_samples):
        object_class = random.choices(object_classes, weights=class_weights, k=1)[0]  # noqa: S311

        # Detection confidence: 0.3 to 0.99
        confidence = random.uniform(0.3, 0.99)  # noqa: S311

        # Record detection (no labels)
        DETECTIONS_PROCESSED_TOTAL.inc()
        counts["detections_processed"] += 1

        # Confidence histogram (no labels)
        DETECTION_CONFIDENCE.observe(confidence)
        counts["detection_confidences"] += 1

        # Detection by class (labels: object_class only)
        DETECTIONS_BY_CLASS_TOTAL.labels(object_class=object_class).inc()
        counts["detections_by_class"] += 1

        # Low confidence detections (< 0.5) get filtered (no labels)
        if confidence < 0.5:
            DETECTIONS_FILTERED_LOW_CONFIDENCE_TOTAL.inc()
            counts["detections_filtered"] += 1

    # Set queue depth (current number of items waiting)
    queue_depth = random.randint(0, 20)  # noqa: S311
    DETECTION_QUEUE_DEPTH.set(queue_depth)
    counts["queue_depth_updates"] = 1

    print(f"  Seeded {counts['detections_processed']} detections processed")
    print(f"  Seeded {counts['detections_by_class']} detections by class")
    print(f"  Seeded {counts['detections_filtered']} low-confidence detections filtered")
    return counts


async def seed_event_metrics(num_samples: int = 30) -> dict[str, int]:
    """Simulate event creation and review metrics.

    Seeds:
    - hsi_events_created_total (Counter)
    - hsi_events_by_risk_level_total (Counter)
    - hsi_events_by_camera_total (Counter)
    - hsi_events_reviewed_total (Counter)
    - hsi_events_acknowledged_total (Counter)
    - hsi_event_analysis_cost_usd_total (Counter)
    - hsi_cost_per_event_usd (Gauge)

    Args:
        num_samples: Number of event metrics to simulate

    Returns:
        Dictionary with counts of seeded metrics
    """
    from backend.core.metrics import (
        COST_PER_EVENT_USD,
        EVENT_ANALYSIS_COST_USD,
        EVENTS_ACKNOWLEDGED_TOTAL,
        EVENTS_BY_CAMERA_TOTAL,
        EVENTS_BY_RISK_LEVEL,
        EVENTS_CREATED_TOTAL,
        EVENTS_REVIEWED_TOTAL,
    )

    cameras = await get_cameras()
    # Build camera info with both id and name
    camera_info = [(c.id, c.name) for c in cameras] if cameras else [("cam_default", "Default")]

    risk_levels = ["low", "medium", "high", "critical"]
    risk_weights = [0.50, 0.30, 0.15, 0.05]

    counts = {
        "events_created": 0,
        "events_by_risk": 0,
        "events_by_camera": 0,
        "events_reviewed": 0,
        "events_acknowledged": 0,
        "cost_updates": 0,
    }

    total_cost = 0.0

    for _ in range(num_samples):
        camera_id, camera_name = random.choice(camera_info)  # noqa: S311
        risk_level = random.choices(risk_levels, weights=risk_weights, k=1)[0]  # noqa: S311

        # Event creation (no labels)
        EVENTS_CREATED_TOTAL.inc()
        counts["events_created"] += 1

        # Events by risk level (labels: level)
        EVENTS_BY_RISK_LEVEL.labels(level=risk_level).inc()
        counts["events_by_risk"] += 1

        # Events by camera (labels: camera_id, camera_name)
        EVENTS_BY_CAMERA_TOTAL.labels(camera_id=camera_id, camera_name=camera_name).inc()
        counts["events_by_camera"] += 1

        # 60% of events are reviewed (no labels)
        if random.random() < 0.6:  # noqa: S311
            EVENTS_REVIEWED_TOTAL.inc()
            counts["events_reviewed"] += 1

        # 40% of events are acknowledged (labels: camera_name, risk_level)
        if random.random() < 0.4:  # noqa: S311
            EVENTS_ACKNOWLEDGED_TOTAL.labels(camera_name=camera_name, risk_level=risk_level).inc()
            counts["events_acknowledged"] += 1

        # Analysis cost: $0.001 to $0.05 per event (labels: camera_id)
        cost = random.uniform(0.001, 0.05)  # noqa: S311
        EVENT_ANALYSIS_COST_USD.labels(camera_id=camera_id).inc(cost)
        total_cost += cost
        counts["cost_updates"] += 1

    # Set average cost per event
    avg_cost = total_cost / num_samples if num_samples > 0 else 0.0
    COST_PER_EVENT_USD.set(avg_cost)

    print(f"  Seeded {counts['events_created']} events created metrics")
    print(f"  Seeded {counts['events_reviewed']} events reviewed metrics")
    print(f"  Seeded {counts['events_acknowledged']} events acknowledged metrics")
    return counts


async def seed_metrics_layer() -> dict[str, int]:
    """Seed all metrics data (Phase 7).

    Exercises Prometheus metrics to ensure all dashboard panels show data.

    Returns:
        Dictionary with counts of seeded metrics
    """
    counts: dict[str, int] = {}

    print("\n  Step 1: Seeding face recognition metrics...")
    face_counts = await seed_face_recognition_metrics()
    counts["face_detections"] = face_counts.get("face_detections", 0)

    print("\n  Step 2: Seeding action recognition metrics...")
    action_counts = await seed_action_recognition_metrics()
    counts["action_recognitions"] = action_counts.get("action_recognitions", 0)
    counts["loitering_alerts"] = action_counts.get("loitering_alerts", 0)

    print("\n  Step 3: Seeding circuit breaker metrics...")
    cb_counts = await seed_circuit_breaker_metrics()
    counts["circuit_breaker_trips"] = cb_counts.get("trips", 0)

    print("\n  Step 4: Seeding cache metrics...")
    cache_counts = await seed_cache_metrics()
    counts["cache_hits"] = cache_counts.get("cache_hits", 0)
    counts["cache_misses"] = cache_counts.get("cache_misses", 0)

    print("\n  Step 5: Seeding DLQ metrics...")
    dlq_counts = await seed_dlq_metrics()
    counts["dlq_items"] = dlq_counts.get("items_moved_to_dlq", 0)

    print("\n  Step 6: Seeding RUM metrics...")
    rum_counts = await seed_rum_metrics()
    counts["rum_page_loads"] = rum_counts.get("page_loads", 0)

    print("\n  Step 7: Seeding Re-ID metrics...")
    reid_counts = await seed_reid_metrics()
    counts["reid_tracks"] = reid_counts.get("tracks_reidentified", 0)

    print("\n  Step 8: Seeding track metrics...")
    track_counts = await seed_track_metrics()
    counts["tracks_created"] = track_counts.get("tracks_created", 0)
    counts["tracks_lost"] = track_counts.get("tracks_lost", 0)

    print("\n  Step 9: Seeding zone metrics...")
    zone_counts = await seed_zone_metrics()
    counts["zone_crossings"] = zone_counts.get("zone_crossings", 0)
    counts["zone_intrusions"] = zone_counts.get("zone_intrusions", 0)

    print("\n  Step 10: Seeding worker metrics...")
    worker_counts = await seed_worker_metrics()
    counts["worker_restarts"] = worker_counts.get("worker_restarts", 0)
    counts["worker_crashes"] = worker_counts.get("worker_crashes", 0)

    print("\n  Step 11: Seeding GPU metrics...")
    gpu_counts = await seed_gpu_metrics()
    counts["gpu_seconds"] = gpu_counts.get("gpu_seconds", 0)

    print("\n  Step 12: Seeding detection metrics...")
    detection_counts = await seed_detection_metrics()
    counts["detections_processed"] = detection_counts.get("detections_processed", 0)

    print("\n  Step 13: Seeding event metrics...")
    event_counts = await seed_event_metrics()
    counts["events_metrics"] = event_counts.get("events_created", 0)

    print("\n  Step 14: Seeding A/B testing metrics...")
    ab_counts = await seed_ab_testing_metrics()
    counts["ab_analyses"] = ab_counts.get("analyses", 0)
    counts["ab_feedback"] = ab_counts.get("feedback_submissions", 0)

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

        print("  Clearing properties...")
        await session.execute(delete(Property))

        print("  Clearing households...")
        await session.execute(delete(Household))

        # Original tables
        print("  Clearing plate reads...")
        await session.execute(delete(PlateRead))

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
  # DEFAULT: Process synthetic videos from data/synthetic/ (recommended)
  uv run python scripts/seed-events.py

  # Process specific number of synthetic scenarios
  uv run python scripts/seed-events.py --scenarios 50

  # Process only specific categories
  uv run python scripts/seed-events.py --categories normal,suspicious

  # Process synthetic data and validate results
  uv run python scripts/seed-events.py --validate

  # Legacy mode: Touch existing images from /export/foscam
  uv run python scripts/seed-events.py --existing-data --images 100

  # Config only - setup without heavy AI data
  uv run python scripts/seed-events.py --config-only

  # Clear all data first, then run full pipeline
  uv run python scripts/seed-events.py --clear

  # Quick run without waiting for pipeline completion
  uv run python scripts/seed-events.py --no-wait

Pipeline Flow:
  1. Extract frames from synthetic videos (or touch existing images with --existing-data)
  2. File Watcher → YOLO26 (object detection)
  3. YOLO26 → Batch Aggregator (group detections)
  4. Batch Aggregator → Nemotron LLM (risk analysis)
  5. Events created with AI-generated summaries and risk scores

Synthetic Data Benefits:
  - Known expected labels for validation (expected_labels.json)
  - Repeatable test scenarios across categories (normal, suspicious, threats)
  - Detection accuracy and risk score calibration metrics
  - End-to-end pipeline testing with controlled inputs

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
        default=600,
        help="Max seconds to wait for pipeline completion (default: 600)",
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
        "--no-metrics",
        action="store_true",
        help="Skip seeding Prometheus metrics data (face, action, cache, DLQ, RUM metrics)",
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
        default=0,
        help="Number of events to soft-delete for trash (default: 0)",
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

    # Synthetic data arguments (DEFAULT behavior)
    parser.add_argument(
        "--existing-data",
        action="store_true",
        help="Legacy mode: touch images from /export/foscam instead of using synthetic data",
    )
    parser.add_argument(
        "--scenarios",
        type=int,
        default=10,
        help="Number of synthetic scenarios per category (default: 10, totaling ~30)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="all_scenarios",
        help="Process all available synthetic scenarios (overrides --scenarios)",
    )
    parser.add_argument(
        "--categories",
        type=str,
        default=None,
        help="Comma-separated list of categories to process (normal,suspicious,threats)",
    )
    parser.add_argument(
        "--frames-per-video",
        type=int,
        default=5,
        help="Number of frames to extract from each synthetic video (default: 5)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate pipeline results against expected labels after processing",
    )
    parser.add_argument(
        "--report-path",
        type=str,
        default=None,
        help="Path to save validation report JSON (default: data/synthetic/validation_report.json)",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help=(
            "Process all categories simultaneously (default: sequential with 90s gaps "
            "to prevent cross-camera contamination inflating normal event scores)"
        ),
    )
    parser.add_argument(
        "--camera-strategy",
        choices=["scenario", "category"],
        default="scenario",
        help=(
            "Camera assignment strategy for synthetic scenarios: "
            "'scenario' (default, isolated camera per scenario for clean timeline mapping) "
            "or 'category' (legacy shared camera per category)"
        ),
    )
    parser.add_argument(
        "--reasoning-retries",
        type=int,
        default=2,
        help=(
            "Automatically retry weakly reasoned scenarios with alternate synthetic events "
            "(default: 2 rounds, set 0 to disable)"
        ),
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

    # ==========================================================================
    # ADMIN USER (required before anything else -- SetupGuardMiddleware blocks
    # all API endpoints with HTTP 503 until at least one user exists)
    # ==========================================================================
    print("\n" + "=" * 50)
    print("ENSURING ADMIN USER EXISTS")
    print("=" * 50)
    await seed_admin_user()

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
    synthetic_scenarios: list[SyntheticScenario] = []
    selected_categories: list[str] | None = None

    if not args.config_only:
        # Get initial event count
        initial_events = await get_events()
        initial_count = len(initial_events)

        print("\n" + "=" * 50)
        print("TRIGGERING REAL AI PIPELINE")
        print("=" * 50)
        print(f"Current events in database: {initial_count}")

        # --- Pre-flight health check (Fix #5) ---
        # Verify AI services are healthy before triggering the pipeline.
        # If any service is unhealthy, warn the user and allow a short wait.
        import httpx as _httpx

        api_port = os.environ.get("API_PORT", "8000")
        health_url = f"http://localhost:{api_port}/api/system/health"
        try:
            async with _httpx.AsyncClient(timeout=10.0) as _hc:
                health_resp = await _hc.get(health_url)
                if health_resp.status_code == 200:
                    health_data = health_resp.json()
                    health_status = health_data.get("status", "unknown")
                    if health_status == "healthy":
                        print("  Pre-flight check: System healthy")
                    else:
                        print(f"  WARNING: System not fully healthy: {health_status}")
                        # Print individual service statuses if available
                        services = health_data.get("services", {})
                        for svc_name, svc_info in services.items():
                            svc_status = (
                                svc_info
                                if isinstance(svc_info, str)
                                else svc_info.get("status", "unknown")
                            )
                            if svc_status != "healthy":
                                print(f"    - {svc_name}: {svc_status}")
                        print("  Continuing anyway, but pipeline results may be incomplete...")
                else:
                    print(f"  WARNING: Health check returned HTTP {health_resp.status_code}")
                    print("  Continuing anyway...")
        except Exception as _health_err:
            print(f"  WARNING: Could not reach health endpoint ({health_url}): {_health_err}")
            print("  Continuing anyway (API may not be running)...")

        if args.existing_data:
            # Legacy mode: touch existing images in /export/foscam
            print("\n[LEGACY MODE] Using existing camera images from /export/foscam")
            touched = trigger_pipeline(num_images=args.images, delay_between=args.delay)
            total_created["images_triggered"] = touched
        else:
            # DEFAULT: Use synthetic video data
            print("\n[SYNTHETIC MODE] Processing synthetic videos from data/synthetic/")

            # Parse categories if specified
            categories = None
            if args.categories:
                categories = [c.strip() for c in args.categories.split(",")]
                print(f"  Categories: {', '.join(categories)}")
            selected_categories = categories

            # Discover synthetic scenarios
            # --all overrides --scenarios to process everything
            per_category_limit = None if args.all_scenarios else args.scenarios
            synthetic_scenarios = discover_synthetic_scenarios(
                categories=categories,
                per_category_limit=per_category_limit,
            )

            if not synthetic_scenarios:
                print("Warning: No synthetic scenarios found")
                print(f"  Check that {SYNTHETIC_DATA_PATH} exists and contains Cosmos videos")
                touched = 0
            else:
                print(f"  Found {len(synthetic_scenarios)} synthetic scenarios")
                by_cat: dict[str, int] = {}
                for s in synthetic_scenarios:
                    by_cat[s.category] = by_cat.get(s.category, 0) + 1
                for cat, count in sorted(by_cat.items()):
                    print(f"    - {cat}: {count}")

                if args.parallel:
                    # --parallel: Process all scenarios together (faster but may
                    # have cross-camera contamination between categories)
                    touched, _frame_paths = await seed_synthetic_scenarios(
                        scenarios=synthetic_scenarios,
                        frames_per_video=args.frames_per_video,
                        delay_between=args.delay,
                        camera_strategy=args.camera_strategy,
                    )
                else:
                    # Default: Process one category at a time with a 90-second
                    # gap between categories. This prevents cross-camera contamination
                    # where normal events get inflated scores because they are processed
                    # simultaneously with threat events on different cameras, triggering
                    # the cross-camera correlation feature.

                    BATCH_WINDOW_GAP = 90  # Match the 90-second batch window
                    categories_in_order = sorted(by_cat.keys())
                    touched = 0

                    for cat_idx, cat_name in enumerate(categories_in_order):
                        cat_scenarios = [s for s in synthetic_scenarios if s.category == cat_name]
                        print(
                            f"\n  [Sequential] Processing category: {cat_name} "
                            f"({len(cat_scenarios)} scenarios)"
                        )

                        cat_touched, _cat_frames = await seed_synthetic_scenarios(
                            scenarios=cat_scenarios,
                            frames_per_video=args.frames_per_video,
                            delay_between=args.delay,
                            camera_strategy=args.camera_strategy,
                        )
                        touched += cat_touched

                        # Wait for the batch window gap before next category
                        if cat_idx < len(categories_in_order) - 1:
                            print(
                                f"\n  [Sequential] Waiting {BATCH_WINDOW_GAP}s for batch "
                                f"window to close before next category..."
                            )
                            await asyncio.sleep(BATCH_WINDOW_GAP)

                total_created["frames_extracted"] = touched
                total_created["synthetic_scenarios"] = len(synthetic_scenarios)

        # Wait for pipeline completion unless --no-wait
        if not args.no_wait and touched > 0:
            num_scenarios = len(synthetic_scenarios) if synthetic_scenarios else touched // 5
            if args.camera_strategy == "scenario":
                # Default isolated mode: target roughly one event per scenario.
                expected_events = max(1, min(num_scenarios, touched))
            else:
                # Legacy category camera mode can coalesce many detections per event.
                expected_events = max(5, min(num_scenarios * 2 // 3, touched // 3))
            expected_camera_ids: set[str] | None = None
            if synthetic_scenarios:
                expected_camera_ids = {
                    (s.assigned_camera_id or get_test_camera_for_category(s.category))
                    for s in synthetic_scenarios
                }
                print(
                    "Waiting for coverage across cameras: " + ", ".join(sorted(expected_camera_ids))
                )
            _final_count, new_events, success = await wait_for_pipeline_completion(
                initial_event_count=initial_count,
                expected_min_events=expected_events,
                timeout_seconds=max(args.timeout, 600),  # Ensure at least 600s timeout
                expected_camera_ids=expected_camera_ids,
            )
            total_created["events_created"] = new_events

            if not success:
                print("\nWarning: Pipeline may not have completed fully")
                print("  Check that AI services (YOLO26, Nemotron) are running")

            # Resilience by default: if reasoning quality is weak, automatically
            # seed alternate scenarios from the same categories and try again.
            if synthetic_scenarios and args.reasoning_retries > 0:
                processed_scenarios = list(synthetic_scenarios)
                used_video_ids = {s.video_id for s in processed_scenarios}
                all_available_scenarios = discover_synthetic_scenarios(
                    categories=selected_categories,
                    per_category_limit=None,
                )

                for retry_round in range(1, args.reasoning_retries + 1):
                    validation_snapshot = await validate_synthetic_results(processed_scenarios)
                    weak_results = _find_weak_reasoning_results(validation_snapshot)
                    if not weak_results:
                        print("\n✓ Reasoning resilience check passed (no weak scenarios detected)")
                        break

                    print(
                        f"\nReasoning resilience round {retry_round}/{args.reasoning_retries}: "
                        f"{len(weak_results)} weak scenarios detected"
                    )
                    retry_scenarios = _select_retry_scenarios(
                        all_available=all_available_scenarios,
                        weak_results=weak_results,
                        used_video_ids=used_video_ids,
                    )
                    if not retry_scenarios:
                        print("  No alternate scenarios left to retry for weak categories")
                        break

                    print(f"  Retrying with {len(retry_scenarios)} alternate scenarios")
                    retry_initial_events = await get_events()
                    retry_touched, _retry_paths = await seed_synthetic_scenarios(
                        scenarios=retry_scenarios,
                        frames_per_video=args.frames_per_video,
                        delay_between=args.delay,
                        camera_strategy=args.camera_strategy,
                    )
                    if retry_touched <= 0:
                        print("  Retry seeding produced no frames; stopping resilience retries")
                        break

                    if args.camera_strategy == "scenario":
                        retry_expected_events = max(1, len(retry_scenarios))
                    else:
                        retry_expected_events = max(
                            1, min(len(retry_scenarios), retry_touched // 3)
                        )
                    retry_expected_cameras = {
                        (s.assigned_camera_id or get_test_camera_for_category(s.category))
                        for s in retry_scenarios
                    }
                    (
                        _retry_final,
                        retry_new_events,
                        retry_success,
                    ) = await wait_for_pipeline_completion(
                        initial_event_count=len(retry_initial_events),
                        expected_min_events=retry_expected_events,
                        timeout_seconds=max(300, args.timeout // 2),
                        expected_camera_ids=retry_expected_cameras,
                    )
                    total_created["events_created"] = (
                        total_created.get("events_created", 0) + retry_new_events
                    )
                    if not retry_success:
                        print("  Retry pipeline window ended without full success")

                    processed_scenarios.extend(retry_scenarios)
                    used_video_ids.update(s.video_id for s in retry_scenarios)
                    total_created["synthetic_scenarios"] = len(processed_scenarios)
                    total_created["frames_extracted"] = (
                        total_created.get("frames_extracted", 0) + retry_touched
                    )

                synthetic_scenarios = processed_scenarios

            # Validate results if requested and using synthetic data
            if args.validate and synthetic_scenarios:
                print("\n" + "=" * 50)
                print("VALIDATING SYNTHETIC RESULTS")
                print("=" * 50)

                validation_results = await validate_synthetic_results(synthetic_scenarios)
                report_path = Path(
                    args.report_path or str(SYNTHETIC_DATA_PATH / "validation_report.json")
                )
                report = generate_validation_report(validation_results, report_path)
                print_validation_summary(report)

                total_created["validation_passed"] = report["summary"]["passed"]
                total_created["validation_failed"] = report["summary"]["failed"]

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

            print("\nSeeding plate reads...")
            total_created["plate_reads"] = await seed_plate_reads()

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

        # Seed cost tracking data for Cost Analytics Dashboard
        if not args.no_metrics:
            print("\nSeeding cost tracking data (30 days)...")
            total_created["cost_tracking_days"] = await seed_cost_tracking_data()

        # ==========================================================================
        # PHASE 7: METRICS LAYER (unless --minimal or --no-metrics)
        # ==========================================================================
        if not args.minimal and not args.no_metrics:
            print("\n" + "=" * 50)
            print("SEEDING METRICS LAYER (Phase 7)")
            print("=" * 50)
            print("Creating face recognition, action, circuit breaker, cache, DLQ, RUM metrics...")

            metrics_counts = await seed_metrics_layer()
            total_created.update(metrics_counts)
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
    print(f"  Total plate reads: {counts['plate_reads']}")
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
        print("  Metrics layer (Phase 7):")
        print(f"    - Face detections: {total_created.get('face_detections', 0)}")
        print(f"    - Action recognitions: {total_created.get('action_recognitions', 0)}")
        print(f"    - Loitering alerts: {total_created.get('loitering_alerts', 0)}")
        print(f"    - Circuit breaker trips: {total_created.get('circuit_breaker_trips', 0)}")
        print(f"    - Cache hits: {total_created.get('cache_hits', 0)}")
        print(f"    - Cache misses: {total_created.get('cache_misses', 0)}")
        print(f"    - DLQ items: {total_created.get('dlq_items', 0)}")
        print(f"    - RUM page loads: {total_created.get('rum_page_loads', 0)}")
        print(f"    - Re-ID tracks: {total_created.get('reid_tracks', 0)}")
        print(f"    - Tracks created: {total_created.get('tracks_created', 0)}")
        print(f"    - Tracks lost: {total_created.get('tracks_lost', 0)}")
        print(f"    - Zone crossings: {total_created.get('zone_crossings', 0)}")
        print(f"    - Zone intrusions: {total_created.get('zone_intrusions', 0)}")
        print(f"    - Worker restarts: {total_created.get('worker_restarts', 0)}")
        print(f"    - Worker crashes: {total_created.get('worker_crashes', 0)}")
        print(f"    - GPU seconds: {total_created.get('gpu_seconds', 0)}")
        print(f"    - Detections processed: {total_created.get('detections_processed', 0)}")
        print(f"    - Event metrics: {total_created.get('events_metrics', 0)}")

    # Print synthetic data stats if used
    if not args.existing_data and "synthetic_scenarios" in total_created:
        print("  Synthetic data:")
        print(f"    - Scenarios processed: {total_created.get('synthetic_scenarios', 0)}")
        print(f"    - Frames extracted: {total_created.get('frames_extracted', 0)}")
        if "validation_passed" in total_created:
            passed = total_created.get("validation_passed", 0)
            failed = total_created.get("validation_failed", 0)
            total = passed + failed
            rate = f"{(passed / total * 100):.1f}%" if total > 0 else "N/A"
            print(f"    - Validation: {passed}/{total} passed ({rate})")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
