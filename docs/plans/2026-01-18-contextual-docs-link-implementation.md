# Contextual Documentation Link Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a dynamic documentation link to the header that changes based on the current page.

**Architecture:** Route-based configuration maps paths to GitHub doc URLs. A `PageDocsLink` component reads the current route via `useLocation()` and renders a styled link. Component is placed in Header before the health indicator.

**Tech Stack:** React, React Router v7, TypeScript, Tailwind CSS, Lucide icons

---

## Task 1: Create Page Documentation Config

**Files:**

- Create: `frontend/src/config/pageDocumentation.ts`
- Test: `frontend/src/config/pageDocumentation.test.ts`

**Step 1: Write the test**

```typescript
// frontend/src/config/pageDocumentation.test.ts
import { describe, it, expect } from 'vitest';
import { PAGE_DOCUMENTATION, PageDocConfig } from './pageDocumentation';

describe('pageDocumentation', () => {
  it('exports PAGE_DOCUMENTATION config object', () => {
    expect(PAGE_DOCUMENTATION).toBeDefined();
    expect(typeof PAGE_DOCUMENTATION).toBe('object');
  });

  it('has config for dashboard route', () => {
    const config = PAGE_DOCUMENTATION['/'];
    expect(config).toBeDefined();
    expect(config.label).toBe('Dashboard');
    expect(config.docPath).toMatch(/docs\/ui\/dashboard\.md$/);
  });

  it('has config for all main routes', () => {
    const expectedRoutes = [
      '/',
      '/timeline',
      '/entities',
      '/alerts',
      '/audit',
      '/analytics',
      '/jobs',
      '/ai-audit',
      '/ai',
      '/operations',
      '/trash',
      '/logs',
      '/settings',
    ];

    expectedRoutes.forEach((route) => {
      expect(PAGE_DOCUMENTATION[route]).toBeDefined();
      expect(PAGE_DOCUMENTATION[route].label).toBeTruthy();
      expect(PAGE_DOCUMENTATION[route].docPath).toMatch(/^docs\/ui\/.+\.md$/);
    });
  });

  it('does not have config for dev-tools route', () => {
    expect(PAGE_DOCUMENTATION['/dev-tools']).toBeUndefined();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- src/config/pageDocumentation.test.ts`
Expected: FAIL - module not found

**Step 3: Write the implementation**

```typescript
// frontend/src/config/pageDocumentation.ts
export interface PageDocConfig {
  /** Display name shown in link (e.g., "Alerts", "Jobs") */
  label: string;
  /** Path to documentation file relative to repo root */
  docPath: string;
  /** Optional tooltip description */
  description?: string;
}

/**
 * Maps routes to their documentation configuration.
 * Used by PageDocsLink to render contextual help links.
 */
export const PAGE_DOCUMENTATION: Record<string, PageDocConfig> = {
  '/': {
    label: 'Dashboard',
    docPath: 'docs/ui/dashboard.md',
    description: 'Live monitoring and risk overview',
  },
  '/timeline': {
    label: 'Timeline',
    docPath: 'docs/ui/timeline.md',
    description: 'Chronological event history',
  },
  '/entities': {
    label: 'Entities',
    docPath: 'docs/ui/entities.md',
    description: 'Tracked people and objects',
  },
  '/alerts': {
    label: 'Alerts',
    docPath: 'docs/ui/alerts.md',
    description: 'Alert management and configuration',
  },
  '/audit': {
    label: 'Audit Log',
    docPath: 'docs/ui/audit-log.md',
    description: 'System audit trail',
  },
  '/analytics': {
    label: 'Analytics',
    docPath: 'docs/ui/analytics.md',
    description: 'Insights and trends',
  },
  '/jobs': {
    label: 'Jobs',
    docPath: 'docs/ui/jobs.md',
    description: 'Background job monitoring',
  },
  '/ai-audit': {
    label: 'AI Audit',
    docPath: 'docs/ui/ai-audit.md',
    description: 'AI decision explanations',
  },
  '/ai': {
    label: 'AI Performance',
    docPath: 'docs/ui/ai-performance.md',
    description: 'Model metrics and performance',
  },
  '/operations': {
    label: 'Operations',
    docPath: 'docs/ui/operations.md',
    description: 'System health and resources',
  },
  '/trash': {
    label: 'Trash',
    docPath: 'docs/ui/trash.md',
    description: 'Deleted event recovery',
  },
  '/logs': {
    label: 'Logs',
    docPath: 'docs/ui/logs.md',
    description: 'Application log viewer',
  },
  '/settings': {
    label: 'Settings',
    docPath: 'docs/ui/settings.md',
    description: 'Application configuration',
  },
};
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- src/config/pageDocumentation.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/config/pageDocumentation.ts frontend/src/config/pageDocumentation.test.ts
git commit -m "feat: add page documentation config mapping routes to docs"
```

