# Events Components Directory

## Purpose

Contains components for displaying, filtering, and interacting with security events. Includes event cards, timeline views, detailed event modals with AI-generated summaries, detection visualizations, and thumbnail sequences.

## Key Components

### EventCard.tsx

**Purpose:** Compact card displaying a single security event with thumbnail, detections, and AI analysis

**Key Features:**

- Thumbnail with bounding box overlay (if detections have bbox data)
- Camera name, timestamp (relative: "5 mins ago", "2 hours ago")
- Event duration display (started_at to ended_at)
- Risk badge with score and progress bar
- Object type badges (person, vehicle, animal, etc.)
- AI-generated summary text
- Detection chips showing label + confidence percentage
- Expandable AI reasoning section (collapsible)
- "View Details" button (optional, triggers `onViewDetails` callback)
- Left border color based on risk level
- Hover effects on card border

**Props:**

```typescript
interface EventCardProps {
  id: string;
  timestamp: string;
  camera_name: string;
  risk_score: number;
  risk_label: string;
  summary: string;
  reasoning?: string;
  thumbnail_url?: string;
  detections: Detection[];
  started_at?: string;
  ended_at?: string | null;
  onViewDetails?: (eventId: string) => void;
  className?: string;
}
```

**Detection Interface:**

```typescript
interface Detection {
  label: string; // "person", "car", "dog"
  confidence: number; // 0-1
  bbox?: {
    // Optional bounding box
    x: number;
    y: number;
    width: number;
    height: number;
  };
}
```

**Helper Functions:**

- `formatTimestamp()` - Converts ISO to relative time or absolute format
- `convertToBoundingBoxes()` - Transforms Detection[] to BoundingBox[] for DetectionImage
- `formatConfidence()` - Converts 0-1 to percentage string
- `getBorderColorClass()` - Returns risk-level-based border color class

### EventTimeline.tsx

**Purpose:** Full-page timeline view with filtering, search, bulk actions, and pagination

**Key Features:**

- Paginated event list with server-side filtering
- Filter panel (collapsible) with:
  - Camera dropdown (all cameras)
  - Risk level dropdown (low/medium/high/critical)
  - Review status dropdown (all/unreviewed/reviewed)
  - Object type dropdown (person/vehicle/animal/package/other)
  - Date range filters (start date, end date)
- Client-side search bar (filters summaries)
- Clear all filters button
- Risk summary badges showing counts per level
- Bulk selection and "Mark as Reviewed" action
- Select all / deselect all functionality
- Responsive grid: 1 col (mobile) -> 2 (lg) -> 3 (xl)
- Previous/Next pagination buttons
- Results summary: "Showing 1-20 of 150 events"
- Loading spinner, error states, empty states
- "Active" badge when filters are applied

**Props:**

```typescript
interface EventTimelineProps {
  onViewEventDetails?: (eventId: number) => void;
  className?: string;
}
```

**State Management:**

- `filters: EventsQueryParams` - Current filter state
- `events: Event[]` - Loaded events from API
- `cameras: Camera[]` - Available cameras for dropdown
- `searchQuery: string` - Client-side search text
- `totalCount: number` - Total events matching filters
- `selectedEventIds: Set<number>` - Selected events for bulk actions
- `bulkActionLoading: boolean` - Bulk action in progress

**API Integration:**

- `fetchEvents(filters)` - Loads paginated events with filters
- `fetchCameras()` - Loads camera list for filter dropdown
- `bulkUpdateEvents(ids, updates)` - Bulk mark as reviewed
- Re-fetches on filter changes

### EventDetailModal.tsx

**Purpose:** Full-screen modal displaying complete event details with navigation

**Key Features:**

- Headless UI Dialog with backdrop blur and animations
- Full-size image with bounding box overlay
- Detection sequence thumbnail strip (ThumbnailStrip component)
- Complete event metadata (ID, camera, risk score, duration, status)
- AI summary and reasoning sections
- Detailed detection list with confidence percentages
- User notes section with save functionality
- "Mark as Reviewed" button
- "Flag Event" toggle button
- "Download Media" button
- Previous/Next navigation buttons
- Keyboard shortcuts:
  - Escape -> Close modal
  - Left/Right arrows -> Navigate between events
