"""Model Registry for On-Demand Model Loading.

This module defines the model configurations and registry for the enrichment service.
Each model has a configuration that specifies its VRAM requirements, priority,
loader/unloader functions, and loading triggers.

The registry is used by OnDemandModelManager to know which models are available
and how to load them on-demand when needed for specific detection types.

Available models (10 total):
- fashion_clip: Clothing attribute extraction (FashionSigLIP, ~800MB, MEDIUM priority)
- vehicle_classifier: Vehicle type classification (~1.5GB, MEDIUM priority)
- pet_classifier: Cat/dog classification (~200MB, MEDIUM priority)
- depth_estimator: Monocular depth estimation (~150MB, LOW priority)
- pose_estimator: YOLOv8n-pose body posture (~300MB, HIGH priority)
- threat_detector: Weapon detection (~400MB, CRITICAL priority)
- demographics: Age-gender from face crops (~500MB, HIGH priority)
- person_reid: OSNet re-identification (~100MB, MEDIUM priority)
- action_recognizer: X-CLIP video action recognition (~2GB, LOW priority)
- yolo26_detector: YOLO26 secondary object detection (~100MB, LOW priority)
"""

from __future__ import annotations

import logging
import os
from typing import Any

import torch

# Import ModelPriority and ModelConfig from model_manager to avoid duplication
try:
    # When running from tests or as a package
    from ai.enrichment.model_manager import ModelConfig, ModelPriority
except ImportError:
    # When running from within the enrichment directory
    from model_manager import ModelConfig, ModelPriority

logger = logging.getLogger(__name__)


# =============================================================================
# Unloader Functions
# =============================================================================


def unload_torch_model(model: Any) -> None:
    """Generic unloader for PyTorch models.

    Properly releases GPU memory by deleting model attributes
    and clearing the CUDA cache.

    Args:
        model: The model instance to unload. Can be any model with
               GPU tensors that needs cleanup.
    """
    # Handle classifier-style models with multiple attributes
    if hasattr(model, "model") and model.model is not None:
        del model.model
        model.model = None

    if hasattr(model, "processor") and model.processor is not None:
        del model.processor
        model.processor = None

    if hasattr(model, "transform") and model.transform is not None:
        del model.transform
        model.transform = None

    if hasattr(model, "tokenizer") and model.tokenizer is not None:
        del model.tokenizer
        model.tokenizer = None

    if hasattr(model, "preprocess") and model.preprocess is not None:
        del model.preprocess
        model.preprocess = None

    # Clear CUDA cache to actually free VRAM
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    logger.debug("PyTorch model unloaded, CUDA cache cleared")


def unload_model_with_processor(model_tuple: tuple[Any, Any] | Any) -> None:
    """Unloader for models that come with a processor.

    Some models (like transformers) return both a model and processor.
    This unloader handles cleaning up both components.

    Args:
        model_tuple: Tuple of (model, processor) to unload, or a single model.
    """
    if isinstance(model_tuple, tuple):
        model, processor = model_tuple
        if model is not None:
            del model
        if processor is not None:
            del processor
    elif model_tuple is not None:
        del model_tuple

    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    logger.debug("Model and processor unloaded, CUDA cache cleared")


# =============================================================================
# Loader Functions for New Models
# =============================================================================


def load_pose_estimator(model_path: str, device: str = "cuda:0") -> Any:
    """Load YOLOv8n-pose model for body posture detection.

    Detects 17 body keypoints and can be used to classify posture
    (standing, crouching, bending, arms raised).

    Args:
        model_path: Path to the YOLOv8n-pose model file.
        device: CUDA device string for model placement.

    Returns:
        Loaded YOLO pose model instance.

    Note:
        Requires ultralytics package. The model auto-downloads
        if not found at the specified path.
    """
    try:
        from ultralytics import YOLO
    except ImportError as e:
        logger.error("ultralytics package required for pose estimation")
        raise ImportError(
            "ultralytics package is required for pose estimation. "
            "Install with: pip install ultralytics"
        ) from e

    model = YOLO(model_path)
    if "cuda" in device and torch.cuda.is_available():
        model.to(device)
    logger.info(f"Pose estimator (YOLOv8n-pose) loaded from {model_path}")
    return model


