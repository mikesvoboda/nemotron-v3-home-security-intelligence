"""Florence-2 model loader for vision-language queries.

This module provides the async loader function for Florence-2-large model,
which is used for comprehensive attribute extraction from security camera feeds.

Florence-2-large is a vision-language model that supports:
- Object attribute extraction (vehicle color/type, person clothing)
- Scene analysis and description
- Visual question answering

VRAM Budget: ~1.2GB (4-bit quantized)
"""

from __future__ import annotations

import asyncio
from typing import Any

from backend.core.logging import get_logger

logger = get_logger(__name__)


async def load_florence_model(model_path: str) -> Any:
    """Load Florence-2 model from HuggingFace.

    This function loads the Florence-2-large model using the transformers library.
    The model is loaded with 4-bit quantization to fit within VRAM budget.

    Args:
        model_path: HuggingFace model path (e.g., "microsoft/Florence-2-large")

    Returns:
        Tuple of (model, processor) for inference

    Raises:
        ImportError: If transformers or torch is not installed
        RuntimeError: If model loading fails
    """
    try:
        # Import transformers and torch for Florence-2
        import torch
        from transformers import AutoModelForCausalLM, AutoProcessor

        logger.info(f"Loading Florence-2 model from {model_path}")

        # Run model loading in thread pool to avoid blocking
        loop = asyncio.get_event_loop()

        def _load_model() -> tuple[Any, Any]:
            """Load model and processor synchronously."""
            # Load processor
            processor = AutoProcessor.from_pretrained(
                model_path,
                trust_remote_code=True,
            )

            # Determine device and dtype
            if torch.cuda.is_available():
                device = "cuda"
                # Use float16 for GPU inference
                dtype = torch.float16
            else:
                device = "cpu"
                dtype = torch.float32

            # Load model with appropriate settings
            # Use eager attention implementation to avoid SDPA compatibility issues
            # with Florence-2's custom model code
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=dtype,
                trust_remote_code=True,
                attn_implementation="eager",
            )

            # Move to device
            model = model.to(device)  # type: ignore[arg-type]
            model.eval()

            return model, processor

        model, processor = await loop.run_in_executor(None, _load_model)

        logger.info(f"Successfully loaded Florence-2 model from {model_path}")
        return (model, processor)

    except ImportError as e:
        logger.warning(
            "transformers or torch package not installed. "
            "Install with: pip install transformers torch"
        )
        raise ImportError(
            "Florence-2 requires transformers and torch. "
            "Install with: pip install transformers torch"
        ) from e

    except Exception as e:
        logger.error(
            "Failed to load Florence-2 model", exc_info=True, extra={"model_path": model_path}
        )
        raise RuntimeError(f"Failed to load Florence-2 model: {e}") from e