- Reviewed status indicator (green checkmark or yellow "Pending Review")

**Props:**

```typescript
interface EventDetailModalProps {
  event: Event | null;
  isOpen: boolean;
  onClose: () => void;
  onMarkReviewed?: (eventId: string) => void;
  onNavigate?: (direction: 'prev' | 'next') => void;
  onSaveNotes?: (eventId: string, notes: string) => Promise;
  onFlagEvent?: (eventId: string, flagged: boolean) => Promise;
  onDownloadMedia?: (eventId: string) => Promise;
}
```

**Event Interface:**

```typescript
interface Event {
  id: string;
  timestamp: string;
  camera_name: string;
  risk_score: number;
  risk_label: string;
  summary: string;
  reasoning?: string;
  image_url?: string; // Full-size image
  thumbnail_url?: string; // Fallback if no image_url
  detections: Detection[];
  started_at?: string;
  ended_at?: string | null;
  reviewed?: boolean;
  notes?: string | null;
  flagged?: boolean;
}
```

### ThumbnailStrip.tsx

**Purpose:** Horizontal scrollable strip of detection thumbnails with timestamps

**Key Features:**

- Displays sequence of detection thumbnails from an event
- Shows relative time from first detection (00:00, 00:15, etc.)
- Shows absolute timestamp (HH:MM:SS format)
- Click thumbnail to select/view specific detection
- Loading skeleton state
- Selected thumbnail highlighted with NVIDIA green ring
- Sequence number badges (#1, #2, etc.)
- Object type and confidence display (if available)

**Props:**

```typescript
interface ThumbnailStripProps {
  detections: DetectionThumbnail[];
  selectedDetectionId?: number;
  onThumbnailClick?: (detectionId: number) => void;
  loading?: boolean;
}

interface DetectionThumbnail {
  id: number;
  detected_at: string;
  thumbnail_url: string;
  object_type?: string;
  confidence?: number;
}
```

## Important Patterns

### Event Data Flow

```
API -> EventTimeline -> EventCard -> EventDetailModal
                             |
                    onViewDetails(eventId)
                             |
                    Parent loads full event
                             |
                    EventDetailModal displays
                             |
                    ThumbnailStrip shows detection sequence
```

### Timestamp Formatting

All components use consistent relative time formatting:

- < 1 min: "Just now"
- < 60 min: "X minutes ago"
- < 24 hrs: "X hours ago"
- < 7 days: "X days ago"
- Older: "Jan 15, 2024 3:45 PM"

### Duration Formatting

Uses `formatDuration()` from `../../utils/time`:

- Shows elapsed time between started_at and ended_at
- Handles ongoing events (ended_at is null)

### Detection Visualization

Components integrate with detection components:

- `DetectionImage` - Wraps image with bounding box overlay
- `BoundingBoxOverlay` - SVG overlay with colored boxes
- Automatic conversion from `Detection[]` to `BoundingBox[]`

### Filter State Management

EventTimeline manages complex filter state:

- Server-side filters: camera_id, risk_level, start_date, end_date, reviewed, object_type
- Client-side search: filters summaries locally
- Pagination: limit, offset
- Reset to page 0 when filters change

### Bulk Actions

EventTimeline supports bulk operations:

- Checkbox selection per event card
- "Select All" toggle for current page
- "Mark as Reviewed" bulk action
- Shows loading state during bulk updates

### Modal Animations

EventDetailModal uses Headless UI Transition:

- Fade in/out backdrop (300ms ease-out)
- Scale + fade modal panel (300ms ease-out)
- Smooth enter/leave animations

### Responsive Grid

EventTimeline uses responsive breakpoints:

- Mobile: 1 column (full width cards)
- Tablet (lg): 2 columns
- Desktop (xl): 3 columns

## Styling Conventions

### EventCard

- Card background: bg-[#1F1F1F]
- Border: border-gray-800 with risk-colored left border
- Left border colors: border-l-risk-low/medium/high, border-l-red-500 (critical)
- Hover: border-gray-700
- Detection chips: rounded-full, bg-gray-800/60
- Reasoning section: bg-[#76B900]/10 (NVIDIA green tint)
- Risk progress bar with dynamic color

### EventTimeline

- Filter panel: bg-[#1F1F1F], border-gray-800
- Search input: bg-[#1A1A1A], border-gray-700, focus:border-[#76B900]
- Pagination: rounded buttons with hover:bg-[#76B900]/10
- Active filter badge: bg-[#76B900], text-black
- Selection checkbox: bg-[#1A1A1A]/90 backdrop-blur

### EventDetailModal

- Modal panel: bg-[#1A1A1A], border-gray-800, shadow-2xl
- Max width: 1024px (4xl)
- Max height: calc(100vh - 200px)
- Overflow scroll for long events
- Notes textarea: bg-black/30, focus:border-[#76B900]
- Footer: bg-black/20

### ThumbnailStrip

- Container: bg-black/20, border-gray-800
- Thumbnail: border-gray-700, hover/selected: border-[#76B900]
- Selected: bg-[#76B900]/20, ring-2 ring-[#76B900]
- Sequence badge: bg-black/75, text-white

## Testing

Comprehensive test coverage:

- `EventCard.test.tsx` - Rendering, expandable reasoning, view button, detection chips, duration display
- `EventTimeline.test.tsx` - Filtering, search, pagination, camera dropdown, date ranges, bulk actions
- `EventDetailModal.test.tsx` - Modal lifecycle, keyboard shortcuts, navigation, mark reviewed, notes, flags
- `ThumbnailStrip.test.tsx` - Thumbnail rendering, selection, click handlers, loading state

## Entry Points

**Start here:** `EventTimeline.tsx` - Understand full page layout, filtering, and pagination
**Then explore:** `EventCard.tsx` - See compact event display and interaction patterns
**Deep dive:** `EventDetailModal.tsx` - Learn modal patterns and keyboard navigation
**Finally:** `ThumbnailStrip.tsx` - Understand detection sequence visualization

## Dependencies

- `@headlessui/react` - Dialog, Transition for modal
- `lucide-react` - Icons (Clock, Timer, Eye, ChevronUp/Down, ArrowLeft/Right, CheckCircle2, CheckSquare, Square, AlertCircle, X, Filter, Search, Calendar, Save, Flag, Download)
- `clsx` - Conditional class composition
- `react` - useState, useEffect, Fragment
- `../../utils/risk` - getRiskLevel, getRiskColor, getRiskLabel
- `../../utils/time` - formatDuration
- `../../services/api` - fetchEvents, fetchCameras, fetchEventDetections, getDetectionImageUrl, bulkUpdateEvents, Event, Camera types
- `../common/RiskBadge` - Risk level display
- `../common/ObjectTypeBadge` - Object type display
- `../detection/DetectionImage` - Image with bounding boxes

### ExportPanel.tsx

**Purpose:** Comprehensive UI for exporting events data with filters and format selection

**Key Features:**

- Export format selection (CSV supported, JSON coming soon)
- Filter options matching EventTimeline:
  - Camera dropdown
  - Risk level dropdown (low/medium/high/critical)
  - Date range filters (start date, end date)
  - Review status filter (all/unreviewed/reviewed)
- Export preview showing estimated record count
- Clear all filters button
- Collapsible panel option
- Progress indicator during export
- Success/error feedback with auto-dismissing messages
- Disabled state when no events to export

**Props:**

```typescript
interface ExportPanelProps {
  /** Pre-populate filters from EventTimeline */
  initialFilters?: ExportQueryParams;
  /** Callback when export starts (for external UI state management) */
  onExportStart?: () => void;
  /** Callback when export completes or fails */
  onExportComplete?: (success: boolean, message?: string) => void;
  /** Whether the panel is collapsible */
  collapsible?: boolean;
  /** Whether the panel starts collapsed */
  defaultCollapsed?: boolean;
  /** Additional CSS classes */
  className?: string;
}

type ExportFormat = 'csv' | 'json';
```

**API Integration:**

- `fetchCameras()` - Loads camera list for filter dropdown
- `fetchEventStats(filters)` - Gets estimated count for preview
- `exportEventsCSV(filters)` - Triggers CSV download

## Future Enhancements

- Event tagging system
- Comments/notes on events (partially implemented)
- Video playback (if cameras support it)
- Share events via link
- Advanced filtering (confidence ranges)
- Keyboard shortcuts for bulk actions
- Infinite scroll alternative to pagination
- JSON export format
