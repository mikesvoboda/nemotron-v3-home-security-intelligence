# AI Audit Components Directory

## Purpose

This directory is a placeholder for future AI Audit-specific components. Currently, all AI Audit components live in the `../ai/` directory alongside AI Performance components.

## Files

| File       | Purpose                             |
| ---------- | ----------------------------------- |
| `index.ts` | Barrel exports (currently empty)    |
| `AGENTS.md`| This documentation file             |

## Current Status

The `index.ts` file contains TODOs for future component exports:

```typescript
// TODO: Add PromptPlayground export when implementation is complete
// TODO: Add VersionHistory export when implementation is complete
```

## Note on PromptPlayground

The `PromptPlayground` component mentioned in plans is implemented in the `../ai/` directory as `../ai/PromptPlayground.tsx`. It is exported from `../ai/index.ts` along with other AI components.

## Related Components

All AI Audit functionality is currently implemented in:

- `../ai/AIAuditPage.tsx` - Main AI audit dashboard
- `../ai/PromptPlayground.tsx` - Slide-out panel for prompt editing
- `../ai/QualityScoreTrends.tsx` - Quality score metrics
- `../ai/RecommendationsPanel.tsx` - Prompt improvement suggestions
- `../ai/BatchAuditModal.tsx` - Batch audit trigger dialog
- `../ai/ModelLeaderboard.tsx` - Model contribution rankings
- `../ai/ModelContributionChart.tsx` - Contribution bar chart

See `../ai/AGENTS.md` for full documentation of these components.
