"""The camera stage (agent-driven design §7; parent spec §3.4).

A 1280x720 render becomes a 1920x1080 JPEG like a Foscam still: a Lanczos resize, per-camera
barrel distortion, IR-night grey and bloom, sensor noise, the timestamp overlay, and JPEG. The
same render, camera, lighting, overlay text, seed and parameters give the same bytes.

The parameters are committed defaults (default-v1.json) until `camera calibrate` fits them to
the owner's footage (parent D13; plan ruling P3-R3). Each still records the set's id.
"""

from __future__ import annotations

import io
import math
import random
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw, ImageFont
from pydantic import Field

from synthbench.contract.common import ContractModel

DEFAULT_PARAMS = Path(__file__).resolve().parent / "default-v1.json"
_LUMA = np.array([0.299, 0.587, 0.114], dtype=np.float32)

Pixels = NDArray[np.float32]


class Bloom(ContractModel):
    threshold: float = Field(ge=0, le=255)
    radius: float = Field(gt=0)
    strength: float = Field(ge=0)


class Overlay(ContractModel):
    font_px: int = Field(ge=8)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    stroke_px: int = Field(ge=0)


class CameraParams(ContractModel):
    id: str
    size: tuple[int, int]
    jpeg_quality: int = Field(ge=1, le=95)
    distortion: dict[str, float]  # barrel k per camera type (taxonomy camera ids)
    noise_sigma: dict[str, float]  # sensor noise per lighting id, on the 0-255 scale
    ir_lighting: tuple[str, ...]  # lighting ids the camera sees in infrared
    bloom: Bloom
    overlay: Overlay


def load_params(path: Path = DEFAULT_PARAMS) -> CameraParams:
    return CameraParams.model_validate_json(path.read_text(encoding="utf-8"))


def overlay_time(scene_time: str, weather: str, seed: int) -> str:
    """The timestamp the stage draws (plan ruling P3-R16): the spec's HH:MM on a seeded 2026
    date, with seeded seconds; snow falls in December to February."""
    rng = random.Random(seed)  # noqa: S311  # reproducible, not security
    month = rng.choice((12, 1, 2)) if weather == "snow" else rng.randint(1, 12)
    day = rng.randint(1, 28)
    return f"2026-{month:02d}-{day:02d} {scene_time}:{rng.randrange(60):02d}"


def distort(pixels: Pixels, k: float) -> Pixels:
    """Barrel distortion: the corners stay put and the centre is magnified by 1 + k."""
    if k == 0:
        return pixels
    height, width = pixels.shape[:2]
    ys, xs = np.indices((height, width), dtype=np.float32)
    cx, cy = (width - 1) / 2, (height - 1) / 2
    norm = math.hypot(cx, cy)
    dx, dy = (xs - cx) / norm, (ys - cy) / norm
    scale = (1 + k * (dx * dx + dy * dy)) / (1 + k)
    map_x = (cx + dx * scale * norm).astype(np.float32)
    map_y = (cy + dy * scale * norm).astype(np.float32)
    warped = cv2.remap(
        pixels, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
    )
    return np.asarray(warped, dtype=np.float32)


def infrared(pixels: Pixels, bloom: Bloom) -> Pixels:
    """IR night: grey from luma, with a glow around the brightest areas."""
    luma = pixels @ _LUMA
    bright = np.clip(luma - bloom.threshold, 0, None)
    glow = np.asarray(cv2.GaussianBlur(bright, (0, 0), bloom.radius), dtype=np.float32)
    luma = np.clip(luma + bloom.strength * glow, 0, 255)
    return np.repeat(luma[..., None], 3, axis=2).astype(np.float32)


def render_still(
    png: bytes, *, camera: str, lighting: str, overlay_text: str, seed: int, params: CameraParams
) -> bytes:
    """The Foscam-style JPEG still for one render."""
    if camera not in params.distortion or lighting not in params.noise_sigma:
        raise ValueError(
            f"camera parameters {params.id} cover no camera {camera!r} or lighting {lighting!r}"
        )
    with Image.open(io.BytesIO(png)) as source:
        image = source.convert("RGB").resize(params.size, Image.Resampling.LANCZOS)
    pixels = distort(np.asarray(image, dtype=np.float32), params.distortion[camera])
    infrared_night = lighting in params.ir_lighting
    if infrared_night:
        pixels = infrared(pixels, params.bloom)
    height, width = pixels.shape[:2]
    channels = 1 if infrared_night else 3  # one noise plane keeps IR grey
    noise = np.random.default_rng(seed).normal(
        0.0, params.noise_sigma[lighting], (height, width, channels)
    )
    still = Image.fromarray(np.clip(pixels + noise, 0, 255).astype(np.uint8))
    if overlay_text:
        _draw_overlay(still, overlay_text, params.overlay)
    out = io.BytesIO()
    still.save(out, "JPEG", quality=params.jpeg_quality, subsampling="4:2:0")
    return out.getvalue()


def _draw_overlay(image: Image.Image, text: str, overlay: Overlay) -> None:
    """White text with a dark outline in the top-left corner, as Foscam draws it [A]."""
    font = ImageFont.load_default(size=overlay.font_px)
    ImageDraw.Draw(image).text(
        (overlay.x, overlay.y),
        text,
        font=font,
        fill=(255, 255, 255),
        stroke_width=overlay.stroke_px,
        stroke_fill=(0, 0, 0),
    )
