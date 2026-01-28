"""Combined Enrichment Service for Detection Classification.

HTTP server hosting multiple smaller classification models for enriching
YOLO26v2 detections with additional attributes.

Models hosted:
1. Vehicle Segment Classification (~1.5GB) - ResNet-50 for vehicle type/color
2. Pet Classifier (~200MB) - ResNet-18 for dog/cat classification
3. FashionSigLIP (~800MB) - Zero-shot clothing attribute extraction (57% more accurate)
4. Depth Anything V2 Small (~150MB) - Monocular depth estimation

Port: 8094 (configurable via PORT env var)
Expected VRAM: ~2.65GB total
"""

import asyncio
import base64
import binascii
import io
import logging
import os
import time
import warnings
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from model_manager import ModelConfig, ModelPriority, OnDemandModelManager
from PIL import Image, UnidentifiedImageError
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field

# Suppress transformers deprecation warning for ConvNextFeatureExtractor
# The warning states it will be removed in transformers v5, recommending ConvNextImageProcessor.
# We use AutoImageProcessor which handles this automatically, so we can safely suppress the warning.
# See: https://huggingface.co/docs/transformers/en/model_doc/auto#transformers.AutoImageProcessor
warnings.filterwarnings(
    "ignore",
    message="The class ConvNextFeatureExtractor is deprecated",
    category=FutureWarning,
    module="transformers.models.convnext.feature_extraction_convnext",
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# =============================================================================
# Pyroscope Continuous Profiling (NEM-3921)
# =============================================================================
def init_profiling() -> None:
    """Initialize Pyroscope continuous profiling for ai-enrichment service.

    This function configures Pyroscope for continuous CPU profiling of the
    heavy enrichment service. It enables identification of performance
    bottlenecks in model inference and request handling.

    Configuration is via environment variables:
    - PYROSCOPE_ENABLED: Enable/disable profiling (default: true)
    - PYROSCOPE_URL: Pyroscope server address (default: http://pyroscope:4040)
    - SERVICE_NAME: Service name in Pyroscope (default: ai-enrichment)
    - GPU_TIER: GPU tier tag for filtering (default: heavy)
    - ENVIRONMENT: Environment tag (default: production)

    The function gracefully handles:
    - Missing pyroscope-io package (ImportError)
    - Configuration errors (logs warning, doesn't fail startup)
    """
    if os.getenv("PYROSCOPE_ENABLED", "true").lower() != "true":
        logger.info("Pyroscope profiling disabled (PYROSCOPE_ENABLED != true)")
        return

    try:
        import pyroscope

        service_name = os.getenv("SERVICE_NAME", "ai-enrichment")
        pyroscope_server = os.getenv("PYROSCOPE_URL", "http://pyroscope:4040")

        pyroscope.configure(
            application_name=service_name,
            server_address=pyroscope_server,
            tags={
                "service": service_name,
                "environment": os.getenv("ENVIRONMENT", "production"),
                "gpu_tier": os.getenv("GPU_TIER", "heavy"),
            },
            oncpu=True,
            gil_only=False,  # Profile all threads, not just GIL-holding threads
            enable_logging=True,
        )
        logger.info(f"Pyroscope profiling initialized: {service_name} -> {pyroscope_server}")
    except ImportError:
        logger.debug("Pyroscope profiling skipped: pyroscope-io not installed")
    except Exception as e:
        logger.warning(f"Failed to initialize Pyroscope profiling: {e}")


# Initialize profiling early (before model loading)
init_profiling()

# Track service start time for uptime calculation
SERVICE_START_TIME = datetime.now(UTC)

# =============================================================================
# Prometheus Metrics
# =============================================================================
# Total inference requests
INFERENCE_REQUESTS_TOTAL = Counter(
    "enrichment_inference_requests_total",
    "Total number of inference requests",
    ["endpoint", "status"],
)

# Inference latency histogram (buckets tuned for typical inference times)
INFERENCE_LATENCY_SECONDS = Histogram(
    "enrichment_inference_latency_seconds",
    "Inference latency in seconds",
    ["endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# Model status gauges (1 = loaded, 0 = not loaded)
VEHICLE_MODEL_LOADED = Gauge(
    "enrichment_vehicle_model_loaded",
    "Whether the vehicle classifier is loaded (1) or not (0)",
)
PET_MODEL_LOADED = Gauge(
    "enrichment_pet_model_loaded",
    "Whether the pet classifier is loaded (1) or not (0)",
)
CLOTHING_MODEL_LOADED = Gauge(
    "enrichment_clothing_model_loaded",
    "Whether the clothing classifier is loaded (1) or not (0)",
)
DEPTH_MODEL_LOADED = Gauge(
    "enrichment_depth_model_loaded",
    "Whether the depth estimator is loaded (1) or not (0)",
)

# GPU metrics gauge
GPU_MEMORY_USED_GB = Gauge(
    "enrichment_gpu_memory_used_gb",
    "GPU memory used in GB",
)

# Unified enrichment endpoint metrics
ENRICH_MODELS_USED = Counter(
    "enrichment_enrich_models_used_total",
    "Models used in unified enrichment requests",
    ["model"],
)
POSE_MODEL_LOADED = Gauge(
    "enrichment_pose_model_loaded",
    "Whether the pose analyzer is loaded (1) or not (0)",
)

# Size limits for image uploads (10MB is reasonable for security camera images)
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_BASE64_SIZE_BYTES = int(MAX_IMAGE_SIZE_BYTES * 4 / 3) + 100  # ~13.3MB + padding


def validate_model_path(path: str) -> str:
    """Validate model path to prevent path traversal attacks.

    Args:
        path: The model path to validate (local path or HuggingFace ID)

    Returns:
        The validated path (normalized if local)

    Raises:
        ValueError: If path contains traversal sequences or is otherwise invalid
    """
    # Reject paths with traversal sequences
    if ".." in path:
        logger.warning(f"Suspicious model path detected (traversal sequence): {path}")
        raise ValueError(f"Invalid model path: path traversal sequences not allowed: {path}")

    # For local paths, normalize and validate
    if path.startswith("/") or path.startswith("./"):
        abs_path = str(Path(path).resolve())

        # Check again after normalization (handles things like "/foo/bar/../../../etc/passwd")
        # Path.resolve() resolves ".." so we compare the result
        if not abs_path.startswith("/") and not abs_path.startswith("./"):
            logger.warning(f"Suspicious model path after normalization: {path} -> {abs_path}")
            raise ValueError(f"Invalid model path: path resolves outside expected location: {path}")

        logger.debug(f"Local model path validated: {path} -> {abs_path}")
        return abs_path

    # Non-local paths (HuggingFace IDs, etc.) - just return as-is
    return path


# Magic bytes for image format detection
# These are the first few bytes that identify image file formats
IMAGE_MAGIC_BYTES: dict[bytes, str] = {
    b"\xff\xd8\xff": "JPEG",  # JPEG images
    b"\x89PNG\r\n\x1a\n": "PNG",  # PNG images
    b"GIF87a": "GIF",  # GIF87a
    b"GIF89a": "GIF",  # GIF89a
    b"BM": "BMP",  # BMP images
    b"RIFF": "WEBP",  # WEBP (RIFF container, need to check for WEBP)
}


def validate_image_magic_bytes(image_bytes: bytes) -> tuple[bool, str]:  # noqa: PLR0911 - Multiple validation checks require multiple returns
    """Validate image data by checking magic bytes (file signature).

    This provides an early check before passing to PIL, catching obvious
    non-image files like text files, videos, or corrupted data.

    Args:
        image_bytes: Raw image file bytes

    Returns:
        Tuple of (is_valid, detected_format_or_error_message)
    """
    if not image_bytes:
        return False, "Empty image data"

    if len(image_bytes) < 8:
        return False, "Image data too small to be a valid image"

    # Check for known image magic bytes
    for magic, fmt in IMAGE_MAGIC_BYTES.items():
        if image_bytes.startswith(magic):
            # Special case for WEBP: RIFF container must contain "WEBP"
            if fmt == "WEBP":
                if len(image_bytes) >= 12 and image_bytes[8:12] == b"WEBP":
                    return True, "WEBP"
                # It's a RIFF file but not WEBP (could be AVI, WAV, etc.)
                continue
            return True, fmt

    # Check for common non-image file signatures to provide better errors
    # Text files often start with common ASCII characters or BOM
    if image_bytes[:3] in (b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff"):  # UTF-8/16 BOM
        return False, "Text file (BOM detected), not an image"

    # Check if it looks like plain text (mostly printable ASCII)
    sample = image_bytes[:256]
    printable_count = sum(1 for b in sample if 32 <= b <= 126 or b in (9, 10, 13))
    if printable_count > len(sample) * 0.85:
        return False, "Text file detected, not an image"

    # Common video format signatures
    if image_bytes[:4] == b"\x00\x00\x00\x1c" or image_bytes[4:8] == b"ftyp":
        return False, "Video file (MP4/MOV), not an image"
    if image_bytes[:4] == b"\x1aE\xdf\xa3":  # EBML (Matroska/WebM)
        return False, "Video file (MKV/WebM), not an image"
    if image_bytes[:4] == b"RIFF" and len(image_bytes) >= 12:
        if image_bytes[8:12] == b"AVI ":
            return False, "Video file (AVI), not an image"
        if image_bytes[8:12] == b"WAVE":
            return False, "Audio file (WAV), not an image"

    return False, "Unknown file format, not a recognized image type"


# =============================================================================
# Vehicle Segment Classification (ResNet-50)
# =============================================================================

# Vehicle class labels (from classes.txt)
VEHICLE_SEGMENT_CLASSES: list[str] = [
    "articulated_truck",
    "background",
    "bicycle",
    "bus",
    "car",
    "motorcycle",
    "non_motorized_vehicle",
    "pedestrian",
    "pickup_truck",
    "single_unit_truck",
    "work_van",
]

# Classes that are not vehicles (filter these from results)
NON_VEHICLE_CLASSES: frozenset[str] = frozenset({"background", "pedestrian"})

# Commercial/delivery vehicle classes
COMMERCIAL_VEHICLE_CLASSES: frozenset[str] = frozenset(
    {
        "articulated_truck",
        "single_unit_truck",
        "work_van",
    }
)

# Simplified display names for context strings
VEHICLE_DISPLAY_NAMES: dict[str, str] = {
    "articulated_truck": "articulated truck (semi/18-wheeler)",
    "bicycle": "bicycle",
    "bus": "bus",
    "car": "car/sedan",
    "motorcycle": "motorcycle",
    "non_motorized_vehicle": "non-motorized vehicle",
    "pickup_truck": "pickup truck",
    "single_unit_truck": "single-unit truck (box truck/delivery)",
    "work_van": "work van/delivery van",
}

# Common vehicle colors for color classification - reserved for future use
# with FashionSigLIP zero-shot color classification
_VEHICLE_COLORS: list[str] = [
    "white",
    "black",
    "silver",
    "gray",
    "red",
    "blue",
    "green",
    "brown",
    "beige",
    "yellow",
    "orange",
    "gold",
]


class VehicleClassifier:
    """ResNet-50 Vehicle Segment Classification model wrapper."""

    def __init__(self, model_path: str, device: str = "cuda:0"):
        """Initialize vehicle classifier.

        Args:
            model_path: Path to model directory containing pytorch_model.bin
            device: Device to run inference on

        Raises:
            ValueError: If model_path contains path traversal sequences
        """
        self.model_path = validate_model_path(model_path)
        self.device = device
        self.model: Any = None
        self.transform: Any = None
        self.classes: list[str] = VEHICLE_SEGMENT_CLASSES

        logger.info(f"Initializing VehicleClassifier from {self.model_path}")

    def load_model(self) -> None:
        """Load the ResNet-50 model into memory."""
        from torchvision import models, transforms

        logger.info("Loading Vehicle Segment Classification model...")

        model_dir = Path(self.model_path)

        # Load class names if available
        classes_file = (model_dir / "classes.txt").resolve()
        # Validate path is within model directory to prevent path traversal
        if classes_file.exists() and str(classes_file).startswith(str(model_dir.resolve())):
            self.classes = classes_file.read_text().splitlines()
            logger.info(f"Loaded {len(self.classes)} classes from classes.txt")

        # Create ResNet-50 model architecture
        model = models.resnet50(weights=None)

        # Modify final layer to match number of classes
        num_ftrs = model.fc.in_features
        model.fc = torch.nn.Linear(num_ftrs, len(self.classes))

        # Load trained weights
        weights_file = model_dir / "pytorch_model.bin"
        if not weights_file.exists():
            raise FileNotFoundError(f"Model weights not found: {weights_file}")

        state_dict = torch.load(weights_file, map_location="cpu", weights_only=True)
        model.load_state_dict(state_dict)

        # Move to device
        if "cuda" in self.device and torch.cuda.is_available():
            model = model.to(self.device).half()  # Use fp16 for efficiency
            logger.info(f"VehicleClassifier loaded on {self.device} with fp16")
        else:
            self.device = "cpu"
            logger.info("VehicleClassifier using CPU")

        model.eval()
        self.model = model

        # Define image transforms (same as training)
        self.transform = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]
        )

        logger.info("VehicleClassifier loaded successfully")

    def classify(self, image: Image.Image, top_k: int = 3) -> dict[str, Any]:
        """Classify vehicle type from an image.

        Args:
            image: PIL Image of vehicle crop
            top_k: Number of top classes to include in scores

        Returns:
            Dictionary with vehicle_type, confidence, is_commercial, all_scores
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        # Ensure RGB mode
        rgb_image = image.convert("RGB") if image.mode != "RGB" else image

        # Preprocess image
        input_tensor = self.transform(rgb_image).unsqueeze(0)

        # Move to device with correct dtype
        model_dtype = next(self.model.parameters()).dtype
        input_tensor = input_tensor.to(self.device, model_dtype)

        # Run inference
        with torch.inference_mode():
            outputs = self.model(input_tensor)
            probs = torch.nn.functional.softmax(outputs, dim=-1)[0]

        # Get scores for all classes
        all_class_scores = {cls: float(probs[i].item()) for i, cls in enumerate(self.classes)}

        # Filter out non-vehicle classes for ranking
        vehicle_scores = {
            cls: score for cls, score in all_class_scores.items() if cls not in NON_VEHICLE_CLASSES
        }

        # Sort by score
        sorted_scores = sorted(vehicle_scores.items(), key=lambda x: x[1], reverse=True)

        # Get top prediction
        top_class = sorted_scores[0][0]
        top_confidence = sorted_scores[0][1]

        # Get top_k scores
        top_k_scores = dict(sorted_scores[:top_k])

        return {
            "vehicle_type": top_class,
            "display_name": VEHICLE_DISPLAY_NAMES.get(top_class, top_class),
            "confidence": round(top_confidence, 4),
            "is_commercial": top_class in COMMERCIAL_VEHICLE_CLASSES,
            "all_scores": {k: round(v, 4) for k, v in top_k_scores.items()},
        }


# =============================================================================
# Pet Classifier (ResNet-18)
# =============================================================================

PET_LABELS = ["cat", "dog"]


class PetClassifier:
    """ResNet-18 Cat/Dog classification model wrapper."""

    def __init__(self, model_path: str, device: str = "cuda:0"):
        """Initialize pet classifier.

        Args:
            model_path: Path to model directory (HuggingFace format)
            device: Device to run inference on

        Raises:
            ValueError: If model_path contains path traversal sequences
        """
        self.model_path = validate_model_path(model_path)
        self.device = device
        self.model: Any = None
        self.processor: Any = None

        logger.info(f"Initializing PetClassifier from {self.model_path}")

    def load_model(self) -> None:
        """Load the ResNet-18 pet classifier model."""
        from transformers import AutoImageProcessor, AutoModelForImageClassification

        logger.info("Loading Pet Classifier model...")

        self.processor = AutoImageProcessor.from_pretrained(self.model_path, local_files_only=True)
        self.model = AutoModelForImageClassification.from_pretrained(
            self.model_path, local_files_only=True
        )

        # Move to device
        if "cuda" in self.device and torch.cuda.is_available():
            self.model = self.model.to(self.device).half()  # Use fp16 for efficiency
            logger.info(f"PetClassifier loaded on {self.device} with fp16")
        else:
            self.device = "cpu"
            logger.info("PetClassifier using CPU")

        self.model.eval()
        logger.info("PetClassifier loaded successfully")

    def classify(self, image: Image.Image) -> dict[str, Any]:
        """Classify whether an image contains a cat or dog.

        Args:
            image: PIL Image of animal crop

        Returns:
            Dictionary with pet_type, breed, confidence, scores
        """
        if self.model is None or self.processor is None:
            raise RuntimeError("Model not loaded")

        # Preprocess image
        inputs = self.processor(images=image, return_tensors="pt")

        # Move to device with correct dtype
        model_dtype = next(self.model.parameters()).dtype
        if next(self.model.parameters()).is_cuda:
            inputs = {k: v.to(self.device, model_dtype) for k, v in inputs.items()}

        # Run inference
        with torch.inference_mode():
            outputs = self.model(**inputs)
            logits = outputs.logits

        # Get probabilities via softmax
        probs = torch.nn.functional.softmax(logits, dim=-1)[0]

        # Get predicted class
        pred_idx = int(probs.argmax().item())
        confidence = float(probs[pred_idx].item())

        # Map to labels based on model's id2label config
        if hasattr(self.model.config, "id2label") and self.model.config.id2label:
            raw_label = self.model.config.id2label.get(str(pred_idx), PET_LABELS[pred_idx])
            # Normalize "cats" -> "cat", "dogs" -> "dog"
            if raw_label.endswith("s"):
                raw_label = raw_label[:-1]
        else:
            raw_label = PET_LABELS[pred_idx]

        # Extract scores
        cat_score = float(probs[0].item())  # Index 0 = cats
        dog_score = float(probs[1].item())  # Index 1 = dogs

        return {
            "pet_type": raw_label,
            "breed": "unknown",  # Basic model doesn't provide breed
            "confidence": round(confidence, 4),
            "is_household_pet": True,
            "cat_score": round(cat_score, 4),
            "dog_score": round(dog_score, 4),
        }


# =============================================================================
# Clothing Classifier (FashionSigLIP)
# =============================================================================

# Category-specific confidence thresholds for clothing classification
# Lower thresholds for suspicious categories ensure they are flagged with less certainty
# Higher thresholds for normal categories reduce false positives
CLOTHING_CATEGORY_THRESHOLDS: dict[str, float] = {
    "suspicious": 0.25,  # Low threshold - flag even with moderate confidence
    "delivery": 0.40,  # Medium threshold - clear uniform identification
    "authority": 0.45,  # Medium-high threshold - avoid misidentifying authority figures
    "utility": 0.40,  # Medium threshold - work uniforms
    "casual": 0.35,  # Medium-low threshold - common default
    "weather": 0.35,  # Medium-low threshold - weather-appropriate clothing
    "carrying": 0.30,  # Low threshold - important for threat assessment
    "athletic": 0.35,  # Medium-low threshold
}

# Default threshold for categories not explicitly listed
DEFAULT_CLOTHING_THRESHOLD: float = 0.35

# Security-focused clothing classification prompts organized by category (~40 prompts)
SECURITY_CLOTHING_PROMPTS_BY_CATEGORY: dict[str, list[str]] = {
    # Potentially suspicious attire - items that may indicate concealment or criminal intent
    "suspicious": [
        "person wearing dark hoodie with hood up",
        "person wearing ski mask or balaclava",
        "person wearing all black clothing",
        "person with face partially covered",
        "person wearing face mask at night",
        "person wearing gloves in warm weather",
        "person with hat and sunglasses obscuring face",
        "person wearing bandana over face",
    ],
    # Delivery uniforms - legitimate package carriers
    "delivery": [
        "delivery driver in uniform",
        "postal worker in uniform",
        "UPS driver in brown uniform",
        "FedEx driver in purple uniform",
        "Amazon delivery driver in blue vest",
        "DoorDash delivery person with red bag",
        "food delivery courier with insulated bag",
        "package courier in company uniform",
    ],
    # Authority and emergency services
    "authority": [
        "police officer in uniform",
        "security guard in uniform",
        "firefighter in gear",
        "paramedic or EMT in uniform",
        "military personnel in uniform",
    ],
    # Utility and maintenance workers
    "utility": [
        "maintenance worker in uniform",
        "utility worker with safety vest",
        "construction worker in hard hat",
        "electrician in work clothes",
        "landscaper or gardener in work clothes",
        "cable technician in company uniform",
        "plumber in work attire",
    ],
    # Casual and everyday wear
    "casual": [
        "person in casual everyday clothes",
        "person in casual business attire",
        "person in jeans and t-shirt",
        "person in shorts and casual top",
        "person in professional suit",
        "person in formal dress attire",
    ],
    # Weather-appropriate clothing
    "weather": [
        "person in rain jacket or raincoat",
        "person in winter coat",
        "person in light summer clothing",
        "person wearing umbrella or rain gear",
    ],
    # Carrying items - critical for security assessment
    "carrying": [
        "person carrying a large box or package",
        "person with a backpack",
        "person carrying a duffel bag",
        "person carrying tools or equipment",
        "person carrying nothing visible",
        "person with hands in pockets",
    ],
    # Athletic and active wear
    "athletic": [
        "person in workout clothes",
        "person walking dog in casual wear",
        "person jogging in athletic wear",
        "person in outdoor or hiking clothing",
    ],
}

# Flatten prompts for backward compatibility with existing classify() interface
SECURITY_CLOTHING_PROMPTS: list[str] = [
    prompt for prompts in SECURITY_CLOTHING_PROMPTS_BY_CATEGORY.values() for prompt in prompts
]

# Suspicious clothing categories (for is_suspicious flag)
SUSPICIOUS_CATEGORIES: frozenset[str] = frozenset(
    SECURITY_CLOTHING_PROMPTS_BY_CATEGORY["suspicious"]
)

# Service/uniform categories (for is_service_uniform flag)
SERVICE_CATEGORIES: frozenset[str] = frozenset(
    SECURITY_CLOTHING_PROMPTS_BY_CATEGORY["delivery"]
    + SECURITY_CLOTHING_PROMPTS_BY_CATEGORY["utility"]
)

# Authority categories (for special handling)
AUTHORITY_CATEGORIES: frozenset[str] = frozenset(SECURITY_CLOTHING_PROMPTS_BY_CATEGORY["authority"])

# Carrying categories (important for threat context)
CARRYING_CATEGORIES: frozenset[str] = frozenset(SECURITY_CLOTHING_PROMPTS_BY_CATEGORY["carrying"])


def get_category_for_prompt(prompt: str) -> str:
    """Get the category name for a given prompt.

    Args:
        prompt: The clothing classification prompt

    Returns:
        Category name (e.g., "suspicious", "delivery", "casual")
    """
    for category, prompts in SECURITY_CLOTHING_PROMPTS_BY_CATEGORY.items():
        if prompt in prompts:
            return category
    return "unknown"


def get_threshold_for_category(category: str) -> float:
    """Get the confidence threshold for a given category.

    Args:
        category: The category name

    Returns:
        Confidence threshold for flagging this category
    """
    return CLOTHING_CATEGORY_THRESHOLDS.get(category, DEFAULT_CLOTHING_THRESHOLD)


class ClothingClassifier:
    """FashionSigLIP zero-shot clothing classification model wrapper.

    FashionSigLIP provides 57% improved accuracy over FashionCLIP:
    - Text-to-Image MRR: 0.239 vs 0.165 (FashionCLIP2.0)
    - Text-to-Image Recall@1: 0.121 vs 0.077 (FashionCLIP2.0)
    - Text-to-Image Recall@10: 0.340 vs 0.249 (FashionCLIP2.0)

    Uses open_clip library directly instead of transformers.AutoModel because
    the Marqo model custom wrapper has meta tensor issues when loaded via
    transformers that cause "Cannot copy out of meta tensor" errors.
    """

    def __init__(self, model_path: str, device: str = "cuda:0"):
        """Initialize clothing classifier.

        Args:
            model_path: Path to FashionSigLIP model directory or HuggingFace model ID
            device: Device to run inference on

        Raises:
            ValueError: If model_path contains path traversal sequences
        """
        self.model_path = validate_model_path(model_path)
        self.device = device
        self.model: Any = None
        self.preprocess: Any = None
        self.tokenizer: Any = None

        logger.info(f"Initializing ClothingClassifier from {self.model_path}")

    def load_model(self) -> None:
        """Load the FashionSigLIP model using open_clip."""
        from open_clip import create_model_from_pretrained, get_tokenizer

        logger.info("Loading FashionSigLIP model...")

        # Convert path to HuggingFace hub format if needed
        if self.model_path.startswith("/") or self.model_path.startswith("./"):
            # Local path - use hf-hub format with Marqo FashionSigLIP model
            hub_path = "hf-hub:Marqo/marqo-fashionSigLIP"
            logger.info(f"Local path {self.model_path} detected, using HuggingFace hub: {hub_path}")
        elif "/" in self.model_path and not self.model_path.startswith("hf-hub:"):
            # HuggingFace model ID without prefix
            hub_path = f"hf-hub:{self.model_path}"
        else:
            hub_path = self.model_path

        # Determine target device before loading
        # Pass device directly to create_model_from_pretrained to avoid
        # "Cannot copy out of meta tensor" error when loading HF Hub models
        # that use meta tensors during initialization
        if "cuda" in self.device and torch.cuda.is_available():
            target_device = self.device
        else:
            target_device = "cpu"
            self.device = "cpu"

        # Load model and preprocess using open_clip with device specified
        # This loads weights directly onto the target device, avoiding the
        # meta tensor issue that occurs when loading to CPU then moving
        self.model, self.preprocess = create_model_from_pretrained(hub_path, device=target_device)
        self.tokenizer = get_tokenizer(hub_path)

        logger.info(f"ClothingClassifier loaded on {self.device}")
        self.model.eval()
        logger.info("ClothingClassifier loaded successfully")

    def classify(
        self,
        image: Image.Image,
        prompts: list[str] | None = None,
        top_k: int = 3,
    ) -> dict[str, Any]:
        """Classify clothing in a person crop using zero-shot classification.

        Args:
            image: PIL Image of person crop
            prompts: Custom text prompts (defaults to SECURITY_CLOTHING_PROMPTS)
            top_k: Number of top categories to include in scores

        Returns:
            Dictionary with clothing_type, color, style, confidence, etc.
        """
        if self.model is None or self.preprocess is None or self.tokenizer is None:
            raise RuntimeError("Model not loaded")

        if prompts is None:
            prompts = SECURITY_CLOTHING_PROMPTS

        # Ensure RGB mode
        rgb_image = image.convert("RGB") if image.mode != "RGB" else image

        # Process image using open_clip preprocess
        image_tensor = self.preprocess(rgb_image).unsqueeze(0).to(self.device)

        # Tokenize text prompts
        text_tokens = self.tokenizer(prompts).to(self.device)

        # Get image and text features
        with torch.inference_mode():
            image_features = self.model.encode_image(image_tensor)
            text_features = self.model.encode_text(text_tokens)

            # Normalize features
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

            # Compute similarity scores
            similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)
            scores = similarity[0].cpu().numpy()

        # Create score dictionary
        all_scores = {prompt: float(score) for prompt, score in zip(prompts, scores, strict=True)}

        # Sort by score and get top result
        sorted_items = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
        top_category = sorted_items[0][0]
        top_confidence = sorted_items[0][1]

        # Keep only top_k scores
        top_k_scores = dict(sorted_items[:top_k])

        # Determine classification flags
        is_suspicious = top_category in SUSPICIOUS_CATEGORIES
        is_service = top_category in SERVICE_CATEGORIES

        # Generate human-readable description
        if is_service:
            description = f"Service worker: {top_category.replace('person wearing ', '')}"
        elif is_suspicious:
            description = f"Alert: {top_category.replace('person wearing ', '')}"
        else:
            description = top_category.replace("person wearing ", "").capitalize()

        # Extract basic clothing attributes
        clothing_type = self._extract_clothing_type(top_category)
        color = self._extract_color(top_category)
        style = self._extract_style(top_category)

        return {
            "clothing_type": clothing_type,
            "color": color,
            "style": style,
            "confidence": round(top_confidence, 4),
            "top_category": top_category,
            "description": description,
            "is_suspicious": is_suspicious,
            "is_service_uniform": is_service,
            "all_scores": {k: round(v, 4) for k, v in top_k_scores.items()},
        }

    def classify_multilabel(
        self,
        image: Image.Image,
        use_category_thresholds: bool = True,
    ) -> dict[str, Any]:
        """Classify clothing with multi-label support per category.

        Unlike classify(), this method returns the best match per category,
        allowing identification of multiple attributes (e.g., suspicious hoodie
        AND carrying a backpack).

        Args:
            image: PIL Image of person crop
            use_category_thresholds: If True, use per-category confidence thresholds
                                     to filter results. If False, include all categories.

        Returns:
            Dictionary with:
            - matched_categories: Dict of category -> {prompt, confidence, above_threshold}
            - primary_category: The highest-confidence category overall
            - is_suspicious: True if any suspicious category is above threshold
            - is_service_uniform: True if any service category is above threshold
            - is_authority: True if any authority category is above threshold
            - carrying_item: Description of what person is carrying (if detected)
            - all_scores: Dict of all prompts to their confidence scores
        """
        if self.model is None or self.preprocess is None or self.tokenizer is None:
            raise RuntimeError("Model not loaded")

        # Ensure RGB mode
        rgb_image = image.convert("RGB") if image.mode != "RGB" else image

        # Process image using open_clip preprocess
        image_tensor = self.preprocess(rgb_image).unsqueeze(0).to(self.device)

        # Tokenize all prompts
        all_prompts = SECURITY_CLOTHING_PROMPTS
        text_tokens = self.tokenizer(all_prompts).to(self.device)

        # Get image and text features
        with torch.inference_mode():
            image_features = self.model.encode_image(image_tensor)
            text_features = self.model.encode_text(text_tokens)

            # Normalize features
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

            # Compute similarity scores
            similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)
            scores = similarity[0].cpu().numpy()

        # Create score dictionary for all prompts
        all_scores = {
            prompt: float(score) for prompt, score in zip(all_prompts, scores, strict=True)
        }

        # Find best match per category
        matched_categories: dict[str, dict[str, Any]] = {}
        for category, prompts in SECURITY_CLOTHING_PROMPTS_BY_CATEGORY.items():
            # Get scores for this category's prompts
            category_scores = [(p, all_scores[p]) for p in prompts]
            # Sort by score descending
            category_scores.sort(key=lambda x: x[1], reverse=True)

            best_prompt, best_score = category_scores[0]
            threshold = get_threshold_for_category(category)
            above_threshold = best_score >= threshold if use_category_thresholds else True

            matched_categories[category] = {
                "prompt": best_prompt,
                "confidence": round(best_score, 4),
                "threshold": threshold,
                "above_threshold": above_threshold,
            }

        # Find primary category (highest confidence that's above threshold)
        valid_categories = [
            (cat, data) for cat, data in matched_categories.items() if data["above_threshold"]
        ]
        if valid_categories:
            primary_category = max(valid_categories, key=lambda x: x[1]["confidence"])[0]
        else:
            # Fall back to highest confidence regardless of threshold
            primary_category = max(matched_categories.items(), key=lambda x: x[1]["confidence"])[0]

        # Determine flags based on threshold-passing categories
        suspicious_match = matched_categories.get("suspicious", {})
        is_suspicious = suspicious_match.get("above_threshold", False)

        delivery_match = matched_categories.get("delivery", {})
        utility_match = matched_categories.get("utility", {})
        is_service_uniform = delivery_match.get("above_threshold", False) or utility_match.get(
            "above_threshold", False
        )

        authority_match = matched_categories.get("authority", {})
        is_authority = authority_match.get("above_threshold", False)

        # Extract carrying item if above threshold
        carrying_match = matched_categories.get("carrying", {})
        carrying_item = None
        if carrying_match.get("above_threshold", False):
            carrying_prompt = carrying_match.get("prompt", "")
            # Extract item from prompt like "person carrying a large box or package"
            carrying_item = (
                carrying_prompt.replace("person ", "").replace("carrying ", "").replace("with ", "")
            )

        # Build result
        return {
            "matched_categories": matched_categories,
            "primary_category": primary_category,
            "primary_prompt": matched_categories[primary_category]["prompt"],
            "primary_confidence": matched_categories[primary_category]["confidence"],
            "is_suspicious": is_suspicious,
            "is_service_uniform": is_service_uniform,
            "is_authority": is_authority,
            "carrying_item": carrying_item,
            "all_scores": {k: round(v, 4) for k, v in all_scores.items()},
        }

    def _extract_clothing_type(self, category: str) -> str:
        """Extract clothing type from category string."""
        category_lower = category.lower()
        # Map keywords to clothing types, checked in order of priority
        keyword_mappings = [
            (["hoodie"], "hoodie"),
            (["jacket", "coat"], "jacket"),
            (["vest"], "vest"),
            (["uniform"], "uniform"),
            (["suit", "attire"], "formal"),
            (["athletic", "sportswear"], "athletic"),
            (["mask"], "masked"),
        ]
        for keywords, clothing_type in keyword_mappings:
            if any(kw in category_lower for kw in keywords):
                return clothing_type
        return "casual"

    def _extract_color(self, category: str) -> str:
        """Extract color from category string."""
        category_lower = category.lower()
        if "dark" in category_lower or "black" in category_lower:
            return "dark"
        elif "high-visibility" in category_lower:
            return "high-visibility"
        else:
            return "unknown"

    def _extract_style(self, category: str) -> str:
        """Extract style from category string."""
        category_lower = category.lower()
        if any(x in category_lower for x in ["suspicious", "mask", "obscured"]):
            return "suspicious"
        elif any(x in category_lower for x in ["delivery", "uniform", "worker", "vest"]):
            return "work"
        elif any(x in category_lower for x in ["athletic", "outdoor", "hiking"]):
            return "active"
        elif any(x in category_lower for x in ["business", "suit"]):
            return "formal"
        else:
            return "casual"


# =============================================================================
# Depth Estimator (Depth Anything V2 Small)
# =============================================================================


class DepthEstimator:
    """Depth Anything V2 Small monocular depth estimation model wrapper.

    This model estimates relative depth from a single RGB image. The output
    is a depth map where lower values indicate objects closer to the camera
    and higher values indicate objects farther away.

    Use cases for home security:
    - Estimate how close a person is to the camera/door
    - Detect approaching vs departing movement
    - Provide distance context to Nemotron for risk analysis
    """

    def __init__(self, model_path: str, device: str = "cuda:0"):
        """Initialize depth estimator.

        Args:
            model_path: Path to Depth Anything V2 model directory
            device: Device to run inference on

        Raises:
            ValueError: If model_path contains path traversal sequences
        """
        self.model_path = validate_model_path(model_path)
        self.device = device
        self.model: Any = None
        self.processor: Any = None

        logger.info(f"Initializing DepthEstimator from {self.model_path}")

    def load_model(self) -> None:
        """Load the Depth Anything V2 model."""
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation

        logger.info("Loading Depth Anything V2 model...")

        self.processor = AutoImageProcessor.from_pretrained(self.model_path, local_files_only=True)
        self.model = AutoModelForDepthEstimation.from_pretrained(
            self.model_path, local_files_only=True
        )

        # Move to device
        if "cuda" in self.device and torch.cuda.is_available():
            self.model = self.model.to(self.device)
            logger.info(f"DepthEstimator loaded on {self.device}")
        else:
            self.device = "cpu"
            logger.info("DepthEstimator using CPU")

        self.model.eval()
        logger.info("DepthEstimator loaded successfully")

    def estimate_depth(self, image: Image.Image) -> dict[str, Any]:
        """Estimate depth map for an image.

        Args:
            image: PIL Image to estimate depth for

        Returns:
            Dictionary containing:
            - depth_map_base64: Base64 encoded PNG depth map visualization
            - min_depth: Minimum depth value (normalized 0-1)
            - max_depth: Maximum depth value (normalized 0-1)
            - mean_depth: Mean depth value across the image
        """
        import numpy as np

        if self.model is None or self.processor is None:
            raise RuntimeError("Model not loaded")

        # Ensure RGB mode
        rgb_image = image.convert("RGB") if image.mode != "RGB" else image

        # Preprocess image
        inputs = self.processor(images=rgb_image, return_tensors="pt")

        # Move to device
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Run inference
        with torch.inference_mode():
            outputs = self.model(**inputs)
            predicted_depth = outputs.predicted_depth

        # Interpolate to original size
        prediction = torch.nn.functional.interpolate(
            predicted_depth.unsqueeze(1),
            size=rgb_image.size[::-1],  # (height, width)
            mode="bicubic",
            align_corners=False,
        ).squeeze()

        # Normalize depth map to 0-1 range
        depth_array = prediction.cpu().numpy()
        min_val = float(depth_array.min())
        max_val = float(depth_array.max())

        if max_val - min_val > 0:
            normalized_depth = (depth_array - min_val) / (max_val - min_val)
        else:
            normalized_depth = np.zeros_like(depth_array)

        # Convert to grayscale image for visualization (0-255)
        depth_visual = (normalized_depth * 255).astype(np.uint8)
        depth_image = Image.fromarray(depth_visual, mode="L")

        # Encode to base64 PNG
        buffer = io.BytesIO()
        depth_image.save(buffer, format="PNG")
        buffer.seek(0)
        depth_map_base64 = base64.b64encode(buffer.read()).decode("utf-8")

        return {
            "depth_map_base64": depth_map_base64,
            "min_depth": round(float(normalized_depth.min()), 4),
            "max_depth": round(float(normalized_depth.max()), 4),
            "mean_depth": round(float(normalized_depth.mean()), 4),
            "normalized_depth": normalized_depth,  # Keep for object distance calculation
        }

    def estimate_object_distance(
        self,
        image: Image.Image,
        bbox: list[float],
        method: str = "center",
    ) -> dict[str, Any]:
        """Estimate relative distance to an object at a bounding box location.

        Args:
            image: PIL Image
            bbox: Bounding box [x1, y1, x2, y2]
            method: How to sample depth:
                - "center": Sample at bbox center (fastest)
                - "mean": Average depth over bbox (most accurate)
                - "median": Median depth over bbox (robust to outliers)
                - "min": Minimum depth in bbox (closest point)

        Returns:
            Dictionary containing:
            - estimated_distance_m: Estimated distance in meters (relative scale)
            - relative_depth: Normalized depth value (0=close, 1=far)
            - proximity_label: Human-readable proximity description
        """
        import numpy as np

        if self.model is None or self.processor is None:
            raise RuntimeError("Model not loaded")

        # First get the full depth map
        depth_result = self.estimate_depth(image)
        normalized_depth = depth_result["normalized_depth"]

        # Extract bbox coordinates
        x1, y1, x2, y2 = bbox
        h, w = normalized_depth.shape[:2]

        # Clamp bbox to image boundaries
        x1 = max(0, min(int(x1), w - 1))
        y1 = max(0, min(int(y1), h - 1))
        x2 = max(0, min(int(x2), w - 1))
        y2 = max(0, min(int(y2), h - 1))

        # Handle invalid bbox
        if x2 <= x1 or y2 <= y1:
            relative_depth = 0.5
        elif method == "center":
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            relative_depth = float(normalized_depth[center_y, center_x])
        elif method == "mean":
            region = normalized_depth[y1:y2, x1:x2]
            relative_depth = float(np.mean(region))
        elif method == "median":
            region = normalized_depth[y1:y2, x1:x2]
            relative_depth = float(np.median(region))
        elif method == "min":
            region = normalized_depth[y1:y2, x1:x2]
            relative_depth = float(np.min(region))
        else:
            raise ValueError(f"Unknown depth sampling method: {method}")

        # Convert relative depth to approximate distance
        estimated_distance_m = self._depth_to_distance(relative_depth)

        # Generate proximity label
        proximity_label = self._depth_to_proximity_label(relative_depth)

        return {
            "estimated_distance_m": round(estimated_distance_m, 2),
            "relative_depth": round(relative_depth, 4),
            "proximity_label": proximity_label,
        }

    def _depth_to_distance(self, depth_value: float) -> float:
        """Convert normalized depth value to estimated distance in meters.

        This uses a simple heuristic mapping since monocular depth is relative.
        The scale is calibrated for typical home security camera scenarios.

        Args:
            depth_value: Normalized depth in [0, 1]

        Returns:
            Estimated distance in meters (approximate)
        """
        # Map depth 0-1 to distance range 0.5m - 15m
        min_distance = 0.5
        max_distance = 15.0

        # Exponential mapping: closer objects have more resolution
        distance = min_distance + (max_distance - min_distance) * (depth_value**0.7)
        return distance

    def _depth_to_proximity_label(self, depth_value: float) -> str:
        """Convert normalized depth value to human-readable proximity label.

        Args:
            depth_value: Normalized depth in [0, 1]

        Returns:
            Human-readable proximity label
        """
        if depth_value < 0.15:
            return "very close"
        elif depth_value < 0.35:
            return "close"
        elif depth_value < 0.55:
            return "moderate distance"
        elif depth_value < 0.75:
            return "far"
        else:
            return "very far"


# =============================================================================
# Pydantic Models for API
# =============================================================================


class BoundingBox(BaseModel):
    """Bounding box coordinates."""

    x1: float = Field(..., description="Left coordinate")
    y1: float = Field(..., description="Top coordinate")
    x2: float = Field(..., description="Right coordinate")
    y2: float = Field(..., description="Bottom coordinate")


class VehicleClassifyRequest(BaseModel):
    """Request format for vehicle classification endpoint."""

    image: str = Field(..., description="Base64 encoded image")
    bbox: list[float] | None = Field(
        default=None,
        description="Optional bounding box [x1, y1, x2, y2] to crop before classification",
    )


class VehicleClassifyResponse(BaseModel):
    """Response format for vehicle classification endpoint."""

    vehicle_type: str = Field(..., description="Classified vehicle type")
    display_name: str = Field(..., description="Human-readable vehicle type")
    confidence: float = Field(..., description="Classification confidence (0-1)")
    is_commercial: bool = Field(..., description="Whether vehicle is commercial/delivery type")
    all_scores: dict[str, float] = Field(..., description="Top classification scores")
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")


class PetClassifyRequest(BaseModel):
    """Request format for pet classification endpoint."""

    image: str = Field(..., description="Base64 encoded image")
    bbox: list[float] | None = Field(
        default=None,
        description="Optional bounding box [x1, y1, x2, y2] to crop before classification",
    )


class PetClassifyResponse(BaseModel):
    """Response format for pet classification endpoint."""

    pet_type: str = Field(..., description="Classified pet type (cat/dog)")
    breed: str = Field(..., description="Pet breed (if available)")
    confidence: float = Field(..., description="Classification confidence (0-1)")
    is_household_pet: bool = Field(..., description="Whether this is a household pet")
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")


class ClothingClassifyRequest(BaseModel):
    """Request format for clothing classification endpoint."""

    image: str = Field(..., description="Base64 encoded image")
    bbox: list[float] | None = Field(
        default=None,
        description="Optional bounding box [x1, y1, x2, y2] to crop before classification",
    )


class ClothingClassifyResponse(BaseModel):
    """Response format for clothing classification endpoint."""

    clothing_type: str = Field(..., description="Primary clothing type")
    color: str = Field(..., description="Primary color")
    style: str = Field(..., description="Overall style classification")
    confidence: float = Field(..., description="Classification confidence (0-1)")
    top_category: str = Field(..., description="Top matched category")
    description: str = Field(..., description="Human-readable description")
    is_suspicious: bool = Field(..., description="Whether clothing is potentially suspicious")
    is_service_uniform: bool = Field(..., description="Whether clothing is a service uniform")
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")


class DepthEstimateRequest(BaseModel):
    """Request format for depth estimation endpoint."""

    image: str = Field(..., description="Base64 encoded image")


class DepthEstimateResponse(BaseModel):
    """Response format for depth estimation endpoint."""

    depth_map_base64: str = Field(..., description="Base64 encoded PNG depth map visualization")
    min_depth: float = Field(..., description="Minimum depth value (normalized 0-1)")
    max_depth: float = Field(..., description="Maximum depth value (normalized 0-1)")
    mean_depth: float = Field(..., description="Mean depth value across the image")
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")


class ObjectDistanceRequest(BaseModel):
    """Request format for object distance estimation endpoint."""

    image: str = Field(..., description="Base64 encoded image")
    bbox: list[float] = Field(
        ...,
        description="Bounding box [x1, y1, x2, y2] of object to measure distance to",
        min_length=4,
        max_length=4,
    )
    method: str = Field(
        default="center",
        description="Depth sampling method: 'center', 'mean', 'median', or 'min'",
    )


class ObjectDistanceResponse(BaseModel):
    """Response format for object distance estimation endpoint."""

    estimated_distance_m: float = Field(
        ..., description="Estimated distance in meters (approximate, relative scale)"
    )
    relative_depth: float = Field(..., description="Normalized depth value (0=close, 1=far)")
    proximity_label: str = Field(..., description="Human-readable proximity description")
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")


class ModelStatus(BaseModel):
    """Status of a single model."""

    name: str
    loaded: bool
    vram_mb: float | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    models: list[ModelStatus]
    total_vram_used_gb: float | None = None
    device: str
    cuda_available: bool


class DetailedModelStatus(BaseModel):
    """Detailed status of a single model for /models/status endpoint."""

    name: str
    loaded: bool
    vram_mb: int
    priority: str
    last_used: str | None = None


class SystemStatus(BaseModel):
    """System status response for /models/status endpoint."""

    status: str  # "healthy", "degraded", "unhealthy"
    vram_total_mb: int
    vram_used_mb: int
    vram_available_mb: int
    vram_budget_mb: int
    loaded_models: list[DetailedModelStatus]
    pending_loads: list[str]
    uptime_seconds: float


class ReadinessResponse(BaseModel):
    """Readiness probe response."""

    ready: bool
    gpu_available: bool
    model_manager_initialized: bool


class ModelPreloadResponse(BaseModel):
    """Response for model preload endpoint."""

    status: str
    model: str
    message: str | None = None


class ModelUnloadResponse(BaseModel):
    """Response for model unload endpoint."""

    status: str
    model: str


class ModelRegistryEntry(BaseModel):
    """Single model entry in the registry."""

    name: str
    vram_mb: int
    priority: str
    loaded: bool


class ModelRegistryResponse(BaseModel):
    """Response for model registry endpoint."""

    models: list[ModelRegistryEntry]


# =============================================================================
# Unified Enrichment Endpoint Schemas
# =============================================================================


class EnrichmentRequest(BaseModel):
    """Request format for unified enrichment endpoint.

    This endpoint accepts detection context and returns all relevant enrichments
    by automatically selecting appropriate models based on detection type.
    """

    image: str = Field(..., description="Base64 encoded image")
    detection_type: str = Field(
        ...,
        description="Type of detection: 'person', 'vehicle', 'animal', or 'object'",
        json_schema_extra={"enum": ["person", "vehicle", "animal", "object"]},
    )
    bbox: BoundingBox = Field(..., description="Bounding box of the detection")
    frames: list[str] | None = Field(
        default=None,
        description="Optional list of base64 encoded frames for action recognition",
    )
    options: dict[str, bool] = Field(
        default_factory=dict,
        description="Additional options: action_recognition, include_depth, include_pose",
    )


class PoseResult(BaseModel):
    """Result from pose estimation."""

    keypoints: list[dict] = Field(..., description="List of keypoint dictionaries")
    posture: str = Field(..., description="Classified posture (standing, sitting, etc.)")
    alerts: list[str] = Field(
        default_factory=list,
        description="Security-relevant pose alerts",
    )


class ClothingResult(BaseModel):
    """Result from clothing classification."""

    clothing_type: str = Field(..., description="Primary clothing type")
    color: str = Field(..., description="Primary color")
    style: str = Field(..., description="Overall style classification")
    confidence: float = Field(..., description="Classification confidence (0-1)")
    top_category: str = Field(..., description="Top matched category")
    description: str = Field(..., description="Human-readable description")
    is_suspicious: bool = Field(..., description="Whether clothing is potentially suspicious")
    is_service_uniform: bool = Field(..., description="Whether clothing is a service uniform")


class DemographicsResult(BaseModel):
    """Result from demographics analysis (placeholder for future implementation)."""

    age_range: str = Field(default="unknown", description="Estimated age range")
    age_confidence: float = Field(default=0.0, description="Age estimation confidence")
    gender: str = Field(default="unknown", description="Estimated gender")
    gender_confidence: float = Field(default=0.0, description="Gender estimation confidence")


class VehicleEnrichmentResult(BaseModel):
    """Result from vehicle classification."""

    vehicle_type: str = Field(..., description="Classified vehicle type")
    display_name: str = Field(..., description="Human-readable vehicle type")
    color: str | None = Field(default=None, description="Vehicle color if detected")
    is_commercial: bool = Field(..., description="Whether vehicle is commercial/delivery type")
    confidence: float = Field(..., description="Classification confidence (0-1)")


class ThreatResult(BaseModel):
    """Result from threat detection (placeholder for future implementation)."""

    threats: list[dict] = Field(
        default_factory=list,
        description="List of detected threats with type, confidence, bbox, severity",
    )
    has_threat: bool = Field(default=False, description="Whether any threat was detected")


class DepthResult(BaseModel):
    """Result from depth estimation."""

    estimated_distance_m: float = Field(..., description="Estimated distance in meters")
    relative_depth: float = Field(..., description="Normalized depth value (0=close, 1=far)")
    proximity_label: str = Field(..., description="Human-readable proximity description")


class PetEnrichmentResult(BaseModel):
    """Result from pet classification."""

    pet_type: str = Field(..., description="Classified pet type (cat/dog)")
    breed: str = Field(default="unknown", description="Pet breed if detected")
    confidence: float = Field(..., description="Classification confidence (0-1)")
    is_household_pet: bool = Field(default=True, description="Whether this is a household pet")


class EnrichmentResponse(BaseModel):
    """Response format for unified enrichment endpoint.

    Contains all enrichment results based on detection type.
    Fields are optional and populated based on applicable models.
    """

    pose: PoseResult | None = Field(default=None, description="Pose estimation results")
    clothing: ClothingResult | None = Field(
        default=None, description="Clothing classification results"
    )
    demographics: DemographicsResult | None = Field(
        default=None, description="Demographics analysis results"
    )
    vehicle: VehicleEnrichmentResult | None = Field(
        default=None, description="Vehicle classification results"
    )
    pet: PetEnrichmentResult | None = Field(default=None, description="Pet classification results")
    threat: ThreatResult | None = Field(default=None, description="Threat detection results")
    reid_embedding: list[float] | None = Field(
        default=None, description="Re-identification embedding vector"
    )
    action: dict | None = Field(default=None, description="Action recognition results")
    depth: DepthResult | None = Field(default=None, description="Depth estimation results")
    models_used: list[str] = Field(
        default_factory=list, description="List of models that were executed"
    )
    inference_time_ms: float = Field(..., description="Total inference time in milliseconds")


# =============================================================================
# On-Demand Model Manager (replaces always-loaded global instances)
# =============================================================================

# Global model manager instance
model_manager: OnDemandModelManager | None = None

# Legacy global instances - kept for backward compatibility during transition
# These are now populated on-demand from the model manager
vehicle_classifier: VehicleClassifier | None = None
pet_classifier: PetClassifier | None = None
clothing_classifier: ClothingClassifier | None = None
depth_estimator: DepthEstimator | None = None

# Import PoseAnalyzer from vitpose module
try:
    from vitpose import PoseAnalyzer
except ImportError:
    # Fallback for different import contexts
    try:
        from ai.enrichment.vitpose import PoseAnalyzer
    except ImportError:
        PoseAnalyzer = None  # type: ignore[misc, assignment]
        logger.warning("PoseAnalyzer not available - pose estimation will be disabled")

pose_analyzer: PoseAnalyzer | None = None  # type: ignore[valid-type]


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


def get_vram_usage() -> float | None:
    """Get total VRAM usage in GB."""
    try:
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated() / (1024**3)
    except Exception as e:
        logger.warning(f"Failed to get VRAM usage: {e}")
    return None


def get_gpu_memory_info() -> tuple[int, int, int]:
    """Get GPU memory info in MB.

    Returns:
        Tuple of (total_mb, used_mb, available_mb).
        Returns (0, 0, 0) if CUDA is not available.
    """
    try:
        if torch.cuda.is_available():
            total = torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
            reserved = torch.cuda.memory_reserved(0) // (1024 * 1024)
            allocated = torch.cuda.memory_allocated(0) // (1024 * 1024)
            # Available is total minus reserved (reserved includes allocated + fragmented)
            available = total - reserved
            return total, allocated, available
    except Exception as e:
        logger.warning(f"Failed to get GPU memory info: {e}")
    return 0, 0, 0


def decode_and_crop_image(
    base64_image: str,
    bbox: list[float] | None = None,
) -> Image.Image:
    """Decode base64 image and optionally crop to bounding box.

    Args:
        base64_image: Base64 encoded image string
        bbox: Optional bounding box [x1, y1, x2, y2]

    Returns:
        PIL Image (cropped if bbox provided)

    Raises:
        ValueError: If base64 decoding fails or image is invalid
    """
    # Validate base64 string size
    if len(base64_image) > MAX_BASE64_SIZE_BYTES:
        raise ValueError(
            f"Base64 image size ({len(base64_image)} bytes) exceeds maximum "
            f"({MAX_BASE64_SIZE_BYTES} bytes)"
        )

    # Decode base64
    try:
        image_bytes = base64.b64decode(base64_image)
    except binascii.Error as e:
        raise ValueError(f"Invalid base64 encoding: {e}") from e

    # Validate decoded size
    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise ValueError(
            f"Decoded image size ({len(image_bytes)} bytes) exceeds maximum "
            f"({MAX_IMAGE_SIZE_BYTES} bytes)"
        )

    # Validate magic bytes before passing to PIL
    magic_valid, magic_result = validate_image_magic_bytes(image_bytes)
    if not magic_valid:
        logger.warning(f"Invalid image magic bytes: {magic_result}")
        raise ValueError(
            f"Invalid image data: {magic_result}. Supported formats: JPEG, PNG, GIF, BMP, WEBP."
        )

    # Open image with explicit error handling
    try:
        image = Image.open(io.BytesIO(image_bytes))
    except UnidentifiedImageError as e:
        logger.warning(f"PIL could not identify image: {e}")
        raise ValueError(
            "Invalid image data: Cannot identify image format. File may be corrupted or truncated."
        ) from e
    except OSError as e:
        logger.warning(f"PIL error loading image: {e}")
        raise ValueError(f"Corrupted image data: {e!s}") from e
    except Exception as e:
        logger.error(f"Unexpected error loading image: {e}", exc_info=True)
        raise ValueError(f"Invalid image data: {e}") from e

    # Convert to RGB if needed
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Crop if bbox provided
    if bbox and len(bbox) == 4:
        x1, y1, x2, y2 = bbox
        width, height = image.size

        # Clamp coordinates to image bounds
        x1 = max(0, int(x1))
        y1 = max(0, int(y1))
        x2 = min(width, int(x2))
        y2 = min(height, int(y2))

        if x2 > x1 and y2 > y1:
            image = image.crop((x1, y1, x2, y2))

    return image


# =============================================================================
# FastAPI Application
# =============================================================================


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Lifespan context manager for FastAPI app.

    This now uses on-demand model loading instead of loading all models at startup.
    Models are registered with the OnDemandModelManager and loaded when first requested.
    """
    global model_manager

    logger.info("Starting Combined Enrichment Service with on-demand model loading...")

    # Get configuration from environment
    vram_budget_gb = float(os.environ.get("VRAM_BUDGET_GB", "6.8"))
    device = "cuda:0" if torch.cuda.is_available() else "cpu"

    # Get model paths from environment
    vehicle_model_path = os.environ.get(
        "VEHICLE_MODEL_PATH", "/models/vehicle-segment-classification"
    )
    pet_model_path = os.environ.get("PET_MODEL_PATH", "/models/pet-classifier")
    clothing_model_path = os.environ.get("CLOTHING_MODEL_PATH", "/models/fashion-clip")
    depth_model_path = os.environ.get("DEPTH_MODEL_PATH", "/models/depth-anything-v2-small")
    pose_model_path = os.environ.get("POSE_MODEL_PATH", "/models/vitpose-plus-small")

    # Initialize the on-demand model manager
    model_manager = OnDemandModelManager(vram_budget_gb=vram_budget_gb)

    # Register all models (but don't load them yet)
    # Vehicle Classifier (~1.5GB)
    model_manager.register_model(
        ModelConfig(
            name="vehicle_classifier",
            vram_mb=1500,
            priority=ModelPriority.MEDIUM,
            loader_fn=lambda path=vehicle_model_path, dev=device: _create_and_load_model(
                VehicleClassifier, path, dev
            ),
            unloader_fn=_unload_model,
        )
    )

    # Pet Classifier (~200MB)
    model_manager.register_model(
        ModelConfig(
            name="pet_classifier",
            vram_mb=200,
            priority=ModelPriority.MEDIUM,
            loader_fn=lambda path=pet_model_path, dev=device: _create_and_load_model(
                PetClassifier, path, dev
            ),
            unloader_fn=_unload_model,
        )
    )

    # FashionSigLIP Clothing Classifier (~800MB) - 57% accuracy improvement over FashionCLIP
    model_manager.register_model(
        ModelConfig(
            name="fashion_clip",
            vram_mb=800,
            priority=ModelPriority.HIGH,
            loader_fn=lambda path=clothing_model_path, dev=device: _create_and_load_model(
                ClothingClassifier, path, dev
            ),
            unloader_fn=_unload_model,
        )
    )

    # Depth Estimator (~150MB)
    model_manager.register_model(
        ModelConfig(
            name="depth_estimator",
            vram_mb=150,
            priority=ModelPriority.LOW,
            loader_fn=lambda path=depth_model_path, dev=device: _create_and_load_model(
                DepthEstimator, path, dev
            ),
            unloader_fn=_unload_model,
        )
    )

    # Pose Analyzer (~300MB) - only if PoseAnalyzer is available
    if PoseAnalyzer is not None:
        model_manager.register_model(
            ModelConfig(
                name="pose_analyzer",
                vram_mb=300,
                priority=ModelPriority.HIGH,
                loader_fn=lambda path=pose_model_path, dev=device: _create_and_load_model(
                    PoseAnalyzer, path, dev
                ),
                unloader_fn=_unload_model,
            )
        )

    logger.info(
        f"OnDemandModelManager initialized with {vram_budget_gb}GB VRAM budget. "
        f"Registered {len(model_manager.model_registry)} models for on-demand loading."
    )

    # Preload specified models at startup (optional, for keeping models resident)
    # Set ENRICHMENT_PRELOAD_MODELS=vehicle_classifier,fashion_clip to preload
    preload_models = os.environ.get("ENRICHMENT_PRELOAD_MODELS", "").strip()
    if preload_models:
        model_names = [m.strip() for m in preload_models.split(",") if m.strip()]
        logger.info(f"Preloading {len(model_names)} models: {model_names}")
        for model_name in model_names:
            if model_name in model_manager.model_registry:
                try:
                    await model_manager.get_model(model_name)
                    logger.info(f"Preloaded model: {model_name}")
                except Exception as e:
                    logger.error(f"Failed to preload {model_name}: {e}")
            else:
                logger.warning(f"Unknown model for preload: {model_name}")

        # Log memory usage after preload
        if torch.cuda.is_available():
            mem_used = torch.cuda.memory_allocated() / 1e9
            logger.info(f"GPU memory after preload: {mem_used:.2f} GB")

    yield

    # Shutdown - unload all models
    logger.info("Shutting down Combined Enrichment Service...")

    if model_manager is not None:
        await model_manager.unload_all()

    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    logger.info("Shutdown complete")


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


# Create FastAPI app
app = FastAPI(
    title="Combined Enrichment Service",
    description="Detection enrichment service with vehicle, pet, clothing classification and depth estimation",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint with all model statuses.

    With on-demand loading, 'healthy' means the model manager is initialized
    and ready to load models. Individual model status shows which are currently loaded.
    """
    cuda_available = torch.cuda.is_available()
    device = "cuda:0" if cuda_available else "cpu"
    vram_used = get_vram_usage()

    # Build model status list from model manager
    models: list[ModelStatus] = []

    if model_manager is not None:
        # Model name to display name mapping
        display_names = {
            "vehicle_classifier": "vehicle-segment-classification",
            "pet_classifier": "pet-classifier",
            "fashion_clip": "fashion-clip",
            "depth_estimator": "depth-anything-v2-small",
            "pose_analyzer": "vitpose-plus-small",
        }

        for name, config in model_manager.model_registry.items():
            is_loaded = model_manager.is_loaded(name)
            models.append(
                ModelStatus(
                    name=display_names.get(name, name),
                    loaded=is_loaded,
                    vram_mb=config.vram_mb if is_loaded else None,
                )
            )

        # Status is healthy if manager is ready (models load on-demand)
        status = "healthy" if model_manager is not None else "unhealthy"
    else:
        status = "unhealthy"

    return HealthResponse(
        status=status,
        models=models,
        total_vram_used_gb=vram_used,
        device=device,
        cuda_available=cuda_available,
    )


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint.

    Returns metrics in Prometheus text format for scraping.
    Updates GPU metrics gauges before returning.

    Includes VRAM monitoring metrics (NEM-3149):
    - enrichment_vram_usage_bytes: Current VRAM usage by model manager
    - enrichment_vram_budget_bytes: Configured VRAM budget
    - enrichment_vram_utilization_percent: VRAM utilization percentage
    - enrichment_models_loaded: Number of currently loaded models
    - enrichment_model_evictions_total: Counter of model evictions by name/priority
    - enrichment_model_load_time_seconds: Histogram of model load times
    """
    # Update model status gauges from model manager
    if model_manager is not None:
        VEHICLE_MODEL_LOADED.set(1 if model_manager.is_loaded("vehicle_classifier") else 0)
        PET_MODEL_LOADED.set(1 if model_manager.is_loaded("pet_classifier") else 0)
        CLOTHING_MODEL_LOADED.set(1 if model_manager.is_loaded("fashion_clip") else 0)
        DEPTH_MODEL_LOADED.set(1 if model_manager.is_loaded("depth_estimator") else 0)
        POSE_MODEL_LOADED.set(1 if model_manager.is_loaded("pose_analyzer") else 0)

        # Update VRAM metrics to ensure they're current before serving
        # This calls _update_vram_metrics() which updates:
        # - enrichment_vram_usage_bytes
        # - enrichment_vram_utilization_percent
        # - enrichment_models_loaded
        model_manager._update_vram_metrics()
    else:
        VEHICLE_MODEL_LOADED.set(0)
        PET_MODEL_LOADED.set(0)
        CLOTHING_MODEL_LOADED.set(0)
        DEPTH_MODEL_LOADED.set(0)
        POSE_MODEL_LOADED.set(0)

    # Update GPU metrics gauges
    if torch.cuda.is_available():
        vram_used = get_vram_usage()
        if vram_used is not None:
            GPU_MEMORY_USED_GB.set(vram_used)

    return Response(content=generate_latest(), media_type="text/plain; charset=utf-8")


# =============================================================================
# Health Check and Status Endpoints (NEM-3046)
# =============================================================================


@app.get("/readiness", response_model=ReadinessResponse)
async def readiness_check() -> ReadinessResponse:
    """Readiness probe - check if service can handle requests.

    This endpoint is designed for Kubernetes readiness probes. It returns
    ready=True if the GPU is available and the model manager is initialized.
    """
    gpu_available = torch.cuda.is_available()
    manager_initialized = model_manager is not None

    return ReadinessResponse(
        ready=gpu_available and manager_initialized,
        gpu_available=gpu_available,
        model_manager_initialized=manager_initialized,
    )


@app.get("/models/status", response_model=SystemStatus)
async def get_model_status() -> SystemStatus:
    """Detailed status of all models and VRAM usage.

    Returns comprehensive information about:
    - Overall system health status
    - GPU VRAM usage (total, used, available)
    - List of loaded models with their VRAM usage and last access time
    - List of models currently being loaded
    - Service uptime
    """
    if model_manager is None:
        raise HTTPException(status_code=503, detail="Model manager not initialized")

    total, used, available = get_gpu_memory_info()

    loaded: list[DetailedModelStatus] = []
    for name, info in model_manager.loaded_models.items():
        loaded.append(
            DetailedModelStatus(
                name=name,
                loaded=True,
                vram_mb=info.vram_mb,
                priority=info.priority.name,
                last_used=info.last_used.isoformat() if info.last_used else None,
            )
        )

    # Determine overall status based on VRAM usage
    vram_usage_pct = used / total if total > 0 else 0
    if not torch.cuda.is_available():
        status = "unhealthy"
    elif vram_usage_pct > 0.95:
        status = "degraded"
    else:
        status = "healthy"

    uptime = (datetime.now(UTC) - SERVICE_START_TIME).total_seconds()

    return SystemStatus(
        status=status,
        vram_total_mb=total,
        vram_used_mb=used,
        vram_available_mb=available,
        vram_budget_mb=int(model_manager.vram_budget),
        loaded_models=loaded,
        pending_loads=list(model_manager.pending_loads),
        uptime_seconds=uptime,
    )


@app.post("/vehicle-classify", response_model=VehicleClassifyResponse)
async def vehicle_classify(request: VehicleClassifyRequest) -> VehicleClassifyResponse:
    """Classify vehicle type and attributes from an image.

    Input: Base64 encoded image with optional bounding box
    Output: Vehicle type, color, confidence, commercial status

    Model is loaded on-demand if not already in memory.
    """
    if model_manager is None:
        raise HTTPException(status_code=503, detail="Model manager not initialized")

    try:
        start_time = time.perf_counter()

        # Get model on-demand (loads if necessary)
        classifier = await model_manager.get_model("vehicle_classifier")

        # Decode and optionally crop image
        image = decode_and_crop_image(request.image, request.bbox)

        # Run classification
        result = classifier.classify(image)

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        # Record metrics
        INFERENCE_LATENCY_SECONDS.labels(endpoint="vehicle-classify").observe(
            inference_time_ms / 1000
        )
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="vehicle-classify", status="success").inc()

        return VehicleClassifyResponse(
            vehicle_type=result["vehicle_type"],
            display_name=result["display_name"],
            confidence=result["confidence"],
            is_commercial=result["is_commercial"],
            all_scores=result["all_scores"],
            inference_time_ms=round(inference_time_ms, 2),
        )

    except ValueError as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="vehicle-classify", status="error").inc()
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="vehicle-classify", status="error").inc()
        logger.error(f"Vehicle classification failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Classification failed: {e!s}") from e


