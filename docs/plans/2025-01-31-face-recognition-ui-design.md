# Face Recognition & Person Re-ID UI Design

**Date:** 2025-01-31
**Status:** Approved
**Priority:** HIGH
**Complexity:** Comprehensive
**Epic:** NEM-4688

## Problem Statement

The backend has comprehensive face recognition and person re-identification capabilities, but NO frontend UI exists:

- `face_detector.py` - YOLO11 face detection
- `reid_service.py` - CLIP embeddings for person re-ID
- `household_matcher.py` - Match detections to known people
- `face_recognition_service.py` - Known persons database

Users cannot:

- View or manage known persons
- Enroll faces from detections
- See unknown stranger alerts
- Track person appearances across cameras

## Goals

1. Create Face Recognition management page
2. Enable face enrollment from detections
3. Display unknown stranger alerts
4. Show person tracking timeline
5. Integrate with household members

## Non-Goals

- Real-time face detection overlay (performance concern)
- Face search across video archives
- Age/gender estimation UI (data exists but not priority)

---

## Architecture Overview

```
/face-recognition (NEW)
├── Known Persons Tab
│   ├── Person List
│   ├── Person Detail Modal
│   └── Add Person Flow
├── Face Events Tab
│   ├── Recent Detections
│   ├── Unknown Strangers
│   └── Match Results
└── Person Tracking Tab
    ├── Appearance Timeline
    └── Cross-Camera Journey
```

---

## Data Model Relationships

```
HouseholdMember (existing)
    ↓ (optional link)
KnownPerson
    ↓ (1:many)
FaceEmbedding (512-dim ArcFace)
    ↓ (matches)
FaceDetectionEvent
    ↓ (links to)
Detection → Entity (768-dim CLIP)
```

**Note:** Two separate embedding systems exist:

- Face embeddings: 512-dim ArcFace (face-specific)
- Person re-ID: 768-dim CLIP (full-body)

Future integration could cross-reference these.

---

## API Endpoints

### Existing Endpoints (Already Available)

```
# Known Persons
GET    /api/known-persons
POST   /api/known-persons
GET    /api/known-persons/{id}
PATCH  /api/known-persons/{id}
DELETE /api/known-persons/{id}
POST   /api/known-persons/{id}/embeddings
GET    /api/known-persons/{id}/embeddings
DELETE /api/known-persons/{id}/embeddings/{embedding_id}

# Face Events
GET    /api/face-events
GET    /api/face-events/unknown
POST   /api/face-events/match
```

### New Endpoints Needed

```
POST /api/known-persons/{id}/enroll-from-detection
  - Create face embedding from detection image
  - Body: { detection_id: string }
  - Returns: { success, embedding_id, quality_score }

GET /api/known-persons/{id}/appearances
  - Get appearance timeline for person
  - Query: start_date, end_date, camera_id?
  - Returns: { appearances: [{ timestamp, camera_id, detection_id, confidence }] }

POST /api/face-events/{event_id}/identify
  - Manually identify unknown face as known person
  - Body: { known_person_id: string }
  - Returns: { success, created_embedding: boolean }

GET /api/face-events/stats
  - Face detection statistics
  - Returns: { total_today, known_count, unknown_count, by_camera: {...} }

PATCH /api/household/members/{id}/link-person
  - Link household member to known person
  - Body: { known_person_id: string }
  - Returns: { success }
```

### Backend Fix Needed

```
# Currently placeholder - needs real implementation
POST /api/household/members/{id}/embeddings
  - Currently returns hardcoded "placeholder_embedding"
  - Should extract and store actual embedding
```

---

## Page Layout

### Face Recognition Page (`/face-recognition`)

