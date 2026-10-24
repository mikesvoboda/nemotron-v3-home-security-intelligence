#!/usr/bin/env python3
"""Prepare and compile the face leg's SCRFD + ArcFace ONNX models for Triton ([r307a]).

Ruling 307 moves the face leg (InsightFace `buffalo_l` `det_10g.onnx` /
`scrfd_10g_bnkps.onnx` and `w600k_r50.onnx`) to Triton as TensorRT plans built
for the serving GPU, keeping F12's conditions:
  * Exactly two SHA-256-pinned ONNX files from `models.yml`
    (`face-detector-scrfd` and `face-recognizer`), never `insightface.FaceAnalysis`.
  * Stored `FaceEmbedding.model_id` values stay identical to the CPU loader's
    (`face-detector-scrfd@scrfd_10g_bnkps@5838f7fe0536` and
    `face-recognizer@w600k_r50@4c06341c33c2`).

Why each ONNX graph needs a deterministic graph surgery before `trtexec`:
  1. `scrfd_10g_bnkps.onnx` (`det_10g.onnx`):
     - Declares `input.1` with dynamic spatial dims `[1, 3, '?', '?']` and 149
       unpopulated `value_info` entries (`dim_value = 0`), while its 9 output
       tensors (`448`, `471`, `494`, `451`, `474`, `497`, `454`, `477`, `500`)
       declare static anchor counts (`12800`, `3200`, `800`) that are valid only
       at `640x640`.
     - Its two FPN `Resize` nodes (`Resize_124`, `Resize_144`) compute their 4th
       input (`sizes` = `'399'`, `'419'`) dynamically via a `Shape -> Gather ->
       Unsqueeze -> Slice -> Concat` subgraph, leaving every downstream tensor's
       batch/spatial dims unknown (`[0, 0, 0, 0]`) under ONNX shape inference.
     - `prepare_scrfd_onnx` pins `input.1` to `[1, 3, 640, 640]`, replaces `'399'`
       and `'419'` with constant `int64` initializers `[1, 56, 40, 40]` and
       `[1, 56, 80, 80]`, drops the dead `Shape/Gather/Unsqueeze/Slice/Concat`
       nodes, and re-runs strict ONNX shape inference (`0` unknown shapes,
       bit-identical `onnxruntime` CPU outputs).
  2. `w600k_r50.onnx`:
     - Declares `input.1` with dynamic batch `['None', 3, 112, 112]` (`dim_param='None'`)
       while output `683` pins a static batch dimension `[1, 512]` (`dim_value=1`),
       which fails strict ONNX shape inference (`Inferred shape and existing shape
       differ in dimension 0: (2) vs (1)`) for any batch > 1 (`max_batch_size: 16`).
     - `prepare_arcface_onnx` unifies dimension 0 of `input.1` and `683` to
       `dim_param = "batch"` and re-runs strict ONNX shape inference so dynamic
       batch profiles `1..16` validate and compile cleanly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import onnx
from onnx import numpy_helper, shape_inference

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

SCRFD_ZOO_NAME = "face-detector-scrfd"
SCRFD_SOURCE_FILE = "scrfd_10g_bnkps.onnx"
SCRFD_EXPECTED_SHA256 = (
    "5838f7fe053675b1c7a08b633df49e7af5495cee0493c7dcf6697200b85b5b91"  # pragma: allowlist secret
)
SCRFD_INPUT_HEIGHT = 640
SCRFD_INPUT_WIDTH = 640

ARCFACE_ZOO_NAME = "face-recognizer"
ARCFACE_SOURCE_FILE = "w600k_r50.onnx"
ARCFACE_EXPECTED_SHA256 = (
    "4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43"  # pragma: allowlist secret
)
ARCFACE_INPUT_HEIGHT = 112
ARCFACE_INPUT_WIDTH = 112
ARCFACE_EMBEDDING_DIM = 512
ARCFACE_MAX_BATCH = 16

PROVENANCE_FILE = "provenance.json"
PLAN_FILE = "model.plan"
DEFAULT_WORKSPACE_GB = 1
DEFAULT_PLAN_TIMEOUT_S = 600
TRTEXEC_CANDIDATES = ("/usr/src/tensorrt/bin/trtexec", "/usr/local/bin/trtexec")

_SCRFD_DEAD_SHAPE_OUTPUTS = frozenset(
    {
        "383",
        "385",
        "386",
        "388",
        "389",
        "390",
        "393",
        "397",
        "399",
        "403",
        "405",
        "406",
        "408",
        "409",
        "410",
        "413",
        "417",
        "419",
    }
)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _trt_major_version() -> int | None:
    raw = os.environ.get("TRT_VERSION", "").strip()
    if not raw:
        return None
    head = raw.split(".", 1)[0]
    return int(head) if head.isdigit() else None


def find_trtexec() -> str | None:
    found = shutil.which("trtexec")
    if found:
        return found
    for candidate in TRTEXEC_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return None


def prepare_scrfd_onnx(
    model: onnx.ModelProto,
    *,
    input_height: int = SCRFD_INPUT_HEIGHT,
    input_width: int = SCRFD_INPUT_WIDTH,
) -> onnx.ModelProto:
    """Pin SCRFD's input to [1, 3, 640, 640] and fold its dynamic FPN Resize sizes."""
    out = onnx.ModelProto()
    out.CopyFrom(model)

    if len(out.graph.input) != 1 or out.graph.input[0].name != "input.1":
        raise RuntimeError("expected SCRFD graph with single input 'input.1'")
    dims = out.graph.input[0].type.tensor_type.shape.dim
    if len(dims) != 4:
        raise RuntimeError(f"expected 4-D SCRFD input, got {len(dims)}-D")
    for idx, val in enumerate((1, 3, input_height, input_width)):
        dims[idx].ClearField("dim_param")
        dims[idx].dim_value = val

    kept_nodes = [n for n in out.graph.node if not (set(n.output) <= _SCRFD_DEAD_SHAPE_OUTPUTS)]
    del out.graph.node[:]
    out.graph.node.extend(kept_nodes)

    existing_inits = {i.name for i in out.graph.initializer}
    if "399" not in existing_inits:
        out.graph.initializer.append(
            numpy_helper.from_array(
                np.array([1, 56, input_height // 16, input_width // 16], dtype=np.int64),
                name="399",
            )
        )
    if "419" not in existing_inits:
        out.graph.initializer.append(
            numpy_helper.from_array(
                np.array([1, 56, input_height // 8, input_width // 8], dtype=np.int64),
                name="419",
            )
        )

    del out.graph.value_info[:]
    out = shape_inference.infer_shapes(out, check_type=True, strict_mode=True, data_prop=True)
    onnx.checker.check_model(out)
    return out


def prepare_arcface_onnx(model: onnx.ModelProto) -> onnx.ModelProto:
    """Unify ArcFace's input.1 and output 683 batch dimension to 'batch'."""
    out = onnx.ModelProto()
    out.CopyFrom(model)

    if len(out.graph.input) != 1 or out.graph.input[0].name != "input.1":
        raise RuntimeError("expected ArcFace graph with single input 'input.1'")
    if len(out.graph.output) != 1 or out.graph.output[0].name != "683":
        raise RuntimeError("expected ArcFace graph with single output '683'")

    in_dim0 = out.graph.input[0].type.tensor_type.shape.dim[0]
    in_dim0.ClearField("dim_value")
    in_dim0.dim_param = "batch"

    out_dim0 = out.graph.output[0].type.tensor_type.shape.dim[0]
    out_dim0.ClearField("dim_value")
    out_dim0.dim_param = "batch"

    del out.graph.value_info[:]
    out = shape_inference.infer_shapes(out, check_type=True, strict_mode=True, data_prop=True)
    onnx.checker.check_model(out)
    return out


def _verify_source_file(source: Path, expected_sha256: str, label: str) -> str:
    if not source.is_file():
        raise RuntimeError(f"{label} weights not found: {source}")
    actual = sha256_of(source)
    if expected_sha256 and actual != expected_sha256.lower():
        raise RuntimeError(
            f"{label} sha256 mismatch for {source.name}: got {actual}, "
            f"expected {expected_sha256} (models.yml pin)"
        )
    return actual


def _write_provenance(
    output_path: Path, *, zoo_name: str, canonical_file: str, sha256: str
) -> Path:
    record = {
        "zoo_name": zoo_name,
        "source_file": canonical_file,
        "source_sha256": sha256,
    }
    target = output_path.parent / PROVENANCE_FILE
    target.write_text(json.dumps(record, indent=2) + "\n")
    return target


def read_provenance(version_dir: Path) -> dict[str, str] | None:
    record_path = version_dir / PROVENANCE_FILE
    if not record_path.is_file():
        return None
    try:
        loaded = json.loads(record_path.read_text())
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def export_scrfd_onnx(
    source_path: str,
    output_path: str,
    *,
    skip_validation: bool = False,
) -> Path:
    """Validate, prepare, verify on CPU ORT, and write scrfd/1/model.onnx + provenance.json."""
    src = Path(source_path)
    out = Path(output_path)
    (out.parent / PROVENANCE_FILE).unlink(missing_ok=True)

    sha = _verify_source_file(src, SCRFD_EXPECTED_SHA256, SCRFD_ZOO_NAME)
    raw = onnx.load(str(src))
    prepared = prepare_scrfd_onnx(raw)

    out.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(prepared, str(out))

    if not skip_validation:
        import onnxruntime as ort

        rng = np.random.default_rng(7)
        blob = rng.standard_normal((1, 3, SCRFD_INPUT_HEIGHT, SCRFD_INPUT_WIDTH), dtype=np.float32)
        s_raw = ort.InferenceSession(str(src), providers=["CPUExecutionProvider"])
        s_prep = ort.InferenceSession(str(out), providers=["CPUExecutionProvider"])
        outs_raw = s_raw.run(None, {"input.1": blob})
        outs_prep = s_prep.run(None, {"input.1": blob})
        max_diff = max(
            float(np.max(np.abs(a - b))) for a, b in zip(outs_raw, outs_prep, strict=True)
        )
        if max_diff > 1e-5:
            out.unlink(missing_ok=True)
            raise RuntimeError(
                f"SCRFD prepared ONNX diverged from source on CPU ORT: max_diff={max_diff:.2e}"
            )

    _write_provenance(
        out,
        zoo_name=SCRFD_ZOO_NAME,
        canonical_file=SCRFD_SOURCE_FILE,
        sha256=sha,
    )
    return out


def export_arcface_onnx(
    source_path: str,
    output_path: str,
    *,
    skip_validation: bool = False,
) -> Path:
    """Validate, prepare, verify on CPU ORT, and write arcface/1/model.onnx + provenance.json."""
    src = Path(source_path)
    out = Path(output_path)
    (out.parent / PROVENANCE_FILE).unlink(missing_ok=True)

    sha = _verify_source_file(src, ARCFACE_EXPECTED_SHA256, ARCFACE_ZOO_NAME)
    raw = onnx.load(str(src))
    prepared = prepare_arcface_onnx(raw)

    out.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(prepared, str(out))

    if not skip_validation:
        import onnxruntime as ort

        rng = np.random.default_rng(13)
        s_raw = ort.InferenceSession(str(src), providers=["CPUExecutionProvider"])
        s_prep = ort.InferenceSession(str(out), providers=["CPUExecutionProvider"])
        for batch in (1, 4, 8):
            crops = rng.standard_normal(
                (batch, 3, ARCFACE_INPUT_HEIGHT, ARCFACE_INPUT_WIDTH), dtype=np.float32
            )
            # Raw graph output declares dim[0]=1 but ORT still executes batch>1; compare sample 0
            out_raw = s_raw.run(None, {"input.1": crops[:1]})[0][0]
            out_prep = s_prep.run(None, {"input.1": crops})[0]
            if out_prep.shape != (batch, ARCFACE_EMBEDDING_DIM):
                out.unlink(missing_ok=True)
                raise RuntimeError(
                    f"ArcFace prepared ONNX shape {out_prep.shape} != ({batch}, {ARCFACE_EMBEDDING_DIM})"
                )
            cos = float(
                np.dot(out_raw, out_prep[0])
                / (np.linalg.norm(out_raw) * np.linalg.norm(out_prep[0]) + 1e-12)
            )
            if cos < 0.9999:
                out.unlink(missing_ok=True)
                raise RuntimeError(
                    f"ArcFace prepared ONNX diverged from source on CPU ORT: cosine={cos:.6f}"
                )

    _write_provenance(
        out,
        zoo_name=ARCFACE_ZOO_NAME,
        canonical_file=ARCFACE_SOURCE_FILE,
        sha256=sha,
    )
    return out


def build_tensorrt_engine(
    onnx_path: str,
    engine_path: str,
    *,
    role: str,
    precision: str = "fp16",
    max_batch: int = ARCFACE_MAX_BATCH,
    workspace_gb: int = DEFAULT_WORKSPACE_GB,
    plan_timeout: int = DEFAULT_PLAN_TIMEOUT_S,
    trtexec: str | None = None,
    run: Callable[..., Any] | None = None,
) -> str:
    """Compile the prepared ONNX into a TensorRT plan for the serving GPU."""
    if role not in ("scrfd", "arcface"):
        raise ValueError(f"unknown face role {role!r} (expected 'scrfd' or 'arcface')")

    builder = trtexec if trtexec is not None else find_trtexec()
    if builder is None:
        raise RuntimeError(
            "trtexec not found — a TensorRT plan must be built on the serving "
            f"host (looked for PATH plus {', '.join(TRTEXEC_CANDIDATES)})"
        )

    runner = run if run is not None else subprocess.run
    engine = Path(engine_path)
    engine.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        builder,
        f"--onnx={onnx_path}",
        f"--saveEngine={engine_path}",
    ]
    if role == "arcface":
        opt_batch = max(1, max_batch // 2)
        shape = f"3x{ARCFACE_INPUT_HEIGHT}x{ARCFACE_INPUT_WIDTH}"
        cmd.extend(
            [
                f"--minShapes=input.1:1x{shape}",
                f"--optShapes=input.1:{opt_batch}x{shape}",
                f"--maxShapes=input.1:{max_batch}x{shape}",
            ]
        )
    cmd.append(f"--memPoolSize=workspace:{workspace_gb * 1024}")

    if precision == "fp16":
        trt_major = _trt_major_version()
        if trt_major is None or trt_major < 11:
            cmd.append("--fp16")
    elif precision != "fp32":
        raise ValueError(f"unknown precision {precision!r} (expected fp16 or fp32)")

    logger.info("Building %s TensorRT plan: %s", role, " ".join(cmd))
    started = time.time()
    try:
        result = runner(cmd, check=False, capture_output=True, text=True, timeout=plan_timeout)
    except BaseException:
        engine.unlink(missing_ok=True)
        raise
    if getattr(result, "returncode", 1) != 0:
        engine.unlink(missing_ok=True)
        stdout = getattr(result, "stdout", "") or ""
        stderr = getattr(result, "stderr", "") or ""
        logger.error("trtexec stdout:\n%s", stdout[-2000:])
        logger.error("trtexec stderr:\n%s", stderr[-2000:])
        raise RuntimeError(f"trtexec failed for {role} with return code {result.returncode}")

    if not engine.is_file():
        raise RuntimeError(
            f"trtexec reported success for {role} but wrote no plan at {engine_path}"
        )

    size_mb = engine.stat().st_size / (1024 * 1024)
    logger.info(
        "%s plan built in %.1fs (%.1f MB) -> %s", role, time.time() - started, size_mb, engine
    )
    return engine_path


def compile_face_plan(
    *,
    role: str,
    source_path: str,
    plan_path: str,
    precision: str = "fp16",
    plan_timeout: int | None = None,
    trtexec: str | None = None,
    run: Callable[..., Any] | None = None,
) -> str:
    """Compile scrfd or arcface `model.plan` beside a provenance-vouched `model.onnx`."""
    if role == "scrfd":
        expected_zoo = SCRFD_ZOO_NAME
        expected_sha = SCRFD_EXPECTED_SHA256
    elif role == "arcface":
        expected_zoo = ARCFACE_ZOO_NAME
        expected_sha = ARCFACE_EXPECTED_SHA256
    else:
        raise ValueError(f"unknown face role {role!r} (expected 'scrfd' or 'arcface')")

    plan = Path(plan_path)
    version_dir = plan.parent
    onnx_file = version_dir / "model.onnx"

    if plan.name != PLAN_FILE:
        raise RuntimeError(
            f"a TensorRT plan must be named {PLAN_FILE} (Triton's fixed filename), not {plan.name!r}"
        )
    if not onnx_file.is_file():
        raise RuntimeError(f"no {onnx_file} to compile a plan from — run the ONNX export first")
    record = read_provenance(version_dir)
    if record is None:
        raise RuntimeError(f"no {PROVENANCE_FILE} beside {onnx_file}")
    if record.get("zoo_name") != expected_zoo:
        raise RuntimeError(f"provenance names {record.get('zoo_name')!r}, not {expected_zoo!r}")

    actual = _verify_source_file(Path(source_path), expected_sha, expected_zoo)
    recorded = str(record.get("source_sha256", ""))
    if actual != recorded:
        raise RuntimeError(
            f"source {Path(source_path).name} sha256 {actual[:12]}… != recorded {recorded[:12]}…"
        )

    extra: dict[str, Any] = {}
    if plan_timeout is not None:
        extra["plan_timeout"] = plan_timeout
    if trtexec is not None:
        extra["trtexec"] = trtexec
    if run is not None:
        extra["run"] = run
    return build_tensorrt_engine(
        str(onnx_file),
        str(plan),
        role=role,
        precision=precision,
        **extra,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare SCRFD / ArcFace ONNX for Triton or compile their TensorRT plans ([r307a])"
    )
    parser.add_argument(
        "--role",
        required=True,
        choices=["scrfd", "arcface"],
        help="Face leg model role: scrfd (detector) or arcface (recognizer)",
    )
    parser.add_argument(
        "--model-path",
        required=True,
        help="Path to the pinned source ONNX file (scrfd_10g_bnkps.onnx / det_10g.onnx or w600k_r50.onnx)",
    )
    parser.add_argument(
        "--output-path",
        required=True,
        help="Output path: .../1/model.onnx to prepare/export, .../1/model.plan to compile",
    )
    parser.add_argument(
        "--precision",
        default="fp16",
        choices=["fp16", "fp32"],
        help="Plan precision (plan mode only)",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip CPU onnxruntime validation step",
    )
    parser.add_argument(
        "--plan-timeout",
        type=int,
        default=None,
        metavar="SECONDS",
        help=f"Wall-clock bound on trtexec build (default {DEFAULT_PLAN_TIMEOUT_S}s)",
    )
    args = parser.parse_args(argv)

    if args.output_path.endswith(".plan"):
        try:
            compile_face_plan(
                role=args.role,
                source_path=args.model_path,
                plan_path=args.output_path,
                precision=args.precision,
                plan_timeout=args.plan_timeout,
            )
            return 0
        except Exception as e:
            logger.error("Face plan build failed (%s): %s", args.role, e, exc_info=True)
            return 1

    try:
        if args.role == "scrfd":
            export_scrfd_onnx(
                args.model_path,
                args.output_path,
                skip_validation=args.skip_validation,
            )
        else:
            export_arcface_onnx(
                args.model_path,
                args.output_path,
                skip_validation=args.skip_validation,
            )
        return 0
    except Exception as e:
        logger.error("Face ONNX export failed (%s): %s", args.role, e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
