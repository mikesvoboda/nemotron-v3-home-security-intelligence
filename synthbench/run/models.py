"""The models `synthbench replay` can score (P5a design §3). Imports nothing from `backend`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Model:
    """One replayable model.

    `served_id` is the identity the endpoint must report before a replay trusts it: for `ai-vlm`
    (llama.cpp) the model file's stem from `/props`, for vLLM an id from `/v1/models`.
    """

    name: str
    transport: Literal["ai-vlm", "vllm"]
    served_id: str
    url_env: str
    default_url: str


MODELS: dict[str, Model] = {
    model.name: model
    for model in (
        # The product VLM (VSS spec rev 7) and the other two VSS bake-off candidates, all served by
        # the product's `ai-vlm` on port 8098, one at a time.
        Model(
            "qwen3-vl-8b",
            "ai-vlm",
            "Qwen3VL-8B-Instruct-Q4_K_M",
            "AI_VLM_URL",
            "http://127.0.0.1:8098",
        ),
        Model(
            "qwen3-vl-4b",
            "ai-vlm",
            "Qwen3VL-4B-Instruct-Q4_K_M",
            "AI_VLM_URL",
            "http://127.0.0.1:8098",
        ),
        Model(
            "nemotron-12b-vl",
            "ai-vlm",
            "NVIDIA-Nemotron-Nano-12B-v2-VL-Q4_K_M",
            "AI_VLM_URL",
            "http://127.0.0.1:8098",
        ),
        # Comparison models under vLLM (owner, 2026-09-29).
        Model(
            "cosmos-reason2-8b",
            "vllm",
            "nvidia/Cosmos-Reason2-8B",
            "SYNTHBENCH_COSMOS_URL",
            "http://127.0.0.1:8099",
        ),
        Model(
            "flagship",
            "vllm",
            "claude-flagship",
            "SYNTHBENCH_FLAGSHIP_URL",
            "http://127.0.0.1:8000",
        ),
    )
}
