#!/usr/bin/env python3
"""Export ST-GCN++ model to ONNX for Triton serving.

This script converts the pyskl ST-GCN++ checkpoint to ONNX format
for deployment via Triton Inference Server.

Usage:
    python scripts/export_stgcn_onnx.py

Input checkpoint: /export/ai_models/model-zoo/stgcn-plus-plus/stgcnpp_ntu60_xsub_hrnet_j.pth
Output ONNX: ai/triton/model_repository/stgcn_action/1/model.onnx
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import torch
from backend.services.stgcn_loader import STGCNPP, _map_checkpoint_keys


def export_to_onnx(
    checkpoint_path: str,
    output_path: str,
    opset_version: int = 17,
) -> None:
    """Export ST-GCN++ to ONNX.

    Args:
        checkpoint_path: Path to the .pth checkpoint file
        output_path: Path for the output .onnx file
        opset_version: ONNX opset version (default 17)
    """
    print(f"Loading checkpoint from {checkpoint_path}")

    # Load checkpoint
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    state_dict = checkpoint.get("state_dict", checkpoint)

    # Create model
    model = STGCNPP(num_classes=60, in_channels=3, num_person=2)
    mapped_dict = _map_checkpoint_keys(state_dict)
    missing, unexpected = model.load_state_dict(mapped_dict, strict=False)
    if missing:
        print(f"Warning: missing keys: {missing[:5]}{'...' if len(missing) > 5 else ''}")
    if unexpected:
        print(f"Warning: unexpected keys: {unexpected[:5]}{'...' if len(unexpected) > 5 else ''}")

    model.eval()
    params = sum(p.numel() for p in model.parameters())
    print(f"Model loaded: {params:,} parameters")

    # Create dummy input: (1, M=2, T=100, V=17, C=3)
    dummy_input = torch.randn(1, 2, 100, 17, 3)

    # Verify forward pass
    with torch.inference_mode():
        output = model(dummy_input)
        print(f"Forward pass OK: output shape = {output.shape}")

    # Export to ONNX
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Exporting to ONNX (opset {opset_version})...")
    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        opset_version=opset_version,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={
            "input": {0: "batch", 2: "frames"},
            "output": {0: "batch"},
        },
    )

    # Verify ONNX model
    import onnx

    onnx_model = onnx.load(output_path)
    onnx.checker.check_model(onnx_model)

    file_size = Path(output_path).stat().st_size
    print(f"ONNX model saved to {output_path} ({file_size / 1024 / 1024:.1f} MB)")
    print("ONNX model validation passed")


if __name__ == "__main__":
    import os

    checkpoint = os.environ.get(
        "STGCN_CHECKPOINT",
        "/export/ai_models/model-zoo/stgcn-plus-plus/stgcnpp_ntu60_xsub_hrnet_j.pth",
    )
    output = os.environ.get(
        "STGCN_ONNX_OUTPUT",
        str(
            Path(__file__).resolve().parent.parent
            / "ai/triton/model_repository/stgcn_action/1/model.onnx"
        ),
    )

    if not Path(checkpoint).exists():
        print(f"Error: checkpoint not found at {checkpoint}")
        print("Download with:")
        print(
            "  curl -L -o /export/ai_models/model-zoo/stgcn-plus-plus/stgcnpp_ntu60_xsub_hrnet_j.pth "
            "http://download.openmmlab.com/mmaction/pyskl/ckpt/stgcnpp/stgcnpp_ntu60_xsub_hrnet/j.pth"
        )
        sys.exit(1)

    export_to_onnx(checkpoint, output)
