# WP4.4 Triage Dossier — backend/services/hybrid_entity_storage.py

- Surviving mutants: **107** (of 252 keys; meta read clean, no JSONDecodeError retries needed)
- Diffs: all via `uv run mutmut show <key>` (read-only, ~0.7 s each, no cache conflicts)
- Functions with survivors: `HybridEntityMatch.from_redis_match` (9),
  `HybridEntityMatch.from_postgresql_match` (17), `HybridEntityStorage.store_detection_embedding` (48),
  `HybridEntityStorage.get_entity_full_history` (16), `HybridEntityStorage.get_entities_by_timerange` (17).
  9 + 17 + 48 + 16 + 17 = **107** ✔
- Covering test file (all five functions, per `mutmut-stats.json` tests_by_mangled_function_name):
  `backend/tests/unit/services/test_hybrid_entity_storage.py` (985 lines)
  - `TestStoreDetectionEmbedding` L199-298 · `TestErrorHandling` L770-835 ·
    `TestGetEntityFullHistory` L561-598 · `TestGetEntitiesByTimerange` L606-675 ·
    `TestMatchConversion` L916-985 · `TestHybridStorageWorkflows` L683-762

## Key structural finding

Every behavior-bearing survivor is a **kwarg/field value mutation** (`x=None`, kwarg deleted,
`str(x)`→`str(None)`, ternary cond forced). Each survives for the same reason: tests assert the
**return value** (`assert entity_id == new_entity.id`, `assert is_new is True`) and assert
`assert_called_once()` plus only the _outermost_ fields of mock payloads —
`stored_embedding.entity_type/embedding/camera_id/attributes` (test L295-298) but **not** `detection_id`
or `timestamp`; `assign_entity.call_args[1]["entity_type"]` (test L761-762) but no other kwarg;
`list.call_args[1]` only for `limit`/`offset` (L673-675) but **not** `entity_type`/`since`. AsyncMocks
accept any kwargs silently, so `since=None` / `timestamp=None` / `detection_id=None` flow through
unobserved. Two `assert_called_once_with(...)` calls kill ~12 survivors wholesale.

The remaining mass (~62) is **logger-argument/string survivors**: pytest never runs with DEBUG/WARNING
capture for this module (no `caplog` anywhere in the file; `backend/core/logging.py` never sets
`propagate=False`, so a caplog test is cheap if wanted). Mutmut's arg-deletion class is doubly invisible:
`logger.debug(msg, a, b)` with a deleted arg raises `TypeError: not enough arguments for format string`
**only when the record is actually emitted** — at DEBUG (off) that never happens; inside the store
method's `try` the even the WARNING-path arity break is swallowed. These are LOW-VALUE plumbing.

`from_redis_match` / `from_postgresql_match` assignment→None variants are **validation-masked**: the
`HybridEntityMatch` dataclass / source attribute access raises inside `find_matches`' per-source
`try` (L347, L378), the exception is logged as a warning, and the surviving asserts are only
`assert len(matches) >= 1` / `isinstance` / `.similarity` / `.source` — the converted fields are never
field-checked. Fix = assert the converted fields (T-D, T-E below).

## Cluster table

Key suffix = `__mutmut_N` within the named function.