@app.post("/pet-classify", response_model=PetClassifyResponse)
async def pet_classify(request: PetClassifyRequest) -> PetClassifyResponse:
    """Classify pet type (cat/dog) from an image.

    Input: Base64 encoded image with optional bounding box
    Output: Pet type, breed, confidence

    Model is loaded on-demand if not already in memory.
    """
    if model_manager is None:
        raise HTTPException(status_code=503, detail="Model manager not initialized")

    try:
        start_time = time.perf_counter()

        # Get model on-demand (loads if necessary)
        classifier = await model_manager.get_model("pet_classifier")

        # Decode and optionally crop image
        image = decode_and_crop_image(request.image, request.bbox)

        # Run classification
        result = classifier.classify(image)

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        # Record metrics
        INFERENCE_LATENCY_SECONDS.labels(endpoint="pet-classify").observe(inference_time_ms / 1000)
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="pet-classify", status="success").inc()

        return PetClassifyResponse(
            pet_type=result["pet_type"],
            breed=result["breed"],
            confidence=result["confidence"],
            is_household_pet=result["is_household_pet"],
            inference_time_ms=round(inference_time_ms, 2),
        )

    except ValueError as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="pet-classify", status="error").inc()
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="pet-classify", status="error").inc()
        logger.error(f"Pet classification failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Classification failed: {e!s}") from e


