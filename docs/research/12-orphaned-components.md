# Orphaned Frontend Components Analysis

## Executive Summary

Analysis identified **5 orphaned components** that are exported but never imported elsewhere in the codebase. These represent dead code that should be deleted.

## Identified Orphaned Components

### 1. FeedbackPanel (HIGH CONFIDENCE - DELETE)

**Location:** `frontend/src/components/feedback/FeedbackPanel.tsx`

**Evidence:**

- Exported from `feedback/index.ts`
- Only references found are in the export barrel file itself
- No imports in any other component or page
- Comment says "for EventDetailModal" but EventDetailModal doesn't import it

**Recommendation:** DELETE

### 2. NotificationHistoryPanel (HIGH CONFIDENCE - DELETE)

**Location:** `frontend/src/components/notifications/NotificationHistoryPanel.tsx`

**Evidence:**

- Exported from `notifications/index.ts`
- Only references are in export barrel and test files
- Never imported elsewhere in the codebase
- Has comprehensive test coverage suggesting it was planned but not integrated

**Recommendation:** DELETE

### 3. BatchProcessingIndicator (MEDIUM-HIGH CONFIDENCE - DELETE)

**Location:** `frontend/src/components/BatchProcessingIndicator.tsx` (root components)

**Evidence:**

- No imports found outside of test files
- Exported as root component but never used
- Has test file (`BatchProcessingIndicator.test.tsx`)
- Comment suggests it should show "real-time batch processing status"

**Recommendation:** DELETE (or move to appropriate directory and integrate if planned feature)

### 4. DateRangePicker (MEDIUM CONFIDENCE - DELETE)

**Location:** `frontend/src/components/DateRangePicker.tsx` (root components)

**Evidence:**

- Root-level component with test file
- Not imported anywhere in the application
- Similar components exist that ARE used:
  - `DateRangePickerModal`
  - `CustomDateRangePicker`
- Likely superseded by more specific implementations

**Recommendation:** DELETE (replaced by specific implementations)

### 5. RetryIndicator (LOW CONFIDENCE - DELETE)

**Location:** `frontend/src/components/RetryIndicator.tsx`

**Evidence:**

- Has test file but no imports found
- Similar component `RetryingIndicator` IS used in App.tsx
- May have been an earlier version before RetryingIndicator

**Recommendation:** DELETE (keep RetryingIndicator which is in use)

## Summary Table

| Component                | Confidence  | Reason                          | Action |
| ------------------------ | ----------- | ------------------------------- | ------ |
| FeedbackPanel            | HIGH        | Exported but never imported     | DELETE |
| NotificationHistoryPanel | HIGH        | Exported but never imported     | DELETE |
| BatchProcessingIndicator | MEDIUM-HIGH | Never integrated                | DELETE |
| DateRangePicker          | MEDIUM      | Superseded                      | DELETE |
| RetryIndicator           | MEDIUM      | Superseded by RetryingIndicator | DELETE |

## Components with Limited But Valid Usage

These components are used but in limited contexts (not orphaned):

| Component               | Usage              | Notes                    |
| ----------------------- | ------------------ | ------------------------ |
| ExportButton            | EventTimeline only | Valid, specific use case |
| AIPerformanceSummaryRow | DashboardPage only | Valid, dashboard widget  |
| VideoPlayer             | EventDetailModal   | Valid, video playback    |

## Single-Component Directories

These directories export only one or two components and may indicate incomplete features:

| Directory       | Components               | Status                   |
| --------------- | ------------------------ | ------------------------ |
| ai-performance/ | AIPerformanceSummaryRow  | USED                     |
| feedback/       | FeedbackPanel            | **UNUSED**               |
| notifications/  | NotificationHistoryPanel | **UNUSED**               |
| forms/          | FormField, SubmitButton  | USED (React 19 patterns) |
| logs/           | LogsPage                 | USED                     |
| status/         | AIServiceStatus          | USED (Header)            |
| reports/        | ScheduledReportForm      | USED                     |
| tracing/        | TracingPage              | USED                     |
| video/          | VideoPlayer              | USED                     |
| pyroscope/      | PyroscopePage            | USED                     |

## Cleanup Actions

### Files to Delete

```bash
# Components
rm frontend/src/components/feedback/FeedbackPanel.tsx
rm frontend/src/components/notifications/NotificationHistoryPanel.tsx
rm frontend/src/components/BatchProcessingIndicator.tsx
rm frontend/src/components/DateRangePicker.tsx
rm frontend/src/components/RetryIndicator.tsx

# Test files
rm frontend/src/components/feedback/FeedbackPanel.test.tsx
rm frontend/src/components/notifications/NotificationHistoryPanel.test.tsx
rm frontend/src/components/BatchProcessingIndicator.test.tsx
rm frontend/src/components/DateRangePicker.test.tsx
rm frontend/src/components/RetryIndicator.test.tsx
```

### Export Barrel Updates

Update `feedback/index.ts`:

```typescript
// Remove: export { FeedbackPanel } from './FeedbackPanel';
```

Update `notifications/index.ts`:

```typescript
// Remove: export { NotificationHistoryPanel } from './NotificationHistoryPanel';
```

## Automated Detection

Run `npm run dead-code` (knip) to catch additional unused exports and dependencies:

```bash
cd frontend && npx knip
```

This will identify:

- Unused exports
- Unused dependencies
- Unused type exports
- Files not referenced anywhere

## Prevention

To prevent future orphaned components:

1. **Use knip in CI** - Add dead code detection to CI pipeline
2. **Review barrel exports** - Ensure all exports are imported somewhere
3. **Delete test files with components** - When removing components, remove tests too
4. **Document incomplete features** - If a component is planned but not integrated, add a TODO
