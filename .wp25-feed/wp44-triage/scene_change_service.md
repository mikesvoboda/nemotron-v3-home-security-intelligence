# WP4.4 triage — backend/services/scene_change_service.py

**Module:** `backend/services/scene_change_service.py` (orig 193 lines, small module)
**Meta:** `mutants/backend/services/scene_change_service.py.meta` → 88 keys, 49 killed, **39 survivors**, 0 unchecked.
**Covering test file:** `backend/tests/unit/services/test_scene_change_service.py` (549 lines).
No survivors in `classify_scene_change_type` (all 4 tests exercise its boundaries → fully killed) and none in `__init__`.

## Why so many survive (root cause)

The covering test file mocks the two collaborators in a way that discards the very
behavior the mutants change:

1. **`SceneChange` constructor is patched to `lambda **_kwargs: mock_scene_change`**
   (`test_scene_change_service.py:155-159`, 206-210, 241-245). Every constructor
   keyword — `camera_id`, `similarity_score`, `change_type`, `file_path`,
   `detected_at`, `acknowledged` — is dropped on the floor and the mock's canned
   attributes are what the payload assertions then read. So 15 constructor-field
   mutants are invisible.
2. **`session.execute` is a bare `AsyncMock` returning a canned result** (line 44),
   and the statement object passed to it is never captured or inspected. So the
   query-shape mutants (`get_scene_change`, `get_unacknowledged_for_camera`) survive:
   `execute(None)`, `where(None)`, `select(None)`, `== → !=`, `is_(False) → is_(True/None)`,
   `order_by(None)`, `limit(None)` all still "return" the canned rows.
3. **`session.add` / `session.refresh` assertions are `assert X.called`**, which cannot
   tell `add(record)` from `add(None)`.
4. **The WS payload assertions never check `detected_at` / `acknowledged_at`**
   (`test_create_scene_change_success` asserts id/camera_id/similarity_score/change_type/
   file_path/acknowledged but omits `detected_at`; `test_acknowledge_scene_change_success`
   asserts id/camera_id/acknowledged but omits `acknowledged_at`). That is exactly the
   two payload keys the rename/guard mutants pick.

## Equivalence probe (SQLAlchemy 2.0.53, repo venv)

Empirically confirmed against the repo's SQLAlchemy, deciding the EQUIVALENT calls:
- `datetime.now(None)` → `tzinfo is None` (naive) — a real divergence vs `datetime.now(UTC)`.
- `where(None)` renders `WHERE NULL`; `select(None)` renders `SELECT NULL` and
  `column_descriptions[0]['entity'] is None`; `== → !=` renders `id !=`; `order_by(None)`
  empties `_order_by_clauses`; `limit(None)` sets `_limit_clause is None`; `is_(True)`→`IS true`,
  `is_(None)`→`IS NULL` vs original `is_(False)`→`IS false`. All distinguishable from a captured statement.
- Column **defaults fire when a value is explicitly `None`** (probed on a real session):
  a NOT-NULL column with a `default` (detected_at=utc_now, change_type=UNKNOWN,
  acknowledged=False) ends up with the **default value** after flush/refresh whether the
  kwarg is set to None or omitted. → for those three columns, `None`/omission reproduce
  the original *when the original also had the default*; but `change_type=None` still
  overrides a **caller-supplied non-UNKNOWN** value → real divergence, not EQUIVALENT.

## Cluster table (39 survivors, classified)

