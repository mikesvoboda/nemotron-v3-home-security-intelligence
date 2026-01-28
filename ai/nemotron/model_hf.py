"""Nemotron LLM Server using HuggingFace Transformers with BitsAndBytes Quantization.

HTTP server wrapping Nemotron LLM models via HuggingFace Transformers.
Supports BitsAndBytes 4-bit and 8-bit quantization for efficient GPU memory usage.

This is an alternative to the llama.cpp-based server (Dockerfile) that:
- Uses native HuggingFace Transformers format (not GGUF)
- Supports BitsAndBytes 4-bit quantization (NEM-3810)
- Supports FlashAttention-2 for faster inference (NEM-3811)
- Provides OpenAI-compatible API endpoints

Environment Variables:
    NEMOTRON_MODEL_PATH: HuggingFace model path or name
    NEMOTRON_QUANTIZATION: Quantization mode ("4bit", "8bit", "none")
    NEMOTRON_4BIT_QUANT_TYPE: 4-bit type ("nf4", "fp4")
    NEMOTRON_4BIT_DOUBLE_QUANT: Enable double quantization ("true", "false")
    NEMOTRON_COMPUTE_DTYPE: Compute dtype ("float16", "bfloat16")
    NEMOTRON_USE_FLASH_ATTENTION: Enable FlashAttention-2 ("true", "false")
    NEMOTRON_MAX_NEW_TOKENS: Maximum tokens to generate (default: 1536)
    NEMOTRON_USE_COMPILE: Enable torch.compile ("true", "false")
    PORT: Server port (default: 8091)
    HOST: Server host (default: 0.0.0.0)

Port: 8091 (same as llama.cpp server)
Expected VRAM with 4-bit quantization:
    - 30B model: ~17-18 GB (down from ~60 GB at fp16)
    - 4B model: ~3 GB (down from ~8 GB at fp16)

References:
    - NEM-3810: BitsAndBytes 4-bit quantization
    - NEM-3811: FlashAttention-2 integration
    - https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field

# Add parent directory to path for shared utilities
_ai_dir = Path(__file__).parent.parent
if str(_ai_dir) not in sys.path:
    sys.path.insert(0, str(_ai_dir))

from flash_attention_config import (
    FlashAttentionSettings,
    get_attention_implementation,
    is_flash_attention_available,
    log_attention_info,
)
from quantization_config import (
    QuantizationSettings,
    get_memory_estimate,
    get_quantization_config,
    log_memory_info,
)
from torch_optimizations import compile_model, is_compile_supported

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================
INFERENCE_REQUESTS_TOTAL = Counter(
    "nemotron_hf_inference_requests_total",
    "Total number of inference requests",
    ["endpoint", "status"],
)

INFERENCE_LATENCY_SECONDS = Histogram(
    "nemotron_hf_inference_latency_seconds",
    "Inference latency in seconds",
    ["endpoint"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

TOKENS_GENERATED = Counter(
    "nemotron_hf_tokens_generated_total",
    "Total number of tokens generated",
)

MODEL_LOADED = Gauge(
    "nemotron_hf_model_loaded",
    "Whether the model is loaded (1) or not (0)",
)

GPU_MEMORY_USED_GB = Gauge(
    "nemotron_hf_gpu_memory_used_gb",
    "GPU memory used in GB",
)

QUANTIZATION_MODE = Gauge(
    "nemotron_hf_quantization_mode",
    "Quantization mode: 0=none, 4=4bit, 8=8bit",
)

FLASH_ATTENTION_ENABLED = Gauge(
    "nemotron_hf_flash_attention_enabled",
    "Whether FlashAttention-2 is enabled (1) or not (0)",
)


# =============================================================================
# Request/Response Models
# =============================================================================
class CompletionRequest(BaseModel):
    """Request format for /completion endpoint (llama.cpp compatible)."""

    prompt: str = Field(..., description="The prompt to complete")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: float = Field(default=0.95, ge=0.0, le=1.0, description="Top-p (nucleus) sampling")
    max_tokens: int = Field(default=1536, ge=1, le=8192, description="Max tokens to generate")
    stop: list[str] | None = Field(default=None, description="Stop sequences")


class CompletionResponse(BaseModel):
    """Response format for /completion endpoint."""

    content: str = Field(..., description="Generated text")
    tokens_predicted: int = Field(..., description="Number of tokens generated")
    tokens_evaluated: int = Field(..., description="Number of prompt tokens")
    generation_time_ms: float = Field(..., description="Generation time in milliseconds")
    model: str = Field(..., description="Model name")


class ChatMessage(BaseModel):
    """A single chat message."""

    role: str = Field(..., description="Message role (system, user, assistant)")
    content: str = Field(..., description="Message content")


class ChatCompletionRequest(BaseModel):
    """Request format for /v1/chat/completions (OpenAI compatible)."""

    messages: list[ChatMessage] = Field(..., description="Chat messages")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.95, ge=0.0, le=1.0)
    max_tokens: int = Field(default=1536, ge=1, le=8192)
    stream: bool = Field(default=False, description="Stream response (not yet supported)")


class ChatCompletionChoice(BaseModel):
    """A single completion choice."""

    index: int
    message: ChatMessage
    finish_reason: str


class ChatCompletionUsage(BaseModel):
    """Token usage information."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """Response format for /v1/chat/completions."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    model: str
    model_loaded: bool
    device: str
    cuda_available: bool
    vram_used_gb: float | None = None
    quantization: str
    quantization_details: dict[str, Any] | None = None
    attention_implementation: str = "unknown"
    flash_attention_available: bool = False


