"""Unit tests for request recorder middleware (NEM-1646).

This module provides comprehensive tests for:
- RequestRecorderMiddleware: Recording HTTP requests for debugging
- RequestRecording: Data class for recorded request data
- Sensitive field redaction using SENSITIVE_FIELD_NAMES
- Configurable sampling and recording triggers

Tests verify request recording, redaction, and replay functionality.
"""

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from backend.api.middleware.request_recorder import (
    RequestRecorderMiddleware,
    RequestRecording,
    redact_request_body,
)

# =============================================================================
# RequestRecording Data Class Tests
# =============================================================================


class TestRequestRecording:
    """Tests for RequestRecording data class."""

    def test_recording_creation_with_required_fields(self):
        """Test that RequestRecording can be created with required fields."""
        recording = RequestRecording(
            recording_id="test-123",
            timestamp=datetime.now(UTC).isoformat(),
            method="POST",
            path="/api/events",
            headers={"content-type": "application/json"},
            body={"event_id": "abc"},
            query_params={},
            status_code=500,
        )

        assert recording.recording_id == "test-123"
        assert recording.method == "POST"
        assert recording.path == "/api/events"
        assert recording.status_code == 500

    def test_recording_serialization_to_dict(self):
        """Test that RequestRecording can be serialized to dict."""
        recording = RequestRecording(
            recording_id="test-456",
            timestamp="2025-01-08T10:00:00Z",
            method="GET",
            path="/api/cameras",
            headers={},
            body=None,
            query_params={"limit": "10"},
            status_code=200,
        )

        data = recording.to_dict()

        assert isinstance(data, dict)
        assert data["recording_id"] == "test-456"
        assert data["method"] == "GET"
        assert data["query_params"] == {"limit": "10"}

    def test_recording_deserialization_from_dict(self):
        """Test that RequestRecording can be loaded from dict."""
        data = {
            "recording_id": "test-789",
            "timestamp": "2025-01-08T10:00:00Z",
            "method": "DELETE",
            "path": "/api/events/123",
            "headers": {"authorization": "[REDACTED]"},
            "body": None,
            "query_params": {},
            "status_code": 204,
        }

        recording = RequestRecording.from_dict(data)

        assert recording.recording_id == "test-789"
        assert recording.method == "DELETE"
        assert recording.status_code == 204

    def test_recording_includes_response_body_on_error(self):
        """Test that error responses include response body for debugging."""
        recording = RequestRecording(
            recording_id="err-001",
            timestamp=datetime.now(UTC).isoformat(),
            method="POST",
            path="/api/test",
            headers={},
            body={"data": "test"},
            query_params={},
            status_code=500,
            response_body={"error": "Internal server error", "detail": "Something went wrong"},
        )

        assert recording.response_body is not None
        assert recording.response_body["error"] == "Internal server error"


# =============================================================================
# Redaction Tests
# =============================================================================


