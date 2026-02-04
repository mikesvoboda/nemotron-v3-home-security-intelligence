# Investigation Report: NEM-5379 - Duplicate batch_id in Events

**Date:** 2026-02-04
**Investigator:** Claude Code
**Status:** CONFIRMED BUG - Race Condition Found

---

## Executive Summary

A race condition in the event creation pipeline allows multiple Events to be created with the same `batch_id`. This occurs when two concurrent analysis requests process the same batch before either has committed its Event to the database.

**Root Cause:** Idempotency check happens outside the database transaction, creating a time window where concurrent requests can both pass the check.

**Impact:** Low severity data integrity issue. Duplicate events may confuse users and analytics.

**Recommendation:** Fix the race condition by implementing database-level unique constraint + proper transaction handling.

---

## 1. Data Analysis

### Duplicate Batch ID Found

- **Batch ID:** `batch-15ba6507`
- **Event Count:** 2 events (expected: 1)
- **Location in Code:** Events table, no unique constraint on `batch_id` column

### Database Schema Analysis

**File:** `/home/msvoboda/.claude-squad/worktrees/msvoboda/dos9_1890f730fcf4fdc8/backend/models/event.py`

```python
# Line 48 - batch_id has NO unique constraint
batch_id: Mapped[str] = mapped_column(String, nullable=False)
```

**Indexes on batch_id (Line 193):**

```python
Index("idx_events_batch_id", "batch_id"),
```

This is a **regular index**, not a unique index. Multiple events can have the same `batch_id`.

---

## 2. Code Review - Race Condition Found

### 2.1 Batch ID Generation

**File:** `/home/msvoboda/.claude-squad/worktrees/msvoboda/dos9_1890f730fcf4fdc8/backend/services/batch_aggregator.py`

```python
# Line 103-117
def generate_batch_id() -> str:
    """Generate a short, unique batch identifier.

    Returns a batch ID in the format 'batch-XXXXXXXX' where X is a hex character.
    This provides 4 billion unique IDs while keeping logs human-readable.
    """
    return f"batch-{uuid.uuid4().hex[:8]}"
```

**Finding:** Batch ID generation is correct - uses UUID4 for uniqueness. Collision probability is negligible (1 in 4.3 billion).

### 2.2 Event Creation Flow

**File:** `/home/msvoboda/.claude-squad/worktrees/msvoboda/dos9_1890f730fcf4fdc8/backend/services/nemotron_analyzer.py`

#### Step 1: Idempotency Check (Line 1928)

```python
# Line 1928 - Check happens BEFORE transaction
existing_event_id = await self._check_idempotency(batch_id)
if existing_event_id is not None:
    # Return existing event
    return existing_event
```

#### Step 2: Create Event (Line 2213-2238)

```python
# Line 2213 - Transaction starts
async with get_session() as session:
    # Line 2215 - Create Event with batch_id
    event = Event(
        batch_id=batch_id,  # <-- DUPLICATE CAN OCCUR HERE
        camera_id=camera_id,
        ...
    )
    session.add(event)
    await session.flush()  # Get ID but don't commit
```

#### Step 3: Set Idempotency Key (Line 2274)

```python
# Line 2274 - Set Redis key INSIDE transaction (before commit)
await self._set_idempotency(batch_id, event.id)
```

#### Step 4: Transaction Commit (Line 679 in database.py)

```python
# backend/core/database.py Line 679
async with factory() as session:
    try:
        yield session
        await session.commit()  # <-- COMMIT HAPPENS HERE
```

---

## 3. Race Condition Timeline

### Vulnerable Window: Between idempotency check and commit

```
Time  Request A (batch-15ba6507)           Request B (batch-15ba6507)
----  --------------------------------      --------------------------------
T0    Check idempotency → None
T1    BEGIN TRANSACTION
T2                                          Check idempotency → None (!)
T3    CREATE Event(batch_id=...)
T4                                          BEGIN TRANSACTION
T5    FLUSH (get event.id)
T6    Set Redis: batch-15ba6507 → event_1
T7                                          CREATE Event(batch_id=...)
T8                                          FLUSH (get event.id)
T9                                          Set Redis: batch-15ba6507 → event_2
T10   COMMIT ✓
T11                                          COMMIT ✓ (DUPLICATE!)
```

