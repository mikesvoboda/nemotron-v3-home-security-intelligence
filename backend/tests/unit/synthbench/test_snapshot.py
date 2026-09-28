"""snapshot.filtered: keep only the node types the builders use; free the LoadImage name."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from synthbench.generate.comfy import graphs, snapshot


def test_filtered_keeps_only_the_node_types_the_builders_use() -> None:
    used = {n["class_type"] for g in graphs.sample_graphs().values() for n in g.values()}
    info: dict[str, Any] = {name: {"input": {"required": {}}, "output": []} for name in used}
    info["LoadImage"] = {"input": {"required": {"image": [["example.png"], {}]}}, "output": []}
    info["UnusedNode"] = {"input": {}, "output": []}
    kept = snapshot.filtered(info)
    assert set(kept) == used
    assert list(kept) == sorted(kept)


def test_filtered_turns_the_load_image_file_list_into_a_free_string() -> None:
    info: dict[str, Any] = {
        "LoadImage": {"input": {"required": {"image": [["example.png"], {}]}}, "output": []}
    }
    assert snapshot.filtered(info)["LoadImage"]["input"]["required"]["image"] == ["STRING", {}]


class FakeClient:
    closed = False

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def object_info(self) -> dict[str, Any]:
        return {"SaveImage": {"input": {"required": {}}, "output": []}, "Other": {}}

    def close(self) -> None:
        FakeClient.closed = True


def test_main_writes_the_filtered_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "object_info.json"
    monkeypatch.setattr(snapshot, "ComfyClient", FakeClient)
    monkeypatch.setattr(snapshot, "OUT", out)
    assert snapshot.main() == 0
    assert json.loads(out.read_text()) == {"SaveImage": {"input": {"required": {}}, "output": []}}
    assert out.read_text().endswith("}\n")
    assert FakeClient.closed
    assert f"wrote {out}" in capsys.readouterr().out
