"""Integration tests for RestoreService (B4.6 / 4n-restore.md)."""

from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from backend.models.alert import AlertRule
from backend.models.area import Area, camera_areas
from backend.models.baseline import ActivityBaseline, ClassBaseline
from backend.models.camera import Camera
from backend.models.camera_zone import CameraZone
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.face_identity import KnownPerson
from backend.models.gpu_config import SystemSetting
from backend.models.household import HouseholdMember, MemberRole, TrustLevel
from backend.models.household_org import Household
from backend.models.prompt_version import PromptVersion
from backend.models.property import Property
from backend.services.backup_service import (
    INSTALLATION_ID_SETTING_KEY,
    BackupService,
    get_or_create_installation_id,
    reset_backup_service,
)
from backend.services.restore_service import (
    BackupValidationError,
    RestoreError,
    RestoreService,
    reset_restore_service,
)
from backend.tests.conftest import unique_id

pytestmark = [pytest.mark.integration]


@pytest.fixture
def restore_service() -> RestoreService:
    """Create a RestoreService instance."""
    reset_restore_service()
    return RestoreService()


@pytest.fixture
def backup_service(tmp_path: Path) -> BackupService:
    """Create a BackupService instance with a temporary backup directory."""
    reset_backup_service()
    return BackupService(backup_dir=tmp_path)


