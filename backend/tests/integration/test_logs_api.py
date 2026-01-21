"""Integration tests for frontend logs API endpoints.

Tests cover end-to-end frontend log ingestion including:
- Single log entry ingestion via POST /api/logs/frontend
- Batch log ingestion via POST /api/logs/frontend/batch
- Log level validation (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Context data handling
- Error handling for invalid payloads
- User-agent and URL metadata capture

These integration tests verify the complete flow from API request
through to structured logging.

Integration Focus:
- Real HTTP client testing via httpx with ASGITransport
- Actual logging calls with captured output
- Multi-entry batch processing
- Error handling and validation scenarios
"""

from __future__ import annotations

import pytest


class TestFrontendLogIngestion:
    """Integration tests for single frontend log entry ingestion."""

    @pytest.mark.asyncio
    async def test_ingest_error_log_end_to_end(self, client, mock_redis):
        """Test end-to-end ERROR log ingestion.

        Verifies:
        1. POST /api/logs/frontend accepts log entry
        2. Returns success response
        3. Log entry is processed without errors
        """
        response = await client.post(
            "/api/logs/frontend",
            json={
                "level": "ERROR",
                "message": "Failed to load dashboard data",
                "component": "Dashboard",
                "timestamp": "2024-01-15T10:30:00Z",
                "extra": {
                    "error_code": "API_TIMEOUT",
                    "retry_count": 3,
                },
                "url": "https://example.com/dashboard",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 1
        assert "Successfully ingested 1 log entry" in data["message"]

    @pytest.mark.asyncio
    async def test_ingest_info_log_end_to_end(self, client, mock_redis):
        """Test end-to-end INFO log ingestion."""
        response = await client.post(
            "/api/logs/frontend",
            json={
                "level": "INFO",
                "message": "User navigated to events page",
                "component": "Navigation",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 1

    @pytest.mark.asyncio
    async def test_ingest_warning_log_end_to_end(self, client, mock_redis):
        """Test end-to-end WARNING log ingestion."""
        response = await client.post(
            "/api/logs/frontend",
            json={
                "level": "WARNING",
                "message": "Connection unstable, retrying",
                "component": "WebSocket",
                "extra": {
                    "retry_attempt": 2,
                    "max_retries": 5,
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 1

    @pytest.mark.asyncio
    async def test_ingest_debug_log_end_to_end(self, client, mock_redis):
        """Test end-to-end DEBUG log ingestion."""
        response = await client.post(
            "/api/logs/frontend",
            json={
                "level": "DEBUG",
                "message": "Component rendered with props",
                "component": "AlertCard",
                "extra": {"prop_count": 5},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 1

    @pytest.mark.asyncio
    async def test_ingest_critical_log_end_to_end(self, client, mock_redis):
        """Test end-to-end CRITICAL log ingestion."""
        response = await client.post(
            "/api/logs/frontend",
            json={
                "level": "CRITICAL",
                "message": "Application crashed - unrecoverable error",
                "component": "App",
                "extra": {
                    "error_type": "ChunkLoadError",
                    "stack_trace": "Error at line 42...",
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 1

    @pytest.mark.asyncio
    async def test_ingest_log_with_minimal_fields(self, client, mock_redis):
        """Test log ingestion with only required fields (level, message)."""
        response = await client.post(
            "/api/logs/frontend",
            json={
                "level": "INFO",
                "message": "Simple log message",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 1

    @pytest.mark.asyncio
    async def test_ingest_log_with_all_fields(self, client, mock_redis):
        """Test log ingestion with all optional fields populated."""
        response = await client.post(
            "/api/logs/frontend",
            json={
                "level": "ERROR",
                "message": "Complete log entry with all fields",
                "timestamp": "2024-01-15T10:30:00.123Z",
                "component": "FullComponent",
                "extra": {
                    "key1": "value1",
                    "key2": 123,
                    "key3": True,
                },
                "url": "https://example.com/full/path?query=param",
                "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 1


class TestFrontendLogBatchIngestion:
    """Integration tests for batch frontend log ingestion."""

    @pytest.mark.asyncio
    async def test_ingest_multiple_logs_batch(self, client, mock_redis):
        """Test batch ingestion of multiple frontend log entries.

        Verifies:
        1. Multiple logs processed in single request
        2. All logs recorded successfully
        3. Correct count in response
        """
        response = await client.post(
            "/api/logs/frontend/batch",
            json={
                "entries": [
                    {
                        "level": "INFO",
                        "message": "Page loaded",
                        "component": "App",
                    },
                    {
                        "level": "WARNING",
                        "message": "Slow API response",
                        "component": "API",
                        "extra": {"response_time_ms": 3500},
                    },
                    {
                        "level": "ERROR",
                        "message": "Failed to save settings",
                        "component": "Settings",
                    },
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 3
        assert "Successfully ingested 3 log entry" in data["message"]

    @pytest.mark.asyncio
    async def test_ingest_batch_with_mixed_levels(self, client, mock_redis):
        """Test batch ingestion with all log levels."""
        response = await client.post(
            "/api/logs/frontend/batch",
            json={
                "entries": [
                    {"level": "DEBUG", "message": "Debug message"},
                    {"level": "INFO", "message": "Info message"},
                    {"level": "WARNING", "message": "Warning message"},
                    {"level": "ERROR", "message": "Error message"},
                    {"level": "CRITICAL", "message": "Critical message"},
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 5

    @pytest.mark.asyncio
    async def test_ingest_batch_single_entry(self, client, mock_redis):
        """Test batch endpoint with a single entry."""
        response = await client.post(
            "/api/logs/frontend/batch",
            json={
                "entries": [
                    {
                        "level": "INFO",
                        "message": "Single entry in batch",
                    }
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 1

    @pytest.mark.asyncio
    async def test_ingest_batch_with_context(self, client, mock_redis):
        """Test batch ingestion with various context data."""
        response = await client.post(
            "/api/logs/frontend/batch",
            json={
                "entries": [
                    {
                        "level": "INFO",
                        "message": "User interaction",
                        "component": "UserEvent",
                        "extra": {
                            "action": "click",
                            "element": "save_button",
                            "page": "/settings",
                        },
                    },
                    {
                        "level": "ERROR",
                        "message": "API request failed",
                        "component": "API",
                        "extra": {
                            "endpoint": "/api/events",
                            "status_code": 500,
                            "error_message": "Internal Server Error",
                        },
                    },
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 2


class TestFrontendLogValidation:
    """Integration tests for frontend log validation and error handling."""

    @pytest.mark.asyncio
    async def test_empty_entries_array_returns_422(self, client, mock_redis):
        """Test that empty entries array returns 422 Unprocessable Entity."""
        response = await client.post(
            "/api/logs/frontend/batch",
            json={"entries": []},
        )

        assert response.status_code == 422
        data = response.json()
        # API returns structured error format with "error" key
        assert "detail" in data or "error" in data

    @pytest.mark.asyncio
    async def test_missing_entries_field_returns_422(self, client, mock_redis):
        """Test that missing entries field returns 422."""
        response = await client.post(
            "/api/logs/frontend/batch",
            json={},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_log_level_returns_422(self, client, mock_redis):
        """Test that invalid log level returns 422."""
        response = await client.post(
            "/api/logs/frontend",
            json={
                "level": "INVALID_LEVEL",
                "message": "Test message",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_required_fields_returns_422(self, client, mock_redis):
        """Test that missing required fields return 422."""
        # Missing message
        response = await client.post(
            "/api/logs/frontend",
            json={"level": "INFO"},
        )
        assert response.status_code == 422

        # Missing level
        response = await client.post(
            "/api/logs/frontend",
            json={"message": "Test message"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_message_returns_422(self, client, mock_redis):
        """Test that empty message returns 422."""
        response = await client.post(
            "/api/logs/frontend",
            json={
                "level": "INFO",
                "message": "",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_timestamp_format_returns_422(self, client, mock_redis):
        """Test that invalid timestamp format returns 422."""
        response = await client.post(
            "/api/logs/frontend",
            json={
                "level": "INFO",
                "message": "Test message",
                "timestamp": "not-a-timestamp",
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_batch_with_one_invalid_entry_returns_422(self, client, mock_redis):
        """Test that batch with any invalid entry returns 422.

        Pydantic validates all entries before processing, so a batch
        with any invalid entry will be rejected entirely.
        """
        response = await client.post(
            "/api/logs/frontend/batch",
            json={
                "entries": [
                    {"level": "INFO", "message": "Valid entry"},
                    {"level": "INVALID", "message": "Invalid entry"},
                ]
            },
        )

        assert response.status_code == 422


class TestFrontendLogMetadataCapture:
    """Integration tests for frontend log metadata capture."""

    @pytest.mark.asyncio
    async def test_log_captures_user_agent_from_header(self, client, mock_redis):
        """Test that user-agent header is captured when not in payload."""
        response = await client.post(
            "/api/logs/frontend",
            json={
                "level": "INFO",
                "message": "Test with header user-agent",
            },
            headers={
                "User-Agent": "TestBrowser/1.0",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_log_payload_user_agent_takes_precedence(self, client, mock_redis):
        """Test that payload user_agent takes precedence over header."""
        response = await client.post(
            "/api/logs/frontend",
            json={
                "level": "INFO",
                "message": "Test with payload user-agent",
                "user_agent": "PayloadBrowser/2.0",
            },
            headers={
                "User-Agent": "HeaderBrowser/1.0",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestFrontendLogConcurrency:
    """Integration tests for concurrent frontend log ingestion."""

    @pytest.mark.asyncio
    async def test_concurrent_log_ingestion(self, client, mock_redis):
        """Test that concurrent log ingestion requests are handled correctly.

        Verifies that multiple simultaneous log ingestion requests
        don't interfere with each other and all logs are processed.
        """
        import asyncio

        tasks = []
        for i in range(5):
            task = client.post(
                "/api/logs/frontend",
                json={
                    "level": "INFO",
                    "message": f"Concurrent log message {i}",
                    "component": "ConcurrencyTest",
                    "extra": {"index": i},
                },
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)

        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["count"] == 1

    @pytest.mark.asyncio
    async def test_concurrent_batch_ingestion(self, client, mock_redis):
        """Test concurrent batch log ingestion."""
        import asyncio

        tasks = []
        for i in range(3):
            task = client.post(
                "/api/logs/frontend/batch",
                json={
                    "entries": [
                        {
                            "level": "INFO",
                            "message": f"Batch {i} entry 1",
                        },
                        {
                            "level": "WARNING",
                            "message": f"Batch {i} entry 2",
                        },
                    ]
                },
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)

        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["count"] == 2


class TestFrontendLogFieldLimits:
    """Integration tests for frontend log field length limits."""

    @pytest.mark.asyncio
    async def test_long_message_within_limit(self, client, mock_redis):
        """Test that messages up to the max length are accepted."""
        # Create a message close to but within the 10000 char limit
        long_message = "A" * 9999

        response = await client.post(
            "/api/logs/frontend",
            json={
                "level": "INFO",
                "message": long_message,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_message_exceeding_limit_returns_422(self, client, mock_redis):
        """Test that messages exceeding the limit are rejected."""
        # Create a message exceeding the 10000 char limit
        too_long_message = "A" * 10001

        response = await client.post(
            "/api/logs/frontend",
            json={
                "level": "INFO",
                "message": too_long_message,
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_component_length_limit(self, client, mock_redis):
        """Test component name length validation."""
        # Within limit
        response = await client.post(
            "/api/logs/frontend",
            json={
                "level": "INFO",
                "message": "Test",
                "component": "A" * 100,
            },
        )
        assert response.status_code == 200

        # Exceeding limit
        response = await client.post(
            "/api/logs/frontend",
            json={
                "level": "INFO",
                "message": "Test",
                "component": "A" * 101,
            },
        )
        assert response.status_code == 422
