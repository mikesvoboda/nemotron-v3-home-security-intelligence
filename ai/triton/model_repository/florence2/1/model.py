"""Florence-2 Vision-Language Model - Triton Python Backend.

Loads Florence-2-base with trust_remote_code=True for autoregressive
image-to-text generation tasks (captioning, OCR, object detection, etc.).
Cannot be exported to ONNX/TensorRT due to custom HuggingFace model code
and autoregressive generation.

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
import io
import json
import logging
import os
import time

import numpy as np
import torch
import triton_python_backend_utils as pb_utils
from PIL import Image
from transformers import AutoModelForCausalLM, AutoProcessor

logger = logging.getLogger("triton.florence2")


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

        # Load processor (tokenizer + image processor)
        self.processor = AutoProcessor.from_pretrained(
            model_path,
            trust_remote_code=True,
        )

        # Load model with eager attention to avoid SDPA compatibility
        # issues with Florence-2's custom model code
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=dtype,
            trust_remote_code=True,
            attn_implementation="eager",
        ).to(self.device)

        self.model.eval()

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

        inputs = self.processor(
            text=prompt,
            images=image,
            return_tensors="pt",
        )

        # Move inputs to device with model dtype
        model_dtype = next(self.model.parameters()).dtype
        inputs = inputs.to(self.device, model_dtype)

        # Greedy decoding with KV cache disabled to work around
        # Florence-2's prepare_inputs_for_generation bug
        with torch.inference_mode():
            generated_ids = self.model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=1024,
                early_stopping=False,
                do_sample=False,
                num_beams=1,
                use_cache=False,
            )

        generated_text = self.processor.batch_decode(generated_ids, skip_special_tokens=False)[0]

        parsed = self.processor.post_process_generation(
            generated_text,
            task=prompt,
            image_size=(image.width, image.height),
        )

        if prompt in parsed:
            return parsed[prompt]
        return parsed

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
        if hasattr(self, "processor") and self.processor is not None:
            del self.processor
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("Florence-2: finalized")