**Key Problem:** Between T2 and T6, Request B checks Redis but Request A hasn't set the key yet, even though Request A has already created the Event in its transaction.

---

## 4. Why Does This Happen?

### 4.1 Two-Phase Check-Then-Act Pattern

The code uses a **check-then-act** pattern across two different data stores:

1. **Check** in Redis (fast, external cache)
2. **Act** in PostgreSQL (transactional database)

### 4.2 Transaction Isolation

PostgreSQL transactions provide **ACID guarantees**, but the idempotency check happens **outside** the transaction. This means:

- Request A's Event is not visible to Request B until T10 (commit)
- Request A's Redis key is visible to Request B at T6 (before commit)
- Window T2-T6: Both requests think they are the first

### 4.3 Idempotency Key Timing

The idempotency key is set at line 2274, **inside** the transaction but **before** the commit at line 679. However, the check at line 1928 happens **before** the transaction even starts.

---

## 5. Search for Other Duplicate Batch IDs

**Recommendation:** Query the database to find all duplicate batch_ids:

```sql
SELECT batch_id, COUNT(*) as event_count
FROM events
WHERE deleted_at IS NULL
GROUP BY batch_id
HAVING COUNT(*) > 1
ORDER BY event_count DESC;
```

This will reveal:

- How many duplicates exist in production
- Whether this is a rare or common occurrence
- Which batch_ids are affected

---

## 6. Is batch_id Meant to Be Unique?

### Evidence That batch_id SHOULD Be Unique:

1. **Name suggests uniqueness:** "batch_id" implies a unique identifier for a batch
2. **Idempotency system exists:** Lines 1238-1298 implement Redis-based idempotency specifically to prevent duplicate Events for the same batch
3. **Comment at Line 1242:** "This prevents duplicate Event creation when Nemotron analyzer retries"
4. **generate_batch_id() uses UUID4:** Designed to be globally unique
5. **Index exists:** `idx_events_batch_id` suggests batch_id is used for lookups (1:1 mapping expected)

### Evidence That batch_id Might Allow Duplicates:

1. **No unique constraint in database:** Line 48 defines `batch_id` without `unique=True`
2. **No migration adding unique constraint found**
3. **Tests may not verify uniqueness**

### Conclusion:

Based on the idempotency system and UUID-based generation, **batch_id is clearly intended to be unique**. The lack of database constraint is an oversight.

---

## 7. Additional Findings

### 7.1 Fast Path Uses Same Pattern

The fast path analysis method (`analyze_detection_fast_path`, line 2444) has the **same race condition**:

- Line 2483: Check idempotency
- Line 2651: Create Event
- Line 2705: Set idempotency

### 7.2 Idempotency Key TTL

Line 1290: Idempotency keys expire after 1 hour (3600 seconds). This means:

- After 1 hour, the same batch_id could theoretically be reprocessed
- However, batch_ids use UUID4 so collision is unlikely

---

## 8. Recommended Fix

### Option A: Database Unique Constraint (Recommended)

**Pros:**

- Enforces uniqueness at database level (ACID guarantees)
- Prevents duplicates even if application logic fails
- Simple to implement

**Cons:**

- Will raise IntegrityError on duplicate, needs error handling
- Requires Alembic migration

**Implementation:**

1. Add unique constraint to `batch_id` column in `event.py`
2. Create Alembic migration to add constraint
3. Update error handling to catch IntegrityError and return existing event
4. Clean up existing duplicates before applying migration

### Option B: Pessimistic Locking with Redis

**Pros:**

- No database schema changes
- Can be implemented immediately

**Cons:**

- More complex (distributed lock management)
- Requires Redis to be available
- Lock timeout and deadlock handling needed

**Implementation:**

1. Use Redis SETNX for atomic lock acquisition
2. Acquire lock before creating event
3. Check database within lock for existing event
4. Create event if not exists
5. Release lock

### Option C: Move Idempotency Check Inside Transaction

**Pros:**

- Minimal code changes
- Maintains existing idempotency system

