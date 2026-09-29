"""`camera --batch <b>` (agent-driven design §3 step 5)."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest
from PIL import Image
from synthbench import cli
from synthbench.contract.provenance import Provenance, still_name
from synthbench.generate.camera.model import overlay_time

from backend.tests.unit.synthbench import helpers as h


def _camera(root: Path) -> int:
    return h.run(root, "camera", "--batch", "pilot-1")


def test_camera_makes_a_still_for_each_new_render(tmp_path: Path) -> None:
    specs = h.rendered_batch(tmp_path, n=2)
    assert _camera(tmp_path) == cli.EXIT_OK
    store = h.store(tmp_path)
    for spec in specs:
        attempt = store.read(store.provenance_file(spec.event_id), Provenance).attempts[-1]
        assert attempt.still is not None
        assert attempt.still.path == still_name(1, attempt.seed)
        assert attempt.camera_params == "default-v1"
        assert attempt.overlay_time == overlay_time(
            spec.scene_time, spec.cell.weather, attempt.seed
        )
        data = (store.event_dir(spec.event_id) / attempt.still.path).read_bytes()
        assert hashlib.sha256(data).hexdigest() == attempt.still.sha256
        with Image.open(io.BytesIO(data)) as image:
            assert image.size == (1920, 1080)
    assert h.run(tmp_path, "check", "--batch", "pilot-1") == cli.EXIT_OK  # sha256s verified


def test_a_rerun_makes_nothing_new(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    h.rendered_batch(tmp_path, n=1)
    assert _camera(tmp_path) == cli.EXIT_OK
    capsys.readouterr()
    assert _camera(tmp_path) == cli.EXIT_OK
    assert "0 still(s) made now" in capsys.readouterr().out


def test_a_render_that_no_longer_matches_its_sha256_stops_camera(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (spec,) = h.rendered_batch(tmp_path, n=1)
    store = h.store(tmp_path)
    attempt = store.read(store.provenance_file(spec.event_id), Provenance).attempts[-1]
    assert attempt.render is not None
    (store.event_dir(spec.event_id) / attempt.render.path).write_bytes(h.png(color=(0, 0, 0)))
    assert _camera(tmp_path) == cli.EXIT_ASK
    assert "does not match its recorded sha256" in capsys.readouterr().err


def test_camera_waits_for_renders(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    h.frozen_batch(tmp_path, n=2)
    assert _camera(tmp_path) == cli.EXIT_OK
    assert "0 still(s) made now; 2 attempt(s) still await a render" in capsys.readouterr().out


def test_a_failed_event_does_not_await_a_render(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An event `render` gave up on (index status `failed`) never gets a render: `camera` must
    not count it as waiting for one."""
    specs = h.frozen_batch(tmp_path, n=2)
    store = h.store(tmp_path)
    row = store.latest_index()[specs[0].event_id]
    store.append_index(
        [row.model_copy(update={"status": "failed", "time": "2026-09-29T10:00:00Z"})]
    )
    assert _camera(tmp_path) == cli.EXIT_OK
    assert "0 still(s) made now; 1 attempt(s) still await a render" in capsys.readouterr().out