class TestRedaction:
    """Tests for sensitive field redaction."""

    def test_redacts_password_field(self):
        """Test that password fields are redacted."""
        body = {"username": "testuser", "password": "secret123"}  # pragma: allowlist secret

        redacted = redact_request_body(body)

        assert redacted["username"] == "testuser"
        assert redacted["password"] == "[REDACTED]"  # noqa: S105  # pragma: allowlist secret

    def test_redacts_api_key_field(self):
        """Test that api_key fields are redacted."""
        body = {"name": "test", "api_key": "sk-123456"}  # pragma: allowlist secret

        redacted = redact_request_body(body)

        assert redacted["name"] == "test"
        assert redacted["api_key"] == "[REDACTED]"  # pragma: allowlist secret

    def test_redacts_token_field(self):
        """Test that token fields are redacted."""
        body = {"access_token": "jwt-token-here", "refresh_token": "refresh-here"}

        redacted = redact_request_body(body)

        assert redacted["access_token"] == "[REDACTED]"  # noqa: S105  # pragma: allowlist secret
        assert redacted["refresh_token"] == "[REDACTED]"  # noqa: S105  # pragma: allowlist secret

    def test_redacts_authorization_header(self):
        """Test that Authorization headers are redacted."""
        headers = {
            "content-type": "application/json",
            "authorization": "Bearer jwt-token-abc123",
        }

        redacted = redact_request_body(headers)

        assert redacted["content-type"] == "application/json"
        assert redacted["authorization"] == "[REDACTED]"

    def test_redacts_nested_sensitive_fields(self):
        """Test that nested sensitive fields are redacted."""
        body = {
            "user": {
                "email": "test@example.com",
                "credentials": {
                    "password": "secret",  # pragma: allowlist secret
                    "api_key": "key123",  # pragma: allowlist secret
                },
            }
        }

        redacted = redact_request_body(body)

        assert redacted["user"]["email"] == "test@example.com"
        # fmt: off
        assert redacted["user"]["credentials"]["password"] == "[REDACTED]"  # noqa: S105  # pragma: allowlist secret
        assert redacted["user"]["credentials"]["api_key"] == "[REDACTED]"  # pragma: allowlist secret
        # fmt: on

    def test_redacts_sensitive_fields_in_arrays(self):
        """Test that sensitive fields in arrays are redacted."""
        body = {
            "users": [
                {"username": "user1", "password": "pass1"},  # pragma: allowlist secret
                {"username": "user2", "password": "pass2"},  # pragma: allowlist secret
            ]
        }

        redacted = redact_request_body(body)

        assert redacted["users"][0]["username"] == "user1"
        assert redacted["users"][0]["password"] == "[REDACTED]"  # noqa: S105  # pragma: allowlist secret
        assert redacted["users"][1]["password"] == "[REDACTED]"  # noqa: S105  # pragma: allowlist secret

    def test_handles_none_body(self):
        """Test that None body returns None."""
        result = redact_request_body(None)
        assert result is None

    def test_handles_non_dict_body(self):
        """Test that non-dict body is returned as-is."""
        result = redact_request_body("plain text body")
        assert result == "plain text body"

    def test_uses_sensitive_field_names_constant(self):
        """Test that redaction uses SENSITIVE_FIELD_NAMES from logging module."""
        from backend.core.logging import SENSITIVE_FIELD_NAMES

        # All fields in SENSITIVE_FIELD_NAMES should be redacted
        body = {field: f"value_{field}" for field in SENSITIVE_FIELD_NAMES if "_url" not in field}

        redacted = redact_request_body(body)

        for field in body:
            if field in SENSITIVE_FIELD_NAMES:
                assert redacted[field] == "[REDACTED]", f"Field {field} should be redacted"


# =============================================================================
# RequestRecorderMiddleware Tests
# =============================================================================


