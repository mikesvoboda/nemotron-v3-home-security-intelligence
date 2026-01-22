# Full Platform Seed Script Design

**Date:** 2026-01-21
**Goal:** Expand `scripts/seed-events.py` to exercise all 47 database tables with realistic, production-like data.

## Overview

The current seed script exercises 16 tables (34%) focused on the core event pipeline. This design adds 25 new seed functions to cover the remaining 31 tables across 6 feature areas:

1. Foundation (properties, households, notifications)
2. Zones & Spatial (camera zones, areas, calibrations)
3. AI Enrichment (demographics, poses, actions, threats, re-id)
4. Jobs & Exports (background processing, video exports)
5. Prompt Experimentation (A/B testing, versioning)
6. Monitoring & Feedback (zone anomalies, user feedback, prometheus alerts)

## Dependency Order

```
Level 1 (no deps):     cameras ✅, properties, households, prompt_configs
Level 2 (needs L1):    areas, household_members, camera_zones, notification_preferences, prompt_versions
Level 3 (needs L2):    camera_areas, zone_household_configs, camera_calibrations, camera_notification_settings
Level 4 (needs events): demographics_results, pose_results, action_results, threat_detections,
                        reid_embeddings, person_embeddings, scene_changes, event_feedback
Level 5 (background):  jobs → job_attempts → job_transitions → job_logs, export_jobs
Level 6 (monitoring):  prometheus_alerts, zone_activity_baselines, zone_anomalies
```

## CLI Interface

```bash
# Full platform exercise - DEFAULT (all 47 tables)
uv run python scripts/seed-events.py --images 100

# Minimal - just pipeline data (old behavior)
uv run python scripts/seed-events.py --images 100 --minimal

# Config only - setup without heavy AI data
uv run python scripts/seed-events.py --config-only
```

---

## Layer 1: Foundation (Properties, Households, Notifications)

### seed_properties

```python
async def seed_properties(num_properties: int = 2) -> list[str]:
    """Create properties (e.g., 'Main Residence', 'Vacation Home').
    Links cameras to properties for multi-site deployments."""
```

**Fields:**

- `id`, `name`, `address`, `timezone`, `created_at`

**Sample data:**

- "Main Residence" - 123 Oak Street
- "Lake House" - 456 Lakeview Drive

### seed_households

```python
async def seed_households(num_households: int = 3) -> list[str]:
    """Create households within properties (e.g., 'Smith Family').
    Each property gets 1-2 households."""
```

**Fields:**

- `id`, `property_id`, `name`, `created_at`

**Sample data:**

- "Smith Family" → Main Residence
- "Guest House" → Main Residence
- "Johnson Family" → Lake House

### seed_household_members

```python
async def seed_household_members(num_members: int = 8) -> list[str]:
    """Create family members with names, roles (adult/child/pet).
    Generates placeholder face embeddings for person_embeddings table."""
```

**Fields:**

- `id`, `household_id`, `name`, `role`, `created_at`

**Roles:** `owner`, `spouse`, `child`, `relative`, `caregiver`, `pet`

**Sample data:**

- John Smith (owner), Jane Smith (spouse), Tommy Smith (child), Max (pet)

### seed_registered_vehicles

```python
async def seed_registered_vehicles(num_vehicles: int = 5) -> list[str]:
    """Create known vehicles (plate, make, model, color).
    Links to households for 'family car arriving' scenarios."""
```

**Fields:**

- `id`, `household_id`, `plate_number`, `make`, `model`, `color`, `year`, `created_at`

**Sample data:**

- ABC-1234, Toyota Camry, Silver, 2022 → Smith Family

### seed_notification_preferences

```python
async def seed_notification_preferences() -> int:
    """Create notification prefs for each household member.
    Configures push settings, email digests, severity thresholds."""
```

**Fields:**

- `id`, `household_member_id`, `push_enabled`, `email_enabled`, `min_severity`, `sound`, `created_at`

### seed_quiet_hours

```python
async def seed_quiet_hours() -> int:
    """Create quiet hours periods (e.g., 11pm-7am weekdays).
    Links to notification_preferences."""
```

**Fields:**

- `id`, `notification_preference_id`, `start_time`, `end_time`, `days_of_week`, `enabled`