def load_threat_detector(model_path: str, device: str = "cuda:0") -> Any:
    """Load threat detection model for weapons.

    YOLOv8n fine-tuned for weapon detection (gun, knife, etc.).
    This is a CRITICAL priority model for security applications.

    Args:
        model_path: Path to the threat detection model.
        device: CUDA device string for model placement.

    Returns:
        Loaded YOLO threat detection model instance.

    Note:
        Requires ultralytics package. Model should be downloaded
        from HuggingFace: Subh775/Threat-Detection-YOLOv8n
    """
    try:
        from ultralytics import YOLO
    except ImportError as e:
        logger.error("ultralytics package required for threat detection")
        raise ImportError(
            "ultralytics package is required for threat detection. "
            "Install with: pip install ultralytics"
        ) from e

    model = YOLO(model_path)
    if "cuda" in device and torch.cuda.is_available():
        model.to(device)
    logger.info(f"Threat detector loaded from {model_path}")
    return model


def load_demographics(
    age_model_path: str,
    gender_model_path: str | None = None,  # noqa: ARG001 - Reserved for future gender-specific model
    device: str = "cuda:0",
) -> tuple[Any, Any]:
    """Load age and gender classification models.

    ViT-based classifiers for demographic estimation from face crops.

    Args:
        age_model_path: Path to the age classifier model.
        gender_model_path: Path to the gender classifier model (reserved for future use).
                          Currently not used as age model handles both.
        device: CUDA device string for model placement.

    Returns:
        Tuple of (model, processor) for age-gender prediction.

    Note:
        Requires transformers package with vision support.
        gender_model_path is reserved for future use when separate models are needed.
    """
    try:
        from transformers import AutoImageProcessor, AutoModelForImageClassification
    except ImportError as e:
        logger.error("transformers package required for demographics")
        raise ImportError(
            "transformers package is required for demographics. "
            "Install with: pip install transformers"
        ) from e

    # Load age model
    processor = AutoImageProcessor.from_pretrained(age_model_path)
    model = AutoModelForImageClassification.from_pretrained(age_model_path)

    if "cuda" in device and torch.cuda.is_available():
        model = model.to(device)

    model.eval()
    logger.info(f"Demographics model loaded from {age_model_path}")
    return (model, processor)


def load_person_reid(model_path: str, device: str = "cuda:0") -> Any:
    """Load OSNet model for person re-identification.

    Generates 512-dimensional embeddings for person re-identification
    across different camera views.

    Args:
        model_path: Path to the OSNet model weights.
        device: CUDA device string for model placement.

    Returns:
        Loaded OSNet model instance.

    Note:
        Requires torchreid package or compatible model loading.
    """
    try:
        from torchreid import models as torchreid_models

        # Build OSNet model
        model = torchreid_models.build_model(
            name="osnet_x0_25",
            num_classes=1000,  # Pretrained classes
            pretrained=True,
        )

        # Load custom weights if provided and file exists
        if model_path and os.path.exists(model_path):
            state_dict = torch.load(model_path, map_location="cpu", weights_only=True)
            model.load_state_dict(state_dict, strict=False)

        if "cuda" in device and torch.cuda.is_available():
            model = model.to(device)

        model.eval()
        logger.info(f"Person ReID (OSNet) loaded from {model_path}")
        return model

    except ImportError as err:
        # Fallback: try loading as a standard PyTorch model
        logger.warning("torchreid not available, attempting direct PyTorch load")
        if os.path.exists(model_path):
            model = torch.load(model_path, map_location="cpu", weights_only=True)
            if "cuda" in device and torch.cuda.is_available() and hasattr(model, "to"):
                model = model.to(device)
            logger.info(f"Person ReID loaded from {model_path} (direct load)")
            return model
        raise ImportError(
            "torchreid package is required for person re-identification. "
            "Install from: https://github.com/KaiyangZhou/deep-person-reid"
        ) from err


