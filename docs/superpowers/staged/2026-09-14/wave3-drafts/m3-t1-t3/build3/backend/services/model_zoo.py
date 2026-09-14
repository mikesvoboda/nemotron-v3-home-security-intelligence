"""Model Zoo for on-demand model loading.

This module provides a registry of AI models that can be loaded on-demand during
batch processing to extract additional context (license plates, faces, OCR text,
pose estimation).

The ModelManager handles VRAM-efficient loading and unloading of models using
async context managers that automatically release GPU memory when done.

Models:
    - fast-alpr: End-to-end license plate detection + OCR (28MB, replaces YOLO11+PaddleOCR)
    - yolo11-license-plate: License plate detection on vehicles (legacy, 300MB)
    - yolo11-face: Face detection on persons
    - paddleocr: OCR text extraction from detected plates (legacy, 100MB)
    - siglip2-base-patch16-224: SigLIP 2 Base embeddings for re-identification (replaces CLIP ViT-L)
    - florence-2-large: Vision-language queries for attribute extraction
    - yolo-world-s: Open-vocabulary zero-shot detection
    - vitpose-small: Human pose keypoint detection (17 COCO keypoints)
    - depth-anything-v2-tiny: Monocular depth estimation for distance context (3x faster than Small)
    - violence-detection: Binary violence classification on full frame
    - weather-classification: Weather condition classification (5 classes)
    - segformer-b2-clothes: Clothing segmentation on person detections
    - xclip-base: Temporal action recognition in video sequences
    - fashion-clip: Zero-shot clothing classification for security context
    - brisque-quality: Image quality assessment (CPU-based, 0 VRAM)
    - vehicle-segment-classification: Detailed vehicle type classification (11 types)
    - pet-classifier: Cat/dog classification for false positive reduction
    - osnet-ain-x1-0: OSNet-AIN x1.0 for person re-identification embeddings (~100MB)
    - threat-detection-yolov8n: Weapon/threat detection (~300MB)
    - vit-age-classifier: Age estimation from face/person crops (~200MB)
    - vit-gender-classifier: Gender classification from face/person crops (~200MB)
    - yolov8n-pose: Alternative pose estimation model (~200MB)
    - zero-dce-plus-plus: Low-light image enhancement preprocessing (~5MB)

VRAM Budget:
    - Nemotron LLM: 21,700 MB (always loaded)
    - YOLO26v2: 650 MB (always loaded)
    - Available for Model Zoo: ~1,650 MB
    - Models load sequentially, never concurrently
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict, TypeVar

import yaml

from backend.core.logging import get_logger
from backend.core.metrics import record_model_restart, set_model_load_duration
from backend.services.age_classifier_loader import load_age_classifier_model
from backend.services.clip_loader import load_clip_model
from backend.services.depth_anything_loader import load_depth_model
from backend.services.fashion_clip_loader import load_fashion_clip_model
from backend.services.fast_alpr_loader import load_fast_alpr
from backend.services.florence_loader import load_florence_model
from backend.services.gender_classifier_loader import load_gender_classifier_model
from backend.services.image_quality_loader import load_brisque_model
from backend.services.osnet_loader import load_osnet_model
from backend.services.pet_classifier_loader import load_pet_classifier_model
from backend.services.segformer_loader import load_segformer_model
from backend.services.smoke_fire_loader import load_smoke_fire_model
from backend.services.stgcn_loader import load_stgcn_model
from backend.services.threat_detection_loader import load_threat_detection_model
from backend.services.vehicle_classifier_loader import load_vehicle_classifier
from backend.services.vehicle_damage_loader import load_vehicle_damage_model
from backend.services.violence_loader import load_violence_model
from backend.services.vitpose_loader import load_vitpose_model
from backend.services.weather_loader import load_weather_model
from backend.services.xclip_loader import load_xclip_model
from backend.services.yolo_world_loader import load_yolo_world_model
from backend.services.zero_dce_loader import load_zero_dce_model

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = get_logger(__name__)

# TypeVar for generic model type (models can be YOLO, PaddleOCR, etc.)
ModelT = TypeVar("ModelT")


class ModelManagerStatus(TypedDict):
    """Type for ModelManager status dictionary."""

    loaded_models: list[str]
    total_loaded_vram_mb: int
    load_counts: dict[str, int]


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
# These are common animal classes from COCO/YOLO26v2 that might be pets
ANIMAL_CLASSES = frozenset(
    {
        "cat",
        "dog",
    }
)


@dataclass(slots=True)
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
        priority: Model priority level ("critical", "high", "medium", "low")
                  Critical models should never be evicted from VRAM
        preload: Whether the model should be preloaded at startup
        never_evict: Whether the model should never be evicted from VRAM
    """

    name: str
    path: str
    category: str
    vram_mb: int
    load_fn: Callable[[str], Awaitable[Any]]
    enabled: bool = True
    available: bool = False
    priority: str = "medium"
    preload: bool = False
    never_evict: bool = False


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
        RuntimeError: If model loading fails or model file is missing
    """
    try:
        from pathlib import Path

        # Attempt to import ultralytics for YOLO support
        from ultralytics import YOLO

        logger.info(f"Loading YOLO model from {model_path}")

        # Validate model file exists for local paths (paths containing '/')
        # This catches missing model files early with a clear error message
        # instead of letting ultralytics raise a cryptic FileNotFoundError
        if "/" in model_path and not model_path.startswith("http"):
            if not Path(model_path).exists():
                # Check if this is a .pt file path vs a directory
                parent_dir = str(Path(model_path).parent)
                if Path(parent_dir).is_dir():
                    available_files = [
                        f.name
                        for f in Path(parent_dir).iterdir()
                        if f.name.endswith((".pt", ".pth", ".onnx"))
                    ]
                    logger.warning(
                        f"Model file not found: {model_path}. "
                        f"Available model files in {parent_dir}: {available_files}"
                    )
                else:
                    logger.warning(
                        f"Model path does not exist: {model_path}. "
                        f"Ensure the model directory is mounted in the container. "
                        f"Download with: python scripts/download-model-zoo.py --all"
                    )
                raise RuntimeError(
                    f"Model file not found: {model_path}. "
                    f"Download the model with: python scripts/download-model-zoo.py --all"
                )

        def _load_and_fuse() -> Any:
            """Load YOLO model and pre-fuse for thread-safe concurrent use.

            YOLO models automatically fuse batch normalization into Conv layers
            on first predict() call. This fusion is NOT thread-safe and causes
            "'Conv' object has no attribute 'bn'" errors when multiple threads
            call predict() concurrently on a freshly loaded model.

            By calling fuse() immediately after loading, we ensure the model
            is ready for concurrent use without race conditions.

            See: https://github.com/ultralytics/yolov5/issues/12071

            GIL note: model.fuse() calls model.info() → thop.profile(deepcopy(model))
            which deep-copies the full network in pure Python, holding the GIL for
            seconds.  On CPU this overhead is not worth the BN-fusion speedup (which
            only matters on GPU anyway), so we skip fuse() on CPU-only hosts.
            """
            import threading as _threading

            import torch as _torch

            _threading.current_thread().name = f"load-yolo[{Path(model_path).name}]"

            model = YOLO(model_path)

            # fuse() only provides speedup via BN-Conv merging on CUDA;
            # on CPU the thop deepcopy holds the GIL for seconds with no benefit.
            if _torch.cuda.is_available() and hasattr(model, "fuse"):
                inner_model = getattr(model, "model", None)
                if inner_model is not None and hasattr(inner_model, "is_fused"):
                    if not inner_model.is_fused():
                        model.fuse()
                else:
                    model.fuse()

            return model

        # Run model loading in thread pool to avoid blocking
        loop = asyncio.get_running_loop()
        model = await loop.run_in_executor(None, _load_and_fuse)

        logger.info(f"Successfully loaded YOLO model from {model_path}")
        return model

    except ImportError:
        logger.warning("ultralytics package not installed. Install with: pip install ultralytics")
        raise

    except Exception as e:
        logger.error("Failed to load YOLO model", exc_info=True, extra={"model_path": model_path})
        raise RuntimeError(f"Failed to load YOLO model: {e}") from e


def _is_paddleocr_available() -> bool:
    """Check if PaddleOCR package is available.

    Returns:
        True if paddleocr is installed, False otherwise
    """
    try:
        import importlib.util

        return importlib.util.find_spec("paddleocr") is not None
    except (ImportError, ModuleNotFoundError):
        return False


async def load_paddle_ocr(model_path: str) -> Any:
    """Load PaddleOCR model.

    This is a placeholder implementation. The actual implementation will use
    PaddlePaddle/PaddleOCR for text recognition.

    Note: PaddleOCR is an optional dependency. If not installed, this function
    raises RuntimeError with a descriptive message (not ImportError) so that
    the ModelManager can handle it gracefully without logging a full traceback.

    Args:
        model_path: Model path (used for configuration, not direct loading)

    Returns:
        Loaded PaddleOCR instance

    Raises:
        RuntimeError: If paddleocr is not installed or model loading fails
    """
    # Check availability first to provide graceful failure
    if not _is_paddleocr_available():
        logger.info(
            "paddleocr package not installed - OCR features disabled. "
            "Install with: pip install paddleocr paddlepaddle"
        )
        raise RuntimeError(
            "paddleocr package not installed. OCR features are disabled. "
            "Install with: pip install paddleocr paddlepaddle"
        )

    try:
        from paddleocr import PaddleOCR

        logger.info(f"Loading PaddleOCR model (config: {model_path})")

        # Run model loading in thread pool to avoid blocking
        loop = asyncio.get_running_loop()
        # PaddleOCR downloads models automatically on first use
        # use_angle_cls=True enables text direction classification
        # lang='en' for English text recognition (license plates)
        model = await loop.run_in_executor(
            None,
            lambda: PaddleOCR(use_angle_cls=True, lang="en", show_log=False),
        )

        logger.info("Successfully loaded PaddleOCR model")
        return model

    except ImportError as e:
        logger.info(
            "paddleocr package not installed - OCR features disabled. "
            "Install with: pip install paddleocr paddlepaddle"
        )
        raise RuntimeError(
            "paddleocr package not installed. OCR features are disabled. "
            "Install with: pip install paddleocr paddlepaddle"
        ) from e

    except Exception as e:
        logger.error("Failed to load PaddleOCR", exc_info=True)
        raise RuntimeError(f"Failed to load PaddleOCR: {e}") from e


# Model Zoo registry with default configurations
# These are the models available for on-demand loading during enrichment
MODEL_ZOO: dict[str, ModelConfig] = {}


def _get_model_zoo_base_path() -> str:
    """Get the base path for model zoo.

    Uses MODEL_ZOO_PATH environment variable if set, otherwise defaults
    to /models/model-zoo (the Docker container mount point).

    Returns:
        Base path for model zoo directory
    """
    import os

    return os.environ.get("MODEL_ZOO_PATH", "/models/model-zoo")


# ---------------------------------------------------------------------------
# Loader map — single place that binds a model name to its load_fn.
# All loader imports live at the top of this file; this dict just wires names.
# ---------------------------------------------------------------------------
_LOADER_MAP: dict[str, Callable[[str], Awaitable[Any]]] = {
    # Detection
    "yolo11-face": load_yolo_model,
    "yolo11-license-plate": load_yolo_model,
    "yolov8n-pose": load_yolo_model,
    "threat-detection-yolov8n": load_threat_detection_model,
    "smoke-fire-yolov8n": load_smoke_fire_model,
    "yolo-world-s": load_yolo_world_model,
    "vehicle-damage-detection": load_vehicle_damage_model,
    "yolo26-general": load_yolo_model,
    # Classification
    "vehicle-segment-classification": load_vehicle_classifier,
    "pet-classifier": load_pet_classifier_model,
    "fashion-clip": load_fashion_clip_model,
    "violence-detection": load_violence_model,
    "weather-classification": load_weather_model,
    "vit-age-classifier": load_age_classifier_model,
    "vit-gender-classifier": load_gender_classifier_model,
    # Segmentation
    "segformer-b2-clothes": load_segformer_model,
    # Embedding / Re-ID
    "siglip2-base-patch16-224": load_clip_model,
    "osnet-ain-x1-0": load_osnet_model,
    # Pose
    "vitpose-small": load_vitpose_model,
    # Depth
    "depth-anything-v2-tiny": load_depth_model,
    # Action recognition
    "stgcn-plus-plus": load_stgcn_model,
    "xclip-base": load_xclip_model,
    # Vision-language
    "florence-2-large": load_florence_model,
    # Preprocessing
    "zero-dce-plus-plus": load_zero_dce_model,
    # Quality assessment
    "brisque-quality": load_brisque_model,
    # OCR / ALPR
    "paddleocr": load_paddle_ocr,
    "fast-alpr": load_fast_alpr,
}

# Path to models.yml — placed at /app/models.yml inside the container by Dockerfile
_MODELS_YML = Path(__file__).parents[2] / "models.yml"


def _resolve_model_path(m: dict[str, Any], base_path: str) -> str:
    """Compute the runtime filesystem path for a model entry from models.yml.

    Priority:
      1. runtime_path  — used verbatim (library sentinels like "piq", "fast-alpr")
      2. local_path + runtime_file  — directory model with a specific weight file
      3. local_path  — directory model (most common case)

    local_path values in models.yml are relative to AI_MODELS_PATH and start
    with "model-zoo/". The container's MODEL_ZOO_PATH env var already points
    to that "model-zoo/" directory, so we strip the prefix before joining.
    """
    if m.get("runtime_path"):
        return str(m["runtime_path"])

    local = m.get("local_path") or ""
    # Strip the "model-zoo/" prefix — base_path already ends at model-zoo/
    if local.startswith("model-zoo/"):
        rel = local[len("model-zoo/") :]
    else:
        rel = local

    if not rel:
        return base_path

    if m.get("runtime_file"):
        return f"{base_path}/{rel}/{m['runtime_file']}"
    return f"{base_path}/{rel}"


def _init_model_zoo() -> dict[str, ModelConfig]:
    """Initialize the MODEL_ZOO registry from models.yml (single source of truth).

    Reads /app/models.yml (placed there by the Dockerfile COPY instruction),
    filters to models with service "backend" or "both" that have a known
    loader in _LOADER_MAP, and constructs a ModelConfig for each.

    The base path is resolved via _get_model_zoo_base_path() which reads the
    MODEL_ZOO_PATH environment variable (default: /models/model-zoo).

    Returns:
        Dictionary mapping model names to ModelConfig instances.
    """
    base_path = _get_model_zoo_base_path()

    if not _MODELS_YML.exists():
        logger.error(
            f"models.yml not found at {_MODELS_YML}. "
            "Ensure the Dockerfile copies models.yml into /app/. "
            "Falling back to empty model zoo."
        )
        return {}

    try:
        entries: list[dict[str, Any]] = yaml.safe_load(_MODELS_YML.read_text())["models"]
    except Exception:
        logger.exception(f"Failed to parse {_MODELS_YML}. Falling back to empty model zoo.")
        return {}

    result: dict[str, ModelConfig] = {}
    for m in entries:
        if m.get("service") not in ("backend", "both"):
            continue

        name = m["name"]
        if name not in _LOADER_MAP:
            logger.debug(f"models.yml entry '{name}' has no entry in _LOADER_MAP — skipped")
            continue

        path = _resolve_model_path(m, base_path)
        result[name] = ModelConfig(
            name=name,
            path=path,
            category=m.get("category", "other"),
            vram_mb=int(m.get("vram_mb", 0)),
            load_fn=_LOADER_MAP[name],
            enabled=bool(m.get("enabled", True)),
            available=False,
            priority=str(m.get("priority", "medium")),
            preload=bool(m.get("preload", False)),
            never_evict=bool(m.get("never_evict", False)),
        )

    logger.info(
        f"Model zoo initialised from models.yml: "
        f"{sum(1 for c in result.values() if c.enabled)} enabled, "
        f"{sum(1 for c in result.values() if not c.enabled)} disabled"
    )
    return result


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
    for the primary models (Nemotron and YOLO26v2).

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
        self._previously_loaded: set[str] = set()  # Track models that have been loaded before
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

    async def _load_model(self, model_name: str, restart_reason: str | None = None) -> Any:
        """Load a model into memory.

        Args:
            model_name: Name of the model to load
            restart_reason: If this is a restart, the reason (oom, crash, manual, health_check).
                           If None and model was previously loaded, defaults to 'manual'.

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

        # Check if this is a restart (model was previously loaded)
        is_restart = model_name in self._previously_loaded

        logger.info(f"Loading model {model_name} (~{config.vram_mb}MB VRAM)")

        # Track load time for metrics (NEM-4145)
        start_time = time.perf_counter()

        # Hard timeout for model loading: prevents a single slow model from
        # blocking the enrichment pipeline indefinitely and keeps the event loop
        # responsive for health checks.  The underlying run_in_executor thread
        # will keep running, but the asyncio coroutine is freed so other tasks
        # (watchdog, health endpoints) can execute.
        _MODEL_LOAD_TIMEOUT = 20.0

        try:
            # Add Pyroscope label for per-model profiling
            try:
                import pyroscope

                with pyroscope.tag_wrapper({"model": model_name}):
                    model = await asyncio.wait_for(
                        config.load_fn(config.path),
                        timeout=_MODEL_LOAD_TIMEOUT,
                    )
            except ImportError:
                # Pyroscope not installed, load without tagging
                model = await asyncio.wait_for(
                    config.load_fn(config.path),
                    timeout=_MODEL_LOAD_TIMEOUT,
                )
        except TimeoutError:
            load_duration = time.perf_counter() - start_time
            logger.error(
                "Model load timed out after %.1fs — skipping %s "
                "(background thread will finish but event loop is now free)",
                load_duration,
                model_name,
            )
            raise RuntimeError(
                f"Model {model_name} load timed out after {_MODEL_LOAD_TIMEOUT}s"
            ) from None

        except RuntimeError as e:
            # Check if this is an optional dependency not being installed
            # (e.g., paddleocr). Log at INFO level for missing optional deps.
            error_msg = str(e).lower()
            if "not installed" in error_msg or "optional" in error_msg:
                logger.info(
                    f"Model {model_name} unavailable: {e}",
                    extra={"model_name": model_name},
                )
            else:
                logger.error(
                    "Failed to load model",
                    exc_info=True,
                    extra={"model_name": model_name},
                )
            raise

        except Exception:
            logger.error("Failed to load model", exc_info=True, extra={"model_name": model_name})
            raise

        # Happy path: all except branches raise, so reaching here means success.
        load_duration = time.perf_counter() - start_time
        set_model_load_duration(model_name, load_duration)

        self._loaded_models[model_name] = model

        # Mark as available after successful load
        config.available = True

        # Track that this model has been loaded (for restart detection)
        self._previously_loaded.add(model_name)

        # Record restart metric if this is a reload (NEM-4145)
        if is_restart:
            reason = restart_reason if restart_reason else "manual"
            record_model_restart(model_name, reason)
            logger.info(
                f"Successfully reloaded model {model_name} in {load_duration:.2f}s "
                f"(restart reason: {reason})"
            )
        else:
            logger.info(f"Successfully loaded model {model_name} in {load_duration:.2f}s")

        return model

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
                # torch not installed - no CUDA cache to clear.
                # Model unload completes successfully without CUDA cleanup.
                # See: NEM-2540 for rationale
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
                # torch not installed - no CUDA cache to clear.
                # Full model unload completes successfully without CUDA cleanup.
                # See: NEM-2540 for rationale
                pass

        logger.info("All models unloaded")

    async def reload(self, model_name: str, reason: str) -> Any:
        """Reload a model with a specific restart reason.

        This method unloads the model if loaded, then reloads it.
        The restart is recorded with the specified reason for metrics tracking.

        Args:
            model_name: Name of the model to reload
            reason: Restart reason, one of: 'oom', 'crash', 'manual', 'health_check'

        Returns:
            Reloaded model instance

        Raises:
            KeyError: If model name is not in MODEL_ZOO
            RuntimeError: If model is disabled or loading fails
            ValueError: If reason is not a valid restart reason
        """
        from backend.core.metrics import MODEL_RESTART_REASONS

        if reason not in MODEL_RESTART_REASONS:
            raise ValueError(
                f"Invalid restart reason '{reason}'. "
                f"Valid reasons are: {', '.join(sorted(MODEL_RESTART_REASONS))}"
            )

        async with self._lock:
            # Unload if currently loaded
            if model_name in self._loaded_models:
                await self._unload_model(model_name)
                self._load_counts.pop(model_name, None)

            # Reload with the specified reason
            model = await self._load_model(model_name, restart_reason=reason)
            self._load_counts[model_name] = 1
            return model

    def get_status(self) -> ModelManagerStatus:
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
