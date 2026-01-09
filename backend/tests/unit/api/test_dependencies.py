"""Unit tests for API dependency functions.

Tests for reusable entity lookup functions in backend/api/dependencies.py
that provide consistent 404 handling across route handlers.

Test cases:
- get_alert_rule_or_404: Alert rule lookup and 404 handling
- get_zone_or_404: Zone lookup with optional camera filter
- get_prompt_version_or_404: Prompt version lookup
- get_event_audit_or_404: Event audit lookup by event_id
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from backend.api.dependencies import (
    get_alert_rule_or_404,
    get_event_audit_or_404,
    get_prompt_version_or_404,
    get_zone_or_404,
)


class TestGetAlertRuleOr404:
    """Tests for the get_alert_rule_or_404 function."""

    @pytest.mark.asyncio
    async def test_returns_rule_when_found(self) -> None:
        """Test that function returns AlertRule when found in database."""
        mock_rule = MagicMock()
        mock_rule.id = str(uuid4())
        mock_rule.name = "Test Rule"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_rule

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_alert_rule_or_404(mock_rule.id, mock_db)

        assert result == mock_rule
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self) -> None:
        """Test that function raises HTTPException 404 when rule not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        rule_id = str(uuid4())
        with pytest.raises(HTTPException) as exc_info:
            await get_alert_rule_or_404(rule_id, mock_db)

        assert exc_info.value.status_code == 404
        assert "Alert rule" in exc_info.value.detail
        assert rule_id in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_error_message_includes_rule_id(self) -> None:
        """Test that the 404 error message includes the requested rule_id."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        rule_id = "test-rule-id-123"
        with pytest.raises(HTTPException) as exc_info:
            await get_alert_rule_or_404(rule_id, mock_db)

        assert rule_id in exc_info.value.detail


class TestGetZoneOr404:
    """Tests for the get_zone_or_404 function."""

    @pytest.mark.asyncio
    async def test_returns_zone_when_found(self) -> None:
        """Test that function returns Zone when found in database."""
        mock_zone = MagicMock()
        mock_zone.id = str(uuid4())
        mock_zone.name = "Test Zone"
        mock_zone.camera_id = "camera-1"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_zone

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_zone_or_404(mock_zone.id, mock_db)

        assert result == mock_zone
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_zone_when_found_with_camera_filter(self) -> None:
        """Test that function returns Zone when found with camera_id filter."""
        mock_zone = MagicMock()
        mock_zone.id = str(uuid4())
        mock_zone.name = "Test Zone"
        mock_zone.camera_id = "camera-1"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_zone

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_zone_or_404(mock_zone.id, mock_db, camera_id="camera-1")

        assert result == mock_zone
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self) -> None:
        """Test that function raises HTTPException 404 when zone not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        zone_id = str(uuid4())
        with pytest.raises(HTTPException) as exc_info:
            await get_zone_or_404(zone_id, mock_db)

        assert exc_info.value.status_code == 404
        assert "Zone" in exc_info.value.detail
        assert zone_id in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_404_with_camera_filter_not_found(self) -> None:
        """Test that 404 message includes camera_id when filter is used."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        zone_id = str(uuid4())
        camera_id = "camera-1"
        with pytest.raises(HTTPException) as exc_info:
            await get_zone_or_404(zone_id, mock_db, camera_id=camera_id)

        assert exc_info.value.status_code == 404
        assert zone_id in exc_info.value.detail
        assert camera_id in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_error_message_without_camera_filter(self) -> None:
        """Test that 404 message format is correct without camera filter."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        zone_id = "zone-123"
        with pytest.raises(HTTPException) as exc_info:
            await get_zone_or_404(zone_id, mock_db)

        # Without camera filter, should not mention "for camera"
        assert "Zone with id" in exc_info.value.detail
        assert "for camera" not in exc_info.value.detail


class TestGetPromptVersionOr404:
    """Tests for the get_prompt_version_or_404 function."""

    @pytest.mark.asyncio
    async def test_returns_version_when_found(self) -> None:
        """Test that function returns PromptVersion when found in database."""
        mock_version = MagicMock()
        mock_version.id = 42
        mock_version.model = "nemotron"
        mock_version.version = 3

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_version

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_prompt_version_or_404(42, mock_db)

        assert result == mock_version
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self) -> None:
        """Test that function raises HTTPException 404 when version not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        version_id = 999
        with pytest.raises(HTTPException) as exc_info:
            await get_prompt_version_or_404(version_id, mock_db)

        assert exc_info.value.status_code == 404
        assert "Prompt version" in exc_info.value.detail
        assert str(version_id) in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_error_message_includes_version_id(self) -> None:
        """Test that the 404 error message includes the requested version_id."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        version_id = 12345
        with pytest.raises(HTTPException) as exc_info:
            await get_prompt_version_or_404(version_id, mock_db)

        assert str(version_id) in exc_info.value.detail


class TestGetEventAuditOr404:
    """Tests for the get_event_audit_or_404 function."""

    @pytest.mark.asyncio
    async def test_returns_audit_when_found(self) -> None:
        """Test that function returns EventAudit when found in database."""
        mock_audit = MagicMock()
        mock_audit.id = 1
        mock_audit.event_id = 100
        mock_audit.overall_quality_score = 4.5

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_audit

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await get_event_audit_or_404(100, mock_db)

        assert result == mock_audit
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self) -> None:
        """Test that function raises HTTPException 404 when audit not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        event_id = 999
        with pytest.raises(HTTPException) as exc_info:
            await get_event_audit_or_404(event_id, mock_db)

        assert exc_info.value.status_code == 404
        assert "audit" in exc_info.value.detail.lower()
        assert str(event_id) in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_error_message_includes_event_id(self) -> None:
        """Test that the 404 error message includes the requested event_id."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        event_id = 54321
        with pytest.raises(HTTPException) as exc_info:
            await get_event_audit_or_404(event_id, mock_db)

        assert str(event_id) in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_error_message_format(self) -> None:
        """Test that the 404 error message has the expected format."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        event_id = 123
        with pytest.raises(HTTPException) as exc_info:
            await get_event_audit_or_404(event_id, mock_db)

        # Should match the format "No audit found for event {event_id}"
        assert "No audit found for event" in exc_info.value.detail
