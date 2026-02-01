# Face Recognition and Person Re-ID Coverage Analysis

## Executive Summary

The system has **comprehensive backend capabilities** for face recognition and person re-identification, but **significant gaps exist in frontend exposure**. This represents one of the largest feature gaps in the codebase.

## Backend Services

### 1. Face Detection Service (`backend/services/face_detector.py`)

**Capabilities:**

- Detects faces within person bounding box regions using YOLO11
- Async face detection with metrics
- Bbox conversion and image processing
- Detection counts, embedding duration, confidence scores (NEM-4143)

### 2. Re-Identification Service (`backend/services/reid_service.py`)

**Capabilities:**

- CLIP ViT-L embeddings (768-dim) via HTTP service (ai-clip)
- Methods:
  - `generate_embedding()` - with bbox validation, retry logic, timeout
  - `store_embedding()` - Redis + PostgreSQL persistence (NEM-4474 Lua scripts)
  - `find_matching_entities()` - batch similarity matching (NEM-1071)
  - `get_entity_history()` - 24-hour Redis + historical queries
- Hybrid storage: 30-day PostgreSQL retention (NEM-2499)
- Metrics: attempts, matches, duration, cross-camera handoffs (NEM-4140)

### 3. Household Matcher Service (`backend/services/household_matcher.py`)

**Capabilities:**

- Person matching via embedding similarity (0.85 threshold)
- Vehicle matching: license plate (exact, priority) or visual embedding
- Methods:
  - `match_person()` - embed similarity matching
  - `match_vehicle()` - plate + visual matching
  - `match_detections()` - detection-attributed matching (NEM-4234)
- Cached embedding extraction (NEM-4234 Phase 3):
  - `extract_person_embedding()` - OSNet 512-dim
  - `extract_vehicle_embedding()` - CLIP 768-dim
  - `extract_face_embedding()` - CLIP 768-dim

### 4. Entity Clustering Service (`backend/services/entity_clustering_service.py`)

**Capabilities:**

- Groups detections into canonical entities via embedding similarity
- Methods:
  - `assign_entity()` - match or create entity (0.85 threshold)
  - `_update_entity_with_detection()` - update seen timestamp, count
  - `_create_entity()` - new entity creation
- Webhook events (NEM-3624): ENTITY_DISCOVERED on new entity
- Tracks `cameras_seen` in entity_metadata (NEM-2453)

## API Endpoints

### Face Recognition Endpoints

| Method | Endpoint                                  | Description                   |
| ------ | ----------------------------------------- | ----------------------------- |
| GET    | `/api/known-persons`                      | List known persons            |
| POST   | `/api/known-persons`                      | Create person                 |
| GET    | `/api/known-persons/{id}`                 | Get person                    |
| PATCH  | `/api/known-persons/{id}`                 | Update person                 |
| DELETE | `/api/known-persons/{id}`                 | Delete person                 |
| POST   | `/api/known-persons/{id}/embeddings`      | Add 512-dim ArcFace embedding |
| GET    | `/api/known-persons/{id}/embeddings`      | List embeddings               |
| DELETE | `/api/known-persons/{id}/embeddings/{id}` | Delete embedding              |
| GET    | `/api/face-events`                        | List face detection events    |
| GET    | `/api/face-events/unknown`                | Unknown stranger alerts       |
| POST   | `/api/face-events/match`                  | Match 512-dim face embedding  |

### Household Management Endpoints

| Method | Endpoint                                 | Description                  |
| ------ | ---------------------------------------- | ---------------------------- |
| GET    | `/api/household/members`                 | List members                 |
| POST   | `/api/household/members`                 | Create member                |
| GET    | `/api/household/members/{id}`            | Get member                   |
| PATCH  | `/api/household/members/{id}`            | Update member                |
| DELETE | `/api/household/members/{id}`            | Delete member                |
| GET    | `/api/household/vehicles`                | List vehicles                |
| POST   | `/api/household/vehicles`                | Create vehicle               |
| GET    | `/api/household/vehicles/{id}`           | Get vehicle                  |
| PATCH  | `/api/household/vehicles/{id}`           | Update vehicle               |
| DELETE | `/api/household/vehicles/{id}`           | Delete vehicle               |
| POST   | `/api/household/members/{id}/embeddings` | Add embedding (PLACEHOLDER!) |

### Entity Re-ID Endpoints

