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


def _loaded_images(graph: graphs.Graph) -> list[str]:
    return sorted(n["inputs"]["image"] for n in graph.values() if n["class_type"] == "LoadImage")


# Two distinctive argument sets. No template constant equals any of these values, and every
# size is a multiple of 64, so LTX's half-size stage 1 stays on its 32-pixel grid and
# Ideogram's 16-pixel rounding is the identity.
ARGS_A: dict[str, Any] = {
    "prompt": "a porch at noon",
    "seed": 918273645,
    "width": 1344,
    "height": 768,
    "frames": 121,
}
ARGS_B: dict[str, Any] = {
    "prompt": "a driveway at dusk",
    "seed": 546372819,
    "width": 1152,
    "height": 896,
    "frames": 89,
}

Site = tuple[str, str]  # (class_type, input name)
_FLUX_SIZE: list[Site] = [("EmptyFlux2LatentImage", "{}"), ("Flux2Scheduler", "{}")]


def _size(*sites: tuple[str, str]) -> dict[str, list[Site]]:
    return {
        "width": sorted((c, i.format("width")) for c, i in sites),
        "height": sorted((c, i.format("height")) for c, i in sites),
    }


# Where each builder must route each argument: nowhere else, and never dropped.
ROUTES: dict[str, dict[str, list[Site]]] = {
    "t2i:z-image-turbo": {
        "prompt": [("CLIPTextEncode", "text")],
        "seed": [("KSampler", "seed")],
        **_size(("EmptySD3LatentImage", "{}")),
    },
    "t2i:flux2-dev": {
        "prompt": [("CLIPTextEncode", "text")],
        "seed": [("RandomNoise", "noise_seed")],
        **_size(*_FLUX_SIZE),
    },
    "t2i:flux2-klein-4b": {
        "prompt": [("CLIPTextEncode", "text")],
        "seed": [("RandomNoise", "noise_seed")],
        **_size(*_FLUX_SIZE),
    },
    "t2i:qwen-image-2.1": {
        "prompt": [("TextEncodeQwenImage21", "prompt")],
        "seed": [("KSampler", "seed")],
        **_size(("EmptyLatentImage", "{}")),
    },
    "t2i:hidream-i1-full": {
        "prompt": [("CLIPTextEncode", "text")],
        "seed": [("KSampler", "seed")],
        **_size(("EmptySD3LatentImage", "{}")),
    },
    "t2i:ideogram-4": {
        "prompt": [("CLIPTextEncode", "text")],
        "seed": [("RandomNoise", "noise_seed")],
        **_size(("EmptyFlux2LatentImage", "{}"), ("Ideogram4Scheduler", "{}")),
    },
    "edit:qwen-image-2.1": {
        "prompt": [("TextEncodeQwenImage21", "prompt")],
        "seed": [("KSampler", "seed")],
        **_size(("EmptyLatentImage", "{}")),
    },
    "edit:flux2-dev": {
        "prompt": [("CLIPTextEncode", "text")],
        "seed": [("RandomNoise", "noise_seed")],
        **_size(*_FLUX_SIZE),
    },
    "edit:flux2-klein-4b": {
        "prompt": [("CLIPTextEncode", "text")],
        "seed": [("RandomNoise", "noise_seed")],
        **_size(*_FLUX_SIZE),
    },
    "i2v:ltx-2.5": {  # stage 1 samples at half size; the x2 latent upsampler restores it
        "prompt": [("CLIPTextEncode", "text")],
        "seed": [("RandomNoise", "noise_seed")],
        **_size(("EmptyLTXVLatentVideo", "{}")),
        "frames": [("EmptyLTXVLatentVideo", "length"), ("LTXVEmptyLatentAudio", "frames_number")],
    },
    "i2v:wan2.2-i2v": {
        "prompt": [("CLIPTextEncode", "text")],
        "seed": [("KSamplerAdvanced", "noise_seed")],
        **_size(("WanImageToVideo", "{}")),
        "frames": [("WanImageToVideo", "length")],
    },
}


def _build(key: str, args: dict[str, Any]) -> graphs.Graph:
    kind, model = key.split(":", 1)
    common = {"seed": args["seed"], "width": args["width"], "height": args["height"]}
    if kind == "t2i":
        return graphs.T2I_BUILDERS[model](args["prompt"], **common)
    if kind == "edit":
        return graphs.EDIT_BUILDERS[model](args["prompt"], images=["id.png"], **common)
    return graphs.I2V_BUILDERS[model](
        args["prompt"], image="key.png", frames=args["frames"], **common
    )


def _expected_value(key: str, arg: str, args: dict[str, Any]) -> Any:
    if key == "i2v:ltx-2.5" and arg in {"width", "height"}:
        return args[arg] // 2
    return args[arg]


