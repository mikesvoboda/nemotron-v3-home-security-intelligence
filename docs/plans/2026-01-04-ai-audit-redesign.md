# AI Audit Page Redesign

**Date:** 2026-01-04
**Status:** Approved

## Overview

Redesign the AI Audit Dashboard to focus on quality metrics and prompt improvement recommendations, with a new Prompt Playground feature for testing and refining AI model configurations.

## Goals

1. Separate concerns: Move performance metrics to AI Performance page
2. Elevate recommendations: Make prompt improvements the primary focus
3. Enable experimentation: Add Prompt Playground for testing changes before deployment
4. Support all configurable models: Nemotron, Florence-2, YOLO-World, X-CLIP, Fashion-CLIP

## Current State

The AI Audit page currently displays:

- 4 summary metric cards (Average Quality, Consistency Rate, Enrichment Utilization, Evaluation Coverage)
- Model Contribution Rates bar chart
- Model Leaderboard table (12 rows)
- Prompt Improvement Recommendations (4 expandable sections)

## Proposed Changes

### 1. Remove from AI Audit Page

- **Model Contribution Rates chart** → Move to AI Performance page
- **Model Leaderboard table** → Move to AI Performance page

### 2. Revised Page Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│ AI Audit Dashboard                    [Last 7 days ▼] [Trigger] [↻] │
├─────────────────────────────────────────────────────────────────────┤
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                 │
│ │ Avg      │ │Consistency│ │Enrichment│ │Evaluation│                 │
│ │ Quality  │ │ Rate     │ │Utilization│ │ Coverage │                 │
│ │ 4.8/5    │ │ 2.0/5    │ │ 42%      │ │ 2%       │                 │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘                 │
├─────────────────────────────────────────────────────────────────────┤
│ Prompt Improvement Recommendations              20 High Priority     │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ ▶ Missing Context Information                         5 items   │ │
│ ├─────────────────────────────────────────────────────────────────┤ │
│ │ ▼ Unused Data                                         5 items   │ │
│ │   • Cross-Camera Activity details...            [high] 1x  [→]  │ │
│ │   • Baseline Comparison section...              [high] 1x  [→]  │ │
│ ├─────────────────────────────────────────────────────────────────┤ │
│ │ ▶ Model Gaps                                          5 items   │ │
│ ├─────────────────────────────────────────────────────────────────┤ │
│ │ ▶ Format Suggestions                                  5 items   │ │
│ └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

Each recommendation item has a `[→]` button to open the Prompt Playground.

### 3. Prompt Playground Slide-Out Panel

