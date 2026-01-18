# Entities

The Entities page provides comprehensive tracking and re-identification of people and vehicles detected across your security camera network. Using AI-powered visual embeddings, the system automatically recognizes when the same person or vehicle appears on different cameras.

## What You're Looking At

The Entities page is your central hub for entity tracking and management. It provides:

- **Entity Grid** - Visual cards showing all tracked persons and vehicles
- **Statistics Card** - Overview of total entities, appearances, and repeat visitors
- **Filtering Controls** - Filter by type, time range, camera, data source, and trust status
- **Detail Modal** - Full entity history with detection images and appearance timeline

When a person or vehicle is detected, the system generates a 768-dimensional CLIP embedding (visual fingerprint) that allows matching across different camera views with high accuracy.

## Key Components

### Entity Cards

Each entity card displays:

- **Entity Type Badge** - Person (user icon) or Vehicle (car icon) with NVIDIA green (#76B900) accent
- **Trust Status Badge** - Trusted (green shield with checkmark), Suspicious (amber warning triangle), or no badge for Unknown/Unclassified
- **Thumbnail** - Most recent detection image (128px height), or placeholder icon matching entity type
- **Appearance Count** - How many times this entity has been detected (eye icon)
- **Cameras Seen** - Number of unique cameras where the entity appeared (camera icon)
- **Timestamps** - When the entity was first and last seen (relative formatting like "5 minutes ago", "2 days ago")
- **Entity ID** - Truncated UUID displayed in the card header (hover for full ID)

Click any entity card to open the detail modal with full history. Cards support keyboard navigation (Enter/Space to activate).

### Entity Statistics Card

The collapsible statistics panel at the top shows:

- **Total Entities** - Unique persons and vehicles tracked
- **Persons Count** - Number of tracked people
- **Vehicles Count** - Number of tracked vehicles
- **Repeat Visitors** - Entities seen more than once
- **Total Appearances** - Sum of all detection events

Toggle the "Stats" button to show/hide this panel. Data refreshes automatically every 60 seconds.

### Re-Identification (CLIP Embeddings)

The system uses CLIP ViT-L (Vision Transformer Large) to generate visual embeddings for person and vehicle re-identification across cameras.

**How It Works:**

1. **Detection** - RT-DETRv2 detects a person or vehicle in a camera frame
2. **Embedding Generation** - The detected region is cropped and processed through the CLIP model
3. **768-Dimensional Vector** - The model outputs a compact visual fingerprint (embedding)
4. **Cosine Similarity Matching** - New embeddings are compared against existing entity embeddings using cosine similarity
5. **Entity Assignment** - If similarity >= 85% (configurable `DEFAULT_SIMILARITY_THRESHOLD = 0.85`), the detection is linked to an existing entity; otherwise, a new entity is created

**What CLIP Can Match:**

- Same person at different angles or poses
- Same person across different cameras with varying lighting
- Same vehicle from different viewpoints
- Same person/vehicle over multiple days (within 30-day retention)

**Limitations:**

- Very different clothing may reduce person similarity scores
- Extreme lighting differences or occlusion can affect accuracy
- Very similar-looking individuals may be incorrectly merged (rare)
- Vehicles of the same make/model/color may match incorrectly

**Technical Details:**

- **Model**: CLIP ViT-L/14 (Vision Transformer Large with 14x14 patches)
- **Embedding Dimension**: 768 floats
- **Memory Usage**: ~800MB VRAM on GPU
- **Fallback**: CPU processing available if GPU is unavailable
- **TTL**: Embeddings cached in Redis for 24 hours (86400 seconds)

### Trust Classification

Entities can be classified based on whether they are known and trusted. This helps filter alerts and focus on unknown or suspicious activity.

**Trust Status Values:**

| Display Name   | API Value      | Color | Description                                                                     |
| -------------- | -------------- | ----- | ------------------------------------------------------------------------------- |
| **Trusted**    | `trusted`      | Green | Known individuals like family members, neighbors, or regular delivery personnel |
| **Suspicious** | `untrusted`    | Amber | Flagged entities that warrant attention or monitoring                           |
| **Unknown**    | `unclassified` | Gray  | Entities that haven't been classified (default state)                           |

**Setting Trust Status:**

Trust status can be set from the Entity Detail Modal using the action buttons:

- **"Mark as Trusted"** - Sets entity to `trusted` status (green shield icon)
- **"Mark as Suspicious"** - Sets entity to `untrusted` status (amber warning icon)
- **"Reset"** - Clears classification back to `unclassified` (gray shield icon)

**Use Cases:**

- Mark family members as "Trusted" to reduce alert noise
- Flag unknown visitors as "Suspicious" for monitoring
- Filter the entity list by trust status to focus on specific categories

**TrustClassificationControls Component:**

The standalone `TrustClassificationControls` component provides advanced trust management:

- **Status Badge** - Shows current trust status with appropriate icon and color
- **Help Tooltip** - Hover for description of current status
- **Action Buttons** - Click to change status (shows all three options)
- **Confirmation Dialog** - Requires confirmation before changing status
- **Loading State** - Shows spinner during API call
- **Error Handling** - Displays error message if update fails
- **Size Variants** - `sm`, `md`, `lg` for different contexts
- **Read-Only Mode** - Can display status badge without action buttons

### Entity Detail Modal

Clicking an entity card opens a modal with comprehensive entity information:

**Header Section:**

- Entity thumbnail (64px circular) or placeholder icon
- Entity type title with NVIDIA green icon (Person/Vehicle)
- Full entity ID (monospace font for easy copying)
- Current trust status badge with icon
- Trust classification action buttons (contextual - only shows options not currently set)

**Statistics Row (4 cards):**

- **Appearances** - Total detection count (eye icon)
- **Cameras** - Number of unique cameras (camera icon)
- **First seen** - Relative timestamp of first detection (clock icon)
- **Last seen** - Relative timestamp of most recent detection (clock icon)

**Cameras List:**

- Badge for each camera where the entity was detected
- Camera icon with camera name/ID

**Detection History:**

- **Image gallery** with previous/next navigation arrows
- **Thumbnail strip** for quick navigation (64px thumbnails with confidence scores)
- **Metadata card** for selected detection:
  - Camera name
  - Timestamp (relative format)
  - Object type badge
  - Confidence percentage
- **"View Full Size" button** opens a lightbox with full-resolution image
- **"Load more" button** for paginated detection history (infinite query)

**Appearance Timeline (`EntityTimeline` component):**

- Chronological list of all sightings (most recent first)
- Thumbnail (48px circular), camera name, and timestamp for each
- Similarity score badges (when available) in NVIDIA green
- Vertical dotted timeline connector visualization
- Empty state with entity-type icon when no appearances

**Modal Controls:**

- Close button (X icon) in header
- Close button in footer
- Click outside to close (backdrop)
- Smooth transitions using Headless UI

### Re-ID History Panel

The `ReidHistoryPanel` component provides advanced re-identification features for comparing entity appearances:

**Features:**

- **Side-by-Side Comparison** - Select up to 2 appearances to compare visually
- **Timeline View** - Chronological list of all appearances with thumbnails
- **Camera Tracking** - See which cameras captured each appearance

**Similarity Score Badges:**

Color-coded badges indicate matching confidence:

| Score Range | Color        | Meaning                               |
| ----------- | ------------ | ------------------------------------- |
| >= 90%      | Green        | High confidence match                 |
| >= 80%      | NVIDIA green | Good match                            |
| >= 70%      | Yellow       | Moderate confidence                   |
| < 70%       | Orange       | Lower confidence (may warrant review) |

**Attributes Display:**

When available, the panel shows extracted attributes for each appearance:

- Clothing color/type
- Vehicle color/make
- Other visual characteristics extracted by the AI

**Usage:**

1. Open an entity detail modal
2. Click on appearances in the timeline to select them
3. Select a second appearance to enable side-by-side comparison
4. Click "Clear" to reset the selection

## Settings & Configuration

### Filter Options

**Entity Type:**

- All - Show all tracked entities
- Persons - Show only people
- Vehicles - Show only vehicles

**Time Range:**

- All Time - No time filtering
- Last 1h - Entities seen in the past hour
- Last 24h - Entities seen in the past day
- Last 7d - Entities seen in the past week
- Last 30d - Entities seen in the past month
- Custom Range - Specify start/end dates

**Camera:**

- All Cameras - Show entities from all cameras
- Specific camera - Filter to a single camera

**Data Source:**

- All Sources - Combined Redis and PostgreSQL data
- Real-time (24h) - Redis hot cache only
- Historical (30d) - PostgreSQL persistence only

**Trust Status:**

- All Trust - Show all entities regardless of trust status (shows count)
- Trusted - Show only `trusted` entities (shows count)
- Suspicious - Show only `untrusted` entities (shows count)
- Unknown - Show only `unclassified` entities (shows count)

**Sort Options:**

- Last Seen - Most recently seen first
- First Seen - Most recently discovered first
- Appearances - Most frequently seen first

### Backend Configuration

Entity tracking behavior is configured via environment variables:

| Variable                       | Default | Description                                     |
| ------------------------------ | ------- | ----------------------------------------------- |
| `REID_MAX_CONCURRENT_REQUESTS` | 10      | Maximum concurrent re-identification operations |
| `REID_EMBEDDING_TIMEOUT`       | 30.0    | Timeout (seconds) for embedding generation      |
| `REID_MAX_RETRIES`             | 3       | Maximum retry attempts for transient failures   |

### Storage Architecture

Entities use a hybrid storage pattern:

- **Redis (Hot Cache)** - 24-hour TTL for fast recent lookups
- **PostgreSQL (Persistence)** - 30-day retention for historical data

The `HybridEntityStorage` service coordinates write-through storage to both systems and tiered reads (Redis first, PostgreSQL fallback).

## Troubleshooting

### Entity shows "No appearances recorded"

The entity record exists but no detection history was found. This can happen if:

1. The detection images were cleaned up (retention policy)
2. There was a data synchronization issue

Try refreshing the page or checking the Events page for related detections.

### Entities not matching across cameras

If the same person/vehicle creates multiple entity records:

1. **Lighting conditions** - Extreme lighting differences can affect embedding accuracy
2. **Angle variations** - Very different viewing angles may reduce similarity
3. **Threshold too high** - Consider if the 85% similarity threshold is appropriate

The system logs similarity scores - check backend logs for matching attempts.

### Entity images show placeholder instead of thumbnail

1. **Image not available** - The detection image may have been cleaned up
2. **Loading error** - Check browser network tab for failed image requests
3. **Path issue** - Verify the `/export/foscam/` mount is accessible

### Trust status not saving

1. **API error** - Check browser console for failed API requests
2. **Permissions** - Verify backend service is running
3. **Database** - Check PostgreSQL connection status

### Slow entity list loading

1. **Large dataset** - Use time range filters to limit results
2. **Pagination** - The page uses cursor-based infinite scroll with 50 items per page
3. **Background refresh** - Auto-refresh runs every 30 seconds; watch for the "Updating..." indicator
4. **Trust filtering** - Trust filtering happens client-side after data loads, which may cause slight delays on large datasets

### "Failed to load entity statistics" error

1. **Backend service** - Ensure the backend is running
2. **Database connection** - Check PostgreSQL connectivity
3. **Time range** - Very large time ranges may timeout

---

## Technical Deep Dive

For developers wanting to understand the underlying systems.

### Architecture

- **Re-Identification Pipeline**: [AI Pipeline Architecture](../architecture/ai-pipeline.md)
- **Data Model**: [Entity Data Model](../architecture/data-model.md)
- **Real-time Updates**: [WebSocket Implementation](../architecture/real-time.md)
- **System Overview**: [Architecture Overview](../architecture/overview.md)

### Key Services

**Backend Services:**

- `ReIdentificationService` - CLIP embedding generation and matching
- `EntityClusteringService` - Deduplication and entity assignment
- `HybridEntityStorage` - Redis/PostgreSQL coordination

**Frontend Hooks:**

- `useEntitiesInfiniteQuery` - Cursor-based paginated entity list with infinite scroll (30s auto-refresh)
- `useEntityDetailQuery` - Single entity detail fetch
- `useEntityHistory` - Entity detection history with infinite query pagination
- `useEntityStats` - Aggregated statistics (60s auto-refresh)
- `useEntitiesV2Query` - V2 API hook with historical support and source filtering

### Related Code

**Frontend:**

- Page Component: `frontend/src/components/entities/EntitiesPage.tsx`
- Entity Card: `frontend/src/components/entities/EntityCard.tsx`
- Detail Modal: `frontend/src/components/entities/EntityDetailModal.tsx`
- Timeline: `frontend/src/components/entities/EntityTimeline.tsx`
- Stats Card: `frontend/src/components/entities/EntityStatsCard.tsx`
- Trust Controls: `frontend/src/components/entities/TrustClassificationControls.tsx`
- Re-ID History: `frontend/src/components/entities/ReidHistoryPanel.tsx`
- Empty State: `frontend/src/components/entities/EntitiesEmptyState.tsx`

**Frontend Hooks:**

- Infinite Query: `frontend/src/hooks/useEntitiesInfiniteQuery.ts`
- Entity Query: `frontend/src/hooks/useEntitiesQuery.ts`
- Entity History: `frontend/src/hooks/useEntityHistory.ts`

**Backend:**

- Re-ID Service: `backend/services/reid_service.py`
- CLIP Loader: `backend/services/clip_loader.py`
- Clustering Service: `backend/services/entity_clustering_service.py`
- Hybrid Storage: `backend/services/hybrid_entity_storage.py`
- API Routes: `backend/api/routes/entities.py`

### API Endpoints

| Endpoint                     | Method | Description                               |
| ---------------------------- | ------ | ----------------------------------------- |
| `/api/entities`              | GET    | List entities with pagination and filters |
| `/api/entities/{id}`         | GET    | Get single entity with full details       |
| `/api/entities/{id}/history` | GET    | Get entity appearance history             |
| `/api/entities/{id}/trust`   | PUT    | Update entity trust status                |
| `/api/entities/stats`        | GET    | Get aggregated entity statistics          |

### CLIP Embedding Details

The CLIP ViT-L model provides:

- **768-dimensional embeddings** for robust visual representation
- **~800MB VRAM usage** on GPU
- **CPU fallback** available if GPU is unavailable
- **Cosine similarity matching** with 0.85 default threshold (`DEFAULT_SIMILARITY_THRESHOLD`)
- **Embedding TTL**: 24 hours (86400 seconds) in Redis cache

Embeddings are computed by the `ai-clip` container service, keeping the model in a dedicated container for better VRAM management.

### Empty State

When no entities have been tracked, the `EntitiesEmptyState` component displays:

- **Animated illustration** with floating icons (person, vehicle, location, clock)
- **Explanation** of what entities are and how they're created
- **"How it works" section** with 4 steps:
  1. Camera detects a person or vehicle
  2. AI extracts visual features
  3. System matches across all camera feeds
  4. Entity profile created with movement history
- **CTA button** linking to detection settings

This provides onboarding guidance for new users.
