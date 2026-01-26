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

GPU Optimization Utilities (NEM-3771, NEM-3772, NEM-3813, NEM-3814):
    - cuda_graph_manager: CUDA graphs for reduced kernel launch overhead
    - gpu_memory_pool: Memory pooling for tensor allocation
    - static_kv_cache: StaticCache for KV cache optimization
    - cpu_offloading: CPU offloading for large models

    from ai.cuda_graph_manager import CUDAGraphManager, CUDAGraphInferenceWrapper
    from ai.gpu_memory_pool import GPUMemoryPool, get_global_pool
    from ai.static_kv_cache import StaticCacheManager, create_static_cache
    from ai.cpu_offloading import load_model_with_offloading, OffloadingConfig
"""
