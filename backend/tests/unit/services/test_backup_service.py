"""WP3.1 first tests for backend.services.backup_service.

Mutation history: no_tests (2 mutants never even measured). The service's
DB surface is faked at its narrowest seam (db.execute -> .scalars().all()),
so the ZIP/manifest/checksum/retention logic — the part that carries the
integrity promise — is asserted for real:

  * manifest to_dict/from_dict round trip (isoformat datetime, contents map)
  * _export_table: mapper column extraction, datetime->isoformat,
    bytes->base64, Enum->value, JSON on disk, count returned
  * _calculate_checksum: equals hashlib over the same bytes; missing file
    raises FileNotFoundError (the pre-read validation, not an open() OSError)
  * create_backup end to end on a real tmp dir: filename pattern, ZIP member
    set, manifest checksum equals sha256 of the empty-JSON body, exact
    progress-step sequence, file_size == stat
  * list_backups: newest-first, non-ZIP junk skipped without killing the list
  * delete/get_by_id/cleanup_old_backups: age cutoff AND count overflow,
    with exact deleted counts
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import DateTime, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.time_utils import utc_now
from backend.models.camera import Base
from backend.services.backup_service import (
    BackupManifest,
    BackupService,
    get_backup_service,
    reset_backup_service,
)


class Color(StrEnum):
    RED = "red"


class ExportProbe(Base):
    """Throwaway mapper so _export_table's real column introspection runs."""

    __tablename__ = "wp31_export_probe"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(default="x")
    when: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    blob: Mapped[bytes | None] = mapped_column(LargeBinary, default=None)


class FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return FakeScalars(self._rows)


class FakeDB:
    """execute() answers for EVERY model with the given rows."""

    def __init__(self, rows=None):
        self.rows = rows or []
        self.queries = 0

    async def execute(self, stmt):
        self.queries += 1
        return FakeResult(self.rows)


def _service(tmp_path: Path) -> BackupService:
    return BackupService(backup_dir=tmp_path / "bk")


def _write_backup(
    svc: BackupService,
    backup_id: str,
    created_at: datetime,
    *,
    junk: bool = False,
) -> Path:
    ts = created_at.strftime("%Y%m%d_%H%M%S")
    path = svc._backup_dir / f"backup_{ts}_{backup_id[:8]}.zip"
    if junk:
        path.write_bytes(b"not a zip")
        return path
    manifest = BackupManifest(
        backup_id=backup_id,
        version=BackupService.BACKUP_FORMAT_VERSION,
        created_at=created_at,
        app_version=None,
        contents={},
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest.to_dict()))
    return path


# ---------------------------------------------------------------- manifest


class TestManifest:
    def test_round_trip(self) -> None:
        m = BackupManifest(
            backup_id="id-1",
            version="1.0",
            created_at=datetime(2026, 9, 20, 12, 30, tzinfo=UTC),
            app_version="0.9.9",
            contents={
                "events": __import__(
                    "backend.services.backup_service", fromlist=["x"]
                ).BackupContentInfo(count=3, checksum="ab")
            },
        )
        as_dict = m.to_dict()
        assert as_dict["created_at"] == "2026-09-20T12:30:00+00:00"
        assert as_dict["contents"]["events"] == {"count": 3, "checksum": "ab"}
        back = BackupManifest.from_dict(as_dict)
        assert back.backup_id == "id-1"
        assert back.created_at == m.created_at
        assert back.contents["events"].count == 3
        assert back.app_version == "0.9.9"

    def test_from_dict_missing_contents_is_empty(self) -> None:
        m = BackupManifest.from_dict(
            {"backup_id": "b", "version": "1", "created_at": "2026-01-01T00:00:00+00:00"}
        )
        assert m.contents == {}
        assert m.app_version is None  # .get default, not KeyError


