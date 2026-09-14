# Face Recognition Components

Face recognition and person re-identification UI components for the home security monitoring dashboard.

## Purpose

This directory contains React components for managing known persons, viewing face detection events, and tracking person appearances across cameras. The face recognition system uses AI-powered face detection and embedding matching to identify household members and detect unknown persons.

## Key Files

| File | Purpose |
|------|---------|
| `index.ts` | Barrel exports for the module |
| `KnownPersonCard.tsx` | Display card for known person in grid layout |
| `KnownPersonCard.test.tsx` | Test suite for KnownPersonCard |

## Related Files

| File | Purpose |
|------|---------|
| `frontend/src/types/faceRecognition.ts` | TypeScript type definitions |
| `frontend/src/services/faceRecognitionApi.ts` | API client for face recognition endpoints |
| `frontend/src/hooks/useFaceRecognition.ts` | React Query hooks for data fetching |
| `backend/api/routes/face_recognition.py` | Backend API endpoints |
| `backend/api/schemas/face_recognition.py` | Backend Pydantic schemas |
| `backend/services/face_detector.py` | Face detection service |
| `backend/services/household_matcher.py` | Household member matching service |

## Component Hierarchy

```
FaceRecognitionPage
|-- KnownPersonsTab
|   |-- KnownPersonCard[]
|   |-- UnknownStrangersPanel
|   +-- FaceStatsCards
|-- FaceEventsTab
|   +-- FaceEventCard[]
+-- PersonTrackingTab
    |-- PersonJourneyTimeline
    +-- FaceStatsCards (PersonStats variant)

Modals (rendered at page level):
|-- KnownPersonDetailModal
|-- AddPersonModal
|-- EnrollFaceModal
+-- IdentifyPersonModal
```

## Key Components

### KnownPersonCard.tsx

**Purpose:** Display card for a known person in the face recognition grid with avatar, name, badges, and context menu.

**Key Features:**

- Person avatar with placeholder icon
- Name display with truncation for long names
- Embedding count badge with visual feedback (green check vs yellow warning)
- Household member badge when applicable
- Context menu for edit/delete actions
- Hover state with NVIDIA green highlight
- Full keyboard accessibility (Enter/Space to select)

**Props:**

```typescript
interface KnownPersonCardProps {
  /** The known person data to display */
  person: KnownPerson;
  /** Callback when the card is clicked/selected */
  onSelect: (person: KnownPerson) => void;
  /** Optional callback for edit action */
  onEdit?: (person: KnownPerson) => void;
  /** Optional callback for delete action */
  onDelete?: (person: KnownPerson) => void;
  /** Additional CSS classes */
  className?: string;
}
```

**State Management:** Stateless component using memo for performance optimization.

### Planned Components (NEM-4688)

#### Tab Components

| Component | Purpose | Phase |
|-----------|---------|-------|
| `KnownPersonsTab` | Grid view of known persons with search and filters | 2 |
| `FaceEventsTab` | Chronological feed of face detection events | 2 |
| `PersonTrackingTab` | Journey visualization for a selected person | 3 |

#### Card Components

| Component | Purpose | Phase |
|-----------|---------|-------|
| `FaceEventCard` | Display card for face detection event with thumbnail | 2 |

#### Modal Components

| Component | Purpose | Phase |
|-----------|---------|-------|
| `KnownPersonDetailModal` | Full detail view with embeddings and appearances | 2 |
| `AddPersonModal` | Form for adding a new known person | 2 |
| `EnrollFaceModal` | Enroll face from detection into known person | 2 |
| `IdentifyPersonModal` | Manually identify unknown face as known person | 2 |

#### Panel Components

| Component | Purpose | Phase |
|-----------|---------|-------|
| `UnknownStrangersPanel` | Alert panel showing recent unknown faces | 3 |
| `FaceStatsCards` | Statistics cards for face detection metrics | 3 |

#### Timeline Components

| Component | Purpose | Phase |
|-----------|---------|-------|
| `PersonJourneyTimeline` | Visual timeline of person appearances across cameras | 3 |

## Important Patterns

### KnownPerson Data Model

```typescript
interface KnownPerson {
  id: number;
  name: string;
  is_household_member: boolean;
  embedding_count: number;
  notes: string | null;
  household_member_id?: number | null;
  created_at: string;
  updated_at: string;
}
```

### Face Detection Event Model

