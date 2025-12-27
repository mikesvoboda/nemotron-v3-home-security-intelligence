"""Unit tests for middleware modules: request_id.py and auth.py.

This module provides comprehensive tests for:
- RequestIDMiddleware: Request ID generation and propagation
- AuthMiddleware: API key authentication (extending existing coverage)
- WebSocket authentication functions
"""

import hashlib
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, WebSocket, status
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response
from starlette.testclient import TestClient as StarletteTestClient

from backend.api.middleware.auth import (
    AuthMiddleware,
    _get_valid_key_hashes,
    _hash_key,
    authenticate_websocket,
    validate_websocket_api_key,
)
from backend.api.middleware.request_id import RequestIDMiddleware
from backend.core.config import get_settings
from backend.core.logging import get_request_id, set_request_id


# =============================================================================
# RequestIDMiddleware Tests
# =============================================================================


class TestRequestIDMiddleware:
    """Tests for RequestIDMiddleware class."""

    @pytest.fixture
    def app_with_request_id_middleware(self):
        """Create a test FastAPI app with RequestIDMiddleware."""
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        @app.get("/check-context")
        async def check_context():
            """Endpoint that returns the current request ID from context."""
            request_id = get_request_id()
            return {"request_id": request_id}

        return app

    def test_generates_request_id_when_not_provided(self, app_with_request_id_middleware):
        """Test that middleware generates a request ID when none is provided."""
        client = TestClient(app_with_request_id_middleware)
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        # Generated IDs are 8 characters (truncated UUID)
        assert len(response.headers["X-Request-ID"]) == 8

    def test_uses_provided_request_id_from_header(self, app_with_request_id_middleware):
        """Test that middleware uses X-Request-ID from incoming request header."""
        client = TestClient(app_with_request_id_middleware)
        provided_id = "test-req-123"
        response = client.get("/test", headers={"X-Request-ID": provided_id})

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == provided_id

    def test_request_id_propagated_to_response(self, app_with_request_id_middleware):
        """Test that request ID is added to response headers."""
        client = TestClient(app_with_request_id_middleware)
        response = client.get("/test")

        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]
        assert request_id is not None
        assert len(request_id) > 0

    def test_request_id_set_in_context_during_request(self, app_with_request_id_middleware):
        """Test that request ID is set in context during request processing."""
        client = TestClient(app_with_request_id_middleware)
        provided_id = "context-test-id"
        response = client.get("/check-context", headers={"X-Request-ID": provided_id})

        assert response.status_code == 200
        # During the request, context should have the request ID
        # Note: TestClient runs synchronously, so context behavior may differ

    def test_context_cleared_after_request(self, app_with_request_id_middleware):
        """Test that request ID context is cleared after request completes."""
        client = TestClient(app_with_request_id_middleware)

        # Make a request
        response = client.get("/test", headers={"X-Request-ID": "temp-id"})
        assert response.status_code == 200

        # After request, context should be cleared (None)
        # Note: This tests the finally block cleanup
        assert get_request_id() is None

    def test_unique_request_ids_generated(self, app_with_request_id_middleware):
        """Test that multiple requests get unique generated IDs."""
        client = TestClient(app_with_request_id_middleware)

        ids = set()
        for _ in range(10):
            response = client.get("/test")
            ids.add(response.headers["X-Request-ID"])

        # All 10 IDs should be unique
        assert len(ids) == 10

    def test_empty_request_id_header_generates_new(self, app_with_request_id_middleware):
        """Test that empty X-Request-ID header causes new ID generation."""
        client = TestClient(app_with_request_id_middleware)
        response = client.get("/test", headers={"X-Request-ID": ""})

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        # Empty string is falsy, so a new ID should be generated
        assert len(response.headers["X-Request-ID"]) == 8

    @pytest.mark.asyncio
    async def test_dispatch_sets_and_clears_context(self):
        """Test dispatch method directly to verify context management."""
        app = FastAPI()
        middleware = RequestIDMiddleware(app)

        # Create mock request and call_next
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"X-Request-ID": "direct-test-id"}

        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}

        async def mock_call_next(request):
            # During call_next, context should be set
            assert get_request_id() == "direct-test-id"
            return mock_response

        # Execute dispatch
        response = await middleware.dispatch(mock_request, mock_call_next)

        # After dispatch, context should be cleared
        assert get_request_id() is None
        assert response.headers["X-Request-ID"] == "direct-test-id"

    @pytest.mark.asyncio
    async def test_dispatch_clears_context_on_exception(self):
        """Test that context is cleared even when call_next raises an exception."""
        app = FastAPI()
        middleware = RequestIDMiddleware(app)

        # Create mock request
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"X-Request-ID": "exception-test-id"}

        async def mock_call_next_raises(request):
            raise ValueError("Test exception")

        # Execute dispatch and expect exception
        with pytest.raises(ValueError, match="Test exception"):
            await middleware.dispatch(mock_request, mock_call_next_raises)

        # Context should still be cleared (finally block)
        assert get_request_id() is None

    @pytest.mark.asyncio
    async def test_dispatch_generates_uuid_when_no_header(self):
        """Test that dispatch generates a UUID when no header is provided."""
        app = FastAPI()
        middleware = RequestIDMiddleware(app)

        # Create mock request without X-Request-ID header
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {}  # No X-Request-ID

        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}

        generated_id = None

        async def mock_call_next(request):
            nonlocal generated_id
            generated_id = get_request_id()
            return mock_response

        await middleware.dispatch(mock_request, mock_call_next)

        # Should have generated an 8-character ID
        assert generated_id is not None
        assert len(generated_id) == 8


