# AI Audit Components Directory

## Purpose

This directory contains components for the AI Audit page's Prompt Playground feature, which allows users to test and refine AI model configurations.

## Key Components

| Component              | Purpose                                             |
| ---------------------- | --------------------------------------------------- |
| `PromptPlayground.tsx` | Slide-out panel for testing and editing AI prompts  |

## Component Details

### PromptPlayground

A slide-out panel (80% viewport width) that provides editors for all configurable AI models:

**Features:**
- Nemotron: Full text editor for risk analysis system prompt
- Florence-2: Query list editor for scene analysis
- YOLO-World: Tag input for custom object classes + confidence threshold slider
- X-CLIP: Tag input for action recognition classes
- Fashion-CLIP: Tag input for clothing categories

**Interaction:**
- Opens when clicking `[->]` button on a recommendation in RecommendationsPanel
- Keyboard shortcuts: `Ctrl+S` (save), `Ctrl+Enter` (run test), `Escape` (close)
- Before/after comparison when testing prompts
- Export/import JSON configuration

**Dependencies:**
- Headless UI for Dialog, Transition, and Disclosure components
- lucide-react for icons
- Backend API for prompt test endpoint (NEM-1140)

## Testing

```bash
# Run component tests
cd frontend && npm test -- PromptPlayground

# Run with coverage
cd frontend && npm test -- --coverage PromptPlayground
```

## Integration

The PromptPlayground is designed to be opened from the RecommendationsPanel component in the AI Audit page:

```tsx
import PromptPlayground from '../ai-audit/PromptPlayground';

// In parent component
<PromptPlayground
  isOpen={isPlaygroundOpen}
  onClose={() => setIsPlaygroundOpen(false)}
  recommendation={selectedRecommendation}
  sourceEvent={sourceEvent}
  recentEvents={recentEvents}
  onSave={handleSaveConfig}
/>
```

## File Inventory

| File                         | Description                       |
| ---------------------------- | --------------------------------- |
| `PromptPlayground.tsx`       | Main slide-out panel component    |
| `PromptPlayground.test.tsx`  | Test suite                        |
| `AGENTS.md`                  | This documentation file           |
| `index.ts`                   | Barrel exports                    |

## Related Components

- `../ai/RecommendationsPanel.tsx` - Parent component that triggers playground opening
- `../ai/AIAuditPage.tsx` - Main page that hosts the recommendations panel