| #   | Pattern (function / concern)                                                                                                                                                         | Count   | Example keys                            | Classification                            |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------- | --------------------------------------- | ----------------------------------------- |
| C1  | `store_detection_embedding` L265-272: `assign_entity(**kw)` → None or kwarg deleted (detection_id/entity_type/embedding/camera_id/timestamp/attributes)                              | 10      | store**2, store**4, store\_\_10         | TEST-GAP                                  |
| C2  | `store_detection_embedding` L283-290: `EntityEmbedding(...)` field → None (timestamp, detection_id incl. `str(None)`)                                                                | 3       | store**35, store**36, store\_\_44       | TEST-GAP                                  |
| C3  | `store_detection_embedding` L293: Redis client `self.redis` → None in `reid.store_embedding(...)`                                                                                    | 1       | store\_\_46                             | TEST-GAP                                  |
| C4  | `store_detection_embedding` L274-279: `("created" if is_new else "matched")` cond forced (`and False` / `or True`) — debug log misreports created-vs-matched                         | 2       | store**25, store**26                    | TEST-GAP                                  |
| C5  | `from_postgresql_match` L147-161: field assignments → None (entity_id/entity_type/embedding/camera_id/timestamp/detection_id/attributes/time_gap_seconds/entity)                     | 9       | from_postgresql_match**1, **2, \_\_5    | TEST-GAP                                  |
| C6  | `store_detection_embedding` L300-304: warning path `str(e)` → `str(None)` — corrupts the only record of a failed Redis write                                                         | 1       | store\_\_66                             | TEST-GAP                                  |
| C7  | `from_postgresql_match`: detection_id ternary cond forced, `str(pid)`→`str(None)` (yields literal `"None"`), `entity=entity` deletion, `or []`/`or {}` fallbacks → `and`             | 6       | from_postgresql_match**22, **26, \_\_29 | TEST-GAP                                  |
| C8  | `from_redis_match` L116-128: field assignments → None (same nine fields; `entity=None` deletion)                                                                                     | 9       | from_redis_match**1, **3, \_\_9         | TEST-GAP                                  |
| C9  | `get_entities_by_timerange` L494-499: `entity_repo.list(entity_type=…, since=…)` → None                                                                                              | 2       | timerange**2, timerange**3              | TEST-GAP                                  |
| C10 | `get_entities_by_timerange` L494-499: `entity_repo.list(entity_type=…, since=…)` kwarg deleted                                                                                       | 2       | timerange**6, timerange**7              | TEST-GAP                                  |
| C11 | `from_postgresql_match`: `"unknown"` sentinel string clobbers (`XXunknownXX`, `UNKNOWN`) in camera_id fallback                                                                       | 2       | from_postgresql_match**24, **25         | LOW-VALUE (T-D kills for free)            |
| C12 | `store_detection_embedding` L274-279, L294-297, L300-304: logger debug+warning args → None (msg fmt, "created/matched", detection_id, is_new, str(e))                                | 9       | store**14, store**50, store\_\_57       | LOW-VALUE                                 |
| C13 | `store_detection_embedding` L274-279: `"created"`/`"matched"` log-word clobbers (XX/UPPER/lowercase — text only, NOT the cond-forced C4)                                             | 4       | store**27, store**28, store\_\_29       | LOW-VALUE                                 |
| C14 | `store_detection_embedding`: logger debug+warning args **deleted** (breaks format arity; fatal only if the call emits — debug never emits in tests, warning break is inside the try) | 9       | store**18, store**52, store\_\_60       | LOW-VALUE                                 |
| C15 | `store_detection_embedding`: logger debug+warning message-string clobbers (XX/UPPER/lowercase ×3 lines)                                                                              | 9       | store**22, store**54, store\_\_63       | LOW-VALUE                                 |
| C16 | `get_entity_full_history` L452-457: found-path logger.debug args → None (fmt, entity_id, detection_count)                                                                            | 3       | full_history**3, **4, \_\_5             | LOW-VALUE                                 |
| C17 | `get_entity_full_history` L452-457: found-path logger.debug args deleted                                                                                                             | 3       | full_history**6, **7, \_\_8             | LOW-VALUE                                 |
| C18 | `get_entity_full_history` L459: not-found-path logger.debug arg → None / arg deleted (fmt, entity_id, both-args forms)                                                               | 4       | full_history**12, **13, \_\_14          | LOW-VALUE                                 |
| C19 | `get_entities_by_timerange` L501-507: logger.debug args → None (fmt, len, total, entity_type, since)                                                                                 | 5       | timerange**10, **11, \_\_14             | LOW-VALUE                                 |
| C20 | `get_entities_by_timerange` L501-507: logger.debug args deleted                                                                                                                      | 5       | timerange**15, **16, \_\_19             | LOW-VALUE                                 |
| C21 | `get_entity_full_history`: logger message-string clobbers (both debug lines: XX/UPPER/lowercase)                                                                                     | 6       | full_history**9, **10, \_\_11           | EQUIVALENT                                |
| C22 | `get_entities_by_timerange`: logger message-string clobbers (XX/UPPER/lowercase)                                                                                                     | 3       | timerange**20, **21, \_\_22             | EQUIVALENT                                |
|     | **Total**                                                                                                                                                                            | **107** |                                         | TEST-GAP 45 / LOW-VALUE 53 / EQUIVALENT 9 |

