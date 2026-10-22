"""Unit tests for RestoreService (NEM-3566).

Tests verify backup restoration functionality including:
1. Manifest validation and version compatibility checking
2. File checksum verification for integrity
3. Transactional restore with rollback on failure
4. Progress callback reporting
5. Table restoration in dependency order
6. Error handling and edge cases

Run with: uv run pytest backend/tests/unit/services/test_restore_service.py -v
"""

from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.restore_service import (
    RESTORE_TABLE_ORDER,
    SUPPORTED_BACKUP_VERSION,
    BackupCorruptedError,
    BackupValidationError,
    RestoreError,
    RestoreResult,
    RestoreService,
    get_restore_service,
    reset_restore_service,
)


@pytest.fixture(autouse=True)
def reset_service():
    """Reset service singleton before each test."""
    reset_restore_service()
    yield
    reset_restore_service()


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def sample_manifest():
    """Create a sample backup manifest."""
    return {
        "backup_id": "backup-123",
        "version": "1.0",
        "created_at": "2024-01-15T10:30:00Z",
        "contents": {
            "cameras": {
                "count": 2,
                "checksum": "abc123",
            },
            "events": {
                "count": 5,
                "checksum": "def456",
            },
        },
    }


@pytest.fixture
def sample_camera_data():
    """Create sample camera backup data."""
    return [
        {
            "id": "camera-1",
            "name": "Front Door",
            "folder_path": "/cameras/front_door",
            "status": "online",
            "created_at": "2024-01-15T10:00:00Z",
        },
        {
            "id": "camera-2",
            "name": "Back Yard",
            "folder_path": "/cameras/back_yard",
            "status": "offline",
            "created_at": "2024-01-15T10:05:00Z",
        },
    ]


@pytest.fixture
def sample_event_data():
    """Create sample event backup data."""
    return [
        {
            "id": 1,
            "camera_id": "camera-1",
            "started_at": "2024-01-15T10:30:00Z",
            "risk_score": 75,
        },
    ]


class TestRestoreServiceSingleton:
    """Test singleton pattern for RestoreService."""

    def test_get_restore_service_returns_singleton(self):
        """Test get_restore_service returns singleton instance."""
        service1 = get_restore_service()
        service2 = get_restore_service()

        assert service1 is service2

    def test_reset_restore_service_clears_singleton(self):
        """Test reset_restore_service clears singleton."""
        service1 = get_restore_service()
        reset_restore_service()
        service2 = get_restore_service()

        assert service1 is not service2


class TestValidateManifest:
    """Test _validate_manifest method."""

    def test_validate_manifest_success(self, sample_manifest):
        """Test valid manifest passes validation."""
        service = RestoreService()
        # Should not raise
        service._validate_manifest(sample_manifest)

    @pytest.mark.parametrize("field", ["backup_id", "version", "created_at"])
    def test_validate_manifest_missing_required_field(self, sample_manifest, field):
        """Test manifest without a required field raises BackupValidationError."""
        del sample_manifest[field]
        service = RestoreService()

        with pytest.raises(
            BackupValidationError, match=f"Missing required manifest field: {field}"
        ):
            service._validate_manifest(sample_manifest)

    def test_validate_manifest_unsupported_version(self, sample_manifest):
        """Test manifest with unsupported version raises error."""
        sample_manifest["version"] = "2.0"
        service = RestoreService()

        with pytest.raises(BackupValidationError, match=r"Unsupported backup version: 2\.0"):
            service._validate_manifest(sample_manifest)

    def test_validate_manifest_invalid_contents_type(self, sample_manifest):
        """Test manifest with invalid contents type raises error."""
        sample_manifest["contents"] = "not a dict"
        service = RestoreService()

        with pytest.raises(BackupValidationError, match="Invalid manifest contents structure"):
            service._validate_manifest(sample_manifest)

    def test_validate_manifest_invalid_content_info_type(self, sample_manifest):
        """Test manifest with invalid content info type raises error."""
        sample_manifest["contents"]["cameras"] = "not a dict"
        service = RestoreService()

        with pytest.raises(BackupValidationError, match="Invalid content info for table cameras"):
            service._validate_manifest(sample_manifest)

    @pytest.mark.parametrize("field", ["count", "checksum"])
    def test_validate_manifest_missing_content_field(self, sample_manifest, field):
        """Test manifest with missing count or checksum raises BackupValidationError."""
        del sample_manifest["contents"]["cameras"][field]
        service = RestoreService()

        with pytest.raises(
            BackupValidationError, match="Missing count or checksum for table cameras"
        ):
            service._validate_manifest(sample_manifest)

    def test_validate_manifest_empty_contents(self, sample_manifest):
        """Test manifest with empty contents is valid."""
        sample_manifest["contents"] = {}
        service = RestoreService()
        # Should not raise
        service._validate_manifest(sample_manifest)


class TestCalculateChecksum:
    """Test _calculate_checksum method."""

    def test_calculate_checksum_returns_hex_string(self, tmp_path):
        """Test checksum is returned as hex string."""
        file_path = tmp_path / "test.json"
        file_path.write_text('{"test": "data"}')

        service = RestoreService()
        checksum = service._calculate_checksum(file_path)

        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA256 hex string length
        assert all(c in "0123456789abcdef" for c in checksum)

    def test_calculate_checksum_same_content_same_checksum(self, tmp_path):
        """Test same content produces same checksum."""
        file1 = tmp_path / "test1.json"
        file2 = tmp_path / "test2.json"
        content = '{"test": "data"}'
        file1.write_text(content)
        file2.write_text(content)

        service = RestoreService()
        checksum1 = service._calculate_checksum(file1)
        checksum2 = service._calculate_checksum(file2)

        assert checksum1 == checksum2

    def test_calculate_checksum_different_content_different_checksum(self, tmp_path):
        """Test different content produces different checksum."""
        file1 = tmp_path / "test1.json"
        file2 = tmp_path / "test2.json"
        file1.write_text('{"test": "data1"}')
        file2.write_text('{"test": "data2"}')

        service = RestoreService()
        checksum1 = service._calculate_checksum(file1)
        checksum2 = service._calculate_checksum(file2)

        assert checksum1 != checksum2

    def test_calculate_checksum_missing_file_raises_error(self, tmp_path):
        """Test missing file raises FileNotFoundError."""
        file_path = tmp_path / "missing.json"
        service = RestoreService()

        with pytest.raises(FileNotFoundError):
            service._calculate_checksum(file_path)