**Sample data:**

- 23:00-07:00, Mon-Fri (suppress non-critical overnight)
- 14:00-15:00, Sat-Sun (nap time)

### seed_camera_notification_settings

```python
async def seed_camera_notification_settings() -> int:
    """Per-camera notification overrides.
    E.g., 'Backyard camera' always notifies, 'Garage' only high-risk."""
```

**Fields:**

- `id`, `camera_id`, `notification_preference_id`, `override_enabled`, `min_severity_override`

---

## Layer 2: Zones & Spatial Configuration

### seed_camera_zones

```python
async def seed_camera_zones(zones_per_camera: int = 3) -> list[str]:
    """Create detection zones for each camera.
    Types: 'driveway', 'entrance', 'perimeter', 'pool', 'garage'.
    Each zone has polygon coordinates (normalized 0-1 for any resolution)."""
```

**Fields:**

- `id`, `camera_id`, `name`, `zone_type`, `polygon_coords`, `sensitivity`, `detection_classes`, `enabled`

**Realistic polygons:**

- Driveway: `[[0.2,0.9], [0.4,0.5], [0.6,0.5], [0.8,0.9]]` (trapezoid receding)
- Entrance: `[[0.3,0.3], [0.7,0.3], [0.7,0.7], [0.3,0.7]]` (rectangle around door)
- Perimeter: `[[0.0,0.5], [0.1,0.5], [0.1,1.0], [0.0,1.0]]` (edge strip)

### seed_areas

```python
async def seed_areas() -> list[str]:
    """Create logical areas within properties.
    E.g., 'Front Yard', 'Backyard', 'Side Gate', 'Interior'."""
```

**Fields:**

- `id`, `property_id`, `name`, `description`, `created_at`

### seed_camera_areas

```python
async def seed_camera_areas() -> int:
    """Link cameras to areas (many-to-many).
    A camera can cover multiple areas, an area can have multiple cameras."""
```

**Fields:**

- `id`, `camera_id`, `area_id`

### seed_camera_calibrations

```python
async def seed_camera_calibrations() -> int:
    """Store camera calibration data for distance/size estimation.
    Includes: focal length, mounting height, tilt angle, reference measurements."""
```

**Fields:**

- `id`, `camera_id`, `focal_length_mm`, `mounting_height_m`, `tilt_angle_deg`, `reference_object_size`, `pixels_per_meter`, `calibrated_at`

### seed_user_calibration

```python
async def seed_user_calibration() -> int:
    """User-provided calibration points.
    E.g., 'This line is my fence, it's 50ft long' for scale reference."""
```

**Fields:**

- `id`, `camera_id`, `point1`, `point2`, `real_world_distance_m`, `label`, `created_at`

### seed_zone_household_configs

```python
async def seed_zone_household_configs() -> int:
    """Per-zone rules for household recognition.
    E.g., 'In driveway zone, suppress alerts for known family members'."""
```

**Fields:**

- `id`, `zone_id`, `household_id`, `suppress_known_members`, `suppress_known_vehicles`, `created_at`

---

## Layer 3: AI Enrichment Results

### seed_demographics_results

```python
async def seed_demographics_results() -> int:
    """Create demographic analysis for person detections.
    Only for detections where class='person'."""
```

**Fields:**

- `id`, `detection_id`, `age_min`, `age_max`, `gender`, `gender_confidence`, `created_at`

**Distribution:**

- Age ranges: 0-12 (10%), 13-25 (25%), 26-45 (35%), 46-65 (20%), 65+ (10%)
- Gender: male (48%), female (48%), unknown (4%)

### seed_pose_results

```python
async def seed_pose_results() -> int:
    """Create pose keypoint data for person detections.
    17-point skeleton (COCO format)."""
```

**Fields:**

- `id`, `detection_id`, `keypoints` (JSON array of 17 points), `pose_class`, `confidence`, `created_at`

**Pose classes:** `standing`, `walking`, `running`, `sitting`, `crouching`, `fallen`

### seed_action_results

```python
async def seed_action_results() -> int:
    """Create action recognition results."""
```

**Fields:**

- `id`, `detection_id`, `action`, `confidence`, `duration_ms`, `created_at`

