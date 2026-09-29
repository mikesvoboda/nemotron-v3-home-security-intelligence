"""Corpus snapshots and the prune rule (agent-driven design §6; plan rulings P3-R5, P3-R6).

`python -m synthbench corpus snapshot` (the 6-hourly timer) snapshots the corpus dataset, then
prunes. While more than KEEP synthbench snapshots exist, it looks at the oldest only:

- A removed file, or a changed file other than JSON, JSONL or a batch view, means the oldest
  holds the only copy. Pruning stops, and status/snapshots.json names the snapshot.
- Otherwise the changes are expected churn: the oldest is destroyed and the loop repeats.

Only the oldest is ever destroyed, so no deletion slips through a gap.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath

from synthbench.status import SnapshotHold, SnapshotStatus, snapshots_file, write_status

DATASET = "primary/export/synthbench/corpus"
PREFIX = "synthbench-"
KEEP = 5
CHURN = frozenset({".json", ".jsonl", ".md", ".html"})  # files commands replace (P3-R6)
HOLD_PATHS_SHOWN = 20

Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class Change:
    kind: str  # "-", "+", "M" or "R"
    file_type: str  # zfs diff -F: "F" file, "/" directory, "@" link, ...
    path: str
    new_path: str | None = None  # R only


def parse_diff(text: str) -> list[Change]:
    """`zfs diff -FH` lines: change, type, path, and the new path of a rename. A fourth field on
    another change is a link-count note such as `(+1)`, and is dropped."""
    changes: list[Change] = []
    for line in text.splitlines():
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) not in (3, 4) or fields[0] not in {"-", "+", "M", "R"}:
            raise ValueError(f"unexpected zfs diff line: {line!r}")
        new_path = fields[3] if fields[0] == "R" and len(fields) == 4 else None
        changes.append(Change(fields[0], fields[1], fields[2], new_path))
    return changes


def _store_temp(path: str) -> bool:
    name = PurePosixPath(path).name
    return name.startswith(".") and name.endswith(".tmp")


@dataclass(frozen=True)
class Verdict:
    removed: tuple[str, ...]
    modified: tuple[str, ...]

    @property
    def held(self) -> tuple[str, ...]:
        """Paths the older snapshot holds the only copy of (design §6)."""
        edited = tuple(p for p in self.modified if PurePosixPath(p).suffix not in CHURN)
        return (*self.removed, *edited)


def classify(changes: Sequence[Change]) -> Verdict:
    """A replace shows as `-` and `+` on one path: that is a modification (P3-R5)."""
    gone: set[str] = set()
    made: set[str] = set()
    changed: set[str] = set()
    for change in changes:
        if change.file_type == "/" or _store_temp(change.path):
            continue
        if change.kind == "-":
            gone.add(change.path)
        elif change.kind == "+":
            made.add(change.path)
        elif change.kind == "M":
            changed.add(change.path)
        else:  # R: the old path is gone, the new one made
            gone.add(change.path)
            if change.new_path is not None:
                made.add(change.new_path)
    changed |= gone & made
    return Verdict(removed=tuple(sorted(gone - made)), modified=tuple(sorted(changed)))


def prune(
    snapshots: Sequence[str],
    *,
    diff: Callable[[str, str], str],
    destroy: Callable[[str], None],
    keep: int = KEEP,
) -> tuple[SnapshotHold | None, int]:
    """Destroy the oldest while more than `keep` remain and it holds no only copy.

    Returns the hold that stopped pruning (or None) and how many snapshots were destroyed.
    """
    remaining = list(snapshots)
    destroyed = 0
    while len(remaining) > keep:
        oldest, following = remaining[0], remaining[1]
        held = classify(parse_diff(diff(oldest, following))).held
        if held:
            hold = SnapshotHold(snapshot=oldest, count=len(held), paths=held[:HOLD_PATHS_SHOWN])
            return hold, destroyed
        destroy(oldest)
        remaining.pop(0)
        destroyed += 1
    return None, destroyed


def take_snapshot(dataset: str, now: datetime, run: Runner) -> str:
    name = f"{dataset}@{PREFIX}{now:%Y%m%dT%H%M%SZ}"
    run(["zfs", "snapshot", name], check=True, capture_output=True, text=True, timeout=120)
    return name


def list_snapshots(dataset: str, run: Runner) -> list[str]:
    """The dataset's synthbench snapshots, oldest first."""
    done = run(
        [
            "zfs",
            "list",
            "-H",
            "-t",
            "snapshot",
            "-o",
            "name",
            "-s",
            "createtxg",
            "-d",
            "1",
            dataset,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    lines = (line.strip() for line in done.stdout.splitlines())
    names = (line for line in lines if line)
    return [name for name in names if name.startswith(f"{dataset}@{PREFIX}")]


def zfs_diff(older: str, newer: str, run: Runner) -> str:
    done = run(
        ["zfs", "diff", "-FH", older, newer],
        check=True,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    return done.stdout


def destroy_snapshot(name: str, dataset: str, run: Runner) -> None:
    """Refuse anything but the exact name `take_snapshot` produces.

    zfs reads more into a name than a prefix shows: `…@synthbench-1%` is a range (destroys from
    `synthbench-1` through the newest snapshot) and `…@synthbench-1,manual` is a list. A full
    match on the timestamp format `take_snapshot` writes closes both holes.
    """
    pattern = rf"{re.escape(dataset)}@{re.escape(PREFIX)}\d{{8}}T\d{{6}}Z"
    if re.fullmatch(pattern, name) is None:
        raise ValueError(f"refusing to destroy {name!r}: not a {PREFIX} snapshot of {dataset}")
    run(["zfs", "destroy", name], check=True, capture_output=True, text=True, timeout=600)


def snapshot_and_prune(env: Mapping[str, str], *, run: Runner, now: datetime) -> SnapshotStatus:
    dataset = env.get("SYNTHBENCH_CORPUS_DATASET", DATASET)
    take_snapshot(dataset, now, run)
    snapshots = list_snapshots(dataset, run)
    hold, destroyed = prune(
        snapshots,
        diff=lambda older, newer: zfs_diff(older, newer, run),
        destroy=lambda name: destroy_snapshot(name, dataset, run),
    )
    status = SnapshotStatus(time=now, snapshots=len(snapshots) - destroyed, hold=hold)
    write_status(snapshots_file(env), status)
    return status
