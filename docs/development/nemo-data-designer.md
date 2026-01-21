---
title: NeMo Data Designer Integration
source_refs:
  - docs/plans/2026-01-21-nemo-data-designer-integration-design.md
  - tools/nemo_data_designer/
  - backend/tests/fixtures/synthetic/
---

# NeMo Data Designer Integration

This document covers the integration of NVIDIA NeMo Data Designer for synthetic data generation to improve testing coverage and Nemotron prompt quality.

## Overview

[NeMo Data Designer](https://github.com/NVIDIA-NeMo/DataDesigner) is NVIDIA's synthetic data generation toolkit that enables:

- **Synthetic scenario generation** - Create diverse security scenarios with ground truth
- **LLM-as-Judge evaluation** - Quality assessment using rubric-based scoring
- **Embedding generation** - Semantic similarity for scenario clustering
- **Structured output validation** - Pydantic-validated detection payloads

### Why We Use It

| Problem                        | Solution                                    |
| ------------------------------ | ------------------------------------------- |
| Inconsistent risk scores       | Ground truth ranges for each scenario type  |
| Poor reasoning quality         | Expected key points for validation          |
| Context underutilization       | Enrichment-level controlled test scenarios  |
| No quantitative prompt ranking | Metrics-driven template comparison          |
| Edge case failures             | Systematic coverage of ambiguous situations |

## Prerequisites

### Required Software

- Python 3.11+ (matching project requirements)
- NVIDIA API key with access to Nemotron 49B

### Environment Variables

| Variable         | Description                  | Required |
| ---------------- | ---------------------------- | -------- |
| `NVIDIA_API_KEY` | API key for build.nvidia.com | Yes      |

### NVIDIA API Access

1. Create an account at [build.nvidia.com](https://build.nvidia.com)
2. Generate an API key with access to Nemotron models
3. Set the key in your environment or `.env` file:

```bash
export NVIDIA_API_KEY="nvapi-xxxx"  # pragma: allowlist secret
```

## Installation

Install the NeMo Data Designer dependencies using the optional `nemo` extra:

```bash
# Install with NeMo dependencies
uv sync --extra nemo

# Verify installation
uv run python -c "import data_designer; print('NeMo Data Designer installed')"
```

### Dependencies

The `nemo` extra installs (from `pyproject.toml`):

```toml
[project.optional-dependencies]
nemo = [
    "data-designer>=0.1.0",
    "pandas>=2.0.0",
    "pyarrow>=14.0.0",
    "numpy>=1.24.0",
]
```

## Configuration

### Model Aliases

The generation scripts use these NVIDIA API model endpoints:

| Model       | Alias          | Purpose                        |
| ----------- | -------------- | ------------------------------ |
| Nemotron-4  | `nemotron-49b` | Scenario generation, LLM-Judge |
| E5 Embedder | `nv-embed-v1`  | Semantic embeddings            |

### Generation Configuration

Configuration is defined in `tools/nemo_data_designer/config.py`:

```python
# Scenario type definitions
SCENARIO_TYPES = ["normal", "suspicious", "threat", "edge_case"]

# Ground truth risk ranges
RISK_RANGES = {
    "normal": (0, 25),
    "suspicious": (30, 55),
    "threat": (70, 100),
    "edge_case": (20, 60),
}
```

## Workflow

### 1. Generating Scenarios

Use the generation script to create synthetic security scenarios:

```bash
# Generate default scenario set (100 scenarios)
uv run python tools/nemo_data_designer/generate_scenarios.py

# Generate with custom count
uv run python tools/nemo_data_designer/generate_scenarios.py --count 500

# Generate specific scenario types
uv run python tools/nemo_data_designer/generate_scenarios.py --types threat,edge_case

# Output to custom location
uv run python tools/nemo_data_designer/generate_scenarios.py \
    --output backend/tests/fixtures/synthetic/scenarios.parquet
```

**Output files:**

| File                | Format  | Contents                        |
| ------------------- | ------- | ------------------------------- |
| `scenarios.parquet` | Parquet | All 24 columns of scenario data |
| `ground_truth.json` | JSON    | Risk ranges and key points      |
| `embeddings.npy`    | NumPy   | Pre-computed scenario vectors   |

### 2. Running Evaluations

The evaluation harness compares prompt templates against synthetic scenarios.

See the [Prompt Evaluation Results](prompt-evaluation-results.md) document for metrics tracking.

```bash
# Run full evaluation suite
uv run pytest backend/tests/integration/test_nemotron_prompts.py -v

# Run evaluation with specific template
uv run pytest backend/tests/integration/test_nemotron_prompts.py \
    -k "test_template_enriched" -v

# Generate evaluation report
uv run python backend/evaluation/reports.py --format html
```

### 3. CI Integration

The prompt evaluation runs as a nightly scheduled workflow.

See `.github/workflows/prompt-evaluation.yml` for the CI configuration:

```yaml
prompt-evaluation:
  runs-on: ubuntu-latest
  if: github.event_name == 'schedule' # Nightly only
  steps:
    - uses: actions/checkout@v4
    - name: Run prompt evaluation suite
      run: |
        uv run pytest backend/tests/integration/test_nemotron_prompts.py \
          --tb=short -v --json-report
    - name: Upload evaluation report
      uses: actions/upload-artifact@v4
      with:
        name: prompt-evaluation-report
        path: reports/prompt_evaluation.json
```

## Column Documentation

The synthetic scenario dataset contains 24 columns organized into 7 categories.

### Sampler Columns (7)

Statistical control variables for balanced scenario generation:

| Column             | Type   | Values                                      | Purpose                     |
| ------------------ | ------ | ------------------------------------------- | --------------------------- |
| `time_of_day`      | string | morning, midday, evening, night, late_night | Time-based risk calibration |
| `day_type`         | string | weekday, weekend, holiday                   | Baseline deviation testing  |
| `camera_location`  | string | front_door, backyard, driveway, side_gate   | Zone-based context          |
| `detection_count`  | string | 1, 2-3, 4-6, 7+                             | Batch complexity testing    |
| `primary_object`   | string | person, vehicle, animal, package            | Core detection types        |
| `scenario_type`    | string | normal, suspicious, threat, edge_case       | Ground truth classification |
| `enrichment_level` | string | none, basic, full                           | Context utilization testing |

### LLM-Structured Columns (3)

Pydantic-validated structured output:

| Column               | Type              | Schema                              | Purpose                    |
| -------------------- | ----------------- | ----------------------------------- | -------------------------- |
| `detections`         | list[Detection]   | object_type, confidence, bbox, time | Detection payload          |
| `enrichment_context` | EnrichmentContext | zone, baseline, cross-camera        | Pipeline enrichment data   |
| `ground_truth`       | GroundTruth       | risk_range, key_points, models      | Expected output validation |

### LLM-Text Columns (3)

Narrative text generation:

| Column                 | Type   | Purpose                                |
| ---------------------- | ------ | -------------------------------------- |
| `scenario_narrative`   | string | Human-readable scenario description    |
| `expected_summary`     | string | Expected Nemotron summary output       |
| `reasoning_key_points` | string | Comma-separated reasoning expectations |

### LLM-Judge Columns (6)

Quality rubrics scored 1-4:

| Column                  | Scale | Evaluates                                   |
| ----------------------- | ----- | ------------------------------------------- |
| `relevance`             | 1-4   | Does output address the security concern?   |
| `risk_calibration`      | 1-4   | Is score appropriate for scenario severity? |
| `context_usage`         | 1-4   | Are enrichment inputs in reasoning?         |
| `reasoning_quality`     | 1-4   | Is the explanation logical and complete?    |
| `threat_identification` | 1-4   | Did it correctly identify the threat?       |
| `actionability`         | 1-4   | Is output useful for homeowner action?      |

### Embedding Columns (2)

Pre-computed vector representations:

| Column                | Type        | Purpose                      |
| --------------------- | ----------- | ---------------------------- |
| `scenario_embedding`  | vector[768] | Scenario semantic similarity |
| `reasoning_embedding` | vector[768] | Reasoning comparison vectors |

### Expression Columns (3)

Derived/computed fields:

| Column                   | Type   | Purpose                             |
| ------------------------ | ------ | ----------------------------------- |
| `formatted_prompt_input` | string | Pre-rendered input for templates    |
| `complexity_score`       | float  | Computed scenario difficulty        |
| `scenario_hash`          | string | Unique identifier for deduplication |

### Validation Columns (2)

Quality gate flags:

| Column                   | Type | Purpose                      |
| ------------------------ | ---- | ---------------------------- |
| `detection_schema_valid` | bool | Pydantic validation passed   |
| `temporal_consistency`   | bool | Timestamps within 90s window |

## Pydantic Models

The structured columns use these Pydantic models for validation:

```python
from pydantic import BaseModel, Field
from typing import Literal

class Detection(BaseModel):
    """Single object detection within a batch."""
    object_type: Literal["person", "car", "truck", "dog", "cat", "bicycle"]
    confidence: float = Field(ge=0.5, le=1.0)
    bbox: tuple[int, int, int, int]  # x, y, width, height
    timestamp_offset_seconds: int = Field(ge=0, le=90)

class EnrichmentContext(BaseModel):
    """Pipeline enrichment data for a detection batch."""
    zone_name: str | None
    is_entry_point: bool
    baseline_expected_count: int
    baseline_deviation_score: float = Field(ge=-3.0, le=3.0)
    cross_camera_matches: int = Field(ge=0, le=5)

class GroundTruth(BaseModel):
    """Expected evaluation outputs for a scenario."""
    risk_range: tuple[int, int]
    reasoning_key_points: list[str]
    expected_enrichment_models: list[str]
    should_trigger_alert: bool
```

## File Structure

```
tools/
└── nemo_data_designer/           # Generation scripts
    ├── __init__.py
    ├── config.py                 # Column definitions, Pydantic models
    ├── generate_scenarios.py     # Main generation script
    ├── multimodal/               # Image-based evaluation
    │   ├── __init__.py
    │   ├── image_analyzer.py     # NVIDIA vision API wrapper
    │   ├── ground_truth_generator.py
    │   └── pipeline_comparator.py
    ├── notebooks/
    │   ├── 01_scenario_generation.ipynb
    │   ├── 02_evaluation_analysis.ipynb
    │   └── 03_multimodal_evaluation.ipynb
    └── README.md

backend/
├── tests/
│   ├── fixtures/
│   │   └── synthetic/            # Generated fixtures
│   │       ├── scenarios.parquet
│   │       ├── ground_truth.json
│   │       ├── embeddings.npy
│   │       └── images/           # Multimodal test images
│   │           ├── normal/
│   │           ├── suspicious/
│   │           ├── threat/
│   │           └── edge_case/
│   │
│   ├── integration/
│   │   ├── test_nemotron_prompts.py    # Prompt evaluation tests
│   │   └── test_multimodal_pipeline.py # Vision comparison tests
│   │
│   └── conftest.py               # Fixture loaders
│
└── evaluation/                   # Evaluation tooling
    ├── __init__.py
    ├── harness.py                # Prompt evaluation runner
    ├── metrics.py                # Score calculation
    └── reports.py                # Report generation
```

## Troubleshooting

### "NVIDIA API key not found"

**Cause:** The `NVIDIA_API_KEY` environment variable is not set.

**Solution:**

```bash
# Set in current shell
export NVIDIA_API_KEY="nvapi-xxxx"  # pragma: allowlist secret

# Or add to .env file
echo 'NVIDIA_API_KEY="nvapi-xxxx"' >> .env  # pragma: allowlist secret
```

### "Rate limit exceeded"

**Cause:** Too many API requests in a short period.

**Solution:**

- Reduce `--count` parameter for generation
- Add delays between batch generations
- Use cached fixtures when possible

### "Pydantic validation failed"

**Cause:** Generated detection data doesn't match schema constraints.

**Solution:**

- Check the generation config for constraint ranges
- Review `config.py` Pydantic model definitions
- Re-run generation with `--validate-only` to see failures

### "Fixtures not found"

**Cause:** Synthetic fixtures haven't been generated yet.

**Solution:**

```bash
# Generate fixtures
uv run python tools/nemo_data_designer/generate_scenarios.py

# Verify output location
ls backend/tests/fixtures/synthetic/
```

### "Import error: data_designer"

**Cause:** NeMo dependencies not installed.

**Solution:**

```bash
# Install with nemo extra
uv sync --extra nemo

# Verify installation
uv run pip show data-designer
```

## Related Documentation

- [Design Document](../plans/2026-01-21-nemo-data-designer-integration-design.md) - Full integration design
- [Prompt Evaluation Results](prompt-evaluation-results.md) - Metrics tracking template
- [Testing Guide](testing.md) - General test infrastructure
- [Testing Workflow](testing-workflow.md) - TDD practices
