#!/usr/bin/env python3
"""Quantize CPU ONNX models to INT8 for faster inference."""

from pathlib import Path

from onnxruntime.quantization import QuantType, quantize_dynamic

TRITON_CACHE = Path("/export/ai_models/triton")

CPU_MODELS = [
    "fashion_clip",
    "demographics_age",
    "demographics_gender",
    "depth",
    "vehicle",
    "pet",
    "pose",
    "threat",
    "reid",
]

for model_name in CPU_MODELS:
    model_dir = TRITON_CACHE / model_name / "1"
    input_path = model_dir / "model.onnx"
    output_path = model_dir / "model_int8.onnx"

    if not input_path.exists():
        print(f"SKIP {model_name}: {input_path} not found")
        continue

    if output_path.exists():
        print(f"SKIP {model_name}: already quantized")
        continue

    print(f"Quantizing {model_name}...")
    quantize_dynamic(
        model_input=str(input_path),
        model_output=str(output_path),
        weight_type=QuantType.QInt8,
    )
    print(f"  Done: {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")

print("\nAll models quantized. Update config.pbtxt files to use model_int8.onnx")
