# Theme Module

This module centralizes all color constants and theme-related utilities for WCAG 2.1 AA compliance.

## Purpose

- **Centralize color definitions** - Single source of truth for status colors
- **WCAG compliance** - All colors meet 4.5:1 contrast ratio requirements
- **Semantic naming** - Color names describe purpose, not appearance
- **Multiple formats** - Tremor colors, Tailwind classes, and hex values

## Key Files

| File | Purpose |
|------|---------|
| `colors.ts` | All status color constants and utility functions |
| `colors.test.ts` | Comprehensive tests for color constants |
| `index.ts` | Module re-exports |

## Status Colors

### Semantic Mapping

| Semantic Status | Tremor Color | Why |
|-----------------|--------------|-----|
| healthy/online | `emerald` | Better contrast than `green` (4.5:1 vs 3.8:1) |
| warning/degraded | `yellow` | Standard warning color |
| error/offline/unhealthy | `red` | Standard error color |
| inactive/unknown | `gray` | Neutral for unknown states |

### Color Types Available

1. **Tremor Colors** (`STATUS_COLORS`)
   ```tsx
   import { STATUS_COLORS } from '@/theme/colors';
   <Badge color={STATUS_COLORS.healthy}>Healthy</Badge>
   ```

2. **Tailwind Background Classes** (`STATUS_BG_CLASSES`, `STATUS_BG_LIGHT_CLASSES`)
   ```tsx
   import { STATUS_BG_CLASSES, STATUS_BG_LIGHT_CLASSES } from '@/theme/colors';
   <div className={STATUS_BG_CLASSES.error}>Solid background</div>
   <div className={STATUS_BG_LIGHT_CLASSES.warning}>10% opacity background</div>
   ```

3. **Tailwind Text Classes** (`STATUS_TEXT_CLASSES`)
   ```tsx
   import { STATUS_TEXT_CLASSES } from '@/theme/colors';
   <span className={STATUS_TEXT_CLASSES.healthy}>Healthy</span>
   ```

4. **Tailwind Border Classes** (`STATUS_BORDER_CLASSES`)
   ```tsx
   import { STATUS_BORDER_CLASSES } from '@/theme/colors';
   <div className={`border ${STATUS_BORDER_CLASSES.error}`}>Error border</div>
   ```

5. **Hex Colors** (`STATUS_HEX_COLORS`)
   ```tsx
   import { STATUS_HEX_COLORS } from '@/theme/colors';
   // For charts, Canvas, or programmatic use
   ctx.fillStyle = STATUS_HEX_COLORS.healthy; // '#10B981'
   ```

## Utility Functions

### getStatusColor(status)
Returns Tremor color name for any status string.

```tsx
import { getStatusColor } from '@/theme/colors';

// Direct status
<Badge color={getStatusColor('healthy')}>Healthy</Badge>

// Handles aliases
<Badge color={getStatusColor('ok')}>OK</Badge>  // Returns 'emerald'
<Badge color={getStatusColor('fail')}>Fail</Badge>  // Returns 'red'
```

### getStatusClasses(status)
Returns all Tailwind class types for a status.

```tsx
import { getStatusClasses } from '@/theme/colors';

const classes = getStatusClasses('error');
<div className={`${classes.bgLightClass} ${classes.borderClass} border`}>
  <span className={classes.textClass}>Error message</span>
</div>
```

### getQueueStatusColor(depth, threshold)
Returns color based on queue depth relative to threshold.

```tsx
import { getQueueStatusColor } from '@/theme/colors';

// depth=0 -> 'gray' (empty)
// depth <= threshold/2 -> 'emerald' (normal)
// depth <= threshold -> 'yellow' (elevated)
// depth > threshold -> 'red' (critical)
<Badge color={getQueueStatusColor(currentDepth, 10)}>{currentDepth}</Badge>
```

### getLatencyStatusColor(ms, threshold)
Returns color based on latency relative to threshold.

```tsx
import { getLatencyStatusColor } from '@/theme/colors';

// null/undefined -> 'gray' (unknown)
// ms < threshold/2 -> 'emerald' (fast)
// ms < threshold -> 'yellow' (normal)
// ms >= threshold -> 'red' (slow)
<Badge color={getLatencyStatusColor(latencyMs, 1000)}>{latencyMs}ms</Badge>
```

## Tailwind Config Integration

The `tailwind.config.js` also includes semantic status colors:

```css
/* Available classes */
bg-status-healthy
bg-status-healthy-light
text-status-healthy-text
border-status-healthy-border

bg-status-warning
bg-status-error
bg-status-inactive
```

## WCAG 2.1 AA Compliance

All colors in this module are designed to meet WCAG 2.1 AA requirements:

- **4.5:1 contrast ratio** for normal text
- **3:1 contrast ratio** for large text (18pt+ or 14pt+ bold)

### Why Emerald Instead of Green

The default Tailwind `green-500` (#22c55e) only achieves ~3.8:1 contrast on our dark background (#1A1A1A), which fails WCAG AA for normal text. `emerald-500` (#10B981) achieves 4.6:1 contrast, meeting the requirement.

### Text Color Shade Selection

We use the `-400` shade for text colors on dark backgrounds because:
- `-500` shades are optimized for white backgrounds
- `-400` shades provide better contrast on dark backgrounds (#1A1A1A)

## Testing

```bash
cd frontend && npm test -- src/theme/colors.test.ts
```

Tests verify:
- All status mappings are correct
- Alias handling works (ok -> healthy, fail -> error, etc.)
- Case insensitivity and whitespace trimming
- Queue and latency threshold logic
- WCAG compliance notes

## Migration Guide

### From Hardcoded Colors

Before:
```tsx
function getStatusBadgeColor(status: string) {
  if (status === 'healthy') return 'green';  // Wrong! Use emerald
  if (status === 'warning') return 'yellow';
  return 'gray';
}
```

After:
```tsx
import { getStatusColor } from '@/theme/colors';

<Badge color={getStatusColor(status)}>{status}</Badge>
```

### From Inline Tailwind Classes

Before:
```tsx
<div className="bg-green-500/10 border-green-500/30 text-green-400">
  Healthy
</div>
```

After:
```tsx
import { getStatusClasses } from '@/theme/colors';

const classes = getStatusClasses('healthy');
<div className={`${classes.bgLightClass} border ${classes.borderClass} ${classes.textClass}`}>
  Healthy
</div>
```

## Related Files

- `/frontend/tailwind.config.js` - Contains extended status colors for Tailwind
- `/frontend/src/utils/risk.ts` - Risk-level specific colors (different from status)
- `/frontend/src/utils/confidence.ts` - Confidence-level specific colors
