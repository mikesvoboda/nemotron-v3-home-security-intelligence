"""Combined Enrichment Service for Detection Classification.

HTTP server hosting multiple smaller classification models for enriching
RT-DETRv2 detections with additional attributes.

Models hosted:
1. Vehicle Segment Classification (~1.5GB) - ResNet-50 for vehicle type/color
2. Pet Classifier (~200MB) - ResNet-18 for dog/cat classification
3. FashionCLIP (~800MB) - Zero-shot clothing attribute extraction
4. Depth Anything V2 Small (~150MB) - Monocular depth estimation

Port: 8094 (configurable via PORT env var)
Expected VRAM: ~2.65GB total
"""

import base64
import binascii
import io
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import torch
from fastapi import FastAPI, HTTPException
from PIL import Image
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Size limits for image uploads (10MB is reasonable for security camera images)
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_BASE64_SIZE_BYTES = int(MAX_IMAGE_SIZE_BYTES * 4 / 3) + 100  # ~13.3MB + padding


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
# with FashionCLIP zero-shot color classification
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
        """
        self.model_path = model_path
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
        classes_file = model_dir / "classes.txt"
        if classes_file.exists():
            with open(classes_file) as f:
                self.classes = f.read().splitlines()
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
        with torch.no_grad():
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
        """
        self.model_path = model_path
        self.device = device
        self.model: Any = None
        self.processor: Any = None

        logger.info(f"Initializing PetClassifier from {self.model_path}")

    def load_model(self) -> None:
        """Load the ResNet-18 pet classifier model."""
        from transformers import AutoImageProcessor, AutoModelForImageClassification

        logger.info("Loading Pet Classifier model...")

        self.processor = AutoImageProcessor.from_pretrained(self.model_path)
        self.model = AutoModelForImageClassification.from_pretrained(self.model_path)

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
        with torch.no_grad():
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
# Clothing Classifier (FashionCLIP)
# =============================================================================

# Security-focused clothing classification prompts
SECURITY_CLOTHING_PROMPTS: list[str] = [
    # Potentially suspicious attire
    "person wearing dark hoodie",
    "person wearing face mask",
    "person wearing ski mask or balaclava",
    "person wearing gloves",
    "person wearing all black clothing",
    "person with obscured face",
    # Delivery and service uniforms
    "delivery uniform",
    "Amazon delivery vest",
    "FedEx uniform",
    "UPS uniform",
    "USPS postal worker uniform",
    "high-visibility vest or safety vest",
    "utility worker uniform",
    "maintenance worker clothing",
    # General clothing categories
    "casual clothing",
    "business attire or suit",
    "athletic wear or sportswear",
    "outdoor or hiking clothing",
    "winter coat or jacket",
    "rain jacket or raincoat",
]

# Suspicious clothing categories
SUSPICIOUS_CATEGORIES: frozenset[str] = frozenset(
    {
        "person wearing dark hoodie",
        "person wearing face mask",
        "person wearing ski mask or balaclava",
        "person wearing gloves",
        "person wearing all black clothing",
        "person with obscured face",
    }
)

# Service/uniform categories
SERVICE_CATEGORIES: frozenset[str] = frozenset(
    {
        "delivery uniform",
        "Amazon delivery vest",
        "FedEx uniform",
        "UPS uniform",
        "USPS postal worker uniform",
        "high-visibility vest or safety vest",
        "utility worker uniform",
        "maintenance worker clothing",
    }
)


