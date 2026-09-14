"""Unit tests for SceneChangeService (NEM-3555, NEM-3674).

This module tests the SceneChangeService which handles:
- Creating and persisting scene changes to the database
- Broadcasting scene changes via WebSocket for real-time updates
- Acknowledging scene changes (idempotent operation)
- Querying scene changes by ID and camera
- Classifying scene change types based on similarity scores

Coverage expanded per NEM-3674 requirements:
- All async methods (create_scene_change, get_scene_change, acknowledge_scene_change)
- WebSocket emission validation
- Error handling for invalid inputs and database errors
- Edge cases (not found, idempotent acknowledgment)
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from backend.core.websocket.event_types import WebSocketEventType
from backend.models.scene_change import SceneChange, SceneChangeType
from backend.services.scene_change_service import (
    SceneChangeService,
    classify_scene_change_type,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session for testing."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_websocket_emitter() -> AsyncMock:
    """Create a mock WebSocket emitter for testing."""
    emitter = AsyncMock()
    emitter.emit = AsyncMock()
    return emitter


@pytest.fixture
def scene_change_service(
    mock_db_session: AsyncMock,
    mock_websocket_emitter: AsyncMock,
) -> SceneChangeService:
    """Create a SceneChangeService with mocked dependencies."""
    return SceneChangeService(
        session=mock_db_session,
        emitter=mock_websocket_emitter,
    )


@pytest.fixture
def scene_change_service_no_emitter(
    mock_db_session: AsyncMock,
) -> SceneChangeService:
    """Create a SceneChangeService without WebSocket emitter."""
    return SceneChangeService(session=mock_db_session, emitter=None)


# =============================================================================
# Classification Tests
# =============================================================================


class TestClassifySceneChangeType:
    """Tests for classify_scene_change_type function."""

    def test_very_low_score_is_view_blocked(self) -> None:
        assert classify_scene_change_type(0.0) == SceneChangeType.VIEW_BLOCKED
        assert classify_scene_change_type(0.29) == SceneChangeType.VIEW_BLOCKED

    def test_low_score_is_view_tampered(self) -> None:
        assert classify_scene_change_type(0.3) == SceneChangeType.VIEW_TAMPERED
        assert classify_scene_change_type(0.49) == SceneChangeType.VIEW_TAMPERED

    def test_medium_score_is_angle_changed(self) -> None:
        assert classify_scene_change_type(0.5) == SceneChangeType.ANGLE_CHANGED
        assert classify_scene_change_type(0.69) == SceneChangeType.ANGLE_CHANGED

    def test_high_score_is_unknown(self) -> None:
        assert classify_scene_change_type(0.7) == SceneChangeType.UNKNOWN
        assert classify_scene_change_type(0.89) == SceneChangeType.UNKNOWN


# =============================================================================
# Initialization Tests
# =============================================================================


class TestSceneChangeServiceInit:
    """Tests for SceneChangeService initialization."""

    def test_init_with_session_only(self) -> None:
        mock_session = MagicMock()
        service = SceneChangeService(mock_session)
        assert service._session is mock_session
        assert service._emitter is None

    def test_init_with_emitter(self) -> None:
        mock_session = MagicMock()
        mock_emitter = MagicMock()
        service = SceneChangeService(mock_session, mock_emitter)
        assert service._session is mock_session
        assert service._emitter is mock_emitter


# =============================================================================
# Create Scene Change Tests (NEM-3674)
# =============================================================================


class TestCreateSceneChange:
    """Tests for create_scene_change async method."""

    @pytest.mark.asyncio
    async def test_create_scene_change_success(
        self,
        scene_change_service: SceneChangeService,
        mock_db_session: AsyncMock,
        mock_websocket_emitter: AsyncMock,
    ) -> None:
        """Test successful scene change creation with all parameters."""
        # Mock the scene change object that will be returned
        mock_scene_change = MagicMock(spec=SceneChange)
        mock_scene_change.id = 123
        mock_scene_change.camera_id = "front_door"
        mock_scene_change.similarity_score = 0.3
        mock_scene_change.change_type = SceneChangeType.VIEW_TAMPERED
        mock_scene_change.file_path = "/path/to/frame.jpg"
        mock_scene_change.detected_at = datetime.now(UTC)
        mock_scene_change.acknowledged = False

        # Configure mock session to return our mock scene change
        mock_db_session.add = MagicMock()
        mock_db_session.flush = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        # Patch the SceneChange constructor to return our mock
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "backend.services.scene_change_service.SceneChange",
                lambda **_kwargs: mock_scene_change,
            )

            result = await scene_change_service.create_scene_change(
                camera_id="front_door",
                similarity_score=0.3,
                change_type=SceneChangeType.VIEW_TAMPERED,
                file_path="/path/to/frame.jpg",
                correlation_id="test-correlation-id",
            )

        # Verify database operations
        assert mock_db_session.add.called
        assert mock_db_session.flush.called
        assert mock_db_session.refresh.called

        # Verify WebSocket emission
        mock_websocket_emitter.emit.assert_called_once()
        call_args = mock_websocket_emitter.emit.call_args
        assert call_args[0][0] == WebSocketEventType.SCENE_CHANGE_DETECTED
        assert call_args[1]["correlation_id"] == "test-correlation-id"

        # Verify payload structure
        payload = call_args[0][1]
        assert payload["id"] == 123
        assert payload["camera_id"] == "front_door"
        assert payload["similarity_score"] == 0.3
        assert payload["change_type"] == SceneChangeType.VIEW_TAMPERED.value
        assert payload["file_path"] == "/path/to/frame.jpg"
        assert payload["acknowledged"] is False

    @pytest.mark.asyncio
    async def test_create_scene_change_minimal_params(
        self,
        scene_change_service: SceneChangeService,
        mock_db_session: AsyncMock,
        mock_websocket_emitter: AsyncMock,
    ) -> None:
        """Test scene change creation with minimal required parameters."""
        mock_scene_change = MagicMock(spec=SceneChange)
        mock_scene_change.id = 456
        mock_scene_change.camera_id = "back_yard"
        mock_scene_change.similarity_score = 0.15
        mock_scene_change.change_type = SceneChangeType.UNKNOWN
        mock_scene_change.file_path = None
        mock_scene_change.detected_at = datetime.now(UTC)
        mock_scene_change.acknowledged = False

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "backend.services.scene_change_service.SceneChange",
                lambda **_kwargs: mock_scene_change,
            )

            result = await scene_change_service.create_scene_change(
                camera_id="back_yard",
                similarity_score=0.15,
            )

        # Verify database operations
        assert mock_db_session.add.called
        assert mock_db_session.flush.called
        assert mock_db_session.refresh.called

        # Verify WebSocket emission
        assert mock_websocket_emitter.emit.called

    @pytest.mark.asyncio
    async def test_create_scene_change_without_emitter(
        self,
        scene_change_service_no_emitter: SceneChangeService,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test scene change creation when WebSocket emitter is not available."""
        mock_scene_change = MagicMock(spec=SceneChange)
        mock_scene_change.id = 789
        mock_scene_change.camera_id = "side_gate"
        mock_scene_change.similarity_score = 0.45
        mock_scene_change.change_type = SceneChangeType.ANGLE_CHANGED
        mock_scene_change.file_path = None
        mock_scene_change.detected_at = datetime.now(UTC)
        mock_scene_change.acknowledged = False

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "backend.services.scene_change_service.SceneChange",
                lambda **_kwargs: mock_scene_change,
            )

            result = await scene_change_service_no_emitter.create_scene_change(
                camera_id="side_gate",
                similarity_score=0.45,
                change_type=SceneChangeType.ANGLE_CHANGED,
            )

        # Verify database operations still occur
        assert mock_db_session.add.called
        assert mock_db_session.flush.called
        assert mock_db_session.refresh.called

    @pytest.mark.asyncio
    async def test_create_scene_change_database_error(
        self,
        scene_change_service: SceneChangeService,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test scene change creation handles database errors."""
        # Simulate database error during flush
        mock_db_session.flush.side_effect = SQLAlchemyError("Database error")

        with pytest.raises(SQLAlchemyError):
            await scene_change_service.create_scene_change(
                camera_id="front_door",
                similarity_score=0.3,
            )


# =============================================================================
# Get Scene Change Tests (NEM-3674)
# =============================================================================


class TestGetSceneChange:
    """Tests for get_scene_change async method."""

    @pytest.mark.asyncio
    async def test_get_scene_change_found(
        self,
        scene_change_service: SceneChangeService,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test retrieving an existing scene change by ID."""
        mock_scene_change = MagicMock(spec=SceneChange)
        mock_scene_change.id = 123
        mock_scene_change.camera_id = "front_door"

        # Mock the execute result
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_scene_change)
        mock_db_session.execute.return_value = mock_result

        result = await scene_change_service.get_scene_change(scene_change_id=123)

        assert result is not None
        assert result.id == 123
        assert result.camera_id == "front_door"
        assert mock_db_session.execute.called

    @pytest.mark.asyncio
    async def test_get_scene_change_not_found(
        self,
        scene_change_service: SceneChangeService,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test retrieving a non-existent scene change returns None."""
        # Mock the execute result to return None
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db_session.execute.return_value = mock_result

        result = await scene_change_service.get_scene_change(scene_change_id=999)

        assert result is None
        assert mock_db_session.execute.called

    @pytest.mark.asyncio
    async def test_get_scene_change_database_error(
        self,
        scene_change_service: SceneChangeService,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test get_scene_change handles database errors."""
        mock_db_session.execute.side_effect = SQLAlchemyError("Database error")

        with pytest.raises(SQLAlchemyError):
            await scene_change_service.get_scene_change(scene_change_id=123)


# =============================================================================
# Acknowledge Scene Change Tests (NEM-3674)
# =============================================================================


class TestAcknowledgeSceneChange:
    """Tests for acknowledge_scene_change async method."""

    @pytest.mark.asyncio
    async def test_acknowledge_scene_change_success(
        self,
        scene_change_service: SceneChangeService,
        mock_db_session: AsyncMock,
        mock_websocket_emitter: AsyncMock,
    ) -> None:
        """Test successful acknowledgment of an unacknowledged scene change."""
        # Mock an unacknowledged scene change
        mock_scene_change = MagicMock(spec=SceneChange)
        mock_scene_change.id = 123
        mock_scene_change.camera_id = "front_door"
        mock_scene_change.acknowledged = False
        mock_scene_change.acknowledged_at = None

        # Mock get_scene_change to return our mock
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_scene_change)
        mock_db_session.execute.return_value = mock_result

        result = await scene_change_service.acknowledge_scene_change(
            scene_change_id=123,
            correlation_id="ack-test-123",
        )

        # Verify the scene change was updated
        assert result is not None
        assert mock_scene_change.acknowledged is True
        assert mock_scene_change.acknowledged_at is not None

        # Verify database operations
        assert mock_db_session.flush.called
        assert mock_db_session.refresh.called

        # Verify WebSocket emission
        mock_websocket_emitter.emit.assert_called_once()
        call_args = mock_websocket_emitter.emit.call_args
        assert call_args[0][0] == WebSocketEventType.SCENE_CHANGE_ACKNOWLEDGED
        assert call_args[1]["correlation_id"] == "ack-test-123"

        # Verify payload structure
        payload = call_args[0][1]
        assert payload["id"] == 123
        assert payload["camera_id"] == "front_door"
        assert payload["acknowledged"] is True

    @pytest.mark.asyncio
    async def test_acknowledge_scene_change_idempotent(
        self,
        scene_change_service: SceneChangeService,
        mock_db_session: AsyncMock,
        mock_websocket_emitter: AsyncMock,
    ) -> None:
        """Test acknowledging an already acknowledged scene change is idempotent."""
        # Mock an already acknowledged scene change
        ack_time = datetime.now(UTC)
        mock_scene_change = MagicMock(spec=SceneChange)
        mock_scene_change.id = 456
        mock_scene_change.camera_id = "back_yard"
        mock_scene_change.acknowledged = True
        mock_scene_change.acknowledged_at = ack_time

        # Mock get_scene_change to return our mock
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_scene_change)
        mock_db_session.execute.return_value = mock_result

        result = await scene_change_service.acknowledge_scene_change(scene_change_id=456)

        # Verify the scene change is returned unchanged
        assert result is not None
        assert result.acknowledged is True
        assert result.acknowledged_at == ack_time

        # Verify database operations were NOT called (idempotent)
        assert not mock_db_session.flush.called
        assert not mock_db_session.refresh.called

        # Verify WebSocket emission did NOT occur (idempotent)
        assert not mock_websocket_emitter.emit.called

    @pytest.mark.asyncio
    async def test_acknowledge_scene_change_not_found(
        self,
        scene_change_service: SceneChangeService,
        mock_db_session: AsyncMock,
        mock_websocket_emitter: AsyncMock,
    ) -> None:
        """Test acknowledging a non-existent scene change returns None."""
        # Mock get_scene_change to return None
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db_session.execute.return_value = mock_result

        result = await scene_change_service.acknowledge_scene_change(scene_change_id=999)

        assert result is None

        # Verify no database updates or WebSocket emissions
        assert not mock_db_session.flush.called
        assert not mock_websocket_emitter.emit.called

    @pytest.mark.asyncio
    async def test_acknowledge_scene_change_without_emitter(
        self,
        scene_change_service_no_emitter: SceneChangeService,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test acknowledgment works when WebSocket emitter is not available."""
        mock_scene_change = MagicMock(spec=SceneChange)
        mock_scene_change.id = 789
        mock_scene_change.camera_id = "side_gate"
        mock_scene_change.acknowledged = False
        mock_scene_change.acknowledged_at = None

        # Mock get_scene_change to return our mock
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_scene_change)
        mock_db_session.execute.return_value = mock_result

        result = await scene_change_service_no_emitter.acknowledge_scene_change(scene_change_id=789)

        # Verify the scene change was updated
        assert result is not None
        assert mock_scene_change.acknowledged is True

        # Verify database operations occurred
        assert mock_db_session.flush.called
        assert mock_db_session.refresh.called

    @pytest.mark.asyncio
    async def test_acknowledge_scene_change_database_error(
        self,
        scene_change_service: SceneChangeService,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test acknowledge_scene_change handles database errors during update."""
        mock_scene_change = MagicMock(spec=SceneChange)
        mock_scene_change.acknowledged = False

        # Mock successful get but failed flush
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_scene_change)
        mock_db_session.execute.return_value = mock_result
        mock_db_session.flush.side_effect = SQLAlchemyError("Database error")

        with pytest.raises(SQLAlchemyError):
            await scene_change_service.acknowledge_scene_change(scene_change_id=123)