**Actions:** `walking`, `running`, `loitering`, `climbing`, `carrying_object`, `using_phone`, `looking_around`, `approaching_door`

### seed_threat_detections

```python
async def seed_threat_detections() -> int:
    """Create threat classification results."""
```

**Fields:**

- `id`, `detection_id`, `threat_type`, `severity`, `confidence`, `created_at`

**Threat types:** `weapon_visible`, `aggressive_posture`, `face_covered`, `unusual_clothing`, `prowling_behavior`

### seed_scene_changes

```python
async def seed_scene_changes() -> int:
    """Create scene change detection records."""
```

**Fields:**

- `id`, `camera_id`, `event_id`, `change_type`, `before_embedding`, `after_embedding`, `similarity_score`, `detected_at`

**Change types:** `object_left_behind`, `object_removed`, `door_opened`, `light_changed`, `camera_tampered`

### seed_reid_embeddings

```python
async def seed_reid_embeddings() -> int:
    """Create re-identification embeddings for tracking across cameras.
    512-dim vectors for person/vehicle appearance matching."""
```

**Fields:**

- `id`, `detection_id`, `embedding` (512-dim float array), `entity_id`, `created_at`

### seed_person_embeddings

```python
async def seed_person_embeddings() -> int:
    """Create face embeddings for known household members.
    Links to household_members for 'known person' recognition."""
```

**Fields:**

- `id`, `household_member_id`, `embedding` (512-dim float array), `quality_score`, `source_image_path`, `created_at`

---

## Layer 4: Jobs & Exports

### seed_jobs

```python
async def seed_jobs(num_jobs: int = 20) -> list[str]:
    """Create background job records with realistic state distribution."""
```

**Fields:**

- `id`, `job_type`, `status`, `payload`, `result`, `error`, `attempts`, `created_at`, `started_at`, `finished_at`

**Job types:** `video_export`, `report_generation`, `batch_analysis`, `model_inference`, `cleanup`, `notification_digest`

**State distribution:** 70% completed, 15% failed, 10% running, 5% pending

### seed_job_attempts

```python
async def seed_job_attempts(attempts_per_job: int = 2) -> int:
    """Create job attempt history showing retry behavior."""
```

**Fields:**

- `id`, `job_id`, `attempt_number`, `status`, `worker_id`, `started_at`, `finished_at`, `error`

### seed_job_transitions

```python
async def seed_job_transitions() -> int:
    """Create job state machine transitions."""
```

**Fields:**

- `id`, `job_id`, `from_status`, `to_status`, `trigger`, `triggered_by`, `transitioned_at`

**Triggers:** `scheduler`, `worker`, `timeout`, `manual_retry`, `cancel`

### seed_job_logs

```python
async def seed_job_logs(logs_per_job: int = 5) -> int:
    """Create structured job execution logs."""
```

**Fields:**

- `id`, `job_id`, `level`, `message`, `context`, `logged_at`

**Sample messages:**

- INFO: "Starting export for camera front_door, 2h timerange"
- DEBUG: "Processed 50/100 frames"
- ERROR: "GPU OOM at frame 73, retrying with smaller batch"

### seed_export_jobs

```python
async def seed_export_jobs(num_exports: int = 10) -> list[str]:
    """Create video/data export job records."""
```

**Fields:**

- `id`, `job_id`, `export_type`, `camera_ids`, `time_range_start`, `time_range_end`, `format`, `file_size_bytes`, `download_url`, `expires_at`

**Export types:** `video_clip`, `event_report`, `csv_export`, `timelapse`

---

## Layer 5: Prompt Experimentation & Feedback

### seed_prompt_configs

```python
async def seed_prompt_configs(num_configs: int = 3) -> list[str]:
    """Create prompt configuration templates."""
```

**Fields:**

- `id`, `name`, `description`, `system_prompt`, `user_template`, `model`, `temperature`, `max_tokens`, `status`, `created_at`

**Configs:**

- `risk_analysis_v1` - Main threat assessment prompt
- `scene_description` - Natural language scene summary
- `threat_assessment` - Specialized threat-focused analysis

### seed_prompt_versions

```python
async def seed_prompt_versions(versions_per_config: int = 4) -> int:
    """Create version history for each prompt config."""
```

**Fields:**

