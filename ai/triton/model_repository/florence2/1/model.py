"""Florence-2 Vision-Language Model - Triton Python Backend.

Loads Florence-2-base for autoregressive image-to-text generation tasks
(captioning, OCR, object detection, etc.).  Uses the Microsoft custom
modeling code (trust_remote_code) with runtime patches for transformers
5.x compatibility.  Cannot be exported to ONNX/TensorRT due to
autoregressive generation.

Compatibility notes (transformers >= 5.0):
  - The old Microsoft ``configuration_florence2.py`` accesses
    ``self.forced_bos_token_id`` before ``super().__init__()`` sets it.
    We monkey-patch ``PretrainedConfig.__getattribute__`` to return
    ``None`` for that attribute instead of raising ``AttributeError``.
  - The old Microsoft ``modeling_florence2.py`` calls
    ``torch.linspace(...).item()`` during ``__init__``, which fails
    when transformers materialises parameters on the meta device.
    We monkey-patch ``torch.linspace`` to fall back to CPU tensors.
  - The model class lacks ``_supports_sdpa``; we set it to ``False``.
  - Weight-tied parameters (``embed_tokens``, ``lm_head``) are reported
    as MISSING by the new loader.  We re-assign them from ``shared``.
  - The old ``processing_florence2.py`` is incompatible (accesses
    ``tokenizer.additional_special_tokens``), so we build the processor
    from separate ``AutoTokenizer`` + ``AutoImageProcessor`` and import
    the old ``Florence2PostProcesser`` class for post-processing only.

Input tensors (defined in config.pbtxt):
  - image: TYPE_STRING [1] - base64-encoded image bytes
  - prompt: TYPE_STRING [1] - Florence-2 task prompt string

Output tensors:
  - result: TYPE_STRING [1] - JSON string with task-specific result
  - inference_time_ms: TYPE_FP32 [1] - inference time in milliseconds

Supported prompts:
  <CAPTION>, <DETAILED_CAPTION>, <MORE_DETAILED_CAPTION>,
  <OD>, <DENSE_REGION_CAPTION>, <REGION_PROPOSAL>,
  <OCR>, <OCR_WITH_REGION>, <VQA>...,
  <OPEN_VOCABULARY_DETECTION>...,
  <REGION_TO_DESCRIPTION>..., <CAPTION_TO_PHRASE_GROUNDING>...

Model zoo path: /models/zoo/florence-2-base
Reference: ai/florence/model.py (standalone FastAPI server)
"""

import base64
import importlib.util
import io
import json
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np
import safetensors.torch as safetensors_load
import torch
import triton_python_backend_utils as pb_utils
from PIL import Image

logger = logging.getLogger("triton.florence2")

# ---------------------------------------------------------------------------
# Task prompt / post-processing maps (must match the old MS processor)
# ---------------------------------------------------------------------------
TASKS_ANSWER_POST_PROCESSING_TYPE = {
    "<OCR>": "pure_text",
    "<OCR_WITH_REGION>": "ocr",
    "<CAPTION>": "pure_text",
    "<DETAILED_CAPTION>": "pure_text",
    "<MORE_DETAILED_CAPTION>": "pure_text",
    "<OD>": "description_with_bboxes",
    "<DENSE_REGION_CAPTION>": "description_with_bboxes",
    "<CAPTION_TO_PHRASE_GROUNDING>": "phrase_grounding",
    "<REFERRING_EXPRESSION_SEGMENTATION>": "polygons",
    "<REGION_TO_SEGMENTATION>": "polygons",
    "<OPEN_VOCABULARY_DETECTION>": "description_with_bboxes_or_polygons",
    "<REGION_TO_CATEGORY>": "pure_text",
    "<REGION_TO_DESCRIPTION>": "pure_text",
    "<REGION_TO_OCR>": "pure_text",
    "<REGION_PROPOSAL>": "bboxes",
}

