# AI Audit Components Directory

## Purpose

This directory contains AI Audit-specific components and re-exports key components from the `../ai/` directory for a unified import path.

## Files

| File                        | Purpose                                         |
| --------------------------- | ----------------------------------------------- |
| `index.ts`                  | Barrel exports for all AI Audit components      |
| `AGENTS.md`                 | This documentation file                         |
| `AuditProgressBar.tsx`      | Real-time batch audit progress indicator        |
| `AuditResultsTable.tsx`     | Table displaying audit results                  |
| `ModelContributionChart.tsx`| Chart showing model contribution breakdown      |

## Exported Components

### Direct Exports (defined in this directory)

- `AuditProgressBar` - Real-time progress indicator for batch audit operations
- `AuditResultsTable` - Table displaying individual audit results
- `ModelContributionChart` - Bar chart showing model contributions

### Re-exported Components (from `../ai/` directory)

- `PromptPlayground` - Slide-out panel for A/B testing, prompt editing, and version management
- `PromptABTest` - Split-view A/B testing component for prompt comparison
- `ABTestStats` - Aggregate statistics display for A/B test results
- `SuggestionDiffView` - GitHub-style diff view for prompt suggestions
- `SuggestionExplanation` - Expandable "Why This Matters" component

## Usage

Import components from the `ai-audit` barrel export:

```typescript
import {
  PromptPlayground,
  PromptABTest,
  ABTestStats,
  AuditProgressBar,
  ModelContributionChart,
} from '../components/ai-audit';
```

## PromptPlayground Features

The PromptPlayground component provides comprehensive A/B testing functionality:

1. **Prompt Editor Panel** - Monaco-style editor with syntax highlighting for template variables
2. **A/B Test Configuration** - Compare original vs modified prompts on real events
3. **Test Results Display** - Side-by-side comparison with quality scores and delta indicators
4. **Diff View** - GitHub-style diff showing changes between versions
5. **Version History** - Track and restore previous prompt versions
6. **Import/Export** - Save and load prompt configurations as JSON
7. **Statistical Analysis** - Improvement/regression rates with winner recommendation

## Related Components in `../ai/`

Additional AI Audit functionality is implemented in the `../ai/` directory:

- `../ai/AIAuditPage.tsx` - Main AI audit dashboard
- `../ai/QualityScoreTrends.tsx` - Quality score metrics
- `../ai/RecommendationsPanel.tsx` - Prompt improvement suggestions
- `../ai/BatchAuditModal.tsx` - Batch audit trigger dialog
- `../ai/ModelLeaderboard.tsx` - Model contribution rankings

See `../ai/AGENTS.md` for full documentation of these components.