def load_action_recognizer(model_path: str, device: str = "cuda:0") -> tuple[Any, Any]:
    """Load X-CLIP model for zero-shot action recognition.

    Video-level action classification using text prompts.
    Only loaded for suspicious activity analysis.

    Args:
        model_path: Path or HuggingFace model ID for X-CLIP
            (e.g., "microsoft/xclip-base-patch16-16-frames").
        device: CUDA device string for model placement.

    Returns:
        Tuple of (model, processor) for X-CLIP.

    Note:
        Requires transformers[video] for video processing.
        Memory-intensive (~2GB VRAM for patch16-16-frames model).
        Uses 16 frames for ~4% improved accuracy (NEM-3908).
    """
    try:
        from transformers import XCLIPModel, XCLIPProcessor
    except ImportError as e:
        logger.error("transformers package required for action recognition")
        raise ImportError(
            "transformers package with video support is required for action recognition. "
            "Install with: pip install transformers[video]"
        ) from e

    processor = XCLIPProcessor.from_pretrained(model_path)
    model = XCLIPModel.from_pretrained(model_path)

    if "cuda" in device and torch.cuda.is_available():
        model = model.to(device)

    model.eval()
    logger.info(f"Action recognizer (X-CLIP) loaded from {model_path}")
    return (model, processor)


def _unload_model(model: Any) -> None:
    """Helper function to unload a model and free its resources.

    Args:
        model: The model instance to unload
    """

    # Delete model reference
    if hasattr(model, "model") and model.model is not None:
        del model.model
        model.model = None

    if hasattr(model, "processor") and model.processor is not None:
        del model.processor
        model.processor = None

    if hasattr(model, "transform") and model.transform is not None:
        del model.transform
        model.transform = None

    if hasattr(model, "tokenizer") and model.tokenizer is not None:
        del model.tokenizer
        model.tokenizer = None

    if hasattr(model, "preprocess") and model.preprocess is not None:
        del model.preprocess
        model.preprocess = None


