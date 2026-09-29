"""Pins for the YOLO26 ONNX export's detection head (A5500 bring-up, 2026-09-28).

Triton's yolo26 config declares output0 as YOLO26's NMS-free one-to-one head,
[1, 300, 6] (x1, y1, x2, y2, score, class). ultralytics 8.4.164 changed the
export default: `nms=None` now means "external NMS", and the exporter sets
`model.end2end = args.nms is False`, so a bare `model.export(format="onnx")`
emits the one-to-many training head [1, 84, 8400]. The unpinned --no-cache
gateway rebuild picked that up, validate_model() checked only the file size,
and the first sign was Triton refusing the model at boot.

These are the sandbox-provable half. The live half is Triton loading the
re-exported file (ledger).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from ai.gateway.export import export_yolo26

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG = REPO_ROOT / "ai" / "triton" / "model_repository" / "yolo26" / "config.pbtxt"
SCRIPT = REPO_ROOT / "ai" / "gateway" / "export" / "export_yolo26.py"


def _config_output0_dims() -> tuple[int, ...]:
    text = CONFIG.read_text(encoding="utf-8")
    match = re.search(r'name:\s*"output0".*?dims:\s*\[([^\]]*)\]', text, re.S)
    assert match, "yolo26 config.pbtxt no longer declares output0 dims"
    return tuple(int(d) for d in match.group(1).split(","))


def test_expected_output_shape_is_the_triton_contract() -> None:
    assert _config_output0_dims() == export_yolo26.EXPECTED_OUTPUT_SHAPE, (
        "the export's shape guard must name exactly what Triton's config declares"
    )


def test_one_to_many_head_is_rejected() -> None:
    assert not export_yolo26.output_shape_ok((1, 84, 8400)), (
        "the one-to-many head is what an nms=None export produces; Triton refuses it"
    )


def test_end_to_end_head_is_accepted() -> None:
    assert export_yolo26.output_shape_ok((1, 300, 6))


def _onnx_export_call() -> ast.Call:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    func = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "export_to_onnx"
    )
    calls = [
        n
        for n in ast.walk(func)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "export"
        and any(
            k.arg == "format" and isinstance(k.value, ast.Constant) and k.value.value == "onnx"
            for k in n.keywords
        )
    ]
    assert len(calls) == 1, f"expected one model.export(format='onnx') call, found {len(calls)}"
    return calls[0]


def test_onnx_export_requests_the_nms_free_head() -> None:
    nms = {k.arg: k.value for k in _onnx_export_call().keywords}.get("nms")
    assert isinstance(nms, ast.Constant) and nms.value is False, (
        "export_to_onnx must pass nms=False: under ultralytics >= 8.4.164 that is the "
        "only spelling that selects YOLO26's one-to-one head (and under older releases "
        "it is the default, so the explicit value is correct on both)"
    )
