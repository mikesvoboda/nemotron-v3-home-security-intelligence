"""ST-GCN++ model loader for skeleton-based action recognition.

This module provides async loading and inference for ST-GCN++ (Spatial-Temporal
Graph Convolutional Network++) models trained on NTU RGB+D 60.

ST-GCN++ replaces X-CLIP for action recognition (NEM-5563):
- X-CLIP: ~2GB VRAM, requires 16 video frames, slow
- ST-GCN++: ~14MB VRAM, uses pose keypoints (already extracted), fast

The model takes 17 COCO keypoints (x, y, confidence) across T frames
and classifies actions from the NTU RGB+D 60 dataset (60 classes).

Input tensor shape: (N, C, T, V, M)
  N = batch, C = 3 (x, y, score), T = frames, V = 17 joints, M = persons

Architecture: Standalone reimplementation of pyskl's STGCN backbone + head,
loaded from pyskl-format checkpoints without requiring pyskl as a dependency.

Reference: https://github.com/kennymckormick/pyskl
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

from backend.core.logging import get_logger

logger = get_logger(__name__)

# ==============================================================================
# NTU RGB+D 60 Action Labels
# ==============================================================================
NTU60_LABELS: list[str] = [
    "drink water",
    "eat meal/snack",
    "brushing teeth",
    "brushing hair",
    "drop",
    "pickup",
    "throw",
    "sitting down",
    "standing up",
    "clapping",
    "reading",
    "writing",
    "tear up paper",
    "wear jacket",
    "take off jacket",
    "wear a shoe",
    "take off a shoe",
    "wear on glasses",
    "take off glasses",
    "put on a hat/cap",
    "take off a hat/cap",
    "cheer up",
    "hand waving",
    "kicking something",
    "reach into pocket",
    "hopping",
    "jump up",
    "make a phone call",
    "playing with phone/tablet",
    "typing on a keyboard",
    "pointing to something",
    "taking a selfie",
    "check time (from watch)",
    "rub two hands together",
    "nod head/bow",
    "shake head",
    "wipe face",
    "salute",
    "put the palms together",
    "cross hands in front",
    "sneeze/cough",
    "staggering",
    "falling",
    "touch head (headache)",
    "touch chest (stomachache/heart pain)",
    "touch back (backache)",
    "touch neck (neckache)",
    "nausea or vomiting condition",
    "use a fan/feeling warm",
    "punching/slapping other person",
    "kicking other person",
    "pushing other person",
    "pat on back of other person",
    "point finger at other person",
    "hugging other person",
    "giving something to other person",
    "touch other person's pocket",
    "handshaking",
    "walking towards each other",
    "walking apart from each other",
]

# Security-relevant action mapping for home security context
# Maps NTU-60 action indices to security risk levels
SECURITY_RISK_MAP: dict[int, str] = {
    42: "critical",  # falling
    49: "high",  # punching/slapping
    50: "high",  # kicking other person
    51: "high",  # pushing other person
    56: "high",  # touch other person's pocket (pickpocketing)
    41: "medium",  # staggering
    24: "medium",  # kicking something
    23: "low",  # hand waving
    58: "low",  # walking towards each other
    59: "low",  # walking apart from each other
}

# Actions that are security-relevant for home monitoring
SECURITY_RELEVANT_ACTIONS: frozenset[int] = frozenset(
    {
        5,  # pickup
        6,  # throw
        22,  # hand waving
        24,  # kicking something
        25,  # hopping
        26,  # jump up
        41,  # staggering
        42,  # falling
        49,  # punching/slapping other person
        50,  # kicking other person
        51,  # pushing other person
        56,  # touch other person's pocket
        58,  # walking towards each other
        59,  # walking apart from each other
    }
)

# COCO keypoint names in order (17 joints)
COCO_KEYPOINT_NAMES: list[str] = [
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
]


# ==============================================================================
# COCO Skeleton Graph
# ==============================================================================


def _build_coco_adjacency() -> np.ndarray:
    """Build the COCO skeleton adjacency matrix (3, 17, 17).

    Returns a stacked adjacency matrix with three components:
    - A[0]: Self-connections (identity)
    - A[1]: Inward edges (normalized)
    - A[2]: Outward edges (normalized)

    This matches the pyskl spatial graph construction.
    """
    num_node = 17

    # COCO inward edges (child -> parent)
    inward = [
        (15, 13),
        (13, 11),
        (16, 14),
        (14, 12),
        (11, 5),
        (12, 6),
        (9, 7),
        (7, 5),
        (10, 8),
        (8, 6),
        (5, 0),
        (6, 0),
        (1, 0),
        (3, 1),
        (2, 0),
        (4, 2),
    ]
    outward = [(j, i) for (i, j) in inward]
    self_link = [(i, i) for i in range(num_node)]

    def _edge2mat(edges: list[tuple[int, int]]) -> np.ndarray:
        mat = np.zeros((num_node, num_node), dtype=np.float32)
        for i, j in edges:
            mat[j, i] = 1.0
        return mat

    def _normalize(mat: np.ndarray) -> np.ndarray:
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


# ==============================================================================
# ST-GCN++ Model Components (matching pyskl checkpoint structure exactly)
# ==============================================================================
# Architecture reverse-engineered from the pyskl checkpoint key structure:
#   backbone.gcn.{i}.gcn.{conv, bn, A, down}  — Graph Convolution unit
#   backbone.gcn.{i}.tcn.{branches, bn, transform}  — Temporal Convolution unit
#   backbone.gcn.{i}.residual.{conv, bn}  — Block-level residual (at inflate stages)


class _GCNUnit(nn.Module):
    """Graph Convolution unit matching pyskl's gcn sub-block.

    Keys: conv, bn, A (buffer), down (optional residual)
    """

    def __init__(self, in_channels: int, out_channels: int, A: torch.Tensor) -> None:
        super().__init__()
        num_subsets = A.shape[0]  # 3
        self.num_subsets = num_subsets
        self.out_channels = out_channels

        # Partition-wise 1x1 convolution
        self.conv = nn.Conv2d(in_channels, out_channels * num_subsets, 1)
        self.bn = nn.BatchNorm2d(out_channels)
        self.register_buffer("A", A.clone())

        # Residual when channels change
        if in_channels != out_channels:
            self.down = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, 1),
                nn.BatchNorm2d(out_channels),
            )
        else:
            self.down = None

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        N, C, T, V = x.shape
        res = self.down(x) if self.down is not None else x

        z = self.conv(x)
        z = z.view(N, self.num_subsets, self.out_channels, T, V)

        out = torch.zeros(N, self.out_channels, T, V, device=x.device, dtype=x.dtype)
        for k in range(self.num_subsets):
            out = out + torch.einsum("nctv,vw->nctw", z[:, k], self.A[k])

        out = self.bn(out)
        return F.relu(out + res, inplace=True)


class _TCNBranch(nn.Module):
    """Single TCN branch with 1x1 conv + BN + optional temporal conv.

    Branches 0-3: 1x1 -> BN -> ReLU -> temporal_conv
    Branch 4: 1x1 -> BN (no temporal conv)
    """

    def __init__(
        self,
        in_ch: int,
        out_ch: int,
        *,
        has_temporal: bool = True,
        kernel_size: int = 3,
        stride: int = 1,
        dilation: int = 1,
    ) -> None:
        super().__init__()
        # ModuleList indexed as [0]=Conv2d, [1]=BN, [2]=ReLU, [3]=TemporalConv
        self.layers = nn.ModuleList(
            [
                nn.Conv2d(in_ch, out_ch, 1),
                nn.BatchNorm2d(out_ch),
            ]
        )
        if has_temporal:
            self.layers.append(nn.ReLU(inplace=True))
            padding = dilation * (kernel_size - 1) // 2
            self.layers.append(
                _TemporalConvWrap(out_ch, out_ch, kernel_size, stride, dilation, padding)
            )
        self.has_temporal = has_temporal

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.layers[0](x)
        out = self.layers[1](out)
        if self.has_temporal:
            out = self.layers[2](out)
            out = self.layers[3](out)
        return out

    # Allow subscript access for state_dict key compatibility
    def __getitem__(self, idx: int) -> nn.Module:
        return self.layers[idx]


class _TemporalConvWrap(nn.Module):
    """Temporal convolution wrapper with .conv attribute for checkpoint compat."""

    def __init__(
        self,
        in_ch: int,
        out_ch: int,
        kernel_size: int = 3,
        stride: int = 1,
        dilation: int = 1,
        padding: int = 1,
    ) -> None:
        super().__init__()
        self.conv = nn.Conv2d(
            in_ch, out_ch, (kernel_size, 1), (stride, 1), (padding, 0), (dilation, 1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(x)


class _TCNUnit(nn.Module):
    """Temporal Convolution unit matching pyskl's tcn sub-block.

    Keys: branches (ModuleList), bn, transform (Sequential)
    Branch channel distribution: ceil(ch/6) for first, floor(ch/6) for rest.
    """

    def __init__(self, channels: int, stride: int = 1) -> None:
        super().__init__()
        num_temporal_branches = 5  # branches 0-4
        num_total_branches = 6  # branches 0-5
        branch_ch = channels // num_total_branches
        first_ch = channels - branch_ch * (num_total_branches - 1)

        self.branches = nn.ModuleList()
        for i in range(num_temporal_branches):
            ch = first_ch if i == 0 else branch_ch
            if i < 4:
                # Branches 0-3: with temporal conv
                dilation = i + 1
                self.branches.append(
                    _TCNBranch(
                        channels,
                        ch,
                        has_temporal=True,
                        kernel_size=3,
                        stride=stride,
                        dilation=dilation,
                    )
                )
            else:
                # Branch 4: no temporal conv (identity path)
                self.branches.append(_TCNBranch(channels, ch, has_temporal=False))

        # Branch 5: simple 1x1 conv (maxpool-like)
        self.branches.append(nn.Conv2d(channels, branch_ch, 1))

        self.bn = nn.BatchNorm2d(channels)

        # Residual transform: BN(0) -> ReLU(1) -> Conv2d(2)
        self.transform = nn.Sequential(
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels, channels, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        res = self.transform(x)

        outs = []
        for branch in self.branches:
            outs.append(branch(x))

        out = torch.cat(outs, dim=1)
        out = self.bn(out)
        return out + res


class _STGCNPPBlock(nn.Module):
    """Single ST-GCN++ block: GCN + TCN + optional block-level residual."""

    def __init__(self, in_ch: int, out_ch: int, A: torch.Tensor, stride: int = 1) -> None:
        super().__init__()
        self.gcn = _GCNUnit(in_ch, out_ch, A)
        self.tcn = _TCNUnit(out_ch, stride=stride)

        # Block-level residual at inflate/downsample stages
        if in_ch != out_ch or stride != 1:
            self.residual = nn.ModuleDict(
                {
                    "conv": nn.Conv2d(in_ch, out_ch, 1),
                    "bn": nn.BatchNorm2d(out_ch),
                }
            )
            self._has_block_residual = True
        else:
            self._has_block_residual = False

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.tcn(self.gcn(x))


class STGCNPP(nn.Module):
    """ST-GCN++ model for skeleton-based action recognition.

    Matches the pyskl checkpoint structure exactly.

    Architecture:
    - Data BN (VC mode) -> 10 GCN+TCN blocks -> Global Average Pooling -> FC head
    - Channels: 3 -> 64 (x4) -> 128 (x3) -> 256 (x3)
    - Inflate stages: 4, 7 (channel change + temporal stride=2)
    """

    def __init__(self, num_classes: int = 60, in_channels: int = 3, num_person: int = 2) -> None:
        super().__init__()
        self.num_classes = num_classes
        self.in_channels = in_channels
        self.num_person = num_person

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
        """Forward pass.

        Args:
            x: Input tensor of shape (N, M, T, V, C)

        Returns:
            Logits of shape (N, num_classes)
        """
        N, M, T, V, C = x.shape

        # Data BN (VC mode): merge person into batch
        x = x.permute(0, 1, 4, 3, 2).contiguous().view(N * M, C * V, T)
        x = self.data_bn(x)
        x = x.view(N * M, C, V, T).permute(0, 1, 3, 2).contiguous()

        for block in self.gcn:
            x = block(x)

        x = self.pool(x).view(N, M, -1).mean(dim=1)
        return self.fc(x)


# ==============================================================================
# Result Dataclass
# ==============================================================================


@dataclass(slots=True)
class SkeletonActionResult:
    """Result from ST-GCN++ skeleton action recognition.

    Attributes:
        action_label: Human-readable action label
        action_index: NTU-60 action class index (0-59)
        confidence: Confidence score (0-1)
        security_risk: Security risk level ('critical', 'high', 'medium', 'low', 'none')
        is_security_relevant: Whether the action is security-relevant
        top_actions: Top-k predicted actions as (label, confidence) tuples
    """

    action_label: str
    action_index: int
    confidence: float
    security_risk: str
    is_security_relevant: bool
    top_actions: list[tuple[str, float]]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "action_label": self.action_label,
            "action_index": self.action_index,
            "confidence": self.confidence,
            "security_risk": self.security_risk,
            "is_security_relevant": self.is_security_relevant,
            "top_actions": [
                {"label": label, "confidence": conf} for label, conf in self.top_actions
            ],
        }


# ==============================================================================
# Model Loading and Inference
# ==============================================================================


def _map_checkpoint_keys(state_dict: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    """Map pyskl checkpoint keys to our model keys.

    Pyskl checkpoints use:
        backbone.data_bn.* -> data_bn.*
        backbone.gcn.{i}.gcn.* -> gcn.{i}.gcn.*
        backbone.gcn.{i}.tcn.* -> gcn.{i}.tcn.*
        backbone.gcn.{i}.residual.* -> gcn.{i}.residual.*
        cls_head.fc_cls.* -> fc.*
    """
    mapped = {}
    for key, value in state_dict.items():
        new_key = key
        if new_key.startswith("backbone."):
            new_key = new_key[len("backbone.") :]
        if new_key.startswith("cls_head.fc_cls."):
            new_key = new_key.replace("cls_head.fc_cls.", "fc.")
        elif new_key.startswith("cls_head."):
            new_key = new_key[len("cls_head.") :]
        mapped[new_key] = value
    return mapped


async def load_stgcn_model(model_path: str) -> dict[str, Any]:
    """Load an ST-GCN++ model from a pyskl checkpoint.

    Args:
        model_path: Path to the model directory containing the .pth checkpoint

    Returns:
        Dictionary containing:
            - model: The ST-GCN++ model instance
            - labels: NTU-60 action labels
            - num_classes: Number of action classes

    Raises:
        RuntimeError: If model loading fails
    """
    logger.info(f"Loading ST-GCN++ model from {model_path}")

    loop = asyncio.get_running_loop()

    def _load() -> dict[str, Any]:
        # Find checkpoint file
        model_dir = Path(model_path)
        checkpoint_path = None
        if model_dir.is_dir():
            for fpath in model_dir.iterdir():
                if fpath.suffix == ".pth":
                    checkpoint_path = str(fpath)
                    break
        elif model_dir.is_file() and model_dir.suffix == ".pth":
            checkpoint_path = model_path

        if checkpoint_path is None:
            raise RuntimeError(
                f"No .pth checkpoint found in {model_path}. "
                "Download with: curl -L -o stgcnpp_ntu60_xsub_hrnet_j.pth "
                "http://download.openmmlab.com/mmaction/pyskl/ckpt/stgcnpp/stgcnpp_ntu60_xsub_hrnet/j.pth"
            )

        logger.info(f"Loading checkpoint from {checkpoint_path}")

        # Load checkpoint
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)

        # Extract state dict
        if "state_dict" in checkpoint:
            state_dict = checkpoint["state_dict"]
        else:
            state_dict = checkpoint

        # Create model
        model = STGCNPP(num_classes=60, in_channels=3, num_person=2)

        # Map checkpoint keys
        mapped_dict = _map_checkpoint_keys(state_dict)

        # Load with strict=False to handle minor mismatches
        missing, unexpected = model.load_state_dict(mapped_dict, strict=False)
        if missing:
            logger.warning(
                f"ST-GCN++ missing keys: {missing[:5]}{'...' if len(missing) > 5 else ''}"
            )
        if unexpected:
            logger.warning(
                f"ST-GCN++ unexpected keys: {unexpected[:5]}{'...' if len(unexpected) > 5 else ''}"
            )

        # Move to GPU if available, use float32 (model is tiny)
        device = "cpu"
        if torch.cuda.is_available():
            device = "cuda"
            model = model.to(device)
            logger.info("ST-GCN++ model moved to CUDA")

        model.eval()

        logger.info(
            f"ST-GCN++ loaded: {sum(p.numel() for p in model.parameters()):,} parameters, "
            f"device={device}"
        )

        return {
            "model": model,
            "labels": NTU60_LABELS,
            "num_classes": 60,
            "device": device,
        }

    result = await loop.run_in_executor(None, _load)
    logger.info("Successfully loaded ST-GCN++ model")
    return result


async def classify_skeleton_action(
    model_dict: dict[str, Any],
    keypoints_sequence: np.ndarray,
    top_k: int = 5,
) -> SkeletonActionResult:
    """Classify action from a sequence of skeleton keypoints.

    Args:
        model_dict: Dictionary from load_stgcn_model
        keypoints_sequence: Keypoints array of shape (M, T, V, C)
            M = number of persons (1 or 2, padded with zeros)
            T = number of frames (will be resampled to 100 if needed)
            V = 17 COCO keypoints
            C = 3 (x, y, confidence)

    Returns:
        SkeletonActionResult with action classification

    Raises:
        ValueError: If keypoints have invalid shape
        RuntimeError: If inference fails
    """
    model = model_dict["model"]
    labels = model_dict["labels"]
    device = model_dict.get("device", "cpu")

    loop = asyncio.get_running_loop()

    def _classify() -> SkeletonActionResult:
        # Validate input
        if keypoints_sequence.ndim != 4:
            raise ValueError(
                f"Expected keypoints shape (M, T, V, C), got {keypoints_sequence.shape}"
            )
        M, T, V, C = keypoints_sequence.shape
        if V != 17:
            raise ValueError(f"Expected 17 COCO keypoints, got {V}")
        if C < 2:
            raise ValueError(f"Expected at least 2 channels (x, y), got {C}")

        # Pad to 3 channels if needed (add confidence=1.0)
        if C == 2:
            conf = np.ones((*keypoints_sequence.shape[:3], 1), dtype=np.float32)
            kp = np.concatenate([keypoints_sequence, conf], axis=-1)
        elif C > 3:
            kp = keypoints_sequence[..., :3]
        else:
            kp = keypoints_sequence.copy()

        # Pad persons to 2 if needed
        if M == 1:
            kp = np.concatenate([kp, np.zeros((1, T, V, 3), dtype=np.float32)], axis=0)
        elif M > 2:
            kp = kp[:2]
        M = 2

        # Resample to 100 frames (pyskl default)
        target_T = 100
        if target_T != T:
            indices = np.linspace(0, T - 1, target_T, dtype=int)
            kp = kp[:, indices]

        # Build input tensor: (1, M, T, V, C)
        x = torch.tensor(kp, dtype=torch.float32).unsqueeze(0)
        x = x.to(device)

        # Run inference
        with torch.inference_mode():
            logits = model(x)  # (1, 60)
            probs = F.softmax(logits, dim=-1).squeeze(0).cpu().numpy()

        # Get top-k predictions
        top_indices = np.argsort(probs)[::-1][:top_k]
        top_actions = [(labels[i], float(probs[i])) for i in top_indices]

        # Best prediction
        best_idx = int(top_indices[0])
        best_label = labels[best_idx]
        best_conf = float(probs[best_idx])

        # Security assessment
        security_risk = SECURITY_RISK_MAP.get(best_idx, "none")
        is_relevant = best_idx in SECURITY_RELEVANT_ACTIONS

        return SkeletonActionResult(
            action_label=best_label,
            action_index=best_idx,
            confidence=best_conf,
            security_risk=security_risk,
            is_security_relevant=is_relevant,
            top_actions=top_actions,
        )

    return await loop.run_in_executor(None, _classify)