@app.post("/clothing-classify", response_model=ClothingClassifyResponse)
async def clothing_classify(request: ClothingClassifyRequest) -> ClothingClassifyResponse:
    """Classify clothing attributes from a person image using FashionSigLIP.

    Input: Base64 encoded image with optional bounding box
    Output: Clothing type, color, style, confidence, suspicious/service flags

    Model is loaded on-demand if not already in memory.
    """
    if model_manager is None:
        raise HTTPException(status_code=503, detail="Model manager not initialized")

    try:
        start_time = time.perf_counter()

        # Get model on-demand (loads if necessary)
        classifier = await model_manager.get_model("fashion_clip")

        # Decode and optionally crop image
        image = decode_and_crop_image(request.image, request.bbox)

        # Run classification
        result = classifier.classify(image)

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        # Record metrics
        INFERENCE_LATENCY_SECONDS.labels(endpoint="clothing-classify").observe(
            inference_time_ms / 1000
        )
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="clothing-classify", status="success").inc()

        return ClothingClassifyResponse(
            clothing_type=result["clothing_type"],
            color=result["color"],
            style=result["style"],
            confidence=result["confidence"],
            top_category=result["top_category"],
            description=result["description"],
            is_suspicious=result["is_suspicious"],
            is_service_uniform=result["is_service_uniform"],
            inference_time_ms=round(inference_time_ms, 2),
        )

    except ValueError as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="clothing-classify", status="error").inc()
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="clothing-classify", status="error").inc()
        logger.error(f"Clothing classification failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Classification failed: {e!s}") from e


