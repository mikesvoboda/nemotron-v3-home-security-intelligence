"""AI services package.

Contains GPU-accelerated ML services for the home security monitoring system:
- clip: CLIP image-text embedding service
- common: Shared TensorRT optimization infrastructure
- enrichment: Detection enrichment classifiers (vehicle, pet, clothing, depth, pose)
- florence: Florence-2 vision-language model service
- nemotron: Nemotron LLM risk analysis service
- rtdetr: RT-DETRv2 object detection service

TensorRT Optimization:
    The common package provides reusable TensorRT infrastructure for accelerating
    model inference. See ai/common/AGENTS.md for documentation.

    from ai.common import TensorRTConverter, TensorRTInferenceBase
"""
