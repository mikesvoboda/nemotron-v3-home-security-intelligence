"""NVIDIA Vision API wrapper for ground truth generation.

This module provides a client for NVIDIA's vision-capable models (e.g., NVLM)
to analyze security camera images and generate ground truth data for evaluating
the local RT-DETRv2 + Nemotron pipeline.

The analyzer extracts:
- Scene descriptions
- Detected objects with bounding boxes and confidence scores
- Risk assessments (risk score, level, reasoning)
- Scene attributes (lighting, weather, activity level)

Usage:
    analyzer = NVIDIAVisionAnalyzer()
    result = await analyzer.analyze_image(Path("suspicious_person.jpg"))
    print(f"Risk score: {result.risk_assessment['risk_score']}")
    print(f"Objects: {result.detected_objects}")
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from collections.abc import Sequence

# NVIDIA API endpoint for vision models
NVIDIA_API_ENDPOINT = "https://integrate.api.nvidia.com/v1"

# Supported image formats
SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

# Vision model to use (NVLM is NVIDIA's vision-language model)
DEFAULT_VISION_MODEL = "nvidia/llama-3.2-nv-vision-90b-instruct"

# Cache directory for API responses
DEFAULT_CACHE_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "backend"
    / "tests"
    / "fixtures"
    / "synthetic"
    / ".vision_cache"
)


class VisionAnalysisResult(BaseModel):
    """Result from NVIDIA vision model analysis.

    Contains structured output from analyzing a security camera image,
    including scene description, detected objects, risk assessment,
    and scene attributes.
    """

    description: str = Field(description="Natural language description of the scene")
    detected_objects: list[dict[str, Any]] = Field(
        default_factory=list, description="List of detected objects with type, confidence, and bbox"
    )
    risk_assessment: dict[str, Any] = Field(
        default_factory=dict, description="Risk assessment with score, level, and reasoning"
    )
    scene_attributes: dict[str, Any] = Field(
        default_factory=dict, description="Scene attributes like lighting, weather, activity"
    )
    raw_response: str = Field(
        default="", description="Raw response from the vision model for debugging"
    )


@dataclass
class VisionAnalyzerConfig:
    """Configuration for the NVIDIA Vision Analyzer."""

    api_key: str | None = None
    endpoint: str = NVIDIA_API_ENDPOINT
    model: str = DEFAULT_VISION_MODEL
    timeout: float = 60.0
    max_retries: int = 3
    cache_enabled: bool = True
    cache_dir: Path = field(default_factory=lambda: DEFAULT_CACHE_DIR)
    mock_mode: bool = False


class NVIDIAVisionAnalyzer:
    """Wrapper for NVIDIA vision-capable models.

    This class provides methods to analyze images using NVIDIA's vision models
    (like NVLM) to generate ground truth data for pipeline evaluation.

    Features:
    - Async image analysis with structured output
    - Response caching to avoid repeated API costs
    - Mock mode for testing without API calls
    - Batch processing with concurrency control
    - Automatic retry with exponential backoff

    Example:
        >>> analyzer = NVIDIAVisionAnalyzer()
        >>> result = await analyzer.analyze_image(Path("front_door.jpg"))
        >>> print(f"Risk: {result.risk_assessment['risk_level']}")
        'medium'
    """

    def __init__(
        self,
        api_key: str | None = None,
        config: VisionAnalyzerConfig | None = None,
    ) -> None:
        """Initialize the NVIDIA Vision Analyzer.

        Args:
            api_key: NVIDIA API key. If not provided, reads from NVIDIA_API_KEY env var.
            config: Optional configuration object. If not provided, uses defaults.
        """
        self.config = config or VisionAnalyzerConfig()

        # API key priority: argument > config > environment
        self.api_key = api_key or self.config.api_key or os.environ.get("NVIDIA_API_KEY")

        if not self.api_key and not self.config.mock_mode:
            print("Warning: NVIDIA_API_KEY not set. Running in mock mode.")
            self.config.mock_mode = True

        # Ensure cache directory exists
        if self.config.cache_enabled:
            self.config.cache_dir.mkdir(parents=True, exist_ok=True)

        # Create HTTP client
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _get_cache_key(self, image_path: Path) -> str:
        """Generate a cache key for an image.

        Uses SHA256 hash of image content for cache invalidation when images change.
        """
        image_content = image_path.read_bytes()
        content_hash = hashlib.sha256(image_content).hexdigest()[:16]
        return f"{image_path.stem}_{content_hash}"

    def _get_cached_result(self, cache_key: str) -> VisionAnalysisResult | None:
        """Retrieve a cached analysis result if available."""
        if not self.config.cache_enabled:
            return None

        cache_file = self.config.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                return VisionAnalysisResult(**data)
            except (json.JSONDecodeError, KeyError, TypeError):
                # Invalid cache entry, will regenerate
                return None
        return None

    def _save_to_cache(self, cache_key: str, result: VisionAnalysisResult) -> None:
        """Save an analysis result to cache."""
        if not self.config.cache_enabled:
            return

        cache_file = self.config.cache_dir / f"{cache_key}.json"
        cache_file.write_text(result.model_dump_json(indent=2))

    def _encode_image_to_base64(self, image_path: Path) -> str:
        """Encode an image file to base64 string."""
        image_data = image_path.read_bytes()
        return base64.standard_b64encode(image_data).decode("utf-8")

    def _get_image_media_type(self, image_path: Path) -> str:
        """Get the MIME type for an image file."""
        suffix = image_path.suffix.lower()
        media_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        return media_types.get(suffix, "image/jpeg")

    def _build_analysis_prompt(self) -> str:
        """Build the prompt for image analysis.

        Returns a structured prompt that instructs the vision model to output
        JSON with the expected fields.
        """
        return """Analyze this security camera image and provide a structured JSON response.

