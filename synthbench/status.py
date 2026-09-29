"""Host status files the sandbox reads (agent-driven design §1, §5.2, §6).

The guard writes status/flagship.json every 5 s; `corpus snapshot` writes
status/snapshots.json. The sandbox mounts status/ read-only at the same path.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import AwareDatetime, Field, ValidationError

from synthbench.contract.common import ContractModel

STALE_AFTER_S = 30.0  # design §5.2: an older flagship.json means the guard is down

M = TypeVar("M", bound=ContractModel)


class FlagshipStatus(ContractModel):
    schema_version: Literal[1] = 1
    time: AwareDatetime
    healthy: bool
    running: int | None = Field(default=None, ge=0)
    waiting: int | None = Field(default=None, ge=0)
    failures: int = Field(default=0, ge=0)  # consecutive failed health checks


class SnapshotHold(ContractModel):
    snapshot: str
    count: int = Field(ge=1)
    paths: tuple[str, ...]


class SnapshotStatus(ContractModel):
    schema_version: Literal[1] = 1
    time: AwareDatetime
    snapshots: int = Field(ge=0)
    hold: SnapshotHold | None = None


class FlagshipUnknown(RuntimeError):
    """No fresh flagship status: the guard is down, so nothing may render (design §5.2)."""


def status_dir(env: Mapping[str, str] | None = None) -> Path:
    e = os.environ if env is None else env
    return Path(e.get("SYNTHBENCH_ROOT", "/export/synthbench")) / "status"


def flagship_file(env: Mapping[str, str] | None = None) -> Path:
    return status_dir(env) / "flagship.json"


def snapshots_file(env: Mapping[str, str] | None = None) -> Path:
    return status_dir(env) / "snapshots.json"


def write_status(path: Path, model: ContractModel) -> None:
    """Replace a status file atomically, world-readable: the sandbox reads it through a mount."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o644)
            handle.write(model.model_dump_json() + "\n")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def read_status(path: Path, model: type[M]) -> M:
    return model.model_validate_json(path.read_text(encoding="utf-8"))


def fresh_flagship(path: Path, now: datetime) -> FlagshipStatus:
    try:
        status = read_status(path, FlagshipStatus)
    except (OSError, UnicodeDecodeError, ValidationError) as error:
        raise FlagshipUnknown(
            f"cannot read {path} ({type(error).__name__}); is synthbench-guard running?"
        ) from error
    age = (now - status.time).total_seconds()
    if age > STALE_AFTER_S:
        raise FlagshipUnknown(f"{path} is {age:.0f} s old, so the guard is down")
    return status