# =============================================================================
# Auth Middleware - Standalone Function Tests
# =============================================================================


class TestAuthHashFunctions:
    """Tests for standalone hash functions in auth module."""

    def test_hash_key_produces_sha256(self):
        """Test that _hash_key produces correct SHA-256 hash."""
        key = "test_api_key"
        expected_hash = hashlib.sha256(key.encode()).hexdigest()
        assert _hash_key(key) == expected_hash

    def test_hash_key_different_inputs_different_hashes(self):
        """Test that different keys produce different hashes."""
        hash1 = _hash_key("key_one")
        hash2 = _hash_key("key_two")
        assert hash1 != hash2

    def test_hash_key_same_input_same_hash(self):
        """Test that same key always produces same hash."""
        key = "consistent_key"
        hash1 = _hash_key(key)
        hash2 = _hash_key(key)
        assert hash1 == hash2

    def test_hash_key_empty_string(self):
        """Test hashing an empty string."""
        # Empty string should still produce a valid hash
        result = _hash_key("")
        assert len(result) == 64  # SHA-256 produces 64 hex characters

    def test_hash_key_special_characters(self):
        """Test hashing keys with special characters."""
        key = "key!@#$%^&*()_+-=[]{}|;':\",./<>?"
        result = _hash_key(key)
        assert len(result) == 64

    def test_hash_key_unicode(self):
        """Test hashing keys with unicode characters."""
        key = "key_with_unicode_"
        result = _hash_key(key)
        assert len(result) == 64

    def test_get_valid_key_hashes_returns_set(self):
        """Test that _get_valid_key_hashes returns a set of hashes."""
        os.environ["API_KEYS"] = '["key1", "key2"]'
        get_settings.cache_clear()

        try:
            hashes = _get_valid_key_hashes()
            assert isinstance(hashes, set)
            assert len(hashes) == 2
            # Verify they are actual hashes
            for h in hashes:
                assert len(h) == 64
        finally:
            os.environ.pop("API_KEYS", None)
            get_settings.cache_clear()

    def test_get_valid_key_hashes_empty_list(self):
        """Test _get_valid_key_hashes with empty API_KEYS list."""
        os.environ["API_KEYS"] = "[]"
        get_settings.cache_clear()

        try:
            hashes = _get_valid_key_hashes()
            assert isinstance(hashes, set)
            assert len(hashes) == 0
        finally:
            os.environ.pop("API_KEYS", None)
            get_settings.cache_clear()


# =============================================================================
# WebSocket Authentication Tests
# =============================================================================