@app.post("/depth-estimate", response_model=DepthEstimateResponse)
async def depth_estimate(request: DepthEstimateRequest) -> DepthEstimateResponse:
    """Estimate depth map for an image using Depth Anything V2.

    Input: Base64 encoded image
    Output: Depth map as base64 PNG, depth statistics

    Model is loaded on-demand if not already in memory.
    """
    if model_manager is None:
        raise HTTPException(status_code=503, detail="Model manager not initialized")

    try:
        start_time = time.perf_counter()

        # Get model on-demand (loads if necessary)
        estimator = await model_manager.get_model("depth_estimator")

        # Decode image
        image = decode_and_crop_image(request.image)

        # Run depth estimation
        result = estimator.estimate_depth(image)

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        # Record metrics
        INFERENCE_LATENCY_SECONDS.labels(endpoint="depth-estimate").observe(
            inference_time_ms / 1000
        )
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="depth-estimate", status="success").inc()

        return DepthEstimateResponse(
            depth_map_base64=result["depth_map_base64"],
            min_depth=result["min_depth"],
            max_depth=result["max_depth"],
            mean_depth=result["mean_depth"],
            inference_time_ms=round(inference_time_ms, 2),
        )

    except ValueError as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="depth-estimate", status="error").inc()
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="depth-estimate", status="error").inc()
        logger.error(f"Depth estimation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Depth estimation failed: {e!s}") from e


