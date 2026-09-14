"""Unit tests for idempotency middleware.

Tests for Idempotency-Key header support on mutation endpoints (POST, PUT, DELETE).
Implements NEM-2018 acceptance criteria:
- Middleware implementation
- POST/PUT/DELETE endpoints support header
- Cached response returned on replay
- Different request body with same key returns 422
- TTL configurable (default 24h)

Tests follow TDD methodology.
"""

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request, Response
from starlette.datastructures import Headers

from backend.api.middleware.idempotency import (
    IDEMPOTENCY_KEY_MAX_LENGTH,
    IdempotencyMiddleware,
    compute_request_fingerprint,
    validate_idempotency_key,
)

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestComputeRequestFingerprint:
    """Tests for compute_request_fingerprint helper function."""

    def test_fingerprint_includes_method(self):
        """Test that fingerprint changes with HTTP method."""
        body = b'{"key": "value"}'
        fp_post = compute_request_fingerprint("POST", "/api/cameras", body)
        fp_put = compute_request_fingerprint("PUT", "/api/cameras", body)
        assert fp_post != fp_put

    def test_fingerprint_includes_path(self):
        """Test that fingerprint changes with request path."""
        body = b'{"key": "value"}'
        fp_cameras = compute_request_fingerprint("POST", "/api/cameras", body)
        fp_events = compute_request_fingerprint("POST", "/api/events", body)
        assert fp_cameras != fp_events

    def test_fingerprint_includes_body(self):
        """Test that fingerprint changes with request body."""
        body1 = b'{"key": "value1"}'
        body2 = b'{"key": "value2"}'
        fp1 = compute_request_fingerprint("POST", "/api/cameras", body1)
        fp2 = compute_request_fingerprint("POST", "/api/cameras", body2)
        assert fp1 != fp2

    def test_fingerprint_is_deterministic(self):
        """Test that same inputs produce same fingerprint."""
        body = b'{"key": "value"}'
        fp1 = compute_request_fingerprint("POST", "/api/cameras", body)
        fp2 = compute_request_fingerprint("POST", "/api/cameras", body)
        assert fp1 == fp2

    def test_fingerprint_handles_empty_body(self):
        """Test that empty body produces valid fingerprint."""
        fp = compute_request_fingerprint("DELETE", "/api/cameras/123", b"")
        assert fp is not None
        assert len(fp) == 64  # SHA-256 hex digest length