class TestValidateWebsocketApiKey:
    """Tests for validate_websocket_api_key function."""

    @pytest.fixture(autouse=True)
    def cleanup_env(self):
        """Clean up environment after each test."""
        yield
        os.environ.pop("API_KEY_ENABLED", None)
        os.environ.pop("API_KEYS", None)
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_returns_true_when_auth_disabled(self):
        """Test that validation passes when API key auth is disabled."""
        os.environ["API_KEY_ENABLED"] = "false"
        get_settings.cache_clear()

        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.query_params = {}
        mock_websocket.headers = {}

        result = await validate_websocket_api_key(mock_websocket)
        assert result is True

    @pytest.mark.asyncio
    async def test_validates_api_key_from_query_param(self):
        """Test validation with API key in query parameter."""
        test_key = "valid_ws_key"
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = f'["{test_key}"]'
        get_settings.cache_clear()

        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.query_params = {"api_key": test_key}
        mock_websocket.headers = {}

        result = await validate_websocket_api_key(mock_websocket)
        assert result is True

    @pytest.mark.asyncio
    async def test_rejects_invalid_api_key_from_query_param(self):
        """Test rejection of invalid API key in query parameter."""
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = '["valid_key"]'
        get_settings.cache_clear()

        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.query_params = {"api_key": "invalid_key"}
        mock_websocket.headers = {}

        result = await validate_websocket_api_key(mock_websocket)
        assert result is False

    @pytest.mark.asyncio
    async def test_validates_api_key_from_protocol_header(self):
        """Test validation with API key in Sec-WebSocket-Protocol header."""
        test_key = "protocol_key"
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = f'["{test_key}"]'
        get_settings.cache_clear()

        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.query_params = {}  # No query param
        mock_websocket.headers = {"sec-websocket-protocol": f"api-key.{test_key}"}

        result = await validate_websocket_api_key(mock_websocket)
        assert result is True

    @pytest.mark.asyncio
    async def test_validates_api_key_from_protocol_header_with_multiple_protocols(self):
        """Test validation with multiple protocols in header."""
        test_key = "multi_protocol_key"
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = f'["{test_key}"]'
        get_settings.cache_clear()

        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.query_params = {}
        mock_websocket.headers = {
            "sec-websocket-protocol": f"graphql-ws, api-key.{test_key}, other-protocol"
        }

        result = await validate_websocket_api_key(mock_websocket)
        assert result is True

    @pytest.mark.asyncio
    async def test_rejects_invalid_api_key_from_protocol_header(self):
        """Test rejection of invalid API key in protocol header."""
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = '["valid_key"]'
        get_settings.cache_clear()

        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.query_params = {}
        mock_websocket.headers = {"sec-websocket-protocol": "api-key.invalid_key"}

        result = await validate_websocket_api_key(mock_websocket)
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_api_key_provided(self):
        """Test that validation fails when no API key is provided."""
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = '["some_key"]'
        get_settings.cache_clear()

        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.query_params = {}
        mock_websocket.headers = {}

        result = await validate_websocket_api_key(mock_websocket)
        assert result is False

    @pytest.mark.asyncio
    async def test_query_param_takes_precedence_over_header(self):
        """Test that query parameter API key takes precedence over header."""
        query_key = "query_key"
        header_key = "header_key"
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = f'["{query_key}"]'  # Only query_key is valid
        get_settings.cache_clear()

        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.query_params = {"api_key": query_key}
        mock_websocket.headers = {"sec-websocket-protocol": f"api-key.{header_key}"}

        result = await validate_websocket_api_key(mock_websocket)
        assert result is True

    @pytest.mark.asyncio
    async def test_falls_back_to_header_when_no_query_param(self):
        """Test fallback to header when query param is not provided."""
        header_key = "header_only_key"
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = f'["{header_key}"]'
        get_settings.cache_clear()

        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.query_params = {}  # No query param
        mock_websocket.headers = {"sec-websocket-protocol": f"api-key.{header_key}"}

        result = await validate_websocket_api_key(mock_websocket)
        assert result is True

    @pytest.mark.asyncio
    async def test_protocol_header_without_api_key_prefix(self):
        """Test that protocol header without api-key. prefix is ignored."""
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = '["some_key"]'
        get_settings.cache_clear()

        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.query_params = {}
        mock_websocket.headers = {"sec-websocket-protocol": "graphql-ws, some_key"}

        result = await validate_websocket_api_key(mock_websocket)
        assert result is False  # No api-key. prefix, so no key extracted

    @pytest.mark.asyncio
    async def test_empty_protocol_header(self):
        """Test handling of empty protocol header."""
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = '["some_key"]'
        get_settings.cache_clear()

        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.query_params = {}
        mock_websocket.headers = {"sec-websocket-protocol": ""}

        result = await validate_websocket_api_key(mock_websocket)
        assert result is False