| Method | Endpoint                               | Description               |
| ------ | -------------------------------------- | ------------------------- |
| GET    | `/api/entities`                        | List entities             |
| GET    | `/api/entities/stats`                  | Statistics by type/camera |
| GET    | `/api/entities/trusted`                | List trusted              |
| GET    | `/api/entities/untrusted`              | List untrusted            |
| PATCH  | `/api/entities/{id}/trust`             | Update trust status       |
| GET    | `/api/entities/{id}`                   | Get entity details        |
| GET    | `/api/entities/{id}/history`           | Appearance timeline       |
| GET    | `/api/entities/matches/{detection_id}` | Find re-ID matches        |

## Frontend Components

### Household Management (`HouseholdSettings.tsx`)

**Implemented:**

- CRUD for members and vehicles
- Member form: name, role, trust_level, notes
- Vehicle form: description, type, plate, color, owner, trusted flag
- Member roles: resident, family, service_worker, frequent_visitor
- Trust levels: full, partial, monitor

### Entity Management

**Implemented:**

- `EntityDetailModal.tsx` - Entity details with:
  - Trust classification controls
  - Detection history visualization
  - Appearance timeline across cameras
  - "View Events" navigation
- `EntityCard.tsx` - Summary cards
- `EntityTimeline.tsx` - Appearance timeline
- `EntityStatsCard.tsx` - Statistics

## Database Models

### Face Models (`backend/models/face_identity.py`)

| Model              | Fields                                            |
| ------------------ | ------------------------------------------------- |
| KnownPerson        | name, household_member, notes                     |
| FaceEmbedding      | 512-dim ArcFace, quality_score, source_image_path |
| FaceDetectionEvent | bbox, confidence, age/gender estimates            |

### Household Models (`backend/models/household.py`)

| Model             | Fields                              |
| ----------------- | ----------------------------------- |
| HouseholdMember   | role, trust_level, typical_schedule |
| PersonEmbedding   | cached from detections              |
| RegisteredVehicle | plate, type, color, reid_embedding  |

### Entity Models (`backend/models/entity.py`)

| Model  | Fields                                                     |
| ------ | ---------------------------------------------------------- |
| Entity | type, first_seen, last_seen, detection_count, trust_status |

## Critical Gaps

### Missing UI Components (0% Coverage)

1. **Face Management UI**

   - No way to view/manage known persons
   - No way to view/manage face embeddings
   - No face gallery or enrollment interface

2. **Face Event Viewer**

   - No UI for `/api/face-events` endpoint
   - No unknown stranger alerts dashboard
   - No face detection history view

3. **Person Embedding/Face Enrollment UI**

   - No workflow to add faces from detections
   - No quality assessment during enrollment
   - No bulk face enrollment

4. **Face Match Testing UI**
   - No interface for `/api/face-events/match`
   - No similarity score visualization
   - No face comparison tool

### Missing Household UI Coverage

1. **No embedded member photo/thumbnail management**
2. **No embedding source/quality UI**
3. **No "assign person from detection" workflow**
4. **No schedule management UI** (typical_schedule field exists but unused)

### Missing Person Tracking UI

1. **No persistent person tracking history** beyond entity re-ID
2. **No person cross-reference** between entities and household members
3. **No person profile page** (all detections linked to a member)
4. **No "add person from detection" quick action**

## Backend Issues

1. **`POST /members/{id}/embeddings` has placeholder implementation** (hardcoded "placeholder_embedding")
2. **No face quality filtering** in face event endpoints
3. **Face detection metrics** record "unknown" status at detection time, never updated to "known"
4. **No automatic face enrollment** from high-confidence detections
5. **Limited integration** between face recognition and household matcher

## API/Data Flow Issues

1. **Separate embedding systems:**

   - Face embeddings: 512-dim ArcFace
   - Person re-ID embeddings: 768-dim CLIP
   - No automatic face-to-person mapping

2. **EntityDetailed appearances** missing actual face detection data

3. **Re-ID service doesn't leverage face embeddings** for person matching

## Recommended Actions

### High Priority

1. **Create Face Recognition Page** (`/face-recognition`)

   - Known persons list with CRUD
   - Face embedding gallery per person
   - Enrollment workflow from detections

2. **Create Face Events Dashboard**

   - Unknown stranger alerts with thumbnails
   - Face detection history with filters
   - Quick action: "Add to known persons"

3. **Fix Household Embedding Endpoint**
   - Remove placeholder implementation
   - Implement actual embedding storage

### Medium Priority

1. **Integrate Face + Re-ID Systems**

   - Cross-reference face embeddings with entity embeddings
   - Auto-match faces to entities

2. **Add Person Profile Page**

   - Show all detections linked to household member
   - Timeline across cameras
   - Face recognition matches

3. **Schedule Management UI**
   - Allow setting typical_schedule for members
   - Use for anomaly detection

### Low Priority

1. **Face Quality Assessment UI**
2. **Bulk Face Enrollment**
3. **Face Similarity Comparison Tool**
