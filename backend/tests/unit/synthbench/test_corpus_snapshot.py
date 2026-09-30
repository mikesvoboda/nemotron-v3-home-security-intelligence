"""Corpus snapshots and the prune rule (agent-driven design §6; plan rulings P3-R5, P3-R6)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from synthbench import cli
from synthbench.commands import corpus
from synthbench.commands.common import AskOwner
from synthbench.host.snapshot import (
    DATASET,
    classify,
    destroy_snapshot,
    list_snapshots,
    parse_diff,
    prune,
)
from synthbench.status import SnapshotHold, SnapshotStatus, read_status, snapshots_file

from backend.tests.unit.synthbench import helpers as h

BASE = "/synthbench/corpus/.p3probe"
# Recorded on maui 2026-09-28 with `zfs diff -FH` across: a replace (rename over), an in-place
# write, a deletion, an append, a rename, a temp file left by a crash, and write_new's link.
PROBE = "".join(
    f"{line}\n"
    for line in (
        f"-\tF\t{BASE}/replaced.json",
        f"M\tF\t{BASE}/inplace.json",
        f"-\tF\t{BASE}/gone.png",
        f"M\tF\t{BASE}/log.jsonl",
        f"R\tF\t{BASE}/renamed_src.json\t{BASE}/renamed_dst.json",
        f"+\tF\t{BASE}/replaced.json",
        f"+\tF\t{BASE}/sub/.leftover.json.abc.tmp",
        f"M\t/\t{BASE}",
        f"M\t/\t{BASE}/sub",
        f"+\tF\t{BASE}/sub/new.json",
    )
)


def test_the_recorded_probe_classifies_as_the_rule_says() -> None:
    verdict = classify(parse_diff(PROBE))
    assert verdict.removed == (f"{BASE}/gone.png", f"{BASE}/renamed_src.json")
    assert verdict.modified == (
        f"{BASE}/inplace.json",
        f"{BASE}/log.jsonl",
        f"{BASE}/replaced.json",
    )
    assert verdict.held == verdict.removed


@pytest.mark.parametrize(
    ("lines", "held"),
    [
        (
            [
                "M\tF\t/c/v/index.jsonl",
                "-\tF\t/c/v/e/spec.json",
                "+\tF\t/c/v/e/spec.json",
                "M\tF\t/c/v/b/report.md",
                "M\tF\t/c/v/b/sheet.html",
            ],
            (),
        ),
        (["M\tF\t/c/v/e/renders/a1-s1.png"], ("/c/v/e/renders/a1-s1.png",)),
        (
            ["-\tF\t/c/v/e/stills/a1-s1.jpg", "+\tF\t/c/v/e/stills/a1-s1.jpg"],
            ("/c/v/e/stills/a1-s1.jpg",),
        ),
        (["-\tF\t/c/v/e/.spec.json.x1y2.tmp"], ()),
        (["M\tF\t/c/v/notes.txt"], ("/c/v/notes.txt",)),
        (["+\tF\t/c/v/e/renders/a2-s9.png", "M\t/\t/c/v/e/renders"], ()),
        (["M\tF\t/c/v/e/renders/a1-s1.png\t(+1)"], ("/c/v/e/renders/a1-s1.png",)),
    ],
    ids=[
        "json-churn",
        "image-edited",
        "image-replaced",
        "temp-removed",
        "unknown-type",
        "added",
        "link-count",
    ],
)
def test_what_holds_a_snapshot(lines: list[str], held: tuple[str, ...]) -> None:
    assert classify(parse_diff("".join(f"{line}\n" for line in lines))).held == held


def test_an_unknown_diff_line_is_an_error() -> None:
    with pytest.raises(ValueError, match="unexpected zfs diff line"):
        parse_diff("?\tF\t/c/x\n")


def test_prune_destroys_only_churn_snapshots_down_to_five() -> None:
    snaps = [f"{DATASET}@synthbench-{i}" for i in range(8)]
    destroyed: list[str] = []
    hold, count = prune(
        snaps, diff=lambda _a, _b: "M\tF\t/c/v/index.jsonl\n", destroy=destroyed.append
    )
    assert (hold, count) == (None, 3)
    assert destroyed == snaps[:3]


def test_a_hold_stops_pruning_and_nothing_past_it_is_destroyed() -> None:
    snaps = [f"{DATASET}@synthbench-{i}" for i in range(8)]
    destroyed: list[str] = []

    def diff(older: str, _newer: str) -> str:
        return (
            "-\tF\t/c/v/e/renders/a1-s1.png\n" if older == snaps[1] else "M\tF\t/c/v/index.jsonl\n"
        )

    hold, count = prune(snaps, diff=diff, destroy=destroyed.append)
    assert destroyed == [snaps[0]]
    assert count == 1
    assert hold == SnapshotHold(snapshot=snaps[1], count=1, paths=("/c/v/e/renders/a1-s1.png",))


@pytest.mark.parametrize(
    "name",
    [
        DATASET,
        f"{DATASET}@manual",
        "primary/export@synthbench-1",
        f"{DATASET}@synthbench-1%",  # a zfs range: synthbench-1 through the newest snapshot
        f"{DATASET}@synthbench-1,manual",  # a zfs list
    ],
)
def test_destroy_refuses_anything_but_a_synthbench_snapshot_of_the_dataset(name: str) -> None:
    def never(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError(f"ran {argv}")

    with pytest.raises(ValueError, match="refusing"):
        destroy_snapshot(name, DATASET, never)


def test_destroy_accepts_the_exact_name_take_snapshot_produces() -> None:
    name = f"{DATASET}@synthbench-20260928T120000Z"
    calls: list[list[str]] = []

    def record(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    destroy_snapshot(name, DATASET, record)
    assert calls == [["zfs", "destroy", name]]


def test_list_snapshots_keeps_a_name_with_a_space_intact() -> None:
    """`.split()` would break a spaced name into fragments; one of them (the part before the
    space) still starts with the dataset/prefix and would slip through as a corrupted name."""
    weird = f"{DATASET}@synthbench-20260928T120000Z odd"

    def fake_run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 0, f"{weird}\n", "")

    assert list_snapshots(DATASET, fake_run) == [weird]


class FakeZfs:
    """zfs snapshot, list, diff and destroy over an in-memory snapshot list."""

    def __init__(self, existing: list[str], diffs: dict[str, str] | None = None) -> None:
        self.snaps = list(existing)
        self.diffs = diffs or {}

    def __call__(self, argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        verb, out = argv[1], ""
        if verb == "snapshot":
            self.snaps.append(argv[2])
        elif verb == "list":
            out = "".join(f"{name}\n" for name in self.snaps)
        elif verb == "diff":
            out = self.diffs.get(argv[3], "M\tF\t/c/v/index.jsonl\n")
        elif verb == "destroy":
            self.snaps.remove(argv[2])
        return subprocess.CompletedProcess(argv, 0, out, "")


def test_the_command_snapshots_prunes_and_writes_the_status(tmp_path: Path) -> None:
    zfs = FakeZfs([f"{DATASET}@synthbench-2026092{i}T000000Z" for i in range(5)])
    env = h.env(tmp_path)
    assert corpus.execute_snapshot(env, run=zfs, now=h.NOW) == cli.EXIT_OK
    assert len(zfs.snaps) == 5
    assert zfs.snaps[-1] == f"{DATASET}@synthbench-20260928T120000Z"
    status = read_status(snapshots_file(env), SnapshotStatus)
    assert (status.snapshots, status.hold) == (5, None)


def test_a_hold_is_written_and_asks_the_owner(tmp_path: Path) -> None:
    snaps = [f"{DATASET}@synthbench-2026092{i}T000000Z" for i in range(5)]
    zfs = FakeZfs(snaps, diffs={snaps[0]: "-\tF\t/c/v/e/renders/a1-s1.png\n"})
    env = h.env(tmp_path)
    with pytest.raises(AskOwner, match="holds the only copy"):
        corpus.execute_snapshot(env, run=zfs, now=h.NOW)
    status = read_status(snapshots_file(env), SnapshotStatus)
    assert status.hold is not None
    assert status.hold.snapshot == snaps[0]
    assert status.snapshots == 6


def test_a_zfs_failure_asks_the_owner_and_destroys_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing_run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if argv[1] == "destroy":
            raise AssertionError(f"destroyed {argv[2]}")
        if argv[1] == "snapshot":
            raise subprocess.CalledProcessError(1, argv, stderr="zfs: out of space")
        raise AssertionError(f"unexpected zfs call: {argv}")

    monkeypatch.setattr(subprocess, "run", failing_run)
    assert cli.main(["corpus", "snapshot"], env=h.env(tmp_path)) == cli.EXIT_ASK


def test_an_unexpected_snapshot_error_keeps_its_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The timer's journal is the only record of a host run, so an unexpected error keeps its
    traceback there, beside cli.main's one-line `unexpected error` and exit 2."""

    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(corpus, "snapshot_and_prune", boom)
    assert h.run(tmp_path, "corpus", "snapshot") == cli.EXIT_ASK
    err = capsys.readouterr().err
    assert "Traceback (most recent call last)" in err
    assert "unexpected error: RuntimeError: boom" in err