Count check: 10+3+1+2+9+1+6+9+2+2 (=45) + 2+9+4+9+9+3+3+4+5+5 (=53) + 6+3 (=9) = **107** ✔
Per-function check: from_redis 9 (C8) + from_pg 9+6+2=17 (C5,C7,C11) + store 10+3+1+2+1+9+4+9+9=48
(C1,C2,C3,C4,C6,C12,C13,C14,C15) + history 3+3+4+6=16 (C16,C17,C18,C21) + timerange 2+2+5+5+3=17
(C9,C10,C19,C20,C22) ✔

### Classification notes

- **C1 (10)**: `hybrid_entity_storage.py:265-272`. Every mutation changes what the clustering service —
  the entire PostgreSQL write path — receives. Tests execute the line
  (`test_stores_in_redis_and_postgresql`, test L202-233) but only `assert_called_once()` (L227); no
  `assert_called_once_with` exists for this call anywhere in the file. Executed, never asserted → TEST-GAP.
  (Mutants 7/13 `attributes=None` coincide with `test_none_attributes`' own None attributes —
  unkillable _by that test_; T-A uses non-None attributes and kills them.)
- **C2 (3)**: `:283-290` — hot-cache payload loses timestamp/detection_id.
  `test_stores_entity_embedding_in_redis` (L265-298) asserts four payload fields but skips exactly these
  two. "Test exists, asserts too weakly" → TEST-GAP.
- **C3 (1)**: `:293` — the Redis hot-cache write would target client `None`; silent cache-miss on every
  store (read path then falls to slow PostgreSQL for everything). Killed by T-C's `args[0] is mock_redis`.
- **C4 (2)**: `:274-279` — only the debug message differs ("matched" printed when an entity was _created_),
  and that line is the operator's only record of clustering outcomes. Marked TEST-GAP with a one-line
  caplog assert; demote to LOW-VALUE if the team rules debug-log content out of contract.
- **C5/C8 (18)**: `:147-161`, `:116-128` — assignment→None raises on non-nullable fields (`camera_id=None`
  fails `str`, `entity_id=None` fails `UUID | str`), thrown inside `find_matches`' `try` (L347/L378),
  then swallowed as a warning. Surviving asserts: `len(matches) >= 1` (L342/L376), `isinstance`,
  `.similarity`, `.source` (`TestMatchConversion` L916-985) — never field-by-field. The conversion
  contract is untested → TEST-GAP (kills by asserting every converted field; note `assert len(matches)
== 1` alone fails when conversion crashes, which is itself the kill signal).
- **C6 (1)**: `:300-304` — the except path is contract ("log but don't fail when Redis is down", see
  `test_handles_redis_store_error_gracefully` L774-805); `str(e)`→`str(None)` erases the error text from
  the operator-visible warning. Killed by T-C's warning-message assert.
- **C7 (6)**: `:151-160` — real output changes: `detection_id` becomes literal `"None"` (a truthy string
  that then _pollutes the seen_ids dedup set_ — find_matches L388-391 stores `"None"`, so every future
  detection-less entity collides); `entity=entity` deletion drops the full Entity (default None);
  `or []`/`or {}`→`and` returns falsy-side values. Same unasserted conversion fields → TEST-GAP, killed
  by T-D.
- **C9/C10 (4)**: `:494-499` — `since=None` (or dropped) silently disables the time filter: a 7-day
  dashboard query returns all-time rows while the test's mock echoes the fixture list back unchanged,
  so `len(entities) == 2` still passes. `test_pagination_parameters` asserts only limit/offset on
  `call_args[1]` (L673-675) — the exact two kwargs _not_ mutated. Executed, weakly asserted → TEST-GAP.
- **C11 (2)**: the sentinel literal `"unknown"` is asserted nowhere, and `create_mock_entity` always
  passes `entity_metadata=None` so even the fallback branch is value-untested. Nobody should assert the
  literal; T-D asserts `camera_id == "unknown"` for the fallback case and kills them incidentally.
  LOW-VALUE.
- **C12/C14/C15/C16/C17/C18/C19/C20 (51)**: logger arg plumbing. All execute under existing tests
  (TestGetEntityFullHistory L561-598, TestGetEntitiesByTimerange L606-675, TestStoreDetectionEmbedding
  L199-298); zero log capture. Arg→None only changes emitted text (off by default); arg-deletion breaks
  format arity but the `TypeError` fires only if the record emits (and store's warning variant is inside
  the try). Asserting logging-library plumbing is low value → LOW-VALUE; recommend
  mutmut config suppression for logger calls in this module.
