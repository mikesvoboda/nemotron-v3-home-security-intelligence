"""OSNet-x0.25 Person Re-Identification Model.

This module provides the PersonReID class for generating person embeddings
that can be used to track individuals across cameras and time.

Features:
- Generates 512-dimensional normalized embeddings
- Cosine similarity computation for person matching
- Configurable matching threshold
- Embedding hash for quick lookup
- Standalone OSNet architecture (no torchreid dependency)

Reference:
- Model: OSNet-x0.25
- Paper: Omni-Scale Feature Learning for Person Re-Identification (ICCV 2019)
- Authors: Zhou et al.

VRAM Usage: ~100MB
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.nn import functional as F

logger = logging.getLogger(__name__)

# OSNet-x0.25 input dimensions
OSNET_INPUT_HEIGHT = 256
OSNET_INPUT_WIDTH = 128

# Embedding dimension for OSNet-x0.25
EMBEDDING_DIMENSION = 512

# ImageNet normalization constants
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

# Default similarity threshold for same-person matching
DEFAULT_SIMILARITY_THRESHOLD = 0.7


# =============================================================================
# OSNet Architecture Components
# Adapted from torchreid: https://github.com/KaiyangZhou/deep-person-reid
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
        x = self.conv(x)
        x = self.bn(x)
        return self.relu(x)


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
        x = self.conv(x)
        x = self.bn(x)
        return self.relu(x)


class Conv1x1Linear(nn.Module):
    """1x1 convolution + bn (w/o non-linearity)."""

    def __init__(self, in_channels: int, out_channels: int, stride: int = 1):
        super().__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, 1, stride=stride, padding=0, bias=False)
        self.bn = nn.BatchNorm2d(out_channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.conv(x)
        return self.bn(x)


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
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.bn(x)
        return self.relu(x)


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
            in_channels,
            in_channels // reduction,
            kernel_size=1,
            bias=True,
            padding=0,
        )
        self.norm1: nn.LayerNorm | None = None
        if layer_norm:
            self.norm1 = nn.LayerNorm((in_channels // reduction, 1, 1))
        self.relu = nn.ReLU(inplace=True)
        self.fc2 = nn.Conv2d(
            in_channels // reduction,
            num_gates,
            kernel_size=1,
            bias=True,
            padding=0,
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
    """Omni-scale feature learning block."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        bottleneck_reduction: int = 4,
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
        return F.relu(out)


