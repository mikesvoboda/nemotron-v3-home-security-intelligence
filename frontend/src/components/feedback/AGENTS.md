# Feedback Components Directory

## Purpose

Contains React components for event feedback functionality, enabling users to provide classification feedback on AI detections. This feedback helps improve AI accuracy by training the system to recognize false positives, missed threats, and severity miscalculations.

## Files

| File                      | Purpose                                           |
| ------------------------- | ------------------------------------------------- |
| `FeedbackPanel.tsx`       | Feedback submission panel for event detail modal  |
| `FeedbackPanel.test.tsx`  | Test suite for FeedbackPanel                      |

## Key Components

### FeedbackPanel.tsx

**Purpose:** Displays feedback buttons and form for event classification feedback

**Key Features:**

- Four feedback types with distinctive styling:
  - **Accurate** (green): Detection was correct
  - **False Positive** (red): Event was incorrectly flagged
  - **Missed Threat** (orange): System failed to detect a threat
  - **Severity Wrong** (yellow): Risk level was incorrect
- Quick feedback for "Accurate" (no notes required)
- Notes form for other feedback types
- Existing feedback display (read-only)
- Loading, error, and success states
- Query invalidation for real-time updates

**Layout - Initial State:**

```
+------------------------------------------+
|  DETECTION FEEDBACK                      |
|  Help improve AI accuracy by providing   |
|  feedback on this detection.             |
+------------------------------------------+
|  [Accurate] [False Positive]             |
|  [Missed Threat] [Severity Wrong]        |
+------------------------------------------+
```

**Layout - Notes Form:**

```
+------------------------------------------+
|  False Positive                      [X] |
+------------------------------------------+
|  Additional notes (optional)             |
|  [________________________]              |
|  [________________________]              |
|                              0/1000      |
+------------------------------------------+
|  [Cancel]        [Submit Feedback]       |
+------------------------------------------+
```

**Layout - Existing Feedback:**

```
+------------------------------------------+
|  [check] Accurate                        |
|  Submitted 1/15/2024                     |
+------------------------------------------+
```

**Props Interface:**

```typescript
interface FeedbackPanelProps {
  /** Event ID to submit feedback for */
  eventId: number;
  /** Current risk score of the event (0-100) */
  currentRiskScore?: number;
  /** Optional CSS class name */
  className?: string;
  /** Callback when feedback is successfully submitted */
  onFeedbackSubmitted?: (feedback: EventFeedbackResponse) => void;
}
```

**Related:** NEM-2353

## Types

### FeedbackType

Feedback classification types:

```typescript
type FeedbackType = 'accurate' | 'false_positive' | 'missed_threat' | 'severity_wrong';
```

### FeedbackOption

Configuration for each feedback button:

```typescript
interface FeedbackOption {
  type: FeedbackType;
  label: string;
  icon: React.ElementType;
  description: string;
  colorClass: string;
  bgClass: string;
  borderClass: string;
}
```

### EventFeedbackResponse

API response for feedback:

```typescript
interface EventFeedbackResponse {
  id: number;
  event_id: number;
  feedback_type: FeedbackType;
  notes: string | null;
  created_at: string;
}
```

## Related Hooks

Uses React Query (`@tanstack/react-query`) for:

- `useQuery` - Fetching existing feedback
- `useMutation` - Submitting new feedback
- `useQueryClient` - Cache invalidation

## Query Keys

- `['eventFeedback', eventId]` - Existing feedback for event
- `['feedbackStats']` - Aggregate feedback statistics

## Styling

- Dark theme with NVIDIA branding
- Background: `#1A1A1A` with gray-800 border
- Feedback type colors:
  - Accurate: green-400/600
  - False Positive: red-400/600
  - Missed Threat: orange-400/600
  - Severity Wrong: yellow-400/600
- Primary accent: `#76B900` (NVIDIA Green) for submit button

## API Endpoints Used

- `GET /api/events/{event_id}/feedback` - Fetch existing feedback
- `POST /api/events/{event_id}/feedback` - Submit new feedback

## Entry Points

**Start here:** `FeedbackPanel.tsx` - Main feedback component used in EventDetailModal

## Dependencies

- `@tanstack/react-query` - Data fetching and caching
- `clsx` - Conditional class composition
- `lucide-react` - AlertTriangle, Check, CheckCircle2, Loader2, MessageSquare, ThumbsDown, ThumbsUp, X icons
- `../../services/api` - getEventFeedback, submitEventFeedback