---

## Task 2: Create PageDocsLink Component

**Files:**

- Create: `frontend/src/components/layout/PageDocsLink.tsx`
- Test: `frontend/src/components/layout/PageDocsLink.test.tsx`

**Step 1: Write the test**

```typescript
// frontend/src/components/layout/PageDocsLink.test.tsx
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import { PageDocsLink } from './PageDocsLink';

const renderWithRouter = (initialRoute: string) => {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <PageDocsLink />
    </MemoryRouter>
  );
};

describe('PageDocsLink', () => {
  it('renders dashboard documentation link on root route', () => {
    renderWithRouter('/');

    const link = screen.getByRole('link', { name: /dashboard documentation/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', expect.stringContaining('docs/ui/dashboard.md'));
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('renders alerts documentation link on alerts route', () => {
    renderWithRouter('/alerts');

    const link = screen.getByRole('link', { name: /alerts documentation/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', expect.stringContaining('docs/ui/alerts.md'));
  });

  it('renders jobs documentation link on jobs route', () => {
    renderWithRouter('/jobs');

    const link = screen.getByRole('link', { name: /jobs documentation/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', expect.stringContaining('docs/ui/jobs.md'));
  });

  it('renders nothing for unmapped routes', () => {
    renderWithRouter('/dev-tools');

    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('includes BookOpen icon', () => {
    renderWithRouter('/');

    // The link should contain an svg (the BookOpen icon)
    const link = screen.getByRole('link');
    const svg = link.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });

  it('has NVIDIA green styling', () => {
    renderWithRouter('/');

    const link = screen.getByRole('link');
    expect(link).toHaveClass('text-[#76B900]');
  });

  it('shows short text on mobile (via responsive class)', () => {
    renderWithRouter('/');

    // Check that "Docs" text exists for mobile
    expect(screen.getByText('Docs')).toBeInTheDocument();
    // Check that full text exists for desktop
    expect(screen.getByText(/dashboard documentation/i)).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- src/components/layout/PageDocsLink.test.tsx`
Expected: FAIL - module not found

**Step 3: Write the implementation**

```typescript
// frontend/src/components/layout/PageDocsLink.tsx
import { BookOpen } from 'lucide-react';
import { useLocation } from 'react-router-dom';

import { PAGE_DOCUMENTATION } from '../../config/pageDocumentation';

const GITHUB_BASE_URL =
  'https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/blob/main/';

/**
 * Renders a contextual documentation link based on the current route.
 * The link text and destination change as the user navigates between pages.
 *
 * Returns null for routes without configured documentation.
 */
export function PageDocsLink() {
  const { pathname } = useLocation();
  const pageDoc = PAGE_DOCUMENTATION[pathname];

  // Don't render if no docs configured for this page
  if (!pageDoc) {
    return null;
  }

  const url = `${GITHUB_BASE_URL}${pageDoc.docPath}`;

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-[#76B900] transition-colors hover:bg-[#76B900]/20 hover:text-white"
      title={pageDoc.description}
    >
      <BookOpen className="h-4 w-4" aria-hidden="true" />
      <span className="hidden sm:inline">{pageDoc.label} Documentation</span>
      <span className="sm:hidden">Docs</span>
    </a>
  );
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- src/components/layout/PageDocsLink.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/layout/PageDocsLink.tsx frontend/src/components/layout/PageDocsLink.test.tsx
git commit -m "feat: add PageDocsLink component for contextual documentation"
```

