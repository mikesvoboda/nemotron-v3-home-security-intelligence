"""Unit tests for centralized mock utilities.

Tests cover:
- Redis mock factories
- HTTP client mock factories
- Database mock factories
- AI service mock factories
- Context manager helpers
- Assertion helpers
- Parametrize helpers
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from backend.models.enums import Severity
from backend.tests.mock_utils import (
    assert_called_once_with_partial,
    create_mock_async_context,
    create_mock_db_session,
    create_mock_detector_client,
    create_mock_http_client,
    create_mock_nemotron_client,
    create_mock_query_result,
    create_mock_redis,
    create_mock_redis_pubsub,
    create_mock_response,
    get_call_kwargs,
    parametrize_http_status_codes,
    parametrize_object_types,
    parametrize_risk_levels,
)

# =============================================================================
# Redis Mock Factories Tests
# =============================================================================


class TestCreateMockRedis:
    """Tests for create_mock_redis factory."""

    def test_default_health_check(self) -> None:
        """Test default health check response."""
        mock_redis = create_mock_redis()

        result = mock_redis.health_check.return_value
        assert result["status"] == "healthy"
        assert result["connected"] is True
        assert result["redis_version"] == "7.0.0"

    def test_custom_health_status(self) -> None:
        """Test custom health status."""
        mock_redis = create_mock_redis(health_status="degraded", connected=False)

        result = mock_redis.health_check.return_value
        assert result["status"] == "degraded"
        assert result["connected"] is False

    def test_extra_methods_as_values(self) -> None:
        """Test adding extra methods with simple return values."""
        mock_redis = create_mock_redis(get="test_value", set=True)

        # Methods should be AsyncMock with configured return values
        assert isinstance(mock_redis.get, AsyncMock)
        assert isinstance(mock_redis.set, AsyncMock)
        assert mock_redis.get.return_value == "test_value"
        assert mock_redis.set.return_value is True

    def test_extra_methods_as_mocks(self) -> None:
        """Test adding extra methods as pre-configured mocks."""
        custom_get = AsyncMock(return_value="custom")
        mock_redis = create_mock_redis(get=custom_get)

        assert mock_redis.get is custom_get
        assert mock_redis.get.return_value == "custom"


class TestCreateMockRedisPubSub:
    """Tests for create_mock_redis_pubsub factory."""

    def test_default_pubsub(self) -> None:
        """Test default pub/sub client without messages."""
        mock_pubsub = create_mock_redis_pubsub()

        assert isinstance(mock_pubsub, AsyncMock)

    def test_pubsub_with_messages(self) -> None:
        """Test pub/sub client with configured messages."""
        messages = [
            {"type": "subscribe", "channel": "events", "data": 1},
            {"type": "message", "channel": "events", "data": '{"event": "test"}'},
        ]
        mock_pubsub = create_mock_redis_pubsub(messages=messages)

        # Should be iterable with configured messages
        assert list(mock_pubsub.__aiter__.return_value) == messages


# =============================================================================
# HTTP Client Mock Factories Tests
# =============================================================================


class TestCreateMockHttpClient:
    """Tests for create_mock_http_client factory."""

    @pytest.mark.asyncio
    async def test_default_client(self) -> None:
        """Test default HTTP client."""
        mock_client = create_mock_http_client()

        assert isinstance(mock_client, AsyncMock)

    @pytest.mark.asyncio
    async def test_get_responses(self) -> None:
        """Test configured GET responses."""
        mock_client = create_mock_http_client(
            get_responses={
                "/health": {"status": "healthy"},
                "/api/data": {"data": [1, 2, 3]},
            }
        )

        # Test GET /health
        response = await mock_client.get("/health")
        assert response.status_code == 200
        assert response.json.return_value == {"status": "healthy"}

        # Test GET /api/data
        response = await mock_client.get("/api/data")
        assert response.json.return_value == {"data": [1, 2, 3]}

    @pytest.mark.asyncio
    async def test_post_responses(self) -> None:
        """Test configured POST responses."""
        mock_client = create_mock_http_client(
            post_responses={
                "/api/create": {"id": 123, "created": True},
            }
        )

        response = await mock_client.post("/api/create")
        assert response.status_code == 200
        assert response.json.return_value == {"id": 123, "created": True}

    @pytest.mark.asyncio
    async def test_custom_status_code(self) -> None:
        """Test custom status code."""
        mock_client = create_mock_http_client(
            get_responses={"/not-found": {"error": "Not found"}},
            status_code=404,
        )

        response = await mock_client.get("/not-found")
        assert response.status_code == 404

    def test_extra_methods(self) -> None:
        """Test adding extra methods."""
        delete_mock = AsyncMock()
        mock_client = create_mock_http_client(delete=delete_mock)

        assert mock_client.delete is delete_mock


class TestCreateMockResponse:
    """Tests for create_mock_response factory."""

    def test_default_response(self) -> None:
        """Test default response."""
        response = create_mock_response()

        assert response.status_code == 200
        assert response.headers == {}

    def test_json_response(self) -> None:
        """Test response with JSON data."""
        response = create_mock_response(
            status_code=201,
            json_data={"id": 123, "name": "test"},
        )

        assert response.status_code == 201
        assert response.json.return_value == {"id": 123, "name": "test"}

    def test_text_response(self) -> None:
        """Test response with text data."""
        response = create_mock_response(text="Plain text response")

        assert response.text == "Plain text response"

    def test_custom_headers(self) -> None:
        """Test response with custom headers."""
        response = create_mock_response(
            headers={"Content-Type": "application/json", "X-Custom": "value"}
        )

        assert response.headers["Content-Type"] == "application/json"
        assert response.headers["X-Custom"] == "value"


# =============================================================================
# Database Mock Factories Tests
# =============================================================================


class TestCreateMockDbSession:
    """Tests for create_mock_db_session factory."""

    def test_default_session(self) -> None:
        """Test default database session."""
        session = create_mock_db_session()

        assert isinstance(session, AsyncMock)

    def test_session_with_execute_results(self) -> None:
        """Test session with configured execute results."""
        result1 = Mock()
        result2 = Mock()
        session = create_mock_db_session(execute_results=[result1, result2])

        # execute() should have side_effect configured
        # Convert to list to compare since side_effect might be an iterator
        assert list(session.execute.side_effect) == [result1, result2]

    def test_session_with_commit_side_effect(self) -> None:
        """Test session with commit error."""
        error = ValueError("Commit failed")
        session = create_mock_db_session(commit_side_effect=error)

        assert session.commit.side_effect is error


class TestCreateMockQueryResult:
    """Tests for create_mock_query_result factory."""

    def test_result_with_scalars(self) -> None:
        """Test query result with scalars."""
        item1 = Mock()
        item2 = Mock()
        result = create_mock_query_result(scalars=[item1, item2])

        # Test scalars().all()
        assert result.scalars().all() == [item1, item2]

        # Test scalars().first()
        assert result.scalars().first() is item1

    def test_result_with_empty_scalars(self) -> None:
        """Test query result with no items."""
        result = create_mock_query_result(scalars=[])

        assert result.scalars().all() == []
        assert result.scalars().first() is None

    def test_result_with_first(self) -> None:
        """Test query result with first() value."""
        item = Mock()
        result = create_mock_query_result(first=item)

        assert result.first() is item

    def test_result_with_all_results(self) -> None:
        """Test query result with all_results parameter."""
        items = [Mock(), Mock(), Mock()]
        result = create_mock_query_result(all_results=items)

        assert result.scalars().all() == items


# =============================================================================
# AI Service Mock Factories Tests
# =============================================================================


class TestCreateMockDetectorClient:
    """Tests for create_mock_detector_client factory."""

    def test_default_client(self) -> None:
        """Test default detector client."""
        client = create_mock_detector_client()

        assert client.check_health.return_value == {"status": "healthy"}

    def test_custom_health_status(self) -> None:
        """Test custom health status."""
        client = create_mock_detector_client(health_status="unhealthy")

        assert client.check_health.return_value == {"status": "unhealthy"}

    def test_detect_response(self) -> None:
        """Test detect response configuration."""
        detections = [
            {"label": "person", "confidence": 0.95, "bbox": [100, 200, 150, 300]},
            {"label": "vehicle", "confidence": 0.87, "bbox": [500, 300, 200, 150]},
        ]
        client = create_mock_detector_client(detect_response=detections)

        assert client.detect.return_value == detections


class TestCreateMockNemotronClient:
    """Tests for create_mock_nemotron_client factory."""

    def test_default_client(self) -> None:
        """Test default Nemotron client."""
        client = create_mock_nemotron_client()

        assert client.check_health.return_value == {"status": "healthy"}

    def test_analyze_response(self) -> None:
        """Test analyze response configuration."""
        analysis = {
            "risk_score": 75,
            "risk_level": "high",
            "summary": "Person detected at entry point",
            "reasoning": "Suspicious activity",
        }
        client = create_mock_nemotron_client(analyze_response=analysis)

        assert client.analyze.return_value == analysis


# =============================================================================
# Context Manager Helpers Tests
# =============================================================================


class TestCreateMockAsyncContext:
    """Tests for create_mock_async_context helper."""

    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        """Test mock configured as async context manager."""
        mock_obj = AsyncMock()
        create_mock_async_context(mock_obj)

        # Should work with async with
        async with mock_obj as ctx:
            assert ctx is mock_obj

        # Verify __aenter__ and __aexit__ were called
        mock_obj.__aenter__.assert_called_once()
        mock_obj.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_same_mock(self) -> None:
        """Test that helper returns the same mock instance."""
        mock_obj = AsyncMock()
        result = create_mock_async_context(mock_obj)

        assert result is mock_obj


# =============================================================================
# Assertion Helpers Tests
# =============================================================================


class TestAssertCalledOnceWithPartial:
    """Tests for assert_called_once_with_partial helper."""

    def test_succeeds_when_kwargs_match(self) -> None:
        """Test assertion succeeds when kwargs match."""
        mock_obj = Mock()
        mock_obj.set(key="test_key", value="test_value", expire=100, nx=True)

        # Should not raise - only checking key and value
        assert_called_once_with_partial(mock_obj, "set", key="test_key", value="test_value")

    def test_fails_when_not_called(self) -> None:
        """Test assertion fails when method not called."""
        mock_obj = Mock()

        with pytest.raises(AssertionError, match="was not called"):
            assert_called_once_with_partial(mock_obj, "set", key="test_key")

    def test_fails_when_called_multiple_times(self) -> None:
        """Test assertion fails when called more than once."""
        mock_obj = Mock()
        mock_obj.set(key="key1")
        mock_obj.set(key="key2")

        with pytest.raises(AssertionError, match="was called 2 times"):
            assert_called_once_with_partial(mock_obj, "set", key="key1")

    def test_fails_when_kwarg_missing(self) -> None:
        """Test assertion fails when expected kwarg missing."""
        mock_obj = Mock()
        mock_obj.set(key="test_key")

        with pytest.raises(AssertionError, match="not found"):
            assert_called_once_with_partial(mock_obj, "set", key="test_key", value="missing")

    def test_fails_when_kwarg_value_wrong(self) -> None:
        """Test assertion fails when kwarg value doesn't match."""
        mock_obj = Mock()
        mock_obj.set(key="test_key", value="actual_value")

        with pytest.raises(AssertionError, match="expected 'expected_value'"):
            assert_called_once_with_partial(mock_obj, "set", value="expected_value")


