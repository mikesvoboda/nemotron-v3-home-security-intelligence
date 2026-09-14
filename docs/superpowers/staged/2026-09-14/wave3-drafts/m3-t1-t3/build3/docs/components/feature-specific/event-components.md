# Event Components

> Components for displaying and interacting with security events.

---

## Overview

Event components display security detections from the AI pipeline. They support timeline views, filtering, event details, and user feedback.

**Location:** `frontend/src/components/events/`

---

## Page Components

### EventTimeline

Main timeline view for browsing security events.

**Location:** `frontend/src/components/events/EventTimeline.tsx`

**Features:**

- Infinite scroll with virtualization
- Time-based grouping
- Filter by camera, risk level, object type
- Date range selection
- Multiple view modes (cards, list, timeline)

**Data Dependencies:**

- `useInfiniteEvents()` - Paginated events
- `useCameras()` - Camera list for filters
- `useEventFilters()` - Filter state management

---

### EventListView

Compact list view of events.

**Location:** `frontend/src/components/events/EventListView.tsx`

**Props:**

| Prop       | Type                   | Default | Description        |
| ---------- | ---------------------- | ------- | ------------------ |
| events     | `Event[]`              | -       | Event list         |
| onSelect   | `(id: string) => void` | -       | Selection handler  |
| selectedId | `string`               | -       | Currently selected |

---

## Card Components

### EventCard

Primary event display card.

**Location:** `frontend/src/components/events/EventCard.tsx`

**Props:**

| Prop        | Type                           | Default | Description          |
| ----------- | ------------------------------ | ------- | -------------------- |
| event       | `Event`                        | -       | Event data           |
| onClick     | `() => void`                   | -       | Click handler        |
| onFeedback  | `(feedback: Feedback) => void` | -       | Feedback handler     |
| showActions | `boolean`                      | `true`  | Show action buttons  |
| compact     | `boolean`                      | `false` | Compact display mode |

**Content:**

- Thumbnail with detection overlay
- Timestamp and camera name
- Risk badge and confidence
- Object type badges
- AI-generated summary (if available)

**Usage:**

```tsx
import { EventCard } from '@/components/events';

<EventCard
  event={event}
  onClick={() => openDetail(event.id)}
  onFeedback={(fb) => submitFeedback(event.id, fb)}
/>;
```

---

### EventClusterCard

Card for grouped/clustered events.

**Location:** `frontend/src/components/events/EventClusterCard.tsx`

**Props:**

| Prop     | Type           | Default | Description    |
| -------- | -------------- | ------- | -------------- |
| cluster  | `EventCluster` | -       | Cluster data   |
| onExpand | `() => void`   | -       | Expand handler |

**Features:**

- Shows count and time range
- Highest risk indicator
- Representative thumbnail
- Expand to see all events

---

### MobileEventCard

Mobile-optimized event card.

**Location:** `frontend/src/components/events/MobileEventCard.tsx`

**Features:**

- Touch-friendly actions
- Swipe to dismiss/acknowledge
- Larger touch targets
- Simplified layout

---

### DeletedEventCard

Placeholder for deleted events.

**Location:** `frontend/src/components/events/DeletedEventCard.tsx`

**Props:**

| Prop      | Type     | Default | Description        |
| --------- | -------- | ------- | ------------------ |
| eventId   | `string` | -       | Deleted event ID   |
| deletedAt | `Date`   | -       | Deletion timestamp |

---

## Detail Components

### EventDetailModal

Full event detail modal.

**Location:** `frontend/src/components/events/EventDetailModal.tsx`

**Props:**

| Prop       | Type                                    | Default | Description      |
| ---------- | --------------------------------------- | ------- | ---------------- |
| event      | `Event`                                 | -       | Event data       |
| isOpen     | `boolean`                               | -       | Modal visibility |
| onClose    | `() => void`                            | -       | Close handler    |
| onNavigate | `(direction: 'prev' \| 'next') => void` | -       | Navigate events  |

**Content:**

- Full-size detection image
- Bounding box overlay
- Detection metadata
- AI enrichment details
- Risk assessment
- Entity tracking info
- Feedback submission
- Related events

---

### EventStatsPanel

Event statistics panel.

**Location:** `frontend/src/components/events/EventStatsPanel.tsx`