# =============================================================================
# Get Unacknowledged Scene Changes Tests
# =============================================================================


class TestGetUnacknowledgedForCamera:
    """Tests for get_unacknowledged_for_camera async method."""

    @pytest.mark.asyncio
    async def test_get_unacknowledged_for_camera_success(
        self,
        scene_change_service: SceneChangeService,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test retrieving unacknowledged scene changes for a camera."""
        mock_changes = [
            MagicMock(spec=SceneChange, id=1, camera_id="front_door", acknowledged=False),
            MagicMock(spec=SceneChange, id=2, camera_id="front_door", acknowledged=False),
        ]

        # Mock the execute result
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=mock_changes)
        mock_result = AsyncMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        mock_db_session.execute.return_value = mock_result

        result = await scene_change_service.get_unacknowledged_for_camera(
            camera_id="front_door",
            limit=100,
        )

        assert len(result) == 2
        assert all(change.acknowledged is False for change in result)
        assert mock_db_session.execute.called

    @pytest.mark.asyncio
    async def test_get_unacknowledged_for_camera_empty_result(
        self,
        scene_change_service: SceneChangeService,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test retrieving unacknowledged scene changes when none exist."""
        # Mock empty result
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[])
        mock_result = AsyncMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        mock_db_session.execute.return_value = mock_result

        result = await scene_change_service.get_unacknowledged_for_camera(
            camera_id="nonexistent_camera"
        )

        assert len(result) == 0
        assert mock_db_session.execute.called
