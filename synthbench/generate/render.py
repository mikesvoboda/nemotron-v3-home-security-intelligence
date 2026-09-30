"""Rendering beside the flagship (agent-driven design §3 step 4, §5.2): find ComfyUI, yield to
the flagship, and build the FLUX.2 [dev] graph for one attempt."""

from __future__ import annotations

import io
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Literal

import httpx
from PIL import Image

from synthbench.contract.corpus import TIER_B_RENDER_SIZE
from synthbench.contract.provenance import Attempt
from synthbench.contract.spec import Spec
from synthbench.generate.comfy.client import ComfyClient, Graph
from synthbench.generate.comfy.graphs import flux2_dev_t2i
from synthbench.generate.weights import load_manifest
from synthbench.prompt.rules import render_text
from synthbench.status import fresh_flagship

RENDER_MODEL = "flux2-dev"
MANIFEST = Path(__file__).resolve().parent / "manifests" / "p1-slate.json"
# Plan ruling P3-R9: the host reaches ComfyUI on its loopback; a sandbox reaches the host's
# loopback at host.docker.internal (docs/benchmarks/synthbench/p3-probes.md).
DEFAULT_URLS = ("http://127.0.0.1:8188", "http://host.docker.internal:8188")
YIELD_POLL_S = 5.0


class RendererUnreachable(RuntimeError):
    """No ComfyUI answered."""


def model_hashes(manifest: Path = MANIFEST) -> dict[str, str]:
    """The weights FLUX.2 [dev] renders with, by category: an attempt's `models`."""
    return {f.category: f.sha256 for f in load_manifest(manifest) if f.model == RENDER_MODEL}


def comfy_url(env: Mapping[str, str], get: Callable[..., httpx.Response] = httpx.get) -> str:
    """$SYNTHBENCH_COMFYUI_URL, else the first default whose /system_stats answers."""
    configured = env.get("SYNTHBENCH_COMFYUI_URL")
    candidates = (configured,) if configured else DEFAULT_URLS
    for url in candidates:
        try:
            if get(f"{url}/system_stats", timeout=3.0).status_code == 200:
                return url
        except httpx.HTTPError:
            continue
    raise RendererUnreachable(f"ComfyUI did not answer at {', '.join(candidates)}")


def wait_for_flagship(
    status_file: Path,
    *,
    deadline: float,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
    now: Callable[[], datetime],
) -> bool:
    """Wait, polling every 5 s, while the flagship is unhealthy or has requests waiting (§5.2).

    Returns False when the next poll would pass the deadline. Raises FlagshipUnknown when the
    status file is missing, unreadable or older than 30 s.
    """
    while True:
        status = fresh_flagship(status_file, now())
        if status.healthy and not status.waiting:
            return True
        if clock() + YIELD_POLL_S > deadline:
            return False
        sleep(YIELD_POLL_S)


def attempt_graph(spec: Spec, attempt: Attempt) -> Graph:
    """The attempt's FLUX.2 [dev] graph: the frozen text, the attempt's seed, 1280x720.

    ComfyUI also keeps its own copy under comfy-out/synthbench/<version>/<event>/, the fallback
    for a render lost before a snapshot (design §6).
    """
    width, height = TIER_B_RENDER_SIZE
    graph = flux2_dev_t2i(render_text(spec), seed=attempt.seed, width=width, height=height)
    prefix = f"synthbench/{spec.corpus_version}/{spec.event_id}/a{attempt.k}-s{attempt.seed}"
    for node in graph.values():
        if node["class_type"] == "SaveImage":
            node["inputs"]["filename_prefix"] = prefix
    return graph


def check_png(data: bytes) -> None:
    """Raise ValueError unless data is a 1280x720 PNG."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            kind, size = image.format, image.size
    except OSError as error:  # PIL.UnidentifiedImageError is an OSError
        raise ValueError(f"not an image ({type(error).__name__})") from error
    if kind != "PNG" or size != TIER_B_RENDER_SIZE:
        width, height = TIER_B_RENDER_SIZE
        raise ValueError(f"expected a {width}x{height} PNG, got {kind} {size}")


Family = Literal["flux2", "h3", "other"]
FLUX2_UNET = "flux2_dev_fp8mixed.safetensors"
H3_UNET = "minimax_h3_fl2va_pruned_int8_convrot.safetensors"


def family(graph: Graph) -> Family:
    """The model family a graph loads, by its UNETLoader (clips design §4.1, ruling H3-R15)."""
    names = {
        node.get("inputs", {}).get("unet_name")
        for node in graph.values()
        if node.get("class_type") == "UNETLoader"
    }
    if H3_UNET in names:
        return "h3"
    if FLUX2_UNET in names:
        return "flux2"
    return "other"


def last_family(client: ComfyClient) -> Family | None:
    """The family of the renderer's newest job; None when it has run nothing yet."""
    graph = client.last_prompt()
    return None if graph is None else family(graph)


FREE_POLL_S = 1.0
FREE_WAIT_S = 30.0  # the clips probe: /free answers at once; the memory returns within ~5 s
FLUX2_NEED_GIB = 60.0  # FLUX.2's 56.2 GiB peak plus --reserve-vram 4 (the renderer precheck)


def wait_for_free(
    client: ComfyClient,
    need_gib: float,
    *,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
    timeout_s: float = FREE_WAIT_S,
) -> float:
    """Poll the GPU's free memory every second until it reaches need_gib or timeout_s passes;
    returns the last reading. ComfyUI's /free answers before it releases (ruling H3-R16)."""
    deadline = clock() + timeout_s
    while True:
        free = client.free_vram_gib()
        if free >= need_gib or clock() >= deadline:
            return free
        sleep(FREE_POLL_S)
