# WP4.4 Triage Dossier — backend/services/face_recognition_service.py

**Survivors:** 72 of 135 mutants (63 killed, 0 unchecked). All survivors live in 3 functions:
`FaceRecognitionService.__init__` (8), `get_person_appearances` (23), `identify_face_event` (41).

**Diffs obtained via** `uv run mutmut show <key>` (all 72 succeeded; no manual fallback needed).

## Covering tests (from mutants/mutmut-stats.json → tests_by_mangled_function_name)

| Function | Test file | Class / lines |
|---|---|---|
| `__init__` | `backend/tests/unit/services/test_face_recognition_service.py` + `backend/tests/unit/api/routes/test_face_recognition.py` | instantiated in `TestGetPersonAppearances.service` fixture (services file :24-27) and every `TestIdentifyFaceEventService` test (:1267-1475) |
| `get_person_appearances` | `backend/tests/unit/services/test_face_recognition_service.py` | `TestGetPersonAppearances` :21-258 |
| `identify_face_event` | `backend/tests/unit/api/routes/test_face_recognition.py` | `TestIdentifyFaceEventService` :1267-1475 |

**Root cause of the whole TEST-GAP population:** every covering test mocks
`session.execute = AsyncMock(side_effect=[...])` and never inspects the statement passed, nor
`session.add`'s argument. Any change confined to the SQLAlchemy statement objects (filters,
order_by, limit/offset, select entity, `.where(None)`) is invisible to the suite. Log-line
mutants survive trivially (no caplog assertions).

Verified locally (render-only, no tests executed): `.where(None)` renders `WHERE NULL`,
`select(None)` renders `SELECT NULL FROM ...`, `order_by(None)` drops the ORDER BY,
`limit(None)` renders `LIMIT -1`, `offset(None)` drops OFFSET — so string-compare assertions
against a locally-built reference statement kill all statement mutants without DB access.

## Cluster table (counts sum to 72)

| # | Cluster (pattern) | Function | Count | Keys (≤3 examples) | Class |
|---|---|---|---|---|---|
| C1 | Constructor threshold assignment clobbered: `self._similarity_threshold = similarity_threshold` → `= None` | `__init__` (src :93) | 1 | `__init____mutmut_1` | **TEST-GAP** |
| C2 | `__init__` logger.info format-string / arg removal or `None`-swap (`"FaceRecognitionService initialized..."` → `None`/removed) | `__init__` (:94-97) | 4 | `__init____mutmut_2`, `_3`, `_4` | EQUIVALENT |
| C3 | Log message **text-case / XX-wrapping** tweaks on 4 init/info/debug log lines (`"XX...XX"`, lowercase, UPPERCASE) | `__init__`, `get_person_appearances`, `identify_face_event` | 12 | `__init____mutmut_6`, `get_person_appearances__mutmut_60`, `identify_face_event__mutmut_47` | EQUIVALENT |
| C4 | Log format-string / arg **removal or None-swap** on info/debug calls ("Retrieved %d appearances...", "Created embedding...", "Identified face event...") | `get_person_appearances` (:753-758), `identify_face_event` (:826-831, :835-840) | 24 | `get_person_appearances__mutmut_52`, `identify_face_event__mutmut_39`, `_50` | EQUIVALENT |
| C5 | Appearances person-filter clobbered: `select(FaceDetectionEvent)` → `select(None)`, `.where(matched_person_id == person_id)` → `.where(None)` / `!=` | `get_person_appearances` (:713-717) | 3 | `get_person_appearances__mutmut_9`, `_10`, `_11` | **TEST-GAP** |
| C6 | Optional camera filter condition inverted: `if camera_id is not None:` → `is None` | `get_person_appearances` (:724) | 1 | `get_person_appearances__mutmut_15` | **TEST-GAP** |
| C7 | Pagination/ordering clobbered: `order_by(timestamp.desc())` → `order_by(None)`; `stmt.limit(limit).offset(offset)` → `stmt = None` / `offset(None)` / `limit(None)` | `get_person_appearances` (:733-734) | 4 | `get_person_appearances__mutmut_25`, `_26`, `_27` | **TEST-GAP** |
| C8 | Count-then-page execute plumbing clobbered: `count_stmt = select(func.count())...` → `None` / `select(None)...`; `session.execute(count_stmt)` / `session.execute(stmt)` → `execute(None)` | `get_person_appearances` (:728-735) | 4 | `get_person_appearances__mutmut_16`, `_18`, `_30` | **TEST-GAP** |
| C9 | identify_face_event lookup-query clobbered: `select(FaceDetectionEvent).where(id == event_id)` / `select(KnownPerson).where(id == known_person_id)` → whole stmt `None`, `where(None)`, `select(None)`, `!=`; `execute(event_stmt/person_stmt)` → `execute(None)` | `identify_face_event` (:791-804) | 10 | `identify_face_event__mutmut_1`, `_4`, `_15` | **TEST-GAP** |
| C10 | High-quality embedding construction clobbered: `new_embedding = FaceEmbedding(...)` → `None`; kwargs `person_id=`/`embedding=`/`quality_score=` set to `None` or line removed; `session.add(new_embedding)` → `add(None)` | `identify_face_event` (:818-824) | 9 | `identify_face_event__mutmut_28`, `_29`, `_36` | **TEST-GAP** |

