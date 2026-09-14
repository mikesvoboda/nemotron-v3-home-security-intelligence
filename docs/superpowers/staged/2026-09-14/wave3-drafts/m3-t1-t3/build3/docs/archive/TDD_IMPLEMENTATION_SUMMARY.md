# TDD Implementation Summary: Alert Rule New Condition Types

**Issue:** NEM-5084 - [TDD] Write tests for Phase 5: Alert Rule Condition Types
**Status:** RED Phase Complete (78 tests written, all failing as expected)
**Design Reference:** docs/plans/2026-02-01-platform-enhancement-strategy-design.md

## Tests Written

### Backend Service Tests (23 tests)

**File:** `backend/tests/unit/services/test_alert_engine_new_conditions.py`

Tests cover evaluation logic for 5 new condition types:

1. **Dwell Time Condition (4 tests)**

   - Triggers when threshold exceeded
   - No trigger when below threshold
   - Filter by specific zone IDs
   - Exclude household members

2. **Pose Type Condition (5 tests)**

   - Triggers on crouching
   - Triggers on lying_down (fall detection)
   - Triggers on climbing/arms_raised
   - No trigger for standing
   - Confidence threshold validation

3. **Action Type Condition (4 tests)**

   - Triggers on loitering
   - Triggers on suspicious behaviors
   - Multiple actions (OR logic)
   - Confidence threshold validation

4. **Threat Detection Condition (5 tests)**

   - Triggers on weapon detection
   - Gun = CRITICAL severity
   - Knife = HIGH severity
   - Severity filter
   - Confidence threshold validation

5. **Smoke/Fire Condition (3 tests)**

   - Basic trigger
   - Consecutive detections required
   - Confidence threshold validation

6. **Combined Conditions (2 tests)**
   - Multiple new conditions with AND logic
   - New conditions with existing conditions

### Schema Validation Tests (33 tests)

**File:** `backend/tests/unit/api/schemas/test_alert_new_conditions.py`

Tests cover Pydantic schema validation:

- Dwell time fields (5 tests)
- Pose type fields (6 tests)
- Action type fields (6 tests)
- Threat detection fields (6 tests)
- Smoke/fire fields (6 tests)
- Combined schema tests (3 tests)

### Model Field Tests (22 tests)

**File:** `backend/tests/unit/models/test_alert_rule_new_fields.py`

Tests cover SQLAlchemy model fields:

- Field existence (5 tests)
- Default values (7 tests)
- Field types and nullability (4 tests)
- Database column definitions (3 tests)
- Integration tests (2 tests)

### Frontend Component Tests (15 tests)

**File:** `frontend/src/components/alerts/__tests__/AlertRuleForm.newConditions.test.tsx`

Tests cover React form UI:

- Dwell time form fields (3 tests)
- Pose type selector (4 tests)
- Action type selector (4 tests)
- Threat detection fields (4 tests)
- Smoke/fire fields (4 tests)
- Combined conditions (2 tests)

## Expected Test Failures

All 78 tests are expected to fail with errors like:

- `TypeError: 'dwell_threshold_seconds' is an invalid keyword argument for AlertRule`
- `AssertionError: assert False - hasattr(..., 'pose_types')`

This is correct TDD RED phase behavior.

## Next Steps (GREEN Phase)

To make these tests pass, implement the following:

### 1. Database Migration

Add new columns to `alert_rules` table:

```sql
-- Dwell time
ALTER TABLE alert_rules ADD COLUMN dwell_threshold_seconds INTEGER NULL;
ALTER TABLE alert_rules ADD COLUMN exclude_household_members BOOLEAN DEFAULT FALSE;

-- Pose detection
ALTER TABLE alert_rules ADD COLUMN pose_types JSON NULL;
ALTER TABLE alert_rules ADD COLUMN pose_confidence_threshold FLOAT NULL;

-- Action recognition
ALTER TABLE alert_rules ADD COLUMN action_types JSON NULL;
ALTER TABLE alert_rules ADD COLUMN action_confidence_threshold FLOAT NULL;

-- Threat detection
ALTER TABLE alert_rules ADD COLUMN threat_detection_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE alert_rules ADD COLUMN threat_types JSON NULL;
ALTER TABLE alert_rules ADD COLUMN threat_min_severity VARCHAR(20) NULL;
ALTER TABLE alert_rules ADD COLUMN threat_confidence_threshold FLOAT NULL;

-- Smoke/fire detection
ALTER TABLE alert_rules ADD COLUMN smoke_fire_detection_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE alert_rules ADD COLUMN smoke_fire_consecutive_required INTEGER DEFAULT 2;
ALTER TABLE alert_rules ADD COLUMN smoke_fire_confidence_threshold FLOAT NULL;
```

### 2. Update Backend Models

**File:** `backend/models/alert.py`

Add mapped columns to `AlertRule` class (lines 249+):

```python
# Dwell time conditions
dwell_threshold_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
exclude_household_members: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

# Pose detection conditions
pose_types: Mapped[list | None] = mapped_column(JSON, nullable=True)
pose_confidence_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)

# Action recognition conditions
action_types: Mapped[list | None] = mapped_column(JSON, nullable=True)
action_confidence_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)

# Threat detection conditions
threat_detection_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
threat_types: Mapped[list | None] = mapped_column(JSON, nullable=True)
threat_min_severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
threat_confidence_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)

# Smoke/fire detection conditions
smoke_fire_detection_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
smoke_fire_consecutive_required: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
smoke_fire_confidence_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
```