class ClothingClassifier:
    """FashionCLIP zero-shot clothing classification model wrapper.

    Uses open_clip library directly instead of transformers.AutoModel because
    the Marqo-FashionCLIP custom model wrapper has meta tensor issues when
    loaded via transformers that cause "Cannot copy out of meta tensor" errors.
    """

    def __init__(self, model_path: str, device: str = "cuda:0"):
        """Initialize clothing classifier.

        Args:
            model_path: Path to FashionCLIP model directory or HuggingFace model ID
            device: Device to run inference on
        """
        self.model_path = model_path
        self.device = device
        self.model: Any = None
        self.preprocess: Any = None
        self.tokenizer: Any = None

        logger.info(f"Initializing ClothingClassifier from {self.model_path}")

    def load_model(self) -> None:
        """Load the FashionCLIP model using open_clip."""
        from open_clip import create_model_from_pretrained, get_tokenizer

        logger.info("Loading FashionCLIP model...")

        # Convert path to HuggingFace hub format if needed
        if self.model_path.startswith("/") or self.model_path.startswith("./"):
            # Local path - use hf-hub format with Marqo model
            hub_path = "hf-hub:Marqo/marqo-fashionCLIP"
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
        with torch.no_grad():
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
        """
        self.model_path = model_path
        self.device = device
        self.model: Any = None
        self.processor: Any = None

        logger.info(f"Initializing DepthEstimator from {self.model_path}")

    def load_model(self) -> None:
        """Load the Depth Anything V2 model."""
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation

        logger.info("Loading Depth Anything V2 model...")

        self.processor = AutoImageProcessor.from_pretrained(self.model_path)
        self.model = AutoModelForDepthEstimation.from_pretrained(self.model_path)

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
        with torch.no_grad():
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


# =============================================================================
# Global Model Instances
# =============================================================================

vehicle_classifier: VehicleClassifier | None = None
pet_classifier: PetClassifier | None = None
clothing_classifier: ClothingClassifier | None = None
depth_estimator: DepthEstimator | None = None


def get_vram_usage() -> float | None:
    """Get total VRAM usage in GB."""
    try:
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated() / (1024**3)
    except Exception as e:
        logger.warning(f"Failed to get VRAM usage: {e}")
    return None


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

    # Open image
    try:
        image = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
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
async def lifespan(_app: FastAPI):  # noqa: PLR0912
    """Lifespan context manager for FastAPI app."""
    global vehicle_classifier, pet_classifier, clothing_classifier, depth_estimator  # noqa: PLW0603

    logger.info("Starting Combined Enrichment Service...")

    # Get model paths from environment
    vehicle_model_path = os.environ.get(
        "VEHICLE_MODEL_PATH", "/models/vehicle-segment-classification"
    )
    pet_model_path = os.environ.get("PET_MODEL_PATH", "/models/pet-classifier")
    clothing_model_path = os.environ.get("CLOTHING_MODEL_PATH", "/models/fashion-clip")
    depth_model_path = os.environ.get("DEPTH_MODEL_PATH", "/models/depth-anything-v2-small")

    device = "cuda:0" if torch.cuda.is_available() else "cpu"

    # Load vehicle classifier
    try:
        vehicle_classifier = VehicleClassifier(
            model_path=vehicle_model_path,
            device=device,
        )
        vehicle_classifier.load_model()
        logger.info("Vehicle classifier loaded successfully")
    except FileNotFoundError:
        logger.warning(f"Vehicle model not found at {vehicle_model_path}")
    except Exception as e:
        logger.error(f"Failed to load vehicle classifier: {e}")

    # Load pet classifier
    try:
        pet_classifier = PetClassifier(
            model_path=pet_model_path,
            device=device,
        )
        pet_classifier.load_model()
        logger.info("Pet classifier loaded successfully")
    except FileNotFoundError:
        logger.warning(f"Pet model not found at {pet_model_path}")
    except Exception as e:
        logger.error(f"Failed to load pet classifier: {e}")

    # Load clothing classifier
    try:
        clothing_classifier = ClothingClassifier(
            model_path=clothing_model_path,
            device=device,
        )
        clothing_classifier.load_model()
        logger.info("Clothing classifier loaded successfully")
    except FileNotFoundError:
        logger.warning(f"Clothing model not found at {clothing_model_path}")
    except Exception as e:
        logger.error(f"Failed to load clothing classifier: {e}")

    # Load depth estimator
    try:
        depth_estimator = DepthEstimator(
            model_path=depth_model_path,
            device=device,
        )
        depth_estimator.load_model()
        logger.info("Depth estimator loaded successfully")
    except FileNotFoundError:
        logger.warning(f"Depth model not found at {depth_model_path}")
    except Exception as e:
        logger.error(f"Failed to load depth estimator: {e}")

    vram = get_vram_usage()
    logger.info(f"All models loaded. Total VRAM usage: {vram:.2f} GB" if vram else "VRAM: N/A")

    yield

    # Shutdown
    logger.info("Shutting down Combined Enrichment Service...")

    # Clean up models
    if vehicle_classifier and vehicle_classifier.model:
        del vehicle_classifier.model
    if pet_classifier and pet_classifier.model:
        del pet_classifier.model
    if clothing_classifier and clothing_classifier.model:
        del clothing_classifier.model
    if depth_estimator and depth_estimator.model:
        del depth_estimator.model

    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Combined Enrichment Service",
    description="Detection enrichment service with vehicle, pet, clothing classification and depth estimation",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint with all model statuses."""
    cuda_available = torch.cuda.is_available()
    device = "cuda:0" if cuda_available else "cpu"
    vram_used = get_vram_usage()

    models = [
        ModelStatus(
            name="vehicle-segment-classification",
            loaded=vehicle_classifier is not None and vehicle_classifier.model is not None,
            vram_mb=1500 if vehicle_classifier and vehicle_classifier.model else None,
        ),
        ModelStatus(
            name="pet-classifier",
            loaded=pet_classifier is not None and pet_classifier.model is not None,
            vram_mb=200 if pet_classifier and pet_classifier.model else None,
        ),
        ModelStatus(
            name="fashion-clip",
            loaded=clothing_classifier is not None and clothing_classifier.model is not None,
            vram_mb=800 if clothing_classifier and clothing_classifier.model else None,
        ),
        ModelStatus(
            name="depth-anything-v2-small",
            loaded=depth_estimator is not None and depth_estimator.model is not None,
            vram_mb=150 if depth_estimator and depth_estimator.model else None,
        ),
    ]

    all_loaded = all(m.loaded for m in models)
    any_loaded = any(m.loaded for m in models)

    status = "healthy" if all_loaded else ("degraded" if any_loaded else "unhealthy")

    return HealthResponse(
        status=status,
        models=models,
        total_vram_used_gb=vram_used,
        device=device,
        cuda_available=cuda_available,
    )


