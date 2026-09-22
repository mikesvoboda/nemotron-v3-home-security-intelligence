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

**Props:**

| Prop               | Type                        | Default | Description             |
| ------------------ | --------------------------- | ------- | ----------------------- |
| onViewEventDetails | `(eventId: number) => void` | -       | Open event detail modal |
| className          | `string`                    | -       | Additional CSS classes  |

**Features:**

- Infinite scroll (with virtualization)
- Time-based grouping
- Filters (camera, risk level, object type); initial camera / `risk_level` / event selection are read from URL search params
- Date range selection
- View modes: grid, list, grouped (`ViewMode` from `ViewToggle.tsx`); view mode, clustering, and grouping are persisted in localStorage

**Data Dependencies:**

- `useEventsInfiniteQuery` / `useEventsQuery` - Paginated events
- `useTimelineData` - Timeline grouping and buckets
- `useEventStream` - Live events over WebSocket
- `useEventStats` - Aggregate statistics
- `useInfiniteScroll` - Scroll sentinel wiring
- `useSnoozeEvent` - Snooze action (NEM-3592/NEM-3640)
- `usePaginationState`, `useSearchParams` - Page and filter state

---

### EventListView

Compact list view of events with bulk selection.

**Location:** `frontend/src/components/events/EventListView.tsx`

**Props:**

| Prop              | Type                                         | Default | Description                  |
| ----------------- | -------------------------------------------- | ------- | ---------------------------- |
| events            | `EventListItem[]`                            | -       | Event list                   |
| selectedIds       | `Set<number>`                                | -       | Currently selected event IDs |
| onToggleSelection | `(eventId: number) => void`                  | -       | Toggle one row's selection   |
| onToggleSelectAll | `() => void`                                 | -       | Toggle all rows              |
| onEventClick      | `(eventId: number) => void`                  | -       | Row click handler            |
| onMarkReviewed    | `(eventId: number) => void`                  | -       | Mark-reviewed action         |
| onSnooze          | `(eventId: number, seconds: number) => void` | -       | Snooze action (NEM-3592)     |
| sortField         | `SortField`                                  | -       | Current sort field           |
| sortDirection     | `SortDirection`                              | -       | Current sort direction       |
| onSort            | `(field: SortField) => void`                 | -       | Column-header sort handler   |
| className         | `string`                                     | -       | Additional CSS classes       |

---

## Card Components

### EventCard

Primary event display card. Event fields are passed as individual props (not a single `event` object).

**Location:** `frontend/src/components/events/EventCard.tsx`

**Props (core):**

| Prop               | Type                                         | Default | Description                        |
| ------------------ | -------------------------------------------- | ------- | ---------------------------------- |
| id                 | `string`                                     | -       | Event ID                           |
| timestamp          | `string`                                     | -       | Event timestamp                    |
| camera_name        | `string`                                     | -       | Camera name                        |
| risk_score         | `number`                                     | -       | Risk score (0-100)                 |
| risk_label         | `string`                                     | -       | Risk label                         |
| summary            | `string`                                     | -       | AI-generated summary               |
| detections         | `Detection[]`                                | -       | Detections for this event          |
| reasoning          | `string`                                     | -       | LLM reasoning text                 |
| thumbnail_url      | `string`                                     | -       | Thumbnail URL                      |
| started_at         | `string`                                     | -       | Event start                        |
| ended_at           | `string \| null`                             | -       | Event end                          |
| onViewDetails      | `(eventId: string) => void`                  | -       | Open details handler               |
| onClick            | `(eventId: string) => void`                  | -       | Card click handler                 |
| onSnooze           | `(eventId: string, seconds: number) => void` | -       | Snooze handler                     |
| snooze_until       | `string \| null`                             | -       | Snooze expiry (NEM-3640)           |
| onGenerateClip     | `(eventId: string) => void`                  | -       | Generate clip handler (NEM-3870)   |
| onDownloadClip     | `(eventId: string) => void`                  | -       | Download clip (NEM-3870)           |
| isGeneratingClip   | `boolean`                                    | -       | Clip generation in progress        |
| clipUrl            | `string \| null`                             | -       | Generated clip URL                 |
| approachVector     | `ApproachVectorData \| null`                 | -       | Zone approach vector (NEM-5024)    |
| threats            | `ThreatData[] \| null`                       | -       | Threat detections (NEM-5025)       |
| hasCheckboxOverlay | `boolean`                                    | -       | Header margin for checkbox overlay |
| className          | `string`                                     | -       | Additional CSS classes             |