class TestVerifyChecksums:
    """Test _verify_checksums method."""

    def test_verify_checksums_success(self, tmp_path, sample_manifest):
        """Test valid checksums pass verification."""
        # Create backup files
        cameras_file = tmp_path / "cameras.json"
        events_file = tmp_path / "events.json"
        cameras_file.write_text('{"test": "cameras"}')
        events_file.write_text('{"test": "events"}')

        # Calculate real checksums
        service = RestoreService()
        sample_manifest["contents"]["cameras"]["checksum"] = service._calculate_checksum(
            cameras_file
        )
        sample_manifest["contents"]["events"]["checksum"] = service._calculate_checksum(events_file)

        # Should not raise
        service._verify_checksums(tmp_path, sample_manifest)

    def test_verify_checksums_mismatch_raises_error(self, tmp_path, sample_manifest):
        """Test checksum mismatch raises BackupCorruptedError."""
        cameras_file = tmp_path / "cameras.json"
        cameras_file.write_text('{"test": "cameras"}')

        sample_manifest["contents"]["cameras"]["checksum"] = "wrong_checksum"

        service = RestoreService()

        with pytest.raises(BackupCorruptedError, match="Checksum mismatch for cameras"):
            service._verify_checksums(tmp_path, sample_manifest)

    def test_verify_checksums_missing_file_raises_error(self, tmp_path, sample_manifest):
        """Test missing file for a manifest-listed table raises BackupValidationError."""
        service = RestoreService()

        with pytest.raises(
            BackupValidationError,
            match="Backup file for table 'cameras' listed in manifest is missing",
        ):
            service._verify_checksums(tmp_path, sample_manifest)

    def test_verify_checksums_empty_contents(self, tmp_path, sample_manifest):
        """Test empty contents doesn't raise error."""
        sample_manifest["contents"] = {}
        service = RestoreService()

        # Should not raise
        service._verify_checksums(tmp_path, sample_manifest)


class TestIsDatetimeField:
    """Test _is_datetime_field method."""

    @pytest.mark.parametrize(
        ("field_name", "value"),
        [
            ("created_at", "2024-01-15T10:30:00Z"),
            ("updated_at", "2024-01-15T10:30:00Z"),
            ("started_at", "2024-01-15T10:30:00Z"),
            ("start_date", "2024-01-15"),
            ("event_time", "2024-01-15T10:30:00"),
            ("event_timestamp", "2024-01-15T10:30:00"),
        ],
    )
    def test_is_datetime_field_recognized_suffixes(self, field_name, value):
        """Test fields ending with _at/_date/_time/_timestamp are recognized as datetime."""
        service = RestoreService()
        assert service._is_datetime_field(field_name, value)

    def test_is_datetime_field_non_datetime_field(self):
        """Test non-datetime field is not recognized."""
        service = RestoreService()
        assert not service._is_datetime_field("name", "test")
        assert not service._is_datetime_field("status", "online")
        assert not service._is_datetime_field("id", "123")

    def test_is_datetime_field_datetime_suffix_non_iso_value(self):
        """Test datetime field with non-ISO value returns True if it has dash."""
        service = RestoreService()
        # The method checks for "-" in first 10 chars, so "not-a-date" returns True
        assert service._is_datetime_field("created_at", "not-a-date")
        # But "123" without dash returns False
        assert not service._is_datetime_field("created_at", "123")

    def test_is_datetime_field_short_value(self):
        """Test datetime field with short value returns False."""
        service = RestoreService()
        assert not service._is_datetime_field("created_at", "2024")


class TestProcessRecordData:
    """Test _process_record_data method."""

    def test_process_record_data_converts_datetime_strings(self):
        """Test datetime strings are converted to datetime objects."""
        service = RestoreService()
        data = {
            "id": "camera-1",
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T11:00:00+00:00",
        }

        processed = service._process_record_data(data)

        assert isinstance(processed["created_at"], datetime)
        assert isinstance(processed["updated_at"], datetime)
        assert processed["id"] == "camera-1"

    def test_process_record_data_preserves_none_values(self):
        """Test None values are preserved."""
        service = RestoreService()
        data = {
            "id": "camera-1",
            "ended_at": None,
            "description": None,
        }

        processed = service._process_record_data(data)

        assert processed["ended_at"] is None
        assert processed["description"] is None

    def test_process_record_data_preserves_non_datetime_strings(self):
        """Test non-datetime strings are preserved."""
        service = RestoreService()
        data = {
            "id": "camera-1",
            "name": "Front Door",
            "status": "online",
        }

        processed = service._process_record_data(data)

        assert processed["name"] == "Front Door"
        assert processed["status"] == "online"

    def test_process_record_data_handles_invalid_datetime(self):
        """Test invalid datetime strings are preserved as strings."""
        service = RestoreService()
        data = {
            "id": "camera-1",
            "created_at": "not-a-valid-date",
        }

        processed = service._process_record_data(data)

        assert processed["created_at"] == "not-a-valid-date"

    def test_process_record_data_preserves_other_types(self):
        """Test other types (int, bool, list, dict) are preserved."""
        service = RestoreService()
        data = {
            "id": 1,
            "active": True,
            "count": 42,
            "tags": ["tag1", "tag2"],
            "metadata": {"key": "value"},
        }

        processed = service._process_record_data(data)

        assert processed["id"] == 1
        assert processed["active"] is True
        assert processed["count"] == 42
        assert processed["tags"] == ["tag1", "tag2"]
        assert processed["metadata"] == {"key": "value"}


class TestGetModelClass:
    """Test _get_model_class method."""

    @pytest.mark.parametrize(
        ("table_name", "expected_class_name"),
        [
            ("households", "Household"),
            ("properties", "Property"),
            ("areas", "Area"),
            ("cameras", "Camera"),
            ("zones", "CameraZone"),
            ("activity_baselines", "ActivityBaseline"),
            ("class_baselines", "ClassBaseline"),
            ("household_members", "HouseholdMember"),
            ("prompt_versions", "PromptVersion"),
            ("settings", "SystemSetting"),
            ("alert_rules", "AlertRule"),
            ("recipients", "Recipient"),
            ("recipient_channels", "RecipientChannel"),
        ],
    )
    def test_get_model_class_returns_expected_model(self, table_name, expected_class_name):
        """Test getting mapped model class for known backup tables."""
        service = RestoreService()
        model_class = service._get_model_class(table_name)

        assert model_class is not None
        assert model_class.__name__ == expected_class_name

    def test_get_model_class_unknown_table_returns_none(self):
        """Test unknown table returns None."""
        service = RestoreService()
        model_class = service._get_model_class("unknown_table")

        assert model_class is None

    def test_get_model_class_import_error_returns_none(self):
        """Test import error returns None and logs error."""
        service = RestoreService()
        # Create invalid mapping
        service.TABLE_MODEL_MAPPING["bad_table"] = "backend.models.nonexistent.BadModel"

        model_class = service._get_model_class("bad_table")

        assert model_class is None


