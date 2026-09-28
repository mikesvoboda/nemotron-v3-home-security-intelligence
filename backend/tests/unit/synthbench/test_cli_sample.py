"""`python -m synthbench sample` (agent-driven design §3 step 1)."""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
from synthbench import cli
from synthbench.contract.corpus import TIER_B_RENDER_SIZE, BatchRecord, CorpusManifest
from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore
from synthbench.taxonomy.model import taxonomy_sha256
from synthbench.taxonomy.sampler import default_seed

REPO_ROOT = Path(__file__).resolve().parents[4]


def _run(root: Path, *argv: str) -> int:
    return cli.main(["sample", *argv], env={"SYNTHBENCH_ROOT": str(root)})


def _exit_code(root: Path, *argv: str) -> int:
    """argparse raises SystemExit for usage errors; the command returns its code."""
    try:
        return _run(root, *argv)
    except SystemExit as stop:
        return int(stop.code or 0)


def _store(root: Path) -> CorpusStore:
    return CorpusStore(root / "corpus", "tierb-v0")


def test_sample_writes_manifest_batch_specs_and_index(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(tmp_path, "--batch", "pilot-1", "--n", "10") == cli.EXIT_OK
    store = _store(tmp_path)
    record = store.read(store.batch_file("pilot-1"), BatchRecord)
    assert (record.n, record.seed, record.prior_counts) == (10, default_seed("pilot-1"), {})
    specs = [store.read(store.spec_file(event), Spec) for event in record.event_ids]
    assert [s.event_id for s in specs] == [f"B-pilot-1-{i:03d}" for i in range(10)]
    assert all(s.prompt is None for s in specs)
    manifest = store.read(store.manifest_file, CorpusManifest)
    assert manifest.taxonomy_sha256 == taxonomy_sha256()
    assert manifest.render_size == TIER_B_RENDER_SIZE
    index = store.latest_index()
    assert sorted(index) == list(record.event_ids)
    assert {row.status for row in index.values()} == {"sampled"}
    out = capsys.readouterr().out
    assert "batch pilot-1" in out and "10 events" in out


def test_the_same_request_gives_byte_identical_specs(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    for root in (first, second):
        assert _run(root, "--batch", "pilot-1", "--n", "12", "--seed", "5") == cli.EXIT_OK
    specs = sorted((first / "corpus").rglob("spec.json"))
    assert len(specs) == 12
    for path in specs:
        assert path.read_bytes() == (second / path.relative_to(first)).read_bytes()


def test_a_rerun_completes_a_partly_written_batch(tmp_path: Path) -> None:
    assert _run(tmp_path, "--batch", "pilot-1", "--n", "5") == cli.EXIT_OK
    lost = _store(tmp_path).spec_file("B-pilot-1-003")
    original = lost.read_bytes()
    lost.unlink()  # as if the first run died before writing it
    assert _run(tmp_path, "--batch", "pilot-1", "--n", "5") == cli.EXIT_OK
    assert lost.read_bytes() == original
    assert len(_store(tmp_path).latest_index()) == 5


def test_a_rerun_with_other_parameters_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(tmp_path, "--batch", "pilot-1", "--n", "5") == cli.EXIT_OK
    assert _run(tmp_path, "--batch", "pilot-1", "--n", "6") == cli.EXIT_ERROR
    assert "already exists" in capsys.readouterr().err


def test_a_hand_edited_spec_stops_the_rerun(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(tmp_path, "--batch", "pilot-1", "--n", "3") == cli.EXIT_OK
    path = _store(tmp_path).spec_file("B-pilot-1-001")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["scene_time"] = "03:33" if data["scene_time"] != "03:33" else "04:44"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert _run(tmp_path, "--batch", "pilot-1", "--n", "3") == cli.EXIT_ASK
    assert "ask the owner" in capsys.readouterr().err


def test_a_changed_taxonomy_needs_a_new_corpus_version(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = _store(tmp_path)
    store.write_new(
        store.manifest_file,
        CorpusManifest(
            version="tierb-v0",
            taxonomy_sha256="0" * 64,
            render_size=TIER_B_RENDER_SIZE,
            created="2026-09-28T00:00:00+00:00",
        ),
    )
    assert _run(tmp_path, "--batch", "pilot-1", "--n", "2") == cli.EXIT_ASK
    assert "new corpus version" in capsys.readouterr().err
    assert not store.batch_dir("pilot-1").exists()


def test_a_second_batch_records_the_first_batch_counts(tmp_path: Path) -> None:
    assert _run(tmp_path, "--batch", "pilot-1", "--n", "20") == cli.EXIT_OK
    assert _run(tmp_path, "--batch", "batch-2", "--n", "20") == cli.EXIT_OK
    store = _store(tmp_path)
    first = store.read(store.batch_file("pilot-1"), BatchRecord)
    second = store.read(store.batch_file("batch-2"), BatchRecord)
    first_counts = Counter(
        store.read(store.spec_file(e), Spec).cell.scenario for e in first.event_ids
    )
    assert second.prior_counts == dict(first_counts)
    assert len(store.latest_index()) == 40


def test_only_limits_the_scenarios(tmp_path: Path) -> None:
    argv = ("--batch", "pilot-1", "--n", "6", "--only", "knife_visible,firearm_visible")
    assert _run(tmp_path, *argv) == cli.EXIT_OK
    store = _store(tmp_path)
    scenarios = {
        store.read(store.spec_file(f"B-pilot-1-{i:03d}"), Spec).cell.scenario for i in range(6)
    }
    assert scenarios == {"knife_visible", "firearm_visible"}


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (("--batch", "Pilot 1", "--n", "5"), "must match"),
        (("--batch", "pilot-1", "--n", "5", "--only", "nope"), "unknown scenario"),
        (("--batch", "pilot-1", "--n", "0"), "1..500"),
        (
            (
                "--batch",
                "pilot-1",
            ),
            "required",
        ),
    ],
)
def test_bad_requests_exit_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], argv: tuple[str, ...], message: str
) -> None:
    assert _exit_code(tmp_path, *argv) == cli.EXIT_ERROR
    assert message in capsys.readouterr().err
    assert not (tmp_path / "corpus" / "tierb-v0" / "batches").exists()


def test_python_dash_m_synthbench_runs() -> None:
    done = subprocess.run(  # intentional - tests the real python -m entry point
        [sys.executable, "-m", "synthbench", "sample", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert "--batch" in done.stdout