def create_model_registry(device: str = "cuda:0") -> dict[str, ModelConfig]:
    """Create the model registry with all available enrichment models.

    This function creates ModelConfig entries for all models that can be
    loaded on-demand by the OnDemandModelManager. Each config includes
    a loader function that instantiates and loads the model.

    Args:
        device: Device to load models on (e.g., "cuda:0", "cpu")

    Returns:
        Dictionary mapping model names to their configurations.
    """
    # Import model classes here to avoid circular imports
    try:
        # When running from tests or as a package
        from ai.enrichment.model import (
            ClothingClassifier,
            DepthEstimator,
            PetClassifier,
            VehicleClassifier,
        )
    except ImportError:
        # When running from within the enrichment directory
        from model import (
            ClothingClassifier,
            DepthEstimator,
            PetClassifier,
            VehicleClassifier,
        )

    registry: dict[str, ModelConfig] = {}

    # Vehicle Classifier (~1.5GB)
    vehicle_path = os.environ.get("VEHICLE_MODEL_PATH", "/models/vehicle-segment-classification")
    registry["vehicle_classifier"] = ModelConfig(
        name="vehicle_classifier",
        vram_mb=1500,
        priority=ModelPriority.MEDIUM,
        loader_fn=lambda: _create_and_load_model(VehicleClassifier, vehicle_path, device),
        unloader_fn=_unload_model,
    )

    # Pet Classifier (~200MB)
    pet_path = os.environ.get("PET_MODEL_PATH", "/models/pet-classifier")
    registry["pet_classifier"] = ModelConfig(
        name="pet_classifier",
        vram_mb=200,
        priority=ModelPriority.MEDIUM,
        loader_fn=lambda: _create_and_load_model(PetClassifier, pet_path, device),
        unloader_fn=_unload_model,
    )

    # FashionSigLIP Clothing Classifier (~800MB) - 57% accuracy improvement over FashionCLIP
    # FashionSigLIP performance vs FashionCLIP2.0:
    # - Text-to-Image MRR: 0.239 vs 0.165
    # - Text-to-Image Recall@1: 0.121 vs 0.077
    # - Text-to-Image Recall@10: 0.340 vs 0.249
    clothing_path = os.environ.get("CLOTHING_MODEL_PATH", "/models/fashion-siglip")
    registry["fashion_clip"] = ModelConfig(
        name="fashion_clip",
        vram_mb=800,
        priority=ModelPriority.MEDIUM,  # Standard classification model
        loader_fn=lambda p=clothing_path, d=device: _create_and_load_model(
            ClothingClassifier, p, d
        ),
        unloader_fn=unload_torch_model,
    )

    # Depth Estimator (~150MB)
    depth_path = os.environ.get("DEPTH_MODEL_PATH", "/models/depth-anything-v2-small")
    registry["depth_estimator"] = ModelConfig(
        name="depth_estimator",
        vram_mb=150,
        priority=ModelPriority.LOW,
        loader_fn=lambda: _create_and_load_model(DepthEstimator, depth_path, device),
        unloader_fn=_unload_model,
    )

    # Pose Estimator - YOLOv8n-pose (~300MB)
    # Trigger conditions: Person detected, need body posture analysis
    pose_path = os.environ.get("POSE_MODEL_PATH", "/models/yolov8n-pose/yolov8n-pose.pt")
    registry["pose_estimator"] = ModelConfig(
        name="pose_estimator",
        vram_mb=300,
        priority=ModelPriority.HIGH,  # Important for security posture analysis
        loader_fn=lambda: _create_pose_estimator(pose_path, device),
        unloader_fn=_unload_pose_estimator,
    )

    # Action Recognizer - X-CLIP (~2GB) (NEM-3908: upgraded to patch16-16-frames)
    # Trigger conditions: Person detected >3 seconds, multiple frames available,
    # unusual pose detected (trigger from pose estimator)
    # Uses 16 frames for ~4% improved accuracy over 8-frame patch32 model
    action_path = os.environ.get("ACTION_MODEL_PATH", "/models/xclip-base-patch16-16-frames")
    registry["action_recognizer"] = ModelConfig(
        name="action_recognizer",
        vram_mb=2000,  # Upgraded from 1500MB for patch16-16-frames
        priority=ModelPriority.LOW,  # Expensive, use sparingly
        loader_fn=lambda: _create_action_recognizer(action_path, device),
        unloader_fn=_unload_action_recognizer,
    )

    # Person Re-Identification - OSNet-x0.25 (~100MB)
    # Trigger conditions: Person detected, need to track across cameras/time
    # Use case: Identify if same person has been seen before
    reid_path = os.environ.get("REID_MODEL_PATH", "/models/osnet-x0-25/osnet_x0_25.pth")
    registry["person_reid"] = ModelConfig(
        name="person_reid",
        vram_mb=100,
        priority=ModelPriority.MEDIUM,  # Important for tracking but not critical
        loader_fn=lambda: _create_person_reid(reid_path, device),
        unloader_fn=_unload_person_reid,
    )

    # Threat Detector - YOLOv8n Weapon Detection (~400MB)
    # Trigger conditions: Always checked for person detections (CRITICAL priority)
    # Use case: Detect weapons (knives, guns, rifles) in security footage
    # Reference: HuggingFace Subh775/Threat-Detection-YOLOv8n
    threat_path = os.environ.get(
        "THREAT_MODEL_PATH", "/models/threat-detection-yolov8n/weights/best.pt"
    )
    registry["threat_detector"] = ModelConfig(
        name="threat_detector",
        vram_mb=400,
        priority=ModelPriority.CRITICAL,  # Never evict if possible
        loader_fn=lambda: _create_threat_detector(threat_path, device),
        unloader_fn=_unload_threat_detector,
    )

    # Demographics Estimator - ViT-based age and gender (~500MB)
    # Trigger conditions: Person detected with visible face
    # Use case: Provide identification context (expected vs unexpected visitors)
    # Reference: nateraw/vit-age-classifier or similar ViT models
    age_model_path = os.environ.get("AGE_MODEL_PATH", "/models/vit-age-classifier")
    gender_model_path = os.environ.get("GENDER_MODEL_PATH", None)
    registry["demographics"] = ModelConfig(
        name="demographics",
        vram_mb=500,
        priority=ModelPriority.HIGH,  # Important for person identification context
        loader_fn=lambda: _create_demographics_estimator(age_model_path, gender_model_path, device),
        unloader_fn=_unload_demographics_estimator,
    )

    # YOLO26 Detector - Optional secondary object detector (~100MB)
    # Trigger conditions: Used for fine-grained object detection or validation
    # Use case: Complement YOLO26v2 with YOLO26 for specific tasks
    # Reference: https://docs.ultralytics.com/models/
    yolo26_path = os.environ.get("YOLO26_ENRICHMENT_MODEL_PATH", "/models/yolo26m.pt")
    registry["yolo26_detector"] = ModelConfig(
        name="yolo26_detector",
        vram_mb=100,
        priority=ModelPriority.LOW,  # Optional secondary detector
        loader_fn=lambda: _create_yolo26_detector(yolo26_path, device),
        unloader_fn=_unload_yolo26_detector,
    )

    logger.info(f"Model registry created with {len(registry)} models")
    return registry


