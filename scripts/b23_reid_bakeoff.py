#!/usr/bin/env python3
"""B2.3 Re-ID model bake-off: exporter, TensorRT compiler, and evaluation harness (ruling 333).

Compares the incumbent OSNet-AIN x1.0 (`osnet_ain_x1_0_msmt17.pth`) against the
three ruling-333 challengers through `O2.4`'s TensorRT path:
  1. `clip_reid_vit_b_16`: CLIP-ReID ViT-B/16 MSMT17 (`Syliz517/CLIP-ReID`, MIT license),
     `ViT-B-16_60.pth` (`1280`-d = `768` CLS + `512` projected).
  2. `tao_swin_tiny_256`: NVIDIA TAO `ReIdentificationNet Transformer` `deployable_v1.0`
     `swin_tiny_market1501_aicity156_featuredim256.onnx` (`256`-d, NVIDIA Model EULA).
  3. `tao_swin_base_1024`: NVIDIA TAO `ReIdentificationNet Transformer` `deployable_v1.0`
     `swin_base_market1501_aicity156_featuredim1024.onnx` (`1024`-d, NVIDIA Model EULA).

Metrics per model:
  - Rank-1 and mAP (both all-pairs and cross-camera/cross-event)
  - Calibrated match threshold (`calibrated_threshold` maximizing F1, plus TAR @ FAR <= 1%)
  - GPU milliseconds per crop (median and p95) and GPU memory (MiB)
  - License and no-login install source (ruling 333 item 4)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import onnx
import torch
from onnx import shape_inference
from PIL import Image
from torch import nn

INPUT_HEIGHT = 256
INPUT_WIDTH = 128
MAX_BATCH = 16
OPT_BATCH = 4
DEFAULT_WORKSPACE_GB = 1
DEFAULT_PLAN_TIMEOUT_S = 600
PROVENANCE_FILE = "provenance.json"
TRTEXEC_CANDIDATES = ("/usr/src/tensorrt/bin/trtexec", "/usr/local/bin/trtexec")

OSNET_EXPECTED_SHA256 = (
    "8a07e8da38946f7cee37f4561617bf8b6d2fe8f3a4027852893ea092e46d919f"  # pragma: allowlist secret
)
CLIP_REID_EXPECTED_SHA256 = (
    "9974ef57c418e8c88e59581f66f3f53fbe02f879311f7438009f84fd150b1c63"  # pragma: allowlist secret
)
TAO_SWIN_TINY_256_EXPECTED_SHA256 = (
    "37b008d887495d5fbad31c72aadbf381c5456cb619e0e2a9c246a6d48a2932ff"  # pragma: allowlist secret
)
TAO_SWIN_BASE_1024_EXPECTED_SHA256 = (
    "de5d3dc9a44b07a61a57ec9be66be04a0260c779c96b50271014920a5b3e264c"  # pragma: allowlist secret
)


@dataclass(frozen=True, slots=True)
class ModelSpec:
    key: str
    zoo_name: str
    filename: str
    sha256: str
    embedding_dim: int
    mean: tuple[float, float, float]
    std: tuple[float, float, float]
    license_name: str
    download_url: str
    install_source: str


MODEL_SPECS: dict[str, ModelSpec] = {
    "osnet_ain_x1_0": ModelSpec(
        key="osnet_ain_x1_0",
        zoo_name="osnet-ain-x1-0",
        filename="osnet_ain_x1_0_msmt17.pth",
        sha256=OSNET_EXPECTED_SHA256,
        embedding_dim=512,
        mean=(0.485, 0.456, 0.406),
        std=(0.229, 0.224, 0.225),
        license_name="MIT (KaiyangZhou/deep-person-reid)",
        download_url=(
            "https://huggingface.co/kaiyangzhou/osnet/resolve/main/"
            "osnet_ain_x1_0_msmt17_256x128_amsgrad_ep50_lr0.0015_coslr_b64_fb10_softmax_labsmth_flip_jitter.pth"
        ),
        install_source="Hugging Face (`kaiyangzhou/osnet`, public no-login)",
    ),
    "clip_reid_vit_b_16": ModelSpec(
        key="clip_reid_vit_b_16",
        zoo_name="clip-reid-vit-b-16",
        filename="ViT-B-16_60.pth",
        sha256=CLIP_REID_EXPECTED_SHA256,
        embedding_dim=1280,
        mean=(0.5, 0.5, 0.5),
        std=(0.5, 0.5, 0.5),
        license_name="MIT (Syliz517/CLIP-ReID)",
        download_url=(
            "https://drive.usercontent.google.com/download?"
            "id=1BVaZo93kOksYLjFNH3Gf7JxIbPlWSkcO&export=download&confirm=t"
        ),
        install_source=(
            "Mirror to project Hugging Face repo required before install "
            "(ruling 333 item 4; upstream is Google Drive no-login)"
        ),
    ),
    "tao_swin_tiny_256": ModelSpec(
        key="tao_swin_tiny_256",
        zoo_name="tao-reid-swin-tiny-256",
        filename="swin_tiny_market1501_aicity156_featuredim256.onnx",
        sha256=TAO_SWIN_TINY_256_EXPECTED_SHA256,
        embedding_dim=256,
        mean=(0.5, 0.5, 0.5),
        std=(0.5, 0.5, 0.5),
        license_name="NVIDIA Model EULA (nvidia/tao/reidentificationnet_transformer)",
        download_url=(
            "https://api.ngc.nvidia.com/v2/models/nvidia/tao/reidentificationnet_transformer/"
            "versions/deployable_v1.0/files/swin_tiny_market1501_aicity156_featuredim256.onnx"
        ),
        install_source="NGC public file API (`nvidia/tao/reidentificationnet_transformer:deployable_v1.0`, no login)",
    ),
    "tao_swin_base_1024": ModelSpec(
        key="tao_swin_base_1024",
        zoo_name="tao-reid-swin-base-1024",
        filename="swin_base_market1501_aicity156_featuredim1024.onnx",
        sha256=TAO_SWIN_BASE_1024_EXPECTED_SHA256,
        embedding_dim=1024,
        mean=(0.5, 0.5, 0.5),
        std=(0.5, 0.5, 0.5),
        license_name="NVIDIA Model EULA (nvidia/tao/reidentificationnet_transformer)",
        download_url=(
            "https://api.ngc.nvidia.com/v2/models/nvidia/tao/reidentificationnet_transformer/"
            "versions/deployable_v1.0/files/swin_base_market1501_aicity156_featuredim1024.onnx"
        ),
        install_source="NGC public file API (`nvidia/tao/reidentificationnet_transformer:deployable_v1.0`, no login)",
    ),
}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_source_sha256(path: Path, expected_sha256: str, label: str) -> str:
    if not path.is_file():
        raise RuntimeError(f"{label} weights not found: {path}")
    actual = sha256_of(path)
    if expected_sha256 and actual != expected_sha256.lower():
        raise RuntimeError(
            f"{label} sha256 mismatch for {path.name}: got {actual}, expected {expected_sha256}"
        )
    return actual


def fetch_checkpoint(model_key: str, dest_dir: Path) -> Path:
    """Download `model_key`'s checkpoint with no login (if absent) and verify its SHA-256."""
    spec = MODEL_SPECS[model_key]
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / spec.filename
    if not target.is_file():
        if not spec.download_url.startswith("https://"):
            raise RuntimeError(f"Refusing non-HTTPS download URL: {spec.download_url}")
        urllib.request.urlretrieve(spec.download_url, target)  # noqa: S310
    verify_source_sha256(target, spec.sha256, spec.zoo_name)
    return target


