# WP4.4 Triage Dossier — backend/services/entity_clustering_service.py

**Wave**: gen-2 NEW tier (never-tallied module)
**Source**: `backend/services/entity_clustering_service.py` (373 lines)
**Verdicts source**: `mutants/backend/services/entity_clustering_service.py.meta` — 154 keys total: **82 killed, 72 SURVIVED, 0 unchecked**
**Diff source**: `uv run mutmut show <key>` for all 72 survivors (0 failures; raw dump at `/tmp/wp25/wp44-triage/ecs_diffs.txt`, normalized JSON at `/tmp/wp25/wp44-triage/ecs_final.json`)

## Covering test files (from mutmut-stats `tests_by_mangled_function_name`)

| Function | Covering tests |
|---|---|
| `__init__` (27 tests), `assign_entity` (22), `_update_entity_with_detection` (9), `_create_entity` (14), `_trigger_entity_discovered_webhook` (16) | `backend/tests/unit/services/test_entity_clustering_service.py` (1082 lines, fixtures `mock_entity_repository`/`clustering_service` at :99/:115) |
| `_trigger_entity_discovered_webhook` also | `backend/tests/unit/services/test_webhook_integration.py` (`TestEntityClusteringWebhookIntegration` :261-353) |

**Structural root cause of most survivors**: `mock_entity_repository` fakes the DB session, so `flag_modified()` / `session.flush()` mutations are inert under test, and **no unit test ever reads back `entity.entity_metadata`** (the word `cameras_seen` appears in the unit test file only in a comment at :1039). Webhook payload keys `first_seen_at`/`detection_count`/`event_id` and the warning-path `extra` dict are likewise never asserted (the integration test asserts only `entity_type`/`camera_id`/`trust_status` membership — `test_webhook_integration.py:310-313`).

## Cluster table (16 clusters, counts sum to 72)

