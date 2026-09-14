#!/usr/bin/env python3
"""Export ST-GCN++ model to ONNX for Triton serving.

Standalone export script (no backend dependencies). Converts pyskl checkpoint
to ONNX for deployment via Triton Inference Server.

Usage:
    python export_stgcn.py --checkpoint /models/zoo/stgcn-plus-plus/stgcnpp_ntu60_xsub_hrnet_j.pth \
        --output-path /models/cache/stgcn_action/1/model.onnx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn


def _build_coco_adjacency() -> np.ndarray:
    """Build COCO skeleton adjacency matrix (3, 17, 17)."""
    num_node = 17
    inward = [
        (15, 13), (13, 11), (16, 14), (14, 12), (11, 5), (12, 6),
        (9, 7), (7, 5), (10, 8), (8, 6), (5, 0), (6, 0), (1, 0), (3, 1), (2, 0), (4, 2),
    ]
    outward = [(j, i) for (i, j) in inward]
    self_link = [(i, i) for i in range(num_node)]

    def _edge2mat(edges):
        mat = np.zeros((num_node, num_node), dtype=np.float32)
        for i, j in edges:
            mat[j, i] = 1.0
        return mat

    def _normalize(mat):
        Dl = np.sum(mat, axis=0)
        Dn = np.zeros_like(mat)
        for i in range(num_node):
            if Dl[i] > 0:
                Dn[i, i] = Dl[i] ** (-1)
        return np.dot(mat, Dn)

    iden = _edge2mat(self_link)
    in_mat = _normalize(_edge2mat(inward))
    out_mat = _normalize(_edge2mat(outward))
    return np.stack([iden, in_mat, out_mat]).astype(np.float32)


class _GCNUnit(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, A: torch.Tensor) -> None:
        super().__init__()
        num_subsets = A.shape[0]
        self.num_subsets = num_subsets
        self.out_channels = out_channels
        self.conv = nn.Conv2d(in_channels, out_channels * num_subsets, 1)
        self.bn = nn.BatchNorm2d(out_channels)
        self.register_buffer("A", A.clone())
        self.down = None
        if in_channels != out_channels:
            self.down = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, 1),
                nn.BatchNorm2d(out_channels),
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        N, C, T, V = x.shape
        res = self.down(x) if self.down is not None else x
        z = self.conv(x)
        z = z.view(N, self.num_subsets, self.out_channels, T, V)
        A = self.A
        out = torch.zeros(N, self.out_channels, T, V, device=x.device, dtype=x.dtype)
        for k in range(self.num_subsets):
            out = out + torch.einsum("nctv,vw->nctw", z[:, k], A[k])
        out = self.bn(out)
        return F.relu(out + res, inplace=True)


class _TemporalConvWrap(nn.Module):
    def __init__(self, in_ch: int, out_ch: int, kernel_size: int = 3, stride: int = 1,
                 dilation: int = 1, padding: int = 1) -> None:
        super().__init__()
        self.conv = nn.Conv2d(in_ch, out_ch, (kernel_size, 1), (stride, 1), (padding, 0), (dilation, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(x)


class _TCNUnit(nn.Module):
    def __init__(self, channels: int, stride: int = 1) -> None:
        super().__init__()
        self.stride = stride
        num_total_branches = 6
        branch_ch = channels // num_total_branches
        first_ch = channels - branch_ch * (num_total_branches - 1)
        self.branches = nn.ModuleList()
        for i in range(4):
            ch = first_ch if i == 0 else branch_ch
            dilation = i + 1
            padding = dilation * (3 - 1) // 2
            self.branches.append(nn.Sequential(
                nn.Conv2d(channels, ch, 1), nn.BatchNorm2d(ch), nn.ReLU(inplace=True),
                _TemporalConvWrap(ch, ch, 3, stride, dilation, padding),
            ))
        self.branches.append(nn.Sequential(nn.Conv2d(channels, branch_ch, 1), nn.BatchNorm2d(branch_ch)))
        self.branches.append(nn.Conv2d(channels, branch_ch, 1))
        self.bn = nn.BatchNorm2d(channels)
        self.transform = nn.Sequential(nn.BatchNorm2d(channels), nn.ReLU(inplace=True), nn.Conv2d(channels, channels, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        res = self.transform(x)
        if self.stride > 1:
            res = F.avg_pool2d(res, (self.stride, 1), (self.stride, 1))
        outs = [self.branches[i](x) for i in range(4)]
        out4 = self.branches[4](x)
        if self.stride > 1:
            out4 = F.avg_pool2d(out4, (self.stride, 1), (self.stride, 1))
        outs.append(out4)
        if self.stride > 1:
            outs.append(self.branches[5](F.max_pool2d(x, (3, 1), (self.stride, 1), (1, 0))))
        else:
            outs.append(self.branches[5](x))
        out = torch.cat(outs, dim=1)
        return self.bn(out) + res


class _STGCNPPBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int, A: torch.Tensor, stride: int = 1) -> None:
        super().__init__()
        self.stride = stride
        self.gcn = _GCNUnit(in_ch, out_ch, A)
        self.tcn = _TCNUnit(out_ch, stride=stride)
        if in_ch != out_ch or stride != 1:
            self.residual = nn.ModuleDict({"conv": nn.Conv2d(in_ch, out_ch, 1), "bn": nn.BatchNorm2d(out_ch)})
            self._has_block_residual = True
        else:
            self._has_block_residual = False

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self._has_block_residual:
            res = self.residual["bn"](self.residual["conv"](x))
            if self.stride > 1:
                res = F.avg_pool2d(res, (self.stride, 1), (self.stride, 1))
        else:
            res = x
        return F.relu(self.tcn(self.gcn(x)) + res)


class STGCNPP(nn.Module):
    def __init__(self, num_classes: int = 60, in_channels: int = 3, num_person: int = 2) -> None:
        super().__init__()
        A = torch.tensor(_build_coco_adjacency(), dtype=torch.float32)
        self.data_bn = nn.BatchNorm1d(in_channels * 17)
        channels = [64, 64, 64, 64, 128, 128, 128, 256, 256, 256]
        strides = [1, 1, 1, 1, 2, 1, 1, 2, 1, 1]
        self.gcn = nn.ModuleList()
        c_in = in_channels
        for i in range(10):
            self.gcn.append(_STGCNPPBlock(c_in, channels[i], A, strides[i]))
            c_in = channels[i]
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Linear(256, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        N, M, T, V, C = x.shape
        x = x.permute(0, 1, 4, 3, 2).contiguous().view(N * M, C * V, T)
        x = self.data_bn(x)
        x = x.view(N * M, C, V, T).permute(0, 1, 3, 2).contiguous()
        for block in self.gcn:
            x = block(x)
        x = self.pool(x).view(N, M, -1).mean(dim=1)
        return self.fc(x)


def _map_checkpoint_keys(state_dict: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    mapped = {}
    for key, value in state_dict.items():
        new_key = key
        if new_key.startswith("backbone."):
            new_key = new_key[len("backbone."):]
        if new_key.startswith("cls_head.fc_cls."):
            new_key = new_key.replace("cls_head.fc_cls.", "fc.")
        elif new_key.startswith("cls_head."):
            new_key = new_key[len("cls_head."):]
        mapped[new_key] = value
    return mapped


def main() -> int:
    parser = argparse.ArgumentParser(description="Export ST-GCN++ to ONNX")
    parser.add_argument("--checkpoint", type=str, required=True, help="Path to .pth checkpoint")
    parser.add_argument("--output-path", type=str, required=True, help="Output ONNX path")
    parser.add_argument("--opset", type=int, default=17, help="ONNX opset version")
    args = parser.parse_args()

    checkpoint_path = Path(args.checkpoint)
    if not checkpoint_path.exists():
        print(f"Error: checkpoint not found at {checkpoint_path}", file=sys.stderr)
        return 1

    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading checkpoint from {checkpoint_path}")
    checkpoint = torch.load(str(checkpoint_path), map_location="cpu", weights_only=False)
    state_dict = checkpoint.get("state_dict", checkpoint)

    model = STGCNPP(num_classes=60, in_channels=3, num_person=2)
    mapped_dict = _map_checkpoint_keys(state_dict)
    missing, unexpected = model.load_state_dict(mapped_dict, strict=False)
    if missing:
        print(f"Warning: missing keys: {missing[:5]}{'...' if len(missing) > 5 else ''}")
    if unexpected:
        print(f"Warning: unexpected keys: {unexpected[:5]}{'...' if len(unexpected) > 5 else ''}")

    model.eval()
    print(f"Model loaded: {sum(p.numel() for p in model.parameters()):,} parameters")

    dummy_input = torch.randn(1, 2, 100, 17, 3)
    with torch.inference_mode():
        output = model(dummy_input)
        print(f"Forward pass OK: output shape = {output.shape}")

    print(f"Exporting to ONNX (opset {args.opset})...")
    torch.onnx.export(
        model,
        dummy_input,
        str(output_path),
        opset_version=args.opset,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch", 2: "frames"}, "output": {0: "batch"}},
    )

    import onnx
    onnx_model = onnx.load(str(output_path))
    onnx.checker.check_model(onnx_model)
    print(f"ONNX saved to {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
