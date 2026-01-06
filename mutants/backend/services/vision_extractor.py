"""Vision extraction service using Florence-2 for attribute extraction.

This module provides comprehensive attribute extraction from security camera feeds
using Florence-2, a vision-language model that supports:
- Vehicle attributes (color, type, commercial status, logos)
- Person attributes (clothing, carried items, actions)
- Scene analysis (unusual objects, tools, abandoned items)
- Environment context (time of day, lighting, weather)

The VisionExtractor calls the ai-florence HTTP service for Florence-2 inference,
which runs as a dedicated service at http://ai-florence:8092. This architecture
improves VRAM management by keeping Florence-2 in a separate container.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger
from backend.services.florence_client import FlorenceUnavailableError, get_florence_client

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)

# Florence-2 task prompts
CAPTION_TASK = "<CAPTION>"
DETAILED_CAPTION_TASK = "<DETAILED_CAPTION>"
MORE_DETAILED_CAPTION_TASK = "<MORE_DETAILED_CAPTION>"
VQA_TASK = "<VQA>"


@dataclass(frozen=True, slots=True)
class VehicleAttributes:
    """Extracted attributes for a detected vehicle.

    Attributes:
        color: Vehicle color (e.g., "white", "red", "black")
        vehicle_type: Type of vehicle (e.g., "sedan", "SUV", "pickup", "van")
        is_commercial: Whether this appears to be a commercial vehicle
        commercial_text: Visible company name/logo text if commercial
        caption: Full description of the vehicle
    """

    color: str | None
    vehicle_type: str | None
    is_commercial: bool
    commercial_text: str | None
    caption: str


@dataclass(frozen=True, slots=True)
class PersonAttributes:
    """Extracted attributes for a detected person.

    Attributes:
        clothing: Description of clothing (e.g., "blue jacket, dark pants")
        carrying: What the person is carrying (e.g., "backpack", "package", "nothing")
        is_service_worker: Whether this appears to be a delivery/service worker
        action: Current action (e.g., "walking", "standing", "crouching")
        caption: Full description of the person
    """

    clothing: str | None
    carrying: str | None
    is_service_worker: bool
    action: str | None
    caption: str


@dataclass(slots=True)
class SceneAnalysis:
    """Analysis of the scene for unusual elements.

    Attributes:
        unusual_objects: List of unusual objects detected
        tools_detected: List of tools visible (ladder, crowbar, etc.)
        abandoned_items: List of abandoned bags/packages
        scene_description: General description of the scene
    """

    unusual_objects: list[str] = field(default_factory=list)
    tools_detected: list[str] = field(default_factory=list)
    abandoned_items: list[str] = field(default_factory=list)
    scene_description: str = ""


@dataclass(slots=True)
class BatchExtractionResult:
    """Result of batch attribute extraction.

    Attributes:
        vehicle_attributes: Dict mapping detection_id to VehicleAttributes
        person_attributes: Dict mapping detection_id to PersonAttributes
        scene_analysis: Scene analysis for the full frame
        environment_context: Environment context for the full frame
    """

    vehicle_attributes: dict[str, VehicleAttributes] = field(default_factory=dict)
    person_attributes: dict[str, PersonAttributes] = field(default_factory=dict)
    scene_analysis: SceneAnalysis | None = None
    environment_context: EnvironmentContext | None = None


# Vehicle classes from COCO that should trigger vehicle attribute extraction
VEHICLE_CLASSES = frozenset(
    {
        "car",
        "truck",
        "bus",
        "motorcycle",
        "bicycle",
        "vehicle",
    }
)

# Person class
PERSON_CLASS = "person"


@dataclass(frozen=True, slots=True)
class EnvironmentContext:
    """Environmental context from the scene.

    Attributes:
        time_of_day: Estimated time of day ("day", "dusk", "night")
        artificial_light: Whether artificial light source is visible
        weather: Weather conditions if visible
    """

    time_of_day: str
    artificial_light: bool
    weather: str | None


# Query templates for Florence-2
VEHICLE_QUERIES = {
    "color": "What color is this vehicle?",
    "type": "What type of vehicle is this? (sedan, SUV, pickup, van, truck, motorcycle)",
    "commercial": "Is this a commercial vehicle? Answer yes or no.",
    "commercial_text": "What company logo or text is visible on this vehicle?",
}

PERSON_QUERIES = {
    "clothing": "What is this person wearing?",
    "carrying": "Is this person carrying anything? If yes, what?",
    "service_worker": "Does this person appear to be a delivery worker or service worker? Answer yes or no.",
    "action": "What is this person doing?",
}

SCENE_QUERIES = {
    "unusual": "Are there any unusual objects in this scene?",
    "tools": "Are there any tools visible? (ladder, crowbar, bolt cutters, etc.)",
    "abandoned": "Are there any abandoned bags or packages?",
}

ENVIRONMENT_QUERIES = {
    "time_of_day": "What time of day does this appear to be based on lighting? (day, dusk, night)",
    "artificial_light": "Is there a flashlight or artificial light source visible? Answer yes or no.",
    "weather": "What are the weather conditions?",
}


class VisionExtractor:
    """Service for extracting visual attributes using Florence-2.

    This service calls the ai-florence HTTP service for Florence-2 inference
    and provides methods for extracting vehicle attributes, person attributes,
    and scene analysis from cropped detection images.

    The ai-florence service runs Florence-2 as a dedicated container, which
    improves VRAM management by keeping the model separate from the backend.

    Usage:
        extractor = VisionExtractor()

        # Extract vehicle attributes
        vehicle = await extractor.extract_vehicle_attributes(
            full_image, bbox=(100, 100, 300, 300)
        )

        # Extract person attributes
        person = await extractor.extract_person_attributes(
            full_image, bbox=(50, 50, 150, 400)
        )

        # Analyze scene
        scene = await extractor.extract_scene_analysis(full_image)
    """

    def __init__(self) -> None:
        """Initialize the VisionExtractor."""
        self._florence_client = get_florence_client()
        logger.info("VisionExtractor initialized with Florence HTTP client")

    async def _query_florence(
        self,
        image: Image.Image,
        task: str,
        text_input: str = "",
    ) -> str:
        """Run a query on Florence-2 via the HTTP service.

        Args:
            image: PIL Image to analyze
            task: Florence-2 task prompt (e.g., "<CAPTION>", "<VQA>")
            text_input: Additional text input for VQA tasks

        Returns:
            Model response as string, or empty string on error
        """
        # Construct the prompt
        prompt = f"{task}{text_input}" if task == VQA_TASK and text_input else task

        try:
            result = await self._florence_client.extract(image, prompt)
            return result
        except FlorenceUnavailableError as e:
            logger.warning(f"Florence service unavailable: {e}")
            return ""

    def _crop_image(self, image: Image.Image, bbox: tuple[int, int, int, int]) -> Image.Image:
        """Crop image to bounding box with padding.

        Args:
            image: Full PIL Image
            bbox: Bounding box as (x1, y1, x2, y2)

        Returns:
            Cropped PIL Image with 10% padding
        """
        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1

        # Add 10% padding
        pad_x = int(width * 0.1)
        pad_y = int(height * 0.1)

        # Clamp to image bounds
        img_width, img_height = image.size
        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(img_width, x2 + pad_x)
        y2 = min(img_height, y2 + pad_y)

        return image.crop((x1, y1, x2, y2))

    def _parse_yes_no(self, response: str) -> bool:
        """Parse a yes/no response from Florence-2.

        Args:
            response: Model response text

        Returns:
            True if response indicates yes, False otherwise
        """
        response_lower = response.lower().strip()
        return response_lower.startswith("yes") or "yes" in response_lower[:20]

    def _parse_none_response(self, response: str) -> str | None:
        """Parse response that might indicate nothing/none.

        Args:
            response: Model response text

        Returns:
            Response text or None if indicating nothing
        """
        response_lower = response.lower().strip()
        nothing_indicators = [
            "nothing",
            "none",
            "no ",
            "not carrying",
            "empty",
            "n/a",
            "not visible",
            "cannot see",
            "can't see",
        ]
        for indicator in nothing_indicators:
            if response_lower.startswith(indicator):
                return None
        return response.strip() if response.strip() else None

    async def extract_vehicle_attributes(
        self,
        image: Image.Image,
        bbox: tuple[int, int, int, int] | None = None,
    ) -> VehicleAttributes:
        """Extract attributes from a detected vehicle.

        Args:
            image: Full frame or cropped vehicle image
            bbox: Optional bounding box to crop (x1, y1, x2, y2)

        Returns:
            VehicleAttributes with extracted information
        """
        if bbox is not None:
            image = self._crop_image(image, bbox)

        # Get caption first
        caption = await self._query_florence(image, CAPTION_TASK)

        # Query for specific attributes
        color = await self._query_florence(image, VQA_TASK, VEHICLE_QUERIES["color"])
        vehicle_type = await self._query_florence(image, VQA_TASK, VEHICLE_QUERIES["type"])
        commercial_response = await self._query_florence(
            image, VQA_TASK, VEHICLE_QUERIES["commercial"]
        )

        is_commercial = self._parse_yes_no(commercial_response)

        commercial_text = None
        if is_commercial:
            commercial_text = await self._query_florence(
                image, VQA_TASK, VEHICLE_QUERIES["commercial_text"]
            )
            commercial_text = self._parse_none_response(commercial_text)

        return VehicleAttributes(
            color=color.strip() if color else None,
            vehicle_type=vehicle_type.strip() if vehicle_type else None,
            is_commercial=is_commercial,
            commercial_text=commercial_text,
            caption=caption,
        )

    async def extract_person_attributes(
        self,
        image: Image.Image,
        bbox: tuple[int, int, int, int] | None = None,
    ) -> PersonAttributes:
        """Extract attributes from a detected person.

        Args:
            image: Full frame or cropped person image
            bbox: Optional bounding box to crop (x1, y1, x2, y2)

        Returns:
            PersonAttributes with extracted information
        """
        if bbox is not None:
            image = self._crop_image(image, bbox)

        # Get caption first
        caption = await self._query_florence(image, CAPTION_TASK)

        # Query for specific attributes
        clothing = await self._query_florence(image, VQA_TASK, PERSON_QUERIES["clothing"])
        carrying_response = await self._query_florence(image, VQA_TASK, PERSON_QUERIES["carrying"])
        service_response = await self._query_florence(
            image, VQA_TASK, PERSON_QUERIES["service_worker"]
        )
        action = await self._query_florence(image, VQA_TASK, PERSON_QUERIES["action"])

        return PersonAttributes(
            clothing=clothing.strip() if clothing else None,
            carrying=self._parse_none_response(carrying_response),
            is_service_worker=self._parse_yes_no(service_response),
            action=action.strip() if action else None,
            caption=caption,
        )

    async def extract_scene_analysis(
        self,
        image: Image.Image,
    ) -> SceneAnalysis:
        """Analyze the full scene for unusual elements.

        Args:
            image: Full frame image

        Returns:
            SceneAnalysis with detected unusual elements
        """
        # Get scene description
        description = await self._query_florence(image, CAPTION_TASK)

        # Query for unusual elements
        unusual_response = await self._query_florence(image, VQA_TASK, SCENE_QUERIES["unusual"])
        tools_response = await self._query_florence(image, VQA_TASK, SCENE_QUERIES["tools"])
        abandoned_response = await self._query_florence(image, VQA_TASK, SCENE_QUERIES["abandoned"])

        # Parse responses into lists
        unusual_objects: list[str] = []
        if unusual_response and not self._is_negative_response(unusual_response):
            unusual_objects = [unusual_response.strip()]

        tools_detected: list[str] = []
        if tools_response and not self._is_negative_response(tools_response):
            # Parse comma-separated tools
            tools_detected = [t.strip() for t in tools_response.split(",") if t.strip()]

        abandoned_items: list[str] = []
        if abandoned_response and not self._is_negative_response(abandoned_response):
            abandoned_items = [abandoned_response.strip()]

        return SceneAnalysis(
            unusual_objects=unusual_objects,
            tools_detected=tools_detected,
            abandoned_items=abandoned_items,
            scene_description=description,
        )

    async def extract_environment_context(
        self,
        image: Image.Image,
    ) -> EnvironmentContext:
        """Extract environmental context from the scene.

        Args:
            image: Full frame image

        Returns:
            EnvironmentContext with time, lighting, and weather info
        """
        time_response = await self._query_florence(
            image, VQA_TASK, ENVIRONMENT_QUERIES["time_of_day"]
        )
        light_response = await self._query_florence(
            image, VQA_TASK, ENVIRONMENT_QUERIES["artificial_light"]
        )
        weather_response = await self._query_florence(
            image, VQA_TASK, ENVIRONMENT_QUERIES["weather"]
        )

        # Parse time of day
        time_lower = time_response.lower() if time_response else ""
        if "night" in time_lower:
            time_of_day = "night"
        elif "dusk" in time_lower or "dawn" in time_lower or "evening" in time_lower:
            time_of_day = "dusk"
        else:
            time_of_day = "day"

        return EnvironmentContext(
            time_of_day=time_of_day,
            artificial_light=self._parse_yes_no(light_response),
            weather=self._parse_none_response(weather_response),
        )

    def _is_negative_response(self, response: str) -> bool:
        """Check if response indicates nothing/no/none.

        Args:
            response: Model response text

        Returns:
            True if response is negative
        """
        response_lower = response.lower().strip()
        negative_indicators = [
            "no ",
            "no,",
            "no.",
            "none",
            "nothing",
            "not ",
            "cannot",
            "can't",
            "don't see",
            "do not see",
            "isn't",
            "aren't",
        ]
        return any(response_lower.startswith(indicator) for indicator in negative_indicators)

    async def extract_batch_attributes(
        self,
        image: Image.Image,
        detections: list[dict[str, Any]],
    ) -> BatchExtractionResult:
        """Extract attributes from all detections in a batch.

        This method processes all detections via the ai-florence HTTP service,
        which keeps the Florence-2 model loaded and ready for inference.

        Args:
            image: Full frame image
            detections: List of detection dictionaries with:
                - class_name: Detection class (e.g., "person", "car")
                - bbox: Bounding box as [x1, y1, x2, y2]
                - detection_id: Optional unique ID for the detection

        Returns:
            BatchExtractionResult with all extracted attributes
        """
        result = BatchExtractionResult()

        # Separate detections by type
        vehicle_dets = []
        person_dets = []

        for det in detections:
            class_name = det.get("class_name", "").lower()
            if class_name in VEHICLE_CLASSES:
                vehicle_dets.append(det)
            elif class_name == PERSON_CLASS:
                person_dets.append(det)

        # Extract vehicle attributes
        for det in vehicle_dets:
            bbox = det.get("bbox")
            if bbox:
                bbox = tuple(bbox) if isinstance(bbox, list) else bbox
                cropped = self._crop_image(image, bbox)
            else:
                cropped = image

            vehicle_attrs = await self._extract_vehicle_internal(cropped)
            det_id = det.get("detection_id", str(len(result.vehicle_attributes)))
            result.vehicle_attributes[det_id] = vehicle_attrs

        # Extract person attributes
        for det in person_dets:
            bbox = det.get("bbox")
            if bbox:
                bbox = tuple(bbox) if isinstance(bbox, list) else bbox
                cropped = self._crop_image(image, bbox)
            else:
                cropped = image

            person_attrs = await self._extract_person_internal(cropped)
            det_id = det.get("detection_id", str(len(result.person_attributes)))
            result.person_attributes[det_id] = person_attrs

        # Extract scene analysis (full frame)
        result.scene_analysis = await self._extract_scene_internal(image)

        # Extract environment context (full frame)
        result.environment_context = await self._extract_environment_internal(image)

        logger.info(
            f"Extracted attributes: {len(result.vehicle_attributes)} vehicles, "
            f"{len(result.person_attributes)} persons"
        )
        return result

    async def _extract_vehicle_internal(
        self,
        image: Image.Image,
    ) -> VehicleAttributes:
        """Extract vehicle attributes via HTTP service.

        Args:
            image: Cropped vehicle image

        Returns:
            VehicleAttributes with extracted information
        """
        caption = await self._query_florence(image, CAPTION_TASK)
        color = await self._query_florence(image, VQA_TASK, VEHICLE_QUERIES["color"])
        vehicle_type = await self._query_florence(image, VQA_TASK, VEHICLE_QUERIES["type"])
        commercial_response = await self._query_florence(
            image, VQA_TASK, VEHICLE_QUERIES["commercial"]
        )

        is_commercial = self._parse_yes_no(commercial_response)

        commercial_text = None
        if is_commercial:
            commercial_text = await self._query_florence(
                image, VQA_TASK, VEHICLE_QUERIES["commercial_text"]
            )
            commercial_text = self._parse_none_response(commercial_text)

        return VehicleAttributes(
            color=color.strip() if color else None,
            vehicle_type=vehicle_type.strip() if vehicle_type else None,
            is_commercial=is_commercial,
            commercial_text=commercial_text,
            caption=caption,
        )

    async def _extract_person_internal(
        self,
        image: Image.Image,
    ) -> PersonAttributes:
        """Extract person attributes via HTTP service.

        Args:
            image: Cropped person image

        Returns:
            PersonAttributes with extracted information
        """
        caption = await self._query_florence(image, CAPTION_TASK)
        clothing = await self._query_florence(image, VQA_TASK, PERSON_QUERIES["clothing"])
        carrying_response = await self._query_florence(image, VQA_TASK, PERSON_QUERIES["carrying"])
        service_response = await self._query_florence(
            image, VQA_TASK, PERSON_QUERIES["service_worker"]
        )
        action = await self._query_florence(image, VQA_TASK, PERSON_QUERIES["action"])

        return PersonAttributes(
            clothing=clothing.strip() if clothing else None,
            carrying=self._parse_none_response(carrying_response),
            is_service_worker=self._parse_yes_no(service_response),
            action=action.strip() if action else None,
            caption=caption,
        )

    async def _extract_scene_internal(
        self,
        image: Image.Image,
    ) -> SceneAnalysis:
        """Extract scene analysis via HTTP service.

        Args:
            image: Full frame image

        Returns:
            SceneAnalysis with detected unusual elements
        """
        description = await self._query_florence(image, CAPTION_TASK)
        unusual_response = await self._query_florence(image, VQA_TASK, SCENE_QUERIES["unusual"])
        tools_response = await self._query_florence(image, VQA_TASK, SCENE_QUERIES["tools"])
        abandoned_response = await self._query_florence(image, VQA_TASK, SCENE_QUERIES["abandoned"])

        unusual_objects: list[str] = []
        if unusual_response and not self._is_negative_response(unusual_response):
            unusual_objects = [unusual_response.strip()]

        tools_detected: list[str] = []
        if tools_response and not self._is_negative_response(tools_response):
            tools_detected = [t.strip() for t in tools_response.split(",") if t.strip()]

        abandoned_items: list[str] = []
        if abandoned_response and not self._is_negative_response(abandoned_response):
            abandoned_items = [abandoned_response.strip()]

        return SceneAnalysis(
            unusual_objects=unusual_objects,
            tools_detected=tools_detected,
            abandoned_items=abandoned_items,
            scene_description=description,
        )

    async def _extract_environment_internal(
        self,
        image: Image.Image,
    ) -> EnvironmentContext:
        """Extract environment context via HTTP service.

        Args:
            image: Full frame image

        Returns:
            EnvironmentContext with time, lighting, and weather info
        """
        time_response = await self._query_florence(
            image, VQA_TASK, ENVIRONMENT_QUERIES["time_of_day"]
        )
        light_response = await self._query_florence(
            image, VQA_TASK, ENVIRONMENT_QUERIES["artificial_light"]
        )
        weather_response = await self._query_florence(
            image, VQA_TASK, ENVIRONMENT_QUERIES["weather"]
        )

        time_lower = time_response.lower() if time_response else ""
        if "night" in time_lower:
            time_of_day = "night"
        elif "dusk" in time_lower or "dawn" in time_lower or "evening" in time_lower:
            time_of_day = "dusk"
        else:
            time_of_day = "day"

        return EnvironmentContext(
            time_of_day=time_of_day,
            artificial_light=self._parse_yes_no(light_response),
            weather=self._parse_none_response(weather_response),
        )


# Global service instance
_vision_extractor: VisionExtractor | None = None


def get_vision_extractor() -> VisionExtractor:
    """Get or create the global VisionExtractor instance.

    Returns:
        Global VisionExtractor instance
    """
    global _vision_extractor  # noqa: PLW0603
    if _vision_extractor is None:
        _vision_extractor = VisionExtractor()
    return _vision_extractor


def reset_vision_extractor() -> None:
    """Reset the global VisionExtractor instance (for testing)."""
    global _vision_extractor  # noqa: PLW0603
    _vision_extractor = None


# ============================================================================
# Prompt Formatting Functions
# ============================================================================


def format_vehicle_attributes(
    attrs: VehicleAttributes,
    detection_id: str | None = None,
) -> str:
    """Format vehicle attributes for prompt inclusion.

    Args:
        attrs: VehicleAttributes to format
        detection_id: Optional detection ID prefix

    Returns:
        Formatted string for prompt
    """
    lines = []
    prefix = f"[{detection_id}] " if detection_id else ""

    # Start with caption
    lines.append(f"{prefix}Vehicle: {attrs.caption}")

    # Add specific attributes
    details = []
    if attrs.color:
        details.append(f"Color: {attrs.color}")
    if attrs.vehicle_type:
        details.append(f"Type: {attrs.vehicle_type}")
    if attrs.is_commercial:
        commercial_desc = "Commercial vehicle"
        if attrs.commercial_text:
            commercial_desc += f" ({attrs.commercial_text})"
        details.append(commercial_desc)

    if details:
        lines.append(f"  {', '.join(details)}")

    return "\n".join(lines)


def format_person_attributes(
    attrs: PersonAttributes,
    detection_id: str | None = None,
) -> str:
    """Format person attributes for prompt inclusion.

    Args:
        attrs: PersonAttributes to format
        detection_id: Optional detection ID prefix

    Returns:
        Formatted string for prompt
    """
    lines = []
    prefix = f"[{detection_id}] " if detection_id else ""

    # Start with caption
    lines.append(f"{prefix}Person: {attrs.caption}")

    # Add specific attributes
    details = []
    if attrs.clothing:
        details.append(f"Wearing: {attrs.clothing}")
    if attrs.carrying:
        details.append(f"Carrying: {attrs.carrying}")
    if attrs.action:
        details.append(f"Action: {attrs.action}")
    if attrs.is_service_worker:
        details.append("Appears to be service/delivery worker")

    if details:
        lines.append(f"  {', '.join(details)}")

    return "\n".join(lines)


def format_scene_analysis(scene: SceneAnalysis) -> str:
    """Format scene analysis for prompt inclusion.

    Args:
        scene: SceneAnalysis to format

    Returns:
        Formatted string for prompt
    """
    lines = []

    if scene.scene_description:
        lines.append(f"Scene: {scene.scene_description}")

    if scene.unusual_objects:
        lines.append(f"Unusual objects: {', '.join(scene.unusual_objects)}")

    if scene.tools_detected:
        lines.append(f"Tools detected: {', '.join(scene.tools_detected)}")

    if scene.abandoned_items:
        lines.append(f"Abandoned items: {', '.join(scene.abandoned_items)}")

    if not lines:
        return "No notable scene elements detected."

    return "\n".join(lines)


def format_environment_context(env: EnvironmentContext) -> str:
    """Format environment context for prompt inclusion.

    Args:
        env: EnvironmentContext to format

    Returns:
        Formatted string for prompt
    """
    parts = [f"Time of day: {env.time_of_day}"]

    if env.artificial_light:
        parts.append("Artificial light source detected")

    if env.weather:
        parts.append(f"Weather: {env.weather}")

    return ", ".join(parts)


def format_batch_extraction_result(
    result: BatchExtractionResult,
    include_scene: bool = True,
    include_environment: bool = True,
) -> str:
    """Format a complete batch extraction result for prompt inclusion.

    Args:
        result: BatchExtractionResult to format
        include_scene: Whether to include scene analysis
        include_environment: Whether to include environment context

    Returns:
        Formatted string for prompt
    """
    sections = []

    # Format vehicle attributes
    if result.vehicle_attributes:
        vehicle_lines = ["## Vehicles"]
        for det_id, vehicle_attrs in result.vehicle_attributes.items():
            vehicle_lines.append(format_vehicle_attributes(vehicle_attrs, det_id))
        sections.append("\n".join(vehicle_lines))

    # Format person attributes
    if result.person_attributes:
        person_lines = ["## Persons"]
        for det_id, person_attrs in result.person_attributes.items():
            person_lines.append(format_person_attributes(person_attrs, det_id))
        sections.append("\n".join(person_lines))

    # Format scene analysis
    if include_scene and result.scene_analysis:
        scene_section = "## Scene Analysis\n" + format_scene_analysis(result.scene_analysis)
        sections.append(scene_section)

    # Format environment context
    if include_environment and result.environment_context:
        env_section = "## Environment\n" + format_environment_context(result.environment_context)
        sections.append(env_section)

    if not sections:
        return "No vision extraction data available."

    return "\n\n".join(sections)


def format_detections_with_attributes(  # noqa: PLR0912
    detections: list[dict[str, Any]],
    result: BatchExtractionResult,
) -> str:
    """Format detections list with vision extraction attributes inline.

    This creates a combined view of detections with their extracted attributes
    for use in the Nemotron prompt's detection section.

    Args:
        detections: List of detection dicts with class_name, confidence, bbox, detection_id
        result: BatchExtractionResult with extracted attributes

    Returns:
        Formatted string with detections and their attributes
    """
    lines = []

    for det in detections:
        det_id = det.get("detection_id", "")
        class_name = det.get("class_name", "unknown")
        confidence = det.get("confidence", 0.0)
        bbox = det.get("bbox", [])

        # Base detection info
        bbox_str = f"[{', '.join(str(int(b)) for b in bbox)}]" if bbox else "[]"
        base_line = f"- {class_name} ({confidence:.0%}) at {bbox_str}"

        # Add attributes if available
        if det_id in result.vehicle_attributes:
            vehicle_attrs = result.vehicle_attributes[det_id]
            attr_parts = []
            if vehicle_attrs.color:
                attr_parts.append(vehicle_attrs.color)
            if vehicle_attrs.vehicle_type:
                attr_parts.append(vehicle_attrs.vehicle_type)
            if vehicle_attrs.is_commercial:
                commercial = "commercial"
                if vehicle_attrs.commercial_text:
                    commercial = f"commercial: {vehicle_attrs.commercial_text}"
                attr_parts.append(commercial)
            if attr_parts:
                base_line += f" [{', '.join(attr_parts)}]"

        elif det_id in result.person_attributes:
            person_attrs = result.person_attributes[det_id]
            attr_parts = []
            if person_attrs.clothing:
                attr_parts.append(person_attrs.clothing)
            if person_attrs.carrying:
                attr_parts.append(f"carrying {person_attrs.carrying}")
            if person_attrs.action:
                attr_parts.append(person_attrs.action)
            if person_attrs.is_service_worker:
                attr_parts.append("service worker")
            if attr_parts:
                base_line += f" [{', '.join(attr_parts)}]"

        lines.append(base_line)

    if not lines:
        return "No detections."

    return "\n".join(lines)
