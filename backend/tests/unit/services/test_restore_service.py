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
            "status": "online",
            "created_at": "2024-01-15T10:00:00Z",
        },
        {
            "id": "camera-2",
            "name": "Back Yard",
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

    def test_validate_manifest_missing_backup_id(self, sample_manifest):
        """Test manifest without backup_id raises error."""
        del sample_manifest["backup_id"]
        service = RestoreService()

        with pytest.raises(
            BackupValidationError, match="Missing required manifest field: backup_id"
        ):
            service._validate_manifest(sample_manifest)

    def test_validate_manifest_missing_version(self, sample_manifest):
        """Test manifest without version raises error."""
        del sample_manifest["version"]
        service = RestoreService()

        with pytest.raises(BackupValidationError, match="Missing required manifest field: version"):
            service._validate_manifest(sample_manifest)

    def test_validate_manifest_missing_created_at(self, sample_manifest):
        """Test manifest without created_at raises error."""
        del sample_manifest["created_at"]
        service = RestoreService()

        with pytest.raises(
            BackupValidationError, match="Missing required manifest field: created_at"
        ):
            service._validate_manifest(sample_manifest)

    def test_validate_manifest_unsupported_version(self, sample_manifest):
        """Test manifest with unsupported version raises error."""
        sample_manifest["version"] = "2.0"
        service = RestoreService()

        with pytest.raises(BackupValidationError, match="Unsupported backup version: 2.0"):
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

    def test_validate_manifest_missing_count(self, sample_manifest):
        """Test manifest with missing count raises error."""
        del sample_manifest["contents"]["cameras"]["count"]
        service = RestoreService()

        with pytest.raises(
            BackupValidationError, match="Missing count or checksum for table cameras"
        ):
            service._validate_manifest(sample_manifest)

    def test_validate_manifest_missing_checksum(self, sample_manifest):
        """Test manifest with missing checksum raises error."""
        del sample_manifest["contents"]["cameras"]["checksum"]
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

    def test_verify_checksums_missing_file_logs_warning(self, tmp_path, sample_manifest):
        """Test missing file logs warning but doesn't raise."""
        # Don't create cameras.json file
        service = RestoreService()

        # Should not raise, just log warning
        service._verify_checksums(tmp_path, sample_manifest)

    def test_verify_checksums_empty_contents(self, tmp_path, sample_manifest):
        """Test empty contents doesn't raise error."""
        sample_manifest["contents"] = {}
        service = RestoreService()

        # Should not raise
        service._verify_checksums(tmp_path, sample_manifest)


class TestIsDatetimeField:
    """Test _is_datetime_field method."""

    def test_is_datetime_field_with_at_suffix(self):
        """Test field ending with _at is recognized as datetime."""
        service = RestoreService()
        assert service._is_datetime_field("created_at", "2024-01-15T10:30:00Z")
        assert service._is_datetime_field("updated_at", "2024-01-15T10:30:00Z")
        assert service._is_datetime_field("started_at", "2024-01-15T10:30:00Z")

    def test_is_datetime_field_with_date_suffix(self):
        """Test field ending with _date is recognized as datetime."""
        service = RestoreService()
        assert service._is_datetime_field("start_date", "2024-01-15")

    def test_is_datetime_field_with_time_suffix(self):
        """Test field ending with _time is recognized as datetime."""
        service = RestoreService()
        assert service._is_datetime_field("event_time", "2024-01-15T10:30:00")

    def test_is_datetime_field_with_timestamp_suffix(self):
        """Test field ending with _timestamp is recognized as datetime."""
        service = RestoreService()
        assert service._is_datetime_field("event_timestamp", "2024-01-15T10:30:00")

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

    def test_get_model_class_returns_camera_model(self):
        """Test getting Camera model class."""
        service = RestoreService()
        model_class = service._get_model_class("cameras")

        assert model_class is not None
        assert model_class.__name__ == "Camera"

    def test_get_model_class_returns_event_model(self):
        """Test getting Event model class."""
        service = RestoreService()
        model_class = service._get_model_class("events")

        assert model_class is not None
        assert model_class.__name__ == "Event"

    def test_get_model_class_returns_alert_model(self):
        """Test getting Alert model class."""
        service = RestoreService()
        model_class = service._get_model_class("alerts")

        assert model_class is not None
        assert model_class.__name__ == "Alert"

    def test_get_model_class_returns_zone_model(self):
        """Test getting CameraZone model class."""
        service = RestoreService()
        model_class = service._get_model_class("zones")

        assert model_class is not None
        assert model_class.__name__ == "CameraZone"

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

        with patch.object(service, "_get_model_class", return_value=Camera):
            count = await service._restore_table(mock_db_session, "cameras", cameras_file)

            assert count == 2
            assert mock_db_session.add.call_count == 2
            # Flush is called after delete and after inserts
            assert mock_db_session.flush.call_count == 2

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

    async def test_restore_table_no_model_mapping_returns_zero(
        self, mock_db_session, tmp_path, sample_camera_data
    ):
        """Test table without model mapping returns 0."""
        cameras_file = tmp_path / "cameras.json"
        cameras_file.write_text(json.dumps(sample_camera_data))

        service = RestoreService()

        with patch.object(service, "_get_model_class", return_value=None):
            count = await service._restore_table(mock_db_session, "cameras", cameras_file)

            assert count == 0
            mock_db_session.add.assert_not_called()

    async def test_restore_table_clears_existing_data(
        self, mock_db_session, tmp_path, sample_camera_data
    ):
        """Test table data is cleared before restore."""
        cameras_file = tmp_path / "cameras.json"
        cameras_file.write_text(json.dumps(sample_camera_data))

        service = RestoreService()

        # Use real Camera model instead of mock
        from backend.models.camera import Camera

        with patch.object(service, "_get_model_class", return_value=Camera):
            await service._restore_table(mock_db_session, "cameras", cameras_file)

            # Verify delete was executed
            mock_db_session.execute.assert_called_once()

    async def test_restore_table_continues_on_record_error(
        self, mock_db_session, tmp_path, sample_camera_data
    ):
        """Test restore continues when individual record fails."""
        cameras_file = tmp_path / "cameras.json"
        cameras_file.write_text(json.dumps(sample_camera_data))

        service = RestoreService()

        # Use real Camera model and mock the model instantiation by making it fail
        from backend.models.camera import Camera

        # Track calls to model constructor
        call_count = 0
        original_init = Camera.__init__

        def mock_init(self, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ValueError("Invalid data")
            # Call original for first record
            original_init(self, **kwargs)

        with patch.object(service, "_get_model_class", return_value=Camera):
            with patch.object(Camera, "__init__", mock_init):
                count = await service._restore_table(mock_db_session, "cameras", cameras_file)

                # Only first record should be added (second failed)
                assert count == 1
                assert mock_db_session.add.call_count == 1


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

        with patch.object(service, "_get_model_class", return_value=Camera):
            result = await service.restore_from_backup(
                backup_file=backup_file,
                db=mock_db_session,
                job_id="job-123",
            )

            assert isinstance(result, RestoreResult)
            assert result.backup_id == "backup-123"
            assert result.total_items == 2
            assert "cameras" in result.items_restored
            mock_db_session.commit.assert_called_once()

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

        with patch.object(service, "_get_model_class", return_value=Camera):
            with pytest.raises(RestoreError, match="Restore failed"):
                await service.restore_from_backup(
                    backup_file=backup_file,
                    db=mock_db_session,
                    job_id="job-123",
                )

            mock_db_session.rollback.assert_called_once()
            mock_db_session.commit.assert_not_called()

    async def test_restore_from_backup_skips_missing_table_files(
        self, mock_db_session, tmp_path, sample_manifest
    ):
        """Test restore skips tables without backup files."""
        backup_file = tmp_path / "backup.zip"

        with zipfile.ZipFile(backup_file, "w") as zf:
            zf.writestr("manifest.json", json.dumps(sample_manifest))
            # Don't write cameras.json or events.json

        service = RestoreService()

        result = await service.restore_from_backup(
            backup_file=backup_file,
            db=mock_db_session,
            job_id="job-123",
        )

        assert result.total_items == 0
        assert len(result.items_restored) == 0

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

        with patch.object(service, "_restore_table", side_effect=track_restore_order):
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
        """Test table order includes required tables."""
        assert "cameras" in RESTORE_TABLE_ORDER
        assert "zones" in RESTORE_TABLE_ORDER
        assert "events" in RESTORE_TABLE_ORDER
        assert "alerts" in RESTORE_TABLE_ORDER

    def test_restore_table_order_cameras_before_zones(self):
        """Test cameras come before zones (FK dependency)."""
        cameras_idx = RESTORE_TABLE_ORDER.index("cameras")
        zones_idx = RESTORE_TABLE_ORDER.index("zones")
        assert cameras_idx < zones_idx

    def test_restore_table_order_cameras_before_events(self):
        """Test cameras come before events (FK dependency)."""
        cameras_idx = RESTORE_TABLE_ORDER.index("cameras")
        events_idx = RESTORE_TABLE_ORDER.index("events")
        assert cameras_idx < events_idx


class TestRestoreServiceExceptions:
    """Test custom exception classes."""

    def test_backup_validation_error_is_exception(self):
        """Test BackupValidationError is an Exception."""
        error = BackupValidationError("test")
        assert isinstance(error, Exception)

    def test_backup_corrupted_error_is_exception(self):
        """Test BackupCorruptedError is an Exception."""
        error = BackupCorruptedError("test")
        assert isinstance(error, Exception)

    def test_restore_error_is_exception(self):
        """Test RestoreError is an Exception."""
        error = RestoreError("test")
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