Total: 1+4+12+24+3+1+4+4+10+9 = **72** ✓
TEST-GAP = 32 (C1,C5,C6,C7,C8,C9,C10); EQUIVALENT = 40 (C2,C3,C4); LOW-VALUE = 0.

### Cluster notes

- **C2/C3/C4 (EQUIVALENT):** every one is inside a `logger.info`/`logger.debug` call. Text-case and
  XX-wrap mutants leave `%`-specs intact; arg-removal/`None`-swap mutants only change the `%`
  formatting of a log message that tests never capture (no caplog usage anywhere in either test
  file). No behavior or API output changes. Nobody should assert log-message spelling. Note
  `__init____mutmut_2..5`: `logger.info(None, self._similarity_threshold)` does *not* raise
  (logger handles non-str msg), so even runtime-error mutants here are inert.
- **C5 (TEST-GAP, src :713-717):** all 6 appearance tests mock `session.execute` by positional
  `side_effect` and patch `get_known_person`; the built statement is never asserted. A `!=` flip or
  dropped WHERE silently returns the wrong person's timeline in production; tests pass.
  `test_get_appearances_returns_correct_structure` (:78-130) asserts only mock-echoed row fields.
- **C6 (TEST-GAP, src :724):** no appearance test ever passes `camera_id=`, and none asserts the
  filter's presence — the inverted condition ("filter when NOT given") is unexercised.
- **C7 (TEST-GAP, src :733-734):** `test_get_appearances_returns_total_count_independent_of_limit`
  (:217-258) passes `limit=1` but the mock returns the row regardless — limit/offset/ordering are
  never read off the statement. `order_by(None)` silently breaks "most recent first".
- **C8 (TEST-GAP, src :728-735):** tests verify the count *return value* (mocked) but never that
  execute received `count_stmt` first and the page stmt second; `execute(None)` passes.
- **C9 (TEST-GAP, src :791-804):** `TestIdentifyFaceEventService` (:1267-1475) feeds results via
  `mock_db.execute.side_effect` and asserts only ValueError texts, return dict, event mutations and
  `commit` — never the two statements or the execute args. With a real DB, `where(None)`/`!=`/
  `execute(None)` mean wrong-row or crash; unit tests are blind to it.
- **C10 (TEST-GAP, src :818-824):** `test_service_identify_face_event_creates_embedding` (:1308-1344)
  asserts only `mock_db.add.assert_called_once()` — argument shape unchecked. So `person_id=None`,
  `embedding=None`, `quality_score=None`, `add(None)` all survive. **Exception:** key
  `identify_face_event__mutmut_35` (removes `source_image_path=None,`) is semantically equivalent —
  the column (`backend/models/face_identity.py:140`) defaults to NULL and is already None; this one
  key inside C10 is not killable and is excluded from the drafted test's kill claim.
