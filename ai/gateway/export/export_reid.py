#!/usr/bin/env python3
"""Export Person Re-ID (OSNet-AIN x1.0) to ONNX format for Triton Inference Server.

Model: OSNet-AIN x1.0 — Omni-Scale Network with instance normalization (IN stem,
    IN inside the residual branch of selected omni-scale blocks).
Source: /models/zoo/osnet-ain-x1-0/osnet_ain_x1_0_msmt17.pth (raw PyTorch checkpoint)
Input: (B, 3, 256, 128) FP32 — ImageNet-normalized (height=256, width=128)
Output: (B, 512) FP32 — the raw embedding, NOT L2-normalized. This is
    torchreid's eval-mode forward (fc = Linear + BatchNorm1d + ReLU, no
    normalization); consumers normalize it (gateway /person-reid in
    ai/gateway/adapters/enrichment_light.py, backend
    backend/services/osnet_loader.py).

Upgraded from OSNet-x0.25 to OSNet-AIN x1.0 for 4x better re-identification
accuracy (NEM-5562). Uses MSMT17 domain-generalization trained weights.

The architecture below is a standalone port of torchreid 0.2.5's
``torchreid/reid/models/osnet_ain.py::osnet_ain_x1_0`` — the same network the
backend builds with ``build_model('osnet_ain_x1_0')`` — because the ai-gateway
image does not ship torchreid. It must stay key-for-key and numerically
identical to torchreid: ai/gateway/tests/test_export_reid.py checks both against
torchreid itself, and load_pytorch_model refuses any backbone key mismatch.

Reference:
    Zhou et al. "Omni-Scale Feature Learning for Person Re-Identification."
    ICCV 2019.
    Zhou et al. "Learning Generalisable Omni-Scale Representations
    for Person Re-Identification." TPAMI 2021.

Usage:
    python export_reid.py \
        --model-path /models/zoo/osnet-ain-x1-0/osnet_ain_x1_0_msmt17.pth \
        --output-path /models/repository/reid/1/model.onnx

    # O2.4 (owner ruling 107): compile the TensorRT plan the gateway's `reid`
    # serves. Run ON the serving GPU — engines are architecture-specific — and
    # it COMPILES the model.onnx beside the target rather than re-deriving it,
    # refusing unless that ONNX's provenance record vouches for THESE bytes.
    python export_reid.py \
        --model-path /models/zoo/osnet-ain-x1-0/osnet_ain_x1_0_msmt17.pth \
        --output-path /models/cache/reid/1/model.plan
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
import torch
from torch import nn
from torch.nn import functional as F

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# OSNet-AIN x1.0 input dimensions (standard person ReID)
INPUT_HEIGHT = 256
INPUT_WIDTH = 128

# Output embedding dimension
EMBEDDING_DIM = 512

# OSNet-AIN x1.0 channel configuration (full-width)
OSNET_AIN_X10_CHANNELS = [64, 256, 384, 512]

# The identity-classification head is trained per dataset (MSMT17: 4101
# identities) and never runs in the eval forward the ONNX captures — the only
# part of a checkpoint that may legitimately be absent or differ.
CLASSIFIER_PREFIX = "classifier."


# =============================================================================
# OSNet-AIN architecture — port of torchreid/reid/models/osnet_ain.py (0.2.5).
# Module attribute names are load-bearing: they ARE the checkpoint keys.
# =============================================================================


class ConvLayer(nn.Module):
    """Convolution layer (conv + norm + relu); the norm is affine IN when ``instance_norm``."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        stride: int = 1,
        padding: int = 0,
        groups: int = 1,
        instance_norm: bool = False,
    ):
        super().__init__()
        self.conv = nn.Conv2d(
            in_channels,
            out_channels,
            kernel_size,
            stride=stride,
            padding=padding,
            bias=False,
            groups=groups,
        )
        # torchreid names the norm "bn" even when it is an InstanceNorm.
        self.bn: nn.Module
        if instance_norm:
            self.bn = nn.InstanceNorm2d(out_channels, affine=True)
        else:
            self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.relu(self.bn(self.conv(x)))


class Conv1x1(nn.Module):
    """1x1 convolution + bn + relu."""

    def __init__(self, in_channels: int, out_channels: int, stride: int = 1, groups: int = 1):
        super().__init__()
        self.conv = nn.Conv2d(
            in_channels,
            out_channels,
            1,
            stride=stride,
            padding=0,
            bias=False,
            groups=groups,
        )
        self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.relu(self.bn(self.conv(x)))