class TestGetCallKwargs:
    """Tests for get_call_kwargs helper."""

    def test_get_kwargs_from_first_call(self) -> None:
        """Test extracting kwargs from first call."""
        mock_obj = Mock()
        mock_obj.set("key1", "value1", expire=100, nx=True)

        kwargs = get_call_kwargs(mock_obj, "set", 0)
        assert kwargs["expire"] == 100
        assert kwargs["nx"] is True

    def test_get_kwargs_from_second_call(self) -> None:
        """Test extracting kwargs from second call."""
        mock_obj = Mock()
        mock_obj.set("key1", expire=100)
        mock_obj.set("key2", expire=200)

        kwargs = get_call_kwargs(mock_obj, "set", 1)
        assert kwargs["expire"] == 200

    def test_fails_when_not_called(self) -> None:
        """Test error when method not called."""
        mock_obj = Mock()

        with pytest.raises(AssertionError, match="was not called"):
            get_call_kwargs(mock_obj, "set", 0)

    def test_fails_when_index_out_of_range(self) -> None:
        """Test error when call index out of range."""
        mock_obj = Mock()
        mock_obj.set("key1")

        with pytest.raises(IndexError, match="out of range"):
            get_call_kwargs(mock_obj, "set", 5)


# =============================================================================
# Parametrize Helpers Tests
# =============================================================================


