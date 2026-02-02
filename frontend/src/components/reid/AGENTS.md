# Re-ID Dashboard Components Directory

## Purpose

Components for visualizing cross-camera entity re-identification matches. Displays entity movements through property, camera journey timelines, similarity scores, and household member links.

## Files

| File                      | Purpose                                      |
| ------------------------- | -------------------------------------------- |
| `ReIDDashboard.tsx`       | Main dashboard for cross-camera matching     |
| `ReIDDashboard.test.tsx`  | Test suite for ReIDDashboard                 |
| `index.ts`                | Barrel exports                               |

## Architecture

```
ReIDDashboard
├── Header (title, description, refresh button)
├── Filters (All | Persons | Vehicles, Minimum cameras)
├── Stats summary (cross-camera counts)
├── Entity list (ReIDEntityCard grid)
│   └── ReIDEntityCard
│       ├── Entity thumbnail/icon
│       ├── Household member link badge
│       ├── Camera journey badges (Front Door -> Back Yard -> ...)
│       └── Stats (cameras, appearances, last seen)
└── Detail panel (ReIDDetailPanel)
    ├── Entity summary stats
    ├── CameraJourneyDiagram (visual path)
    ├── CameraJourneyTimeline (chronological appearances)
    └── Similarity scores
```

## Key Components

### ReIDDashboard.tsx

**Purpose:** Main page component for Re-ID cross-camera matching visualization

**Features:**
- Filter entities by type (person/vehicle)
- Filter by minimum cameras seen (2+, 3+, 4+, 5+)
- Display entities with cross-camera appearances
- Click to view detailed entity journey
- Household member linking
- Auto-refresh every 60 seconds

**State Management:**
```typescript
const [entityTypeFilter, setEntityTypeFilter] = useState<EntityTypeFilter>('all');
const [minCamerasFilter, setMinCamerasFilter] = useState<MinCamerasFilter>(2);
const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
```

### ReIDEntityCard

**Purpose:** Card component showing entity's cross-camera journey

**Features:**
- Entity thumbnail with type badge
- Household member link badge (if matched)
- Camera journey visualization with arrows
- Appearance count and last seen time
- Keyboard accessible

### CameraJourneyTimeline

**Purpose:** Chronological timeline of entity appearances

**Features:**
- Sorted appearances (oldest to newest)
- Time differences between stops
- Similarity scores for each detection
- Thumbnails for each appearance

### CameraJourneyDiagram

**Purpose:** Visual representation of entity path through property

**Features:**
- Numbered camera stops
- Directional arrows showing flow
- Total journey duration

### ReIDDetailPanel

**Purpose:** Detailed view of selected entity

**Features:**
- Entity summary with stats
- Link to household page (if matched)
- Journey diagram and timeline
- Appearance thumbnails with similarity scores

## API Integration

Backend endpoints used:

| Endpoint                       | Method | Purpose                              |
| ------------------------------ | ------ | ------------------------------------ |
| `/api/entities`                | GET    | List entities with filtering         |
| `/api/entities/{id}`           | GET    | Get entity with appearances          |
| `/api/reid/similar/{id}`       | GET    | Find similar entities for detection  |

Frontend API functions:

```typescript
// Fetch paginated entity list (via hooks)
useEntitiesInfiniteQuery(filters)

// Fetch single entity with appearances
useEntityDetailQuery(entityId)

// Find similar entities by detection
fetchReidSimilar(detectionId, params)
```

## Data Flow

1. Entities loaded via `useEntitiesInfiniteQuery`
2. Filtered by minimum cameras seen (client-side)
3. Sorted by camera count (most first), then last seen
4. Selected entity triggers `useEntityDetailQuery`
5. Detail panel displays journey and similarity data

## Styling Conventions

NVIDIA Dark Theme:
- Background: `#1F1F1F`
- Accent: `#76B900` (NVIDIA green)
- Text: white, gray-300, gray-400, gray-500
- Borders: gray-800

Component-specific:
- Entity card: `border-gray-800` -> `border-[#76B900]` on select
- Journey badges: `bg-gray-800 text-gray-300`
- Journey arrows: `text-gray-600`
- Similarity scores: `bg-[#76B900]/20 text-[#76B900]`
- Household link: `text-blue-400`

## Testing

Run tests:

```bash
cd frontend && npm test -- --run src/components/reid/
```

**Test Coverage:**
- Rendering states (loading, error, empty, data)
- Entity filtering by type
- Minimum cameras filter
- Entity selection and detail panel
- Camera journey timeline
- Household member linking
- Keyboard accessibility

## Dependencies

- `lucide-react` - Icons
- `react-router-dom` - Link for household navigation
- React hooks (useState, useCallback, useMemo)
- Custom hooks: `useEntitiesInfiniteQuery`, `useEntityDetailQuery`, `useCamerasQuery`

## Usage Example

```tsx
import { ReIDDashboard } from './components/reid';

// In router
<Route path="/reid" element={<ReIDDashboard />} />
```

## Entry Points

**Start here:** `ReIDDashboard.tsx` - Main orchestration component