@app.post("/vehicle-classify", response_model=VehicleClassifyResponse)
async def vehicle_classify(request: VehicleClassifyRequest) -> VehicleClassifyResponse:
    """Classify vehicle type and attributes from an image.

    Input: Base64 encoded image with optional bounding box
    Output: Vehicle type, color, confidence, commercial status
    """
    if vehicle_classifier is None or vehicle_classifier.model is None:
        raise HTTPException(status_code=503, detail="Vehicle classifier not loaded")

    try:
        start_time = time.perf_counter()

        # Decode and optionally crop image
        image = decode_and_crop_image(request.image, request.bbox)

        # Run classification
        result = vehicle_classifier.classify(image)

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        return VehicleClassifyResponse(
            vehicle_type=result["vehicle_type"],
            display_name=result["display_name"],
            confidence=result["confidence"],
            is_commercial=result["is_commercial"],
            all_scores=result["all_scores"],
            inference_time_ms=round(inference_time_ms, 2),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Vehicle classification failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Classification failed: {e!s}") from e


@app.post("/pet-classify", response_model=PetClassifyResponse)
async def pet_classify(request: PetClassifyRequest) -> PetClassifyResponse:
    """Classify pet type (cat/dog) from an image.

    Input: Base64 encoded image with optional bounding box
    Output: Pet type, breed, confidence
    """
    if pet_classifier is None or pet_classifier.model is None:
        raise HTTPException(status_code=503, detail="Pet classifier not loaded")

    try:
        start_time = time.perf_counter()

        # Decode and optionally crop image
        image = decode_and_crop_image(request.image, request.bbox)

        # Run classification
        result = pet_classifier.classify(image)

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        return PetClassifyResponse(
            pet_type=result["pet_type"],
            breed=result["breed"],
            confidence=result["confidence"],
            is_household_pet=result["is_household_pet"],
            inference_time_ms=round(inference_time_ms, 2),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Pet classification failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Classification failed: {e!s}") from e


@app.post("/clothing-classify", response_model=ClothingClassifyResponse)
async def clothing_classify(request: ClothingClassifyRequest) -> ClothingClassifyResponse:
    """Classify clothing attributes from a person image using FashionCLIP.

    Input: Base64 encoded image with optional bounding box
    Output: Clothing type, color, style, confidence, suspicious/service flags
    """
    if clothing_classifier is None or clothing_classifier.model is None:
        raise HTTPException(status_code=503, detail="Clothing classifier not loaded")

    try:
        start_time = time.perf_counter()

        # Decode and optionally crop image
        image = decode_and_crop_image(request.image, request.bbox)

        # Run classification
        result = clothing_classifier.classify(image)

        inference_time_ms = (time.perf_counter() - start_time) * 1000

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
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Clothing classification failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Classification failed: {e!s}") from e


@app.post("/depth-estimate", response_model=DepthEstimateResponse)
async def depth_estimate(request: DepthEstimateRequest) -> DepthEstimateResponse:
    """Estimate depth map for an image using Depth Anything V2.

    Input: Base64 encoded image
    Output: Depth map as base64 PNG, depth statistics
    """
    if depth_estimator is None or depth_estimator.model is None:
        raise HTTPException(status_code=503, detail="Depth estimator not loaded")

    try:
        start_time = time.perf_counter()

        # Decode image
        image = decode_and_crop_image(request.image)

        # Run depth estimation
        result = depth_estimator.estimate_depth(image)

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        return DepthEstimateResponse(
            depth_map_base64=result["depth_map_base64"],
            min_depth=result["min_depth"],
            max_depth=result["max_depth"],
            mean_depth=result["mean_depth"],
            inference_time_ms=round(inference_time_ms, 2),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Depth estimation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Depth estimation failed: {e!s}") from e


@app.post("/object-distance", response_model=ObjectDistanceResponse)
async def object_distance(request: ObjectDistanceRequest) -> ObjectDistanceResponse:
    """Estimate distance to an object within a bounding box.

    Input: Base64 encoded image, bounding box, optional sampling method
    Output: Estimated distance in meters, relative depth, proximity label
    """
    if depth_estimator is None or depth_estimator.model is None:
        raise HTTPException(status_code=503, detail="Depth estimator not loaded")

    # Validate method
    valid_methods = {"center", "mean", "median", "min"}
    if request.method not in valid_methods:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid method '{request.method}'. Must be one of: {valid_methods}",
        )

    try:
        start_time = time.perf_counter()

        # Decode image
        image = decode_and_crop_image(request.image)

        # Run object distance estimation
        result = depth_estimator.estimate_object_distance(
            image=image,
            bbox=request.bbox,
            method=request.method,
        )

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        return ObjectDistanceResponse(
            estimated_distance_m=result["estimated_distance_m"],
            relative_depth=result["relative_depth"],
            proximity_label=result["proximity_label"],
            inference_time_ms=round(inference_time_ms, 2),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Object distance estimation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Distance estimation failed: {e!s}") from e


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")  # noqa: S104
    port = int(os.getenv("PORT", "8094"))
    uvicorn.run(app, host=host, port=port, log_level="info")