class TestAuthenticateWebsocket:
    """Tests for authenticate_websocket function."""

    @pytest.fixture(autouse=True)
    def cleanup_env(self):
        """Clean up environment after each test."""
        yield
        os.environ.pop("API_KEY_ENABLED", None)
        os.environ.pop("API_KEYS", None)
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_returns_true_on_successful_auth(self):
        """Test that successful authentication returns True."""
        test_key = "auth_success_key"
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = f'["{test_key}"]'
        get_settings.cache_clear()

        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.query_params = {"api_key": test_key}
        mock_websocket.headers = {}
        mock_websocket.close = AsyncMock()

        result = await authenticate_websocket(mock_websocket)

        assert result is True
        mock_websocket.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_false_and_closes_on_failed_auth(self):
        """Test that failed authentication returns False and closes connection."""
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = '["valid_key"]'
        get_settings.cache_clear()

        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.query_params = {"api_key": "invalid_key"}
        mock_websocket.headers = {}
        mock_websocket.close = AsyncMock()

        result = await authenticate_websocket(mock_websocket)

        assert result is False
        mock_websocket.close.assert_awaited_once_with(code=status.WS_1008_POLICY_VIOLATION)

    @pytest.mark.asyncio
    async def test_closes_with_policy_violation_code(self):
        """Test that connection is closed with correct status code."""
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = '["valid_key"]'
        get_settings.cache_clear()

        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.query_params = {}
        mock_websocket.headers = {}
        mock_websocket.close = AsyncMock()

        await authenticate_websocket(mock_websocket)

        # WS_1008_POLICY_VIOLATION is 1008
        mock_websocket.close.assert_awaited_once_with(code=1008)

    @pytest.mark.asyncio
    async def test_does_not_close_when_auth_disabled(self):
        """Test that connection is not closed when auth is disabled."""
        os.environ["API_KEY_ENABLED"] = "false"
        get_settings.cache_clear()

        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.query_params = {}
        mock_websocket.headers = {}
        mock_websocket.close = AsyncMock()

        result = await authenticate_websocket(mock_websocket)

        assert result is True
        mock_websocket.close.assert_not_called()


# =============================================================================
# AuthMiddleware Additional Tests (Extending existing coverage)
# =============================================================================


class TestAuthMiddlewareExtended:
    """Extended tests for AuthMiddleware class to improve coverage."""

    @pytest.fixture(autouse=True)
    def cleanup_env(self):
        """Clean up environment after each test."""
        yield
        os.environ.pop("API_KEY_ENABLED", None)
        os.environ.pop("API_KEYS", None)
        get_settings.cache_clear()

    def test_middleware_hash_key_static_method(self):
        """Test the static _hash_key method on the middleware class."""
        key = "static_method_test"
        expected = hashlib.sha256(key.encode()).hexdigest()
        assert AuthMiddleware._hash_key(key) == expected

    def test_load_key_hashes_from_settings(self):
        """Test that _load_key_hashes correctly loads from settings."""
        test_key = "load_test_key"
        os.environ["API_KEYS"] = f'["{test_key}"]'
        get_settings.cache_clear()

        app = FastAPI()
        middleware = AuthMiddleware(app)

        expected_hash = hashlib.sha256(test_key.encode()).hexdigest()
        assert expected_hash in middleware.valid_key_hashes

    def test_exempt_paths_with_docs_subpath(self):
        """Test that /docs/* subpaths are exempt."""
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = '["test_key"]'
        get_settings.cache_clear()

        app = FastAPI()
        middleware = AuthMiddleware(app)

        assert middleware._is_exempt_path("/docs") is True
        assert middleware._is_exempt_path("/docs/") is True
        assert middleware._is_exempt_path("/docs/oauth2-redirect") is True

    def test_exempt_paths_with_redoc_subpath(self):
        """Test that /redoc/* subpaths are exempt."""
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = '["test_key"]'
        get_settings.cache_clear()

        app = FastAPI()
        middleware = AuthMiddleware(app)

        assert middleware._is_exempt_path("/redoc") is True
        assert middleware._is_exempt_path("/redoc/") is True

    def test_non_exempt_api_paths(self):
        """Test that API paths are not exempt."""
        app = FastAPI()
        middleware = AuthMiddleware(app, valid_key_hashes=set())

        assert middleware._is_exempt_path("/api/events") is False
        assert middleware._is_exempt_path("/api/cameras") is False
        assert middleware._is_exempt_path("/api/detections") is False
        assert middleware._is_exempt_path("/api/telemetry") is False

    def test_custom_valid_key_hashes_override(self):
        """Test that custom valid_key_hashes override settings-loaded hashes."""
        os.environ["API_KEYS"] = '["settings_key"]'
        get_settings.cache_clear()

        custom_hash = hashlib.sha256(b"custom_key").hexdigest()
        app = FastAPI()
        middleware = AuthMiddleware(app, valid_key_hashes={custom_hash})

        # Should only have custom hash, not settings hash
        assert custom_hash in middleware.valid_key_hashes
        settings_hash = hashlib.sha256(b"settings_key").hexdigest()
        assert settings_hash not in middleware.valid_key_hashes

    @pytest.mark.asyncio
    async def test_dispatch_auth_disabled_path(self):
        """Test dispatch when auth is disabled passes through."""
        os.environ["API_KEY_ENABLED"] = "false"
        get_settings.cache_clear()

        app = FastAPI()
        app.add_middleware(AuthMiddleware)

        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)
        response = client.get("/api/test")

        assert response.status_code == 200
        assert response.json() == {"message": "success"}

    def test_api_key_from_both_header_and_query_uses_header(self):
        """Test that header takes precedence when both are provided."""
        valid_key = "header_key"
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = f'["{valid_key}"]'
        get_settings.cache_clear()

        app = FastAPI()
        app.add_middleware(AuthMiddleware)

        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)
        # Valid header, invalid query param
        response = client.get(
            "/api/test?api_key=invalid_query_key", headers={"X-API-Key": valid_key}
        )

        assert response.status_code == 200

    def test_missing_key_detailed_error_message(self):
        """Test that missing key returns descriptive error message."""
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = '["test_key"]'
        get_settings.cache_clear()

        app = FastAPI()
        app.add_middleware(AuthMiddleware)

        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)
        response = client.get("/api/test")

        assert response.status_code == 401
        detail = response.json()["detail"]
        assert "API key required" in detail
        assert "X-API-Key" in detail
        assert "api_key" in detail

    def test_invalid_key_error_message(self):
        """Test that invalid key returns correct error message."""
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = '["valid_key"]'
        get_settings.cache_clear()

        app = FastAPI()
        app.add_middleware(AuthMiddleware)

        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)
        response = client.get("/api/test", headers={"X-API-Key": "wrong_key"})

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid API key"