---

## Task 3: Integrate PageDocsLink into Header

**Files:**

- Modify: `frontend/src/components/layout/Header.tsx`
- Modify: `frontend/src/components/layout/Header.test.tsx`

**Step 1: Write the test**

Add to existing Header tests:

```typescript
// Add to frontend/src/components/layout/Header.test.tsx

// Add import at top
import { PAGE_DOCUMENTATION } from '../../config/pageDocumentation';

// Add new describe block
describe('PageDocsLink integration', () => {
  it('renders documentation link in header', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Header />
      </MemoryRouter>
    );

    const docsLink = screen.getByRole('link', { name: /documentation/i });
    expect(docsLink).toBeInTheDocument();
  });

  it('documentation link changes based on route', () => {
    const { rerender } = render(
      <MemoryRouter initialEntries={['/alerts']}>
        <Header />
      </MemoryRouter>
    );

    expect(screen.getByRole('link', { name: /alerts documentation/i })).toBeInTheDocument();

    rerender(
      <MemoryRouter initialEntries={['/jobs']}>
        <Header />
      </MemoryRouter>
    );

    expect(screen.getByRole('link', { name: /jobs documentation/i })).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- src/components/layout/Header.test.tsx`
Expected: FAIL - documentation link not found

**Step 3: Modify Header.tsx**

Add import at top of file (around line 9):

```typescript
import { PageDocsLink } from './PageDocsLink';
```

Add PageDocsLink component inside the right-side flex container, before the health indicator (around line 255):

```tsx
<div className="flex items-center gap-2 px-3 md:gap-6 md:px-6">
  {/* Contextual documentation link */}
  <PageDocsLink />

  {/* System Health Indicator with Tooltip */}
  <div
    ref={containerRef}
    // ... rest of health indicator
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- src/components/layout/Header.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/layout/Header.tsx frontend/src/components/layout/Header.test.tsx
git commit -m "feat: integrate PageDocsLink into Header component"
```

---

## Task 4: Create Documentation Files Scaffold

**Files:**

- Create: `docs/ui/README.md`
- Create: `docs/ui/dashboard.md` (template)

**Step 1: Create docs/ui/README.md**

```markdown
# UI Documentation

Page-specific documentation for the Nemotron Home Security dashboard.

## Pages

| Page                                | Description                                                          |
| ----------------------------------- | -------------------------------------------------------------------- |
| [Dashboard](dashboard.md)           | Main monitoring view with risk gauge, camera grid, and activity feed |
| [Timeline](timeline.md)             | Chronological event history with filtering                           |
| [Entities](entities.md)             | Tracked people and objects                                           |
| [Alerts](alerts.md)                 | Alert configuration and history                                      |
| [Audit Log](audit-log.md)           | System audit trail                                                   |
| [Analytics](analytics.md)           | Insights and trend analysis                                          |
| [Jobs](jobs.md)                     | Background job monitoring                                            |
| [AI Audit](ai-audit.md)             | AI decision explanations                                             |
| [AI Performance](ai-performance.md) | Model metrics and performance                                        |
| [Operations](operations.md)         | System health and resources                                          |
| [Trash](trash.md)                   | Deleted event recovery                                               |
| [Logs](logs.md)                     | Application log viewer                                               |
| [Settings](settings.md)             | Application configuration                                            |

## Documentation Structure

Each page doc follows this structure:

1. **What You're Looking At** - Plain language overview
2. **Key Components** - UI element explanations
3. **Settings & Configuration** - Configurable options
4. **Troubleshooting** - Common issues
5. **Technical Deep Dive** - Architecture links for developers
```