class TestServiceConstruction:
    def test_backup_dir_created(self, tmp_path) -> None:
        svc = _service(tmp_path)
        assert svc._backup_dir.is_dir()

    def test_default_backup_dir_is_on_data_volume(self) -> None:
        assert Path("/app/data/backups") == BackupService.BACKUP_DIR

    def test_shared_configuration_tables_order(self, tmp_path) -> None:
        from backend.services.restore_service import RESTORE_TABLE_ORDER, RestoreService

        tables = _service(tmp_path)._get_backup_tables()
        names = [n for n, _ in tables]
        assert names == [
            "households",
            "properties",
            "areas",
            "cameras",
            "camera_areas",
            "zones",
            "activity_baselines",
            "class_baselines",
            "household_members",
            "prompt_versions",
            "settings",
            "alert_rules",
            "recipients",
            "recipient_channels",
        ]
        assert "events" not in names
        assert "alerts" not in names
        assert "prompts" not in names
        # Every table the backup writes has a restore mapping in the same order
        assert names == RESTORE_TABLE_ORDER
        restore_svc = RestoreService()
        for name in names:
            assert restore_svc._get_model_class(name) is not None


# -------------------------------------------------------------- _export_table


class TestExportTable:
    @pytest.mark.asyncio
    async def test_empty_table_writes_empty_json(self, tmp_path) -> None:
        svc = _service(tmp_path)
        out = tmp_path / "t.json"
        assert await svc._export_table(FakeDB([]), ExportProbe, out) == 0
        assert json.loads(out.read_text()) == []

    @pytest.mark.asyncio
    async def test_serializes_datetime_bytes_and_enum(self, tmp_path) -> None:
        svc = _service(tmp_path)
        stamp = datetime(2026, 9, 20, 8, 15, tzinfo=UTC)

        class Row:
            id = 7
            label = Color.RED  # enum column value -> .value
            when = stamp
            blob = b"\x00\x01\x02"

        out = tmp_path / "t.json"
        assert await svc._export_table(FakeDB([Row()]), ExportProbe, out) == 1
        (row,) = json.loads(out.read_text())
        assert row["id"] == 7
        assert row["label"] == "red"  # enum VALUE, not "Color.RED" / repr
        assert row["when"] == "2026-09-20T08:15:00+00:00"
        assert row["blob"] == "AAEC"  # base64 of 00 01 02

    @pytest.mark.asyncio
    async def test_none_values_pass_through(self, tmp_path) -> None:
        svc = _service(tmp_path)

        class Row:
            id = 1
            label = "x"
            when = None
            blob = None

        out = tmp_path / "t.json"
        await svc._export_table(FakeDB([Row()]), ExportProbe, out)
        (row,) = json.loads(out.read_text())
        assert row["when"] is None and row["blob"] is None

    @pytest.mark.asyncio
    async def test_alert_reserved_metadata_key_exports_alert_metadata_payload(
        self,
        tmp_path,
    ) -> None:
        """[r271b] Q-040: the walk must read the mapped attribute, not the key.

        ``Alert`` names its payload column ``alert_metadata`` but maps it to the
        table's ``metadata`` column (models/alert.py:120-121), so the mapper's
        column KEY ``metadata`` has no class-bound attribute behind it. Reading
        the walk's ``getattr(record, "metadata")`` therefore returns SQLAlchemy's
        reserved ``MetaData`` object -- which the exporter stringifies into the
        JSON as ``"metadata": "MetaData()"`` -- while the real payload is never
        written. The fix reads each column through the mapper's column_attrs
        (the key resolves to ``alert_metadata``), so the payload lands in the
        backup. Red on the pre-fix code: the JSON carried ``"metadata":
        "MetaData()"`` and no ``alert_metadata`` key.

        The row is a real (unsaved) ``Alert`` instance, the same object shape
        the integration tier's loaded rows present to the walk; the census at
        the PR base (d5c470715) measured Alert as the only walked model with
        this collision, so the probe is scoped to it.
        """
        from backend.models.alert import Alert

        class PayloadRow(Alert):
            """Instance shape the export loop sees: a mapped Alert row."""

        row = PayloadRow(event_id=1, dedup_key="r271b-probe")
        row.alert_metadata = {"sentinel": "R271B-PAYLOAD"}

        svc = _service(tmp_path)
        out = tmp_path / "alerts.json"
        count = await svc._export_table(FakeDB([row]), Alert, out)
        assert count == 1
        (exported,) = json.loads(out.read_text())
        # The payload must be IN the backup under the attribute's key ...
        assert exported["alert_metadata"] == {"sentinel": "R271B-PAYLOAD"}
        # ... and the reserved key must not carry a stringified MetaData.
        assert "metadata" not in exported

    @pytest.mark.asyncio
    async def test_recipient_channels_export_without_secrets(self, tmp_path) -> None:
        """[B4.2] 4n-restore.md §Privacy: recipient channels arrive without their secrets.

        The signing secret (Fernet ciphertext) and its hint are excluded from the
        exported rows entirely -- the key is absent, not None -- so a restore merge
        keeps the local value on update and the default (None) on insert
        (4n-restore.md §Shape: "A key missing from a record keeps the local value
        on update and the default on insert"). The row is a real unsaved
        RecipientChannel instance, the same object shape the export loop sees.
        """
        from backend.models.alert_delivery import RecipientChannel

        row = RecipientChannel(
            recipient_id="11111111-1111-7111-8111-111111111111",
            kind="webhook",
            target="http://example.invalid/hook",
        )
        row.signing_secret_encrypted = "gAAAAABh-fake-fernet-ciphertext"  # pragma: allowlist secret
        row.signing_secret_hint = "gAAA"  # pragma: allowlist secret

        svc = _service(tmp_path)
        out = tmp_path / "recipient_channels.json"
        count = await svc._export_table(
            FakeDB([row]), RecipientChannel, out, table_name="recipient_channels"
        )
        assert count == 1
        (exported,) = json.loads(out.read_text())
        # The secret columns are absent from the archive, not nulled in it.
        assert "signing_secret_encrypted" not in exported
        assert "signing_secret_hint" not in exported
        # The rest of the channel still ships.
        assert exported["kind"] == "webhook"
        assert exported["target"] == "http://example.invalid/hook"
        assert exported["recipient_id"] == "11111111-1111-7111-8111-111111111111"

    @pytest.mark.asyncio
    async def test_recipients_export_without_user_id(self, tmp_path) -> None:
        """[B4.2] user_id points at users, which backups do not carry; an archive
        row with a dangling user_id would fail the whole all-or-nothing restore on
        the FK. Excluded for the same absent-key reason as the channel secrets.
        """
        from backend.models.alert_delivery import Recipient

        row = Recipient(name="Alex")
        row.user_id = "user-7"

        svc = _service(tmp_path)
        out = tmp_path / "recipients.json"
        count = await svc._export_table(FakeDB([row]), Recipient, out, table_name="recipients")
        assert count == 1
        (exported,) = json.loads(out.read_text())
        assert "user_id" not in exported
        assert exported["name"] == "Alex"
        assert exported["enabled"] is True
        assert exported["critical_breaks_quiet"] is True

    @pytest.mark.asyncio
    async def test_excluded_columns_only_apply_to_their_table(self, tmp_path) -> None:
        """The exclusion map is keyed by table name; another table exporting the
        same column name keeps it."""
        from backend.models.alert_delivery import Recipient

        row = Recipient(name="Sam")
        row.user_id = "user-9"

        svc = _service(tmp_path)
        out = tmp_path / "no-name.json"
        await svc._export_table(FakeDB([row]), Recipient, out, table_name=None)
        (exported,) = json.loads(out.read_text())
        assert exported["user_id"] == "user-9"