```
┌─────────────────────────────────────────────────────────────┐
│  Face Recognition                                           │
├─────────────────────────────────────────────────────────────┤
│  [Known Persons] [Face Events] [Person Tracking]            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Known Persons (12)                    [+ Add Person]       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐    │   │
│  │ │ 👤  │ │ 👤  │ │ 👤  │ │ 👤  │ │ 👤  │ │ 👤  │    │   │
│  │ │John │ │Jane │ │ Bob │ │Alice│ │ Tom │ │ Sue │    │   │
│  │ │ ✓3  │ │ ✓2  │ │ ✓1  │ │ ✓4  │ │ ✓2  │ │ ✓1  │    │   │
│  │ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Recent Unknown Faces                   [View All →]        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ┌─────┐  10:32 AM - Front Door                      │   │
│  │ │ 👤? │  Unknown person detected                    │   │
│  │ └─────┘  [Identify] [Dismiss] [Add as New Person]   │   │
│  │                                                     │   │
│  │ ┌─────┐  9:15 AM - Driveway                         │   │
│  │ │ 👤? │  Unknown person detected                    │   │
│  │ └─────┘  [Identify] [Dismiss] [Add as New Person]   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Today's Stats                                              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │ Total   │ │ Known   │ │ Unknown │ │ Cameras │          │
│  │   47    │ │   38    │ │    9    │ │    4    │          │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Known Person Detail Modal

```
┌─────────────────────────────────────────────────────────────┐
│  John Smith                              [Edit] [Delete]    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  Name: John Smith                         │
│  │             │  Role: Family Member                       │
│  │   Primary   │  Trust Level: Full                         │
│  │    Photo    │  Linked Household: Yes (John S.)           │
│  │             │  Created: Jan 15, 2025                      │
│  └─────────────┘                                            │
│                                                             │
│  Face Embeddings (3)                    [+ Add from Event]  │
│  ┌───────┐ ┌───────┐ ┌───────┐                             │
│  │ Face1 │ │ Face2 │ │ Face3 │                             │
│  │ Q:0.92│ │ Q:0.88│ │ Q:0.85│                             │
│  │  [×]  │ │  [×]  │ │  [×]  │                             │
│  └───────┘ └───────┘ └───────┘                             │
│                                                             │
│  Recent Appearances                                         │
│  ────────────────────────────────────────────────────────  │
│  Today 10:32 AM    Front Door      95% confidence          │
│  Today 8:15 AM     Driveway        92% confidence          │
│  Yesterday 6:45 PM Backyard        89% confidence          │
│  [View Full Timeline →]                                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Face Events Tab

```
┌─────────────────────────────────────────────────────────────┐
│  Face Events                    [All ▼] [Camera ▼] [Date ▼]│
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────┬───────────────────────────────────────────────┐   │
│  │     │ 10:32 AM - Front Door                         │   │
│  │ 👤  │ Matched: John Smith (95% confidence)          │   │
│  │     │ [View Detection]                              │   │
│  ├─────┼───────────────────────────────────────────────┤   │
│  │     │ 10:28 AM - Driveway                           │   │
│  │ 👤? │ Unknown person                                │   │
│  │     │ [Identify] [Add New] [Dismiss]                │   │
│  ├─────┼───────────────────────────────────────────────┤   │
│  │     │ 9:45 AM - Front Door                          │   │
│  │ 👤  │ Matched: Jane Smith (91% confidence)          │   │
│  │     │ [View Detection]                              │   │
│  └─────┴───────────────────────────────────────────────┘   │
│                                                             │
│  [Load More]                                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Person Tracking Tab

```
┌─────────────────────────────────────────────────────────────┐
│  Person Tracking                         [Person: John ▼]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Today's Journey                                            │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  8:15 AM ──○── Driveway (arrived)                          │
│            │                                                │
│  8:17 AM ──○── Front Door (entered)                        │
│            │                                                │
│  10:32 AM ─○── Front Door (exited)                         │
│            │                                                │
│  10:34 AM ─○── Driveway (departed)                         │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  [Camera view with path overlay]                     │  │
│  │  Showing movement across 4 cameras                   │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  Statistics (Last 7 Days)                                   │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐                       │
│  │Sightings│ │Avg/Day  │ │Cameras  │                       │
│  │   23    │ │   3.3   │ │    4    │                       │
│  └─────────┘ └─────────┘ └─────────┘                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Components

### New Components

