"""Integration tests for audit API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from backend.models.audit import AuditAction
from backend.services.audit import AuditService

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


class TestAuditAPI:
    """Integration tests for the audit API endpoints."""

    @pytest.mark.asyncio
    async def test_list_audit_logs_empty(self, client: AsyncClient):
        """Test listing audit logs when empty."""
        response = await client.get("/api/audit")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "pagination" in data

    @pytest.mark.asyncio
    async def test_list_audit_logs_with_data(self, client: AsyncClient, db_session: AsyncSession):
        """Test listing audit logs with existing data."""
        # Create some audit logs
        for i in range(3):
            await AuditService.log_action(
                db=db_session,
                action=AuditAction.CAMERA_CREATED,
                resource_type="camera",
                resource_id=f"camera-{i}",
                actor="test_user",
            )
        await db_session.commit()

        # Request with include_total_count=true to get accurate total
        response = await client.get("/api/audit?include_total_count=true")
        assert response.status_code == 200

        data = response.json()
        assert data["pagination"]["total"] >= 3
        assert len(data["items"]) >= 3

    @pytest.mark.asyncio
    async def test_list_audit_logs_filter_by_action(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test filtering audit logs by action."""
        # Create logs with different actions
        await AuditService.log_action(
            db=db_session,
            action=AuditAction.EVENT_REVIEWED,
            resource_type="event",
            resource_id="event-1",
            actor="user1",
        )
        await AuditService.log_action(
            db=db_session,
            action=AuditAction.CAMERA_DELETED,
            resource_type="camera",
            resource_id="camera-1",
            actor="user1",
        )
        await db_session.commit()

        # Filter by action
        response = await client.get("/api/audit?action=event_reviewed")
        assert response.status_code == 200

        data = response.json()
        assert all(log["action"] == "event_reviewed" for log in data["items"])

    @pytest.mark.asyncio
    async def test_list_audit_logs_filter_by_resource_type(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test filtering audit logs by resource type."""
        await AuditService.log_action(
            db=db_session,
            action=AuditAction.CAMERA_CREATED,
            resource_type="camera",
            resource_id="camera-1",
            actor="user1",
        )
        await AuditService.log_action(
            db=db_session,
            action=AuditAction.EVENT_REVIEWED,
            resource_type="event",
            resource_id="event-1",
            actor="user1",
        )
        await db_session.commit()

        response = await client.get("/api/audit?resource_type=camera")
        assert response.status_code == 200

        data = response.json()
        assert all(log["resource_type"] == "camera" for log in data["items"])

    @pytest.mark.asyncio
    async def test_list_audit_logs_filter_by_actor(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test filtering audit logs by actor."""
        await AuditService.log_action(
            db=db_session,
            action=AuditAction.SETTINGS_CHANGED,
            resource_type="settings",
            actor="admin_user",
        )
        await AuditService.log_action(
            db=db_session,
            action=AuditAction.SETTINGS_CHANGED,
            resource_type="settings",
            actor="regular_user",
        )
        await db_session.commit()

        response = await client.get("/api/audit?actor=admin_user")
        assert response.status_code == 200

        data = response.json()
        assert all(log["actor"] == "admin_user" for log in data["items"])

    @pytest.mark.asyncio
    async def test_list_audit_logs_pagination(self, client: AsyncClient, db_session: AsyncSession):
        """Test pagination of audit logs."""
        # Create 15 logs
        for i in range(15):
            await AuditService.log_action(
                db=db_session,
                action=AuditAction.CAMERA_UPDATED,
                resource_type="camera",
                resource_id=f"camera-{i}",
                actor="system",
            )
        await db_session.commit()

        # Get first page
        response1 = await client.get("/api/audit?limit=5&offset=0")
        assert response1.status_code == 200
        data1 = response1.json()
        assert len(data1["items"]) == 5

        # Get second page
        response2 = await client.get("/api/audit?limit=5&offset=5")
        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2["items"]) == 5

        # Ensure no overlap
        ids1 = {log["id"] for log in data1["items"]}
        ids2 = {log["id"] for log in data2["items"]}
        assert ids1.isdisjoint(ids2)

    @pytest.mark.asyncio
    async def test_get_audit_log_by_id(self, client: AsyncClient, db_session: AsyncSession):
        """Test getting a specific audit log by ID."""
        log = await AuditService.log_action(
            db=db_session,
            action=AuditAction.MEDIA_EXPORTED,
            resource_type="event",
            actor="export_user",
            details={"filename": "events.csv", "count": 100},
        )
        await db_session.commit()

        response = await client.get(f"/api/audit/{log.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == log.id
        assert data["action"] == "media_exported"
        assert data["resource_type"] == "event"
        assert data["actor"] == "export_user"
        assert data["details"]["filename"] == "events.csv"

    @pytest.mark.asyncio
    async def test_get_audit_log_not_found(self, client: AsyncClient):
        """Test getting a non-existent audit log."""
        response = await client.get("/api/audit/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_audit_stats(self, client: AsyncClient, db_session: AsyncSession):
        """Test the audit statistics endpoint."""
        # Create diverse audit logs
        actions = [
            AuditAction.CAMERA_CREATED,
            AuditAction.CAMERA_CREATED,
            AuditAction.EVENT_REVIEWED,
            AuditAction.SETTINGS_CHANGED,
        ]
        for i, action in enumerate(actions):
            await AuditService.log_action(
                db=db_session,
                action=action,
                resource_type="camera"
                if "CAMERA" in action.name
                else "event"
                if "EVENT" in action.name
                else "settings",
                resource_id=f"resource-{i}",
                actor="test_user" if i < 2 else "admin_user",
            )
        await db_session.commit()

        response = await client.get("/api/audit/stats")
        assert response.status_code == 200

        data = response.json()
        assert "total_logs" in data
        assert "logs_today" in data
        assert "by_action" in data
        assert "by_resource_type" in data
        assert "by_status" in data
        assert "recent_actors" in data


class TestAuditIntegration:
    """Test that audit logging is integrated with other endpoints.

    These tests verify that camera CRUD operations properly create audit logs.
    """

    @pytest.mark.asyncio
    async def test_camera_create_logs_audit(self, client: AsyncClient, db_session: AsyncSession):
        """Test that creating a camera creates an audit log."""
        response = await client.post(
            "/api/cameras",
            json={
                "name": "Test Audit Camera",
                "folder_path": "/test/path",
                "status": "online",
            },
        )
        assert response.status_code == 201

        # Check for audit log
        response = await client.get("/api/audit?action=camera_created")
        assert response.status_code == 200

        data = response.json()
        camera_logs = [
            log
            for log in data["items"]
            if log["details"] and log["details"].get("name") == "Test Audit Camera"
        ]
        assert len(camera_logs) >= 1

    @pytest.mark.asyncio
    async def test_camera_delete_logs_audit(self, client: AsyncClient, db_session: AsyncSession):
        """Test that deleting a camera creates an audit log."""
        # First create a camera
        create_response = await client.post(
            "/api/cameras",
            json={
                "name": "Camera To Delete",
                "folder_path": "/test/delete",
                "status": "online",
            },
        )
        camera_id = create_response.json()["id"]

        # Delete it
        delete_response = await client.delete(f"/api/cameras/{camera_id}")
        assert delete_response.status_code == 204

        # Check for audit log
        response = await client.get("/api/audit?action=camera_deleted")
        assert response.status_code == 200

        data = response.json()
        delete_logs = [log for log in data["items"] if log["resource_id"] == camera_id]
        assert len(delete_logs) >= 1