class TestParametrizeHttpStatusCodes:
    """Tests for parametrize_http_status_codes helper."""

    def test_default_codes(self) -> None:
        """Test default status codes include success and errors."""
        codes = parametrize_http_status_codes()

        # Should include success codes
        assert 200 in codes
        assert 201 in codes
        assert 204 in codes

        # Should include error codes
        assert 400 in codes
        assert 404 in codes
        assert 500 in codes

    def test_custom_success_codes(self) -> None:
        """Test custom success codes."""
        codes = parametrize_http_status_codes(success_codes=[200, 202])

        assert 200 in codes
        assert 202 in codes
        assert 201 not in codes  # Default 201 not included

    def test_custom_error_codes(self) -> None:
        """Test custom error codes."""
        codes = parametrize_http_status_codes(error_codes=[400, 401])

        assert 400 in codes
        assert 401 in codes
        assert 404 not in codes  # Default 404 not included


class TestParametrizeRiskLevels:
    """Tests for parametrize_risk_levels helper."""

    def test_returns_tuples(self) -> None:
        """Test returns list of (score, level) tuples."""
        risk_levels = parametrize_risk_levels()

        assert isinstance(risk_levels, list)
        assert all(isinstance(item, tuple) for item in risk_levels)
        assert all(len(item) == 2 for item in risk_levels)

    def test_covers_all_severity_levels(self) -> None:
        """Test covers low, medium, high, and critical."""
        risk_levels = parametrize_risk_levels()
        levels = [level for _, level in risk_levels]

        assert "low" in levels
        assert "medium" in levels
        assert "high" in levels
        assert "critical" in levels

    def test_score_ranges_correct(self) -> None:
        """Test risk scores match expected severity levels."""
        risk_levels = dict(parametrize_risk_levels())

        # Low scores
        assert risk_levels[0] == "low"
        assert risk_levels[10] == "low"
        assert risk_levels[30] == "low"

        # Medium scores
        assert risk_levels[40] == "medium"
        assert risk_levels[50] == "medium"
        assert risk_levels[60] == "medium"

        # High scores
        assert risk_levels[70] == "high"
        assert risk_levels[80] == "high"
        assert risk_levels[90] == "high"

        # Critical scores
        assert risk_levels[95] == "critical"
        assert risk_levels[100] == "critical"

    def test_boundary_values_included(self) -> None:
        """Test boundary values are included."""
        risk_levels = dict(parametrize_risk_levels())

        assert 0 in risk_levels  # Min score
        assert 100 in risk_levels  # Max score


