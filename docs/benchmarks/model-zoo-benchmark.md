# Model Zoo Benchmark Results

**Date:** 2026-01-01 16:39:46
**GPU:** NVIDIA RTX A5500

## Summary

| Model | Load Time | VRAM Used | Inference | Recovered | Status |
|-------|-----------|-----------|-----------|-----------|--------|
| fashion-clip | 0.00s | 0MB | N/A | Yes | ERROR |
| weather-classification | 0.59s | 444MB | 274ms | No | OK |
| pet-classifier | 0.16s | 2MB | N/A | No | OK |

## Statistics

- **Models benchmarked:** 3
- **Successful:** 2
- **Failed:** 1
- **Total VRAM (all models):** 446MB
- **Average load time:** 0.38s
- **All VRAM recovered:** No

## Success Criteria

| Criteria | Target | Actual | Pass |
|----------|--------|--------|------|
| Max VRAM per model | <1500MB | 444MB | PASS |
| Max load time | <5s | 0.59s | PASS |
| VRAM recovered | Yes | No | FAIL |

## Detailed Results

### fashion-clip

**ERROR:** FashionCLIP requires transformers and torch. Install with: pip install transformers torch

### weather-classification

- Load time: 0.59s
- VRAM before: 20651MB
- VRAM after: 21095MB
- VRAM used: 444MB
- Inference time: 273.5ms
- Unload time: 0.00s
- VRAM final: 21075MB
- VRAM recovered: No

### pet-classifier

- Load time: 0.16s
- VRAM before: 21075MB
- VRAM after: 21077MB
- VRAM used: 2MB
- Unload time: 0.01s
- VRAM final: 20775MB
- VRAM recovered: No
