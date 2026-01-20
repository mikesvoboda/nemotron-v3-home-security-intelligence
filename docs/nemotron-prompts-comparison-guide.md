# Nemotron Prompt Comparison Guide

This guide explains how to extract and compare Nemotron prompts before and after improvements.

## File Locations

| File                                 | Purpose                                          |
| ------------------------------------ | ------------------------------------------------ |
| `backend/services/prompts.py`        | Source of all prompt templates                   |
| `docs/nemotron-prompts-baseline.txt` | Pre-improvement snapshot                         |
| `docs/nemotron-prompts-improved.txt` | Post-improvement snapshot (create after changes) |

## Prompt Templates

There are 5 risk analysis templates, used based on available enrichment data:

| Template                                  | Selection Condition                      |
| ----------------------------------------- | ---------------------------------------- |
| `RISK_ANALYSIS_PROMPT`                    | Fallback - no enrichment                 |
| `ENRICHED_RISK_ANALYSIS_PROMPT`           | Zone/baseline context available          |
| `FULL_ENRICHED_RISK_ANALYSIS_PROMPT`      | + Vision enrichment (plates, faces, OCR) |
| `VISION_ENHANCED_RISK_ANALYSIS_PROMPT`    | + Florence-2 attributes                  |
| `MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT` | Full model zoo (PRIMARY)                 |

Plus summary generation templates: `SUMMARY_SYSTEM_PROMPT`, `SUMMARY_PROMPT_TEMPLATE`, etc.

## Extraction Process

### Manual Extraction

1. Open `backend/services/prompts.py`
2. Copy each template constant (they're triple-quoted strings)
3. Paste into a new text file with clear headers
4. Note the template variable placeholders like `{camera_name}`

### Script Extraction

```bash
#!/usr/bin/env bash
# extract-nemotron-prompts.sh
# Extracts prompt templates from prompts.py to a text file

OUTPUT_FILE="${1:-docs/nemotron-prompts-$(date +%Y%m%d).txt}"
SOURCE_FILE="backend/services/prompts.py"

echo "# Nemotron Prompt Templates - $(date +%Y-%m-%d)" > "$OUTPUT_FILE"
echo "# Source: $SOURCE_FILE" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# Extract each template using Python
python3 << 'PYTHON' >> "$OUTPUT_FILE"
import sys
sys.path.insert(0, '.')

from backend.services.prompts import (
    RISK_ANALYSIS_PROMPT,
    ENRICHED_RISK_ANALYSIS_PROMPT,
    FULL_ENRICHED_RISK_ANALYSIS_PROMPT,
    VISION_ENHANCED_RISK_ANALYSIS_PROMPT,
    MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
    SUMMARY_PROMPT_TEMPLATE,
    SUMMARY_EMPTY_STATE_INSTRUCTION,
    SUMMARY_EVENT_FORMAT,
)

templates = [
    ("RISK_ANALYSIS_PROMPT", RISK_ANALYSIS_PROMPT),
    ("ENRICHED_RISK_ANALYSIS_PROMPT", ENRICHED_RISK_ANALYSIS_PROMPT),
    ("FULL_ENRICHED_RISK_ANALYSIS_PROMPT", FULL_ENRICHED_RISK_ANALYSIS_PROMPT),
    ("VISION_ENHANCED_RISK_ANALYSIS_PROMPT", VISION_ENHANCED_RISK_ANALYSIS_PROMPT),
    ("MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT", MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT),
    ("SUMMARY_SYSTEM_PROMPT", SUMMARY_SYSTEM_PROMPT),
    ("SUMMARY_PROMPT_TEMPLATE", SUMMARY_PROMPT_TEMPLATE),
    ("SUMMARY_EMPTY_STATE_INSTRUCTION", SUMMARY_EMPTY_STATE_INSTRUCTION),
    ("SUMMARY_EVENT_FORMAT", SUMMARY_EVENT_FORMAT),
]

for name, content in templates:
    print("=" * 80)
    print(f"TEMPLATE: {name}")
    print("=" * 80)
    print(content)
    print()
PYTHON

echo "Extracted prompts to: $OUTPUT_FILE"
```

## Comparison Methods

### Quick Diff

```bash
diff docs/nemotron-prompts-baseline.txt docs/nemotron-prompts-improved.txt
```

### Side-by-Side Diff

```bash
diff -y --width=160 docs/nemotron-prompts-baseline.txt docs/nemotron-prompts-improved.txt | less
```

### Git Diff (if both committed)

```bash
git diff docs/nemotron-prompts-baseline.txt docs/nemotron-prompts-improved.txt
```

### Visual Diff Tools

```bash
# VS Code
code --diff docs/nemotron-prompts-baseline.txt docs/nemotron-prompts-improved.txt

# Meld (if installed)
meld docs/nemotron-prompts-baseline.txt docs/nemotron-prompts-improved.txt
```

## Evaluating Prompt Improvements

### Qualitative Comparison

1. **Clarity**: Are instructions clearer?
2. **Structure**: Is the prompt better organized?
3. **Risk Guidance**: Are risk factors better explained?
4. **Output Format**: Is the expected JSON schema clearer?

### Quantitative Testing

Run the same events through both prompt versions:

```bash
# 1. Save current prompts as "improved"
# 2. Test with sample events and compare:
#    - Risk score consistency
#    - Reasoning quality
#    - False positive/negative rates

# Example: Use the prompt test endpoint
curl -X POST http://localhost:8000/api/prompts/test \
  -H "Content-Type: application/json" \
  -d '{"model": "nemotron", "test_input": "sample event data"}'
```

### A/B Testing (Production)

The system supports A/B testing via the prompt management API:

```bash
# Enable shadow mode to run both versions in parallel
curl -X POST http://localhost:8000/api/prompts/nemotron/shadow \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "shadow_version": 2}'
```

See `docs/developer/prompt-management.md` for full A/B testing documentation.

## Checklist After Prompt Changes

- [ ] Extract new prompts to `docs/nemotron-prompts-improved.txt`
- [ ] Run diff to review all changes
- [ ] Test with representative security events
- [ ] Compare risk scores and reasoning quality
- [ ] Update baseline file if improvements are accepted
- [ ] Document changes in commit message