**Content:**

- Thumbnail (when `thumbnail_url` provided)
- Timestamp and camera name
- Risk score/label badge
- Collapsible detections list (`CollapsibleDetections`, capped by `maxVisible`)
- AI-generated summary
- Snooze indicator and clip actions when provided

**Usage:**

```tsx
import { EventCard } from '@/components/events';

<EventCard
  id={event.id}
  timestamp={event.timestamp}
  camera_name={event.camera_name}
  risk_score={event.risk_score}
  risk_label={event.risk_label}
  summary={event.summary}
  detections={event.detections}
  onViewDetails={(id) => openDetail(id)}
/>;
```

---

### EventClusterCard

Card for grouped/clustered events.

**Location:** `frontend/src/components/events/EventClusterCard.tsx`

**Props:**

| Prop               | Type                           | Default | Description                         |
| ------------------ | ------------------------------ | ------- | ----------------------------------- |
| cluster            | `EventCluster`                 | -       | Cluster data                        |
| onEventClick       | `(eventId: number) => void`    | -       | Individual event click handler      |
| onBulkMarkReviewed | `(eventIds: number[]) => void` | -       | Bulk mark-as-reviewed handler       |
| bulkActionLoading  | `boolean`                      | -       | Bulk action in progress             |
| hasCheckboxOverlay | `boolean`                      | -       | Adjust padding for checkbox overlay |
| className          | `string`                       | -       | Additional CSS classes              |

**Features:**

- Click through to individual events
- Bulk mark-reviewed across the cluster with loading state

---

### MobileEventCard

Mobile-optimized event card. Takes the same flat event fields as `EventCard`, plus swipe handlers.

**Location:** `frontend/src/components/events/MobileEventCard.tsx`

**Props (mobile-specific):**

| Prop         | Type                        | Default | Description            |
| ------------ | --------------------------- | ------- | ---------------------- |
| onSwipeLeft  | `(eventId: string) => void` | -       | Swipe-left action      |
| onSwipeRight | `(eventId: string) => void` | -       | Swipe-right action     |
| onClick      | `(eventId: string) => void` | -       | Card tap handler       |
| actions      | `MobileEventCardAction[]`   | -       | Quick-action buttons   |
| className    | `string`                    | -       | Additional CSS classes |

(Core event props — `id`, `timestamp`, `camera_name`, `risk_score`, `risk_label`, `summary`, `detections`, `thumbnail_url`, `started_at`, `ended_at` — are required the same way as on `EventCard`.)

---

### DeletedEventCard

Placeholder for deleted events, with restore/permanent-delete actions.

**Location:** `frontend/src/components/events/DeletedEventCard.tsx`

**Props:**

| Prop              | Type                                           | Default | Description              |
| ----------------- | ---------------------------------------------- | ------- | ------------------------ |
| event             | `DeletedEvent`                                 | -       | The deleted event data   |
| onRestore         | `(eventId: number) => void`                    | -       | Restore handler          |
| onPermanentDelete | `(eventId: number) => void`                    | -       | Permanent delete handler |
| isRestoring       | `boolean`                                      | -       | Restore in progress      |
| isDeleting        | `boolean`                                      | -       | Delete in progress       |
| isSelected        | `boolean`                                      | -       | Bulk-selection state     |
| onSelectionChange | `(eventId: number, selected: boolean) => void` | -       | Selection change handler |
| showSelection     | `boolean`                                      | -       | Show selection checkbox  |
| className         | `string`                                       | -       | Additional CSS classes   |

