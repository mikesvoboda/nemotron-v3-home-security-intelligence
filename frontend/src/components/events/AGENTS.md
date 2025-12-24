# Events Components Directory

## Purpose

Contains components for displaying, filtering, and interacting with security events. Includes event cards, timeline views, and detailed event modals with AI-generated summaries and detection visualizations.

## Key Components

### EventCard.tsx

**Purpose:** Compact card displaying a single security event with thumbnail, detections, and AI analysis

**Key Features:**

- Thumbnail with bounding box overlay (if detections have bbox data)
- Camera name, timestamp (relative: "5 mins ago", "2 hours ago")
- Risk badge with score
- AI-generated summary text
- Detection chips showing label + confidence percentage
- Expandable AI reasoning section (collapsible)
- "View Details" button (optional, triggers `onViewDetails` callback)
- Hover effects on card border

**Props:**

- `id: string` - Event ID
- `timestamp: string` - ISO timestamp
- `camera_name: string` - Camera that captured event
- `risk_score: number` - 0-100 risk score
- `risk_label: string` - "Low", "Medium", "High", "Critical"
- `summary: string` - AI-generated event summary
- `reasoning?: string` - AI reasoning (optional, expandable section)
- `thumbnail_url?: string` - Event thumbnail URL
- `detections: Detection[]` - Array of detected objects
- `onViewDetails?: (eventId: string) => void` - Click handler for view button
- `className?: string`

**Detection Interface:**

```typescript
{
  label: string;        // "person", "car", "dog"
  confidence: number;   // 0-1
  bbox?: {              // Optional bounding box
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

### EventTimeline.tsx

**Purpose:** Full-page timeline view with filtering, search, and pagination

**Key Features:**

- Paginated event list with server-side filtering
- Filter panel (collapsible) with:
  - Camera dropdown (all cameras)
  - Risk level dropdown (low/medium/high/critical)
  - Review status dropdown (all/unreviewed/reviewed)
  - Date range filters (start date, end date)
- Client-side search bar (filters summaries)
- Clear all filters button
- Responsive grid: 1 col (mobile) → 2 (lg) → 3 (xl)
- Previous/Next pagination buttons
- Results summary: "Showing 1-20 of 150 events"
- Loading spinner, error states, empty states
- "Active" badge when filters are applied

**Props:**

- `onViewEventDetails?: (eventId: number) => void` - Callback when event card clicked
- `className?: string`

**State Management:**

- `filters: EventsQueryParams` - Current filter state
- `events: Event[]` - Loaded events from API
- `cameras: Camera[]` - Available cameras for dropdown
- `searchQuery: string` - Client-side search text
- `totalCount: number` - Total events matching filters

**API Integration:**

- `fetchEvents(filters)` - Loads paginated events with filters
- `fetchCameras()` - Loads camera list for filter dropdown
- Re-fetches on filter changes (debounced)

### EventDetailModal.tsx

**Purpose:** Full-screen modal displaying complete event details with navigation

**Key Features:**

- Headless UI Dialog with backdrop blur and animations
- Full-size image with bounding box overlay
- Complete event metadata (ID, camera, risk score, status)
- AI summary and reasoning sections
- Detailed detection list with confidence percentages
- "Mark as Reviewed" button (calls `onMarkReviewed` callback)
- Previous/Next navigation buttons (calls `onNavigate` callback)
- Keyboard shortcuts:
  - Escape → Close modal
  - Left/Right arrows → Navigate between events
- Reviewed status indicator (green checkmark or yellow "Pending Review")

**Props:**

- `event: Event | null` - Event to display (null hides modal)
- `isOpen: boolean` - Modal visibility state
- `onClose: () => void` - Close callback
- `onMarkReviewed?: (eventId: string) => void` - Mark reviewed callback
- `onNavigate?: (direction: 'prev' | 'next') => void` - Navigation callback

**Event Interface:**

```typescript
{
  id: string;
  timestamp: string;
  camera_name: string;
  risk_score: number;
  risk_label: string;
  summary: string;
  reasoning?: string;
  image_url?: string;        // Full-size image
  thumbnail_url?: string;    // Fallback if no image_url
  detections: Detection[];
  reviewed?: boolean;
}
```

**Keyboard Navigation:**

- `useEffect` hooks register keyboard listeners
- Escape key closes modal
- Arrow keys navigate when `onNavigate` prop provided

## Important Patterns

### Event Data Flow

```
API → EventTimeline → EventCard → EventDetailModal
                           ↓
                    onViewDetails(eventId)
                           ↓
                    Parent loads full event
                           ↓
                    EventDetailModal displays
```

### Timestamp Formatting

All components use consistent relative time formatting:

- < 1 min: "Just now"
- < 60 min: "X minutes ago"
- < 24 hrs: "X hours ago"
- < 7 days: "X days ago"
- Older: "Jan 15, 2024 3:45 PM"

### Detection Visualization

Components integrate with detection components:

- `DetectionImage` - Wraps image with bounding box overlay
- `BoundingBoxOverlay` - SVG overlay with colored boxes
- Automatic conversion from `Detection[]` to `BoundingBox[]`

### Filter State Management

EventTimeline manages complex filter state:

- Server-side filters: camera_id, risk_level, start_date, end_date, reviewed
- Client-side search: filters summaries locally
- Pagination: limit, offset
- Reset to page 0 when filters change

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
- Border: border-gray-800
- Hover: border-gray-700
- Detection chips: rounded-full, bg-gray-800/60
- Reasoning section: bg-[#76B900]/10 (NVIDIA green tint)

### EventTimeline

- Filter panel: bg-[#1F1F1F], border-gray-800
- Search input: bg-[#1A1A1A], border-gray-700, focus:border-[#76B900]
- Pagination: rounded buttons with hover:bg-[#76B900]/10
- Active filter badge: bg-[#76B900], text-black

### EventDetailModal

- Modal panel: bg-[#1A1A1A], border-gray-800, shadow-2xl
- Max width: 1024px (4xl)
- Max height: calc(100vh - 200px)
- Overflow scroll for long events

## Testing

Comprehensive test coverage:

- `EventCard.test.tsx` - Rendering, expandable reasoning, view button, detection chips
- `EventTimeline.test.tsx` - Filtering, search, pagination, camera dropdown, date ranges
- `EventDetailModal.test.tsx` - Modal lifecycle, keyboard shortcuts, navigation, mark reviewed

## Entry Points

**Start here:** `EventTimeline.tsx` - Understand full page layout, filtering, and pagination
**Then explore:** `EventCard.tsx` - See compact event display and interaction patterns
**Deep dive:** `EventDetailModal.tsx` - Learn modal patterns and keyboard navigation

## Dependencies

- `@headlessui/react` - Dialog, Transition for modal
- `lucide-react` - Icons (Clock, Camera, Eye, ChevronUp/Down, ArrowLeft/Right, CheckCircle2, AlertCircle, X, Filter, Search, Calendar)
- `clsx` - Conditional class composition
- `react` - useState, useEffect, Fragment
- `../../utils/risk` - getRiskLevel, getRiskColor, getRiskLabel
- `../../services/api` - fetchEvents, fetchCameras, Event, Camera types
- `../common/RiskBadge` - Risk level display
- `../detection/DetectionImage` - Image with bounding boxes

## Future Enhancements

- Export events to CSV/JSON
- Bulk actions (mark multiple as reviewed)
- Event tagging system
- Comments/notes on events
- Video playback (if cameras support it)
- Share events via link
- Advanced filtering (object types, confidence ranges)