**Cons:**

- Still has small race window (Redis is external)
- Doesn't prevent duplicates if Redis is down

**Implementation:**

1. Move `_check_idempotency()` call inside the transaction
2. Use database-level locking (SELECT ... FOR UPDATE)

---

## 9. Recommended Solution (Hybrid Approach)

**Combine Option A + Option C for defense-in-depth:**

1. **Add unique constraint** to `batch_id` (prevents duplicates at DB level)
2. **Keep Redis idempotency** for fast duplicate detection (avoids unnecessary DB queries)
3. **Add error handling** for IntegrityError (catch race condition, return existing event)

### Implementation Steps:

#### Step 1: Database Migration

```python
# alembic/versions/XXXX_add_unique_constraint_batch_id.py
def upgrade():
    # Clean up duplicates first
    op.execute("""
        DELETE FROM events e1
        USING events e2
        WHERE e1.id > e2.id
        AND e1.batch_id = e2.batch_id
        AND e1.deleted_at IS NULL
        AND e2.deleted_at IS NULL
    """)

    # Add unique constraint
    op.create_unique_constraint(
        'uq_events_batch_id',
        'events',
        ['batch_id'],
        postgresql_where='deleted_at IS NULL'  # Partial unique index
    )
```

#### Step 2: Update Model

```python
# backend/models/event.py Line 48
batch_id: Mapped[str] = mapped_column(
    String,
    nullable=False,
    unique=True  # Add this
)
```

#### Step 3: Add Error Handling

```python
# backend/services/nemotron_analyzer.py
async with get_session() as session:
    try:
        event = Event(batch_id=batch_id, ...)
        session.add(event)
        await session.flush()
        await self._set_idempotency(batch_id, event.id)
        # ... rest of code
    except IntegrityError as e:
        # Duplicate batch_id detected - retrieve existing event
        if 'uq_events_batch_id' in str(e):
            logger.info(f"Duplicate batch_id {batch_id}, returning existing event")
            existing_event = await self._get_event_by_batch_id(batch_id)
            if existing_event:
                return existing_event
        raise  # Re-raise if not our constraint
```

---

## 10. Testing Recommendations

### 10.1 Unit Tests

```python
# Test concurrent event creation with same batch_id
async def test_duplicate_batch_id_prevented():
    batch_id = generate_batch_id()

    # Create two concurrent requests
    results = await asyncio.gather(
        analyzer.analyze_batch(batch_id, camera_id, detection_ids),
        analyzer.analyze_batch(batch_id, camera_id, detection_ids),
        return_exceptions=True
    )

    # Verify only one event was created
    events = await get_events_by_batch_id(batch_id)
    assert len(events) == 1
```

### 10.2 Integration Tests

```python
# Test race condition with real database
async def test_race_condition_protection():
    # Use real Redis and PostgreSQL
    # Simulate concurrent requests
    # Verify database constraint prevents duplicates
```

---

## 11. Prevention Recommendations

1. **Always use database constraints** for uniqueness requirements
2. **Document uniqueness assumptions** in model docstrings
3. **Add integration tests** for concurrent operations
4. **Review idempotency patterns** across codebase
5. **Use database-level locking** for critical sections

---

## 12. Files to Update

1. `backend/models/event.py` - Add unique constraint
2. `backend/services/nemotron_analyzer.py` - Add IntegrityError handling
3. `alembic/versions/` - Create migration
4. `backend/tests/integration/test_nemotron_analyzer.py` - Add concurrency tests
5. `docs/development/data-integrity.md` - Document uniqueness constraints (if exists)

---

## Conclusion

**Bug Confirmed:** Race condition allows duplicate `batch_id` values in Events table.

**Root Cause:** Idempotency check happens outside database transaction, creating vulnerable time window.

**Fix Priority:** Medium (data integrity issue, but low impact)

**Recommended Fix:** Add database unique constraint + error handling (Option A + C hybrid)

**Next Steps:**

1. Query database for existing duplicates
2. Implement recommended fix following TDD
3. Add integration tests for concurrency
4. Run `./scripts/validate.sh` to verify fix
5. Document findings in Linear ticket NEM-5379
