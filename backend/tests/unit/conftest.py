"""Unit test configuration and fixtures.

This module provides fixtures specific to unit tests in backend/tests/unit/.

NOTE: Marker application logic (skipping integration tests, applying unit marker)
has been consolidated into the main backend/tests/conftest.py to avoid multiple
iterations over test items. See pytest_collection_modifyitems in conftest.py.
"""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

# NOTE: pytest_collection_modifyitems has been removed from this file.
# All marker logic is now consolidated in backend/tests/conftest.py
# for O(n) instead of O(4n) complexity when processing test items.

# Test API key for unit tests - used to authenticate test requests
UNIT_TEST_API_KEY = "test-unit-api-key-12345"  # pragma: allowlist secret

# TP-fix (measured 2026-09-23, PR run 35866358876 Test Performance Audit):
# `torchvision`/`piq` are imported LAZILY inside image_quality_loader.assess_image_quality
# (backend/services/image_quality_loader.py:172) and are pulled by NO module-level
# import anywhere else — so the first BRISQUE-phase test in each fresh xdist
# worker pays the ~0.5-1.5s cold import INSIDE its measured <testcase time>, and
# pytest-randomly + --dist=worksteal rotates which victim eats it (measured
# victims across runs: four different enrichment-pipeline tests at 4.04-4.60s).
# Warming the modules HERE charges the cost to worker COLLECTION, which junit
# does not bill to any testcase. Deliberately module-level, NOT an autouse
# fixture: fixture setup bills the first test and re-points the same lottery.
# Same class of fix as mock_transformers_for_speed below (shipped in 3d30ef71
# for the identical gate). Best-effort: import failure here must never break
# collection — the lazy site still governs behavior.
for _warm in ("torchvision", "piq"):
    try:
        __import__(_warm)
    except Exception:  # pragma: no cover - absent dep just skips the warm-up
        pass
del _warm


@pytest.fixture(autouse=True)
def isolate_redis_module_global() -> Generator[None]:
    """Sweep backend.core.redis module globals before and after every unit test.

    `init_redis()` caches its client in the `backend.core.redis._redis_client`
    module global, which under xdist persists across test MODULES on a worker.
    A module whose lifespan/init test leaves a client bound to a since-closed
    event loop poisons every later test on that worker: the next `redis.get`
    raises "Event loop is closed" mid-request. Surfaced by the WP0.5-era honest
    validate.sh run (seed 1556902420) as gpu_config's concurrent-apply guard
    answering 500 where the shipped contract says 409.

    Sweep is unconditional at BOTH ends: entry, so residue can never reach a
    unit test (the observed direction of harm), and exit, so a unit test can
    never poison the next module. Nothing in backend/tests/unit legitimately
    relies on the global persisting across tests — tests that need a client
    build or patch their own — so None is always the safe inter-test value.
    """
    import backend.core.redis as redis_module

    redis_module._redis_client = None
    redis_module._redis_init_lock = None
    try:
        yield
    finally:
        redis_module._redis_client = None
        redis_module._redis_init_lock = None


@pytest.fixture(scope="session", autouse=True)
def enable_api_key_auth_for_unit_tests() -> Generator[None]:
    """Enable API key authentication for all unit tests.

    This session-scoped autouse fixture sets environment variables to enable
    API key authentication mode with a test API key. This ensures all unit
    tests that create test clients can authenticate properly.

    The fixture is autouse=True so it runs automatically for all unit tests
    without needing to be explicitly requested.
    """
    # Store original values
    original_api_key_enabled = os.environ.get("API_KEY_ENABLED")
    original_api_keys = os.environ.get("API_KEYS")

    # Enable API key auth with test key
    os.environ["API_KEY_ENABLED"] = "true"  # pragma: allowlist secret
    os.environ["API_KEYS"] = f'["{UNIT_TEST_API_KEY}"]'  # pragma: allowlist secret

    # Clear settings cache to pick up new values
    try:
        from backend.core.config import get_settings

        get_settings.cache_clear()
    except ImportError:
        pass  # Settings not available yet

    yield

    # Restore original values
    if original_api_key_enabled is not None:
        os.environ["API_KEY_ENABLED"] = original_api_key_enabled
    else:
        os.environ.pop("API_KEY_ENABLED", None)

    if original_api_keys is not None:
        os.environ["API_KEYS"] = original_api_keys
    else:
        os.environ.pop("API_KEYS", None)

    # Clear settings cache again
    try:
        from backend.core.config import get_settings

        get_settings.cache_clear()
    except ImportError:
        pass


@asynccontextmanager
async def authenticated_async_client() -> AsyncGenerator[AsyncClient]:
    """Create an authenticated AsyncClient for unit tests.

    This context manager creates an httpx AsyncClient with the test API key
    header pre-configured. Use this when testing FastAPI endpoints that
    require authentication.

    Usage:
        async with authenticated_async_client() as client:
            response = await client.get("/api/some-endpoint")

    Note: This context manager ensures API key auth is enabled before creating
    the client. The settings cache is cleared and API_KEY_ENABLED is set to
    ensure the middleware sees the correct authentication mode.
    """
    from httpx import ASGITransport, AsyncClient

    from backend.core.config import get_settings

    # Ensure API key auth is enabled - this is critical because the app/middleware
    # might have cached settings before the session fixture ran
    os.environ["API_KEY_ENABLED"] = "true"  # pragma: allowlist secret
    os.environ["API_KEYS"] = f'["{UNIT_TEST_API_KEY}"]'  # pragma: allowlist secret
    get_settings.cache_clear()

    from backend.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": UNIT_TEST_API_KEY},
    ) as client:
        yield client


def get_auth_headers() -> dict[str, str]:
    """Get authentication headers for unit tests.

    Returns a dict with the X-API-Key header set to the test API key.
    Use this when manually creating test clients.

    Usage:
        client = TestClient(app, headers=get_auth_headers())
    """
    return {"X-API-Key": UNIT_TEST_API_KEY}


@pytest.fixture(autouse=True)
def mock_transformers_for_speed(monkeypatch):
    """Mock transformers to speed up unit tests.

    The transformers package import takes ~0.54s. Since unit tests
    mock the actual model loading anyway, we mock the import to
    avoid this overhead on every test.

    Tests that need real transformers should use integration tests
    or explicitly unmock in the test.
    """
    # Only mock if not already imported (avoid breaking other tests)
    if "transformers" not in sys.modules:
        mock_transformers = MagicMock()
        # Configure from_pretrained to raise OSError for nonexistent paths
        # (matching real HuggingFace behavior)
        mock_transformers.AutoImageProcessor.from_pretrained.side_effect = OSError(
            "Can't load tokenizer for 'nonexistent'. Make sure that model path exists."
        )
        mock_transformers.AutoModelForImageClassification.from_pretrained.side_effect = OSError(
            "Can't load model for 'nonexistent'. Make sure that model path exists."
        )
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)
