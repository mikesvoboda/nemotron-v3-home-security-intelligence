# Prompt Playground: Enhanced "Apply Suggestion" Design

**Date**: 2026-01-05
**Status**: Draft
**Author**: Claude + Human collaboration

## Overview

Redesign the "Apply Suggestion" feature in the Prompt Playground to transform AI audit recommendations into actionable prompt improvements through a progressive disclosure UX that serves both operators and engineers.

### Problem Statement

The current implementation appends suggestions as comments (`/* Suggestion: ... */`) to the end of prompts. This provides no meaningful assistance - users must manually figure out where and how to integrate recommendations.

### Goals

1. **Immediate improvement** - Smart auto-insertion of suggestions into the correct prompt location
2. **Guided editing** - Diff preview showing exactly what will change before applying
3. **Learning experience** - Explain why suggestions matter with evidence from actual events
4. **A/B testing** - Compare original vs modified prompts on real data before committing

### Target Users

Hybrid audience requiring layered complexity:

- **Security Operators**: Want "just fix it" simplicity
- **ML/AI Practitioners**: Want experimentation and validation tools
- **Developers/Engineers**: Want efficient editing with full control

## Design

### Core Flow: Progressive Disclosure

```
┌─────────────────────────────────────────────────────────────┐
│  Stage 1: PREVIEW (Default Landing)                         │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Suggestion: Time since last detected motion or event    ││
│  └─────────────────────────────────────────────────────────┘│
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ DIFF VIEW                                               ││
│  │   ## Camera & Time Context                              ││
│  │   Camera: {camera_name}                                 ││
│  │   Time: {timestamp}                                     ││
│  │   Day: {day_of_week}                                    ││
│  │   Lighting: {time_of_day}                               ││
│  │ + Time Since Last Event: {time_since_last_event}        ││
│  └─────────────────────────────────────────────────────────┘│
│                                                             │
│  [ Apply ]  [ Dismiss ]                                     │
│                                                             │
│  ▶ Why this matters (collapsed)                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼ (user clicks Apply)
┌─────────────────────────────────────────────────────────────┐
│  Stage 2: APPLIED                                           │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ ✓ Suggestion applied. Test it or save.                  ││
│  └─────────────────────────────────────────────────────────┘│
│                                                             │
│  [Prompt editor with change highlighted]                    │
│                                                             │
│  [ Reset ]  [ Save ]  [ Create A/B Test ]                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼ (user clicks Create A/B Test)
┌─────────────────────────────────────────────────────────────┐
│  Stage 3: A/B TEST                                          │
│  ┌────────────────────┬────────────────────┐                │
│  │   Original (A)     │   Modified (B)     │                │
│  ├────────────────────┼────────────────────┤                │
│  │ [Select Event ▼]   │ [Select Event ▼]   │                │
│  │                    │                    │                │
│  │ Risk Score: 65     │ Risk Score: 42     │                │
│  │ Level: high        │ Level: medium      │                │
│  │                    │                    │
│  │ Reasoning:         │ Reasoning:         │                │
│  │ "Person at night"  │ "Person at night,  │                │
│  │                    │  30s after last    │                │
│  │                    │  motion suggests   │                │
│  │                    │  continuous..."    │                │
│  └────────────────────┴────────────────────┘                │
│                                                             │
│  [ Run on 5 Random Events ]  [ Promote B ]                  │
└─────────────────────────────────────────────────────────────┘
```

### Component 1: Diff View

The diff view is the centerpiece of Stage 1.

#### Smart Context Detection

The system analyzes suggestion type to determine WHERE in the prompt it belongs:

| Category             | Action                                       | Example                                                  |
| -------------------- | -------------------------------------------- | -------------------------------------------------------- |
| `missing_context`    | Add new variable to relevant section         | Add `{time_since_last_event}` to "Camera & Time Context" |
| `unused_data`        | Highlight section for removal/simplification | Strike through unused `{legacy_field}`                   |
| `model_gaps`         | Suggest adding model-specific section        | Add "## Weather Context" section                         |
| `format_suggestions` | Show structural changes                      | Reorder sections for clarity                             |

#### Diff Display Rules

- Show only the **affected section** with 2-3 lines of context (not full prompt)
- GitHub-style colors: green (additions), red (removals), yellow (modifications)
- Line numbers for reference
- Monospace font for code-like appearance