| # | Cluster (function / concern) | Mutation pattern | Count | Keys (examples, ≤3) | Classification | Rationale |
|---|---|---|---|---|---|---|
| C1 | `__init__`, `assign_entity` ×2 — `logger.debug(...)` calls | log msg→None / arg→None / arg removed / XX-wrapped / lower / UPPER | 29 | `__init__#4`, `assign_entity#42`, `assign_entity#85` | EQUIVALENT | `logger.debug` with `%s` args never executes its format string when DEBUG is below the configured level; message text/arg order is diagnostic-only. Not behavior anyone should assert. |
| C3 | `assign_entity` :179 read side — `entity_metadata.get("cameras_seen", [])` | key→None / XX / UPPER | 3 | `assign_entity#24`, `assign_entity#28`, `assign_entity#29` | TEST-GAP | Key rename on the *read* silently breaks camera accumulation for entities that already have `cameras_seen` — subsequent cameras are re-appended onto a fresh list, duplicating/losing history. Unit tests run the line but never inspect the dict. Killed by T1/T2. |
| C4 | `assign_entity` :180 guard `if camera_id and camera_id not in cameras_seen:` | `and`→`or`; `not in`→`in` | 2 | `assign_entity#30`, `assign_entity#31` | TEST-GAP | **`or` flip**: empty-string `camera_id` now passes the guard and `""` is appended to `cameras_seen`; a brand-new empty metadata is mutated **without** `flag_modified`/flush (branch condition false) → JSONB write silently dropped. **`in` flip**: accumulation is inverted — existing cameras never tracked, unseen ones skipped. No test ever feeds a repeat/new camera and asserts the list. Highest-severity gap. Killed by T1. |
| C5 | `assign_entity` :182 write side `metadata["cameras_seen"] = cameras_seen` | value→None; key→XX/UPPER | 3 | `assign_entity#33`, `assign_entity#34`, `assign_entity#35` | TEST-GAP | Same accumulation concern on the write side: a renamed/None key leaves `cameras_seen` permanently missing → `cameras_seen: []` surfaces in the entities API (consumers: `backend/api/routes/entities.py`, `EntityCard.tsx`). Killed by T1/T2. |
| C6 | `assign_entity` :181 `cameras_seen.append(camera_id)` | appended value→None | 1 | `assign_entity#32` | TEST-GAP | `None` lands inside the cameras list → API `camera_count = len(cameras)` inflates with a phantom camera. Killed by T1. |
| C7 | `assign_entity` :206 new-entity init `metadata["cameras_seen"] = [camera_id]` | key→XX/UPPER | 2 | `assign_entity#68`, `assign_entity#69` | TEST-GAP | New entities ship without `cameras_seen` → exactly the NEM-3262 "legacy entity" defect class the integration suite guards against, but only at the API layer; the unit-level writer is unguarded. Killed by T2. |
| C8 | `assign_entity` :207 new-entity init `metadata["camera_id"] = camera_id` | value→None; key→XX/UPPER | 3 | `assign_entity#70`, `assign_entity#71`, `assign_entity#72` | TEST-GAP | `camera_id` metadata key feeds the NEM-3262 camera-count fallback (`backend/services/unified_embedding_service.py`); silent loss degrades camera attribution to zero. Killed by T2. |
| C13 | `assign_entity` :170-173 → `_update_entity_with_detection(detection_id=…, timestamp=…)` | kwarg→None | 2 | `assign_entity#14`, `assign_entity#15` | TEST-GAP | `timestamp=None` makes `Entity.update_seen` fall back to `datetime.now(UTC)` (`backend/models/entity.py:187`) instead of the detection's timestamp — historical replays/backfill corrupt `last_seen_at`. Existing assertion `assert existing_entity.last_seen_at >= old_timestamp` (`test_entity_clustering_service.py:513`) is direction-only and passes on the mutant. Killed by T3. `detection_id` leg: param is `noqa ARG002` reserved → EQUIVALENT-knob within cluster (note). |
| C14 | `_create_entity` :279-285 `Entity.from_detection(model=…, entity_metadata=attributes)` | kwarg→None / kwarg removed (default kicks in) | 4 | `_create_entity#5`, `_create_entity#6`, `_create_entity#10` | TEST-GAP | `model=None` records `model: None` in the embedding metadata (real clobber — `Entity.get_embedding_model()` returns it). `entity_metadata=None` (mutants 6/11) *drops caller attributes entirely* — `from_detection` default replaces them with nothing; no test inspects `added_entity.entity_metadata` (test :209 asserts only type/detection_id/embedding vector). Killed by T4. |
| C15 | `_update_entity_with_detection` :241 `entity.update_seen(timestamp)` | timestamp→None | 1 | `_update_entity_with_detection#1` | TEST-GAP | Same `datetime.now(UTC)`-fallback hazard as C13, one frame deeper; `>=`-style assertions are too weak. Killed by T3. |
| C16 | `assign_entity` :174 + :200 — `attributes=attributes` → `attributes=None` on both downstream calls | kwarg→None | 2 | `assign_entity#16`, `assign_entity#59` | TEST-GAP | Attribute merge (`_update_entity_with_detection` :244-250) and initial metadata (`_create_entity` → `from_detection`) both silently stop persisting caller-supplied attributes. Killed by T2/T4. |
| C20 | `_trigger_entity_discovered_webhook` :313-327 call args | session→None; `event_id=None`; `event_id` kwarg removed | 3 | `_trigger#2`, `_trigger#5`, `_trigger#9` | TEST-GAP | `event_id` is the webhook **idempotency/dedup key** (`event_id=str(entity.id)`); losing it lets retries fire duplicate ENTITY_DISCOVERED deliveries. Mock session accepts None so nothing fails. Integration test asserts only positional args 0[1]/0[2] (`test_webhook_integration.py:306-313`). Killed by T5. |
| C21 | `_trigger_entity_discovered_webhook` :321-323 payload `first_seen_at` | key→XX/UPPER; ternary cond `and False` (always None) / `or True` (crash path) | 4 | `_trigger#19`, `_trigger#21`, `_trigger#22` | TEST-GAP | Payload schema key rename breaks every ENTITY_DISCOVERED consumer; `and False` silently nulls the timestamp, `or True` raises `AttributeError` on a None `first_seen_at` (swallowed by the except → *webhook silently never sent*, indistinguishable from success). Killed by T5. |
| C22 | `_trigger_entity_discovered_webhook` payload/kwargs — `"entity_id": str(None)`, `"detection_count"` key XX/UPPER, `event_id=str(None)` | value/`str()` arg→None; key rename | 4 | `_trigger#12`, `_trigger#23`, `_trigger#25` | TEST-GAP | Consumers get `entity_id="None"` / `event_id="None"` (corrupt dedup key pointing at a literal string) and missing `detection_count`. Killed by T5. |
| C23 | `_trigger_entity_discovered_webhook` :330-333 `except` → `logger.warning(f"...{e}", extra={...})` | msg→None; `extra`→None/removed; extra keys XX/UPPER; `str(None)` | 8 | `_trigger#26`, `_trigger#27`, `_trigger#30` | LOW-VALUE | The warning fires only when webhook delivery already failed; behavior contract ("webhook failure does not fail entity creation") is already asserted (`test_webhook_integration.py:316-353`). `extra` dict and message text are operational-log content — arguably worth a log-format test, but not core behavior. |
| C24 | `assign_entity` :218 `_trigger_entity_discovered_webhook(new_entity, None)` | `camera_id` arg→None | 1 | `assign_entity#89` | TEST-GAP | ENTITY_DISCOVERED webhook ships `camera_id: None` for every *new* entity — camera routing filters on that field downstream. Killed by T2 (payload assert via service-level test) / T5 pairing. |

