"""CLIP HTTP client service for embedding generation.

This service provides an HTTP client interface to the ai-clip service,
sending images for embedding generation using SigLIP 2 Base (via AI Gateway).

The ai-clip service runs CLIP as a dedicated HTTP service (URL configured via
settings.clip_url) to avoid loading the model on-demand in the backend, which
improves VRAM management.

Embedding Flow:
    1. Encode image to base64
    2. POST to ai-clip service with image
    3. Parse JSON response with embedding
    4. Return 768-dimensional embedding vector

Error Handling:
    - Connection errors: Raise CLIPUnavailableError (allows retry)
    - Timeouts: Raise CLIPUnavailableError (allows retry)
    - HTTP 5xx errors: Raise CLIPUnavailableError (allows retry)
    - HTTP 4xx errors: Log and raise CLIPUnavailableError (client error)
    - Invalid JSON: Log and raise CLIPUnavailableError (malformed response)
"""

from __future__ import annotations

import base64
import io
import time
from typing import TYPE_CHECKING

import httpx

from backend.api.middleware.correlation import get_correlation_headers
from backend.core.config import get_settings
from backend.core.logging import get_logger, sanitize_error
from backend.core.metrics import observe_ai_request_duration, record_pipeline_error
from backend.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)

# Timeout configuration for CLIP service
# Note: These defaults are used as fallbacks. Production code uses Settings values:
# - settings.ai_connect_timeout: Maximum time to establish connection (default: 10s)
# - settings.clip_read_timeout: Maximum time to wait for response (default: 15s)
# - settings.ai_health_timeout: Health check timeout (default: 5s)
CLIP_CONNECT_TIMEOUT = 10.0  # Fallback, use settings.ai_connect_timeout
CLIP_READ_TIMEOUT = 15.0  # Fallback, use settings.clip_read_timeout
CLIP_HEALTH_TIMEOUT = 5.0  # Fallback, use settings.ai_health_timeout

# SigLIP 2 Base / CLIP ViT-L embedding dimension (both 768-dim)
EMBEDDING_DIMENSION = 768


class CLIPUnavailableError(Exception):
    """Raised when the CLIP service is unavailable.

    This exception is raised when the CLIP service cannot be reached due to:
    - Connection errors (service down, network issues)
    - Timeout errors (service overloaded, slow response)
    - HTTP 5xx errors (server-side failures)

    This exception signals that the operation should be retried later,
    as the failure is transient and not due to invalid input.
    """

    def __init__(self, message: str, original_error: Exception | None = None):
        """Initialize the error.

        Args:
            message: Human-readable error description
            original_error: The underlying exception that caused this error
        """
        super().__init__(message)
        self.original_error = original_error


