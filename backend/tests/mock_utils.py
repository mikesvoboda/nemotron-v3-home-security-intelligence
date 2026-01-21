"""Centralized mock utilities for testing.

This module provides reusable mock factories and helpers to reduce boilerplate
in test files. All mocks follow consistent patterns and can be composed together.

Usage:
    from backend.tests.mock_utils import (
        create_mock_redis,
        create_mock_http_client,
        create_mock_db_session,
        create_mock_detector_client,
    )

    # In test
    mock_redis = create_mock_redis(health_status="healthy")
    mock_http = create_mock_http_client(get_responses={"/health": {"status": "ok"}})
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

# =============================================================================
# Redis Mock Factories
# =============================================================================


def create_mock_redis(
    health_status: str = "healthy",
    redis_version: str = "7.0.0",
    connected: bool = True,
    **extra_methods: Any,
) -> AsyncMock:
    """Create a mock Redis client with common operations pre-configured.

    Args:
        health_status: Health check status ("healthy", "unhealthy", "degraded")
        redis_version: Redis version string
        connected: Whether Redis is connected
        **extra_methods: Additional method return values as method_name=return_value

    Returns:
        AsyncMock configured as Redis client

    Example:
        mock_redis = create_mock_redis(
            health_status="healthy",
            get=AsyncMock(return_value="test_value"),
        )
    """
    mock_redis = AsyncMock()
    mock_redis.health_check.return_value = {
        "status": health_status,
        "connected": connected,
        "redis_version": redis_version,
    }

    # Configure additional methods
    for method_name, return_value in extra_methods.items():
        if isinstance(return_value, Mock | MagicMock | AsyncMock):
            setattr(mock_redis, method_name, return_value)
        else:
            method_mock = AsyncMock(return_value=return_value)
            setattr(mock_redis, method_name, method_mock)

    return mock_redis


def create_mock_redis_pubsub(
    messages: list[dict[str, Any]] | None = None,
) -> AsyncMock:
    """Create a mock Redis Pub/Sub client.

    Args:
        messages: List of messages to return from subscribe/listen

    Returns:
        AsyncMock configured as Redis Pub/Sub client

    Example:
        messages = [
            {"type": "subscribe", "channel": "events", "data": 1},
            {"type": "message", "channel": "events", "data": '{"event": "test"}'},
        ]
        mock_pubsub = create_mock_redis_pubsub(messages=messages)
    """
    mock_pubsub = AsyncMock()
    if messages:
        mock_pubsub.__aiter__.return_value = iter(messages)
    return mock_pubsub


# =============================================================================
# HTTP Client Mock Factories
# =============================================================================


def create_mock_http_client(
    get_responses: dict[str, Any] | None = None,
    post_responses: dict[str, Any] | None = None,
    status_code: int = 200,
    **extra_methods: Any,
) -> AsyncMock:
    """Create a mock HTTP client (httpx.AsyncClient) with response mocks.

    Args:
        get_responses: Dict of URL -> response data for GET requests
        post_responses: Dict of URL -> response data for POST requests
        status_code: Default HTTP status code
        **extra_methods: Additional method mocks

    Returns:
        AsyncMock configured as httpx.AsyncClient

    Example:
        mock_client = create_mock_http_client(
            get_responses={"/health": {"status": "healthy"}},
            post_responses={"/detect": {"detections": []}},
        )
    """
    mock_client = AsyncMock()

    # Configure GET responses
    if get_responses:

        async def mock_get(url: str, **kwargs: Any) -> AsyncMock:
            response = AsyncMock()
            response.status_code = status_code
            response.json.return_value = get_responses.get(url, {})
            return response

        mock_client.get = mock_get

    # Configure POST responses
    if post_responses:

        async def mock_post(url: str, **kwargs: Any) -> AsyncMock:
            response = AsyncMock()
            response.status_code = status_code
            response.json.return_value = post_responses.get(url, {})
            return response

        mock_client.post = mock_post

    # Configure additional methods
    for method_name, method_mock in extra_methods.items():
        setattr(mock_client, method_name, method_mock)

    return mock_client


def create_mock_response(
    status_code: int = 200,
    json_data: dict[str, Any] | None = None,
    text: str | None = None,
    headers: dict[str, str] | None = None,
) -> AsyncMock:
    """Create a mock HTTP response object.

    Args:
        status_code: HTTP status code
        json_data: JSON response data
        text: Text response data
        headers: Response headers

    Returns:
        AsyncMock configured as httpx.Response

    Example:
        response = create_mock_response(
            status_code=200,
            json_data={"detections": [{"label": "person"}]},
        )
    """
    mock_response = AsyncMock()
    mock_response.status_code = status_code
    mock_response.headers = headers or {}

    if json_data is not None:
        mock_response.json.return_value = json_data
    if text is not None:
        mock_response.text = text

    return mock_response


# =============================================================================
# Database Mock Factories
# =============================================================================


def create_mock_db_session(
    execute_results: list[Any] | None = None,
    commit_side_effect: Exception | None = None,
) -> AsyncMock:
    """Create a mock database session with query result mocks.

    Args:
        execute_results: List of results to return from execute() calls
        commit_side_effect: Exception to raise on commit()

    Returns:
        AsyncMock configured as AsyncSession

    Example:
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [camera1, camera2]

        session = create_mock_db_session(execute_results=[mock_result])
    """
    mock_session = AsyncMock()

    # Configure execute() to return results sequentially
    if execute_results:
        mock_session.execute.side_effect = execute_results

    # Configure commit behavior
    if commit_side_effect:
        mock_session.commit.side_effect = commit_side_effect

    return mock_session


def create_mock_query_result(
    scalars: list[Any] | None = None,
    first: Any | None = None,
    all_results: list[Any] | None = None,
) -> MagicMock:
    """Create a mock SQLAlchemy query result object.

    Args:
        scalars: Results for scalars().all() or scalars().first()
        first: Result for first() or scalars().first()
        all_results: Results for all() or scalars().all()

    Returns:
        MagicMock configured as SQLAlchemy Result

    Example:
        result = create_mock_query_result(scalars=[camera1, camera2])
        # result.scalars().all() returns [camera1, camera2]
    """
    mock_result = MagicMock()

    if scalars is not None or all_results is not None:
        items = scalars or all_results or []
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = items
        mock_scalars.first.return_value = items[0] if items else None
        mock_result.scalars.return_value = mock_scalars

    if first is not None:
        mock_result.first.return_value = first

    return mock_result


# =============================================================================
# AI Service Mock Factories
# =============================================================================


def create_mock_detector_client(
    health_status: str = "healthy",
    detect_response: list[dict[str, Any]] | None = None,
) -> AsyncMock:
    """Create a mock RT-DETR detector client.

    Args:
        health_status: Health check status
        detect_response: Detection results to return

    Returns:
        AsyncMock configured as DetectorClient

    Example:
        mock_client = create_mock_detector_client(
            detect_response=[
                {"label": "person", "confidence": 0.95, "bbox": [100, 200, 150, 300]}
            ]
        )
    """
    mock_client = AsyncMock()
    mock_client.check_health.return_value = {"status": health_status}

    if detect_response:
        mock_client.detect.return_value = detect_response

    return mock_client


def create_mock_nemotron_client(
    health_status: str = "healthy",
    analyze_response: dict[str, Any] | None = None,
) -> AsyncMock:
    """Create a mock Nemotron LLM client.

    Args:
        health_status: Health check status
        analyze_response: Analysis result to return

    Returns:
        AsyncMock configured as NemotronClient

    Example:
        mock_client = create_mock_nemotron_client(
            analyze_response={
                "risk_score": 75,
                "risk_level": "high",
                "summary": "Person detected at entry point",
                "reasoning": "High risk activity",
            }
        )
    """
    mock_client = AsyncMock()
    mock_client.check_health.return_value = {"status": health_status}

    if analyze_response:
        mock_client.analyze.return_value = analyze_response

    return mock_client


# =============================================================================
# Context Manager Helpers
# =============================================================================


def create_mock_async_context(mock_instance: AsyncMock) -> AsyncMock:
    """Configure a mock to work as an async context manager.

    Args:
        mock_instance: The mock to configure

    Returns:
        The same mock, configured for async context manager usage

    Example:
        mock_client = AsyncMock()
        create_mock_async_context(mock_client)

        # Now works with async with
        async with mock_client as client:
            await client.get("/endpoint")
    """
    mock_instance.__aenter__.return_value = mock_instance
    mock_instance.__aexit__.return_value = None
    return mock_instance


# =============================================================================
# Assertion Helpers
# =============================================================================


def assert_called_once_with_partial(
    mock_obj: Mock | AsyncMock,
    method_name: str,
    **expected_kwargs: Any,
) -> None:
    """Assert a mock method was called once with kwargs matching a subset.

    Useful when you want to verify specific kwargs without caring about all args.

    Args:
        mock_obj: The mock object
        method_name: The method name to check
        **expected_kwargs: Expected kwargs that must be present

    Raises:
        AssertionError: If assertion fails

    Example:
        mock_redis.set.assert_called_once()
        assert_called_once_with_partial(
            mock_redis, "set",
            key="test_key",
            # Don't care about expire, nx, etc.
        )
    """
    method = getattr(mock_obj, method_name)
    if not method.called:
        raise AssertionError(f"{method_name} was not called")

    if method.call_count != 1:
        raise AssertionError(f"{method_name} was called {method.call_count} times, expected 1")

    actual_call = method.call_args
    actual_kwargs = actual_call.kwargs if actual_call else {}

    missing_keys = set(expected_kwargs.keys()) - set(actual_kwargs.keys())
    if missing_keys:
        raise AssertionError(f"Expected kwargs {missing_keys} not found in call to {method_name}")

    for key, expected_value in expected_kwargs.items():
        actual_value = actual_kwargs[key]
        if actual_value != expected_value:
            raise AssertionError(
                f"For kwarg '{key}': expected {expected_value!r}, got {actual_value!r}"
            )


def get_call_kwargs(mock_obj: Mock | AsyncMock, method_name: str, call_index: int = 0) -> dict:
    """Extract kwargs from a specific call to a mock method.

    Args:
        mock_obj: The mock object
        method_name: The method name
        call_index: Which call to extract (0-indexed)

    Returns:
        Dict of kwargs from that call

    Example:
        mock_redis.set("key1", "value1", expire=100)
        kwargs = get_call_kwargs(mock_redis, "set", 0)
        assert kwargs["expire"] == 100
    """
    method = getattr(mock_obj, method_name)
    if not method.called:
        raise AssertionError(f"{method_name} was not called")

    if call_index >= method.call_count:
        raise IndexError(
            f"Call index {call_index} out of range (method called {method.call_count} times)"
        )

    return method.call_args_list[call_index].kwargs


# =============================================================================
# Factory Combinators
# =============================================================================


def create_mock_service_with_deps(
    service_class: type,
    redis: AsyncMock | None = None,
    db_session: AsyncMock | None = None,
    http_client: AsyncMock | None = None,
    **extra_deps: Any,
) -> tuple[Any, dict[str, Any]]:
    """Create a mock service with all its dependencies pre-mocked.

    This is useful for testing services that have multiple injected dependencies.

    Args:
        service_class: The service class to instantiate
        redis: Mock Redis client (or None to create default)
        db_session: Mock DB session (or None to create default)
        http_client: Mock HTTP client (or None to create default)
        **extra_deps: Additional constructor arguments

    Returns:
        Tuple of (service_instance, dict of mock dependencies)

    Example:
        service, mocks = create_mock_service_with_deps(
            DetectionService,
            http_client=create_mock_http_client(),
        )

        # Use service normally, mocks are tracked
        await service.process_image("/path/to/image.jpg")
        mocks["http_client"].post.assert_called_once()
    """
    # Create default mocks if not provided
    mocks = {
        "redis": redis or create_mock_redis(),
        "db_session": db_session or create_mock_db_session(),
        "http_client": http_client or create_mock_http_client(),
    }

    # Merge extra dependencies
    constructor_args = {**mocks, **extra_deps}

    # Instantiate service
    service = service_class(**constructor_args)

    return service, mocks


# =============================================================================
# Parametrize Helpers
# =============================================================================


def parametrize_http_status_codes(
    success_codes: list[int] | None = None,
    error_codes: list[int] | None = None,
) -> list[int]:
    """Generate a list of HTTP status codes for parametrized tests.

    Args:
        success_codes: Success codes to include (default: [200, 201, 204])
        error_codes: Error codes to include (default: [400, 401, 403, 404, 500, 503])

    Returns:
        List of status codes

    Example:
        @pytest.mark.parametrize("status_code", parametrize_http_status_codes())
        def test_http_response(status_code):
            ...
    """
    success = success_codes or [200, 201, 204]
    errors = error_codes or [400, 401, 403, 404, 500, 503]
    return success + errors


def parametrize_risk_levels() -> list[tuple[int, str]]:
    """Generate risk score/level pairs for parametrized tests.

    Returns:
        List of (risk_score, risk_level) tuples

    Example:
        @pytest.mark.parametrize("risk_score,risk_level", parametrize_risk_levels())
        def test_risk_assessment(risk_score, risk_level):
            ...
    """
    return [
        (0, "low"),
        (10, "low"),
        (30, "low"),
        (40, "medium"),
        (50, "medium"),
        (60, "medium"),
        (70, "high"),
        (80, "high"),
        (90, "high"),
        (95, "critical"),
        (100, "critical"),
    ]


def parametrize_object_types() -> list[str]:
    """Generate object types for parametrized detection tests.

    Returns:
        List of object type strings

    Example:
        @pytest.mark.parametrize("object_type", parametrize_object_types())
        def test_detection_filtering(object_type):
            ...
    """
    return ["person", "vehicle", "animal", "package", "unknown"]
