# Events Components

## Purpose

Components for displaying and interacting with security events. Events are aggregated detection results analyzed by Nemotron with risk scoring and reasoning.

## Current Status

**This directory is currently empty** (contains only `.gitkeep`). Components will be implemented in **Phase 5** (Events & Real-time) and **Phase 7** (Pages & Modals).

## Planned Components

### EventCard

Display a single security event with thumbnail, risk badge, timestamp, and detection summary.

**Planned Features:**

- Event thumbnail with detection overlay
- Risk badge (low/medium/high/critical)
- Timestamp and duration
- Detection count and types
- Camera name/location
- Truncated reasoning text with "Show more" link
- Click to open detail modal

### EventDetailModal

Full-screen or large modal showing comprehensive event details.

**Planned Features:**

- Full-size image with bounding boxes
- Complete Nemotron reasoning/explanation
- Risk score breakdown
- All detections with confidence scores
- Event metadata (camera, timestamp, duration)
- Related events (if any)
- Actions (archive, dismiss, mark as false positive)

### EventTimeline

Chronological list or timeline view of security events.

**Planned Features:**

- Scrollable event list
- Date grouping (Today, Yesterday, This Week, etc.)
- Filtering by risk level, camera, object type
- Infinite scroll or pagination
- Real-time updates via WebSocket
- Empty state for no events

### EventFilters

Filter controls for event lists.

**Planned Features:**

- Risk level checkboxes
- Camera selector
- Date range picker
- Object type filters (person, car, package, etc.)
- Search by keywords in reasoning
- Sort options (newest first, highest risk first)

## Data Model

Events are expected to follow this structure (based on backend schema):

```typescript
interface Event {
  id: string;
  camera_id: string;
  camera_name: string;
  timestamp: string; // ISO 8601
  duration_seconds: number;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  risk_score: number; // 0-100
  reasoning: string; // Nemotron explanation
  image_path: string;
  detections: Detection[];
  created_at: string;
}

interface Detection {
  id: string;
  object_type: string;
  confidence: number; // 0-1
  bbox_x: number;
  bbox_y: number;
  bbox_width: number;
  bbox_height: number;
}
```

## Integration Points

Events components will integrate with:

- **Events API** (`/api/v1/events`) - Fetch event list, detail, filtering
- **WebSocket** - Real-time event notifications
- **Detection components** - Reuse `DetectionImage` for thumbnails and overlays
- **Common components** - Reuse `RiskBadge` for risk display
- **Router** - Navigation to event detail pages

## Styling Approach

Will follow app-wide styling patterns:

- **Tailwind CSS** for layout and styling
- **Tremor** for data visualization (if needed)
- Dark theme consistency:
  - Card backgrounds: `#1A1A1A`
  - Borders: `gray-800`
  - NVIDIA green accents: `#76B900`
- Card-based layouts for events
- Modal overlays with backdrop blur
- Responsive grid for event lists

## Test Files

When implemented, test files will be co-located:

- `EventCard.test.tsx`
- `EventDetailModal.test.tsx`
- `EventTimeline.test.tsx`
- `EventFilters.test.tsx`

**Coverage Requirements:**

- Component rendering with various event data
- User interactions (clicks, filters, modal open/close)
- Real-time updates (WebSocket integration)
- Empty states and loading states
- Error handling
- Accessibility (keyboard navigation, screen readers)

## Implementation Priority

Per project phase plan:

1. **Phase 5** - EventCard, EventTimeline basics
2. **Phase 7** - EventDetailModal, EventFilters, full timeline page
