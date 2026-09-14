# Types Tests Directory - AI Agent Guide

## Purpose

This directory contains tests for TypeScript type definitions, specifically testing type guards and runtime validation functions that ensure type safety when handling API responses and WebSocket messages.

## Key Files

| File                | Purpose                                      | Lines |
| ------------------- | -------------------------------------------- | ----- |
| `summary.test.ts`   | Tests for Summary type guards                | ~211  |
| `zoneAlert.test.ts` | Tests for zone alert type system             | ~395  |

## What These Tests Cover

### summary.test.ts

Tests type guards for the Summary type used in event summaries:

| Type Guard              | Purpose                                    |
| ----------------------- | ------------------------------------------ |
| `isSummary`             | Validates Summary object structure         |
| `isSummaryUpdateMessage`| Validates WebSocket summary update messages|

**Test Scenarios:**

- Valid summary objects with all required fields
- Objects with additional fields (should pass)
- Null, undefined, and primitive values (should fail)
- Objects missing individual required fields
- Invalid WebSocket message types
- Messages without required `data` property

### zoneAlert.test.ts

Tests the zone alert type system including enums, type guards, and conversion functions:

| Export                      | Type          | Purpose                           |
| --------------------------- | ------------- | --------------------------------- |
| `TrustViolationType`        | Enum          | Trust violation categories        |
| `AlertPriority`             | Enum          | Alert priority levels (0=critical)|
| `TRUST_VIOLATION_TYPE_CONFIG` | Config      | Display config for violation types|
| `severityToPriority`        | Function      | Convert severity to priority enum |
| `isTrustViolationType`      | Type guard    | Validate violation type string    |
| `isTrustViolation`          | Type guard    | Validate TrustViolation object    |
| `isUnifiedZoneAlert`        | Type guard    | Validate UnifiedZoneAlert object  |
| `isAnomalyAlert`            | Type guard    | Check if alert is anomaly-based   |
| `isTrustViolationAlert`     | Type guard    | Check if alert is trust violation |

**Test Scenarios:**

- Enum value correctness
- Priority ordering (CRITICAL < WARNING < INFO)
- Configuration completeness for all enum values
- Severity to priority mapping
- Type guard validation for valid objects
- Type guard rejection of invalid inputs

## Usage Patterns

### Testing Type Guards

```typescript
import { describe, it, expect } from 'vitest';
import { isSummary, Summary } from '../summary';

describe('isSummary type guard', () => {
  it('returns true for valid summary', () => {
    const summary: Summary = {
      id: 1,
      content: 'Test content',
      eventCount: 2,
      windowStart: '2026-01-18T14:00:00Z',
      windowEnd: '2026-01-18T15:00:00Z',
      generatedAt: '2026-01-18T14:55:00Z',
    };

    expect(isSummary(summary)).toBe(true);
  });

  it('returns false for null', () => {
    expect(isSummary(null)).toBe(false);
  });

  it('returns false for object missing required field', () => {
    const partial = { id: 1 }; // Missing other fields
    expect(isSummary(partial)).toBe(false);
  });
});
```

### Testing Enum Values and Ordering

```typescript
import { AlertPriority } from '../zoneAlert';

describe('AlertPriority enum', () => {
  it('maintains correct ordering for sorting', () => {
    const priorities = [AlertPriority.INFO, AlertPriority.CRITICAL, AlertPriority.WARNING];
    const sorted = priorities.sort((a, b) => a - b);

    // CRITICAL (0) should come first
    expect(sorted).toEqual([AlertPriority.CRITICAL, AlertPriority.WARNING, AlertPriority.INFO]);
  });
});
```

### Testing Discriminated Unions

```typescript
import { isAnomalyAlert, isTrustViolationAlert, UnifiedZoneAlert } from '../zoneAlert';

describe('discriminated union type guards', () => {
  it('identifies anomaly alerts', () => {
    const alert: UnifiedZoneAlert = {
      source: 'anomaly',
      // ... other fields
    };

    expect(isAnomalyAlert(alert)).toBe(true);
    expect(isTrustViolationAlert(alert)).toBe(false);
  });
});
```

## Test Patterns

### Exhaustive Null/Undefined Testing

Always test type guards against null, undefined, and primitives:

```typescript
it('returns false for null', () => {
  expect(isSummary(null)).toBe(false);
});

it('returns false for undefined', () => {
  expect(isSummary(undefined)).toBe(false);
});

it('returns false for primitive values', () => {
  expect(isSummary('string')).toBe(false);
  expect(isSummary(123)).toBe(false);
  expect(isSummary(true)).toBe(false);
});
```

### Testing Missing Fields Individually

Test each required field separately to ensure comprehensive validation:

```typescript
it('returns false for object missing id', () => {
  const { id, ...partial } = validObject;
  expect(isValid(partial)).toBe(false);
});

it('returns false for object missing name', () => {
  const { name, ...partial } = validObject;
  expect(isValid(partial)).toBe(false);
});
```

### Testing Configuration Completeness

Ensure all enum values have corresponding configuration:

```typescript
it('has configuration for all types', () => {
  Object.values(TrustViolationType).forEach((type) => {
    const config = TRUST_VIOLATION_TYPE_CONFIG[type];
    expect(config).toBeDefined();
    expect(config.label).toBeTruthy();
    expect(config.description).toBeTruthy();
  });
});
```

## Related Type Files

These tests validate types defined in the parent types directory:

| Type File          | Tested In              |
| ------------------ | ---------------------- |
| `summary.ts`       | `summary.test.ts`      |
| `zoneAlert.ts`     | `zoneAlert.test.ts`    |
| `zoneAnomaly.ts`   | Used in zoneAlert tests|

## Notes for AI Agents

- **Always test null/undefined**: Type guards must handle all falsy values
- **Test missing fields individually**: Each required field needs a separate test
- **Test enum completeness**: Config objects must cover all enum values
- **Test discriminated unions**: Verify source field determines subtype
- **Test ordering for sortable enums**: Priority enums should sort correctly
- **Use realistic test data**: Timestamps, IDs, and values should be realistic
- **Reference Linear issues**: Include `@see NEM-XXXX` in doc comments