def _create_pose_estimator(model_path: str, device: str) -> Any:
    """Create and load a PoseEstimator instance.

    Args:
        model_path: Path to YOLOv8n-pose model file
        device: Device to load the model on

    Returns:
        Loaded PoseEstimator instance
    """
    from models.pose_estimator import PoseEstimator

    estimator = PoseEstimator(model_path=model_path, device=device)
    estimator.load_model()
    return estimator


def _unload_pose_estimator(model: Any) -> None:
    """Unload a PoseEstimator instance.

    Args:
        model: The PoseEstimator instance to unload
    """
    if hasattr(model, "unload"):
        model.unload()


def _create_action_recognizer(model_path: str, device: str) -> Any:
    """Create and load an ActionRecognizer instance.

    Args:
        model_path: Path to X-CLIP model or HuggingFace model ID
        device: Device to load the model on

    Returns:
        Loaded ActionRecognizer instance
    """
    from models.action_recognizer import ActionRecognizer

    recognizer = ActionRecognizer(model_path=model_path, device=device)
    recognizer.load_model()
    return recognizer


def _unload_action_recognizer(model: Any) -> None:
    """Unload an ActionRecognizer instance.

    Args:
        model: The ActionRecognizer instance to unload
    """
    if hasattr(model, "unload_model"):
        model.unload_model()


def _create_person_reid(model_path: str, device: str) -> Any:
    """Create and load a PersonReID instance.

    Args:
        model_path: Path to OSNet model weights file
        device: Device to load the model on

    Returns:
        Loaded PersonReID instance
    """
    from models.person_reid import PersonReID

    reid = PersonReID(model_path=model_path, device=device)
    reid.load_model()
    return reid


def _unload_person_reid(model: Any) -> None:
    """Unload a PersonReID instance.

    Args:
        model: The PersonReID instance to unload
    """
    if hasattr(model, "unload"):
        model.unload()


def _create_threat_detector(model_path: str, device: str) -> Any:
    """Create and load a ThreatDetector instance.

    Args:
        model_path: Path to YOLOv8 threat detection model file
        device: Device to load the model on

    Returns:
        Loaded ThreatDetector instance
    """
    from models.threat_detector import ThreatDetector

    detector = ThreatDetector(model_path=model_path, device=device)
    detector.load_model()
    return detector


def _unload_threat_detector(model: Any) -> None:
    """Unload a ThreatDetector instance.

    Args:
        model: The ThreatDetector instance to unload
    """
    if hasattr(model, "unload"):
        model.unload()