| Component                | Purpose                      |
| ------------------------ | ---------------------------- |
| `FaceRecognitionPage`    | Main page with tabs          |
| `KnownPersonsTab`        | Grid of known persons        |
| `KnownPersonCard`        | Person thumbnail with count  |
| `KnownPersonDetailModal` | Full person details          |
| `AddPersonModal`         | Create new known person      |
| `FaceEmbeddingGallery`   | Display face embeddings      |
| `EnrollFaceModal`        | Enroll face from detection   |
| `FaceEventsTab`          | Face detection event feed    |
| `FaceEventCard`          | Individual face event        |
| `IdentifyPersonModal`    | Identify unknown as known    |
| `UnknownStrangersPanel`  | Highlight unknown faces      |
| `PersonTrackingTab`      | Person journey timeline      |
| `PersonJourneyTimeline`  | Vertical timeline            |
| `PersonJourneyMap`       | Camera path visualization    |
| `FaceStatsCards`         | Today's face detection stats |

### Component Hierarchy

```
FaceRecognitionPage
├── TabGroup
│   ├── KnownPersonsTab
│   │   ├── KnownPersonCard[]
│   │   │   └── KnownPersonDetailModal
│   │   │       ├── FaceEmbeddingGallery
│   │   │       └── AppearanceTimeline
│   │   └── AddPersonModal
│   │       └── EnrollFaceModal
│   ├── FaceEventsTab
│   │   ├── FaceEventCard[]
│   │   │   ├── IdentifyPersonModal
│   │   │   └── AddPersonModal
│   │   └── UnknownStrangersPanel
│   └── PersonTrackingTab
│       ├── PersonSelector
│       ├── PersonJourneyTimeline
│       └── PersonJourneyMap
└── FaceStatsCards
```

---

## Hooks

```typescript
// useKnownPersons.ts
export function useKnownPersons() {
  return useQuery({
    queryKey: ['known-persons'],
    queryFn: () => fetchApi('/api/known-persons'),
  });
}

export function useKnownPerson(id: string) {
  return useQuery({
    queryKey: ['known-person', id],
    queryFn: () => fetchApi(`/api/known-persons/${id}`),
    enabled: !!id,
  });
}

export function useCreateKnownPerson() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateKnownPersonRequest) =>
      fetchApi('/api/known-persons', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => queryClient.invalidateQueries(['known-persons']),
  });
}

export function useEnrollFace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ personId, detectionId }: { personId: string; detectionId: string }) =>
      fetchApi(`/api/known-persons/${personId}/enroll-from-detection`, {
        method: 'POST',
        body: JSON.stringify({ detection_id: detectionId }),
      }),
    onSuccess: (_, { personId }) => queryClient.invalidateQueries(['known-person', personId]),
  });
}

// useFaceEvents.ts
export function useFaceEvents(filters?: FaceEventFilters) {
  return useInfiniteQuery({
    queryKey: ['face-events', filters],
    queryFn: ({ pageParam }) =>
      fetchApi(`/api/face-events?cursor=${pageParam}&${buildQueryString(filters)}`),
    getNextPageParam: (lastPage) => lastPage.next_cursor,
  });
}

export function useUnknownStrangers() {
  return useQuery({
    queryKey: ['face-events-unknown'],
    queryFn: () => fetchApi('/api/face-events/unknown'),
    refetchInterval: 30000, // Check for new unknowns
  });
}

export function useIdentifyFace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ eventId, personId }: { eventId: string; personId: string }) =>
      fetchApi(`/api/face-events/${eventId}/identify`, {
        method: 'POST',
        body: JSON.stringify({ known_person_id: personId }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries(['face-events']);
      queryClient.invalidateQueries(['face-events-unknown']);
    },
  });
}

export function useFaceStats() {
  return useQuery({
    queryKey: ['face-stats'],
    queryFn: () => fetchApi('/api/face-events/stats'),
  });
}

// usePersonTracking.ts
export function usePersonAppearances(personId: string, dateRange?: DateRange) {
  return useQuery({
    queryKey: ['person-appearances', personId, dateRange],
    queryFn: () =>
      fetchApi(`/api/known-persons/${personId}/appearances?${buildDateQuery(dateRange)}`),
    enabled: !!personId,
  });
}
```

