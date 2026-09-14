# Decision: Entity-Detection Referential Integrity

**Date:** 2026-01-28
**Status:** Decided
**Related Issues:** NEM-1880, NEM-2210, NEM-2431, NEM-2670

---

## Context

The Home Security Intelligence system tracks unique individuals and objects (entities) across multiple cameras using re-identification techniques. Each entity can be associated with a "primary detection" - the best or most representative detection image for that entity.

### The Problem

The `entities` table needs to reference records in the `detections` table via a `primary_detection_id` column. However, the `detections` table uses PostgreSQL table partitioning by `detected_at` timestamp for performance optimization, which creates a composite primary key `(id, detected_at)`.

**PostgreSQL Limitation:** Foreign key constraints cannot reference only part of a composite primary key on partitioned tables. This means we cannot create a standard FK constraint from `entities.primary_detection_id` to `detections.id`.

### Current Schema

```sql
-- Detections table (partitioned)
CREATE TABLE detections (
    id SERIAL,
    detected_at TIMESTAMPTZ NOT NULL,
    camera_id VARCHAR NOT NULL,
    -- ... other columns
    PRIMARY KEY (id, detected_at)  -- Composite PK required for partitioning
) PARTITION BY RANGE (detected_at);

-- Entities table
CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(20) NOT NULL,
    primary_detection_id INTEGER,  -- Cannot have FK to detections.id alone
    -- ... other columns
);
```

---

## Decision Summary

**Enforce referential integrity at the application level rather than the database level.**

The `primary_detection_id` column will NOT have a foreign key constraint. Instead:

1. An index is created on `primary_detection_id` for query performance
2. Application-level validation methods enforce integrity before writes
3. The relationship is defined as `viewonly=True` in SQLAlchemy

---

## Options Evaluated

### Option 1: Database-Level FK (Not Possible)

| Pros                            | Cons                                                                 |
| ------------------------------- | -------------------------------------------------------------------- |
| Automatic integrity enforcement | **Not supported** - PG partitioned tables require full composite key |
| -                               | Would require restructuring entire detection storage                 |

### Option 2: Application-Level Validation (Selected)

| Pros                                               | Cons                                               |
| -------------------------------------------------- | -------------------------------------------------- |
| Works with partitioned tables                      | Requires discipline to use validation methods      |
| No schema changes needed                           | Orphaned references possible if validation skipped |
| Explicit validation provides better error messages | Slightly more code                                 |
| Allows soft-delete patterns                        | -                                                  |

### Option 3: Denormalize into Entities Table

| Pros                      | Cons             |
| ------------------------- | ---------------- |
| No cross-table references | Data duplication |
| Simple queries            | Storage overhead |
| -                         | Sync complexity  |

### Option 4: Junction Table with Full Composite Key

| Pros                          | Cons                                       |
| ----------------------------- | ------------------------------------------ |
| Could enable FK with full key | Requires storing `detected_at` in entities |
| -                             | More complex queries                       |
| -                             | Breaks existing API contracts              |

---

## Rationale

We selected **Option 2 (Application-Level Validation)** for the following reasons:

### 1. Partitioning Benefits Outweigh FK Enforcement

The `detections` table is partitioned by `detected_at` for:

- **Efficient pruning:** Queries on recent data only scan relevant partitions
- **Maintenance:** Old partitions can be dropped without vacuuming
- **Performance:** 10-100x faster for time-range queries

Removing partitioning to enable FK would significantly degrade performance for the core detection workflow.

### 2. Primary Detection is Optional and Display-Only

The `primary_detection_id` is used for:

- Displaying a representative thumbnail for an entity
- Quick access to the "best" detection

It is NOT used for:

- Critical business logic
- Financial transactions
- Data that requires ACID guarantees

If a referenced detection is deleted (e.g., retention policy), the entity remains valid with a NULL reference.

### 3. Validation Methods Provide Better UX

Application-level validation returns meaningful errors:

```python
is_valid, error = await entity.validate_primary_detection_async(session)
if not is_valid:
    raise ValueError(error)
# Error: "Detection with id=123 does not exist. Cannot set as primary_detection_id for Entity."
```

Database FK violations would only return generic constraint violation errors.

### 4. Follows Existing Patterns

The codebase already uses application-level validation for other constraints (e.g., `enrichment_data` schema validation in the Detection model).

---

## Implementation

### Database Schema

