# Orphaned Infrastructure Integration Design

**Date:** 2026-01-20
**Status:** Draft
**Epic:** NEM-3056 (Orphaned Frontend Features)

## Overview

This design addresses the integration of orphaned infrastructure discovered through codebase analysis:

- 51 unused backend API endpoints (71% of total)
- 30 unused frontend hooks
- 11+ orphaned WebSocket events
- 94 unused service functions
- 200+ backend config options not exposed in UI

The goal is to incorporate and expand functionality rather than delete unused code.

---

## 1. Organizational Hierarchy

### Current State

- `HouseholdMember` - people who shouldn't trigger alerts
- `RegisteredVehicle` - vehicles linked to household members
- `Camera` - standalone, no organizational grouping
- `Zone` - detection polygons on camera view

### Target State

```
Household (org unit, e.g., "Svoboda Family")
├── Members (people)
├── Vehicles (cars)
└── Properties (locations)
      ├── "Main House"
      └── "Beach House"
            ├── Areas (logical zones, e.g., "Front Yard", "Garage")
            │     └── many-to-many with Cameras
            └── Cameras
                  └── CameraZones (detection polygons)
```

### Database Changes

#### New Models

```python
# backend/models/property.py
class Property(Base):
    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"))
    name: Mapped[str] = mapped_column(String(100))  # "Main House"
    address: Mapped[str | None] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    household: Mapped["Household"] = relationship(back_populates="properties")
    areas: Mapped[list["Area"]] = relationship(back_populates="property")
    cameras: Mapped[list["Camera"]] = relationship(back_populates="property")
```

```python
# backend/models/area.py
class Area(Base):
    __tablename__ = "areas"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"))
    name: Mapped[str] = mapped_column(String(100))  # "Front Yard"
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(String(7), default="#76B900")  # For UI
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    property: Mapped["Property"] = relationship(back_populates="areas")
    cameras: Mapped[list["Camera"]] = relationship(
        secondary="camera_areas",
        back_populates="areas"
    )
```

```python
# backend/models/household.py (new parent model)
class Household(Base):
    __tablename__ = "households"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))  # "Svoboda Family"
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    members: Mapped[list["HouseholdMember"]] = relationship(back_populates="household")
    vehicles: Mapped[list["RegisteredVehicle"]] = relationship(back_populates="household")
    properties: Mapped[list["Property"]] = relationship(back_populates="household")
```

```python
# Association table for Camera <-> Area many-to-many
camera_areas = Table(
    "camera_areas",
    Base.metadata,
    Column("camera_id", String, ForeignKey("cameras.id"), primary_key=True),
    Column("area_id", Integer, ForeignKey("areas.id"), primary_key=True),
)
```

#### Model Renames

| Current | New          | Reason                         |
| ------- | ------------ | ------------------------------ |
| `Zone`  | `CameraZone` | Distinguish from logical Areas |

#### Model Updates

```python
# Camera gains property_id and areas relationship
class Camera(Base):
    property_id: Mapped[int | None] = mapped_column(ForeignKey("properties.id"))
    property: Mapped["Property"] = relationship(back_populates="cameras")
    areas: Mapped[list["Area"]] = relationship(
        secondary="camera_areas",
        back_populates="cameras"
    )

# HouseholdMember gains household_id
class HouseholdMember(Base):
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"))
    household: Mapped["Household"] = relationship(back_populates="members")

# RegisteredVehicle gains household_id
class RegisteredVehicle(Base):
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"))
    household: Mapped["Household"] = relationship(back_populates="vehicles")
```

### API Endpoints

#### New Endpoints

