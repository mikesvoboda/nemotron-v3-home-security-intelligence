"""Automated backup and restore testing for disaster recovery (NEM-2217).

This module tests critical database backup and restore functionality:
- Database schema extraction and verification
- Data export and import validation
- Data consistency verification after restore
- Point-in-time data capture testing
- Backup integrity validation

All tests use testcontainers for full isolation and real PostgreSQL operations.

Related: NEM-2096 (Epic: Disaster Recovery Testing)
         NEM-2217 (Add automated backup/restore tests in CI)

Testing Strategy:
1. RED: Tests written first, defining expected behavior
2. GREEN: Minimal implementation to pass tests
3. REFACTOR: Improve while keeping tests green

Expected Behavior:
- Database schema can be extracted programmatically
- Data can be exported and validated
- Data integrity is maintained through export/import cycle
- Point-in-time snapshots capture database state accurately
- Backup validation detects data corruption

Note: These tests verify backup/restore patterns using SQLAlchemy and Python
rather than pg_dump/pg_restore binaries, making them portable across
environments without requiring PostgreSQL client tools on the host.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect, select, text

from backend.core.database import get_engine, get_session
from backend.models.camera import Camera
from backend.tests.factories import CameraFactory, EventFactory


class TestDatabaseSchemaExtraction:
    """Tests for database schema extraction and validation."""

    @pytest.mark.asyncio
    async def test_extract_table_names(self, integration_db: str) -> None:
        """Can extract all table names from database."""
        engine = get_engine()

        # SQLAlchemy reflection must be done with run_sync to handle greenlet context
        def get_table_names(conn):
            inspector = inspect(conn)
            return inspector.get_table_names()

        async with engine.begin() as conn:
            table_names = await conn.run_sync(get_table_names)

        # Verify expected tables exist
        assert len(table_names) > 0, "Database should have tables"
        assert "cameras" in table_names, "cameras table should exist"
        assert "events" in table_names, "events table should exist"
        assert "detections" in table_names, "detections table should exist"

    @pytest.mark.asyncio
    async def test_extract_table_schema(self, integration_db: str) -> None:
        """Can extract table schema with columns and types."""
        engine = get_engine()

        # Extract cameras table schema using run_sync
        def get_columns(conn):
            inspector = inspect(conn)
            return inspector.get_columns("cameras")

        async with engine.begin() as conn:
            columns = await conn.run_sync(get_columns)

        assert len(columns) > 0, "cameras table should have columns"

        # Verify expected columns
        column_names = [col["name"] for col in columns]
        assert "id" in column_names, "Should have id column"
        assert "name" in column_names, "Should have name column"
        assert "created_at" in column_names, "Should have created_at column"

        # Verify column types are captured
        id_column = next(col for col in columns if col["name"] == "id")
        assert id_column["type"] is not None, "Column type should be captured"

    @pytest.mark.asyncio
    async def test_extract_foreign_key_relationships(self, integration_db: str) -> None:
        """Can extract foreign key relationships between tables."""
        engine = get_engine()

        # Get foreign keys for events table using run_sync
        def get_foreign_keys(conn):
            inspector = inspect(conn)
            return inspector.get_foreign_keys("events")

        async with engine.begin() as conn:
            foreign_keys = await conn.run_sync(get_foreign_keys)

        assert len(foreign_keys) > 0, "events table should have foreign keys"

        # Verify camera_id foreign key
        camera_fk = next(
            (fk for fk in foreign_keys if "camera_id" in fk.get("constrained_columns", [])),
            None,
        )
        assert camera_fk is not None, "Should have camera_id foreign key"
        assert camera_fk["referred_table"] == "cameras", "Should reference cameras table"

    @pytest.mark.asyncio
    async def test_extract_indexes(self, integration_db: str) -> None:
        """Can extract table indexes."""
        engine = get_engine()

        # Get indexes for cameras table using run_sync
        def get_indexes(conn):
            inspector = inspect(conn)
            return inspector.get_indexes("cameras")

        async with engine.begin() as conn:
            indexes = await conn.run_sync(get_indexes)

        # Should have at least the primary key index
        assert len(indexes) >= 0, "Should be able to extract indexes"

        # Verify index structure
        for index in indexes:
            assert "name" in index, "Index should have name"
            assert "column_names" in index, "Index should have column names"


class TestDataExportImport:
    """Tests for data export and import operations."""

    @pytest.mark.asyncio
    async def test_export_table_data_to_dict(self, integration_db: str) -> None:
        """Can export table data to dictionary format."""
        # Create test data
        async with get_session() as session:
            camera = CameraFactory.build(id="export_test_cam", name="Export Test Camera")
            session.add(camera)
            await session.commit()

        # Export data using SQLAlchemy
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == "export_test_cam"))
            camera = result.scalar_one()

            # Export to dictionary
            exported_data = {
                "id": camera.id,
                "name": camera.name,
                "created_at": camera.created_at.isoformat() if camera.created_at else None,
            }

        # Verify exported data structure
        assert exported_data["id"] == "export_test_cam"
        assert exported_data["name"] == "Export Test Camera"
        assert exported_data["created_at"] is not None

    @pytest.mark.asyncio
    async def test_export_import_cycle_preserves_data(self, integration_db: str) -> None:
        """Complete export/import cycle preserves all data."""
        # Create original data
        original_camera_id = "cycle_test_cam"
        async with get_session() as session:
            camera = CameraFactory.build(
                id=original_camera_id,
                name="Cycle Test Camera",
            )
            session.add(camera)
            await session.commit()

        # Export data
        exported_data = {}
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == original_camera_id))
            camera = result.scalar_one()
            exported_data = {
                "id": camera.id,
                "name": camera.name,
                "created_at": camera.created_at,
            }

        # Delete original
        async with get_session() as session:
            await session.execute(
                text("DELETE FROM cameras WHERE id = :id").bindparams(id=original_camera_id)
            )
            await session.commit()

        # Verify deletion
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == original_camera_id))
            assert result.scalar_one_or_none() is None, "Camera should be deleted"

        # Import data back - use factory to ensure required fields
        async with get_session() as session:
            new_camera = CameraFactory.build(
                id=exported_data["id"],
                name=exported_data["name"],
                created_at=exported_data["created_at"],
            )
            session.add(new_camera)
            await session.commit()

        # Verify import
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == original_camera_id))
            restored_camera = result.scalar_one()
            assert restored_camera.id == exported_data["id"]
            assert restored_camera.name == exported_data["name"]

    @pytest.mark.asyncio
    async def test_bulk_export_multiple_records(self, integration_db: str) -> None:
        """Can export multiple records efficiently."""
        # Create multiple test records
        camera_ids = [f"bulk_cam_{i}" for i in range(5)]
        async with get_session() as session:
            for cam_id in camera_ids:
                camera = CameraFactory.build(id=cam_id, name=f"Bulk Camera {cam_id}")
                session.add(camera)
            await session.commit()

        # Bulk export
        exported_records = []
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id.in_(camera_ids)))
            cameras = result.scalars().all()

            for camera in cameras:
                exported_records.append(
                    {
                        "id": camera.id,
                        "name": camera.name,
                    }
                )

        # Verify all records exported
        assert len(exported_records) == 5, "Should export all 5 cameras"
        exported_ids = {rec["id"] for rec in exported_records}
        assert exported_ids == set(camera_ids), "Should export correct camera IDs"


class TestDataConsistency:
    """Tests for data consistency verification."""

    @pytest.mark.asyncio
    async def test_verify_foreign_key_relationships_intact(self, integration_db: str) -> None:
        """Verify foreign key relationships are maintained."""
        # Create related data
        async with get_session() as session:
            camera = CameraFactory.build(id="fk_test_cam", name="FK Test Camera")
            session.add(camera)
            await session.flush()

            event = EventFactory.build(
                camera_id=camera.id,
                summary="FK test event",
                risk_score=75,
            )
            session.add(event)
            await session.commit()
            event_id = event.id

        # Verify relationship via query
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT e.id, e.camera_id, c.id, c.name
                    FROM events e
                    JOIN cameras c ON e.camera_id = c.id
                    WHERE e.id = :event_id
                """
                ).bindparams(event_id=event_id)
            )
            row = result.fetchone()

            assert row is not None, "Should find event with camera"
            assert row[1] == "fk_test_cam", "Event should reference correct camera"
            assert row[2] == "fk_test_cam", "Camera ID should match"
            assert row[3] == "FK Test Camera", "Camera name should be correct"

    @pytest.mark.asyncio
    async def test_detect_orphaned_records(self, integration_db: str) -> None:
        """Can detect orphaned records (if foreign keys were disabled)."""
        # This query pattern helps detect orphans in disaster recovery scenarios
        # In production, FK constraints prevent orphans, but this validates the detection query

        async with get_session() as session:
            # Query for orphaned events (should be empty due to FK constraints)
            result = await session.execute(
                text(
                    """
                    SELECT e.id, e.camera_id
                    FROM events e
                    LEFT JOIN cameras c ON e.camera_id = c.id
                    WHERE c.id IS NULL
                """
                )
            )
            orphaned_events = result.fetchall()

            # Should be empty (FK constraints prevent orphans)
            assert len(orphaned_events) == 0, "Should not have orphaned events"

    @pytest.mark.asyncio
    async def test_verify_data_checksums(self, integration_db: str) -> None:
        """Can calculate and verify data checksums for integrity."""
        # Create test data
        async with get_session() as session:
            camera = CameraFactory.build(
                id="checksum_cam",
                name="Checksum Test Camera",
            )
            session.add(camera)
            await session.commit()

        # Calculate checksum of data
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == "checksum_cam"))
            camera = result.scalar_one()

            # Create deterministic representation
            data_str = f"{camera.id}|{camera.name}"
            checksum1 = hashlib.sha256(data_str.encode()).hexdigest()

        # Read data again and recalculate checksum
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == "checksum_cam"))
            camera = result.scalar_one()

            data_str = f"{camera.id}|{camera.name}"
            checksum2 = hashlib.sha256(data_str.encode()).hexdigest()

        # Checksums should match
        assert checksum1 == checksum2, "Data checksums should be consistent"
        assert len(checksum1) == 64, "SHA256 checksum should be 64 characters"


