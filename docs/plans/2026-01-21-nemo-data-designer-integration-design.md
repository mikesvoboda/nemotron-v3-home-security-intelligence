# NeMo Data Designer Integration Design

**Date:** 2026-01-21
**Status:** Draft
**Author:** AI-assisted design session

## Overview

Integration of NVIDIA NeMo Data Designer to improve testing coverage and Nemotron prompt quality through synthetic data generation and systematic evaluation.

## Goals

1. **Improve testing coverage** across all layers (baseline/anomaly, enrichment pipeline, batch aggregation, end-to-end integration)
2. **Improve Nemotron prompts** by addressing:
   - Inconsistent risk scores
   - Poor reasoning quality
   - Context underutilization
   - No quantitative template comparison
   - Edge case failures
3. **Validate full pipeline** through multimodal evaluation against NVIDIA vision models

## Non-Goals

- Production runtime integration (developer-only tooling)
- Replacing real camera feeds during development
- Fine-tuning production Nemotron on synthetic data

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Development Workflow                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐      ┌──────────────────┐                 │
│  │ NeMo Data        │      │ NVIDIA API       │                 │
│  │ Designer         │─────▶│ (Nemotron 49B)   │                 │
│  │ (Generation)     │      │ (Generation +    │                 │
│  └────────┬─────────┘      │  LLM-as-Judge)   │                 │
│           │                └──────────────────┘                 │
│           ▼                                                      │
│  ┌──────────────────┐                                           │
│  │ Synthetic        │  Versioned fixtures checked into repo     │
│  │ Scenario         │  - scenarios.parquet                      │
│  │ Fixtures         │  - ground_truth_scores.json               │
│  └────────┬─────────┘  - evaluation_rubrics.yaml                │
│           │                                                      │
├───────────┼─────────────────────────────────────────────────────┤
│           │            CI / Test Workflow                        │
│           ▼                                                      │
│  ┌──────────────────┐      ┌──────────────────┐                 │
│  │ Prompt           │      │ Local Nemotron   │                 │
│  │ Evaluation       │─────▶│ (Your 5          │                 │
│  │ Harness          │      │  Templates)      │                 │
│  └────────┬─────────┘      └──────────────────┘                 │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                           │
│  │ Comparison       │  Compare outputs against ground truth     │
│  │ Reports          │  - Risk score deviation                   │
│  └──────────────────┘  - Reasoning quality metrics              │
│                        - Template performance rankings           │
└─────────────────────────────────────────────────────────────────┘
```

## Scenario Taxonomy

### Sampler Columns (Statistical Control)

| Column             | Values                                      | Purpose                          |
| ------------------ | ------------------------------------------- | -------------------------------- |
| `time_of_day`      | morning, midday, evening, night, late_night | Test time-based risk calibration |
| `day_type`         | weekday, weekend, holiday                   | Baseline deviation testing       |
| `camera_location`  | front_door, backyard, driveway, side_gate   | Zone-based context               |
| `detection_count`  | 1, 2-3, 4-6, 7+                             | Batch complexity                 |
| `primary_object`   | person, vehicle, animal, package            | Core detection types             |
| `scenario_type`    | normal, suspicious, threat, edge_case       | Ground truth classification      |
| `enrichment_level` | none, basic, full                           | Context utilization testing      |

### Scenario Type Definitions

- **normal** - Expected activity (family arriving, delivery, pets)
- **suspicious** - Unusual but not threatening (unknown person lingering, vehicle idling)
- **threat** - Clear security concern (weapon detected, forced entry attempt, prowler)
- **edge_case** - Ambiguous situations (contractor at odd hours, costume, wildlife)

### Ground Truth Risk Ranges

| Scenario Type | Risk Range | Risk Level    |
| ------------- | ---------- | ------------- |
| normal        | 0-25       | low           |
| suspicious    | 30-55      | medium        |
| threat        | 70-100     | high/critical |
| edge_case     | 20-60      | varies        |

## Column Inventory

### Complete Column Structure (24 columns across 7 types)

```yaml
# SAMPLERS (7) - Statistical control
- time_of_day: [morning, midday, evening, night, late_night]
- day_type: [weekday, weekend, holiday]
- camera_location: [front_door, backyard, driveway, side_gate]
- detection_count: [1, 2-3, 4-6, 7+]
- primary_object: [person, vehicle, animal, package]
- scenario_type: [normal, suspicious, threat, edge_case]
- enrichment_level: [none, basic, full]

# LLM-STRUCTURED (3) - Pydantic-validated generation
- detections: list[Detection]
- enrichment_context: EnrichmentContext | None
- ground_truth: GroundTruth # risk_range, reasoning, expected_models

# LLM-TEXT (3) - Narrative generation
- scenario_narrative: str
- expected_summary: str
- reasoning_key_points: str

# LLM-JUDGE (6) - Quality rubrics
- relevance: 1-4
- risk_calibration: 1-4
- context_usage: 1-4
- reasoning_quality: 1-4
- threat_identification: 1-4
- actionability: 1-4