80% viewport width panel slides in from right when clicking `[→]` on any recommendation.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Prompt Playground                                                    [✕]     │
├──────────────────────────────────────────────────────────────────────────────┤
│ Recommendation: "Cross-Camera Activity details were not utilized"            │
│ Source Event: #7832 (beach_front_left, Jan 4 1:15am)           [View Event]  │
├──────────────────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ NEMOTRON - Risk Analysis Prompt                            [▼ Expanded] │ │
│ │ ┌────────────────────────────────┬─────────────────────────────────────┐ │ │
│ │ │ You are a security analyst...  │  Test: [Event #7832 ▼] [Upload]     │ │ │
│ │ │                                │  Before: 50  After: -- [▶ Run Test] │ │ │
│ │ │ ## Detection Context           │                                     │ │ │
│ │ │ {detections}                   │  [Apply Suggestion] [Reset]         │ │ │
│ │ └────────────────────────────────┴─────────────────────────────────────┘ │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ FLORENCE-2 - Scene Analysis Queries                       [▶ Collapsed] │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ YOLO-WORLD - Custom Object Classes                        [▶ Collapsed] │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ X-CLIP - Action Recognition Classes                       [▶ Collapsed] │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ FASHION-CLIP - Clothing Categories                        [▶ Collapsed] │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│ VERSION HISTORY                                              [▶ Collapsed]  │
├──────────────────────────────────────────────────────────────────────────────┤
│ [Apply to All Similar] [Save as Template] [Export JSON ↓] [Import JSON ↑] [Save All] │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 4. Model-Specific Editors

#### Nemotron (Full Text Editor)

- Syntax-highlighted prompt editor
- Variables: `{detections}`, `{cross_camera_data}`, `{enrichment}`, etc.
- "Apply Suggestion" auto-inserts recommended changes with diff highlighting
- "Reset" reverts to saved version

#### Florence-2 (Query List)

```
┌────────────────────────────────────────────────────────────────┐
│ • What is the person doing?                                [×] │
│ • What objects are they carrying?                          [×] │
│ • Describe the environment                                 [×] │
│ • Is there anything unusual in this scene?                 [×] │
│ [+ Add Query]                                                  │
└────────────────────────────────────────────────────────────────┘
```

#### YOLO-World (Tag Input + Threshold)

```
┌────────────────────────────────────────────────────────────────┐
│ [knife ×] [gun ×] [package ×] [crowbar ×] [spray paint ×]      │
│ [Amazon box ×] [FedEx package ×] [suspicious bag ×]            │
│ [+ Add class...]                                               │
└────────────────────────────────────────────────────────────────┘
Confidence threshold: [====●=====] 0.35
```

#### X-CLIP (Tag Input)

```
┌────────────────────────────────────────────────────────────────┐
│ [loitering ×] [running away ×] [fighting ×] [breaking in ×]    │
│ [climbing fence ×] [hiding ×] [normal walking ×]               │
│ [+ Add action...]                                              │
└────────────────────────────────────────────────────────────────┘
```

#### Fashion-CLIP (Tag Input)

```
┌────────────────────────────────────────────────────────────────┐
│ [dark hoodie ×] [face mask ×] [gloves ×] [all black ×]         │
│ [delivery uniform ×] [high-vis vest ×] [business attire ×]     │
│ [+ Add category...]                                            │
└────────────────────────────────────────────────────────────────┘
```

### 5. Testing Workflow

1. User clicks `[→]` on a recommendation
2. Panel opens with source event pre-selected
3. User clicks "Apply Suggestion" or manually edits
4. User clicks "Run Test"
5. System runs inference with modified prompt (~10-30s for Nemotron)
6. Results show before/after comparison:
   ```
   Before: Score 50 (Medium) | After: Score 35 (Low) ✓ Improved
   ```
7. User can test against different events or upload custom image
8. "Save All" persists changes, "Export JSON" downloads config

### 6. Export/Import JSON Format

```json
{
  "version": "1.0",
  "exported_at": "2026-01-04T06:45:00Z",
  "prompts": {
    "nemotron": {
      "system_prompt": "You are a security analyst...",
      "version": 3
    },
    "florence2": {
      "queries": [
        "What is the person doing?",
        "What objects are they carrying?",
        "Describe the environment",
        "Is there anything unusual in this scene?"
      ]
    },
    "yolo_world": {
      "classes": ["knife", "gun", "package", "crowbar", "spray paint"],
      "confidence_threshold": 0.35
    },
    "xclip": {
      "action_classes": ["loitering", "running away", "fighting", "breaking in"]
    },
    "fashion_clip": {
      "clothing_categories": ["dark hoodie", "face mask", "delivery uniform"]
    }
  }
}
```

Import validates JSON schema and shows diff before applying.

### 7. Additional Metrics (from Prometheus)

Based on metrics being collected in `backend/core/metrics.py` but not currently displayed:

**Prompt Template Usage:**

Add to main dashboard or Prompt Playground:

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Prompt Template Usage                             [Last 7 days ▼]          │
├────────────────────────────────────────────────────────────────────────────┤
│ nemotron_risk_v3     ████████████████████████████████  847 (85%)           │
│ nemotron_risk_v2     ████████████                      124 (12%)           │
│ custom_high_security ██                                 28 (3%)            │
│                                                                            │
│ Metric: hsi_prompt_template_used_total (Counter, by template label)        │
└────────────────────────────────────────────────────────────────────────────┘
```

- Shows which prompt templates are being used
- Helps track A/B testing of prompt variations
- Click template → open in Prompt Playground

**Florence-2 Task Breakdown:**

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Florence-2 Tasks                                  [Last 7 days ▼]          │
├────────────────────────────────────────────────────────────────────────────┤
│ <CAPTION>              ████████████████████████████  2,847                 │
│ <DETAILED_CAPTION>     ████████████████               1,523                 │
│ <MORE_DETAILED_CAPTION>██████████                      847                  │
│ <OD>                   ████████                        623                  │
│ <REGION_TO_DESCRIPTION>██████                          412                  │
│                                                                            │
│ Metric: hsi_florence_task_total (Counter, by task label)                   │
└────────────────────────────────────────────────────────────────────────────┘
```

- Shows which Florence-2 tasks are being invoked
- Helps identify if certain tasks are underutilized
- Useful for understanding enrichment pipeline behavior

**Enrichment Model Calls:**

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Enrichment Model Usage                            [Last 7 days ▼]          │
├────────────────────────────────────────────────────────────────────────────┤
│ florence2            ████████████████████████████████  3,847               │
│ clip_vit_l           ██████████████████████████        2,523               │
│ yolo_world           ████████████████                  1,847               │
│ xclip                ████████████                      1,223               │
│ fashion_clip         ████████                            823               │
│                                                                            │
│ Metric: hsi_enrichment_model_calls_total (Counter, by model label)         │
└────────────────────────────────────────────────────────────────────────────┘
```

- Shows how often each enrichment model is called
- Helps identify underutilized models
- Click model → navigate to Model Zoo with that model highlighted

**Events Reviewed Counter:**

Add to summary metrics row:

```
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ Avg      │ │Consistency│ │Enrichment│ │Evaluation│ │ Events   │
│ Quality  │ │ Rate     │ │Utilization│ │ Coverage │ │ Reviewed │
│ 4.8/5    │ │ 2.0/5    │ │ 42%      │ │ 2%       │ │ 847      │
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
```

- Metric: `hsi_events_reviewed_total` (Counter)
- Shows how many events have been manually reviewed by user
- Helps track audit coverage and user engagement
- Clicking navigates to Timeline filtered to reviewed events

### 8. Version History

- Tracks all prompt changes with timestamps
- "Restore" button reverts to any previous version
- Stored per-model in database
- Shows who made the change (for future multi-user support)

## Interaction Details

### Opening the Panel

1. Click `[→]` on recommendation
2. Panel slides in (300ms ease-out)
3. Main content compresses to 20% width (dimmed)
4. Source event auto-selected

### Closing the Panel

- Click `[✕]`, click outside, or press `Escape`
- Unsaved changes prompt: "Discard changes?"

### Keyboard Shortcuts

- `Ctrl+S` - Save all
- `Ctrl+Enter` - Run test
- `Escape` - Close panel

## Backend API Requirements

| Endpoint                                  | Method | Description                          |
| ----------------------------------------- | ------ | ------------------------------------ |
| `/api/ai-audit/prompts`                   | GET    | Fetch current prompts for all models |
| `/api/ai-audit/prompts/{model}`           | GET    | Fetch prompt for specific model      |
| `/api/ai-audit/prompts/{model}`           | PUT    | Update prompt/config for model       |
| `/api/ai-audit/prompts/test`              | POST   | Run test with modified prompt        |
| `/api/ai-audit/prompts/history`           | GET    | Get version history                  |
| `/api/ai-audit/prompts/history/{version}` | POST   | Restore specific version             |
| `/api/ai-audit/prompts/export`            | GET    | Export all configs as JSON           |
| `/api/ai-audit/prompts/import`            | POST   | Import and validate JSON config      |

## Implementation Tasks

1. **Move charts to AI Performance page**

   - Move Model Contribution Rates chart
   - Move Model Leaderboard table
   - Update AI Performance layout

2. **Update AI Audit page layout**

   - Remove chart components
   - Add `[→]` buttons to recommendation items
   - Full-width recommendations section

3. **Build Prompt Playground panel**

   - Slide-out panel component (80% width)
   - Nemotron prompt editor with syntax highlighting
   - Florence-2 query list editor
   - YOLO-World tag input + threshold slider
   - X-CLIP tag input
   - Fashion-CLIP tag input

4. **Testing infrastructure**

   - Event/image selector
   - Run test button with loading state
   - Before/after score comparison
   - Full response diff view

5. **Version history**

   - Database schema for prompt versions
   - History list component
   - Restore functionality

6. **Export/Import**

   - JSON schema definition
   - Export download
   - Import with validation and diff preview

7. **Backend APIs**
   - Prompt CRUD endpoints
   - Test endpoint (runs inference)
   - History endpoints
   - Export/Import endpoints

## Success Criteria

- [ ] Model charts moved to AI Performance page
- [ ] Recommendations section has full width and prominence
- [ ] Prompt Playground opens on recommendation click
- [ ] Can edit and test Nemotron prompts
- [ ] Can edit and test Florence-2 queries
- [ ] Can edit and test YOLO-World classes
- [ ] Can edit and test X-CLIP actions
- [ ] Can edit and test Fashion-CLIP categories
- [ ] Before/after score comparison works
- [ ] Version history tracks all changes
- [ ] Export/Import JSON works
- [ ] Responsive design for smaller screens
