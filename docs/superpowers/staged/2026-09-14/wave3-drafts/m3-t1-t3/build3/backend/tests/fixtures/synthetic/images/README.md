# Multimodal Test Images

This directory contains curated test images for the multimodal evaluation pipeline.
Images are organized by category to validate the local YOLO26 + Nemotron pipeline
against NVIDIA vision models.

## Directory Structure

```
images/
  normal/        - Expected activity (family, delivery, pets)
  suspicious/    - Unusual but not threatening (unknown person lingering)
  threat/        - Security concerns (tampering, forced entry attempt)
  edge_case/     - Ambiguous situations (costumes, unusual lighting)
```

## Adding Test Images

### Guidelines

1. **Resolution**: Use images at least 640x480 pixels for reliable detection
2. **Format**: JPEG (.jpg) or PNG (.png) are preferred
3. **Naming**: Use descriptive names like `delivery_person_daytime.jpg`
4. **Privacy**: Never include real people without consent - use staged scenarios
5. **No real weapons**: Threat scenarios should use props or synthetic images

### Category Definitions

| Category      | Risk Range | Description                 |
| ------------- | ---------- | --------------------------- |
| `normal/`     | 0-25       | Expected daily activity     |
| `suspicious/` | 30-55      | Unusual but not threatening |
| `threat/`     | 70-100     | Clear security concern      |
| `edge_case/`  | 20-60      | Ambiguous situations        |

### Example Images Needed

**Normal (25 images)**

- Family member arriving home
- Package delivery person
- Pet in yard
- Mail carrier
- Gardener during business hours

**Suspicious (15 images)**

- Unknown person at door
- Vehicle idling in driveway
- Person looking in windows
- Late night visitor

**Threat (10 images)**

- Person attempting to force entry (staged)
- Person concealing face at night
- Tampering with lock (staged)
- Prowler behavior

**Edge Cases (15 images)**

- Halloween costumes
- Heavy rain/fog conditions
- Night with IR illumination
- Multiple people overlap
- Unusual angles

## Usage

Images in this directory are used by:

1. **Ground Truth Generation**: `MultimodalGroundTruthGenerator` analyzes images with NVIDIA vision
2. **Pipeline Evaluation**: Compare local detections against NVIDIA ground truth
3. **Integration Tests**: Validate detection accuracy and risk scoring

### Generate Ground Truth

```python
from tools.nemo_data_designer.multimodal import (
    NVIDIAVisionAnalyzer,
    MultimodalGroundTruthGenerator,
)
from pathlib import Path

async with NVIDIAVisionAnalyzer() as analyzer:
    generator = MultimodalGroundTruthGenerator(
        image_dir=Path("backend/tests/fixtures/synthetic/images"),
        analyzer=analyzer,
    )
    df = await generator.generate_ground_truth()
    generator.export_ground_truth(Path("multimodal_ground_truth.parquet"))
```

### Run Evaluation

```bash
# Run multimodal evaluation tests
uv run pytest backend/tests/integration/test_multimodal_pipeline.py -v

# Run full multimodal evaluation script
uv run python tools/nemo_data_designer/multimodal_evaluation.py
```

## Notes

- Images are NOT checked into git (add to `.gitignore` or use Git LFS for large files)
- For CI, tests run in mock mode without real images
- NVIDIA_API_KEY environment variable required for real API calls
- Generated ground truth is cached to avoid repeated API costs

## Related Documentation

- [NeMo Data Designer Integration Design](docs/plans/2026-01-21-nemo-data-designer-integration-design.md)
- [Multimodal Evaluation (Phase 6)](docs/plans/2026-01-21-nemo-data-designer-integration-design.md#multimodal-evaluation-phase-6)
