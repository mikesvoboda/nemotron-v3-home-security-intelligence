"""Model Zoo for on-demand model loading.

This module provides a registry of AI models that can be loaded on-demand during
batch processing to extract additional context (license plates, faces, OCR text,
pose estimation).

The ModelManager handles VRAM-efficient loading and unloading of models using
async context managers that automatically release GPU memory when done.

Models:
    - yolo11-license-plate: License plate detection on vehicles
    - yolo11-face: Face detection on persons
    - paddleocr: OCR text extraction from detected plates
    - clip-vit-l: CLIP embeddings for re-identification
    - florence-2-large: Vision-language queries for attribute extraction
    - yolo-world-s: Open-vocabulary zero-shot detection
    - vitpose-small: Human pose keypoint detection (17 COCO keypoints)
    - depth-anything-v2-small: Monocular depth estimation for distance context
    - violence-detection: Binary violence classification on full frame
    - weather-classification: Weather condition classification (5 classes)
    - segformer-b2-clothes: Clothing segmentation on person detections
    - xclip-base: Temporal action recognition in video sequences
    - fashion-clip: Zero-shot clothing classification for security context
    - brisque-quality: Image quality assessment (CPU-based, 0 VRAM)
    - vehicle-segment-classification: Detailed vehicle type classification (11 types)
    - pet-classifier: Cat/dog classification for false positive reduction

VRAM Budget:
    - Nemotron LLM: 21,700 MB (always loaded)
    - RT-DETRv2: 650 MB (always loaded)
    - Available for Model Zoo: ~1,650 MB
    - Models load sequentially, never concurrently
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger
from backend.services.clip_loader import load_clip_model
from backend.services.depth_anything_loader import load_depth_model
from backend.services.fashion_clip_loader import load_fashion_clip_model
from backend.services.florence_loader import load_florence_model
from backend.services.image_quality_loader import load_brisque_model
from backend.services.pet_classifier_loader import load_pet_classifier_model
from backend.services.segformer_loader import load_segformer_model
from backend.services.vehicle_classifier_loader import load_vehicle_classifier
from backend.services.vehicle_damage_loader import load_vehicle_damage_model
from backend.services.violence_loader import load_violence_model
from backend.services.vitpose_loader import load_vitpose_model
from backend.services.weather_loader import load_weather_model
from backend.services.xclip_loader import load_xclip_model
from backend.services.yolo_world_loader import load_yolo_world_model

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = get_logger(__name__)

# Vehicle classes from COCO that should trigger license plate detection
VEHICLE_CLASSES = frozenset(
    {
        "car",
        "truck",
        "bus",
        "motorcycle",
        "bicycle",
    }
)

# Person class that should trigger face detection
PERSON_CLASS = "person"

# Animal classes that should trigger pet classification
# These are common animal classes from COCO/RT-DETRv2 that might be pets
ANIMAL_CLASSES = frozenset(
    {
        "cat",
        "dog",
    }
)


@dataclass
class ModelConfig:
    """Configuration for a Model Zoo model.

    Attributes:
        name: Unique identifier for the model (e.g., "yolo11-license-plate")
        path: HuggingFace repo path or local file path
        category: Model category ("detection", "recognition", "ocr")
        vram_mb: Estimated VRAM usage in megabytes
        load_fn: Async callable that loads the model and returns it
        enabled: Whether the model is enabled for use (default True)
        available: Set to True after successful initial load (default False)
    """

    name: str
    path: str
    category: str
    vram_mb: int
    load_fn: Callable[[str], Awaitable[Any]]
    enabled: bool = True
    available: bool = False


async def load_yolo_model(model_path: str) -> Any:
    """Load a YOLO model from HuggingFace or local path.

    This is a placeholder implementation. The actual implementation will use
    ultralytics or a similar library to load YOLO models.

    Args:
        model_path: HuggingFace repo path or local file path

    Returns:
        Loaded YOLO model instance

    Raises:
        ImportError: If ultralytics is not installed
        RuntimeError: If model loading fails
    """
    try:
        # Attempt to import ultralytics for YOLO support
        from ultralytics import YOLO

        logger.info(f"Loading YOLO model from {model_path}")

        # Run model loading in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        model = await loop.run_in_executor(None, lambda: YOLO(model_path))

        logger.info(f"Successfully loaded YOLO model from {model_path}")
        return model

    except ImportError:
        logger.warning("ultralytics package not installed. Install with: pip install ultralytics")
        raise

    except Exception as e:
        logger.error(f"Failed to load YOLO model from {model_path}: {e}")
        raise RuntimeError(f"Failed to load YOLO model: {e}") from e


async def load_paddle_ocr(model_path: str) -> Any:
    """Load PaddleOCR model.

    This is a placeholder implementation. The actual implementation will use
    PaddlePaddle/PaddleOCR for text recognition.

    Args:
        model_path: Model path (used for configuration, not direct loading)

    Returns:
        Loaded PaddleOCR instance

    Raises:
        ImportError: If paddleocr is not installed
        RuntimeError: If model loading fails
    """
    try:
        from paddleocr import PaddleOCR

        logger.info(f"Loading PaddleOCR model (config: {model_path})")

        # Run model loading in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        # PaddleOCR downloads models automatically on first use
        # use_angle_cls=True enables text direction classification
        # lang='en' for English text recognition (license plates)
        model = await loop.run_in_executor(
            None,
            lambda: PaddleOCR(use_angle_cls=True, lang="en", show_log=False),
        )

        logger.info("Successfully loaded PaddleOCR model")
        return model

    except ImportError:
        logger.warning(
            "paddleocr package not installed. Install with: pip install paddleocr paddlepaddle"
        )
        raise

    except Exception as e:
        logger.error(f"Failed to load PaddleOCR: {e}")
        raise RuntimeError(f"Failed to load PaddleOCR: {e}") from e


# Model Zoo registry with default configurations
# These are the models available for on-demand loading during enrichment
MODEL_ZOO: dict[str, ModelConfig] = {}


def _init_model_zoo() -> dict[str, ModelConfig]:
    """Initialize the MODEL_ZOO registry with default models.

    This function is called lazily to avoid issues at import time.

    Returns:
        Dictionary mapping model names to ModelConfig instances
    """
    return {
        "yolo11-license-plate": ModelConfig(
            name="yolo11-license-plate",
            path="/models/model-zoo/yolo11-license-plate/license-plate-finetune-v1n.pt",
            category="detection",
            vram_mb=300,
            load_fn=load_yolo_model,
            enabled=True,
            available=False,
        ),
        "yolo11-face": ModelConfig(
            name="yolo11-face",
            path="/models/model-zoo/yolo11-face-detection/model.pt",
            category="detection",
            vram_mb=200,
            load_fn=load_yolo_model,
            enabled=True,
            available=False,
        ),
        "paddleocr": ModelConfig(
            name="paddleocr",
            path="/models/model-zoo/paddleocr",
            category="ocr",
            vram_mb=100,
            load_fn=load_paddle_ocr,
            enabled=True,
            available=False,
        ),
        # Future: YOLO26 when released
        "yolo26-general": ModelConfig(
            name="yolo26-general",
            path="ultralytics/yolo26",  # TBD
            category="detection",
            vram_mb=400,
            load_fn=load_yolo_model,
            enabled=False,  # Disabled until available
            available=False,
        ),
        # CLIP ViT-L for re-identification embeddings
        # DISABLED: Not downloaded to local model zoo
        "clip-vit-l": ModelConfig(
            name="clip-vit-l",
            path="/models/model-zoo/clip-vit-l",
            category="embedding",
            vram_mb=800,
            load_fn=load_clip_model,
            enabled=True,
            available=False,
        ),
        # Florence-2-large for vision-language queries (attributes, behavior, scene)
        # DISABLED: Florence-2 now runs as a dedicated HTTP service at http://ai-florence:8092
        # The backend calls the service via florence_client.py instead of loading the model directly.
        # This improves VRAM management by keeping Florence-2 in a separate container.
        "florence-2-large": ModelConfig(
            name="florence-2-large",
            path="/models/model-zoo/florence-2-large",
            category="vision-language",
            vram_mb=1200,  # ~1.2GB with float16
            load_fn=load_florence_model,
            enabled=False,  # Disabled - now runs as dedicated ai-florence service
            available=False,
        ),
        # YOLO-World-S for open-vocabulary detection via text prompts
        # Enables zero-shot detection of security-relevant objects (knives, packages, etc.)
        "yolo-world-s": ModelConfig(
            name="yolo-world-s",
            path="/models/model-zoo/yolo-world-s",
            category="detection",
            vram_mb=1500,  # ~1.5GB
            load_fn=load_yolo_world_model,
            enabled=True,
            available=False,
        ),
        # ViTPose+ Small for human pose keypoint detection
        # Detects 17 COCO keypoints for pose classification (standing, crouching, running)
        "vitpose-small": ModelConfig(
            name="vitpose-small",
            path="/models/model-zoo/vitpose-small",
            category="pose",
            vram_mb=1500,  # ~1.5GB with float16
            load_fn=load_vitpose_model,
            enabled=True,
            available=False,
        ),
        # Depth Anything V2 Small for monocular depth estimation
        # Provides relative distance estimation for detected objects
        # Output: depth map where lower values = closer to camera
        "depth-anything-v2-small": ModelConfig(
            name="depth-anything-v2-small",
            path="/models/model-zoo/depth-anything-v2-small",
            category="depth-estimation",
            vram_mb=150,  # ~100-200MB (very lightweight)
            load_fn=load_depth_model,
            enabled=True,
            available=False,
        ),
        # ViT Violence Detection for identifying violent content
        # Binary classification: violent vs non-violent
        # Runs on full frame when 2+ persons detected (optimization)
        # Reported accuracy: 98.80%
        "violence-detection": ModelConfig(
            name="violence-detection",
            path="/models/model-zoo/violence-detection",
            category="classification",
            vram_mb=500,  # ~500MB
            load_fn=load_violence_model,
            enabled=True,
            available=False,
        ),
        # Weather Classification for environmental context
        # SigLIP-based model fine-tuned for weather classification
        # Classes: cloudy/overcast, foggy/hazy, rain/storm, snow/frosty, sun/clear
        # Runs once per batch on full frame (not per detection)
        # Weather context helps Nemotron calibrate risk assessments
        "weather-classification": ModelConfig(
            name="weather-classification",
            path="/models/model-zoo/weather-classification",
            category="classification",
            vram_mb=200,  # ~200MB
            load_fn=load_weather_model,
            enabled=True,
            available=False,
        ),
        # SegFormer B2 Clothes for clothing segmentation on person detections
        # Segments 18 clothing/body part categories for re-identification
        # Enables clothing-based person identification and suspicious attire detection
        "segformer-b2-clothes": ModelConfig(
            name="segformer-b2-clothes",
            path="/models/model-zoo/segformer-b2-clothes",
            category="segmentation",
            vram_mb=1500,  # ~1.5GB
            load_fn=load_segformer_model,
            enabled=True,
            available=False,
        ),
        # X-CLIP for temporal action recognition in video sequences
        # Analyzes multiple frames to classify security-relevant actions:
        # loitering, approaching door, running away, suspicious behavior, etc.
        # Based on microsoft/xclip-base-patch32 - extends CLIP for video understanding
        "xclip-base": ModelConfig(
            name="xclip-base",
            path="/models/model-zoo/xclip-base",
            category="action-recognition",
            vram_mb=2000,  # ~2GB with float16
            load_fn=load_xclip_model,
            enabled=True,
            available=False,
        ),
        # Marqo-FashionCLIP for zero-shot clothing classification
        # Identifies security-relevant clothing attributes on person crops:
        # - Suspicious attire (dark hoodie, face mask, gloves, all black)
        # - Service uniforms (Amazon, FedEx, UPS, high-vis vest)
        # - General clothing categories (casual, business, athletic)
        # Runs on person crop bounding boxes from RT-DETRv2
        "fashion-clip": ModelConfig(
            name="fashion-clip",
            path="/models/model-zoo/fashion-clip",
            category="classification",
            vram_mb=500,  # ~500MB
            load_fn=load_fashion_clip_model,
            enabled=True,
            available=False,
        ),
        # BRISQUE image quality assessment via PyIQA
        # No-reference image quality metric for detecting:
        # - Camera obstruction/tampering (sudden quality drop)
        # - Motion blur (fast movement detection)
        # - General quality degradation (noise, artifacts)
        # CPU-based, no VRAM required
        "brisque-quality": ModelConfig(
            name="brisque-quality",
            path="pyiqa",  # Uses pyiqa library, not a model path
            category="quality-assessment",
            vram_mb=0,  # CPU-based, no VRAM needed
            load_fn=load_brisque_model,
            enabled=False,  # Disabled: pyiqa incompatible with NumPy 2.0 (np.sctypes removed)
            available=False,
        ),
        # ResNet-50 Vehicle Segment Classification for detailed vehicle type ID
        # Classifies vehicles into 11 categories beyond RT-DETRv2's generic types:
        # car, pickup_truck, single_unit_truck, articulated_truck, bus,
        # motorcycle, bicycle, work_van, non_motorized_vehicle, pedestrian, background
        # Helps distinguish delivery vehicles (work_van) from personal vehicles
        # Trained on MIO-TCD Traffic Dataset (50K images)
        "vehicle-segment-classification": ModelConfig(
            name="vehicle-segment-classification",
            path="/models/model-zoo/vehicle-segment-classification",
            category="classification",
            vram_mb=1500,  # ~1.5GB (conservative estimate for ResNet-50)
            load_fn=load_vehicle_classifier,
            enabled=True,
            available=False,
        ),
        # YOLOv11 Vehicle Damage Segmentation
        # Classes: cracks, dents, glass_shatter, lamp_broken, scratches, tire_flat
        # Security: glass_shatter + lamp_broken at night = suspicious (break-in)
        "vehicle-damage-detection": ModelConfig(
            name="vehicle-damage-detection",
            path="/models/model-zoo/vehicle-damage-detection",
            category="detection",
            vram_mb=2000,  # ~2GB (yolo11x-seg architecture)
            load_fn=load_vehicle_damage_model,
            enabled=True,
            available=False,
        ),
        # ResNet-18 Pet Classifier for false positive reduction
        # Classifies dog vs cat from animal crop detections
        # High-confidence pet detections can skip Nemotron analysis
        # Lightweight model for quick load/unload cycles
        "pet-classifier": ModelConfig(
            name="pet-classifier",
            path="/models/model-zoo/pet-classifier",
            category="classification",
            vram_mb=200,  # ~200MB (very lightweight ResNet-18)
            load_fn=load_pet_classifier_model,
            enabled=True,
            available=False,
        ),
    }


def get_model_zoo() -> dict[str, ModelConfig]:
    """Get the MODEL_ZOO registry, initializing if needed.

    Returns:
        Dictionary mapping model names to ModelConfig instances
    """
    global MODEL_ZOO  # noqa: PLW0603
    if not MODEL_ZOO:
        MODEL_ZOO = _init_model_zoo()
    return MODEL_ZOO


def reset_model_zoo() -> None:
    """Reset the MODEL_ZOO registry (for testing).

    This clears the global MODEL_ZOO dictionary, causing it to be
    reinitialized on next access via get_model_zoo().
    """
    global MODEL_ZOO  # noqa: PLW0603
    MODEL_ZOO = {}


def get_model_config(model_name: str) -> ModelConfig | None:
    """Get configuration for a specific model.

    Args:
        model_name: Name of the model to look up

    Returns:
        ModelConfig if found, None otherwise
    """
    zoo = get_model_zoo()
    return zoo.get(model_name)


def get_enabled_models() -> list[ModelConfig]:
    """Get list of all enabled models.

    Returns:
        List of ModelConfig instances where enabled=True
    """
    zoo = get_model_zoo()
    return [config for config in zoo.values() if config.enabled]


def get_available_models() -> list[ModelConfig]:
    """Get list of all available (verified working) models.

    Returns:
        List of ModelConfig instances where available=True
    """
    zoo = get_model_zoo()
    return [config for config in zoo.values() if config.available]


def get_total_vram_if_loaded(model_names: list[str]) -> int:
    """Calculate total VRAM if specified models were all loaded.

    Args:
        model_names: List of model names to sum VRAM for

    Returns:
        Total estimated VRAM in megabytes
    """
    zoo = get_model_zoo()
    total = 0
    for name in model_names:
        config = zoo.get(name)
        if config:
            total += config.vram_mb
    return total


class ModelManager:
    """Manager for on-demand model loading with VRAM optimization.

    The ModelManager provides async context managers for loading models,
    ensuring proper cleanup and VRAM release when done. Models are loaded
    lazily and unloaded immediately after use to maximize available VRAM
    for the primary models (Nemotron and RT-DETRv2).

    Thread-safe via asyncio.Lock for concurrent access.

    Usage:
        manager = ModelManager()

        async with manager.load("yolo11-license-plate") as model:
            results = model.predict(image)
        # Model is automatically unloaded and CUDA cache cleared

    Attributes:
        _loaded_models: Dictionary of currently loaded models
        _lock: Asyncio lock for thread-safe operations
    """

    def __init__(self) -> None:
        """Initialize the ModelManager."""
        self._loaded_models: dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._load_counts: dict[str, int] = {}  # Reference counting for nested loads
        logger.info("ModelManager initialized")

    @property
    def loaded_models(self) -> list[str]:
        """Get list of currently loaded model names.

        Returns:
            List of model names that are currently loaded
        """
        return list(self._loaded_models.keys())

    @property
    def total_loaded_vram(self) -> int:
        """Get estimated total VRAM usage of loaded models.

        Returns:
            Total estimated VRAM in megabytes
        """
        return get_total_vram_if_loaded(self.loaded_models)

    def is_loaded(self, model_name: str) -> bool:
        """Check if a model is currently loaded.

        Args:
            model_name: Name of the model to check

        Returns:
            True if model is loaded, False otherwise
        """
        return model_name in self._loaded_models

    async def _load_model(self, model_name: str) -> Any:
        """Load a model into memory.

        Args:
            model_name: Name of the model to load

        Returns:
            Loaded model instance

        Raises:
            KeyError: If model name is not in MODEL_ZOO
            RuntimeError: If model is disabled or loading fails
        """
        config = get_model_config(model_name)
        if config is None:
            raise KeyError(f"Unknown model: {model_name}")

        if not config.enabled:
            raise RuntimeError(f"Model {model_name} is disabled")

        logger.info(f"Loading model {model_name} (~{config.vram_mb}MB VRAM)")

        try:
            model = await config.load_fn(config.path)
            self._loaded_models[model_name] = model

            # Mark as available after successful load
            config.available = True

            logger.info(f"Successfully loaded model {model_name}")
            return model

        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            raise

    async def _unload_model(self, model_name: str) -> None:
        """Unload a model from memory and clear CUDA cache.

        Args:
            model_name: Name of the model to unload
        """
        if model_name not in self._loaded_models:
            return

        logger.info(f"Unloading model {model_name}")

        try:
            # Remove model reference
            del self._loaded_models[model_name]

            # Clear CUDA cache if torch is available
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    logger.debug("CUDA cache cleared after model unload")
            except ImportError:
                # torch not installed, skip CUDA cleanup
                pass

        except Exception as e:
            logger.warning(f"Error during model unload: {e}")

    @asynccontextmanager
    async def load(self, model_name: str) -> AsyncGenerator[Any]:
        """Load a model for use within a context.

        This context manager loads the model if not already loaded,
        yields it for use, then unloads it and clears CUDA cache.

        Supports reference counting for nested loads of the same model.

        Args:
            model_name: Name of the model to load

        Yields:
            Loaded model instance

        Raises:
            KeyError: If model name is not in MODEL_ZOO
            RuntimeError: If model is disabled or loading fails

        Example:
            async with manager.load("yolo11-face") as face_model:
                faces = face_model.predict(image)
        """
        async with self._lock:
            # Increment reference count
            self._load_counts[model_name] = self._load_counts.get(model_name, 0) + 1

            # Load if not already loaded
            if model_name not in self._loaded_models:
                await self._load_model(model_name)

            model = self._loaded_models[model_name]

        try:
            yield model
        finally:
            async with self._lock:
                # Decrement reference count
                self._load_counts[model_name] = self._load_counts.get(model_name, 1) - 1

                # Unload only when no more references
                if self._load_counts.get(model_name, 0) <= 0:
                    await self._unload_model(model_name)
                    self._load_counts.pop(model_name, None)

    async def preload(self, model_name: str) -> None:
        """Preload a model without using context manager.

        Useful for warming up models before batch processing.
        Call unload() when done.

        Args:
            model_name: Name of the model to preload

        Raises:
            KeyError: If model name is not in MODEL_ZOO
            RuntimeError: If model is disabled or loading fails
        """
        async with self._lock:
            if model_name not in self._loaded_models:
                await self._load_model(model_name)
                self._load_counts[model_name] = 1

    async def unload(self, model_name: str) -> None:
        """Explicitly unload a preloaded model.

        Args:
            model_name: Name of the model to unload
        """
        async with self._lock:
            self._load_counts.pop(model_name, None)
            await self._unload_model(model_name)

    async def unload_all(self) -> None:
        """Unload all loaded models and clear CUDA cache."""
        async with self._lock:
            model_names = list(self._loaded_models.keys())
            for model_name in model_names:
                await self._unload_model(model_name)
            self._load_counts.clear()

            # Final CUDA cache clear
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass

        logger.info("All models unloaded")

    def get_status(self) -> dict[str, Any]:
        """Get current status of the ModelManager.

        Returns:
            Dictionary with loaded models, VRAM usage, and counts
        """
        return {
            "loaded_models": self.loaded_models,
            "total_loaded_vram_mb": self.total_loaded_vram,
            "load_counts": dict(self._load_counts),
        }


# Global ModelManager instance
_model_manager: ModelManager | None = None


def get_model_manager() -> ModelManager:
    """Get or create the global ModelManager instance.

    Returns:
        Global ModelManager instance
    """
    global _model_manager  # noqa: PLW0603
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager


def reset_model_manager() -> None:
    """Reset the global ModelManager instance (for testing)."""
    global _model_manager  # noqa: PLW0603
    _model_manager = None
