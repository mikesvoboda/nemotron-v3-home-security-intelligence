"""On-demand enrichment models for the ai-enrichment service.

This package contains model implementations that can be loaded on-demand
to reduce VRAM usage when not needed.

Models:
- ActionRecognizer: X-CLIP video action recognition (~1.5GB VRAM)
- DemographicsEstimator: ViT-based age and gender estimation (~500MB VRAM)
- FaceRecognizer: InsightFace face detection and recognition (~1.5GB VRAM)
- PersonReID: OSNet-x0.25 for person re-identification (~100MB VRAM)
- PlateOCR: PaddleOCR-based license plate text recognition (~500MB VRAM)
- PoseEstimator: YOLOv8n-pose for human pose estimation (~300MB VRAM)
- ThreatDetector: Weapon detection YOLOv8 variant (~400MB VRAM, CRITICAL priority)
- YOLO26Detector: YOLO26 secondary object detection (~100MB VRAM, LOW priority)
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
from ai.enrichment.models.face_recognizer import (
    DEFAULT_MATCH_THRESHOLD,
    FaceRecognizer,
    FaceResult,
    MatchResult,
    load_face_recognizer,
)
from ai.enrichment.models.face_recognizer import (
    EMBEDDING_DIMENSION as FACE_EMBEDDING_DIMENSION,
)
from ai.enrichment.models.face_recognizer import (
    MIN_QUALITY_THRESHOLD as FACE_MIN_QUALITY_THRESHOLD,
)
from ai.enrichment.models.person_reid import (
    DEFAULT_SIMILARITY_THRESHOLD,
    EMBEDDING_DIMENSION,
    PersonReID,
    ReIDResult,
    load_person_reid,
)
from ai.enrichment.models.plate_ocr import (
    LOW_LIGHT_THRESHOLD,
    MIN_QUALITY_SCORE,
    MOTION_BLUR_THRESHOLD,
    VALID_CHARS,
    PlateOCR,
    PlateOCRResult,
    load_plate_ocr,
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
from ai.enrichment.models.yolo26_detector import (
    COCO_CLASSES,
    YOLO26_DEFAULT_MODEL,
    YOLO26_MODEL_PATH_ENV,
    Detection,
    YOLO26Detector,
    YOLO26Result,
    load_yolo26_detector,
)

__all__ = [
    "AGE_RANGES",
    "COCO_CLASSES",
    "DEFAULT_AGE_CONFIDENCE_THRESHOLD",
    "DEFAULT_GENDER_CONFIDENCE_THRESHOLD",
    "DEFAULT_MATCH_THRESHOLD",
    "DEFAULT_SIMILARITY_THRESHOLD",
    "EMBEDDING_DIMENSION",
    "FACE_EMBEDDING_DIMENSION",
    "FACE_MIN_QUALITY_THRESHOLD",
    "GENDER_LABELS",
    "KEYPOINT_NAMES",
    "LOW_LIGHT_THRESHOLD",
    "MIN_QUALITY_SCORE",
    "MOTION_BLUR_THRESHOLD",
    "SECURITY_ACTIONS",
    "SEVERITY_ORDER",
    "SUSPICIOUS_ACTIONS",
    "SUSPICIOUS_POSES",
    "THREAT_CLASSES",
    "THREAT_CLASSES_BY_NAME",
    "VALID_CHARS",
    "YOLO26_DEFAULT_MODEL",
    "YOLO26_MODEL_PATH_ENV",
    "ActionRecognizer",
    "ActionResult",
    "DemographicsEstimator",
    "DemographicsResult",
    "Detection",
    "FaceRecognizer",
    "FaceResult",
    "Keypoint",
    "MatchResult",
    "PersonReID",
    "PlateOCR",
    "PlateOCRResult",
    "PoseEstimator",
    "PoseResult",
    "ReIDResult",
    "ThreatDetection",
    "ThreatDetector",
    "ThreatResult",
    "YOLO26Detector",
    "YOLO26Result",
    "load_action_recognizer",
    "load_demographics",
    "load_face_recognizer",
    "load_person_reid",
    "load_plate_ocr",
    "load_pose_estimator",
    "load_threat_detector",
    "load_yolo26_detector",
]