# EMBEDDING (2) - Semantic search
- scenario_embedding: vector[768]
- reasoning_embedding: vector[768]

# EXPRESSION (3) - Derived fields
- formatted_prompt_input: str # Pre-rendered for each template
- complexity_score: float
- scenario_hash: str

# VALIDATION (2) - Quality gates
- detection_schema_valid: bool
- temporal_consistency: bool
```

### Pydantic Models

```python
from pydantic import BaseModel, Field
from typing import Literal

class Detection(BaseModel):
    object_type: Literal["person", "car", "truck", "dog", "cat", "bicycle"]
    confidence: float = Field(ge=0.5, le=1.0)
    bbox: tuple[int, int, int, int]  # x, y, width, height
    timestamp_offset_seconds: int = Field(ge=0, le=90)

class EnrichmentContext(BaseModel):
    zone_name: str | None
    is_entry_point: bool
    baseline_expected_count: int
    baseline_deviation_score: float = Field(ge=-3.0, le=3.0)
    cross_camera_matches: int = Field(ge=0, le=5)

class GroundTruth(BaseModel):
    risk_range: tuple[int, int]
    reasoning_key_points: list[str]
    expected_enrichment_models: list[str]
    should_trigger_alert: bool
```

## Evaluation Harness

### Workflow

```
1. LOAD FIXTURES
   scenarios.parquet → DataFrame with all columns

2. FOR EACH PROMPT TEMPLATE (5 templates)
   ├─ Render prompt using formatted_prompt_input
   ├─ Call local Nemotron → get risk_score, reasoning
   └─ Store in results DataFrame

3. COMPUTE METRICS
   ├─ Risk score deviation from ground_truth range
   ├─ Reasoning similarity to expected_summary (cosine)
   ├─ Key point coverage (reasoning_key_points)
   └─ Aggregate by scenario_type, enrichment_level

4. GENERATE REPORTS
   ├─ Template ranking by overall score
   ├─ Failure cases (score outside ground_truth range)
   ├─ Context utilization gaps
   └─ Edge case performance breakdown
```

### LLM-Judge Rubrics

| Dimension               | Scale | Evaluates                                         |
| ----------------------- | ----- | ------------------------------------------------- |
| `relevance`             | 1-4   | Does output address the actual security concern?  |
| `risk_calibration`      | 1-4   | Is score appropriate for scenario severity?       |
| `context_usage`         | 1-4   | Are enrichment inputs reflected in reasoning?     |
| `reasoning_quality`     | 1-4   | Is the explanation logical and complete?          |
| `threat_identification` | 1-4   | Did it correctly identify/miss the actual threat? |
| `actionability`         | 1-4   | Is the output useful for a homeowner to act on?   |

## File Structure

```
backend/
├── tests/
│   ├── fixtures/
│   │   └── synthetic/                    # Generated fixtures
│   │       ├── scenarios.parquet         # Main scenario dataset
│   │       ├── ground_truth.json         # Risk ranges, key points
│   │       ├── embeddings.npy            # Pre-computed vectors
│   │       ├── images/                   # Multimodal test images
│   │       │   ├── normal/
│   │       │   ├── suspicious/
│   │       │   ├── threat/
│   │       │   └── edge_case/
│   │       └── multimodal_ground_truth.parquet
│   │
│   ├── integration/
│   │   ├── test_nemotron_prompts.py      # Prompt evaluation tests
│   │   └── test_multimodal_pipeline.py   # Vision comparison tests
│   │
│   └── conftest.py                       # Fixture loaders
│
├── evaluation/                           # Evaluation tooling
│   ├── __init__.py
│   ├── harness.py                        # Prompt evaluation runner
│   ├── metrics.py                        # Score calculation, comparisons
│   └── reports.py                        # Report generation (JSON, HTML)

tools/
└── nemo_data_designer/                   # Generation scripts
    ├── __init__.py
    ├── config.py                         # Column definitions, Pydantic models
    ├── generate_scenarios.py             # Main generation script
    ├── multimodal/
    │   ├── __init__.py
    │   ├── image_analyzer.py             # NVIDIA vision API wrapper
    │   ├── ground_truth_generator.py     # Generate GT from images
    │   └── pipeline_comparator.py        # Compare local vs NVIDIA outputs
    ├── notebooks/
    │   ├── 01_scenario_generation.ipynb
    │   ├── 02_evaluation_analysis.ipynb
    │   └── 03_multimodal_evaluation.ipynb
    └── README.md
```

## Testing Integration

### Pytest Fixtures

```python
# backend/tests/conftest.py additions

import pandas as pd
import pytest
from pathlib import Path

SYNTHETIC_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "synthetic"

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

### Test Patterns

