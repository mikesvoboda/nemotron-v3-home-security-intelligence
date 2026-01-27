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

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger
from backend.services.bbox_validation import prepare_bbox_for_crop
from backend.services.florence_client import FlorenceUnavailableError, get_florence_client

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)

# Regex pattern to match Florence-2 location tokens like <loc_123>
# Replace with a space to preserve word boundaries
_LOC_TOKEN_PATTERN = re.compile(r"<loc_\d+>")

# Pattern to match VQA prefix and question up to the first loc token or end
# Handles: "VQA>What tools are visible?A ladder" -> removes "VQA>What tools are visible?"
# The question typically ends with ? followed by the actual answer
_VQA_PREFIX_PATTERN = re.compile(r"^.*?VQA>[^?]*\?", re.IGNORECASE)

# Patterns for validation of VQA output (NEM-3009)
# These patterns indicate garbage output that should be rejected
_GARBAGE_TOKEN_PATTERNS = [
    re.compile(r"<loc_\d+>"),  # Location tokens
    re.compile(r"<poly>", re.IGNORECASE),  # Polygon tokens
    re.compile(r"<pad>", re.IGNORECASE),  # Padding tokens
    re.compile(r"VQA>", re.IGNORECASE),  # VQA prefix artifact
]

# Minimum valid length for a meaningful VQA response
# Single letter outputs like "a" or "-" are considered garbage
_MIN_VALID_LENGTH = 2

# Short valid responses that are accepted despite being short
_VALID_SHORT_RESPONSES = frozenset(
    {"no", "yes", "red", "blue", "green", "white", "black", "gray", "grey", "suv", "van"}
)


def clean_vqa_output(text: str) -> str:
    """Clean Florence-2 VQA output by removing artifacts.

    Florence-2 VQA responses can contain artifacts that leak into downstream
    prompts, including:
    - VQA> prefix with the original question echoed
    - <loc_N> location tokens from the model's spatial encoding
    - Duplicated words like "visible visible" or "etc.) etc.)"

    Args:
        text: Raw VQA output text from Florence-2

    Returns:
        Cleaned text with artifacts removed. Returns empty string if the
        cleaned result would be empty or just whitespace.

    Examples:
        >>> clean_vqa_output("VQA>Are there any unusual objects<loc_1><loc_998>")
        ''
        >>> clean_vqa_output("A ladder against the wall<loc_100><loc_200>")
        'A ladder against the wall'
        >>> clean_vqa_output("tools visible visible (ladder)")
        'tools visible (ladder)'
    """
    if not text:
        return ""

    result = text

    # Remove VQA> prefix and the question (up to and including the ?)
    # This handles cases like "VQA>What tools are visible?A ladder"
    result = _VQA_PREFIX_PATTERN.sub("", result)

    # Also handle case where VQA prefix exists but no question mark follows
    # (the question may have been truncated or not include ?)
    # Remove "VQA>" and any following text that looks like a question
    if "VQA>" in result:
        # Find VQA> and remove everything from start to the first < (loc token)
        vqa_idx = result.find("VQA>")
        if vqa_idx != -1:
            # Find the first < after VQA>, or empty if no loc tokens
            loc_start = result.find("<", vqa_idx)
            result = result[loc_start:] if loc_start != -1 else ""

    # Replace all <loc_N> tokens with spaces to preserve word boundaries
    result = _LOC_TOKEN_PATTERN.sub(" ", result)

    # Remove duplicated consecutive words (case-insensitive)
    # Handles "visible visible", "etc.) etc.)", "the the", etc.
    # Use a function to preserve original case of first occurrence
    def remove_consecutive_duplicates(s: str) -> str:
        words = s.split()
        if len(words) < 2:
            return s

        cleaned_words = [words[0]]
        for i in range(1, len(words)):
            # Compare lowercase versions to catch "Visible visible"
            if words[i].lower() != words[i - 1].lower():
                cleaned_words.append(words[i])

        return " ".join(cleaned_words)

    result = remove_consecutive_duplicates(result)

    # Strip extra whitespace (normalizes multiple spaces to single space)
    result = " ".join(result.split())

    return result.strip()