# -------------------------------------------------------------- _calculate_checksum


class TestChecksum:
    def test_matches_hashlib(self, tmp_path) -> None:
        svc = _service(tmp_path)
        f = tmp_path / "f.bin"
        f.write_bytes(b"hello backup")
        assert svc._calculate_checksum(f) == hashlib.sha256(b"hello backup").hexdigest()

    def test_large_file_chunks_concatenate(self, tmp_path) -> None:
        svc = _service(tmp_path)
        payload = bytes(range(256)) * 600  # ~150KB > one 64KB chunk
        f = tmp_path / "big.bin"
        f.write_bytes(payload)
        assert svc._calculate_checksum(f) == hashlib.sha256(payload).hexdigest()

    def test_missing_file_raises(self, tmp_path) -> None:
        with pytest.raises(FileNotFoundError):
            _service(tmp_path)._calculate_checksum(tmp_path / "ghost.bin")


class TestAppVersion:
    def test_reads_repo_pyproject(self, tmp_path) -> None:
        import tomllib

        with open("pyproject.toml", "rb") as fh:
            expected = tomllib.load(fh)["project"].get("version")
        assert _service(tmp_path)._get_app_version() == expected


# --------------------------------------------------------------- create_backup


class TestCreateBackup:
    @pytest.mark.asyncio
    async def test_zip_layout_manifest_and_progress(self, tmp_path) -> None:
        svc = _service(tmp_path)
        steps: list[tuple[int, str]] = []

        async def cb(pct, name):
            steps.append((pct, name))

        result = await svc.create_backup(FakeDB([]), job_id="abcdef12345", progress_callback=cb)

        assert result.file_path.name.startswith("backup_")
        assert result.file_path.name.endswith("_abcdef12.zip")
        assert result.file_size == result.file_path.stat().st_size > 0

        with zipfile.ZipFile(result.file_path) as zf:
            names = set(zf.namelist())
            assert "manifest.json" in names
            assert "households.json" in names and "alert_rules.json" in names
            assert "events.json" not in names and "alerts.json" not in names
            assert len(names) == 15  # manifest + 14 configuration tables
            body = json.loads(zf.read("manifest.json"))
        assert body["backup_id"] == "abcdef12345"
        assert body["version"] == "1.1"
        assert body["installation_id"]
        # every table exported empty: count 0 and checksum of "[]"
        assert body["contents"]["cameras"]["count"] == 0
        assert body["contents"]["cameras"]["checksum"] == hashlib.sha256(b"[]").hexdigest()

        # progress: 14 export steps at int(idx/14*80), then 85/90/95/100
        assert [p for p, _ in steps] == [
            0,
            5,
            11,
            17,
            22,
            28,
            34,
            40,
            45,
            51,
            57,
            62,
            68,
            74,
            85,
            90,
            95,
            100,
        ]
        assert steps[-1][1] == "Backup complete"
        assert steps[14][1] == "Creating manifest"

    @pytest.mark.asyncio
    async def test_without_callback_still_succeeds(self, tmp_path) -> None:
        result = await _service(tmp_path).create_backup(FakeDB([]), job_id="job-2")
        assert result.manifest.contents["cameras"].count == 0