- `id`, `prompt_config_id`, `version`, `system_prompt`, `user_template`, `changelog`, `is_current`, `created_at`, `created_by`

### seed_experiment_results

```python
async def seed_experiment_results(num_results: int = 50) -> int:
    """Create A/B test results comparing prompt versions."""
```

**Fields:**

- `id`, `prompt_version_id`, `event_id`, `latency_ms`, `token_count`, `user_rating`, `accuracy_score`, `created_at`

### seed_event_feedback

```python
async def seed_event_feedback(feedback_per_event: float = 0.3) -> int:
    """Create user feedback on ~30% of events."""
```

**Fields:**

- `id`, `event_id`, `feedback_type`, `feedback_text`, `corrected_risk_level`, `corrected_labels`, `created_by`, `created_at`

**Feedback types:** `correct`, `incorrect`, `partially_correct`

**Distribution:** 70% correct, 20% partially_correct, 10% incorrect

### seed_prometheus_alerts

```python
async def seed_prometheus_alerts(num_alerts: int = 25) -> int:
    """Create ingested Prometheus alert records."""
```

**Fields:**

- `id`, `alert_name`, `status`, `severity`, `labels`, `annotations`, `started_at`, `resolved_at`, `created_at`

**Alert names:** `HighCPU`, `GPUMemoryPressure`, `DiskSpaceLow`, `AIServiceUnhealthy`, `HighLatency`, `ErrorRateSpike`

---

## Layer 6: Zone Monitoring

### seed_zone_activity_baselines

```python
async def seed_zone_activity_baselines() -> int:
    """Create per-zone activity baselines.
    Tracks typical detection counts per zone per hour/day."""
```

**Fields:**

- `id`, `zone_id`, `hour_of_day`, `day_of_week`, `avg_detections`, `std_dev`, `sample_count`, `updated_at`

### seed_zone_anomalies

```python
async def seed_zone_anomalies(num_anomalies: int = 15) -> int:
    """Create detected anomaly records."""
```

**Fields:**

- `id`, `zone_id`, `anomaly_type`, `baseline_value`, `actual_value`, `deviation_score`, `event_id`, `detected_at`

**Anomaly types:** `activity_spike`, `activity_drop`, `new_pattern`, `schedule_violation`

---

## Implementation Plan

### Phase 1: Foundation Layer

1. Implement `seed_properties`, `seed_households`, `seed_household_members`
2. Implement `seed_registered_vehicles`
3. Implement `seed_notification_preferences`, `seed_quiet_hours`, `seed_camera_notification_settings`

### Phase 2: Zones & Spatial

4. Implement `seed_camera_zones` with realistic polygon generation
5. Implement `seed_areas`, `seed_camera_areas`
6. Implement `seed_camera_calibrations`, `seed_user_calibration`
7. Implement `seed_zone_household_configs`

### Phase 3: AI Enrichment

8. Implement `seed_demographics_results`, `seed_pose_results`
9. Implement `seed_action_results`, `seed_threat_detections`
10. Implement `seed_scene_changes`, `seed_reid_embeddings`, `seed_person_embeddings`

### Phase 4: Jobs & Exports

11. Implement `seed_jobs`, `seed_job_attempts`, `seed_job_transitions`, `seed_job_logs`
12. Implement `seed_export_jobs`

### Phase 5: Experimentation & Feedback

13. Implement `seed_prompt_configs`, `seed_prompt_versions`, `seed_experiment_results`
14. Implement `seed_event_feedback`, `seed_prometheus_alerts`

### Phase 6: Zone Monitoring

15. Implement `seed_zone_activity_baselines`, `seed_zone_anomalies`

### Phase 7: Integration

16. Update CLI arguments (`--minimal`, `--config-only`)
17. Update main() to call new functions in dependency order
18. Update verification to report all 47 tables
19. Test full seeding, verify all tables populated

---

## Success Criteria

- [ ] All 47 tables have non-zero row counts after `--images 100` (default full mode)
- [ ] `--minimal` produces same output as current script (backward compatible)
- [ ] `--config-only` seeds configuration without requiring images
- [ ] Data passes foreign key constraints (proper relationships)
- [ ] Realistic data distributions (timestamps, states, values)
- [ ] Script completes in <5 minutes for 100 images
