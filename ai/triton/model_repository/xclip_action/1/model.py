"""X-CLIP Action Recognition - Triton Python Backend.

Loads microsoft/xclip-base-patch16-16-frames for zero-shot temporal
action recognition from multi-frame video clips. Cannot be exported to
ONNX/TensorRT due to custom cross-frame temporal attention requiring
trust_remote_code=True.

Input tensors (defined in config.pbtxt):
  - frames: TYPE_STRING [1] - JSON array of base64-encoded frame images
  - labels: TYPE_STRING [1] - optional JSON array of action label strings

Output tensors:
  - action: TYPE_STRING [1] - recognized action class string
  - confidence: TYPE_FP32 [1] - top action confidence (0.0-1.0)
  - all_scores: TYPE_STRING [1] - JSON with all scores, is_suspicious, risk_weight

Model zoo path: /models/zoo/xclip-base-patch16-16-frames
Reference: ai/enrichment/models/action_recognizer.py (standalone ActionRecognizer)
"""

import base64
import io
import json
import logging
import os
import time

import numpy as np
import torch
from PIL import Image
from transformers import XCLIPModel, XCLIPProcessor

import triton_python_backend_utils as pb_utils

logger = logging.getLogger("triton.xclip_action")

# Security-relevant action classes for home surveillance.
# Replicated from ai/enrichment/models/action_recognizer.py.
SECURITY_ACTIONS = [
    "walking normally",
    "running",
    "delivering package",
    "checking mailbox",
    "ringing doorbell",
    "waving",
    "fighting",
    "falling down",
    "climbing",
    "breaking window",
    "picking lock",
    "hiding",
    "loitering",
    "carrying large object",
    "looking around suspiciously",
]

SUSPICIOUS_ACTIONS = frozenset({
    "fighting",
    "climbing",
    "breaking window",
    "picking lock",
    "hiding",
    "loitering",
    "looking around suspiciously",
})

# Risk weights for security assessment.
# Replicated from ai/enrichment/model.py.
_ACTION_RISK_WEIGHTS = {
    "fighting": 0.95,
    "breaking window": 0.95,
    "picking lock": 0.90,
    "climbing": 0.80,
    "hiding": 0.75,
    "loitering": 0.60,
    "looking around suspiciously": 0.65,
    "falling down": 0.50,
    "carrying large object": 0.40,
    "running": 0.30,
}