#### Intelligent Insertion Logic

```python
def find_insertion_point(prompt: str, suggestion: EnrichedSuggestion) -> int:
    """
    Determine where to insert the suggestion based on:
    1. Target section header (e.g., "## Camera & Time Context")
    2. Variable naming patterns (match existing style)
    3. Suggestion category (missing_context → context sections)
    """
    # Find target section
    section_match = re.search(rf"## {suggestion.target_section}.*?\n(.*?)(?=\n##|\Z)", prompt, re.DOTALL)
    if section_match:
        # Insert at end of section, before next section
        return section_match.end()

    # Fallback: append to end with comment
    return len(prompt)
```

### Component 2: "Why This Matters" (Learning Mode)

Expandable section providing educational context.

#### Content Structure

**1. Impact Summary** (1-2 sentences)

> "Adding time-since-last-event helps the AI distinguish between routine activity and unusual timing patterns. Events occurring shortly after previous motion are often less suspicious than isolated incidents."

**2. Evidence From Your Data**

- "This suggestion came from **3 events** where timing context could have improved analysis"
- Clickable links to source events
- Example: "Event #142 scored 65 (high) but might have been 40 (medium) with this context"

**3. Prompt Engineering Tip**

- Best-practice guidance for this suggestion type
- Example: "Temporal context variables work best near other time-related fields"

#### Visual Design

- Light background card (subtle elevation)
- Lightbulb icon
- "Don't show tips" checkbox for power users
- "Learn more" link to documentation

### Component 3: A/B Testing Mode

Split-view comparison of original vs modified prompts.

#### Features

| Feature              | Description                                                  |
| -------------------- | ------------------------------------------------------------ |
| Event Selector       | Dropdown to pick specific events, or "Random N events"       |
| Side-by-side results | Both prompts score the same event simultaneously             |
| Aggregate stats      | After multiple tests: avg score difference, consistency rate |
| "Promote B"          | Makes modified prompt the new default                        |

#### Test Results Display

```typescript
interface ABTestResult {
  eventId: number;
  originalResult: {
    riskScore: number;
    riskLevel: string;
    reasoning: string;
  };
  modifiedResult: {
    riskScore: number;
    riskLevel: string;
    reasoning: string;
  };
  scoreDelta: number; // modified - original
}
```

## Data Architecture

### Enhanced Suggestion Schema

```typescript
interface EnrichedSuggestion {
  // Existing fields
  category: 'missing_context' | 'unused_data' | 'model_gaps' | 'format_suggestions';
  suggestion: string;
  priority: 'high' | 'medium' | 'low';
  frequency: number;

  // New fields for smart application
  targetSection: string; // "Camera & Time Context"
  insertionPoint: 'append' | 'prepend' | 'replace';
  proposedVariable: string; // "{time_since_last_event}"
  proposedLabel: string; // "Time Since Last Event:"

  // New fields for learning mode
  impactExplanation: string; // "Why this matters" content
  sourceEventIds: number[]; // Events that triggered this

  // Optional improvement estimate
  exampleImprovement?: {
    eventId: number;
    beforeScore: number;
    estimatedAfterScore: number;
  };
}
```

### API Endpoints

#### 1. Test Prompt (Ephemeral)

```
POST /api/ai-audit/test-prompt

Request:
{
  "eventId": 142,
  "customPrompt": "...",
  "temperature": 0.7,
  "maxTokens": 2048
}

Response:
{
  "riskScore": 42,
  "riskLevel": "medium",
  "reasoning": "...",
  "entities": [...],
  "flags": [...],
  "processingTimeMs": 1250
}
```

#### 2. Save Prompt Configuration

```
PUT /api/ai-audit/prompts/{model}

Request:
{
  "systemPrompt": "...",
  "temperature": 0.7,
  "maxTokens": 2048
}

Response:
{
  "success": true,
  "version": 3,
  "savedAt": "2026-01-05T12:00:00Z"
}
```

#### 3. Get Enriched Recommendations