def is_valid_vqa_output(text: str) -> bool:
    """Validate Florence-2 VQA output for garbage token patterns.

    Florence-2 VQA can return garbage outputs containing location tokens,
    prompt artifacts, or other invalid patterns instead of actual text answers.
    This function detects such garbage outputs.

    NEM-3009: VQA outputs like "VQA>person wearing<loc_95><loc_86><loc_901><loc_918>"
    should be rejected so the system can fall back to scene captioning.

    Args:
        text: VQA output text to validate

    Returns:
        True if the output appears to be valid text, False if it contains
        garbage patterns that indicate a failed VQA response.

    Examples:
        >>> is_valid_vqa_output("dark hoodie and jeans")
        True
        >>> is_valid_vqa_output("<loc_95><loc_86><loc_901><loc_918>")
        False
        >>> is_valid_vqa_output("VQA>person wearing<loc_95>")
        False
    """
    if not text or not text.strip():
        return False

    # Check for garbage token patterns
    for pattern in _GARBAGE_TOKEN_PATTERNS:
        if pattern.search(text):
            return False

    # Check minimum length (unless it's a known valid short response)
    stripped = text.strip().lower()
    return not (len(stripped) < _MIN_VALID_LENGTH and stripped not in _VALID_SHORT_RESPONSES)


def validate_and_clean_vqa_output(text: str) -> str | None:
    """Clean and validate Florence-2 VQA output, returning None if invalid.

    This function combines cleaning (removing artifacts) with validation
    (detecting garbage output). It first validates the raw text for garbage
    patterns - if any are found, the output is rejected entirely. Only clean
    outputs are then processed for artifact removal.

    NEM-3304: When VQA returns output containing <loc_> tokens like
    "sedan<loc_1><loc_2>" or "walking<loc_100>", the entire output should
    be rejected and return None. We do not clean and accept such outputs
    because the presence of location tokens indicates a failed VQA response.

    Args:
        text: Raw VQA output text from Florence-2

    Returns:
        Cleaned text if valid, or None if the output contains garbage tokens.
        Returning None allows callers to implement fallback behavior.

    Examples:
        >>> validate_and_clean_vqa_output("dark hoodie and jeans")
        'dark hoodie and jeans'
        >>> validate_and_clean_vqa_output("sedan<loc_1><loc_2>")
        None
        >>> validate_and_clean_vqa_output("walking<loc_100>")
        None
        >>> validate_and_clean_vqa_output("<loc_95><loc_86><loc_901><loc_918>")
        None
        >>> validate_and_clean_vqa_output("VQA>person wearing<loc_95>")
        None
    """
    if not text:
        return None

    # CRITICAL (NEM-3304): Validate BEFORE cleaning
    # If the original output contains garbage tokens (especially <loc_>),
    # reject it entirely. Do not clean and accept.
    for pattern in _GARBAGE_TOKEN_PATTERNS:
        if pattern.search(text):
            return None

    # Now that we've validated the raw text doesn't contain garbage tokens,
    # clean it to remove other artifacts (whitespace, duplicates, etc.)
    cleaned = clean_vqa_output(text)

    # If cleaning resulted in empty string, it's invalid
    if not cleaned:
        return None

    # Check minimum length
    if len(cleaned) < _MIN_VALID_LENGTH and cleaned.lower() not in _VALID_SHORT_RESPONSES:
        return None

    return cleaned


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

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "color": self.color,
            "vehicle_type": self.vehicle_type,
            "is_commercial": self.is_commercial,
            "commercial_text": self.commercial_text,
            "caption": self.caption,
        }


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

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "clothing": self.clothing,
            "carrying": self.carrying,
            "is_service_worker": self.is_service_worker,
            "action": self.action,
            "caption": self.caption,
        }


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

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "unusual_objects": self.unusual_objects,
            "tools_detected": self.tools_detected,
            "abandoned_items": self.abandoned_items,
            "scene_description": self.scene_description,
        }


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

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "vehicle_attributes": {
                det_id: attrs.to_dict() for det_id, attrs in self.vehicle_attributes.items()
            },
            "person_attributes": {
                det_id: attrs.to_dict() for det_id, attrs in self.person_attributes.items()
            },
            "scene_analysis": self.scene_analysis.to_dict() if self.scene_analysis else None,
            "environment_context": (
                self.environment_context.to_dict() if self.environment_context else None
            ),
        }


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

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "time_of_day": self.time_of_day,
            "artificial_light": self.artificial_light,
            "weather": self.weather,
        }


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