---

## Enrollment Flow

### From Detection (Most Common)

```
1. User sees detection with face in event timeline
2. Clicks "Add to Known Persons" on detection
3. Modal opens with:
   - Face crop preview
   - Quality score
   - Option to create new person OR add to existing
4. User selects/creates person
5. System:
   - Extracts face embedding from detection image
   - Stores embedding linked to person
   - Updates face event as "identified"
```

### From Face Event

```
1. User views unknown face event
2. Clicks "Identify" button
3. Modal shows list of known persons with thumbnails
4. User selects matching person
5. System:
   - Links face event to person
   - Optionally creates new embedding if quality is good
```

### Manual Upload (Future)

Not in MVP scope - would require separate image upload endpoint.

---

## Integration Points

### Event Timeline Integration

Add "Enroll Face" button to event detail modal when face detected:

```typescript
// In EventDetailModal
{hasFaceDetection && (
  <Button onClick={() => setShowEnrollModal(true)}>
    Add Face to Known Persons
  </Button>
)}
```

### Household Settings Integration

Link known persons to household members:

```typescript
// In HouseholdSettings member form
<Select
  label="Linked Known Person"
  options={knownPersons}
  value={member.known_person_id}
  onChange={handleLinkPerson}
/>
```

### Entity Page Integration

Show linked known person on entity cards:

```typescript
// In EntityCard
{entity.linked_person && (
  <Badge>Known: {entity.linked_person.name}</Badge>
)}
```

---

## Error Handling

| Scenario             | Handling                                |
| -------------------- | --------------------------------------- |
| No face in detection | Disable "Enroll" button, show tooltip   |
| Low quality face     | Warning before enrollment               |
| Duplicate person     | Suggest merge with existing             |
| Enrollment fails     | Toast with retry option                 |
| No known persons     | Empty state with "Add First Person" CTA |

---

## Testing Strategy

### Unit Tests

- Component rendering
- Hook data transformations
- Enrollment flow logic

### Integration Tests

- Create person → enroll face → verify appears
- Identify unknown → verify updated
- Person tracking timeline loads

### E2E Tests

- Full enrollment flow from detection
- Unknown stranger identification
- Person tracking journey view

---

## Rollout Plan

### Phase 1: Known Persons Management (Epic)

1. Backend: Fix household embeddings endpoint (placeholder)
2. Backend: Add enroll-from-detection endpoint
3. Backend: Add appearances endpoint
4. Frontend: Page skeleton and routing
5. Frontend: Known persons grid and cards
6. Frontend: Person detail modal
7. Frontend: Add/edit person forms

### Phase 2: Face Events & Enrollment (Epic)

1. Frontend: Face events tab
2. Frontend: Face event cards
3. Frontend: Unknown strangers panel
4. Frontend: Enroll face modal
5. Frontend: Identify person modal
6. Integration: Event timeline "Enroll" button

### Phase 3: Person Tracking (Epic)

1. Frontend: Person tracking tab
2. Frontend: Journey timeline component
3. Frontend: Journey map visualization
4. Frontend: Statistics cards

### Phase 4: Integration & Polish (Epic)

1. Household member linking
2. Entity page integration
3. Real-time unknown stranger alerts
4. Performance optimization

---

## Decisions (Finalized 2025-01-31)

1. **Face enrollment minimum quality score**

   - **Decision:** Yes, 0.7 minimum with warning for 0.7-0.8
   - Block enrollments < 0.7, yellow warning 0.7-0.8, green ≥ 0.8

2. **Maximum embeddings per person**

   - **Decision:** 10 max, with option to replace low-quality ones
   - Good balance of recognition accuracy vs matching performance

3. **Unknown strangers expiry**

   - **Decision:** Auto-delete after 30 days (matches event retention policy)
   - Keeps data manageable while preserving recent security-relevant data

4. **Real-time alerts for unknown strangers**
   - **Decision:** Yes, WebSocket notification + optional push
   - In-app real-time badge/toast, optional browser push notifications
