"""Where a corpus version's files live, and how they are written (agent-driven design §2).

The corpus is append-only. Images and clips are created once and never replaced. JSON files
and the batch views (report.md, sheet.html) change only by atomic replace. index.jsonl only
grows. Every file is mode 0644 so the owner can read what the sandbox agent wrote.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TypeVar

from synthbench.contract.common import SLUG, ContractModel
from synthbench.contract.corpus import IndexRow

M = TypeVar("M", bound=ContractModel)

DEFAULT_SYNTHBENCH_ROOT = Path("/export/synthbench")
# A tier letter, then no path separators or dot segments: the id never leaves version_dir.
_EVENT_ID = re.compile(r"[AB]-[A-Za-z0-9][A-Za-z0-9_-]*")
_FILE_MODE = 0o644
_REPLACEABLE = frozenset({".json", ".md", ".html"})
# A filesystem that refuses hard links (the sandbox's virtiofs mount may: P3 Task 1) gets an
# O_EXCL create instead. It still never replaces a file.
_NO_HARDLINK = frozenset({errno.EPERM, errno.EOPNOTSUPP, errno.ENOTSUP, errno.EMLINK})


def to_json(model: ContractModel) -> str:
    """Stable JSON: alias keys, no nulls, sorted keys, one-space indent, trailing newline."""
    payload = model.model_dump(mode="json", exclude_none=True)
    return json.dumps(payload, indent=1, sort_keys=True) + "\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_tmp(directory: Path, name: str, data: bytes) -> Path:
    """A fsynced 0644 temporary file beside `name`; store temps are named `.<name>.*.tmp`."""
    fd, tmp_name = tempfile.mkstemp(dir=directory, prefix=f".{name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), _FILE_MODE)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return tmp


def _create_exclusive(path: Path, data: bytes) -> None:
    """The fallback where hard links are refused: O_EXCL never replaces; a failed write is
    removed rather than left half-written."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, _FILE_MODE)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), _FILE_MODE)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


class CorpusStore:
    """Paths and writes for one corpus version, under <root>/<version>/."""

    def __init__(self, root: Path, version: str) -> None:
        if not SLUG.fullmatch(version):
            raise ValueError(f"corpus version {version!r} must match {SLUG.pattern}")
        self.root = root
        self.version = version

    @classmethod
    def from_env(cls, version: str, env: Mapping[str, str] | None = None) -> CorpusStore:
        """The corpus lives at $SYNTHBENCH_ROOT/corpus (a ZFS dataset on maui, design §6)."""
        environment = os.environ if env is None else env
        root = Path(environment.get("SYNTHBENCH_ROOT", str(DEFAULT_SYNTHBENCH_ROOT)))
        return cls(root / "corpus", version)

    @property
    def version_dir(self) -> Path:
        return self.root / self.version

    @property
    def manifest_file(self) -> Path:
        return self.version_dir / "corpus.json"

    @property
    def index_file(self) -> Path:
        return self.version_dir / "index.jsonl"

    def event_dir(self, event_id: str) -> Path:
        if not _EVENT_ID.fullmatch(event_id):
            raise ValueError(
                f"event_id must be A- or B- followed by letters, digits, '_' or '-': {event_id!r}"
            )
        return self.version_dir / "events" / event_id[0] / event_id

    def spec_file(self, event_id: str) -> Path:
        return self.event_dir(event_id) / "spec.json"

    def provenance_file(self, event_id: str) -> Path:
        return self.event_dir(event_id) / "provenance.json"

    def batch_dir(self, name: str) -> Path:
        if not SLUG.fullmatch(name):
            raise ValueError(f"batch name {name!r} must match {SLUG.pattern}")
        return self.version_dir / "batches" / name

    def batch_file(self, name: str) -> Path:
        return self.batch_dir(name) / "batch.json"

    def _check_inside(self, path: Path) -> None:
        if not path.resolve().is_relative_to(self.version_dir.resolve()):
            raise ValueError(f"{path} is outside corpus version {self.version_dir}")

    def write_new(self, path: Path, model: ContractModel) -> None:
        """Create path holding model's JSON. Raises FileExistsError if it exists."""
        self.write_new_bytes(path, to_json(model).encode())

    def write_new_bytes(self, path: Path, data: bytes) -> None:
        """Create path holding data, atomically where hard links work; never replaces a file.

        Raises FileExistsError if path exists.
        """
        self._check_inside(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = _write_tmp(path.parent, path.name, data)
        try:
            path.hardlink_to(tmp)  # a new link never replaces: FileExistsError if path exists
        except OSError as error:
            if error.errno not in _NO_HARDLINK:
                raise
            _create_exclusive(path, data)
        finally:
            tmp.unlink(missing_ok=True)

    def replace_text(self, path: Path, text: str) -> None:
        """Write a JSON file or a batch view atomically, replacing any earlier version.

        zfs diff shows the replace as `-` and `+` on the same path; the snapshot prune rule
        counts that pair as a modification (plan rulings P3-R5, P3-R6).
        """
        self._check_inside(path)
        if path.suffix not in _REPLACEABLE:
            raise ValueError(
                f"only {', '.join(sorted(_REPLACEABLE))} files change in place, not {path.name}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = _write_tmp(path.parent, path.name, text.encode())
        try:
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)

    def replace_json(self, path: Path, model: ContractModel) -> None:
        self.replace_text(path, to_json(model))

    @staticmethod
    def read(path: Path, model: type[M]) -> M:
        return model.model_validate_json(path.read_text(encoding="utf-8"))

    def append_index(self, rows: Iterable[IndexRow]) -> None:
        """Append rows in one O_APPEND write, so no other append splits a row (ruling P3-R15)."""
        data = "".join(
            json.dumps(row.model_dump(mode="json", exclude_none=True), sort_keys=True) + "\n"
            for row in rows
        ).encode()
        if not data:
            return
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        created = not self.index_file.exists()
        fd = os.open(self.index_file, os.O_WRONLY | os.O_APPEND | os.O_CREAT, _FILE_MODE)
        try:
            if created:
                os.fchmod(fd, _FILE_MODE)
            written = os.write(fd, data)
            if written != len(data):
                raise OSError(
                    errno.EIO, f"short append to {self.index_file}: {written} of {len(data)} bytes"
                )
            os.fsync(fd)
        finally:
            os.close(fd)

    def latest_index(self) -> dict[str, IndexRow]:
        """The latest row per event. The index is append-only, so later rows win."""
        if not self.index_file.exists():
            return {}
        latest: dict[str, IndexRow] = {}
        for line in self.index_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = IndexRow.model_validate_json(line)
                latest[row.event_id] = row
        return latest
