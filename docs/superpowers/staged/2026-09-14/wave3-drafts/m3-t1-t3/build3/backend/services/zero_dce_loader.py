"""Zero-DCE++ low-light image enhancement loader.

Zero-DCE++ (Zero-Reference Deep Curve Estimation++) learns brightness curve
adjustments to enhance low-light images without paired training data.

Architecture: 7 depthwise separable conv layers (~10K parameters, ~40KB weights)
Speed: ~1000 FPS on GPU, essentially zero overhead
Input: RGB image tensor [B, 3, H, W] normalized to [0, 1]
Output: Enhanced RGB image tensor [B, 3, H, W]

The model predicts per-pixel curve parameters (not a direct mapping). The curve
is applied iteratively (8 iterations) to progressively brighten dark regions.

Reference: https://github.com/Li-Chongyi/Zero-DCE_extension
"""

from __future__ import annotations

import asyncio
from typing import Any

import torch
from PIL import Image
from torch import nn
from torch.nn import functional as F

from backend.core.logging import get_logger

logger = get_logger(__name__)

# Brightness threshold below which enhancement is applied (0-1 scale).
# Images with mean luminance below this are considered low-light.
LOW_LIGHT_BRIGHTNESS_THRESHOLD = 0.35

# Scale factor for the model (1 = process at full resolution)
SCALE_FACTOR = 1


