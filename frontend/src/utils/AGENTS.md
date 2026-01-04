# Frontend Utils Directory

## Purpose

Utility functions for common operations across the frontend application, including risk scoring, confidence levels, and time/duration formatting.

## Key Files

| File                  | Purpose                                              |
| --------------------- | ---------------------------------------------------- |
| `index.ts`            | Barrel export for all utility modules                |
| `risk.ts`             | Risk scoring utilities for security events           |
| `risk.test.ts`        | Tests for risk utilities                             |
| `confidence.ts`       | Detection confidence level utilities                 |
| `confidence.test.ts`  | Tests for confidence utilities                       |
| `time.ts`             | Time and duration formatting utilities               |
| `time.test.ts`        | Tests for time utilities                             |
| `webcodecs.ts`        | WebCodecs API feature detection and fallback helpers |
| `webcodecs.test.ts`   | Tests for WebCodecs utilities                        |

## Risk Utilities (`risk.ts`)

### Types

```typescript
type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

// Configurable thresholds matching backend defaults
const RISK_THRESHOLDS = {
  LOW_MAX: 29, // 0-29 = Low
  MEDIUM_MAX: 59, // 30-59 = Medium
  HIGH_MAX: 84, // 60-84 = High
  // 85-100 = Critical
} as const;
```

### Functions

#### `getRiskLevel(score: number): RiskLevel`

Converts numeric risk score (0-100) to categorical risk level using default thresholds.

**Default Thresholds (matching backend SeverityService):**

- 0-29: `low`
- 30-59: `medium`
- 60-84: `high`
- 85-100: `critical`

**Note:** Thresholds are configurable on backend via environment variables (`SEVERITY_LOW_MAX`, `SEVERITY_MEDIUM_MAX`, `SEVERITY_HIGH_MAX`). Use `getRiskLevelWithThresholds()` for dynamic threshold support.

**Throws:** Error if score is outside 0-100 range

```typescript
getRiskLevel(29); // 'low'
getRiskLevel(30); // 'medium'
getRiskLevel(84); // 'high'
getRiskLevel(85); // 'critical'
```

#### `getRiskLevelWithThresholds(score, thresholds): RiskLevel`

Converts score to risk level using custom thresholds fetched from backend API.

```typescript
// Fetch dynamic thresholds from GET /api/system/severity
const thresholds = { low_max: 29, medium_max: 59, high_max: 84 };
getRiskLevelWithThresholds(50, thresholds); // 'medium'
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

## Confidence Utilities (`confidence.ts`)

### Types

```typescript
type ConfidenceLevel = 'low' | 'medium' | 'high';
```

### Functions

#### `getConfidenceLevel(confidence: number): ConfidenceLevel`

Converts detection confidence score (0.0-1.0) to categorical level.

**Thresholds:**

- 0.0-0.69: `low`
- 0.70-0.84: `medium`
- 0.85-1.0: `high`

**Throws:** Error if confidence is outside 0.0-1.0 range

```typescript
getConfidenceLevel(0.5); // 'low'
getConfidenceLevel(0.75); // 'medium'
getConfidenceLevel(0.9); // 'high'
```

#### `getConfidenceColor(level: ConfidenceLevel): string`

Returns hex color code for a confidence level.

| Level    | Color  | Hex       |
| -------- | ------ | --------- |
| `low`    | Red    | `#E74856` |
| `medium` | Yellow | `#FFB800` |
| `high`   | Green  | `#76B900` |

#### `getConfidenceTextColorClass(level): string`

Returns Tailwind text color class.

```typescript
getConfidenceTextColorClass('high'); // 'text-green-400'
```

#### `getConfidenceBgColorClass(level): string`

Returns Tailwind background color class with transparency.

```typescript
getConfidenceBgColorClass('medium'); // 'bg-yellow-500/20'
```

#### `getConfidenceBorderColorClass(level): string`

Returns Tailwind border color class.

```typescript
getConfidenceBorderColorClass('low'); // 'border-red-500/40'
```

#### `getConfidenceLabel(level): string`

Returns human-readable label.

```typescript
getConfidenceLabel('high'); // 'High Confidence'
```

#### `formatConfidencePercent(confidence): string`

Formats confidence as percentage string.

```typescript
formatConfidencePercent(0.95); // '95%'
```

#### Array Operations

```typescript
// Calculate average confidence
calculateAverageConfidence(detections); // number | null

// Get maximum confidence
calculateMaxConfidence(detections); // number | null

// Sort detections by confidence (highest first)
sortDetectionsByConfidence(detections); // T[]

// Filter by minimum confidence threshold
filterDetectionsByConfidence(detections, 0.7); // T[]
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

- Risk levels align with Tailwind CSS risk badge classes (`.risk-badge-low`, `.risk-badge-high`, etc.)
- Risk colors use NVIDIA brand palette for consistency with the theme
- Score validation ensures type safety at runtime
- Default thresholds match backend SeverityService: Low (0-29), Medium (30-59), High (60-84), Critical (85-100)
- Use `getRiskLevelWithThresholds()` if backend has custom thresholds configured
- Time utilities handle ISO 8601 timestamp strings
- Ongoing event detection uses 5-minute threshold for "ongoing" vs duration display
- Confidence utilities are for detection confidence (0.0-1.0), not risk scores (0-100)

## WebCodecs Utilities (`webcodecs.ts`)

Feature detection and fallback utilities for the WebCodecs API, which requires a secure context (HTTPS, localhost, or file://).

### Functions

#### `isSecureContext(): boolean`

Checks if the current browsing context is secure (HTTPS, localhost, 127.0.0.1, or file://).

#### `isVideoDecoderSupported(): boolean`

Checks if the VideoDecoder API is available (requires secure context).

#### `isVideoEncoderSupported(): boolean`

Checks if the VideoEncoder API is available (requires secure context).

#### `isAudioDecoderSupported(): boolean`

Checks if the AudioDecoder API is available (requires secure context).

#### `isAudioEncoderSupported(): boolean`

Checks if the AudioEncoder API is available (requires secure context).

#### `isWebCodecsSupported(): boolean`

Checks if the full WebCodecs API is available (all decoder/encoder APIs).

#### `getWebCodecsCapabilities(): WebCodecsCapabilities`

Returns an object with boolean flags for each WebCodecs API capability.

```typescript
interface WebCodecsCapabilities {
  secureContext: boolean;
  videoDecoder: boolean;
  videoEncoder: boolean;
  audioDecoder: boolean;
  audioEncoder: boolean;
}
```

**Use Cases:**

- Graceful degradation for video playback features
- Feature detection before using WebCodecs for video processing
- Fallback to alternative video handling methods in non-secure contexts

## Entry Points

For AI agents exploring this codebase:

1. **Risk utilities**: `risk.ts` - Score-to-level conversion with configurable thresholds, colors, labels
2. **Confidence utilities**: `confidence.ts` - Detection confidence levels, colors, Tailwind classes, array helpers
3. **Time utilities**: `time.ts` - Duration formatting, ongoing event detection
4. **WebCodecs utilities**: `webcodecs.ts` - Browser API feature detection for secure context requirements
5. **Tests**: Each utility has a `.test.ts` file with comprehensive examples