```python
# backend/models/entity.py

class Entity(Base):
    __tablename__ = "entities"

    # No ForeignKey constraint - intentional for partitioned table compatibility
    primary_detection_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,  # Index for efficient joins
    )

    # Relationship without FK - uses explicit primaryjoin
    primary_detection: Mapped[Detection | None] = relationship(
        "Detection",
        primaryjoin="Entity.primary_detection_id == Detection.id",
        foreign_keys=[primary_detection_id],
        lazy="selectin",
        viewonly=True,  # No cascade since there's no FK
    )
```

### Validation Methods

```python
# Async validation for use with database sessions
async def validate_primary_detection_async(
    self, session: AsyncSession
) -> tuple[bool, str | None]:
    """Validate that primary_detection_id references an existing detection."""
    if self.primary_detection_id is None:
        return True, None

    result = await session.execute(
        select(Detection.id)
        .where(Detection.id == self.primary_detection_id)
        .limit(1)
    )
    detection_exists = result.scalar_one_or_none() is not None

    if not detection_exists:
        return False, (
            f"Detection with id={self.primary_detection_id} does not exist. "
            f"Cannot set as primary_detection_id for Entity."
        )

    return True, None

# Convenience method that validates before setting
async def set_primary_detection_validated(
    self,
    session: AsyncSession,
    detection_id: int | None,
) -> tuple[bool, str | None]:
    """Set primary_detection_id with validation."""
    # ... implementation
```

### Usage Pattern

```python
# Creating an entity with a primary detection
entity = Entity.from_detection(
    entity_type=EntityType.PERSON,
    detection_id=detection.id,
    embedding=embedding_vector,
)

# Validate before persisting
is_valid, error = await entity.validate_primary_detection_async(session)
if not is_valid:
    raise ValueError(error)

session.add(entity)
await session.commit()

# Or use the validated setter
success, error = await entity.set_primary_detection_validated(session, detection.id)
if not success:
    raise ValueError(error)
```

---

## Consequences

### Positive

1. **Partitioning preserved:** Detection queries remain fast with time-based partitioning
2. **Flexible schema:** Can add soft-delete or archive patterns without FK complications
3. **Clear errors:** Validation provides descriptive error messages
4. **No migration needed:** Works with existing partitioned table structure

### Negative

1. **Requires discipline:** Developers must call validation methods
2. **Orphaned references possible:** If validation is skipped, invalid IDs can be stored
3. **No cascade delete:** Deleting a detection does not auto-null the entity reference

### Mitigations

1. **Code review checks:** Enforce validation in PR reviews
2. **Cleanup job:** Periodic job nullifies orphaned `primary_detection_id` values
3. **Monitoring:** Alert on orphaned reference counts

---

## Monitoring and Maintenance

### Orphan Detection Query

```sql
-- Find entities with orphaned primary_detection_id
SELECT e.id, e.primary_detection_id
FROM entities e
LEFT JOIN detections d ON e.primary_detection_id = d.id
WHERE e.primary_detection_id IS NOT NULL
  AND d.id IS NULL;
```

### Cleanup Job

```python
async def cleanup_orphaned_entity_references(session: AsyncSession) -> int:
    """Null out primary_detection_id for entities pointing to deleted detections."""
    result = await session.execute(
        update(Entity)
        .where(
            Entity.primary_detection_id.isnot(None),
            ~exists(
                select(Detection.id)
                .where(Detection.id == Entity.primary_detection_id)
            )
        )
        .values(primary_detection_id=None)
    )
    await session.commit()
    return result.rowcount
```

### Metrics

| Metric                    | Alert Threshold |
| ------------------------- | --------------- |
| Orphaned references count | > 100           |
| Validation failures/hour  | > 10            |

---

## Related Documentation

- [Entity Model](../../backend/models/entity.py) - Implementation
- [Detection Model](../../backend/models/detection.py) - Partitioned table
- [Re-identification Feature](../guides/face-recognition.md) - Entity tracking overview
- [PostgreSQL Partitioning](https://www.postgresql.org/docs/current/ddl-partitioning.html) - Official docs

---

## Decision Approval

| Role         | Name | Date       | Approval |
| ------------ | ---- | ---------- | -------- |
| Tech Lead    | -    | 2026-01-28 | Approved |
| Backend Lead | -    | 2026-01-28 | Approved |
| DBA          | -    | 2026-01-28 | Approved |

---

[Back to Decision Records](README.md)