# =============================================================================
# Model Wrapper
# =============================================================================
class NemotronHFModel:
    """HuggingFace Transformers-based Nemotron model with quantization support.

    Supports:
    - BitsAndBytes 4-bit/8-bit quantization (NEM-3810)
    - FlashAttention-2 for faster attention computation (NEM-3811)
    - torch.compile() for optimized inference (NEM-3375)
    - ChatML format prompting
    """

    # ChatML special tokens
    IM_START = "<|im_start|>"
    IM_END = "<|im_end|>"

    def __init__(
        self,
        model_path: str,
        device: str = "cuda:0",
        quantization_settings: QuantizationSettings | None = None,
        flash_attention_settings: FlashAttentionSettings | None = None,
        use_compile: bool = True,
        max_new_tokens: int = 1536,
    ):
        """Initialize Nemotron model.

        Args:
            model_path: HuggingFace model path or local directory
            device: Target device (cuda:0, cpu)
            quantization_settings: Quantization configuration
            flash_attention_settings: FlashAttention-2 configuration
            use_compile: Whether to use torch.compile()
            max_new_tokens: Default max tokens for generation
        """
        self.model_path = model_path
        self.device = device
        self.quantization_settings = (
            quantization_settings or QuantizationSettings.from_environment()
        )
        self.flash_attention_settings = (
            flash_attention_settings or FlashAttentionSettings.from_environment()
        )
        self.use_compile = use_compile
        self.max_new_tokens = max_new_tokens

        self.model: Any = None
        self.tokenizer: Any = None
        self.is_compiled = False
        self.attention_implementation: str = "eager"
        self.model_name = (
            Path(model_path).name if "/" not in model_path else model_path.split("/")[-1]
        )

        logger.info(f"Initializing Nemotron HF model from {model_path}")
        logger.info(f"Device: {device}")
        logger.info(f"Quantization: {self.quantization_settings.mode.value}")
        logger.info(
            f"FlashAttention-2: {'enabled' if self.flash_attention_settings.enabled else 'disabled'}"
        )
        logger.info(f"torch.compile: {use_compile}")

    def load_model(self) -> None:
        """Load the model with quantization and FlashAttention-2 configuration."""
        from transformers import AutoModelForCausalLM, AutoTokenizer

        logger.info("Loading Nemotron model with HuggingFace Transformers...")
        log_memory_info()
        log_attention_info()

        # Get quantization configuration
        try:
            bnb_config = get_quantization_config(settings=self.quantization_settings)
        except (ImportError, RuntimeError) as e:
            logger.error(f"Quantization setup failed: {e}")
            raise

        # Get attention implementation (FlashAttention-2, SDPA, or eager)
        self.attention_implementation = get_attention_implementation(
            settings=self.flash_attention_settings
        )
        logger.info(f"Using attention implementation: {self.attention_implementation}")

        # Log memory estimate
        # Nemotron-3-Nano-30B-A3B has ~30B parameters
        estimates = get_memory_estimate(30.0, self.quantization_settings.mode)
        logger.info(
            f"Memory estimates for 30B model: "
            f"weights={estimates['model_weights']:.1f}GB, "
            f"min_total={estimates['total_min']:.1f}GB, "
            f"recommended={estimates['total_recommended']:.1f}GB"
        )

        # Load tokenizer
        logger.info("Loading tokenizer...")
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_path,
            trust_remote_code=True,
        )

        # Set padding token if not set (required for batch generation)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # Load model with quantization and attention optimization
        logger.info(
            f"Loading model with quantization={self.quantization_settings.mode.value}, "
            f"attention={self.attention_implementation}..."
        )
        load_start = time.perf_counter()

        if bnb_config is not None:
            # Load with BitsAndBytes quantization and attention optimization
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                quantization_config=bnb_config,
                attn_implementation=self.attention_implementation,
                device_map="auto",  # Accelerate handles device placement
                trust_remote_code=True,
                torch_dtype=self.quantization_settings.compute_dtype,
            )
        else:
            # Load without quantization but with attention optimization
            dtype = torch.float16 if "cuda" in self.device else torch.float32
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                attn_implementation=self.attention_implementation,
                device_map="auto" if "cuda" in self.device else None,
                torch_dtype=dtype,
                trust_remote_code=True,
            )
            if "cuda" not in self.device:
                self.model = self.model.to(self.device)

        load_time = time.perf_counter() - load_start
        logger.info(f"Model loaded in {load_time:.1f}s")

        # Set to evaluation mode
        self.model.eval()

        # Log memory after loading
        log_memory_info()

        # Apply torch.compile if requested
        if self.use_compile and is_compile_supported():
            try:
                logger.info("Applying torch.compile() for optimized inference...")
                # Use reduce-overhead mode for inference
                self.model = compile_model(self.model, mode="reduce-overhead")
                self.is_compiled = True
                logger.info("Model compiled successfully")
            except Exception as e:
                logger.warning(f"torch.compile() failed: {e}")
                logger.info("Continuing with uncompiled model")

        # Warmup inference
        self._warmup()

        logger.info("Model loaded and ready for inference")

    def _warmup(self, num_iterations: int = 2) -> None:
        """Warmup the model with short prompts."""
        logger.info(f"Warming up model with {num_iterations} iterations...")

        warmup_prompt = f"{self.IM_START}user\nHello{self.IM_END}\n{self.IM_START}assistant\n"

        for i in range(num_iterations):
            try:
                _ = self.generate(warmup_prompt, max_tokens=10)
                logger.info(f"Warmup iteration {i + 1}/{num_iterations} complete")
            except Exception as e:
                logger.warning(f"Warmup iteration {i + 1} failed: {e}")

        logger.info("Warmup complete")

    def format_chat_messages(self, messages: list[ChatMessage]) -> str:
        """Format chat messages in ChatML format.

        Args:
            messages: List of chat messages

        Returns:
            ChatML-formatted prompt string
        """
        prompt_parts = []

        for msg in messages:
            prompt_parts.append(f"{self.IM_START}{msg.role}\n{msg.content}{self.IM_END}")

        # Add assistant prompt start
        prompt_parts.append(f"{self.IM_START}assistant\n")

        return "\n".join(prompt_parts)

    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        top_p: float = 0.95,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> tuple[str, int, int, float]:
        """Generate text from a prompt.

        Args:
            prompt: Input prompt (should be in ChatML format)
            temperature: Sampling temperature
            top_p: Top-p (nucleus) sampling
            max_tokens: Maximum tokens to generate
            stop: Stop sequences

        Returns:
            Tuple of (generated_text, tokens_generated, tokens_input, time_ms)
        """
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("Model not loaded")

        max_tokens = max_tokens or self.max_new_tokens

        start_time = time.perf_counter()

        # Tokenize input
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            padding=True,
            truncation=True,
        )

        # Move inputs to model device
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        input_length = inputs["input_ids"].shape[1]

        # Build stopping criteria if stop sequences provided
        stop_token_ids = []
        if stop:
            for stop_seq in stop:
                # Encode stop sequence
                stop_ids = self.tokenizer.encode(stop_seq, add_special_tokens=False)
                if stop_ids:
                    stop_token_ids.append(stop_ids[0])

        # Add ChatML end token
        im_end_id = self.tokenizer.encode(self.IM_END, add_special_tokens=False)
        if im_end_id:
            stop_token_ids.extend(im_end_id)

        # Generate
        with torch.inference_mode():
            generation_config = {
                "max_new_tokens": max_tokens,
                "do_sample": temperature > 0,
                "temperature": temperature if temperature > 0 else 1.0,
                "top_p": top_p,
                "pad_token_id": self.tokenizer.pad_token_id,
                "eos_token_id": stop_token_ids if stop_token_ids else self.tokenizer.eos_token_id,
            }

            outputs = self.model.generate(
                **inputs,
                **generation_config,
            )

        # Decode output
        generated_ids = outputs[0][input_length:]
        generated_text = self.tokenizer.decode(generated_ids, skip_special_tokens=False)

        # Clean up stop sequences from output
        for stop_seq in (stop or []) + [self.IM_END, self.IM_START]:
            if stop_seq in generated_text:
                generated_text = generated_text.split(stop_seq)[0]

        tokens_generated = len(generated_ids)
        generation_time_ms = (time.perf_counter() - start_time) * 1000

        return generated_text.strip(), tokens_generated, input_length, generation_time_ms


