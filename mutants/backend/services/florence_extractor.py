"""Florence-2 based vision extraction for security camera analysis.

This module provides comprehensive attribute extraction from security camera feeds
using Florence-2-large vision-language model.

Extracts:
- Vehicle attributes: color, type, commercial status, company logos
- Person attributes: clothing, carrying items, actions
- Scene analysis: unusual objects, tools, abandoned items
- Environment context: time of day, artificial light, weather

Usage:
    extractor = FlorenceExtractor()

    async with model_manager.load("florence-2-large") as model:
        vehicle_attrs = await extractor.extract_vehicle_attributes(model, image, bbox)
        person_attrs = await extractor.extract_person_attributes(model, image, bbox)
        scene = await extractor.extract_scene_analysis(model, image)
        env = await extractor.extract_environment_context(model, image)
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)


# Florence-2 query templates for different extraction types
VEHICLE_QUERIES = {
    "caption": "<CAPTION>",
    "color": "What color is this vehicle?",
    "type": "What type of vehicle is this?",
    "commercial": "Is this a commercial vehicle?",
    "logo": "What company logo or text is visible?",
}

PERSON_QUERIES = {
    "caption": "<CAPTION>",
    "clothing": "What is this person wearing?",
    "carrying": "Is this person carrying anything?",
    "service_worker": "Does this person appear to be a delivery worker or service worker?",
    "action": "What is this person doing?",
}

SCENE_QUERIES = {
    "caption": "<CAPTION>",
    "unusual": "Are there any unusual objects in this scene?",
    "tools": "Are there any tools visible? (ladder, crowbar, bolt cutters, etc.)",
    "abandoned": "Are there any abandoned bags or packages?",
    "out_of_place": "Is there anything unusual or out of place in this scene?",
}

ENVIRONMENT_QUERIES = {
    "time_of_day": "What time of day does this appear to be based on lighting?",
    "artificial_light": "Is there a flashlight or artificial light source visible?",
    "weather": "What are the weather conditions?",
}


@dataclass
class VehicleAttributes:
    """Extracted attributes for a detected vehicle.

    Attributes:
        color: Vehicle color (e.g., "white", "red", "black")
        vehicle_type: Type of vehicle (e.g., "sedan", "SUV", "pickup", "van")
        is_commercial: Whether this appears to be a commercial vehicle
        commercial_text: Company name or logo text if visible
        caption: Full description from Florence-2
        confidence: Extraction confidence (0.0-1.0)
    """

    color: str | None = None
    vehicle_type: str | None = None
    is_commercial: bool = False
    commercial_text: str | None = None
    caption: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "color": self.color,
            "vehicle_type": self.vehicle_type,
            "is_commercial": self.is_commercial,
            "commercial_text": self.commercial_text,
            "caption": self.caption,
            "confidence": self.confidence,
        }

    def to_context_string(self) -> str:
        """Format attributes for LLM prompt context."""
        parts = []
        if self.color:
            parts.append(f"Color: {self.color}")
        if self.vehicle_type:
            parts.append(f"Type: {self.vehicle_type}")
        if self.is_commercial:
            parts.append("Commercial: Yes")
            if self.commercial_text:
                parts.append(f"Company: {self.commercial_text}")
        if self.caption and not parts:
            parts.append(self.caption)
        return ", ".join(parts) if parts else "No attributes extracted"


@dataclass
class PersonAttributes:
    """Extracted attributes for a detected person.

    Attributes:
        clothing: Description of clothing (e.g., "blue jacket, dark pants")
        carrying: What the person is carrying (e.g., "backpack", "package", "nothing")
        is_service_worker: Whether person appears to be a delivery/service worker
        action: Current action (e.g., "walking", "standing", "crouching")
        caption: Full description from Florence-2
        confidence: Extraction confidence (0.0-1.0)
    """

    clothing: str | None = None
    carrying: str | None = None
    is_service_worker: bool = False
    action: str | None = None
    caption: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "clothing": self.clothing,
            "carrying": self.carrying,
            "is_service_worker": self.is_service_worker,
            "action": self.action,
            "caption": self.caption,
            "confidence": self.confidence,
        }

    def to_context_string(self) -> str:
        """Format attributes for LLM prompt context."""
        parts = []
        if self.clothing:
            parts.append(f"Wearing: {self.clothing}")
        if self.carrying:
            parts.append(f"Carrying: {self.carrying}")
        if self.action:
            parts.append(f"Action: {self.action}")
        if self.is_service_worker:
            parts.append("Appears to be service worker")
        if self.caption and not parts:
            parts.append(self.caption)
        return ", ".join(parts) if parts else "No attributes extracted"


@dataclass
class SceneAnalysis:
    """Analysis of the overall scene in the image.

    Attributes:
        unusual_objects: List of unusual objects detected (e.g., ["ladder against fence"])
        tools_detected: List of tools visible (e.g., ["ladder", "crowbar"])
        abandoned_items: List of abandoned items (e.g., ["package near door"])
        scene_description: General scene description
        confidence: Analysis confidence (0.0-1.0)
    """

    unusual_objects: list[str] = field(default_factory=list)
    tools_detected: list[str] = field(default_factory=list)
    abandoned_items: list[str] = field(default_factory=list)
    scene_description: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "unusual_objects": self.unusual_objects,
            "tools_detected": self.tools_detected,
            "abandoned_items": self.abandoned_items,
            "scene_description": self.scene_description,
            "confidence": self.confidence,
        }

    def has_security_concerns(self) -> bool:
        """Check if scene analysis found any security concerns."""
        return bool(self.unusual_objects or self.tools_detected or self.abandoned_items)

    def to_context_string(self) -> str:
        """Format analysis for LLM prompt context."""
        parts = []
        if self.tools_detected:
            parts.append(f"Tools: {', '.join(self.tools_detected)}")
        if self.unusual_objects:
            parts.append(f"Unusual: {', '.join(self.unusual_objects)}")
        if self.abandoned_items:
            parts.append(f"Abandoned: {', '.join(self.abandoned_items)}")
        if self.scene_description and not parts:
            parts.append(self.scene_description)
        return "; ".join(parts) if parts else "No unusual elements detected"


@dataclass
class EnvironmentContext:
    """Environmental context extracted from the image.

    Attributes:
        time_of_day: Estimated time of day ("day", "dusk", "night")
        artificial_light: Whether artificial light (flashlight) is detected
        weather: Weather conditions if visible
        confidence: Extraction confidence (0.0-1.0)
    """

    time_of_day: str = "unknown"
    artificial_light: bool = False
    weather: str | None = None
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "time_of_day": self.time_of_day,
            "artificial_light": self.artificial_light,
            "weather": self.weather,
            "confidence": self.confidence,
        }

    def is_suspicious_lighting(self) -> bool:
        """Check for suspicious lighting conditions (night + artificial light)."""
        return self.time_of_day == "night" and self.artificial_light

    def to_context_string(self) -> str:
        """Format context for LLM prompt context."""
        parts = [f"Time: {self.time_of_day}"]
        if self.artificial_light:
            parts.append("Artificial light detected")
        if self.weather:
            parts.append(f"Weather: {self.weather}")
        return ", ".join(parts)


class FlorenceExtractor:
    """Extracts attributes from images using Florence-2 vision-language model.

    This class provides methods for extracting various types of information
    from security camera images including vehicle attributes, person attributes,
    scene analysis, and environmental context.

    The extractor uses Florence-2's visual question answering capabilities
    to parse images and extract structured information.

    Usage:
        extractor = FlorenceExtractor()

        async with model_manager.load("florence-2-large") as model:
            # model is a tuple of (model, processor)
            attrs = await extractor.extract_vehicle_attributes(model, image, bbox)
    """

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        """Initialize the Florence extractor.

        Args:
            timeout_seconds: Maximum time to wait for model inference
        """
        self.timeout_seconds = timeout_seconds
        logger.info("FlorenceExtractor initialized")

    async def _run_inference(
        self,
        model_tuple: tuple[Any, Any],
        image: Image.Image,
        prompt: str,
    ) -> str:
        """Run Florence-2 inference on an image with a prompt.

        Args:
            model_tuple: Tuple of (model, processor) from load_florence_model
            image: PIL Image to process
            prompt: Text prompt or task string

        Returns:
            Generated text response from the model

        Raises:
            RuntimeError: If inference fails or times out
        """
        model, processor = model_tuple

        try:
            import torch

            loop = asyncio.get_event_loop()

            def _inference() -> str:
                """Run inference synchronously."""
                # Determine device from model
                device = next(model.parameters()).device

                # Prepare inputs
                inputs = processor(
                    text=prompt,
                    images=image,
                    return_tensors="pt",
                )

                # Move to device
                inputs = {k: v.to(device) for k, v in inputs.items()}

                # Generate
                with torch.no_grad():
                    generated_ids = model.generate(
                        **inputs,
                        max_new_tokens=256,
                        num_beams=3,
                        do_sample=False,
                    )

                # Decode
                generated_text: str = processor.batch_decode(
                    generated_ids,
                    skip_special_tokens=True,
                )[0]

                return generated_text

            result = await asyncio.wait_for(
                loop.run_in_executor(None, _inference),
                timeout=self.timeout_seconds,
            )
            return result

        except TimeoutError:
            logger.error(f"Florence-2 inference timed out after {self.timeout_seconds}s")
            raise RuntimeError("Florence-2 inference timed out") from None
        except Exception as e:
            logger.error(f"Florence-2 inference failed: {e}")
            raise RuntimeError(f"Florence-2 inference failed: {e}") from e

    def _crop_bbox(
        self,
        image: Image.Image,
        bbox: tuple[int, int, int, int],
        padding: int = 10,
    ) -> Image.Image:
        """Crop image to bounding box with optional padding.

        Args:
            image: Source PIL Image
            bbox: Bounding box as (x1, y1, x2, y2)
            padding: Pixels to add around bbox

        Returns:
            Cropped PIL Image
        """
        x1, y1, x2, y2 = bbox
        width, height = image.size

        # Add padding and clamp to image bounds
        x1 = max(0, x1 - padding)
        y1 = max(0, y1 - padding)
        x2 = min(width, x2 + padding)
        y2 = min(height, y2 + padding)

        return image.crop((x1, y1, x2, y2))

    def _parse_yes_no(self, response: str) -> bool:
        """Parse a yes/no response from Florence-2.

        Args:
            response: Model response text

        Returns:
            True if response indicates yes, False otherwise
        """
        response_lower = response.lower().strip()
        yes_indicators = ["yes", "true", "appears to be", "looks like", "seems to be"]
        return any(ind in response_lower for ind in yes_indicators)

    def _parse_list_response(self, response: str) -> list[str]:
        """Parse a response that may contain multiple items.

        Args:
            response: Model response text

        Returns:
            List of extracted items
        """
        # Handle "no/none/nothing" responses
        if any(neg in response.lower() for neg in ["no ", "none", "nothing", "not visible"]):
            return []

        # Split on common delimiters
        items = re.split(r"[,;\n]", response)
        items = [item.strip() for item in items if item.strip()]

        # Filter out phrases that indicate absence
        items = [
            item
            for item in items
            if not any(neg in item.lower() for neg in ["no ", "none", "nothing"])
        ]

        return items

    def _extract_color(self, response: str) -> str | None:
        """Extract color from a response.

        Args:
            response: Model response text

        Returns:
            Color string or None
        """
        colors = [
            "white",
            "black",
            "red",
            "blue",
            "green",
            "yellow",
            "orange",
            "purple",
            "pink",
            "brown",
            "gray",
            "grey",
            "silver",
            "gold",
            "beige",
            "tan",
        ]
        response_lower = response.lower()
        for color in colors:
            if color in response_lower:
                return color
        # Return the full response if no standard color found
        return response.strip() if response.strip() else None

    def _extract_vehicle_type(self, response: str) -> str | None:
        """Extract vehicle type from a response.

        Args:
            response: Model response text

        Returns:
            Vehicle type string or None
        """
        # Order longer strings first to avoid substring matches (e.g., "minivan" before "van")
        types = [
            "minivan",
            "sedan",
            "suv",
            "pickup",
            "truck",
            "van",
            "coupe",
            "hatchback",
            "wagon",
            "convertible",
            "motorcycle",
            "bicycle",
            "bus",
        ]
        response_lower = response.lower()
        for vtype in types:
            if vtype in response_lower:
                return vtype
        return response.strip() if response.strip() else None

    def _extract_time_of_day(self, response: str) -> str:
        """Extract time of day from a response.

        Args:
            response: Model response text

        Returns:
            Time of day string ("day", "dusk", "dawn", "night", "unknown")
        """
        response_lower = response.lower()
        if any(t in response_lower for t in ["night", "dark", "nighttime"]):
            return "night"
        if any(t in response_lower for t in ["dusk", "evening", "sunset"]):
            return "dusk"
        if any(t in response_lower for t in ["dawn", "sunrise", "morning"]):
            return "dawn"
        if any(t in response_lower for t in ["day", "daytime", "afternoon", "midday", "bright"]):
            return "day"
        return "unknown"

    async def extract_vehicle_attributes(
        self,
        model_tuple: tuple[Any, Any],
        image: Image.Image,
        bbox: tuple[int, int, int, int],
    ) -> VehicleAttributes:
        """Extract attributes from a detected vehicle.

        Args:
            model_tuple: Tuple of (model, processor) from load_florence_model
            image: Full PIL Image containing the vehicle
            bbox: Bounding box of the vehicle as (x1, y1, x2, y2)

        Returns:
            VehicleAttributes with extracted information
        """
        logger.debug(f"Extracting vehicle attributes from bbox {bbox}")

        # Crop to vehicle region
        vehicle_crop = self._crop_bbox(image, bbox)

        attrs = VehicleAttributes()

        try:
            # Get caption first
            caption_response = await self._run_inference(
                model_tuple, vehicle_crop, VEHICLE_QUERIES["caption"]
            )
            attrs.caption = caption_response.strip()

            # Extract color
            color_response = await self._run_inference(
                model_tuple, vehicle_crop, VEHICLE_QUERIES["color"]
            )
            attrs.color = self._extract_color(color_response)

            # Extract type
            type_response = await self._run_inference(
                model_tuple, vehicle_crop, VEHICLE_QUERIES["type"]
            )
            attrs.vehicle_type = self._extract_vehicle_type(type_response)

            # Check if commercial
            commercial_response = await self._run_inference(
                model_tuple, vehicle_crop, VEHICLE_QUERIES["commercial"]
            )
            attrs.is_commercial = self._parse_yes_no(commercial_response)

            # Extract logo/company text if commercial
            if attrs.is_commercial:
                logo_response = await self._run_inference(
                    model_tuple, vehicle_crop, VEHICLE_QUERIES["logo"]
                )
                if not any(neg in logo_response.lower() for neg in ["no ", "none", "not visible"]):
                    attrs.commercial_text = logo_response.strip()

            attrs.confidence = 0.8  # Default confidence for successful extraction

            logger.debug(f"Vehicle attributes extracted: {attrs.to_dict()}")
            return attrs

        except Exception as e:
            logger.warning(f"Failed to extract vehicle attributes: {e}")
            attrs.confidence = 0.0
            return attrs

    async def extract_person_attributes(
        self,
        model_tuple: tuple[Any, Any],
        image: Image.Image,
        bbox: tuple[int, int, int, int],
    ) -> PersonAttributes:
        """Extract attributes from a detected person.

        Args:
            model_tuple: Tuple of (model, processor) from load_florence_model
            image: Full PIL Image containing the person
            bbox: Bounding box of the person as (x1, y1, x2, y2)

        Returns:
            PersonAttributes with extracted information
        """
        logger.debug(f"Extracting person attributes from bbox {bbox}")

        # Crop to person region
        person_crop = self._crop_bbox(image, bbox)

        attrs = PersonAttributes()

        try:
            # Get caption first
            caption_response = await self._run_inference(
                model_tuple, person_crop, PERSON_QUERIES["caption"]
            )
            attrs.caption = caption_response.strip()

            # Extract clothing
            clothing_response = await self._run_inference(
                model_tuple, person_crop, PERSON_QUERIES["clothing"]
            )
            if not any(neg in clothing_response.lower() for neg in ["cannot", "unable", "unclear"]):
                attrs.clothing = clothing_response.strip()

            # Extract what they're carrying
            carrying_response = await self._run_inference(
                model_tuple, person_crop, PERSON_QUERIES["carrying"]
            )
            if self._parse_yes_no(carrying_response):
                # Try to extract what they're carrying
                attrs.carrying = carrying_response.strip()
            else:
                attrs.carrying = "nothing"

            # Check if service worker
            service_response = await self._run_inference(
                model_tuple, person_crop, PERSON_QUERIES["service_worker"]
            )
            attrs.is_service_worker = self._parse_yes_no(service_response)

            # Extract action
            action_response = await self._run_inference(
                model_tuple, person_crop, PERSON_QUERIES["action"]
            )
            attrs.action = action_response.strip()

            attrs.confidence = 0.8  # Default confidence for successful extraction

            logger.debug(f"Person attributes extracted: {attrs.to_dict()}")
            return attrs

        except Exception as e:
            logger.warning(f"Failed to extract person attributes: {e}")
            attrs.confidence = 0.0
            return attrs

    async def extract_scene_analysis(
        self,
        model_tuple: tuple[Any, Any],
        image: Image.Image,
    ) -> SceneAnalysis:
        """Analyze the overall scene for security-relevant information.

        Args:
            model_tuple: Tuple of (model, processor) from load_florence_model
            image: Full PIL Image to analyze

        Returns:
            SceneAnalysis with detected objects and description
        """
        logger.debug("Extracting scene analysis")

        analysis = SceneAnalysis()

        try:
            # Get scene description
            caption_response = await self._run_inference(
                model_tuple, image, SCENE_QUERIES["caption"]
            )
            analysis.scene_description = caption_response.strip()

            # Check for tools
            tools_response = await self._run_inference(model_tuple, image, SCENE_QUERIES["tools"])
            if self._parse_yes_no(tools_response):
                analysis.tools_detected = self._parse_list_response(tools_response)

            # Check for abandoned items
            abandoned_response = await self._run_inference(
                model_tuple, image, SCENE_QUERIES["abandoned"]
            )
            if self._parse_yes_no(abandoned_response):
                analysis.abandoned_items = self._parse_list_response(abandoned_response)

            # Check for unusual objects
            unusual_response = await self._run_inference(
                model_tuple, image, SCENE_QUERIES["unusual"]
            )
            if self._parse_yes_no(unusual_response):
                analysis.unusual_objects = self._parse_list_response(unusual_response)

            analysis.confidence = 0.8  # Default confidence for successful extraction

            logger.debug(f"Scene analysis extracted: {analysis.to_dict()}")
            return analysis

        except Exception as e:
            logger.warning(f"Failed to extract scene analysis: {e}")
            analysis.confidence = 0.0
            return analysis

    async def extract_environment_context(
        self,
        model_tuple: tuple[Any, Any],
        image: Image.Image,
    ) -> EnvironmentContext:
        """Extract environmental context from the image.

        Args:
            model_tuple: Tuple of (model, processor) from load_florence_model
            image: Full PIL Image to analyze

        Returns:
            EnvironmentContext with lighting and weather information
        """
        logger.debug("Extracting environment context")

        context = EnvironmentContext()

        try:
            # Extract time of day
            time_response = await self._run_inference(
                model_tuple, image, ENVIRONMENT_QUERIES["time_of_day"]
            )
            context.time_of_day = self._extract_time_of_day(time_response)

            # Check for artificial light
            light_response = await self._run_inference(
                model_tuple, image, ENVIRONMENT_QUERIES["artificial_light"]
            )
            context.artificial_light = self._parse_yes_no(light_response)

            # Extract weather if visible
            weather_response = await self._run_inference(
                model_tuple, image, ENVIRONMENT_QUERIES["weather"]
            )
            if not any(
                neg in weather_response.lower() for neg in ["cannot", "unable", "unclear", "indoor"]
            ):
                context.weather = weather_response.strip()

            context.confidence = 0.8  # Default confidence for successful extraction

            logger.debug(f"Environment context extracted: {context.to_dict()}")
            return context

        except Exception as e:
            logger.warning(f"Failed to extract environment context: {e}")
            context.confidence = 0.0
            return context


# Global instance for convenience
_florence_extractor: FlorenceExtractor | None = None


def get_florence_extractor() -> FlorenceExtractor:
    """Get or create the global FlorenceExtractor instance.

    Returns:
        Global FlorenceExtractor instance
    """
    global _florence_extractor  # noqa: PLW0603
    if _florence_extractor is None:
        _florence_extractor = FlorenceExtractor()
    return _florence_extractor


def reset_florence_extractor() -> None:
    """Reset the global FlorenceExtractor instance (for testing)."""
    global _florence_extractor  # noqa: PLW0603
    _florence_extractor = None
