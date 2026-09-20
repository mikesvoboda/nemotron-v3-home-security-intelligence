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

    def test_tables_events_first(self, tmp_path) -> None:
        tables = _service(tmp_path)._get_backup_tables()
        names = [n for n, _ in tables]
        assert names[0] == "events"
        assert names[-1] == "settings"
        assert len(names) == 9


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
            assert "events.json" in names and "settings.json" in names
            assert len(names) == 10  # manifest + 9 tables
            body = json.loads(zf.read("manifest.json"))
        assert body["backup_id"] == "abcdef12345"
        assert body["version"] == BackupService.BACKUP_FORMAT_VERSION
        # every table exported empty: count 0 and checksum of "[]"
        assert body["contents"]["events"]["count"] == 0
        assert body["contents"]["events"]["checksum"] == hashlib.sha256(b"[]").hexdigest()

        # progress: 9 export steps at int(idx/9*80), then 85/90/95/100
        assert [p for p, _ in steps] == [0, 8, 17, 26, 35, 44, 53, 62, 71, 85, 90, 95, 100]
        assert steps[-1][1] == "Backup complete"
        assert steps[9][1] == "Creating manifest"

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
