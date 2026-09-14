# Contextual Documentation Link Design

**Date:** 2026-01-18
**Status:** Approved
**Author:** maui + Mike Svoboda

## Summary

Add a dynamic documentation link to the header that changes based on the current page. When a user navigates to `/alerts`, the header shows "Alerts Documentation" linking to `docs/ui/alerts.md` on GitHub. This provides contextual help without leaving the app's mental model.

## Goals

- Give users immediate access to relevant documentation for the page they're viewing
- Use progressive disclosure: simple explanations first, technical deep dives linked at the bottom
- Leverage existing GitHub-hosted docs infrastructure
- Maintain NVIDIA branding consistency

## Non-Goals

- In-app documentation rendering (links to GitHub instead)
- Auto-generating documentation from code
- Documentation for dev-tools page (developer-only)

## Design

### Configuration

**New file: `frontend/src/config/pageDocumentation.ts`**

```typescript
export interface PageDocConfig {
  label: string; // Display name: "Alerts", "Jobs", etc.
  docPath: string; // GitHub path: "docs/ui/alerts.md"
  description?: string; // Tooltip text (optional)
}

export const PAGE_DOCUMENTATION: Record<string, PageDocConfig> = {
  '/': {
    label: 'Dashboard',
    docPath: 'docs/ui/dashboard.md',
    description: 'Live monitoring and risk overview',
  },
  '/timeline': { label: 'Timeline', docPath: 'docs/ui/timeline.md' },
  '/entities': { label: 'Entities', docPath: 'docs/ui/entities.md' },
  '/alerts': { label: 'Alerts', docPath: 'docs/ui/alerts.md' },
  '/audit': { label: 'Audit Log', docPath: 'docs/ui/audit-log.md' },
  '/analytics': { label: 'Analytics', docPath: 'docs/ui/analytics.md' },
  '/jobs': { label: 'Jobs', docPath: 'docs/ui/jobs.md' },
  '/ai-audit': { label: 'AI Audit', docPath: 'docs/ui/ai-audit.md' },
  '/ai': { label: 'AI Performance', docPath: 'docs/ui/ai-performance.md' },
  '/operations': { label: 'Operations', docPath: 'docs/ui/operations.md' },
  '/trash': { label: 'Trash', docPath: 'docs/ui/trash.md' },
  '/logs': { label: 'Logs', docPath: 'docs/ui/logs.md' },
  '/settings': { label: 'Settings', docPath: 'docs/ui/settings.md' },
};
```

### Component

**New file: `frontend/src/components/layout/PageDocsLink.tsx`**

```typescript
import { useLocation } from 'react-router-dom';
import { BookOpen } from 'lucide-react';
import { PAGE_DOCUMENTATION } from '../../config/pageDocumentation';

const GITHUB_BASE = 'https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/blob/main/';

export function PageDocsLink() {
  const { pathname } = useLocation();
  const pageDoc = PAGE_DOCUMENTATION[pathname];

  // Don't render if no docs configured for this page
  if (!pageDoc) return null;

  const url = `${GITHUB_BASE}${pageDoc.docPath}`;

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium
                 text-[#76B900] hover:text-white hover:bg-[#76B900]/20
                 rounded-md transition-colors"
      title={pageDoc.description}
    >
      <BookOpen className="h-4 w-4" />
      <span className="hidden sm:inline">{pageDoc.label} Documentation</span>
      <span className="sm:hidden">Docs</span>
    </a>
  );
}
```

**Key behaviors:**

- Returns `null` for pages without documentation (e.g., `/dev-tools`)
- Opens in new tab with `noopener noreferrer` for security
- Responsive: "Docs" on mobile, full "{Page} Documentation" on larger screens
- NVIDIA green (#76B900) text with hover state

### Header Integration

**Modify: `frontend/src/components/layout/Header.tsx`**

Add `PageDocsLink` to the left of the "Live Monitoring" indicator:

```tsx
import { PageDocsLink } from './PageDocsLink';

// Inside the Header's right-side flex container:
<div className="flex items-center gap-4">
  {/* New: Contextual documentation link */}
  <PageDocsLink />
  {/* Existing: Live Monitoring indicator */}
  <div className="hidden md:flex items-center gap-2">...</div>
  {/* Existing: System health, GPU stats, etc. */}
  ...
</div>;
```

**Visual layout:**

```
[NVIDIA Logo] .............. [📖 Dashboard Documentation] [● Live Monitoring] [Health] [GPU]
```

### Documentation Template

Each page documentation file follows this structure:

```markdown
# {Page Name}

Overview of the page and its purpose.

## What You're Looking At

Brief plain-language explanation of what the user can accomplish here.

## Key Components

### {Component 1}

Explanation of this UI element, what it shows, how to interact with it.

### {Component 2}

...

## Settings & Configuration

Any configurable options relevant to this page.

## Troubleshooting

Common issues and how to resolve them.

---

## Technical Deep Dive

For those wanting to understand how this works under the hood.

### Architecture

- **Backend:** [Link to relevant architecture doc](../architecture/...)
- **AI:** [Link to AI docs](../architecture/...)

### Related Code

- `frontend/src/pages/...`
- `backend/services/...`
```

## Files to Create

### Documentation (14 files)

| File                        | Page                |
| --------------------------- | ------------------- |
| `docs/ui/README.md`         | Index/overview      |
| `docs/ui/dashboard.md`      | Main dashboard      |
| `docs/ui/timeline.md`       | Event timeline      |
| `docs/ui/entities.md`       | Entity tracking     |
| `docs/ui/alerts.md`         | Alert management    |
| `docs/ui/audit-log.md`      | System audit log    |
| `docs/ui/analytics.md`      | Analytics dashboard |
| `docs/ui/jobs.md`           | Background jobs     |
| `docs/ui/ai-audit.md`       | AI decision audit   |
| `docs/ui/ai-performance.md` | AI model metrics    |
| `docs/ui/operations.md`     | System monitoring   |
| `docs/ui/trash.md`          | Soft-deleted events |
| `docs/ui/logs.md`           | Application logs    |
| `docs/ui/settings.md`       | App configuration   |

### Frontend (2 new, 1 modified)

| File                                              | Action |
| ------------------------------------------------- | ------ |
| `frontend/src/config/pageDocumentation.ts`        | Create |
| `frontend/src/components/layout/PageDocsLink.tsx` | Create |
| `frontend/src/components/layout/Header.tsx`       | Modify |

## Implementation Order

1. **Phase 1: Feature scaffolding**

   - Create `pageDocumentation.ts` config
   - Create `PageDocsLink.tsx` component
   - Integrate into `Header.tsx`
   - Feature works immediately (links may 404 until docs exist)

2. **Phase 2: Documentation**
   - Create `docs/ui/README.md` as index
   - Write documentation files, prioritizing most-used pages:
     1. Dashboard (home page)
     2. Timeline (primary workflow)
     3. Alerts (critical feature)
     4. Settings (configuration reference)
     5. Remaining pages

## Testing

- Unit test for `PageDocsLink`: renders correct label/URL for each route
- Unit test for `PageDocsLink`: returns null for unmapped routes
- Integration test: link appears in Header on navigation
- Manual verification: links resolve to valid GitHub URLs

## Future Considerations

- Could add a "Was this helpful?" feedback mechanism
- Could cache doc content and show preview on hover
- Could integrate with command palette (`Cmd+K` → "View docs")
