# Frontend Utils Directory

## Purpose

Utility functions for common operations across the frontend application.

## Key Files

### `risk.ts`

Risk scoring utilities for security events.

## Risk Utilities

### Types

```typescript
type RiskLevel = 'low' | 'medium' | 'high' | 'critical';
```

### Functions

#### `getRiskLevel(score: number): RiskLevel`

Converts numeric risk score (0-100) to categorical risk level.

**Thresholds:**

- 0-25: `low`
- 26-50: `medium`
- 51-75: `high`
- 76-100: `critical`

**Throws:** Error if score is outside 0-100 range

**Usage:**

```typescript
const level = getRiskLevel(45); // 'medium'
```

#### `getRiskColor(level: RiskLevel): string`

Returns hex color code for a risk level.

**Color Mapping:**

- `low`: `#22c55e` (green-500)
- `medium`: `#eab308` (yellow-500)
- `high`: `#f97316` (orange-500)
- `critical`: `#ef4444` (red-500)

**Usage:**

```typescript
const color = getRiskColor('high'); // '#f97316'
```

#### `getRiskLabel(level: RiskLevel): string`

Returns capitalized human-readable label for a risk level.

**Label Mapping:**

- `low` → `"Low"`
- `medium` → `"Medium"`
- `high` → `"High"`
- `critical` → `"Critical"`

**Usage:**

```typescript
const label = getRiskLabel('medium'); // 'Medium'
```

## Testing

### `risk.test.ts`

Comprehensive test coverage including:

- Score to level conversion for all thresholds
- Boundary conditions (0, 25, 50, 75, 100)
- Error handling for invalid scores (-1, 101)
- Color mapping for all levels
- Label generation for all levels

**Test Framework:** Vitest

## Usage Examples

### Display Risk Badge

```tsx
import { getRiskLevel, getRiskColor, getRiskLabel } from '@/utils/risk';

function RiskBadge({ score }: { score: number }) {
  const level = getRiskLevel(score);
  const color = getRiskColor(level);
  const label = getRiskLabel(level);

  return (
    <span className={`risk-badge-${level}`} style={{ borderColor: color }}>
      {label}: {score}
    </span>
  );
}
```

### Sort Events by Risk

```typescript
import { getRiskLevel } from '@/utils/risk';

const events = [...];
const sortedEvents = events.sort((a, b) => {
  const levelOrder = { low: 0, medium: 1, high: 2, critical: 3 };
  const aLevel = getRiskLevel(a.risk_score);
  const bLevel = getRiskLevel(b.risk_score);
  return levelOrder[bLevel] - levelOrder[aLevel];
});
```

### Filter High-Risk Events

```typescript
import { getRiskLevel } from '@/utils/risk';

const highRiskEvents = events.filter((event) => {
  const level = getRiskLevel(event.risk_score);
  return level === 'high' || level === 'critical';
});
```

## Notes

- Risk levels align with Tailwind CSS risk badge classes (`.risk-badge-low`, etc.)
- Color codes match Tailwind's color palette for consistency
- Score validation ensures type safety at runtime
- Pure functions with no side effects (easily testable)
- Thresholds are inclusive: 25 is `low`, 26 is `medium`
