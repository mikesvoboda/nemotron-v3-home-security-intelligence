"""Demographics Estimator for Age and Gender Classification.

This module implements age and gender estimation from face crops using
ViT-based models. It's designed for on-demand loading to efficiently
manage VRAM in the ai-enrichment service.

Model Details:
- Age Model: nateraw/vit-age-classifier or similar ViT-based classifier
- Gender Model: Optional separate model or combined model
- Combined VRAM: ~500MB
- Priority: HIGH (important for person identification context)

Usage:
    estimator = DemographicsEstimator(
        age_model_path="/models/vit-age-classifier",
        gender_model_path="/models/vit-gender-classifier",  # Optional
    )
    estimator.load_model()
    result = estimator.estimate_demographics(face_image)
    print(f"Age: {result.age_range}, Gender: {result.gender}")

Privacy Note:
    Demographics are used for identification context only and should not
    be stored long-term. They help identify "expected" vs "unexpected"
    visitors in home security scenarios.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import torch
from PIL import Image

logger = logging.getLogger(__name__)


# Age range labels for classification output
# These represent discrete age buckets that the model predicts
AGE_RANGES: list[str] = [
    "0-10",  # Child
    "11-20",  # Teenager
    "21-35",  # Young adult
    "36-50",  # Adult
    "51-65",  # Middle-aged
    "65+",  # Senior
]

# Gender labels
GENDER_LABELS: list[str] = ["female", "male"]

# Default confidence thresholds for reliable predictions
DEFAULT_AGE_CONFIDENCE_THRESHOLD: float = 0.3
DEFAULT_GENDER_CONFIDENCE_THRESHOLD: float = 0.5


@dataclass
class DemographicsResult:
    """Result from demographics estimation.

    Attributes:
        age_range: Predicted age range (e.g., "21-35", "51-65")
        age_confidence: Confidence score for age prediction (0-1)
        gender: Predicted gender ("male", "female", or "unknown")
        gender_confidence: Confidence score for gender prediction (0-1)
    """

    age_range: str
    age_confidence: float
    gender: str  # "male", "female", "unknown"
    gender_confidence: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "age_range": self.age_range,
            "age_confidence": round(self.age_confidence, 4),
            "gender": self.gender,
            "gender_confidence": round(self.gender_confidence, 4),
        }


def validate_model_path(path: str) -> str:
    """Validate model path to prevent path traversal attacks.

    Args:
        path: The model path to validate (local path or HuggingFace ID)

    Returns:
        The validated path

    Raises:
        ValueError: If path contains traversal sequences
    """
    if ".." in path:
        logger.warning(f"Suspicious model path detected (traversal sequence): {path}")
        raise ValueError(f"Invalid model path: path traversal sequences not allowed: {path}")
    return path


class DemographicsEstimator:
    """ViT-based demographics estimation model wrapper.

    This class provides age and gender estimation from face crops using
    Vision Transformer (ViT) models. It supports both combined models
    (age + gender) and separate models for each task.

    The model is designed for on-demand loading to efficiently manage VRAM.
    When not in use, it can be unloaded to free GPU memory.

    Attributes:
        age_model_path: Path to age classification model
        gender_model_path: Optional path to gender classification model
        device: Device to run inference on (cuda:0, cpu, etc.)
        age_model: Loaded age model (None if not loaded)
        gender_model: Loaded gender model (None if not loaded)
    """

    def __init__(
        self,
        age_model_path: str,
        gender_model_path: str | None = None,
        device: str = "cuda:0",
    ):
        """Initialize demographics estimator.

        Args:
            age_model_path: Path to age classification model directory
                           or HuggingFace model ID (e.g., "nateraw/vit-age-classifier")
            gender_model_path: Optional path to separate gender model.
                              If None, gender will not be estimated or
                              a combined model may be used.
            device: Device to run inference on

        Raises:
            ValueError: If model paths contain path traversal sequences
        """
        self.age_model_path = validate_model_path(age_model_path)
        self.gender_model_path = (
            validate_model_path(gender_model_path) if gender_model_path else None
        )
        self.device = device

        # Model components (loaded on demand)
        self.age_model: Any = None
        self.age_processor: Any = None
        self.gender_model: Any = None
        self.gender_processor: Any = None

        # Model metadata
        self._age_labels: list[str] = []
        self._gender_labels: list[str] = []

        logger.info(
            f"Initialized DemographicsEstimator with age_model={self.age_model_path}, "
            f"gender_model={self.gender_model_path}, device={device}"
        )

    def load_model(self) -> DemographicsEstimator:
        """Load the age and gender models into memory.

        Returns:
            Self for method chaining

        Raises:
            Exception: If model loading fails
        """
        from transformers import AutoImageProcessor, ViTForImageClassification

        logger.info("Loading demographics models...")

        # Determine target device
        if "cuda" in self.device and torch.cuda.is_available():
            target_device = self.device
        else:
            target_device = "cpu"
            self.device = "cpu"
            logger.info("CUDA not available, using CPU")

        # Load age model
        logger.info(f"Loading age model from {self.age_model_path}")
        self.age_processor = AutoImageProcessor.from_pretrained(self.age_model_path)

        # Try to load with SDPA (Scaled Dot-Product Attention) for 15-40% faster inference
        # SDPA requires PyTorch 2.0+ and compatible hardware
        try:
            self.age_model = ViTForImageClassification.from_pretrained(
                self.age_model_path,
                attn_implementation="sdpa",
            )
            logger.info("Age model loaded with SDPA attention (optimized)")
        except (ValueError, ImportError) as e:
            # Fall back to default attention if SDPA is not supported
            logger.warning(f"SDPA not available for age model, falling back to default: {e}")
            self.age_model = ViTForImageClassification.from_pretrained(self.age_model_path)

        self.age_model.to(target_device)
        self.age_model.eval()

        # Extract age labels from model config
        if hasattr(self.age_model.config, "id2label"):
            self._age_labels = [
                self.age_model.config.id2label.get(str(i), f"age_{i}")
                for i in range(self.age_model.config.num_labels)
            ]
            logger.info(f"Age model labels: {self._age_labels}")
        else:
            self._age_labels = AGE_RANGES[: self.age_model.config.num_labels]
            logger.info(f"Using default age labels: {self._age_labels}")

        logger.info(f"Age model loaded on {target_device}")

        # Load gender model if specified
        if self.gender_model_path:
            logger.info(f"Loading gender model from {self.gender_model_path}")
            self.gender_processor = AutoImageProcessor.from_pretrained(self.gender_model_path)

            # Try to load with SDPA for gender model as well
            try:
                self.gender_model = ViTForImageClassification.from_pretrained(
                    self.gender_model_path,
                    attn_implementation="sdpa",
                )
                logger.info("Gender model loaded with SDPA attention (optimized)")
            except (ValueError, ImportError) as e:
                # Fall back to default attention if SDPA is not supported
                logger.warning(f"SDPA not available for gender model, falling back to default: {e}")
                self.gender_model = ViTForImageClassification.from_pretrained(
                    self.gender_model_path
                )

            self.gender_model.to(target_device)
            self.gender_model.eval()

            # Extract gender labels
            if hasattr(self.gender_model.config, "id2label"):
                self._gender_labels = [
                    self.gender_model.config.id2label.get(str(i), f"gender_{i}")
                    for i in range(self.gender_model.config.num_labels)
                ]
            else:
                self._gender_labels = GENDER_LABELS[: self.gender_model.config.num_labels]

            logger.info(f"Gender model loaded on {target_device}")

        logger.info("Demographics models loaded successfully")
        return self

    def unload(self) -> None:
        """Unload models from memory to free VRAM.

        Safe to call even if models are not loaded.
        """
        if self.age_model is not None:
            del self.age_model
            self.age_model = None
        if self.age_processor is not None:
            del self.age_processor
            self.age_processor = None
        if self.gender_model is not None:
            del self.gender_model
            self.gender_model = None
        if self.gender_processor is not None:
            del self.gender_processor
            self.gender_processor = None

        # Clear CUDA cache if available
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        logger.info("Demographics models unloaded")

    def estimate_demographics(
        self,
        face_image: Image.Image | Any,
    ) -> DemographicsResult:
        """Estimate age and gender from a face crop.

        Args:
            face_image: PIL Image of the face crop. Can also accept numpy array
                       which will be converted to PIL Image.

        Returns:
            DemographicsResult with age_range, age_confidence, gender, gender_confidence

        Raises:
            RuntimeError: If model is not loaded
        """
        if self.age_model is None or self.age_processor is None:
            raise RuntimeError("Age model not loaded. Call load_model() first.")

        # Convert numpy array to PIL Image if needed
        if not isinstance(face_image, Image.Image):
            import numpy as np

            if isinstance(face_image, np.ndarray):
                face_image = Image.fromarray(face_image)
            else:
                raise TypeError(f"Expected PIL.Image.Image or numpy array, got {type(face_image)}")

        # Ensure RGB mode
        if face_image.mode != "RGB":
            face_image = face_image.convert("RGB")

        # Estimate age
        age_range, age_confidence = self._estimate_age(face_image)

        # Estimate gender (if model is loaded)
        if self.gender_model is not None:
            gender, gender_confidence = self._estimate_gender(face_image)
        else:
            gender = "unknown"
            gender_confidence = 0.0

        return DemographicsResult(
            age_range=age_range,
            age_confidence=age_confidence,
            gender=gender,
            gender_confidence=gender_confidence,
        )

    def _estimate_age(self, face_image: Image.Image) -> tuple[str, float]:
        """Estimate age from a face image.

        Args:
            face_image: PIL Image of the face (RGB mode)

        Returns:
            Tuple of (age_range, confidence)
        """
        # Preprocess image
        inputs = self.age_processor(images=face_image, return_tensors="pt")

        # Move to device
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Run inference
        with torch.inference_mode():
            outputs = self.age_model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1)[0]

        # Get top prediction
        age_idx = int(probs.argmax().item())
        confidence = float(probs[age_idx].item())

        # Map to age range label
        if age_idx < len(self._age_labels):
            age_label = self._age_labels[age_idx]
            # Try to map model-specific labels to our standard age ranges
            age_range = self._normalize_age_label(age_label)
        else:
            age_range = "unknown"

        return age_range, confidence

    def _estimate_gender(self, face_image: Image.Image) -> tuple[str, float]:
        """Estimate gender from a face image.

        Args:
            face_image: PIL Image of the face (RGB mode)

        Returns:
            Tuple of (gender, confidence)
        """
        if self.gender_model is None or self.gender_processor is None:
            return "unknown", 0.0

        # Preprocess image
        inputs = self.gender_processor(images=face_image, return_tensors="pt")

        # Move to device
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Run inference
        with torch.inference_mode():
            outputs = self.gender_model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1)[0]

        # Get top prediction
        gender_idx = int(probs.argmax().item())
        confidence = float(probs[gender_idx].item())

        # Map to gender label
        if gender_idx < len(self._gender_labels):
            gender_label = self._gender_labels[gender_idx].lower()
            # Normalize gender label
            gender = self._normalize_gender_label(gender_label)
        else:
            gender = "unknown"

        return gender, confidence

    def _normalize_age_label(self, label: str) -> str:
        """Normalize model-specific age labels to standard age ranges.

        Different models may use different label formats:
        - nateraw/vit-age-classifier: "0-2", "3-9", "10-19", etc.
        - Other models: "child", "teenager", "adult", etc.

        This method maps them to our standard AGE_RANGES.

        Args:
            label: The raw label from the model

        Returns:
            Normalized age range from AGE_RANGES
        """
        label_lower = label.lower().strip()

        # Try exact match first
        if label_lower in [r.lower() for r in AGE_RANGES]:
            return label_lower

        # Map common age ranges from nateraw/vit-age-classifier
        # Model uses: 0-2, 3-9, 10-19, 20-29, 30-39, 40-49, 50-59, 60-69, 70+
        age_mappings = {
            # Direct numeric ranges
            "0-2": "0-10",
            "3-9": "0-10",
            "10-19": "11-20",
            "20-29": "21-35",
            "30-39": "21-35",
            "40-49": "36-50",
            "50-59": "51-65",
            "60-69": "51-65",
            "70+": "65+",
            "more than 70": "65+",
            # Semantic labels
            "baby": "0-10",
            "toddler": "0-10",
            "child": "0-10",
            "kid": "0-10",
            "teenager": "11-20",
            "teen": "11-20",
            "young_adult": "21-35",
            "young adult": "21-35",
            "adult": "36-50",
            "middle_aged": "51-65",
            "middle aged": "51-65",
            "senior": "65+",
            "elderly": "65+",
        }

        if label_lower in age_mappings:
            return age_mappings[label_lower]

        # Try to parse numeric patterns
        result = self._parse_numeric_age_label(label_lower)
        if result:
            return result

        # Fall back to unknown
        logger.warning(f"Could not map age label '{label}' to standard range")
        return "unknown"

    def _parse_numeric_age_label(self, label_lower: str) -> str | None:
        """Parse numeric age labels and map to standard ranges.

        Args:
            label_lower: Lowercase label string

        Returns:
            Mapped age range or None if not parseable
        """
        import re

        # Try to extract numeric range (e.g., "25-30")
        match = re.match(r"(\d+)[-_](\d+)", label_lower)
        if match:
            return self._map_start_age_to_range(int(match.group(1)))

        # Check for "70+" or similar patterns
        match = re.match(r"(\d+)\+", label_lower)
        if match and int(match.group(1)) >= 65:
            return "65+"

        return None

    def _map_start_age_to_range(self, start_age: int) -> str:
        """Map a starting age to a standard age range.

        Args:
            start_age: The starting age value

        Returns:
            Standard age range string
        """
        if start_age < 11:
            return "0-10"
        if start_age < 21:
            return "11-20"
        if start_age < 36:
            return "21-35"
        if start_age < 51:
            return "36-50"
        if start_age < 66:
            return "51-65"
        return "65+"

    def _normalize_gender_label(self, label: str) -> str:
        """Normalize model-specific gender labels to standard format.

        Args:
            label: The raw label from the model

        Returns:
            Normalized gender ("male", "female", or "unknown")
        """
        label_lower = label.lower().strip()

        # Map common variations
        male_labels = {"male", "man", "m", "boy"}
        female_labels = {"female", "woman", "f", "girl"}

        if label_lower in male_labels:
            return "male"
        elif label_lower in female_labels:
            return "female"
        else:
            return "unknown"

    @property
    def is_loaded(self) -> bool:
        """Check if the model is currently loaded."""
        return self.age_model is not None


def load_demographics(
    age_model_path: str,
    gender_model_path: str | None = None,
    device: str = "cuda:0",
) -> DemographicsEstimator:
    """Factory function for model registry integration.

    Creates and loads a DemographicsEstimator instance.

    Args:
        age_model_path: Path to age classification model
        gender_model_path: Optional path to gender classification model
        device: Device to run inference on

    Returns:
        Loaded DemographicsEstimator instance
    """
    estimator = DemographicsEstimator(
        age_model_path=age_model_path,
        gender_model_path=gender_model_path,
        device=device,
    )
    estimator.load_model()
    return estimator