@pytest.fixture
async def backup_file(test_db, backup_service: BackupService) -> Path:
    """Create a test backup file and return its path."""
    camera_id = unique_id("restore_test_cam")
    async with test_db() as session:
        camera = Camera(
            id=camera_id,
            name=f"Restore Test Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.commit()

        result = await backup_service.create_backup(session, unique_id("restore_test"))
        await session.commit()

    return result.file_path


class TestRestoreServiceRestore:
    """Tests for RestoreService.restore_from_backup()."""

    @pytest.mark.asyncio
    async def test_restores_from_valid_backup(
        self,
        test_db,
        restore_service: RestoreService,
        backup_file: Path,
    ) -> None:
        """Test that restore works with a valid backup file."""
        async with test_db() as session:
            result = await restore_service.restore_from_backup(
                backup_file,
                session,
                unique_id("restore_job"),
            )
            await session.commit()

        assert result.backup_id is not None
        assert result.total_items >= 1
        assert isinstance(result.items_restored, dict)

    @pytest.mark.asyncio
    async def test_progress_callback_called(
        self,
        test_db,
        restore_service: RestoreService,
        backup_file: Path,
    ) -> None:
        """Test that progress callback is invoked during restore."""
        progress_updates: list[tuple[int, str]] = []

        async def progress_callback(percent: int, step: str) -> None:
            progress_updates.append((percent, step))

        async with test_db() as session:
            await restore_service.restore_from_backup(
                backup_file,
                session,
                unique_id("restore_job"),
                progress_callback,
            )
            await session.commit()

        assert len(progress_updates) > 0
        steps = [step for _, step in progress_updates]
        assert any("Extracting" in s for s in steps)

    @pytest.mark.asyncio
    async def test_restore_result_contains_item_counts(
        self,
        test_db,
        restore_service: RestoreService,
        backup_file: Path,
    ) -> None:
        """Test that restore result includes per-table item counts."""
        async with test_db() as session:
            result = await restore_service.restore_from_backup(
                backup_file,
                session,
                unique_id("restore_job"),
            )
            await session.commit()

        assert isinstance(result.items_restored, dict)
        assert result.total_items == sum(result.items_restored.values())


class TestRestoreServiceIntegration:
    """End-to-end integration tests for B4.6 / 4n-restore.md requirements."""

    @pytest.mark.asyncio
    async def test_restoring_into_db_with_events_keeps_every_event_and_detection(
        self,
        test_db,
        backup_service: BackupService,
        restore_service: RestoreService,
    ) -> None:
        """Restoring into a database that holds events leaves every event and detection in place."""
        cam_id = unique_id("evt_cam")
        async with test_db() as session:
            cam = Camera(
                id=cam_id,
                name=f"Original {cam_id[-6:]}",
                folder_path=f"/export/foscam/{cam_id}",
            )
            session.add(cam)
            await session.commit()

            backup_res = await backup_service.create_backup(session, unique_id("bk_before_events"))
            await session.commit()

            # Now rename camera and add events + detections after the backup was taken
            cam.name = f"Renamed {cam_id[-6:]}"
            det = Detection(
                camera_id=cam_id,
                file_path=f"/export/foscam/{cam_id}/snap1.jpg",
                detected_at=datetime.now(UTC),
                object_type="person",
                confidence=0.92,
            )
            evt = Event(
                batch_id=unique_id("batch"),
                camera_id=cam_id,
                started_at=datetime.now(UTC),
                risk_score=65,
                summary="Post-backup event must survive restore",
            )
            session.add_all([det, evt])
            await session.commit()
            det_id = det.id
            evt_id = evt.id

        async with test_db() as session:
            await restore_service.restore_from_backup(backup_res.file_path, session)
            await session.commit()

        async with test_db() as session:
            restored_cam = (
                await session.execute(select(Camera).where(Camera.id == cam_id))
            ).scalar_one()
            assert restored_cam.name == f"Original {cam_id[-6:]}"

            surviving_evt = (
                await session.execute(select(Event).where(Event.id == evt_id))
            ).scalar_one_or_none()
            surviving_det = (
                await session.execute(select(Detection).where(Detection.id == det_id))
            ).scalar_one_or_none()
            assert surviving_evt is not None
            assert surviving_det is not None

    @pytest.mark.asyncio
    async def test_restore_into_empty_database_succeeds_parents_first(
        self,
        test_db,
        backup_service: BackupService,
        restore_service: RestoreService,
    ) -> None:
        """Restoring into an empty database succeeds, restoring parent tables before children."""
        cam_id = unique_id("hier_cam")
        zone_id = str(uuid4())
        rule_id = str(uuid4())

        async with test_db() as session:
            hh = Household(name="Svoboda Household")
            session.add(hh)
            await session.flush()

            prop = Property(household_id=hh.id, name="Main Residence", timezone="UTC")
            session.add(prop)
            await session.flush()

            area = Area(property_id=prop.id, name="Front Driveway", color="#76B900")
            cam = Camera(
                id=cam_id,
                name=f"Hierarchy Camera {cam_id[-6:]}",
                folder_path=f"/export/foscam/{cam_id}",
                property_id=prop.id,
            )
            session.add_all([area, cam])
            await session.flush()

            await session.execute(camera_areas.insert().values(camera_id=cam_id, area_id=area.id))
            session.add_all(
                [
                    CameraZone(
                        id=zone_id,
                        camera_id=cam_id,
                        name="Entry Polygon",
                        coordinates=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
                    ),
                    ActivityBaseline(
                        camera_id=cam_id, hour=10, day_of_week=2, avg_count=3.5, sample_count=10
                    ),
                    ClassBaseline(
                        camera_id=cam_id,
                        detection_class="person",
                        hour=10,
                        frequency=0.75,
                        sample_count=8,
                    ),
                    HouseholdMember(
                        household_id=hh.id,
                        name="Mike",
                        role=MemberRole.RESIDENT,
                        trusted_level=TrustLevel.FULL,
                    ),
                    PromptVersion(
                        model="nemotron",
                        version=1,
                        config_json='{"system_prompt": "v1"}',
                        is_active=True,
                    ),
                    AlertRule(id=rule_id, name="High Risk Rule", risk_threshold=75),
                ]
            )
            await session.commit()

            backup_res = await backup_service.create_backup(session, unique_id("full_hier_bk"))
            await session.commit()

            # Wipe all configuration tables in child-first order to make DB empty
            await session.execute(delete(AlertRule))
            await session.execute(delete(PromptVersion))
            await session.execute(delete(HouseholdMember))
            await session.execute(delete(ClassBaseline))
            await session.execute(delete(ActivityBaseline))
            await session.execute(delete(CameraZone))
            await session.execute(camera_areas.delete())
            await session.execute(delete(Camera))
            await session.execute(delete(Area))
            await session.execute(delete(Property))
            await session.execute(delete(Household))
            await session.commit()

        # Restore into the empty database
        async with test_db() as session:
            restore_res = await restore_service.restore_from_backup(backup_res.file_path, session)
            await session.commit()

        assert restore_res.tables["households"].inserted == 1
        assert restore_res.tables["properties"].inserted == 1
        assert restore_res.tables["areas"].inserted == 1
        assert restore_res.tables["cameras"].inserted == 1
        assert restore_res.tables["camera_areas"].inserted == 1
        assert restore_res.tables["zones"].inserted == 1
        assert restore_res.tables["activity_baselines"].replaced == 1
        assert restore_res.tables["class_baselines"].replaced == 1
        assert restore_res.tables["household_members"].inserted == 1
        assert restore_res.tables["prompt_versions"].inserted == 1
        assert restore_res.tables["alert_rules"].inserted == 1

    @pytest.mark.asyncio
    async def test_camera_merge_kept_reporting_and_baseline_replacement_scoping(
        self,
        test_db,
        backup_service: BackupService,
        restore_service: RestoreService,
    ) -> None:
        """A camera in the backup overwrites the current one; a camera not in the backup is kept
        and reported; baselines are replaced for the archive's cameras only."""
        cam_in_bk = unique_id("cam_in_bk")
        cam_local_only = unique_id("cam_local")

        async with test_db() as session:
            session.add(
                Camera(
                    id=cam_in_bk,
                    name=f"Backup Name {cam_in_bk[-6:]}",
                    folder_path=f"/export/foscam/{cam_in_bk}",
                )
            )
            session.add(
                ActivityBaseline(
                    camera_id=cam_in_bk, hour=8, day_of_week=1, avg_count=5.0, sample_count=20
                )
            )
            await session.commit()

            backup_res = await backup_service.create_backup(session, unique_id("cam_merge_bk"))
            await session.commit()

            # Mutate cam_in_bk, change its baseline, and add a second camera not in the backup
            cam_row = (
                await session.execute(select(Camera).where(Camera.id == cam_in_bk))
            ).scalar_one()
            cam_row.name = f"Mutated Name {cam_in_bk[-6:]}"

            bl_row = (
                await session.execute(
                    select(ActivityBaseline).where(ActivityBaseline.camera_id == cam_in_bk)
                )
            ).scalar_one()
            bl_row.avg_count = 99.0
            session.add(
                ActivityBaseline(
                    camera_id=cam_in_bk, hour=9, day_of_week=1, avg_count=42.0, sample_count=5
                )
            )

            session.add(
                Camera(
                    id=cam_local_only,
                    name=f"Local Only {cam_local_only[-6:]}",
                    folder_path=f"/export/foscam/{cam_local_only}",
                )
            )
            session.add(
                ActivityBaseline(
                    camera_id=cam_local_only,
                    hour=12,
                    day_of_week=3,
                    avg_count=7.0,
                    sample_count=15,
                )
            )
            await session.commit()

        async with test_db() as session:
            res = await restore_service.restore_from_backup(backup_res.file_path, session)
            await session.commit()

        assert res.tables["cameras"].updated == 1
        assert res.tables["cameras"].kept == 1
        assert res.tables["activity_baselines"].replaced == 1
        assert res.tables["activity_baselines"].kept == 1

        async with test_db() as session:
            c1 = (await session.execute(select(Camera).where(Camera.id == cam_in_bk))).scalar_one()
            c2 = (
                await session.execute(select(Camera).where(Camera.id == cam_local_only))
            ).scalar_one()
            assert c1.name == f"Backup Name {cam_in_bk[-6:]}"
            assert c2.name == f"Local Only {cam_local_only[-6:]}"

            b1 = (
                (
                    await session.execute(
                        select(ActivityBaseline).where(ActivityBaseline.camera_id == cam_in_bk)
                    )
                )
                .scalars()
                .all()
            )
            assert len(b1) == 1
            assert b1[0].hour == 8
            assert b1[0].avg_count == 5.0

            b2 = (
                (
                    await session.execute(
                        select(ActivityBaseline).where(ActivityBaseline.camera_id == cam_local_only)
                    )
                )
                .scalars()
                .all()
            )
            assert len(b2) == 1
            assert b2[0].avg_count == 7.0

    @pytest.mark.asyncio
    async def test_foreign_installation_inserts_members_with_new_ids_and_clears_known_person(
        self,
        test_db,
        backup_service: BackupService,
        restore_service: RestoreService,
    ) -> None:
        """An archive from another installation inserts its members with new IDs and never
        overwrites a local one; a member's known-person link is cleared and reported;
        after restore, inserting a new member or baseline does not fail on a duplicate key."""
        async with test_db() as session:
            kp = KnownPerson(name="Enrolled Person", is_household_member=True)
            hh = Household(name="Shared Family Name")
            session.add_all([kp, hh])
            await session.flush()

            foreign_member = HouseholdMember(
                household_id=hh.id,
                name="Foreign Member",
                role=MemberRole.RESIDENT,
                trusted_level=TrustLevel.FULL,
                known_person_id=kp.id,
            )
            session.add(foreign_member)
            await session.commit()
            foreign_member_id = foreign_member.id

            backup_res = await backup_service.create_backup(session, unique_id("foreign_bk"))
            await session.commit()

            # Simulate restoring onto a DIFFERENT installation that has a local member with the same ID
            setting = (
                await session.execute(
                    select(SystemSetting).where(SystemSetting.key == INSTALLATION_ID_SETTING_KEY)
                )
            ).scalar_one()
            setting.value = {"installation_id": str(uuid4())}
            local_install_id = setting.value["installation_id"]
            foreign_member.name = "Local Member At Same ID"
            await session.commit()

        async with test_db() as session:
            res = await restore_service.restore_from_backup(backup_res.file_path, session)
            await session.commit()

        assert res.same_installation is False
        assert res.tables["household_members"].inserted == 1
        assert res.tables["household_members"].kept == 1
        assert "Foreign Member" in res.added_rows.get("household_members", [])
        assert "Foreign Member" in res.cleared_known_person_links

        async with test_db() as session:
            # Local installation_id is never overwritten by restore
            assert await get_or_create_installation_id(session) == local_install_id

            members = (
                (await session.execute(select(HouseholdMember).order_by(HouseholdMember.id)))
                .scalars()
                .all()
            )
            assert len(members) == 2
            local_m = next(m for m in members if m.id == foreign_member_id)
            inserted_m = next(m for m in members if m.id != foreign_member_id)
            assert local_m.name == "Local Member At Same ID"
            assert local_m.known_person_id is not None
            assert inserted_m.name == "Foreign Member"
            assert inserted_m.known_person_id is None

            # Sequence setval check: inserting another member without explicit ID succeeds
            new_member = HouseholdMember(
                name="Post Restore Member",
                role=MemberRole.FAMILY,
                trusted_level=TrustLevel.PARTIAL,
            )
            session.add(new_member)
            await session.commit()
            assert new_member.id > inserted_m.id

    @pytest.mark.asyncio
    async def test_unknown_table_or_bad_record_changes_nothing_and_names_detail(
        self,
        test_db,
        restore_service: RestoreService,
        tmp_path: Path,
    ) -> None:
        """A backup with an unknown table or a bad record changes nothing and fails with detail."""
        cam_id = unique_id("untouched_cam")
        async with test_db() as session:
            session.add(
                Camera(
                    id=cam_id,
                    name="Untouched Camera",
                    folder_path=f"/export/foscam/{cam_id}",
                )
            )
            await session.commit()

        # 1. Unknown table in manifest
        unknown_payload = "[]"
        unknown_manifest = {
            "backup_id": "bad-table-bk",
            "version": "1.1",
            "created_at": datetime.now(UTC).isoformat(),
            "contents": {
                "mystery_table": {
                    "count": 0,
                    "checksum": hashlib.sha256(unknown_payload.encode()).hexdigest(),
                }
            },
        }
        unknown_zip = tmp_path / "unknown_table.zip"
        with zipfile.ZipFile(unknown_zip, "w") as zf:
            zf.writestr("manifest.json", json.dumps(unknown_manifest))
            zf.writestr("mystery_table.json", unknown_payload)

        async with test_db() as session:
            with pytest.raises(
                BackupValidationError, match="Unrecognised table in backup manifest: mystery_table"
            ) as exc_info:
                await restore_service.restore_from_backup(unknown_zip, session)
            assert exc_info.value.table == "mystery_table"

        # 2. Bad record in alert_rules after modifying cameras in the same archive
        cameras_payload = json.dumps(
            [
                {
                    "id": cam_id,
                    "name": "Should Roll Back",
                    "folder_path": f"/export/foscam/{cam_id}",
                    "status": "online",
                }
            ]
        )
        bad_rules_payload = json.dumps(
            [{"id": str(uuid4()), "name": "Bad Rule", "nonexistent_col": 123}]
        )
        bad_record_manifest = {
            "backup_id": "bad-record-bk",
            "version": "1.1",
            "created_at": datetime.now(UTC).isoformat(),
            "contents": {
                "cameras": {
                    "count": 1,
                    "checksum": hashlib.sha256(cameras_payload.encode()).hexdigest(),
                },
                "alert_rules": {
                    "count": 1,
                    "checksum": hashlib.sha256(bad_rules_payload.encode()).hexdigest(),
                },
            },
        }
        bad_record_zip = tmp_path / "bad_record.zip"
        with zipfile.ZipFile(bad_record_zip, "w") as zf:
            zf.writestr("manifest.json", json.dumps(bad_record_manifest))
            zf.writestr("cameras.json", cameras_payload)
            zf.writestr("alert_rules.json", bad_rules_payload)

        async with test_db() as session:
            with pytest.raises(
                RestoreError,
                match=r"Unknown column\(s\) \['nonexistent_col'\] in table 'alert_rules' at record 0",
            ) as exc_info:
                await restore_service.restore_from_backup(bad_record_zip, session)
            assert exc_info.value.table == "alert_rules"
            assert exc_info.value.record_index == 0

        # Verify camera name in DB is still 'Untouched Camera'
        async with test_db() as session:
            cam_after = (
                await session.execute(select(Camera).where(Camera.id == cam_id))
            ).scalar_one()
            assert cam_after.name == "Untouched Camera"