class _DepthwiseSeparableConv(nn.Module):
    """Depthwise separable convolution (CSDN_Tem from Zero-DCE++)."""

    def __init__(self, in_ch: int, out_ch: int) -> None:
        super().__init__()
        self.depth_conv = nn.Conv2d(in_ch, in_ch, kernel_size=3, stride=1, padding=1, groups=in_ch)
        self.point_conv = nn.Conv2d(in_ch, out_ch, kernel_size=1, stride=1, padding=0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        result: torch.Tensor = self.point_conv(self.depth_conv(x))
        return result


class ZeroDCEPP(nn.Module):
    """Zero-DCE++ network for low-light image enhancement.

    7 depthwise separable conv layers with skip connections.
    Predicts curve parameters that are iteratively applied to brighten images.
    """

    def __init__(self, scale_factor: int = SCALE_FACTOR) -> None:
        super().__init__()
        self.relu = nn.ReLU(inplace=True)
        self.scale_factor = scale_factor
        if scale_factor != 1:
            self.upsample = nn.UpsamplingBilinear2d(scale_factor=scale_factor)
        n = 32
        self.e_conv1 = _DepthwiseSeparableConv(3, n)
        self.e_conv2 = _DepthwiseSeparableConv(n, n)
        self.e_conv3 = _DepthwiseSeparableConv(n, n)
        self.e_conv4 = _DepthwiseSeparableConv(n, n)
        self.e_conv5 = _DepthwiseSeparableConv(n * 2, n)
        self.e_conv6 = _DepthwiseSeparableConv(n * 2, n)
        self.e_conv7 = _DepthwiseSeparableConv(n * 2, 3)

    def _apply_curve(self, x: torch.Tensor, x_r: torch.Tensor) -> torch.Tensor:
        """Apply learned curve parameters iteratively (8 iterations)."""
        for _ in range(8):
            x = x + x_r * (torch.pow(x, 2) - x)
        return x

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.scale_factor != 1:
            x_down = F.interpolate(x, scale_factor=1 / self.scale_factor, mode="bilinear")
        else:
            x_down = x

        x1 = self.relu(self.e_conv1(x_down))
        x2 = self.relu(self.e_conv2(x1))
        x3 = self.relu(self.e_conv3(x2))
        x4 = self.relu(self.e_conv4(x3))
        x5 = self.relu(self.e_conv5(torch.cat([x3, x4], 1)))
        x6 = self.relu(self.e_conv6(torch.cat([x2, x5], 1)))
        x_r = torch.tanh(self.e_conv7(torch.cat([x1, x6], 1)))

        if self.scale_factor != 1:
            x_r = self.upsample(x_r)

        return self._apply_curve(x, x_r)


async def load_zero_dce_model(model_path: str) -> dict[str, Any]:
    """Load Zero-DCE++ model from pretrained weights.

    Args:
        model_path: Path to directory containing Epoch99.pth

    Returns:
        Dictionary with 'model' key containing the loaded ZeroDCEPP model

    Raises:
        RuntimeError: If model loading fails or weights not found
    """
    from pathlib import Path

    weights_path = Path(model_path) / "Epoch99.pth"
    if not weights_path.exists():
        raise RuntimeError(
            f"Zero-DCE++ weights not found at {weights_path}. "
            f"Download from: https://github.com/Li-Chongyi/Zero-DCE_extension"
        )

    logger.info("Loading Zero-DCE++ low-light enhancement model from %s", weights_path)

    loop = asyncio.get_running_loop()

    def _load() -> dict[str, Any]:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = ZeroDCEPP(scale_factor=SCALE_FACTOR)
        state_dict = torch.load(str(weights_path), map_location=device, weights_only=True)
        model.load_state_dict(state_dict)
        model = model.to(device)
        model.eval()
        logger.info(
            "Zero-DCE++ loaded on %s (%.1f KB parameters)",
            device,
            sum(p.numel() * p.element_size() for p in model.parameters()) / 1024,
        )
        return {"model": model, "device": device}

    result = await loop.run_in_executor(None, _load)
    logger.info("Successfully loaded Zero-DCE++ model")
    return result


def _compute_mean_brightness(image: Image.Image) -> float:
    """Compute mean luminance of an image (0-1 scale).

    Uses ITU-R BT.601 luminance: 0.299*R + 0.587*G + 0.114*B

    Args:
        image: PIL Image (RGB)

    Returns:
        Mean brightness value between 0 and 1
    """
    import numpy as np

    img = image.convert("RGB") if image.mode != "RGB" else image
    arr = np.array(img, dtype=np.float32)
    luminance = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    return float(luminance.mean() / 255.0)


def should_enhance(image: Image.Image, threshold: float = LOW_LIGHT_BRIGHTNESS_THRESHOLD) -> bool:
    """Check if an image should be enhanced (is low-light).

    Args:
        image: PIL Image to check
        threshold: Brightness threshold below which enhancement is applied

    Returns:
        True if the image is low-light and should be enhanced
    """
    return _compute_mean_brightness(image) < threshold


async def enhance_image(model_data: dict[str, Any], image: Image.Image) -> Image.Image:
    """Enhance a low-light image using Zero-DCE++.

    Args:
        model_data: Dictionary from load_zero_dce_model with 'model' and 'device'
        image: PIL Image to enhance

    Returns:
        Enhanced PIL Image (or original if enhancement fails)
    """
    import numpy as np
    from torchvision import transforms

    model = model_data["model"]
    device = model_data["device"]

    loop = asyncio.get_running_loop()

    def _enhance() -> Image.Image:
        rgb_image = image.convert("RGB") if image.mode != "RGB" else image
        original_size = rgb_image.size  # (W, H)

        # Convert to tensor [0, 1]
        to_tensor = transforms.ToTensor()
        img_tensor = to_tensor(rgb_image).unsqueeze(0).to(device)

        with torch.inference_mode():
            enhanced_tensor = model(img_tensor)

        # Clamp to valid range and convert back to PIL
        enhanced_tensor = enhanced_tensor.clamp(0, 1).squeeze(0).cpu()
        enhanced_np = (enhanced_tensor.permute(1, 2, 0).numpy() * 255).astype(np.uint8)
        enhanced_pil = Image.fromarray(enhanced_np)

        # Resize back if dimensions changed due to scale_factor padding
        if enhanced_pil.size != original_size:
            enhanced_pil = enhanced_pil.resize(original_size, Image.Resampling.BILINEAR)

        return enhanced_pil

    return await loop.run_in_executor(None, _enhance)
