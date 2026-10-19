"""AI services package.

Contains GPU-accelerated ML services for the home security monitoring system:
- gateway: FastAPI facade over Triton (/yolo26 + /enrich-lt)
- triton: Triton Inference Server model repository
- vlm: ai-vlm llama.cpp engine build context
- yolo26: YOLO26 TensorRT engine builder
"""
