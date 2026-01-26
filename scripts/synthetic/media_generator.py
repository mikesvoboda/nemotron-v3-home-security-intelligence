# ABOUTME: Handles media generation via NVIDIA's inference API for the synthetic data generation system.
# ABOUTME: Supports Veo 3.1 for video generation and Gemini for image generation with async polling.
"""
Media Generator for Synthetic Data Generation System.

This module provides API interactions with NVIDIA's inference endpoint for generating
synthetic security camera footage using Veo 3.1 (video) and Gemini (images).

Usage:
    from scripts.synthetic.media_generator import MediaGenerator

    generator = MediaGenerator()

    # Generate an image
    success = await generator.generate_image(
        prompt="Security camera view of front porch at night",
        output_path=Path("output/image.png")
    )

    # Generate a video
    success = await generator.generate_video(
        prompt="Person walking up driveway at dusk",
        output_path=Path("output/video.mp4")
    )
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import httpx

# Configure logging
logger = logging.getLogger(__name__)


class MediaStatus(Enum):
    """Status of a media generation job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class GenerationResult:
    """Result of a media generation operation."""

    success: bool
    status: MediaStatus
    output_path: Path | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MediaGeneratorError(Exception):
    """Base exception for media generator errors."""

    pass


class APIKeyNotFoundError(MediaGeneratorError):
    """Raised when the API key is not found in environment variables."""

    pass


class GenerationTimeoutError(MediaGeneratorError):
    """Raised when video generation polling times out."""

    pass


