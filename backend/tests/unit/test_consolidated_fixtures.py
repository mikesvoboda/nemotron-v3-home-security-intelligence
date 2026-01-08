"""Unit tests for consolidated mock fixtures (NEM-1448).

This module validates that the consolidated mock fixtures defined in conftest.py
work as expected and can be used to simplify test code across the codebase.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestMockDbSession:
    """Tests for the mock_db_session fixture."""

    def test_has_sync_operations(self, mock_db_session: AsyncMock) -> None:
        """Test that sync operations are MagicMock."""
        assert isinstance(mock_db_session.add, MagicMock)
        assert isinstance(mock_db_session.add_all, MagicMock)
        assert isinstance(mock_db_session.expunge, MagicMock)
        assert isinstance(mock_db_session.expunge_all, MagicMock)

    def test_has_async_operations(self, mock_db_session: AsyncMock) -> None:
        """Test that async operations are AsyncMock."""
        assert isinstance(mock_db_session.commit, AsyncMock)
        assert isinstance(mock_db_session.refresh, AsyncMock)
        assert isinstance(mock_db_session.flush, AsyncMock)
        assert isinstance(mock_db_session.rollback, AsyncMock)
        assert isinstance(mock_db_session.close, AsyncMock)
        assert isinstance(mock_db_session.delete, AsyncMock)
        assert isinstance(mock_db_session.get, AsyncMock)
        assert isinstance(mock_db_session.scalar, AsyncMock)
        assert isinstance(mock_db_session.execute, AsyncMock)

    @pytest.mark.asyncio
    async def test_execute_returns_result(self, mock_db_session: AsyncMock) -> None:
        """Test that execute returns a configurable result."""
        result = await mock_db_session.execute("SELECT 1")
        assert result is not None
        assert result.scalars().all() == []
        assert result.scalars().first() is None

    @pytest.mark.asyncio
    async def test_can_configure_execute_result(self, mock_db_session: AsyncMock) -> None:
        """Test that execute result can be configured with custom data."""
        # Configure custom return data
        mock_camera = MagicMock()
        mock_camera.id = "front_door"
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = [mock_camera]

        result = await mock_db_session.execute("SELECT * FROM cameras")
        cameras = result.scalars().all()

        assert len(cameras) == 1
        assert cameras[0].id == "front_door"

    @pytest.mark.asyncio
    async def test_add_and_commit_flow(self, mock_db_session: AsyncMock) -> None:
        """Test typical add/commit flow works."""
        mock_entity = MagicMock()

        mock_db_session.add(mock_entity)
        await mock_db_session.commit()

        mock_db_session.add.assert_called_once_with(mock_entity)
        mock_db_session.commit.assert_called_once()


class TestMockDbSessionContext:
    """Tests for the mock_db_session_context fixture."""

    @pytest.mark.asyncio
    async def test_async_context_manager(
        self, mock_db_session: AsyncMock, mock_db_session_context: AsyncMock
    ) -> None:
        """Test that context manager yields mock_db_session."""
        async with mock_db_session_context as session:
            assert session is mock_db_session

    @pytest.mark.asyncio
    async def test_can_patch_get_session(
        self, mock_db_session: AsyncMock, mock_db_session_context: AsyncMock
    ) -> None:
        """Test integration with patching get_session."""
        with patch("backend.core.database.get_session", return_value=mock_db_session_context):
            # Simulate code that uses get_session
            from backend.core.database import get_session

            async with get_session() as session:
                session.add(MagicMock())
                await session.commit()

            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()


class TestMockHttpResponse:
    """Tests for the mock_http_response fixture."""

    def test_default_values(self, mock_http_response: MagicMock) -> None:
        """Test default response values."""
        assert mock_http_response.status_code == 200
        assert mock_http_response.json() == {}
        assert mock_http_response.text == ""
        assert mock_http_response.content == b""
        assert mock_http_response.is_success is True
        assert mock_http_response.is_error is False

    def test_can_configure_json(self, mock_http_response: MagicMock) -> None:
        """Test that json response can be configured."""
        mock_http_response.json.return_value = {"detections": [{"label": "person"}]}

        assert mock_http_response.json() == {"detections": [{"label": "person"}]}

    def test_can_configure_status(self, mock_http_response: MagicMock) -> None:
        """Test that status code can be modified."""
        mock_http_response.status_code = 404

        assert mock_http_response.status_code == 404


class TestMockHttpClient:
    """Tests for the mock_http_client fixture."""

    @pytest.mark.asyncio
    async def test_async_context_manager(self, mock_http_client: AsyncMock) -> None:
        """Test that client supports async context manager."""
        async with mock_http_client as client:
            assert client is mock_http_client

    @pytest.mark.asyncio
    async def test_has_http_methods(self, mock_http_client: AsyncMock) -> None:
        """Test that all HTTP methods are available."""
        assert isinstance(mock_http_client.get, AsyncMock)
        assert isinstance(mock_http_client.post, AsyncMock)
        assert isinstance(mock_http_client.put, AsyncMock)
        assert isinstance(mock_http_client.delete, AsyncMock)
        assert isinstance(mock_http_client.patch, AsyncMock)
        assert isinstance(mock_http_client.head, AsyncMock)
        assert isinstance(mock_http_client.options, AsyncMock)

    @pytest.mark.asyncio
    async def test_can_configure_response(
        self, mock_http_client: AsyncMock, mock_http_response: MagicMock
    ) -> None:
        """Test that HTTP methods can return mock response."""
        mock_http_response.json.return_value = {"status": "healthy"}
        mock_http_client.get.return_value = mock_http_response

        response = await mock_http_client.get("/health")

        assert response.json() == {"status": "healthy"}
        mock_http_client.get.assert_called_once_with("/health")


class TestMockDetectorClient:
    """Tests for the mock_detector_client fixture."""

    @pytest.mark.asyncio
    async def test_detect_objects_default(self, mock_detector_client: AsyncMock) -> None:
        """Test default detect_objects returns empty list."""
        result = await mock_detector_client.detect_objects("/path/to/image.jpg", "camera_id", None)
        assert result == []

    @pytest.mark.asyncio
    async def test_health_check_default(self, mock_detector_client: AsyncMock) -> None:
        """Test default health_check returns True."""
        result = await mock_detector_client.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_can_configure_detections(self, mock_detector_client: AsyncMock) -> None:
        """Test that detections can be configured."""
        mock_detection = MagicMock()
        mock_detection.object_type = "person"
        mock_detection.confidence = 0.95
        mock_detector_client.detect_objects.return_value = [mock_detection]

        result = await mock_detector_client.detect_objects("/path/to/image.jpg", "camera_id", None)

        assert len(result) == 1
        assert result[0].object_type == "person"


class TestMockNemotronClient:
    """Tests for the mock_nemotron_client fixture."""

    @pytest.mark.asyncio
    async def test_analyze_default(self, mock_nemotron_client: AsyncMock) -> None:
        """Test default analyze returns low risk assessment."""
        result = await mock_nemotron_client.analyze([])

        assert result["risk_score"] == 25
        assert result["risk_level"] == "low"

    @pytest.mark.asyncio
    async def test_health_check_default(self, mock_nemotron_client: AsyncMock) -> None:
        """Test default health_check returns True."""
        result = await mock_nemotron_client.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_can_configure_analysis(self, mock_nemotron_client: AsyncMock) -> None:
        """Test that analysis can be configured."""
        mock_nemotron_client.analyze.return_value = {
            "risk_score": 85,
            "risk_level": "high",
            "summary": "Suspicious activity",
            "reasoning": "High risk patterns detected",
        }

        result = await mock_nemotron_client.analyze([])

        assert result["risk_score"] == 85
        assert result["risk_level"] == "high"


class TestMockRedisClient:
    """Tests for the mock_redis_client fixture."""

    @pytest.mark.asyncio
    async def test_basic_operations(self, mock_redis_client: AsyncMock) -> None:
        """Test basic Redis operations."""
        # Default get returns None
        result = await mock_redis_client.get("key")
        assert result is None

        # Set returns True
        result = await mock_redis_client.set("key", "value")
        assert result is True

        # Delete returns 1
        result = await mock_redis_client.delete("key")
        assert result == 1

    @pytest.mark.asyncio
    async def test_pubsub_operations(self, mock_redis_client: AsyncMock) -> None:
        """Test pub/sub operations."""
        result = await mock_redis_client.publish("channel", "message")
        assert result == 1  # Default 1 subscriber

    @pytest.mark.asyncio
    async def test_list_operations(self, mock_redis_client: AsyncMock) -> None:
        """Test list operations."""
        assert await mock_redis_client.lpush("list", "item") == 1
        assert await mock_redis_client.rpush("list", "item") == 1
        assert await mock_redis_client.llen("list") == 0  # Default empty
        assert await mock_redis_client.lrange("list", 0, -1) == []

    @pytest.mark.asyncio
    async def test_health_check(self, mock_redis_client: AsyncMock) -> None:
        """Test health check returns healthy status."""
        result = await mock_redis_client.health_check()

        assert result["status"] == "healthy"
        assert result["connected"] is True

    @pytest.mark.asyncio
    async def test_queue_safe(self, mock_redis_client: AsyncMock) -> None:
        """Test add_to_queue_safe returns success."""
        result = await mock_redis_client.add_to_queue_safe("queue", "item")

        assert result.success is True
        assert result.queue_length == 1

    @pytest.mark.asyncio
    async def test_can_configure_get(self, mock_redis_client: AsyncMock) -> None:
        """Test that get can be configured to return data."""
        mock_redis_client.get.return_value = '{"cached": "data"}'

        result = await mock_redis_client.get("key")

        assert result == '{"cached": "data"}'


class TestMockSettings:
    """Tests for the mock_settings fixture."""

    def test_database_settings(self, mock_settings: MagicMock) -> None:
        """Test database settings are configured."""
        assert "postgresql" in mock_settings.database_url
        assert mock_settings.database_pool_size == 5

    def test_redis_settings(self, mock_settings: MagicMock) -> None:
        """Test Redis settings are configured."""
        assert "redis://" in mock_settings.redis_url

    def test_ai_settings(self, mock_settings: MagicMock) -> None:
        """Test AI service settings are configured."""
        assert mock_settings.ai_host == "localhost"
        assert mock_settings.detector_port == 8001
        assert mock_settings.nemotron_port == 8002

    def test_can_override_settings(self, mock_settings: MagicMock) -> None:
        """Test that settings can be overridden."""
        mock_settings.detector_port = 9001

        assert mock_settings.detector_port == 9001


class TestMockBaselineService:
    """Tests for the mock_baseline_service fixture."""

    @pytest.mark.asyncio
    async def test_update_baseline(self, mock_baseline_service: MagicMock) -> None:
        """Test update_baseline is async."""
        await mock_baseline_service.update_baseline("camera_id", {"metric": "value"})
        mock_baseline_service.update_baseline.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_baseline_default(self, mock_baseline_service: MagicMock) -> None:
        """Test get_baseline returns None by default."""
        result = await mock_baseline_service.get_baseline("camera_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_check_anomaly_default(self, mock_baseline_service: MagicMock) -> None:
        """Test check_anomaly returns False by default."""
        result = await mock_baseline_service.check_anomaly("camera_id", {"metric": "value"})
        assert result is False
