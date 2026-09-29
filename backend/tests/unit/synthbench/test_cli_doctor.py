"""`doctor` (owner request, 2026-09-28): checks a machine's prerequisites for a batch, and the
cv2 lazy import that lets every other command survive a sandbox without OpenCV's system
libraries.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from synthbench import cli
from synthbench.commands import doctor
from synthbench.commands.common import AskOwner
from synthbench.contract.corpus import TIER_B_RENDER_SIZE, CorpusManifest

from backend.tests.unit.synthbench import helpers as h

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_importing_cli_does_not_import_cv2() -> None:
    """Prerequisite for `doctor`: a sandbox without OpenCV's system libraries can still run
    every command but `camera`. cv2 is already loaded in the pytest process, so this runs the
    real check in a fresh subprocess (as test_cli_sample.py's `python -m` test does)."""
    done = subprocess.run(  # intentional - checks the real interpreter's sys.modules
        [sys.executable, "-c", "import sys, synthbench.cli; print('cv2' in sys.modules)"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "False"


def _ok_get(url: str, timeout: float) -> httpx.Response:
    return httpx.Response(200, json={"system": {}})


def _unreachable_get(url: str, timeout: float) -> httpx.Response:
    raise httpx.ConnectError("connection refused")


def _ok_cv2() -> None:
    return None


def _missing_cv2() -> None:
    raise ImportError("libxcb.so.1: cannot open shared object file")


def _deps(
    get: Callable[..., httpx.Response] = _ok_get,
    import_cv2: Callable[[], None] = _ok_cv2,
) -> doctor.Deps:
    return doctor.Deps(get=get, now=lambda: h.NOW, import_cv2=import_cv2)


def _corpus(root: Path) -> Path:
    directory = root / "corpus"
    directory.mkdir()
    return directory


def test_everything_ok_gives_six_ok_lines_and_exits_ok(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _corpus(tmp_path)
    h.flagship(tmp_path)
    assert doctor.execute(h.env(tmp_path), _deps()) == cli.EXIT_OK
    out = capsys.readouterr().out
    ok_lines = [line for line in out.splitlines() if line.startswith("ok")]
    assert len(ok_lines) == 6
    assert "ok   no corpus version yet: the first sample creates it and pins the taxonomy" in out
    assert "doctor: ready for every command" in out


def test_an_existing_matching_corpus_version_is_ok(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    h.sample(tmp_path)  # writes corpus.json, pinning the committed taxonomy
    h.flagship(tmp_path)
    assert doctor.execute(h.env(tmp_path), _deps()) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert f"ok   corpus version {h.VERSION} matches the committed taxonomy" in out


def test_an_unhealthy_flagship_prints_wait_and_still_exits_ok(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _corpus(tmp_path)
    h.flagship(tmp_path, healthy=False)
    assert doctor.execute(h.env(tmp_path), _deps()) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "WAIT flagship unhealthy or busy: render waits for it" in out
    assert "doctor: ready for every command" in out


def test_a_busy_flagship_also_waits(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _corpus(tmp_path)
    h.flagship(tmp_path, waiting=3)
    assert doctor.execute(h.env(tmp_path), _deps()) == cli.EXIT_OK
    assert "WAIT flagship unhealthy or busy: render waits for it" in capsys.readouterr().out


def test_opencv_missing_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _corpus(tmp_path)
    h.flagship(tmp_path)
    with pytest.raises(AskOwner, match="1 problem"):
        doctor.execute(h.env(tmp_path), _deps(import_cv2=_missing_cv2))
    out = capsys.readouterr().out
    assert (
        "FAIL opencv: the sandbox image lacks OpenCV's libraries: the owner runs sbx exec "
        "<sandbox> sudo apt-get install -y libxcb1 libgl1 libglib2.0-0"
    ) in out


def test_corpus_mount_missing_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    h.flagship(tmp_path)  # status is fine; tmp_path/corpus is never created
    with pytest.raises(AskOwner, match="1 problem"):
        doctor.execute(h.env(tmp_path), _deps())
    out = capsys.readouterr().out
    assert (
        "FAIL corpus mount: mount /synthbench/corpus read-write into the sandbox (never a path "
        "under /export)"
    ) in out


def test_guard_status_directory_missing_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _corpus(tmp_path)  # corpus is fine; tmp_path/status is never created
    with pytest.raises(AskOwner, match="1 problem"):
        doctor.execute(h.env(tmp_path), _deps())
    out = capsys.readouterr().out
    assert "FAIL guard status: mount /synthbench/status read-only into the sandbox" in out


def test_guard_status_file_missing_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _corpus(tmp_path)
    (tmp_path / "status").mkdir()  # mounted, but the guard has never written to it
    with pytest.raises(AskOwner, match="1 problem"):
        doctor.execute(h.env(tmp_path), _deps())
    out = capsys.readouterr().out
    assert (
        "FAIL guard status: the guard is not running: the owner runs systemctl --user enable "
        "--now synthbench-guard.service"
    ) in out


def test_guard_status_stale_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _corpus(tmp_path)
    h.flagship(tmp_path, time=h.NOW - timedelta(seconds=45))
    with pytest.raises(AskOwner, match="1 problem"):
        doctor.execute(h.env(tmp_path), _deps())
    out = capsys.readouterr().out
    assert (
        "FAIL guard status: the guard is not running: the owner runs systemctl --user enable "
        "--now synthbench-guard.service"
    ) in out


def test_renderer_unreachable_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _corpus(tmp_path)
    h.flagship(tmp_path)
    with pytest.raises(AskOwner, match="1 problem"):
        doctor.execute(h.env(tmp_path), _deps(get=_unreachable_get))
    out = capsys.readouterr().out
    assert (
        "FAIL renderer: the renderer is not running: the owner starts "
        'synthbench-renderer.service (docs/synthbench/operator-runbook.md, "The renderer")'
    ) in out


def test_corpus_version_mismatch_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _corpus(tmp_path)
    h.flagship(tmp_path)
    store = h.store(tmp_path)
    store.write_new(
        store.manifest_file,
        CorpusManifest(
            version=h.VERSION,
            taxonomy_sha256="0" * 64,
            render_size=TIER_B_RENDER_SIZE,
            created="2026-09-28T00:00:00+00:00",
        ),
    )
    with pytest.raises(AskOwner, match="1 problem"):
        doctor.execute(h.env(tmp_path), _deps())
    out = capsys.readouterr().out
    assert (
        f"FAIL corpus version {h.VERSION} was sampled from another taxonomy: ask the owner "
        "(a new corpus version)"
    ) in out


def test_a_corrupt_corpus_json_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _corpus(tmp_path)
    h.flagship(tmp_path)
    store = h.store(tmp_path)
    store.manifest_file.parent.mkdir(parents=True, exist_ok=True)
    store.manifest_file.write_text("not valid json", encoding="utf-8")
    with pytest.raises(AskOwner, match="1 problem"):
        doctor.execute(h.env(tmp_path), _deps())
    out = capsys.readouterr().out
    assert f"FAIL corpus version: cannot read {store.manifest_file}" in out


def test_every_check_runs_even_when_several_fail(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """doctor reports every gap in one run, not just the first (the agent should not have to
    re-run it once per fix)."""
    _corpus(tmp_path)
    h.flagship(tmp_path)
    with pytest.raises(AskOwner, match="2 problem"):
        doctor.execute(h.env(tmp_path), _deps(get=_unreachable_get, import_cv2=_missing_cv2))
    out = capsys.readouterr().out
    assert out.count("FAIL") == 2  # opencv and renderer; corpus mount and guard status are fine