### 3. Update API Schemas

**File:** `backend/api/schemas/alerts.py`

Add fields to `AlertRuleCreate` and `AlertRuleUpdate` (around line 300):

```python
# Dwell time
dwell_threshold_seconds: int | None = Field(None, ge=0)
exclude_household_members: bool = Field(False)

# Pose detection
pose_types: list[str] | None = Field(None)
pose_confidence_threshold: float | None = Field(None, ge=0.0, le=1.0)

# Action recognition
action_types: list[str] | None = Field(None)
action_confidence_threshold: float | None = Field(None, ge=0.0, le=1.0)

# Threat detection
threat_detection_enabled: bool = Field(False)
threat_types: list[str] | None = Field(None)
threat_min_severity: str | None = Field(None)
threat_confidence_threshold: float | None = Field(None, ge=0.0, le=1.0)

# Smoke/fire detection
smoke_fire_detection_enabled: bool = Field(False)
smoke_fire_consecutive_required: int = Field(2, ge=1)
smoke_fire_confidence_threshold: float | None = Field(None, ge=0.0, le=1.0)
```

Add validators for enum fields (pose_types, threat_min_severity).

### 4. Update Alert Engine Service

**File:** `backend/services/alert_engine.py`

In `_evaluate_rule()` method (around line 398), add new condition checks:

```python
# Check dwell time
if rule.dwell_threshold_seconds is not None:
    if not await self._check_dwell_time(rule, event, detections):
        return False, []
    matched_conditions.append(f"dwell_time >= {rule.dwell_threshold_seconds}s")

# Check pose types
if rule.pose_types:
    if not await self._check_pose_types(rule, event, detections):
        return False, []
    matched_conditions.append(f"pose_type in {rule.pose_types}")

# Check action types
if rule.action_types:
    if not await self._check_action_types(rule, event, detections):
        return False, []
    matched_conditions.append(f"action_type in {rule.action_types}")

# Check threat detection
if rule.threat_detection_enabled:
    if not await self._check_threats(rule, event, detections):
        return False, []
    matched_conditions.append("threat_detected")

# Check smoke/fire
if rule.smoke_fire_detection_enabled:
    if not await self._check_smoke_fire(rule, event, detections):
        return False, []
    matched_conditions.append("smoke_fire_detected")
```

Implement helper methods:

- `_check_dwell_time()` - Query DwellTimeRecord table
- `_check_pose_types()` - Query PoseResult table
- `_check_action_types()` - Query ActionResult table
- `_check_threats()` - Query ThreatDetection table
- `_check_smoke_fire()` - Query future SmokeFireResult table

### 5. Update Frontend Component

**File:** `frontend/src/components/alerts/AlertRuleForm.tsx`

Add form fields for new condition types:

- Number input for `dwell_threshold_seconds`
- Checkbox for `exclude_household_members`
- Multi-select for `pose_types`
- Slider for `pose_confidence_threshold`
- Multi-select for `action_types`
- Slider for `action_confidence_threshold`
- Checkbox for `threat_detection_enabled`
- Multi-select for `threat_types` (conditional)
- Dropdown for `threat_min_severity` (conditional)
- Slider for `threat_confidence_threshold` (conditional)
- Checkbox for `smoke_fire_detection_enabled`
- Number input for `smoke_fire_consecutive_required` (conditional)
- Slider for `smoke_fire_confidence_threshold` (conditional)

## Test Execution Commands

```bash
# Run all new condition tests
uv run pytest backend/tests/unit/services/test_alert_engine_new_conditions.py -v
uv run pytest backend/tests/unit/api/schemas/test_alert_new_conditions.py -v
uv run pytest backend/tests/unit/models/test_alert_rule_new_fields.py -v

# Run frontend tests
cd frontend && npm test -- AlertRuleForm.newConditions.test.tsx

# Full validation
./scripts/validate.sh
```

## Design References

- **Design Doc:** docs/plans/2026-02-01-platform-enhancement-strategy-design.md
- **Section:** New Alert Condition Types (lines 179-187)
- **Related Epic:** Foundation Infrastructure (Epic 0)
- **Dependent Epics:** AI Differentiation (Epic 2), Hidden Backend Exposure (Epic 1)

## Data Sources

| Condition Type  | Data Source Table | Key Fields                            |
| --------------- | ----------------- | ------------------------------------- |
| dwell_time      | DwellTimeRecord   | total_seconds, zone_id, track_id      |
| pose_type       | PoseResult        | pose_class, confidence, is_suspicious |
| action_type     | ActionResult      | action, confidence, is_suspicious     |
| threat_detected | ThreatDetection   | threat_type, confidence, severity     |
| smoke_fire      | SmokeFireResult   | detection_type, confidence (future)   |

## Success Criteria

When implementation is complete:

- All 78 tests pass (GREEN phase)
- Alert rules can be created with new condition types
- Alert engine evaluates new conditions correctly
- UI displays new condition fields
- Full validation passes: `./scripts/validate.sh`
