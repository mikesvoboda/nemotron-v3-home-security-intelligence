"""Unit tests for API key authentication middleware."""

import hashlib
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.middleware import AuthMiddleware
from backend.core.config import get_settings


@pytest.fixture
def test_api_key():
    """Return a test API key."""
    return "test_secret_key_12345"


@pytest.fixture
def test_api_key_hash(test_api_key):
    """Return the hash of the test API key."""
    return hashlib.sha256(test_api_key.encode()).hexdigest()


@pytest.fixture
def app_with_auth(test_api_key):
    """Create a test FastAPI app with authentication middleware."""
    # Set up environment for testing
    os.environ["API_KEY_ENABLED"] = "true"
    os.environ["API_KEYS"] = f'["{test_api_key}"]'
    get_settings.cache_clear()

    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    @app.get("/")
    async def root():
        return {"message": "ok"}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/api/system/health")
    async def system_health():
        return {"status": "healthy"}

    @app.get("/api/system/health/live")
    async def liveness():
        return {"status": "alive"}

    @app.get("/api/system/health/ready")
    async def readiness():
        return {"ready": True, "status": "ready"}

    @app.get("/api/metrics")
    async def metrics():
        return "# Prometheus metrics"

    @app.get("/api/protected")
    async def protected():
        return {"message": "protected"}

    yield app

    # Cleanup
    os.environ.pop("API_KEY_ENABLED", None)
    os.environ.pop("API_KEYS", None)
    get_settings.cache_clear()


@pytest.fixture
def app_without_auth():
    """Create a test FastAPI app without authentication enabled."""
    # Set up environment for testing
    os.environ["API_KEY_ENABLED"] = "false"
    get_settings.cache_clear()

    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    @app.get("/")
    async def root():
        return {"message": "ok"}

    @app.get("/api/protected")
    async def protected():
        return {"message": "protected"}

    yield app

    # Cleanup
    os.environ.pop("API_KEY_ENABLED", None)
    get_settings.cache_clear()


def test_valid_key_in_header(app_with_auth, test_api_key):
    """Test that a valid API key in the header allows access."""
    client = TestClient(app_with_auth)
    response = client.get("/api/protected", headers={"X-API-Key": test_api_key})
    assert response.status_code == 200
    assert response.json() == {"message": "protected"}


def test_valid_key_in_query_param(app_with_auth, test_api_key):
    """Test that a valid API key in query parameter allows access."""
    client = TestClient(app_with_auth)
    response = client.get(f"/api/protected?api_key={test_api_key}")
    assert response.status_code == 200
    assert response.json() == {"message": "protected"}


def test_invalid_key_returns_401(app_with_auth):
    """Test that an invalid API key returns 401."""
    client = TestClient(app_with_auth)
    response = client.get("/api/protected", headers={"X-API-Key": "invalid_key"})
    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


def test_missing_key_returns_401(app_with_auth):
    """Test that missing API key returns 401."""
    client = TestClient(app_with_auth)
    response = client.get("/api/protected")
    assert response.status_code == 401
    assert "API key required" in response.json()["detail"]


def test_health_endpoint_bypasses_auth(app_with_auth):
    """Test that health endpoints bypass authentication."""
    client = TestClient(app_with_auth)

    # Test root health endpoint
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

    # Test system health endpoint
    response = client.get("/api/system/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

    # Test root endpoint
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "ok"}