```
GET /api/ai-audit/recommendations?enriched=true

Response:
{
  "recommendations": [
    {
      "category": "missing_context",
      "suggestion": "Time since last detected motion or event",
      "priority": "high",
      "frequency": 3,
      "targetSection": "Camera & Time Context",
      "insertionPoint": "append",
      "proposedVariable": "{time_since_last_event}",
      "proposedLabel": "Time Since Last Event:",
      "impactExplanation": "Adding time-since-last-event helps...",
      "sourceEventIds": [142, 156, 189]
    }
  ]
}
```

## Error Handling

### Suggestion Application Failures

| Scenario                 | Handling                                                        |
| ------------------------ | --------------------------------------------------------------- |
| Target section not found | Fallback to comment at end; show message "Couldn't auto-insert" |
| Variable already exists  | Skip change; show "This suggestion is already applied"          |
| Conflicting suggestions  | Queue and apply sequentially; show consolidated diff            |

### A/B Testing Failures

| Scenario               | Handling                                          |
| ---------------------- | ------------------------------------------------- |
| Nemotron timeout/error | Show error in that panel; don't block other panel |
| No events available    | Disable "Run Test"; show "No events available"    |
| Rate limiting          | Queue requests; show progress indicator           |

### Save Failures

| Scenario            | Handling                                                   |
| ------------------- | ---------------------------------------------------------- |
| Backend unreachable | Keep in local state; show "Retry?" with Export JSON backup |
| Validation error    | Show specific error; highlight invalid field               |

### Recovery Options

- **Reset button**: Always visible, reverts to last saved state
- **Export JSON**: Download current configuration as backup
- **Version history** (future): Track last 5 saved versions per prompt

## Frontend Components

### New Components

```
frontend/src/components/ai/
├── PromptPlayground.tsx          # Existing - needs updates
├── SuggestionDiffView.tsx        # NEW - GitHub-style diff display
├── SuggestionExplanation.tsx     # NEW - "Why this matters" expandable
├── PromptABTest.tsx              # NEW - Split-view A/B testing
└── PromptTestResult.tsx          # NEW - Individual test result display
```

### State Management

```typescript
interface PromptPlaygroundState {
  // Current prompt state
  originalPrompt: string;
  modifiedPrompt: string;
  hasUnsavedChanges: boolean;

  // Active suggestion
  activeSuggestion: EnrichedSuggestion | null;
  suggestionApplied: boolean;

  // A/B testing
  abTestResults: ABTestResult[];
  isTestRunning: boolean;

  // UI state
  showExplanation: boolean;
  showABTest: boolean;
}
```

## Testing Strategy

### Unit Tests

- `SuggestionDiffView`: Renders correct diff for each suggestion type
- `findInsertionPoint`: Correctly identifies insertion location
- `PromptABTest`: Handles loading, error, and success states

### Integration Tests

- Apply suggestion → verify prompt modified correctly
- Run A/B test → verify both prompts executed
- Save prompt → verify persistence

### E2E Tests

- Full flow: Click Edit → Preview → Apply → A/B Test → Promote → Save
- Error recovery: Network failure during save → retry succeeds

## Implementation Phases

### Phase 1: Core Infrastructure

- Enhanced suggestion schema
- `POST /api/ai-audit/test-prompt` endpoint
- `PUT /api/ai-audit/prompts/{model}` endpoint
- Prompt parsing utilities

### Phase 2: Diff View & Smart Apply

- `SuggestionDiffView` component
- Intelligent insertion logic
- Preview before apply

### Phase 3: Learning Mode

- `SuggestionExplanation` component
- Link suggestions to source events
- Impact explanations

### Phase 4: A/B Testing

- `PromptABTest` component
- Side-by-side comparison
- Aggregate statistics
- "Promote B" functionality

## Success Metrics

| Metric                | Target                             |
| --------------------- | ---------------------------------- |
| Suggestion apply rate | >50% of viewed suggestions applied |
| A/B test usage        | >20% of applied suggestions tested |
| Prompt save rate      | >80% of applied suggestions saved  |
| Time to apply         | <10 seconds from click to applied  |

## Open Questions

1. **Suggestion generation**: How do we generate the enriched suggestion fields (`targetSection`, `proposedVariable`, etc.)? LLM-generated during audit? Rule-based?

2. **Prompt versioning**: Should we implement full version history now, or defer to future release?

3. **Multi-model coordination**: If a suggestion affects multiple models (e.g., Nemotron + Florence-2), how do we handle that in the UI?

---

_Document generated through collaborative brainstorming session._
