# Synthetic Data Quality and Prompt-Image Alignment

This document explains the limitations of AI-generated synthetic test images and provides guidance for creating valid test data for the Home Security Intelligence pipeline.

## Problem Summary

AI image generation models (Gemini, Veo, DALL-E, Stable Diffusion, etc.) are trained with content policies that prevent them from generating certain types of content. This causes a **prompt-image misalignment** where the generated images do not match the generation prompts.

**Example:**

- **Prompt:** "Person approaching property with handgun visible in hand, aggressive posture"
- **Actual Image:** Person in hoodie standing on porch, NO WEAPON VISIBLE

This misalignment means:

1. We cannot validate weapon detection capabilities using AI-generated images
2. Risk scores may appear miscalibrated because expected threats are not in the images
3. Tests may give false confidence in threat detection accuracy

## Content Policy Restrictions

AI image generators typically refuse to generate:

| Category             | Restricted Elements                             | Impact                             |
| -------------------- | ----------------------------------------------- | ---------------------------------- |
| **Weapons**          | Handguns, rifles, knives, crowbars, bats        | Cannot test weapon detection       |
| **Violence**         | Aggressive poses, threatening behavior, attacks | Cannot test violence detection     |
| **Crime**            | Break-ins, theft, burglary in progress          | Criminal actions sanitized         |
| **Face Concealment** | Masks, balaclavas, hoods covering faces         | May generate visible faces instead |

## Scenario Alignment Status

### Suitable for AI Generation (2 scenarios)

These scenarios should produce reasonably accurate AI-generated images:

- **vehicle_parking** - Normal vehicle activity
- **casing** - Observing property from distance (no obvious criminal behavior)

### Require Alternative Data Sources (11 scenarios)

These scenarios have known prompt-image misalignment issues:

#### High Risk (weapons/violence)

| Scenario           | Issues                         | Recommendation                 |
| ------------------ | ------------------------------ | ------------------------------ |
| `weapon_visible`   | Weapons NOT generated          | Use real test footage or stock |
| `break_in_attempt` | Tools, forcing entry not shown | Use staged footage             |
| `vandalism`        | Weapons, breaking not shown    | Use stock footage              |

#### Medium Risk (crime/concealment)

| Scenario        | Issues                        | Recommendation              |
| --------------- | ----------------------------- | --------------------------- |
| `package_theft` | Theft action unclear          | Use stock footage           |
| `prowling`      | Masks not rendered            | Use winter clothing footage |
| `loitering`     | Hood may be down              | Acceptable proxy            |
| `tailgating`    | Aggressive behavior sanitized | Use staged footage          |

## Validation Script

Run the validation script to audit all scenarios:

```bash
# Audit all scenario templates for content policy restrictions
uv run scripts/validate_synthetic_quality.py audit

# Validate a specific generation run
uv run scripts/validate_synthetic_quality.py validate --run-id 20260125_143022

# Generate summary report
uv run scripts/validate_synthetic_quality.py report
```

Output is saved to:

- `data/synthetic/validation_report.json` - Detailed validation results
- `data/synthetic/scenario_alignment_status.json` - Per-scenario status

## Recommended Approaches

### 1. Use Stock Footage for Threat Scenarios

```bash
# Generate using Pexels/Pixabay stock footage instead of AI
uv run scripts/synthetic_data.py generate --scenario weapon_visible --source stock
uv run scripts/synthetic_data.py generate --scenario break_in_attempt --source stock
uv run scripts/synthetic_data.py generate --scenario package_theft --source stock
```

Stock footage sources:

- **Pexels**: https://www.pexels.com/api/ (requires PEXELS_API_KEY)
- **Pixabay**: https://pixabay.com/api/docs/ (requires PIXABAY_API_KEY)

### 2. Update Expected Labels to Match Reality

For scenarios where AI generation is used, update `expected_labels.json` to reflect what the AI actually generates:

**Before (unrealistic for AI generation):**

```json
{
  "threats": {
    "has_threat": true,
    "types": ["firearm", "armed_individual"],
    "max_severity": "critical"
  }
}
```

**After (realistic for AI generation):**

```json
{
  "threats": {
    "has_threat": false,
    "types": [],
    "max_severity": "none"
  },
  "_ai_generation_note": "Weapon not rendered due to content policy"
}
```

### 3. Use Staged Real Footage

For most accurate testing, especially for threat scenarios:

1. Create controlled test footage with props (toy weapons, etc.)
2. Use consenting participants
3. Label with actual ground truth
4. Store in `data/synthetic/staged/` directory

### 4. Separate AI-Generated from Real Test Data

Structure your test data to clearly distinguish sources:

```
data/synthetic/
  threats/
    weapon_visible_20260125_143022/    # AI-generated (limited)
      metadata.json                     # source: "ai"
      media/
    weapon_visible_stock_20260125/      # Stock footage
      metadata.json                     # source: "stock"
      media/
    weapon_visible_staged_20260125/     # Real staged footage
      metadata.json                     # source: "staged"
      media/
```

## Testing Strategy

### For Unit Tests

- Use mock data with realistic expected labels
- Don't rely on AI-generated images for threat detection tests

### For Integration Tests

- Use stock footage for threat scenarios
- Use AI-generated images only for benign scenarios (vehicle_parking, etc.)

### For E2E/Visual Tests

- Combine stock and staged footage for comprehensive coverage
- Document which test cases use which data sources

## Florence-2 Caption Validation

The comparison engine supports semantic caption matching with synonyms. When validating Florence captions against expected labels:

```python
# These are considered equivalent:
# "A man holding a cardboard box" matches expected ["person", "package"]
# because "man" is a synonym for "person" and "cardboard box" for "package"
```

However, Florence cannot describe what isn't in the image. If a weapon was not generated, Florence will not mention it, causing validation failures.

## Related Files

- **Validation Script:** `scripts/validate_synthetic_quality.py`
- **Generation Script:** `scripts/synthetic_data.py`
- **Comparison Engine:** `scripts/synthetic/comparison_engine.py`
- **Scenario Templates:** `scripts/synthetic/scenarios/threats/*.json`
- **Validation Report:** `data/synthetic/validation_report.json`

## Conclusion

AI-generated images are suitable for testing normal activity scenarios but **NOT suitable** for testing threat detection (weapons, violence, break-ins). Use stock footage or staged real footage for threat scenario testing.

Run `uv run scripts/validate_synthetic_quality.py audit` regularly to ensure test data quality.