@app.post("/object-distance", response_model=ObjectDistanceResponse)
async def object_distance(request: ObjectDistanceRequest) -> ObjectDistanceResponse:
    """Estimate distance to an object within a bounding box.

    Input: Base64 encoded image, bounding box, optional sampling method
    Output: Estimated distance in meters, relative depth, proximity label

    Model is loaded on-demand if not already in memory.
    """
    if model_manager is None:
        raise HTTPException(status_code=503, detail="Model manager not initialized")

    # Validate method
    valid_methods = {"center", "mean", "median", "min"}
    if request.method not in valid_methods:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid method '{request.method}'. Must be one of: {valid_methods}",
        )

    try:
        start_time = time.perf_counter()

        # Get model on-demand (loads if necessary)
        estimator = await model_manager.get_model("depth_estimator")

        # Decode image
        image = decode_and_crop_image(request.image)

        # Run object distance estimation
        result = estimator.estimate_object_distance(
            image=image,
            bbox=request.bbox,
            method=request.method,
        )

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        # Record metrics
        INFERENCE_LATENCY_SECONDS.labels(endpoint="object-distance").observe(
            inference_time_ms / 1000
        )
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="object-distance", status="success").inc()

        return ObjectDistanceResponse(
            estimated_distance_m=result["estimated_distance_m"],
            relative_depth=result["relative_depth"],
            proximity_label=result["proximity_label"],
            inference_time_ms=round(inference_time_ms, 2),
        )

    except ValueError as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="object-distance", status="error").inc()
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="object-distance", status="error").inc()
        logger.error(f"Object distance estimation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Distance estimation failed: {e!s}") from e