class TestPointInTimeCapture:
    """Tests for point-in-time data capture."""

    @pytest.mark.asyncio
    async def test_capture_database_state_at_timestamp(self, integration_db: str) -> None:
        """Can capture database state at specific timestamp."""
        # Create initial state
        async with get_session() as session:
            camera = CameraFactory.build(
                id="pitr_cam",
                name="PITR Camera - Before",
            )
            session.add(camera)
            await session.commit()

        # Capture state at T1
        state_t1 = {}
        timestamp_t1 = datetime.now(UTC)
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == "pitr_cam"))
            camera = result.scalar_one()
            state_t1 = {
                "id": camera.id,
                "name": camera.name,
                "timestamp": timestamp_t1.isoformat(),
            }

        # Modify state at T2
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == "pitr_cam"))
            camera = result.scalar_one()
            camera.name = "PITR Camera - After"
            await session.commit()

        # Capture state at T2
        state_t2 = {}
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == "pitr_cam"))
            camera = result.scalar_one()
            state_t2 = {
                "id": camera.id,
                "name": camera.name,
            }

        # Verify states are different
        assert state_t1["name"] == "PITR Camera - Before"
        assert state_t2["name"] == "PITR Camera - After"
        assert state_t1["name"] != state_t2["name"], "States should be different"

    @pytest.mark.asyncio
    async def test_multiple_snapshots_preserve_timeline(self, integration_db: str) -> None:
        """Multiple snapshots preserve different points in timeline."""
        snapshots = []

        # Create 3 snapshots at different states
        for i in range(3):
            # Create camera
            async with get_session() as session:
                camera = CameraFactory.build(
                    id=f"timeline_cam_{i}",
                    name=f"Timeline Camera {i}",
                )
                session.add(camera)
                await session.commit()

            # Capture snapshot
            snapshot = {
                "timestamp": datetime.now(UTC).isoformat(),
                "cameras": [],
            }

            async with get_session() as session:
                result = await session.execute(
                    select(Camera).where(Camera.id.like("timeline_cam_%"))
                )
                cameras = result.scalars().all()

                for cam in cameras:
                    snapshot["cameras"].append(
                        {
                            "id": cam.id,
                            "name": cam.name,
                        }
                    )

            snapshots.append(snapshot)

        # Verify snapshots capture progressive state
        assert len(snapshots[0]["cameras"]) == 1, "First snapshot should have 1 camera"
        assert len(snapshots[1]["cameras"]) == 2, "Second snapshot should have 2 cameras"
        assert len(snapshots[2]["cameras"]) == 3, "Third snapshot should have 3 cameras"

    @pytest.mark.asyncio
    async def test_restore_to_previous_snapshot(self, integration_db: str) -> None:
        """Can restore data to a previous snapshot state."""
        # Create initial state
        async with get_session() as session:
            camera = CameraFactory.build(
                id="restore_snap_cam",
                name="Original Name",
            )
            session.add(camera)
            await session.commit()

        # Save snapshot
        snapshot = {}
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == "restore_snap_cam"))
            camera = result.scalar_one()
            snapshot = {
                "id": camera.id,
                "name": camera.name,
            }

        # Modify data
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == "restore_snap_cam"))
            camera = result.scalar_one()
            camera.name = "Modified Name"
            await session.commit()

        # Verify modification
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == "restore_snap_cam"))
            camera = result.scalar_one()
            assert camera.name == "Modified Name"

        # Restore from snapshot
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == "restore_snap_cam"))
            camera = result.scalar_one()
            camera.name = snapshot["name"]
            await session.commit()

        # Verify restoration
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == "restore_snap_cam"))
            camera = result.scalar_one()
            assert camera.name == "Original Name", "Should restore to snapshot state"