- **C1 (TEST-GAP, src :93):** mutant sets `self._similarity_threshold = None`; the property
  (:99-102) and `match_face` default threshold (:423-424) silently become None (all matches match).
  `__init__` is executed by 13 tests (both files) but no test reads `.similarity_threshold`.

## Drafted kill-tests

### T1 → kills C1 (1 survivor) — target: `backend/tests/unit/services/test_face_recognition_service.py` (append at module level)

```python
# // UNVERIFIED - not yet run red/green
def test_init_preserves_similarity_threshold() -> None:
    """Default and explicit similarity thresholds must be stored and exposed.

    TDD: on __init____mutmut_1 (self._similarity_threshold = None) the first
    assert fails (None != DEFAULT_MATCH_THRESHOLD); passes on original.
    """
    from backend.services.face_recognition_service import (
        DEFAULT_MATCH_THRESHOLD,
        FaceRecognitionService,
    )

    assert FaceRecognitionService().similarity_threshold == DEFAULT_MATCH_THRESHOLD
    assert FaceRecognitionService(similarity_threshold=0.42).similarity_threshold == 0.42
```

### T2 → kills C5 + C6 + C7 + C8 (12 survivors) — target: `backend/tests/unit/services/test_face_recognition_service.py` (append inside `class TestGetPersonAppearances`, after :258)

```python
# // UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_get_appearances_builds_expected_count_and_page_queries(
    self, service: FaceRecognitionService
) -> None:
    """The count query and the paginated main query must be the real statements.

    Captures both session.execute() statements and string-compares them against
    locally-built references (verified render behavior: where(None) renders
    'WHERE NULL', select(None) renders 'SELECT NULL FROM', order_by(None) drops
    ORDER BY, limit(None) renders 'LIMIT -1', offset(None) drops OFFSET).

    TDD: fails on every C5/C6/C7/C8 mutant (statement None / NULL / != / missing
    filter, order, limit or offset / execute(None) -> call_args arg None);
    passes on original.
    """
    from sqlalchemy import func, select
    from sqlalchemy.orm import selectinload

    mock_session = AsyncMock()

    mock_person = MagicMock(spec=KnownPerson)
    mock_person.id = 1
    mock_person.name = "John Doe"

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 0

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    with patch.object(service, "get_known_person", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_person

        result = await service.get_person_appearances(
            mock_session, person_id=1, camera_id="front_door", limit=5, offset=10
        )

    assert result is not None
    assert mock_session.execute.call_count == 2

    # execute call #1 must be the count-over-subquery, call #2 the page query
    count_stmt = mock_session.execute.call_args_list[0].args[0]
    page_stmt = mock_session.execute.call_args_list[1].args[0]

    base = (
        select(FaceDetectionEvent)
        .where(FaceDetectionEvent.matched_person_id == 1)
        .options(selectinload(FaceDetectionEvent.camera))
        .where(FaceDetectionEvent.camera_id == "front_door")
    )
    assert str(count_stmt) == str(select(func.count()).select_from(base.subquery()))
    assert str(page_stmt) == str(
        base.order_by(FaceDetectionEvent.timestamp.desc()).limit(5).offset(10)
    )
```

### T3 → kills C9 (10 survivors) — target: `backend/tests/unit/api/routes/test_face_recognition.py` (append inside `class TestIdentifyFaceEventService`, after :1475)