```typescript
interface FaceDetectionEvent {
  id: number;
  camera_id: number;
  camera_name: string;
  timestamp: string;
  bbox: [number, number, number, number]; // [x, y, width, height]
  matched_person_id?: number | null;
  matched_person_name?: string | null;
  match_confidence?: number | null;
  is_unknown: boolean;
  quality_score: number;
  thumbnail_url?: string | null;
  detection_id?: string | null;
  event_id?: number | null;
}
```

### Embedding Count Visual Feedback

The embedding count badge uses color coding to indicate enrollment status:

- **Green (0+ embeddings):** Person has enrolled faces, recognition active
- **Yellow (0 embeddings):** Person has no enrolled faces, needs enrollment

### Context Menu Pattern

Uses Headless UI Menu component with transition animations:

```typescript
<Menu as="div" className="relative">
  <Menu.Button>...</Menu.Button>
  <Transition as={Fragment} ...>
    <Menu.Items>
      <Menu.Item>{({ active }) => ...}</Menu.Item>
    </Menu.Items>
  </Transition>
</Menu>
```

## Styling Conventions

### KnownPersonCard

- Card: `bg-[#1A1A1A]`, `border-gray-700`, `hover:border-[#76B900]`
- Avatar: `w-16 h-16`, `rounded-full`, `bg-gray-700`
- Name: `text-white`, `font-medium`, `truncate`
- Badges: `text-xs`, color-coded by status
- Context menu: `bg-[#252525]`, `border-gray-700`

### Color Coding

- NVIDIA Green: `#76B900` - Primary accent, hover states
- Success/Active: `text-green-400` - Enrolled faces, active status
- Warning: `text-yellow-400` - Missing embeddings
- Household: `text-blue-400` - Household member badge
- Danger: `text-red-400` - Delete actions

## API Endpoints Used

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/face-recognition/known-persons` | List known persons |
| POST | `/api/face-recognition/known-persons` | Create known person |
| GET | `/api/face-recognition/known-persons/{id}` | Get known person details |
| PUT | `/api/face-recognition/known-persons/{id}` | Update known person |
| DELETE | `/api/face-recognition/known-persons/{id}` | Delete known person |
| GET | `/api/face-recognition/known-persons/{id}/embeddings` | List embeddings |
| POST | `/api/face-recognition/known-persons/{id}/enroll` | Enroll face |
| DELETE | `/api/face-recognition/embeddings/{id}` | Delete embedding |
| GET | `/api/face-recognition/events` | List face events |
| POST | `/api/face-recognition/events/{id}/identify` | Identify face |
| GET | `/api/face-recognition/stats` | Get face statistics |
| GET | `/api/face-recognition/known-persons/{id}/appearances` | Get appearances |
| GET | `/api/face-recognition/unknown-strangers` | Get unknown faces |

## Testing

Run component tests:

```bash
cd frontend && npm test -- --testPathPattern=face-recognition
```

Run specific test file:

```bash
cd frontend && npm test -- KnownPersonCard.test.tsx
```

Run type checking:

```bash
cd frontend && npm run typecheck
```

### Test Files

| File | Coverage |
|------|----------|
| `KnownPersonCard.test.tsx` | Card rendering, badges, context menu, keyboard nav |
| `KnownPersonsTab.test.tsx` | Tab rendering, person grid, search, filters |
| `FaceEventCard.test.tsx` | Event card rendering, thumbnails, actions |
| `AddPersonModal.test.tsx` | Form validation, submission, error handling |
| `KnownPersonDetailModal.test.tsx` | Detail view, embeddings list, appearances |

## Entry Points

- **Navigation**: Sidebar under ANALYTICS group as "Face Recognition"
- **Route**: `/face-recognition`
- **Component**: `FaceRecognitionPage` (lazy-loaded)

**Start here:** `KnownPersonCard.tsx` - Understand the card component pattern
**Then explore:** `index.ts` - See barrel exports and type re-exports

## Dependencies

- `@headlessui/react` - Menu, Transition for context menu
- `lucide-react` - Icons (User, Home, Check, AlertTriangle, MoreVertical, Pencil, Trash2)
- `react` - memo, useCallback, Fragment

## Future Enhancements

- Face thumbnail grid in person cards
- Similarity search for unknown faces
- Batch enrollment from camera feed
- Face clustering for unknown persons
- Real-time face event WebSocket updates
- Person re-identification across cameras
- Face quality score filtering
- Confidence threshold configuration
- Face embedding visualization
- Export known persons database
