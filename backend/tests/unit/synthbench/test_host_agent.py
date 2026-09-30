"""The owner's agent command: retire and recreate the generation agent's sandbox (runbook,
"Create the agent's sandbox")."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from synthbench.host.agent import (
    APT_LIBS,
    MOUNTS,
    SANDBOX,
    SESSION,
    Host,
    Refused,
    blob_id,
    down,
    up,
)
from synthbench.host.units import GUARD, RENDERER

TARGET = "a" * 40
BASE = "b" * 40
NOTE = "docs/synthbench/h3-prompt-notes.md"


class Fake:
    """Answers the read-only commands; records every call; fails the step named in `fail`."""

    def __init__(
        self,
        *,
        old: bool = True,
        renderer: str = "inactive",
        host_dirty: str = "",
        trees: dict[str, dict[str, bytes]] | None = None,
        new_head: str = TARGET,
        fail: str | None = None,
    ) -> None:
        self.old = old
        self.renderer = renderer
        self.host_dirty = host_dirty
        self.trees = trees or {}
        self.new_head = new_head
        self.fail = fail
        self.calls: list[tuple[list[str], Path | None]] = []

    def __call__(self, argv: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        argv = [str(a) for a in argv]
        self.calls.append((argv, kwargs.get("cwd")))
        if self.fail and self.fail in " ".join(argv):
            if kwargs.get("check"):
                raise subprocess.CalledProcessError(1, argv)
            return subprocess.CompletedProcess(argv, 1, "", "")
        return subprocess.CompletedProcess(argv, *self._answer(argv))

    def _answer(self, argv: list[str]) -> tuple[int, str, str]:
        reads = {
            "rev-parse": (0, TARGET),
            "log": (0, "the subject"),
            "status": (0, self.host_dirty),
            "is-active": (0 if self.renderer == "active" else 3, self.renderer),
        }
        for word, (code, out) in reads.items():
            if word in argv:
                return code, out + "\n", ""
        if "ls-tree" in argv:
            files = self.trees.get(argv[argv.index("ls-tree") + 2], {})
            lines = [f"100644 blob {blob_id(data)}\t{path}" for path, data in files.items()]
            return 0, "".join(line + "\n" for line in lines), ""
        if argv[:2] == ["agent-dgx", "inspect"]:
            return 0, json.dumps(self._inspect()), ""
        return 0, "", ""

    def _inspect(self) -> dict[str, Any]:
        created = self.ran("agent-dgx", "run")
        retired = self.ran("agent-dgx", "session", "rm")
        if created:
            head = self.new_head
        elif self.old and not retired:
            head = BASE
        else:
            return {"id": SESSION, "manifest": None, "sandbox": None}
        return {
            "id": SESSION,
            "manifest": {"source_repository": {"head": head}, "status": "prepared"},
            "sandbox": {"status": "running"},
        }

    def ran(self, *prefix: str) -> bool:
        return any(argv[: len(prefix)] == list(prefix) for argv, _ in self.calls)

    def changes(self) -> list[list[str]]:
        """Every call that changes something: not a read, not a check."""
        reads = ("rev-parse", "log", "status", "ls-tree", "cat-file", "is-active", "inspect")
        return [argv for argv, _ in self.calls if not any(r in argv for r in reads)]


def host(tmp_path: Path, fake: Fake, *, dry_run: bool = False, herdr: bool = True) -> Host:
    return Host(
        repo=tmp_path / "repo",
        host_checkout=tmp_path / "host-checkout",
        workspace=tmp_path / "workspace",
        backups=tmp_path / "backups",
        run=fake,
        env={"HERDR_PANE_ID": "w1:p1"} if herdr else {},
        which=lambda name: f"/usr/bin/{name}",
        now=lambda: datetime(2026, 9, 30, 12, 0, tzinfo=UTC),
        dry_run=dry_run,
    )


def workspace_note(tmp_path: Path, text: bytes) -> None:
    path = tmp_path / "workspace" / NOTE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text)


def test_blob_id_is_git_s_object_id() -> None:
    data = b"# notes\n\nmotion wording\n"
    git = shutil.which("git")
    assert git is not None
    done = subprocess.run(  # intentional - checks blob_id against git itself  # noqa: S603
        [git, "hash-object", "--no-filters", "--stdin"], input=data, capture_output=True, check=True
    )
    assert blob_id(data) == done.stdout.decode().strip()


@pytest.mark.parametrize(
    ("fake", "herdr", "says"),
    [
        (Fake(), False, "herdr"),
        (Fake(renderer="active"), True, "synthbench-renderer.service"),
        (Fake(host_dirty=" M synthbench/cli.py\n"), True, "uncommitted"),
    ],
)
def test_up_refuses_before_changing_anything(
    tmp_path: Path, fake: Fake, herdr: bool, says: str
) -> None:
    with pytest.raises(Refused, match=says):
        up(host(tmp_path, fake, herdr=herdr), ref="HEAD", discard_notes=False, renderer=True)
    assert fake.changes() == []
    assert not (tmp_path / "backups").exists()


def test_notes_the_agent_changed_block_retirement_and_are_copied_out(tmp_path: Path) -> None:
    workspace_note(tmp_path, b"clips-1: gestures morph\n")
    fake = Fake(trees={BASE: {NOTE: b"empty log\n"}, TARGET: {NOTE: b"empty log\n"}})
    with pytest.raises(Refused, match=NOTE):
        up(host(tmp_path, fake), ref="HEAD", discard_notes=False, renderer=True)
    assert fake.changes() == []
    copies = list((tmp_path / "backups").rglob("h3-prompt-notes.md"))
    assert [c.read_bytes() for c in copies] == [b"clips-1: gestures morph\n"]


def test_a_note_the_agent_created_blocks_retirement(tmp_path: Path) -> None:
    workspace_note(tmp_path, b"new file\n")
    with pytest.raises(Refused, match=NOTE):
        down(host(tmp_path, Fake()), ref="HEAD", discard_notes=False)


@pytest.mark.parametrize(
    ("base", "target"),
    [
        (b"empty log\n", b"clips-1: gestures morph\n"),  # already committed to the target
        (b"clips-1: gestures morph\n", b"owner edit\n"),  # the agent never touched it
    ],
)
def test_notes_the_new_agent_keeps_or_never_had_do_not_block(
    tmp_path: Path, base: bytes, target: bytes
) -> None:
    workspace_note(tmp_path, b"clips-1: gestures morph\n")
    fake = Fake(trees={BASE: {NOTE: base}, TARGET: {NOTE: target}})
    down(host(tmp_path, fake), ref="HEAD", discard_notes=False)
    assert fake.ran("agent-dgx", "session", "rm", SESSION, "--force")


def test_discard_notes_retires_anyway_after_the_copy(tmp_path: Path) -> None:
    workspace_note(tmp_path, b"clips-1: gestures morph\n")
    fake = Fake()
    down(host(tmp_path, fake), ref="HEAD", discard_notes=True)
    assert fake.changes() == [
        ["agent-dgx", "stop", SESSION],
        ["agent-dgx", "session", "rm", SESSION, "--force"],
    ]
    assert list((tmp_path / "backups").rglob("h3-prompt-notes.md"))


def test_down_without_a_session_changes_nothing(tmp_path: Path) -> None:
    fake = Fake(old=False)
    down(host(tmp_path, fake), ref="HEAD", discard_notes=False)
    assert fake.changes() == []


def test_up_runs_every_step_in_order(tmp_path: Path) -> None:
    fake = Fake()
    h = host(tmp_path, fake)
    up(h, ref="HEAD", discard_notes=False, renderer=True)
    ws = f"cd {h.workspace} && "
    assert fake.changes() == [
        ["agent-dgx", "stop", SESSION],
        ["agent-dgx", "session", "rm", SESSION, "--force"],
        ["git", "-C", str(h.host_checkout), "checkout", "--detach", TARGET],
        ["uv", "sync", "--frozen"],
        [str(h.host_checkout / ".venv/bin/python"), "-m", "synthbench.host.units", "install"],
        ["systemctl", "--user", "restart", GUARD],
        ["agent-dgx", "run", SESSION, "--agent", "claude", "--endpoint", "dgx"]
        + [arg for mount in MOUNTS for arg in ("--mount", mount)]
        + ["--split"],
        ["sbx", "exec", SANDBOX, "sudo", "apt-get", "install", "-y", *APT_LIBS],
        ["sbx", "exec", SANDBOX, "bash", "-lc", ws + "uv sync --frozen"],
        [
            "sbx",
            "exec",
            SANDBOX,
            "bash",
            "-lc",
            ws + 'uv run python -c "import synthbench.cli, av"',
        ],
        ["systemctl", "--user", "start", RENDERER],
        ["sbx", "exec", SANDBOX, "bash", "-lc", ws + "uv run python -m synthbench doctor"],
    ]
    cwd = {" ".join(argv[:2]): where for argv, where in fake.calls}
    assert cwd["uv sync"] == h.host_checkout
    assert cwd["agent-dgx run"] == h.host_checkout  # the clone's source is the host checkout


def test_up_stops_when_the_new_agent_is_not_at_the_commit(tmp_path: Path) -> None:
    fake = Fake(new_head="c" * 40)
    with pytest.raises(Refused, match="c" * 8):
        up(host(tmp_path, fake), ref="HEAD", discard_notes=False, renderer=True)
    assert not fake.ran("sbx")
    assert not fake.ran("systemctl", "--user", "start")


def test_a_failed_step_stops_and_names_it(tmp_path: Path) -> None:
    fake = Fake(fail="synthbench.host.units")
    with pytest.raises(Refused, match="install the host units"):
        up(host(tmp_path, fake), ref="HEAD", discard_notes=False, renderer=True)
    assert not fake.ran("systemctl", "--user", "restart")
    assert not fake.ran("agent-dgx", "run")


def test_no_renderer_skips_the_renderer_and_doctor(tmp_path: Path) -> None:
    fake = Fake()
    up(host(tmp_path, fake), ref="HEAD", discard_notes=False, renderer=False)
    assert not fake.ran("systemctl", "--user", "start")
    assert not any("doctor" in " ".join(argv) for argv in fake.changes())


def test_dry_run_only_reads(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace_note(tmp_path, b"clips-1: gestures morph\n")
    fake = Fake(trees={BASE: {NOTE: b"x\n"}, TARGET: {NOTE: b"clips-1: gestures morph\n"}})
    up(host(tmp_path, fake, dry_run=True), ref="HEAD", discard_notes=False, renderer=True)
    assert fake.changes() == []
    assert not (tmp_path / "backups").exists()
    out = capsys.readouterr().out
    assert "agent-dgx run synthbench-gen" in out
    assert "systemctl --user start synthbench-renderer.service" in out


def test_a_failed_copy_stops_retirement(tmp_path: Path) -> None:
    workspace_note(tmp_path, b"clips-1: gestures morph\n")
    (tmp_path / "backups").write_text("a file where the backups directory should be")
    fake = Fake()
    with pytest.raises(Refused, match="could not copy"):
        down(host(tmp_path, fake), ref="HEAD", discard_notes=True)
    assert fake.changes() == []