def preprocess_crop(path: Path | Image.Image, spec: ModelSpec) -> np.ndarray:
    """Resize to (128, 256) BILINEAR RGB and normalize per `spec.mean`/`spec.std` -> (1, 3, 256, 128)."""
    img = Image.open(path) if isinstance(path, Path) else path
    rgb = img.convert("RGB").resize((INPUT_WIDTH, INPUT_HEIGHT), Image.Resampling.BILINEAR)
    arr: np.ndarray = np.asarray(rgb, dtype=np.float32) / 255.0
    mean: np.ndarray = np.asarray(spec.mean, dtype=np.float32)
    std: np.ndarray = np.asarray(spec.std, dtype=np.float32)
    normed: np.ndarray = (arr - mean) / std
    out: np.ndarray = np.ascontiguousarray(
        normed.transpose(2, 0, 1)[np.newaxis, ...], dtype=np.float32
    )
    return out


# ---------------------------------------------------------------------------
# 1. CLIP-ReID ViT-B/16 Vision Encoder (Syliz517/CLIP-ReID, MIT)
# ---------------------------------------------------------------------------


class _LayerNorm(nn.LayerNorm):
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        orig_type = x.dtype
        ret = super().forward(x.type(torch.float32))
        return ret.type(orig_type)


class _QuickGELU(nn.Module):
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x * torch.sigmoid(1.702 * x)


