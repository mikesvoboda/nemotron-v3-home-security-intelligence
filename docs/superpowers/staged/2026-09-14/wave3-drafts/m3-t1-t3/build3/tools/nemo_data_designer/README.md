# NeMo Data Designer Integration

Generate synthetic security scenarios using [NVIDIA NeMo Data Designer](https://nvidia-nemo.github.io/DataDesigner/latest/) for improving testing coverage and Nemotron prompt quality evaluation.

## Overview

This tool generates structured synthetic data for testing the home security pipeline. It creates realistic security scenarios with:

- Object detections (persons, vehicles, animals)
- Enrichment context (zone info, baseline deviation)
- Ground truth risk assessments
- Narrative descriptions
- Expected Nemotron summaries

## Setup

### 1. Get NVIDIA API Key

1. Visit [build.nvidia.com](https://build.nvidia.com)
2. Create an account or sign in
3. Navigate to API Keys section
4. Generate a new API key

### 2. Set Environment Variable

```bash
export NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxx
```

Add to your shell profile (`.bashrc`, `.zshrc`) for persistence.

### 3. Install Dependencies

```bash
# Install NeMo Data Designer and dependencies
uv sync --group nemo
```

## Usage

### Preview Configuration

Preview the workflow configuration without generating data or using API credits:

```bash
uv run python tools/nemo_data_designer/generate_scenarios.py --preview
```

This displays:

- All column configurations
- Pydantic schemas
- Risk range mappings
- Output path

### Generate Scenarios

Generate scenarios and save to the default fixtures path:

```bash
# Generate 100 scenarios (default)
uv run python tools/nemo_data_designer/generate_scenarios.py --generate

# Generate specific number
uv run python tools/nemo_data_designer/generate_scenarios.py --generate --rows 500

# Custom output path
uv run python tools/nemo_data_designer/generate_scenarios.py --generate --rows 100 \
    --output /path/to/custom.parquet
```

## Column Reference

### Sampler Columns (Statistical Control)

| Column             | Values                                      | Purpose                     |
| ------------------ | ------------------------------------------- | --------------------------- |
| `time_of_day`      | morning, midday, evening, night, late_night | Time-based risk calibration |
| `day_type`         | weekday, weekend, holiday                   | Activity pattern variation  |
| `camera_location`  | front_door, backyard, driveway, side_gate   | Zone-based context          |
| `detection_count`  | 1, 2-3, 4-6, 7+                             | Batch complexity            |
| `primary_object`   | person, vehicle, animal, package            | Core detection types        |
| `scenario_type`    | normal, suspicious, threat, edge_case       | Ground truth classification |
| `enrichment_level` | none, basic, full                           | Context utilization level   |

### LLM-Structured Columns (Pydantic Validated)

| Column               | Type                        | Description                |
| -------------------- | --------------------------- | -------------------------- |
| `detections`         | `list[Detection]`           | YOLO26v2 detection objects |
| `enrichment_context` | `EnrichmentContext \| None` | Enrichment pipeline output |
| `ground_truth`       | `GroundTruth`               | Expected risk assessment   |

### LLM-Text Columns

| Column                 | Description                         |
| ---------------------- | ----------------------------------- |
| `scenario_narrative`   | Human-readable scenario description |
| `expected_summary`     | Expected Nemotron summary output    |
| `reasoning_key_points` | Key factors justifying risk score   |

## Pydantic Models

### Detection

```python
class Detection(BaseModel):
    object_type: Literal["person", "car", "truck", "dog", "cat", "bicycle", "motorcycle", "bus"]
    confidence: float  # 0.5-1.0
    bbox: tuple[int, int, int, int]  # x, y, width, height
    timestamp_offset_seconds: int  # 0-90 seconds
```

### EnrichmentContext

```python
class EnrichmentContext(BaseModel):
    zone_name: str | None
    is_entry_point: bool
    baseline_expected_count: int  # 0+
    baseline_deviation_score: float  # -3.0 to +3.0 (z-score)
    cross_camera_matches: int  # 0-5
```

### GroundTruth

```python
class GroundTruth(BaseModel):
    risk_range: tuple[int, int]  # (min, max) on 0-100 scale
    reasoning_key_points: list[str]
    expected_enrichment_models: list[str]
    should_trigger_alert: bool
```

## Ground Truth Risk Ranges

| Scenario Type | Risk Range | Alert  |
| ------------- | ---------- | ------ |
| normal        | 0-25       | No     |
| suspicious    | 30-55      | Yes    |
| threat        | 70-100     | Yes    |
| edge_case     | 20-60      | Varies |

## Output Format

Generated scenarios are saved as Apache Parquet files with all columns included. Load them in tests using:

```python
import pandas as pd
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "synthetic"
scenarios = pd.read_parquet(FIXTURES_DIR / "scenarios.parquet")

# Filter by scenario type
threats = scenarios[scenarios.scenario_type == "threat"]
```

## Integration with Tests

The generated fixtures are designed to work with pytest fixtures in `backend/tests/conftest.py`:

```python
@pytest.fixture(scope="session")
def synthetic_scenarios() -> pd.DataFrame:
    """Load pre-generated NeMo Data Designer scenarios."""
    return pd.read_parquet(SYNTHETIC_FIXTURES_DIR / "scenarios.parquet")

@pytest.fixture(scope="session")
def scenario_by_type(synthetic_scenarios):
    """Group scenarios for targeted testing."""
    return {
        "normal": synthetic_scenarios[synthetic_scenarios.scenario_type == "normal"],
        "suspicious": synthetic_scenarios[synthetic_scenarios.scenario_type == "suspicious"],
        "threat": synthetic_scenarios[synthetic_scenarios.scenario_type == "threat"],
        "edge_case": synthetic_scenarios[synthetic_scenarios.scenario_type == "edge_case"],
    }
```

## Cost Considerations

NeMo Data Designer uses NVIDIA API credits. Approximate costs:

- Preview mode: Free (no API calls)
- 100 scenarios: ~$0.50-1.00
- 1000 scenarios: ~$5-10

Use `--preview` first to verify configuration before generating.

## Troubleshooting

### "NVIDIA_API_KEY not set"

Set the environment variable:

```bash
export NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxx
```

### "data-designer package not installed"

Install the nemo dependency group:

```bash
uv sync --group nemo
```

### Rate limiting errors

NVIDIA API has rate limits. For large generations:

- Generate in batches of 100-200
- Add delays between batches
- Use off-peak hours

## Related Documentation

- [NeMo Data Designer Docs](https://nvidia-nemo.github.io/DataDesigner/latest/)
- [NeMo Data Designer GitHub](https://github.com/NVIDIA-NeMo/DataDesigner)
- [Design Document](../../docs/plans/2026-01-21-nemo-data-designer-integration-design.md)