def _create_demographics_estimator(
    age_model_path: str,
    gender_model_path: str | None,
    device: str,
) -> Any:
    """Create and load a DemographicsEstimator instance.

    Args:
        age_model_path: Path to ViT age classification model
        gender_model_path: Optional path to gender classification model
        device: Device to load the model on

    Returns:
        Loaded DemographicsEstimator instance
    """
    from models.demographics import DemographicsEstimator

    estimator = DemographicsEstimator(
        age_model_path=age_model_path,
        gender_model_path=gender_model_path,
        device=device,
    )
    estimator.load_model()
    return estimator


def _unload_demographics_estimator(model: Any) -> None:
    """Unload a DemographicsEstimator instance.

    Args:
        model: The DemographicsEstimator instance to unload
    """
    if hasattr(model, "unload"):
        model.unload()


def _create_yolo26_detector(model_path: str, device: str) -> Any:
    """Create and load a YOLO26Detector instance.

    Args:
        model_path: Path to YOLO26 model file
        device: Device to load the model on

    Returns:
        Loaded YOLO26Detector instance
    """
    from models.yolo26_detector import YOLO26Detector

    detector = YOLO26Detector(model_path=model_path, device=device)
    detector.load_model()
    return detector


def _unload_yolo26_detector(model: Any) -> None:
    """Unload a YOLO26Detector instance.

    Args:
        model: The YOLO26Detector instance to unload
    """
    if hasattr(model, "unload"):
        model.unload()


def _create_and_load_model(model_class: type, model_path: str, device: str) -> Any:
    """Create a model instance and load it.

    Args:
        model_class: The model class to instantiate
        model_path: Path to the model files
        device: Device to load the model on

    Returns:
        The loaded model instance
    """
    instance = model_class(model_path=model_path, device=device)
    instance.load_model()
    return instance


def get_models_for_detection_type(
    detection_type: str,
    is_suspicious: bool = False,
    has_multiple_frames: bool = False,
) -> list[str]:
    """Get model names that should be loaded for a detection type.

    This function maps detection types from YOLO26v2 to the appropriate
    enrichment models that should be loaded.

    Args:
        detection_type: Type of detection (e.g., "person", "car", "dog")
        is_suspicious: Whether the detection is flagged as suspicious
                      (triggers action recognition for person detections)
        has_multiple_frames: Whether multiple frames are available
                            (required for action recognition)

    Returns:
        List of model names that should be loaded for this detection type.
    """
    detection_type_lower = detection_type.lower()

    # Map detection types to models
    # threat_detector is listed first for person detections due to CRITICAL priority
    detection_model_mapping: dict[str, list[str]] = {
        # Person detections - threat detection is CRITICAL, then clothing, pose, re-ID
        "person": [
            "threat_detector",  # CRITICAL: always check for weapons first
            "fashion_clip",
            "pose_estimator",
            "person_reid",
            "depth_estimator",
        ],
        # Vehicle detections
        "car": ["vehicle_classifier", "depth_estimator"],
        "truck": ["vehicle_classifier", "depth_estimator"],
        "bus": ["vehicle_classifier", "depth_estimator"],
        "motorcycle": ["vehicle_classifier", "depth_estimator"],
        "bicycle": ["vehicle_classifier", "depth_estimator"],
        # Animal detections
        "dog": ["pet_classifier", "depth_estimator"],
        "cat": ["pet_classifier", "depth_estimator"],
        "bird": ["pet_classifier"],
    }

    # Check for exact match first
    if detection_type_lower in detection_model_mapping:
        models = detection_model_mapping[detection_type_lower].copy()
    else:
        # Check for partial matches
        models = []
        for key, model_list in detection_model_mapping.items():
            if key in detection_type_lower or detection_type_lower in key:
                models = model_list.copy()
                break

    # Add action recognition for suspicious person detections with multiple frames
    # Trigger conditions from design doc:
    # - Person detected for >3 seconds (implied by has_multiple_frames)
    # - Multiple frames available in buffer
    # - Unusual pose detected (implied by is_suspicious flag)
    if detection_type_lower == "person" and is_suspicious and has_multiple_frames:
        models.append("action_recognizer")

    return models
