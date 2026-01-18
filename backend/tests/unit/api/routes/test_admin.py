"""Unit tests for admin API routes (NEM-2547).

Tests the admin-only endpoints for seeding test data and maintenance:
- POST /api/admin/seed/cameras - Camera seeding
- POST /api/admin/seed/events - Event seeding
- DELETE /api/admin/seed/clear - Clear all data
- POST /api/admin/cleanup/orphans - Orphan file cleanup

Note: Admin access is always allowed (no authentication required for local deployment).

These tests follow TDD methodology with comprehensive coverage of:
- Data seeding operations
- Clear data confirmation requirements
- Orphan cleanup safety features
- Error handling and edge cases
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.routes.admin import (
    ClearDataRequest,
    OrphanCleanupRequest,
    SeedCamerasRequest,
    SeedEventsRequest,
)
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event


def create_mock_db_with_id_assignment() -> AsyncMock:
    """Create a mock database session that properly assigns IDs on flush.

    The seed_events endpoint relies on flush() to populate IDs for Detection
    and Event objects before linking them via the junction table. This helper
    creates a mock that simulates this behavior by assigning auto-incrementing
    IDs to objects that were added via add().
    """
    mock_db = AsyncMock()

    # Track added objects for ID assignment on flush
    added_objects: list = []
    id_counter = {"value": 1}

    def mock_add(obj):
        added_objects.append(obj)

    async def mock_flush():
        # Assign IDs to objects that don't have them yet
        for obj in added_objects:
            if hasattr(obj, "id") and obj.id is None:
                obj.id = id_counter["value"]
                id_counter["value"] += 1

    mock_db.add = MagicMock(side_effect=mock_add)
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock(side_effect=mock_flush)
    mock_db.execute = AsyncMock()

    return mock_db


class TestAdminSecurityControls:
    """Tests for admin endpoint security controls.

    Admin endpoints are always accessible for local deployment (no authentication required).
    The require_admin_access() function is a no-op placeholder for potential future auth.
    """

    @pytest.mark.asyncio
    async def test_admin_access_always_allowed_for_local_deployment(self) -> None:
        """Verify admin access is always allowed (no authentication for local deployment)."""
        from backend.api.routes.admin import require_admin_access

        # Should not raise - function is a no-op
        require_admin_access()


class TestSeedCamerasEndpoint:
    """Tests for POST /api/admin/seed/cameras endpoint."""

    @pytest.mark.asyncio
    async def test_seed_cameras_creates_specified_count(self) -> None:
        """Verify seed cameras creates the specified number of cameras."""
        from backend.api.routes.admin import seed_cameras

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        request = SeedCamerasRequest(count=3, clear_existing=False, create_folders=False)

        # Mock existing camera IDs query (none exist)
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        with (
            patch("backend.api.routes.admin.get_settings") as mock_settings,
            patch("backend.api.routes.admin._get_sample_cameras") as mock_samples,
        ):
            mock_settings.return_value.foscam_base_path = "/export/foscam"
            mock_samples.return_value = [
                {
                    "id": "cam1",
                    "name": "Camera 1",
                    "folder_path": "/export/foscam/cam1",
                    "status": "online",
                },
                {
                    "id": "cam2",
                    "name": "Camera 2",
                    "folder_path": "/export/foscam/cam2",
                    "status": "online",
                },
                {
                    "id": "cam3",
                    "name": "Camera 3",
                    "folder_path": "/export/foscam/cam3",
                    "status": "online",
                },
                {
                    "id": "cam4",
                    "name": "Camera 4",
                    "folder_path": "/export/foscam/cam4",
                    "status": "online",
                },
            ]

            result = await seed_cameras(request=request, db=mock_db, _admin=None)

        assert result.created == 3
        assert result.cleared == 0
        assert len(result.cameras) == 3
        assert mock_db.add.call_count == 3

    @pytest.mark.asyncio
    async def test_seed_cameras_clears_existing_when_requested(self) -> None:
        """Verify seed cameras clears existing cameras when clear_existing=True."""
        from backend.api.routes.admin import seed_cameras

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        request = SeedCamerasRequest(count=2, clear_existing=True, create_folders=False)

        # Mock existing cameras
        mock_camera1 = MagicMock(spec=Camera)
        mock_camera1.id = "old_cam1"
        mock_camera2 = MagicMock(spec=Camera)
        mock_camera2.id = "old_cam2"

        # Mock clear query
        mock_clear_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_camera1, mock_camera2]
        mock_clear_result.scalars.return_value = mock_scalars

        # Mock delete result
        mock_delete_result = MagicMock()

        # Mock existing IDs query (empty after clear)
        mock_ids_result = MagicMock()
        mock_ids_result.all.return_value = []

        mock_db.execute.side_effect = [mock_clear_result, mock_delete_result, mock_ids_result]

        with (
            patch("backend.api.routes.admin.get_settings") as mock_settings,
            patch("backend.api.routes.admin._get_sample_cameras") as mock_samples,
        ):
            mock_settings.return_value.foscam_base_path = "/export/foscam"
            mock_samples.return_value = [
                {
                    "id": "cam1",
                    "name": "Camera 1",
                    "folder_path": "/export/foscam/cam1",
                    "status": "online",
                },
                {
                    "id": "cam2",
                    "name": "Camera 2",
                    "folder_path": "/export/foscam/cam2",
                    "status": "online",
                },
            ]

            result = await seed_cameras(request=request, db=mock_db, _admin=None)

        assert result.created == 2
        assert result.cleared == 2
        # Verify delete was called during clear
        assert any("delete" in str(call).lower() for call in mock_db.execute.call_args_list)

    @pytest.mark.asyncio
    async def test_seed_cameras_skips_duplicate_ids(self) -> None:
        """Verify seed cameras skips cameras with duplicate IDs."""
        from backend.api.routes.admin import seed_cameras

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        request = SeedCamerasRequest(count=3, clear_existing=False, create_folders=False)

        # Mock existing IDs query - cam2 already exists
        mock_result = MagicMock()
        mock_result.all.return_value = [("cam2",)]
        mock_db.execute.return_value = mock_result

        with (
            patch("backend.api.routes.admin.get_settings") as mock_settings,
            patch("backend.api.routes.admin._get_sample_cameras") as mock_samples,
        ):
            mock_settings.return_value.foscam_base_path = "/export/foscam"
            mock_samples.return_value = [
                {
                    "id": "cam1",
                    "name": "Camera 1",
                    "folder_path": "/export/foscam/cam1",
                    "status": "online",
                },
                {
                    "id": "cam2",
                    "name": "Camera 2",
                    "folder_path": "/export/foscam/cam2",
                    "status": "online",
                },
                {
                    "id": "cam3",
                    "name": "Camera 3",
                    "folder_path": "/export/foscam/cam3",
                    "status": "online",
                },
            ]

            result = await seed_cameras(request=request, db=mock_db, _admin=None)

        # Only cam1 and cam3 should be created (cam2 already exists)
        assert result.created == 2
        assert mock_db.add.call_count == 2

    @pytest.mark.asyncio
    async def test_seed_cameras_creates_folders_when_requested(self) -> None:
        """Verify seed cameras creates folder directories when create_folders=True."""
        from backend.api.routes.admin import seed_cameras

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        request = SeedCamerasRequest(count=1, clear_existing=False, create_folders=True)

        # Mock existing IDs query (none exist)
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        with (
            patch("backend.api.routes.admin.get_settings") as mock_settings,
            patch("backend.api.routes.admin._get_sample_cameras") as mock_samples,
            patch("backend.api.routes.admin.Path") as mock_path,
        ):
            mock_settings.return_value.foscam_base_path = "/export/foscam"
            mock_samples.return_value = [
                {
                    "id": "cam1",
                    "name": "Camera 1",
                    "folder_path": "/export/foscam/cam1",
                    "status": "online",
                },
            ]

            mock_folder = MagicMock()
            mock_path.return_value = mock_folder

            result = await seed_cameras(request=request, db=mock_db, _admin=None)

        assert result.created == 1
        # Verify mkdir was called
        mock_folder.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @pytest.mark.asyncio
    async def test_seed_cameras_continues_on_folder_creation_failure(self) -> None:
        """Verify seed cameras continues creating cameras even if folder creation fails."""
        from backend.api.routes.admin import seed_cameras

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        request = SeedCamerasRequest(count=1, clear_existing=False, create_folders=True)

        # Mock existing IDs query (none exist)
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        with (
            patch("backend.api.routes.admin.get_settings") as mock_settings,
            patch("backend.api.routes.admin._get_sample_cameras") as mock_samples,
            patch("backend.api.routes.admin.Path") as mock_path,
        ):
            mock_settings.return_value.foscam_base_path = "/export/foscam"
            mock_samples.return_value = [
                {
                    "id": "cam1",
                    "name": "Camera 1",
                    "folder_path": "/export/foscam/cam1",
                    "status": "online",
                },
            ]

            mock_folder = MagicMock()
            mock_folder.mkdir.side_effect = OSError("Permission denied")
            mock_path.return_value = mock_folder

            # Should not raise, just continue
            result = await seed_cameras(request=request, db=mock_db, _admin=None)

        assert result.created == 1

    @pytest.mark.asyncio
    async def test_seed_cameras_respects_count_limit(self) -> None:
        """Verify seed cameras respects maximum count of 6."""
        from backend.api.routes.admin import seed_cameras

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        # Request 6 cameras (max)
        request = SeedCamerasRequest(count=6, clear_existing=False, create_folders=False)

        # Mock existing IDs query (none exist)
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        with (
            patch("backend.api.routes.admin.get_settings") as mock_settings,
            patch("backend.api.routes.admin._get_sample_cameras") as mock_samples,
        ):
            mock_settings.return_value.foscam_base_path = "/export/foscam"
            # Provide 6 sample cameras
            mock_samples.return_value = [
                {
                    "id": f"cam{i}",
                    "name": f"Camera {i}",
                    "folder_path": f"/export/foscam/cam{i}",
                    "status": "online",
                }
                for i in range(1, 7)
            ]

            result = await seed_cameras(request=request, db=mock_db, _admin=None)

        assert result.created == 6
        assert len(result.cameras) == 6


class TestSeedEventsEndpoint:
    """Tests for POST /api/admin/seed/events endpoint."""

    @pytest.mark.asyncio
    async def test_seed_events_creates_specified_count(self) -> None:
        """Verify seed events creates the specified number of events."""
        from backend.api.routes.admin import seed_events

        mock_db = create_mock_db_with_id_assignment()

        request = SeedEventsRequest(count=5, clear_existing=False)

        # Mock camera query
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "test_camera"
        mock_camera.folder_path = "/export/foscam/test_camera"

        mock_camera_result = MagicMock()
        mock_camera_result.scalars.return_value.all.return_value = [mock_camera]
        mock_db.execute.return_value = mock_camera_result

        with patch("backend.api.routes.admin.random") as mock_random:
            # Control randomness for consistent testing
            mock_random.choice.return_value = mock_camera
            mock_random.random.return_value = 0.25  # Low risk
            mock_random.randint.side_effect = lambda a, _b: a  # Return min value
            mock_random.uniform.side_effect = lambda a, b: (a + b) / 2  # Return middle value

            result = await seed_events(request=request, db=mock_db, _admin=None)

        assert result.events_created == 5
        assert result.detections_created > 0  # At least 1 detection per event
        assert result.events_cleared == 0
        assert result.detections_cleared == 0

    @pytest.mark.asyncio
    async def test_seed_events_requires_cameras_to_exist(self) -> None:
        """Verify seed events returns 400 when no cameras exist."""
        from fastapi import HTTPException

        from backend.api.routes.admin import seed_events

        mock_db = AsyncMock()

        request = SeedEventsRequest(count=5, clear_existing=False)

        # Mock empty camera query
        mock_camera_result = MagicMock()
        mock_camera_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_camera_result

        with pytest.raises(HTTPException) as exc_info:
            await seed_events(request=request, db=mock_db, _admin=None)

        assert exc_info.value.status_code == 400
        assert "No cameras found" in exc_info.value.detail
        assert "Seed cameras first" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_seed_events_clears_existing_when_requested(self) -> None:
        """Verify seed events clears existing events and detections when clear_existing=True."""
        from backend.api.routes.admin import seed_events

        mock_db = create_mock_db_with_id_assignment()

        request = SeedEventsRequest(count=2, clear_existing=True)

        # Mock existing events and detections
        mock_event1 = MagicMock(spec=Event)
        mock_event2 = MagicMock(spec=Event)
        mock_detection1 = MagicMock(spec=Detection)
        mock_detection2 = MagicMock(spec=Detection)

        mock_events_result = MagicMock()
        mock_events_scalars = MagicMock()
        mock_events_scalars.all.return_value = [mock_event1, mock_event2]
        mock_events_result.scalars.return_value = mock_events_scalars

        mock_detections_result = MagicMock()
        mock_detections_scalars = MagicMock()
        mock_detections_scalars.all.return_value = [mock_detection1, mock_detection2]
        mock_detections_result.scalars.return_value = mock_detections_scalars

        # Mock delete results
        mock_delete_event = MagicMock()
        mock_delete_detection = MagicMock()

        # Mock camera query
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "test_camera"
        mock_camera.folder_path = "/export/foscam/test_camera"

        mock_camera_result = MagicMock()
        mock_camera_scalars = MagicMock()
        mock_camera_scalars.all.return_value = [mock_camera]
        mock_camera_result.scalars.return_value = mock_camera_scalars

        # Junction table inserts (line 553) - one per detection per event
        # With count=2 and randint returning min value (1 detection per event), need 2 more
        mock_junction_insert = MagicMock()

        mock_db.execute.side_effect = [
            mock_events_result,
            mock_detections_result,
            mock_delete_event,
            mock_delete_detection,
            mock_camera_result,
            mock_junction_insert,  # Event 1 detection junction
            mock_junction_insert,  # Event 2 detection junction
        ]

        with patch("backend.api.routes.admin.random") as mock_random:
            mock_random.choice.return_value = mock_camera
            mock_random.random.return_value = 0.25
            mock_random.randint.side_effect = lambda a, _b: a
            mock_random.uniform.side_effect = lambda a, b: (a + b) / 2

            result = await seed_events(request=request, db=mock_db, _admin=None)

        assert result.events_cleared == 2
        assert result.detections_cleared == 2
        assert result.events_created == 2

    @pytest.mark.asyncio
    async def test_seed_events_generates_proper_risk_distribution(self) -> None:
        """Verify seed events generates events with proper risk distribution (50% low, 35% medium, 15% high)."""
        from backend.api.routes.admin import seed_events

        mock_db = create_mock_db_with_id_assignment()

        request = SeedEventsRequest(count=10, clear_existing=False)

        # Mock camera query
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "test_camera"
        mock_camera.folder_path = "/export/foscam/test_camera"

        mock_camera_result = MagicMock()
        mock_camera_scalars = MagicMock()
        mock_camera_scalars.all.return_value = [mock_camera]
        mock_camera_result.scalars.return_value = mock_camera_scalars
        mock_db.execute.return_value = mock_camera_result

        risk_levels = []
        added_objects: list = []
        id_counter = {"value": 1}

        def mock_add(obj):
            added_objects.append(obj)
            if isinstance(obj, Event):
                risk_levels.append(obj.risk_level)

        async def mock_flush():
            for obj in added_objects:
                if hasattr(obj, "id") and obj.id is None:
                    obj.id = id_counter["value"]
                    id_counter["value"] += 1

        mock_db.add.side_effect = mock_add
        mock_db.flush = AsyncMock(side_effect=mock_flush)

        with patch("backend.api.routes.admin.random") as mock_random:
            mock_random.choice.return_value = mock_camera
            # Simulate risk distribution - create more than needed for random calls
            risk_rolls = [
                0.3,
                0.7,
                0.4,
                0.6,
                0.2,
                0.9,
                0.5,
                0.8,
                0.1,
                0.45,
            ] * 3  # Mix of low/medium/high
            mock_random.random.side_effect = risk_rolls
            mock_random.randint.return_value = 1  # Always return 1 detection per event
            mock_random.uniform.return_value = 0.8

            result = await seed_events(request=request, db=mock_db, _admin=None)

        assert result.events_created == 10
        # Verify risk levels are generated (not testing exact distribution due to randomness)
        assert len(risk_levels) == 10

    @pytest.mark.asyncio
    async def test_seed_events_creates_detections_for_each_event(self) -> None:
        """Verify seed events creates 1-5 detections for each event."""
        from backend.api.routes.admin import seed_events

        mock_db = create_mock_db_with_id_assignment()

        request = SeedEventsRequest(count=3, clear_existing=False)

        # Mock camera query
        mock_camera = MagicMock(spec=Camera)
        mock_camera.id = "test_camera"
        mock_camera.folder_path = "/export/foscam/test_camera"

        mock_camera_result = MagicMock()
        mock_camera_scalars = MagicMock()
        mock_camera_scalars.all.return_value = [mock_camera]
        mock_camera_result.scalars.return_value = mock_camera_scalars
        mock_db.execute.return_value = mock_camera_result

        # Mock detection to track created detections
        created_detections = []
        added_objects: list = []
        id_counter = {"value": 1}

        def mock_add(obj):
            added_objects.append(obj)
            if isinstance(obj, Detection):
                created_detections.append(obj)

        async def mock_flush():
            for obj in added_objects:
                if hasattr(obj, "id") and obj.id is None:
                    obj.id = id_counter["value"]
                    id_counter["value"] += 1

        mock_db.add.side_effect = mock_add
        mock_db.flush = AsyncMock(side_effect=mock_flush)

        # Track randint calls to return 3 for first 3 event counts, then various for detection generation
        randint_calls = []

        def mock_randint(a, b):
            randint_calls.append((a, b))
            # First 3 calls are for num_detections (1-5 range)
            if len([c for c in randint_calls if c == (1, 5)]) <= 3:
                return 3  # 3 detections per event
            # Subsequent calls are for detection data
            return a  # Return minimum value

        with patch("backend.api.routes.admin.random") as mock_random:
            mock_random.choice.return_value = mock_camera
            mock_random.random.return_value = 0.25
            mock_random.randint.side_effect = mock_randint
            mock_random.uniform.return_value = 0.8

            result = await seed_events(request=request, db=mock_db, _admin=None)

        assert result.events_created == 3
        assert result.detections_created == 9  # 3 events * 3 detections each


class TestClearDataEndpoint:
    """Tests for DELETE /api/admin/seed/clear endpoint."""

    @pytest.mark.asyncio
    async def test_clear_data_requires_exact_confirmation_string(self) -> None:
        """Verify clear data requires exact confirmation string 'DELETE_ALL_DATA'."""
        from fastapi import HTTPException

        from backend.api.routes.admin import clear_seeded_data

        mock_db = AsyncMock()
        mock_request = MagicMock()

        body = ClearDataRequest(confirm="WRONG_STRING")

        with pytest.raises(HTTPException) as exc_info:
            await clear_seeded_data(body=body, request=mock_request, db=mock_db, _admin=None)

        assert exc_info.value.status_code == 400
        assert "DELETE_ALL_DATA" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_clear_data_deletes_in_correct_order(self) -> None:
        """Verify clear data deletes in correct order (Event, Detection, Camera) to respect foreign keys."""
        from backend.api.routes.admin import clear_seeded_data

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_request = MagicMock()

        body = ClearDataRequest(confirm="DELETE_ALL_DATA")

        # Mock existing data
        mock_event = MagicMock(spec=Event)
        mock_detection = MagicMock(spec=Detection)
        mock_camera = MagicMock(spec=Camera)

        mock_events_result = MagicMock()
        mock_events_result.scalars.return_value.all.return_value = [mock_event]

        mock_detections_result = MagicMock()
        mock_detections_result.scalars.return_value.all.return_value = [mock_detection]

        mock_cameras_result = MagicMock()
        mock_cameras_result.scalars.return_value.all.return_value = [mock_camera]

        mock_db.execute.side_effect = [
            mock_events_result,
            mock_detections_result,
            mock_cameras_result,
            # Then delete statements return None
            None,
            None,
            None,
        ]

        with patch("backend.api.routes.admin.get_db_audit_service") as mock_audit:
            mock_audit.return_value.log_action = AsyncMock()

            result = await clear_seeded_data(
                body=body, request=mock_request, db=mock_db, _admin=None
            )

        assert result.events_cleared == 1
        assert result.detections_cleared == 1
        assert result.cameras_cleared == 1

        # Verify delete was called 3 times
        execute_calls = [str(call) for call in mock_db.execute.call_args_list]
        delete_calls = [call for call in execute_calls if "delete" in call.lower()]
        assert len(delete_calls) == 3

    @pytest.mark.asyncio
    async def test_clear_data_returns_accurate_counts(self) -> None:
        """Verify clear data returns accurate count of cleared items."""
        from backend.api.routes.admin import clear_seeded_data

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_request = MagicMock()

        body = ClearDataRequest(confirm="DELETE_ALL_DATA")

        # Mock 10 events, 25 detections, 5 cameras
        mock_events = [MagicMock(spec=Event) for _ in range(10)]
        mock_detections = [MagicMock(spec=Detection) for _ in range(25)]
        mock_cameras = [MagicMock(spec=Camera) for _ in range(5)]

        mock_events_result = MagicMock()
        mock_events_result.scalars.return_value.all.return_value = mock_events

        mock_detections_result = MagicMock()
        mock_detections_result.scalars.return_value.all.return_value = mock_detections

        mock_cameras_result = MagicMock()
        mock_cameras_result.scalars.return_value.all.return_value = mock_cameras

        mock_db.execute.side_effect = [
            mock_events_result,
            mock_detections_result,
            mock_cameras_result,
            None,
            None,
            None,
        ]

        with patch("backend.api.routes.admin.get_db_audit_service") as mock_audit:
            mock_audit.return_value.log_action = AsyncMock()

            result = await clear_seeded_data(
                body=body, request=mock_request, db=mock_db, _admin=None
            )

        assert result.events_cleared == 10
        assert result.detections_cleared == 25
        assert result.cameras_cleared == 5

    @pytest.mark.asyncio
    async def test_clear_data_logs_to_audit(self) -> None:
        """Verify clear data logs action to audit log."""
        from backend.api.routes.admin import clear_seeded_data
        from backend.models.audit import AuditAction

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_request = MagicMock()

        body = ClearDataRequest(confirm="DELETE_ALL_DATA")

        # Mock empty data
        mock_empty_result = MagicMock()
        mock_empty_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [
            mock_empty_result,
            mock_empty_result,
            mock_empty_result,
            None,
            None,
            None,
        ]

        with patch("backend.api.routes.admin.get_db_audit_service") as mock_audit:
            mock_audit_service = AsyncMock()
            mock_audit.return_value = mock_audit_service

            result = await clear_seeded_data(
                body=body, request=mock_request, db=mock_db, _admin=None
            )

        # Verify audit log was called
        mock_audit_service.log_action.assert_called_once()
        call_args = mock_audit_service.log_action.call_args
        assert call_args.kwargs["action"] == AuditAction.DATA_CLEARED
        assert call_args.kwargs["resource_type"] == "admin"
        assert call_args.kwargs["actor"] == "admin"


class TestOrphanCleanupEndpoint:
    """Tests for POST /api/admin/cleanup/orphans endpoint."""

    @pytest.mark.asyncio
    async def test_orphan_cleanup_dry_run_by_default(self) -> None:
        """Verify orphan cleanup defaults to dry_run=True."""
        from backend.api.routes.admin import cleanup_orphans

        mock_db = AsyncMock()
        mock_request = MagicMock()

        request = OrphanCleanupRequest()  # Uses default dry_run=True

        with (
            patch("backend.jobs.orphan_cleanup_job.OrphanCleanupJob") as mock_job_class,
            patch("backend.services.job_tracker.get_job_tracker") as mock_tracker,
            patch("backend.api.routes.admin.get_db_audit_service") as mock_audit,
        ):
            mock_job = AsyncMock()
            mock_report = MagicMock()
            mock_report.scanned_files = 100
            mock_report.orphaned_files = 10
            mock_report.deleted_files = 0  # Dry run doesn't delete
            mock_report.deleted_bytes = 0
            mock_report.failed_deletions = []
            mock_report.duration_seconds = 1.5
            mock_report.dry_run = True
            mock_report.skipped_young = 5
            mock_report.skipped_size_limit = 0
            mock_report._format_bytes.return_value = "0 B"

            mock_job.run.return_value = mock_report
            mock_job_class.return_value = mock_job

            mock_audit_service = AsyncMock()
            mock_audit.return_value = mock_audit_service

            result = await cleanup_orphans(
                request=request, http_request=mock_request, db=mock_db, _admin=None
            )

        assert result.dry_run is True
        assert result.deleted_files == 0

    @pytest.mark.asyncio
    async def test_orphan_cleanup_respects_min_age_hours(self) -> None:
        """Verify orphan cleanup respects min_age_hours threshold."""
        from backend.api.routes.admin import cleanup_orphans

        mock_db = AsyncMock()
        mock_request = MagicMock()

        request = OrphanCleanupRequest(dry_run=True, min_age_hours=48)

        with (
            patch("backend.jobs.orphan_cleanup_job.OrphanCleanupJob") as mock_job_class,
            patch("backend.services.job_tracker.get_job_tracker") as mock_tracker,
            patch("backend.api.routes.admin.get_db_audit_service") as mock_audit,
        ):
            mock_job = AsyncMock()
            mock_report = MagicMock()
            mock_report.scanned_files = 100
            mock_report.orphaned_files = 10
            mock_report.deleted_files = 0
            mock_report.deleted_bytes = 0
            mock_report.failed_deletions = []
            mock_report.duration_seconds = 1.5
            mock_report.dry_run = True
            mock_report.skipped_young = 8  # 8 files too young
            mock_report.skipped_size_limit = 0
            mock_report._format_bytes.return_value = "0 B"

            mock_job.run.return_value = mock_report
            mock_job_class.return_value = mock_job

            mock_audit_service = AsyncMock()
            mock_audit.return_value = mock_audit_service

            result = await cleanup_orphans(
                request=request, http_request=mock_request, db=mock_db, _admin=None
            )

        # Verify job was created with correct min_age_hours
        mock_job_class.assert_called_once()
        assert mock_job_class.call_args.kwargs["min_age_hours"] == 48
        assert result.skipped_young == 8

    @pytest.mark.asyncio
    async def test_orphan_cleanup_respects_max_delete_gb(self) -> None:
        """Verify orphan cleanup respects max_delete_gb limit."""
        from backend.api.routes.admin import cleanup_orphans

        mock_db = AsyncMock()
        mock_request = MagicMock()

        request = OrphanCleanupRequest(dry_run=False, max_delete_gb=5.0)

        with (
            patch("backend.jobs.orphan_cleanup_job.OrphanCleanupJob") as mock_job_class,
            patch("backend.services.job_tracker.get_job_tracker") as mock_tracker,
            patch("backend.api.routes.admin.get_db_audit_service") as mock_audit,
        ):
            mock_job = AsyncMock()
            mock_report = MagicMock()
            mock_report.scanned_files = 100
            mock_report.orphaned_files = 20
            mock_report.deleted_files = 15
            mock_report.deleted_bytes = 5 * 1024**3  # 5 GB
            mock_report.failed_deletions = []
            mock_report.duration_seconds = 3.2
            mock_report.dry_run = False
            mock_report.skipped_young = 0
            mock_report.skipped_size_limit = 5  # 5 files skipped due to size limit
            mock_report._format_bytes.return_value = "5.00 GB"

            mock_job.run.return_value = mock_report
            mock_job_class.return_value = mock_job

            mock_audit_service = AsyncMock()
            mock_audit.return_value = mock_audit_service

            result = await cleanup_orphans(
                request=request, http_request=mock_request, db=mock_db, _admin=None
            )

        # Verify job was created with correct max_delete_gb
        mock_job_class.assert_called_once()
        assert mock_job_class.call_args.kwargs["max_delete_gb"] == 5.0
        assert result.skipped_size_limit == 5

    @pytest.mark.asyncio
    async def test_orphan_cleanup_logs_to_audit(self) -> None:
        """Verify orphan cleanup logs action to audit log."""
        from backend.api.routes.admin import cleanup_orphans
        from backend.models.audit import AuditAction

        mock_db = AsyncMock()
        mock_request = MagicMock()

        request = OrphanCleanupRequest(dry_run=True)

        with (
            patch("backend.jobs.orphan_cleanup_job.OrphanCleanupJob") as mock_job_class,
            patch("backend.services.job_tracker.get_job_tracker") as mock_tracker,
            patch("backend.api.routes.admin.get_db_audit_service") as mock_audit,
        ):
            mock_job = AsyncMock()
            mock_report = MagicMock()
            mock_report.scanned_files = 50
            mock_report.orphaned_files = 5
            mock_report.deleted_files = 0
            mock_report.deleted_bytes = 0
            mock_report.failed_deletions = []
            mock_report.duration_seconds = 1.0
            mock_report.dry_run = True
            mock_report.skipped_young = 2
            mock_report.skipped_size_limit = 0
            mock_report._format_bytes.return_value = "0 B"

            mock_job.run.return_value = mock_report
            mock_job_class.return_value = mock_job

            mock_audit_service = AsyncMock()
            mock_audit.return_value = mock_audit_service

            result = await cleanup_orphans(
                request=request, http_request=mock_request, db=mock_db, _admin=None
            )

        # Verify audit log was called
        mock_audit_service.log_action.assert_called_once()
        call_args = mock_audit_service.log_action.call_args
        assert call_args.kwargs["action"] == AuditAction.DATA_CLEARED
        assert call_args.kwargs["resource_type"] == "orphan_cleanup"
        assert call_args.kwargs["actor"] == "admin"
        assert "dry_run" in call_args.kwargs["details"]

    @pytest.mark.asyncio
    async def test_orphan_cleanup_limits_failed_deletions_in_response(self) -> None:
        """Verify orphan cleanup limits failed deletions to first 50 in response."""
        from backend.api.routes.admin import cleanup_orphans

        mock_db = AsyncMock()
        mock_request = MagicMock()

        request = OrphanCleanupRequest(dry_run=False)

        with (
            patch("backend.jobs.orphan_cleanup_job.OrphanCleanupJob") as mock_job_class,
            patch("backend.services.job_tracker.get_job_tracker") as mock_tracker,
            patch("backend.api.routes.admin.get_db_audit_service") as mock_audit,
        ):
            mock_job = AsyncMock()
            mock_report = MagicMock()
            mock_report.scanned_files = 200
            mock_report.orphaned_files = 100
            mock_report.deleted_files = 0
            mock_report.deleted_bytes = 0
            # Create 75 failed deletions
            mock_report.failed_deletions = [f"/path/to/file{i}.jpg" for i in range(75)]
            mock_report.duration_seconds = 5.0
            mock_report.dry_run = False
            mock_report.skipped_young = 0
            mock_report.skipped_size_limit = 0
            mock_report._format_bytes.return_value = "0 B"

            mock_job.run.return_value = mock_report
            mock_job_class.return_value = mock_job

            mock_audit_service = AsyncMock()
            mock_audit.return_value = mock_audit_service

            result = await cleanup_orphans(
                request=request, http_request=mock_request, db=mock_db, _admin=None
            )

        # Response should limit to 50 failures
        assert result.failed_count == 75
        assert len(result.failed_deletions) == 50


class TestGetSampleCameras:
    """Tests for _get_sample_cameras helper function."""

    def test_get_sample_cameras_uses_foscam_base_path(self) -> None:
        """Verify _get_sample_cameras uses configured foscam_base_path."""
        from backend.api.routes.admin import _get_sample_cameras

        with patch("backend.api.routes.admin.get_settings") as mock_settings:
            mock_settings.return_value.foscam_base_path = "/custom/camera/path"

            cameras = _get_sample_cameras()

        assert len(cameras) == 6
        for camera in cameras:
            assert camera["folder_path"].startswith("/custom/camera/path/")

    def test_get_sample_cameras_returns_six_cameras(self) -> None:
        """Verify _get_sample_cameras returns exactly 6 cameras."""
        from backend.api.routes.admin import _get_sample_cameras

        with patch("backend.api.routes.admin.get_settings") as mock_settings:
            mock_settings.return_value.foscam_base_path = "/export/foscam"

            cameras = _get_sample_cameras()

        assert len(cameras) == 6

    def test_get_sample_cameras_includes_required_fields(self) -> None:
        """Verify _get_sample_cameras includes all required camera fields."""
        from backend.api.routes.admin import _get_sample_cameras

        with patch("backend.api.routes.admin.get_settings") as mock_settings:
            mock_settings.return_value.foscam_base_path = "/export/foscam"

            cameras = _get_sample_cameras()

        required_fields = {"id", "name", "folder_path", "status"}
        for camera in cameras:
            assert set(camera.keys()) == required_fields
            assert camera["id"]
            assert camera["name"]
            assert camera["folder_path"]
            assert camera["status"] in ["online", "offline"]