You are a home security AI analyzing camera footage. Evaluate the scene for potential security concerns.

Return ONLY a valid JSON object with these exact fields:
{
    "description": "A detailed description of what you see in the image",
    "detected_objects": [
        {
            "type": "person|car|truck|dog|cat|bicycle|motorcycle|bus|unknown",
            "confidence": 0.0 to 1.0,
            "bbox": [x, y, width, height] as approximate percentages (0-100),
            "attributes": {"optional": "details like clothing, behavior, etc."}
        }
    ],
    "risk_assessment": {
        "risk_score": 0 to 100,
        "risk_level": "low|medium|high|critical",
        "reasoning": "Explanation of the risk assessment",
        "concerning_factors": ["list", "of", "concerns"],
        "mitigating_factors": ["list", "of", "mitigating", "factors"]
    },
    "scene_attributes": {
        "lighting": "daylight|dusk|night|artificial",
        "weather": "clear|cloudy|rainy|unknown",
        "activity_level": "none|low|moderate|high",
        "location_type": "front_door|backyard|driveway|side_gate|other"
    }
}

Risk scoring guidelines:
- 0-25 (low): Normal activity - family, expected visitors, pets
- 30-55 (medium): Unusual but not threatening - unknown person, lingering vehicle
- 70-100 (high/critical): Security concern - suspicious behavior, forced entry attempt

