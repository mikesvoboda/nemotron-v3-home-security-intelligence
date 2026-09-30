"""Clip rendering helpers (clips design §4): the input fit, the clip check, the frame strip and
the H3 graphs. `clip render` (synthbench/commands/clip_render.py) drives them."""

from __future__ import annotations

import io
from pathlib import Path

import av
from PIL import Image, ImageOps

from synthbench.clips.rules import motion_text
from synthbench.clips.settings import CLIP_FRAMES, CLIP_SIZE, MIN_CLIP_FRAMES
from synthbench.contract.clip import ClipAttempt, ClipSpec
from synthbench.generate.comfy import graphs
from synthbench.generate.comfy.client import Graph

# Ruling H3-R14: the shortest length on H3's 17k+5 grid above its minimum, from the committed
# smoke image; long enough to load every H3 weight, short enough to cost little.
WARMUP_FRAMES = 22
WARMUP_IMAGE = Path(graphs.__file__).resolve().parent / "smoke_ref.png"
WARMUP_PROMPT = "A quiet driveway; leaves move a little in the wind. Fixed camera, one shot."
# Ruling H3-R18: six evenly spaced frames, 448x256 each, tiled 3 x 2.
STRIP_FRAMES = 6
STRIP_TILE = (448, 256)
STRIP_COLUMNS = 3


def fit_input(image_bytes: bytes) -> bytes:
    """An image fitted to H3's canvas: scaled to cover 1344x768, then centre-cropped (H3-R3)."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            fitted = ImageOps.fit(image.convert("RGB"), CLIP_SIZE, Image.Resampling.LANCZOS)
    except OSError as error:  # PIL.UnidentifiedImageError is an OSError
        raise ValueError(f"not an image ({type(error).__name__})") from error
    out = io.BytesIO()
    fitted.save(out, "PNG")
    return out.getvalue()


def clip_shape(data: bytes) -> tuple[tuple[int, int], int]:
    """The first video stream's (width, height) and its decoded frame count."""
    try:
        with av.open(io.BytesIO(data), "r") as container:
            stream = container.streams.video[0]
            size = (stream.codec_context.width, stream.codec_context.height)
            count = sum(1 for _ in container.decode(stream))
    except (ValueError, IndexError) as error:  # PyAV's errors are ValueErrors
        raise ValueError(f"not a video ({type(error).__name__}: {error})") from error
    return size, count


def check_clip(data: bytes) -> int:
    """The clip's frame count; ValueError unless it is 1344x768 with at least 240 frames."""
    size, count = clip_shape(data)
    if size != CLIP_SIZE or count < MIN_CLIP_FRAMES:
        width, height = CLIP_SIZE
        raise ValueError(
            f"expected a {width}x{height} clip of at least {MIN_CLIP_FRAMES} frames, got "
            f"{size[0]}x{size[1]} with {count}"
        )
    return count


def strip(data: bytes, count: int) -> bytes:
    """Six frames at evenly spaced indices, first to last, tiled 3 x 2 into one JPEG."""
    picks = {round(i * (count - 1) / (STRIP_FRAMES - 1)) for i in range(STRIP_FRAMES)}
    tiles: list[Image.Image] = []
    with av.open(io.BytesIO(data), "r") as container:
        for index, frame in enumerate(container.decode(video=0)):
            if index in picks:
                tiles.append(frame.to_image().resize(STRIP_TILE, Image.Resampling.LANCZOS))
    rows = -(-len(tiles) // STRIP_COLUMNS)
    width, height = STRIP_TILE
    sheet = Image.new("RGB", (width * STRIP_COLUMNS, height * rows))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % STRIP_COLUMNS) * width, (i // STRIP_COLUMNS) * height))
    out = io.BytesIO()
    sheet.save(out, "JPEG", quality=85)
    return out.getvalue()


def _save_as(graph: Graph, prefix: str) -> Graph:
    for node in graph.values():
        if node["class_type"] == "SaveVideo":
            node["inputs"]["filename_prefix"] = prefix
    return graph


def clip_graph(spec: ClipSpec, attempt: ClipAttempt, image: str) -> Graph:
    """The attempt's H3 turbo graph: the frozen motion and suffix, its seed, 1344x768, 243
    frames. ComfyUI also keeps a copy under comfy-out/synthbench/<version>/<clip>/."""
    width, height = CLIP_SIZE
    graph = graphs.minimax_h3_turbo_i2v(
        motion_text(spec),
        image=image,
        seed=attempt.seed,
        width=width,
        height=height,
        frames=CLIP_FRAMES,
    )
    prefix = f"synthbench/{spec.corpus_version}/{spec.event_id}/a{attempt.k}-s{attempt.seed}"
    return _save_as(graph, prefix)


def warmup_graph(image: str) -> Graph:
    width, height = CLIP_SIZE
    graph = graphs.minimax_h3_turbo_i2v(
        WARMUP_PROMPT, image=image, seed=0, width=width, height=height, frames=WARMUP_FRAMES
    )
    return _save_as(graph, "synthbench/warmup-h3")
