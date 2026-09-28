"""Offline validation of an API-format graph against ComfyUI's /object_info.

Catches, without a GPU: unknown node types, missing/unknown inputs, combo
values the server would reject (including model files missing from the
farm), dangling links, and link type mismatches. Both combo formats are
understood: [[options...], {...}] and ["COMBO", {"options": [...]}].
"""

from __future__ import annotations

from typing import Any

from synthbench.generate.comfy.client import Graph


def _is_link(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    )


def _options(spec: list[Any]) -> list[Any] | None:
    if isinstance(spec[0], list):
        return spec[0]
    if spec[0] == "COMBO" and len(spec) > 1 and isinstance(spec[1], dict):
        options = spec[1].get("options")
        return options if isinstance(options, list) else None
    return None


def _types(declared: Any) -> set[str]:
    return {t.strip() for t in str(declared).split(",")}


def validate_graph(graph: Graph, object_info: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for node_id, node in graph.items():
        class_type = node.get("class_type")
        info = object_info.get(str(class_type))
        if info is None:
            errors.append(f"{node_id}: unknown class_type {class_type!r}")
            continue
        declared = info.get("input", {})
        required: dict[str, Any] = declared.get("required", {})
        optional: dict[str, Any] = declared.get("optional", {})
        inputs: dict[str, Any] = node.get("inputs", {})
        where = f"{node_id} ({class_type})"
        errors += [
            f"{where}: missing required input {name!r}" for name in required if name not in inputs
        ]
        for name, value in inputs.items():
            spec = required.get(name) or optional.get(name)
            if spec is None:
                errors.append(f"{where}: unknown input {name!r}")
                continue
            if _is_link(value):
                errors += _check_link(where, name, value, spec, graph, object_info)
                continue
            options = _options(spec)
            if options is not None and value not in options:
                errors.append(f"{where}: {name}={value!r} is not an allowed value")
    return errors


def _check_link(
    where: str,
    name: str,
    value: list[Any],
    spec: list[Any],
    graph: Graph,
    object_info: dict[str, Any],
) -> list[str]:
    source_id, index = value
    source = graph.get(source_id)
    if source is None:
        return [f"{where}: {name} links to missing node {source_id!r}"]
    source_info = object_info.get(str(source.get("class_type")))
    if source_info is None:
        return []  # already reported as an unknown class_type
    outputs: list[Any] = source_info.get("output", [])
    if index >= len(outputs):
        return [
            f"{where}: {name} links to output {index} of {source_id!r} "
            f"({source['class_type']} has {len(outputs)})"
        ]
    wanted, given = _types(spec[0]), _types(outputs[index])
    if "*" in wanted or "*" in given or wanted & given or _options(spec) is not None:
        return []
    return [f"{where}: {name} expects {spec[0]} but {source_id!r} gives {outputs[index]}"]
