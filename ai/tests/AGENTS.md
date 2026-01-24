# AI Tests Directory

This directory contains tests for AI model utilities.

## Test Files

| File                    | Purpose                                        |
| ----------------------- | ---------------------------------------------- |
| `test_compile_utils.py` | Tests for torch.compile() utilities (NEM-3370) |
| `test_batch_utils.py`   | Tests for batch inference utilities (NEM-3372) |

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