# =============================================================================
# Unified Enrichment Endpoint
# =============================================================================


async def _run_pose_estimation(cropped_image: Image.Image) -> PoseResult | None:
    """Run pose estimation on a cropped person image.

    Uses on-demand model loading via the model manager.
    """
    if model_manager is None:
        return None

    try:
        analyzer = await model_manager.get_model("pose_analyzer")
        result = analyzer.analyze(cropped_image)
        return PoseResult(
            keypoints=result.get("keypoints", []),
            posture=result.get("posture", "unknown"),
            alerts=result.get("alerts", []),
        )
    except ValueError:
        # Model not registered (e.g., PoseAnalyzer not available)
        return None
    except Exception as e:
        logger.warning(f"Pose estimation failed: {e}")
        return None


async def _run_clothing_classification(cropped_image: Image.Image) -> ClothingResult | None:
    """Run clothing classification on a cropped person image.

    Uses on-demand model loading via the model manager.
    """
    if model_manager is None:
        return None

    try:
        classifier = await model_manager.get_model("fashion_clip")
        result = classifier.classify(cropped_image)
        return ClothingResult(
            clothing_type=result.get("clothing_type", "unknown"),
            color=result.get("color", "unknown"),
            style=result.get("style", "unknown"),
            confidence=result.get("confidence", 0.0),
            top_category=result.get("top_category", ""),
            description=result.get("description", ""),
            is_suspicious=result.get("is_suspicious", False),
            is_service_uniform=result.get("is_service_uniform", False),
        )
    except Exception as e:
        logger.warning(f"Clothing classification failed: {e}")
        return None


