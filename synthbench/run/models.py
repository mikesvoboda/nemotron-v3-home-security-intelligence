"""The models `synthbench replay` can score (P5a design §3). Imports nothing from `backend`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class Model:
    """One replayable model.

    `served_id` is the identity the endpoint must report before a replay trusts it: for `ai-vlm`
    (llama.cpp) the model file's stem from `/props`, for vLLM an id from `/v1/models`.
    `request_extra` holds top-level fields merged into (and overriding) every chat-completions
    body the replay sends a vLLM model: the served model's own switches and token budget, never
    the shipped prompt or schema. `read_timeout` (seconds) replaces the shipped per-attempt
    `ai_vlm_read_timeout` when set. `run.json` records both.
    """

    name: str
    transport: Literal["ai-vlm", "vllm"]
    served_id: str
    url_env: str
    default_url: str
    request_extra: Mapping[str, Any] = field(default_factory=dict, hash=False)
    read_timeout: float | None = None


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
        # Comparison models under vLLM (owner, 2026-09-29). Cosmos does not think, but one
        # evidence string alone ran past the shipped 1024 tokens (Task 1 Step 8: finish_reason
        # length); at 4096 the shipped 25 s read timeout expired first. With 4096 tokens and a
        # longer timeout it answered schema-valid in 1326 tokens, in about 17 s.
        Model(
            "cosmos-reason2-8b",
            "vllm",
            "nvidia/Cosmos-Reason2-8B",
            "SYNTHBENCH_COSMOS_URL",
            "http://127.0.0.1:8099",
            request_extra={"max_tokens": 4096},
            read_timeout=120.0,
        ),
        # The flagship thinks before it answers, and spent the shipped 1024-token budget thinking
        # (Task 1 Step 7: empty content, finish_reason length); with thinking off it answered
        # schema-valid in 187 tokens. It is measured in its non-thinking mode.
        Model(
            "flagship",
            "vllm",
            "claude-flagship",
            "SYNTHBENCH_FLAGSHIP_URL",
            "http://127.0.0.1:8000",
            request_extra={"chat_template_kwargs": {"enable_thinking": False}},
        ),
    )
}
