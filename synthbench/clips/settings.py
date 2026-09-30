"""The clip settings each round records, and the weights clips render with (clips design §2.3).

H3 turbo renders on its 768p canvas at 24 fps. Its `length` snaps to a 17k+5 grid (ComfyUI
v0.37.0 object_info; trained on about 124-362 frames): 243 = 17 x 14 + 5 frames is 10.1 s, the
grid length nearest the owner's ~10 s (C7, ruling H3-R1).
"""

from __future__ import annotations

import hashlib
import json

from synthbench.contract.clip import ClipSettings
from synthbench.generate.render import MANIFEST
from synthbench.generate.weights import load_manifest

CLIP_MODEL = "minimax-h3-turbo"
CLIP_SIZE = (1344, 768)
CLIP_FPS = 24
CLIP_FRAMES = 243
MIN_CLIP_FRAMES = 240  # 10 s at 24 fps: what the clip check accepts (ruling H3-R2)
# Frozen into every clip spec after the agent's motion, as CAMERA_SUFFIX is for stills.
CLIP_SUFFIX = "Fixed security camera; the camera does not move; one continuous shot."


def model_hashes() -> dict[str, str]:
    """The weights H3 turbo renders with, by manifest path: an attempt's `models` (H3-R19)."""
    return {f.path: f.sha256 for f in load_manifest(MANIFEST) if f.model == CLIP_MODEL}


def current() -> ClipSettings:
    """The settings `clip sample` records in a new round and the gate compares."""
    pairs = sorted(model_hashes().items())
    return ClipSettings(
        frames=CLIP_FRAMES,
        fps=CLIP_FPS,
        size=CLIP_SIZE,
        weights=hashlib.sha256(json.dumps(pairs).encode()).hexdigest(),
        clip_suffix_sha256=hashlib.sha256(CLIP_SUFFIX.encode()).hexdigest(),
    )