- **C13 (4)**: log-word case/surround clobbers ("XXcreatedXX"/"CREATED") — cosmetic text → LOW-VALUE.
- **C21/C22 (9)**: pure message-string case/decoration changes (XX-wraps, lowercase, SCREAMING with
  format specs intact) on the two `get_entity_full_history` debug lines and the one timerange debug line.
  No formatting-semantics change, no behavioral surface — canonical EQUIVALENT bucket.

## Drafted tests (6 highest-value clusters)

All **UNVERIFIED — not yet run red/green**. TDD procedure (same for all six): apply the cluster's mutant
diff → run `uv run pytest backend/tests/unit/services/test_hybrid_entity_storage.py -k <test_name>` →
new test FAILS on the asserted line; revert diff to original → PASSES. Style follows the existing file
(fixtures `hybrid_storage`/`mock_*`, class grouping, `@pytest.mark.asyncio`, `create_mock_entity`).

### T-A → kills C1 (10)

```python
    # ADD to class TestStoreDetectionEmbedding (test_hybrid_entity_storage.py)
    @pytest.mark.asyncio
    async def test_passes_all_arguments_to_clustering_assign_entity(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_clustering_service: AsyncMock,
    ) -> None:
        """Test that store_detection_embedding forwards every argument to assign_entity verbatim."""
        embedding = create_sample_embedding(seed=600)
        timestamp = datetime.now(UTC)
        attributes = {"clothing": "hi-vis vest"}

        new_entity = create_mock_entity(entity_type="person", embedding=embedding)
        mock_clustering_service.assign_entity.return_value = (new_entity, True, None)

        await hybrid_storage.store_detection_embedding(
            detection_id=5001,
            entity_type="person",
            embedding=embedding,
            camera_id="side_yard",
            timestamp=timestamp,
            attributes=attributes,
        )

        # UNVERIFIED - not yet run red/green
        # Exact-call assertion: any kwarg mutated to None or dropped must fail here.
        mock_clustering_service.assign_entity.assert_called_once_with(
            detection_id=5001,
            entity_type="person",
            embedding=embedding,
            camera_id="side_yard",
            timestamp=timestamp,
            attributes=attributes,
        )
```

Kills store**2,4,5,6,7,8,10,11,12,13. TDD: mutant `**4` (`embedding=None`) → kwargs mismatch → fails on
mutant, passes on original.

### T-B → kills C2 (3)

```python
    # ADD to class TestStoreDetectionEmbedding
    @pytest.mark.asyncio
    async def test_redis_embedding_carries_detection_id_and_timestamp(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_clustering_service: AsyncMock,
        mock_reid_service: AsyncMock,
    ) -> None:
        """Test the EntityEmbedding handed to reid preserves detection_id and timestamp."""
        embedding = create_sample_embedding(seed=601)
        timestamp = datetime.now(UTC)

        new_entity = create_mock_entity(entity_type="person", embedding=embedding)
        mock_clustering_service.assign_entity.return_value = (new_entity, True, None)

        await hybrid_storage.store_detection_embedding(
            detection_id=5002,
            entity_type="person",
            embedding=embedding,
            camera_id="porch",
            timestamp=timestamp,
        )

        # UNVERIFIED - not yet run red/green
        mock_reid_service.store_embedding.assert_called_once()
        stored = mock_reid_service.store_embedding.call_args[0][1]
        assert stored.detection_id == "5002"   # str(detection_id) contract
        assert stored.timestamp == timestamp
```

Kills store**35, store**36, store**44. TDD: `**44` (`str(None)`→`"None"`) fails the first assert on the
mutant, passes on original.

### T-C → kills C3 (1) + C6 (1) + C4 (2, caplog)