class OSNet(nn.Module):
    """Omni-Scale Network for Person Re-Identification.

    Reference:
        - Zhou et al. Omni-Scale Feature Learning for Person Re-Identification.
          ICCV, 2019.
        - Zhou et al. Learning Generalisable Omni-Scale Representations
          for Person Re-Identification. TPAMI, 2021.
    """

    def __init__(
        self,
        num_classes: int,
        blocks: list[type[OSBlock]],
        layers: list[int],
        channels: list[int],
        feature_dim: int = 512,
    ):
        super().__init__()
        num_blocks = len(blocks)
        assert num_blocks == len(layers)
        assert num_blocks == len(channels) - 1
        self.feature_dim = feature_dim

        # Convolutional backbone
        self.conv1 = ConvLayer(3, channels[0], 7, stride=2, padding=3)
        self.maxpool = nn.MaxPool2d(3, stride=2, padding=1)
        self.conv2 = self._make_layer(blocks[0], layers[0], channels[0], channels[1], True)
        self.conv3 = self._make_layer(blocks[1], layers[1], channels[1], channels[2], True)
        self.conv4 = self._make_layer(blocks[2], layers[2], channels[2], channels[3], False)
        self.conv5 = Conv1x1(channels[3], channels[3])
        self.global_avgpool = nn.AdaptiveAvgPool2d(1)

        # Fully connected layer for feature extraction
        self.fc = self._construct_fc_layer(self.feature_dim, channels[3])

        # Identity classification layer (used during training only)
        self.classifier = nn.Linear(self.feature_dim, num_classes)

        self._init_params()

    def _make_layer(
        self,
        block: type[OSBlock],
        layer: int,
        in_channels: int,
        out_channels: int,
        reduce_spatial_size: bool,
    ) -> nn.Sequential:
        layers: list[nn.Module] = []
        layers.append(block(in_channels, out_channels))
        for _ in range(1, layer):
            layers.append(block(out_channels, out_channels))

        if reduce_spatial_size:
            layers.append(
                nn.Sequential(Conv1x1(out_channels, out_channels), nn.AvgPool2d(2, stride=2))
            )

        return nn.Sequential(*layers)

    def _construct_fc_layer(self, fc_dims: int, input_dim: int) -> nn.Sequential:
        layers: list[nn.Module] = [
            nn.Linear(input_dim, fc_dims),
            nn.BatchNorm1d(fc_dims),
            nn.ReLU(inplace=True),
        ]
        return nn.Sequential(*layers)

    def _init_params(self) -> None:
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="relu")
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.BatchNorm2d | nn.BatchNorm1d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, 0, 0.01)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)

    def featuremaps(self, x: torch.Tensor) -> torch.Tensor:
        """Extract feature maps from backbone."""
        x = self.conv1(x)
        x = self.maxpool(x)
        x = self.conv2(x)
        x = self.conv3(x)
        x = self.conv4(x)
        return self.conv5(x)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass returns embeddings (not logits) for inference."""
        x = self.featuremaps(x)
        v = self.global_avgpool(x)
        v = v.view(v.size(0), -1)
        if self.fc is not None:
            v = self.fc(v)
        # During inference, return the feature embedding
        if not self.training:
            return v
        # During training, return classifier logits
        return self.classifier(v)


def create_osnet_x0_25(num_classes: int = 1) -> OSNet:
    """Create OSNet-x0.25 architecture (very tiny, width x0.25).

    Args:
        num_classes: Number of output classes. Use 1 for feature extraction.

    Returns:
        OSNet model configured for x0.25 width.
    """
    return OSNet(
        num_classes=num_classes,
        blocks=[OSBlock, OSBlock, OSBlock],
        layers=[2, 2, 2],
        channels=[16, 64, 96, 128],
        feature_dim=EMBEDDING_DIMENSION,
    )


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ReIDResult:
    """Result from person re-identification embedding extraction.

    Attributes:
        embedding: 512-dimensional normalized embedding vector
        embedding_hash: First 16 characters of SHA-256 hash for quick lookup
    """

    embedding: list[float]
    embedding_hash: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "embedding": self.embedding,
            "embedding_hash": self.embedding_hash,
        }


# =============================================================================
# PersonReID Wrapper
# =============================================================================


class PersonReID:
    """OSNet-x0.25 person re-identification model wrapper.

    This model generates 512-dimensional embeddings for person crops that can
    be used to track individuals across cameras and time. Embeddings are
    normalized to unit length for cosine similarity computation.

    The model is optimized for small VRAM footprint (~100MB) while maintaining
    good re-identification accuracy.

    Example usage:
        >>> reid = PersonReID("/models/osnet-reid")
        >>> reid.load_model()
        >>> result = reid.extract_embedding(person_crop_image)
        >>> print(f"Embedding hash: {result.embedding_hash}")

        # Compare two persons
        >>> sim = reid.compute_similarity(emb1, emb2)
        >>> is_same = reid.is_same_person(emb1, emb2, threshold=0.7)
    """

    def __init__(self, model_path: str | None = None, device: str = "cuda:0"):
        """Initialize person re-identification model.

        Args:
            model_path: Path to OSNet model weights file (.pth) or directory.
                       If None, will attempt to use torchreid pretrained weights.
            device: Device to run inference on (default: "cuda:0")
        """
        self.model_path = model_path
        self.device = device
        self.model: Any = None
        self._transform: Any = None

        logger.info(f"Initializing PersonReID from {self.model_path or 'pretrained'}")

    def load_model(self) -> PersonReID:
        """Load the OSNet-x0.25 model into memory.

        Attempts to load using torchreid library first, then falls back to
        direct weight loading with standalone OSNet architecture.

        Returns:
            Self for method chaining.

        Raises:
            ImportError: If neither torchreid nor weights file is available.
            FileNotFoundError: If specified model_path doesn't exist.
        """
        from torchvision import transforms

        logger.info("Loading OSNet-x0.25 model for person re-identification...")

        # Try to use torchreid if available
        try:
            self._load_with_torchreid()
        except ImportError:
            logger.info("torchreid not available, using standalone OSNet architecture")
            self._load_direct_weights()

        # Move to device
        if "cuda" in self.device and torch.cuda.is_available():
            self.model = self.model.to(self.device)
            # Use half precision for efficiency
            self.model = self.model.half()
            logger.info(f"PersonReID loaded on {self.device} with fp16")
        else:
            self.device = "cpu"
            logger.info("PersonReID using CPU")

        self.model.eval()

        # Create preprocessing transform
        self._transform = transforms.Compose(
            [
                transforms.Resize((OSNET_INPUT_HEIGHT, OSNET_INPUT_WIDTH)),
                transforms.ToTensor(),
                transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
            ]
        )

        logger.info("PersonReID loaded successfully")
        return self

    def _load_with_torchreid(self) -> None:
        """Load model using torchreid library."""
        import torchreid

        # Build model architecture
        self.model = torchreid.models.build_model(
            name="osnet_x0_25",
            num_classes=1,  # Not used for feature extraction
            pretrained=self.model_path is None,
        )

        # Load custom weights if provided
        if self.model_path:
            torchreid.utils.load_pretrained_weights(self.model, self.model_path)
            logger.info(f"Loaded weights from {self.model_path}")
        else:
            logger.info("Using pretrained torchreid weights")

    def _load_direct_weights(self) -> None:
        """Load model weights directly using standalone OSNet architecture.

        This method creates the OSNet-x0.25 architecture and loads weights
        from the specified file without requiring torchreid.
        """
        if not self.model_path:
            raise ImportError(
                "torchreid not available and no model_path specified. "
                "Install torchreid or provide a weights file path."
            )

        logger.info("Creating standalone OSNet-x0.25 architecture...")

        # Create the model architecture
        self.model = create_osnet_x0_25(num_classes=1)

        # Load weights from file
        logger.info(f"Loading weights from {self.model_path}")
        state_dict = torch.load(self.model_path, map_location="cpu", weights_only=True)

        # Handle potential key mismatches (e.g., 'module.' prefix from DataParallel)
        if any(k.startswith("module.") for k in state_dict):
            state_dict = {k.replace("module.", ""): v for k, v in state_dict.items()}

        # Load weights with strict=False to handle classifier layer mismatch
        # (pretrained model may have different num_classes)
        missing, unexpected = self.model.load_state_dict(state_dict, strict=False)

        if missing:
            # Filter out classifier-related keys (expected to be missing)
            missing_important = [k for k in missing if "classifier" not in k]
            if missing_important:
                logger.warning(f"Missing keys in state_dict: {missing_important}")
            else:
                logger.debug(f"Missing classifier keys (expected): {missing}")

        if unexpected:
            logger.debug(f"Unexpected keys in state_dict (ignored): {unexpected}")

        logger.info("OSNet-x0.25 weights loaded successfully")

    def _preprocess(self, image: Image.Image | np.ndarray) -> torch.Tensor:
        """Preprocess image for model input.

        Args:
            image: PIL Image or numpy array of person crop.

        Returns:
            Preprocessed tensor ready for model input.
        """
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)

        # Ensure RGB mode
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Apply transforms
        img_tensor: torch.Tensor = self._transform(image)

        # Add batch dimension and move to device with correct dtype
        model_dtype = next(self.model.parameters()).dtype
        return img_tensor.unsqueeze(0).to(self.device, model_dtype)

    def extract_embedding(self, person_crop: Image.Image | np.ndarray) -> ReIDResult:
        """Extract 512-dimensional embedding for a person crop.

        The embedding is normalized to unit length for cosine similarity
        computation. A hash is also generated for quick lookup.

        Args:
            person_crop: PIL Image or numpy array of the person crop.
                        Should be the bounding box region containing the person.

        Returns:
            ReIDResult containing the embedding and hash.

        Raises:
            RuntimeError: If model is not loaded.
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        img_tensor = self._preprocess(person_crop)

        with torch.inference_mode():
            # Extract features
            embedding = self.model(img_tensor)

            # Handle different output formats
            if isinstance(embedding, tuple):
                # Some models return (global_feat, local_feat)
                embedding = embedding[0]

            # Move to CPU and convert to numpy
            embedding = embedding.cpu().float().numpy().flatten()

        # L2 normalize the embedding
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        # Validate embedding dimension
        if len(embedding) != EMBEDDING_DIMENSION:
            logger.warning(
                f"Unexpected embedding dimension: {len(embedding)}, expected {EMBEDDING_DIMENSION}"
            )

        # Create hash for quick lookup
        embedding_hash = hashlib.sha256(embedding.tobytes()).hexdigest()[:16]

        return ReIDResult(
            embedding=embedding.tolist(),
            embedding_hash=embedding_hash,
        )

    @staticmethod
    def compute_similarity(emb1: list[float], emb2: list[float]) -> float:
        """Compute cosine similarity between two embeddings.

        Since embeddings are already L2 normalized, cosine similarity
        is simply the dot product.

        Args:
            emb1: First embedding vector (512-dim).
            emb2: Second embedding vector (512-dim).

        Returns:
            Cosine similarity in range [-1, 1]. Higher values indicate
            more similar embeddings.
        """
        a = np.array(emb1)
        b = np.array(emb2)

        # Embeddings should already be normalized, but normalize again
        # for robustness
        a_norm = np.linalg.norm(a)
        b_norm = np.linalg.norm(b)

        if a_norm == 0 or b_norm == 0:
            return 0.0

        return float(np.dot(a, b) / (a_norm * b_norm))

    @staticmethod
    def is_same_person(
        emb1: list[float],
        emb2: list[float],
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> bool:
        """Determine if two embeddings are likely the same person.

        Args:
            emb1: First embedding vector (512-dim).
            emb2: Second embedding vector (512-dim).
            threshold: Similarity threshold for matching (default: 0.7).
                      Higher threshold = stricter matching.

        Returns:
            True if similarity exceeds threshold, indicating likely same person.
        """
        similarity = PersonReID.compute_similarity(emb1, emb2)
        return similarity > threshold

    def unload(self) -> None:
        """Unload the model from memory.

        Useful for freeing VRAM when the model is no longer needed.
        """
        if self.model is not None:
            del self.model
            self.model = None

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        logger.info("PersonReID model unloaded")


def load_person_reid(model_path: str | None = None) -> PersonReID:
    """Factory function for model registry.

    Creates and loads a PersonReID model. This function is intended
    to be used with the OnDemandModelManager.

    Args:
        model_path: Optional path to model weights.

    Returns:
        Loaded PersonReID model instance.
    """
    reid = PersonReID(model_path)
    reid.load_model()
    return reid