---

## Detail Components

### EventDetailModal

Full event detail modal.

**Location:** `frontend/src/components/events/EventDetailModal.tsx`

**Props:**

| Prop            | Type                                                   | Default | Description             |
| --------------- | ------------------------------------------------------ | ------- | ----------------------- |
| event           | `Event \| null`                                        | -       | Event data              |
| isOpen          | `boolean`                                              | -       | Modal visibility        |
| onClose         | `() => void`                                           | -       | Close handler           |
| onMarkReviewed  | `(eventId: string) => void`                            | -       | Mark reviewed           |
| onNavigate      | `(direction: 'prev' \| 'next') => void`                | -       | Navigate events         |
| onSaveNotes     | `(eventId: string, notes: string) => Promise<void>`    | -       | Save notes handler      |
| onFlagEvent     | `(eventId: string, flagged: boolean) => Promise<void>` | -       | Flag/unflag event       |
| onDownloadMedia | `(eventId: string) => Promise<void>`                   | -       | Download media          |
| onSnooze        | `(eventId: string, seconds: number) => void`           | -       | Snooze event (NEM-3640) |
| onUnsnooze      | `(eventId: string) => void`                            | -       | Clear snooze (NEM-3640) |

**Content:**

- Full-size detection image with threat bounding boxes (`ThreatBoundingBox`)
- AI enrichment (`EnrichmentPanel` / `EnrichmentBadges`)
- Risk factors breakdown (`RiskFactorsBreakdown`, `RiskFactorsList`) and LLM reasoning explorer
- Entity tracking (`EntityTrackingPanel`), matched entities (`MatchedEntitiesSection`), Re-ID matches (`ReidMatchesPanel`)
- Notes, flagging, media download, and snooze controls

---

### EventStatsPanel

Event statistics panel.

**Location:** `frontend/src/components/events/EventStatsPanel.tsx`

**Props:**

| Prop      | Type                 | Default | Description              |
| --------- | -------------------- | ------- | ------------------------ |
| stats     | `EventStatsResponse` | -       | Stats data from the API  |
| isLoading | `boolean`            | -       | Loading state (required) |
| className | `string`             | -       | Additional CSS classes   |

**Displays (server-side stats, not local calculations):**

- Total events
- Events by risk level (critical / high / medium / low)
- Mini risk distribution chart (`RiskDistributionMini`)

---

### EventVideoPlayer

Video playback for an event's clip; the player fetches the clip itself from the event ID.

**Location:** `frontend/src/components/events/EventVideoPlayer.tsx`

**Props:**

| Prop      | Type     | Default | Description            |
| --------- | -------- | ------- | ---------------------- |
| eventId   | `number` | -       | Event ID to play clip  |
| className | `string` | -       | Additional CSS classes |

---

## Enrichment Components

### EnrichmentBadges

Compact badges showing what AI enrichment data is available for an event (face count, license plate read).

**Location:** `frontend/src/components/events/EnrichmentBadges.tsx`

**Props:**

| Prop                | Type                        | Default | Description                                   |
| ------------------- | --------------------------- | ------- | --------------------------------------------- |
| enrichmentSummary   | `EnrichmentSummary \| null` | -       | Summary data for badge display                |
| enrichmentData      | `EnrichmentData \| null`    | -       | Full enrichment data (alternative to summary) |
| isEnrichmentPending | `boolean`                   | -       | Enrichment still processing                   |
| onExpandEnrichment  | `() => void`                | -       | Badge click opens the full `EnrichmentPanel`  |
| className           | `string`                    | -       | Additional CSS classes                        |

---

### EnrichmentPanel

Detailed enrichment display panel.

**Location:** `frontend/src/components/events/EnrichmentPanel.tsx`