class CLIPClient:
    """Client for interacting with CLIP embedding service.

    This client handles communication with the external ai-clip service,
    including health checks, image submission, and response parsing.

    The CLIP model generates 768-dimensional embeddings suitable for
    cosine similarity comparisons in re-identification tasks.

    Usage:
        client = CLIPClient()

        # Check if service is healthy
        if await client.check_health():
            # Generate embedding from image
            embedding = await client.embed(image)
            # embedding is a list of 768 floats
    """

    def __init__(self, base_url: str | None = None) -> None:
        """Initialize CLIP client with configuration.

        Args:
            base_url: Optional base URL for the CLIP service.
                     Defaults to settings.clip_url from configuration.
        """
        settings = get_settings()

        # Use provided URL, or AI Gateway, or settings
        gw_url = getattr(settings, "ai_gateway_url", None)
        if base_url is not None:
            self._base_url = base_url.rstrip("/")
        elif getattr(settings, "use_ai_gateway", False) is True and isinstance(gw_url, str):
            self._base_url = f"{gw_url.rstrip('/')}/clip"
        else:
            self._base_url = settings.clip_url.rstrip("/")

        # Use httpx.Timeout for proper timeout configuration from Settings (NEM-2524)
        # Read timeout from settings (configurable via CLIP_READ_TIMEOUT env var)
        self._timeout = httpx.Timeout(
            connect=settings.ai_connect_timeout,
            read=settings.clip_read_timeout,
            write=settings.clip_read_timeout,
            pool=settings.ai_connect_timeout,
        )
        self._health_timeout = httpx.Timeout(
            connect=settings.ai_health_timeout,
            read=settings.ai_health_timeout,
            write=settings.ai_health_timeout,
            pool=settings.ai_health_timeout,
        )

        # Initialize per-endpoint circuit breakers for CLIP service.
        # Each endpoint gets its own breaker so that failures on one endpoint
        # (e.g. embed) do not block unrelated endpoints (e.g. classify).
        _cb_config = CircuitBreakerConfig(
            failure_threshold=settings.clip_cb_failure_threshold,
            recovery_timeout=settings.clip_cb_recovery_timeout,
            half_open_max_calls=settings.clip_cb_half_open_max_calls,
        )
        self._breakers: dict[str, CircuitBreaker] = {
            "embed": CircuitBreaker(name="clip_embed", config=_cb_config),
            "anomaly_score": CircuitBreaker(name="clip_anomaly_score", config=_cb_config),
            "classify": CircuitBreaker(name="clip_classify", config=_cb_config),
            "similarity": CircuitBreaker(name="clip_similarity", config=_cb_config),
            "batch_similarity": CircuitBreaker(name="clip_batch_similarity", config=_cb_config),
        }
        # Backward-compatible alias
        self._circuit_breaker = self._breakers["embed"]

        # Create persistent HTTP connection pool (NEM-1721)
        # Reusing connections avoids TCP overhead and resource exhaustion
        self._http_client = httpx.AsyncClient(
            timeout=self._timeout,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        self._health_http_client = httpx.AsyncClient(
            timeout=self._health_timeout,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

        logger.info(f"CLIPClient initialized with base_url={self._base_url}")

    def _get_headers(self) -> dict[str, str]:
        """Get headers for outgoing HTTP requests.

        Includes W3C Trace Context headers (traceparent, tracestate) for
        distributed tracing and correlation IDs for request tracking.

        Returns:
            Dictionary of headers to include in requests
        """
        return get_correlation_headers()

    async def close(self) -> None:
        """Close the HTTP client connections.

        Should be called when the client is no longer needed to release resources.
        """
        await self._http_client.aclose()
        await self._health_http_client.aclose()
        logger.debug("CLIPClient HTTP connections closed")

    def _encode_image_to_base64(self, image: Image.Image) -> str:
        """Encode a PIL Image to base64 string.

        Args:
            image: PIL Image to encode

        Returns:
            Base64-encoded string of the image in PNG format
        """
        buffer = io.BytesIO()
        # Use PNG for lossless encoding
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode("utf-8")

    def _get_breaker(self, endpoint: str) -> CircuitBreaker:
        """Get the per-endpoint circuit breaker for the given endpoint.

        Args:
            endpoint: Endpoint name (e.g. "embed", "classify", "similarity").

        Returns:
            The per-endpoint CircuitBreaker instance.
        """
        return self._breakers.get(endpoint, self._circuit_breaker)

    def get_circuit_breaker_state(self, endpoint: str | None = None) -> CircuitState:
        """Get current circuit breaker state.

        Args:
            endpoint: Optional endpoint name. If None, returns worst state across all breakers.

        Returns:
            Current CircuitState (CLOSED, OPEN, or HALF_OPEN)
        """
        if endpoint is not None:
            return self._get_breaker(endpoint).get_state()
        states = [b.get_state() for b in self._breakers.values()]
        if CircuitState.OPEN in states:
            return CircuitState.OPEN
        if CircuitState.HALF_OPEN in states:
            return CircuitState.HALF_OPEN
        return CircuitState.CLOSED

    def get_all_circuit_breaker_states(self) -> dict[str, str]:
        """Get the state of every per-endpoint circuit breaker.

        Returns:
            Dictionary mapping endpoint name to state string value.
        """
        return {name: breaker.get_state().value for name, breaker in self._breakers.items()}

    def reset_circuit_breaker(self, endpoint: str | None = None) -> None:
        """Manually reset circuit breaker(s) to CLOSED state.

        Args:
            endpoint: Optional endpoint name. If None, resets ALL breakers.
        """
        if endpoint is not None:
            self._get_breaker(endpoint).reset()
        else:
            for breaker in self._breakers.values():
                breaker.reset()

    def _check_circuit_breaker(self, endpoint: str = "embed") -> None:
        """Check if circuit breaker allows the request.

        Args:
            endpoint: Endpoint name to check breaker for.

        Raises:
            CLIPUnavailableError: If circuit breaker is open and rejecting requests
        """
        breaker = self._get_breaker(endpoint)
        if not breaker.allow_request():
            state = breaker.get_state()
            logger.warning(f"CLIP {endpoint} circuit breaker is {state.value}, rejecting request")
            record_pipeline_error("clip_circuit_open")
            raise CLIPUnavailableError(
                f"CLIP {endpoint} circuit breaker is open (state: {state.value}). "
                "Service is temporarily unavailable."
            )

    async def check_health(self) -> bool:
        """Check if CLIP service is healthy and reachable.

        Returns:
            True if CLIP service is healthy, False otherwise
        """
        try:
            # Use persistent HTTP client (NEM-1721)
            # NEM-3147: Include W3C Trace Context headers for distributed tracing
            response = await self._health_http_client.get(
                f"{self._base_url}/health",
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return True
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning(f"CLIP health check failed: {e}", exc_info=True)
            return False
        except httpx.HTTPStatusError as e:
            logger.warning(f"CLIP health check returned error status: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error during CLIP health check: {sanitize_error(e)}", exc_info=True
            )
            return False

    async def embed(self, image: Image.Image) -> list[float]:
        """Generate CLIP embedding from an image.

        Sends an image to the CLIP service and returns the 768-dimensional
        embedding vector suitable for cosine similarity comparisons.

        Args:
            image: PIL Image to generate embedding from

        Returns:
            768-dimensional embedding vector as list of floats

        Raises:
            CLIPUnavailableError: If the service is unavailable (connection, timeout, 5xx)
                or if the circuit breaker is open
        """
        # Check circuit breaker before making request
        self._check_circuit_breaker("embed")
        breaker = self._get_breaker("embed")

        start_time = time.time()

        logger.debug("Sending embedding request to CLIP service...")

        try:
            # Encode image to base64
            image_b64 = self._encode_image_to_base64(image)

            # Build request payload
            payload = {
                "image": image_b64,
            }

            # Track AI request time
            ai_start_time = time.time()

            # Send to CLIP service using persistent HTTP client (NEM-1721)
            # Includes W3C Trace Context headers for distributed tracing
            response = await self._http_client.post(
                f"{self._base_url}/embed",
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()

            # Record AI request duration
            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("clip", ai_duration)

            # Parse response
            result = response.json()

            if "embedding" not in result:
                logger.warning(f"Malformed response from CLIP (missing 'embedding'): {result}")
                record_pipeline_error("clip_malformed_response")
                raise CLIPUnavailableError(
                    "Malformed response from CLIP service: missing 'embedding'"
                )

            embedding: list[float] = result["embedding"]

            # Validate embedding dimension
            if len(embedding) != EMBEDDING_DIMENSION:
                logger.warning(
                    f"CLIP returned embedding with unexpected dimension: {len(embedding)} != {EMBEDDING_DIMENSION}"
                )
                record_pipeline_error("clip_invalid_dimension")
                raise CLIPUnavailableError(
                    f"CLIP returned embedding with invalid dimension: {len(embedding)}"
                )

            duration_ms = int((time.time() - start_time) * 1000)

            # Record success with circuit breaker
            breaker.record_success()

            logger.debug(f"CLIP embedding completed: {len(embedding)} dims in {duration_ms}ms")
            return embedding

        except httpx.ConnectError as e:
            # Record failure with circuit breaker for connection errors
            breaker.record_failure()
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("clip_connection_error")
            logger.error(
                f"Failed to connect to CLIP service: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"Failed to connect to CLIP service: {e}",
                original_error=e,
            ) from e

        except httpx.TimeoutException as e:
            # Record failure with circuit breaker for timeouts
            breaker.record_failure()
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("clip_timeout")
            logger.error(
                f"CLIP request timed out: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"CLIP request timed out: {e}",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            status_code = e.response.status_code

            # 5xx errors are server-side failures that should be retried
            if status_code >= 500:
                # Record failure with circuit breaker for server errors
                breaker.record_failure()
                record_pipeline_error("clip_server_error")
                logger.error(
                    f"CLIP returned server error: {status_code} - {e}",
                    extra={"duration_ms": duration_ms, "status_code": status_code},
                    exc_info=True,
                )
                raise CLIPUnavailableError(
                    f"CLIP returned server error: {status_code}",
                    original_error=e,
                ) from e

            # 4xx errors are client errors (bad request, etc.)
            # Don't record circuit breaker failure for client errors (user's fault)
            record_pipeline_error("clip_client_error")
            logger.error(
                f"CLIP returned client error: {status_code} - {e}",
                extra={"duration_ms": duration_ms, "status_code": status_code},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"CLIP returned client error: {status_code}",
                original_error=e,
            ) from e

        except CLIPUnavailableError:
            # Re-raise our own exceptions (circuit breaker already recorded if needed)
            raise

        except Exception as e:
            # Record failure with circuit breaker for unexpected errors
            breaker.record_failure()
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("clip_unexpected_error")
            logger.error(
                f"Unexpected error during CLIP embedding: {sanitize_error(e)}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"Unexpected error during CLIP embedding: {sanitize_error(e)}",
                original_error=e,
            ) from e

    async def anomaly_score(
        self, image: Image.Image, baseline_embedding: list[float]
    ) -> tuple[float, float]:
        """Compute scene anomaly score by comparing image to baseline embedding.

        Sends an image and baseline embedding to the CLIP service, which computes
        how different the current frame is from the baseline. This is useful for:
        - Detecting new objects appearing in frame
        - Identifying significant scene changes
        - Alerting on unexpected activity patterns

        The anomaly score is computed as: 1 - cosine_similarity
        - 0.0 = identical to baseline (no anomaly)
        - 1.0 = completely different from baseline (high anomaly)

        Args:
            image: PIL Image to analyze
            baseline_embedding: 768-dimensional baseline embedding (average of "normal" frames)

        Returns:
            Tuple of (anomaly_score, similarity_to_baseline)
            - anomaly_score: float in [0, 1] where higher = more anomalous
            - similarity_to_baseline: cosine similarity in [-1, 1]

        Raises:
            CLIPUnavailableError: If the service is unavailable or circuit breaker is open
            ValueError: If baseline_embedding has wrong dimension
        """
        # Check circuit breaker before making request
        self._check_circuit_breaker("anomaly_score")
        breaker = self._get_breaker("anomaly_score")

        start_time = time.time()

        # Validate baseline embedding dimension
        if len(baseline_embedding) != EMBEDDING_DIMENSION:
            raise ValueError(
                f"Baseline embedding must have {EMBEDDING_DIMENSION} dimensions, "
                f"got {len(baseline_embedding)}"
            )

        logger.debug("Sending anomaly score request to CLIP service...")

        try:
            # Encode image to base64
            image_b64 = self._encode_image_to_base64(image)

            # Build request payload
            payload = {
                "image": image_b64,
                "baseline_embedding": baseline_embedding,
            }

            # Track AI request time
            ai_start_time = time.time()

            # Send to CLIP service using persistent HTTP client (NEM-1721)
            # Includes W3C Trace Context headers for distributed tracing
            response = await self._http_client.post(
                f"{self._base_url}/anomaly-score",
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()

            # Record AI request duration
            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("clip_anomaly", ai_duration)

            # Parse response
            result = response.json()

            # Validate required fields
            if "anomaly_score" not in result:
                logger.warning(f"Malformed response from CLIP (missing 'anomaly_score'): {result}")
                record_pipeline_error("clip_anomaly_malformed_response")
                raise CLIPUnavailableError(
                    "Malformed response from CLIP service: missing 'anomaly_score'"
                )

            if "similarity_to_baseline" not in result:
                logger.warning(
                    f"Malformed response from CLIP (missing 'similarity_to_baseline'): {result}"
                )
                record_pipeline_error("clip_anomaly_malformed_response")
                raise CLIPUnavailableError(
                    "Malformed response from CLIP service: missing 'similarity_to_baseline'"
                )

            anomaly_score_val: float = result["anomaly_score"]
            similarity: float = result["similarity_to_baseline"]

            duration_ms = int((time.time() - start_time) * 1000)

            # Record success with circuit breaker
            breaker.record_success()

            logger.debug(
                f"CLIP anomaly score completed: score={anomaly_score_val:.3f}, "
                f"similarity={similarity:.3f} in {duration_ms}ms"
            )
            return anomaly_score_val, similarity

        except httpx.ConnectError as e:
            # Record failure with circuit breaker for connection errors
            breaker.record_failure()
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("clip_anomaly_connection_error")
            logger.error(
                f"Failed to connect to CLIP service for anomaly score: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"Failed to connect to CLIP service: {e}",
                original_error=e,
            ) from e

        except httpx.TimeoutException as e:
            # Record failure with circuit breaker for timeouts
            breaker.record_failure()
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("clip_anomaly_timeout")
            logger.error(
                f"CLIP anomaly score request timed out: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"CLIP anomaly score request timed out: {e}",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            status_code = e.response.status_code

            if status_code >= 500:
                # Record failure with circuit breaker for server errors
                breaker.record_failure()
                record_pipeline_error("clip_anomaly_server_error")
                logger.error(
                    f"CLIP anomaly score returned server error: {status_code} - {e}",
                    extra={"duration_ms": duration_ms, "status_code": status_code},
                    exc_info=True,
                )
                raise CLIPUnavailableError(
                    f"CLIP returned server error: {status_code}",
                    original_error=e,
                ) from e

            # Don't record circuit breaker failure for client errors
            record_pipeline_error("clip_anomaly_client_error")
            logger.error(
                f"CLIP anomaly score returned client error: {status_code} - {e}",
                extra={"duration_ms": duration_ms, "status_code": status_code},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"CLIP returned client error: {status_code}",
                original_error=e,
            ) from e

        except CLIPUnavailableError:
            # Re-raise our own exceptions (circuit breaker already recorded if needed)
            raise

        except Exception as e:
            # Record failure with circuit breaker for unexpected errors
            breaker.record_failure()
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("clip_anomaly_unexpected_error")
            logger.error(
                f"Unexpected error during CLIP anomaly score: {sanitize_error(e)}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"Unexpected error during CLIP anomaly score: {sanitize_error(e)}",
                original_error=e,
            ) from e

    async def classify(self, image: Image.Image, labels: list[str]) -> tuple[dict[str, float], str]:
        """Classify an image against a list of text labels using zero-shot classification.

        Uses CLIP's text encoder and image encoder to compute similarity scores,
        then applies softmax to normalize scores to sum to 1.0.

        Args:
            image: PIL Image to classify
            labels: List of text labels to classify against

        Returns:
            Tuple of (scores dict, top_label)

        Raises:
            CLIPUnavailableError: If the service is unavailable (connection, timeout, 5xx)
                or if the circuit breaker is open
            ValueError: If labels list is empty
        """
        if not labels:
            raise ValueError("Labels list cannot be empty")

        # Check circuit breaker before making request
        self._check_circuit_breaker("classify")
        breaker = self._get_breaker("classify")

        start_time = time.time()

        logger.debug(f"Sending classification request to CLIP service with {len(labels)} labels...")

        try:
            # Encode image to base64
            image_b64 = self._encode_image_to_base64(image)

            # Build request payload
            payload = {
                "image": image_b64,
                "labels": labels,
            }

            # Track AI request time
            ai_start_time = time.time()

            # Send to CLIP service using persistent HTTP client (NEM-1721)
            # Includes W3C Trace Context headers for distributed tracing
            response = await self._http_client.post(
                f"{self._base_url}/classify",
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()

            # Record AI request duration
            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("clip", ai_duration)

            # Parse response
            result = response.json()

            if "scores" not in result or "top_label" not in result:
                logger.warning(f"Malformed response from CLIP classify (missing fields): {result}")
                record_pipeline_error("clip_malformed_response")
                raise CLIPUnavailableError(
                    "Malformed response from CLIP service: missing 'scores' or 'top_label'"
                )

            scores: dict[str, float] = result["scores"]
            top_label: str = result["top_label"]

            duration_ms = int((time.time() - start_time) * 1000)

            # Record success with circuit breaker
            breaker.record_success()

            logger.debug(
                f"CLIP classification completed: top_label='{top_label}' in {duration_ms}ms"
            )
            return scores, top_label

        except httpx.ConnectError as e:
            # Record failure with circuit breaker for connection errors
            breaker.record_failure()
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("clip_connection_error")
            logger.error(
                f"Failed to connect to CLIP service: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"Failed to connect to CLIP service: {e}",
                original_error=e,
            ) from e

        except httpx.TimeoutException as e:
            # Record failure with circuit breaker for timeouts
            breaker.record_failure()
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("clip_timeout")
            logger.error(
                f"CLIP request timed out: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"CLIP request timed out: {e}",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            status_code = e.response.status_code

            if status_code >= 500:
                # Record failure with circuit breaker for server errors
                breaker.record_failure()
                record_pipeline_error("clip_server_error")
                logger.error(
                    f"CLIP returned server error: {status_code} - {e}",
                    extra={"duration_ms": duration_ms, "status_code": status_code},
                    exc_info=True,
                )
                raise CLIPUnavailableError(
                    f"CLIP returned server error: {status_code}",
                    original_error=e,
                ) from e

            # Don't record circuit breaker failure for client errors
            record_pipeline_error("clip_client_error")
            logger.error(
                f"CLIP returned client error: {status_code} - {e}",
                extra={"duration_ms": duration_ms, "status_code": status_code},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"CLIP returned client error: {status_code}",
                original_error=e,
            ) from e

        except CLIPUnavailableError:
            # Re-raise our own exceptions (circuit breaker already recorded if needed)
            raise

        except Exception as e:
            # Record failure with circuit breaker for unexpected errors
            breaker.record_failure()
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("clip_unexpected_error")
            logger.error(
                f"Unexpected error during CLIP classification: {sanitize_error(e)}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"Unexpected error during CLIP classification: {sanitize_error(e)}",
                original_error=e,
            ) from e

    async def similarity(self, image: Image.Image, text: str) -> float:
        """Compute cosine similarity between an image and a text description.

        Args:
            image: PIL Image to compare
            text: Text description to compare against

        Returns:
            Cosine similarity score (typically between -1 and 1, but usually 0-1 for CLIP)

        Raises:
            CLIPUnavailableError: If the service is unavailable (connection, timeout, 5xx)
                or if the circuit breaker is open
        """
        # Check circuit breaker before making request
        self._check_circuit_breaker("similarity")
        breaker = self._get_breaker("similarity")

        start_time = time.time()

        logger.debug("Sending similarity request to CLIP service...")

        try:
            # Encode image to base64
            image_b64 = self._encode_image_to_base64(image)

            # Build request payload
            payload = {
                "image": image_b64,
                "text": text,
            }

            # Track AI request time
            ai_start_time = time.time()

            # Send to CLIP service using persistent HTTP client (NEM-1721)
            # Includes W3C Trace Context headers for distributed tracing
            response = await self._http_client.post(
                f"{self._base_url}/similarity",
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()

            # Record AI request duration
            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("clip", ai_duration)

            # Parse response
            result = response.json()

            if "similarity" not in result:
                logger.warning(
                    f"Malformed response from CLIP similarity (missing 'similarity'): {result}"
                )
                record_pipeline_error("clip_malformed_response")
                raise CLIPUnavailableError(
                    "Malformed response from CLIP service: missing 'similarity'"
                )

            sim_score: float = result["similarity"]

            duration_ms = int((time.time() - start_time) * 1000)

            # Record success with circuit breaker
            breaker.record_success()

            logger.debug(f"CLIP similarity completed: {sim_score:.4f} in {duration_ms}ms")
            return sim_score

        except httpx.ConnectError as e:
            # Record failure with circuit breaker for connection errors
            breaker.record_failure()
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("clip_connection_error")
            logger.error(
                f"Failed to connect to CLIP service: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"Failed to connect to CLIP service: {e}",
                original_error=e,
            ) from e

        except httpx.TimeoutException as e:
            # Record failure with circuit breaker for timeouts
            breaker.record_failure()
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("clip_timeout")
            logger.error(
                f"CLIP request timed out: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"CLIP request timed out: {e}",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            status_code = e.response.status_code

            if status_code >= 500:
                # Record failure with circuit breaker for server errors
                breaker.record_failure()
                record_pipeline_error("clip_server_error")
                logger.error(
                    f"CLIP returned server error: {status_code} - {e}",
                    extra={"duration_ms": duration_ms, "status_code": status_code},
                    exc_info=True,
                )
                raise CLIPUnavailableError(
                    f"CLIP returned server error: {status_code}",
                    original_error=e,
                ) from e

            # Don't record circuit breaker failure for client errors
            record_pipeline_error("clip_client_error")
            logger.error(
                f"CLIP returned client error: {status_code} - {e}",
                extra={"duration_ms": duration_ms, "status_code": status_code},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"CLIP returned client error: {status_code}",
                original_error=e,
            ) from e

        except CLIPUnavailableError:
            # Re-raise our own exceptions (circuit breaker already recorded if needed)
            raise

        except Exception as e:
            # Record failure with circuit breaker for unexpected errors
            breaker.record_failure()
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("clip_unexpected_error")
            logger.error(
                f"Unexpected error during CLIP similarity: {sanitize_error(e)}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"Unexpected error during CLIP similarity: {sanitize_error(e)}",
                original_error=e,
            ) from e

    async def batch_similarity(self, image: Image.Image, texts: list[str]) -> dict[str, float]:
        """Compute cosine similarity between an image and multiple text descriptions.

        Args:
            image: PIL Image to compare
            texts: List of text descriptions to compare against

        Returns:
            Dictionary mapping each text to its similarity score

        Raises:
            CLIPUnavailableError: If the service is unavailable (connection, timeout, 5xx)
                or if the circuit breaker is open
            ValueError: If texts list is empty
        """
        if not texts:
            raise ValueError("Texts list cannot be empty")

        # Check circuit breaker before making request
        self._check_circuit_breaker("batch_similarity")
        breaker = self._get_breaker("batch_similarity")

        start_time = time.time()

        logger.debug(f"Sending batch similarity request to CLIP service with {len(texts)} texts...")

        try:
            # Encode image to base64
            image_b64 = self._encode_image_to_base64(image)

            # Build request payload
            payload = {
                "image": image_b64,
                "texts": texts,
            }

            # Track AI request time
            ai_start_time = time.time()

            # Send to CLIP service using persistent HTTP client (NEM-1721)
            # Includes W3C Trace Context headers for distributed tracing
            response = await self._http_client.post(
                f"{self._base_url}/batch-similarity",
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()

            # Record AI request duration
            ai_duration = time.time() - ai_start_time
            observe_ai_request_duration("clip", ai_duration)

            # Parse response
            result = response.json()

            if "similarities" not in result:
                logger.warning(
                    f"Malformed response from CLIP batch-similarity (missing 'similarities'): {result}"
                )
                record_pipeline_error("clip_malformed_response")
                raise CLIPUnavailableError(
                    "Malformed response from CLIP service: missing 'similarities'"
                )

            similarities: dict[str, float] = result["similarities"]

            duration_ms = int((time.time() - start_time) * 1000)

            # Record success with circuit breaker
            breaker.record_success()

            logger.debug(
                f"CLIP batch similarity completed: {len(similarities)} scores in {duration_ms}ms"
            )
            return similarities

        except httpx.ConnectError as e:
            # Record failure with circuit breaker for connection errors
            breaker.record_failure()
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("clip_connection_error")
            logger.error(
                f"Failed to connect to CLIP service: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"Failed to connect to CLIP service: {e}",
                original_error=e,
            ) from e

        except httpx.TimeoutException as e:
            # Record failure with circuit breaker for timeouts
            breaker.record_failure()
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("clip_timeout")
            logger.error(
                f"CLIP request timed out: {e}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"CLIP request timed out: {e}",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            status_code = e.response.status_code

            # 5xx errors are server-side failures that should be retried
            if status_code >= 500:
                # Record failure with circuit breaker for server errors
                breaker.record_failure()
                record_pipeline_error("clip_server_error")
                logger.error(
                    f"CLIP returned server error: {status_code} - {e}",
                    extra={"duration_ms": duration_ms, "status_code": status_code},
                    exc_info=True,
                )
                raise CLIPUnavailableError(
                    f"CLIP returned server error: {status_code}",
                    original_error=e,
                ) from e

            # 4xx errors are client errors (bad request, etc.) - don't record circuit breaker failure
            record_pipeline_error("clip_client_error")
            logger.error(
                f"CLIP returned client error: {status_code} - {e}",
                extra={"duration_ms": duration_ms, "status_code": status_code},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"CLIP returned client error: {status_code}",
                original_error=e,
            ) from e

        except CLIPUnavailableError:
            # Re-raise our own exceptions (circuit breaker already recorded if needed)
            raise

        except Exception as e:
            # Record failure with circuit breaker for unexpected errors
            breaker.record_failure()
            duration_ms = int((time.time() - start_time) * 1000)
            record_pipeline_error("clip_unexpected_error")
            logger.error(
                f"Unexpected error during CLIP batch similarity: {sanitize_error(e)}",
                extra={"duration_ms": duration_ms},
                exc_info=True,
            )
            raise CLIPUnavailableError(
                f"Unexpected error during CLIP batch similarity: {sanitize_error(e)}",
                original_error=e,
            ) from e


# Global client instance
_clip_client: CLIPClient | None = None


def get_clip_client() -> CLIPClient:
    """Get or create the global CLIPClient instance.

    Returns:
        Global CLIPClient instance
    """
    global _clip_client  # noqa: PLW0603
    if _clip_client is None:
        _clip_client = CLIPClient()
    return _clip_client


async def reset_clip_client() -> None:
    """Reset the global CLIPClient instance (for testing).

    This async function properly closes HTTP connections before resetting.
    """
    global _clip_client  # noqa: PLW0603
    if _clip_client is not None:
        await _clip_client.close()
    _clip_client = None
