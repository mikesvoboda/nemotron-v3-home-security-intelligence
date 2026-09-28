"""smoke.main against a fake ComfyClient: one output file per graph; failures reported, not fatal."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import pytest
from synthbench.generate.comfy import smoke
from synthbench.generate.comfy.client import ComfyError


class FakeClient:
    graphs: ClassVar[list[dict[str, Any]]] = []

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def upload_image(self, path: Path) -> str:
        return f"uploaded-{path.name}"

    def run(self, graph: dict[str, Any], *, timeout_s: float) -> list[bytes]:
        FakeClient.graphs.append(graph)
        classes = {n["class_type"] for n in graph.values()}
        if "WanImageToVideo" in classes:
            raise ComfyError("p1 failed at node 13 (KSamplerAdvanced): OutOfMemoryError: oom")
        return [b"media"]

    def close(self) -> None:
        pass


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    FakeClient.graphs = []
    monkeypatch.setattr(smoke, "ComfyClient", FakeClient)
    monkeypatch.setenv("SYNTHBENCH_ROOT", str(tmp_path))
    return tmp_path / "smoke"


def test_only_runs_the_named_keys_and_writes_their_outputs(
    fake: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert smoke.main(["--only", "t2i:z-image-turbo,edit:flux2-klein-4b"]) == 0
    assert sorted(p.name for p in fake.iterdir()) == [
        "edit_flux2-klein-4b.png",
        "t2i_z-image-turbo.png",
    ]
    out = capsys.readouterr().out
    assert "OK   edit:flux2-klein-4b" in out and "OK   t2i:z-image-turbo" in out
    edit = FakeClient.graphs[0]
    loads = [n["inputs"]["image"] for n in edit.values() if n["class_type"] == "LoadImage"]
    assert loads == ["uploaded-smoke_ref.png"]


def test_a_failing_graph_is_reported_and_the_run_continues(
    fake: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert smoke.main(["--only", "i2v:wan2.2-i2v,i2v:ltx-2.5"]) == 1
    assert sorted(p.name for p in fake.iterdir()) == ["i2v_ltx-2.5.mp4"]
    out = capsys.readouterr().out
    assert "FAIL i2v:wan2.2-i2v" in out and "OutOfMemoryError" in out


def test_unknown_only_keys_are_rejected_before_any_work(
    fake: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        smoke.main(["--only", "i2v:ltx-2.5,i2v:wan2.2_i2v,t2i:nope"])
    assert exit_info.value.code == 2
    err = capsys.readouterr().err
    assert "unknown --only key(s): i2v:wan2.2_i2v, t2i:nope" in err
    assert "i2v:wan2.2-i2v" in err and "t2i:z-image-turbo" in err  # the valid keys are listed
    assert FakeClient.graphs == []
    assert not fake.exists()


def _latent_size(graph: dict[str, Any], class_type: str) -> tuple[int, int]:
    [node] = [n for n in graph.values() if n["class_type"] == class_type]
    return node["inputs"]["width"], node["inputs"]["height"]


def test_i2v_smokes_at_a_size_whose_ltx_stage_one_stays_on_the_32_pixel_grid(fake: Path) -> None:
    assert smoke.main(["--only", "i2v:ltx-2.5,t2i:z-image-turbo"]) == 0
    ltx, z_image = FakeClient.graphs
    assert _latent_size(ltx, "EmptyLTXVLatentVideo") == (256, 160)  # half of 512x320
    assert _latent_size(z_image, "EmptySD3LatentImage") == (512, 288)
    assert smoke.SMOKE_SIZES == {"t2i": (512, 288), "edit": (512, 288), "i2v": (512, 320)}