```python
    # ADD to class TestErrorHandling (module needs `import logging` at top)
    @pytest.mark.asyncio
    async def test_store_targets_real_redis_client_and_logs_outcome(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_clustering_service: AsyncMock,
        mock_reid_service: AsyncMock,
        mock_redis: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test Redis store targets the real client and the warning log keeps the error text."""
        embedding = create_sample_embedding(seed=602)
        timestamp = datetime.now(UTC)
        new_entity = create_mock_entity(entity_type="person", embedding=embedding)
        mock_clustering_service.assign_entity.return_value = (new_entity, True, None)

        with caplog.at_level(logging.DEBUG, logger="backend.services.hybrid_entity_storage"):
            await hybrid_storage.store_detection_embedding(
                detection_id=5003,
                entity_type="person",
                embedding=embedding,
                camera_id="front_door",
                timestamp=timestamp,
            )

        # UNVERIFIED - not yet run red/green
        call = mock_reid_service.store_embedding.call_args
        assert call[0][0] is mock_redis  # kills store__46 (None client)
        messages = [r.getMessage() for r in caplog.records]
        # kills store__25/__26 ("matched" when is_new=True) via the created-report
        assert any("Entity created for detection 5003 (is_new=True)" in m for m in messages)

        # Now force the Redis failure path: warning must carry the real exception text.
        mock_reid_service.store_embedding.side_effect = Exception("boom-redis")
        with caplog.at_level(logging.WARNING, logger="backend.services.hybrid_entity_storage"):
            entity_id, is_new = await hybrid_storage.store_detection_embedding(
                detection_id=5004,
                entity_type="person",
                embedding=embedding,
                camera_id="front_door",
                timestamp=timestamp,
            )
        assert entity_id == new_entity.id  # pg path still succeeded (matches existing test's contract)
        warns = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        # kills store__66 (str(None) -> "None" instead of "boom-redis")
        assert any("boom-redis" in m and "5004" in m for m in warns)
```

(`caplog` works: `backend/core/logging.py` never sets `propagate=False`.)

### T-D → kills C5 (9) + C7 (6) + C11 (2)

```python
    # ADD to class TestMatchConversion (sibling of test_postgresql_match_to_hybrid_match L956-985)
    @pytest.mark.asyncio
    async def test_postgresql_match_maps_every_field(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_reid_service: AsyncMock,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test from_postgresql_match maps every Entity field into the HybridEntityMatch."""
        from backend.services.hybrid_entity_storage import HybridEntityMatch

        embedding = create_sample_embedding(seed=603)
        last_seen = datetime.now(UTC) - timedelta(hours=2)
        pg_entity = create_mock_entity(
            entity_type="person",
            embedding=embedding,
            last_seen_at=last_seen,
        )
        pg_entity.primary_detection_id = 4242
        pg_entity.entity_metadata = {"camera_id": "front_door", "clothing": "hoodie"}
        mock_reid_service.find_matching_entities.return_value = []
        mock_entity_repository.find_by_embedding.return_value = [(pg_entity, 0.88)]

        matches = await hybrid_storage.find_matches(
            embedding=embedding,
            entity_type="person",
            threshold=0.85,
            include_historical=True,
        )

        # UNVERIFIED - not yet run red/green
        assert len(matches) == 1
        m = matches[0]
        assert isinstance(m, HybridEntityMatch)
        assert m.source == "postgresql"
        assert m.entity_id == pg_entity.id
        assert m.entity_type == "person"
        assert m.embedding == embedding          # kills or->and on `or []`
        assert m.camera_id == "front_door"       # kills metadata-branch None
        assert m.timestamp == last_seen
        assert m.detection_id == "4242"          # kills str(None)/cond-forced "None" variants
        assert m.attributes == pg_entity.entity_metadata
        assert m.similarity == 0.88
        assert m.entity is pg_entity             # kills entity=None / entity=entity-deleted

    @pytest.mark.asyncio
    async def test_postgresql_match_fallbacks_when_entity_bare(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_reid_service: AsyncMock,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test camera_id/detection_id/embedding/attributes fallbacks for a metadata-less entity."""
        embedding = create_sample_embedding(seed=604)
        mock_reid_service.find_matching_entities.return_value = []
        bare = create_mock_entity(entity_type="person")  # metadata=None, primary_detection_id=None
        mock_entity_repository.find_by_embedding.return_value = [(bare, 0.7)]

        matches = await hybrid_storage.find_matches(
            embedding=embedding,
            entity_type="person",
            threshold=0.85,
            include_historical=True,
        )

        # UNVERIFIED - not yet run red/green
        assert len(matches) == 1
        assert matches[0].camera_id == "unknown"   # kills XX/UNKNOWN clobbers + None
        assert matches[0].detection_id is None
        assert matches[0].embedding == []          # kills `and []` variant
        assert matches[0].attributes == {}         # kills `and {}` variant
```