class Conv1x1Linear(nn.Module):
    """1x1 convolution + optional bn (without non-linearity)."""

    def __init__(self, in_channels: int, out_channels: int, stride: int = 1, bn: bool = True):
        super().__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, 1, stride=stride, padding=0, bias=False)
        self.bn: nn.BatchNorm2d | None = None
        if bn:
            self.bn = nn.BatchNorm2d(out_channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.conv(x)
        if self.bn is not None:
            x = self.bn(x)
        return x


class LightConv3x3(nn.Module):
    """Lightweight 3x3 convolution: 1x1 (linear) + dw 3x3 (nonlinear)."""

    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, 1, stride=1, padding=0, bias=False)
        self.conv2 = nn.Conv2d(
            out_channels,
            out_channels,
            3,
            stride=1,
            padding=1,
            bias=False,
            groups=out_channels,
        )
        self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.relu(self.bn(self.conv2(self.conv1(x))))


class LightConvStream(nn.Module):
    """Lightweight convolution stream: ``depth`` stacked LightConv3x3."""

    def __init__(self, in_channels: int, out_channels: int, depth: int):
        super().__init__()
        if depth < 1:
            raise ValueError(f"depth must be equal to or larger than 1, but got {depth}")
        layers = [LightConv3x3(in_channels, out_channels)]
        layers += [LightConv3x3(out_channels, out_channels) for _ in range(depth - 1)]
        self.layers = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.layers(x)