| Method | Path                                     | Description         |
| ------ | ---------------------------------------- | ------------------- |
| GET    | `/api/v1/households`                     | List households     |
| POST   | `/api/v1/households`                     | Create household    |
| GET    | `/api/v1/households/{id}`                | Get household       |
| PATCH  | `/api/v1/households/{id}`                | Update household    |
| DELETE | `/api/v1/households/{id}`                | Delete household    |
| GET    | `/api/v1/households/{id}/properties`     | List properties     |
| POST   | `/api/v1/households/{id}/properties`     | Create property     |
| GET    | `/api/v1/properties/{id}`                | Get property        |
| PATCH  | `/api/v1/properties/{id}`                | Update property     |
| DELETE | `/api/v1/properties/{id}`                | Delete property     |
| GET    | `/api/v1/properties/{id}/areas`          | List areas          |
| POST   | `/api/v1/properties/{id}/areas`          | Create area         |
| GET    | `/api/v1/areas/{id}`                     | Get area            |
| PATCH  | `/api/v1/areas/{id}`                     | Update area         |
| DELETE | `/api/v1/areas/{id}`                     | Delete area         |
| POST   | `/api/v1/areas/{id}/cameras`             | Link camera to area |
| DELETE | `/api/v1/areas/{id}/cameras/{camera_id}` | Unlink camera       |

### Frontend Components

#### New Components

- `HouseholdManagement.tsx` - CRUD for households, members, vehicles
- `PropertyManagement.tsx` - CRUD for properties and areas
- `AreaCameraLinking.tsx` - Visual interface for linking cameras to areas

#### Settings Integration

Add "HOUSEHOLD" tab to Settings (10th tab) containing:

- Household name/info
- Members list with CRUD
- Vehicles list with CRUD
- Properties with nested areas

---

## 2. Real-Time Updates

### WebSocket Events to Consume

| Event                   | UI Behavior                                         |
| ----------------------- | --------------------------------------------------- |
| `ALERT_DELETED`         | Remove from alerts list, update count badge         |
| `SCENE_CHANGE_DETECTED` | Toast notification, camera status indicator         |
| `WORKER_STARTED`        | Update pipeline health indicator (green)            |
| `WORKER_STOPPED`        | Update pipeline health indicator (yellow)           |
| `WORKER_ERROR`          | Toast notification, pipeline health indicator (red) |

### Prometheus Alert Integration

```
┌─────────────┐     ┌──────────────┐     ┌─────────┐     ┌───────────┐     ┌──────────┐
│ Prometheus  │────▶│ Alertmanager │────▶│ Backend │────▶│ WebSocket │────▶│ Frontend │
└─────────────┘     └──────────────┘     └─────────┘     └───────────┘     └──────────┘
                                              │
                                              ▼
                                         ┌─────────┐
                                         │   DB    │
                                         │ (history)│
                                         └─────────┘
```

#### Backend Webhook Receiver

```python
# backend/api/routes/alertmanager.py
@router.post("/api/v1/alertmanager/webhook")
async def receive_alertmanager_webhook(
    payload: AlertmanagerWebhook,
    broadcaster: EventBroadcaster = Depends(get_broadcaster),
    session: AsyncSession = Depends(get_db),
):
    """Receive alerts from Alertmanager and broadcast to frontend."""
    for alert in payload.alerts:
        # Store in DB for history
        db_alert = PrometheusAlert(
            fingerprint=alert.fingerprint,
            status=alert.status,  # "firing" or "resolved"
            labels=alert.labels,
            annotations=alert.annotations,
            starts_at=alert.startsAt,
            ends_at=alert.endsAt,
        )
        session.add(db_alert)

        # Broadcast to frontend
        await broadcaster.broadcast_prometheus_alert(alert)

    await session.commit()
    return {"status": "ok"}
```

#### Frontend Alert Handling

```typescript
// New WebSocket event handler
case 'PROMETHEUS_ALERT':
  const alert = payload as PrometheusAlert;

  // Update status indicator badge
  updateAlertCounts(alert);

  // Show toast for critical/warning
  if (alert.labels.severity === 'critical') {
    toast.error(alert.annotations.summary, {
      description: alert.annotations.description,
      duration: 10000,
    });
  } else if (alert.labels.severity === 'warning') {
    toast.warning(alert.annotations.summary, {
      duration: 5000,
    });
  }
  break;
```

#### UI Components

- **AlertBadge** - Header component showing: 🔴 2 critical, 🟡 5 warning
- **AlertDrawer** - Click badge to see active alerts list with details
- **Toast notifications** - Auto-dismiss based on severity

---

## 3. Settings Expansion

### Tab Mapping