async def _run_vehicle_classification(cropped_image: Image.Image) -> VehicleEnrichmentResult | None:
    """Run vehicle classification on a cropped vehicle image.

    Uses on-demand model loading via the model manager.
    """
    if model_manager is None:
        return None

    try:
        classifier = await model_manager.get_model("vehicle_classifier")
        result = classifier.classify(cropped_image)
        return VehicleEnrichmentResult(
            vehicle_type=result.get("vehicle_type", "unknown"),
            display_name=result.get("display_name", "unknown"),
            color=None,  # Color detection not yet implemented
            is_commercial=result.get("is_commercial", False),
            confidence=result.get("confidence", 0.0),
        )
    except Exception as e:
        logger.warning(f"Vehicle classification failed: {e}")
        return None


async def _run_pet_classification(cropped_image: Image.Image) -> PetEnrichmentResult | None:
    """Run pet classification on a cropped animal image.

    Uses on-demand model loading via the model manager.
    """
    if model_manager is None:
        return None

    try:
        classifier = await model_manager.get_model("pet_classifier")
        result = classifier.classify(cropped_image)
        return PetEnrichmentResult(
            pet_type=result.get("pet_type", "unknown"),
            breed=result.get("breed", "unknown"),
            confidence=result.get("confidence", 0.0),
            is_household_pet=result.get("is_household_pet", True),
        )
    except Exception as e:
        logger.warning(f"Pet classification failed: {e}")
        return None


