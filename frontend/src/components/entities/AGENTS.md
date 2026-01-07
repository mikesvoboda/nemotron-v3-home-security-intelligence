# Entity Tracking Components Directory

## Purpose

Components for tracking and displaying re-identified entities (persons and vehicles) across multiple cameras. Uses CLIP-based embeddings for cross-camera entity matching with cosine similarity threshold of 0.85.

## Files

| File                        | Purpose                                |
| --------------------------- | -------------------------------------- |
| `EntitiesPage.tsx`          | Main page for listing tracked entities |
| `EntitiesPage.test.tsx`     | Test suite for EntitiesPage            |
| `EntityCard.tsx`            | Card display for individual entity     |
| `EntityCard.test.tsx`       | Test suite for EntityCard              |
| `EntityTimeline.tsx`        | Timeline of entity appearances         |
| `EntityTimeline.test.tsx`   | Test suite for EntityTimeline          |
| `EntityDetailModal.tsx`     | Modal for entity details               |
| `EntityDetailModal.test.tsx`| Test suite for EntityDetailModal       |
| `ReidHistoryPanel.tsx`      | Re-identification history panel        |
| `ReidHistoryPanel.test.tsx` | Test suite for ReidHistoryPanel        |
| `index.ts`                  | Barrel exports                         |

## Architecture

```
EntitiesPage
├── Header (title, description, refresh button)
├── Filter buttons (All | Persons | Vehicles)
├── Stats display (person/vehicle counts)
└── Entity grid
    └── EntityCard (for each entity)
        └── onClick -> EntityDetailModal
            ├── Entity summary info
            └── EntityTimeline
```

## Key Components

### EntitiesPage.tsx

**Purpose:** Main page component for entity tracking and management

**Features:**
- List tracked persons and vehicles
- Filter by entity type (All, Persons, Vehicles)
- Display entity type counts
- Click to view entity details
- Refresh functionality
- Loading, error, and empty states

**State Management:**
```typescript
const [entities, setEntities] = useState<EntitySummary[]>([]);
const [entityTypeFilter, setEntityTypeFilter] = useState<'all' | 'person' | 'vehicle'>('all');
const [selectedEntity, setSelectedEntity] = useState<EntityDetail | null>(null);
const [modalOpen, setModalOpen] = useState(false);
```

### EntityCard.tsx

**Purpose:** Card component displaying entity summary

**Props Interface:**
```typescript
interface EntityCardProps {
  id: string;
  entity_type: 'person' | 'vehicle';
  first_seen: string;
  last_seen: string;
  appearance_count: number;
  cameras_seen: string[];
  thumbnail_url: string | null;
  onClick?: (entityId: string) => void;
  className?: string;
}
```

**Features:**
- Entity type badge with icon (User/Car)
- Thumbnail or placeholder
- Appearance count and camera count
- First/last seen timestamps (relative formatting)
- Keyboard accessible (Enter/Space to activate)
- Hover effects

### EntityTimeline.tsx

**Purpose:** Display chronological timeline of entity appearances

**Props Interface:**
```typescript
interface EntityTimelineProps {
  entity_id: string;
  entity_type: 'person' | 'vehicle';
  appearances: EntityAppearance[];
  className?: string;
}

interface EntityAppearance {
  detection_id: string;
  camera_id: string;
  camera_name: string | null;
  timestamp: string;
  thumbnail_url: string | null;
  similarity_score: number | null;
  attributes: Record<string, unknown>;
}
```

**Features:**
- Chronological appearance list (most recent first)
- Thumbnail for each appearance
- Camera name and timestamp
- Similarity score badge
- Vertical timeline connector lines

### EntityDetailModal.tsx

**Purpose:** Modal dialog showing full entity details with timeline

**Props Interface:**
```typescript
interface EntityDetailModalProps {
  entity: EntityDetail | null;
  isOpen: boolean;
  onClose: () => void;
}
```

**Features:**
- HeadlessUI Dialog component
- Entity summary stats (appearances, cameras, timestamps)
- Camera list badges
- Embedded EntityTimeline
- Animated transitions
- Accessible close buttons

## API Integration

Backend endpoints (see `backend/api/routes/entities.py`):

| Endpoint                    | Method | Purpose                              |
| --------------------------- | ------ | ------------------------------------ |
| `/api/entities`             | GET    | List entities with filtering         |
| `/api/entities/{id}`        | GET    | Get entity with all appearances      |
| `/api/entities/{id}/history`| GET    | Get appearance timeline              |

Frontend API functions (see `frontend/src/services/api.ts`):

```typescript
// Fetch paginated entity list
fetchEntities(params?: EntitiesQueryParams): Promise<EntityListResponse>

// Fetch single entity with appearances
fetchEntity(entityId: string): Promise<EntityDetail>

// Fetch entity appearance history
fetchEntityHistory(entityId: string): Promise<EntityHistoryResponse>
```

**Query Parameters:**
- `entity_type`: 'person' | 'vehicle' - Filter by type
- `camera_id`: string - Filter by camera
- `since`: ISO timestamp - Filter by time
- `limit`: number (1-1000) - Results per page
- `offset`: number - Pagination offset

## Entity Types

- **person** - Tracked person with 768-dim CLIP embedding
- **vehicle** - Tracked vehicle with 768-dim CLIP embedding

Cross-camera matching uses cosine similarity with threshold 0.85.
Embeddings stored in Redis with 24-hour rolling window.

## Styling Conventions

NVIDIA Dark Theme:
- Background: `#1F1F1F`
- Modal background: `#1A1A1A`
- Accent: `#76B900` (NVIDIA green)
- Text: white, gray-300, gray-400, gray-500
- Borders: gray-800

Component-specific:
- Entity type badge: `bg-[#76B900]/20` with green text
- Filter buttons: active = green bg, inactive = gray
- Timeline connector: `border-l-2 border-gray-700`

## Testing

All components have comprehensive test suites:

```bash
# Run all entity component tests
cd frontend && npm test -- --run src/components/entities/

# Run specific component tests
npm test -- --run src/components/entities/EntityCard.test.tsx
npm test -- --run src/components/entities/EntityTimeline.test.tsx
npm test -- --run src/components/entities/EntityDetailModal.test.tsx
npm test -- --run src/components/entities/EntitiesPage.test.tsx
```

**Test Coverage:**
- EntityCard: 37 tests (rendering, interactions, accessibility)
- EntityTimeline: 24 tests (rendering, chronological order, styling)
- EntityDetailModal: 21 tests (modal behavior, content, accessibility)
- EntitiesPage: 17 tests (loading, filtering, API integration)

**Total: 99 tests**

## Dependencies

- `lucide-react` - Icons (Users, User, Car, Camera, Clock, Eye, etc.)
- `@headlessui/react` - Dialog, Transition for modal
- React hooks (useState, useCallback, useEffect)

## Usage Example

```tsx
import { EntitiesPage } from './components/entities';

// In router
<Route path="/entities" element={<EntitiesPage />} />

// Or use individual components
import { EntityCard, EntityDetailModal, EntityTimeline } from './components/entities';
```

## Entry Points

**Start here:** `EntitiesPage.tsx` - Main orchestration component
**Then explore:** `EntityCard.tsx` - Understand entity display pattern
**For modals:** `EntityDetailModal.tsx` - Modal pattern with HeadlessUI