class TestParametrizeObjectTypes:
    """Tests for parametrize_object_types helper."""

    def test_returns_list_of_strings(self) -> None:
        """Test returns list of object type strings."""
        object_types = parametrize_object_types()

        assert isinstance(object_types, list)
        assert all(isinstance(obj_type, str) for obj_type in object_types)

    def test_includes_common_types(self) -> None:
        """Test includes common detection object types."""
        object_types = parametrize_object_types()

        assert "person" in object_types
        assert "vehicle" in object_types
        assert "animal" in object_types

    def test_includes_edge_cases(self) -> None:
        """Test includes edge case types."""
        object_types = parametrize_object_types()

        assert "unknown" in object_types  # Edge case for unrecognized objects


# =============================================================================
# Integration Tests (Using Mocks Together)
# =============================================================================


class TestMockIntegration:
    """Integration tests showing how mocks work together."""

    @pytest.mark.asyncio
    async def test_redis_with_http_client(self) -> None:
        """Test using Redis and HTTP client mocks together."""
        mock_redis = create_mock_redis(health_status="healthy")
        mock_http = create_mock_http_client(get_responses={"/api": {"data": "test"}})

        # Both should be usable
        redis_health = mock_redis.health_check.return_value
        assert redis_health["status"] == "healthy"

        http_response = await mock_http.get("/api")
        assert http_response.json.return_value == {"data": "test"}

    @pytest.mark.asyncio
    async def test_full_service_mock_stack(self) -> None:
        """Test complete mock stack for a service."""
        # Create all mocks
        mock_redis = create_mock_redis()
        mock_db = create_mock_db_session()
        mock_http = create_mock_http_client()
        mock_detector = create_mock_detector_client()

        # Simulate service using all dependencies
        health = mock_detector.check_health.return_value
        assert health["status"] == "healthy"

        mock_db.execute.return_value = Mock()
        mock_db.commit.return_value = None

        # All mocks work together
        assert isinstance(mock_redis, AsyncMock)
        assert isinstance(mock_db, AsyncMock)
        assert isinstance(mock_http, AsyncMock)
        assert isinstance(mock_detector, AsyncMock)


# =============================================================================
# Parametrized Test Examples Using Helpers
# =============================================================================


class TestParametrizedExamples:
    """Example parametrized tests using the helper functions."""

    @pytest.mark.parametrize("status_code", parametrize_http_status_codes())
    def test_http_status_code_handling(self, status_code: int) -> None:
        """Example: Test HTTP status code handling."""
        response = create_mock_response(status_code=status_code)

        assert response.status_code == status_code

        # Classify response
        if 200 <= status_code < 300:
            assert status_code in [200, 201, 204]
        elif 400 <= status_code < 600:
            assert status_code in [400, 401, 403, 404, 500, 503]

    @pytest.mark.parametrize(("risk_score", "risk_level"), parametrize_risk_levels())
    def test_risk_level_classification(self, risk_score: int, risk_level: str) -> None:
        """Example: Test risk level classification."""
        # Map string level to Severity enum for validation
        severity_map = {
            "low": Severity.LOW,
            "medium": Severity.MEDIUM,
            "high": Severity.HIGH,
            "critical": Severity.CRITICAL,
        }

        assert risk_level in severity_map
        assert 0 <= risk_score <= 100

    @pytest.mark.parametrize("object_type", parametrize_object_types())
    def test_detection_object_types(self, object_type: str) -> None:
        """Example: Test detection filtering by object type."""
        # Simulate creating a detection with this object type
        assert isinstance(object_type, str)
        assert len(object_type) > 0