class TestRequestRecorderMiddleware:
    """Tests for RequestRecorderMiddleware class."""

    @pytest.fixture
    def temp_recordings_dir(self):
        """Create a temporary directory for recordings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def app_with_recorder(self, temp_recordings_dir):
        """Create a test FastAPI app with RequestRecorderMiddleware."""
        app = FastAPI()
        app.add_middleware(
            RequestRecorderMiddleware,
            enabled=True,
            sample_rate=0.0,  # Don't sample by default in tests
            max_body_size=10000,
            recordings_dir=temp_recordings_dir,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        @app.post("/create")
        async def create_endpoint():
            return {"id": 123}

        @app.get("/error")
        async def error_endpoint():
            raise ValueError("Test error")

        @app.post("/data")
        async def data_endpoint(body: dict):
            return {"received": body}

        return app

    def test_middleware_does_not_record_successful_requests_by_default(
        self, app_with_recorder, temp_recordings_dir
    ):
        """Test that successful requests are not recorded by default."""
        client = TestClient(app_with_recorder)

        response = client.get("/test")

        assert response.status_code == 200

        # No recordings should exist (sample_rate=0 and status < 500)
        recordings_path = Path(temp_recordings_dir)
        recordings = list(recordings_path.glob("*.json"))
        assert len(recordings) == 0

    def test_middleware_records_error_responses(self, app_with_recorder, temp_recordings_dir):
        """Test that error responses (status >= 500) are recorded."""
        client = TestClient(app_with_recorder, raise_server_exceptions=False)

        response = client.get("/error")

        assert response.status_code == 500

        # Recording should exist for 500 error
        recordings_path = Path(temp_recordings_dir)
        recordings = list(recordings_path.glob("*.json"))
        assert len(recordings) == 1

        # Verify recording content
        with open(recordings[0]) as f:  # nosemgrep: path-traversal-open
            recording_data = json.load(f)

        assert recording_data["method"] == "GET"
        assert recording_data["path"] == "/error"
        assert recording_data["status_code"] == 500

    def test_middleware_records_when_debug_header_present(
        self, app_with_recorder, temp_recordings_dir
    ):
        """Test that requests with X-Debug-Record header are always recorded."""
        client = TestClient(app_with_recorder)

        response = client.get("/test", headers={"X-Debug-Record": "true"})

        assert response.status_code == 200

        # Recording should exist due to debug header
        recordings_path = Path(temp_recordings_dir)
        recordings = list(recordings_path.glob("*.json"))
        assert len(recordings) == 1

    def test_middleware_respects_sample_rate(self, temp_recordings_dir):
        """Test that middleware samples successful requests based on sample_rate."""
        app = FastAPI()
        app.add_middleware(
            RequestRecorderMiddleware,
            enabled=True,
            sample_rate=1.0,  # Record all requests
            recordings_dir=temp_recordings_dir,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)

        response = client.get("/test")

        assert response.status_code == 200

        # Recording should exist due to 100% sample rate
        recordings_path = Path(temp_recordings_dir)
        recordings = list(recordings_path.glob("*.json"))
        assert len(recordings) == 1

    def test_middleware_disabled_does_not_record(self, temp_recordings_dir):
        """Test that disabled middleware does not record any requests."""
        app = FastAPI()
        app.add_middleware(
            RequestRecorderMiddleware,
            enabled=False,
            sample_rate=1.0,  # Would record all if enabled
            recordings_dir=temp_recordings_dir,
        )

        @app.get("/error")
        async def error_endpoint():
            raise ValueError("Test error")

        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/error")

        assert response.status_code == 500

        # No recordings because middleware is disabled
        recordings_path = Path(temp_recordings_dir)
        recordings = list(recordings_path.glob("*.json"))
        assert len(recordings) == 0

    def test_middleware_includes_headers_in_recording(self, app_with_recorder, temp_recordings_dir):
        """Test that request headers are included in recording."""
        client = TestClient(app_with_recorder)

        response = client.get(
            "/test",
            headers={
                "X-Debug-Record": "true",
                "User-Agent": "TestClient/1.0",
                "Accept": "application/json",
            },
        )

        assert response.status_code == 200

        recordings_path = Path(temp_recordings_dir)
        recordings = list(recordings_path.glob("*.json"))
        with open(recordings[0]) as f:  # nosemgrep: path-traversal-open
            recording_data = json.load(f)

        assert "user-agent" in recording_data["headers"]

    def test_middleware_redacts_sensitive_headers(self, app_with_recorder, temp_recordings_dir):
        """Test that sensitive headers (Authorization) are redacted."""
        client = TestClient(app_with_recorder)

        response = client.get(
            "/test",
            headers={
                "X-Debug-Record": "true",
                "Authorization": "Bearer secret-token",
            },
        )

        assert response.status_code == 200

        recordings_path = Path(temp_recordings_dir)
        recordings = list(recordings_path.glob("*.json"))
        with open(recordings[0]) as f:  # nosemgrep: path-traversal-open
            recording_data = json.load(f)

        assert recording_data["headers"]["authorization"] == "[REDACTED]"

    def test_middleware_includes_query_params(self, app_with_recorder, temp_recordings_dir):
        """Test that query parameters are included in recording."""
        client = TestClient(app_with_recorder)

        response = client.get(
            "/test",
            params={"page": "1", "limit": "10"},
            headers={"X-Debug-Record": "true"},
        )

        assert response.status_code == 200

        recordings_path = Path(temp_recordings_dir)
        recordings = list(recordings_path.glob("*.json"))
        with open(recordings[0]) as f:  # nosemgrep: path-traversal-open
            recording_data = json.load(f)

        assert recording_data["query_params"]["page"] == "1"
        assert recording_data["query_params"]["limit"] == "10"

    def test_middleware_truncates_large_body(self, temp_recordings_dir):
        """Test that large request bodies are truncated."""
        app = FastAPI()
        app.add_middleware(
            RequestRecorderMiddleware,
            enabled=True,
            sample_rate=1.0,
            max_body_size=100,  # Very small limit
            recordings_dir=temp_recordings_dir,
        )

        @app.post("/data")
        async def data_endpoint(request: Request):
            await request.body()  # Just consume the body
            return {"received": True}

        client = TestClient(app)

        # Send a large body
        large_body = {"data": "x" * 1000}
        response = client.post("/data", json=large_body)

        assert response.status_code == 200

        recordings_path = Path(temp_recordings_dir)
        recordings = list(recordings_path.glob("*.json"))
        with open(recordings[0]) as f:  # nosemgrep: path-traversal-open
            recording_data = json.load(f)

        # Body should be truncated
        assert recording_data.get("body_truncated", False) is True

    def test_middleware_generates_unique_recording_id(self, app_with_recorder, temp_recordings_dir):
        """Test that each recording gets a unique ID."""
        client = TestClient(app_with_recorder)

        # Make two requests
        client.get("/test", headers={"X-Debug-Record": "true"})
        client.get("/test", headers={"X-Debug-Record": "true"})

        recordings_path = Path(temp_recordings_dir)
        recordings = list(recordings_path.glob("*.json"))
        assert len(recordings) == 2

        # Recording IDs should be different
        ids = []
        for recording_path in recordings:
            with open(recording_path) as f:  # nosemgrep: path-traversal-open
                data = json.load(f)
                ids.append(data["recording_id"])

        assert ids[0] != ids[1]

    def test_recording_id_returned_in_response_header(self, temp_recordings_dir):
        """Test that recording ID is returned in X-Recording-ID header for sampled requests."""
        app = FastAPI()
        app.add_middleware(
            RequestRecorderMiddleware,
            enabled=True,
            sample_rate=1.0,  # Always sample
            recordings_dir=temp_recordings_dir,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-Recording-ID" in response.headers
        # Recording ID should be a non-empty string
        assert len(response.headers["X-Recording-ID"]) > 0


# =============================================================================
# Configuration Tests
# =============================================================================


class TestRequestRecorderConfiguration:
    """Tests for middleware configuration options."""

    def test_default_configuration_values(self):
        """Test that default configuration values are sensible."""
        app = FastAPI()
        middleware = RequestRecorderMiddleware(app)

        # Default should be disabled (safe default for production)
        assert middleware.enabled is False
        # Default sample rate should be low
        assert middleware.sample_rate == 0.01
        # Default max body size should be reasonable
        assert middleware.max_body_size == 10000

    def test_loads_configuration_from_settings(self):
        """Test that middleware loads configuration from settings."""
        with patch("backend.api.middleware.request_recorder.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                request_recording_enabled=True,
                request_recording_sample_rate=0.05,
                request_recording_max_body_size=5000,
            )

            app = FastAPI()
            middleware = RequestRecorderMiddleware(app)

            assert middleware.enabled is True
            assert middleware.sample_rate == 0.05
            assert middleware.max_body_size == 5000

    def test_explicit_config_overrides_settings(self):
        """Test that explicit configuration overrides settings."""
        with patch("backend.api.middleware.request_recorder.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                request_recording_enabled=False,
                request_recording_sample_rate=0.01,
                request_recording_max_body_size=10000,
            )

            app = FastAPI()
            middleware = RequestRecorderMiddleware(
                app,
                enabled=True,  # Override settings
                sample_rate=0.5,  # Override settings
            )

            assert middleware.enabled is True
            assert middleware.sample_rate == 0.5


# =============================================================================
# Storage Tests
# =============================================================================


class TestRecordingStorage:
    """Tests for recording storage functionality."""

    @pytest.fixture
    def temp_recordings_dir(self):
        """Create a temporary directory for recordings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_recordings_stored_in_configured_directory(self, temp_recordings_dir):
        """Test that recordings are stored in the configured directory."""
        app = FastAPI()
        app.add_middleware(
            RequestRecorderMiddleware,
            enabled=True,
            sample_rate=1.0,
            recordings_dir=temp_recordings_dir,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        client.get("/test")

        recordings_path = Path(temp_recordings_dir)
        recordings = list(recordings_path.glob("*.json"))
        assert len(recordings) == 1

    def test_recording_filename_includes_timestamp(self, temp_recordings_dir):
        """Test that recording filename includes timestamp for sorting."""
        app = FastAPI()
        app.add_middleware(
            RequestRecorderMiddleware,
            enabled=True,
            sample_rate=1.0,
            recordings_dir=temp_recordings_dir,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        client.get("/test")

        recordings_path = Path(temp_recordings_dir)
        recordings = list(recordings_path.glob("*.json"))
        assert len(recordings) == 1

        # Filename should contain date-like pattern
        filename = recordings[0].name
        # Expecting format like: 2025-01-08T10-30-00_abc123.json
        assert "-" in filename

    def test_creates_recordings_directory_if_not_exists(self, temp_recordings_dir):
        """Test that recordings directory is created if it doesn't exist."""
        new_dir = Path(temp_recordings_dir) / "nested" / "recordings"

        app = FastAPI()
        app.add_middleware(
            RequestRecorderMiddleware,
            enabled=True,
            sample_rate=1.0,
            recordings_dir=str(new_dir),
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        client.get("/test")

        assert new_dir.exists()
        recordings = list(new_dir.glob("*.json"))
        assert len(recordings) == 1


# =============================================================================
# Edge Cases
# =============================================================================


class TestRequestRecorderEdgeCases:
    """Edge case tests for request recorder middleware."""

    @pytest.fixture
    def temp_recordings_dir(self):
        """Create a temporary directory for recordings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_handles_binary_request_body(self, temp_recordings_dir):
        """Test handling of binary request bodies."""
        app = FastAPI()
        app.add_middleware(
            RequestRecorderMiddleware,
            enabled=True,
            sample_rate=1.0,
            recordings_dir=temp_recordings_dir,
        )

        @app.post("/upload")
        async def upload_endpoint(request: Request):
            await request.body()
            return {"received": True}

        client = TestClient(app)
        response = client.post(
            "/upload",
            content=b"\x00\x01\x02\x03",  # Binary data
            headers={"Content-Type": "application/octet-stream"},
        )

        assert response.status_code == 200

        # Recording should handle binary gracefully
        recordings_path = Path(temp_recordings_dir)
        recordings = list(recordings_path.glob("*.json"))
        assert len(recordings) == 1

    def test_handles_empty_request_body(self, temp_recordings_dir):
        """Test handling of empty request bodies."""
        app = FastAPI()
        app.add_middleware(
            RequestRecorderMiddleware,
            enabled=True,
            sample_rate=1.0,
            recordings_dir=temp_recordings_dir,
        )

        @app.post("/empty")
        async def empty_endpoint():
            return {"received": True}

        client = TestClient(app)
        response = client.post("/empty")

        assert response.status_code == 200

        recordings_path = Path(temp_recordings_dir)
        recordings = list(recordings_path.glob("*.json"))
        assert len(recordings) == 1

    def test_handles_multipart_form_data(self, temp_recordings_dir):
        """Test handling of multipart form data requests."""
        app = FastAPI()
        app.add_middleware(
            RequestRecorderMiddleware,
            enabled=True,
            sample_rate=1.0,
            recordings_dir=temp_recordings_dir,
        )

        @app.post("/form")
        async def form_endpoint(request: Request):
            form = await request.form()
            return {"fields": list(form.keys())}

        client = TestClient(app)
        response = client.post(
            "/form",
            data={"field1": "value1", "field2": "value2"},
        )

        assert response.status_code == 200

        recordings_path = Path(temp_recordings_dir)
        recordings = list(recordings_path.glob("*.json"))
        assert len(recordings) == 1

    def test_does_not_block_on_storage_failure(self, temp_recordings_dir):
        """Test that storage failures don't block request processing."""
        app = FastAPI()
        app.add_middleware(
            RequestRecorderMiddleware,
            enabled=True,
            sample_rate=1.0,
            recordings_dir="/nonexistent/readonly/path",  # Will fail to write
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)

        # Request should succeed even if recording fails
        response = client.get("/test")
        assert response.status_code == 200

    def test_websocket_requests_not_recorded(self, temp_recordings_dir):
        """Test that WebSocket requests are not recorded."""
        from fastapi import WebSocket as FastAPIWebSocket

        app = FastAPI()
        app.add_middleware(
            RequestRecorderMiddleware,
            enabled=True,
            sample_rate=1.0,
            recordings_dir=temp_recordings_dir,
        )

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: FastAPIWebSocket):
            await websocket.accept()
            await websocket.send_text("Hello")
            await websocket.close()

        with TestClient(app) as client:
            try:
                with client.websocket_connect("/ws") as ws:
                    data = ws.receive_text()
                    assert data == "Hello"
            except Exception:
                # WebSocket handling varies by test client - expected to fail in some cases
                pass

        # No recordings for WebSocket - connections bypass BaseHTTPMiddleware
        recordings_path = Path(temp_recordings_dir)
        assert len(list(recordings_path.glob("*.json"))) == 0


# =============================================================================
# Replay Endpoint Tests
# =============================================================================


class TestReplayEndpoint:
    """Tests for the debug replay endpoint.

    Note: Replay tests that involve actual HTTP requests are complex because
    they require the httpx client to make real HTTP calls. These tests focus
    on the endpoint's API contract and error handling rather than full
    end-to-end replay functionality.
    """

    @pytest.fixture
    def temp_recordings_dir(self):
        """Create a temporary directory for recordings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def app_with_replay(self, temp_recordings_dir):
        """Create app with replay endpoint enabled."""
        from backend.api.routes.debug import router as debug_router

        app = FastAPI()
        app.include_router(debug_router)

        # Create a test recording
        recording_data = {
            "recording_id": "test-recording-123",
            "timestamp": "2025-01-08T10:00:00Z",
            "method": "POST",
            "path": "/api/events",
            "headers": {"content-type": "application/json"},
            "body": {"event_id": "abc123"},
            "query_params": {},
            "status_code": 500,
        }

        recordings_path = Path(temp_recordings_dir)
        recording_file = recordings_path / "test-recording-123.json"
        with open(recording_file, "w") as f:  # nosemgrep: path-traversal-open
            json.dump(recording_data, f)

        return app, temp_recordings_dir

    def test_replay_returns_404_when_debug_disabled(self):
        """Test that replay endpoint returns 404 when debug mode disabled."""
        from backend.api.routes.debug import router as debug_router

        app = FastAPI()
        app.include_router(debug_router)

        with patch("backend.api.routes.debug.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(debug=False)

            client = TestClient(app)
            response = client.post("/api/debug/replay/test-123")

            assert response.status_code == 404

    def test_replay_returns_404_for_nonexistent_recording(self, app_with_replay):
        """Test that replay returns 404 for nonexistent recording."""
        app, recordings_dir = app_with_replay

        with patch("backend.api.routes.debug.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(debug=True)
            with patch("backend.api.routes.debug.RECORDINGS_DIR", recordings_dir):
                client = TestClient(app)
                response = client.post("/api/debug/replay/nonexistent-id")

                assert response.status_code == 404
                assert "not found" in response.json()["detail"].lower()

    def test_replay_reconstructs_and_executes_request(self, app_with_replay):
        """Test that replay reconstructs and executes the recorded request.

        Note: This test mocks httpx to avoid real HTTP requests.
        """
        import httpx

        app, recordings_dir = app_with_replay

        with patch("backend.api.routes.debug.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(debug=True)
            with patch("backend.api.routes.debug.RECORDINGS_DIR", recordings_dir):
                # Mock httpx to return a successful response
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"replayed": True, "original_event_id": "abc123"}

                with patch.object(
                    httpx.AsyncClient, "request", new_callable=AsyncMock
                ) as mock_request:
                    mock_request.return_value = mock_response

                    client = TestClient(app)
                    response = client.post("/api/debug/replay/test-recording-123")

                    # Should return the result of replaying the request
                    assert response.status_code == 200
                    result = response.json()
                    assert "replay_status_code" in result
                    assert result["replay_status_code"] == 200

    def test_replay_includes_original_headers(self, temp_recordings_dir):
        """Test that replay includes headers from original request.

        Note: This test mocks httpx and verifies headers were passed correctly.
        """
        import httpx

        from backend.api.routes.debug import router as debug_router

        app = FastAPI()
        app.include_router(debug_router)

        # Create recording with custom headers
        recording_data = {
            "recording_id": "header-test",
            "timestamp": "2025-01-08T10:00:00Z",
            "method": "GET",
            "path": "/api/test",
            "headers": {
                "x-custom-header": "custom-value",
                "content-type": "application/json",
            },
            "body": None,
            "query_params": {},
            "status_code": 200,
        }

        recordings_path = Path(temp_recordings_dir)
        recording_file = recordings_path / "header-test.json"
        with open(recording_file, "w") as f:  # nosemgrep: path-traversal-open
            json.dump(recording_data, f)

        with patch("backend.api.routes.debug.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(debug=True)
            with patch("backend.api.routes.debug.RECORDINGS_DIR", temp_recordings_dir):
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"ok": True}

                with patch.object(
                    httpx.AsyncClient, "request", new_callable=AsyncMock
                ) as mock_request:
                    mock_request.return_value = mock_response

                    client = TestClient(app)
                    response = client.post("/api/debug/replay/header-test")

                    assert response.status_code == 200
                    # Verify httpx was called with custom headers
                    call_args = mock_request.call_args
                    assert call_args is not None
                    passed_headers = call_args.kwargs.get("headers", {})
                    assert passed_headers.get("x-custom-header") == "custom-value"

    def test_replay_includes_query_params(self, temp_recordings_dir):
        """Test that replay includes query parameters from original request.

        Note: This test mocks httpx and verifies query params were passed correctly.
        """
        import httpx

        from backend.api.routes.debug import router as debug_router

        app = FastAPI()
        app.include_router(debug_router)

        # Create recording with query params
        recording_data = {
            "recording_id": "query-test",
            "timestamp": "2025-01-08T10:00:00Z",
            "method": "GET",
            "path": "/api/search",
            "headers": {},
            "body": None,
            "query_params": {"q": "test", "page": "2"},
            "status_code": 200,
        }

        recordings_path = Path(temp_recordings_dir)
        recording_file = recordings_path / "query-test.json"
        with open(recording_file, "w") as f:  # nosemgrep: path-traversal-open
            json.dump(recording_data, f)

        with patch("backend.api.routes.debug.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(debug=True)
            with patch("backend.api.routes.debug.RECORDINGS_DIR", temp_recordings_dir):
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"ok": True}

                with patch.object(
                    httpx.AsyncClient, "request", new_callable=AsyncMock
                ) as mock_request:
                    mock_request.return_value = mock_response

                    client = TestClient(app)
                    response = client.post("/api/debug/replay/query-test")

                    assert response.status_code == 200
                    # Verify httpx was called with URL containing query params
                    call_args = mock_request.call_args
                    assert call_args is not None
                    url = call_args.kwargs.get("url", "")
                    assert "q=test" in url
                    assert "page=2" in url

    def test_replay_response_includes_metadata(self, app_with_replay):
        """Test that replay response includes metadata about the replay."""
        import httpx

        app, recordings_dir = app_with_replay

        with patch("backend.api.routes.debug.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(debug=True)
            with patch("backend.api.routes.debug.RECORDINGS_DIR", recordings_dir):
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"status": "created"}

                with patch.object(
                    httpx.AsyncClient, "request", new_callable=AsyncMock
                ) as mock_request:
                    mock_request.return_value = mock_response

                    client = TestClient(app)
                    response = client.post("/api/debug/replay/test-recording-123")

                    assert response.status_code == 200
                    result = response.json()
                    # Response should include replay metadata
                    assert "replay_metadata" in result
                    assert "original_path" in result["replay_metadata"]
                    assert "replay_duration_ms" in result["replay_metadata"]