**Props:**

| Prop            | Type                     | Default | Description            |
| --------------- | ------------------------ | ------- | ---------------------- |
| enrichment_data | `EnrichmentData \| null` | -       | Enrichment data        |
| className       | `string`                 | -       | Additional CSS classes |

---

### RiskFlagsPanel

Risk assessment flags, sorted by severity (critical, then alert, then warning). Each flag renders its formatted `type` as the title with the `description` below.

**Location:** `frontend/src/components/events/RiskFlagsPanel.tsx`

**Props:**

| Prop      | Type                              | Default | Description            |
| --------- | --------------------------------- | ------- | ---------------------- |
| flags     | `RiskFlag[] \| null \| undefined` | -       | Risk flags             |
| className | `string`                          | -       | Additional CSS classes |

`RiskFlag` (`frontend/src/types/risk-analysis.ts`): `{ type: string; description: string; severity: FlagSeverity }`.

---

## Entity Components

### EntityThreatCards

Entity cards from risk analysis.

**Location:** `frontend/src/components/events/EntityThreatCards.tsx`

**Props:**

| Prop      | Type                                | Default | Description            |
| --------- | ----------------------------------- | ------- | ---------------------- |
| entities  | `RiskEntity[] \| null \| undefined` | -       | Entities from analysis |
| className | `string`                            | -       | Additional CSS classes |

---

### EntityTrackingPanel

Entity movement tracking timeline across cameras.

**Location:** `frontend/src/components/events/EntityTrackingPanel.tsx`

**Props:**

| Prop             | Type     | Default | Description                            |
| ---------------- | -------- | ------- | -------------------------------------- |
| entityId         | `string` | -       | Entity ID to show tracking history for |
| currentCameraId  | `string` | -       | Camera highlighted in the timeline     |
| currentTimestamp | `string` | -       | Reference timestamp                    |
| className        | `string` | -       | Optional CSS class name                |

---

### MatchedEntitiesSection

Known-entity matches for an event; fetches its own match data from the event ID.

**Location:** `frontend/src/components/events/MatchedEntitiesSection.tsx`

**Props:**

| Prop          | Type                         | Default | Description                             |
| ------------- | ---------------------------- | ------- | --------------------------------------- |
| eventId       | `number`                     | -       | Event ID to fetch matches for           |
| onEntityClick | `(entityId: string) => void` | -       | Opens `EntityDetailModal` for an entity |

---

### ReidMatchesPanel

Re-identification matches for a detection; fetches matches itself.

**Location:** `frontend/src/components/events/ReidMatchesPanel.tsx`

**Props:**

| Prop         | Type                               | Default | Description                      |
| ------------ | ---------------------------------- | ------- | -------------------------------- |
| detectionId  | `number`                           | -       | Detection ID to find matches for |
| entityType   | `'person' \| 'vehicle'`            | -       | Entity type to search            |
| onMatchClick | `(match: EntityMatchItem) => void` | -       | Navigate to entity detail        |
| className    | `string`                           | -       | Optional CSS class name          |

---

## Filter & Navigation Components

### FilterChips

Active filter chips with risk-level counts; chips act as toggles.

**Location:** `frontend/src/components/events/FilterChips.tsx`

**Props:**

| Prop           | Type                                                          | Default | Description                |
| -------------- | ------------------------------------------------------------- | ------- | -------------------------- |
| filters        | `EventFilters`                                                | -       | Current filter state       |
| riskCounts     | `Record<RiskLevel, number>`                                   | -       | Counts shown on risk chips |
| onFilterChange | `(key: keyof EventFilters, value: string \| boolean) => void` | -       | Filter change handler      |
| onClearFilters | `() => void`                                                  | -       | Clear all handler          |
| className      | `string`                                                      | -       | Additional CSS classes     |

---

### ViewToggle

Toggle between view modes.

**Location:** `frontend/src/components/events/ViewToggle.tsx`

**Props:**