TDD: e.g. `from_postgresql_match__2` (`entity_type=None`) makes the dataclass raise inside find_matches'
try → `len(matches) == 1` fails on mutant; `__26` (cond `and False` → detection_id `"None"` literal) fails
the `== "4242"` assert; both pass on original.

### T-E → kills C8 (9)

```python
    # ADD to class TestMatchConversion (sibling of existing test_redis_match_to_hybrid_match L920-954)
    @pytest.mark.asyncio
    async def test_redis_match_maps_every_field(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_reid_service: AsyncMock,
    ) -> None:
        """Test from_redis_match copies every EntityMatch field into the HybridEntityMatch."""
        from backend.services.hybrid_entity_storage import HybridEntityMatch

        embedding = create_sample_embedding(seed=605)
        ts = datetime.now(UTC) - timedelta(minutes=5)
        redis_match = EntityMatch(
            entity=EntityEmbedding(
                entity_type="person",
                embedding=embedding,
                camera_id="garage",
                timestamp=ts,
                detection_id="det_605",
                attributes={"carrying": "box"},
            ),
            similarity=0.92,
            time_gap_seconds=300,
        )
        mock_reid_service.find_matching_entities.return_value = [redis_match]

        matches = await hybrid_storage.find_matches(
            embedding=embedding,
            entity_type="person",
            threshold=0.85,
            include_historical=False,
        )

        # UNVERIFIED - not yet run red/green
        assert len(matches) == 1
        m = matches[0]
        assert isinstance(m, HybridEntityMatch)
        assert m.source == "redis"
        assert m.entity_id == "det_605"
        assert m.entity_type == "person"
        assert m.embedding == embedding
        assert m.camera_id == "garage"
        assert m.timestamp == ts
        assert m.detection_id == "det_605"
        assert m.attributes == {"carrying": "box"}
        assert m.similarity == 0.92
        assert m.time_gap_seconds == 300
        assert m.entity is None
```

TDD: `from_redis_match__9` (`time_gap_seconds=None`) fails `== 300` on mutant, passes on original.

### T-F → kills C9 (2) + C10 (2)

```python
    # ADD to class TestGetEntitiesByTimerange
    @pytest.mark.asyncio
    async def test_forwards_filters_verbatim_to_repository_list(
        self,
        hybrid_storage: HybridEntityStorage,
        mock_entity_repository: AsyncMock,
    ) -> None:
        """Test entity_type/since/limit/offset are forwarded to entity_repo.list unchanged."""
        since = datetime.now(UTC) - timedelta(days=7)
        entities_list = [create_mock_entity(entity_type="person")]
        mock_entity_repository.list.return_value = (entities_list, 1)

        await hybrid_storage.get_entities_by_timerange(
            entity_type="person",
            since=since,
            limit=10,
            offset=0,
        )

        # UNVERIFIED - not yet run red/green
        mock_entity_repository.list.assert_called_once_with(
            entity_type="person",
            since=since,
            limit=10,
            offset=0,
        )
```

TDD: mutant `timerange__3` (`since=None`) → kwargs mismatch → fails on mutant, passes on original.
Closes the silent-filter-drop hazard: a `since=None` bug means a 7-day query returns all-time rows.

## Coverage math for the drafted six

T-A..T-F collectively kill all 45 TEST-GAP survivors (C1-C10), plus incidental claims on C11 (2) and parts
of C12/C13/C14/C15 via the caplog asserts in T-C. Worst case 45/107 killed by tests; the remaining 62
(LOW-VALUE 51 + EQUIVALENT 9 + C11's 2) are log-string/plumbing mass recommended for mutmut config
suppression (exclude logger calls in `backend/services/hybrid_entity_storage`) rather than tests.

## Verdict summary

- **TEST-GAP: 45** in 10 clusters (C1-C10) — six drafted tests close them.
- **LOW-VALUE: 53** in 10 clusters (C11-C20) — log plumbing; suppress via config.
- **EQUIVALENT: 9** in 2 clusters (C21, C22) — pure message-string case changes.
- Total 107 ✔ (cluster counts sum exactly; each key assigned to exactly one cluster from its diff).