class TestIdempotencyMiddlewareInit:
    """Tests for IdempotencyMiddleware initialization."""

    def test_default_ttl(self, mock_settings):
        """Test default TTL is 24 hours (86400 seconds)."""
        app = FastAPI()
        mock_settings.idempotency_ttl_seconds = 86400

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)
            assert middleware.ttl == 86400

    def test_custom_ttl(self, mock_settings):
        """Test custom TTL configuration."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app, ttl=3600)
            assert middleware.ttl == 3600

    def test_custom_key_prefix(self, mock_settings):
        """Test custom Redis key prefix."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app, key_prefix="custom_idem")
            assert middleware.key_prefix == "custom_idem"

    def test_default_key_prefix(self, mock_settings):
        """Test default Redis key prefix."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)
            assert middleware.key_prefix == "idempotency"


class TestIdempotencyMiddlewareDispatch:
    """Tests for IdempotencyMiddleware.dispatch method."""

    @pytest.mark.asyncio
    async def test_skip_get_requests(self, mock_redis_client, mock_settings):
        """Test that GET requests are passed through without idempotency check."""
        app = FastAPI()

        @app.get("/api/test")
        async def get_test():
            return {"status": "ok"}

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            # Create mock request
            mock_request = MagicMock(spec=Request)
            mock_request.method = "GET"
            mock_request.headers = Headers({"Idempotency-Key": "test-key-123"})
            mock_request.url.path = "/api/test"

            call_next_called = False

            async def mock_call_next(request):
                nonlocal call_next_called
                call_next_called = True
                return Response(content=b'{"status": "ok"}', media_type="application/json")

            # Patch get_redis_optional to return our mock
            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                response = await middleware.dispatch(mock_request, mock_call_next)

        assert call_next_called
        assert "Idempotency-Replayed" not in response.headers

    @pytest.mark.asyncio
    async def test_skip_requests_without_idempotency_key(self, mock_redis_client, mock_settings):
        """Test that requests without Idempotency-Key header are passed through."""
        app = FastAPI()

        @app.post("/api/test")
        async def post_test():
            return {"status": "created"}

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "POST"
            mock_request.headers = Headers({})  # No Idempotency-Key
            mock_request.url.path = "/api/test"

            call_next_called = False

            async def mock_call_next(request):
                nonlocal call_next_called
                call_next_called = True
                return Response(content=b'{"status": "created"}', media_type="application/json")

            response = await middleware.dispatch(mock_request, mock_call_next)

            assert call_next_called
            assert "Idempotency-Replayed" not in response.headers

    @pytest.mark.asyncio
    async def test_cache_miss_processes_request_and_caches(self, mock_redis_client, mock_settings):
        """Test that on cache miss, request is processed and response is cached."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app, ttl=3600)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "POST"
            mock_request.headers = Headers({"Idempotency-Key": "unique-key-abc"})
            mock_request.url.path = "/api/cameras"

            # Mock body reading
            mock_request.body = AsyncMock(return_value=b'{"name": "camera1"}')

            # Mock Redis to return None (cache miss)
            mock_redis_client.get = AsyncMock(return_value=None)
            mock_redis_client.setex = AsyncMock(return_value=True)

            call_next_called = False
            response_body = b'{"id": "cam-123", "name": "camera1"}'

            async def mock_call_next(request):
                nonlocal call_next_called
                call_next_called = True
                return Response(
                    content=response_body,
                    status_code=201,
                    media_type="application/json",
                )

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                response = await middleware.dispatch(mock_request, mock_call_next)

            assert call_next_called
            assert response.status_code == 201
            assert "Idempotency-Replayed" not in response.headers

            # Verify cache was set
            mock_redis_client.setex.assert_called_once()
            call_args = mock_redis_client.setex.call_args
            assert call_args[0][1] == 3600  # TTL

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_response(self, mock_redis_client, mock_settings):
        """Test that on cache hit, cached response is returned without processing."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "POST"
            mock_request.headers = Headers({"Idempotency-Key": "existing-key-xyz"})
            mock_request.url.path = "/api/cameras"
            mock_request.body = AsyncMock(return_value=b'{"name": "camera1"}')

            # Mock Redis to return cached data
            cached_data = {
                "status_code": 201,
                "content": '{"id": "cam-123", "name": "camera1"}',
                "media_type": "application/json",
                "fingerprint": compute_request_fingerprint(
                    "POST", "/api/cameras", b'{"name": "camera1"}'
                ),
            }
            mock_redis_client.get = AsyncMock(return_value=json.dumps(cached_data))

            call_next_called = False

            async def mock_call_next(request):
                nonlocal call_next_called
                call_next_called = True
                return Response(content=b"should not be called")

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                response = await middleware.dispatch(mock_request, mock_call_next)

            # Request should NOT have been processed
            assert not call_next_called

            # Should return cached response with replay header
            assert response.status_code == 201
            assert response.headers.get("Idempotency-Replayed") == "true"

    @pytest.mark.asyncio
    async def test_fingerprint_mismatch_returns_422(self, mock_redis_client, mock_settings):
        """Test that different request body with same key returns 422."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "POST"
            mock_request.headers = Headers({"Idempotency-Key": "reused-key-123"})
            mock_request.url.path = "/api/cameras"
            # Different body than originally used
            mock_request.body = AsyncMock(return_value=b'{"name": "different-camera"}')

            # Mock Redis to return cached data with different fingerprint
            original_fingerprint = compute_request_fingerprint(
                "POST", "/api/cameras", b'{"name": "original-camera"}'
            )
            cached_data = {
                "status_code": 201,
                "content": '{"id": "cam-123"}',
                "media_type": "application/json",
                "fingerprint": original_fingerprint,
            }
            mock_redis_client.get = AsyncMock(return_value=json.dumps(cached_data))

            call_next_called = False

            async def mock_call_next(request):
                nonlocal call_next_called
                call_next_called = True
                return Response(content=b"should not be called")

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                response = await middleware.dispatch(mock_request, mock_call_next)

            # Request should NOT have been processed
            assert not call_next_called

            # Should return 422 Unprocessable Entity
            assert response.status_code == 422
            body = json.loads(response.body)
            assert "detail" in body
            assert "idempotency" in body["detail"].lower()

    @pytest.mark.asyncio
    async def test_supports_put_method(self, mock_redis_client, mock_settings):
        """Test that PUT requests support idempotency."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "PUT"
            mock_request.headers = Headers({"Idempotency-Key": "put-key-123"})
            mock_request.url.path = "/api/cameras/cam-123"
            mock_request.body = AsyncMock(return_value=b'{"name": "updated-camera"}')

            mock_redis_client.get = AsyncMock(return_value=None)
            mock_redis_client.setex = AsyncMock(return_value=True)

            async def mock_call_next(request):
                return Response(
                    content=b'{"id": "cam-123", "name": "updated-camera"}',
                    status_code=200,
                    media_type="application/json",
                )

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                response = await middleware.dispatch(mock_request, mock_call_next)

            assert response.status_code == 200
            mock_redis_client.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_supports_delete_method(self, mock_redis_client, mock_settings):
        """Test that DELETE requests support idempotency."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "DELETE"
            mock_request.headers = Headers({"Idempotency-Key": "delete-key-456"})
            mock_request.url.path = "/api/cameras/cam-123"
            mock_request.body = AsyncMock(return_value=b"")

            mock_redis_client.get = AsyncMock(return_value=None)
            mock_redis_client.setex = AsyncMock(return_value=True)

            async def mock_call_next(request):
                return Response(content=b"", status_code=204)

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                response = await middleware.dispatch(mock_request, mock_call_next)

            assert response.status_code == 204
            mock_redis_client.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_supports_patch_method(self, mock_redis_client, mock_settings):
        """Test that PATCH requests support idempotency."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "PATCH"
            mock_request.headers = Headers({"Idempotency-Key": "patch-key-789"})
            mock_request.url.path = "/api/cameras/cam-123"
            mock_request.body = AsyncMock(return_value=b'{"status": "offline"}')

            mock_redis_client.get = AsyncMock(return_value=None)
            mock_redis_client.setex = AsyncMock(return_value=True)

            async def mock_call_next(request):
                return Response(
                    content=b'{"id": "cam-123", "status": "offline"}',
                    status_code=200,
                    media_type="application/json",
                )

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                response = await middleware.dispatch(mock_request, mock_call_next)

            assert response.status_code == 200
            mock_redis_client.setex.assert_called_once()


class TestIdempotencyMiddlewareErrorHandling:
    """Tests for IdempotencyMiddleware error handling."""

    @pytest.mark.asyncio
    async def test_redis_unavailable_passes_through(self, mock_redis_client, mock_settings):
        """Test that requests pass through when Redis is unavailable."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "POST"
            mock_request.headers = Headers({"Idempotency-Key": "test-key"})
            mock_request.url.path = "/api/cameras"
            mock_request.body = AsyncMock(return_value=b'{"name": "camera1"}')

            call_next_called = False

            async def mock_call_next(request):
                nonlocal call_next_called
                call_next_called = True
                return Response(content=b'{"id": "cam-123"}', status_code=201)

            # Simulate Redis being unavailable
            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield None  # Redis unavailable

                mock_get_redis.return_value = get_redis()

                response = await middleware.dispatch(mock_request, mock_call_next)

            # Request should be processed normally
            assert call_next_called
            assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_redis_error_on_get_passes_through(self, mock_redis_client, mock_settings):
        """Test that Redis errors on cache lookup pass through to normal processing."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "POST"
            mock_request.headers = Headers({"Idempotency-Key": "test-key"})
            mock_request.url.path = "/api/cameras"
            mock_request.body = AsyncMock(return_value=b'{"name": "camera1"}')

            # Redis get raises exception
            mock_redis_client.get = AsyncMock(side_effect=Exception("Redis connection error"))
            mock_redis_client.setex = AsyncMock(return_value=True)

            call_next_called = False

            async def mock_call_next(request):
                nonlocal call_next_called
                call_next_called = True
                return Response(content=b'{"id": "cam-123"}', status_code=201)

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                response = await middleware.dispatch(mock_request, mock_call_next)

            # Request should be processed normally (fail open)
            assert call_next_called
            assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_redis_error_on_set_still_returns_response(
        self, mock_redis_client, mock_settings
    ):
        """Test that Redis errors on cache set don't affect the response."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "POST"
            mock_request.headers = Headers({"Idempotency-Key": "test-key"})
            mock_request.url.path = "/api/cameras"
            mock_request.body = AsyncMock(return_value=b'{"name": "camera1"}')

            # Cache miss, but set fails
            mock_redis_client.get = AsyncMock(return_value=None)
            mock_redis_client.setex = AsyncMock(side_effect=Exception("Redis write error"))

            async def mock_call_next(request):
                return Response(content=b'{"id": "cam-123"}', status_code=201)

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                response = await middleware.dispatch(mock_request, mock_call_next)

            # Response should still be returned
            assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_invalid_cached_json_passes_through(self, mock_redis_client, mock_settings):
        """Test that invalid JSON in cache doesn't break the request."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "POST"
            mock_request.headers = Headers({"Idempotency-Key": "test-key"})
            mock_request.url.path = "/api/cameras"
            mock_request.body = AsyncMock(return_value=b'{"name": "camera1"}')

            # Return invalid JSON from cache
            mock_redis_client.get = AsyncMock(return_value="not valid json {{{")
            mock_redis_client.setex = AsyncMock(return_value=True)

            call_next_called = False

            async def mock_call_next(request):
                nonlocal call_next_called
                call_next_called = True
                return Response(content=b'{"id": "cam-123"}', status_code=201)

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                response = await middleware.dispatch(mock_request, mock_call_next)

            # Should fall back to normal processing
            assert call_next_called
            assert response.status_code == 201


class TestIdempotencyMiddlewareRedisKey:
    """Tests for Redis key generation in IdempotencyMiddleware."""

    def test_make_cache_key_includes_prefix(self, mock_settings):
        """Test that cache key includes configured prefix."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app, key_prefix="idem")

            key = middleware._make_cache_key("test-idempotency-key")
            assert key.startswith("idem:")

    def test_make_cache_key_includes_idempotency_key(self, mock_settings):
        """Test that cache key includes the idempotency key."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app, key_prefix="idempotency")

            idempotency_key = "unique-request-key-abc123"
            key = middleware._make_cache_key(idempotency_key)
            assert idempotency_key in key

    def test_make_cache_key_deterministic(self, mock_settings):
        """Test that same idempotency key produces same cache key."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            key1 = middleware._make_cache_key("same-key")
            key2 = middleware._make_cache_key("same-key")
            assert key1 == key2

    def test_different_idempotency_keys_produce_different_cache_keys(self, mock_settings):
        """Test that different idempotency keys produce different cache keys."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            key1 = middleware._make_cache_key("key-a")
            key2 = middleware._make_cache_key("key-b")
            assert key1 != key2


class TestIdempotencyMiddlewareCacheData:
    """Tests for cache data structure in IdempotencyMiddleware."""

    @pytest.mark.asyncio
    async def test_cache_stores_status_code(self, mock_redis_client, mock_settings):
        """Test that cached data includes response status code."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "POST"
            mock_request.headers = Headers({"Idempotency-Key": "test-key"})
            mock_request.url.path = "/api/cameras"
            mock_request.body = AsyncMock(return_value=b'{"name": "camera1"}')

            mock_redis_client.get = AsyncMock(return_value=None)
            mock_redis_client.setex = AsyncMock(return_value=True)

            async def mock_call_next(request):
                return Response(content=b'{"id": "cam-123"}', status_code=201)

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                await middleware.dispatch(mock_request, mock_call_next)

            # Verify cache data includes status_code
            setex_call = mock_redis_client.setex.call_args
            cached_json = setex_call[0][2]
            cached_data = json.loads(cached_json)
            assert cached_data["status_code"] == 201

    @pytest.mark.asyncio
    async def test_cache_stores_content(self, mock_redis_client, mock_settings):
        """Test that cached data includes response content."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "POST"
            mock_request.headers = Headers({"Idempotency-Key": "test-key"})
            mock_request.url.path = "/api/cameras"
            mock_request.body = AsyncMock(return_value=b'{"name": "camera1"}')

            mock_redis_client.get = AsyncMock(return_value=None)
            mock_redis_client.setex = AsyncMock(return_value=True)

            response_content = b'{"id": "cam-123", "name": "camera1"}'

            async def mock_call_next(request):
                return Response(content=response_content, status_code=201)

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                await middleware.dispatch(mock_request, mock_call_next)

            setex_call = mock_redis_client.setex.call_args
            cached_json = setex_call[0][2]
            cached_data = json.loads(cached_json)
            assert cached_data["content"] == response_content.decode("utf-8")

    @pytest.mark.asyncio
    async def test_cache_stores_fingerprint(self, mock_redis_client, mock_settings):
        """Test that cached data includes request fingerprint for collision detection."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            request_body = b'{"name": "camera1"}'

            mock_request = MagicMock(spec=Request)
            mock_request.method = "POST"
            mock_request.headers = Headers({"Idempotency-Key": "test-key"})
            mock_request.url.path = "/api/cameras"
            mock_request.body = AsyncMock(return_value=request_body)

            mock_redis_client.get = AsyncMock(return_value=None)
            mock_redis_client.setex = AsyncMock(return_value=True)

            async def mock_call_next(request):
                return Response(content=b'{"id": "cam-123"}', status_code=201)

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                await middleware.dispatch(mock_request, mock_call_next)

            setex_call = mock_redis_client.setex.call_args
            cached_json = setex_call[0][2]
            cached_data = json.loads(cached_json)

            expected_fingerprint = compute_request_fingerprint("POST", "/api/cameras", request_body)
            assert cached_data["fingerprint"] == expected_fingerprint


