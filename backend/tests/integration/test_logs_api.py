"""Integration tests for logs API endpoints."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from backend.models.log import Log


@pytest.fixture
async def clean_logs(integration_db):
    """Delete logs table data before test runs for proper isolation.

    This ensures tests that expect specific log counts start with empty tables.
    Uses DELETE instead of TRUNCATE to avoid AccessExclusiveLock deadlocks
    when tests run in parallel with xdist.
    """
    from sqlalchemy import text

    from backend.core.database import get_engine

    async with get_engine().begin() as conn:
        await conn.execute(text("DELETE FROM logs"))

    yield

    # Cleanup after test too (best effort)
    try:
        async with get_engine().begin() as conn:
            await conn.execute(text("DELETE FROM logs"))
    except Exception:
        pass


@pytest.mark.asyncio
class TestLogsAPI:
    """Tests for /api/logs endpoints."""

    async def test_list_logs_empty(self, client: AsyncClient, db_session, clean_logs):
        """Test listing logs when database is empty."""
        response = await client.get("/api/logs")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["pagination"]["total"] == 0

    async def test_list_logs_with_data(self, client: AsyncClient, db_session, clean_logs):
        """Test listing logs with data."""
        log1 = Log(
            timestamp=datetime.now(UTC),
            level="INFO",
            component="test",
            message="Test message 1",
            source="backend",
        )
        log2 = Log(
            timestamp=datetime.now(UTC),
            level="ERROR",
            component="test",
            message="Test error",
            source="backend",
        )
        db_session.add_all([log1, log2])
        await db_session.commit()

        response = await client.get("/api/logs")
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 2
        assert len(data["items"]) == 2

    async def test_list_logs_filter_by_level(self, client: AsyncClient, db_session, clean_logs):
        """Test filtering logs by level."""
        log1 = Log(
            timestamp=datetime.now(UTC),
            level="INFO",
            component="test",
            message="Info message",
            source="backend",
        )
        log2 = Log(
            timestamp=datetime.now(UTC),
            level="ERROR",
            component="test",
            message="Error message",
            source="backend",
        )
        db_session.add_all([log1, log2])
        await db_session.commit()

        response = await client.get("/api/logs?level=ERROR")
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 1
        assert data["items"][0]["level"] == "ERROR"

    async def test_list_logs_filter_by_component(self, client: AsyncClient, db_session, clean_logs):
        """Test filtering logs by component."""
        log1 = Log(
            timestamp=datetime.now(UTC),
            level="INFO",
            component="file_watcher",
            message="Watching files",
            source="backend",
        )
        log2 = Log(
            timestamp=datetime.now(UTC),
            level="INFO",
            component="api",
            message="Request received",
            source="backend",
        )
        db_session.add_all([log1, log2])
        await db_session.commit()

        response = await client.get("/api/logs?component=file_watcher")
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 1
        assert data["items"][0]["component"] == "file_watcher"

    async def test_get_log_stats(self, client: AsyncClient, db_session):
        """Test getting log statistics."""
        response = await client.get("/api/logs/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_today" in data
        assert "errors_today" in data
        assert "by_component" in data

    async def test_post_frontend_log(self, client: AsyncClient, db_session, clean_logs):
        """Test submitting a frontend log."""
        payload = {
            "level": "ERROR",
            "component": "DashboardPage",
            "message": "Failed to load data",
            "extra": {"endpoint": "/api/events"},
        }
        response = await client.post("/api/logs/frontend", json=payload)
        assert response.status_code == 201

        # Verify it was stored
        response = await client.get("/api/logs?component=DashboardPage")
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 1
        assert data["items"][0]["source"] == "frontend"

    async def test_get_single_log(self, client: AsyncClient, db_session):
        """Test getting a single log by ID."""
        log = Log(
            timestamp=datetime.now(UTC),
            level="INFO",
            component="test",
            message="Test message",
            source="backend",
        )
        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)

        response = await client.get(f"/api/logs/{log.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == log.id
        assert data["message"] == "Test message"

    async def test_get_nonexistent_log(self, client: AsyncClient, db_session):
        """Test getting a nonexistent log returns 404."""
        response = await client.get("/api/logs/99999")
        assert response.status_code == 404

    async def test_list_logs_pagination(self, client: AsyncClient, db_session, clean_logs):
        """Test pagination of logs."""
        # Use a unique component to isolate this test's data from other concurrent tests
        # This avoids race conditions with shared database state in CI
        import uuid

        unique_component = f"pagination_test_{uuid.uuid4().hex[:8]}"

        for i in range(15):
            log = Log(
                timestamp=datetime.now(UTC),
                level="INFO",
                component=unique_component,
                message=f"Message {i}",
                source="backend",
            )
            db_session.add(log)
        await db_session.commit()

        # First page - filter by our unique component
        response = await client.get(f"/api/logs?component={unique_component}&limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 10
        assert data["pagination"]["total"] == 15

        # Second page - filter by our unique component
        response = await client.get(f"/api/logs?component={unique_component}&limit=10&offset=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5