# ------------------------------------------------------------ list/delete/get


class TestListAndDelete:
    def test_lists_newest_first_and_skips_junk(self, tmp_path) -> None:
        svc = _service(tmp_path)
        old = _write_backup(svc, "old-1", datetime(2026, 9, 1, tzinfo=UTC))
        _write_backup(svc, "junk", datetime(2026, 9, 10, tzinfo=UTC), junk=True)
        new = _write_backup(svc, "new-1", datetime(2026, 9, 15, tzinfo=UTC))
        listed = svc.list_backups()
        assert [b.backup_id for b in listed] == ["new-1", "old-1"]
        assert listed[0].file_path == new and listed[1].file_path == old
        assert listed[1].file_size == old.stat().st_size

    def test_missing_dir_lists_empty(self, tmp_path) -> None:
        svc = BackupService(backup_dir=tmp_path / "gone")
        svc._backup_dir.rmdir()  # ctor created it; emulate vanishing afterwards
        assert svc.list_backups() == []

    def test_delete_true_and_false(self, tmp_path) -> None:
        svc = _service(tmp_path)
        path = _write_backup(svc, "del-1", datetime(2026, 9, 15, tzinfo=UTC))
        assert svc.delete_backup("del-1") is True
        assert not path.exists()
        assert svc.delete_backup("del-1") is False  # second delete finds nothing

    def test_get_backup_path(self, tmp_path) -> None:
        svc = _service(tmp_path)
        path = _write_backup(svc, "find-1", datetime(2026, 9, 15, tzinfo=UTC))
        assert svc.get_backup_path("find-1") == path
        assert svc.get_backup_path("nope") is None


class TestCleanupOldBackups:
    def test_age_cutoff_removes_only_old(self, tmp_path) -> None:
        svc = _service(tmp_path)
        now = utc_now()
        _write_backup(svc, "ancient", now - timedelta(days=40))
        _write_backup(svc, "recent", now - timedelta(days=5))
        assert svc.cleanup_old_backups(max_age_days=30, max_count=10) == 1
        assert [b.backup_id for b in svc.list_backups()] == ["recent"]

    def test_count_overflow_removes_oldest(self, tmp_path) -> None:
        svc = _service(tmp_path)
        now = utc_now()
        for i in range(4):
            _write_backup(svc, f"b{i}", now - timedelta(days=i))  # b3 oldest
        assert svc.cleanup_old_backups(max_age_days=365, max_count=2) == 2
        assert [b.backup_id for b in svc.list_backups()] == ["b0", "b1"]

    def test_noop_returns_zero(self, tmp_path) -> None:
        assert _service(tmp_path).cleanup_old_backups() == 0