# Security-focused VQA queries for threat assessment
# These questions help identify suspicious behavior or potential threats
SECURITY_VQA_QUERIES = {
    "looking_at_camera": "Is this person looking at the camera?",
    "weapons_or_tools": "Are there any weapons or tools visible?",
    "face_covering": "Is this person wearing a mask or face covering?",
    "bags_or_packages": "Are there any bags or packages being carried?",
    "gloves": "Is this person wearing gloves?",
    "interaction_with_property": "Is this person interacting with doors, windows, or locks?",
    "flashlight": "Is this person carrying or using a flashlight?",
    "crouching_or_hiding": "Is this person crouching, hiding, or trying to stay out of view?",
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

        Handles edge cases such as:
        - Inverted coordinates (x2 < x1 or y2 < y1)
        - Out-of-bounds coordinates
        - Zero-dimension boxes

        Args:
            image: Full PIL Image
            bbox: Bounding box as (x1, y1, x2, y2)

        Returns:
            Cropped PIL Image with 10% padding, or original image if bbox is invalid
        """
        img_width, img_height = image.size

        # Calculate 10% padding based on box dimensions
        # Handle inverted coords by using abs()
        x1, y1, x2, y2 = bbox
        width = abs(x2 - x1)
        height = abs(y2 - y1)
        pad_x = int(width * 0.1) if width > 0 else 0
        pad_y = int(height * 0.1) if height > 0 else 0
        padding = max(pad_x, pad_y)

        # Use safe crop preparation that handles all edge cases
        safe_bbox = prepare_bbox_for_crop(
            bbox,
            image_width=img_width,
            image_height=img_height,
            padding=padding,
            min_size=1,
        )

        if safe_bbox is None:
            logger.warning(
                f"Invalid bounding box {bbox} for image size {img_width}x{img_height}. "
                f"Using full image instead."
            )
            return image

        return image.crop(safe_bbox)

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

        Note:
            NEM-3009: VQA responses are validated and garbage outputs (containing
            location tokens, VQA> prefix, etc.) are rejected. Invalid outputs
            result in None for that attribute, with the caption providing fallback.
        """
        if bbox is not None:
            image = self._crop_image(image, bbox)

        # Get caption first (used as fallback context when VQA fails)
        caption = await self._query_florence(image, CAPTION_TASK)

        # Query for specific attributes and validate each response (NEM-3009)
        color_raw = await self._query_florence(image, VQA_TASK, VEHICLE_QUERIES["color"])
        vehicle_type_raw = await self._query_florence(image, VQA_TASK, VEHICLE_QUERIES["type"])
        commercial_response = await self._query_florence(
            image, VQA_TASK, VEHICLE_QUERIES["commercial"]
        )

        # Validate VQA responses to reject garbage outputs
        color = validate_and_clean_vqa_output(color_raw)
        vehicle_type = validate_and_clean_vqa_output(vehicle_type_raw)

        is_commercial = self._parse_yes_no(commercial_response)

        commercial_text = None
        if is_commercial:
            commercial_text_raw = await self._query_florence(
                image, VQA_TASK, VEHICLE_QUERIES["commercial_text"]
            )
            commercial_text_clean = validate_and_clean_vqa_output(commercial_text_raw)
            commercial_text = (
                self._parse_none_response(commercial_text_clean) if commercial_text_clean else None
            )

        return VehicleAttributes(
            color=color,
            vehicle_type=vehicle_type,
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

        Note:
            NEM-3009: VQA responses are validated and garbage outputs (containing
            location tokens, VQA> prefix, etc.) are rejected. Invalid outputs
            result in None for that attribute, with the caption providing fallback.
        """
        if bbox is not None:
            image = self._crop_image(image, bbox)

        # Get caption first (used as fallback context when VQA fails)
        caption = await self._query_florence(image, CAPTION_TASK)

        # Query for specific attributes and validate each response (NEM-3009)
        clothing_raw = await self._query_florence(image, VQA_TASK, PERSON_QUERIES["clothing"])
        carrying_raw = await self._query_florence(image, VQA_TASK, PERSON_QUERIES["carrying"])
        service_response = await self._query_florence(
            image, VQA_TASK, PERSON_QUERIES["service_worker"]
        )
        action_raw = await self._query_florence(image, VQA_TASK, PERSON_QUERIES["action"])

        # Validate VQA responses to reject garbage outputs
        clothing = validate_and_clean_vqa_output(clothing_raw)
        carrying_clean = validate_and_clean_vqa_output(carrying_raw)
        action = validate_and_clean_vqa_output(action_raw)

        return PersonAttributes(
            clothing=clothing,
            carrying=self._parse_none_response(carrying_clean) if carrying_clean else None,
            is_service_worker=self._parse_yes_no(service_response),
            action=action,
            caption=caption,
        )

    async def extract_with_vqa(
        self,
        image: Image.Image,
        questions: list[str],
        bbox: tuple[int, int, int, int] | None = None,
    ) -> dict[str, str]:
        """Ask custom questions about an image using Florence-2 VQA.

        This method allows querying the image with arbitrary security-focused
        questions, returning the model's responses for each question.

        Args:
            image: PIL Image to analyze (full frame or cropped)
            questions: List of questions to ask about the image
            bbox: Optional bounding box to crop (x1, y1, x2, y2)

        Returns:
            Dictionary mapping each question to its answer.
            Empty answers are filtered out.

        Example:
            >>> questions = [
            ...     "Is this person looking at the camera?",
            ...     "Are there any weapons visible?",
            ... ]
            >>> results = await extractor.extract_with_vqa(image, questions)
            >>> # {'Is this person looking at the camera?': 'Yes, directly', ...}
        """
        if bbox is not None:
            image = self._crop_image(image, bbox)

        results: dict[str, str] = {}
        for question in questions:
            answer = await self._query_florence(image, VQA_TASK, question)
            # Only include non-empty answers
            if answer and answer.strip():
                results[question] = answer.strip()

        logger.debug(
            f"VQA extraction completed: {len(results)}/{len(questions)} questions answered"
        )
        return results

    async def extract_security_vqa(
        self,
        image: Image.Image,
        bbox: tuple[int, int, int, int] | None = None,
    ) -> dict[str, str]:
        """Extract security-specific VQA answers using predefined questions.

        This is a convenience method that uses the default security-focused
        questions defined in SECURITY_VQA_QUERIES for threat assessment.

        Args:
            image: PIL Image to analyze
            bbox: Optional bounding box to crop (x1, y1, x2, y2)

        Returns:
            Dictionary mapping security questions to answers
        """
        return await self.extract_with_vqa(image, list(SECURITY_VQA_QUERIES.values()), bbox)

    async def extract_scene_caption(
        self,
        image: Image.Image,
    ) -> str:
        """Extract a detailed scene caption using Florence-2.

        This method uses DETAILED_CAPTION_TASK to generate a richer, more
        comprehensive description of the scene compared to the standard
        CAPTION_TASK. Useful for providing more context to the LLM for
        risk assessment.

        Args:
            image: Full frame image

        Returns:
            Detailed scene description string
        """
        caption = await self._query_florence(image, DETAILED_CAPTION_TASK)
        return caption.strip() if caption else ""

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

        # Clean VQA responses to remove Florence-2 artifacts
        unusual_cleaned = clean_vqa_output(unusual_response)
        tools_cleaned = clean_vqa_output(tools_response)
        abandoned_cleaned = clean_vqa_output(abandoned_response)

        # Parse responses into lists
        unusual_objects: list[str] = []
        if unusual_cleaned and not self._is_negative_response(unusual_cleaned):
            unusual_objects = [unusual_cleaned]

        tools_detected: list[str] = []
        if tools_cleaned and not self._is_negative_response(tools_cleaned):
            # Parse comma-separated tools
            tools_detected = [t.strip() for t in tools_cleaned.split(",") if t.strip()]

        abandoned_items: list[str] = []
        if abandoned_cleaned and not self._is_negative_response(abandoned_cleaned):
            abandoned_items = [abandoned_cleaned]

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

        Note:
            NEM-3304: VQA responses are validated to reject garbage outputs
            containing <loc_> tokens or VQA> prefix artifacts.
        """
        caption = await self._query_florence(image, CAPTION_TASK)
        color_raw = await self._query_florence(image, VQA_TASK, VEHICLE_QUERIES["color"])
        vehicle_type_raw = await self._query_florence(image, VQA_TASK, VEHICLE_QUERIES["type"])
        commercial_response = await self._query_florence(
            image, VQA_TASK, VEHICLE_QUERIES["commercial"]
        )

        # Validate VQA responses to reject garbage outputs (NEM-3304)
        color = validate_and_clean_vqa_output(color_raw)
        vehicle_type = validate_and_clean_vqa_output(vehicle_type_raw)

        is_commercial = self._parse_yes_no(commercial_response)

        commercial_text = None
        if is_commercial:
            commercial_text_raw = await self._query_florence(
                image, VQA_TASK, VEHICLE_QUERIES["commercial_text"]
            )
            commercial_text_clean = validate_and_clean_vqa_output(commercial_text_raw)
            commercial_text = (
                self._parse_none_response(commercial_text_clean) if commercial_text_clean else None
            )

        return VehicleAttributes(
            color=color,
            vehicle_type=vehicle_type,
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

        Note:
            NEM-3304: VQA responses are validated to reject garbage outputs
            like "VQA>person wearing<loc_95><loc_86><loc_901><loc_918>".
        """
        caption = await self._query_florence(image, CAPTION_TASK)
        clothing_raw = await self._query_florence(image, VQA_TASK, PERSON_QUERIES["clothing"])
        carrying_raw = await self._query_florence(image, VQA_TASK, PERSON_QUERIES["carrying"])
        service_response = await self._query_florence(
            image, VQA_TASK, PERSON_QUERIES["service_worker"]
        )
        action_raw = await self._query_florence(image, VQA_TASK, PERSON_QUERIES["action"])

        # Validate VQA responses to reject garbage outputs (NEM-3304)
        clothing = validate_and_clean_vqa_output(clothing_raw)
        carrying_clean = validate_and_clean_vqa_output(carrying_raw)
        action = validate_and_clean_vqa_output(action_raw)

        return PersonAttributes(
            clothing=clothing,
            carrying=self._parse_none_response(carrying_clean) if carrying_clean else None,
            is_service_worker=self._parse_yes_no(service_response),
            action=action,
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

        # Clean VQA responses to remove Florence-2 artifacts
        unusual_cleaned = clean_vqa_output(unusual_response)
        tools_cleaned = clean_vqa_output(tools_response)
        abandoned_cleaned = clean_vqa_output(abandoned_response)

        unusual_objects: list[str] = []
        if unusual_cleaned and not self._is_negative_response(unusual_cleaned):
            unusual_objects = [unusual_cleaned]

        tools_detected: list[str] = []
        if tools_cleaned and not self._is_negative_response(tools_cleaned):
            tools_detected = [t.strip() for t in tools_cleaned.split(",") if t.strip()]

        abandoned_items: list[str] = []
        if abandoned_cleaned and not self._is_negative_response(abandoned_cleaned):
            abandoned_items = [abandoned_cleaned]

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


def format_detections_with_attributes(
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