class MediaGenerator:
    """
    Generates synthetic media using NVIDIA's inference API.

    Supports:
    - Video generation via Veo 3.1
    - Image generation via Gemini

    All processing is done through NVIDIA's inference API endpoint.
    """

    # API Configuration
    BASE_URL = "https://inference-api.nvidia.com"
    VIDEO_MODEL = "gcp/google/veo-3.1-generate-001"
    IMAGE_MODEL = "gcp/google/gemini-3-pro-image-preview"

    # Default settings
    DEFAULT_VIDEO_DURATION = 8  # seconds
    DEFAULT_VIDEO_RESOLUTION = "720p"
    DEFAULT_IMAGE_RESOLUTION = "1080p"
    DEFAULT_ASPECT_RATIO = "16:9"

    # Polling settings
    DEFAULT_POLL_INTERVAL = 10  # seconds
    DEFAULT_TIMEOUT = 300  # seconds (5 minutes)

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        poll_interval: int | None = None,
        timeout: int | None = None,
    ):
        """
        Initialize the MediaGenerator.

        Args:
            api_key: NVIDIA API key. If not provided, reads from NVIDIA_API_KEY or NVAPIKEY env vars.
            base_url: Override the default API base URL.
            poll_interval: Override the default poll interval in seconds.
            timeout: Override the default timeout in seconds.
        """
        self._api_key = api_key
        self.base_url = base_url or self.BASE_URL
        self.poll_interval = poll_interval or self.DEFAULT_POLL_INTERVAL
        self.timeout = timeout or self.DEFAULT_TIMEOUT

    @property
    def api_key(self) -> str:
        """Get the API key, reading from environment if not set."""
        if self._api_key:
            return self._api_key

        api_key = os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVAPIKEY")
        if not api_key:
            raise APIKeyNotFoundError(
                "NVIDIA API key not found. Set NVIDIA_API_KEY or NVAPIKEY environment variable, "
                "or pass api_key to MediaGenerator constructor."
            )
        return api_key

    def _get_headers(self) -> dict[str, str]:
        """Get the HTTP headers for API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def generate_image(
        self,
        prompt: str,
        output_path: Path,
        resolution: str | None = None,
        aspect_ratio: str | None = None,
    ) -> bool:
        """
        Generate an image using Gemini via NVIDIA's inference API.

        Args:
            prompt: Text prompt describing the image to generate.
            output_path: Path where the generated image will be saved.
            resolution: Image resolution (default: 1080p).
            aspect_ratio: Aspect ratio (default: 16:9).

        Returns:
            True if generation was successful, False otherwise.
        """
        resolution = resolution or self.DEFAULT_IMAGE_RESOLUTION
        aspect_ratio = aspect_ratio or self.DEFAULT_ASPECT_RATIO

        logger.info(f"Generating image with prompt: {prompt[:100]}...")

        # Prepare request payloads for different API formats
        api_formats: list[dict[str, Any]] = [
            # Format 1: Simple image generation endpoint
            {
                "url": f"{self.base_url}/v1/images/generations",
                "json": {
                    "model": self.IMAGE_MODEL,
                    "prompt": prompt,
                    "n": 1,
                    "size": resolution,
                    "response_format": "b64_json",
                },
            },
            # Format 2: Chat completions with image generation
            {
                "url": f"{self.base_url}/v1/chat/completions",
                "json": {
                    "model": self.IMAGE_MODEL,
                    "messages": [
                        {
                            "role": "user",
                            "content": f"Generate an image: {prompt}",
                        }
                    ],
                    "max_tokens": 4096,
                },
            },
            # Format 3: Direct model endpoint
            {
                "url": f"{self.base_url}/v1/models/{self.IMAGE_MODEL}/generate",
                "json": {
                    "prompt": prompt,
                    "resolution": resolution,
                    "aspect_ratio": aspect_ratio,
                },
            },
        ]

        async with httpx.AsyncClient(timeout=120.0) as client:
            for i, api_format in enumerate(api_formats, 1):
                logger.debug(f"Trying image API format {i}/{len(api_formats)}...")
                try:
                    response = await client.post(
                        api_format["url"],
                        json=api_format["json"],
                        headers=self._get_headers(),
                    )

                    if response.status_code == 200:
                        logger.info(f"Image generation successful with format {i}")
                        return await self._save_image_response(
                            response.json(), output_path
                        )
                    else:
                        logger.debug(
                            f"Format {i} returned status {response.status_code}: "
                            f"{response.text[:200]}"
                        )

                except httpx.RequestError as e:
                    logger.debug(f"Format {i} failed with error: {e}")

        logger.error("All image generation API formats failed")
        return False

    async def _save_image_response(
        self, response: dict[str, Any], output_path: Path
    ) -> bool:
        """
        Extract and save image data from API response.

        Args:
            response: API response containing image data.
            output_path: Path to save the image.

        Returns:
            True if successful, False otherwise.
        """
        image_data = self._extract_image_data(response)
        if image_data is None:
            logger.error("Could not extract image data from response")
            logger.debug(f"Response structure: {list(response.keys())}")
            return False

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write image data
        output_path.write_bytes(image_data)
        logger.info(f"Image saved to: {output_path}")
        return True

    def _extract_image_data(self, response: dict[str, Any]) -> bytes | None:
        """
        Extract image data from various API response formats.

        Args:
            response: API response dict.

        Returns:
            Raw image bytes, or None if extraction failed.
        """
        # Format 1: OpenAI-style data array
        if "data" in response and isinstance(response["data"], list):
            for item in response["data"]:
                if "b64_json" in item:
                    return base64.b64decode(item["b64_json"])
                if "url" in item:
                    # Would need to fetch URL, but prefer b64 for simplicity
                    logger.warning("URL response format not yet supported")

        # Format 2: Direct image field
        if "image" in response:
            image_data = response["image"]
            if isinstance(image_data, str):
                # Check for data URI
                if image_data.startswith("data:image"):
                    _, base64_data = image_data.split(",", 1)
                    return base64.b64decode(base64_data)
                else:
                    return base64.b64decode(image_data)

        # Format 3: Nested in choices (chat completion style)
        if "choices" in response:
            for choice in response["choices"]:
                message = choice.get("message", {})
                content = message.get("content", "")
                # Check for base64 image in content
                if isinstance(content, str) and "data:image" in content:
                    import re

                    match = re.search(
                        r"data:image/[^;]+;base64,([A-Za-z0-9+/=]+)", content
                    )
                    if match:
                        return base64.b64decode(match.group(1))

        # Format 4: Predictions array (Vertex AI style)
        if "predictions" in response:
            for pred in response["predictions"]:
                if "bytesBase64Encoded" in pred:
                    return base64.b64decode(pred["bytesBase64Encoded"])
                if "image" in pred:
                    return base64.b64decode(pred["image"])

        return None

    async def generate_video(
        self,
        prompt: str,
        output_path: Path,
        duration: int | None = None,
        resolution: str | None = None,
        aspect_ratio: str | None = None,
    ) -> bool:
        """
        Generate a video using Veo 3.1 via NVIDIA's inference API.

        This method handles the full lifecycle:
        1. Submit video generation request
        2. Poll for completion
        3. Download and save the video

        Args:
            prompt: Text prompt describing the video to generate.
            output_path: Path where the generated video will be saved.
            duration: Video duration in seconds (default: 8, max: 8).
            resolution: Video resolution (default: 720p).
            aspect_ratio: Aspect ratio (default: 16:9).

        Returns:
            True if generation was successful, False otherwise.
        """
        duration = min(duration or self.DEFAULT_VIDEO_DURATION, 8)  # Max 8 seconds
        resolution = resolution or self.DEFAULT_VIDEO_RESOLUTION
        aspect_ratio = aspect_ratio or self.DEFAULT_ASPECT_RATIO

        logger.info(f"Generating {duration}s video with prompt: {prompt[:100]}...")

        # Try different API formats
        api_formats: list[dict[str, Any]] = [
            # Format 1: Simple video generation endpoint
            {
                "url": f"{self.base_url}/v1/video/generations",
                "json": {
                    "model": self.VIDEO_MODEL,
                    "prompt": prompt,
                    "seconds": str(duration),
                    "resolution": resolution,
                    "aspect_ratio": aspect_ratio,
                },
            },
            # Format 2: Async generation with job ID
            {
                "url": f"{self.base_url}/v1/videos",
                "json": {
                    "model": self.VIDEO_MODEL,
                    "prompt": prompt,
                    "duration_seconds": duration,
                    "resolution": resolution,
                    "aspect_ratio": aspect_ratio,
                },
            },
            # Format 3: Direct model endpoint
            {
                "url": f"{self.base_url}/v1/models/{self.VIDEO_MODEL}/generate",
                "json": {
                    "prompt": prompt,
                    "duration_seconds": duration,
                    "resolution": resolution,
                    "aspect_ratio": aspect_ratio,
                },
            },
            # Format 4: Vertex AI style
            {
                "url": f"{self.base_url}/v1/video/generate",
                "json": {
                    "model": self.VIDEO_MODEL,
                    "instances": [{"prompt": prompt}],
                    "parameters": {
                        "durationSeconds": duration,
                        "resolution": resolution,
                        "aspectRatio": aspect_ratio,
                        "sampleCount": 1,
                    },
                },
            },
        ]

        async with httpx.AsyncClient(timeout=300.0) as client:
            for i, api_format in enumerate(api_formats, 1):
                logger.debug(f"Trying video API format {i}/{len(api_formats)}...")
                try:
                    response = await client.post(
                        api_format["url"],
                        json=api_format["json"],
                        headers=self._get_headers(),
                    )

                    if response.status_code == 200:
                        logger.info(f"Video request successful with format {i}")
                        response_data = response.json()

                        # Check if this is a synchronous response with video data
                        video_data = self._extract_video_data(response_data)
                        if video_data:
                            return self._save_video_data(video_data, output_path)

                        # Check if this is an async job that needs polling
                        video_id = self._extract_video_id(response_data)
                        if video_id:
                            logger.info(f"Video job submitted: {video_id}")
                            return await self._poll_and_download(
                                video_id, output_path
                            )

                        logger.error(
                            "Response successful but no video data or job ID found"
                        )
                        logger.debug(f"Response: {response_data}")

                    elif response.status_code == 202:
                        # Accepted - async job
                        response_data = response.json()
                        video_id = self._extract_video_id(response_data)
                        if video_id:
                            logger.info(f"Video job accepted: {video_id}")
                            return await self._poll_and_download(
                                video_id, output_path
                            )
                    else:
                        logger.debug(
                            f"Format {i} returned status {response.status_code}: "
                            f"{response.text[:200]}"
                        )

                except httpx.RequestError as e:
                    logger.debug(f"Format {i} failed with error: {e}")

        logger.error("All video generation API formats failed")
        return False

    def _extract_video_id(self, response: dict[str, Any]) -> str | None:
        """Extract video job ID from API response."""
        # Common field names for job/video IDs
        for field_name in ["id", "video_id", "job_id", "generation_id", "name"]:
            if field_name in response:
                return str(response[field_name])

        # Nested in data
        if "data" in response and isinstance(response["data"], dict):
            return self._extract_video_id(response["data"])

        return None

    def _extract_video_data(self, response: dict[str, Any]) -> bytes | None:
        """
        Extract video data from various API response formats.

        Args:
            response: API response dict.

        Returns:
            Raw video bytes, or None if not found.
        """
        # Format 1: Direct base64 video
        if "video" in response:
            video_data = response["video"]
            if isinstance(video_data, str):
                if video_data.startswith("data:video"):
                    _, base64_data = video_data.split(",", 1)
                    return base64.b64decode(base64_data)
                else:
                    return base64.b64decode(video_data)

        # Format 2: Nested in data array
        if "data" in response and isinstance(response["data"], list):
            for item in response["data"]:
                if "video" in item:
                    return base64.b64decode(item["video"])
                if "b64_json" in item:
                    return base64.b64decode(item["b64_json"])

        # Format 3: Nested in predictions
        if "predictions" in response:
            for pred in response["predictions"]:
                if "video" in pred:
                    return base64.b64decode(pred["video"])
                if "bytesBase64Encoded" in pred:
                    return base64.b64decode(pred["bytesBase64Encoded"])

        # Format 4: OpenAI-style choices
        if "choices" in response:
            for choice in response["choices"]:
                message = choice.get("message", {})
                content = message.get("content", "")
                if isinstance(content, str) and "data:video" in content:
                    import re

                    match = re.search(
                        r"data:video/[^;]+;base64,([A-Za-z0-9+/=]+)", content
                    )
                    if match:
                        return base64.b64decode(match.group(1))

        return None

    def _save_video_data(self, video_data: bytes, output_path: Path) -> bool:
        """Save video data to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(video_data)
        logger.info(f"Video saved to: {output_path}")
        return True

    async def _poll_and_download(
        self,
        video_id: str,
        output_path: Path,
    ) -> bool:
        """
        Poll for video completion and download when ready.

        Args:
            video_id: Video job ID to poll.
            output_path: Path to save the completed video.

        Returns:
            True if successful, False otherwise.
        """
        try:
            result = await self.poll_for_completion(video_id, self.timeout)
        except GenerationTimeoutError as e:
            logger.error(str(e))
            return False

        if result.get("status") != "completed":
            logger.error(f"Video generation failed: {result.get('error', 'Unknown error')}")
            return False

        return await self.download_media(video_id, output_path)

    async def poll_for_completion(
        self,
        video_id: str,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """
        Poll the API for video generation completion.

        Args:
            video_id: The video job ID to poll.
            timeout: Maximum time to wait in seconds.

        Returns:
            Dict with status and result data.

        Raises:
            GenerationTimeoutError: If polling times out.
        """
        timeout = timeout or self.timeout
        start_time = time.time()
        poll_count = 0

        logger.info(f"Polling for video {video_id} completion (timeout: {timeout}s)...")

        async with httpx.AsyncClient(timeout=30.0) as client:
            while (time.time() - start_time) < timeout:
                poll_count += 1
                elapsed = int(time.time() - start_time)
                logger.info(
                    f"Poll #{poll_count} for video {video_id} "
                    f"(elapsed: {elapsed}s / {timeout}s)"
                )

                try:
                    # Try different status endpoint formats
                    status_endpoints = [
                        f"{self.base_url}/v1/videos/{video_id}",
                        f"{self.base_url}/v1/video/generations/{video_id}",
                        f"{self.base_url}/v1/jobs/{video_id}",
                    ]

                    for endpoint in status_endpoints:
                        response = await client.get(
                            endpoint,
                            headers=self._get_headers(),
                        )

                        if response.status_code == 200:
                            data = response.json()
                            status = self._extract_status(data)

                            logger.debug(f"Status: {status}")

                            if status == MediaStatus.COMPLETED:
                                logger.info(f"Video {video_id} generation completed!")
                                return {"status": "completed", "data": data}

                            if status == MediaStatus.FAILED:
                                error_msg = data.get("error", data.get("message", "Unknown error"))
                                logger.error(f"Video generation failed: {error_msg}")
                                return {"status": "failed", "error": error_msg}

                            # Still processing, break out of endpoint loop
                            break

                except httpx.RequestError as e:
                    logger.warning(f"Poll request failed: {e}")

                # Wait before next poll
                await asyncio.sleep(self.poll_interval)

        raise GenerationTimeoutError(
            f"Video generation timed out after {timeout} seconds "
            f"({poll_count} polls)"
        )

    def _extract_status(self, response: dict[str, Any]) -> MediaStatus:
        """Extract status from API response."""
        status_str = response.get("status", response.get("state", "")).lower()

        status_mapping = {
            "pending": MediaStatus.PENDING,
            "queued": MediaStatus.PENDING,
            "processing": MediaStatus.PROCESSING,
            "running": MediaStatus.PROCESSING,
            "in_progress": MediaStatus.PROCESSING,
            "completed": MediaStatus.COMPLETED,
            "succeeded": MediaStatus.COMPLETED,
            "success": MediaStatus.COMPLETED,
            "done": MediaStatus.COMPLETED,
            "failed": MediaStatus.FAILED,
            "error": MediaStatus.FAILED,
            "cancelled": MediaStatus.FAILED,
        }

        return status_mapping.get(status_str, MediaStatus.PENDING)

    async def download_media(
        self,
        video_id: str,
        output_path: Path,
    ) -> bool:
        """
        Download completed media from the API.

        Args:
            video_id: The video job ID.
            output_path: Path to save the downloaded media.

        Returns:
            True if download was successful, False otherwise.
        """
        logger.info(f"Downloading video {video_id}...")

        async with httpx.AsyncClient(timeout=120.0) as client:
            # Try different download endpoint formats
            download_endpoints = [
                (f"{self.base_url}/v1/videos/{video_id}/content", "stream"),
                (f"{self.base_url}/v1/videos/{video_id}/download", "stream"),
                (f"{self.base_url}/v1/videos/{video_id}", "json"),
            ]

            for endpoint, response_type in download_endpoints:
                try:
                    response = await client.get(
                        endpoint,
                        headers=self._get_headers(),
                    )

                    if response.status_code == 200:
                        video_data: bytes | None = None
                        if response_type == "stream":
                            # Direct binary content
                            video_data = response.content
                        else:
                            # JSON with base64 data
                            data = response.json()
                            video_data = self._extract_video_data(data)

                        if video_data is None:
                            continue

                        # Save the video
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        output_path.write_bytes(video_data)
                        logger.info(
                            f"Video downloaded successfully: {output_path} "
                            f"({len(video_data)} bytes)"
                        )
                        return True

                except httpx.RequestError as e:
                    logger.debug(f"Download from {endpoint} failed: {e}")

        logger.error(f"Failed to download video {video_id}")
        return False


# Synchronous wrapper functions for convenience
def generate_image_sync(
    prompt: str,
    output_path: Path,
    **kwargs: Any,
) -> bool:
    """
    Synchronous wrapper for generate_image.

    Args:
        prompt: Text prompt describing the image.
        output_path: Path to save the generated image.
        **kwargs: Additional arguments passed to MediaGenerator.

    Returns:
        True if successful, False otherwise.
    """
    generator = MediaGenerator(**kwargs)
    return asyncio.run(generator.generate_image(prompt, output_path))


def generate_video_sync(
    prompt: str,
    output_path: Path,
    **kwargs: Any,
) -> bool:
    """
    Synchronous wrapper for generate_video.

    Args:
        prompt: Text prompt describing the video.
        output_path: Path to save the generated video.
        **kwargs: Additional arguments passed to MediaGenerator.

    Returns:
        True if successful, False otherwise.
    """
    generator = MediaGenerator(**kwargs)
    return asyncio.run(generator.generate_video(prompt, output_path))


if __name__ == "__main__":
    # Simple CLI for testing
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="Generate synthetic media")
    parser.add_argument(
        "--type",
        "-t",
        choices=["image", "video"],
        required=True,
        help="Type of media to generate",
    )
    parser.add_argument(
        "--prompt",
        "-p",
        required=True,
        help="Generation prompt",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        type=Path,
        help="Output file path",
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=int,
        default=8,
        help="Video duration in seconds (max 8)",
    )

    args = parser.parse_args()

    if args.type == "image":
        success = generate_image_sync(args.prompt, args.output)
    else:
        success = generate_video_sync(
            args.prompt,
            args.output,
        )

    sys.exit(0 if success else 1)
