# PWA Components

## Purpose

Progressive Web App (PWA) components for the NVIDIA Security Intelligence dashboard. Provides install prompts, offline support, and service worker integration for an app-like experience.

## Key Components

| File                    | Purpose                                    |
| ----------------------- | ------------------------------------------ |
| `InstallPrompt.tsx`     | PWA install prompt banner component        |
| `InstallPrompt.test.tsx`| Test suite for InstallPrompt               |
| `index.ts`              | Barrel exports for PWA components          |

## Component Details

### InstallPrompt

A custom PWA install banner that captures the `beforeinstallprompt` event and displays after user engagement criteria are met.

**Props:**

| Prop                   | Type       | Default   | Description                                          |
| ---------------------- | ---------- | --------- | ---------------------------------------------------- |
| `minVisits`            | `number?`  | `2`       | Minimum number of visits before showing the prompt   |
| `minTimeOnSite`        | `number?`  | `30000`   | Minimum time on site (ms) before showing the prompt  |
| `dismissCooldownDays`  | `number?`  | `7`       | Days to wait after dismissal before showing again    |
| `className`            | `string?`  | -         | Additional CSS classes to apply to the banner        |

**Features:**

- **Event Capture:** Intercepts the browser's `beforeinstallprompt` event
- **Engagement Criteria:** Shows banner only after configurable visit count and time thresholds
- **Persistent State:** Tracks visits, dismissals, and installation via localStorage
- **Dismissal Cooldown:** Respects user dismissal with configurable cooldown period
- **Installation Tracking:** Records successful installations
- **WCAG 2.1 AA Compliant:** Proper ARIA roles and labels

**localStorage Keys:**

| Key                    | Purpose                          |
| ---------------------- | -------------------------------- |
| `pwa-visit-count`      | Number of site visits            |
| `pwa-install-dismissed`| Timestamp of last dismissal      |
| `pwa-installed`        | Whether app has been installed   |

**Types Exported:**

```typescript
interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{
    outcome: 'accepted' | 'dismissed';
    platform: string;
  }>;
}

interface InstallPromptProps {
  minVisits?: number;
  minTimeOnSite?: number;
  dismissCooldownDays?: number;
  className?: string;
}
```

**Usage:**

```tsx
import { InstallPrompt } from '@/components/pwa';

// Basic usage - shows after 2 visits and 30 seconds
<InstallPrompt />

// Custom thresholds
<InstallPrompt minVisits={3} minTimeOnSite={60000} />

// Immediate show (for testing)
<InstallPrompt minVisits={0} minTimeOnSite={0} />
```

## Test Coverage

The test suite covers:

- **Rendering:** Nothing renders initially without event, nothing with event if criteria not met
- **Visit Criteria:** Shows after minimum visits, increments visit count, threshold enforcement
- **Time Criteria:** Shows after minimum time on site, threshold enforcement
- **Combined Criteria:** Both visit and time requirements
- **Dismissal:** Hides banner, stores in localStorage, respects cooldown period
- **Installation Flow:** Calls prompt(), stores installed state, hides banner on success/dismissal
- **Already Installed:** Does not show if already installed
- **Content Display:** App name, benefits, install/dismiss buttons
- **Accessibility:** ARIA role, aria-labelledby, aria-hidden on decorative elements
- **Styling:** Fixed positioning, custom className support
- **Cleanup:** Event listener cleanup on unmount
- **Default Props:** Default minVisits (2) and minTimeOnSite (30000ms)

## Dependencies

- `clsx` - Conditional class composition
- `lucide-react` - Icons (Smartphone, X)
- `../common/Button` - Shared button component

## Styling

Uses Tailwind CSS with NVIDIA dark theme:

- Fixed position: `fixed bottom-4 left-4 right-4`
- Responsive: `md:left-auto md:right-4 md:w-96`
- Background: `bg-gray-800`
- Border: `border-gray-700`
- NVIDIA green accent: `#76B900` for the smartphone icon
- Icon container: `bg-gray-700` rounded circle