**Totals** (folded from the 16 table rows, not re-typed from the cluster list): TEST-GAP **35** (C3 3 + C4 2 + C5 3 + C6 1 + C7 2 + C8 3 + C13 2 + C14 4 + C15 1 + C16 2 + C20 3 + C21 4 + C22 4 + C24 1) · LOW-VALUE **8** (C23) · EQUIVALENT **29** (C1; the `detection_id=None` members of C13/C16 whose target param is `noqa: ARG002` reserved are counted inside their clusters, which are classified by their dominant member). 35 + 8 + 29 = **72** ✓

## Drafted kill-tests (5 tests; the 6 drafted test slots target the highest-value TEST-GAP concerns — camera accumulation C3-C6 via T1, new-entity camera metadata C7/C8/C16 via T2, timestamp fidelity C13/C15 via T3, factory passthrough C14 via T4, and the whole webhook payload contract C20/C21/C22 via T5, with C23's warning-extra killed as a freebie inside T5)

Style follows the two existing files (fixtures, `AsyncMock` repo, `MagicMock` session, `patch(...get_webhook_service)`, real `Entity` instances).

```python
# =============================================================================
# WP4.4 kill-tests for entity_clustering_service survivors
# UNVERIFIED - not yet run red/green (drawn from /tmp/wp25/wp44-triage dossier)
# TDD procedure: each assert below fails on the mutant diff named in its
# docstring, and passes on the unmutated original.
# =============================================================================

# -----------------------------------------------------------------------------
# T1 — kills C4 (guard flips), C5 (write-side metadata), C6 (append value),
#      and the repeat-camera leg of C3
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_matched_entity_accumulates_unique_cameras_seen(
    self,
    clustering_service: EntityClusteringService,
    mock_entity_repository: AsyncMock,
) -> None:
    """NEM-2453: matched entity must accumulate cameras_seen without duplicates.

    Kills assign_entity#30/#31 (guard and->or, not in->in), #32 (append None),
    #24/#28/#29 (cameras_seen key broken on the read side -> prior cameras
    lost) and #33/#34/#35 (write side None / key rename).
    """
    embedding = create_sample_embedding(seed=700)
    existing_entity = create_mock_entity(entity_type="person", embedding=embedding)
    existing_entity.entity_metadata = {"cameras_seen": ["front_door"]}
    mock_entity_repository.find_by_embedding.return_value = [
        (existing_entity, 0.97),
    ]
    timestamp = datetime.now(UTC)

    # Second sighting from a NEW camera -> appended
    await clustering_service.assign_entity(
        detection_id=1101,
        entity_type="person",
        embedding=embedding,
        camera_id="backyard",
        timestamp=timestamp,
    )
    assert existing_entity.entity_metadata.get("cameras_seen") == ["front_door", "backyard"]

    # Third sighting from a KNOWN camera -> no duplicate
    await clustering_service.assign_entity(
        detection_id=1102,
        entity_type="person",
        embedding=embedding,
        camera_id="front_door",
        timestamp=timestamp + timedelta(minutes=1),
    )
    assert existing_entity.entity_metadata["cameras_seen"] == ["front_door", "backyard"]
    assert None not in existing_entity.entity_metadata["cameras_seen"]  # kills assign_entity#32


# -----------------------------------------------------------------------------
# T2 — kills C7 + C8 (new-entity metadata keys/values), C16 (attributes dropped)
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_new_entity_camera_metadata_initialized(
    self,
    clustering_service: EntityClusteringService,
    mock_entity_repository: AsyncMock,
) -> None:
    """NEM-2453/NEM-3262: new entity must seed cameras_seen + camera_id metadata.

    Kills assign_entity#68/#69 (cameras_seen key), #70/#71/#72 (camera_id
    value/key), #59 (attributes=None on _create_entity call).
    """
    mock_entity_repository.find_by_embedding.return_value = []
    embedding = create_sample_embedding(seed=701)
    timestamp = datetime.now(UTC)
    attributes = {"clothing": "blue jacket"}

    added_entity: Entity | None = None

    def capture_add(entity: Entity) -> None:
        nonlocal added_entity
        added_entity = entity

    mock_entity_repository.session.add.side_effect = capture_add

    async def mock_refresh(entity: Entity) -> None:
        entity.id = uuid.uuid4()

    mock_entity_repository.session.refresh.side_effect = mock_refresh

    await clustering_service.assign_entity(
        detection_id=1201,
        entity_type="person",
        embedding=embedding,
        camera_id="front_door",
        timestamp=timestamp,
        attributes=attributes,
    )

    assert added_entity is not None
    metadata = added_entity.entity_metadata
    assert metadata is not None, "entity_metadata lost by _create_entity kwarg clobber"
    assert metadata["cameras_seen"] == ["front_door"]
    assert metadata["camera_id"] == "front_door"
    assert metadata["clothing"] == "blue jacket"


# -----------------------------------------------------------------------------
# T3 — kills C15 (update_seen(None)) and the timestamp leg of C13.
#      NOTE: must be added to class TestTimestampUpdates (which holds the
#      clustering_service / mock_entity_repository fixtures' import scope);
#      T1/T2/T4 go in the same file as new methods of their natural classes.
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_matched_entity_uses_detection_timestamp_verbatim(
    self,
    clustering_service: EntityClusteringService,
    mock_entity_repository: AsyncMock,
) -> None:
    """last_seen_at must equal the detection timestamp, not wall-clock now().

    Kills _update_entity_with_detection#1 and assign_entity#15
    (timestamp=None -> Entity.update_seen falls back to datetime.now(UTC),
    backend/models/entity.py:187). The existing >= assertion at
    test_entity_clustering_service.py:513 cannot see this.
    """
    embedding = create_sample_embedding(seed=702)
    original_last_seen = datetime(2020, 1, 1, tzinfo=UTC)
    detection_timestamp = datetime(2023, 6, 15, 12, 30, tzinfo=UTC)
    existing_entity = create_mock_entity(
        entity_type="person",
        embedding=embedding,
        detection_count=4,
        first_seen_at=datetime(2019, 1, 1, tzinfo=UTC),
        last_seen_at=original_last_seen,
    )
    mock_entity_repository.find_by_embedding.return_value = [
        (existing_entity, 0.94),
    ]

    await clustering_service.assign_entity(
        detection_id=1301,
        entity_type="person",
        embedding=embedding,
        camera_id="driveway",
        timestamp=detection_timestamp,
    )

    assert existing_entity.last_seen_at == detection_timestamp


# -----------------------------------------------------------------------------
# T4 — kills C14 (from_detection model=/entity_metadata= kwargs clobbered)
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_entity_propagates_model_and_attributes_to_metadata(
    self,
    clustering_service: EntityClusteringService,
    mock_entity_repository: AsyncMock,
) -> None:
    """_create_entity must pass embedding_model and attributes through.

    Kills _create_entity#5/#6/#10/#11. entity_metadata=None reverts to the
    from_detection default (nothing); model=None records model: None in the
    embedding metadata blob.
    """
    mock_entity_repository.find_by_embedding.return_value = []
    embedding = create_sample_embedding(seed=703)
    timestamp = datetime.now(UTC)

    added_entity: Entity | None = None

    def capture_add(entity: Entity) -> None:
        nonlocal added_entity
        added_entity = entity

    mock_entity_repository.session.add.side_effect = capture_add

    async def mock_refresh(entity: Entity) -> None:
        entity.id = uuid.uuid4()

    mock_entity_repository.session.refresh.side_effect = mock_refresh

    await clustering_service.assign_entity(
        detection_id=1401,
        entity_type="person",
        embedding=embedding,
        camera_id="garage",
        timestamp=timestamp,
        attributes={"carrying": "package"},
    )

    assert added_entity is not None
    assert added_entity.get_embedding_model() == "clip"
    assert added_entity.entity_metadata is not None
    assert added_entity.entity_metadata["carrying"] == "package"


# -----------------------------------------------------------------------------
# T5 — kills C20 + C21 + C22 (webhook kwargs + payload keys + first_seen ternary)
#      Append to TestEntityClusteringWebhookIntegration; needs module-level
#      `import logging` (test_webhook_integration.py currently lacks it).
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_entity_discovered_payload_full_contract(
    self,
    mock_webhook_service: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """ENTITY_DISCOVERED payload, event_id and failure-path extra are contract.

    Kills _trigger_entity_discovered_webhook:
    - #2 (session -> None), #5/#9 (event_id None/removed)          [C20]
    - #19/#20 (first_seen_at key), #21/#22 (ternary and-False / or-True) [C21]
    - #12/#25 (str(None) entity_id/event_id), #23/#24 (detection_count key) [C22]
    - #26/#27/#29-#34 warning text/extra (LOW-VALUE, killed for free)  [C23]
    """
    from backend.models import Entity
    from backend.services.entity_clustering_service import EntityClusteringService

    mock_repo = MagicMock()
    mock_repo.session = AsyncMock()
    entity_id = uuid.uuid4()
    first_seen = datetime(2024, 3, 1, 8, 0, tzinfo=UTC)
    entity = Entity(
        id=entity_id,
        entity_type="person",
        trust_status="unknown",
        first_seen_at=first_seen,
        detection_count=2,
    )

    with patch(
        "backend.services.entity_clustering_service.get_webhook_service",
        return_value=mock_webhook_service,
        autospec=True,
    ):
        service = EntityClusteringService(entity_repository=mock_repo)
        await service._trigger_entity_discovered_webhook(
            entity=entity,
            camera_id="front_door",
        )

        call = mock_webhook_service.trigger_webhooks_for_event.call_args
        assert call[0][0] is mock_repo.session  # session positional survives
        payload = call[0][2]
        assert payload["entity_id"] == str(entity_id)
        assert payload["entity_type"] == "person"
        assert payload["camera_id"] == "front_door"
        assert payload["trust_status"] == "unknown"
        assert payload["first_seen_at"] == first_seen.isoformat()
        assert payload["detection_count"] == 2
        assert set(payload) == {
            "entity_id", "entity_type", "trust_status",
            "camera_id", "first_seen_at", "detection_count",
        }
        assert call.kwargs["event_id"] == str(entity_id)

    # Failure path: warning carries the structured extra, and entity creation
    # contract (no raise) holds — kills _trigger#26/#27/#29-#34.
    mock_webhook_service.trigger_webhooks_for_event.side_effect = RuntimeError("boom")
    with caplog.at_level(logging.WARNING, logger="backend.services.entity_clustering_service"):
        await service._trigger_entity_discovered_webhook(
            entity=entity,
            camera_id="front_door",
        )
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings, "webhook failure must emit a warning"
    assert getattr(warnings[0], "entity_id", None) == str(entity_id)
    assert getattr(warnings[0], "entity_type", None) == "person"
```

