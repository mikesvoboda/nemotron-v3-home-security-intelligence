# AI Tests Directory

This directory contains tests for AI model utilities.

## Test Files

| File                             | Purpose                                        |
| -------------------------------- | ---------------------------------------------- |
| `test_compile_utils.py`          | Tests for torch.compile() utilities (NEM-3370) |
| `test_batch_utils.py`            | Tests for batch inference utilities (NEM-3372) |
| `test_cpu_offloading.py`         | Tests for CPU offloading utilities             |
| `test_cuda_graph_manager.py`     | Tests for CUDA graph management                |
| `test_flash_attention_config.py` | Tests for FlashAttention configuration         |
| `test_gpu_memory_pool.py`        | Tests for GPU memory pool management           |
| `test_hub_cache_config.py`       | Tests for HuggingFace hub cache configuration  |
| `test_quantization_config.py`    | Tests for quantization configuration           |
| `test_static_kv_cache.py`        | Tests for static KV cache                      |
| `test_torch_optimizations.py`    | Tests for PyTorch optimization utilities       |
| `test_warmup_utils.py`           | Tests for model warmup utilities               |

## Running Tests

```bash
# Run all AI tests
cd ai && python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_compile_utils.py -v

# Run with coverage
python -m pytest tests/ -v --cov=. --cov-report=term-missing
```

## Test Categories

### Compile Utils Tests (NEM-3370)

- Version detection for PyTorch 2.0+
- Configuration validation
- Safe fallback on compilation errors
- Warmup functionality

### Batch Utils Tests (NEM-3372)

- Batch configuration
- Image padding for variable sizes
- Batch processing with chunking
- Bounding box coordinate adjustment
