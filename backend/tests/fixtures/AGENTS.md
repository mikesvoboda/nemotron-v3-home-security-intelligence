# Test Fixtures

## Purpose

The `backend/tests/fixtures/` directory contains test fixture files used by automated tests. These include sample images for pipeline testing, the env file that renders the prod compose file for the services-render test, and the saved pre-upgrade database schema that the upgrade-path test restores.

## Directory Structure

```
backend/tests/fixtures/
├── AGENTS.md                 # This file
├── compose-render.env        # Minimal env that renders the prod compose file
├── schema_pre_upgrade.sql    # Saved pre-upgrade database shape, with rows
└── images/                   # Test images
    └── pipeline_test/        # Pipeline integration test images (14 files)
```

## Fixture Files

### `compose-render.env` (env file)

The minimum env that renders `docker-compose.prod.yml`: the file interpolates
exactly two variables with no fallback (`PODMAN_SOCKET`, `POSTGRES_PASSWORD`),
so two stubs make `config --services` work on any box. **Test evidence only —
not a deployment env**; the values are fake. It exists so the O1.3 Done-when
render (a plain `config --services`, no profile flag, lists `ai-vlm`) is
reproducible from the repo; see
`backend/tests/unit/core/test_compose_render_lists_ai_vlm.py`.

### `images/pipeline_test/` (14 JPEG images)

Contains test images for pipeline integration tests:

**Person Detection Images:**

- `test_person_house_front.jpg` - Person in front of house (110KB)
- `test_person_porch_1.jpg` - Person on porch (167KB)
- `test_person_porch_cat.jpg` - Person with cat on porch (151KB)
- `test_person_walking_dog.jpg` - Person walking a dog (792KB)

**Pet Detection Images:**

- `test_pet_cat_porch_tabby.jpg` - Tabby cat on porch (156KB)
- `test_pet_dog_grass_brown.jpg` - Brown dog on grass (412KB)
- `test_pet_dog_yard_labrador.jpg` - Labrador in yard (183KB)

**Vehicle Detection Images:**

- `test_vehicle_car_house.jpg` - Car near house (256KB)
- `test_vehicle_compact_building.jpg` - Compact car near building (345KB)
- `test_vehicle_sedan_road.jpg` - Sedan on road (97KB)

**Motion Detection Alarm Images:**

- `HMDAlarm_20260101-103424.jpg` - Human motion alarm (298KB)
- `HMDAlarm_20260101-171020.jpg` - Human motion alarm (151KB)
- `MDAlarm_20250805-220848.jpg` - Motion detection alarm (124KB)
- `MDAlarm_20260101-143519.jpg` - Motion detection alarm (333KB)

### `schema_pre_upgrade.sql` (saved pre-upgrade database, with rows)

The database shape `main` leaves behind **before** B3.3's recorded upgrades run, as a loadable
SQL script: the alert tables with plain `JSON` columns (the shape NEM-5051 converts), the three
vector tables with no `model_id` column (F11's provenance addition), the two tables R8 S4 retired,
and `cameras` / `events` / `detections` / `user_calibration` / `event_feedback` **without** the 12
January-2026 model columns upgrade 0005 adds — plus rows in each, because an upgrade that quietly
lost data passes a schema-only check.

- Restored by `backend/tests/integration/test_schema_upgrade_path.py` into a fresh database per
  test (that test loads it with psycopg2, not through the runner's own lexer, so the lexer cannot
  grade its own homework).
- It is a **file** rather than inline DDL for the same reason as the other fixtures here: it is
  diffable, and reproducible outside pytest with `psql -d <empty-db> -f schema_pre_upgrade.sql`.
- The 0005 tables are **minimal on purpose** — id, a couple of columns, rows. Spelling today's
  full column list would recreate the bug 0005 fixes: a database that already has the columns
  proves nothing. Their id TYPES do match the models (`cameras.id` TEXT per `String`, the rest
  INTEGER per `Integer`) because the boot test's `create_all` builds the other tables against
  these, and a type mismatch surfaces as a confusing FK error instead of a finding. No FKs are
  declared here at all: `create_all` does not add constraints to an existing table, so an FK in
  this file would be testing the fixture rather than the upgrade path.
- `vector(...)` columns are deliberately omitted: the sandbox Postgres has pg_trgm but not
  pgvector, and no upgrade under test touches a vector column's type. If an upgrade ever does,
  this fixture cannot express that case and needs a pgvector-capable database.
- Do not "fix" it by adding today's columns — its whole value is being wrong in the old way. That
  includes the five 0005 tables: adding `events.llm_prompt` here makes upgrade 0005 a no-op and
  the test that asserts it ran go red, which is the correct reading of that red.

## Usage in Tests

These fixtures are used in:

- **E2E tests** (`backend/tests/e2e/test_pipeline_integration.py`)
- **Integration tests** for detector client
- **Unit tests** for file watcher and image validation

**Example Usage:**

```python
import pytest
from pathlib import Path


@pytest.fixture
def test_image_path():
    return (
        Path(__file__).parent / "fixtures" / "images" / "pipeline_test" / "test_person_porch_1.jpg"
    )


async def test_detection(test_image_path):
    # Use fixture image for testing
    result = await detector.detect_objects(str(test_image_path), "test_camera", session)
    assert len(result) > 0
```

## Image Specifications

All test images are:

- JPEG format
- Real camera captures from Foscam cameras
- Various resolutions (typical: 1920x1080 or 2560x1440)
- File sizes ranging from ~100KB to ~800KB

## Adding New Fixtures

When adding new test fixtures:

1. Place files in appropriate subdirectory
2. Use descriptive filenames
3. Document the fixture in this file
4. Ensure files are committed to git (not ignored)

## Related Documentation

- `/backend/tests/AGENTS.md` - Test infrastructure overview
- `/backend/tests/e2e/AGENTS.md` - E2E test documentation
- `/backend/tests/conftest.py` - Shared pytest fixtures