# =============================================================================
# Global Model Instance
# =============================================================================
model: NemotronHFModel | None = None


def get_vram_usage() -> float | None:
    """Get VRAM usage in GB."""
    try:
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated() / (1024**3)
    except Exception as e:
        logger.warning(f"Failed to get VRAM usage: {e}")
    return None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Lifespan context manager for FastAPI app."""
    global model

    # Startup
    logger.info("Starting Nemotron HuggingFace Server...")

    # Load model configuration from environment
    model_path = os.environ.get("NEMOTRON_MODEL_PATH", "nvidia/Nemotron-3-Nano-30B-A3B")
    device = "cuda:0" if torch.cuda.is_available() else "cpu"

    # Get quantization settings from environment
    quant_settings = QuantizationSettings.from_environment()

    # Get FlashAttention-2 settings from environment
    flash_attn_settings = FlashAttentionSettings.from_environment()

    # torch.compile settings
    use_compile = os.environ.get("NEMOTRON_USE_COMPILE", "1").lower() in ("1", "true", "yes")

    # Max tokens setting
    max_new_tokens = int(os.environ.get("NEMOTRON_MAX_NEW_TOKENS", "1536"))

    try:
        model = NemotronHFModel(
            model_path=model_path,
            device=device,
            quantization_settings=quant_settings,
            flash_attention_settings=flash_attn_settings,
            use_compile=use_compile,
            max_new_tokens=max_new_tokens,
        )
        model.load_model()

        # Update metrics
        MODEL_LOADED.set(1)
        mode_value = {"none": 0, "4bit": 4, "8bit": 8}.get(quant_settings.mode.value, 0)
        QUANTIZATION_MODE.set(mode_value)
        flash_attn_enabled = 1 if model.attention_implementation == "flash_attention_2" else 0
        FLASH_ATTENTION_ENABLED.set(flash_attn_enabled)

        logger.info("Model loaded successfully")

    except FileNotFoundError:
        logger.warning(f"Model not found at {model_path}")
        logger.warning("Server will start but inference endpoints will fail")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        logger.warning("Server will start but inference endpoints will fail")

    yield

    # Shutdown
    logger.info("Shutting down Nemotron HuggingFace Server...")
    if model is not None and model.model is not None:
        del model.model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


# =============================================================================
# FastAPI Application
# =============================================================================
app = FastAPI(
    title="Nemotron HuggingFace Server",
    description="LLM inference server using HuggingFace Transformers with BitsAndBytes quantization",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    cuda_available = torch.cuda.is_available()
    device = "cuda:0" if cuda_available else "cpu"
    vram_used = get_vram_usage() if cuda_available else None

    quant_mode = "none"
    quant_details = None
    attn_impl = "unknown"
    if model is not None:
        quant_mode = model.quantization_settings.mode.value
        quant_details = {
            "mode": quant_mode,
            "quant_type": model.quantization_settings.quant_type.value,
            "double_quant": model.quantization_settings.use_double_quant,
            "compute_dtype": str(model.quantization_settings.compute_dtype),
        }
        attn_impl = model.attention_implementation

    return HealthResponse(
        status="healthy" if model is not None and model.model is not None else "degraded",
        model=model.model_name if model else "not loaded",
        model_loaded=model is not None and model.model is not None,
        device=device,
        cuda_available=cuda_available,
        vram_used_gb=vram_used,
        quantization=quant_mode,
        quantization_details=quant_details,
        attention_implementation=attn_impl,
        flash_attention_available=is_flash_attention_available(),
    )


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    # Update gauges
    MODEL_LOADED.set(1 if model is not None and model.model is not None else 0)

    if torch.cuda.is_available():
        vram_used = get_vram_usage()
        if vram_used is not None:
            GPU_MEMORY_USED_GB.set(vram_used)

    return Response(content=generate_latest(), media_type="text/plain; charset=utf-8")


@app.post("/completion", response_model=CompletionResponse)
async def completion(request: CompletionRequest) -> CompletionResponse:
    """Text completion endpoint (llama.cpp compatible).

    Accepts a prompt in ChatML format and generates a completion.
    """
    if model is None or model.model is None:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="completion", status="error").inc()
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        start_time = time.perf_counter()

        # Run generation in thread pool to avoid blocking
        generated_text, tokens_gen, tokens_input, gen_time_ms = await asyncio.to_thread(
            model.generate,
            request.prompt,
            request.temperature,
            request.top_p,
            request.max_tokens,
            request.stop,
        )

        latency = time.perf_counter() - start_time

        # Record metrics
        INFERENCE_LATENCY_SECONDS.labels(endpoint="completion").observe(latency)
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="completion", status="success").inc()
        TOKENS_GENERATED.inc(tokens_gen)

        return CompletionResponse(
            content=generated_text,
            tokens_predicted=tokens_gen,
            tokens_evaluated=tokens_input,
            generation_time_ms=gen_time_ms,
            model=model.model_name,
        )

    except HTTPException:
        raise
    except Exception as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="completion", status="error").inc()
        logger.error(f"Completion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Completion failed: {e!s}") from e


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest) -> ChatCompletionResponse:
    """OpenAI-compatible chat completions endpoint.

    Accepts messages in OpenAI format and returns a chat completion.
    """
    if model is None or model.model is None:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="chat_completions", status="error").inc()
        raise HTTPException(status_code=503, detail="Model not loaded")

    if request.stream:
        raise HTTPException(status_code=400, detail="Streaming not yet supported")

    try:
        start_time = time.perf_counter()

        # Format messages to ChatML prompt
        prompt = model.format_chat_messages(request.messages)

        # Generate
        generated_text, tokens_gen, tokens_input, _ = await asyncio.to_thread(
            model.generate,
            prompt,
            request.temperature,
            request.top_p,
            request.max_tokens,
            None,  # No custom stop sequences
        )

        latency = time.perf_counter() - start_time

        # Record metrics
        INFERENCE_LATENCY_SECONDS.labels(endpoint="chat_completions").observe(latency)
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="chat_completions", status="success").inc()
        TOKENS_GENERATED.inc(tokens_gen)

        # Build response
        import uuid

        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
            created=int(time.time()),
            model=model.model_name,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=generated_text),
                    finish_reason="stop",
                )
            ],
            usage=ChatCompletionUsage(
                prompt_tokens=tokens_input,
                completion_tokens=tokens_gen,
                total_tokens=tokens_input + tokens_gen,
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        INFERENCE_REQUESTS_TOTAL.labels(endpoint="chat_completions", status="error").inc()
        logger.error(f"Chat completion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat completion failed: {e!s}") from e


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8091"))
    uvicorn.run(app, host=host, port=port, log_level="info")
