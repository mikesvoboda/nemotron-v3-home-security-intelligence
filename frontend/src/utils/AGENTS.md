# Frontend Utils Directory

## Purpose

Utility functions for common operations across the frontend application, including risk scoring and time/duration formatting.

## Key Files

| File           | Purpose                                    |
| -------------- | ------------------------------------------ |
| `risk.ts`      | Risk scoring utilities for security events |
| `risk.test.ts` | Tests for risk utilities                   |
| `time.ts`      | Time and duration formatting utilities     |
| `time.test.ts` | Tests for time utilities                   |

## Risk Utilities (`risk.ts`)

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

```typescript
getRiskLevel(25); // 'low'
getRiskLevel(26); // 'medium'
getRiskLevel(75); // 'high'
getRiskLevel(76); // 'critical'
```

#### `getRiskColor(level: RiskLevel): string`

Returns hex color code for a risk level, using NVIDIA brand colors.

| Level      | Color    | Hex       |
| ---------- | -------- | --------- |
| `low`      | Green    | `#76B900` |
| `medium`   | Yellow   | `#FFB800` |
| `high`     | Red      | `#E74856` |
| `critical` | Dark Red | `#ef4444` |

```typescript
getRiskColor('high'); // '#E74856'
```

#### `getRiskLabel(level: RiskLevel): string`

Returns capitalized human-readable label for a risk level.

```typescript
getRiskLabel('medium'); // 'Medium'
getRiskLabel('critical'); // 'Critical'
```

## Time Utilities (`time.ts`)

### Functions

#### `formatDuration(startedAt: string, endedAt: string | null): string`

Format duration between two timestamps in human-readable format.

**Parameters:**

- `startedAt` - ISO timestamp string when event started
- `endedAt` - ISO timestamp string when event ended (null if ongoing)

**Behavior:**

- Ongoing events (started within last 5 minutes): returns `"ongoing"`
- Ongoing events (older than 5 minutes): returns `"2h 30m (ongoing)"`
- Completed events: returns duration like `"2m 30s"`, `"1h 15m"`, `"2d 5h"`
- Invalid dates: returns `"unknown"`
- Negative durations: returns `"0s"`

**Duration Formatting Rules:**

- Days + hours for durations over a day: `"2d 5h"`
- Hours + minutes for durations over an hour: `"1h 15m"`
- Minutes + seconds for durations over a minute: `"2m 30s"`
- Seconds only for durations under a minute: `"45s"`

```typescript
formatDuration('2024-01-01T10:00:00Z', '2024-01-01T10:02:30Z'); // "2m 30s"
formatDuration('2024-01-01T10:00:00Z', null); // "ongoing" (if recent)
```

#### `getDurationLabel(startedAt: string, endedAt: string | null): string`

Alias for `formatDuration()` - provides consistent API for duration display.

#### `isEventOngoing(endedAt: string | null): boolean`

Check if an event is currently ongoing.

```typescript
isEventOngoing(null); // true
isEventOngoing('2024-01-01T10:00:00Z'); // false
```

## Testing

### `risk.test.ts`

Covers:

- Score to level conversion for all thresholds
- Boundary conditions (0, 25, 50, 75, 100)
- Error handling for invalid scores (-1, 101)
- Color mapping for all levels including critical
- Label generation for all levels

### `time.test.ts`

Covers:

- Duration formatting for various time ranges
- Ongoing event handling (recent vs older)
- Invalid date handling
- Negative duration handling
- Edge cases (exactly 1 minute, exactly 1 hour, etc.)

## Usage Examples

### Display Risk Badge

```tsx
import { getRiskLevel, getRiskColor, getRiskLabel } from '@/utils/risk';

function RiskBadge({ score }: { score: number }) {
  const level = getRiskLevel(score);
  const color = getRiskColor(level);
  const label = getRiskLabel(level);

  return (
    <span className={\`risk-badge-\${level}\`} style={{ borderColor: color }}>
      {label}: {score}
    </span>
  );
}
```

### Display Event Duration

```tsx
import { formatDuration, isEventOngoing } from '@/utils/time';

function EventDuration({ event }: { event: Event }) {
  const duration = formatDuration(event.started_at, event.ended_at);
  const ongoing = isEventOngoing(event.ended_at);

  return <span className={ongoing ? 'text-primary-500' : 'text-text-secondary'}>{duration}</span>;
}
```

### Filter High-Risk Events

```typescript
import { getRiskLevel } from '@/utils/risk';

const highRiskEvents = events.filter((event) => {
  const level = getRiskLevel(event.risk_score);
  return level === 'high' || level === 'critical';
});
```

## Utility Patterns

### Pure Functions

All utility functions are pure with no side effects:

- Same input always produces same output
- No external state modifications
- No async operations
- Easily testable and composable

### Error Handling

**Risk functions** throw on invalid input for fail-fast behavior:

```typescript
try {
  getRiskLevel(150); // Throws: "Risk score must be between 0 and 100"
} catch (e) {
  // Handle invalid score
}
```

**Time functions** return safe defaults for invalid input:

```typescript
formatDuration('invalid', null); // Returns "unknown"
formatDuration('2024-01-01T10:00:00Z', '2024-01-01T09:00:00Z'); // Returns "0s" (negative)
```

## Notes

- Risk levels align with Tailwind CSS risk badge classes (`.risk-badge-low`, `.risk-badge-critical`, etc.)
- Risk colors use NVIDIA brand palette for consistency with the theme
- Score validation ensures type safety at runtime
- Thresholds are inclusive: 25 is `low`, 26 is `medium`
- Time utilities handle ISO 8601 timestamp strings
- Ongoing event detection uses 5-minute threshold for "ongoing" vs duration display

## Entry Points

For AI agents exploring this codebase:

1. **Risk utilities**: `risk.ts` - Score-to-level conversion, colors, labels
2. **Time utilities**: `time.ts` - Duration formatting, ongoing event detection
3. **Tests**: Each utility has a `.test.ts` file with comprehensive examples