| # | Cluster | Count | Class | Example keys (≤3) | Note |
|---|---------|-------|-------|-------------------|------|
| C1 | create_scene_change: None/omitted on columns whose model default reproduces original (`detected_at=None`/omitted, `acknowledged=None`/omitted, `acknowledged_at` omitted) | 5 | EQUIVALENT | `_mutmut_6`, `_mutmut_12`, `_mutmut_13` | detected_at/acknowledged have model defaults; acknowledged_at nullable→None anyway. Verified: default fires for explicit None == omitted == original. Not killable. |
| C2 | create_scene_change: persisted field replaced by `None` (camera_id, similarity_score, file_path, change_type override) | 4 | TEST-GAP | `_mutmut_2`, `_mutmut_3`, `_mutmut_4` | camera_id/similarity_score NOT NULL no default→IntegrityError; change_type=None overrides caller's non-UNKNOWN; file_path=None drops caller's path. |
| C3 | create_scene_change: constructor kwarg omitted for a required/caller-meaningful field | 4 | TEST-GAP | `_mutmut_8`, `_mutmut_9`, `_mutmut_11` | Same loss modes as C2 but via kwarg deletion. |
| C4 | create_scene_change: new record initialized `acknowledged=True` | 1 | TEST-GAP | `_mutmut_16` | Fresh detection marked already-acknowledged → vanishes from unack queue. |
| C5 | create_scene_change: `detected_at=datetime.now(None)` (naive tz) | 1 | TEST-GAP | `_mutmut_15` | naive timestamp stored in tz-aware column; isoformat loses offset. |
| C6 | create_scene_change: `session.add(None)` / `session.refresh(None)` | 2 | TEST-GAP | `_mutmut_17`, `_mutmut_18` | `add.called`/`refresh.called` can't distinguish the arg. |
| C7 | create_scene_change: WS payload key `"detected_at"` renamed | 2 | TEST-GAP | `_mutmut_36`, `_mutmut_37` | test never asserts payload["detected_at"]. |
| C8 | get_scene_change: statement clobbered or predicate flipped (`execute(None)`, `where(None)`, `select(None)`, `== → !=`) | 4 | TEST-GAP | `_mutmut_5`, `_mutmut_2`, `_mutmut_4` | wrong-row lookup; test returns canned result for any stmt. |
| C9 | get_unacknowledged_for_camera: query clause clobbered (`select(None)`, `where(None)`×2, `order_by(None)`, `limit(None)`, whole-select→None) | 6 | TEST-GAP | `_mutmut_4`, `_mutmut_3`, `_mutmut_2` | drops camera filter / ordering / limit. |
| C10 | get_unacknowledged_for_camera: predicate flipped (`camera_id !=`, `is_(None)`, `is_(True)`) | 3 | TEST-GAP | `_mutmut_10`, `_mutmut_9`, `_mutmut_8` | `is_(True)` returns acknowledged rows; `is_(None)` matches nothing (NOT NULL col). |
| C11 | acknowledge_scene_change: `get_scene_change(None)` wrong lookup id | 1 | TEST-GAP | `_mutmut_2` | acks wrong row; canned mock hides it. |
| C12 | acknowledge_scene_change: `acknowledged_at=datetime.now(None)` naive + `refresh(None)` | 2 | TEST-GAP | `_mutmut_7`, `_mutmut_8` | naive ack timestamp in broadcast; refresh(None) passes `refresh.called`. |
| C13 | acknowledge_scene_change: WS payload key `"acknowledged_at"` renamed | 2 | TEST-GAP | `_mutmut_22`, `_mutmut_23` | test never asserts payload["acknowledged_at"]. |
| C14 | acknowledge_scene_change: guard `if acknowledged_at` → `and False` (always falsy → ack ts lost) | 1 | TEST-GAP | `_mutmut_24` | forces `else None`; payload ack ts None, unasserted. |
| C15 | acknowledge_scene_change: guard `if acknowledged_at` → `or True` (always truthy) | 1 | EQUIVALENT | `_mutmut_25` | acknowledged_at is always truthy when broadcast fires (just set to now), so original takes isoformat branch anyway → same result on every reachable path. Not killable. |

**Totals:** EQUIVALENT 7 (C1,C15) · TEST-GAP 32 (C2–C14) · LOW-VALUE 0. Sum = 39.

## Covering test file (file:line)

