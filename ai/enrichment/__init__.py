"""Combined Enrichment Service package.

HTTP server hosting multiple classification models for enriching YOLO26v2
detections with additional attributes.

Models hosted:
- VehicleClassifier: Vehicle type classification (~1.5GB)
- PetClassifier: Cat/dog classification (~200MB)
- ClothingClassifier: Zero-shot clothing classification with FashionCLIP (~800MB)
- DepthEstimator: Monocular depth estimation with Depth Anything V2 (~150MB)
- PoseAnalyzer: Human pose estimation with ViTPose+ (~100MB)

Analytics:
- LoiteringDetector: Real-time tracking of object dwell time in zones

Port: 8094 (configurable via PORT env var)
"""

from ai.enrichment.loitering_detector import (
    LoiteringAlertData,
    LoiteringDetector,
    TrackedObject,
    ZoneConfig,
    get_loitering_detector,
    reset_loitering_detector,
)
from ai.enrichment.model_manager import (
    ModelConfig,
    ModelInfo,
    ModelPriority,
    OnDemandModelManager,
)

__all__ = [
    "LoiteringAlertData",
    "LoiteringDetector",
    "ModelConfig",
    "ModelInfo",
    "ModelPriority",
    "OnDemandModelManager",
    "TrackedObject",
    "ZoneConfig",
    "get_loitering_detector",
    "reset_loitering_detector",
]