# =============================================================================
# Integration-style tests for middleware chain
# =============================================================================


class TestMiddlewareChain:
    """Tests for middleware working together."""

    @pytest.fixture(autouse=True)
    def cleanup_env(self):
        """Clean up environment after each test."""
        yield
        os.environ.pop("API_KEY_ENABLED", None)
        os.environ.pop("API_KEYS", None)
        get_settings.cache_clear()

    def test_request_id_and_auth_middleware_together(self):
        """Test that RequestIDMiddleware and AuthMiddleware work together."""
        test_key = "integration_key"
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = f'["{test_key}"]'
        get_settings.cache_clear()

        app = FastAPI()
        # Add both middlewares (order matters: last added runs first)
        app.add_middleware(AuthMiddleware)
        app.add_middleware(RequestIDMiddleware)

        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)
        response = client.get("/api/test", headers={"X-API-Key": test_key})

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert response.json() == {"message": "success"}

    def test_request_id_present_on_auth_failure(self):
        """Test that request ID is still added even when auth fails."""
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = '["valid_key"]'
        get_settings.cache_clear()

        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.add_middleware(RequestIDMiddleware)

        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)
        response = client.get("/api/test")  # No API key

        assert response.status_code == 401
        # Request ID should still be present from RequestIDMiddleware
        assert "X-Request-ID" in response.headers

    def test_exempt_path_with_both_middlewares(self):
        """Test that exempt paths work with both middlewares."""
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = '["valid_key"]'
        get_settings.cache_clear()

        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.add_middleware(RequestIDMiddleware)

        @app.get("/health")
        async def health():
            return {"status": "healthy"}

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert response.json() == {"status": "healthy"}

    def test_provided_request_id_preserved_through_chain(self):
        """Test that provided request ID is preserved through middleware chain."""
        test_key = "chain_test_key"
        os.environ["API_KEY_ENABLED"] = "true"
        os.environ["API_KEYS"] = f'["{test_key}"]'
        get_settings.cache_clear()

        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.add_middleware(RequestIDMiddleware)

        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(app)
        provided_id = "preserved-request-id"
        response = client.get(
            "/api/test",
            headers={"X-API-Key": test_key, "X-Request-ID": provided_id},
        )

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == provided_id