class ChannelGate(nn.Module):
    """Mini-network that generates channel-wise gates conditioned on input."""

    def __init__(
        self,
        in_channels: int,
        num_gates: int | None = None,
        return_gates: bool = False,
        gate_activation: str = "sigmoid",
        reduction: int = 16,
        layer_norm: bool = False,
    ):
        super().__init__()
        if num_gates is None:
            num_gates = in_channels
        self.return_gates = return_gates
        self.global_avgpool = nn.AdaptiveAvgPool2d(1)
        self.fc1 = nn.Conv2d(
            in_channels, in_channels // reduction, kernel_size=1, bias=True, padding=0
        )
        self.norm1: nn.LayerNorm | None = None
        if layer_norm:
            self.norm1 = nn.LayerNorm((in_channels // reduction, 1, 1))
        self.relu = nn.ReLU()
        self.fc2 = nn.Conv2d(
            in_channels // reduction, num_gates, kernel_size=1, bias=True, padding=0
        )
        if gate_activation == "sigmoid":
            self.gate_activation: nn.Module | None = nn.Sigmoid()
        elif gate_activation == "relu":
            self.gate_activation = nn.ReLU()
        elif gate_activation == "linear":
            self.gate_activation = None
        else:
            raise RuntimeError(f"Unknown gate activation: {gate_activation}")

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        input_tensor = x
        x = self.global_avgpool(x)
        x = self.fc1(x)
        if self.norm1 is not None:
            x = self.norm1(x)
        x = self.relu(x)
        x = self.fc2(x)
        if self.gate_activation is not None:
            x = self.gate_activation(x)
        if self.return_gates:
            return x
        return input_tensor * x


class OSBlock(nn.Module):
    """Omni-scale feature learning block: T streams of depth 1..T, one shared gate."""

    def __init__(self, in_channels: int, out_channels: int, reduction: int = 4, T: int = 4):
        super().__init__()
        if T < 1 or out_channels < reduction or out_channels % reduction != 0:
            raise ValueError(
                f"invalid OSBlock config: out={out_channels} reduction={reduction} T={T}"
            )
        mid_channels = out_channels // reduction

        self.conv1 = Conv1x1(in_channels, mid_channels)
        self.conv2 = nn.ModuleList(
            [LightConvStream(mid_channels, mid_channels, t) for t in range(1, T + 1)]
        )
        self.gate = ChannelGate(mid_channels)
        self.conv3 = Conv1x1Linear(mid_channels, out_channels)
        self.downsample: Conv1x1Linear | None = None
        if in_channels != out_channels:
            self.downsample = Conv1x1Linear(in_channels, out_channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        identity = x
        x1 = self.conv1(x)
        x2: torch.Tensor | int = 0
        for conv2_t in self.conv2:
            x2 = x2 + self.gate(conv2_t(x1))
        x3 = self.conv3(x2)
        if self.downsample is not None:
            identity = self.downsample(identity)
        return F.relu(x3 + identity)


class OSBlockINin(nn.Module):
    """Omni-scale block with instance normalization inside the residual branch.

    Differs from OSBlock in exactly two places: conv3 has no BatchNorm, and an
    affine InstanceNorm ("IN") normalizes the branch BEFORE the residual add.
    """

    def __init__(self, in_channels: int, out_channels: int, reduction: int = 4, T: int = 4):
        super().__init__()
        if T < 1 or out_channels < reduction or out_channels % reduction != 0:
            raise ValueError(
                f"invalid OSBlockINin config: out={out_channels} reduction={reduction} T={T}"
            )
        mid_channels = out_channels // reduction

        self.conv1 = Conv1x1(in_channels, mid_channels)
        self.conv2 = nn.ModuleList(
            [LightConvStream(mid_channels, mid_channels, t) for t in range(1, T + 1)]
        )
        self.gate = ChannelGate(mid_channels)
        self.conv3 = Conv1x1Linear(mid_channels, out_channels, bn=False)
        self.downsample: Conv1x1Linear | None = None
        if in_channels != out_channels:
            self.downsample = Conv1x1Linear(in_channels, out_channels)
        self.IN = nn.InstanceNorm2d(out_channels, affine=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        identity = x
        x1 = self.conv1(x)
        x2: torch.Tensor | int = 0
        for conv2_t in self.conv2:
            x2 = x2 + self.gate(conv2_t(x1))
        x3 = self.IN(self.conv3(x2))  # IN inside the residual branch
        if self.downsample is not None:
            identity = self.downsample(identity)
        return F.relu(x3 + identity)


class OSNet(nn.Module):
    """Omni-Scale Network (torchreid's OSNet class, softmax-loss variant).

    Stage layout: conv1 (7x7, IN stem for AIN) -> maxpool -> conv2 -> pool2
    -> conv3 -> pool3 -> conv4 -> conv5 (1x1) -> global avgpool -> fc.
    """

    def __init__(
        self,
        num_classes: int,
        blocks: list[list[type[nn.Module]]],
        channels: list[int],
        feature_dim: int = 512,
        conv1_instance_norm: bool = False,
    ):
        super().__init__()
        if len(blocks) != len(channels) - 1:
            raise ValueError("OSNet needs one channel width per stage plus the stem width")
        self.feature_dim = feature_dim

        # Convolutional backbone
        self.conv1 = ConvLayer(
            3, channels[0], 7, stride=2, padding=3, instance_norm=conv1_instance_norm
        )
        self.maxpool = nn.MaxPool2d(3, stride=2, padding=1)
        self.conv2 = self._make_layer(blocks[0], channels[0], channels[1])
        self.pool2 = nn.Sequential(Conv1x1(channels[1], channels[1]), nn.AvgPool2d(2, stride=2))
        self.conv3 = self._make_layer(blocks[1], channels[1], channels[2])
        self.pool3 = nn.Sequential(Conv1x1(channels[2], channels[2]), nn.AvgPool2d(2, stride=2))
        self.conv4 = self._make_layer(blocks[2], channels[2], channels[3])
        self.conv5 = Conv1x1(channels[3], channels[3])
        self.global_avgpool = nn.AdaptiveAvgPool2d(1)

        # Fully connected layer for feature extraction
        self.fc = nn.Sequential(
            nn.Linear(channels[3], feature_dim),
            nn.BatchNorm1d(feature_dim),
            nn.ReLU(),
        )

        # Identity classification layer (used during training only)
        self.classifier = nn.Linear(feature_dim, num_classes)

    @staticmethod
    def _make_layer(
        blocks: list[type[nn.Module]], in_channels: int, out_channels: int
    ) -> nn.Sequential:
        layers = [blocks[0](in_channels, out_channels)]
        layers += [block(out_channels, out_channels) for block in blocks[1:]]
        return nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Embeddings (not logits) in eval mode — torchreid's feature-extraction output."""
        x = self.conv1(x)
        x = self.maxpool(x)
        x = self.conv2(x)
        x = self.pool2(x)
        x = self.conv3(x)
        x = self.pool3(x)
        x = self.conv4(x)
        x = self.conv5(x)
        v = self.global_avgpool(x)
        # Same values as torchreid's view(v.size(0), -1); flatten(1) makes the
        # ONNX export trace a dynamic batch dimension on the output tensor.
        v = v.flatten(1)
        v = self.fc(v)
        # During inference (eval mode), return feature embeddings
        if not self.training:
            return v
        # During training, return classifier logits
        return self.classifier(v)


def create_osnet_ain_x1_0(num_classes: int = 1) -> OSNet:
    """Create OSNet-AIN x1.0 exactly as torchreid's ``osnet_ain_x1_0(pretrained=False)``.

    No weight init is ported: the export path loads every backbone tensor
    strictly from the checkpoint (load_pytorch_model), so init never reaches
    an exported graph.

    Args:
        num_classes: Width of the (eval-unused) classifier head.

    Returns:
        OSNet model configured for AIN x1.0 width.
    """
    return OSNet(
        num_classes=num_classes,
        blocks=[
            [OSBlockINin, OSBlockINin],
            [OSBlock, OSBlockINin],
            [OSBlockINin, OSBlock],
        ],
        channels=OSNET_AIN_X10_CHANNELS,
        feature_dim=EMBEDDING_DIM,
        conv1_instance_norm=True,
    )


def load_pytorch_model(model_path: str) -> torch.nn.Module:
    """Load OSNet-AIN x1.0 from a PyTorch checkpoint file — every backbone key or nothing.

    Creates the model with num_classes matching the checkpoint so the head
    loads too when present. The head is the only tolerated difference: in
    eval mode forward() returns the 512-dim embedding before the classifier,
    so a missing or extra ``classifier.*`` key never affects the export.
    Any other missing or unexpected key raises — a silently partial load
    exports a partly random-initialized embedder.

    Handles both direct state dicts and DataParallel-wrapped checkpoints
    (keys prefixed with 'module.').

    Args:
        model_path: Path to the .pth checkpoint file.

    Returns:
        Loaded OSNet model in eval mode.

    Raises:
        FileNotFoundError: If the checkpoint file does not exist.
        RuntimeError: If any non-classifier key is missing, unexpected, or
            has the wrong shape.
    """
    weights_path = Path(model_path)
    if not weights_path.exists():
        raise FileNotFoundError(f"Model weights not found: {weights_path}")

    logger.info(f"Loading weights from {model_path}")
    state_dict = torch.load(str(weights_path), map_location="cpu", weights_only=True)

    # Handle DataParallel-wrapped checkpoints
    if any(k.startswith("module.") for k in state_dict):
        state_dict = {k.removeprefix("module."): v for k, v in state_dict.items()}
        logger.info("Stripped 'module.' prefix from DataParallel checkpoint")

    # Detect num_classes from checkpoint classifier weights so the model
    # architecture matches the pretrained checkpoint exactly.
    num_classes = 1  # default fallback
    if "classifier.weight" in state_dict:
        num_classes = state_dict["classifier.weight"].shape[0]
        logger.info(f"Detected num_classes={num_classes} from checkpoint classifier weights")

    logger.info(f"Creating OSNet-AIN x1.0 architecture (num_classes={num_classes})...")
    model = create_osnet_ain_x1_0(num_classes=num_classes)

    # strict=False only so the classifier head may differ; shape mismatches
    # still raise inside load_state_dict, and every other key is checked here.
    result = model.load_state_dict(state_dict, strict=False)
    missing = [k for k in result.missing_keys if not k.startswith(CLASSIFIER_PREFIX)]
    unexpected = [k for k in result.unexpected_keys if not k.startswith(CLASSIFIER_PREFIX)]
    if missing or unexpected:
        raise RuntimeError(
            f"{weights_path} is not a torchreid osnet_ain_x1_0 checkpoint: "
            f"{len(missing)} missing backbone keys {missing[:10]}, "
            f"{len(unexpected)} unexpected keys {unexpected[:10]} — refusing to export "
            "a partially random-initialized embedder"
        )
    head_keys = sorted(set(result.missing_keys) | set(result.unexpected_keys))
    if head_keys:
        logger.info(f"Classifier head not loaded (unused by the eval embedding): {head_keys}")
    logger.info(f"Strict backbone load OK: {len(state_dict)} checkpoint tensors, none refused")

    model.eval()
    logger.info(
        f"OSNet-AIN x1.0 loaded: input ({INPUT_HEIGHT}x{INPUT_WIDTH}), output ({EMBEDDING_DIM},)"
    )
    return model


#: The record written next to ``model.onnx``: which checkpoint the graph came
#: from. The gateway reads it to label every embedding (B2.2, owner ruling 68:
#: "the model ID on a gateway embedding comes from the source checkpoint's
#: sha256, recorded at export and reported by the gateway").
PROVENANCE_FILE = "provenance.json"

#: The models.yml row these weights belong to; the backend's osnet_model_id()
#: uses the same name, so both paths label the same weights alike.
OSNET_ZOO_NAME = "osnet-ain-x1-0"


def write_provenance(checkpoint_path: str, output_path: str) -> Path:
    """Record the source checkpoint's name and sha256 beside the ONNX file."""
    import hashlib
    import json

    checkpoint = Path(checkpoint_path)
    digest = hashlib.sha256()
    with checkpoint.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    record = {
        "zoo_name": OSNET_ZOO_NAME,
        "source_file": checkpoint.name,
        "source_sha256": digest.hexdigest(),
    }
    target = Path(output_path).parent / PROVENANCE_FILE
    target.write_text(json.dumps(record, indent=2) + "\n")
    logger.info(f"Provenance recorded: {target} (sha256 {record['source_sha256'][:12]})")
    return target


def export_to_onnx(
    model: torch.nn.Module,
    output_path: str,
) -> None:
    """Export the OSNet model to ONNX format.

    The model in eval mode returns (B, 512) embedding vectors directly.

    Args:
        model: Loaded OSNet model in eval mode.
        output_path: Destination path for the ONNX file.
    """
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    dummy_input = torch.randn(1, 3, INPUT_HEIGHT, INPUT_WIDTH, dtype=torch.float32)

    # Verify output shape
    with torch.inference_mode():
        test_output = model(dummy_input)
    assert test_output.shape == (1, EMBEDDING_DIM), (
        f"Expected output shape (1, {EMBEDDING_DIM}), got {test_output.shape}"
    )

    dynamic_axes = {
        "input": {0: "batch_size"},
        "embedding": {0: "batch_size"},
    }

    logger.info(f"Exporting to ONNX: {output_path}")
    logger.info(f"  Input shape: (B, 3, {INPUT_HEIGHT}, {INPUT_WIDTH}) FP32")
    logger.info(f"  Output shape: (B, {EMBEDDING_DIM}) FP32")
    logger.info("  Opset version: 21")

    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        export_params=True,
        opset_version=21,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["embedding"],
        dynamic_axes=dynamic_axes,
    )

    file_size_mb = Path(output_path).stat().st_size / (1024 * 1024)
    logger.info(f"ONNX model saved: {output_path} ({file_size_mb:.1f} MB)")
    logger.info(
        f"Estimated VRAM at runtime: ~{file_size_mb * 1.1:.0f} MB (model weights + buffers)"
    )


def validate_onnx(
    pytorch_model: torch.nn.Module,
    onnx_path: str,
) -> bool:
    """Validate the ONNX conversion by comparing outputs against the exported PyTorch model.

    Tests multiple batch sizes to verify dynamic axis support,
    and checks that embeddings are numerically close.

    This proves export fidelity ONLY — it compares the ONNX against the very
    model it was exported from, so it cannot see a wrong architecture (it
    passed at cosine 1.000 while a mis-ported network left 459 tensors at
    random init). Correctness against an independent reference lives
    elsewhere: load_pytorch_model refuses any backbone key mismatch, and
    ai/gateway/tests/test_export_reid.py checks the port against torchreid's
    osnet_ain_x1_0 key-for-key and numerically.

    Args:
        pytorch_model: The original PyTorch OSNet model.
        onnx_path: Path to the exported ONNX file.

    Returns:
        True if validation passes.
    """
    try:
        import onnx
        import onnxruntime as ort
    except ImportError:
        logger.warning("onnx or onnxruntime not installed — skipping validation")
        return True

    logger.info("Validating ONNX model against PyTorch...")

    onnx_model = onnx.load(onnx_path)
    onnx.checker.check_model(onnx_model)
    logger.info("ONNX model structure check passed")

    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    session = ort.InferenceSession(onnx_path, providers=providers)

    test_batch_sizes = [1, 2, 4, 8]
    all_passed = True

    for batch_size in test_batch_sizes:
        test_input = np.random.randn(batch_size, 3, INPUT_HEIGHT, INPUT_WIDTH).astype(np.float32)

        # PyTorch inference
        with torch.inference_mode():
            pt_input = torch.from_numpy(test_input)
            pt_output = pytorch_model(pt_input).numpy()

        # ONNX Runtime inference
        ort_output = session.run(None, {"input": test_input})[0]

        # Check shapes
        assert pt_output.shape == ort_output.shape == (batch_size, EMBEDDING_DIM), (
            f"Shape mismatch: PyTorch={pt_output.shape}, ONNX={ort_output.shape}"
        )

        max_diff = np.abs(pt_output - ort_output).max()
        _mean_diff = np.abs(pt_output - ort_output).mean()

        # Also check cosine similarity between embedding vectors
        cosine_sims = []
        for i in range(batch_size):
            pt_norm = pt_output[i] / (np.linalg.norm(pt_output[i]) + 1e-8)
            ort_norm = ort_output[i] / (np.linalg.norm(ort_output[i]) + 1e-8)
            cosine_sims.append(float(np.dot(pt_norm, ort_norm)))
        min_cosine = min(cosine_sims)

        if max_diff < 0.15 and min_cosine > 0.999:
            logger.info(
                f"  Batch size {batch_size}: PASS "
                f"(max_diff={max_diff:.2e}, cosine_sim>={min_cosine:.6f})"
            )
        else:
            logger.error(
                f"  Batch size {batch_size}: FAIL "
                f"(max_diff={max_diff:.2e}, min_cosine={min_cosine:.6f})"
            )
            all_passed = False

    if all_passed:
        logger.info("ONNX validation PASSED for all batch sizes")
    else:
        logger.error("ONNX validation FAILED — embeddings diverge from PyTorch")

    return all_passed


# =============================================================================
# O2.4 (owner ruling 107): the TensorRT plan the gateway's `reid` serves.
#
# Ruling 106 closed the ONNX Runtime CUDA execution provider on the GB300
# (`cudaErrorSymbolNotFound` on Blackwell/aarch64, Triton 26.01-py3), so the
# GPU path IS a TensorRT plan now: "a plan built for the serving GPU as yolo26's
# is". Two consequences shape the code below:
#
#   * An engine is GPU-architecture-specific (the warning at the top of
#     copy_yolo26_engine.py), so this step runs ON the serving host and is never
#     part of an image build or CI. Nothing here is importable-safe for a GPU:
#     `trtexec` is a subprocess, exactly as export_fashion_clip.py does it.
#   * This step COMPILES the model.onnx the ONNX pass already exported and
#     already validated against PyTorch (CPU EP — no GPU needed), per the
#     pipeline in export/README.md. It does not re-derive the ONNX and it does
#     not run inference on the engine: there is no GPU to run it on, and the
#     plan is a deterministic compile of an already-vouched graph. The numeric
#     proof of the PLAN is the owner's scripts/reid_parity_check.py run on the
#     GB300 (ruling 107's Done when), never a check invented here.
#
# What this step DOES enforce is B2.2's provenance rule at the new seam: a plan
# may only be compiled from an ONNX a provenance record vouches for, and that
# record's `source_sha256` must be the bytes of the checkpoint named on the
# command line. Without it, `export_all.sh`'s skip-if-present behaviour (an
# existing model.onnx is never re-exported, and its check already accepts a
# .plan) would let a stale pre-B2.2 ONNX — or a plan built from different
# weights than the record claims — become the model the gateway reports an ID
# for.
# =============================================================================

#: The Triton `tensorrt` backend's fixed filename inside the version dir.
PLAN_FILE = "model.plan"

#: The gateway config's `max_batch_size` for `reid`
#: (ai/triton/model_repository/reid/config.pbtxt). The plan must carry profiles
#: up to it or Triton refuses to load the engine.
MAX_BATCH = 16

#: Builder workspace. 1 GB is the value every export helper in this directory
#: defaults to because it is what fits beside the other residents on the small
#: second card (export/README.md "Notes").
DEFAULT_WORKSPACE_GB = 1

#: trtexec is pre-installed in the NVIDIA serving container but not on PATH
#: there; the same candidate list export_fashion_clip.py uses.
TRTEXEC_CANDIDATES = ("/usr/src/tensorrt/bin/trtexec", "/usr/local/bin/trtexec")


def find_trtexec() -> str | None:
    """Locate the TensorRT engine builder, or None if this host has no TensorRT."""
    found = shutil.which("trtexec")
    if found:
        return found
    for candidate in TRTEXEC_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return None


def build_tensorrt_engine(
    onnx_path: str,
    engine_path: str,
    *,
    precision: str = "fp16",
    max_batch: int = MAX_BATCH,
    workspace_gb: int = DEFAULT_WORKSPACE_GB,
    trtexec: str | None = None,
    run: Callable[..., Any] | None = None,
) -> str:
    """Compile the exported ONNX into a TensorRT plan for THIS GPU.

    The batch profiles are the config's: min 1, opt max_batch//2, max
    max_batch, on the ONNX's real input name, so the `dynamic_batching` block
    the config declares stays satisfiable inside the engine.

    Args:
        onnx_path: The already-validated ONNX to compile.
        engine_path: Destination for the plan (Triton wants ``model.plan``).
        precision: ``fp16`` (what yolo26's shipped engine is) or ``fp32``.
        max_batch: Upper bound of the dynamic batch profile.
        workspace_gb: Builder workspace, in GB.
        trtexec: Builder binary; auto-detected when omitted.
        run: Subprocess runner; ``subprocess.run`` when omitted. Injectable so
            the command shape is testable without a GPU or TensorRT.

    Returns:
        ``engine_path``, after confirming the builder actually wrote it.

    Raises:
        RuntimeError: No builder on this host, or the builder failed. A partial
            file left by a failed build is removed — a husk in the version dir
            would be linked by the entrypoint and served as a model.
    """
    builder = trtexec if trtexec is not None else find_trtexec()
    if builder is None:
        raise RuntimeError(
            "trtexec not found — a TensorRT plan must be built on the serving "
            f"host (looked for PATH plus {', '.join(TRTEXEC_CANDIDATES)})"
        )

    runner = run if run is not None else subprocess.run

    opt_batch = max(1, max_batch // 2)
    shape = f"3x{INPUT_HEIGHT}x{INPUT_WIDTH}"
    engine = Path(engine_path)
    engine.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        builder,
        f"--onnx={onnx_path}",
        f"--saveEngine={engine_path}",
        f"--minShapes=input:1x{shape}",
        f"--optShapes=input:{opt_batch}x{shape}",
        f"--maxShapes=input:{max_batch}x{shape}",
        f"--workspace={workspace_gb * 1024}",
    ]
    if precision == "fp16":
        cmd.append("--fp16")
    elif precision != "fp32":
        raise ValueError(f"unknown precision {precision!r} (expected fp16 or fp32)")

    logger.info("Building the reid TensorRT plan: %s", " ".join(cmd))
    started = time.time()
    result = runner(cmd, check=False, capture_output=True, text=True, timeout=600)
    if getattr(result, "returncode", 1) != 0:
        engine.unlink(missing_ok=True)
        stdout = getattr(result, "stdout", "") or ""
        stderr = getattr(result, "stderr", "") or ""
        logger.error("trtexec stdout:\n%s", stdout[-2000:])
        logger.error("trtexec stderr:\n%s", stderr[-2000:])
        raise RuntimeError(f"trtexec failed with return code {result.returncode}")

    if not engine.is_file():
        raise RuntimeError(f"trtexec reported success but wrote no plan at {engine_path}")

    size_mb = engine.stat().st_size / (1024 * 1024)
    logger.info("reid plan built in %.1fs (%.1f MB) -> %s", time.time() - started, size_mb, engine)
    return engine_path


def read_provenance(version_dir: Path) -> dict[str, str] | None:
    """The provenance record beside the model files, or None if there is none.

    The same path `reid_model_id()` reads in the running gateway
    (ai/gateway/adapters/enrichment_light.py:197), which is the point: what the
    export refuses to build without and what the gateway reports as the model ID
    are the same record, read the same way.
    """
    record_path = version_dir / PROVENANCE_FILE
    if not record_path.is_file():
        return None
    try:
        loaded = json.loads(record_path.read_text())
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compile_plan_from_validated_onnx(
    checkpoint_path: str,
    plan_path: str,
    *,
    precision: str = "fp16",
) -> str:
    """Compile the plan beside ``plan_path`` from the ONNX vouched for by provenance.

    Refuses (raises ``RuntimeError``) unless:
      * the sibling ``model.onnx`` exists — this step compiles, it does not re-export;
      * a provenance record stands beside it — #6970's precondition, stated as a
        stop instead of a paragraph an operator has to remember;
      * that record names this zoo model and its ``source_sha256`` is the bytes of
        ``checkpoint_path`` — so a plan can never ship labelled with weights that
        are not the ones its record vouches for.

    The record itself is never rewritten: it was written beside the ONNX after
    that ONNX was validated, and the plan inherits it (entrypoint.sh §0c links
    the whole version dir, which is why the plan is placed beside the ONNX
    rather than instead of it).
    """
    plan = Path(plan_path)
    version_dir = plan.parent
    onnx = version_dir / "model.onnx"

    if not onnx.is_file():
        raise RuntimeError(
            f"no {onnx} to compile a plan from — run the ONNX export first "
            "(export_all.sh phase 2); the plan is a compile step, not an export"
        )

    record = read_provenance(version_dir)
    if record is None:
        raise RuntimeError(
            f"no {PROVENANCE_FILE} beside {onnx} — that ONNX predates B2.2's "
            "provenance write (or was never validated), so it must not seed a "
            "plan. Delete it and re-run the ONNX export with this head."
        )

    if record.get("zoo_name") != OSNET_ZOO_NAME:
        raise RuntimeError(
            f"provenance names {record.get('zoo_name')!r}, not {OSNET_ZOO_NAME!r} — "
            f"refusing to build a plan for weights recorded as something else"
        )

    checkpoint = Path(checkpoint_path)
    if not checkpoint.is_file():
        raise RuntimeError(f"checkpoint not found: {checkpoint}")

    actual = sha256_of(checkpoint)
    recorded = str(record.get("source_sha256", ""))
    if actual != recorded:
        raise RuntimeError(
            f"checkpoint {checkpoint.name} is not the recorded weights: sha256 "
            f"{actual[:12]}… but {PROVENANCE_FILE} says {recorded[:12] or '<missing>'}… — "
            "a plan must be compiled from the same weights the ONNX and its "
            "model ID came from"
        )

    return build_tensorrt_engine(str(onnx), str(plan), precision=precision)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export Person Re-ID (OSNet-AIN x1.0) to ONNX, or compile its TensorRT plan"
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default="/models/zoo/osnet-ain-x1-0/osnet_ain_x1_0_msmt17.pth",
        help="Path to the OSNet-AIN x1.0 checkpoint file (.pth)",
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default="reid/1/model.onnx",
        help="Output path: model.onnx to export, model.plan to compile (O2.4, on the serving GPU)",
    )
    parser.add_argument(
        "--precision",
        type=str,
        default="fp16",
        choices=["fp16", "fp32"],
        help="Plan precision (plan mode only); yolo26's shipped engine is fp16",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip ONNX validation step",
    )
    args = parser.parse_args()

    # Plan mode (O2.4): a compile over the ONNX pass that already ran, guarded by
    # provenance. It loads no model and runs no inference — there is no GPU in
    # the places that run this file's tests, and a plan's numeric proof is the
    # owner's GB300 run, not a check fabricated here.
    if args.output_path.endswith(".plan"):
        try:
            compile_plan_from_validated_onnx(
                args.model_path, args.output_path, precision=args.precision
            )
            logger.info("Person Re-ID TensorRT plan complete")
            return 0
        except Exception as e:
            # Never leave a partial plan for the entrypoint to link.
            Path(args.output_path).unlink(missing_ok=True)
            logger.error(f"Plan build failed: {e}", exc_info=True)
            return 1

    # A provenance record vouches for the model.onnx beside it (B2.2): drop any
    # old one first, and write the new one only once the export is validated.
    (Path(args.output_path).parent / PROVENANCE_FILE).unlink(missing_ok=True)

    try:
        model = load_pytorch_model(args.model_path)
        export_to_onnx(model, args.output_path)

        if not args.skip_validation:
            if not validate_onnx(model, args.output_path):
                logger.error("Validation failed — exported ONNX may produce incorrect results")
                return 1

        write_provenance(args.model_path, args.output_path)
        logger.info("Person Re-ID export complete")
        return 0

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
