"""Request recording middleware for debugging production issues (NEM-1646).

This module provides:
- RequestRecorderMiddleware: Records HTTP requests for replay debugging
- RequestRecording: Data class for recorded request data
- Redaction utilities for sensitive field protection

Recording triggers:
1. Always record on error (status >= 500)
2. Sample % of successful requests (configurable)
3. Always record if X-Debug-Record header is present

Security considerations:
- Uses SENSITIVE_FIELD_NAMES from logging module for consistent redaction
- Sensitive headers (Authorization, etc.) are automatically redacted
- Request/response bodies are redacted before storage
"""

from __future__ import annotations

import json
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.core.config import get_settings
from backend.core.logging import SENSITIVE_FIELD_NAMES, get_logger

logger = get_logger(__name__)

# Default recordings directory
DEFAULT_RECORDINGS_DIR = "data/recordings"

# Headers that should always be redacted (case-insensitive)
SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "x-api-key",
        "api-key",
        "cookie",
        "set-cookie",
        "x-auth-token",
        "x-access-token",
        "x-refresh-token",
        "proxy-authorization",
    }
)


def redact_request_body(data: Any, _depth: int = 0) -> Any:
    """Redact sensitive fields from request/response body.

    Uses SENSITIVE_FIELD_NAMES from backend.core.logging for consistent
    redaction patterns across the application.

    Args:
        data: The data to redact (dict, list, or primitive)
        _depth: Current recursion depth (internal use)

    Returns:
        Data with sensitive fields redacted to "[REDACTED]"
    """
    # Prevent infinite recursion
    if _depth > 10:
        return data

    if data is None:
        return None

    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            key_lower = key.lower()

            # Check if key exactly matches a known sensitive field name
            # Only exact matches to prevent over-redaction
            # (e.g., "user" is not sensitive, "credentials" as a container is not,
            # but "password", "api_key", "authorization" are)
            sensitive_field_names = {
                "password",
                "passwd",
                "secret",
                "api_key",
                "apikey",
                "access_token",
                "refresh_token",
                "authorization",
                "token",
                "credential",
                "auth_token",
                "bearer",
                "private_key",
                "secret_key",
                "session_id",
                "session_token",
                "auth",
            }
            is_sensitive = (
                key_lower in SENSITIVE_FIELD_NAMES
                or key_lower in SENSITIVE_HEADERS
                or key_lower in sensitive_field_names
            )

            if is_sensitive:
                result[key] = "[REDACTED]"
            else:
                result[key] = redact_request_body(value, _depth + 1)

        return result

    if isinstance(data, list):
        return [redact_request_body(item, _depth + 1) for item in data]

    # Return primitives as-is
    return data