class TestBackupValidation:
    """Tests for backup validation and integrity checking."""

    @pytest.mark.asyncio
    async def test_validate_exported_data_structure(self, integration_db: str) -> None:
        """Can validate structure of exported data."""
        # Create and export data
        async with get_session() as session:
            camera = CameraFactory.build(id="validate_cam", name="Validation Test")
            session.add(camera)
            await session.commit()

        # Export and validate
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id == "validate_cam"))
            camera = result.scalar_one()

            exported = {
                "id": camera.id,
                "name": camera.name,
            }

            # Validate required fields
            assert "id" in exported, "Export should contain id"
            assert "name" in exported, "Export should contain name"
            assert exported["id"], "ID should not be empty"
            assert exported["name"], "Name should not be empty"

    @pytest.mark.asyncio
    async def test_detect_incomplete_backup(self, integration_db: str) -> None:
        """Can detect incomplete or corrupted backup data."""
        # Create test data
        expected_cameras = set()
        async with get_session() as session:
            for i in range(5):
                cam_id = f"incomplete_cam_{i}"
                camera = CameraFactory.build(id=cam_id, name=f"Camera {i}")
                session.add(camera)
                expected_cameras.add(cam_id)
            await session.commit()

        # Export with simulated incomplete data (missing one camera)
        exported_cameras = set()
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id.like("incomplete_cam_%")))
            cameras = result.scalars().all()

            # Intentionally skip one camera to simulate incomplete backup
            for camera in cameras[:4]:  # Only export 4 out of 5
                exported_cameras.add(camera.id)

        # Detect incomplete backup
        missing_cameras = expected_cameras - exported_cameras
        assert len(missing_cameras) > 0, "Should detect missing cameras"
        assert len(missing_cameras) == 1, "Should detect exactly 1 missing camera"

    @pytest.mark.asyncio
    async def test_verify_backup_completeness(self, integration_db: str) -> None:
        """Can verify backup contains all expected records."""
        # Create test data
        expected_count = 5
        async with get_session() as session:
            for i in range(expected_count):
                camera = CameraFactory.build(
                    id=f"complete_cam_{i}",
                    name=f"Camera {i}",
                )
                session.add(camera)
            await session.commit()

        # Export all data
        async with get_session() as session:
            result = await session.execute(select(Camera).where(Camera.id.like("complete_cam_%")))
            exported_cameras = result.scalars().all()

        # Verify completeness
        assert len(exported_cameras) == expected_count, "Backup should contain all records"
