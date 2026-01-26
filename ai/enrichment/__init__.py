"""Combined Enrichment Service package.

HTTP server hosting multiple classification models for enriching YOLO26v2
detections with additional attributes.

Models hosted:
- VehicleClassifier: Vehicle type classification (~1.5GB)
- PetClassifier: Cat/dog classification (~200MB)
- ClothingClassifier: Zero-shot clothing classification with FashionCLIP (~800MB)
- DepthEstimator: Monocular depth estimation with Depth Anything V2 (~150MB)
- PoseAnalyzer: Human pose estimation with ViTPose+ (~100MB)

Port: 8094 (configurable via PORT env var)
"""

from ai.enrichment.model_manager import (
    ModelConfig,
    ModelInfo,
    ModelPriority,
    OnDemandModelManager,
)

__all__ = [
    "ModelConfig",
    "ModelInfo",
    "ModelPriority",
    "OnDemandModelManager",
]