async def _run_depth_estimation(full_image: Image.Image, bbox: list[float]) -> DepthResult | None:
    """Run depth estimation for an object in the image.

    Uses on-demand model loading via the model manager.
    """
    if model_manager is None:
        return None

    try:
        estimator = await model_manager.get_model("depth_estimator")
        result = estimator.estimate_object_distance(full_image, bbox)
        return DepthResult(
            estimated_distance_m=result.get("estimated_distance_m", 0.0),
            relative_depth=result.get("relative_depth", 0.5),
            proximity_label=result.get("proximity_label", "unknown"),
        )
    except Exception as e:
        logger.warning(f"Depth estimation failed: {e}")
        return None


@app.post("/enrich", response_model=EnrichmentResponse)
async def enrich_detection(request: EnrichmentRequest) -> EnrichmentResponse:
    """Unified endpoint that runs appropriate models based on detection type.

    This endpoint accepts detection context and returns all relevant enrichments
    by automatically selecting appropriate models based on detection type.

    Detection types and their models:
    - person: pose, clothing, depth (threat and demographics are placeholders)
    - vehicle: vehicle classification, depth
    - animal: pet classification, depth
    - object: depth only

    Options:
    - include_depth: Run depth estimation (default: False for person, True for others)
    - include_pose: Run pose estimation for person (default: True)
    - action_recognition: Run action recognition if frames provided (not yet implemented)
    """
    start_time = time.perf_counter()

    try:
        # Decode full image
        full_image = decode_and_crop_image(request.image)

        # Extract bbox as list
        bbox_list = [request.bbox.x1, request.bbox.y1, request.bbox.x2, request.bbox.y2]

        # Crop to bounding box
        cropped_image = decode_and_crop_image(request.image, bbox_list)

        # Initialize response fields
        results: dict[str, Any] = {}
        models_used: list[str] = []

        # Determine which models to run based on detection type
        detection_type = request.detection_type.lower()

        if detection_type == "person":
            # Run person-relevant models in parallel
            tasks: list[tuple[str, Any]] = []

            # Pose estimation (default: on)
            if request.options.get("include_pose", True):
                tasks.append(("pose", _run_pose_estimation(cropped_image)))

            # Clothing analysis (always run for person)
            tasks.append(("clothing", _run_clothing_classification(cropped_image)))

            # Depth estimation (optional for person)
            if request.options.get("include_depth", False):
                tasks.append(("depth", _run_depth_estimation(full_image, bbox_list)))

            # Run all tasks in parallel
            if tasks:
                task_names = [t[0] for t in tasks]
                task_coros = [t[1] for t in tasks]
                task_results = await asyncio.gather(*task_coros, return_exceptions=True)

                for name, result in zip(task_names, task_results, strict=True):
                    if isinstance(result, Exception):
                        logger.warning(f"Task {name} failed with exception: {result}")
                    elif result is not None:
                        results[name] = result
                        models_used.append(name)
                        ENRICH_MODELS_USED.labels(model=name).inc()

        elif detection_type == "vehicle":
            # Run vehicle-relevant models
            tasks = [
                ("vehicle", _run_vehicle_classification(cropped_image)),
                ("depth", _run_depth_estimation(full_image, bbox_list)),
            ]

            task_names = [t[0] for t in tasks]
            task_coros = [t[1] for t in tasks]
            task_results = await asyncio.gather(*task_coros, return_exceptions=True)

            for name, result in zip(task_names, task_results, strict=True):
                if isinstance(result, Exception):
                    logger.warning(f"Task {name} failed with exception: {result}")
                elif result is not None:
                    results[name] = result
                    models_used.append(name)
                    ENRICH_MODELS_USED.labels(model=name).inc()

        elif detection_type == "animal":
            # Run animal-relevant models
            tasks = [
                ("pet", _run_pet_classification(cropped_image)),
                ("depth", _run_depth_estimation(full_image, bbox_list)),
            ]

            task_names = [t[0] for t in tasks]
            task_coros = [t[1] for t in tasks]
            task_results = await asyncio.gather(*task_coros, return_exceptions=True)

            for name, result in zip(task_names, task_results, strict=True):
                if isinstance(result, Exception):
                    logger.warning(f"Task {name} failed with exception: {result}")
                elif result is not None:
                    results[name] = result
                    models_used.append(name)
                    ENRICH_MODELS_USED.labels(model=name).inc()

        elif detection_type == "object":
            # For generic objects, only run depth estimation
            depth_result = await _run_depth_estimation(full_image, bbox_list)
            if depth_result is not None:
                results["depth"] = depth_result
                models_used.append("depth")
                ENRICH_MODELS_USED.labels(model="depth").inc()

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid detection_type: {detection_type}. "
                f"Must be one of: person, vehicle, animal, object",
            )

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        # Record metrics
        INFERENCE_LATENCY_SECONDS.labels(endpoint="enrich").observe(inference_time_ms / 1000)
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="enrich", status="success").inc()

        return EnrichmentResponse(
            pose=results.get("pose"),
            clothing=results.get("clothing"),
            demographics=results.get("demographics"),
            vehicle=results.get("vehicle"),
            pet=results.get("pet"),
            threat=results.get("threat"),
            reid_embedding=results.get("reid_embedding"),
            action=results.get("action"),
            depth=results.get("depth"),
            models_used=models_used,
            inference_time_ms=round(inference_time_ms, 2),
        )

    except ValueError as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="enrich", status="error").inc()
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="enrich", status="error").inc()
        raise
    except Exception as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="enrich", status="error").inc()
        logger.error(f"Unified enrichment failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {e!s}") from e


# =============================================================================
# Model Management Endpoints
# =============================================================================

# Track service start time for uptime calculation
_service_start_time: float = time.time()


@app.get("/models/status", response_model=SystemStatus)
async def get_models_status() -> SystemStatus:
    """Get detailed status of the model manager and all models.

    Returns comprehensive status including:
    - VRAM budget, usage, and availability
    - List of loaded models with details
    - Pending model loads
    - Service uptime
    """
    if model_manager is None:
        raise HTTPException(status_code=503, detail="Model manager not initialized")

    # Get VRAM info
    vram_total_mb = 0
    vram_used_mb = 0
    if torch.cuda.is_available():
        vram_total_mb = int(torch.cuda.get_device_properties(0).total_memory / (1024**2))
        vram_used_mb = int(torch.cuda.memory_allocated(0) / (1024**2))

    vram_budget_mb = int(model_manager.vram_budget)

    # Build loaded models list
    loaded_models: list[DetailedModelStatus] = []
    for name, info in model_manager.loaded_models.items():
        loaded_models.append(
            DetailedModelStatus(
                name=name,
                loaded=True,
                vram_mb=info.vram_mb,
                priority=info.priority.name,
                last_used=info.last_used.isoformat(),
            )
        )

    # Calculate uptime
    uptime_seconds = time.time() - _service_start_time

    # Determine overall status
    status = "healthy" if model_manager is not None else "unhealthy"

    return SystemStatus(
        status=status,
        vram_total_mb=vram_total_mb,
        vram_used_mb=vram_used_mb,
        vram_available_mb=vram_total_mb - vram_used_mb,
        vram_budget_mb=vram_budget_mb,
        loaded_models=loaded_models,
        pending_loads=list(model_manager.pending_loads),
        uptime_seconds=round(uptime_seconds, 2),
    )


@app.post("/models/preload", response_model=ModelPreloadResponse)
async def preload_model(model_name: str) -> ModelPreloadResponse:
    """Preload a model into VRAM for warming up.

    This endpoint allows manual preloading of models before they are needed
    for inference, reducing first-request latency.

    Args:
        model_name: Name of the model to preload (e.g., "vehicle_classifier",
                   "pet_classifier", "fashion_clip", "depth_estimator", "pose_analyzer")

    Returns:
        Status of the preload operation
    """
    if model_manager is None:
        raise HTTPException(status_code=503, detail="Model manager not initialized")

    # Validate model name
    if model_name not in model_manager.model_registry:
        available_models = list(model_manager.model_registry.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model: '{model_name}'. Available models: {available_models}",
        )

    try:
        # Check if already loaded
        if model_manager.is_loaded(model_name):
            return ModelPreloadResponse(
                status="already_loaded",
                model=model_name,
                message="Model is already loaded in VRAM",
            )

        # Load the model
        await model_manager.get_model(model_name)

        return ModelPreloadResponse(
            status="loaded",
            model=model_name,
            message=f"Model '{model_name}' successfully loaded",
        )

    except RuntimeError as e:
        # VRAM insufficient
        raise HTTPException(
            status_code=507,  # Insufficient Storage
            detail=f"Failed to preload model: {e!s}",
        ) from e
    except Exception as e:
        logger.error(f"Failed to preload model {model_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to preload model: {e!s}",
        ) from e


@app.post("/models/unload", response_model=ModelUnloadResponse)
async def unload_model(model_name: str) -> ModelUnloadResponse:
    """Explicitly unload a model from VRAM.

    This endpoint allows manual unloading of models to free VRAM.

    Args:
        model_name: Name of the model to unload

    Returns:
        Status of the unload operation
    """
    if model_manager is None:
        raise HTTPException(status_code=503, detail="Model manager not initialized")

    if model_name not in model_manager.model_registry:
        available_models = list(model_manager.model_registry.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model: '{model_name}'. Available models: {available_models}",
        )

    if not model_manager.is_loaded(model_name):
        return ModelUnloadResponse(
            status="not_loaded",
            model=model_name,
        )

    await model_manager.unload_model(model_name)

    return ModelUnloadResponse(
        status="unloaded",
        model=model_name,
    )


@app.get("/models/registry", response_model=ModelRegistryResponse)
async def get_model_registry() -> ModelRegistryResponse:
    """Get list of all registered models and their configurations.

    Returns all models that can be loaded on-demand, including their
    VRAM requirements and current load status.
    """
    if model_manager is None:
        raise HTTPException(status_code=503, detail="Model manager not initialized")

    models: list[ModelRegistryEntry] = []
    for name, config in model_manager.model_registry.items():
        models.append(
            ModelRegistryEntry(
                name=name,
                vram_mb=config.vram_mb,
                priority=config.priority.name,
                loaded=model_manager.is_loaded(name),
            )
        )

    return ModelRegistryResponse(models=models)


@app.get("/readiness", response_model=ReadinessResponse)
async def readiness_probe() -> ReadinessResponse:
    """Kubernetes readiness probe endpoint.

    Returns whether the service is ready to accept requests.
    With on-demand loading, ready means model manager is initialized.
    """
    gpu_available = torch.cuda.is_available()
    manager_initialized = model_manager is not None

    return ReadinessResponse(
        ready=manager_initialized,
        gpu_available=gpu_available,
        model_manager_initialized=manager_initialized,
    )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8094"))
    uvicorn.run(app, host=host, port=port, log_level="info")