# Task token -> natural language prompt conversion.
# Florence-2's architecture requires task tokens to be converted before tokenization.
# From processing_florence2.py _construct_prompts().
TASK_PROMPTS_WITHOUT_INPUTS = {
    "<CAPTION>": "What does the image describe?",
    "<DETAILED_CAPTION>": "Describe in detail what is shown in the image.",
    "<MORE_DETAILED_CAPTION>": "Describe with a paragraph what is shown in the image.",
    "<OD>": "Locate the objects with category name in the image.",
    "<DENSE_REGION_CAPTION>": "Locate the objects in the image, with their descriptions.",
    "<REGION_PROPOSAL>": "Locate the region proposals in the image.",
    "<OCR>": "What is the text in the image?",
    "<OCR_WITH_REGION>": "What is the text in the image, with regions?",
}

TASK_PROMPTS_WITH_INPUT = {
    "<CAPTION_TO_PHRASE_GROUNDING>": "Locate the phrases in the caption: {input}",
    "<REFERRING_EXPRESSION_SEGMENTATION>": "Locate {input} in the image with mask",
    "<REGION_TO_SEGMENTATION>": "What is the polygon mask of region {input}",
    "<OPEN_VOCABULARY_DETECTION>": "Locate {input} in the image.",
    "<REGION_TO_CATEGORY>": "What is the region {input}?",
    "<REGION_TO_DESCRIPTION>": "What does the region {input} describe?",
    "<REGION_TO_OCR>": "What text is in the region {input}?",
}


def _convert_task_prompt(prompt: str) -> str:
    """Convert Florence-2 task tokens to natural language prompts.

    The bare tokenizer doesn't know about task tokens like <CAPTION>.
    They must be converted to natural language before tokenization.
    """
    # Check simple tasks first
    if prompt in TASK_PROMPTS_WITHOUT_INPUTS:
        return TASK_PROMPTS_WITHOUT_INPUTS[prompt]

    # Check tasks with input (e.g., "<CAPTION_TO_PHRASE_GROUNDING> a cat")
    for task_token, template in TASK_PROMPTS_WITH_INPUT.items():
        if prompt.startswith(task_token):
            user_input = prompt[len(task_token) :].strip()
            return template.format(input=user_input)

    # Unknown task — pass through as-is (may be a natural language prompt)
    return prompt


# ---------------------------------------------------------------------------
# Transformers 5.x compatibility patches
# ---------------------------------------------------------------------------
def _apply_transformers5_patches():
    """Apply monkey-patches so the old Microsoft Florence-2 custom code
    works under transformers >= 5.0.

    Must be called before any ``from_pretrained`` / model construction.
    """
    import transformers.configuration_utils as _cfg

    _original_getattr = _cfg.PretrainedConfig.__getattribute__

    def _patched_getattr(self, key):
        try:
            return _original_getattr(self, key)
        except AttributeError:
            # The old Florence2LanguageConfig.__init__ reads these before
            # super().__init__() has a chance to set them.
            if key in ("forced_bos_token_id", "forced_eos_token_id"):
                return None
            raise

    _cfg.PretrainedConfig.__getattribute__ = _patched_getattr

    # torch.linspace on the meta device doesn't support .item()
    _real_linspace = torch.linspace

    def _safe_linspace(*args, **kwargs):
        result = _real_linspace(*args, **kwargs)
        if result.device.type == "meta":
            cpu_kwargs = {k: v for k, v in kwargs.items() if k != "device"}
            return _real_linspace(*args, device="cpu", **cpu_kwargs)
        return result

    torch.linspace = _safe_linspace


