"""Re-identification service for entity matching across cameras.

This module generates person re-ID embeddings and matches them across
camera views. After the full swap (owner ruling, ledger item 20) the ONE
person-vector space is OSNet-AIN x1.0 (512-d, SHA-256-pinned weights from
the models.yml zoo row): ``generate_embedding`` computes with the resident
zoo handle and returns ``(vector, model_id)`` — the belt that lets every
reader know which space the bytes live in (F11).

CLIP-as-re-ID-producer is retired (the ai-clip HTTP seam is gone; CLIP
stays where it is really CLIP's job — scene baseline, threat similarity).
Vehicles have no embedding producer in the shipped mode (B5a): their
identity rides plate match, and a vehicle crop through a person re-ID model
would be noise wearing plausible numbers.

Availability: the producer reads the zoo handle (never triggers a load);
when the weights are not resident it raises ReIDUnavailableError naming the
zoo row — callers answer honestly (enrollment: 5xx; trail legs: unavailable)
instead of storing a stub.

Rate Limiting:
    The service implements concurrency-based rate limiting using asyncio.Semaphore
    to prevent resource exhaustion from too many concurrent requests. This is
    configurable via REID_MAX_CONCURRENT_REQUESTS setting (default: 10).

Redis Storage Pattern:
    Key: entity_embeddings:{model_id}:{date}   (partition = the strong guard)
    Entry: model_id rides inside each payload (the belt)
    TTL: 24 hours (86400 seconds)
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID

import numpy as np

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.core.metrics import (
    observe_reid_match_duration,
    record_cross_camera_handoff,
    record_reid_attempt,
    record_reid_match,
)
from backend.core.vector_provenance import LEGACY_MODEL_ID
from backend.services import osnet_loader
from backend.services.bbox_validation import (
    InvalidBoundingBoxError,
    clamp_bbox_to_image,
    is_valid_bbox,
)

if TYPE_CHECKING:
    from PIL import Image
    from redis.asyncio import Redis

    from backend.services.hybrid_entity_storage import HybridEntityStorage

logger = get_logger(__name__)

# TTL for entity embeddings (24 hours)
EMBEDDING_TTL_SECONDS = 86400

# Default similarity threshold for matching — the OSNet-AIN x1.0 space's
# value (osnet_loader.match_person_embeddings ships 0.7; the CLIP-era 0.85
# would silently drop every legitimate OSNet match). PROVISIONAL: calibrate
# against real household galleries, same note as the face thresholds (D-2).
DEFAULT_SIMILARITY_THRESHOLD = 0.7

# Person-vector embedding dimension — OSNet-AIN x1.0 (ledger item 20: the
# full swap retired CLIP-as-re-ID-producer, so this store's space is the
# resident re-ID weights' 512-d space, not CLIP's 768).
EMBEDDING_DIMENSION = 512

# Regex pattern for Florence-2 location tokens like <loc_71>, <loc_86>, etc.
_LOC_TOKEN_PATTERN = re.compile(r"<loc_\d+>")

# Regex pattern for VQA prefix with query text: VQA>question text
_VQA_PREFIX_PATTERN = re.compile(r"VQA>[^<]*")


def clean_vqa_output(text: str | None) -> str | None:
    """Clean raw Florence-2 VQA output by removing artifacts.

    This function extracts meaningful content from VQA responses by removing
    VQA prefixes and location tokens. Use this when you want to salvage content
    from responses that may contain artifacts (e.g., in format_entity_match).

    Note: R8 S2 deleted `vision_extractor.py` (Florence-2 extraction, legacy
    tier) along with the `validate_and_clean_vqa_output` helper it owned -
    this local cleaner is now the only VQA-artifact scrubber (NEM-3304).

    Florence-2 VQA responses may contain artifacts like:
    - VQA> prefix followed by the query text
    - <loc_N> location tokens (bounding box coordinates)

    This function removes these artifacts to produce clean text suitable
    for human-readable prompt inclusion.

    Args:
        text: Raw VQA output text, possibly containing artifacts

    Returns:
        Cleaned text with artifacts removed, or None if the cleaned text
        is empty or was None/empty to begin with.

    Examples:
        >>> clean_vqa_output("VQA>person wearing<loc_71><loc_86>blue jacket")
        'blue jacket'
        >>> clean_vqa_output("<loc_10><loc_20>backpack")
        'backpack'
        >>> clean_vqa_output("VQA>Is this person carrying anything<loc_1><loc_2>")
        None  # No meaningful content after cleaning
        >>> clean_vqa_output("blue jacket, dark pants")
        'blue jacket, dark pants'  # Clean text unchanged
    """
    if not text:
        return None

    # Remove VQA> prefix and query text
    cleaned = _VQA_PREFIX_PATTERN.sub("", text)

    # Remove all <loc_N> tokens
    cleaned = _LOC_TOKEN_PATTERN.sub("", cleaned)

    # Strip whitespace and clean up any double spaces left behind
    cleaned = " ".join(cleaned.split())

    # Return None if nothing meaningful remains
    if not cleaned or cleaned.isspace():
        return None

    return cleaned


class ReIDUnavailableError(RuntimeError):
    """The re-ID weights are not resident, so no vector can be computed.

    The swap's honesty rule (ledger item 20): a missing producer is an
    AVAILABILITY state, never a zero vector. A stored ``[0.0] * 512`` reads
    as a plausible embedding until someone compares it, so the producer
    refuses loudly and the caller says so — enrollment answers 5xx naming
    the cause, trail legs report "unavailable".
    """


@dataclass(slots=True)
class EntityEmbedding:
    """Embedding data for a detected entity.

    Provenance (F11, ledger item 20): every entry names the weights that
    computed it. The Redis key is partitioned by model_id as the strong
    guard, but the belt travels INSIDE each payload — a row that never
    said who computed it decodes to the sentinel and is untrusted, never
    trusted-with-nothing.

    Attributes:
        entity_type: Type of entity ("person" or "vehicle")
        embedding: 512-dimensional OSNet-AIN x1.0 vector
        camera_id: ID of the camera that captured the entity
        timestamp: When the entity was detected
        detection_id: Unique ID of the detection
        attributes: Additional attributes from vision extraction (e.g., clothing, color)
        model_id: Which weights computed this embedding (or the sentinel)
    """

    entity_type: str
    embedding: list[float]
    camera_id: str
    timestamp: datetime
    detection_id: str
    attributes: dict[str, Any] = field(default_factory=dict)
    model_id: str = LEGACY_MODEL_ID

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the embedding
        """
        return {
            "entity_type": self.entity_type,
            "embedding": self.embedding,
            "camera_id": self.camera_id,
            "timestamp": self.timestamp.isoformat(),
            "detection_id": self.detection_id,
            "attributes": self.attributes,
            "model_id": self.model_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EntityEmbedding:
        """Create from dictionary.

        A payload with no ``model_id`` key predates provenance (or was
        written by a producer that never named itself): it decodes to the
        sentinel, which every comparison reads as untrusted. Defaulting a
        silent gap to the LIVE model would launder old CLIP bytes into the
        OSNet space — the failure F11 exists to prevent.

        Args:
            data: Dictionary with embedding data

        Returns:
            EntityEmbedding instance
        """
        timestamp = data["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        return cls(
            entity_type=data["entity_type"],
            embedding=data["embedding"],
            camera_id=data["camera_id"],
            timestamp=timestamp,
            detection_id=data["detection_id"],
            attributes=data.get("attributes", {}),
            model_id=data.get("model_id") or LEGACY_MODEL_ID,
        )


@dataclass(slots=True)
class EntityMatch:
    """A match result between two entities.

    Attributes:
        entity: The matched entity embedding
        similarity: Cosine similarity score (0-1)
        time_gap_seconds: Time difference in seconds
    """

    entity: EntityEmbedding
    similarity: float
    time_gap_seconds: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary containing all EntityMatch fields for storage,
            including nested entity data via EntityEmbedding.to_dict().
        """
        return {
            "entity": self.entity.to_dict(),
            "similarity": self.similarity,
            "time_gap_seconds": self.time_gap_seconds,
        }


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors.

    Args:
        vec1: First embedding vector
        vec2: Second embedding vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    if len(vec1) != len(vec2):
        raise ValueError(f"Vectors must have same dimension: {len(vec1)} vs {len(vec2)}")

    # Convert to numpy for efficient computation
    a = np.array(vec1, dtype=np.float32)
    b = np.array(vec2, dtype=np.float32)

    # Calculate cosine similarity
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    # Avoid division by zero
    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(dot_product / (norm_a * norm_b))


def batch_cosine_similarity(query: list[float], candidates: list[list[float]]) -> list[float]:
    """Calculate cosine similarities between a query vector and multiple candidates.

    This function uses vectorized numpy operations for efficient batch computation,
    avoiding the overhead of computing similarities one-by-one in a loop.

    NEM-1071: Optimization using batch matrix operations.

    Args:
        query: Query embedding vector (1D list of floats)
        candidates: List of candidate embedding vectors to compare against

    Returns:
        List of cosine similarity scores (one per candidate), values between -1 and 1.
        Returns empty list if candidates is empty.
    """
    if not candidates:
        return []

    # Convert to numpy arrays for vectorized computation
    query_vec = np.array(query, dtype=np.float32)
    candidates_matrix = np.array(candidates, dtype=np.float32)

    # Handle zero query vector
    query_norm = np.linalg.norm(query_vec)
    if query_norm == 0:
        return [0.0] * len(candidates)

    # Normalize query vector
    query_normalized = query_vec / query_norm

    # Compute norms of all candidates at once (vectorized)
    candidate_norms = np.linalg.norm(candidates_matrix, axis=1)

    # Handle zero candidate vectors by setting their norm to 1 (result will be 0)
    # Use np.where to avoid division by zero
    safe_norms = np.where(candidate_norms == 0, 1.0, candidate_norms)

    # Normalize all candidates at once (broadcasting)
    candidates_normalized = candidates_matrix / safe_norms[:, np.newaxis]

    # Compute all dot products at once using matrix-vector multiplication
    similarities = np.dot(candidates_normalized, query_normalized)

    # Zero out similarities for candidates that had zero norm
    similarities = np.where(candidate_norms == 0, 0.0, similarities)

    # Convert to Python list of floats
    return [float(s) for s in similarities]


class ReIdentificationService:
    """Service for person re-identification across cameras.

    This service extracts embeddings from person crops using the resident
    OSNet-AIN x1.0 zoo handle (ledger item 20 — the full swap retired the
    ai-clip HTTP producer), stores them in Redis with 24-hour TTL — keyed
    by the producing ``model_id`` so two vector spaces can never be
    compared — and provides matching functionality to identify the same
    person across different camera views. When the pinned weights are not
    resident, ``generate_embedding`` raises ``ReIDUnavailableError``; the
    store never sees a zero-vector stub.

    Rate Limiting:
        All async operations (generate_embedding, store_embedding,
        find_matching_entities, get_entity_history) are rate-limited using
        an asyncio.Semaphore to prevent resource exhaustion. The limit is
        configurable via `max_concurrent_requests` parameter or the
        REID_MAX_CONCURRENT_REQUESTS setting.

    Usage:
        service = ReIdentificationService()

        # Extract embedding from a person crop (server-side, provenanced)
        embedding, model_id = await service.generate_embedding(
            image, bbox=(100, 100, 200, 200)
        )

        # Store embedding
        entity = EntityEmbedding(
            entity_type="person",
            embedding=embedding,
            camera_id="front_door",
            timestamp=datetime.now(timezone.utc),
            detection_id="det_123",
            model_id=model_id,
            attributes={"clothing": "blue jacket"},
        )
        await service.store_embedding(redis_client, entity)

        # Find matches
        matches = await service.find_matching_entities(
            redis_client, embedding, entity_type="person", threshold=0.85
        )
    """

    def __init__(
        self,
        max_concurrent_requests: int | None = None,
        embedding_timeout: float | None = None,
        max_retries: int | None = None,
        hybrid_storage: HybridEntityStorage | None = None,
    ) -> None:
        """Initialize the ReIdentificationService.

        Args:
            max_concurrent_requests: Maximum concurrent re-identification
                        operations. If not provided, uses the value from
                        settings (REID_MAX_CONCURRENT_REQUESTS, default: 10).
            embedding_timeout: Timeout in seconds for embedding generation
                        operations. If not provided, uses the value from
                        settings (REID_EMBEDDING_TIMEOUT, default: 30.0).
            max_retries: Maximum retry attempts for transient failures.
                        If not provided, uses the value from settings
                        (REID_MAX_RETRIES, default: 3).
            hybrid_storage: Optional HybridEntityStorage instance for PostgreSQL
                        persistence. If provided, enables storing and searching
                        entities in both Redis and PostgreSQL (NEM-2499).
        """
        self._hybrid_storage = hybrid_storage

        # Get settings for defaults
        settings = get_settings()

        # Set up rate limiting
        if max_concurrent_requests is not None:
            self._max_concurrent_requests = max_concurrent_requests
        else:
            self._max_concurrent_requests = settings.reid_max_concurrent_requests

        self._rate_limit_semaphore = asyncio.Semaphore(self._max_concurrent_requests)

        # Set up timeout (NEM-1085)
        if embedding_timeout is not None:
            self._embedding_timeout = embedding_timeout
        else:
            self._embedding_timeout = settings.reid_embedding_timeout

        # Set up retry configuration (NEM-1085)
        if max_retries is not None:
            self._max_retries = max_retries
        else:
            self._max_retries = settings.reid_max_retries

        logger.info(
            "ReIdentificationService initialized with max_concurrent_requests=%d, "
            "embedding_timeout=%.1fs, max_retries=%d, hybrid_storage=%s",
            self._max_concurrent_requests,
            self._embedding_timeout,
            self._max_retries,
            "enabled" if hybrid_storage else "disabled",
        )

    @property
    def max_concurrent_requests(self) -> int:
        """Get the maximum concurrent requests limit.

        Returns:
            Maximum number of concurrent re-identification operations allowed.
        """
        return self._max_concurrent_requests

    @property
    def hybrid_storage(self) -> HybridEntityStorage | None:
        """Get the HybridEntityStorage instance.

        Returns:
            HybridEntityStorage instance if configured, None otherwise.
            When configured, enables storing and searching entities in both
            Redis (hot cache) and PostgreSQL (persistence).

        Related to NEM-2499: Update ReIdentificationService to Use Hybrid Storage.
        """
        return self._hybrid_storage

    async def generate_embedding(
        self,
        image: Image.Image,
        bbox: tuple[int, int, int, int] | None = None,
    ) -> tuple[list[float], str]:
        """Compute a 512-dim OSNet-AIN x1.0 person re-ID embedding.

        The producer is the resident models.yml zoo handle (F12-pinned
        weights), read via the osnet_loader module — never a load trigger,
        never a stale dict (ledger item 20 retired the CLIP-as-re-ID seam;
        see the module docstring for why).

        Returns ``(vector, model_id)``: the belt travels with the bytes so
        every store and reader knows which space this vector lives in (F11).
        The belt is the HANDLE's own string — the file actually loaded —
        not the catalog's claim, so hand-deployed weights label honestly.

        This method is rate-limited to prevent resource exhaustion.
        It also implements timeout and retry logic with exponential backoff (NEM-1085).

        Bounding box validation (NEM-1073):
        - Invalid bboxes (zero width/height, NaN, inverted) raise InvalidBoundingBoxError
        - Bboxes exceeding image bounds are clamped automatically
        - Bboxes completely outside the image raise InvalidBoundingBoxError

        Timeout and Retry (NEM-1085):
        - Operations timeout after `embedding_timeout` seconds (default: 30s)
        - Transient failures are retried up to `max_retries` times
        - Uses exponential backoff: 2^attempt seconds between retries
        - An absent weights handle is NOT retried: availability is not transient

        Args:
            image: PIL Image to generate the embedding from
            bbox: Optional bounding box (x1, y1, x2, y2) to crop before embedding

        Returns:
            Tuple of (512-dimensional embedding vector, producer model_id)

        Raises:
            InvalidBoundingBoxError: If bbox has invalid dimensions or is outside image
            ReIDUnavailableError: If the re-ID weights are not resident
            RuntimeError: If extraction fails after all retries or times out
        """
        handle = osnet_loader.get_reid_handle()
        if handle is None:
            raise ReIDUnavailableError(
                f"The re-ID weights ({osnet_loader.OSNET_ZOO_NAME}) are not resident, so no person "
                "embedding can be computed. Check model zoo preload (BACKEND_MODEL_PRELOAD) "
                "and the models.yml weights path — a stored vector requires the pinned "
                "weights, and there is no stub fallback."
            )

        async with self._rate_limit_semaphore:
            # Validate and process bounding box if provided (NEM-1073)
            processed_image = image
            if bbox is not None:
                # Convert to float for validation
                bbox_float = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))

                # Check for fundamentally invalid bbox (NaN, zero dimensions, inverted)
                if not is_valid_bbox(bbox_float, allow_negative=True):
                    raise InvalidBoundingBoxError(
                        f"Invalid bounding box dimensions: {bbox}. "
                        "Bounding box has zero width/height, NaN values, or inverted coordinates.",
                        bbox=bbox_float,
                    )

                # Clamp bbox to image boundaries
                image_width, image_height = image.size
                clamped_bbox = clamp_bbox_to_image(
                    bbox,
                    image_width,
                    image_height,
                    min_size=1,
                    return_none_if_empty=True,
                )

                if clamped_bbox is None:
                    raise InvalidBoundingBoxError(
                        f"Bounding box {bbox} is completely outside image boundaries "
                        f"({image_width}x{image_height}) or became too small after clamping.",
                        bbox=bbox_float,
                    )

                # Log if clamping occurred
                if clamped_bbox != bbox:
                    logger.debug(
                        f"Bounding box clamped from {bbox} to {clamped_bbox} "
                        f"for image size {image_width}x{image_height}"
                    )

                # Crop using the validated/clamped bbox
                x1, y1, x2, y2 = clamped_bbox
                processed_image = image.crop((x1, y1, x2, y2))

            # Implement retry logic with exponential backoff (NEM-1085).
            # Extraction is CPU inference on the resident handle, so retrying
            # a transient failure is still meaningful (memory pressure, a
            # busy worker); an absent handle already refused above.
            last_exception: Exception | None = None
            for attempt in range(self._max_retries):
                try:
                    # Apply timeout to the extraction operation (NEM-1085)
                    async with asyncio.timeout(self._embedding_timeout):
                        result = await osnet_loader.extract_person_embedding(
                            handle, processed_image
                        )

                    # Native floats, not numpy scalars: store_embedding
                    # serializes the payload with json.dumps for its atomic
                    # Lua write, and json cannot encode a numpy float32. The
                    # retired CLIP producer arrived JSON-decoded from HTTP
                    # (already native); local OSNet inference returns a
                    # float32 array, so the conversion lives HERE — pinned
                    # by TestGenerateEmbedding (the swap's real-bytes driver
                    # found it, ledger item 20).
                    embedding = [float(x) for x in result.embedding]
                    belt = result.model_id
                    if not belt:
                        # The handle dict is built by load_osnet_model, which
                        # always sets model_id; a handle without one is a
                        # caller-supplied dict that never named itself. F11:
                        # that is the sentinel state, said as the sentinel —
                        # never laundered into the live space.
                        belt = LEGACY_MODEL_ID

                    logger.debug(
                        f"Generated re-ID embedding with dimension {len(embedding)} "
                        f"from weights {belt}"
                    )
                    return embedding, belt

                except InvalidBoundingBoxError:
                    # Re-raise bbox validation errors as-is (should not happen here)
                    raise
                except TimeoutError:
                    last_exception = TimeoutError(
                        f"Embedding generation timed out after {self._embedding_timeout}s"
                    )
                    if attempt < self._max_retries - 1:
                        delay = 2**attempt  # Exponential backoff: 1s, 2s, 4s, ...
                        logger.warning(
                            f"Embedding generation timed out (attempt {attempt + 1}/{self._max_retries}), "
                            f"retrying in {delay}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"Embedding generation timed out after {self._max_retries} attempts"
                        )
                except Exception as e:
                    last_exception = e
                    if attempt < self._max_retries - 1:
                        delay = 2**attempt  # Exponential backoff: 1s, 2s, 4s, ...
                        logger.warning(
                            f"Embedding generation failed (attempt {attempt + 1}/{self._max_retries}): {e}, "
                            f"retrying in {delay}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"Embedding generation failed after {self._max_retries} attempts: {e}"
                        )

            # All retries exhausted
            error_msg = f"Embedding generation failed after {self._max_retries} attempts"
            if last_exception:
                if isinstance(last_exception, TimeoutError):
                    error_msg = f"Embedding generation timed out after {self._max_retries} attempts"
                raise RuntimeError(error_msg) from last_exception
            raise RuntimeError(error_msg)

    async def store_embedding(
        self,
        redis_client: Redis | Any,
        embedding: EntityEmbedding,
        persist_to_postgres: bool = True,
    ) -> UUID | None:
        """Store an entity embedding in Redis, optionally with PostgreSQL persistence.

        Embeddings are stored with 24-hour TTL for session-based tracking in Redis.
        When persist_to_postgres=True and hybrid_storage is configured, also stores
        the embedding in PostgreSQL for 30-day retention.

        This method is rate-limited to prevent resource exhaustion.

        NEM-4474: Uses Redis Lua script for atomic read-modify-write to prevent
        race conditions when multiple processes store embeddings concurrently.

        Args:
            redis_client: Redis client instance (raw Redis or RedisClient wrapper)
            embedding: EntityEmbedding to store
            persist_to_postgres: If True and hybrid_storage is configured, also
                persist to PostgreSQL. Defaults to True. (NEM-2499)

        Returns:
            Entity UUID if persisted to PostgreSQL, None if Redis-only or
            if hybrid_storage is not configured.

        Related to NEM-2499: Update ReIdentificationService to Use Hybrid Storage.
        """
        async with self._rate_limit_semaphore:
            date_key = embedding.timestamp.strftime("%Y-%m-%d")
            # The key is PARTITIONED by provenance (F11, D-3): a search
            # over one space physically cannot read another's rows, and a
            # weights swap just stops writing the old partition (the 24 h
            # TTL expires it — no flush op). The per-entry model_id stays
            # the belt: a partition's key never outranks its payload.
            key = f"entity_embeddings:{embedding.model_id}:{date_key}"

            try:
                # NEM-4474: Use Lua script for atomic read-modify-write operation
                # This prevents race conditions when multiple processes store embeddings
                lua_script = """
                local key = KEYS[1]
                local embedding_json = ARGV[1]
                local list_key = ARGV[2]
                local ttl = tonumber(ARGV[3])

                -- Get existing data or create empty structure
                local data_json = redis.call('GET', key)
                local data
                if data_json then
                    data = cjson.decode(data_json)
                else
                    data = {persons = {}, vehicles = {}}
                end

                -- Add new embedding to appropriate list
                local embedding = cjson.decode(embedding_json)
                table.insert(data[list_key], embedding)

                -- Store with TTL
                redis.call('SET', key, cjson.encode(data), 'EX', ttl)
                return 1
                """

                list_key = "persons" if embedding.entity_type == "person" else "vehicles"
                embedding_json = json.dumps(embedding.to_dict())

                # Execute Lua script atomically using underlying Redis client
                # NEM-4474: Use Lua script for atomic read-modify-write
                from backend.core.redis import RedisClient

                # Check if Redis client supports eval (for atomic operations)
                # Mocks in tests may not have eval, so we fallback to non-atomic get/set
                raw_client = None
                if isinstance(redis_client, RedisClient):
                    raw_client = redis_client._client

                # Try atomic approach first (production), fallback to non-atomic (tests)
                use_atomic = (
                    raw_client is not None
                    and hasattr(raw_client, "eval")
                    and callable(getattr(raw_client, "eval", None))
                )

                if use_atomic and raw_client is not None:
                    await raw_client.eval(  # type: ignore[union-attr, misc]
                        lua_script,
                        1,  # Number of keys
                        key,
                        embedding_json,
                        list_key,
                        str(EMBEDDING_TTL_SECONDS),
                    )
                else:
                    # Fallback to non-atomic get/set for mocks without eval support
                    # This maintains backward compatibility with existing tests
                    data_json = await redis_client.get(key)
                    if data_json:
                        data = json.loads(data_json)
                    else:
                        data = {"persons": [], "vehicles": []}

                    data[list_key].append(embedding.to_dict())
                    await redis_client.set(
                        key,
                        json.dumps(data),
                        ex=EMBEDDING_TTL_SECONDS,
                    )

                logger.debug(
                    f"Stored {embedding.entity_type} embedding for camera {embedding.camera_id} (atomic)"
                )

            except Exception as e:
                logger.error(f"Failed to store embedding: {e}")
                raise

            # Persist to PostgreSQL via hybrid storage if configured (NEM-2499)
            if persist_to_postgres and self._hybrid_storage:
                try:
                    # Parse detection_id to int if possible (for PostgreSQL storage)
                    detection_id = (
                        int(embedding.detection_id) if embedding.detection_id.isdigit() else 0
                    )

                    entity_id, _is_new = await self._hybrid_storage.store_detection_embedding(
                        detection_id=detection_id,
                        entity_type=embedding.entity_type,
                        embedding=embedding.embedding,
                        camera_id=embedding.camera_id,
                        timestamp=embedding.timestamp,
                        attributes=embedding.attributes,
                        # The belt continues to the JSONB leg (F11).
                        model_id=embedding.model_id,
                    )

                    logger.debug(
                        "Persisted %s embedding to PostgreSQL for camera %s (entity_id=%s)",
                        embedding.entity_type,
                        embedding.camera_id,
                        entity_id,
                    )

                    return entity_id

                except Exception as e:
                    # Log warning but don't fail - Redis storage succeeded
                    logger.warning(
                        "Failed to persist %s embedding to PostgreSQL for camera %s: %s",
                        embedding.entity_type,
                        embedding.camera_id,
                        str(e),
                    )
                    return None

            return None

    async def _history_partition_keys(
        self, redis_client: Redis | Any, dates: list[str]
    ) -> list[str]:
        """Every ``entity_embeddings:{model_id}:{date}`` partition key.

        SCAN discovery, the repo's established pattern (batch_aggregator,
        dedupe, cache_service). Handles the RedisClient wrapper (scan_keys)
        and a raw client (scan_iter); anything else (a test double whose
        auto-mock returns a coroutine, a client without SCAN, a raised
        scan) contributes nothing and is simply skipped — SURFACING browse
        still reads the pre-partition date-only keys, which the caller
        always includes.
        """
        keys: list[str] = []

        def _collect(found: Any) -> None:
            for k in found:
                item = k.decode() if isinstance(k, bytes) else k
                keys.append(str(item))

        try:
            from backend.core.redis import RedisClient

            if isinstance(redis_client, RedisClient):
                for date_str in dates:
                    _collect(await redis_client.scan_keys(f"entity_embeddings:*:{date_str}"))
            elif hasattr(redis_client, "scan_iter"):
                for date_str in dates:
                    found = redis_client.scan_iter(
                        match=f"entity_embeddings:*:{date_str}", count=100
                    )
                    if inspect.isawaitable(found):
                        # A Mock double's scan_iter auto-mock returns a
                        # coroutine, not the async iterator redis gives:
                        # close it (no "never awaited" warning) and move on.
                        close = getattr(found, "close", None)
                        if callable(close):
                            close()
                        continue
                    _collect([k async for k in found])
        except Exception as e:
            logger.debug("entity_embeddings partition scan failed: %s", e)

        return keys

    async def find_matching_entities(
        self,
        redis_client: Redis,
        embedding: list[float],
        entity_type: str = "person",
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        exclude_detection_id: str | None = None,
        include_historical: bool = False,
        camera_id: str | None = None,
        model_id: str | None = None,
    ) -> list[EntityMatch]:
        """Find entities matching the given embedding.

        This method is rate-limited to prevent resource exhaustion.

        NEM-1071: Optimized with batch matrix operations for similarity computation.
        Instead of computing similarities one-by-one, we collect all candidate
        embeddings and compute similarities in a single vectorized operation.

        NEM-2499: When include_historical=True and hybrid_storage is configured,
        uses HybridEntityStorage for combined Redis + PostgreSQL search.

        NEM-4140: Instrumented with Prometheus metrics for monitoring Re-ID
        performance (attempts, matches, and match duration).

        Args:
            redis_client: Redis client instance
            embedding: 512-dimensional OSNet-AIN x1.0 person embedding to match
            entity_type: Type of entity to search ("person" or "vehicle")
            threshold: Minimum cosine similarity threshold (default
                DEFAULT_SIMILARITY_THRESHOLD — 0.7, the OSNet-space value)
            exclude_detection_id: Optional detection ID to exclude from results
            include_historical: If True and hybrid_storage is configured, search
                both Redis and PostgreSQL. Defaults to False. (NEM-2499)
            camera_id: Optional camera ID for metrics recording. If not provided,
                "unknown" is used. (NEM-4140)
            model_id: The producer's model id whose Redis partition is read
                (D-3, ledger item 20) — candidates are only ever drawn from
                ``entity_embeddings:{model_id}:{date}``. None (or the legacy
                sentinel) means no partition to read: zero candidates, the
                honest F11 answer, never a cross-space score.

        Returns:
            List of EntityMatch objects sorted by similarity (highest first)

        Related to NEM-2499: Update ReIdentificationService to Use Hybrid Storage.
        Related to NEM-4140: Re-ID Service Prometheus Metrics.
        """
        async with self._rate_limit_semaphore:
            matches: list[EntityMatch] = []
            now = datetime.now(UTC)
            start_time = time.perf_counter()

            # Record re-identification attempt (NEM-4140)
            metric_camera_id = camera_id or "unknown"
            record_reid_attempt(entity_type, metric_camera_id)

            # Use hybrid storage for combined Redis + PostgreSQL search (NEM-2499)
            if include_historical and self._hybrid_storage:
                try:
                    hybrid_matches = await self._hybrid_storage.find_matches(
                        embedding=embedding,
                        entity_type=entity_type,
                        threshold=threshold,
                        exclude_detection_id=exclude_detection_id,
                        include_historical=include_historical,
                        model_id=model_id,
                    )

                    # Convert HybridEntityMatch to EntityMatch for backward compatibility
                    for hybrid_match in hybrid_matches:
                        entity_embedding = EntityEmbedding(
                            entity_type=hybrid_match.entity_type,
                            embedding=hybrid_match.embedding,
                            camera_id=hybrid_match.camera_id,
                            timestamp=hybrid_match.timestamp,
                            detection_id=hybrid_match.detection_id or str(hybrid_match.entity_id),
                            model_id=hybrid_match.model_id,
                            attributes=hybrid_match.attributes,
                        )
                        matches.append(
                            EntityMatch(
                                entity=entity_embedding,
                                similarity=hybrid_match.similarity,
                                time_gap_seconds=hybrid_match.time_gap_seconds,
                            )
                        )

                    # Record metrics for successful matches (NEM-4140)
                    duration = time.perf_counter() - start_time
                    observe_reid_match_duration(entity_type, duration)
                    for match in matches:
                        record_reid_match(entity_type, match.entity.camera_id)
                        # Record cross-camera handoff if camera changed
                        is_known_camera = metric_camera_id != "unknown"
                        is_cross_camera = match.entity.camera_id != metric_camera_id
                        if is_known_camera and is_cross_camera:
                            record_cross_camera_handoff(
                                match.entity.camera_id, metric_camera_id, entity_type
                            )

                    logger.debug(
                        "Found %d hybrid matches for %s (threshold=%.2f, include_historical=%s)",
                        len(matches),
                        entity_type,
                        threshold,
                        include_historical,
                    )
                    return matches

                except Exception as e:
                    logger.warning(
                        "Hybrid storage search failed, falling back to Redis-only: %s",
                        str(e),
                    )
                    # Fall through to Redis-only search

            # Redis-only search (original behavior)
            try:
                # Check today's and yesterday's embeddings
                today = now.strftime("%Y-%m-%d")
                yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

                # Use a set to avoid duplicates if today and yesterday are the same key
                dates_to_check = list({today, yesterday})

                # Read ONLY the probe's own partition (F11, D-3): a search
                # over OSNet bytes physically cannot read another space's
                # rows. Without a named model_id there is no partition to
                # read and no honest comparison — the legacy date-only keys
                # hold pre-swap vectors, which are untrusted by definition,
                # so scoring them is not an option; zero candidates is.
                candidate_entities: list[EntityEmbedding] = []
                candidate_embeddings: list[list[float]] = []
                skipped_provenance = 0

                for date_str in dates_to_check:
                    if not model_id or model_id == LEGACY_MODEL_ID:
                        continue
                    key = f"entity_embeddings:{model_id}:{date_str}"
                    data_raw = await redis_client.get(key)

                    if not data_raw:
                        continue

                    # Handle both raw Redis (returns bytes/string) and RedisClient wrapper (returns JSON-decoded)
                    data = data_raw if isinstance(data_raw, dict) else json.loads(data_raw)
                    list_key = "persons" if entity_type == "person" else "vehicles"

                    # Safely get the list, handling edge case where data might be malformed
                    entity_list = data.get(list_key, []) if isinstance(data, dict) else []
                    for stored_data in entity_list:
                        # Skip if stored_data is not a dict (malformed data)
                        if not isinstance(stored_data, dict):
                            logger.warning(
                                "Skipping malformed entity data in Redis key %s: expected dict, got %s",
                                key,
                                type(stored_data).__name__,
                            )
                            continue

                        # Skip if this is the same detection
                        if (
                            exclude_detection_id
                            and stored_data.get("detection_id") == exclude_detection_id
                        ):
                            continue

                        # The belt inside the payload outranks the key:
                        # a foreign- or sentinel-provenance row inside a
                        # well-named partition is still uncomparable, and
                        # a mis-sized one (a stale 768-d row) would RAISE
                        # inside batch_cosine_similarity and kill the whole
                        # pass. Skip it, counted, and keep scoring.
                        entry_id = stored_data.get("model_id") or LEGACY_MODEL_ID
                        if entry_id != model_id:
                            skipped_provenance += 1
                            continue

                        stored = EntityEmbedding.from_dict(stored_data)
                        if len(stored.embedding) != len(embedding):
                            skipped_provenance += 1
                            continue
                        candidate_entities.append(stored)
                        candidate_embeddings.append(stored.embedding)

                if skipped_provenance:
                    logger.debug(
                        "Re-ID search skipped %d uncomparable %s row(s) "
                        "(provenance mismatch or dimension)",
                        skipped_provenance,
                        entity_type,
                    )

                # Compute all similarities at once using batch operation (NEM-1071)
                if candidate_embeddings:
                    similarities = batch_cosine_similarity(embedding, candidate_embeddings)

                    # Filter by threshold and create matches
                    for entity, similarity in zip(candidate_entities, similarities, strict=True):
                        if similarity >= threshold:
                            time_gap = (now - entity.timestamp).total_seconds()
                            matches.append(
                                EntityMatch(
                                    entity=entity,
                                    similarity=similarity,
                                    time_gap_seconds=time_gap,
                                )
                            )

                # Sort by similarity (highest first)
                matches.sort(key=lambda m: m.similarity, reverse=True)

                # Record metrics (NEM-4140)
                duration = time.perf_counter() - start_time
                observe_reid_match_duration(entity_type, duration)
                for match in matches:
                    record_reid_match(entity_type, match.entity.camera_id)
                    # Record cross-camera handoff if camera changed
                    is_known_camera = metric_camera_id != "unknown"
                    is_cross_camera = match.entity.camera_id != metric_camera_id
                    if is_known_camera and is_cross_camera:
                        record_cross_camera_handoff(
                            match.entity.camera_id, metric_camera_id, entity_type
                        )

                logger.debug(
                    f"Found {len(matches)} matching {entity_type}(s) with threshold {threshold}"
                )
                return matches

            except Exception as e:
                logger.error(f"Failed to find matching entities: {e}")
                return []

    async def get_entity_history(
        self,
        redis_client: Redis,
        entity_type: str,
        camera_id: str | None = None,
    ) -> list[EntityEmbedding]:
        """Get all stored embeddings for an entity type.

        This method is rate-limited to prevent resource exhaustion.

        Args:
            redis_client: Redis client instance
            entity_type: Type of entity ("person" or "vehicle")
            camera_id: Optional camera ID to filter by

        Returns:
            List of EntityEmbedding objects
        """
        async with self._rate_limit_semaphore:
            embeddings: list[EntityEmbedding] = []
            now = datetime.now(UTC)

            try:
                # Check today's and yesterday's embeddings
                today = now.strftime("%Y-%m-%d")
                yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

                # Use a set to avoid duplicates if today and yesterday are the same key
                dates_to_check = list({today, yesterday})

                # A BROWSE surface lists all spaces side by side (each row
                # carries its own model_id and the API shows it), so unlike
                # find_matching_entities it reads the pre-partition
                # date-only keys AND every model partition SCAN finds.
                # Surfacing is not scoring — F11's guard lives where a
                # similarity is produced.
                keys_to_read = [f"entity_embeddings:{d}" for d in dates_to_check]
                keys_to_read += await self._history_partition_keys(redis_client, dates_to_check)
                for key in keys_to_read:
                    data_raw = await redis_client.get(key)

                    if not data_raw:
                        continue

                    # Handle both raw Redis (returns bytes/string) and RedisClient wrapper (returns JSON-decoded)
                    data = data_raw if isinstance(data_raw, dict) else json.loads(data_raw)
                    list_key = "persons" if entity_type == "person" else "vehicles"

                    # Safely get the list, handling edge case where data might be malformed
                    entity_list = data.get(list_key, []) if isinstance(data, dict) else []
                    for stored_data in entity_list:
                        # Skip if stored_data is not a dict (malformed data)
                        if not isinstance(stored_data, dict):
                            logger.warning(
                                "Skipping malformed entity data in Redis key %s: expected dict, got %s",
                                key,
                                type(stored_data).__name__,
                            )
                            continue

                        entity = EntityEmbedding.from_dict(stored_data)

                        # Filter by camera if specified
                        if camera_id is None or entity.camera_id == camera_id:
                            embeddings.append(entity)

                # Sort by timestamp (newest first)
                embeddings.sort(key=lambda e: e.timestamp, reverse=True)
                return embeddings

            except Exception as e:
                logger.error(f"Failed to get entity history: {e}")
                return []


# Global service instance
_reid_service: ReIdentificationService | None = None


def get_reid_service() -> ReIdentificationService:
    """Get or create the global ReIdentificationService instance.

    Returns:
        Global ReIdentificationService instance
    """
    global _reid_service  # noqa: PLW0603
    if _reid_service is None:
        _reid_service = ReIdentificationService()
    return _reid_service


def reset_reid_service() -> None:
    """Reset the global ReIdentificationService instance (for testing)."""
    global _reid_service  # noqa: PLW0603
    _reid_service = None


# ============================================================================
# Prompt Formatting Functions
# ============================================================================


def format_entity_match(match: EntityMatch) -> str:
    """Format a single entity match for prompt inclusion.

    Args:
        match: EntityMatch to format

    Returns:
        Formatted string describing the match
    """
    entity = match.entity

    # Format time gap
    minutes = abs(match.time_gap_seconds) / 60
    if minutes < 1:
        time_str = f"{int(abs(match.time_gap_seconds))} seconds ago"
    elif minutes < 60:
        time_str = f"{int(minutes)} minutes ago"
    else:
        hours = minutes / 60
        time_str = f"{hours:.1f} hours ago"

    # Format similarity
    similarity_pct = match.similarity * 100

    # Build description
    lines = [
        f"  - Camera: {entity.camera_id}, Time: {time_str} (similarity: {similarity_pct:.0f}%)"
    ]

    # Add attributes if available, cleaning VQA artifacts (NEM-3009)
    # Note: Use local clean_vqa_output which extracts content after <loc_> tokens,
    # rather than validate_and_clean_vqa_output which rejects such output entirely.
    attrs = entity.attributes
    if attrs:
        attr_parts = []
        # Clean clothing attribute (may contain raw VQA output with artifacts)
        clothing_raw = attrs.get("clothing")
        clothing = clean_vqa_output(clothing_raw) if clothing_raw else None
        if clothing:
            attr_parts.append(f"wearing {clothing}")
        # Clean carrying attribute (may contain raw VQA output with artifacts)
        carrying_raw = attrs.get("carrying")
        carrying = clean_vqa_output(carrying_raw) if carrying_raw else None
        if carrying:
            attr_parts.append(f"carrying {carrying}")
        # Clean color attribute (may contain raw VQA output with artifacts)
        color_raw = attrs.get("color")
        color = clean_vqa_output(color_raw) if color_raw else None
        if color:
            attr_parts.append(color)
        # Clean vehicle_type attribute (may contain raw VQA output with artifacts)
        vehicle_type_raw = attrs.get("vehicle_type")
        vehicle_type = clean_vqa_output(vehicle_type_raw) if vehicle_type_raw else None
        if vehicle_type:
            attr_parts.append(vehicle_type)
        if attr_parts:
            lines.append(f"    Attributes: {', '.join(attr_parts)}")

    return "\n".join(lines)


def format_reid_context(
    matches_by_entity: dict[str, list[EntityMatch]],
    entity_type: str = "person",
) -> str:
    """Format re-identification matches for prompt inclusion.

    Args:
        matches_by_entity: Dict mapping detection_id to list of matches
        entity_type: Type of entity ("person" or "vehicle")

    Returns:
        Formatted string for prompt
    """
    if not matches_by_entity:
        return f"No {entity_type} re-identification matches found."

    lines = []
    for det_id, matches in matches_by_entity.items():
        if not matches:
            continue

        match_count = len(matches)
        lines.append(f"- [{det_id}] Seen {match_count} time(s) before:")
        for match in matches[:3]:  # Limit to top 3 matches
            lines.append(format_entity_match(match))

    if not lines:
        return f"No {entity_type} re-identification matches found."

    return "\n".join(lines)


def format_full_reid_context(
    person_matches: dict[str, list[EntityMatch]] | None = None,
    vehicle_matches: dict[str, list[EntityMatch]] | None = None,
) -> str:
    """Format complete re-identification context for all entity types.

    Args:
        person_matches: Dict mapping person detection_id to matches
        vehicle_matches: Dict mapping vehicle detection_id to matches

    Returns:
        Formatted string for prompt
    """
    sections = []

    if person_matches:
        person_section = format_reid_context(person_matches, "person")
        if not person_section.startswith("No "):
            sections.append(f"## Person Re-Identification\n{person_section}")

    if vehicle_matches:
        vehicle_section = format_reid_context(vehicle_matches, "vehicle")
        if not vehicle_section.startswith("No "):
            sections.append(f"## Vehicle Re-Identification\n{vehicle_section}")

    if not sections:
        return "No entities matched with previous sightings."

    return "\n\n".join(sections)


def format_reid_summary(
    person_matches: dict[str, list[EntityMatch]] | None = None,
    vehicle_matches: dict[str, list[EntityMatch]] | None = None,
) -> str:
    """Format a brief summary of re-identification matches.

    Args:
        person_matches: Dict mapping person detection_id to matches
        vehicle_matches: Dict mapping vehicle detection_id to matches

    Returns:
        Brief summary string for prompt
    """
    parts = []

    if person_matches:
        matched_persons = sum(1 for m in person_matches.values() if m)
        if matched_persons > 0:
            parts.append(f"{matched_persons} person(s) seen before")

    if vehicle_matches:
        matched_vehicles = sum(1 for m in vehicle_matches.values() if m)
        if matched_vehicles > 0:
            parts.append(f"{matched_vehicles} vehicle(s) seen before")

    if not parts:
        return "All entities appear to be new (not seen in last 24h)."

    return ", ".join(parts) + "."