| Prop       | Type                             | Default | Description                        |
| ---------- | -------------------------------- | ------- | ---------------------------------- |
| viewMode   | `ViewMode` (`grid/list/grouped`) | -       | Current view mode                  |
| onChange   | `(mode: ViewMode) => void`       | -       | Change handler                     |
| persistKey | `string`                         | -       | localStorage key to persist choice |
| className  | `string`                         | -       | Optional CSS class                 |

---

### DateRangePickerModal

Date range selection modal. Dates are `YYYY-MM-DD` strings.

**Location:** `frontend/src/components/events/DateRangePickerModal.tsx`

**Props:**

| Prop             | Type                                           | Default | Description           |
| ---------------- | ---------------------------------------------- | ------- | --------------------- |
| isOpen           | `boolean`                                      | -       | Modal visibility      |
| onClose          | `() => void`                                   | -       | Close handler         |
| initialStartDate | `string`                                       | -       | Initial start date    |
| initialEndDate   | `string`                                       | -       | Initial end date      |
| onApply          | `(startDate: string, endDate: string) => void` | -       | Applied-range handler |

---

### TimelineScrubber

Timeline navigation control over bucketed event data.

**Location:** `frontend/src/components/events/TimelineScrubber.tsx`

**Props:**

| Prop                | Type                                           | Default | Description                            |
| ------------------- | ---------------------------------------------- | ------- | -------------------------------------- |
| buckets             | `TimelineBucket[]`                             | -       | Bucketed event data to display         |
| onTimeRangeChange   | `(range: TimeRange) => void`                   | -       | Selected time-range handler            |
| zoomLevel           | `ZoomLevel`                                    | -       | Current zoom level                     |
| onZoomChange        | `(level: ZoomLevel) => void`                   | -       | Zoom change handler                    |
| currentRange        | `TimeRange`                                    | -       | Viewport range to highlight            |
| isLoading           | `boolean`                                      | -       | Loading state                          |
| onCustomRangeSelect | `(startDate: string, endDate: string) => void` | -       | Custom date range selection (NEM-3585) |
| isCustomRangeActive | `boolean`                                      | -       | Custom range active (NEM-3585)         |
| onReset             | `() => void`                                   | -       | Reset/clear custom range (NEM-3585)    |
| initialStartDate    | `string`                                       | -       | Date-picker initial start (YYYY-MM-DD) |
| initialEndDate      | `string`                                       | -       | Date-picker initial end (YYYY-MM-DD)   |
| className           | `string`                                       | -       | Additional CSS classes                 |

---

### TimeGroupedEvents

Events grouped by time period, with selection support.

**Location:** `frontend/src/components/events/TimeGroupedEvents.tsx`

**Props:**

| Prop               | Type                        | Default | Description                      |
| ------------------ | --------------------------- | ------- | -------------------------------- |
| events             | `Event[]`                   | -       | Events to group                  |
| cameraNameMap      | `Map<string, string>`       | -       | Camera ID to display-name lookup |
| selectedEventIds   | `Set<number>`               | -       | Selected event IDs               |
| onToggleSelection  | `(eventId: number) => void` | -       | Selection toggle handler         |
| onEventClick       | `(eventId: number) => void` | -       | Event click handler              |
| onViewEventDetails | `(eventId: number) => void` | -       | Open-details handler             |
| isLoading          | `boolean`                   | -       | Loading state                    |
| className          | `string`                    | -       | Additional CSS classes           |

---

## Feedback Components

### DetectionFeedback

Quick feedback buttons for detection accuracy.

**Location:** `frontend/src/components/events/DetectionFeedback.tsx`

**Props:**