def _load_old_ms_post_processor(model_path, tokenizer):
    """Load the Florence2PostProcesser from the old Microsoft checkpoint.

    Tries to import the old processing_florence2.py module. If that fails
    (e.g. transformers 5.x metaclass conflicts), falls back to extracting
    just the Florence2PostProcesser class by patching the module to skip
    the incompatible Florence2Processor class definition.
    """
    proc_py = Path(model_path) / "processing_florence2.py"
    if not proc_py.is_file():
        logger.warning("processing_florence2.py not found, using fallback post-processor")
        return _FallbackPostProcessor(tokenizer)

    try:
        # Read the source and remove the Florence2Processor class (inherits
        # from ProcessorMixin which is incompatible with transformers 5.x).
        # We only need Florence2PostProcesser.
        source = proc_py.read_text()

        # Replace the ProcessorMixin import with a stub
        source = source.replace(
            "from transformers import ProcessorMixin",
            "class ProcessorMixin: pass  # stub",
        )
        source = source.replace(
            "from transformers.processing_utils import ProcessorMixin",
            "class ProcessorMixin: pass  # stub",
        )

        import types

        mod = types.ModuleType("_ms_proc_florence2")
        mod.__file__ = str(proc_py)
        sys.modules[mod.__name__] = mod
        exec(compile(source, str(proc_py), "exec"), mod.__dict__)  # noqa: S102 nosemgrep: dangerous-eval
        return mod.Florence2PostProcesser(tokenizer=tokenizer)
    except Exception as exc:
        logger.warning("Failed to load MS post-processor: %s, using fallback", exc)
        return _FallbackPostProcessor(tokenizer)


class _FallbackPostProcessor:
    """Minimal post-processor for when the old MS module can't be loaded."""

    def __init__(self, tokenizer):
        self.tokenizer = tokenizer

    def __call__(self, text, image_size, parse_tasks):  # noqa: ARG002
        clean = text.replace("<s>", "").replace("</s>", "").replace("<pad>", "").strip()
        return {parse_tasks: clean}


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------
def _load_florence2_model(model_path, dtype, device):
    """Load the old Microsoft Florence-2 model on *device* with *dtype*.

    Uses ``trust_remote_code=True`` for the model architecture (which
    relies on ``einops``), then manually loads safetensors weights and
    re-ties the shared embedding.
    """
    from transformers import AutoConfig
    from transformers.dynamic_module_utils import get_class_from_dynamic_module

    # 1. Config ---------------------------------------------------------------
    config = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
    config._attn_implementation = "eager"
    config._attn_implementation_internal = "eager"

    # 2. Model class ----------------------------------------------------------
    model_cls = get_class_from_dynamic_module(
        "modeling_florence2.Florence2ForConditionalGeneration",
        model_path,
        trust_remote_code=True,
    )
    model_cls._supports_sdpa = False

    # 3. Instantiate with random weights on CPU -------------------------------
    model = model_cls(config)

    # 4. Load safetensors checkpoint ------------------------------------------
    ckpt_path = Path(model_path) / "model.safetensors"
    if not ckpt_path.is_file():
        # Fall back to pytorch_model.bin
        ckpt_path = Path(model_path) / "pytorch_model.bin"
        ckpt = torch.load(str(ckpt_path), map_location="cpu", weights_only=True)
    else:
        ckpt = safetensors_load.load_file(str(ckpt_path), device="cpu")

    model_sd = model.state_dict()
    loaded = 0
    for key, tensor in ckpt.items():
        if key in model_sd and model_sd[key].shape == tensor.shape:
            model_sd[key] = tensor
            loaded += 1

    model.load_state_dict(model_sd, strict=False)
    logger.info("Florence-2: loaded %d/%d checkpoint tensors", loaded, len(ckpt))

    # 5. Re-tie shared embedding -> encoder, decoder, lm_head ----------------
    shared = model.language_model.model.shared.weight
    model.language_model.model.encoder.embed_tokens.weight = shared
    model.language_model.model.decoder.embed_tokens.weight = shared
    model.language_model.lm_head.weight = shared

    # 6. Cast and move --------------------------------------------------------
    model = model.to(dtype=dtype, device=device)
    model.eval()
    return model