class TestIdempotencyMiddlewareTTLConfiguration:
    """Tests for TTL configuration via settings."""

    @pytest.mark.asyncio
    async def test_uses_settings_ttl_when_not_explicit(self, mock_redis_client, mock_settings):
        """Test that middleware uses settings TTL when not explicitly configured."""
        app = FastAPI()
        mock_settings.idempotency_ttl_seconds = 7200  # 2 hours

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)
            assert middleware.ttl == 7200

    @pytest.mark.asyncio
    async def test_explicit_ttl_overrides_settings(self, mock_redis_client, mock_settings):
        """Test that explicit TTL parameter overrides settings."""
        app = FastAPI()
        mock_settings.idempotency_ttl_seconds = 7200

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app, ttl=1800)  # Explicit 30 minutes
            assert middleware.ttl == 1800


class TestIdempotencyMiddlewareLogging:
    """Tests for logging in IdempotencyMiddleware."""

    @pytest.mark.asyncio
    async def test_logs_cache_hit(self, mock_redis_client, mock_settings, caplog):
        """Test that cache hit is logged."""
        import logging

        caplog.set_level(logging.INFO)

        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "POST"
            mock_request.headers = Headers({"Idempotency-Key": "test-key"})
            mock_request.url.path = "/api/cameras"
            mock_request.body = AsyncMock(return_value=b'{"name": "camera1"}')

            cached_data = {
                "status_code": 201,
                "content": '{"id": "cam-123"}',
                "media_type": "application/json",
                "fingerprint": compute_request_fingerprint(
                    "POST", "/api/cameras", b'{"name": "camera1"}'
                ),
            }
            mock_redis_client.get = AsyncMock(return_value=json.dumps(cached_data))

            async def mock_call_next(request):
                return Response(content=b"")

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                await middleware.dispatch(mock_request, mock_call_next)

            # Check that cache hit was logged
            assert "idempotent" in caplog.text.lower() or "replayed" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_logs_fingerprint_mismatch(self, mock_redis_client, mock_settings, caplog):
        """Test that fingerprint mismatch is logged as warning."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "POST"
            mock_request.headers = Headers({"Idempotency-Key": "reused-key"})
            mock_request.url.path = "/api/cameras"
            mock_request.body = AsyncMock(return_value=b'{"name": "different"}')

            # Different fingerprint in cache
            cached_data = {
                "status_code": 201,
                "content": '{"id": "cam-123"}',
                "media_type": "application/json",
                "fingerprint": "different-fingerprint-hash",
            }
            mock_redis_client.get = AsyncMock(return_value=json.dumps(cached_data))

            async def mock_call_next(request):
                return Response(content=b"")

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                await middleware.dispatch(mock_request, mock_call_next)

            # Check that mismatch was logged
            assert "mismatch" in caplog.text.lower() or "collision" in caplog.text.lower()


class TestValidateIdempotencyKey:
    """Tests for validate_idempotency_key function (NEM-2593)."""

    def test_valid_key_alphanumeric(self):
        """Test that valid alphanumeric keys pass validation."""
        is_valid, error = validate_idempotency_key("abc123")
        assert is_valid is True
        assert error is None

    def test_valid_key_uuid_format(self):
        """Test that UUID-formatted keys pass validation."""
        is_valid, error = validate_idempotency_key("550e8400-e29b-41d4-a716-446655440000")
        assert is_valid is True
        assert error is None

    def test_valid_key_with_underscores(self):
        """Test that keys with underscores pass validation."""
        is_valid, error = validate_idempotency_key("request_key_123")
        assert is_valid is True
        assert error is None

    def test_valid_key_with_hyphens(self):
        """Test that keys with hyphens pass validation."""
        is_valid, error = validate_idempotency_key("request-key-123")
        assert is_valid is True
        assert error is None

    def test_valid_key_max_length(self):
        """Test that keys at maximum length pass validation."""
        key = "a" * IDEMPOTENCY_KEY_MAX_LENGTH
        is_valid, error = validate_idempotency_key(key)
        assert is_valid is True
        assert error is None

    def test_invalid_key_empty(self):
        """Test that empty keys fail validation."""
        is_valid, error = validate_idempotency_key("")
        assert is_valid is False
        assert "cannot be empty" in error.lower()

    def test_invalid_key_too_long(self):
        """Test that keys exceeding maximum length fail validation."""
        key = "a" * (IDEMPOTENCY_KEY_MAX_LENGTH + 1)
        is_valid, error = validate_idempotency_key(key)
        assert is_valid is False
        assert "maximum length" in error.lower()
        assert str(IDEMPOTENCY_KEY_MAX_LENGTH) in error

    def test_invalid_key_special_characters(self):
        """Test that keys with special characters fail validation."""
        is_valid, error = validate_idempotency_key("key@with#special$chars")
        assert is_valid is False
        assert "invalid characters" in error.lower()

    def test_invalid_key_spaces(self):
        """Test that keys with spaces fail validation."""
        is_valid, error = validate_idempotency_key("key with spaces")
        assert is_valid is False
        assert "invalid characters" in error.lower()

    def test_invalid_key_unicode(self):
        """Test that keys with unicode characters fail validation."""
        is_valid, error = validate_idempotency_key("key-with-émojis-😀")
        assert is_valid is False
        assert "invalid characters" in error.lower()


class TestIdempotencyMiddlewareChunking:
    """Tests for chunked response handling (NEM-2592)."""

    def test_init_default_max_payload_size(self, mock_settings):
        """Test default max payload size from settings."""
        app = FastAPI()
        mock_settings.idempotency_max_payload_size = 10485760  # 10MB

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)
            assert middleware.max_payload_size == 10485760

    def test_init_custom_max_payload_size(self, mock_settings):
        """Test custom max payload size parameter."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app, max_payload_size=5242880)  # 5MB
            assert middleware.max_payload_size == 5242880

    def test_init_default_chunk_size(self, mock_settings):
        """Test default chunk size from settings."""
        app = FastAPI()
        mock_settings.idempotency_chunk_size = 65536  # 64KB

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)
            assert middleware.chunk_size == 65536

    def test_init_custom_chunk_size(self, mock_settings):
        """Test custom chunk size parameter."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app, chunk_size=131072)  # 128KB
            assert middleware.chunk_size == 131072

    def test_make_chunks_key(self, mock_settings):
        """Test chunks key generation for chunked responses."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app, key_prefix="idem")
            chunks_key = middleware._make_chunks_key("test-key-123")
            assert chunks_key == "idem:chunks:test-key-123"

    @pytest.mark.asyncio
    async def test_cache_response_exceeds_max_payload_size(self, mock_redis_client, mock_settings):
        """Test that responses exceeding max_payload_size are not cached."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app, max_payload_size=100)  # Very small limit

            mock_request = MagicMock(spec=Request)
            mock_request.url.path = "/api/cameras"

            # Create a large response
            large_body = b"x" * 200  # Exceeds limit
            response = Response(content=large_body, status_code=201)

            cache_key = "idempotency:test-key"
            fingerprint = "test-fingerprint"

            result = await middleware._cache_response(
                mock_redis_client, cache_key, response, fingerprint, "test-key", mock_request
            )

            # Response should be returned but not cached
            assert result.status_code == 201
            mock_redis_client.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_replay_chunked_response(self, mock_redis_client, mock_settings):
        """Test replaying a cached chunked response."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.url.path = "/api/cameras"

            # Simulate chunked data in Redis
            chunk1 = b"First chunk"
            chunk2 = b"Second chunk"
            cached_data = {
                "status_code": 200,
                "media_type": "application/json",
                "is_chunked": True,
                "chunk_count": 2,
                "total_size": len(chunk1) + len(chunk2),
            }

            # Mock Redis lrange to return base64-encoded chunks
            mock_redis_client.lrange = AsyncMock(
                return_value=[
                    base64.b64encode(chunk1).decode("ascii"),
                    base64.b64encode(chunk2).decode("ascii"),
                ]
            )

            response = await middleware._replay_chunked_response(
                mock_redis_client, cached_data, "test-key", mock_request
            )

            assert response.status_code == 200
            assert response.body == chunk1 + chunk2
            assert response.headers.get("Idempotency-Replayed") == "true"

    @pytest.mark.asyncio
    async def test_replay_chunked_response_error(self, mock_redis_client, mock_settings):
        """Test error handling when replaying chunked response fails."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.url.path = "/api/cameras"

            cached_data = {
                "status_code": 200,
                "media_type": "application/json",
                "is_chunked": True,
                "chunk_count": 2,
            }

            # Simulate Redis error
            mock_redis_client.lrange = AsyncMock(side_effect=Exception("Redis read error"))

            response = await middleware._replay_chunked_response(
                mock_redis_client, cached_data, "test-key", mock_request
            )

            assert response.status_code == 500
            body = json.loads(response.body)
            assert "Failed to replay" in body["detail"]

    @pytest.mark.asyncio
    async def test_cache_hit_with_chunked_response(self, mock_redis_client, mock_settings):
        """Test cache hit handling for chunked responses."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "POST"
            mock_request.url.path = "/api/cameras"
            request_body = b'{"name": "camera1"}'
            fingerprint = compute_request_fingerprint("POST", "/api/cameras", request_body)

            # Simulate chunked response in cache
            cached_data = {
                "status_code": 201,
                "media_type": "application/json",
                "fingerprint": fingerprint,
                "is_chunked": True,
                "chunk_count": 2,
                "total_size": 100,
            }

            chunk1 = b'{"id": "'
            chunk2 = b'cam-123"}'
            mock_redis_client.lrange = AsyncMock(
                return_value=[
                    base64.b64encode(chunk1).decode("ascii"),
                    base64.b64encode(chunk2).decode("ascii"),
                ]
            )

            response = await middleware._handle_cache_hit(
                mock_redis_client, cached_data, fingerprint, "test-key", mock_request
            )

            assert response.status_code == 201
            assert response.body == chunk1 + chunk2
            assert response.headers.get("Idempotency-Replayed") == "true"


