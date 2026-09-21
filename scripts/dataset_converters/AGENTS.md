# Dataset Converters - Agent Guide

## Purpose

Converters that transform external public datasets (COCO, FLIR, CCPD, Kinetics-700, ShanghaiTech) into the `expected_labels.json` scenario format consumed by the AI evaluation pipeline. Each converter is a standalone CLI that reads raw data under `data/external/<dataset>/raw` and writes `data/external/<dataset>/converted`.

## Key Files

| File                        | Purpose                                                              |
| --------------------------- | -------------------------------------------------------------------- |
| `__init__.py`               | Shared base: `DatasetConverter` ABC, `ConvertedSample` dataclass, `RISK_MAPPINGS` (action/label → category + score band + risk level), `get_risk_mapping()` |
| `coco_converter.py`         | COCO detection annotations (val2017/train2017 JSON) → labeled samples |
| `flir_converter.py`         | FLIR ADAS thermal imagery + COCO-style JSON annotations              |
| `ccpd_converter.py`         | CCPD license-plate images (metadata encoded in filenames)            |
| `kinetics_converter.py`     | Kinetics-700 action CSVs → risk-mapped scenario labels               |
| `shanghaitech_converter.py` | ShanghaiTech anomaly surveillance (MATLAB ground-truth files)        |

## Usage

```bash
uv run scripts/dataset_converters/coco_converter.py \
    --input data/external/coco/raw --output data/external/coco/converted
```

Run any converter with `--help` for dataset-specific flags (e.g. `--split` for COCO).

## Patterns

- **Subclass `DatasetConverter`** in `__init__.py` and implement `convert()`; reuse `to_expected_labels()` for output formatting instead of hand-rolling JSON.
- **Risk scoring is centralized** in `RISK_MAPPINGS` (`__init__.py`) — add new action/label mappings there, not inside individual converters.
- **Raw data is not in git** — `data/external/*/raw` must be downloaded first (see `scripts/download_open_datasets.py`).