| Tab               | New Settings                                                                                                                                                                 |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **PROCESSING**    | `detection_confidence_threshold`, `fast_path_confidence_threshold`, `batch_window_seconds`, `batch_idle_timeout_seconds`, `video_frame_interval_seconds`, `video_max_frames` |
| **RULES**         | `severity_low_max`, `severity_medium_max`, `severity_high_max`                                                                                                               |
| **NOTIFICATIONS** | `notification_enabled`, SMTP settings, webhook settings                                                                                                                      |
| **AMBIENT**       | `scene_change_enabled`, `scene_change_threshold`                                                                                                                             |
| **CALIBRATION**   | `reid_enabled`, `reid_similarity_threshold`, `reid_ttl_hours`                                                                                                                |
| **STORAGE**       | `retention_days`, `log_retention_days`, orphan cleanup settings, transcode cache settings                                                                                    |
| **ADMIN** (new)   | Feature toggles, system config, maintenance, dev tools                                                                                                                       |

### New ADMIN Tab

```
┌─────────────────────────────────────────────────────────────────┐
│ FEATURE TOGGLES                                                 │
│ ┌───────────────────┐ ┌───────────────────┐ ┌─────────────────┐│
│ │ Vision Extraction │ │ Re-ID Tracking    │ │ Scene Change    ││
│ │ [═══════ON══════] │ │ [═══════ON══════] │ │ [═══════ON════] ││
│ └───────────────────┘ └───────────────────┘ └─────────────────┘│
│ ┌───────────────────┐ ┌───────────────────┐ ┌─────────────────┐│
│ │ Clip Generation   │ │ Image Quality     │ │ Background Eval ││
│ │ [═══════ON══════] │ │ [═══════ON══════] │ │ [═══════ON════] ││
│ └───────────────────┘ └───────────────────┘ └─────────────────┘│
├─────────────────────────────────────────────────────────────────┤
│ SYSTEM CONFIG                                                   │
│                                                                 │
│ Rate Limiting                                                   │
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ Requests/min: [60    ]  Burst: [10   ]  Enabled: [✓]       ││
│ └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│ Queue Settings                                                  │
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ Max Size: [10000 ]  Backpressure: [80  ]%                  ││
│ └─────────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────┤
│ MAINTENANCE                                                     │
│                                                                 │
│ [🗑️ Run Orphan Cleanup]  [🧹 Clear Cache]  [📤 Flush Queues]   │
│                                                                 │
│ Last cleanup: 2 hours ago (removed 15 files, 2.3 GB)           │
├─────────────────────────────────────────────────────────────────┤
│ DEVELOPER TOOLS  ⚠️ Debug Mode Only                             │
│                                                                 │
│ [📷 Seed Cameras]  [📅 Seed Events]  [🗑️ Clear Test Data]      │
└─────────────────────────────────────────────────────────────────┘
```

### Backend API for Settings

```python
# backend/api/routes/settings.py

@router.get("/api/v1/settings")
async def get_settings() -> SettingsResponse:
    """Get current system settings (user-configurable subset)."""
    settings = get_settings()
    return SettingsResponse(
        detection=DetectionSettings(
            confidence_threshold=settings.detection_confidence_threshold,
            fast_path_threshold=settings.fast_path_confidence_threshold,
        ),
        batch=BatchSettings(
            window_seconds=settings.batch_window_seconds,
            idle_timeout_seconds=settings.batch_idle_timeout_seconds,
        ),
        # ... etc
    )

@router.patch("/api/v1/settings")
async def update_settings(updates: SettingsUpdate) -> SettingsResponse:
    """Update system settings (writes to runtime.env, triggers reload)."""
    # Validate and write to runtime.env
    # Signal settings reload
    pass
```

### Runtime Settings Reload

Settings changes write to `data/runtime.env` and trigger a reload without restart:

```python
# backend/core/config.py
def reload_settings():
    """Clear cached settings and reload from env files."""
    get_settings.cache_clear()
    return get_settings()
```

---

## 4. Implementation Phases

### Phase 1: Settings ADMIN Tab

1. Create `AdminSettings.tsx` component
2. Add feature toggles UI (read-only initially)
3. Add maintenance actions (orphan cleanup, cache clear)
4. Wire to existing backend APIs

### Phase 2: Settings API

1. Create `/api/v1/settings` GET/PATCH endpoints
2. Implement runtime.env writing
3. Add settings reload mechanism
4. Make feature toggles writable