class TestIdempotencyMiddlewareStreamingResponse:
    """Tests for streaming response caching."""

    @pytest.mark.asyncio
    async def test_cache_streaming_response_success(self, mock_redis_client, mock_settings):
        """Test caching a streaming response with chunked storage."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app, chunk_size=10, max_payload_size=100)

            mock_request = MagicMock(spec=Request)
            mock_request.url.path = "/api/cameras"

            # Create streaming response
            async def body_iterator():
                yield b"chunk1"
                yield b"chunk2"
                yield b"chunk3"

            response = Response(status_code=200, media_type="application/json")
            response.body_iterator = body_iterator()

            mock_redis_client.rpush = AsyncMock(return_value=1)
            mock_redis_client.setex = AsyncMock(return_value=True)
            mock_redis_client.expire = AsyncMock(return_value=True)

            result = await middleware._cache_streaming_response(
                mock_redis_client,
                "cache-key",
                response,
                "fingerprint",
                "idem-key",
                mock_request,
            )

            # Should cache chunks
            assert mock_redis_client.rpush.call_count > 0
            mock_redis_client.setex.assert_called_once()
            mock_redis_client.expire.assert_called_once()

            # Result should contain all chunks
            assert result.status_code == 200
            assert b"chunk1" in result.body
            assert b"chunk2" in result.body
            assert b"chunk3" in result.body

    @pytest.mark.asyncio
    async def test_cache_streaming_response_exceeds_limit(self, mock_redis_client, mock_settings):
        """Test streaming response that exceeds max_payload_size is not cached."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app, chunk_size=10, max_payload_size=10)

            mock_request = MagicMock(spec=Request)
            mock_request.url.path = "/api/cameras"

            # Create streaming response that exceeds limit
            async def body_iterator():
                yield b"x" * 5
                yield b"x" * 10  # This will exceed the limit

            response = Response(status_code=200, media_type="application/json")
            response.body_iterator = body_iterator()

            mock_redis_client.rpush = AsyncMock(return_value=1)
            mock_redis_client.setex = AsyncMock(return_value=True)
            mock_redis_client.delete = AsyncMock(return_value=1)

            result = await middleware._cache_streaming_response(
                mock_redis_client,
                "cache-key",
                response,
                "fingerprint",
                "idem-key",
                mock_request,
            )

            # Should not cache metadata (setex not called)
            mock_redis_client.setex.assert_not_called()
            # Should clean up partial chunks
            mock_redis_client.delete.assert_called_once()

            # Result should still be returned
            assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_cache_streaming_response_error_cleanup(self, mock_redis_client, mock_settings):
        """Test that streaming response errors trigger cleanup."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app, chunk_size=10)

            mock_request = MagicMock(spec=Request)
            mock_request.url.path = "/api/cameras"

            # Create streaming response that raises error
            async def body_iterator():
                yield b"chunk1"
                raise Exception("Stream error")

            response = Response(status_code=200, media_type="application/json")
            response.body_iterator = body_iterator()

            mock_redis_client.rpush = AsyncMock(return_value=1)
            mock_redis_client.delete = AsyncMock(return_value=1)

            result = await middleware._cache_streaming_response(
                mock_redis_client,
                "cache-key",
                response,
                "fingerprint",
                "idem-key",
                mock_request,
            )

            # Should attempt cleanup
            mock_redis_client.delete.assert_called()

            # Result should contain chunk before error
            assert b"chunk1" in result.body


class TestIdempotencyMiddlewareBinaryContent:
    """Tests for binary content handling."""

    @pytest.mark.asyncio
    async def test_cache_binary_response(self, mock_redis_client, mock_settings):
        """Test caching binary content (base64 encoded)."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.url.path = "/api/media"

            # Binary content that can't be decoded as UTF-8
            binary_body = bytes([0xFF, 0xD8, 0xFF, 0xE0])  # JPEG header
            response = Response(content=binary_body, status_code=200, media_type="image/jpeg")

            mock_redis_client.setex = AsyncMock(return_value=True)

            result = await middleware._cache_simple_response(
                mock_redis_client,
                "cache-key",
                binary_body,
                response,
                "fingerprint",
                "idem-key",
                mock_request,
            )

            # Should cache with is_binary flag
            setex_call = mock_redis_client.setex.call_args
            cached_json = setex_call[0][2]
            cached_data = json.loads(cached_json)
            assert cached_data["is_binary"] is True
            # Content should be base64 encoded
            assert cached_data["content"] == base64.b64encode(binary_body).decode("ascii")

            # Result should return original binary
            assert result.body == binary_body

    @pytest.mark.asyncio
    async def test_replay_binary_response(self, mock_redis_client, mock_settings):
        """Test replaying cached binary response."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "POST"
            mock_request.url.path = "/api/media"
            request_body = b'{"upload": "data"}'
            fingerprint = compute_request_fingerprint("POST", "/api/media", request_body)

            # Binary content in cache
            binary_content = bytes([0xFF, 0xD8, 0xFF, 0xE0])
            cached_data = {
                "status_code": 200,
                "content": base64.b64encode(binary_content).decode("ascii"),
                "media_type": "image/jpeg",
                "fingerprint": fingerprint,
                "is_binary": True,
            }

            response = await middleware._handle_cache_hit(
                mock_redis_client, cached_data, fingerprint, "test-key", mock_request
            )

            assert response.status_code == 200
            assert response.body == binary_content
            assert response.headers.get("Idempotency-Replayed") == "true"


class TestIdempotencyMiddlewareDispatchEdgeCases:
    """Tests for dispatch edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_dispatch_invalid_key_format(self, mock_redis_client, mock_settings):
        """Test that invalid key format returns 400."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "POST"
            mock_request.headers = Headers({"Idempotency-Key": "invalid key with spaces"})
            mock_request.url.path = "/api/cameras"

            async def mock_call_next(request):
                return Response(content=b"should not be called")

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                response = await middleware.dispatch(mock_request, mock_call_next)

            assert response.status_code == 400
            body = json.loads(response.body)
            assert "invalid characters" in body["detail"].lower()

    @pytest.mark.asyncio
    async def test_dispatch_key_too_long(self, mock_redis_client, mock_settings):
        """Test that overly long key returns 400."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "POST"
            long_key = "a" * (IDEMPOTENCY_KEY_MAX_LENGTH + 1)
            mock_request.headers = Headers({"Idempotency-Key": long_key})
            mock_request.url.path = "/api/cameras"

            async def mock_call_next(request):
                return Response(content=b"should not be called")

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                response = await middleware.dispatch(mock_request, mock_call_next)

            assert response.status_code == 400
            body = json.loads(response.body)
            assert "maximum length" in body["detail"].lower()

    @pytest.mark.asyncio
    async def test_dispatch_empty_key_skips_idempotency(self, mock_redis_client, mock_settings):
        """Test that empty key skips idempotency processing and proceeds normally."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "POST"
            mock_request.headers = Headers({"Idempotency-Key": ""})
            mock_request.url.path = "/api/cameras"

            async def mock_call_next(request):
                return Response(content=b"normal response", status_code=200)

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                response = await middleware.dispatch(mock_request, mock_call_next)

            # Empty key is treated as no key - skips idempotency, proceeds normally
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_dispatch_request_body_read_error(self, mock_redis_client, mock_settings):
        """Test that request body read errors fall back to normal processing."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "POST"
            mock_request.headers = Headers({"Idempotency-Key": "test-key"})
            mock_request.url.path = "/api/cameras"
            mock_request.body = AsyncMock(side_effect=Exception("Body read error"))

            call_next_called = False

            async def mock_call_next(request):
                nonlocal call_next_called
                call_next_called = True
                return Response(content=b'{"id": "cam-123"}', status_code=201)

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                response = await middleware.dispatch(mock_request, mock_call_next)

            # Should fall back to normal processing
            assert call_next_called
            assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_get_redis_client_exception(self, mock_redis_client, mock_settings):
        """Test _get_redis_client handles exceptions gracefully."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def failing_redis():
                    raise Exception("Redis connection failed")

                mock_get_redis.return_value = failing_redis()

                result = await middleware._get_redis_client("test-key")

            assert result is None

    @pytest.mark.asyncio
    async def test_dispatch_with_unknown_response_type(self, mock_redis_client, mock_settings):
        """Test that unknown response types are handled gracefully."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            mock_request = MagicMock(spec=Request)
            mock_request.method = "POST"
            mock_request.headers = Headers({"Idempotency-Key": "test-key"})
            mock_request.url.path = "/api/cameras"
            mock_request.body = AsyncMock(return_value=b'{"name": "camera1"}')

            mock_redis_client.get = AsyncMock(return_value=None)

            # Create response without body or body_iterator
            async def mock_call_next(request):
                response = Response(status_code=201)
                # Remove body attribute to simulate unknown response type
                if hasattr(response, "body"):
                    delattr(response, "body")
                return response

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                response = await middleware.dispatch(mock_request, mock_call_next)

            # Should return response without caching
            assert response.status_code == 201
            mock_redis_client.setex.assert_not_called()


