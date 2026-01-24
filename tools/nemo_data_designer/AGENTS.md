# NeMo Data Designer Integration

## Purpose

Generate synthetic security scenarios using [NVIDIA NeMo Data Designer](https://nvidia-nemo.github.io/DataDesigner/latest/) for improving testing coverage and Nemotron prompt quality evaluation. This tool creates realistic test data for the home security pipeline including object detections, enrichment context, ground truth risk assessments, and expected model outputs.

## Directory Contents

```
tools/nemo_data_designer/
├── AGENTS.md                  # This file
├── README.md                  # Setup guide and usage documentation
├── __init__.py                # Package exports (Detection, EnrichmentContext, etc.)
├── config.py                  # Pydantic models and column configurations
├── generate_scenarios.py      # Main CLI for scenario generation
├── analyze_coverage.py        # Coverage analysis and gap detection
├── enrichment_scenarios.py    # Edge case scenario generators
├── multimodal_evaluation.py   # Multimodal pipeline evaluation runner
├── multimodal/                # Multimodal evaluation subpackage
│   ├── AGENTS.md              # Multimodal subpackage documentation
│   ├── __init__.py            # Subpackage exports
│   ├── image_analyzer.py      # NVIDIA Vision API client
│   ├── ground_truth_generator.py  # Ground truth from curated images
│   └── pipeline_comparator.py # Local vs NVIDIA comparison
└── notebooks/                 # Jupyter notebooks (empty placeholder)
```

## Key Files

### `config.py` (Pydantic Models and Configuration)

Defines the schema for synthetic security scenarios with 24 columns across 7 categories.

**Core Models:**

| Model               | Purpose                              |
| ------------------- | ------------------------------------ |
| `Detection`         | Single RT-DETRv2 detection with bbox |
| `EnrichmentContext` | Zone info, baseline deviation        |
| `GroundTruth`       | Expected risk range and reasoning    |
| `JudgeScores`       | LLM-Judge rubric scores (6 dims)     |
| `ScenarioBundle`    | Complete scenario combining all      |

**Column Types (24 total):**

| Category       | Count | Purpose                                    |
| -------------- | ----- | ------------------------------------------ |
| Samplers       | 7     | Statistical control (time, location, type) |
| LLM-Structured | 3     | Pydantic-validated generation              |
| LLM-Text       | 3     | Narrative generation                       |
| LLM-Judge      | 6     | Quality rubric scores                      |
| Embedding      | 2     | Semantic search vectors                    |
| Expression     | 3     | Derived fields (hash, complexity)          |
| Validation     | 2     | Schema and temporal checks                 |

**Helper Functions:**

- `calculate_complexity_score()` - Scenario complexity (0.0-1.0)
- `generate_scenario_hash()` - SHA-256 deduplication hash
- `validate_detection_schema()` - Schema validation
- `validate_temporal_consistency()` - Timestamp validation
- `format_prompt_input()` - Pre-render for Nemotron
- `generate_default_judge_scores()` - Default LLM-Judge values

### `generate_scenarios.py` (Main CLI)

CLI tool for generating synthetic scenarios using NVIDIA NeMo Data Designer API or local dry-run mode.

**Usage:**

```bash
# Preview configuration (no API calls)
uv run python tools/nemo_data_designer/generate_scenarios.py --preview

# Generate 100 scenarios (requires NVIDIA_API_KEY)
uv run python tools/nemo_data_designer/generate_scenarios.py --generate --rows 100

# Dry run (local generation, no API)
uv run python tools/nemo_data_designer/generate_scenarios.py \
    --generate --rows 1500 --full-columns --dry-run

# Full generation with embeddings
uv run python tools/nemo_data_designer/generate_scenarios.py \
    --generate --rows 1500 --full-columns --embeddings \
    --output backend/tests/fixtures/synthetic/
```

**Output Files (with `--full-columns`):**

- `scenarios.parquet` - Main scenario data
- `ground_truth.json` - Expected risk assessments
- `coverage_report.json` - Column coverage analysis
- `embeddings.npz` - Semantic embeddings (if `--embeddings`)

### `analyze_coverage.py` (Coverage Analysis)

Analyzes generated scenarios for coverage gaps and distribution issues.

**Usage:**

```bash
# Analyze default scenarios
uv run python tools/nemo_data_designer/analyze_coverage.py

# Analyze with detailed output
uv run python tools/nemo_data_designer/analyze_coverage.py --detailed

# Export analysis to JSON
uv run python tools/nemo_data_designer/analyze_coverage.py --output report.json
```

**Metrics Analyzed:**

- Sampler column coverage and distribution
- Cross-tabulation coverage (scenario_type x enrichment_level)
- Validation quality (schema, temporal consistency)
- Complexity distribution
- LLM-Judge score distribution
- Embedding coverage

### `enrichment_scenarios.py` (Edge Case Generators)

Generates targeted edge case scenarios for testing enrichment pipeline behavior.

**Scenario Types:**

| Generator                                  | Count | Purpose                       |
| ------------------------------------------ | ----- | ----------------------------- |
| `generate_multi_threat_scenarios()`        | 20    | Multiple weapons, persons     |
| `generate_rare_pose_scenarios()`           | 20    | Crouching, climbing, crawling |
| `generate_boundary_confidence_scenarios()` | 20    | Decision threshold testing    |
| `generate_ocr_failure_scenarios()`         | 20    | Blurry plates, poor lighting  |
| `generate_vram_stress_scenarios()`         | 10    | Maximum model concurrency     |

**Export Function:**

```python
from tools.nemo_data_designer.enrichment_scenarios import export_enrichment_scenarios
from pathlib import Path

export_enrichment_scenarios(Path("backend/tests/fixtures/synthetic/enrichment"))
```

### `multimodal_evaluation.py` (Pipeline Evaluation Runner)

Orchestrates the full multimodal evaluation pipeline comparing local RT-DETRv2 + Nemotron against NVIDIA vision ground truth.

**Usage:**

```bash
# Preview what would be done
uv run python tools/nemo_data_designer/multimodal_evaluation.py --preview

# Run evaluation (mock mode)
uv run python tools/nemo_data_designer/multimodal_evaluation.py --run --mock

# Run with NVIDIA API
uv run python tools/nemo_data_designer/multimodal_evaluation.py --run

# Force regenerate ground truth
uv run python tools/nemo_data_designer/multimodal_evaluation.py --run --regenerate-ground-truth
```

**Output Files:**

- `multimodal_ground_truth.parquet` - NVIDIA vision analysis
- `local_pipeline_results.parquet` - Local pipeline output
- `comparison_report.json` - Detailed comparison metrics
- `comparison_summary.txt` - Human-readable summary

## Environment Variables

| Variable         | Required | Description                   |
| ---------------- | -------- | ----------------------------- |
| `NVIDIA_API_KEY` | Yes\*    | API key from build.nvidia.com |

\*Not required when using `--dry-run` or `--mock` modes.

## Ground Truth Risk Ranges

| Scenario Type | Risk Range | Alert  |
| ------------- | ---------- | ------ |
| normal        | 0-25       | No     |
| suspicious    | 30-55      | Yes    |
| threat        | 70-100     | Yes    |
| edge_case     | 20-60      | Varies |

## Integration with Tests

Generated scenarios integrate with pytest fixtures:

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

## Setup

```bash
# Install NeMo Data Designer dependencies
uv sync --group nemo

# Set API key
export NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxx

# Verify setup
uv run python tools/nemo_data_designer/generate_scenarios.py --preview
```

## Cost Considerations

NeMo Data Designer uses NVIDIA API credits:

- Preview mode: Free (no API calls)
- 100 scenarios: ~$0.50-1.00
- 1000 scenarios: ~$5-10

Use `--preview` first to verify configuration before generating.

## Entry Points

1. **CLI generation**: `generate_scenarios.py:main()` - Scenario generation
2. **Coverage analysis**: `analyze_coverage.py:main()` - Gap detection
3. **Multimodal eval**: `multimodal_evaluation.py:main()` - Pipeline comparison
4. **Edge cases**: `enrichment_scenarios.py:export_enrichment_scenarios()` - Edge case export
5. **Config models**: `config.py` - Pydantic models and constants
6. **Multimodal pipeline**: `multimodal/` - NVIDIA vision ground truth generation

## Related Documentation

- [NeMo Data Designer Docs](https://nvidia-nemo.github.io/DataDesigner/latest/)
- [Design Document](../../docs/plans/2026-01-21-nemo-data-designer-integration-design.md)
- [Testing Guide](../../docs/development/testing.md)