Be objective and avoid false positives. Normal delivery people or expected activity should score low."""

    def _generate_mock_result(self, image_path: Path) -> VisionAnalysisResult:
        """Generate a mock result for testing without API calls.

        Uses the image filename to determine the category and generate
        appropriate mock data.
        """
        # Determine category from path
        path_str = str(image_path).lower()
        if "threat" in path_str:
            category = "threat"
        elif "suspicious" in path_str:
            category = "suspicious"
        elif "edge_case" in path_str:
            category = "edge_case"
        else:
            category = "normal"

        # Generate category-appropriate mock data
        mock_data = {
            "normal": {
                "description": "Normal residential scene with expected activity.",
                "detected_objects": [
                    {
                        "type": "person",
                        "confidence": 0.92,
                        "bbox": [30, 20, 15, 40],
                        "attributes": {"activity": "walking"},
                    }
                ],
                "risk_assessment": {
                    "risk_score": 15,
                    "risk_level": "low",
                    "reasoning": "Normal activity observed, no concerning behavior.",
                    "concerning_factors": [],
                    "mitigating_factors": ["Daylight", "Expected activity pattern"],
                },
                "scene_attributes": {
                    "lighting": "daylight",
                    "weather": "clear",
                    "activity_level": "low",
                    "location_type": "front_door",
                },
            },
            "suspicious": {
                "description": "Unknown person lingering near entry point.",
                "detected_objects": [
                    {
                        "type": "person",
                        "confidence": 0.88,
                        "bbox": [45, 30, 12, 35],
                        "attributes": {"behavior": "lingering"},
                    }
                ],
                "risk_assessment": {
                    "risk_score": 45,
                    "risk_level": "medium",
                    "reasoning": "Unknown individual exhibiting unusual behavior near entry point.",
                    "concerning_factors": [
                        "Unknown person",
                        "Lingering behavior",
                        "Near entry point",
                    ],
                    "mitigating_factors": ["Daylight", "No forced entry attempt"],
                },
                "scene_attributes": {
                    "lighting": "dusk",
                    "weather": "clear",
                    "activity_level": "low",
                    "location_type": "front_door",
                },
            },
            "threat": {
                "description": "Suspicious activity detected at entry point.",
                "detected_objects": [
                    {
                        "type": "person",
                        "confidence": 0.95,
                        "bbox": [40, 25, 20, 50],
                        "attributes": {"behavior": "tampering"},
                    }
                ],
                "risk_assessment": {
                    "risk_score": 85,
                    "risk_level": "high",
                    "reasoning": "Individual attempting to tamper with entry point lock.",
                    "concerning_factors": [
                        "Tampering with lock",
                        "Late night",
                        "Unknown person",
                        "Concealing face",
                    ],
                    "mitigating_factors": [],
                },
                "scene_attributes": {
                    "lighting": "night",
                    "weather": "clear",
                    "activity_level": "low",
                    "location_type": "front_door",
                },
            },
            "edge_case": {
                "description": "Person in costume at door during daytime.",
                "detected_objects": [
                    {
                        "type": "person",
                        "confidence": 0.75,
                        "bbox": [35, 20, 18, 45],
                        "attributes": {"wearing": "costume"},
                    }
                ],
                "risk_assessment": {
                    "risk_score": 35,
                    "risk_level": "medium",
                    "reasoning": "Unusual appearance but possibly legitimate (Halloween, costume party).",
                    "concerning_factors": ["Unusual appearance", "Face partially obscured"],
                    "mitigating_factors": [
                        "Daylight",
                        "No aggressive behavior",
                        "Possibly holiday-related",
                    ],
                },
                "scene_attributes": {
                    "lighting": "daylight",
                    "weather": "clear",
                    "activity_level": "low",
                    "location_type": "front_door",
                },
            },
        }

        data = mock_data[category]
        return VisionAnalysisResult(
            description=data["description"],
            detected_objects=data["detected_objects"],
            risk_assessment=data["risk_assessment"],
            scene_attributes=data["scene_attributes"],
            raw_response=f"[MOCK MODE] Category: {category}",
        )

    def _parse_response(self, response_text: str) -> VisionAnalysisResult:
        """Parse the vision model's response into structured data.

        Attempts to extract JSON from the response, handling cases where
        the model includes extra text around the JSON.
        """
        # Try to find JSON in the response
        response_text = response_text.strip()

        # Remove markdown code blocks if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        response_text = response_text.strip()

        # Try to parse as JSON directly
        try:
            data = json.loads(response_text)
            return VisionAnalysisResult(
                description=data.get("description", ""),
                detected_objects=data.get("detected_objects", []),
                risk_assessment=data.get("risk_assessment", {}),
                scene_attributes=data.get("scene_attributes", {}),
                raw_response=response_text,
            )
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in the response
        start_idx = response_text.find("{")
        end_idx = response_text.rfind("}") + 1

        if start_idx != -1 and end_idx > start_idx:
            json_str = response_text[start_idx:end_idx]
            try:
                data = json.loads(json_str)
                return VisionAnalysisResult(
                    description=data.get("description", ""),
                    detected_objects=data.get("detected_objects", []),
                    risk_assessment=data.get("risk_assessment", {}),
                    scene_attributes=data.get("scene_attributes", {}),
                    raw_response=response_text,
                )
            except json.JSONDecodeError:
                pass

        # If all parsing fails, return a basic result with the raw response
        return VisionAnalysisResult(
            description="Failed to parse structured response",
            detected_objects=[],
            risk_assessment={
                "risk_score": 50,
                "risk_level": "medium",
                "reasoning": "Parsing failed",
            },
            scene_attributes={},
            raw_response=response_text,
        )

    async def analyze_image(
        self,
        image_path: Path,
        use_cache: bool = True,
    ) -> VisionAnalysisResult:
        """Analyze a single image using NVIDIA vision model.

        Args:
            image_path: Path to the image file to analyze.
            use_cache: Whether to use cached results if available.

        Returns:
            VisionAnalysisResult with structured analysis data.

        Raises:
            FileNotFoundError: If the image file doesn't exist.
            ValueError: If the image format is not supported.
            httpx.HTTPError: If the API request fails after retries.
        """
        # Validate image path
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        if image_path.suffix.lower() not in SUPPORTED_IMAGE_FORMATS:
            raise ValueError(
                f"Unsupported image format: {image_path.suffix}. "
                f"Supported: {SUPPORTED_IMAGE_FORMATS}"
            )

        # Check cache
        cache_key = self._get_cache_key(image_path)
        if use_cache:
            cached = self._get_cached_result(cache_key)
            if cached is not None:
                return cached

        # Use mock mode if enabled
        if self.config.mock_mode:
            result = self._generate_mock_result(image_path)
            if use_cache:
                self._save_to_cache(cache_key, result)
            return result

        # Encode image to base64
        image_b64 = self._encode_image_to_base64(image_path)
        media_type = self._get_image_media_type(image_path)

        # Build API request
        prompt = self._build_analysis_prompt()

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{image_b64}",
                        },
                    },
                ],
            }
        ]

        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": 2048,
            "temperature": 0.1,  # Low temperature for consistent structured output
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Send request with retry
        result = await self._send_api_request_with_retry(payload, headers)

        # Cache the result
        if use_cache:
            self._save_to_cache(cache_key, result)

        return result

    async def _send_api_request_with_retry(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> VisionAnalysisResult:
        """Send API request with retry logic for transient failures.

        Args:
            payload: JSON payload for the API request.
            headers: HTTP headers including authorization.

        Returns:
            Parsed VisionAnalysisResult from the API response.

        Raises:
            httpx.HTTPStatusError: For non-retryable HTTP errors.
            RuntimeError: If all retries are exhausted.
        """
        client = await self._get_client()
        last_error: Exception | None = None

        for attempt in range(self.config.max_retries):
            try:
                response = await client.post(
                    f"{self.config.endpoint}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()

                response_data = response.json()
                response_text = response_data["choices"][0]["message"]["content"]
                return self._parse_response(response_text)

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code >= 500:
                    # Server error, retry with backoff
                    delay = min(2**attempt, 30)
                    await asyncio.sleep(delay)
                else:
                    # Client error, don't retry
                    raise

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                delay = min(2**attempt, 30)
                await asyncio.sleep(delay)

        # All retries exhausted
        if last_error:
            raise last_error
        raise RuntimeError("Analysis failed after all retries")

    async def analyze_batch(
        self,
        image_paths: Sequence[Path],
        max_concurrency: int = 5,
        use_cache: bool = True,
    ) -> list[VisionAnalysisResult]:
        """Analyze multiple images concurrently.

        Args:
            image_paths: List of paths to image files.
            max_concurrency: Maximum concurrent API requests.
            use_cache: Whether to use cached results.

        Returns:
            List of VisionAnalysisResult in the same order as input paths.
        """
        semaphore = asyncio.Semaphore(max_concurrency)

        async def analyze_with_semaphore(path: Path) -> VisionAnalysisResult:
            async with semaphore:
                return await self.analyze_image(path, use_cache=use_cache)

        tasks = [analyze_with_semaphore(path) for path in image_paths]
        return await asyncio.gather(*tasks)

    async def __aenter__(self) -> NVIDIAVisionAnalyzer:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