def _sites(graph: graphs.Graph, value: Any) -> list[Site]:
    """Every (class_type, input) holding exactly `value`; type-strict, so 7 never matches 7.0."""
    return sorted(
        (node["class_type"], name)
        for node in graph.values()
        for name, v in node["inputs"].items()
        if type(v) is type(value) and v == value
    )


def test_routes_cover_every_registered_builder() -> None:
    assert set(ROUTES) == set(graphs.sample_graphs())


@pytest.mark.parametrize("key", sorted(ROUTES))
@pytest.mark.parametrize("args", [ARGS_A, ARGS_B], ids=["A", "B"])
def test_each_argument_lands_exactly_in_its_sampler_and_latent_inputs(
    key: str, args: dict[str, Any]
) -> None:
    graph = _build(key, args)
    for arg, sites in ROUTES[key].items():
        assert _sites(graph, _expected_value(key, arg, args)) == sites, arg


@pytest.mark.parametrize("key", sorted(ROUTES))
def test_only_the_routed_inputs_change_with_the_arguments(key: str) -> None:
    a, b = _build(key, ARGS_A), _build(key, ARGS_B)
    assert {k: sorted(n["inputs"]) for k, n in a.items()} == {
        k: sorted(n["inputs"]) for k, n in b.items()
    }
    changed = sorted(
        (a[k]["class_type"], name)
        for k in a
        for name in a[k]["inputs"]
        if a[k]["inputs"][name] != b[k]["inputs"][name]
    )
    assert changed == sorted(site for sites in ROUTES[key].values() for site in sites)


def test_ltx_seeds_stage_one_and_keeps_the_template_fixed_stage_two_noise() -> None:
    graph = _build("i2v:ltx-2.5", ARGS_A)
    noise = {n["inputs"]["noise_seed"] for n in graph.values() if n["class_type"] == "RandomNoise"}
    assert noise == {ARGS_A["seed"], 42}
    [stage1] = [
        n
        for n in graph.values()
        if n["class_type"] == "SamplerCustomAdvanced"
        and graph[n["inputs"]["noise"][0]]["inputs"]["noise_seed"] == ARGS_A["seed"]
    ]
    [latent] = [n for n in graph.values() if n["class_type"] == "EmptyLTXVLatentVideo"]
    assert graph[stage1["inputs"]["sigmas"][0]]["inputs"]["sigmas"].startswith("1.0, ")
    assert (latent["inputs"]["width"], latent["inputs"]["height"]) == (672, 384)


def test_wan_seeds_the_high_noise_pass_that_adds_the_noise() -> None:
    graph = _build("i2v:wan2.2-i2v", ARGS_A)
    [seeded] = [
        n
        for n in graph.values()
        if n["class_type"] == "KSamplerAdvanced" and n["inputs"]["noise_seed"] == ARGS_A["seed"]
    ]
    assert seeded["inputs"]["add_noise"] == "enable"
    assert seeded["inputs"]["start_at_step"] == 0
    model = graph[seeded["inputs"]["model"][0]]
    lora = graph[model["inputs"]["model"][0]]
    assert "high_noise" in lora["inputs"]["lora_name"]


def test_ideogram_rounds_its_size_the_way_the_template_does() -> None:
    graph = graphs.T2I_BUILDERS["ideogram-4"]("x", seed=1, width=1000, height=200)
    [latent] = [n for n in graph.values() if n["class_type"] == "EmptyFlux2LatentImage"]
    assert (latent["inputs"]["width"], latent["inputs"]["height"]) == (1008, 256)


@pytest.mark.parametrize("model", sorted(graphs.EDIT_BUILDERS))
def test_edit_builders_load_one_image_per_reference(
    model: str, object_info: dict[str, Any]
) -> None:
    graph = graphs.EDIT_BUILDERS[model](
        "the same man", images=["id.png", "scene.png"], seed=7, width=1920, height=1088
    )
    assert _loaded_images(graph) == ["id.png", "scene.png"]
    assert validate_graph(graph, object_info) == []


@pytest.mark.parametrize("model", sorted(graphs.EDIT_BUILDERS))
def test_edit_builders_need_a_reference_image(model: str) -> None:
    with pytest.raises(ValueError, match="reference image"):
        graphs.EDIT_BUILDERS[model]("x", images=[], seed=1, width=512, height=288)


@pytest.mark.parametrize("model", sorted(graphs.I2V_BUILDERS))
def test_i2v_builders_load_the_keyframe(model: str) -> None:
    graph = graphs.I2V_BUILDERS[model](
        "he walks", image="key.png", seed=7, width=1280, height=704, frames=97
    )
    assert _loaded_images(graph) == ["key.png"]