**Props:**

| Prop      | Type        | Default | Description            |
| --------- | ----------- | ------- | ---------------------- |
| timeRange | `TimeRange` | -       | Stats time range       |
| cameraId  | `string`    | -       | Optional camera filter |

**Displays:**

- Total events
- Events by risk level
- Events by object type
- Detection accuracy

---

### EventVideoPlayer

Video playback for event clips.

**Location:** `frontend/src/components/events/EventVideoPlayer.tsx`

**Props:**

| Prop        | Type           | Default | Description              |
| ----------- | -------------- | ------- | ------------------------ |
| videoUrl    | `string`       | -       | Video URL                |
| startTime   | `number`       | `0`     | Start position (seconds) |
| annotations | `Annotation[]` | `[]`    | Bounding box annotations |

---

## Enrichment Components

### EnrichmentBadges

Badges showing AI enrichment types.

**Location:** `frontend/src/components/events/EnrichmentBadges.tsx`

**Props:**

| Prop        | Type           | Default | Description     |
| ----------- | -------------- | ------- | --------------- |
| enrichments | `Enrichment[]` | -       | Enrichment data |
| showDetails | `boolean`      | `false` | Expand on hover |

**Badge Types:**

- Nemotron analysis
- Face detection
- License plate
- Clothing description
- Action recognition

---

### EnrichmentPanel

Detailed enrichment display panel.

**Location:** `frontend/src/components/events/EnrichmentPanel.tsx`

**Props:**

| Prop        | Type                     | Default | Description     |
| ----------- | ------------------------ | ------- | --------------- |
| enrichments | `Enrichment[]`           | -       | Enrichment data |
| onExpand    | `(type: string) => void` | -       | Expand handler  |

---

### RiskFlagsPanel

Risk assessment flags display.

**Location:** `frontend/src/components/events/RiskFlagsPanel.tsx`

**Props:**

| Prop      | Type         | Default | Description |
| --------- | ------------ | ------- | ----------- |
| riskFlags | `RiskFlag[]` | -       | Risk flags  |

**Flag Types:**

- Unusual time
- Unrecognized person
- Restricted zone
- Multiple entities
- Extended duration

---

## Entity Components

### EntityThreatCards

Entity threat assessment cards.

**Location:** `frontend/src/components/events/EntityThreatCards.tsx`

**Props:**

| Prop     | Type             | Default | Description        |
| -------- | ---------------- | ------- | ------------------ |
| entities | `EntityThreat[]` | -       | Entity threat data |

---

### EntityTrackingPanel

Entity movement tracking panel.

**Location:** `frontend/src/components/events/EntityTrackingPanel.tsx`

**Props:**

| Prop     | Type     | Default | Description      |
| -------- | -------- | ------- | ---------------- |
| entityId | `string` | -       | Entity ID        |
| eventId  | `string` | -       | Current event ID |

---

### MatchedEntitiesSection

Matched entity display section.

**Location:** `frontend/src/components/events/MatchedEntitiesSection.tsx`

**Props:**

| Prop         | Type                   | Default | Description         |
| ------------ | ---------------------- | ------- | ------------------- |
| matches      | `EntityMatch[]`        | -       | Entity matches      |
| onViewEntity | `(id: string) => void` | -       | View entity handler |

---

### ReidMatchesPanel

Re-identification matches panel.

**Location:** `frontend/src/components/events/ReidMatchesPanel.tsx`

**Props:**

| Prop      | Type          | Default | Description                |
| --------- | ------------- | ------- | -------------------------- |
| matches   | `ReidMatch[]` | -       | Re-ID matches              |
| threshold | `number`      | `0.8`   | Match confidence threshold |

---

## Filter & Navigation Components

### FilterChips

Active filter display chips.

**Location:** `frontend/src/components/events/FilterChips.tsx`

**Props:**

| Prop       | Type                    | Default | Description           |
| ---------- | ----------------------- | ------- | --------------------- |
| filters    | `ActiveFilter[]`        | -       | Active filters        |
| onRemove   | `(key: string) => void` | -       | Remove filter handler |
| onClearAll | `() => void`            | -       | Clear all handler     |

---

### ViewToggle

Toggle between view modes.

**Location:** `frontend/src/components/events/ViewToggle.tsx`

**Props:**

