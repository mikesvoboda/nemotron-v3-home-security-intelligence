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
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Person Re-ID (OSNet-AIN x1.0) to ONNX")
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
        help="Output path for the ONNX model file",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip ONNX validation step",
    )
    args = parser.parse_args()

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
