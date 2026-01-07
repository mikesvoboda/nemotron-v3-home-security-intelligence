# Florence-2 Prompts Directory - Agent Guide

## Purpose

This directory contains configuration files for Florence-2, a Visual Question Answering (VQA) model that enriches object detections with contextual information. Florence-2 answers free-form questions about detected objects (people, vehicles) to provide detailed descriptions.

## Files

| File              | Purpose                                             | Version Control  |
| ----------------- | --------------------------------------------------- | ---------------- |
| `current.json`    | Current active configuration (list of VQA queries)  | Runtime-managed  |
| `history/`        | Version history directory                           | -                |
| `history/v1.json` | Initial default configuration (8 default questions) | Checked into git |

## Configuration Schema

```json
{
  "model_name": "florence2",
  "config": {
    "vqa_queries": [
      "What is this person wearing?",
      "What is this person carrying?",
      "What is this person doing?",
      "Is this person a service worker or delivery person?",
      "What color is this vehicle?",
      "What type of vehicle is this?",
      "Is this a commercial or personal vehicle?",
      "Are there any visible company logos or text on this vehicle?"
    ]
  },
  "version": 1,
  "created_at": "2026-01-06T13:16:23.587691+00:00",
  "created_by": "system",
  "description": "Initial default configuration",
  "updated_at": "2026-01-06T13:16:23.587691+00:00"
}
```

## Configuration Fields

### `vqa_queries` (array of strings, required)

List of natural language questions to ask Florence-2 about each detected object. The model processes the image region around each detection and generates free-form text answers.

**Default queries (v1):**

| Query                                                          | Target  | Purpose                                                |
| -------------------------------------------------------------- | ------- | ------------------------------------------------------ |
| "What is this person wearing?"                                 | Person  | Clothing description (complements Fashion-CLIP)        |
| "What is this person carrying?"                                | Person  | Identify suspicious items (backpack, tools, etc.)      |
| "What is this person doing?"                                   | Person  | Activity description (complements X-CLIP)              |
| "Is this person a service worker or delivery person?"          | Person  | Risk reduction (uniforms indicate legitimate activity) |
| "What color is this vehicle?"                                  | Vehicle | Vehicle description for tracking                       |
| "What type of vehicle is this?"                                | Vehicle | Vehicle classification (car, truck, van, etc.)         |
| "Is this a commercial or personal vehicle?"                    | Vehicle | Distinguish delivery/work vehicles                     |
| "Are there any visible company logos or text on this vehicle?" | Vehicle | Identify service vehicles by branding                  |

**Requirements:**

- Must have at least one query
- Queries should be clear, specific questions (not commands)
- Queries are object-agnostic (system determines which apply based on detection type)

## How Florence-2 VQA Works

1. **Object detection:** RT-DETR detects objects in the image (person, car, etc.)
2. **Region cropping:** The system crops the image around each detected bounding box
3. **Question answering:** Florence-2 processes each crop with all VQA queries
4. **Response filtering:** Responses like "N/A", "unknown", or empty strings are discarded
5. **Attribute storage:** Valid responses are stored as detection attributes in PostgreSQL

**Example flow:**

```
Detection: person (x=100, y=200, w=150, h=300, confidence=0.95)
  ↓ Crop region (100, 200, 150, 300)
  ↓ Ask: "What is this person wearing?"
  ↓ Response: "dark hoodie, black pants, white sneakers"
  ↓ Store: detection.attributes['florence2_vqa'] = {"clothing": "dark hoodie, ..."}
```

## Use Cases for Custom Queries

### Enhanced Person Analysis

Add queries for more detailed person descriptions:

```json
"vqa_queries": [
  "What is this person wearing?",
  "What is this person carrying?",
  "What is this person doing?",
  "Is this person a service worker or delivery person?",
  "What color is this person's clothing?",
  "Is this person wearing any face covering or mask?",
  "What is the approximate age range of this person?",
  "Is this person alone or with others?"
]
```

### Vehicle-Focused Analysis

Prioritize vehicle identification queries:

```json
"vqa_queries": [
  "What color is this vehicle?",
  "What type of vehicle is this?",
  "Is this a commercial or personal vehicle?",
  "Are there any visible company logos or text on this vehicle?",
  "What is the make and model of this vehicle?",
  "What is the license plate number?",
  "Are there any visible damage or modifications to this vehicle?",
  "How many doors does this vehicle have?"
]
```

### Security-Specific Queries

Focus on suspicious indicators:

```json
"vqa_queries": [
  "What is this person carrying?",
  "Is this person wearing gloves?",
  "Is this person's face visible or covered?",
  "Are there any tools or equipment visible?",
  "Is this person looking at the camera?",
  "Is this person interacting with doors or windows?",
  "Are there any bags or packages visible?"
]
```

## Integration with Risk Analysis

Florence-2 VQA responses are incorporated into the Nemotron risk analysis prompt as contextual enrichment:

```
## Detections with Full Enrichment
1. Person (conf: 0.95)
   - Clothing (Fashion-CLIP): all_black_clothing, hoodie, gloves
   - VQA (Florence-2):
     - "What is this person wearing?" → "black hoodie with hood up, dark gloves"
     - "What is this person carrying?" → "backpack and flashlight"
     - "Is this person a service worker?" → "no visible uniform or company branding"
   - Risk factors: Suspicious attire + carrying items + no service indicators
```

Nemotron uses these VQA responses to make more informed risk assessments.

## Performance Considerations

- **Query count:** Each query adds ~100-200ms inference time per detection
- **Response length:** Longer queries may produce longer responses, increasing processing time
- **Redundancy:** Avoid asking similar questions (overlap with Fashion-CLIP, X-CLIP)
- **Specificity:** More specific questions yield more useful answers

**Recommended query count:** 4-8 queries per detection for optimal balance of detail and performance.

## Best Practices

### Question Design

- Use clear, natural language questions
- Ask one thing per question (not compound questions)
- Prefer "what" questions over yes/no questions for richer descriptions
- Consider the model's visual capabilities (can't see very small text or fine details)

### Avoiding Redundancy

Florence-2 VQA complements other enrichment models:

| Model        | Purpose                              | Overlap with Florence-2 VQA     |
| ------------ | ------------------------------------ | ------------------------------- |
| Fashion-CLIP | Clothing classification (categories) | "What is this person wearing?"  |
| X-CLIP       | Action recognition (predefined list) | "What is this person doing?"    |
| Vehicle-CLIP | Vehicle type classification          | "What type of vehicle is this?" |

**Recommendation:** Use Florence-2 for open-ended context that structured models can't provide:

- Specific descriptions (color, branding, text)
- Contextual clues (service worker identification)
- Item identification (bags, tools, accessories)

## Version History

Version history tracks changes to VQA query lists. Use the API to:

- View history: `GET /api/prompts/florence2/history`
- Restore version: `POST /api/prompts/florence2/versions/{version}/restore`
- Compare query lists: Diff JSON files in `history/`

## Testing Configuration Changes

1. **Add new queries gradually:** Test 1-2 new queries at a time
2. **Review responses:** Check if answers provide useful security context
3. **Monitor inference time:** Measure P95 latency with new query count
4. **Validate with test images:** Use known test cases with expected answers

## Related Documentation

- `/backend/services/enrichment/florence2_enrichment.py` - Florence-2 VQA service
- `/ai/florence2/AGENTS.md` - Florence-2 model server setup (if applicable)
- `/backend/api/routes/prompt_management.py` - Prompt configuration API
- `/backend/data/prompts/AGENTS.md` - Prompts directory overview