class TestSingleton:
    def test_get_stable_reset_rebuilds(self) -> None:
        reset_backup_service()
        svc = get_backup_service()
        assert get_backup_service() is svc
        reset_backup_service()
        assert get_backup_service() is not svc
        reset_backup_service()


class TestInstallationIdAndAssociationExport:
    @pytest.mark.asyncio
    async def test_get_or_create_installation_id_reads_and_creates(self) -> None:
        from backend.models.gpu_config import SystemSetting
        from backend.services.backup_service import (
            INSTALLATION_ID_SETTING_KEY,
            get_or_create_installation_id,
        )

        class _FakeResult:
            def __init__(self, row: Any) -> None:
                self._row = row

            def scalar_one_or_none(self) -> Any:
                return self._row

        class _FakeSession:
            def __init__(self, row: Any = None) -> None:
                self.row = row
                self.added: list[Any] = []
                self.flushed = False
                self.executed_stmts: list[Any] = []

            async def execute(self, stmt: Any) -> _FakeResult:
                self.executed_stmts.append(stmt)
                return _FakeResult(self.row)

            def add(self, obj: Any) -> None:
                self.added.append(obj)

            async def flush(self) -> None:
                self.flushed = True

        existing = SystemSetting(
            key=INSTALLATION_ID_SETTING_KEY,
            value={"installation_id": "inst-existing-123"},
        )
        assert await get_or_create_installation_id(_FakeSession(existing)) == "inst-existing-123"  # type: ignore[arg-type]

        existing_str = SystemSetting(
            key=INSTALLATION_ID_SETTING_KEY,
            value="inst-str-456",  # type: ignore[arg-type]
        )
        assert await get_or_create_installation_id(_FakeSession(existing_str)) == "inst-str-456"  # type: ignore[arg-type]

        fresh = _FakeSession(None)
        generated = await get_or_create_installation_id(fresh)  # type: ignore[arg-type]
        assert len(generated) == 36
        assert fresh.flushed is True
        assert len(fresh.added) == 1
        assert fresh.added[0].key == INSTALLATION_ID_SETTING_KEY

        class _ConcurrentRaceSession(_FakeSession):
            async def execute(self, stmt: Any) -> _FakeResult:
                self.executed_stmts.append(stmt)
                if len(self.executed_stmts) >= 3:
                    return _FakeResult(
                        SystemSetting(
                            key=INSTALLATION_ID_SETTING_KEY,
                            value={"installation_id": "winner-from-concurrent-insert"},
                        )
                    )
                return _FakeResult(None)

        raced = _ConcurrentRaceSession(None)
        assert (
            await get_or_create_installation_id(raced)  # type: ignore[arg-type]
            == "winner-from-concurrent-insert"
        )
        assert raced.flushed is False

    def test_resolve_backup_dir_falls_back_when_unwritable(self, tmp_path: Path) -> None:
        from backend.services.backup_service import resolve_backup_dir

        writable = tmp_path / "writable-backups"
        writable.mkdir()
        assert resolve_backup_dir(writable) == writable

    @pytest.mark.asyncio
    async def test_export_association_table_serializes_rows(self, tmp_path: Path) -> None:
        from backend.models.area import camera_areas

        svc = _service(tmp_path)

        class _FakeMappingResult:
            def mappings(self) -> _FakeMappingResult:
                return self

            def all(self) -> list[dict[str, Any]]:
                return [
                    {"camera_id": "front_door", "area_id": 1},
                    {"camera_id": "back_yard", "area_id": 2},
                ]

        class _FakeSession:
            async def execute(self, _stmt: Any) -> _FakeMappingResult:
                return _FakeMappingResult()

        out_file = tmp_path / "camera_areas.json"
        count = await svc._export_table(_FakeSession(), camera_areas, out_file)  # type: ignore[arg-type]
        assert count == 2
        rows = json.loads(out_file.read_text())
        assert rows == [
            {"camera_id": "front_door", "area_id": 1},
            {"camera_id": "back_yard", "area_id": 2},
        ]