```python
# backend/tests/integration/test_nemotron_prompts.py

@pytest.mark.parametrize("template", PROMPT_TEMPLATES)
def test_risk_score_within_ground_truth_range(template, scenario_by_type):
    """Each template should produce scores within expected ranges."""
    for scenario in scenario_by_type["threat"].itertuples():
        result = evaluate_prompt(template, scenario.formatted_prompt_input)
        min_score, max_score = scenario.ground_truth_risk_range
        assert min_score <= result.risk_score <= max_score

def test_enrichment_context_reflected_in_reasoning(synthetic_scenarios):
    """Full enrichment scenarios should reference context in reasoning."""
    full_enrichment = synthetic_scenarios[
        synthetic_scenarios.enrichment_level == "full"
    ]
    for scenario in full_enrichment.itertuples():
        result = evaluate_prompt(ENRICHED_TEMPLATE, scenario.formatted_prompt_input)
        for key_point in scenario.reasoning_key_points:
            assert key_point.lower() in result.reasoning.lower()
```

### CI Integration

```yaml
# .github/workflows/prompt-evaluation.yml
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

## Multimodal Evaluation (Phase 6)

### Pipeline

```
Sample Images (from curated test set)
        │
        ├──────────────────┬───────────────────────┐
        ▼                  ▼                       ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ NVIDIA API      │  │ Your Pipeline   │  │                 │
│ (Vision Model)  │  │ YOLO26 +     │  │   Compare       │
│                 │  │ Florence-2 +    │  │   Outputs       │
│ Ground Truth    │  │ Enrichment      │  │                 │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│ Comparison Metrics:                                         │
│ • Detection accuracy (did YOLO26 find what NVIDIA saw?) │
│ • Enrichment quality (Florence-2 vs NVIDIA vision desc)    │
│ • End-to-end risk score alignment                          │
└─────────────────────────────────────────────────────────────┘
```

### Additional Columns

| Column                      | Type           | Purpose                             |
| --------------------------- | -------------- | ----------------------------------- |
| `image_path`                | Seed           | Reference to test image             |
| `nvidia_vision_description` | LLM-Structured | What NVIDIA's vision model sees     |
| `nvidia_detected_objects`   | LLM-Structured | Objects with bounding boxes         |
| `nvidia_risk_assessment`    | LLM-Structured | Full risk analysis from image       |
| `vision_alignment_score`    | LLM-Judge      | How well does local pipeline match? |

### Image Curation

| Category          | Count | Source                                 |
| ----------------- | ----- | -------------------------------------- |
| Normal activity   | 25    | Stock footage, staged captures         |
| Suspicious        | 15    | Staged scenarios                       |
| Threat simulation | 10    | Controlled/synthetic (no real weapons) |
| Edge cases        | 15    | Weather, lighting, occlusion, costumes |
| **Total**         | 65    | Curated test set                       |

## Implementation Phases

| Phase                        | Scope                         | Deliverables                                        | Effort   |
| ---------------------------- | ----------------------------- | --------------------------------------------------- | -------- |
| **1. Foundation**            | NeMo setup + basic generation | `tools/nemo_data_designer/`, initial 100 scenarios  | 3-4 days |
| **2. Evaluation Harness**    | Metrics + comparison engine   | `backend/evaluation/`, prompt comparison reports    | 2-3 days |
| **3. Testing Integration**   | Pytest + CI                   | `test_nemotron_prompts.py`, GitHub Actions workflow | 2 days   |
| **4. Full Coverage**         | Scenario expansion            | 1,500+ scenarios, embeddings, coverage analysis     | 3-4 days |
| **5. Enrichment Pipeline**   | Model zoo edge cases          | Circuit breaker tests, VRAM eviction scenarios      | 2-3 days |
| **6. Multimodal Evaluation** | Image-based ground truth      | Vision comparison pipeline, image test fixtures     | 4-5 days |

**Total estimated effort:** 16-21 days

## Dependencies

### Python Packages (dev dependencies)

```toml
[project.optional-dependencies]
nemo = [
    "data-designer>=0.1.0",
    "pandas>=2.0.0",
    "pyarrow>=14.0.0",
    "numpy>=1.24.0",
]
```

### External Services

- NVIDIA API key (`NVIDIA_API_KEY` environment variable)
- Access to Nemotron 49B via build.nvidia.com

## Success Criteria

1. **Prompt template ranking** - Quantitative comparison showing best-performing template
2. **Risk score consistency** - <15 point deviation from ground truth for 90%+ scenarios
3. **Context utilization** - Full enrichment scenarios score 3+ on context_usage rubric
4. **Edge case coverage** - All 4 scenario types have dedicated test fixtures
5. **Multimodal alignment** - Local pipeline achieves 70%+ IoU with NVIDIA vision detection

## Open Questions

1. Should we version fixtures in Git LFS or generate on-demand?
2. What's the budget for NVIDIA API usage during generation?
3. How often should we regenerate fixtures (quarterly, on prompt changes)?

## References

- [NeMo Data Designer GitHub](https://github.com/NVIDIA-NeMo/DataDesigner)
- [NeMo Data Designer Documentation](https://nvidia-nemo.github.io/DataDesigner/latest/)
- [Nemotron Personas on HuggingFace](https://huggingface.co/collections/nvidia/nemotron-personas)
- [NVIDIA GenerativeAIExamples](https://github.com/NVIDIA/GenerativeAIExamples/tree/main/nemo/NeMo-Data-Designer)
