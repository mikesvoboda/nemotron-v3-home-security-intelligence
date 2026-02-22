#!/usr/bin/env python3
"""Export Person Re-ID (OSNet-AIN x1.0) to ONNX format for Triton Inference Server.

Model: OSNet-AIN x1.0 — Omni-Scale Feature Learning with Attention Instance Normalization.
Source: /models/zoo/osnet-ain-x1-0/osnet_ain_x1_0_msmt17.pth (raw PyTorch checkpoint)
Input: (B, 3, 256, 128) FP32 — ImageNet-normalized (height=256, width=128)
Output: (B, 512) FP32 — L2-normalizable embedding vector

Upgraded from OSNet-x0.25 to OSNet-AIN x1.0 for 4x better re-identification
accuracy (NEM-5562). Uses MSMT17 domain-generalization trained weights.

This model uses a standalone OSNet architecture (no torchreid dependency).
The architecture is reproduced from ai/enrichment-light/models/person_reid.py
which defines the complete OSNet-AIN x1.0 network structure.

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


# =============================================================================
# OSNet Architecture Components
# Reproduced from ai/enrichment-light/models/person_reid.py
# =============================================================================


class ConvLayer(nn.Module):
    """Convolution layer (conv + bn + relu)."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        stride: int = 1,
        padding: int = 0,
        groups: int = 1,
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
        self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)

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
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.relu(self.bn(self.conv(x)))


