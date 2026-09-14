"""Scene baseline service for CLIP-based anomaly detection.

This service manages scene embedding baselines per camera using Redis, enabling
detection of visual anomalies by comparing current frame embeddings against
a rolling average of "normal" scene embeddings.

Features:
    - Store and retrieve per-camera baseline embeddings in Redis
    - Rolling average baseline updates with configurable decay
    - Anomaly score computation via CLIP service
    - Automatic baseline refresh during low-activity hours

Usage:
    from backend.services.scene_baseline import SceneBaselineService, get_scene_baseline_service

    service = get_scene_baseline_service(redis_client, clip_client)

    # Update baseline with a new normal frame
    await service.update_baseline("camera_1", embedding)

    # Check anomaly score for current frame
    score, similarity = await service.get_anomaly_score("camera_1", current_image)

Redis Keys:
    scene_baseline:{camera_id}:embedding  -> JSON array of 768 floats
    scene_baseline:{camera_id}:count      -> Number of samples in baseline
    scene_baseline:{camera_id}:updated    -> ISO timestamp of last update
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL import Image

    from backend.core.redis import RedisClient
    from backend.services.clip_client import CLIPClient

logger = get_logger(__name__)

# CLIP ViT-L embedding dimension
EMBEDDING_DIMENSION = 768

# Default TTL for baseline data (7 days)
DEFAULT_BASELINE_TTL_SECONDS = 7 * 24 * 60 * 60

# Default decay factor for exponential moving average
# Higher values weight recent samples more heavily
DEFAULT_DECAY_FACTOR = 0.1

# Minimum samples before baseline is considered reliable
MIN_SAMPLES_FOR_RELIABLE_BASELINE = 5

# Redis key prefixes
BASELINE_KEY_PREFIX = "scene_baseline"


class SceneBaselineError(Exception):
    """Base exception for scene baseline operations."""

    pass


class BaselineNotFoundError(SceneBaselineError):
    """Raised when no baseline exists for a camera."""

    pass


class InvalidEmbeddingError(SceneBaselineError):
    """Raised when an embedding has invalid dimensions."""

    pass


class SceneBaselineService:
    """Service for managing scene embedding baselines per camera.

    This service stores and manages CLIP embeddings representing "normal"
    scene appearances for each camera. It uses exponential moving average
    to update baselines incrementally and provides anomaly detection by
    comparing new frames against stored baselines.

    Attributes:
        redis_client: Redis client for storing baselines
        clip_client: CLIP client for computing embeddings and anomaly scores
        decay_factor: EMA decay factor (0 < decay <= 1)
        baseline_ttl: TTL in seconds for baseline data in Redis
    """

    def __init__(
        self,
        redis_client: RedisClient,
        clip_client: CLIPClient | None = None,
        decay_factor: float = DEFAULT_DECAY_FACTOR,
        baseline_ttl: int = DEFAULT_BASELINE_TTL_SECONDS,
    ) -> None:
        """Initialize the scene baseline service.

        Args:
            redis_client: Redis client for storing baselines
            clip_client: Optional CLIP client for embedding and anomaly computation.
                        If not provided, get_anomaly_score() will raise an error.
            decay_factor: Exponential decay factor (0 < decay <= 1).
                         Higher values weight recent samples more heavily.
            baseline_ttl: TTL in seconds for baseline data (default: 7 days)

        Raises:
            ValueError: If decay_factor is not in (0, 1]
        """
        if not 0 < decay_factor <= 1:
            raise ValueError("decay_factor must be between 0 (exclusive) and 1 (inclusive)")

        self._redis = redis_client
        self._clip = clip_client
        self._decay_factor = decay_factor
        self._baseline_ttl = baseline_ttl

        logger.info(f"SceneBaselineService initialized: decay={decay_factor}, ttl={baseline_ttl}s")

    def _get_embedding_key(self, camera_id: str) -> str:
        """Get Redis key for camera embedding."""
        return f"{BASELINE_KEY_PREFIX}:{camera_id}:embedding"

    def _get_count_key(self, camera_id: str) -> str:
        """Get Redis key for sample count."""
        return f"{BASELINE_KEY_PREFIX}:{camera_id}:count"

    def _get_updated_key(self, camera_id: str) -> str:
        """Get Redis key for last update timestamp."""
        return f"{BASELINE_KEY_PREFIX}:{camera_id}:updated"

    async def get_baseline(self, camera_id: str) -> tuple[list[float], int, datetime | None]:
        """Get the current baseline embedding for a camera.

        Uses Redis pipelining to fetch all three keys in a single round trip,
        reducing network latency from 3 RTTs to 1 RTT.

        Args:
            camera_id: Camera identifier

        Returns:
            Tuple of (embedding, sample_count, last_updated):
            - embedding: 768-dimensional baseline embedding
            - sample_count: Number of samples in the baseline
            - last_updated: Timestamp of last update (None if never updated)

        Raises:
            BaselineNotFoundError: If no baseline exists for the camera
        """
        embedding_key = self._get_embedding_key(camera_id)
        count_key = self._get_count_key(camera_id)
        updated_key = self._get_updated_key(camera_id)

        # Use pipeline to fetch all three keys in a single round trip
        # This reduces network latency from 3 RTTs to 1 RTT
        if self._redis._client is None:
            raise SceneBaselineError("Redis client is not connected")
        pipe = self._redis._client.pipeline()
        pipe.get(embedding_key)
        pipe.get(count_key)
        pipe.get(updated_key)
        results = await pipe.execute()

        embedding_data, count_data, updated_data = results

        if embedding_data is None:
            raise BaselineNotFoundError(f"No baseline found for camera: {camera_id}")

        # Parse embedding
        if isinstance(embedding_data, str):
            embedding = json.loads(embedding_data)
        else:
            embedding = embedding_data

        # Parse count
        sample_count = int(count_data) if count_data else 1

        # Parse timestamp
        last_updated = None
        if updated_data:
            try:
                last_updated = datetime.fromisoformat(updated_data)
            except (TypeError, ValueError):
                last_updated = None

        return embedding, sample_count, last_updated

    async def has_baseline(self, camera_id: str) -> bool:
        """Check if a baseline exists for a camera.

        Args:
            camera_id: Camera identifier

        Returns:
            True if baseline exists, False otherwise
        """
        embedding_key = self._get_embedding_key(camera_id)
        exists = await self._redis.exists(embedding_key)
        return exists > 0

    async def get_baseline_info(self, camera_id: str) -> dict:
        """Get metadata about a camera's baseline without the full embedding.

        Args:
            camera_id: Camera identifier

        Returns:
            Dictionary with baseline metadata:
            - exists: Whether baseline exists
            - sample_count: Number of samples in baseline
            - last_updated: ISO timestamp of last update
            - is_reliable: Whether baseline has enough samples

        """
        try:
            _, sample_count, last_updated = await self.get_baseline(camera_id)
            return {
                "exists": True,
                "sample_count": sample_count,
                "last_updated": last_updated.isoformat() if last_updated else None,
                "is_reliable": sample_count >= MIN_SAMPLES_FOR_RELIABLE_BASELINE,
            }
        except BaselineNotFoundError:
            return {
                "exists": False,
                "sample_count": 0,
                "last_updated": None,
                "is_reliable": False,
            }

    async def update_baseline(
        self,
        camera_id: str,
        embedding: list[float],
    ) -> tuple[list[float], int]:
        """Update the baseline embedding for a camera.

        Uses exponential moving average to incorporate the new embedding:
        new_baseline = decay * old_baseline + (1 - decay) * new_embedding

        If no baseline exists, the new embedding becomes the baseline.

        Args:
            camera_id: Camera identifier
            embedding: 768-dimensional CLIP embedding from a "normal" frame

        Returns:
            Tuple of (updated_baseline, new_sample_count)

        Raises:
            InvalidEmbeddingError: If embedding has wrong dimension
        """
        # Validate embedding dimension
        if len(embedding) != EMBEDDING_DIMENSION:
            raise InvalidEmbeddingError(
                f"Embedding must have {EMBEDDING_DIMENSION} dimensions, got {len(embedding)}"
            )

        embedding_key = self._get_embedding_key(camera_id)
        count_key = self._get_count_key(camera_id)
        updated_key = self._get_updated_key(camera_id)

        try:
            old_baseline, old_count, _ = await self.get_baseline(camera_id)

            # Compute EMA update
            new_baseline = [
                self._decay_factor * old_val + (1 - self._decay_factor) * new_val
                for old_val, new_val in zip(old_baseline, embedding, strict=True)
            ]
            new_count = old_count + 1

        except BaselineNotFoundError:
            # First sample becomes the baseline
            new_baseline = embedding
            new_count = 1

        # Normalize the baseline embedding to unit length
        norm = sum(x * x for x in new_baseline) ** 0.5
        if norm > 0:
            new_baseline = [x / norm for x in new_baseline]

        # Store updated baseline using pipeline for atomic operation
        # This reduces network latency from 3 RTTs to 1 RTT
        if self._redis._client is None:
            raise SceneBaselineError("Redis client is not connected")
        now = datetime.now(UTC)
        pipe = self._redis._client.pipeline()
        pipe.setex(embedding_key, self._baseline_ttl, json.dumps(new_baseline))
        pipe.setex(count_key, self._baseline_ttl, str(new_count))
        pipe.setex(updated_key, self._baseline_ttl, now.isoformat())
        await pipe.execute()

        logger.debug(f"Updated baseline for camera={camera_id}: count={new_count}")

        return new_baseline, new_count

    async def set_baseline(
        self,
        camera_id: str,
        embedding: list[float],
        sample_count: int = 1,
    ) -> None:
        """Set the baseline embedding for a camera (replaces existing).

        Unlike update_baseline(), this method replaces the entire baseline
        rather than using EMA. Use this for:
        - Initial baseline setup from a known-good image set
        - Resetting a baseline after significant scene changes
        - Importing baselines from external sources

        Args:
            camera_id: Camera identifier
            embedding: 768-dimensional CLIP embedding
            sample_count: Number of samples this baseline represents (default: 1)

        Raises:
            InvalidEmbeddingError: If embedding has wrong dimension
        """
        # Validate embedding dimension
        if len(embedding) != EMBEDDING_DIMENSION:
            raise InvalidEmbeddingError(
                f"Embedding must have {EMBEDDING_DIMENSION} dimensions, got {len(embedding)}"
            )

        embedding_key = self._get_embedding_key(camera_id)
        count_key = self._get_count_key(camera_id)
        updated_key = self._get_updated_key(camera_id)

        # Normalize the embedding to unit length
        norm = sum(x * x for x in embedding) ** 0.5
        if norm > 0:
            embedding = [x / norm for x in embedding]

        # Use pipeline to set all three keys in a single round trip
        # This reduces network latency from 3 RTTs to 1 RTT
        if self._redis._client is None:
            raise SceneBaselineError("Redis client is not connected")
        now = datetime.now(UTC)
        pipe = self._redis._client.pipeline()
        pipe.setex(embedding_key, self._baseline_ttl, json.dumps(embedding))
        pipe.setex(count_key, self._baseline_ttl, str(sample_count))
        pipe.setex(updated_key, self._baseline_ttl, now.isoformat())
        await pipe.execute()

        logger.info(f"Set baseline for camera={camera_id}: count={sample_count}")

    async def delete_baseline(self, camera_id: str) -> bool:
        """Delete the baseline for a camera.

        Args:
            camera_id: Camera identifier

        Returns:
            True if baseline was deleted, False if it didn't exist
        """
        embedding_key = self._get_embedding_key(camera_id)
        count_key = self._get_count_key(camera_id)
        updated_key = self._get_updated_key(camera_id)

        deleted = await self._redis.delete(embedding_key, count_key, updated_key)
        if deleted > 0:
            logger.info(f"Deleted baseline for camera={camera_id}")
            return True
        return False

    async def get_anomaly_score(
        self,
        camera_id: str,
        image: Image.Image,
    ) -> tuple[float, float]:
        """Compute anomaly score for an image against the camera's baseline.

        Uses the CLIP service to compute how different the current frame is
        from the camera's stored baseline embedding.

        Args:
            camera_id: Camera identifier
            image: PIL Image to analyze

        Returns:
            Tuple of (anomaly_score, similarity):
            - anomaly_score: Value in [0, 1] where higher = more anomalous
            - similarity: Cosine similarity to baseline in [-1, 1]

        Raises:
            BaselineNotFoundError: If no baseline exists for the camera
            SceneBaselineError: If CLIP client is not configured
            CLIPUnavailableError: If CLIP service is unavailable
        """
        if self._clip is None:
            raise SceneBaselineError("CLIP client not configured. Cannot compute anomaly score.")

        # Get baseline
        baseline_embedding, sample_count, _ = await self.get_baseline(camera_id)

        # Warn if baseline is not reliable
        if sample_count < MIN_SAMPLES_FOR_RELIABLE_BASELINE:
            logger.warning(
                f"Baseline for camera={camera_id} has only {sample_count} samples "
                f"(< {MIN_SAMPLES_FOR_RELIABLE_BASELINE}). Anomaly score may be unreliable."
            )

        # Compute anomaly score via CLIP service
        anomaly_score, similarity = await self._clip.anomaly_score(image, baseline_embedding)

        logger.debug(
            f"Anomaly score for camera={camera_id}: score={anomaly_score:.3f}, "
            f"similarity={similarity:.3f}"
        )

        return anomaly_score, similarity

    async def update_baseline_from_image(
        self,
        camera_id: str,
        image: Image.Image,
    ) -> tuple[list[float], int]:
        """Update baseline using a "normal" image.

        Convenience method that extracts the CLIP embedding from an image
        and updates the camera's baseline.

        Args:
            camera_id: Camera identifier
            image: PIL Image representing a "normal" scene

        Returns:
            Tuple of (updated_baseline, new_sample_count)

        Raises:
            SceneBaselineError: If CLIP client is not configured
            CLIPUnavailableError: If CLIP service is unavailable
        """
        if self._clip is None:
            raise SceneBaselineError(
                "CLIP client not configured. Cannot extract embedding from image."
            )

        # Extract embedding
        embedding = await self._clip.embed(image)

        # Update baseline
        return await self.update_baseline(camera_id, embedding)


# Global singleton
_scene_baseline_service: SceneBaselineService | None = None


def get_scene_baseline_service(
    redis_client: RedisClient,
    clip_client: CLIPClient | None = None,
) -> SceneBaselineService:
    """Get or create the global scene baseline service singleton.

    Args:
        redis_client: Redis client for storing baselines
        clip_client: Optional CLIP client for embedding/anomaly computation

    Returns:
        The global SceneBaselineService instance
    """
    global _scene_baseline_service  # noqa: PLW0603
    if _scene_baseline_service is None:
        _scene_baseline_service = SceneBaselineService(redis_client, clip_client)
    return _scene_baseline_service


def reset_scene_baseline_service() -> None:
    """Reset the global scene baseline service singleton.

    Useful for testing to ensure a clean state.
    """
    global _scene_baseline_service  # noqa: PLW0603
    _scene_baseline_service = None
