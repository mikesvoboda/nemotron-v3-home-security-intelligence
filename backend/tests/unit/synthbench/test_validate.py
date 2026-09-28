"""validate_graph: API graphs checked offline against /object_info."""

from __future__ import annotations

from typing import Any

from synthbench.generate.comfy.validate import validate_graph

INFO: dict[str, Any] = {
    "UNETLoader": {
        "input": {
            "required": {
                "unet_name": [["z.safetensors"], {}],
                "weight_dtype": [["default", "fp8_e4m3fn"], {}],
            }
        },
        "output": ["MODEL"],
    },
    "KSampler": {
        "input": {
            "required": {
                "model": ["MODEL", {}],
                "seed": ["INT", {"min": 0}],
                "sampler_name": ["COMBO", {"options": ["euler", "res_multistep"]}],
            },
            "optional": {"note": ["STRING", {}]},
        },
        "output": ["LATENT"],
    },
    "VAEDecode": {"input": {"required": {"samples": ["LATENT", {}]}}, "output": ["IMAGE"]},
    "AnyNode": {"input": {"required": {"x": ["*", {}]}}, "output": ["*"]},
}


def _good() -> dict[str, dict[str, Any]]:
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "z.safetensors", "weight_dtype": "default"},
        },
        "2": {
            "class_type": "KSampler",
            "inputs": {"model": ["1", 0], "seed": 3, "sampler_name": "euler"},
        },
        "3": {"class_type": "VAEDecode", "inputs": {"samples": ["2", 0]}},
    }


def test_a_valid_graph_has_no_errors() -> None:
    assert validate_graph(_good(), INFO) == []


def test_unknown_class_type() -> None:
    graph = _good() | {"4": {"class_type": "Nope", "inputs": {}}}
    assert validate_graph(graph, INFO) == ["4: unknown class_type 'Nope'"]


def test_missing_required_input() -> None:
    graph = _good()
    del graph["2"]["inputs"]["seed"]
    assert validate_graph(graph, INFO) == ["2 (KSampler): missing required input 'seed'"]


def test_unknown_input_name() -> None:
    graph = _good()
    graph["3"]["inputs"]["bogus"] = 1
    assert validate_graph(graph, INFO) == ["3 (VAEDecode): unknown input 'bogus'"]


def test_a_combo_value_must_be_allowed_in_both_formats() -> None:
    graph = _good()
    graph["1"]["inputs"]["unet_name"] = "missing.safetensors"
    graph["2"]["inputs"]["sampler_name"] = "dpm"
    errors = validate_graph(graph, INFO)
    assert "1 (UNETLoader): unet_name='missing.safetensors' is not an allowed value" in errors
    assert "2 (KSampler): sampler_name='dpm' is not an allowed value" in errors


def test_links_must_point_at_an_existing_node_and_output() -> None:
    graph = _good()
    graph["3"]["inputs"]["samples"] = ["9", 0]
    graph["2"]["inputs"]["model"] = ["1", 5]
    errors = validate_graph(graph, INFO)
    assert "3 (VAEDecode): samples links to missing node '9'" in errors
    assert "2 (KSampler): model links to output 5 of '1' (UNETLoader has 1)" in errors


def test_link_types_must_match_unless_wildcard() -> None:
    graph = _good()
    graph["3"]["inputs"]["samples"] = ["1", 0]
    graph["5"] = {"class_type": "AnyNode", "inputs": {"x": ["1", 0]}}
    assert validate_graph(graph, INFO) == [
        "3 (VAEDecode): samples expects LATENT but '1' gives MODEL"
    ]


def test_optional_inputs_are_accepted() -> None:
    graph = _good()
    graph["2"]["inputs"]["note"] = "hi"
    assert validate_graph(graph, INFO) == []