### Phase 3: Real-Time Alerts

1. Create Alertmanager webhook receiver
2. Create `PrometheusAlert` database model
3. Add WebSocket event type for alerts
4. Create AlertBadge and AlertDrawer components

### Phase 4: WebSocket Event Consumers

1. Add handlers for ALERT_DELETED, SCENE_CHANGE_DETECTED
2. Add handlers for WORKER\_\* events
3. Update pipeline health indicators

### Phase 5: Hierarchy Models

1. Create Household, Property, Area models
2. Rename Zone → CameraZone
3. Add foreign keys and relationships
4. Create migration

### Phase 6: Hierarchy APIs

1. Create CRUD endpoints for hierarchy
2. Update Camera endpoints for property assignment
3. Create area-camera linking endpoints

### Phase 7: Hierarchy UI

1. Create HouseholdManagement component
2. Create PropertyManagement component
3. Add HOUSEHOLD tab to Settings
4. Update Camera settings for property/area assignment

---

## 5. Migration Strategy

### Database Migration Order

1. Create `households` table with default household
2. Add `household_id` to `household_members` (nullable initially)
3. Add `household_id` to `registered_vehicles` (nullable initially)
4. Migrate existing members/vehicles to default household
5. Make `household_id` non-nullable
6. Create `properties` table
7. Create `areas` table
8. Create `camera_areas` association table
9. Add `property_id` to `cameras` (nullable)
10. Rename `zones` → `camera_zones`

### Backward Compatibility

- All new foreign keys start nullable
- Default household/property created for existing data
- Existing APIs continue to work
- New hierarchy APIs are additive

---

## 6. Files to Create/Modify

### New Files

| Path                                                     | Purpose                    |
| -------------------------------------------------------- | -------------------------- |
| `backend/models/household_org.py`                        | Household org unit model   |
| `backend/models/property.py`                             | Property model             |
| `backend/models/area.py`                                 | Area model                 |
| `backend/api/routes/hierarchy.py`                        | Hierarchy CRUD APIs        |
| `backend/api/routes/alertmanager.py`                     | Alertmanager webhook       |
| `backend/api/routes/settings_api.py`                     | Settings GET/PATCH         |
| `backend/api/schemas/hierarchy.py`                       | Hierarchy Pydantic schemas |
| `backend/api/schemas/settings_api.py`                    | Settings schemas           |
| `frontend/src/components/settings/AdminSettings.tsx`     | Admin tab                  |
| `frontend/src/components/settings/HouseholdSettings.tsx` | Household tab              |
| `frontend/src/components/common/AlertBadge.tsx`          | Alert count badge          |
| `frontend/src/components/common/AlertDrawer.tsx`         | Active alerts list         |
| `frontend/src/hooks/useSettingsApi.ts`                   | Settings API hooks         |
| `frontend/src/hooks/useHierarchy.ts`                     | Hierarchy API hooks        |
| `frontend/src/hooks/usePrometheusAlerts.ts`              | Alert state management     |

### Modified Files

| Path                                                | Changes                                |
| --------------------------------------------------- | -------------------------------------- |
| `backend/models/household.py`                       | Add household_id FK                    |
| `backend/models/camera.py`                          | Add property_id FK, areas relationship |
| `backend/models/zone.py`                            | Rename to camera_zone.py               |
| `backend/core/websocket/event_schemas.py`           | Add PROMETHEUS_ALERT event             |
| `frontend/src/components/settings/SettingsPage.tsx` | Add ADMIN and HOUSEHOLD tabs           |
| `frontend/src/components/layout/Header.tsx`         | Add AlertBadge                         |
| `frontend/src/hooks/useWebSocket.ts`                | Handle new event types                 |

---

## 7. Success Criteria

- [ ] All 200+ config options accessible via Settings API
- [ ] Feature toggles controllable from UI
- [ ] Prometheus alerts visible in real-time
- [ ] Orphaned WebSocket events consumed
- [ ] Household → Property → Area hierarchy functional
- [ ] Cameras assignable to properties and areas
- [ ] No breaking changes to existing APIs
- [ ] All existing tests pass
- [ ] New functionality has >80% test coverage