- `backend/tests/unit/services/test_scene_change_service.py`
  - fixtures `mock_db_session:38`, `mock_websocket_emitter:49`, `scene_change_service:56`
  - `TestCreateSceneChange::test_create_scene_change_success:132` — payload asserts omit `detected_at` (C7), constructor patched to discard kwargs (C2/C3/C4/C5).
  - `TestGetSceneChange::test_get_scene_change_found:284` — `execute` canned (C8).
  - `TestGetUnacknowledgedForCamera::test_get_unacknowledged_for_camera_success:503` — canned `scalars().all()` (C9/C10).
  - `TestAcknowledgeSceneChange::test_acknowledge_scene_change_success:345` — payload asserts omit `acknowledged_at` (C13/C14); `acknowledged_at is not None` but not tz-checked (C12).

## Drafted tests (UNVERIFIED — not yet run red/green)

Target file: `backend/tests/unit/services/test_scene_change_service.py`. Follows existing
style (`@pytest.mark.asyncio`, module fixtures, `pytest.MonkeyPatch`). TDD procedure for each:
add the test, run it against the **mutant copy** → assert fails on the changed line; run
against `backend/services/scene_change_service.py` original → passes.

```python
# ---- Draft 1: kill C8 + C11 (get_scene_change query shape) ---- UNVERIFIED ----
    @pytest.mark.asyncio
    async def test_get_scene_change_builds_id_equality_query(
        self,
        scene_change_service: SceneChangeService,
        mock_db_session: AsyncMock,
    ) -> None:
        """Captured statement must be a real SELECT ... WHERE id == <given id>."""
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db_session.execute.return_value = mock_result

        await scene_change_service.get_scene_change(scene_change_id=123)

        stmt = mock_db_session.execute.call_args[0][0]
        assert stmt is not None                                   # kills execute(None) _2
        assert stmt.column_descriptions[0].get("entity") is SceneChange  # kills select(None) _4
        sql = str(stmt.compile())
        assert "scene_changes.id = :" in sql                     # kills !=_5 and where(None)_3
        assert 123 in stmt.compile().params.values()             # kills wrong-id lookup
```
Add the same capture inside `test_acknowledge_scene_change_success` asserting the
`get_scene_change` lookup used the passed id (kills C11 `_mutmut_2`):
```python
# inside acknowledge success test, after the call: UNVERIFIED
        stmt = mock_db_session.execute.call_args[0][0]
        assert 123 in stmt.compile().params.values()   # get_scene_change(None) drops the id
```

```python
# ---- Draft 2: kill C9 + C10 (get_unacknowledged_for_camera query shape) ---- UNVERIFIED ----
    @pytest.mark.asyncio
    async def test_get_unacknowledged_query_filters_orders_limits(
        self,
        scene_change_service: SceneChangeService,
        mock_db_session: AsyncMock,
    ) -> None:
        """Statement must filter on camera_id AND unacknowledged, order DESC, apply LIMIT."""
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[])
        mock_result = AsyncMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        mock_db_session.execute.return_value = mock_result

        await scene_change_service.get_unacknowledged_for_camera(
            camera_id="front_door", limit=50
        )

        stmt = mock_db_session.execute.call_args[0][0]
        assert stmt is not None                                   # _mutmut_2 whole→None
        assert stmt.column_descriptions[0].get("entity") is SceneChange  # _mutmut_7 select(None)
        sql = str(stmt.compile())
        assert "scene_changes.camera_id = :" in sql              # _mutmut_6 where(None), _mutmut_8 !=
        assert "acknowledged IS false" in sql                     # _mutmut_5 where(None), _mutmut_9 is_(None), _mutmut_10 is_(True)
        assert "detected_at DESC" in sql                          # _mutmut_4 order_by(None)
        assert "LIMIT" in sql                                     # _mutmut_3 limit(None)
        compiled = stmt.compile()
        assert "front_door" in compiled.params.values()          # _mutmut_8 camera_id != / None
        assert 50 in compiled.params.values()                      # _mutmut_3 limit
```

