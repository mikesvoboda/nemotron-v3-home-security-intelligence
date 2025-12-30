# Entities Components Directory

## Purpose

Contains components for entity tracking and identification. Currently a placeholder for future functionality that will track people and vehicles detected across cameras.

**Status: Work in Progress (WIP)**

## Files

| File                    | Purpose                              |
| ----------------------- | ------------------------------------ |
| `EntitiesPage.tsx`      | Placeholder page for entity tracking |
| `EntitiesPage.test.tsx` | Test suite for EntitiesPage          |

## Key Components

### EntitiesPage.tsx

**Purpose:** Placeholder component displaying planned entity tracking features

**Props Interface:**

```typescript
// No props - standalone page component
```

**Current Implementation:**

- "Coming Soon" placeholder UI
- Feature description list
- NVIDIA dark theme styling
- Users icon with green accent

**Planned Features (from UI):**

1. Track detected people and vehicles over time
2. View movement patterns across multiple cameras
3. Classify entities as known or unknown
4. Search and filter entity history

**Usage:**

```tsx
import EntitiesPage from './components/entities/EntitiesPage';

// In router
<Route path="/entities" element={<EntitiesPage />} />;
```

## Future Implementation Notes

When implementing entity tracking, consider:

### Data Model

```typescript
interface Entity {
  id: string;
  type: 'person' | 'vehicle' | 'other';
  first_seen_at: string;
  last_seen_at: string;
  camera_ids: string[];
  known: boolean;
  label?: string; // "John", "Delivery Van", etc.
  thumbnail_url?: string;
  detection_count: number;
}
```

### Planned Components

- `EntityCard` - Display individual entity with thumbnail
- `EntityTimeline` - Show entity appearances over time
- `EntityGrid` - Grid view of all tracked entities
- `EntityDetailModal` - Detailed entity view with history
- `EntityFilters` - Filter by type, known/unknown, date range

### API Endpoints (Future)

- `GET /api/entities` - List tracked entities
- `GET /api/entities/:id` - Get entity details
- `PATCH /api/entities/:id` - Update entity (mark as known, add label)
- `GET /api/entities/:id/timeline` - Get entity appearance history

### Integration Points

- Object detection (RT-DETRv2) provides initial detections
- Re-identification model matches detections to entities
- Face recognition (optional) for person identification
- License plate recognition (optional) for vehicles

## Styling Conventions

- Page background: inherited from Layout
- Placeholder container: bg-[#1F1F1F], border-gray-800
- Icon circle: bg-[#76B900]/10
- Feature bullets: bg-[#76B900] (green dots)
- Header icon: text-[#76B900] (NVIDIA green)

## Testing

### EntitiesPage.test.tsx

Tests cover:

- Renders "Coming Soon" message
- Displays feature list items
- Shows appropriate icons
- Has correct page structure

## Dependencies

- `lucide-react` - Users, Clock icons

## Entry Points

**Start here:** `EntitiesPage.tsx` - Understand the placeholder structure and planned features

## Development Roadmap

1. **Phase 1:** Backend entity tracking service
2. **Phase 2:** Re-identification model integration
3. **Phase 3:** Entity API endpoints
4. **Phase 4:** EntityCard and EntityGrid components
5. **Phase 5:** EntityDetailModal and timeline view
6. **Phase 6:** Search and filtering
7. **Phase 7:** Known entity management
