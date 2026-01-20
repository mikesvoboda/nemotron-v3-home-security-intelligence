"""On-demand enrichment models for the ai-enrichment service.

This package contains model implementations that can be loaded on-demand
to reduce VRAM usage when not needed.

Models:
- ActionRecognizer: X-CLIP video action recognition (~1.5GB VRAM)
- DemographicsEstimator: ViT-based age and gender estimation (~500MB VRAM)
- PersonReID: OSNet-x0.25 for person re-identification (~100MB VRAM)
- PoseEstimator: YOLOv8n-pose for human pose estimation (~300MB VRAM)
- ThreatDetector: Weapon detection YOLOv8 variant (~400MB VRAM, CRITICAL priority)
"""

from ai.enrichment.models.action_recognizer import (
    SECURITY_ACTIONS,
    SUSPICIOUS_ACTIONS,
    ActionRecognizer,
    ActionResult,
    load_action_recognizer,
)
from ai.enrichment.models.demographics import (
    AGE_RANGES,
    DEFAULT_AGE_CONFIDENCE_THRESHOLD,
    DEFAULT_GENDER_CONFIDENCE_THRESHOLD,
    GENDER_LABELS,
    DemographicsEstimator,
    DemographicsResult,
    load_demographics,
)
from ai.enrichment.models.person_reid import (
    DEFAULT_SIMILARITY_THRESHOLD,
    EMBEDDING_DIMENSION,
    PersonReID,
    ReIDResult,
    load_person_reid,
)
from ai.enrichment.models.pose_estimator import (
    KEYPOINT_NAMES,
    SUSPICIOUS_POSES,
    Keypoint,
    PoseEstimator,
    PoseResult,
    load_pose_estimator,
)
from ai.enrichment.models.threat_detector import (
    SEVERITY_ORDER,
    THREAT_CLASSES,
    THREAT_CLASSES_BY_NAME,
    ThreatDetection,
    ThreatDetector,
    ThreatResult,
    load_threat_detector,
)

__all__ = [
    "AGE_RANGES",
    "DEFAULT_AGE_CONFIDENCE_THRESHOLD",
    "DEFAULT_GENDER_CONFIDENCE_THRESHOLD",
    "DEFAULT_SIMILARITY_THRESHOLD",
    "EMBEDDING_DIMENSION",
    "GENDER_LABELS",
    "KEYPOINT_NAMES",
    "SECURITY_ACTIONS",
    "SEVERITY_ORDER",
    "SUSPICIOUS_ACTIONS",
    "SUSPICIOUS_POSES",
    "THREAT_CLASSES",
    "THREAT_CLASSES_BY_NAME",
    "ActionRecognizer",
    "ActionResult",
    "DemographicsEstimator",
    "DemographicsResult",
    "Keypoint",
    "PersonReID",
    "PoseEstimator",
    "PoseResult",
    "ReIDResult",
    "ThreatDetection",
    "ThreatDetector",
    "ThreatResult",
    "load_action_recognizer",
    "load_demographics",
    "load_person_reid",
    "load_pose_estimator",
    "load_threat_detector",
]