```python
# ---- Draft 3: kill C2 + C3 + C4 (create_scene_change constructor fields) ---- UNVERIFIED ----
    @pytest.mark.asyncio
    async def test_create_scene_change_persists_all_fields(
        self,
        scene_change_service: SceneChangeService,
        mock_db_session: AsyncMock,
        mock_websocket_emitter: AsyncMock,
    ) -> None:
        """The SceneChange constructor must receive every persisted field, unmodified."""
        captured: dict = {}

        def recorder(**kwargs):
            captured.update(kwargs)
            m = MagicMock(spec=SceneChange)
            m.id = 1
            m.camera_id = kwargs.get("camera_id")
            m.similarity_score = kwargs.get("similarity_score")
            m.change_type = kwargs.get("change_type")
            m.file_path = kwargs.get("file_path")
            m.detected_at = kwargs.get("detected_at")
            m.acknowledged = kwargs.get("acknowledged")
            return m

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("backend.services.scene_change_service.SceneChange", recorder)
            await scene_change_service.create_scene_change(
                camera_id="front_door",
                similarity_score=0.3,
                change_type=SceneChangeType.VIEW_TAMPERED,
                file_path="/path/to/frame.jpg",
            )

        assert captured.get("camera_id") == "front_door"          # _mutmut_2 None, _mutmut_8 omitted
        assert captured.get("similarity_score") == 0.3            # _mutmut_3 None, _mutmut_9 omitted
        assert captured.get("change_type") == SceneChangeType.VIEW_TAMPERED  # _mutmut_4 None, _mutmut_10 omitted
        assert "file_path" in captured and captured["file_path"] == "/path/to/frame.jpg"  # _mutmut_5, _mutmut_11
        assert captured.get("acknowledged") is False              # _mutmut_16 True
```

```python
# ---- Draft 4: kill C5 + C12 (tz-awareness of detected_at / acknowledged_at) ---- UNVERIFIED ----
    @pytest.mark.asyncio
    async def test_create_scene_change_detected_at_is_utc_aware(
        self,
        scene_change_service: SceneChangeService,
        mock_db_session: AsyncMock,
    ) -> None:
        captured: dict = {}
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "backend.services.scene_change_service.SceneChange",
                lambda **kwargs: captured.update(kwargs) or MagicMock(spec=SceneChange),
            )
            await scene_change_service.create_scene_change(
                camera_id="cam", similarity_score=0.4
            )
        assert captured["detected_at"].tzinfo is not None  # _mutmut_15 datetime.now(None)
```
```python
# tz-awareness on the ack path — add to test_acknowledge_scene_change_success (UNVERIFIED):
        assert mock_scene_change.acknowledged_at.tzinfo is not None   # _mutmut_7 datetime.now(None)
        assert mock_db_session.refresh.call_args[0][0] is mock_scene_change  # _mutmut_8 refresh(None)
        assert mock_db_session.add.call_args[0][0] is not None   # C6: add(record) not add(None)
```
Add `assert mock_db_session.add.call_args[0][0] is mock_scene_change` to the create
success test to kill C6 `_mutmut_17`.

```python
# ---- Draft 5: kill C7 + C13 + C14 (WS payload keys) ---- UNVERIFIED ----
# In test_create_scene_change_success, extend the payload block (UNVERIFIED):
        assert "detected_at" in payload                    # _mutmut_36 XX…, _mutmut_37 DETECTED_AT
        assert payload["detected_at"] == mock_scene_change.detected_at.isoformat()

# In test_acknowledge_scene_change_success, extend the payload block (UNVERIFIED):
        assert "acknowledged_at" in payload                # _mutmut_22 XX…, _mutmut_23 ACKNOWLEDGED_AT
        assert payload["acknowledged_at"] == mock_scene_change.acknowledged_at.isoformat()  # _mutmut_24 and False → None
```
C15 (`or True`, `_mutmut_25`) is EQUIVALENT — no assertion can kill it (both branches
yield the isoformat value because acknowledged_at is always truthy when the emit fires).
C1 keys are likewise EQUIVALENT (SQLAlchemy applies the column default for None/omitted).
