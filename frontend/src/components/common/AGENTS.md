# Common Components

## Purpose

Shared, reusable UI components used throughout the application. These are domain-agnostic primitives that provide consistent styling and behavior.

## Components

### RiskBadge

Displays security risk levels with appropriate color coding, icons, and optional scoring.

**File:** `RiskBadge.tsx`

**Props Interface:**

```typescript
interface RiskBadgeProps {
  level: RiskLevel; // 'low' | 'medium' | 'high' | 'critical'
  score?: number; // Optional numeric risk score (0-100)
  showScore?: boolean; // Display score alongside level (default: false)
  size?: 'sm' | 'md' | 'lg'; // Badge size (default: 'md')
  animated?: boolean; // Enable pulse animation for critical (default: true)
  className?: string; // Additional Tailwind classes
}
```

**Features:**

- Color-coded by risk level:
  - Low: Green (`green-500`)
  - Medium: Yellow (`yellow-500`)
  - High: Orange (`orange-500`)
  - Critical: Red (`red-500`) with pulse animation
- Icon integration via `lucide-react`:
  - Low: CheckCircle
  - Medium/High: AlertTriangle
  - Critical: AlertOctagon
- Responsive sizing (sm/md/lg)
- Accessible with ARIA labels
- Optional score display format: "LEVEL (score)"

**Usage:**

```typescript
import { RiskBadge } from '@/components/common';

<RiskBadge level="critical" score={95} showScore />
<RiskBadge level="low" size="sm" />
```

## Exports

The directory exports components via `index.ts`:

- `RiskBadge` (default export)
- `RiskBadgeProps` (type export)

## Styling Approach

- **Tailwind CSS** utility classes for all styling
- Uses `clsx` for conditional class composition
- Follows dark theme with semi-transparent backgrounds (e.g., `bg-red-500/10`)
- Rounded pill shape (`rounded-full`)
- Inline-flex layout with gap spacing

## Test Files

**Location:** Co-located with components

- `RiskBadge.test.tsx` - Unit tests for risk badge rendering, sizing, colors, and accessibility

**Coverage:** All components must maintain 95% test coverage including:

- Rendering with different props
- Color and icon selection logic
- Accessibility (ARIA labels, semantic HTML)
- Animation behavior
- Edge cases (missing/invalid props)