class TritonPythonModel:
    """Triton Python backend for X-CLIP temporal action recognition."""

    def initialize(self, args):
        """Load X-CLIP model and processor onto GPU.

        Called once when Triton loads this model. The model expects
        16-frame video clips and performs zero-shot action classification.

        Args:
            args: Dict with model configuration provided by Triton.
        """
        logger.info("X-CLIP: initializing Triton Python backend...")

        model_path = os.environ.get(
            "ACTION_MODEL_PATH", "/models/zoo/xclip-base-patch16-16-frames"
        )
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.num_frames = 16

        logger.info("X-CLIP: loading from %s on %s", model_path, self.device)

        # Load processor
        self.processor = XCLIPProcessor.from_pretrained(model_path)

        # Try SDPA for faster inference, fall back to default
        try:
            self.model = XCLIPModel.from_pretrained(
                model_path,
                attn_implementation="sdpa",
            )
            logger.info("X-CLIP: loaded with SDPA attention (optimized)")
        except (ValueError, ImportError) as exc:
            logger.warning("X-CLIP: SDPA unavailable, using default: %s", exc)
            self.model = XCLIPModel.from_pretrained(model_path)

        if "cuda" in self.device and torch.cuda.is_available():
            self.model = self.model.to(self.device)
        else:
            self.device = "cpu"

        self.model.eval()

        # Warmup
        self._warmup()
        logger.info("X-CLIP: initialization complete")

    def _warmup(self):
        """Run warmup inference with dummy frames."""
        dummy_frames = [
            Image.new("RGB", (224, 224), color=(128, 128, 128))
            for _ in range(self.num_frames)
        ]
        for i in range(2):
            try:
                self._run_inference(dummy_frames, ["walking normally", "running"])
                logger.info("X-CLIP: warmup %d/2 complete", i + 1)
            except Exception as exc:
                logger.warning("X-CLIP: warmup %d failed: %s", i + 1, exc)

    def _sample_frames(self, frames, num_frames=16):
        """Sample frames evenly from input sequence.

        Replicates logic from ActionRecognizer._sample_frames():
        - Fewer than needed: pad by repeating last frame.
        - More than needed: sample at regular intervals.

        Args:
            frames: List of PIL Images.
            num_frames: Target frame count (default 16).

        Returns:
            List of exactly num_frames RGB PIL Images.
        """
        if not frames:
            raise ValueError("Cannot sample from empty frame list")

        rgb_frames = []
        for frame in frames:
            if frame.mode != "RGB":
                frame = frame.convert("RGB")
            rgb_frames.append(frame)

        if len(rgb_frames) <= num_frames:
            result = rgb_frames.copy()
            while len(result) < num_frames:
                result.append(rgb_frames[-1])
            return result

        indices = np.linspace(0, len(rgb_frames) - 1, num_frames, dtype=int)
        return [rgb_frames[i] for i in indices]

    def _run_inference(self, frames, actions):
        """Run X-CLIP zero-shot action classification.

        Replicates the core logic from ActionRecognizer.recognize_action().

        Args:
            frames: List of PIL Images.
            actions: List of action label strings.

        Returns:
            Dict with action, confidence, is_suspicious, risk_weight, all_scores.
        """
        sampled = self._sample_frames(frames, self.num_frames)

        # "a person {action}" format for better zero-shot performance
        text_prompts = [f"a person {a}" for a in actions]

        # X-CLIP expects videos as list of frame lists: [[frame1, frame2, ...]]
        inputs = self.processor(
            text=text_prompts,
            videos=[sampled],
            return_tensors="pt",
            padding=True,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.inference_mode():
            outputs = self.model(**inputs)
            logits = outputs.logits_per_video
            probs = torch.softmax(logits, dim=1)[0]

        probs_np = probs.cpu().numpy()
        top_idx = int(probs_np.argmax())
        top_action = actions[top_idx]
        top_confidence = float(probs_np[top_idx])

        all_scores = {
            action: round(float(probs_np[i]), 4)
            for i, action in enumerate(actions)
        }

        is_suspicious = top_action in SUSPICIOUS_ACTIONS
        default_weight = 0.5 if is_suspicious else 0.1
        risk_weight = _ACTION_RISK_WEIGHTS.get(top_action, default_weight)

        return {
            "action": top_action,
            "confidence": round(top_confidence, 4),
            "is_suspicious": is_suspicious,
            "risk_weight": risk_weight,
            "all_scores": all_scores,
        }

    def execute(self, requests):
        """Process a batch of action recognition requests.

        Each request contains:
          - ``frames``: JSON array of base64-encoded images (TYPE_STRING)
          - ``labels``: optional JSON array of action labels (TYPE_STRING)

        Returns one InferenceResponse per request.
        """
        responses = []

        for request in requests:
            try:
                start_time = time.perf_counter()

                # --- Decode frames ---
                frames_tensor = pb_utils.get_input_tensor_by_name(request, "frames")
                if frames_tensor is None:
                    responses.append(pb_utils.InferenceResponse(
                        error=pb_utils.TritonError("Missing required input: 'frames'"),
                    ))
                    continue

                frames_raw = frames_tensor.as_numpy().flat[0]
                if isinstance(frames_raw, (bytes, np.bytes_)):
                    frames_str = bytes(frames_raw).decode("utf-8")
                else:
                    frames_str = str(frames_raw)

                try:
                    frame_b64_list = json.loads(frames_str)
                except json.JSONDecodeError as exc:
                    responses.append(pb_utils.InferenceResponse(
                        error=pb_utils.TritonError(f"Invalid JSON in 'frames': {exc}"),
                    ))
                    continue

                if not isinstance(frame_b64_list, list) or not frame_b64_list:
                    responses.append(pb_utils.InferenceResponse(
                        error=pb_utils.TritonError(
                            "'frames' must be a non-empty JSON array of base64 images"
                        ),
                    ))
                    continue

                # Decode each base64 frame to PIL Image
                pil_frames = []
                decode_ok = True
                for idx, frame_b64 in enumerate(frame_b64_list):
                    try:
                        raw = frame_b64 if isinstance(frame_b64, str) else str(frame_b64)
                        frame_bytes = base64.b64decode(raw)
                        pil_frames.append(Image.open(io.BytesIO(frame_bytes)))
                    except Exception as exc:
                        responses.append(pb_utils.InferenceResponse(
                            error=pb_utils.TritonError(
                                f"Failed to decode frame {idx}: {exc}"
                            ),
                        ))
                        decode_ok = False
                        break

                if not decode_ok:
                    continue

                # --- Decode labels (optional) ---
                actions = SECURITY_ACTIONS
                labels_tensor = pb_utils.get_input_tensor_by_name(request, "labels")
                if labels_tensor is not None:
                    labels_raw = labels_tensor.as_numpy().flat[0]
                    if isinstance(labels_raw, (bytes, np.bytes_)):
                        labels_str = bytes(labels_raw).decode("utf-8")
                    else:
                        labels_str = str(labels_raw)

                    labels_str = labels_str.strip()
                    if labels_str:
                        try:
                            parsed = json.loads(labels_str)
                            if isinstance(parsed, list) and parsed:
                                actions = parsed
                        except json.JSONDecodeError:
                            logger.warning(
                                "X-CLIP: invalid JSON in 'labels', using defaults"
                            )

                # --- Run inference ---
                result = self._run_inference(pil_frames, actions)
                inference_ms = (time.perf_counter() - start_time) * 1000

                # Build output tensors
                action_tensor = pb_utils.Tensor(
                    "action",
                    np.array([result["action"].encode("utf-8")], dtype=np.object_),
                )
                confidence_tensor = pb_utils.Tensor(
                    "confidence",
                    np.array([result["confidence"]], dtype=np.float32),
                )

                scores_output = {
                    "all_scores": result["all_scores"],
                    "is_suspicious": result["is_suspicious"],
                    "risk_weight": result["risk_weight"],
                    "inference_time_ms": round(inference_ms, 2),
                }
                all_scores_tensor = pb_utils.Tensor(
                    "all_scores",
                    np.array(
                        [json.dumps(scores_output).encode("utf-8")], dtype=np.object_
                    ),
                )

                responses.append(pb_utils.InferenceResponse(
                    output_tensors=[action_tensor, confidence_tensor, all_scores_tensor],
                ))

            except torch.cuda.OutOfMemoryError:
                logger.error("X-CLIP: GPU OOM during inference")
                torch.cuda.empty_cache()
                responses.append(pb_utils.InferenceResponse(
                    error=pb_utils.TritonError(
                        "GPU out of memory during X-CLIP inference"
                    ),
                ))

            except Exception as exc:
                logger.error("X-CLIP: inference failed: %s", exc, exc_info=True)
                responses.append(pb_utils.InferenceResponse(
                    error=pb_utils.TritonError(f"X-CLIP inference error: {exc}"),
                ))

        return responses

    def finalize(self):
        """Release GPU resources when Triton unloads this model."""
        logger.info("X-CLIP: finalizing...")
        if hasattr(self, "model") and self.model is not None:
            del self.model
        if hasattr(self, "processor") and self.processor is not None:
            del self.processor
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("X-CLIP: finalized")
