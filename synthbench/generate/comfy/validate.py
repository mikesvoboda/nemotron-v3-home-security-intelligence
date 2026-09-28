"""Offline validation of an API-format graph against ComfyUI's /object_info.

Catches, without a GPU: unknown node types, missing/unknown inputs, combo
values the server would reject (including model files missing from the
farm), dangling links, and link type mismatches. Both combo formats are
understood: [[options...], {...}] and ["COMBO", {"options": [...]}].

ComfyUI's "v3" dynamic inputs are expanded the way the server expands them
(comfy_api.latest._io.get_finalized_class_inputs) before checking:
COMFY_AUTOGROW_V3 becomes its template slots ("images.image_1", ...),
COMFY_DYNAMICCOMBO_V3 becomes a combo of its option keys plus the selected
option's inputs ("format.codec", ...), and a COMFY_MATCHTYPE_V3 input accepts
its template's allowed_types while a COMFY_MATCHTYPE_V3 output matches any input.
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


_AUTOGROW = "COMFY_AUTOGROW_V3"
_DYNAMIC_COMBO = "COMFY_DYNAMICCOMBO_V3"
_MATCH_TYPE = "COMFY_MATCHTYPE_V3"


def _autogrow_slots(name: str, spec: list[Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    template: dict[str, Any] = spec[1]["template"]
    names: list[str] = template["names"]
    section, slots = next((k, v) for k, v in template["input"].items() if v)
    slot = next(iter(slots.values()))
    required: dict[str, Any] = {}
    optional: dict[str, Any] = {}
    for i, slot_name in enumerate(names):
        target = required if i < template.get("min", 1) and section == "required" else optional
        target[f"{name}.{slot_name}"] = slot
    return required, optional


def _expand(
    declared: dict[str, Any], inputs: dict[str, Any], prefix: str = ""
) -> tuple[dict[str, Any], dict[str, Any]]:
    """(required, optional) input specs keyed by the names an API graph uses."""
    required: dict[str, Any] = {}
    optional: dict[str, Any] = {}
    for section, target in (("required", required), ("optional", optional)):
        for name, spec in declared.get(section, {}).items():
            key = f"{prefix}{name}"
            if spec[0] == _AUTOGROW:
                grown_required, grown_optional = _autogrow_slots(key, spec)
                required |= grown_required
                optional |= grown_optional
            elif spec[0] == _DYNAMIC_COMBO:
                options: list[dict[str, Any]] = spec[1]["options"]
                target[key] = ["COMBO", {"options": [o["key"] for o in options]}]
                chosen = next((o for o in options if o["key"] == inputs.get(key)), None)
                if chosen is not None:
                    nested_required, nested_optional = _expand(chosen["inputs"], inputs, f"{key}.")
                    required |= nested_required
                    optional |= nested_optional
            else:
                target[key] = spec
    return required, optional


def validate_graph(graph: Graph, object_info: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for node_id, node in graph.items():
        class_type = node.get("class_type")
        info = object_info.get(str(class_type))
        if info is None:
            errors.append(f"{node_id}: unknown class_type {class_type!r}")
            continue
        inputs: dict[str, Any] = node.get("inputs", {})
        required, optional = _expand(info.get("input", {}), inputs)
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
    declared = spec[1]["template"]["allowed_types"] if spec[0] == _MATCH_TYPE else spec[0]
    wanted, given = _types(declared), _types(outputs[index])
    matches_any = "*" in wanted or "*" in given or _MATCH_TYPE in given
    if matches_any or wanted & given or _options(spec) is not None:
        return []
    return [f"{where}: {name} expects {declared} but {source_id!r} gives {outputs[index]}"]
