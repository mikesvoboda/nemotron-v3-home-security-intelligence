"""Integration tests for PipelineQualityAuditService.

Tests database interactions for the AI pipeline audit service including:
- Persisting audit records
- Retrieving aggregate statistics
- Getting model leaderboard
- Getting recommendations

Uses shared fixtures from conftest.py:
- integration_db: Clean database with initialized schema
- client: httpx AsyncClient with test app
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

    from backend.models.camera import Camera
    from backend.models.event import Event


# Alias for backward compatibility
@pytest.fixture
async def async_client(client: AsyncClient) -> AsyncClient:
    """Alias for shared client fixture for backward compatibility."""
    return client


@pytest.fixture
async def _clean_audit_tables(integration_db: str):
    """Delete audit related data before test runs for proper isolation.

    Uses DELETE instead of TRUNCATE to avoid AccessExclusiveLock deadlocks.
    """
    from sqlalchemy import text

    from backend.core.database import get_engine

    async with get_engine().begin() as conn:
        # Delete in order respecting foreign key constraints
        await conn.execute(text("DELETE FROM event_audits"))
        await conn.execute(text("DELETE FROM detections"))
        await conn.execute(text("DELETE FROM events"))
        await conn.execute(text("DELETE FROM cameras"))

    yield

    # Cleanup after test
    try:
        async with get_engine().begin() as conn:
            await conn.execute(text("DELETE FROM event_audits"))
            await conn.execute(text("DELETE FROM detections"))
            await conn.execute(text("DELETE FROM events"))
            await conn.execute(text("DELETE FROM cameras"))
    except Exception:
        pass


@pytest.fixture
async def audit_test_camera(integration_db: str, _clean_audit_tables: None) -> Camera:
    """Create a sample camera for audit service tests."""
    from backend.core.database import get_session
    from backend.models.camera import Camera

    camera_id = str(uuid.uuid4())
    async with get_session() as db:
        camera = Camera(
            id=camera_id,
            name="Audit Service Test Camera",
            folder_path="/export/foscam/audit_svc_test",
            status="online",
        )
        db.add(camera)
        await db.commit()
        await db.refresh(camera)
        return camera


@pytest.fixture
async def audit_test_event(integration_db: str, audit_test_camera: Camera) -> Event:
    """Create a sample event for audit service tests."""
    from backend.core.database import get_session
    from backend.models.event import Event

    async with get_session() as db:
        event = Event(
            batch_id=str(uuid.uuid4()),
            camera_id=audit_test_camera.id,
            started_at=datetime(2025, 12, 23, 12, 0, 0, tzinfo=UTC),
            ended_at=datetime(2025, 12, 23, 12, 2, 30, tzinfo=UTC),
            risk_score=65,
            risk_level="medium",
            summary="Test event for audit service",
            reasoning="Testing audit service database persistence.",
            reviewed=False,
            llm_prompt="Test prompt for audit evaluation",
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event


class TestPipelineQualityAuditServiceIntegration:
    """Integration tests for PipelineQualityAuditService database operations."""

    @pytest.mark.asyncio
    async def test_persist_record(self, integration_db: str, audit_test_event: Event):
        """Test persisting audit record to database."""
        from backend.core.database import get_session
        from backend.models.event_audit import EventAudit
        from backend.services.pipeline_quality_audit_service import (
            PipelineQualityAuditService,
            reset_audit_service,
        )

        reset_audit_service()
        service = PipelineQualityAuditService()

        # Create a partial audit record
        audit = EventAudit(
            event_id=audit_test_event.id,
            audited_at=datetime.now(UTC),
            has_yolo26=True,
            has_florence=False,
            has_clip=False,
            has_violence=False,
            has_clothing=False,
            has_vehicle=False,
            has_pet=False,
            has_weather=False,
            has_image_quality=False,
            has_zones=False,
            has_baseline=False,
            has_cross_camera=False,
            prompt_length=100,
            prompt_token_estimate=25,
            enrichment_utilization=0.083,  # 1/12 models
        )

        # Persist using service method
        async with get_session() as session:
            persisted = await service.persist_record(audit, session)

            # Verify record was persisted with an ID
            assert persisted.id is not None
            assert persisted.event_id == audit_test_event.id
            assert persisted.has_yolo26 is True
            assert persisted.has_florence is False

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, integration_db: str, _clean_audit_tables: None):
        """Test get_stats returns empty stats when no audits exist."""
        from backend.core.database import get_session
        from backend.services.pipeline_quality_audit_service import (
            PipelineQualityAuditService,
            reset_audit_service,
        )

        reset_audit_service()
        service = PipelineQualityAuditService()

        async with get_session() as session:
            stats = await service.get_stats(session, days=7)

            assert stats["total_events"] == 0
            assert stats["audited_events"] == 0
            assert stats["fully_evaluated_events"] == 0
            assert stats["avg_quality_score"] is None
            assert stats["avg_consistency_rate"] is None

    @pytest.mark.asyncio
    async def test_get_stats_with_data(self, integration_db: str, audit_test_event: Event):
        """Test get_stats returns correct statistics with audit data."""
        from backend.core.database import get_session
        from backend.models.event_audit import EventAudit
        from backend.services.pipeline_quality_audit_service import (
            PipelineQualityAuditService,
            reset_audit_service,
        )

        reset_audit_service()
        service = PipelineQualityAuditService()

        # Create and persist an audit record
        async with get_session() as session:
            audit = EventAudit(
                event_id=audit_test_event.id,
                audited_at=datetime.now(UTC),
                has_yolo26=True,
                has_florence=True,
                has_clip=False,
                has_violence=False,
                has_clothing=True,
                has_vehicle=False,
                has_pet=False,
                has_weather=True,
                has_image_quality=False,
                has_zones=True,
                has_baseline=False,
                has_cross_camera=False,
                prompt_length=200,
                prompt_token_estimate=50,
                enrichment_utilization=0.5,
                overall_quality_score=4.0,
            )
            session.add(audit)
            await session.commit()

        # Get stats
        async with get_session() as session:
            stats = await service.get_stats(session, days=7)

            assert stats["total_events"] == 1
            assert stats["audited_events"] == 1
            assert stats["avg_quality_score"] == 4.0
            assert stats["avg_enrichment_utilization"] == 0.5
            assert stats["model_contribution_rates"]["yolo26"] == 1.0
            assert stats["model_contribution_rates"]["florence"] == 1.0
            assert stats["model_contribution_rates"]["clip"] == 0.0

    @pytest.mark.asyncio
    async def test_get_leaderboard(self, integration_db: str, audit_test_event: Event):
        """Test get_leaderboard returns model rankings."""
        from backend.core.database import get_session
        from backend.models.event_audit import EventAudit
        from backend.services.pipeline_quality_audit_service import (
            MODEL_NAMES,
            PipelineQualityAuditService,
            reset_audit_service,
        )

        reset_audit_service()
        service = PipelineQualityAuditService()

        # Create and persist an audit record
        async with get_session() as session:
            audit = EventAudit(
                event_id=audit_test_event.id,
                audited_at=datetime.now(UTC),
                has_yolo26=True,
                has_florence=True,
                has_clip=False,
                has_violence=False,
                has_clothing=False,
                has_vehicle=False,
                has_pet=False,
                has_weather=False,
                has_image_quality=False,
                has_zones=False,
                has_baseline=False,
                has_cross_camera=False,
                prompt_length=100,
                prompt_token_estimate=25,
                enrichment_utilization=0.167,
            )
            session.add(audit)
            await session.commit()

        # Get leaderboard
        async with get_session() as session:
            leaderboard = await service.get_leaderboard(session, days=7)

            # Verify structure
            assert len(leaderboard) == len(MODEL_NAMES)
            for entry in leaderboard:
                assert "model_name" in entry
                assert "contribution_rate" in entry
                assert "quality_correlation" in entry
                assert "event_count" in entry

            # Verify yolo26 and florence are at top (100% contribution)
            top_models = [e["model_name"] for e in leaderboard[:2]]
            assert "yolo26" in top_models
            assert "florence" in top_models

    @pytest.mark.asyncio
    async def test_get_recommendations_empty(self, integration_db: str, _clean_audit_tables: None):
        """Test get_recommendations returns empty list when no audits exist."""
        from backend.core.database import get_session
        from backend.services.pipeline_quality_audit_service import (
            PipelineQualityAuditService,
            reset_audit_service,
        )

        reset_audit_service()
        service = PipelineQualityAuditService()

        async with get_session() as session:
            recommendations = await service.get_recommendations(session, days=7)

            assert recommendations == []

    @pytest.mark.asyncio
    async def test_create_partial_audit(self, integration_db: str, audit_test_event: Event):
        """Test create_partial_audit creates correct audit record."""
        from backend.services.pipeline_quality_audit_service import (
            PipelineQualityAuditService,
            reset_audit_service,
        )

        reset_audit_service()
        service = PipelineQualityAuditService()

        # Create a partial audit without enrichment data
        audit = service.create_partial_audit(
            event_id=audit_test_event.id,
            llm_prompt="Test prompt",
            enriched_context=None,
            enrichment_result=None,
        )

        # Verify audit was created correctly
        assert audit.event_id == audit_test_event.id
        assert audit.has_yolo26 is True  # Always true
        assert audit.has_florence is False
        assert audit.has_clip is False
        assert audit.prompt_length == len("Test prompt")
        assert audit.prompt_token_estimate == len("Test prompt") // 4
