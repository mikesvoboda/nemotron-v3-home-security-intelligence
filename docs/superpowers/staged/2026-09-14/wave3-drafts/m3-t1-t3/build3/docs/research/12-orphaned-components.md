# Orphaned Frontend Components Analysis

## Executive Summary

Analysis identified **5 orphaned components** that are exported but never imported elsewhere in the codebase. After detailed code review:

- **3 components are VALUABLE** and should be integrated (1,021 lines of production-ready code)
- **2 components are SUPERSEDED** and should be deleted (523 lines of redundant code)

## Updated Assessment

### INTEGRATE: Valuable Components

| Component                | Lines | Integration Target   | Value                             |
| ------------------------ | ----- | -------------------- | --------------------------------- |
| FeedbackPanel            | 390   | EventDetailModal     | AI feedback with calibration      |
| NotificationHistoryPanel | 403   | NotificationSettings | Notification history viewer       |
| BatchProcessingIndicator | 328   | Dashboard header     | Real-time batch processing status |

### DELETE: Superseded Components

| Component       | Lines | Reason                                                     |
| --------------- | ----- | ---------------------------------------------------------- |
| DateRangePicker | 300   | Superseded by DateRangePickerModal & CustomDateRangePicker |
| RetryIndicator  | 223   | Superseded by RetryingIndicator (used in App.tsx)          |

---

## Detailed Analysis

### 1. FeedbackPanel - INTEGRATE ⭐

**Location:** `frontend/src/components/feedback/FeedbackPanel.tsx`

**Features:**

- Complete AI feedback system for event classification
- Calibration field editing (person detection sensitivity, loitering threshold, etc.)
- Feedback submission with useTransition for non-blocking UI
- References: NEM-2353, NEM-3552

**Why it's valuable:**

- Enables users to correct AI classifications, improving model accuracy over time
- Fully implemented with proper error handling and loading states
- Has comprehensive test coverage

**Integration target:** EventDetailModal (the comment says this, but it was never connected)

**Recommendation:** INTEGRATE into EventDetailModal

### 2. NotificationHistoryPanel - INTEGRATE ⭐

**Location:** `frontend/src/components/notifications/NotificationHistoryPanel.tsx`

**Features:**

- Notification delivery history with pagination
- Filter by channel (email, SMS, push, webhook) and status
- Retry failed notifications
- WebSocket integration for real-time updates
- Comprehensive test coverage

**Why it's valuable:**

- Users need visibility into notification delivery status
- Critical for debugging why alerts weren't received
- Fully implemented with proper UX patterns

**Integration target:** NotificationSettings page or dedicated Notification History page

**Recommendation:** INTEGRATE into NotificationSettings

### 3. BatchProcessingIndicator - INTEGRATE ⭐

**Location:** `frontend/src/components/BatchProcessingIndicator.tsx`

**Features:**

- Real-time display of batch processing status
- Shows batch state (idle, collecting, processing, complete)
- Detection count, time remaining, progress bar
- WebSocket integration for live updates
- Reference: NEM-3607

**Why it's valuable:**

- Critical UX - users need to know when AI is processing batches
- Explains why events may not appear immediately
- Fully implemented with proper styling

**Integration target:** Dashboard header or status bar

**Recommendation:** INTEGRATE into dashboard header

### 4. DateRangePicker - DELETE 🗑️

**Location:** `frontend/src/components/DateRangePicker.tsx`

**Evidence:**

- Uses React 19 useTransition pattern
- Two other implementations exist that ARE used:
  - `DateRangePickerModal.tsx` (used in analytics)
  - `CustomDateRangePicker.tsx` (used in event filtering)
- Likely an earlier implementation before more specific versions

**Recommendation:** DELETE (superseded by specific implementations)

### 5. RetryIndicator - DELETE 🗑️

**Location:** `frontend/src/components/RetryIndicator.tsx`

**Evidence:**

- Shows retry countdown for rate limiting
- `RetryingIndicator.tsx` IS actively used in `App.tsx` for WebSocket reconnection
- This is a duplicate/earlier version that was never connected

**Recommendation:** DELETE (superseded by RetryingIndicator)

---

## Action Items

### Files to Delete

```bash
# Superseded components
rm frontend/src/components/DateRangePicker.tsx
rm frontend/src/components/RetryIndicator.tsx

# Test files for deleted components
rm frontend/src/components/DateRangePicker.test.tsx
rm frontend/src/components/RetryIndicator.test.tsx
```

### Files to KEEP and INTEGRATE

```bash
# These are VALUABLE - integrate, don't delete!
frontend/src/components/feedback/FeedbackPanel.tsx          # → EventDetailModal
frontend/src/components/notifications/NotificationHistoryPanel.tsx  # → NotificationSettings
frontend/src/components/BatchProcessingIndicator.tsx        # → Dashboard header
```

### Integration Tasks

1. **FeedbackPanel → EventDetailModal**

   - Add FeedbackPanel as a tab or section in EventDetailModal
   - Wire up feedback submission to API
   - Connect calibration fields to settings

2. **NotificationHistoryPanel → NotificationSettings**

   - Add as new section in NotificationSettings page
   - Or create dedicated /notifications/history route
   - Wire up WebSocket for real-time updates

3. **BatchProcessingIndicator → Dashboard**
   - Add to dashboard header or create status bar component
   - Wire up WebSocket for batch status updates
   - Show only when batch is in progress

---

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
| feedback/       | FeedbackPanel            | **UNUSED - INTEGRATE**   |
| notifications/  | NotificationHistoryPanel | **UNUSED - INTEGRATE**   |
| forms/          | FormField, SubmitButton  | USED (React 19 patterns) |
| logs/           | LogsPage                 | USED                     |
| status/         | AIServiceStatus          | USED (Header)            |
| reports/        | ScheduledReportForm      | USED                     |
| tracing/        | TracingPage              | USED                     |
| video/          | VideoPlayer              | USED                     |
| pyroscope/      | PyroscopePage            | USED                     |

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