@pytest.mark.asyncio
class TestRestoreTable:
    """Test _restore_table method."""

    async def test_restore_table_success(self, mock_db_session, tmp_path, sample_camera_data):
        """Test successful table restoration."""
        # Create backup file
        cameras_file = tmp_path / "cameras.json"
        cameras_file.write_text(json.dumps(sample_camera_data))

        service = RestoreService()

        # Use real Camera model instead of mock to avoid SQLAlchemy errors
        from backend.models.camera import Camera

        with patch.object(service, "_get_model_class", return_value=Camera, autospec=True):
            count = await service._restore_table(mock_db_session, "cameras", cameras_file)

            assert count == 2
            assert mock_db_session.add.call_count == 2
            assert mock_db_session.flush.call_count == 1
            mock_db_session.commit.assert_not_called()

    async def test_restore_table_empty_list(self, mock_db_session, tmp_path):
        """Test restoring table with empty list."""
        cameras_file = tmp_path / "cameras.json"
        cameras_file.write_text("[]")

        service = RestoreService()

        count = await service._restore_table(mock_db_session, "cameras", cameras_file)

        assert count == 0
        mock_db_session.add.assert_not_called()

    async def test_restore_table_missing_file_raises_error(self, mock_db_session, tmp_path):
        """Test missing file raises RestoreError."""
        cameras_file = tmp_path / "missing.json"
        service = RestoreService()

        with pytest.raises(RestoreError, match="Backup file not found"):
            await service._restore_table(mock_db_session, "cameras", cameras_file)

    async def test_restore_table_invalid_json_raises_error(self, mock_db_session, tmp_path):
        """Test invalid JSON raises RestoreError."""
        cameras_file = tmp_path / "cameras.json"
        cameras_file.write_text("not valid json")

        service = RestoreService()

        with pytest.raises(RestoreError, match="Invalid JSON"):
            await service._restore_table(mock_db_session, "cameras", cameras_file)

    async def test_restore_table_not_a_list_raises_error(self, mock_db_session, tmp_path):
        """Test non-list JSON raises RestoreError."""
        cameras_file = tmp_path / "cameras.json"
        cameras_file.write_text('{"not": "a list"}')

        service = RestoreService()

        with pytest.raises(RestoreError, match="Expected list of records"):
            await service._restore_table(mock_db_session, "cameras", cameras_file)

    async def test_restore_table_no_model_mapping_raises_error(
        self, mock_db_session, tmp_path, sample_camera_data
    ):
        """Test table without model mapping raises RestoreError."""
        cameras_file = tmp_path / "cameras.json"
        cameras_file.write_text(json.dumps(sample_camera_data))

        service = RestoreService()

        with patch.object(service, "_get_model_class", return_value=None, autospec=True):
            with pytest.raises(RestoreError, match="No model mapping for table cameras"):
                await service._restore_table(mock_db_session, "cameras", cameras_file)

            mock_db_session.add.assert_not_called()

    async def test_restore_table_does_not_delete_cameras(
        self, mock_db_session, tmp_path, sample_camera_data
    ):
        """Test cameras table is merged without DELETE so event cascades never fire."""
        cameras_file = tmp_path / "cameras.json"
        cameras_file.write_text(json.dumps(sample_camera_data))

        service = RestoreService()

        from backend.models.camera import Camera

        with patch.object(service, "_get_model_class", return_value=Camera, autospec=True):
            await service._restore_table(mock_db_session, "cameras", cameras_file)

            mock_db_session.execute.assert_not_called()

    async def test_restore_table_raises_on_record_error(
        self, mock_db_session, tmp_path, sample_camera_data
    ):
        """Test restore raises RestoreError naming table and record index when a record fails."""
        cameras_file = tmp_path / "cameras.json"
        cameras_file.write_text(json.dumps(sample_camera_data))

        service = RestoreService()

        from backend.models.camera import Camera

        call_count = 0
        original_init = Camera.__init__
        Camera.__init__ = original_init  # type: ignore[method-assign]

        def mock_init(self, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ValueError("Invalid data")
            original_init(self, **kwargs)

        with patch.object(service, "_get_model_class", return_value=Camera, autospec=True):
            with patch.object(Camera, "__init__", mock_init):
                with pytest.raises(
                    RestoreError,
                    match="Invalid record in table 'cameras' at index 1",
                ) as exc_info:
                    await service._restore_table(mock_db_session, "cameras", cameras_file)

                assert exc_info.value.table == "cameras"
                assert exc_info.value.record_index == 1


@pytest.mark.asyncio
class TestRestoreFromBackup:
    """Test restore_from_backup method."""

    async def test_restore_from_backup_invalid_zip_raises_error(self, mock_db_session, tmp_path):
        """Test invalid ZIP file raises BackupValidationError."""
        backup_file = tmp_path / "backup.zip"
        backup_file.write_text("not a zip file")

        service = RestoreService()

        with pytest.raises(BackupValidationError, match="Invalid backup file"):
            await service.restore_from_backup(
                backup_file=backup_file,
                db=mock_db_session,
                job_id="job-123",
            )

    async def test_restore_from_backup_missing_manifest_raises_error(
        self, mock_db_session, tmp_path
    ):
        """Test ZIP without manifest raises BackupValidationError."""
        backup_file = tmp_path / "backup.zip"

        with zipfile.ZipFile(backup_file, "w") as zf:
            zf.writestr("cameras.json", "[]")

        service = RestoreService()

        with pytest.raises(BackupValidationError, match="Backup manifest not found"):
            await service.restore_from_backup(
                backup_file=backup_file,
                db=mock_db_session,
                job_id="job-123",
            )

    async def test_restore_from_backup_invalid_manifest_json_raises_error(
        self, mock_db_session, tmp_path
    ):
        """Test invalid manifest JSON raises BackupValidationError."""
        backup_file = tmp_path / "backup.zip"

        with zipfile.ZipFile(backup_file, "w") as zf:
            zf.writestr("manifest.json", "not valid json")

        service = RestoreService()

        with pytest.raises(BackupValidationError, match="Invalid manifest JSON"):
            await service.restore_from_backup(
                backup_file=backup_file,
                db=mock_db_session,
                job_id="job-123",
            )

    async def test_restore_from_backup_success(
        self, mock_db_session, tmp_path, sample_manifest, sample_camera_data
    ):
        """Test successful backup restoration."""
        backup_file = tmp_path / "backup.zip"

        # Calculate correct checksum first
        import hashlib

        cameras_json = json.dumps(sample_camera_data)
        sample_manifest["contents"]["cameras"]["checksum"] = hashlib.sha256(
            cameras_json.encode()
        ).hexdigest()
        # Remove events from manifest to avoid checksum issues
        del sample_manifest["contents"]["events"]

        # Create valid backup ZIP
        with zipfile.ZipFile(backup_file, "w") as zf:
            # Write manifest
            zf.writestr("manifest.json", json.dumps(sample_manifest))
            # Write camera data
            zf.writestr("cameras.json", cameras_json)

        service = RestoreService()

        # Use real Camera model
        from backend.models.camera import Camera

        with patch.object(service, "_get_model_class", return_value=Camera, autospec=True):
            result = await service.restore_from_backup(
                backup_file=backup_file,
                db=mock_db_session,
                job_id="job-123",
            )

            assert isinstance(result, RestoreResult)
            assert result.backup_id == "backup-123"
            assert result.total_items == 2
            assert "cameras" in result.items_restored
            # RestoreService never commits; it flushes and leaves commit to Session B caller
            mock_db_session.commit.assert_not_called()
            assert mock_db_session.flush.call_count >= 1

    async def test_restore_from_backup_calls_progress_callback(
        self, mock_db_session, tmp_path, sample_manifest
    ):
        """Test progress callback is called during restore."""
        backup_file = tmp_path / "backup.zip"

        # Create minimal backup
        sample_manifest["contents"] = {}
        with zipfile.ZipFile(backup_file, "w") as zf:
            zf.writestr("manifest.json", json.dumps(sample_manifest))

        service = RestoreService()
        progress_callback = AsyncMock()

        await service.restore_from_backup(
            backup_file=backup_file,
            db=mock_db_session,
            job_id="job-123",
            progress_callback=progress_callback,
        )

        # Verify callback was called multiple times
        assert progress_callback.call_count >= 4  # Extract, manifest, checksums, finalize

    async def test_restore_from_backup_rollback_on_error(
        self, mock_db_session, tmp_path, sample_manifest, sample_camera_data
    ):
        """Test transaction is rolled back on error."""
        backup_file = tmp_path / "backup.zip"

        # Calculate correct checksum first
        import hashlib

        cameras_json = json.dumps(sample_camera_data)
        sample_manifest["contents"]["cameras"]["checksum"] = hashlib.sha256(
            cameras_json.encode()
        ).hexdigest()
        # Remove events from manifest
        del sample_manifest["contents"]["events"]

        with zipfile.ZipFile(backup_file, "w") as zf:
            zf.writestr("manifest.json", json.dumps(sample_manifest))
            zf.writestr("cameras.json", cameras_json)

        service = RestoreService()

        # Make flush fail to trigger rollback
        mock_db_session.flush.side_effect = ValueError("Database error")

        # Use real Camera model
        from backend.models.camera import Camera

        with patch.object(service, "_get_model_class", return_value=Camera, autospec=True):
            with pytest.raises(RestoreError, match="Restore failed"):
                await service.restore_from_backup(
                    backup_file=backup_file,
                    db=mock_db_session,
                    job_id="job-123",
                )

            mock_db_session.rollback.assert_called_once()
            mock_db_session.commit.assert_not_called()

    async def test_restore_from_backup_missing_table_file_raises_error(
        self, mock_db_session, tmp_path, sample_manifest
    ):
        """Test restore fails when a manifest-listed non-skipped table file is missing."""
        backup_file = tmp_path / "backup.zip"

        with zipfile.ZipFile(backup_file, "w") as zf:
            zf.writestr("manifest.json", json.dumps(sample_manifest))
            # Don't write cameras.json

        service = RestoreService()

        with pytest.raises(
            BackupValidationError,
            match="Backup file for table 'cameras' listed in manifest is missing",
        ):
            await service.restore_from_backup(
                backup_file=backup_file,
                db=mock_db_session,
                job_id="job-123",
            )

    async def test_restore_from_1_0_archive_skips_events_and_alerts(
        self, mock_db_session, tmp_path, sample_camera_data
    ):
        """Test a 1.0 archive with events and alerts restores cameras and lists both as skipped."""
        import hashlib

        cameras_json = json.dumps(sample_camera_data)
        events_json = json.dumps([{"id": 1, "camera_id": "camera-1"}])
        alerts_json = json.dumps([{"id": "alert-1", "event_id": 1}])
        manifest = {
            "backup_id": "legacy-1.0-backup",
            "version": "1.0",
            "created_at": "2026-01-15T10:30:00Z",
            "contents": {
                "events": {
                    "count": 1,
                    "checksum": hashlib.sha256(events_json.encode()).hexdigest(),
                },
                "alerts": {
                    "count": 1,
                    "checksum": hashlib.sha256(alerts_json.encode()).hexdigest(),
                },
                "cameras": {
                    "count": 2,
                    "checksum": hashlib.sha256(cameras_json.encode()).hexdigest(),
                },
            },
        }
        backup_file = tmp_path / "legacy_1_0.zip"
        with zipfile.ZipFile(backup_file, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("events.json", events_json)
            zf.writestr("alerts.json", alerts_json)
            zf.writestr("cameras.json", cameras_json)

        service = RestoreService()
        result = await service.restore_from_backup(backup_file, mock_db_session)

        assert result.items_restored == {"cameras": 2}
        assert result.skipped_tables == ["events", "alerts"]

    async def test_restore_from_backup_processes_tables_in_order(
        self, mock_db_session, tmp_path, sample_manifest
    ):
        """Test tables are restored in dependency order."""
        backup_file = tmp_path / "backup.zip"

        # Calculate correct checksums for empty arrays
        import hashlib

        empty_json = "[]"
        correct_checksum = hashlib.sha256(empty_json.encode()).hexdigest()

        # Add all tables to manifest
        for table in RESTORE_TABLE_ORDER:
            sample_manifest["contents"][table] = {"count": 0, "checksum": correct_checksum}

        with zipfile.ZipFile(backup_file, "w") as zf:
            zf.writestr("manifest.json", json.dumps(sample_manifest))
            for table in RESTORE_TABLE_ORDER:
                zf.writestr(f"{table}.json", empty_json)

        service = RestoreService()
        restore_order = []

        async def track_restore_order(db, table_name, file_path):
            restore_order.append(table_name)
            return 0

        with patch.object(
            service, "_restore_table", side_effect=track_restore_order, autospec=True
        ):
            await service.restore_from_backup(
                backup_file=backup_file,
                db=mock_db_session,
                job_id="job-123",
            )

            # Verify tables were restored in correct order
            assert restore_order == RESTORE_TABLE_ORDER

    async def test_restore_from_backup_parses_datetime_correctly(
        self, mock_db_session, tmp_path, sample_manifest
    ):
        """Test backup_created_at is parsed correctly."""
        backup_file = tmp_path / "backup.zip"

        sample_manifest["contents"] = {}
        sample_manifest["created_at"] = "2024-01-15T10:30:00Z"

        with zipfile.ZipFile(backup_file, "w") as zf:
            zf.writestr("manifest.json", json.dumps(sample_manifest))

        service = RestoreService()

        result = await service.restore_from_backup(
            backup_file=backup_file,
            db=mock_db_session,
            job_id="job-123",
        )

        assert isinstance(result.backup_created_at, datetime)
        assert result.backup_created_at.year == 2024
        assert result.backup_created_at.month == 1
        assert result.backup_created_at.day == 15

    async def test_restore_from_backup_checksum_mismatch_raises_error(
        self, mock_db_session, tmp_path, sample_manifest
    ):
        """Test checksum mismatch prevents restore."""
        backup_file = tmp_path / "backup.zip"

        sample_manifest["contents"]["cameras"]["checksum"] = "wrong_checksum"

        with zipfile.ZipFile(backup_file, "w") as zf:
            zf.writestr("manifest.json", json.dumps(sample_manifest))
            zf.writestr("cameras.json", "[]")

        service = RestoreService()

        with pytest.raises(BackupCorruptedError, match="Checksum mismatch"):
            await service.restore_from_backup(
                backup_file=backup_file,
                db=mock_db_session,
                job_id="job-123",
            )

    async def test_restore_from_backup_path_traversal_protection(
        self, mock_db_session, tmp_path, sample_manifest
    ):
        """Test path traversal protection for manifest."""
        backup_file = tmp_path / "backup.zip"

        with zipfile.ZipFile(backup_file, "w") as zf:
            zf.writestr("manifest.json", json.dumps(sample_manifest))

        service = RestoreService()

        # Mock the manifest path resolution to return path outside backup dir
        original_resolve = Path.resolve

        def mock_resolve(self):
            # Only mock the manifest.json path
            if "manifest.json" in str(self):
                return Path("/etc/passwd")
            return original_resolve(self)

        with patch.object(Path, "resolve", mock_resolve):
            with pytest.raises(BackupValidationError, match="Invalid manifest path"):
                await service.restore_from_backup(
                    backup_file=backup_file,
                    db=mock_db_session,
                    job_id="job-123",
                )


class TestRestoreTableOrder:
    """Test RESTORE_TABLE_ORDER constant."""

    def test_restore_table_order_has_required_tables(self):
        """Test table order includes all 14 configuration tables and excludes history."""
        assert "households" in RESTORE_TABLE_ORDER
        assert "properties" in RESTORE_TABLE_ORDER
        assert "areas" in RESTORE_TABLE_ORDER
        assert "cameras" in RESTORE_TABLE_ORDER
        assert "camera_areas" in RESTORE_TABLE_ORDER
        assert "zones" in RESTORE_TABLE_ORDER
        assert "activity_baselines" in RESTORE_TABLE_ORDER
        assert "class_baselines" in RESTORE_TABLE_ORDER
        assert "household_members" in RESTORE_TABLE_ORDER
        assert "prompt_versions" in RESTORE_TABLE_ORDER
        assert "settings" in RESTORE_TABLE_ORDER
        assert "alert_rules" in RESTORE_TABLE_ORDER
        assert "recipients" in RESTORE_TABLE_ORDER
        assert "recipient_channels" in RESTORE_TABLE_ORDER
        assert "events" not in RESTORE_TABLE_ORDER
        assert "alerts" not in RESTORE_TABLE_ORDER

    def test_restore_table_order_parents_before_children(self):
        """Test parent tables come before child tables (FK dependency)."""
        assert RESTORE_TABLE_ORDER.index("households") < RESTORE_TABLE_ORDER.index("properties")
        assert RESTORE_TABLE_ORDER.index("properties") < RESTORE_TABLE_ORDER.index("areas")
        assert RESTORE_TABLE_ORDER.index("properties") < RESTORE_TABLE_ORDER.index("cameras")
        assert RESTORE_TABLE_ORDER.index("cameras") < RESTORE_TABLE_ORDER.index("camera_areas")
        assert RESTORE_TABLE_ORDER.index("areas") < RESTORE_TABLE_ORDER.index("camera_areas")
        assert RESTORE_TABLE_ORDER.index("cameras") < RESTORE_TABLE_ORDER.index("zones")
        assert RESTORE_TABLE_ORDER.index("cameras") < RESTORE_TABLE_ORDER.index(
            "activity_baselines"
        )
        assert RESTORE_TABLE_ORDER.index("cameras") < RESTORE_TABLE_ORDER.index("class_baselines")
        assert RESTORE_TABLE_ORDER.index("households") < RESTORE_TABLE_ORDER.index(
            "household_members"
        )
        # recipients before their channels (FK dependency)
        assert RESTORE_TABLE_ORDER.index("recipients") < RESTORE_TABLE_ORDER.index(
            "recipient_channels"
        )


class TestRestoreServiceExceptions:
    """Test custom exception classes."""

    @pytest.mark.parametrize(
        "exc_cls",
        [BackupValidationError, BackupCorruptedError, RestoreError],
    )
    def test_custom_error_is_exception(self, exc_cls):
        """Test custom restore exception classes inherit from Exception."""
        error = exc_cls("test")
        assert isinstance(error, Exception)


class TestRestoreResult:
    """Test RestoreResult dataclass."""

    def test_restore_result_creation(self):
        """Test RestoreResult can be created with required fields."""
        result = RestoreResult(
            backup_id="backup-123",
            backup_created_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
            items_restored={"cameras": 2, "events": 5},
            total_items=7,
        )

        assert result.backup_id == "backup-123"
        assert result.total_items == 7
        assert result.items_restored["cameras"] == 2

    def test_restore_result_has_all_fields(self):
        """Test RestoreResult includes all expected fields."""
        result = RestoreResult(
            backup_id="backup-123",
            backup_created_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
            items_restored={},
            total_items=0,
        )

        assert hasattr(result, "backup_id")
        assert hasattr(result, "backup_created_at")
        assert hasattr(result, "items_restored")
        assert hasattr(result, "total_items")


class TestSupportedBackupVersion:
    """Test SUPPORTED_BACKUP_VERSION constant."""

    def test_supported_backup_version_is_defined(self):
        """Test SUPPORTED_BACKUP_VERSION is defined."""
        assert SUPPORTED_BACKUP_VERSION is not None
        assert isinstance(SUPPORTED_BACKUP_VERSION, str)

    def test_supported_backup_version_format(self):
        """Test SUPPORTED_BACKUP_VERSION has expected format."""
        # Should be in format "major.minor"
        parts = SUPPORTED_BACKUP_VERSION.split(".")
        assert len(parts) == 2
        assert parts[0].isdigit()
        assert parts[1].isdigit()


class _FakeScalarResult:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def scalar_one_or_none(self) -> Any:
        return self._items[0] if self._items else None

    def scalars(self) -> _FakeScalarResult:
        return self

    def all(self) -> list[Any]:
        return list(self._items)

    def mappings(self) -> _FakeScalarResult:
        return self


class _InMemoryAsyncDB:
    """Lightweight in-memory async session for exercising all 12 restore merge strategies."""

    def __init__(self, initial: list[Any] | None = None) -> None:
        self.objects: list[Any] = list(initial or [])
        self.deleted: list[Any] = []
        self.committed = False
        self.rolled_back = False
        self.next_id = 100

    async def execute(self, stmt: Any) -> _FakeScalarResult:
        stmt_str = str(stmt)
        if "pg_get_serial_sequence" in stmt_str or "setval" in stmt_str:
            return _FakeScalarResult([1])
        if stmt_str.lstrip().upper().startswith("DELETE"):
            if "camera_areas" in stmt_str:
                self.objects = [o for o in self.objects if not isinstance(o, dict)]
            elif "activity_baselines" in stmt_str:
                from backend.models.baseline import ActivityBaseline

                self.objects = [o for o in self.objects if not isinstance(o, ActivityBaseline)]
            elif "class_baselines" in stmt_str:
                from backend.models.baseline import ClassBaseline

                self.objects = [o for o in self.objects if not isinstance(o, ClassBaseline)]
            return _FakeScalarResult([])
        if stmt_str.lstrip().upper().startswith("INSERT"):
            return _FakeScalarResult([])

        target_cls = None
        try:
            desc = getattr(stmt, "column_descriptions", None)
            if desc and isinstance(desc[0], dict):
                entity = desc[0].get("entity")
                if isinstance(entity, type):
                    target_cls = entity
        except Exception:
            target_cls = None

        if target_cls is not None:
            matches = [o for o in self.objects if isinstance(o, target_cls)]
            try:
                compiled = stmt.compile()
                params = compiled.params
            except Exception:
                params = {}
            for k, v in params.items():
                col = k.split("_1")[0]
                if isinstance(v, (list, tuple, set)):
                    matches = [o for o in matches if getattr(o, col, None) in v]
                else:
                    matches = [o for o in matches if getattr(o, col, None) == v]
            return _FakeScalarResult(matches)

        if "camera_areas" in stmt_str:
            return _FakeScalarResult([o for o in self.objects if isinstance(o, dict)])

        return _FakeScalarResult([])

    def add(self, obj: Any) -> None:
        from datetime import UTC, datetime

        if getattr(obj, "created_at", None) is None and hasattr(obj, "created_at"):
            obj.created_at = datetime.now(UTC)
        if obj not in self.objects:
            self.objects.append(obj)

    async def flush(self) -> None:
        for obj in self.objects:
            if hasattr(obj, "id") and getattr(obj, "id", None) is None:
                obj.id = self.next_id
                self.next_id += 1

    async def commit(self) -> None:
        await self.flush()
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)
        self.objects = [o for o in self.objects if o is not obj]

    async def refresh(self, _obj: Any) -> None:
        return None


class TestAllTableMergesAndRoutesUnit:
    """Exercise all 12 table merge strategies (same & foreign installation) and route helpers."""

    @staticmethod
    def _build_full_archive(
        tmp_path: Path,
        *,
        backup_id: str = "full-bk-1",
        version: str = "1.1",
        installation_id: str | None = "inst-same",
        extra_tables: dict[str, list[dict[str, Any]]] | None = None,
    ) -> Path:
        tables_data: dict[str, list[dict[str, Any]]] = {
            "households": [{"id": 1, "name": "Svoboda Home"}],
            "properties": [{"id": 1, "household_id": 1, "name": "Main House"}],
            "areas": [{"id": 1, "property_id": 1, "name": "Front Yard"}],
            "cameras": [
                {
                    "id": "front_door",
                    "name": "Front Door",
                    "folder_path": "/export/foscam/front_door",
                    "status": "online",
                    "property_id": 1,
                }
            ],
            "camera_areas": [{"camera_id": "front_door", "area_id": 1}],
            "zones": [
                {
                    "id": "zone_porch",
                    "camera_id": "front_door",
                    "name": "Porch",
                    "zone_type": "entry_point",
                    "coordinates": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
                    "shape": "rectangle",
                }
            ],
            "activity_baselines": [
                {
                    "id": 50,
                    "camera_id": "front_door",
                    "hour": 12,
                    "day_of_week": 1,
                    "avg_count": 3.5,
                    "sample_count": 10,
                }
            ],
            "class_baselines": [
                {
                    "id": 60,
                    "camera_id": "front_door",
                    "detection_class": "person",
                    "hour": 12,
                    "frequency": 2.0,
                    "sample_count": 8,
                }
            ],
            "household_members": [
                {
                    "id": 1,
                    "household_id": 1,
                    "name": "Alice",
                    "role": "resident",
                    "trusted_level": "full",
                    "known_person_id": 42,
                }
            ],
            "prompt_versions": [
                {
                    "id": 1,
                    "model": "nemotron",
                    "version": 1,
                    "config_json": json.dumps({"system_prompt": " prompt v1 "}),
                    "is_active": True,
                }
            ],
            "settings": [
                {"key": "retention_days", "value": {"days": 30}},
                {"key": "installation_id", "value": {"installation_id": "foreign-inst-999"}},
            ],
            "alert_rules": [
                {
                    "id": "11111111-2222-3333-4444-555555555555",
                    "name": "Night Person Alert",
                    "severity": "high",
                    "enabled": True,
                }
            ],
            "recipients": [
                {
                    "id": "22222222-2222-7222-8222-222222222222",
                    "name": "Household",
                    "enabled": True,
                    "critical_breaks_quiet": True,
                }
            ],
            "recipient_channels": [
                {
                    "id": "33333333-3333-7333-8333-333333333333",
                    "recipient_id": "22222222-2222-7222-8222-222222222222",
                    "kind": "webhook",
                    "target": "http://192.168.1.50/hook",
                    "on_local_network": True,
                    "include_names": False,
                    "enabled": True,
                }
            ],
        }
        if extra_tables:
            tables_data.update(extra_tables)

        contents: dict[str, dict[str, Any]] = {}
        import hashlib

        zip_path = tmp_path / f"{backup_id}.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for tname, rows in tables_data.items():
                payload = json.dumps(rows, indent=2)
                zf.writestr(f"{tname}.json", payload)
                contents[tname] = {
                    "count": len(rows),
                    "checksum": hashlib.sha256(payload.encode()).hexdigest(),
                }
            manifest: dict[str, Any] = {
                "backup_id": backup_id,
                "version": version,
                "created_at": "2026-10-22T06:00:00Z",
                "contents": contents,
            }
            if installation_id is not None:
                manifest["installation_id"] = installation_id
            zf.writestr("manifest.json", json.dumps(manifest))
        return zip_path

    @pytest.mark.asyncio
    async def test_restore_same_and_foreign_installation_all_tables(self, tmp_path: Path) -> None:
        from backend.models.face_identity import KnownPerson
        from backend.models.gpu_config import SystemSetting

        service = RestoreService()
        db_same = _InMemoryAsyncDB(
            [
                SystemSetting(
                    key="installation_id",
                    value={"installation_id": "inst-same"},
                ),
                KnownPerson(id=42, name="Alice"),
            ]
        )
        zip_same = self._build_full_archive(
            tmp_path, backup_id="bk-same", installation_id="inst-same"
        )
        res_same = await service.restore_from_backup(zip_same, db_same)  # type: ignore[arg-type]
        assert res_same.same_installation is True
        assert res_same.total_items >= 12
        assert res_same.cleared_known_person_links == []
        assert "households" in res_same.added_rows

        res_same_2 = await service.restore_from_backup(zip_same, db_same)  # type: ignore[arg-type]
        assert res_same_2.same_installation is True
        assert res_same_2.tables["cameras"].updated == 1
        assert res_same_2.tables["zones"].updated == 1
        assert res_same_2.tables["alert_rules"].updated == 1
        assert res_same_2.tables["prompt_versions"].updated == 1
        assert res_same_2.tables["settings"].updated == 1
        assert res_same_2.tables["recipients"].updated == 1
        assert res_same_2.tables["recipient_channels"].updated == 1

        zip_foreign = self._build_full_archive(
            tmp_path, backup_id="bk-foreign", installation_id="inst-other"
        )
        res_foreign = await service.restore_from_backup(zip_foreign, db_same)  # type: ignore[arg-type]
        assert res_foreign.same_installation is False
        assert res_foreign.cleared_known_person_links == ["Alice"]

        zip_v10 = self._build_full_archive(
            tmp_path,
            backup_id="bk-v10",
            version="1.0",
            installation_id=None,
            extra_tables={
                "events": [{"id": 1}],
                "alerts": [{"id": "a1"}],
                "prompts": [{"id": 1}],
                "baselines": [
                    {
                        "camera_id": "front_door",
                        "hour": 9,
                        "day_of_week": 2,
                        "avg_count": 1.0,
                        "sample_count": 4,
                    }
                ],
            },
        )
        res_v10 = await service.restore_from_backup(zip_v10, db_same)  # type: ignore[arg-type]
        assert res_v10.same_installation is False
        assert set(res_v10.skipped_tables) == {"events", "alerts", "prompts"}

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_restored_recipient_channels_arrive_without_secrets(self, tmp_path: Path) -> None:
        """[B4.2] 4n-restore.md §Privacy: recipient channels arrive without their
        secrets. The backup strips signing_secret_encrypted/signing_secret_hint at
        export, so the archive row carries no such key; per 4n-restore.md §Shape
        ("A key missing from a record keeps the local value on update and the
        default on insert") a same-installation merge keeps the live channel's
        secret and a new channel inserts with None.
        """
        from backend.models.alert_delivery import Recipient, RecipientChannel
        from backend.models.gpu_config import SystemSetting

        service = RestoreService()
        local_recipient = Recipient(
            id="22222222-2222-7222-8222-222222222222",
            name="Household",
            enabled=True,
            critical_breaks_quiet=True,
        )
        local_channel = RecipientChannel(
            id="33333333-3333-7333-8333-333333333333",
            recipient_id=local_recipient.id,
            kind="webhook",
            target="http://192.168.1.50/hook",
            on_local_network=True,
        )
        local_channel.signing_secret_encrypted = (
            "gAAAAABl-live-fernet-secret"  # pragma: allowlist secret
        )
        local_channel.signing_secret_hint = "gAAA"  # pragma: allowlist secret
        db = _InMemoryAsyncDB(
            [
                SystemSetting(
                    key="installation_id",
                    value={"installation_id": "inst-same"},
                ),
                local_recipient,
                local_channel,
            ]
        )

        zip_path = self._build_full_archive(
            tmp_path,
            backup_id="bk-secrets",
            installation_id="inst-same",
            # Two channels: one merging into the live row by id, one fresh.
            extra_tables={
                "recipient_channels": [
                    {
                        "id": "33333333-3333-7333-8333-333333333333",
                        "recipient_id": "22222222-2222-7222-8222-222222222222",
                        "kind": "webhook",
                        "target": "http://192.168.1.50/hook",
                        "on_local_network": True,
                        "include_names": False,
                        "enabled": True,
                    },
                    {
                        "id": "44444444-4444-7444-8444-444444444444",
                        "recipient_id": "22222222-2222-7222-8222-222222222222",
                        "kind": "email",
                        "target": "person@example.com",
                        "on_local_network": False,
                        "include_names": False,
                        "enabled": True,
                    },
                ]
            },
        )
        res = await service.restore_from_backup(zip_path, db)  # type: ignore[arg-type]
        assert res.same_installation is True

        # The merged channel KEPT its live secret (the absent key never overwrote it).
        kept_secret = local_channel.signing_secret_encrypted  # pragma: allowlist secret
        assert kept_secret == "gAAAAABl-live-fernet-secret"  # pragma: allowlist secret
        assert local_channel.signing_secret_hint == "gAAA"  # pragma: allowlist secret
        # The rest of the channel followed the archive.
        assert local_channel.target == "http://192.168.1.50/hook"
        assert local_channel.on_local_network is True

        # The fresh channel from the same archive arrives without secrets.
        fresh = next(
            o
            for o in db.objects
            if isinstance(o, RecipientChannel) and o.id == "44444444-4444-7444-8444-444444444444"
        )
        assert fresh.signing_secret_encrypted is None
        assert fresh.signing_secret_hint is None
        assert fresh.kind in {"webhook", "email"}

    async def test_camera_clash_and_invalid_record_errors(self, tmp_path: Path) -> None:
        from backend.models.camera import Camera

        service = RestoreService()
        existing_cam = Camera(
            id="other_cam",
            name="Front Door",
            folder_path="/export/foscam/other",
            status="online",
        )
        db = _InMemoryAsyncDB([existing_cam])
        cam_file = tmp_path / "cameras.json"
        cam_file.write_text(
            json.dumps(
                [
                    {
                        "id": "front_door",
                        "name": "Front Door",
                        "folder_path": "/export/foscam/front_door",
                        "status": "online",
                    }
                ]
            )
        )
        with pytest.raises(RestoreError, match="clashes on unique name"):
            await service._restore_table(db, "cameras", cam_file)  # type: ignore[arg-type]

        bad_zones = tmp_path / "zones.json"
        bad_zones.write_text(json.dumps(["not-a-dict"]))
        with pytest.raises(RestoreError, match="expected object"):
            await service._restore_table(db, "zones", bad_zones)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_backup_routes_and_background_jobs_unit(self, tmp_path: Path) -> None:
        from io import BytesIO
        from unittest.mock import MagicMock

        from fastapi import BackgroundTasks, HTTPException, UploadFile

        from backend.api.routes.backup import (
            _backup_model_to_response,
            _restore_model_to_response,
            create_backup,
            delete_backup,
            download_backup,
            get_backup_status,
            get_restore_status,
            list_backups,
            run_backup_job,
            run_restore_job,
            start_restore,
        )
        from backend.api.schemas.backup import BackupJobCreate
        from backend.models.backup_job import (
            BackupJob,
            BackupJobStatus,
            RestoreJob,
            RestoreJobStatus,
        )
        from backend.models.gpu_config import SystemSetting
        from backend.services.backup_service import BackupService

        bjob = BackupJob(
            id="bjob-1",
            status=BackupJobStatus.COMPLETED,
            total_tables=12,
            completed_tables=12,
            progress_percent=100,
            file_path="/app/data/backups/backup.zip",
            file_size_bytes=512,
            manifest_json={
                "backup_id": "bjob-1",
                "version": "1.1",
                "created_at": "2026-10-22T06:00:00Z",
                "installation_id": "inst-1",
                "label": "before restore of x",
                "contents": {"cameras": {"count": 1, "checksum": "abc"}},
            },
        )
        bjob.created_at = datetime(2026, 10, 22, 6, 0, tzinfo=UTC)
        b_resp = _backup_model_to_response(bjob)
        assert b_resp.manifest is not None
        assert b_resp.manifest.installation_id == "inst-1"
        assert b_resp.manifest.label == "before restore of x"

        rjob = RestoreJob(
            id="rjob-1",
            status=RestoreJobStatus.COMPLETED,
            total_tables=12,
            completed_tables=12,
            progress_percent=100,
            items_restored={
                "cameras": 1,
                "_details": {
                    "safety_backup_id": "safety-1",
                    "same_installation": False,
                    "tables": {"cameras": {"inserted": 1, "updated": 0, "replaced": 0, "kept": 0}},
                    "added_rows": {"cameras": ["Front Door"]},
                    "cleared_known_person_links": ["Alice"],
                    "skipped_tables": ["events"],
                },
            },
        )
        rjob.created_at = datetime(2026, 10, 22, 6, 5, tzinfo=UTC)
        r_resp = _restore_model_to_response(rjob)
        assert r_resp.items_restored == {"cameras": 1}
        assert r_resp.safety_backup_id == "safety-1"
        assert r_resp.same_installation is False
        assert r_resp.tables is not None and r_resp.tables["cameras"].inserted == 1
        assert r_resp.added_rows == {"cameras": ["Front Door"]}
        assert r_resp.cleared_known_person_links == ["Alice"]
        assert r_resp.skipped_tables == ["events"]

        bk_svc = BackupService(backup_dir=tmp_path / "backups")
        run_bjob = BackupJob(id="bjob-run", status=BackupJobStatus.PENDING, total_tables=12)
        run_bjob.created_at = datetime(2026, 10, 22, 6, 0, tzinfo=UTC)
        db_for_backup = _InMemoryAsyncDB(
            [
                run_bjob,
                SystemSetting(key="installation_id", value={"installation_id": "inst-same"}),
            ]
        )
        await run_backup_job("bjob-run", bk_svc, db_for_backup)  # type: ignore[arg-type]
        assert run_bjob.status == BackupJobStatus.COMPLETED
        assert run_bjob.file_path is not None

        run_rjob = RestoreJob(id="rjob-run", status=RestoreJobStatus.PENDING, total_tables=12)
        run_rjob.created_at = datetime(2026, 10, 22, 6, 10, tzinfo=UTC)
        db_for_restore = _InMemoryAsyncDB(
            [
                run_rjob,
                SystemSetting(key="installation_id", value={"installation_id": "inst-same"}),
            ]
        )
        upload_copy = self._build_full_archive(
            tmp_path, backup_id="upload-copy", installation_id="inst-same"
        )
        zip_bytes = upload_copy.read_bytes()
        await run_restore_job(
            run_rjob.id,
            upload_copy,
            RestoreService(),
            db_for_restore,  # type: ignore[arg-type]
            backup_service=bk_svc,
        )
        assert run_rjob.status == RestoreJobStatus.COMPLETED
        assert run_rjob.items_restored is not None
        assert "_details" in run_rjob.items_restored

        fail_rjob = RestoreJob(id="rjob-fail", status=RestoreJobStatus.PENDING, total_tables=12)
        fail_rjob.created_at = datetime(2026, 10, 22, 6, 15, tzinfo=UTC)
        db_fail = _InMemoryAsyncDB([fail_rjob])
        broken_bk = MagicMock(spec=BackupService)
        broken_bk.create_backup.side_effect = RuntimeError("disk full")
        await run_restore_job(
            fail_rjob.id,
            tmp_path / "nonexistent.zip",
            RestoreService(),
            db_fail,  # type: ignore[arg-type]
            backup_service=broken_bk,
        )
        assert fail_rjob.status == RestoreJobStatus.FAILED
        assert "Safety backup failed before restore" in (fail_rjob.error_message or "")

        bg = BackgroundTasks()
        start_resp = await create_backup(BackupJobCreate(), bg, db_for_backup)  # type: ignore[arg-type]
        assert start_resp.status.value == "pending"

        list_resp = await list_backups(db_for_backup)  # type: ignore[arg-type]
        assert list_resp.total >= 1

        status_resp = await get_backup_status("bjob-run", db_for_backup)  # type: ignore[arg-type]
        assert status_resp.id == "bjob-run"

        with pytest.raises(HTTPException) as exc404:
            await get_backup_status("missing-id", db_for_backup)  # type: ignore[arg-type]
        assert exc404.value.status_code == 404

        dl_resp = await download_backup("bjob-run", db_for_backup)  # type: ignore[arg-type]
        assert str(dl_resp.path) == str(run_bjob.file_path)

        upload = UploadFile(filename="backup.zip", file=BytesIO(zip_bytes))
        restore_start = await start_restore(bg, upload, db_for_restore)  # type: ignore[arg-type]
        assert restore_start.status.value == "pending"

        bad_upload = UploadFile(filename="backup.txt", file=BytesIO(b"hello"))
        with pytest.raises(HTTPException) as exc400:
            await start_restore(bg, bad_upload, db_for_restore)  # type: ignore[arg-type]
        assert exc400.value.status_code == 400

        r_status = await get_restore_status("rjob-run", db_for_restore)  # type: ignore[arg-type]
        assert r_status.id == "rjob-run"

        del_resp = await delete_backup("bjob-run", db_for_backup)  # type: ignore[arg-type]
        assert del_resp == {"deleted": True}