```python
# // UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_service_identify_face_event_queries_lookup_rows_by_id() -> None:
    """Both lookups must select the right entity filtered by the right id."""
    from sqlalchemy import select

    from backend.models.face_identity import FaceDetectionEvent, KnownPerson
    from backend.services.face_recognition_service import FaceRecognitionService

    service = FaceRecognitionService()
    mock_db = AsyncMock()

    mock_event = MagicMock(spec=FaceDetectionEvent)
    mock_event.id = 100
    mock_event.is_unknown = True
    mock_event.quality_score = 0.5  # below 0.7: no embedding branch
    mock_event.embedding = np.zeros(512, dtype=np.float32).tobytes()

    mock_person = MagicMock(spec=KnownPerson)
    mock_person.id = 1
    mock_person.name = "John Doe"

    mock_event_result = MagicMock()
    mock_event_result.scalar_one_or_none.return_value = mock_event
    mock_person_result = MagicMock()
    mock_person_result.scalar_one_or_none.return_value = mock_person

    mock_db.execute.side_effect = [mock_event_result, mock_person_result]

    result = await service.identify_face_event(mock_db, event_id=100, known_person_id=1)
    assert result["success"] is True

    assert mock_db.execute.call_count == 2
    event_stmt = mock_db.execute.call_args_list[0].args[0]
    person_stmt = mock_db.execute.call_args_list[1].args[0]
    assert str(event_stmt) == str(
        select(FaceDetectionEvent).where(FaceDetectionEvent.id == 100)
    )
    assert str(person_stmt) == str(select(KnownPerson).where(KnownPerson.id == 1))

    # // UNVERIFIED - not yet run red/green. TDD: each C9 mutant (stmt None,
    # where(None) -> 'WHERE NULL', select(None) -> 'SELECT NULL', != flip,
    # execute(None) -> arg None) breaks one of the two str-compare asserts;
    # both hold on the original.
```

### T4 → kills C10 (8 of 9; `identify_face_event__mutmut_35` is source-equivalent, see cluster note) — target: `backend/tests/unit/api/routes/test_face_recognition.py` (append inside `class TestIdentifyFaceEventService`)

```python
# // UNVERIFIED - not yet run red/green
@pytest.mark.asyncio
async def test_service_identify_face_event_stores_full_embedding_fields() -> None:
    """The created FaceEmbedding must carry person_id, event embedding and event quality."""
    from backend.models.face_identity import FaceEmbedding, FaceDetectionEvent, KnownPerson
    from backend.services.face_recognition_service import FaceRecognitionService

    service = FaceRecognitionService()
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    embedding_bytes = np.arange(512, dtype=np.float32).tobytes()

    mock_event = MagicMock(spec=FaceDetectionEvent)
    mock_event.id = 100
    mock_event.is_unknown = True
    mock_event.quality_score = 0.92  # above 0.7: embedding branch
    mock_event.embedding = embedding_bytes

    mock_person = MagicMock(spec=KnownPerson)
    mock_person.id = 1
    mock_person.name = "John Doe"

    mock_event_result = MagicMock()
    mock_event_result.scalar_one_or_none.return_value = mock_event
    mock_person_result = MagicMock()
    mock_person_result.scalar_one_or_none.return_value = mock_person

    mock_db.execute.side_effect = [mock_event_result, mock_person_result]

    result = await service.identify_face_event(mock_db, event_id=100, known_person_id=1)

    assert result["success"] is True
    assert result["created_embedding"] is True
    mock_db.add.assert_called_once()

    new_embedding = mock_db.add.call_args[0][0]
    assert isinstance(new_embedding, FaceEmbedding)  # kills _28 (add(None)) / _36
    assert new_embedding.person_id == 1              # kills _29 (person_id=None) / _32 (kwarg removed)
    assert bytes(new_embedding.embedding) == embedding_bytes  # kills _30 / _33
    assert new_embedding.quality_score == 0.92       # kills _31 / _34
    assert new_embedding.source_image_path is None   # documents _35 (equivalent: column default NULL)

    # TDD: each C10 mutant zeroes one field (SQLAlchemy constructor stores None for
    # omitted kwargs pre-flush — verified reasoning, models/face_identity.py:130-140);
    # exactly one assert fails per mutant, all pass on original.
```

## Verification loop for the fix lane (not run here — read-only triage)

1. Apply T1-T4 to the two test files (serial pytest lane only).
2. Red-prove per key: for each survivor key in C1/C5/C6/C7/C8/C9/C10, run the mapped test against
   the mutant copy (`mutants/backend/services/face_recognition_service.py` variant for that key) —
   expect FAILED; run against original `backend/services/face_recognition_service.py` — expect PASSED.
3. Expected post-fix kill rate for this module: 63/135 → 95/135 (survivors 72 → 40, all log-text
   EQUIVALENT; recommend marking C2/C3/C4 as an accepted-equivalence group in the WP4.4 ledger
   rather than writing caplog asserts for 40 mutants).