class TestIdempotencyMiddlewareIntegrationScenarios:
    """Integration-style tests for complete scenarios."""

    @pytest.mark.asyncio
    async def test_complete_idempotent_flow_cache_miss_then_hit(
        self, mock_redis_client, mock_settings
    ):
        """Test complete flow: cache miss, then cache hit with replay."""
        app = FastAPI()

        with patch("backend.api.middleware.idempotency.get_settings", return_value=mock_settings):
            middleware = IdempotencyMiddleware(app)

            # First request - cache miss
            mock_request1 = MagicMock(spec=Request)
            mock_request1.method = "POST"
            mock_request1.headers = Headers({"Idempotency-Key": "test-flow-key"})
            mock_request1.url.path = "/api/cameras"
            request_body = b'{"name": "camera1"}'
            mock_request1.body = AsyncMock(return_value=request_body)

            mock_redis_client.get = AsyncMock(return_value=None)
            mock_redis_client.setex = AsyncMock(return_value=True)

            response_body = b'{"id": "cam-123", "name": "camera1"}'

            async def mock_call_next(request):
                return Response(content=response_body, status_code=201)

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                response1 = await middleware.dispatch(mock_request1, mock_call_next)

            assert response1.status_code == 201
            assert "Idempotency-Replayed" not in response1.headers
            mock_redis_client.setex.assert_called_once()

            # Second request - cache hit
            mock_request2 = MagicMock(spec=Request)
            mock_request2.method = "POST"
            mock_request2.headers = Headers({"Idempotency-Key": "test-flow-key"})
            mock_request2.url.path = "/api/cameras"
            mock_request2.body = AsyncMock(return_value=request_body)

            # Setup cached response
            fingerprint = compute_request_fingerprint("POST", "/api/cameras", request_body)
            cached_data = {
                "status_code": 201,
                "content": response_body.decode("utf-8"),
                "media_type": "application/json",
                "fingerprint": fingerprint,
            }
            mock_redis_client.get = AsyncMock(return_value=json.dumps(cached_data))

            call_next_called = False

            async def mock_call_next_should_not_run(request):
                nonlocal call_next_called
                call_next_called = True
                return Response(content=b"should not be called")

            with patch("backend.api.middleware.idempotency.get_redis_optional") as mock_get_redis:

                async def get_redis():
                    yield mock_redis_client

                mock_get_redis.return_value = get_redis()

                response2 = await middleware.dispatch(mock_request2, mock_call_next_should_not_run)

            assert not call_next_called  # Request not processed
            assert response2.status_code == 201
            assert response2.body == response_body
            assert response2.headers.get("Idempotency-Replayed") == "true"
