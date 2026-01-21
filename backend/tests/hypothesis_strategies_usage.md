# Domain-Specific Hypothesis Strategies Usage Guide

This guide demonstrates how to use the domain-specific Hypothesis strategies in `backend/tests/hypothesis_strategies.py` for property-based testing.

## Quick Start

```python
from hypothesis import given
from backend.tests.hypothesis_strategies import (
    valid_camera_id,
    valid_detection_bbox,
    valid_risk_score,
)

@given(camera_id=valid_camera_id(), risk_score=valid_risk_score())
def test_event_creation(camera_id, risk_score):
    """Test event creation with generated valid data."""
    event = Event(camera_id=camera_id, risk_score=risk_score)
    assert 0 <= event.risk_score <= 100
    assert event.camera_id.islower()
```

## Available Strategies

### Basic Domain Types

```python
from backend.tests.hypothesis_strategies import (
    valid_camera_id,          # Camera IDs: "front_door", "driveway_cam"
    valid_camera_name,        # Display names: "Front Door", "Driveway (Main)"
    valid_camera_folder_path, # Folder paths: "/export/foscam/Front Door"
    valid_uuid4,              # Standard UUID4 strings
    valid_uuid_hex,           # UUID hex (for batch IDs)
    valid_risk_score,         # Risk scores: 0-100
    valid_confidence,         # Confidence: 0.0-1.0
    valid_detection_label,    # Object types: "person", "vehicle", etc.
    valid_timezone,           # IANA timezones: "UTC", "America/New_York"
)
```

### Bounding Box Strategies

```python
from backend.tests.hypothesis_strategies import (
    valid_detection_bbox,    # Pixel coordinates {x, y, width, height}
    valid_normalized_bbox,   # Normalized [0-1] coordinates
)

@given(bbox=valid_detection_bbox())
def test_bbox_validation(bbox):
    """Test bounding box is within frame bounds."""
    assert bbox["x"] + bbox["width"] <= 1920
    assert bbox["y"] + bbox["height"] <= 1080
    assert bbox["width"] >= 1
    assert bbox["height"] >= 1
```

### Timestamp Strategies

```python
from backend.tests.hypothesis_strategies import (
    valid_utc_timestamp,
    valid_timestamp_range,
)

@given(timestamp_range=valid_timestamp_range())
def test_event_duration(timestamp_range):
    """Test event duration calculation."""
    start, end = timestamp_range
    assert start < end
    assert start.tzinfo == UTC
    assert end.tzinfo == UTC
```

### Composite Model Strategies

Generate complete model dictionaries ready for instantiation:

```python
from backend.tests.hypothesis_strategies import (
    camera_dict_strategy,
    detection_dict_strategy,
    event_dict_strategy,
    zone_dict_strategy,
)

@given(camera_data=camera_dict_strategy())
def test_camera_creation(camera_data):
    """Test camera creation with all fields."""
    camera = Camera(**camera_data)
    assert camera.id == camera_data["id"]
    assert camera.status in ["online", "offline", "error", "unknown"]

@given(detection_data=detection_dict_strategy())
def test_detection_bbox_consistency(detection_data):
    """Test detection bbox coordinates are consistent."""
    detection = Detection(**detection_data)
    assert detection.bbox_x >= 0
    assert detection.bbox_y >= 0
    assert detection.confidence >= 0.0
    assert detection.confidence <= 1.0
```

### Edge Case Strategies

Test boundary conditions and extreme values:

```python
from backend.tests.hypothesis_strategies import (
    edge_case_risk_scores,    # Severity boundaries: 0, 25, 50, 75, 100
    edge_case_confidence,     # Confidence boundaries: 0.0, 0.5, 1.0
    edge_case_bbox,           # Frame edges, minimum size
    edge_case_timestamp,      # Year boundaries: 2000, 2024, 2038
)

@given(risk_score=edge_case_risk_scores())
def test_severity_boundaries(risk_score):
    """Test severity mapping at boundaries."""
    from backend.services.severity import get_severity_service

    service = get_severity_service()
    severity = service.risk_score_to_severity(risk_score)

    # Test boundary transitions
    if risk_score == 25:
        assert severity in [Severity.LOW, Severity.MEDIUM]
    elif risk_score == 50:
        assert severity in [Severity.MEDIUM, Severity.HIGH]
```

### Example-Based Strategies

Generate realistic examples for common scenarios:

```python
from backend.tests.hypothesis_strategies import (
    example_person_detection,    # Realistic person detection
    example_vehicle_detection,   # Realistic vehicle detection
    example_high_risk_event,     # Critical severity event
)

@given(detection=example_person_detection())
def test_person_detection_confidence(detection):
    """Test person detections have high confidence."""
    assert detection["object_type"] == "person"
    assert detection["confidence"] >= 0.7
    # Verify realistic proportions (taller than wide)
    assert detection["bbox_height"] > detection["bbox_width"]
```

## Hypothesis Profiles

Use different profiles for different testing scenarios:

```bash
# Fast profile: 10 examples, quick smoke tests
pytest tests/ --hypothesis-profile=fast

# Default profile: 100 examples, local development (default)
pytest tests/

# CI profile: 200 examples, thorough testing
pytest tests/ --hypothesis-profile=ci

# Debug profile: 10 examples, verbose output
pytest tests/ --hypothesis-profile=debug
```

## Advanced Usage

### Combining Strategies

```python
from hypothesis import given, strategies as st
from backend.tests.hypothesis_strategies import (
    valid_camera_id,
    detection_dict_strategy,
)

@given(
    camera_id=valid_camera_id(),
    detections=st.lists(
        detection_dict_strategy(),
        min_size=1,
        max_size=10
    )
)
def test_event_from_detections(camera_id, detections):
    """Test event creation from multiple detections."""
    # Ensure all detections are for the same camera
    for det in detections:
        det["camera_id"] = camera_id

    event = create_event_from_detections(detections)
    assert event.camera_id == camera_id
    assert len(event.detections) == len(detections)
```

### Filtering Generated Data

```python
from hypothesis import given, assume
from backend.tests.hypothesis_strategies import valid_risk_score

@given(risk_score=valid_risk_score())
def test_high_risk_only(risk_score):
    """Test high-risk event handling."""
    # Only test high-risk scores
    assume(risk_score >= 51)

    event = Event(risk_score=risk_score)
    assert event.get_severity() in [Severity.HIGH, Severity.CRITICAL]
```

### Custom Strategies

Build custom strategies on top of domain strategies:

```python
from hypothesis import strategies as st
from backend.tests.hypothesis_strategies import (
    valid_camera_id,
    valid_utc_timestamp,
)

@st.composite
def camera_with_recent_activity(draw):
    """Generate camera with recent detection activity."""
    from datetime import timedelta

    camera_id = draw(valid_camera_id())
    now = draw(valid_utc_timestamp())
    last_seen = now - timedelta(minutes=draw(st.integers(1, 60)))

    return {
        "id": camera_id,
        "status": "online",
        "last_seen_at": last_seen,
    }

@given(camera_data=camera_with_recent_activity())
def test_active_camera(camera_data):
    """Test cameras with recent activity."""
    assert camera_data["status"] == "online"
    assert camera_data["last_seen_at"] is not None
```

## Testing Tips

1. **Start Simple**: Begin with basic strategies and add complexity as needed.

2. **Use Edge Cases**: Combine edge case strategies with regular strategies:

   ```python
   @given(risk_score=st.one_of(valid_risk_score(), edge_case_risk_scores()))
   def test_all_risk_scores(risk_score):
       # Tests both regular and boundary values
       pass
   ```

3. **Shrinking**: Hypothesis automatically shrinks failing examples to minimal cases:

   ```python
   @given(camera_id=valid_camera_id())
   def test_camera_id_length(camera_id):
       # If this fails, Hypothesis will find the shortest failing camera_id
       assert len(camera_id) <= 50
   ```

4. **Reproduce Failures**: Use `@example()` to add specific test cases:

   ```python
   from hypothesis import given, example

   @given(risk_score=valid_risk_score())
   @example(risk_score=0)   # Always test edge case
   @example(risk_score=100) # Always test edge case
   def test_risk_score(risk_score):
       assert 0 <= risk_score <= 100
   ```

5. **Profile Selection**: Choose the right profile for your needs:
   - Development: `fast` or `default`
   - Pre-commit: `default`
   - CI: `ci`
   - Debugging: `debug`

## Common Patterns

### Testing Model Constraints

```python
@given(event_data=event_dict_strategy())
def test_event_constraints(event_data):
    """Test Event model enforces constraints."""
    event = Event(**event_data)

    # Risk score range
    if event.risk_score is not None:
        assert 0 <= event.risk_score <= 100

    # Risk level consistency
    if event.risk_score and event.risk_level:
        if event.risk_score <= 25:
            assert event.risk_level == "low"
        # ... more assertions
```

### Testing Service Logic

```python
@given(
    detections=st.lists(detection_dict_strategy(), min_size=1, max_size=5),
    camera_id=valid_camera_id()
)
def test_batch_aggregation(detections, camera_id):
    """Test batch aggregator groups detections correctly."""
    # Ensure all detections are for same camera
    for det in detections:
        det["camera_id"] = camera_id

    batch = BatchAggregator.aggregate(detections)
    assert batch.camera_id == camera_id
    assert len(batch.detections) == len(detections)
```

### Testing API Schemas

```python
@given(camera_data=camera_dict_strategy())
def test_camera_schema_validation(camera_data):
    """Test CameraSchema validates correctly."""
    schema = CameraSchema(**camera_data)
    assert schema.id == camera_data["id"]
    assert schema.status in ["online", "offline", "error", "unknown"]
```

## See Also

- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [Property-Based Testing Guide](https://hypothesis.works/articles/what-is-property-based-testing/)
- `backend/tests/conftest.py` - Hypothesis profile configuration
- `backend/tests/unit/test_hypothesis_strategies.py` - Strategy validation tests