## Cluster → test map (kill coverage)

| Test | Target file (append) | Kills |
|---|---|---|
| T1 `test_matched_entity_accumulates_unique_cameras_seen` | `backend/tests/unit/services/test_entity_clustering_service.py` (new class `TestCamerasSeenTracking` — fixtures are module-level) | C3 (3), C4 (2), C5 (3), C6, C16 #16 |
| T2 `test_new_entity_camera_metadata_initialized` | same file, class `TestAssignEntityNewEntity` | C7 (2), C8 (3), C16 #59 |
| T3 `test_matched_entity_uses_detection_timestamp_verbatim` | same file, class `TestTimestampUpdates` | C15, C13 #15 |
| T4 `test_create_entity_propagates_model_and_attributes_to_metadata` | same file, class `TestAssignEntityNewEntity` | C14 (4), C16 #16 |
| T5 `test_entity_discovered_payload_full_contract` | `backend/tests/unit/services/test_webhook_integration.py`, class `TestEntityClusteringWebhookIntegration` (+ module-level `import logging`) | C20 (3), C21 (4), C22 (4), C24 (via payload contract on real path — see residual), C23 (8, freebie) |

**Residual not killed by drafts** (deliberate): C1 (29, EQUIVALENT log-arg/format mutants — adding a caplog-DEBUG assertion to kill these is not recommended), C13 #14 (`detection_id=None` — the param is `noqa: ARG002` reserved, behaviorally inert under all current call paths), and C24 (`assign_entity#89` — its line runs only in the mocked-session unit flow, so an exact-payload assert there duplicates T2's fixture cost; T5 covers the payload contract itself). C16 is fully covered: #16 (`attributes=None` on the `_update_entity_with_detection` call, matched path :174) dies to T1 once T1 passes attributes — add `attributes={"hair": "dark"}` + `assert existing_entity.entity_metadata["hair"] == "dark"` to the T1 body; #59 (`attributes=None` on the `_create_entity` call, new path :200) dies to T2's `metadata["clothing"]` and T4's `metadata["carrying"]` asserts.

## Notes / hazards

- `test_full_workflow_new_entity` (:993) already asserts `flush.call_count >= 1` with a comment naming `cameras_seen` tracking (:1039-1040) — the author knew the tracking existed but never asserted its content; C4-C8 are pure assert-strength gaps, not reach gaps.
- `Entity.update_seen`'s `timestamp or datetime.now(UTC)` fallback (entity.py:187) is why C13/C15 timestamp mutants survive any `>=`-style assertion — future timestamp tests must assert **equality** with a synthetic historical timestamp.
- caplog-based asserts (T5 failure path) assume the module logger propagates to root (repo convention: 8+ unit files already use `caplog` against `get_logger` loggers).
- Mocks accept `session=None`/`flush()` freely, so C20/C5/C6 mutants can only die on **payload/dict-content asserts**, never on call-count asserts.