def test_health_probe_endpoints_bypass_auth(app_with_auth):
    """Test that liveness and readiness probe endpoints bypass authentication.

    This is critical for Docker healthchecks which call these endpoints without
    API keys. If authentication is enabled, healthchecks should still work.
    """
    client = TestClient(app_with_auth)

    # Test liveness probe endpoint (used by Docker healthchecks)
    response = client.get("/api/system/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}

    # Test readiness probe endpoint
    response = client.get("/api/system/health/ready")
    assert response.status_code == 200
    assert response.json() == {"ready": True, "status": "ready"}


def test_metrics_endpoint_bypasses_auth(app_with_auth):
    """Test that metrics endpoint bypasses authentication.

    The /api/metrics endpoint must be accessible without authentication
    to allow Prometheus to scrape metrics without API key configuration.
    """
    client = TestClient(app_with_auth)

    # Test metrics endpoint (used by Prometheus scraping)
    response = client.get("/api/metrics")
    assert response.status_code == 200
    assert "# Prometheus metrics" in response.text


def test_disabled_auth_allows_all_requests(app_without_auth):
    """Test that disabled authentication allows all requests."""
    client = TestClient(app_without_auth)

    # Test without API key
    response = client.get("/api/protected")
    assert response.status_code == 200
    assert response.json() == {"message": "protected"}

    # Test with invalid API key (should still work)
    response = client.get("/api/protected", headers={"X-API-Key": "anything"})
    assert response.status_code == 200
    assert response.json() == {"message": "protected"}


def test_docs_endpoints_bypass_auth(app_with_auth):
    """Test that documentation endpoints bypass authentication."""
    client = TestClient(app_with_auth)

    # Test OpenAPI schema endpoint
    response = client.get("/openapi.json")
    assert response.status_code == 200

    # Note: /docs and /redoc return HTML and TestClient may not handle them perfectly,
    # but we can verify they don't return 401
    response = client.get("/docs")
    assert response.status_code != 401

    response = client.get("/redoc")
    assert response.status_code != 401


def test_hash_key_produces_correct_hash(test_api_key, test_api_key_hash):
    """Test that the _hash_key method produces correct SHA-256 hash."""
    app = FastAPI()
    middleware = AuthMiddleware(app, valid_key_hashes=set())
    computed_hash = middleware._hash_key(test_api_key)
    assert computed_hash == test_api_key_hash


def test_middleware_loads_keys_from_settings(test_api_key, test_api_key_hash):
    """Test that middleware correctly loads and hashes keys from settings."""
    os.environ["API_KEYS"] = f'["{test_api_key}"]'
    get_settings.cache_clear()

    app = FastAPI()
    middleware = AuthMiddleware(app)

    assert test_api_key_hash in middleware.valid_key_hashes

    # Cleanup
    os.environ.pop("API_KEYS", None)
    get_settings.cache_clear()


def test_middleware_accepts_custom_key_hashes(test_api_key_hash):
    """Test that middleware accepts custom key hashes."""
    app = FastAPI()
    custom_hashes = {test_api_key_hash, "another_hash"}
    middleware = AuthMiddleware(app, valid_key_hashes=custom_hashes)

    assert middleware.valid_key_hashes == custom_hashes


def test_is_exempt_path():
    """Test that _is_exempt_path correctly identifies exempt paths."""
    app = FastAPI()
    middleware = AuthMiddleware(app, valid_key_hashes=set())

    # Test exempt paths
    assert middleware._is_exempt_path("/") is True
    assert middleware._is_exempt_path("/health") is True
    assert middleware._is_exempt_path("/api/system/health") is True
    assert middleware._is_exempt_path("/api/system/health/live") is True
    assert middleware._is_exempt_path("/api/system/health/ready") is True
    assert middleware._is_exempt_path("/api/metrics") is True
    assert middleware._is_exempt_path("/docs") is True
    assert middleware._is_exempt_path("/redoc") is True
    assert middleware._is_exempt_path("/openapi.json") is True

    # Test non-exempt paths
    assert middleware._is_exempt_path("/api/cameras") is False
    assert middleware._is_exempt_path("/api/events") is False
    assert middleware._is_exempt_path("/api/protected") is False


def test_multiple_valid_keys():
    """Test that multiple valid API keys work correctly."""
    key1 = "key_one"
    key2 = "key_two"
    os.environ["API_KEY_ENABLED"] = "true"
    os.environ["API_KEYS"] = f'["{key1}", "{key2}"]'
    get_settings.cache_clear()

    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    @app.get("/api/test")
    async def test_endpoint():
        return {"message": "success"}

    client = TestClient(app)

    # Test first key
    response = client.get("/api/test", headers={"X-API-Key": key1})
    assert response.status_code == 200

    # Test second key
    response = client.get("/api/test", headers={"X-API-Key": key2})
    assert response.status_code == 200

    # Test invalid key
    response = client.get("/api/test", headers={"X-API-Key": "invalid"})
    assert response.status_code == 401

    # Cleanup
    os.environ.pop("API_KEY_ENABLED", None)
    os.environ.pop("API_KEYS", None)
    get_settings.cache_clear()


def test_header_takes_precedence_over_query_param(app_with_auth, test_api_key):
    """Test that X-API-Key header takes precedence over query parameter."""
    client = TestClient(app_with_auth)

    # Valid header, invalid query param - should succeed
    response = client.get(
        "/api/protected?api_key=invalid",
        headers={"X-API-Key": test_api_key},
    )
    assert response.status_code == 200


def test_empty_api_keys_list():
    """Test behavior when API_KEYS list is empty but auth is enabled."""
    os.environ["API_KEY_ENABLED"] = "true"
    os.environ["API_KEYS"] = "[]"
    get_settings.cache_clear()

    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    @app.get("/api/test")
    async def test_endpoint():
        return {"message": "success"}

    client = TestClient(app)

    # Should reject all requests since no valid keys exist
    response = client.get("/api/test", headers={"X-API-Key": "any_key"})
    assert response.status_code == 401

    # Cleanup
    os.environ.pop("API_KEY_ENABLED", None)
    os.environ.pop("API_KEYS", None)
    get_settings.cache_clear()