@dataclass
class RequestRecording:
    """Data class representing a recorded HTTP request.

    Contains all information needed to replay the request for debugging.
    """

    recording_id: str
    timestamp: str
    method: str
    path: str
    headers: dict[str, str]
    body: Any
    query_params: dict[str, str]
    status_code: int
    response_body: Any = None
    body_truncated: bool = False
    duration_ms: float = 0.0
    client_ip: str = ""
    error_type: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize recording to dictionary."""
        return {
            "recording_id": self.recording_id,
            "timestamp": self.timestamp,
            "method": self.method,
            "path": self.path,
            "headers": self.headers,
            "body": self.body,
            "query_params": self.query_params,
            "status_code": self.status_code,
            "response_body": self.response_body,
            "body_truncated": self.body_truncated,
            "duration_ms": self.duration_ms,
            "client_ip": self.client_ip,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RequestRecording:
        """Deserialize recording from dictionary."""
        return cls(
            recording_id=data["recording_id"],
            timestamp=data["timestamp"],
            method=data["method"],
            path=data["path"],
            headers=data.get("headers", {}),
            body=data.get("body"),
            query_params=data.get("query_params", {}),
            status_code=data.get("status_code", 0),
            response_body=data.get("response_body"),
            body_truncated=data.get("body_truncated", False),
            duration_ms=data.get("duration_ms", 0.0),
            client_ip=data.get("client_ip", ""),
            error_type=data.get("error_type"),
            error_message=data.get("error_message"),
        )


class RequestRecorderMiddleware(BaseHTTPMiddleware):
    """Middleware for recording HTTP requests for debugging.

    Records requests based on configurable triggers:
    1. Always on error (status >= 500)
    2. Sample % of successful requests
    3. When X-Debug-Record header is present

    Recordings are stored as JSON files in the configured directory.

    NEM-1646: Request replay capability for debugging production issues.
    """

    def __init__(
        self,
        app: Any,
        enabled: bool | None = None,
        sample_rate: float | None = None,
        max_body_size: int | None = None,
        recordings_dir: str | None = None,
    ) -> None:
        """Initialize the middleware.

        Args:
            app: ASGI application
            enabled: Enable/disable recording. Defaults to settings value.
            sample_rate: Fraction of successful requests to sample (0.0-1.0).
                        Defaults to settings value.
            max_body_size: Maximum body size to record in bytes.
                          Defaults to settings value.
            recordings_dir: Directory to store recordings.
                           Defaults to data/recordings.
        """
        super().__init__(app)

        # Load settings
        settings = get_settings()

        # Use explicit values or fall back to settings
        self.enabled = (
            enabled
            if enabled is not None
            else getattr(settings, "request_recording_enabled", False)
        )
        self.sample_rate = (
            sample_rate
            if sample_rate is not None
            else getattr(settings, "request_recording_sample_rate", 0.01)
        )
        self.max_body_size = (
            max_body_size
            if max_body_size is not None
            else getattr(settings, "request_recording_max_body_size", 10000)
        )
        self.recordings_dir = recordings_dir or DEFAULT_RECORDINGS_DIR

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Process request and potentially record it.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler

        Returns:
            HTTP response from the application
        """
        # Skip if disabled
        if not self.enabled:
            response: Response = await call_next(request)
            return response

        # Determine if we should record this request
        should_record = self._should_record(request)
        recording_id = None

        # Read and cache the body for potential recording
        body_bytes = b""
        body_data: Any = None
        body_truncated = False

        if should_record or request.headers.get("x-debug-record"):
            try:
                body_bytes = await request.body()

                # Check if body exceeds max size
                if len(body_bytes) > self.max_body_size:
                    body_truncated = True
                    body_bytes = body_bytes[: self.max_body_size]

                # Try to parse as JSON
                if body_bytes:
                    try:
                        body_data = json.loads(body_bytes.decode("utf-8"))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # Store as base64 if not JSON
                        import base64

                        body_data = {"_binary": base64.b64encode(body_bytes).decode("ascii")}
            except Exception as e:
                logger.debug(f"Failed to read request body: {e}")
                body_data = None

            # Rebuild request with cached body so route handler can read it
            # This is necessary because body() consumes the stream
            request._body = body_bytes

        # Record timing
        start_time = time.perf_counter()

        # Call the route handler
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Determine if we need to record based on response
            force_record = request.headers.get("x-debug-record")
            is_error = response.status_code >= 500
            # Use secrets.randbelow for secure random sampling
            # Sample rate is a float 0-1, so we compare against scaled random
            is_sampled = should_record and (secrets.randbelow(10000) / 10000.0) < self.sample_rate

            if self.enabled and (force_record or is_error or is_sampled):
                recording_id = self._generate_recording_id()

                recording = self._create_recording(
                    recording_id=recording_id,
                    request=request,
                    body_data=body_data,
                    body_truncated=body_truncated,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                )

                # Store recording asynchronously (don't block response)
                self._store_recording(recording)

                # Add recording ID to response header
                response.headers["X-Recording-ID"] = recording_id

            return response

        except Exception as e:
            # Record the error
            duration_ms = (time.perf_counter() - start_time) * 1000

            if self.enabled:
                recording_id = self._generate_recording_id()

                recording = self._create_recording(
                    recording_id=recording_id,
                    request=request,
                    body_data=body_data,
                    body_truncated=body_truncated,
                    status_code=500,
                    duration_ms=duration_ms,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )

                self._store_recording(recording)

            # Re-raise the exception
            raise

    def _should_record(self, request: Request) -> bool:
        """Determine if request should potentially be recorded.

        Args:
            request: HTTP request

        Returns:
            True if request might be recorded (subject to sampling/error check)
        """
        # Always record if debug header present
        if request.headers.get("x-debug-record"):
            return True

        # Don't record health check endpoints
        path = request.url.path
        return path not in ("/health", "/ready", "/metrics", "/", "/api/system/health")

    def _generate_recording_id(self) -> str:
        """Generate a unique recording ID."""
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        unique = uuid.uuid4().hex[:8]
        return f"{timestamp}_{unique}"

    def _create_recording(
        self,
        recording_id: str,
        request: Request,
        body_data: Any,
        body_truncated: bool,
        status_code: int,
        duration_ms: float,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> RequestRecording:
        """Create a RequestRecording from request data.

        Args:
            recording_id: Unique ID for this recording
            request: HTTP request
            body_data: Parsed request body
            body_truncated: Whether body was truncated
            status_code: HTTP response status code
            duration_ms: Request duration in milliseconds
            error_type: Exception type name if error occurred
            error_message: Exception message if error occurred

        Returns:
            RequestRecording instance
        """
        # Extract and redact headers
        headers = dict(request.headers)
        redacted_headers = {}
        for key, value in headers.items():
            key_lower = key.lower()
            if key_lower in SENSITIVE_HEADERS:
                redacted_headers[key_lower] = "[REDACTED]"
            else:
                redacted_headers[key_lower] = value

        # Redact body data
        redacted_body = redact_request_body(body_data) if body_data else None

        # Extract query parameters
        query_params = dict(request.query_params)

        # Get client IP
        client_ip = ""
        if request.client:
            client_ip = request.client.host

        return RequestRecording(
            recording_id=recording_id,
            timestamp=datetime.now(UTC).isoformat(),
            method=request.method,
            path=str(request.url.path),
            headers=redacted_headers,
            body=redacted_body,
            query_params=query_params,
            status_code=status_code,
            body_truncated=body_truncated,
            duration_ms=round(duration_ms, 2),
            client_ip=client_ip,
            error_type=error_type,
            error_message=error_message,
        )

    def _store_recording(self, recording: RequestRecording) -> None:
        """Store recording to disk.

        Args:
            recording: RequestRecording to store
        """
        try:
            # Ensure directory exists
            recordings_path = Path(self.recordings_dir).resolve()
            recordings_path.mkdir(parents=True, exist_ok=True)

            # Sanitize recording_id to prevent path traversal
            # Only allow alphanumeric, hyphen, and underscore
            safe_id = "".join(c for c in recording.recording_id if c.isalnum() or c in "-_")
            if not safe_id:
                safe_id = "unknown"

            # Create filename with timestamp for sorting
            filename = f"{safe_id}.json"
            filepath = (recordings_path / filename).resolve()

            # Validate path is within recordings directory (prevent traversal)
            if not str(filepath).startswith(str(recordings_path)):
                logger.warning(
                    f"Path traversal attempt blocked: {filepath}",
                    extra={"recording_id": recording.recording_id},
                )
                return

            # Write recording - filepath is validated above
            with filepath.open("w", encoding="utf-8") as f:
                json.dump(recording.to_dict(), f, indent=2, default=str)

            logger.debug(
                f"Recorded request {recording.recording_id}",
                extra={
                    "recording_id": recording.recording_id,
                    "method": recording.method,
                    "path": recording.path,
                    "status_code": recording.status_code,
                },
            )

        except Exception as e:
            # Don't fail the request if recording fails
            logger.warning(
                f"Failed to store recording: {e}",
                extra={"recording_id": recording.recording_id, "error": str(e)},
            )


def load_recording(
    recording_id: str, recordings_dir: str = DEFAULT_RECORDINGS_DIR
) -> RequestRecording | None:
    """Load a recording from disk.

    Args:
        recording_id: ID of the recording to load
        recordings_dir: Directory containing recordings

    Returns:
        RequestRecording if found, None otherwise
    """
    try:
        # Resolve the base directory
        base_path = Path(recordings_dir).resolve()

        # Sanitize recording_id to prevent path traversal
        safe_id = "".join(c for c in recording_id if c.isalnum() or c in "-_")
        if not safe_id:
            return None

        filepath = (base_path / f"{safe_id}.json").resolve()

        # Validate path is within recordings directory (prevent traversal)
        if not str(filepath).startswith(str(base_path)):
            logger.warning(f"Path traversal attempt blocked: {filepath}")
            return None

        if not filepath.exists():
            return None

        # Read recording - filepath is validated above
        with filepath.open(encoding="utf-8") as f:
            data = json.load(f)

        return RequestRecording.from_dict(data)

    except Exception as e:
        logger.warning(f"Failed to load recording {recording_id}: {e}")
        return None