class TritonPythonModel:
    """Triton Python backend for Florence-2 vision-language model."""

    def initialize(self, _args):
        """Load Florence-2 model and processor onto GPU.

        Called once when Triton loads this model. Uses FP16/BF16
        to minimize VRAM footprint (~460 MiB).

        Args:
            args: Dict with model configuration provided by Triton.
        """
        logger.info("Florence-2: initializing Triton Python backend...")

        # Apply compatibility patches before any transformers import
        _apply_transformers5_patches()

        model_path = os.environ.get("FLORENCE_MODEL_PATH", "/models/zoo/florence-2-base")
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"

        # Determine compute dtype
        if self.device != "cpu":
            if torch.cuda.is_bf16_supported():
                dtype = torch.bfloat16
            else:
                dtype = torch.float16
        else:
            dtype = torch.float32

        logger.info(
            "Florence-2: loading from %s on %s with %s",
            model_path,
            self.device,
            dtype,
        )

        # Load tokenizer and image processor separately.
        # (The old MS Florence2Processor is incompatible with
        # transformers 5.x, so we build the pipeline by hand.)
        from transformers import AutoImageProcessor, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.image_processor = AutoImageProcessor.from_pretrained(model_path)

        # Add Florence-2's special location/segmentation tokens.
        # The full AutoProcessor (trust_remote_code) registers these automatically,
        # but since we use a bare AutoTokenizer we must add them manually.
        # Without these tokens, location outputs like <loc_123> appear as garbage.
        special_tokens = [f"<loc_{i}>" for i in range(1000)] + [f"<seg_{i}>" for i in range(128)]
        self.tokenizer.add_special_tokens({"additional_special_tokens": special_tokens})
        logger.info(
            "Florence-2: added %d special tokens (loc_0..999, seg_0..127)",
            len(special_tokens),
        )

        # Import the old MS post-processor for structured output parsing
        self.post_processor = _load_old_ms_post_processor(model_path, self.tokenizer)

        # Load model with trust_remote_code + manual weight loading
        self.model = _load_florence2_model(model_path, dtype, self.device)

        # Warmup to pre-allocate CUDA memory
        self._warmup()
        logger.info("Florence-2: initialization complete")

    def _warmup(self):
        """Run warmup inference with a dummy image."""
        dummy = Image.new("RGB", (640, 480), color=(128, 128, 128))
        for i in range(2):
            try:
                self._run_inference(dummy, "<CAPTION>")
                logger.info("Florence-2: warmup %d/2 complete", i + 1)
            except Exception as exc:
                logger.warning("Florence-2: warmup %d failed: %s", i + 1, exc)

    def _run_inference(self, image, prompt):
        """Run Florence-2 inference on a single image.

        Replicates the core inference logic from
        ``ai/florence/model.py:Florence2Model.extract_raw()``.

        Args:
            image: PIL Image in RGB mode.
            prompt: Florence-2 task prompt string.

        Returns:
            The parsed model output for the given prompt (dict, list, or str).
        """
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Convert task tokens to natural language prompts.
        # The bare tokenizer doesn't understand <CAPTION> etc.
        nl_prompt = _convert_task_prompt(prompt)

        # Tokenize text (the old MS model fuses image+text internally
        # in its custom generate() method, so we do NOT prepend image
        # tokens to the text).
        text_inputs = self.tokenizer(nl_prompt, return_tensors="pt")
        pixel_values = self.image_processor(image, return_tensors="pt")["pixel_values"]

        # Move inputs to device with model dtype
        model_dtype = next(self.model.parameters()).dtype
        input_ids = text_inputs["input_ids"].to(self.device)
        pixel_values = pixel_values.to(self.device, model_dtype)

        # Greedy decoding with KV cache disabled to work around
        # Florence-2's prepare_inputs_for_generation bug
        with torch.inference_mode():
            generated_ids = self.model.generate(
                input_ids=input_ids,
                pixel_values=pixel_values,
                max_new_tokens=1024,
                early_stopping=False,
                do_sample=False,
                num_beams=1,
                use_cache=False,
            )

        generated_text = self.tokenizer.batch_decode(generated_ids, skip_special_tokens=False)[0]

        # Post-process using the old MS Florence2PostProcesser
        task_type = TASKS_ANSWER_POST_PROCESSING_TYPE.get(prompt, "pure_text")
        parsed = self.post_processor(
            text=generated_text,
            image_size=(image.width, image.height),
            parse_tasks=task_type,
        )

        # Extract the task-specific result
        if task_type in parsed:
            result = parsed[task_type]
            if task_type == "pure_text":
                # Remove special tokens from pure text
                result = result.replace("<s>", "").replace("</s>", "").strip()
            return result

        # Fallback: return cleaned text
        return generated_text.replace("<s>", "").replace("</s>", "").strip()

    def execute(self, requests):
        """Process a batch of inference requests.

        Each request contains:
          - ``image``: base64-encoded image (TYPE_STRING)
          - ``prompt``: task prompt string (TYPE_STRING)

        Returns one InferenceResponse per request.  Errors are returned
        via ``pb_utils.TritonError`` instead of raised exceptions.
        """
        responses = []

        for request in requests:
            try:
                start_time = time.perf_counter()

                # --- Decode image input ---
                image_tensor = pb_utils.get_input_tensor_by_name(request, "image")
                if image_tensor is None:
                    responses.append(
                        pb_utils.InferenceResponse(
                            error=pb_utils.TritonError("Missing required input: 'image'"),
                        )
                    )
                    continue

                image_raw = image_tensor.as_numpy().flat[0]
                if isinstance(image_raw, bytes | np.bytes_):
                    image_b64 = bytes(image_raw)
                else:
                    image_b64 = image_raw.encode("utf-8")

                try:
                    image_data = base64.b64decode(image_b64)
                except Exception as exc:
                    responses.append(
                        pb_utils.InferenceResponse(
                            error=pb_utils.TritonError(f"Invalid base64 image: {exc}"),
                        )
                    )
                    continue

                try:
                    image = Image.open(io.BytesIO(image_data))
                except Exception as exc:
                    responses.append(
                        pb_utils.InferenceResponse(
                            error=pb_utils.TritonError(f"Cannot decode image: {exc}"),
                        )
                    )
                    continue

                # --- Decode prompt input ---
                prompt_tensor = pb_utils.get_input_tensor_by_name(request, "prompt")
                if prompt_tensor is None:
                    responses.append(
                        pb_utils.InferenceResponse(
                            error=pb_utils.TritonError("Missing required input: 'prompt'"),
                        )
                    )
                    continue

                prompt_raw = prompt_tensor.as_numpy().flat[0]
                if isinstance(prompt_raw, bytes | np.bytes_):
                    prompt = bytes(prompt_raw).decode("utf-8")
                else:
                    prompt = str(prompt_raw)

                # --- Run inference ---
                result = self._run_inference(image, prompt)
                inference_ms = (time.perf_counter() - start_time) * 1000

                # Serialize result to JSON
                output_dict = {"result": result, "prompt": prompt}
                result_json = json.dumps(output_dict, default=str)

                # Build output tensors
                out_result = pb_utils.Tensor(
                    "result",
                    np.array([result_json.encode("utf-8")], dtype=np.object_),
                )
                out_time = pb_utils.Tensor(
                    "inference_time_ms",
                    np.array([inference_ms], dtype=np.float32),
                )
                responses.append(pb_utils.InferenceResponse(output_tensors=[out_result, out_time]))

            except torch.cuda.OutOfMemoryError:
                logger.error("Florence-2: GPU OOM during inference")
                torch.cuda.empty_cache()
                responses.append(
                    pb_utils.InferenceResponse(
                        error=pb_utils.TritonError("GPU out of memory during Florence-2 inference"),
                    )
                )

            except Exception as exc:
                logger.error("Florence-2: inference failed: %s", exc, exc_info=True)
                responses.append(
                    pb_utils.InferenceResponse(
                        error=pb_utils.TritonError(f"Florence-2 inference error: {exc}"),
                    )
                )

        return responses

    def finalize(self):
        """Release GPU resources when Triton unloads this model."""
        logger.info("Florence-2: finalizing...")
        if hasattr(self, "model") and self.model is not None:
            del self.model
        if hasattr(self, "tokenizer") and self.tokenizer is not None:
            del self.tokenizer
        if hasattr(self, "image_processor") and self.image_processor is not None:
            del self.image_processor
        if hasattr(self, "post_processor") and self.post_processor is not None:
            del self.post_processor
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("Florence-2: finalized")