| Prop             | Type                                        | Default | Description                   |
| ---------------- | ------------------------------------------- | ------- | ----------------------------- |
| detectionId      | `string`                                    | -       | Detection ID                  |
| eventId          | `string`                                    | -       | Parent event ID               |
| onFeedbackSubmit | `(feedback: DetectionFeedbackData) => void` | -       | Submit handler                |
| disabled         | `boolean`                                   | -       | Disable interactions          |
| initialFeedback  | `InitialFeedback`                           | -       | Previously submitted feedback |
| compact          | `boolean`                                   | -       | Smaller buttons               |
| className        | `string`                                    | -       | Additional CSS classes        |

**Feedback Types** (`DetectionFeedbackType`): `'correct' | 'incorrect' | 'unsure'` (an `incorrect` submission collects a reason).

---

### FeedbackForm

Detailed feedback submission form.

**Location:** `frontend/src/components/events/FeedbackForm.tsx`

**Props:**

| Prop            | Type                                                 | Default | Description                      |
| --------------- | ---------------------------------------------------- | ------- | -------------------------------- |
| eventId         | `number`                                             | -       | Event ID the feedback is for     |
| feedbackType    | `FeedbackType`                                       | -       | Type of feedback being submitted |
| currentSeverity | `number`                                             | -       | Current risk score (0-100)       |
| onSubmit        | `(notes: string, expectedSeverity?: number) => void` | -       | Submit handler                   |
| onCancel        | `() => void`                                         | -       | Cancel handler                   |
| isSubmitting    | `boolean`                                            | -       | Submitting state                 |

---

## Media Components

### ThumbnailStrip

Horizontal detection thumbnail strip with progressive "Show more".

**Location:** `frontend/src/components/events/ThumbnailStrip.tsx`

**Props:**

| Prop                   | Type                            | Default | Description                                 |
| ---------------------- | ------------------------------- | ------- | ------------------------------------------- |
| detections             | `DetectionThumbnail[]`          | -       | Thumbnail data                              |
| selectedDetectionId    | `number`                        | -       | Currently selected detection                |
| onThumbnailClick       | `(detectionId: number) => void` | -       | Click handler                               |
| onThumbnailDoubleClick | `(detectionId: number) => void` | -       | Double-click (lightbox) handler             |
| loading                | `boolean`                       | -       | Loading state                               |
| initialDisplayCount    | `number`                        | `20`    | Thumbnails shown before "Show more"         |
| loadMoreCount          | `number`                        | `20`    | Additional thumbnails per "Show more" click |

---

### ConfidenceIndicators

Detection confidence visual display.

**Location:** `frontend/src/components/events/ConfidenceIndicators.tsx`

**Props:**

| Prop              | Type                                     | Default | Description                           |
| ----------------- | ---------------------------------------- | ------- | ------------------------------------- |
| confidenceFactors | `ConfidenceFactors \| null \| undefined` | -       | Confidence factors from risk analysis |
| mode              | `'inline' \| 'detailed'`                 | -       | `inline` compact, `detailed` full     |
| className         | `string`                                 | -       | Additional CSS classes                |

---

## Export Components

### ExportPanel

Event export configuration panel; runs the export itself and reports progress via callbacks.

**Location:** `frontend/src/components/events/ExportPanel.tsx`

**Props:**

| Prop             | Type                                           | Default | Description                                |
| ---------------- | ---------------------------------------------- | ------- | ------------------------------------------ |
| initialFilters   | `ExportQueryParams`                            | -       | Pre-populated filters from `EventTimeline` |
| onExportStart    | `() => void`                                   | -       | Export started (external UI state)         |
| onExportComplete | `(success: boolean, message?: string) => void` | -       | Export finished or failed                  |
| collapsible      | `boolean`                                      | -       | Panel can collapse                         |
| defaultCollapsed | `boolean`                                      | -       | Panel starts collapsed                     |
| className        | `string`                                       | -       | Additional CSS classes                     |

---

## Testing

```bash
cd frontend && npm test -- src/components/events
```

Test coverage includes:

- Card rendering with various event types
- Filter interaction and state
- Modal navigation
- Feedback submission
- Infinite scroll behavior
- Responsive layouts
