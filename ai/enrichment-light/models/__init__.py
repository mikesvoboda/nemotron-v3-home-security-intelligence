"""Lightweight enrichment models for GPU 1 (A400 4GB).

This package contains small, efficient models suitable for the secondary GPU:
- PoseEstimator: YOLOv8n-pose body keypoint detection (~300MB, TensorRT-optimized)
- ThreatDetector: YOLOv8n weapon detection (~400MB, TensorRT-optimized)
- PersonReID: OSNet-x0.25 re-identification embeddings (~100MB)
- PetClassifier: Cat/dog classification (~200MB)
- DepthEstimator: Monocular depth estimation (~150MB)
"""

from models.person_reid import PersonReID
from models.pose_estimator import PoseEstimator
from models.threat_detector import ThreatDetector

__all__ = [
    "PersonReID",
    "PoseEstimator",
    "ThreatDetector",
]