**Step 2: Create docs/ui/dashboard.md (template for other pages)**

```markdown
# Dashboard

The main monitoring view showing real-time security status across all cameras.

## What You're Looking At

The Dashboard is your central hub for home security monitoring. It provides:

- **Risk Gauge** - Current overall threat level (0-100)
- **Camera Grid** - Live status of all connected cameras
- **Activity Feed** - Recent detection events

## Key Components

### Risk Gauge

The circular gauge in the top-left shows the current risk score from 0-100:

- **0-30 (Green)**: Normal activity, no concerns
- **31-60 (Yellow)**: Elevated activity, worth monitoring
- **61-100 (Red)**: High-risk event detected, review immediately

The risk score is calculated by the Nemotron AI model analyzing detected objects, time of day, and historical patterns.

### Camera Grid

Each camera card shows:

- **Camera name** - Location identifier
- **Last activity** - Time since last detection
- **Status indicator** - Green (active), Yellow (idle), Red (offline)

Click any camera to view its recent events in the Timeline.

### Activity Feed

The right panel shows the most recent detection events:

- **Timestamp** - When the event occurred
- **Camera** - Which camera captured it
- **Detection** - What was detected (person, vehicle, animal, etc.)
- **Risk score** - AI-assigned threat level

## Settings & Configuration

Dashboard settings are available in [Settings > Dashboard](settings.md#dashboard):

- **Refresh interval** - How often to poll for updates (default: 5 seconds)
- **Camera grid layout** - Grid size (2x2, 3x3, or auto)
- **Activity feed limit** - Number of recent events to show

## Troubleshooting

### Risk Gauge shows "--"

The AI service may be starting up or disconnected. Check the health indicator in the header.

### Camera shows "Offline"

1. Verify the camera is powered on
2. Check FTP upload settings on the camera
3. Ensure the camera's folder exists at `/export/foscam/{camera_name}/`

### Activity Feed is empty

No events have been detected in the selected time range. Try expanding the time filter.

---

## Technical Deep Dive

For developers wanting to understand the underlying systems.

### Architecture

- **Event Processing**: [AI Pipeline Architecture](../architecture/ai-pipeline.md)
- **AI Risk Scoring**: [Risk Analysis](../developer/risk-analysis.md)
- **Real-time Updates**: [Real-time Architecture](../architecture/real-time.md)

### Related Code

- Frontend: `frontend/src/pages/DashboardPage.tsx`
- Components: `frontend/src/components/dashboard/`
- Backend API: `backend/api/routes/dashboard.py`
- Risk Service: `backend/services/risk_scoring_service.py`
```

**Step 3: Commit**

```bash
git add docs/ui/README.md docs/ui/dashboard.md
git commit -m "docs: add UI documentation scaffold with dashboard template"
```

---

## Task 5: Run Full Validation

**Step 1: Run all frontend tests**

Run: `cd frontend && npm test`
Expected: All tests pass

**Step 2: Run type check**

Run: `cd frontend && npm run typecheck`
Expected: No errors

**Step 3: Run linter**

Run: `cd frontend && npm run lint`
Expected: No errors

**Step 4: Run full validation script**

Run: `./scripts/validate.sh`
Expected: All checks pass

---

## Summary

After completing all tasks:

- **3 new files**: `pageDocumentation.ts`, `PageDocsLink.tsx`, tests
- **1 modified file**: `Header.tsx`
- **2 documentation files**: `docs/ui/README.md`, `docs/ui/dashboard.md`
- **4 commits**: Config, component, integration, docs

The feature will be functional immediately. Remaining documentation files can be added incrementally.