class Conv1x1Linear(nn.Module):
    """1x1 convolution + bn (without non-linearity)."""

    def __init__(self, in_channels: int, out_channels: int, stride: int = 1):
        super().__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, 1, stride=stride, padding=0, bias=False)
        self.bn = nn.BatchNorm2d(out_channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.bn(self.conv(x))


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
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.relu(self.bn(self.conv2(self.conv1(x))))


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
            self.norm1 = nn.LayerNorm([in_channels // reduction, 1, 1])
        self.relu = nn.ReLU(inplace=True)
        self.fc2 = nn.Conv2d(
            in_channels // reduction, num_gates, kernel_size=1, bias=True, padding=0
        )
        if gate_activation == "sigmoid":
            self.gate_activation: nn.Module | None = nn.Sigmoid()
        elif gate_activation == "relu":
            self.gate_activation = nn.ReLU(inplace=True)
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
    """Omni-scale feature learning block with optional instance normalization."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        bottleneck_reduction: int = 4,
        instance_norm: bool = False,
    ):
        super().__init__()
        mid_channels = out_channels // bottleneck_reduction
        self.conv1 = Conv1x1(in_channels, mid_channels)
        self.conv2a = LightConv3x3(mid_channels, mid_channels)
        self.conv2b = nn.Sequential(
            LightConv3x3(mid_channels, mid_channels),
            LightConv3x3(mid_channels, mid_channels),
        )
        self.conv2c = nn.Sequential(
            LightConv3x3(mid_channels, mid_channels),
            LightConv3x3(mid_channels, mid_channels),
            LightConv3x3(mid_channels, mid_channels),
        )
        self.conv2d = nn.Sequential(
            LightConv3x3(mid_channels, mid_channels),
            LightConv3x3(mid_channels, mid_channels),
            LightConv3x3(mid_channels, mid_channels),
            LightConv3x3(mid_channels, mid_channels),
        )
        self.gate = ChannelGate(mid_channels)
        self.conv3 = Conv1x1Linear(mid_channels, out_channels)
        self.downsample: Conv1x1Linear | None = None
        if in_channels != out_channels:
            self.downsample = Conv1x1Linear(in_channels, out_channels)
        self.IN: nn.InstanceNorm2d | None = None
        if instance_norm:
            self.IN = nn.InstanceNorm2d(out_channels, affine=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        identity = x
        x1 = self.conv1(x)
        x2a = self.conv2a(x1)
        x2b = self.conv2b(x1)
        x2c = self.conv2c(x1)
        x2d = self.conv2d(x1)
        x2 = self.gate(x2a) + self.gate(x2b) + self.gate(x2c) + self.gate(x2d)
        x3 = self.conv3(x2)
        if self.downsample is not None:
            identity = self.downsample(identity)
        out = x3 + identity
        if self.IN is not None:
            out = self.IN(out)
        return F.relu(out)


class OSNet(nn.Module):
    """Omni-Scale Network with Attention Instance Normalization for Person Re-Identification.

    This is the complete OSNet-AIN architecture reproduced from
    ai/enrichment-light/models/person_reid.py to avoid import dependencies.
    """

    def __init__(
        self,
        num_classes: int,
        blocks: list[type[OSBlock]],
        layers: list[int],
        channels: list[int],
        feature_dim: int = 512,
        conv1_IN: bool = False,
        instance_norm_blocks: list[bool] | None = None,
    ):
        super().__init__()
        num_blocks = len(blocks)
        self.feature_dim = feature_dim

        # Convolutional backbone
        self.conv1 = ConvLayer(3, channels[0], 7, stride=2, padding=3)
        self.conv1_IN: nn.InstanceNorm2d | None = None
        if conv1_IN:
            self.conv1_IN = nn.InstanceNorm2d(channels[0], affine=True)
        self.maxpool = nn.MaxPool2d(3, stride=2, padding=1)

        if instance_norm_blocks is None:
            instance_norm_blocks = [False] * num_blocks
        self.conv2 = self._make_layer(
            blocks[0], layers[0], channels[0], channels[1], True, instance_norm_blocks[0]
        )
        self.conv3 = self._make_layer(
            blocks[1], layers[1], channels[1], channels[2], True, instance_norm_blocks[1]
        )
        self.conv4 = self._make_layer(
            blocks[2], layers[2], channels[2], channels[3], False, instance_norm_blocks[2]
        )
        self.conv5 = Conv1x1(channels[3], channels[3])
        self.global_avgpool = nn.AdaptiveAvgPool2d(1)

        # Fully connected layer for feature extraction
        self.fc = nn.Sequential(
            nn.Linear(channels[3], feature_dim),
            nn.BatchNorm1d(feature_dim),
            nn.ReLU(inplace=True),
        )

        # Identity classification layer (used during training only)
        self.classifier = nn.Linear(feature_dim, num_classes)

    def _make_layer(
        self,
        block: type[OSBlock],
        layer: int,
        in_channels: int,
        out_channels: int,
        reduce_spatial_size: bool,
        instance_norm: bool = False,
    ) -> nn.Sequential:
        layers_list: list[nn.Module] = [
            block(in_channels, out_channels, instance_norm=instance_norm)
        ]
        for _ in range(1, layer):
            layers_list.append(block(out_channels, out_channels, instance_norm=instance_norm))
        if reduce_spatial_size:
            layers_list.append(
                nn.Sequential(Conv1x1(out_channels, out_channels), nn.AvgPool2d(2, stride=2))
            )
        return nn.Sequential(*layers_list)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass returns embeddings (not logits) when in eval mode."""
        x = self.conv1(x)
        if self.conv1_IN is not None:
            x = self.conv1_IN(x)
        x = self.maxpool(x)
        x = self.conv2(x)
        x = self.conv3(x)
        x = self.conv4(x)
        x = self.conv5(x)
        v = self.global_avgpool(x)
        # Use flatten(1) instead of view(v.size(0), -1) so ONNX export
        # correctly traces a dynamic batch dimension on the output tensor.
        v = v.flatten(1)
        v = self.fc(v)
        # During inference (eval mode), return feature embeddings
        if not self.training:
            return v
        # During training, return classifier logits
        return self.classifier(v)


def create_osnet_ain_x1_0(num_classes: int = 1) -> OSNet:
    """Create OSNet-AIN x1.0 architecture (full-width with instance normalization).

    Args:
        num_classes: Number of output classes. Use 1 for feature extraction.

    Returns:
        OSNet model configured for AIN x1.0 width.
    """
    return OSNet(
        num_classes=num_classes,
        blocks=[OSBlock, OSBlock, OSBlock],
        layers=[2, 2, 2],
        channels=OSNET_AIN_X10_CHANNELS,
        feature_dim=EMBEDDING_DIM,
        conv1_IN=True,
        instance_norm_blocks=[True, True, False],
    )


def load_pytorch_model(model_path: str) -> torch.nn.Module:
    """Load OSNet-AIN x1.0 from a PyTorch checkpoint file.

    Creates the model with num_classes matching the checkpoint so that all
    weights load without size mismatches.  The classifier head is only used
    during training; in eval mode the forward() method returns the 512-dim
    embedding vector before the classifier, so the extra classifier weights
    are harmless dead weight that never affect inference output.

    Handles both direct state dicts and DataParallel-wrapped checkpoints
    (keys prefixed with 'module.').

    Args:
        model_path: Path to the .pth checkpoint file.

    Returns:
        Loaded OSNet model in eval mode.

    Raises:
        FileNotFoundError: If the checkpoint file does not exist.
    """
    weights_path = Path(model_path)
    if not weights_path.exists():
        raise FileNotFoundError(f"Model weights not found: {weights_path}")

    logger.info(f"Loading weights from {model_path}")
    state_dict = torch.load(str(weights_path), map_location="cpu", weights_only=True)

    # Handle DataParallel-wrapped checkpoints
    if any(k.startswith("module.") for k in state_dict):
        state_dict = {k.replace("module.", ""): v for k, v in state_dict.items()}
        logger.info("Stripped 'module.' prefix from DataParallel checkpoint")

    # Detect num_classes from checkpoint classifier weights so the model
    # architecture matches the pretrained checkpoint exactly.
    num_classes = 1  # default fallback
    if "classifier.weight" in state_dict:
        num_classes = state_dict["classifier.weight"].shape[0]
        logger.info(f"Detected num_classes={num_classes} from checkpoint classifier weights")

    logger.info(f"Creating OSNet-AIN x1.0 architecture (num_classes={num_classes})...")
    model = create_osnet_ain_x1_0(num_classes=num_classes)

    # Load weights — should be an exact match now
    missing, unexpected = model.load_state_dict(state_dict, strict=False)

    missing_important = [k for k in missing if "classifier" not in k]
    if missing_important:
        logger.warning(f"Missing keys in state_dict: {missing_important}")
    if unexpected:
        logger.debug(f"Unexpected keys in state_dict (ignored): {unexpected}")

    model.eval()
    logger.info(
        f"OSNet-AIN x1.0 loaded: input ({INPUT_HEIGHT}x{INPUT_WIDTH}), output ({EMBEDDING_DIM},)"
    )
    return model


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
    """Validate the ONNX model by comparing outputs against PyTorch.

    Tests multiple batch sizes to verify dynamic axis support,
    and checks that embeddings are numerically close.

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

    try:
        model = load_pytorch_model(args.model_path)
        export_to_onnx(model, args.output_path)

        if not args.skip_validation:
            if not validate_onnx(model, args.output_path):
                logger.error("Validation failed — exported ONNX may produce incorrect results")
                return 1

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
