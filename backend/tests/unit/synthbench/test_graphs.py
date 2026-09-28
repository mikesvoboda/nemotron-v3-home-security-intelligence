"""Every registered graph builder validates against the captured /object_info (v0.37.0 + our farm)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from synthbench.generate.comfy import graphs
from synthbench.generate.comfy.validate import validate_graph

REPO_ROOT = Path(__file__).resolve().parents[4]
SNAPSHOT = REPO_ROOT / "synthbench" / "generate" / "comfy" / "object_info.v0.37.0.json"


@pytest.fixture(scope="module")
def object_info() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(SNAPSHOT.read_text())
    return data


def test_registries_cover_the_approved_slate() -> None:
    assert set(graphs.T2I_BUILDERS) == {
        "flux2-dev",
        "flux2-klein-4b",
        "qwen-image-2.1",
        "z-image-turbo",
        "hidream-i1-full",
        "ideogram-4",
    }
    assert set(graphs.EDIT_BUILDERS) == {"qwen-image-2.1", "flux2-dev", "flux2-klein-4b"}
    assert set(graphs.I2V_BUILDERS) == {"ltx-2.5", "wan2.2-i2v"}
    assert len(graphs.sample_graphs()) == 11


@pytest.mark.parametrize("key", sorted(graphs.sample_graphs()))
def test_every_sample_graph_validates(key: str, object_info: dict[str, Any]) -> None:
    assert validate_graph(graphs.sample_graphs()[key], object_info) == []


@pytest.mark.parametrize("key", sorted(graphs.sample_graphs()))
def test_every_graph_saves_under_its_model_prefix(key: str) -> None:
    model = key.split(":", 1)[1]
    savers = [
        n
        for n in graphs.sample_graphs()[key].values()
        if n["class_type"] in {"SaveImage", "SaveVideo"}
    ]
    assert len(savers) == 1
    assert savers[0]["inputs"]["filename_prefix"] == f"synthbench/{model}"


def test_builders_thread_their_arguments() -> None:
    graph = graphs.T2I_BUILDERS["z-image-turbo"]("a porch", seed=7, width=1920, height=1088)
    values = [v for node in graph.values() for v in node["inputs"].values()]
    assert "a porch" in values and 7 in values and 1920 in values and 1088 in values


def _values(graph: graphs.Graph) -> list[Any]:
    return [v for node in graph.values() for v in node["inputs"].values()]


def _loaded_images(graph: graphs.Graph) -> list[str]:
    return sorted(n["inputs"]["image"] for n in graph.values() if n["class_type"] == "LoadImage")


@pytest.mark.parametrize("model", sorted(graphs.T2I_BUILDERS))
def test_t2i_builders_thread_prompt_and_seed(model: str) -> None:
    graph = graphs.T2I_BUILDERS[model]("a porch", seed=7, width=1920, height=1088)
    values = _values(graph)
    assert "a porch" in values and 7 in values


@pytest.mark.parametrize("model", sorted(graphs.EDIT_BUILDERS))
def test_edit_builders_load_one_image_per_reference(
    model: str, object_info: dict[str, Any]
) -> None:
    graph = graphs.EDIT_BUILDERS[model](
        "the same man", images=["id.png", "scene.png"], seed=7, width=1920, height=1088
    )
    assert _loaded_images(graph) == ["id.png", "scene.png"]
    values = _values(graph)
    assert "the same man" in values and 7 in values and 1920 in values and 1088 in values
    assert validate_graph(graph, object_info) == []


@pytest.mark.parametrize("model", sorted(graphs.EDIT_BUILDERS))
def test_edit_builders_need_a_reference_image(model: str) -> None:
    with pytest.raises(ValueError, match="reference image"):
        graphs.EDIT_BUILDERS[model]("x", images=[], seed=1, width=512, height=288)


@pytest.mark.parametrize("model", sorted(graphs.I2V_BUILDERS))
def test_i2v_builders_thread_keyframe_and_frames(model: str) -> None:
    graph = graphs.I2V_BUILDERS[model](
        "he walks", image="key.png", seed=7, width=1280, height=704, frames=97
    )
    assert _loaded_images(graph) == ["key.png"]
    values = _values(graph)
    assert "he walks" in values and 7 in values and 97 in values
