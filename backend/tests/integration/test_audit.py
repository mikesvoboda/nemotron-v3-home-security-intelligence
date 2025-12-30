"""Integration tests for audit logging functionality with real database.

These tests require a real PostgreSQL database (test_db fixture).
For unit tests with mocked sessions, see backend/tests/unit/test_audit.py
"""

from __future__ import annotations

import os

import pytest

from backend.models.audit import AuditAction
from backend.services.audit import AuditService

# Mark as integration tests requiring real PostgreSQL database
pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    "CI" not in os.environ,
    reason="Database tests require PostgreSQL - run in CI or with TEST_DATABASE_URL set",
)
class TestAuditServiceDatabase:
    """Integration tests for AuditService with real database."""

    @pytest.mark.asyncio
    async def test_log_and_retrieve_audit(self, test_db):
        """Test logging and retrieving audit entries from database."""
        async with test_db() as session:
            # Log an action
            await AuditService.log_action(
                db=session,
                action=AuditAction.CAMERA_CREATED,
                resource_type="camera",
                resource_id="test-camera-1",
                actor="test_user",
                details={"name": "Test Camera"},
            )
            await session.commit()

            # Retrieve the logs
            logs, count = await AuditService.get_audit_logs(
                db=session,
                action="camera_created",
            )

            assert count >= 1
            assert any(log.resource_id == "test-camera-1" for log in logs)

    @pytest.mark.asyncio
    async def test_get_audit_logs_with_filters(self, test_db):
        """Test filtering audit logs."""
        async with test_db() as session:
            # Create multiple audit logs
            for i in range(5):
                await AuditService.log_action(
                    db=session,
                    action=AuditAction.EVENT_REVIEWED
                    if i % 2 == 0
                    else AuditAction.EVENT_DISMISSED,
                    resource_type="event",
                    resource_id=f"event-{i}",
                    actor="test_user" if i < 3 else "other_user",
                )
            await session.commit()

            # Filter by action
            logs, _count = await AuditService.get_audit_logs(
                db=session,
                action="event_reviewed",
            )
            assert all(log.action == "event_reviewed" for log in logs)

            # Filter by actor
            logs, _count = await AuditService.get_audit_logs(
                db=session,
                actor="test_user",
            )
            assert all(log.actor == "test_user" for log in logs)

    @pytest.mark.asyncio
    async def test_get_audit_logs_pagination(self, test_db):
        """Test pagination of audit logs."""
        async with test_db() as session:
            # Create 10 audit logs
            for i in range(10):
                await AuditService.log_action(
                    db=session,
                    action=AuditAction.CAMERA_UPDATED,
                    resource_type="camera",
                    resource_id=f"camera-{i}",
                    actor="system",
                )
            await session.commit()

            # Test pagination
            logs_page1, total = await AuditService.get_audit_logs(
                db=session,
                action="camera_updated",
                limit=5,
                offset=0,
            )
            assert len(logs_page1) == 5 or len(logs_page1) == total

            if total > 5:
                logs_page2, _ = await AuditService.get_audit_logs(
                    db=session,
                    action="camera_updated",
                    limit=5,
                    offset=5,
                )
                # Ensure no overlap
                page1_ids = {log.id for log in logs_page1}
                page2_ids = {log.id for log in logs_page2}
                assert page1_ids.isdisjoint(page2_ids)

    @pytest.mark.asyncio
    async def test_get_audit_log_by_id(self, test_db):
        """Test retrieving a specific audit log by ID."""
        async with test_db() as session:
            # Create an audit log
            log = await AuditService.log_action(
                db=session,
                action=AuditAction.MEDIA_EXPORTED,
                resource_type="event",
                actor="test_user",
                details={"filename": "export.csv"},
            )
            await session.commit()

            # Retrieve by ID
            retrieved = await AuditService.get_audit_log_by_id(db=session, audit_id=log.id)

            assert retrieved is not None
            assert retrieved.id == log.id
            assert retrieved.action == "media_exported"

    @pytest.mark.asyncio
    async def test_get_audit_log_by_id_not_found(self, test_db):
        """Test retrieving a non-existent audit log."""
        async with test_db() as session:
            result = await AuditService.get_audit_log_by_id(db=session, audit_id=99999)
            assert result is None