class _ResidualAttentionBlock(nn.Module):
    def __init__(self, d_model: int, n_head: int) -> None:
        super().__init__()
        self.attn = nn.MultiheadAttention(d_model, n_head)
        self.ln_1 = _LayerNorm(d_model)
        self.mlp = nn.Sequential(
            OrderedDict(
                [
                    ("c_fc", nn.Linear(d_model, d_model * 4)),
                    ("gelu", _QuickGELU()),
                    ("c_proj", nn.Linear(d_model * 4, d_model)),
                ]
            )
        )
        self.ln_2 = _LayerNorm(d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        ln1 = self.ln_1(x)
        x = x + self.attn(ln1, ln1, ln1, need_weights=False)[0]
        x = x + self.mlp(self.ln_2(x))
        return x


class _Transformer(nn.Module):
    def __init__(self, width: int, layers: int, heads: int) -> None:
        super().__init__()
        self.resblocks = nn.Sequential(
            *[_ResidualAttentionBlock(width, heads) for _ in range(layers)]
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out: torch.Tensor = self.resblocks(x)
        return out


class ClipReidViTB16(nn.Module):
    """Pure-vision inference module for `Syliz517/CLIP-ReID` ViT-B/16 (`NECK_FEAT='before'`).

    Emits `torch.cat([img_feature (width), img_feature_proj (output_dim)], dim=1)`
    (`1280`-d for ViT-B/16 with `width=768, output_dim=512`).
    """

    def __init__(
        self,
        h_resolution: int = 16,
        w_resolution: int = 8,
        patch_size: int = 16,
        stride_size: int = 16,
        width: int = 768,
        layers: int = 12,
        heads: int = 12,
        output_dim: int = 512,
    ) -> None:
        super().__init__()
        self.width = width
        self.output_dim = output_dim
        self.conv1 = nn.Conv2d(3, width, kernel_size=patch_size, stride=stride_size, bias=False)
        scale = width**-0.5
        self.class_embedding = nn.Parameter(scale * torch.randn(width))
        self.positional_embedding = nn.Parameter(
            scale * torch.randn(h_resolution * w_resolution + 1, width)
        )
        self.ln_pre = _LayerNorm(width)
        self.transformer = _Transformer(width, layers, heads)
        self.ln_post = _LayerNorm(width)
        self.proj = nn.Parameter(scale * torch.randn(width, output_dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.conv1(x)
        x = x.reshape(x.shape[0], x.shape[1], -1).permute(0, 2, 1)
        cls_tokens = (
            self.class_embedding.to(x.dtype).unsqueeze(0).unsqueeze(0).expand(x.shape[0], 1, -1)
        )
        x = torch.cat([cls_tokens, x], dim=1)
        x = x + self.positional_embedding.to(x.dtype)
        x = self.ln_pre(x)
        x = x.permute(1, 0, 2)  # NLD -> LND
        x = self.transformer(x)
        x = x.permute(1, 0, 2)  # LND -> NLD
        x12 = self.ln_post(x)
        img_feature = x12[:, 0]
        img_feature_proj = img_feature @ self.proj
        return torch.cat([img_feature, img_feature_proj], dim=1)


def load_clip_reid_model(
    checkpoint_path: Path,
    *,
    expected_sha256: str = CLIP_REID_EXPECTED_SHA256,
    width: int = 768,
    layers: int = 12,
    heads: int = 12,
    output_dim: int = 512,
) -> ClipReidViTB16:
    verify_source_sha256(checkpoint_path, expected_sha256, "clip-reid-vit-b-16")
    raw_sd = torch.load(str(checkpoint_path), map_location="cpu", weights_only=True)
    if not isinstance(raw_sd, dict):
        raise RuntimeError(f"Expected state_dict mapping in {checkpoint_path}")
    vis_sd = {
        k.removeprefix("module.").removeprefix("image_encoder."): v
        for k, v in raw_sd.items()
        if k.removeprefix("module.").startswith("image_encoder.")
    }
    model = ClipReidViTB16(
        width=width,
        layers=layers,
        heads=heads,
        output_dim=output_dim,
    )
    model.eval()
    model.load_state_dict(vis_sd, strict=True)
    return model


def _write_provenance(output_path: Path, *, zoo_name: str, source_file: str, sha256: str) -> Path:
    target = output_path.parent / PROVENANCE_FILE
    target.write_text(
        json.dumps(
            {
                "zoo_name": zoo_name,
                "source_file": source_file,
                "source_sha256": sha256,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


def export_clip_reid_onnx(
    checkpoint_path: Path,
    output_path: Path,
    *,
    expected_sha256: str = CLIP_REID_EXPECTED_SHA256,
    width: int = 768,
    layers: int = 12,
    heads: int = 12,
    output_dim: int = 512,
) -> Path:
    """Export CLIP-ReID ViT-B/16 to ONNX, verify on CPU ORT (`cosine >= 0.9999`), and write provenance."""
    sha = verify_source_sha256(checkpoint_path, expected_sha256, "clip-reid-vit-b-16")
    model = load_clip_reid_model(
        checkpoint_path,
        expected_sha256=sha,
        width=width,
        layers=layers,
        heads=heads,
        output_dim=output_dim,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dummy = torch.randn(2, 3, INPUT_HEIGHT, INPUT_WIDTH, dtype=torch.float32)
    with torch.no_grad():
        pt_out = model(dummy).numpy()

    torch.onnx.export(
        model,
        (dummy,),
        str(output_path),
        input_names=["input"],
        output_names=["embedding"],
        dynamic_axes={"input": {0: "batch"}, "embedding": {0: "batch"}},
        opset_version=17,
        dynamo=False,
    )
    onnx.checker.check_model(onnx.load(str(output_path)))

    import onnxruntime as ort

    sess = ort.InferenceSession(str(output_path), providers=["CPUExecutionProvider"])
    ort_out = sess.run(["embedding"], {"input": dummy.numpy()})[0]
    for a, b in zip(pt_out, ort_out, strict=True):
        cos = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
        if cos < 0.9999:
            output_path.unlink(missing_ok=True)
            raise RuntimeError(f"CLIP-ReID ONNX diverged from PyTorch on CPU ORT: cos={cos:.6f}")

    _write_provenance(
        output_path,
        zoo_name=MODEL_SPECS["clip_reid_vit_b_16"].zoo_name,
        source_file=MODEL_SPECS["clip_reid_vit_b_16"].filename,
        sha256=sha,
    )
    return output_path


# ---------------------------------------------------------------------------
# 2. NVIDIA TAO ReIdentificationNet Transformer (swin_tiny_256, swin_base_1024)
# ---------------------------------------------------------------------------


def prepare_tao_swin_onnx(model: onnx.ModelProto, *, feat_dim: int) -> onnx.ModelProto:
    """Normalize TAO Swin Re-ID ONNX output to `embedding` `['batch', feat_dim]`."""
    out = onnx.ModelProto()
    out.CopyFrom(model)

    if len(out.graph.input) != 1 or out.graph.input[0].name != "input":
        raise RuntimeError("Expected TAO Swin ONNX with single input 'input'")
    if len(out.graph.output) != 1:
        raise RuntimeError("Expected TAO Swin ONNX with single output")

    old_out_name = out.graph.output[0].name
    if old_out_name != "embedding":
        for node in out.graph.node:
            for idx, name in enumerate(node.output):
                if name == old_out_name:
                    node.output[idx] = "embedding"
        out.graph.output[0].name = "embedding"

    in_dims = out.graph.input[0].type.tensor_type.shape.dim
    in_dims[0].ClearField("dim_value")
    in_dims[0].dim_param = "batch"

    out_dims = out.graph.output[0].type.tensor_type.shape.dim
    out_dims[0].ClearField("dim_value")
    out_dims[0].dim_param = "batch"
    out_dims[1].ClearField("dim_param")
    out_dims[1].dim_value = feat_dim

    del out.graph.value_info[:]
    out = shape_inference.infer_shapes(out, check_type=True, strict_mode=True, data_prop=True)
    onnx.checker.check_model(out)
    return out


def export_tao_swin_onnx(
    role: str,
    source_path: Path,
    output_path: Path,
    *,
    expected_sha256: str | None = None,
) -> Path:
    spec = MODEL_SPECS[role]
    pin = expected_sha256 if expected_sha256 is not None else spec.sha256
    sha = verify_source_sha256(source_path, pin, spec.zoo_name)

    raw = onnx.load(str(source_path))
    prepared = prepare_tao_swin_onnx(raw, feat_dim=spec.embedding_dim)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(prepared, str(output_path))

    import onnxruntime as ort

    rng = np.random.default_rng(19)
    x = rng.standard_normal((2, 3, INPUT_HEIGHT, INPUT_WIDTH), dtype=np.float32)
    s_raw = ort.InferenceSession(str(source_path), providers=["CPUExecutionProvider"])
    s_prep = ort.InferenceSession(str(output_path), providers=["CPUExecutionProvider"])
    raw_out = s_raw.run(None, {"input": x})[0]
    prep_out = s_prep.run(["embedding"], {"input": x})[0]
    if prep_out.shape != (2, spec.embedding_dim):
        output_path.unlink(missing_ok=True)
        raise RuntimeError(f"{role} unexpected output shape: {prep_out.shape}")
    max_diff = float(np.max(np.abs(raw_out - prep_out)))
    if max_diff > 1e-5:
        output_path.unlink(missing_ok=True)
        raise RuntimeError(f"{role} prepared ONNX diverged from source: max_diff={max_diff:.2e}")

    _write_provenance(
        output_path,
        zoo_name=spec.zoo_name,
        source_file=spec.filename,
        sha256=sha,
    )
    return output_path


# ---------------------------------------------------------------------------
# 3. TensorRT Plan Compilation (O2.4 path)
# ---------------------------------------------------------------------------


def find_trtexec() -> str | None:
    found = shutil.which("trtexec")
    if found:
        return found
    for candidate in TRTEXEC_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return None


def _trt_major_version() -> int | None:
    raw = os.environ.get("TRT_VERSION", "").strip()
    if not raw:
        return None
    head = raw.split(".", 1)[0]
    return int(head) if head.isdigit() else None


def compile_challenger_plan(
    role: str,
    source_path: Path,
    plan_path: Path,
    *,
    expected_sha256: str | None = None,
    precision: str = "fp16",
    workspace_gb: int = DEFAULT_WORKSPACE_GB,
    plan_timeout: int = DEFAULT_PLAN_TIMEOUT_S,
) -> Path:
    """Compile a TensorRT `model.plan` with O2.4's dynamic batch profiles `1..16`."""
    onnx_path = plan_path.with_suffix(".onnx")
    if not onnx_path.is_file():
        if role == "clip_reid_vit_b_16":
            export_clip_reid_onnx(
                source_path,
                onnx_path,
                expected_sha256=expected_sha256 or CLIP_REID_EXPECTED_SHA256,
            )
        else:
            export_tao_swin_onnx(
                role,
                source_path,
                onnx_path,
                expected_sha256=expected_sha256,
            )

    trtexec = find_trtexec()
    if trtexec is None:
        raise RuntimeError("trtexec not found on PATH or standard TensorRT locations")

    min_shape = f"input:1x3x{INPUT_HEIGHT}x{INPUT_WIDTH}"
    opt_shape = f"input:{OPT_BATCH}x3x{INPUT_HEIGHT}x{INPUT_WIDTH}"
    max_shape = f"input:{MAX_BATCH}x3x{INPUT_HEIGHT}x{INPUT_WIDTH}"

    cmd = [
        trtexec,
        f"--onnx={onnx_path}",
        f"--saveEngine={plan_path}",
        f"--minShapes={min_shape}",
        f"--optShapes={opt_shape}",
        f"--maxShapes={max_shape}",
        f"--memPoolSize=workspace:{workspace_gb * 1024}",
    ]
    trt_major = _trt_major_version()
    if precision == "fp16" and (trt_major is None or trt_major < 11):
        cmd.append("--fp16")

    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=plan_timeout,
        check=False,
    )
    if res.returncode != 0 or not plan_path.is_file():
        plan_path.unlink(missing_ok=True)
        raise RuntimeError(f"trtexec failed for {role} (rc={res.returncode}): {res.stderr[-600:]}")
    return plan_path


# ---------------------------------------------------------------------------
# 4. Bake-off Scoring: Rank-1, mAP, Calibrated Threshold, Latency & Report
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BakeoffMetrics:
    model_key: str
    embedding_dim: int
    queries_count: int
    cross_camera_queries_count: int
    rank1: float
    map_score: float
    cross_camera_rank1: float
    cross_camera_map: float
    calibrated_threshold: float
    calibrated_f1: float
    tar_at_far_1pct: float
    pos_min_cosine: float
    neg_max_cosine: float
    latency_median_ms: float
    latency_p95_ms: float
    vram_mib: int
    license_name: str
    install_source: str


def _unit_vec(v: np.ndarray) -> np.ndarray:
    v64: np.ndarray = np.asarray(v, dtype=np.float64).reshape(-1)
    norm = float(np.linalg.norm(v64))
    res: np.ndarray = v64 / norm if norm > 0.0 else v64
    return res


def _compute_ranking_metrics(
    items: list[dict[str, Any]],
    unit_vecs: list[np.ndarray],
    *,
    cross_camera_only: bool,
) -> tuple[int, float, float]:
    """Return `(valid_queries, rank1, mAP)` over `items`."""
    n = len(items)
    sim_matrix: np.ndarray = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        for j in range(n):
            sim_matrix[i, j] = float(np.dot(unit_vecs[i], unit_vecs[j]))

    rank1_hits = 0
    aps: list[float] = []
    valid_queries = 0

    for i in range(n):
        q_pid = str(items[i]["person_id"])
        q_cam = str(items[i].get("camera_id", ""))
        q_evt = str(items[i].get("event_id", ""))

        gallery_indices: list[int] = []
        for j in range(n):
            if i == j:
                continue
            if cross_camera_only and str(items[j]["person_id"]) == q_pid:
                # Exclude same-event or same-camera views of the query person when measuring cross-camera re-ID
                if (
                    q_cam
                    and str(items[j].get("camera_id", "")) == q_cam
                    and q_evt
                    and str(items[j].get("event_id", "")) == q_evt
                ):
                    continue
                if q_cam and str(items[j].get("camera_id", "")) == q_cam:
                    continue
            gallery_indices.append(j)

        pos_in_gallery = [j for j in gallery_indices if str(items[j]["person_id"]) == q_pid]
        if not pos_in_gallery:
            continue

        valid_queries += 1
        ranked = sorted(gallery_indices, key=lambda j: sim_matrix[i, j], reverse=True)
        if str(items[ranked[0]]["person_id"]) == q_pid:
            rank1_hits += 1

        hits = 0
        sum_precisions = 0.0
        for rank_idx, j in enumerate(ranked, start=1):
            if str(items[j]["person_id"]) == q_pid:
                hits += 1
                sum_precisions += hits / rank_idx
        aps.append(sum_precisions / len(pos_in_gallery))

    if valid_queries == 0:
        return 0, 0.0, 0.0
    return valid_queries, rank1_hits / valid_queries, float(np.mean(aps))


def _calibrate_threshold(
    items: list[dict[str, Any]],
    unit_vecs: list[np.ndarray],
) -> tuple[float, float, float, float, float]:
    """Return `(best_threshold, best_f1, tar_at_far_1pct, pos_min, neg_max)`."""
    pos_scores: list[float] = []
    neg_scores: list[float] = []
    n = len(items)
    for i in range(n):
        for j in range(i + 1, n):
            s = float(np.dot(unit_vecs[i], unit_vecs[j]))
            if str(items[i]["person_id"]) == str(items[j]["person_id"]):
                pos_scores.append(s)
            else:
                neg_scores.append(s)

    if not pos_scores or not neg_scores:
        return 0.70, 0.0, 0.0, 0.0, 0.0

    pos_arr: np.ndarray = np.asarray(pos_scores, dtype=np.float64)
    neg_arr: np.ndarray = np.asarray(neg_scores, dtype=np.float64)

    candidates = np.linspace(0.10, 0.98, 177)
    best_thresh = 0.70
    best_f1 = -1.0
    for tau in candidates:
        tp = int(np.sum(pos_arr >= tau))
        fp = int(np.sum(neg_arr >= tau))
        fn = int(np.sum(pos_arr < tau))
        denom = 2 * tp + fp + fn
        f1 = (2.0 * tp / denom) if denom > 0 else 0.0
        if f1 > best_f1 or (f1 == best_f1 and abs(tau - 0.70) < abs(best_thresh - 0.70)):
            best_f1 = f1
            best_thresh = float(tau)

    # TAR at FAR <= 1%
    far_1pct_thresh = float(np.percentile(neg_arr, 99))
    tar_at_far_1pct = float(np.mean(pos_arr > far_1pct_thresh))

    return (
        round(best_thresh, 3),
        round(best_f1, 4),
        round(tar_at_far_1pct, 4),
        float(np.min(pos_arr)),
        float(np.max(neg_arr)),
    )


def score_model_embeddings(
    *,
    model_key: str,
    labels: list[dict[str, Any]],
    embeddings: dict[str, np.ndarray | list[float]],
    latency_ms: list[float],
    vram_mib: int = 0,
) -> BakeoffMetrics:
    spec = MODEL_SPECS[model_key]
    ordered = [row for row in labels if str(row["crop_id"]) in embeddings]
    unit_vecs = [_unit_vec(np.asarray(embeddings[str(row["crop_id"])])) for row in ordered]

    q_all, r1_all, map_all = _compute_ranking_metrics(ordered, unit_vecs, cross_camera_only=False)
    q_cc, r1_cc, map_cc = _compute_ranking_metrics(ordered, unit_vecs, cross_camera_only=True)
    thresh, f1, tar1, pos_min, neg_max = _calibrate_threshold(ordered, unit_vecs)

    lat_arr = np.asarray(latency_ms, dtype=np.float64) if latency_ms else np.zeros(1)
    dim = int(unit_vecs[0].shape[0]) if unit_vecs else spec.embedding_dim

    return BakeoffMetrics(
        model_key=model_key,
        embedding_dim=dim,
        queries_count=q_all,
        cross_camera_queries_count=q_cc,
        rank1=r1_all,
        map_score=map_all,
        cross_camera_rank1=r1_cc,
        cross_camera_map=map_cc,
        calibrated_threshold=thresh,
        calibrated_f1=f1,
        tar_at_far_1pct=tar1,
        pos_min_cosine=pos_min,
        neg_max_cosine=neg_max,
        latency_median_ms=float(np.median(lat_arr)),
        latency_p95_ms=float(np.percentile(lat_arr, 95)),
        vram_mib=vram_mib,
        license_name=spec.license_name,
        install_source=spec.install_source,
    )


def format_bakeoff_report(
    results: list[BakeoffMetrics],
    *,
    labels_summary: dict[str, Any],
) -> str:
    lines = [
        "## B2.3 Re-ID Model Bake-Off Results (Ruling 333)",
        "",
        f"- **Labelled set:** `{labels_summary.get('total_kept_crops', 0)}` kept crops across "
        f"`{labels_summary.get('identities_count', 0)}` identities "
        f"(`{labels_summary.get('multi_crop_identities_count', 0)}` multi-crop identities, "
        f"`{labels_summary.get('cameras_count', 0)}` cameras; pre-grouped neutrally by event and track).",
        "",
        "| Model | Dim | Rank-1 (all / cross-cam) | mAP (all / cross-cam) | Calibrated Threshold (F1) | GPU ms/crop (med / p95) | GPU MiB | License | Install Source (Ruling 333 §4) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for r in results:
        lines.append(
            f"| `{r.model_key}` | {r.embedding_dim} | "
            f"{r.rank1 * 100:.1f}% / {r.cross_camera_rank1 * 100:.1f}% | "
            f"{r.map_score * 100:.1f}% / {r.cross_camera_map * 100:.1f}% | "
            f"`{r.calibrated_threshold:.3f}` ({r.calibrated_f1:.3f}) | "
            f"{r.latency_median_ms:.2f} / {r.latency_p95_ms:.2f} ms | "
            f"{r.vram_mib} | {r.license_name} | {r.install_source} |"
        )
    lines.append("")
    lines.append("### Checkpoint SHA-256 Pins")
    for r in results:
        spec = MODEL_SPECS[r.model_key]
        lines.append(f"- `{spec.filename}` (`{r.model_key}`): `{spec.sha256}`")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B2.3 Re-ID model bake-off CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_fetch = sub.add_parser("fetch", help="Fetch and SHA-256 verify all 4 bake-off checkpoints")
    p_fetch.add_argument("--zoo-dir", type=Path, required=True)
    p_fetch.add_argument(
        "--models",
        nargs="+",
        default=list(MODEL_SPECS.keys()),
        choices=list(MODEL_SPECS.keys()),
    )

    p_export = sub.add_parser("export", help="Export a challenger model to ONNX or TensorRT plan")
    p_export.add_argument(
        "--role", required=True, choices=[k for k in MODEL_SPECS if k != "osnet_ain_x1_0"]
    )
    p_export.add_argument("--model-path", type=Path, required=True)
    p_export.add_argument("--output-path", type=Path, required=True)
    p_export.add_argument("--precision", choices=["fp16", "fp32"], default="fp16")
    p_export.add_argument("--plan-timeout", type=int, default=DEFAULT_PLAN_TIMEOUT_S)

    p_score = sub.add_parser("score", help="Score saved embeddings JSON against labels.json")
    p_score.add_argument("--labels", type=Path, required=True)
    p_score.add_argument("--runs-json", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.cmd == "fetch":
        for key in args.models:
            path = fetch_checkpoint(key, args.zoo_dir)
            print(f"{key}: {path} sha256={MODEL_SPECS[key].sha256} OK")
        return 0

    if args.cmd == "export":
        if args.output_path.suffix == ".onnx":
            if args.role == "clip_reid_vit_b_16":
                export_clip_reid_onnx(args.model_path, args.output_path)
            else:
                export_tao_swin_onnx(args.role, args.model_path, args.output_path)
        elif args.output_path.suffix == ".plan":
            compile_challenger_plan(
                args.role,
                args.model_path,
                args.output_path,
                precision=args.precision,
                plan_timeout=args.plan_timeout,
            )
        else:
            raise SystemExit(f"Unsupported output suffix: {args.output_path.suffix}")
        return 0

    if args.cmd == "score":
        labels_doc = json.loads(args.labels.read_text(encoding="utf-8"))
        runs_doc = json.loads(args.runs_json.read_text(encoding="utf-8"))
        metrics: list[BakeoffMetrics] = []
        for entry in runs_doc["models"]:
            metrics.append(
                score_model_embeddings(
                    model_key=str(entry["model_key"]),
                    labels=labels_doc["crops"],
                    embeddings=entry["embeddings"],
                    latency_ms=entry.get("latency_ms", []),
                    vram_mib=int(entry.get("vram_mib", 0)),
                )
            )
        print(format_bakeoff_report(metrics, labels_summary=labels_doc.get("summary", {})))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