| Prop     | Type                              | Default | Description       |
| -------- | --------------------------------- | ------- | ----------------- |
| value    | `'cards' \| 'list' \| 'timeline'` | -       | Current view mode |
| onChange | `(mode: ViewMode) => void`        | -       | Change handler    |

---

### DateRangePickerModal

Date range selection modal.

**Location:** `frontend/src/components/events/DateRangePickerModal.tsx`

**Props:**

| Prop     | Type                         | Default | Description          |
| -------- | ---------------------------- | ------- | -------------------- |
| isOpen   | `boolean`                    | -       | Modal visibility     |
| onClose  | `() => void`                 | -       | Close handler        |
| value    | `DateRange`                  | -       | Current range        |
| onChange | `(range: DateRange) => void` | -       | Change handler       |
| presets  | `Preset[]`                   | -       | Quick select presets |

---

### TimelineScrubber

Timeline navigation control.

**Location:** `frontend/src/components/events/TimelineScrubber.tsx`

**Props:**

| Prop         | Type                   | Default | Description             |
| ------------ | ---------------------- | ------- | ----------------------- |
| range        | `TimeRange`            | -       | Time range              |
| currentTime  | `Date`                 | -       | Current position        |
| onChange     | `(time: Date) => void` | -       | Position change handler |
| eventMarkers | `Date[]`               | `[]`    | Event timestamps        |

---

### TimeGroupedEvents

Events grouped by time period.

**Location:** `frontend/src/components/events/TimeGroupedEvents.tsx`

**Props:**

| Prop    | Type                        | Default | Description     |
| ------- | --------------------------- | ------- | --------------- |
| events  | `Event[]`                   | -       | Events to group |
| groupBy | `'hour' \| 'day' \| 'week'` | `day`   | Grouping period |

---

## Feedback Components

### DetectionFeedback

Quick feedback buttons for detection accuracy.

**Location:** `frontend/src/components/events/DetectionFeedback.tsx`

**Props:**

| Prop     | Type                               | Default | Description    |
| -------- | ---------------------------------- | ------- | -------------- |
| eventId  | `string`                           | -       | Event ID       |
| onSubmit | `(feedback: FeedbackType) => void` | -       | Submit handler |

**Feedback Types:**

- Correct detection
- Incorrect detection
- False positive
- Missing detection

---

### FeedbackForm

Detailed feedback submission form.

**Location:** `frontend/src/components/events/FeedbackForm.tsx`

**Props:**

| Prop     | Type                                   | Default | Description    |
| -------- | -------------------------------------- | ------- | -------------- |
| eventId  | `string`                               | -       | Event ID       |
| onSubmit | `(feedback: DetailedFeedback) => void` | -       | Submit handler |
| onCancel | `() => void`                           | -       | Cancel handler |

---

## Media Components

### ThumbnailStrip

Horizontal thumbnail strip.

**Location:** `frontend/src/components/events/ThumbnailStrip.tsx`

**Props:**

| Prop          | Type                      | Default | Description       |
| ------------- | ------------------------- | ------- | ----------------- |
| images        | `string[]`                | -       | Image URLs        |
| selectedIndex | `number`                  | `0`     | Selected image    |
| onSelect      | `(index: number) => void` | -       | Selection handler |

---

### ConfidenceIndicators

Detection confidence visual display.

**Location:** `frontend/src/components/events/ConfidenceIndicators.tsx`

**Props:**

| Prop       | Type          | Default | Description            |
| ---------- | ------------- | ------- | ---------------------- |
| detections | `Detection[]` | -       | Detection data         |
| showLabels | `boolean`     | `true`  | Show confidence labels |

---

## Export Components

### ExportPanel

Event export configuration panel.

**Location:** `frontend/src/components/events/ExportPanel.tsx`

**Props:**

| Prop     | Type                             | Default | Description     |
| -------- | -------------------------------- | ------- | --------------- |
| filters  | `EventFilters`                   | -       | Current filters |
| onExport | `(config: ExportConfig) => void` | -       | Export handler  |

---

## Testing

```bash
cd frontend && npm test -- --testPathPattern=events
```

Test coverage includes:

- Card rendering with various event types
- Filter interaction and state
- Modal navigation
- Feedback submission
- Infinite scroll behavior
- Responsive layouts
