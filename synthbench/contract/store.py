"""Where a corpus version's files live, and how they are written (agent-driven design §2).

The corpus is append-only: write_new creates a file atomically and never replaces one.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TypeVar

from synthbench.contract.common import SLUG, ContractModel
from synthbench.contract.corpus import IndexRow

M = TypeVar("M", bound=ContractModel)

DEFAULT_SYNTHBENCH_ROOT = Path("/export/synthbench")


def to_json(model: ContractModel) -> str:
    """Stable JSON: alias keys, no nulls, sorted keys, one-space indent, trailing newline."""
    payload = model.model_dump(mode="json", exclude_none=True)
    return json.dumps(payload, indent=1, sort_keys=True) + "\n"


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
        tier, _, rest = event_id.partition("-")
        if tier not in ("A", "B") or not rest:
            raise ValueError(f"event_id must start with A- or B-: {event_id!r}")
        return self.version_dir / "events" / tier / event_id

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

    def write_new(self, path: Path, model: ContractModel) -> None:
        """Create path holding model's JSON, atomically. Raises FileExistsError if it exists."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(to_json(model))
                handle.flush()
                os.fsync(handle.fileno())
            path.hardlink_to(tmp)  # a new link never replaces: FileExistsError if path exists
        finally:
            tmp.unlink()

    @staticmethod
    def read(path: Path, model: type[M]) -> M:
        return model.model_validate_json(path.read_text(encoding="utf-8"))

    def append_index(self, rows: Iterable[IndexRow]) -> None:
        lines = [
            json.dumps(row.model_dump(mode="json", exclude_none=True), sort_keys=True) + "\n"
            for row in rows
        ]
        if not lines:
            return
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        with self.index_file.open("a", encoding="utf-8") as handle:
            handle.writelines(lines)
            handle.flush()
            os.fsync(handle.fileno())

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
